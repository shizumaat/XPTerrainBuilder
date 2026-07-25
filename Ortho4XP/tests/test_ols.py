"""Obstacle-limitation-surface CUT emitter — ``auto_patch.ols``.

Headless, fixture-free: a synthetic 1-arc-second DEM and a single-runway
layout, so every assertion is about the LAW and the emitter's contract
rather than about one airport's terrain.  Spec:
``docs/specs/obstacle-limitation-surfaces-spec.md`` (slices 2 + 3).

What is pinned here:

* the pre-scan reports islands, and reports REFUSED ones without cutting
  them (``grade_law.ols_island_refused``);
* the gate is byte-inert off;
* the vectorized ceiling field reproduces the SCALAR ``grade_law``
  functions exactly (a second law would be a second source of truth);
* ``None`` inside the handover ``S`` means "adjacent-ground owns that
  ground" — the flank band starts at ``S``, never inside it;
* CUT-ONLY: every emitted vertex is ``min(ceiling, DEM)`` — never above
  the DEM (no fill) and never above the ceiling (no under-cut);
* the daylight row meets the DEM;
* the approach fan is confined by the law's own splay.
"""
import math

import numpy as np
import pytest
from shapely.geometry import Polygon

from auto_patch import config as apc
from auto_patch import ols
from auto_patch.config import (
    CLEARANCE_STATION_STEP_M,
    OLS_APPROACH_DIVERGENCE,
    OLS_APPROACH_EMIT_REACH_M,
    OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M,
    OLS_APPROACH_SETBACK_M,
    OLS_MAX_CUT_DEPTH_M,
    OLS_OBSTRUCTION_THRESHOLD_M,
    OLS_TRANSITIONAL_EMIT_REACH_M,
)
from auto_patch.grade_law import (
    ols_approach_ceiling,
    ols_lateral_handover_distance_m,
    ols_transitional_ceiling,
)
from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    R_EARTH,
    ROLE_OLS_CUT,
    ROLE_RUNWAY,
)

RUNWAY_LEN_M = 3000.0            # code 4
RUNWAY_WIDTH_M = 45.0
PAVEMENT_ALT_M = 6.2             # the SPJC 16R origin-case anchor
BASE_TERRAIN_M = 5.0
# Mid-tile, so terrain on BOTH sides of the runway is inside the DEM.
LAT0, LON0 = -12.5, -77.5
TILE_LAT, TILE_LON = -13, -78
COS0 = math.cos(math.radians(LAT0))


# ──────────────────────────────────────────────────────────────────────
# Synthetic scene
# ──────────────────────────────────────────────────────────────────────
class FakeDEM:
    """The read surface of ``O4_DEM_Utils.DEM`` the module uses: the raw
    ``alt_dem`` raster + its tile-relative frame, and a scalar ``alt``."""

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

    def raise_disc(self, x_m: float, y_m: float, radius_m: float,
                   height_m: float):
        """Set a disc of cells around local-metre ``(x_m, y_m)``."""
        i, j = self._ij(x_m, y_m)
        rad = max(1, int(round(radius_m / self.posting_m)))
        n = self.nxdem
        ii, jj = np.ogrid[max(0, i - rad):min(n, i + rad + 1),
                          max(0, j - rad):min(n, j + rad + 1)]
        disc = (ii - i) ** 2 + (jj - j) ** 2 <= rad * rad
        block = self.alt_dem[max(0, i - rad):min(n, i + rad + 1),
                             max(0, j - rad):min(n, j + rad + 1)]
        block[disc] = float(height_m)

    def _ij(self, x_m: float, y_m: float):
        lat = LAT0 + math.degrees(y_m / R_EARTH)
        lon = LON0 + math.degrees(x_m / (R_EARTH * COS0))
        nmax = self.nxdem - 1
        return (int(round((1.0 - (lat - TILE_LAT)) * nmax)),
                int(round((lon - TILE_LON) * nmax)))

    def alt_at_local(self, x_m: float, y_m: float) -> float:
        i, j = self._ij(x_m, y_m)
        return float(self.alt_dem[i, j])


