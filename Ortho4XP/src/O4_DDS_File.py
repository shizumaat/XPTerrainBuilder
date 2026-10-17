"""Is a ``.dds`` texture on disk WHOLE, and how one is written so that it
always is (issue #600).

The texture converter used to write straight onto the texture's final
name.  A converter killed mid-write (a stopped build, a crash, a power
cut) left a short file there, and the next build's "already on disk" test
— a bare ``os.path.isfile`` — took it as the texture.

* A DDS file says how long it must be: its 128-byte header carries the
  width, the height, the mip count and the pixel format, so the size of
  the pixel data is computed (:func:`expected_size`), not guessed.
  :func:`is_whole` is the "already on disk" test.
* The converter writes a PARTIAL name beside the texture
  (:func:`partial_name`) and :func:`land` renames it onto the final name
  only when it is whole.  The partial keeps the ``.dds`` ending the
  converters expect; :func:`is_partial_name` is how a reader that lists
  ``*.dds`` tells it is not a texture.
* The in-process encoder (``O4_DDS_Encode``) writes its files through
  :func:`build_header` / :func:`assemble`, and the quality tool reads them
  through :func:`split_levels` — the ONE header writer, ported from
  OrthoStudio XP's ``textures/dds.py`` (see the notice above
  :func:`full_mip_count`) and sized by the same :func:`expected_size` that
  :func:`is_whole` reads.

Standard library only.
"""
from __future__ import annotations

import contextlib
import os
import struct
import uuid

import O4_Held_File as HELD

__all__ = ["BLOCK_FORMATS", "HEADER_BYTES", "assemble", "build_header",
           "expected_size", "full_mip_count", "is_partial_name", "is_whole",
           "land", "level_size", "mip_dims", "partial_name", "split_levels",
           "sweep_partials"]

#: ``"DDS "`` + the 124-byte ``DDS_HEADER``.
HEADER_BYTES = 128
#: The ``DDS_HEADER_DXT10`` extension that follows when the FourCC is DX10.
_DX10_HEADER_BYTES = 20
_MAGIC = b"DDS "
_DDSD_MIPMAPCOUNT = 0x20000
_DDPF_FOURCC = 0x4
#: Bytes per 4x4 block of each block-compressed format, by FourCC ...
_FOURCC_BLOCK_BYTES = {b"DXT1": 8, b"DXT2": 16, b"DXT3": 16, b"DXT4": 16,
                       b"DXT5": 16, b"ATI1": 8, b"BC4U": 8, b"BC4S": 8,
                       b"ATI2": 16, b"BC5U": 16, b"BC5S": 16}
#: ... and by ``DXGI_FORMAT`` (BC1 70-72, BC2 73-75, BC3 76-78, BC4 79-81,
#: BC5 82-84, BC6H 94-96, BC7 97-99).
_DXGI_BLOCK_BYTES = {**{f: 8 for f in (70, 71, 72, 79, 80, 81)},
                     **{f: 16 for f in (73, 74, 75, 76, 77, 78, 82, 83, 84,
                                        94, 95, 96, 97, 98, 99)}}
#: The block formats the texture encoder writes: name -> (FourCC, bytes per
#: 4x4 block).  ``bc1`` is DXT1 (no alpha), ``bc3`` is DXT5.
BLOCK_FORMATS = {"bc1": (b"DXT1", 8), "bc3": (b"DXT5", 16)}
_DDSD_CAPS, _DDSD_HEIGHT, _DDSD_WIDTH = 0x1, 0x2, 0x4
_DDSD_PIXELFORMAT, _DDSD_LINEARSIZE = 0x1000, 0x80000
_DDSCAPS_COMPLEX, _DDSCAPS_TEXTURE, _DDSCAPS_MIPMAP = 0x8, 0x1000, 0x400000
#: magic, DDS_HEADER (size, flags, height, width, linear size, depth, mip
#: count, 11 reserved), DDS_PIXELFORMAT (size, flags, FourCC, 5 masks),
#: caps 1-4, reserved2 — 128 bytes.
_HEADER_STRUCT = struct.Struct("<4s7I11I2I4s5I5I")
#: What marks a converter's unfinished output: ``<texture>.<pid>.<token>``
#: + this.
_PARTIAL_ENDING = ".partial.dds"


