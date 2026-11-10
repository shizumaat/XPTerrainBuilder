"""The World pack's commands (flight manager / World spec §5.2, §7,
capability ``world_pack``): ONE Custom Scenery pack (``O4_World_Pack``)
holds every tile the app manages, placeholders where none is built.

* :func:`world_status` -- sync: the fields of ``WorldStatus`` plus the
  region rows (``regions``).
* :func:`world_install` -- the pack folder and its ``scenery_packs.ini``
  row; ``restart_needed`` when X-Plane runs (a new pack is read at start).
* :func:`start_world_regions_set` -- the on-demand regions (RULINGS
  2026-11-10e (3): the ``imagery_on_demand_<region>`` switches) set, then
  placeholders written for the tiles of the regions turned on that X-Plane's
  own scenery holds, and the regions turned off given back (their drape
  and light tiles swapped out, their placeholders removed; full tiles
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

__all__ = ["LOG_NAME", "pack_dir", "staging_root", "scenery_dir_or_default",
           "loaded_tiles", "tile_loaded", "world_status", "world_install",
           "start_world_regions_set", "world_regions_set", "world_tile_set",
           "status_event", "write_log"]

LOG_NAME = "world_pack.log"
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


def loaded_tiles(scenery_dir: str) -> dict:
    """The World pack's tiles X-Plane loaded this session (the witness),
    ``{}`` when X-Plane does not run."""
    if not _xplane_running():
        return {}
    return _witness(scenery_dir)[0]


def tile_loaded(scenery_dir: str,
                position: Optional[Callable[[], Optional[tuple]]] = None
                ) -> Callable[[int, int], bool]:
    """The predicate of rule S3 for one moment: may X-Plane hold tile
    ``(lat, lon)``?  Never, while X-Plane does not run.  While it runs:
    yes when the witness shows a load of it this session, or the aircraft
    (``position()`` -> ``(lat, lon)``, from the position feed) has it in
    the union of the plausible DSF windows, or no position is known (the
    disagreeing or unknown case counts as loaded)."""
    if not _xplane_running():
        return lambda lat, lon: False
    import O4_World_Window as WINDOW
    loads = _witness(scenery_dir)[0]
    here = position() if position else None

    def held(lat: int, lon: int) -> bool:
        if (lat, lon) in loads or here is None:
            return True
        return WINDOW.reach(here[0], here[1], lat, lon)["in_window"]
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


def _status_fields(scenery_dir: str) -> dict:
    pack = pack_dir(scenery_dir) if scenery_dir else ""
    exists = bool(pack) and os.path.isdir(pack)
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
    if not installed:
        state, reason = "off", "The World pack is not installed."
    elif seen is False:
        state, reason = "idle", "Restart X-Plane once: it has not read the World pack."
    else:
        state, reason = "idle", ""
    return {"state": state, "reason": reason, "installed": installed,
            "seen_by_xplane": seen, "restart_needed": seen is False,
            "tiles": counts, "loaded": loaded, "kinds": kinds}


def world_status(scenery_dir: str = "", **_ignored) -> Dict[str, Any]:
    """ENGINE COMMAND ``world_status``: the ``WorldStatus`` fields and
    ``regions`` (``[{id, name, enabled, placeholders, tiles}]``)."""
    scenery_dir = scenery_dir_or_default(scenery_dir)
    fields = _status_fields(scenery_dir)
    kinds = fields.pop("kinds")
    return {**fields, "loaded": list(fields["loaded"]),
            "regions": _regions_rows(scenery_dir, kinds)}


def status_event(scenery_dir: str, **extra):
    """A ``WorldStatus`` event of the pack now (``extra`` sets fields such
    as ``last_swap``)."""
    from .events import WorldStatus
    fields = _status_fields(scenery_dir_or_default(scenery_dir))
    fields.pop("kinds")
    return WorldStatus(**fields, **extra)


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
    os.makedirs(os.path.join(pack_dir(scenery_dir), "Earth nav data"),
                exist_ok=True)
    lines, newline = SP.read_ini_lines(_ini_path(scenery_dir), missing_ok=True)
    added = WP.ini_install(lines)
    SP.write_ini_lines(_ini_path(scenery_dir), lines, newline)
    running = _xplane_running()
    write_log({"install": scenery_dir, "ini_added": added})
    return {"installed": True, "ini_added": added,
            "restart_needed": bool(running and added)}


def _global_tiles(scenery_dir: str) -> "set | None":
    """Tiles X-Plane's own Global Scenery has a DSF for (land), or
    ``None`` when its folder is not beside ``scenery_dir``."""
    root = os.path.join(os.path.dirname(os.path.normpath(scenery_dir)),
                        _GLOBAL_PACK)
    if not os.path.isdir(os.path.join(root, "Earth nav data")):
        return None
    return {key for key, _path, _size in WP.pack_dsfs(root)}


def world_regions_set(regions, scenery_dir: str = "") -> Dict[str, Any]:
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
    if not os.path.isdir(pack):
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
        elif kind in ("drape", "light"):
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
                result = world_regions_set(regions, scenery_dir)
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
    if not os.path.isdir(pack):
        raise ValueError("world_tile_set: the World pack is not installed.")
    lat, lon = int(lat), int(lon)
    done = _swap_out(pack, lat, lon, tile_loaded(scenery_dir))
    write_log({"swap_out": WP.tile_name(lat, lon), **done})
    return {"tile": WP.tile_name(lat, lon), **done}
