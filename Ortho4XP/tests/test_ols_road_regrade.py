"""OLS ROAD REGRADE — ``auto_patch.ols._emit_road_regrades``.

The corridor mask leaves a surface road on its own DEM embankment; across
an ADMITTED penetration island that preserves the very hill the cut law
removes, as a road-width causeway proud of the fan at grades far beyond
``SERVICE_ROAD_MAX_GRADE`` (measured SPJC 16R: 12.8 % / 13.2 %).  With
``config.OLS_ROAD_REGRADE_ENABLED`` such a road is regraded: a
grade-capped, cut-only profile along the mapped way, bounded by the
composed ceiling over admitted cells, blending back into the DEM on both
sides, emitted as corridor deck strips (ref ``ols.REF_ROAD``).

Headless and fixture-free, on the ``test_ols`` synthetic harness: one
runway, a knoll penetrating the north approach fan, and a monkeypatched
road network (``bridges._load_tunnel_road_network`` — the same seam the
skirt tests use, and the one both the corridor mask and the regrade read).

Pinned here:

* a road crossing the admitted island grows a deck; every deck edge obeys
  the service-road grade cap; along the spine the deck never rides above
  the DEM (cut-only) and its ends blend into the DEM;
* the deck never overlaps the banded cut pieces (mask/deck disjointness);
* the sub-gate off restores the embankment (no decks, bands unchanged);
* a REFUSED island (depth guard) grades no road;
* BLEND refusal: a way that ends mid-hill emits no deck;
* railways are out of scope.
"""
import math

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from auto_patch import config as apc
from auto_patch import ols
from auto_patch.config import (
    SERVICE_ROAD_MAX_GRADE,
    SERVICE_ROAD_MAX_TRANSVERSE,
)
from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    R_EARTH,
    ROLE_OLS_CUT,
    ROLE_RUNWAY,
    ROLE_SERVICE_JUNCTION,
)

RUNWAY_LEN_M = 3000.0            # code 4
RUNWAY_WIDTH_M = 45.0
PAVEMENT_ALT_M = 6.2
BASE_TERRAIN_M = 5.0
LAT0, LON0 = -12.5, -77.5
TILE_LAT, TILE_LON = -13, -78
COS0 = math.cos(math.radians(LAT0))

#: The knoll in the north approach fan: centred on the extended
#: centreline, 300 m beyond the end (240 m past the 60 m setback, well
#: inside the fan), penetrating the ~11 m ceiling there by ~5 m.
KNOLL_X, KNOLL_Y = 0.0, RUNWAY_LEN_M + 300.0
KNOLL_R_M = 60.0
KNOLL_H_M = 16.0


class FakeDEM:
    """The read surface of ``O4_DEM_Utils.DEM`` the module uses."""

    def __init__(self, n: int = 3601, base: float = BASE_TERRAIN_M):
        self.x0, self.x1, self.y0, self.y1 = 0.0, 1.0, 0.0, 1.0
        self.nxdem = self.nydem = n
        self.alt_dem = np.full((n, n), float(base), dtype=np.float32)
        self.nodata = -32768
        self.posting_m = math.radians(1.0 / (n - 1)) * R_EARTH

    def alt(self, node):
        x, y = node
        nmax = self.nxdem - 1
        x = min(max(float(x), self.x0), self.x1)
        y = min(max(float(y), self.y0), self.y1)
        j = int(round(x * nmax))
        i = int(round((1.0 - y) * nmax))
        return float(self.alt_dem[i, j])

    def raise_disc(self, x_m, y_m, radius_m, height_m):
        i, j = self._ij(x_m, y_m)
        rad = max(1, int(round(radius_m / self.posting_m)))
        n = self.nxdem
        ii, jj = np.ogrid[max(0, i - rad):min(n, i + rad + 1),
                          max(0, j - rad):min(n, j + rad + 1)]
        disc = (ii - i) ** 2 + (jj - j) ** 2 <= rad * rad
        block = self.alt_dem[max(0, i - rad):min(n, i + rad + 1),
                             max(0, j - rad):min(n, j + rad + 1)]
        block[disc] = float(height_m)

    def _ij(self, x_m, y_m):
        lat = LAT0 + math.degrees(y_m / R_EARTH)
        lon = LON0 + math.degrees(x_m / (R_EARTH * COS0))
        nmax = self.nxdem - 1
        return (int(round((1.0 - (lat - TILE_LAT)) * nmax)),
                int(round((lon - TILE_LON) * nmax)))

    def alt_at_local(self, x_m, y_m):
        i, j = self._ij(x_m, y_m)
        return float(self.alt_dem[i, j])


