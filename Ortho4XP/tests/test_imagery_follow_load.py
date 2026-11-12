"""The follow job across X-Plane's start and flight loads (#2028).

On 1.0.501 the job's first position was read while X-Plane was still
loading a flight at its departure: the camera came out 5,800 km away,
the spawn episode opened there, and the load itself was never seen (the
Web API answered all through it, so no id reset; its first position at
the departure came more than 5 s after the bad one, so no jump).  The
episode's core held every fetch slot for minutes while the departure
stayed at its 512 px placeholders.

The twins replay that sequence on the fake X-Plane of
``test_imagery_follow`` and flight 1's squares of ``test_imagery_spawn``:

* no position is trusted until X-Plane's clock runs
  (``O4_XPlane_WebAPI.PositionReader``): the start's samples open no
  episode, the first running one does, at the right place;
* a load X-Plane answers through (its clock stops, then runs again) is a
  flight load;
* a move no aircraft flies is a jump however long the gap before it;
* a camera farther from the aircraft than any view puts it is the
  aircraft's position.
"""
from __future__ import annotations

import O4_XPlane_WebAPI as WEBAPI
import pytest
import test_imagery_follow as P3B
from o4_engine import imagery_follow as FOLLOW
from O4_Imagery_Follow_Motion import MotionTracker
from test_imagery_spawn import ELSEWHERE, FIELD, Flight, _core

xplane = P3B.xplane                         # the fake X-Plane, a fixture

CLOCK_REF = "sim/time/total_running_time_sec"


@pytest.fixture()
def clocked(xplane, monkeypatch):
    """The fake X-Plane with its clock published (``sim_time_s``)."""
    monkeypatch.setitem(P3B._OFFERED, CLOCK_REF, "sim_time_s")
    xplane.values["sim_time_s"] = 0.0
    return xplane


def _log(tmp_path) -> str:
    return (tmp_path / "od.log").read_text(encoding="utf-8")


# --- the reader --------------------------------------------------------------


def test_no_position_is_trusted_until_the_clock_runs(clocked):
    reader = WEBAPI.PositionReader(clocked.base)
    clocked.values.update(lat=60.5, lon=-135.5)
    assert reader.read() is None and reader.loading      # first: unknown
    assert reader.error == WEBAPI.LOADING
    assert reader.read() is None                          # frozen: loading
    clocked.values["sim_time_s"] = 1.0
    assert reader.read()["lat"] == 60.5 and not reader.loading
    assert reader.resets == 0                             # no flight before
    clocked.values["paused"] = 1                          # paused: trusted
    assert reader.read() is not None
    clocked.values["paused"] = 0                          # frozen, unpaused
    assert reader.read() is None and reader.loading
    clocked.values["sim_time_s"] = 0.5                    # a new flight's clock
    assert reader.read() is None
    clocked.values["sim_time_s"] = 1.5
    assert reader.read() is not None and reader.resets == 1


def test_the_recorder_reads_every_record(clocked):
    reader = WEBAPI.PositionReader(clocked.base, settled_only=False)
    assert reader.read() is not None and reader.read() is not None


def test_a_camera_further_than_any_view_is_the_aircraft():
    """#2028: 5,800 km between camera and aircraft is two local frames."""
    rec = {"lat": 42.37, "lon": -122.87, "local_x": -3.97e6,
           "local_z": -4.26e6, "view_x": 0.0, "view_z": 0.0}
    assert WEBAPI.camera_position(rec) == (42.37, -122.87)


def test_a_move_no_aircraft_flies_is_a_jump_after_any_gap():
    tracker = MotionTracker(square_m=4744.0)
    tracker.add(0.0, 4.1, -74.6)
    tracker.add(30.0, 42.37, -122.87)               # 5,800 km, 30 s later
    assert tracker.jumps == 1 and tracker.jumped
    tracker.add(630.0, 42.40, -122.87)              # 3 km in 10 min: flying
    tracker.add(4230.0, 43.0, -122.87)              # 67 km in an hour
    assert tracker.jumps == 1


# --- the job -----------------------------------------------------------------


def test_a_start_read_while_x_plane_loads_opens_no_episode(clocked, tmp_path):
    """The #2028 sequence: X-Plane starting reports a place with squares
    (the field) and a frozen clock; the flight then runs ELSEWHERE, the
    first running sample more than 5 s after the last frozen one."""
    flight = Flight(clocked, tmp_path, download_s=1000.0)
    for t in range(5):
        flight.tick(float(t), FIELD)
        assert flight.job.state == "waiting"
        assert flight.job.reason == FOLLOW.LOADING_REASON
    assert flight.job.spawn.episodes == 0 and flight.lander.entered == 0
    clocked.values["sim_time_s"] = 3.0              # the flight runs
    flight.tick(35.0, ELSEWHERE)
    assert flight.job.spawn.episodes == 1
    assert "spawn=spawn" in _log(tmp_path)
    flight.fly(36, 40, ELSEWHERE)
    assert flight.lander.entered == 0               # nothing of the field


