"""THE LOT TAKES ITS PAD'S LEVEL (issue #359; owner RULINGS 2026-10-03c,
2026-10-04p (B) b2): geometry only, pre-solve.

A lot a declared wall terrace stands over (``airport/road_ramp
.wall_terraces``: a record's ``lots``, the record carrying at least one
lot→pad pair) is graded flat out from its building's pad.  Per vertex of
such a lot the map names the vertex of its pad it takes the level of: the
nearest ring vertex of the NEAREST pad, when the straight segment between
the two stays inside the lot — crossing no declared wall and no pad — so a
lot vertex behind a wall, or behind another building, is never bound to a
pad it does not see.

The record is ``PlanarMap.road_terrace['lot_level']``: ``{"lots": [face
id], "pairs": {lot vertex: pad vertex}}``.  Its rows are minted ONLY in
the follower pass after stage 2 (``pipeline/lot_follow``), where every
pad is a constant: in stage 2, the lot and the pad solved together, the
same coupling made a loop with no leader (MEASURED HECA: ``building8`` sank 100.37 -> 99.24 m)."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..law.tables import airside_stage_roles, role_side
from ..model.planar import PlanarMap

__all__ = ["lot_level"]

#: metres the lot is grown before the segment test: a segment along the
#: lot's own edge is inside it
_TOL_M = 0.05


def _lot_faces(walls: _t.Mapping[int, _t.Mapping]) -> list[int]:
    """The lot faces of every wall record carrying a lot→pad pair."""
    return sorted({int(f) for rec in walls.values() if rec.get("pairs")
                   for f in rec.get("lots") or ()})


def _polygon(pm: PlanarMap, face):
    from shapely.geometry import Polygon
    ring = [pm.vertices[v].xy for v in pm.ring_vertices(face.ring)]
    holes = [[pm.vertices[v].xy for v in pm.ring_vertices(h)]
             for h in getattr(face, "holes", ()) or ()]
    g = Polygon(ring, [h for h in holes if len(h) >= 3])
    return g if g.is_valid else g.buffer(0.0)


def lot_level(pm: PlanarMap, law: Law,
              walls: _t.Mapping[int, _t.Mapping]) -> dict[str, _t.Any]:
    """``{"lots", "pairs"}`` (module docstring); ``{}`` when no lot."""
    lots = _lot_faces(walls)
    if not lots:
        return {}
    pairs = _pairs(pm, law, walls, lots)
    return {"lots": lots, "pairs": pairs} if pairs else {}


def _pairs(pm: PlanarMap, law: Law, walls: _t.Mapping[int, _t.Mapping],
           lots: _t.Sequence[int]) -> dict[int, int]:
    from shapely.geometry import LineString, Point, Polygon
    from shapely.strtree import STRtree

    from .road_ramp import contact_roles
    stage1 = airside_stage_roles(law)
    pad_roles = frozenset(r for r in contact_roles(law)
                          if role_side(law, r) == "airside" and r not in stage1)
    pads = [f for f in pm.faces.values()
            if f.role in pad_roles and len(f.ring) >= 3]
    if not pads:
        return {}
    pad_g = [_polygon(pm, f) for f in pads]
    ptree = STRtree(pad_g)
    wall_g = [Polygon(rec["line"]) for rec in walls.values()
              if len(rec.get("line") or ()) >= 4]
    wall_g = [g if g.is_valid else g.buffer(0.0) for g in wall_g]
    wtree = STRtree(wall_g) if wall_g else None

    def crosses(seg, tree, geoms) -> bool:
        # through a wall's or a pad's interior: touching its outline is not
        return tree is not None and any(
            not seg.touches(geoms[int(j)])
            for j in tree.query(seg, predicate="intersects"))
    out: dict[int, int] = {}
    for fid in lots:
        face = pm.faces.get(fid)
        if face is None:
            continue
        inside = _polygon(pm, face).buffer(_TOL_M)
        for v in sorted(pm.ring_vertices(face.ring)) + sorted(
                v for h in getattr(face, "holes", ()) or () for v in pm.ring_vertices(h)):
            if v in out:
                continue
            p = Point(pm.vertices[v].xy)
            k = int(ptree.nearest(p))
            ring = pm.ring_vertices(pads[k].ring)
            if v in ring:
                continue                  # the pad's own vertex: it is the pad
            x, y = pm.vertices[v].xy
            q = min(ring, key=lambda u: ((pm.vertices[u].xy[0] - x) ** 2
                                         + (pm.vertices[u].xy[1] - y) ** 2, u))
            seg = LineString([pm.vertices[v].xy, pm.vertices[q].xy])
            if not seg.within(inside):
                continue
            if crosses(seg, ptree, pad_g) or crosses(seg, wtree, wall_g):
                continue
            out[int(v)] = int(q)
    return out
