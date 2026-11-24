"""The coarse depth fill: follows depth, stays off fine data and land."""
import os
import sys
from types import SimpleNamespace

import numpy
import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

gdal = pytest.importorskip("osgeo.gdal")
from osgeo import osr  # noqa: E402

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_Bathymetry_Coarse as COARSE  # noqa: E402
import O4_Bathymetry_Source_Revision as REVISION  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Geo_Utils as GEO  # noqa: E402

LAT, LON, ZOOM = 24, -78, 14


def _raster(path, values, west, north, step):
    driver = gdal.GetDriverByName("GTiff")
    data = driver.Create(str(path), values.shape[1], values.shape[0], 1,
                         gdal.GDT_Float32)
    data.SetGeoTransform((west, step, 0, north, 0, -step))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    data.SetProjection(srs.ExportToWkt())
    band = data.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values)
    data = None
    return str(path)


def _square():
    (til_x, til_y) = GEO.wgs84_to_orthogrid(LAT + 0.5, LON + 0.5, ZOOM)
    return (til_x, til_y)


def _tile(**extra):
    return SimpleNamespace(lat=LAT, lon=LON, mask_zl=ZOOM,
                           reef_visibility_depth=25.0,
                           masks_use_DEM_too="auto", **extra)


def _all_sea():
    return numpy.ones((6144, 6144), dtype=bool)


def test_bank_far_from_any_shore_shows_and_deep_water_stays_zero(tmp_path):
    values = numpy.full((300, 300), -2000.0, dtype=numpy.float32)
    values[:, :150] = -5.0                     # a bank, west half
    path = _raster(tmp_path / "c.tif", values, LON - 0.1, LAT + 1.1, 0.004)
    alpha = COARSE.square_alpha(*_square(), _tile(),
                                COARSE.CoarseFill(path, None), _all_sea())
    assert alpha is not None
    (til_x, _) = _square()
    (_, west) = GEO.gtile_to_wgs84(til_x, _square()[1], ZOOM)
    (_, east) = GEO.gtile_to_wgs84(til_x + 16, _square()[1], ZOOM)
    edge = LON - 0.1 + 150 * 0.004
    column = int(4096 * (edge - west) / (east - west))
    assert alpha[2048, max(column - 900, 0)] > 100
    if column + 900 < 4096:
        assert alpha[2048, column + 900] == 0
    assert alpha.max() <= round(255 * COARSE.MAXIMUM_OPACITY)


def test_all_deep_square_adds_nothing(tmp_path):
    values = numpy.full((300, 300), -2000.0, dtype=numpy.float32)
    path = _raster(tmp_path / "c.tif", values, LON - 0.1, LAT + 1.1, 0.004)
    assert COARSE.square_alpha(*_square(), _tile(),
                               COARSE.CoarseFill(path, None),
                               _all_sea()) is None


def test_alpha_is_zero_on_fine_data_and_off_the_sea(tmp_path):
    coarse = numpy.full((300, 300), -3.0, dtype=numpy.float32)
    path = _raster(tmp_path / "c.tif", coarse, LON - 0.1, LAT + 1.1, 0.004)
    fine = numpy.full((300, 300), -32768.0, dtype=numpy.float32)
    fine[:, :150] = -3.0
    fine_path = _raster(tmp_path / "f.tif", fine, LON - 0.1, LAT + 1.1, 0.004)
    from O4_Bathymetry_Band import read_band_window

    alpha = COARSE.square_alpha(*_square(), _tile(),
                                COARSE.CoarseFill(path, fine_path), _all_sea())
    window = read_band_window(*_square(), ZOOM, fine_path)
    valid = window[1024:5120, 1024:5120] > -32000.0
    assert valid.any() and not valid.all()
    assert alpha[valid].max() == 0
    assert alpha[~valid].max() > 100
    land = _all_sea()
    land[:] = False
    assert COARSE.square_alpha(*_square(), _tile(),
                               COARSE.CoarseFill(path, None), land) is None


@pytest.fixture
def provider(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "e"))
    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "o"))
    definition = {"code": "COARSETEST", "role": "bathymetry",
                  "native_resolution_m": 450.0, "source_revision": "2"}
    monkeypatch.setattr(INSETS, "select_bathymetry_definitions",
                        lambda lat, lon: [definition])
    return definition


def test_raster_is_fetched_once_and_keys_the_step(provider, monkeypatch):
    calls = []

    def fetch(definition, box, resolution, path):
        calls.append((box, resolution))
        _raster(path, numpy.full((10, 10), -3.0, dtype=numpy.float32),
                box[0], box[3], 0.12)
        return {"ok": True}

    monkeypatch.setattr(INSETS, "fetch_inset", fetch)
    tile = _tile()
    assert COARSE.fill_state(tile) is None      # no coastline cached yet
    fill = COARSE.ensure_coarse_fill(tile, None)
    assert fill is not None and os.path.isfile(fill.coarse_path)
    assert COARSE.ensure_coarse_fill(tile, None) == fill
    assert len(calls) == 1 and calls[0][1] == 450.0
    state = COARSE.fill_state(tile)
    assert state not in (None, REVISION.PENDING)


def test_durable_no_data_is_not_asked_again(provider, monkeypatch):
    calls = []
    monkeypatch.setattr(INSETS, "fetch_inset",
                        lambda *a, **k: calls.append(a))
    tile = _tile()
    assert COARSE.ensure_coarse_fill(tile, None) is None
    assert COARSE.ensure_coarse_fill(tile, None) is None
    assert len(calls) == 1 and COARSE.fill_state(tile) is None


def test_never_asked_coastal_tile_keeps_its_key_but_is_not_settled(
        provider, monkeypatch):
    import O4_Bathymetry_Band as BAND

    cached = FNAMES.osm_cached(LAT, LON, "coastline")
    os.makedirs(os.path.dirname(cached), exist_ok=True)
    open(cached, "wb").close()
    monkeypatch.setattr(BAND, "_cached_coastline_is_empty", lambda tile: False)
    assert COARSE.fill_state(_tile()) is None
    assert not COARSE.fill_is_settled(_tile())


def test_failed_fetch_is_pending_until_it_succeeds(provider, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("network")

    monkeypatch.setattr(INSETS, "fetch_inset", fail)
    tile = _tile()
    assert COARSE.ensure_coarse_fill(tile, None) is None
    assert COARSE.fill_state(tile) == REVISION.PENDING

    def fetch(definition, box, resolution, path):
        _raster(path, numpy.full((10, 10), -3.0, dtype=numpy.float32),
                box[0], box[3], 0.12)
        return {"ok": True}

    monkeypatch.setattr(INSETS, "fetch_inset", fetch)
    assert COARSE.ensure_coarse_fill(tile, None) is not None
    assert COARSE.fill_state(tile) not in (None, REVISION.PENDING)


def test_fine_only_mode_settings_have_no_fill_state(provider):
    assert COARSE.fill_state(_tile(
    ).__class__(**{**vars(_tile()), "masks_use_DEM_too": "True"})) is None
