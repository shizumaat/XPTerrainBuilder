"""#1896 (PAKT, Taquan Air's float docks): A BODY A GROUP'S ZERO WOULD HANG
OVER WATER KEEPS ITS OWN SEAT.

The pack authors one frame for the whole seaplane base: floats and their
deck at y 0 (the water), the shore pad 0..2.6 m and its buildings on top.
The drawn shore stands ~6 m over the sea, so the shore unit took 5.68 and
pulled the float-dock deck (``pakt-taquan-4``, joined by box proximity), its
guide piles (``pakt-taquan-5`` b2, a unit member) and the fittings on the
deck (b3, carried) 6.0-6.5 m over the water while the floats stayed on it.
Water is no ground (R12 amendment 1): ``anchor_rule.hangs_over_water`` is
the witness, read by the unit pass and by ``open_frame_seat.group_zero``;
the §16b census reads no water as ground either."""
from __future__ import annotations

import dataclasses
import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import open_frame_seat as OFS
from auto_patch_v2.airport import placement_census as PC
from auto_patch_v2.airport.placement_record import Body, Split

_SHORE_LON = -131.7000        # east of this is the shore at 6 m


def _surface(dock_islands=True):
    """The drawn mesh: sea at 0.00 west of the shore line, land at 6.0
    east of it; under the docks the mesh keeps ground at the water's level
    (-0.43, no water bit), as PAKT's object-footprint triangles do."""
    def surface(la, lo):
        if lo >= _SHORE_LON:
            return 6.0
        if dock_islands and 55.3574 <= la <= 55.3578:
            return -0.43
        return 0.0

    surface.water = lambda la, lo: lo < _SHORE_LON and not (
        dock_islands and 55.3574 <= la <= 55.3578)
    return surface


_DECK_FEET = ((55.3575, -131.7015, 0.0), (55.3577, -131.7012, 0.0))
_DECK_BOX = (55.3570, -131.7020, 55.3580, -131.7004)
_DECK_PTS = AR.box_points([_DECK_BOX])


def test_a_deck_lifted_clear_of_the_water_hangs():
    s = _surface()
    assert AR.water_level_under(_DECK_PTS, s) == 0.0
    assert AR.hangs_over_water(_DECK_FEET, s, 5.68, 0.5, _DECK_PTS)
    # at its own seat (the ground under it, -0.43) it does not
    assert not AR.hangs_over_water(_DECK_FEET, s, -0.43, 0.5, _DECK_PTS)


def test_piles_reaching_into_the_water_do_not_hang():
    """A pier on piles authored INTO the water reaches the surface at the
    group's zero: it stays with its group (RULINGS 2026-11-13r)."""
    piles = tuple((la, lo, -6.0) for la, lo, _y in _DECK_FEET)
    assert not AR.hangs_over_water(piles, _surface(), 5.68, 0.5, _DECK_PTS)


def test_a_body_on_land_or_with_no_water_under_it_does_not_hang():
    s = _surface()
    land = ((55.3575, -131.6990, 0.0),)
    assert not AR.hangs_over_water(land, s, 8.0, 0.5, AR.box_points(
        [(55.3574, -131.6995, 55.3576, -131.6985)]))
    no_bit = lambda la, lo: s(la, lo)                     # noqa: E731
    assert not AR.hangs_over_water(_DECK_FEET, no_bit, 5.68, 0.5, _DECK_PTS)
    assert not AR.hangs_over_water(_DECK_FEET, s, 5.68, 0.0, _DECK_PTS)


def _body(i, zero, ground, feet=(), merged="", pids=()):
    a = AR.Anchor(AR.OTHER, 55.3575, -131.7015, ground - zero, "own", ground,
                  offset=(0.0, ground - zero, 0.0))
    return Body(i, AR.OTHER, (i,), a, f"objects/dock__b{i}.obj", pids=pids,
                merged_into=merged, feet=feet, plan_box=_DECK_BOX)


def _record(deck_pids=(), left=""):
    m = types.SimpleNamespace(id="dsf:obj1", resource="objects/dock.obj", zero_y=0.0)
    deck = _body(0, -0.43, -0.43, feet=_DECK_FEET, pids=deck_pids)
    if left:
        deck = dataclasses.replace(deck, anchor=dataclasses.replace(deck.anchor, left_unit=left))
    rider = _body(1, -0.43, -0.43, merged="objects/dock__b0.obj")
    shed = _body(2, 5.0, 6.0, feet=((55.3575, -131.6990, 0.0),), pids=(3,))
    return m, Split(0, m.id, m.resource, "/x/" + m.resource, 55.3575, -131.7015,
                    0.0, (deck, rider, shed))


