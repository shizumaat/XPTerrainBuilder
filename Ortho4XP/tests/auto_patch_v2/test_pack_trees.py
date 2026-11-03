"""OLD FLAT TREES that are not library forests (issue #1710): flat tree
OBJECTS become X-Plane 12 3D point forests, a pack's own flat ``.for``
maps by its trees, ground cover stays.

Synthetic ``tmp_path`` packs and installs only; no corpus, no X-Plane,
no DSFTool.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from auto_patch_v2.airport import pack_forests as PF
from auto_patch_v2.airport import pack_trees as PT
from auto_patch_v2.airport.pack_trees_map import FAMILIES, LOCAL_FOREST

FIR = "lib/vegetation/trees/coniferous/fir_*.for"
SOLID = "A\n1200\nFOREST\nSHADER_3D\nMESH 0 3 3\n"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _billboards(trees, width=2.0, tex="trees.dds", extra="") -> str:
    """An OBJ8 of crossed quads: one cross (two quads) per (x, z, h)."""
    vt: list[str] = []
    idx: list[int] = []
    for x, z, h in trees:
        w = width / 2
        for (ax, az, bx, bz) in ((x - w, z, x + w, z), (x, z - w, x, z + w)):
            n = len(vt)
            vt += [f"VT {ax} {h} {az} 0 1 0 0 1", f"VT {bx} {h} {bz} 0 1 0 1 1",
                   f"VT {bx} 0 {bz} 0 1 0 1 0", f"VT {ax} 0 {az} 0 1 0 0 0"]
            idx += [n, n + 1, n + 2, n, n + 2, n + 3]
    body = "\n".join(vt) + "\n" + "\n".join(f"IDX {i}" for i in idx)
    return (f"I\n800\nOBJ\nTEXTURE {tex}\n{extra}POINT_COUNTS {len(vt)} 0 0 "
            f"{len(idx)}\n{body}\nTRIS 0 {len(idx)}\n")


def _mesh() -> str:
    """A real 3D object: triangles that are not quads."""
    return ("I\n800\nOBJ\nTEXTURE tree.dds\nPOINT_COUNTS 3 0 0 3\n"
            "VT 0 0 0 0 1 0 0 0\nVT 1 5 0 0 1 0 1 0\nVT 0 5 1 0 1 0 0 1\n"
            "IDX 0\nIDX 1\nIDX 2\nTRIS 0 3\n")


# ── THE CHECK OF AN OBJECT ──────────────────────────────────────────────

def test_a_flat_tree_object_reads_its_trees_and_species(tmp_path):
    p = _write(tmp_path / "Veg" / "Pack_Veg_Fir_01.obj",
               _billboards([(0, 0, 6), (10, 0, 18), (0, 30, 25)]))
    ft = PT.flat_trees(str(p))
    assert ft is not None and ft.family == FIR
    assert sorted(round(h) for _x, _z, h in ft.trees) == [6, 18, 25], \
        "a crossed pair is ONE tree"


@pytest.mark.parametrize("width,height,family", [
    (2.0, 12, "coniferous/spruce_*.for"),        # narrow: a conifer
    (10.0, 12, "deciduous/broadleaf_*.for"),     # wide: broadleaf
    (2.0, 2, "deciduous/shrubs_*.for"),          # wide for its height, low
])
def test_an_unnamed_tree_takes_its_kind_from_its_shape(tmp_path, width, height,
                                                       family):
    p = _write(tmp_path / "Tree_07.obj",
               _billboards([(0, 0, height)], width=width))
    assert PT.flat_trees(str(p)).family.endswith(family)


@pytest.mark.parametrize("name,text", [
    ("Hangar_01.obj", _billboards([(0, 0, 10)], tex="hangar.dds")),  # no tree word
    ("Tree_3D.obj", _mesh()),                           # a real 3D tree
    ("Tree_anim.obj", _billboards([(0, 0, 10)]) + "ANIM_begin\nTRIS 0 6\nANIM_end\n"),
])
def test_what_is_not_a_flat_tree_object(tmp_path, name, text):
    assert PT.flat_trees(str(_write(tmp_path / name, text))) is None


def test_a_tree_texture_names_it_too(tmp_path):
    p = _write(tmp_path / "obj_01.obj", _billboards([(0, 0, 10)],
                                                     tex="birch_trees.dds"))
    assert PT.flat_trees(str(p)).family.endswith("deciduous/birch_*.for")


def test_the_size_is_the_nearest_height():
    assert PT._size_for(FIR, 6).endswith("fir_small.for")
    assert PT._size_for(FIR, 15).endswith("fir_big.for")
    assert PT._size_for(FIR, 40).endswith("fir_tall.for")


# ── A PACK'S OWN .for ───────────────────────────────────────────────────

def _for(rows, spacing="5 5") -> str:
    return ("A\n800\nFOREST\nTEXTURE t.png\nSCALE_X 2048\nSCALE_Y 2048\n"
            f"SPACING {spacing}\n" + "".join(
                f"TREE 0 0 {w} {h} 0 {f} {lo} {hi} 2 1\n"
                for w, h, f, lo, hi in rows))


@pytest.mark.parametrize("rows,spacing,want", [
    ([(577, 618, 20, 7, 15), (499, 514, 20, 7, 15)], "4.5 5", ("broad", False)),
    ([(200, 618, 50, 7, 15)], "4.5 5", ("coni", False)),
    ([(200, 618, 50, 7, 15), (600, 600, 50, 7, 15)], "14 14", ("mixed", True)),
    ([(600, 600, 100, 1, 3)], "4 4", ("shrb", False)),
])
def test_a_local_forest_maps_by_its_trees(tmp_path, rows, spacing, want):
    p = _write(tmp_path / "forest.for", _for(rows, spacing))
    assert PT.local_forest_target(str(p)) == LOCAL_FOREST[want]


def test_ground_cover_maps_to_nothing(tmp_path):
    grass = _write(tmp_path / "grass.for",
                   _for([(300, 60, 100, 0.1, 0.4)], "0.4 0.4"))
    assert PT.local_forest_target(str(grass)) == ""


# ── THE CHECK IN A PACK, AND THE REWRITE ────────────────────────────────

DUMP = ("PROPERTY sim/west -113\nPROPERTY sim/south 43\n"
        "PROPERTY sim/east -112\nPROPERTY sim/north 44\n"
        "OBJECT_DEF objects/hangar.obj\n"
        "OBJECT_DEF Veg/Pack_Veg_Fir_01.obj\n"
        "POLYGON_DEF vegetation/local.for\n"
        "OBJECT 0 -112.5 43.5 0.0\n"
        "OBJECT 1 -112.5 43.5 90.0\n"
        "BEGIN_POLYGON 0 255 2\n"
        "BEGIN_WINDING\nPOLYGON_POINT -112.4 43.4\nEND_WINDING\n"
        "END_POLYGON\n")


def _install(tmp_path: Path):
    xp = tmp_path / "X-Plane 12"
    ds = xp / "Resources" / "default scenery"
    index = {}
    for fam in FAMILIES.values():
        for vpath, _h in fam:
            index[vpath] = str(_write(ds / "1200 forests" / vpath, SOLID))
    index["lib/g8/broad_tmp_wet.for"] = str(_write(ds / "g8" / "b.for", SOLID))
    pack = xp / "Custom Scenery" / "Pack"
    _write(pack / "objects" / "hangar.obj",
           _billboards([(0, 0, 10)], tex="hangar.dds"))
    _write(pack / "Veg" / "Pack_Veg_Fir_01.obj",
           _billboards([(0, 0, 6), (0, 20, 25)]))
    _write(pack / "vegetation" / "local.for",
           _for([(577, 618, 20, 7, 15)]))
    return pack, index, str(ds)


def test_the_check_offers_tree_objects_and_the_local_forest(tmp_path):
    pack, index, ds = _install(tmp_path)
    got = PF.old_forests(str(pack), DUMP.splitlines(True), index, ds)
    assert got == (
        PF.OldForest(0, "vegetation/local.for", 1, "lib/g8/broad_tmp_wet.for",
                     True),
        PF.OldForest(1, "Veg/Pack_Veg_Fir_01.obj", 1, FIR, True, "object"),
    ), "a hangar with no tree word is not a tree"


def test_an_install_without_the_3d_trees_offers_nothing(tmp_path):
    pack, _index, ds = _install(tmp_path)
    got = PF.old_forests(str(pack), DUMP.splitlines(True), {}, ds)
    assert got and not PF.renames_of(got)


def test_the_rewrite_turns_each_placement_into_point_forests(tmp_path):
    pack, index, ds = _install(tmp_path)
    renames = PF.renames_of(PF.old_forests(str(pack), DUMP.splitlines(True),
                                           index, ds))
    # the placement write split the tree object into a body: same tree
    edited = DUMP.replace("OBJECT_DEF Veg/Pack_Veg_Fir_01.obj\n",
                          "OBJECT_DEF Veg/Pack_Veg_Fir_01__b0_1a2b3c4d.obj\n")
    out, n = PF.apply_upgrade(edited, DUMP, renames, str(pack))
    assert n == 2
    assert "Pack_Veg_Fir_01" not in out, "the object and its body are gone"
    assert "OBJECT 0 -112.5 43.5 0.0" in out, "the hangar stays"
    assert "POLYGON_DEF lib/g8/broad_tmp_wet.for\n" in out
    defs = [r.split()[1] for r in out.splitlines() if r.startswith("POLYGON_DEF")]
    assert defs[1:] == ["lib/vegetation/trees/coniferous/fir_small.for",
                        "lib/vegetation/trees/coniferous/fir_tall.for"]
    rows = out.splitlines()
    k = rows.index("BEGIN_POLYGON 1 767 2")
    lon, lat = map(float, rows[k + 2].split()[1:])
    assert (lon, lat) == pytest.approx((-112.5, 43.5))
    k = rows.index("BEGIN_POLYGON 2 767 2")
    lon, lat = map(float, rows[k + 2].split()[1:])
    # heading 90: authored +z (south) turns to the west, 20 m
    assert lat == pytest.approx(43.5, abs=1e-7)
    assert (lon + 112.5) * 111195 * 0.7254 == pytest.approx(-20, abs=0.2)


def test_trees_off_the_tile_are_not_placed(tmp_path):
    pack, index, ds = _install(tmp_path)
    dump = DUMP.replace("OBJECT 1 -112.5 43.5 90.0", "OBJECT 1 -112.0 43.5 270.0")
    renames = {"Veg/Pack_Veg_Fir_01.obj": FIR}
    out, _n = PF.apply_upgrade(dump, dump, renames, str(pack))
    pts = [r for r in out.splitlines() if r.startswith("POLYGON_POINT")]
    assert all(float(r.split()[1]) <= -112.0 for r in pts)


def test_no_upgrade_is_the_text_unchanged(tmp_path):
    pack, _index, _ds = _install(tmp_path)
    assert PF.apply_upgrade(DUMP, DUMP, {}, str(pack)) == (DUMP, 0)
