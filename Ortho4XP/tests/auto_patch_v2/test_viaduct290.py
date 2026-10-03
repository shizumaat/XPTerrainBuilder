"""Lane ``viaduct290`` (issue #290; owner RULINGS 2026-10-03e).

A deck that belongs to a terminal unit — parts of a §16g plan-wide unit,
authored in members sharing the deck's placement origin and heading,
stand inside the deck's model footprint, and that unit holds parts
outside it too — rides the UNIT's level with every piece of its viaduct
(deck, piers, sidewalks, railings, kerb segments) as ONE rigid unit.  A
free-standing deck keeps 2026-09-30g (3).  Hermetic.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import bridge_family as BF
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import placement_carrier as PC

U_ZERO = 99.29
ORIGIN = (30.112118049, 31.412026019)
UID = "fu:40:120/b4"


def _ramp() -> BF.DeckPrint:
    """A deck 100 m long: y 0 at lat 40.0 (the landing), 10 at 40.0009."""
    a, b = (40.0, -3.0), (40.0, -2.9998)
    c, d = (40.0009, -2.9998), (40.0009, -3.0)
    p = BF.DeckPrint(key="T23/T3_road.obj", unit=0, member=0, under_y=0.0,
                     box=(40.0, -3.0, 40.0009, -2.9998),
                     tris=((a, b, c), (a, c, d)),
                     ys=((0.0, 0.0, 10.0), (0.0, 10.0, 10.0)))
    p.index()
    return p


def _part(pid, lat, lon, base_y=0.0, feet=()):
    return types.SimpleNamespace(pid=pid, lat=lat, lon=lon, base_y=base_y,
                                 box=(lat, lon, lat, lon), feet=feet,
                                 line=False)


def _member(resource, parts, origin=ORIGIN, heading=0.0, deck_kind=""):
    return types.SimpleNamespace(resource=resource, parts=tuple(parts),
                                 origin=origin, heading_deg=heading,
                                 deck_kind=deck_kind)


def _plan(pier_origin=ORIGIN, outside=True):
    deck = _member("T23/T3_road.obj", [_part(1, 40.0004, -2.9999)],
                   deck_kind="flag")
    pier = _member("T23/T3_2.obj", [_part(2, 40.00045, -2.9999),
                                    _part(3, 40.0006, -2.9999)],
                   origin=pier_origin)
    terminal = _member("T23/floor.obj", [_part(4, 40.002, -2.999)])
    members = [deck, pier] + ([terminal] if outside else [])
    return types.SimpleNamespace(units=[types.SimpleNamespace(members=members)])


def _pw(outside=True):
    row = (UID, U_ZERO, "building4/b4", "cluster_pad")
    return {2: row, 3: row, **({4: row} if outside else {})}


def test_a_deck_whose_piers_are_a_terminal_units_is_that_units_viaduct():
    counts: dict = {}
    v = BF.unit_viaducts([_ramp()], _plan(), _pw(), counts)
    assert set(v) == {"T23/T3_road.obj"}
    w = v["T23/T3_road.obj"]
    assert (w.uid, w.zero, w.where, w.voters) == (UID, U_ZERO, "building4/b4", 2)
    assert w.frame == BF.frame_of(_plan().units[0].members[0])
    assert counts["viaduct_decks_of_a_unit"] == 1


def test_a_free_standing_deck_is_no_units_viaduct():
    # its piers chained into a unit of their own (nothing outside the deck)
    assert BF.unit_viaducts([_ramp()], _plan(outside=False),
                            _pw(outside=False), {}) == {}
    # the piers belong to another pack row (another placement origin)
    assert BF.unit_viaducts([_ramp()], _plan(pier_origin=(1.0, 2.0)),
                            _pw(), {}) == {}
    # a plan written before placement origins names no viaduct
    p = _plan()
    for m in p.units[0].members:
        m.origin = None
    assert BF.unit_viaducts([_ramp()], p, _pw(), {}) == {}


def _surface(lat, lon):
    """Real ground: 93.1 at the landing rising 0.4 m per 10 m north."""
    return 93.1 + (lat - 40.0) * 111_000.0 * 0.04


def _body(mi, resource, cls, feet, anchor, bridge="", unit_seat=False):
    a = AR.Anchor(cls, feet[0][0], feet[0][1], anchor[1], anchor[0],
                  _surface(feet[0][0], feet[0][1]), unit_seat=unit_seat)
    parts = [types.SimpleNamespace(pid=100 * mi + k, lat=f[0], lon=f[1],
                                   base_y=f[2]) for k, f in enumerate(feet)]
    raw = [(parts, cls, a, tuple(feet), False)]
    st = types.SimpleNamespace(mi=mi, m=_member(resource, ()), groups=[[0]],
                               raw=raw, ground_off=[0.0], bridge=[bridge])
    c = PC.Candidate(mi, resource, a, frozenset(p.pid for p in parts),
                     len(feet), (feet[0][0], feet[0][1], feet[0][0], feet[0][1]),
                     group=0, body_class=cls)
    return st, c


def test_every_viaduct_body_rides_the_unit_level_spread_zero():
    deck_key = "T23/T3_road.obj"
    v = BF.unit_viaducts([_ramp()], _plan(), _pw(), {})
    staged, cands = [], []
    # the DECK on its own landing ground (30g (3)): the low-side foot
    st, c = _body(0, deck_key, AR.DECK,
                  [(40.0, -2.9999, -0.2), (40.0002, -2.9999, 2.2)],
                  ("low-side foot", -0.2))
    staged.append(st); cands.append(c)
    # a kerb segment on its own ground, inside the deck's footprint
    st, c = _body(1, "T23/brick.obj", AR.LINE_SEGMENT,
                  [(40.0003, -2.9999, 0.0)], ("line segment 1/6", 0.0),
                  bridge=deck_key)
    staged.append(st); cands.append(c)
    # a pier the §16g unit already seated: untouched
    st, c = _body(2, "T23/T3_2.obj", "building", [(40.0006, -2.9999, 0.0)],
                  ("§16g unit", _surface(40.0006, -2.9999) - U_ZERO),
                  bridge=deck_key, unit_seat=True)
    staged.append(st); cands.append(c)
    # a body of the terminal far from the deck: untouched
    st, c = _body(3, "T23/floor.obj", "building", [(40.002, -2.999, 0.0)],
                  ("surface at the body's zero", 0.0))
    staged.append(st); cands.append(c)
    before3 = cands[3].anchor
    counts: dict = {}
    fams = FU.seat_viaducts(cands, staged, _surface, counts, v,
                            unit_index=0, visual_m=0.5)
    zeros = [float(c.anchor.surface_z) - float(c.anchor.y_zero)
             for c in cands[:3]]
    assert max(zeros) - min(zeros) < 1e-9
    assert abs(zeros[0] - U_ZERO) < 1e-9
    assert cands[0].anchor.unit_seat and "RULINGS 2026-10-03e" in cands[0].anchor.reason
    assert cands[2].anchor.reason.startswith("§16g unit") and "viaduct" not in cands[2].anchor.reason
    assert cands[3].anchor is before3
    assert counts["viaduct_bodies_seated"] == 2
    assert len(fams) == 1 and fams[0].unit == UID
    # the written staged anchor is the candidate's (one rewrite)
    assert staged[0].raw[0][2] is cands[0].anchor


def test_a_free_standing_deck_still_seats_on_its_landing_ground():
    """30g (3) is untouched for a deck no unit claims: its own feet read
    a zero far from the abutting building's and it seats on its ground."""
    feet = [(40.0, -2.9999, -0.2), (40.0002, -2.9999, 2.2)]
    geom = AR.BodyGeometry(((40.0, -2.9999, -0.2, tuple(feet)),),
                           40.0005, -2.9999)
    # the abutting building's origin reads 108.53; the landing ground 93
    surf = lambda la, lo: _surface(la, lo) if la < 40.0004 else 108.53
    a = AR.anchor_for(AR.DECK, geom, surf, deck_own_ground_m=0.5)
    assert "kerb" not in a.reason
    assert abs((a.surface_z - a.y_zero) - 93.3) < 2.0
    # and seat_viaducts with no viaduct changes nothing
    st, c = _body(0, "T23/T3_road.obj", AR.DECK, feet, ("low-side foot", -0.2))
    cands = [c]
    assert FU.seat_viaducts(cands, [st], _surface, {}, {}, unit_index=0) == []
    assert cands[0] is c
