"""THE DECLARED-EMPTY INSET (2026-09-18, the LSGP / LSGY class).

Two rules disagreed about one file.  ``LSGP_swissalti3d.tif`` (9,733
bytes, 0.00 % valid pixels, fetched 2026-07-23, index ``"SWISSALTI3D":
"ok"``) made the bake say, LOUDLY, "NO INSET: it is not baked and carries
no coverage; the build proceeds on the base DEM" — and made v2's frame
check say "the bake reports NO inset while the file exists — the prep
degraded silently (2026-08-07 class)" and refuse the airport.  In app
1.0.351 that refusal took the whole +46+006 tile down; the other nine
airports on it had solved.

ONE PREDICATE now answers for all three readers
(``O4_Airport_Elevation_Insets.cached_inset_declined_reason``, the BAKE's
own valid-pixel rule):

* the frame check reports a DECLARED state and refuses nothing;
* the 2026-08-07 class — a VALID inset the bake dropped in silence —
  still refuses;
* the fetch loop stops calling an empty raster ``ok``.

Everything here runs on a tmp corpus with rasters written by GDAL.  No
network, no shared-repo write.
"""
from __future__ import annotations

import json
import os
import types

import numpy
import pytest

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
from auto_patch_v2.airport import dem_production as DP

LAT, LON = 46, 6
STEM, BLOCK = "N46E006", "+40+000"
ICAO = "LSGP"
#: LSGP's real box, from the tile's own index.json.
REQUIRED = (6.228775334989304, 46.38548829431761,
            6.287351165010697, 46.426947205682396)


def _write_raster(path, *, valid):
    """A small georeferenced float32 GeoTIFF: all-nodata, or all data."""
    from osgeo import gdal
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(str(path), 32, 32, 1, gdal.GDT_Float32)
    (west, south, east, north) = REQUIRED
    dataset.SetGeoTransform((west, (east - west) / 32.0, 0.0,
                             north, 0.0, -(north - south) / 32.0))
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(numpy.full((32, 32), 412.0 if valid else -32768.0,
                               dtype=numpy.float32))
    band.FlushCache()
    dataset = None


def _corpus(tmp_path, monkeypatch, *, valid, manifest=True):
    """Elevation_data / OSM_data with one tile holding one inset."""
    elevation = tmp_path / "Elevation_data"
    osm = tmp_path / "OSM_data"
    block = elevation / BLOCK
    insets = block / f"{STEM}_airport_insets"
    insets.mkdir(parents=True)
    (block / f"{STEM}.hgt").write_bytes(b"\0" * 8)
    layer = osm / BLOCK / "+46+006"
    layer.mkdir(parents=True)
    (layer / "+46+006_airports.osm.bz2").write_bytes(b"\0")
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(elevation))
    INSETS._inset_valid_fraction_cache.clear()
    raster = insets / f"{ICAO}_swissalti3d.tif"
    _write_raster(raster, valid=valid)
    if manifest:
        (insets / f"{ICAO}_swissalti3d.json").write_text(json.dumps(
            {"provider": "SWISSALTI3D",
             "bounding_box_wgs84": list(REQUIRED)}))
    (insets / "index.json").write_text(json.dumps(
        {ICAO: {"SWISSALTI3D": "ok", "bounding_box": list(REQUIRED),
                "checked": "2026-07-23"}}))
    return (str(elevation), str(osm), str(raster))


# =====================================================================
# THE ONE PREDICATE
# =====================================================================
def test_the_predicate_names_an_empty_raster_and_clears_a_valid_one(
        tmp_path, monkeypatch):
    (_e, _o, empty) = _corpus(tmp_path, monkeypatch, valid=False)
    reason = INSETS.cached_inset_declined_reason(empty)
    assert reason and "0.00 % valid pixels" in reason
    INSETS._inset_valid_fraction_cache.clear()
    _write_raster(empty, valid=True)
    assert INSETS.cached_inset_declined_reason(empty) is None
    assert INSETS.cached_inset_declined_reason(empty + ".absent") is None


def test_the_frame_problem_is_EMPTY_not_missing_and_not_stale(
        tmp_path, monkeypatch):
    (_e, _o, raster) = _corpus(tmp_path, monkeypatch, valid=False)
    problem = INSETS.airport_inset_frame_problem(LAT, LON, ICAO, REQUIRED)
    assert problem is not None
    (kind, text) = problem
    assert kind == "empty"
    assert os.path.basename(raster) in text
    assert "BASE DEM" in text and "--refresh-data dem" in text


