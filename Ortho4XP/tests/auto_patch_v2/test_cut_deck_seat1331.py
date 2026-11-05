"""Owner RULINGS 2026-10-26d (Q142 "b", #1331): a pack HARD DECK over the
pack's own cut sits flush with the solved surface it carries — the
taxiway where it drives onto the deck, read one step outside the deck's
end lines (the trench is under its edges) — and is never left at the
pack's shared zero.  A deck over no pack cut is left as it was (22n (2)).
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import cut_deck_seat as CDS
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.model.frame import m_per_deg_exact

LAT, LON = 40.0, -3.0
ML, MO = m_per_deg_exact(LAT)
#: the deck slab: 40 m east-west, 30 m north-south, top y 0.0 (a taxiway
#: runs NORTH-SOUTH over it; the road in the trench under it EAST-WEST)
HALF_X, HALF_Z = 20.0, 15.0
N, S = LAT + HALF_Z / ML, LAT - HALF_Z / ML
TAXI_N, TAXI_S, TRENCH = 100.0, 100.2, 94.0


def _deck_obj(tmp_path, y=0.0):
    """An OBJ8 whose only geometry is one ATTR_hard_deck quad at ``y``."""
    v = [(-HALF_X, y, -HALF_Z), (HALF_X, y, -HALF_Z), (HALF_X, y, HALF_Z), (-HALF_X, y, HALF_Z)]
    tris = [v[0], v[2], v[1], v[0], v[3], v[2]]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(tris)} 0 0 {len(tris)}"]
    out += [f"VT {p[0]:.4f} {p[1]:.4f} {p[2]:.4f} 0 1 0 0 0" for p in tris]
    out += [f"IDX {i}" for i in range(len(tris))]
    out += ["ATTR_hard_deck concrete", f"TRIS 0 {len(tris)}"]
    path = tmp_path / "deck.obj"
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _member(path):
    return types.SimpleNamespace(deck_kind="flag", deck_top_y=0.0, authored_path=path,
                                 heading_deg=0.0, resource="objects/deck.obj", zero_y=0.0,
                                 origin=(LAT, LON))


def _record(zero=77.0):
    """The deck body as the stack left it: riding a shared zero ``zero``."""
    a = AR.Anchor(AR.OTHER, LAT, LON, TRENCH - zero, "carried by the stack", TRENCH,
                  offset=(0.0, TRENCH - zero, 0.0))
    box = (S - 1e-6, LON - HALF_X / MO - 1e-6, N + 1e-6, LON + HALF_X / MO + 1e-6)
    b = Body(0, AR.OTHER, (), a, "objects/deck__b0.obj", merged_into="objects/shell__b0.obj",
             geom_box=box, plan_box=box)
    return Split(0, "dsf:obj0", "objects/deck.obj", "/x/deck.obj", LAT, LON, 0.0, (b,))


def _surface(n_role="cross_connector", ew_role="tunnel_trench"):
    """The taxiway north and south of the deck; the trench under it and
    its ramps east and west (``tunnel_trench`` is a STRUCTURE role the law
    registers airside — never the surface the deck carries)."""
    def surface(la, lo):
        if la > N + 1e-7:
            return TAXI_N
        if la < S - 1e-7:
            return TAXI_S
        return TRENCH

    class Roles:
        def roles_many(self, las, los):
            return [n_role if (a > N + 1e-7 or a < S - 1e-7) else ew_role for a in las]
    surface.roles = Roles()
    return surface


def _cut(pad_m=10.0):
    """The pack cut's footprint ring, ``pad_m`` beyond the deck."""
    dn, de = (HALF_Z + pad_m) / ML, (HALF_X + pad_m) / MO
    return ((LAT - dn, LON - de), (LAT - dn, LON + de), (LAT + dn, LON + de),
            (LAT + dn, LON - de))


def _seat(tmp_path, cuts, surface=None, counts=None):
    m = _member(_deck_obj(tmp_path))
    return CDS.seat_cut_decks(_record(), m, (LAT, LON), surface or _surface(), cuts, 2.0,
                              0.5, {} if counts is None else counts)


def _zero(b):
    return b.anchor.surface_z - b.anchor.y_zero


