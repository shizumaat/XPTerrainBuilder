"""Base voids: a void post of a base cell is never given 0 m (#1465).

THE RULE.  A void post of a base cell read from the configured base
source is filled, in this order:

1. by the neighbour fill (``O4_DEM_Utils.fill_nodata_values_with_nearest_
   neighbor``) when it closes every void -- fewer than its 10,000-post
   limit, within its 20 steps -- exactly as before, so a tile it always
   served is unchanged;
2. else from the first ranked fallback source (``base_fallback.
   fallback_definitions``: Copernicus GLO-30, then GLO-90) that covers
   the cell and holds data at the post, OFFSET by the base-minus-fallback
   difference at the nearest valid base post, so the fill meets the base
   at the void's edge (GLO-30 is a surface model: +7.5 m mean against
   Viewfinderpanoramas, measured 2026-10-12);
3. else by the nearest valid base post's height.

A raster with no valid post has nothing to fill from and is returned
unchanged for the caller's old zero.  Each fallback read is returned as
a record ``{"cell", "code", "path", "voids"}`` for the provenance stamp.
"""

import numpy
import O4_DEM_Utils as DEM
import O4_UI_Utils as UI
from scipy.ndimage import (
    distance_transform_edt,
    map_coordinates,
    uniform_filter,
)

from elevation_access import base_fallback
from elevation_access.base_tiles import cached_elevation_file_is_valid

__all__ = [
    "SMOOTHING_PASSES", "fill_base_voids", "offset_fill", "on_base_grid",
]

#: 3 x 3 mean passes over the filled posts only (the valid posts stay
#: fixed): they soften the creases the nearest-post offset leaves where
#: two rim posts of different offset meet inside a void.
SMOOTHING_PASSES = 3


def offset_fill(values, void, donor=None):
    """Fill ``values[void]`` in place: ``donor`` plus the difference
    ``values - donor`` of the nearest non-void post (``donor`` absent:
    the nearest non-void post's height).  Returns False, changing
    nothing, when no post is valid."""
    if not void.any():
        return True
    if void.all():
        return False
    donor = numpy.zeros_like(values) if donor is None else donor
    residual = numpy.where(void, 0.0, values - donor).astype(numpy.float64)
    nearest = distance_transform_edt(
        void, return_distances=False, return_indices=True)
    residual = residual[tuple(nearest)]
    for _pass in range(SMOOTHING_PASSES):
        smoothed = uniform_filter(residual, size=3, mode="nearest")
        residual = numpy.where(void, smoothed, residual)
    values[void] = (donor[void] + residual[void]).astype(values.dtype)
    return True


def on_base_grid(values, valid, frame, shape):
    """A whole-degree cell (posts on both edges) sampled at the posts of
    a raster of ``shape`` spanning the tile-relative ``frame`` ``(x0, y0,
    x1, y1)``: ``(heights, valid)``.  Bilinear, so a post that lands on a
    cell post reads it exactly; a post outside the cell, or touching a
    void of it, is not valid."""
    (x0, y0, x1, y1) = frame
    (rows, cols) = shape
    span = values.shape[0] - 1
    x = x0 + (x1 - x0) * numpy.arange(cols) / (cols - 1)
    y = y1 - (y1 - y0) * numpy.arange(rows) / (rows - 1)
    (row_index, col_index) = numpy.meshgrid((1.0 - y) * span, x * span,
                                            indexing="ij")
    where = numpy.stack([row_index, col_index])
    heights = map_coordinates(numpy.where(valid, values, 0.0).astype(
        numpy.float64), where, order=1, mode="constant", cval=0.0)
    holes = map_coordinates((~valid).astype(numpy.float64), where, order=1,
                            mode="constant", cval=1.0)
    inside = ((row_index >= -1e-6) & (row_index <= span + 1e-6)
              & (col_index >= -1e-6) & (col_index <= span + 1e-6))
    return (heights, inside & (holes < 1e-6))


