"""Owner RULINGS 2026-10-22b..e (#1214, KMCI beta 3): an object group
seats as ONE unit on our ground, and a bridge seats with its deck flush
with the terrain at its ends.

(b) a frame the law re-seats by its FEET keeps no authored ``OBJECT_AGL``
    lift — every body of it moves together (KMCI's terminal, +8.5 m AGL,
    stood 8.5 m over its own apron); a frame with no footed member keeps
    the lift (14g (1)'s dock heads);
(d) a FREE-STANDING deck (every member of its frame a deck) takes the
    deck-top datum at its END LINES even with feet of its own, and reads
    its stations off its ``deck_ends`` when the plan stamped none; a deck
    sharing its frame with a building is that unit's viaduct (10-03e) and
    is unchanged.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import placement_family as PF
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.airport.placement_record import Body, Split

LIFT = 8.5
TOL = 0.05


def _row(kind="OBJECT_AGL", elevation=LIFT, path="objects/terminal.obj"):
    return types.SimpleNamespace(def_path=path, lat=40.0, lon=-3.0,
                                 heading_deg=0.0, kind=kind, elevation=elevation)


def _body(i, y_off=0.0, feet=((40.0, -3.0, 0.0),), reason="§16g unit fu:1@pad"):
    a = AR.Anchor(AR.BUILDING, 40.0, -3.0, y_off, reason, 100.0,
                  offset=(0.0, y_off, 0.0))
    return Body(i, AR.BUILDING, (i,), a, f"objects/terminal__b{i}.obj", feet=feet)


def _split(*bodies):
    return Split(0, "dsf:obj0", "objects/terminal.obj", "/x/objects/terminal.obj",
                 40.0, -3.0, 0.0, tuple(bodies))


def _flat(la, lo):
    return 100.0


# ── (b) the lift of a re-seated footed frame ────────────────────────────

def test_a_re_seated_footed_frame_keeps_no_lift():
    """The terminal's bodies are seated on the apron pad by the unit law
    (their zero 2 m off the authored row's): the author's +8.5 m would
    float all of them, so every body of the placement drops it."""
    rec, landed = PP._lifted(_split(_body(0, 2.0), _body(1, 2.0)), [_row()],
                             frozenset(), _flat, TOL, footed_frame=True)
    assert landed is False
    assert all(b.lift_m == 0.0 for b in rec.bodies)


def test_a_frame_with_no_footed_member_keeps_its_lift():
    """14g (1) stands where nothing reads our ground: a dock head split
    off its row keeps the author's lift."""
    rec, landed = PP._lifted(_split(_body(0, 2.0, feet=())), [_row()],
                             frozenset(), _flat, TOL, footed_frame=False)
    assert landed is False and rec.bodies[0].lift_m == LIFT


def test_a_placement_that_lands_on_its_authored_seat_keeps_its_lift():
    """14g (3) is untouched: a placement every body of which lands where
    the authored row draws it is KEPT as authored, lift and all."""
    rec, landed = PP._lifted(_split(_body(0), _body(1)), [_row()],
                             frozenset(), _flat, TOL, footed_frame=True)
    assert landed is True and all(b.lift_m == LIFT for b in rec.bodies)


def test_no_row_no_lift_reading():
    rec, landed = PP._lifted(_split(_body(0, 2.0)), None, frozenset(), _flat,
                             TOL, footed_frame=True)
    assert landed is None and rec.bodies[0].lift_m == 0.0


# ── (d) a free-standing bridge seats on its deck ends ───────────────────

def _deck(**kw):
    base = dict(plate_y=None, plate_stations=(), plate_clearance_m=0.0,
                deck_top_y=7.7, deck_datum_z=None, deck_kind="signature",
                deck_end_stations=(),
                deck_ends=(((40.0, -3.0), (40.0, -3.0001)),
                           ((40.001, -3.0), (40.001, -3.0001))),
                parts=(types.SimpleNamespace(feet=((40.0005, -3.0, -6.0),)),))
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_a_free_standing_deck_with_piers_takes_the_deck_top_datum():
    """The deck top lands on the ground at its END LINES whatever its
    piers reach — they may sink or float (10-22d)."""
    d = AR.datum_of(_deck(), abutment_step_m=5.0, free_standing=True)
    assert d is not None and d.label == "deck top" and d.y == 7.7
    assert len(d.stations) >= 4 and len(d.ends) == 2

    def ground(la, lo):
        return 290.0 if la < 40.0005 else 290.4
    g = AR.BodyGeometry(((40.0005, -3.0, -6.0, ((40.0005, -3.0, -6.0),)),),
                        40.0, -3.0)
    a = AR.anchor_for(AR.DECK, g, ground, tol_m=0.3, datum=d)
    assert a.datum and a.y_zero == 7.7 and a.surface_z in (290.0, 290.4)
    # the pier foot at y -6 is NOT what seats it: it stands 13.7 m under
    # the deck top, wherever the ground under it is
    assert "deck top datum" in a.reason


def test_a_deck_in_a_buildings_frame_keeps_the_old_rule():
    """10-03e: a deck that shares its frame with a building is that
    unit's viaduct; with feet of its own and no free-standing frame it
    reads no datum, exactly as before."""
    assert AR.datum_of(_deck(), abutment_step_m=5.0) is None
    st = ((40.0, -3.0), (40.001, -3.0))
    assert AR.datum_of(_deck(deck_end_stations=st)) is None
    # a flyover over an emitted deck face stays the §49 reading's
    assert AR.datum_of(_deck(deck_datum_z=3.9), abutment_step_m=5.0,
                       free_standing=True) is None
    # a candidate plate (no spanning evidence) is no deck at all
    assert AR.datum_of(_deck(deck_kind="candidate"), abutment_step_m=5.0,
                       free_standing=True) is None


def test_free_standing_is_every_member_a_deck():
    deck = types.SimpleNamespace(deck_kind="signature")
    flag = types.SimpleNamespace(deck_kind="flag")
    hall = types.SimpleNamespace(deck_kind="")
    assert PF.frame_is_bridge(types.SimpleNamespace(members=(deck, flag)))
    assert not PF.frame_is_bridge(types.SimpleNamespace(members=(deck, hall)))
    assert not PF.frame_is_bridge(types.SimpleNamespace(members=()))
