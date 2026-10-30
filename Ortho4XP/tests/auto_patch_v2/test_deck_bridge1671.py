"""#1671 / #1640 twins (owner RULINGS 2026-10-30a; Q-A as ruled 2026-10-30:
"the cut should be the road width, then a bank sloping from the road edge up
to just short of the bridge width"): ONE reading of a pack hard deck the
taxiway drives across (``planar/deck_bridge``), read by the structure pass,
the floor rows (``constraints/edge_floor``), the rigid row and the floor's
release (``constraints/edge_deck``, ``walled_plate.release_across``), the
object stage's plate (``pipeline/rebake_inputs``, ``airside_deck_seat``) and
the portal reading (``airport/portal_objects``)."""
from __future__ import annotations

import types

from auto_patch_v2.airport import airside_deck_seat as ADS
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.constraints import edge_deck as ED
from auto_patch_v2.constraints import edge_floor as EF
from auto_patch_v2.constraints import walled_plate as WP
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Linear, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline import rebake_inputs as RI
from auto_patch_v2.planar import deck_bridge as DB
from shapely.geometry import LineString
from shapely.geometry import box as _sbox

LAW = Law.for_airport("")
THICK = LAW.tables.structures.basin.min_solid_thickness_m
FRAME = Frame("ZZZZ", origin=(36.0, -86.0), identity_dp=11)
TAXI = "primary_parallel"


