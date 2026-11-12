"""A converted tile's records kept where a new tile keeps them (owner
2026-11-12T21:56Z):

    "Shouldn't that move into the World folder for converted tiles just
    like new tiles? The point is not to need the old source because
    they've been converted..."

A tile the app builds for the World pack keeps its records in the data
root's ``Tiles/zOrtho4XP_<tile>/`` folder, where the scanner and the tile
pane read them (``O4_Tile_Info``).  A tile Convert existing tiles KEPT
(journal ``done``: built here or adopted) had them only in its homes:
its folder in the work folder's ``originals/``, its on-demand copy in
``lean/`` (the journal's ``config_dir``), its source on another drive.
:func:`copy_records` copies them into its Tiles folder, so the pane reads
it like any new tile and needs no old source:

* the tile cfgs (this app's, its ``.defaults``, Ortho4XP's), the imagery
  record, the rebuild pointer, the airport record
  (``o4_unpatched_airports.json``: the airports and their elevation inset
  sources), the colour field and the adopted stamp -- each from the FIRST
  home that has it (:func:`homes` order), written only where the Tiles
  folder has none or an older one (a later build's record there wins);
* ``build_logs/build_record.json`` -- merged by build (``start``), the
  newest ``O4_Tile_Build_Log.KEPT_BUILDS`` kept, each kept row's log
  copied when the folder lacks it.

The convert run calls it for each tile it keeps (``world_migrate``,
``world_adopt.readopt``); :func:`backfill` (``tools/ondemand_convert.py
world-records``) does it for the tiles kept before.  A drive that is not
connected is not a home, and no home is ever written.  The on-demand
copy's own stamp (``.ondemand_convert.json``) is not copied: it marks a
lean copy, which the Tiles folder is not.

No tile or airport is named here.
"""
from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

import O4_Config_Names as CN
import O4_File_Names as FNAMES
import O4_Tile_Build_Log as TLOG
import O4_Tile_Info as TINFO
import O4_Unpatched_Airports as UNPATCHED

__all__ = ["HOME_KINDS", "copy_quietly", "backfill"]

#: Where a record came from, in the order the homes are read.
HOME_ORIGINALS = "originals"
HOME_LEAN = "lean"
HOME_DRIVE = "drive"
HOME_KINDS = (HOME_ORIGINALS, HOME_LEAN, HOME_DRIVE)
_PREFIX = "zOrtho4XP_"
_KEPT = ("done",)


def _names(lat: int, lon: int) -> List[str]:
    """The record files of tile ``(lat, lon)`` (module docstring)."""
    cfg = CN.tile_cfg_name(lat, lon)
    return [cfg, cfg + ".defaults", CN.ortho4xp_tile_cfg_name(lat, lon),
            os.path.basename(TINFO.imagery_record_path("", lat, lon)),
            os.path.basename(FNAMES.tile_record_path("", lat, lon,
                                                      "rebuild")),
            UNPATCHED.UNPATCHED_SIDECAR, FNAMES.COLOR_FIELD_FILE,
            TINFO.ADOPTED_STAMP]


def homes(record: dict) -> List[Tuple[str, str]]:
    """``[(kind, folder)]`` of a journal record's homes there now, in
    :data:`HOME_KINDS` order (a drive not connected is absent)."""
    out, seen = [], set()
    for kind, folder in ((HOME_ORIGINALS, record.get("original")),
                         (HOME_LEAN, record.get("config_dir")),
                         (HOME_DRIVE, record.get("source"))):
        if not folder or not os.path.isdir(folder):
            continue
        real = os.path.realpath(folder)
        if real not in seen:
            seen.add(real)
            out.append((kind, folder))
    return out


def _takes(source: str, target: str) -> bool:
    """Should ``target`` take ``source`` (none there, or an older one)?"""
    if not os.path.exists(target):
        return True
    try:
        return os.path.getmtime(source) > os.path.getmtime(target)
    except OSError:
        return False


def _builds(home_list, tiles_dir: str, lat: int, lon: int) -> dict:
    """The merged build record (module docstring): ``{"rows", "kind",
    "logs": [(source, target)]}``; ``rows`` empty when no home adds a
    build the Tiles folder lacks."""
    tile = FNAMES.short_latlon(lat, lon)
    rows = TLOG._read_rows(tiles_dir)
    have = {row.get("start") for row in rows if row.get("tile") == tile}
    added, kind = [], None
    for home_kind, folder in home_list:
        for row in TLOG.read_records(folder, lat, lon):
            if row.get("start") not in have:
                have.add(row.get("start"))
                added.append((row, folder))
                kind = kind or home_kind
    if not added:
        return {"rows": [], "kind": None, "logs": []}
    mine = sorted([r for r in rows if r.get("tile") == tile]
                  + [row for row, _f in added],
                  key=lambda r: r.get("start") or 0, reverse=True)
    kept = mine[:TLOG.KEPT_BUILDS]
    ids = {id(row) for row in kept}
    new = [(row, folder) for row, folder in added if id(row) in ids]
    if not new:
        return {"rows": [], "kind": None, "logs": []}
    logs = []
    for row, folder in new:
        name = row.get("log") or ""
        if not name or os.path.basename(name) != name:
            continue
        source = os.path.join(TLOG.build_logs_dir(folder), name)
        target = os.path.join(TLOG.build_logs_dir(tiles_dir), name)
        if os.path.isfile(source) and not os.path.lexists(target):
            logs.append((source, target))
    others = [r for r in rows if r.get("tile") != tile]
    return {"rows": others + kept, "kind": kind, "logs": logs}


