"""THE REGION of the tree upgrade (issue #1965): the tile's climate from
X-Plane 12's own definitions, and the species and forests each old flat
tree takes there; a pack's grass and reeds never become trees in any
climate (#1920).

Synthetic names, ``tmp_path`` packs and a Python stand-in for DSFTool;
no corpus, no X-Plane.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from auto_patch_v2.airport import pack_forests as PF
from auto_patch_v2.airport import pack_trees as PT
from auto_patch_v2.airport.pack_climate import (
    DEFAULT,
    Climate,
    climate_of_names,
    g8_forest,
    latitude_climate,
    regional_family,
)
from auto_patch_v2.airport.pack_trees_map import FAMILIES

T = "lib/vegetation/trees/"
TROPIC = Climate("vhot", "wet", "global scenery")
DESERT = Climate("vhot", "dry", "global scenery")
MED = Climate("wrm", "sdry", "global scenery")
NORTH = Climate("cld", "wet", "global scenery")


# ── THE WITNESS ─────────────────────────────────────────────────────────

def test_the_climate_is_the_most_named_temperature_and_moisture():
    names = ["lib/g10/terrain10/fst_hot_wet_hill.ter",
             "lib/g10/terrain10/grass_vhot_wet.ter",
             "lib/g8/broad_vhot_sdry.for", "lib/g8/wetl_wdy_vhot_rain.for",
             "terrain_Water", "lib/g12/beaches.bch"]
    assert climate_of_names(names) == Climate("vhot", "wet", "global scenery")


def test_a_tie_goes_to_the_cooler_and_the_wetter_tier():
    assert climate_of_names(["a_tmp_sdry.ter", "b_wrm_wet.ter"]).tag == "tmp_wet"


def test_names_without_a_climate_say_nothing():
    assert climate_of_names(["terrain_Water", "lib/g8/palms.for"]) is None


@pytest.mark.parametrize("lat,temp", [(24.6, "hot"), (-12, "vhot"), (26, "hot"),
                                      (37.9, "wrm"), (51.5, "tmp"),
                                      (64, "cld"), (-78, "vcld")])
def test_the_latitude_band_stands_in(lat, temp):
    assert latitude_climate(lat) == Climate(temp, "wet", "latitude")


# ── THE CHOICE ──────────────────────────────────────────────────────────

def test_a_local_forest_takes_its_type_and_density_in_the_climate():
    assert g8_forest("broad", False, TROPIC) == "lib/g8/broad_vhot_wet.for"
    assert g8_forest("coni", True, MED) == "lib/g8/coni_sp_wrm_sdry.for"
    assert g8_forest("mixed", False, None) == "lib/g8/mixed_tmp_wet.for"


@pytest.mark.parametrize("cls,climate,family", [
    ("conifer", TROPIC, "palm/palm_*.for"),            # no fir in the tropics
    ("conifer", DESERT, "palm/date_palm_*.for"),
    ("conifer", MED, "evergreen/cypress_*.for"),
    ("conifer", None, "coniferous/spruce_*.for"),      # the temperate default
    ("conifer", NORTH, "coniferous/spruce_*.for"),
    ("broadleaf", TROPIC, "evergreen/kapok_*.for"),
    ("broadleaf", MED, "deciduous/oak_*.for"),
    ("broadleaf", DEFAULT, "deciduous/broadleaf_*.for"),
    ("broadleaf", NORTH, "deciduous/birch_*.for"),
    ("palm", TROPIC, "palm/palm_*.for"),
    ("palm", MED, "palm/date_palm_*.for"),
    ("shrub", TROPIC, ""),
])
def test_a_generic_tree_takes_the_regions_species(cls, climate, family):
    got = regional_family(cls, climate)
    assert got == (T + family if family else "")
    assert not got or got in FAMILIES


def test_every_family_runs_low_to_high():
    for fam in FAMILIES.values():
        heights = [h for _p, h in fam]
        assert heights == sorted(heights) and len(set(heights)) == len(heights)


# ── A PACK'S OWN .for ───────────────────────────────────────────────────

def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _for(rows, spacing="5 5") -> str:
    return ("A\n800\nFOREST\nTEXTURE t.png\nSCALE_X 2048\nSCALE_Y 2048\n"
            f"SPACING {spacing}\n" + "".join(
                f"TREE 0 0 {w} {h} 0 {f} {lo} {hi} 2 1\n"
                for w, h, f, lo, hi in rows))


BROAD = [(577, 618, 20, 7, 15)]
NARROW = [(200, 618, 50, 7, 13)]


def test_a_local_forest_is_the_regions(tmp_path):
    p = str(_write(tmp_path / "veg_high.for", _for(BROAD)))
    assert PT.local_forest_target(p, TROPIC) == "lib/g8/broad_vhot_wet.for"
    assert PT.local_forest_target(p, MED) == "lib/g8/broad_wrm_sdry.for"
    assert PT.local_forest_target(p) == "lib/g8/broad_tmp_wet.for"


def test_a_palm_forest_stays_a_palm_of_the_region(tmp_path):
    # KEYW's palm_trees.for went to a temperate conifer forest (#1965)
    p = str(_write(tmp_path / "palm_trees.for", _for(NARROW)))
    assert PT.local_forest_target(p, TROPIC) == T + "palm/coconut_palm_medium.for"
    assert PT.local_forest_target(p, MED) == T + "palm/date_palm_medium.for"


@pytest.mark.parametrize("name", ["reed_tall.for", "grass_high.for",
                                  "palm_grass.for"])
@pytest.mark.parametrize("climate", [TROPIC, MED, NORTH, None])
def test_grass_and_reeds_never_become_trees_anywhere(tmp_path, name, climate):
    # #1920 (RULINGS 2026-11-06d (11)): the pack keeps its own grass file
    p = str(_write(tmp_path / name, _for([(300, 600, 50, 2, 6)])))
    assert PT.local_forest_target(p, climate) == ""


# ── A FLAT TREE OBJECT ──────────────────────────────────────────────────

def _billboard(h: float, width: float, tex: str = "trees.dds") -> str:
    w = width / 2
    vt, idx = [], []
    for (ax, az, bx, bz) in ((-w, 0, w, 0), (0, -w, 0, w)):
        n = len(vt)
        vt += [f"VT {ax} {h} {az} 0 1 0 0 1", f"VT {bx} {h} {bz} 0 1 0 1 1",
               f"VT {bx} 0 {bz} 0 1 0 1 0", f"VT {ax} 0 {az} 0 1 0 0 0"]
        idx += [n, n + 1, n + 2, n, n + 2, n + 3]
    return (f"I\n800\nOBJ\nTEXTURE {tex}\nPOINT_COUNTS {len(vt)} 0 0 {len(idx)}\n"
            + "\n".join(vt) + "\n" + "\n".join(f"IDX {i}" for i in idx)
            + f"\nTRIS 0 {len(idx)}\n")


@pytest.mark.parametrize("name,width,climate,family", [
    ("Tree_07.obj", 2.0, TROPIC, "palm/palm_*.for"),         # narrow, tropics
    ("Tree_07.obj", 2.0, None, "coniferous/spruce_*.for"),   # as before
    ("Tree_07.obj", 10.0, TROPIC, "evergreen/kapok_*.for"),
    ("Tree_07.obj", 10.0, NORTH, "deciduous/birch_*.for"),
    ("Veg_Fir_01.obj", 2.0, TROPIC, "coniferous/fir_*.for"),  # named: stays
    ("Veg_Conifer_01.obj", 2.0, MED, "evergreen/cypress_*.for"),
    ("Veg_Palm_01.obj", 10.0, DESERT, "palm/date_palm_*.for"),
])
def test_a_tree_object_keeps_its_species_or_takes_the_regions(
        tmp_path, name, width, climate, family):
    ft = PT.flat_trees(str(_write(tmp_path / name, _billboard(12, width))))
    assert PT.object_family(ft, climate) == T + family


DUMP = ("PROPERTY sim/west -82\nPROPERTY sim/east -81\n"
        "PROPERTY sim/north 25\nPROPERTY sim/south 24\n"
        "POLYGON_DEF vegetation/palm_trees.for\n"
        "OBJECT_DEF Veg/Tree_01.obj\n"
        "OBJECT 0 -81.5 24.5 0.0\n"
        "BEGIN_POLYGON 0 255 2\nBEGIN_WINDING\n"
        "POLYGON_POINT -81.5 24.5\nPOLYGON_POINT -81.4 24.5\n"
        "POLYGON_POINT -81.4 24.6\nEND_WINDING\nEND_POLYGON\n")


def test_the_check_asks_the_climate_once_and_uses_it(tmp_path):
    ds = tmp_path / "X-Plane 12" / "Resources" / "default scenery"
    solid = "A\n1200\nFOREST\nSHADER_3D\nMESH 0 3 3\n"
    index = {v: str(_write(ds / "1200 forests" / v, solid))
             for fam in FAMILIES.values() for v, _h in fam}
    pack = tmp_path / "X-Plane 12" / "Custom Scenery" / "Pack"
    _write(pack / "vegetation" / "palm_trees.for", _for(NARROW))
    _write(pack / "Veg" / "Tree_01.obj", _billboard(12, 2.0))
    asked = []

    def climate():
        asked.append(1)
        return TROPIC
    got = PF.old_forests(str(pack), DUMP.splitlines(True), index, str(ds),
                         climate=climate)
    assert asked == [1]
    assert [(f.path, f.target) for f in got] == [
        ("vegetation/palm_trees.for", T + "palm/coconut_palm_medium.for"),
        ("Veg/Tree_01.obj", T + "palm/palm_*.for")]
    lines = PF.target_lines(got, TROPIC)
    assert lines[0] == "climate vhot_wet (from global scenery)"
    assert lines[1] == f"vegetation/palm_trees.for -> {T}palm/coconut_palm_medium.for"


# ── THE READER ──────────────────────────────────────────────────────────

def test_the_header_read_stops_the_tool_at_the_first_other_row():
    import O4_DSFTool
    script = ("import sys\nprint('A'); print('TERRAIN_DEF a_hot_wet.ter')\n"
              "print('BEGIN_PATCH 0')\nsys.stdout.flush()\n"
              "while True: print('x' * 80)\n")
    got = O4_DSFTool.head([sys.executable, "-c", script],
                          lambda ln: ln.startswith("BEGIN"), timeout=20)
    assert got == ["A", "TERRAIN_DEF a_hot_wet.ter"]


def test_a_tile_without_global_scenery_takes_the_latitude_band(tmp_path):
    from auto_patch import forest_stage as GC
    assert GC._tile_climate(str(tmp_path), 24, -82) == Climate("hot", "wet",
                                                              "latitude")


def test_a_global_scenery_tile_gives_x_planes_own_climate(tmp_path, monkeypatch):
    from auto_patch import forest_stage as GC
    dsf = _write(tmp_path / "Global Scenery" / "X-Plane 12 Global Scenery"
                 / "Earth nav data" / "+30+020" / "+37+023.dsf", "7z")
    calls = []

    def defs(path):
        calls.append(path)
        return ["lib/g8/broad_wrm_sdry.for", "lib/g10/terrain10/x_wrm_dry.ter",
                "lib/g10/terrain10/y_wrm_sdry.ter"]
    monkeypatch.setattr(GC, "_definitions", defs)
    monkeypatch.setattr(GC, "_MEMO", {})
    for _ in range(2):
        assert GC._tile_climate(str(tmp_path), 37, 23) == MED
    assert calls == [str(dsf)], "read once per tile"
