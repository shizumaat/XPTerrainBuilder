"""#2042: a GRADED facade's base stands on its drawn ground.

X-Plane stands a graded facade on the ground at its first wall's centre
and keeps it flat (facade spec); ``airport/facade_seat`` lowers the
FILE (a copy beside it, every height moved) until no foot — a mesh
vertex at or below the file's ground line — hangs over the drawn ground,
and ``dsf_write`` points the polygon at the copy.  The twins: the base
read (an embankment's two feet, an elevated guideway's buried columns
only, the files it cannot lower), the lowered copy, the seat on a
synthetic shore, the plan record and the DSF edit (text, and one real
DSFTool round trip on a synthetic pack)."""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest
from auto_patch.dsf_reader import _dsftool_path
from auto_patch_v2.airport import dsf as D
from auto_patch_v2.airport import dsf_write as W
from auto_patch_v2.airport import facade_seat as FS
from auto_patch_v2.model.placement import CUT_MARK, FacadeSeat, PlacementPlan, Provenance

#: An embankment like KOAK's ``see.fac``: a crest 2.1 m up, a steep foot
#: 7.3 m to the LEFT at -0.16 and a long slope to 13.6 m RIGHT at -0.48.
EMBANKMENT = """A
1000
FACADE
RING 0
GRADED
TEXTURE\tSeaEdge_road.dds

FLOOR see
SEGMENT 0
MESH 0 5000.000000 4 6 6
VERTEX\t-7.3 -0.16 0.0 0 1 0 0 0
VERTEX\t0.0 2.10 0.0 0 1 0 0 0
VERTEX\t13.6 -0.48 0.0 0 1 0 0 0
VERTEX\t11.2 0.75 -10.0 0 1 0 0 0
IDX 0 1 2 1 2 3
ATTACH_GRADED 0 1.0 0.5 -2.0 0
ATTACH_DRAPED 0 1.0 0.0 -2.0 0
WALL 0 10000 0 0 see
SPELLING 0
"""

#: An elevated guideway: a deck 4-5.5 m up on a column whose foot is
#: buried 3.98 m — only the column foot is base.
GUIDEWAY = EMBANKMENT.replace(
    "VERTEX\t-7.3 -0.16 0.0 0 1 0 0 0\nVERTEX\t0.0 2.10 0.0 0 1 0 0 0\n"
    "VERTEX\t13.6 -0.48 0.0 0 1 0 0 0\nVERTEX\t11.2 0.75 -10.0 0 1 0 0 0\n",
    "VERTEX\t-3.0 4.5 0.0 0 1 0 0 0\nVERTEX\t3.0 4.5 0.0 0 1 0 0 0\n"
    "VERTEX\t0.5 -3.98 0.0 0 1 0 0 0\nVERTEX\t0.5 5.5 -10.0 0 1 0 0 0\n")


def test_base_is_the_vertices_at_or_below_the_ground_line():
    b = FS._facade_base(EMBANKMENT)
    assert b is not None and b.ring is False
    assert b.feet == ((-7.3, -0.16), (13.6, -0.48))
    g = FS._facade_base(GUIDEWAY)
    assert g is not None and g.feet == ((0.5, -3.98),)


@pytest.mark.parametrize("edit", [
    ("1000\n", "800\n"),                       # v800: wall quads
    ("GRADED\n", "DRAPED\n"),                  # draped: X-Plane follows the ground
    ("MESH 0 5000.000000 4 6 6\n", ""),        # a segment without a mesh
    ("FLOOR see\n", "FLOOR see\nROOF_HEIGHT 6.0\n"),   # a roof
])
def test_files_no_edit_can_lower(edit):
    assert FS._facade_base(EMBANKMENT.replace(*edit)) is None


def test_a_facade_drawn_to_hang_has_no_base():
    hang = EMBANKMENT.replace("-0.16", "0.20").replace("-0.48", "0.30")
    assert FS._facade_base(hang) is None


