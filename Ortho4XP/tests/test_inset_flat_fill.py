"""#1171: an inset whose valid pixels carry no relief is a provider fill.

A national coverage service asked beyond its extent can answer with a
constant FILL instead of nodata (the Spanish provider served 0.0 over
Morocco for GMTT, flattening a hill to sea level).  Such a raster is not
elevation data: the one predicate every reader asks
(``inset_is_effectively_empty``) declines it, the bake leaves the base
DEM in place with one plain line, and a fresh fetch that returns one is
recorded as no-coverage so the next provider is asked.
"""

import os

import numpy
import pytest

try:
    from osgeo import gdal
    HAS_GDAL = True
except Exception:                                        # pragma: no cover
    HAS_GDAL = False

import O4_Airport_Elevation_Insets as INSETS
from elevation_access import warp as ea_warp

pytestmark = pytest.mark.skipif(not HAS_GDAL, reason="needs GDAL")

NODATA = -32768.0


def _write(path, values):
    rows, columns = values.shape
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((-5.95, 0.1 / columns, 0.0,
                             35.78, 0.0, -0.1 / rows))
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteArray(values.astype(numpy.float32))
    dataset = None
    return str(path)


def _all_zero_fill(tmp_path):
    values = numpy.zeros((64, 64))
    values[:4, :] = NODATA                 # a nodata margin, as fetched
    return _write(tmp_path / "XFIL_fillprov.tif", values)


def test_an_all_zero_fill_is_declined_by_the_one_predicate(tmp_path):
    path = _all_zero_fill(tmp_path)
    assert ea_warp.inset_valid_fraction(path) > 0.9   # it LOOKS covered
    assert ea_warp.inset_carries_no_relief(path) is True
    (is_empty, fraction) = INSETS.inset_is_effectively_empty(path)
    assert is_empty is True and fraction > 0.9
    reason = INSETS.cached_inset_declined_reason(path)
    assert reason is not None and "no relief" in reason


def test_real_relief_is_kept(tmp_path):
    values = 20.0 + numpy.tile(numpy.linspace(0.0, 40.0, 64), (64, 1))
    path = _write(tmp_path / "XREL_fillprov.tif", values)
    assert ea_warp.inset_carries_no_relief(path) is False
    assert INSETS.inset_is_effectively_empty(path)[0] is False
    assert INSETS.cached_inset_declined_reason(path) is None


def test_a_flat_fill_below_the_floor_is_still_a_fill(tmp_path):
    values = numpy.full((64, 64), 0.0)
    values[0, 0] = 0.5 * ea_warp.INSET_MIN_RELIEF_M
    path = _write(tmp_path / "XLOW_fillprov.tif", values)
    assert ea_warp.inset_carries_no_relief(path) is True


def test_the_bake_leaves_the_base_dem_under_a_fill(tmp_path, monkeypatch):
    """The hill stays a hill: nothing of the fill reaches the raster and
    the refusal is recorded beside the baked insets."""
    path = _all_zero_fill(tmp_path)
    monkeypatch.setattr(INSETS, "bake_candidate_inset_paths",
                        lambda tile: [path])
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile",
                        lambda tile: True)
    baked = []
    monkeypatch.setattr(INSETS, "_bake_one_inset",
                        lambda *a, **k: baked.append(a))
    hill = 120.0 + numpy.tile(numpy.linspace(0.0, 80.0, 16), (16, 1))
    dem = type("D", (), {"alt_dem": hill.copy(), "subdems": ()})()
    tile = type("T", (), {"lat": 35, "lon": -6, "dem": dem})()
    INSETS.bake_airport_insets_into_alt_dem(tile)
    assert baked == []
    assert numpy.array_equal(dem.alt_dem, hill)
    assert dem.airport_inset_provenance == []
    assert len(dem.airport_inset_nodata_refusals) == 1
