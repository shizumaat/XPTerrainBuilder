"""#2256: a flight is ready only when the departure's imagery has landed.

Headless: the follow job over a fake X-Plane with a stub lander, the
schedule's rows and the session's request classes in a temporary folder.
"""
from __future__ import annotations

import O4_Flight_Schedule as S
import O4_Imagery_Follow_Reach as FOLLOW_REACH
import O4_Imagery_Spawn as SPAWN
import O4_Imagery_Tier_Plan as PLAN
import O4_Machine_Slots as SLOTS
import pytest
import test_imagery_follow as P3B
import test_imagery_spawn as SPAWN_TESTS
from o4_engine.imagery_follow_core import STALL_S, DepartureCore
from test_imagery_follow import FakeLander, _fly, _job, _settle

xplane = P3B.xplane
FIELD = SPAWN_TESTS.FIELD


def _core_row(core):
    facts = S.Facts(jobs=(), world_installed=True, budget_fits=True,
                    network_ok=True, prefetch_done=True, departure_core=core)
    return next(i for i in S.readiness_items(facts) if i.key == "core")


def test_the_core_is_a_row_the_flight_waits_for():
    assert "core" in S.READY_KEYS
    assert _core_row(None).state == "done"
    going = _core_row({"state": "working", "left": 5, "total": 24,
                       "eta_s": 12.0})
    assert (going.state, going.eta_s) == ("working", 12.0)
    assert "still sharpening" in going.detail and "5 of 24" in going.detail
    assert _core_row({"state": "offline", "left": 5,
                      "total": 24}).state == "blocked"
    slow = _core_row({"state": "stalled", "left": 1, "total": 24})
    assert slow.state == "working" and slow.eta_s is None
    done = _core_row({"state": "done", "left": 0, "total": 24, "failed": 2})
    assert done.state == "done" and "2 square" in done.detail


def test_the_count_comes_from_the_rows_and_says_when_it_stalls():
    rows = SPAWN_TESTS._rows()
    core = DepartureCore(*FIELD, 0.0)
    fetch_s = {1: 1.0, 2: 2.0, 3: 5.0}
    first = core.update(rows, None, set(), 1.0, fetch_s, 2)
    assert first["state"] == "working" and first["left"] == first["total"] == 71
    assert first["eta_s"] > 0
    assert core.update(rows, None, set(), 1.0 + STALL_S, fetch_s,
                       2)["state"] == "stalled"
    for row in rows.values():
        row["tier_px"] = PLAN.TIER_WIDTH[-1]
    done = core.update(rows, None, set(), 2.0 + STALL_S, fetch_s, 2)
    assert (done["state"], done["left"], done["total"]) == ("done", 0, 71)
    assert not core.holds_network(2.0 + STALL_S)


def test_a_flight_load_at_the_departure_keeps_the_plans_core():
    rows = SPAWN_TESTS._rows()
    watch = SPAWN.SpawnWatch()
    plan = watch.witness("plan", 10.0, *FIELD, rows)
    wanted = dict(plan.wants)
    key = next(iter(wanted))
    plan.note_landed(key, wanted[key], 15.0)
    assert key in plan.missed                       # no window yet
    # the load's first sample reads a camera thousands of km up
    assert watch.witness("flight_load", 20.0, *FIELD, rows,
                         agl_m=5.4e6) is None
    assert watch.episode is plan and plan.wants == wanted
    assert not plan.missed and plan.window_end == 20.0 + watch.window_s


def test_the_plan_lets_go_once_the_aircraft_has_left():
    rows = SPAWN_TESTS._rows()
    watch = SPAWN.SpawnWatch()
    plan = watch.witness("plan", 0.0, *FIELD, rows)
    assert plan.follow(rows, *SPAWN_TESTS.ELSEWHERE) == 0   # not there yet
    assert plan.witness == "plan"
    watch.witness("flight_load", 5.0, *FIELD, rows)
    plan.follow(rows, *SPAWN_TESTS.ELSEWHERE)
    assert plan.witness == "flight_load"


def test_a_reread_during_a_fetch_does_not_land_the_square_twice(
        xplane, tmp_path):
    job, _events, clock, lander, _t, _i = _job(xplane, tmp_path)
    job.open()
    positions = P3B.REPLAY["pos"][:40]

    def reread(_i):                 # each tick: rows as a reread hands them
        job._rows = {k: dict(r) for k, r in job._rows.items()}
        job._tiles = FOLLOW_REACH.by_tile(job._rows)

    _fly(job, xplane, clock, positions, each=reread)
    assert lander.calls and len(lander.calls) == len(set(lander.calls))
    job.close()


class _MissingFile(FakeLander):
    def __call__(self, row, tier):
        raise FileNotFoundError(2, "No such file or directory")


def test_a_missing_file_is_not_the_network(xplane, tmp_path):
    job, events, clock, _l, _t, _i = _job(xplane, tmp_path,
                                          lander=_MissingFile())
    job.open()
    _fly(job, xplane, clock, P3B.REPLAY["pos"][:60])
    assert job.counts["failed"] >= P3B.FOLLOW.OFFLINE_AFTER
    assert not any(e.reason.startswith("Offline") for e in events)
    job.close()


def test_the_job_counts_the_core_and_holds_other_downloads(
        xplane, tmp_path, monkeypatch):
    holds = []
    monkeypatch.setattr(SLOTS, "hold_net_for_flight",
                        lambda: holds.append(1))
    job, _events, clock, _l, _t, _i = _job(xplane, tmp_path)
    job.open()
    lat, lon = P3B.REPLAY["pos"][0][1:3]
    assert job.departure_status(lat, lon)["state"] == "working"
    clock.t = 1.0
    job.tick()
    _settle(job)
    status = job.departure_status(lat, lon)
    assert status["total"] > 0 and holds
    job.close()


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(SLOTS, "ensure_session",
                        lambda: (str(tmp_path), 4))


def test_the_flight_hold_keeps_builds_off_every_server(session):
    assert SLOTS.try_take_class("net:a.example", 1, 2).release() is None
    SLOTS.hold_net_for_flight()
    assert SLOTS.try_take_class("net:a.example", 1, 2).count == 0
    assert SLOTS.try_take_class("other", 1, 2).count == 1
    with SLOTS.net_priority():
        held = SLOTS.try_take_class("net:a.example", 1, 2)
    assert held.count == 1
    held.release()
