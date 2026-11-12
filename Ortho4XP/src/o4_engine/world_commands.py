"""The World pack's commands (flight manager / World spec §5.2, §7,
capability ``world_pack``): ONE Custom Scenery pack (``O4_World_Pack``)
holds every tile the app manages, placeholders where none is built.

* :func:`world_status` -- sync: the fields of ``WorldStatus`` plus the
  region rows (``regions``).
* :func:`world_onboard` -- at the app's start: the World pack made when
  its folder does not exist (owner 2026-11-11, RULINGS 2026-11-11a), and
  how many per-tile packs "Convert existing tiles" could move -- offered
  ONCE (RULINGS 2026-11-11h (2): :data:`OFFERED_KEY` in the pack's
  marker), whether the pack was made now or before.
* :func:`world_install` -- the pack folder, its marker (:func:`managed`:
  builds publish only into a pack the app made) and its
  ``scenery_packs.ini`` row; ``restart_needed`` when X-Plane runs (a new
  pack is read at start).
* :func:`start_world_regions_set` -- the on-demand regions (RULINGS
  2026-11-10e (3): the ``imagery_on_demand_<region>`` switches) set, then
  placeholders written for the tiles of the regions turned on that X-Plane's
  own scenery holds, and the regions turned off given back (their drape
  tiles swapped out, their placeholders removed; full tiles
  stay).  Replies ``{"status": "started"}``; ``WorldReady`` completes it.
* :func:`world_tile_set` -- "Give this tile back": the placeholder over the
  tile (``swap_out``, spec §7.4); its folders go only when X-Plane cannot
  hold them.

A command module, not a session method (``imagery_commands`` gives the
reason): it stays out of the session's import closure.  Paths: the pack
is ``<Custom Scenery>/<PACK_NAME>``; staged tiles live under the data
folder (``World_staging``); X-Plane's ``Log.txt`` is beside its Custom
Scenery folder.  Every change is a line of ``logs/world_pack.log``.
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import threading
import time
from typing import Any, Callable, Dict, Optional

import O4_File_Names as FNAMES
import O4_World_Pack as WP

__all__ = ["LOG_NAME", "S3_MARGIN_KM", "pack_dir", "staging_root", "scenery_dir_or_default",
           "managed", "refuse_foreign",
           "OFFERED_KEY",
           "tile_loaded", "world_status", "world_install", "world_onboard",
           "start_world_regions_set", "world_tile_set",
           "status_event", "write_log"]

LOG_NAME = "world_pack.log"
#: Rule S3's margin outside the window: 0.05° (the 60 s of flight it also
#: names needs a speed: ``tile_loaded(speed_ms=)``, and the build-ahead
#: job's own rule, ``world_job.WorldJob.held``).
S3_MARGIN_KM = 0.05 * 111.32
_GLOBAL_PACK = os.path.join("Global Scenery", "X-Plane 12 Global Scenery")
_GUARD = threading.Lock()


def scenery_dir_or_default(scenery_dir: str = "") -> str:
    """``scenery_dir``, else the app's ``custom_scenery_dir`` setting."""
    if scenery_dir:
        return str(scenery_dir)
    try:
        import O4_Settings_Model as SM
        return SM.read_global_raw().get("custom_scenery_dir", "") or ""
    except Exception:                       # no readable settings: none
        return ""


def pack_dir(scenery_dir: str) -> str:
    """The World pack's folder in a Custom Scenery folder."""
    return os.path.join(scenery_dir, WP.PACK_NAME)


#: ``world_onboard``'s ``reason`` when the World folder is not the app's.
_FOREIGN_REASON = "world_foreign"


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:                      # other drive (Windows)
        return False


def _foreign_target(scenery_dir: str) -> str:
    """Where the World folder really is when it is NOT the app's own
    World pack, else ``""``: a link (another tool's or a test kit's), or a
    folder whose real path lies outside the Custom Scenery folder, inside
    the app's data folder, or inside a ``.harness`` folder.  No command
    makes, offers into, moves into or writes through such a folder."""
    if not scenery_dir:
        return ""
    path = pack_dir(scenery_dir)
    if not os.path.islink(path) and not os.path.isdir(path):
        return ""                           # absent: world_install makes it
    if os.path.islink(path):
        return os.path.realpath(path)
    real = os.path.realpath(path)
    if not _inside(real, os.path.realpath(scenery_dir)):
        return real
    if ".harness" in real.split(os.sep):
        return real
    try:
        data_root = os.path.realpath(FNAMES.current_data_root())
    except Exception:                       # no data root resolved: no test
        data_root = ""
    if data_root and _inside(real, data_root):
        return real
    return ""


