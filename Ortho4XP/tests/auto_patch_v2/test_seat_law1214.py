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


def test_a_signature_deck_in_a_buildings_frame_is_the_buildings_own():
    """10-22b: the wall chain and the contents refuse a deck verdict only
    for a bridge; a flag deck or one over a deck face keeps §48 (1) (c)."""
    sig = types.SimpleNamespace(deck_kind="signature", deck_datum_z=None)
    flag = types.SimpleNamespace(deck_kind="flag", deck_datum_z=None)
    faced = types.SimpleNamespace(deck_kind="signature", deck_datum_z=101.0)
    hall = types.SimpleNamespace(deck_kind="", deck_datum_z=None)
    building = types.SimpleNamespace(members=(sig, flag, faced, hall))
    bridge = types.SimpleNamespace(members=(sig,))
    assert not PF.member_is_bridge_deck(building, sig)
    assert PF.member_is_bridge_deck(building, flag)
    assert PF.member_is_bridge_deck(building, faced)
    assert not PF.member_is_bridge_deck(building, hall)
    assert PF.member_is_bridge_deck(bridge, sig)


def test_a_deck_is_never_the_contents_of_a_below_grade_singleton():
    """KDAL's drainage cap over its channel: the channel (authored -3.6 m)
    is a retaining structure, not a building; its cap stays out of it."""
    from shapely.geometry import box as _b  # noqa: F401
    from auto_patch_v2.airport import contents as C
    ring = ((0.0, 0.0), (0.0, 1e-3), (1e-3, 1e-3), (1e-3, 0.0))
    shim = lambda by: types.SimpleNamespace(rings=(ring,), part_boxes=(), base_y=by)  # noqa: E731
    shims = [shim(-3.6), shim(0.0)]
    kw = dict(is_deck=lambda i: False, base_y=lambda i: shims[i].base_y,
              ml=111_000.0, mo=85_000.0)
    out, _s = C.attach_contents(shims, [], [0], [1], 0.5, 0.5, {}, **kw)
    assert out == {1: -1}                      # no verdict handed in: as before
    out, _s = C.attach_contents(shims, [], [0], [1], 0.5, 0.5, {},
                                deck_verdict=lambda i: i == 1, **kw)
    assert out == {}
    shims[0] = shim(0.0)                        # a building at grade hosts it
    out, _s = C.attach_contents(shims, [], [0], [1], 0.5, 0.5, {},
                                deck_verdict=lambda i: i == 1, **kw)
    assert out == {1: -1}


# ── round 2 (owner KMCI 1.0.415 read, 2026-10-22T22:22Z) ─────────────────

def _model_split(index, zero, lift, box, row_g=100.0):
    b = types.SimpleNamespace(surface_z=row_g, y_zero=row_g - zero, lift_m=lift,
                              plan_box=box)
    return types.SimpleNamespace(placement=types.SimpleNamespace(index=index),
                                 bodies=(b,))


def _dump(*rows):
    return types.SimpleNamespace(placements=list(rows))


