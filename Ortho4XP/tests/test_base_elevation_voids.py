"""Twins for the base void fill (issue #1465).

``N47E007.hgt`` holds 27,883 void posts; the DEM load used to set every
one of them to 0 m because there were more than the neighbour fill's
10,000.  The rule these twins hold: voids the neighbour fill closes are
closed by it as before; the rest take the first ranked fallback source,
offset to meet the base at the void's edge, then the nearest base post;
0 m is never written for a void.

No network: the fallback strategy writes a local file.
"""

import os

import numpy
import O4_Airport_Elevation_Insets as INSETS
import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_UI_Utils as UI
import pytest
from auto_patch import provenance
from elevation_access import base_voids
from elevation_access import registry as ea_registry

NODATA = -32768
SIDE = 101
CELL = (47, 7)


def _slope():
    """A tilted plane, 500 m at the north-west corner."""
    rows, cols = numpy.mgrid[0:SIDE, 0:SIDE]
    return (500.0 - rows - 0.5 * cols).astype(numpy.float32)


def _with_void(values, size=60):
    """``values`` with a square void too wide for the neighbour fill."""
    holed = values.copy()
    start = (SIDE - size) // 2
    holed[start:start + size, start:start + size] = NODATA
    return holed


class _Donor:
    """A fallback writing the same plane 8 m higher (a surface model)."""

    calls = []
    failing = False

    def covers(self, definition, lat, lon):
        return True

    def tile_cache_path(self, definition, lat, lon):
        return "%s_%s.hgt" % (FNAMES.base_file_name(lat, lon),
                              definition["code"])

    def ensure_tile(self, definition, lat, lon, verbose=True):
        _Donor.calls.append(definition["code"])
        if _Donor.failing:
            raise RuntimeError("bucket unreachable")
        path = self.tile_cache_path(definition, lat, lon)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        numpy.round(_slope() + 8.0).astype(">i2").tofile(path)
        return 1


@pytest.fixture
def providers(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setitem(ea_registry.ACCESS_STRATEGIES, "_donor", _Donor)
    monkeypatch.setattr(UI, "red_flag", False)
    _Donor.calls, _Donor.failing = [], False
    return {"SPARE1": {"code": "SPARE1", "role": "base",
                       "fallback_rank": "1", "access_strategy": "_donor"}}


def test_voids_the_neighbour_fill_closes_are_filled_as_before(providers):
    holed = _with_void(_slope(), size=4)
    legacy = holed.copy()
    assert DEM.fill_nodata_values_with_nearest_neighbor(legacy, NODATA)
    filled = holed.copy()
    assert base_voids.fill_base_voids(
        filled, NODATA, *CELL, providers) == (True, [])
    assert numpy.array_equal(filled, legacy)
    assert _Donor.calls == []


def test_a_wide_void_takes_the_fallback_offset_to_the_base(providers):
    plane = _slope()
    holed = _with_void(plane)
    void = holed == NODATA
    (filled, records) = base_voids.fill_base_voids(
        holed, NODATA, *CELL, providers)
    assert filled
    assert [r["code"] for r in records] == ["SPARE1"]
    assert records[0]["voids"] == int(void.sum())
    assert not (holed == NODATA).any()
    assert not (holed[void] == 0).any()
    assert numpy.array_equal(holed[~void], plane[~void])
    # The donor's +8 m is offset away: the plane is recovered (to the
    # donor file's whole-metre rounding).
    assert numpy.abs(holed[void] - plane[void]).max() <= 1.0


def test_without_a_fallback_the_nearest_base_post_fills_never_zero(
        providers):
    _Donor.failing = True
    plane = _slope()
    holed = _with_void(plane)
    void = holed == NODATA
    (filled, records) = base_voids.fill_base_voids(
        holed, NODATA, *CELL, providers)
    assert filled and records == []
    assert not (holed == NODATA).any()
    lo = plane[~void].min()
    assert (holed[void] >= lo).all() and not (holed[void] == 0).any()


def test_a_raster_with_no_valid_post_is_left_to_the_caller(providers):
    empty = numpy.full((SIDE, SIDE), NODATA, dtype=numpy.float32)
    assert base_voids.fill_base_voids(
        empty, NODATA, *CELL, providers) == (False, [])
    assert (empty == NODATA).all()


def test_the_dem_load_fills_a_base_cell_from_the_fallback(
        providers, monkeypatch):
    monkeypatch.setattr(INSETS, "elevation_providers_dict", providers)
    holed = _with_void(_slope())
    dem = DEM.DEM.__new__(DEM.DEM)
    (dem.lat, dem.lon, dem.nodata) = (*CELL, NODATA)
    (dem.alt_dem, dem.base_void_fills) = (holed, [])
    dem.fill_base_voids()
    assert not (dem.alt_dem == NODATA).any()
    assert [r["code"] for r in dem.base_void_fills] == ["SPARE1"]


def test_a_coarse_cell_keeps_its_wide_voids_void_on_the_fine_grid():
    rows, cols = numpy.mgrid[0:1201, 0:1201]
    coarse = (900.0 - 0.1 * rows).astype(numpy.float32)
    coarse[400:500, 400:500] = NODATA
    fine = DEM.upsample_keeping_voids(coarse, NODATA)
    assert fine.shape == (3601, 3601)
    void = fine == NODATA
    assert void[1200:1497, 1200:1497].all()
    assert not void[:1190].any()
    assert fine[~void].min() > 700
    small = (900.0 - 0.1 * rows).astype(numpy.float32)
    small[10, 10] = NODATA
    legacy = small.copy()
    DEM.fill_nodata_values_with_nearest_neighbor(legacy, NODATA)
    assert numpy.array_equal(DEM.upsample_keeping_voids(small, NODATA),
                             DEM.upsample(legacy))


class _Tile:
    lat, lon = CELL

    def __init__(self, dem):
        self.dem = dem


class _Dem:
    source_path = ""


def test_void_fills_enter_the_fingerprint_only_when_present(tmp_path):
    plain = provenance.dem_fingerprint(_Tile(_Dem()))
    empty = _Dem()
    empty.base_void_fills = []
    assert provenance.dem_fingerprint(_Tile(empty)) == plain
    path = str(tmp_path / "N47E007_SPARE1.hgt")
    numpy.zeros((5, 5), dtype=">i2").tofile(path)
    filled = _Dem()
    filled.base_void_fills = [
        {"cell": "+47+007", "code": "SPARE1", "path": path, "voids": 9}]
    assert provenance.dem_fingerprint(_Tile(filled)) != plain