def _inside_cell(frame, shape):
    """Posts of a raster of ``shape`` over ``frame`` inside the cell."""
    (x0, y0, x1, y1) = frame
    (rows, cols) = shape
    x = x0 + (x1 - x0) * numpy.arange(cols) / (cols - 1)
    y = y1 - (y1 - y0) * numpy.arange(rows) / (rows - 1)
    tol = 1e-9
    return numpy.outer((y >= -tol) & (y <= 1 + tol),
                       (x >= -tol) & (x <= 1 + tol))


def _fallback_cell(definition, lat, lon, frame, shape):
    """The fallback's heights and valid mask on the base grid, or None."""
    strategy = base_fallback._strategy(definition)
    try:
        if not strategy.covers(definition, lat, lon):
            return None
        if not strategy.ensure_tile(definition, lat, lon, False):
            return None
    except Exception as error:
        UI.vprint(1, "    ", base_fallback.source_label(definition),
                  "could not fill the base voids:",
                  "%s: %s" % (type(error).__name__, error))
        return None
    path = base_fallback._cache_path(strategy, definition, lat, lon)
    if not path or not cached_elevation_file_is_valid(path):
        return None
    result = DEM.read_elevation_from_file(path, lat, lon, False)
    (nodata, values) = (result[5], result[-1])
    if values is None or values.ndim != 2 or values.shape[0] != (
            values.shape[1]) or values.shape[0] < 2:
        return None
    valid = (values != nodata) & numpy.isfinite(values)
    return (path,) + on_base_grid(values, valid, frame, shape)


def fill_base_voids(alt_dem, nodata, lat, lon, providers,
                    frame=(0.0, 0.0, 1.0, 1.0)):
    """Fill the void posts of base cell ``(lat, lon)`` under THE RULE,
    in place; ``frame`` is the raster's tile-relative extent ``(x0, y0,
    x1, y1)`` (a combined raster reaches beyond the cell, and its posts
    there only take the nearest-post fill).  Returns ``(filled,
    records)``: ``filled`` False only when the raster holds no valid
    post."""
    void = alt_dem == nodata
    if not void.any():
        return (True, [])
    trial = alt_dem.copy()
    if DEM.fill_nodata_values_with_nearest_neighbor(
            trial, nodata, zero_remainder=False):
        alt_dem[...] = trial
        return (True, [])
    if void.all():
        return (False, [])
    cell = base_fallback._cell_label(lat, lon)
    UI.vprint(1, "    Elevation cell", cell, "has", int(void.sum()),
              "void posts; filling them from the fallback sources.")
    records = []
    donor = numpy.zeros(alt_dem.shape, dtype=numpy.float64)
    donated = numpy.zeros(alt_dem.shape, dtype=bool)
    # Only posts inside the cell can be donated: a void beyond it (the
    # combined raster's margin) asks no further source.
    in_cell = _inside_cell(frame, alt_dem.shape)
    for definition in base_fallback.fallback_definitions(providers or {}):
        if not (void & in_cell & ~donated).any() or UI.red_flag:
            break
        fallback = _fallback_cell(definition, lat, lon, frame,
                                  alt_dem.shape)
        if fallback is None:
            continue
        (path, values, valid) = fallback
        # Where the base is valid the fallback supplies the offset's
        # reference, so it must be valid there too: posts it lacks there
        # are left to the next source's (or nearest-post) reference.
        take = valid & ~donated
        donor[take] = values[take]
        donated |= take
        records.append({"cell": cell, "code": definition["code"],
                        "path": path, "voids": int((void & take).sum())})
    from_donor = void & donated
    if from_donor.any():
        # The offset reference: posts where the base AND the donor hold
        # data.  Everything else is unknown to the offset field.
        filled = alt_dem.astype(numpy.float64)
        if offset_fill(filled, void | ~donated, donor):
            alt_dem[from_donor] = filled[from_donor].astype(alt_dem.dtype)
            void = void & ~donated
    if void.any():
        filled = alt_dem.astype(numpy.float64)
        offset_fill(filled, void)
        alt_dem[void] = filled[void].astype(alt_dem.dtype)
    records = [record for record in records if record["voids"]]
    for record in records:
        UI.vprint(1, "    Elevation cell", cell + ":", record["voids"],
                  "void posts filled from", record["code"], "(%s)."
                  % record["path"])
    return (True, records)
