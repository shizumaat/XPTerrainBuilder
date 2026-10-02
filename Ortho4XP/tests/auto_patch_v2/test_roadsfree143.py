"""Twins for lane ``roadsfree143`` (issue #143, OWNER RULING
``docs/RULINGS.md`` 2026-10-02v (1) "ROADS NEVER HOLD AIRSIDE"): RULINGS
2026-09-30aa rule 1 and the §37 (9) join-pin guard hold for EVERY road face —
the apt.dat 1206 / DSF service-road network, not only the mapped-road ribbons.

    (a) a §37 (9) coverage-edge join pin never lands on an apron/airside
        vertex as a stage-1 constant — the airside vertex solves FREE and the
        road conforms in stage 2 (``constraints/road_ramp.airside_joins``,
        lane ``joinyield128``);
    (b) no ``roads`` / ``road_ramp`` / ``road_cross_section`` / pavement-
        ceiling row footed on a PINNED ROAD vertex enters stage 1 — stage 1
        treats a pinned GROUNDSIDE vertex as FOREIGN.

MEASURED at main 0b3da356 (HECA / KCLT, issue #143 and RULINGS 2026-10-02g):
stage 1 never treated a pinned vertex as foreign, so the join pin was one of
its own constants and every road row footed on it entered the AIRSIDE problem
— 10 rows at HECA, 21 at KCLT, the worst holding an apron ring vertex 1.00 m
up at 30.13577666876, 31.41073906739.  Lane ``roadrows143`` closed that door
ONE GENERATOR AT A TIME (``roads``, ``transverse``, ``pavement_cap``, the
ceiling twin — ``constraints/roads.road_pair_side``, which STAYS: it also
decides who follows in stage 2).  The ruling puts the same law at stage 1's
own derivation site (``solve/design.stage_split`` reading ``[design]
groundside_pin_rulings``), where it holds for every generator and every road
face: ``road_ramp``'s own §37 (6) ramp target and its HARD ceiling among them.

ON THIS SYNTHETIC FIXTURE (apron + a 5 m service road welded to its east edge,
the coverage join at the road's far kerb) the measurement is:

* road-footed rows reaching stage 1 under the old law 4, and 6 once the §37 (6)
  road-ramp channel is published too — 2 ``roads common.roles longitudinal``,
  2 ``rulesets.common.pavement_max_grade ceiling`` and 2 ``roads.
  groundside_road ramp ceiling``; under the ruling, 0.  The last pair is the
  one that makes the case for ONE SITE: ``road_ramp``'s rows are ONE-VERTEX
  rows, so ``road_pair_side``'s one-way minting has no groundside foot to use
  and could never have reached them;
* stage-1 unknowns 177 either way, and the airside answer is BIT-IDENTICAL
  with and without the join pin — 0.0 m, not "within tolerance"
  (:func:`test_the_apron_never_feels_the_join_pin`);
* the kerb, pinned 8 m up at the ribbon's level, emits welded to the apron
  under the service road's own cap (:func:`test_the_road_still_welds_to_the_
  apron_under_its_cap`).

No corpus, no build: the owner's session measures the HECA / KCLT / SPJC
replays (``docs/DEFERRED_VERIFICATION.md``).
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.road_ramp import (GEN as RAMP_GEN, JOIN_RULING,
                                                 airside_joins, road_join_rows,
                                                 reach_seed_rewrite)
from auto_patch_v2.constraints.roads import stage_one_vertices
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.constraints import ConstraintSet, Flat, Source
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve import design as D
from auto_patch_v2.solve.pin_yield import row_vertices, stage1_read_pins

from test_roadrows143 import (RIBBON_ABOVE_M, _airport, _cells, _road_vertices,
                             law)  # noqa: F401  (fixture + fixture geometry)

#: the generators whose rows are the ruling's own list, plus every other
#: generator that can foot a row on a road vertex: the twin asks the ROW's
#: feet, not a generator allow-list (that is the point of the one site)
_RULED_GENS = ("roads", "road_ramp", "transverse", "pavement_ceiling",
               "pavement_road_cap")


def _build(law, *, with_road: bool):
    """The fixture, with or without the service road — the no-road arm is
    the same apron and runway with the road cell removed."""
    airport = _airport(law)
    cells = tuple(c for c in _cells()
                  if with_road or c.role != "service_road")
    pm, _st = build(airport, Classification(cells, (), {}, ()), law)
    return pm, airport


def _generate(pm, law, airport, join: dict[int, float] | None = None,
              ramp: dict[int, float] | None = None):
    """The constraint set, with the §37 (9) coverage-edge join channel (and,
    where asked, the §37 (6) road-ramp target channel) published on the map so
    ``road_join_rows`` / ``road_ramp_rows`` mint their rows THEMSELVES (the
    derivation has one site — the twin never hand-mints a join pin)."""
    ch: dict = {}
    if join is not None:
        ch["road_coverage_join"] = dict(join)
    if ramp is not None:
        ch["road_ramp_z"] = dict(ramp)
    if ch:
        pm = _dc.replace(pm, **ch)
    cs, _c, _w = generate(pm, law, airport)
    return pm, cs


@pytest.fixture(scope="module")
def arm(law):  # noqa: F811
    """The road arm: the map, the weld vertices (road ∩ airside) and the
    road's own groundside kerb."""
    pm, airport = _build(law, with_road=True)
    air = stage_one_vertices(pm, law)
    rv = _road_vertices(pm)
    weld = sorted(rv & air)
    kerb = sorted(rv - air)
    assert weld and kerb, "the fixture welds the road to the apron ring"
    return pm, airport, air, weld, kerb