def test_lowered_copy_moves_every_height_and_carries_the_mark():
    out = FS._lowered_text(EMBANKMENT, -1.6, "Objects/see.fac")
    lines = out.splitlines()
    assert lines[:3] == ["A", "1000", "FACADE"]
    assert lines[3].startswith(CUT_MARK + "Objects/see.fac")
    v = [ln.split() for ln in lines if ln.startswith("VERTEX")]
    assert [float(t[2]) for t in v] == pytest.approx([-1.76, 0.5, -2.08, -0.85])
    assert [t[1] for t in v] == ["-7.3", "0.0", "13.6", "11.2"]       # x untouched
    g = next(ln.split() for ln in lines if ln.startswith("ATTACH_GRADED"))
    d = next(ln.split() for ln in lines if ln.startswith("ATTACH_DRAPED"))
    assert float(g[3]) == pytest.approx(-1.1) and d[3] == "0.0"
    # the copy is still a graded mesh facade, its feet moved by the drop
    feet = dict(FS._facade_base(out).feet)
    assert feet[-7.3] == pytest.approx(-1.76) and feet[13.6] == pytest.approx(-2.08)
    a = FS._variant_resource("Objects/see.fac", EMBANKMENT, -1.6)
    assert a.startswith("Objects/see__g_") and a.endswith(".fac")
    assert a == FS._variant_resource("Objects/see.fac", EMBANKMENT, -1.6)
    assert a != FS._variant_resource("Objects/see.fac", EMBANKMENT, -1.5)


# ── a synthetic shore: land (2.0 m) east of lon 0, water (0.0) west ──────

def _shore(lat, lon):
    return 2.0 if lon > -0.00004 else 0.0


def _southward(n=3):
    """A chain walking SOUTH along lon 0: its RIGHT (outward) is WEST."""
    return [(0.0, 0.001 * (n - 1 - i)) for i in range(n)]


def test_seat_reads_the_first_wall_and_every_foot():
    # walking south the right foot (13.6 m, -0.48) lies WEST, over water
    s = FS._seat_polygon(_southward(), FS._facade_base(EMBANKMENT), _shore)
    assert s.anchor_z == 2.0
    assert s.need_z == pytest.approx(0.48)
    assert s.drop_m == pytest.approx(-1.52)
    # walking north the left foot (-0.16) is the one over the water
    north = list(reversed(_southward()))
    s = FS._seat_polygon(north, FS._facade_base(EMBANKMENT), _shore)
    assert s.drop_m == pytest.approx(-1.84)


def test_never_raised_and_a_guideway_stays_up():
    up = FS._seat_polygon(_southward(), FS._facade_base(EMBANKMENT),
                         lambda la, lo: 2.0)
    assert up.drop_m == 0.0                      # the feet are buried already
    col = FS._seat_polygon(_southward(), FS._facade_base(GUIDEWAY), _shore)
    assert col.drop_m == 0.0                     # columns 3.98 m deep: no float


def _pack(tmp_path: Path) -> tuple[str, types.SimpleNamespace]:
    (tmp_path / "Objects").mkdir()
    (tmp_path / "Objects" / "see.fac").write_text(EMBANKMENT, encoding="latin-1",
                                                  newline="")
    poly = types.SimpleNamespace(def_path="Objects/see.fac", index=3,
                                 nodes=(tuple((lo, la, 0, False)
                                              for lo, la in _southward()),))
    lib = types.SimpleNamespace(def_path="lib/fence.fac", index=4,
                                nodes=poly.nodes)
    return str(tmp_path), types.SimpleNamespace(polygons=(poly, lib))


