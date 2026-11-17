"""Twins of the pack-edit writers of spec 2123 (P0): ``airport/apt_edit``
(110 hole / notch, 120 split), ``airport/dsf_poly_clip`` (page clip, UV
refusal) and ``airport/dsf_additions`` (object row, road chain)."""
from __future__ import annotations

import json

import pytest
from shapely.geometry import Polygon, box

from auto_patch_v2.airport import apt_dat, apt_edit, dsf_additions, dsf_poly_clip

# a 0.01 deg square apron (CCW) with one CW hole, a centre line across it
# carrying a yellow line and centreline lights, and an untouched sign row
BLOCK = [
    "1    137 0 0 TEST Test Airport",
    "110 1 0.25 0.00 Apron",
    "111 59.00000000 17.00000000",
    "111 59.00000000 17.01000000 3",
    "111 59.01000000 17.01000000",
    "113 59.01000000 17.00000000",
    "111 59.00800000 17.00100000",
    "111 59.00900000 17.00100000",
    "111 59.00900000 17.00200000",
    "113 59.00800000 17.00200000",
    "120 Centre",
    "111 59.00500000 17.00000000 1 101",
    "111 59.00500000 17.00500000 1 101",
    "115 59.00500000 17.01000000",
    "120 Far line",
    "111 59.00900000 17.00800000 3",
    "115 59.00950000 17.00800000",
    "20 59.00100000 17.00100000 0.0 0 2 {@Y}A",
]


def _pav(block):
    return list(apt_dat.parse_airport_block(block).pavements)


def test_inside_region_becomes_a_hole_and_raw_contours_stay():
    region = box(17.004, 59.004, 17.006, 59.006)         # lon, lat
    res = apt_edit.cut_block(BLOCK, region)
    (pav,) = _pav(res.block)
    assert len(pav.rings) == 3                          # exterior + old hole + new hole
    assert Polygon(pav.rings[0], pav.rings[1:]).is_valid
    assert Polygon(pav.rings[0]).exterior.is_ccw
    assert all(not Polygon(r).exterior.is_ccw for r in pav.rings[1:])
    # the exterior and the old hole are untouched: their raw rows are copied
    assert [ln for ln in res.block if ln in BLOCK[2:10]] == BLOCK[2:10]
    assert "20 59.00100000 17.00100000 0.0 0 2 {@Y}A" in res.block
    assert res.record[0]["kind"] == "pavement_cut"
    assert res.record[0]["contours_rewritten"] == 1


def test_crossing_region_notches_and_keeps_edge_codes():
    region = box(17.004, 58.999, 17.006, 59.002)         # bites the south edge
    res = apt_edit.cut_block(BLOCK, region)
    (pav,) = _pav(res.block)
    assert len(pav.rings) == 2 and Polygon(pav.rings[0], pav.rings[1:]).is_valid
    rows = [ln.split() for ln in res.block if ln.startswith(("111", "113"))]
    # the east edge (code 3 on its start node) survives with its code;
    # the notch's new edges carry none
    assert ["111", "59.00000000", "17.01000000", "3"] in rows
    notch = [t for t in rows if t[1] == "59.00200000"]
    assert len(notch) == 2 and all(len(t) == 3 for t in notch)


def test_line_is_split_and_the_inside_returned():
    region = box(17.004, 59.004, 17.006, 59.006)
    res = apt_edit.cut_block(BLOCK, region)
    centres = [i for i, ln in enumerate(res.block) if ln == "120 Centre"]
    assert len(centres) == 2
    (d,) = res.dropped
    assert (d.line, d.light) == (1, 101)
    assert d.points[0][0] == pytest.approx(17.004)
    assert d.points[-1][0] == pytest.approx(17.006)
    first = res.block[centres[0] + 1:centres[1]]
    assert first[0].split()[3:] == ["1", "101"] and first[-1].split()[0] == "115"
    assert "120 Far line" in res.block                 # untouched feature stays raw


def test_edit_apt_dat_writes_file_and_record(tmp_path):
    src = tmp_path / "apt.dat"
    src.write_text("I\n1200 test\n\n" + "\n".join(BLOCK) + "\n\n99\n", encoding="utf-8")
    dst = tmp_path / "out.dat"
    apt_edit.edit_apt_dat(str(src), str(dst), "TEST", box(17.004, 59.004, 17.006, 59.006))
    text = dst.read_text(encoding="utf-8")
    assert text.startswith("I\n1200 test\n") and text.rstrip().endswith("99")
    rec = json.loads((tmp_path / ("out.dat" + apt_edit.EDITS_SUFFIX)).read_text())
    assert rec["icao"] == "TEST"
    assert {e["kind"] for e in rec["edits"]} == {"pavement_cut", "line_split"}