class FakeRunway:
    """The ``apt_dat_reader.Runway`` fields ``ols`` reads."""

    def __init__(self, markings: int = 3, lights: int = 1):
        self.desig_a, self.desig_b = "16R", "34L"
        self.lat_a, self.lon_a = LAT0, LON0
        self.lat_b = LAT0 + math.degrees(RUNWAY_LEN_M / R_EARTH)
        self.lon_b = LON0
        self.width_m = RUNWAY_WIDTH_M
        self.markings_a = self.markings_b = markings
        self.approach_lights_a = self.approach_lights_b = lights


def make_layout() -> PavementLayout:
    layout = PavementLayout(icao="TEST", anchor=(LAT0, LON0))
    half = 0.5 * RUNWAY_WIDTH_M
    ring = [(-half, 0.0), (half, 0.0), (half, RUNWAY_LEN_M),
            (-half, RUNWAY_LEN_M)]
    layout.shapes.append(BuiltShape(
        polygon=Polygon(ring + [ring[0]]), role=ROLE_RUNWAY, ref="16R/34L",
        altitude=PAVEMENT_ALT_M,
        node_altitudes=[PAVEMENT_ALT_M] * 5))
    return layout


def _ll(x_m: float, y_m: float):
    """Local metres → (lat, lon), the exact inverse of ``layout.ll_to_m``."""
    return (LAT0 + math.degrees(y_m / R_EARTH),
            LON0 + math.degrees(x_m / (R_EARTH * COS0)))


def road_network(ways):
    """``bridges._load_tunnel_road_network`` return shape from a list of
    ``(way_id, [(x, y), ...], tags)`` in local metres."""
    nodes, out = {}, []
    for way_id, pts, tags in ways:
        refs = []
        for k, (x, y) in enumerate(pts):
            nid = f"{way_id}:{k}"
            nodes[nid] = _ll(x, y)
            refs.append(nid)
        out.append((way_id, refs, tags))
    return nodes, out, {w[0] for w in ways}, {}


#: A service road along the extended centreline, crossing the knoll with
#: ample blend room on both sides.
THROUGH_ROAD = [("road_a",
                 [(0.0, RUNWAY_LEN_M + 80.0), (0.0, RUNWAY_LEN_M + 700.0)],
                 {"highway": "service"})]


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(apc, "OLS_CUT_ENABLED", True)
    monkeypatch.setattr(apc, "OLS_ROAD_REGRADE_ENABLED", True)


def _patch_roads(monkeypatch, ways):
    from auto_patch import bridges
    net = road_network(ways)
    monkeypatch.setattr(bridges, "_load_tunnel_road_network",
                        lambda _layout: net)


def _emit(monkeypatch, ways, knoll_h=KNOLL_H_M):
    layout = make_layout()
    dem = FakeDEM()
    dem.raise_disc(KNOLL_X, KNOLL_Y, KNOLL_R_M, knoll_h)
    _patch_roads(monkeypatch, ways)
    n = ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
    return layout, dem, n


def decks(layout):
    return [s for s in layout.shapes
            if s.role == ROLE_SERVICE_JUNCTION and s.ref == ols.REF_ROAD]


def bands(layout):
    return [s for s in layout.shapes if s.role == ROLE_OLS_CUT]


def _ring(shape):
    coords = list(shape.polygon.exterior.coords)[:-1]
    alts = shape.node_altitudes[:len(coords)]
    return coords, alts


