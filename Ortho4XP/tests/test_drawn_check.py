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


def _world(tmp_path, msl_elev, kept_reason=None, deck=False, floor_clearance=None):
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
    if floor_clearance is not None:
        sidecar["portal_cuts"] = []
        sidecar["object_floors"] = [{"id": "object_floor:portal.obj@0", "objects": ["dsf:obj0"],
                                     "clearance_m": floor_clearance}]
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


def _split(tmp_path, msl_elev):
    _rows, drawn = _world(tmp_path, msl_elev)
    rec = {"kind": "split_level", "floor_ref": "basin_floor:0",
           "resources": ["objects/portal.obj"], "anchor_longitude_latitude": [LON, LAT],
           "plate_y_m": -5.0, "floor_below_rim_m": 5.0, "floor_m": 95.0,
           # the open side 5 m east of the anchor, north-south
           "open_sides_ll": [[[LAT - 0.00005, LON + 0.00005], [LAT + 0.00005, LON + 0.00005]]]}
    return DC.check_split(rec, drawn, 0.3)


def test_split_level_lower_floor_on_the_floor_upper_at_the_ground(tmp_path):
    row = _split(tmp_path, 100.0)       # zero 100: lower floor 95, upper 100 = mesh
    assert row["upper_floor"] == pytest.approx(100.0)
    assert row["open_ground_median"] == pytest.approx(100.0)
    # the drawn floor is the flat 100 m mesh: the lower floor 5 m under it fails
    assert any("lower floor - drawn floor" in f for f in row["fails"])


def test_split_level_upper_floor_over_the_ground_is_a_gap(tmp_path):
    row = _split(tmp_path, 104.0)
    assert any("gap to the terrain" in f for f in row["fails"])


def test_an_object_floor_stands_its_clearance_over_the_cut(tmp_path):
    """RULINGS 2026-11-06d (4) (#1921 / #1936): an object floor's cut stands
    ``clearance_m`` beneath the floor, so the floor drawn 0.3 m over the cut
    PASSES and one ON the cut (hidden, z-fighting) FAILS."""
    rows, _ = _world(tmp_path, 100.3, floor_clearance=0.3)   # bottom 95.3 over floor 95
    assert rows[0]["role"] == "CUT" and rows[0]["verdict"] == "PASS"
    rows, _ = _world(tmp_path / "b", 99.65, floor_clearance=0.3)  # bottom 94.65: covered
    assert rows[0]["verdict"] == "FAIL"


def test_graded_facade_sites_judge_every_span_of_the_run():
    """#2042: ``drawn_facade`` stands a graded facade flat on the drawn
    ground at its first wall's centre and fails each 500 m span where a
    foot hangs over the ground; a lowered copy (feet moved down) passes."""
    import types

    import drawn_facade as DF
    from auto_patch_v2.airport import facade_seat as FS
    text = ("A\n1000\nFACADE\nRING 0\nGRADED\nFLOOR f\nSEGMENT 0\n"
            "MESH 0 5000 2 3 3\nVERTEX\t-5.0 -0.2 0 0 1 0 0 0\n"
            "VERTEX\t0.0 2.0 0 0 1 0 0 0\nVERTEX\t5.0 -0.2 0 0 1 0 0 0\n"
            "WALL 0 10000 0 0 f\nSPELLING 0\n")

    class Mesh:                       # land 2 m east of lon 0.00008, water west
        def elevation_at_or_none(self, lat, lon):
            return 2.0 if lon > 0.00008 else 0.0

        def sample_many(self, lats, lons):
            return [types.SimpleNamespace(elevation_metres=self.elevation_at_or_none(a, o))
                    for a, o in zip(lats, lons, strict=True)]

    nodes = ((0.0001, 0.0, 0, False), (0.0001, 0.009, 0, False))   # 1 km north
    poly = types.SimpleNamespace(def_path="Objects/e.fac", index=0, nodes=(nodes,))
    rows = DF._rows(poly, FS._facade_base(text), DF._surface(Mesh()))
    assert [r["verdict"] for r in rows] == ["FAIL", "FAIL"]       # 0 m, 500 m
    assert rows[0]["delta"] == pytest.approx(1.8)          # 2.0 - 0.2 over water
    low = FS._lowered_text(text, -1.8, "Objects/e.fac")
    rows = DF._rows(poly, FS._facade_base(low), DF._surface(Mesh()))
    assert {r["verdict"] for r in rows} == {"PASS"}


# ── #1971 a deck stack: its decks take the DECK bar; D1-D6 ──────────────

def _ll(x, y):
    """Local metres (east, north) about (LAT, LON) to (lat, lon)."""
    import math
    return (LAT + y / DC.M_PER_DEG,
            LON + x / (DC.M_PER_DEG * math.cos(math.radians(LAT))))


