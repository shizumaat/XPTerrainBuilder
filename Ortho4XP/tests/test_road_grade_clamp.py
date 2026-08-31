"""Twins for the CORE road law — the longitudinal clamp, the bridge/
tunnel exclusion seam, and the unconditional patch-area road detail.

The law (owner RULINGS 2026-08-31a/31b, docs/specs/linear-transport-
redesign-spec.md §2): a road FOLLOWS TERRAIN, and only where the terrain
out-grades ``road_grade_limit`` does it LIFT or CUT — the minimum needed
to hold the cap.  "A road capped below 8 % into a cutting is a defect"
is stated here as an identity: on cap-lawful terrain the clamp returns
the terrain, unchanged, to the last bit.

Everything is headless: pure arrays, a fake OSM layer, ``tmp_path``.
"""

from __future__ import annotations

import json
import math
import sys
import types
from pathlib import Path

import numpy
import pytest

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import O4_Cfg_Vars as CFGVARS                                   # noqa: E402
import O4_Geo_Utils as GEO                                      # noqa: E402
import O4_OSM_Utils as OSM                                      # noqa: E402
import O4_Vector_Map as VM                                      # noqa: E402
import O4_Vector_Utils as VECT                                  # noqa: E402
from auto_patch.config import SERVICE_ROAD_MAX_GRADE            # noqa: E402

CAP = 0.08
STATION_M = 20.0


def _grades(s, z):
    s = numpy.asarray(s, dtype=float)
    z = numpy.asarray(z, dtype=float)
    ds = numpy.diff(s)
    return numpy.abs(numpy.diff(z)) / numpy.where(ds > 0, ds, numpy.inf)


# ── THE CLAMP ITSELF ────────────────────────────────────────────────────

def test_cap_lawful_hill_is_untouched():
    """THE HEADLINE TWIN.  A hill the road may lawfully climb is climbed:
    the clamp returns the terrain identically, so no cutting can appear
    where the law does not ask for one."""
    s = numpy.arange(0, 20 * STATION_M, STATION_M)
    # 7 % up then 7 % down — under the 8 % cap the whole way.
    z = numpy.array([0.07 * min(v, 180.0) - 0.07 * max(v - 180.0, 0.0)
                     for v in s])
    out = VECT.cap_lipschitz_profile(s, z, CAP)
    assert numpy.allclose(out, z, atol=1e-12)
    # ... and a FLAT road is likewise its own answer.
    flat = numpy.full_like(z, 42.0)
    assert numpy.allclose(VECT.cap_lipschitz_profile(s, flat, CAP), flat)


def test_terrain_exactly_at_the_cap_is_untouched():
    s = numpy.arange(0, 10 * STATION_M, STATION_M)
    z = CAP * s
    assert numpy.allclose(VECT.cap_lipschitz_profile(s, z, CAP), z,
                          atol=1e-9)


def test_over_cap_slope_is_lifted_and_cut_minimally():
    """A cliff the road may NOT follow: the clamp lifts the low side and
    cuts the high side, by the smallest amount that holds the cap."""
    s = numpy.arange(0, 5 * STATION_M, STATION_M)
    z = numpy.array([0.0, 0.0, 10.0, 10.0, 10.0])
    out = VECT.cap_lipschitz_profile(s, z, CAP)
    # 1. the result HOLDS THE CAP.
    assert (_grades(s, out) <= CAP + 1e-9).all()
    # 2. it BOTH lifts and cuts — the owner's "lift or cut", not
    #    cut-only (a cutting through the hill) and not lift-only (an
    #    embankment over the valley).
    delta = out - z
    assert delta.max() > 0.5 and delta.min() < -0.5
    # 3. MINIMALLY: the worst move is exactly half the profile's worst
    #    cap violation, which is the best any cap-lawful profile can do.
    worst_excess = max(
        abs(z[j] - z[k]) - CAP * abs(s[j] - s[k])
        for j in range(len(z)) for k in range(len(z))
    )
    assert numpy.abs(delta).max() == pytest.approx(0.5 * worst_excess,
                                                   abs=1e-9)


