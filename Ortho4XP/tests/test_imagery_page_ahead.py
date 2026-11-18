"""Twins of the imagery page-ahead (#2109): ``O4_Imagery_Page_Ahead``,
``o4_engine.imagery_follow_ahead``, the follow job's use of them, the
cross-tile airport cores (``O4_Imagery_OnDemand_Cores.airport_points``
with ``neighbours``) and
``tools/imagery_page_ahead_replay.py``.

The claim: the squares of a tile that will ENTER X-Plane's DSF window
along the path are fetched at the tier the path wants there, each by the
tile's entry less rule S3's margin, in a schedule one fetcher can keep;
a tile already held is left to the step-up planner.  Synthetic squares on
a westbound track at 37.5 N (the 2026-11-16 KMMH departure's latitude);
no network, no sim.
"""
from __future__ import annotations

import math
import os
import sys

import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Page_Ahead as PAGE
import O4_Imagery_Tier_Plan as PLAN
import O4_World_Ahead as AHEAD
import O4_World_Window as WINDOW
import O4_XPlane_WebAPI as WEBAPI
import test_imagery_follow as P3B
from o4_engine import imagery_follow as FOLLOW
from o4_engine.imagery_follow_ahead import PageAhead, merge

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
import imagery_page_ahead_replay as REPLAY  # noqa: E402

xplane = P3B.xplane                         # the fake X-Plane, a fixture

LAT = 37.5
S = 7_750.0                                 # a ZL16 square's S at 37.5 N
V = 130.0                                   # m/s, the fitted climb-out
_M_PER_DEG = 111_320.0


def _lon_step(metres: float) -> float:
    return metres / (_M_PER_DEG * math.cos(math.radians(LAT)))


def _motion(lon: float, gs: float = V, track: float = 270.0) -> PLAN.Motion:
    return PLAN.Motion(LAT, lon, 3000.0, track, gs, 2000.0)


def _sq(name, lat, lon, size=S) -> PLAN.Square:
    return PLAN.Square(name, lat, lon, size)


def _window(lat: float, lon: float) -> WINDOW.WindowTracker:
    tracker = WINDOW.WindowTracker()
    tracker.load(lat, lon)
    return tracker


# --- the pure planner ------------------------------------------------------


def test_the_tier_follows_the_distance_from_the_path_in_units_of_s():
    path = PAGE.straight_path(_motion(-120.0), 600.0)
    off = lambda metres: LAT - metres / _M_PER_DEG     # noqa: E731
    lon = -120.3
    assert PAGE.target_tier(path, _sq("a", LAT, lon)) == 3
    assert PAGE.target_tier(path, _sq("b", off(2.0 * S), lon)) == 3   # 1.65+0.5
    assert PAGE.target_tier(path, _sq("c", off(3.0 * S), lon)) == 2
    assert PAGE.target_tier(path, _sq("d", off(5.0 * S), lon)) == 1
    assert PAGE.target_tier(path, _sq("e", off(6.0 * S), lon)) == 0
    behind = _sq("f", LAT, -119.3)                   # 62 km behind
    assert PAGE.target_tier(path, behind) == 0


def test_a_route_is_flown_from_the_aircraft_s_nearest_point_on_it():
    route = [(LAT, -119.0), (LAT, -120.0), (LAT + 1.0, -120.0)]
    m = _motion(-119.5)
    path = PAGE.route_path(route, m, math.inf)
    assert path[0][1:] == (LAT, -119.5)
    assert abs(path[-1][1] - (LAT + 1.0)) < 1e-9 and path[-1][2] == -120.0
    leg = 0.5 * _M_PER_DEG * math.cos(math.radians(LAT)) + _M_PER_DEG
    assert abs(path[-1][0] - leg / V) < 2.0
    times = [p[0] for p in path]
    assert times == sorted(times)
    # no route, or parked: the straight track
    assert PAGE.route_path([], m, 60.0) == PAGE.straight_path(m, 60.0)


