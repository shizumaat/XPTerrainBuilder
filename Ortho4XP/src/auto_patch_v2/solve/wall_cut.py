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

:func:`wall_cut_edges` is the set of mesh edges the bending skips: an edge
with exactly one end on the LOWER side of a wall that retains its height
(the record's ``retains``; a 10-03c lot terrace at a thin wall is
unchanged) whose segment touches the wall's outline (the same test
``wall_release`` applies to a pair row)."""
from __future__ import annotations

import typing as _t

from ..model.planar import PlanarMap

__all__ = ["wall_cut_edges"]


def wall_cut_edges(planar: PlanarMap, tris: _t.Iterable[tuple[int, int, int]]
                   ) -> frozenset[tuple[int, int]]:
    """``(min, max)`` vertex pairs of the triangle edges across a declared
    wall terrace (module docstring); empty without one."""
    tris = list(tris)
    out_r = _riser_edges(planar, tris)
    walls = (getattr(planar, "road_terrace", None) or {}).get("wall") or {}
    if not walls:
        return out_r
    from shapely.geometry import LineString, Polygon
    from shapely.strtree import STRtree
    polys, low = [], set()
    for _k, r in sorted(walls.items()):
        if len(r.get("line") or ()) >= 4 and r.get("lower") and r.get("retains"):
            g = Polygon(r["line"])
            polys.append(g if g.is_valid else g.buffer(0.0))
            low.update(int(v) for v in r["lower"])
    if not polys:
        return out_r
    tree = STRtree(polys)
    out: set[tuple[int, int]] = set()
    for a, b, c in tris:
        for i, j in ((a, b), (b, c), (c, a)):
            if (i in low) == (j in low):
                continue
            key = (min(i, j), max(i, j))
            if key in out:
                continue
            seg = LineString([planar.vertices[i].xy, planar.vertices[j].xy])
            if len(tree.query(seg, predicate="intersects")):
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
