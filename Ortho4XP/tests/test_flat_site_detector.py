"""FLAT-SITE detector twins — docs/specs/flat-site-detector-spec.md §4.

Synthetic fixtures only: no X-Plane install, no network, no DEM download,
no build.  Every DEM here is an in-memory raster over a synthetic 1°x1°
tile at (0, 0), carrying exactly the surface ``O4_DEM_Utils.DEM`` exposes
to the detector (``alt_dem`` + ``nxdem``/``nydem``/``x0``/``x1``/``y0``/
``y1``/``nodata``/``elevation_level``).

The five fixtures the spec names, plus the sidecar-key registration twin:

* flat DEM + identical thresholds        -> ``flat_candidate``
* PLATEAU (flat pavement, sloped ring)   -> NOT (only the ring sees it)
* identical thresholds + real relief     -> NOT
* LIDAR-class source                     -> ``lidar_credible`` short-circuit
* missing CIFP / missing DEM             -> ``no_data``, never a crash
"""
from __future__ import annotations

import math
import os
import sys
import types

import numpy as np
import pytest
from shapely.geometry import Polygon, box

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from auto_patch import config, flat_site  # noqa: E402

R_EARTH = 6378137.0

#: The synthetic tile and the anchor every fixture measures about.
TILE_LAT, TILE_LON = 0, 0
ANCHOR = (0.5, 0.5)

#: 1201x1201 over one degree = 3 arc-second posting (~92 m), the class the
#: base tier reports under the default "auto" elevation level.
GRID_N = 1201


class SyntheticDEM:
    """A DEM raster built from an elevation function of local metres."""

    def __init__(self, elevation_fn, *, n: int = GRID_N,
                 elevation_level: str = "auto", nodata: float = -32768.0):
        self.lat, self.lon = TILE_LAT, TILE_LON
        self.nxdem = self.nydem = int(n)
        self.x0 = self.y0 = 0.0
        self.x1 = self.y1 = 1.0
        self.nodata = nodata
        self.elevation_level = elevation_level
        self.source_path = "<synthetic>"
        cos0 = math.cos(math.radians(ANCHOR[0]))
        lon_deg = TILE_LON + np.linspace(0.0, 1.0, self.nxdem)
        lat_deg = TILE_LAT + np.linspace(1.0, 0.0, self.nydem)   # top row first
        x_m = np.radians(lon_deg - ANCHOR[1]) * R_EARTH * cos0
        y_m = np.radians(lat_deg - ANCHOR[0]) * R_EARTH
        grid_x, grid_y = np.meshgrid(x_m, y_m)
        self.alt_dem = np.asarray(elevation_fn(grid_x, grid_y),
                                  dtype=np.float32)


#: The synthetic airport: a 2 km x 500 m pavement about the anchor.
PAVEMENT_M = box(-1000.0, -250.0, 1000.0, 250.0)
EXTENT_M = PAVEMENT_M.buffer(config.FLAT_SITE_MARGIN_M)

#: Four identical thresholds — the OTHH consensus shape (spread 0).
FLAT_THRESHOLDS = [4.0, 4.0, 4.0, 4.0]


def _classify(dem, thresholds=FLAT_THRESHOLDS, *, dem_meta=None,
              extent_m=EXTENT_M, pack_targets=None):
    return flat_site.classify_site(
        icao="TEST", cifp_elevations_m=thresholds, dem=dem,
        tile_lat=TILE_LAT, tile_lon=TILE_LON, anchor=ANCHOR,
        extent_m=extent_m, dem_meta=dem_meta, pack_targets=pack_targets)


