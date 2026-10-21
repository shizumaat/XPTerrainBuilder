"""The machine worker budget (issue #1225): one slot pool per engine session,
shared by every tile, airport process and work pool, sized from cores AND
available memory.  Synthetic machine numbers; real OS locks."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import O4_Machine_Slots as SLOTS  # noqa: E402
from auto_patch_v2.airport import pool as POOL  # noqa: E402


@pytest.mark.parametrize("cores,total,avail,want", [
    (18, 128.0, 100.0, 18),    # the owner's machine: cores bind, memory has room
    (18, 128.0, 40.0, 6),      # same machine, busy: (40 - 19.2) // 3
    (32, 64.0, 40.0, 10),      # memory binds: (40 - 9.6) // 3
    (8, 16.0, 6.0, 1),         # no room: never below one
    (4, 8.0, 1.0, 1),
])
def test_capacity_is_cores_and_available_memory(cores, total, avail, want):
    assert SLOTS.capacity(cores, total, avail) == want


def test_headroom_is_the_larger_of_fraction_and_floor():
    b = dict(SLOTS.BUDGET, worker_gb=1.0)
    assert SLOTS.capacity(99, 100.0, 50.0, b) == 35      # 15 GB kept
    assert SLOTS.capacity(99, 10.0, 10.0, b) == 6        # the 4 GB floor kept


@pytest.fixture
def session(tmp_path, monkeypatch):
    def make(cap):
        d = tmp_path / f"slots{cap}"
        d.mkdir()
        monkeypatch.setenv(SLOTS.ENV_DIR, str(d))
        monkeypatch.setenv(SLOTS.ENV_CAPACITY, str(cap))
        return d
    return make


def test_slots_never_exceed_capacity_and_come_back(session):
    session(3)
    a = SLOTS.try_take(5)
    assert a.count == 3
    assert SLOTS.try_take(1).count == 0
    a.release()
    with SLOTS.try_take(2) as b:
        assert b.count == 2
        assert SLOTS.try_take(9).count == 1


def test_a_session_is_opened_and_published_when_none_is_inherited(monkeypatch):
    monkeypatch.delenv(SLOTS.ENV_DIR, raising=False)
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "4")
    path, cap = SLOTS.ensure_session()
    assert cap == 4 and os.path.isdir(path)
    assert os.environ[SLOTS.ENV_DIR] == path
    assert SLOTS.ensure_session() == (path, 4)            # the same session after


def test_take_queues_until_a_holder_releases(session):
    session(1)
    first = SLOTS.try_take(1)
    waited = []
    threading.Timer(0.3, first.release).start()
    t0 = time.monotonic()
    with SLOTS.take(1, poll_s=0.05, on_wait=lambda: waited.append(1)) as got:
        assert got.count == 1
    assert waited == [1] and time.monotonic() - t0 >= 0.25


def test_take_never_asks_for_more_than_the_capacity(session):
    session(2)
    with SLOTS.take(10, poll_s=0.01) as got:
        assert got.count == 2


def test_a_slot_held_by_another_process_counts_and_dies_with_it(session):
    session(2)
    child = subprocess.Popen(
        [sys.executable, "-c",
         "import sys, time; sys.path.insert(0, sys.argv[1]);"
         "import O4_Machine_Slots as S; h = S.try_take(1);"
         "print(h.count, flush=True); time.sleep(60)",
         str(Path(SLOTS.__file__).parent)],
        stdout=subprocess.PIPE, text=True, encoding="utf-8", env=dict(os.environ))
    try:
        assert child.stdout.readline().strip() == "1"
        assert SLOTS.try_take(2).count == 1
    finally:
        child.kill()
        child.wait(10)
        child.stdout.close()
    with SLOTS.try_take(2) as after:                      # the system released it
        assert after.count == 2


@pytest.fixture
def derived_budget():
    POOL.configure(None)
    yield
    POOL.configure(1)                                     # the suite's pin


def test_a_pool_takes_what_is_free_and_gives_it_back(session, derived_budget):
    session(3)
    wp = POOL.WorkPool(workers=8)
    try:
        assert wp._start()
        assert (wp.workers, wp.bound) == (3, "machine")
        assert SLOTS.try_take(1).count == 0
    finally:
        wp.close()
    assert SLOTS.try_take(3).count == 3


def test_a_pool_without_two_free_slots_runs_serially(session, derived_budget):
    session(2)
    hold = SLOTS.try_take(1)
    wp = POOL.WorkPool(workers=4)
    assert not wp._start()
    assert (wp.workers, wp.bound, wp.parallel) == (1, "machine", False)
    assert wp.begin(abs, [1, 2]) is None                  # the caller runs it serially
    wp.close()
    hold.release()


def test_a_pinned_budget_is_verbatim(session):
    session(1)
    POOL.configure(3)
    try:
        wp = POOL.WorkPool()
        assert wp._take_slots() and wp.workers == 3
    finally:
        POOL.configure(1)
