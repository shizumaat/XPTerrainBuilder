"""THE MEMORY GUARD's twin (``airport/pool_memory.py``, issue #1980): a pool
whose worker grows past the ceiling stops with the NAMED error in seconds —
workers gone, no serial fall-back — the error is catalogued, the verdicts
name each ceiling, and the heartbeat phrase reads this build's memory.
Also the mechanism the guard was born from: the roof test's trim
(``obj8_grade._near_points``) is the multipoint buffer's region, built by
cascade.
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pytest

from auto_patch_v2.airport import obj8_grade as G
from auto_patch_v2.airport import pool as P
from auto_patch_v2.airport import pool_memory as M


# ── module-level tasks (a spawned worker imports them by name) ───────────

def _setup_hold(parent):
    return {"pid": os.getpid(), "parent": parent}


def _hold(state, t):
    """In a worker: take ~200 MB and keep it (a runaway reading)."""
    if state is not None and state.get("pid") != state.get("parent"):
        block = np.ones(25_000_000)                # 200 MB, every page touched
        time.sleep(60)
        return float(block[0])
    return t


def test_a_worker_past_the_ceiling_stops_the_stage_by_name(monkeypatch):
    monkeypatch.setattr(M, "WORKER_CEILING_GB", 0.15)
    monkeypatch.setattr(M, "CHECK_S", 0.2)
    said: list[str] = []
    t0 = time.monotonic()
    with P.WorkPool(_setup_hold, (os.getpid(),), workers=2, out=said.append) as p:
        with pytest.raises(M.MemoryCeilingError) as err:
            p.try_map(_hold, range(2), what="twin readings", unit="resources")
        pids = p.pids()
        assert not p.parallel and p.reason == "memory ceiling" and not p.fell_back
    assert time.monotonic() - t0 < 40.0            # never the 60 s task, never a stall
    assert pids == []                               # the workers were stopped
    msg = str(err.value)
    assert msg.startswith("twin readings: stopped before the computer runs out of memory")
    assert "one worker holds" in msg and err.value.reading.workers_gb
    assert any(s.startswith("[pool] MEMORY CEILING: twin readings") for s in said)
    assert not any("FELL BACK" in s for s in said)


def test_the_error_is_a_memory_error_with_its_own_catalogue_entry():
    import O4_Tile_Failures as F
    e = M.MemoryCeilingError("x")
    assert isinstance(e, MemoryError)
    assert F.code_for_exception(e) == "airport_memory_ceiling" in F.CATALOGUE
    assert F.record_fields(e)["code"] == "airport_memory_ceiling"


@pytest.mark.parametrize("reading,ram,share,word", [
    (M.Reading(1.0, (9.0,), 0.5), 128.0, 1, "one worker holds 9.0 GB"),
    (M.Reading(30.0, (7.0,) * 7, 0.5), 128.0, 1, "the build holds 79.0 GB"),
    (M.Reading(10.0, (5.0,), 0.5), 64.0, 4, "ceiling 9.6 GB"),
    (M.Reading(1.0, (1.0,), 0.03), 128.0, 1, "3 % of its memory free"),
    (M.Reading(1.0, (1.0,), None), None, 1, ""),
    (M.Reading(10.0, (7.9,) * 8, 0.4), 128.0, 1, ""),
])
def test_each_ceiling_is_named(reading, ram, share, word):
    got = M.breach(reading, ram, share)
    assert (word in got) if word else got == ""


def test_check_raises_with_the_reading_and_passes_under_every_ceiling():
    hot = M.Reading(2.0, (9.5,), 0.4)
    with pytest.raises(M.MemoryCeilingError) as err:
        M.check("pack partition: resource readings", [1], 128.0, 1, reader=lambda _p: hot)
    assert err.value.reading is hot and "resource readings" in str(err.value)
    cool = M.Reading(2.0, (1.0,), 0.4)
    assert M.check("x", [1], 128.0, 1, reader=lambda _p: cool) is cool


@pytest.mark.skipif(sys.platform == "win32", reason="ps reads POSIX; Windows reads ctypes")
def test_the_heartbeat_phrase_reads_this_process():
    from auto_patch import engine_v2
    r = M.read()
    assert r.parent_gb > 0.0 and r.workers_gb == ()
    assert M.describe().startswith("memory ")
    assert "memory " in engine_v2._activity()


# ── the mechanism (#1980): the roof test's trim ──────────────────────────

def test_near_points_is_the_multipoint_buffer_region():
    from shapely.geometry import MultiPoint
    rng = np.random.default_rng(1980)
    for n in (1, 7, 300):
        xy = rng.uniform(0.0, 20.0, (n, 2))
        xy = np.concatenate([xy, xy[: n // 3]])    # duplicates, as a mesh has
        old = MultiPoint(xy).buffer(3.0, join_style=2, mitre_limit=2.0)
        new = G._near_points(MultiPoint(xy), 3.0)
        assert new.normalize().equals_exact(old.normalize(), 1e-7)


def test_near_points_stays_bounded_on_a_dense_cloud():
    """12,824 lower vertices in a 343 m² mezzanine took a worker past
    20 GB through ``MultiPoint.buffer``; the cascade is seconds."""
    from shapely.geometry import MultiPoint
    rng = np.random.default_rng(1980)
    xy = rng.uniform(0.0, 18.5, (12_824, 2))
    t0 = time.monotonic()
    got = G._near_points(MultiPoint(xy), 3.0)
    assert time.monotonic() - t0 < 30.0
    assert got.area == pytest.approx(18.5 ** 2 + 4 * 18.5 * 3.0 + np.pi * 9.0, rel=0.01)
