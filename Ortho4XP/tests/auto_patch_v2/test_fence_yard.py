"""Spec 2068 A2 F2: THE FENCE YARD (``classify/fence_yard``).  A unit's
fence standing a storey up round its upper pad encloses the fence-foot
plane's ground: one plane through the upper stations, the yard out to the
fence and nothing outside it, low stations left out, a pocket across a
shared fence taken, a one-sided corridor refused; a non-planar fence, no
upper pad and level ground take nothing."""
from __future__ import annotations

import math
import types

import pytest
from auto_patch_v2.classify import fence_yard as fy
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.classify.storey_edge import (
    UPPER_AIR_Z_KEY,
    UPPER_FLOOR_KEY,
    UPPER_UNIT_KEY,
    UPPER_Y_KEY,
)
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import EdgeLine
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

LAW = Law.for_airport("SYNT")
GX, GY = 0.0, -0.02            # the authored ground falls 2 % toward the apron (north)


def _base(x, y):
    return 4.5 + GX * (x - 50.0) + GY * (y - 50.0)


def _fence(fid, pts, closed=False, base=_base):
    return EdgeLine(fid, "fence.obj", tuple(pts), closed, 0.0, 8.0, 0.0, 0.3, 0.0,
                    unit=0, base_ys=tuple(base(x, y) for x, y in pts), panel_m=3.5)


RING = [(20.0, 20.0), (80.0, 20.0), (80.0, 80.0), (20.0, 80.0)]
PAD = box(40.0, 40.0, 60.0, 60.0)
APRON = box(0.0, 100.0, 100.0, 130.0)


class _Dem:
    """A constant ground, or ``z(x, y)`` when given a callable."""

    def __init__(self, z):
        self.zv = z

    def z(self, x, y):
        return self.zv(x, y) if callable(self.zv) else self.zv


def _cells(upper=True, za=0.0):
    ev = {UPPER_Y_KEY: 4.5, UPPER_FLOOR_KEY: 0.0, UPPER_UNIT_KEY: 0.0,
          UPPER_AIR_Z_KEY: za} if upper else {}
    return [Cell(0, "building", "building2", tuple(PAD.exterior.coords)[:-1], (), None, None,
                 "groundside", "building", ev),
            Cell(1, "apron", "pol1", tuple(APRON.exterior.coords)[:-1], (), None, None,
                 "airside", "apron", {})]


def _mint(lines, dem=5.0, upper=True, za=0.0):
    cells = _cells(upper, za)
    out = []

    def add(r, rf, poly, kind, cn=None, cl=None, evidence=None):
        out.append((r, rf, poly, dict(evidence or {})))
    st = fy.mint_fence_yards(types.SimpleNamespace(edge_lines=tuple(lines), dem=_Dem(dem)),
                             cells, LAW, load_rules(), add)
    return out, st, cells


def test_a_fence_round_an_upper_pad_reads_one_plane_and_its_yard():
    out, st, cells = _mint([_fence("unit:0:a#0", RING, closed=True)])
    assert st["fence_yards"] >= 1 and out
    yard = unary_union([p for _r, _f, p, _e in out])
    assert all(r == "groundside_pavement" and f.startswith("fenceyard:")
               and f.endswith(":building2")
               for r, f, _p, _e in out)
    pl = fy._yard_plane_of(out[0][3])
    assert pl[1] == pytest.approx(GX, abs=1e-6) and pl[2] == pytest.approx(GY, abs=1e-6)
    assert out[0][3]["yard_rms"] == pytest.approx(0.0, abs=1e-6)
    # the pad carries its plane too (the planar front reads no late cell)
    assert fy._yard_plane_of(cells[0].evidence) == pl
    # the yard reaches the fence and nothing stands outside it
    assert yard.buffer(1.0).contains(Point(50.0, 21.0)) and yard.contains(Point(30.0, 30.0))
    assert not yard.intersects(Point(10.0, 50.0)) and not yard.intersects(Point(50.0, 90.0))
    assert not yard.intersects(PAD)
    assert Polygon(RING).buffer(1.0).contains(yard)


