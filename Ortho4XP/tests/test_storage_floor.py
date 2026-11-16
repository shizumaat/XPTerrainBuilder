"""Twins for #2103: the disk's free-space floor.  Under it, the storage
manager offloads to a tier before it trims, in tile priority order
(RULINGS 2026-11-14i), never touches a flyable file or the dev corpus
(#2093), and a build step held for the floor starts once it is met.
Synthetic: a fake disk (free space follows the files that left the data
folder), no build."""
from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import pytest  # noqa: E402
from o4_engine import parallel  # noqa: E402
from o4_engine import storage_floor as FLOOR  # noqa: E402
from o4_engine import storage_priority as PRIORITY  # noqa: E402
from o4_engine import storage_tier_data as TIER_DATA  # noqa: E402
from o4_engine import storage_tiers as TIERS  # noqa: E402
from test_step_memory_admission import _Child  # noqa: E402
from test_storage_priority import BLOCK, _left, _log, _tier, _tile, data, drive  # noqa: E402,F401
from test_storage_settings import _write, root  # noqa: E402,F401


@pytest.fixture
def disk(data, monkeypatch):  # noqa: F811
    """A disk whose free space is ``base`` plus whatever left the data
    folder; the floor gated, with no margin (whole blocks are exact)."""
    monkeypatch.delenv(FLOOR.ENV_UNGATED, raising=False)
    monkeypatch.setattr(FLOOR, "MARGIN_BYTES", 0)
    monkeypatch.setattr(FLOOR, "_STATE", {"running": False, "last_at": 0.0,
                                          "last_freed": -1})
    state = {"base": 0, "files": []}

    def free(folder=None):
        gone = sum(BLOCK for path in state["files"] if not os.path.exists(path))
        return state["base"] + gone
    monkeypatch.setattr(FLOOR, "free_bytes", free)
    return state


def _raw(floor_bytes):
    return {FLOOR.SETTING: floor_bytes / 1e9}


def _track(disk, *tiles):
    for tile in tiles:
        disk["files"] += list(tile.values())


def test_floor_setting_defaults_to_60_gb_and_zero_is_off():
    assert FLOOR.floor_bytes({}) == 60 * 10**9
    assert FLOOR.floor_bytes({FLOOR.SETTING: "0"}) == 0
    assert FLOOR.floor_bytes({FLOOR.SETTING: "120"}) == 120 * 10**9


def test_floor_trip_offloads_to_the_tier_before_anything_is_deleted(
        data, drive, disk, monkeypatch):  # noqa: F811
    _tier(monkeypatch, drive, 100 * BLOCK)
    old = _tile(45, 7, 90)
    _track(disk, old)
    out = FLOOR.relieve(raw=_raw(2 * BLOCK))
    assert out["ran"] and out["free_after"] >= 2 * BLOCK
    assert len(out["passes"]) == 1                  # the offload sufficed
    assert _left(old) == set(old) - {"imagery", "masks"}
    assert os.path.isfile(TIER_DATA._target(drive, FNAMES.Imagery_dir,
                                            old["imagery"]))
    assert "deleted" not in _log() and "free-space floor, offload" in _log()


def test_trim_follows_only_when_the_tier_is_full(
        data, drive, disk, monkeypatch):  # noqa: F811
    _tier(monkeypatch, drive, 100 * BLOCK)
    taken = []                                      # room for one file
    monkeypatch.setattr(TIER_DATA, "_make_room",
                        lambda *a: taken.append(1) or len(taken) == 1)
    old = _tile(45, 7, 90)
    _track(disk, old)
    out = FLOOR.relieve(raw=_raw(3 * BLOCK))
    assert len(out["passes"]) == 2 and out["free_after"] >= 3 * BLOCK
    log = _log()
    assert log.index("moved") < log.index("deleted")
    assert os.path.isfile(TIER_DATA._target(drive, FNAMES.Imagery_dir,
                                            old["imagery"]))   # offloaded
    assert "imagery" not in _left(old)


