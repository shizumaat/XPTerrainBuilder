"""The masked-footprint fill never stands above the fetched surface (#2066).

A surface model carries ground plus whatever stands on it, so the ground
under a masked pixel is never above the surface measured there.  The
nearest-ground fill copies a rim value across the masked component; on a
slope that copy stands above the surface on the low side (LOWS
Festungsberg: a 488 m plateau where the surface falls 519 -> 435 m).
``_clamp_fill_to_surface`` lowers those pixels to the surface, for both
fill methods, and leaves a flat apron's fill (below its roofs) unchanged.

Hermetic: synthetic rasters only, no network, no airport builds.
"""

import numpy
import O4_Airport_Elevation_Insets as INSETS
import pytest
from shapely import geometry as shapely_geometry

try:
    from osgeo import gdal

    HAS_GDAL = True
except Exception:
    HAS_GDAL = False

requires_gdal = pytest.mark.skipif(
    not HAS_GDAL, reason="osgeo (GDAL python bindings) not available"
)

PIXEL_M = 3.0
STEP = PIXEL_M / 111320.0
SIZE = 120
BOX = (0.0, -SIZE * STEP, SIZE * STEP, 0.0)
METHODS = (INSETS.INSET_FILL_METHOD_DISTANCE_TRANSFORM,
           INSETS.INSET_FILL_METHOD_LEGACY)


def _write(path, values):
    dataset = gdal.GetDriverByName("GTiff").Create(
        path, values.shape[1], values.shape[0], 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((0.0, STEP, 0.0, 0.0, 0.0, -STEP))
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-32768.0)
    band.WriteArray(values.astype(numpy.float32))
    dataset = None


def _read(path):
    dataset = gdal.Open(path)
    values = dataset.GetRasterBand(1).ReadAsArray()
    dataset = None
    return values


def _footprint(col0, col1, row0, row1):
    """A footprint polygon over pixel columns/rows (half-open)."""
    return shapely_geometry.box(col0 * STEP, -row1 * STEP,
                                col1 * STEP, -row0 * STEP)


def _mask(tmp_path, monkeypatch, values, footprint, method, clamp=True):
    """Run the masking pass; ``clamp=False`` (call it LAST) disables the
    clamp for the rest of the test, to show what it changes."""
    monkeypatch.setenv("O4_INSET_FILL_METHOD", method)
    monkeypatch.setattr(INSETS, "has_gdal", True)
    monkeypatch.setattr(
        INSETS, "_collect_inset_building_footprints",
        lambda *args, **kwargs: ([footprint], "test footprints"))
    monkeypatch.setattr(INSETS, "package_footprint_pack_names",
                        lambda box: [])
    if not clamp:
        monkeypatch.setattr(INSETS, "_clamp_fill_to_surface",
                            lambda *args: None)
    path = str(tmp_path / ("inset_%s_%d.tif" % (method, clamp)))
    _write(path, values)
    summary = INSETS.mask_building_footprints_in_surface_model(
        path, BOX, {"code": "TEST", "footprint_mask_buffer_m": 0,
                    INSETS.RESIDUAL_STRUCTURE_MASKING: False})
    return summary, _read(path)


def _hillside():
    """Ground falling 0.5 m per metre eastward (a hill's flank)."""
    columns = numpy.mgrid[0:SIZE, 0:SIZE][1]
    return 400.0 - 0.5 * PIXEL_M * columns


@requires_gdal
@pytest.mark.parametrize("method", METHODS)
def test_hillside_fill_never_stands_above_the_surface(
        tmp_path, monkeypatch, method):
    surface = _hillside()
    # A narrow, tall masked block: its west half copies the HIGH west rim.
    footprint = _footprint(40, 60, 20, 100)
    summary, filled = _mask(tmp_path, monkeypatch, surface, footprint,
                            method)
    _, unclamped = _mask(tmp_path, monkeypatch, surface, footprint, method,
                         clamp=False)
    block = (slice(22, 98), slice(42, 58))
    # The twin bites: the unclamped fill stands above the slope (12 m by
    # nearest ground, 2.8 m by the legacy inverse-distance inpaint).
    assert float((unclamped[block] - surface[block]).max()) > 1.0
    # The clamped fill never does, anywhere.
    assert float((filled - surface.astype(numpy.float32)).max()) <= 0.0
    assert summary[INSETS.FILL_CLAMP] == 1
    # Ground outside the footprint is byte-identical.
    assert numpy.array_equal(filled[:, :30],
                             surface[:, :30].astype(numpy.float32))


@requires_gdal
@pytest.mark.parametrize("method", METHODS)
def test_flat_apron_fill_is_unchanged_by_the_clamp(
        tmp_path, monkeypatch, method):
    surface = numpy.full((SIZE, SIZE), 25.0)
    surface[50:70, 50:70] += 12.0          # a terminal roof
    footprint = _footprint(50, 70, 50, 70)
    _, filled = _mask(tmp_path, monkeypatch, surface, footprint, method)
    _, unclamped = _mask(tmp_path, monkeypatch, surface, footprint, method,
                         clamp=False)
    assert numpy.array_equal(filled, unclamped)
    assert float(abs(filled[52:68, 52:68] - 25.0).max()) < 0.5


@requires_gdal
@pytest.mark.parametrize("method", METHODS)
def test_radar_pit_under_a_footprint_is_not_dug_back_in(
        tmp_path, monkeypatch, method):
    """A pit narrower than the structure window is not ground (OTHH
    25.283, 51.605: -8 m in 4 m ground under the terminal)."""
    surface = numpy.full((SIZE, SIZE), 4.0)
    surface[50:70, 50:70] += 12.0          # the roof
    surface[56:62, 56:63] = -8.0           # the radar pit inside it
    footprint = _footprint(50, 70, 50, 70)
    _, filled = _mask(tmp_path, monkeypatch, surface, footprint, method)
    assert float(abs(filled[50:70, 50:70] - 4.0).max()) < 0.5
