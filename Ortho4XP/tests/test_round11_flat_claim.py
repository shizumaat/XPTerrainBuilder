"""Round 11 — a flat site never flattens another airport; an empty inset
is no inset (docs/specs/round11-kmci-flat-claim-spec.md).

Synthetic fixtures only: no X-Plane install, no CIFP, no network, no
build, no write outside ``tmp_path``.

* **R11-1** (AMENDED 2026-08-11) a containment claim extends a flat
  substitution outright; a FALLBACK claim is recorded and extends it
  only where the cluster clears BOTH guards — the
  ``config.FLAT_SITE_CLUSTER_MAX_KM`` distance bound and R11-2's
  feather-datum check.  HZMB (fallback, ~1 km, datum-clean) survives;
  KFLV→KMCI (fallback, ~19 km, −64.5 m) dies on either.  A dropped
  claim entry is NAMED, because that is what left KFLV alone on KMCI's
  DSF.
* **R11-2** the feather-ring datum check REFUSES for cluster insets:
  the cluster is dropped and counted, and the airport's own apt.dat
  substitution is untouched either way.
* **R11-3** inset coverage counts VALID PIXELS: an all-nodata raster is
  no inset at all — 0 % coverage, ``nodata_fraction`` 1.0 in the
  provenance, a loud line, and the build proceeds on the base DEM.
"""
from __future__ import annotations

import json
import math
import os
import sys
import types

