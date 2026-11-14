"""#2065 R1 twins (spec ``bridge-classifier-spec.md`` §1, §5 R1): the free
bridge's positive witness (``airport/bridge_witness`` W1-W6), the one class
table (``airport/bridge_class``) and the moved chain join
(``airport/deck_carry.route_chains``, ``planar/overpass_deck._own_route``).
Synthetic frames in metres; faces are ``(n, 3, 3)`` x, y, authored y."""
from __future__ import annotations

import math
import types

import numpy as np
from auto_patch_v2.airport import bridge_witness as BW
from auto_patch_v2.airport.bridge_class import CLASSES, DeckFacts, classify
from auto_patch_v2.airport.deck_carry import route_chains
from auto_patch_v2.geom.centreline import ribbon_centreline
from auto_patch_v2.geom.lowest_face import every_z_at, floor_z_at
from auto_patch_v2.law import Law
from auto_patch_v2.planar.overpass_deck import _own_route
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry import box as _box

LAW = Law.for_airport("")


def _way(i, pts, **tags):
    return types.SimpleNamespace(id=i, points=tuple(pts), tags=dict(tags))


def _slab(poly: Polygon, z: float) -> np.ndarray:
    """``poly`` (convex or a box) as a fan of faces at height ``z``."""
    c = list(poly.exterior.coords)[:-1]
    return np.array([[(*c[0], z), (*c[k], z), (*c[k + 1], z)] for k in range(1, len(c) - 1)])