class TestDeckEmission:
    def test_road_through_the_island_grows_a_deck(self, gate_on,
                                                  monkeypatch):
        layout, _dem, n = _emit(monkeypatch, THROUGH_ROAD)
        assert n > 0
        dk = decks(layout)
        assert dk, "no deck emitted for a road crossing an admitted island"
        # The deck covers the knoll crossing on the extended centreline.
        union_covers = any(
            s.polygon.buffer(0.5).covers(Point(0.0, KNOLL_Y)) for s in dk)
        assert union_covers, "deck does not cover the island crossing"

    def test_every_deck_edge_obeys_the_service_road_grade_cap(
            self, gate_on, monkeypatch):
        layout, _dem, _n = _emit(monkeypatch, THROUGH_ROAD)
        dk = decks(layout)
        assert dk
        worst = 0.0
        for s in dk:
            coords, alts = _ring(s)
            m = len(coords)
            for i in range(m):
                (x0, y0), (x1, y1) = coords[i], coords[(i + 1) % m]
                dist = math.hypot(x1 - x0, y1 - y0)
                if dist < 2.0:
                    continue
                g = abs(alts[(i + 1) % m] - alts[i]) / dist
                worst = max(worst, g)
        # The road is STRAIGHT, so boundary edges parallel the spine and
        # carry the profile grade directly; +0.011 absorbs the 1 cm emit
        # quantum on both endpoints of a >= 2 m edge.  (On a CURVED way
        # the inside edge lawfully reads above the cap — the profile law
        # is a centreline law; see ``_emit_road_regrades``.)
        assert worst <= SERVICE_ROAD_MAX_GRADE + 0.011, worst

    def test_cut_only_and_blend_along_the_spine(self, gate_on, monkeypatch):
        """Along the spine chain the road never rides above the DEM, and
        at the graded segment's longitudinal extremes it sits ON the DEM
        (the blend)."""
        layout, dem, _n = _emit(monkeypatch, THROUGH_ROAD)
        dk = decks(layout)
        assert dk
        y_lo = min(s.polygon.bounds[1] for s in dk)
        y_hi = max(s.polygon.bounds[3] for s in dk)
        for s in dk:
            coords, alts = _ring(s)
            for (x, y), z in zip(coords, alts):
                if abs(x) > 0.5:
                    continue                    # spine chain only
                d = dem.alt_at_local(0.0, y)
                assert z <= d + 0.05, (x, y, z, d)
        # Blend: within a station of either extreme the road is at base
        # terrain level.
        for s in dk:
            coords, alts = _ring(s)
            for (x, y), z in zip(coords, alts):
                if y < y_lo + 5.0 or y > y_hi - 5.0:
                    assert abs(z - BASE_TERRAIN_M) <= 0.35, (y, z)

    def test_two_matching_halves_welded_on_the_spine(self, gate_on,
                                                     monkeypatch):
        """One half-shape each side of the spine; every coordinate shared
        between opposite-side shapes carries the SAME altitude (the weld
        that makes them one road surface)."""
        layout, _dem, _n = _emit(monkeypatch, THROUGH_ROAD)
        dk = decks(layout)
        left = [s for s in dk if s.polygon.centroid.x < 0.0]
        right = [s for s in dk if s.polygon.centroid.x > 0.0]
        assert left and right, "expected half-shapes on BOTH sides"
        vals = {}
        mismatches = []
        shared = 0
        for side, shapes in (("L", left), ("R", right)):
            for s in shapes:
                coords, alts = _ring(s)
                for (x, y), z in zip(coords, alts):
                    key = (round(x, 3), round(y, 3))
                    if key in vals and vals[key][0] != side:
                        shared += 1
                        if abs(vals[key][1] - z) > 1e-6:
                            mismatches.append((key, vals[key], z))
                    else:
                        vals.setdefault(key, (side, z))
        assert shared >= 10, f"halves share only {shared} spine vertices"
        assert not mismatches, mismatches[:5]

    def test_outer_edge_obeys_the_lateral_rule(self, gate_on, monkeypatch):
        """On the straight test road each station has a spine vertex
        (x≈0) and an outer vertex (|x|≈half width): the outer altitude
        stays within SERVICE_ROAD_MAX_TRANSVERSE x half-width of the
        spine altitude."""
        layout, _dem, _n = _emit(monkeypatch, THROUGH_ROAD)
        dk = decks(layout)
        assert dk
        spine_z = {}
        for s in dk:
            coords, alts = _ring(s)
            for (x, y), z in zip(coords, alts):
                if abs(x) < 0.5:
                    spine_z[round(y, 1)] = z
        half_w = max(abs(s.polygon.bounds[0]) for s in dk)
        cap = SERVICE_ROAD_MAX_TRANSVERSE * half_w
        for s in dk:
            coords, alts = _ring(s)
            for (x, y), z in zip(coords, alts):
                zs = spine_z.get(round(y, 1))
                if zs is None or abs(x) < half_w - 0.5:
                    continue
                assert abs(z - zs) <= cap + 0.03, (x, y, z, zs, cap)

    def test_follows_the_spine_past_the_ols_to_dem_ends(self, gate_on,
                                                        monkeypatch):
        """The whole test way lies inside the fan footprint, so the
        graded segment must follow it end to end (clamped at the way's
        ends, which sit on the DEM)."""
        layout, _dem, _n = _emit(monkeypatch, THROUGH_ROAD)
        dk = decks(layout)
        assert dk
        y_lo = min(s.polygon.bounds[1] for s in dk)
        y_hi = max(s.polygon.bounds[3] for s in dk)
        assert y_lo <= RUNWAY_LEN_M + 90.0, y_lo
        assert y_hi >= RUNWAY_LEN_M + 690.0, y_hi

    def test_deck_cuts_through_the_hill(self, gate_on, monkeypatch):
        """At the knoll centre the deck is metres below the DEM — the road
        goes THROUGH the hill, not over it."""
        layout, dem, _n = _emit(monkeypatch, THROUGH_ROAD)
        centre = Point(0.0, KNOLL_Y)
        got = None
        for s in decks(layout):
            if s.polygon.buffer(0.5).covers(centre):
                coords, alts = _ring(s)
                d2 = [(math.hypot(x - 0.0, y - KNOLL_Y), z)
                      for (x, y), z in zip(coords, alts)]
                got = min(d2)[1]
        assert got is not None
        assert got <= KNOLL_H_M - 4.0, got

    def test_deck_never_overlaps_the_banded_cut(self, gate_on, monkeypatch):
        layout, _dem, _n = _emit(monkeypatch, THROUGH_ROAD)
        for d in decks(layout):
            for b in bands(layout):
                inter = d.polygon.intersection(b.polygon)
                assert inter.area < 0.5, (d.ref, b.ref, inter.area)


