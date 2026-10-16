"""Twin of ``geom/triangulate.face_triangles`` (issue #752): the triangles
of a face cover it EXACTLY — their area sum is the polygon's area and
their union leaves nothing out and adds nothing — and name only the
face's own vertex ids.

The routine was an unconstrained Delaunay kept by triangle centroid; on a
concave face it dropped area and could cover ground outside the ring.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from auto_patch_v2.geom import face_triangles

#: relative area tolerance of an exact cover (float round-off only)
_REL = 1e-9


def _check_cover(xy, ring, holes=()):
    tris = face_triangles(xy, ring, holes)
    ids = set(ring) | {v for h in holes for v in h}
    assert tris, "a face with area triangulates"
    assert all(set(t) <= ids and len(set(t)) == 3 for t in tris), \
        "only the face's own vertex ids, three distinct per triangle"
    poly = Polygon([xy[v] for v in ring], [[xy[v] for v in h] for h in holes])
    if not poly.is_valid:
        poly = Polygon([xy[v] for v in ring]).difference(
            unary_union([Polygon([xy[v] for v in h]) for h in holes]))
    parts = [Polygon([xy[a], xy[b], xy[c]]) for a, b, c in tris]
    assert sum(p.area for p in parts) == pytest.approx(poly.area, rel=_REL)
    union = unary_union(parts)
    assert poly.difference(union).area <= _REL * poly.area, "area left uncovered"
    assert union.difference(poly).area <= _REL * poly.area, "ground outside covered"
    return tris


def _ids(pts, start=0):
    return {start + k: p for k, p in enumerate(pts)}, list(range(start, start + len(pts)))


def test_concave_comb_is_covered_exactly():
    """A comb of five deep teeth: every notch is a concavity whose
    Delaunay triangles have centroids in the notch."""
    pts = [(0.0, 0.0), (50.0, 0.0)]
    for k in range(5, 0, -1):
        x = 10.0 * k
        pts += [(x, 40.0), (x - 4.0, 40.0), (x - 4.0, 5.0), (x - 6.0, 5.0)]
    pts[-1] = (0.0, 40.0)
    xy, ring = _ids(pts)
    _check_cover(xy, ring)


def test_two_holes_are_left_out_and_the_rest_covered():
    outer = [(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)]
    h1 = [(10.0, 10.0), (30.0, 10.0), (30.0, 50.0), (10.0, 50.0)]
    h2 = [(60.0, 20.0), (80.0, 15.0), (70.0, 45.0)]
    xy, ring = _ids(outer)
    x1, r1 = _ids(h1, 100)
    x2, r2 = _ids(h2, 200)
    xy.update(x1)
    xy.update(x2)
    _check_cover(xy, ring, [r1, r2])


#: A concave service-road face of an emitted airport patch (local metres,
#: first vertex at the origin): the centroid-kept unconstrained Delaunay
#: covered 47 % of it.
_SPIKE_FACE = [(0.0, 0.0), (2.5, -6.5), (10.0, -2.5), (3.0, -5.5), (2.0, -1.0),
               (12.0, 1.5), (11.5, 5.5), (11.0, 5.5), (10.5, 2.5)]


def test_measured_concave_face_is_covered_exactly():
    xy, ring = _ids(_SPIKE_FACE)
    _check_cover(xy, ring)


def test_the_retired_rule_loses_area_on_the_measured_face():
    """The defect, reproduced: Delaunay of the vertices, triangles kept by
    centroid — about half the face goes missing.  Guards that the fixture
    above is a witness, not a convex face."""
    import numpy as np
    from scipy.spatial import Delaunay
    from shapely.geometry import Point
    poly = Polygon(_SPIKE_FACE)
    pts = np.array(_SPIKE_FACE)
    kept = sum(Polygon(pts[s]).area for s in Delaunay(pts).simplices
               if poly.contains(Point(*pts[s].mean(axis=0))))
    assert kept < 0.6 * poly.area


def test_hole_sharing_an_edge_with_the_ring_is_ring_minus_hole():
    """An INVALID face (a nested face sharing an edge with its parent)
    is the ring minus the hole — never an exception."""
    outer = [(0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0)]
    hole = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    xy, ring = _ids(outer)
    xh, rh = _ids(hole[1:], 100)
    xy.update(xh)
    rh = [ring[0], *rh]
    _check_cover(xy, ring, [rh])


@pytest.mark.parametrize("ring", [[], [0], [0, 1], [0, 1, 2]])
def test_nothing_to_give_is_empty(ring):
    xy = {0: (0.0, 0.0), 1: (1.0, 0.0), 2: (2.0, 0.0)}   # collinear
    assert face_triangles(xy, ring, []) == []
