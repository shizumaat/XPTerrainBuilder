"""The World folder as the tiles' home (RULINGS 2026-11-12g/h, spec
``docs/specs/world-home-20261112.md``; ``o4_engine.world_home``,
``O4_File_Names._tiles_root``, ``storage_packages.store_dir``,
``o4_engine.storage_tiers``).  Twins on temporary folders only."""
from __future__ import annotations

import json
import os

import pytest

import O4_File_Names as FNAMES
import O4_Scenery_Links as LINKS
import O4_World_Pack as WP
from o4_engine import storage_packages as STORE
from o4_engine import storage_tiers as STORE_TIERS
from o4_engine import world_commands as WORLD
from o4_engine import world_home as HOME


@pytest.fixture
def roots(tmp_path, monkeypatch):
    """A data folder and a Custom Scenery folder holding the app's World
    pack (its marker only: no placeholders)."""
    data = tmp_path / "data"
    scenery = tmp_path / "xp" / "Custom Scenery"
    pack = scenery / WP.PACK_NAME
    pack.mkdir(parents=True)
    (pack / WP.MARKER).write_text("{}", encoding="utf-8")
    data.mkdir()
    monkeypatch.setattr(FNAMES, "_data_root_override", str(data))
    monkeypatch.delitem(FNAMES.__dict__, "Tile_dir", raising=False)
    monkeypatch.setattr(HOME, "_log", lambda out: None)
    assert WORLD.managed(str(scenery))
    return data, scenery, pack


def _tile(folder, name, files=("Ortho4XP_%s.cfg",)):
    path = folder / name
    path.mkdir(parents=True)
    for pattern in files:
        (path / (pattern % name[len("zOrtho4XP_"):])).write_text(
            "x" * 10, encoding="utf-8")
    return path


def test_tile_dir_is_the_data_folder_until_a_pointer_names_the_world(roots):
    data, _scenery, pack = roots
    assert FNAMES.Tile_dir == str(data / "Tiles")
    assert STORE.store_dir() == str(data / STORE.STORE_DIR)
    HOME.write_pointer(str(pack))           # its tiles folder is missing
    assert FNAMES.Tile_dir == str(data / "Tiles")
    (pack / FNAMES.WORLD_TILES_DIR).mkdir()
    assert FNAMES.Tile_dir == str(pack / FNAMES.WORLD_TILES_DIR)
    assert FNAMES.build_dir(1, 2, "") == str(
        pack / FNAMES.WORLD_TILES_DIR / "zOrtho4XP_+01+002")
    assert STORE.store_dir() == str(pack / FNAMES.WORLD_PACKAGES_DIR)


def test_migrate_moves_tiles_and_packages_then_points_home(roots):
    data, scenery, pack = roots
    _tile(data / "Tiles", "zOrtho4XP_+01+002")
    _tile(data / "Tiles", "zOrtho4XP_+03+004")
    store = data / "Tile_packages"
    store.mkdir()
    (store / "+01+002_adopted.xptb").write_bytes(b"p" * 20)
    (store / "packaged.json").write_text(json.dumps(
        {"+01+002": {"path": str(store / "+01+002_adopted.xptb")}}),
        encoding="utf-8")

    first = HOME.migrate(str(scenery), busy=lambda: {"+03+004"})
    assert (first["moved"], first["busy"], first["left"]) == (1, 1, 1)
    assert first["active"] is False          # a tile still building: not yet
    assert FNAMES.Tile_dir == str(data / "Tiles")
    assert (data / "Tiles" / "zOrtho4XP_+03+004").is_dir()

    second = HOME.migrate(str(scenery))
    assert second["moved"] == 1 and second["left"] == 0 and second["active"]
    tiles = pack / FNAMES.WORLD_TILES_DIR
    assert FNAMES.Tile_dir == str(tiles)
    assert sorted(os.listdir(tiles)) == ["zOrtho4XP_+01+002", "zOrtho4XP_+03+004"]
    assert (tiles / "zOrtho4XP_+01+002" / "Ortho4XP_+01+002.cfg").is_file()
    packages = pack / FNAMES.WORLD_PACKAGES_DIR
    assert STORE.store_dir() == str(packages)
    assert (packages / "+01+002_adopted.xptb").is_file()
    assert STORE.packaged()["+01+002"]["path"] == str(
        packages / "+01+002_adopted.xptb")
    work = pack / HOME.HOME_DIR
    assert any(".before-world-home" in name or "-before-world-home" in name
               for name in os.listdir(work))   # the journal backed up first
    third = HOME.migrate(str(scenery))
    assert third["planned"] == 0 and third["active"]


