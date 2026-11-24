"""#2206: ``geom/line_walk.points_along`` is ``shapely.line_interpolate_point``
bit for bit -- on rings with holes, unions of many triangles, and at the
distances GEOS answers specially (0, vertex totals, a component's end, past
the end)."""
from __future__ import annotations

import numpy as np
import shapely
from auto_patch_v2.geom.line_walk import points_along


def _same(line, d):
    want = shapely.get_coordinates(shapely.line_interpolate_point(line, d))
    got = shapely.get_coordinates(points_along(line, d))
    assert want.shape == got.shape and (want == got).all()


def test_random_outlines_and_their_samples_match_geos_bit_for_bit():
    rng = np.random.default_rng(2206)
    for _ in range(40):
        c = rng.uniform(-300.0, 300.0, (60, 2))
        tris = shapely.polygons(c[rng.integers(0, 60, (80, 3))] * rng.uniform(0.1, 1.3))
        tris = tris[shapely.area(tris) > 1e-6]
        foot = shapely.union_all(shapely.make_valid(tris)).buffer(0.37).buffer(-0.2)
        for poly in [g for g in shapely.get_parts(foot) if g.geom_type == "Polygon"][:3]:
            ring = poly.boundary
            L = ring.length
            n = max(1, int(np.ceil(L / 0.7)))
            _same(ring, (np.arange(n) + 0.5) * (L / n))
            _same(ring, rng.uniform(-1.0, L + 1.0, 500))


def test_the_distances_geos_answers_specially():
    outer = [(0, 0), (10, 0), (10, 10), (0, 10)]
    hole = [(2, 2), (4, 2), (4, 4), (2, 4)]
    ring = shapely.Polygon(outer, [hole]).boundary
    totals = [0.0, 10.0, 20.0, 30.0, 40.0, 42.0, 44.0, 46.0, 48.0]
    _same(ring, np.array(totals + [-1.0, 1e9, 5.0, 40.5]))
    _same(shapely.LineString([(0, 0), (0, 0), (3, 4), (3, 4), (6, 8)]),
          np.array([0.0, 2.5, 5.0, 7.5, 10.0, 11.0]))
