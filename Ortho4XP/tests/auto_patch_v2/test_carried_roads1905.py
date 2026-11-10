"""#1905 twin (owner RULINGS 2026-11-10f (1), SBSP "b"): an untagged road
under a pack deck, mapped within a metre of a road the map places lower,
is the deck's own CARRIED road and mints no ground ribbon under the deck
(``airport/carried_roads``).  Hermetic: a metre frame (lat = y, lon = x),
the deck pieces stubbed."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import bridge_family as BF
from auto_patch_v2.airport import carried_roads as CR
from auto_patch_v2.airport import partition_prints as PP
from auto_patch_v2.airport.road_ways import ribbon_half_width_m
from auto_patch_v2.law import Law
from shapely.geometry import box

LAW = Law.for_airport("SBSP")


class _Piece:
    """A deck piece: everything inside ``area`` (frame metres) is its."""

    def __init__(self, area):
        self.area = area
        x0, y0, x1, y1 = area.bounds
        self.box = (y0, x0, y1, x1)

    def contains_many(self, lats, lons, tol_m=0.5):
        from shapely.geometry import Point
        return [self.area.distance(Point(lo, la)) <= tol_m
                for la, lo in zip(lats, lons, strict=True)]


class _Frame:
    def transformers(self):
        return (lambda lon, lat: (lon, lat)), (lambda x, y: (y, x))


def _way(wid, pts, **tags):
    return types.SimpleNamespace(id=wid, kind="airport_small_roads", points=tuple(pts),
                                 closed=False, tags={"highway": "service", **tags})


def _airport(ways):
    return types.SimpleNamespace(partition=object(), frame=_Frame(), osm_ways=tuple(ways))


@pytest.fixture
def deck(monkeypatch):
    piece = _Piece(box(0, -20, 200, 20))
    monkeypatch.setattr(PP, "partition_prints", lambda _part: [piece])
    monkeypatch.setattr(BF, "deck_components", lambda p: [p])
    return piece


def test_the_untagged_twin_of_a_lower_road_under_a_deck_is_carried(deck):
    """SBSP: ``-8899`` (no level tag) runs 0.5 m from ``-8134`` (layer -1,
    covered) under the departures deck — the deck's kerb road over the
    arrivals road.  The untagged one is carried over its run in the deck."""
    up = _way(-8899, [(-50, 0.5), (250, 0.5)])
    down = _way(-8134, [(20, 0), (180, 0)], layer="-1", covered="yes")
    counts: dict = {}
    got = CR.carried_runs(_airport([up, down]), LAW, counts)
    assert set(got) == {("airport_small_roads", -8899)}
    (a, b), = got[("airport_small_roads", -8899)]
    hw = ribbon_half_width_m(up.tags, LAW)
    assert a == pytest.approx(50.0 - hw, abs=1.5) and b == pytest.approx(250.0 + hw, abs=1.5)
    assert counts["carried_roads"] == 1


def test_no_witness_no_carry(deck):
    """Both twins untagged: nothing says which is the deck's; a lone road;
    a twin too short (a crossing); a lower road a lane away."""
    up = _way(1, [(-50, 0.5), (250, 0.5)])
    assert CR.carried_runs(_airport([up, _way(2, [(20, 0), (180, 0)])]), LAW) == {}
    assert CR.carried_runs(_airport([up]), LAW) == {}
    short = _way(3, [(20, 0), (30, 0)], layer="-1")
    assert CR.carried_runs(_airport([up, short]), LAW) == {}
    apart = _way(4, [(20, -4), (180, -4)], layer="-1")
    assert CR.carried_runs(_airport([up, apart]), LAW) == {}


def test_no_deck_no_carry(monkeypatch):
    monkeypatch.setattr(PP, "partition_prints", lambda _part: [])
    up = _way(-8899, [(-50, 0.5), (250, 0.5)])
    down = _way(-8134, [(20, 0), (180, 0)], layer="-1")
    assert CR.carried_runs(_airport([up, down]), LAW) == {}


def test_level_tags():
    assert not CR.is_level_tagged({"highway": "service"})
    assert not CR.is_level_tagged({"highway": "service", "layer": "0", "bridge": "no"})
    assert CR.is_level_tagged({"highway": "service", "covered": "yes"})
    assert CR.is_tagged_lower({"layer": "-1"})
    assert CR.is_tagged_lower({"tunnel": "building_passage"})
    assert not CR.is_tagged_lower({"layer": "1"})


def test_a_kerb_road_in_and_out_of_the_print_by_a_metre_is_carried_whole(deck):
    """SBSP: -8899 runs along the deck's outer edge, 0-1.7 m outside its
    print for 30-60 m at a time; within its own half-width it is on the
    deck, so its run is ONE run, not three with ground remnants between."""
    up = _way(-8899, [(0, 19.0), (60, 21.5), (120, 19.0), (200, 19.0)])
    down = _way(-8134, [(0, 18.5), (60, 21.0), (120, 18.5), (200, 18.5)], layer="-1")
    got = CR.carried_runs(_airport([up, down]), LAW)
    assert len(got[("airport_small_roads", -8899)]) == 1


def _routes_over(monkeypatch, runs):
    from auto_patch_v2.planar import cut_runout as CRO
    monkeypatch.setattr(CR, "carried_runs", lambda _a, _l, counts=None: runs)
    level = box(0, -10, 100, 10)
    way = _way(-8899, [(50, 0), (200, 0)])
    return CRO._routes(_airport([way]), LAW, [level], 0.5)


def test_a_way_carried_where_it_crosses_the_level_edge_is_no_route(monkeypatch):
    """#1905 round 3 (R4): the deck's own road leaves the lower level where
    the deck carries it -- it runs out nowhere; carried elsewhere only, it
    is a route."""
    assert len(_routes_over(monkeypatch, {})) == 1
    assert _routes_over(monkeypatch, {("airport_small_roads", -8899): [(30.0, 80.0)]}) == []
    assert len(_routes_over(monkeypatch, {("airport_small_roads", -8899): [(90.0, 140.0)]})) == 1