def test_a_valid_inset_is_still_no_problem_at_all(tmp_path, monkeypatch):
    _corpus(tmp_path, monkeypatch, valid=True)
    assert INSETS.airport_inset_frame_problem(LAT, LON, ICAO,
                                              REQUIRED) is None


# =====================================================================
# PRODUCTION: declared ⇒ not a problem; the 2026-08-07 class still refuses
# =====================================================================
def test_frame_state_records_the_declared_empty_and_raises_no_problem(
        tmp_path, monkeypatch):
    (elevation, osm, _r) = _corpus(tmp_path, monkeypatch, valid=False)
    (state, problems) = DP.frame_state(elevation, osm, LAT, LON, ICAO,
                                       REQUIRED)
    assert problems == []
    assert state["airport_inset_problem_kind"] == "empty"
    assert "DECLARED-EMPTY" in state["airport_inset_declared_empty"]


def _baker(icao=ICAO):
    """The pieces of ``ProductionDem`` ``_bake`` uses, and nothing else."""
    dem = DP.ProductionDem.__new__(DP.ProductionDem)
    dem.icao = icao
    dem.allow_degraded = False
    dem.provenance = {}
    dem._required_boxes = {}
    dem.lines = []
    dem._out = dem.lines.append
    return dem


def _surface(*, refusals):
    return types.SimpleNamespace(
        alt_dem=numpy.ones((4, 4), dtype=numpy.float32),
        nxdem=4, nydem=4, baked_query_active=False,
        x0=0.0, x1=1.0, y0=0.0, y1=1.0,
        airport_inset_provenance=[],
        airport_inset_nodata_refusals=refusals,
        synthetic_flat_site_provenance=[],
        tile_overlay_provenance=None)


def test_the_bake_that_DECLARED_its_declination_does_not_refuse():
    """The LSGP class: the raster is on disk, nothing was baked, and the
    bake SAID SO.  A declared state is never a silent degrade."""
    dem = _baker()
    state = {"airport_inset": f"/x/{ICAO}_swissalti3d.tif",
             "airport_inset_declared_empty": "DECLARED-EMPTY …"}
    baked = dem._bake(LAT, LON, _surface(refusals=[
        {"icao": ICAO, "provider": "SWISSALTI3D", "nodata_fraction": 1.0,
         "path": f"/x/{ICAO}_swissalti3d.tif"}]),
        STEM, state, tile=None, airports_smoothed=1, how="composed")
    assert baked is not None
    assert any("DECLARED EMPTY" in line for line in dem.lines)
    assert "nodata_refused=LSGP:LSGP_swissalti3d.tif" in \
        dem.provenance[f"tile:{STEM}"]
    assert dem.provenance[f"inset_declared_empty:{STEM}"]
    assert "degraded" not in dem.provenance


def test_a_VALID_inset_dropped_in_silence_still_REFUSES():
    """The 2026-08-07 class this check exists for is untouched: the file
    is there, nothing baked, and the bake declared NOTHING."""
    dem = _baker()
    state = {"airport_inset": f"/x/{ICAO}_swissalti3d.tif"}
    with pytest.raises(DP.ColdDemFrame, match="degraded silently"):
        dem._bake(LAT, LON, _surface(refusals=[]), STEM, state, tile=None,
                  airports_smoothed=1, how="composed")


def test_a_refusal_for_ANOTHER_airport_does_not_excuse_this_one():
    dem = _baker()
    state = {"airport_inset": f"/x/{ICAO}_swissalti3d.tif"}
    with pytest.raises(DP.ColdDemFrame, match="degraded silently"):
        dem._bake(LAT, LON, _surface(refusals=[
            {"icao": "LSGY", "provider": "SWISSALTI3D",
             "path": "/x/LSGY_swissalti3d.tif"}]),
            STEM, state, tile=None, airports_smoothed=1, how="composed")


