"""Write and rewrite DSF files in binary, without DSFTool (flight manager /
World spec §7.1, §7.3).

A DSF is ``XPLNEDSF`` + version 1, then top-level atoms (id stored
byte-reversed, little-endian length including the 8-byte atom header), then
an MD5 of everything before it.  Two jobs need no more than that:

* :func:`placeholder_bytes` -- the overlay-only DSF of a tile with no
  content, byte for byte what DSFTool's ``--text2dsf`` writes for the
  World pack's placeholder text (twin-checked), in microseconds instead of
  two DSFTool runs: enabling a region writes thousands of them.
* :func:`rewrite` -- a built DSF moved into the World pack: its
  ``HEAD``/``PROP`` properties replaced and every string of its
  ``DEFN`` tables (``TERT`` ``OBJT`` ``POLY`` ``NETW`` ``DEMN``) passed
  through a function; every other atom is copied unchanged and the MD5
  footer recomputed.  The DSFTool text round trip it replaces took 59 s on
  a light tile.

Standard library only.  The reader of 7z DSFs is :mod:`O4_DSF_Header`.
"""
from __future__ import annotations

import hashlib
import struct
from typing import Callable, Iterable, Optional

__all__ = ["DEFN_TABLES", "dsf_md5_ok", "atoms",
           "properties", "definitions", "placeholder_bytes", "rewrite"]

_COOKIE = b"XPLNEDSF"
#: The definition tables of the ``DEFN`` atom, in DSFTool's write order.
DEFN_TABLES = ("TERT", "OBJT", "POLY", "NETW", "DEMN")


def _atom(name: str, body: bytes) -> bytes:
    """One atom: ``name`` stored byte-reversed, the length, the body."""
    return name.encode("ascii")[::-1] + struct.pack("<I", 8 + len(body)) + body


def _dsf_file(top: Iterable[bytes]) -> bytes:
    """A whole DSF from its top-level atoms: cookie, version, MD5 footer."""
    body = _COOKIE + struct.pack("<I", 1) + b"".join(top)
    return body + hashlib.md5(body).digest()


def dsf_md5_ok(buf: bytes) -> bool:
    """Does the MD5 footer match the rest of the file?"""
    return len(buf) > 16 and hashlib.md5(buf[:-16]).digest() == buf[-16:]


def atoms(buf: bytes, start: int, end: int) -> list[tuple[str, int, int]]:
    """``(name, body start, body end)`` of the atoms in ``buf[start:end]``;
    ``ValueError`` when one runs past ``end``."""
    out = []
    at = start
    while at + 8 <= end:
        raw, length = struct.unpack_from("<4sI", buf, at)
        if length < 8 or at + length > end:
            raise ValueError(f"DSF atom at {at} runs past its parent")
        out.append((raw[::-1].decode("ascii", "replace"), at + 8, at + length))
        at += length
    return out


def _top(buf: bytes) -> list[tuple[str, int, int]]:
    if not buf.startswith(_COOKIE) or len(buf) < 28:
        raise ValueError("not an uncompressed DSF")
    return atoms(buf, 12, len(buf) - 16)


def _strings(body: bytes) -> list[str]:
    parts = body.split(b"\0")
    return [p.decode("utf-8") for p in (parts[:-1] if parts and parts[-1] == b""
                                         else parts)]


def _table(strings: Iterable[str]) -> bytes:
    return b"".join(s.encode("utf-8") + b"\0" for s in strings)


def properties(buf: bytes) -> list[tuple[str, str]]:
    """The ``HEAD``/``PROP`` pairs of a DSF, in order."""
    for name, body, end in _top(buf):
        if name == "HEAD":
            for kid, kbody, kend in atoms(buf, body, end):
                if kid == "PROP":
                    words = _strings(buf[kbody:kend])
                    return list(zip(words[0::2], words[1::2], strict=False))
    return []


def definitions(buf: bytes) -> dict[str, list[str]]:
    """``{"TERT": [...], "OBJT": [...], ...}`` of a DSF's ``DEFN`` atom."""
    for name, body, end in _top(buf):
        if name == "DEFN":
            return {kid: _strings(buf[kbody:kend])
                    for kid, kbody, kend in atoms(buf, body, end)}
    return {}


def _prop_bytes(pairs: Iterable[tuple[str, str]]) -> bytes:
    return _table(w for pair in pairs for w in pair)


def placeholder_bytes(lat: int, lon: int, agent: str) -> bytes:
    """The overlay-only DSF of tile (lat, lon) with no content and
    ``sim/creation_agent`` ``agent``: the shape DSFTool writes for the
    property-only text (empty definition tables, an empty 4-plane and
    2-plane point pool, one command), 328 bytes for the World pack's
    agent."""
    head = _atom("HEAD", _atom("PROP", _prop_bytes([
        ("sim/planet", "earth"), ("sim/overlay", "1"),
        ("sim/creation_agent", agent), ("sim/west", str(lon)),
        ("sim/east", str(lon + 1)), ("sim/north", str(lat + 1)),
        ("sim/south", str(lat))])))
    defn = _atom("DEFN", b"".join(_atom(t, b"") for t in DEFN_TABLES))
    # PO32: 0 points, 4 planes, per-plane encoding 3 (RLE + differenced).
    scal = struct.pack("<8f", 1.0, float(lon), 1.0, float(lat),
                       65535.0, -32768.0, 0.0, 0.0)
    geod = _atom("GEOD", _atom("PO32", struct.pack("<IB4B", 0, 4, 3, 3, 3, 3))
                + _atom("SC32", scal)
                + _atom("PO32", struct.pack("<IB", 0, 0)) + _atom("SC32", b""))
    # One command: 2 = set the junction offset (uint32 0).
    cmds = _atom("CMDS", struct.pack("<BI", 2, 0))
    return _dsf_file([head, defn, geod, cmds])


def rewrite(buf: bytes,
            props: Optional[Callable[[list[tuple[str, str]]],
                                     list[tuple[str, str]]]] = None,
            defs: Optional[Callable[[str, str], str]] = None) -> bytes:
    """``buf`` (an uncompressed DSF) with its properties passed through
    ``props`` (the pair list in, the new pair list out) and every
    definition string through ``defs(table, string)``; all other atoms,
    and the order of everything, unchanged; MD5 footer recomputed."""
    out = []
    for name, body, end in _top(buf):
        whole = buf[body - 8:end]
        if name == "HEAD" and props is not None:
            kids = []
            for kid, kbody, kend in atoms(buf, body, end):
                if kid == "PROP":
                    words = _strings(buf[kbody:kend])
                    pairs = list(zip(words[0::2], words[1::2], strict=False))
                    kids.append(_atom("PROP", _prop_bytes(props(pairs))))
                else:
                    kids.append(buf[kbody - 8:kend])
            whole = _atom("HEAD", b"".join(kids))
        elif name == "DEFN" and defs is not None:
            kids = []
            for kid, kbody, kend in atoms(buf, body, end):
                if kid in DEFN_TABLES:
                    kids.append(_atom(kid, _table(
                        defs(kid, s) for s in _strings(buf[kbody:kend]))))
                else:
                    kids.append(buf[kbody - 8:kend])
            whole = _atom("DEFN", b"".join(kids))
        out.append(whole)
    return _dsf_file(out)
