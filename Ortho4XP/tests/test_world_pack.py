"""Twins of the World pack (``src/O4_World_Pack.py``,
``src/O4_DSF_Binary.py``, ``tools/world_pack.py``): tile names, the
placeholder DSF (pure Python, byte for byte DSFTool's), the per-tile
subfolder rewrites (the binary DSF rewrite against the DSFTool text round
trip on three DSFs), kinds, publish / stage / swap (rules S1, S3/S4), the
one-rename swap and the ini row (the DSF window:
``test_world_window.py``).  The DSFTool oracles run when the platform's
bundled DSFTool is present."""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess

import O4_DSF_Binary as DSFB
import O4_World_Pack as WP
import pytest

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "mesh_dsf")

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
        with open(os.path.join(root, sub, tile, name), "w", encoding="utf-8",
                  newline="\n") as h:
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
    # X-Plane holding the old file: POSIX keeps the old inode for its
    # reader; Windows refuses a rename over an open file (held-file
    # handling is the flight-manager spec's phase X), so it is not held there.
    held = None if os.name == "nt" else open(dest, "rb")
    res = WP.swap_in(pack, staged, 53, -63)
    assert res["was_placeholder"] is True
    with open(dest, "rb") as h:
        assert h.read() == b"XPLNEDSF real tile"
    if held is not None:
        assert b"placeholder" in held.read()  # old inode intact for its reader
        held.close()
    assert os.path.isfile(os.path.join(pack, "terrain", "+53-063", "a.ter"))
    assert os.path.isfile(os.path.join(pack, "textures", "+53-063", "a.dds"))
    assert not WP.is_placeholder(dest)
    WP.swap_in(pack, staged, 53, -63)        # again: replaces, no leftovers
    assert sorted(os.listdir(os.path.join(pack, "terrain"))) == ["+53-063"]


def test_placeholder_is_328_bytes_of_an_empty_overlay(tmp_path):
    path = WP.write_placeholder(str(tmp_path), 53, -63)
    data = open(path, "rb").read()
    assert len(data) == 328 and DSFB.dsf_md5_ok(data)
    assert dict(DSFB.properties(data)) == {
        "sim/planet": "earth", "sim/overlay": "1",
        "sim/creation_agent": WP.PLACEHOLDER_AGENT, "sim/west": "-63",
        "sim/east": "-62", "sim/north": "54", "sim/south": "53"}
    assert not any(DSFB.definitions(data).values())
    assert WP.is_placeholder(path) and WP.kind_of(path) == "placeholder"
    assert not WP.is_placeholder(path, size=WP.PLACEHOLDER_MAX_BYTES + 1)
    res = WP.verify_tile(str(tmp_path), 53, -63)
    assert res["overlay"] is True and res["defs"] == 0 and not res["problems"]


_HAS_TOOL = pytest.mark.skipif(
    _tool() is None or platform.machine() not in ("arm64", "x86_64", "AMD64"),
    reason="no runnable bundled DSFTool")


def _dsf2text(path: str) -> str:
    done = subprocess.run([_tool(), "--dsf2text", path, "-"],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=True)
    return "\n".join(line.replace(path, "<dsf>")
                     for line in done.stdout.splitlines()
                     if not line.startswith(("#", "Convert")))


@_HAS_TOOL
@pytest.mark.parametrize("lat,lon", [(53, -63), (-1, 5), (45, 7)])
def test_placeholder_bytes_equal_dsftools(tmp_path, lat, lon):
    src = tmp_path / "ph.txt"
    src.write_text(WP.placeholder_text(lat, lon), encoding="utf-8",
                   newline="\n")
    out = tmp_path / "ph.dsf"
    subprocess.run([_tool(), "--text2dsf", str(src), str(out)],
                   capture_output=True, check=True)
    assert out.read_bytes() == DSFB.placeholder_bytes(
        lat, lon, WP.PLACEHOLDER_AGENT)


def _build_dir(root, fixture: str, lat: int, lon: int) -> str:
    """A build folder around a fixture DSF: one ``.ter`` per terrain
    definition, each naming one texture."""
    build = os.path.join(str(root), "build")
    dsf = os.path.join(build, WP.dsf_relpath(lat, lon))
    os.makedirs(os.path.dirname(dsf))
    os.makedirs(os.path.join(build, "terrain"))
    os.makedirs(os.path.join(build, "textures"))
    shutil.copyfile(fixture, dsf)
    data = open(dsf, "rb").read()
    for ref in DSFB.definitions(data).get("TERT", []):
        if ref.startswith("terrain/"):
            with open(os.path.join(build, ref), "w", encoding="utf-8",
                      newline="\n") as h:
                h.write(TER)
    for name in ("21040_21648_BI16.dds", "21040_21648_ZL16.png"):
        with open(os.path.join(build, "textures", name), "wb") as h:
            h.write(b"DDS ")
    return build


THREE_DSFS = [("full_ortho.dsf", 45, 7), ("default_xplane.dsf", 45, 7),
              (None, 53, -63)]


