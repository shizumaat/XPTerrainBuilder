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
from auto_patch_v2.law import tables as V2TABLES                # noqa: E402

#: THE ONE DEFINITION of the road grade cap since 2026-09-17 (lane
#: v1retire round 1, session ruling (c)): ``[common.roles]``
#: ``service_road.longitudinal`` in ``auto_patch_v2/law/rulesets.toml``.
#: It was ``auto_patch.config.SERVICE_ROAD_MAX_GRADE`` — inside the
#: retired v1 engine — and both core readers moved with it.
ROAD_CAP_FROM_LAW = float(V2TABLES.role_cap(
    V2TABLES.load_default(), "service_road").longitudinal)

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


def test_sidecar_precision_cannot_manufacture_an_over_cap_grade(tmp_path):
    """THE ROUNDING TWIN (Batch-2 residual fix).

    ``refine_way`` KEEPS every original vertex, so a dense OSM way puts
    consecutive stations decimetres apart — and a station VALUE rounded
    coarsely then reads as a grade the clamp never wrote.  At 3 dp the
    Batch-1 LEMD sidecar carried 11,267 steps over the 8 % cap (worst
    8.103 %) on a cap-Lipschitz profile.  The sidecar's own numbers must
    price the law they publish: terrain exactly AT the cap round-trips
    through the file still at the cap.
    """
    from shapely import geometry

    VECT.scalx = math.cos(math.radians(0.5))
    dlat = GEO.m_to_lat
    # 40 vertices ~1.13 m apart (the dense-way case), terrain climbing at
    # EXACTLY the cap: the clamp is the identity here, so every step the
    # sidecar spells must read the cap and never a hair above it.
    line = geometry.LineString([(0.0, i * 1.13 * dlat) for i in range(40)])

    def alt_vec(pts):
        pts = numpy.asarray(pts, dtype=float)
        return CAP * pts[:, 1] / dlat

    lev = VECT.clamp_road_network(geometry.MultiLineString([line]),
                                  alt_vec, CAP, 4.0, station_m=STATION_M)
    tile = types.SimpleNamespace(lat=40, lon=-4,
                                 build_dir=str(tmp_path / "dense"))
    doc = json.loads(Path(VM.write_levelled_roads_sidecar(tile, lev))
                     .read_text())
    (way,) = doc["ways"]
    s = way["s_m"]
    z = way["alt"]
    d = way["dem_alt"]
    assert 1.0 < (s[1] - s[0]) < 1.3          # the dense spacing is real
    worst = max(abs(z[k + 1] - z[k]) / (s[k + 1] - s[k])
                for k in range(len(s) - 1))
    worst_dem = max(abs(d[k + 1] - d[k]) / (s[k + 1] - s[k])
                    for k in range(len(s) - 1))
    # 1e-6 of grade = 1e-4 pp: below any threshold the instrument prices.
    assert worst <= CAP + 1e-6, worst
    assert worst_dem <= CAP + 1e-6, worst_dem


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
    assert var["default"] == ROAD_CAP_FROM_LAW
    assert "road_grade_limit" in CFGVARS.list_vector_vars
    # beside road_banking_limit, as the census asked
    keys = list(CFGVARS.cfg_vars)
    assert abs(keys.index("road_grade_limit")
               - keys.index("road_banking_limit")) == 1


def test_both_road_cap_readers_read_the_LAW_TABLE_and_not_the_v1_engine():
    """Session ruling (c) of the v1 stage-B brief: ONE definition, both
    readers re-pointed.  ``O4_Cfg_Vars`` (the knob's default) and
    ``O4_Vector_Map`` (the fallback for a tile object predating the knob)
    must agree with ``rulesets.toml`` and must not import the v1
    constant — which does not survive the config split of round 2."""
    assert CFGVARS._ROAD_GRADE_CAP == ROAD_CAP_FROM_LAW
    assert VM.ROAD_GRADE_CAP_DEFAULT == ROAD_CAP_FROM_LAW
    assert CFGVARS.cfg_vars["road_grade_limit"]["default"] == ROAD_CAP_FROM_LAW
    for mod in (CFGVARS, VM):
        src = Path(mod.__file__).read_text()
        code = "\n".join(l for l in src.splitlines()
                         if not l.lstrip().startswith("#"))
        assert "SERVICE_ROAD_MAX_GRADE" not in code, (
            f"{mod.__name__} still reads the v1 engine's constant")
    # and the law table is the value the CENSUS prices roads by, so the
    # knob's default cannot drift from what a defect count assumes
    assert ROAD_CAP_FROM_LAW == CAP


