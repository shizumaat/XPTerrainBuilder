"""THE FLATTEN FLAG, REMOVED FROM A PACK THE APP MODIFIES (owner RULINGS
2026-10-20ac; issue #1916).

An airport block's ``1302 flatten 1`` asks X-Plane to flatten the ground
under the airport; the app's tile mesh does not work with it (owner
2026-11-06: "The flatten line should be removed whenever found since our
tile mesh will not work with it, don't ask the user, just include it as
an undoable part of the airport modifications").  So whenever the object
stage writes a pack, its ``apt.dat`` loses every ``1302 flatten 1`` row:

* :func:`strip_flatten` — the one WRITE.  The pack's apt.dat as shipped is
  kept ONCE as ``apt.dat.anchor_bak`` (the backup every other pack file
  of ours has, ``model.placement.BACKUP_SUFFIX``), and the live file is
  that backup without the flatten rows — nothing else changes.
* :func:`classify` — is the live file still our strip of the backup?
  Answered FROM THE FILES, with no record: ours exactly when the live
  bytes are the backup's minus its flatten rows.  A pack the user
  updated in place reads as ``REPLACED``: the restore never puts the old
  backup over it, and the next strip retires the stale backup
  (``backup_state.adopt``: renamed, never deleted) before keeping the
  new file.
* :func:`read_path` — THE apt.dat READ FRAME: every block read
  (``apt_dat.read_airport_block``) and the freshness stamp
  (:func:`read_mtime`) open the shipped file, so the flat-design witness
  (``pack.flatten_declared``, ``flat_pack``: report only) still reads the
  author's ORIGINAL flag after the strip, the airport's signature does
  not move, and the patch is not rebuilt for the strip.

THE ONE apt.dat WRITER (spec 2123 A3, RULINGS 2026-11-16y): the live
file is the backup plus RECORDED transforms -- the flatten strip and, for
a generated taxiway deck or road bridge, the REGION CUT (``apt_edit``: a
hole in each ``110`` pavement, every ``120`` line split there, the inside
dropped) of :func:`write_regions`.  The record ``apt.dat.o4_edits.json``
names the backup's and the live file's hashes and the regions, so
:func:`classify` reads a cut file as ``OURS`` from the files alone, and
every read still opens the SHIPPED backup.

The Undo is the pack's "Restore originals" (``object_rebake.
restore_detail``), which copies the backup back over a file classified
``OURS``.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil

from ..model.placement import BACKUP_SUFFIX
from . import backup_state as _bs

__all__ = ["classify", "read_path", "read_mtime", "apt_dat_of", "pack_flatten",
           "write_regions", "EDITS_SUFFIX"]

#: the transform record beside a region-cut apt.dat
EDITS_SUFFIX = ".o4_edits.json"

#: (path, live stat, backup stat) -> Verdict
_MEMO: dict[tuple, _bs.Verdict] = {}


def is_flatten_row(line: str | bytes) -> bool:
    """Is ``line`` an apt.dat ``1302 flatten 1`` row?"""
    if isinstance(line, bytes):
        line = line.decode("utf-8", "replace")
    toks = line.split()
    return (len(toks) >= 3 and toks[0] == "1302" and toks[1] == "flatten"
            and toks[2] == "1")


def stripped(data: bytes) -> bytes:
    """``data`` (an apt.dat's bytes) without its flatten rows; every
    other byte, line endings included, is kept."""
    return b"".join(ln for ln in data.splitlines(keepends=True)
                    if not is_flatten_row(ln))


def carries_flatten(data: bytes) -> bool:
    """Does an apt.dat's bytes hold a ``1302 flatten 1`` row?"""
    return any(is_flatten_row(ln) for ln in data.splitlines())


def _read(path: str) -> bytes | None:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def classify(apt_path: str) -> _bs.Verdict:
    """The one rule for a pack apt.dat and its backup (pure; memoised on
    both stats).  ``NO_BACKUP`` (never stripped: read the live file),
    ``PRISTINE`` (the backup's bytes), ``OURS`` (the backup minus its
    flatten rows: read the backup; the restore puts it back),
    ``REPLACED`` (the user's newer file: read it, never overwrite it),
    ``LIVE_MISSING``, ``UNPROVEN`` (a file that cannot be read)."""
    backup = apt_path + BACKUP_SUFFIX
    key = (os.path.abspath(apt_path), _bs._stat(apt_path), _bs._stat(backup))
    hit = _MEMO.get(key)
    if hit is None:
        hit = _MEMO[key] = _classify(apt_path, backup)
    return hit


def _classify(live: str, backup: str) -> _bs.Verdict:
    State, Verdict = _bs.State, _bs.Verdict
    if not os.path.isfile(backup):
        return Verdict(State.NO_BACKUP, live, "", live, False, "")
    if not os.path.isfile(live):
        return Verdict(State.LIVE_MISSING, live, backup, live, False, "")
    have, shipped = _read(live), _read(backup)
    if have is None or shipped is None:
        return Verdict(State.UNPROVEN, live, backup, live, False, "")
    if have == shipped:
        return Verdict(State.PRISTINE, live, backup, backup, False, "bytes")
    if have == stripped(shipped):
        return Verdict(State.OURS, live, backup, backup, True, "flatten-strip")
    rec = _record(live)
    if rec and rec.get("live_sha256") == hashlib.sha256(have).hexdigest() \
            and rec.get("backup_sha256") == hashlib.sha256(shipped).hexdigest():
        return Verdict(State.OURS, live, backup, backup, True, "region-cut")
    return Verdict(State.REPLACED, live, backup, live, False, "")


def _record(apt_path: str) -> dict | None:
    try:
        with open(apt_path + EDITS_SUFFIX, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def _cut(data: bytes, icao: str, regions) -> tuple[bytes, list, list]:
    """``data`` with every region cut out of ``icao``'s block
    (``apt_edit.cut_block``), and the edit records and dropped lines."""
    from . import apt_dat as _apt
    from .apt_edit import cut_block
    text = data.decode("utf-8", "surrogateescape")
    eol = "\r\n" if "\r\n" in text[:4096] else "\n"
    lines = text.split(eol)
    start = next((i for i, ln in enumerate(lines)
                  if _apt._is_header_for(ln.split(), icao.upper())), None)
    if start is None or not regions:
        return data, [], []
    end = start + 1
    while end < len(lines):
        t = lines[end].split()
        if t and (t[0] == "99" or (t[0] in ("1", "16", "17") and len(t) >= 5)):
            break
        end += 1
    block = lines[start:end]
    records, dropped = [], []
    for region in regions:
        res = cut_block(block, region)
        block = res.block
        records += list(res.record)
        dropped += list(res.dropped)
    lines[start:end] = block
    return eol.join(lines).encode("utf-8", "surrogateescape"), records, dropped


def write_regions(apt_path: str, icao: str, regions) -> tuple[str, list]:
    """THE apt.dat WRITE of a pack the app modifies (module doc): the live
    file becomes the shipped backup with its flatten rows stripped and
    ``regions`` (lon/lat polygons) cut out of ``icao``'s block.  Returns
    ``(state, dropped 120 pieces)``: ``"written"``, ``"unchanged"`` when
    the live file and its record already are this cut (#2178: an airport
    on two tiles asks once per tile; the second writes nothing), or ``""``
    when the file is not ours to write (nothing changed).  Raises
    ``OSError`` on a failed write, the live file as it was."""
    v = classify(apt_path)
    if v.state in (_bs.State.REPLACED, _bs.State.UNPROVEN) and v.backup:
        _bs.adopt(v)            # the user's newer apt.dat: retire the backup
        v = classify(apt_path)
    if v.state is _bs.State.LIVE_MISSING:
        return "", []
    backup = apt_path + BACKUP_SUFFIX
    if not os.path.isfile(backup):
        shutil.copy2(apt_path, backup + ".o4tmp")
        os.replace(backup + ".o4tmp", backup)
    shipped = _read(backup)
    if shipped is None:
        return "", []
    data, records, dropped = _cut(stripped(shipped), icao, list(regions))
    if _already(apt_path, data, [r.wkt for r in regions]):
        return "unchanged", dropped
    with open(apt_path + ".o4tmp", "wb") as fh:
        fh.write(data)
    os.replace(apt_path + ".o4tmp", apt_path)
    rec = {"icao": icao, "backup_sha256": hashlib.sha256(shipped).hexdigest(),
           "live_sha256": hashlib.sha256(data).hexdigest(),
           "regions": [r.wkt for r in regions], "edits": records}
    with open(apt_path + EDITS_SUFFIX + ".o4tmp", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(rec, fh, indent=1)
    os.replace(apt_path + EDITS_SUFFIX + ".o4tmp", apt_path + EDITS_SUFFIX)
    _bs.invalidate_memo()
    return "written", dropped


def _already(apt_path: str, data: bytes, regions: list) -> bool:
    """Are the live file and its record already ``data`` cut by
    ``regions`` (:func:`write_regions`)?"""
    live = _read(apt_path)
    if live is None or live != data:
        return False
    try:
        with open(apt_path + EDITS_SUFFIX, encoding="utf-8") as fh:
            return json.load(fh).get("regions") == regions
    except (OSError, ValueError):
        return False


def read_path(apt_path: str) -> str:
    """The file a reader opens for the pack apt.dat ``apt_path``: its
    shipped backup while the live file is our strip of it, else the live
    file.  One stat when the pack was never stripped."""
    if not apt_path or not os.path.isfile(apt_path + BACKUP_SUFFIX):
        return apt_path
    return classify(apt_path).read_path


def read_mtime(apt_path: str) -> float:
    """``os.path.getmtime`` of the read frame — the freshness stamp's and
    the gate's apt.dat date (the strip must not read as a pack update)."""
    return os.path.getmtime(read_path(apt_path))


def strip_flatten(apt_path: str) -> str:
    """Remove every ``1302 flatten 1`` row from the pack apt.dat, keeping
    the shipped file as its backup.  Returns ``"removed"`` (written now),
    ``"removed_before"`` (the live file already is our strip) or ``""``
    (no flatten row: nothing written).  Raises ``OSError`` on a failed
    write, the live file as it was."""
    v = classify(apt_path)
    if v.state is _bs.State.OURS:
        return "removed_before"
    if v.state in (_bs.State.REPLACED, _bs.State.UNPROVEN) and v.backup:
        _bs.adopt(v)            # the user's newer apt.dat: retire the backup
    data = _read(apt_path)
    if data is None or not carries_flatten(data):
        return ""
    backup = apt_path + BACKUP_SUFFIX
    if not os.path.isfile(backup):
        shutil.copy2(apt_path, backup + ".o4tmp")
        os.replace(backup + ".o4tmp", backup)
    with open(apt_path + ".o4tmp", "wb") as fh:
        fh.write(stripped(data))
    os.replace(apt_path + ".o4tmp", apt_path)
    _bs.invalidate_memo()
    return "removed"


def apt_dat_of(pack_root: str) -> str:
    """The pack's ``Earth nav data/apt.dat`` (the folder matched without
    regard to case), ``""`` when it has none."""
    import O4_Scenery_Packs as _SP
    p = os.path.join(_SP.earth_nav_data(pack_root), "apt.dat")
    return p if os.path.isfile(p) else ""


def pack_flatten(pack_root: str, *, write: bool) -> str:
    """The pack's flatten state: with ``write``, :func:`strip_flatten`'s
    answer; without, ``"found"`` when its apt.dat still carries the row,
    ``"removed_before"`` when it is our strip, else ``""``."""
    apt = apt_dat_of(pack_root)
    if not apt:
        return ""
    if write:
        return strip_flatten(apt)
    if classify(apt).state is _bs.State.OURS:
        return "removed_before"
    data = _read(apt)
    return "found" if data is not None and carries_flatten(data) else ""
