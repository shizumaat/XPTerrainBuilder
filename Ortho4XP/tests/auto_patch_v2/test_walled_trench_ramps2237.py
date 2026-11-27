"""#2237 (owner 2026-11-27T04:09Z, CYYZ ``Tx_A``: "their floor ramps are
missing?"): a walled trench's floor ramps up to every open end an at-grade
mapped road leaves it by -- a plane at ``ramp_grade`` from the walls' top at
the opening, steeper only where a bore's end on the floor would stand over
it -- and stays at the walls' feet where a bore ends."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport.walled_trench import _ramp_z, _ramps, _runs
from auto_patch_v2.law import Law
from shapely.geometry import box

LAW = Law.for_airport("KDEN")
TN = LAW.tables.structures.tunnel


def _ring(floor, step=1.0):
    ring = floor.exterior
    n = int(ring.length / step)
    pts = [ring.interpolate((k + 0.5) * ring.length / n) for k in range(n)]
    return np.array([(p.x, p.y) for p in pts])


def _way(pts, **tags):
    return types.SimpleNamespace(points=tuple(pts), tags={"highway": "service", **tags})


def _setup():
    floor = box(0.0, 0.0, 20.0, 300.0)               # walls on x = 0 and x = 20
    smp = _ring(floor)
    walled = ~((smp[:, 1] < 0.6) | (smp[:, 1] > 299.4))   # both 20 m ends open
    tops = np.full(len(smp), 0.0)
    return floor, smp, walled, tops


def test_runs_are_the_open_stretches_cyclically():
    w = np.array([False, True, True, False, False, True, False])
    got = sorted(sorted(r.tolist()) for r in _runs(w))
    assert got == [[0, 6], [3, 4]]
    assert _runs(np.ones(4, bool)) == [] and _runs(np.zeros(4, bool)) == []


def test_a_road_through_both_ends_ramps_both_at_the_design_grade():
    floor, smp, walled, tops = _setup()
    road = _way([(10.0, -50.0), (10.0, 350.0)])
    ramps, notes = _ramps(floor, smp, walled, tops, 100.0, lambda x, y: 92.0, [road], LAW)
    assert len(ramps) == 2 and len(notes) == 2
    assert all(g == pytest.approx(float(TN.ramp_grade)) for *_r, g in ramps)
    assert _ramp_z(ramps, 10.0, 0.0) == pytest.approx(100.0, abs=0.6)
    assert _ramp_z(ramps, 10.0, 150.0) == pytest.approx(100.0 - 150.0 * float(TN.ramp_grade),
                                                        abs=0.1)


def test_a_bore_end_on_the_floor_steepens_the_ramp_to_reach_it():
    floor, smp, walled, tops = _setup()
    road = _way([(10.0, -50.0), (10.0, 350.0)])
    bore = _way([(-100.0, 60.0), (0.5, 60.0)], tunnel="yes", layer="-1")
    ramps, _n = _ramps(floor, smp, walled, tops, 100.0, lambda x, y: 92.0, [road, bore], LAW)
    g0 = min(ramps, key=lambda r: r[0][1])[3]         # the ramp from y = 0
    assert g0 == pytest.approx(8.0 / 60.0 if 8.0 / 60.0 <= float(TN.ramp_max_grade)
                               else float(TN.ramp_max_grade), rel=0.02)


def test_no_road_no_ramp_and_a_bore_opening_stays_deep():
    floor, smp, walled, tops = _setup()
    assert _ramps(floor, smp, walled, tops, 100.0, lambda x, y: 92.0, [], LAW)[0] == []
    bore = _way([(10.0, -50.0), (10.0, 0.0)], tunnel="yes")
    road = _way([(10.0, 0.0), (10.0, 350.0)])
    ramps, _n = _ramps(floor, smp, walled, tops, 100.0, lambda x, y: 92.0, [bore, road], LAW)
    assert len(ramps) == 1 and ramps[0][0][1] > 200.0  # only the far end ramps
