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


def test_a_proud_wall_is_capped_at_what_it_retains(monkeypatch):
    from auto_patch_v2.airport import sunken_ramp
    monkeypatch.setattr(sunken_ramp, "_member_tris", lambda *a, **k: _tris())
    # 21 m solid, top at +6, retaining only the 15 m under its zero: the
    # upper ground is AT the zero and the 6 m above it is a parapet
    comp = types.SimpleNamespace(seat_z=280.0, member=object(), origin=(0.0, 0.0),
                                 height_m=21.0, retained_m=15.0, top_y=6.0)
    a = np.asarray(WT.top_profile(comp, WALL, _upper_face(), None), float)
    assert float(a[:, 1].max()) == 280.0
    full = types.SimpleNamespace(seat_z=280.0, member=object(), origin=(0.0, 0.0),
                                 height_m=21.0, retained_m=21.0, top_y=6.0)
    assert float(np.asarray(WT.top_profile(full, WALL, _upper_face(), None))[:, 1].max()) > 285.9


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


def test_a_station_that_retains_no_hill_takes_no_top():
    face = _upper_face()
    half = face.length / 2.0
    prof = ((0.0, None), (half - 1.0, None), (half, 290.0), (face.length, 290.0))
    lines = [_line(prof)]
    p_end = face.interpolate(1.0).coords[0]
    p_mid = face.interpolate(half + 20.0).coords[0]
    assert WZ.face_top(lines, p_end) is None
    assert WZ.face_top(lines, p_mid) == 290.0


def test_the_lower_level_round_the_end_withdraws_the_top():
    class _Dem:
        # the upper ground 300 m, except past y = 50 where the lower level
        # (280 m) wraps round the wall's end
        def z_many(self, xs, ys):
            return np.where(np.asarray(ys, float) > 50.0, 280.0, 300.0)
    face = _upper_face()
    prof = tuple((float(s), 300.0) for s in np.arange(0.0, face.length + 1.0, 10.0))
    got = WS._retaining_stations(_Dem(), face, prof, 20.0, 20.0)
    for s, z in got:
        y = face.interpolate(s).y
        assert (z is None) == (y > 50.0)


def test_the_slope_is_the_upper_band_no_region_holds():
    up = box(40.0, -100.0, 60.0, 100.0)
    w = WS.WallSides(WALL, 20.0, 20.0, up, box(65.0, -100.0, 85.0, 100.0), 6.0, "w",
                     WALL.buffer(-0.5), _upper_face(), ((0.0, 290.0), (200.0, 290.0)))
    got = wall_slopes([w], [box(30.0, 50.0, 70.0, 120.0)], [], 1.0, 0.02)
    assert len(got) == 1 and is_wall_slope_ref(got[0][0])
    assert got[0][0].startswith(WALL_SLOPE_REF_PREFIX)
    assert abs(got[0][1].area - 20.0 * 150.0) < 1.0
    unread = WS.WallSides(WALL, 20.0, 20.0, up, None, 6.0, "w", None, _upper_face(), None)
    assert wall_slopes([unread], [], [], 1.0, 0.02) == []
    # a road past the wall's end keeps its stand-off: no shared vertex
    road = box(30.0, -120.0, 70.0, -110.0)
    got = wall_slopes([w], [], [road], 15.0, 0.02)
    assert got and all(g.distance(road) >= 15.0 - 1e-6 for _r, g in got)


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
    tops = RR._wall_levels(pm, lines, xy)
    assert set(tops) == {1}
    assert abs(tops[1][0] - 288.0) < 0.05 and tops[1][1] == RR.WALL_TOP_RULING


# --- #1662: the low side meets the wall's foot -------------------------------

def _lower_face() -> LineString:
    a, b = WS._wall_faces(WALL)
    return b if abs(a.coords[0][0] - 60.0) < 1e-9 else a


def _east_tris():
    """The wall's EAST (lower) face: its bottom edge at y_auth -15, plus a
    footing deeper still under the west (upper) side that is never read."""
    top = [(65.0, -100.0, 0.0), (65.0, 100.0, 0.0)]
    bot = [(65.0, -100.0, -15.0), (65.0, 100.0, -15.0)]
    deep = [(60.0, -100.0, -30.0), (60.0, 100.0, -30.0), (62.0, 0.0, -30.0)]
    return np.array([[top[0], top[1], bot[0]], [bot[0], top[1], bot[1]], deep], float)