def test_only_the_tiles_that_enter_are_planned_and_by_their_entry():
    lon0 = -119.55                          # B = -120: columns -122..-119
    window = _window(LAT, lon0)
    m = _motion(lon0)
    path = PAGE.straight_path(m, PAGE.PAGE_HORIZON_S)
    judged = PAGE.straight_path(m, PAGE.PAGE_HORIZON_S + PAGE.PASS_S)
    entries = PAGE.entries(window, path)
    # the window moves at B - 0.65 = -120.65: column -123 enters
    assert {t for t in entries} == {(36, -123), (37, -123), (38, -123)}
    entry = entries[(37, -123)]
    flown = 1.1 * _M_PER_DEG * math.cos(math.radians(LAT))   # to -120.65
    assert flown / V <= entry <= flown / V + AHEAD.STEP_S
    on_track = [_sq(f"+37-123/{i}", LAT, -122.1 - 0.15 * i) for i in range(5)]
    beside = _sq("+37-123/far", LAT - 0.5, -122.5)        # 7 S off: none
    held = _sq("+37-121/held", LAT, -120.9)                # in the window
    tiles = {(37, -123): on_track + [beside], (37, -121): [held]}
    plan = PAGE.plan_ahead([judged[0], judged[-1]], entries, tiles,
                           {on_track[0].name: 3}, V)
    names = [f.square for f in plan]
    assert names and set(names) == {s.name for s in on_track[1:]}
    deadline = AHEAD.deadline_s(entry, V)
    for f in plan:
        assert f.tier == 3 and f.crossing == PAGE.PAGE_CROSSING
        assert f.deadline_s == deadline and not f.late


def test_the_schedule_lands_a_column_one_at_a_time_by_its_entry():
    fetch_s = {1: 0.4, 2: 1.05, 3: 2.86}
    squares = [_sq(f"+37-123/{i}", LAT - 0.02 * (i % 7), -122.05 - 0.01 * i)
               for i in range(60)]
    path = PAGE.straight_path(_motion(-119.55),
                              PAGE.PAGE_HORIZON_S + PAGE.PASS_S)
    plan = PAGE.plan_ahead([path[0], path[-1]],
                           {(37, -123): 300.0}, {(37, -123): squares}, {}, V,
                           fetch_s=fetch_s, lead_s=30.0)
    assert len(plan) == 60
    # run them one at a time at their start times: each lands in time
    t = -math.inf
    for f in sorted(plan, key=lambda f: f.start_in_s):
        t = max(t, f.start_in_s + 30.0) + fetch_s[f.tier]
        assert t <= f.deadline_s + 1e-6
    assert plan == sorted(plan, key=lambda f: (f.deadline_s, f.tier, f.square))


# --- the follow job's page-ahead ---------------------------------------------


def test_a_flight_load_loads_the_window_and_a_first_position_keeps_all():
    ahead = PageAhead(route=lambda: None)
    ahead.locate("flight_load", LAT, -118.84)
    assert ahead.describe() == "-119,37"         # B = round(lon), R = floor
    ahead.locate("spawn", LAT, -119.55)
    assert ahead.describe() == "?"               # both -120 and -119 plausible
    assert ahead.window.cols == {-120, -119}


def test_merge_keeps_the_planner_s_squares_and_its_late_ones_last():
    a = PLAN.Fetch("a", 1, 1, 50.0, 20.0, 1.0, False)
    late = PLAN.Fetch("z", 1, 1, -5.0, -35.0, 1.0, True)
    mine = PLAN.Fetch("a", 3, 0, 10.0, -20.0, 1.0, False)
    b = PLAN.Fetch("b", 3, 0, 30.0, -5.0, 1.0, False)
    assert merge([a, late], [mine, b]) == [b, a, late]
    assert merge([a], []) == [a]


def _seed(tmp_path, squares):
    """Index rows for ``(tile, name, lat, lon)``, each a whole tiny DDS."""
    build = tmp_path / "build"
    (build / "textures").mkdir(parents=True)
    path = tmp_path / "index.sqlite"
    conn = INDEX.open_index(str(path))
    for tile, name, lat, lon in squares:
        P3B._whole_dds(build / "textures" / name, 0)
        INDEX.upsert(conn, {"tile": tile, "name": name, "zl": 16,
                            "provider": "Arc", "build_dir": str(build),
                            "centre_lat": lat, "centre_lon": lon,
                            "load_size_m": S, "state": "low",
                            "tier_px": PLAN.TIER_WIDTH[0]})
    conn.close()
    return str(path)


