"""Twins for #2083: the tile scheduler projects a step's memory from the
tile's own recorded peak, falls back to a conservative default without
one, keeps a share of RAM free, and holds a heavy step while LIVE free
memory is short.  Synthetic: no worker process, no build.
"""
from __future__ import annotations

import dataclasses
import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from o4_engine import parallel, step_memory, tile_time_model

TILES = [(10, 10), (11, 11), (12, 12)]


class _Child:
    """The scheduler's view of a worker: no process behind it."""

    def __init__(self):
        self.tile = None
        self.running_step = None
        self.step_class = None
        self.autopatch_pending = None
        self.step_failed = False
        self.cancelling = False
        self.retired = False
        self.prefetch_token = False
        self.step_peak_gb = 0.0

    def start_step(self, step_key, build_arguments):
        self.running_step = step_key
        return True

    def send(self, payload):
        return True


@pytest.fixture(autouse=True)
def machine(monkeypatch, tmp_path):
    """A 64 GB machine with all of it free, gates as a real build has them
    (the suite-wide ungated marker lifted: the live check is under test)."""
    import O4_Machine_Slots as SLOTS
    import O4_Parallel_Utils as PU

    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "64")
    monkeypatch.delenv(SLOTS.ENV_UNGATED, raising=False)
    monkeypatch.delenv("O4_CACHE_AWARE_ADMISSION", raising=False)
    monkeypatch.setattr(PU, "machine_core_count", lambda: 16)
    monkeypatch.setattr(PU, "machine_memory_gigabytes", lambda: 64.0)
    free = {"gb": 64.0}
    monkeypatch.setattr(PU, "machine_available_memory_gigabytes",
                        lambda: free["gb"])
    return free


def _run(budget):
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        TILES, "P", 16, "", (True, False, False), 3)
    run._memory_budget = budget
    return run


def _admit_all(run):
    """Start each tile's vector step; the children that got one."""
    started = []
    with run._lock:
        for _ in TILES:
            child = _Child()
            if run._start_new_tile_locked(child):
                started.append(child)
    return started


def _record_vector_peak(tile, gigabytes):
    before = time.time() - 1.0
    tile_time_model.record_build(tile[0], tile[1], {}, {"vector": 600.0})
    tile_time_model.record_step_peak(tile[0], tile[1], "vector", gigabytes,
                                     since=before)


def test_no_record_projects_the_conservative_default():
    run = _run(1024.0)
    assert run._step_memory_estimate((10, 10), "vector") == pytest.approx(
        step_memory.VECTOR_AIRPORT_DEFAULT_GB)
    assert run._step_memory_estimate((10, 10), "mesh") == pytest.approx(
        parallel.MESH_MEMORY_DEFAULT_GB)
    # A history that planned no airport: the OSM parse alone.
    run._airports_planned[(10, 10)] = {}
    assert run._step_memory_estimate((10, 10), "vector") == pytest.approx(
        step_memory.VECTOR_NO_AIRPORT_GB)


def test_recorded_peaks_admit_fewer():
    # No record: three 8 GB vector projections fit 30 GB.
    assert len(_admit_all(_run(30.0))) == 3
    # The same tiles after builds that peaked at 12 GB each: 13.8 GB
    # projected, but a vector step's airport builds gate themselves on
    # live memory, so it is CHARGED the 8 GB default and all three fit.
    for tile in TILES:
        _record_vector_peak(tile, 12.0)
    run = _run(30.0)
    assert run._step_memory_estimate((10, 10), "vector") == pytest.approx(
        12.0 * step_memory.RECORDED_PEAK_MARGIN)
    assert run._step_memory_charge((10, 10), "vector") == pytest.approx(
        step_memory.VECTOR_AIRPORT_DEFAULT_GB)
    assert len(_admit_all(run)) == 3
    # A step that does not gate itself is charged its whole projection.
    run._recorded_peaks[(10, 10)] = {"mesh": 12.0}
    assert run._step_memory_charge((10, 10), "mesh") == pytest.approx(
        12.0 * step_memory.RECORDED_PEAK_MARGIN)