def test_a_lifted_row_inside_a_re_seated_frame_moves_with_it():
    """KMCI's 614 seats (+4.7 AGL) stood on the concourse roof once the
    terminal (+8.5 AGL) dropped its lift: a lifted row in the frame's
    plan box moves by the frame's displacement, never under the ground."""
    from auto_patch_v2.airport import frame_riders as FR
    shell = _row(elevation=8.5)
    chair = types.SimpleNamespace(def_path="objects/seat.obj", lat=40.0001,
                                  lon=-3.0001, heading_deg=0.0,
                                  kind="OBJECT_AGL", elevation=4.7)
    plain = types.SimpleNamespace(def_path="objects/kiosk.obj", lat=40.0001,
                                  lon=-3.0001, heading_deg=0.0, kind="OBJECT",
                                  elevation=None)
    box = (39.9999, -3.0003, 40.0003, -2.9999)
    # the shell re-seated at 101.0: 7.5 m under its authored 100 + 8.5
    seats = FR.frame_rider_seats(_dump(shell, chair, plain),
                                 [_model_split(0, 101.0, 0.0, box)], _flat,
                                 frozenset({0}))
    assert [(m.index, round(m.elevation, 3)) for m in seats] == [(1, 100.0)]
    assert seats[0].why == FR.FRAME_RIDER
    # a frame that kept its lift moves nothing
    assert FR.frame_rider_seats(_dump(shell, chair),
                                [_model_split(0, 108.5, 8.5, box)], _flat,
                                frozenset({0})) == ()
    # ...and the census reads the same relation
    from auto_patch_v2.airport import placement_coherence as PCo
    sp = [{"placement": {"index": 0}, "bodies": [
        {"surface_z": 100.0, "y_zero": -1.0, "lift_m": 0.0, "plan_box": list(box)}]}]
    bad = PCo.census_frame_riders(_dump(shell, chair), sp, [], _flat)
    assert bad["riders"] == 1 and bad["off_frame"] == 1
    ok = PCo.census_frame_riders(_dump(shell, chair), sp,
                                 [{"index": 1, "elevation": 100.0}], _flat)
    assert ok["off_frame"] == 0


def test_the_unit_datum_puts_the_walls_feet_on_the_pad():
    """10-22b: the walls seat the unit — a terminal whose walls stand at
    y -1.1 takes its zero 1.1 m over the pad, not on it; a tower's cab
    (walled, 70 m up, no feet) does not count."""
    from auto_patch_v2.airport import footprint_unit as FU
    wall = types.SimpleNamespace(base_y=-1.1, height_m=6.0, line=False,
                                 feet=((40.0, -3.0, -1.1), (40.0, -3.0, -1.1)))
    cab = types.SimpleNamespace(base_y=70.0, height_m=5.0, line=False, feet=())
    un = types.SimpleNamespace(id="fu:1:2/p1", pids=frozenset({1, 2}))
    other = types.SimpleNamespace(id="fu:1:2/p2", pids=frozenset({3}))
    parts = {1: wall, 2: cab, 3: wall}
    assert FU._wall_base(un, [un, other], parts, 2.5, {}) == -1.1
    assert FU._wall_base(un, [un], parts, 0.0, {}) == 0.0
    assert FU._wall_base(types.SimpleNamespace(id="j", pids=frozenset()), [],
                         parts, 2.5, {}) == 0.0


def test_a_bridge_deck_meets_both_approaches():
    """10-22f: an end line on the embankment slope (289.9) is not the road
    onto the bridge (294-296 further on): each end reads its approach and
    the rigid deck splits what it cannot meet at both."""
    M = 111_132.954
    ends = (((0.0, 0.0), (0.0, 2e-5)), ((-5e-4, 0.0), (-5e-4, 2e-5)))

    def surface(la, lo):
        # the dip under the span, the embankments rising away from it
        if la > 0.0:
            return min(296.0, 289.9 + la * M * 0.4)
        if la < -5e-4:
            return min(294.0, 289.9 + (-5e-4 - la) * M * 0.4)
        return 288.5
    d = AR.Datum(12.2, tuple(p for e in ends for p in e), "deck top",
                 ends=ends, step_m=5.0, walk_max_m=60.0, level_tol_m=0.3)
    a = AR.anchor_for(AR.DECK, _geom_at_(-2.5e-4, 1e-5, -6.0), surface,
                      tol_m=0.3, datum=d)
    deck = a.surface_z - a.y_zero + 12.2
    # 10-22m: flush with the HIGHER approach (296.0); the 2 m over the
    # other one is the terrain's to grade (#1138)
    assert abs(deck - 296.0) < 1e-6
    assert "approach ground 296.00 / 294.00" in a.reason


def _geom_at_(lat, lon, y=0.0):
    return AR.BodyGeometry(((lat, lon, y, ((lat, lon, y),)),), lat, lon)