def _foreign_sentence(target: str) -> str:
    """The apps' sentence for a foreign World folder (``O4_Storage_Text``)."""
    import O4_Storage_Text as TEXT
    return TEXT.WORLD_FOREIGN.format(target=target)


def refuse_foreign(scenery_dir: str) -> None:
    """``ValueError`` (the sentence) when the World folder is foreign."""
    target = _foreign_target(scenery_dir)
    if target:
        raise ValueError(_foreign_sentence(target))


def staging_root() -> str:
    """Where staged tiles wait (never inside Custom Scenery)."""
    return FNAMES.data_path(WP.STAGING_DIR)


def write_log(record: Dict[str, Any]) -> None:
    """One JSON line of ``logs/world_pack.log`` (spec §7.5 S8)."""
    with contextlib.suppress(OSError):
        folder = FNAMES.data_path("logs")
        os.makedirs(folder, exist_ok=True)
        line = json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                time.gmtime()), **record})
        with open(os.path.join(folder, LOG_NAME), "a", encoding="utf-8",
                  newline="\n") as handle:
            handle.write(line + "\n")


def _ini_path(scenery_dir: str) -> str:
    return os.path.join(scenery_dir, "scenery_packs.ini")


def _ini_has_row(scenery_dir: str) -> bool:
    import O4_Scenery_Packs as SP
    try:
        lines, _nl = SP.read_ini_lines(_ini_path(scenery_dir))
    except OSError:
        return False
    return any(SP.pack_name_from_ini_path(line.split(None, 1)[1]) == WP.PACK_NAME
               for line in lines
               if line.startswith("SCENERY_PACK ") and len(line.split(None, 1)) == 2)


def _xplane_running() -> bool:
    from .xplane_root import xplane_running
    return xplane_running()


def _witness(scenery_dir: str):
    """``(loads, packages)`` of X-Plane's current ``Log.txt``: the World
    pack's tiles loaded this session ``{(lat, lon): DsfLoad}`` and the
    packs the session listed (``[]`` when not read yet)."""
    import O4_XPlane_Log as XLOG
    tail = XLOG.LogTail(XLOG.log_path(os.path.dirname(
        os.path.normpath(scenery_dir))))
    records = tail.read()
    return XLOG.pack_loads(records, WP.PACK_NAME), tail.packages


def tile_loaded(scenery_dir: str,
                position: Optional[Callable[[], Optional[tuple]]] = None,
                speed_ms: Optional[float] = None) -> Callable[[int, int], bool]:
    """The predicate of rule S3 for one moment: may X-Plane hold tile
    ``(lat, lon)``?  Never, while X-Plane does not run.  While it runs:
    yes when the witness shows a load of it this session, or the aircraft
    (``position()`` -> ``(lat, lon)``; default the shared position feed's
    latest, ``position_feed.latest_position``) has it in
    the union of the plausible DSF windows or within the S3 margin of
    entering it (:data:`S3_MARGIN_KM`, or 60 s of flight at ``speed_ms``
    when more, ``O4_World_Ahead.margin_km``; default the feed's latest
    ``gs_ms``), or no position is known (the disagreeing or unknown case
    counts as loaded)."""
    if not _xplane_running():
        return lambda lat, lon: False
    import O4_World_Ahead as AHEAD
    import O4_World_Window as WINDOW

    from .position_feed import latest_position, latest_record
    if speed_ms is None:
        rec = latest_record() or {}
        speed_ms = float(rec.get("gs_ms") or 0.0)
    margin = max(S3_MARGIN_KM, AHEAD.margin_km(speed_ms))
    loads = _witness(scenery_dir)[0]
    here = (position or latest_position)()

    def held(lat: int, lon: int) -> bool:
        if (lat, lon) in loads or here is None:
            return True
        where = WINDOW.reach(here[0], here[1], lat, lon)
        return where["in_window"] or where["km_to_load"] < margin
    return held


