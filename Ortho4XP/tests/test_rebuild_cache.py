"""Twins for the per-tile rebuild cache (owner RULINGS 2026-11-10d (4)):
rebuild data out of the installed tile folder, the old layout still read,
the migration moves (never deletes) and keeps the steps reusable.

Headless: tile folders in ``tmp_path``; the rebuild root is the session
folder ``tests/conftest.py`` points ``O4_REBUILD_CACHE_DIR`` at, or a
per-test one here.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Config_Names as CN  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Rebuild_Cache as REBUILD  # noqa: E402
import O4_Step_Reuse as REUSE  # noqa: E402
from test_step_reuse import _complete_build, _reasons, _Tile  # noqa: E402

LAT, LON = 25, 51
KEY = FNAMES.short_latlon(LAT, LON)

#: what an older build left in the tile folder
_REBUILD_NAMES = ("Data%s.alt" % KEY, "Data%s.alt.frame.json" % KEY,
                  "Data%s.apt" % KEY, "Data%s.mesh" % KEY,
                  "Data%s.node" % KEY, "Data%s.poly" % KEY,
                  "Data%s.zprov.json" % KEY, "o4_levelled_roads.json",
                  "color_field.json", CN.tile_cfg_name(LAT, LON) + ".bak")
#: what stays: X-Plane's files and the records the apps read
_TILE_NAMES = (CN.tile_cfg_name(LAT, LON), "Ortho4XP_%s_imagery.json" % KEY,
               "o4_unpatched_airports.json")


@pytest.fixture
def root(tmp_path, monkeypatch):
    path = tmp_path / "Rebuild_cache"
    path.mkdir()
    monkeypatch.setenv("O4_REBUILD_CACHE_DIR", str(path))
    return path


def _tile_folder(parent, names=_REBUILD_NAMES + _TILE_NAMES):
    folder = parent / FNAMES.tile_dir(LAT, LON)
    (folder / "Earth nav data" / "+20+050").mkdir(parents=True)
    (folder / "Earth nav data" / "+20+050" / (KEY + ".dsf")).write_bytes(b"d")
    for name in names:
        (folder / name).write_text(name, encoding="utf-8")
    return folder


def _tile(folder):
    tile = _Tile(folder)
    tile.lat, tile.lon = LAT, LON
    return tile


def test_a_tile_folder_without_a_cache_keeps_its_files(tmp_path, root):
    """The old layout: no pointer, every accessor names the tile folder."""
    folder = _tile_folder(tmp_path)
    tile = _tile(folder)
    assert FNAMES.mesh_file(str(folder), LAT, LON) == str(
        folder / ("Data%s.mesh" % KEY))
    assert FNAMES.input_node_file(tile) == str(folder / ("Data%s.node" % KEY))
    assert FNAMES.alt_file(tile) == str(folder / ("Data%s.alt" % KEY))
    assert FNAMES.rebuild_dir(str(folder), LAT, LON) is None


def test_a_new_tile_writes_its_rebuild_data_into_the_cache(tmp_path, root):
    folder = tmp_path / FNAMES.tile_dir(LAT, LON)
    folder.mkdir()
    tile = _tile(folder)
    cache = REBUILD.claim(tile)
    assert cache == str(root / FNAMES.tile_dir(LAT, LON))
    for path in (FNAMES.input_node_file(tile), FNAMES.input_poly_file(tile),
                 FNAMES.alt_file(tile), FNAMES.apt_file(tile),
                 FNAMES.mesh_file(tile.build_dir, LAT, LON),
                 FNAMES.levelled_roads_file(tile.build_dir, LAT, LON),
                 FNAMES.step_record_file(tile.build_dir, LAT, LON)):
        assert os.path.dirname(path) == cache
    # The tile folder holds only the pointer.
    assert os.listdir(folder) == [os.path.basename(
        FNAMES.rebuild_pointer_path(str(folder), LAT, LON))]


def test_migration_moves_the_rebuild_data_and_nothing_else(tmp_path, root):
    folder = _tile_folder(tmp_path)
    sizes = {n: os.path.getsize(folder / n) for n in _REBUILD_NAMES}
    out = REBUILD.migrate_folder(str(tmp_path))
    (row,) = out["tiles"]
    assert sorted(row["moved"]) == sorted(_REBUILD_NAMES)
    assert row["bytes"] == sum(sizes.values()) == out["bytes"]
    cache = row["cache"]
    assert sorted(os.listdir(cache)) == sorted(
        _REBUILD_NAMES + (REBUILD.OWNER_NAME,))
    left = set(os.listdir(folder))
    assert left == set(_TILE_NAMES) | {"Earth nav data", os.path.basename(
        FNAMES.rebuild_pointer_path(str(folder), LAT, LON))}
    # Every reader finds the moved files through the one helper.
    assert FNAMES.mesh_file(str(folder), LAT, LON) == os.path.join(
        cache, "Data%s.mesh" % KEY)


def test_migration_is_idempotent_and_never_replaces_the_cache(
        tmp_path, root):
    folder = _tile_folder(tmp_path)
    REBUILD.migrate_folder(str(tmp_path))
    again = REBUILD.migrate_folder(str(tmp_path))
    assert again["moved_files"] == 0 and again["tiles"] == []
    # An old file next to a newer cached one is kept, never moved over it.
    (folder / ("Data%s.mesh" % KEY)).write_text("old", encoding="utf-8")
    third = REBUILD.migrate_folder(str(tmp_path))
    assert third["moved_files"] == 0
    assert third["tiles"][0]["kept"] == ["Data%s.mesh" % KEY]
    cached = FNAMES.mesh_file(str(folder), LAT, LON)
    assert open(cached, encoding="utf-8").read() == "Data%s.mesh" % KEY


def test_dry_run_moves_and_makes_nothing(tmp_path, root):
    folder = _tile_folder(tmp_path)
    out = REBUILD.rebuild_migrate([str(tmp_path)], dry_run=True)
    assert out["moved_files"] == len(_REBUILD_NAMES)
    assert os.listdir(root) == []
    assert all((folder / n).exists() for n in _REBUILD_NAMES)


def test_a_file_not_yet_moved_is_read_where_the_old_build_left_it(
        tmp_path, root):
    folder = tmp_path / FNAMES.tile_dir(LAT, LON)
    folder.mkdir()
    REBUILD.claim(_tile(folder))
    (folder / ("Data%s.mesh" % KEY)).write_text("old", encoding="utf-8")
    assert FNAMES.mesh_file(str(folder), LAT, LON) == str(
        folder / ("Data%s.mesh" % KEY))


def test_a_second_folder_of_the_same_tile_gets_its_own_cache(
        tmp_path, root):
    one = _tile_folder(tmp_path / "one")
    two = _tile_folder(tmp_path / "two")
    first = REBUILD.claim(_tile(one))
    second = REBUILD.claim(_tile(two))
    assert first != second
    assert os.path.basename(second) == FNAMES.tile_dir(LAT, LON) + "_2"
    assert FNAMES.mesh_file(str(two), LAT, LON).startswith(second)


def test_a_tile_cfg_backup_goes_with_the_rebuild_data(tmp_path, root):
    import O4_Settings_Model as SETTINGS
    folder = tmp_path / FNAMES.tile_dir(LAT, LON)
    folder.mkdir()
    cache = REBUILD.claim(_tile(folder))
    cfg = str(folder / CN.tile_cfg_name(LAT, LON))
    SETTINGS.write_tile_cfg(cfg, {"default_zl": "16"})
    SETTINGS.write_tile_cfg(cfg, {"default_zl": "17"})
    assert not os.path.exists(cfg + ".bak")
    assert os.path.isfile(os.path.join(cache, os.path.basename(cfg) + ".bak"))
    # A global cfg keeps its backup beside it.
    other = str(tmp_path / "XPTerrainBuilder.cfg")
    assert CN.cfg_backup_path(other) == other + ".bak"


def test_library_delete_takes_the_rebuild_data_with_the_tile(
        tmp_path, root):
    folder = _tile_folder(tmp_path)
    REBUILD.migrate_folder(str(tmp_path))
    cache = FNAMES.rebuild_dir(str(folder), LAT, LON)
    assert REBUILD.remove(str(folder), LAT, LON) > 0
    assert not os.path.exists(cache)


# --------------------------------------------------- step reuse round trip
@pytest.fixture
def built(tmp_path, monkeypatch, root):
    """A tile built BEFORE the cache: every step recorded, its files in
    the tile folder."""
    for name in ("osm", "patches", "masks", "insets"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(FNAMES, "osm_dir", lambda lat, lon: str(tmp_path / "osm"))
    monkeypatch.setattr(FNAMES, "patch_dir",
                        lambda lat, lon: str(tmp_path / "patches"))
    monkeypatch.setattr(FNAMES, "mask_dir", lambda lat, lon: str(tmp_path / "masks"))
    monkeypatch.setattr(FNAMES, "airport_inset_directory",
                        lambda lat, lon: str(tmp_path / "insets"))
    monkeypatch.delenv("O4_STEP_REUSE", raising=False)
    (tmp_path / "osm" / "+25+051_airports.osm.bz2").write_bytes(b"osm")
    (tmp_path / "masks" / "mask.png").write_bytes(b"mask")
    folder = _tile_folder(tmp_path / "Tiles", names=_TILE_NAMES)
    tile = _tile(folder)
    for path in (FNAMES.input_node_file(tile), FNAMES.input_poly_file(tile),
                 FNAMES.alt_file(tile), FNAMES.apt_file(tile),
                 FNAMES.mesh_file(tile.build_dir, LAT, LON)):
        assert os.path.dirname(path) == str(folder)      # the old layout
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("data")
    _complete_build(tile)
    assert os.path.isfile(folder / ("Ortho4XP_%s_steps.json" % KEY))
    return tile


def test_the_migration_keeps_every_step_reusable(built):
    assert _reasons(built) == {"vector": None, "mesh": None, "masks": None}
    out = REBUILD.migrate_folder(os.path.dirname(built.build_dir))
    moved = out["tiles"][0]["moved"]
    assert "Ortho4XP_%s_steps.json" % KEY in moved
    record = FNAMES.step_record_file(built.build_dir, LAT, LON)
    assert os.path.dirname(record) == out["tiles"][0]["cache"]
    assert _reasons(built) == {"vector": None, "mesh": None, "masks": None}
    # The record reads its paths where the files are now ...
    rows = REUSE.committed_entry(built, "mesh")["outputs"]
    assert rows[0][0] == FNAMES.mesh_file(built.build_dir, LAT, LON)
    # ... and takes them at its next write.
    REUSE.forget_from(built, "masks")
    with open(record, encoding="utf-8") as handle:
        rows = json.load(handle)["committed"]["mesh"]["outputs"]
    assert rows[0][0] == FNAMES.mesh_file(built.build_dir, LAT, LON)
    assert _reasons(built)["mesh"] is None


def test_a_step_stale_before_the_migration_stays_stale(built):
    mesh = FNAMES.mesh_file(built.build_dir, LAT, LON)
    with open(mesh, "w", encoding="utf-8") as handle:
        handle.write("changed by hand")
    os.utime(mesh, (1, 1))
    before = _reasons(built)
    assert before["mesh"] is not None
    REBUILD.migrate_folder(os.path.dirname(built.build_dir))
    assert _reasons(built)["mesh"] is not None
    assert _reasons(built)["vector"] is None


def test_a_rebuild_in_the_new_layout_reuses_its_steps(tmp_path, built):
    """The claim at a step's start migrates; the next build reuses."""
    REBUILD.claim(built)
    assert _reasons(built) == {"vector": None, "mesh": None, "masks": None}
    _complete_build(built, steps=())
    assert REBUILD.legacy_entries(built.build_dir, LAT, LON) == []
