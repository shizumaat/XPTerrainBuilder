"""#2128 round 4 (owner RULINGS 2026-11-17d, spec ``sim-review/2128-R2b.md``
B2, R2 spec R4): A ROAD TAKES A LEVEL ONLY ALONG ITS DIRECTION OF TRAVEL.

Two roads whose centrelines cross one over the other
(``planar/grade_separation``, published as ``PlanarMap.road_crossings``)
are not joined in the road ramp's graph and lend each other no level
(``airport/road_ramp``); a T-junction and an untagged crossing stay
joined.  Inside the surveyed cut beside a kept hard deck
(``PlanarMap.survey_cuts``) no road-ramp seed or target applies.
MEASURED KIAH: an apt.dat 1206 route over a mapped service bridge was
joined to the primary road in the cut under it, whose envelope carried
the route's 25.36 m down to 24.21 m at the owner's spot (DEM 21.37)."""
from __future__ import annotations

import dataclasses as _dc

import pytest
from auto_patch_v2.airport import road_ramp as rr
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.grade_separation import (
    RoadCrossing,
    crossing_vertices,
    far_keys,
    other_side,
    road_key,
)
from auto_patch_v2.planar.build import build
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot
from tests.auto_patch_v2.test_v2roadramp import PLATEAU_Z, RUN_LEN, _airport

LOW = PLATEAU_Z - 12.0
W = 8.0


class _Shelf:
    """The apron's shelf, a 30 % bank from local x 40 to 80, then flat 12 m
    lower (``_rot(0)`` lays local x on the frame's y)."""
    provenance = {"synthetic": "shelf + bank"}

    def z(self, x, y):
        return max(LOW, PLATEAU_Z - 0.3 * max(0.0, y - 40.0))

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _arm(law, a_tags, b_y=(100.0, 300.0)):
    """Road A (way -1) leaves the apron's edge (local x -20) east along
    y 200 down the bank; road B (way -2) runs along x 100 over ``b_y``."""
    r = _rot(0.0)
    airport, _r = _airport(law, _Shelf())
    ways = (OsmWay(-1, "airport_small_roads", (r((-20.0, 200.0)), r((280.0, 200.0))), False,
                   {"highway": "service", **a_tags}),
            OsmWay(-2, "airport_small_roads", (r((100.0, b_y[0])), r((100.0, b_y[1]))), False,
                   {"highway": "service"}))
    airport = _dc.replace(airport, osm_ways=ways)
    cells = (Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                              HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
             Cell(1, "apron", "apronA", _rect(r, -220.0, 150.0, -20.0, 250.0), (),
                  None, "D", "airside", "apron", {}),
             Cell(2, "service_road", "small_roads:-1", _rect(r, -20.0, 200.0 - W / 2,
                                                             280.0, 200.0 + W / 2), (),
                  None, "D", "groundside", "service_road", {}),
             Cell(3, "service_road", "small_roads:-2", _rect(r, 100.0 - W / 2, b_y[0],
                                                             100.0 + W / 2, b_y[1]), (),
                  None, "D", "groundside", "service_road", {}))
    pm, _st = build(airport, Classification(cells, (), {}, ()), law)
    return airport, pm


def _local(pm, v):
    """Local (x, y) of vertex ``v`` (``_rot(0)``: frame (-y, x))."""
    fx, fy = pm.vertices[v].xy
    return fy, -fx


def _b_lift(pm, tg) -> float:
    """The most road B's targets stand over its ground, clear of A's own
    faces (local y >= 212)."""
    out = 0.0
    for f in pm.faces.values():
        if f.ref != "small_roads:-2":
            continue
        for v in pm.ring_vertices(f.ring):
            if v in tg and _local(pm, v)[1] >= 212.0:
                out = max(out, tg[v] - LOW)
    return out


def test_road_key_reads_the_centreline_a_profile_way_stands_on():
    assert road_key("osm:-5106") == "osm:-5106"
    assert road_key("route4#17") == "route4"


