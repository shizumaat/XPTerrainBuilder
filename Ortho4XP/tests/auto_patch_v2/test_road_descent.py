"""THE ROAD RAMP'S GRADE (spec §37 (6) as amended; owner RULINGS
2026-10-08c (1), 2026-10-09c (2b)) — ``airport/road_descent.descend`` on a
graph small enough to read: one road, 10 m between vertices, its floor at
0 m, a contact 10 m above it.

  * ample run -> the DESIGN grade (5 %);
  * a run that fits only at 7.3 % -> 7.3 %, from the road's end or from
    the next contact;
  * a run that needs more than the cap -> the cap, the road ending above
    its floor (what every ramp did when the cap was the grade);
  * no contact -> nothing (the road keeps its floor).
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport.road_descent import descend, descent_line, envelope
from auto_patch_v2.geom.ramp_grade import built_grade, least_grade

DESIGN, CAP, LANE = 0.05, 0.10, 7.0
DROP = 10.0


def _road(length: float, step: float = 10.0):
    """A straight road ``length`` long: vertex 0 the contact, the last
    vertex its end.  ``(adjacency, floors, end_of)``."""
    xs = [step * k for k in range(int(length // step) + 1)]
    if xs[-1] < length - 1e-9:
        xs.append(length)
    adj: dict[int, list[tuple[int, float]]] = {}
    for i in range(len(xs) - 1):
        d = xs[i + 1] - xs[i]
        adj.setdefault(i, []).append((i + 1, d))
        adj.setdefault(i + 1, []).append((i, d))
    floors = {i: 0.0 for i in range(1, len(xs))}
    last = len(xs) - 1
    return adj, floors, xs, (lambda v: ("r", 1) if v == last else None)


def _descend(adj, mouths, floors, end_of, design=DESIGN):
    return descend(adj, mouths, lambda v: mouths.get(v, floors.get(v)), floors,
                   design, CAP, LANE, end_of)


def test_ample_run_is_built_at_the_design_grade():
    adj, floors, xs, end_of = _road(400.0)
    d = _descend(adj, {0: DROP}, floors, end_of)
    assert [r["grade"] for r in d.ramps] == [DESIGN] and d.ramps[0]["why"] == ""
    for i, x in enumerate(xs):
        if x <= DROP / DESIGN:
            assert d.label[i] == pytest.approx(DROP - DESIGN * x)
        else:
            assert i not in d.label           # the ramp ended at its first meet
    # the ramp stands over the floor for drop / design, not drop / cap
    assert d.ramps[0]["length_m"] == pytest.approx(DROP / DESIGN - 10.0)


def test_a_run_that_fits_only_at_7_3_percent_is_built_at_7_3_percent():
    run = DROP / 0.073
    adj, floors, xs, end_of = _road(run)
    (r,) = _descend(adj, {0: DROP}, floors, end_of).ramps
    assert r["grade"] == pytest.approx(0.073) and r["fits"]
    assert DESIGN < r["grade"] < CAP and "the road's end at 137 m" == r["why"]
    d = _descend(adj, {0: DROP}, floors, end_of)
    assert d.label[len(xs) - 1] == pytest.approx(0.0)        # down at its end


def test_the_next_contact_ends_the_run_too():
    """Two contacts 100 m apart, 7.3 m apart in level, the road between
    them on a floor far below: the upper ramp comes down to the lower
    contact (7.3 %)."""
    adj, floors, xs, _e = _road(100.0)
    floors = {v: -50.0 for v in floors if v != len(xs) - 1}
    d = _descend(adj, {0: 7.3, len(xs) - 1: 0.0}, floors, lambda v: None)
    by = {r["mouth"]: r for r in d.ramps}
    assert by[0]["grade"] == pytest.approx(0.073) and by[0]["why"] == "the next contact at 100 m"
    # ... and arrives AT the lower contact's level; that contact's own
    # ramp stands under it everywhere, so it is no ramp of its own
    assert d.label[len(xs) - 1] == pytest.approx(0.0) and len(xs) - 1 not in by


def test_a_run_that_needs_more_than_the_cap_is_built_at_the_cap():
    adj, floors, xs, end_of = _road(80.0)                    # 12.5 %
    d = _descend(adj, {0: DROP}, floors, end_of)
    (r,) = d.ramps
    assert r["grade"] == CAP and not r["fits"]
    # TODAY'S OUTCOME: the cap's own descent, the end 2 m above its floor
    old, _w, _s = envelope(adj, {0: DROP}, CAP)
    assert d.label == pytest.approx(old) and d.label[len(xs) - 1] == pytest.approx(2.0)


def test_an_end_inside_one_lane_width_is_the_mouth_not_a_run():
    adj, floors, _xs, end_of = _road(5.0, step=5.0)
    assert _descend(adj, {0: DROP}, floors, end_of).ramps == []
    assert _descend(adj, {0: DROP}, floors, end_of).label[1] == pytest.approx(DROP - DESIGN * 5.0)


def test_a_road_with_no_contact_has_no_ramp():
    adj, floors, _xs, end_of = _road(200.0)
    assert _descend(adj, {}, floors, end_of) == ({}, {}, [])


def test_the_design_grade_at_the_cap_is_the_envelope_of_old():
    adj, floors, _xs, end_of = _road(300.0)
    mouths = {0: DROP, 12: 4.0}
    d = _descend(adj, mouths, floors, end_of, design=CAP)
    old, walked, _s = envelope(adj, mouths, CAP, floors=floors)
    assert d.label == pytest.approx(old) and d.walked == pytest.approx(walked)


# ── RULINGS 2026-10-09d (2): FIRST MEET, PER RUN, ONLY WHERE FORCED ─────

def test_a_cone_that_met_its_floor_does_not_re_emerge_over_a_later_fall():
    """F1 (§37 (6a) (iii)).  2 m of fill at the contact, level ground for
    200 m, then the floor falls at the cap: the ramp is the first 40 m.
    The persistent cone stood over the fall again (at 300 m it is 13 m
    under the contact's 5 % line... and the floor 10 m lower still)."""
    adj, floors, xs, end_of = _road(400.0)
    floors = {i: (0.0 if xs[i] <= 200.0 else -CAP * (xs[i] - 200.0)) for i in floors}
    d = _descend(adj, {0: 2.0}, floors, end_of)
    (r,) = d.ramps
    assert r["grade"] == DESIGN and r["length_m"] == pytest.approx(30.0)
    assert max(d.walked.values()) == pytest.approx(40.0)
    assert all(xs[i] <= 40.0 for i in d.label)
    # the envelope without the floors is the cone that re-emerged
    old, _w, _s = envelope(adj, {0: 2.0}, DESIGN)
    assert old[len(xs) - 1] > floors[len(xs) - 1] + 1.0


def _forked():
    """A contact (0) with a long road east (1..40, 10 m apart) and a stub
    west (41, 42: 4 m and 8 m away) that ends 3 m down."""
    adj, floors, xs, _e = _road(400.0)
    for a, b in ((0, 41), (41, 42)):
        adj.setdefault(a, []).append((b, 4.0))
        adj.setdefault(b, []).append((a, 4.0))
    floors.update({41: -3.0, 42: -3.0})
    last = len(xs) - 1
    return adj, floors, xs, (lambda v: ("r", 1) if v == last else ("s", 1) if v == 42 else None)


def test_a_stub_end_steepens_its_own_run_only():
    """F2 (§37 (6a) (ii)).  The stub's end, 8 m away and 5 m under the
    contact, cannot be served by the cap: ITS run is at the cap and ends
    in the air; the long run fits at the design grade and keeps it.  Per
    CONTACT the whole cone went to the cap."""
    adj, floors, xs, end_of = _forked()
    d = _descend(adj, {0: 2.0}, floors, end_of)
    (r,) = d.ramps
    assert r["grade"] == DESIGN and r["steepest"] == CAP
    assert not r["fits"]                      # the stub ends in the air
    assert r["why"] == "the road's end at 8 m" and r["length_m"] == pytest.approx(30.0)
    for i in range(1, 5):
        assert d.label[i] == pytest.approx(2.0 - DESIGN * xs[i])
    assert d.label[41] == pytest.approx(2.0 - CAP * 4.0)
    assert d.label[42] == pytest.approx(2.0 - CAP * 8.0)


def test_a_road_that_can_follow_its_floor_from_the_contact_has_no_ramp():
    """RULINGS 2026-10-09d (2).  The contact stands ON the road's floor
    and the floor falls away at 7 % — inside the cap: nothing forces the
    road off its ground, so there is no ramp (a 5 % cone would stand on
    2 m of fill 100 m out).  Half a metre of fill at the contact is a
    ramp again, and it ends where it first meets the floor."""
    adj, floors, xs, end_of = _road(400.0)
    floors = {i: (-0.07 * xs[i] if xs[i] <= 100.0 else -7.0) for i in floors}
    d = _descend(adj, {0: 0.0}, floors, end_of)
    assert d.ramps == [] and d.label == {0: 0.0}
    # ... the same hillside at 12 % (a floor the clamp would not make):
    # the cap cannot follow it, the ramp is built — down the fall AT THE
    # CAP (the steepest it may; 2.5 m over the floor at its foot), and at
    # the design grade from there
    steep = {i: (-0.12 * xs[i] if xs[i] <= 100.0 else -12.0) for i in floors}
    d = _descend(adj, {0: 0.0}, steep, end_of)
    (r,) = d.ramps
    assert d.label[10] == pytest.approx(-0.5 - CAP * 90.0)
    assert r["grade"] == DESIGN and r["length_m"] == pytest.approx(140.0)


def test_a_ramp_never_stands_higher_over_its_floor_than_where_it_left():
    """RULINGS 2026-10-09d (2).  Half a metre of fill at the contact; the
    floor falls at 7 % for 100 m and is level beyond.  At 5 % the ramp
    would open to 2.3 m of fill at the foot of the hillside; it follows
    the fall instead (7 %, inside the cap), 0.3 m over the floor as it
    stood at its first vertex, and comes down at 5 % on the level."""
    adj, floors, xs, end_of = _road(400.0)
    floors = {i: (-0.5 - 0.07 * xs[i] if xs[i] <= 100.0 else -7.5) for i in floors}
    d = _descend(adj, {0: 0.0}, floors, end_of)
    (r,) = d.ramps
    assert r["grade"] == DESIGN
    first = d.label[1] - floors[1]
    assert first == pytest.approx(0.5 + 0.02 * 10.0)
    for i in range(1, 11):
        assert d.label[i] - floors[i] == pytest.approx(first)
    assert d.label[11] == pytest.approx(d.label[10] - DESIGN * 10.0)
    assert max(z - floors[v] for v, z in d.label.items() if v in floors) == pytest.approx(first)
    assert r["length_m"] == pytest.approx(110.0)


def test_the_grade_arithmetic_is_the_tunnel_ramp_s():
    """One arithmetic for every unframed ramp (``geom/ramp_grade``)."""
    assert least_grade([(0.0, 9.0), (50.0, -5.0), (100.0, 7.3)]) == pytest.approx(0.073)
    assert least_grade([]) is None
    assert built_grade(0.02, DESIGN, CAP) == DESIGN
    assert built_grade(0.073, DESIGN, CAP) == 0.073
    assert built_grade(0.11, DESIGN, CAP) is None and built_grade(None, DESIGN, CAP) is None


# ── THE REACH SEED (§37 (10) / 27a (11)) IS THE SAME RAMP, IN STAGE 2 ───

def _seeded(run_m: float, drop: float):
    """A road ``run_m`` long, its targets ``drop`` under the solved level
    of the airside edge it ends beside: the stage-2 rewrite's targets."""
    import types

    from auto_patch_v2.constraints.road_ramp import (GEN, RULING, RULING_CEILING,
                                                     reach_seed_rewrite)
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.constraints import Band, ConstraintSet, Linear, Source

    law = Law.for_airport("ZZZZ")
    ss = [10.0 * k for k in range(int(run_m // 10) + 1)]
    if ss[-1] < run_m - 1e-9:
        ss.append(run_m)
    vs = list(range(10, 10 + len(ss)))
    lin = tuple(Linear(((v, 1.0),), 0.0, 0.0, Source(GEN, RULING, (f"vertex:{v}", "r")))
                for v in vs)
    bands = tuple(Band(v, None, 0.3, Source(GEN, RULING_CEILING, (f"vertex:{v}", "r")))
                  for v in vs)
    pm = types.SimpleNamespace(road_reach_seed={v: (1, 2, 0.5, s) for v, s in zip(vs, ss)},
                               road_terrace={}, road_between_levels={}, faces={}, vertices={})
    cs, rep = reach_seed_rewrite(pm, law, ConstraintSet(linears=lin, bands=bands),
                                 {1: drop, 2: drop})
    got = {int(r.source.inputs[0][7:]): r.hi for r in cs.linears}
    return [(s, got[v]) for v, s in zip(vs, ss)], rep, law


def test_the_reach_seed_descends_at_the_design_grade():
    prof, rep, law = _seeded(400.0, DROP)
    g = law.tables.emit.road_contact.ramp_grade
    assert g == DESIGN and rep["steepened"] == 0
    for s, z in prof:
        assert z == pytest.approx(max(0.0, DROP - g * s))


def test_the_reach_seed_steepens_only_where_its_run_is_short():
    prof, rep, _law = _seeded(DROP / 0.073, DROP)
    assert rep["steepened"] == 1
    for s, z in prof:
        assert z == pytest.approx(max(0.0, DROP - 0.073 * s))
    prof, rep, law = _seeded(80.0, DROP)                    # 12.5 %: the cap
    cap = law.tables.common.road_max_grade
    assert prof[-1][1] == pytest.approx(DROP - cap * 80.0) and rep["steepened"] == 1


def test_the_log_line_states_at_cap_and_over_cap_as_two_counts():
    """``ramps_over_cap`` (a contact with a run asking more than the cap)
    is not a subset of ``ramps_at_cap`` (a ramp whose steepest published
    run is at the cap): KCLT printed "9 at the cap 10 % of which 10 the
    cap does not bring down".  The line states them as two clauses."""
    rep = {"ramps": 38, "design": 0.05, "cap": 0.10, "ramps_at_design": 24,
           "ramps_steepened": 5, "ramps_at_cap": 9, "ramps_over_cap": 10,
           "ramp_total_m": 598.0, "ramp_longest_m": 103.0}
    line = descent_line(rep)
    assert "of which" not in line, line
    assert "9 at the cap 10 %;" in line, line
    assert "10 with a run the cap does not bring down)" in line, line
    assert line.startswith("ramps built: 38 of a lane width or more"), line
