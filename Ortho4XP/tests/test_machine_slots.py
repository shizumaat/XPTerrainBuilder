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
    (18, 128.0, 100.0, 16),    # the owner's machine: cores - 2 bind
    (18, 128.0, 40.0, 6),      # same machine, busy: (40 - 19.2) // 3
    (32, 64.0, 40.0, 10),      # memory binds: (40 - 9.6) // 3
    (8, 16.0, 6.0, 1),         # no room: never below one
    (4, 8.0, 1.0, 1),
    (2, 64.0, 60.0, 1),        # two cores: both reserved, still one
])
def test_capacity_is_cores_and_available_memory(cores, total, avail, want):
    assert SLOTS.capacity(cores, total, avail) == want


def test_headroom_is_the_larger_of_fraction_and_floor():
    b = dict(SLOTS.BUDGET, worker_gb=1.0)
    assert SLOTS.capacity(99, 100.0, 50.0, b) == 35      # 15 GB kept
    assert SLOTS.capacity(99, 10.0, 12.0, b) == 4        # the 8 GB floor kept


@pytest.fixture
def session(tmp_path, monkeypatch, request):
    gated = "free_gb" in request.fixturenames       # the gate is under test
    def make(cap):
        d = tmp_path / f"slots{cap}"
        d.mkdir()
        monkeypatch.setenv(SLOTS.ENV_DIR, str(d))
        monkeypatch.setenv(SLOTS.ENV_CAPACITY, str(cap))
        # the runner's free memory is not under test (``free_gb`` pins it)
        if not gated:
            monkeypatch.setenv(SLOTS.ENV_UNGATED, "1")
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


# ── #1225, second report: the live gate, the step slot, priority, and
#    worker processes started only after their slot ──────────────────────

@pytest.fixture
def free_gb(monkeypatch):
    """Pin the machine at 128 GB with ``free_gb(x)`` GB free right now —
    the live gate armed."""
    monkeypatch.delenv(SLOTS.ENV_UNGATED, raising=False)
    monkeypatch.setattr(SLOTS._PU, "machine_memory_gigabytes", lambda: 128.0)

    def set_free(x):
        monkeypatch.setattr(SLOTS._PU, "machine_available_memory_gigabytes",
                            lambda: x)
    set_free(100.0)
    return set_free


def test_memory_pressure_holds_new_grants_until_it_recovers(session, free_gb):
    session(4)
    first = SLOTS.try_take(1)
    assert first.count == 1
    free_gb(20.0)                          # below 19.2 GB headroom + one worker
    assert not SLOTS.memory_admits()
    assert SLOTS.try_take(2).count == 0    # held: something else is running
    first.release()
    with SLOTS.try_take(3) as idle:        # nothing runs: exactly one starts
        assert idle.count == 1
    free_gb(60.0)                          # recovered
    with SLOTS.try_take(3) as back:
        assert back.count == 3


def test_a_step_holds_one_slot_and_lends_it_while_it_waits(session, free_gb):
    session(1)
    with SLOTS.step() as held:
        assert held.count == 1 and SLOTS.try_take(1).count == 0
        with SLOTS.step():                 # nested: covered by the outer
            assert SLOTS.try_take(1).count == 0
        with SLOTS.lend():                 # its airports may take it
            with SLOTS.try_take(1) as airport:
                assert airport.count == 1
        assert held.count == 1 and SLOTS.try_take(1).count == 0
    assert SLOTS.try_take(1).count == 1


def test_a_cancelled_wait_gives_up_with_nothing(session, free_gb):
    session(1)
    with SLOTS.try_take(1):
        got = SLOTS.take(1, poll_s=0.01, give_up=lambda: True)
        assert got.count == 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX nice")
