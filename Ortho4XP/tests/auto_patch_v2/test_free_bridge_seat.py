"""Owner RULINGS 2026-10-22m / 22p, class B (OTHH +25+051 Bridge_04 canal
bridge 25.25153, 51.62030 and the flyover ramps by 25.25185, 51.61724): a
frame that IS a free-standing bridge — its deck plus piers and rails on one
anchor, no building — seats its deck flush at the end nearer its ground,
every body with it (``airport/free_bridge_seat``); the end reading takes the
deck top AT each end and reads 22p's road-under only with the anchor under
the deck (``airport/bridge_approach``).  #2065 S3: only a deck the rebake
plan published FREE (``plate_kind == "free"``) is admitted, one zero per
published bridge id over its published land ends, at its published tops."""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import bridge_approach as BA
from auto_patch_v2.airport import deck_end_read as DE
from auto_patch_v2.airport import free_bridge_seat as FB
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.planar import overpass_deck as OD
from shapely.geometry import box as _sbox
from tests.auto_patch_v2.test_overpass_deck1692 import FRAME, LAW, THICK

# a 78 m canal bridge along latitude: banks at 40.0 and 40.0007, water between
RING = ((40.0, -3.0), (40.0, -2.9998), (40.0007, -2.9998), (40.0007, -3.0))
ENDS = (((40.0, -3.0), (40.0, -2.9998)), ((40.0007, -3.0), (40.0007, -2.9998)))
DECK = "objects/bridge_deck.obj"


def _member(**kw):
    base = dict(resource=DECK, id="dsf:obj1", deck_kind="flag", deck_top_y=4.65,
                deck_datum_z=None, deck_ring=RING, deck_ends=ENDS,
                deck_end_stations=(), plate_kind="free", plate_y=None, plate_stations=(),
                parts=(), authored_path="", heading_deg=0.0, free_bridge="free:dsf:obj1",
                deck_end_tops=(4.65, 4.65), deck_end_land=(True, True))
    base.update(kw)
    return types.SimpleNamespace(**base)


def _canal(la, lo):
    return 0.0 if 40.00001 < la < 40.00069 else 3.9


_canal.water = lambda la, lo: 40.00001 < la < 40.00069


def _staged(*members, keys=None):
    return [types.SimpleNamespace(m=m, bridge=list(keys or [DECK]), boxes=[None])
            for m in members]


def test_a_canal_bridge_frame_with_piers_is_seated_flush_at_its_banks():
    pier = _member(resource="objects/bridge_piers.obj", id="dsf:obj2", deck_kind="",
                   deck_top_y=None, deck_ring=None)
    zs = FB.free_bridge_zeros(_staged(_member(), pier), _canal,
                              origin=(40.00035, -2.9999), agl_m=-0.65, step_m=5.0,
                              walk_max_m=60.0, level_tol_m=0.3)
    zero, why, _box = zs[DECK]
    # deck top 4.65 flush with the 3.9 banks; the piers sink into the canal
    assert abs(zero + 4.65 - 3.9) < 1e-6 and "22m" in why


def test_only_a_deck_published_free_is_admitted():
    """#2065 S3: a deck the witness never published (an all-deck frame's, a
    plated one, one beside a building) keeps its own reader."""
    for kw in ({"plate_kind": ""}, {"plate_kind": "overpass", "plate_y": 0.0},
               {"deck_end_land": ()}):
        st = _staged(_member(**kw))
        assert FB.free_bridge_zeros(st, _canal, origin=(40.00035, -2.9999), agl_m=0.0,
                                    step_m=5.0) == {}


def test_a_ramp_is_flush_at_the_end_whose_ground_less_its_top_is_highest():
    def land(la, lo):
        return 296.0 if la < 40.00035 else 294.0
    d = AR.Datum(8.3, (), "deck top", ends=ENDS, step_m=5.0)
    s = BA.approach_seat(d, land, tops=(1.0, -0.5))
    # 296 - 1.0 = 295.0 beats 294 + 0.5 = 294.5: end 1 flush, end 2 floats 0.5
    assert abs(s.zero - 295.0) < 1e-6
    # without the ends' tops the crown would bury both ends 7 m
    assert abs(BA.approach_seat(d, land).zero - (296.0 - 8.3)) < 1e-6


