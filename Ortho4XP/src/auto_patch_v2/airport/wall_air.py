"""THE AIRSIDE PAIRS ACROSS A DECLARED PACK WALL (owner RULINGS 2026-10-28s
(2), Q250 a, issue #507): "across a declared pack wall with airside
pavement on both sides, the lower side is bounded to no more than the
wall's height below the upper side, in the geometry".

:func:`wall_air_pairs` is geometry only, published once per map by
``airport/road_ramp.with_road_ramp`` as ``PlanarMap.road_terrace
['wall_air']``: per wall piece (a walled tunnel MOUTH excepted — its outline
bounds the open cut as well), every pair of stage-1 pavement vertices
within ``emit.terrace.straddle_pair_m`` of each other whose segment touches
the piece grown by its own thickness (``2 x area / perimeter``) — the
census's own pairing (``check_grade_lib/families/wall_outline_step``), so
the law and its reading name the same pairs.  The floor rows are stage 1's
(``solve/wall_floor``): which end is the lower one is a solved answer.

``lower`` / ``upper`` of a ``road_terrace['wall']`` record carry only the
lot and road vertices a terrace grades (``wall_terraces``), never an apron
across the wall from another apron — MEASURED HECA ``metal_strip_2.obj``
comp 12: aprons ``dsf:objpav402`` / ``dsf:objpav1`` stood 4.19 m apart at
the bend of a 3.10 m wall, and no row named the pair."""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["wall_air_pairs"]


def _stage_one_vertices(pm: PlanarMap, law: Law) -> set[int]:
    from ..law.tables import airside_stage_roles
    roles = airside_stage_roles(law)
    out: set[int] = set()
    for f in pm.faces.values():
        if f.role in roles:
            for ring in (f.ring, *f.holes):
                out.update(pm.ring_vertices(ring))
    return out


def wall_air_pairs(pm: PlanarMap, law: Law, walls: _t.Sequence[_t.Any]
                   ) -> dict[int, dict[str, _t.Any]]:
    """Wall index (``walls``' order, as ``road_terrace['wall']``) ->
    ``{line, height_m, label, pairs: [(a, b, d)]}``; a wall with no pair is
    absent (module docstring)."""
    out: dict[int, dict[str, _t.Any]] = {}
    if not walls:
        return out
    air = sorted(_stage_one_vertices(pm, law))
    if not air:
        return out
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree
    pair_m = float(law.tables.emit.terrace.straddle_pair_m)
    tree = STRtree([Point(pm.vertices[v].xy) for v in air])
    for k, w in enumerate(walls):
        poly, h = w.poly, float(w.height_m)
        if w.mouth or h <= 0.0 or poly.is_empty or poly.length <= 0.0:
            continue
        grown = poly.buffer(2.0 * poly.area / poly.length)
        near = sorted(air[int(j)] for j in tree.query(poly.buffer(pair_m),
                                                      predicate="intersects"))
        pairs: list[tuple[int, int, float]] = []
        for i, a in enumerate(near):
            xa, ya = pm.vertices[a].xy
            for b in near[i + 1:]:
                xb, yb = pm.vertices[b].xy
                d = math.hypot(xb - xa, yb - ya)
                if d > pair_m or d <= 1e-6:
                    continue
                if LineString([(xa, ya), (xb, yb)]).intersects(grown):
                    pairs.append((a, b, round(d, 6)))
        if pairs:
            out[k] = {"line": [tuple(c) for c in poly.exterior.coords],
                      "height_m": h, "label": w.label, "pairs": pairs}
    return out
