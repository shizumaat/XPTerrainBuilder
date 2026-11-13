"""Twin of track mode beside a flight (#2019, owner 2026-11-12: "No
matter what the flight plan is set to, we should still dynamically load
tiles wherever the aircraft is"): ``src/o4_engine/build_share.py`` (one
slot budget, one owner per tile) with the real ``WorldJob`` (track mode),
``FlightManager`` (the flight's job) and ``world_job_run._SessionBuilder``.

The flight is the CYYR one of ``test_flight_manager`` (its kit's
placeholders); the aircraft is either far off its corridor (CYWG,
Winnipeg) or parked at its departure.  Hermetic: drapes are faked and
finish when the twin says so; no network, no X-Plane, no build.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone

import O4_Flight_Plan as FP
import O4_Flight_Schedule as SCHEDULE
import O4_World_Pack as WP
import pytest
from o4_engine import flight_job_run as FLIGHT
from o4_engine import flight_record as RECORD
from o4_engine import world_job as JOB
from o4_engine import world_job_run as RUN
from o4_engine.build_share import BuildShare
from o4_engine.flight_manager import FlightManager

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "tools"))

import flight_schedule_replay as R  # noqa: E402

CYYR = (53.30427, -60.447077)
CYWG = (49.9100, -97.2399)          # far off the CYYR corridor
DEST = (53.15, -63.9)
WHEN = datetime(2026, 11, 10, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def kit():
    with open(R.KIT, encoding="utf-8") as f:
        return json.load(f)


def _placeholders(kit):
    places = {WP.parse_tile(n) for n in kit["placeholders"]}
    return lambda t: "placeholder" if t in places else None


def _estimate(tile, kind, role):
    return SCHEDULE.job_estimate(kind, {"full": 900.0}.get(kind), known=True)


class Session:
    """Full builds are recorded; their BuildDone never comes (the twin
    looks at drapes)."""

    def __init__(self):
        self.full = []

    def subscribe(self, callback):
        pass

    def enqueue_build(self, tiles, *args, **kw):
        self.full.append(tuple(tiles[0]))
        return True


class Drapes:
    """The drape writer: every call recorded; each finishes when the twin
    releases its tile."""

    def __init__(self):
        self.calls, self.gates = [], {}
        self.lock = threading.Lock()

    def __call__(self, tile):
        with self.lock:
            self.calls.append(tuple(tile))
            gate = self.gates.setdefault(tuple(tile), threading.Event())
        gate.wait(10.0)
        return True

    def release(self, *tiles):
        with self.lock:
            for tile in tiles:
                self.gates.setdefault(tuple(tile), threading.Event()).set()


class Publisher:
    def settle(self, tile, kind, held):
        return "staged" if held else "swapped"


def _builder(share, owner, drapes, session=None):
    return RUN._SessionBuilder(session or Session(), "BI", 16, drape=drapes,
                               share=share, owner=owner)


def _track(share, drapes, capacity=4, state_of=lambda t: "placeholder"):
    """Track mode as ``world_job_run._Runner`` wires it (``state_of``:
    the pack's placeholders, ``_Wanted``)."""
    return JOB.WorldJob(
        builder=_builder(share, "track", drapes), publisher=Publisher(),
        wanted=lambda tile: (not share.claimed("track", tile)
                             and state_of(tile) == "placeholder"),
        slot_free=lambda slots, running: share.free_for("track", slots,
                                                        running),
        capacity=capacity)


def _flight(share, drapes, state_of, slots=2):
    """A flight's job as ``flight_job_run._Runner`` wires it."""
    plan = FP.FlightPlan([FP.Waypoint("DEP", *CYYR),
                          FP.Waypoint("DEST", *DEST)], source="test")
    manager = FlightManager(
        RECORD.from_plan(plan, "none", WHEN), plan,
        builder=_builder(share, "flight", drapes), publisher=Publisher(),
        facts=lambda: {"world_installed": True, "budget_fits": True,
                       "network_ok": True, "all_on_disk": True,
                       "prefetch_done": True},
        state_of=state_of, estimate=_estimate, intermediate="drape",
        parked_slots=slots, flight_slots=slots,
        others_running=lambda: share.others_running("flight"))
    FLIGHT._share_slots(manager, share)
    return manager


def _parked(where):
    return {"lat": where[0], "lon": where[1], "agl_m": 0.0, "gs_ms": 0.0}


def _settle(drapes, count, seconds=5.0):
    deadline = time.time() + seconds
    while len(drapes.calls) < count and time.time() < deadline:
        time.sleep(0.01)
    return list(drapes.calls)


def _wait_built(share, tiles, seconds=5.0):
    """Wait until the released drapes reached the share."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if all(share.owner_of(t) and share._held[t][2] == "built"
               for t in tiles):
            return True
        time.sleep(0.01)
    return False


def test_track_builds_around_the_aircraft_beside_a_flight_off_its_route(kit):
    """The owner's case: a prepared flight still active (its tiles built),
    X-Plane loaded far from its corridor.  Track mode dispatches the ring
    around the aircraft on the slots the flight does not use."""
    share, drapes = BuildShare(), Drapes()
    flight = _flight(share, drapes, state_of=lambda t: "full")   # all built
    assert not any(j.state == "queued" for j in flight.jobs)
    track = _track(share, drapes)
    track.flight_loaded(*CYWG)
    for t in range(3):
        flight.tick(float(t), _parked(CYWG))
        FLIGHT._share_slots(flight, share)
        track.tick(float(t), {"lat": CYWG[0], "lon": CYWG[1]})
    started = _settle(drapes, 2)
    assert len(started) == 2                       # parked: 4 - 2 slots
    assert all(abs(lat - 49.9) <= 2 and abs(lon + 97.2) <= 2
               for lat, lon in started), started
    assert not any(share.claimed("track", t) for t in started)
    assert track.status(3.0)["state"] == "building"
    drapes.release(*started)


def test_corridor_deadlines_win_a_contended_slot(kit):
    """Track mode holds both slots when the flight is created; neither
    job starts more while they run; when one ends, the flight takes the
    slot (track mode ticks first and still leaves it), and track mode
    starts nothing while the flight has jobs waiting."""
    share, drapes = BuildShare(), Drapes()
    track = _track(share, drapes)
    track.flight_loaded(*CYWG)
    track.tick(0.0, {"lat": CYWG[0], "lon": CYWG[1]})
    first = _settle(drapes, 2)
    assert len(first) == 2
    flight = _flight(share, drapes, state_of=_placeholders(kit))
    for t in (1.0, 2.0):
        track.tick(t, {"lat": CYWG[0], "lon": CYWG[1]})
        flight.tick(t, _parked(CYYR))
        FLIGHT._share_slots(flight, share)
    assert len(drapes.calls) == 2                  # one budget: full
    assert not any(j.state == "building" for j in flight.jobs)
    drapes.release(first[0])
    assert _wait_built(share, [first[0]])
    track.tick(3.0, {"lat": CYWG[0], "lon": CYWG[1]})   # track first
    flight.tick(3.0, _parked(CYYR))
    FLIGHT._share_slots(flight, share)
    # the flight's job took the slot (a corridor drape, or its tight
    # destination's full build: the laxity guard), track mode nothing
    building = [j for j in flight.jobs if j.state == "building"]
    assert len(building) == 1
    corridor = {j.tile for j in flight.jobs}
    started = _settle(drapes, 3, seconds=0.5)[2:] + flight.builder.session.full
    assert started == [building[0].tile] and started[0] in corridor
    track.tick(4.0, {"lat": CYWG[0], "lon": CYWG[1]})
    assert len(_settle(drapes, 4, seconds=0.3)) == 2 + (building[0].kind == "drape")
    drapes.release(*drapes.calls)


def test_no_tile_is_built_twice(kit):
    """Parked at the departure, track mode drapes the ring before the
    flight is created; part of the ring is the flight's first window.
    The flight adopts those drapes (running and finished) instead of
    fetching them again; track mode leaves the flight's tiles and keeps
    the rest of its ring; across both jobs every drape is fetched once."""
    share, drapes = BuildShare(), Drapes()
    track = _track(share, drapes, capacity=8,      # 6 parked slots
                   state_of=_placeholders(kit))
    track.flight_loaded(*CYYR)
    track.tick(0.0, {"lat": CYYR[0], "lon": CYYR[1]})
    ring = _settle(drapes, 6)
    assert len(ring) >= 4
    half = len(ring) // 2
    drapes.release(*ring[:half])                   # some built, some running
    assert _wait_built(share, ring[:half])
    flight = _flight(share, drapes, state_of=_placeholders(kit), slots=8)
    corridor = {j.tile for j in flight.jobs}
    shared = set(ring) & corridor
    assert shared and set(ring) - corridor
    for t in range(1, 40):
        track.tick(float(t), {"lat": CYYR[0], "lon": CYYR[1]})
        flight.tick(float(t), _parked(CYYR))
        FLIGHT._share_slots(flight, share)
        drapes.release(*drapes.calls)
        time.sleep(0.02)
    assert len(drapes.calls) == len(set(drapes.calls)), drapes.calls
    assert not set(track.jobs) & corridor          # all the flight's now
    assert set(ring) - corridor <= set(track.jobs)  # its own ring stays
    adopted = {j.tile: j.state for j in flight.jobs if j.tile in shared}
    assert set(adopted.values()) <= {"staged", "swapped"}, adopted  # built once


def test_the_share_routes_adopts_and_refuses():
    share = BuildShare()
    tile = (53, -63)
    assert share.take("track", tile, "drape") == "start"
    assert share.take("track", (1, 1), "drape") == "start"
    assert share.others_running("flight") == 2
    assert share.take("flight", tile, "full") == "busy"   # the drape first
    assert share.take("flight", tile, "drape") == "adopted"
    assert share.poll("track") == [(tile, None)]
    share.finish(tile, True)
    assert share.poll("flight") == [(tile, True)] and share.poll("track") == []
    assert share.take("track", tile, "drape") == "busy"   # lower rank
    share.finish((1, 1), True)                            # built by track
    assert share.poll("track") == [((1, 1), True)]
    assert share.take("flight", (1, 1), "drape") == "adopted"
    assert share.poll("flight") == [((1, 1), True)]       # at once
    assert share.take("flight", (2, 2), "drape") == "start"
    share.finish((2, 2), False)
    assert share.owner_of((2, 2)) is None                 # may be tried again
    share.claim("flight", [(5, 5)])
    assert share.claimed("track", (5, 5)) and not share.claimed("flight", (5, 5))
    share.publish("flight", 2, 1)
    assert share.free_for("track", 4, 0) == 1             # min(4, 2) - 1
    share.take("flight", (6, 6), "drape")
    assert share.free_for("track", 4, 0) == 0
    share.leave("flight")
    assert share.free_for("track", 4, 1) == 3 and not share.claimed("track", (5, 5))