# ── §2-SUPPLEMENT: THE CLAMP IS SCOPED TO THE PATCH NEIGHBOURHOOD ───────
#
# Owner RULINGS 2026-09-18n, spec §2-SUPPLEMENT (lane ``roadclampscope``).
# Outside the band a road gets the NORMAL ENGINE ROAD PROCESSING and NO
# longitudinal clamp; over a 100 m run-out it is eased onto the patch at
# its OSM CLASS's cap, which YIELDS uniformly so the profile never stands
# more than the deviation budget off the terrain.
#
# The fixture is the shipped TFFJ tile's own sidecar (app 1.0.351): four
# ways, their stations, the terrain the build sampled, the altitude the
# 8 % tile-wide clamp gave them, and the in-band mask.

FIXTURE = (_ROOT / "tests" / "fixtures" / "roadclampscope"
           / "tffj_ways.json")


def _fixture():
    doc = json.loads(FIXTURE.read_text())
    return doc["params"], {w["sidecar_index"]: w for w in doc["ways"]}


def _way_arrays(w):
    return (numpy.array(w["s_m"], dtype=float),
            numpy.array(w["dem_alt"], dtype=float),
            numpy.array(w["in_coverage_band"], dtype=bool))


def _profile(w, params, **over):
    s, dem, band = _way_arrays(w)
    kw = dict(cap_inside=params["cap_inside"], runout_m=params["runout_m"],
              budget_m=params["budget_m"], cap_ceiling=params["cap_ceiling"])
    kw.update(over)
    cap_class = params["class_caps"].get(w["highway"], params["cap_inside"])
    return VECT.neighbourhood_road_profile(s, dem, band, cap_class, **kw)


# T1 ── the scalar cap is BIT-IDENTICAL, and a constant per-segment array
#       says exactly the same thing.

def test_t1_scalar_cap_is_the_shipped_profile_and_equals_a_constant_array():
    _params, ways = _fixture()
    for w in ways.values():
        s, dem, _band = _way_arrays(w)
        got = VECT.cap_lipschitz_profile(s, dem, 0.08)
        shipped = numpy.array(w["shipped_alt_cap008"], dtype=float)
        # the sidecar writes 6 dp, so 1e-6 IS bit-identity here
        assert numpy.abs(got - shipped).max() <= 1e-6, w["sidecar_index"]
        per_seg = VECT.cap_lipschitz_profile(
            s, dem, numpy.full(len(s) - 1, 0.08))
        assert numpy.abs(got - per_seg).max() <= 1e-9, w["sidecar_index"]


# T2 ── a per-SEGMENT cap: each segment holds ITS OWN cap.

def test_t2_per_segment_cap_holds_each_segment_to_its_own_cap():
    s = numpy.array([0.0, 100.0, 200.0])
    dem = numpy.array([0.0, 30.0, 60.0])          # a 30 % ramp throughout
    caps = numpy.array([0.08, 0.20])
    z = VECT.cap_lipschitz_profile(s, dem, caps)
    got = numpy.abs(numpy.diff(z)) / numpy.diff(s)
    assert got[0] <= caps[0] + 1e-12, got
    assert got[1] <= caps[1] + 1e-12, got
    # and the looser segment really is allowed to be steeper
    assert got[1] > caps[0] + 1e-3, got


# T3 ── THE JOIN.  A way that never enters the band is TERRAIN; a way that
#       does re-meets the terrain EXACTLY at the run-out pin.