def test_the_job_plans_the_entering_tile_and_logs_its_track(xplane, tmp_path):
    on_track = [("+37-123", f"t{i}.dds", LAT, -122.1 - 0.2 * i)
                for i in range(4)]
    beside = [("+37-123", "far.dds", LAT - 0.6, -122.5)]
    held = [("+37-121", "held.dds", LAT + 0.4, -120.9)]
    index_path = _seed(tmp_path, on_track + beside + held)
    clock, events = P3B.Clock(), []
    job = FOLLOW.FollowJob(
        events.append, reader=WEBAPI.PositionReader(xplane.base),
        lander=P3B.FakeLander(), index_path=index_path, clock=clock,
        log_path=str(tmp_path / "od.log"),
        page_ahead=PageAhead(route=lambda: None))
    job.open()
    lon = -119.55
    for t in range(12):
        clock.t = 1000.0 + t
        xplane.values.update(lat=LAT, lon=lon - _lon_step(V * t), elev_m=3000.0,
                             gs_ms=V)
        job.tick()
        P3B._settle(job)
    ahead = {f.square: f for f in job.last_plan
             if f.crossing == PAGE.PAGE_CROSSING}
    assert set(ahead) == {f"+37-123/{n}" for _t, n, *_ in on_track}
    assert all(f.tier == 3 and f.deadline_s > 600.0 for f in ahead.values())
    assert not any(f.square in ahead for f in job.last_dispatched)  # not due
    with open(tmp_path / "od.log", encoding="utf-8") as handle:
        log = handle.read()
    assert "pos=37.50000,-119.5" in log and "window=" in log
    job.close()


# --- the airport cores cross tile edges --------------------------------------


def test_an_airport_on_the_neighbour_keeps_its_ring_on_this_tile(monkeypatch):
    kmmh = ("KMMH", 37.6240, -118.8378)                 # on +37-119
    monkeypatch.setattr(CORES, "_tile_points", lambda la, lo, *_a: (
        [kmmh] if (la, lo) == (37, -119) else []))
    ring = CORES.airport_points(37, -120, neighbours=True)
    assert ring == [kmmh]
    assert CORES.airport_points(37, -120) == []             # the tile alone
    assert CORES.airport_points(37, -122, neighbours=True) == []
    near = {"centre_lat": 37.62, "centre_lon": -119.05, "load_size_m": S}
    assert CORES.core_tier(near, ring) == 2                 # 19 km


# --- the replay tool ----------------------------------------------------------


def _squares_along(lat, lons, tile):
    return {tile: [_sq(f"{tile}/{i}", lat, lon) for i, lon in enumerate(lons)]}


def test_the_replay_lands_every_entering_square_before_its_entry():
    track = [(float(t), LAT, -119.55 - _lon_step(V * t)) for t in range(2400)]
    squares = _squares_along(LAT, [-122.05 - 0.1 * i for i in range(8)],
                             (37, -123))
    sim = REPLAY.simulate(track, squares, {}, REPLAY.FETCH_S["p90"][1], slots=1)
    assert len(sim["paged"]) >= 4 and not sim["short"]
    slow = {k: 400.0 for k in (1, 2, 3)}                # a dead network
    late = REPLAY.simulate(track, squares, {}, slow, slots=1)
    assert late["short"]


def test_the_replay_reports_the_first_window_s_stale_squares():
    track = [(float(t), LAT, -119.55 - _lon_step(V * t)) for t in range(300)]
    squares = _squares_along(LAT, [-119.7, -119.8], (37, -120))
    sim = REPLAY.simulate(track, squares, {"(37, -120)/1": 3},
                          REPLAY.FETCH_S["median"][1])
    stale = {s["square"] for s in sim["first_window_stale"]}
    assert stale == {"(37, -120)/0"}
