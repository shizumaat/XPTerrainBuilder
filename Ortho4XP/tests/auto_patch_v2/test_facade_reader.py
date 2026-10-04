"""Twins of the ``.fac`` reader (issue #334, RULINGS 2026-10-04d (3)):
the class table, the attachment reach, the per-edge wall and the DSF wall
index carried through ``dsf.read_dump``.  Synthetic files only."""
from __future__ import annotations

import os
import sys

import pytest

from auto_patch_v2.airport import dsf, facade

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))
import facade_census  # noqa: E402

VT = "VT {x} {y} {z} 0 1 0 0 0\n"


def _obj(path, pts):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("A\n800\nOBJ\n\n" + "".join(VT.format(x=x, y=y, z=z)
                                                for x, y, z in pts))


def _fac(path, body, version=1000):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"A\n{version}\nFACADE\n{body}")
    return str(path)


CARGO = """GRADED
RING 1
SHADER_ROOF
OBJ door.obj
OBJ lib/vehicles/trailer.obj
OBJ stairs.obj
FLOOR low
ROOF_HEIGHT 6.7
SEGMENT 0
SEGMENT 1
ATTACH_GRADED 0 0.2 0.0 -2.5 90.0 3 4
ATTACH_DRAPED 1 3.4 0.0 -2.5 90.0 3 4
SEGMENT 2
ATTACH_DRAPED 2 0.2 0.0 -1.0 90.0
SEGMENT_CURVED 0
SEGMENT_CURVED 1
ATTACH_GRADED 0 0.2 0.0 -2.5 90.0 3 4
WALL 0 1000 0 0 Loading_doors
SPELLING 0
SPELLING 0 1 0
WALL 0 1000 0 0 Entrance
SPELLING 0 2
WALL 0 1000 0 0 Solid_wall
SPELLING 0
FLOOR high
ROOF_HEIGHT 12.0
SEGMENT 0
WALL 0 1000 0 0 Solid_wall
SPELLING 0
"""


