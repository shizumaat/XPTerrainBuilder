"""#1340: a provider's PARTIAL fill is masked as nodata; coastal 0 m survives.

AUSTRALIA5M served YMML's box as real ground in the south and exactly 0.0
over the north (62.7 % of the pixels, the airport centre included), with
nodata -32768 declared and never used: the airport was baked into a 0 m
pit.  The rule (``elevation_access.provider_fill``) masks a large, exactly
constant, edge- or centre-connected region when the provider declares the
value as its fill or the ground bordering it stands far from it -- and a
genuine sea beside a shore that rises out of it is kept.
"""

import json
import os

import numpy
import pytest

try:
    from osgeo import gdal
    HAS_GDAL = True
except Exception:                                        # pragma: no cover
    HAS_GDAL = False

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
from elevation_access import provider_fill as PF
from elevation_access import warp as ea_warp

pytestmark = pytest.mark.skipif(not HAS_GDAL, reason="needs GDAL")

NODATA = -32768.0
SIZE = 120
WEST, NORTH, DEG = 144.78, -37.62, 0.1


def _write(path, values, nodata=NODATA):
    rows, columns = values.shape
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((WEST, DEG / columns, 0.0,
                             NORTH, 0.0, -DEG / rows))
    band = dataset.GetRasterBand(1)
    if nodata is not None:
        band.SetNoDataValue(nodata)
    band.WriteArray(values.astype(numpy.float32))
    dataset = None
    return str(path)


def _read(path):
    dataset = gdal.Open(path)
    band = dataset.GetRasterBand(1)
    return band.ReadAsArray(), band.GetNoDataValue()


def _ground():
    """Real ground at 84-138 m, varied in both axes."""
    rows = numpy.linspace(0.0, 1.0, SIZE)[:, None]
    columns = numpy.linspace(0.0, 1.0, SIZE)[None, :]
    return 84.0 + 40.0 * rows + 14.0 * numpy.sin(6.0 * columns)


