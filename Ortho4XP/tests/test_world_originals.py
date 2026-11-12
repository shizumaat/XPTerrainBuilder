"""Twins for where Convert existing tiles keeps a LOCAL tile's folder
(owner 2026-11-12T13:42Z: "if the folders are still there it looks like
it didn't work"; ``o4_engine.world_originals``), offline on
``test_world_migrate``'s synthetic X-Plane folder in ``tmp_path``:

* a converted local tile leaves no folder and no row in Custom Scenery;
  its folder is whole in the work folder's ``originals/``, the World
  pack's tile is full, the journal names the kept folder and the
  on-demand index rows are written from it;
* Undo moves it back, files its row enabled and gives the World tile
  back; a name Custom Scenery already has is refused for that tile;
* ``tidy`` (``world-tidy-originals``) moves the folders an older run
  left in Custom Scenery: the dry run moves nothing, the run moves them;
* a run killed between the rename and the journal is finished by the
  next call; Undo from that state works;
* a tile that fails (no DSF) stays where it is and the summary names it
  with its reason.
"""
from __future__ import annotations

import os

import O4_Imagery_OnDemand_Index as INDEX
import O4_Scenery_Packs as SP
import O4_World_Pack as WP
from o4_engine import world_migrate as MIGRATE
from o4_engine import world_originals as ORIGINALS
from test_world_migrate import _hashes, _rows, xp  # noqa: F401

LOCAL = "zOrtho4XP_+46+008"
MANIFEST = "Ortho4XP_+46+008_imagery.json"


def _index_dirs(index: str) -> set:
    conn = INDEX.open_index(index)
    try:
        return {row.get("config_dir") or row.get("build_dir")
                for row in INDEX.rows(conn, tile="+46+008")}
    finally:
        conn.close()


def _files(folder: str) -> dict:
    """The folder's hashes but its imagery record (the layout key moves)."""
    return {k: v for k, v in _hashes(folder).items() if k != MANIFEST}


def _old_code(monkeypatch) -> None:
    """Convert as before 2026-11-12: the folder stays in Custom Scenery."""
    monkeypatch.setattr(ORIGINALS, "try_put_away", lambda *a, **k: None)


def test_remove_rows_drops_only_the_named_rows():
    lines = ["I", "SCENERY_PACK Custom Scenery/zOrtho4XP_+45+007/",
             "SCENERY_PACK_DISABLED Custom Scenery/zOrtho4XP_+46+008/",
             "SCENERY_PACK Custom Scenery/Other/"]
    assert SP.remove_rows(lines, ["zOrtho4XP_+46+008", "Nope"]) == \
        ["zOrtho4XP_+46+008"]
    assert lines == ["I", "SCENERY_PACK Custom Scenery/zOrtho4XP_+45+007/",
                     "SCENERY_PACK Custom Scenery/Other/"]


def test_convert_leaves_no_folder_and_undo_brings_it_back(xp):  # noqa: F811
    scenery, work = xp["scenery"], xp["work"]
    before = _files(os.path.join(scenery, LOCAL))
    MIGRATE.migrate(scenery, [LOCAL], index=xp["index"])
    kept = ORIGINALS.path_of(work, LOCAL)
    assert not os.path.lexists(os.path.join(scenery, LOCAL))
    assert LOCAL not in _rows(scenery)
    assert WP.world_tiles(xp["pack"])[(46, 8)] == "full"
    assert not WP.verify_tile(xp["pack"], 46, 8)["problems"]
    assert _files(kept) == before
    record = MIGRATE.Journal(work).get(LOCAL)
    assert record["original"] == record["config_dir"] == kept
    assert _index_dirs(xp["index"]) == {kept}
    back = MIGRATE.revert(scenery, [LOCAL], index=xp["index"])
    assert back == {"reverted": [LOCAL], "gone": [], "failed": []}
    assert os.path.isdir(os.path.join(scenery, LOCAL))
    assert not os.path.lexists(kept)
    assert _rows(scenery)[LOCAL] == "SCENERY_PACK"
    assert (46, 8) not in WP.world_tiles(xp["pack"])
    assert _index_dirs(xp["index"]) == {os.path.join(scenery, LOCAL)}
    assert _files(os.path.join(scenery, LOCAL)) == before


def test_undo_refuses_a_name_custom_scenery_already_has(xp):  # noqa: F811
    scenery = xp["scenery"]
    MIGRATE.migrate(scenery, [LOCAL], index=xp["index"])
    os.makedirs(os.path.join(scenery, LOCAL))           # someone else's
    back = MIGRATE.run_command(False, True, [LOCAL], scenery_dir=scenery)
    assert back["reverted"] == [] and back["failed"][0]["name"] == LOCAL
    assert "already has" in back["summary"]
    assert os.path.isdir(ORIGINALS.path_of(xp["work"], LOCAL))
    assert MIGRATE.Journal(xp["work"]).get(LOCAL)["state"] == "done"
    assert WP.world_tiles(xp["pack"])[(46, 8)] == "full"


