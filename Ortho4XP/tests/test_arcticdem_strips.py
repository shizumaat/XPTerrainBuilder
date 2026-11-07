"""ArcticDEM dated strips: newest-valid-first composite + EGM2008 shift.

ARCTICDEM2M.elv (``stac_dated_strips``) composites PGC strips newest
first, a cell taking the newest strip whose bitmask is 0 there, and
records which strip filled each cell; ``geoid_shift=egm2008`` then
reduces the WGS84 ellipsoidal heights to the engine's EGM2008 (Nuuk's
undulation is about +28 m, so H = h - N is ~28 m LOWER).  Synthetic
rasters in ``/vsimem``; no network.
"""

import numpy
import pytest

try:
    from osgeo import gdal, osr
    HAS_GDAL = True
except Exception:                                        # pragma: no cover
    HAS_GDAL = False

import O4_Airport_Elevation_Insets as INSETS
from elevation_access.base import ProviderUnavailable
from elevation_access import geoid_shift as GEOID
from elevation_access.strategies import stac_dated_strips as STRIPS

pytestmark = pytest.mark.skipif(not HAS_GDAL, reason="needs GDAL")

NODATA = -32768.0
#: A small box at Nuuk (BGGH).
BOX = (-51.70, 64.18, -51.66, 64.20)


def _item(item_id, stamp, dem="/vsimem/d.tif", mask="/vsimem/m.tif"):
    assets = {}
    if dem:
        assets["dem"] = {"href": dem}
    if mask:
        assets["mask"] = {"href": mask}
    return {"id": item_id, "properties": {"datetime": stamp},
            "assets": assets, "bbox": list(BOX)}


def test_strips_order_newest_first_and_need_both_assets():
    items = [
        _item("b", "2023-09-18T14:00:00Z"),
        _item("old", "2022-04-14T00:00:00Z"),
        _item("new", "2024-11-05T21:34:43Z"),
        _item("a", "2023-09-18T14:00:00Z"),
        _item("nomask", "2025-01-01T00:00:00Z", mask=None),
    ]
    ordered = STRIPS.strips_newest_first(items, "dem", "mask")
    assert [item["id"] for item in ordered] == ["new", "a", "b", "old"]


def test_fill_takes_the_newest_valid_cell_and_respects_the_bitmask():
    composite = numpy.full((2, 3), NODATA, dtype=numpy.float32)
    index = numpy.full((2, 3), STRIPS.NO_STRIP, dtype=numpy.int16)
    newest = numpy.array([[80, 81, NODATA], [82, 83, 84]], numpy.float32)
    newest_mask = numpy.array([[0, 0, 0], [2, 0, 4]], numpy.uint8)
    older = numpy.full((2, 3), 91.0, dtype=numpy.float32)
    clean = numpy.zeros((2, 3), numpy.uint8)
    assert STRIPS.fill_from_strip(composite, index, newest, newest_mask,
                                  0) == 3
    assert STRIPS.fill_from_strip(composite, index, older, clean, 1) == 3
    # The older strip only fills the nodata cell and the two masked ones
    # (water bit 2, cloud bit 4); the newer cells are never overwritten.
    assert composite.tolist() == [[80, 81, 91], [91, 83, 91]]
    assert index.tolist() == [[0, 0, 1], [1, 0, 1]]


def test_strip_index_round_trips_through_the_record():
    index = numpy.array([[0, 1, -1], [2, 2, 0]], dtype=numpy.int16)
    record = STRIPS.encode_strip_index(index)
    assert STRIPS.decode_strip_index(record).tolist() == index.tolist()


def _write_raster(path, values, box=BOX, dtype=None, nodata=NODATA):
    (rows, columns) = values.shape
    dataset = gdal.GetDriverByName("GTiff").Create(
        path, columns, rows, 1, dtype or gdal.GDT_Float32)
    (west, south, east, north) = box
    dataset.SetGeoTransform((west, (east - west) / columns, 0.0, north,
                             0.0, -(north - south) / rows))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    if nodata is not None:
        band.SetNoDataValue(nodata)
    band.WriteArray(values)
    dataset = None


def _read(path):
    dataset = gdal.Open(path)
    return (dataset.GetRasterBand(1).ReadAsArray(),
            dataset.GetMetadataItem(GEOID.GEOID_SHIFT_STAMP))