def test_t3_the_owner_site_way_is_terrain_and_the_run_meets_the_dem():
    params, ways = _fixture()
    w435 = ways[435]
    s, dem, band = _way_arrays(w435)
    assert not band.any()                        # 637 m off the patch
    z, rep = _profile(w435, params)
    assert rep["scope"] == "terrain"
    assert rep["runs"] == []
    assert numpy.array_equal(z, dem)             # the DEM, identically

    z9, rep9 = _profile(ways[9], params)
    assert rep9["scope"] == "neighbourhood"
    (run,) = rep9["runs"]
    s9, dem9, band9 = _way_arrays(ways[9])
    for k in (run["i0"], run["i1"]):
        if not band9[k]:
            assert abs(z9[k] - dem9[k]) == 0.0    # step 0.000 by construction
    # outside every run the profile IS the DEM, identically
    outside = numpy.ones(len(s9), bool)
    outside[run["i0"]:run["i1"] + 1] = False
    assert numpy.array_equal(z9[outside], dem9[outside])


def test_t3_a_terrain_way_puts_no_station_in_the_answering_tree():
    from shapely import geometry

    dlat = 1.0 / GEO.lat_to_m
    line = geometry.LineString([(0.0, i * 25.0 * dlat) for i in range(20)])

    def alt_vec(pts):
        return 0.5 * numpy.asarray(pts, dtype=float)[:, 1] / dlat

    # a band far away: the way is not OURS
    band = geometry.Point(0.02, 0.02).buffer(0.0005)
    lev = VECT.clamp_road_network(geometry.MultiLineString([line]), alt_vec,
                                  CAP, 4.0, coverage=band)
    (way,) = lev.ways
    assert way["scope"] == "terrain"
    assert numpy.array_equal(way["alt"], way["dem"])
    assert lev._tree is None                      # nothing answers
    q = numpy.array([[0.0, 5.0 * 25.0 * dlat]])
    dem_q = numpy.array([123.0])
    assert lev.answer(q, dem_q)[0] == 123.0       # the shifted DEM stands


def test_t3_an_empty_band_clamps_nothing():
    from shapely import geometry

    dlat = 1.0 / GEO.lat_to_m
    line = geometry.LineString([(0.0, i * 25.0 * dlat) for i in range(10)])

    def alt_vec(pts):
        return 0.5 * numpy.asarray(pts, dtype=float)[:, 1] / dlat

    lev = VECT.clamp_road_network(geometry.MultiLineString([line]), alt_vec,
                                  CAP, 4.0, coverage=geometry.Polygon())
    (way,) = lev.ways
    assert way["scope"] == "terrain"
    assert lev.summary()["neighbourhood_ways"] == 0


# T4 ── THE YIELD.

def test_t4_the_cap_yields_uniformly_to_the_deviation_budget():
    params, ways = _fixture()
    expect = {9: (0.1623, 1.000, 4.343, 4),
              782: (0.2000, 0.554, 0.554, 1),
              1054: (0.2531, 1.000, 2.934, 2)}
    for idx, (cap_eff, dev, dev_free, n05) in expect.items():
        w = ways[idx]
        s, dem, band = _way_arrays(w)
        z, rep = _profile(w, params)
        (run,) = rep["runs"]
        assert abs(run["cap_eff"] - cap_eff) <= 1e-3, (idx, run)
        off = numpy.abs(z - dem)[~band]
        assert abs(off.max() - dev) <= 0.005, (idx, off.max())
        assert int((off > 0.5).sum()) == n05, idx
        # and with no budget the class cap alone stands this far off
        z2, _r2 = _profile(w, params, budget_m=1e9)
        assert abs(numpy.abs(z2 - dem)[~band].max() - dev_free) <= 0.005, idx


def test_t4_dev_is_monotone_in_the_cap():
    params, ways = _fixture()
    w = ways[9]
    s, dem, band = _way_arrays(w)
    prev = None
    for c in (0.10, 0.12, 0.15, 0.18, 0.22, 0.30):
        z, _r = VECT.neighbourhood_road_profile(
            s, dem, band, c, cap_inside=params["cap_inside"],
            runout_m=params["runout_m"], budget_m=1e9,
            cap_ceiling=params["cap_ceiling"])
        dev = float(numpy.abs(z - dem)[~band].max())
        if prev is not None:
            assert dev <= prev + 1e-9, (c, dev, prev)
        prev = dev


