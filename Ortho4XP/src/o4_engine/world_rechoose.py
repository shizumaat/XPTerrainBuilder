"""Choose again for tiles Convert existing tiles KEPT: make them DYNAMIC
(after the 2026-11-11 Convert run: keep only the tiles this app built,
make the other tools' tiles dynamic so their drive can retire).

A kept tile (``world_migrate`` journal state ``done``) is a real tile in
the World pack: its DSF, ``terrain/<tile>/`` and ``textures/<tile>/``.
:func:`rechoose` turns each one picked into what ``world_retire`` makes
a dynamic tile:

* the World pack's tile is swapped out for its placeholder in ONE step
  (``O4_World_Pack.swap_out``: the placeholder renamed over the DSF, so
  no moment has neither), verified, then its folders are removed
  (X-Plane is closed; a local tile's textures there are hard links, its
  own folder keeps the files);
* its on-demand index rows are forgotten (``world_retire._forget``);
* a LINK entry (its tile on another drive) is removed from Custom
  Scenery, its target journalled; its row stays disabled (filed again
  when another program dropped it);
* the journal record goes ``done`` -> ``dynamic`` with ``rechosen: true``,
  keeping ``config_dir`` (the lean on-demand copy, which a later Convert
  reuses) and ``prior``.  Undo (``world_migrate.revert``) therefore gives
  a rechosen tile back exactly as it gives back any dynamic one: its link
  made again, its row enabled, its own pack drawing it.

``only_not_ours`` picks the kept tiles NOT built by XPTerrainBuilder
(``O4_Tile_Info.built_here`` of the tile's source folder, else of its
lean copy, which carries the tile cfg); a tile neither folder can tell
is left kept and counted ``unknown``.  Before anything moves, every kept
tile of the selection this app DID build gets its package written
(``o4_engine.package_first``, as ``world_retire._package_first`` does)
and its lean copy the mask PNGs and colour field a provider landing
needs (``O4_Imagery_OnDemand_Convert.backfill``) while its source is
readable.  The dry run (``dry_run``) only counts.
Refused while X-Plane runs, and while the World pack is missing.

No tile or airport is named here.
"""
from __future__ import annotations

import os
import shutil
import threading
from typing import Any, Callable, Dict, Optional

import O4_World_Pack as WP

from . import world_migrate as MIGRATE
from . import world_retire as RETIRE

__all__ = ["rechoose", "start_world_rechoose"]

_PREFIX = "zOrtho4XP_"


def _tile_of(name: str) -> tuple:
    return WP.parse_tile(name[len(_PREFIX):])


def _ours(record: dict, lat: int, lon: int) -> Optional[bool]:
    """Did this app build the tile?  ``None`` when no folder can tell."""
    import O4_Tile_Info as TINFO
    for folder in (record.get("source"), record.get("config_dir")):
        if folder and os.path.isdir(folder):
            try:
                return TINFO.built_here(folder, lat, lon)
            except Exception:              # an unreadable folder: next one
                continue
    return None


def _sort(records: dict, names, only_not_ours: bool,
          links_only: bool = False) -> Dict[str, list]:
    """``{"pick", "ours", "unknown"}`` of the kept tiles (``names`` and
    ``links_only`` -- entries that were links to another drive -- limit
    them): ``pick`` becomes dynamic, ``ours`` (built here) is packaged
    first, ``unknown`` is left kept."""
    wanted = set(names) if names else None
    out: Dict[str, list] = {"pick": [], "ours": [], "unknown": []}
    for name, record in sorted(records.items()):
        if record.get("state") != "done" or (wanted is not None
                                             and name not in wanted):
            continue
        if links_only and record.get("kind") not in ("link", "link-unmounted"):
            continue
        try:
            lat, lon = _tile_of(name)
        except ValueError:
            continue
        ours = _ours(record, lat, lon)
        if ours:
            out["ours"].append(name)
        if not only_not_ours or ours is False:
            out["pick"].append(name)
        elif ours is None:
            out["unknown"].append(name)
    return out


def _package_ours(names, records: dict, dry_run: bool) -> Dict[str, int]:
    """Each tile of ``names`` (built here) packaged from its source folder
    (``package_first``), and its lean copy given the mask PNGs and colour
    field it may lack (``O4_Imagery_OnDemand_Convert.backfill``: a kept
    tile lands its full tier from the provider once its drive retires);
    ``{action: tiles}``."""
    import O4_Imagery_OnDemand_Convert as CONVERT

    from . import package_first as FIRST
    first = FIRST.Pass(dry_run=dry_run)
    for name in names:
        source = records[name].get("source")
        if source and os.path.isdir(source):
            RETIRE._package_first(first, source, name)
            lean = records[name].get("config_dir")
            if not dry_run and lean and CONVERT.is_converted(lean):
                CONVERT.backfill(lean)
    counts: Dict[str, int] = {}
    for done in first.done.values():
        if done:
            counts[done["action"]] = counts.get(done["action"], 0) + 1
    return counts


def _rechoose_one(name: str, record: dict, *, scenery_dir: str, pack: str,
                  journal, index: Optional[str]) -> None:
    """One kept tile made dynamic (module doc); idempotent."""
    lat, lon = _tile_of(name)
    path = os.path.join(scenery_dir, name)
    target = record.get("link_target") or (
        os.readlink(path) if os.path.islink(path) else None)
    WP.swap_out(pack, lat, lon)             # the placeholder, in one rename
    if WP.kind_of(os.path.join(pack, WP.dsf_relpath(lat, lon))) != "placeholder":
        raise OSError(f"{name}: the World pack's placeholder did not land.")
    for sub in ("terrain", "textures"):
        shutil.rmtree(os.path.join(pack, sub, WP.tile_name(lat, lon)),
                      ignore_errors=True)
    RETIRE._forget(lat, lon, index)
    MIGRATE._set_row(scenery_dir, name, enabled=False)
    if target and os.path.islink(path):
        os.unlink(path)                     # the link only, never its target
    journal.set(name, state="dynamic", rechosen=True, link_target=target,
                problems=[])


