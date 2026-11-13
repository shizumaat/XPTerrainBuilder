"""Twins of #2047 (``o4_engine.world_adopt_supersede``): a full build of
ours that swaps into the World pack supersedes the tile's adopt record from
Convert -- the journal stops saying ``adopted``, the build folder's adopted
stamp reads as none, the adopted package and the Convert copy's stamp are
kept (history, Undo) -- and ``world_state`` reads the DSF first, so the map
and the Library say "built here".  The start's one-time correction finds
the tiles already rebuilt, is idempotent and backs the journal up first.
All on ``tmp_path``; nothing touches a real install."""
from __future__ import annotations

import json
from pathlib import Path

import O4_DSF_Binary as DSFB
import O4_Tile_Info as TINFO
import O4_World_Pack as WP
import pytest
from o4_engine import world_adopt_supersede as SUPERSEDE
from o4_engine import world_commands as WORLD
from o4_engine import world_publish as PUBLISH
from o4_engine import world_state as WS
from o4_engine.world_migrate import WORK_DIR_NAME, Journal

HERE_AGENT = "XPTerrainBuilder 1.0.504 (engine 1.50.1902) [world full]"
OTHER_AGENT = "Ortho4XP [world full]"
REBUILT, KEPT = (-23, -44), (8, 38)


def _name(tile) -> str:
    return "zOrtho4XP_" + WP.tile_name(*tile)


def _dsf(pack: Path, tile, agent: str) -> None:
    path = pack / WP.dsf_relpath(*tile)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(DSFB.placeholder_bytes(*tile, agent))


def _stamp(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / TINFO.ADOPTED_STAMP
    path.write_text('{"adopted": "2026-11-12T22:05:14Z", "built_by": "%s"}'
                    % OTHER_AGENT, encoding="utf-8", newline="\n")
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Two tiles Convert adopted: REBUILT now holds a full build of ours,
    KEPT still the other tool's mesh."""
    logged = []
    monkeypatch.setattr(WORLD, "write_log", logged.append)
    scenery = tmp_path / "X-Plane 12" / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    pack.mkdir(parents=True)
    (pack / WP.MARKER).write_text("{}", encoding="utf-8", newline="\n")
    work = scenery.parent / WORK_DIR_NAME
    package = pack / "XPTerrainBuilder_packages" / "-23-044_adopted.xptb"
    package.parent.mkdir(parents=True)
    package.write_bytes(b"xptb")
    builds = pack / "XPTerrainBuilder_tiles"
    journal = {}
    for tile, agent in ((REBUILT, HERE_AGENT), (KEPT, OTHER_AGENT)):
        _dsf(pack, tile, agent)
        lean = work / "lean" / _name(tile)
        _stamp(lean)
        _stamp(builds / _name(tile))
        journal[_name(tile)] = {"state": "done", "kind": "link",
                                "adopted": True, "built_by": OTHER_AGENT,
                                "config_dir": str(lean),
                                "package": str(package)}
    (work / "journal.json").write_text(json.dumps(journal), encoding="utf-8",
                                       newline="\n")
    return {"scenery": str(scenery), "work": work, "builds": builds,
            "package": package, "logged": logged}


def _build_of(world):
    return lambda lat, lon: str(world["builds"] / _name((lat, lon)))


def test_world_state_reads_the_dsf_first(world):
    got = WS.read_world(world["scenery"], index_path="")
    assert got[REBUILT].origin == TINFO.ORIGIN_HERE
    assert got[KEPT].origin == TINFO.ORIGIN_ADOPTED
    assert WS.read_tile(world["scenery"], REBUILT).origin == TINFO.ORIGIN_HERE


def test_publish_supersedes_the_adopt_record(world):
    build = world["builds"] / _name(REBUILT)
    PUBLISH._supersede(world["scenery"], str(build), *REBUILT)
    record = Journal(str(world["work"])).get(_name(REBUILT))
    assert record["adopted"] is False
    assert record["superseded_by"] == HERE_AGENT and record["superseded"]
    assert record["package"] == str(world["package"])     # history kept
    assert world["package"].read_bytes() == b"xptb"
    assert TINFO.adopted_record(str(build)) == {}
    stamp = json.loads((build / TINFO.ADOPTED_STAMP).read_text("utf-8"))
    assert stamp["adopted"] and stamp["superseded_by"] == HERE_AGENT
    # the Convert copy (Undo's source) keeps its stamp
    assert TINFO.adopted_record(record["config_dir"])["adopted"]
    assert world["logged"][-1]["adopt_superseded"] == ["-23-044"]


def test_another_tools_mesh_is_left_adopted(world):
    build = world["builds"] / _name(KEPT)
    assert SUPERSEDE.supersede(world["scenery"], str(build), *KEPT) == {
        "journal": False, "stamp": False}
    assert Journal(str(world["work"])).get(_name(KEPT))["adopted"] is True
    assert TINFO.adopted_record(str(build))


def test_no_journal_write_while_a_convert_run_holds_it(world):
    from o4_engine import world_migrate as MIGRATE
    with MIGRATE.active_run():
        assert SUPERSEDE.correct(world["scenery"]) == {"tiles": [],
                                                       "backup": None}
        out = SUPERSEDE.supersede(world["scenery"], "", *REBUILT)
    assert out == {"journal": False, "stamp": False}
    assert Journal(str(world["work"])).get(_name(REBUILT))["adopted"] is True


def test_start_correction_is_one_time_and_idempotent(world):
    journal = world["work"] / "journal.json"
    before = journal.read_bytes()
    listed = SUPERSEDE.correct(world["scenery"], dry_run=True,
                               build_dir_of=_build_of(world))
    assert listed == {"tiles": [_name(REBUILT)], "backup": None}
    assert journal.read_bytes() == before                   # nothing written
    out = SUPERSEDE.correct(world["scenery"], build_dir_of=_build_of(world))
    assert out["tiles"] == [_name(REBUILT)]
    assert Path(out["backup"]).read_bytes() == before
    assert out["backup"].endswith("-before-supersede")
    records = Journal(str(world["work"])).records
    assert records[_name(REBUILT)]["adopted"] is False
    assert records[_name(KEPT)]["adopted"] is True
    assert TINFO.adopted_record(str(world["builds"] / _name(REBUILT))) == {}
    again = SUPERSEDE.correct(world["scenery"], build_dir_of=_build_of(world))
    assert again == {"tiles": [], "backup": None}


def test_the_apps_start_runs_the_correction(world, monkeypatch):
    seen = []
    monkeypatch.setattr(SUPERSEDE, "correct",
                        lambda d, dry_run: seen.append(dry_run) or {"tiles": ["t"]})
    assert WORLD._supersede_rebuilt(world["scenery"], dry_run=False) == ["t"]
    assert seen == [False]
    out = WORLD.world_onboard(world["scenery"])             # a bare call lists
    assert out["superseded"] == ["t"] and seen[-1] is True


def test_the_publish_swap_calls_it():
    import inspect
    assert "_supersede(scenery_dir, build_dir, lat, lon)" in inspect.getsource(
        PUBLISH._after_swap)