def test_t4_an_in_band_cliff_ships_at_the_ceiling_and_says_so():
    # An 8 % in-band segment pushed off terrain by a cliff INSIDE the
    # band: no out-of-band cap can buy the budget back, so the run ships
    # at the ceiling and is named.
    s = numpy.array([0.0, 20.0, 40.0, 60.0, 80.0, 100.0])
    dem = numpy.array([0.0, 0.0, 40.0, 40.0, 40.0, 40.0])
    band = numpy.array([True, True, True, False, False, False])
    z, rep = VECT.neighbourhood_road_profile(
        s, dem, band, 0.15, cap_inside=0.08, runout_m=100.0, budget_m=1.0,
        cap_ceiling=0.30)
    (run,) = rep["runs"]
    assert run["at_ceiling"] is True
    assert run["yielded"] is True
    assert abs(run["cap_eff"] - 0.30) < 1e-9


# T5 ── a deck pin inside a run is still EXACT, and §6's refusal survives.

def test_t5_a_deck_pin_inside_a_run_is_exact():
    s = numpy.arange(0.0, 201.0, 20.0)
    dem = 0.02 * s
    band = numpy.zeros(len(s), bool)
    band[:3] = True
    z, rep = VECT.neighbourhood_road_profile(
        s, dem, band, 0.15, cap_inside=0.08, runout_m=100.0, budget_m=1.0,
        cap_ceiling=0.30, pin_idx=[5], pin_val=[dem[5] + 0.8])
    assert rep["pins"] == 1
    assert rep["refused"] is False
    assert abs(z[5] - (dem[5] + 0.8)) <= 1e-9


def test_t5_two_unreachable_pins_still_refuse():
    s = numpy.arange(0.0, 201.0, 20.0)
    dem = numpy.zeros(len(s))
    band = numpy.zeros(len(s), bool)
    band[:3] = True
    _z, rep = VECT.neighbourhood_road_profile(
        s, dem, band, 0.15, cap_inside=0.08, runout_m=100.0, budget_m=1.0,
        cap_ceiling=0.30, pin_idx=[3, 4], pin_val=[0.0, 40.0])
    assert rep["refused"] is True
    assert rep["worst_infeasibility_m"] > 0.01


# T6 ── ``accepted_ids`` is parallel to the geoms.

def test_t6_accepted_ids_are_parallel_to_the_geoms():
    layer = _FakeLayer({
        1: ({"highway": "service"}, [(0.0, 0.0), (0.001, 0.0)]),
        2: ({"highway": "track", "bridge": "yes"},
            [(0.0, 0.001), (0.001, 0.001)]),
        3: ({"highway": "residential"}, [(0.0, 0.002)]),   # degenerate
        4: ({"railway": "rail"}, [(0.0, 0.003), (0.001, 0.003)]),
    })
    ids = []
    banked, _rej = OSM.OSM_to_MultiLineString(
        layer, 0, 0, set(["bridge", "tunnel"]), lambda w, n: True,
        accepted_ids=ids)
    assert len(ids) == len(banked.geoms)
    assert ids == [1, 4]                       # 2 excluded, 3 degenerate
    assert VM._way_classes(layer, ids) == ["service", "railway:rail"]


def test_t6_a_length_mismatch_falls_back_to_default_caps():
    from shapely import geometry

    dlat = 1.0 / GEO.lat_to_m
    lines = [geometry.LineString([(0.0, 0.0), (0.0, 100.0 * dlat)]),
             geometry.LineString([(0.001, 0.0), (0.001, 100.0 * dlat)])]
    band = geometry.box(-0.001, -0.001, 0.01, 0.01)
    lev = VECT.clamp_road_network(
        geometry.MultiLineString(lines),
        lambda pts: 0.3 * numpy.asarray(pts, float)[:, 1] / dlat,
        CAP, 4.0, coverage=band, way_classes=["service"])   # 1 of 2
    assert all(w["class"] is None for w in lev.ways)


# T7 ── ``answer`` interpolates at the projection.

