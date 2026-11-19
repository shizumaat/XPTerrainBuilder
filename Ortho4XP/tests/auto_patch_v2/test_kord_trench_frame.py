"""K1 (kord-trench-frame-spec) and owner RULINGS 2026-11-19k (2): what a
building pad is NOT.

K1 -- a building rises above its own grade: a cluster whose tallest
ABOVE-GRADE component extent is under the walled height mints no pad, even
where a footprint-cache ring vouches the ground (KORD's I-190 road bed,
one slab y -5..0, vouched by 52 m2 of a neighbour's ring).

19k (2) -- a taxi route never crosses a building: a 1202 route passing
over the closed outline refuses the pad; one ending at its edge keeps it.
"""
from __future__ import annotations

import types

from auto_patch_v2.geom import cluster_outlines
from auto_patch_v2.geom.cluster_outline import CACHE_VOUCHED_SOURCE
from auto_patch_v2.geom.pad_evidence import PadEvidence
from auto_patch_v2.geom.route_over_pad import OVER, TOUCH, RouteWitness
from auto_patch_v2.geom.wall_lines import inner_faces, wall_lines
from auto_patch_v2.law.tables import load_default, pad_admission
from shapely.geometry import box

ADMISSION = pad_admission(load_default())


def _ident(lon: float, lat: float) -> tuple[float, float]:
    return (lon, lat)


def _cluster(cid: str, x0, y0, x1, y1, above: float, total: float = 2.72,
             tops: tuple = (), rows: tuple = ()):
    ring = [(y0, x0), (y0, x1), (y1, x1), (y1, x0)]
    area = (x1 - x0) * (y1 - y0)
    rows = rows or (("slab.obj", total, above, area),)
    ev = PadEvidence(tall_base_fill=0.86, tallest_extent_m=above,
                     evidence_coverage=0.0, hull_area_m2=area,
                     name_vouched=False, evidence_name_vouched=False,
                     length_m=x1 - x0, width_m=y1 - y0, components=len(rows),
                     rows=rows, tops=tuple(tops))
    return types.SimpleNamespace(id=cid, rings=[ring], walled=1, area_m2=area,
                                 floors=(-5.0,), members=("slab.obj",),
                                 evidence=ev, bridges=())


def _outlines(clusters, routes=None, vouch=CACHE_VOUCHED_SOURCE):
    refused: list[dict] = []
    got, counts = cluster_outlines(clusters, _ident, 0.0, walled_only=True,
                                   admission=ADMISSION,
                                   osm_evidence=lambda _u: vouch,
                                   refused=refused, routes=routes)
    return got, counts, refused


def test_k1_admission_carries_the_walled_height():
    law = load_default()
    assert ADMISSION.above_grade_min_m == float(
        law.tables.structures.placement.chain_min_height_m) == 2.5


def test_k1_a_slab_under_its_own_grade_mints_nothing_even_vouched():
    """The road bed: one component y -5.00..0.00 (above grade 0), the cache
    vouching its corner.  The vouch says a building is NEAR, never that the
    slab is one."""
    got, counts, refused = _outlines([_cluster("bed", 0, 0, 470, 96, 0.0)])
    assert got == [] and counts["below_grade"] == 1
    assert refused[0]["id"] == "bed" and refused[0]["gate"] == "above_grade_min_m"


def test_k1_a_building_standing_above_grade_still_mints_on_the_vouch():
    """A 4 m shed (under rule 10's 6 m, so the vouch carries it) is above
    the walled height: K1 leaves it alone."""
    got, counts, _r = _outlines([_cluster("shed", 0, 0, 40, 20, 4.0)])
    assert len(got) == 1 and counts["below_grade"] == 0
    assert counts["cache_vouched"] == 1


def test_k1_half_sunk_structure_under_the_walled_height_loses_its_pad():
    """0.82 m above grade is under 2.5 m; measured WITHOUT component tops
    (a cluster from before the field) it is read as before: refused."""
    got, counts, _r = _outlines([_cluster("park", 0, 0, 20, 17, 0.82)])
    assert got == [] and counts["below_grade"] == 1


def test_k1_an_at_grade_slab_keeps_its_pad():
    """Lane lk1fix: a landside slab whose top stands at its grade (+1.48,
    a skirt to -1.27) is no road bed: K1 leaves it to the vouch."""
    got, counts, _r = _outlines([_cluster("zone", 0, 0, 100, 60, 1.48,
                                          total=2.75, tops=(1.48,))])
    assert len(got) == 1 and counts["below_grade"] == 0
    assert counts["at_grade_slab"] == 1 and counts["cache_vouched"] == 1


