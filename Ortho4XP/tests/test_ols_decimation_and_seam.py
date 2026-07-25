"""OLS emission economy + cross-tile seam determinism — spec slices 8/9.

Spec: ``docs/specs/obstacle-limitation-surfaces-spec.md``.  Two OLS-flip
prerequisites, both headless and fixture-free (a synthetic 1-arc-second
DEM and a single-runway layout).

**Slice 8 — snap + decimation** (spec emission step 5).  Emitted vertices
used to be rounded to 0.1 m and the OLS group was never handed to
``emit_decimate.decimate_shape_group`` at all, so every 5 m station of the
largest-area law in the repo reached the triangulator.  Now a penetrating
vertex carries the ANALYTIC ceiling at a 1 cm quantum, a vertex grazing
the surface within ``adjacent_ground._CORRIDOR_SNAP_TOL_M`` snaps onto it,
and the group is decimated with the adjacent-ground band pattern
(``Z_TOL_BOUNDARY_M`` + the foreign-boundary protect predicate).

**Slice 9 — cross-tile seam determinism.**  ``elevation._sample_dem``
returns ``None`` out-of-tile and the pre-scan raster is clamped to the
covering DEM, so at a tile line each build sees only HALF an island —
while ``grade_law.ols_island_refused`` is an island-GLOBAL rule.  The two
builds could therefore reach OPPOSITE verdicts on one island and leave a
wall along the seam.  An island touching the raster's tile-boundary edge
is now refused whole from either side.
"""
import math

import numpy as np
import pytest
from shapely.geometry import Polygon

from auto_patch import config as apc
from auto_patch import ols
from auto_patch.adjacent_ground import _CORRIDOR_SNAP_TOL_M
from auto_patch.grade_law import ols_island_refused
from auto_patch.layout import (
    BuiltShape,
    PavementLayout,
    R_EARTH,
    ROLE_OLS_CUT,
    ROLE_RUNWAY,
)

LAT0 = -12.5
RUNWAY_LEN_M = 3000.0
RUNWAY_WIDTH_M = 45.0
# Deliberately OFF the 0.1 m grid: the analytic ceiling is then never a
# decimetre multiple, so a 0.1 m emit quantum is detectable.
PAVEMENT_ALT_M = 6.24
BASE_TERRAIN_M = 5.0
COS0 = math.cos(math.radians(LAT0))


# ──────────────────────────────────────────────────────────────────────
# Synthetic scene — an EAST-WEST runway whose approach fan runs east
# ──────────────────────────────────────────────────────────────────────
class TileDEM:
    """The read surface of ``O4_DEM_Utils.DEM`` that ``ols`` uses, for ONE
    1-degree tile: outside its own tile it simply has no cells, which is
    the whole point of the seam tests."""

    def __init__(self, tile_lat: int, tile_lon: int, lon0: float,
                 n: int = 3601, base: float = BASE_TERRAIN_M):
        self.tile_lat, self.tile_lon = int(tile_lat), int(tile_lon)
        self.lon0 = float(lon0)
        self.x0, self.x1, self.y0, self.y1 = 0.0, 1.0, 0.0, 1.0
        self.nxdem = self.nydem = int(n)
        self.alt_dem = np.full((n, n), float(base), dtype=np.float32)

    def _to_ll(self, x_m: float, y_m: float):
        return (LAT0 + math.degrees(y_m / R_EARTH),
                self.lon0 + math.degrees(x_m / (R_EARTH * COS0)))

    def _ij(self, lat: float, lon: float):
        nmax = self.nxdem - 1
        return ((1.0 - (lat - self.tile_lat)) * nmax,
                (lon - self.tile_lon) * nmax)

    def alt(self, node):
        x, y = node
        nmax = self.nxdem - 1
        x = min(max(float(x), 0.0), 1.0)
        y = min(max(float(y), 0.0), 1.0)
        return float(self.alt_dem[int(round((1.0 - y) * nmax)),
                                  int(round(x * nmax))])

    def raise_box(self, x0, x1, y0, y1, h) -> int:
        """Raise the cells of the local-metre box that EXIST in this tile."""
        ia, ja = self._ij(*self._to_ll(x0, y0))
        ib, jb = self._ij(*self._to_ll(x1, y1))
        i0, i1 = sorted((ia, ib))
        j0, j1 = sorted((ja, jb))
        n = self.nxdem
        i0, i1 = max(0, int(math.floor(i0))), min(n - 1, int(math.ceil(i1)))
        j0, j1 = max(0, int(math.floor(j0))), min(n - 1, int(math.ceil(j1)))
        if i1 < i0 or j1 < j0:
            return 0
        self.alt_dem[i0:i1 + 1, j0:j1 + 1] = float(h)
        return (i1 - i0 + 1) * (j1 - j0 + 1)