def test_a_bridge_over_a_road_is_published_and_lends_it_no_level(law):
    airport, pm = _arm(law, {"bridge": "yes", "layer": "1"})
    (c,) = pm.road_crossings
    assert {c.a, c.b} == {"osm:-1", "osm:-2"} and "mapped levels" in c.witness
    assert c.a_vertices and c.b_vertices and c.vertices
    got = rr.road_ramp_targets(pm, law, airport)
    joined = rr.road_ramp_targets(_dc.replace(pm, road_crossings=()), law, airport)
    assert _b_lift(pm, joined.targets) > 1.0           # the control: lifted across
    assert _b_lift(pm, got.targets) < 0.05             # separated: B keeps its floor
    assert got.report["grade_separated_crossings"] == 1


def test_an_untagged_crossing_stays_joined(law):
    _ap, pm = _arm(law, {})
    assert pm.road_crossings == ()


def test_a_t_junction_under_a_bridge_tag_stays_joined(law):
    """B ends on A's centreline: no crossing, whatever A's tags."""
    _ap, pm = _arm(law, {"bridge": "yes"}, b_y=(200.0, 300.0))
    assert pm.road_crossings == ()


def test_no_seed_or_target_inside_the_surveyed_cut(law):
    """C over the mouth and the bank: no target there and no ramp beyond."""
    airport, pm = _arm(law, {})
    r = _rot(0.0)
    ring = _rect(r, -25.0, 150.0, 90.0, 250.0)
    base = rr.road_ramp_targets(pm, law, airport)
    got = rr.road_ramp_targets(_dc.replace(pm, survey_cuts=((ring, ()),)), law, airport)
    assert got.report["survey_cut_vertices"] > 0
    assert got.report["mouths"] < base.report["mouths"]
    inside = [v for v in base.targets if -25.0 <= _local(pm, v)[0] <= 90.0]
    assert inside and not any(v in got.targets for v in inside)
    assert max(z - pm.vertices[v].dem_z for v, z in got.targets.items()) < \
        max(z - pm.vertices[v].dem_z for v, z in base.targets.items()) - 1.0


def test_crossing_record_sides():
    c = RoadCrossing("osm:-1", "route4", (1.0, 2.0), "mapped levels 1 / 0",
                     frozenset({1, 3}), frozenset({2, 3}))
    assert crossing_vertices([c]) == frozenset({3})
    assert far_keys([c]) == {1: frozenset({"route4"}), 2: frozenset({"osm:-1"})}
    assert other_side([c]) == {"osm:-1": frozenset({2, 3}), "route4": frozenset({1, 3})}


def test_a_route_takes_the_level_of_the_mapped_bridge_it_duplicates(law):
    """An apt.dat route states no tag: it takes the level of a bridge way
    running ALONG it within the dedup distance; a bridge way crossing it
    (another road over the junction) lends it nothing."""
    from auto_patch_v2.planar.grade_separation import _twin_level
    from shapely.geometry import LineString, Point
    route = LineString([(0.0, 0.0), (100.0, 0.0)])
    along = OsmWay(-7, "small_roads", ((10.0, 4.0), (90.0, 4.0)), False,
                   {"highway": "service", "bridge": "yes", "layer": "1"})
    across = OsmWay(-8, "small_roads", ((50.0, -40.0), (50.0, 40.0)), False,
                    {"highway": "service", "bridge": "yes"})
    p = Point(50.0, 0.0)
    assert _twin_level(route, p, [(along, LineString(along.points))], 8.0, law) == 1
    assert _twin_level(route, p, [(across, LineString(across.points))], 8.0, law) == 0
    assert _twin_level(route, p, [(along, LineString(along.points))], 3.0, law) == 0


def test_a_ribbon_is_its_own_feeds_way_only():
    """Two OSM feeds reuse way ids (MEASURED ESSA: 405 shared ids, -260 a
    taxiway, a service bridge and a railway): a face is a road's by its
    feed-qualified ref, or as that way's bridge deck."""
    from auto_patch_v2.planar.grade_separation import _is_named, _ref_key
    assert _ref_key("big_roads:-3078#1") == ("big_roads", -3078)
    assert _ref_key("dsf:pol200") is None and _ref_key("route52") is None
    assert _is_named(("small_roads", -260), "small_roads:-260")
    assert not _is_named(("big_roads", -260), "small_roads:-260")
    assert _is_named(("bridge_deck", -260), "airport_small_roads:-260")
