"""Twins for the on-demand follow-up of 2026-11-10 (#1992; owner: a tile
just built with imagery on demand stayed low-res at its airport):

* the airport cores read the graded airports from the tile's OWN patch
  folder (``O4_File_Names.patch_dir``, not that folder twice);
* the on-demand tiles are found in every place a tile may be: the build
  folder, the Tiles folder and Custom Scenery (a link to a tile already
  found is not given twice);
* when a run ends the session hands each tile it built to
  ``imagery_after_build``, which registers an on-demand tile's rows and
  lands its core squares at their tiers -- no X-Plane, no network here
  (the lander is a stub); a full-resolution build is left alone;
* the follow job writes its log line at start even with nothing to
  follow, and the status line says plainly there is nothing to follow;
* the Mac app starts the follow job by itself: at the engine session's
  start and when the world switch changes in Settings.
"""
from __future__ import annotations

import json
import os
import re
import types
from pathlib import Path

import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_OnDemand_Text as TEXT
import O4_Imagery_Tier_Plan as PLAN
import pytest
from o4_engine import imagery_after_build as AFTER
from o4_engine import imagery_follow as FOLLOW
from o4_engine import imagery_ondemand as ONDEMAND
from o4_engine import storage_redundant
from test_imagery_ondemand import LAT, LON, TILE, _centre, world  # noqa: F401

REPO = Path(__file__).resolve().parents[2]


def _graded(folder, lat, lon, icao="TEST"):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, icao + CORES.GRADED_SUFFIX), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump({"frame": {"origin": [lat, lon]}}, handle)


@pytest.fixture()
def patches(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Patch_dir", str(tmp_path / "Patches"))
    return tmp_path / "Patches"


def test_cores_read_the_tiles_own_patch_folder(patches):
    lat, lon = _centre(0)
    _graded(FNAMES.patch_dir(LAT, LON), lat, lon)
    assert CORES.airport_points(LAT, LON) == [("TEST", lat, lon)]


@pytest.fixture()
def roots(world, tmp_path, monkeypatch):  # noqa: F811
    """No other place than the ones a test makes; the tile carries its
    scenery file, as a built one does (the scan's witness)."""
    monkeypatch.setattr(FNAMES, "Tile_dir", str(tmp_path / "Tiles"))
    scenery = tmp_path / "Custom Scenery"
    scenery.mkdir()
    monkeypatch.setattr(storage_redundant, "_custom_scenery_dir",
                        lambda: str(scenery))
    return types.SimpleNamespace(world=world, scenery=scenery)


def _built(world):  # noqa: F811
    world.make(2).close()
    dsf = world.build / "Earth nav data" / FNAMES.long_latlon(LAT, LON)
    dsf = dsf.with_name(dsf.name + ".dsf")
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"XPLNEDSF")


def test_tiles_are_found_in_custom_scenery_too(roots, tmp_path):
    _built(roots.world)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    moved = roots.scenery / roots.world.build.name
    os.replace(roots.world.build, moved)             # built straight in
    found = list(ONDEMAND.on_demand_tiles(str(elsewhere)))
    assert found == [(str(moved), LAT, LON)]


def test_a_linked_tile_is_found_once(roots):
    _built(roots.world)
    os.symlink(roots.world.build, roots.scenery / roots.world.build.name)
    found = list(ONDEMAND.on_demand_tiles(""))
    assert [t[1:] for t in found] == [(LAT, LON)]


class Lander:
    """Lands nothing; answers the facts of the tier asked for."""

    def __init__(self):
        self.calls = []

    def __call__(self, row, tier):
        self.calls.append((row["name"], tier))
        return {"tier_px": PLAN.TIER_WIDTH[tier], "full_bytes": 1,
                "jpeg_path": None, "dds_cache_key": None, "network": False}


def _fresh_build(world, n=6):  # noqa: F811
    """A tile as a build leaves it: on disk, in no index."""
    world.make(n).close()
    conn = INDEX.open_index()
    INDEX.forget_tile(conn, TILE)
    conn.close()
    return [(str(world.build), LAT, LON)]


def test_after_build_registers_and_lands_the_cores(world, patches):  # noqa: F811
    tiles = _fresh_build(world)
    lat, lon = _centre(0)
    _graded(FNAMES.patch_dir(LAT, LON), lat, lon)
    lander = Lander()
    thread = AFTER.start(tiles, lander=lander)
    thread.join(30)
    conn = INDEX.open_index()
    rows = {r["name"]: r for r in INDEX.rows(conn, tile=TILE)}
    assert len(rows) == 6
    cores = [r for r in rows.values() if r["core"]]
    assert 0 < len(cores) < 6
    points = CORES.airport_points(LAT, LON)
    assert sorted(lander.calls) == sorted(
        (r["name"], CORES.core_tier(r, points)) for r in cores)
    for row in cores:
        assert row["state"] == "upgraded"
        assert row["tier_px"] == PLAN.TIER_WIDTH[CORES.core_tier(row, points)]
    log = (world.tmp / "data" / "logs" / "imagery_on_demand.log").read_text(
        encoding="utf-8")
    assert "registered=" + TILE in log and "landed=%d" % len(cores) in log
    # Done once: a second pass wants nothing.
    assert AFTER.core_wants(conn, tiles[0][0], LAT, LON) == []


def test_after_build_leaves_a_full_build_alone(world):  # noqa: F811
    tiles = _fresh_build(world)
    record = world.build / ("Ortho4XP_%s_imagery.json" % TILE)
    record.write_text(json.dumps({"on_demand": False}), encoding="utf-8",
                      newline="\n")
    assert AFTER.register_built(tiles) == []
    conn = INDEX.open_index()
    assert INDEX.rows(conn, tile=TILE) == []


