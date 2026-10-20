"""THE BENDING DOES NOT REACH ACROSS A DECLARED WALL (owner RULINGS
2026-10-15a (2), #715: "Yes, the wall is the step").

A declared wall terrace (``PlanarMap.road_terrace['wall']``, derived once
by ``airport/road_ramp.wall_terraces``) is a step the pack's wall object
stands on: the airside above at its level, the road and the lot below at
the lower ground.  ``constraints/road_ramp.wall_release`` withdraws the
pair rows across the wall's line; the design's thin-plate bending
(``solve/rows._cotangent_laplacian``) is the other coupling across it —
MEASURED (synthetic twin ``test_wall_step715``): with every pair row
released, a road at the foot of an 8 m wall stood 3.5 m over its ground,
carried up by the bending stencils of the strip faces spanning the wall.

:func:`wall_cut_edges` is the set of mesh edges the bending skips, at a
wall that retains its height (the record's ``retains``; a 10-03c lot
terrace at a thin wall is unchanged): an edge whose SEGMENT touches the
wall's outline (the test ``wall_release`` applies to a pair row) and
either has exactly one end in the record's ``lower`` set, or has its two
ends on OPPOSITE SIDES of the wall (issue #767).  A vertex's side is its
own (``lower`` / ``upper``), else that of the nearest ``lower`` or
``upper`` vertex it sees without crossing the wall: ``lower`` holds only
the vertices nearest the wall (a road's near kerb), so an edge from the
upper strip to the road's FAR kerb crossed the wall with neither end in
it.  MEASURED (``test_wall_step715``, main 2026-10-16): 11.51 of 25.53
of the stage-2 bending weight on the wall's edges stayed uncut, and
cutting it moved the road 0.858 -> 0.580 m from its 92 m ground."""
from __future__ import annotations

import math
import typing as _t

from ..model.planar import PlanarMap

__all__ = ["wall_cut_edges"]

class _Wall(_t.NamedTuple):
    poly: _t.Any
    side: dict[int, str]          # ``lower`` / ``upper`` vertex -> its side


def _walls(planar: PlanarMap) -> list[_Wall]:
    from shapely.geometry import Polygon
    out = []
    walls = (getattr(planar, "road_terrace", None) or {}).get("wall") or {}
    for _k, r in sorted(walls.items()):
        if len(r.get("line") or ()) >= 4 and r.get("lower") and r.get("retains"):
            g = Polygon(r["line"])
            side = {int(v): "upper" for v in r.get("upper") or ()}
            side.update({int(v): "lower" for v in r["lower"]})
            out.append(_Wall(g if g.is_valid else g.buffer(0.0), side))
    return out


def _side_of(planar: PlanarMap, w: _Wall, v: int,
             memo: dict[tuple[int, int], "str | None"], k: int) -> "str | None":
    """``v``'s side of wall ``k``: its own, else the nearest labelled
    vertex's that it sees without crossing the wall; ``None`` when it
    sees none (a vertex inside the wall)."""
    if v in w.side:
        return w.side[v]
    got = memo.get((k, v), "?")
    if got != "?":
        return got
    from shapely.geometry import LineString
    x, y = planar.vertices[v].xy
    found = None
    for _d, q in sorted((math.hypot(planar.vertices[q].xy[0] - x,
                                    planar.vertices[q].xy[1] - y), q) for q in w.side):
        if not LineString([(x, y), planar.vertices[q].xy]).intersects(w.poly):
            found = w.side[q]
            break
    memo[(k, v)] = found
    return found


def wall_cut_edges(planar: PlanarMap, tris: _t.Iterable[tuple[int, int, int]]
                   ) -> frozenset[tuple[int, int]]:
    """``(min, max)`` vertex pairs of the triangle edges across a declared
    wall terrace (module docstring); empty without one."""
    tris = list(tris)
    out_r = _riser_edges(planar, tris)
    walls = _walls(planar)
    if not walls:
        return out_r
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    tree = STRtree([w.poly for w in walls])
    low = {v for w in walls for v, s in w.side.items() if s == "lower"}
    memo: dict[tuple[int, int], "str | None"] = {}
    seen: set[tuple[int, int]] = set()
    out: set[tuple[int, int]] = set()
    for a, b, c in tris:
        for i, j in ((a, b), (b, c), (c, a)):
            key = (min(i, j), max(i, j))
            if key in seen:
                continue
            seen.add(key)
            seg = LineString([planar.vertices[i].xy, planar.vertices[j].xy])
            hit = tree.query(seg, predicate="intersects")
            if not len(hit):
                continue
            if (i in low) != (j in low) or any(
                    {_side_of(planar, walls[k], i, memo, k),
                     _side_of(planar, walls[k], j, memo, k)} == {"lower", "upper"}
                    for k in map(int, hit)):
                out.add(key)
    return frozenset(out) | out_r


def _riser_edges(planar: PlanarMap, tris) -> frozenset[tuple[int, int]]:
    """THE RISER OF A LOWER LEVEL (owner RULINGS 2026-10-19ai,
    ``planar/low_level``): the object's own storey between a held block and
    its lower level ``<block>/p1``, across the strip ``<block>/p1#strip`` —
    a declared step like a wall's, so the bending skips every triangle edge
    from a lower-level vertex to a strip vertex off that level.  MEASURED
    KATL: bent across the 1 m strip, the 13 m riser held the lower level
    2 m over its own ground."""
    from ..model.planar import plane_origin_ref, platform_ref_of
    low: set[int] = set()
    strip: set[int] = set()
    for f in planar.faces.values():
        r = platform_ref_of(f.ref)
        if plane_origin_ref(r) == r:
            continue
        vs = {v for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)}
        (strip if str(f.ref) != r else low).update(vs)
    if not low or not strip:
        return frozenset()
    out: set[tuple[int, int]] = set()
    for a, b, c in tris:
        for i, j in ((a, b), (b, c), (c, a)):
            if (i in low) != (j in low) and (i in strip and j in strip):
                out.add((min(i, j), max(i, j)))
    return frozenset(out)
