"""Twin of the flight manager (spec flight-manager-and-world-20261110
§4.3, §5.2, §5.3, §6.2, §8.2, §9, §12; lane F1b):
``src/o4_engine/flight_manager.py`` (the flight's jobs, readiness,
countdown, phases), ``flight_budget.py`` (the budget pre-check),
``flight_job_run.py`` / ``flight_commands.py`` (the engine commands and
``world_job_start {mode: "flight"}``), and the ``FlightStatus`` /
``FlightReady`` wire.

The end-to-end case is the CYYR World pack flight (W0's fixture): a flight
from the recording's first position to +53-064 is created, waits on the
ground until ready (one ground reload for the staged first window, S6
(a)), then flies the recording (``tools/flight_schedule_replay.py
--flight``).  Hermetic: tmp_path, no network, no X-Plane, no build.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import O4_Flight_Plan as FP
import O4_Flight_Schedule as SCHEDULE
import O4_World_Pack as WP
import pytest
from o4_engine import flight_budget as BUDGET
from o4_engine import flight_commands as FC
from o4_engine import flight_job_run as FLIGHT
from o4_engine import flight_record as RECORD
from o4_engine import world_commands as WORLD
from o4_engine import world_job_run as WORLD_JOB
from o4_engine.events import CAPABILITIES, FlightReady, FlightStatus
from o4_engine.flight_manager import FlightManager, flight_jobs

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "tools"))

import flight_schedule_replay as R  # noqa: E402

CYYR = (53.30427, -60.447077)
DEST = (53.15, -63.9)              # in +53-064, the tile built on the fly
WHEN = datetime(2026, 11, 10, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def recording():
    with open(R.FIXTURE, encoding="utf-8") as f:
        flight = json.load(f)
    with open(R.KIT, encoding="utf-8") as f:
        kit = json.load(f)
    return flight, kit


def _plan(dest=DEST, alternate=None):
    return FP.FlightPlan([FP.Waypoint("DEP", *CYYR), FP.Waypoint("DEST", *dest)],
                         source="test", alternate=alternate)


def _kit_state(kit):
    placeholders = {WP.parse_tile(n) for n in kit["placeholders"]}
    external = {WP.parse_tile(n) for n in kit["external"]}
    return lambda t: ("external" if t in external
                      else "placeholder" if t in placeholders else None)


def _estimate(tile, kind, role):
    return SCHEDULE.job_estimate(kind, {"full": 900.0}.get(kind), known=True)


# ---------------------------------------------------------------- the plan

def test_a_flight_becomes_its_jobs(recording):
    """CYYR -> +53-064 over the kit's World pack: the departure is the
    user's own tile (external: ready as it is), the destination a full
    build (P2), the corridor drapes where the pack holds a
    placeholder -- the first window P0 (before the flight loads), the
    rest P1 with deadlines from where they enter the window; nothing
    outside the regions."""
    jobs, (_samples, times) = flight_jobs(
        _plan(), corridor_km=20, build_alternate=False,
        cruise_ms=290 * SCHEDULE.KT_TO_MS, intermediate="drape",
        state_of=_kit_state(recording[1]), estimate=_estimate)
    by = {WP.tile_name(*j.tile): j for j in jobs}
    assert by["+53-061"].role == "departure"
    assert by["+53-061"].state == "external"
    dest = by["+53-064"]
    assert (dest.role, dest.kind, dest.klass, dest.state) == (
        "destination", "full", SCHEDULE.P2, "queued")
    assert dest.est_s == (675.0, 1350.0) and dest.deadline_s > 0
    first = {n for n, j in by.items()
             if j.klass == SCHEDULE.P0 and j.role == "enroute"}
    assert first == {"+52-060", "+52-061", "+52-062", "+52-063", "+53-060",
                     "+53-062", "+53-063", "+54-060", "+54-061", "+54-062",
                     "+54-063"}
    later = [j for j in jobs if j.klass == SCHEDULE.P1]
    assert later and all(j.kind == "drape" and j.deadline_s > 0 for j in later)
    assert all(j.deadline_s <= times[-1] for j in jobs)
    assert "+51-060" not in by          # the kit has no placeholder there


def test_the_alternate_is_built_only_with_the_checkbox(recording):
    alt = FP.Waypoint("ALT", 52.5, -62.5)
    for on, expected in ((False, "enroute"), (True, "alternate")):
        jobs, _ = flight_jobs(_plan(alternate=alt), corridor_km=20,
                              build_alternate=on, cruise_ms=None,
                              intermediate="drape",
                              state_of=_kit_state(recording[1]),
                              estimate=_estimate)
        job = next(j for j in jobs if j.tile == (52, -63))
        assert job.role == expected
        if on:
            assert job.kind == "full"


# ---------------------------------------------------- end to end (replay)

def test_the_cyyr_flight_waits_for_readiness_then_flies(recording):
    """The flight replayed (14 parked slots, 3 in the air, light 397 s,
    full 900 s): the countdown at creation covers the real wait and never
    rose; the first-window tiles X-Plane held (its loaded columns -62 to
    -60) went in with ONE ground reload (offered, pressed by the replayed
    pilot, 12c (4); taken as soon as the departure area is ready, 12c (2),
    so it may carry the first window's staged column -63 too); every
    World tile X-Plane opened in flight was swapped before it, none after
    a load; the flight is airborne by the recording's end."""
    result = R.replay_flight(*recording, DEST)
    assert result["ok"], result
    assert result["countdown_s"] >= result["wait_s"]
    assert len(result["reloads"]) == 1
    held = {r["tile"] for r in result["tiles"]
            if r["klass"] == "P0" and r["role"] == "enroute"
            and r["tile"][4:] in ("060", "061", "062")}
    first_window = {r["tile"] for r in result["tiles"]
                    if r["klass"] == "P0" and r["role"] == "enroute"}
    assert held <= set(result["reloads"][0][1]) <= first_window
    assert result["state"] == "flying"
    opened = [r for r in result["tiles"] if r["opened_s"] is not None]
    assert {r["tile"] for r in opened} >= {"+53-063", "+53-064", "+53-065"}
    assert all(r["margin_s"] > 0 for r in opened)
    assert all(i[1] == "done" for i in result["items"])


def test_slow_builds_wait_longer_and_still_never_load_a_placeholder(recording):
    """Three slots on a small machine (one parked, one flying): the wait
    grows with the countdown, and nothing opened in flight is late."""
    small = R.replay_flight(*recording, DEST, capacity=3, cores=8)
    assert small["ok"], small
    assert small["wait_s"] > R.replay_flight(*recording, DEST)["wait_s"]


def test_a_faster_flight_leaves_with_its_departure_area_and_is_warned(
        recording):
    """RULINGS 2026-11-12c (2) (replacing 10g's "wait for every row"):
    the same flight at 3x (870 kt) waits only for its departure area, as
    long as at 1x; what its route cannot get in time is warned of
    (``falling_behind``) instead of held on the ground."""
    slow, fast = (R.replay_flight(*recording, DEST, speed=k) for k in (1, 3))
    assert fast["wait_s"] == pytest.approx(slow["wait_s"], abs=5.0)
    codes = {c for _t, c in fast["notices"]}
    assert "ready" in codes
    if not fast["ok"]:
        assert "falling_behind" in codes


# ------------------------------------------------------- manager details

class _Builder:
    def __init__(self):
        self.started, self.done = [], []

    def start(self, tile, kind, due, klass):
        self.started.append((tuple(tile), kind, klass))
        return True

    def poll(self, now):
        done, self.done = self.done, []
        return done


class _Publisher:
    @staticmethod
    def settle(tile, kind, held):
        return "staged" if held else "swapped"


def _manager(recording, facts=None, **kw):
    record = RECORD.from_plan(_plan(), "none", WHEN, cruise_kt=290)
    builder = _Builder()
    base = {"world_installed": True, "budget_fits": True, "network_ok": True,
            "all_on_disk": True, "prefetch_done": True}
    base.update(facts or {})
    manager = FlightManager(record, _plan(), builder=builder,
                            publisher=_Publisher(), facts=lambda: base,
                            state_of=_kit_state(recording[1]),
                            estimate=_estimate, **kw)
    return manager, builder, base


def test_a_blocked_row_shows_a_dash_and_its_sentence(recording):
    manager, _builder, facts = _manager(recording, {
        "budget_fits": False, "budget_detail": "Raise the budget"})
    manager.tick(0.0, None)
    status = manager.status(0.0)
    assert status["countdown_s"] is None
    assert status["reason"] == "Raise the budget"
    assert ["budget", "blocked", None, "Raise the budget"] in [
        list(i) for i in status["items"]]
    facts.update(budget_fits=True)
    manager.tick(1.0, None)
    assert manager.status(1.0)["countdown_s"] > 0


def test_a_build_that_fails_twice_is_failed(recording):
    manager, builder, _facts = _manager(recording, parked_slots=1)
    manager.tick(0.0, None)
    tile = builder.started[0][0]
    for t in (1.0, 2.0):
        builder.done.append((tile, False))
        manager.tick(t, None)
    job = next(j for j in manager.jobs if j.tile == tile)
    assert job.state == "failed"
    assert len([s for s in builder.started if s[0] == tile]) == 2
    assert manager.record.state == "preparing"


def test_phases_takeoff_and_arrival(recording):
    manager, _builder, _facts = _manager(recording)
    manager.tick(0.0, {"lat": CYYR[0], "lon": CYYR[1], "agl_m": 0.0,
                       "gs_ms": 0.0})
    assert manager.record.phase == "parked"
    manager.tick(1.0, {"lat": CYYR[0], "lon": CYYR[1], "agl_m": 0.0,
                       "gs_ms": 8.0})
    assert manager.record.phase == "taxi"
    for t in range(2, 14):
        manager.tick(float(t), {"lat": CYYR[0], "lon": CYYR[1] - 0.001 * t,
                                "agl_m": 200.0, "gs_ms": 80.0})
    assert manager.record.state == "flying" and manager.takeoff_at == 2.0
    for t in range(14, 20):
        manager.tick(float(t), {"lat": DEST[0], "lon": DEST[1],
                                "agl_m": 500.0, "gs_ms": 70.0})
    assert manager.record.phase == "approach"
    for t in (20.0, 700.0):
        manager.tick(t, {"lat": DEST[0], "lon": DEST[1], "agl_m": 0.0,
                         "gs_ms": 0.0})
    assert manager.record.phase == "landed"
    assert manager.record.state == "arrived"


def test_update_replans_and_keeps_started_jobs(recording):
    manager, builder, _facts = _manager(recording, parked_slots=2)
    manager.tick(0.0, None)
    started = {s[0] for s in builder.started}
    manager.record.corridor_km = 60.0
    manager.replan()
    states = {j.tile: j.state for j in manager.jobs}
    assert started and all(states[t] == "building" for t in started)


def test_status_is_the_wire_event_and_the_fly_fixture_shape(recording):
    """``FlightStatus`` carries exactly the fields the Fly panes decode
    (the shared fixture ``fly_pane_cases.json``, ``FlyPaneTests``)."""
    from o4_engine.jsonl import serialize_event
    sys.path.insert(0, HERE)
    import test_fly_pane as FLY
    manager, _builder, _facts = _manager(recording)
    manager.tick(0.0, None)
    wire = json.loads(json.dumps(serialize_event(
        FlightStatus(**manager.status(0.0)))))
    assert set(FLY.FLIGHT_STATUS) == set(wire) - {"seq", "ts"}
    assert wire["event"] == "FlightStatus"
    assert wire["flight"] == manager.record.id
    assert all(len(row) == 4 for row in wire["items"])
    assert all(len(row) == 6 and len(row[0]) == 2 for row in wire["jobs"])
    ready = serialize_event(FlightReady(request=7, result={"waypoints": []}))
    assert ready["event"] == "FlightReady" and ready["request"] == 7
    assert "flight_manager" in CAPABILITIES


# ------------------------------------------------------------- the budget

def test_the_budget_pre_check():
    jobs = [SCHEDULE.Job((0, 0), "enroute", "drape", SCHEDULE.P1, 0.0, (1, 2)),
            SCHEDULE.Job((0, 1), "destination", "full", SCHEDULE.P2, 0.0,
                         (1, 2)),
            SCHEDULE.Job((0, 2), "enroute", "drape", SCHEDULE.P1, 0.0, (1, 2),
                         state="swapped")]
    need = BUDGET.need_bytes(jobs, 3600.0, uncached_tiles=1)
    assert need[0] == pytest.approx(45e6 + 220e6 + 0.05 * 1024 ** 3 + 2.2e9)
    sharp = BUDGET.need_bytes(jobs, 3600.0, uncached_tiles=1, drape_px=1024)
    assert sharp[0] - need[0] == pytest.approx(3 * 45e6)    # (1024/512)^2
    assert BUDGET.verdict(need, None, None) == (True, "")
    fits = {"budget_bytes": 100e9, "used_bytes": 50e9, "floor_bytes": 20e9}
    assert BUDGET.verdict(need, fits, 500e9) == (True, "")
    ok, detail = BUDGET.verdict(need, dict(fits, used_bytes=99e9), 500e9)
    assert ok and detail.startswith("Fits after clearing about")
    ok, detail = BUDGET.verdict(
        need, dict(fits, used_bytes=99.5e9, floor_bytes=99.5e9), 500e9)
    assert not ok and "Raise the budget" in detail
    assert "narrow the corridor" in detail
    ok, detail = BUDGET.verdict(need, fits, 1e9)
    assert not ok and "narrow the corridor" in detail


# ----------------------------------------------------- the engine commands

@pytest.fixture
def engine(tmp_path, monkeypatch, recording):
    """A World pack with the kit's placeholders in a tmp Custom Scenery,
    the flights folder in tmp_path, and every slow or outside fact faked:
    the feed answers the aircraft parked at CYYR."""
    import O4_Machine_Slots as SLOTS
    from o4_engine import position_feed as FEED
    scenery = tmp_path / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    (pack / "Earth nav data").mkdir(parents=True)
    with open(pack / WP.MARKER, "w", encoding="utf-8", newline="\n") as h:
        h.write("{}")
    for name in recording[1]["placeholders"]:
        WP.write_placeholder(str(pack), *WP.parse_tile(name))
    folder = str(tmp_path / "Flights")
    monkeypatch.setattr(RECORD, "flights_dir", lambda data_root=None: folder)
    monkeypatch.setattr(WORLD, "staging_root", lambda: str(tmp_path / "staging"))
    monkeypatch.setattr(WORLD, "write_log", lambda record: None)
    monkeypatch.setattr(WORLD, "scenery_dir_or_default",
                        lambda scenery_dir="": scenery_dir or str(scenery))
    monkeypatch.setattr(WORLD, "_xplane_running", lambda: False)
    monkeypatch.setattr(FLIGHT, "_settings", lambda: {"default_website": "BI"})
    monkeypatch.setattr(WORLD_JOB, "_settings", lambda: {})
    monkeypatch.setattr(FLIGHT, "estimate", lambda *a: _estimate)
    monkeypatch.setattr(FLIGHT, "pack_state", lambda scenery_dir: _kit_state(
        recording[1]))
    monkeypatch.setattr(SLOTS, "session_capacity", lambda: 4)

    class Facts:
        def __init__(self, *args, **kw):
            pass

        def __call__(self):
            return {"world_installed": True, "budget_fits": True,
                    "network_ok": True, "all_on_disk": True,
                    "prefetch_done": True}
    monkeypatch.setattr(FLIGHT, "_Facts", Facts)

    class Feed:
        resets = 0

        def read(self):
            return {"lat": CYYR[0], "lon": CYYR[1], "agl_m": 0.0,
                    "gs_ms": 0.0, "frame_s": 0.02}
    monkeypatch.setattr(FEED, "shared", lambda base=None: Feed())
    events, builds = [], []
    # the corridor's drapes (RULINGS 2026-11-11j): no network in a twin
    monkeypatch.setattr(WORLD_JOB, "drape_tile", lambda tile, p, z, px=None:
                        bool(builds.append(("drape", tile, px))))

    class Session:
        _emit = events.append

        def subscribe(self, callback):
            pass

        def enqueue_build(self, tiles, *args, **kw):
            builds.append((tiles, kw))
            return True

        def tile_build_dir(self, lat, lon):
            return str(tmp_path / "build")
    yield Session(), events, builds, folder
    FLIGHT.stop()
    WORLD_JOB.world_job_stop()


def _wait_for(predicate, seconds=15.0):
    deadline = time.time() + seconds
    while not predicate() and time.time() < deadline:
        time.sleep(0.05)
    return predicate()


def test_create_status_update_end(engine, monkeypatch):
    """``flight_create`` from a departure + arrival writes the record and
    starts the flight in world_job's flight mode: full builds queued
    through the session (class, never interactive), ``FlightStatus``
    events; track mode starts beside it (#2019); ``flight_update``
    replans; ``flight_end`` closes it and track mode runs on."""
    session, events, builds, folder = engine
    table = FC.flight_handlers(session)
    reply = table["flight_create"](
        dep={"ident": "cyyr", "lat": CYYR[0], "lon": CYYR[1]},
        arr={"ident": "dest", "lat": DEST[0], "lon": DEST[1]}, cruise_kt=290)
    flight = reply["flight"]
    assert flight.endswith("-CYYR-DEST")
    assert os.path.isfile(os.path.join(folder, flight + ".json"))
    assert _wait_for(lambda: builds and any(
        isinstance(e, FlightStatus) for e in events))
    # the first window goes first, as drapes (the departure is external);
    # the long destination starts beside it at once: with the countdown
    # to the departure area only (12c (2)) its slack is under the
    # laxity guard
    assert _wait_for(lambda: any(b[0] == "drape" for b in builds[:3]))
    first = next(b for b in builds if b[0] == "drape")
    assert first[1][1] in range(-63, -59)
    for _tiles, kw in (b for b in builds if b[0] != "drape"):
        assert kw["missing_art"] == "leave" and kw["klass"] in ("P0", "P2")
        assert "overrides" not in kw     # a full build: no profile (11j)
    with pytest.raises(ValueError, match="already active"):
        table["flight_create"](dep={"lat": 1, "lon": 1},
                               arr={"lat": 2, "lon": 2})
    assert WORLD_JOB.world_job_start(session) == {"status": "started"}
    assert FLIGHT.current().manager.record.id == flight
    status = table["flight_status"]()
    assert status["flight"] == flight and status["state"] == "preparing"
    assert status["phase"] == "parked" and status["items"]
    assert table["flight_update"](flight=flight, corridor_km=40,
                                  build_alternate=True) == {"flight": flight}
    with pytest.raises(ValueError, match="no alternate"):
        table["flight_divert"](flight=flight, to="alternate")
    assert table["flight_divert"](
        flight=flight, to={"ident": "alt", "lat": 52.5, "lon": -62.5}) == {
        "flight": flight, "diverted_to": "ALT"}
    assert table["flight_status"]()["diverted_to"] == "ALT"
    with pytest.raises(ValueError, match="No scenery reload"):
        table["flight_reload"](flight=flight)
    assert [r["flight"] for r in table["flight_list"]()["flights"]] == [flight]
    starts = []
    monkeypatch.setattr(WORLD_JOB, "autostart",
                        lambda session, **kw: starts.append(session))
    assert table["flight_end"](flight=flight) == {"flight": flight,
                                                  "state": "closed"}
    assert FLIGHT.current() is None and starts == [session]
    assert WORLD_JOB._RUNNER is not None        # track mode runs on
    assert RECORD.load(os.path.join(folder, flight + ".json")).state == "closed"
    assert table["flight_status"](flight=flight)["state"] == "closed"


def test_autostart_resumes_the_active_flight(engine):
    """At launch the active record (preparing) runs again in flight mode,
    beside track mode (#2019)."""
    session, events, _builds, folder = engine
    record = RECORD.from_plan(_plan(), "none", WHEN)
    RECORD.save(record, folder)
    assert WORLD_JOB.autostart(session) == {"status": "started",
                                            "mode": "flight",
                                            "flight": record.id,
                                            "track": "started"}
    assert WORLD_JOB._RUNNER is not None
    assert FLIGHT.current().manager.record.id == record.id
    assert _wait_for(lambda: any(isinstance(e, FlightStatus) for e in events))


def test_create_refuses_without_the_world_pack_or_a_route(engine, tmp_path):
    session = engine[0]
    with pytest.raises(ValueError, match="no route"):
        FC.flight_create(session, plan={"waypoints": []})
    with pytest.raises(ValueError, match="Name a flight"):
        FC.flight_create(session)
    with pytest.raises(ValueError, match="World pack"):
        FC.flight_create(session, scenery_dir=str(tmp_path / "nothing"),
                         dep={"lat": 1, "lon": 1}, arr={"lat": 2, "lon": 2})


def test_a_plan_from_the_wire_round_trips():
    plan = FP.FlightPlan([FP.Waypoint("A", 1.0, 2.0, 3000.0, 0.0),
                          FP.Waypoint("B", 3.0, 4.0, None, 900.0)],
                         source="x.fms", alternate=FP.Waypoint("C", 5.0, 6.0),
                         ete_s=900.0, cruise_ms=100.0, cruise_alt_ft=9000.0)
    assert FC.plan_from_wire(FC.plan_wire(plan)) == plan
    assert FC._source_kind("x.fms") == "fms"
    assert FC._source_kind("SimBrief") == "simbrief"
    record = RECORD.from_plan(plan, "fms", WHEN)
    again = RECORD.plan_of(record)
    assert again.points() == plan.points() and again.alternate.ident == "C"


def test_simbrief_completes_with_flight_ready(monkeypatch):
    plan = FP.FlightPlan([FP.Waypoint("A", 1.0, 2.0),
                          FP.Waypoint("B", 3.0, 4.0)], source="SimBrief")
    monkeypatch.setattr(FP, "fetch_simbrief", lambda user: plan)
    events = []
    assert FC.start_flight_plan_simbrief(events.append, request=5,
                                         user="me") == {"status": "started"}
    assert _wait_for(lambda: events)
    assert events[0].request == 5 and events[0].result["origin"] == "A"
    with pytest.raises(ValueError, match="SimBrief"):
        FC.start_flight_plan_simbrief(events.append, user=" ")


def test_no_plan_closes_a_prepared_flight_and_track_mode_runs(engine):
    """#2019 (the owner's CYWG case: a prepared KMRY-KFAT record still
    active owned build-ahead): "No plan" sends ``flight_end {if_prepared:
    true}``; a preparing flight closes, track mode runs alone; a flight
    in the air is left as it is."""
    session, _events, _builds, folder = engine
    table = FC.flight_handlers(session)
    record = RECORD.from_plan(_plan(), "none", WHEN)
    RECORD.save(record, folder)
    assert WORLD_JOB.autostart(session)["flight"] == record.id
    assert WORLD_JOB._RUNNER is not None            # beside the flight
    assert table["flight_end"](if_prepared=True) == {"flight": record.id,
                                                     "state": "closed"}
    assert FLIGHT.current() is None and RECORD.active_flight(folder) is None
    assert WORLD_JOB._RUNNER is not None            # track mode runs on
    assert table["flight_end"](if_prepared=True) == {"flight": None}
    flying = RECORD.from_plan(_plan(), "none", WHEN)
    flying.id += "-air"
    flying.state = "flying"
    RECORD.save(flying, folder)
    assert table["flight_end"](if_prepared=True) == {"flight": None}
    assert RECORD.load(os.path.join(folder, flying.id + ".json")).state == "flying"


def test_create_with_a_departure_only(engine):
    """#2023: ``flight_create`` with a departure and no arrival prepares
    only X-Plane's window at the departure, its drapes fetched at 512 px
    (the departure here is the kit's external tile: nothing to build)."""
    import O4_World_Window as WINDOW
    session, _events, builds, _folder = engine
    table = FC.flight_handlers(session)
    flight = table["flight_create"](
        dep={"ident": "cyyr", "lat": CYYR[0], "lon": CYYR[1]})["flight"]
    assert flight.endswith("-CYYR-NONE")
    ring = {t for t, i in WINDOW.route_entries([CYYR]).items() if i <= 0}
    assert _wait_for(lambda: len([b for b in builds if b[0] == "drape"]) >= 3)
    drapes = [b for b in builds if b[0] == "drape"]
    assert all(tuple(b[1]) in ring and b[2] == 512 for b in drapes)
    jobs = FLIGHT.current().manager.jobs
    assert {j.tile for j in jobs} <= ring
    assert not any(j.role == "destination" for j in jobs)
    assert table["flight_update"](flight=flight, destination={
        "ident": "dest", "lat": DEST[0], "lon": DEST[1]}) == {"flight": flight}
    manager = FLIGHT.current().manager
    assert not manager.plan.departure_only
    assert manager.record.destination["ident"] == "DEST"
    assert any(j.role == "destination" for j in manager.jobs)
