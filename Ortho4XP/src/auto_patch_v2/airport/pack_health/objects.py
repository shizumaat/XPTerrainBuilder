"""OUR REPAIRED COPY of a pack object (issue #1954, #1978).

The vendor ``.obj`` is never written.  A pack object the tile DSF places
whose ``LIGHT_*`` records are malformed (``light_records``) gets a copy
beside it, ``<stem>.o4fix.obj`` — beside, so its texture paths still
resolve — with every such record completed or dropped, and the written
DSF names the copy instead (:func:`rename_rows`, the same row rewrite as
"Optimise pack"'s object copies, #1707).  The copy is written from the
vendor file on every write that needs it, stamped with the vendor file's
size and time; Restore originals removes it with the DSF's record.

An object "Optimise pack" already copies (``.o4opt.obj``) carries the
repair in that copy (``objcopy.copy_text``), and a split placement's
bodies are written from the repaired text (``obj8_split``), so neither
needs this one.
"""
from __future__ import annotations

import os
import typing as _t

# the package, not its names: ``pack_optimise`` imports this package's
# ``light_records`` while it is still initialising (#1901)
from .. import pack_optimise as _po
from ..pack_optimise import objcopy as _oc
from . import light_records as _lr

__all__ = ["COPY_SUFFIX", "GENERATED_MARK", "copy_path",
           "broken_objects", "write_copies", "rename_rows", "remove"]

#: the copy of ``<stem>.obj``
COPY_SUFFIX = ".o4fix.obj"
#: every file this module writes carries this in its name
GENERATED_MARK = ".o4fix"
#: the params the copy's stamp is taken over (``objcopy.stamp``)
_STAMP_PARAMS = {"lights": "repaired", "version": 1}
#: ``{physical path: ((size, mtime_ns), findings)}`` — an object is read
#: once per process while it does not change
_MEMO: dict[str, tuple[tuple[int, int], tuple]] = {}


def copy_path(path: str) -> str:
    """The copy of the declared ``path``."""
    return _oc.copy_path(path, COPY_SUFFIX)


def _lines(phys: str) -> tuple[str, list[str]]:
    """The vendor file's line ending and lines (latin-1: every byte is
    kept)."""
    with open(phys, encoding="latin-1", newline="") as fh:
        raw = fh.read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    return eol, raw.split(eol)


def _light_rows(raw: bytes) -> list[str]:
    """The rows of an object that start with ``LIGHT`` (every keyword
    ``light_records`` checks), found by a byte search: a heavy pack's
    objects are hundreds of MB of vertices (KIAH, 479 objects, 536 MB:
    4 s to split every line, 2 s for a multi-line regex)."""
    rows: list[str] = []
    i = raw.find(b"LIGHT")
    while i >= 0:
        lf = raw.rfind(b"\n", 0, i)
        start = max(lf, raw.rfind(b"\r", lf + 1, i)) + 1
        end = raw.find(b"\n", i)
        end = len(raw) if end < 0 else end
        cr = raw.find(b"\r", i, end)          # CRLF, or an old CR-only file
        end = cr if cr >= 0 else end
        line = raw[start:end]
        if line.lstrip().startswith(b"LIGHT"):
            rows.append(line.decode("latin-1"))
        i = raw.find(b"LIGHT", end)
    return rows


def _findings(phys: str) -> tuple:
    """The malformed light records of the object file ``phys`` (their
    ``line`` counts its light rows, not its lines)."""
    try:
        st = os.stat(phys)
    except OSError:
        return ()
    key = (st.st_size, st.st_mtime_ns)
    hit = _MEMO.get(phys)
    if hit is not None and hit[0] == key:
        return hit[1]
    try:
        with open(phys, "rb") as fh:
            raw = fh.read()
    except OSError:
        return ()
    found = tuple(_lr.check_lines(_light_rows(raw)))
    _MEMO[phys] = (key, found)
    return found


def _ours(path: str) -> bool:
    """A file this app wrote: a split body or a copy."""
    base = os.path.basename(path)
    return "__b" in base or ".o4opt" in base or GENERATED_MARK in base


def broken_objects(pack_root: str, text: str) -> dict[str, tuple]:
    """``{declared path: findings}`` for each ``OBJECT_DEF`` of the dump
    ``text`` that is a pack ``.obj`` file with a malformed light record."""
    out: dict[str, tuple] = {}
    for raw in text.splitlines():
        if not raw.startswith("OBJECT_DEF "):
            continue
        path = raw[len("OBJECT_DEF "):].strip()
        if not path.lower().endswith(".obj") or _ours(path):
            continue
        phys = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
        if os.path.isfile(phys):
            found = _findings(phys)
            if found:
                out[path] = found
    return out


def _copy_text(phys: str) -> str:
    """The repaired copy of the vendor file ``phys``: its bytes, the
    malformed light records completed or dropped, and the stamp."""
    eol, lines = _lines(phys)
    lines = _lr.repair_lines(lines)[0]
    head = lines[:3] + [f"# o4fix {_oc.stamp(phys, _STAMP_PARAMS)}"] + lines[3:]
    return eol.join(head)


def _current(dst: str, phys: str) -> bool:
    try:
        with open(dst, encoding="latin-1") as fh:
            head = [fh.readline() for _ in range(4)]
    except OSError:
        return False
    return head[3].strip() == f"# o4fix {_oc.stamp(phys, _STAMP_PARAMS)}"


def write_copies(pack_root: str, paths: _t.Iterable[str]) -> list[str]:
    """Write the copy of each declared path when absent or stale; returns
    them pack-relative.  A vendor file that no longer reads raises: the
    DSF must never name a missing file."""
    out: list[str] = []
    for path in sorted(set(paths)):
        phys = os.path.join(pack_root, *path.replace("\\", "/").split("/"))
        rel = copy_path(path).replace("\\", "/")
        dst = os.path.join(pack_root, *rel.replace("\\", "/").split("/"))
        if not _current(dst, phys):
            _po.write_if_changed(dst, _copy_text(phys), "latin-1")
        out.append(rel)
    return out


def rename_rows(text: str, paths: _t.Iterable[str]) -> tuple[str, int]:
    """``text`` with each ``OBJECT_DEF`` of ``paths`` naming its copy."""
    return _oc.rename_rows(text, dict.fromkeys(paths, True), copy_path)


def remove(pack_root: str, rels: _t.Iterable[str]) -> list[str]:
    """Remove copies ``rels`` (pack-relative); only a name carrying
    :data:`GENERATED_MARK` is ever touched."""
    return _po.remove_generated(pack_root, rels, GENERATED_MARK)
