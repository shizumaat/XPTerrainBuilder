# OrthoStudio XP, Copyright (C) 2026 radioharris. Free software under the GNU GPL: see LICENSE.
# Additional terms (GPL v3 section 7) apply to radioharris's material in this file: see NOTICE.
# Origin: OrthoStudio XP (github.com/radioharris/orthostudio-xp), src/orthostudio/textures/encode.py
#   @ 7c028d82dcc59a27296972973aa0663ef37efddc; LICENSE/NOTICE: THIRD_PARTY/orthostudio-xp/.
# Modified for XPTerrainBuilder, 2026-10-17: the nvcompress fallback is dropped (our
#   DDSTool/nvcompress subprocess path in O4_Imagery_Utils stays the default); the header comes
#   from O4_DDS_File; the O4_DDS_ENCODER flag, the file writer and the process pool are added.
"""In-process BC1/BC3 (DXT1/DXT5) texture encoding through ``ispc_texcomp``.

``O4_DDS_ENCODER=inproc`` makes ``O4_Imagery_Utils.convert_texture`` encode here instead of
running DDSTool (macOS) / nvcompress (Windows, Linux) per texture; the default is ``tool``
(owner RULINGS 2026-10-17a Q5: off until the owner's sim read). Spec:
``docs/specs/texture-encode-spec.md`` section 4.

Post-passes kept from OrthoStudio XP's field work: the optimal single-colour endpoint table
for uniform blocks (:func:`encode_flat_blocks`), forced four-colour mode
(:func:`force_four_colour_mode`) and the ispc_texcomp 1.0.1 BC1 over-allocation trim.
"""

from __future__ import annotations

import concurrent.futures as _cf
import multiprocessing as _mp
import os
import threading
from functools import cache

import numpy as np

import O4_DDS_File as dds
from O4_DDS_Mips import MipMode, mip_chain
from O4_DDS_Refine import refine_blocks

__all__ = ["DEFAULT_MIP_MODE", "ENCODER_ENV", "chosen_encoder", "count_three_colour_blocks",
           "encode_dds", "encode_file", "encode_flat_blocks", "encode_level", "encode_texture",
           "force_four_colour_mode", "ispc_available", "shutdown_pool"]

#: The flag: ``inproc`` (this module, default) or ``tool`` (today's subprocess converter).
ENCODER_ENV = "O4_DDS_ENCODER"
#: The mip filter of today's converters, MEASURED (spec section 5 step 1, 2026-10-17, three
#: real textures): DDSTool (macOS) and nvcompress -fast both filter RGB in linear light with a
#: 2.2 power law — their decoded mips sit closest to the gamma-2.2 chain at every level
#: (L8: 32.2 dB vs 32.0 sRGB vs 29.4 stored-value), with a flat mean offset equal to level 0's.
DEFAULT_MIP_MODE: MipMode = "gamma22"


@cache
def ispc_available() -> bool:
    """Is the ``ispc_texcomp`` wheel importable here?"""
    try:
        import ispc_texcomp  # noqa: F401
    except ImportError:
        return False
    return True


def chosen_encoder(environ=None) -> str:
    """``'inproc'`` (the default, owner RULINGS 2026-10-17d) when the wheel imports, else ``'tool'``.

    ``O4_DDS_ENCODER=tool`` opts back into today's subprocess converter; any other value,
    unset included, is ``inproc``.
    """
    value = (environ if environ is not None else os.environ).get(ENCODER_ENV, "")
    if value.strip().lower() == "tool" or not ispc_available():
        return "tool"
    return "inproc"


def as_rgba(image: np.ndarray) -> np.ndarray:
    """Return a C-contiguous (h, w, 4) uint8 view/copy; an RGB input gets an opaque alpha."""
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] not in (3, 4):
        raise ValueError("expected a (height, width, 3|4) uint8 array")
    if image.shape[2] == 3:
        rgba = np.empty((*image.shape[:2], 4), dtype=np.uint8)
        rgba[:, :, :3] = image
        rgba[:, :, 3] = 255
        return rgba
    return np.ascontiguousarray(image)


def _pad_to_blocks(rgba: np.ndarray) -> np.ndarray:
    """Pad with edge replication so both sides are multiples of 4 (nvtt clamps the same way)."""
    h, w = rgba.shape[:2]
    ph, pw = (-h) % 4, (-w) % 4
    if ph == 0 and pw == 0:
        return rgba
    return np.pad(rgba, ((0, ph), (0, pw), (0, 0)), mode="edge")