def test_low_stations_take_no_ground():
    """The west leg stands at its unit's floor (base 0.5): the ground
    nearer it than any upper station is not the yard."""
    def base(x, y):
        return 0.5 if x <= 20.0 else _base(x, y)
    west = _fence("unit:0:w#0", [(20.0, 80.0), (20.0, 20.0)], base=base)
    rest = _fence("unit:0:r#0", [(20.0, 20.0), (80.0, 20.0), (80.0, 80.0), (20.0, 80.0)])
    # the ground follows the fence: low by the west leg, up by the rest
    out, st, _c = _mint([west, rest], dem=lambda x, y: 0.5 if x <= 21.0 else 5.0)
    yard = unary_union([p for _r, _f, p, _e in out])
    assert out and not yard.intersects(Point(22.0, 50.0))
    assert yard.contains(Point(70.0, 50.0))
    assert out[0][3]["yard_upper"] < out[0][3]["yard_stations"]


def test_a_pocket_across_a_shared_fence_is_taken_and_a_corridor_is_not():
    ring = _fence("unit:0:a#0", RING, closed=True)
    east = _fence("unit:0:e#0", [(80.0, 30.0), (120.0, 30.0), (120.0, 70.0), (80.0, 70.0)])
    corridor = _fence("unit:0:c#0", [(20.0, -20.0), (80.0, -20.0)])     # 40 m south
    out, _st, _c = _mint([ring, east, corridor])
    yard = unary_union([p for _r, _f, p, _e in out])
    assert yard.contains(Point(100.0, 50.0))          # the east enclosure: a pocket
    assert not yard.intersects(Point(50.0, 0.0))      # one-sided: chords 40 m, not fenced


@pytest.mark.parametrize("case", ["non_planar", "no_upper_pad", "level_ground"])
def test_doubt_takes_nothing(case):
    def wavy(x, y):
        return _base(x, y) + (1.5 if int(x + y) % 40 < 20 else -1.5)
    line = _fence("unit:0:a#0", RING, closed=True, base=wavy if case == "non_planar" else _base)
    out, st, cells = _mint([line], dem=0.0 if case == "level_ground" else 5.0,
                           upper=case != "no_upper_pad")
    assert out == [] and st["fence_yards"] == 0
    assert fy._yard_plane_of(cells[0].evidence) is None


def test_no_unit_line_reads_nothing():
    dsf = EdgeLine("dsf:line0", "f.fac", tuple(RING), True, 0.0, 2.0, 0.0, 0.3, 0.1)
    out, st, _c = _mint([dsf])
    assert out == [] and st == {"fence_yards": 0, "fence_yard_m2": 0.0}
    assert math.isfinite(_base(0.0, 0.0))


def test_projection_stands_the_yard_on_the_level_less_the_fence_foot_plane():
    """Spec 2068 A2 F3 (``solve/project_yard``): every yard vertex takes
    ``L + plane(x, y) - y_p`` from its level's landing record, the level is
    read and never written, an airside-carried vertex never moves."""
    from auto_patch_v2.solve.project_strip import project_facade_strips
    xy = {0: (0, 0), 1: (10, 0), 2: (10, 10), 3: (0, 10),             # the level
          4: (12, 0), 5: (30, 0), 6: (30, 10), 7: (12, 10),           # the yard
          8: (30, 20), 9: (12, 20)}                                    # an apron
    V = {k: types.SimpleNamespace(xy=(float(x), float(y))) for k, (x, y) in xy.items()}
    F = [("building", "building1/p1", (0, 1, 2, 3)),
         ("groundside_pavement", "fenceyard:0:building2", (4, 5, 6, 7)),
         ("apron", "pol1", (7, 6, 8, 9))]
    plane = (4.0, 0.0, -0.03, 0.0, 0.0)
    pm = types.SimpleNamespace(
        faces={i: types.SimpleNamespace(id=i, role=r, ref=ref, ring=ring, holes=())
               for i, (r, ref, ring) in enumerate(F)},
        vertices=V, ring_vertices=lambda ring: tuple(ring),
        registries=types.SimpleNamespace(landings={"building1/p1": {
            "pad": "building2", "y_p": 4.7, "yard_plane": plane}}))
    z = [38.0] * 4 + [30.0] * 4 + [33.0, 33.0]
    out, rep = project_facade_strips(pm, LAW, z)
    assert out[:4] == tuple(z[:4]) and out[8:] == tuple(z[8:])
    for v in (4, 5):
        assert out[v] == pytest.approx(38.0 + 4.0 - 4.7)
    assert out[6] == 30.0 and out[7] == 30.0            # the apron's: airside is king
    yr = rep["yards"]
    assert yr["vertices"] == 2 and yr["airside"] == 2 and yr["yielded"] == 0


