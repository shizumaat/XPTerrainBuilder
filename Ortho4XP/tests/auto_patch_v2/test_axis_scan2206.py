"""#2206 — ``stretches.AxisIndex._best_all``, the WHOLE-INDEX nearest scan
measured at once, is the per-segment scan's answer bit for bit.

The old reading is ``_best(x, y, range(len(segs)))`` (kept, it still reads
the 3x3 block); every twin asserts ``==`` on the five floats, never
``approx``.  The tie rule is order-dependent (a tie with a stricter cap
RAISES the running distance), so the twins include tie chains where it
does.  Offline and synthetic.
"""
from __future__ import annotations

import random

import pytest

from auto_patch_v2.constraints.stretches import AxisIndex

from test_perf412a import _axes


def _old(ix: AxisIndex, x: float, y: float):
    return ix._best(x, y, range(len(ix.segs)))


@pytest.mark.parametrize("cell,tie", [(3.0, 1e-6), (15.0, 1e-6), (60.0, 0.5), (15.0, 5.0)])
def test_the_whole_scan_is_the_per_segment_scans(cell, tie):
    rng = random.Random(2206)
    ix = AxisIndex(_axes(rng), cell, tie_m=tie)
    pts = [(300.0, 0.0), (150.0, 0.0), (0.0, 0.0), (5000.0, -4000.0), (-2500.0, 9000.0)]
    pts += [s[:2] for s in ix.segs]                       # every corner: ties
    pts += [(rng.uniform(-3000, 4000), rng.uniform(-3000, 4000)) for _ in range(1500)]
    for x, y in pts:
        assert ix._best_all(x, y) == _old(ix, x, y)


def test_a_tie_chain_that_raises_the_running_distance():
    """Parallel axes 0.4 m apart against a 0.5 m tie, caps falling in scan
    order: each tie takes the farther, stricter axis — the running distance
    climbs past the first candidate set."""
    for seed in range(200):
        rng = random.Random(seed)
        rs = [10.0 + 0.4 * i for i in range(12)] + [rng.uniform(5.0, 40.0) for _ in range(20)]
        rng.shuffle(rs)
        axes = [([(-1.0, r), (1.0, r)], rng.choice((0.03, 0.02, 0.01, 0.005)), 0.02)
                for r in rs]
        ix = AxisIndex(axes, 1000.0, tie_m=rng.choice((0.5, 0.45, 0.41, 1e-6)))
        assert ix._best_all(0.0, 0.0) == _old(ix, 0.0, 0.0)


def test_an_empty_index_reads_none():
    assert AxisIndex([], 15.0)._best_all(0.0, 0.0) is None
