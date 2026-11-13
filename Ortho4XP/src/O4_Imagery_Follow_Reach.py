"""Which index rows the follow job reads each tick: the squares the camera
can reach (#2037).

The index holds every on-demand tile the user has (215,200 rows in 567
tiles on 2026-11-13), and the follow job planned all of them every tick:
1.3 s of pure Python over that index, 0.2 s more for ``last_near_at``,
on the job's one thread.  While a World drape run shared the engine,
ticks stretched to 85-176 s, and each landed square waited that long to
be counted and its slot reused.

A square further from the camera than the planner can reach within its
horizon is never in a plan: groundspeed times the horizon plus the
coarsest crossing it plans (``CROSSING_S[1]``) and the turn margin, in
units of S.  :func:`by_tile` bounds each tile's square CENTRES (a box in
degrees, and its largest S) once per reread of the rows;
:func:`keys_within` keeps the rows of the tiles whose box is within such
a distance, by the same equirectangular metric as
``O4_Imagery_OnDemand_Index.distance_m`` (the box's nearest point: a
lower bound, so no square in reach is left out).

Pure: no I/O.
"""
from __future__ import annotations

import math

import O4_Imagery_Tier_Plan as PLAN

__all__ = ["by_tile", "keys_within", "near_reach", "plan_reach"]

_M_PER_DEG = 111_320.0


def by_tile(rows) -> dict:
    """``{tile: (lat_min, lat_max, lon_min, lon_max, largest S, [keys])}``
    of index ``rows`` (``{key: row}``, each with a centre)."""
    out: dict = {}
    for key, row in rows.items():
        lat, lon = float(row["centre_lat"]), float(row["centre_lon"])
        size = float(row.get("load_size_m") or 0.0)
        box = out.get(row.get("tile"))
        if box is None:
            out[row.get("tile")] = [lat, lat, lon, lon, size, [key]]
            continue
        box[0], box[1] = min(box[0], lat), max(box[1], lat)
        box[2], box[3] = min(box[2], lon), max(box[3], lon)
        box[4] = max(box[4], size)
        box[5].append(key)
    return {tile: tuple(box) for tile, box in out.items()}


def plan_reach(motion, horizon_s: float = PLAN.HORIZON_S):
    """``(metres, per S)`` the planner can reach: the camera's travel in
    ``horizon_s`` plus the coarsest crossing it plans and its margin."""
    return (max(0.0, motion.groundspeed_ms) * float(horizon_s),
            PLAN.CROSSING_S[1] + PLAN.LATERAL_MARGIN_S)


def near_reach():
    """``(metres, per S)`` of ``last_near_at``: a row's tier distance is
    at most ``CROSSING_S[0]`` S."""
    return 0.0, PLAN.CROSSING_S[0]


def _box_m(box, lat: float, lon: float) -> float:
    """Distance from ``(lat, lon)`` to the nearest point of ``box``."""
    lat_min, lat_max, lon_min, lon_max = box[:4]
    north = (min(max(lat, lat_min), lat_max) - lat) * _M_PER_DEG
    east = ((min(max(lon, lon_min), lon_max) - lon) * _M_PER_DEG
            * math.cos(math.radians(lat)))
    return math.hypot(east, north)


def keys_within(tiles, lat: float, lon: float, reach) -> list[str]:
    """The keys of ``tiles`` (:func:`by_tile`) whose box of centres lies
    within ``reach`` = ``(metres, per S)`` of ``(lat, lon)``, S the
    tile's largest."""
    metres, per_size = reach
    out: list[str] = []
    for box in tiles.values():
        if _box_m(box, lat, lon) <= metres + per_size * box[4]:
            out.extend(box[5])
    return out