class TestGatesAndRefusals:
    def test_subgate_off_restores_the_embankment(self, monkeypatch):
        monkeypatch.setattr(apc, "OLS_CUT_ENABLED", True)
        monkeypatch.setattr(apc, "OLS_ROAD_REGRADE_ENABLED", False)
        layout, _dem, n = _emit(monkeypatch, THROUGH_ROAD)
        assert not decks(layout)
        assert bands(layout), "bands must be unaffected by the sub-gate"

    def test_refused_island_grades_no_road(self, gate_on, monkeypatch):
        """Knoll deep enough to trip OLS_MAX_CUT_DEPTH_M: island refused,
        no bands — and no deck either (refused ground is untouchable)."""
        layout, _dem, n = _emit(monkeypatch, THROUGH_ROAD, knoll_h=40.0)
        assert not decks(layout)

    def test_way_ending_mid_hill_is_blend_refused(self, gate_on,
                                                  monkeypatch):
        stub = [("road_stub",
                 [(0.0, RUNWAY_LEN_M + 80.0), (0.0, KNOLL_Y)],
                 {"highway": "service"})]
        layout, _dem, _n = _emit(monkeypatch, stub)
        assert not decks(layout)

    def test_railway_keeps_its_embankment(self, gate_on, monkeypatch):
        rail = [("rail_a",
                 [(0.0, RUNWAY_LEN_M + 80.0), (0.0, RUNWAY_LEN_M + 700.0)],
                 {"railway": "rail"})]
        layout, _dem, _n = _emit(monkeypatch, rail)
        assert not decks(layout)

    def test_road_clear_of_any_island_emits_no_deck(self, gate_on,
                                                    monkeypatch):
        far = [("road_far",
                [(2000.0, RUNWAY_LEN_M + 80.0),
                 (2000.0, RUNWAY_LEN_M + 700.0)],
                {"highway": "service"})]
        layout, _dem, _n = _emit(monkeypatch, far)
        assert not decks(layout)


