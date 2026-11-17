"""#1949 (owner 2026-11-10T14:33Z, OMDB): a pack that hangs a whole sunken
area off one shared datum authors the floor AT the zero and the ground at the
top of its retaining walls.  The walls' rim is the pit's ground: the floor is
cut ``rim - floor`` under it, and a frame whose rim stands off the ground
around it is moved so the rim lands there (``airport/walled_pit``).  A pit is
sunken: a walled floor over the ground around it is a roof or deck (#2005)."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import object_floor as OF
from shapely.geometry import LineString
from test_hanging_objects1298 import LAW, THICK, _box, _write


def _flat(z):
    return lambda xs, ys: np.full(len(np.atleast_1d(xs)), float(z))


def _at(path, oid, zero=100.0):
    return types.SimpleNamespace(id=oid, path=f"objects/{oid}.obj", resolved=path, xy=(0.0, 0.0),
                                 heading_deg=0.0, kind="OBJECT", anchor_z=zero, agl_m=0.0,
                                 plan_bbox=None)


def _pit(tmp_path, wall_h=12.0, roof=False):
    """A 60 x 40 m floor plate at y 0 .. 0.2 and, co-placed, four walls
    standing on its edges from y 0 to ``wall_h`` (and a roof over it)."""
    floor = _write(tmp_path / "floor.obj", [_box(0.0, 0.0, 60.0, 40.0, 0.2)])
    walls = [_box(-0.5, 0.0, 0.5, 40.0, wall_h), _box(60.0, 0.0, 0.5, 40.0, wall_h),
             _box(0.0, -0.5, 60.0, 0.5, wall_h), _box(0.0, 40.0, 60.0, 0.5, wall_h)]
    if roof:
        walls.append(_box(-0.5, -0.5, 61.0, 41.0, 0.3, y0=wall_h))
    return [_at(_write(tmp_path / "walls.obj", walls), "dsf:obj1"),
            _at(floor, "dsf:obj2")]


def _read(objs, ground):
    return OF.read_object_floors(objs, O.ResourceCache(THICK), LAW, {}, ground=_flat(ground))


def test_a_frame_standing_proud_of_the_ground_lands_its_rim_on_it(tmp_path):
    """OMDB: the walls' rim 12 m over the zero, the ground 5 m over it (the
    floor sunken under the ground, the rim 7 m proud) — the frame moves 7 m
    down and the floor is cut 12 m under the ground."""
    floors, notes = _read(_pit(tmp_path), 105.0)
    assert [f.object_id for f in floors] == ["dsf:obj2"], notes
    f = floors[0]
    assert abs(f.lift + 7.0) < 0.05 and f.covers == ("dsf:obj1",)
    assert abs(f.floor_z - 93.0) < 0.05 and abs(f.rim_z - 105.0) < 0.05
    assert {pid: round(z, 2) for pid, _r, z in f.seats} == {"dsf:obj2": 93.0, "dsf:obj1": 93.0}
    recs = OF.seat_records(floors)
    assert {r["id"]: r["elevation"] for r in recs} == {"dsf:obj2": 93.0, "dsf:obj1": 93.0}
    assert abs(f.footprint.area - 2400.0) < 5.0


def test_a_walled_floor_over_the_ground_is_a_roof_not_a_pit(tmp_path):
    """#2005 (KMCI): a plate walled to a rim inside a building's frame — a
    roof behind its parapet, a deck under the storey above — stands OVER
    the ground around it.  A pit is sunken: no floor, no lift, the frame
    keeps its seat."""
    floors, notes = _read(_pit(tmp_path), 90.0)
    assert floors == [] and any("a roof or deck in its frame, not a pit" in n
                                for n in notes), notes


def test_a_rim_at_the_ground_keeps_the_authored_seat(tmp_path):
    """The rim 1 m over the ground (within ``authored_crest_max_m``): no
    lift, the floor cut at its authored level 11 m under the ground."""
    floors, notes = _read(_pit(tmp_path), 111.0)
    assert len(floors) == 1 and floors[0].lift == 0.0, notes
    assert abs(floors[0].floor_z - 100.0) < 0.05


def test_low_walls_round_a_plate_are_no_pit(tmp_path):
    """A kerb or a fence 1.5 m high round a plate is no retaining wall."""
    floors, notes = _read(_pit(tmp_path, wall_h=1.5), 90.0)
    assert floors == [], notes


def test_a_floor_under_its_own_roof_is_a_building(tmp_path):
    """Walls round a floor with a roof over it: a building's (the basin
    basement test), never a pit."""
    floors, notes = _read(_pit(tmp_path, roof=True), 90.0)
    assert floors == [] and any("a building, not a pit" in n for n in notes), notes


def test_the_frames_placements_in_the_pit_move_with_it_and_the_rest_keep_their_seats(tmp_path):
    """The pit's lamps (a lights-only object over it) move with the frame;
    a co-placed building far from it keeps its own seat."""
    lamps = tmp_path / "lamps.obj"
    lamps.write_text("I\n800\nOBJ\n\nPOINT_COUNTS 0 0 0 0\n\n"
                     "LIGHT_PARAM full_custom_halo_night 10.0 9.0 10.0 1 1 1 1 100 0 -1 0 1\n"
                     "LIGHT_PARAM full_custom_halo_night 50.0 9.0 30.0 1 1 1 1 100 0 -1 0 1\n",
                     encoding="utf-8", newline="\n")
    far = _write(tmp_path / "far.obj", [_box(500.0, 500.0, 30.0, 30.0, 8.0)])
    objs = _pit(tmp_path) + [_at(str(lamps), "dsf:obj3"), _at(far, "dsf:obj4")]
    floors, notes = _read(objs, 105.0)
    assert len(floors) == 1, notes
    assert {pid for pid, _r, _z in floors[0].seats} == {"dsf:obj1", "dsf:obj2", "dsf:obj3"}


def test_a_pit_floor_is_no_author_ground_for_the_floors_read_after_it():
    """#1949 (5): the pit's floor plate stands under its rim — dropped from
    the author's ground (``AuthorGround.without``), it is never the ground
    another floor (OMDB ``duong_ray_FACE``) is read against."""
    from auto_patch_v2.geom.author_ground import AuthorGround
    tri = np.array([[[0.0, 0.0, 1.0], [10.0, 0.0, 1.0], [0.0, 10.0, 1.0]]])
    ag = AuthorGround(np.concatenate([tri, tri + [0.0, 0.0, 5.0]]), ["pit", "plate"])
    assert abs(ag.at([1.0], [1.0])[0] - 1.0) < 1e-9
    rest = ag.without({"pit"})
    assert abs(rest.at([1.0], [1.0])[0] - 6.0) < 1e-9 and list(rest.owners) == ["plate"]
    assert ag.without(set()) is ag


def test_a_road_ramp_between_its_parapets_is_no_pit(tmp_path):
    """#2091 (OTHH TerminalRoads_03_002): a road that dips under its datum at
    one end and climbs to a viaduct between parapet walls has a floor under
    the ground and walls round it, but most of it stands OVER the ground —
    no pit, no frame lift, no cut under the bridge beside it."""
    steps = [_box(10.0 * k, 0.0, 10.0, 40.0, 0.2, y0=2.0 * k) for k in range(6)]
    floor = _write(tmp_path / "ramp.obj", steps)
    walls = [_box(-0.5, 0.0, 0.5, 40.0, 12.0), _box(60.0, 0.0, 0.5, 40.0, 12.0),
             _box(0.0, -0.5, 60.0, 0.5, 12.0), _box(0.0, 40.0, 60.0, 0.5, 12.0)]
    objs = [_at(_write(tmp_path / "parapets.obj", walls), "dsf:obj1"),
            _at(floor, "dsf:obj2")]
    floors, notes = _read(objs, 102.0)
    assert floors == [], notes
    assert any("a ramp climbing out of the ground" in n for n in notes), notes


def test_a_pit_whose_own_floor_is_hard_deck_still_reads(tmp_path):
    """OTHH TerminalRoads_02_000: the floor object flags its own floor
    ``ATTR_hard_deck``.  The hard-deck guard (KBNA taxiway L) reads only a
    deck standing ``bridge.clearance_minimum_m`` over the floor -- a deck AT
    the floor is the floor, no road under a bridge -- so the pit still
    reads (#1689 R2 F8)."""
    objs = _pit(tmp_path)
    objs[1].resolved = _write(tmp_path / "floor_deck.obj",
                              [_box(0.0, 0.0, 60.0, 40.0, 0.2)], hard=(0,))
    objs[1].deck_kind = "flag"
    floors, notes = _read(objs, 105.0)
    assert [f.object_id for f in floors] == ["dsf:obj2"], notes


def _trench(tmp_path, roof=False, low_wall=None, low_portal=False):
    """A trench authored as ONE open hollow (OMDB ``duong_2``): a 60 x 40 m
    floor at y 0 .. 0.2 with its own side walls to y 12, and, co-placed,
    the walls of its portals standing on the same edges (``tuner1``);
    ``roof`` closes the hollow (a building, never a trench); ``low_wall``
    the height of the hollow's own north wall (one wall lower than the
    rim, its 0.5 m cap under it), and with ``low_portal`` of the portal
    walls' too (the whole north side lower than the rim)."""
    sides = [_box(-0.5, 0.0, 0.5, 40.0, 12.0), _box(60.0, 0.0, 0.5, 40.0, 12.0),
             _box(0.0, -0.5, 60.0, 0.5, 12.0), _box(0.0, 40.0, 60.0, 0.5, 12.0)]
    own = sides if low_wall is None else [*sides[:3], _box(0.0, 40.0, 60.0, 0.5, low_wall)]
    shell = [_box(0.0, 0.0, 60.0, 40.0, 0.2), *own]
    if low_portal:
        sides = own
    if roof:
        shell.append(_box(-0.5, -0.5, 61.0, 41.0, 0.3, y0=12.0))
    return [_at(_write(tmp_path / "portal_walls.obj", sides), "dsf:obj1"),
            _at(_write(tmp_path / "trench.obj", shell), "dsf:obj2")]


def _read_bored(objs, ground, bores):
    return OF.read_object_floors(objs, O.ResourceCache(THICK), LAW, {}, ground=_flat(ground),
                                 bores=bores)


#: a mapped bore running into the trench from its west end
_BORE = LineString([(-80.0, -20.0), (30.0, -20.0)])


def test_a_trench_in_one_open_hollow_object_is_a_walled_pit(tmp_path):
    """#1949 (owner sim read 2026-11-17, OMDB 25.242834, 55.360158: "the
    tunnel object ... doesn't appear to be getting a cut and seat"): its
    floor object carries its own walls, so it is no plate, but it is an
    open hollow with its portal walls co-placed on its edges.  It reads as
    the plate pit does: the rim lands on the ground, the floor is the cut,
    the portal walls move with it."""
    floors, notes = _read_bored(_trench(tmp_path), 105.0, [_BORE])
    assert [f.object_id for f in floors] == ["dsf:obj2"], notes
    f = floors[0]
    assert abs(f.lift + 7.0) < 0.05 and abs(f.floor_z - 93.0) < 0.05, notes
    assert {pid: round(z, 2) for pid, _r, z in f.seats} == {"dsf:obj2": 93.0, "dsf:obj1": 93.0}


def test_a_closed_hollow_with_walls_beside_it_is_no_trench(tmp_path):
    """The same object under its own roof is covered, no open hollow: a
    building, never a pit."""
    floors, notes = _read_bored(_trench(tmp_path, roof=True), 105.0, [_BORE])
    assert floors == [], notes


def test_an_open_hollow_no_mapped_bore_runs_into_is_no_trench(tmp_path):
    """The census (lane lomdb): an open hollow with walls co-placed on its
    edges is also a landscape block's terraces (EFHK ``infra_6_01``, 56,000
    m2) or a loading bay (EGGW ``eggw_bays``).  A trench is a tunnel's: a
    mapped bore runs into its floor, else nothing is read."""
    away = LineString([(-80.0, -200.0), (30.0, -200.0)])
    for bores in ([], [away]):
        floors, notes = _read_bored(_trench(tmp_path), 105.0, bores)
        assert floors == [], (bores, notes)


def test_the_top_of_a_hollows_own_wall_is_no_floor(tmp_path):
    """#1949 R1 (OMDB ``duong_2``: 27 of its 36 floor planes were the 0.4 -
    0.8 m caps of its own walls, read as floor, and the 0.5 m lattice pinned
    the rim alternately on the cap and the floor, a 3.16 m road step): a
    plane under the rim nowhere wider than a wall, standing over the floor
    beside it, is the wall's top -- it leaves the floor's faces and
    footprint."""
    floors, notes = _read_bored(_trench(tmp_path, low_wall=6.0), 105.0, [_BORE])
    assert [f.object_id for f in floors] == ["dsf:obj2"], notes
    f = floors[0]
    assert float(f.faces[:, :, 2].max()) < f.floor_z + 1.0, notes
    assert f.footprint.bounds[3] <= 40.0 + 1e-6, f.footprint.bounds
    assert any("tops of its own walls" in n for n in notes), notes


def test_a_wall_lower_than_the_ground_behind_it_states_its_rim_a_parapet_under_its_top(tmp_path):
    """#1949 R2 (RULINGS 2026-11-16l; OMDB: the gore's walls top out up to
    4.3 m under the DEM and the mesh drew a cliff over them): the frame
    lands its rim (12 m) on the ground (105), so its 6 m north side stands
    6 m under it -- an OPEN EDGE.  The pit states its rim there 1 m
    (``retaining_parapet_m``) under the wall's top, and nowhere else."""
    floors, notes = _read_bored(_trench(tmp_path, low_wall=6.0, low_portal=True), 105.0, [_BORE])
    assert [f.object_id for f in floors] == ["dsf:obj2"], notes
    f = floors[0]
    assert f.rim_banks and f.rim_tops, notes
    T = np.asarray(f.rim_tops, float)
    z = f.zero_z + T[:, 2]
    # the wall's top as seated: 100 + 6 - 7 = 99; the rim 1 m under it,
    # eased from the ground at the run's ends at 1:3
    mid = np.abs(T[:, 0] - 30.0) < 5.0
    assert np.allclose(z[mid], 98.0, atol=0.05), z
    assert float(z.max()) <= 105.0 + 1e-6 and float(z.min()) >= 98.0 - 1e-6, z
    d = np.minimum(T[:, 0] - T[:, 0].min(), T[:, 0].max() - T[:, 0])
    assert np.all(z <= np.maximum(98.0, 105.0 - 0.33 * d) + 0.7), z
    # only the low side: every stated sample on one line, the north rim
    assert float(np.ptp(T[:, 1])) < 2.5, T[:, 1]


def test_a_pit_with_a_roof_over_its_floor_is_no_open_trench_and_states_no_rim(tmp_path):
    """#1949 rule 7 (owner RULINGS 2026-11-17 (a); lane lomdb2's census
    brought the ground down 1-3 m to buildings' lower storeys, KBNA, CYYZ
    ``Terminal1_Parte29``): the same low-walled trench with a roof at its rim
    over half its floor (in the co-placed walls' object; under the basement
    share, so it still reads as a pit) is no OPEN TRENCH: it states no open
    edge and takes no bank; its floor and seat read as before."""
    objs = _trench(tmp_path, low_wall=6.0, low_portal=True)
    walls = [_box(-0.5, 0.0, 0.5, 40.0, 12.0), _box(60.0, 0.0, 0.5, 40.0, 12.0),
             _box(0.0, -0.5, 60.0, 0.5, 12.0), _box(0.0, 40.0, 60.0, 0.5, 6.0),
             _box(0.0, 0.0, 60.0, 20.0, 0.3, y0=12.0)]
    objs[0].resolved = _write(tmp_path / "roofed.obj", walls)
    floors, notes = _read_bored(objs, 105.0, [_BORE])
    assert [f.object_id for f in floors] == ["dsf:obj2"], notes
    f = floors[0]
    assert f.rim_tops == () and not f.rim_banks, notes
    assert abs(f.lift + 7.0) < 0.05 and abs(f.floor_z - 93.0) < 0.05, notes
    assert any("no open trench" in n for n in f.notes), f.notes


def test_a_plate_standing_on_walls_hanging_under_it_is_a_roof_and_states_no_rim(tmp_path):
    """#1949 rule 7 (LEMD ``Cargo-tej2``: a roof object's low roof read as the
    floor of its own facades, which hang 6 m under it; the rim brought down
    25.7 m): a plate whose walls hang more than ``cover_flush_m`` under it
    along its outline is a ROOF -- the floor the walls stand on lies under
    it -- so it states no open edge, however low a wall stands."""
    def frame(y0):
        walls = [_box(-0.5, 0.0, 0.5, 40.0, 12.0 - y0, y0=y0),
                 _box(60.0, 0.0, 0.5, 40.0, 12.0 - y0, y0=y0),
                 _box(0.0, -0.5, 60.0, 0.5, 12.0 - y0, y0=y0),
                 _box(0.0, 40.0, 60.0, 0.5, 6.0 - y0, y0=y0)]
        floor = _write(tmp_path / f"plate{y0}.obj", [_box(0.0, 0.0, 60.0, 40.0, 0.2, y0=3.0)])
        return [_at(_write(tmp_path / f"facades{y0}.obj", walls), "dsf:obj1"),
                _at(floor, "dsf:obj2")]
    open_, _ = _read(frame(3.0), 105.0)
    assert [f.object_id for f in open_] == ["dsf:obj2"] and open_[0].rim_tops
    floors, notes = _read(frame(-2.0), 105.0)
    assert [f.object_id for f in floors] == ["dsf:obj2"], notes
    assert floors[0].rim_tops == () and not floors[0].rim_banks, notes
    assert any("no open trench" in n for n in floors[0].notes), floors[0].notes


def test_a_flush_rim_states_no_open_edge(tmp_path):
    """A walled pit whose walls all land on the ground states no rim and
    takes no bank (the accepted rim stays)."""
    floors, notes = _read_bored(_trench(tmp_path), 105.0, [_BORE])
    assert [f.object_id for f in floors] == ["dsf:obj2"], notes
    assert floors[0].rim_tops == () and not floors[0].rim_banks, notes


def test_an_open_edge_takes_a_bank_from_its_crest_to_the_dem(tmp_path):
    """#1949 R3: the open edge's run mints ``graded_strip`` bank pieces
    outside the pit's void band, ``max(bank_min_width_m, rise /
    bank_slope)`` wide (rise 7 m: 21 m), welded to the band's ring (its
    crest); a road ribbon that cuts it short is listed with its grade."""
    from auto_patch_v2.model.planar import is_pit_bank_ref
    from auto_patch_v2.planar.pit_bank import pit_bank_pieces
    from shapely.geometry import box
    floors, notes = _read_bored(_trench(tmp_path, low_wall=6.0, low_portal=True), 105.0, [_BORE])
    f = floors[0]
    ap = types.SimpleNamespace(dem=types.SimpleNamespace(z_many=lambda xs, ys: np.full(len(xs),
                                                                                       105.0)))
    T = np.asarray(f.rim_tops, float)
    side = float(np.median(T[:, 1]))
    out = pit_bank_pieces(floors, ap, [], [], 2.0, 0.1, 5.0, LAW)
    assert out and all(is_pit_bank_ref(r) for r, _g in out), out
    from shapely.ops import unary_union
    bank = unary_union([g for _r, g in out])
    band = f.footprint.buffer(1.0, join_style="mitre")
    assert bank.intersection(band).area < 1.0
    assert bank.distance(band) < 1e-6
    away = side + np.sign(side - f.footprint.centroid.y) * 21.0
    assert abs(max(abs(y - side) for y in (bank.bounds[1], bank.bounds[3])) - 21.0) < 1.0, \
        (bank.bounds, away)
    road = box(-100.0, min(side, away) + 9.0, 100.0, min(side, away) + 12.0) \
        if away > side else box(-100.0, side - 12.0, 100.0, side - 9.0)
    clipped: list[str] = []
    out = pit_bank_pieces(floors, ap, [], [road], 2.0, 0.1, 5.0, LAW, ribbons=[road],
                          notes=clipped)
    assert any(n.startswith("pit_bank_clipped:") for n in clipped), clipped
    assert unary_union([g for _r, g in out]).intersection(road).area < 1e-6


def test_a_sloped_wall_hangs_from_where_the_sample_stands():
    """Rule 7's hang reads a wall face where the outline sample stands: a
    ramp's side wall, one long sloped face (OTHH ``TerminalRoads_02_004``,
    bottoms -6.55 .. 10 m along a climbing road), hangs under no part of the
    road it follows -- its lowest corner 50 m away is no witness."""
    from auto_patch_v2.airport.walled_pit import _slice
    prof = np.array([[[0.0, 0.0], [100.0, 10.0], [100.0, 12.0]]] * 3)
    lo, hi = _slice(prof, np.array([50.0, 0.0, 100.0]))
    assert np.allclose(lo, [5.0, 0.0, 10.0]) and np.allclose(hi, [6.0, 0.0, 12.0]), (lo, hi)
