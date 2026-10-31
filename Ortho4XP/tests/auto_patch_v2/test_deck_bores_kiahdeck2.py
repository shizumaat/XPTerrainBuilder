"""kiahdeck2 twins (owner RULINGS 2026-10-30a (2), 30b, 30f (1), 30g;
``planar/deck_bores``, ``planar/deck_bridge``): a hard deck bores the road
under it when nothing else does; the carriageways under one deck are one cut
only where they are one road; the deck's end lines are the facing contacts
the road under it runs along; a §34 (5) bore under a deck is that deck's,
wherever its ribbon put its ends."""
from __future__ import annotations

import types

from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import deck_bores as DBO
from auto_patch_v2.planar import deck_bridge as DB
from auto_patch_v2.planar.structure_underpass import UNDERPASS_TAG
from shapely.geometry import LineString
from shapely.geometry import box as _sbox

LAW = Law.for_airport("")
SEP = LAW.tables.structures.tunnel.dual_carriageway_max_separation_m


def _deck(oid="dsf:obj1"):
    """A 200 m deck along an E-W taxiway (x -100..100), 30 m across the
    road under it (y -15..15); its end lines at x = -100 / +100."""
    ring = tuple(_sbox(-100.0, -15.0, 100.0, 15.0).exterior.coords[:-1])
    a = tuple((-100.0, y) for y in (-10.0, 0.0, 10.0))
    b = tuple((100.0, y) for y in (-10.0, 0.0, 10.0))
    return DB.DeckBridge(oid, "objects/deck.obj", (oid,), ring, a, b, 1.5, 1.5, -3.5, 30.0)


def _road(wid, x, highway="primary", y0=-200.0, y1=200.0):
    return OsmWay(wid, "big_roads", ((x, y0), (x, y1)), False,
                  {"highway": highway, "lanes": "2"})


def test_a_hard_deck_bores_the_road_under_it_that_nothing_else_bores():
    db = _deck()
    roads = [_road(-1, -60.0), _road(-2, 60.0)]
    bored = [OsmWay(-2, "big_roads", ((60.0, -12.0), (60.0, 12.0)), False,
                    {"highway": "primary", "tunnel": "yes"})]
    ways, parents, notes = DBO.deck_bores((db,), roads, bored, LAW, UNDERPASS_TAG)
    assert [w.id for w in ways] == [-1]                 # -2 already runs in a bore
    w = ways[0]
    assert w.tags["tunnel"] == LAW.tables.structures.tunnel.admitted_values[0]
    assert w.tags[UNDERPASS_TAG] == "dsf:obj1"
    ys = sorted(y for _x, y in w.points)
    assert -15.0 < ys[0] < -12.0 and 12.0 < ys[-1] < 15.0   # the ring less the rim stand-off
    assert parents[id(w)].length == 400.0 and "bores 1 road" in notes[0]


def test_a_road_whose_carriageway_meets_an_end_line_is_not_under_the_deck():
    """A road along the deck's end (its carriageway reaching past the end
    line) and a road running beside the deck never under its midline are
    not bored."""
    db = _deck()
    along_end = OsmWay(-3, "big_roads", ((-98.0, -200.0), (-98.0, 200.0)), False,
                       {"highway": "service"})
    beside = OsmWay(-4, "big_roads", ((-200.0, 13.5), (200.0, 13.5)), False,
                    {"highway": "service"})
    ways, _p, notes = DBO.deck_bores((db,), [along_end, beside], [], LAW, UNDERPASS_TAG)
    assert ways == [] and notes == []


def test_carriageways_farther_apart_than_one_road_are_two_lanes_of_one_deck():
    """obj24549: two carriageways 120 m apart under one deck are two cuts,
    the bank split halfway across the median; two 15 m apart are one."""
    db = _deck()

    def mouth(x):
        return types.SimpleNamespace(xy=(x, 0.0))
    ms = [mouth(-60.0), mouth(-45.0), mouth(60.0)]
    lane_of, centres = DBO.deck_lanes(ms, {id(m): db for m in ms}, SEP)
    assert [lane_of[id(m)] for m in ms] == [0, 0, 1]
    assert centres[id(db)] == [-52.5, 60.0]
    assert DBO.lane_band(db, centres[id(db)], 0) == (float("-inf"), 3.75)
    assert DBO.lane_band(db, centres[id(db)], 1) == (3.75, float("inf"))
    assert DBO.lane_band(db, [0.0], 0) is None


def test_a_lanes_bank_stops_halfway_to_the_next_carriageway():
    db = _deck()
    axis, _d = DB.deck_mouth(LineString([(60.0, 18.0), (60.0, 120.0)]), (0.0, -1.0), db)
    ramp = _sbox(55.0, -10.0, 65.0, 100.0)
    outer = ramp.buffer(1.6, join_style="mitre")
    _r, whole = DB.deck_cut(db, axis, ramp, outer, 0.6)
    _r, lane = DB.deck_cut(db, axis, ramp, outer, 0.6, band=(3.75, float("inf")))
    assert abs(whole.bounds[0] + 99.4) < 1e-6
    assert abs(lane.bounds[0] - 3.75) < 1e-6 and abs(lane.bounds[2] - 99.4) < 1e-6


def test_the_end_lines_are_the_facing_pair_the_road_runs_along():
    """obj24551: a deck the pavement meets on its long sides AND at its
    ends reads the ends as its end lines when the road crosses its width."""
    sides = ([(0.0002, x * 1e-5) for x in range(-5, 6)],
             [(-0.0002, x * 1e-5) for x in range(-5, 6)])
    ends = ([(y * 1e-5, -0.001) for y in range(-2, 3)],
            [(y * 1e-5, 0.001) for y in range(-2, 3)])

    def to_xy(lon, lat):
        return (lon * 1e5, lat * 1e5)
    assert DB._end_pair([sides, ends], (0.0, 1.0), to_xy) is ends
    assert DB._end_pair([sides, ends], None, to_xy) is sides
    assert DB._end_pair([], (0.0, 1.0), to_xy) is None


def test_a_bore_synthesised_under_an_aeroway_bridge_is_its_decks_wherever_it_ends():
    db = _deck()
    way = OsmWay(-5, "big_roads", ((-60.0, -40.0), (-60.0, 40.0)), False,
                 {"highway": "service", UNDERPASS_TAG: "-67"})
    bore = types.SimpleNamespace(ways=[way], line=LineString(way.points))
    m = types.SimpleNamespace(xy=(-60.0, 40.0), bore=bore)
    assert DB.deck_under(m, (db,), 6.6) is db
    mapped = OsmWay(-6, "big_roads", way.points, False, {"highway": "service", "tunnel": "yes"})
    m2 = types.SimpleNamespace(xy=(-60.0, 40.0), bore=types.SimpleNamespace(
        ways=[mapped], line=LineString(mapped.points)))
    assert DB.deck_under(m2, (db,), 6.6) is None