def test_t7_answer_interpolates_between_two_stations():
    from shapely import geometry

    dlat = 1.0 / GEO.lat_to_m
    # two stations 20 m apart, the profile rising 2 m over them
    line = geometry.LineString([(0.0, 0.0), (0.0, 40.0 * dlat)])
    band = geometry.box(-0.001, -0.001, 0.001, 0.01)

    def alt_vec(pts):
        return 0.05 * numpy.asarray(pts, dtype=float)[:, 1] / dlat

    lev = VECT.clamp_road_network(geometry.MultiLineString([line]), alt_vec,
                                  0.08, 4.0, station_m=20.0, coverage=band)
    (way,) = lev.ways
    assert way["scope"] == "neighbourhood"
    mid_y = 0.5 * (way["points"][0][1] + way["points"][1][1])
    q = numpy.array([[0.0, mid_y]])
    got = float(lev.answer(q, numpy.array([-999.0]))[0])
    want = 0.5 * (way["alt"][0] + way["alt"][1])
    assert abs(got - want) <= 1e-6, (got, want)
    # far outside the radius the DEM argument stands
    far = numpy.array([[0.01, mid_y]])
    assert lev.answer(far, numpy.array([-999.0]))[0] == -999.0


# T8 ── the sidecar is version 2 and carries the frame every run used.

def test_t8_sidecar_v2_keys(tmp_path):
    from shapely import geometry

    dlat = 1.0 / GEO.lat_to_m
    line = geometry.LineString([(0.0, i * 20.0 * dlat) for i in range(12)])
    off = geometry.LineString([(0.01, i * 20.0 * dlat) for i in range(12)])
    band = geometry.box(-0.001, -0.001, 0.001, 0.0005)

    def alt_vec(pts):
        return 0.25 * numpy.asarray(pts, dtype=float)[:, 1] / dlat

    lev = VECT.clamp_road_network(
        geometry.MultiLineString([line, off]), alt_vec, CAP, 4.0,
        station_m=20.0, coverage=band,
        way_classes=["residential", "service"], way_ids=[11, 22])
    tile = types.SimpleNamespace(lat=17, lon=-63,
                                 build_dir=str(tmp_path / "t"))
    doc = json.loads(Path(VM.write_levelled_roads_sidecar(tile, lev))
                     .read_text())
    assert doc["version"] == 2
    assert doc["grade_cap"] == doc["cap_inside"] == CAP
    for k in ("runout_m", "budget_m", "cap_ceiling", "class_caps"):
        assert doc[k] is not None, k
    ours, terrain = doc["ways"][0], doc["ways"][1]
    assert ours["scope"] == "neighbourhood"
    assert ours["class"] == "residential" and ours["layer_way_id"] == 11
    assert ours["cap_class"] == doc["class_caps"]["residential"]
    assert ours["runs"] and set(ours["runs"][0]) >= {
        "i0", "i1", "cap_eff", "yielded", "at_ceiling", "max_offset_m"}
    assert terrain["scope"] == "terrain"
    assert terrain["alt"] == terrain["dem_alt"]
    s = doc["summary"]
    assert s["neighbourhood_ways"] == 1 and s["runs"] == 1
    assert set(s) >= {"yielded_runs", "ceiling_runs"}
    # the geometry keys ``bank_pavement_lines`` reads are untouched
    for w in doc["ways"]:
        assert len(w["lat"]) == len(w["lon"]) == w["stations"]
    assert doc["lane_width_m"] == 4.0


# T10 ── ONE law table: the core's reader IS ``emit.toml``.

def test_t10_the_class_caps_come_from_one_law_table():
    law = CFGVARS.road_neighbourhood_law()
    rp = V2TABLES.load_default().tables.emit.road_profile
    assert law["runout_m"] == rp.runout_m
    assert law["budget_m"] == rp.budget_m
    assert law["cap_ceiling"] == rp.cap_ceiling
    assert law["class_caps"] == {str(k): float(v)
                                 for k, v in rp.class_caps.items()}
    # the rows the spec's table states, by value
    for tag, cap in (("motorway", 0.06), ("trunk", 0.08), ("primary", 0.10),
                     ("secondary", 0.12), ("tertiary", 0.12),
                     ("residential", 0.15), ("unclassified", 0.15),
                     ("service", 0.20), ("track", 0.18),
                     ("railway:rail", 0.04), ("railway:tram", 0.08)):
        assert law["class_caps"][tag] == cap, tag
    # an unknown / untagged class takes ``road_grade_limit``
    assert VECT.road_class_cap(None, law["class_caps"], CAP) == CAP
    assert VECT.road_class_cap("pier", law["class_caps"], CAP) == CAP
    assert law["cap_ceiling"] > max(law["class_caps"].values())
