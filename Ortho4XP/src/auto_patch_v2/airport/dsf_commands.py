"""The DSF binary's atoms and command stream, and the one repair made to it.

DSFTool 2.4.0-b1 crashes (SIGSEGV, address 0x18) on ``--dsf2text`` of an
OVERLAY DSF whose command stream names a 16-bit definition, an object or
an object range BEFORE any pool is selected (#568).  Its pool census
(``DSFLib.cpp`` ``GetAllPools``, xptools ``c31ed76b5``) records the
"current pool" at each of those commands; before the first ``PoolSelect``
that is the sentinel 0xFFFF, and ``planeScales[0xFFFF][3]`` is then read
far past the pool table.  DSFTool's own writer emits "definition, pool,
objects", so a file whose FIRST object uses a definition index above 255
has the trait.  Upstream fixed it on 2026-03-08 (``9c1a06c7b``, "Fix
dsf2text crash for object def indices over 255": the sentinel is no
longer recorded); no tool release carries the fix yet.

:func:`select_pool_first` makes the same DSF with ONE command put in
front: a ``PoolSelect`` of a pool the census records anyway.  Nothing the
file says changes — every command that reads a pool is still preceded by
the file's own ``PoolSelect`` — and the census is the bundled tool's own
without the sentinel: the pool put in front is one it records anyway.
"""
from __future__ import annotations

import hashlib
import struct

__all__ = ["atoms", "header_properties", "places_elevated_objects",
           "select_pool_first"]

_COOKIE = b"XPLNEDSF"
_FOOTER = 16                       # the trailing MD5
_CMDS = b"SDMC"                    # atom ids are stored byte-reversed
_HEAD, _PROP = b"DAEH", b"PORP"
_UNSELECTED = 0xFFFF

_POOL_SELECT = 1
_GEOD, _POOL = b"DOEG", b"LOOP"
#: Object and ObjectRange: the commands that place objects
_OBJECT_COMMANDS = frozenset((7, 8))
#: an object point carrying an elevation (OBJECT_MSL / OBJECT_AGL) has a
#: fourth plane after longitude, latitude and heading
_ELEVATED_PLANES = 4
#: The commands at which DSFTool's census of an OVERLAY records the
#: current pool: SetDefinition16, Object, ObjectRange.
_POOL_READERS = frozenset((4, 7, 8))
#: Operand bytes of the fixed-length commands (``DSFDefs.h``).
_FIXED = {1: 2, 2: 4, 3: 1, 4: 2, 5: 4, 6: 1, 7: 2, 8: 4, 10: 4, 13: 6,
          16: 0, 17: 1, 18: 9, 25: 4, 28: 4, 31: 4}
#: Commands that are a one-byte count and ``count * width`` operand bytes.
_COUNTED = {9: 2, 11: 4, 23: 2, 26: 2, 29: 2, 24: 4, 27: 4, 30: 4}
#: Comments: the width of their length field.
_COMMENT = {32: "<B", 33: "<H", 34: "<I"}


def atoms(buf: bytes, off: int, end: int) -> list[tuple[bytes, int, int]]:
    """``(id as read, offset, length)`` of the atoms in ``buf[off:end]``."""
    out = []
    while off < end:
        if off + 8 > end:
            raise ValueError(f"truncated atom header at {off}")
        aid, ln = struct.unpack_from("<4sI", buf, off)
        if ln < 8 or off + ln > end:
            raise ValueError(f"atom {aid[::-1]!r} at {off}: bad length {ln}")
        out.append((aid, off, ln))
        off += ln
    return out


def header_properties(path: str) -> "dict[str, str] | None":
    """The ``HEAD``/``PROP`` strings of an UNCOMPRESSED DSF, read from its
    first atom alone (``None`` for a 7z-compressed or unreadable file).
    ``airport/terrain_mesh_witness`` screens installed packs with it before
    paying for a DSFTool dump."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(12 + 8)
            if len(head) < 20 or head[:8] != _COOKIE:
                return None
            aid, ln = struct.unpack_from("<4sI", head, 12)
            if aid != _HEAD or ln < 8:
                return None
            buf = head[12:] + fh.read(ln - 8)
    except OSError:
        return None
    try:
        for kid, koff, klen in atoms(buf, 8, len(buf)):
            if kid == _PROP:
                strings = buf[koff + 8:koff + klen].split(b"\0")
                return {k.decode("utf-8", "replace"): v.decode("utf-8", "replace")
                        for k, v in zip(strings[0::2], strings[1::2], strict=False) if k}
    except ValueError:
        return None
    return {}


def _operand_bytes(cmds: bytes, at: int, command: int) -> int | None:
    """Length of the operands of ``command`` whose operands start at
    ``at``; ``None`` for a command DSFTool's census stops at."""
    if command in _FIXED:
        return _FIXED[command]
    if command in _COUNTED:
        return 1 + cmds[at] * _COUNTED[command]
    if command == 12:                               # Polygon
        return 3 + 2 * cmds[at + 2]
    if command == 15:                               # NestedPolygonRange
        return 5 + 2 * cmds[at + 2]
    if command == 14:                               # NestedPolygon
        size = 3
        for _ in range(cmds[at + 2]):
            size += 1 + 2 * cmds[at + size]
        return size
    if command in _COMMENT:
        fmt = _COMMENT[command]
        return struct.calcsize(fmt) + struct.unpack_from(fmt, cmds, at)[0]
    return None


