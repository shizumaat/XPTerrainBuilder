"""Owner RULINGS 2026-10-19aq (#721): A BODY WHOSE OWN GROUND IS FAR BELOW
ITS UNIT'S DATUM LEAVES THE UNIT.  "Far" is the cockpit's visual bar
(``[cockpit] visual_m``): the HECA T3_14 tower and its door rode the
cluster-pad unit at 101.85 m, 8.1 m over their own ground.  A member whose
own ground stands within the bar stays; a piece the leaver carries rides
the leaver, never the unit it left."""
from __future__ import annotations

import dataclasses as _dc
import types

import auto_patch_v2.airport.anchor_rule as AR

from test_v2connector import (_blk, _cand, _lat, _PMember, _PPart, _PPlan,
                              _PUnit, _Staged)


def _bind(ground_b: float):
    from auto_patch_v2.airport import footprint_unit as FU
    box_a = [_blk(_lat(0), _lat(40))]
    box_b = [_blk(_lat(40), _lat(60))]
    box_c = [_blk(_lat(-20), _lat(0))]
    a = _PMember("objects/deck.obj", [_PPart(1, box_a[0])], deck_datum_z=20.0)
    b = _PMember("objects/tower.obj", [_PPart(2, box_b[0])])
    c = _PMember("objects/wing.obj", [_PPart(3, box_c[0])])
    plan = _PPlan([_PUnit("unit:0", [a, b, c])])

    def surface(la, lo):
        if la > _lat(40.5):
            return ground_b
        return 19.8 if la < _lat(-0.5) else 20.0

    counts: dict = {}
    pw, _seats = FU.plan_wide_seats(plan, surface, (), 0.5, 0.0, counts, 200.0)
    cands = [_cand(0, box_a, 20.0, {1}), _cand(1, box_b, ground_b, {2}),
             _cand(2, box_c, 19.8, {3})]
    st = [_Staged(0, a.resource, [(q[0], q[1], 0.0) for q in box_a]),
          _Staged(1, b.resource, [(_lat(50), -2.9995, 0.0)]),
          _Staged(2, c.resource, [(_lat(-10), -2.9995, 0.0)])]
    FU.bind_footprint_units(cands, st, surface, (), counts, unit_id="unit:0",
                            touch_m=0.5, visual_m=0.5, connector_span_m=200.0,
                            plan_wide=pw)
    return cands, counts


def test_a_body_far_below_the_datum_leaves_the_unit():
    cands, counts = _bind(ground_b=12.0)
    assert counts.get("unit_members_left_far_below") == 1, counts
    b = cands[1].anchor
    assert not b.unit_seat and b.left_unit
    assert b.surface_z == 12.0          # the seat §16c gave it, on its ground
    c = cands[2].anchor                 # 0.2 m under the datum: it stays
    assert c.unit_seat and abs((c.surface_z - c.y_zero) - 20.0) < 1e-6


def test_a_body_within_the_visual_bar_stays():
    cands, counts = _bind(ground_b=19.6)
    assert not counts.get("unit_members_left_far_below")
    assert cands[1].anchor.unit_seat and not cands[1].anchor.left_unit


def test_a_piece_rides_the_carrier_that_left_its_unit():
    from auto_patch_v2.airport.footprint_carry import contents_seat
    left = types.SimpleNamespace(
        anchor=AR.Anchor(AR.BUILDING, 0.0, 0.0, 0.0, "r", 12.0,
                         left_unit="fu:0"), resource="objects/tower.obj")
    pw = {7: ("fu:0", 20.0, "deck.obj", "deck")}
    over = [(left, "rests on it")]
    ix = {"fu:0": ((0.0, 0.0, 1.0, 1.0), [], 20.0, "deck.obj", "deck")}
    kept, uc = contents_seat(over, {7}, None, pw, ix, tol_m=0.3)
    assert uc is None and kept == over


def test_one_members_leavers_that_touch_stand_together_on_their_own_ground():
    from auto_patch_v2.airport import footprint_unit as FU
    box_a = [_blk(_lat(0), _lat(40))]
    box_b = [_blk(_lat(40), _lat(60))]
    box_d = [_blk(_lat(60), _lat(80))]
    a = _PMember("objects/deck.obj", [_PPart(1, box_a[0])], deck_datum_z=20.0)
    b = _PMember("objects/tower.obj", [_PPart(2, box_b[0]),
                                       _PPart(4, box_d[0])])
    plan = _PPlan([_PUnit("unit:0", [a, b])])

    def surface(la, lo):
        if la > _lat(60.5):
            return 11.0
        return 12.0 if la > _lat(40.5) else 20.0

    counts: dict = {}
    pw, _seats = FU.plan_wide_seats(plan, surface, (), 0.5, 0.0, counts, 200.0)
    cands = [_cand(0, box_a, 20.0, {1}), _cand(1, box_b, 12.0, {2}),
             _dc.replace(_cand(1, box_d, 11.0, {4}), group=1)]
    sb = _Staged(1, b.resource, [(_lat(50), -2.9995, 0.0)])
    sb.raw.append(([], AR.BUILDING, AR.Anchor(AR.BUILDING, _lat(70), -2.9995,
                                              0.0, "r", 0.0),
                   ((_lat(70), -2.9995, 0.0),), False, (), (), None))
    sb.groups = [[0], [1]]
    sb.ground_off = [0.0, 0.0]
    st = [_Staged(0, a.resource, [(q[0], q[1], 0.0) for q in box_a]), sb]
    FU.bind_footprint_units(cands, st, surface, (), counts, unit_id="unit:0",
                            touch_m=0.5, visual_m=0.5, connector_span_m=200.0,
                            plan_wide=pw)
    assert counts.get("unit_members_left_far_below") == 2, counts
    zb = cands[1].anchor.surface_z - cands[1].anchor.y_zero
    zd = cands[2].anchor.surface_z - cands[2].anchor.y_zero
    assert abs(zb - zd) < 1e-6 and 11.0 <= zb <= 12.0
    assert cands[1].anchor.left_unit and cands[2].anchor.left_unit