def test_relief_honours_tile_priority(data, drive, disk, monkeypatch):  # noqa: F811
    _tier(monkeypatch, drive, 100 * BLOCK)
    old, recent, building = _tile(45, 7, 90), _tile(46, 7, 20), _tile(47, 7, 90)
    PRIORITY.note_session([(47, 7)])
    _track(disk, old, recent, building)
    FLOOR.relieve(raw=_raw(5 * BLOCK))
    assert _left(old) == set()                      # the older tile first
    assert _left(recent) == set(recent)
    assert _left(building) == set(building)         # this session's: kept


def test_relief_never_moves_a_flyable_file(data, drive, disk, monkeypatch):  # noqa: F811
    _tier(monkeypatch, drive, 100 * BLOCK)
    dsf = _write(os.path.join(FNAMES.Tile_dir, "zOrtho4XP_+45+007",
                              "Earth nav data", "+40+000", "+45+007.dsf"),
                 BLOCK, 400)
    old = _tile(45, 7, 90)
    _track(disk, old)
    FLOOR.relieve(raw=_raw(100 * BLOCK))            # more than there is
    assert os.path.isfile(dsf)
    assert "still under the floor" in _log()


def test_relief_never_touches_the_dev_corpus(data, drive, disk, monkeypatch):  # noqa: F811
    os.makedirs(os.path.join(str(data), FLOOR.CORPUS_MARKER))
    _tier(monkeypatch, drive, 100 * BLOCK)
    old = _tile(45, 7, 90)
    _track(disk, old)
    FLOOR.relieve(raw=_raw(100 * BLOCK))
    spared = {"elevation", "osm", "imagery"}        # Elevation/OSM/Orthophotos
    assert spared <= _left(old)
    assert "rebuild" not in _left(old)              # not corpus: offloaded
    assert not os.path.exists(os.path.join(drive, TIERS.TIER_DIR,
                                           "Elevation_data"))


def test_a_mounted_corpus_folder_is_spared_through_its_link(tmp_path):
    corpus = tmp_path / "corpus"
    (corpus / FLOOR.CORPUS_MARKER).mkdir(parents=True)
    (corpus / "Elevation_data").mkdir()
    lane = tmp_path / "lane"
    lane.mkdir()
    os.symlink(corpus / "Elevation_data", lane / "Elevation_data")
    (lane / "OSM_data").mkdir()                     # lane-local: not spared
    roots = FLOOR.corpus_roots(str(lane))
    assert str(lane / "Elevation_data") in roots
    assert not any(r.endswith("OSM_data") for r in roots)


# ------------------------------------------------------------- scheduler
def test_held_step_waits_visibly_and_resumes_after_offload(monkeypatch):
    monkeypatch.delenv(FLOOR.ENV_UNGATED, raising=False)
    disk = {"free": 10 * 10**9}
    monkeypatch.setattr(FLOOR, "free_bytes", lambda folder=None: disk["free"])
    monkeypatch.setattr(FLOOR, "floor_bytes", lambda raw=None: 60 * 10**9)
    reliefs = []
    monkeypatch.setattr(FLOOR, "relieve_async",
                        lambda abort=None: reliefs.append(1) or True)
    monkeypatch.setattr(parallel.ParallelBuildRun, "DISK_CHECK_SECONDS", 0.0)
    events = []
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=events.append, _run_finished=lambda: None),
        [(10, 10)], "P", 16, "", (True, False, False), 2)
    child = _Child()
    run._children.append(child)
    with run._lock:
        assert run._start_new_tile_locked(child) is False
    assert reliefs                                  # the relief started
    run._announce_memory_waits()
    (wait,) = [e for e in events if type(e).__name__ == "MemoryWait"]
    assert wait.reason == FLOOR.REASON_DISK and not wait.resolved
    assert wait.message.startswith("Waiting for disk space: 10 GB free, "
                                   "keeping at least 60 GB")
    disk["free"] = 75 * 10**9                       # the offload moved data
    with run._lock:
        run._dispatch_locked()
    assert child.running_step == "vector"
    run._announce_memory_waits()
    assert [e for e in events if type(e).__name__ == "MemoryWait"][-1].resolved


def test_corpus_dirs_twin_the_harness_mounts():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools",
                                    "harness"))
    import shared_repo_guard as GUARD
    assert tuple(FLOOR.CORPUS_DIRS) == tuple(GUARD.SHARED_DATA_DIRS)


