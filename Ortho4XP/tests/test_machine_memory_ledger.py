"""Twins for the machine memory ledger (incident 2026-11-17 ~22:46Z: four
harness builds and an app build each sized their budget from the same free
memory, then grew into it).  Synthetic free memory, a fake process table,
fake sessions; real OS locks and one real killed holder."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import O4_Machine_Memory as MEMORY  # noqa: E402
import O4_Machine_Slots as SLOTS  # noqa: E402
import O4_Parallel_Utils as PU  # noqa: E402

GIB = 1024 * 1024                          # KiB per GiB
HEADROOM = 19.2                            # 15 % of the 128 GB machine
XPLANE_EXE = "/Applications/X-Plane 12/X-Plane.app/Contents/MacOS/X-Plane"


@pytest.fixture
def machine(monkeypatch, tmp_path):
    """A 128 GB machine with ``machine.free`` GB free, this process at
    ``machine.rss[pid]`` GB, and whatever ``machine.extra`` rows add."""
    state = type("Machine", (), {})()
    state.free, state.rss, state.extra = 100.0, {os.getpid(): 1.0}, []
    state.pressure = "normal"
    monkeypatch.delenv(SLOTS.ENV_UNGATED, raising=False)
    monkeypatch.setenv(MEMORY.ENV_DIR, str(tmp_path / "ledger"))
    monkeypatch.setitem(MEMORY.BUDGET, "snapshot_s", 0.0)
    monkeypatch.setitem(MEMORY.BUDGET, "table_s", 0.0)
    monkeypatch.setattr(MEMORY, "XPLANE_NAMES",
                        frozenset({"X-Plane", "X-Plane-x86_64"}))
    monkeypatch.setattr(PU, "machine_memory_gigabytes", lambda: 128.0)
    monkeypatch.setattr(PU, "machine_available_memory_gigabytes",
                        lambda: state.free)
    monkeypatch.setattr(PU, "machine_memory_pressure",
                        lambda: state.pressure)
    monkeypatch.setattr(MEMORY, "_read_process_table", lambda: [
        (pid, 1, int(gb * GIB), "python") for pid, gb in state.rss.items()
    ] + list(state.extra))
    return state


def _as(monkeypatch, session, role):
    """Become ``session`` of ``role`` (the env a session's processes share)."""
    monkeypatch.setenv(MEMORY.ENV_SESSION, session)
    monkeypatch.setenv(MEMORY.ENV_ROLE, role)
    monkeypatch.setenv(MEMORY.ENV_LABEL, "%s %s" % (role, session))


def test_a_second_session_waits_for_the_first_ones_reservations(
        machine, monkeypatch, tmp_path):
    """THE INCIDENT: both sessions read 60 GB free.  Before the ledger the
    second admitted its step too; now the first's 35 GB still to grow is
    counted, and the second waits."""
    machine.free = 60.0
    _as(monkeypatch, "A", "lane")
    held = MEMORY.reserve(35.0, "tile +30+031 vector step")
    _as(monkeypatch, "B", "lane")
    assert MEMORY.admits(8.0, HEADROOM, snap=MEMORY.Snapshot(free_gb=60.0)).ok
    verdict = SLOTS.machine_verdict(8.0)                 # 60-8-19.2-35 < 0
    assert not verdict.ok and verdict.contended
    assert "lane A 35 GB" in verdict.text
    held.release()
    assert SLOTS.machine_verdict(8.0).ok                 # A let go


def test_the_idle_rule_yields_to_another_sessions_reservation(
        machine, monkeypatch, tmp_path):
    machine.free = 30.0
    _as(monkeypatch, "A", "lane")
    held = MEMORY.reserve(20.0, "A step")
    _as(monkeypatch, "B", "lane")
    (tmp_path / "slotsB").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slotsB"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "4")
    assert SLOTS.try_take(1).count == 0                  # B holds none: waits
    got = SLOTS.take(1, poll_s=0.01, give_up=lambda: True)
    assert got.count == 0
    held.release()
    with SLOTS.try_take(1) as one:                       # nobody else: runs
        assert one.count == 1


def test_growth_already_made_is_not_counted_twice(machine, monkeypatch):
    """A reservation's process tree that has grown into it holds that
    memory already — it is out of ``free``, not still to come."""
    machine.free = 45.0
    _as(monkeypatch, "A", "lane")
    held = MEMORY.reserve(30.0, "A step")
    machine.rss[os.getpid()] += 20.0                    # 20 of 30 grown
    _as(monkeypatch, "B", "lane")
    snap = MEMORY.snapshot()
    assert snap.outstanding_gb == pytest.approx(10.0)
    assert MEMORY.admits(8.0, HEADROOM).ok              # 45-8-19.2-10 > 0
    held.release()


def test_a_nested_process_with_its_own_record_counts_once(machine,
                                                          monkeypatch):
    """A step's child that holds its own record (an airport's pool) grows
    into ITS record, not also into the step's."""
    parent, child = os.getpid(), 999_001
    machine.rss[child] = 1.0
    machine.extra = []
    monkeypatch.setattr(MEMORY, "_read_process_table", lambda: [
        (parent, 1, int(machine.rss[parent] * GIB), "python"),
        (child, parent, int(machine.rss[child] * GIB), "python")])
    _as(monkeypatch, "A", "app")
    step = MEMORY.reserve(10.0, "vector step")
    pool = MEMORY.reserve(6.0, "airport pool", pid=child)
    machine.rss[child] += 6.0                            # the pool grew
    snap = MEMORY.snapshot()
    assert snap.outstanding_gb == pytest.approx(10.0)    # step: none grown
    step.release()
    pool.release()


def test_a_nested_root_is_its_parents_process(machine, monkeypatch):
    """Owner 2026-11-18: an airport build A holds a slot its parent P
    booked for it (3 GB) and books its pool's workers itself.  P's record
    counts A's own memory, A's record only its workers — before, P's slot
    lost sight of A once A's pool booked, and stayed 3 GB outstanding."""
    parent, build, w1, w2 = os.getpid(), 999_101, 999_102, 999_103
    rss = {parent: 1.0, build: 0.2, w1: 0.0, w2: 0.0}
    monkeypatch.setattr(MEMORY, "_read_process_table", lambda: [
        (parent, 1, int(rss[parent] * GIB), "python"),
        (build, parent, int(rss[build] * GIB), "python")] + [
        (w, build, int(rss[w] * GIB), "python") for w in (w1, w2)
        if rss[w] > 0.0])
    _as(monkeypatch, "A", "app")
    slot = MEMORY.reserve(3.0, "an airport build")       # P, for A
    pool = MEMORY.reserve(6.0, "2 workers", pid=build)   # A, for W1, W2
    rss[build] += 2.5                                    # A grew into its slot
    rss[w1] = rss[w2] = 1.5                              # workers at work
    snap = MEMORY.snapshot()
    assert snap.outstanding_gb == pytest.approx((3.0 - 2.5) + (6.0 - 3.0))
    pool.release()
    slot.release()


def test_a_settled_pool_books_what_its_workers_measured(machine, monkeypatch,
                                                         tmp_path):
    """A pool's slots book the flat per-worker guess until its workers are
    measured; then each keeps what the largest worker held (x margin)."""
    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "16")
    _as(monkeypatch, "A", "app")
    with SLOTS.try_take(16) as held:
        assert held.count == 16
        assert MEMORY.snapshot().outstanding_gb == pytest.approx(48.0)
        held.settle(1.5 * 1.25)
        assert MEMORY.snapshot().outstanding_gb == pytest.approx(30.0)
        held.settle(2.9)                                 # never raised back
        assert MEMORY.snapshot().outstanding_gb == pytest.approx(30.0)
        body = [MEMORY._read_body(os.path.join(MEMORY.ledger_dir(), n))
                for n in os.listdir(MEMORY.ledger_dir())
                if n.startswith("r-")]
        assert [b["gb"] for b in body] == [30.0]         # parses, padded
    assert MEMORY.snapshot().outstanding_gb == 0.0