def test_k1_a_road_bed_with_its_top_measured_is_still_refused():
    """The road bed's top stands 2.28 m under its grade: sunk, refused."""
    got, counts, _r = _outlines([_cluster("bed", 0, 0, 470, 96, 0.0,
                                          tops=(-2.28,))])
    assert got == [] and counts["below_grade"] == 1


def test_k1_a_walled_trench_whose_floor_carries_the_area_is_refused():
    """Walls to +2.4 over 1,000 m2, the floor (top -5.0) over 9,000 m2: the
    cluster lies under its grade although its walls reach it."""
    rows = (("trench.obj", 7.4, 2.4, 1000.0), ("trench.obj", 0.6, 0.0, 9000.0))
    got, counts, _r = _outlines([_cluster("trench", 0, 0, 100, 100, 2.4,
                                          tops=(2.4, -5.0), rows=rows)])
    assert got == [] and counts["below_grade"] == 1


def test_mostly_under_grade_reads_area_not_count():
    from auto_patch_v2.geom.pad_evidence import mostly_under_grade
    rows = (("a", 1.0, 0.0, 10.0), ("a", 1.0, 0.0, 10.0), ("a", 3.0, 1.0, 50.0))
    ev = types.SimpleNamespace(rows=rows, tops=(-3.0, -3.0, 1.0))
    assert mostly_under_grade(ev, 2.0) is False
    ev = types.SimpleNamespace(rows=rows, tops=(-3.0, -3.0, -2.5))
    assert mostly_under_grade(ev, 2.0) is True
    assert mostly_under_grade(types.SimpleNamespace(rows=rows, tops=()), 2.0) is None


def _airport(*edges):
    nodes = {}
    out = []
    for a, b in edges:
        for p in (a, b):
            nodes.setdefault(p, types.SimpleNamespace(xy=p))
        out.append(types.SimpleNamespace(a=a, b=b))
    ids = {p: k for k, p in enumerate(nodes)}
    return types.SimpleNamespace(
        taxi_nodes={ids[p]: n for p, n in nodes.items()},
        taxi_edges=[types.SimpleNamespace(a=ids[e.a], b=ids[e.b]) for e in out])


def test_route_over_a_pad_reads_over():
    rw = RouteWitness(_airport(((-10.0, 5.0), (50.0, 5.0))))
    kind, inside = rw.read(box(0, 0, 40, 10))
    assert kind == OVER and inside == 40.0


def test_route_through_a_node_inside_reads_over():
    rw = RouteWitness(_airport(((-10.0, 5.0), (20.0, 5.0)),
                               ((20.0, 5.0), (20.0, 30.0))))
    assert rw.read(box(0, 0, 40, 10))[0] == OVER


def test_route_ending_at_or_in_a_hangar_reads_touch():
    door = RouteWitness(_airport(((20.0, -30.0), (20.0, 0.0))))
    assert door.read(box(0, 0, 40, 10)) == (TOUCH, 0.0)
    inside = RouteWitness(_airport(((20.0, -30.0), (20.0, 4.0))))
    assert inside.read(box(0, 0, 40, 10)) == (TOUCH, 4.0)
    along = RouteWitness(_airport(((-10.0, 0.0), (50.0, 0.0))))
    assert along.read(box(0, 0, 40, 10))[0] == TOUCH
    clear = RouteWitness(_airport(((-10.0, -5.0), (50.0, -5.0))))
    assert clear.read(box(0, 0, 40, 10)) == ("", 0.0)


def test_a_route_over_a_cluster_refuses_its_pad_a_door_keeps_it():
    tall = _cluster("hangar", 0, 0, 40, 10, 12.0)
    over = RouteWitness(_airport(((-10.0, 5.0), (50.0, 5.0))))
    got, counts, refused = _outlines([tall], routes=over)
    assert got == [] and counts["taxi_route_over"] == 1
    assert refused[0]["gate"] == "taxi_route"
    door = RouteWitness(_airport(((20.0, -30.0), (20.0, 0.0))))
    got, counts, _r = _outlines([tall], routes=door)
    assert len(got) == 1 and counts["taxi_route_touch"] == 1


# ── K2: the trench's walls are the pair at the edge of the frame's floor ──

#: two outer walls (u -33.5, +46.5) and three 1 m piers (faces at
#: -27/-26, 3.5/4.5, 23/24) along s 0..36, the deck's middle near u 6.5
WALLS = [(u, 0.0, 36.0) for u in (-33.5, -27.0, -26.0, 3.5, 4.5, 23.0, 24.0, 46.5)]
#: the road bed between the outer walls (bays split at the piers, as a
#: mesh of triangles would be)
FLOOR = [(-33.5, -27.0, 0.0, 36.0), (-26.0, 3.5, 0.0, 36.0),
         (4.5, 23.0, 0.0, 36.0), (24.0, 46.5, 0.0, 36.0)]


