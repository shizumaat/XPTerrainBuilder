"""#1138 round 6 (owner sim read 2026-10-28T14:26Z points 2-5): an EDGE
BRIDGE's top is flush with the airside at its SEAT, the trench is never
deeper than an object's bottom, and the open stretch between two bridges is
one cut as wide as the objects, its floor sloping from each object's bottom
to the other's (RULINGS 2026-10-28u Q271 (b)) (``planar/bridge_span``,
``constraints/structures``, ``constraints/edge_floor``,
``pipeline/rebake_inputs``, ``airport/anchor_rule.datum_of``)."""
from __future__ import annotations

import dataclasses as _dc
import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.planar import bridge_span as BS
from auto_patch_v2.pipeline import rebake_inputs as RI
from shapely.geometry import Point, Polygon
from shapely.geometry import box as _sbox
from test_edge_bridge1138 import PAV, _bridge


def test_the_seat_is_the_airside_pavement_point_nearest_the_origin(tmp_path):
    """The seat (where the object's top meets the solved surface) is on the
    airside pavement the object edges, nearest its placement origin; the
    pre-solve floor is the deck level less the depth."""
    br = _bridge(tmp_path)
    assert PAV.boundary.distance(Point(br.seat)) < 1e-6
    assert abs(br.seat[0]) < 1e-6 and abs(br.seat[1] + 40.0) < 1e-6
    assert abs(br.floor_z - (br.deck_z - br.depth_m)) < 1e-9


def _facing(br, dy: float, deck_z: float):
    """``br`` mirrored across the cut, ``dy`` further along it: a second
    bridge whose cut side faces ``br``'s."""
    def mv(pts):
        return tuple((x, -y + dy) for x, y in pts)
    return _dc.replace(br, object_id="dsf:obj8", back=mv(br.back), plan=mv(br.plan),
                       toward=(0.0, 1.0), cover=Polygon(mv(br.cover.exterior.coords)),
                       deck_z=deck_z, seat=(0.0, dy + 40.0))


def test_the_stretch_between_two_bridges_is_one_cut_as_wide_as_the_objects(tmp_path):
    """Point 3: the cut between two facing bridges is the hull of both
    plans — every carriageway and the median at full width — off both
    span sides; a corridor meeting no other bridge takes its own plan."""
    br = _bridge(tmp_path)
    other = _facing(br, 100.0, br.deck_z)           # its cut side faces br's
    ramp = _sbox(-5.0, -10.0, 5.0, 130.0)           # a lane-wide corridor
    outer = ramp.buffer(1.6, join_style="mitre")
    r2, o2 = BS.edge_cut(br, ramp, outer, 1.6, 500.0, (other,))
    mid = _sbox(-29.0, 40.0, 29.0, 60.0)             # between the two objects
    assert r2.contains(mid)
    assert r2.intersection(br.cover).area < 1e-6 and r2.intersection(other.cover).area < 1e-6
    r1, _o1 = BS.edge_cut(br, ramp, outer, 1.6, 500.0)
    assert not r1.contains(mid)


def test_an_edge_bridge_is_plate_seated_at_its_seat_ahead_of_the_rim():
    """Point 2: every bridge an edge trench meets is entered as an EDGE
    plate — zero 0.0 at its seat — and the anchor reads that datum first;
    a seat the authored-seat census kept is not entered."""
    tn = types.SimpleNamespace(edge_seats=(("dsf:obj7", (0.0, -40.0), 26.0),
                                           ("dsf:obj8", (0.0, 60.0), 24.0)))
    pm = types.SimpleNamespace(structures=(tn,))
    got = RI._edge_seat_plates(pm, kept={"dsf:obj8"})
    assert got == {"dsf:obj7": (0.0, [(0.0, -40.0)], 0.0, RI.EDGE_PLATE)}
    m = types.SimpleNamespace(plate_y=0.0, plate_kind=RI.EDGE_PLATE,
                              plate_stations=((33.6, -84.4),))
    d = AR.datum_of(m)
    assert d is not None and d.y == 0.0 and d.stations == ((33.6, -84.4),)
    assert AR.datum_of(types.SimpleNamespace(
        plate_y=0.0, plate_kind="", plate_stations=((33.6, -84.4),))) is None


def test_the_span_is_held_level_with_the_airside_abeam(monkeypatch):
    """Points 4 / 5 (Q212): every vertex inside an edge bridge's cover, off
    its back and on no trench face, takes the airside abeam's level as a
    hard pair; a vertex on the trench's own faces does not."""
    import auto_patch_v2.constraints.roads as R
    from auto_patch_v2.constraints import edge_deck as ED
    from auto_patch_v2.solve.design_roles import hard_rulings, is_hard
    from test_hanging_objects1298 import LAW
    v = {0: (0.0, 0.0), 1: (50.0, 0.0), 2: (5.0, 10.0), 3: (45.0, 12.0), 4: (20.0, 15.0)}
    roles = {0: ("runway",), 1: ("runway",), 2: ("parking_lot",), 3: ("graded_strip",),
             4: ("tunnel_ramp",)}
    tn = types.SimpleNamespace(id="tunnel:-1@0", portal="dsf:obj7", decks=(),
                               edge_back=((0.0, 20.0), (50.0, 20.0)),
                               edge_covers=(((0.0, 0.0), (50.0, 0.0), (50.0, 20.0),
                                             (0.0, 20.0), (0.0, 0.0)),))
    pm = types.SimpleNamespace(
        structures=(tn,), faces={},
        vertices={k: types.SimpleNamespace(xy=p) for k, p in v.items()},
        ring_vertices=lambda ring: ring, roles_at=lambda k: roles[k])
    monkeypatch.setattr(R, "stage_one_vertices", lambda _pm, _law: frozenset({0, 1}))
    rows = ED.edge_deck_rows(pm, LAW, None)
    pairs = sorted({tuple(sorted((r.terms[0][0], r.terms[1][0]))) for r in rows})
    assert pairs == [(0, 2), (1, 3)] and len(rows) == 4
    assert all(is_hard(hard_rulings(LAW), r) for r in rows)