class FakeRunway:
    """The ``apt_dat_reader.Runway`` fields ``ols`` reads."""

    def __init__(self, markings: int = 3, lights: int = 1,
                 length_m: float = RUNWAY_LEN_M,
                 width_m: float = RUNWAY_WIDTH_M,
                 markings_b: int | None = None,
                 lights_b: int | None = None):
        self.desig_a, self.desig_b = "16R", "34L"
        self.lat_a, self.lon_a = LAT0, LON0
        self.lat_b = LAT0 + math.degrees(length_m / R_EARTH)
        self.lon_b = LON0
        self.width_m = width_m
        self.markings_a = markings
        self.markings_b = markings if markings_b is None else markings_b
        self.approach_lights_a = lights
        self.approach_lights_b = lights if lights_b is None else lights_b


def make_layout(length_m: float = RUNWAY_LEN_M,
                width_m: float = RUNWAY_WIDTH_M) -> PavementLayout:
    """A layout holding one flat runway rectangle at ``PAVEMENT_ALT_M``."""
    layout = PavementLayout(icao="TEST", anchor=(LAT0, LON0))
    half = 0.5 * width_m
    ring = [(-half, 0.0), (half, 0.0), (half, length_m), (-half, length_m)]
    layout.shapes.append(BuiltShape(
        polygon=Polygon(ring + [ring[0]]), role=ROLE_RUNWAY, ref="16R/34L",
        altitude=PAVEMENT_ALT_M,
        node_altitudes=[PAVEMENT_ALT_M] * 5))
    return layout


@pytest.fixture
def gate_on(monkeypatch):
    """``OLS_CUT_ENABLED`` is read at call time precisely so this works."""
    monkeypatch.setattr(apc, "OLS_CUT_ENABLED", True)


def emitted(layout):
    return [s for s in layout.shapes if s.role == ROLE_OLS_CUT]


# ──────────────────────────────────────────────────────────────────────
# The gate
# ──────────────────────────────────────────────────────────────────────
class TestGate:
    def test_gate_off_is_byte_inert(self, monkeypatch):
        """Gate OFF: no shapes, no mutation of the layout at all."""
        monkeypatch.setattr(apc, "OLS_CUT_ENABLED", False)
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 200.0, 60.0, 10.8)
        before = list(layout.shapes)
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) == 0
        assert layout.shapes == before

    def test_no_dem_is_a_no_op(self, gate_on):
        layout = make_layout()
        assert ols.emit_ols_cuts(layout, None, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) == 0
        assert emitted(layout) == []

    def test_prescan_is_not_gated(self, monkeypatch):
        """Slice 2 is a report-only pass and the validator reads it in
        lockstep, so the pre-scan runs whatever the emission gate says."""
        monkeypatch.setattr(apc, "OLS_CUT_ENABLED", False)
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 200.0, 60.0, 10.8)
        islands = ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        assert islands, "the pre-scan must report with the gate off"


# ──────────────────────────────────────────────────────────────────────
# Flat control — nothing to cut costs nothing
# ──────────────────────────────────────────────────────────────────────
class TestFlatControl:
    def test_flat_terrain_reports_no_islands(self):
        layout = make_layout()
        assert ols.ols_penetration_islands(
            layout, FakeDEM(), TILE_LAT, TILE_LON, [FakeRunway()]) == []

    def test_flat_terrain_emits_nothing(self, gate_on):
        layout = make_layout()
        before = list(layout.shapes)
        assert ols.emit_ols_cuts(layout, FakeDEM(), TILE_LAT, TILE_LON,
                                 [FakeRunway()]) == 0
        assert layout.shapes == before

    def test_terrain_just_under_the_trigger_emits_nothing(self, gate_on):
        """The trigger is ``OLS_OBSTRUCTION_THRESHOLD_M`` above the
        ceiling — terrain below it is lawful and untouched.  Sized against
        the ceiling at the disc's NEAREST edge (the lowest it sees)."""
        layout = make_layout()
        dem = FakeDEM()
        centre, radius = 500.0, 40.0
        ceiling = PAVEMENT_ALT_M + ols_approach_ceiling(
            4, "precision", centre - radius, 0.0)
        dem.raise_disc(60.0, RUNWAY_LEN_M + centre, radius,
                       ceiling + 0.5 * OLS_OBSTRUCTION_THRESHOLD_M)
        assert ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()]) == []
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) == 0


