"""Twins for MAKE ROOM BEFORE A RUN (owner 2026-11-18T13:32Z,
``o4_engine.storage_room``): a run needing more than the disk has frees
the difference before its first tile starts -- offload, then trim -- and
never touches its own tiles; a run that fits frees nothing; one that
cannot be given enough room says so and starts anyway.  Synthetic: the
fake disk of ``test_storage_floor``, no build."""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import parallel  # noqa: E402
from o4_engine import storage_room as ROOM  # noqa: E402
from test_storage_floor import _raw, _track, disk  # noqa: E402,F401
from test_storage_priority import BLOCK, _left, _log, _tier, _tile, data, drive  # noqa: E402,F401
from test_storage_settings import root  # noqa: E402,F401

_NO_SCAN = {"budget": {"budget_set": False}}


def test_a_run_needing_more_than_free_makes_room_but_never_from_its_own_tiles(
        data, drive, disk, monkeypatch, capsys):  # noqa: F811
    _tier(monkeypatch, drive, 100 * BLOCK)
    other = _tile(45, 7, 90)
    own = _tile(50, 7, 400)                 # older: cleared first otherwise
    _track(disk, other, own)
    out = ROOM._make_room(2 * BLOCK, [(50, 7)], raw=_raw(BLOCK), scan=_NO_SCAN)
    assert out["to_free"] == 3 * BLOCK and out["freed"] >= 3 * BLOCK
    assert out["short"] == 0
    assert _left(own) == set(own)                   # the run's tile: kept
    assert len(_left(other)) < len(other)           # room came from another
    assert "deleted" not in _log()                  # the offload sufficed
    line = capsys.readouterr().out
    assert "making room: needs 0.0 GB, freed 0.0 GB (budget not set)" in line


def test_a_run_that_fits_does_nothing(data, drive, disk, monkeypatch, capsys):  # noqa: F811
    _tier(monkeypatch, drive, 100 * BLOCK)
    other = _tile(45, 7, 90)
    _track(disk, other)
    disk["base"] = 10 * BLOCK
    out = ROOM._make_room(2 * BLOCK, [(50, 7)], raw=_raw(BLOCK), scan=_NO_SCAN)
    assert out["to_free"] == 0 and out["freed"] == 0
    assert _left(other) == set(other)
    assert "making room" not in capsys.readouterr().out


def test_a_set_budget_the_run_would_exceed_makes_room_too(
        data, drive, disk, monkeypatch):  # noqa: F811
    _tier(monkeypatch, drive, 100 * BLOCK)
    other = _tile(45, 7, 90)
    _track(disk, other)
    disk["base"] = 100 * BLOCK                      # the disk has room
    scan = {"budget": {"budget_set": True, "budget_bytes": 10 * BLOCK,
                       "used_bytes": 9 * BLOCK}}
    out = ROOM._make_room(2 * BLOCK, [(50, 7)], raw=_raw(BLOCK), scan=scan)
    assert out["to_free"] == BLOCK and out["freed"] >= BLOCK
    assert out["budget"] == 10 * BLOCK


def test_it_cannot_free_enough_so_it_says_so_and_the_run_starts(
        data, disk, monkeypatch, capsys):  # noqa: F811
    own = _tile(50, 7, 400)                 # nothing else to free; no tier
    _track(disk, own)
    out = ROOM._make_room(100 * BLOCK, [(50, 7)], raw=_raw(BLOCK),
                         scan=_NO_SCAN)
    assert out["short"] > 0 and _left(own) == set(own)
    printed = capsys.readouterr().out
    assert "making room: needs" in printed
    assert "starting anyway" in printed
    # ... and the parallel run makes room BEFORE it spawns, then goes on
    order = []
    monkeypatch.setattr(ROOM, "before_run",
                        lambda *a, **k: order.append("room") or out)
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        [(50, 7)], "P", 16, "", (True, True, False), 2)
    monkeypatch.setattr(run, "_spawn_child",
                        lambda: order.append("spawn") and None)
    run.start()
    assert order == ["room", "spawn"]


def test_need_counts_each_tiles_estimate_and_skips_a_failed_one(monkeypatch):
    from o4_engine import plan_estimate

    def estimate(lat, lon, *a):
        if lat == 2:
            raise OSError("unreadable")
        return {"tile_bytes": [1, 10], "cache_bytes": [2, 20]}
    monkeypatch.setattr(plan_estimate, "tile_estimate", estimate)
    assert ROOM._need_bytes([(1, 1), (2, 2), (3, 3)], "P", 16, "") == 60


def test_no_room_is_made_in_a_harness_session_or_a_worker_child(monkeypatch):
    import O4_Machine_Memory as MEMORY
    called = []
    monkeypatch.setattr(ROOM, "_make_room", lambda *a, **k: called.append(1))
    monkeypatch.setenv(ROOM.FLOOR.ENV_UNGATED, "1")
    assert ROOM.before_run([(1, 1)], "P", 16, "") is None
    monkeypatch.delenv(ROOM.FLOOR.ENV_UNGATED)
    monkeypatch.setenv(MEMORY.ENV_STEP_RESERVED, "1")
    assert ROOM.before_run([(1, 1)], "P", 16, "") is None
    assert not called