def test_no_cap_lawful_profile_sits_closer_to_the_terrain():
    """The minimality claim, checked against a brute-force search rather
    than restated: no cap-lawful profile on this fixture beats the
    clamp's worst deviation."""
    rng = numpy.random.default_rng(20260831)
    s = numpy.arange(0, 6 * STATION_M, STATION_M)
    z = numpy.array([0.0, 1.0, 9.0, 9.5, 2.0, 2.0])
    out = VECT.cap_lipschitz_profile(s, z, CAP)
    ours = float(numpy.abs(out - z).max())
    assert (_grades(s, out) <= CAP + 1e-9).all()
    for _ in range(4000):
        cand = out + rng.normal(0.0, 1.0, size=len(z))
        if (_grades(s, cand) > CAP + 1e-9).any():
            continue
        assert float(numpy.abs(cand - z).max()) >= ours - 1e-9


def test_a_single_station_way_is_returned_unchanged():
    assert VECT.cap_lipschitz_profile([0.0], [7.0], CAP).tolist() == [7.0]


# ── THE #111 TRAP: PER WAY, ON CENTERLINES, NEVER THE MERGED RING ───────

def _line(lat0, lon0, n, alt, geometry_mod):
    """A straight way of ``n`` stations marching north from (lat0, lon0),
    tile-relative, with its own flat terrain ``alt``."""
    dlat = STATION_M * GEO.m_to_lat
    return geometry_mod.LineString(
        [(lon0, lat0 + i * dlat) for i in range(n)]), alt


def test_clamp_is_per_way_and_never_fuses_two_roads():
    """THE TRAP (census #111): the clamp must run PER WAY on the
    CENTERLINE, never over the merged buffered ring's vertex order.

    Two roads running side by side 40 m apart — the ordinary case of an
    elevated road and the street beneath it, 100 m and 130 m, each flat
    and so each perfectly cap-lawful.  A merged ring walks one and then
    jumps to the other, and in THAT order the 30 m altitude difference
    across a 40 m jump is a 75 % grade: the clamp would drag both roads
    metres towards each other, fusing two unrelated roads into one
    profile.  Read per way, as the code does, both are untouched.
    """
    from shapely import geometry

    dlat = STATION_M * GEO.m_to_lat
    east = 40.0 * GEO.m_to_lat / math.cos(math.radians(0.5))
    alt_a, alt_b = 100.0, 130.0
    line_a = geometry.LineString([(0.0, i * dlat) for i in range(12)])
    # antiparallel, like a ring's return side: its FIRST station sits
    # beside the other way's LAST.
    line_b = geometry.LineString(
        [(east, (11 - i) * dlat) for i in range(12)])
    network = geometry.MultiLineString([line_a, line_b])

    def alt_vec(pts):
        pts = numpy.asarray(pts, dtype=float)
        return numpy.where(pts[:, 0] > 0.5 * east, alt_b, alt_a)

    VECT.scalx = math.cos(math.radians(0.5))
    lev = VECT.clamp_road_network(network, alt_vec, CAP, 4.0,
                                  station_m=STATION_M)

    # ONE WAY IS ONE PROFILE: never one fused chain.
    assert len(lev.ways) == 2
    for way, alt in zip(lev.ways, (alt_a, alt_b)):
        assert numpy.allclose(way["dem"], alt)
        assert numpy.allclose(way["alt"], alt, atol=1e-9), (
            "a cap-lawful road was moved — the other way's stations "
            "reached it")
    assert lev.summary()["clamped_stations"] == 0

    # THE TRAP, QUANTIFIED: the same stations read in one ring-order
    # sequence — the thing option (ii) would have done.
    fused_pts = numpy.concatenate([w["points"] for w in lev.ways])
    fused_dem = numpy.concatenate([w["dem"] for w in lev.ways])
    fused_s = VECT.way_arclengths(fused_pts)
    fused = VECT.cap_lipschitz_profile(fused_s, fused_dem, CAP)
    assert numpy.abs(fused - fused_dem).max() > 5.0, (
        "the fixture no longer demonstrates the fusion it exists to "
        "rule out")


