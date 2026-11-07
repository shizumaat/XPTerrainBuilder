"""HOW MUCH OF A TEXTURE IS OPAQUE — read from a sample of the file, never
from its name (issue #1916, the draped-orthophoto witness of
``pack_drapes``).

An orthophoto is a photograph of the ground: opaque nearly everywhere.
A weathering decal laid over pavement (dirt, skid marks, ambient-
occlusion shadows) is mostly transparent.  :func:`opaque_fraction` answers
the share of a texture that is opaque, from:

* a DDS — the top mip level's blocks, :data:`SAMPLE_BLOCKS` of them on
  an even grid (a few kilobytes read whatever the file's size): ``DXT1``
  and uncompressed formats without an alpha channel are opaque; ``DXT3``
  blocks are decoded from their explicit 4-bit alphas, ``DXT5`` blocks
  from their interpolated alpha palette;
* a PNG — its colour type (no alpha channel: opaque), else the decoded
  alpha channel (Pillow), sampled;
* anything else, or a file that cannot be read — ``None`` (not known).
"""
from __future__ import annotations

import os
import struct

__all__ = ["SAMPLE_BLOCKS", "OPAQUE_ALPHA", "opaque_fraction", "image_file"]

#: blocks sampled from a DDS's top mip level
SAMPLE_BLOCKS = 256
#: the alpha (0-255) from which a pixel is opaque
OPAQUE_ALPHA = 250

_MEMO: dict[tuple, float | None] = {}


def image_file(pol_dir: str, name: str) -> str:
    """The texture a ``.pol`` names, as X-Plane finds it: the file, else
    the same name as ``.dds`` / ``.png`` (X-Plane prefers a DDS beside a
    PNG of the same name); ``""`` when none exists."""
    path = os.path.join(pol_dir, name.replace("\\", "/"))
    stem = os.path.splitext(path)[0]
    for cand in (stem + ".dds", path, stem + ".png"):
        if os.path.isfile(cand):
            return cand
    return ""


def opaque_fraction(path: str) -> float | None:
    """The share (0-1) of the texture's sampled pixels that are opaque, or
    ``None`` when it cannot be told.  Memoised on the file's stat."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (os.path.abspath(path), st.st_size, st.st_mtime_ns)
    if key not in _MEMO:
        try:
            _MEMO[key] = _measure(path)
        except (OSError, ValueError, struct.error):
            _MEMO[key] = None
    return _MEMO[key]


def _measure(path: str) -> float | None:
    with open(path, "rb") as fh:
        head = fh.read(128)
        if head[:4] == b"DDS ":
            return _dds(fh, head)
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return _png(path, head)
    return None


def _dds(fh, head: bytes) -> float | None:
    height, width = struct.unpack_from("<II", head, 12)
    pf_flags, = struct.unpack_from("<I", head, 80)
    fourcc = head[84:88]
    if fourcc == b"DX10":
        return None
    if fourcc == b"DXT1":
        return 1.0
    if fourcc not in (b"DXT3", b"DXT5", b"DXT2", b"DXT4"):
        # uncompressed: opaque unless it has an alpha channel
        return None if pf_flags & 0x1 else 1.0
    bw, bh = max(1, (width + 3) // 4), max(1, (height + 3) // 4)
    side = max(1, int(SAMPLE_BLOCKS ** 0.5))
    rows = sorted({min(bh - 1, (2 * j + 1) * bh // (2 * side)) for j in range(side)})
    cols = sorted({min(bw - 1, (2 * i + 1) * bw // (2 * side)) for i in range(side)})
    opaque = total = 0
    for b in (r * bw + c for r in rows for c in cols):
        fh.seek(128 + 16 * b)
        raw = fh.read(16)
        if len(raw) < 16:
            break
        alphas = (_dxt3_alpha(raw) if fourcc in (b"DXT2", b"DXT3")
                  else _dxt5_alpha(raw))
        opaque += sum(1 for a in alphas if a >= OPAQUE_ALPHA)
        total += 16
    return opaque / total if total else None


def _dxt3_alpha(raw: bytes) -> list[int]:
    out = []
    for byte in raw[:8]:
        out += [(byte & 0xF) * 17, (byte >> 4) * 17]
    return out


def _dxt5_alpha(raw: bytes) -> list[int]:
    a0, a1 = raw[0], raw[1]
    if a0 > a1:
        pal = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    else:
        pal = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] \
            + [0, 255]
    bits = int.from_bytes(raw[2:8], "little")
    return [pal[(bits >> (3 * i)) & 7] for i in range(16)]


def _png(path: str, head: bytes) -> float | None:
    colour_type = head[25]
    if colour_type in (0, 2):
        return 1.0                       # grey / RGB: no alpha channel
    try:
        from PIL import Image
    except ImportError:
        return None
    with Image.open(path) as im:
        im.thumbnail((128, 128))
        alpha = im.convert("RGBA").getchannel("A")
        hist = alpha.histogram()
    total = sum(hist)
    return sum(hist[OPAQUE_ALPHA:]) / total if total else None