def test_the_yard_edge_stepping_across_its_stand_off_is_a_declared_joint():
    """Spec 2068 A2 F5 (``pipeline/upper_pad_publication``): a run of yard
    edge stepping more than ``visual_m`` to the road across its stand-off is
    a ``wall_terrace`` joint; the level's record carries the yard."""
    from auto_patch_v2.pipeline.upper_pad_publication import upper_pad_records, yard_edge_joints
    xy = {0: (0, 0), 1: (20, 0), 2: (20, 10), 3: (0, 10),             # the yard
          4: (0, -0.5), 5: (20, -0.5), 6: (20, -8), 7: (0, -8),       # a road below it
          8: (30, 0), 9: (40, 0), 10: (40, 10), 11: (30, 10)}         # the level
    V = {k: types.SimpleNamespace(xy=(float(x), float(y)), key=(1e-5 * y, 1e-5 * x),
                                  incident_faces=())
         for k, (x, y) in xy.items()}
    F = [("groundside_pavement", "fenceyard:0:building2", (0, 1, 2, 3)),
         ("service_road", "road1", (4, 5, 6, 7)),
         ("building", "building1/p1", (8, 9, 10, 11))]
    pm = types.SimpleNamespace(
        faces={i: types.SimpleNamespace(id=i, role=r, ref=ref, ring=ring, holes=())
               for i, (r, ref, ring) in enumerate(F)},
        vertices=V, ring_vertices=lambda ring: tuple(ring), road_terrace={},
        registries=types.SimpleNamespace(landings={"building1/p1": {
            "pad": "building2", "y_p": 4.7, "witness": "group_up",
            "yard_plane": (4.0, 0.0, 0.0, 0.0, 0.0)}}))
    z = [37.0] * 4 + [34.0] * 4 + [38.0] * 4
    joints = yard_edge_joints(pm, LAW, z)
    assert len(joints) == 1 and joints[0]["kind"] == "wall_terrace"
    assert joints[0]["height_m"] == pytest.approx(3.0) and joints[0]["pairs"] == 2
    (rec,) = upper_pad_records(pm, LAW, z)
    assert rec["yard"]["faces"] == ["fenceyard:0:building2"] and rec["yard"]["z"] == [37.0, 37.0]


def _ratio_case(dem, za=0.0, floor_run=True):
    """A fence whose west leg stands at the floor (base 0.0) and the rest a
    storey up: G6' reads the DEM at the floor stations (or T4's ``za``)."""
    def base(x, y):
        return 0.0 if x <= 20.0 else _base(x, y)
    lines = [_fence("unit:0:r#0", [(20.0, 20.0), (80.0, 20.0), (80.0, 80.0), (20.0, 80.0)])]
    if floor_run:
        lines.append(_fence("unit:0:w#0", [(20.0, 80.0), (20.0, 20.0)], base=base))
    return _mint(lines, dem=dem, za=za)


@pytest.mark.parametrize("rise, ok", [(4.5, True), (1.35, False), (9.0, False)])
def test_g6_prime_reads_the_ground_at_the_fences_own_stations(rise, ok):
    """Spec 2068 A3 R1: the DEM's rise from the floor stations to the upper
    ones over the fence's own rise is between 0.5 and 1.5 — here 1.0 passes,
    0.3 and 2.0 refuse; the ratio rides the evidence."""
    out, st, _c = _ratio_case(lambda x, y: 10.0 + (0.0 if x <= 21.0 else rise))
    assert bool(out) is ok
    if ok:
        assert out[0][3]["yard_g6_ratio"] == pytest.approx(1.0, abs=0.05)
        assert "yard_dem_m" in out[0][3]
    else:
        assert "ground ratio" in st["fence_yard_refused:building2"]