def test_a_taken_name_is_never_overwritten(roots):
    data, scenery, pack = roots
    _tile(data / "Tiles", "zOrtho4XP_+01+002")
    kept = _tile(pack / FNAMES.WORLD_TILES_DIR, "zOrtho4XP_+01+002",
                 files=("Ortho4XP_%s_imagery.json",))
    out = HOME.migrate(str(scenery))
    assert out["conflicts"] == 1 and out["left"] == 0 and out["active"]
    assert (data / "Tiles" / "zOrtho4XP_+01+002").is_dir()   # nothing deleted
    assert os.listdir(kept) == ["Ortho4XP_+01+002_imagery.json"]


def test_the_legacy_build_folder_moves_but_never_custom_scenery(roots, tmp_path):
    _data, scenery, pack = roots
    legacy = tmp_path / "MyTiles"
    _tile(legacy, "zOrtho4XP_+05+006")
    _tile(scenery, "zOrtho4XP_+07+008")        # a per-tile pack: Convert's
    out = HOME.migrate(str(scenery), legacy_build_dir=str(legacy) + "/")
    assert out["moved"] == 1
    assert (pack / FNAMES.WORLD_TILES_DIR / "zOrtho4XP_+05+006").is_dir()
    out = HOME.migrate(str(scenery), legacy_build_dir=str(scenery))
    assert out["planned"] == 0 and (scenery / "zOrtho4XP_+07+008").is_dir()


def test_across_volumes_the_copy_is_checked_before_the_source_goes(roots, monkeypatch):
    data, scenery, pack = roots
    _tile(data / "Tiles", "zOrtho4XP_+01+002")
    monkeypatch.setattr(HOME, "_same_volume", lambda a, b: False)
    out = HOME.migrate(str(scenery))
    assert out["moved"] == 1 and out["active"]
    assert not (data / "Tiles" / "zOrtho4XP_+01+002").exists()
    moved = pack / FNAMES.WORLD_TILES_DIR / "zOrtho4XP_+01+002"
    assert (moved / "Ortho4XP_+01+002.cfg").read_text(encoding="utf-8") == "x" * 10
    assert not os.path.exists(str(moved) + ".part")


def test_a_foreign_world_folder_is_never_a_home(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "_data_root_override", str(tmp_path / "data"))
    scenery = tmp_path / "Custom Scenery"
    target = tmp_path / "elsewhere"
    target.mkdir()
    (target / WP.MARKER).write_text("{}", encoding="utf-8")
    scenery.mkdir()
    os.symlink(target, scenery / WP.PACK_NAME)
    out = HOME.migrate(str(scenery))
    assert out["active"] is False and out["reason"] == "no_world_pack"


def test_no_link_is_made_for_a_build_folder_inside_the_world_pack(roots):
    _data, scenery, pack = roots
    build = _tile(pack / FNAMES.WORLD_TILES_DIR, "zOrtho4XP_+01+002")
    LINKS.install(1, 2, str(build), str(scenery))
    assert not os.path.lexists(scenery / "zOrtho4XP_+01+002")


def test_a_tier_keeps_a_texture_and_gives_it_back(tmp_path, monkeypatch):
    import O4_DDS_Cache as DDSC
    drive = tmp_path / "Drive"
    drive.mkdir()
    monkeypatch.setattr(STORE_TIERS, "configured",
                        lambda raw=None: {str(drive): 1.0})
    monkeypatch.setattr(STORE_TIERS, "_mounted", lambda mount: True)
    monkeypatch.setattr(STORE_TIERS, "_USED", {})
    cache = tmp_path / "cache"
    entry = DDSC.entry_path("abc123", str(cache))
    os.makedirs(os.path.dirname(entry))
    with open(entry, "wb") as handle:
        handle.write(b"d" * 64)
    kept = STORE_TIERS.stash("abc123", entry)
    assert kept.startswith(str(drive / STORE_TIERS.TIER_DIR))
    assert not os.path.exists(entry) and os.path.getsize(kept) == 64
    assert STORE_TIERS.find("abc123") == kept
    monkeypatch.setattr(STORE_TIERS, "_mounted", lambda mount: False)
    assert STORE_TIERS.find("abc123") is None   # absent: downloaded again