def rechoose(scenery_dir: str, names=None, *, only_not_ours: bool = False,
             links_only: bool = False,
             dry_run: bool = False, work_dir: Optional[str] = None,
             index: Optional[str] = None,
             progress: Optional[Callable[[int, int, str], None]] = None
             ) -> Dict[str, Any]:
    """Make the kept tiles ``names`` (all when omitted; with
    ``only_not_ours`` only those another tool built; with ``links_only``
    only the entries that were links to another drive) dynamic.  ``{"dry_run",
    "rechosen" (names; a count in the dry run), "ours", "unknown",
    "packaged" ({action: tiles}), "failed" ([{"name", "problems"}]),
    "pack_missing", "summary"}`` (``summary``: the sentence).  The engine
    command and ``tools/ondemand_convert.py world-rechoose`` call it."""
    from . import world_commands as WORLD
    if MIGRATE._xplane_running():
        raise ValueError("Quit X-Plane first: tiles leave the World pack "
                         "only while it is closed.")
    WORLD.refuse_foreign(scenery_dir)
    if not WORLD.managed(scenery_dir):
        raise ValueError("The World pack is not installed: no tile is kept "
                         "in it to choose again.")
    work = work_dir or MIGRATE.work_dir_for(scenery_dir)
    journal = MIGRATE.Journal(work)
    sort = _sort(journal.records, names, only_not_ours, links_only)
    out: Dict[str, Any] = {"dry_run": bool(dry_run), "ours": len(sort["ours"]),
                           "unknown": len(sort["unknown"]), "failed": []}
    with MIGRATE.active_run():
        out["packaged"] = _package_ours(sort["ours"], journal.records, dry_run)
        if dry_run:
            out.update(rechosen=len(sort["pick"]), pack_missing=0)
            return {**out, "summary": _summary(out)}
        pack = WORLD.pack_dir(scenery_dir)
        done = []
        for count, name in enumerate(sort["pick"], 1):
            try:
                _rechoose_one(name, journal.get(name), scenery_dir=scenery_dir,
                              pack=pack, journal=journal, index=index)
                done.append(name)
            except (OSError, ValueError) as error:
                journal.set(name, problems=[str(error)])
                out["failed"].append({"name": name, "problems": [str(error)]})
            if progress:
                progress(count, len(sort["pick"]), name)
        out["rechosen"] = done
        out["pack_missing"] = len(MIGRATE.missing_from_pack(
            scenery_dir, work_dir=work))
    WORLD.write_log({"rechoose": len(done), "failed": len(out["failed"]),
                     "only_not_ours": bool(only_not_ours),
                     "links_only": bool(links_only)})
    return {**out, "summary": _summary(out)}


def _summary(result: Dict[str, Any]) -> str:
    """The sentence of a :func:`rechoose` result."""
    count = result["rechosen"]
    count = count if isinstance(count, int) else len(count)
    verb = "Would make" if result.get("dry_run") else "Made"
    text = (f"{verb} {count:,} kept tiles dynamic; {result['ours']:,} of the "
            "kept tiles were built by XPTerrainBuilder")
    packaged = result.get("packaged") or {}
    if packaged:
        text += " (packages: " + ", ".join(
            f"{n:,} {action.replace('_', ' ')}"
            for action, n in sorted(packaged.items())) + ")"
    text += "."
    if result.get("unknown"):
        text += (f" {result['unknown']:,} stay kept: their drive is not "
                 "connected, so who built them is not known.")
    if result.get("failed"):
        text += f" {len(result['failed']):,} failed."
    if result.get("pack_missing"):
        text += " " + MIGRATE.pack_missing_sentence(result["pack_missing"])
    return text


def start_world_rechoose(emit: Callable[[Any], None], request: Any = None,
                         tiles=None, only_not_ours: bool = False,
                         links_only: bool = False,
                         dry_run: bool = True, scenery_dir: str = "",
                         **_ignored) -> dict:
    """ENGINE COMMAND ``world_rechoose``: :func:`rechoose` of ``tiles``
    (entry names; every kept tile when omitted), a dry run unless
    ``dry_run`` is false.  Replies ``{"status": "started"}``;
    ``WorldReady`` (``request`` = this command's id) carries the result.
    Shares ``world_migrate``'s one-run lock."""
    from . import world_commands as WORLD
    from .events import WorldReady
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    if not MIGRATE._RUN.acquire(blocking=False):
        raise ValueError("world_rechoose: a migration is already running.")

    def work() -> None:
        try:
            result = rechoose(scenery_dir, tiles,
                              only_not_ours=bool(only_not_ours),
                              links_only=bool(links_only),
                              dry_run=bool(dry_run),
                              progress=MIGRATE._count_events(emit, "move"))
        except Exception as error:            # the sentence goes to the app
            emit(WorldReady(request=request, result=None,
                            error=str(error) or repr(error)))
            return
        finally:
            MIGRATE._RUN.release()
        emit(WorldReady(request=request, result=result))
        if not dry_run:
            emit(WORLD.status_event(scenery_dir))
    threading.Thread(target=work, daemon=True,
                     name="o4-world-rechoose").start()
    return {"status": "started"}
