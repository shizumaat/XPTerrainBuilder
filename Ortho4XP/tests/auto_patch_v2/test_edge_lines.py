"""Twins of issue #2054: a pack LINE object's class read from its geometry
and texture (``airport/line_solidity``), and the strip a line standing on
a paved edge where the ground falls away mints out to its base
(``classify/edge_line_mint``), levelled onto its host after the solve
(``solve/project_strip``)."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import dsf, facade, wall_class, wall_top
from auto_patch_v2.airport import line_solidity as ls
from auto_patch_v2.classify import edge_line_mint as em
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model import planar as mp
from auto_patch_v2.model.airport import EdgeLine
from PIL import Image
from shapely.geometry import Polygon, box

CFG = load_rules().service


# ── the class, from geometry and texture ─────────────────────────────────

def _texture(path, mesh: bool = False):
    """A 64 px RGBA texture: v in [0.5, 1] opaque concrete, v in [0, 0.5) a
    chain-link (one wire pixel in four) when ``mesh``."""
    a = np.full((64, 64), 255, dtype=np.uint8)
    if mesh:
        a[32:, :] = 0
        a[32::2, ::2] = 255
    Image.fromarray(np.dstack([a, a, a, a]), "RGBA").save(path)


def _quad(y0, y1, v0, v1, z0=0.0, z1=-6.0):
    """A vertical sheet x = 0 from y0 to y1 along z, v mapped v0..v1."""
    return [(0.0, y0, z0, 0.0, v0), (0.0, y1, z0, 0.0, v1),
            (0.0, y1, z1, 1.0, v1), (0.0, y0, z1, 1.0, v0)]


def _obj(path, quads, tex="t.png", width=0.0):
    vts, idx = [], []
    for q in quads:
        b = len(vts)
        vts += q
        idx += [b, b + 1, b + 2, b, b + 2, b + 3]
    if width:                                # a plan-wide foot
        b = len(vts)
        vts += [(-width, 0.0, 0.0, 0.0, 0.9), (width, 0.0, 0.0, 0.1, 0.9),
                (width, 0.0, -6.0, 0.1, 1.0)]
        idx += [b, b + 1, b + 2]
    lines = ["A", "800", "OBJ", "", f"TEXTURE {tex}",
             f"POINT_COUNTS {len(vts)} 0 0 {len(idx)}"]
    lines += [f"VT {x} {y} {z} 0 0 1 {u} {v}" for x, y, z, u, v in vts]
    lines += [f"IDX {i}" for i in idx]
    lines += [f"TRIS 0 {len(idx)}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return str(path)


def test_a_wire_fence_reads_its_foot(tmp_path):
    _texture(tmp_path / "t.png", mesh=True)
    s = ls.obj_solidity(_obj(tmp_path / "w.obj", [_quad(0.0, 2.0, 0.0, 0.49)]))
    assert s.solid_m < CFG.line_wire_max_solid_m and s.opaque_share < 0.5
    assert ls.kind_of(s, CFG) == ls.WIRE_FENCE


def test_a_barrier_under_a_chain_link_reads_the_barrier(tmp_path):
    _texture(tmp_path / "t.png", mesh=True)
    s = ls.obj_solidity(_obj(tmp_path / "b.obj", [_quad(0.0, 1.0, 0.5, 1.0),
                                                   _quad(1.0, 4.0, 0.0, 0.49)],
                             width=0.35))
    assert s.solid_m == pytest.approx(1.0, abs=ls.BIN_M)
    assert s.half_width_m == pytest.approx(0.35)
    assert ls.kind_of(s, CFG) == ls.LOW_BARRIER


def test_a_solid_wall_on_its_zero_stands_on_top_and_a_buried_one_retains(tmp_path):
    _texture(tmp_path / "t.png")
    tall = ls.obj_solidity(_obj(tmp_path / "s.obj", [_quad(0.0, 4.0, 0.5, 1.0)]))
    assert ls.kind_of(tall, CFG) == ls.SOLID_WALL and ls.SOLID_WALL in ls.ON_TOP
    buried = ls.obj_solidity(_obj(tmp_path / "r.obj", [_quad(-4.2, 3.8, 0.5, 1.0)]))
    assert buried.buried_m == pytest.approx(4.2) and buried.solid_m == pytest.approx(8.0)
    assert ls.kind_of(buried, CFG) == ls.RETAINING_WALL
    assert ls.RETAINING_WALL not in ls.ON_TOP
    # a fence sunk by design (0.6 m) is no retaining wall
    sunk = ls.obj_solidity(_obj(tmp_path / "k.obj", [_quad(-0.6, 1.0, 0.5, 1.0)]))
    assert ls.kind_of(sunk, CFG) == ls.LOW_BARRIER
    up = ls.obj_solidity(_obj(tmp_path / "e.obj", [_quad(5.0, 7.5, 0.5, 1.0)]))
    assert ls.kind_of(up, CFG) == ls.ELEVATED


def test_a_facade_reads_its_mesh_with_its_attached_objects(tmp_path):
    _texture(tmp_path / "t.png", mesh=True)
    _obj(tmp_path / "base.obj", [_quad(0.0, 1.0, 0.5, 1.0)], width=0.35)
    v = [(0, 1.0, 0, 0.0, 0.0), (0, 4.0, 0, 0.0, 0.49), (0, 4.0, -6, 1.0, 0.49),
         (0, 1.0, -6, 1.0, 0.0)]
    fac = tmp_path / "f.fac"
    fac.write_text("\n".join(
        ["A", "1000", "FACADE", "", "RING 0", "TEXTURE t.png", "OBJ base.obj",
         "FLOOR fence", "SEGMENT 0", "MESH 0 1000 1 4 6"]
        + [f"VERTEX {x} {y} {z} 0 0 1 {u} {vv}" for x, y, z, u, vv in v]
        + ["IDX 0 1 2 0 2 3", "ATTACH_GRADED 0 0 0 0 0", "WALL 0 1000 0 0 w",
           "SPELLING 0"]) + "\n", encoding="utf-8", newline="\n")
    s = ls.facade_solidity(str(fac))
    assert s.top_y == pytest.approx(4.0) and s.solid_m == pytest.approx(1.0, abs=ls.BIN_M)
    assert ls.kind_of(s, CFG) == ls.LOW_BARRIER
    assert facade.facade_class(facade.parse_facade(str(fac))) == facade.LINE


def test_a_two_node_line_facade_is_kept_only_when_asked(tmp_path):
    p = tmp_path / "d.txt"
    p.write_text("POLYGON_DEF lib/f.fac\nBEGIN_POLYGON 0 0 2\nBEGIN_WINDING\n"
                 "POLYGON_POINT -122.0 37.0\nPOLYGON_POINT -122.001 37.0\n"
                 "END_WINDING\nEND_POLYGON\n", encoding="utf-8", newline="\n")
    assert dsf.read_dump(str(p)).polygons == ()
    (got,) = dsf.read_dump(str(p), keep_line=lambda d: True).polygons
    assert len(got.windings[0]) == 2


# ── the strip: the host's edge out to the line's base ───────────────────

ROAD = ((0.0, 0.0), (100.0, 0.0), (100.0, 8.0), (0.0, 8.0))   # a road, y 0..8


class _Dem:
    """Flat 3 m on the road side, falling to 0 beyond y = 14, water past 15."""

    def z_many(self, xs, ys):
        return np.where(np.asarray(ys, float) > 14.0, 0.0, 3.0)

    def water_many(self, xs, ys):
        ys = np.asarray(ys, float)
        return ys > 15.0, np.where(ys > 15.0, 0.0, np.nan)

    def water_geometry(self, bounds):
        return Polygon([(-50, 15), (150, 15), (150, 60), (-50, 60)])


def _line(base=0.0, solid_top=1.25, y=13.0):
    return EdgeLine("dsf:line0", "Misc/Fence_Concrete_Barrier.fac",
                    ((0.0, y), (100.0, y)), False, base, 4.0, solid_top, 0.6, 0.35)


def _mint(lines, dem=None, role="service_road", ref="small_roads:-1232#1",
          side="groundside", grown=None):
    law, rules = Law.for_airport("KSFO"), load_rules()
    cells = [Cell(0, role, ref, ROAD, (), None, None, side, role, {})]
    out = []

    def add(r, rf, poly, kind, cn=None, cl=None, evidence=None):
        out.append((r, rf, poly, dict(evidence or {})))
    st = em.mint_edge_strips(types.SimpleNamespace(edge_lines=lines, dem=dem or _Dem()),
                             cells, law, rules, add)
    if grown is not None:
        grown.extend(cells)
    return out, st


def test_a_groundside_host_takes_the_ground_out_to_the_barriers_base():
    cells = []
    out, st = _mint((_line(),), grown=cells)
    assert out == [] and st["edge_hosts_grown"] == 1
    (road,) = cells
    g = Polygon(road.ring, road.holes)
    assert road.ref == "small_roads:-1232#1" and road.role == "service_road"
    assert g.bounds[3] == pytest.approx(13.35, abs=0.1)       # the line + its half base
    assert road.evidence["edge_kind"] == ls.LOW_BARRIER


def test_an_airside_host_gets_a_late_strip_and_never_grows():
    cells = []
    out, st = _mint((_line(),), role="apron", ref="pav2", side="airside", grown=cells)
    ((role, ref, poly, ev),) = out
    assert role == "groundside_pavement" and ref == "edgestrip:0:pav2"
    assert mp.edge_strip_host(ref) == "pav2" and mp.is_late_ref(ref)
    assert ev["edge_kind"] == ls.LOW_BARRIER and st["edge_strips"] == 1
    assert poly.bounds[3] == pytest.approx(13.35, abs=0.1)
    assert poly.distance(Polygon(ROAD)) >= 1.4                # the §52 stand-off
    assert Polygon(cells[0].ring).equals(Polygon(ROAD))       # the apron as it was


def test_no_strip_where_the_ground_does_not_fall_or_the_line_retains():
    class Level(_Dem):
        def z_many(self, xs, ys):
            return np.full(np.shape(ys), 3.0)

        def water_many(self, xs, ys):
            return np.zeros(np.shape(ys), bool), np.full(np.shape(ys), np.nan)
    assert _mint((_line(),), Level())[1].get("edge_hosts_grown", 0) == 0
    out, st = _mint((_line(base=-4.2, solid_top=3.8),))
    assert st["edge_kind_retaining_wall"] == 1 and st.get("edge_hosts_grown", 0) == 0
    assert _mint((_line(y=30.0),))[1].get("edge_hosts_grown", 0) == 0   # out of reach


def test_ground_rising_past_a_boundary_fence_marks_the_edge_too():
    """KCRW 38.363304, -81.588474 (owner 16:04Z): the terrain RISES outside
    the fence -- the graded level holds to the fence all the same."""
    class Rising(_Dem):
        def z_many(self, xs, ys):
            return np.where(np.asarray(ys, float) > 13.5, 304.0, 300.0)

        def water_many(self, xs, ys):
            return np.zeros(np.shape(ys), bool), np.full(np.shape(ys), np.nan)

        def water_geometry(self, bounds):
            return None
    wire = EdgeLine("dsf:line0", "lib/constructions/fencing/fence_MeshHigh_05.fac",
                    ((0.0, 13.0), (100.0, 13.0)), False, -0.05, 2.33, -0.05, 0.3, 0.0)
    cells = []
    _mint((wire,), Rising(), grown=cells)
    assert cells[0].evidence["edge_kind"] == ls.WIRE_FENCE
    assert Polygon(cells[0].ring).bounds[3] == pytest.approx(13.0, abs=0.1)


def test_the_edge_ground_stops_at_the_water():
    cells = []
    _mint((_line(y=16.0),), grown=cells)
    assert Polygon(cells[0].ring).bounds[3] <= 15.0 + 1e-6


def test_projection_levels_the_edge_strip_on_its_host_rim():
    from auto_patch_v2.solve.project_strip import project_facade_strips
    xy = {0: (0, 0), 1: (100, 0), 2: (100, 8), 3: (0, 8),            # the road
          4: (0, 9.5), 5: (100, 9.5), 6: (100, 13.3), 7: (0, 13.3)}  # its strip
    V = {k: types.SimpleNamespace(xy=(float(x), float(y))) for k, (x, y) in xy.items()}
    F = [("service_road", "small_roads:-1232#1", (0, 1, 2, 3)),
         ("groundside_pavement", "edgestrip:0:small_roads:-1232#1", (4, 5, 6, 7))]
    pm = types.SimpleNamespace(
        faces={i: types.SimpleNamespace(id=i, role=r, ref=ref, ring=ring, holes=())
               for i, (r, ref, ring) in enumerate(F)},
        vertices=V, ring_vertices=lambda ring: tuple(ring))
    z = [3.0, 3.1, 3.1, 3.0, 1.0, 1.2, 0.4, 0.2]
    out, rep = project_facade_strips(pm, Law.for_airport("KSFO"), z)
    assert out[:4] == tuple(z[:4])                    # the host is read, never written
    assert out[4] == pytest.approx(3.0) and out[5] == pytest.approx(3.1)
    assert out[6] == pytest.approx(3.1) and out[7] == pytest.approx(3.0)
    assert rep["strips"][0]["pad_ref"] == "small_roads:-1232#1" and rep["no_host"] == 0


# ── a buried solid wall retains the step it shows, whatever its name ────

WALL = box(0.0, 0.0, 200.0, 0.5)       # 0.5 m thick along y = 0..0.5


class _StepDem:
    """35.3 m on the upper side (y < 0.25), 32.5 m on the lower: a 2.8 m
    step across a wall 8 m solid and 4.2 m under its zero (KLAX's)."""

    def z_many(self, xs, ys):
        return np.where(np.asarray(ys, float) < 0.25, 35.3, 32.5)


def test_the_buried_witness_retains_the_step_within_the_buried_face():
    ap = types.SimpleNamespace(dem=_StepDem())
    got = wall_class._buried_step(ap, WALL, 0.5, 8.0, 4.2, CFG)
    assert got == pytest.approx(2.8)
    # the depth and the solid height witnesses do not match a 2.8 m step
    assert not wall_class._retains_its_height(ap, WALL, 0.5, 8.0, CFG, 4.2)
    # a step under the wall-class height, or past the buried face, is none
    assert wall_class._buried_step(ap, WALL, 0.5, 8.0, 2.0, CFG) == 0.0
    ap.dem = types.SimpleNamespace(z_many=lambda xs, ys: np.where(
        np.asarray(ys, float) < 0.25, 34.0, 32.5))
    assert wall_class._buried_step(ap, WALL, 0.5, 8.0, 4.2, CFG) == 0.0


def _fence_airport(tmp_path, base_y, name="Misc/Fence_Terminal_1.obj"):
    _texture(tmp_path / "t.png")
    path = _obj(tmp_path / "w.obj", [_quad(base_y, base_y + 8.0, 0.5, 1.0)])
    ring = [(lat, lon) for lon, lat in WALL.exterior.coords]
    part = types.SimpleNamespace(rings=[ring], line=False, height_m=8.0,
                                 base_y=base_y, comp=0, feet=[(0.0, 0.0)])
    member = types.SimpleNamespace(id="m1", resource=name, authored_path=path,
                                   parts=[part], zero_y=0.0, origin=(0.0, 100.0))
    unit = types.SimpleNamespace(id="unit:1", agl_m=0.0, anchor=(0.0, 100.0),
                                 members=[member])
    return types.SimpleNamespace(
        partition=types.SimpleNamespace(units=[unit]), dem=_StepDem(),
        frame=types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat))))


def test_a_fence_named_wall_buried_under_its_zero_is_a_retaining_wall(tmp_path):
    wall_class._BURIED.clear()
    (w,) = wall_class.wall_class_components(_fence_airport(tmp_path, -4.2), CFG)
    assert w.retains and w.retained_m == pytest.approx(2.8)
    assert w.retained_top_y == 0.0            # its retained face stops at its zero
    assert wall_top._retained_floor(w) == pytest.approx(-2.8)


def test_a_fence_standing_on_its_zero_stays_no_wall(tmp_path):
    wall_class._BURIED.clear()
    assert wall_class.wall_class_components(_fence_airport(tmp_path, 0.0), CFG) == []
