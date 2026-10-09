"""Owner RULINGS 2026-10-08d (2) / spec §57 (3) as amended: a pad whose
frontage no one flat level reaches by LESS than the terrace floor is welded
by the pavement — the pavement-tier rows naming one of its frontage contacts
give by the floor (``constraints/weld_floor``); nothing else is touched.
Hermetic."""
from __future__ import annotations

from auto_patch_v2.constraints.weld_floor import (pavement_heads, ruling_note,
                                                  seat_misfit, widen_weld_rows)
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import design
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Linear, Source

LAW = Law.load()
APRON = "common.roles.apron frontage chord"
TAXI = "rulesets.taxi.longitudinal centreline"
RUNWAY = "rulesets.runway.longitudinal"
HOLD = "structures.building_pad frontage_hold"


def _src(head):
    return Source("g", head + " (the ruling's text)", ())


def test_the_pavement_heads_are_the_taxi_and_apron_tiers_and_no_other():
    heads = pavement_heads(LAW)
    d = design(LAW)
    by_tier = dict(zip(d.hard_conflict_tiers, d.hard_conflict_ranks))
    assert heads == frozenset(by_tier["taxi"]) | frozenset(by_tier["apron"])
    assert APRON in heads and TAXI in heads
    assert RUNWAY not in heads and HOLD not in heads
    assert not heads & frozenset(by_tier["runway"]) and not heads & frozenset(by_tier["pad"])


def test_a_pavement_row_naming_a_contact_gives_by_the_floor_over_its_chord():
    cs = ConstraintSet.from_rows([Diff(1, 2, 0.015, 20.0, _src(APRON)),
                                  Diff(2, 3, 0.015, 20.0, _src(APRON)),
                                  Diff(1, 4, 0.03, 10.0, _src(TAXI))])
    out, st = widen_weld_rows(cs, {1}, 1.0, pavement_heads(LAW))
    a, b, c = out.diffs
    assert abs(a.bound_m - (0.015 * 20.0 + 1.0)) < 1e-12        # cap·d + floor
    assert abs(c.bound_m - (0.03 * 10.0 + 1.0)) < 1e-12
    assert (b.cap, b.source) == (0.015, _src(APRON))             # names no contact
    assert a.source.ruling.split(" (")[0] == APRON               # the head stands
    assert a.source.ruling.endswith(ruling_note)
    assert st == {1: {"rows": 2, "runway_rows_kept": 0}}


def test_a_runway_vertex_a_runway_head_and_the_pads_own_row_are_never_widened():
    rows = [Diff(1, 9, 0.015, 20.0, _src(APRON)),      # 9 is a runway-family vertex
            Diff(1, 2, 0.0125, 30.0, _src(RUNWAY)),
            Linear(((1, 1.0), (7, -1.0)), 0.0, 0.0, _src(HOLD))]
    cs = ConstraintSet.from_rows(rows)
    out, st = widen_weld_rows(cs, {1}, 1.0, pavement_heads(LAW), never={9})
    assert list(out.rows()) == list(cs.rows())
    assert st == {1: {"rows": 0, "runway_rows_kept": 1}}


def test_a_linear_row_gives_the_floor_times_the_contacts_coefficient():
    row = Linear(((1, 0.5), (2, -0.25), (3, -0.25)), -0.1, 0.1, _src("plane_gradient"))
    out, _st = widen_weld_rows(ConstraintSet.from_rows([row]), {1}, 1.0, pavement_heads(LAW))
    (got,) = out.linears
    assert abs(got.lo - (-0.6)) < 1e-12 and abs(got.hi - 0.6) < 1e-12


def test_it_is_idempotent_and_a_set_with_no_contact_row_is_returned_as_it_is():
    cs = ConstraintSet.from_rows([Diff(1, 2, 0.015, 20.0, _src(APRON))])
    once, _ = widen_weld_rows(cs, {1}, 1.0, pavement_heads(LAW))
    twice, st = widen_weld_rows(once, {1}, 1.0, pavement_heads(LAW))
    assert twice is once and st == {}
    assert widen_weld_rows(cs, {5}, 1.0, pavement_heads(LAW))[0] is cs
    assert widen_weld_rows(cs, {1}, 0.0, pavement_heads(LAW))[0] is cs


INF = float("inf")


def test_a_frontage_whose_two_halves_do_not_meet_by_under_the_floor_is_welded_at_the_middle():
    # one half's contacts reach no higher than 99.4, the other's no lower than 100.4
    misfit, welded, level = seat_misfit(100.4, 99.4, -INF, INF, 1.0, 0.02)
    assert (round(misfit, 6), welded, round(level, 6)) == (0.5, True, 99.9)


def test_the_reach_intersection_closes_the_set_as_the_pair_interval_does():
    # the pair interval admits [99, 101]; the reach bands only [101.6, 103]
    misfit, welded, level = seat_misfit(99.0, 101.0, 101.6, 103.0, 1.0, 0.02)
    assert (round(misfit, 6), welded, round(level, 6)) == (0.3, True, 101.3)


def test_a_frontage_that_meets_has_no_misfit_and_one_at_the_floor_is_not_decided_here():
    assert seat_misfit(99.0, 101.0, -INF, INF, 1.0, 0.02) == (0.0, False, None)
    assert seat_misfit(99.0, 101.0, 100.0, 100.5, 1.0, 0.02) == (0.0, False, None)
    misfit, welded, level = seat_misfit(102.4, 100.0, -INF, INF, 1.0, 0.02)   # 1.2 m: the owner's
    assert (round(misfit, 6), welded, level) == (1.2, False, None)
    assert seat_misfit(100.02, 100.0, -INF, INF, 1.0, 0.02)[1] is False       # under the tolerance
