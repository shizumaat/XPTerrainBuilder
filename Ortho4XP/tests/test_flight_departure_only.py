"""Twin of a flight plan with a departure only (#2023; RULINGS
2026-11-12c (2): ready at the departure area, a conservative countdown,
never an automatic reload).

From with an empty To (both apps' quick entry, a plan file naming one
airport) is a plan of one place.  The flight prepares only the
departure area: the departure tile built ``full`` first, at the highest
priority (its build fetches the airport's imagery first), and the tiles
of X-Plane's window around it as drapes at 512 px whatever
``drape_photo_px`` says; nothing else is planned or waited for, and
build-ahead's track mode does the rest in flight (#2019).  A To added
later plans the route again.  Hermetic: no files, no network, no build.
"""
from __future__ import annotations

from datetime import datetime, timezone

import O4_Flight_Plan as FP
import O4_Flight_Schedule as SCHEDULE
import O4_World_Window as WINDOW
from o4_engine import flight_commands as FC
from o4_engine import flight_job_run as FLIGHT
from o4_engine import flight_record as RECORD
from o4_engine.flight_manager import (PREP_DRAPE_PX, FlightManager,
                                      flight_jobs, prep_drape_px)
from o4_engine.flight_notices import notice

CYYR = (53.30427, -60.447077)
DEST = (53.15, -63.9)
WHEN = datetime(2026, 11, 12, tzinfo=timezone.utc)
FACTS = {"world_installed": True, "budget_fits": True, "network_ok": True,
         "all_on_disk": True, "prefetch_done": True}


def _alone():
    return FC._plan_of(None, "", {"ident": "cyyr", "lat": CYYR[0],
                                  "lon": CYYR[1]}, None)


def _placeholder(_tile):
    return "placeholder"            # every tile in an enabled region


def _estimate(tile, kind, role):
    return SCHEDULE.job_estimate(kind, {"full": 900.0}.get(kind), known=True)


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
        return "swapped"


def _manager(slots=1):
    plan = _alone()
    record = RECORD.from_plan(plan, "none", WHEN)
    builder = _Builder()
    manager = FlightManager(record, plan, builder=builder,
                            publisher=_Publisher(), facts=lambda: dict(FACTS),
                            state_of=_placeholder, estimate=_estimate,
                            parked_slots=slots)
    return manager, builder


def test_a_departure_only_plan_is_accepted():
    plan = _alone()
    assert plan.departure_only and plan.destination == ""
    assert plan.origin == "CYYR" and len(plan.waypoints) == 1
    wire = FC.plan_wire(plan)
    assert wire["destination"] == "" and wire["route_km"] == 0
    assert FC.plan_from_wire(wire) == plan
    # A plan file naming one airport reads as two copies of it: the same.
    assert FP.parse_fms("I\n1100 Version\nCYCLE 2511\nADEP CYYR\nNUMENR 1\n"
                        "1 CYYR ADEP 0.0 53.30427 -60.447077\n").departure_only
    record = RECORD.from_plan(plan, "none", WHEN)
    assert record.destination is None and record.origin["ident"] == "CYYR"
    assert record.id.endswith("-CYYR-NONE")
    assert RECORD.plan_of(record).departure_only
    two = FP.FlightPlan([plan.waypoints[0], FP.Waypoint("D", *DEST)])
    assert not two.departure_only and two.destination == "D"


def test_its_jobs_are_the_departure_full_and_the_window_ring_drapes():
    jobs, (samples, times) = flight_jobs(
        _alone(), corridor_km=20, build_alternate=False, cruise_ms=None,
        intermediate="drape", state_of=_placeholder, estimate=_estimate)
    ring = {t for t, i in WINDOW.route_entries([CYYR]).items() if i <= 0}
    departure = FP.tile_of(*CYYR)
    assert {j.tile for j in jobs} == ring and departure in ring
    by = {j.tile: j for j in jobs}
    assert (by[departure].role, by[departure].kind) == ("departure", "full")
    assert all((j.role, j.kind) == ("enroute", "drape")
               for t, j in by.items() if t != departure)
    assert all(j.klass == SCHEDULE.P0 and j.deadline_s == 0 for j in jobs)
    assert times == [0.0] and len(samples) == 1


def test_the_departure_starts_first_and_ready_waits_for_only_those():
    manager, builder = _manager(slots=1)
    manager.tick(0.0, None)
    assert builder.started[0] == (FP.tile_of(*CYYR), "full", "P0")
    expected = SCHEDULE.departure_countdown(manager._live_jobs(0.0), 1)
    assert manager.countdown_s == expected > 0
    assert manager.record.state == "preparing"
    for t in range(1, 40):
        for tile, _kind, _klass in builder.started:
            if tile not in {d[0] for d in builder.done}:
                builder.done.append((tile, True))
        manager.tick(float(t), None)
        if manager.record.state == "ready":
            break
    assert manager.record.state == "ready"
    assert {s[0] for s in builder.started} == {j.tile for j in manager.jobs}
    assert manager.countdown_s == 0.0
    codes = [n["code"] for n in manager.notices()]
    assert "ready" in codes


