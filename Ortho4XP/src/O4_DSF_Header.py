"""Is a DSF a base mesh or an overlay?  Read from its header alone.

X-Plane draws, for each tile, the FIRST base-mesh DSF it meets in
``scenery_packs.ini`` order; overlays (``sim/overlay 1``) stack on top of
it (#1729).  The answer lives in the DSF's ``HEAD``/``PROP`` atom, a few
hundred bytes at the front of the file, so a check reads that far and no
further.

Third-party DSFs are often 7-Zip archives of one file.  The archive's
packed stream starts right after its 32-byte signature header and runs to
the "next header" offset the signature header gives; 7-Zip's DSF archives
are plain LZMA with the default literal and position settings (or
LZMA2), which the standard library's :mod:`lzma` decodes raw.  Only the
first :data:`HEAD_BYTES` of the DSF are decoded.  The macOS app reads the
same flag (``Sources/SceneryKit/DSFReader.swift``, through libarchive);
this is the engine's reader, standard library only, for both apps.
"""

from __future__ import annotations

import lzma
import struct
from typing import Optional

__all__ = ["HEAD_BYTES", "dsf_properties", "dsf_is_overlay"]

#: How much of the DSF a check decodes: HEAD comes first in every DSF.
HEAD_BYTES = 1 << 16

_DSF_COOKIE = b"XPLNEDSF"
_SEVEN_ZIP = b"7z\xbc\xaf\x27\x1c"
_SIGNATURE_HEADER = 32
_HEAD_IDS = (b"DAEH", b"HEAD")      # atom ids are stored byte-reversed
_PROP_IDS = (b"PORP", b"PROP")
#: Most packed bytes read: the head of the DSF is far smaller than this.
_PACKED_CAP = 4 << 20
_RAW_FILTERS = (
    {"id": lzma.FILTER_LZMA1, "dict_size": 1 << 26,
     "lc": 3, "lp": 0, "pb": 2},
    {"id": lzma.FILTER_LZMA2, "dict_size": 1 << 26},
)


def _seven_zip_head(handle) -> bytes:
    """The first :data:`HEAD_BYTES` of the one file a 7z DSF holds, or
    ``b""`` when no supported coder decodes it to a DSF."""
    handle.seek(0)
    header = handle.read(_SIGNATURE_HEADER)
    if len(header) < _SIGNATURE_HEADER:
        return b""
    packed_size = struct.unpack_from("<Q", header, 12)[0]
    packed = handle.read(min(packed_size, _PACKED_CAP))
    for filters in _RAW_FILTERS:
        try:
            out = lzma.LZMADecompressor(
                lzma.FORMAT_RAW, filters=[filters]).decompress(
                    packed, max_length=HEAD_BYTES)
        except lzma.LZMAError:
            continue
        if out.startswith(_DSF_COOKIE):
            return out
    return b""


def _head(path: str) -> bytes:
    """The DSF's first bytes, decompressed when the file is a 7z."""
    with open(path, "rb") as handle:
        start = handle.read(HEAD_BYTES)
        if start.startswith(_SEVEN_ZIP):
            return _seven_zip_head(handle)
        return start if start.startswith(_DSF_COOKIE) else b""


def _atoms(buf: bytes, off: int, end: int):
    """``(id as stored, body start, body end)`` of the atoms in
    ``buf[off:end]``, stopping at the first one that runs past ``end``."""
    while off + 8 <= end:
        atom_id, length = struct.unpack_from("<4sI", buf, off)
        if length < 8:
            return
        yield atom_id, off + 8, min(off + length, end)
        if off + length > end:
            return
        off += length


def dsf_properties(path: str) -> Optional[dict]:
    """The DSF's ``HEAD``/``PROP`` pairs (``{"sim/overlay": "1", …}``), or
    ``None`` when the file cannot be read or decoded as a DSF."""
    try:
        buf = _head(path)
    except OSError:
        return None
    if not buf:
        return None
    for atom_id, body, end in _atoms(buf, 12, len(buf)):
        if atom_id not in _HEAD_IDS:
            continue
        for kid, kbody, kend in _atoms(buf, body, end):
            if kid in _PROP_IDS:
                strings = buf[kbody:kend].split(b"\0")
                return {name.decode("utf-8", "replace"):
                        value.decode("utf-8", "replace").strip()
                        for name, value in zip(strings[0::2], strings[1::2], strict=False)
                        if name}
        return {}
    return None


def dsf_is_overlay(path: str) -> Optional[bool]:
    """``True`` for an overlay DSF, ``False`` for a base mesh, ``None``
    when the header cannot be read (the caller cannot tell)."""
    props = dsf_properties(path)
    if props is None:
        return None
    return props.get("sim/overlay", "0") == "1"
