"""THE WORK POOL's twin (``airport/pool.py``, issue #362): answers come back
in input order whatever order the workers finish in, with 1, 2 and N
workers; no pool → ``None`` and the serial answer is the same list; a dead
worker and a stall end as a serial answer, never a hang; a task's own
error is the caller's error; the budget rules.
"""
from __future__ import annotations

import os
import time

import pytest

from auto_patch_v2.airport import frame_entry as FE
from auto_patch_v2.airport import pool as P


# ── module-level tasks (a spawned worker imports them by name) ───────────

def _setup(base):
    return {"base": base, "pid": os.getpid(), "calls": 0}


def _square(state, t):
    state["calls"] += 1
    return state["base"] + t * t


def _slow_first(state, t):
    """The EARLIER a task, the LATER it finishes."""
    time.sleep(0.02 * (8 - t) if t < 8 else 0.0)
    return (t, state["base"])


def _who(state, t):
    return (state["pid"], state["calls"], P.budget())


def _die(state, t):
    if state is not None and state.get("pid") != state.get("parent"):
        os._exit(3)
    return t + 1


def _setup_die(parent):
    return {"pid": os.getpid(), "parent": parent}


def _boom(state, t):
    if t == 3:
        raise ValueError("task three")
    return t


def _hang(state, t):
    if state is not None and state.get("pid") != state.get("parent"):
        time.sleep(60)
    return t * 2


def _rung(state, t):
    """A task whose union fell to a fallback rung ``t % 3`` times."""
    for _ in range(t % 3):
        FE._count("twin.pool", t % 2)
    return t


SERIAL = [10 + t * t for t in range(40)]


@pytest.mark.parametrize("n", [2, 3, max(2, os.cpu_count() or 2)])
def test_pooled_equals_serial(n):
    with P.WorkPool(_setup, (10,), workers=n, out=lambda s: None) as p:
        assert p.parallel
        assert p.try_map(_square, range(40)) == SERIAL
        assert p.try_map(_square, range(40), chunk=7) == SERIAL
        assert p.try_map(_square, range(40), weights=list(range(40))) == SERIAL
        assert p.try_map(_square, []) == []
        assert p.tasks_done == 120


def test_one_worker_is_serial_and_map_answers_locally():
    with P.WorkPool(_setup, (10,), workers=1) as p:
        assert not p.parallel
        assert p.try_map(_square, range(40)) is None
        assert p.map(_square, range(40), _setup(10)) == SERIAL
        assert p._ex is None                      # nothing was ever spawned


def test_input_order_under_shuffled_completion():
    with P.WorkPool(_setup, ("s",), workers=4, out=lambda s: None) as p:
        got = p.try_map(_slow_first, range(16))
    assert got == [(t, "s") for t in range(16)]


def test_begin_and_collect_are_the_map_with_the_callers_work_between():
    with P.WorkPool(_setup, (10,), workers=2, out=lambda s: None) as p:
        pending = p.begin(_square, range(40), chunk=3, what="twin", unit="tasks")
        mine = [t * t for t in range(5)]          # the caller's own work, beside
        assert pending.collect() == SERIAL and pending.collect() == SERIAL
        assert p.tasks_done == 40 and mine == [0, 1, 4, 9, 16]
    with P.WorkPool(_setup, (10,), workers=1) as p:
        assert p.begin(_square, range(40)) is None and p._ex is None


def test_a_worker_that_dies_after_begin_is_none_at_collect():
    said = []
    with P.WorkPool(_setup_die, (os.getpid(),), workers=2, out=said.append) as p:
        pending = p.begin(_die, range(6))
        assert pending is None or pending.collect() is None
        assert p.fell_back and not p.parallel and "FELL BACK" in said[0]


def test_state_is_built_once_per_worker_and_workers_never_nest():
    with P.WorkPool(_setup, (0,), workers=2, out=lambda s: None) as p:
        got = p.try_map(_who, range(12)) + p.try_map(_who, range(12))
    pids = {pid for pid, _c, _b in got}
    assert 1 <= len(pids) <= 2 and os.getpid() not in pids
    assert all(b == 1 for _p, _c, b in got)       # a worker's budget is 1