# ──────────────────────────────────────────────────────────────────────
# The vectorized ceiling field IS the scalar law
# ──────────────────────────────────────────────────────────────────────
class TestLawLockstep:
    def _scene(self):
        return ols._Scene(make_layout(), FakeDEM(), TILE_LAT, TILE_LON,
                          [FakeRunway()])

    def test_transitional_field_matches_the_scalar_law(self):
        scene = self._scene()
        flank = [s for s in scene.surfaces if s.kind == "transitional"][0]
        half = 0.5 * RUNWAY_WIDTH_M
        along = 0.5 * RUNWAY_LEN_M
        for d in np.arange(0.0, 500.0, 3.0):
            x = flank.origin[0] + flank.u[0] * along + flank.n[0] * d
            y = flank.origin[1] + flank.u[1] * along + flank.n[1] * d
            got = float(scene.surface_ceiling(flank, x, y))
            want = ols_transitional_ceiling(4, "precision", float(d), half)
            if want is None:
                assert math.isnan(got), f"d={d}: law says ungoverned"
            else:
                assert got == pytest.approx(PAVEMENT_ALT_M + want, abs=1e-6)

    def test_approach_field_matches_the_scalar_law(self):
        scene = self._scene()
        fan = [s for s in scene.surfaces if s.kind == "approach"][0]
        for beyond in np.arange(0.0, 1200.0, 7.0):
            for off in (0.0, 100.0, 160.0, 400.0):
                x = (fan.origin[0] + fan.u[0] * beyond + fan.n[0] * off)
                y = (fan.origin[1] + fan.u[1] * beyond + fan.n[1] * off)
                got = float(scene.surface_ceiling(fan, x, y))
                want = ols_approach_ceiling(4, "precision", float(beyond),
                                            off)
                if want is None:
                    assert math.isnan(got), f"s={beyond} off={off}"
                else:
                    assert got == pytest.approx(PAVEMENT_ALT_M + want,
                                                abs=1e-6)

    def test_mixed_class_flank_field_matches_the_composed_law(self):
        """One instrument end + one visual end: the flank surface is the
        ``min`` of both classes at every ``d``, and the vectorized field
        must reproduce that piecewise composition, not one class's line."""
        rw = FakeRunway(markings=3, markings_b=1, lights_b=0)
        scene = ols._Scene(make_layout(), FakeDEM(), TILE_LAT, TILE_LON,
                           [rw])
        flank = [s for s in scene.surfaces if s.kind == "transitional"][0]
        assert len(flank.pieces) == 2, "expected both classes to contribute"
        half = 0.5 * RUNWAY_WIDTH_M
        along = 0.5 * RUNWAY_LEN_M
        for d in np.arange(0.0, 500.0, 2.0):
            x = flank.origin[0] + flank.u[0] * along + flank.n[0] * d
            y = flank.origin[1] + flank.u[1] * along + flank.n[1] * d
            got = float(scene.surface_ceiling(flank, x, y))
            vals = [ols_transitional_ceiling(4, c, float(d), half)
                    for c in ("precision", "visual")]
            vals = [v for v in vals if v is not None]
            if not vals:
                assert math.isnan(got)
            else:
                assert got == pytest.approx(PAVEMENT_ALT_M + min(vals),
                                            abs=1e-6)

    def test_origin_case_arithmetic(self):
        """The SPJC 16R origin case, from the spec: a precision code-4 end
        anchored at 6.2 m has a 9.0 m ceiling 200 m beyond the end, and a
        10.8 m knoll 160 m off the extended centreline penetrates by
        1.8 m — inside the splay (half-width 171 m there)."""
        off = ols_approach_ceiling(4, "precision", 200.0, 160.0)
        assert off is not None
        assert PAVEMENT_ALT_M + off == pytest.approx(9.0, abs=0.01)
        assert 10.8 - (PAVEMENT_ALT_M + off) == pytest.approx(1.8, abs=0.01)