def test_lower_priority_is_inherited_below_normal():
    env = {k: v for k, v in os.environ.items() if k != SLOTS.ENV_PRIORITY}
    out = subprocess.run(
        [sys.executable, "-c",
         "import os, sys, subprocess; sys.path.insert(0, sys.argv[1]);"
         "import O4_Machine_Slots as S; S.lower_priority();"
         "print(subprocess.run([sys.executable, '-c', 'import os;"
         "print(os.getpriority(os.PRIO_PROCESS, 0))'],"
         " capture_output=True, text=True).stdout.strip())",
         str(Path(SLOTS.__file__).parent)],
        capture_output=True, text=True, env=env, timeout=60)
    assert int(out.stdout.strip()) >= SLOTS.NICE


def test_workers_start_without_a_qos_clamp():
    """RULINGS 2026-10-22k: no ``taskpolicy -c utility`` clamp (it kept
    workers on the efficiency cores); nice 10 alone lowers them."""
    par = Path(SLOTS.__file__).parent / "o4_engine" / "parallel.py"
    assert not hasattr(SLOTS, "qos_command")
    assert "taskpolicy" not in par.read_text(encoding="utf-8")


def _hold(seconds):
    time.sleep(seconds)
    return os.getpid()


def test_a_worker_process_starts_only_after_its_slot(session, free_gb):
    import concurrent.futures as cf
    import multiprocessing as mp

    from auto_patch import slot_gated_pool as GATED

    session(2)
    outside = SLOTS.try_take(1)            # another tile holds one slot
    ctx = mp.get_context("spawn")
    live, peak, pids = [0], [0], []

    def start(task):
        assert SLOTS.try_take(1).count == 0   # the budget is full while it runs
        live[0] += 1
        peak[0] = max(peak[0], live[0])
        ex = cf.ProcessPoolExecutor(max_workers=1, mp_context=ctx)
        return ex, ex.submit(_hold, 0.2)

    def teardown(ex, fut, task):
        ex.shutdown(wait=True)
        live[0] -= 1

    waited = []
    threading.Timer(0.5, outside.release).start()
    GATED.run(range(5), width=4, start=start, teardown=teardown,
              on_done=lambda t, f: pids.append(f.result()),
              on_wait=lambda: waited.append(1), poll_s=0.05)
    assert len(pids) == 5 and len(set(pids)) == 5      # one process each
    assert peak[0] <= 2                    # never more than the free slots
    assert SLOTS.try_take(2).count == 2    # every slot came back


def test_tile_children_and_compute_never_exceed_the_budget(session, free_gb):
    from types import SimpleNamespace

    from o4_engine import parallel

    session(3)
    tiles = [(lat, lon) for lat in range(-60, 0) for lon in range(-180, -130)]
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        tiles, "P", 16, "", (True, False, False), 18)
    assert run._slots == 3                 # 3,000 queued, 3 children at most
    assert parallel.compute_class_limit(18) <= 3
    assert len(run._queue) == 3000


def test_the_driver_starts_each_airport_worker_after_its_slot(session, free_gb,
                                                              monkeypatch):
    """The tile driver's parallel path end to end: three airports, two
    slots, one single-use worker each; every airport keeps its name (these
    fail at once — no airport data) and every slot comes back."""
    from auto_patch import config as CFG
    from auto_patch import driver as D

    session(2)
    monkeypatch.setattr(CFG, "PARALLEL_AIRPORTS", True)
    tasks = [{"icao": "ZZ%02d" % k} for k in range(3)]
    reported = []
    results = D._run_airport_builds(tasks, None, reported.append)
    assert sorted(r["icao"] for r in results) == ["ZZ00", "ZZ01", "ZZ02"]
    assert not any(r["ok"] for r in results) and len(reported) == 3
    assert SLOTS.try_take(2).count == 2


def test_an_ungated_session_keeps_its_capacity_under_pressure(session, free_gb,
                                                               monkeypatch):
    """The pool self-check's own session (a small CI runner is always
    below the headroom) — the real build never sets the variable."""
    session(4)
    free_gb(4.0)
    assert SLOTS.try_take(4).count == 1
    monkeypatch.setenv(SLOTS.ENV_UNGATED, "1")
    with SLOTS.try_take(4) as all_four:
        assert all_four.count == 4
