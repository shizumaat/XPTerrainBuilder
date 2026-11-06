"""THE ROAD'S OWN GROUND BESIDE A HARD DECK — the floor under a hard deck
never stands above the ground the road it carries over runs at beside it
(#1902 / #1903, owner sim read on 1.0.470, 2026-11-06T00:02Z: "there's a
huge cliff in the road instead of a smooth transition to the natural
ground").

A hard deck whose frame states no road level (``deck_bridge._road_floor``)
takes its floor from the ladder: ``[tunnel] clearance_m`` (or level B)
under its top.  Where the mapped road already runs LOWER than that beside
the deck — the survey carries the real road in its cutting — that floor is
a FILL: the cut's ramp climbed from it to the cover it assumed and the
road beyond stood metres under the ramp's end, a vertical wall across the
carriageway.  MEASURED KIAH 1.0.470 (drawn tile mesh along the trunk under
``KIAH_Bridge2`` obj24615): the road at 20.4 m beside the deck, the floor
at 22.62 (5.0 m under the deck top 27.62), the ramp's end at 24.14 — a
3.79 m cliff; obj24614 2.18 m; obj24549/24550 0.92 m.

The reading: along every mapped road or rail line (no bridge) that passes
under the deck's ring, the ground (the DEM) from :data:`NEAR_M` to
:data:`FAR_M` beyond the ring on each side, off every hard deck (the
survey reads a deck as ground, RULINGS 2026-11-03b Q344 a); each side's
MEDIAN is that side's road ground and the lowest side's is the deck's.
The floor sinks to it (the ladder's floor "may sink, never rise closer",
``DeckBridge.floor_min_m``) — the road keeps its own ground under the deck
and its run-out on the higher side climbs at the road ramp law.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics

from shapely.geometry import LineString, Point
from shapely.ops import linemerge, unary_union

__all__ = ["road_ground_beside", "sink_to_road_ground"]

#: the band beyond the deck's ring the road's ground is read in (m): past
#: the abutment's own toe, short of the next feature along the road
NEAR_M, FAR_M = 3.0, 30.0
#: the sampling step along the road (m) and the least samples a side needs
STEP_M, MIN_SAMPLES = 1.0, 5


def _lines_under(airport, ring) -> list:
    """The mapped road and rail lines (merged through their joints, no
    bridge way) that cross ``ring``."""
    from .structure_approach import is_bridge
    near = ring.buffer(FAR_M + NEAR_M)
    ways = [LineString(w.points) for w in getattr(airport, "osm_ways", ()) or ()
            if len(w.points) >= 2 and not is_bridge(w)
            and any((w.tags or {}).get(k) for k in ("highway", "railway"))]
    ways = [ln for ln in ways if ln.intersects(near)]
    if not ways:
        return []
    u = unary_union(ways)
    m = linemerge(u) if u.geom_type == "MultiLineString" else u
    return [g for g in getattr(m, "geoms", [m])
            if g.geom_type == "LineString" and g.intersection(ring).length > 1.0]


def road_ground_beside(airport, ring, off_decks=None) -> "float | None":
    """The lowest side's median ground along the roads under ``ring``
    (module doc), off ``off_decks`` (every hard deck's plan); ``None``
    where no road side carries :data:`MIN_SAMPLES`."""
    dem = getattr(airport, "dem", None)
    if dem is None:
        return None
    sides: list[float] = []
    for ln in _lines_under(airport, ring):
        inside = ln.intersection(ring)
        s_in = [ln.project(Point(c)) for g in getattr(inside, "geoms", [inside])
                if g.geom_type == "LineString" for c in (g.coords[0], g.coords[-1])]
        if not s_in:
            continue
        for s0, sgn in ((min(s_in), -1.0), (max(s_in), 1.0)):
            zs = []
            for k in range(int(round((FAR_M - NEAR_M) / STEP_M)) + 1):
                s = s0 + sgn * (NEAR_M + k * STEP_M)
                if s < 0.0 or s > ln.length:
                    break
                p = ln.interpolate(s)
                if ring.contains(p) or (off_decks is not None and off_decks.contains(p)):
                    continue
                z = float(dem.z(p.x, p.y))
                if math.isfinite(z):
                    zs.append(z)
            if len(zs) >= MIN_SAMPLES:
                sides.append(statistics.median(zs))
    return min(sides) if sides else None


def sink_to_road_ground(db, airport, ring, off_decks, notes: list, tol: float):
    """``db`` with its floor sunk to the road's ground beside it where that
    stands more than ``tol`` under the ladder's floor (module doc); ``db``
    unchanged otherwise."""
    g = road_ground_beside(airport, ring, off_decks)
    if g is None:
        return db
    top = 0.5 * (db.top_a + db.top_b)
    depth = float(db.deck_z) - g
    if depth <= db.depth_m + tol:
        return db
    notes.append(f"{db.object_id} {db.resource.rsplit('/', 1)[-1]}: the road beside it runs "
                 f"at {g:.2f}, {depth - db.depth_m:.2f} m under the ladder's floor — the floor "
                 f"sinks to it ({depth:.2f} m under the deck; #1902, never a fill under a deck)")
    return _dc.replace(db, bottom_y=top - depth)