def test_geoid_undulation_at_nuuk_is_positive_and_the_shift_lowers():
    undulation = float(GEOID.geoid_undulation_m("egm2008", [64.19],
                                                [-51.68])[0])
    # NGA EGM2008 2.5' grid: 28.31 m at the airport.
    assert 27.9 < undulation < 28.7
    path = "/vsimem/geoid_shift.tif"
    values = numpy.full((20, 20), 110.0, dtype=numpy.float32)
    values[0, 0] = NODATA
    _write_raster(path, values)
    record = GEOID.apply_geoid_shift(path, {"geoid_shift": "egm2008"})
    (shifted, stamp) = _read(path)
    assert stamp == "egm2008"
    assert shifted[0, 0] == NODATA
    assert abs(float(shifted[10, 10]) - (110.0 - undulation)) < 0.2
    assert 27.5 < record["undulation_min_m"] <= record["undulation_max_m"]
    # A second pass over the stamped raster changes nothing.
    assert GEOID.apply_geoid_shift(path, {"geoid_shift": "egm2008"}) is None
    assert numpy.array_equal(_read(path)[0], shifted)
    gdal.Unlink(path)


def test_no_key_is_a_no_op_and_outside_the_grid_is_a_refusal():
    path = "/vsimem/geoid_none.tif"
    _write_raster(path, numpy.full((4, 4), 5.0, dtype=numpy.float32))
    assert GEOID.apply_geoid_shift(path, {}) is None
    assert _read(path) == (pytest.approx(numpy.full((4, 4), 5.0)), None)
    gdal.Unlink(path)
    with pytest.raises(ProviderUnavailable):
        GEOID.geoid_undulation_m("egm2008", [30.0], [-51.0])
    with pytest.raises(ProviderUnavailable):
        GEOID.geoid_undulation_m("egm96", [64.0], [-51.0])


def test_fetch_composites_strips_newest_first_and_records_provenance(
        monkeypatch, tmp_path):
    shape = (40, 40)
    newest = numpy.full(shape, 80.0, dtype=numpy.float32)
    newest[:, 20:] = NODATA                      # strip edge: east half
    newest_mask = numpy.zeros(shape, numpy.uint8)
    newest_mask[:10, :] = 2                      # water bit, north rows
    older = numpy.full(shape, 91.0, dtype=numpy.float32)
    _write_raster("/vsimem/new_dem.tif", newest)
    _write_raster("/vsimem/new_mask.tif", newest_mask,
                  dtype=gdal.GDT_Byte, nodata=None)
    _write_raster("/vsimem/old_dem.tif", older)
    _write_raster("/vsimem/old_mask.tif", numpy.zeros(shape, numpy.uint8),
                  dtype=gdal.GDT_Byte, nodata=None)
    items = [
        _item("OLD", "2022-04-14T00:00:00Z", "/vsimem/old_dem.tif",
              "/vsimem/old_mask.tif"),
        _item("NEW", "2024-11-05T21:34:43Z", "/vsimem/new_dem.tif",
              "/vsimem/new_mask.tif"),
    ]
    strategy = STRIPS.StacDatedStripsStrategy()
    monkeypatch.setattr(strategy, "discover", lambda *_args: items)
    destination = str(tmp_path / "BGGH_ARCTICDEM2M.tif")
    definition = {"code": "ARCTICDEM2M",
                  "access_strategy": "stac_dated_strips",
                  "native_resolution_m": 2}
    record = strategy.fetch(definition, BOX, 50.0, destination)
    (values, _stamp) = _read(destination)
    provenance = record["strip_provenance"]
    assert [strip["id"] for strip in provenance["strips"]] == ["NEW", "OLD"]
    assert provenance["covered_fraction"] == 1.0
    index = STRIPS.decode_strip_index(provenance["index_grid"])
    assert index.shape == values.shape
    (rows, columns) = values.shape
    # South-west: the newest strip; its masked north and absent east: OLD.
    assert index[rows - 1, 0] == 0 and values[rows - 1, 0] == 80.0
    assert index[0, 0] == 1 and values[0, 0] == 91.0
    assert index[rows - 1, columns - 1] == 1
    assert sum(strip["cells_filled"] for strip in provenance["strips"]) \
        == index.size
    assert record["source_ids"] == ["NEW", "OLD"]


def test_the_definition_parses_and_ranks_above_copernicus():
    INSETS.initialize_elevation_providers_dict()
    definitions = INSETS.elevation_providers_dict
    arctic = definitions["ARCTICDEM2M"]
    assert arctic["access_strategy"] == "stac_dated_strips"
    assert arctic["geoid_shift"] == "egm2008"
    assert arctic["priority"] > definitions["COPERNICUSGLO30"]["priority"]
    from elevation_access.definitions import provider_serves_country
    assert provider_serves_country(arctic, "GRL")
    assert not provider_serves_country(arctic, "EGY")


def test_a_raster_outside_the_grid_is_removed_never_kept_ellipsoidal():
    path = "/vsimem/geoid_south.tif"
    _write_raster(path, numpy.full((4, 4), 5.0, dtype=numpy.float32),
                  box=(-51.0, 30.0, -50.9, 30.1))
    with pytest.raises(ProviderUnavailable):
        GEOID.apply_geoid_shift(path, {"geoid_shift": "egm2008"})
    assert gdal.VSIStatL(path) is None
