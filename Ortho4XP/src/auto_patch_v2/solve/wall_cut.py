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
``wall_release`` applies to a pair row).

THE BAND'S RISER beside a road inside a safety-area band (owner RULINGS
2026-10-19a / 19i / 19k, #951; ``planar/band_riser``) is the same cut, with
no pack object: an edge from a road ribbon's vertex to a band
(``graded_strip``) vertex that crosses a riser face is skipped, so the
bending neither lifts the road toward the band nor drags the band down to
the road — the riser carries the step (:func:`riser_cut_edges`)."""
from __future__ import annotations

import typing as _t

from ..model.planar import PlanarMap

__all__ = ["wall_cut_edges", "riser_cut_edges"]


def wall_cut_edges(planar: PlanarMap, tris: _t.Iterable[tuple[int, int, int]],
                   law=None) -> frozenset[tuple[int, int]]:
    """``(min, max)`` vertex pairs of the triangle edges across a declared
    wall terrace (module docstring); empty without one."""
    tris = list(tris)
    riser = riser_cut_edges(planar, tris, law)
    walls = (getattr(planar, "road_terrace", None) or {}).get("wall") or {}
    if not walls:
        return riser
    from shapely.geometry import LineString, Polygon
    from shapely.strtree import STRtree
    polys, low = [], set()
    for _k, r in sorted(walls.items()):
        if len(r.get("line") or ()) >= 4 and r.get("lower") and r.get("retains"):
            g = Polygon(r["line"])
            polys.append(g if g.is_valid else g.buffer(0.0))
            low.update(int(v) for v in r["lower"])
    if not polys:
        return riser
    tree = STRtree(polys)
    out: set[tuple[int, int]] = set(riser)
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
    return frozenset(out)


def riser_cut_edges(planar: PlanarMap, tris: _t.Iterable[tuple[int, int, int]],
                    law=None) -> frozenset[tuple[int, int]]:
    """``(min, max)`` pairs of the triangle edges from a road ribbon vertex
    to a band vertex across a band riser face (module docstring); empty
    without a riser."""
    from ..model.band_riser import band_risers
    from ..model.planar import is_osm_ribbon_ref
    near = 0.0
    if law is not None:
        from ..law.tables import riser_kerb_near_m
        near = riser_kerb_near_m(law)
    risers = band_risers(planar, near)
    if not risers:
        return frozenset()
    from shapely.geometry import LineString, Polygon
    from shapely.strtree import STRtree
    rib: set[int] = set()
    band: set[int] = set()
    for f in planar.faces.values():
        tgt = rib if is_osm_ribbon_ref(f.ref) else (
            band if f.role == "graded_strip" else None)
        if tgt is not None:
            for cyc in (f.ring, *f.holes):
                tgt.update(planar.ring_vertices(cyc))
    for _fid, lo, _up in risers:
        rib |= lo              # a riser vertex the emit welds onto a ribbon
    band -= rib
    polys = []
    for fid, _lo, _up in risers:
        f = planar.faces[fid]
        ring = [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]
        if len(ring) >= 3:
            g = Polygon(ring)
            polys.append(g if g.is_valid else g.buffer(0.0))
    tree = STRtree(polys)
    out: set[tuple[int, int]] = set()
    for a, b, c in tris:
        for i, j in ((a, b), (b, c), (c, a)):
            if not ((i in rib and j in band) or (j in rib and i in band)):
                continue
            key = (min(i, j), max(i, j))
            if key in out:
                continue
            seg = LineString([planar.vertices[i].xy, planar.vertices[j].xy])
            if len(tree.query(seg, predicate="intersects")):
                out.add(key)
    return frozenset(out)
