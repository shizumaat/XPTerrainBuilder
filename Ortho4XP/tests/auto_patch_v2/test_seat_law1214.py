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

from auto_patch_v2.airport import airside_deck_seat as ADS
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import open_frame_seat as OFS
from auto_patch_v2.airport import placement_family as PF
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.airport.placement_record import Body, Split

LIFT = 8.5
TOL = 0.05
#: the Member shape the file-name rule reads (``placement_file.baked_name``)
_M = types.SimpleNamespace(resource="objects/terminal.obj", zero_y=0.0)


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
    piers reach — they may sink or float (10-22d) — where the ends stand
    on an embankment (22p's witness)."""
    d = AR.datum_of(_deck(), abutment_step_m=5.0, free_standing=True)
    assert d is not None and d.label == "deck top" and d.y == 7.7
    assert len(d.stations) >= 4 and len(d.ends) == 2

    def ground(la, lo):
        if la <= 40.0 + 1e-9:
            return 297.7
        if la >= 40.001 - 1e-9:
            return 298.1
        return 290.0                       # the road under the span
    g = AR.BodyGeometry(((40.0005, -3.0, -6.0, ((40.0005, -3.0, -6.0),)),),
                        40.0005, -3.0)
    a = AR.anchor_for(AR.DECK, g, ground, tol_m=0.3, datum=d)
    assert a.datum
    # flush at the end nearer its ground: the HIGHER end (298.1)
    assert abs(a.surface_z - a.y_zero + 7.7 - 298.1) < 1e-6
    # the pier foot at y -6 is NOT what seats it
    assert "flush with the ground at end line 2" in a.reason


def test_a_bridge_with_no_embankment_keeps_its_authored_clearance():
    """RULINGS 2026-10-22p (Q118, "A"): both end lines at the road's own
    level — no raised approach — so the deck keeps the author's clearance
    over the road at its anchor; the end gaps are #1138's."""
    d = AR.datum_of(_deck(), abutment_step_m=5.0, free_standing=True)

    def ground(la, lo):
        return 292.9
    g = AR.BodyGeometry(((40.0005, -3.0, -6.0, ((40.0005, -3.0, -6.0),)),),
                        40.0005, -3.0)
    a = AR.anchor_for(AR.DECK, g, ground, tol_m=0.3, datum=d, authored_agl_m=-1.0)
    # the authored zero is the anchor's ground plus the author's AGL
    assert abs((a.surface_z - a.y_zero) - (292.9 - 1.0)) < 1e-6
    assert "authored clearance" in a.reason and "22p" in a.reason


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
    from auto_patch_v2.airport import contents as C
    from shapely.geometry import box as _b  # noqa: F401
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


def test_a_bridge_deck_meets_the_ground_at_its_end_lines():
    """#1214 round 3, R4: each end reads the ground AT its end line — the
    road ribbon where most stations lie on one — never the highest land of
    a walk beyond it (KMCI road-bridge-6 / -10 floated 5-7 m / 2 m)."""
    ends = (((0.0, 0.0), (0.0, 2e-5)), ((-5e-4, 0.0), (-5e-4, 2e-5)))

    class Roles:
        def roles_many(self, la, lo):
            return ["service_road" if abs(a) < 1e-9 else None for a in la]

    def surface(la, lo):
        if abs(la) < 1e-9:
            return 296.0                   # the road onto the bridge
        if abs(la + 5e-4) < 1e-9:
            return 294.0
        return 288.5 if -5e-4 < la < 0.0 else 299.0     # a rise beyond
    surface.roles = Roles()
    d = AR.Datum(12.2, tuple(p for e in ends for p in e), "deck top",
                 ends=ends, step_m=5.0, walk_max_m=60.0, level_tol_m=0.3)
    a = AR.anchor_for(AR.DECK, _geom_at_(-2.5e-4, 1e-5, -6.0), surface,
                      tol_m=0.3, datum=d)
    deck = a.surface_z - a.y_zero + 12.2
    # flush with the end nearer its ground (296.0, on the road ribbon);
    # the 2 m over the other one is the terrain's to grade (#1138)
    assert abs(deck - 296.0) < 1e-6
    assert "296.00 (road) / 294.00 (mesh)" in a.reason


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
    out = OFS.rigid_open(rec, _M, True)
    zs = {round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in out.bodies}
    assert zs == {300.97}
    assert all(b.anchor.offset[1] == b.anchor.y_zero for b in out.bodies)
    assert all(o.anchor.offset[0] == 1.0 for o in out.bodies)
    dat = OFS.rigid_open(_split(body(0, 300.0), body(1, 305.0, datum=True)), _M, True)
    assert {round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in dat.bodies} == {305.0}
    assert OFS.rigid_open(rec, _M, False) is rec      # a building's frame: as before


def test_the_group_offset_census_catches_a_bridge_apart():
    from auto_patch_v2.airport import placement_coherence as PCo
    sp = [{"placement": {"index": 8, "resource": "objects/bridge.obj"}, "bodies": [
        {"surface_z": 100.0, "y_zero": 0.0}, {"surface_z": 100.0, "y_zero": -22.6}]}]
    c = PCo.census_group_offsets(sp, {"objects/bridge.obj"})
    assert c["apart"] == 1 and abs(c["worst"][0][0] - 22.6) < 1e-9
    assert PCo.census_group_offsets(sp, set())["apart"] == 0
    assert "VIOLATED" in "\n".join(PCo.coherence_lines(c, None, None))


def test_an_airside_hard_deck_sits_flush_with_the_solved_airside():
    """10-22n as read by #1214 round 3 (R3): a taxiway carried over a road
    on a pack hard deck (LFPG's ``H*.obj``) has its slab's max y on the
    SOLVED AIRSIDE surface read at its two END LINES (the mean of the two
    lines' medians), never the ring median that takes in the road under
    it; the whole frame moves with it when every other member stands on
    the deck; over groundside it is class B."""
    ring = ((40.0, -3.0), (40.0, -2.9998), (40.0002, -2.9998), (40.0002, -3.0))
    m = types.SimpleNamespace(deck_kind="flag", deck_top_y=6.96,
                              deck_datum_z=99.7, deck_ring=ring,
                              resource="objects/deck.obj", zero_y=0.0)
    rail = types.SimpleNamespace(deck_kind="", resource="objects/rail.obj")

    class Roles:
        """The taxiway runs north-south over the deck; the road under it
        east-west — what lies one step outside each edge of the ring."""
        def __init__(self, role):
            self.role = role

        def roles_many(self, la, lo):
            return [self.role if (a <= 40.0 + 1e-9 or a >= 40.0002 - 1e-9) else "service_road"
                    for a in la]

    def surface(la, lo):
        if la <= 40.0 + 1e-9:
            return 100.8                   # the taxiway onto the deck
        if la >= 40.0002 - 1e-9:
            return 101.0
        return 96.2                        # the road under the deck
    surface.roles = Roles("primary_parallel")
    st_deck = types.SimpleNamespace(m=m, bridge=["objects/deck.obj"])
    st_rail = types.SimpleNamespace(m=rail, bridge=["objects/deck.obj#0"])
    got = ADS.airside_frame([st_deck, st_rail], (), surface, {}, 2.0)
    assert got is not None and abs(got[0] - (100.9 - 6.96)) < 1e-9
    assert "end lines 100.80 / 101.00" in got[1] or "end lines 101.00 / 100.80" in got[1]
    rec = ADS.airside_deck(_split(_body(0, 0.0)), m, got, {})
    b = rec.bodies[0]
    assert b.anchor.datum and abs((b.anchor.surface_z - b.anchor.y_zero) + 6.96 - 100.9) < 1e-9
    # R1: the file is named for the offset it now bakes
    from auto_patch_v2.airport import obj8_split as OS
    assert b.new_resource == OS.body_resource_name("objects/deck.obj", 0, b.anchor.offset)
    # no end lines read (no step): the ring median, as round 2 read it
    got0 = ADS.airside_frame([st_deck, st_rail], (), surface, {}, 0.0)
    assert abs(got0[0] - (99.7 - 6.96)) < 1e-9
    # a building beside the deck in its frame: not a bridge, nothing moves
    st_hall = types.SimpleNamespace(m=rail, bridge=[""])
    assert ADS.airside_frame([st_deck, st_hall], (), surface, {}, 2.0) is None
    surface.roles = Roles("service_road")
    assert ADS.airside_frame([st_deck, st_rail], (), surface, {}, 2.0) is None


# ── #1214 round 3 ────────────────────────────────────────────────────────

def test_r2_a_deck_placed_at_n_anchors_is_n_placements_not_skipped(tmp_path):
    """R2: the I-4 skip ("one file cannot carry per-placement offsets") is
    obsolete for a DECK — 14at keys a body file on the offset it bakes, so
    N placements write N files.  LFPG's H2 x3, H3 x2, H7 x4 and H17 x3 stood
    at their authored AGL, tuned to the stock mesh.  A plain resource at
    two anchors is still dropped (its seat is the DSF row's, §16g (5))."""
    from types import SimpleNamespace as NS

    from auto_patch_v2.airport import obj8 as O
    from auto_patch_v2.airport import pack_partition as PPa
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.frame import Frame
    from test_v2packscatter import _box, _write_obj
    law = Law.for_airport("")
    root = tmp_path / "pack"
    (root / "Earth nav data").mkdir(parents=True)
    (root / "Earth nav data" / "apt.dat").write_text("I\n1100\n", encoding="utf-8", newline="")
    _write_obj(root / "deck.obj", [_box(0, 0, 60, 12, 0.8, y0=7.0)]
               + [_box(x, 5, 1.5, 1.5, 7.0) for x in (2, 20, 38, 56)])
    _write_obj(root / "twice.obj", [_box(0, 0, 3, 3, 3)])

    def place(oid, name, xy, kind=""):
        return O.PlacedObject(id=oid, path=name, resolved=str(root / name), xy=xy,
                              heading_deg=0.0, agl_m=0.0, kind="OBJECT",
                              anchor_z=100.0, below_grade=None, plan_bbox=None,
                              solid_min_z=None, solid_min_depth_m=None,
                              hard_deck=None, deck_top_z=None, deck_kind=kind)
    objs = [place("dsf:obj0", "deck.obj", (100.0, 40.0), "signature"),
            place("dsf:obj1", "deck.obj", (400.0, 40.0), "signature"),
            place("dsf:obj2", "twice.obj", (300.0, 0.0)),
            place("dsf:obj3", "twice.obj", (320.0, 0.0))]
    pack = NS(name="pack", apt_dat_path=str(root / "Earth nav data" / "apt.dat"))
    air = NS(icao="ZZZZ", frame=Frame("ZZZZ", (60.0, -135.0), 11), pack=pack)
    cache = O.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    part = PPa.partition_pack(air, objs, cache, law)
    skipped = dict(part.skipped)
    assert "(I-4)" in skipped.get("twice.obj", "") and "deck.obj" not in skipped
    assert part.counts["multi_anchor"] == 1 and part.counts["multi_anchor_decks_kept"] == 1
    decks = [m for u in part.units for m in u.members if m.resource == "deck.obj"]
    assert len(decks) == 2                # one member per placement


def test_r1_every_pass_that_moves_an_anchor_renames_the_file():
    """R1: the file a body is written as is named for what it BAKES — the
    open-frame zero renames it; the DSF writer refuses a body file that is
    not in the pack."""
    from auto_patch_v2.airport import obj8_split as OS
    from auto_patch_v2.airport import placement_file as PFi

    def body(i, zero):
        a = AR.Anchor(AR.OTHER, 40.0, -3.0, 100.0 - zero, "own", 100.0,
                      offset=(1.0, 100.0 - zero, 2.0))
        return Body(i, AR.OTHER, (i,), a,
                    OS.body_resource_name(_M.resource, i, (1.0, 100.0 - zero, 2.0)))
    out = OFS.rigid_open(_split(body(0, 300.0), body(1, 310.0)), _M, True)
    for b in out.bodies:
        assert b.new_resource == PFi.baked_name(_M, b)
    assert out.bodies[1].new_resource != body(1, 310.0).new_resource
    # a member read against its own zero (#1102) bakes the PRISTINE offset
    m6 = types.SimpleNamespace(resource=_M.resource, zero_y=6.0)
    b = body(0, 300.0)
    assert PFi.baked_name(m6, b) == OS.body_resource_name(
        _M.resource, 0, (1.0, 100.0 - 300.0 + 6.0, 2.0))


def test_r1_the_dsf_writer_refuses_a_body_file_nothing_wrote(tmp_path):
    from auto_patch_v2.airport import dsf_write as W
    (tmp_path / "objects").mkdir()
    (tmp_path / "objects" / "a__b0_1.obj").write_text("I\n", encoding="utf-8", newline="")
    plan = types.SimpleNamespace(new_resources=lambda: ("objects/a__b0_1.obj",
                                                        "objects/a__b1_2.obj"))
    assert W.missing_body_files(str(tmp_path), plan) == ["objects/a__b1_2.obj"]
    import pytest
    with pytest.raises(ValueError, match="REFUSING"):
        W._refuse_missing_bodies(str(tmp_path), plan)


def test_r5_a_one_anchor_lifted_frame_stands_on_the_authors_ground():
    """R5: every part of the unit in ONE frame with ONE lift (KMCI's
    terminal, +8.499): the base is the author's ground y = -lift, cross-
    checked by the lowest plane of the walls' feet; the median (-1.1, the
    concourse) put the lower floor 7.4 m under the apron."""
    from auto_patch_v2.airport import footprint_unit as FU

    def wall(y, n=1):
        return types.SimpleNamespace(base_y=y, height_m=6.0, line=False,
                                     feet=((40.0, -3.0, y),) * n)
    parts = {1: wall(-8.5, 4), 2: wall(-1.1, 6), 3: wall(-1.1, 6)}
    un = types.SimpleNamespace(id="fu:1:2/p1", pids=frozenset({1, 2, 3}))
    one = {q: ((40.0, -3.0), 8.499) for q in parts}
    assert FU._wall_base(un, [un], parts, 2.5, {}, one) == -8.499
    # a second, smaller frame chained in: the DOMINANT frame's ground
    two = dict(one)
    two[3] = ((40.1, -3.0), 0.0)
    assert FU._wall_base(un, [un], parts, 2.5, {}, two) == -8.499
    # the dominant frame unlifted: the walls' median, as 10-22b read it
    flat = {q: ((40.0, -3.0), 0.0) for q in parts}
    assert FU._wall_base(un, [un], parts, 2.5, {}, flat) == -1.1
    # no wall-foot plane at the author's ground: the median stands
    parts_hi = {1: wall(-1.1, 4), 2: wall(-1.1, 6), 3: wall(-1.1, 6)}
    assert FU._wall_base(un, [un], parts_hi, 2.5, {}, one) == -1.1


def test_r5_the_bodies_of_one_connected_unit_take_one_zero():
    """22o: a connected unit's pieces (the pad-level / block cut) and every
    pass's seat of its parts — a basin rim, a line-segment wall — take the
    unit's one zero; a body with no chained part keeps its own."""
    def body(i, zero, pids):
        a = AR.Anchor(AR.OTHER, 40.0, -3.0, 100.0 - zero, "basin rim", 100.0,
                      offset=(0.0, 100.0 - zero, 0.0))
        return Body(i, AR.OTHER, (i,), a, f"objects/t__b{i}.obj", pids=pids)
    pw = {1: ("fu:16:1/p1/b0", 305.97), 2: ("fu:16:1/p2/b1", 305.99),
          3: ("fu:16:1/p2/b1", 305.99)}
    plan = types.SimpleNamespace(units=(types.SimpleNamespace(id="unit:20", agl_m=8.5, members=(
        types.SimpleNamespace(parts=tuple(types.SimpleNamespace(pid=q) for q in (1, 2, 3))),)),))
    zeros = OFS.root_zeros(pw, plan)
    assert zeros == {"fu:16:1|unit:20": (305.99, 8.5)}
    rec = _split(body(0, 305.99, (2,)), body(1, 304.89, (1,)), body(2, 312.91, (3,)),
                 body(3, 290.0, (9,)))
    counts: dict = {}
    out = OFS.group_zero(rec, _M, pw, zeros, counts, "unit:20")
    z = [round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in out.bodies]
    assert z == [305.99, 305.99, 305.99, 290.0] and counts["group_zero_bodies"] == 2
    assert out.bodies[1].anchor.reason.startswith(OFS.GROUP_REASON)
    # another FRAME chained into the unit (a tower beside the terminal) has
    # no share keyed here and keeps its own seat (#1214 round 4)
    other = OFS.group_zero(_split(body(0, 300.0, (2,))), _M, pw, zeros, {}, "unit:21")
    assert round(other.bodies[0].anchor.surface_z - other.bodies[0].anchor.y_zero, 2) == 300.0


def test_r5_an_unchained_body_within_a_metre_joins_the_unit():
    """22o: a body none of whose parts is chained (a kerb, a border slab)
    whose plan box comes within a metre of the connected unit's parts
    moves with it; one 3 m off keeps its own seat."""
    def body(i, zero, box):
        a = AR.Anchor(AR.OTHER, 40.0, -3.0, 100.0 - zero, "low-side foot", 100.0,
                      offset=(0.0, 100.0 - zero, 0.0))
        return Body(i, AR.OTHER, (i,), a, f"objects/t__b{i}.obj", pids=(99,),
                    plan_box=box)
    pw = {1: ("fu:16:1/p1", 313.39)}
    zeros = {"fu:16:1|unit:20": (313.39, 8.5)}
    m_lat = 111_132.954
    boxes = {"fu:16:1": [(40.0, -3.0, 40.0001, -2.9999)]}
    near = body(0, 310.3, (40.0001 + 0.5 / m_lat, -3.0, 40.0002, -2.9999))
    far = body(1, 310.3, (40.0001 + 3.0 / m_lat, -3.0, 40.0002, -2.9999))
    out = OFS.group_zero(_split(near, far), _M, pw, zeros, {}, "unit:20", root_boxes=boxes)
    z = [round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in out.bodies]
    assert z == [313.39, 310.3]


def test_r5_touching_units_of_one_frame_move_as_one():
    """22o: two connected units of ONE frame whose parts come within a
    metre of each other (a viaduct between two halls, which the §16g chain
    never links through) are one group, moving with the larger; a unit 5 m
    off keeps its own zero."""
    m_lat = 111_132.954
    a = [(40.0, -3.0, 40.001, -2.999)] * 3
    b = [(40.001 + 0.5 / m_lat, -3.0, 40.002, -2.999)]
    c = [(40.002 + 5.5 / m_lat, -3.0, 40.003, -2.999)]
    got = OFS.merge_frame_roots({"fu:1": a, "fu:2": b, "fu:3": c})
    assert got == {"fu:1": "fu:1", "fu:2": "fu:1", "fu:3": "fu:3"}


def test_r5_an_airside_group_sits_on_its_foundation_plane():
    """RULINGS 2026-10-22q as read by round 5: the airside floor is the
    FOUNDATION — the lowest substantial plane of the edge-contact feet
    (the highest plane of ``airside z - y``).  KMCI: the concourse walls
    (y -1.1, candidates ~306) are upper storeys over the curb plane
    (y -5.8, candidate 310.7); a stray wall strip is no plane."""
    from auto_patch_v2.airport.airside_group_seat import floor_plane
    concourse = [306.0] * 900 + [305.0] * 460 + [304.0] * 110
    curb = [310.7] * 250
    assert floor_plane(concourse + curb) == 310.7
    # a stray piece: 12 deep feet over 66 halls' feet is not a floor
    halls = [104.3] * 35 + [100.2] * 14 + [105.0] * 5 + [106.0] * 12
    assert abs(floor_plane(halls + [111.3] * 12) - 104.3) < 0.8
    assert floor_plane([]) is None
