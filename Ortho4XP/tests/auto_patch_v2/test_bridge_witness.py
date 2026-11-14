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
