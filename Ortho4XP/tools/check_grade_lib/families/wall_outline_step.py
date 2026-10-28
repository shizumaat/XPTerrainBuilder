"""THE STEP ACROSS A DECLARED PACK WALL, READ ALONG ITS WHOLE OUTLINE — a
reading of the ``terrace_actual_step`` family (owner RULINGS 2026-10-28s
(2), Q250 a, issue #507: across a pack wall the step is at most the wall).

``check_grade._check_terrace_actual_step``'s straddle reading sides a
vertex by its nearest joint segment, and a wall terrace's joint is the
wall's closed OUTLINE: both faces of a thin wall are "outside" it, so a
pair standing on the two faces never straddles it, and a pack apron's edge
drawn AT the wall's face is on neither.  MEASURED HECA
``metal_strip_2.obj`` comp 12 (main 43ce4c5c1): 4.18 m over 4.25 m across
its east bend against a 3.10 m wall, and 0 ``terrace_actual_step`` rows
within 80 m.

This reading takes every pair of emitted pavement vertices within the
pair window of each other whose segment touches the outline grown by the
wall's own thickness (``2 x area / perimeter``), and prices it as the
straddle reading does: ``|dz| <= step + cap x d + quant``.  One row per
vertex (its worst partner), each pair once.  A wall's declared step is
the caller's (``check_grade._declared_joint_step``: the wall's height).
"""
from __future__ import annotations

import math
from typing import List, Sequence, Set, Tuple

from check_grade_lib.rows import Violation, Way

Vert = Tuple[float, float, float, Way]


def wall_outline_rows(walls_m: Sequence[Tuple[list, float]],
                      verts: Sequence[Vert], pair_m: float, max_grade: float,
                      quant: float,
                      seen: Set[Tuple[Tuple[float, float], Tuple[float, float]]]
                      ) -> List[Violation]:
    """The rows of every wall in ``walls_m`` (``(outline points, step)``,
    the outline closed); ``seen`` holds the pairs another reading already
    reported (rounded plan points) and is extended."""
    from shapely.geometry import LineString, Point, Polygon
    from shapely.strtree import STRtree
    out: List[Violation] = []
    if not walls_m or not verts:
        return out
    tree = STRtree([Point(x, y) for x, y, _z, _w in verts])
    for pts, step in walls_m:
        if len(pts) < 4:
            continue
        poly = Polygon(pts)
        poly = poly if poly.is_valid else poly.buffer(0.0)
        if poly.is_empty or poly.length <= 0.0:
            continue
        grown = poly.buffer(2.0 * poly.area / poly.length)
        near = sorted(int(j) for j in tree.query(poly.buffer(pair_m),
                                                 predicate="intersects"))
        worst = {}
        for i, a in enumerate(near):
            x1, y1, z1, _w1 = verts[a]
            for b in near[i + 1:]:
                x2, y2, z2, _w2 = verts[b]
                d = math.hypot(x2 - x1, y2 - y1)
                if d > pair_m or d <= 1e-6:
                    continue
                excess = abs(z1 - z2) - (step + max_grade * d + quant)
                if excess <= 0.0:
                    continue
                if not LineString([(x1, y1), (x2, y2)]).intersects(grown):
                    continue
                for v in (a, b):
                    if v not in worst or excess > worst[v][0]:
                        worst[v] = (excess, a, b, d)
        for _v, (_e, a, b, d) in sorted(worst.items()):
            key = pair_key(verts[a], verts[b])
            if key in seen:
                continue
            seen.add(key)
            out.append(_row(verts[a], verts[b], d))
    return out


def pair_key(a: Vert, b: Vert) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """The unordered plan key of a pair (the dedupe the readings share)."""
    p, q = (round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))
    return (p, q) if p <= q else (q, p)


def _row(a: Vert, b: Vert, d: float) -> Violation:
    (x1, y1, z1, w1), (x2, y2, z2, w2) = a, b
    return Violation(grade_pct=abs(z1 - z2) / d * 100.0, excess_pct=100.0,
                     distance_m=d, de_m=abs(z1 - z2), way_a=w1, way_b=w2,
                     pt_a=(x1, y1), pt_b=(x2, y2), elev_a=z1, elev_b=z2)