def test_tidy_moves_what_the_old_code_left(xp, monkeypatch):  # noqa: F811
    scenery, work = xp["scenery"], xp["work"]
    with monkeypatch.context() as patch:
        _old_code(patch)
        MIGRATE.migrate(scenery, [LOCAL], index=xp["index"])
    assert os.path.isdir(os.path.join(scenery, LOCAL))
    assert _rows(scenery)[LOCAL] == "SCENERY_PACK_DISABLED"
    assert _index_dirs(xp["index"]) == {os.path.realpath(
        os.path.join(scenery, LOCAL))}
    dry = ORIGINALS.tidy(scenery, dry_run=True, index=xp["index"])
    assert dry["moved"] == [LOCAL] and dry["summary"].startswith("Would move 1")
    assert os.path.isdir(os.path.join(scenery, LOCAL))
    assert not os.path.exists(os.path.join(work, ORIGINALS.ORIGINALS))
    run = ORIGINALS.tidy(scenery, dry_run=False, index=xp["index"])
    kept = ORIGINALS.path_of(work, LOCAL)
    assert run["moved"] == [LOCAL] and run["failed"] == []
    assert not os.path.lexists(os.path.join(scenery, LOCAL))
    assert LOCAL not in _rows(scenery)
    record = MIGRATE.Journal(work).get(LOCAL)
    assert record["original"] == record["config_dir"] == kept
    assert _index_dirs(xp["index"]) == {kept}
    again = ORIGINALS.tidy(scenery, dry_run=False, index=xp["index"])
    assert again["moved"] == again["settled"] == []


def test_tidy_from_the_command_line(xp, monkeypatch, capsys):  # noqa: F811
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools", "ondemand_convert.py")
    spec = importlib.util.spec_from_file_location("ondemand_convert", path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    with monkeypatch.context() as patch:
        _old_code(patch)
        MIGRATE.migrate(xp["scenery"], [LOCAL], index=xp["index"])
    args = ["--custom-scenery", xp["scenery"], "world-tidy-originals"]
    assert tool.main(args) == 0
    assert "Would move 1" in capsys.readouterr().out
    assert os.path.isdir(os.path.join(xp["scenery"], LOCAL))
    assert tool.main(args + ["--run"]) == 0
    assert "Moved 1" in capsys.readouterr().out
    assert os.path.isdir(ORIGINALS.path_of(xp["work"], LOCAL))


def test_a_run_killed_after_the_rename_is_finished(xp, monkeypatch):  # noqa: F811
    """The rename happened, the journal and the ini did not: the next run
    (or tidy) settles it, and Undo from that state brings it back."""
    scenery, work = xp["scenery"], xp["work"]
    with monkeypatch.context() as patch:
        _old_code(patch)
        MIGRATE.migrate(scenery, [LOCAL], index=xp["index"])
    kept = ORIGINALS.path_of(work, LOCAL)
    os.makedirs(os.path.dirname(kept))
    os.rename(os.path.join(scenery, LOCAL), kept)           # then killed
    assert "original" not in MIGRATE.Journal(work).get(LOCAL)
    dry = ORIGINALS.tidy(scenery, dry_run=True)
    assert dry["moved"] == [] and dry["settled"] == [LOCAL]
    MIGRATE.migrate(scenery, index=xp["index"])         # the next run settles
    record = MIGRATE.Journal(work).get(LOCAL)
    assert record["original"] == record["config_dir"] == kept
    assert LOCAL not in _rows(scenery)
    assert _index_dirs(xp["index"]) == {kept}
    back = MIGRATE.revert(scenery, [LOCAL], index=xp["index"])
    assert back["reverted"] == [LOCAL]
    assert os.path.isdir(os.path.join(scenery, LOCAL))
    assert _rows(scenery)[LOCAL] == "SCENERY_PACK"


def test_undo_killed_after_the_rename_back_finishes(xp):  # noqa: F811
    scenery, work = xp["scenery"], xp["work"]
    MIGRATE.migrate(scenery, [LOCAL], index=xp["index"])
    os.rename(ORIGINALS.path_of(work, LOCAL), os.path.join(scenery, LOCAL))
    back = MIGRATE.revert(scenery, [LOCAL], index=xp["index"])
    assert back["reverted"] == [LOCAL]
    assert _rows(scenery)[LOCAL] == "SCENERY_PACK"
    assert _index_dirs(xp["index"]) == {os.path.join(scenery, LOCAL)}


def test_a_failed_tile_stays_and_is_named(xp):  # noqa: F811
    scenery = xp["scenery"]
    os.remove(os.path.join(scenery, LOCAL, WP.dsf_relpath(46, 8)))
    result = MIGRATE.run_command(False, tiles=[LOCAL], scenery_dir=scenery)
    assert [row["name"] for row in result["failed"]] == [LOCAL]
    assert f"Not converted (left in Custom Scenery): {LOCAL} (no DSF" \
        in result["summary"]
    assert os.path.isdir(os.path.join(scenery, LOCAL))
    assert _rows(scenery)[LOCAL] == "SCENERY_PACK"
    assert not os.path.exists(ORIGINALS.path_of(xp["work"], LOCAL))


def test_a_rechosen_local_tile_stays_kept_and_free_space_deletes_it(xp):  # noqa: F811
    """``world_rechoose`` of a kept local tile: dynamic, its folder still
    in ``originals/`` with no row filed; Free space deletes it there."""
    from o4_engine import world_rechoose as RECHOOSE
    scenery, work = xp["scenery"], xp["work"]
    MIGRATE.migrate(scenery, [LOCAL], index=xp["index"])
    kept = ORIGINALS.path_of(work, LOCAL)
    out = RECHOOSE.rechoose(scenery, [LOCAL], index=xp["index"])
    assert out["rechosen"] == [LOCAL] and not out["failed"]
    assert MIGRATE.Journal(work).get(LOCAL)["state"] == "dynamic"
    assert os.path.isdir(kept) and LOCAL not in _rows(scenery)
    assert not os.path.lexists(os.path.join(scenery, LOCAL))
    assert WP.world_tiles(xp["pack"])[(46, 8)] == "placeholder"
    freed = MIGRATE.run_command(False, scenery_dir=scenery, purge=True)
    assert freed["removed"] == [LOCAL] and freed["freed_bytes"] > 0
    assert not os.path.exists(kept)
    back = MIGRATE.revert(scenery, index=xp["index"])
    assert back["gone"] == [LOCAL] and LOCAL not in _rows(scenery)