def test_big_vector_step_does_not_starve_small_ones(machine):
    """The owner's 1.0.539 run: +43-080's vector step (recorded tree peak
    54.7 GB, 62.9 projected) runs at ~10 GB; small tiles queued behind it
    with 73 GB free must start, not wait on the projection."""
    machine["gb"] = 83.8
    big, small = (10, 10), (11, 11)
    run, _ = _events_run(65.0, [big, small, (12, 12)])
    run._recorded_peaks[big] = {"vector": 54.7}
    first, second, third = _give_children(run, 3)
    with run._lock:
        assert run._start_new_tile_locked(first) is True
        assert first.tile == big
        # Booked at its own parse: its airports book on the ledger.
        assert run._memory_in_use == pytest.approx(
            step_memory.VECTOR_NO_AIRPORT_GB)
        machine["gb"] = 73.0
        assert run._start_new_tile_locked(second) is True
        assert run._start_new_tile_locked(third) is True
        assert not run._memory_waits


def test_recorded_mesh_peak_never_undercuts_the_elevation_level():
    run = _run(1024.0)
    run._mesh_memory_estimates[(10, 10)] = 18.0      # a 1 m raster now
    run._recorded_peaks[(10, 10)] = {"mesh": 3.0}    # built at auto before
    assert run._step_memory_estimate((10, 10), "mesh") == pytest.approx(18.0)
    run._recorded_peaks[(10, 10)] = {"mesh": 30.0}
    assert run._step_memory_estimate((10, 10), "mesh") == pytest.approx(
        30.0 * step_memory.RECORDED_PEAK_MARGIN)


def test_low_live_free_memory_holds_admission(machine):
    run = _run(1024.0)
    with run._lock:
        first = _Child()
        machine["gb"] = 5.0
        # Nothing running: one step is always admitted, however low.
        assert run._start_new_tile_locked(first) is True
        # Free 15 GB, headroom 9.6 GB (15 % of 64): an 8 GB step would
        # leave 7 — it waits; the running step is untouched.
        machine["gb"] = 15.0
        second = _Child()
        assert run._start_new_tile_locked(second) is False
        assert first.running_step == "vector"
        # Memory comes back: the same tile is admitted.
        machine["gb"] = 30.0
        assert run._start_new_tile_locked(second) is True


def test_peak_lands_on_the_record_the_step_wrote():
    started = time.time() - 1.0
    tile_time_model.record_build(10, 10, {}, {"mesh": 100.0})
    tile_time_model.record_step_peak(10, 10, "vector", 9.0, since=started)
    assert tile_time_model.step_peaks(10, 10) == {}     # no vector record
    tile_time_model.record_step_peak(10, 10, "mesh", 4.5, since=started)
    assert tile_time_model.step_peaks(10, 10) == {"mesh": 4.5}
    # A step that wrote no record (it failed) touches no older record.
    tile_time_model.record_step_peak(10, 10, "mesh", 9.0,
                                     since=time.time() + 60.0)
    assert tile_time_model.step_peaks(10, 10) == {"mesh": 4.5}


def test_tree_resident_counts_descendants():
    kib = 1024 * 1024
    table = [(100, 1, 1 * kib), (101, 100, 2 * kib), (102, 101, 3 * kib),
             (200, 1, 4 * kib), (300, 1, 9 * kib)]
    assert step_memory.tree_resident_gigabytes([100, 200, 999], table) == {
        100: pytest.approx(6.0), 200: pytest.approx(4.0)}


def test_step_done_records_the_sampled_peak():
    run = _run(1024.0)
    child = _admit_all(run)[0]
    tile_time_model.record_build(child.tile[0], child.tile[1], {},
                                 {"vector": 600.0})
    child.step_peak_gb = 11.0
    run._record_step_peak(child)
    assert tile_time_model.step_peaks(*child.tile) == {"vector": 11.0}


# ── #2101: a held heavy step is not starved ──────────────────────────────

def _events_run(budget, tiles):
    events = []
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=events.append, _run_finished=lambda: None),
        tiles, "P", 16, "", (True, False, False), 3)
    run._memory_budget = budget
    return run, events


def _give_children(run, count):
    children = [_Child() for _ in range(count)]
    run._children.extend(children)
    return children


def _heavy(run, tile):
    """``tile`` leads with a 57.5 GB mesh step (a 1 m raster's record): a
    heavy step that does not gate its own inner work."""
    run._programs[tile] = ["mesh"]
    run._recorded_peaks[tile] = {"mesh": 50.0}


