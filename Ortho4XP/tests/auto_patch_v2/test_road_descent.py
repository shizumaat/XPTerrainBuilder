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

from auto_patch_v2.airport.road_descent import descend, envelope
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
        assert d.label[i] == pytest.approx(DROP - DESIGN * x)
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
    old, walked, _s = envelope(adj, mouths, CAP)
    assert d.label == pytest.approx(old) and d.walked == pytest.approx(walked)


def test_the_grade_arithmetic_is_the_tunnel_ramp_s():
    """One arithmetic for every unframed ramp (``geom/ramp_grade``)."""
    assert least_grade([(0.0, 9.0), (50.0, -5.0), (100.0, 7.3)]) == pytest.approx(0.073)
    assert least_grade([]) is None
    assert built_grade(0.02, DESIGN, CAP) == DESIGN
    assert built_grade(0.073, DESIGN, CAP) == 0.073
    assert built_grade(0.11, DESIGN, CAP) is None and built_grade(None, DESIGN, CAP) is None
