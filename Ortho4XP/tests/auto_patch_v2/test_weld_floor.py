"""Owner RULINGS 2026-10-08d (2) / spec §57 (3) as amended: a pad whose
frontage no one flat level reaches by LESS than the terrace floor is welded
by the pavement — the pavement-tier rows naming a contact that closes the
set give by what that contact is short (``constraints/weld_floor``); nothing
else is touched; a weld off its datum by under the floor is sealed on it.
Hermetic."""
from __future__ import annotations

from auto_patch_v2.constraints.weld_floor import (contact_gives, pavement_heads,
                                                  ruling_note, seal_welds, seat_misfit,
                                                  widen_weld_rows)
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


def test_a_pavement_row_naming_a_contact_gives_by_its_shortfall_over_its_chord():
    cs = ConstraintSet.from_rows([Diff(1, 2, 0.015, 20.0, _src(APRON)),
                                  Diff(2, 3, 0.015, 20.0, _src(APRON)),
                                  Diff(1, 4, 0.03, 10.0, _src(TAXI))])
    out, st = widen_weld_rows(cs, {1: 0.4}, pavement_heads(LAW))
    a, b, c = out.diffs
    assert abs(a.bound_m - (0.015 * 20.0 + 0.4)) < 1e-12        # cap·d + give
    assert abs(c.bound_m - (0.03 * 10.0 + 0.4)) < 1e-12
    assert (b.cap, b.source) == (0.015, _src(APRON))             # names no contact
    assert a.source.ruling.split(" (")[0] == APRON               # the head stands
    assert a.source.ruling.endswith(ruling_note)
    assert st == {1: {"rows": 2, "runway_rows_kept": 0}}


def test_a_runway_vertex_a_runway_head_and_the_pads_own_row_are_never_widened():
    rows = [Diff(1, 9, 0.015, 20.0, _src(APRON)),      # 9 is a runway-family vertex
            Diff(1, 2, 0.0125, 30.0, _src(RUNWAY)),
            Linear(((1, 1.0), (7, -1.0)), 0.0, 0.0, _src(HOLD))]
    cs = ConstraintSet.from_rows(rows)
    out, st = widen_weld_rows(cs, {1: 1.0}, pavement_heads(LAW), never={9})
    assert list(out.rows()) == list(cs.rows())
    assert st == {1: {"rows": 0, "runway_rows_kept": 1}}


def test_a_row_naming_two_contacts_takes_the_larger_give():
    cs = ConstraintSet.from_rows([Diff(1, 2, 0.015, 20.0, _src(APRON))])
    out, st = widen_weld_rows(cs, {1: 0.2, 2: 0.5}, pavement_heads(LAW))
    assert abs(out.diffs[0].bound_m - (0.015 * 20.0 + 0.5)) < 1e-12
    assert st == {1: {"rows": 1, "runway_rows_kept": 0}, 2: {"rows": 1, "runway_rows_kept": 0}}


def test_a_linear_row_gives_the_shortfall_times_the_contacts_coefficient():
    row = Linear(((1, 0.5), (2, -0.25), (3, -0.25)), -0.1, 0.1, _src("plane_gradient"))
    out, _st = widen_weld_rows(ConstraintSet.from_rows([row]), {1: 1.0}, pavement_heads(LAW))
    (got,) = out.linears
    assert abs(got.lo - (-0.6)) < 1e-12 and abs(got.hi - 0.6) < 1e-12


def test_it_is_idempotent_and_a_set_with_no_contact_row_is_returned_as_it_is():
    cs = ConstraintSet.from_rows([Diff(1, 2, 0.015, 20.0, _src(APRON))])
    once, _ = widen_weld_rows(cs, {1: 1.0}, pavement_heads(LAW))
    twice, st = widen_weld_rows(once, {1: 1.0}, pavement_heads(LAW))
    assert twice is once and st == {}
    assert widen_weld_rows(cs, {5: 1.0}, pavement_heads(LAW))[0] is cs
    assert widen_weld_rows(cs, {1: 0.0}, pavement_heads(LAW))[0] is cs
    assert widen_weld_rows(cs, {}, pavement_heads(LAW))[0] is cs


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


def test_only_the_contacts_that_close_the_set_give_each_by_what_it_is_short():
    # level 99.9; contact 1 reaches no higher than 99.4, contact 2 no lower than
    # 100.4, contact 3 holds the level, contact 4's REACH BAND stops at 99.7
    gives = contact_gives(99.9, [1, 2, 3, 4], lo={1: 98.0, 2: 100.4, 3: 99.0, 4: 99.0},
                          hi={1: 99.4, 2: 101.0, 3: 100.5, 4: 100.5},
                          bands={4: (None, 99.7)}, tol_m=0.02)
    assert {c: round(g, 6) for c, g in gives.items()} == {1: 0.52, 2: 0.52, 4: 0.22}