def test_the_foot_is_the_bottom_edge_on_the_lower_face(monkeypatch):
    from auto_patch_v2.airport import sunken_ramp
    monkeypatch.setattr(sunken_ramp, "_member_tris", lambda *a, **k: _east_tris())
    comp = types.SimpleNamespace(seat_z=300.0, member=object(), origin=(0.0, 0.0))
    a = np.asarray(WT.foot_profile(comp, WALL, _lower_face(), None), float)
    assert np.allclose(a[:, 1], 285.0)          # the footing under the hill unread


def test_a_buried_bottom_rises_to_the_real_ground_past_the_smear():
    class _Dem:
        # the real lower ground 290 m, past y = 50 288 m (under the bottom)
        def z_many(self, xs, ys):
            return np.where(np.asarray(ys, float) > 50.0, 288.0, 290.0)
    face = _lower_face()
    prof = tuple((float(s), 289.0) for s in np.arange(0.0, face.length + 1.0, 10.0))
    for s, z in WS._foot_on_ground(_Dem(), face, prof, 10.0):
        y = face.interpolate(s).y
        assert z == (289.0 if y > 50.0 else 290.0)


def test_only_the_lower_face_takes_the_foot():
    face = _lower_face()
    line = WZ.RetainingLine(WALL, 80.0, 20.0, {}, _upper_face(), None, face,
                            ((0.0, 289.5), (face.length, 289.5)))
    assert WZ.face_foot([line], (65.0, 0.0)) == 289.5
    assert WZ.face_foot([line], (65.6, 10.0)) == 289.5      # snapped near it
    assert WZ.face_foot([line], (60.0, 0.0)) is None         # the upper face
    assert WZ.face_foot([line], (75.0, 0.0)) is None         # out on the low side


def test_the_foot_strip_is_the_lower_band_no_region_holds():
    up, lo = box(40.0, -100.0, 60.0, 100.0), box(65.0, -100.0, 85.0, 100.0)
    w = WS.WallSides(WALL, 20.0, 20.0, up, lo, 6.0, "w", WALL.buffer(-0.5),
                     _upper_face(), None, _lower_face(), ((0.0, 289.5), (200.0, 289.5)))
    pad = box(70.0, -100.0, 90.0, 100.0)        # a pad 5 m past the foot
    got = wall_slopes([w], [], [pad], 1.0, 0.02)
    assert len(got) == 1 and is_wall_slope_ref(got[0][0])
    g = got[0][1]
    assert abs(g.area - 4.0 * 200.0) < 1.0 and g.distance(pad) >= 1.0 - 1e-6


def test_a_slope_vertex_on_the_lower_face_is_held_at_the_foot():
    face = _lower_face()
    lines = [WZ.RetainingLine(WALL, 80.0, 20.0, {}, _upper_face(),
                              ((0.0, 301.0), (200.0, 301.0)), face,
                              ((0.0, 289.0), (face.length, 291.0)))]
    slope = types.SimpleNamespace(ref=f"{WALL_SLOPE_REF_PREFIX}w#1")
    vx = {1: types.SimpleNamespace(incident_faces=(0,)),
          2: types.SimpleNamespace(incident_faces=(0,))}
    pm = types.SimpleNamespace(vertices=vx, faces={0: slope})
    got = RR._wall_levels(pm, lines, {1: (65.0, 0.0), 2: (60.0, 0.0)})
    assert got[1][1] == RR.WALL_FOOT_RULING and abs(got[1][0] - 290.0) < 0.05
    assert got[2] == (301.0, RR.WALL_TOP_RULING)


def test_the_strip_corner_at_the_walls_end_takes_the_foot():
    face = _lower_face()
    line = WZ.RetainingLine(WALL, 80.0, 20.0, {}, _upper_face(), None, face,
                            ((0.0, 289.5), (face.length, 289.5)))
    # 0.3 m off the lower face, 0.2 m past the wall's south end
    assert WZ.face_foot([line], (65.3, -100.2)) == 289.5