def test_22p_reads_the_road_under_only_with_the_anchor_under_the_deck():
    flat = lambda la, lo: 3.96                                 # noqa: E731
    under = AR.Datum(8.3, (), "deck top", ends=ENDS, step_m=5.0, ring=RING)
    kept = BA.approach_seat(under, flat, origin=(40.00035, -2.9999), authored_agl_m=4.0)
    assert "22p" in kept.reason and abs(kept.zero - 7.96) < 1e-6
    off = BA.approach_seat(under, flat, origin=(40.002, -2.9999), authored_agl_m=4.0,
                           tops=(-0.1, 0.4))
    assert "22p" not in off.reason and abs(off.zero - 4.06) < 1e-6


def test_every_body_of_a_one_deck_frame_takes_the_decks_zero():
    def body(i, zero, key="", box=None):
        a = AR.Anchor(AR.OTHER, 40.0, -3.0, 3.9 - zero, "own", 3.9,
                      offset=(0.0, 3.9 - zero, 0.0))
        return Body(i, AR.OTHER, (i,), a, f"objects/b__b{i}.obj", bridge_of=key,
                    geom_box=box)
    far = (41.0, -3.0, 41.001, -2.999)
    rec = Split(0, "dsf:obj1", "objects/rails.obj", "/x/objects/rails.obj", 40.0, -3.0,
                0.0, (body(0, 1.78, DECK), body(1, 1.78, box=RING[0] + RING[2]),
                      body(2, -0.75, DECK + "#1"), body(3, 1.78, box=far)))
    m = types.SimpleNamespace(resource="objects/rails.obj", zero_y=0.0)
    box = RING[0] + RING[2]
    out = FB.free_bridge_seat(rec, m, {DECK: (-0.75, "why", box)})
    assert {round(b.anchor.surface_z - b.anchor.y_zero, 2) for b in out.bodies} == {-0.75}
    # several decks: a body no footprint names goes with the deck its box
    # overlaps; one overlapping none keeps its seat
    two = FB.free_bridge_seat(rec, m, {DECK: (-0.75, "a", box),
                                       "objects/other.obj": (9.0, "b", (50.0, 0.0, 50.1, 0.1))})
    assert [round(b.anchor.surface_z - b.anchor.y_zero, 2)
            for b in two.bodies] == [-0.75, -0.75, -0.75, 1.78]


# ── round 2 (spec othh-deck-round2-spec.md S1-S4) ────────────────────────

M_LAT = 111_000.0          # about; the end lines below are built in degrees


def _quad(x0, z0, x1, z1, y):
    """Two upward triangles of a flat plate at height ``y``."""
    a, b, c, d = (x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)
    return [(a, b, c), (a, c, d)]