def test_a_weld_off_its_datum_inside_the_residual_class_is_sealed_on_it():
    """Spec §57 (3) (ii-c): contact 1 stands 0.04 m off its datum 9 (the solve's
    residual: sealed), contact 2 within the tolerance, contact 3 is a FIXED point
    (skipped), contact 4 is 0.30 m off — over the seal's bound and under the
    floor: NOT sealed, it is the pavement's to give (``welds_off``) — contact 5
    is held by two datum columns, contact 7 is 1.2 m off (the floor or over:
    nobody's here)."""
    from auto_patch_v2.constraints.weld_floor import welds_off
    levels = {9: 100.0, 8: 101.0, 1: 99.96, 2: 100.015, 3: 99.5, 4: 99.7, 5: 100.3,
              7: 98.8}
    z = dict(levels)
    welds = [(1, 9, "b1"), (2, 9, "b1"), (3, 9, "b1"), (4, 9, "b1"), (5, 9, "b1"),
             (5, 8, "b2"), (6, 9, "b1"), (7, 9, "b1")]
    off = welds_off(welds, levels, 0.05, 1.0, 0.02, {3})
    assert {c: round(g, 6) for c, g in off.items()} == {4: 0.32}
    got = seal_welds(welds, levels, z, max_m=0.05, tol_m=0.02, skip={3})
    assert {c: (p, round(m, 6)) for c, (p, m) in got.items()} == {1: ("b1", 0.04)}
    assert levels[1] == z[1] == 100.0
    assert (levels[2], levels[3], levels[4], levels[5], levels[7]) == (
        100.015, 99.5, 99.7, 100.3, 98.8)
    assert seal_welds(welds, levels, None, 0.05, 0.02, {3}) == {}       # idempotent


def test_the_least_allowance_is_bisected_and_feasible():
    """Spec §57 (3) (ii-b): the least over-cap grade that opens the set, by
    bisection — the returned value is feasible and within hi / 2**steps."""
    from auto_patch_v2.constraints.weld_floor import least_allowance
    calls = []

    def opens(d):
        calls.append(d)
        return d >= 0.011
    got = least_allowance(opens, 0.08, steps=8)
    assert opens(got) and got - 0.011 <= 0.08 / 256 and len(calls) == 10
    assert least_allowance(lambda d: False, 0.08) is None


def test_every_pavement_row_inside_the_fronted_faces_takes_the_one_allowance():
    """ONE over-cap grade per block, uniform over the rows whose EVERY vertex
    lies in the fronted faces: a Diff reads cap + delta, a point-vs-foot
    Linear gives delta x span x coefficient, a row with a vertex outside, a
    row of another head, a pad row and a runway row are left; idempotent."""
    from auto_patch_v2.constraints.weld_floor import face_note, widen_face_rows
    heads = {"A"}
    def src(h):
        return Source("g", h + " (note)", ())
    xy = {1: (0.0, 0.0), 2: (10.0, 0.0), 3: (20.0, 0.0), 4: (30.0, 0.0), 9: (5.0, 0.0)}
    rows = [Diff(1, 2, 0.015, 10.0, src("A")),            # inside: widened
            Diff(2, 4, 0.015, 20.0, src("A")),            # 4 is outside
            Diff(1, 3, 0.015, 20.0, src("B")),            # not a pavement head
            Diff(1, 9, 0.015, 5.0, src("A")),             # 9 is runway
            Linear(((2, 1.0), (1, -0.5), (3, -0.5)), None, 0.0, src("A")),   # span 0: left
            Linear(((3, 1.0), (1, -1.0)), -0.3, 0.3, src("A"))]             # span 20 m
    cs = ConstraintSet.from_rows(rows)
    out, st = widen_face_rows(cs, [({1, 2, 3, 9}, 0.011)], heads, {9}, xy)
    got = {(type(r).__name__, getattr(r, "a", None), getattr(r, "b", None)): r for r in out.rows()}
    assert abs(got[("Diff", 1, 2)].cap - 0.026) < 1e-12
    assert face_note in got[("Diff", 1, 2)].source.ruling
    assert got[("Diff", 2, 4)].cap == got[("Diff", 1, 3)].cap == got[("Diff", 1, 9)].cap == 0.015
    lin = [r for r in out.rows() if isinstance(r, Linear)]
    wide = [r for r in lin if face_note in r.source.ruling]
    assert len(wide) == 1 and abs(wide[0].hi - 0.52) < 1e-9 and abs(wide[0].lo + 0.52) < 1e-9
    assert st == [{"rows": 2, "runway_rows_kept": 1}]
    assert widen_face_rows(out, [({1, 2, 3, 9}, 0.011)], heads, {9}, xy)[0] is out
