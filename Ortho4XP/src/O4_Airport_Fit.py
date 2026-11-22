""""Fit custom airport buildings to the new ground", PER AIRPORT (#2182).

Owner 2026-11-19T14:15Z: the setting "has to be per airport, because the
user could want an auto-patch at some airports and a custom patch at
others on the same tile."  Each airport's own value lives in the tile's
build folder, ``<build dir>/airport_fit.json`` = ``{ICAO: bool}``, and is
read by the object stage for that airport only — another airport's value
never stands an airport's objects down.

THE MIGRATION: an airport with no value of its own takes the tile's
former setting ``modify_custom_airports`` (the tile cfg, else Settings'
global), so every airport of a tile keeps what the tile said until its
own switch is changed.  A per-build switch from the Build card
(``Tile.apply_build_overrides``) still wins for that one build, for every
airport.  Writers: the Build card's per-airport switch (engine command
``set_airport_fit``) and a custom patch new to the tile
(``O4_Custom_Patches.stand_down_new``, RULINGS 2026-11-18l, now per
airport).

Imported by the object stage (``auto_patch.object_stage``): keep it to
the standard library.
"""

from __future__ import annotations

import json
import os

__all__ = ["FIT_KEY", "RECORD", "read", "set_fit", "fits", "any_fits"]

#: The tile setting each airport's value falls back to (the migration).
FIT_KEY = "modify_custom_airports"
#: The per-airport record in the tile's build folder.
RECORD = "airport_fit.json"


def read(build_dir: str) -> dict:
    """``{ICAO: bool}`` of the airports with a value of their own."""
    try:
        with open(os.path.join(build_dir, RECORD), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).upper(): v for (k, v) in data.items() if isinstance(v, bool)}


def set_fit(build_dir: str, icao: str, fit: bool) -> dict:
    """Give *icao* its own value in the tile at *build_dir*; returns the
    record written."""
    record = read(build_dir)
    record[icao.upper()] = bool(fit)
    os.makedirs(build_dir, exist_ok=True)
    with open(os.path.join(build_dir, RECORD), "w", encoding="utf-8",
              newline="") as handle:
        json.dump(record, handle, sort_keys=True)
    return record


def _per_build(tile) -> bool:
    """Whether this build's Build-card switch landed on the tile."""
    return FIT_KEY in (getattr(tile, "__dict__", {})
                       .get("_build_override_saved") or {})


def _tile_value(tile) -> bool:
    return bool(getattr(tile, FIT_KEY, True))


def fits(tile, icao: str) -> bool:
    """Whether this build of *tile* fits *icao*'s buildings: the per-build
    switch, else the airport's own value, else the tile's setting."""
    if _per_build(tile):
        return _tile_value(tile)
    own = read(getattr(tile, "build_dir", "") or "").get(str(icao).upper())
    return _tile_value(tile) if own is None else own


def any_fits(tile) -> bool:
    """Whether this build may fit any airport of *tile* at all (the object
    stage stands down whole when not)."""
    if _per_build(tile) or _tile_value(tile):
        return _tile_value(tile)
    return any(read(getattr(tile, "build_dir", "") or "").values())
