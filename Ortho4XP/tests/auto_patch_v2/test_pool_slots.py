"""#2267: a work pool's workers run only on the machine slots it holds,
idle slots go back, a waiting step is served down to the pool's floor,
and the answers are the serial ones.  Stubbed waiters and a stubbed
clock; real OS locks; no wall-time assert."""
from __future__ import annotations

import concurrent.futures as cf
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import O4_Machine_Slots as SLOTS  # noqa: E402
from auto_patch_v2.airport import pool as POOL  # noqa: E402
from auto_patch_v2.airport import pool_slots as PS  # noqa: E402


@pytest.fixture
def session(tmp_path, monkeypatch):
    def make(cap):
        d = tmp_path / f"slots{cap}"
        d.mkdir()
        monkeypatch.setenv(SLOTS.ENV_DIR, str(d))
        monkeypatch.setenv(SLOTS.ENV_CAPACITY, str(cap))
        monkeypatch.setenv(SLOTS.ENV_UNGATED, "1")
        return d
    return make


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        self.t += PS.LOOK_S                 # every read is a new look
        return self.t


def _book(n, workers, waiters=lambda: 0):
    return PS.SlotBook(SLOTS.try_take(n, what="airport ZZZZ pool"), workers,
                       "airport ZZZZ pool", waiters=waiters, clock=Clock())


def test_the_floor_is_half_the_workers_and_never_none():
    assert [PS.yield_floor(n) for n in (1, 2, 3, 12)] == [1, 1, 1, 6]


def test_idle_slots_go_back_and_come_back(session):
    session(6)
    book = _book(4, 4)
    assert book.fit(busy=1, queued=0) == 0          # the map's tail
    assert book.count == 1 and book.idled == 3
    assert SLOTS.try_take(6).count == 5             # the others are free
    assert book.fit(busy=0, queued=9) == 4          # the next map takes them again
    assert book.count == 4
    book.release()
    assert SLOTS.try_take(6).count == 6


def test_a_waiter_is_served_as_tasks_finish_down_to_the_floor(session):
    session(4)
    waiting = [3]
    book = _book(4, 4, waiters=lambda: waiting[0])
    assert book.fit(busy=4, queued=10) == 0         # every worker busy: none is shed
    assert book.count == 4
    assert book.fit(busy=3, queued=10) == 0         # one finished: its slot is lent
    assert book.count == 3 and book.yielded == 1
    assert book.fit(busy=2, queued=10) == 0
    assert book.count == 2                          # the floor: half its workers
    assert book.fit(busy=1, queued=10) == 1         # kept, and used
    assert book.count == 2
    waiting[0] = 0                                  # the steps got their slots
    SLOTS.try_take(4).release()                     # (and gave them back)
    assert book.fit(busy=1, queued=10) == 3
    assert book.count == 4
    book.release()


class FakeJobRun:
    """Futures the test completes by hand, and the most ever running."""

    def __init__(self):
        self.futs, self.peak = [], 0

    def submit(self, span):
        f = cf.Future()
        f.set_running_or_notify_cancel()
        self.futs.append(f)
        self.peak = max(self.peak, self.running())
        return f

    def running(self):
        return sum(1 for f in self.futs if not f.done())

    def finish_one(self):
        next(f for f in self.futs if not f.done()).set_result(None)


def test_the_feeder_never_runs_more_tasks_than_slots(session):
    session(8)
    book = _book(3, 3)
    feeder = PS.Feeder(book)
    run = FakeJobRun()
    job = PS.Job([(i, i + 1) for i in range(10)], run.submit)
    feeder._thread = object()                       # pumped by hand here
    feeder.add(job)
    assert run.running() == 3 and len(job.queue) == 7
    for _ in range(10):
        run.finish_one()
        feeder.pump()
        assert run.running() <= book.count
    assert run.peak == 3 and not job.queue
    feeder.pump()                                   # nothing left: slots go back
    assert book.count == 0
    feeder.close()


def test_a_collecting_map_with_no_slot_runs_one_on_the_builds_own(session):
    session(2)
    book = _book(2, 2)
    book.fit(busy=0, queued=0)                      # between maps: all given back
    assert book.count == 0
    blocker = SLOTS.try_take(2)                     # the session is full
    assert blocker.count == 2
    feeder = PS.Feeder(book)
    feeder._thread = object()
    run = FakeJobRun()
    job = PS.Job([(0, 1), (1, 2)], run.submit)
    feeder.add(job)
    assert run.running() == 0                       # begin: no slot, nothing runs
    job.collecting = True
    feeder.pump()
    assert run.running() == 1                       # the build's own slot
    feeder.pump()
    assert run.running() == 1                       # and only one
    feeder.close()
    blocker.release()


def _square(state, x):
    return x * x


@pytest.fixture
def derived_budget():
    POOL.configure(None)
    yield
    POOL.configure(1)


def test_a_pool_yielding_to_a_waiter_answers_what_serial_does(session, derived_budget,
                                                              monkeypatch):
    if os.name == "posix":
        from multiprocessing import resource_tracker
        resource_tracker.ensure_running()
    session(4)
    monkeypatch.setattr(SLOTS, "slot_waiters", lambda: 2)  # two steps wait
    tasks = list(range(40))
    with POOL.WorkPool(workers=4) as wp:
        got = wp.try_map(_square, tasks, weights=[t % 7 for t in tasks], what="sq")
        assert got == [_square(None, t) for t in tasks]     # the serial answer
        assert wp.workers == 4 and wp._held.yielded >= 2    # down to the floor
        assert wp._held.count == 0                          # and none kept after
    assert SLOTS.try_take(4).count == 4
