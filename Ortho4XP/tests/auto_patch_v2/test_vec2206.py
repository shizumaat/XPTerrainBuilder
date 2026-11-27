"""#2206 lane lvec -- three hot scans read at once, bit for bit.

* ``junction_mesh._nearest_axis_all`` == ``nearest_axis`` (the per-chain
  ``project_to_chain`` walk), ties, duplicates, degenerate segments and
  one-point chains included;
* ``anchor_rule.first_pads_holding`` == the per-point first-box-then-ray
  scan ``pad_plurality`` / ``pad_majority`` ran (``placement_family.
  pad_plurality`` and ``anchor_rule.pad_majority`` read through it);
* ``unit_storey.dem_samples`` == the point-by-point grid walk.

Every twin asserts ``==``, never ``approx``.  Offline and synthetic.
"""
from __future__ import annotations

import math
import random

import pytest
from auto_patch_v2.airport import anchor_rule as _ar
from auto_patch_v2.airport.placement_family import pad_plurality
from auto_patch_v2.airport.unit_storey import dem_samples
from auto_patch_v2.constraints.junction_mesh import _nearest_axis_all, nearest_axis
from shapely.geometry import Point, Polygon
from test_perf412a import _axes


# ---------------------------------------------------------------- (c) axes
def _with_degenerates(rng):
    axes = _axes(rng)
    axes += [([(5.0, 5.0)], 0.001, 0.001),                         # one point
             ([(7.0, 7.0), (7.0, 7.0)], 0.001, 0.001),             # degenerate only
             ([(9.0, 9.0), (9.0, 9.0), (40.0, 9.0)], 0.004, 0.01),  # leading degenerate
             ([(1.0, 1.0), (1.0 + 5e-10, 1.0)], 0.0001, 0.01)]     # l2 < 1e-18
    rng.shuffle(axes)
    return axes


@pytest.mark.parametrize("tie", [1e-6, 0.5, 5.0])
def test_the_whole_population_scan_is_nearest_axis(tie):
    for seed in range(6):
        rng = random.Random(2206 + seed)
        axes = _with_degenerates(rng)
        pts = [(5.0, 5.0), (7.0, 7.0), (9.0, 9.0), (150.0, 0.0)]
        pts += [q for a, _c, _t in axes for q in a]                # every vertex: ties
        pts += [(rng.uniform(-1500, 2500), rng.uniform(-1500, 2500)) for _ in range(400)]
        for p in pts:
            assert _nearest_axis_all(p, axes, tie) == nearest_axis(p, axes, tie)


def test_parallel_tie_chains():
    for seed in range(100):
        rng = random.Random(seed)
        rs = [10.0 + 0.4 * i for i in range(12)] + [rng.uniform(5.0, 40.0) for _ in range(20)]
        rng.shuffle(rs)
        axes = [([(-1.0, r), (0.0, r), (1.0, r)], rng.choice((0.03, 0.02, 0.01)), 0.02)
                for r in rs]
        tie = rng.choice((0.5, 0.45, 0.41, 1e-6))
        assert _nearest_axis_all((0.0, 0.0), axes, tie) == nearest_axis((0.0, 0.0), axes, tie)


def test_no_usable_axis_reads_none():
    assert _nearest_axis_all((0.0, 0.0), []) is None
    assert _nearest_axis_all((0.0, 0.0), [([(1.0, 1.0)], 0.1, 0.1)]) is None
    axes = [([(1.0, 1.0), (1.0, 1.0)], 0.1, 0.1)]
    assert _nearest_axis_all((0.0, 0.0), axes) == nearest_axis((0.0, 0.0), axes)


# ---------------------------------------------------------------- (b) pads
def _old_first(pads, cands):
    boxes = [(p, min(v[0] for v in p.ring), min(v[1] for v in p.ring),
              max(v[0] for v in p.ring), max(v[1] for v in p.ring))
             for p in pads if len(p.ring) >= 3]
    out = []
    for la, lo, *_r in cands:
        got = None
        for p, y0, x0, y1, x1 in boxes:
            if y0 <= la <= y1 and x0 <= lo <= x1 and _ar._inside(p.ring, la, lo):
                got = p
                break
        out.append(got)
    return out


def _old_plurality(cands, pads):
    hits = {}
    for p in _old_first(pads, cands):
        if p is not None:
            got = hits.get(p.ref)
            hits[p.ref] = (p, (got[1] if got else 0) + 1)
    if not hits:
        return None
    won = max(hits.values(), key=lambda q: (q[1], q[0].ref))[0]
    return _ar.fold_pad_ref(pads, won.ref) or won