def test_a_deck_over_the_packs_cut_sits_flush_with_the_taxiway(tmp_path):
    """LGAV ``Trench_00`` over ``Trench_02``: the deck stood at the stack's
    zero; it now meets the taxiway at its two end lines (100.0 / 100.2),
    never the trench under its edges (94.0)."""
    counts: dict = {}
    rec = _seat(tmp_path, (_cut(),), counts=counts)
    b = rec.bodies[0]
    assert abs(_zero(b) - 0.5 * (TAXI_N + TAXI_S)) < 1e-6
    assert b.anchor.datum and not b.merged_into
    assert "RULINGS 2026-10-26d" in b.anchor.reason
    assert counts["cut_deck_bodies"] == 1
    # the offset the file bakes is the anchor's own (R1: renamed for it)
    assert b.anchor.offset[1] == b.anchor.y_zero
    assert b.new_resource != "objects/deck__b0.obj"


def test_a_deck_over_no_pack_cut_is_left_as_it_was(tmp_path):
    """22n (2): a deck over an OSM cut, or over nothing, keeps its seat."""
    rec0 = _record()
    m = _member(_deck_obj(tmp_path))
    assert CDS.seat_cut_decks(rec0, m, (LAT, LON), _surface(), (), 2.0, 0.5, {}) is rec0
    far = tuple((la + 0.01, lo) for la, lo in _cut())
    assert CDS.seat_cut_decks(rec0, m, (LAT, LON), _surface(), (far,), 2.0, 0.5, {}) is rec0


def test_a_road_deck_reads_the_road_when_no_taxiway_drives_onto_it(tmp_path):
    rec = _seat(tmp_path, (_cut(),), surface=_surface(n_role="service_road"))
    assert abs(_zero(rec.bodies[0]) - 0.5 * (TAXI_N + TAXI_S)) < 1e-6


def test_the_trench_is_never_the_carried_surface(tmp_path):
    """With nothing but the cut's own structure roles around it, the deck
    has no end lines and stays where it was (counted)."""
    counts: dict = {}
    rec0 = _record()
    m = _member(_deck_obj(tmp_path))
    got = CDS.seat_cut_decks(rec0, m, (LAT, LON), _surface(n_role="tunnel_ramp"),
                             (_cut(),), 2.0, 0.5, counts)
    assert got is rec0 and counts["cut_deck_no_end_lines"] == 1


def test_cut_rings_are_read_off_the_seat_records_once():
    ring = [[40.0, -3.0], [40.0, -2.999], [40.001, -2.999]]
    recs = [{"id": "a", CDS.CUT_RING: ring}, {"id": "b", CDS.CUT_RING: ring}, {"id": "c"}]
    assert CDS.cut_rings(recs) == (tuple((a, b) for a, b in ring),)


def test_the_planar_cut_is_stamped_on_its_objects_seat_record():
    """``pipeline/rebake_inputs`` publishes each OBJECT cut's footprint
    ring as ``[lat, lon]`` on its placements' seat records."""
    from auto_patch_v2.pipeline.rebake_inputs import _stamp_cut_rings
    tn = types.SimpleNamespace(source="object", objects=("dsf:obj1",), wall_path=(),
                               footprint=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)))
    osm = types.SimpleNamespace(source="osm", objects=(), footprint=((0.0, 0.0),) * 3,
                                wall_path=())
    frame = types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (40.0 + y, -3.0 + x)))
    seats = {"dsf:obj1": {"id": "dsf:obj1"}}
    _stamp_cut_rings(seats, types.SimpleNamespace(structures=(tn, osm)),
                     types.SimpleNamespace(frame=frame))
    assert seats["dsf:obj1"][CDS.CUT_RING] == [[40.0, -3.0], [40.0, 7.0], [50.0, 7.0]]