class _Mesh:
    """A drawn mesh as a function of local metres: the floor 100 between
    the walls (|x| <= 6), the roads 104 at the deck's ends (|x| >= 30), the
    ground ``beside`` elsewhere."""

    def __init__(self, beside=103.5):
        self.beside = beside

    def elevation_at_or_none(self, lat, lon):
        import math
        x = (lon - LON) * DC.M_PER_DEG * math.cos(math.radians(LAT))
        return 100.0 if abs(x) <= 6.0 else 104.0 if abs(x) >= 30.0 else self.beside


def _stack(deck_elev=100.0, beside=103.5):
    import types

    import numpy
    rec = {"id": "object_floor:stack:dsf:obj0", "resource": "objects/walls.obj",
           "objects": ["dsf:obj0", "dsf:obj1"],
           "stack": {"id": "stack:dsf:obj0", "zero_m": 100.0, "levels": 1, "feet_y": 0.0,
                     "crest_y": 3.5, "floor_line": [_ll(0, y) for y in range(-50, 51, 2)],
                     "rim": [[_ll(-6, y) for y in range(-50, 51, 2)],
                             [_ll(6, y) for y in range(-50, 51, 2)]],
                     "decks": [{"object": "dsf:obj1", "resource": "objects/deck.obj",
                                "piece": 0, "level": 1, "carried": [-10], "plate_min_y": 4.0,
                                "ring": [_ll(-30, -5), _ll(30, -5), _ll(30, 5), _ll(-30, 5)],
                                "ends": [{"end": "a", "top": 4.0,
                                          "stations": [_ll(-30, y) for y in (-5, 0, 5)]},
                                         {"end": "b", "top": 4.0,
                                          "stations": [_ll(30, y) for y in (-5, 0, 5)]}]}]}}
    rows = [types.SimpleNamespace(def_path="objects/walls.obj", lat=LAT, lon=LON,
                                  kind="OBJECT_MSL", elevation=100.0, heading_deg=0.0),
            types.SimpleNamespace(def_path="objects/deck.obj", lat=LAT, lon=LON,
                                  kind="OBJECT_MSL", elevation=deck_elev, heading_deg=0.0)]
    drawn = types.SimpleNamespace(
        rows=rows, mesh=_Mesh(beside),
        vertices=lambda i: (numpy.array([LON]), numpy.array([LAT]), numpy.array([100.0])))
    claims = [DC.Claim("object_floor", rec["id"], "objects/walls.obj", "whole")]
    return DC.check_stack(rec, drawn, claims, 0.3, 5.0), rec


def test_a_stack_deck_takes_the_deck_bar_not_the_cut_bar():
    import types
    _row, rec = _stack()
    dump = types.SimpleNamespace(placements=[types.SimpleNamespace(def_path="objects/walls.obj"),
                                             types.SimpleNamespace(def_path="objects/deck.obj")])
    claims = DC.read_claims({"object_floors": [rec]}, "+45+010", {}, {"+45+010": dump})
    kinds = {c.resource: c.kind for c in claims}
    assert kinds == {"objects/walls.obj": "object_floor", "objects/deck.obj": DC.DECK_ANCHOR}


def test_a_seated_stack_passes_d1_to_d6():
    row, _rec = _stack()
    assert row["role"] == "STACK" and row["verdict"] == "PASS", row["fails"]
    assert row["d1_spread"] == 0.0 and row["d2_worst"] == 0.0
    assert all(abs(x) < 1e-6 for e in row["d3"] for x in e["road"] + e["ground"])
    assert len(row["d3"]) == 2
    assert row["d4"][0]["least"] == pytest.approx(0.5)


def test_a_deck_off_the_stack_zero_and_ground_through_a_deck_fail():
    row, _rec = _stack(deck_elev=101.0)
    assert any(f.startswith("D1") for f in row["fails"])
    assert any(f.startswith("D3") for f in row["fails"])
    row, _rec = _stack(beside=105.0)
    assert any(f.startswith("D4") for f in row["fails"])
    assert any(f.startswith("D5") for f in row["fails"])


# ── v2 (spec interchange-levels-v2-20261113.md §8.2 / §8.3, T24) ────────

class _Faces:
    """A synthetic patch: the road face where |x| >= 30 and |y| <= 2, the
    ground face elsewhere within |y| <= ``covered``, nothing beyond; its
    surface is ``mesh``."""

    def __init__(self, mesh, covered=1e9):
        self.mesh, self.covered = mesh, covered

    def _xy(self, lat, lon):
        import math
        return ((lon - LON) * DC.M_PER_DEG * math.cos(math.radians(LAT)),
                (lat - LAT) * DC.M_PER_DEG)

    def at(self, lat, lon):
        x, y = self._xy(lat, lon)
        if abs(y) > self.covered:
            return None
        role = "service_road" if abs(x) >= 30.0 and abs(y) <= 2.0 else "graded_strip"
        return self.mesh.elevation_at_or_none(lat, lon), role, "r"

    def gap_m(self, lat, lon):
        return max(0.0, abs(self._xy(lat, lon)[1]) - self.covered)

    def elevation_at_or_none(self, lat, lon):
        return self.mesh.elevation_at_or_none(lat, lon)