# ──────────────────────────────────────────────────────────────────────
# The handover: None inside S means adjacent-ground owns that ground
# ──────────────────────────────────────────────────────────────────────
class TestHandover:
    def test_law_is_none_inside_the_handover(self):
        half = 0.5 * RUNWAY_WIDTH_M
        s = ols_lateral_handover_distance_m(4, "precision", half)
        assert ols_transitional_ceiling(4, "precision", s - 0.01, half) is None
        assert ols_transitional_ceiling(4, "precision", s, half) is not None
        assert ols_transitional_ceiling(
            4, "precision", s + OLS_TRANSITIONAL_EMIT_REACH_M, half) is None

    def test_the_emitter_closure_is_none_inside_the_handover(self):
        """The closure ``_build_cut_bands`` marches with IS the law: it
        answers ``None`` inside ``S`` and beyond the reach, and the builder
        skips a ``None`` ceiling — that skip is what bounds the band."""
        half = 0.5 * RUNWAY_WIDTH_M
        closure, pieces = ols._flank_law(4, ("precision",), half)
        s = ols_lateral_handover_distance_m(4, "precision", half)
        assert closure(0.0) is None
        assert closure(s - 0.01) is None
        assert closure(s) == pytest.approx(pieces[0][1])
        assert closure(s + OLS_TRANSITIONAL_EMIT_REACH_M) is None
        # and it min-composes when the two ends differ in class
        mixed, _ = ols._flank_law(4, ("precision", "visual"), half)
        for d in (80.0, 120.0, 200.0, 300.0):
            vals = [ols_transitional_ceiling(4, c, d, half)
                    for c in ("precision", "visual")]
            vals = [v for v in vals if v is not None]
            assert mixed(d) == (min(vals) if vals else None)

    def test_flank_band_never_starts_inside_S(self, gate_on):
        """``_build_cut_bands`` skips a ``None`` ceiling, which IS the
        "adjacent-ground owns that ground" semantics: no emitted flank
        vertex may sit closer to the pavement edge than ``S``."""
        half = 0.5 * RUNWAY_WIDTH_M
        s = ols_lateral_handover_distance_m(4, "precision", half)
        layout = make_layout()
        dem = FakeDEM()
        # A knoll alongside the runway, straddling the handover: shallow
        # enough to be admitted (a 30 m ridge here would refuse).
        dem.raise_disc(half + s + 60.0, 0.5 * RUNWAY_LEN_M, 70.0, 12.0)
        islands = ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        assert islands and not islands[0]["refused"]
        assert islands[0]["surface"] == "transitional"
        n = ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                              [FakeRunway()])
        flanks = [sh for sh in emitted(layout)
                  if sh.ref == ols.REF_TRANSITIONAL]
        assert n and flanks, "expected a transitional band"
        for sh in flanks:
            for x, y in sh.polygon.exterior.coords:
                if 0.0 <= y <= RUNWAY_LEN_M:      # alongside the runway
                    d = abs(x) - half
                    assert d >= s - 0.05, (
                        f"flank vertex at d={d:.2f} m is inside S={s:.2f} m")


# ──────────────────────────────────────────────────────────────────────
# Cut-only
# ──────────────────────────────────────────────────────────────────────
class TestCutOnly:
    @pytest.fixture
    def knoll(self, gate_on):
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 220.0, 70.0, 10.8)
        n = ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                              [FakeRunway()])
        return layout, dem, n

    def test_the_knoll_is_cut(self, knoll):
        layout, _dem, n = knoll
        assert n > 0
        assert all(sh.ref == ols.REF_APPROACH for sh in emitted(layout))

    def test_no_vertex_rides_above_the_dem(self, knoll):
        """Never a FILL: a cut law may only lower terrain."""
        layout, dem, _n = knoll
        for sh in emitted(layout):
            for (x, y), a in zip(sh.polygon.exterior.coords,
                                 sh.node_altitudes):
                assert a <= dem.alt_at_local(x, y) + 0.06, (
                    f"({x:.1f},{y:.1f}) sits {a - dem.alt_at_local(x, y):.2f} "
                    "m ABOVE the DEM")

    def test_no_vertex_rides_above_the_ceiling(self, knoll):
        """And never an UNDER-cut: min(ceiling, DEM) is the whole rule."""
        layout, _dem, _n = knoll
        scene = ols._Scene(layout, FakeDEM(), TILE_LAT, TILE_LON,
                           [FakeRunway()])
        for sh in emitted(layout):
            coords = list(sh.polygon.exterior.coords)
            xs = np.array([c[0] for c in coords])
            ys = np.array([c[1] for c in coords])
            ceil = scene.composed_ceiling(xs, ys)
            for a, c in zip(sh.node_altitudes, ceil):
                if not math.isnan(c):
                    assert a <= c + 0.06

    def test_the_cut_actually_reaches_the_ceiling(self, knoll):
        """At least one vertex sits ON the ceiling — otherwise the band is
        a DEM tracing, not a cut."""
        layout, dem, _n = knoll
        cut = 0
        for sh in emitted(layout):
            for (x, y), a in zip(sh.polygon.exterior.coords,
                                 sh.node_altitudes):
                if dem.alt_at_local(x, y) - a > 0.5:
                    cut += 1
        assert cut > 0