def test_plan_seats_lowers_the_pack_facade_and_writes_one_copy(tmp_path):
    root, dump = _pack(tmp_path)
    seats, files, counts = FS.plan_seats(dump, root, _shore)
    (s,) = seats
    assert (s.index, s.resource) == (3, "Objects/see.fac")
    assert -1.53 <= s.drop_m <= -1.52            # floored to the centimetre
    assert counts == {"graded_facades": 1, "graded_facades_lowered": 1,
                      "graded_facade_drop_max_m": s.drop_m}
    assert files[0].resource == s.new_resource
    feet = dict(FS._facade_base(files[0].text).feet)
    assert feet[13.6] == pytest.approx(-0.48 + s.drop_m)
    box = FS.candidates_box(FS.candidates(dump, root))
    assert box[0] < -0.0001 and box[2] > 0.0001     # widened by the feet
    # on flat ground nothing is written
    assert FS.plan_seats(dump, root, lambda la, lo: 2.0)[0] == ()


# ── the plan and the DSF edit ────────────────────────────────────────────

SEAT = FacadeSeat(1, "Objects/see.fac", "Objects/see__g_00000000.fac", -1.6,
                  -94.65, 39.25, 1.76, 0.16)


def _plan(tmp_path: Path, **kw) -> PlacementPlan:
    d = dict(icao="TEST", pack_name="pack", pack_root=str(tmp_path),
             dsf_path=str(tmp_path / "t.dsf"),
             dsf_backup_path=str(tmp_path / "t.dsf.anchor_bak"),
             provenance=Provenance("sha", "1.0", "digest"))
    d.update(kw)
    return PlacementPlan(**d)


def test_plan_record_round_trips_and_composes(tmp_path):
    p = _plan(tmp_path, facade_seats=(SEAT,))
    assert PlacementPlan.from_dict(json.loads(p.to_json())).facade_seats == (SEAT,)
    assert PlacementPlan.from_dict(p.edit_rows()).facade_seats == (SEAT,)
    assert p.new_facades() == (SEAT.new_resource,) and p.counts()["facade_seats"] == 1
    other = _plan(tmp_path, facade_seats=(
        FacadeSeat(1, "Objects/see.fac", "Objects/x.fac", -9.0, 0, 0, 0, 0),
        FacadeSeat(2, "Objects/see.fac", "Objects/y.fac", -1.0, 0, 0, 0, 0)))
    got = p.compose([other]).facade_seats
    assert [f.new_resource for f in got] == [SEAT.new_resource, "Objects/y.fac"]


DUMP = """A
800 written by DSFTool 2.4.0-b1
DSF2TEXT

PROPERTY sim/west -95
PROPERTY sim/east -94
PROPERTY sim/north 40
PROPERTY sim/south 39
PROPERTY sim/planet earth
PROPERTY sim/creation_agent test
PROPERTY sim/overlay 1
OBJECT_DEF objects/tower.obj
POLYGON_DEF Objects/fence.fac
POLYGON_DEF Objects/see.fac
OBJECT 0 -94.715004864 39.296891928 194.027008
BEGIN_POLYGON 0 10 2
BEGIN_WINDING
POLYGON_POINT -94.70 39.20
POLYGON_POINT -94.69 39.20
POLYGON_POINT -94.68 39.20
END_WINDING
END_POLYGON
BEGIN_POLYGON 1 10 2
BEGIN_WINDING
POLYGON_POINT -94.65 39.26
POLYGON_POINT -94.65 39.25
POLYGON_POINT -94.65 39.24
END_WINDING
END_POLYGON
"""


def test_read_dump_counts_every_polygon(tmp_path):
    p = tmp_path / "d.txt"
    p.write_text(DUMP, encoding="utf-8", newline="")
    polys = D.read_dump(str(p), accept_polygon=lambda d: d.endswith("see.fac")).polygons
    assert [(q.index, q.def_path) for q in polys] == [(1, "Objects/see.fac")]