def test_k2_without_a_floor_the_pair_is_the_nearest_the_middle():
    assert inner_faces(WALLS, 0.0, 36.0, 6.5, (-34.0, 47.0)) == (4.5, 23.0)


def test_k2_with_a_floor_the_pair_is_the_floors_edges():
    assert inner_faces(WALLS, 0.0, 36.0, 6.5, (-34.0, 47.0), FLOOR) == (-33.5, 46.5)


def test_k2_piers_are_dividers_never_span_ends():
    assert wall_lines(WALLS, 0.0, 36.0) == sorted(u for u, _a, _b in WALLS)
    assert wall_lines(WALLS, 0.0, 36.0, FLOOR) == [-33.5, 46.5]


def test_k2_a_floor_off_the_stretch_is_no_floor():
    """The floor is read over the stretch asked: one standing elsewhere
    along the road leaves the nearest-the-middle pair."""
    far = [(a, b, 100.0, 140.0) for a, b, _s0, _s1 in FLOOR]
    assert inner_faces(WALLS, 0.0, 36.0, 6.5, (-34.0, 47.0), far) == (4.5, 23.0)


def _walled_deck(ring_half: float = 20.0, wall_u: float = 15.0):
    """A deck across a road along x: ring u (y) in [-ring_half, ring_half],
    s (x) in [0, 10]; walls at u = +-wall_u running the whole stretch."""
    from auto_patch_v2.model.structures import DeckBridge
    ring = ((0.0, -ring_half), (10.0, -ring_half), (10.0, ring_half), (0.0, ring_half))
    sa = tuple((x, -ring_half) for x in (2.0, 5.0, 8.0))
    sb = tuple((x, ring_half) for x in (2.0, 5.0, 8.0))
    faces = ((-wall_u, -50.0, 60.0), (wall_u, -50.0, 60.0))
    return DeckBridge("o", "r.obj", ("o",), ring, sa, sb, 0.0, 0.0, -5.05, 199.0,
                      walls=((1.0, 0.0), (0.0, 1.0), faces, ()))


def test_w3_end_stations_stand_one_step_outside_the_ring_and_rim():
    from auto_patch_v2.planar.deck_bridge import rim_end_stations
    a, b = rim_end_stations(_walled_deck(), 5.0, 0.6)
    assert [p[0] for p in a] == [2.0, 5.0, 8.0]
    assert all(abs(p[1] + 25.0) < 1e-9 for p in a)       # ring 20 > rim 15.6
    assert all(abs(p[1] - 25.0) < 1e-9 for p in b)


def test_w3_the_rim_wins_where_it_stands_past_the_ring():
    from auto_patch_v2.planar.deck_bridge import rim_end_stations
    a, b = rim_end_stations(_walled_deck(ring_half=15.2, wall_u=15.4), 5.0, 0.6)
    assert all(abs(p[1] + 21.0) < 1e-9 for p in a)       # rim 16.0 > ring 15.2
    assert all(abs(p[1] - 21.0) < 1e-9 for p in b)


def test_w3_a_wall_less_deck_keeps_its_ring_stations():
    import dataclasses

    from auto_patch_v2.planar.deck_bridge import rim_end_stations
    assert rim_end_stations(dataclasses.replace(_walled_deck(), walls=()), 5.0, 0.6) is None


def test_open_stretch_reads_the_floor_where_one_side_draws_no_wall():
    from auto_patch_v2.geom.wall_lines import stretch_pair
    faces = ((0.0, 0.0, 50.0),)                     # one side's wall only
    floor = ((0.0, 80.0, 0.0, 50.0),)               # the frame's floor across
    assert stretch_pair(faces, 0.0, 50.0, (0.0, 79.0), (0.0, 80.0), floor) == (0.0, 79.0)
    assert stretch_pair(faces, 0.0, 50.0, (0.0, 79.0), (0.0, 80.0)) == (0.0, None)


def test_open_stretch_takes_a_skewed_wall_at_the_inner_line():
    from auto_patch_v2.geom.wall_lines import stretch_pair
    # a wall skewing 79 -> 82 across the stretch, in short faces
    faces = ((0.0, 0.0, 50.0),) + tuple((79.0 + 0.6 * k, 10.0 * k, 10.0 * k + 10.0)
                                        for k in range(5))
    assert stretch_pair(faces, 0.0, 50.0, (0.0, 79.0), (0.0, 82.0)) == (0.0, 79.0)