import numpy as np
import pytest
from shapely.geometry import Point, box

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (os.path.join(_ROOT, "src"), _ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
from auto_patch import config, flat_site_mode, post_mesh, provenance  # noqa: E402

R_EARTH = 6378137.0
TILE_LAT, TILE_LON = 0, 0
ANCHOR = (0.5, 0.5)              # (lat, lon)


def _lonlat(east_m: float, north_m: float) -> tuple[float, float]:
    """``(longitude, latitude)`` at a local-metre offset from ANCHOR."""
    cos0 = math.cos(math.radians(ANCHOR[0]))
    return (ANCHOR[1] + math.degrees(east_m / (R_EARTH * cos0)),
            ANCHOR[0] + math.degrees(north_m / R_EARTH))


def _placement_block(centre_east_m, centre_north_m, count, spread_m=80.0):
    """``count`` placements scattered inside a ``spread_m`` box."""
    out = []
    side = max(1, int(math.ceil(math.sqrt(count))))
    for index in range(count):
        row, column = divmod(index, side)
        out.append(_lonlat(
            centre_east_m + (column - side / 2.0) * (spread_m / side),
            centre_north_m + (row - side / 2.0) * (spread_m / side)))
    return out


# ══════════════════════════════════════════════════════════════════════
# R11-1 — containment claims the ground; the fallbacks only anchor
# ══════════════════════════════════════════════════════════════════════
_DSF = "/packs/TwoAirports/Earth nav data/+00+000/+00+000.dsf"


def _claim_ring(east_m, north_m, half_m=400.0):
    """A square claim ring in ``(longitude, latitude)`` around a point."""
    corners = [(-half_m, -half_m), (half_m, -half_m),
               (half_m, half_m), (-half_m, half_m)]
    ring = [_lonlat(east_m + dx, north_m + dy) for dx, dy in corners]
    return ring + [ring[0]]


def _install_two_airport_pack(monkeypatch, *, raise_for=None):
    """One DSF, two airports with disjoint claims, placements inside the
    FIRST airport's claim only.  ``raise_for`` makes that airport's
    worklist entry blow up the way KMCI's did."""
    from auto_patch import driver, dsf_reader

    claims = {
        "AAAA": {"hull_lonlat": _claim_ring(0.0, 0.0),
                 "centre_lonlat": list(_lonlat(0.0, 0.0)),
                 "radius_m": 400.0},
        "BBBB": {"hull_lonlat": _claim_ring(19000.0, 0.0),
                 "centre_lonlat": list(_lonlat(19000.0, 0.0)),
                 "radius_m": 400.0},
    }

    monkeypatch.setattr(flat_site_mode, "_cifp_runways",
                        lambda xplane_root, icao: {"09": {"lat": 0.5,
                                                          "lon": 0.5}})
    monkeypatch.setattr(driver, "_airport_claim_lonlat",
                        lambda runways, **kwargs: None)

    def _entries(icao, xplane_root, runways, tile_lat, tile_lon,
                 seen_dsf_paths, scan_cache, claim=None):
        if raise_for and icao == raise_for:
            raise RuntimeError("apt.dat unreadable")
        return [{"icao": icao, "dsf_path": _DSF, "pack_root": "/packs/x",
                 "claim": claims[icao]}]

    monkeypatch.setattr(driver, "_object_anchor_worklist_entries", _entries)
    monkeypatch.setattr(
        dsf_reader, "read_dsf_object_placement_positions",
        lambda dsf_path, pack_root=None: _placement_block(0.0, 0.0, 12))


def test_containment_claims_the_placements_when_both_entries_survive(
        monkeypatch):
    """The control arm: AAAA's claim CONTAINS the placements, so AAAA
    gets them and BBBB gets nothing."""
    _install_two_airport_pack(monkeypatch)

    out = flat_site_mode.claimed_placements_by_icao(
        ["AAAA", "BBBB"], "/xplane", TILE_LAT, TILE_LON)

    assert sorted(out) == ["AAAA"]
    assert len(out["AAAA"]) == 12


def test_a_dropped_claim_entry_is_named_and_its_ground_is_not_awarded(
        monkeypatch, capsys):
    """R11-1, the KMCI mechanism: AAAA's entry raises, the DSF is left
    with BBBB's entry alone, and its placements reach BBBB — 19 km away
    — by the sole-entry FALLBACK.  Both the drop and the fallback are
    said out loud, the fallback set is handed back, and the cluster that
    would flatten AAAA's ground dies on BBBB's distance bound (the
    amended R11-1: recorded, then guarded, never silently inherited)."""
    _install_two_airport_pack(monkeypatch, raise_for="AAAA")

    fallback: dict = {}
    out = flat_site_mode.claimed_placements_by_icao(
        ["AAAA", "BBBB"], "/xplane", TILE_LAT, TILE_LON,
        fallback_out=fallback)

    assert sorted(out) == ["BBBB"] and len(out["BBBB"]) == 12
    assert len(fallback["BBBB"]) == 12
    printed = capsys.readouterr().out
    assert "claim-entry for AAAA dropped (RuntimeError: apt.dat unreadable)" \
        in printed
    assert "can only fall to OTHER airports" in printed
    assert "BBBB: 12 placement(s)" in printed
    assert "FALLBACK, not by containment" in printed
    assert "clears BOTH guards" in printed

    # BBBB's own extent is 19 km away: the guard, not the claim mode, is
    # what stops the inheritance.
    findings: list = []
    boxes = flat_site_mode.claimed_placement_cluster_bounds(
        out["BBBB"], ANCHOR, TILE_LAT, TILE_LON,
        inside=Point(19000.0, 0.0).buffer(1000.0), findings=findings,
        fallback_ll=fallback["BBBB"])
    assert boxes == []
    assert findings[0]["kind"] == flat_site_mode.CLUSTER_FINDING_TOO_FAR
    assert findings[0]["fallback_placements"] == 12
    assert findings[0]["distance_km"] == pytest.approx(18.0, abs=0.2)


def test_a_fallback_claimed_cluster_survives_both_guards_at_one_km():
    """R11-1 as AMENDED (the HZMB pin): a fallback-claimed cluster ~1 km
    outside the extent is KEPT — the fallback is recorded, not a veto —
    and it carries the count of the claims it rests on."""
    extent = Point(0.0, 0.0).buffer(1000.0)
    placements = _placement_block(2000.0, 0.0, 20)

    findings: list = []
    boxes = flat_site_mode.claimed_placement_cluster_bounds(
        placements, ANCHOR, TILE_LAT, TILE_LON, inside=extent,
        findings=findings, fallback_ll=placements)

    assert len(boxes) == 1
    assert boxes[0]["placements"] == 20
    assert boxes[0]["fallback_placements"] == 20
    assert findings == []


def test_a_fallback_claimed_cluster_is_refused_at_six_km():
    """...and the same cluster beyond the bound refuses, with the
    fallback count in the finding."""
    extent = Point(0.0, 0.0).buffer(1000.0)
    placements = _placement_block(8000.0, 0.0, 20)

    findings: list = []
    boxes = flat_site_mode.claimed_placement_cluster_bounds(
        placements, ANCHOR, TILE_LAT, TILE_LON, inside=extent,
        findings=findings, fallback_ll=placements)

    assert boxes == []
    assert findings[0]["kind"] == flat_site_mode.CLUSTER_FINDING_TOO_FAR
    assert findings[0]["fallback_placements"] == 20
    assert 6.9 < findings[0]["distance_km"] < 7.1


def test_a_fallback_claimed_cluster_at_one_km_still_faces_the_datum_check(
        monkeypatch, capsys):
    """The SECOND guard on the same cluster: 1 km out and datum-clean it
    bakes; 1 km out with a 60 m ring offset it is refused and counted.
    Both guards, or the fallback does not move ground."""
    dem, substitution = _overlay_one_cluster(monkeypatch, 2.0,
                                             fallback_placements=20)
    kinds = [entry["kind"] for entry in dem.synthetic_flat_site_provenance]
    assert kinds == ["synthetic_flat_site",
                     "synthetic_flat_site_object_cluster"]
    assert substitution["cluster_findings"] == []
    capsys.readouterr()

    dem, substitution = _overlay_one_cluster(monkeypatch, 60.0,
                                             fallback_placements=20)
    printed = capsys.readouterr().out
    kinds = [entry["kind"] for entry in dem.synthetic_flat_site_provenance]
    assert kinds == ["synthetic_flat_site"]
    finding = substitution["cluster_findings"][0]
    assert finding["kind"] == flat_site_mode.CLUSTER_FINDING_DATUM
    assert finding["fallback_placements"] == 20
    assert "20 fallback-claimed" in printed


def test_the_assigner_reports_how_a_point_reached_its_owner():
    """The assigner's compatible extension: the same icao, plus WHICH
    rule awarded it.  The default call is unchanged."""
    entries = [
        {"icao": "AAAA", "dsf_path": _DSF,
         "claim": {"hull_lonlat": _claim_ring(0.0, 0.0),
                   "centre_lonlat": list(_lonlat(0.0, 0.0))}},
        {"icao": "BBBB", "dsf_path": _DSF,
         "claim": {"hull_lonlat": _claim_ring(19000.0, 0.0),
                   "centre_lonlat": list(_lonlat(19000.0, 0.0))}},
    ]
    assign = post_mesh.worklist_claim_assigner(entries)
    inside_lon, inside_lat = _lonlat(0.0, 0.0)
    between_lon, between_lat = _lonlat(9000.0, 0.0)

    assert assign(_DSF, inside_lat, inside_lon) == "AAAA"
    assert assign(_DSF, inside_lat, inside_lon, with_mode=True) == (
        "AAAA", post_mesh.CLAIM_CONTAINMENT)
    # Claimed by nobody -> the nearest airport still anchors it, and says
    # that is what happened.
    assert assign(_DSF, between_lat, between_lon, with_mode=True)[1] == \
        post_mesh.CLAIM_NEAREST

    sole = post_mesh.worklist_claim_assigner(entries[1:])
    assert sole(_DSF, inside_lat, inside_lon) == "BBBB"
    assert sole(_DSF, inside_lat, inside_lon, with_mode=True) == (
        "BBBB", post_mesh.CLAIM_SOLE_ENTRY)


def test_a_far_cluster_is_refused_and_a_near_one_is_kept():
    """R11-1's belt-and-suspenders bound: 6 km out is refused with both
    distances named; 1 km out (the HZMB pin) is kept."""
    extent = Point(0.0, 0.0).buffer(1000.0)

    findings: list = []
    far = flat_site_mode.claimed_placement_cluster_bounds(
        _placement_block(8000.0, 0.0, 20), ANCHOR, TILE_LAT, TILE_LON,
        inside=extent, findings=findings)
    assert far == []
    assert len(findings) == 1
    finding = findings[0]
    assert finding["kind"] == flat_site_mode.CLUSTER_FINDING_TOO_FAR
    assert finding["max_km"] == config.FLAT_SITE_CLUSTER_MAX_KM
    assert 6.9 < finding["distance_km"] < 7.1, finding
    assert finding["placements"] == 20

    near_findings: list = []
    near = flat_site_mode.claimed_placement_cluster_bounds(
        _placement_block(2000.0, 0.0, 20), ANCHOR, TILE_LAT, TILE_LON,
        inside=extent, findings=near_findings)
    assert len(near) == 1 and near[0]["placements"] == 20
    assert near_findings == []


# ══════════════════════════════════════════════════════════════════════
# R11-2 — the datum check refuses for cluster insets
# ══════════════════════════════════════════════════════════════════════
class _FakeDEM:
    """The surface ``_bake_one_inset`` reads from a working grid.

    2401 posts across the degree (~46 m) so a 1 km substitution box holds
    a real interior AND a real feather ring — the ring IS the datum
    measurement, and a grid too coarse to carry one would test nothing.
    """

    def __init__(self, constant=0.0, n=2401):
        self.lat, self.lon = TILE_LAT, TILE_LON
        self.nxdem = self.nydem = int(n)
        self.x0 = self.y0 = 0.0
        self.x1 = self.y1 = 1.0
        self.nodata = -32768.0
        self.elevation_level = "auto"
        self.source_path = "<synthetic>"
        self.alt_dem = np.full((self.nydem, self.nxdem), float(constant),
                               dtype=np.float32)


def _overlay_one_cluster(monkeypatch, z0_m, fallback_placements=0):
    """Bake one airport + one 3 km-distant claimed-object cluster at
    ``z0_m`` over a base DEM at 0 m, and hand back what was stamped.

    ``fallback_placements`` marks the cluster as resting on that many
    FALLBACK claims, which changes no gate — both guards apply to every
    cluster — but must reach the finding and the log line."""
    dem = _FakeDEM(constant=0.0)
    tile = types.SimpleNamespace(
        lat=TILE_LAT, lon=TILE_LON, dem=dem,
        airport_elevation_inset_feather_m=60.0)

    airport_box = flat_site_mode.claimed_placement_cluster_bounds(
        _placement_block(0.0, 0.0, 12, spread_m=600.0),
        ANCHOR, TILE_LAT, TILE_LON)[0]
    island_box = flat_site_mode.claimed_placement_cluster_bounds(
        _placement_block(3000.0, 0.0, 20, spread_m=600.0),
        ANCHOR, TILE_LAT, TILE_LON)[0]

    island_box = dict(island_box)
    island_box["fallback_placements"] = int(fallback_placements)
    substitution = {
        "icao": "TEST",
        "verdict": "flat_candidate",
        "z0_m": float(z0_m),
        "extent_deg": airport_box["extent_deg"],
        "extent_area_km2": airport_box["extent_area_km2"],
        "object_clusters": [island_box],
        "cluster_findings": [],
        "record": {"verdict": "flat_candidate"},
    }
    monkeypatch.setattr(
        flat_site_mode, "flat_site_substitutions",
        lambda tile_, dico_airports=None, xplane_root=None: [substitution])

    INSETS.overlay_flat_site_insets(tile)
    return dem, substitution


def test_a_cluster_inset_off_the_base_datum_is_refused_and_counted(
        monkeypatch, capsys):
    """R11-2: 60 m over a 0 m base is datum-class disagreement — the
    CLUSTER is dropped and counted, the airport's own extent is not."""
    dem, substitution = _overlay_one_cluster(monkeypatch, 60.0)
    printed = capsys.readouterr().out

    kinds = [entry["kind"] for entry in dem.synthetic_flat_site_provenance]
    assert kinds == ["synthetic_flat_site"]
    findings = dem.synthetic_flat_site_provenance[0]["cluster_findings"]
    assert [finding["kind"] for finding in findings] == [
        flat_site_mode.CLUSTER_FINDING_DATUM]
    assert findings[0]["ring_offset_m"] == pytest.approx(60.0, abs=0.5)
    assert findings[0]["threshold_m"] == INSETS.INSET_DATUM_WARNING_THRESHOLD_M
    assert "REFUSED a CLAIMED-OBJECT cluster inset" in printed
    assert "stays on the real surface" in printed

    # The airport's own extent DID substitute: its centre reads Z0.
    x0, y0, x1, y1 = substitution["extent_deg"]
    column = int(round((x0 + x1) / 2.0 * (dem.nxdem - 1)))
    row = int(round((1.0 - (y0 + y1) / 2.0) * (dem.nydem - 1)))
    assert dem.alt_dem[row, column] == pytest.approx(60.0, abs=0.5)
    # ...and the refused cluster did not.
    cx0, cy0, cx1, cy1 = substitution["object_clusters"][0]["extent_deg"]
    ccolumn = int(round((cx0 + cx1) / 2.0 * (dem.nxdem - 1)))
    crow = int(round((1.0 - (cy0 + cy1) / 2.0) * (dem.nydem - 1)))
    assert dem.alt_dem[crow, ccolumn] == pytest.approx(0.0, abs=1e-6)


def test_a_cluster_inset_on_the_base_datum_is_kept(monkeypatch):
    """The equivalence pin: 2 m off the base is the normal
    surface-vs-bare-earth gap and this law must be inert there."""
    dem, substitution = _overlay_one_cluster(monkeypatch, 2.0)

    kinds = [entry["kind"] for entry in dem.synthetic_flat_site_provenance]
    assert kinds == ["synthetic_flat_site",
                     "synthetic_flat_site_object_cluster"]
    assert dem.synthetic_flat_site_provenance[0]["cluster_findings"] == []
    cx0, cy0, cx1, cy1 = substitution["object_clusters"][0]["extent_deg"]
    ccolumn = int(round((cx0 + cx1) / 2.0 * (dem.nxdem - 1)))
    crow = int(round((1.0 - (cy0 + cy1) / 2.0) * (dem.nydem - 1)))
    assert dem.alt_dem[crow, ccolumn] == pytest.approx(2.0, abs=0.1)


# ══════════════════════════════════════════════════════════════════════
# R11-3 — an empty inset is no inset
# ══════════════════════════════════════════════════════════════════════
gdal = pytest.importorskip("osgeo.gdal", reason="GDAL required for R11-3")


def _write_inset(directory, name, valid_fraction, *, project="TEST_PROJECT"):
    """A 1-degree-square inset GeoTIFF whose southern band is nodata."""
    path = os.path.join(str(directory), name)
    rows = columns = 64
    values = np.full((rows, columns), -32768.0, dtype=np.float32)
    valid_rows = int(round(rows * valid_fraction))
    if valid_rows:
        values[:valid_rows, :] = 100.0
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((0.0, 1.0 / columns, 0.0,
                             1.0, 0.0, -1.0 / rows))
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values)
    band.FlushCache()
    dataset.FlushCache()
    dataset = None
    with open(path[:-4] + ".json", "w") as handle:
        json.dump({"provider": "TESTDEP", "project_titles": [project],
                   "source_ids": ["1"], "resolution_m": 1.0}, handle)
    return path


