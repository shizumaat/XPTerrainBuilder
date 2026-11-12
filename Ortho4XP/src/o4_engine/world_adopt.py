"""ADOPT the tiles another tool built (owner 2026-11-12T14:19Z):

    "For adopting Ortho4XP tiles: I want to be sure the app can do it ...
    Shouldn't we keep already downloaded imagery just near any custom
    airports, and then only if budget is full downgrade all the other
    imagery to 512px placeholders that then get dynamically downloaded
    and upgraded during flight? ... Rather than increasing budget it
    should use our system to intelligently offload imagery based on our
    priority criteria. Re-downloads get new imagery, that's acceptable"

Convert existing tiles KEEPS a tile (``world_retire.fate`` ``keep``) by
moving it into the World pack (``world_migrate``).  A kept tile another
tool built (``O4_Tile_Info.ours`` false) is ADOPTED: kept the same way
-- its mesh, terrain and masks drawn by the World pack, its imagery the
512 px placeholders of its on-demand copy -- and then made ours:

* :func:`finish` -- its on-demand copy gets the adopted stamp
  (``O4_Tile_Info.ADOPTED_STAMP``, which the Library, ``world_rechoose``
  and the package gates read as ours; a tile's own folder is never
  written: its journal record says it),
  its ADOPTED package (``tile_bundle.adopted``: DSF, terrain, masks,
  cfg; no imagery) is written into the package store while its source
  is readable, and its journal record says ``adopted``;
* :func:`readopt_candidates` / :func:`readopt` -- a tile an earlier run
  made DYNAMIC (journal ``dynamic``, chosen again or not; never one Free
  space removed) whose files are readable again is adopted when Convert
  runs with a choice that keeps it.  No link is made again: the World
  pack draws it; a drape of ours is replaced, a tile built here is not;
* :func:`keep_cores` -- once every tile of the run is in (the floor
  first), the squares near a custom airport
  (``O4_Imagery_OnDemand_Cores``: the cores) are landed at their tier
  from the imagery the tile already has -- never a download -- while
  the budget (``storage_budget.session_budget``, 90 % of it) and the
  disk (:data:`CORE_RESERVE_BYTES`) keep room, finest tier first.  Every
  other square stays 512 px: the follow job sharpens it in flight, from
  the provider once the tile's drive is gone (newer imagery, owner OK),
  and the budget's sweep makes it low-res again when the budget is full,
  cores last (``O4_Imagery_OnDemand_Index.lru_order``);
* :func:`room_left` / :data:`RESERVE_BYTES` -- a run writes a tile only
  while the disk keeps that much free (owner HARD RULE 2026-11-06);
* :func:`install_package` -- an adopted package installed
  (``package_install``): laid out as an on-demand copy and published
  into the World pack;
* :func:`plan` -- the dry run's figures of adopting;
* every adopted tile gets its X-Plane overlay like a built full tile
  (#2021): requested from ``overlay_queue`` by :func:`finish` and
  :func:`install_package`.

No tile or airport is named here.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from typing import Callable, Dict, Optional

import O4_File_Names as FNAMES
import O4_World_Pack as WP

__all__ = ["RESERVE_BYTES", "CORE_RESERVE_BYTES", "PACKAGE_SUFFIX",
           "room_left", "foreign", "finish",
           "readopt_candidates", "readopt", "keep_cores", "plan",
           "plan_copy_bytes", "PLAN_WORKERS",
           "install_package"]

#: A run writes a tile only while the disk keeps this much free.
RESERVE_BYTES = 30 * 10**9
#: ... and lands the cores' imagery only while it keeps this much.
CORE_RESERVE_BYTES = 50 * 10**9
#: ``<store>/<tile>_adopted.xptb`` (``storage_packages.store_dir``).
PACKAGE_SUFFIX = "_adopted.xptb"
_PREFIX = "zOrtho4XP_"
#: World-pack kinds an adoption may replace: nothing, a placeholder, a
#: drape of ours (a stand-in); never a tile built here (``full``).
_REPLACEABLE = (None, "placeholder", "drape")


def room_left(path: str) -> int:
    """Free bytes on the disk holding ``path`` (its nearest folder)."""
    probe = os.path.abspath(path or os.sep)
    while not os.path.exists(probe) and os.path.dirname(probe) != probe:
        probe = os.path.dirname(probe)
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return 0


def foreign(folder: Optional[str], lat: int, lon: int) -> bool:
    """Is ``folder`` a tile another tool built (not built here, not
    adopted)?  ``False`` when it cannot be read."""
    import O4_Tile_Info as TINFO
    if not folder or not os.path.isdir(folder):
        return False
    try:
        return not TINFO.ours(folder, lat, lon)
    except Exception:                       # unreadable: left as it is
        return False


def package_path(lat: int, lon: int) -> str:
    """Where tile ``(lat, lon)``'s adopted package is kept."""
    from . import storage_packages as STORE
    return os.path.join(STORE.store_dir(),
                        FNAMES.short_latlon(lat, lon) + PACKAGE_SUFFIX)


