"""THE LOT PAGE ENDS AT THE WALL — a groundside lot is trimmed at a placed
wall standing along the kerb of a road or airside pavement (owner RULINGS
2026-10-04p (B), issue #359; spec §54).

Owner (HECA read of 1.0.376, building shapeID 1308): the lot is "graded
flat out from the building pad to the surrounding retaining wall objects".
RULINGS 2026-10-03c made the wall the STEP between the road at the airside
level (its top) and the lot at its building's level (its foot) — but the
lot PAGE ran on under the wall to the road's kerb, so road and lot shared
the wall-top kerb vertices and one vertex could not stand on both levels.
MEASURED (HECA capture at 28500ecf): lot ``dsf:objpav394`` (33,507 m²)
shares its kerb with ``route3``; ``metal_strip_2.obj`` comp 117 (3.10 m
tall, 262 m) stands 0.26 m inside that kerb, wholly on the lot.

THE RULE AS GEOMETRY, at this ONE derivation site (2026-08-30l corollary
(a): trim the region where it is derived, no per-consumer veto).  Per wall
piece (``airport/road_ramp.wall_pieces`` — the terrace's own reader) the
SHADOW is the piece plus the ground between it and the UPPER pavement
(road family, §20b stage-1 airside) within one lane width of it: the
outline is walked at the identity spacing and every step joined to its
nearest upper points.  A lot loses its shadow, widened by the zone band's
own groundside stand-off (cut-back + snap margin) so lot and kerb can no
longer node to one vertex; the freed
strip is nobody's pavement — the wall stands on it and the mesh carries
the step.  Past the wall's end and through a gate the lot still reaches
the road and ramps to it under its own cap.

No new number: the reach is ``[road_profile] lane_width_m`` (the reach of
``road_terrace``'s own walled test), the step ``[identity]
min_distinct_spacing_m``, the stand-off ``[adjacent_ground]
groundside_cutback_m`` + ``tables.snap_margin_m``, the remainder floor
the planar sliver floor (spacing x ``[terrace] sliver_area_factor``,
squared).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import MultiPoint, Polygon
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree

from ..airport.road_ramp import wall_pieces
from ..law import Law
from ..law.tables import (airside_stage_roles, family, is_structure_role,
                          is_value_role, role_side, sliver_area_factor,
                          snap_margin_m)
from ..model.airport import Airport

__all__ = ["wall_shadow", "trim_lots_at_walls"]


def _poly(ring, holes=()) -> Polygon:
    g = Polygon(ring, [h for h in holes if len(h) >= 3])
    return g if g.is_valid else g.buffer(0.0)


def wall_shadow(piece: Polygon, upper, reach: float, step: float):
    """One wall piece's SHADOW on the upper side (module docstring): the
    piece and the ground between it and ``upper`` (any geometry) where the
    two stand within ``reach``; empty when they nowhere do."""
    if piece.is_empty or upper is None or upper.is_empty or step <= 0.0:
        return Polygon()
    local = upper.intersection(piece.buffer(reach + step))
    if local.is_empty:
        return Polygon()
    ring = piece.exterior
    n = max(int(math.ceil(ring.length / step)), 4)
    feet: list[tuple[tuple[float, float], tuple[float, float]] | None] = []
    for i in range(n):
        p = ring.interpolate(i * ring.length / n)
        q = nearest_points(p, local)[1]
        feet.append(((p.x, p.y), (q.x, q.y)) if p.distance(q) <= reach else None)
    if not any(feet):
        return Polygon()
    parts = [piece]
    for a, b in zip(feet, feet[1:] + feet[:1]):
        if a is None or b is None:
            continue
        hull = MultiPoint([*a, *b]).convex_hull
        if hull.geom_type == "Polygon":
            parts.append(hull)
    return unary_union(parts)


def trim_lots_at_walls(airport: Airport, cells: list, law: Law, rules
                       ) -> tuple[list, dict[str, float]]:
    """Every groundside LOT cell (value role, not a road, not a structure)
    less the shadow of every wall piece along an upper pavement's kerb.
    Returns the cells (ids positional, like the pad set-back's) and the
    stats ``wall_trim_lots`` / ``wall_trim_walls`` / ``wall_trim_m2``."""
    stats = {"wall_trim_lots": 0, "wall_trim_walls": 0, "wall_trim_m2": 0.0}
    walls = wall_pieces(airport, rules.service)
    if not walls:
        return cells, stats
    roads = frozenset(family(law, "road_cross_section").roles)
    up_roles = roads | frozenset(airside_stage_roles(law))
    lot_idx = [i for i, c in enumerate(cells)
               if c.role not in roads and role_side(law, c.role) == "groundside"
               and is_value_role(law, c.role)
               and not is_structure_role(law, c.role)]
    up = [_poly(c.ring, c.holes) for c in cells if c.role in up_roles]
    if not lot_idx or not up:
        return cells, stats
    lots = {i: _poly(cells[i].ring, cells[i].holes) for i in lot_idx}
    ltree = STRtree([lots[i] for i in lot_idx])
    utree = STRtree(up)
    lane = float(law.tables.emit.road_profile.lane_width_m)
    step = float(law.tables.emit.identity.min_distinct_spacing_m)
    quantum = float(law.tables.emit.identity.input_quantum_m)
    # THE STAND-OFF IS THE ZONE BAND'S OWN (``planar/zones``: cut-back +
    # snap margin), measured from the SHADOW — which reaches the kerb.  The
    # margin alone is not enough where the wall stands ON the kerb: MEASURED
    # (HECA arm 1) nine lot vertices 0.35-0.65 m off ``route3`` noded back
    # onto its kerb and the lot foot stood +3.5 m, at the road's level
    standoff = float(law.tables.zones.adjacent_ground.groundside_cutback_m) \
        + snap_margin_m(law)
    knives: dict[int, list] = {}
    for w in walls:
        zone = w.poly.buffer(lane)
        hit = [lot_idx[int(k)] for k in ltree.query(zone, predicate="intersects")]
        near = [up[int(k)] for k in utree.query(zone, predicate="intersects")]
        if not hit or not near:
            continue
        shadow = wall_shadow(w.poly, unary_union(near), lane, step)
        if shadow.is_empty:
            continue
        # mitred and thinned to the input quantum: the walk leaves a point
        # every step along a straight wall, and a round join an arc at
        # every corner — none of which the lot's ring should inherit
        knife = shadow.buffer(standoff, join_style="mitre",
                              mitre_limit=2.0).simplify(quantum)
        used = False
        for i in hit:
            if lots[i].intersects(knife):
                knives.setdefault(i, []).append(knife)
                used = True
        stats["wall_trim_walls"] += int(used)
    if not knives:
        return cells, stats
    # what the wall leaves of a lot under the planar sliver floor is no lot
    # (MEASURED KCLT dry run: ``dsf:pol84`` left 12 m² and 2 m² chips, HECA
    # ``dsf:objpav397`` 7 m² of 70 — each would be a face of its own)
    floor = max((step * sliver_area_factor(law)) ** 2,
                float(rules.cells.min_area_m2))
    out: list = []
    for i, c in enumerate(cells):
        if i not in knives:
            out.append(c)
            continue
        left = lots[i].difference(unary_union(knives[i]))
        stats["wall_trim_lots"] += 1
        stats["wall_trim_m2"] += lots[i].area - left.area
        parts = [g for g in getattr(left, "geoms", [left])
                 if g.geom_type == "Polygon"
                 and g.area >= floor]
        for k, part in enumerate(sorted(parts, key=lambda g: -g.area)):
            out.append(_dc.replace(
                c, ref=c.ref if k == 0 else f"{c.ref}#w{k}",
                ring=tuple(part.exterior.coords)[:-1],
                holes=tuple(tuple(h.coords)[:-1] for h in part.interiors),
                evidence=dict(c.evidence, wall_trim=1.0)))
    stats["wall_trim_m2"] = round(stats["wall_trim_m2"], 1)
    return [_dc.replace(c, id=k) for k, c in enumerate(out)], stats