def test_a_bridge_frame_zero_keeps_a_deck_seated_over_its_cut(tmp_path):
    """LGAV 1.0.464: the trench stack carries two taxiway decks over two
    pack cuts; the refused-bridge frame zero (10-22c/d) read off the first
    deck put the second 3.1 m under its taxiway.  A body this reading
    seated keeps its seat (``seated``); the frame's other bodies move."""
    from auto_patch_v2.airport import open_frame_seat as OFS
    rec = _seat(tmp_path, (_cut(),))
    b = rec.bodies[0]
    assert CDS.seated(b) and not CDS.seated(_record().bodies[0])
    m = types.SimpleNamespace(resource="objects/deck.obj", zero_y=0.0)
    stack = _record(zero=77.0).bodies[0]
    both = Split(0, "dsf:obj0", "objects/deck.obj", "/x/deck.obj", LAT, LON, 0.0, (b, stack))
    out = OFS.frame_zero(both, m, 76.0, "one bridge frame", keep=CDS.seated)
    assert out.bodies[0] is b and abs(_zero(out.bodies[0]) - 0.5 * (TAXI_N + TAXI_S)) < 1e-6
    assert abs(_zero(out.bodies[1]) - 76.0) < 1e-6


def _rider(low_y, zero=77.0, frac=1.0):
    """A rail on the deck (``low_y`` its authored y), standing on its
    own ground at ``zero``; ``frac`` of its box over the deck."""
    a = AR.Anchor(AR.OTHER, LAT, LON, TRENCH - zero, "own ground", TRENCH,
                  offset=(0.0, TRENCH - zero, 0.0))
    w = 2.0 * HALF_X / MO
    lo0 = LON - HALF_X / MO + (1.0 - frac) * w
    box = (S, lo0, N, lo0 + w)
    pts = tuple((LAT, lo0 + (k + 0.5) * w / 10.0, low_y) for k in range(10))
    return Body(0, AR.OTHER, (), a, "objects/rail__b0.obj", geom_box=box, plan_box=box,
                geom_pts=pts)


def test_what_stands_on_a_deck_seated_over_its_cut_rides_its_seat(tmp_path):
    """#1883 (LGAV ``Bridge_Fences`` on ``Trench_00``): the deck's pieces
    are read before its bodies, at the zero its body takes, and a rail on
    the deck takes it; a plant on the trench floor under the deck, or a
    body mostly off the deck, does not."""
    m = _member(_deck_obj(tmp_path))
    seats = CDS.cut_seats(m, (LAT, LON), _surface(), (_cut(),), 2.0, 0.5)
    deck = _seat(tmp_path, (_cut(),)).bodies[0]
    assert len(seats) == 1 and abs(seats[0][1] - _zero(deck)) < 1e-6
    assert abs(CDS.seat_under(_rider(0.4), seats, 0.5) - _zero(deck)) < 1e-6
    assert CDS.seat_under(_rider(-6.0), seats, 0.5) is None      # under the deck
    assert CDS.seat_under(_rider(0.4, frac=0.3), seats, 0.5) is None
    assert CDS.seat_under(deck, seats, 0.5) is None              # the deck itself
    assert CDS.cut_seats(m, (LAT, LON), _surface(), (), 2.0, 0.5) == []


def test_the_bridges_own_walls_under_the_deck_ride_it_too(tmp_path):
    """LGAV ``Trench_01`` (the walled bridge at the second site, -12.67 to
    +0.44): its top reaches the deck's slab, so it rides the deck's seat
    (it stood 13.4 m under it at the channel floor's crest plate)."""
    m = _member(_deck_obj(tmp_path))
    seats = CDS.cut_seats(m, (LAT, LON), _surface(), (_cut(),), 2.0, 0.5)
    wall = _rider(-12.0)
    wall = Body(0, AR.OTHER, (), wall.anchor, "objects/wall__b0.obj", geom_box=wall.geom_box,
                plan_box=wall.plan_box,
                geom_pts=wall.geom_pts[:5] + tuple((q[0], q[1], 0.4) for q in wall.geom_pts[5:]))
    assert abs(CDS.seat_under(wall, seats, 0.5) - seats[0][1]) < 1e-6