def test_protected_tiles_are_moved_to_the_tier_never_deleted(
        data, drive, disk, monkeypatch):  # noqa: F811
    """Recent and this session's tiles are most of what grows: under the
    floor their data MOVES to the tier (kept), the session's build inputs
    stay, and the trim pass still deletes none of it."""
    _tier(monkeypatch, drive, 100 * BLOCK)
    recent, building = _tile(46, 7, 3), _tile(47, 7, 2)
    PRIORITY.note_session([(47, 7)])
    _track(disk, recent, building)
    out = FLOOR.relieve(raw=_raw(100 * BLOCK))      # more than there is
    # All of it moved, but its elevation: the neighbour raster the
    # session's build reads (an input).
    assert _left(recent) == {"elevation"}
    for kind in set(recent) - {"elevation"}:
        store = {"imagery": FNAMES.Imagery_dir, "masks": FNAMES.masks_root(),
                "osm": FNAMES.OSM_dir, "elevation": FNAMES.Elevation_dir,
                "rebuild": FNAMES.rebuild_root()}[kind]
        assert os.path.isfile(TIER_DATA._target(drive, store, recent[kind]))
    assert {"elevation", "osm"} <= _left(building)  # its build's inputs
    assert "rebuild" not in _left(building)         # moved after `recent`
    assert "deleted" not in _log()                  # nothing protected deleted
    assert len(out["passes"]) == 2


def test_without_a_tier_protected_tiles_lose_nothing(data, disk):  # noqa: F811
    recent = _tile(46, 7, 3)
    _track(disk, recent)
    FLOOR.relieve(raw=_raw(100 * BLOCK))
    assert _left(recent) == set(recent)


# ------------------------------------------- RULINGS 2026-11-16c offload
def test_after_a_build_everything_movable_lives_on_the_tier(
        data, drive, disk, monkeypatch):  # noqa: F811
    """Not only under pressure: every cache file X-Plane does not read
    moves, the recent and favourite tiles' too; flyable files stay."""
    from o4_engine import storage_offload as OFFLOAD
    _tier(monkeypatch, drive, 100 * BLOCK)
    old, recent = _tile(45, 7, 90), _tile(46, 7, 2)
    dsf = _write(os.path.join(FNAMES.Tile_dir, "zOrtho4XP_+45+007",
                              "Earth nav data", "+40+000", "+45+007.dsf"),
                 BLOCK, 400)
    out = OFFLOAD.offload_now()
    assert out["ran"] and out["files"] == 10
    assert _left(old) == set() and _left(recent) == set()
    assert os.path.isfile(dsf)
    assert "deleted" not in _log()


def test_offload_keeps_the_running_builds_inputs_and_the_corpus(
        data, drive, disk, monkeypatch):  # noqa: F811
    from o4_engine import storage as ST
    _tier(monkeypatch, drive, 100 * BLOCK)
    tile = _tile(45, 7, 90)
    sweep = ST._Sweep(False, "t", None)
    sweep.tier_only = True
    PRIORITY.offload(1 << 62, sweep, time.time(), keep_tiles=[(45, 7)])
    assert {"elevation", "osm"} <= _left(tile)       # its build reads them
    assert "rebuild" not in _left(tile)
    os.makedirs(os.path.join(str(data), FLOOR.CORPUS_MARKER))
    other = _tile(46, 7, 90)
    from o4_engine import storage_offload as OFFLOAD
    OFFLOAD.offload_now()
    assert {"elevation", "osm", "imagery"} <= _left(other)   # harness-pinned
    assert "rebuild" not in _left(other)                     # app-owned


def test_no_offload_without_a_mounted_tier_or_in_a_harness_session(
        data, disk, monkeypatch):  # noqa: F811
    from o4_engine import storage_offload as OFFLOAD
    tile = _tile(45, 7, 90)
    assert not OFFLOAD.offload_now()["ran"]
    monkeypatch.setenv(FLOOR.ENV_UNGATED, "1")
    monkeypatch.setattr(OFFLOAD, "_tier_mounted", lambda: True)
    assert not OFFLOAD.offload_now()["ran"]
    assert _left(tile) == set(tile)


def test_a_sweep_that_is_not_tier_only_may_not_offload():
    from o4_engine import storage as ST
    with pytest.raises(ValueError):
        PRIORITY.offload(1, ST._Sweep(False, "t", None), time.time())