def test_a_load_x_plane_answers_through_is_a_flight_load(clocked, tmp_path):
    """The clock stops while X-Plane loads the field (its datarefs still
    answer), then runs: the field's core is the episode."""
    flight = Flight(clocked, tmp_path, download_s=1000.0)
    for t in range(6):
        clocked.values["sim_time_s"] = float(t)
        flight.tick(float(t), ELSEWHERE)
    for t in range(6, 30):                          # loading: frozen clock
        flight.tick(float(t), FIELD)
    assert flight.job.reason == FOLLOW.LOADING_REASON
    clocked.values["sim_time_s"] = 0.5
    flight.tick(30.0, FIELD)
    clocked.values["sim_time_s"] = 1.5
    flight.tick(31.0, FIELD)
    episode = flight.job.spawn.episode
    assert flight.job.reader.resets == 1
    assert episode is not None and episode.witness == "flight_load"
    assert {k.split("/", 1)[1] for k in episode.wants} == set(_core())
    assert episode.window_end > 31.0                # the window is counted on


def test_a_far_move_after_a_gap_replaces_the_open_episode(xplane, tmp_path):
    """No clock (an older X-Plane): the first sample opens the field's
    episode; the camera at another place 40 s later is a jump, and the
    field's core is no longer fetched."""
    flight = Flight(xplane, tmp_path, download_s=1000.0)
    flight.tick(0.0, FIELD)
    assert flight.job.spawn.episode.witness == "spawn"
    flight.tick(40.0, ELSEWHERE)
    assert flight.job.tracker.jumps == 1
    assert "spawn=jump" in _log(tmp_path)
    assert flight.job.spawn.episode is None         # nothing to land there
    assert flight.job.last_dispatched == []


# --- the start: never blocks, never contradicts itself ----------------------


def test_the_rescan_runs_beside_the_job(tmp_path, monkeypatch):
    """#2028 (restart): ~560 tiles were rescanned inside the start command
    and before the job's first word; the job now says "starting" at once,
    follows the index as it stands and rescans beside it."""
    import threading

    from o4_engine import imagery_ondemand as ONDEMAND
    gate, scanned = threading.Event(), []

    def tiles(working_dir):
        assert gate.wait(20), "TIMED_OUT"
        yield ("dir", 60, -136)
    monkeypatch.setattr(ONDEMAND, "on_demand_tiles", tiles)
    monkeypatch.setattr(FOLLOW.INDEX, "rebuild",
                        lambda conn, t, **kw: scanned.extend(t) or 3)
    events = []
    job = FOLLOW.FollowJob(
        events.append, reader=WEBAPI.PositionReader(WEBAPI.base_url(9, "127.0.0.1"),
                                                    timeout=0.2),
        lander=lambda row, tier: {}, index_path=str(tmp_path / "i.sqlite"),
        log_path=str(tmp_path / "od.log"), rescan_dir=str(tmp_path))
    job._status(0.0, force=True)
    assert events[-1].state == "starting"
    job.open()                                  # returns: the scan waits
    assert job.rescan.is_alive() and scanned == []
    gate.set()
    job.rescan.join(20)
    assert scanned == [("dir", 60, -136)]
    assert "rescanned=1 textures=3" in _log(tmp_path)
    job._conn.close()


def test_the_headline_agrees_with_the_button():
    import O4_Imagery_OnDemand_Text as TEXT
    starting, stopped = (TEXT.FOLLOW_TEMPLATES[k] for k in ("starting", "stopped"))
    assert TEXT.follow_headline(None, True) == starting
    assert TEXT.follow_headline(None, False) == stopped
    assert TEXT.follow_headline({"state": "stopped"}, True) == starting
    following = {"state": "following", "textures": 4}
    assert TEXT.follow_headline(following, True) == TEXT.follow_lines(following)[0]
    assert TEXT.follow_headline(following, False) == stopped