@pytest.fixture()
def cargo(tmp_path):
    pack = tmp_path / "lib" / "bld"
    _obj(str(pack / "door.obj"), [(-2, 0, -0.6), (2, 4, 0.0)])
    _obj(str(pack / "stairs.obj"), [(-1, 0, -2.7), (1, 1, 0.0)])
    # the library: ONE virtual path, two models and an empty — the merged
    # index keeps one of them per key (the empty, under the exact case)
    veh = tmp_path / "lib" / "veh"
    _obj(str(veh / "t1.obj"), [(-1.3, 0, -9.8), (1.3, 4, 2.5)])
    _obj(str(veh / "t2.obj"), [(-1.3, 0, -6.0), (1.3, 4, 2.0)])
    _obj(str(veh / "Empty.obj"), [])
    with open(veh.parent / "library.txt", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("A\n800\nLIBRARY\n\n"
                 "EXPORT lib/vehicles/trailer.obj veh/t1.obj\n"
                 "EXPORT lib/vehicles/trailer.obj veh/t2.obj\n"
                 "EXPORT lib/vehicles/trailer.obj veh/Empty.obj\n")
    index = {"lib/vehicles/trailer.obj": str(veh / "Empty.obj")}
    return facade.parse_facade(_fac(pack / "cargo.fac", CARGO), index)


def test_class_table(tmp_path, cargo):
    cls = {
        "ring0": "RING 0\nSHADER_ROOF\nFLOOR a\nROOF_HEIGHT 3\nWALL 0 9 0 0 w\n",
        "fence": "RING 1\nFLOOR a\nWALL 0 9 0 0 w\n",
        "lot": "SHADER_ROOF\nOBJ lib/cars/car_static.obj\nFLOOR p\n"
               "ROOF_HEIGHT 0.000000\nROOF_OBJ_HEADING 0 1 1 0\nWALL 0 9 0 0 w\n",
        "deck": "SHADER_ROOF\nOBJ lib/cars/car_static.obj\nFLOOR p\n"
                "ROOF_HEIGHT 0 3 6\nROOF_OBJ_HEADING 0 1 1 0\nWALL 0 9 0 0 w\n",
        "no_mesh": "RING 1\nNO_ROOF_MESH\nSHADER_ROOF\nFLOOR a\nROOF_HEIGHT 9\n",
    }
    got = {k: facade.facade_class(facade.parse_facade(
        _fac(tmp_path / f"{k}.fac", body))) for k, body in cls.items()}
    assert got == {"ring0": facade.LINE, "fence": facade.LINE,
                   "lot": facade.LOT, "deck": facade.PARKING_STRUCTURE,
                   "no_mesh": facade.LINE}
    assert facade.facade_class(cargo) == facade.ROOFED
    v800 = {"shader": ("RING 1\nTWO_SIDED 0\nSHADER_ROOF\nWALL 0 8 0 360 solid\n",
                       facade.ROOFED),
            "roofrow": ("RING 1\nROOF 0 0\nWALL 0 8 solid\n", facade.ROOFED),
            "two_sided": ("RING 1\nTWO_SIDED 1\nSHADER_ROOF\n", facade.LINE),
            "bare": ("RING 1\nWALL 0 8 solid\n", facade.LINE)}
    for k, (body, want) in v800.items():
        f = facade.parse_facade(_fac(tmp_path / f"v8{k}.fac", body, 800))
        assert facade.facade_class(f) == want, k
    # the v800 two-argument WALL row keeps its name
    f = facade.parse_facade(_fac(tmp_path / "v8w.fac", "RING 1\nWALL 0 8 solid\n", 800))
    assert f.floors[0].walls[0].name == "solid" and f.floors[0].walls[0].fits(5.0)


def test_attachment_reach_is_the_widest_variant(cargo):
    low = facade.floor_for(cargo, 6.0)
    assert low.name == "low" and facade.floor_for(cargo, 11.0).name == "high"
    doors, entrance, solid = low.walls
    att = {os.path.basename(a.obj): a for a in doors.attachments}
    # x 3.4, heading 90: out = x - oz; the widest model's nose is 9.8 m out
    tr = att["trailer.obj"]
    assert tr.kind == "draped" and tr.vehicle and tr.variants == 3
    assert tr.reach == pytest.approx((3.4 - 2.5, 3.4 + 9.8))
    assert att["door.obj"].reach == pytest.approx((0.2, 0.8)) and not att["door.obj"].vehicle
    assert doors.reach_m() == pytest.approx(13.2)
    assert doors.reach_m(vehicles_only=True) == pytest.approx(13.2)
    # the curved twin of the dock segment carries no trailer
    assert [os.path.basename(a.obj) for a in doors.curved_attachments] == ["door.obj"]
    assert doors.reach_m(curved=True) == pytest.approx(0.8)
    assert entrance.reach_m() == pytest.approx(2.9) and entrance.reach_m(True) == 0.0
    assert solid.attachments == () and solid.reach_m() == 0.0


def test_unresolved_object_is_reported_not_zero(tmp_path):
    f = facade.parse_facade(_fac(
        tmp_path / "u.fac", "SHADER_ROOF\nOBJ lib/none.obj\nFLOOR a\nROOF_HEIGHT 5\n"
        "SEGMENT 0\nATTACH_DRAPED 0 1 0 0 0\nWALL 0 9 0 0 w\nSPELLING 0\n"), {})
    (a,) = f.floors[0].walls[0].attachments
    assert a.reach is None and a.reach_m is None and a.variants == 0


def test_edge_wall_dsf_index_wins_and_no_index_is_never_wall_zero(cargo):
    low = facade.floor_for(cargo, 6.0)
    got = facade.edge_walls(low, [40.0, 40.0, 40.0], [0, 2, 7])
    assert [(e.wall, e.from_dsf) for e in got] == [(0, True), (2, True), (None, True)]
    # no index: three walls fit and attach different things -> undecided
    (e,) = facade.edge_walls(low, [40.0], [None])
    assert e.wall is None and e.candidates == (0, 1, 2) and not e.from_dsf
    # ... and decided when every fitting wall attaches the same (the high
    # floor has one wall)
    (e,) = facade.edge_walls(facade.floor_for(cargo, 12.0), [40.0], [None])
    assert e.wall == 0 and e.candidates == (0,)


def test_placed_edges_take_the_whole_edge_and_the_curved_table(cargo):
    nodes = [(0.0, 0.0, 0, False), (50.0, 0.0, 2, False), (50.0, 20.0, 0, True),
             (0.0, 20.0, 2, False), (0.0, 20.0, 2, False)]
    edges = facade.placed_edges(cargo, 6.0, nodes)
    # the repeated closing node's zero-length edge is dropped
    assert [e.i for e in edges] == [0, 1, 2, 4]
    assert edges[0].name == "Loading_doors" and edges[0].length_m == 50.0
    assert max(a.reach_m for a in edges[0].attachments) == pytest.approx(13.2)
    assert edges[1].curved and edges[1].attachments == ()
    # a bezier Loading_doors edge draws the curved segment: no trailer
    assert edges[2].curved and edges[2].name == "Loading_doors"
    assert [os.path.basename(a.obj) for a in edges[2].attachments] == ["door.obj"]


DUMP = """POLYGON_DEF lib/a/Cargo.fac
POLYGON_DEF lib/a/page.pol
BEGIN_POLYGON 0 6 3
BEGIN_WINDING
POLYGON_POINT -77.10 -12.00 4.000000000
POLYGON_POINT -77.11 -12.00 0.000000000
POLYGON_POINT -77.11 -12.01 2.000000000
END_WINDING
END_POLYGON
BEGIN_POLYGON 0 6 2
BEGIN_WINDING
POLYGON_POINT -77.10 -12.00
POLYGON_POINT -77.11 -12.00
POLYGON_POINT -77.11 -12.01
END_WINDING
END_POLYGON
BEGIN_POLYGON 0 6 4
BEGIN_WINDING
POLYGON_POINT -77.10 -12.00 -77.10 -12.00
POLYGON_POINT -77.11 -12.00 -77.1101 -12.0001
POLYGON_POINT -77.11 -12.01 -77.11 -12.01
END_WINDING
END_POLYGON
BEGIN_POLYGON 0 6 5
BEGIN_WINDING
POLYGON_POINT -77.10 -12.00 4.000000000 -77.10 -12.00
POLYGON_POINT -77.11 -12.00 1.000000000 -77.1101 -12.0001
POLYGON_POINT -77.11 -12.01 0.000000000 -77.11 -12.01
END_WINDING
END_POLYGON
BEGIN_POLYGON 1 65535 4
BEGIN_WINDING
POLYGON_POINT -77.10 -12.00 0 0
POLYGON_POINT -77.11 -12.00 1 0
POLYGON_POINT -77.11 -12.01 1 1
END_WINDING
END_POLYGON
"""


def test_read_dump_keeps_the_wall_index(tmp_path):
    p = tmp_path / "d.text"
    p.write_text(DUMP, encoding="utf-8", newline="\n")
    d3, d2, d4, d5, uv = dsf.read_dump(str(p)).polygons
    assert (d3.depth, d2.depth, d4.depth, d5.depth) == (3, 2, 4, 5)
    assert [n[2] for n in d3.nodes[0]] == [4, 0, 2]
    assert [n[2] for n in d2.nodes[0]] == [None] * 3
    assert [n[2] for n in d4.nodes[0]] == [None] * 3
    assert [n[2] for n in d5.nodes[0]] == [4, 1, 0]
    assert [n[3] for n in d4.nodes[0]] == [False, True, False] == [n[3] for n in d5.nodes[0]]
    assert [n[:2] for n in d3.nodes[0]] == list(d3.windings[0])
    # the flattened rings are what they were: a straight ring is its nodes,
    # a curved one is re-sampled (its node count is not the ring's)
    assert d2.windings == d3.windings and d4.windings == d5.windings
    assert len(d4.windings[0]) > 3
    assert uv.nodes == ((),) and len(uv.windings[0]) == 3


def test_census_reads_class_area_and_reach(tmp_path, cargo, monkeypatch):
    p = tmp_path / "d.text"
    p.write_text(DUMP, encoding="utf-8", newline="\n")
    polys = dsf.read_dump(str(p), lambda q: q.endswith(".fac")).polygons
    monkeypatch.setattr(facade_census.facade, "read_facade", lambda d, root, index: cargo)
    rows = facade_census.census(polys, None, None)
    (r,) = rows.values()
    assert r["n"] == 4 and r["class"] == facade.ROOFED
    assert r["depths"] == {3: 1, 2: 1, 4: 1, 5: 1}
    one = 0.5 * (0.01 * 111320.0 * 0.978) * (0.01 * 110574.0)
    assert r["area_m2"] == pytest.approx(4 * one, rel=0.01)
    key = ("Loading_doors", "draped", "lib/vehicles/trailer.obj")
    assert r["attachments"][key]["reach"][1] == pytest.approx(13.2)
    # depth 3 edge 1 and depth 5 edge 2: wall 0 by the DSF index, straight
    assert r["attachments"][key]["edges"] == 2
    # the two polygons with no wall index are undecided on every edge
    assert len(r["undecided"]) == 6
    assert facade_census.census(polys, None, None, keep=lambda la, lo: False) == {}


def test_an_undecided_edge_may_attach_the_widest_candidate(cargo):
    """RULINGS 2026-10-04h (2): no DSF wall index and fitting walls that
    differ -> the edge is graded for what ANY of them may attach; a bezier
    edge counts its candidates' CURVED tables only."""
    nodes = [(0.0, 0.0, None, False), (50.0, 0.0, None, False),
             (50.0, 20.0, None, True), (0.0, 20.0, None, False)]
    e0, e1, e2, e3 = facade.placed_edges(cargo, 6.0, nodes)
    assert e0.wall.wall is None and e0.attachments == ()
    assert max(a.reach_m for a in e0.may_attach) == pytest.approx(13.2)
    assert e1.curved and max(a.reach_m for a in e1.may_attach) == pytest.approx(0.8)
    assert not e3.curved and max(a.reach_m for a in e3.may_attach) == pytest.approx(13.2)
    # a DECIDED edge never reads the candidates
    (d,) = facade.placed_edges(cargo, 6.0, [(0.0, 0.0, 2, False), (50.0, 0.0, 2, False)][:2]
                               + [(50.0, 20.0, 2, False)])[:1]
    assert d.may_attach == () and d.name == "Solid_wall"
    poly = dsf.DsfPolygon("x.fac", 6, (((0.0, 0.0), (0.0005, 0.0), (0.0005, 0.0002)),), 2,
                          (((0.0, 0.0, None, False), (0.0005, 0.0, None, False),
                            (0.0005, 0.0002, None, False)),))
    import unittest.mock as um
    with um.patch.object(facade, "read_facade", lambda *a: cargo):
        fr = facade.read_placed(poly, None, None, lambda lo, la: (lo * 1e5, la * 1e5))
    assert fr.undecided == 3 and len(fr.edges) == 3
    assert {round(e.reach_m, 1) for e in fr.edges} == {13.2}
    assert fr.edges[0].wall == "(any fitting wall)" and fr.edges[0].vehicle
