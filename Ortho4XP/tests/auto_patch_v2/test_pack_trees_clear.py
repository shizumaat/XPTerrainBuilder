"""Twins of issue #1920: the X-Plane 12 tree upgrade puts no tree on a
runway strip, its safety area or a taxiway strip
(``auto_patch_v2.airport.pack_trees_clear``), and the record says which
rules wrote it (``pack_forests.UPGRADE_VERSION``)."""
from __future__ import annotations

import math

from auto_patch_v2.airport import pack_forests as PF
from auto_patch_v2.airport import pack_trees_clear as PC
from shapely.geometry import Point

# a N-S code-4 precision runway (3,000 m, 45 m) and one taxiway east of it
LAT0, LON0 = 37.90, 23.90
M_LAT = 1.0 / (math.pi * PC.EARTH_R / 180.0)
M_LON = M_LAT / math.cos(math.radians(LAT0))
DLAT = 3000.0 * M_LAT
RW100 = (f"100 45.00 1 0 0.25 1 2 0 01 {LAT0:.8f} {LON0:.8f} 0 0 3 0 0 0 "
         f"19 {LAT0 + DLAT:.8f} {LON0:.8f} 0 0 3 0 0 0")
APT = f"""I
1200 Version

1 300 0 0 ZZZZ Synthetic
{RW100}
1201 {LAT0 + 1500 * M_LAT:.8f} {LON0 + 400 * M_LON:.8f} both 1 a
1201 {LAT0 + 1500 * M_LAT:.8f} {LON0 + 600 * M_LON:.8f} both 2 b
1202 1 2 twoway taxiway_E A
99
"""
TREE = "lib/g8/broad_tmp_wet.for"


def _pack(tmp_path):
    (tmp_path / "Earth nav data").mkdir()
    (tmp_path / "Earth nav data" / "apt.dat").write_text(APT, encoding="utf-8", newline="\n")
    return str(tmp_path)


def _pt(east_m: float, north_m: float) -> Point:
    return Point(LON0 + east_m * M_LON, LAT0 + north_m * M_LAT)


def _square(east_m: float, north_m: float, side: float = 20.0) -> str:
    pts = [_pt(east_m + dx, north_m + dy)
           for dx, dy in ((0, 0), (side, 0), (side, side), (0, side))]
    return ("BEGIN_POLYGON 0 255 2\nBEGIN_WINDING\n"
            + "".join(f"POLYGON_POINT {p.x:.9f} {p.y:.9f}\n" for p in pts)
            + "END_WINDING\nEND_POLYGON\n")


def _dump(*polys: str, defs=(TREE,)) -> str:
    return ("PROPERTY sim/west 23\n"
            + "".join(f"POLYGON_DEF {d}\n" for d in defs) + "".join(polys))


def test_the_areas_read_the_strip_and_safety_area_law(tmp_path):
    rw, twy = PC.clear_areas(_pack(tmp_path))
    # ICAO code 4 precision: 75 m each side; 300 m beyond each end (the
    # strip's 60 m end + the 240 m RESA)
    assert rw.contains(_pt(70, 1500)) and not rw.contains(_pt(80, 1500))
    assert rw.contains(_pt(0, -290)) and not rw.contains(_pt(0, -310))
    # taxiway letter E: 19 m each side of the centreline
    assert twy.contains(_pt(500, 1515)) and not twy.contains(_pt(500, 1525))


def test_a_tree_inside_the_strip_goes_and_one_outside_stays(tmp_path):
    pack = _pack(tmp_path)
    inside, outside = _square(20, 1000), _square(250, 1000)
    in_resa = _square(-10, -200)
    text, n = PF.clear_strips(_dump(inside, outside, in_resa), {TREE}, pack)
    assert n == 2
    assert outside in text and inside not in text and in_resa not in text


def test_a_forest_across_the_strip_edge_is_cut_at_it(tmp_path):
    pack = _pack(tmp_path)
    text, n = PF.clear_strips(_dump(_square(60, 1000, side=40)), {TREE}, pack)
    assert n == 1
    east = [(float(ln.split()[1]) - LON0) / M_LON for ln in text.splitlines()
            if ln.startswith("POLYGON_POINT")]
    assert east and min(east) >= 75.0 - 0.01 and max(east) <= 100.0 + 0.01


def test_the_taxiway_strip_is_clear_too(tmp_path):
    text, n = PF.clear_strips(_dump(_square(490, 1495, side=10)), {TREE},
                              _pack(tmp_path))
    assert n == 1 and "BEGIN_POLYGON" not in text