def test_the_ring_is_fetched_at_quick_whatever_the_setting(monkeypatch):
    monkeypatch.setattr("o4_engine.world_job_run.drape_px", lambda: 4096)
    assert prep_drape_px(_alone()) == PREP_DRAPE_PX == 512
    two = FP.FlightPlan([_alone().waypoints[0], FP.Waypoint("D", *DEST)])
    assert prep_drape_px(two) is None
    quick = FLIGHT.estimate(px_of=lambda: prep_drape_px(_alone()))
    user = FLIGHT.estimate(px_of=lambda: prep_drape_px(two))
    assert quick((53, -60), "drape", "enroute") == SCHEDULE.job_estimate(
        "drape", SCHEDULE.DRAPE_SECONDS[512])
    assert user((53, -60), "drape", "enroute") == SCHEDULE.job_estimate(
        "drape", SCHEDULE.DRAPE_SECONDS[4096])


def test_a_later_to_plans_the_route_again():
    manager, builder = _manager(slots=1)
    manager.tick(0.0, None)
    departure = FP.tile_of(*CYYR)
    name = manager.set_destination(1.0, FP.Waypoint("DEST", *DEST))
    assert name == "DEST" and not manager.plan.departure_only
    by = {j.tile: j for j in manager.jobs}
    assert by[departure].state == "building"          # kept, not restarted
    dest = by[FP.tile_of(*DEST)]
    assert (dest.role, dest.kind) == ("destination", "full")
    assert manager.record.destination["ident"] == "DEST"
    assert len(manager.record.waypoints) == 2
    assert prep_drape_px(manager.plan) is None
    assert manager.status(1.0)["route_km"] > 0


def test_a_departure_only_flight_never_arrives():
    manager, _builder = _manager()
    for t in range(0, 12):
        manager.tick(float(t), {"lat": CYYR[0] + 0.01 * t, "lon": CYYR[1],
                                "agl_m": 300.0, "gs_ms": 80.0})
    assert manager.record.state == "flying"
    assert manager.record.phase == "airborne"       # never "approach"
    for t in (20.0, 700.0):
        manager.tick(t, {"lat": CYYR[0], "lon": CYYR[1], "agl_m": 0.0,
                         "gs_ms": 0.0})
    assert manager.record.phase == "landed"
    assert manager.record.state == "flying"


def test_the_ready_notice_names_the_departure_area():
    text = notice("ready", origin="CYYR")["text"]
    assert "CYYR" in text and "destination" not in text
    assert notice("ready", origin="CYYR", destination="CYYT")["text"] == (
        "Your flight from CYYR to CYYT is ready for departure.")


def test_a_flight_with_a_destination_refuses_a_new_one():
    import pytest
    manager, _builder = _manager()
    manager.set_destination(0.0, FP.Waypoint("DEST", *DEST))
    with pytest.raises(ValueError, match="divert"):
        manager.set_destination(1.0, FP.Waypoint("X", 50.0, -60.0))


def test_2032_ring_drapes_go_in_over_held_placeholders_and_keep_the_offer():
    """#2032 (KTUS): X-Plane loaded the ring's placeholders before its
    drapes were ready, so rule S3 kept them staged; they never went in
    once the app closed.  Over a placeholder with no file the publisher
    swaps at once (``O4_World_Pack.nothing_held``); X-Plane shows the new
    tiles only at its next load of them, so the ground reload is still
    offered for them until the witness shows a newer load."""
    manager, builder = _manager(slots=4)
    ring = {j.tile for j in manager.jobs}
    facts = dict(FACTS, xplane_running=True, loads=set(ring),
                 load_stamps={t: 5.0 for t in ring})
    manager.facts = lambda: facts
    parked = {"lat": CYYR[0], "lon": CYYR[1], "agl_m": 0.0, "gs_ms": 0.0}
    for t in range(1, 60):
        for tile, _kind, _klass in builder.started:
            if tile not in {d[0] for d in builder.done}:
                builder.done.append((tile, True))
        manager.tick(float(t), parked)
        if all(j.state == "swapped" for j in manager.jobs):
            break
    assert all(j.state == "swapped" for j in manager.jobs)
    assert set(manager._unread) == ring
    assert not manager._loaded_real()
    manager.tick(70.0, parked)
    assert manager.reload == "offered" and set(manager._ground_tiles) == ring
    facts["load_stamps"] = {t: 80.0 for t in ring}    # X-Plane read them
    manager.tick(81.0, parked)
    assert manager._unread == {} and manager._loaded_real()