def test_each_way_is_clamped_exactly_as_it_would_be_alone():
    """The per-way guarantee stated on ways that DO need clamping: a
    way's answer must not depend on what else is in the network."""
    from shapely import geometry

    dlat = STATION_M * GEO.m_to_lat
    steep = geometry.LineString([(0.0, i * dlat) for i in range(8)])
    other = geometry.LineString([(0.03, 0.04 + i * dlat) for i in range(8)])

    def alt_vec(pts):
        pts = numpy.asarray(pts, dtype=float)
        far = pts[:, 1] > 0.02
        # the near way climbs a 30 % bank; the far way sits at 900 m
        return numpy.where(far, 900.0, pts[:, 1] / dlat * 6.0)

    VECT.scalx = math.cos(math.radians(0.5))
    together = VECT.clamp_road_network(
        geometry.MultiLineString([steep, other]), alt_vec, CAP, 4.0,
        station_m=STATION_M)
    alone = VECT.clamp_road_network(
        geometry.MultiLineString([steep]), alt_vec, CAP, 4.0,
        station_m=STATION_M)
    assert numpy.allclose(together.ways[0]["alt"], alone.ways[0]["alt"])
    assert together.summary()["clamped_stations"] > 0


def test_a_closed_way_is_its_own_profile():
    """A roundabout (first node == last node) on lawful ground is
    untouched: the wrap is the way's own geometry, not a fusion."""
    from shapely import geometry

    d = 40.0 * GEO.m_to_lat
    ring = geometry.LineString(
        [(0.0, 0.0), (d, 0.0), (d, d), (0.0, d), (0.0, 0.0)])

    VECT.scalx = math.cos(math.radians(0.5))
    lev = VECT.clamp_road_network(
        geometry.MultiLineString([ring]),
        lambda pts: numpy.full(len(pts), 12.0), CAP, 4.0,
        station_m=STATION_M)
    assert len(lev.ways) == 1
    assert numpy.allclose(lev.ways[0]["alt"], 12.0)


# ── ANSWERING: NEAREST CLAMPED STATION, DEM BEYOND ──────────────────────

def test_answer_takes_the_nearest_station_within_the_radius():
    from shapely import geometry

    dlat = STATION_M * GEO.m_to_lat
    line = geometry.LineString([(0.0, i * dlat) for i in range(10)])

    def alt_vec(pts):
        pts = numpy.asarray(pts, dtype=float)
        return pts[:, 1] / dlat * 5.0            # 25 % — well over cap

    VECT.scalx = math.cos(math.radians(0.5))
    lev = VECT.clamp_road_network(geometry.MultiLineString([line]),
                                  alt_vec, CAP, 4.0, station_m=STATION_M)
    # A query 1 m to the side of the way (radius is lane_width x 2 = 8 m):
    # the NEAREST clamped station owns it, whichever that is.
    q = numpy.array([[1.0 * GEO.m_to_lat, 2 * dlat]])
    pts = lev.ways[0]["points"]
    near = int(numpy.argmin(((pts - q[0]) ** 2).sum(axis=1)))
    answered = lev.answer(q, alt_vec(q))
    assert answered[0] == pytest.approx(lev.ways[0]["alt"][near], abs=1e-9)
    # and it is NOT the raw DEM: this ramp is over the cap, so the clamp
    # has something to say here.
    assert abs(answered[0] - alt_vec(q)[0]) > 1.0


def test_answer_falls_back_to_the_dem_beyond_the_radius():
    from shapely import geometry

    dlat = STATION_M * GEO.m_to_lat
    line = geometry.LineString([(0.0, i * dlat) for i in range(10)])

    def alt_vec(pts):
        pts = numpy.asarray(pts, dtype=float)
        return pts[:, 1] / dlat * 5.0

    VECT.scalx = math.cos(math.radians(0.5))
    lev = VECT.clamp_road_network(geometry.MultiLineString([line]),
                                  alt_vec, CAP, 4.0, station_m=STATION_M)
    # 100 m to the side: no clamped station owns this ground.
    q = numpy.array([[100.0 * GEO.m_to_lat, 3 * dlat]])
    dem = numpy.array([777.0])
    assert lev.answer(q, dem)[0] == pytest.approx(777.0)


