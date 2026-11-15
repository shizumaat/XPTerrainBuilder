"""l2090d twins (#2090; RULINGS 2026-11-14f (1)): a pack deck whose route the
load's feed box missed has it read at the pack stage (``airport/deck_routes``),
and a deck no mapped route crosses is read along its own axis when a mapped
way stands a lawful clearance under both its ends (``airport/bridge_axis``).
Synthetic frames in metres."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import bridge_axis as BA
from auto_patch_v2.airport import bridge_witness as BW
from auto_patch_v2.airport import deck_routes as DRT
from auto_patch_v2.airport import osm as OSM
from auto_patch_v2.law import Law
from auto_patch_v2.model.frame import Frame
from shapely.geometry import Polygon
from shapely.geometry import box as _box

LAW = Law.for_airport("")
FRAME = Frame("TEST", (40.0, -100.0), 9)


def _way(i, pts, **tags):
    return types.SimpleNamespace(id=i, points=tuple(pts), tags=dict(tags))


def _slab(poly: Polygon, z: float) -> np.ndarray:
    c = list(poly.exterior.coords)[:-1]
    return np.array([[(*c[0], z), (*c[k], z), (*c[k + 1], z)] for k in range(1, len(c) - 1)])


# a 60 x 12 m deck along x over a motorway crossing at x = 0 on the skew
DECK = _box(-30.0, -6.0, 30.0, 6.0)
MOTORWAY = _way(7, [(-20.0, -40.0), (20.0, 40.0)], highway="motorway")


def _embankment(xs, ys):
    """Ground 7 m up at both deck ends, 0 at the motorway under the span."""
    return 7.0 * np.minimum(np.abs(np.asarray(xs, float)) / 25.0, 1.0)


def test_an_unmapped_deck_over_a_way_on_its_embankment_holds_along_its_axis():
    up = _slab(DECK, 7.5)
    w = BW.deck_witness(DECK, up, up, [MOTORWAY], LAW, ground=_embankment)
    assert w.failed == "", w.failed
    assert w.route.ways == () and w.span.startswith("axis way 7")
    assert abs(abs(w.route.end_a[0]) - 30.0) < 1e-6 and abs(abs(w.route.end_b[0]) - 30.0) < 1e-6
    assert BW.any_route([DECK], [MOTORWAY], LAW, _embankment)
    assert not BW.any_route([DECK], [MOTORWAY], LAW)          # no ground: no span read


def test_an_unmapped_deck_on_level_ground_or_over_nothing_keeps_w1s_failure():
    up = _slab(DECK, 0.5)
    level = BW.deck_witness(DECK, up, up, [MOTORWAY], LAW,
                            ground=lambda xs, ys: np.zeros(len(xs)))
    assert level.route is None and level.failed.startswith("W1 route")
    nothing = BW.deck_witness(DECK, up, up, [], LAW, ground=_embankment)
    assert nothing.route is None and nothing.failed.startswith(BW.NO_ROUTE)
    assert not BW.any_route([DECK], [], LAW, _embankment)


def test_the_axis_span_needs_the_clearance_under_both_ends():
    r = BA.axis_route(DECK, LAW)
    st = BW._stations(r.path, r.s_a, r.s_b, 5.0)
    bar = float(LAW.tables.structures.bridge.clearance_minimum_m)

    def one_end_low(xs, ys):
        g = _embankment(xs, ys)
        return np.where(np.asarray(xs) < -20.0, bar - 0.5, g)
    assert BA.axis_span(r, st, [MOTORWAY], LAW, _embankment).startswith("way 7")
    assert BA.axis_span(r, st, [MOTORWAY], LAW, one_end_low) == ""


def _doc(ways):
    raw = [OSM.RawWay(f"+40-100:{i}", tuple(pts), tags) for i, pts, tags in ways]
    return OSM.OsmDoc("big_roads", tuple(raw), (), OSM.RelationReport(), ())


def test_a_far_decks_route_and_its_continuation_are_read(monkeypatch):
    to_ll = FRAME.transformers()[1]
    to_xy = FRAME.entry()
    # a 16 m rail viaduct 9 km east of the reference point (past a 0.05 deg box)
    x0 = 9000.0
    deck = types.SimpleNamespace(id="dsf:obj1", resolved="x.obj", deck_top_z=16.0,
                                 hard_deck=_box(x0 - 30.0, -6.0, x0 + 30.0, 6.0))

    def ll(x, y):
        return to_ll(x, y)
    viaduct = [ll(x0 - 40.0, 0.0), ll(x0 + 40.0, 0.0)]
    on = [ll(x0 + 40.0, 0.0), ll(x0 + 400.0, 0.0)]
    beside = [ll(x0 - 20.0, 200.0), ll(x0 + 20.0, 200.0)]
    feed = _doc([(-1, viaduct, {"railway": "rail", "bridge": "viaduct"}),
                 (-2, on, {"railway": "rail"}),
                 (-3, beside, {"highway": "service"})])
    monkeypatch.setattr(OSM, "load_feed", lambda *a, **k: feed)
    monkeypatch.setattr(OSM, "ROAD_FEEDS", ("big_roads",))
    airport = types.SimpleNamespace(frame=FRAME, osm_ways=())
    import dataclasses as dc
    monkeypatch.setattr(dc, "replace", lambda o, **kw: types.SimpleNamespace(
        **{**vars(o), **kw}))
    got, notes = DRT.attach_deck_routes(airport, [deck], "root", LAW, 0.05)
    assert sorted(w.id for w in got.osm_ways) == [-2, -1] and notes
    assert got.osm_ways[0].points[0] == to_xy(viaduct[0][1], viaduct[0][0])
    # a deck whose reach lies inside the box reads nothing
    near = types.SimpleNamespace(id="dsf:obj2", resolved="x.obj", deck_top_z=1.0,
                                 hard_deck=_box(-30.0, -6.0, 30.0, 6.0))
    assert DRT.attach_deck_routes(airport, [near], "root", LAW, 0.05) == (airport, [])