def test_held_heavy_step_reserves_its_memory_fifo(machine):
    """The owner's case: a 57 GB vector step waits on live memory; a tile
    queued after it may not start a step that takes the memory it needs,
    however well that step alone fits."""
    big, later = (10, 10), (11, 11)
    run, _ = _events_run(1024.0, [(12, 12), big, later])
    _heavy(run, big)                                  # 57.5 GB projected
    first, second = _give_children(run, 2)
    with run._lock:
        assert run._start_new_tile_locked(first) is True    # (12,12) runs
        machine["gb"] = 50.0      # another application holds the rest
        run._refresh_memory_budget_locked()   # the budget follows it
        # The scan reaches big first: refused and held; `later` (8 GB,
        # which fits the machine alone) may not take big's memory.
        assert run._start_new_tile_locked(second) is False
        assert (big, "mesh") in run._memory_waits
        assert later in run._queue and second.tile is None
        # Without the hold, `later` would have started (pre-#2101).
        run._memory_waits.clear((big, "mesh"))
        run._queue.remove(big)
        assert run._start_new_tile_locked(second) is True
        assert second.tile == later


def test_held_step_starts_when_the_run_drains(machine):
    """Running steps are never paused; when they finish and nothing else
    holds memory, the held step is admitted — the wait is bounded."""
    big, later = (10, 10), (11, 11)
    run, _ = _events_run(1024.0, [(12, 12), big, later])
    _heavy(run, big)
    first, second = _give_children(run, 2)
    with run._lock:
        assert run._start_new_tile_locked(first) is True
        machine["gb"] = 50.0
        run._refresh_memory_budget_locked()
        assert run._start_new_tile_locked(second) is False
        assert first.running_step == "vector"           # never paused
        # The running step ends and gives its memory back.
        held = run._memory_holders.pop(((12, 12), "vector"))
        run._memory_in_use -= held
        first.running_step = None
        first.tile = None
        assert run._start_new_tile_locked(second) is True
        assert second.tile == big
        assert (big, "mesh") not in run._memory_waits
        # `later`, refused behind big's reservation, is shown waiting too.
        assert (later, "vector") in run._memory_waits


def test_only_waiting_work_starts_on_the_budget_sum(machine):
    """A held step that is the only work the run could start is admitted
    once the run's committed memory leaves it room, even while another
    application keeps live memory short (its airport builds take machine
    slots against live memory one worker at a time)."""
    big = (10, 10)
    run, _ = _events_run(1024.0, [(12, 12), big])
    _heavy(run, big)
    first, second = _give_children(run, 2)
    with run._lock:
        assert run._start_new_tile_locked(first) is True
        machine["gb"] = 50.0
        # First refusal: it is held (the reservation), not waved through.
        assert run._start_new_tile_locked(second) is False
        # Second look: the only waiting work, budget sum fits -> starts.
        assert run._start_new_tile_locked(second) is True
        assert second.tile == big


def test_reservation_does_not_block_while_the_waiter_has_no_child(machine):
    """A queued waiter with every child busy reserves nothing: the busy
    children's next steps go on, so one of them frees a child."""
    big, other = (10, 10), (11, 11)
    run, _ = _events_run(1024.0, [other, big])
    _heavy(run, big)
    (only,) = _give_children(run, 1)
    machine["gb"] = 50.0
    with run._lock:
        run._queue.remove(other)
        only.tile = other                     # between its vector and mesh
        run._next_step_index[other] = 1
        run._memory_waits.note((big, "mesh"), 57.5, 50.0, "machine")
        run._memory_holders[((9, 9), "mesh")] = 2.0     # someone running
        run._memory_in_use = 2.0
        run._refresh_memory_budget_locked()
        assert run._try_start_step_locked(only) is True
        assert only.running_step == "mesh"
        # With an idle child the same waiter does reserve its memory.
        idle = _Child()
        run._children.append(idle)
        blocked = _Child()
        blocked.tile = (12, 12)
        run._children.append(blocked)
        run._programs[(12, 12)] = ["vector", "mesh"]
        run._next_step_index[(12, 12)] = 1
        assert run._try_start_step_locked(blocked) is False


def test_single_tile_never_deadlocks(machine):
    run, _ = _events_run(4.0, [(10, 10)])
    _heavy(run, (10, 10))
    (child,) = _give_children(run, 1)
    machine["gb"] = 2.0
    with run._lock:
        assert run._start_new_tile_locked(child) is True