def test_pressure_warn_stops_lanes_not_the_app_with_room(machine,
                                                         monkeypatch):
    """Owner 2026-11-18: at the kernel's ``warn`` the app's own run goes on
    while free memory covers it (its wait named the pressure although
    room, not the pressure, held it); a lane starts nothing new; at
    ``critical`` nobody does."""
    machine.free = 80.0
    machine.pressure = "warn"
    _as(monkeypatch, "APP", "app")
    verdict = MEMORY.admits(9.0, HEADROOM)
    assert verdict.ok and "pressure" not in verdict.text
    _as(monkeypatch, "L", "lane")
    verdict = MEMORY.admits(9.0, HEADROOM)
    assert not verdict.ok and verdict.contended
    assert "memory pressure warn" in verdict.text
    machine.pressure = "critical"
    _as(monkeypatch, "APP", "app")
    assert not MEMORY.admits(1.0, HEADROOM).ok


def test_a_wait_says_what_builds_booked_and_do_not_use(machine, monkeypatch):
    machine.free = 60.0
    _as(monkeypatch, "APP", "app")
    held = MEMORY.reserve(45.0, "pool")
    verdict = MEMORY.admits(3.0, HEADROOM)
    assert not verdict.ok
    assert "45 GB booked by builds and not yet in use" in verdict.text
    held.release()


