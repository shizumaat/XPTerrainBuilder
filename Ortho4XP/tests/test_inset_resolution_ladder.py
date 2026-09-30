"""#130 -- the USGS3DEP resolution ladder (KASE, Aspen).

KASE's 1 m 3DEP mosaic held 0.22 % valid pixels (the only 1 m project
there never flew the cell over the airport), the bake refused it, and the
airport was graded on the 30 m base DEM while 3DEP publishes 1/3
arc-second (~10 m) over the whole box.  The ladder: a rung below the
bake's own threshold (``INSET_MIN_VALID_FRAC``) climbs to the next,
coarser rung declared in the provider's ``.elv``; the record names every
rung tried and the one delivered; no-coverage only when no rung listed a
product.  No network: a fake strategy writes synthetic GeoTIFFs whose
valid fraction is keyed on the rung's native resolution.
"""

import json
import os

import numpy
import pytest

import O4_File_Names as FNAMES
import O4_Airport_Elevation_Insets as INSETS

try:
    from osgeo import gdal, osr

    HAS_GDAL = True
except Exception:                                        # pragma: no cover
    HAS_GDAL = False

requires_gdal = pytest.mark.skipif(not HAS_GDAL, reason="no osgeo")

BOX = (-106.8994, 39.1893, -106.8378, 39.2532)
STRATEGY = "ladder_fake_strategy"


def _write_raster(path, valid_fraction, size=40):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, size, size, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform(
        (BOX[0], (BOX[2] - BOX[0]) / size, 0.0, BOX[3], 0.0,
         -(BOX[3] - BOX[1]) / size))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    values = numpy.full((size, size), -32768.0, dtype=numpy.float32)
    valid_rows = int(round(valid_fraction * size))
    values[:valid_rows, :] = 2400.0
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values)
    dataset = None


@pytest.fixture
def fake_strategy():
    """``plan[native_m]`` = valid fraction to deliver, ``None`` for "no
    product listed", or an Exception instance to raise."""
    plan = {}
    calls = []

    @INSETS.register_access_strategy(STRATEGY)
    class _Fake:
        def discover(self, definition, bounding_box_wgs84):
            return [{"note": "fake"}]

        def fetch(self, definition, bounding_box_wgs84,
                  target_resolution_m, destination_path):
            native = definition["native_resolution_m"]
            calls.append((native, target_resolution_m, destination_path))
            outcome = plan.get(native)
            if isinstance(outcome, Exception):
                _write_raster(destination_path, 0.5)     # partial file
                raise outcome
            if outcome is None:
                return None
            _write_raster(destination_path, outcome)
            return {
                "provider": definition["code"],
                "native_resolution_m": native,
                "resolution_m": target_resolution_m,
                "sources_used": [{"title": "rung %g" % native}],
            }

    try:
        yield plan, calls
    finally:
        INSETS.ACCESS_STRATEGIES.pop(STRATEGY, None)


def _definition():
    return {
        "code": "FAKE3DEP",
        "access_strategy": STRATEGY,
        "role": INSETS.ROLE_AIRPORT_INSET,
        "enabled": True,
        "priority": 1.0,
        "native_resolution_m": 1.0,
        "ladder_label": "1 meter",
        "discovery_url_template": "rung0",
        "resolution_ladder_rungs": INSETS._parse_resolution_ladder(
            "10|1/3 arc-second|rung2;3|1/9 arc-second|rung1"),
    }


@requires_gdal
def test_empty_1m_climbs_to_3m(tmp_path, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 0.0, 3.0: 1.0, 10.0: 1.0})
    destination = str(tmp_path / "KASE_fake3dep.tif")
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True)
    assert [call[0] for call in calls] == [1.0, 3.0]    # 10 m never asked
    assert calls[1][1] == 3.0                           # warped at 3 m
    assert provenance["resolution_m"] == 3.0
    assert provenance["native_resolution_m"] == 3.0
    ladder = provenance["ladder"]
    assert ladder["delivered_rung"] == 1
    assert ladder["delivered_label"] == "1/9 arc-second"
    assert ladder["threshold_valid_fraction"] == INSETS.INSET_MIN_VALID_FRAC
    assert [r["outcome"] for r in ladder["rungs_tried"]] == [
        "below-threshold", "delivered"]
    # The 3 m raster IS the inset now; no rung scratch file survives.
    assert INSETS.inset_valid_fraction(destination) == 1.0
    assert sorted(os.listdir(tmp_path)) == ["KASE_fake3dep.tif"]