def _regions_rows(scenery_dir: str, kinds: dict) -> list:
    import O4_Imagery_Regions as REGIONS
    import O4_Settings_Model as SM
    values = SM.read_global_raw()
    rows = []
    for code, label in REGIONS.REGIONS:
        name = REGIONS.setting_name(code)
        raw = str(values.get(name, "True")).strip().lower()
        rows.append({"id": code, "name": label,
                     "enabled": raw not in ("false", "0", "no", "off", ""),
                     "placeholders": sum(
                         1 for k, kind in kinds.items()
                         if kind == "placeholder"
                         and REGIONS.region_of(*k) == code),
                     "tiles": sum(1 for k, kind in kinds.items()
                                  if kind != "placeholder"
                                  and REGIONS.region_of(*k) == code)})
    return rows


def _staged_count() -> int:
    try:
        return sum(1 for name in os.listdir(staging_root())
                   if not name.startswith("."))
    except OSError:
        return 0


def managed(scenery_dir: str) -> bool:
    """Has ``world_install`` made the World pack in ``scenery_dir`` (its
    :data:`WP.MARKER`)?  Only then do builds publish into it -- never
    into a foreign folder (:func:`_foreign_target`), marker or not."""
    return bool(scenery_dir) and os.path.isfile(
        os.path.join(pack_dir(scenery_dir), WP.MARKER)) and not _foreign_target(scenery_dir)


def _status_fields(scenery_dir: str) -> dict:
    pack = pack_dir(scenery_dir) if scenery_dir else ""
    exists = managed(scenery_dir)
    installed = exists and _ini_has_row(scenery_dir)
    kinds = WP.world_tiles(pack) if exists else {}
    counts = {kind: 0 for kind in WP.KINDS}
    for kind in kinds.values():
        counts[kind] = counts.get(kind, 0) + 1
    counts["staged"] = _staged_count()
    running = _xplane_running()
    seen = None
    loaded = ()
    if running and installed:
        loads, packages = _witness(scenery_dir)
        if packages:
            seen = any(p.rstrip("/").endswith("/" + WP.PACK_NAME)
                       for p in packages)
        loaded = tuple(sorted(WP.tile_name(*k) for k, rec in loads.items()
                              if rec.tris > 0))
    foreign = _foreign_target(scenery_dir)
    missing = _converted_missing(scenery_dir, kinds) if not foreign else 0
    if foreign:
        state, reason = "off", _foreign_sentence(foreign)
    elif missing:
        from .world_migrate import pack_missing_sentence
        state = "idle" if installed else "off"
        reason = pack_missing_sentence(missing)
    elif not installed:
        state, reason = "off", "The World pack is not installed."
    elif seen is False:
        state, reason = "idle", "Restart X-Plane once: it has not read the World pack."
    else:
        state, reason = "idle", ""
    return {"state": state, "reason": reason, "installed": installed,
            "seen_by_xplane": seen, "restart_needed": seen is False,
            "tiles": counts, "loaded": loaded, "kinds": kinds}


def _converted_missing(scenery_dir: str, kinds: dict) -> int:
    """How many tiles Convert existing tiles moved the World pack lacks
    (``world_migrate.missing_from_pack``); 0 with no journal."""
    if not scenery_dir:
        return 0
    from .world_migrate import missing_from_pack, work_dir_for
    if not os.path.isdir(work_dir_for(scenery_dir)):
        return 0                            # never converted: no import cost
    try:
        return len(missing_from_pack(scenery_dir, kinds if kinds else None))
    except (OSError, ValueError):
        return 0


