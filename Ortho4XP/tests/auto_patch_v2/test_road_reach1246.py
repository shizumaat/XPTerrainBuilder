"""#1246 — THE ROAD REACH IS THE AERODROME BOUNDARY + 50 M (owner RULINGS
2026-10-22g, superseding 30e (2)'s extent).

Every mapped at-grade road inside the apt.dat 130 boundary, and within
``osm_roads.boundary_reach_m`` outside it, is ribboned (and so graded by
the road law); a road leaving that reach runs out to its own ground (the
road-exit law, 29y), never to the level of an airside far away; an airport
with no boundary keeps the pavement + zone-2 envelope.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch_v2.classify import classify, load_rules
from auto_patch_v2.classify.ribbon_mint import exit_reach
from auto_patch_v2.classify.roles import is_osm_ribbon
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Boundary, OsmWay

from test_classify import _rect, _synthetic

#: the synthetic's boundary: the field and 500 m round the runway's axis
BOUNDARY = Boundary("b", tuple(_rect(-200.0, -500.0, 1300.0, 700.0)), ())


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _way(wid, pts, **tags):
    return OsmWay(wid, "airport_small_roads", tuple(pts), False, dict(tags))


def _ribbons(cl):
    return [c for c in cl.cells if is_osm_ribbon(c)]


def _with(*ways, boundary=True):
    a = _synthetic(gate=True, island=False)
    return _dc.replace(a, osm_ways=tuple(ways),
                       boundaries=(BOUNDARY,) if boundary else ())


def test_the_reach_key_is_fifty_metres():
    assert load_rules().osm_roads.boundary_reach_m == 50.0


def test_a_road_inside_the_boundary_far_from_airside_is_ribboned(law):
    # 300 m south of the runway: outside every zone-2 envelope, inside 130
    road = _way(-3, ((200.0, -300.0), (800.0, -300.0)), highway="tertiary")
    assert [c.ref for c in _ribbons(classify(_with(road), law))] == ["small_roads:-3"]
    # the same road with no boundary: the 30e (2) envelope alone, nothing
    assert _ribbons(classify(_with(road, boundary=False), law)) == []


def test_a_road_within_fifty_metres_outside_is_ribboned_and_beyond_is_not(law):
    near = _way(-4, ((200.0, -540.0), (800.0, -540.0)), highway="service")
    far = _way(-5, ((200.0, -570.0), (800.0, -570.0)), highway="service")
    refs = [c.ref for c in _ribbons(classify(_with(near, far), law))]
    assert refs == ["small_roads:-4"]


def test_a_road_leaving_the_reach_runs_out_one_station_on_flat_ground(law):
    # straight out of the boundary across its south edge (y = -500): the
    # reach ends at y = -550; on flat ground the exit law adds one station
    # past the first station met, so the last ring vertex stands on the DEM
    road = _way(-6, ((500.0, -300.0), (500.0, -900.0)), highway="tertiary")
    rib = _ribbons(classify(_with(road), law))
    assert [c.ref for c in rib] == ["small_roads:-6"]
    ymin = min(y for _x, y in rib[0].ring)
    station = float(law.tables.emit.road_profile.lane_width_m)
    assert ymin == pytest.approx(-550.0 - 2.0 * station, abs=0.5)


class _Slope:
    """A DEM that rises away from an airside: 100 m at the airside, the
    mouth's own ground 10 m higher."""

    def z(self, x: float, y: float) -> float:
        return 100.0 if x < 100.0 else 110.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def test_a_mouth_far_from_the_airside_leaves_at_its_own_ground():
    line = LineString([(500.0, 0.0), (1500.0, 0.0)])
    airside = Polygon(_rect(0.0, -15.0, 90.0, 15.0))
    near = Polygon(_rect(0.0, -40.0, 130.0, 40.0))       # the zone envelope
    # the mouth at x = 900 is 770 m from the envelope: the level is the
    # mouth's own ground, which the terrain beyond meets at the first station
    a, b = exit_reach(line, 0.0, 400.0, _Slope(), airside, 0.08, 2.0, 8.0, near=near)
    assert b == pytest.approx(404.0, abs=1e-6)
    # without ``near`` (30e (2)'s reading) the airside's 100 m is the mouth's
    # level, and the ribbon runs on 10 m / 8 % past it
    _a, b_old = exit_reach(line, 0.0, 400.0, _Slope(), airside, 0.08, 2.0, 8.0)
    assert b_old >= 400.0 + 10.0 / 0.08