def test_dead_worker_falls_back_to_the_serial_answer():
    said = []
    with P.WorkPool(_setup_die, (os.getpid(),), workers=2, out=said.append) as p:
        t0 = time.monotonic()
        assert p.try_map(_die, range(6)) is None
        assert not p.parallel and p._ex is None
        local = {"pid": os.getpid(), "parent": os.getpid()}
        assert p.map(_die, range(6), local) == [1, 2, 3, 4, 5, 6]
        assert time.monotonic() - t0 < 60
    assert any("FELL BACK" in s and "a worker died" in s for s in said)
    r = p.report()
    assert r["fell_back"] and not r["parallel"] and "a worker died" in r["reason"]
    assert r["workers"] == 2 and r["tasks"] == 0
    assert "FELL BACK" in p.line()


def test_the_account_says_what_the_pool_did():
    """A pool that never was one, and one that answered, cannot be confused
    (lane ``parpack``: a serial run once printed the budget as its workers)."""
    one = P.WorkPool(_setup, (0,), workers=1)
    assert one.report() == {"workers": 1, "bound": "pinned", "parallel": False,
                            "fell_back": False, "reason": "budget 1", "wall_s": 0.0,
                            "tasks": 0}
    assert "serial" in one.line() and "[pool] workers 1 (bound: pinned):" in one.line()
    with P.WorkPool(_setup, (0,), workers=2, out=lambda s: None) as p:
        assert p.report()["tasks"] == 0           # opened, nothing asked yet
        p.try_map(_square, range(5))
        r = p.report()
    assert r["parallel"] and not r["fell_back"] and r["tasks"] == 5 and r["reason"] == ""
    assert "5 task(s) answered by workers" in p.line()


def test_stall_is_bounded(monkeypatch):
    monkeypatch.setattr(P, "TICK_S", 0.1)
    monkeypatch.setattr(P, "TEARDOWN_S", 0.5)
    said = []
    p = P.WorkPool(_setup_die, (os.getpid(),), workers=2, out=said.append, stall_s=1.5)
    t0 = time.monotonic()
    local = {"pid": os.getpid(), "parent": os.getpid()}
    assert p.map(_hang, range(4), local, what="hang") == [0, 2, 4, 6]
    assert time.monotonic() - t0 < 30
    assert any("no task finished" in s for s in said)


def test_a_tasks_own_error_is_the_callers():
    with P.WorkPool(_setup, (0,), workers=2, out=lambda s: None) as p:
        with pytest.raises(ValueError, match="task three"):
            p.try_map(_boom, range(6))
        assert p.try_map(_boom, [0, 1, 2]) == [0, 1, 2]   # the pool restarts