# ──────────────────────────────────────────────────────────────────────
# Daylight — the outer row meets the DEM
# ──────────────────────────────────────────────────────────────────────
class TestDaylight:
    def test_outer_row_meets_the_dem(self, gate_on):
        """The band daylights where the ceiling meets the terrain: the
        emitted footprint may not extend past the penetration by more than
        the trigger allows, so its outermost vertices sit ON the DEM."""
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(100.0, RUNWAY_LEN_M + 250.0, 70.0, 10.8)
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) > 0
        on_dem = 0
        for sh in emitted(layout):
            for (x, y), a in zip(sh.polygon.exterior.coords,
                                 sh.node_altitudes):
                if abs(a - dem.alt_at_local(x, y)) <= 0.06:
                    on_dem += 1
        assert on_dem > 0, "no vertex daylights onto the DEM"

    def test_the_band_does_not_run_the_whole_reach(self, gate_on):
        """Island scoping: a single knoll must not drag the band out to
        ``OLS_APPROACH_EMIT_REACH_M``."""
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(100.0, RUNWAY_LEN_M + 250.0, 70.0, 10.8)
        ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        far = max((max(y for _x, y in sh.polygon.exterior.coords)
                   for sh in emitted(layout)), default=0.0)
        assert far < RUNWAY_LEN_M + OLS_APPROACH_EMIT_REACH_M


# ──────────────────────────────────────────────────────────────────────
# Mountain refusal
# ──────────────────────────────────────────────────────────────────────
class TestRefusal:
    def _mountain(self):
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 300.0, 150.0,
                       PAVEMENT_ALT_M + 3.0 * OLS_MAX_CUT_DEPTH_M)
        return layout, dem

    def test_a_deep_island_is_reported_refused(self):
        layout, dem = self._mountain()
        islands = ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        assert islands, "the mountain must still be REPORTED"
        assert all(i["refused"] for i in islands)
        assert max(i["max_depth_m"] for i in islands) > OLS_MAX_CUT_DEPTH_M

    def test_a_refused_island_emits_nothing(self, gate_on):
        layout, dem = self._mountain()
        before = list(layout.shapes)
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) == 0
        assert layout.shapes == before

    def test_a_shallow_island_is_admitted(self):
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 220.0, 70.0, 10.8)
        islands = ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        assert islands and not any(i["refused"] for i in islands)
        assert islands[0]["max_depth_m"] <= OLS_MAX_CUT_DEPTH_M

    def test_refused_ground_is_untouched_beside_an_admitted_island(
            self, gate_on):
        """A mountain and a knoll on the same fan: the knoll is cut, the
        mountain is not — no piece may cover a refused cell."""
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(-140.0, RUNWAY_LEN_M + 500.0, 130.0,
                       PAVEMENT_ALT_M + 3.0 * OLS_MAX_CUT_DEPTH_M)
        dem.raise_disc(120.0, RUNWAY_LEN_M + 220.0, 70.0, 10.8)
        islands = ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        assert any(i["refused"] for i in islands)
        assert any(not i["refused"] for i in islands)
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) > 0
        refused_cells = [xy for i in islands if i["refused"]
                         for xy in i["cells"]]
        for sh in emitted(layout):
            for x, y in refused_cells:
                assert not sh.polygon.contains(
                    Polygon([(x - 1, y - 1), (x + 1, y - 1),
                             (x + 1, y + 1), (x - 1, y + 1)]).centroid), (
                    "an emitted piece covers refused ground")


