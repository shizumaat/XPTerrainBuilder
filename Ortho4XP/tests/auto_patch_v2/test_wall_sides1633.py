"""#1633 round 3 twins: a route or road that meets a retaining wall is two
roads; the wall is the step; the band stops short of the wall's back.

A synthetic wall 5 m thick along x = 60..65 (y -100..100), 20 m retained:
the upper level west of it, the lower level east (``airport/wall_sides``).
"""
from __future__ import annotations

import types

import numpy as np
import pytest
from shapely.geometry import LineString, Point, Polygon, box

from auto_patch_v2.airport import wall_sides as WS
from auto_patch_v2.airport.road_profile import ROUTE, RoadProfiles, Way
from auto_patch_v2.airport.road_ramp import merge_routes
from auto_patch_v2.law import Law

WALL = box(60.0, -100.0, 65.0, 100.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


class _StepDem:
    """Upper ground 300 m west of the wall, lower 280 m east, and the lidar
    SMEAR: a linear blend over 10 m either side of the wall."""

    def z_many(self, xs, ys):
        xs = np.asarray(xs, float)
        t = np.clip((xs - 50.0) / 25.0, 0.0, 1.0)
        return 300.0 - 20.0 * t

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


def _walls():
    a, b = WS.wall_faces(WALL)
    up = box(40.0, -100.0, 60.0, 100.0)
    lo = box(65.0, -100.0, 85.0, 100.0)
    return (WS.WallSides(WALL, 20.0, 20.0, up, lo, 6.8, "synthetic",
                         WALL.buffer(-0.5)),)


def test_the_two_faces_of_a_thin_wall():
    a, b = WS.wall_faces(WALL)
    assert {round(a.length), round(b.length)} == {200}
    bent = Polygon([(0, 0), (100, 0), (100, 50), (95, 50), (95, 5), (0, 5)])
    f = WS.wall_faces(bent)
    assert f is not None and abs(f[0].length - f[1].length) < 12.0


def test_the_upper_face_is_the_high_ground():
    comp = types.SimpleNamespace(retains=True, retained_m=20.0, height_m=20.0,
                                 pieces=(WALL,), top_y=6.8, resource="w")
    ap = types.SimpleNamespace(dem=_StepDem(), partition=object())
    cfg = types.SimpleNamespace(retaining_wall_clear_step_m=2.0)
    (w,) = WS.wall_sides(ap, cfg, [comp])
    assert w.upper.centroid.x < 60.0 < 65.0 < w.lower.centroid.x
    assert w.smear == 20.0 and w.side_of((55.0, 0.0)) == "upper"


def test_a_road_is_never_on_both_sides_of_a_wall():
    """§1 (1): the road band that ran round the wall's end and on to its
    back (the 27R trench) is cut back: no road inside the footprint or in
    the upper band; its own (lower) side stands."""
    road = box(50.0, -120.0, 75.0, 120.0)          # mostly lower + ends
    road = road.union(box(62.0, -120.0, 75.0, 120.0)).difference(box(40, -100, 55, 100))
    kept = WS.far_side_cut(road, _walls())
    assert kept.intersection(WALL).area < 1e-6
    assert kept.intersection(box(40.0, -100.0, 60.0, 100.0)).area < 1e-6
    assert kept.intersection(box(65.0, -100.0, 75.0, 100.0)).area == pytest.approx(10 * 200)


def test_the_cells_and_the_centreline_are_cut_at_one_site():
    from auto_patch_v2.classify.roles import Cell, CutLine
    from auto_patch_v2.classify.wall_cutback import cut_lines_at_walls, cut_roads_at_walls
    ring = tuple(box(56.0, -120.0, 75.0, 120.0).exterior.coords)[:-1]
    cells = [Cell(0, "service_road", "route1", ring, (), None, None,
                  "groundside", "service_road", {}),
             Cell(1, "apron", "pav1", ring, (), None, None, "airside", "apron", {})]
    out, st = cut_roads_at_walls(cells, {"service_road"}, _walls(), 1.0)
    road = [c for c in out if c.role == "service_road"]
    assert st["wall_cut_cells"] == 1 and [c.id for c in out] == list(range(len(out)))
    assert all(not WALL.buffer(-0.1).contains(Point(p)) and not
               box(40.0, -100.0, 60.0, 100.0).buffer(-0.1).contains(Point(p))
               for c in road for p in c.ring)
    assert any(c.role == "apron" and c.ring == ring for c in out)   # roads only
    # route U: along the upper level, INTO the wall's end, inside it, out
    # on the lower side — three parts, the inside one dropped
    line = CutLine("road_centerline", "route7",
                   ((0.0, -110.0), (62.0, -110.0), (62.0, -60.0), (70.0, -50.0), (70.0, 90.0)))
    parts, ls = cut_lines_at_walls([line], _walls())
    assert ls["wall_cut_lines"] == 1 and len(parts) == 2
    assert all(not LineString(p.points).intersects(WALL.buffer(-0.01)) for p in parts)


def _way(ref, xs, ys, z):
    xy = np.column_stack([xs, ys]).astype(float)
    s = np.r_[0.0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
    return Way(ROUTE, ref, xy, s, np.full(len(xy), z), np.full(len(xy), z))


def test_a_way_never_answers_across_the_wall():
    """§1 (3): the foot road (east of the wall) answers its own side only —
    a vertex on the wall's back reads the upper way, never the foot one,
    even when the foot way runs THROUGH its face (radius ``inf``)."""
    foot = _way("foot", [67.0, 67.0], [-90.0, 90.0], 280.0)
    top = _way("top", [45.0, 45.0], [-90.0, 90.0], 299.0)
    prof = RoadProfiles(0.08, 5.0, 3.0, 8.0, (foot, top), walls=_walls())
    a = prof.answer((58.0, 0.0), 297.0, [(foot, float("inf"))])
    assert a.way is None or a.way.ref == "top"
    assert prof.answer((66.0, 0.0), 281.0).way.ref == "foot"
    # a vertex ON the face is its own side's
    assert prof.answer((65.0, 0.0), 281.0).way.ref == "foot"


def test_two_ways_across_a_wall_are_never_one_carriageway():
    foot = _way("foot", np.linspace(66, 66, 21), np.linspace(-90, 90, 21), 280.0)
    top = _way("top", np.linspace(59, 59, 21), np.linspace(-80, 80, 21), 299.0)
    raw, xy = {}, {}
    for k, (w, r) in enumerate(((foot, 0), (top, 1))):
        for i, (x, y) in enumerate(w.xy):
            raw[k * 100 + i] = (r, float(w.s[i]), 0.0)
            xy[k * 100 + i] = (float(x), float(y))
    assert merge_routes((foot, top), raw, xy, 7.5, 10.0, 3.0)[0]       # control
    assert merge_routes((foot, top), raw, xy, 7.5, 10.0, 3.0, _walls()) == ({}, [])


def test_the_road_beside_the_wall_reads_past_the_smear():
    """§2: at the foot the smeared DEM reads 296 m 2 m from the wall; the
    station reads the lower ground past the smear (280 m) — and mirrored on
    the upper side, the upper ground (300 m), never across the wall."""
    dem = _StepDem()
    smp = WS.smear_sampler(dem.z_many, _walls())
    z = smp(np.array([67.0, 58.0, 100.0]), np.array([0.0, 0.0, 0.0]))
    assert dem.z(67.0, 0.0) > 285.0 and z[0] == pytest.approx(280.0)
    assert dem.z(58.0, 0.0) < 300.0 and z[1] == pytest.approx(300.0)
    assert z[2] == pytest.approx(280.0)


def test_the_wall_top_as_seated():
    (w,) = _walls()
    assert WS.top_z(w, 280.0, 300.0) == pytest.approx(286.8)
    assert WS.top_z(w._replace(top_y=None) if hasattr(w, "_replace")
                    else __import__("dataclasses").replace(w, top_y=None),
                    280.0, 300.0) == 300.0


def test_the_band_stops_smear_short_of_the_wall(law):
    """§3 (2): a runway 40 m from a wall's upper face — its band ends 20 m
    (the smear) short of the face; a wall AT the pavement edge keeps the
    band to the wall (#1139's plane is ``wall_zone``'s)."""
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.planar.zones import zone_regions
    pav = ((-40.0, -500.0), (0.0, -500.0), (0.0, 500.0), (-40.0, 500.0))
    cells = (Cell(0, "runway", "09/27", pav, (), 4, None, "airside", "runway", {}),)
    def reach(walls, probe=box(0.0, -90.0, 39.9, 90.0)):
        regs = zone_regions(cells, law, (), None, (), None,
                            wall_setbacks=WS.band_setbacks(walls))
        got = [r.polygon.intersection(probe) for r in regs]
        return max(g.bounds[2] for g in got if not g.is_empty)
    edge = reach(())
    assert edge == pytest.approx(39.9)                  # control: to the wall
    far = WS.WallSides(box(40.0, -100, 45.0, 100), 20.0, 20.0, box(20.0, -100, 40.0, 100),
                       box(45.0, -100, 65.0, 100), 6.8, "far", None)
    assert reach((far,)) == pytest.approx(20.0, abs=0.05)
    near = WS.WallSides(box(3.0, -100, 8.0, 100), 20.0, 20.0, box(0.0, -100, 3.0, 100),
                        box(8.0, -100, 28.0, 100), 6.8, "near", None)
    assert reach((near,)) == pytest.approx(edge)


def test_a_chord_from_the_wall_line_crosses_it():
    """§4: a chord whose END lies on a declared wall line is forgiven its
    declared step (the muro_concreto5 outline vertex, 10.28 m over 10.66)."""
    import importlib
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    cg = importlib.import_module("check_grade")
    d = cg.DeclaredWallSteps.__new__(cg.DeclaredWallSteps)
    d.joints = [([(0.0, 0.0), (0.0, 100.0)], 10.66)]
    d._index = cg._JointSegments(d.joints)
    assert d.allowance(0.02, 50.0, 5.0, 50.0) == pytest.approx(10.66)   # on the line
    assert d.allowance(-2.0, 50.0, 3.0, 50.0) == pytest.approx(10.66)   # across
    assert d.allowance(0.8, 50.0, 5.0, 50.0) == 0.0                      # beside it