def test_a_full_tier_takes_nothing(tmp_path, monkeypatch):
    drive = tmp_path / "Drive"
    drive.mkdir()
    monkeypatch.setattr(STORE_TIERS, "configured",
                        lambda raw=None: {str(drive): 1e-9})
    monkeypatch.setattr(STORE_TIERS, "_mounted", lambda mount: True)
    monkeypatch.setattr(STORE_TIERS, "_USED", {})
    entry = tmp_path / "e.dds"
    entry.write_bytes(b"d" * 64)
    assert STORE_TIERS.stash("k", str(entry)) == "" and entry.is_file()


def test_the_index_knows_the_tier_folder():
    import O4_Imagery_OnDemand_Index as INDEX
    assert INDEX._TIER_DIR == STORE_TIERS.TIER_DIR


def test_tier_setting_reads_only_sizes_above_zero():
    raw = {STORE_TIERS.SETTING: json.dumps({"/Volumes/A": 50, "/Volumes/B": 0,
                                            "/Volumes/C": "x"})}
    assert STORE_TIERS.configured(raw) == {"/Volumes/A": 50.0}
    assert STORE_TIERS.configured({STORE_TIERS.SETTING: "not json"}) == {}


def test_the_apps_start_moves_the_home_a_bare_call_only_reports(roots, monkeypatch):
    data, scenery, pack = roots
    monkeypatch.setattr(WORLD, "ensure_coverage", lambda scenery_dir: None)
    _tile(data / "Tiles", "zOrtho4XP_+01+002")
    bare = WORLD.world_onboard(str(scenery))["home"]
    assert bare["planned"] == 1 and bare["active"] is False
    assert (data / "Tiles" / "zOrtho4XP_+01+002").is_dir()
    done = WORLD.world_onboard(str(scenery), move_home=True)["home"]
    assert done["moved"] == 1 and done["active"]
    assert done["tiles_dir"] == str(pack / FNAMES.WORLD_TILES_DIR)


def test_a_moved_folder_s_index_rows_name_its_new_place(roots):
    import O4_Imagery_OnDemand_Index as INDEX
    data, scenery, pack = roots
    old = _tile(data / "Tiles", "zOrtho4XP_+01+002")
    conn = INDEX.open_index()
    INDEX.upsert(conn, {"tile": "+01+002", "name": "a.dds",
                        "build_dir": str(old),
                        "textures_dir": str(old / "textures"),
                        "config_dir": str(old), "state": "low"})
    INDEX.upsert(conn, {"tile": "+01+003", "name": "b.dds",
                        "build_dir": str(old) + "_other", "state": "low"})
    conn.close()
    out = HOME.migrate(str(scenery))
    assert out["moved"] == 1 and out["index_rows"] == 3
    new = pack / FNAMES.WORLD_TILES_DIR / "zOrtho4XP_+01+002"
    conn = INDEX.open_index()
    try:
        row = INDEX.get(conn, "+01+002", "a.dds")
        other = INDEX.get(conn, "+01+003", "b.dds")
    finally:
        conn.close()
    assert row["build_dir"] == str(new) and row["config_dir"] == str(new)
    assert row["textures_dir"] == str(new / "textures")
    assert other["build_dir"] == str(old) + "_other"     # a prefix, not a path


def test_a_copy_landed_before_a_kill_is_finished_not_a_conflict(roots):
    import shutil

    from o4_engine.world_migrate import Journal
    data, scenery, pack = roots
    source = _tile(data / "Tiles", "zOrtho4XP_+01+002")
    target = pack / FNAMES.WORLD_TILES_DIR / "zOrtho4XP_+01+002"
    shutil.copytree(source, target)          # the copy landed, then the kill
    journal = Journal(str(pack / HOME.HOME_DIR))
    journal.set("zOrtho4XP_+01+002@" + str(data / "Tiles"), state="moving",
                source=str(source), target=str(target))
    out = HOME.migrate(str(scenery))
    assert (out["moved"], out["conflicts"]) == (1, 0) and not source.exists()