DUMP = "\n".join([
    "A", "800 written by DSFTool", "DSF2TEXT", "",
    "PROPERTY sim/west 17", "PROPERTY sim/overlay 1",
    "OBJECT_DEF lib/a.obj",
    "POLYGON_DEF lib/airport/pavement/asphalt_1L.pol",
    "POLYGON_DEF lib/airport/markings/DrapedLocSigns.pol",
    "POLYGON_DEF lib/fac/hangar.fac",
    "OBJECT 0 17.001 59.001 0.0",
    "BEGIN_POLYGON 0 0 4", "BEGIN_WINDING",
    "POLYGON_POINT 17.000 59.000 17.000 59.000",
    "POLYGON_POINT 17.010 59.000 17.010 59.000",
    "POLYGON_POINT 17.010 59.010 17.010 59.010",
    "POLYGON_POINT 17.000 59.010 17.000 59.010",
    "END_WINDING", "END_POLYGON",
    "BEGIN_POLYGON 1 65535 4", "BEGIN_WINDING",
    "POLYGON_POINT 17.020 59.020 0.1 0.1",
    "POLYGON_POINT 17.021 59.020 0.9 0.1",
    "POLYGON_POINT 17.021 59.021 0.9 0.9",
    "END_WINDING", "END_POLYGON",
    "BEGIN_POLYGON 2 5 3", "BEGIN_WINDING",
    "POLYGON_POINT 17.004 59.004 0", "POLYGON_POINT 17.006 59.004 0",
    "POLYGON_POINT 17.006 59.006 0", "END_WINDING", "END_POLYGON", ""])


def test_page_clip_cuts_pages_only():
    text, rep = dsf_poly_clip.clip_text(DUMP, box(17.004, 59.004, 17.006, 59.006))
    assert rep.pages_cut == 1 and rep.area_removed_m2 > 0
    assert text.count("BEGIN_POLYGON 0 0 4") == 1
    assert text.count("BEGIN_WINDING") == 4             # the page gained a hole winding
    # the UV page (far away; its u v are NOT a bezier control) and the
    # facade are copied untouched
    assert "POLYGON_POINT 17.020 59.020 0.1 0.1" in text
    assert "BEGIN_POLYGON 2 5 3" in text and "OBJECT 0 17.001 59.001 0.0" in text


def test_uv_page_under_the_region_is_refused():
    with pytest.raises(dsf_poly_clip.UvMappedPage):
        dsf_poly_clip.clip_text(DUMP, box(17.0195, 59.0195, 17.0215, 59.0215))


def test_add_object_appends_a_def_and_an_msl_row():
    text, idx = dsf_additions.add_object(DUMP, "objects/o4_generated/deck_x.obj",
                                         17.005, 59.005, 31.25, 58.5)
    lines = text.split("\n")
    assert idx == 1
    assert lines[lines.index("OBJECT_DEF lib/a.obj") + 1] == "OBJECT_DEF objects/o4_generated/deck_x.obj"
    assert "OBJECT_MSL 1 17.005000000 59.005000000 31.2500 58.500000" in lines


def test_add_network_writes_one_def_and_the_level_chain():
    chain = dsf_additions.Chain(50, ((17.0, 59.0, 0), (17.001, 59.0, 1),
                                     (17.002, 59.0, 1), (17.003, 59.0, 0)))
    text = dsf_additions.add_network(DUMP, "lib/g10/roads_EU.net", [chain])
    lines = text.split("\n")
    assert lines.count("NETWORK_DEF lib/g10/roads_EU.net") == 1
    assert lines.index("NETWORK_DEF lib/g10/roads_EU.net") > lines.index("POLYGON_DEF lib/fac/hangar.fac")
    segs = [ln.split() for ln in lines if ln.startswith(("BEGIN_SEGMENT", "END_SEGMENT"))]
    assert len(segs) == 6
    assert segs[0][-1] == "0.000000000" and segs[1][1] == "2" and segs[1][-1] == "1.000000000"
    assert segs[2][3] == "2"                             # the junction is shared
    with pytest.raises(ValueError):
        dsf_additions.add_network(text, "lib/g10/roads.net", [chain])