_PW = {q: ("fu:5:188", 5.68, "", "ground") for q in (1, 3)}
_ZEROS = {OFS.group_key("fu:5:188", "unit:5"): (5.68, 0.0)}
_BOXES = {"fu:5:188": [(55.3574, -131.7004, 55.3580, -131.6990)]}


def _zeros_of(rec):
    return [round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in rec.bodies]


def test_group_zero_keeps_a_box_joined_body_and_its_rider_on_the_water():
    """PAKT's deck: no part chained into the shore unit, joined by plan-box
    proximity alone (``body_root``'s last fallback)."""
    m, rec = _record()
    counts: dict = {}
    afloat: set = set()
    out = OFS.group_zero(rec, m, _PW, _ZEROS, counts, "unit:5", root_boxes=_BOXES,
                         surface=_surface(), gap_m=0.5, afloat=afloat)
    assert _zeros_of(out) == [-0.43, -0.43, 5.68]   # the shed on land still moves
    assert counts["group_zero_kept_over_water"] == 2
    assert afloat == {"objects/dock__b0.obj", "objects/dock__b1.obj"}
    # without the water reading the group takes them all (the old reading)
    old = OFS.group_zero(rec, m, _PW, _ZEROS, {}, "unit:5", root_boxes=_BOXES)
    assert _zeros_of(old) == [5.68, 5.68, 5.68]


def test_group_zero_keeps_a_body_the_unit_pass_let_go_over_water():
    m, rec = _record(deck_pids=(1,), left="fu:5:188")
    out = OFS.group_zero(rec, m, _PW, _ZEROS, {}, "unit:5", root_boxes=_BOXES,
                         surface=_surface(), gap_m=0.5, afloat=set())
    assert _zeros_of(out) == [-0.43, -0.43, 5.68]


def test_a_body_chained_into_the_unit_is_never_asked():
    """A bridge's deck piece over a canal is chained into its bridge's unit:
    the water reading never moves it off the unit's zero."""
    m, rec = _record(deck_pids=(1,))
    out = OFS.group_zero(rec, m, _PW, _ZEROS, {}, "unit:5", root_boxes=_BOXES,
                         surface=_surface(), gap_m=0.5, afloat=set())
    assert _zeros_of(out) == [5.68, 5.68, 5.68]


def test_land_anywhere_under_the_plan_is_ground():
    """SBRJ's Arsenal: four quay-wall feet at the water, the island 12 m
    high under the rest of its plan — it does not hang."""
    s = _surface()
    island = (55.3570, -131.7020, 55.3580, -131.6995)    # reaches the 6 m shore
    assert not AR.hangs_over_water(_DECK_FEET, s, 5.68, 0.5, AR.box_points([island]))


def test_the_census_reads_no_water_as_ground():
    """A wharf deck carried at the shore's zero over the sea: its own
    ground is the water, so §16b's float bar does not read it."""
    s = _surface(dock_islands=False)
    wharf = {"new_resource": "objects/wharf__b0.obj", "merged_into": "pad",
             "surface_z": 6.0, "y_zero": 0.3,
             "geom_pts": [(55.3575, -131.7015), (55.3576, -131.7010)]}
    shore = {"new_resource": "objects/shed__b0.obj", "merged_into": "pad",
             "surface_z": 6.0, "y_zero": -2.0,
             "geom_pts": [(55.3575, -131.6990), (55.3576, -131.6985)]}
    c = PC.census_v16b([{"bodies": [wharf, shore]}], s, split_tol_m=0.3)
    assert c["over_water"] == 1 and c["bodies_read"] == 1
    assert c["carried_own_ground_gt"] == 1           # the shed: +2.0 m
    bare = lambda la, lo: s(la, lo)                   # noqa: E731
    c0 = PC.census_v16b([{"bodies": [wharf, shore]}], bare, split_tol_m=0.3)
    assert c0["over_water"] == 0 and c0["carried_own_ground_gt"] == 2