def _census(cmds: bytes) -> tuple[bool, int | None]:
    """What DSFTool's overlay pool census meets in ``cmds``: whether it
    records the unselected sentinel, and the first SELECTED pool it
    records (``None`` when it records none)."""
    current = _UNSELECTED
    unselected = False
    first: int | None = None
    at = 0
    while at < len(cmds):
        command = cmds[at]
        at += 1
        size = _operand_bytes(cmds, at, command)
        if size is None:
            break
        if command == _POOL_SELECT:
            current = struct.unpack_from("<H", cmds, at)[0]
        elif command in _POOL_READERS:
            if current == _UNSELECTED:
                unselected = True
            elif first is None:
                first = current
        at += size
    return unselected, first


def _is_overlay(buf: bytes, top: list[tuple[bytes, int, int]]) -> bool:
    """Whether the header carries ``sim/overlay 1`` — DSFTool's census
    reads the object commands only then."""
    for aid, off, length in top:
        if aid != _HEAD:
            continue
        for kid, koff, klen in atoms(buf, off + 8, off + length):
            if kid == _PROP:
                strings = buf[koff + 8:koff + klen].split(b"\0")
                pairs = zip(strings[0::2], strings[1::2])
                return any(name == b"sim/overlay" and value.strip() == b"1"
                           for name, value in pairs)
    return False


def select_pool_first(buf: bytes) -> bytes | None:
    """``buf`` (an uncompressed overlay DSF) with a ``PoolSelect`` put in front of
    its command stream, or ``None`` when the file does not have the trait
    in the module text (or is not a DSF this reads): then there is nothing
    to repair and the caller's failure stands."""
    if buf[:8] != _COOKIE or len(buf) < 12 + _FOOTER:
        return None
    body_end = len(buf) - _FOOTER
    try:
        top = atoms(buf, 12, body_end)
        found = [a for a in top if a[0] == _CMDS]
        if len(found) != 1 or not _is_overlay(buf, top):
            return None
        _aid, off, length = found[0]
        cmds = buf[off + 8:off + length]
        unselected, pool = _census(cmds)
    except (ValueError, IndexError, struct.error):
        return None
    if not unselected or pool is None:
        return None
    cmds = struct.pack("<BH", _POOL_SELECT, pool) + cmds
    out = (buf[:off] + struct.pack("<4sI", _CMDS, 8 + len(cmds)) + cmds
           + buf[off + length:body_end])
    return out + hashlib.md5(out).digest()


def _pool_planes(buf: bytes, top: list[tuple[bytes, int, int]]) -> list[int]:
    """The plane count of each 16-bit point pool (``POOL`` atoms in GEOD,
    in file order — the index ``PoolSelect`` names)."""
    planes: list[int] = []
    for aid, off, length in top:
        if aid == _GEOD:
            for kid, koff, _klen in atoms(buf, off + 8, off + length):
                if kid == _POOL:
                    planes.append(buf[koff + 12])
    return planes


def places_elevated_objects(buf: bytes) -> "bool | None":
    """Does the (uncompressed) DSF place an object from a pool with an
    elevation plane — an ``OBJECT_MSL`` or ``OBJECT_AGL`` row (#1252)?
    Read off the command stream, no DSFTool dump; ``None`` when ``buf`` is
    not a DSF this reads."""
    if buf[:8] != _COOKIE or len(buf) < 12 + _FOOTER:
        return None
    try:
        top = atoms(buf, 12, len(buf) - _FOOTER)
        planes = _pool_planes(buf, top)
        for aid, off, length in top:
            if aid != _CMDS:
                continue
            cmds, at, current = buf[off + 8:off + length], 0, _UNSELECTED
            while at < len(cmds):
                command = cmds[at]
                at += 1
                size = _operand_bytes(cmds, at, command)
                if size is None:
                    break
                if command == _POOL_SELECT:
                    current = struct.unpack_from("<H", cmds, at)[0]
                elif (command in _OBJECT_COMMANDS and current < len(planes)
                      and planes[current] >= _ELEVATED_PLANES):
                    return True
                at += size
    except (ValueError, IndexError, struct.error):
        return None
    return False