def _tool(dsf: str) -> str:
    """Who built the tile, as its DSF says (``""`` when it does not)."""
    import O4_Tile_Build_Log as TLOG
    try:
        return TLOG.dsf_creation_agent(dsf)
    except Exception:                       # unreadable: unknown
        return ""


def _stamp(folder: str, **fields) -> None:
    import O4_Tile_Info as TINFO
    path = os.path.join(folder, TINFO.ADOPTED_STAMP)
    with open(path + ".part", "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"adopted": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            time.gmtime()), **fields},
                  handle, indent=1,
                  sort_keys=True)
    os.replace(path + ".part", path)


def _source_dsf(record: dict, lat: int, lon: int) -> str:
    from . import world_originals as ORIGINALS
    home = ORIGINALS.home(record) or record.get("source") or ""
    return os.path.join(home, WP.dsf_relpath(lat, lon)) if home else ""


def finish(name: str, *, journal, pack: str, lat: int, lon: int) -> dict:
    """Make the kept tile ``name`` (journal ``done``) ours: stamp its
    folder, write its adopted package, journal ``adopted``.  A package
    that cannot be written leaves its reason in ``package_problem``; the
    tile is adopted all the same.  ``{"package", "package_bytes"}``."""
    from tile_bundle import BundleRefused
    from tile_bundle import adopted as ADOPTED

    from . import world_originals as ORIGINALS
    record = journal.get(name) or {}
    folder = record.get("config_dir")
    tool = _tool(os.path.join(pack, WP.dsf_relpath(lat, lon)))
    own = {os.path.realpath(p) for p in (record.get("source"),
                                         ORIGINALS.home(record)) if p}
    if folder and os.path.isdir(folder) and os.path.realpath(folder) not in own:
        # the on-demand copy is ours; a tile's own folder is never written
        _stamp(folder, source=record.get("source") or "", built_by=tool)
    out = {"package": None, "package_bytes": 0}
    try:
        done = ADOPTED.save(folder or "", _source_dsf(record, lat, lon),
                            lat, lon, package_path(lat, lon), tool)
        out.update(package=done["path"], package_bytes=done["bytes"])
        journal.set(name, adopted=True, built_by=tool, package_problem="",
                    **out)
    except (BundleRefused, OSError, ValueError) as error:
        journal.set(name, adopted=True, built_by=tool,
                    package_problem=str(error), **out)
    _request_overlay(pack, lat, lon)
    return out


def _request_overlay(pack: str, lat: int, lon: int) -> None:
    """An adopted full tile gets its X-Plane overlay like a built one
    (#2021): queued, beside the World pack's Custom Scenery folder."""
    from . import overlay_queue as OVERLAYS
    OVERLAYS.request(lat, lon, os.path.dirname(os.path.normpath(pack)))


# ------------------------------------------------------------- re-adopt


def _kept_by(choice: str, tile: tuple, custom) -> bool:
    from . import world_retire as RETIRE
    return choice == RETIRE.KEEP_ALL or (choice == RETIRE.KEEP_CUSTOM
                                         and tile in custom)


def _pending(records: Dict[str, dict], choice: str, custom, names=None):
    """``(name, record, tile)`` of the journalled tiles :func:`readopt`
    may take under ``choice``, from the journal alone (no file read):
    made dynamic (or a readoption half done), not removed by Free space."""
    wanted = set(names) if names else None
    for name, record in sorted(records.items()):
        state = record.get("state")
        if wanted is not None and name not in wanted:
            continue
        if not (state == "dynamic" or (record.get("readopt")
                                       and state in ("staging", "swapped"))):
            continue
        if record.get("purged"):
            continue
        try:
            tile = WP.parse_tile(name[len(_PREFIX):])
        except ValueError:
            continue
        if _kept_by(choice, tile, custom):
            yield name, record, tile


def _readable(home: Optional[str], tile: tuple, facts=None) -> bool:
    """Are the files of a :func:`_pending` tile at ``home`` readable and
    another tool's (``facts``: a ``world_tile_facts.TileFacts``)?"""
    if not home:
        return False
    if facts is None:
        return (os.path.isfile(os.path.join(home, WP.dsf_relpath(*tile)))
                and foreign(home, *tile))
    return bool(facts.get(home, *tile, "readable",
                          lambda: _readable(home, tile)))