class FakeRunway:
    """``apt_dat_reader.Runway`` fields ``ols`` reads.  Laid east-west with
    its EAST end at local x = 0, so the 09 approach fan runs east."""

    def __init__(self, lon0: float):
        self.desig_a, self.desig_b = "27", "09"
        self.lat_a = self.lat_b = LAT0
        self.lon_a = lon0 - math.degrees(RUNWAY_LEN_M / (R_EARTH * COS0))
        self.lon_b = lon0
        self.width_m = RUNWAY_WIDTH_M
        self.markings_a = self.markings_b = 3
        self.approach_lights_a = self.approach_lights_b = 1


def make_layout(lon0: float) -> PavementLayout:
    layout = PavementLayout(icao="TEST", anchor=(LAT0, lon0))
    half = 0.5 * RUNWAY_WIDTH_M
    ring = [(-RUNWAY_LEN_M, -half), (0.0, -half), (0.0, half),
            (-RUNWAY_LEN_M, half)]
    layout.shapes.append(BuiltShape(
        polygon=Polygon(ring + [ring[0]]), role=ROLE_RUNWAY, ref="09/27",
        node_altitudes=[PAVEMENT_ALT_M] * 5))
    return layout


def emitted(layout):
    return [s for s in layout.shapes if s.role == ROLE_OLS_CUT]


def ring_nodes(shape) -> int:
    return len(list(shape.polygon.exterior.coords)) - 1


@pytest.fixture
def gate_on(monkeypatch):
    monkeypatch.setattr(apc, "OLS_CUT_ENABLED", True)


# Mid-tile scene: the OLS footprint is nowhere near a tile boundary, so
# the seam rule cannot fire and the decimation tests see a clean island.
MID_LON0 = -77.5
MID_TILE = (-13, -78)


def mid_scene(plateau=(200.0, 600.0, -120.0, 120.0), height=13.0):
    layout = make_layout(MID_LON0)
    dem = TileDEM(MID_TILE[0], MID_TILE[1], MID_LON0)
    dem.raise_box(plateau[0], plateau[1], plateau[2], plateau[3], height)
    return layout, dem, FakeRunway(MID_LON0)


def emit_mid(monkeypatch=None, *, decimate: bool = True, height: float = 13.0):
    layout, dem, rw = mid_scene(height=height)
    if not decimate:
        monkeypatch.setattr(ols, "decimate_shape_group",
                            lambda *a, **k: 0)
    n = ols.emit_ols_cuts(layout, dem, MID_TILE[0], MID_TILE[1], [rw])
    return layout, dem, n


# ══════════════════════════════════════════════════════════════════════
# Fixture guard
# ══════════════════════════════════════════════════════════════════════

def test_mid_tile_plateau_really_penetrates(gate_on):
    layout, dem, rw = mid_scene()
    islands = ols.ols_penetration_islands(layout, dem, *MID_TILE, [rw])
    assert islands, "the fixture must produce a penetration island"
    assert not any(i["refused"] for i in islands), (
        "a mid-tile island must be admitted — no seam rule, no mountain")
    assert not any(i["on_tile_edge"] for i in islands)


