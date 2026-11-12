"""Airport cores of an on-demand tile: the photo squares kept sharp
around every airport the tile build graded (#1992, local-imagery-cache
spec §6.1, owner design answer 2026-11-10).

A core is every square whose centre lies within :data:`CORE_RING_S`
(5.2 S, the 1024 px crossing, so the T2/T1 rings are in it) of a graded
airport's reference point; inside, the tier the core wants is the one a
camera standing at the airport would want (:func:`core_tier`: full within
1.65 S, 2048 within 2.8 S, 1024 within 5.2 S).  A texture finer than the
tile's own zoom level -- the airport cover and approach corridors the
build was asked for -- is a core at full resolution wherever it lies
(owner 2026-11-10T14:26Z: the airport area keeps its high-res imagery,
placeholders only outside).  Cores count against the
cap and are downgraded only after every other row
(``O4_Imagery_OnDemand_Index.lru_order``); the follow job fetches them
after the build.

The airports are those the tile's patches graded: one
``<ICAO>.graded.json`` per airport in the tile's patch folder, its
``frame.origin`` the airport's reference point (written by the v2
grader); and every airport of an ENABLED custom airport pack in the
user's Custom Scenery folder (``O4_Custom_Scenery.airport_points_by_tile``,
owner 2026-11-12T14:19Z: "keep already downloaded imagery just near any
custom airports") -- so a tile another tool built, which no grader of
ours read, keeps its imagery sharp around the airports the user
installed.  General: no airport is named here.

* :func:`airport_points` -- ``[(icao, lat, lon), ...]`` of a tile.
* :func:`custom_points` -- the custom airport packs' airports of a tile.
* :func:`base_zoom` -- the tile's own zoom level (its imagery record).
* :func:`core_names` -- the index rows of a tile that are in a core.
* :func:`core_tier` -- the tier (0-3, ``O4_Imagery_Tier_Plan``) a core
  square wants, or ``None`` outside every core.
"""
from __future__ import annotations

import json
import os

import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Tier_Plan as PLAN

__all__ = ["CORE_RING_S", "GRADED_SUFFIX", "airport_points", "base_zoom",
           "core_names", "core_tier"]

#: The core's radius in units of a square's S: the 1024 px crossing.
CORE_RING_S = PLAN.CROSSING_S[1]
#: The graded surface beside each airport's patch (``O4_Unpatched_
#: Airports.PATCH_FAMILY``).
GRADED_SUFFIX = ".graded.json"


def _tile_patch_dir(lat: int, lon: int) -> str:
    """The tile's patch folder, ``Patches/<10 deg>/<1 deg>`` (already
    the tile's own: ``O4_File_Names.patch_dir``)."""
    return FNAMES.patch_dir(lat, lon)


def custom_points(lat: int, lon: int, scenery_dir: "str | None" = None
                  ) -> "list[tuple[str, float, float]]":
    """``(icao, lat, lon)`` of every airport of an enabled custom airport
    pack in ``scenery_dir`` (default: the ``custom_scenery_dir`` setting)
    that lies on tile ``(lat, lon)``; ``[]`` when there is no folder."""
    if scenery_dir is None:
        try:
            import O4_Settings_Model as SM
            scenery_dir = SM.read_global_raw().get("custom_scenery_dir", "")
        except Exception:                   # no readable settings: none
            scenery_dir = ""
    import O4_Custom_Scenery as SCENERY
    try:
        found = SCENERY.airport_points_by_tile(scenery_dir or "")
    except OSError:
        return []
    return list(found.get((int(lat), int(lon)), ()))


def airport_points(lat: int, lon: int, patch_dir: "str | None" = None,
                   scenery_dir: "str | None" = None
                   ) -> "list[tuple[str, float, float]]":
    """``(icao, lat, lon)`` of every airport graded for tile ``(lat,
    lon)`` (its patch folder, or ``patch_dir``; an unreadable surface is
    skipped), then each custom airport pack's airport on it
    (:func:`custom_points`) that no graded surface already names."""
    points = _graded_points(lat, lon, patch_dir)
    graded = {icao for icao, _la, _lo in points}
    return points + [p for p in custom_points(lat, lon, scenery_dir)
                     if p[0] not in graded]


def _graded_points(lat: int, lon: int, patch_dir: "str | None"
                   ) -> "list[tuple[str, float, float]]":
    folder = patch_dir or _tile_patch_dir(lat, lon)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    points = []
    for name in names:
        if not name.endswith(GRADED_SUFFIX):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                origin = json.load(handle)["frame"]["origin"]
            points.append((name[:-len(GRADED_SUFFIX)], float(origin[0]),
                           float(origin[1])))
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            continue
    return points


def base_zoom(build_dir: str, lat: int, lon: int) -> "int | None":
    """The zoom level the tile was built at (``zoomlevel`` of its imagery
    record), ``None`` when the record does not say."""
    import O4_Tile_Info as TINFO
    try:
        value = TINFO.read_imagery_record(build_dir, int(lat), int(lon)).get(
            "zoomlevel")
        return int(value) if value else None
    except (OSError, TypeError, ValueError):
        return None


def core_tier(row: dict, points, base_zl: "int | None" = None) -> "int | None":
    """The finest tier a core wants for ``row``'s square: full for a
    texture finer than ``base_zl`` (a cover texture), else the tier whose
    crossing ``c_k * S`` contains the nearest airport of ``points``;
    ``None`` beyond :data:`CORE_RING_S`."""
    if base_zl is not None and int(row.get("zl") or 0) > int(base_zl):
        return len(PLAN.CROSSING_S) - 1
    size = float(row.get("load_size_m") or 0.0)
    if size <= 0 or not points:
        return None
    nearest = min(INDEX.distance_m(row, p[1], p[2]) for p in points)
    inside = [k for k in range(1, len(PLAN.CROSSING_S))
              if nearest <= PLAN.CROSSING_S[k] * size]
    return max(inside) if inside else None


def core_names(rows, points, base_zl: "int | None" = None) -> "set[str]":
    """The names of ``rows`` (index rows of one tile) inside a core."""
    return {row["name"] for row in rows
            if core_tier(row, points, base_zl) is not None}