def readopt_candidates(records: Dict[str, dict], choice: str, custom,
                       names=None) -> list:
    """``[(name, record)]`` of the journalled tiles :func:`readopt` takes
    under ``choice``: made dynamic (or a readoption half done), not
    removed by Free space, another tool's, their files readable."""
    from . import world_originals as ORIGINALS
    return [(name, record)
            for name, record, tile in _pending(records, choice, custom, names)
            if _readable(ORIGINALS.home(record), tile)]


def _entry(name: str, record: dict, scenery_dir: str):
    """The ``world_migrate`` entry of a journalled tile, read from where
    its files are now."""
    from . import world_originals as ORIGINALS
    from .imagery_convert import _Entry
    lat, lon = WP.parse_tile(name[len(_PREFIX):])
    kind = record.get("kind") or "dir"
    kind = "link" if kind.startswith("link") else kind
    return _Entry(name, os.path.join(scenery_dir, name), lat, lon, kind,
                  ORIGINALS.home(record) or record.get("source") or "", True)


def readopt(name: str, record: dict, *, scenery_dir: str, pack: str,
            work: str, journal, swap_lock: threading.Lock, px: int,
            threads: int, index: Optional[str] = None) -> dict:
    """Adopt one :func:`readopt_candidates` tile (module doc); the row
    of the result.  A tile that fails goes back to ``dynamic`` (its
    placeholder still drawn) with its reasons."""
    from . import world_migrate as MIGRATE
    entry = _entry(name, record, scenery_dir)
    out = {"name": name, "kind": entry.kind, "action": "adopt"}
    dsf = os.path.join(pack, WP.dsf_relpath(entry.lat, entry.lon))
    held = WP.kind_of(dsf)
    if record.get("state") == "dynamic":
        if held not in _REPLACEABLE:
            return {**out, "status": "skip: the World pack has a tile "
                                     "built here"}
        record = journal.set(name, state="staging", readopt=True, prior=held)
    if record.get("state") == "staging":
        record = MIGRATE._stage_and_swap(entry, record, pack=pack, work=work,
                                         journal=journal, swap_lock=swap_lock,
                                         px=px, threads=threads)
        if record.get("state") != "swapped":
            journal.set(name, state="dynamic", readopt=False,
                        problems=record["problems"])
            return {**out, "status": "failed", "problems": record["problems"]}
    out["index_rows"] = MIGRATE._index(record["config_dir"], entry.lat,
                                       entry.lon, pack, index)
    journal.set(name, state="done", readopt=False, rechosen=False,
                problems=[])
    out.update(finish(name, journal=journal, pack=pack, lat=entry.lat,
                      lon=entry.lon))
    from . import world_records as RECORDS
    RECORDS.copy_quietly(journal, name, entry.lat, entry.lon)
    return {**out, "status": "migrated", "adopted": True,
            "bytes_written": record.get("bytes_written", 0)}


# --------------------------------------------------------------- cores


def _sharp_room(index: Optional[str]) -> int:
    """Bytes of sharp imagery the budget takes before 90 % of it."""
    import O4_Imagery_OnDemand_Index as INDEX

    from . import imagery_downgrade as DOWNGRADE
    from . import storage_budget as SBUDGET
    conn = INDEX.open_index(index)
    try:
        budget = SBUDGET.session_budget(conn, DOWNGRADE.cap_bytes())
        return (int(budget.cap * DOWNGRADE.LOW_WATER)
                - budget.total(INDEX.capped_bytes(conn)))
    finally:
        conn.close()


def keep_cores(tiles, *, index: Optional[str] = None, work: str = "",
               lander=None, room: Optional[int] = None) -> dict:
    """Land the core squares of ``tiles`` (``(folder, lat, lon)``) from
    the imagery they have (module doc); ``fetch_cores``' counts with
    ``bytes`` landed, ``room`` (the budget's room before) and
    ``no_room`` (squares left low-res for want of room)."""
    from . import imagery_after_build as AFTER
    from .imagery_follow_land import TierLander
    room = _sharp_room(index) if room is None else int(room)
    base = lander or TierLander(source_only=True)
    held = {"bytes": 0, "no_room": 0}
    lock = threading.Lock()

    def land(row: dict, tier: int) -> dict:
        with lock:
            full = (held["bytes"] >= room
                    or room_left(work or row.get("build_dir") or "")
                    < CORE_RESERVE_BYTES)
            held["no_room"] += full
        if full:
            raise RuntimeError("no room left in the budget or on the disk")
        facts = base(row, tier)
        with lock:
            held["bytes"] += int(facts.get("full_bytes") or 0)
        return facts
    counts = AFTER.fetch_cores(list(tiles), index=index, lander=land)
    return {**counts, **held, "room": room}


