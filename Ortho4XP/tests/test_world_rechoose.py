"""Twins for the Convert existing tiles incident fixes (app 1.0.492,
2026-11-11) and for choosing again (``o4_engine.world_rechoose``),
offline on ``test_world_migrate``'s synthetic X-Plane folder in
``tmp_path`` (never the real install or a real drive):

* a row another program dropped is filed again: a run disables it, Undo
  enables it (a row is disabled, never removed);
* the World pack's folder gone mid-run: nothing more is retired or moved
  (every link stays), the result and the World status count the
  converted tiles it lacks, and Undo still gives every tile back;
* a tile that fails keeps its reasons in its journal record;
* ``tidy_scenery_packs`` waits while a run changes the ini;
* rechoose: kept tiles another tool built become dynamic (placeholder in
  the pack, link removed, journal ``rechosen``), ours stay kept and are
  packaged first; the dry run counts only; Undo round-trips.
"""
from __future__ import annotations

import os
import shutil

import O4_Scenery_Packs as SP
import O4_Scenery_Packs_Tidy as TIDY
import O4_World_Pack as WP
from o4_engine import world_commands as WORLD
from o4_engine import world_migrate as MIGRATE
from o4_engine import world_rechoose as RECHOOSE
from o4_engine import world_retire as RETIRE
from test_world_migrate import _hashes, _rows, xp  # noqa: F401

LINK, LOCAL = "zOrtho4XP_+45+007", "zOrtho4XP_+46+008"


def _drop_rows(scenery: str, names) -> None:
    """What the Mac app's reconcile did on 2026-11-11: rows removed."""
    path = os.path.join(scenery, SP.INI_FILENAME)
    lines, newline = SP.read_ini_lines(path)
    lines = [ln for ln in lines
             if not any(f"Custom Scenery/{n}/" in ln for n in names)]
    SP.write_ini_lines(path, lines, newline)


def test_a_missing_row_is_filed_when_asked():
    lines = ["I", "SCENERY_PACK Custom Scenery/zOrtho4XP_+44+006/", ""]
    assert SP.set_rows_enabled(lines, ["zOrtho4XP_+45+007"], False) == []
    assert SP.set_rows_enabled(lines, ["zOrtho4XP_+45+007"], False,
                               insert_kind="ortho") == ["zOrtho4XP_+45+007"]
    assert lines[1:] == ["SCENERY_PACK Custom Scenery/zOrtho4XP_+44+006/",
                         "SCENERY_PACK_DISABLED Custom Scenery/zOrtho4XP_+45+007/",
                         ""]


def test_undo_files_again_the_rows_another_program_dropped(xp):  # noqa: F811
    scenery = xp["scenery"]
    MIGRATE.migrate(scenery, index=xp["index"], choice=RETIRE.DYNAMIC)
    _drop_rows(scenery, [LINK, LOCAL])
    assert LINK not in _rows(scenery)
    back = MIGRATE.revert(scenery, index=xp["index"])
    assert LINK in back["reverted"] and LOCAL in back["reverted"]
    rows = _rows(scenery)
    assert rows[LINK] == rows[LOCAL] == "SCENERY_PACK"
    assert os.path.islink(os.path.join(scenery, LINK))


