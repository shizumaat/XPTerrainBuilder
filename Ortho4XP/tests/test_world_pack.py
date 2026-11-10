"""Twins of the World pack experiment (``src/O4_World_Pack.py``,
``tools/world_pack.py``): tile names, placeholder DSF, the per-tile
subfolder rewrites, the one-rename swap, the ini row and the distance
rule.  The DSFTool round trips run when the platform's bundled DSFTool is
present."""
from __future__ import annotations

import os
import platform

import pytest

import O4_World_Pack as WP

ENGINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tool():
    try:
        return WP.dsftool_path(ENGINE)
    except FileNotFoundError:
        return None


def test_tile_names_and_dsf_path():
    assert WP.tile_name(53, -63) == "+53-063"
    assert WP.parse_tile("+53-063") == (53, -63)
    assert WP.dsf_relpath(53, -63) == os.path.join(
        "Earth nav data", "+50-070", "+53-063.dsf")
    assert WP.dsf_relpath(-1, 5) == os.path.join(
        "Earth nav data", "-10+000", "-01+005.dsf")
    with pytest.raises(ValueError):
        WP.parse_tile("53-63")


def test_placeholder_text_is_an_empty_overlay():
    text = WP.placeholder_text(53, -63)
    for want in ("PROPERTY sim/overlay 1", "PROPERTY sim/west -63",
                 "PROPERTY sim/east -62", "PROPERTY sim/north 54",
                 "PROPERTY sim/south 53", WP.PLACEHOLDER_AGENT):
        assert want in text
    assert "_DEF" not in text


def test_block_skips_the_built_tile():
    tiles = WP.block_tiles(53, -61, 2, skip=[(53, -61)])
    assert len(tiles) == 24 and (53, -61) not in tiles
    assert (51, -63) in tiles and (55, -59) in tiles


TER = """A
800
TERRAIN

LOAD_CENTER 53.98194 -61.04004 5753 4096
BASE_TEX_NOWRAP ../textures/21040_21648_BI16.dds
LOAD_CENTER_BORDER 53.98194 -61.04004 5753 1024
BORDER_TEX ../textures/21040_21648_ZL16.png
WET
"""


def test_ter_rewrite_moves_every_texture_reference():
    text, n = WP.rewrite_ter(TER, "+53-063")
    assert n == 2
    assert "BASE_TEX_NOWRAP ../../textures/+53-063/21040_21648_BI16.dds" in text
    assert "BORDER_TEX ../../textures/+53-063/21040_21648_ZL16.png" in text
    assert WP.rewrite_ter(text, "+53-063")[1] == 0      # idempotent


def test_dsf_rewrite_leaves_library_and_builtin_terrain():
    src = ("TERRAIN_DEF terrain_Water\nTERRAIN_DEF terrain/a_BI16.ter\n"
           "TERRAIN_DEF lib/g10/terrain10/x.ter\nOBJECT_DEF objects/o.obj\n")
    text, n = WP.rewrite_dsf_text(src, "+53-063")
    assert n == 1
    assert "TERRAIN_DEF terrain/+53-063/a_BI16.ter" in text
    assert "TERRAIN_DEF terrain_Water" in text
    assert "TERRAIN_DEF lib/g10/terrain10/x.ter" in text


def test_tile_reach():
    cyyr = (53.3192, -60.4258)
    assert WP.tile_reach(*cyyr, 53, -61)["tiles"] == 0
    far = WP.tile_reach(*cyyr, 53, -63)
    assert far["tiles"] == 2 and 100 < far["km"] < 110
    assert WP.tile_reach(*cyyr, 53, -62)["tiles"] == 1


def test_xp_window_matches_flight_2():
    # flight 2 opened column -138 at lon -135.65 and -139 at -136.65
    assert WP.xp_window(60.75, -135.40, 60, -138)["in_window"] is False
    assert WP.xp_window(60.75, -135.70, 60, -138)["in_window"] is True
    assert WP.xp_window(60.97, -136.70, 60, -139)["in_window"] is True
    # CYYR: +53-062 is in the start window, +53-063 enters 15 km west
    cyyr = (53.3192, -60.4258)
    assert WP.xp_window(*cyyr, 53, -62)["in_window"] is True
    far = WP.xp_window(*cyyr, 53, -63)
    assert far["in_window"] is False and 14 < far["km_to_load"] < 17
    assert 75 < WP.xp_window(*cyyr, 53, -64)["km_to_load"] < 85
    assert WP.xp_window(*cyyr, 55, -61)["in_window"] is False


def test_ini_row_appended_once_and_removed():
    lines = ["I", "1000 Version", "SCENERY",
             "SCENERY_PACK Custom Scenery/zOrtho4XP_+53-061/",
             "SCENERY_PACK Custom Scenery/zzz_mesh/", ""]
    assert WP.ini_install(lines) is True
    row = f"SCENERY_PACK Custom Scenery/{WP.PACK_NAME}/"
    assert lines.count(row) == 1 and lines[-1] == ""
    assert WP.ini_install(lines) is False and lines.count(row) == 1
    lines[lines.index(row)] = row.replace("SCENERY_PACK", "SCENERY_PACK_DISABLED")
    assert WP.ini_install(lines) is False and row in lines
    assert WP.ini_remove(lines) == 1 and row not in lines
    assert lines[3] == "SCENERY_PACK Custom Scenery/zOrtho4XP_+53-061/"


def _fake_staged(root, tile, lat, lon):
    for sub, name in (("terrain", "a.ter"), ("textures", "a.dds")):
        os.makedirs(os.path.join(root, sub, tile))
        with open(os.path.join(root, sub, tile, name), "w", encoding="utf-8", newline="\n") as h:
            h.write(sub)
    dsf = os.path.join(root, WP.dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dsf))
    with open(dsf, "wb") as h:
        h.write(b"XPLNEDSF real tile")


def test_swap_in_replaces_the_placeholder_in_one_rename(tmp_path):
    pack, staged = str(tmp_path / "pack"), str(tmp_path / "staged")
    _fake_staged(staged, "+53-063", 53, -63)
    dest = os.path.join(pack, WP.dsf_relpath(53, -63))
    os.makedirs(os.path.dirname(dest))
    with open(dest, "wb") as h:
        h.write(b"XPLNEDSF " + WP.PLACEHOLDER_AGENT.encode())
    held = open(dest, "rb")                  # X-Plane holding the old file
    res = WP.swap_in(pack, staged, 53, -63)
    assert res["was_placeholder"] is True
    assert open(dest, "rb").read() == b"XPLNEDSF real tile"
    assert b"placeholder" in held.read()     # old inode intact for its reader
    held.close()
    assert os.path.isfile(os.path.join(pack, "terrain", "+53-063", "a.ter"))
    assert os.path.isfile(os.path.join(pack, "textures", "+53-063", "a.dds"))
    assert not WP.is_placeholder(dest)
    WP.swap_in(pack, staged, 53, -63)        # again: replaces, no leftovers
    assert sorted(os.listdir(os.path.join(pack, "terrain"))) == ["+53-063"]


@pytest.mark.skipif(_tool() is None, reason="no bundled DSFTool")
@pytest.mark.skipif(platform.machine() not in ("arm64", "x86_64", "AMD64"),
                    reason="DSFTool builds are x86_64/arm64")
def test_placeholder_round_trips_through_dsftool(tmp_path):
    path = WP.write_placeholder(str(tmp_path), 53, -63, _tool())
    assert WP.is_placeholder(path)
    res = WP.verify_tile(str(tmp_path), 53, -63, _tool())
    assert res["overlay"] is True and res["defs"] == 0 and not res["problems"]