def _obj(path, plates):
    """An OBJ8 whose every triangle is ``ATTR_hard_deck`` (``plates``:
    lists of triangles)."""
    verts = [p for tris in plates for tri in tris for p in tri]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
    out += [f"VT {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} 0 1 0 0 0" for v in verts]
    out += [f"IDX {i}" for i in range(len(verts))]
    out += ["ATTR_hard_deck concrete", f"TRIS 0 {len(verts)}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def test_a_22p_bridge_with_its_anchor_off_the_ring_keeps_its_clearance_on_the_old_path():
    """S1: the all-deck datum (``anchor_rule.datum_of``) carries no ring, so
    22p reads the road at an anchor 4 m off the deck as before (F7)."""
    flat = lambda la, lo: 3.96                                 # noqa: E731
    d = AR.datum_of(_member(), abutment_step_m=5.0, free_standing=True)
    assert d is not None and d.ring == ()
    off = (40.0, -3.0 - 4.0 / 85_000.0)                        # 4 m west of the ring
    s = BA.approach_seat(d, flat, origin=off, authored_agl_m=4.0)
    assert "22p" in s.reason and abs(s.zero - 7.96) < 1e-6


def _deck(res, lat0, lat1, lon0=-3.0, lon1=-2.9998, top=4.65, bridge="free:a",
          land=(True, True)):
    ring = ((lat0, lon0), (lat0, lon1), (lat1, lon1), (lat1, lon0))
    ends = (((lat0, lon0), (lat0, lon1)), ((lat1, lon0), (lat1, lon1)))
    return _member(resource=res, deck_ring=ring, deck_ends=ends, deck_top_y=top,
                   deck_end_tops=(top, top), free_bridge=bridge, deck_end_land=land)


class _NoPad:
    """Face roles with no object pad anywhere (no building in the frame)."""

    def roles_many(self, la, lo):
        return [""] * len(la)


def _bridge_frame(*members):
    """Staged members of one bridge frame: each body named by its own
    member, its hull box on no pad."""
    return [types.SimpleNamespace(m=m, bridge=[m.resource], boxes=[(40.0, -3.0, 40.0, -3.0)])
            for m in members]


def _on(f):
    f.roles = _NoPad()
    return f


def test_one_published_bridge_takes_one_zero_and_two_take_two():
    """#2065 S3: the decks of one published bridge id take one zero (the
    highest ``ground - top`` over its land ends); two ids, two zeros."""
    @_on
    def land(la, lo):
        return 5.0 if la < 40.0005 else 3.0
    pier = _member(resource="objects/piers.obj", deck_kind="", deck_top_y=None, deck_ring=None)
    a = _deck("objects/a.obj", 40.0, 40.0005)
    b = _deck("objects/b.obj", 40.0005, 40.001)
    st = _bridge_frame(a, b, pier)
    zs = FB.free_bridge_zeros(st, land, origin=(40.002, -2.9999), agl_m=0.0, step_m=5.0)
    # one bridge: flush at a's south end (5.0 - 4.65), b's north end floats
    assert abs(zs["objects/a.obj"][0] - 0.35) < 1e-6
    assert zs["objects/b.obj"][0] == zs["objects/a.obj"][0]
    gap = 2.0 / M_LAT
    b2 = _deck("objects/b.obj", 40.0005 + gap, 40.001, bridge="free:b")
    zs2 = FB.free_bridge_zeros(_bridge_frame(a, b2, pier), land,
                               origin=(40.002, -2.9999), agl_m=0.0, step_m=5.0)
    assert abs(zs2["objects/a.obj"][0] - 0.35) < 1e-6
    assert abs(zs2["objects/b.obj"][0] - (3.0 - 4.65)) < 1e-6


def test_a_joint_end_is_no_land_end():
    """#2065 S3 (W7): an end the witness published as a joint is no land
    end — its ground (a hump under the joint) never sets the zero."""
    @_on
    def hump(la, lo):
        return 9.0 if abs(la - 40.0005) < 1e-5 else 3.0
    a = _deck("objects/a.obj", 40.0, 40.0005, land=(True, False))
    b = _deck("objects/b.obj", 40.0005, 40.001, land=(False, True))
    zs = FB.free_bridge_zeros(_bridge_frame(a, b), hump,
                              origin=(40.002, -2.9999), agl_m=0.0, step_m=5.0)
    assert abs(zs["objects/a.obj"][0] - (3.0 - 4.65)) < 1e-6


def test_a_pylon_top_near_an_end_does_not_set_the_end_top(tmp_path):
    """S3: the end's top is the PLATE's own height on the end line (3.5),
    never the maximum within a reach (an upper surface at 11.56 beside it,
    OTHH Bridge_01's LOD0_003)."""
    from auto_patch_v2.airport.airside_deck_seat import end_tops
    from auto_patch_v2.airport.rebake_plan import _mpd
    path = _obj(tmp_path / "deck.obj", [_quad(-8.0, -25.0, 8.0, 25.0, 3.5),
                                        _quad(-8.0, 19.0, 8.0, 25.0, 11.56)])
    origin = (40.0, -3.0)
    ml, mo = _mpd(40.0)
    # obj z = +25 stands 25 m SOUTH of the origin (north = -z)
    lines = [((40.0 - 25.0 / ml, -3.0 - 8.0 / mo), (40.0 - 25.0 / ml, -3.0 + 8.0 / mo)),
             ((40.0 + 25.0 / ml, -3.0 - 8.0 / mo), (40.0 + 25.0 / ml, -3.0 + 8.0 / mo))]
    m = _member(authored_path=path, deck_top_y=11.56)
    assert all(abs(t - 3.5) < 1e-6 for t in DE._plate_end_tops(m, lines, origin, 5.0))
    assert abs(end_tops(m, (list(lines[0]), list(lines[1])), origin, 5.0)[0] - 11.56) < 1e-6


def test_a_free_decks_ends_read_its_published_tops():
    """#2065 S3: a free deck's end reading takes the tops the witness
    published (the driven layer at each route end) — no plate read, no
    rectangle — and the ground at its published end lines."""
    land = lambda la, lo: 3.9                                  # noqa: E731
    r = DE.deck_end_reads(_member(deck_end_tops=(3.58, 2.0)), land,
                          origin=(40.002, -2.9999), agl_m=0.0, step_m=5.0)
    assert [round(e.top, 2) for e in r.ends] == [3.58, 2.0]
    assert all(abs(e.ground - 3.9) < 1e-6 for e in r.ends)


def _crossing(tmp_path, plates):
    path = _obj(tmp_path / "crossing.obj", plates)
    deck = _sbox(-8.0, -25.0, 8.0, 25.0)
    o = types.SimpleNamespace(
        id="dsf:obj9", path="objects/crossing.obj", resolved=path, xy=(0.0, 0.0),
        heading_deg=0.0, kind="OBJECT", anchor_z=100.0, agl_m=0.0, deck_kind="flag",
        hard_deck=deck, deck_top_z=111.0, plan_bbox=deck)
    ways = [types.SimpleNamespace(id=-7, points=[(-60.0, 1.0), (60.0, 1.0)],
                                  tags={"highway": "secondary"})]
    airport = types.SimpleNamespace(frame=FRAME, osm_ways=ways)
    return OD.road_overpasses([o], O.ResourceCache(THICK), types.SimpleNamespace(cells=()),
                              airport, LAW, (), ())


def test_an_overpass_reads_its_clearance_at_the_crossing(tmp_path):
    """S4: the plate over the road beneath stands y 3.5 (an abutment top)
    while an upper surface elsewhere in the frame stands 11.56 — no road
    overpass (< 4.2 m); a plate at 7.5 over the road is one."""
    low, notes = _crossing(tmp_path, [_quad(-8.0, -25.0, 8.0, 25.0, 3.5),
                                      _quad(-8.0, 19.0, 8.0, 25.0, 11.56)])
    assert low == () and "no road overpass" in notes[0]
    (kept,), _n = _crossing(tmp_path, [_quad(-8.0, -25.0, 8.0, 25.0, 7.5)])
    assert abs(kept.top_y - 7.5) < 1e-6


# ── A2: plate_kind "free" IS the class decision ─────────────────────────

class _Airside:
    """Every face role under the ring is an apron (airside)."""

    def roles_many(self, la, lo):
        return ["apron"] * len(la)


def test_a_frame_with_a_second_flag_deck_carrying_a_datum_takes_the_bridge_zero():
    """A2 (placement_plan): the free deck's zero is the frame's; a second
    flag deck over a graded face and its bodies ride it, never their own
    datum."""
    pier = _member(resource="objects/piers.obj", deck_kind="", deck_top_y=None, deck_ring=None)
    other = _member(resource="objects/ramp.obj", id="dsf:obj3", plate_kind="",
                    deck_datum_z=3.96, free_bridge="", deck_end_land=())
    zs = FB.free_bridge_zeros(_staged(_member(), other, pier), _canal,
                              origin=(40.00035, -2.9999), agl_m=-0.65, step_m=5.0,
                              walk_max_m=60.0, level_tol_m=0.3)
    assert set(zs) == {DECK}
    a = AR.Anchor(AR.OTHER, 40.0, -3.0, 5.0, "own", 3.96, offset=(0.0, 5.0, 0.0))
    rec = Split(0, "dsf:obj3", "objects/ramp.obj", "/x/objects/ramp.obj", 40.0, -3.0, 0.0,
                (Body(0, AR.OTHER, (0,), a, "objects/ramp__b0.obj"),))
    out = FB.free_bridge_seat(rec, other, zs)
    assert {round(b.anchor.surface_z - b.anchor.y_zero, 3) for b in out.bodies} \
        == {round(zs[DECK][0], 3)}


def test_a_free_member_is_never_class_a_and_owns_its_datum():
    from auto_patch_v2.airport import airside_deck_seat as AD
    from auto_patch_v2.airport.placement_family import member_is_bridge_deck
    surf = lambda la, lo: 3.9                                   # noqa: E731
    surf.roles = _Airside()
    held = _member(plate_kind="", deck_datum_z=3.96)
    assert AD._airside_witness(held, (), surf) is not None      # today's class A reading
    free = _member(deck_datum_z=None)
    assert AD._airside_witness(free, (), surf) is None
    assert AD.airside_zero(free, (), surf, 5.0) is None
    # a SIGNATURE free deck (datum cleared at the plan) never rides a unit
    sig = _member(deck_kind="signature", deck_datum_z=None)
    assert AD.deck_owns_its_datum(sig)
    assert not AD.deck_owns_its_datum(_member(deck_kind="signature", plate_kind=""))
    unit = types.SimpleNamespace(members=(sig, _member(deck_kind="", deck_top_y=None)))
    assert member_is_bridge_deck(unit, sig)
