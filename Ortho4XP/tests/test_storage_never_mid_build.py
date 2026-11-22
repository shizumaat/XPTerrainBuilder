"""Twins for the 2026-11-18 incident (app 1.0.558, tile +53+010: "a file
it needs was not found ... Data+53+010.node"): a storage pass must never
touch a tile mid-build (owner 2026-11-18T13:06Z).

* the cause: a parallel run's worker child offloaded after ITS tile, on
  a listing made before the vector step rewrote the tile's ``.node`` /
  ``.poly`` -- the pass moved the NEW files on the stale reading;
* the guard: a tile a live build holds (any session, the machine ledger's
  tile holds) keeps every file, and a worker child never offloads.

Synthetic: a fake data folder and tier, a temporary ledger; no build."""
from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Machine_Memory as MEMORY  # noqa: E402
import pytest  # noqa: E402
from o4_engine import storage_hold as HOLD  # noqa: E402
from o4_engine import storage_offload as OFFLOAD  # noqa: E402
from o4_engine import storage_priority as PRIORITY  # noqa: E402
from test_storage_floor import disk  # noqa: E402,F401
from test_storage_priority import BLOCK, _left, _tier, _tile, data, drive  # noqa: E402,F401
from test_storage_settings import root  # noqa: E402,F401


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv(MEMORY.ENV_DIR, str(tmp_path / "ledger"))
    monkeypatch.delenv(MEMORY.ENV_STEP_RESERVED, raising=False)
    HOLD._forget()
    yield
    HOLD._forget()


def test_a_file_rewritten_after_the_listing_is_never_moved(
        data, drive, disk, ledger, monkeypatch):  # noqa: F811
    """THE INCIDENT: the pass lists the tile's rebuild data as old (laid
    back from the tier with the tier copy's times); the vector step then
    rewrites it; the pass must not move the new file on the old reading."""
    _tier(monkeypatch, drive, 100 * BLOCK)
    tile = _tile(45, 7, 90)
    surveyed = PRIORITY._survey

    def survey_then_rewrite(now):
        out = surveyed(now)
        with open(tile["rebuild"], "wb") as handle:      # the vector step
            handle.write(b"\1" * (BLOCK + 1))
        return out
    monkeypatch.setattr(PRIORITY, "_survey", survey_then_rewrite)
    OFFLOAD.offload_now()
    assert "rebuild" in _left(tile)
    assert os.path.getsize(tile["rebuild"]) == BLOCK + 1
    assert "imagery" not in _left(tile)                  # the rest moved


def test_a_tile_a_live_build_holds_keeps_every_file(
        data, drive, disk, ledger, monkeypatch):  # noqa: F811
    _tier(monkeypatch, drive, 100 * BLOCK)
    held, other = _tile(45, 7, 90), _tile(48, 7, 90)   # no neighbour
    hold = MEMORY.hold_tile(45, 7)
    assert MEMORY.held_tiles() == {(45, 7)}
    OFFLOAD.offload_now()
    assert _left(held) == set(held)
    assert _left(other) == set()
    hold.release()
    HOLD._forget()
    assert MEMORY.held_tiles() == set()
    OFFLOAD.offload_now()
    assert _left(held) == set()


def test_a_session_holds_the_tile_it_builds_until_the_run_ends(ledger):
    from o4_engine.session import EngineSession
    session = EngineSession.__new__(EngineSession)
    session._tile_hold = None
    session._hold_tile((45, 7))
    assert MEMORY.held_tiles() == {(45, 7)}
    session._hold_tile((46, 7))                     # the next tile
    assert MEMORY.held_tiles() == {(46, 7)}
    session._hold_tile(None)                        # ``_run_finished``
    assert MEMORY.held_tiles() == set()


def test_a_worker_child_never_offloads(ledger, monkeypatch):
    """The cause: a child's ``RunDone`` is one tile of its parent's run."""
    subscribed = []
    session = SimpleNamespace(subscribe=subscribed.append, _building=False)
    monkeypatch.setenv(MEMORY.ENV_STEP_RESERVED, "1")
    OFFLOAD.watch(session)
    assert subscribed == []
    monkeypatch.delenv(MEMORY.ENV_STEP_RESERVED)
    OFFLOAD.watch(session)
    assert len(subscribed) == 1                     # the app's own engine


def test_held_holds_are_read_from_the_ledger_once_per_window(
        ledger, monkeypatch):
    calls = []
    monkeypatch.setattr(MEMORY, "held_tiles",
                        lambda: calls.append(1) or {(1, 2)})
    for _ in range(50):
        assert HOLD.held_tiles() == {(1, 2)}
    assert len(calls) == 1
    monkeypatch.setattr(HOLD, "_FRESH_S", 0.0)
    time.sleep(0.001)
    HOLD.held_tiles()
    assert len(calls) == 2
