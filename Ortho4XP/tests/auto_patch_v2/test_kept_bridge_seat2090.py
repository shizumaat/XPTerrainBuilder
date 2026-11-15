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


def _obj(tmp_path, rows, hard: bool = True):
    p = tmp_path / ("deck.obj" if hard else "soft.obj")
    vt = "\n".join(f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in rows)
    attr = "ATTR_hard_deck concrete\n" if hard else ""
    p.write_text(f"I\n800\nOBJ\n\nPOINT_COUNTS {len(rows)} 0 0 3\n{vt}\nIDX10 0 1 2\n"
                 f"{attr}TRIS 0 3\n")
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


def test_a_deck_with_no_hard_deck_keeps_its_datum_y_at_both_ends(tmp_path, monkeypatch):
    # l2090d (LEMG bridgeDrei): no vertex of a deck without a hard deck is its
    # road by declaration — a railing at +1.80, a road at +0.30 running on
    # past the ring as the object's own approach ramps.  Seated as before
    # #2090 (``datum.y`` at both ends); a riding frame reads any vertex.
    path = _obj(tmp_path, [(-20.0, 8.0, 0.0), (-5.0, 16.0, 0.0), (20.0, 1.0, 0.0)], hard=False)
    ends = (((LA - 5 * M, LO - 0.00025), (LA + 5 * M, LO - 0.00025)),
            ((LA - 5 * M, LO + 0.00025), (LA + 5 * M, LO + 0.00025)))
    m = types.SimpleNamespace(deck_kind="signature", deck_top_y=16.0, deck_datum_z=None,
                              deck_end_stations=(), deck_ends=ends, parts=(),
                              plate_y=None, plate_kind="", authored_path=path,
                              heading_deg=0.0, deck_end_graded=(), anchor_zero=None)
    u = types.SimpleNamespace(anchor=(LA, LO), members=(m,))
    monkeypatch.setattr(PB._pf, "frame_is_bridge", lambda _u: True)
    assert PB._member_datum(m, u, None, STEP, 0.0, 0.3).tops == ()
    assert DR.end_tops(m, ends, (LA, LO), hard_only=True) is None
    assert DR.frame_datum(m, (LA, LO), abutment_step_m=STEP, free_standing=True
                          ).tops == pytest.approx((8.0, 1.0))


# ── #2090 spec B1 / B3 / B6: a deck end joined to an AGP follower's floor ──

class _Floors:
    """A ``DeckFloors`` stand-in: one follower with floors at ``ys``."""

    def __init__(self, ys, zp=1629.71):
        from auto_patch_v2.law import Law
        from auto_patch_v2.model.agp_group import AgpGroup, AgpMember
        self.agp = Law.load().tables.structures.agp
        fol = AgpMember("dsf:obj9", 9, "J.agp", (0.0, 0.0), (LA, LO), 466.0, -9.0)
        gov = AgpMember("dsf:obj8", 8, "A.agp", (0.0, 600.0), (LA, LO), 0.0, 0.0)
        self.groups = (AgpGroup("agp:dsf:obj8", (gov, fol), (), "dsf:obj8", zp + 9.0, "",
                                frozenset({"dsf:obj8"})),)
        self._ys = list(ys)
        self.to_ll = lambda x, y: (LA, LO)

    def near(self, stations):
        return [(self.groups[0], "dsf:obj9")]

    def levels_under(self, row, stations):
        return list(self._ys)


def _joins(ys, seat=1631.25, top=-0.10):
    from auto_patch_v2.airport.agp_deck_join import end_joins
    return end_joins(_Floors(ys), stack_id="stack:kept:dsf:obj1", object_id="dsf:obj1",
                     ends=[("b", ((0.0, 0.0), (10.0, 0.0)), top)], seat_zero=seat)


def test_b1_a_deck_end_over_three_floors_joins_the_nearest():
    (j,), notes = _joins([0.15, 3.45, 6.75])
    assert j.y_floor == 3.45 and j.d == pytest.approx(1629.71 + 3.45 - 1631.15)
    # the ground slab 0.15 is no connector floor: the next floor is 6.75
    assert j.d_next == pytest.approx(1629.71 + 6.75 - 1631.15)
    assert "JOINED" in notes[-1]


