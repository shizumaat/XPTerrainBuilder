"""Twins for the object stage beside the masks and imagery steps (#1264,
``O4_Object_Stage_Beside``).

Headless: the stage is a fake, the orchestrator is driven with fake
children (no worker processes), the file witness and the tile sidecar run
on temporary files.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Object_Stage as OBJECT_STAGE
import O4_Object_Stage_Beside as BESIDE
import O4_UI_Utils as UI
import O4_Unpatched_Airports as UNPATCHED
import pytest
from auto_patch_v2.airport import file_witness
from o4_engine import parallel


@pytest.fixture
def stage(monkeypatch):
    """A fake stage that waits for ``release`` and notes every tile."""
    release = threading.Event()
    calls = []

    def run(tile, beside=False):
        calls.append(((tile.lat, tile.lon), beside))
        assert release.wait(10.0)
        return {}

    monkeypatch.setattr(OBJECT_STAGE, "run", run)
    monkeypatch.setattr(UI, "red_flag", False)
    yield SimpleNamespace(release=release, calls=calls)
    release.set()
    BESIDE.join()
    BESIDE._WANTED.clear()


def _tile(lat=40, lon=-4):
    return SimpleNamespace(lat=lat, lon=lon)


def test_inline_unless_wanted(stage):
    stage.release.set()
    BESIDE.run(_tile())
    assert stage.calls == [((40, -4), False)]
    assert not BESIDE.pending()


def test_wanted_runs_beside_until_joined_and_the_want_is_taken(stage):
    tile = _tile()
    BESIDE.want(tile, True)
    BESIDE.run(tile)
    assert BESIDE.pending(tile)
    assert stage.calls == [((40, -4), True)]
    stage.release.set()
    BESIDE.join(tile)
    assert not BESIDE.pending()
    BESIDE.run(tile)                      # the next mesh step: inline again
    assert stage.calls[-1] == ((40, -4), False)


def test_masks_and_imagery_of_the_tile_run_beside_anything_else_joins(stage):
    tile = _tile()
    BESIDE.want(tile, True)
    BESIDE.run(tile)
    BESIDE.before_step(tile, "masks")
    BESIDE.before_step(tile, "imagery")
    assert BESIDE.pending(tile)
    stage.release.set()
    BESIDE.before_step(_tile(41, -4), "masks")     # another tile's step
    assert not BESIDE.pending()


def test_a_new_mesh_step_joins_the_last_one(stage):
    first, second = _tile(), _tile(41, -4)
    BESIDE.want(first, True)
    BESIDE.run(first)
    stage.release.set()
    BESIDE.run(second)                    # inline, after the first is joined
    assert not BESIDE.pending()
    assert stage.calls == [((40, -4), True), ((41, -4), False)]


def test_the_mesh_record_is_cut_again_at_the_join_unless_stopped(stage,
                                                                   monkeypatch):
    tile, cuts = _tile(), []
    for stopped in (False, True):
        stage.release.clear()
        BESIDE.want(tile, True)
        BESIDE.run(tile)
        BESIDE.recut_when_done(tile, lambda s=stopped: cuts.append(s))
        monkeypatch.setattr(UI, "red_flag", stopped)
        stage.release.set()
        BESIDE.join()
    assert cuts == [False]


def test_the_mesh_record_names_no_pack_or_code_while_the_stage_runs(stage):
    import O4_Step_Reuse as REUSE
    tile = _tile()
    BESIDE.want(tile, True)
    BESIDE.run(tile)
    assert REUSE._object_stage_beside(tile) is True
    assert BESIDE._JOBS[(40, -4)].recut is not None
    stage.release.set()
    BESIDE.join()
    assert REUSE._object_stage_beside(tile) is False


def test_a_confined_window_records_its_own_thread_only(tmp_path):
    mine, other = tmp_path / "mine.txt", tmp_path / "other.txt"
    for path in (mine, other):
        path.write_text("x", encoding="utf-8", newline="\n")
    seen = {}
    opened, done = threading.Event(), threading.Event()

    def stage_thread():
        file_witness.confine_to_thread()
        rec = file_witness.FileRecorder()
        rec.recording(True)
        opened.set()
        assert done.wait(10.0)
        mine.read_text(encoding="utf-8")
        rec.recording(False)
        seen["confined"] = set(rec.record())

    free = file_witness.FileRecorder()
    free.recording(True)
    worker = threading.Thread(target=stage_thread)
    worker.start()
    assert opened.wait(10.0)
    other.read_text(encoding="utf-8")         # the step's own read
    done.set()
    worker.join(10.0)
    free.recording(False)
    assert seen["confined"] == {str(mine)}
    assert {str(mine), str(other)} <= set(free.record())


def test_the_sidecar_keeps_every_source_written_at_once(tmp_path):
    tiles = [SimpleNamespace(lat=40, lon=-4, build_dir=str(tmp_path))
             for _ in range(2)]

    def write(tile, source):
        for i in range(40):
            UNPATCHED.record_degraded(tile, source, [{"code": source,
                                                      "detail": str(i)}])

    threads = [threading.Thread(target=write, args=(t, s))
               for t, s in zip(tiles, ("masks", "object-stage"), strict=True)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30.0)
    with open(os.path.join(tmp_path, UNPATCHED.UNPATCHED_SIDECAR),
              encoding="utf-8") as handle:
        rows = json.load(handle)[UNPATCHED.DEGRADED_KEY]
    assert set(rows) == {"masks", "object-stage"}


# -- the orchestrator ------------------------------------------------------
class _Child:
    def __init__(self, tile):
        self.tile = tile
        self.running_step = None
        self.retired = False
        self.cancelling = False
        self.objects_beside = True
        self.terminated = 0
        self.process = SimpleNamespace(poll=lambda: None, kill=lambda: None)

    def terminate(self):
        self.terminated += 1
        self.retired = True

    def send(self, payload):
        return True


def _run(program, index, tile=(40, -4)):
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None,
                        with_paid_rebuilds=lambda built: built,
                        _announce_rebuild_pending=lambda cancelled: None),
        [tile], "P", 16, "", (True, True, False), 1)
    run._programs[tile] = tuple(program)
    run._next_step_index[tile] = index
    run._queue.clear()                    # the tile is past its queue
    return run


def test_mesh_and_masks_are_sent_beside_only_when_imagery_follows():
    full = ("vector", "mesh", "masks", "imagery")
    assert _run(full, 1)._objects_beside_locked((40, -4), "mesh")
    assert _run(full, 2)._objects_beside_locked((40, -4), "masks")
    assert not _run(full, 3)._objects_beside_locked((40, -4), "imagery")
    assert not _run(("vector", "mesh", "masks"), 1)._objects_beside_locked(
        (40, -4), "mesh")


def test_a_stop_between_steps_ends_a_child_whose_stage_may_run(monkeypatch):
    monkeypatch.setattr(parallel, "CANCEL_KILL_SECONDS", 0.01)
    run = _run(("vector", "mesh", "masks", "imagery"), 2)
    child = _Child((40, -4))
    run._children = [child]
    assert run.cancel_tile((40, -4))
    assert child.cancelling and child.terminated == 1
    assert child.tile == (40, -4), "reported stopped once it has exited"
