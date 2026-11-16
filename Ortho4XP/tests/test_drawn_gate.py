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
    rec = json.loads((tmp_path / "T.drawn.json").read_text(encoding="utf-8"))
    assert rec["verdict"] == "INCOMPLETE"


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


def _trench(wid, lat, delta, verdict="FAIL", row=7):
    return {"site": f"tunnel_trench {wid}", "lat": lat, "lon": 10.5, "verdict": verdict,
            "delta": delta, "fails": ["bottom-floor"] if verdict == "FAIL" else [],
            "objects": [{"row": row}]}


def test_against_joins_object_sites_by_place_not_way_id():
    """#2099 P5b: a re-ringed way shifts every later way id by 0/+1/+2; the
    same sites read under new names are not MOVED.  A real +0.2 m at one
    place is; a FAIL at a new place is."""
    lats = [45.5 + k * 1e-3 for k in range(4)]
    base = _rep([], [_trench(-100 - k, la, 1.0 + k) for k, la in enumerate(lats)])
    shifted = _rep([], [_trench(-102 - k, la, 1.0 + k) for k, la in enumerate(lats)])
    assert DG.judge(shifted, (), base)["moved"] == []
    worse = _rep([], [_trench(-102 - k, la, 1.0 + k + (0.2 if k == 1 else 0.0))
                      for k, la in enumerate(lats)])
    moved = DG.judge(worse, (), base)["moved"]
    assert len(moved) == 1 and "control tunnel_trench -101" in moved[0]
    fresh = _rep([], [_trench(-102 - k, la, 1.0 + k) for k, la in enumerate(lats)]
                 + [_trench(-200, 45.6, 0.5, row=9)])
    moved = DG.judge(fresh, (), base)["moved"]
    assert len(moved) == 1 and "new -> FAIL" in moved[0]


def test_against_a_fail_one_node_over_on_the_same_row_is_held():
    base = _rep([], [_trench(-100, 45.5, 1.0)])
    nudged = _rep([], [_trench(-101, 45.5 + 3e-5, 1.02)])      # ~3 m over, same row
    assert DG.judge(nudged, (), base)["moved"] == []
    other_row = _rep([], [_trench(-101, 45.5 + 3e-5, 1.02, row=8)])
    assert len(DG.judge(other_row, (), base)["moved"]) == 1


def test_against_joins_patch_sites_by_place_not_node_id():
    base = _rep([SITE_A], [])
    renamed = _rep([dict(SITE_A, node="-77")], [])
    assert DG.judge(renamed, (), base)["moved"] == []
    worse = _rep([dict(SITE_A, node="-77", delta=0.6)], [])
    moved = DG.judge(worse, (), base)["moved"]
    assert len(moved) == 1 and "control node -1" in moved[0]


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


def test_the_road_layer_fails_a_step_along_a_mapped_road(monkeypatch):
    """#2072 step 5: a mapped road sampled on the drawn mesh each metre
    inside a site's radius; a step over ``--road-step`` between two
    consecutive samples FAILs the site, a smooth road PASSes, a site with
    no road is NOT MEASURED, and ``--against`` flags a worse step."""
    import drawn_roads as DR
    lat0, lon0 = 45.5, 10.5
    kx = DR._M_PER_DEG * math.cos(math.radians(lat0))
    road = [(lat0 - 100.0 / DR._M_PER_DEG, lon0), (lat0 + 100.0 / DR._M_PER_DEG, lon0)]
    monkeypatch.setattr(DR, "road_lines", lambda root, la, lo, r, b=None: [] if la != lat0 else
                        [(-1, "primary", road)])

    def stepped(lon, lat):                  # a 2 m lip 20 m north of the site
        return 100.0 + (2.0 if (lat - lat0) * DR._M_PER_DEG > 20.0 else 0.0)

    def smooth(lon, lat):                   # a 5 % ramp
        return 100.0 + 0.05 * (lat - lat0) * DR._M_PER_DEG
    rep = DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere", 0.5)
    row = rep["sites"][0]
    assert rep["verdict"] == "FAIL" and row["max_step_m"] == pytest.approx(2.0)
    assert abs((row["lat"] - lat0) * DR._M_PER_DEG - 20.0) <= 1.5 and row["roads"] == 1
    assert DR.road_layer([("s", lat0, lon0, 50.0)], smooth, "/nowhere")["verdict"] == "PASS"
    assert DR.road_layer([("x", lat0 + 1.0, lon0, 50.0)], smooth,
                         "/nowhere")["verdict"] == "NOT MEASURED"
    # the clip: a road wholly outside the radius is no run
    assert DR._clip_runs([(lat0, lon0 + 500.0 / kx), (lat0, lon0 + 600.0 / kx)],
                         lat0, lon0, 50.0, 1.0) == []
    # a mapped bridge over the road at the lip: the mesh there is the
    # bridge's ground, never the road under it -- not read
    over = [(lat0 + 20.0 / DR._M_PER_DEG, lon0 - 30.0 / kx),
            (lat0 + 20.0 / DR._M_PER_DEG, lon0 + 30.0 / kx)]

    def with_bridge(root, la, lo, r, b=None):
        if b is not None:
            b.append((3.5, over))
        return [(-1, "primary", road)]
    monkeypatch.setattr(DR, "road_lines", with_bridge)
    assert DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere")["verdict"] == "PASS"
    rep2 = {"mesh": {"verdict": "PASS"}, "patch_to_drawn": {"verdict": "PASS", "sites": []},
            "objects": {"verdict": "PASS", "sites": []}, "incomplete": [], "roads": rep}
    base = {"roads": {"sites": [dict(row, max_step_m=0.9)]}}
    judged = DG.judge(rep2, (), base)
    assert judged["verdict"] == "FAIL" and judged["moved"]


