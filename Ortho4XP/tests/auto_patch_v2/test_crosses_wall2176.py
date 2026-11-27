"""#2176: ``crosses_wall`` reads the cores' boxes the caller holds and makes
the segment only past a box; every answer is the one-wall-at-a-time
reading's (the reference below is the function as it stood)."""
from __future__ import annotations

import math
import types

import numpy as np
from auto_patch_v2.airport.wall_sides import crosses_wall
from shapely.geometry import LineString, Point, box


def _reference(a, b, walls):
    seg = LineString([tuple(a), tuple(b)]) if math.dist(a, b) > 1e-9 else Point(a)
    x0, y0, x1, y1 = seg.bounds
    for w in walls:
        if w.core is None:
            continue
        bx0, by0, bx1, by1 = w.core.bounds
        if x0 > bx1 or x1 < bx0 or y0 > by1 or y1 < by0:
            continue
        if seg.intersects(w.core):
            return True
    return False


def test_boxes_answer_as_the_walk():
    rng = np.random.default_rng(2176)
    walls = [types.SimpleNamespace(core=None)]
    for _ in range(25):
        x, y = rng.uniform(-50, 50, 2)
        walls.append(types.SimpleNamespace(core=box(x, y, x + rng.uniform(0.2, 8),
                                                    y + rng.uniform(0.2, 1.5)).buffer(0.1)))
    boxes = [(math.nan,) * 4 if w.core is None else tuple(w.core.bounds) for w in walls]
    for _ in range(3000):
        a = tuple(rng.uniform(-60, 60, 2))
        b = (a[0] + 1e-10, a[1]) if rng.random() < 0.05 else tuple(rng.uniform(-60, 60, 2))
        want = _reference(a, b, walls)
        assert crosses_wall(a, b, walls) == want
        assert crosses_wall(a, b, walls, boxes) == want
