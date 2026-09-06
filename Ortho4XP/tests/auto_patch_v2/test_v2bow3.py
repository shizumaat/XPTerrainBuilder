"""Twins for RULINGS 2026-09-06l (lane v2bow3 — the bow is the
relaxation's ORDER): the 04t(1) last resort is LEXICOGRAPHIC by law order
(04i).  Stage 1a minimises the RUNWAY family's L1 departure from its DEM
fit subject to every relaxable row inside ``max_over_cap_factor``; stage
1b minimises the slack variance holding that runway within
``[relaxation] runway_hold_tolerance_m``; stage 2 as before.

The fixture is ``test_v2bow``'s ``hangar_slack``: a runway pinned at both
ends beside an apron whose rim three flat pads consume, over 3 m of
relief between the stubs — the hard set has two ways out, the apron
takes slack or the runway sinks.  The pure-variance program (04t(1)
alone, ``ORDER_VARIANCE``) prices the runway's sinking at zero and sinks
it; the lexicographic order keeps it on the DEM and the apron takes the
slack, up to the factor.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.solve import Options, Status, relax
from auto_patch_v2.solve.highs import solve as solve_hard
from auto_patch_v2.solve.tiers import solve_law_ordered

from test_v2bow import _runway_off_dem, hangar_slack  # noqa: F401  (the fixture)


@pytest.fixture(scope="module")
def law():
    # the 06l order under test; the shipped table says "variance" (06m)
    return _with_relaxation(Law.for_airport("ZZZZ"), order="lexicographic")


def _with_relaxation(law: Law, **kw) -> Law:
    rl = _dc.replace(law.tables.emit.relaxation, **kw)
    return Law(tables=_dc.replace(law.tables, emit=_dc.replace(law.tables.emit, relaxation=rl)),
               ruleset_key=law.ruleset_key)


def _inside_the_factor(cand, s1, law) -> None:
    rl = law.tables.emit.relaxation
    tol = law.tables.emit.materiality.grade
    for x in cand:
        e = s1.excess.get(x.index, 0.0)
        if x.kind == "diff":
            assert e <= (rl.max_over_cap_factor - 1.0) * x.row.cap + tol, (x.index, e)
        elif x.kind == "pad":
            assert e <= rl.pad_slope_max + tol, (x.index, e)


def test_the_lexicographic_order_keeps_the_runway_and_the_apron_takes_the_slack(hangar_slack, law):
    """06l: single-stage variance sinks the runway between the stubs; the
    lexicographic order keeps it within the tolerance of its DEM fit and
    the apron takes the slack — every row still inside the factor."""
    airport, pm, cs = hangar_slack
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    rl = law.tables.emit.relaxation
    assert rl.runway_fit_weight == 0.0            # the lexicographic order is THE default
    cand = relax.full_scope(pm, law, cs)
    assert any(x.kind == "diff" for x in cand) and any(x.kind == "pad" for x in cand)
    tol = law.tables.emit.materiality.elevation_m
    control = relax.stage1(pm, cs, cand, law, backend="pwl", order=relax.ORDER_VARIANCE)
    ruled = relax.stage1(pm, cs, cand, law, backend="pwl", weights=w)
    assert control.status == ruled.status == "optimal"
    assert control.order == relax.ORDER_VARIANCE and control.linear_cols == 0
    assert ruled.order == relax.ORDER_LEXICOGRAPHIC
    targets = relax.runway_targets(pm, law)
    assert targets and ruled.linear_cols == len(targets) and ruled.linear_rows == 2 * len(targets)
    assert ruled.stage1a_wall_s > 0.0 and ruled.stage1b_wall_s > 0.0
    assert ruled.wall_s >= ruled.stage1a_wall_s + ruled.stage1b_wall_s - 1e-6
    # stage 1a: the runway at its hard-feasible best — on the DEM here (the
    # pins leave room and the apron's allowance covers the relief)
    dep = ruled.runway_departure_m
    assert dep["stage1a"] <= tol * len(targets), dep
    # stage 1b holds it: the departure grows by at most the tolerance per vertex
    assert dep["stage1b"] <= dep["stage1a"] + rl.runway_hold_tolerance_m * len(targets), dep
    assert set(ruled.hold) == set(targets)
    # the apron takes the slack the runway no longer gives
    assert sum(ruled.slack.values()) > sum(control.slack.values()) + tol
    _inside_the_factor(cand, control, law)
    _inside_the_factor(cand, ruled, law)
    # stage 2 on each relaxed set: the runway between the stubs
    for s1, expect_on_dem in ((control, False), (ruled, True)):
        cs2, _repl = relax.relaxed_hard_set(cs, cand, s1)
        sol = solve_hard(pm, cs2, w, Options(diagnose_iis=False))
        assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
        off = _runway_off_dem(pm, sol.z)
        if expect_on_dem:
            assert off <= tol, off
        else:
            assert off > 10 * tol, off


def test_the_whole_last_resort_reports_the_order_and_the_departure(hangar_slack, law):
    """``solve_relaxed`` answers in the lexicographic order and the report
    carries each stage's wall and the runway's departure before / after."""
    airport, pm, cs = hangar_slack
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    rl = law.tables.emit.relaxation
    sol, rep, cs2 = relax.solve_relaxed(pm, cs, law, w, Options())
    assert sol is not None and rep.applied and rep.certificate["ok"]
    assert rep.order == relax.ORDER_LEXICOGRAPHIC
    assert rep.stage1a_wall_s > 0.0 and rep.stage1b_wall_s > 0.0
    assert rep.stage1_wall_s >= rep.stage1a_wall_s + rep.stage1b_wall_s - 1e-6
    assert set(rep.runway_departure_m) == {"stage1a", "stage1b", "final"}
    assert rep.runway_vertices == len(relax.runway_targets(pm, law))
    tol = law.tables.emit.materiality.elevation_m
    assert rep.runway_departure_m["stage1b"] <= (rep.runway_departure_m["stage1a"]
                                                + rl.runway_hold_tolerance_m * rep.runway_vertices)
    # ``final`` is stage 2's surface under the solve's own preferences (the
    # crown, the end zones) — judged against the CONTROL order's final
    # surface, which sank the runway between the stubs
    targets = relax.runway_targets(pm, law)
    cand = relax.full_scope(pm, law, cs)
    control = relax.stage1(pm, cs, cand, law, backend="pwl", order=relax.ORDER_VARIANCE)
    cs_c, _repl = relax.relaxed_hard_set(cs, cand, control)
    sol_c = solve_hard(pm, cs_c, w, Options(diagnose_iis=False))
    assert relax.runway_departure(sol_c.z, targets) > rep.runway_departure_m["final"] + tol
    line = rep.line()
    assert "order lexicographic" in line and "stage1a" in line and "runway departure" in line
    d = rep.as_dict()
    assert d["order"] == relax.ORDER_LEXICOGRAPHIC and d["runway_departure_m"] == rep.runway_departure_m


def test_the_pipeline_dispatch_relaxes_in_the_lexicographic_order(law):
    """On a hard-INFEASIBLE set (``test_relax``'s hangar row: the runway
    climbs at its cap, the apron cannot follow) ``solve_law_ordered``
    relaxes in the ruled order and the tier report carries it."""
    from test_relax import _hangar_row
    airport, pm = _hangar_row(law)
    cs, _c, _w = generate(pm, law, airport)
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    sol, trep = solve_law_ordered(pm, cs, law, w, Options())
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE) and trep.mode == "relaxed"
    rl = trep.relaxation
    assert rl["applied"] and rl["order"] == relax.ORDER_LEXICOGRAPHIC and rl["certificate"]["ok"]
    assert rl["stage1a_wall_s"] > 0.0 and rl["stage1b_wall_s"] > 0.0
    assert set(rl["runway_departure_m"]) == {"stage1a", "stage1b", "final"}
    assert "order lexicographic" in trep.line()


def test_a_positive_runway_fit_weight_is_the_weighted_single_stage(hangar_slack, law):
    """The 0-default key kept: at a positive ``runway_fit_weight`` (and
    the solve's weights) stage 1 is the 06h single-stage alternative."""
    airport, pm, cs = hangar_slack
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    cand = relax.full_scope(pm, law, cs)
    on = relax.stage1(pm, cs, cand, _with_relaxation(law, runway_fit_weight=1.0),
                      backend="pwl", weights=w)
    assert on.status == "optimal" and on.order == relax.ORDER_WEIGHTED
    assert on.linear_cols > 0 and on.stage1a_wall_s == 0.0
    # without the solve's weights the key cannot scale anything: the ruled order answers
    off = relax.stage1(pm, cs, cand, _with_relaxation(law, runway_fit_weight=1.0), backend="pwl")
    assert off.order == relax.ORDER_LEXICOGRAPHIC


def test_infeasible_at_the_factor_falls_to_the_ladder_with_the_named_failure(law):
    """Two runway pins against the runway's own cap: stage 1a is
    infeasible even at the factor (the same feasible region the variance
    program has), the relaxable scope is refuted, the ladder answers and
    names the failure."""
    from tests.auto_patch_v2.test_m5 import _airport
    airport, pm = _airport(law, None, rw1=(700.0, 760.0))
    cs, _c, _w = generate(pm, law, airport)
    nocert = _with_relaxation(law, iis_time_budget_s=0.0)
    cand = relax.full_scope(pm, law, cs)
    s1 = relax.stage1(pm, cs, cand, nocert)
    assert s1.status == "infeasible" and s1.order == relax.ORDER_LEXICOGRAPHIC
    assert s1.stage1a_wall_s > 0.0 and s1.stage1b_wall_s == 0.0 and "stage 1a" in s1.note
    sol, rep = solve_law_ordered(pm, cs, nocert, DEFAULT_WEIGHTS, Options())
    assert sol.status is Status.INFEASIBLE and rep.mode == "tiered"
    rl = rep.relaxation
    assert not rl["applied"] and rl["scope"] == relax.SCOPE_LADDER
    assert rl["order"] == relax.ORDER_LEXICOGRAPHIC
    assert "STILL infeasible" in rl["reason"] and "unrelaxable contradiction" in rl["reason"]
    assert rep.failure and "no lawful surface" in rep.failure