def expected_size(header: bytes) -> int | None:
    """The byte length of the DDS file that starts with ``header`` — its
    headers plus every mip level of pixel data — or ``None`` when
    ``header`` is not a DDS header or its pixel format is one this module
    cannot size (the file is then judged by its header alone)."""
    if len(header) < HEADER_BYTES or header[:4] != _MAGIC:
        return None
    (flags, height, width) = struct.unpack_from("<III", header, 8)
    (mip_count,) = struct.unpack_from("<I", header, 28)
    (format_flags, fourcc, bit_count) = struct.unpack_from("<I4sI", header, 80)
    levels = max(mip_count, 1) if flags & _DDSD_MIPMAPCOUNT else 1
    headers = HEADER_BYTES
    block_bytes = None
    if format_flags & _DDPF_FOURCC:
        if fourcc == b"DX10":
            headers += _DX10_HEADER_BYTES
            if len(header) < headers:
                return None
            (dxgi_format,) = struct.unpack_from("<I", header, HEADER_BYTES)
            block_bytes = _DXGI_BLOCK_BYTES.get(dxgi_format)
        else:
            block_bytes = _FOURCC_BLOCK_BYTES.get(fourcc)
        if block_bytes is None:
            return None
    elif not bit_count:
        return None
    pixels = 0
    for level in range(levels):
        (w, h) = (max(width >> level, 1), max(height >> level, 1))
        if block_bytes:
            pixels += ((w + 3) // 4) * ((h + 3) // 4) * block_bytes
        else:
            pixels += ((w * bit_count + 7) // 8) * h
    return headers + pixels


def is_whole(path: str) -> bool:
    """Is ``path`` a complete DDS file?  ``False`` for a missing file, one
    that does not start with a DDS header, and one SHORTER than its own
    header says it is — the file a converter killed mid-write leaves."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            header = handle.read(HEADER_BYTES + _DX10_HEADER_BYTES)
    except OSError:
        return False
    if len(header) < HEADER_BYTES or header[:4] != _MAGIC:
        return False
    expected = expected_size(header)
    return size > HEADER_BYTES if expected is None else size >= expected


def partial_name(final: str) -> str:
    """A name beside ``final`` for a converter to write, unique to this
    process and call."""
    stem = final[:-4] if final.lower().endswith(".dds") else final
    return f"{stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}{_PARTIAL_ENDING}"


def is_partial_name(name: str) -> bool:
    """Is ``name`` a converter's unfinished output, not a texture?"""
    return name.lower().endswith(_PARTIAL_ENDING)


def sweep_partials(final: str) -> None:
    """Remove the partials an earlier, KILLED conversion of ``final`` left.

    Called by the conversion that is about to make ``final`` again: one
    build converts a texture once, so a partial found now is litter."""
    (folder, name) = os.path.split(final)
    prefix = (name[:-4] if name.lower().endswith(".dds") else name) + "."
    try:
        names = os.listdir(folder or ".")
    except OSError:
        return
    for other in names:
        if other.startswith(prefix) and is_partial_name(other):
            with contextlib.suppress(OSError):
                os.remove(os.path.join(folder, other))


def land(partial: str, final: str) -> bool:
    """Rename a converter's finished ``partial`` onto ``final``; ``False``
    — with ``partial`` removed and ``final`` untouched — when the partial
    is not a whole DDS file or the rename is refused (a file another
    program holds is retried first, :mod:`O4_Held_File`)."""
    if is_whole(partial):
        try:
            HELD.retrying_a_held_file(lambda: os.replace(partial, final))
            return True
        except OSError:
            pass
    with contextlib.suppress(OSError):
        os.remove(partial)
    return False


# ---------------------------------------------------------------------------
# Writing (the in-process encoder).  Ported from OrthoStudio XP
# ``src/orthostudio/textures/dds.py`` @ 7c028d82dcc59a27296972973aa0663ef37efddc
# — OrthoStudio XP, Copyright (C) 2026 radioharris, GNU GPL v3; additional
# terms in THIRD_PARTY/orthostudio-xp/NOTICE.  Modified for XPTerrainBuilder,
# 2026-10-17: merged into this module so there is one DDS writer; the parse
# side reuses :func:`expected_size` instead of a second header parser.


def _check_format(fmt: str) -> tuple[bytes, int]:
    try:
        return BLOCK_FORMATS[fmt]
    except KeyError:
        raise ValueError(f"unsupported DDS format {fmt!r}, expected 'bc1' "
                         "or 'bc3'") from None


def full_mip_count(width: int, height: int) -> int:
    """Levels of a full mip chain down to 1x1 (13 for 4096x4096)."""
    if width < 1 or height < 1:
        raise ValueError("width and height must be >= 1")
    return max(width, height).bit_length()


def mip_dims(width: int, height: int, count: int) -> list[tuple[int, int]]:
    """``count`` successive level sizes, each side halved, floored at 1."""
    return [(max(width >> k, 1), max(height >> k, 1)) for k in range(count)]


def level_size(width: int, height: int, fmt: str) -> int:
    """Bytes of one block-compressed level (partial 4x4 blocks count)."""
    return ((width + 3) // 4) * ((height + 3) // 4) * _check_format(fmt)[1]


def build_header(width: int, height: int, fmt: str, mip_count: int) -> bytes:
    """The 128-byte header (magic included) of a 2D DXT1/DXT5 texture.

    nvcompress's layout field for field except ``dwReserved1``, left zero
    (nvtt writes 'NVTT' tags there; X-Plane ignores it)."""
    fourcc = _check_format(fmt)[0]
    if not 1 <= mip_count <= full_mip_count(width, height):
        raise ValueError(f"mip_count {mip_count} out of range for "
                         f"{width}x{height}")
    flags = (_DDSD_CAPS | _DDSD_HEIGHT | _DDSD_WIDTH | _DDSD_PIXELFORMAT
             | _DDSD_LINEARSIZE)
    caps = _DDSCAPS_TEXTURE
    if mip_count > 1:
        flags |= _DDSD_MIPMAPCOUNT
        caps |= _DDSCAPS_COMPLEX | _DDSCAPS_MIPMAP
    return _HEADER_STRUCT.pack(
        _MAGIC, 124, flags, height, width, level_size(width, height, fmt),
        0, mip_count, *([0] * 11),
        32, _DDPF_FOURCC, fourcc, 0, 0, 0, 0, 0,
        caps, 0, 0, 0, 0)


def assemble(width: int, height: int, fmt: str, levels) -> bytes:
    """Header plus the block data of successive levels: a DDS file image."""
    for (w, h), blob in zip(mip_dims(width, height, len(levels)), levels,
                            strict=True):
        if len(blob) != level_size(w, h, fmt):
            raise ValueError(f"level {w}x{h} has {len(blob)} bytes, expected "
                             f"{level_size(w, h, fmt)}")
    return b"".join((build_header(width, height, fmt, len(levels)), *levels))


def split_levels(data) -> tuple[tuple[int, int, str], list[memoryview]]:
    """``((width, height, fmt), [a zero-copy view per mip level])`` of a
    DXT1/DXT5 file image; ``ValueError`` on anything else or a short one."""
    header = bytes(data[:HEADER_BYTES])
    expected = expected_size(header)
    fourcc = header[84:88]
    fmt = next((name for name, (cc, _) in BLOCK_FORMATS.items()
                if cc == fourcc), None)
    if expected is None or fmt is None:
        raise ValueError("not a DXT1/DXT5 DDS file")
    if len(data) < expected:
        raise ValueError("DDS data truncated")
    (flags, height, width) = struct.unpack_from("<III", header, 8)
    (mip_count,) = struct.unpack_from("<I", header, 28)
    count = max(mip_count, 1) if flags & _DDSD_MIPMAPCOUNT else 1
    view, offset, levels = memoryview(data), HEADER_BYTES, []
    for w, h in mip_dims(width, height, count):
        size = level_size(w, h, fmt)
        levels.append(view[offset:offset + size])
        offset += size
    return (width, height, fmt), levels