def _ribbon_z(law, pm, airport, kerb):  # noqa: F811
    """The core ribbon's level just outside the coverage edge: the HECA
    v28332 class — the ribbon standing ``RIBBON_ABOVE_M`` over the apron it
    is welded to."""
    _pm, cs = _generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    z = np.asarray(sol.z, float)
    return float(max(z[v] for v in kerb)) + RIBBON_ABOVE_M, z


# ── (a) the join pin never lands on an airside vertex ────────────────────

def test_a_coverage_join_on_an_apron_vertex_mints_no_pin(law, arm):  # noqa: F811
    """RULING (a), for a 1206 / DSF service road: the join sits on a vertex
    the apron owns, so it is the AIRSIDE's and is never a stage-1 constant."""
    pm, airport, air, weld, _kerb = arm
    join = {v: 999.0 for v in weld}
    pm_j, cs = _generate(pm, law, airport, join)
    assert airside_joins(pm_j, law) == frozenset(weld)
    assert road_join_rows(pm_j, law, airport) == []
    # and nothing else pinned the apron either: every pin in the set is the
    # runway family's own (the CIFP thresholds)
    on_air = [p for p in cs.pins if p.v in air]
    assert all(p.source.generator == "runway_profile" for p in on_air), \
        [(p.v, p.source.generator, p.source.ruling) for p in on_air]
    assert not [p for p in cs.pins if D.ruling_head(p) == _JOIN_HEAD]


_JOIN_HEAD = JOIN_RULING.split(" (")[0].strip()


def test_the_register_names_the_join_pin_and_nothing_is_hand_listed(law):  # noqa: F811
    """``[design] groundside_pin_rulings`` IS the law: the §37 (9) join is
    in it, and with the register emptied stage 1 is the old problem again."""
    assert _JOIN_HEAD in D.groundside_pin_rulings(law)
    empty = _arm_law(law, ())
    assert D.groundside_pin_rulings(empty) == frozenset()


def _arm_law(law, register):  # noqa: F811
    d = law.tables.emit.design
    return _dc.replace(law, tables=_dc.replace(
        law.tables, emit=_dc.replace(law.tables.emit, design=_dc.replace(
            d, groundside_pin_rulings=tuple(register)))))


# ── (b) no road row footed on a pinned road vertex reaches stage 1 ───────

def _stage_one_rows(pm, cs, law):  # noqa: F811
    drop, fixed = D.stage_split(pm, cs, law)
    rep = D.DesignReport()
    base = D.assemble(pm, cs, law, rep, drop=drop, fixed=fixed,
                      stage_roles=D.airside_stage_roles(law))
    return drop, rep, base


def test_no_road_footed_row_reaches_stage_one(law, arm):  # noqa: F811
    """RULING (b).  The join pin is on the road's own kerb — groundside —
    so stage 1 is FOREIGN to it and no row footed there is stage 1's,
    whichever generator minted it."""
    pm, airport, air, weld, kerb = arm
    ribbon, _z0 = _ribbon_z(law, pm, airport, kerb)
    pm_j, cs = _generate(pm, law, airport, {v: ribbon for v in kerb})
    assert [p.v for p in cs.pins if D.ruling_head(p) == _JOIN_HEAD] == kerb
    drop, rep, base = _stage_one_rows(pm_j, cs, law)
    assert set(kerb) <= drop, "a pinned GROUNDSIDE vertex is foreign"
    assert not set(weld) & drop, "the weld is the apron's: never foreign"
    offenders = [(r.source.generator, D.ruling_head(r), sorted(row_vertices(r)))
                 for _t_, _hi, r in base.one
                 if set(row_vertices(r)) & set(kerb)]
    assert offenders == [], offenders
    # the airside's own rows are untouched, and they are most of the problem
    assert rep.unknowns > 0 and len(base.one) > 0
    # stage 1 no longer READS the join pin, so it is stage 2's to yield
    heads = frozenset(law.tables.emit.design.yielding_pin_rulings)
    assert not stage1_read_pins(cs, heads, drop) & set(kerb)


