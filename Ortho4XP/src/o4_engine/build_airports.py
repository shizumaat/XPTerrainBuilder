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

import O4_Custom_Patches as CUSTOM_PATCHES

#: An object probe stops after this many directory entries per pack (the
#: Mac app's ``PackObjectProbe`` cap): payware airports run to ~10k
#: files, and a mis-tagged multi-gigabyte pack must not stall the card.
__all__ = ["OBJECT_SCAN_CAP", "build_airports", "start_build_airports",
           "set_airport_fit"]

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


def airport_packs(cells, scenery_dir: str | None = None,
                  homes: dict | None = None) -> list:
    """The enabled custom airport packs with an airport in ``cells`` that
    ship their own 3-D objects — the packs object fitting may reseat.
    ``homes``, when given, receives ``{ICAO: (lat, lon)}``: the tile each
    listed airport lies in (its per-airport Fit switch's tile, #2182)."""
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
        here = {a.icao: (int(a.lat // 1), int(a.lon // 1)) for a in airports
                if (int(a.lat // 1), int(a.lon // 1)) in wanted}
        icaos = sorted(here)
        if not icaos:
            continue
        objects = count_objects(content_root)
        if objects:
            if homes is not None:
                homes.update(here)
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
    homes: dict = {}
    packs = airport_packs(cells, scenery_dir, homes=homes)
    (custom, fit) = _custom_patch_fit(cells, custom_build_dir)
    rows = _fit_airports(homes, custom_build_dir)
    if rows:
        fit = any(row["fit"] for row in rows)
    return {"airports": airports,
            "packs": packs,
            "total_s": total,
            "custom_patches": custom, "fit_buildings": fit,
            "fit_confirm": CUSTOM_PATCHES.fit_confirm_text(custom),
            "fit_airports": rows,
            "custom_patch_use": [
                row for (lat, lon) in sorted({(int(c[0]), int(c[1]))
                                              for c in cells})
                for row in CUSTOM_PATCHES.airport_uses(lat, lon)]}


def _fit_airports(homes: dict, custom_build_dir: str = "") -> list:
    """The card's per-airport "Fit custom airport buildings" switches
    (#2182, owner 2026-11-19T14:15Z): one row per airport whose pack the
    build may fit, ``{"icao", "tile": [lat, lon], "fit", "custom_patch",
    "confirm"}`` — ``fit`` what its next build does (its own value, else
    the tile's; off while its custom patch is new), ``confirm`` the
    question asked before it turns on ("" without a custom patch)."""
    import O4_Config_Utils as CFG

    rows = []
    by_tile: dict = {}
    for (icao, cell) in homes.items():
        by_tile.setdefault(cell, []).append(icao)
    for ((lat, lon), icaos) in sorted(by_tile.items()):
        tile = CFG.Tile(lat, lon, custom_build_dir)
        tile.read_from_config()
        custom = set(CUSTOM_PATCHES.unmodified_airports(lat, lon))
        for (icao, fit) in CUSTOM_PATCHES.airport_fits(tile, icaos).items():
            rows.append({
                "icao": icao, "tile": [lat, lon], "fit": fit,
                "custom_patch": icao in custom,
                "confirm": CUSTOM_PATCHES.fit_confirm_text(
                    [icao] if icao in custom else [])})
    return rows


def set_airport_fit(tile: str, icao: str, fit: bool,
                    custom_build_dir: str = "") -> dict:
    """ENGINE COMMAND ``set_airport_fit`` (#2182, capability
    ``airport_fit``): *icao*'s own "Fit custom airport buildings" value in
    tile *tile* (``"+39-107"``), kept for every later build of the tile
    (``O4_Airport_Fit``).  The app asks ``confirm`` first when it turns on
    an airport with a custom patch (RULINGS 2026-11-18l)."""
    import O4_Airport_Fit as AIRPORT_FIT
    import O4_File_Names as FNAMES

    parsed = FNAMES.parse_tile_key(str(tile))
    if parsed is None or not str(icao).strip():
        raise ValueError("set_airport_fit needs a tile like +39-107 and an "
                         "ICAO, not %r / %r" % (tile, icao))
    (lat, lon) = parsed
    AIRPORT_FIT.set_fit(FNAMES.build_dir(lat, lon, custom_build_dir),
                        str(icao).strip(), bool(fit))
    return {"tile": FNAMES.short_latlon(lat, lon),
            "icao": str(icao).strip().upper(), "fit": bool(fit)}


def _custom_patch_fit(cells, custom_build_dir: str = "") -> tuple:
    """``(ICAOs, fit)`` for the card (owner RULINGS 2026-11-18l, #2172):
    the airports a custom patch covers in ``cells`` — the switch asks
    before it turns on for them — and whether the next build fits (off on
    any tile a custom patch is new to, or whose own setting is off)."""
    import O4_Config_Utils as CFG

    (custom, fit) = (set(), True)
    for (lat, lon) in sorted({(int(c[0]), int(c[1])) for c in cells}):
        tile = CFG.Tile(lat, lon, custom_build_dir)
        tile.read_from_config()
        (icaos, tile_fit) = CUSTOM_PATCHES.fit_state(tile)
        custom.update(icaos)
        fit = fit and tile_fit
    return (sorted(custom), fit)


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
