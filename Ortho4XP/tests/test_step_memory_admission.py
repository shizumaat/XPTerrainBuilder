"""Twins for #2083: the tile scheduler projects a step's memory from the
tile's own recorded peak, falls back to a conservative default without
one, keeps a share of RAM free, and holds a heavy step while LIVE free
memory is short.  Synthetic: no worker process, no build.
"""
from __future__ import annotations

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
    # projected, two fit, the third waits.
    for tile in TILES:
        _record_vector_peak(tile, 12.0)
    run = _run(30.0)
    assert run._step_memory_estimate((10, 10), "vector") == pytest.approx(
        12.0 * step_memory.RECORDED_PEAK_MARGIN)
    assert len(_admit_all(run)) == 2


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