def test_the_old_law_let_those_rows_in(law, arm):  # noqa: F811
    """The counterfactual that makes the twin a measurement: with the
    register emptied — stage 1's law before the ruling — road-footed rows
    DO reach stage 1 through the pin."""
    pm, airport, _air, _weld, kerb = arm
    ribbon, _z0 = _ribbon_z(law, pm, airport, kerb)
    before = _arm_law(law, ())
    pm_j, cs = _generate(pm, before, airport, {v: ribbon for v in kerb})
    drop, _rep, base = _stage_one_rows(pm_j, cs, before)
    assert not set(kerb) & drop
    offenders = [r for _t_, _hi, r in base.one
                 if set(row_vertices(r)) & set(kerb)]
    assert offenders, "the fixture reproduces the defect under the old law"
    assert {r.source.generator for r in offenders} <= set(_RULED_GENS), \
        sorted({r.source.generator for r in offenders})


def test_road_ramps_own_rows_leave_stage_one_too(law, arm):  # noqa: F811
    """THE REASON THE LAW MOVED TO ONE SITE.  ``road_ramp``'s own §37 (6)
    rows — the ramp target and its HARD ceiling — were never one of lane
    ``roadrows143``'s four generators, and no per-generator fix could have
    reached them: they are ONE-VERTEX rows, so they have no "groundside
    foot" to be minted one-way on.

    MEASURED on this fixture, both arms: under the old law 6 rows footed on
    the pinned kerb reach stage 1 — 2 ``roads common.roles longitudinal``,
    2 ``pavement_max_grade ceiling`` and 2 ``roads.groundside_road ramp
    ceiling``, which is the class ``[design]``'s own note records as the
    WORST row of HECA's whole airside set (0.1794 m on a pinned service-road
    vertex at 30.13717041421, 31.4124359031).  Under the ruling: 0.
    """
    pm, airport, _air, _weld, kerb = arm
    ribbon, z_nopin = _ribbon_z(law, pm, airport, kerb)
    ramp = {v: float(min(z_nopin[v] for v in kerb)) - 4.0 for v in kerb}
    join = {v: ribbon for v in kerb}

    def _rows(lw):
        pm_j, cs = _generate(pm, lw, airport, join, ramp)
        heads = {D.ruling_head(r) for r in cs.rows()
                 if r.source.generator == RAMP_GEN}
        assert _RAMP_CEILING_HEAD in heads, sorted(heads)
        _drop, _rep, base = _stage_one_rows(pm_j, cs, lw)
        return [(r.source.generator, D.ruling_head(r))
                for _t_, _hi, r in base.one
                if set(row_vertices(r)) & set(kerb)]

    before = _rows(_arm_law(law, ()))
    assert (RAMP_GEN, _RAMP_CEILING_HEAD) in before, before
    assert len(before) == 6, before
    assert _rows(law) == []


_RAMP_CEILING_HEAD = "roads.groundside_road ramp ceiling"


def test_a_pin_welded_into_an_airside_class_is_not_foreign(law, arm):  # noqa: F811
    """THE ONE WAY THIS RULE COULD MOVE AIRSIDE, and it does not: a join
    pin rigidly welded (``Flat``) to an apron vertex fixes the APRON's own
    value too, so the class is airside and keeps every row — that road IS
    the apron (the free-road ruling)."""
    pm, airport, air, weld, kerb = arm
    ribbon, _z0 = _ribbon_z(law, pm, airport, kerb)
    pm_j, cs = _generate(pm, law, airport, {v: ribbon for v in kerb})
    flat = Flat((weld[0], kerb[0]), Source("twin", "roadsfree143 weld", ()))
    welded = ConstraintSet.from_rows([*cs.rows(), flat])
    drop, _rep, base = _stage_one_rows(pm_j, welded, law)
    assert not {weld[0], kerb[0]} & drop
    assert any(weld[0] in row_vertices(r) for _t_, _hi, r in base.one), \
        "the apron keeps its own rows where a road is welded rigid to it"


# ── the apron's answer, and the road conforming to it in stage 2 ─────────

