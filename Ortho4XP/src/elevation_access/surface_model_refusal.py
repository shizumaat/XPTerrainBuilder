"""Surface-model insets: the pixels the base DEM models instead (#2280).

A satellite-stereo surface model (ArcticDEM's 2 m strips) is matched
from image texture.  Over WATER there is none, and under cloud or in a
bad pair the matcher returns BLUNDERS: EKVG's ArcticDEM inset held
mounds of +50 and +160 m in Leitisvatn (the lake reads 29-32 m), pits
to -55 m in it, and a 120-145 m flat-topped block with near-vertical
walls over the low shore beside it -- the base DEM (Copernicus 1")
reads 31-35 m there.  The bake laid all of it into the mesh: water
triangles at up to 155 m, the "mounds in the lake" and the "block with
a river running down its face" of the owner's read.

THE RULE.  On an inset whose provider declares itself a SURFACE MODEL
(the provider definition runs the building-mask pass), a valid pixel is
REFUSED (becomes nodata for the bake, so the base DEM models it, as it
models everything beyond the inset) when

1. it lies inside the tile's mapped INLAND WATER -- WATER IS A DATUM
   (owner RULINGS 2026-09-09m): a stereo model has no texture to match
   there, and the base DEM's water is hydro-edited flat; or
2. it belongs to a BLUNDER: a connected region (8-connected) of pixels
   standing more than ``GROW_M`` outside the base DEM's local envelope
   (its min..max within ``ENVELOPE_RADIUS_M``) that contains at least
   one pixel more than ``BLUNDER_M`` outside it.  The envelope makes a
   real cliff safe (the base's own posts within the radius span it);
   ``BLUNDER_M`` is beyond any tree or unmasked building a surface model
   carries; the region growth takes the blunder's walls with its core,
   so no rim of half-height spikes is left standing.

Every other inset (lidar, bare-earth models) is never judged and bakes
byte for byte.  The rule reads the raster, the base and the cached water
layer only, so it is the same on every build and writes no file.
"""
from __future__ import annotations

import numpy

__all__ = [
    "BLUNDER_M",
    "ENVELOPE_RADIUS_M",
    "GROW_M",
    "blunder_cells",
    "refuse_surface_model_cells",
]

#: Radius (metres) of the base DEM's local min..max envelope.
ENVELOPE_RADIUS_M = 90.0
#: A blunder's core stands this far (metres) outside the envelope.
BLUNDER_M = 50.0
#: A blunder region grows through pixels this far outside the envelope.
GROW_M = 5.0


def _grow_from_cores(region, cores):
    """The 8-connected components of ``region`` holding a ``cores`` pixel."""
    if not cores.any():
        return numpy.zeros_like(region)
    from scipy import ndimage

    labels, _count = ndimage.label(region, structure=numpy.ones((3, 3)))
    hit = numpy.unique(labels[cores & region])
    return numpy.isin(labels, hit[hit > 0])


def blunder_cells(values, valid, low, high,
                  blunder_m=BLUNDER_M, grow_m=GROW_M):
    """The valid pixels of ``values`` in a blunder region (THE RULE (2)),
    against the base envelope ``low``..``high`` at the same posts (NaN
    where the base cannot judge)."""
    values = numpy.asarray(values, dtype=float)
    judged = valid & numpy.isfinite(low) & numpy.isfinite(high)
    with numpy.errstate(invalid="ignore"):
        above = judged & (values > high + grow_m)
        below = judged & (values < low - grow_m)
        high_cores = judged & (values > high + blunder_m)
        low_cores = judged & (values < low - blunder_m)
    return (_grow_from_cores(above, high_cores)
            | _grow_from_cores(below, low_cores))


def _post_coordinates(inset):
    """Tile-relative ``(x, y)`` of the inset's post columns and rows."""
    rows, columns = inset.alt_dem.shape
    x = inset.x0 + numpy.arange(columns) * (
        (inset.x1 - inset.x0) / max(columns - 1, 1))
    y = inset.y1 - numpy.arange(rows) * (
        (inset.y1 - inset.y0) / max(rows - 1, 1))
    return x, y


