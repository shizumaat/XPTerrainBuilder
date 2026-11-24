"""#2206 step 4: ``constraints/zones._nearest_edge`` skips an edge whose
squared foot distance is no less than the best's — the answer, ties
included, is the whole scan's (the scan as it stood, below)."""
from __future__ import annotations

import math
import random
import types

from auto_patch_v2.constraints import zones
from auto_patch_v2.geom import exact


def _whole_scan(vw, v, edges, grid, cell, half_of, reach_m, admit=None):
    x, y = vw.xy[v]
    cx, cy = int(x // cell), int(y // cell)
    span = int(math.ceil(reach_m / cell)) + 1
    best = None
    for dx in range(-span, span + 1):
        for dy in range(-span, span + 1):
            for k in grid.get((cx + dx, cy + dy), ()):
                if admit is not None and not admit(k):
                    continue
                (ax, ay), (bx, by) = vw.xy[edges[k][0]], vw.xy[edges[k][1]]
                vx, vy = bx - ax, by - ay
                l2 = vx * vx + vy * vy
                t = 0.0 if l2 < 1e-18 else max(0.0, min(
                    1.0, ((x - ax) * vx + (y - ay) * vy) / l2))
                d = exact.hypot(x - (ax + t * vx), y - (ay + t * vy))
                half = half_of(edges[k])
                if half is None or d > half:
                    continue
                if best is None or d < best[2]:
                    best = (k, t, d)
    return best


def test_the_pruned_scan_is_the_whole_scan_ties_and_all():
    rnd = random.Random(2206)
    cell = 10.0
    for _trial in range(40):
        # a lattice of shared corners (exact ties) and random points
        xy = {i: (float(rnd.randint(0, 8) * 5), float(rnd.randint(0, 8) * 5))
              for i in range(30)}
        xy.update({100 + i: (rnd.uniform(0, 40), rnd.uniform(0, 40)) for i in range(30)})
        ids = list(xy)
        edges = [(rnd.choice(ids), rnd.choice(ids), rnd.choice(("taxi", "runway")))
                 for _ in range(60)]
        grid: dict = {}
        for k, (a, b, _f) in enumerate(edges):
            (ax, ay), (bx, by) = xy[a], xy[b]
            for gx in range(int(min(ax, bx) // cell), int(max(ax, bx) // cell) + 1):
                for gy in range(int(min(ay, by) // cell), int(max(ay, by) // cell) + 1):
                    grid.setdefault((gx, gy), []).append(k)
        vw = types.SimpleNamespace(xy=xy)
        halves = {"taxi": 6.0, "runway": None if _trial % 3 == 0 else 15.0}
        for v in ids:
            for half_of, admit in ((lambda e: 1e9, None),
                                   (lambda e: halves[e[2]], lambda k: k % 4 != 0)):
                assert zones._nearest_edge(vw, v, edges, grid, cell, half_of, 20.0, admit) \
                    == _whole_scan(vw, v, edges, grid, cell, half_of, 20.0, admit)