# ══════════════════════════════════════════════════════════════════════
# SLICE 8a — the emit quantum and the snap-to-bound
# ══════════════════════════════════════════════════════════════════════
class TestValueQuantumAndSnap:
    def _scene_and_fan(self):
        layout, dem, rw = mid_scene()
        scene = ols._Scene(layout, dem, MID_TILE[0], MID_TILE[1], [rw])
        fan = next(s for s in scene.surfaces
                   if s.kind == "approach" and s.u[0] > 0.5)
        return scene, fan

    def test_penetrating_vertex_carries_the_analytic_ceiling(self):
        """Not ``round(ceiling, 1)``: the emitted value must reproduce the
        law's own plane to the centimetre."""
        scene, fan = self._scene_and_fan()
        coords = [(200.0, -80.0), (400.0, 40.0), (620.0, 0.0)]
        xs = np.array([c[0] for c in coords])
        ys = np.array([c[1] for c in coords])
        ceil = scene.composed_ceiling(xs, ys, own=fan)
        assert not np.isnan(ceil).any()
        scene.sample_dem = lambda x, y: 500.0        # far above: cut
        vals = ols._value_ring(scene, fan, coords)
        assert vals is not None
        for v, c in zip(vals, ceil):
            assert abs(v - float(c)) <= 0.005

    def test_the_ceiling_is_not_on_the_decimetre_grid(self):
        """Guard on the guard: with a 6.24 m anchor the analytic ceiling is
        never a 0.1 m multiple, so the previous quantum WOULD have been
        detectable by the assertion above."""
        scene, fan = self._scene_and_fan()
        ceil = scene.composed_ceiling(np.array([400.0]), np.array([0.0]),
                                      own=fan)
        c = float(ceil[0])
        assert abs(c * 10.0 - round(c * 10.0)) > 0.05

    def test_a_dem_grazing_the_ceiling_snaps_onto_it(self):
        scene, fan = self._scene_and_fan()
        coords = [(300.0, 0.0)]
        ceil = float(scene.composed_ceiling(np.array([300.0]),
                                            np.array([0.0]), own=fan)[0])
        scene.sample_dem = lambda x, y: ceil - 0.5 * _CORRIDOR_SNAP_TOL_M
        vals = ols._value_ring(scene, fan, coords)
        assert vals[0] == pytest.approx(round(ceil, 2), abs=1e-9)

    def test_a_dem_below_the_snap_band_is_kept(self):
        """The snap is a triangle diet, not a fill law: past the band the
        vertex rides the terrain."""
        scene, fan = self._scene_and_fan()
        coords = [(300.0, 0.0)]
        ceil = float(scene.composed_ceiling(np.array([300.0]),
                                            np.array([0.0]), own=fan)[0])
        below = ceil - 5.0 * _CORRIDOR_SNAP_TOL_M
        scene.sample_dem = lambda x, y: below
        vals = ols._value_ring(scene, fan, coords)
        assert vals[0] == pytest.approx(round(below, 2), abs=1e-9)

    def test_the_snap_never_exceeds_its_own_tolerance(self, gate_on):
        """Whole-emitter invariant: no emitted vertex sits more than the
        snap band above the DEM under it (cut-only, to within the diet)."""
        layout, dem, n = emit_mid()
        assert n > 0
        for shape in emitted(layout):
            ring = list(shape.polygon.exterior.coords)[:-1]
            for (x, y), v in zip(ring, shape.node_altitudes):
                lat = LAT0 + math.degrees(y / R_EARTH)
                lon = MID_LON0 + math.degrees(x / (R_EARTH * COS0))
                d = dem.alt((lon - MID_TILE[1], lat - MID_TILE[0]))
                assert v <= d + _CORRIDOR_SNAP_TOL_M + 1e-6