def world_status(scenery_dir: str = "", **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``world_status``: the ``WorldStatus`` fields and
    ``regions`` (``[{id, name, enabled, placeholders, tiles}]``)."""
    scenery_dir = scenery_dir_or_default(scenery_dir)
    fields = _status_fields(scenery_dir)
    kinds = fields.pop("kinds")
    return {**fields, "loaded": list(fields["loaded"]),
            "regions": _regions_rows(scenery_dir, kinds)}


def status_event(scenery_dir: str, **extra):
    """A ``WorldStatus`` event of the pack now (``extra`` sets or
    overrides fields such as ``last_swap``, or ``state`` and ``reason``
    while a migration runs)."""
    from .events import WorldStatus
    fields = _status_fields(scenery_dir_or_default(scenery_dir))
    fields.pop("kinds")
    if fields["state"] == "off" or fields["reason"]:
        # the pack's own state (not installed, not read) outranks the job's
        extra = {k: v for k, v in extra.items() if k not in ("state", "reason")}
    return WorldStatus(**{**fields, **extra})


def world_install(scenery_dir: str = "", **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``world_install``: create the World pack folder and
    file its ``scenery_packs.ini`` row as an ortho-group pack
    (``WP.ini_install``).  ``{"installed", "ini_added",
    "restart_needed"}``."""
    import O4_Scenery_Packs as SP
    scenery_dir = scenery_dir_or_default(scenery_dir)
    if not scenery_dir or not os.path.isdir(scenery_dir):
        raise ValueError("world_install: no Custom Scenery folder "
                         f"({scenery_dir!r}).")
    refuse_foreign(scenery_dir)
    os.makedirs(os.path.join(pack_dir(scenery_dir), "Earth nav data"),
                exist_ok=True)
    marker = os.path.join(pack_dir(scenery_dir), WP.MARKER)
    if not os.path.isfile(marker):
        with open(marker, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"version": 1, "installed_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, handle)
    lines, newline = SP.read_ini_lines(_ini_path(scenery_dir), missing_ok=True)
    added = WP.ini_install(lines)
    SP.write_ini_lines(_ini_path(scenery_dir), lines, newline)
    running = _xplane_running()
    write_log({"install": scenery_dir, "ini_added": added})
    return {"installed": True, "ini_added": added,
            "restart_needed": bool(running and added)}


#: The World pack marker's record that the per-tile packs were offered
#: (RULINGS 2026-11-11h (2)); "Not now" counts as offered.
OFFERED_KEY = "tiles_offered"


def _marker(scenery_dir: str) -> str:
    return os.path.join(pack_dir(scenery_dir), WP.MARKER)


def _offered(scenery_dir: str) -> bool:
    try:
        with open(_marker(scenery_dir), encoding="utf-8") as handle:
            return bool(json.load(handle).get(OFFERED_KEY))
    except (OSError, ValueError, AttributeError):
        return False


def _mark_offered(scenery_dir: str) -> None:
    try:
        with open(_marker(scenery_dir), encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        record = {}
    record = dict(record if isinstance(record, dict) else {}, **{OFFERED_KEY: True})
    with open(_marker(scenery_dir), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle)


def world_onboard(scenery_dir: str = "", **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``world_onboard`` (the apps' start, RULINGS
    2026-11-11a, 11h (2)): when no World pack folder exists in the Custom
    Scenery folder, :func:`world_install` makes it (a folder that exists
    is never touched); ``{"created", "offer", "restart_needed"}`` --
    ``offer``: the enabled ``zOrtho4XP_`` entries (on a mounted drive)
    that ``world_migrate`` could move, which the apps then ask about.  It
    is non-zero ONCE per managed pack: answering it is recorded in the
    marker (:data:`OFFERED_KEY`), so Library > Convert existing tiles is
    the way back.  A foreign World folder (:func:`_foreign_target`) is
    left alone: no offer, ``reason`` :data:`_FOREIGN_REASON`, ``target``
    and the apps' ``message``."""
    from .world_migrate import entries
    scenery_dir = scenery_dir_or_default(scenery_dir)
    out = {"created": False, "offer": 0, "restart_needed": False}
    if not scenery_dir or not os.path.isdir(scenery_dir):
        return out
    foreign = _foreign_target(scenery_dir)
    if foreign:
        return {**out, "reason": _FOREIGN_REASON, "target": foreign,
                "message": _foreign_sentence(foreign)}
    if not os.path.isdir(pack_dir(scenery_dir)):
        out["created"] = True
        out["restart_needed"] = world_install(scenery_dir)["restart_needed"]
    if not managed(scenery_dir) or _offered(scenery_dir):
        return out
    out["offer"] = sum(1 for entry in entries(scenery_dir)
                       if entry.enabled and entry.kind != "link-unmounted")
    if out["offer"]:
        _mark_offered(scenery_dir)
    return out


def _global_tiles(scenery_dir: str) -> "set | None":
    """Tiles X-Plane's own Global Scenery has a DSF for (land), or
    ``None`` when its folder is not beside ``scenery_dir``."""
    root = os.path.join(os.path.dirname(os.path.normpath(scenery_dir)),
                        _GLOBAL_PACK)
    if not os.path.isdir(os.path.join(root, "Earth nav data")):
        return None
    return {key for key, _path, _size in WP.pack_dsfs(root)}


def _regions_set(regions, scenery_dir: str = "") -> Dict[str, Any]:
    """The work of ``world_regions_set`` (see the module docstring), on
    the caller's thread.  ``{"regions", "written", "kept", "removed",
    "swapped_out"}``."""
    import O4_Imagery_Regions as REGIONS
    import O4_Settings_Model as SM
    scenery_dir = scenery_dir_or_default(scenery_dir)
    known = [code for code, _label in REGIONS.REGIONS]
    chosen = [str(r) for r in (regions or ())]
    unknown = sorted(set(chosen) - set(known))
    if unknown:
        raise ValueError(f"world_regions_set: unknown regions {unknown} "
                         f"(known: {known}).")
    SM.write_global({REGIONS.setting_name(code): code in chosen
                     for code in known})
    pack = pack_dir(scenery_dir)
    out = {"regions": [c for c in known if c in chosen], "written": 0,
           "kept": 0, "removed": 0, "swapped_out": 0}
    if not managed(scenery_dir):
        return out
    land = _global_tiles(scenery_dir)
    for code in known:
        tiles = [t for t in REGIONS.region_tiles(code)
                 if land is None or t in land]
        if code in chosen:
            done = WP.write_placeholders(pack, tiles)
            out["written"] += done["written"]
            out["kept"] += done["kept"]
        else:
            _give_back_region(pack, scenery_dir, set(tiles), out)
    write_log({"regions_set": out})
    return out


def _give_back_region(pack: str, scenery_dir: str, tiles: set,
                      out: dict) -> None:
    held = tile_loaded(scenery_dir)
    for key, path, size in list(WP.pack_dsfs(pack)):
        if key not in tiles:
            continue
        kind = "placeholder" if WP.is_placeholder(path, size) else WP.kind_of(path)
        if kind == "placeholder":
            with contextlib.suppress(OSError):
                os.remove(path)
                out["removed"] += 1
        elif kind == "drape":
            _swap_out(pack, *key, held)
            out["swapped_out"] += 1


def _swap_out(pack: str, lat: int, lon: int,
              held: Callable[[int, int], bool]) -> dict:
    """Placeholder over the tile; its folders removed unless X-Plane may
    hold them (spec §7.4)."""
    path = WP.swap_out(pack, lat, lon)
    removed = False
    if not held(lat, lon):
        tile = WP.tile_name(lat, lon)
        for sub in ("terrain", "textures"):
            shutil.rmtree(os.path.join(pack, sub, tile), ignore_errors=True)
        removed = True
    return {"dsf": path, "folders_removed": removed}


def start_world_regions_set(emit: Callable[[Any], None],
                            request: Any = None, regions=(),
                            scenery_dir: str = "", **_ignored) -> dict:
    """ENGINE COMMAND ``world_regions_set``: replies ``{"status":
    "started"}``; ``WorldReady`` (``request`` = this command's id) and a
    ``WorldStatus`` follow."""
    from .events import WorldReady

    def work() -> None:
        with _GUARD:
            try:
                result = _regions_set(regions, scenery_dir)
            except Exception as error:      # the sentence goes to the app
                emit(WorldReady(request=request, result=None,
                                error=str(error) or repr(error)))
                return
            emit(WorldReady(request=request, result=result))
            emit(status_event(scenery_dir))
    threading.Thread(target=work, daemon=True,
                     name="o4-world-regions").start()
    return {"status": "started"}


def world_tile_set(lat, lon, kind: str = "placeholder",
                   scenery_dir: str = "", **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``world_tile_set``: only ``kind="placeholder"``
    ("Give this tile back").  ``{"tile", "dsf", "folders_removed"}``."""
    if kind != "placeholder":
        raise ValueError("world_tile_set: only kind 'placeholder' is "
                         f"supported, not {kind!r}.")
    scenery_dir = scenery_dir_or_default(scenery_dir)
    pack = pack_dir(scenery_dir)
    if not managed(scenery_dir):
        raise ValueError("world_tile_set: the World pack is not installed.")
    lat, lon = int(lat), int(lon)
    done = _swap_out(pack, lat, lon, tile_loaded(scenery_dir))
    write_log({"swap_out": WP.tile_name(lat, lon), **done})
    return {"tile": WP.tile_name(lat, lon), **done}
