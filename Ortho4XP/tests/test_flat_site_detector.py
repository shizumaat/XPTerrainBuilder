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
    # 3-arcsec noise WELL inside its own 8 m floor, no trend.
    rng = np.random.default_rng(20260809)
    dem = SyntheticDEM(lambda x, y: rng.normal(0.0, 0.5, x.shape))
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
    # S3 is REPORTED, never gated: a 4 m DEM-vs-instrument offset at a
    # flat-candidate site is evidence FOR DEM unreliability (OTHH: 3.96 m).
    assert record["s3_offset_m"] == pytest.approx(4.0, abs=0.3)


# ──────────────────────────────────────────────────────────────────────
# Fixture 2 — the PLATEAU: flat pavement, hilly surroundings
# ──────────────────────────────────────────────────────────────────────
def _plateau(x, y):
    """0 m on the pavement, rising 10 % outward through the margin ring."""
    dx = np.maximum(np.abs(x) - 1000.0, 0.0)
    dy = np.maximum(np.abs(y) - 250.0, 0.0)
    return 0.10 * np.hypot(dx, dy)


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
        z = np.zeros_like(x)
        z[x > 0.0] = -32768.0
        return z

    dem = SyntheticDEM(_half_void)
    record = _classify(dem)
    assert record["s2_dem_median_m"] == 0.0
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
    dem = SyntheticDEM(lambda x, y: np.zeros_like(x))
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