def test_x_plane_shrinks_admission(machine, monkeypatch):
    """X-Plane holds 10 GB and is expected to reach 32 (+4 margin): 26 GB
    more are kept for it while it runs."""
    machine.free = 70.0
    _as(monkeypatch, "L", "lane")
    assert MEMORY.admits(30.0, HEADROOM).ok              # 70-30-19.2 > 0
    machine.extra = [(4242, 1, 10 * GIB, XPLANE_EXE)]
    verdict = MEMORY.admits(30.0, HEADROOM)
    assert not verdict.ok and verdict.contended
    assert "X-Plane 10 GB" in verdict.text
    assert MEMORY.admits(15.0, HEADROOM).ok              # what still fits
    # An idle lane does not override X-Plane; an idle app step does.
    assert not MEMORY.admits(30.0, HEADROOM, idle=True).ok
    _as(monkeypatch, "P", "app")
    assert MEMORY.admits(30.0, HEADROOM, idle=True).ok


def test_an_app_session_preempts_lane_admission(machine, monkeypatch):
    """The app holds a 16 GB step: a lane step must leave room for the
    app's next one, where the app's own next step need not."""
    machine.free = 55.0
    _as(monkeypatch, "APP", "app")
    held = MEMORY.reserve(16.0, "tile +30+031 mesh step")
    _as(monkeypatch, "L", "lane")
    verdict = MEMORY.admits(8.0, HEADROOM)               # 55-8-19.2-16-16 < 0
    assert not verdict.ok and verdict.contended
    assert "app APP 16 GB" in verdict.text
    _as(monkeypatch, "APP", "app")
    assert MEMORY.admits(8.0, HEADROOM).ok               # 55-8-19.2-16 > 0
    held.release()


def test_a_waiting_app_step_holds_the_lanes_back(machine, monkeypatch):
    """The app waits for 30 GB (nothing reserved yet): its WANT mark keeps
    the lanes from taking the memory it waits for."""
    machine.free = 55.0
    _as(monkeypatch, "L", "lane")
    assert MEMORY.admits(8.0, HEADROOM).ok
    _as(monkeypatch, "APP", "app")
    refused = MEMORY.Verdict(ok=False, text="holding: lane L 30 GB")
    MEMORY.note_wait("tile +30+031's vector step", refused, 30.0,
                     emit=lambda line: None)
    _as(monkeypatch, "L", "lane")
    verdict = MEMORY.admits(8.0, HEADROOM)               # 55-8-19.2-30 < 0
    assert not verdict.ok and "an app step waiting" in verdict.text
    monkeypatch.setitem(MEMORY.BUDGET, "want_ttl_s", -1.0)
    assert MEMORY.admits(8.0, HEADROOM).ok               # the mark expired


def test_pressure_pauses_the_lowest_priority_first(machine, monkeypatch):
    machine.pressure = "warn"
    _as(monkeypatch, "L", "lane")
    assert not MEMORY.admits(1.0, HEADROOM).ok
    assert not MEMORY.admits(1.0, HEADROOM, idle=True).ok
    _as(monkeypatch, "APP", "app")
    assert MEMORY.admits(1.0, HEADROOM).ok
    machine.pressure = "critical"
    assert not MEMORY.admits(1.0, HEADROOM, idle=True).ok