@pytest.mark.parametrize("fixture,lat,lon", THREE_DSFS)
def test_binary_rewrite_keeps_every_other_atom(tmp_path, fixture, lat, lon):
    data = (open(os.path.join(FIXTURES, fixture), "rb").read() if fixture
            else DSFB.placeholder_bytes(lat, lon, WP.PLACEHOLDER_AGENT))
    assert DSFB.rewrite(data, props=lambda p: p, defs=lambda t, s: s) == data
    tile = WP.tile_name(lat, lon)
    out = DSFB.rewrite(data, defs=lambda t, s: WP._pack_def(s, tile))
    assert DSFB.dsf_md5_ok(out)
    for table, refs in DSFB.definitions(out).items():
        for ref in refs:
            assert not ref.startswith(("terrain/", "textures/")) or \
                ref.startswith((f"terrain/{tile}/", f"textures/{tile}/")), table
    keep = [n for n, _b, _e in DSFB.atoms(data, 12, len(data) - 16)]
    assert [n for n, _b, _e in DSFB.atoms(out, 12, len(out) - 16)] == keep


@_HAS_TOOL
@pytest.mark.parametrize("fixture,lat,lon", THREE_DSFS)
def test_binary_rewrite_equals_the_dsftool_round_trip(tmp_path, fixture,
                                                      lat, lon):
    """The binary relayout reads, through DSFTool, as the DSFTool text
    round trip with :func:`WP.rewrite_dsf_text` (the 59 s path it
    replaces) -- but for the agent's kind stamp."""
    source = (os.path.join(FIXTURES, fixture) if fixture
              else WP.write_placeholder(str(tmp_path / "ph"), lat, lon))
    build = _build_dir(tmp_path, source, lat, lon)
    staged = str(tmp_path / "staged")
    WP.relayout_tile(build, staged, lat, lon, kind="light")
    got = _dsf2text(os.path.join(staged, WP.dsf_relpath(lat, lon)))
    want, _n = WP.rewrite_dsf_text(_dsf2text(source), WP.tile_name(lat, lon))
    agent = re.compile(r"^PROPERTY sim/creation_agent (.*)$", re.M)
    old = agent.search(want).group(1)
    assert agent.search(got).group(1) == WP._stamp(old, "light")
    assert agent.sub("", got) == agent.sub("", want)


def test_kind_stamp_and_publish(tmp_path):
    lat, lon = 45, 7
    build = _build_dir(tmp_path, os.path.join(FIXTURES, "full_ortho.dsf"),
                       lat, lon)
    pack, stage = str(tmp_path / "pack"), str(tmp_path / "stage")
    WP.write_placeholders(pack, [(lat, lon), (lat, lon + 1)])
    # S3/S4: a tile X-Plane may hold stays staged, the pack unchanged.
    res = WP.publish(pack, build, lat, lon, staging_root=stage, kind="full",
                     loaded=lambda la, lo: True)
    assert res["state"] == "staged" and not res["problems"]
    assert WP.world_tiles(pack) == {(45, 7): "placeholder",
                                    (45, 8): "placeholder"}
    assert WP.swap_staged(pack, stage, lambda la, lo: True) == []
    assert WP.swap_staged(pack, stage) == ["+45+007"]
    assert WP.world_tiles(pack) == {(45, 7): "full", (45, 8): "placeholder"}
    assert WP.real_tiles(pack).keys() == {(45, 7)}
    scenery = str(tmp_path)          # the pack's parent, by name
    os.rename(pack, os.path.join(scenery, WP.PACK_NAME))
    assert WP.holds_tile(scenery, 45, 7) and not WP.holds_tile(scenery, 45, 8)
    check = WP.verify_tile(os.path.join(scenery, WP.PACK_NAME), lat, lon)
    assert not check["problems"] and check["kind"] == "full"
    assert check["pack_defs"] == 2 and check["tex_refs"] == 4
    assert WP._stamp("XPTerrainBuilder 1.0 [world light]", "full") == \
        "XPTerrainBuilder 1.0 [world full]"
    with pytest.raises(ValueError):
        WP._stamp("x", "placeholder")


def test_publish_refuses_a_tile_that_does_not_verify(tmp_path):
    """S1: nothing in the pack changes before the staged tile verifies."""
    build = _build_dir(tmp_path, os.path.join(FIXTURES, "full_ortho.dsf"),
                       45, 7)
    for name in os.listdir(os.path.join(build, "textures")):
        os.remove(os.path.join(build, "textures", name))
    pack = str(tmp_path / "pack")
    WP.write_placeholder(pack, 45, 7)
    res = WP.publish(pack, build, 45, 7, staging_root=str(tmp_path / "s"))
    assert res["state"] == "failed" and res["problems"]
    assert WP.world_tiles(pack) == {(45, 7): "placeholder"}
    assert os.listdir(str(tmp_path / "s")) == []


def test_write_placeholders_never_overwrites_a_tile(tmp_path):
    pack = str(tmp_path)
    _fake_staged(str(tmp_path / "st"), "+53-063", 53, -63)
    WP.swap_in(pack, str(tmp_path / "st"), 53, -63)
    done = WP.write_placeholders(pack, [(53, -63), (53, -62)])
    assert done == {"written": 1, "kept": 1}
    assert not WP.is_placeholder(os.path.join(pack, WP.dsf_relpath(53, -63)))
