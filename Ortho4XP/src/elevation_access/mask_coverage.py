"""Which parts of an AIRPORT MASK a cached raster holds data over (#1770).

A raster's whole-file valid share says nothing about the airport it was
fetched for: a coastal aerodrome's inset box is often mostly sea, which
the provider serves as nodata, while the cells under the aerodrome are
all data.  These helpers sample the mask itself on one grid and ask each
raster, per sample, whether it holds data there -- so every raster over
one mask is judged on the SAME points and their coverage can be unioned.
"""

import math

import numpy

from elevation_access.gdal_support import gdal, has_gdal

__all__ = ["mask_sample_points", "raster_valid_at_points"]

#: Samples per axis of the mask's bounding box.  256 x 256 puts a sample
#: every ~15 m on a 4 km aerodrome: far finer than the 80 % coverage gate
#: needs, and one small read per raster.
MASK_SAMPLES_PER_AXIS = 256

#: The largest buffer read from one raster window; finer data is read
#: decimated (nearest), which only thins the cells a sample can land on.
_MAX_READ_PER_AXIS = 2048


def mask_sample_points(mask_geometry):
    """``(xs, ys)`` arrays: cell centres of a regular grid over the
    mask's bounds that fall inside the mask (the mask's own coordinates).
    Never empty for a non-empty mask: a sliver that no grid centre lands
    in is represented by its ``representative_point``."""
    import shapely

    (minx, miny, maxx, maxy) = mask_geometry.bounds
    count = MASK_SAMPLES_PER_AXIS
    xs = minx + (numpy.arange(count) + 0.5) * ((maxx - minx) / count)
    ys = miny + (numpy.arange(count) + 0.5) * ((maxy - miny) / count)
    (grid_x, grid_y) = numpy.meshgrid(xs, ys)
    grid_x = grid_x.ravel()
    grid_y = grid_y.ravel()
    inside = shapely.contains_xy(mask_geometry, grid_x, grid_y)
    if not inside.any():
        point = mask_geometry.representative_point()
        return (numpy.array([point.x]), numpy.array([point.y]))
    return (grid_x[inside], grid_y[inside])


def raster_valid_at_points(raster_path, lons, lats):
    """Boolean array: does ``raster_path`` hold data (finite, not its
    nodata) at each ``(lon, lat)``?  ``False`` outside the raster and
    everywhere when it cannot be read."""
    valid = numpy.zeros(len(lons), dtype=bool)
    if not has_gdal or not len(lons):
        return valid
    try:
        dataset = gdal.Open(raster_path)
        transform = dataset.GetGeoTransform()
        width = dataset.RasterXSize
        height = dataset.RasterYSize
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
    except Exception:
        return valid
    columns = numpy.floor((lons - transform[0]) / transform[1]).astype(int)
    rows = numpy.floor((lats - transform[3]) / transform[5]).astype(int)
    inside = (columns >= 0) & (columns < width) & (rows >= 0) & (rows < height)
    if not inside.any():
        return valid
    columns = columns[inside]
    rows = rows[inside]
    (col0, row0) = (int(columns.min()), int(rows.min()))
    window_w = int(columns.max()) + 1 - col0
    window_h = int(rows.max()) + 1 - row0
    buffer_w = min(window_w, _MAX_READ_PER_AXIS)
    buffer_h = min(window_h, _MAX_READ_PER_AXIS)
    try:
        values = band.ReadAsArray(col0, row0, window_w, window_h,
                                  buf_xsize=buffer_w, buf_ysize=buffer_h)
    except Exception:
        return valid
    if values is None:
        return valid
    buffer_cols = ((columns - col0) * buffer_w) // window_w
    buffer_rows = ((rows - row0) * buffer_h) // window_h
    sampled = values[buffer_rows, buffer_cols]
    held = numpy.isfinite(sampled)
    if nodata is not None and not math.isnan(nodata):
        held &= sampled != nodata
    valid[inside] = held
    return valid