def test_a_kept_departure_has_its_airport_core_fetched(monkeypatch):
    """RULINGS 2026-11-12c (3): a departure already full in the World pack
    is not built, so its cores are fetched at the flight's start."""
    from types import SimpleNamespace as NS

    from o4_engine import flight_job_run as RUN
    from o4_engine import imagery_after_build as AFTER
    seen = {}
    monkeypatch.setattr(AFTER, "start", lambda tiles, busy, extra: seen.update(
        tiles=tiles, busy=busy, extra=extra) or "thread")
    from collections import namedtuple
    point = namedtuple("Point", "ident lat lon")     # hashable, as FP's
    dep, arr = point("AAAA", 42.37, -122.87), point("BBBB", 43.4, -124.2)
    manager = NS(plan=NS(waypoints=[dep, arr]), jobs=[
        NS(tile=(42, -123), kind="full", state="swapped"),     # kept: fetched
        NS(tile=(43, -125), kind="full", state="queued"),      # built: publish
        NS(tile=(42, -124), kind="drape", state="swapped")])
    building = set()
    session = NS(building_tiles=lambda: building,
                 tile_build_dir=lambda lat, lon: f"/b/{lat}{lon}")
    assert RUN._sharpen_kept_endpoints(manager, session) == "thread"
    assert seen["tiles"] == [("/b/42-123", 42, -123)]
    assert seen["extra"][(42, -123)] == [("AAAA", 42.37, -122.87)]
    assert not seen["busy"]()
    building.add("+43-125")                      # another tile: no hold
    assert not seen["busy"]()
    building.add("+42-123")
    assert seen["busy"]()


# --- a flight plan goes first (owner 2026-11-12T23:40:51Z) ------------------


def _dispatched(flight) -> set:
    return {f.square.split("/", 1)[1] for f in flight.job.last_dispatched}


def test_a_plan_drops_the_other_region_and_serves_its_departure(xplane, tmp_path):
    """The other region's episode (FAR) is dropped, the plan's departure
    core (FIELD) is all that is fetched while it lands: no planner
    fetches, nothing more of FAR."""
    from test_imagery_spawn import FAR
    flight = Flight(xplane, tmp_path, download_s=1000.0)
    flight.job.slots.max_slots = 4
    flight.tick(0.0, FAR)
    assert flight.job.spawn.episode.witness == "spawn"
    assert _dispatched(flight) <= set(_core(FAR))
    flight.job.focus(*FIELD)
    flight.tick(1.0, FAR)                           # the camera still at FAR
    episode = flight.job.spawn.episode
    assert episode.witness == "plan" and (episode.lat, episode.lon) == FIELD
    assert "spawn=plan" in _log(tmp_path)
    for t in range(2, 8):
        flight.tick(float(t), FAR)
        assert _dispatched(flight) <= set(_core(FIELD))
        assert all(f.square.split("/", 1)[1] in _core(FIELD)
                   for f in flight.job.last_plan)


def test_a_plan_departure_is_served_before_x_plane_answers(xplane, tmp_path):
    flight = Flight(xplane, tmp_path, download_s=1000.0)
    flight.job.focus(*FIELD)
    flight.tick(0.0, down=True)
    assert flight.job.state == "waiting"
    assert flight.job.spawn.episode.witness == "plan"
    assert _dispatched(flight) and _dispatched(flight) <= set(_core(FIELD))


def test_a_first_position_elsewhere_keeps_the_plan_first(xplane, tmp_path):
    flight = Flight(xplane, tmp_path, download_s=1000.0)
    flight.job.focus(*FIELD)
    flight.tick(0.0, down=True)
    flight.tick(1.0, ELSEWHERE)                     # X-Plane's first answer
    assert flight.job.spawn.episode.witness == "plan"


def test_the_startup_rescan_waits_while_a_core_is_served(tmp_path, monkeypatch):
    import time

    from o4_engine import imagery_ondemand as ONDEMAND
    scanned = []
    monkeypatch.setattr(ONDEMAND, "on_demand_tiles",
                        lambda working_dir: iter([("dir", 60, -136)]))
    monkeypatch.setattr(FOLLOW.INDEX, "rebuild",
                        lambda conn, t, **kw: scanned.extend(t) or 1)
    job = FOLLOW.FollowJob(
        lambda event: None,
        reader=WEBAPI.PositionReader(WEBAPI.base_url(9, "127.0.0.1"), timeout=0.2),
        lander=lambda row, tier: {}, index_path=str(tmp_path / "i.sqlite"),
        log_path=str(tmp_path / "od.log"), rescan_dir=str(tmp_path))
    job.spawn.episode = object()                    # the departure's core
    job.open()
    time.sleep(0.3)
    assert scanned == [] and job.rescan.is_alive()
    job.spawn.episode = None                        # landed: the rest now
    job.rescan.join(20)
    assert scanned == [("dir", 60, -136)]
    job._conn.close()
