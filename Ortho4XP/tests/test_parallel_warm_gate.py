"""The parallel run's OpenStreetMap warmer leaves a tile a worker could
take, and warms off the command process (lane lscale; owner
2026-11-20T18:33-18:40Z: "It's supposed to scale to available resources"
/ "an active dialog should take precedence over any builds which should be
in the background").

The owner's 1.0.568 run: -23-048 joined a run with free slots; the warmer
thread (revived by the enqueue) claimed it while the new worker
handshook, and the worker, which skips the tile being warmed, sat idle
until the warm finished an hour later — the Overpass downloads and their
parse on the COMMAND process's interpreter meanwhile.

Headless: workers are fakes; the warm runner is substituted.
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import osm_warm_process as OSM_WARM
from o4_engine import parallel


class _Child:
    def __init__(self, tile=None):
        self.tile, self.retired, self.cancelling = tile, False, False
        self.running_step = "vector" if tile else None


def _run(tiles, slots):
    session = SimpleNamespace(
        _emit=lambda event: None, _run_finished=lambda: None,
        with_paid_rebuilds=lambda built: built,
        _announce_rebuild_pending=lambda cancelled: None)
    return parallel.ParallelBuildRun(
        session, tiles, "P", 16, "", (True, False, False), slots)


def test_a_tile_a_spawnable_worker_could_take_is_not_warmed():
    """The owner's race: one busy worker of 18 slots, a tile queued — the
    pool grows for it, so the warmer must leave it to its worker."""
    run = _run([(-23, -48)], 18)
    run._children = [_Child((34, 135))]
    with run._lock:
        assert run._worker_could_take_locked((-23, -48)) is True


def test_an_idle_worker_counts_as_room():
    run = _run([(1, 1), (2, 2)], 2)
    run._children = [_Child((9, 9)), _Child()]
    with run._lock:
        assert run._worker_could_take_locked((1, 1)) is True
        assert run._worker_could_take_locked((2, 2)) is False


def test_a_tile_behind_full_slots_is_warmed():
    """Every slot busy: the queued tile waits for a slot, and its warm is
    what the warmer is for."""
    run = _run([(1, 1)], 2)
    run._children = [_Child((8, 8)), _Child((9, 9))]
    with run._lock:
        assert run._worker_could_take_locked((1, 1)) is False


def test_the_token_wait_gives_the_tile_up_when_a_slot_frees():
    run = _run([(1, 1)], 1)
    busy = _Child((9, 9))
    run._children = [busy]
    busy.tile = None                # its tile finished: an idle worker
    assert run._await_warm_token((1, 1)) is False
    assert run._warming_tile is None
    assert run._warm_token_held is False


def test_layers_warm_through_the_runner_and_stop_with_the_tile(
        monkeypatch):
    """Each layer goes to the runner (a process of its own in the app);
    a tile that left the queue stops the warm between layers; the runner
    is always closed."""
    calls, closed = [], []

    class _Runner:
        def layer(self, lat, lon, build_dir, index):
            calls.append((lat, lon, build_dir, index))
            if index == 1:
                run._queue.remove((1, 1))   # a worker took the tile
            return True

        def close(self):
            closed.append(True)

    run = _run([(1, 1)], 1)
    monkeypatch.setattr(OSM_WARM, "open_runner", _Runner)
    assert run._warm_tile_layers((1, 1), "dir", 4) == 2
    assert calls == [(1, 1, "dir", 0), (1, 1, "dir", 1)]
    assert closed == [True]


def test_the_app_warms_in_a_process_of_its_own():
    """The default runner is the spawned worker, never the calling
    thread (the command process's interpreter)."""
    runner = OSM_WARM.open_runner()
    try:
        assert isinstance(runner, OSM_WARM.WarmProcess)
    finally:
        runner.close()


def test_warm_layer_runs_in_another_process():
    """The warm worker is a separate process: a layer function run through
    it answers with another pid (CommandProcess, as a World drape)."""
    from o4_engine.command_process import CommandProcess
    process = CommandProcess(out=lambda line: None, stall_s=120.0)
    try:
        assert process.run(os.getpid, what="pid") != os.getpid()
    finally:
        process.close()