def test_point_forests_lose_the_trees_inside(tmp_path):
    pts = [_pt(10, 1000), _pt(300, 1000)]
    block = ("BEGIN_POLYGON 0 767 2\nBEGIN_WINDING\n"
             + "".join(f"POLYGON_POINT {p.x:.9f} {p.y:.9f}\n" for p in pts)
             + "END_WINDING\nEND_POLYGON\n")
    fam = "lib/vegetation/trees/deciduous/oak_big.for"
    text, n = PF.clear_strips(_dump(block, defs=(fam,)), set(), _pack(tmp_path))
    assert n == 1 and text.count("POLYGON_POINT") == 1


def test_the_packs_own_grass_is_left_alone(tmp_path):
    # not written by the upgrade and no taller than grass: it stays
    root = _pack(tmp_path)
    _own_for(tmp_path, "Vegetation/grass.for", 0.9)
    dump = _dump(_square(20, 1000), defs=("Vegetation/grass.for",))
    assert PF.clear_strips(dump, {TREE}, root) == (dump, 0)


def test_a_pack_without_an_apt_dat_clears_nothing(tmp_path):
    dump = _dump(_square(20, 1000))
    assert PF.clear_strips(dump, {TREE}, str(tmp_path)) == (dump, 0)


def test_the_record_carries_the_rules_it_was_written_under():
    row = PF.record("sha", {"a.for": TREE}, 1, "t")
    assert PF.recorded_version({PF.RECORD_KEY: row}) == PF.UPGRADE_VERSION
    del row["version"]                           # a record from before #1920
    assert PF.recorded_version({PF.RECORD_KEY: row}) == 1
    assert PF.recorded({PF.RECORD_KEY: row}, "sha") == {"a.for": TREE}


def test_a_line_forest_crossing_the_strip_goes_whole(tmp_path):
    pts = [_pt(-200, 1000), _pt(200, 1000)]         # both ends outside
    block = ("BEGIN_POLYGON 0 383 2\nBEGIN_WINDING\n"
             + "".join(f"POLYGON_POINT {p.x:.9f} {p.y:.9f}\n" for p in pts)
             + "END_WINDING\nEND_POLYGON\n")
    text, n = PF.clear_strips(_dump(block), {TREE}, _pack(tmp_path))
    assert n == 1 and "BEGIN_POLYGON" not in text


def test_only_grass_stands_on_the_strips(tmp_path):
    # a shrub planter (1.1 m) is cleared like a tree; grass (1.0 m) stays
    grass = "lib/vegetation/planters/ground/grass_green_1.for"
    shrub = "lib/vegetation/planters/ground/shrubs_red_1.for"
    dump = _dump(_square(20, 1000), _square(20, 1000).replace(
        "BEGIN_POLYGON 0", "BEGIN_POLYGON 1"), defs=(grass, shrub))
    text, n = PF.clear_strips(dump, {grass, shrub}, _pack(tmp_path))
    assert n == 1
    assert "BEGIN_POLYGON 0 255" in text and "BEGIN_POLYGON 1 " not in text


def _own_for(root, rel: str, top_m: float) -> None:
    # one TREE row: s t w h offset freq min max quads (max height = top_m)
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("A\n800\nFOREST\nTEXTURE t.png\nSPACING 3 3\n"
                 f"TREE 0 0 128 256 64 50 {top_m * 0.6} {top_m} 1 palm\n",
                 encoding="utf-8", newline="\n")


def test_the_packs_own_tall_forest_is_cleared_in_the_strip_only(tmp_path):
    # RULINGS 2026-11-06d (8): a kept own file (D2V/reed.for, 6 m) is
    # cleared inside the strip and stays outside; own grass (0.8 m) stays
    root = _pack(tmp_path)
    _own_for(tmp_path, "D2V/reed.for", 6.0)
    _own_for(tmp_path, "D2V/lawn.for", 0.8)
    inside, outside = _square(20, 1000), _square(500, 1000)
    lawn = _square(20, 1200).replace("BEGIN_POLYGON 0", "BEGIN_POLYGON 1")
    text, n = PF.clear_strips(_dump(inside, outside, lawn,
                                    defs=("D2V/reed.for", "D2V/lawn.for")),
                              set(), root)
    assert n == 1
    assert text.count("BEGIN_POLYGON 0 255") == 1        # the outside one
    assert "BEGIN_POLYGON 1 255" in text


def test_a_recorded_upgrade_before_the_ruling_is_redone():
    assert PF.UPGRADE_VERSION >= 4