# ──────────────────────────────────────────────────────────────────────
# The approach fan's splay
# ──────────────────────────────────────────────────────────────────────
class TestFanSplay:
    def test_law_boundary_is_exact(self):
        inner = OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M["precision"][4]
        div = OLS_APPROACH_DIVERGENCE["precision"]
        s = 140.0
        beyond = OLS_APPROACH_SETBACK_M + s
        half = inner + div * s
        assert ols_approach_ceiling(4, "precision", beyond, half) is not None
        assert ols_approach_ceiling(4, "precision", beyond,
                                    half + 0.01) is None

    def test_terrain_outside_the_splay_is_not_cut(self, gate_on):
        """A knoll BESIDE the fan (outside the splay and outside the
        transitional's along-runway span) is nobody's business."""
        inner = OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M["precision"][4]
        div = OLS_APPROACH_DIVERGENCE["precision"]
        s = 240.0
        outside = inner + div * s + 120.0
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(outside,
                       RUNWAY_LEN_M + OLS_APPROACH_SETBACK_M + s, 50.0, 30.0)
        assert ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()]) == []
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) == 0

    def test_emitted_fan_stays_inside_the_splay(self, gate_on):
        inner = OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M["precision"][4]
        div = OLS_APPROACH_DIVERGENCE["precision"]
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 220.0, 70.0, 10.8)
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) > 0
        for sh in emitted(layout):
            if sh.ref != ols.REF_APPROACH:
                continue
            for x, y in sh.polygon.exterior.coords:
                beyond = y - RUNWAY_LEN_M
                if beyond <= 0:
                    continue
                s = beyond - OLS_APPROACH_SETBACK_M
                half = inner + div * max(s, 0.0)
                assert abs(x) <= half + 0.5, (
                    f"fan vertex at ({x:.1f},{y:.1f}) is outside the splay "
                    f"(half={half:.1f} m)")


# ──────────────────────────────────────────────────────────────────────
# Island bookkeeping
# ──────────────────────────────────────────────────────────────────────
class TestIslandReport:
    def test_island_dict_shape(self):
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 220.0, 70.0, 10.8)
        islands = ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        assert len(islands) == 1
        isl = islands[0]
        for key in ("surface", "desig", "max_depth_m", "refused", "cells",
                    "area_m2"):
            assert key in isl
        assert isl["surface"] == "approach"
        assert isl["desig"] == "34L"
        assert isl["area_m2"] > 0.0
        assert len(isl["cells"]) == isl["n_cells"]

    def test_two_separate_knolls_are_two_islands(self):
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(-130.0, RUNWAY_LEN_M + 200.0, 45.0, 10.8)
        dem.raise_disc(130.0, RUNWAY_LEN_M + 600.0, 45.0, 22.0)
        islands = ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        assert len(islands) == 2
        assert islands[0]["max_depth_m"] >= islands[1]["max_depth_m"]

    def test_no_runways_reports_nothing(self):
        layout = PavementLayout(icao="TEST", anchor=(LAT0, LON0))
        assert ols.ols_penetration_islands(
            layout, FakeDEM(), TILE_LAT, TILE_LON, []) == []

    def test_falls_back_to_the_emitted_runway_rects(self, gate_on):
        """No apt.dat metadata: the runway is derived from the emitted
        rects and both ends classify ``non_precision`` — the stricter
        instrument geometry, which is the safe direction."""
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 220.0, 70.0, 10.8)
        islands = ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, None)
        assert islands, "the fallback path must still find the knoll"
        scene = ols._Scene(layout, dem, TILE_LAT, TILE_LON, None)
        assert len(scene.runways) == 1
        rw = scene.runways[0]
        assert rw.class_a == rw.class_b == "non_precision"
        assert rw.length == pytest.approx(RUNWAY_LEN_M, abs=1.0)
        assert 2 * rw.half_width == pytest.approx(RUNWAY_WIDTH_M, abs=1.0)
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON, None) > 0


