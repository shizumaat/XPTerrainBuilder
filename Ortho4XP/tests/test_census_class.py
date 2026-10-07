"""Twins for ``tools/harness/census_class.py`` (``census.py --class``): the
row buckets — standing / ribbon / gap part, inside one part, across a
knife, a breakline — and the floor split of the two grade families."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_harness import (HARNESS, _load, _pavcap_patch, _sloped_rect,  # noqa: E402,F401
                          census_mod, cg)

ROLE = "groundside_pavement"


@pytest.fixture(scope="module")
def cc():
    return _load("harness_twin_census_class", HARNESS / "census_class.py")


def test_the_buckets_read_the_ref_spellings(cc):
    k = cc.row_class
    assert k("mid_edge_step", "pav1", "dsf:objpav3") == "standing | standing"
    assert k("mid_edge_step", "gap:5/s2", "gap:5/s4#1") == "two parts ACROSS A KNIFE"
    assert k("cross_shape", "gap:7/lot", "gap:7/ramp1") == "lot | ramp of one part (breakline)"
    assert k("cross_shape", "gap:0/s4/lot", "gap:0/s4/ramp0") == "lot | ramp of one part (breakline)"
    assert k("mid_edge_step", "gap:1", "gap:5/s0") == "two pieces"
    assert k("terrace_actual_step", "building59#collar", "gap:0/s0/lot") == "part | standing"
    assert k("terrace_actual_step", "gap:0/s21", "small_roads:-3929") == "part | ribbon"
    assert k("road_cross_section", "small_roads:-7", "small_roads:-7") == "ribbon (follower or not)"
    assert k("mid_edge_step", "pav1", "small_roads:-7") == "ribbon | standing"


def test_the_grade_families_split_against_the_floor(cc):
    kw = dict(cap_pct=8.0, distance_m=10.0, floor_m=1.0)
    k = cc.row_class
    assert k("within_shape", "gap:3/s0", "gap:3/s0", magnitude_m=1.5, **kw) \
        == "inside one part — over the cap by <= the floor"
    assert k("within_shape", "gap:3/s0", "gap:3/s0", magnitude_m=2.0, **kw) \
        == "inside one part — over the cap by > the floor"
    # no floor published, a standing pair, a step family: no split
    assert k("within_shape", "gap:3/s0", "gap:3/s0", magnitude_m=2.0,
             cap_pct=8.0, distance_m=10.0) == "inside one part"
    assert k("within_shape", "pav1", "pav1", magnitude_m=2.0, **kw) == "standing | standing"
    assert k("mid_edge_step", "gap:3/s0", "gap:3/s0", magnitude_m=2.0, **kw) == "inside one part"


def test_the_census_carries_the_classes_of_its_own_adjudicated_rows(cc, cg, census_mod, tmp_path):
    """One patch: a part over its cap beyond the floor, a standing lot over
    its cap — the table's counts are the census's own adjudicated rows."""
    osm = _pavcap_patch(tmp_path, name="cls", sidecar={
        "late_stage": {"floor_m": 1.0, "followers": []}}, rings=[
        (ROLE, _sloped_rect(0.20), "gap:3/s0/lot"),
        (ROLE, _sloped_rect(0.12, x0=40.0), "dsf:pol10")])
    rep = census_mod.census_one(osm, cg, want_class=True)
    table = rep["row_classes"]
    assert rep["row_class_floor_m"] == 1.0
    ws = {b["class"]: b for b in table["within_shape"]}
    assert set(ws) == {"inside one part — over the cap by > the floor", "standing | standing"}
    assert sum(b["n"] for fam in table.values() for b in fam) == rep["adjudication"]["adjudicated_total"]
    worst = ws["inside one part — over the cap by > the floor"]["worst"]
    assert worst["refs"] == ["gap:3/s0/lot", "gap:3/s0/lot"] and worst["side"] == "groundside"
    lines = cc.format_class_tables([rep, rep])
    assert any("within_shape" in ln and "delta +0" in ln for ln in lines)
    assert "row_classes" not in census_mod.census_one(osm, cg)
