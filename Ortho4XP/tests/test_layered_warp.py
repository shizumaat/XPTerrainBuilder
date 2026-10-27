"""Twin of ``elevation_access.layered_warp`` (#1327, RULINGS 2026-10-26t):
a mosaic source every later source hides is never read, and the mosaic is
the single warp's, pixel for pixel."""
import os

import numpy
import pytest
from elevation_access import layered_warp
from elevation_access.gdal_support import gdal, has_gdal

pytestmark = pytest.mark.skipif(not has_gdal, reason="GDAL missing")

BOX = (7.0, 47.0, 7.02, 47.02)


def _raster(path, box, values, nodata=-9999.0):
    rows, columns = values.shape
    dataset = gdal.GetDriverByName("GTiff").Create(
        path, columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((box[0], (box[2] - box[0]) / columns, 0.0,
                             box[3], 0.0, -(box[3] - box[1]) / rows))
    dataset.SetProjection('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID['
                          '"WGS 84",6378137,298.257223563]],PRIMEM['
                          '"Greenwich",0],UNIT["degree",0.0174532925199433]]')
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    band.WriteArray(values)
    dataset = None
    return path


def _slope(rows, columns, offset):
    yy, xx = numpy.mgrid[0:rows, 0:columns]
    return (offset + 0.37 * xx + 0.11 * yy).astype(numpy.float32)


def _read(path):
    dataset = gdal.Open(path)
    values = dataset.ReadAsArray()
    dataset = None
    return values


@pytest.fixture
def mosaic(tmp_path):
    """Order = later wins: an old full-box tile, a west tile, the west
    tile's NEWER vintage with a hole, an east tile."""
    west = (7.0, 47.0, 7.01, 47.02)
    east = (7.01, 47.0, 7.02, 47.02)
    old = _raster(str(tmp_path / "old.tif"), BOX, _slope(80, 80, 100.0))
    west_old = _raster(str(tmp_path / "west_old.tif"), west,
                       _slope(80, 40, 200.0))
    newer = _slope(80, 40, 300.0)
    newer[30:40, 10:20] = -9999.0
    west_new = _raster(str(tmp_path / "west_new.tif"), west, newer)
    east_new = _raster(str(tmp_path / "east_new.tif"), east,
                       _slope(80, 40, 400.0))
    return ([old, west_old, west_new, east_new], [BOX, west, west, east])


def test_contiguous_layers_cut_from_the_end():
    a = (0.0, 0.0, 1.0, 1.0)
    b = (1.0, 0.0, 2.0, 1.0)
    sliver = (0.98, 0.0, 2.0, 1.0)  # a projected hull's sliver on a
    assert layered_warp.contiguous_layers([a, b, a, b]) == [[2, 3], [0, 1]]
    assert layered_warp.contiguous_layers([a, sliver]) == [[0, 1]]
    # an unknown footprint shares a chunk with nothing
    assert layered_warp.contiguous_layers([a, None, b]) == [[2], [1], [0]]


def test_matches_the_single_mosaic_and_skips_what_is_hidden(
        tmp_path, mosaic, monkeypatch):
    (sources, footprints) = mosaic
    plain = str(tmp_path / "plain.tif")
    assert layered_warp.warp_vsicurl_sources_to_geotiff(
        sources, BOX, 20.0, plain)
    asked = []
    real = layered_warp.warp_vsicurl_sources_to_geotiff

    def _spy(inputs, *args, **kwargs):
        asked.append([os.path.basename(path) for path in inputs])
        return real(inputs, *args, **kwargs)

    monkeypatch.setattr(layered_warp, "warp_vsicurl_sources_to_geotiff",
                        _spy)
    monkeypatch.setenv("O4_INSET_SCRATCH_DIR", str(tmp_path / "scratch"))
    layered = str(tmp_path / "layered.tif")
    (ok, read) = layered_warp.warp_sources_skipping_hidden(
        sources, footprints, BOX, 20.0, layered)
    assert ok
    numpy.testing.assert_array_equal(_read(layered), _read(plain))
    # the newest west tile's hole is filled from west_old; the full-box
    # old tile is under data everywhere and never read
    assert asked[0] == ["west_new.tif", "east_new.tif"]
    assert ["old.tif"] not in asked
    assert read == [1, 2, 3]
    assert layered_warp.hidden_sources_record(4, read) == {
        "hidden_sources_skipped": 1}
    assert not os.listdir(str(tmp_path / "scratch"))


def test_unknown_footprints_skip_only_once_no_hole_is_left(tmp_path,
                                                          mosaic):
    (sources, _footprints) = mosaic
    plain = str(tmp_path / "plain.tif")
    layered_warp.warp_vsicurl_sources_to_geotiff(sources, BOX, 20.0, plain)
    layered = str(tmp_path / "layered.tif")
    (ok, read) = layered_warp.warp_sources_skipping_hidden(
        sources, None, BOX, 20.0, layered)
    # each source is its own chunk; west_old fills the hole, after which
    # nothing is missing and the old full-box tile is not asked
    assert ok and read == [1, 2, 3]
    numpy.testing.assert_array_equal(_read(layered), _read(plain))


def test_a_raised_fill_leaves_no_partial_raster(tmp_path, mosaic,
                                                monkeypatch):
    (sources, footprints) = mosaic
    real = layered_warp.warp_vsicurl_sources_to_geotiff
    calls = []

    def _second_raises(inputs, *args, **kwargs):
        calls.append(inputs)
        if len(calls) > 1:
            raise RuntimeError("outage")
        return real(inputs, *args, **kwargs)

    monkeypatch.setattr(layered_warp, "warp_vsicurl_sources_to_geotiff",
                        _second_raises)
    monkeypatch.setenv("O4_INSET_SCRATCH_DIR", str(tmp_path / "scratch"))
    layered = str(tmp_path / "layered.tif")
    with pytest.raises(RuntimeError):
        layered_warp.warp_sources_skipping_hidden(
            sources, footprints, BOX, 20.0, layered)
    assert not os.path.exists(layered)
