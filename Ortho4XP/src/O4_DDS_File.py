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

Standard library only.
"""
from __future__ import annotations

import contextlib
import os
import struct
import uuid

import O4_Held_File as HELD

__all__ = ["HEADER_BYTES", "expected_size", "is_partial_name", "is_whole",
           "land", "partial_name", "sweep_partials"]

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