# ──────────────────────────────────────────────────────────────────────
# Clip discipline
# ──────────────────────────────────────────────────────────────────────
class TestClipDiscipline:
    def test_pieces_do_not_overlap_existing_shapes(self, gate_on):
        layout = make_layout()
        # A pre-existing shape squarely in the fan's path.
        blocker = Polygon([(60.0, RUNWAY_LEN_M + 100.0),
                           (180.0, RUNWAY_LEN_M + 100.0),
                           (180.0, RUNWAY_LEN_M + 180.0),
                           (60.0, RUNWAY_LEN_M + 180.0)])
        layout.shapes.append(BuiltShape(polygon=blocker, role="graded_strip",
                                        ref="blocker", altitude=6.0))
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 260.0, 70.0, 10.8)
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) > 0
        for sh in emitted(layout):
            assert sh.polygon.intersection(blocker).area < 1e-6

    def test_pieces_do_not_overlap_each_other(self, gate_on):
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 220.0, 90.0, 10.8)
        ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        pieces = [sh.polygon for sh in emitted(layout)]
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                assert pieces[i].intersection(pieces[j]).area < 1e-6

    def test_node_altitudes_close_the_ring(self, gate_on):
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(120.0, RUNWAY_LEN_M + 220.0, 70.0, 10.8)
        ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        for sh in emitted(layout):
            assert sh.node_altitudes is not None
            assert len(sh.node_altitudes) == len(sh.polygon.exterior.coords)
            assert sh.node_altitudes[0] == sh.node_altitudes[-1]

    def test_step_and_reach_come_from_config(self):
        """Every rule value is config's; nothing is hard-coded here."""
        assert ols._BAND_SPLIT_M == 10.0 * CLEARANCE_STATION_STEP_M
        assert ols._PRESCAN_POSTING_M == CLEARANCE_STATION_STEP_M

    def test_consecutive_slabs_leave_no_groove(self, gate_on):
        """Slabs abut: the weld ruling forbids a strip of raw DEM between
        two active cut bands, so every piece touches a neighbour (or is the
        only one)."""
        layout = make_layout()
        dem = FakeDEM()
        dem.raise_disc(90.0, RUNWAY_LEN_M + 260.0, 120.0, 12.5)
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) > 0
        pieces = [sh.polygon for sh in emitted(layout)]
        if len(pieces) < 2:
            pytest.skip("single piece — nothing to abut")
        for i, p in enumerate(pieces):
            gaps = [p.distance(q) for j, q in enumerate(pieces) if j != i]
            assert min(gaps) <= 1e-6, (
                f"piece {i} stands {min(gaps):.4f} m off every neighbour")


# ──────────────────────────────────────────────────────────────────────
# The slab march (the daylight-bench interaction)
# ──────────────────────────────────────────────────────────────────────
class TestSlabMarch:
    def test_slabs_cover_the_whole_reach_and_no_more(self):
        scene = ols._Scene(make_layout(), FakeDEM(), TILE_LAT, TILE_LON,
                           [FakeRunway()])
        for srf in scene.surfaces:
            slabs = list(ols._surface_slabs(srf))
            assert slabs and slabs[0][0] == 0.0
            far = slabs[-1][0] + slabs[-1][1]
            assert far == pytest.approx(srf.d_hi - srf.d_lo, abs=1e-6)

    def test_the_outermost_slab_stays_inside_the_law(self):
        """The last slab may not overshoot the law's reach — the closure
        would answer ``None`` there and the whole slab would drop out."""
        scene = ols._Scene(make_layout(), FakeDEM(), TILE_LAT, TILE_LON,
                           [FakeRunway()])
        for srf in scene.surfaces:
            d0, cap = list(ols._surface_slabs(srf))[-1]
            if srf.kind == "transitional":
                _st, _a, _o, closure = ols._flank_slab(srf, d0)
            else:
                _st, _a, _o, closure = ols._fan_slab(srf, d0)
            assert closure(cap - 1e-3) is not None
            assert closure(0.0) is not None

    def test_a_long_island_is_cut_over_several_slabs(self, gate_on):
        """The origin geometry: a knoll whose along-track extent far
        exceeds its lateral frontage.  A single full-reach march benches
        that away; the slab march cuts it."""
        layout = make_layout()
        dem = FakeDEM()
        # ~64 m of frontage, ~230 m of along-track extent, climbing faster
        # than the 2 % approach slope so it penetrates the whole way.
        for k in range(6):
            dem.raise_disc(110.0, RUNWAY_LEN_M + 140.0 + 40.0 * k, 32.0,
                           9.5 + 1.2 * k)
        islands = ols.ols_penetration_islands(
            layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        assert islands and not any(i["refused"] for i in islands)
        assert ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON,
                                 [FakeRunway()]) > 0
        ys = [y for sh in emitted(layout)
              for _x, y in sh.polygon.exterior.coords]
        assert max(ys) - min(ys) > 100.0, (
            "the emitted footprint collapsed to one slab — the daylight "
            "bench is eating the island again")
