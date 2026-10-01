"""Twins for lane ``joinyield128`` (issues #128 / #143; RULINGS 2026-09-30be
— the apron cap is HARD everywhere; the free-road ruling; airside is king).

MEASURED (HECA, capture ``frames/hardhold128/HECA.pkl``, branch
``claude/rwyband128`` 270142bf): the §37 (9) coverage-edge join pinned
``pav37|route3`` v7903 — an APRON ring vertex — at the core ribbon's
99.83 m, 5.62 m over the hard-capped apron stage 1 solves there.  The
stage-1 yield released it (94.21 m); stage 2's rewrite re-read the
UN-yielded set and RE-PINNED it at 99.83 m while the sidecar told the core
ribbon to take 94.21 m: a 6.97 m apron|apron cliff at 30.11658, 31.41098.

1. A join on an AIRSIDE (stage-1) face mints no ``Pin``: the vertex takes
   the airside's solved value (``road_ramp.airside_joins``), and the
   published join follows it (``with_pin_yield(withheld=, z=)``).
2. A pin stage 1 released stays released in stage 2.
3. The published patch level is the one the patch carries (final ``z``).
"""
from __future__ import annotations

import dataclasses as _dc
import types

import numpy as np

from auto_patch_v2.constraints.road_ramp import (GEN, JOIN_RULING, airside_joins,
                                                 road_join_rows)
from auto_patch_v2.emit.road_join import with_pin_yield
from auto_patch_v2.law.tables import airside_stage_roles, role_cap
from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve import design as D
from auto_patch_v2.solve.design_roles import hard_rulings, ruling_head
from auto_patch_v2.solve.pin_yield import hard_violated

from test_flatpad128v3 import _arm, built, law  # noqa: F401  (fixtures)

#: the depth of the counterfactual road pin under the apron (the HECA
#: v7903 class: the ribbon 5.62 m off the hard-capped apron)
_ROAD_UNDER_M = 5.0


def _apron_ring_vertex(pm):
    for f in pm.faces.values():
        if f.role == "apron":
            for v in pm.ring_vertices(f.ring):
                return v
    raise AssertionError("the fixture has an apron")


def test_a_join_on_an_apron_vertex_is_withheld_and_the_apron_holds_its_cap(
        law, built):  # noqa: F811
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    sol0, _r0 = solve_design(pm, cs, lw)
    assert sol0.status in (Status.OPTIMAL, Status.FEASIBLE)
    v = _apron_ring_vertex(pm)
    z_road = float(sol0.z[v]) - _ROAD_UNDER_M
    pm_j = _dc.replace(pm, road_coverage_join={v: z_road})
    assert v in airside_joins(pm_j, lw)
    assert road_join_rows(pm_j, lw, None) == []          # never pinned
    sol, _rep = solve_design(pm_j, cs, lw)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    tol = float(lw.tables.emit.design.hard_tol_m)
    # the apron vertex keeps the airside's value — no road pull at all
    assert abs(float(sol.z[v]) - float(sol0.z[v])) <= tol
    # and every hard row on it holds (the apron cap among them)
    on_v = ConstraintSet.from_rows([r for r in cs.rows()
                                    if v in _vertices(r)])
    assert not hard_violated(on_v, sol.z, hard_rulings(lw), tol)
    # the counterfactual: the same join PINNED drags the vertex 5 m down
    pinned = ConstraintSet.from_rows(
        [*cs.rows(), Pin(v, z_road, Source(GEN, JOIN_RULING, (f"vertex:{v}",)))])
    sol_p, _ = solve_design(pm_j, pinned, lw)
    assert abs(float(sol_p.z[v]) - z_road) <= tol
    # the ribbon yields to the airside's level (the sidecar's road_join_yield)
    out = with_pin_yield(pm_j, [], 0.01, withheld=airside_joins(pm_j, lw),
                         z=sol.z)
    assert out.road_join_yield == {v: (z_road, float(sol.z[v]))}
    assert out.road_coverage_join[v] == float(sol.z[v])
    assert role_cap(lw, "apron") is not None


def _vertices(r):
    from auto_patch_v2.solve.pin_yield import row_vertices
    return row_vertices(r)


def test_a_groundside_join_is_still_pinned(law):  # noqa: F811
    air = airside_stage_roles(law)
    assert "apron" in air and "service_road" not in air
    faces = {0: types.SimpleNamespace(role="apron", ref="pav37"),
             1: types.SimpleNamespace(role="service_road", ref="route3")}
    verts = {10: types.SimpleNamespace(incident_faces=(0, 1)),
             11: types.SimpleNamespace(incident_faces=(1,))}
    pm = types.SimpleNamespace(faces=faces, vertices=verts,
                               road_coverage_join={10: 99.83, 11: 100.75})
    assert airside_joins(pm, law) == frozenset({10})
    rows = road_join_rows(pm, law, None)
    assert [(r.v, r.z) for r in rows] == [(11, 100.75)]


def test_the_published_level_is_the_level_the_patch_carries():
    pm = types.SimpleNamespace(road_coverage_join={3: 100.755, 9: 40.0},
                               road_join_yield={})
    pm = _PM(pm.road_coverage_join)
    recs = [{"v": 3, "xy": (0, 0), "pinned_m": 100.755, "z_m": 101.075,
             "excess_m": 0.32}]
    z = [0.0] * 10
    z[3], z[9] = 100.755, 40.0
    # the record's stage-local 101.075 is NOT what the patch carries
    assert with_pin_yield(pm, recs, 0.01, z=z).road_join_yield == {}
    z[3] = 101.0
    assert with_pin_yield(pm, recs, 0.01, z=z).road_join_yield == {
        3: (100.755, 101.0)}
    # no z: the record's value (the previous contract)
    assert with_pin_yield(pm, recs, 0.01).road_join_yield == {
        3: (100.755, 101.075)}


@_dc.dataclass(frozen=True)
class _PM:
    road_coverage_join: dict
    road_join_yield: dict = _dc.field(default_factory=dict)


def test_a_pin_stage_1_released_stays_released_in_stage_2(law, monkeypatch):  # noqa: F811
    lw = _arm(law, staged_solve=True)
    src = Source(GEN, JOIN_RULING, ("vertex:5",))
    cs_orig = ConstraintSet(pins=(Pin(5, 99.83, src),))
    seen: dict = {}
    sol1 = types.SimpleNamespace(z=[0.0] * 6, status=Status.OPTIMAL)
    rep1 = types.SimpleNamespace(hard_settled=True)

    def fake_stage_one(planar, cs, law_, hold, s1):
        return planar, ConstraintSet(), (sol1, rep1, set(), {}, {}, {}), None, [
            {"v": 5, "stage": 1, "pinned_m": 99.83, "z_m": 94.21,
             "excess_m": -5.62}]

    class _Stop(Exception):
        pass

    def fake_solve_stage(planar, cs, law_, options=None, **kw):
        seen["cs"] = cs
        raise _Stop

    monkeypatch.setattr(D, "stage_one", fake_stage_one)
    monkeypatch.setattr(D, "_solve_stage", fake_solve_stage)
    try:
        D.solve_design(types.SimpleNamespace(), cs_orig, lw,
                       stage2_rewrite=lambda lv: (cs_orig, {}))
    except _Stop:
        pass
    cs2 = seen["cs"]
    assert not [p for p in cs2.pins if p.v == 5]          # not re-pinned
    tgt = [r for r in cs2.linears if [t for t, _c in r.terms] == [5]]
    assert tgt and ruling_head(tgt[0]) == ruling_head(cs_orig.pins[0])
    assert np.isclose(tgt[0].lo, 99.83)
