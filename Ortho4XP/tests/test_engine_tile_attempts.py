"""Per-tile attempts (#1326): a stopped tile queued again starts a NEW
attempt, numbered on its ``TileState`` / ``StepProgress`` events, so a
front end tells the stopped attempt's late news from the new one; the
engine never holds two copies of one tile, and a stopped tile's clock
stops with it.

The parallel scheduler is driven at unit level (a bare run with fake
children, as ``test_parallel_coordination`` does) and end to end through
the stub worker of ``test_engine_parallel``; the in-process path through
the stub pipeline of ``test_engine_session``.
"""

import os
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import events as EV  # noqa: E402
from o4_engine import parallel  # noqa: E402
from o4_engine.session import EngineSession  # noqa: E402
from test_engine_parallel import (  # noqa: E402,F401
    Collector,
    _run_in_process,
    _start_parallel,
    _wait_for,
    reset_ui_routing,
    stub_worker,
)
from test_engine_session import install_stub_pipeline  # noqa: E402


class _Child:
    def __init__(self, tile, cancelling=False):
        self.tile = tile
        self.running_step = "mesh"
        self.step_class = None
        self.autopatch_pending = None
        self.step_failed = False
        self.cancelling = cancelling
        self.retired = False
        # No process: the cancel escalation's timer finds nothing to stop.
        self.process = None

    def send(self, payload):
        return True


def _bare_run(session, tiles):
    run = parallel.ParallelBuildRun(
        session, tiles, "P", 16, "", (True, False, False), 2)
    run._spawn_child = lambda: None
    return run


def test_session_numbers_each_admission_and_stamps_its_events():
    session = EngineSession()
    seen = []
    session.subscribe(seen.append)
    assert session.tile_attempt((10, 20)) == 0
    assert session.new_tile_attempt((10, 20)) == 1
    session._emit(EV.StepProgress(lat=10, lon=20, step_key="vector"))
    assert session.new_tile_attempt((10, 20)) == 2
    session._emit(EV.TileState(lat=10, lon=20, state="active"))
    # An attempt fixed where the stop was decided is kept as it is.
    session._emit(EV.TileState(lat=10, lon=20, label="stopped", attempt=1))
    assert [event.attempt for event in seen] == [1, 2, 1]


def test_a_tile_still_being_stopped_is_not_admitted_twice():
    """Never two copies: while the stopped attempt's child is still
    winding down, a re-queue of its tile is refused; once it is gone the
    tile is admitted as attempt 2, with a clock starting at zero."""
    session = EngineSession()
    tile = (10, 10)
    run = _bare_run(session, [tile, (11, 11)])
    assert session.tile_attempt(tile) == 1
    run._queue.remove(tile)
    child = _Child(tile)
    run._children = [child]
    run._next_step_index[tile] = 1
    run._tile_first_started[tile] = time.time() - 120.0

    assert run.cancel_tile(tile) is True
    assert child.cancelling is True
    final = run._tile_final_elapsed[tile]
    assert 119.0 <= final <= 130.0, "the clock stopped with the tile"
    assert run.enqueue([tile], "P", 16, "", (True, False, False)) == 0
    assert session.tile_attempt(tile) == 1

    # The child has gone (what _on_child_exit leaves behind).
    child.tile = None
    run._next_step_index.pop(tile)
    run._children = []
    assert run.enqueue([tile], "P", 16, "", (True, False, False)) == 1
    assert session.tile_attempt(tile) == 2
    assert tile not in run._tile_first_started
    assert tile not in run._tile_final_elapsed


def test_a_queued_tiles_stop_names_the_stopped_attempt():
    session = EngineSession()
    seen = []
    session.subscribe(seen.append)
    run = _bare_run(session, [(10, 10), (11, 11)])
    run._children = [_Child((10, 10))]
    run._queue.remove((10, 10))
    assert run.cancel_tile((11, 11)) is True
    [stopped] = [e for e in seen if isinstance(e, EV.TileState)]
    assert (stopped.lat, stopped.label, stopped.attempt) == (11, "stopped", 1)
    assert run.enqueue([(11, 11)], "P", 16, "", (True, False, False)) == 1
    assert session.tile_attempt((11, 11)) == 2


def test_child_events_carry_the_parents_attempt_not_the_childs():
    event = parallel._rebuild_event(
        {"event": "StepProgress", "lat": 1, "lon": 2, "attempt": 9})
    assert event.attempt == 0, "the parent session stamps its own number"


def test_bare_sessions_without_attempts_still_schedule():
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        [(10, 10)], "P", 16, "", (True, False, False), 2)
    assert run._attempt((10, 10)) == 0


@pytest.mark.usefixtures("stub_worker")
def test_resumed_tile_builds_again_as_a_new_attempt():
    """End to end: stop an active tile while two others build, queue it
    again once its stop is reported, and it builds — its first attempt's
    events and its second's are numbered apart."""
    session = EngineSession()
    collector = Collector(session)
    assert _start_parallel(
        session, [(60, 1), (60, 2), (60, 3)], slots=2) is True
    assert _wait_for(lambda: any(
        isinstance(e, EV.StepProgress) and (e.lat, e.lon) == (60, 1)
        for e in collector.events))
    assert session.cancel_tile(60, 1) is True
    assert _wait_for(lambda: any(
        isinstance(e, EV.TileState) and (e.lat, e.lon) == (60, 1)
        and e.label == "stopped" for e in collector.events))
    assert session.enqueue_build(
        [(60, 1)], "BI", 16, "", do_vector=True, do_imagery=True,
        do_overlays=False) is True
    run_done = collector.wait_run_done(30.0)

    first = collector.tile_events(60, 1)
    stopped = [e for e in first
               if isinstance(e, EV.TileState) and e.label == "stopped"]
    assert [e.attempt for e in stopped] == [1]
    progress = [e.attempt for e in first if isinstance(e, EV.StepProgress)]
    assert progress and set(progress) <= {1, 2} and progress[-1] == 2
    done = [e for e in first
            if isinstance(e, EV.TileState) and e.state == "done"]
    assert [e.attempt for e in done] == [2]
    assert run_done.done_count == 3


def test_in_process_queued_tile_stops_at_once_and_can_be_queued_again(
        monkeypatch, tmp_path):
    """In-process: a queued tile's stop is reported when it is pressed,
    and the same tile queued again builds (its old cancel does not stop
    the new attempt)."""
    holder = {}
    fired = {"done": False}

    def stop_then_requeue(_tile):
        if fired["done"]:
            return
        fired["done"] = True
        session = holder["session"]
        assert session.cancel_tile(11, 21) is True
        holder["stopped_at_once"] = any(
            isinstance(e, EV.TileState) and e.label == "stopped"
            and (e.lat, e.lon) == (11, 21) for e in holder["c"].events)
        assert session.enqueue_build(
            [(11, 21)], "BI", 16, str(tmp_path), do_vector=True,
            do_imagery=True, do_overlays=False) is True

    install_stub_pipeline(monkeypatch, hooks={"vector": stop_then_requeue})
    session = EngineSession()
    holder["session"] = session
    holder["c"] = Collector(session)
    collector = _run_in_process(session, [(10, 20), (11, 21)], tmp_path,
                                holder["c"])
    run_done = collector.wait_run_done(30.0)

    assert holder["stopped_at_once"] is True
    events = collector.tile_events(11, 21)
    builds = [e for e in events if isinstance(e, EV.BuildDone)]
    assert len(builds) == 1 and builds[0].ok is True
    assert {e.attempt for e in events if isinstance(e, EV.StepProgress)} == {2}
    assert run_done.done_count == 2