def test_no_core_fetch_starts_while_a_build_runs(world, patches):  # noqa: F811
    tiles = _fresh_build(world)
    _graded(FNAMES.patch_dir(LAT, LON), *_centre(0))
    AFTER.register_built(tiles)
    lander = Lander()
    counts = AFTER.fetch_cores(tiles, lander=lander, busy=lambda: True)
    assert lander.calls == [] and counts["skipped"] == counts["wanted"] > 0


def test_the_session_hands_its_built_tiles_over(monkeypatch, tmp_path):
    from o4_engine.events import BuildDone, RunDone
    from o4_engine.session import EngineSession

    handed = []
    monkeypatch.setattr(AFTER, "start",
                        lambda tiles, busy=None: handed.append(list(tiles)))
    session = EngineSession()
    AFTER.watch(session)
    session._note_build_dirs([(LAT, LON)], str(tmp_path) + "/")
    session._emit(BuildDone(lat=LAT, lon=LON, ok=True))
    session._emit(BuildDone(lat=LAT + 1, lon=LON, ok=False, error="x"))
    session._emit(RunDone(done_count=1, error_count=1))
    assert handed == [[(FNAMES.build_dir(LAT, LON, str(tmp_path) + "/"),
                        LAT, LON)]]
    session._emit(RunDone(done_count=0, error_count=0))   # nothing new
    session._stepwise_run = True                          # a worker child
    session._emit(BuildDone(lat=LAT, lon=LON, ok=True))
    session._emit(RunDone(done_count=1, error_count=0))
    assert len(handed) == 1


def test_both_apps_watch_their_session():
    src = REPO / "Ortho4XP" / "src"
    for name in ("o4_engine/jsonl.py", "O4_Qt_GUI.py"):
        text = (src / name).read_text(encoding="utf-8")
        assert "_watch_built_tiles(" in text, name


def test_the_follow_job_logs_its_start_with_nothing_to_follow(tmp_path):
    reader = types.SimpleNamespace(read=lambda: None, resets=0)
    log = tmp_path / "od.log"
    job = FOLLOW.FollowJob(lambda e: None, reader=reader, lander=Lander(),
                           index_path=str(tmp_path / "index.sqlite"),
                           log_path=str(log), cap_bytes=1)
    job.open()
    job.tick()
    waiting = job.status()
    job.close()
    assert "start=0 textures=0" in log.read_text(encoding="utf-8")
    assert TEXT.follow_lines(waiting)[0] == TEXT.FOLLOW_NO_TILES


def test_the_line_says_when_there_is_nothing_to_follow():
    for state in TEXT.NO_TILES_STATES:
        assert TEXT.follow_lines({"state": state, "textures": 0})[0] == \
            TEXT.FOLLOW_NO_TILES
        assert TEXT.follow_lines({"state": state, "textures": 3})[0] != \
            TEXT.FOLLOW_NO_TILES
    assert TEXT.follow_lines({"state": "paused", "textures": 0,
                              "reason": "A build"})[0] != TEXT.FOLLOW_NO_TILES
    swift = (REPO / "Sources" / "SceneryKit" / "ImageryOnDemandText.swift"
             ).read_text(encoding="utf-8")
    states = re.search(r"noTilesStates: Set<String> = \[([^\]]*)\]", swift)
    assert set(re.findall(r'"(\w+)"', states.group(1))) == set(
        TEXT.NO_TILES_STATES)
    assert "s.textures == 0 { template = followNoTiles }" in swift


def test_the_mac_app_starts_following_by_itself():
    app = REPO / "Sources" / "XPTerrainBuilder"
    model = (app / "BuildModel.swift").read_text(encoding="utf-8")
    connect = model[model.index("private func connectIfNeeded()"):]
    connect = connect[:connect.index("\n    }\n")]
    assert connect.index("client = newClient") < connect.index(
        "syncImageryFollow()"), "the follow start needs the client"
    setter = model[model.index("func setConfigValue("):]
    setter = setter[:setter.index("\n    }\n")]
    assert "if name == Self.imageryOnDemandKey { syncImageryFollow() }" in setter
    follow = (app / "BuildModel+ImageryFollow.swift").read_text(encoding="utf-8")
    sync = follow[follow.index("func syncImageryFollow()"):]
    sync = sync[:sync.index("\n    }\n")]
    assert 'configValue(for: Self.imageryOnDemandKey) == .bool(true)' in sync
    assert "workingDir: context.workingDir, ifEnabled: true" in sync
    assert "stopImageryFollow" not in sync   # the switch never stops it (#2019)
    wire = (REPO / "Sources" / "SceneryKit" / "OrthoEngineClient.swift").read_text(
        encoding="utf-8")
    assert 'arguments["working_dir"] = workingDir' in wire
    assert 'arguments["if_enabled"] = true' in wire
    assert 'send(command: "imagery_follow_start"' in wire


def test_a_cover_texture_is_a_full_core_wherever_it_lies():
    far = {"zl": 18, "load_size_m": 1000.0, "centre_lat": 10.0,
           "centre_lon": 10.0}
    full = len(PLAN.TIER_WIDTH) - 1
    assert CORES.core_tier(far, [("T", 60.0, -136.0)], base_zl=16) == full
    assert CORES.core_tier(far, [("T", 60.0, -136.0)], base_zl=18) is None
    assert CORES.core_tier(dict(far, zl=16), [], base_zl=16) is None
    assert CORES.core_names([dict(far, name="a")], [], 16) == {"a"}