# ---------------------------------------------------------------- plan


def _ters(folder: str) -> list:
    """``[[texture, centre lat, centre lon, S]]`` of every ``.ter`` of
    ``folder``'s ``terrain/`` (``O4_Imagery_OnDemand_Index._read_ter``)."""
    import O4_Imagery_OnDemand_Index as INDEX
    terrain = os.path.join(folder, "terrain")
    out = []
    for name in sorted(os.listdir(terrain)) if os.path.isdir(terrain) else ():
        read = INDEX._read_ter(os.path.join(terrain, name)) \
            if name.endswith(".ter") else None
        if read is not None:
            out.append(list(read))
    return out


def _core_bytes(ters: list, points, source: Optional[str]) -> int:
    """What landing the cores of one tile from its source takes: each
    ``.ter``'s square inside a core, its source DDS at the core's tier."""
    import O4_Imagery_OnDemand_Cores as CORES
    if not points or not source:
        return 0
    total = 0
    for texture, clat, clon, size in ters:
        row = {"centre_lat": clat, "centre_lon": clon, "load_size_m": size}
        tier = CORES.core_tier(row, points)
        if tier is None:
            continue
        try:
            full = os.path.getsize(os.path.join(source, "textures", texture))
        except OSError:
            continue
        total += full >> (2 * (3 - tier))
    return total


def _plan_row(name: str, record: dict, points, px: int, facts) -> Optional[dict]:
    """What re-adopting one :func:`_pending` tile writes and keeps;
    ``None`` when its files are not readable (not a candidate).  Header
    reads go through ``facts`` (``world_tile_facts.TileFacts``)."""
    import O4_Imagery_OnDemand_Convert as CONVERT

    from . import world_originals as ORIGINALS
    from .world_migrate_size import _dsf_facts
    lat, lon = WP.parse_tile(name[len(_PREFIX):])
    home = ORIGINALS.home(record)
    if not _readable(home, (lat, lon), facts):
        return None
    lean = record.get("config_dir")
    row = {"custom": bool(points), "copy_bytes": 0,
           "dsf_bytes": _dsf_facts(home, lat, lon, facts)[0]}
    copied = bool(lean) and CONVERT.is_converted(lean)
    if not copied and (record.get("kind") or "").startswith("link"):
        row["copy_bytes"] = plan_copy_bytes(home, lat, lon, px, facts)[0]
    if points:
        folder = lean if copied else home
        row["core_bytes"] = _core_bytes(
            facts.get(folder, lat, lon, "ters", lambda: _ters(folder)),
            points, home)
    else:
        row["core_bytes"] = 0
    return row


def plan_copy_bytes(source: str, lat: int, lon: int, px: int, facts) -> list:
    """``[bytes an on-demand copy of source writes (placeholders and
    copies), bytes of its full textures]`` (``O4_Imagery_OnDemand_Convert
    .plan_tile``), kept in ``facts``."""
    import O4_Imagery_OnDemand_Convert as CONVERT

    def compute() -> list:
        found = CONVERT.plan_tile(source, px)
        return [found.total("textures") + found.total("copies"),
                found.total("source_textures")]
    return facts.get(source, lat, lon, "plan_%d" % int(px), compute)


#: Tile folders read at once by :func:`plan` (owner 2026-11-12T19:08Z: a
#: bounded few, at background priority beside a build).
PLAN_WORKERS = 4