def _half_filled(tmp_path, nodata=NODATA):
    """The YMML shape: the north half (the box centre included) is 0.0."""
    values = _ground()
    values[:SIZE // 2 + 5, :] = 0.0
    return _write(tmp_path / "XFIL_fillprov.tif", values, nodata=nodata)


def _coastal(tmp_path):
    """A genuine coast: the west is sea at exactly 0.0, the shore rises
    out of it from 0.3 m to 30 m."""
    values = numpy.zeros((SIZE, SIZE))
    land = numpy.linspace(0.3, 30.0, SIZE // 2)[None, :]
    values[:, SIZE // 2:] = land + 0.01 * numpy.arange(SIZE)[:, None]
    return _write(tmp_path / "XSEA_seaprov.tif", values)


def test_an_edge_fill_beside_high_ground_is_masked(tmp_path):
    path = _half_filled(tmp_path)
    assert ea_warp.inset_valid_fraction(path) == 1.0     # it LOOKS covered
    record = PF.mask_provider_fill(path)
    assert record is not None and record["fill_value"] == 0.0
    values, nodata = _read(path)
    assert nodata == NODATA
    assert (values[: SIZE // 2, :] == NODATA).all()       # the fill is gone
    assert (values[-10:, :] > 80.0).all()                 # the ground stays
    # the TRUE coverage: the ground minus the smear rim
    assert 0.40 < record["valid_fraction"] < 0.46
    assert ea_warp.inset_valid_fraction(path) == pytest.approx(
        record["valid_fraction"], abs=0.01)
    assert PF.mask_provider_fill(path) is None             # idempotent


def test_a_raster_without_nodata_gains_one(tmp_path):
    path = _half_filled(tmp_path, nodata=None)
    record = PF.mask_provider_fill(path)
    assert record is not None
    assert _read(path)[1] == PF.PROVIDER_FILL_NODATA


def test_genuine_coastal_zero_is_not_masked(tmp_path):
    path = _coastal(tmp_path)
    before = _read(path)[0].copy()
    assert PF.mask_provider_fill(path) is None
    assert (_read(path)[0] == before).all()


def test_a_declared_fill_is_masked_even_on_a_low_coast(tmp_path):
    path = _coastal(tmp_path)
    record = PF.mask_provider_fill(path, declared_fills=(0.0,))
    assert record is not None and record["valid_fraction"] < 0.5


def test_a_whole_raster_constant_is_left_to_the_flat_fill_rule(tmp_path):
    values = numpy.zeros((SIZE, SIZE))
    values[:4, :] = NODATA
    path = _write(tmp_path / "XALL_fillprov.tif", values)
    assert PF.mask_provider_fill(path, declared_fills=(0.0,)) is None
    assert ea_warp.inset_carries_no_relief(path) is True


def test_small_or_nonzero_flat_regions_are_kept(tmp_path):
    values = _ground()
    values[50:55, 50:55] = 0.0               # a small interior zero patch
    values[:30, :30] = 97.25                 # a hydro-flattened lake
    path = _write(tmp_path / "XLAK_fillprov.tif", values)
    assert PF.mask_provider_fill(path) is None


def test_declared_fills_parse_and_australia5m_declares_zero():
    assert PF.declared_provider_fills({"provider_fill_value": "0; -9999"}) \
        == (0.0, -9999.0)
    assert PF.declared_provider_fills({}) == ()
    providers = INSETS.initialize_elevation_providers_dict()
    assert PF.declared_provider_fills(providers["AUSTRALIA5M"]) == (0.0,)


def test_the_airport_cover_rule(tmp_path):
    path = _half_filled(tmp_path)
    PF.mask_provider_fill(path)
    north_box = (WEST, NORTH - 0.03, WEST + DEG, NORTH)
    south_box = (WEST, NORTH - DEG, WEST + DEG, NORTH - 0.07)
    reason = INSETS.inset_airport_cover_reason(path, north_box)
    assert reason is not None and "airport boundary" in reason
    assert INSETS.inset_airport_cover_reason(path, south_box) is None
    assert INSETS.inset_airport_cover_reason(path, None) is None


class _FillingStrategy:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path

    def fetch(self, definition, box, target, destination):
        values = _ground()
        values[: SIZE // 2 + 5, :] = 0.0
        _write(destination, values)
        return {"provider": definition["code"]}


def test_every_fetch_masks_and_records_the_fill(tmp_path):
    destination = str(tmp_path / "XFET_fillprov.tif")
    provenance = INSETS._fetch_masking_provider_fill(
        _FillingStrategy(tmp_path), {"code": "FILLPROV"},
        (WEST, NORTH - DEG, WEST + DEG, NORTH), 5.0, destination)
    assert provenance["provider_fill"]["fill_value"] == 0.0
    json.dumps(provenance)                       # sidecar-safe
    assert ea_warp.inset_valid_fraction(destination) < 0.5


def test_bathymetry_is_never_judged(tmp_path):
    path = _half_filled(tmp_path)
    assert INSETS.mask_fetched_provider_fill(
        path, {"code": "B", "role": INSETS.ROLE_BATHYMETRY}) is None
    assert ea_warp.inset_valid_fraction(path) == 1.0


# =====================================================================
# THE CACHED RE-CHECK: a fill cached before the rule stops poisoning
# =====================================================================
LAT, LON = -38, 144
ICAO = "XFIL"
BOX = (WEST, NORTH - DEG, WEST + DEG, NORTH)


def _cached_corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir",
                        str(tmp_path / "Elevation_data"))
    raster = FNAMES.airport_inset_dem(LAT, LON, ICAO, "FILLPROV")
    os.makedirs(os.path.dirname(raster))
    values = _ground()
    values[: SIZE // 2 + 5, :] = 0.0
    _write(raster, values)
    with open(raster[:-4] + ".json", "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump({"provider": "FILLPROV",
                   "bounding_box_wgs84": list(BOX)}, handle)
    ea_warp._inset_valid_fraction_cache.clear()
    return raster


def _ensure(monkeypatch, airport_box, fetch):
    from shapely import geometry

    monkeypatch.setattr(INSETS, "fetch_inset", fetch)
    INSETS.ensure_airport_insets(
        LAT, LON, {ICAO: BOX},
        [{"code": "FILLPROV", "access_strategy": "wcs",
          "coverage_bbox": "144,-38,145,-37"}],
        5.0, airport_polygons={ICAO: geometry.box(*airport_box)})
    return INSETS._read_index(LAT, LON)[ICAO]["FILLPROV"]


def test_a_cached_fill_over_the_airport_is_no_cache(tmp_path, monkeypatch):
    raster = _cached_corpus(tmp_path, monkeypatch)
    seen = []

    def fetch(definition, box, resolution, destination, **kwargs):
        seen.append(destination)
        return None                     # the provider answers no coverage

    status = _ensure(monkeypatch, (WEST + 0.03, NORTH - 0.04,
                                   WEST + 0.07, NORTH - 0.01), fetch)
    assert len(seen) == 1               # it was asked again
    assert status == INSETS.NO_COVERAGE
    assert not os.path.isfile(raster)   # the poisoned raster is gone


def test_a_cached_fill_beside_the_airport_is_masked_and_kept(tmp_path,
                                                             monkeypatch):
    raster = _cached_corpus(tmp_path, monkeypatch)

    def fetch(*a, **k):
        raise AssertionError("a covering cache must never refetch")

    status = _ensure(monkeypatch, (WEST + 0.03, NORTH - 0.095,
                                   WEST + 0.07, NORTH - 0.07), fetch)
    assert status == "ok"
    values, nodata = _read(raster)
    assert (values[: SIZE // 2, :] == nodata).all()
