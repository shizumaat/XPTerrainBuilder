"""M3c twins — THE CORE SMOOTHS FIRST (RULINGS 2026-09-04t-4):

* the law's ``emit.road_profile`` constants ARE the core's own;
* the adapter reproduces the core's clamp (``clamp_road_network``) and
  its lateral answer (``Levelled_Roads.answer``) on a synthetic DEM;
* a lawful road follows the core profile EXACTLY (no row binds, the
  roughness term adds nothing); a lot over ITS cap after the core's
  8 % smoothing triggers v2's rows and moves off the profile;
* a road page with no centreline gets its own axis; a lot beside no
  road keeps the DEM and is counted;
* the tile's ``road_grade_limit`` reaches the clamp.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import pytest

from auto_patch_v2.airport import road_profile as rp
from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.airport import (Airport, OsmWay, Runway, RunwayEnd,
                                         SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve import solve_design
from auto_patch_v2.verify.roads import road_profile_agreement


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


# ── 1. the law mirrors the core ──────────────────────────────────────────

def test_law_road_profile_constants_are_the_cores(law):
    import O4_Cfg_Vars as CFG
    VECT = rp._core_vector_utils()
    t = law.tables.emit.road_profile
    assert t.station_m == VECT.DEFAULT_ROAD_STATION_M
    assert t.lane_width_m == CFG.cfg_vars["lane_width"]["default"]
    lr = VECT.Levelled_Roads(0.08, t.lane_width_m)
    assert t.answer_radius_lane_widths * t.lane_width_m == lr.radius_m
    # ONE constant, not two: the core's cap default is the road role's cap
    assert role_cap(law, "service_road").longitudinal == \
        CFG.cfg_vars["road_grade_limit"]["default"]


# ── 2. the adapter reproduces the core on a synthetic DEM ────────────────

def _ramp(x: np.ndarray) -> np.ndarray:
    """700 m, then a 15 % ramp (over the 8 % cap) from x=100 to 200, then
    flat again — the core lifts/cuts around the ramp and is the terrain
    far from it."""
    return 700.0 + np.clip(x - 100.0, 0.0, 100.0) * 0.15


def test_adapter_reproduces_the_core_clamp_and_lateral_answer(law):
    VECT = rp._core_vector_utils()
    import O4_Geo_Utils as GEO   # noqa: F401 (the core's metric)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    to_xy, to_ll = frame.transformers()
    cap, lane = 0.08, 4.0
    # a straight way along x, vertices 15 m apart (< 20 m: neither side
    # inserts stations, so the station sets coincide)
    xs = np.arange(0.0, 300.1, 15.0)
    way_xy = [(float(x), 0.0) for x in xs]

    class Dem:
        provenance = {}

        def z(self, x, y):
            return float(_ramp(np.array([x]))[0])

        def bounds(self):
            return (-1e4, -1e4, 1e4, 1e4)

    def sample(ax, ay):
        return _ramp(np.asarray(ax, float))
    ours = rp.clamp_way(rp.ROUTE, "w", way_xy, sample, cap, law.tables.emit.road_profile.station_m)
    assert len(ours) == 1
    w = ours[0]
    assert len(w.s) == len(xs)
    # the core, in its tile-relative degree frame on the SAME terrain
    lat0, lon0 = 60, -136
    tile_rel = np.array([[lon - lon0, lat - lat0] for lat, lon in
                         (to_ll(x, y) for x, y in way_xy)])

    def alt_vec(pts):
        pts = np.asarray(pts, float)
        out = []
        for lon_r, lat_r in pts:
            x, _y = to_xy(lon_r + lon0, lat_r + lat0)
            out.append(_ramp(np.array([x]))[0])
        return np.array(out)
    old = VECT.scalx
    VECT.scalx = math.cos((lat0 + 0.5) * math.pi / 180)
    try:
        from shapely.geometry import LineString, MultiLineString
        lr = VECT.clamp_road_network(MultiLineString([LineString(tile_rel)]), alt_vec, cap, lane)
        core_z = lr.ways[0]["alt"]
        assert len(core_z) == len(xs)
        d = np.abs(core_z - w.z)
        # identical where the terrain is cap-lawful and far from the ramp
        # (both clamps are the identity there), within the arclength
        # metric's 0.3 % elsewhere (0.08 × 0.003 × 200 m ≈ 0.05 m)
        assert d[0] < 1e-6 and d[-1] < 1e-6
        assert d.max() < 0.05, d.max()
        assert np.abs(w.z - w.dem).max() > 1.0        # the ramp WAS clamped
        # lateral answer: a kerb 3 m abeam a station reads the station
        # (core: nearest station within 2 lane widths; ours: projection)
        prof = rp.RoadProfiles(cap, 20.0, lane, 2 * lane, (w,))
        for k in (0, 7, 10, 20):
            x = float(xs[k])
            a = prof.answer((x, 3.0), 555.0)
            assert a.kind == rp.ROUTE and abs(a.z - w.z[k]) < 1e-9
            q = tile_rel[k].copy()
            q[1] += 3.0 * GEO.m_to_lat
            got = lr.answer(np.array([q]), np.array([555.0]))[0]
            assert abs(got - a.z) < 0.05
        # beyond the radius both hand back the DEM value they were given
        a = prof.answer((150.0, 9.0), 555.0)
        assert a.kind is None and a.z == 555.0
        q = tile_rel[10].copy()
        q[1] += 9.0 * GEO.m_to_lat
        assert lr.answer(np.array([q]), np.array([555.0]))[0] == 555.0
    finally:
        VECT.scalx = old


# ── 3. the synthetic airport: a road and a lot on a 7 % slope ────────────

class _SlopeDem:
    """1 % along the runway (x), 7 % across it (y): lawful for a road
    (8 %), over the cap for a lot (5 %)."""

    provenance = {"synthetic": "1 % in x, 7 % in y"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.01 * x + 0.07 * y

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law, osm=(), dem=None):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 694.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (), (), (), (),
                   tuple(osm), (), (), pack, dem or _SlopeDem(), law.ruleset_key)


@pytest.fixture(scope="module")
def slope(law):
    """A service road strip (route through it), a narrow lot with an OSM
    service way along it, a road page with NO centreline, and a lot far
    from every road."""
    osm = (OsmWay(1, "airport_small_roads", ((906.0, 100.0), (906.0, 300.0)), False,
                  {"highway": "service"}),)
    airport = _airport(law, osm)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "service_road", "road1", _rect(796, 100, 804, 400), (), None, None,
             "groundside", "road", {}),
        Cell(2, "parking_lot", "lot1", _rect(900, 100, 912, 300), (), None, None,
             "groundside", "lot", {}),
        Cell(3, "service_road", "page1", _rect(1096, 100, 1104, 400), (), None, None,
             "groundside", "road", {}),
        Cell(4, "parking_lot", "lot2", _rect(1300, 100, 1340, 160), (), None, None,
             "groundside", "lot", {}),
    )
    cuts = (CutLine("road_centerline", "road1", ((800.0, 100.0), (800.0, 400.0))),)
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    pref, rep, prof = rp.preferred_road_z(airport, pm, law)
    return airport, pm, pref, rep, prof


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


def _face_vertices(pm, f):
    vs = set()
    for cyc in (f.ring, *f.holes):
        for eid in cyc:
            vs.update((pm.edges[eid].a, pm.edges[eid].b))
    return vs


def test_sources_route_osm_axis_and_dem_fallback(slope, law):
    airport, pm, pref, rep, prof = slope
    kinds = {rp.OSM: 0, rp.ROUTE: 0, rp.AXIS: 0}
    for r in rep["by_role"].values():
        for k in kinds:
            kinds[k] += r[k]
    assert kinds[rp.ROUTE] > 0 and kinds[rp.OSM] > 0 and kinds[rp.AXIS] > 0
    # the road strip: every vertex answered by its route
    road = _face(pm, "road1")
    assert all(v in pref for v in _face_vertices(pm, road))
    # the page with no centreline: its own axis, clamped (identity here)
    page = _face(pm, "page1")
    assert page.id in prof.axes and prof.axes[page.id].kind == rp.AXIS
    assert all(v in pref for v in _face_vertices(pm, page))
    assert np.abs(prof.axes[page.id].z - prof.axes[page.id].dem).max() < 1e-9
    # the lot beside no road: DEM fallback, counted, never in ``preferred``
    lot2 = _face(pm, "lot2")
    assert not any(v in pref for v in _face_vertices(pm, lot2))
    assert rep["by_role"]["parking_lot"]["dem"] >= len(_face_vertices(pm, lot2))
    assert rep["dem_fallback"] == rep["vertices"] - rep["preferred"]
    # lateral levelling: both kerbs of the road read the centreline, so a
    # kerb pair at one station carries ONE value while their DEM differs
    ring = pm.ring_vertices(road.ring)
    by_y = {}
    for v in ring:
        by_y.setdefault(round(pm.vertices[v].xy[1], 3), []).append(v)
    pairs = [vs for vs in by_y.values() if len(vs) >= 2]
    assert pairs
    for vs in pairs:
        assert abs(pref[vs[0]] - pref[vs[1]]) < 1e-9
        assert abs(pm.vertices[vs[0]].dem_z - pm.vertices[vs[1]].dem_z) > 0.03   # 1 % x >= 4 m


def test_lawful_road_holds_the_core_profile_and_over_cap_lot_moves(slope, law):
    airport, pm, pref, rep, prof = slope
    pm2 = _dc.replace(pm, preferred_z=pref)
    cs, _counts, _w = generate(pm2, law, airport)
    sol, _rep = solve_design(pm2, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    ag = road_profile_agreement(pm2, law, sol.z)
    tol = law.tables.emit.materiality.elevation_m
    road = ag["faces"][_face(pm, "road1").id]
    page = ag["faces"][_face(pm, "page1").id]
    # a lawful road (7 % < 8 %, laterally level) IS the core profile —
    # nothing binds and the roughness term adds nothing beyond materiality
    assert road["off"] == 0 and road["max_m"] <= tol, road
    assert page["off"] == 0 and page["max_m"] <= tol, page
    # the lot: the core's 8 % profile is the 7 % terrain, over the lot's
    # 5 % cap — v2's rows bind and the surface leaves the profile
    lot = ag["faces"][_face(pm, "lot1").id]
    assert lot["off"] > 0 and lot["max_m"] > 0.5, lot
    lv = sorted(_face_vertices(pm, _face(pm, "lot1")), key=lambda v: pm.vertices[v].xy[1])
    lo, hi = lv[0], lv[-1]
    dy = pm.vertices[hi].xy[1] - pm.vertices[lo].xy[1]
    grade = abs(sol.z[hi] - sol.z[lo]) / dy
    assert grade <= role_cap(law, "parking_lot").longitudinal + 1e-6


def test_tile_road_grade_limit_reaches_the_clamp(slope, law):
    airport, pm, _pref, _rep, _prof = slope
    prof5, _pf = rp.core_profiles(airport, pm, law, cap=0.05)
    assert prof5.cap == 0.05
    w = next(w for w in prof5.ways if w.kind == rp.ROUTE)
    g = np.abs(np.diff(w.z)) / np.diff(w.s)
    assert g.max() <= 0.05 + 1e-9 and np.abs(w.z - w.dem).max() > 0.5
    # the default is the law's (= the core's cfg default)
    prof8, _pf = rp.core_profiles(airport, pm, law)
    assert prof8.cap == role_cap(law, "service_road").longitudinal
    assert prof8.lane_width_m == law.tables.emit.road_profile.lane_width_m


def test_face_axis_is_the_midline_of_a_strip():
    axis = rp.face_axis(_rect(10, 0, 18, 200), 10.0)
    assert axis is not None and len(axis) >= 15
    assert all(abs(x - 14.0) < 1e-6 for x, _y in axis)
    ys = [y for _x, y in axis]
    assert ys == sorted(ys) or ys == sorted(ys, reverse=True)
    assert rp.face_axis(((0, 0), (1, 0), (0, 0)), 10.0) is None
