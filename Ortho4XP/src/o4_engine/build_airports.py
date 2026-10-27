"""The Build pane's Airports card (#818, protocol 1.17).

Before a build, both front ends show what airport grading and object
fitting will do for the selected tiles: the airports the build grades,
the ruleset each is graded under, about how long that adds, and the
custom airport packs whose 3-D objects it may fit to the new ground.
This module is the ONE reader behind that card; the Mac app asks for it
with the ``build_airports`` command (answered by ``BuildAirportsReady``),
the Qt window calls :func:`build_airports` in process.

Cheap and OFFLINE, like the boundary preflight: it reads each tile's own
config, the CIFP directory, the apt.dat the patch selector already
chooses and the Custom Scenery listing — never a query, never a
download.  The airport list is :func:`auto_patch.selection.
select_patch_airports`, the same function the build calls, so the card
and the build cannot disagree.  The ruleset is the law's own resolver
(owner 2026-08-02: FAA within the USA, ICAO everywhere else) and the
time is :func:`o4_engine.tile_time_model.airport_seconds_range` — a
range, never a single number.
"""

from __future__ import annotations

import os
import threading
import typing as _t

#: An object probe stops after this many directory entries per pack (the
#: Mac app's ``PackObjectProbe`` cap): payware airports run to ~10k
#: files, and a mis-tagged multi-gigabyte pack must not stall the card.
__all__ = ["OBJECT_SCAN_CAP", "build_airports", "start_build_airports"]

OBJECT_SCAN_CAP = 40000

_NAMES: dict = {}


def _airport_names() -> dict:
    """ICAO -> name from the Global Airports index cache, when built."""
    try:
        import O4_Airport_Index as AIRPORT_INDEX
        import O4_File_Names as FNAMES

        cache = FNAMES.airport_index_cache()
        stamp = os.path.getmtime(cache)
    except Exception:
        return {}
    if _NAMES.get("stamp") != stamp:
        try:
            names = {entry.code: entry.name
                     for entry in AIRPORT_INDEX.load_index(cache)}
        except Exception:
            names = {}
        _NAMES.clear()
        _NAMES.update(stamp=stamp, names=names)
    return _NAMES["names"]


def _ruleset_resolver() -> _t.Callable[[str], str]:
    """``icao -> "FAA" | "ICAO"``: the law's resolver, upper-cased."""
    from auto_patch_v2.law import resolve_ruleset
    from auto_patch_v2.law.tables import load_default

    resolution = load_default().tables.resolution
    return lambda icao: resolve_ruleset(resolution, icao).upper()


def tile_airports(lat: int, lon: int, custom_build_dir: str = "") -> list:
    """The airports a build of tile (lat, lon) grades, as card rows.

    Listed under the tile's own ``auto_patch`` mode, or under "All" when
    the tile grades nothing — the mode a per-build "on" lands
    (``Tile.apply_build_overrides``) — so the card can say what turning
    grading on would cost.  Manual patches and airports with no apt.dat
    are not graded and are not listed.
    """
    import O4_Config_Utils as CFG
    import O4_Settings_Model as SETTINGS
    import O4_Vector_Map as VMAP
    from auto_patch import selection as SELECTION

    tile = CFG.Tile(lat, lon, custom_build_dir)
    tile.read_from_config()
    cifp = SETTINGS.resolve_cifp_dir(CFG.cifp_data_path,
                                     CFG.custom_scenery_dir)
    if not cifp:
        return []
    mode = SELECTION.resolved_auto_patch_mode(tile)
    candidates = SELECTION.select_patch_airports(
        tile, cifp, "All" if mode == "None" else mode,
        manual_icaos=VMAP.manual_patch_icaos(tile))
    graded = sorted(SELECTION.patch_set(candidates))
    if not graded:
        return []
    from . import tile_time_model

    (low, high) = tile_time_model.airport_seconds_range(lat, lon)
    names = _airport_names()
    ruleset = _ruleset_resolver()
    return [{"icao": icao, "name": names.get(icao, ""),
             "ruleset": ruleset(icao), "tile": [lat, lon],
             "estimate_s": [round(low, 1), round(high, 1)]}
            for icao in graded]