def _floor_map(points, roles):
    """A map of lone vertices at ``points`` (one face of ``roles[k]`` each)."""
    faces = {k: types.SimpleNamespace(role=r) for k, r in enumerate(roles)}
    verts = {k: types.SimpleNamespace(xy=p, incident_faces=(k,)) for k, p in enumerate(points)}
    return types.SimpleNamespace(vertices=verts, faces=faces)


def test_19m_ground_and_roads_between_the_walls_take_the_objects_floor():
    from auto_patch_v2.constraints.deck_lines import EndLine
    from auto_patch_v2.constraints.walled_floor import walled_floor_rows
    law = load_default()
    db = _walled_deck()
    # ground and a road inside the floor (|u| < 15), a corridor floor vertex,
    # ground beyond the walls, a seat
    pm = _floor_map([(5.0, 0.0), (5.0, 10.0), (5.0, -5.0), (5.0, 18.0), (5.0, -25.0)],
                    ["graded_strip", "service_road", "tunnel_ramp", "graded_strip", "taxiway"])
    lines = {"o": [EndLine(db, db.seats_a, ((4, 1.0),), 5.05),
                   EndLine(db, db.seats_b, ((4, 1.0),), 5.05)]}
    rows, held = walled_floor_rows(pm, law, lines, lambda v: v == 4, "edge_deck")
    assert held == {0, 1}                    # never the corridor's, the beyond, a seat
    lin = [r for r in rows if r.terms[0] == (0, 1.0)]
    assert lin and abs(lin[0].hi + 5.05) < 1e-9     # z[v] - seat <= -depth (and >=)


def test_w7b_the_trench_runs_on_past_the_end_to_the_frames_floor_end():
    import dataclasses

    from auto_patch_v2.planar.deck_bridge import _beyond_stretches
    db = _walled_deck()
    # the frame's floor under the deck (s 0..10) and on past its far end to
    # s 40, then a ramp (no floor solid) beyond; nothing past its near end
    floor = ((-15.0, 15.0, 0.0, 10.0), (-15.0, 15.0, 10.0, 25.0), (-15.0, 15.0, 25.2, 40.0))
    db = dataclasses.replace(db, walls=db.walls[:3] + (floor,))
    (got,) = _beyond_stretches([db], 0.6)
    assert got.beyond == (((-15.0, 15.0), (10.0, 40.0)),)
    # an end facing another piece of the object is the open stretch's
    other = dataclasses.replace(db, ring=tuple((x + 60.0, y) for x, y in db.ring))
    first, _second = _beyond_stretches([db, other], 0.6)
    assert first.beyond == ()


def test_w7b_no_road_ramp_row_inside_the_walls():
    from auto_patch_v2.constraints.walled_floor import release_wall_ramps
    from auto_patch_v2.model.constraints import Band, Source
    law = load_default()
    pm = _floor_map([(5.0, 15.3), (5.0, 30.0)], ["service_road", "service_road"])
    pm.decks = (_walled_deck(),)
    ramp, other = Source("road_ramp", "roads.groundside_road ramp ceiling"), Source("roads", "x")
    rows = [Band(0, None, 190.0, ramp), Band(1, None, 190.0, ramp), Band(0, None, 1.0, other)]
    counts: dict = {}
    got = release_wall_ramps(rows, pm, law, counts)
    assert got == rows[1:] and counts["walled_floor.ramps_released"] == 1


def test_k1_a_slab_mostly_over_a_sunk_cluster_mints_nothing():
    """Lane lk1fix: the road bed mints nothing; a slab mostly over its
    ground is a slab of its frame (no pad); one partly over it is left
    whole (a trim moves the airside around a pad)."""
    bed = _cluster("bed", 0, 0, 100, 40, 0.0, tops=(-2.28,))
    lid = _cluster("lid", 10, 20, 30, 60, 0.82, tops=(0.83,))       # 1/2 over: 400/800
    lid2 = _cluster("lid2", 60, 30, 80, 70, 0.82, tops=(0.83,))     # 1/4 over
    lid3 = _cluster("lid3", 40, 10, 50, 50, 0.82, tops=(0.83,))     # 3/4 over
    got, counts, refused = _outlines([bed, lid, lid2, lid3])
    ids = {i: g for i, _c, g in got}
    assert counts["below_grade"] == 1 and counts["over_sunk"] == 1
    assert [r["id"] for r in refused if r["gate"] == "sunk_ground"] == ["lid3"]
    assert abs(ids["lid2"].area - 800.0) < 1.0 and abs(ids["lid"].area - 800.0) < 1.0
