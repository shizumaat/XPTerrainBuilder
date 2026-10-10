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


# ── task (2): the ramp landing (RULINGS 2026-10-03e) ─────────────────────

def test_the_landing_is_the_ramp_end_within_the_band_at_its_foot():
    """The deck footprint clipped to y <= min + 0.5: the 100 m ramp's low
    end, 4.5 m of it, at the foot's authored y (0)."""
    pieces = BF.landing_pieces(_ramp(), 0.5)
    assert pieces and all(y == 0.0 for _r, y in pieces)
    lats = [la for ring, _y in pieces for la, _lo in ring]
    assert min(lats) == 40.0
    assert abs((max(lats) - 40.0) - 0.0009 * 0.05) < 1e-9     # 0.5 of 10 m


def test_the_planar_stage_asks_the_same_derivation_with_block_keys():
    """ONE reader of the relation: ``viaduct_units`` keyed by the held
    BLOCK a part stands on returns the same deck -> unit as the plan-wide
    seat reading."""
    blocks = {2: "building4/b4", 3: "building4/b4", 4: "building4/b4"}
    v = BF.viaduct_units([_ramp()], _plan(), lambda q: blocks.get(q.pid, ""))
    assert v["T23/T3_road.obj"][0] == "building4/b4"
    w = BF.unit_viaducts([_ramp()], _plan(), _pw(), {})
    assert w["T23/T3_road.obj"].where == v["T23/T3_road.obj"][0]


def test_a_landing_ref_is_never_a_block():
    from auto_patch_v2.model.planar import block_of, unit_ref_of
    from auto_patch_v2.model.platform import is_landing_ref
    assert is_landing_ref("building4/landing0")
    assert is_landing_ref("building4/landing12#collar")
    assert not is_landing_ref("building4/b4")
    assert block_of("building4/landing0") is None
    assert block_of("building4/landing0#collar") is None
    assert unit_ref_of("building4/landing0") != "building4"


def test_the_landing_cut_takes_a_lot_never_a_road_or_airside():
    from shapely.geometry import box
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.platform import LANDINGS
    from auto_patch_v2.planar import landing as LD
    from auto_patch_v2.planar.overlay import Region
    law = Law.load()
    land = Region("building", "u/landing0", box(0, 0, 10, 10), None, None,
                  "airside", "cell")
    lot = Region("parking_lot", "lot", box(-5, -5, 20, 20), None, None,
                 "groundside", "cell")
    road = Region("service_road", "rd", box(-5, 2, 20, 4), None, None,
                  "groundside", "cell")
    apron = Region("apron", "ap", box(10, 0, 20, 10), None, None,
                   "airside", "cell")
    LANDINGS.clear()
    LANDINGS["u/landing0"] = {"block": "u/b0", "y": 0.0}
    try:
        out = LD.landing_cut([lot, road, apron], [land], law)
    finally:
        LANDINGS.clear()
    lots = [r for r in out if r.role == "parking_lot"]
    assert abs(sum(r.polygon.area for r in lots) - (25 * 25 - 100)) < 1e-6
    assert [r for r in out if r.role == "service_road"][0] is road
    assert [r for r in out if r.role == "apron"][0] is apron


# ── spec §56 (10) R-L: the landing gate ──────────────────────────────────

def _regions_for_foot(monkeypatch, foot_y):
    """``landing_regions`` on a 100 m ramp whose foot stands ``foot_y``
    against its unit's pad, the unit a held 200 x 200 m block beside it."""
    from shapely.geometry import box
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.platform import HELD, LANDINGS
    from auto_patch_v2.planar import landing as LD
    from auto_patch_v2.planar.overlay import Region
    p = _ramp()
    p.ys = tuple(tuple(y + foot_y for y in t) for t in p.ys)
    deck = _member(p.key, [_part(1, 40.0004, -2.9999)], deck_kind="flag")
    part = types.SimpleNamespace(units=[types.SimpleNamespace(members=[deck])])
    frame = types.SimpleNamespace(
        entry=lambda: (lambda lo, la: ((lo + 3.0) * 1e5, (la - 40.0) * 1e5)))
    airport = types.SimpleNamespace(partition=part, frame=frame)
    monkeypatch.setattr(LD, "_prints", lambda _part: [p])
    monkeypatch.setattr(BF, "viaduct_units",
                        lambda *_a, **_k: {p.key: ("u", 3, None, p)})
    pad = Region("building", "u", box(-300, 0, -100, 200), None, None,
                 "airside", "cell")
    counts: dict = {}
    HELD.clear()
    HELD["u"] = {"unit": "u", "k": 0, "blocks": 1}
    try:
        got = LD.landing_regions([pad], {}, [box(-900, 0, -800, 10)], airport,
                                 Law.load(), 0.0, 15.0, counts)
        return got, counts, dict(LANDINGS)
    finally:
        HELD.clear()
        LANDINGS.clear()


def test_a_foot_within_the_band_of_its_units_pad_is_a_landing(monkeypatch):
    got, counts, landings = _regions_for_foot(monkeypatch, -0.2)
    assert counts["landings"] == 1 and "landing_below_unit" not in counts
    assert landings["u/landing0"]["y"] == -0.2
    assert {str(r.ref) for r in got} == {"u/landing0", "u/landing0#collar"}


def test_a_pier_footing_below_the_band_mints_no_landing(monkeypatch):
    """A deck whose lowest authored y stands 2 m under its unit's pad is a
    footing in the ground: counted, nothing minted, the ground not dug."""
    got, counts, landings = _regions_for_foot(monkeypatch, -2.0)
    assert got == [] and landings == {}
    assert counts["landing_below_unit"] == 1 and counts["landings"] == 0


def test_a_deck_that_never_comes_down_to_the_pad_mints_no_landing(monkeypatch):
    """An elevated road end whose lowest authored y stands a storey over
    its unit's pad is no ramp foot: the ground is not graded up to it."""
    got, counts, landings = _regions_for_foot(monkeypatch, 10.7)
    assert got == [] and landings == {}
    assert counts["landing_above_unit"] == 1 and counts["landings"] == 0


def test_the_sidecar_publishes_each_landing_with_its_deck_and_level(monkeypatch):
    from auto_patch_v2.constraints import platform as CP
    from auto_patch_v2.emit.osm_adapter import SIDECAR_KEYS
    from auto_patch_v2.model.platform import LANDINGS
    from auto_patch_v2.pipeline import publication as PB
    assert "landings" in SIDECAR_KEYS
    monkeypatch.setattr(CP, "landing_vertices", lambda _p: {"u/landing0": [0, 1, 2]})
    LANDINGS.clear()
    LANDINGS["u/landing0"] = {"block": "u", "y": -0.2, "deck": "d.obj",
                              "area_m2": 12.0}
    try:
        got = PB._landings(None, [99.8, 99.8, 99.9])
        assert got == [{"ref": "u/landing0", "block": "u", "deck": "d.obj",
                        "y": -0.2, "area_m2": 12.0, "level": 99.8}]
        assert PB._landings(None, None)[0]["level"] is None
    finally:
        LANDINGS.clear()