def _box(x, z, w, d, h, y0=0.0):
    x1, z1, y1 = x + w, z + d, y0 + h
    v = [(x, y0, z), (x1, y0, z), (x1, y0, z1), (x, y0, z1),
         (x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
             (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return [(v[a], v[b], v[c]) for a, b, c in faces]


def _write(path, comps, hard=()):
    verts = [p for comp in comps for tri in comp for p in tri]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
    out += [f"VT {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} 0 1 0 0 0" for v in verts]
    out += [f"IDX {i}" for i in range(len(verts))]
    k = 0
    for i, comp in enumerate(comps):
        if i in hard:
            out.append("ATTR_hard_deck concrete")
        out.append(f"TRIS {k} {3 * len(comp)}")
        k += 3 * len(comp)
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _deck(tmp_path, y0=0.0, walls=True):
    """A 40 x 40 m deck plate (top y 6.0) on two abutment blocks reaching
    0.2 m under the zero, centred on the anchor (frame -20..20 both ways) —
    WALLS along the road under it (inner faces x = -17 / +17) — or, with
    ``walls`` false, on four 2 m piers at its corners (no wall)."""
    if walls:
        legs = [_box(-20.0, -20.0, 3.0, 40.0, 5.9, y0=-0.2 + y0),
                _box(17.0, -20.0, 3.0, 40.0, 5.9, y0=-0.2 + y0)]
    else:
        legs = [_box(x, z, 2.0, 2.0, 5.9, y0=-0.2 + y0)
                for x in (-20.0, 18.0) for z in (-20.0, 18.0)]
    return _write(tmp_path / ("deck.obj" if walls else "piers.obj"),
                  [_box(-20.0, -20.0, 40.0, 40.0, 0.3, y0=5.7 + y0)] + legs, hard=(0,))


def _placed(path, oid, kind="flag", xy=(0.0, 0.0)):
    deck = _sbox(-20.0 + xy[0], -20.0 + xy[1], 20.0 + xy[0], 20.0 + xy[1])
    return types.SimpleNamespace(
        id=oid, path=f"objects/{oid}.obj", resolved=path, xy=xy, heading_deg=0.0,
        kind="OBJECT", anchor_z=100.0, agl_m=0.0, deck_kind=kind,
        hard_deck=deck if kind else None, deck_top_z=106.0 if kind else None,
        plan_bbox=deck)


def _cell(i, role, poly):
    return Cell(i, role, f"{role}:{i}", tuple(poly.exterior.coords)[:-1], (), None, None,
                "airside", "pavement", {})


def _classification(both_ends=True, dy=0.0):
    """A taxiway running E-W across the deck (y -10..10), on both sides of
    it or (``both_ends`` false) only to its west."""
    cells = [_cell(0, TAXI, _sbox(-100.0, -10.0 + dy, -20.0, 10.0 + dy))]
    if both_ends:
        cells.append(_cell(1, TAXI, _sbox(20.0, -10.0 + dy, 100.0, 10.0 + dy)))
    return types.SimpleNamespace(cells=tuple(cells))


AIRPORT = types.SimpleNamespace(frame=FRAME)


def _read(tmp_path, objs=None, cl=None, trenches=(), walls=True):
    o = _placed(_deck(tmp_path, walls=walls), "dsf:obj7")
    return DB.deck_bridges(objs or [o], O.ResourceCache(THICK), cl or _classification(),
                           AIRPORT, LAW, trenches)


def test_a_deck_the_taxiway_drives_across_is_a_bridge_seated_at_its_two_end_lines(tmp_path):
    """27c / 30a (1): the pavement runs across the deck; its END LINES are
    the two facing contacts (x = -20 and x = +20, where the taxiway drives
    on); the depth is the deck top less the frame's lowest solid."""
    (db,), notes = _read(tmp_path)
    assert not notes
    xs_a = {round(x) for x, _y in db.seats_a}
    xs_b = {round(x) for x, _y in db.seats_b}
    assert {xs_a.pop(), xs_b.pop()} == {-20, 20} and not xs_a and not xs_b
    assert all(-10.5 <= y <= 10.5 for _x, y in db.seats_a + db.seats_b)
    assert abs(db.top_a - 6.0) < 1e-6 and abs(db.top_b - 6.0) < 1e-6
    assert abs(db.bottom_y + 0.2) < 1e-6 and abs(db.depth_m - 6.2) < 1e-6
    assert db.members == ("dsf:obj7",)


def test_a_deck_the_taxiway_only_touches_is_no_bridge(tmp_path):
    got, notes = _read(tmp_path, cl=_classification(both_ends=False))
    assert got == () and "no pavement runs across it" in notes[0]


def test_a_co_placed_trench_object_states_the_walls_and_the_walls_define_the_cut(tmp_path):
    """Q-A as ruled (EDDF ``Bridge_3`` + ``Tunnel_3``): where the pack
    models walls, the walls define the cut — the frame is the trench
    object's, never a hard-deck bridge here."""
    deck = _placed(_deck(tmp_path), "dsf:obj7")
    trench = _placed(_deck(tmp_path), "dsf:obj8", kind="")
    trench.path = "objects/trench.obj"
    t = types.SimpleNamespace(object_id="dsf:obj8", depth_m=6.0)
    got, notes = _read(tmp_path, objs=[deck, trench], trenches=[t])
    assert got == () and "they define the cut" in notes[0]


def _bridge(tmp_path, walls=False):
    (db,), _n = _read(tmp_path, walls=walls)
    return db


def test_the_mouth_stands_at_the_deck_midline_and_the_cut_banks_to_its_edge(tmp_path):
    """Q-A as ruled: each mouth of the bore cuts half the deck (no end cap
    across the trench); the floor is the road's width, the footprint the
    deck ring ``wall_gap_m`` inside its edge — the bank from the road edge
    up to just short of the deck."""
    db = _bridge(tmp_path)
    axis = LineString([(0.0, 23.0), (0.0, 120.0)])
    moved, d = DB.deck_mouth(axis, (0.0, -1.0), db)
    assert abs(d - 23.0) < 1e-6 and abs(moved.coords[0][1]) < 1e-6
    ramp = _sbox(-4.0, -10.0, 4.0, 100.0)
    outer = ramp.buffer(1.6, join_style="mitre")
    r2, o2 = DB.deck_cut(db, moved, ramp, outer, 0.6)
    assert abs(r2.bounds[1]) < 1e-6 and abs(o2.bounds[1]) < 1e-6      # the midline
    assert abs(o2.bounds[0] + 19.4) < 1e-6 and abs(o2.bounds[2] - 19.4) < 1e-6
    climb, level, stretch, seats, other = DB.deck_seats(db, moved, (db,), 0.6)
    assert abs(climb - 20.6) < 1e-6 and level is None and stretch == () and other is None
    assert [s[0] for s in seats] == ["dsf:obj7", "dsf:obj7"] and len(seats[0][1]) >= 3


def test_a_walled_deck_cuts_the_floor_to_the_walls_inner_faces(tmp_path):
    """#1692, RULINGS 2026-10-30f (3): where the frame models walls under
    the deck (its abutment blocks' inner faces at x = -17 / +17, rising from
    its bottom to the deck), the floor runs to them and the rim stands
    ``wall_gap_m`` behind them — no bank climbs the walls; a deck on piers
    keeps the 30b bank."""
    db = _bridge(tmp_path, walls=True)
    r, n, faces = db.walls
    assert abs(abs(r[1]) - 1.0) < 1e-6 and faces
    floor, rim = DB._walled_trench(db, 0.6)
    assert abs(floor.bounds[0] + 17.0) < 1e-6 and abs(floor.bounds[2] - 17.0) < 1e-6
    assert abs(rim.bounds[0] + 17.6) < 1e-6 and abs(rim.bounds[2] - 17.6) < 1e-6
    axis, _d = DB.deck_mouth(LineString([(0.0, 23.0), (0.0, 120.0)]), (0.0, -1.0), db)
    ramp = _sbox(-4.0, -10.0, 4.0, 100.0)
    r2, o2 = DB.deck_cut(db, axis, ramp, ramp.buffer(1.6, join_style="mitre"), 0.6)
    assert abs(r2.bounds[0] + 17.0) < 1e-6 and abs(r2.bounds[2] - 17.0) < 1e-6
    assert abs(o2.bounds[0] + 17.6) < 1e-6 and abs(r2.bounds[1]) < 1e-6
    assert DB._walled_trench(_bridge(tmp_path), 0.6) is None     # piers are no wall


def test_between_two_decks_the_trench_stays_at_the_floors_to_the_halfway_line(tmp_path):
    """Q271 b: two decks over one road 20 m apart (KBNA's taxiway-L pair):
    each mouth's trench runs from its deck's midline to the line halfway
    across the open stretch, the floor linear between the two decks'
    bottoms; never a climb."""
    a = _placed(_deck(tmp_path), "dsf:obj7")
    b = _placed(_deck(tmp_path), "dsf:obj7b", xy=(0.0, -60.0))
    cl = types.SimpleNamespace(cells=_classification().cells + _classification(dy=-60.0).cells)
    dbs, _n = DB.deck_bridges([a, b], O.ResourceCache(THICK), cl, AIRPORT, LAW)
    assert len(dbs) == 2
    top = next(d for d in dbs if d.object_id == "dsf:obj7")
    axis, _d = DB.deck_mouth(LineString([(0.0, -23.0), (0.0, -200.0)]), (0.0, 1.0), top)
    climb, level, stretch, seats, other = DB.deck_seats(top, axis, dbs, 0.6)
    assert other is not None and other.object_id == "dsf:obj7b"
    assert abs(level - 30.0) < 1e-6 and abs(climb - 30.0) < 1e-6
    assert abs(stretch[0] - 20.0) < 1e-6 and abs(stretch[1] - 40.0) < 1e-6
    assert len(seats) == 4


def test_every_end_line_station_is_held_flush_with_the_deck():
    """#1692, RULINGS 2026-10-30a (1) / 30f (4): every station of every end
    line stands within ``[bridge] deck_flush_m`` of the deck top read from
    the one zero — not only the means (a taxiway's cross-fall left one end
    line 0.76 m from end to end under a flat deck)."""
    ends = [(((1, 0.5), (2, 0.5)), 6.0), (((3, 0.5), (4, 0.5)), 6.1)]
    rows = ED._station_rows("dsf:obj7", ends, 0.04)
    assert len(rows) == 4 and all(r.source.ruling == ED.RIGID for r in rows)
    r3 = next(r for r in rows if dict(r.terms).get(3) == 1.0)
    assert abs(r3.lo - 0.06) < 1e-9 and abs(r3.hi - 0.14) < 1e-9
    r1 = next(r for r in rows if "end 0 station v1" in r.source.inputs[1])
    assert dict(r1.terms) == {1: 0.5, 2: -0.5} and abs(r1.hi - 0.04) < 1e-9


def test_the_floor_hangs_from_the_mean_of_both_end_lines_and_an_edge_seat_is_unchanged():
    """30a (2): a seat SET carries its mean; a deck's own seat is half of
    each end line's; one vertex is the edge bridge's row byte for byte."""
    src = Source("structures", "tunnel.mouth_depth_m (2026-09-03b)", ())
    one = EF.sloped_floor_rows([(5.0, [9])], ((3, 6.0), (4, 2.0)), (0.0, 10.0), src)
    assert one[0].terms == ((9, 1.0), (3, -0.5), (4, -0.5)) and one[0].hi == -4.0
    a = EF._mean_terms([1, 2])
    b = EF._mean_terms([3])
    seat = EF._mean_terms([], ((a, 0.5), (b, 0.5)))
    assert seat == ((1, 0.25), (2, 0.25), (3, 0.5))
    rows = EF.seat_pair(9, (seat, 6.2), src)
    assert dict(rows[0].terms) == {9: 1.0, 1: -0.25, 2: -0.25, 3: -0.5}
    assert abs(rows[0].hi + 6.2) < 1e-12 and abs(rows[1].hi - 6.2) < 1e-12


def test_the_rigid_row_never_releases_the_airside_and_the_floor_is_pulled_by_nothing_outside():
    """30a (1) / §4 (3): the rigid row's first vertex is airside — never a
    governed vertex; a pair row joining the floor to a vertex outside the
    trench is withdrawn, the trench's own law kept."""
    rigid = Linear(((1, 0.5), (2, -0.5)), None, 0.0, Source(ED.GEN, ED.RIGID, ()))
    pin = Pin(1, 100.0, Source("structures", "x", ()))
    assert ED.release_governed([rigid, pin]) == [rigid, pin]
    road = Linear(((10, 1.0), (20, -1.0)), None, 0.1, Source("road_grade", "r", ()))
    inner = Linear(((10, 1.0), (11, -1.0)), None, 0.1, Source("road_grade", "r", ()))
    own = Linear(((10, 1.0), (1, -1.0)), None, -6.0, Source("structures", "t", ()))
    got = WP.release_across([road, inner, own], None, None, None, under=frozenset({10}),
                            inside=frozenset({10, 11}), keep=frozenset({"structures"}))
    assert got == [inner, own]


def test_the_object_stage_seats_the_one_zero_at_the_end_lines():
    """§3 (3): the deck member carries a DECK plate — its top and every end
    line's stations — and class A reads the zero off it alone."""
    tn = types.SimpleNamespace(deck_bridge="dsf:obj7", deck_top_y=6.0, edge_seats=(
        ("dsf:obj7", ((0.0, 1.0), (0.0, 2.0)), 6.2), ("dsf:obj7", ((5.0, 1.0),), 6.2)))
    plates = RI._edge_seat_plates(types.SimpleNamespace(structures=(tn,)), set())
    y, st, clear, kind = plates["dsf:obj7"]
    assert (y, clear, kind) == (6.0, 0.0, RI.DECK_PLATE) and len(st) == 3
    m = types.SimpleNamespace(plate_kind="deck", plate_y=6.0,
                              plate_stations=((36.0, -86.0), (36.1, -86.0)))
    zero, where, _seat = ADS.airside_zero(m, (), lambda la, lo: 110.0 if la < 36.05 else 111.0)
    assert abs(zero - 104.5) < 1e-9 and "hard-deck bridge" in where


def test_a_runway_vertex_on_the_trench_outline_is_never_the_floor():
    """the LFPG batch-AR regression (09L/27R over obj13017): a runway-family
    cell inside a hard-deck outline is NOT cut (the knife's 08-07 ruling 4
    exemption), so a runway vertex the trench ramp shares is the runway's,
    never the floor's — its runway rows to the crown are not released."""
    ring = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    roles = {1: ("tunnel_ramp",), 2: ("tunnel_ramp", "runway"), 3: ("runway",),
             4: ("tunnel_ramp", "runway_crossing"), 5: ("tunnel_ramp", "service_road")}
    pm = types.SimpleNamespace(
        structures=(types.SimpleNamespace(deck_bridge="dsf:obj1", deck_ring=ring),),
        vertices={v: types.SimpleNamespace(xy=(5.0, 5.0)) for v in roles},
        roles_at=lambda v: roles[v])
    floor, trench = ED.deck_floor(pm)
    assert floor == {1, 5}
    assert trench == {1, 2, 4, 5}