def test_t24_d2_reads_a_hanging_wall():
    import numpy
    _row, rec = _stack()
    for bottom, fails in ((100.3, True), (100.05, False)):
        row, _ = _stack()
        drawn = _drawn_with_bottom(bottom)
        row = DC.check_stack(rec, drawn, [], 0.3, 5.0)
        assert any(f.startswith("D2") for f in row["fails"]) is fails, row["fails"]
    del numpy


def _drawn_with_bottom(bottom, beside=103.5):
    import types

    import numpy
    rows = [types.SimpleNamespace(def_path="objects/walls.obj", lat=LAT, lon=LON,
                                  kind="OBJECT_MSL", elevation=100.0, heading_deg=0.0),
            types.SimpleNamespace(def_path="objects/deck.obj", lat=LAT, lon=LON,
                                  kind="OBJECT_MSL", elevation=100.0, heading_deg=0.0)]
    return types.SimpleNamespace(
        rows=rows, mesh=_Mesh(beside),
        vertices=lambda i: (numpy.array([LON]), numpy.array([LAT]), numpy.array([bottom])))


def test_t24_d3_reads_road_and_ground_stations_apart():
    _row, rec = _stack()
    row = DC.check_stack(rec, _drawn_with_bottom(100.0), [], 0.3, 5.0, faces=_Faces(_Mesh()))
    assert all(e["road"] and e["ground"] for e in row["d3"])


def test_t24_d4_reads_the_plate_at_the_cell():
    """An arched plate (4.0 at the ends, 6.0 at the crown): ground at 105
    under mid-span stands under the plate there, over its lowest point."""
    _row, rec = _stack(beside=105.0)
    d = rec["stack"]["decks"][0]
    tris = []
    for x0, x1, y0, y1 in ((-30, 0, 4.0, 6.0), (0, 30, 6.0, 4.0)):
        a, b, c, e = _ll(x0, -5), _ll(x1, -5), _ll(x1, 5), _ll(x0, 5)
        tris += [[[*a, y0], [*b, y1], [*c, y1]], [[*a, y0], [*c, y1], [*e, y0]]]
    d["plate"] = tris
    row = DC.check_stack(rec, _drawn_with_bottom(100.0, 105.0), [], 0.3, 5.0)
    # beside 105 under the walls' notch (|x| 6..30): plate 4.4..6 over it
    least = row["d4"][0]["least"]
    assert least < 0.0
    d["plate"] = []                                       # the old reading: plate_min_y
    row_min = DC.check_stack(rec, _drawn_with_bottom(100.0, 105.0), [], 0.3, 5.0)
    assert row_min["d4"][0]["least"] < least


def test_t24_d6_only_on_published_caps_and_a_sample_on_no_face_is_incomplete():
    _row, rec = _stack()
    rec["stack"]["caps"] = [[_ll(6, -50), _ll(12, -50), _ll(12, 50), _ll(6, 50)]]
    rec["stack"]["band_m"] = 1.0
    row = DC.check_stack(rec, _drawn_with_bottom(100.0), [], 0.3, 5.0)
    assert row["samples"]["D6"] < 52                       # the west rim has no cap
    pred = DC.check_stack(rec, None, [], 0.3, 5.0, faces=_Faces(_Mesh(), covered=20.0),
                          predict=True, standoff=1.0)
    assert pred["mode"] == "PREDICTED" and pred["uncovered"]
    assert pred["verdict"] in ("INCOMPLETE", "FAIL") and pred["verdict"] != "PASS"
    assert DC.run_predict.__doc__ and DC.check_stack is DC.check_stack   # one function


def test_d5_samples_outside_the_wall_line_at_its_end():
    """Outside the wall line is its own normal, away from the floor -- at a
    wall's end, past the floor's last station, the direction to that
    station runs along the wall (KDEN l1971r2: the run-out's void band)."""
    pts = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)]
    n = DC._outward(pts, 0, (20.0, 3.0))          # the floor lies north-east
    assert abs(n[0]) < 1e-9 and n[1] == pytest.approx(-1.0)


def test_a_gap_reads_the_face_at_its_edge_not_inside_a_sliver_triangle():
    """``patch_faces.PatchFaces._on_edge`` (lkden3): a face's height at its
    boundary point is the plane of its triangle read AT the point -- linear
    along the edge's ring vertices -- so a 0.5 m sliver triangle whose far
    vertex falls 5.5 m reads the edge's own height (KDEN round 2's predicted
    D5 -0.30 against a drawn -0.24)."""
    import numpy as np
    import shapely

    import patch_faces as pf
    f = pf.PatchFaces.__new__(pf.PatchFaces)
    f.tris = np.array([[[0.0, -1.0], [0.0, 1.0], [-0.5, 3.0]]])
    f.tz = np.array([[10.0, 10.0, 4.5]])
    f.owner = np.array([0])
    f._tree = shapely.STRtree(shapely.polygons(f.tris))
    assert f._on_edge(0, 0.0, 0.0) == pytest.approx(10.0)
    assert f._on_edge(1, 0.0, 0.0) is None
