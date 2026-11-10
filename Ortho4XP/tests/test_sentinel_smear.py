"""#1956: the rim an UNDECLARED fill leaves after the warp is masked.

TINITALY's WCS answers the sea with -9999 and declares no nodata, so the
bilinear warp blended the fill into the first pixel of ground; the
sanitizer dropped what fell below -600 m and the rest survived as coastal
pits (LICJ, LICC: down to -480 m in the beach strip).  The rule
(``elevation_access.sentinel_smear``) masks the whole rim of a raster
whose rim pixels stand far below the ground beside them and below sea
level, and leaves genuine coasts, cliffs and polders alone.
"""

import numpy
import pytest

try:
    from osgeo import gdal
    HAS_GDAL = True
except Exception:                                        # pragma: no cover
    HAS_GDAL = False

import O4_Airport_Elevation_Insets as INSETS
from elevation_access import sentinel_smear as SS
from elevation_access import warp as ea_warp

pytestmark = pytest.mark.skipif(not HAS_GDAL, reason="needs GDAL")

NODATA = -32768.0
FILL = -9999.0
SIZE = 160
WEST, NORTH, DEG = 13.07, 38.20, 0.016          # ~10 m pixels
BOX = (WEST + 0.001, NORTH - DEG + 0.001, WEST + DEG - 0.001, NORTH - 0.001)
WGS84 = ('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,'
         '298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",'
         '0.0174532925199433],AUTHORITY["EPSG","4326"]]')


def _write(path, values, nodata=None):
    rows, columns = values.shape
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((WEST, DEG / columns, 0.0,
                             NORTH, 0.0, -DEG / rows))
    dataset.SetProjection(WGS84)
    band = dataset.GetRasterBand(1)
    if nodata is not None:
        band.SetNoDataValue(nodata)
    band.WriteArray(values.astype(numpy.float32))
    dataset = None
    return str(path)


def _read(path):
    dataset = gdal.Open(path)
    band = dataset.GetRasterBand(1)
    values = band.ReadAsArray().astype(numpy.float64)
    nodata = band.GetNoDataValue()
    return values, (values != nodata) & numpy.isfinite(values)


def _coast():
    """Ground rising inland from a 2 m beach; the sea beyond a wavy
    shoreline (so the warp kernel straddles it at every fraction)."""
    rows = numpy.arange(SIZE)[:, None]
    columns = numpy.arange(SIZE)[None, :]
    shore = SIZE // 2 + (6.0 * numpy.sin(rows / 7.0)).astype(int)
    land = columns < shore
    ground = 2.0 + 0.3 * (shore - columns) + 0.05 * rows
    return land, numpy.where(land, ground, 0.0)


def _smeared_inset(tmp_path, target_m=10.0):
    """The LICJ chain in miniature: a source whose sea is an UNDECLARED
    -9999, warped by the shared warp core (bilinear, -600 m floor)."""
    (land, ground) = _coast()
    source = _write(tmp_path / "source.tif", numpy.where(land, ground, FILL))
    destination = str(tmp_path / "XSMR_smearprov.tif")
    assert ea_warp.warp_vsicurl_sources_to_geotiff(
        [source], BOX, target_m, destination)
    return destination


def _pits(path):
    values, valid = _read(path)
    return int((valid & (values < 0.0)).sum())


def test_the_warp_leaves_a_smear_and_the_rule_masks_it(tmp_path):
    path = _smeared_inset(tmp_path)
    assert _pits(path) >= SS.SMEAR_MIN_CELLS              # the defect
    before, before_valid = _read(path)
    record = SS.mask_sentinel_smear(path)
    assert record is not None and record["deepest_m"] < -SS.SMEAR_STEP_M
    after, after_valid = _read(path)
    assert _pits(path) == 0
    # Only rim pixels went; the ground behind them is untouched.
    assert numpy.array_equal(after[after_valid], before[after_valid])
    assert record["masked_pixels"] == int((before_valid & ~after_valid).sum())
    assert SS.mask_sentinel_smear(path) is None           # idempotent


def test_an_upsampling_warp_smears_wider_and_is_still_cleaned(tmp_path):
    path = _smeared_inset(tmp_path, target_m=4.0)
    assert SS.mask_sentinel_smear(path) is not None
    assert _pits(path) == 0


def test_a_declared_fill_leaves_no_smear(tmp_path):
    (land, ground) = _coast()
    source = _write(tmp_path / "source.tif", numpy.where(land, ground, FILL),
                    nodata=FILL)
    destination = str(tmp_path / "XDCL_declared.tif")
    assert ea_warp.warp_vsicurl_sources_to_geotiff(
        [source], BOX, 10.0, destination)
    assert _pits(destination) == 0
    assert SS.mask_sentinel_smear(destination) is None


def test_a_genuine_coast_under_a_sea_cliff_is_kept(tmp_path):
    """Nodata sea at the foot of a 60 m cliff fronted by a 0.5 m beach."""
    (land, ground) = _coast()
    cliff = numpy.where(ground > 4.0, ground + 60.0, 0.5)
    path = _write(tmp_path / "XCLF_cliff.tif",
                  numpy.where(land, cliff, NODATA), nodata=NODATA)
    assert SS.mask_sentinel_smear(path) is None


def test_a_polder_below_sea_level_is_kept(tmp_path):
    """Ground at -6..-2 m around a nodata lake with a 3 m ditch on its
    shore: below sea level, but no pixel a fill-sized step down."""
    rows = numpy.arange(SIZE)[:, None]
    columns = numpy.arange(SIZE)[None, :]
    values = -6.0 + 0.0125 * (rows + columns)
    radius2 = (rows - 80) ** 2 + (columns - 80) ** 2
    lake = radius2 < 30 ** 2
    values = numpy.where((radius2 < 31 ** 2) & ~lake, values - 3.0, values)
    path = _write(tmp_path / "XPLD_polder.tif",
                  numpy.where(lake, NODATA, values), nodata=NODATA)
    assert SS.mask_sentinel_smear(path) is None


def test_the_fetch_mask_pass_masks_a_cached_smear(tmp_path):
    """The pass every fetch and every cached inset / ring cell crosses."""
    path = _smeared_inset(tmp_path)
    INSETS.mask_fetched_provider_fill(path, {"code": "SMEARPROV"})
    assert _pits(path) == 0


def test_bathymetry_is_never_judged(tmp_path):
    path = _smeared_inset(tmp_path)
    INSETS.mask_fetched_provider_fill(
        path, {"code": "B", "role": INSETS.ROLE_BATHYMETRY})
    assert _pits(path) >= SS.SMEAR_MIN_CELLS