def _strip(line: LineString, half: float, z) -> np.ndarray:
    """A ribbon of faces ``half`` either side of ``line`` at ``z(s)``."""
    out = []
    n = max(2, int(line.length // 2.0))
    pts = [line.interpolate(line.length * k / n) for k in range(n + 1)]
    for a, b in zip(pts, pts[1:], strict=False):
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy)
        nx, ny = -dy / d * half, dx / d * half
        za, zb = z(line.project(a)), z(line.project(b))
        p = [(a.x + nx, a.y + ny, za), (a.x - nx, a.y - ny, za),
             (b.x - nx, b.y - ny, zb), (b.x + nx, b.y + ny, zb)]
        out += [[p[0], p[1], p[2]], [p[0], p[2], p[3]]]
    return np.array(out)


def _ground(xs, ys):
    """A valley 4 m deep under x = 0 (a straight bridge spans it)."""
    return 4.0 * np.minimum(np.abs(np.asarray(xs)) / 25.0, 1.0)


# a straight 60 x 12 m deck along x, its mapped bridge and approaches
DECK = _box(-30.0, -6.0, 30.0, 6.0)
WAYS = [_way(1, [(-80.0, 0.0), (-30.5, 0.0)], highway="primary"),
        _way(2, [(-30.5, 0.0), (30.5, 0.0)], highway="primary", bridge="yes", layer="1"),
        _way(3, [(30.5, 0.0), (80.0, 0.0)], highway="primary")]


def test_straight_bridge_holds_w1_to_w5():
    up = _slab(DECK, 6.0)
    w = BW.deck_witness(DECK, up, up, WAYS, LAW, ground=_ground)
    assert w.failed == "", w.failed
    r = w.route
    assert set(r.ways) == {1, 2, 3} and r.bridge_m >= 59.0 and r.cover > 0.99
    assert abs(abs(r.end_a[0]) - 30.0) < 1e-6 and abs(abs(r.end_b[0]) - 30.0) < 1e-6
    assert abs(r.out_a[0]) > 0.99 and r.out_a[0] * r.out_b[0] < 0.0
    assert w.surface_share == 1.0 and w.roof_share == 0.0 and w.span.startswith("ground")


def test_curved_ramp_reads_its_route_not_its_rectangle():
    arc = LineString([(80.0 * math.cos(t), 80.0 * math.sin(t))
                      for t in np.linspace(0.0, math.pi / 2.0, 40)])
    plate = arc.buffer(6.0, cap_style="flat")
    up = _strip(arc, 6.0, lambda s: 2.0 + 0.04 * s)
    pts = list(arc.coords)
    ways = [_way(1, [(80.0, -40.0), pts[0]], highway="primary"),
            _way(2, pts, highway="primary", bridge="yes"),
            _way(3, [pts[-1], (-40.0, 80.0)], highway="primary")]
    ways.append(_way(9, [(30.0, 30.0), (90.0, 90.0)], highway="service"))
    w = BW.deck_witness(plate, up, up, ways, LAW)
    assert w.failed == "", w.failed
    assert w.route.s_b - w.route.s_a > 120.0 and w.span == "way 9"


def test_floor_with_a_road_along_one_edge_fails_the_ribbon():
    floor = _box(0.0, 0.0, 80.0, 60.0)
    ways = [_way(1, [(-20.0, 2.0), (100.0, 2.0)], highway="service", bridge="yes")]
    w = BW.deck_witness(floor, _slab(floor, 5.0), _slab(floor, 5.0), ways, LAW)
    assert w.failed.startswith("W2"), w.failed


def test_trench_with_bridges_across_reads_through_but_is_no_bridge():
    trench = _box(0.0, -15.0, 200.0, 15.0)
    ways = [_way(k, [(x, -60.0), (x, 60.0)], highway="primary", bridge="yes")
            for k, x in ((1, 50.0), (2, 150.0))]
    w = BW.deck_witness(trench, _slab(trench, -6.0), _slab(trench, -6.0), ways, LAW)
    assert w.failed.startswith("W2"), w.failed
    assert BW.route_of(trench, ways, LAW).bridge_m >= 29.0


def test_canopy_over_a_road_fails_open_sky():
    up = _slab(DECK, 6.0)
    roof = _slab(DECK, 9.5)
    w = BW.deck_witness(DECK, up, np.concatenate([up, roof]), WAYS, LAW, ground=_ground)
    assert w.failed.startswith("W4"), w.failed


def test_pylon_tops_are_not_the_driven_surface():
    up = _slab(DECK, 6.0)
    tops = np.concatenate([_slab(_box(x - 1.0, -1.0, x + 1.0, 1.0), 16.0)
                           for x in (-20.0, 0.0, 20.0)])
    faces = np.concatenate([up, tops])
    w = BW.deck_witness(DECK, faces, faces, WAYS, LAW, ground=_ground)
    assert w.failed == "", w.failed
    assert np.nanmax(w.layer) == 6.0


def test_station_on_a_viaduct_is_refused():
    up = _slab(DECK, 6.0)
    hall = _slab(_box(-20.0, -8.0, 20.0, 8.0), 10.0)
    w = BW.deck_witness(DECK, up, np.concatenate([up, hall]), WAYS, LAW, ground=_ground)
    assert w.failed.startswith("W4")
    v = classify(DeckFacts(witness=w))
    assert v.cls == "not_a_bridge" and v.reason.startswith("W4")


def test_a_building_beside_the_deck_makes_it_attached():
    up = _slab(DECK, 6.0)
    decks = {"d": (DECK, up, "flag")}
    pier = np.array([[0.0, 0.0], [1.0, 1.0], [-1.0, 1.0]])
    hall = np.array([[0.0, 60.0], [40.0, 60.0], [40.0, 100.0], [0.0, 100.0]])
    free = BW.frame_witness(decks, up, {"d": pier, "pier": pier}, WAYS, LAW, _ground)
    assert free["d"].frame_failed == ""
    assert classify(DeckFacts(witness=free["d"])).cls == "free_bridge"
    held = BW.frame_witness(decks, up, {"pier": pier, "hall": hall}, WAYS, LAW, _ground)
    assert held["d"].frame_failed.startswith("W6") and "hall" in held["d"].frame_failed
    assert classify(DeckFacts(witness=held["d"])).cls == "attached_bridge"


def test_a_touching_stub_joins_its_group():
    stub = _box(30.0, -6.0, 45.0, 6.0)
    sup = _slab(stub, 6.0)
    up = _slab(DECK, 6.0)
    decks = {"d": (DECK, up, "flag"), "s": (stub, sup, "flag")}
    ways = WAYS[:2] + [_way(3, [(30.5, 0.0), (32.0, 30.0)], highway="primary")]
    got = BW.frame_witness(decks, np.concatenate([up, sup]), {}, ways, LAW, _ground)
    assert got["d"].failed == "" and got["s"].failed.startswith(("W1", "W2"))
    assert got["s"].joined == "d"
    assert classify(DeckFacts(witness=got["s"])).cls == "free_bridge"
    wide = _box(30.0, -60.0, 60.0, 60.0)
    decks["s"] = (wide, _slab(wide, 6.0), "flag")
    got = BW.frame_witness(decks, up, {}, ways, LAW, _ground)
    assert got["s"].joined == "" and "refused" in got["s"].failed


def test_the_class_table_precedence():
    w = BW.Witness(None, failed="W1 route: no mapped route over the plate")
    assert CLASSES[0] == "stack_deck" and CLASSES[-1] == "not_a_bridge"
    assert classify(DeckFacts(in_stack=True, frame_cut=True)).cls == "stack_deck"
    assert classify(DeckFacts(frame_cut=True, airside=True)).cls == "cut_deck"
    assert classify(DeckFacts(airside=True, overpass=True)).cls == "airside_hard_deck"
    assert classify(DeckFacts(overpass=True, witness=w)).cls == "road_overpass"
    assert classify(DeckFacts(all_deck_frame=True, witness=w)).cls == "all_deck_frame"
    assert classify(DeckFacts(graded=True, witness=w)).cls == "graded_deck"
    v = classify(DeckFacts(witness=w))
    assert v.cls == "not_a_bridge" and v.reason.startswith("W1")


def test_the_chain_join_and_the_overpass_route_are_unchanged():
    reach = DECK.buffer(5.0)
    under = _way(7, [(0.0, -40.0), (0.0, 40.0)], highway="secondary")
    ways = WAYS + [under]
    chains = sorted(sorted(ways[k].id for k in c) for c in route_chains(ways, reach))
    assert chains == [[1, 2, 3], [7]]
    # a junction of roads at grade ends a chain
    t = [_way(1, [(-50.0, 0.0), (0.0, 0.0)], highway="service"),
         _way(2, [(0.0, 0.0), (50.0, 0.0)], highway="service"),
         _way(3, [(0.0, 0.0), (0.0, 50.0)], highway="service")]
    assert len(route_chains(t, _box(-60.0, -60.0, 60.0, 60.0))) == 3
    assert _own_route(DECK, ways, 5.0) == {1, 2, 3}


def test_every_z_at_reads_every_face_and_floor_z_at_the_lowest():
    faces = np.concatenate([_slab(_box(0.0, 0.0, 10.0, 10.0), z) for z in (1.0, 4.0)])
    zs = every_z_at(faces, [5.0, 20.0], [5.0, 5.0])
    assert sorted(set(zs[0].round(6))) == [1.0, 4.0] and zs[1].size == 0
    assert floor_z_at(faces, [5.0], [5.0])[0] == 1.0


def test_ribbon_centreline_follows_a_curve():
    arc = LineString([(50.0 * math.cos(t), 50.0 * math.sin(t))
                      for t in np.linspace(0.0, math.pi, 60)])
    line = ribbon_centreline(arc.buffer(5.0, cap_style="flat"))
    assert line is not None and line.length > 0.8 * arc.length
    # the diameter runs into a corner at each end (within the half-width)
    mid = [line.interpolate(f, normalized=True) for f in np.linspace(0.1, 0.9, 30)]
    assert max(arc.distance(p) for p in mid) < 1.0
    assert max(arc.distance(Point(p)) for p in line.coords) <= 5.0


# ── A1 (``2065-bridge-class-A1.md`` §A1, §A4 S0): W6 reach, W7 ends, W4b ──

STUB = _box(30.0, -6.0, 45.0, 6.0)
STUB_WAYS = WAYS[:2] + [_way(3, [(30.5, 0.0), (32.0, 30.0)], highway="primary")]


def _line_body(x0, x1, y):
    return np.array([(x, y) for x in np.linspace(x0, x1, 20)])


def _stub_frame(bodies):
    up, sup = _slab(DECK, 6.0), _slab(STUB, 6.0)
    decks = {"d": (DECK, up, "flag"), "s": (STUB, sup, "flag")}
    return BW.frame_witness(decks, np.concatenate([up, sup]), bodies, STUB_WAYS, LAW, _ground)


def test_w6_lamps_off_a_stub_and_a_wing_wall_are_the_bridges_own():
    got = _stub_frame({"lamps": _line_body(32.0, 44.0, 6.8),
                       "wing": _line_body(-30.0, 30.0, -6.0 - 0.2 * 12.0)})
    assert got["s"].joined == "d"
    assert got["d"].frame_failed == "" and got["d"].reach_m == 6.0
    assert classify(DeckFacts(witness=got["s"])).cls == "free_bridge"
    # the stub's ends are its axis's: the one at the deck a joint, the other land
    ends = got["s"].ends
    assert len(ends) == 2 and sorted(e.land for e in ends) == [False, True]
    joint = next(e for e in ends if not e.land)
    assert abs(joint.point[0] - 30.0) < 2.0 and got["s"].axis is not None


def test_w6_a_hall_seven_widths_out_attaches():
    got = _stub_frame({"hall": _line_body(-20.0, 20.0, 6.0 + 7.0 * 12.0)})
    assert got["d"].frame_failed.startswith("W6") and "hall" in got["d"].frame_failed
    assert classify(DeckFacts(witness=got["d"])).cls == "attached_bridge"
    # W7 / W4b are not read for an attached frame; its ends are still kept
    assert got["d"].end_failed == "" and len(got["d"].ends) == 2
    assert all(math.isnan(e.run_on) for e in got["d"].ends)


def _carried(x_end):
    return [_way(1, [(-80.0, 0.0), (-30.5, 0.0)], highway="primary"),
            _way(2, [(-30.5, 0.0), (x_end, 0.0)], highway="primary", bridge="yes"),
            _way(3, [(x_end, 0.0), (x_end + 60.0, 0.0)], highway="primary")]


def test_w7_a_bridge_running_on_past_an_end_is_a_joint():
    up = _slab(DECK, 6.0)
    far = BW.frame_witness({"d": (DECK, up, "flag")}, up, {}, _carried(60.0), LAW, _ground)
    w = far["d"]
    assert w.end_failed.startswith("W7") and "end b" in w.end_failed, w.end_failed
    assert abs(w.ends[1].run_on - 30.0) < 0.6 and not w.ends[1].land and w.ends[0].land
    v = classify(DeckFacts(witness=w))
    assert v.cls == "not_a_bridge" and v.reason.startswith("W7")
    near = BW.frame_witness({"d": (DECK, up, "flag")}, up, {}, _carried(40.0), LAW, _ground)
    assert near["d"].end_failed == "" and abs(near["d"].ends[1].run_on - 10.0) < 0.6
    assert all(e.land for e in near["d"].ends)
    assert classify(DeckFacts(witness=near["d"])).cls == "free_bridge"


def test_w7_an_end_abutting_a_deck_of_its_group_is_exempt():
    d2 = _box(30.0, -6.0, 90.0, 6.0)
    up1, up2 = _slab(DECK, 6.0), _slab(d2, 6.0)
    ways = [_way(1, [(-80.0, 0.0), (-30.5, 0.0)], highway="primary"),
            _way(2, [(-30.5, 0.0), (90.5, 0.0)], highway="primary", bridge="yes"),
            _way(3, [(90.5, 0.0), (150.0, 0.0)], highway="primary"),
            _way(9, [(60.0, -40.0), (60.0, 40.0)], highway="service")]
    got = BW.frame_witness({"d1": (DECK, up1, "flag"), "d2": (d2, up2, "flag")},
                           np.concatenate([up1, up2]), {}, ways, LAW, _ground)
    for k in ("d1", "d2"):
        assert got[k].failed == "" and got[k].end_failed == "", (k, got[k])
        assert classify(DeckFacts(witness=got[k])).cls == "free_bridge"
    assert got["d1"].ends[1].run_on > 20.0 and not got["d1"].ends[1].land


def test_w4b_a_roof_over_another_objects_deck_fails_and_a_crossing_deck_passes():
    up = _slab(DECK, 14.0)
    other = _slab(_box(-30.0, -6.0, 30.0, 6.0), 6.0)
    got = BW.frame_witness({"d": (DECK, up, "flag")}, up, {}, WAYS, LAW, _ground,
                           under=lambda _b: other)
    assert got["d"].end_failed.startswith("W4b") and got["d"].beneath == 1.0
    assert classify(DeckFacts(witness=got["d"])).cls == "not_a_bridge"
    cross = _slab(_box(-5.0, -20.0, 5.0, 20.0), 8.0)
    got = BW.frame_witness({"d": (DECK, up, "flag")}, up, {}, WAYS, LAW, _ground,
                           under=lambda _b: cross)
    assert got["d"].end_failed == "" and 0.0 < got["d"].beneath <= BW.ROOF_UNDER_SHARE


def test_the_a1_class_order():
    held = BW.Witness(None, span="ground 4.0 m")
    assert BW.Witness(None).end_failed == ""
    assert CLASSES.index("all_deck_frame") < CLASSES.index("plated_deck") \
        < CLASSES.index("free_bridge") < CLASSES.index("attached_bridge")
    assert classify(DeckFacts(all_deck_frame=True, witness=held)).cls == "all_deck_frame"
    # A1-E1 E1: deck_datum_z is not read once the witness holds
    assert classify(DeckFacts(graded=True, plated=True, witness=held)).cls == "plated_deck"
    assert classify(DeckFacts(graded=True, witness=held)).cls == "free_bridge"
    assert classify(DeckFacts(plated=True, witness=held)).cls == "plated_deck"
    assert classify(DeckFacts(witness=held)).cls == "free_bridge"
    w6 = _dc_replace(held, frame_failed="W6 free frame: x", end_failed="")
    assert classify(DeckFacts(plated=True, witness=w6)).cls == "attached_bridge"
    w7 = _dc_replace(held, end_failed="W7 ends: end a is a joint")
    assert classify(DeckFacts(graded=True, witness=w7)).cls == "graded_deck"
    v = classify(DeckFacts(plated=True, witness=w7))
    assert v.cls == "not_a_bridge" and v.reason.startswith("W7")


def _dc_replace(w, **kw):
    import dataclasses
    return dataclasses.replace(w, **kw)


def test_w4b_reads_an_object_by_its_faces_not_its_origin():
    """A1-E1 E2: an object whose origin stands 1 km from its geometry is
    still read under the deck; another unit's faces shift by the agl_m
    difference when there is no DEM (``unshifted``)."""
    import importlib.util
    import os
    import types
    p = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "bridge_census.py")
    spec = importlib.util.spec_from_file_location("_bridge_census_twin", p)
    BC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(BC)
    verts = np.array([[1000.0, 2.0, 0.0], [1010.0, 2.0, 0.0], [1000.0, 2.0, -10.0]])
    g = types.SimpleNamespace(vertices=verts, solid=np.array([[0, 1, 2]]))
    geoms = types.SimpleNamespace(of=lambda m: g)
    m = {"id": "far", "origin": [0.0, 0.0], "heading_deg": 0.0}
    own = {"id": "unit:0", "agl_m": 0.0, "members": []}
    other = {"id": "unit:1", "agl_m": 3.0, "members": [m]}
    U = BC._Under([own, other], geoms, lambda lon, lat: (lon, lat), 0.9, None)
    got = U.for_unit(own)((1002.0, 2.0, 1004.0, 4.0))
    assert len(got) == 1 and np.allclose(got[0, :, 2], 5.0)
    assert U.unshifted == {"unit:0"}
    assert len(U.for_unit(own)((0.0, 0.0, 5.0, 5.0))) == 0