def test_an_open_structures_bodies_take_one_zero():
    """10-22c/f: KMCI road-bridge-7 was six bodies 22.6 m apart.  The
    bodies of an OPEN frame take one zero: the deck datum's, else the
    lowest (no support floats)."""
    def body(i, zero, datum=False):
        a = AR.Anchor(AR.OTHER, 40.0, -3.0, 100.0 - zero, "own", 100.0,
                      offset=(1.0, 100.0 - zero, 2.0), datum=datum)
        return Body(i, AR.OTHER, (i,), a, f"objects/b__b{i}.obj")
    rec = _split(body(0, 300.97), body(1, 317.06), body(2, 323.57))
    out = PP._rigid_open(rec, True)
    zs = {round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in out.bodies}
    assert zs == {300.97}
    assert all(b.anchor.offset[1] == b.anchor.y_zero for b in out.bodies)
    assert all(o.anchor.offset[0] == 1.0 for o in out.bodies)
    dat = PP._rigid_open(_split(body(0, 300.0), body(1, 305.0, datum=True)), True)
    assert {round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in dat.bodies} == {305.0}
    assert PP._rigid_open(rec, False) is rec      # a building's frame: as before


def test_the_group_offset_census_catches_a_bridge_apart():
    from auto_patch_v2.airport import placement_coherence as PCo
    sp = [{"placement": {"index": 8, "resource": "objects/bridge.obj"}, "bodies": [
        {"surface_z": 100.0, "y_zero": 0.0}, {"surface_z": 100.0, "y_zero": -22.6}]}]
    c = PCo.census_group_offsets(sp, {"objects/bridge.obj"})
    assert c["apart"] == 1 and abs(c["worst"][0][0] - 22.6) < 1e-9
    assert PCo.census_group_offsets(sp, set())["apart"] == 0
    assert "VIOLATED" in "\n".join(PCo.coherence_lines(c, None, None))


def test_an_airside_hard_deck_sits_flush_with_the_solved_airside():
    """10-22n: a taxiway or runway carried over a road on a pack hard deck
    (LFPG's ``Hard_deck`` objects): its top meets the SOLVED airside
    surface (the plan's ``deck_datum_z``) where the design surface under
    its ring is airside, and the whole frame moves with it when every
    other member stands on the deck; over groundside it is class B."""
    ring = ((40.0, -3.0), (40.0, -2.9998), (40.0002, -2.9998), (40.0002, -3.0))
    m = types.SimpleNamespace(deck_kind="flag", deck_top_y=6.96,
                              deck_datum_z=100.92, deck_ring=ring,
                              resource="objects/deck.obj")
    rail = types.SimpleNamespace(deck_kind="", resource="objects/rail.obj")

    class Roles:
        def __init__(self, role):
            self.role = role

        def roles_many(self, la, lo):
            return [self.role] * len(la)

    def surface(la, lo):
        return 96.2                                # the road under the deck
    surface.roles = Roles("primary_parallel")
    st_deck = types.SimpleNamespace(m=m, bridge=["objects/deck.obj"])
    st_rail = types.SimpleNamespace(m=rail, bridge=["objects/deck.obj#0"])
    got = PP._airside_frame([st_deck, st_rail], (), surface, {})
    assert got is not None and abs(got[0] - (100.92 - 6.96)) < 1e-9
    rec = PP._airside_deck(_split(_body(0, 0.0)), got, {})
    a = rec.bodies[0].anchor
    assert a.datum and abs((a.surface_z - a.y_zero) + 6.96 - 100.92) < 1e-9
    # a building beside the deck in its frame: not a bridge, nothing moves
    st_hall = types.SimpleNamespace(m=rail, bridge=[""])
    assert PP._airside_frame([st_deck, st_hall], (), surface, {}) is None
    surface.roles = Roles("service_road")
    assert PP._airside_frame([st_deck, st_rail], (), surface, {}) is None
