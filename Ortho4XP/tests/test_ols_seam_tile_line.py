"""OLS cross-tile seam refusal measured at the TILE LINE — ``auto_patch.ols``.

The spec's determinism rule refuses whole any penetration island touching
"the covering DEM's tile-boundary edge", and ``_dem_raster`` implemented
that as the rows/columns where the raster WINDOW WAS CLAMPED by the DEM's
own extent.  An airport DEM routinely covers well past the tile it is
keyed to (measured SPLP -13/-078: 1088 m east of lon -77), so no island
near the seam was ever flagged — two of them were admitted, their bands
emitted ``ols_cut`` pieces, and the post-emit tile cut sliced those pieces
at the cut-back line, leaving four nodes 0.35-2.18 m BELOW the DEM the
10 m seam gap renders: the wall the rule exists to prevent.  Those nodes
cannot be DEM-pinned — an OLS cut is ``min(ceiling, DEM)``, so lifting one
to the DEM would UN-CUT a real obstruction — so the laws are reconciled
one step earlier: the OLS must not reach the seam at all.

Gate: ``config.OLS_SEAM_TILE_LINE_REFUSAL`` (env
``O4_OLS_SEAM_TILE_LINE_REFUSAL``), default ON; off ⇒ byte-identical to
the data-extent-only test.

Headless: a synthetic DEM whose frame straddles the tile line (exactly the
real geometry that hid the defect) and one runway laid parallel to it.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
from shapely.geometry import Polygon

from auto_patch import config as apc
from auto_patch import ols
from auto_patch.config import TILE_CUT_HALF_WIDTH_M
from auto_patch.layout import (
    BuiltShape, PavementLayout, R_EARTH, ROLE_OLS_CUT, ROLE_RUNWAY,
)

TILE_LAT, TILE_LON = -13, -78
#: The tile's own east boundary — the line ``tile_cut`` slices on.
SEAM_LON = TILE_LON + 1                       # -77
#: Anchor 150 m WEST of that meridian, so the seam falls in governed
#: transitional ground beside a runway laid parallel to it.
SEAM_OFFSET_M = 150.0
LAT0 = TILE_LAT + 0.5
LON0 = SEAM_LON - math.degrees(
    SEAM_OFFSET_M / (R_EARTH * math.cos(math.radians(LAT0))))
COS0 = math.cos(math.radians(LAT0))

RUNWAY_LEN_M = 3000.0
RUNWAY_WIDTH_M = 45.0
PAVEMENT_ALT_M = 6.2
BASE_TERRAIN_M = 5.0


class WideDEM:
    """A DEM whose frame STRADDLES the tile line, like every real airport
    DEM at a cross-tile airport — so the window is never clamped and the
    data-extent rule alone flags nothing."""

    def __init__(self, n: int = 1201, base: float = BASE_TERRAIN_M):
        # Tile-relative degrees: 0.30 deg of longitude centred on the tile's
        # east boundary (x == 1.0), 0.30 deg of latitude around the anchor.
        self.x0, self.x1 = 0.85, 1.15
        self.y0, self.y1 = 0.35, 0.65
        self.nxdem = self.nydem = n
        self.alt_dem = np.full((n, n), float(base), dtype=np.float32)
        self.nodata = -32768
        self.step_lon = (self.x1 - self.x0) / (n - 1)
        self.step_lat = (self.y1 - self.y0) / (n - 1)

    def alt(self, node):
        x, y = node
        j = int(round((min(max(float(x), self.x0), self.x1) - self.x0)
                      / self.step_lon))
        i = int(round((self.y1 - min(max(float(y), self.y0), self.y1))
                      / self.step_lat))
        return float(self.alt_dem[i, j])

    def _ij(self, x_m: float, y_m: float):
        lat = LAT0 + math.degrees(y_m / R_EARTH)
        lon = LON0 + math.degrees(x_m / (R_EARTH * COS0))
        return (int(round((self.y1 - (lat - TILE_LAT)) / self.step_lat)),
                int(round(((lon - TILE_LON) - self.x0) / self.step_lon)))

    def raise_disc(self, x_m: float, y_m: float, radius_m: float,
                   height_m: float):
        i, j = self._ij(x_m, y_m)
        rad = max(1, int(round(radius_m / 27.0)))
        n = self.nxdem
        ii, jj = np.ogrid[max(0, i - rad):min(n, i + rad + 1),
                          max(0, j - rad):min(n, j + rad + 1)]
        disc = (ii - i) ** 2 + (jj - j) ** 2 <= rad * rad
        block = self.alt_dem[max(0, i - rad):min(n, i + rad + 1),
                             max(0, j - rad):min(n, j + rad + 1)]
        block[disc] = float(height_m)


class FakeRunway:
    """The ``apt_dat_reader.Runway`` fields ``ols`` reads."""

    def __init__(self):
        self.desig_a, self.desig_b = "16R", "34L"
        self.lat_a, self.lon_a = LAT0, LON0
        self.lat_b = LAT0 + math.degrees(RUNWAY_LEN_M / R_EARTH)
        self.lon_b = LON0
        self.width_m = RUNWAY_WIDTH_M
        self.markings_a = self.markings_b = 3
        self.approach_lights_a = self.approach_lights_b = 1


def make_layout() -> PavementLayout:
    layout = PavementLayout(icao="TEST", anchor=(LAT0, LON0))
    half = 0.5 * RUNWAY_WIDTH_M
    ring = [(-half, 0.0), (half, 0.0), (half, RUNWAY_LEN_M),
            (-half, RUNWAY_LEN_M)]
    layout.shapes.append(BuiltShape(
        polygon=Polygon(ring + [ring[0]]), role=ROLE_RUNWAY,
        ref="16R/34L", altitude=PAVEMENT_ALT_M,
        node_altitudes=[PAVEMENT_ALT_M] * 5))
    return layout


def _scene_with_knolls(*, on_line=True, far=True, height=10.0):
    """A knoll ON the tile line and/or one well clear of it, both shallow
    enough that the mountain guard cannot be what refuses them."""
    layout = make_layout()
    dem = WideDEM()
    if on_line:
        # Beside the runway, straddling the tile line.
        dem.raise_disc(SEAM_OFFSET_M, 0.5 * RUNWAY_LEN_M, 60.0, height)
    if far:
        # In the approach fan off the 34L end, 270 m clear of the line.
        dem.raise_disc(-120.0, RUNWAY_LEN_M + 220.0, 70.0, 10.8)
    return layout, dem


def _islands(layout, dem, tile_lat=TILE_LAT, tile_lon=TILE_LON):
    return ols.ols_penetration_islands(layout, dem, tile_lat, tile_lon,
                                       [FakeRunway()])


# ── the mask itself ──────────────────────────────────────────────────────

class _StubScene:
    tile_lat, tile_lon = TILE_LAT, TILE_LON

    @staticmethod
    def to_m(lat, lon):
        return (math.radians(lon - LON0) * R_EARTH * COS0,
                math.radians(lat - LAT0) * R_EARTH)


class TestMask:
    def test_marks_a_band_about_the_tile_boundary_only(self):
        xs = np.array([[-1000.0, 0.0, SEAM_OFFSET_M - 40.0,
                        SEAM_OFFSET_M, SEAM_OFFSET_M + 40.0, 5000.0]])
        ys = np.zeros_like(xs)
        mask = ols._tile_line_seam_mask(_StubScene(), xs, ys, 27.0, 33.0)
        band = TILE_CUT_HALF_WIDTH_M + 27.0
        assert list(mask[0]) == [
            abs(x - SEAM_OFFSET_M) <= band for x in xs[0]], list(mask[0])

    def test_gate_off_is_inert(self, monkeypatch):
        monkeypatch.setattr(apc, "OLS_SEAM_TILE_LINE_REFUSAL", False)
        xs = np.array([[SEAM_OFFSET_M]])
        assert ols._tile_line_seam_mask(
            _StubScene(), xs, np.zeros_like(xs), 27.0, 33.0) is None


# ── the refusal ──────────────────────────────────────────────────────────

class TestTileLineRefusal:
    def test_the_data_extent_rule_alone_flags_nothing_here(self):
        """The premise: this DEM covers past the tile line, so the
        pre-existing clamp test is silent — which is exactly why the
        defect hid at SPLP."""
        layout, dem = _scene_with_knolls()
        islands = _islands(layout, dem)
        assert islands, "the knolls must be detected at all"
        assert not any(i["refused_reason"] == "tile_edge" for i in islands)

    def test_an_island_on_the_tile_line_is_refused_whole(self):
        layout, dem = _scene_with_knolls()
        islands = _islands(layout, dem)
        on_line = [i for i in islands
                   if min(abs(x - SEAM_OFFSET_M)
                          for x, _y in i["cells"]) <= TILE_CUT_HALF_WIDTH_M]
        assert on_line, "no island reached the tile line"
        for isl in on_line:
            assert isl["refused"] and isl["on_tile_edge"]
            assert isl["refused_reason"] == "tile_line"
            assert isl["max_depth_m"] < apc.OLS_MAX_CUT_DEPTH_M, (
                "the mountain guard must not be what refused it")

    def test_an_island_clear_of_the_line_is_still_admitted(self):
        """The trade is bounded: only the seam band is given up."""
        layout, dem = _scene_with_knolls()
        islands = _islands(layout, dem)
        clear = [i for i in islands
                 if min(abs(x - SEAM_OFFSET_M)
                        for x, _y in i["cells"]) > 100.0]
        assert clear, "no island away from the line"
        assert not any(i["refused"] for i in clear)

    def test_gate_off_admits_the_on_line_island(self, monkeypatch):
        monkeypatch.setattr(apc, "OLS_SEAM_TILE_LINE_REFUSAL", False)
        layout, dem = _scene_with_knolls()
        islands = _islands(layout, dem)
        assert islands and not any(i["refused"] for i in islands), (
            "gate OFF must restore the pre-fix verdict exactly")

    def test_both_tile_builds_refuse_the_same_island(self):
        """CROSS-TILE DETERMINISM: the test is a geometric one on the
        SHARED line, so the neighbour tile — for which the same meridian
        is its WEST boundary — reaches the same verdict."""
        layout, dem = _scene_with_knolls()
        west = _islands(layout, dem, tile_lon=TILE_LON)

        class _EastDEM(WideDEM):
            """The same terrain, keyed to the neighbour tile."""

            def __init__(self, src):
                super().__init__(n=src.nxdem)
                self.x0, self.x1 = src.x0 - 1.0, src.x1 - 1.0
                self.alt_dem = src.alt_dem

        east = ols.ols_penetration_islands(
            layout, _EastDEM(dem), TILE_LAT, TILE_LON + 1, [FakeRunway()])

        def _verdicts(islands):
            return sorted(
                (round(min(abs(x - SEAM_OFFSET_M) for x, _y in i["cells"])),
                 bool(i["refused"]))
                for i in islands)

        assert _verdicts(west) == _verdicts(east), (
            _verdicts(west), _verdicts(east))


class TestEmission:
    def test_no_emitted_piece_reaches_the_cut_back_line(self, monkeypatch):
        """The contract the defect broke: after the refusal no ``ols_cut``
        geometry survives near the seam, so the post-emit tile cut has
        nothing to slice there and mints no off-DEM cut-back node."""
        monkeypatch.setattr(apc, "OLS_CUT_ENABLED", True)
        layout, dem = _scene_with_knolls()
        ols.emit_ols_cuts(layout, dem, TILE_LAT, TILE_LON, [FakeRunway()])
        cut_back = SEAM_OFFSET_M - TILE_CUT_HALF_WIDTH_M
        for s in layout.shapes:
            if s.role != ROLE_OLS_CUT:
                continue
            for x, _y in s.polygon.exterior.coords:
                assert x < cut_back - 0.5, (
                    f"an OLS piece reached the cut-back line at x={x:.2f}")
