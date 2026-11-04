"""#1600 twins: the back of a retaining wall is buried — its footprint is
graded ground held at the wall's top, less the slot along its lower face
where the mesh makes the step (owner RULINGS 2026-10-29a Q299 (a)).

The synthetic wall of ``test_wall_top1661.py``: 5 m thick along
x = 60..65 (y -100..100), the upper level west of it, the lower east.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import wall_sides as WS
from auto_patch_v2.constraints import road_ramp as RR
from auto_patch_v2.constraints import wall_zone as WZ
from auto_patch_v2.model.wall_reach import FILL_SLOT_M, WALL_SLOPE_REF_PREFIX
from auto_patch_v2.planar.wall_slope import wall_slopes
from shapely.geometry import box

WALL = box(60.0, -100.0, 65.0, 100.0)


def _faces():
    a, b = WS._wall_faces(WALL)
    return (a, b) if abs(a.coords[0][0] - 60.0) < 1e-9 else (b, a)


def _sides(top):
    up, lo = _faces()
    return WS.WallSides(WALL, 20.0, 20.0, box(40.0, -100.0, 60.0, 100.0),
                        box(65.0, -100.0, 85.0, 100.0), 6.0, "w", WALL.buffer(-0.5),
                        up, top, lo, None)


def _line(top):
    up, lo = _faces()
    return WZ.RetainingLine(WALL, 80.0, 20.0, {}, up, top, lo, None)


def test_the_fill_is_the_footprint_less_the_lower_slot():
    got = wall_slopes([_sides(((0.0, 300.0), (200.0, 300.0)))], [], [], 1.0, 0.02)
    fill = [g for _r, g in got if g.within(WALL.buffer(1e-6))]
    assert len(fill) == 1 and all(r.startswith(WALL_SLOPE_REF_PREFIX) for r, _g in got)
    assert abs(fill[0].area - (5.0 - FILL_SLOT_M) * 200.0) < 1.0
    assert fill[0].bounds[2] <= 65.0 - FILL_SLOT_M + 1e-6      # off the lower face


def test_no_retained_hill_no_fill():
    none = ((0.0, None), (200.0, None))
    assert not [g for _r, g in wall_slopes([_sides(none)], [], [], 1.0, 0.02)
                if g.within(WALL.buffer(1e-6))]


def test_the_fill_stands_off_a_cell_beside_the_wall():
    plateau = box(40.0, -100.0, 60.0, 100.0)        # a plateau at the upper face
    got = wall_slopes([_sides(((0.0, 300.0), (200.0, 300.0)))], [], [plateau], 1.0, 0.02)
    fill = [g for _r, g in got if g.within(WALL.buffer(1e-6))]
    assert fill and all(g.distance(plateau) >= 1.0 - 1e-6 for g in fill)


def test_a_fill_vertex_off_both_faces_is_held_at_the_top():
    lines = [_line(((0.0, 300.0), (100.0, None), (200.0, 302.0)))]
    assert abs(WZ.fill_top(lines, (62.5, 0.0)) - 301.0) < 1e-6   # a lid over the gap
    assert WZ.fill_top(lines, (60.5, 0.0)) is None     # the upper face: face_top's
    assert WZ.fill_top(lines, (64.8, 0.0)) is None     # in the slot
    assert WZ.fill_top(lines, (50.0, 0.0)) is None     # out on the hill
    assert WZ.fill_top([_line(((0.0, None), (200.0, None)))], (62.5, 0.0)) is None


def test_only_slope_vertices_in_the_fill_are_held():
    lines = [_line(((0.0, 300.0), (200.0, 300.0)))]
    fill = types.SimpleNamespace(ref=f"{WALL_SLOPE_REF_PREFIX}w#2")
    pad = types.SimpleNamespace(ref="building7")
    vx = {1: types.SimpleNamespace(incident_faces=(0,)),
          2: types.SimpleNamespace(incident_faces=(0, 1))}
    pm = types.SimpleNamespace(vertices=vx, faces={0: fill, 1: pad})
    got = RR._wall_levels(pm, lines, {1: (63.0, 0.0), 2: (62.0, 10.0)})
    assert got == {1: (300.0, RR.WALL_TOP_RULING)}
