"""#2106: a texture landed while X-Plane runs shows at the next scenery
reload -- X-Plane keeps a texture it holds across "Reload scenery", so
each landing points the tile's ``.ter`` files at a fresh symlink to the
texture (``O4_Imagery_Ter_Alias``)."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Imagery_OnDemand_Index as INDEX  # noqa: E402
import O4_Imagery_Ter_Alias as ALIAS  # noqa: E402

pytestmark = pytest.mark.skipif(sys.platform == "win32",
                                reason="symlinks need a privilege there")

NAME = "25328_10992_USA216.dds"
BASE = ("A\n800\nTERRAIN\n\nLOAD_CENTER 37.75334 -119.57520 7735 4096\n"
        "BASE_TEX_NOWRAP {ref}\nNO_ALPHA\n")
WATER = ("A\n800\nTERRAIN\n\nLOAD_CENTER 37.75334 -119.57520 7735 4096\n"
         "BASE_TEX_NOWRAP {ref}\nLOAD_CENTER_BORDER 37.75334 -119.57520 "
         "7735 1024\nBORDER_TEX ../../textures/+37-120/25328_10992_ZL16.png\n"
         "WET\nNO_SHADOW\n")


def _world_tile(tmp_path, ref="../../textures/+37-120/" + NAME):
    """A World-pack tile: ``terrain/+37-120`` names
    ``../../textures/+37-120/<name>``."""
    textures = tmp_path / "textures" / "+37-120"
    terrain = tmp_path / "terrain" / "+37-120"
    textures.mkdir(parents=True)
    terrain.mkdir(parents=True)
    (textures / NAME).write_bytes(b"placeholder")
    (terrain / (NAME[:-4] + ".ter")).write_text(
        BASE.format(ref=ref), encoding="utf-8", newline="\n")
    (terrain / (NAME[:-4] + "_water_overlay.ter")).write_text(
        WATER.format(ref=ref), encoding="utf-8", newline="\n")
    (terrain / "25328_11008_USA216.ter").write_text(
        BASE.format(ref="../../textures/+37-120/25328_11008_USA216.dds"),
        encoding="utf-8", newline="\n")
    return textures, terrain


def _refs(terrain):
    out = {}
    for ter in sorted(os.listdir(terrain)):
        with open(terrain / ter, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("BASE_TEX"):
                    out[ter] = line.split()[1]
    return out


def test_a_landing_gives_x_plane_a_new_path_that_opens_the_landed_file(
        tmp_path):
    textures, terrain = _world_tile(tmp_path)
    before = (terrain / (NAME[:-4] + "_water_overlay.ter")).read_text(encoding="utf-8")
    alias = ALIAS.renew(str(textures / NAME), str(terrain), now=1000.0)
    assert alias and os.path.islink(alias)
    assert os.path.dirname(alias) == str(textures / ALIAS.ALIAS_DIR)
    refs = _refs(terrain)
    rel = f"../../textures/+37-120/{ALIAS.ALIAS_DIR}/{os.path.basename(alias)}"
    assert refs[NAME[:-4] + ".ter"] == rel
    assert refs[NAME[:-4] + "_water_overlay.ter"] == rel
    # a .ter of another texture is untouched
    assert refs["25328_11008_USA216.ter"].endswith("/25328_11008_USA216.dds")
    # the path resolves, from the .ter, to the texture's own file
    seen = os.path.normpath(os.path.join(terrain, rel))
    assert os.path.realpath(seen) == os.path.realpath(textures / NAME)
    # every other line of the .ter is kept as it was
    after = (terrain / (NAME[:-4] + "_water_overlay.ter")).read_text(encoding="utf-8")
    assert [ln for ln in before.splitlines() if not ln.startswith("BASE_TEX")] \
        == [ln for ln in after.splitlines() if not ln.startswith("BASE_TEX")]


def test_each_landing_is_a_new_path_and_older_paths_open_the_newest_file(
        tmp_path):
    textures, terrain = _world_tile(tmp_path)
    paths = []
    for i, content in enumerate((b"1024", b"2048", b"4096")):
        partial = textures / (NAME + ".part")
        partial.write_bytes(content)
        os.replace(partial, textures / NAME)      # the lander's landing
        paths.append(ALIAS.renew(str(textures / NAME), str(terrain),
                                 now=1000.0 + i))
    assert len(set(paths)) == 3                   # never a path X-Plane holds
    # the path X-Plane may still hold (its last load's) opens the newest
    for path in paths:
        with open(path, "rb") as handle:
            assert handle.read() == b"4096"
    assert _refs(terrain)[NAME[:-4] + ".ter"].endswith(
        "/" + os.path.basename(paths[-1]))


def test_the_newest_symlinks_are_kept_older_ones_go(tmp_path):
    textures, terrain = _world_tile(tmp_path)
    made = [ALIAS.renew(str(textures / NAME), str(terrain), now=1000.0 + i)
            for i in range(ALIAS.KEEP + 3)]
    left = sorted(os.listdir(textures / ALIAS.ALIAS_DIR))
    assert left == sorted(os.path.basename(p) for p in made[-ALIAS.KEEP:])


def test_a_classic_tile_and_two_landings_in_one_tenth_of_a_second(tmp_path):
    textures, terrain = _world_tile(tmp_path, ref="../textures/" + NAME)
    a = ALIAS.renew(str(textures / NAME), str(terrain), now=5.0)
    b = ALIAS.renew(str(textures / NAME), str(terrain), now=5.0)
    assert a != b and os.path.islink(a) and os.path.islink(b)
    assert _refs(terrain)[NAME[:-4] + ".ter"] == \
        f"../textures/{ALIAS.ALIAS_DIR}/{os.path.basename(b)}"


def test_nothing_changes_where_no_ter_names_the_texture(tmp_path):
    textures, terrain = _world_tile(tmp_path)
    other = textures / "25360_10912_USA216.dds"
    other.write_bytes(b"x")
    assert ALIAS.renew(str(other), str(terrain)) is None
    assert not (textures / ALIAS.ALIAS_DIR).exists()
    assert ALIAS.renew(str(textures / NAME), None) is None
    assert ALIAS.renew(str(textures / "gone.dds"), str(terrain)) is None


def test_every_reader_sees_the_texture_not_the_symlink(tmp_path):
    textures, terrain = _world_tile(tmp_path)
    ALIAS.renew(str(textures / NAME), str(terrain), now=7.0)
    assert ALIAS.canonical("../../textures/+37-120/.xp_reload/"
                           "25328_10992_USA216~abc.dds") == NAME
    assert ALIAS.canonical("..\\textures\\" + NAME) == NAME
    read = INDEX._read_ter(str(terrain / (NAME[:-4] + ".ter")))
    assert read is not None and read[0] == NAME
    import O4_Imagery_OnDemand_Convert as CONVERT
    assert NAME in CONVERT._ter_textures(str(terrain))
    from tile_bundle import adopted
    flat = tmp_path / "flat"
    (flat / "terrain").mkdir(parents=True)
    os.replace(terrain / (NAME[:-4] + ".ter"), flat / "terrain" / "a.ter")
    assert adopted.texture_names(str(flat)) == [NAME]


def test_the_follow_job_renames_each_landed_texture(tmp_path):
    import O4_Imagery_Tier_Plan as PLAN
    from o4_engine import imagery_follow as FOLLOW
    textures, terrain = _world_tile(tmp_path)
    seen = []
    row = {"tile": "+37-120", "name": NAME, "build_dir": str(tmp_path),
           "textures_dir": str(textures), "terrain_dir": str(terrain)}

    def lander(row, tier):
        return {"tier_px": PLAN.TIER_WIDTH[tier]}
    job = FOLLOW.FollowJob(lambda e: None, reader=None, lander=lander,
                           renamer=lambda *a: seen.append(a))
    facts, _at = job._land(row, 3)
    assert facts["tier_px"] == 4096
    assert seen == [(str(textures / NAME), str(terrain))]
    real = FOLLOW.FollowJob(lambda e: None, reader=None, lander=lander)
    real._land(row, 3)
    assert ALIAS.ALIAS_DIR in _refs(terrain)[NAME[:-4] + ".ter"]