def _holds(rows, z, tol=1e-9):
    """Every ``Linear`` row ``lo <= Σ c·z <= hi`` holds at ``z``."""
    for r in rows:
        x = sum(c * z[v] for v, c in r.terms)
        if (r.lo is not None and x < r.lo - tol) or (r.hi is not None and x > r.hi + tol):
            return False
    return True


def test_a_trench_between_two_bridges_slopes_from_each_bottom_to_the_other():
    """RULINGS 2026-10-28u Q271 (b): the floor of a trench two edge bridges
    share runs linearly from the first object's bottom (its seat's surface
    less its depth) at the end of that object to the second's at its back,
    and under each object stands at that object's own bottom — never level
    at the shallower bottom, where the deeper object's walls stood into it."""
    from auto_patch_v2.constraints.edge_floor import seat_pair, sloped_floor_rows
    from auto_patch_v2.model.constraints import Source
    src = Source("test", "tunnel.mouth_depth_m", ())
    seats = ((10, 26.0), (11, 24.0))                # (seat vertex, depth)
    z = {10: 300.0, 11: 301.6}                       # bottoms 274.0 and 277.6
    groups = [(0.0, [1, 2]), (40.0, [3]), (90.0, [4]), (140.0, [5]), (170.0, [6])]
    rows = sloped_floor_rows(groups, seats, (40.0, 140.0), src)
    sloped = {**z, 1: 274.0, 3: 274.0, 4: 275.8, 5: 277.6, 6: 277.6}
    assert _holds(rows, sloped)
    level = {**z, **{k: 277.6 for k in (1, 3, 4, 5, 6)}}
    assert not _holds(rows, level)
    assert all(r.source is src for r in rows) and len(rows) == 2 * len(groups)
    assert _holds(seat_pair(7, (10, 26.0), src), {7: 274.0, 10: 300.0})
    assert not _holds(seat_pair(7, (10, 26.0), src), {7: 275.0, 10: 300.0})


def test_the_span_runs_to_the_top_edge_and_sheds_the_rows_that_held_it_off(monkeypatch):
    """#1632 (owner sim read of 1.0.444: "the ground should be flat airside
    all the way to the top edge of those tunnel bridge objects"): a ground
    vertex inside the cover AT the back, and the trench's rim ON the back,
    take the airside abeam's pair; the trench floor and a rim vertex past the
    back's end do not.  A governed vertex sheds its rim DEM pin and its road
    ramp target and ceiling; a pair row and an ungoverned vertex's ramp
    stay."""
    import auto_patch_v2.constraints.roads as R
    from auto_patch_v2.constraints import edge_deck as ED
    from auto_patch_v2.model.constraints import Band, Diff, Linear, Pin, Source
    from test_hanging_objects1298 import LAW
    v = {0: (0.0, 0.0), 1: (50.0, 0.0), 2: (30.0, 19.5), 3: (25.0, 20.2),
         4: (25.0, 21.5), 5: (55.0, 20.2), 6: (10.0, 19.0)}
    roles = {0: ("runway",), 1: ("runway",), 2: ("graded_strip",),
             3: ("retaining_wall",), 4: ("retaining_wall", "tunnel_ramp"),
             5: ("retaining_wall",), 6: ("service_road",)}
    tn = types.SimpleNamespace(id="tunnel:-1@0", portal="dsf:obj7", decks=(),
                               edge_back=((0.0, 20.0), (50.0, 20.0)),
                               edge_covers=(((0.0, 0.0), (50.0, 0.0), (50.0, 20.0),
                                             (0.0, 20.0), (0.0, 0.0)),))
    pm = types.SimpleNamespace(
        structures=(tn,), faces={},
        vertices={k: types.SimpleNamespace(xy=p) for k, p in v.items()},
        ring_vertices=lambda ring: ring, roles_at=lambda k: roles[k])
    monkeypatch.setattr(R, "stage_one_vertices", lambda _pm, _law: frozenset({0, 1}))
    rows = ED.edge_deck_rows(pm, LAW, None)
    assert {r.terms[0][0] for r in rows if r.terms[0][1] > 0} == {2, 3, 6}
    rim = Source("structures", "tunnel.crest = dem", ())
    ramp = Source("road_ramp", ED.RULING, ())
    other = [Pin(3, 290.0, rim), Pin(5, 290.0, rim), Band(6, None, 291.5, ramp),
             Linear(((6, 1.0),), 291.0, 291.0, ramp), Linear(((5, 1.0),), 280.0, 280.0, ramp),
             Diff(6, 2, 0.1, 5.0, ramp)]
    counts: dict = {}
    kept = ED.release_governed(rows + other, counts)
    assert counts["edge_deck.released"] == 3
    assert [r for r in kept if r in other] == [other[1], other[4], other[5]]