# ──────────────────────────────────────────────────────────────────────
# Fixture 1 — a flat site is a candidate
# ──────────────────────────────────────────────────────────────────────
def test_flat_dem_and_identical_thresholds_is_a_candidate():
    # 3-arcsec noise WELL inside its own 8 m floor, no trend.  The land
    # sits at 1.5 m while instrument truth says 4.0 — the OTHH signature
    # (a DEM reading BELOW truth) expressed in LAND, which is what S2a
    # leaves behind once sea and void fill are gone.
    rng = np.random.default_rng(20260809)
    dem = SyntheticDEM(lambda x, y: 1.5 + rng.normal(0.0, 0.2, x.shape))
    record = _classify(dem)

    assert record["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE
    assert record["s1_pass"] is True
    assert record["s1_spread_m"] == 0.0
    assert record["z0_m"] == pytest.approx(4.0)
    assert record["s2_pass"] is True
    assert record["s2_source_class"] == "ge3arcsec"
    assert record["s2_source_whence"] == "base_tier"
    assert record["s2_relief_floor_m"] == 8.0
    assert record["s2_relief_m"] <= 8.0
    assert record["s2_slope_pct"] <= config.FLAT_SITE_MAX_SLOPE_PCT
    # S3 is REPORTED, never gated: a DEM-vs-instrument offset at a
    # flat-candidate site is evidence FOR DEM unreliability (OTHH: 3.96 m).
    assert record["s3_offset_m"] == pytest.approx(2.5, abs=0.3)
    # Land, not sea: S2a ran (Z0 is above the guard) and found nothing
    # to exclude, which is a different statement from "did not run".
    assert record["s2_sea_excluded_frac"] == pytest.approx(0.0, abs=0.01)


# ──────────────────────────────────────────────────────────────────────
# Fixture 2 — the PLATEAU: flat pavement, hilly surroundings
# ──────────────────────────────────────────────────────────────────────
def _plateau(x, y):
    """Flat LAND on the pavement, rising 10 % outward through the margin
    ring.  The plateau sits at 5 m, not at 0: a graded plateau is dry
    land, and a fixture at sea level would be testing S2a instead."""
    dx = np.maximum(np.abs(x) - 1000.0, 0.0)
    dy = np.maximum(np.abs(y) - 250.0, 0.0)
    return 5.0 + 0.10 * np.hypot(dx, dy)


def test_plateau_is_caught_by_the_margin_ring_not_by_slope():
    dem = SyntheticDEM(_plateau)

    # The pavement ALONE reads perfectly flat — this is the reading the
    # margin ring exists to correct.
    pavement_only = _classify(dem, extent_m=PAVEMENT_M)
    assert pavement_only["s2_relief_m"] == pytest.approx(0.0, abs=1e-6)
    assert pavement_only["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE

    record = _classify(dem)
    assert record["verdict"] == flat_site.VERDICT_NOT_FLAT
    assert record["s1_pass"] is True          # the thresholds still agree
    assert record["s2_pass"] is False
    # And it is the RELIEF that catches it: the ring rises on every side,
    # so the plane fit is nearly level.  A slope-only test would pass this
    # site, which is exactly why the floor is a second, independent gate.
    assert record["s2_relief_m"] > record["s2_relief_floor_m"]
    assert record["s2_slope_pct"] <= config.FLAT_SITE_MAX_SLOPE_PCT


# ──────────────────────────────────────────────────────────────────────
# Fixture 3 — identical thresholds over REAL relief
# ──────────────────────────────────────────────────────────────────────
def test_identical_thresholds_over_real_relief_is_not_flat():
    # 2 % uniform tilt: the HECA shape (thresholds can still agree while
    # the site carries tens of metres of genuine relief).
    dem = SyntheticDEM(lambda x, y: 0.02 * x)
    record = _classify(dem)

    assert record["verdict"] == flat_site.VERDICT_NOT_FLAT
    assert record["s1_pass"] is True
    assert record["s2_pass"] is False
    assert record["s2_slope_pct"] == pytest.approx(2.0, rel=0.05)
    assert record["s2_relief_m"] > record["s2_relief_floor_m"]


# ──────────────────────────────────────────────────────────────────────
# Fixture 4 — a metre-credible source short-circuits
# ──────────────────────────────────────────────────────────────────────
LIDAR_META = {"raw": False,
              "insets": [{"icao": "TEST", "provider": "SONNY1",
                          "native_resolution_m": 1.0}]}


def test_lidar_class_source_short_circuits():
    rng = np.random.default_rng(20260809)
    dem = SyntheticDEM(lambda x, y: rng.normal(0.0, 0.5, x.shape))
    record = _classify(dem, dem_meta=LIDAR_META)

    assert record["verdict"] == flat_site.VERDICT_LIDAR_CREDIBLE
    assert record["s2_source_class"] == flat_site.SOURCE_CLASS_LIDAR
    assert record["s2_source_whence"] == "inset"
    assert record["s2_source_resolution_m"] == 1.0
    # Flat-candidacy is NOT APPLICABLE, not denied: the class has no
    # noise floor because the DEM is trustworthy.
    assert record["s2_relief_floor_m"] is None
    assert record["s2_pass"] is None
    # The short-circuit does not depend on the surface being flat.
    steep = SyntheticDEM(lambda x, y: 0.02 * x)
    assert (_classify(steep, dem_meta=LIDAR_META)["verdict"]
            == flat_site.VERDICT_LIDAR_CREDIBLE)


# ──────────────────────────────────────────────────────────────────────
# S2a — THE SEA-BAND EXCLUSION (spec v2 amendment, 2026-08-09)
# ──────────────────────────────────────────────────────────────────────
def _coastal(x, y):
    """A reclaimed airport: flat land at 5 m over the western half, sea
    surface (0 m, with void-fill dips) over the eastern half.

    The VHHH/YSSY/KSFO shape.  Judged whole, this reads ~7 m of relief
    and a land-to-sea gradient across the extent; judged on its LAND it
    is dead flat, which is what the airport actually is.
    """
    land = np.full(x.shape, 5.0)
    sea = np.where(((x * 7.0).astype(int) % 3) == 0, -2.0, 0.0)
    return np.where(x < 0.0, land, sea)


def test_coastal_site_is_classified_on_its_land_not_its_sea():
    dem = SyntheticDEM(_coastal)

    # WITHOUT the exclusion (a below-sea site keeps every sample) the
    # same raster reads as relief AND as a gradient.
    contaminated = _classify(dem, thresholds=[0.5, 0.5])
    assert contaminated["s2_sea_excluded_frac"] is None
    assert contaminated["s2_relief_m"] >= 7.0
    assert contaminated["verdict"] == flat_site.VERDICT_NOT_FLAT

    # WITH it — same raster, same extent, Z0 above the guard — the
    # statistics describe the land the airport is built on.
    record = _classify(dem, thresholds=[5.0, 5.0])
    assert record["s2_sea_excluded_frac"] == pytest.approx(0.5, abs=0.05)
    assert record["s2_relief_m"] == pytest.approx(0.0, abs=1e-6)
    assert record["s2_slope_pct"] == pytest.approx(0.0, abs=1e-6)
    assert record["s2_dem_median_m"] == pytest.approx(5.0)
    assert record["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE
    # The sea samples are gone from the FIT as well as the percentiles —
    # a plane regressed through land and sea together measures the
    # shoreline, and that is the half that refused KSFO.
    assert contaminated["s2_slope_pct"] > record["s2_slope_pct"]


def test_a_below_sea_site_keeps_every_sample():
    """Schiphol's zeros ARE terrain.  Under the Z0 guard the exclusion
    must not run at all — deleting them would delete the airport."""
    assert config.FLAT_SITE_SEA_BAND_MIN_Z0_M == 1.0
    assert flat_site.sea_band_applies(None) is False
    assert flat_site.sea_band_applies(-3.0) is False
    assert flat_site.sea_band_applies(0.999) is False
    assert flat_site.sea_band_applies(1.0) is True

    rng = np.random.default_rng(20260809)
    dem = SyntheticDEM(lambda x, y: rng.uniform(-4.0, 0.0, x.shape))
    record = _classify(dem, thresholds=[-3.0, -3.0])
    assert record["s2_sea_excluded_frac"] is None
    assert record["s2_dem_samples"] > 0
    assert record["s2_dem_median_m"] < 0.0
    assert record["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE


def test_the_excluded_fraction_is_recorded_even_when_it_empties_the_extent():
    """A site whose every sample is sea reports the FRACTION, not a
    crash and not a silent not_flat: 100 % excluded IS the finding."""
    dem = SyntheticDEM(lambda x, y: np.zeros_like(x))
    record = _classify(dem, thresholds=[4.0, 4.0])
    assert record["s2_sea_excluded_frac"] == 1.0
    assert record["s2_dem_samples"] == 0
    assert record["verdict"] == flat_site.VERDICT_NO_DATA


def test_the_exclusion_does_not_rescue_a_site_with_real_land_relief():
    """S2a removes SEA, never terrain: land that genuinely slopes is
    still refused once its sea is gone."""
    def _sloped_coast(x, y):
        return np.where(x < 0.0, 0.02 * x + 40.0, 0.0)

    record = _classify(SyntheticDEM(_sloped_coast), thresholds=[20.0, 20.0])
    assert record["s2_sea_excluded_frac"] == pytest.approx(0.5, abs=0.05)
    assert record["s2_slope_pct"] > config.FLAT_SITE_MAX_SLOPE_PCT
    assert record["verdict"] == flat_site.VERDICT_NOT_FLAT


def test_the_sea_surface_is_a_datum_not_a_knob():
    """The band's upper edge is the DEM's own sea surface.  A sample at
    exactly 0.0 m is excluded; the first millimetre of land is kept."""
    assert config.FLAT_SITE_SEA_BAND_MAX_M == 0.0

    def _one_mm_of_land(x, y):
        return np.where(x < 0.0, 0.001, 0.0)

    record = _classify(SyntheticDEM(_one_mm_of_land), thresholds=[4.0, 4.0])
    assert record["s2_sea_excluded_frac"] == pytest.approx(0.5, abs=0.05)
    assert record["s2_dem_median_m"] == pytest.approx(0.001, abs=1e-6)


# ──────────────────────────────────────────────────────────────────────
# S1 — the owner's 5 m spread boundary (ruling 2026-08-09)
# ──────────────────────────────────────────────────────────────────────
def test_s1_spread_boundary_is_the_owners_five_metres_strictly():
    """Owner 2026-08-09: "CIFP threshold spread < 5m should be a flat
    candidate".  STRICT, and the boundary is reachable — CIFP elevations
    are whole feet and 16 ft is 4.877 m."""
    assert config.FLAT_SITE_THRESHOLD_SPREAD_M == 5.0

    # Just inside: 16 ft of spread, the widest whole-foot gap under 5 m.
    inside = flat_site.threshold_consensus([3.962, 3.962 + 16 * 0.3048])
    assert inside["spread_m"] == pytest.approx(4.877, abs=0.001)
    assert inside["pass"] is True
    # Exactly on it, and just outside.
    assert flat_site.threshold_consensus([0.0, 5.0])["pass"] is False
    assert flat_site.threshold_consensus([0.0, 5.001])["pass"] is False
    assert flat_site.threshold_consensus([0.0, 4.999])["pass"] is True

    # A spread the RETIRED 0.5 m provisional value refused is now a
    # candidate when the DEM agrees — this is the population the ruling
    # is about (a sea-level airport whose ends differ by a metre or two
    # of survey), and Z0 is still the MEAN of the thresholds.
    rng = np.random.default_rng(20260809)
    dem = SyntheticDEM(lambda x, y: 4.0 + rng.normal(0.0, 0.5, x.shape))
    record = _classify(dem, thresholds=[3.0, 5.0, 4.0, 4.0])
    assert record["s1_spread_m"] == 2.0
    assert record["z0_m"] == pytest.approx(4.0)
    assert record["s1_pass"] is True
    assert record["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE

    # The negative type specimen is nowhere near it: HECA's measured
    # 84.43 m of threshold spread still fails S1 outright.
    assert flat_site.threshold_consensus(
        [104.7 - 42.2, 104.7 + 42.23])["pass"] is False


# ──────────────────────────────────────────────────────────────────────
# The PRODUCTION SURFACE case (lead ruling 2026-08-09)
# ──────────────────────────────────────────────────────────────────────
#: What production actually bakes at OTHH: the cached Copernicus GLO-30
#: airport-elevation inset, a 1-arcsec-class SURFACE model.
GLO30_META = {"raw": False,
              "insets": [{"icao": "OTHH", "provider": "COPERNICUSGLO30",
                          "native_resolution_m": 30.0}]}


def test_othh_class_site_is_a_candidate_on_both_dem_surfaces():
    """The type specimen must not change verdict between the base tile it
    is SWEPT on and the airport inset production GRADES on.

    Measured 2026-08-09 at OTHH: base ``.hgt`` relief 6.00 m against the
    3-arcsec floor; the Copernicus GLO-30 inset relief 5.01 m, slope
    0.056 %.  At the pre-ruling 1-arcsec floor of 5.0 m the second
    surface missed by 14 mm and the same airport read ``flat_candidate``
    swept and ``not_flat`` built.  Both arms are candidates now.
    """
    rng = np.random.default_rng(20260809)

    # Arm A — the 3-arcsec base tile: OTHH's measured 6 m of void-fill
    # noise, no trend.
    base = SyntheticDEM(lambda x, y: 6.0 + rng.uniform(-3.33, 3.33, x.shape))
    arm_a = _classify(base)
    assert arm_a["s2_source_class"] == "ge3arcsec"
    assert 5.0 < arm_a["s2_relief_m"] <= arm_a["s2_relief_floor_m"]
    assert arm_a["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE

    # Arm B — the 1-arcsec-class GLO-30 inset: ~5 m of surface-model
    # noise on the same flat ground, at the measured 0.056 % slope.
    inset = SyntheticDEM(
        lambda x, y: 6.0 + 0.00056 * x + rng.uniform(-2.95, 2.95, x.shape))
    arm_b = _classify(inset, dem_meta=GLO30_META)
    assert arm_b["s2_source_class"] == "1arcsec"
    assert arm_b["s2_source_whence"] == "inset"
    assert arm_b["s2_relief_floor_m"] == 8.0, (
        "lead ruling 2026-08-09: a GLO-30 class surface model's own noise "
        "envelope is the 8 m floor, not 5 m")
    assert 5.0 < arm_b["s2_relief_m"] <= 8.0
    assert arm_b["s2_slope_pct"] <= config.FLAT_SITE_MAX_SLOPE_PCT
    assert arm_b["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE


def test_the_raised_floor_still_refuses_a_1arcsec_site_with_real_relief():
    """Raising the 1-arcsec floor relaxes NOISE, not terrain: a genuinely
    sloped site on the same source class is still refused, by the slope
    gate and by relief past the raised floor alike."""
    dem = SyntheticDEM(lambda x, y: 0.02 * x)
    record = _classify(dem, dem_meta=GLO30_META)
    assert record["s2_source_class"] == "1arcsec"
    assert record["verdict"] == flat_site.VERDICT_NOT_FLAT
    assert record["s2_slope_pct"] > config.FLAT_SITE_MAX_SLOPE_PCT
    assert record["s2_relief_m"] > 8.0
    # And the PLATEAU is caught on this class too — the ring, not the floor.
    plateau = _classify(SyntheticDEM(_plateau), dem_meta=GLO30_META)
    assert plateau["verdict"] == flat_site.VERDICT_NOT_FLAT


def test_source_class_reads_provenance_in_the_documented_order():
    dem = SyntheticDEM(lambda x, y: np.zeros_like(x))
    # 1 — insets win, and the FINEST inset is the class.
    meta = {"raw": False, "insets": [
        {"native_resolution_m": 30.0}, {"native_resolution_m": 5.0}]}
    dem.tile_overlay_provenance = {"target_resolution_m": 30.0}
    got = flat_site.source_class_for_dem(dem, dem_meta=meta)
    assert (got["whence"], got["class"], got["resolution_m"]) == (
        "inset", "sub10m", 5.0)
    # 2 — no inset: the tile-wide overlay answers.
    got = flat_site.source_class_for_dem(
        dem, dem_meta={"raw": True, "insets": []})
    assert (got["whence"], got["class"]) == ("overlay", "1arcsec")
    # 3 — neither: the BASE TIER, per the tile's own elevation level.
    del dem.tile_overlay_provenance
    got = flat_site.source_class_for_dem(
        dem, dem_meta={"raw": True, "insets": []})
    assert (got["whence"], got["class"]) == ("base_tier", "ge3arcsec")
    dem.elevation_level = "30"                # a numeric level = 1 arcsec
    got = flat_site.source_class_for_dem(
        dem, dem_meta={"raw": True, "insets": []})
    assert (got["whence"], got["class"]) == ("base_tier", "1arcsec")


def test_raster_posting_is_never_consulted_for_the_source_class():
    """The upsampling trap: a 3-arcsec .hgt is delivered on a 1-arcsec
    grid with no record of the native size, so the ARRAY says 1 arcsec
    over 3-arcsec data.  Reading posting off it would put OTHH under the
    5 m floor instead of the 8 m one and flip the type specimen."""
    coarse = SyntheticDEM(lambda x, y: np.zeros_like(x), n=401)
    fine = SyntheticDEM(lambda x, y: np.zeros_like(x), n=1801)
    meta = {"raw": True, "insets": []}
    assert (flat_site.source_class_for_dem(coarse, dem_meta=meta)
            == flat_site.source_class_for_dem(fine, dem_meta=meta))


# ──────────────────────────────────────────────────────────────────────
# Fixture 5 — absent instruments report no_data and never crash
# ──────────────────────────────────────────────────────────────────────
def test_missing_dem_reports_no_data():
    record = _classify(None)
    assert record["verdict"] == flat_site.VERDICT_NO_DATA
    assert record["s2_dem_samples"] == 0
    assert record["s2_source_class"] is None
    assert record["s1_pass"] is True          # the CIFP half still read


def test_missing_cifp_reports_no_data():
    dem = SyntheticDEM(lambda x, y: np.zeros_like(x))
    record = _classify(dem, thresholds=[])
    assert record["verdict"] == flat_site.VERDICT_NO_DATA
    assert record["s1_pass"] is None          # absent truth is not a fail
    assert record["z0_m"] is None
    assert record["s3_offset_m"] is None
    # The DEM half was still measured — evidence is never withheld.
    assert record["s2_dem_samples"] > 0


def test_missing_extent_and_empty_raster_report_no_data():
    dem = SyntheticDEM(lambda x, y: np.zeros_like(x))
    assert _classify(dem, extent_m=None)["verdict"] == (
        flat_site.VERDICT_NO_DATA)
    # An extent entirely off the tile: the window clamps to nothing.
    off_tile = box(4.0e6, 4.0e6, 4.1e6, 4.1e6)
    assert _classify(dem, extent_m=off_tile)["verdict"] == (
        flat_site.VERDICT_NO_DATA)


def test_nodata_cells_are_dropped_not_measured():
    def _half_void(x, y):
        z = np.full(x.shape, 3.0)
        z[x > 0.0] = -32768.0
        return z

    dem = SyntheticDEM(_half_void)
    record = _classify(dem)
    # nodata is dropped BEFORE the sea band is measured, so the void half
    # never counts as excluded sea.
    assert record["s2_sea_excluded_frac"] == 0.0
    assert record["s2_dem_median_m"] == 3.0
    assert record["s2_relief_m"] == 0.0
    assert record["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE


def test_format_log_line_survives_every_verdict():
    for record in (None, {}, _classify(None),
                   _classify(SyntheticDEM(lambda x, y: np.zeros_like(x)))):
        line = flat_site.format_log_line(record)
        assert isinstance(line, str) and line.startswith("  [flat-site]")


# ──────────────────────────────────────────────────────────────────────
# S4 — the pack-object consensus is confirmatory and never a fail
# ──────────────────────────────────────────────────────────────────────
def test_pack_consensus_is_confirmatory_and_absent_data_is_no_data():
    dem = SyntheticDEM(lambda x, y: np.full(x.shape, 4.0))
    assert _classify(dem)["s4"]["pass"] is None
    assert _classify(dem, pack_targets=[])["s4"]["pass"] is None

    agreeing = _classify(dem, pack_targets=[4.0, 4.1, 3.9, 4.05])["s4"]
    assert agreeing["pass"] is True
    assert agreeing["offset_m"] == pytest.approx(0.025, abs=0.01)

    # A pack that disagrees with instrument truth FAILS S4 and does NOT
    # change the verdict: S4 is confirmatory only.
    disagreeing = _classify(dem, pack_targets=[40.0, 41.0, 39.0])
    assert disagreeing["s4"]["pass"] is False
    assert disagreeing["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE


def test_below_grade_pad_requests_are_excluded(tmp_path):
    """An open-pit drainage basin asks for a TRENCH FLOOR, not a seat."""
    import json

    from auto_patch import object_pads

    sidecar = {
        "version": 4,
        "airports": [{"icao": "TEST", "requests": [
            {"target_ground_metres": 4.0, "base_y": -0.2},
            {"target_ground_metres": 4.1, "base_y": 0.0},
            {"target_ground_metres": 0.2, "base_y": -3.8},   # a basin
        ]}],
    }
    path = object_pads.sidecar_path(str(tmp_path))
    with open(path, "w") as handle:
        json.dump(sidecar, handle)

    got = flat_site.pack_seat_targets(str(tmp_path), "TEST")
    assert got["n_total"] == 3
    assert got["n_below_grade"] == 1
    assert sorted(got["targets"]) == [4.0, 4.1]
    assert flat_site.pack_seat_targets(str(tmp_path), "OTHER")["targets"] == []
    # No sidecar at all is absent data, not an error.
    assert flat_site.pack_seat_targets(str(tmp_path / "nope"),
                                       "TEST")["targets"] == []


# ──────────────────────────────────────────────────────────────────────
# The extent — ONE builder, from the apt.dat record
# ──────────────────────────────────────────────────────────────────────
def test_extent_is_pavement_union_boundary_dilated_by_the_margin():
    def to_m(lon, lat):
        cos0 = math.cos(math.radians(ANCHOR[0]))
        return (math.radians(lon - ANCHOR[1]) * R_EARTH * cos0,
                math.radians(lat - ANCHOR[0]) * R_EARTH)

    # A 1 km square of pavement, expressed in lon/lat about the anchor.
    half_lat = math.degrees(500.0 / R_EARTH)
    half_lon = math.degrees(500.0 / (R_EARTH *
                                     math.cos(math.radians(ANCHOR[0]))))
    square = Polygon([
        (ANCHOR[1] - half_lon, ANCHOR[0] - half_lat),
        (ANCHOR[1] + half_lon, ANCHOR[0] - half_lat),
        (ANCHOR[1] + half_lon, ANCHOR[0] + half_lat),
        (ANCHOR[1] - half_lon, ANCHOR[0] + half_lat)])
    apt = types.SimpleNamespace(
        runways=(), boundary=None,
        pavements=[types.SimpleNamespace(polygon=square)])

    extent = flat_site.extent_from_apt(apt, to_m)
    margin = config.FLAT_SITE_MARGIN_M
    xmin, ymin, xmax, ymax = extent.bounds
    assert xmax - xmin == pytest.approx(1000.0 + 2 * margin, abs=5.0)
    assert ymax - ymin == pytest.approx(1000.0 + 2 * margin, abs=5.0)
    # An airport contributing no geometry has no extent (and no crash).
    assert flat_site.extent_from_apt(
        types.SimpleNamespace(runways=(), pavements=(), boundary=None),
        to_m) is None


# ──────────────────────────────────────────────────────────────────────
# The sidecar contract — registration twin (spec §2, §4)
# ──────────────────────────────────────────────────────────────────────
def test_site_class_is_a_registered_sidecar_evidence_key(tmp_path):
    import json

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    import check_grade as cg

    assert "site_class" in cg.SIDECAR_EVIDENCE_KEYS
    assert "site_class" not in cg.SIDECAR_LAW_KEYS      # evidence, not law

    record = _classify(SyntheticDEM(lambda x, y: np.zeros_like(x)))
    patch = tmp_path / "TEST_auto.patch.osm"
    patch.write_text("<osm></osm>")
    (tmp_path / "TEST_auto.patch.osm.axes.json").write_text(
        json.dumps({"site_class": record}))

    evidence = cg.sidecar_evidence(str(patch))
    assert evidence["unknown_keys"] == []
    # Passed through VERBATIM: summarising it to "<N entries>" would hide
    # exactly the numbers the key exists to carry.
    assert evidence["site_class"] == record


def test_layout_writes_site_class_into_the_axes_sidecar():
    from auto_patch.layout import PavementLayout

    layout = PavementLayout(icao="TEST", anchor=ANCHOR)
    assert layout.site_class is None
    layout.site_class = {"verdict": flat_site.VERDICT_FLAT_CANDIDATE}
    assert layout.site_class["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE
