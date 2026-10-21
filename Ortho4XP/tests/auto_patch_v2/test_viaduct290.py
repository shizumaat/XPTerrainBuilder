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
    from auto_patch_v2.model.registries import Registries
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
    reg = Registries()
    reg.landings["u/landing0"] = {"block": "u/b0", "y": 0.0}
    out = LD.landing_cut([lot, road, apron], [land], law, reg=reg)
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
    from auto_patch_v2.model.registries import Registries
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
    reg = Registries()
    reg.held["u"] = {"unit": "u", "k": 0, "blocks": 1}
    got = LD.landing_regions([pad], {}, [box(-900, 0, -800, 10)], airport,
                             Law.load(), 0.0, 15.0, counts, reg=reg)
    return got, counts, dict(reg.landings)


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
    from auto_patch_v2.model.registries import Registries
    from auto_patch_v2.pipeline import publication as PB
    assert "landings" in SIDECAR_KEYS
    monkeypatch.setattr(CP, "landing_vertices", lambda _p: {"u/landing0": [0, 1, 2]})
    pm = types.SimpleNamespace(registries=Registries())
    pm.registries.landings["u/landing0"] = {"block": "u", "y": -0.2, "deck": "d.obj",
                                            "area_m2": 12.0}
    got = PB._landings(pm, [99.8, 99.8, 99.9])
    assert got == [{"ref": "u/landing0", "block": "u", "deck": "d.obj",
                    "y": -0.2, "area_m2": 12.0, "level": 99.8}]
    assert PB._landings(pm, None)[0]["level"] is None


# ── issue #1179: a viaduct is ONE CONNECTED deck structure ──────────────
# (owner RULINGS 2026-10-03e read with 2026-09-13bo).  A pack that
# authors one deck resource across the whole airport (tyres, carts,
# masts, ground plates under one shared datum) is many structures
# separated by open ground: each connected piece of the footprint is
# claimed on its own, and only bodies standing in a claimed piece ride
# the unit's level.

RES = "LY/TEH_tyres.obj"


def _two_pieces() -> BF.DeckPrint:
    """Piece 0: a 20 m plate at lat 40.0; piece 1: a 20 m plate ~500 m
    north, open ground between them — one resource, two structures."""
    tris = []
    for la in (40.0, 40.0045):
        a, b = (la, -3.0), (la, -2.9998)
        c, d = (la + 0.0002, -2.9998), (la + 0.0002, -3.0)
        tris += [(a, b, c), (a, c, d)]
    p = BF.DeckPrint(key=RES, unit=0, member=0, under_y=0.0,
                     box=(40.0, -3.0, 40.0047, -2.9998), tris=tuple(tris),
                     ys=((0.0,) * 3,) * 4)
    p.index()
    return p


def _tyre_plan():
    deck = _member(RES, [_part(1, 40.0001, -2.9999)], deck_kind="flag")
    # the unit's parts stand inside piece 0 only, and outside the deck
    pier = _member("LY/T2_a.obj", [_part(2, 40.0001, -2.9999),
                                   _part(3, 40.00015, -2.9999)])
    terminal = _member("LY/T2_b.obj", [_part(4, 40.002, -2.999)])
    return types.SimpleNamespace(units=[types.SimpleNamespace(
        members=[deck, pier, terminal])])


def _tyre_pw():
    row = (UID, U_ZERO, "building9/b9", "cluster_pad")
    return {2: row, 3: row, 4: row}


def test_a_deck_footprint_splits_into_its_connected_pieces():
    pieces = BF.deck_components(_two_pieces())
    assert [q.key for q in pieces] == [RES + "#0", RES + "#1"]
    assert pieces[0].contains(40.0001, -2.9999)
    assert not pieces[0].contains(40.0046, -2.9999)
    # ONE connected deck is its own single piece, key unchanged
    r = _ramp()
    assert BF.deck_components(r) == [r]


def test_each_piece_is_claimed_on_its_own():
    counts: dict = {}
    v = BF.unit_viaducts([_two_pieces()], _tyre_plan(), _tyre_pw(), counts)
    assert set(v) == {RES + "#0"}
    w = v[RES + "#0"]
    assert (w.resource, w.whole, w.uid, w.voters) == (RES, False, UID, 2)
    assert counts["viaduct_decks_free_standing"] == 1
    # the #290 viaduct: one connected deck, ONE rigid viaduct, whole
    h = BF.unit_viaducts([_ramp()], _plan(), _pw(), {})
    assert set(h) == {"T23/T3_road.obj"} and h["T23/T3_road.obj"].whole


def test_only_bodies_of_the_claimed_piece_ride_the_unit():
    import dataclasses as dc
    v = BF.unit_viaducts([_two_pieces()], _tyre_plan(), _tyre_pw(), {})
    # the deck member's two bodies: a tyre in the claimed piece, and the
    # same resource's tyre 500 m away on open ground
    st, c0 = _body(0, RES, AR.DECK, [(40.0001, -2.9999, 0.0)],
                   ("low-side foot", 0.0))
    st1, c1 = _body(0, RES, AR.DECK, [(40.0046, -2.9999, 0.0)],
                    ("low-side foot", 0.0))
    st.raw.append(st1.raw[0])
    st.groups.append([1])
    st.ground_off.append(0.0)
    c1 = dc.replace(c1, group=1)
    # a body §16e (3) names as the resource's, standing in piece 1
    st2, c2 = _body(1, "LY/cart.obj", AR.LINE_SEGMENT,
                    [(40.0046, -2.99985, 0.0)], ("line segment", 0.0),
                    bridge=RES)
    cands = [c0, c1, c2]
    before = [c1.anchor, c2.anchor]
    counts: dict = {}
    FU.seat_viaducts(cands, [st, st2], _surface, counts, v, unit_index=0)
    assert cands[0].anchor.unit_seat
    assert abs(float(cands[0].anchor.surface_z)
               - float(cands[0].anchor.y_zero) - U_ZERO) < 1e-9
    assert [cands[1].anchor, cands[2].anchor] == before
    assert counts["viaduct_bodies_seated"] == 1


# ── owner RULINGS 2026-10-20av (#1179): a ground plate on real relief ──

def _plate(ys=0.0) -> BF.DeckPrint:
    """A flat sheet 100 m long laid at its placement's ground (y ``ys``)."""
    a, b = (40.0, -3.0), (40.0, -2.9998)
    c, d = (40.0009, -2.9998), (40.0009, -3.0)
    p = BF.DeckPrint(key="T23/T3_road.obj", unit=0, member=0, under_y=ys,
                     box=(40.0, -3.0, 40.0009, -2.9998),
                     tris=((a, b, c), (a, c, d)),
                     ys=((ys, ys, ys), (ys, ys, ys)))
    p.index()
    return p


def test_a_ground_plate_on_real_relief_is_free_standing():
    # 4 m of real relief under a sheet at the ground: no one level seats it
    assert BF.ground_plate_on_relief(_plate(), _surface, 0.5)
    # a sheet draped DOWN from its datum over the terrain is a plate too
    assert BF.ground_plate_on_relief(_plate(-6.0), _surface, 0.5)
    counts: dict = {}
    assert BF.unit_viaducts([_plate()], _plan(), _pw(), counts,
                            surface=_surface, bar_m=0.5) == {}
    assert counts["viaduct_ground_plates_free_standing"] == 1


def test_a_plate_on_flat_ground_or_held_up_stays_a_viaduct():
    flat = lambda la, lo: 93.1                                  # noqa: E731
    assert not BF.ground_plate_on_relief(_plate(), flat, 0.5)
    # a floor held 4 m above its ground is a deck, not a plate
    assert not BF.ground_plate_on_relief(_plate(4.0), _surface, 0.5)
    assert set(BF.unit_viaducts([_plate()], _plan(), _pw(), {},
                                surface=flat, bar_m=0.5)) == {"T23/T3_road.obj"}


def test_the_290_ramp_on_real_relief_stays_one_viaduct():
    # HECA's T23/T3_road: 10 m of ramp over 4 m of ground is a deck
    assert not BF.ground_plate_on_relief(_ramp(), _surface, 0.5)
    v = BF.unit_viaducts([_ramp()], _plan(), _pw(), {},
                         surface=_surface, bar_m=0.5)
    assert set(v) == {"T23/T3_road.obj"} and v["T23/T3_road.obj"].whole
