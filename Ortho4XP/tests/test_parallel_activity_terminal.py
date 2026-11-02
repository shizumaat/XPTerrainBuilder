"""#1736: a tile reaches the Activity list's Completed section only on its
terminal event, under a parallel run.

A worker child builds ONE step per command and ends every step with
``TileState(done)`` + ``BuildDone(ok)``; the orchestrator must forward
those only for the tile's LAST step.  This twin drives a stub parallel
run of five tiles (one started, four queued into the live run, as the
owner's run of +60+011 was) and replays the merged stream through the
front ends' shared section rule (``O4_Activity_Order.section``, the Mac
app's ``ActivityOrder.section``): after every event each tile's row must
sit where its build stands -- Activity while any step is left, Completed
from its terminal on.

Headless, no network: the workers are ``tests/fixtures/stub_engine_worker
.py`` (the happy path: two ``StepProgress`` lines, then the step's done
pair, per step).
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Activity_Order as ACTORDER
import pytest
from o4_engine import parallel
from o4_engine.events import BuildDone, RunDone, StepProgress, TileState
from o4_engine.session import EngineSession

STUB_WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "fixtures", "stub_engine_worker.py")
FIRST = (10, 10)
QUEUED_LATER = [(11, 11), (12, 12), (13, 13), (14, 14)]
PROGRAM = ["vector", "mesh", "masks", "imagery"]


@pytest.fixture(autouse=True)
def wide_machine(monkeypatch, tmp_path):
    """A machine wide enough that five tiles run at once; stub workers."""
    import O4_Machine_Slots as SLOTS
    import O4_Parallel_Utils as PARALLEL_UTILS

    (tmp_path / "machine-slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "machine-slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "64")
    monkeypatch.setattr(PARALLEL_UTILS, "machine_core_count", lambda: 8)
    monkeypatch.setattr(PARALLEL_UTILS, "machine_available_memory_gigabytes",
                        lambda: 64.0)
    monkeypatch.setattr(parallel, "tile_worker_command",
                        lambda: [sys.executable, STUB_WORKER])


def _run_five_tiles():
    session = EngineSession()
    events = []
    session.subscribe(events.append)
    assert session.build([FIRST], "P", 16, "", do_vector=True,
                         do_imagery=True, slots=5)
    for tile in QUEUED_LATER:
        time.sleep(0.1)
        assert session.enqueue_build([tile], "P", 16, "", do_vector=True,
                                     do_imagery=True)
    deadline = time.time() + 30.0
    while (not any(isinstance(e, RunDone) for e in events)
           and time.time() < deadline):
        time.sleep(0.02)
    assert any(isinstance(e, RunDone) for e in events), "RunDone never came"
    return events


def _row_state(event, previous):
    """The row state a front end gives a tile after ``event`` (the Mac
    app's ``BuildModel.handle``, the Qt window's tile-state and
    step-progress handlers)."""
    if isinstance(event, TileState):
        return event.state
    if isinstance(event, StepProgress):
        return "indeterminate" if event.indeterminate else "active"
    return previous


def test_a_tile_is_completed_only_from_its_terminal_on():
    events = _run_five_tiles()
    rows = {}
    steps_seen = {}
    terminal_seen = set()
    for event in events:
        if not isinstance(event, (TileState, StepProgress, BuildDone)):
            continue
        tile = (event.lat, event.lon)
        if isinstance(event, StepProgress):
            assert tile not in terminal_seen, (
                "%s: progress after its terminal" % (tile,))
            steps_seen.setdefault(tile, []).append(event.step_key)
        rows[tile] = _row_state(event, rows.get(tile, "queued"))
        last_step_running = steps_seen.get(tile, [None])[-1] == PROGRAM[-1]
        if isinstance(event, BuildDone):
            assert event.ok and last_step_running, (
                "%s: BuildDone before its last step" % (tile,))
            terminal_seen.add(tile)
        if ACTORDER.section(rows[tile]) == ACTORDER.COMPLETED:
            # The tile's done may lead its BuildDone by one event, never
            # by a step.
            assert last_step_running, (
                "%s listed under Completed during step %s"
                % (tile, steps_seen.get(tile, [None])[-1]))
    for tile in [FIRST] + QUEUED_LATER:
        assert ACTORDER.section(rows[tile]) == ACTORDER.COMPLETED
        assert tile in terminal_seen, "%s: no terminal" % (tile,)
        dones = [e for e in events if isinstance(e, TileState)
                 and (e.lat, e.lon) == tile and e.state == "done"]
        assert len(dones) == 1, "%s: %d done events" % (tile, len(dones))
        assert list(dict.fromkeys(steps_seen[tile])) == PROGRAM


def test_an_intermediate_step_done_pair_is_never_forwarded():
    """The unit of the rule above: a child's per-step done pair is a
    scheduling signal until the step it ends is the tile's last."""
    emitted = []
    session = type("Session", (), {})()
    session._emit = emitted.append
    session._run_finished = lambda: None
    run = parallel.ParallelBuildRun(
        session, [FIRST], "P", 16, "", (True, True, False), 2)

    class Child:
        tile = FIRST
        cancelling = False
        step_failed = False

    child = Child()
    for index, step in enumerate(PROGRAM):
        run._next_step_index[FIRST] = index
        for payload in ({"event": "TileState", "lat": 10, "lon": 10,
                         "state": "done", "percent": 100.0},
                        {"event": "BuildDone", "lat": 10, "lon": 10,
                         "ok": True}):
            before = len(emitted)
            run._on_child_event(child, payload)
            forwarded = emitted[before:]
            if step == PROGRAM[-1]:
                assert len(forwarded) == 1, step
            else:
                assert forwarded == [], (
                    "step %s's %s reached the front end"
                    % (step, payload["event"]))