def _install_cached_insets(monkeypatch, paths):
    monkeypatch.setattr(INSETS, "select_provider_definitions",
                        lambda *args, **kwargs: [])
    monkeypatch.setattr(
        INSETS, "list_cached_inset_dems",
        lambda lat, lon, provider_codes=None: list(paths))
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda tile: True)
    INSETS._inset_valid_fraction_cache.clear()


def test_an_all_nodata_inset_reports_no_coverage_and_falls_back(
        monkeypatch, capsys, tmp_path):
    """R11-3: the KMCI raster — structurally perfect, 100 % nodata.  No
    coverage, no bake, ``nodata_fraction`` 1.0, a loud line naming the
    file and its source project, and the DEM stays RAW."""
    empty = _write_inset(tmp_path, "KMCI_usgs3dep.tif", 0.0,
                         project="USGS 1 Meter KS_Statewide_2018_A18")
    _install_cached_insets(monkeypatch, [empty])

    assert INSETS.inset_valid_fraction(empty) == 0.0
    assert INSETS.inset_is_effectively_empty(empty) == (True, 0.0)

    dem = _FakeDEM(constant=300.0)
    tile = types.SimpleNamespace(lat=TILE_LAT, lon=TILE_LON, dem=dem,
                                 airport_elevation_inset_feather_m=60.0)
    coverage, finest_pixel_m = INSETS.inset_coverage_of_airport_mask(
        tile, box(0.4, 0.4, 0.6, 0.6))
    assert coverage == 0.0 and finest_pixel_m is None

    INSETS.bake_airport_insets_into_alt_dem(tile)
    printed = capsys.readouterr().out

    assert dem.airport_inset_provenance == []
    refused = dem.airport_inset_nodata_refusals
    assert len(refused) == 1
    assert refused[0]["nodata_fraction"] == 1.0
    assert refused[0]["fallback"].startswith("base DEM")
    assert np.all(dem.alt_dem == 300.0)      # the base DEM, untouched
    assert "KMCI_usgs3dep.tif holds 0.00 % valid pixels" in printed
    assert "KS_Statewide_2018_A18" in printed

    meta = provenance.dem_provenance_from_dem(dem, icao="KMCI")
    assert meta["raw"] is True
    assert meta["nodata_refused"][0]["nodata_fraction"] == 1.0