def test_empty_network_answers_the_dem():
    from shapely import geometry

    lev = VECT.clamp_road_network(geometry.MultiLineString([]),
                                  lambda pts: numpy.zeros(len(pts)),
                                  CAP, 4.0)
    dem = numpy.array([1.0, 2.0])
    assert lev.answer(numpy.zeros((2, 2)), dem).tolist() == [1.0, 2.0]


def test_stations_are_at_most_twenty_metres_apart():
    """Granularity (census #112): the instrument must outresolve
    ``emit_decimate``'s 60 m chords."""
    from shapely import geometry

    long_leg = geometry.LineString(
        [(0.0, 0.0), (0.0, 1000.0 * GEO.m_to_lat)])
    VECT.scalx = math.cos(math.radians(0.5))
    lev = VECT.clamp_road_network(geometry.MultiLineString([long_leg]),
                                  lambda pts: numpy.zeros(len(pts)),
                                  CAP, 4.0, station_m=STATION_M)
    s = lev.ways[0]["s_m"]
    assert numpy.diff(s).max() <= STATION_M + 1e-6
    assert len(s) >= 50


# ── THE SIDECAR ─────────────────────────────────────────────────────────

def test_sidecar_carries_every_station_and_its_two_altitudes(tmp_path):
    from shapely import geometry

    dlat = STATION_M * GEO.m_to_lat
    line = geometry.LineString([(0.0, i * dlat) for i in range(6)])

    def alt_vec(pts):
        pts = numpy.asarray(pts, dtype=float)
        return pts[:, 1] / dlat * 5.0

    VECT.scalx = math.cos(math.radians(0.5))
    lev = VECT.clamp_road_network(geometry.MultiLineString([line]),
                                  alt_vec, CAP, 4.0, station_m=STATION_M)
    tile = types.SimpleNamespace(lat=40, lon=-4,
                                 build_dir=str(tmp_path / "tile"))
    path = VM.write_levelled_roads_sidecar(tile, lev)
    assert path and Path(path).name == "o4_levelled_roads.json"
    doc = json.loads(Path(path).read_text())
    assert doc["grade_cap"] == CAP
    assert doc["station_max_m"] == STATION_M
    assert doc["lat"] == 40 and doc["lon"] == -4
    (way,) = doc["ways"]
    n = way["stations"]
    for key in ("lat", "lon", "s_m", "dem_alt", "alt"):
        assert len(way[key]) == n, key
    # absolute coordinates, not tile-relative
    assert all(39.9 < v < 40.2 for v in way["lat"])
    assert doc["summary"]["clamped_stations"] == way["clamped_stations"]
    assert doc["summary"]["stations"] == n


def test_sidecar_failure_is_not_fatal(tmp_path):
    from shapely import geometry

    lev = VECT.clamp_road_network(
        geometry.MultiLineString([geometry.LineString(
            [(0.0, 0.0), (0.0, 0.001)])]),
        lambda pts: numpy.zeros(len(pts)), CAP, 4.0)
    blocked = tmp_path / "file"
    blocked.write_text("not a directory")
    tile = types.SimpleNamespace(lat=0, lon=0,
                                 build_dir=str(blocked / "tile"))
    assert VM.write_levelled_roads_sidecar(tile, lev) is None


# ── THE BRIDGE / TUNNEL EXCLUSION SEAM (census #106) ────────────────────

class _FakeLayer:
    """The three dicts ``OSM_to_MultiLineString`` reads."""

    def __init__(self, ways):
        self.dicosmn = {}
        self.dicosmw = {}
        self.dicosmtags = {"n": {}, "w": {}, "r": {}}
        self.dicosmfirst = {"n": set(), "w": set(), "r": set()}
        nid = 1
        for wid, (tags, coords) in ways.items():
            nids = []
            for lon, lat in coords:
                self.dicosmn[nid] = (lon, lat)
                nids.append(nid)
                nid += 1
            self.dicosmw[wid] = nids
            self.dicosmtags["w"][wid] = tags
            self.dicosmfirst["w"].add(wid)


