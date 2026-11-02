"""Issue #1643 — a cross-tile airport is built by its owner tile whatever
the queue order.

THE DEFECT: a tile chooses its auto-patch airports at the start of its
vector step, against the tiles the run held then.  A neighbour queued
AFTER that moment was "a tile this build is not building", so an airport
the tile owns that crosses into it was boundary-skipped and never built
(#1642 covered only the owner queued LATER).  Now a tile whose selection
skipped an airport into a cell that joins the run later runs its vector
step again (parallel run) or is queued again (in-process run).

The parallel twins drive the REAL ``ParallelBuildRun`` against the stub
worker (``tests/fixtures/stub_engine_worker.py``); the airport judgement
is a synthetic record — one class-S airport of HOME crossing into NEIGH.
Headless, no network, no corpus.
"""
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Vector_Map as VMAP  # noqa: E402
import pytest  # noqa: E402
from o4_engine import boundary_reselect as BOUNDARY  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine import parallel  # noqa: E402
from o4_engine.session import EngineSession  # noqa: E402
from test_boundary_press_batch import _in_process_session  # noqa: E402
from test_engine_parallel import (  # noqa: E402
    Collector,
    _start_parallel,
    _unconstrain_memory_admission,
    _wait_for,
    stub_worker,
)

#: HOME owns ZZZZ, whose airside claim crosses into NEIGH (its south
#: neighbour).  lat 60 is the stub's sleeper: each step lasts ~0.6 s, so a
#: neighbour can be queued while HOME's vector step is in flight.
HOME = (60, 1)
NEIGH = (59, 1)
FAR = (10, 20)
KEEPALIVE = (60, 5)

__all__ = ["stub_worker"]          # the fixture, re-exported for pytest


def _judge(lat, lon, batch):
    """The synthetic boundary record: ZZZZ is cold into NEIGH unless the
    batch the selection used holds it."""
    if (lat, lon) != HOME:
        return ([], set())
    cold = [] if NEIGH in set(map(tuple, batch)) else [NEIGH]
    return ([("ZZZZ", "S", cold, 40.0)], set())


@pytest.fixture
def dispatches(monkeypatch):
    """``[(tile, step, batch)]`` of every step command the parent sends."""
    seen = []
    lock = threading.Lock()
    original = parallel._WorkerChild.start_step

    def record(child, step_key, arguments):
        with lock:
            seen.append((tuple(child.tile), step_key, frozenset(
                tuple(c) for c in arguments.get("boundary_batch") or ())))
        return original(child, step_key, arguments)

    monkeypatch.setattr(parallel._WorkerChild, "start_step", record)
    monkeypatch.setattr(BOUNDARY, "boundary_record", _judge)
    monkeypatch.setattr(VMAP, "tile_frame_is_warm", lambda lat, lon: False)
    return seen


def _vector(seen, tile):
    return [batch for (t, step, batch) in seen
            if t == tile and step == "vector"]


def _enqueue(session, tiles):
    return session.enqueue_build(list(tiles), "BI", 16, "", do_vector=True,
                                 do_imagery=True, do_overlays=False)


def _built(collector, tile):
    return [e for e in collector.tile_events(*tile)
            if isinstance(e, EV.BuildDone) and e.ok]


# ── the judgement ─────────────────────────────────────────────────────
@pytest.fixture
def cold(monkeypatch):
    monkeypatch.setattr(VMAP, "tile_frame_is_warm", lambda lat, lon: False)


def test_a_skip_into_a_new_neighbour_is_found(monkeypatch, cold):
    monkeypatch.setattr(BOUNDARY, "boundary_record", _judge)
    assert BOUNDARY.airports_skipped_into(HOME, {HOME}, [NEIGH]) == ["ZZZZ"]


def test_a_warm_neighbour_reads_nothing(monkeypatch):
    """A frame warm now was warm for the selection too: it built ZZZZ."""
    def refuse(*_args):
        raise AssertionError("a warm neighbour: nothing may be read")

    monkeypatch.setattr(BOUNDARY, "boundary_record", refuse)
    monkeypatch.setattr(VMAP, "tile_frame_is_warm", lambda lat, lon: True)
    assert BOUNDARY.airports_skipped_into(HOME, {HOME}, [NEIGH]) == []


def test_a_selection_that_held_the_neighbour_reads_nothing(monkeypatch,
                                                         cold):
    def refuse(*_args):
        raise AssertionError("no new neighbour: nothing may be read")

    monkeypatch.setattr(BOUNDARY, "boundary_record", refuse)
    assert BOUNDARY.airports_skipped_into(HOME, {HOME, NEIGH}, [NEIGH]) == []
    assert BOUNDARY.airports_skipped_into(HOME, {HOME}, [FAR]) == []
    assert BOUNDARY.airports_skipped_into(HOME, {HOME}, [HOME]) == []


def test_a_failed_judgement_rejudges_nothing(monkeypatch, cold):
    def broken(*_args):
        raise OSError("no CIFP")

    monkeypatch.setattr(BOUNDARY, "boundary_record", broken)
    assert BOUNDARY.airports_skipped_into(HOME, {HOME}, [NEIGH]) == []