def test_a_half_valid_inset_stays_an_inset_at_half_coverage(
        monkeypatch, tmp_path):
    """The other side of the gate: half the pixels are data, so the
    coverage metric answers 0.5 and the inset is kept."""
    half = _write_inset(tmp_path, "KTST_usgs3dep.tif", 0.5)
    _install_cached_insets(monkeypatch, [half])

    assert INSETS.inset_valid_fraction(half) == pytest.approx(0.5, abs=0.02)
    assert INSETS.inset_is_effectively_empty(half)[0] is False

    dem = _FakeDEM(constant=300.0)
    tile = types.SimpleNamespace(lat=TILE_LAT, lon=TILE_LON, dem=dem,
                                 airport_elevation_inset_feather_m=60.0)
    coverage, _finest = INSETS.inset_coverage_of_airport_mask(
        tile, box(0.4, 0.4, 0.6, 0.6))
    assert coverage == pytest.approx(0.5, abs=0.02)


def test_an_inset_with_no_nodata_value_declared_is_fully_valid(tmp_path):
    """A file that declares no nodata is data everywhere by definition —
    this metric never invents a reason to drop an inset."""
    path = os.path.join(str(tmp_path), "KNOD_usgs3dep.tif")
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, 8, 8, 1, gdal.GDT_Float32)
    dataset.GetRasterBand(1).WriteArray(np.zeros((8, 8), dtype=np.float32))
    dataset.FlushCache()
    dataset = None
    INSETS._inset_valid_fraction_cache.clear()

    assert INSETS.inset_valid_fraction(path) == 1.0
    assert INSETS.inset_is_effectively_empty(path)[0] is False


def test_the_cluster_findings_vocabulary_is_shared():
    """One helper records both refusals, so a reader asking "what was
    refused" needs to know only one key."""
    substitution: dict = {}
    flat_site_mode.record_cluster_finding(
        substitution, flat_site_mode.CLUSTER_FINDING_DATUM, placements=7)
    assert substitution["cluster_findings"] == [
        {"placements": 7, "kind": flat_site_mode.CLUSTER_FINDING_DATUM}]


def test_the_distance_bound_is_a_registered_config_knob():
    """Config knobs are registered where config knobs live (the O4_ pair
    convention), never improvised at a call site."""
    assert config.FLAT_SITE_CLUSTER_MAX_KM == 5.0
    assert INSETS.INSET_MIN_VALID_FRAC == 0.05


def test_with_no_airport_extent_there_is_nothing_to_measure_from():
    """The distance bound needs an extent; with none (the round-8 call
    shape) no bound is applied and nothing refuses."""
    findings: list = []
    boxes = flat_site_mode.claimed_placement_cluster_bounds(
        _placement_block(50000.0, 0.0, 20), ANCHOR, TILE_LAT, TILE_LON,
        findings=findings)
    assert len(boxes) == 1
    assert findings == []
