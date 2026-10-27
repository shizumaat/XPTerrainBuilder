"""Twins for O4_Tile_Texture_Check on synthetic tile folders.

The defect it answers (2026-10-25): a tile cfg reset to the source of an
older build made the imagery audit call the tile's REAL textures unused,
and the cleanup moved every one of them to the Trash; X-Plane then failed
on the tile's terrain files.  Two rules, one per half of the module:

* a texture the terrain folder names is never offered as unused;
* an installed tile whose terrain names a missing texture is reported.
"""

from __future__ import annotations

import os

import O4_Qt_Map as QTMAP
import O4_Tile_Texture_Check as CHECK


def _tile(root, terrain, textures):
    """A tile folder: ``terrain`` maps .ter names to the .dds they name."""
    (root / "terrain").mkdir(parents=True)
    (root / "textures").mkdir()
    for (ter, dds) in terrain.items():
        (root / "terrain" / ter).write_text(
            "A\n800\nTERRAIN\n\nBASE_TEX_NOWRAP ../textures/%s\n" % dds,
            encoding="utf-8", newline="")
    for name in textures:
        (root / "textures" / name).write_bytes(b"DDS ")
    return str(root)


# The -42+175 shape: terrain built from Arc in 2024, a 2017 NZ build's
# textures still beside them.
_TERRAIN = {
    "163856_259008_Arc18.ter": "163856_259008_Arc18.dds",
    "163856_259008_Arc18_sea_overlay.ter": "163856_259008_Arc18.dds",
    "163872_259024_Arc16_water_overlay.ter": "163872_259024_Arc16.dds",
}


def test_terrain_names_stand_for_their_base_texture(tmp_path):
    tile = _tile(tmp_path, _TERRAIN, [])
    assert CHECK.terrain_texture_names(tile) == {"163856_259008_Arc18.dds",
                                                 "163872_259024_Arc16.dds"}
    assert CHECK.terrain_texture_names(str(tmp_path / "none")) is None


def test_textures_the_terrain_uses_are_never_unused(tmp_path):
    tile = _tile(tmp_path, _TERRAIN, ["163856_259008_Arc18.dds",
                                      "163872_259024_Arc16.dds",
                                      "10240_16144_NZ17.dds"])
    textures = os.path.join(tile, "textures")
    # The cfg says NZ (a stale reset); the terrain says Arc.  The Arc
    # textures are in use: nothing is offered, no badge.
    assert QTMAP.audit_textures(textures, "NZ").foreign_files == []
    assert QTMAP.has_foreign_sources(textures, "NZ") is False
    # With the cfg right, the NZ texture nothing names is the offer.
    audit = QTMAP.audit_textures(textures, "Arc")
    assert [os.path.basename(p) for p in audit.foreign_files] == [
        "10240_16144_NZ17.dds"]
    assert QTMAP.has_foreign_sources(textures, "Arc") is True


def test_no_terrain_folder_no_cleanup_offer(tmp_path):
    (tmp_path / "textures").mkdir()
    (tmp_path / "textures" / "163856_259008_Arc18.dds").write_bytes(b"DDS ")
    textures = str(tmp_path / "textures")
    assert QTMAP.has_foreign_sources(textures, "NZ") is False
    assert QTMAP.audit_textures(textures, "NZ") is None


def test_check_reports_missing_textures(tmp_path):
    tile = _tile(tmp_path, _TERRAIN, ["163872_259024_Arc16.dds"])
    reply = CHECK.tile_texture_check(build_dir=tile)
    assert reply == {"build_dir": tile, "checked": True, "missing_count": 1,
                     "missing": ["163856_259008_Arc18.dds"]}


def test_check_of_a_whole_tile_is_clean(tmp_path):
    tile = _tile(tmp_path, _TERRAIN, ["163856_259008_Arc18.dds", "163872_259024_Arc16.dds"])
    assert CHECK.tile_texture_check(build_dir=tile)["missing_count"] == 0


def test_check_without_terrain_is_not_checked(tmp_path):
    reply = CHECK.tile_texture_check(build_dir=str(tmp_path))
    assert (reply["checked"], reply["missing_count"]) == (False, 0)
    assert CHECK.tile_texture_check()["checked"] is False


def test_check_reply_carries_a_sample_and_the_whole_count(tmp_path):
    terrain = {"%d_259008_Arc18.ter" % (163856 + 16 * i):
               "%d_259008_Arc18.dds" % (163856 + 16 * i)
               for i in range(CHECK.SAMPLE_SIZE + 5)}
    reply = CHECK.tile_texture_check(build_dir=_tile(tmp_path, terrain, []))
    assert reply["missing_count"] == CHECK.SAMPLE_SIZE + 5
    assert len(reply["missing"]) == CHECK.SAMPLE_SIZE


def test_the_engine_serves_the_same_function(tmp_path):
    from unittest import mock

    from o4_engine import jsonl
    handler = jsonl._build_handlers(mock.MagicMock())["tile_texture_check"]
    tile = _tile(tmp_path, _TERRAIN, [])
    assert handler(build_dir=tile) == CHECK.tile_texture_check(build_dir=tile)


def test_the_pane_words():
    assert CHECK.warning_text(1) == ("1 texture missing — X-Plane cannot "
                                     "load this tile")
    assert CHECK.warning_text(1805).startswith("1,805 textures missing")
    detail = CHECK.detail_text({"missing_count": 5,
                                "missing": ["a.dds", "b.dds", "c.dds", "d.dds"]})
    assert "(a.dds, b.dds, c.dds and 2 more)" in detail


def _linked_tile(tmp_path, textures=()):
    """A Custom Scenery folder whose tile is a symlink into a library
    folder (#1563: +47-113 lives on a scenery-library drive)."""
    library = tmp_path / "Library" / "zOrtho4XP_+47-113"
    _tile(library, _TERRAIN, list(textures))
    dsf = library / "Earth nav data" / "+40-120" / "+47-113.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"XPLNEDSF")
    scenery = tmp_path / "Custom Scenery"
    scenery.mkdir()
    link = scenery / "zOrtho4XP_+47-113"
    os.symlink(library, link, target_is_directory=True)
    return str(scenery), str(link)


def test_a_symlinked_tile_is_scanned_and_checked_through_its_link(tmp_path):
    import O4_Tile_Info as TINFO
    scenery, link = _linked_tile(tmp_path)
    found = {key: info for (_d, _t, key, info)
             in TINFO.iter_scan_tiles(scenery) if key is not None}
    assert found[(47, -113)].build_dir == link
    reply = CHECK.tile_texture_check(build_dir=found[(47, -113)].build_dir)
    assert reply["checked"] and reply["missing_count"] == 2