def _kept_way_ids(ways):
    """The ways ``OSM_to_MultiLineString`` KEEPS under the road
    exclusion, identified by their first node's longitude (the fixture
    gives each way its own)."""
    layer = _FakeLayer(ways)
    out = OSM.OSM_to_MultiLineString(layer, 0.0, 0.0,
                                     set(["bridge", "tunnel"]))
    return sorted(round(g.coords[0][0], 6) for g in out.geoms)


def test_bridge_no_levels_normally():
    """THE BUG THIS REPLACES: the exclusion tested key PRESENCE, so an
    ordinary road tagged ``bridge=no`` was dropped exactly as if it were
    a bridge."""
    coords = [(0.001, 0.0), (0.001, 0.001)]
    kept = _kept_way_ids({
        -1: ({"highway": "primary", "bridge": "no"}, coords),
    })
    assert kept == [0.001]


def test_bridge_yes_is_still_excluded():
    coords = [(0.002, 0.0), (0.002, 0.001)]
    assert _kept_way_ids({
        -1: ({"highway": "primary", "bridge": "yes"}, coords),
    }) == []


@pytest.mark.parametrize("value,kept", [
    ("no", True), ("NO", True), ("false", True), ("0", True), ("", True),
    ("yes", False), ("viaduct", False), ("1", False), ("culvert", False),
])
def test_only_an_asserted_tag_excludes(value, kept):
    coords = [(0.003, 0.0), (0.003, 0.001)]
    got = _kept_way_ids({-1: ({"highway": "primary", "tunnel": value},
                              coords)})
    assert (got == [0.003]) is kept


def test_an_untagged_way_is_kept():
    coords = [(0.004, 0.0), (0.004, 0.001)]
    assert _kept_way_ids({-1: ({"highway": "primary"}, coords)}) == [0.004]


def test_tag_helper_is_the_one_spelling():
    assert OSM.tag_is_asserted("yes") and not OSM.tag_is_asserted("no")
    assert not OSM.tag_is_asserted(None)
    assert OSM.way_asserts_any_tag({"bridge": "yes"}, {"bridge"})
    assert not OSM.way_asserts_any_tag({"bridge": "no"}, {"bridge"})
    assert not OSM.way_asserts_any_tag({"bridge": "yes"}, set())


# ── PATCH-AREA MAX DETAIL IS UNCONDITIONAL (spec §2 item 2) ─────────────

@pytest.mark.parametrize("mode,runs", [
    ("All", True), ("ICAO", True), ("None", False),
    (True, True), (False, False),
])
def test_auto_patch_runs_reads_every_spelling(mode, runs):
    tile = types.SimpleNamespace(auto_patch=mode)
    assert VM.auto_patch_runs(tile) is runs
    assert VM.resolved_auto_patch_mode(tile) in ("All", "ICAO", "None")


def test_numeric_road_level_keeps_the_patch_area_detail():
    """A numeric user ``road_level`` scopes the TILE-WIDE layers only:
    the airport-inset level-5 + rail pass runs because auto_patch runs,
    which is what it exists for."""
    tile = types.SimpleNamespace(road_level="2", auto_patch="All")
    level, auto = VM.resolved_road_level(tile)
    assert (level, auto) == (2, False)
    assert VM.auto_patch_runs(tile) is True      # the pass's new gate


def test_the_pass_is_off_when_auto_patch_is_off():
    tile = types.SimpleNamespace(road_level="2", auto_patch="None")
    assert VM.resolved_road_level(tile) == (2, False)
    assert VM.auto_patch_runs(tile) is False


# ── THE CFG VAR (census #115/#116) ──────────────────────────────────────

def test_road_grade_limit_defaults_to_the_engine_constant():
    var = CFGVARS.cfg_vars["road_grade_limit"]
    assert var["type"] is float
    assert var["default"] == SERVICE_ROAD_MAX_GRADE
    assert "road_grade_limit" in CFGVARS.list_vector_vars
    # beside road_banking_limit, as the census asked
    keys = list(CFGVARS.cfg_vars)
    assert abs(keys.index("road_grade_limit")
               - keys.index("road_banking_limit")) == 1