class TestNonFiniteAltitudeGuard:
    """The OLS-ROAD NaN class (census class C, SPLP 2026-08-01): the span
    grower extended over ``gov_any`` with no ``valid`` guard, swallowing
    stations the DEM/seam/refusal rules had excluded.  Those carry the
    ``+inf`` profile sentinel (``_road_regrade_profile`` never propagates
    across an invalid station) and ``depth`` is forced 0.0 there, so the
    blend refusal passed and the analytic blend computed ``inf - inf``
    = NaN vertex altitudes — 34 within + 14 cross law-true violations at
    SPLP, every one of them ``inf``-graded."""

    @staticmethod
    def _seam_band(monkeypatch, y_lo, y_hi):
        """Mark a BAND of the way invalid through the real invalidity
        seam (``_near_tile_seam``), which is the cause that actually
        fires at SPLP — measured from the assertion's own output: 97
        invalid stations, all ``_near_tile_seam``, none a DEM hole or a
        refused cell."""
        real = ols._near_tile_seam

        def fake(scene, x, y):
            if y_lo <= y <= y_hi:
                return True
            return real(scene, x, y)

        monkeypatch.setattr(ols, "_near_tile_seam", fake)

    def test_span_stops_at_an_invalid_station_and_stays_finite(
            self, gate_on, monkeypatch):
        """A span whose OLS-governed stretch runs INTO invalid ground
        stops at the last valid station: decks still emit, every emitted
        altitude is finite, and nothing is emitted beyond the band."""
        y_bad = RUNWAY_LEN_M + 500.0
        self._seam_band(monkeypatch, y_bad, RUNWAY_LEN_M + 10_000.0)
        layout, _dem, _n = _emit(monkeypatch, THROUGH_ROAD)
        dk = decks(layout)
        assert dk, "the guard must not suppress the feature itself"
        for s in dk:
            for z in s.node_altitudes:
                assert math.isfinite(z), (s.ref, s.node_altitudes)
        assert max(s.polygon.bounds[3] for s in dk) <= y_bad + 5.1, \
            "span grew past the first invalid station"

    def test_forced_infinite_profile_raises_with_the_piece_named(
            self, gate_on, monkeypatch):
        """FORCED-INVALID fixture: a ``+inf`` left in the spine profile
        inside a span (the exact shape of the sentinel leak) must fail
        LOUDLY at emission, never reach a shape."""
        real = ols._road_regrade_profile
        state = {"n": 0}

        def fake(ss, bound, valid, grade):
            z = real(ss, bound, valid, grade)
            state["n"] += 1
            if state["n"] == 1 and len(z) > 40:
                z = np.asarray(z, dtype=float).copy()
                z[len(z) // 2 + 8] = np.inf
            return z

        monkeypatch.setattr(ols, "_road_regrade_profile", fake)
        with pytest.raises(ols.NonFiniteRoadAltitude) as exc:
            _emit(monkeypatch, THROUGH_ROAD)
        msg = str(exc.value)
        assert "non-finite vertex altitude" in msg
        assert "road_a" in msg, msg          # the piece's way
        assert "span stations" in msg, msg   # the stations

    def test_assertion_message_names_the_invalidity_cause(self):
        """The message helper names WHICH of the three invalidity causes
        fired, per station, so the attribution is read off production's
        own output instead of reconstructed offline."""
        ss = np.arange(6, dtype=float) * 5.0
        valid = np.array([True, False, False, False, True, True])
        cause = [None, "sample_dem is None", "_near_tile_seam",
                 "grid.refused", None, None]
        coords = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]
        vals = [1.0, float("nan"), 3.0]
        msg = ols._nonfinite_road_vals_msg(
            "way_x", 1.0, 0, 5, ss, valid, cause, coords, vals,
            Polygon([(0, 0), (1, 0), (1, 1), (0, 0)]))
        assert "way_x" in msg
        assert "span stations [0, 5]" in msg
        assert "sample_dem is None" in msg
        assert "_near_tile_seam" in msg
        assert "grid.refused" in msg
        assert "vertex 1" in msg

    def test_clean_fixture_emits_finite_altitudes(self, gate_on,
                                                  monkeypatch):
        """Control: with no invalid ground the decks are unchanged and
        every altitude is finite (the assertion is silent)."""
        layout, _dem, _n = _emit(monkeypatch, THROUGH_ROAD)
        dk = decks(layout)
        assert dk
        assert all(math.isfinite(z) for s in dk for z in s.node_altitudes)
