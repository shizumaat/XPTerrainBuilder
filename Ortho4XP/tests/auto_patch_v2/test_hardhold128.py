"""Lane ``hardhold128`` (#128, RULINGS 2026-09-30y): the route reach read
through a super source is the pin x vertex reach, exactly."""
from __future__ import annotations

import numpy as np

from auto_patch_v2.constraints import routes as R


def _graph(n: int, seed: int) -> R.RouteGraph:
    rng = np.random.default_rng(seed)
    a, b = [], []
    for v in range(1, n):
        a.append(int(rng.integers(0, v)))
        b.append(v)
    for _ in range(n):
        x, y = sorted(int(t) for t in rng.integers(0, n, 2))
        if x != y:
            a.append(x)
            b.append(y)
    a, b = np.array(a), np.array(b)
    station = rng.random(n) < 0.7
    return R.RouteGraph(n=n, nodes=frozenset(range(n)), a=a, b=b,
                        length=rng.uniform(5, 80, len(a)),
                        cap=rng.choice([0.015, 0.03, 0.05], len(a)),
                        kind=np.full(len(a), R.CENTRELINE), station=station)


def test_super_source_reach_is_the_pin_matrix_reach():
    g = _graph(300, 7)
    rng = np.random.default_rng(3)
    pins = {int(v): float(rng.uniform(10, 40)) for v in rng.choice(300, 100, replace=False)}
    assert len(pins) > R._SUPER_SOURCE_PINS
    fast = R.reach(g, pins)
    old, R._SUPER_SOURCE_PINS = R._SUPER_SOURCE_PINS, 10 ** 9
    try:
        slow = R.reach(g, pins)
    finally:
        R._SUPER_SOURCE_PINS = old
    assert fast.keys() == slow.keys()
    for v in slow:
        assert fast[v][0] == np.float64(fast[v][0])
        assert abs(fast[v][0] - slow[v][0]) < 1e-9 and abs(fast[v][1] - slow[v][1]) < 1e-9