def test_a_cut_its_packs_deck_frames_rides_the_deck_never_its_authored_seat():
    """Owner 2026-11-05 §0.5 (amends 09q (1)): LGAV ``Trench_02`` stood at
    the stack's zero 2.3 m under the deck seated over it (1.0.465) because
    its crest was in band — "authored (cut)", never re-seated.  A cut a
    co-placed pack deck frames (``Tunnel.cut_frame``, ``planar/cut_frame``)
    is re-seated; the same cut with no deck over it keeps its seat."""
    from auto_patch_v2.airport import authored_seat as AS
    from auto_patch_v2.law import Law
    from auto_patch_v2.pipeline.authored_seats import kept_ids, seat_records

    def tn(oid, frame):
        return types.SimpleNamespace(source="object", objects=(oid,), resource="t.obj",
                                     authored_crest_m=((0.0, 0.0),), cut_frame=frame)
    framed = ((("dsf:obj9", ((0.0, 0.0),), 4.0), ("dsf:obj9", ((5.0, 0.0),), 4.0)))
    pm = types.SimpleNamespace(structures=(tn("dsf:obj1", ()), tn("dsf:obj2", framed)),
                               basins=())
    recs = seat_records(pm, Law.for_airport("ZZZZ"))
    assert recs["dsf:obj1"]["seat"] == AS.SEAT_AUTHORED
    assert recs["dsf:obj2"]["seat"] == AS.SEAT_RESEATED
    assert kept_ids(recs) == {"dsf:obj1"}


def test_the_framed_cut_takes_the_zero_of_the_deck_seated_over_its_ring():
    """Owner 2026-11-05 §0.5: the cut member rides the deck piece seated
    over ITS OWN ring (the piece's box centre inside it), and the residual
    to the frame its floor was read at is reported; a cut with no frame
    zero on its record, or no deck over its ring, rides nothing."""
    ring = [[40.0, -3.0], [40.0, -2.99], [40.01, -2.99], [40.01, -3.0]]
    recs = [{"id": "dsf:obj2", CDS.CUT_RING: ring, CDS.CUT_FRAME_Z: 79.9},
            {"id": "dsf:obj3", CDS.CUT_RING: ring}]
    seats = [((40.5, -2.5, 40.6, -2.4, 0.0), 70.0),          # a deck over another cut
             ((40.004, -2.996, 40.006, -2.994, 0.0), 80.02)]
    zero, res, ring_ll = CDS.framed_zero("dsf:obj2", seats, recs)
    assert abs(zero - 80.02) < 1e-9 and abs(res - 0.12) < 1e-9
    # only the member's bodies standing in the ring ride it (a long
    # object's pieces 1.5 km away keep their own seat)
    near = types.SimpleNamespace(geom_pts=((40.005, -2.995, 0.0), (40.006, -2.994, -4.0)))
    far = types.SimpleNamespace(geom_pts=((40.005, -2.995, 0.0), (40.5, -2.5, -4.0),
                                          (40.5, -2.49, -4.0)))
    assert CDS.stands_in(near, ring_ll, 0.5) and not CDS.stands_in(far, ring_ll, 0.5)
    assert CDS.framed_zero("dsf:obj3", seats, recs) is None
    assert CDS.framed_zero("dsf:obj2", seats[:1], recs) is None


def test_a_cuts_own_cover_never_frames_it():
    """``planar/cut_frame``: a signature-B pair's COVER (VHHH, EGLL ``3.obj``
    over ``3a.obj``) is the cut's roof, never a deck that frames it — read
    as one, EGLL's floor moved 1.39 m off its walls' bottom (Q167)."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.cut_frame import frame_cuts
    from shapely.geometry import box
    shell = types.SimpleNamespace(id="dsf:obj1", xy=(0.0, 0.0), heading_deg=0.0, path="s.obj")
    cover = types.SimpleNamespace(id="dsf:obj2", xy=(0.0, 0.0), heading_deg=0.0, path="c.obj",
                                  deck_kind="flag", hard_deck=box(-10, -10, 10, 10))
    tn = types.SimpleNamespace(id="object-cut:s.obj@0", source="object", objects=("dsf:obj1",),
                               footprint=((-12, -12), (12, -12), (12, 12), (-12, 12)),
                               mouth_z=70.0, notes=())
    airport = types.SimpleNamespace(dsf_objects=(), frame=types.SimpleNamespace(
        transformers=lambda: (None, None)))
    out, notes = frame_cuts([tn], [shell, cover], object(), object(), airport,
                            Law.for_airport("ZZZZ"), (("object-cut:s.obj@0", "dsf:obj2"),))
    assert out == [tn] and notes == []