def test_the_world_pack_gone_mid_run_retires_nothing_more(xp, monkeypatch):  # noqa: F811
    scenery = xp["scenery"]
    real = MIGRATE.migrate_tile

    def trash_the_pack(entry, **kw):        # the owner's Finder, mid-run
        row = real(entry, **kw)
        shutil.rmtree(xp["pack"])
        return row
    monkeypatch.setattr(MIGRATE, "migrate_tile", trash_the_pack)
    out = MIGRATE.migrate(scenery, workers=1, index=xp["index"],
                          choice=RETIRE.KEEP_ALL)
    status = {r["name"]: r["status"] for r in out["rows"]}
    assert list(status.values()).count("migrated") == 1
    assert all(s == "failed" for n, s in status.items()
               if s != "migrated")
    assert out["pack_missing"] == 1
    assert "missing from the World pack" in MIGRATE.summary("migrate", out)
    for name in (LINK, "zOrtho4XP_+47+009", "zOrtho4XP_+48+010"):
        assert os.path.lexists(os.path.join(scenery, name)), name
    fields = WORLD.world_status(scenery)
    assert fields["state"] == "off"
    assert "missing from the World pack" in fields["reason"]
    monkeypatch.setattr(MIGRATE, "migrate_tile", real)
    back = MIGRATE.revert(scenery, index=xp["index"])
    assert back["reverted"]
    assert not os.path.exists(xp["pack"])      # not made again, unmarked
    assert all(v == "SCENERY_PACK" for k, v in _rows(scenery).items()
               if k in (LINK, LOCAL))


def test_retire_refuses_when_the_placeholder_does_not_land(xp, monkeypatch):  # noqa: F811
    scenery = xp["scenery"]
    monkeypatch.setattr(WP, "write_placeholder", lambda *a, **k: None)
    out = MIGRATE.migrate(scenery, [LOCAL], index=xp["index"],
                          choice=RETIRE.DYNAMIC)
    row = out["rows"][0]
    assert row["status"] == "failed" and "no DSF" in row["problems"][0]
    record = MIGRATE.Journal(xp["work"]).get(LOCAL)
    assert record["state"] == "retiring" and record["problems"]
    assert _rows(scenery)[LOCAL] == "SCENERY_PACK"     # nothing changed


def test_a_failed_tile_keeps_its_reasons_in_the_journal(xp):  # noqa: F811
    scenery = xp["scenery"]
    dsf = os.path.join(scenery, LOCAL, WP.dsf_relpath(46, 8))
    os.remove(dsf)
    out = MIGRATE.migrate(scenery, [LOCAL], index=xp["index"])
    assert out["counts"] == {"failed": 1}
    record = MIGRATE.Journal(xp["work"]).get(LOCAL)
    assert record["state"] == "staging"
    assert record["problems"] == [f"no DSF in {os.path.join(scenery, LOCAL)}"]


def test_the_tidy_waits_while_a_run_changes_the_ini(xp):  # noqa: F811
    scenery = xp["scenery"]
    os.makedirs(os.path.join(scenery, "New Pack", "Earth nav data"))
    with MIGRATE.active_run():
        assert MIGRATE.active()
        reply = TIDY.tidy_scenery_packs(scenery)
    assert reply == {"added": [], "backup": "", "deferred": True}
    assert not MIGRATE.active()
    assert TIDY.tidy_scenery_packs(scenery)["added"] == ["New Pack"]


def _ours_is_the_local_tile(monkeypatch):
    import O4_Tile_Info as TINFO
    monkeypatch.setattr(TINFO, "built_here",
                        lambda folder, lat, lon, *a: (lat, lon) == (46, 8))
    packaged = []
    monkeypatch.setattr(RETIRE, "_package_first",
                        lambda first, path, name: packaged.append(name))
    return packaged


