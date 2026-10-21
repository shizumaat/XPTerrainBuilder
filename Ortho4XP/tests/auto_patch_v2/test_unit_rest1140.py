"""#1140 (KATL east terminal): A DECK OF A STEPPED UNIT RESTS ON THE UNIT.
2026-10-19aq lets a body whose own ground is far below its unit's datum
leave the unit -- read on its lowest vertices as if they stood on the
ground.  A garage deck's lowest vertices stand on the unit's own lower
structure, whose feet are on the ground at the datum: it has no ground of
its own and stays with the unit (``footprint_unit._rests_on_unit``).  A
unit seated over ground far under its own floor (#721, HECA ``T3_14``)
witnesses nothing, and its body still leaves."""
from __future__ import annotations

from test_v2connector import _blk, _cand, _lat, _PMember, _PPart, _PPlan, _PUnit, _Staged


def _bind(y_floor: float):
    """Datum 20.0 (a deck member); the lower structure's feet at
    ``y_floor`` and the garage deck's at y -1, both over ground 7.0."""
    from auto_patch_v2.airport import footprint_unit as FU
    box_a = [_blk(_lat(0), _lat(40))]
    box_b = [_blk(_lat(40), _lat(60))]
    a = _PMember("objects/deck.obj", [_PPart(1, box_a[0])], deck_datum_z=20.0)
    b = _PMember("objects/structure.obj", [_PPart(2, box_b[0])])
    c = _PMember("objects/garage_deck.obj", [_PPart(3, box_b[0])])
    plan = _PPlan([_PUnit("unit:0", [a, b, c])])

    def surface(la, lo):
        return 7.0 if la > _lat(40.5) else 20.0

    counts: dict = {}
    pw, _seats = FU.plan_wide_seats(plan, surface, (), 0.5, 0.0, counts, 200.0)
    cands = [_cand(0, box_a, 20.0, {1}), _cand(1, box_b, 7.0, {2}),
             _cand(2, box_b, 7.0, {3})]
    st = [_Staged(0, a.resource, [(q[0], q[1], 0.0) for q in box_a]),
          _Staged(1, b.resource, [(_lat(45), -2.9995, y_floor),
                                  (_lat(55), -2.9995, y_floor)]),
          _Staged(2, c.resource, [(_lat(50), -2.9995, -1.0)])]
    FU.bind_footprint_units(cands, st, surface, (), counts, unit_id="unit:0",
                            touch_m=0.5, visual_m=0.5, connector_span_m=200.0,
                            plan_wide=pw)
    return cands, counts


def test_a_deck_over_the_units_floor_stays_with_the_unit():
    cands, counts = _bind(y_floor=-13.0)
    assert counts.get("unit_members_kept_resting_on_unit") == 1, counts
    assert not counts.get("unit_members_left_far_below")
    d = cands[2].anchor
    assert d.unit_seat and not d.left_unit
    assert abs((d.surface_z - d.y_zero) - 20.0) < 1e-6      # the unit's zero


def test_a_unit_seated_over_ground_far_under_its_floor_witnesses_nothing():
    # the structure's feet at y -1.85 stand 11 m over the ground at 7.0:
    # the unit there is seated too high, not a storey on its ground (#721)
    cands, counts = _bind(y_floor=-1.85)
    assert not counts.get("unit_members_kept_resting_on_unit")
    assert counts.get("unit_members_left_far_below") == 2, counts
    assert cands[2].anchor.left_unit