def test_g6_prime_falls_back_on_the_airside_ground_with_no_floor_run():
    """No floor run: T4's ``za`` and the floor ``t`` stand in for F."""
    out, _st, _c = _ratio_case(14.5, za=10.0, floor_run=False)
    assert out and out[0][3]["yard_g6_ratio"] == pytest.approx(1.0, abs=0.05)
    out, st, _c = _ratio_case(14.5, za=13.0, floor_run=False)
    assert not out and "ground ratio" in st["fence_yard_refused:building2"]


def test_g6_prime_refuses_on_nan():
    out, st, _c = _ratio_case(float("nan"))
    assert not out and st["fence_yards"] == 0


def test_the_plane_never_exceeds_the_pavement_ceiling():
    """Spec 2068 A3 R2: a fence profile falling 12 % gives a plane capped
    at ``[common] pavement_max_grade`` (5 %), or refuses on G5's rms read
    on the capped plane."""
    cap = float(LAW.tables.common.pavement_max_grade)

    def steep(x, y):
        return 4.5 - 0.12 * (y - 50.0)
    out, st, _c = _mint([_fence("unit:0:a#0", RING, closed=True, base=steep)],
                        dem=lambda x, y: steep(x, y) + 1.0)
    if out:
        pl = fy._yard_plane_of(out[0][3])
        assert math.hypot(pl[1], pl[2]) == pytest.approx(cap, abs=1e-9)
    else:
        assert "rms" in st["fence_yard_refused:building2"]


def _road_map(fixed=None, level_z=None, role="service_road"):
    """A 6 m road climbing from an apron edge (x = 0, airside, fixed) to a
    level (x = 60, ``building1/p1``) through a gross yard (x 5..100), and a
    yard face aside; ``fixed`` = ``(z)`` adds a lot corner at (30, 6), a
    standing face that holds that road vertex."""
    xs = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
    xy = {}
    for k, x in enumerate(xs):
        xy[k] = (x, 0.0)
        xy[10 + k] = (x, 6.0)
    road = tuple(range(7)) + tuple(10 + k for k in reversed(range(7)))
    xy.update({30: (-10.0, 0.0), 31: (-10.0, 6.0)})                  # the apron
    xy.update({40: (70.0, 0.0), 41: (70.0, 6.0)})                    # the level
    xy.update({50: (10.0, 30.0), 51: (20.0, 30.0), 52: (20.0, 40.0), 53: (10.0, 40.0)})
    faces = [(role, "road1", road),
             ("apron", "pol1", (30, 0, 10, 31)),
             ("building", "building1/p1", (6, 40, 41, 16)),
             ("groundside_pavement", "fenceyard:0:building2", (50, 51, 52, 53))]
    if fixed is not None:
        xy.update({60: (30.0, 12.0), 61: (40.0, 12.0)})
        faces.append(("parking_lot_x", "lot1", (13, 61, 60)))
    inc: dict = {}
    for i, (_r, _f, ring) in enumerate(faces):
        for v in ring:
            inc.setdefault(v, []).append(i)
    V = {k: types.SimpleNamespace(xy=p, incident_faces=tuple(inc.get(k, ())))
         for k, p in xy.items()}
    hull = ((((5.0, -10.0), (100.0, -10.0), (100.0, 20.0), (5.0, 20.0), (5.0, -10.0)),),)
    pm = types.SimpleNamespace(
        faces={i: types.SimpleNamespace(id=i, role=r if r != "parking_lot_x" else "building",
                                        ref=ref, ring=ring, holes=())
               for i, (r, ref, ring) in enumerate(faces)},
        vertices=V, ring_vertices=lambda ring: tuple(ring),
        registries=types.SimpleNamespace(landings={"building1/p1": {
            "pad": "building2", "y_p": 4.7, "yard_plane": (3.7, 0.0, 0.0, 0.0, 0.0),
            "yard_hull": hull}}))
    z = [0.0] * 70
    for k in range(7):
        z[k] = z[10 + k] = 30.0
    for v in (6, 16, 40, 41):
        z[v] = 40.0 if level_z is None else level_z
    for v in (30, 31):
        z[v] = 30.0
    if fixed is not None:
        z[13] = fixed
    return pm, z


