"""The ``geoid_shift`` key: ellipsoidal heights become EGM2008 heights.

The engine's terrain is orthometric on EGM2008 (the Copernicus base DEM,
the CIFP thresholds).  A provider that delivers heights above the WGS84
ELLIPSOID (photogrammetric strips such as PGC's ArcticDEM) declares
``geoid_shift=egm2008`` in its ``.elv``; after the fetch, every valid cell
loses the geoid undulation N at its own position (``H = h - N``).  In
Greenland N is about +25..+35 m, so an unshifted raster would stand that
far above the base DEM.

The undulations come from a grid bundled with the engine
(``Providers/Geoid``) -- PROJ grids are never downloaded at run time
(``PROJ_NETWORK=OFF``, :mod:`O4_Proj_Runtime`).  The bundled grid holds
EGM2008 north of 45 N at 7.5 arc-minutes in centimetres; bilinear reads of
it stay within 0.35 m of the 2.5-minute NGA grid (p99 0.07 m over
50-84 N).  A cell outside the grid is a refusal, never an unshifted cell.

The raster is stamped (``O4_GEOID_SHIFT_APPLIED``) so a second pass over
the same file is a no-op.
"""

import os

import numpy

from elevation_access.base import ProviderUnavailable
from elevation_access.gdal_support import gdal

__all__ = [
    "GEOID_GRID_FILES",
    "GEOID_SHIFT_KEY",
    "GEOID_SHIFT_STAMP",
    "apply_geoid_shift",
]


#: The ``.elv`` key naming the geoid the source's ellipsoidal heights are
#: reduced to.  Absent: heights pass through unchanged.
GEOID_SHIFT_KEY = "geoid_shift"


#: GDAL metadata item stamped on a shifted raster (its value: the model).
GEOID_SHIFT_STAMP = "O4_GEOID_SHIFT_APPLIED"


#: Geoid model -> bundled grid file under ``Providers/Geoid``.
GEOID_GRID_FILES = {"egm2008": "egm2008_north_of_45n_7p5min_cm.tif"}


#: The grid's cells are integer centimetres.
_GRID_SCALE_M = 0.01


_NODATA = -32768.0


_loaded_grids = {}


def _geoid_grid_dir():
    import O4_File_Names as FNAMES

    return os.path.join(FNAMES.Provider_dir, "Geoid")


def _load_grid(model, grid_dir=None):
    """``(values_m, origin_lon, origin_lat, step_deg)`` of a model's grid;
    the origin is the CENTRE of the north-west post."""
    path = os.path.join(grid_dir or _geoid_grid_dir(),
                        GEOID_GRID_FILES[model])
    if path in _loaded_grids:
        return _loaded_grids[path]
    dataset = gdal.Open(path) if os.path.isfile(path) else None
    if dataset is None:
        raise ProviderUnavailable("geoid grid %s is missing" % path)
    (left, step, _rx, top, _ry, step_y) = dataset.GetGeoTransform()
    values = dataset.GetRasterBand(1).ReadAsArray().astype(numpy.float64)
    grid = (values * _GRID_SCALE_M, left + step / 2.0, top + step_y / 2.0,
            step)
    _loaded_grids[path] = grid
    return grid


def geoid_undulation_m(model, latitudes, longitudes, grid_dir=None):
    """Bilinear geoid undulation N (metres) at each position.

    Raises :class:`ProviderUnavailable` when a position lies outside the
    bundled grid or the model is unknown."""
    if model not in GEOID_GRID_FILES:
        raise ProviderUnavailable(
            "geoid_shift=%s is not one of %s"
            % (model, "|".join(sorted(GEOID_GRID_FILES))))
    (values, origin_lon, origin_lat, step) = _load_grid(model, grid_dir)
    latitudes = numpy.asarray(latitudes, dtype=numpy.float64)
    longitudes = numpy.asarray(longitudes, dtype=numpy.float64)
    rows = (origin_lat - latitudes) / step
    columns = (longitudes - origin_lon) / step
    (row_count, column_count) = values.shape
    if rows.size and (rows.min() < 0 or rows.max() > row_count - 1
                      or columns.min() < 0
                      or columns.max() > column_count - 1):
        raise ProviderUnavailable(
            "geoid_shift=%s: the raster lies outside the bundled %s grid"
            % (model, GEOID_GRID_FILES[model]))
    row0 = numpy.minimum(numpy.floor(rows).astype(int), row_count - 2)
    column0 = numpy.minimum(numpy.floor(columns).astype(int),
                            column_count - 2)
    fraction_row = rows - row0
    fraction_column = columns - column0
    top = (values[row0, column0] * (1.0 - fraction_column)
           + values[row0, column0 + 1] * fraction_column)
    bottom = (values[row0 + 1, column0] * (1.0 - fraction_column)
              + values[row0 + 1, column0 + 1] * fraction_column)
    return top * (1.0 - fraction_row) + bottom * fraction_row


def _shift_open_raster(dataset, model, grid_dir):
    """Subtract N from the valid cells of an open raster; the N range."""
    band = dataset.GetRasterBand(1)
    values = band.ReadAsArray().astype(numpy.float64)
    nodata = band.GetNoDataValue()
    valid = numpy.isfinite(values) & (
        values != (_NODATA if nodata is None else nodata))
    (left, step_x, _rx, top, _ry, step_y) = dataset.GetGeoTransform()
    (rows, columns) = values.shape
    (lon_grid, lat_grid) = numpy.meshgrid(
        left + (numpy.arange(columns) + 0.5) * step_x,
        top + (numpy.arange(rows) + 0.5) * step_y)
    undulation = geoid_undulation_m(model, lat_grid, lon_grid, grid_dir)
    values[valid] -= undulation[valid]
    band.WriteArray(values.astype(numpy.float32))
    band.FlushCache()
    dataset.SetMetadataItem(GEOID_SHIFT_STAMP, model)
    return (float(undulation.min()), float(undulation.max()))


def apply_geoid_shift(raster_path, definition, grid_dir=None):
    """Reduce ``raster_path``'s valid cells from ellipsoidal heights to the
    definition's ``geoid_shift`` model, in place.

    Returns the provenance record (model, undulation range) or ``None``
    when the definition carries no key or the raster is already stamped.
    A failure removes the raster and raises :class:`ProviderUnavailable`:
    an ellipsoidal raster must never be baked as an orthometric one."""
    model = str((definition or {}).get(GEOID_SHIFT_KEY) or "").strip().lower()
    if not model or gdal.VSIStatL(raster_path) is None:
        return None
    dataset = gdal.Open(raster_path, gdal.GA_Update)
    try:
        if dataset.GetMetadataItem(GEOID_SHIFT_STAMP):
            return None
        (low, high) = _shift_open_raster(dataset, model, grid_dir)
    except ProviderUnavailable:
        dataset = None
        gdal.Unlink(raster_path)
        raise
    finally:
        dataset = None
    return {
        "model": model,
        "source_heights": "WGS84 ellipsoidal",
        "undulation_min_m": round(low, 3),
        "undulation_max_m": round(high, 3),
        "grid": GEOID_GRID_FILES[model],
    }