def test_memory_wait_event_reaches_the_row_and_resolves(machine):
    """A step short of MACHINE memory says so; a later step that fits the
    run's budget starts beside it (the reservation is judged against the
    run's budget, not memory another application holds)."""
    big = (10, 10)
    run, events = _events_run(1024.0, [(12, 12), big, (11, 11)])
    _heavy(run, big)
    first, second, third = _give_children(run, 3)
    with run._lock:
        assert run._start_new_tile_locked(first) is True
        machine["gb"] = 50.0
        assert run._start_new_tile_locked(second) is True
        assert second.tile == (11, 11)
    run._announce_memory_waits()
    run._announce_memory_waits()            # unchanged: nothing re-sent
    waits = [e for e in events if type(e).__name__ == "MemoryWait"]
    assert [(e.lat, e.step_key) for e in waits] == [(10, "mesh")]
    wait = waits[0]
    assert (wait.lat, wait.lon, wait.step_key) == (10, 10, "mesh")
    assert wait.needed_gb == pytest.approx(57.5)
    assert wait.free_gb == pytest.approx(50.0)
    assert wait.reason == "machine" and not wait.resolved
    assert wait.message == ("Waiting for memory: needs about 57 GB, 50 GB "
                            "free. Quitting X-Plane or another large "
                            "application frees memory.")
    machine["gb"] = 80.0      # the other application quit
    with run._lock:
        assert run._start_new_tile_locked(third) is True
    run._announce_memory_waits()
    done = [e for e in events if type(e).__name__ == "MemoryWait"
            and (e.lat, e.lon) == (10, 10)][-1]
    assert done.resolved and (done.lat, done.lon) == (10, 10)
    assert done.message == ""


def test_memory_wait_round_trips_the_wire():
    from o4_engine import events as EVENTS
    from o4_engine import jsonl

    event = EVENTS.MemoryWait(lat=47, lon=12, step_key="vector",
                              needed_gb=57.4, free_gb=30.2, reason="machine",
                              message="m", attempt=2)
    payload = jsonl.serialize_event(event)
    assert payload["event"] == "MemoryWait"
    back = parallel._rebuild_event(payload)
    assert back == dataclasses.replace(event, attempt=0)
    assert "memory_wait" in EVENTS.CAPABILITIES
    kit = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                       "SceneryKit")
    with open(os.path.join(kit, "OrthoEngineClient.swift"),
              encoding="utf-8") as handle:
        assert 'case "MemoryWait":' in handle.read()
    with open(os.path.join(kit, "MemoryWait.swift"), encoding="utf-8") as handle:
        model = handle.read()
    for field in payload:
        if field not in ("event", "seq", "ts"):
            assert '"%s"' % field in model, field


# ── owner 2026-11-18: free memory less what is booked and not yet used ──

def _quiet(monkeypatch):
    monkeypatch.setattr(parallel, "print", lambda *a, **k: None,
                        raising=False)


def _run_gate_only(monkeypatch):
    """The RUN's rule alone: these twins fake each worker's tree on the
    child, which the machine ledger (its own twins in
    ``test_machine_memory_ledger``) cannot see in a process table."""
    import O4_Machine_Slots as SLOTS

    monkeypatch.setenv(SLOTS.ENV_UNGATED, "1")


def test_room_is_free_memory_above_the_headroom(machine, monkeypatch):
    """The run's room follows the machine (app 1.0.552 sized it once and
    held steps for hours with 35 GB free) and is free memory above the
    headroom — no 80 % ceiling, no sum of whole projections (1.0.558).
    Scaled to this 64 GB machine (headroom 9.6 GB)."""
    _quiet(monkeypatch)
    machine["gb"] = 14.0                     # other programs hold 50 GB
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        TILES, "P", 16, "", (True, False, False), 3)
    assert run._memory_budget == pytest.approx(14.0 - 9.6)
    first, second = _give_children(run, 2)
    with run._lock:
        assert run._start_new_tile_locked(first) is True     # 3 GB parse
        assert run._start_new_tile_locked(second) is False   # 6 > 4.4
        machine["gb"] = 40.0                 # the other programs quit
        run._refresh_memory_budget_locked()
        assert run._memory_budget == pytest.approx(40.0 - 9.6)
        assert run._start_new_tile_locked(second) is True