def _base_envelope(inset, base_dem, metres_per_degree):
    """``(low, high)`` at every inset post: the base working grid's min
    and max within ``ENVELOPE_RADIUS_M`` (NaN where the base holds only
    nodata there)."""
    from scipy import ndimage

    x, y = _post_coordinates(inset)
    x_step = (base_dem.x1 - base_dem.x0) / (base_dem.nxdem - 1)
    y_step = (base_dem.y1 - base_dem.y0) / (base_dem.nydem - 1)
    reach_x = max(int(numpy.ceil(
        ENVELOPE_RADIUS_M / (x_step * metres_per_degree[0]))), 1)
    reach_y = max(int(numpy.ceil(
        ENVELOPE_RADIUS_M / (y_step * metres_per_degree[1]))), 1)
    columns = numpy.clip(numpy.rint((x - base_dem.x0) / x_step),
                         0, base_dem.nxdem - 1).astype(int)
    rows = numpy.clip(numpy.rint((base_dem.y1 - y) / y_step),
                      0, base_dem.nydem - 1).astype(int)
    c0 = max(int(columns.min()) - reach_x, 0)
    c1 = min(int(columns.max()) + reach_x, base_dem.nxdem - 1)
    r0 = max(int(rows.min()) - reach_y, 0)
    r1 = min(int(rows.max()) + reach_y, base_dem.nydem - 1)
    window = numpy.asarray(base_dem.alt_dem[r0:r1 + 1, c0:c1 + 1],
                           dtype=float)
    missing = ~numpy.isfinite(window) | (window == base_dem.nodata)
    size = (2 * reach_y + 1, 2 * reach_x + 1)
    high = ndimage.maximum_filter(numpy.where(missing, -numpy.inf, window),
                                  size=size, mode="nearest")
    low = ndimage.minimum_filter(numpy.where(missing, numpy.inf, window),
                                 size=size, mode="nearest")
    index = numpy.ix_(rows - r0, columns - c0)
    (low, high) = (low[index], high[index])
    unjudged = ~numpy.isfinite(low) | ~numpy.isfinite(high)
    low[unjudged] = numpy.nan
    high[unjudged] = numpy.nan
    return low, high


def _water_posts(inset, water):
    """Inset posts inside ``water`` (tile-relative geometry or None)."""
    shape = inset.alt_dem.shape
    if water is None or water.is_empty:
        return numpy.zeros(shape, dtype=bool)
    import shapely
    from shapely.geometry import box

    x, y = _post_coordinates(inset)
    # padded by a post: a post ON the clip box's edge is not "contained"
    pad = max(abs(float(x[-1] - x[0])) / max(len(x) - 1, 1),
              abs(float(y[0] - y[-1])) / max(len(y) - 1, 1))
    local = water.intersection(box(float(x.min()) - pad, float(y.min()) - pad,
                                   float(x.max()) + pad, float(y.max()) + pad))
    if local.is_empty:
        return numpy.zeros(shape, dtype=bool)
    (west, south, east, north) = local.bounds
    columns = numpy.flatnonzero((x >= west) & (x <= east))
    rows = numpy.flatnonzero((y >= south) & (y <= north))
    inside = numpy.zeros(shape, dtype=bool)
    if len(columns) == 0 or len(rows) == 0:
        return inside
    shapely.prepare(local)
    grid_x, grid_y = numpy.meshgrid(x[columns], y[rows])
    inside[numpy.ix_(rows, columns)] = shapely.contains_xy(
        local, grid_x, grid_y)
    return inside


def refuse_surface_model_cells(inset, base_dem, water, metres_per_degree):
    """Apply THE RULE to the decoded surface-model ``inset`` in place (its
    refused pixels become ``inset.nodata``) and return the record
    ``{"water", "blunder", "blunder_max_m"}``, or ``None`` when nothing
    was refused.  ``water`` is the tile's inland water (tile-relative,
    or None); ``metres_per_degree`` is ``(east, north)``.  Idempotent: an
    inset already judged returns its first record (the bake may run
    twice on one decoded raster)."""
    if hasattr(inset, "surface_refusal"):
        return inset.surface_refusal
    inset.surface_refusal = None
    values = getattr(inset, "alt_dem", None)
    if values is None:
        return None
    valid = numpy.isfinite(values) & (values != inset.nodata)
    in_water = valid & _water_posts(inset, water)
    low, high = _base_envelope(inset, base_dem, metres_per_degree)
    blunder = blunder_cells(values, valid & ~in_water, low, high)
    if not (in_water.any() or blunder.any()):
        return None
    excess = numpy.where(blunder, numpy.maximum(values - high, low - values),
                         0.0)
    values[in_water | blunder] = inset.nodata
    inset.surface_refusal = {
        "water": int(in_water.sum()),
        "blunder": int(blunder.sum()),
        "blunder_max_m": round(float(numpy.nanmax(excess)), 2),
    }
    return inset.surface_refusal
