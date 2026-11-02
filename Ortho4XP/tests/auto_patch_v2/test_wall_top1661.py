"""#1661 twins: the hill over a retaining wall grades to the wall's top as it
sits (owner RULINGS 2026-10-29a Q299 (a)).

A synthetic wall 5 m thick along x = 60..65 (y -100..100): the upper level
west of it (``tests/auto_patch_v2/test_wall_sides1633.py``'s wall), its top
edge rising along its length the way a pack wall's does.
"""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import wall_sides as WS
from auto_patch_v2.airport import wall_top as WT
from auto_patch_v2.constraints import road_ramp as RR
from auto_patch_v2.constraints import wall_zone as WZ
from auto_patch_v2.model.wall_reach import WALL_SLOPE_REF_PREFIX, is_wall_slope_ref
from auto_patch_v2.planar.wall_slope import wall_slopes
from shapely.geometry import LineString, Point, box

WALL = box(60.0, -100.0, 65.0, 100.0)


def _upper_face() -> LineString:
    a, b = WS._wall_faces(WALL)
    return a if abs(a.coords[0][0] - 60.0) < 1e-9 else b


def _tris():
    """The wall's west face as two triangles whose top runs y_auth 0 -> 6
    from y = -100 to y = 100, plus a footing far below (never the top)."""
    top = [(60.0, -100.0, 0.0), (60.0, 100.0, 6.0)]
    bot = [(60.0, -100.0, -15.0), (60.0, 100.0, -15.0)]
    return np.array([[top[0], top[1], bot[0]], [bot[0], top[1], bot[1]]], float)


def test_the_top_follows_the_object_edge(monkeypatch):
    from auto_patch_v2.airport import sunken_ramp
    monkeypatch.setattr(sunken_ramp, "_member_tris", lambda *a, **k: _tris())
    comp = types.SimpleNamespace(seat_z=280.0, member=object(), origin=(0.0, 0.0))
    face = _upper_face()
    prof = WT.top_profile(comp, WALL, face, None)
    a = np.asarray(prof, float)
    z0 = float(np.interp(face.project(Point(60.0, -100.0)), a[:, 0], a[:, 1]))
    z1 = float(np.interp(face.project(Point(60.0, 100.0)), a[:, 0], a[:, 1]))
    assert {round(z0, 1), round(z1, 1)} == {280.0, 286.0}
    mid = float(np.interp(face.length / 2.0, a[:, 0], a[:, 1]))
    assert abs(mid - 283.0) < 0.1


def test_no_seat_no_top():
    comp = types.SimpleNamespace(seat_z=None, member=object(), origin=(0.0, 0.0))
    assert WT.top_profile(comp, WALL, _upper_face(), None) is None


def _line(prof):
    return WZ.RetainingLine(WALL, 80.0, 20.0, {}, _upper_face(), prof)


def test_only_the_upper_face_takes_the_top():
    face = _upper_face()
    prof = ((0.0, 290.0), (face.length, 290.0))
    lines = [_line(prof)]
    assert WZ.face_top(lines, (60.0, 0.0)) == 290.0
    assert WZ.face_top(lines, (59.4, 10.0)) == 290.0         # snapped near it
    assert WZ.face_top(lines, (65.0, 0.0)) is None           # the lower face
    assert WZ.face_top(lines, (55.0, 0.0)) is None           # out on the hill
    assert WZ.face_top([_line(None)], (60.0, 0.0)) is None   # no top read


def test_the_slope_is_the_upper_band_no_region_holds():
    up = box(40.0, -100.0, 60.0, 100.0)
    w = WS.WallSides(WALL, 20.0, 20.0, up, box(65.0, -100.0, 85.0, 100.0), 6.0, "w",
                     WALL.buffer(-0.5), _upper_face(), ((0.0, 290.0), (200.0, 290.0)))
    got = wall_slopes([w], [box(30.0, 50.0, 70.0, 120.0)], 0.02)
    assert len(got) == 1 and is_wall_slope_ref(got[0][0])
    assert got[0][0].startswith(WALL_SLOPE_REF_PREFIX)
    assert abs(got[0][1].area - 20.0 * 150.0) < 1.0
    unread = WS.WallSides(WALL, 20.0, 20.0, up, None, 6.0, "w", None, _upper_face(), None)
    assert wall_slopes([unread], [], 0.02) == []


def test_a_slope_vertex_on_the_face_is_held_at_the_top():
    face = _upper_face()
    lines = [_line(((0.0, 284.0), (face.length, 292.0)))]
    slope = types.SimpleNamespace(ref=f"{WALL_SLOPE_REF_PREFIX}w#0")
    band = types.SimpleNamespace(ref="adjacent_ground:runway:4:zone2#1")
    vx = {1: types.SimpleNamespace(incident_faces=(0,)),          # face, slope only
          2: types.SimpleNamespace(incident_faces=(0, 1)),        # face, band too
          3: types.SimpleNamespace(incident_faces=(0,))}          # hill edge
    pm = types.SimpleNamespace(vertices=vx, faces={0: slope, 1: band})
    xy = {1: (60.0, 0.0), 2: (60.0, 50.0), 3: (40.0, 0.0)}
    tops = RR._wall_tops(pm, lines, xy)
    assert set(tops) == {1}
    assert abs(tops[1] - 288.0) < 0.05