def test_grown_memory_is_not_booked_twice(machine, monkeypatch):
    """A step's booking shrinks as its tree grows into it: free memory
    falls by what it grew, the booking by the same, and the room for the
    next step is unchanged — the 1.0.558 run counted both."""
    _quiet(monkeypatch)
    _run_gate_only(monkeypatch)
    tiles = [(10, 10), (11, 11), (12, 12)]
    run, _ = _events_run(0.0, tiles)
    for tile in tiles:
        run._programs[tile] = ["mesh"]
        run._recorded_peaks[tile] = {"mesh": 20.0}       # 23 GB each
    children = _give_children(run, 3)
    with run._lock:
        run._refresh_memory_budget_locked()             # 64 - 9.6
        assert run._start_new_tile_locked(children[0]) is True
        assert run._run_booked_locked() == pytest.approx(23.0)
        assert run._start_new_tile_locked(children[1]) is True   # 46 <= 54.4
        assert run._start_new_tile_locked(children[2]) is False  # 69 > 54.4
        # Both running steps grew 18 GB into their bookings.
        for child in children[:2]:
            child.tree_gb = 18.0
        machine["gb"] = 64.0 - 36.0
        run._refresh_memory_budget_locked()
        assert run._run_booked_locked() == pytest.approx(10.0)
        # 28 - 10 - 9.6 = 8.4 GB room: still short of 23 (honest wait).
        assert run._start_new_tile_locked(children[2]) is False
        assert (tiles[2], "mesh") in run._memory_waits
        # They finish growing (and some): nothing is booked any more.
        for child in children[:2]:
            child.tree_gb = 24.0
        machine["gb"] = 64.0 - 48.0 + 30.0   # and other programs left
        run._refresh_memory_budget_locked()
        assert run._run_booked_locked() == 0.0
        assert run._start_new_tile_locked(children[2]) is True


def test_a_tiles_next_step_needs_only_what_its_worker_lacks(machine):
    """The projection is the worker tree's peak; the worker keeps what the
    tile's earlier steps left, so the next step needs only the rest."""
    tile = (10, 10)
    run, _ = _events_run(1024.0, [tile])
    run._programs[tile] = ["vector", "masks"]
    run._recorded_peaks[tile] = {"masks": 7.8}            # 9.0 projected
    (child,) = _give_children(run, 1)
    child.tile = tile
    run._queue.remove(tile)
    run._next_step_index[tile] = 1
    child.tree_gb = 7.5                                   # left by vector
    with run._lock:
        assert run._step_memory_need_locked(tile, "masks") == pytest.approx(
            7.8 * step_memory.RECORDED_PEAK_MARGIN - 7.5)
        # A tile's FIRST step gets no credit: its record was measured on
        # a fresh worker, whatever another tile left in this one.
        run._next_step_index[tile] = 0
        assert run._step_memory_need_locked(tile, "masks") == pytest.approx(
            7.8 * step_memory.RECORDED_PEAK_MARGIN)


def test_seven_tiles_with_plenty_free_do_not_wait(machine, monkeypatch):
    """The owner's 1.0.558 complaint, as a twin: seven tiles whose steps
    project 98.5 GB in all on a 128 GB machine with 61 GB free while the
    steps have grown into most of it — nothing may wait for memory."""
    import O4_Parallel_Utils as PU

    _quiet(monkeypatch)
    _run_gate_only(monkeypatch)
    monkeypatch.setattr(PU, "machine_memory_gigabytes", lambda: 128.0)
    tiles = [(10 + k, 10) for k in range(8)]
    run, events = _events_run(0.0, tiles)
    charges = [14.0, 14.0, 14.0, 14.0, 14.0, 14.0, 14.5]   # 98.5 GB
    for tile, gb in zip(tiles, charges, strict=False):
        run._programs[tile] = ["mesh", "masks"]
        run._recorded_peaks[tile] = {"mesh": gb / 1.15}
    waiter = tiles[-1]
    run._recorded_peaks[waiter] = {"masks": 9.0 / 1.15}
    run._programs[waiter] = ["masks"]
    children = _give_children(run, 8)
    with run._lock:
        machine["gb"] = 120.0
        run._refresh_memory_budget_locked()
        for child in children[:7]:
            assert run._start_new_tile_locked(child) is True
        # The steps grew to 12 GB of their 14 each (84 GB): free fell to
        # 61.4 with the owner's other programs.
        for child in children[:7]:
            child.tree_gb = 12.0
        machine["gb"] = 61.4
        run._refresh_memory_budget_locked()
        assert run._run_booked_locked() == pytest.approx(98.5 - 84.0)
        # 61.4 - 14.5 booked - 19.2 kept = 27.7 >= 9: it starts.
        assert run._start_new_tile_locked(children[7]) is True
        assert not run._memory_waits


