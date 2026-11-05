"""Twin for ``tools/drawn_check.py`` (#1903): the drawn-vs-cut gate.

A synthetic world in DSFTool text: a flat drawn tile mesh at 100 m (plus a
NON-physical overlay patch at 500 m that X-Plane does not collide with and
the gate must ignore), a pack dump with one ``OBJECT_MSL`` row -- whose
elevation comes BEFORE the heading in DSFTool text -- and one ``OBJECT``
row, a 4-vertex OBJ hanging 5 m below its zero, and a patch whose tunnel
ramp floors at 95 m.  The gate must place the MSL row at its elevation,
the OBJECT row on the drawn mesh, and read the bars from those."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import drawn_check as DC  # noqa: E402
from auto_patch_v2.airport import dsf as dsf_text  # noqa: E402

LON, LAT = 10.5, 45.5
MESH_TEXT = """\
TERRAIN_DEF terrain_Water
BEGIN_PATCH 0 0.0 -1.0 1 5
BEGIN_PRIMITIVE 0
PATCH_VERTEX 10.49 45.49 100.0 0 0
PATCH_VERTEX 10.51 45.49 100.0 0 0
PATCH_VERTEX 10.51 45.51 100.0 0 0
END_PRIMITIVE
BEGIN_PRIMITIVE 1
PATCH_VERTEX 10.49 45.49 100.0 0 0
PATCH_VERTEX 10.51 45.51 100.0 0 0
PATCH_VERTEX 10.49 45.51 100.0 0 0
END_PRIMITIVE
END_PATCH
BEGIN_PATCH 0 0.0 -1.0 2 5
BEGIN_PRIMITIVE 0
PATCH_VERTEX 10.49 45.49 500.0 0 0
PATCH_VERTEX 10.51 45.49 500.0 0 0
PATCH_VERTEX 10.51 45.51 500.0 0 0
END_PRIMITIVE
END_PATCH
"""
OBJ = "I\n800\nOBJ\n\nPOINT_COUNTS 4 0 0 0\n" + "".join(
    f"VT {x} {y} {z} 0 1 0 0 0\n"
    for x, y, z in ((-2, -5, -2), (2, -5, -2), (2, 0, 2), (-2, 0, 2)))


def _world(tmp_path, msl_elev, kept_reason=None, deck=False):
    root = tmp_path / "pack"
    (root / "objects").mkdir(parents=True)
    (root / "objects" / "portal.obj").write_text(OBJ, encoding="utf-8", newline="\n")
    (root / "objects" / "other.obj").write_text(OBJ, encoding="utf-8", newline="\n")
    dump = tmp_path / "pack.txt"
    dump.write_text(
        "OBJECT_DEF objects/portal.obj\nOBJECT_DEF objects/other.obj\n"
        f"OBJECT_MSL 0 {LON} {LAT} {msl_elev} 90.0\n"
        f"OBJECT 1 {LON + 0.0001} {LAT} 0.0\n", encoding="utf-8", newline="\n")
    patch = tmp_path / "X_auto.patch.osm"
    nodes = [(-1, LAT, LON, 95.0), (-2, LAT + 0.0001, LON, 96.0),
             (-3, LAT + 0.0002, LON, 98.0)]
    patch.write_text(
        "<osm>" + "".join(
            f"<node id='{i}' lat='{la}' lon='{lo}'><tag k='alt_abs' v='{z}'/></node>"
            for i, la, lo, z in nodes)
        + "<way id='-9'>" + "".join(f"<nd ref='{i}'/>" for i, *_ in nodes)
        + "<tag k='role' v='tunnel_ramp'/></way></osm>", encoding="utf-8", newline="\n")
    sidecar = {"portal_cuts": [{"id": "tunnel:-9@0", "portal": "dsf:obj0"}],
               "tunnel_mouth_depths": [{"id": "tunnel:-9@0",
                                        "mouth_ll": [LAT, LON], "depth_m": 5.0}]}
    if deck:
        sidecar["deck_anchors"] = [{"object": "dsf:obj0", "end": "A"}]
    plan = {"kept": [{"index": 0, "resource": "objects/portal.obj",
                      "reason": kept_reason}]} if kept_reason else {}
    written = dsf_text.read_dump(str(dump), accept_polygon=lambda _p: False)
    mesh = DC.drawn_mesh([iter(MESH_TEXT.splitlines(True))],
                         (10.49, 45.49, 10.51, 45.51))
    claims = DC.read_claims(sidecar, "+45+010", {"+45+010": plan},
                            {"+45+010": written})
    drawn = DC.Drawn(written.placements, str(root), mesh)
    sites = DC.read_sites(str(patch), sidecar, 15.0)
    return [DC.check_site(s, drawn, claims, 15.0, 0.3) for s in sites], drawn


def test_object_msl_reads_elevation_before_heading(tmp_path):
    _rows, drawn = _world(tmp_path, 100.0)
    msl, obj = drawn.rows
    assert (msl.kind, msl.elevation, msl.heading_deg) == ("OBJECT_MSL", 100.0, 90.0)
    assert (obj.kind, obj.heading_deg) == ("OBJECT", 0.0)
    # a swapped read would seat the row at 90 m: the bottom would read 85
    assert drawn.vertices(0)[2].min() == pytest.approx(95.0)


def test_drawn_mesh_ignores_non_physical_patches(tmp_path):
    _rows, drawn = _world(tmp_path, 100.0)
    assert drawn.mesh.elevation_at(LAT, LON) == pytest.approx(100.0)
    # OBJECT row: zero = drawn mesh (100), bottom = 100 - 5
    assert drawn.vertices(1)[2].min() == pytest.approx(95.0)


def test_seated_cut_passes(tmp_path):
    rows, _ = _world(tmp_path, 100.0)          # MSL 100 - 5 = floor 95
    ramp, mouth = rows
    assert ramp["site"] == "tunnel_ramp -9" and ramp["floor"] == 95.0
    assert ramp["relief"] == 3.0 and ramp["role"] == "CUT"
    assert ramp["delta"] == pytest.approx(0.0) and ramp["verdict"] == "PASS"
    assert mouth["floor_from"] == "patch" and mouth["verdict"] == "PASS"


def test_object_left_proud_of_the_cut_fails(tmp_path):
    rows, _ = _world(tmp_path, 104.5,
                     kept_reason="split undone: a body falls off the tile")
    ramp = rows[0]
    assert ramp["delta"] == pytest.approx(4.5) and ramp["verdict"] == "FAIL"
    assert any("split undone" in f for f in ramp["fails"])
    assert any("bottom-floor" in f for f in ramp["fails"])


def test_deck_claim_bars_clearance_not_floor(tmp_path):
    rows, _ = _world(tmp_path, 106.0, deck=True)
    assert rows[0]["role"] == "DECK" and rows[0]["verdict"] == "PASS"
    rows, _ = _world(tmp_path / "b", 99.0, deck=True)   # deck bottom 94 < 95
    assert rows[0]["verdict"] == "FAIL"


def test_against_flags_moved_sites():
    base = [{"site": "a", "verdict": "PASS", "delta": -0.07},
            {"site": "b", "verdict": "PASS", "delta": 0.0}]
    now = [{"site": "a", "verdict": "PASS", "delta": -0.06},
           {"site": "b", "verdict": "FAIL", "delta": 4.5}]
    assert DC.compare(now, base) == ["b: PASS 0.0 -> FAIL 4.5"]