# =====================================================================
# THE HARNESS TWIN: named, never refused
# =====================================================================
def _harness():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))),
        "tools", "harness", "build_airport.py")
    spec = importlib.util.spec_from_file_location("harness_emptyinset", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_harness_NAMES_an_empty_inset_and_builds_anyway(capsys):
    harness = _harness()
    state = {"tile": [LAT, LON], "tile_stem": STEM, "base_raster": True,
             "airport_insets": True, "airports_layer": True}
    harness.require_dem_frame(
        state, inset_problem=("empty", "DECLARED-EMPTY airport elevation "
                                       "inset /x/LSGP_swissalti3d.tif …"))
    out = capsys.readouterr().out
    assert "DECLARED-EMPTY INSET" in out and "base DEM" in out


def test_the_harness_still_REFUSES_a_stale_inset():
    harness = _harness()
    state = {"tile": [LAT, LON], "tile_stem": STEM, "base_raster": True,
             "airport_insets": True, "airports_layer": True}
    with pytest.raises(SystemExit, match="STALE airport elevation inset"):
        harness.require_dem_frame(
            state, inset_problem=("stale", "STALE airport elevation inset "
                                           "/x/LSGP_swissalti3d.tif …"))


def test_an_empty_inset_is_NOT_a_missing_shared_artifact(tmp_path,
                                                         monkeypatch):
    """Nothing is fetched or regenerated by reading an empty raster, so
    listing it would refuse a build that mutates nothing."""
    harness = _harness()
    (elevation, _o, _r) = _corpus(tmp_path, monkeypatch, valid=False)
    state = {"tile": [LAT, LON], "tile_stem": STEM, "base_raster": True,
             "airport_insets": True, "airports_layer": True}
    monkeypatch.setattr(harness, "unverified_inset_negatives",
                        lambda *a, **k: [])
    monkeypatch.setattr(harness, "schema_stale_osm_layers",
                        lambda *a, **k: [])
    monkeypatch.setattr(harness, "missing_pack_dsf_dumps",
                        lambda *a, **k: [])
    missing = harness.missing_shared_artifacts(
        tmp_path, LAT, LON, ICAO, state=state,
        inset_problem=("empty", "DECLARED-EMPTY …"))
    assert missing == []
    stale = harness.missing_shared_artifacts(
        tmp_path, LAT, LON, ICAO, state=state,
        inset_problem=("stale", "STALE …"))
    assert [scope for scope, _a, _w in stale] == ["dem"]


# =====================================================================
# THE FETCH SIDE: an empty raster is never "ok" again
# =====================================================================
def _fetch_once(tmp_path, monkeypatch, *, fetch):
    """One ``ensure_airport_insets`` pass over the tmp corpus."""
    definition = {"code": "SWISSALTI3D", "access_strategy": "stac_cog",
                  "coverage_bbox": "5.5,45.5,11.0,48.0"}
    monkeypatch.setattr(INSETS, "fetch_inset", fetch)
    monkeypatch.setattr(INSETS, "has_gdal", True)
    INSETS.ensure_airport_insets(LAT, LON, {ICAO: REQUIRED}, [definition],
                                 30.0)
    return INSETS._read_index(LAT, LON)[ICAO]


def test_an_empty_cached_raster_is_recorded_empty_and_refetched(
        tmp_path, monkeypatch):
    (_e, _o, raster) = _corpus(tmp_path, monkeypatch, valid=False,
                               manifest=False)
    seen = []

    def fetch(definition, box, resolution, destination, **kwargs):
        seen.append(destination)
        raise INSETS.TransientFetchError("the provider timed out")

    record = _fetch_once(tmp_path, monkeypatch, fetch=fetch)
    assert seen == [raster]                    # it asked again
    status = record["SWISSALTI3D"]
    assert INSETS.status_is_empty(status), status
    assert status != "ok" and status != INSETS.NO_COVERAGE


def test_a_valid_cached_raster_is_still_reused_without_a_fetch(
        tmp_path, monkeypatch):
    _corpus(tmp_path, monkeypatch, valid=True)
    seen = []

    def fetch(*a, **k):
        seen.append(a)
        raise AssertionError("a valid cache must never refetch")

    record = _fetch_once(tmp_path, monkeypatch, fetch=fetch)
    assert seen == []
    assert record["SWISSALTI3D"] == "ok"


def test_a_successful_refetch_overwrites_the_empty_status(tmp_path,
                                                          monkeypatch):
    (_e, _o, raster) = _corpus(tmp_path, monkeypatch, valid=False,
                               manifest=False)

    def fetch(definition, box, resolution, destination, **kwargs):
        INSETS._inset_valid_fraction_cache.clear()
        _write_raster(destination, valid=True)
        return {"provider": "SWISSALTI3D", "bounding_box_wgs84": list(box),
                "fetch_date": "2026-09-18"}

    record = _fetch_once(tmp_path, monkeypatch, fetch=fetch)
    assert record["SWISSALTI3D"] == "ok"
    assert os.path.isfile(raster[:-4] + ".json")
    INSETS._inset_valid_fraction_cache.clear()
    assert INSETS.cached_inset_declined_reason(raster) is None
