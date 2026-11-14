"""#2090: a KEPT bridge's deck is seated where the pack stage predicted it.

KDEN 1.0.528: the Mid / Parking bridges' decks (all-deck frames the witness
holds, their ends graded up to the predicted seat) carried a graded-face
``deck_datum_z`` — the road they span — so ``anchor_rule.datum_of`` gave them
no datum and they took their own ground, 4.7-8.5 m under their ends; the
outer train bridge was seated by its crown (y 16) and its high end stood 8 m
under its ground.  The bridge class decides the datum in ONE place
(``rebake_plan.with_kept``) and the seat reads the deck top at each end
(``deck_riders.with_end_tops``) at both stages.
"""
from __future__ import annotations

import dataclasses as dc
import types

import pytest
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import deck_riders as DR
from auto_patch_v2.airport import placement_body as PB
from auto_patch_v2.airport.bridge_approach import approach_seat
from auto_patch_v2.airport.rebake_plan import with_kept
from auto_patch_v2.model.rebake import Member

LA, LO = 36.0, -86.0
STEP = 2.0
M = 1.0 / 111_000.0
#: a 40 x 10 m deck along east, centred on (LA, LO)
RING = ((LA - 5 * M, LO - 0.00025), (LA - 5 * M, LO + 0.00025),
        (LA + 5 * M, LO + 0.00025), (LA + 5 * M, LO - 0.00025))


def _member(**kw) -> Member:
    base = dict(id="dsf:obj1", resource="b.obj", authored_path="", live_path="",
                heading_deg=0.0, deck_ring=RING, deck_top_y=0.1, deck_datum_z=1630.8,
                deck_kind="flag")
    base.update(kw)
    return Member(**base)