def _pads(rng, n=60):
    pads = []
    for i in range(n):
        la, lo = rng.uniform(0.0, 0.01), rng.uniform(0.0, 0.01)
        k = rng.randint(3, 9)
        r = rng.uniform(1e-4, 2e-3)
        ring = tuple((la + r * math.sin(2 * math.pi * j / k) * rng.uniform(0.5, 1.0),
                      lo + r * math.cos(2 * math.pi * j / k) * rng.uniform(0.5, 1.0))
                     for j in range(k))
        pads.append(_ar.PadRing(f"building{i % 40}", ring, tuple(range(k))))
    pads.append(_ar.PadRing("line", ((0.0, 0.0), (0.01, 0.01))))  # < 3 vertices
    return tuple(pads)


def test_the_first_pad_holding_each_point_is_the_scans():
    for seed in range(5):
        rng = random.Random(seed)
        pads = _pads(rng)
        cands = [(rng.uniform(-0.001, 0.011), rng.uniform(-0.001, 0.011), 0.0, 0.0)
                 for _ in range(3000)]
        cands += [(v[0], v[1], 0.0, 0.0) for p in pads for v in p.ring]  # on the rings
        slot = {"pads": None, "boxes": ()}
        assert _ar.first_pads_holding(pads, cands, slot) == _old_first(pads, cands)
        assert _ar.first_pads_holding(pads, cands, slot) == _old_first(pads, cands)  # held
        assert pad_plurality(cands, pads) == _old_plurality(cands, pads)
        assert pad_plurality(cands[:7], pads) == _old_plurality(cands[:7], pads)
    assert _ar.first_pads_holding((), [(0.0, 0.0)], {"pads": None, "boxes": ()}) == [None]


def test_a_new_pads_object_drops_the_held_arrays():
    rng = random.Random(9)
    a, b = _pads(rng), _pads(rng)
    slot = {"pads": None, "boxes": ()}
    cands = [(rng.uniform(0, 0.01), rng.uniform(0, 0.01)) for _ in range(500)]
    assert _ar.first_pads_holding(a, cands, slot) == _old_first(a, cands)
    assert _ar.first_pads_holding(b, cands, slot) == _old_first(b, cands)


# ---------------------------------------------------------------- (a) DEM
class _Dem:
    def z(self, x, y):
        if x > 180.0:
            raise ValueError("off the raster")
        return float("nan") if y < -50.0 else 0.37 * x - 0.11 * y + math.sin(x * y)

    def z_many(self, xs, ys):
        import numpy as np
        return np.array([self.z(x, y) if x <= 180.0 else np.nan
                         for x, y in zip(xs, ys, strict=True)])


class _PointDem(_Dem):
    z_many = None


def _old_samples(dem, g, step=2.0):
    if dem is None or g is None or g.is_empty:
        return []
    x0, y0, x1, y1 = g.bounds
    h = max(step, math.sqrt(max(g.area, 1.0) / 400.0))
    zs = []
    y = y0 + 0.5 * h
    while y < y1:
        x = x0 + 0.5 * h
        while x < x1:
            if g.contains(Point(x, y)):
                try:
                    z = float(dem.z(x, y))
                except Exception:  # noqa: BLE001
                    z = float("nan")
                if z == z:
                    zs.append(z)
            x += h
        y += h
    return zs


def test_the_dem_grid_is_the_walks():
    rng = random.Random(2206)
    gs = [Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),            # grid points on edges
          Polygon([(0, 0), (4, 0), (4, 4), (0, 4)]).buffer(0.0),
          Point(3.3, 1.7).buffer(0.4),                               # smaller than a step
          Polygon([(0, 0), (900, 0), (900, 3), (0, 3)]),            # long and thin
          Polygon([(150, -80), (220, -80), (220, 40), (150, 40)]),  # NaN and raising
          Polygon(), None]
    for _ in range(40):
        c = (rng.uniform(-100, 200), rng.uniform(-100, 100))
        gs.append(Point(c).buffer(rng.uniform(1, 90), quad_segs=rng.randint(1, 8)))
    for g in gs:
        for step in (2.0, 1.0):
            for dem in (_Dem(), _PointDem()):
                assert dem_samples(dem, g, step) == _old_samples(dem, g, step)
    assert dem_samples(None, gs[0]) == []