def count_objects(content_root: str, cap: int = OBJECT_SCAN_CAP) -> int:
    """The ``.obj`` / ``.agp`` files a pack ships (its DSFs excluded)."""
    count = 0
    visited = 0
    for (_folder, dirs, files) in os.walk(content_root):
        dirs[:] = [d for d in dirs if d != "Earth nav data"
                   and not d.startswith(".")]
        for name in files:
            visited += 1
            if visited > cap:
                return count
            if name.lower().endswith((".obj", ".agp")):
                count += 1
    return count


def airport_packs(cells, scenery_dir: str | None = None) -> list:
    """The enabled custom airport packs with an airport in ``cells`` that
    ship their own 3-D objects — the packs object fitting may reseat."""
    import O4_Custom_Scenery as SCENERY

    if scenery_dir is None:
        import O4_Config_Utils as CFG

        scenery_dir = CFG.custom_scenery_dir
    wanted = {(int(c[0]), int(c[1])) for c in cells}
    rows = []
    for (name, path, content_root, enabled, airports) in (
            SCENERY.iter_airport_packs(scenery_dir or "")):
        if not enabled:
            continue
        icaos = sorted({a.icao for a in airports
                        if (int(a.lat // 1), int(a.lon // 1)) in wanted})
        if not icaos:
            continue
        objects = count_objects(content_root)
        if objects:
            rows.append({"name": name, "path": path,
                         "airports": icaos, "objects": objects})
    return rows


class Superseded(Exception):
    """A newer card was asked for before this one finished."""


def build_airports(cells, custom_build_dir: str = "",
                   scenery_dir: str | None = None,
                   live: _t.Callable[[], bool] = lambda: True) -> dict:
    """The whole card for ``cells``: airports, packs and the total range.

    Prints nothing (``UI.quiet_thread``): the card is asked on every
    selection change, while a build may be filling the console, and the
    selector it runs narrates for the build only."""
    import O4_UI_Utils as UI

    airports = []
    with UI.quiet_thread():
        for (lat, lon) in sorted({(int(c[0]), int(c[1])) for c in cells}):
            if not live():
                raise Superseded("superseded by a newer selection")
            airports.extend(tile_airports(lat, lon, custom_build_dir))
        if not live():
            raise Superseded("superseded by a newer selection")
    total = [round(sum(a["estimate_s"][0] for a in airports), 1),
             round(sum(a["estimate_s"][1] for a in airports), 1)]
    return {"airports": airports,
            "packs": airport_packs(cells, scenery_dir),
            "total_s": total}


#: The newest card asked for (``start_build_airports``).
_GENERATION = [0]
_GENERATION_LOCK = threading.Lock()


def start_build_airports(emit: _t.Callable[[_t.Any], None], tiles=(),
                         custom_build_dir: str = "",
                         request: _t.Any = None) -> dict:
    """The command: replies ``{"status": "started"}`` at once and reads on
    a worker thread (a handler runs on the transport's read loop);
    ``BuildAirportsReady`` with ``request`` = the command's id completes
    it.

    The card is asked on every selection change; a newer ask SUPERSEDES
    an older one still reading, which stops at its next tile and answers
    with an error (its asker has moved on) -- asks never pile up into
    threads that each read the whole install while a build runs."""
    from .events import BuildAirportsReady

    cells = [(int(t[0]), int(t[1])) for t in (tiles or ())]
    with _GENERATION_LOCK:
        _GENERATION[0] += 1
        generation = _GENERATION[0]

    def work() -> None:
        try:
            event = BuildAirportsReady(request=request, **build_airports(
                cells, custom_build_dir,
                live=lambda: _GENERATION[0] == generation))
        except Exception as error:      # the event carries it
            event = BuildAirportsReady(request=request, error=str(error))
        emit(event)

    threading.Thread(target=work, daemon=True,
                     name="o4-build-airports").start()
    return {"status": "started"}