# ══════════════════════════════════════════════════════════════════════
# SLICE 8b — the triangle diet
# ══════════════════════════════════════════════════════════════════════
class TestDecimation:
    def test_the_group_is_actually_decimated(self, gate_on, monkeypatch):
        undec, _dem, n_u = emit_mid(monkeypatch, decimate=False)
        monkeypatch.undo()
        monkeypatch.setattr(apc, "OLS_CUT_ENABLED", True)
        dec, _dem2, n_d = emit_mid()
        assert n_u == n_d > 0, "decimation must not change the piece count"
        before = sum(ring_nodes(s) for s in emitted(undec))
        after = sum(ring_nodes(s) for s in emitted(dec))
        assert before > 200, "the fixture must be node-heavy to be a test"
        assert after <= 0.45 * before, (
            f"planar OLS fan only decimated {before} -> {after} nodes")

    def test_a_planar_fan_piece_collapses_to_a_small_node_count(self,
                                                               gate_on):
        """Every piece here is a planar quad of the 2 % approach surface;
        after the diet none may carry more than a few dozen nodes (the
        floor is set by ``emit_decimate.MAX_CHORD_M``, not by the 5 m
        station march)."""
        layout, _dem, n = emit_mid()
        assert n > 0
        for shape in emitted(layout):
            assert ring_nodes(shape) <= 64, (
                f"{ring_nodes(shape)} nodes on a planar fan piece")

    def test_decimation_preserves_geometry_and_value_alignment(self,
                                                              gate_on,
                                                              monkeypatch):
        undec, _d, _n = emit_mid(monkeypatch, decimate=False)
        monkeypatch.undo()
        monkeypatch.setattr(apc, "OLS_CUT_ENABLED", True)
        dec, _d2, _n2 = emit_mid()
        area_u = sum(s.polygon.area for s in emitted(undec))
        area_d = sum(s.polygon.area for s in emitted(dec))
        assert area_d == pytest.approx(area_u, rel=1e-3)
        for shape in emitted(dec):
            assert shape.polygon.is_valid
            assert len(shape.node_altitudes) == len(
                shape.polygon.exterior.coords)
            assert shape.node_altitudes[0] == shape.node_altitudes[-1]

    def test_gate_off_stays_byte_inert(self, monkeypatch):
        monkeypatch.setattr(apc, "OLS_CUT_ENABLED", False)
        layout, dem, rw = mid_scene()
        before = list(layout.shapes)
        assert ols.emit_ols_cuts(layout, dem, MID_TILE[0], MID_TILE[1],
                                 [rw]) == 0
        assert layout.shapes == before


# ══════════════════════════════════════════════════════════════════════
# SLICE 9 — cross-tile seam determinism
# ══════════════════════════════════════════════════════════════════════
#
# EVIDENCE FORM (stated plainly): this is the SYNTHETIC RASTER fixture the
# brief allows, not a two-tile SPLP build.  It is strictly stronger as a
# determinism proof, because it pins the failure mode itself: the two tile
# builds' DEPTH-ONLY verdicts on the same physical island are constructed
# to DISAGREE (shallow west half, mountain east half), and the assertion
# is that the shipped verdict agrees anyway.
SEAM_LON0 = -77.003                      # the -77 tile line is ~326 m east
SEAM_TILE_A = (-13, -78)                 # the airport's own tile
SEAM_TILE_B = (-13, -77)                 # the tile the fan runs into
TILE_LINE_X = math.radians(-77.0 - SEAM_LON0) * R_EARTH * COS0


def seam_scene(height_a: float, height_b: float,
               box=(200.0, 600.0, -120.0, 120.0)):
    """ONE physical plateau spanning the tile line, seen from each side.

    Tile A's raster holds only the part west of the line, tile B's only
    the part east of it — exactly what each build's DEM gives it.
    """
    dem_a = TileDEM(SEAM_TILE_A[0], SEAM_TILE_A[1], SEAM_LON0)
    dem_b = TileDEM(SEAM_TILE_B[0], SEAM_TILE_B[1], SEAM_LON0)
    dem_a.raise_box(*box, height_a)
    dem_b.raise_box(*box, height_b)
    return dem_a, dem_b


