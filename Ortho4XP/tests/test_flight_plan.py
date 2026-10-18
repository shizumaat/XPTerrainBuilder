"""Twin of ``Tests/SceneryKitTests/FlightPlanTests.swift`` (#829).

Both read ``fixtures/flight_plan_cases.json`` and the plan files in
``fixtures/flight_plan/``: each format parses to the same waypoints, the
same route selects the same tiles, and the dialog copy is the same, so
the Mac and Qt "Select from flight plan" agree.  The properties below
(radius monotonicity, endpoints, great-circle bending, antimeridian) are
asserted here on the one implementation the fixture freezes.  No network:
SimBrief is a committed fetcher answer.
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Flight_Plan as FP  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
PLANS = os.path.join(FIXTURES, "flight_plan")
with open(os.path.join(FIXTURES, "flight_plan_cases.json"), encoding="utf-8") as _fh:
    CASES = json.load(_fh)


@pytest.mark.parametrize("case", CASES["plans"], ids=lambda c: c["file"])
def test_each_format_parses_its_fixture(case):
    plan = FP.read_plan_file(os.path.join(PLANS, case["file"]))
    assert [[w.ident, w.lat, w.lon] for w in plan.waypoints] == case["waypoints"]
    assert (plan.origin, plan.destination) == (case["origin"], case["destination"])
    assert FP.summary_text(plan, "km") == case["summary_km"]
    assert FP.summary_text(plan, "nm") == case["summary_nm"]


def test_the_format_is_sniffed_when_the_name_has_no_extension():
    for case in CASES["plans"]:
        with open(os.path.join(PLANS, case["file"]), encoding="utf-8", newline=None) as fh:
            plan = FP.parse_plan_text(fh.read(), "")
        assert [[w.ident, w.lat, w.lon] for w in plan.waypoints] == case["waypoints"]


@pytest.mark.parametrize("case", CASES["errors"], ids=lambda c: c["name"])
def test_an_unreadable_plan_says_why(case):
    with pytest.raises(FP.FlightPlanError) as exc:
        FP.parse_plan_text(case["text"], case["name"])
    assert str(exc.value) == case["message"]


@pytest.mark.parametrize("case", CASES["simbrief_urls"], ids=lambda c: c["user"])
def test_simbrief_url_by_pilot_id_or_username(case):
    assert FP.simbrief_url(case["user"]) == case["url"]


def test_simbrief_needs_a_user():
    with pytest.raises(FP.FlightPlanError):
        FP.simbrief_url("  ")


def test_units_and_words():
    for case in CASES["units"]:
        assert FP.radius_km(case["value"], case["unit"]) == pytest.approx(case["km"])
    for case in CASES["tiles_text"]:
        assert FP.tiles_text(case["count"]) == case["text"]
    copy = CASES["copy"]
    assert (FP.MENU_TITLE, FP.OPEN_BUTTON, FP.SIMBRIEF_PLACEHOLDER, FP.SIMBRIEF_BUTTON,
            FP.SIMBRIEF_NOTE, FP.RADIUS_LABEL, FP.OF_ROUTE_LABEL) == (
        copy["menu_title"], copy["open_button"], copy["simbrief_placeholder"],
        copy["simbrief_button"], copy["simbrief_note"], copy["radius_label"],
        copy["of_route_label"])
    assert FP.RADIUS_MAX == CASES["radius_max"]
    assert FP.RADIUS_DEFAULT == CASES["radius_default"]


@pytest.mark.parametrize("case", CASES["routes"],
                         ids=lambda c: "%s r%s" % (c["name"], c["radius_km"]))
def test_route_tiles_on_known_routes(case):
    points = [tuple(p) for p in case["points"]]
    assert [list(t) for t in FP.route_tiles(points, case["radius_km"])] == case["tiles"]


@pytest.mark.parametrize("case", CASES["drawing"])
def test_route_drawing(case):
    parts = FP.route_drawing([tuple(p) for p in case["points"]])
    assert len(parts) == len(case["parts"])
    for got, want in zip(parts, case["parts"]):
        assert len(got) == len(want)
        for p, q in zip(got, want):
            assert list(p) == pytest.approx(q)


# --- properties --------------------------------------------------------------
def _plan_points(name):
    return FP.read_plan_file(os.path.join(PLANS, name)).points()


@pytest.mark.parametrize("name", [c["file"] for c in CASES["plans"]])
def test_a_larger_radius_never_drops_a_tile(name):
    points = _plan_points(name)
    previous = set()
    for radius in (0, 10, 25, 50, 100, 200, 300):
        tiles = set(FP.route_tiles(points, radius))
        assert previous <= tiles, radius
        previous = tiles


@pytest.mark.parametrize("name", [c["file"] for c in CASES["plans"]])
def test_departure_and_arrival_tiles_are_always_selected(name):
    points = _plan_points(name)
    tiles = set(FP.route_tiles(points, 0))
    for lat, lon in (points[0], points[-1]):
        assert (math.floor(lat), math.floor(lon)) in tiles


def test_a_long_leg_follows_the_great_circle_not_the_straight_line():
    # New York -> London: the great circle bends north of the straight
    # lat/lon line by several degrees mid-Atlantic.
    jfk, lhr = (40.64, -73.78), (51.48, -0.46)
    tiles = set(FP.route_tiles([jfk, lhr], 0))
    mid_lat, mid_lon = FP.densify([jfk, lhr], step_km=3000.0)[1]  # the middle
    assert mid_lat > 51.5  # the great circle's vertex, north of both ends
    assert (math.floor(mid_lat), math.floor(mid_lon)) in tiles
    straight_mid = (math.floor((jfk[0] + lhr[0]) / 2), math.floor((jfk[1] + lhr[1]) / 2))
    assert straight_mid not in tiles


def test_a_long_leg_skips_no_tile():
    # At radius 0 the selected tiles form one 8-connected chain.
    tiles = set(FP.route_tiles([(40.64, -73.78), (51.48, -0.46)], 0))
    start = next(iter(tiles))
    seen, todo = {start}, [start]
    while todo:
        lat, lon = todo.pop()
        for dl in (-1, 0, 1):
            for dn in (-1, 0, 1):
                n = (lat + dl, ((lon + dn + 180) % 360) - 180)
                if n in tiles and n not in seen:
                    seen.add(n)
                    todo.append(n)
    assert seen == tiles


def test_the_antimeridian_selects_both_sides_and_wraps():
    tiles = set(FP.route_tiles([(45.0, 170.0), (50.0, -170.0)], 0))
    assert any(lon == 179 for _, lon in tiles)
    assert any(lon == -180 for _, lon in tiles)
    assert all(-180 <= lon <= 179 for _, lon in tiles)
    assert not any(-160 < lon < 160 for _, lon in tiles)  # never the long way round
    parts = FP.route_drawing([(45.0, 170.0), (50.0, -170.0)])
    assert len(parts) == 2
    assert parts[0][-1][1] == 180.0 and parts[1][0][1] == -180.0


def test_a_polar_leg_goes_over_the_top():
    tiles = set(FP.route_tiles([(60.19, 11.10), (64.82, -147.86)], 0))
    assert max(lat for lat, _ in tiles) >= 80


def test_a_radius_reaches_the_neighbouring_tiles():
    # A point mid-tile with 50 km: the 1x1 tile is ~111 x 75 km at 47N,
    # so 50 km from its centre reaches the east and west neighbours only.
    tiles = set(FP.route_tiles([(47.5, -122.5)], 50))
    assert tiles == {(47, -123), (47, -122), (47, -124)}
