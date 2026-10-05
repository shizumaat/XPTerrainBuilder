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
    assert any("a worker died" in s for s in said)


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
    assert P.budget() == 1                        # under pytest: serial
    monkeypatch.delitem(P.sys.modules, "pytest")
    monkeypatch.setattr(P.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(P, "_share", [1])
    monkeypatch.setattr(P, "_explicit", [None])
    assert P.budget() == 12
    P.set_share(3)
    assert P.budget() == 4                        # three airports share it
    P.set_share(50)
    assert P.budget() == 1
    P.configure(5)
    assert P.budget() == 5 and P.WorkPool().workers == 5
    P.configure(None)
    assert P.budget() == 1


def test_the_pulse_is_restored():
    from auto_patch_v2.model import pulse
    pulse.tick("outer", 1, 2, "x")
    with P.WorkPool(_setup, (0,), workers=2, out=lambda s: None) as p:
        p.try_map(_square, range(4), what="inner", unit="tasks")
    assert pulse.current() == ("outer", 1, 2, "x")
    pulse.clear()
