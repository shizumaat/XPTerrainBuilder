"""Twin of ``planar/covered_ground`` (issue #714): the ground over a mapped
bore under airside pavement is the ground BESIDE the cover.

Synthetic: a 300 m field with a walled 80 m-wide, 20 m-deep cut along the
y axis (a bare-earth DEM's view of a covered freeway), the bore mapped
``tunnel=yes`` from y = -100 to +100, a runway across it at |y| <= 25."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import load_default
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.covered_ground import covered_ground

LAW = load_default()


class _Dem:
    def __init__(self, cut_depth: float, half_width: float = 40.0):
        self.cut, self.half = cut_depth, half_width

    def z_many(self, xs, ys):
        xs = np.asarray(xs, dtype=float)
        return np.where(np.abs(xs) < self.half, 300.0 - self.cut, 300.0)

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


def _runway() -> Cell:
    ring = ((-500.0, -25.0), (500.0, -25.0), (500.0, 25.0), (-500.0, 25.0))
    return Cell(1, "runway", "10/28", ring, (), 4, "E", "airside", "runway", {})


def _airport(dem, tags=None):
    bore = OsmWay(-1, "big_roads", ((0.0, -100.0), (0.0, 100.0)), False,
                  tags or {"highway": "motorway", "tunnel": "yes", "lanes": "5",
                           "layer": "-1", "covered": "yes"})
    return types.SimpleNamespace(dem=dem, osm_ways=(bore,))


def _cls():
    return Classification((_runway(),), (), {}, ())


def _run(dem, xs, ys, tags=None):
    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    return covered_ground(_airport(dem, tags), _cls(), LAW, xs, ys, dem.z_many(xs, ys))


def test_the_runway_over_the_cut_takes_the_ground_beside_it():
    xs = np.arange(-60.0, 61.0, 5.0)
    z, rep = _run(_Dem(20.0), xs, np.zeros_like(xs))
    assert np.allclose(z, 300.0), z            # no vertex keeps the 280 m floor
    assert rep.vertices_lifted == int((np.abs(xs) < 40.0).sum())
    assert abs(rep.max_lift_m - 20.0) < 1e-6
    assert rep.bores == ["-1"] and rep.rings


def test_the_open_cut_beyond_the_mouth_is_never_touched():
    z, rep = _run(_Dem(20.0), [0.0, 10.0], [130.0, 160.0])
    assert np.allclose(z, 280.0) and rep.vertices_lifted == 0


def test_a_dem_that_sees_the_cover_moves_nothing():
    xs = np.arange(-60.0, 61.0, 5.0)
    z, rep = _run(_Dem(0.0), xs, np.zeros_like(xs))
    assert np.allclose(z, 300.0) and rep.vertices_lifted == 0 and not rep.rings


def test_a_bore_under_no_airside_pavement_is_not_read():
    dem = _Dem(20.0)
    xs = np.array([0.0])
    ap = _airport(dem)
    ap.osm_ways = (OsmWay(-1, "big_roads", ((0.0, 200.0), (0.0, 400.0)), False,
                          {"highway": "motorway", "tunnel": "yes"}),)
    z, rep = covered_ground(ap, _cls(), LAW, xs, np.array([300.0]), dem.z_many(xs, [300.0]))
    assert np.allclose(z, 280.0) and not rep.rings


def test_an_untagged_road_is_not_a_bore():
    xs = np.array([0.0])
    z, rep = _run(_Dem(20.0), xs, np.array([0.0]), tags={"highway": "motorway"})
    assert np.allclose(z, 280.0) and not rep.rings


def test_a_dip_shallower_than_the_mouth_depth_is_not_a_road_floor():
    # the least a real road floor stands under the surface over it is the
    # mouth depth (7.5 m); a 4 m dip is the DEM's own read of the cover
    assert LAW.tables.structures.tunnel.mouth_depth_m > 4.0
    xs = np.arange(-60.0, 61.0, 5.0)
    z, rep = _run(_Dem(4.0), xs, np.zeros_like(xs))
    assert rep.vertices_lifted == 0 and not rep.rings
    assert np.allclose(z, np.where(np.abs(xs) < 40.0, 296.0, 300.0))


def test_the_open_cut_beside_the_pavement_keeps_the_dem():
    # a vertex over the cut but off the airside pavement (|y| > 25 m, still
    # inside the covered chain) is the open cut's, not the deck's
    z, rep = _run(_Dem(20.0), [0.0, 0.0], [10.0, 60.0])
    assert np.allclose(z, [300.0, 280.0])


class _TwoCuts(_Dem):
    """Two 20 m-deep cut stretches (|y| in [400, 600]) 800 m apart, flat
    ground (the DEM sees the bored tunnel's cover) between them."""

    def z_many(self, xs, ys):
        xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
        cut = (np.abs(xs) < self.half) & (np.abs(ys) >= 400.0) & (np.abs(ys) <= 600.0)
        return np.where(cut, 300.0 - self.cut, 300.0)


def test_flat_ground_between_two_cut_stretches_is_not_covered_ground():
    # #1996 (EFHK Ring Rail): the bore reads a cut only at its two ends;
    # the pavement over the middle stands on the DEM and is never lifted
    # by an interpolation across the kilometre between them
    dem = _TwoCuts(20.0)
    ap = types.SimpleNamespace(dem=dem, osm_ways=(OsmWay(
        -1, "big_roads", ((0.0, -600.0), (0.0, 600.0)), False,
        {"highway": "motorway", "tunnel": "yes", "lanes": "5"}),))
    ring = ((-500.0, -700.0), (500.0, -700.0), (500.0, 700.0), (-500.0, 700.0))
    cl = Classification((Cell(1, "runway", "10/28", ring, (), 4, "E", "airside",
                              "runway", {}),), (), {}, ())
    # the middle sits 20 m lower than its DEM to prove a lift would show
    xs = np.array([0.0, 0.0, 0.0])
    ys = np.array([0.0, 500.0, -500.0])
    z0 = dem.z_many(xs, ys) - np.array([20.0, 0.0, 0.0])
    z, rep = covered_ground(ap, cl, LAW, xs, ys, z0)
    assert z[0] == z0[0]                       # the middle is not covered
    assert np.allclose(z[1:], 300.0)           # both cut stretches are
    assert rep.bores == ["-1"]


def test_a_single_dropped_station_is_one_run():
    from auto_patch_v2.planar.covered_ground import section_runs
    S = types.SimpleNamespace
    runs = section_runs([S(s=0.0), S(s=5.0), S(s=15.0), S(s=20.0)])
    assert [len(r) for r in runs] == [4]
    runs = section_runs([S(s=0.0), S(s=5.0), S(s=20.0), S(s=25.0), S(s=40.0)])
    assert [len(r) for r in runs] == [2, 2]    # a lone station reads nothing


def test_a_portal_face_with_no_run_in_reach_reads_the_dem():
    # planar/structure_mouth.face_top_z: the ground beside the cover is the
    # run's nearest the mouth, only where it reaches the mouth (#1996)
    from auto_patch_v2.planar.structure_approach import chains
    from auto_patch_v2.planar.structure_mouth import face_top_z
    dem = _TwoCuts(20.0)
    bore = chains([OsmWay(-1, "big_roads", ((0.0, -600.0), (0.0, 600.0)), False,
                          {"highway": "motorway", "tunnel": "yes", "lanes": "5"})])[0]
    ap = types.SimpleNamespace(dem=dem)
    members = [types.SimpleNamespace(bore=bore)]
    assert face_top_z(ap, LAW, members, (0.0, 0.0), 280.0) == 280.0
    assert abs(face_top_z(ap, LAW, members, (0.0, 600.0), 280.0) - 300.0) < 1e-6