# ── the parallel run: every queue order builds ZZZZ once, at HOME ──────
def test_neighbour_queued_while_the_owner_vector_step_runs(stub_worker,
                                                           dispatches):
    """THE DEFECT, pinned: HOME's vector step was dispatched without
    NEIGH; NEIGH joins mid-step -> HOME runs its vector step again, with
    NEIGH in its batch, and is built once."""
    _unconstrain_memory_admission(stub_worker)
    session = EngineSession()
    collector = Collector(session)
    assert _start_parallel(session, [HOME], slots=2) is True
    assert _wait_for(lambda: _vector(dispatches, HOME))
    assert _enqueue(session, [NEIGH]) is True
    run_done = collector.wait_run_done(60.0)

    assert _vector(dispatches, HOME) == [frozenset({HOME}),
                                         frozenset({HOME, NEIGH})]
    assert len(_built(collector, HOME)) == 1
    assert (run_done.done_count, run_done.error_count) == (2, 0)


def test_neighbour_queued_after_the_owner_finished(stub_worker, dispatches):
    """The owner had already built when NEIGH joined: it is queued again
    and its new vector step counts NEIGH."""
    _unconstrain_memory_admission(stub_worker)
    session = EngineSession()
    collector = Collector(session)
    assert _start_parallel(session, [HOME, KEEPALIVE], slots=2) is True
    assert _wait_for(lambda: _built(collector, HOME), timeout=30.0)
    assert _enqueue(session, [NEIGH]) is True
    collector.wait_run_done(60.0)

    assert _vector(dispatches, HOME) == [frozenset({HOME}),
                                         frozenset({HOME, NEIGH})]
    assert len(_built(collector, HOME)) == 2


@pytest.mark.parametrize("order", [[HOME, NEIGH], [NEIGH, HOME]])
def test_one_press_holding_both_builds_the_owner_once(stub_worker,
                                                      dispatches, order):
    """The control: both tiles in the run from the start (either order)
    -> HOME's one vector step already counts NEIGH; nothing re-runs."""
    _unconstrain_memory_admission(stub_worker)
    session = EngineSession()
    collector = Collector(session)
    assert _start_parallel(session, order, slots=2) is True
    collector.wait_run_done(60.0)
    assert _vector(dispatches, HOME) == [frozenset({HOME, NEIGH})]


def test_a_tile_queued_far_away_reruns_nothing(stub_worker, dispatches):
    _unconstrain_memory_admission(stub_worker)
    session = EngineSession()
    collector = Collector(session)
    assert _start_parallel(session, [HOME], slots=2) is True
    assert _wait_for(lambda: _vector(dispatches, HOME))
    assert _enqueue(session, [FAR]) is True
    collector.wait_run_done(60.0)
    assert _vector(dispatches, HOME) == [frozenset({HOME})]


# ── the in-process run ────────────────────────────────────────────────
def _serial(monkeypatch, skipped_into):
    import O4_UI_Utils as UI

    monkeypatch.setattr(UI, "red_flag", False, raising=False)
    monkeypatch.setattr(VMAP, "BOUNDARY_BATCHES", {}, raising=False)
    monkeypatch.setattr(VMAP, "BOUNDARY_SKIPPED_INTO",
                        {HOME: frozenset(skipped_into)}, raising=False)
    session = _in_process_session([])
    session._run_items = {HOME: (HOME, "BI", 16, "", [])}
    return session


def test_in_process_owner_built_before_the_neighbour_is_queued_again(
        monkeypatch):
    session = _serial(monkeypatch, {NEIGH})
    assert session._enqueue_in_process([NEIGH], "BI", 16, "",
                                       True, False, False) == 1
    assert [item[0] for item in session._work_queue] == [NEIGH, HOME]
    # Judged once: a later press does not queue it a third time.
    assert session._enqueue_in_process([FAR], "BI", 16, "",
                                       True, False, False) == 1
    assert [item[0] for item in session._work_queue] == [NEIGH, HOME, FAR]


def test_in_process_owner_that_skipped_nothing_is_not_queued(monkeypatch):
    session = _serial(monkeypatch, set())
    session._enqueue_in_process([NEIGH], "BI", 16, "", True, False, False)
    assert [item[0] for item in session._work_queue] == [NEIGH]


def test_in_process_active_owner_is_judged_when_it_ends(monkeypatch):
    """The building tile is not queued twice by the press; its own end
    queues it again against the run's queued tiles."""
    session = _serial(monkeypatch, {NEIGH})
    session._active_tile = HOME
    session._enqueue_in_process([NEIGH], "BI", 16, "", True, False, False)
    assert [item[0] for item in session._work_queue] == [NEIGH]
    with session._work_queue_lock:
        session._requeue_boundary_skips(
            session._live_run_cells_locked() - {HOME}, [HOME])
    assert [item[0] for item in session._work_queue] == [NEIGH, HOME]