def plan(record: dict, lat: int, lon: int,
         tiles_dir: Optional[str] = None) -> Dict[str, Any]:
    """What :func:`copy_records` writes for one journal record, read
    only: ``{"tiles_dir", "files": [(kind, source, target)], "builds"
    (:func:`_builds`), "homes": [kinds there]}``."""
    tiles_dir = tiles_dir or FNAMES.build_dir(lat, lon, "")
    home_list = homes(record)
    files = []
    for name in _names(lat, lon):
        target = os.path.join(tiles_dir, name)
        for kind, folder in home_list:
            source = os.path.join(folder, name)
            if os.path.isfile(source):
                if _takes(source, target):
                    files.append((kind, source, target))
                break
    return {"tiles_dir": tiles_dir, "files": files,
            "builds": _builds(home_list, tiles_dir, lat, lon),
            "homes": [kind for kind, _f in home_list]}


def _outcome(todo: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """``(names written, home kinds used)`` of a :func:`plan`."""
    names = [os.path.basename(t) for _k, _s, t in todo["files"]]
    kinds = [k for k, _s, _t in todo["files"]]
    if todo["builds"]["rows"]:
        names.append(TLOG.RECORD_NAME)
        kinds.append(todo["builds"]["kind"])
    return names, sorted(set(kinds))


def copy_records(record: dict, lat: int, lon: int,
                 tiles_dir: Optional[str] = None) -> Dict[str, Any]:
    """Copy a kept tile's records from its homes into its Tiles folder
    (module docstring).  ``{"tiles_dir", "copied": [names], "from":
    [home kinds used], "homes"}``; nothing written when the folder has
    them all.  ``OSError`` when the Tiles folder cannot be written."""
    todo = plan(record, lat, lon, tiles_dir)
    folder, builds = todo["tiles_dir"], todo["builds"]
    if todo["files"] or builds["rows"]:
        os.makedirs(folder, exist_ok=True)
    for _kind, source, target in todo["files"]:
        shutil.copy2(source, target)             # its date: the record's
    if builds["rows"]:
        os.makedirs(TLOG.build_logs_dir(folder), exist_ok=True)
        for source, target in builds["logs"]:
            shutil.copy2(source, target)
        TLOG._write_rows(folder, builds["rows"])
    names, kinds = _outcome(todo)
    return {"tiles_dir": folder, "copied": names, "from": kinds,
            "homes": todo["homes"]}


def copy_quietly(journal, name: str, lat: int, lon: int) -> Optional[str]:
    """:func:`copy_records` for the convert run: the reason it could not,
    kept in the tile's journal record (``records_problem``), or None.  A
    tile is kept all the same (the pane falls back to its home)."""
    try:
        copy_records(journal.get(name) or {}, lat, lon)
    except OSError as error:
        journal.set(name, records_problem=str(error))
        return str(error)
    return None


def _kept(scenery_dir: str):
    """``(name, record, lat, lon)`` of every tile the journal kept."""
    import O4_World_Pack as WP

    from .world_migrate import Journal, work_dir_for
    journal = Journal(work_dir_for(scenery_dir))
    for name, record in sorted(journal.records.items()):
        if (not name.startswith(_PREFIX) or not isinstance(record, dict)
                or record.get("state") not in _KEPT or record.get("purged")):
            continue
        try:
            lat, lon = WP.parse_tile(name[len(_PREFIX):])
        except ValueError:
            continue
        yield name, record, lat, lon


def backfill(scenery_dir: str, *, dry_run: bool = True) -> Dict[str, Any]:
    """:func:`copy_records` for every tile the journal kept (a dry run
    reads only).  ``{"dry_run", "kept", "copied" (tiles given records),
    "complete" (had them all), "no_home" (names), "failed" ([{"name",
    "problems"}]), "from": {home kind: tiles}, "files", "summary"}``."""
    out: Dict[str, Any] = {"dry_run": bool(dry_run), "kept": 0, "copied": 0,
                           "complete": 0, "no_home": [], "failed": [],
                           "from": {k: 0 for k in HOME_KINDS}, "files": 0}
    for name, record, lat, lon in _kept(scenery_dir):
        out["kept"] += 1
        try:
            if dry_run:
                todo = plan(record, lat, lon)
                (names, kinds), there = _outcome(todo), todo["homes"]
            else:
                done = copy_records(record, lat, lon)
                names, kinds, there = done["copied"], done["from"], done["homes"]
        except OSError as error:
            out["failed"].append({"name": name, "problems": [str(error)]})
            continue
        if not there:
            out["no_home"].append(name)
        elif names:
            out["copied"] += 1
            out["files"] += len(names)
            for kind in kinds:
                out["from"][kind] += 1
        else:
            out["complete"] += 1
    out["summary"] = _summary(out)
    return out


def _summary(out: Dict[str, Any]) -> str:
    verb = "Would give" if out["dry_run"] else "Gave"
    origin = ", ".join(f"{n:,} from {k}" for k, n in out["from"].items() if n)
    text = (f"{verb} {out['copied']:,} of {out['kept']:,} kept tiles their "
            f"records in the Tiles folder ({out['files']:,} files"
            + (f"; {origin}" if origin else "") + ")")
    if out["complete"]:
        text += f"; {out['complete']:,} have them already"
    if out["no_home"]:
        text += (f"; {len(out['no_home']):,} have no home there now "
                 "(a drive not connected?): " + ", ".join(out["no_home"][:5]))
    text += "."
    if out["failed"]:
        text += (f" {len(out['failed']):,} failed: "
                 + "; ".join(f"{f['name']} ({f['problems'][0]})"
                             for f in out["failed"][:5]) + ".")
    return text