def plan(records: Dict[str, dict], custom_points: dict, px: int,
         names=None, *, facts=None,
         progress: Optional[Callable[[int, int, str], None]] = None,
         stopping: Callable[[], bool] = lambda: False) -> Dict[str, dict]:
    """The dry run's figures of re-adopting, per choice
    (``world_retire.CHOICES``): ``{"tiles", "new_bytes", "dsf_bytes",
    "copy_bytes", "core_bytes", "custom_tiles"}``.  ``custom_points``:
    ``{(lat, lon): [(icao, lat, lon)]}``
    (``O4_Custom_Scenery.airport_points_by_tile``).  Reads headers and
    ``stat`` only, through ``facts`` (``world_tile_facts.TileFacts``; a
    fresh one, kept nowhere, when omitted), :data:`PLAN_WORKERS` tiles at
    once; ``progress(done, total, name)`` counts the journalled tiles
    read; ``stopping()`` true ends it early (the figures are then
    partial: the caller raises)."""
    from concurrent.futures import ThreadPoolExecutor

    from . import world_retire as RETIRE
    from .world_migrate_size import _counter
    from .world_tile_facts import TileFacts
    facts = facts if facts is not None else TileFacts()
    pending = list(_pending(records, RETIRE.KEEP_ALL, custom_points, names))
    tick = _counter(progress, len(pending))
    if progress and pending:
        progress(0, len(pending), "")

    def one(item) -> Optional[dict]:
        name, record, tile = item
        if stopping():
            return None
        row = _plan_row(name, record, custom_points.get(tile) or [], px, facts)
        tick(name)
        return row
    with ThreadPoolExecutor(PLAN_WORKERS, thread_name_prefix="o4-adopt-plan") as pool:
        rows = [r for r in pool.map(one, pending) if r is not None]
    out = {}
    for choice in RETIRE.CHOICES:
        picked = [r for r in rows
                  if choice == RETIRE.KEEP_ALL
                  or (choice == RETIRE.KEEP_CUSTOM and r["custom"])]
        t = {key: sum(r[key] for r in picked)
             for key in ("dsf_bytes", "copy_bytes", "core_bytes")}
        t.update(tiles=len(picked), custom_tiles=sum(r["custom"] for r in picked),
                 new_bytes=t["dsf_bytes"] + t["copy_bytes"])
        out[choice] = t
    return out


# ------------------------------------------------------------- install


def _placeholders(folder: str, lat: int, lon: int, names) -> list:
    """Each DDS of ``names`` fetched at the placeholder tier from its
    provider into ``folder`` (``imagery_follow_land.TierLander``); the
    names that did not land."""
    import O4_Imagery_OnDemand_Index as INDEX

    from .imagery_follow_land import TierLander
    lander, missing = TierLander(), []
    for name in names:
        zl, provider = INDEX._identity(name)
        row = {"tile": FNAMES.short_latlon(lat, lon), "name": name, "zl": zl,
               "provider": provider, "build_dir": folder}
        try:
            lander(row, 0)
        except Exception:                   # listed: fetched when flown
            missing.append(name)
    return missing


def install_package(path: str, scenery_dir: str = "") -> dict:
    """Install the adopted package ``path``: laid out in the work
    folder's ``lean/`` (``tile_bundle.adopted.lay_out``; placeholders
    already there kept, the others fetched at 512 px), published into
    the World pack and journalled ``done`` + ``adopted``.  Refused while
    X-Plane runs.  ``{"installed", "tile", "missing"}``."""
    from tile_bundle import BundleRefused
    from tile_bundle import adopted as ADOPTED
    from tile_bundle.install import read_manifest

    from . import world_commands as WORLD
    from . import world_migrate as MIGRATE
    from .imagery_convert import _Entry
    if MIGRATE._xplane_running():
        raise BundleRefused("Quit X-Plane first: an adopted tile goes into "
                            "the World pack only while it is closed.")
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    if not scenery_dir or not os.path.isdir(scenery_dir):
        raise BundleRefused("No Custom Scenery folder to install into.")
    WORLD.refuse_foreign(scenery_dir)
    tile = read_manifest(path).get("tile", "")
    lat, lon = WP.parse_tile(tile)
    name = _PREFIX + tile
    work = MIGRATE.work_dir_for(scenery_dir)
    folder = os.path.join(work, "lean", name)
    with MIGRATE.active_run():
        laid = ADOPTED.lay_out(path, folder)
        missing = _placeholders(folder, lat, lon, laid["missing"])
        pack = MIGRATE._ready_pack(scenery_dir)
        journal, lock = MIGRATE.Journal(work), threading.Lock()
        journal.set(name, state="staging", kind="package", source=folder,
                    prior=WP.kind_of(os.path.join(pack, WP.dsf_relpath(lat, lon))))
        entry = _Entry(name, os.path.join(scenery_dir, name), lat, lon,
                       "package", folder, True)
        record = MIGRATE._stage_and_swap(entry, {}, pack=pack, work=work,
                                         journal=journal, swap_lock=lock,
                                         px=512, threads=4)
        if record.get("state") != "swapped":
            raise BundleRefused("; ".join(record["problems"]))
        MIGRATE._index(folder, lat, lon, pack, None)
        _stamp(folder, source=path, built_by=read_manifest(path).get("built_by", ""))
        journal.set(name, state="done", adopted=True, package=path,
                    problems=[])
    _request_overlay(pack, lat, lon)
    return {"installed": laid["files"], "tile": tile, "missing": missing}