def seam_prescan(dem, tile):
    layout = make_layout(SEAM_LON0)
    rw = FakeRunway(SEAM_LON0)
    islands = ols.ols_penetration_islands(layout, dem, tile[0], tile[1],
                                          [rw])
    return layout, islands


class TestSeamDeterminism:
    """Shallow (cut-worthy) west half, mountain (refuse-worthy) east half."""

    HEIGHT_A = 13.0          # ~4.5 m penetration  -> depth rule says CUT
    HEIGHT_B = 30.0          # ~18 m penetration   -> depth rule says REFUSE

    def _both(self):
        dem_a, dem_b = seam_scene(self.HEIGHT_A, self.HEIGHT_B)
        _la, ia = seam_prescan(dem_a, SEAM_TILE_A)
        _lb, ib = seam_prescan(dem_b, SEAM_TILE_B)
        assert len(ia) == len(ib) == 1
        return (dem_a, ia[0]), (dem_b, ib[0])

    def test_the_fixture_really_straddles_the_tile_line(self):
        assert 200.0 < TILE_LINE_X < 600.0

    def test_the_depth_only_verdicts_genuinely_disagree(self):
        """The failure this rule exists to prevent, made explicit: on the
        SAME physical island the two builds' island-global depth verdicts
        are opposite — cut on one side, refuse on the other, wall at the
        seam."""
        (_da, isl_a), (_db, isl_b) = self._both()
        assert ols_island_refused(isl_a["max_depth_m"]) is False
        assert ols_island_refused(isl_b["max_depth_m"]) is True

    def test_both_sides_refuse_the_straddling_island(self):
        (_da, isl_a), (_db, isl_b) = self._both()
        for isl in (isl_a, isl_b):
            assert isl["on_tile_edge"] is True
            assert isl["refused"] is True
            assert isl["refused_reason"] == "tile_edge"

    def test_neither_side_emits_geometry_at_the_seam(self, gate_on):
        """The shared-edge diff the brief asks for: both sides emit
        nothing for this island, so the seam geometry and values are
        trivially identical (an empty diff)."""
        dem_a, dem_b = seam_scene(self.HEIGHT_A, self.HEIGHT_B)
        for dem, tile in ((dem_a, SEAM_TILE_A), (dem_b, SEAM_TILE_B)):
            layout = make_layout(SEAM_LON0)
            n = ols.emit_ols_cuts(layout, dem, tile[0], tile[1],
                                  [FakeRunway(SEAM_LON0)])
            assert n == 0
            assert emitted(layout) == []

    def test_the_verdict_does_not_depend_on_which_half_is_the_mountain(self):
        """Swap the halves: the verdict must not move.  (Without the rule
        the two builds would swap which one cuts.)"""
        dem_a, dem_b = seam_scene(self.HEIGHT_B, self.HEIGHT_A)
        for dem, tile in ((dem_a, SEAM_TILE_A), (dem_b, SEAM_TILE_B)):
            _l, islands = seam_prescan(dem, tile)
            assert islands
            assert all(i["refused"] and i["refused_reason"] == "tile_edge"
                       for i in islands)

    def test_a_refused_seam_island_is_still_REPORTED(self):
        """Lockstep with ``verification.check_ols_surfaces``: refusal must
        be a reported exemption, not a silent drop."""
        (_da, isl_a), (_db, isl_b) = self._both()
        for isl in (isl_a, isl_b):
            assert isl["n_cells"] > 0
            assert isl["max_depth_m"] > 0.0
            assert isl["area_m2"] > 0.0

    def test_a_mid_tile_island_is_untouched_by_the_rule(self, gate_on):
        """Scope guard: the rule costs lawful cuts only AT a seam."""
        layout, dem, n = emit_mid()
        assert n > 0
        islands = ols.ols_penetration_islands(
            make_layout(MID_LON0), dem, MID_TILE[0], MID_TILE[1],
            [FakeRunway(MID_LON0)])
        assert islands
        assert all(i["refused_reason"] is None for i in islands)