def force_four_colour_mode(blocks: bytes | bytearray, fmt: str) -> bytes:
    """Rewrite BC1 colour blocks so that ``color0 > color1`` (or indices 0 when equal).

    X-Plane samples DXT1 in 3-colour mode as transparent black for index 3; ispc_texcomp already
    avoids it; this makes the invariant hold whatever it does.
    """
    bs = dds.BLOCK_FORMATS[fmt][1]
    arr = np.frombuffer(blocks, dtype=np.uint8).reshape(-1, bs).copy()
    colour = arr[:, bs - 8 :]
    c0 = colour[:, 0].astype(np.uint16) | (colour[:, 1].astype(np.uint16) << 8)
    c1 = colour[:, 2].astype(np.uint16) | (colour[:, 3].astype(np.uint16) << 8)
    swap = c0 < c1
    if swap.any():
        ends = colour[swap, 0:4].copy()
        colour[swap, 0:2] = ends[:, 2:4]
        colour[swap, 2:4] = ends[:, 0:2]
        colour[swap, 4:8] ^= 0x55  # idx 0<->1, 2<->3 in every 2-bit field
    equal = c0 == c1
    if equal.any():
        colour[equal, 4:8] = 0
    return arr.tobytes()


def count_three_colour_blocks(blocks: bytes | memoryview, fmt: str) -> tuple[int, int]:
    """Return ``(color0 < color1, color0 == color1 with a non-zero index)`` block counts."""
    bs = dds.BLOCK_FORMATS[fmt][1]
    arr = np.frombuffer(blocks, dtype=np.uint8).reshape(-1, bs)
    colour = arr[:, bs - 8 :]
    c0 = colour[:, 0].astype(np.uint16) | (colour[:, 1].astype(np.uint16) << 8)
    c1 = colour[:, 2].astype(np.uint16) | (colour[:, 3].astype(np.uint16) << 8)
    equal_bad = (c0 == c1) & (colour[:, 4:8] != 0).any(axis=1)
    return int((c0 < c1).sum()), int(equal_bad.sum())