def test_twelve_vector_steps_start_on_an_idle_machine(machine, monkeypatch):
    """App 1.0.558 at run start: 119 GB free on 128 GB, eleven vector
    steps booked at 8 GB each (94.7 GB) and the twelfth held "with 119 GB
    free".  A vector step books its parse; its airports book their own
    slots on the ledger against live memory."""
    import O4_Parallel_Utils as PU

    _quiet(monkeypatch)
    _run_gate_only(monkeypatch)
    monkeypatch.setattr(PU, "machine_memory_gigabytes", lambda: 128.0)
    machine["gb"] = 119.0
    tiles = [(10 + k, 10) for k in range(12)]
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        tiles, "P", 16, "", (True, False, False), 12)
    run._class_limits["osm"] = 12        # the network cap is not under test
    children = _give_children(run, 12)
    with run._lock:
        run._refresh_memory_budget_locked()
        started = sum(run._start_new_tile_locked(child) for child in children)
        # Every one the step classes allow starts; memory holds none.
        assert started == 12
        assert run._run_booked_locked() == pytest.approx(3.0 * started)
        assert not run._memory_waits


def test_real_overcommit_still_waits(machine, monkeypatch):
    """The same run with its steps NOT yet grown: 98.5 GB booked against
    61.4 free is a real overcommit, and the masks step waits — the row
    names the booking, the headroom and the free memory."""
    import O4_Parallel_Utils as PU

    _quiet(monkeypatch)
    _run_gate_only(monkeypatch)
    monkeypatch.setattr(PU, "machine_memory_gigabytes", lambda: 128.0)
    tiles = [(10 + k, 10) for k in range(8)]
    run, events = _events_run(0.0, tiles)
    for tile in tiles[:7]:
        run._programs[tile] = ["mesh"]
        run._recorded_peaks[tile] = {"mesh": 14.0 / 1.15}
    waiter = tiles[-1]
    run._programs[waiter] = ["masks"]
    run._recorded_peaks[waiter] = {"masks": 9.0 / 1.15}
    children = _give_children(run, 8)
    with run._lock:
        machine["gb"] = 128.0
        run._refresh_memory_budget_locked()
        for child in children[:7]:
            assert run._start_new_tile_locked(child) is True
        machine["gb"] = 61.4
        run._refresh_memory_budget_locked()
        assert run._start_new_tile_locked(children[7]) is False
        wait = run._memory_waits.snapshot()[(waiter, "masks")]
        assert wait.reason == "run"
        assert wait.booked_gb == pytest.approx(98.0)
    run._announce_memory_waits()
    rows = [e.message for e in events if type(e).__name__ == "MemoryWait"]
    assert "have booked 98 GB they do not use yet" in rows[-1]
    assert "19.2 GB is kept free" in rows[-1] or "19 GB is kept free" in rows[-1]


def test_tiny_step_never_queues_behind_a_reservation(machine):
    """A 0.5 GB overlays step does not wait for an older 57 GB waiter to
    fit; a bigger step still does (#2101)."""
    big, small = (10, 10), (11, 11)
    run, _ = _events_run(40.0, [(12, 12), big, small])
    _heavy(run, big)
    run._programs[small] = ["overlays"]
    first, second, third = _give_children(run, 3)
    with run._lock:
        assert run._start_new_tile_locked(first) is True
        assert run._start_new_tile_locked(second) is True
        assert second.tile == small and second.running_step == "overlays"
        assert (big, "mesh") in run._memory_waits
        assert (small, "overlays") not in run._memory_waits


def test_wait_names_what_holds_it(machine):
    """The row says what the step waits for: the reserving step by name,
    or what the run's steps booked and do not yet use — never "about 0
    GB"."""
    from o4_engine import memory_waits

    big, later = (10, 10), (11, 11)
    run, events = _events_run(60.0, [(12, 12), big, later])
    _heavy(run, big)
    first, second, third = _give_children(run, 3)
    with run._lock:
        assert run._start_new_tile_locked(first) is True
        assert run._start_new_tile_locked(second) is False
    run._announce_memory_waits()
    rows = {(e.lat, e.step_key): e.message for e in events
            if type(e).__name__ == "MemoryWait"}
    assert rows[(10, "mesh")].startswith(
        "Waiting for memory: needs about 57 GB")
    assert "have booked 3.0 GB they do not use yet" in rows[(10, "mesh")]
    assert rows[(11, "vector")].startswith(
        "Waiting behind +10+010 mesh step, which needs its memory first")
    assert "about 0.5 GB" in memory_waits.wait_message(
        0.5, 34.3, memory_waits.REASON_RUN)