def test_rechoose_makes_the_other_tools_kept_tiles_dynamic(xp, monkeypatch):  # noqa: F811
    scenery = xp["scenery"]
    packaged = _ours_is_the_local_tile(monkeypatch)
    MIGRATE.migrate(scenery, index=xp["index"])                    # keep all
    library = _hashes(xp["library"])
    dry = RECHOOSE.rechoose(scenery, only_not_ours=True, dry_run=True,
                            index=xp["index"])
    assert (dry["rechosen"], dry["ours"], dry["unknown"]) == (1, 1, 0)
    assert WP.world_tiles(xp["pack"]) == {(45, 7): "full", (46, 8): "full"}
    assert "Would make 1 kept tiles dynamic" in dry["summary"]
    out = RECHOOSE.rechoose(scenery, only_not_ours=True, index=xp["index"])
    assert out["rechosen"] == [LINK] and not out["failed"]
    assert packaged == [LOCAL, LOCAL]           # dry run and run, ours only
    assert WP.world_tiles(xp["pack"]) == {(45, 7): "placeholder",
                                          (46, 8): "full"}
    assert not os.path.exists(os.path.join(xp["pack"], "textures", "+45+007"))
    assert not os.path.lexists(os.path.join(scenery, LINK))
    assert _rows(scenery)[LINK] == "SCENERY_PACK_DISABLED"
    record = MIGRATE.Journal(xp["work"]).get(LINK)
    assert record["state"] == "dynamic" and record["rechosen"] is True
    assert os.path.isdir(record["config_dir"])          # the lean copy stays
    assert MIGRATE.Journal(xp["work"]).get(LOCAL)["state"] == "done"
    assert _hashes(xp["library"]) == library            # never touched
    # Undo: as after a plain migration and its Undo
    back = MIGRATE.revert(scenery, index=xp["index"])
    assert sorted(back["reverted"]) == [LINK, LOCAL]
    assert os.path.islink(os.path.join(scenery, LINK))
    assert WP.world_tiles(xp["pack"]) == {(45, 7): "placeholder"}
    rows = _rows(scenery)
    assert rows[LINK] == rows[LOCAL] == "SCENERY_PACK"
    assert MIGRATE.Journal(xp["work"]).records == {}


def test_links_only_leaves_the_local_kept_tiles(xp, monkeypatch):  # noqa: F811
    import O4_Tile_Info as TINFO
    scenery = xp["scenery"]
    monkeypatch.setattr(TINFO, "built_here", lambda *a: False)    # none ours
    MIGRATE.migrate(scenery, index=xp["index"])
    dry = RECHOOSE.rechoose(scenery, only_not_ours=True, links_only=True,
                            dry_run=True, index=xp["index"])
    assert (dry["rechosen"], dry["ours"]) == (1, 0)
    out = RECHOOSE.rechoose(scenery, only_not_ours=True, links_only=True,
                            index=xp["index"])
    assert out["rechosen"] == [LINK]
    assert MIGRATE.Journal(xp["work"]).get(LOCAL)["state"] == "done"


def test_rechoose_leaves_a_tile_nobody_can_tell_kept(xp, monkeypatch):  # noqa: F811
    scenery = xp["scenery"]
    _ours_is_the_local_tile(monkeypatch)
    MIGRATE.migrate(scenery, index=xp["index"])
    journal = MIGRATE.Journal(xp["work"])
    journal.set(LINK, source="/Volumes/NoSuchDrive9/zOrtho4XP_+45+007",
                config_dir="/Volumes/NoSuchDrive9/lean")
    out = RECHOOSE.rechoose(scenery, only_not_ours=True, index=xp["index"])
    assert out["rechosen"] == [] and out["unknown"] == 1
    assert "stay kept" in out["summary"]
    assert WP.world_tiles(xp["pack"])[(45, 7)] == "full"


def test_the_terminal_shell_runs_the_dry_run_then_the_backfill(xp, capsys):  # noqa: F811
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools", "ondemand_convert.py")
    spec = importlib.util.spec_from_file_location("ondemand_convert_tool", path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    scenery = xp["scenery"]
    MIGRATE.migrate(scenery, index=xp["index"])
    assert tool.main(["--custom-scenery", scenery, "world-rechoose",
                      "--links-only"]) == 0
    assert "Would make 1 kept tiles dynamic" in capsys.readouterr().out
    assert WP.world_tiles(xp["pack"])[(45, 7)] == "full"      # a dry run
    assert tool.main(["--custom-scenery", scenery, "world-backfill"]) == 0
    assert "into 1 lean copies" in capsys.readouterr().out