def test_a_step_on_a_claimed_mouth_of_its_own_way_is_its_face(monkeypatch):
    """#1689 A7: the tunnel way's own step pair at its claimed mouth is the
    mouth's face, reported, never judged; another road's step there and a
    step away from the mouth are judged."""
    import drawn_roads as DR
    lat0, lon0 = 45.5, 10.5
    road = [(lat0 - 100.0 / DR._M_PER_DEG, lon0), (lat0 + 100.0 / DR._M_PER_DEG, lon0)]
    mouth_lat = lat0 + 20.5 / DR._M_PER_DEG

    def stepped(lon, lat):                  # the cut face 20 m north of the site
        return 100.0 + (5.0 if (lat - lat0) * DR._M_PER_DEG > 20.0 else 0.0)
    side = {"portal_cuts": [{"id": "tunnel:-7+-8@1", "portal": "dsf:obj1"}],
            "tunnel_mouth_depths": [{"id": "tunnel:-7+-8@1", "mouth_ll": [mouth_lat, lon0 + 3e-5],
                                     "depth_m": 6.0},
                                    {"id": "tunnel:-5@0", "mouth_ll": [lat0, lon0],
                                     "depth_m": 6.0}]}
    mouths = DR.claimed_mouths(side)
    assert mouths == [(frozenset({-7, -8}), mouth_lat, lon0 + 3e-5)]
    monkeypatch.setattr(DR, "road_lines", lambda root, la, lo, r, b=None: [(-7, "primary", road)])
    rep = DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere", 0.5, mouths=mouths)
    row = rep["sites"][0]
    assert rep["verdict"] == "PASS" and row["mouth_faces"][0]["step_m"] == pytest.approx(5.0)
    monkeypatch.setattr(DR, "road_lines", lambda root, la, lo, r, b=None: [(-6, "primary", road)])
    assert DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere", 0.5,
                         mouths=mouths)["verdict"] == "FAIL"
    far = [(frozenset({-6}), lat0 + 40.0 / DR._M_PER_DEG, lon0)]
    assert DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere", 0.5,
                         mouths=far)["verdict"] == "FAIL"


def test_a_feed_way_id_names_its_mouth_by_its_number(monkeypatch):
    """#1689 R3: the road feeds name a way ``+LL+LLL:<number>``; the claimed
    mouth's tunnel id names the bare number -- the face is still its own."""
    import drawn_roads as DR
    lat0, lon0 = 45.5, 10.5
    road = [(lat0 - 100.0 / DR._M_PER_DEG, lon0), (lat0 + 100.0 / DR._M_PER_DEG, lon0)]
    mouth_lat = lat0 + 20.5 / DR._M_PER_DEG

    def stepped(lon, lat):
        return 100.0 + (5.0 if (lat - lat0) * DR._M_PER_DEG > 20.0 else 0.0)
    mouths = [(frozenset({-7}), mouth_lat, lon0)]
    monkeypatch.setattr(DR, "road_lines",
                        lambda root, la, lo, r, b=None: [("+45+010:-7", "primary", road)])
    assert DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere", 0.5,
                         mouths=mouths)["verdict"] == "PASS"
    monkeypatch.setattr(DR, "road_lines",
                        lambda root, la, lo, r, b=None: [("+45+010:-6", "primary", road)])
    assert DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere", 0.5,
                         mouths=mouths)["verdict"] == "FAIL"