def _route(m: Member, graded_sides=(0, 1)):
    mids = [((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0) for a, b in m.deck_ends]
    return {"mode": "kept", "route_mids": [list(q) for q in mids],
            "graded": [list(mids[k]) for k in graded_sides], "zero": 1639.14}


def test_a_kept_deck_over_a_graded_face_gets_its_end_lines_and_no_face_datum():
    counts: dict = {}
    m = with_kept(_member(), {"mode": "kept", "route_mids": [], "graded": []}, counts, STEP)
    assert m.deck_datum_z is None and m.deck_ends is not None and m.deck_end_stations
    assert counts["kept_deck_over_graded_face"] == 1
    assert "datum cleared, #2090" in m.deck_evidence[-1]
    # the object stage now reads the deck-top datum with those end lines
    d = AR.datum_of(m, abutment_step_m=STEP, free_standing=True)
    assert d is not None and d.label == "deck top" and len(d.ends) == 2 and d.zero is None


def test_every_end_graded_seats_the_deck_at_its_predicted_zero():
    counts: dict = {}
    m = with_kept(_member(), {"mode": "kept", "route_mids": [], "graded": []}, counts, STEP)
    m = with_kept(m, _route(m), counts, STEP)
    assert m.deck_end_graded == (True, True) and m.anchor_zero == pytest.approx(1639.14)
    d = AR.datum_of(m, abutment_step_m=STEP, free_standing=True)
    assert d.zero == pytest.approx(1639.14)

    # the ends graded up to the deck (1639.24); the anchor, ON the deck, reads
    # the road it spans 8 m down — 22p's road-under never seats it there
    def surface(lat, lon):
        return 1639.24 if abs(lon - LO) > 0.0002 else 1630.8
    seat = approach_seat(d, surface, origin=(LA, LO), authored_agl_m=0.0)
    assert seat.zero == pytest.approx(1639.14) and "predicted" in seat.reason
    # the pack stage's prediction on the same ground (no flag) agrees within the flush
    pred = approach_seat(dc.replace(d, graded=(), zero=None), surface, origin=(LA, LO),
                         authored_agl_m=0.0)
    assert abs(pred.zero - seat.zero) <= 0.11


def test_a_kept_deck_with_one_graded_end_seats_flush_at_the_other():
    counts: dict = {}
    m = with_kept(_member(), {"mode": "kept", "route_mids": [], "graded": []}, counts, STEP)
    m = with_kept(m, _route(m, (1,)), counts, STEP)
    d = AR.datum_of(m, abutment_step_m=STEP, free_standing=True)

    def surface(lat, lon):
        return 1640.0 if lon < LO else 1645.0     # end b raised (graded), a governs
    seat = approach_seat(d, surface, origin=None, authored_agl_m=0.0)
    assert seat.zero == pytest.approx(1640.0 - 0.1)


def test_a_plated_or_unread_member_keeps_its_face_datum():
    counts: dict = {}
    m = with_kept(_member(plate_kind="overpass"), {"mode": "kept", "graded": []}, counts, STEP)
    assert m.deck_datum_z == 1630.8 and not counts


def _obj(tmp_path, rows):
    p = tmp_path / "deck.obj"
    vt = "\n".join(f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in rows)
    p.write_text(f"I\n800\nOBJ\n\nPOINT_COUNTS {len(rows)} 0 0 3\n{vt}\nIDX10 0 1 2\nTRIS 0 3\n")
    return str(p)


def test_end_tops_read_the_hard_deck_not_its_parapet(tmp_path):
    # a level deck at y -0.10 with a parapet at +0.75 along its end (KDEN's
    # Parking_Hill_Bridge): the deck top is the hard deck's
    p = tmp_path / "hd.obj"
    rows = [(-20.0, -0.1, -5.0), (-20.0, -0.1, 5.0), (20.0, -0.1, 0.0),
            (-20.0, 0.75, -5.2), (-20.0, 0.75, 4.8), (20.0, 0.75, 0.2)]
    vt = "\n".join(f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in rows)
    p.write_text(f"I\n800\nOBJ\n\nPOINT_COUNTS 6 0 0 6\n{vt}\nIDX10 0 1 2 3 4 5\n"
                 "ATTR_hard_deck concrete\nTRIS 0 3\nATTR_no_hard\nTRIS 3 3\n")
    ends = (((LA - 5 * M, LO - 0.00022), (LA + 5 * M, LO - 0.00022)),
            ((LA - 5 * M, LO + 0.00022), (LA + 5 * M, LO + 0.00022)))
    deck = types.SimpleNamespace(authored_path=str(p), heading_deg=0.0)
    assert DR.end_tops(deck, ends, (LA, LO)) == pytest.approx((-0.1, -0.1))


def test_a_deck_on_a_grade_is_seated_by_its_end_tops_not_its_crown(tmp_path, monkeypatch):
    # along east: y 8.0 at the west end, 16.0 at the crown, 1.0 at the east end
    path = _obj(tmp_path, [(-20.0, 8.0, 0.0), (-5.0, 16.0, 0.0), (20.0, 1.0, 0.0)])
    ends = (((LA - 5 * M, LO - 0.00025), (LA + 5 * M, LO - 0.00025)),
            ((LA - 5 * M, LO + 0.00025), (LA + 5 * M, LO + 0.00025)))
    m = types.SimpleNamespace(deck_kind="flag", deck_top_y=16.0, deck_datum_z=None,
                              deck_end_stations=(), deck_ends=ends, parts=(),
                              plate_y=None, plate_kind="", authored_path=path,
                              heading_deg=0.0, deck_end_graded=(), anchor_zero=None)
    u = types.SimpleNamespace(anchor=(LA, LO), members=(m,))
    monkeypatch.setattr(PB._pf, "frame_is_bridge", lambda _u: True)
    d = PB._member_datum(m, u, None, STEP, 0.0, 0.3)
    assert d.tops == pytest.approx((8.0, 1.0))

    def surface(lat, lon):
        return 1626.7 if lon < LO else 1611.5
    seat = approach_seat(d, surface, origin=(LA, LO), authored_agl_m=0.0, tops=d.tops)
    # the west end (ground - top the highest) flush; never 8 m under its ground
    assert seat.zero + 8.0 == pytest.approx(1626.7)
    # a free deck's published tops win over the file
    free = types.SimpleNamespace(deck_end_tops=(3.0, 2.0), authored_path=path, heading_deg=0.0)
    assert DR.with_end_tops(dc.replace(d, tops=()), free, (LA, LO)).tops == (3.0, 2.0)