@cache
def _single_colour_table(bits: int) -> tuple[np.ndarray, np.ndarray]:
    """For every 8-bit value, the endpoint pair whose 2/3-1/3 interpolant is closest to it."""
    e = np.arange(1 << bits)
    expanded = (e << (8 - bits)) | (e >> (2 * bits - 8))
    interp = (2 * expanded[:, None] + expanded[None, :] + 1) // 3  # decoder's palette entry 2
    err = np.abs(interp[None, :, :] - np.arange(256)[:, None, None])
    best = err.reshape(256, -1).argmin(axis=1)
    return (best // (1 << bits)).astype(np.uint16), (best % (1 << bits)).astype(np.uint16)


def encode_flat_blocks(blocks: bytes, rgba: np.ndarray, fmt: str) -> bytes:
    """Re-encode every block whose 16 pixels share one RGB with the optimal endpoint pair.

    ispc_texcomp quantises a uniform block to the nearest 5:6:5 colour (up to 4 codes off);
    nvtt, like stb_dxt, picks two endpoints whose interpolant lands within one code. Sea
    textures are 75-85 % uniform blocks, where this is worth 4-6 dB.
    """
    h, w = rgba.shape[:2]
    if h % 4 or w % 4 or rgba.shape[2] != 4 or not rgba.flags.c_contiguous:
        raise ValueError("expected a C-contiguous RGBA image with sides multiple of 4")
    pixels = rgba.view(np.uint32).reshape(h // 4, 4, w // 4, 4) & np.uint32(0x00FFFFFF)
    same = (pixels == pixels[:, :1, :, :1]).all(axis=(1, 3))
    idx = np.flatnonzero(same)
    if idx.size == 0:
        return blocks
    colours = rgba.reshape(h // 4, 4, w // 4, 4, 4)[:, 0, :, 0, :3].reshape(-1, 3)[idx]
    r0, r1 = (t[colours[:, 0]] for t in _single_colour_table(5))
    g0, g1 = (t[colours[:, 1]] for t in _single_colour_table(6))
    b0, b1 = (t[colours[:, 2]] for t in _single_colour_table(5))
    c0 = (r0 << 11) | (g0 << 5) | b0
    c1 = (r1 << 11) | (g1 << 5) | b1
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    # every pixel uses palette entry 2, or entry 3 when the endpoints had to be swapped
    indices = np.where(swap, np.uint32(0xFFFFFFFF), np.uint32(0xAAAAAAAA))
    indices = np.where(c0 == c1, np.uint32(0), indices).astype(np.uint32)
    packed = np.empty((idx.size, 8), dtype=np.uint8)
    packed[:, 0] = c0 & 0xFF
    packed[:, 1] = c0 >> 8
    packed[:, 2] = c1 & 0xFF
    packed[:, 3] = c1 >> 8
    packed[:, 4:8] = indices.view(np.uint8).reshape(-1, 4)
    bs = dds.BLOCK_FORMATS[fmt][1]
    arr = np.frombuffer(blocks, dtype=np.uint8).reshape(-1, bs).copy()
    arr[idx, bs - 8 :] = packed
    return arr.tobytes()


def _encode_blocks_ispc(rgba: np.ndarray, fmt: str) -> bytes:
    import ispc_texcomp as mod

    padded = _pad_to_blocks(rgba)
    h, w = padded.shape[:2]
    surface = mod.RGBASurface(padded, w, h)
    if fmt == "bc1":
        # ispc_texcomp 1.0.1 allocates width*height bytes for BC1 (twice the block data);
        # the blocks are contiguous at the start, the tail is uninitialised.
        return mod.compress_blocks_bc1(surface)[: dds.level_size(w, h, fmt)]
    return mod.compress_blocks_bc3(surface)


def _finish_level(blocks: bytes, rgba: np.ndarray, fmt: str, refine_passes: int) -> bytes:
    padded = _pad_to_blocks(rgba)
    blocks = encode_flat_blocks(blocks, padded, fmt)
    if refine_passes > 0:
        blocks = refine_blocks(blocks, padded, fmt, refine_passes)
    return force_four_colour_mode(blocks, fmt)


def encode_level(image: np.ndarray, fmt: str, *, refine_passes: int = 0) -> bytes:
    """ispc_texcomp blocks of one level plus the flat-block and 4-colour post-passes."""
    rgba = as_rgba(image)
    return _finish_level(_encode_blocks_ispc(rgba, fmt), rgba, fmt, refine_passes)


def encode_dds(
    image: np.ndarray,
    fmt: str,
    mips: bool = True,
    *,
    mip_mode: MipMode = DEFAULT_MIP_MODE,
    refine_passes: int = 0,
) -> bytes:
    """Encode an (h, w, 3|4) uint8 image to a complete DDS file image (header + levels).

    ``fmt`` is ``'bc1'`` (DXT1, alpha dropped) or ``'bc3'`` (DXT5). With ``mips`` the full
    chain down to 1x1 is generated with ``mip_chain(mode=mip_mode)``; sides must then be
    powers of two. ``refine_passes`` adds least-squares endpoint refinement (slow, numpy).
    """
    dds.level_size(4, 4, fmt)  # ValueError on an unknown format
    rgba = as_rgba(image)
    h, w = rgba.shape[:2]
    levels = mip_chain(rgba, mode=mip_mode) if mips else [rgba]
    blobs = [encode_level(lvl, fmt, refine_passes=refine_passes) for lvl in levels]
    return dds.assemble(w, h, fmt, blobs)


def _load_rgba(source) -> np.ndarray:
    """An ndarray as is; a path (a JPEG or PNG on disk) decoded to RGB(A) uint8."""
    if isinstance(source, np.ndarray):
        return source
    from PIL import Image

    with Image.open(source) as image:
        mode = "RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB"
        return np.asarray(image.convert(mode))


def encode_file(source, fmt: str, path: str, mip_mode: MipMode = DEFAULT_MIP_MODE) -> int:
    """Encode ``source`` (an image path or an (h, w, 3|4) array) and write the DDS to ``path``.

    The caller passes a PARTIAL name (``O4_DDS_File.partial_name``) and lands it; this
    function only writes. Returns the bytes written. Runs in a pool worker.
    """
    data = encode_dds(_load_rgba(source), fmt, mip_mode=mip_mode)
    with open(path, "wb") as handle:
        handle.write(data)
    return len(data)


_POOL_LOCK = threading.Lock()
_POOL: _cf.ProcessPoolExecutor | None = None


def _pool(workers: int) -> _cf.ProcessPoolExecutor:
    """The process-wide encode pool (spawned, ``workers`` wide on first use; shared by the
    convert threads of every tile this process builds)."""
    global _POOL
    with _POOL_LOCK:
        if _POOL is None:
            _POOL = _cf.ProcessPoolExecutor(max_workers=max(1, int(workers)),
                                            mp_context=_mp.get_context("spawn"))
        return _POOL


def shutdown_pool() -> None:
    """Stop the encode pool (the next :func:`encode_file_pooled` starts a new one)."""
    global _POOL
    with _POOL_LOCK:
        pool, _POOL = _POOL, None
    if pool is not None:
        pool.shutdown(wait=True)


def encode_file_pooled(source, fmt: str, path: str, workers: int) -> int:
    """:func:`encode_file` in the process pool; blocks the calling convert thread.

    A broken pool (a worker killed) is dropped so the next texture gets a fresh one, and the
    error is raised for the caller's retry loop."""
    try:
        return _pool(workers).submit(encode_file, source, fmt, path).result()
    except _cf.process.BrokenProcessPool:
        shutdown_pool()
        raise


def encode_texture(source, fmt: str, path: str, workers: int) -> int:
    """The convert site's entry: write the DDS of ``source`` to ``path``.

    An image path (the cached JPEG, the common case) goes to the process pool, whose worker
    decodes it; pixels already in memory (a colour-filtered, harmonized or masked texture)
    are encoded in the calling convert thread — shipping 48-64 MB to a worker cost more
    than it saved (14 real textures, 16 workers: pool 1.2 s vs thread 0.8 s; paths: pool
    0.5 s vs thread 0.6 s; 2026-10-17)."""
    if isinstance(source, np.ndarray):
        return encode_file(source, fmt, path)
    return encode_file_pooled(source, fmt, path, workers)