def test_a_road_ending_at_a_mouth_and_a_tunnel_at_a_floor_ring_are_faces(monkeypatch):
    """T8 (#2099 F2 P3): a road whose END stands at a claimed mouth is that
    mouth's road -- its pair at the mouth line is the face, whatever its way;
    a TUNNEL way's pair straddling the ring of a ground-owning object floor
    is that floor's bore face; an untagged road crossing the ring is judged."""
    import drawn_roads as DR
    lat0, lon0 = 45.5, 10.5
    kx = DR._M_PER_DEG * math.cos(math.radians(lat0))
    mouth_lat = lat0 + 20.5 / DR._M_PER_DEG
    ends_at = [(lat0 - 100.0 / DR._M_PER_DEG, lon0), (mouth_lat + 1.0 / DR._M_PER_DEG, lon0)]

    def stepped(lon, lat):                  # the cut face 20 m north of the site
        return 100.0 + (5.0 if (lat - lat0) * DR._M_PER_DEG > 20.0 else 0.0)
    mouths = [(frozenset({-7}), mouth_lat, lon0)]
    monkeypatch.setattr(DR, "road_lines",
                        lambda root, la, lo, r, b=None: [(-9, "service", ends_at, False)])
    rep = DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere", 0.5, mouths=mouths)
    assert rep["verdict"] == "PASS" and rep["sites"][0]["mouth_faces"]
    # the floor ring: a box from 20.2 m north to 60 m north, 10 m wide
    d = 1.0 / DR._M_PER_DEG
    ring = [(lat0 + 20.2 * d, lon0 - 5.0 / kx), (lat0 + 20.2 * d, lon0 + 5.0 / kx),
            (lat0 + 60.0 * d, lon0 + 5.0 / kx), (lat0 + 60.0 * d, lon0 - 5.0 / kx)]
    side = {"object_floors": [{"owns_ground": True, "outline_ll": [ring]},
                              {"owns_ground": False, "outline_ll": [ring]}]}
    floors = DR.floor_rings(side)
    assert len(floors) == 1
    through = [(lat0 - 100.0 * d, lon0), (lat0 + 100.0 * d, lon0)]
    monkeypatch.setattr(DR, "road_lines",
                        lambda root, la, lo, r, b=None: [(-3, "primary", through, True)])
    assert DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere", 0.5,
                         floors=floors)["verdict"] == "PASS"
    monkeypatch.setattr(DR, "road_lines",
                        lambda root, la, lo, r, b=None: [(-3, "primary", through, False)])
    assert DR.road_layer([("s", lat0, lon0, 50.0)], stepped, "/nowhere", 0.5,
                         floors=floors)["verdict"] == "FAIL"
    # a tunnel way ENDING just short of the ring (0.3 m): its end pair is the face
    short = [(lat0 - 100.0 * d, lon0), (lat0 + 19.9 * d, lon0)]

    def cut(lon, lat):                      # the cut from 19 m north
        return 100.0 + (5.0 if (lat - lat0) * DR._M_PER_DEG > 19.0 else 0.0)
    monkeypatch.setattr(DR, "road_lines",
                        lambda root, la, lo, r, b=None: [(-3, "primary", short, True)])
    assert DR.road_layer([("s", lat0, lon0, 50.0)], cut, "/nowhere", 0.5,
                         floors=floors)["verdict"] == "PASS"
    monkeypatch.setattr(DR, "road_lines",
                        lambda root, la, lo, r, b=None: [(-3, "primary", short, False)])
    assert DR.road_layer([("s", lat0, lon0, 50.0)], cut, "/nowhere", 0.5,
                         floors=floors)["verdict"] == "FAIL"