def test_a_road_through_the_yard_climbs_at_the_road_grade_then_lies_on_the_plane():
    """Spec 2068 A3 R5: the free run vertices take the plane (here L - 1)
    clamped to the road grade (0.20) off the fixed apron edge: at g inside
    (plane - entry) / g = 45 m, flush beyond; the level is never a source."""
    from auto_patch_v2.constraints.yard_edge import projected_vertices, yard_runs
    from auto_patch_v2.solve.project_strip import project_facade_strips
    g = float(LAW.tables.emit.road_contact.upper_pad_road_grade)
    pm, z = _road_map(level_z=46.0)              # target L + plane - y_p = 45
    (run,) = yard_runs(pm, LAW)
    assert run.free == frozenset({1, 2, 3, 4, 5, 11, 12, 13, 14, 15})
    assert run.sources == frozenset({0, 10}) and {6, 16} <= run.level_vertices
    assert run.free <= projected_vertices(pm, LAW)
    out, rep = project_facade_strips(pm, LAW, z)
    for k, x in enumerate([10.0, 20.0, 30.0, 40.0, 50.0], start=1):
        assert out[k] == pytest.approx(min(30.0 + g * x, 45.0))
    # the level's own vertices (z 46) are no source: else lo > hi at x 50
    assert rep["yards"]["runs"][0]["infeasible"] == 0
    assert out[6] == 46.0 and out[0] == 30.0


def test_a_lot_through_the_yard_blends_at_the_lot_grade():
    """Owner 2026-11-14T21:42Z "Lots 5%": the same run as a parking lot
    climbs at the lot's own cap (5 %), not the road's 20 %, so its blend
    off the fixed apron edge spreads wider; the census judges it there."""
    from auto_patch_v2.constraints.yard_edge import lot_vertices, run_grade, yard_runs
    from auto_patch_v2.pipeline.publication import yard_run_lifts
    from auto_patch_v2.solve.project_strip import project_facade_strips
    g = run_grade(LAW, "parking_lot")
    assert g == pytest.approx(0.05) and run_grade(LAW, "service_road") == pytest.approx(
        float(LAW.tables.emit.road_contact.upper_pad_road_grade))
    pm, z = _road_map(level_z=46.0, role="parking_lot")
    (run,) = yard_runs(pm, LAW)
    assert lot_vertices(pm, LAW, run) == run.free
    out, rep = project_facade_strips(pm, LAW, z)
    for k, x in enumerate([10.0, 20.0, 30.0, 40.0, 50.0], start=1):
        assert out[k] == pytest.approx(min(30.0 + g * x, 45.0))
    assert rep["yards"]["runs"][0]["infeasible"] == 0
    assert yard_run_lifts(pm, LAW) == {0: pytest.approx(g)}


@pytest.mark.parametrize("fz, level_z, want", [(30.0, 40.0, 31.2), (36.0, 34.0, 34.8)])
def test_a_fixed_vertex_pulls_the_run_both_ways(fz, level_z, want):
    """A run vertex another standing face holds is FIXED: a source whose
    bounds pull its free neighbour 6 m off down (a low corner under a
    target of L - 1 = 39) or up (a high corner over a target of 33)."""
    from auto_patch_v2.solve.project_strip import project_facade_strips
    pm, z = _road_map(fixed=fz, level_z=level_z)
    out, rep = project_facade_strips(pm, LAW, z)
    assert out[13] == fz and out[3] == pytest.approx(want)
    assert rep["yards"]["runs"][0]["infeasible"] == 0