def test_edit_dump_points_the_polygon_at_its_copy(tmp_path):
    out = W.edit_dump(DUMP, _plan(tmp_path, facade_seats=(SEAT,)), "t")
    lines = out.splitlines()
    i = lines.index("POLYGON_DEF Objects/see.fac")
    assert lines[i + 1] == "POLYGON_DEF Objects/see__g_00000000.fac"
    assert "BEGIN_POLYGON 0 10 2" in lines and "BEGIN_POLYGON 2 10 2" in lines
    assert "BEGIN_POLYGON 1 10 2" not in lines
    with pytest.raises(ValueError, match="dump definition"):
        W.edit_dump(DUMP, _plan(tmp_path, facade_seats=(
            FacadeSeat(0, "Objects/see.fac", "x.fac", -1.0, 0, 0, 0, 0),)), "t")
    with pytest.raises(ValueError, match="does not have"):
        W.edit_dump(DUMP, _plan(tmp_path, facade_seats=(
            FacadeSeat(7, "Objects/see.fac", "x.fac", -1.0, 0, 0, 0, 0),)), "t")


@pytest.mark.skipif(_dsftool_path() is None, reason="no DSFTool on this machine")
def test_real_round_trip_writes_the_copy_and_records_it(tmp_path):
    from auto_patch_v2.airport import placement_write as PW
    tool = _dsftool_path()
    pack = tmp_path / "pack"
    (pack / "objects").mkdir(parents=True)
    (pack / "objects" / "tower.obj").write_text("I\n800\nOBJ\n", encoding="utf-8",
                                                newline="")
    (pack / "Objects").mkdir(exist_ok=True)
    for name in ("fence.fac", "see.fac"):
        (pack / "Objects" / name).write_text(EMBANKMENT, encoding="latin-1", newline="")
    blk = pack / "Earth nav data" / "+30-100"
    blk.mkdir(parents=True)
    src = tmp_path / "src.text"
    src.write_text(DUMP, encoding="utf-8", newline="")
    dsf = W.encode(str(src), str(blk / "+39-095.dsf"), tool)
    text = W.dump(dsf, str(tmp_path / "pristine.text"), tool)
    dump = D.read_dump(text)
    shore = lambda la, lo: 2.0 if lo > -94.65 - 4e-5 else 0.0   # noqa: E731
    seats, files, _c = FS.plan_seats(dump, str(pack), shore)
    assert [s.resource for s in seats] == ["Objects/see.fac"]
    plan = PlacementPlan(icao="TEST", pack_name="pack", pack_root=str(pack),
                         dsf_path=dsf, dsf_backup_path=dsf + ".anchor_bak",
                         provenance=Provenance("", "test", ""), facade_seats=seats)
    res = PW.apply_plan(plan, files, tool, work_dir=str(tmp_path / "w"))
    assert res.dsf.report.ok, res.dsf.report.findings
    after = D.read_dump(W.dump(dsf, str(tmp_path / "after.text"), tool))
    assert sorted(p.def_path for p in after.polygons) == sorted(
        ["Objects/fence.fac", seats[0].new_resource])
    copy = pack / seats[0].new_resource
    assert copy.is_file() and CUT_MARK in copy.read_text(encoding="latin-1", newline="")
    rec = json.loads(Path(res.dsf.provenance_path).read_text(encoding="utf-8"))
    assert seats[0].new_resource in rec["body_files"]
    # the next write, lowering nothing, removes the copy (the restore step)
    bare = PlacementPlan(icao="TEST", pack_name="pack", pack_root=str(pack),
                         dsf_path=dsf, dsf_backup_path=dsf + ".anchor_bak",
                         provenance=Provenance("", "test", ""))
    res2 = PW.apply_plan(bare, (), tool, work_dir=str(tmp_path / "w2"))
    assert res2.dsf.report.ok and not copy.exists()
    assert sorted(p.def_path for p in D.read_dump(
        W.dump(dsf, str(tmp_path / "again.text"), tool)).polygons) == \
        ["Objects/fence.fac", "Objects/see.fac"]