@requires_gdal
def test_finest_rung_answering_stops_the_ladder(tmp_path, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 1.0, 3.0: 1.0, 10.0: 1.0})
    destination = str(tmp_path / "a.tif")
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True)
    assert [call[0] for call in calls] == [1.0]
    assert provenance["ladder"]["delivered_rung"] == 0
    assert provenance["resolution_m"] == 1.0


@requires_gdal
def test_no_product_rung_is_skipped(tmp_path, fake_strategy):
    """The KASE shape: 1 m sub-threshold, 1/9" lists nothing, 1/3" whole."""
    plan, calls = fake_strategy
    plan.update({1.0: 0.0022, 3.0: None, 10.0: 1.0})
    destination = str(tmp_path / "a.tif")
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True)
    ladder = provenance["ladder"]
    assert [r["outcome"] for r in ladder["rungs_tried"]] == [
        "below-threshold", "no-coverage", "delivered"]
    assert ladder["delivered_label"] == "1/3 arc-second"
    assert provenance["resolution_m"] == 10.0


@requires_gdal
def test_every_rung_below_threshold_keeps_the_finest(tmp_path, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 0.025, 3.0: 0.0, 10.0: None})
    destination = str(tmp_path / "a.tif")
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True)
    assert provenance["ladder"]["delivered_rung"] is None
    assert provenance["resolution_m"] == 1.0          # the finest, kept
    assert INSETS.inset_is_effectively_empty(destination)[0]
    assert sorted(os.listdir(tmp_path)) == ["a.tif"]


@requires_gdal
def test_no_coverage_only_when_every_rung_lists_nothing(tmp_path,
                                                        fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: None, 3.0: None, 10.0: None})
    destination = str(tmp_path / "a.tif")
    assert INSETS.fetch_inset(
        _definition(), BOX, 1.0, destination, resolution_ladder=True) is None
    assert len(calls) == 3
    assert os.listdir(tmp_path) == []


@requires_gdal
def test_transient_rung_raises_and_leaves_no_scratch(tmp_path, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 0.0, 3.0: INSETS.TransientFetchError("outage")})
    destination = str(tmp_path / "a.tif")
    with pytest.raises(INSETS.TransientFetchError):
        INSETS.fetch_inset(
            _definition(), BOX, 1.0, destination, resolution_ladder=True)
    assert not any(name.startswith("a.tif.rung")
                   for name in os.listdir(tmp_path))


@requires_gdal
def test_ladder_is_off_unless_asked(tmp_path, fake_strategy):
    """The whole-tile overlay path never trades a sparse 1 m tile down."""
    plan, calls = fake_strategy
    plan.update({1.0: 0.0, 3.0: 1.0})
    provenance = INSETS.fetch_inset(
        _definition(), BOX, 1.0, str(tmp_path / "a.tif"))
    assert [call[0] for call in calls] == [1.0]
    assert "ladder" not in provenance


def test_parse_orders_rungs_finest_first_and_drops_malformed():
    rungs = INSETS._parse_resolution_ladder(
        "10|coarse|u10; nonsense ;3|fine|u3;0|zero|u0")
    assert [(r["native_resolution_m"], r["label"]) for r in rungs] == [
        (3.0, "fine"), (10.0, "coarse")]


def test_shipped_usgs3dep_declares_the_ladder():
    providers = INSETS.initialize_elevation_providers_dict()
    usgs = providers["USGS3DEP"]
    rungs = usgs["resolution_ladder_rungs"]
    assert [r["native_resolution_m"] for r in rungs] == [3.0, 10.0]
    assert all("{west}" in r["discovery_url_template"] for r in rungs)
    assert "1/3 arc-second" in rungs[-1]["discovery_url_template"]
    assert usgs["native_resolution_m"] == 1.0          # rung 0 untouched


@requires_gdal
def test_airport_fetch_records_the_ladder_in_the_sidecar(
        tmp_path, monkeypatch, fake_strategy):
    plan, calls = fake_strategy
    plan.update({1.0: 0.0, 3.0: None, 10.0: 1.0})
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    record = INSETS.ensure_airport_insets(
        39, -107, {"KASE": BOX}, [_definition()], None)
    assert record["KASE"]["FAKE3DEP"] == "ok"
    sidecar = FNAMES.airport_inset_provenance(39, -107, "KASE", "FAKE3DEP")
    with open(sidecar) as handle:
        meta = json.load(handle)
    assert meta["ladder"]["delivered_label"] == "1/3 arc-second"
    assert meta["resolution_m"] == 10.0
    assert meta["native_resolution_m"] == 10.0
