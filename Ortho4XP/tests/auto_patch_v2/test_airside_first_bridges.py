"""Airside-first generated bridges (``docs/specs/airside-first-bridges-
spec.md``; owner RULINGS 2026-11-19s): the deck top is the no-bridge
surface, flush by construction; one deck per taxiway at its class width;
the carve never fixes or frees an airside level it should not; the lip
runs on the sides only.  Headless, synthetic."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.geom.coons_patch import CoonsPatch, edge_profiles, profile_at


def _patch():
    # a 10 x 20 parallelogram: u along the route (y), w across it (x)
    a = ((0.0, 10.0), (0.5, 10.2), (1.0, 10.0))       # end A, crowned
    b = ((0.0, 11.0), (0.5, 11.2), (1.0, 11.0))       # end B, 1 m higher
    s0 = ((0.0, 10.0), (0.5, 10.6), (1.0, 11.0))      # a vertical curve
    s1 = ((0.0, 10.0), (1.0, 11.0))
    return CoonsPatch((0.0, 0.0), (0.0, 20.0), (10.0, 0.0), a, b, s0, s1)


def test_coons_patch_is_exact_on_every_edge():
    p = _patch()
    for t in (0.0, 0.25, 0.5, 0.8, 1.0):
        assert p.z(10.0 * t, 0.0) == pytest.approx(profile_at(p.a, t))
        assert p.z(10.0 * t, 20.0) == pytest.approx(profile_at(p.b, t))
    for s in (0.0, 0.3, 0.5, 1.0):
        assert p.z(0.0, 20.0 * s) == pytest.approx(profile_at(p.s0, s))
        assert p.z(10.0, 20.0 * s) == pytest.approx(profile_at(p.s1, s))
    # the crown carries across the span
    assert p.z(5.0, 10.0) > p.z(9.0, 10.0)
    assert p.low() == pytest.approx(10.0)


def test_edge_profiles_reads_samples_on_the_edges_only():
    smp = [(0.0, 0.0, 1.0), (10.0, 0.0, 1.2), (5.0, 0.02, 1.4),     # end A
           (0.0, 20.0, 2.0), (10.0, 20.0, 2.2),                      # end B
           (5.0, 10.0, 99.0)]                                        # interior: ignored
    p = edge_profiles((0.0, 0.0), (0.0, 20.0), (10.0, 0.0), smp, tol=0.05)
    assert p is not None
    assert p.z(5.0, 0.0) == pytest.approx(1.4)
    assert p.z(5.0, 10.0) < 50.0
    assert edge_profiles((0.0, 0.0), (0.0, 20.0), (10.0, 0.0), smp[3:5]) is None


def _law(**kw):
    from auto_patch_v2.law.deck_gen_schema import DeckGenLaw
    g = DeckGenLaw(**kw)
    return types.SimpleNamespace(tables=types.SimpleNamespace(
        structures=types.SimpleNamespace(deck_gen=g)))


def test_one_deck_per_taxiway_at_its_class_width():
    from auto_patch_v2.planar.deck_width import route_decks
    nodes = {1: types.SimpleNamespace(xy=(0.0, -100.0)), 2: types.SimpleNamespace(xy=(0.0, 100.0)),
             3: types.SimpleNamespace(xy=(60.0, -100.0)), 4: types.SimpleNamespace(xy=(60.0, 100.0))}
    def edge(a, b, c, name):
        return types.SimpleNamespace(a=a, b=b, name=name, is_runway=False, width_class=c)
    airport = types.SimpleNamespace(taxi_nodes=nodes, taxi_edges=[edge(1, 2, "C", "A"),
                                                                  edge(3, 4, "E", "B")])
    # the pavement over a road running along x: one piece spanning both taxiways
    piece = Polygon([(-40, -15), (100, -15), (100, 15), (-40, 15)])
    got = route_decks(piece, (1.0, 0.0), airport, _law())
    assert len(got) == 2
    widths = sorted(round(r.bounds[2] - r.bounds[0], 6) for r, _n in got)
    assert widths == [25.0, 38.0]
    for r, _n in got:
        assert r.bounds[1] == pytest.approx(-15.0) and r.bounds[3] == pytest.approx(15.0)
    # the gap between them stays open
    (r0, _), (r1, _) = got
    assert r0.intersection(r1).area == 0.0


def test_lip_runs_on_the_sides_only():
    from auto_patch_v2.airport.deck_structure import end_edges
    ring = Polygon([(-5, -10), (5, -10), (5, 10), (-5, 10)])     # route along z
    # end lines read far off the ring (KBNA 1.0.565): the ends are still ends
    ends = end_edges(ring, [[(-50.0, 0.0), (-49.0, 0.0)]], 4.0, 25.0)
    assert len(ends) == 2
    assert all(abs(a[1] - b[1]) < 1e-9 for a, b in ends)


def test_the_carve_fixes_unmapped_airside_and_frees_ground(monkeypatch):
    from auto_patch_v2.constraints import deck_floor_follow as dff
    from auto_patch_v2.constraints.edge_floor import DECK_FLOOR
    from auto_patch_v2.model import platform
    from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
    from auto_patch_v2.model.structures import GENERATED_WITNESS, DeckBridge
    ring = ((0.0, 0.0), (10.0, 0.0), (10.0, 20.0), (0.0, 20.0))
    db = DeckBridge("o4gen_t", "objects/o4_generated/deck_t.obj", (), ring,
                    ((0.0, 0.0), (10.0, 0.0)), ((0.0, 20.0), (10.0, 20.0)), 0.0, 0.0,
                    -6.0, 100.0, witness=GENERATED_WITNESS, floor_min_m=6.0)
    def V(x, y):
        return types.SimpleNamespace(xy=(x, y), incident_faces=())
    # stage 1: the filled ring's corners and a crowned end line
    s1pm = types.SimpleNamespace(vertices={0: V(0, 0), 1: V(5, 0), 2: V(10, 0),
                                           3: V(0, 20), 4: V(10, 20)})
    stage1 = types.SimpleNamespace(pm=s1pm, solved={0: 100.0, 1: 100.2, 2: 100.0,
                                                    3: 101.0, 4: 101.0})
    # the full map: 10 an end-line station stage 1 lacks (airside), 11 the
    # bank's crest on a side the join fixed (ground), 12 a floor vertex
    pm = types.SimpleNamespace(decks=(db,), vertices={10: V(2.5, 0.0), 11: V(0.0, 10.0),
                                                      12: V(5.0, 10.0)}, faces={},
                               structures=(types.SimpleNamespace(id="tn", deck_bridge="o4gen_t"),))
    monkeypatch.setattr(platform, "stage_air_vertices", lambda _pm, _law: {10})
    cs = ConstraintSet.from_rows([Pin(12, 99.0, Source("structures", DECK_FLOOR, ("tn",)))])
    from auto_patch_v2.law import Law
    cs2, s2 = dff.floor_follow_rewrite(pm, cs, {11: 100.5}, stage1, law=Law.load())
    assert s2.fixed == {10: pytest.approx(100.1)}
    assert s2.free == frozenset({11})
    assert cs2.pins[0].z == pytest.approx(100.0 - 6.0)
    keys = s2.stage_two({"stage2_free": {7}})
    assert keys["stage2_free"] == frozenset({7, 11})
    assert set(keys["generated_tops"]["o4gen_t"]) == {"o", "u", "w", "a", "b", "s0", "s1"}


def test_one_taxiway_of_many_edges_is_one_deck_and_its_ends_are_read():
    from auto_patch_v2.planar.deck_width import route_decks, route_ends
    nodes = {1: types.SimpleNamespace(xy=(0.0, -100.0)), 2: types.SimpleNamespace(xy=(0.5, 0.0)),
             3: types.SimpleNamespace(xy=(6.0, 100.0))}
    def edge(a, b):
        return types.SimpleNamespace(a=a, b=b, name="L", is_runway=False, width_class="C")
    airport = types.SimpleNamespace(taxi_nodes=nodes, taxi_edges=[edge(1, 2), edge(2, 3)])
    piece = Polygon([(-40, -15), (40, -15), (40, 15), (-40, 15)])
    got = route_decks(piece, (1.0, 0.0), airport, _law())
    assert len(got) == 1
    ring = got[0][0]
    # a deck inside a wider pavement: its ends are its own edges along the road
    wide = Polygon([(-60, -60), (60, -60), (60, 60), (-60, 60)])
    ends = route_ends(ring, (1.0, 0.0), lambda xy: "taxiway" if wide.contains(
        Polygon([(xy[0] - .1, xy[1] - .1), (xy[0] + .1, xy[1] - .1), (xy[0] + .1, xy[1] + .1)]))
        else None, lambda r: r == "taxiway", 2.0, lambda x, y: (y, x))
    assert ends is not None
    for e in ends:
        assert len({round(lat, 6) for lat, _lon in e}) == 1     # one edge each, along the road