def test_budget_rules(monkeypatch):
    assert P.budget() == 1                        # the suite's conftest pins 1
    monkeypatch.setattr(P.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(P, "_share", [1])
    monkeypatch.setattr(P, "_explicit", [None])
    monkeypatch.setattr(P, "physical_ram_gb", lambda: None)   # the cores alone
    assert P.budget() == 12 and P.budget_bound() == (12, "cores")
    P.set_share(3)
    assert P.budget_bound() == (4, "share")       # three airports share it
    P.set_share(50)
    assert P.budget() == 1
    P.configure(5)
    assert P.budget() == 5 and P.WorkPool().workers == 5
    P.configure(None)
    assert P.budget() == 1                        # 12 cores // 50 airports
    P.set_share(1)
    assert P.budget() == 12                       # pytest in sys.modules is not read


def test_the_memory_bound(monkeypatch):
    """The workers are bounded by this build's share of the physical memory
    less the parent's reserve, at one allowance a worker — never below 1 —
    and the pool says which bound decided."""
    monkeypatch.setattr(P.os, "cpu_count", lambda: 16)
    monkeypatch.setattr(P, "_share", [1])
    monkeypatch.setattr(P, "_explicit", [None])
    res, per = P.PARENT_RESERVE_GB, P.WORKER_ALLOWANCE_GB
    got = {}
    for ram in (8, 16, 32, 64, 128):
        monkeypatch.setattr(P, "physical_ram_gb", lambda ram=ram: float(ram))
        got[ram] = P.budget_bound()
        want = max(1, int((ram - res) // per))
        assert got[ram] == ((want, "memory") if want < 16 else (16, "cores"))
    assert got[8] == (1, "memory") and got[128] == (16, "cores")
    assert got[8][0] <= got[16][0] <= got[32][0] <= got[64][0]
    # a machine below the reserve runs every stage on one core, and says why
    monkeypatch.setattr(P, "physical_ram_gb", lambda: 8.0)
    one = P.WorkPool(_setup, (0,))
    assert one.workers == 1 and not one.parallel and one.report()["bound"] == "memory"
    assert "(bound: memory)" in one.line() and \
        one.map(_square, range(4), {"base": 0, "calls": 0}) == [0, 1, 4, 9]
    # airports that share the machine share its memory
    monkeypatch.setattr(P, "physical_ram_gb", lambda: 64.0)
    P.set_share(2)
    assert P.budget_bound() == (min(8, int((32 - res) // per)), "memory"
                                if int((32 - res) // per) < 8 else "share")
    # a caller with fewer tasks than the budget names its own bound
    P.set_share(1)
    assert P.WorkPool(_setup, (0,), workers=2).bound == "tasks"
    # the real figure is a positive number wherever it can be read
    monkeypatch.undo()
    ram = P.physical_ram_gb()
    assert ram is None or ram > 0.5


def test_the_pulse_is_restored():
    from auto_patch_v2.model import pulse
    pulse.tick("outer", 1, 2, "x")
    with P.WorkPool(_setup, (0,), workers=2, out=lambda s: None) as p:
        p.try_map(_square, range(4), what="inner", unit="tasks")
    assert pulse.current() == ("outer", 1, 2, "x")
    pulse.clear()


def test_a_workers_union_fallback_rungs_are_counted_here():
    """The planar report's ``union_fallback_rungs`` is a per-process count
    (``frame_entry.rung_counts``): a union a worker took on this build's
    behalf must read exactly as the one this process would have taken."""
    held = FE.rung_counts()
    try:
        FE.reset_rung_counts()
        [_rung(None, t) for t in range(12)]
        want = FE.rung_counts()
        assert want == {"twin.pool": (6, 6)}
        for kw in ({}, {"chunk": 5}):
            FE.reset_rung_counts()
            FE._count("held.here", 1)
            with P.WorkPool(workers=3, out=lambda s: None) as p:
                assert p.try_map(_rung, range(12), **kw) == list(range(12))
            assert FE.rung_counts() == {"held.here": (0, 1), **want}
    finally:
        FE.reset_rung_counts()
        FE.add_rung_counts(held)


def _dump_dir(state, t):
    return FE.offender_dump_dir()


def test_the_offender_dump_is_armed_in_the_workers(tmp_path):
    held = FE.offender_dump_dir()
    try:
        for want in (str(tmp_path), ""):
            FE.set_offender_dump_dir(want)
            with P.WorkPool(workers=2, out=lambda s: None) as p:
                assert p.try_map(_dump_dir, range(4)) == [want] * 4
    finally:
        FE.set_offender_dump_dir(held)


def _first(_state, spec):
    return float(P.attach(spec)["a"][0])


def _obj(_state, spec):
    return P.shared_object(spec)


def test_a_reused_block_name_never_serves_the_earlier_arrays(monkeypatch):
    """The system may hand a later ``SharedMemory`` an earlier one's name.
    Forced here: every block of the second set is created under the first
    set's name, and each worker — still holding the first — must read the
    second."""
    import numpy as np
    real = P._shm.SharedMemory
    names: list = []

    def reuse(*a, create=False, size=0, **kw):
        if create and names:
            return real(name=names.pop(0), create=True, size=size)
        return real(*a, create=create, size=size, **kw)

    with P.WorkPool(workers=2, out=lambda s: None) as pool:
        with P.SharedArrays({"a": np.full(4, 1.0)}) as one:
            assert pool.try_map(_first, [one.spec] * 8) == [1.0] * 8
            taken = [v[0] for v in one.spec.values()]
        with P.share_object("first") as o1:
            assert pool.try_map(_obj, [o1.spec] * 8) == ["first"] * 8
            taken_o = [v[0] for v in o1.spec.values()]
        monkeypatch.setattr(P._shm, "SharedMemory", reuse)
        names[:] = taken
        with P.SharedArrays({"a": np.full(4, 2.0)}) as two:
            assert [v[0] for v in two.spec.values()] == taken
            assert P.spec_key(two.spec) != P.spec_key(one.spec)
            assert pool.try_map(_first, [two.spec] * 8) == [2.0] * 8
        names[:] = taken_o
        with P.share_object("second") as o2:
            assert [v[0] for v in o2.spec.values()] == taken_o
            assert pool.try_map(_obj, [o2.spec] * 8) == ["second"] * 8


# ── an attachment is released, never left to the collector ───────────────

def _two_sets():
    import numpy as np
    return (P.SharedArrays({"a": np.full(64, 1.0)}), P.SharedArrays({"a": np.full(64, 2.0)}))


def test_attach_closes_the_previous_block_before_it_opens_the_next():
    """The previous spec's handle is CLOSED when ``attach`` returns — the
    views are dropped first, so the close cannot raise and be swallowed."""
    one, two = _two_sets()
    try:
        assert float(P.attach(one.spec)["a"][0]) == 1.0
        held = P._ATTACHED[1][0]
        assert float(P.attach(two.spec)["a"][0]) == 2.0
        assert held.buf is None                       # closed, not waiting for GC
        assert P.attached() == [two.spec["a"][0]]
    finally:
        one.close()
        two.close()
    assert P.attached() == []


def test_the_owner_closing_releases_this_process_own_attachment():
    """One core: the process that shares a block also reads it.  Its
    attachment is closed by the owner's ``close`` — on Windows a block
    lives until its LAST handle closes (the frozen one-core arm's leak)."""
    from multiprocessing import shared_memory
    one, two = _two_sets()
    two.close()
    P.attach(one.spec)
    handle = P._ATTACHED[1][0]
    one.close()
    assert P.attached() == [] and handle.buf is None
    with pytest.raises(FileNotFoundError):
        shared_memory.SharedMemory(name=one.spec["a"][0], track=False)


def test_a_view_a_caller_keeps_holds_its_block_by_name_until_it_is_dropped():
    """A block cannot be closed under a live view: it is NAMED as still
    open, never silently forgotten, and closed once the view is gone."""
    one, two = _two_sets()
    try:
        view = P.attach(one.spec)["a"]
        P.attach(two.spec)
        assert sorted(P.attached()) == sorted([one.spec["a"][0], two.spec["a"][0]])
        assert float(view[0]) == 1.0                  # still readable
        del view
        P.detach()
        assert P.attached() == []
    finally:
        one.close()
        two.close()


# ── a worker's life is its parent's ──────────────────────────────────────

def _quick():
    pass


def test_exited_reads_the_sentinel_not_a_waitpid_someone_else_won():
    """The executor's thread and a teardown both join a worker; the loser
    of the ``waitpid`` reads the worker as ALIVE.  Forced here by reaping
    the child behind the Process object's back."""
    import multiprocessing as mp
    proc = mp.get_context("spawn").Process(target=_quick)
    proc.start()
    if hasattr(os, "waitpid") and os.name == "posix":
        os.waitpid(proc.pid, 0)                       # somebody else reaped it
    else:
        proc.join()
    assert P.exited(proc, 5.0)
    proc._popen.returncode = 0                        # so later tests' child census is clean

    class Stub:                                       # a stand-in has no sentinel
        def __init__(self, alive):
            self.alive, self.joins = alive, []

        def join(self, timeout=None):
            self.joins.append(timeout)

        def is_alive(self):
            return self.alive
    assert P.exited(Stub(False)) and not P.exited(Stub(True), 0.01)


def test_the_parent_watch_is_nothing_in_a_first_process_and_a_thread_in_a_worker():
    import threading
    before = {t.name for t in threading.enumerate()}
    P.exit_with_parent()                              # pytest's worker or the session
    import multiprocessing as mp
    if mp.parent_process() is None:
        assert {t.name for t in threading.enumerate()} == before
    with P.WorkPool(workers=2, out=lambda s: None) as p:
        assert p.try_map(_threads, range(4)) == [True] * 4
        assert len(p.pids()) == 2
    assert p.pids() == []


def _threads(_state, _t):
    import threading
    return any(t.name == "o4-parent-watch" and t.daemon for t in threading.enumerate())


def test_a_normal_close_still_joins_cleanly_and_terminates_nobody(monkeypatch):
    """With the watch in every worker a close is what it was: the workers
    exit by themselves inside the deadline, nothing is terminated, and the
    pool never fell back."""
    import multiprocessing.process as mpp
    sent: list = []
    monkeypatch.setattr(mpp.BaseProcess, "terminate", lambda self: sent.append(self.pid))
    monkeypatch.setattr(mpp.BaseProcess, "kill", lambda self: sent.append(self.pid))
    said: list = []
    pool = P.WorkPool(_setup, (3,), workers=3, out=said.append)
    assert pool.try_map(_square, range(12)) == [3 + t * t for t in range(12)]
    pids = pool.pids()
    t0 = time.monotonic()
    pool.close()
    assert time.monotonic() - t0 < P.TEARDOWN_S
    assert sent == [] and said == [] and not pool.fell_back
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
