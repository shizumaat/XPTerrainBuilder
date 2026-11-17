"""Twins of the car lots' stage (#2114 round 2 P1/P3;
``constraints/car_lot_follow``, ``pipeline/stage_one_map.late_constraints``
``alone``): a car lot meets a standing pad or road with no step only where
its own ground (the DEM under its nearest car) agrees within ``cap x d`` +
the weld step; otherwise the stand-off is a declared terrace and no row
binds it; and no row of any other generator couples a lot to a constant."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.constraints import car_lot_follow as clf
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Pin, Source
from auto_patch_v2.pipeline.stage_one_map import late_constraints, late_followers

LAW = Law.for_airport("KBNA")


def _pm(coords, faces):
    eid, ends = {}, {}

    def edge(a, b):
        k = frozenset((a, b))
        if k not in eid:
            eid[k] = 1000 + len(eid)
            ends[eid[k]] = types.SimpleNamespace(a=a, b=b)
        return eid[k]
    fs = {}
    for i, (role, ref, ring) in enumerate(faces):
        n = len(ring)
        fs[i] = types.SimpleNamespace(
            id=i, role=role, ref=ref, holes=(),
            ring=tuple(edge(ring[k], ring[(k + 1) % n]) for k in range(n)))
    return types.SimpleNamespace(
        vertices={i: types.SimpleNamespace(xy=xy) for i, xy in enumerate(coords)},
        faces=fs, edges=ends,
        ring_vertices=lambda cyc: tuple(v for e in cyc for v in (ends[e].a, ends[e].b)))


class _Slope:
    """A DEM falling ``grade`` per metre eastward from ``z0`` at x = 0."""

    def __init__(self, z0, grade):
        self.z0, self.grade = z0, grade

    def z(self, x, y):
        return self.z0 - self.grade * x


# a standing ring (0..3) and a car lot (4..7) 1.45 m east of it, cars inside
COORDS = [(0.0, 0.0), (10.0, 0.0), (10.0, 40.0), (0.0, 40.0),
          (11.45, 0.0), (40.0, 0.0), (40.0, 40.0), (11.45, 40.0)]
CARS = {"carlot:0": np.array([[17.0, 5.0], [17.0, 35.0], [30.0, 20.0]])}
RING = {0: 172.4, 1: 172.4, 2: 172.4, 3: 172.4}


def _lot_beside(role):
    return _pm(COORDS, [(role, f"{role}40", (0, 1, 2, 3)),
                        ("parking_lot", "carlot:0", (4, 5, 6, 7))])


def test_a_lot_far_below_its_pad_keeps_its_ground_behind_a_declared_terrace():
    # the cars stand ~1.5 m under the pad (6 % ground): a bank, no weld
    rows, rep = clf.car_lot_follow_rows(_lot_beside("building"), LAW, RING, CARS,
                                        _Slope(172.0, 0.06))
    assert rows == [] and rep["welded_lots"] == 0 and rep["terraced_lots"] == 1
    (t,) = rep["terraces"]
    assert t["lot"] == "carlot:0" and t["ring"] == "building:building40"
    assert t["ring_m"] == pytest.approx(172.4) and t["off_m"] > 0.5


def test_a_lot_whose_ground_agrees_with_its_pad_welds_with_no_step():
    rows, rep = clf.car_lot_follow_rows(_lot_beside("building"), LAW, RING, CARS,
                                        _Slope(172.4, 0.0))
    assert sorted(r.terms[0][0] for r in rows) == [4, 7]
    assert rep["welded_lots"] == 1 and rep["terraces"] == []
    for r in rows:
        assert r.lo <= 172.4 <= r.hi and r.hi - 172.4 < 0.05     # from the set-back


def test_a_lot_beside_a_road_follows_it_within_the_tighter_cap():
    rows, rep = clf.car_lot_follow_rows(_lot_beside("service_road"), LAW, RING, CARS,
                                        _Slope(172.6, 0.0))
    cap = min(role_cap(LAW, "parking_lot").longitudinal,
              role_cap(LAW, "service_road").longitudinal)
    assert len(rows) == 2 and rep["welded_lots"] == 1
    assert rows[0].hi - 172.4 == pytest.approx(cap * 1.45)


def test_the_weld_step_is_a_law_key():
    assert LAW.tables.emit.terrace.car_lot_weld_step_m == 0.5


def test_the_lots_stage_follows_the_lots_alone_and_keeps_no_coupling_row():
    pm = _lot_beside("building")
    free, rep = late_followers(pm, lots_only=True)
    assert free == {4, 5, 6, 7} and rep["gap_faces"] == 1
    src = Source("pad_frontage_gs", "groundside_frontage (28)", ())
    inside = Source("roads", "road_within_shape", ())
    cs = ConstraintSet.from_rows([
        Diff(1, 4, 0.05, 1.45, src),          # a lot vertex bound to the pad (§28)
        Diff(4, 5, 0.05, 28.55, inside),      # the lot's own cap
        Pin(6, 170.0, inside),                # a row on the lot alone
        Diff(0, 1, 0.05, 10.0, src)])         # a standing row
    kept, dropped = late_constraints(cs, RING, alone=True)
    assert sorted(type(r).__name__ for r in kept.rows()) == ["Diff", "Pin"]
    assert dropped == {"coupled: pad_frontage_gs": 1, "Diff": 1}
    kept, _d = late_constraints(cs, RING)
    assert len(kept.rows()) == 3                # without ``alone`` the coupling stays