def test_the_apron_never_feels_the_join_pin(law, arm):  # noqa: F811
    """AIRSIDE IS KING, on one map: the same arm with and without the
    coverage-edge join pin solves the airside to the same values."""
    pm, airport, air, _weld, kerb = arm
    ribbon, z0 = _ribbon_z(law, pm, airport, kerb)
    pm_j, cs = _generate(pm, law, airport, {v: ribbon for v in kerb})
    sol, _rep = solve_design(pm_j, cs, law,
                             stage2_rewrite=lambda lv: reach_seed_rewrite(
                                 pm_j, law, cs, lv))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    z = np.asarray(sol.z, float)
    tol = float(law.tables.emit.design.hard_tol_m)
    worst = max((abs(z[v] - z0[v]), v) for v in air)
    # ZERO, not "within tolerance": the two arms assemble the SAME stage-1
    # problem.  Without the pin the kerb is a free groundside vertex, so it
    # is foreign already; with it, the pin's class is foreign by the ruling.
    # Same rows, same matrix, same airside answer (measured 0.0 m).
    assert worst[0] == 0.0, worst


def test_the_apron_equals_the_no_road_arm(law, arm):  # noqa: F811
    """And against the arm that has NO ROAD at all.  The two arms are
    different maps — the road's face CUTS the apron's east ring edge, which
    inserts a vertex — so the comparison is by POSITION, and the inserted
    weld is held apart from the rest:

    * every other shared airside vertex is equal to the solver's tolerance
      (measured worst 0.013 m over 174 vertices: the ripple of that one
      inserted vertex through the apron's own bending, not a road row);
    * at the weld the delta is the CUT's and not the PIN's, and the twin
      proves it the only way that is a proof — the same delta, to the last
      bit, in the arm that has the road and NO join pin (0.048739 m both).
      The cut is #100's business; this ruling is about the pin.
    """
    pm, airport, air, weld, kerb = arm
    ribbon, z_nopin = _ribbon_z(law, pm, airport, kerb)
    pm_j, cs = _generate(pm, law, airport, {v: ribbon for v in kerb})
    sol, _rep = solve_design(pm_j, cs, law,
                             stage2_rewrite=lambda lv: reach_seed_rewrite(
                                 pm_j, law, cs, lv))
    z = np.asarray(sol.z, float)
    pm0, airport0 = _build(law, with_road=False)
    _pm0, cs0 = _generate(pm0, law, airport0)
    sol0, _r0 = solve_design(pm0, cs0, law)
    assert sol0.status in (Status.OPTIMAL, Status.FEASIBLE)
    z0 = np.asarray(sol0.z, float)
    at0: dict[tuple[float, float], int] = {}
    for v, vx in pm0.vertices.items():
        at0.setdefault((round(vx.xy[0], 3), round(vx.xy[1], 3)), v)
    tol = float(law.tables.emit.design.hard_tol_m)
    shared, cut = 0, 0
    for v in sorted(air):
        xy = pm_j.vertices[v].xy
        v0 = at0.get((round(xy[0], 3), round(xy[1], 3)))
        if v0 is None:
            continue
        if v in weld:                      # the vertex the road's cut inserted
            cut += 1
            assert abs(z[v] - z0[v0]) == abs(z_nopin[v] - z0[v0]), \
                (v, v0, xy, z[v], z_nopin[v], z0[v0])
            continue
        shared += 1
        assert abs(z[v] - z0[v0]) <= tol, (v, v0, xy, z[v], z0[v0])
    assert shared >= len(air) // 2, (shared, len(air))
    assert cut, "the fixture's road cuts the apron ring (the weld)"


def test_the_road_still_welds_to_the_apron_under_its_cap(law, arm):  # noqa: F811
    """The road is not freed of its law, only of the airside's: in stage 2
    its kerb stands within the service road's own longitudinal cap of the
    weld it touches (no 8 m spike at the coverage edge)."""
    pm, airport, air, weld, kerb = arm
    ribbon, _z0 = _ribbon_z(law, pm, airport, kerb)
    pm_j, cs = _generate(pm, law, airport, {v: ribbon for v in kerb})
    sol, rep = solve_design(pm_j, cs, law,
                            stage2_rewrite=lambda lv: reach_seed_rewrite(
                                pm_j, law, cs, lv))
    z = np.asarray(sol.z, float)
    cap = role_cap(law, "service_road").longitudinal
    tol = float(law.tables.emit.design.hard_tol_m)
    for v in kerb:
        xv, yv = pm_j.vertices[v].xy
        near = min(weld, key=lambda w: float(np.hypot(
            *np.subtract(pm_j.vertices[w].xy, (xv, yv)))))
        d = float(np.hypot(*np.subtract(pm_j.vertices[near].xy, (xv, yv))))
        assert abs(z[v] - z[near]) <= cap * d + tol, \
            (v, z[v], near, z[near], d, cap)
    assert rep.pin_yield is not None