def test_a_wait_names_who_holds_memory(machine, monkeypatch):
    machine.free = 40.0
    machine.extra = [(4242, 1, 24 * GIB, XPLANE_EXE)]
    _as(monkeypatch, "APP", "app")
    monkeypatch.setenv(MEMORY.ENV_LABEL, "app build")
    app = MEMORY.reserve(30.0, "mesh")
    _as(monkeypatch, "X", "lane")
    monkeypatch.setenv(MEMORY.ENV_LABEL, "lane lessa5")
    lane = MEMORY.reserve(18.0, "vector")
    _as(monkeypatch, "Y", "lane")
    lines = []
    MEMORY.note_wait("step 2 mesh", MEMORY.admits(8.0, HEADROOM),
                     emit=lines.append)
    MEMORY.note_wait("step 2 mesh", MEMORY.admits(8.0, HEADROOM),
                     emit=lines.append)                  # same holders: once
    assert len(lines) == 1
    assert ("holding: X-Plane 24 GB, app build 30 GB, lane lessa5 18 GB"
            in lines[0])
    app.release()
    lane.release()


_HOLDER = """
import os, sys, time
sys.path.insert(0, sys.argv[1])
import O4_Machine_Memory as M
held = M.reserve(40.0, "killed step")
print("held", flush=True)
time.sleep(600)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX kill -9")
def test_a_killed_holder_releases(machine, monkeypatch, tmp_path):
    """A holder killed outright (no cleanup ran) holds nothing: the system
    dropped its lock, and the next reader removes its record."""
    monkeypatch.setitem(MEMORY.BUDGET, "fresh_s", 0.0)
    env = dict(os.environ, **{MEMORY.ENV_SESSION: "K",
                              MEMORY.ENV_ROLE: "lane"})
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(Path(MEMORY.__file__).parent)],
        stdout=subprocess.PIPE, text=True, env=env)
    try:
        assert holder.stdout.readline().strip() == "held"
        snap = MEMORY.snapshot()
        assert "K" in snap.sessions
        assert snap.outstanding_gb == pytest.approx(40.0)   # pid not in table
    finally:
        holder.send_signal(signal.SIGKILL)
        holder.wait(timeout=30)
        holder.stdout.close()
    snap = MEMORY.snapshot()
    assert snap.sessions == {} and snap.outstanding_gb == 0.0
    assert not [n for n in os.listdir(MEMORY.ledger_dir())
                if n.startswith("r-")]


def test_slot_grants_reserve_and_release_on_the_ledger(machine, monkeypatch,
                                                       tmp_path):
    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "8")
    machine.free = 19.2 + 3.0 * 3 + 0.5                  # room for 3 workers
    with SLOTS.try_take(5) as held:
        assert held.count == 3                           # what fits, not 5
        assert MEMORY.snapshot().outstanding_gb == pytest.approx(9.0)
    assert MEMORY.snapshot().outstanding_gb == 0.0
    with SLOTS.step(gb=0.0) as step:                     # parent reserved it
        assert step.count == 1
        assert MEMORY.snapshot().outstanding_gb == 0.0


def test_the_scheduler_holds_its_first_step_for_another_build(
        machine, monkeypatch, tmp_path):
    """A parallel run's FIRST step used to start unconditionally ("one
    step always runs"); with another build's reservation filling the
    machine it waits, its row naming the holder, and starts once it goes."""
    from types import SimpleNamespace

    from o4_engine import parallel
    from test_step_memory_admission import _Child

    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "16")
    monkeypatch.delenv("O4_CACHE_AWARE_ADMISSION", raising=False)
    machine.free = 40.0
    _as(monkeypatch, "OTHER", "app")
    other = MEMORY.reserve(30.0, "+47+012 vector step")
    _as(monkeypatch, "RUN", "lane")
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        [(10, 10)], "P", 16, "", (True, False, False), 3)
    child = _Child()
    with run._lock:
        assert run._start_new_tile_locked(child) is False
        wait = run._memory_waits.snapshot()[((10, 10), "vector")]
        assert wait.reason == "machine" and "app OTHER 30 GB" in wait.behind
    other.release()
    with run._lock:
        assert run._start_new_tile_locked(child) is True
        assert MEMORY.snapshot().outstanding_gb == pytest.approx(
            parallel.step_memory.VECTOR_NO_AIRPORT_GB)
        run._release_step_resources_locked(child)
    assert MEMORY.snapshot().outstanding_gb == 0.0
