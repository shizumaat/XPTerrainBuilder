"""#2206: the wall class's bulk reads equal the point-by-point ones they
replace (``wall_class._across_pairs``; ``sunk_frame._road_plate``'s road
pre-selection)."""
from __future__ import annotations

import types

import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.ops import nearest_points

from auto_patch_v2.airport import sunk_frame, wall_class
from auto_patch_v2.law import Law


def _pairs_one_by_one(whole, wide, ring_m):
    """The reading before #2206: one ``interpolate`` and one
    ``nearest_points`` per ring point."""
    grown = whole.buffer(ring_m)
    near, wall, far = [], [], []
    for g in getattr(grown, "geoms", [grown]):
        for t in np.arange(0.0, g.exterior.length, 2.0):
            p = g.exterior.interpolate(float(t))
            q = nearest_points(whole, p)[0]
            dx, dy = q.x - p.x, q.y - p.y
            n = (dx * dx + dy * dy) ** 0.5
            if n <= 1e-9:
                continue
            k = (wide + ring_m) / n
            near.append((p.x, p.y))
            wall.append((q.x, q.y))
            far.append((q.x + dx * k, q.y + dy * k))
    return tuple(np.asarray(a, dtype=float).reshape(-1, 2) for a in (near, wall, far))


def test_across_pairs_equal_the_point_by_point_reading():
    shapes = [box(0.0, 0.0, 48.3, 2.7),
              Polygon([(0, 0), (31.7, 4.1), (33.0, 7.9), (2.2, 3.3)]),
              box(0, 0, 3, 3).union(box(40, 0, 43, 9))]       # two rings
    for whole in shapes:
        wide = 2.0 * whole.area / whole.length
        for ring in (3.0, 7.5):
            got = wall_class._across_pairs(whole, wide, ring)
            ref = _pairs_one_by_one(whole, wide, ring)
            for a, b in zip(got, ref, strict=True):
                assert a.shape == b.shape and np.array_equal(a, b)


def test_road_preselection_reads_what_every_road_reads():
    """Every road whose box misses the plate crosses none of it: the
    tree's candidates decide as all roads do."""
    law = Law.load()
    rng = np.random.default_rng(2206)
    ways = []
    for i in range(300):
        x, y = rng.uniform(-500, 500, 2)
        pts = [(x, y)] + [(x + dx, y + dy) for dx, dy in rng.uniform(-80, 80, (3, 2))]
        ways.append(types.SimpleNamespace(points=pts, tags={"highway": "service"}, id=i))
    airport = types.SimpleNamespace(osm_ways=ways)
    memo: dict = {}
    lines, tree = sunk_frame._road_lines(airport, law, memo)
    assert sunk_frame._road_lines(airport, law, memo)[1] is tree       # held for the run
    for _ in range(50):
        cx, cy = rng.uniform(-500, 500, 2)
        plate = box(cx, cy, cx + rng.uniform(5, 60), cy + rng.uniform(5, 60))
        for need in (0.0, 5.0, 20.0):
            brute = any(LineString(w.points).intersection(plate).length >= need for w in ways)
            sel = lines[tree.query(plate)] if need > 0.0 else lines
            got = bool(np.any([g.intersection(plate).length >= need for g in sel]))
            assert got == brute
