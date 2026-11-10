"""Airport cores of an on-demand tile: the photo squares kept sharp
around every airport the tile build graded (#1992, local-imagery-cache
spec §6.1, owner design answer 2026-11-10).

A core is every square whose centre lies within :data:`CORE_RING_S`
(5.2 S, the 1024 px crossing, so the T2/T1 rings are in it) of a graded
airport's reference point; inside, the tier the core wants is the one a
camera standing at the airport would want (:func:`core_tier`: full within
1.65 S, 2048 within 2.8 S, 1024 within 5.2 S).  Cores count against the
cap and are downgraded only after every other row
(``O4_Imagery_OnDemand_Index.lru_order``); the follow job fetches them
after the build.

The airports are those the tile's patches graded: one
``<ICAO>.graded.json`` per airport in the tile's patch folder, its
``frame.origin`` the airport's reference point (written by the v2
grader).  General: no airport is named here.

* :func:`airport_points` -- ``[(icao, lat, lon), ...]`` of a tile.
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

__all__ = ["CORE_RING_S", "GRADED_SUFFIX", "airport_points", "core_names",
           "core_tier"]

#: The core's radius in units of a square's S: the 1024 px crossing.
CORE_RING_S = PLAN.CROSSING_S[1]
#: The graded surface beside each airport's patch (``O4_Unpatched_
#: Airports.PATCH_FAMILY``).
GRADED_SUFFIX = ".graded.json"


def _tile_patch_dir(lat: int, lon: int) -> str:
    return os.path.join(FNAMES.patch_dir(lat, lon),
                        FNAMES.short_latlon(lat, lon))


def airport_points(lat: int, lon: int, patch_dir: "str | None" = None
                   ) -> "list[tuple[str, float, float]]":
    """``(icao, lat, lon)`` of every airport graded for tile ``(lat,
    lon)`` (its patch folder, or ``patch_dir``); an unreadable surface is
    skipped."""
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


def core_tier(row: dict, points) -> "int | None":
    """The finest tier a core wants for ``row``'s square: the tier whose
    crossing ``c_k * S`` contains the nearest airport of ``points``;
    ``None`` beyond :data:`CORE_RING_S`."""
    size = float(row.get("load_size_m") or 0.0)
    if size <= 0 or not points:
        return None
    nearest = min(INDEX.distance_m(row, p[1], p[2]) for p in points)
    inside = [k for k in range(1, len(PLAN.CROSSING_S))
              if nearest <= PLAN.CROSSING_S[k] * size]
    return max(inside) if inside else None


def core_names(rows, points) -> "set[str]":
    """The names of ``rows`` (index rows of one tile) inside a core."""
    return {row["name"] for row in rows if core_tier(row, points) is not None}
