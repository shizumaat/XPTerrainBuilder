"""Twin for ``tools/harness/drawn_gate.py`` (#1903): the harness's drawn gate.

A synthetic tile: a flat drawn mesh at 100 m in DSFTool text (streamed in
place of DSFTool), a patch whose nodes the mesh carries or does not, and a
harness ``<tag>.result.json`` naming the build dir.  The gate must read the
drawn mesh, hold pavement nodes to the pavement bar and other nodes to the
ground bar, fail a stale or hidden mesh, and never call a build PASS whose
objects it could not read (no placement plan / no --pack-copy)."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools" / "harness"))
sys.path.insert(0, str(HERE.parent / "tools"))

import drawn_check as DC  # noqa: E402
import drawn_gate as DG  # noqa: E402

TILE = "+45+010"
MESH_TEXT = """\
BEGIN_PATCH 0 0.0 -1.0 1 5
BEGIN_PRIMITIVE 0
PATCH_VERTEX 10.49 45.49 100.0 0 0
PATCH_VERTEX 10.51 45.49 100.0 0 0
PATCH_VERTEX 10.51 45.51 100.0 0 0
END_PRIMITIVE
BEGIN_PRIMITIVE 0
PATCH_VERTEX 10.49 45.49 100.0 0 0
PATCH_VERTEX 10.51 45.51 100.0 0 0
PATCH_VERTEX 10.49 45.51 100.0 0 0
END_PRIMITIVE
END_PATCH
"""


def _patch(path, nodes, ways):
    """nodes: [(id, lat, lon, alt)]; ways: [(role, [ids])]."""
    path.write_text(
        "<osm>" + "".join(
            f"<node id='{i}' lat='{la}' lon='{lo}'><tag k='alt_abs' v='{z}'/></node>"
            for i, la, lo, z in nodes)
        + "".join(f"<way id='-{9 + k}'>" + "".join(f"<nd ref='{i}'/>" for i in ids)
                  + f"<tag k='role' v='{role}'/></way>"
                  for k, (role, ids) in enumerate(ways))
        + "</osm>", encoding="utf-8", newline="\n")
    return path


def _flat(_lon, _lat):
    return 100.0


def test_patch_nodes_roles(tmp_path):
    p = _patch(tmp_path / "X_auto.patch.osm",
               [(-1, 45.5, 10.5, 100.0), (-2, 45.5001, 10.5, 101.0)],
               [("runway", [-1]), ("graded_strip", [-1])])
    got = {n[0]: n[4] for n in DG.patch_nodes(str(p))}
    assert got == {"-1": ("graded_strip", "runway"), "-2": ("(free)",)}


def test_bars_by_role_and_tile_and_clusters():
    nodes = [("-1", 10.5, 45.5, 100.2, ("runway",)),          # pavement 0.2 > 0.05
             ("-2", 10.50001, 45.5, 100.3, ("graded_strip",)),  # ground 0.3 < 0.5
             ("-3", 10.50002, 45.5, 99.0, ("graded_strip",)),   # ground 1.0, 1.6 m away
             ("-4", 10.6, 45.6, 90.0, ("graded_strip",)),       # ground 10 m, far
             ("-5", 11.5, 45.5, 0.0, ("runway",))]              # other tile: skipped
    rep = DG.mesh_follows_patch(nodes, _flat, (45, 10), {"runway"})
    assert rep["nodes"] == 4 and rep["over_bar"] == 3 and rep["verdict"] == "FAIL"
    sites = rep["sites"]
    assert [s["node"] for s in sites] == ["-4", "-3"]           # worst first, -1 folded
    assert sites[1]["nodes"] == 2 and sites[1]["roles"] == ["graded_strip", "runway"]
    assert rep["by_role"]["pavement runway"]["over_bar"] == 1
    assert rep["by_role"]["ground graded_strip"]["over_bar"] == 2


def test_nan_is_off_mesh_not_a_pass():
    rep = DG.mesh_follows_patch([("-1", 10.5, 45.5, 100.0, ("runway",))],
                                lambda x, y: math.nan, (45, 10), {"runway"})
    assert rep["off_mesh"] == 1 and rep["verdict"] == "NOT MEASURED"


def test_mesh_layer_stale_hidden(tmp_path):
    dsf, patch = tmp_path / "t.dsf", tmp_path / "p.osm"
    dsf.write_text("x", encoding="utf-8", newline="\n")
    patch.write_text("x", encoding="utf-8", newline="\n")
    os.utime(dsf, (1000, 1000))
    os.utime(patch, (2000, 2000))
    rep = DG.mesh_layer([str(dsf)], str(patch), ["Some Airport Mesh"])
    assert rep["verdict"] == "FAIL" and len(rep["fails"]) == 2
    os.utime(dsf, (3000, 3000))
    assert DG.mesh_layer([str(dsf)], str(patch), [])["verdict"] == "PASS"
    assert DG.mesh_layer([], str(patch), [])["verdict"] == "NOT MEASURED"


def _tag_world(tmp_path, monkeypatch, nodes, ways, hidden=()):
    build = tmp_path / "tile"
    dsf = build / "Earth nav data" / "+40+010" / f"{TILE}.dsf"
    dsf.parent.mkdir(parents=True)
    patch_dir = tmp_path / "Patches" / "+40+010" / TILE
    patch_dir.mkdir(parents=True)
    _patch(patch_dir / "XXXX_auto.patch.osm", nodes, ways)
    (patch_dir / "XXXX_auto.patch.osm.axes.json").write_text("{}", encoding="utf-8", newline="\n")
    dsf.write_text("dsf", encoding="utf-8", newline="\n")
    os.utime(dsf, (4e9, 4e9))                  # newer than the patch
    (tmp_path / "T.result.json").write_text(json.dumps(
        {"build_dir": str(build), "patch_dir": str(patch_dir)}),
        encoding="utf-8", newline="\n")
    monkeypatch.setattr(DC, "stream_dsf", lambda _p: iter(MESH_TEXT.splitlines(True)))
    import O4_Mesh_Order
    monkeypatch.setattr(O4_Mesh_Order, "tile_mesh_order", lambda *a, **k: {
        "checked": True, "hidden_by": list(hidden), "hides": []})
    return argparse.Namespace(icao="XXXX", tag="T", out=str(tmp_path), tile=None,
                              patches=None, custom_scenery=str(tmp_path / "cs"))


def test_gate_no_objects_is_incomplete_never_pass(tmp_path, monkeypatch):
    args = _tag_world(tmp_path, monkeypatch, [(-1, 45.5, 10.5, 100.0)],
                      [("runway", [-1])])
    rep = DG.gate(args)
    assert rep["mesh"]["verdict"] == "PASS"
    assert rep["patch_to_drawn"]["verdict"] == "PASS"
    assert rep["objects"]["verdict"] == "NOT MEASURED"
    assert rep["verdict"] == "INCOMPLETE"


def test_gate_fails_on_an_undrawn_patch_node(tmp_path, monkeypatch):
    args = _tag_world(tmp_path, monkeypatch, [(-1, 45.5, 10.5, 100.1)],
                      [("runway", [-1])])
    rep = DG.gate(args)
    assert rep["patch_to_drawn"]["over_bar"] == 1 and rep["verdict"] == "FAIL"
    assert "1 of 1 nodes over the bars" in DG.summary_line(rep)


def test_gate_fails_when_hidden(tmp_path, monkeypatch):
    args = _tag_world(tmp_path, monkeypatch, [(-1, 45.5, 10.5, 100.0)],
                      [("runway", [-1])], hidden=["Their Mesh"])
    assert DG.gate(args)["verdict"] == "FAIL"


def test_after_build_patch_only_never_raises(tmp_path):
    (tmp_path / "T.result.json").write_text(json.dumps({"patch": "x.osm"}),
                                             encoding="utf-8", newline="\n")
    rec = DG.after_build("XXXX", "T", tmp_path, custom_scenery=str(tmp_path))
    assert rec["verdict"] == "INCOMPLETE" and "patch-only" in rec["line"]
    assert json.loads((tmp_path / "T.drawn.json").read_text(encoding="utf-8"))["verdict"] == "INCOMPLETE"


@pytest.mark.parametrize("tag,copy,root,want", [
    (None, None, "/x/Custom Scenery/P", True),          # owner products
    ("T", None, "/x/Custom Scenery/P", False),          # lane build, no copy
    ("T", "/c", "/c/P", True),                          # lane build, its copy
    ("T", "/c", "/x/Custom Scenery/P", False)])         # copy not written
def test_pack_is_build_product(tag, copy, root, want):
    ns = argparse.Namespace(tag=tag, pack_copy=copy, plan=None)
    assert DC.pack_is_build_product(ns, root) is want


def test_drawn_tile_dsfs_reads_the_load_order(monkeypatch):
    import O4_Mesh_Order
    seen = []
    monkeypatch.setattr(O4_Mesh_Order, "drawn_mesh_dsf",
                        lambda cs, lat, lon: seen.append((cs, lat, lon)) or
                        (f"{cs}/World/{lat}{lon}.dsf" if lat == 45 else None))
    assert DC.drawn_tile_dsfs("/cs", {"+45+010": {}, "+46+010": {}}) == \
        ["/cs/World/4510.dsf"]
    assert seen == [("/cs", 45, 10), ("/cs", 46, 10)]


def test_a_site_off_the_drawn_mesh_carries_no_bar():
    """A mouth on the neighbour tile reads nan on this tile's mesh: no FAIL
    (LOWS +47+012 read its east mouth on +47+013 as 'bottom-floor +nan')."""
    class _Off:
        mesh = DC.drawn_mesh([iter(MESH_TEXT.splitlines(True))],
                             (10.49, 45.49, 10.51, 45.51))

        @staticmethod
        def bottoms_near(*_a, **_k):
            return {}
    site = DC.Site("mouth m", 11.5, 45.5, math.nan, math.nan, "mouth")
    row = DC.check_site(site, _Off(), [], 15.0, 0.3)
    assert row["verdict"] == "-" and row["role"] == "OFF MESH" and not row["fails"]


def _rep(p2d_sites, obj_sites):
    return {"mesh": {"verdict": "PASS"}, "incomplete": [],
            "patch_to_drawn": {"verdict": "FAIL" if p2d_sites else "PASS",
                               "sites": p2d_sites, "over_bar": len(p2d_sites)},
            "objects": {"verdict": "FAIL", "sites": obj_sites, "failed": 1, "claimed": 2}}


SITE_A = {"node": "-1", "lat": 45.5, "lon": 10.5, "delta": 0.4, "nodes": 1}
SITE_FAR = {"node": "-2", "lat": 45.6, "lon": 10.6, "delta": 3.0, "nodes": 1}
OBJ_FAR = {"site": "tunnel_ramp -7", "lat": 45.6, "lon": 10.6, "verdict": "FAIL",
           "delta": 2.0, "fails": ["bottom-floor"]}
OBJ_NEAR = {"site": "tunnel_ramp -8", "lat": 45.5, "lon": 10.5, "verdict": "PASS",
            "delta": 0.1, "fails": []}


def test_judge_narrows_to_the_round_site():
    rep = DG.judge(_rep([SITE_FAR], [OBJ_FAR, OBJ_NEAR]), [("mouth", 45.5, 10.5, 150.0)])
    assert rep["verdict"] == "PASS"
    assert rep["patch_to_drawn"]["elsewhere"] == 1 and rep["objects"]["elsewhere"] == 1
    rep = DG.judge(_rep([SITE_A, SITE_FAR], [OBJ_FAR, OBJ_NEAR]),
                   [("mouth", 45.5, 10.5, 150.0)])
    assert rep["verdict"] == "FAIL" and rep["patch_to_drawn"]["over_bar"] == 1


def test_judge_against_the_control():
    base = _rep([dict(SITE_FAR, delta=2.99)], [dict(OBJ_FAR, delta=1.99), OBJ_NEAR])
    rep = DG.judge(_rep([SITE_FAR], [OBJ_FAR, OBJ_NEAR]), [("far", 45.6, 10.6, 50.0)],
                   base)
    assert rep["moved"] == [] and rep["verdict"] == "FAIL"      # failing, not moved
    rep = DG.judge(_rep([SITE_FAR, SITE_A], [OBJ_FAR, dict(OBJ_NEAR, verdict="FAIL")]),
                   (), base)
    assert len(rep["moved"]) == 2                                # new node, new FAIL
    assert DG.parse_site("m=45.5,10.5") == ("m", 45.5, 10.5, DG.SITE_RADIUS_M)


def test_no_claim_read_at_a_cut_site_is_not_a_pass(monkeypatch):
    """LOWS +47+013 closing build: its two mouths are claimed by +47+012's
    entrance object, which a one-tile build never writes -- 0 of 0 claimed
    sites is NOT MEASURED, never PASS."""
    monkeypatch.setattr(DC, "run", lambda ns: {
        "pack_root": "/c/P", "pack_is_build_product": True,
        "claims": [{"kind": "portal", "claim_id": "tunnel:-1@0", "resource": "",
                    "fate": "whole"}],
        "sites": [{"site": "mouth m", "role": "UNCLAIMED", "verdict": "-"}]})
    ns = argparse.Namespace(icao="XXXX", tag="T", out="/tmp", tile=None, patches=None)
    rep = DG._objects(ns, None, [])
    assert rep["verdict"] == "NOT MEASURED" and "1 claim(s)" in rep["why"]


def test_judging_a_site_keeps_an_unmeasured_layer_unmeasured():
    rep = _rep([], [OBJ_NEAR])
    rep["objects"].update(verdict="NOT MEASURED", why="no claimed object")
    rep = DG.judge(rep, [("mouth", 45.5, 10.5, 150.0)])
    assert rep["objects"]["verdict"] == "NOT MEASURED" and rep["verdict"] == "INCOMPLETE"


def test_a_near_vertical_step_is_read_with_horizontal_slack():
    """LOWS east: a graded_strip node at 469.20 m 0.49 m from one at 435.11 m;
    the drawn mesh carries it a few cm off, which a fixed-(x, y) read turns
    into metres.  The mesh passing through the node's height within
    XY_TOL_M is carried; 0.5 m away is not."""
    kx = DC.M_PER_DEG * math.cos(math.radians(45.5))

    def cliff(lon, _lat):                   # 70 m per metre east of 10.5
        return 100.0 + 70.0 * (lon - 10.5) * kx
    near = 100.0 + 70.0 * 0.1                # the height 0.1 m east
    far = 100.0 + 70.0 * 0.5
    nodes = [("-1", 10.5, 45.5, near, ("graded_strip",)),
             ("-2", 10.5, 45.5, far, ("graded_strip",))]
    rep = DG.mesh_follows_patch(nodes, cliff, (45, 10), set())
    assert rep["over_bar"] == 1 and rep["sites"][0]["node"] == "-2"
    assert rep["sites"][0]["delta"] == pytest.approx(-(70.0 * (0.5 - DG.XY_TOL_M)), abs=0.05)