def test_b1_a_margin_under_one_metre_refuses():
    # floors 3.45 and 4.05 under the end: their |D| differ by 0.6 m
    joins, notes = _joins([3.45, 4.05], seat=1632.0)
    assert joins == [] and "deck_join_margin_m" in notes[-1]
    # beyond reach: no join
    joins, notes = _joins([13.85], seat=1631.25)
    assert joins == [] and "deck_join_reach_m" in notes[-1]


def test_b6_with_kept_returns_the_zero_for_graded_and_joined_ends():
    counts: dict = {}
    m = with_kept(_member(), {"mode": "kept", "route_mids": [], "graded": []}, counts, STEP)
    rec = _route(m, graded_sides=(0,))
    rec["joined"] = [rec["route_mids"][1]]
    m = with_kept(m, rec, counts, STEP)
    assert m.deck_end_graded == (True, True) and m.anchor_zero == pytest.approx(1639.14)
    d = AR.datum_of(m, abutment_step_m=STEP, free_standing=True)
    assert d.zero == pytest.approx(1639.14)


def test_b3_a_joined_stack_is_published_with_its_final_zero():
    from auto_patch_v2.constraints.agp_level import stack_zero
    from auto_patch_v2.model.deck_stack import KEPT, DeckStack, StackEnd
    from auto_patch_v2.pipeline.rebake_inputs import _kept_published
    ends = (StackEnd("dsf:obj1", "a", ((0.0, 0.0), (0.0, 10.0)), 0.05, (-1.0, 0.0), 1631.3,
                     0.03, "flush", ""),
            StackEnd("dsf:obj1", "b", ((40.0, 0.0), (40.0, 10.0)), -0.10, (1.0, 0.0), 1627.6,
                     5.6, "joined", "joined"))
    from auto_patch_v2.model.deck_stack import StackDeck
    deck = StackDeck("dsf:obj1", "b.obj", 0, ((0, 0), (40, 0), (40, 10), (0, 10)), 1, (), (),
                     ends[0].stations, ends[1].stations, 0.05, -0.10)
    st = DeckStack("stack:kept:dsf:obj1", "", "", (("dsf:obj1", "b.obj"),), 1633.26, 0.0, (),
                   0.0, 0.0, (), (), (), (), (deck,), kind=KEPT, ends=ends,
                   datum_group="agp:dsf:obj8")
    groups = _Floors([3.45]).groups
    rep = {"groups": {"agp:dsf:obj8": {"delta": -0.21, "z_gov": 1638.5, "unread": False}}}
    assert stack_zero(st, groups, rep) == pytest.approx(1633.05)
    fb = types.SimpleNamespace(deck_ids=lambda: ("dsf:obj1",))
    frame = types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (LA + y * M, LO)))
    ap = types.SimpleNamespace(kept_bridges=(fb,), deck_stacks=(st,), frame=frame,
                               agp_groups=groups)
    pm = types.SimpleNamespace(bridge_stacks=(st,), agp_groups=groups)
    rec = _kept_published(ap, pm, rep)["dsf:obj1"]
    assert rec["graded"] == [] and len(rec["joined"]) == 1
    assert rec["zero"] == pytest.approx(1633.05)


def test_b2_an_unmapped_deck_is_read_along_its_own_axis(monkeypatch):
    from auto_patch_v2.planar import free_bridge as FB
    from shapely.geometry import Polygon
    d = types.SimpleNamespace(id="dsf:obj5", hard_deck=Polygon([(0, 0), (42, 0), (42, 14),
                                                                (0, 14)]),
                              deck_top_z=1631.4, anchor_z=1631.3, agl_m=0.0, path="g.obj",
                              heading_deg=0.0, footprint=None, xy=(21.0, 7.0))
    monkeypatch.setattr(FB, "_ring", lambda o: o.hard_deck)   # the plan ring
    a, b = FB._axis_ends(d)
    assert {round(p[0]) for p in a.stations} | {round(p[0]) for p in b.stations} == {0, 42}
    assert a.land and b.land and a.top == pytest.approx(0.1)
    assert sorted((round(a.out[0]), round(b.out[0]))) == [-1, 1]
    # no governed AGP group: no candidate
    assert FB._join_witness([d], [d], types.SimpleNamespace(agp_groups=()), None, None) \
        == ([], [])
