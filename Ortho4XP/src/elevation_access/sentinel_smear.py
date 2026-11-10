"""Sentinel smear: the rim a leaked fill value leaves behind a warp (#1956).

A server that fills "no data" with a sentinel it does not DECLARE
(TINITALY's WCS answers the sea with -9999 and advertises no nodata; the
Hamburg 1 m model does the same over the Elbe) hands the warp a raster
whose fill is, to GDAL, ordinary elevation.  The bilinear warp then
blends it into the first pixel of real ground: a pixel that took a
fraction ``w`` of its kernel from the fill comes out at
``(1 - w) * ground + w * fill``.  The warp's sentinel sanitizer
(:func:`elevation_access.warp.warp_vsicurl_sources_to_geotiff`) turns
everything below the provider's ``value_floor_m`` into nodata -- the fill
itself and the heavily blended pixels -- but the lightly blended ones
(``w`` under ~6 % for a -9999 fill and the -600 m floor) survive as
"valid" ground anywhere between the true height and -600 m.  Along a
coast that is a one-pixel band of pits: LICJ and LICC were baked with
pits to -480 m in the beach and shoreline strip.

THE RULE.  A raster carries a sentinel smear when at least
``SMEAR_MIN_CELLS`` of its RIM pixels (valid pixels touching nodata,
8-connected) are below sea level AND stand more than ``SMEAR_STEP_M``
below the lowest valid non-rim pixel beside them.  No ground does that
in one pixel at a coast; a resampled sentinel does it on every rim it
touched (LICJ: 84 such pixels; clean lidar and Copernicus insets across
the corpus: none -- the deepest natural rim step, ArcticDEM sea-surface
noise, is under 30 m).  The smear is then the whole rim: the fill is
one value over the whole raster, so every rim it touched is suspect,
including the lightly blended pixels that are still above sea level.
The rim becomes nodata, ring by ring, until the raster no longer
carries the evidence (``SMEAR_MAX_RINGS`` at most; one ring when the
warp did not upsample) -- and the next layer (the base DEM, the coarser
ring) models those pixels, exactly as it models the sea beyond them.

Runs where the provider-fill mask runs
(:func:`O4_Airport_Elevation_Insets.mask_fetched_provider_fill`): every
fetch, and every CACHED inset, ring and overlay cell when it is reused,
so a raster cached before the rule heals on its next build.  A cleaned
raster carries no evidence, so the rule is idempotent.  Bathymetry is
never judged (its negative values are the sea floor).
"""

import os

import numpy

from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.provider_fill import (
    PROVIDER_FILL_NODATA,
    _write_masked_copy,
)

__all__ = [
    "SMEAR_MAX_RINGS",
    "SMEAR_MIN_CELLS",
    "SMEAR_STEP_M",
    "mask_sentinel_smear",
]

#: Metres a rim pixel must stand below the ground beside it to witness.
SMEAR_STEP_M = 100.0

#: Witnessing rim pixels needed before the raster is judged smeared.
SMEAR_MIN_CELLS = 3

#: Rim rings removed at most (an upsampling warp smears wider than one).
SMEAR_MAX_RINGS = 3

_EIGHT = numpy.ones((3, 3), dtype=bool)


def _rim(valid):
    """Valid pixels with a nodata pixel among their 8 neighbours."""
    from scipy import ndimage

    return valid & ndimage.binary_dilation(~valid, structure=_EIGHT)


def _witness_count(values, valid):
    """Rim pixels below sea level and ``SMEAR_STEP_M`` below the lowest
    valid non-rim pixel in their 3 x 3 neighbourhood."""
    from scipy import ndimage

    rim = _rim(valid)
    candidates = rim & (values < 0.0)
    if not candidates.any():
        return 0
    inner = valid & ~rim
    beside = ndimage.minimum_filter(
        numpy.where(inner, values, numpy.inf), size=3,
        mode="constant", cval=numpy.inf)
    witnesses = candidates & numpy.isfinite(beside) & (
        beside - values > SMEAR_STEP_M)
    return int(witnesses.sum())


def _sentinel_smear_region(values, valid):
    """The smeared rim of ``values`` (the module rule) as a boolean mask,
    or ``None`` when the raster carries no smear.  ``valid`` is the mask
    of pixels holding data."""
    if not (valid & (values < 0.0)).any():
        return None                       # no pixel below sea level: clean
    if _witness_count(values, valid) < SMEAR_MIN_CELLS:
        return None
    mask = numpy.zeros(values.shape, dtype=bool)
    remaining = valid.copy()
    for _ring in range(SMEAR_MAX_RINGS):
        rim = _rim(remaining)
        mask |= rim
        remaining &= ~rim
        if _witness_count(values, remaining) < SMEAR_MIN_CELLS:
            break
    return mask


def mask_sentinel_smear(raster_path, before_write=None):
    """Rewrite the sentinel smear in ``raster_path`` as nodata, in place.

    Returns ``{"masked_pixels", "masked_fraction", "deepest_m"}`` (the
    deepest masked value, the pit the smear would have baked) or ``None``
    when the raster carries no smear or cannot be read.  Idempotent.
    ``before_write(raster_path)`` is called only when the raster IS
    rewritten (the caller's write declaration)."""
    if not has_gdal or not os.path.isfile(raster_path):
        return None
    try:
        dataset = gdal.Open(raster_path)
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        values = band.ReadAsArray()
    except Exception:
        return None
    if values is None or values.size == 0:
        return None
    values = values.astype(numpy.float32)
    valid = numpy.isfinite(values)
    if nodata is not None:
        valid &= values != nodata
    try:
        mask = _sentinel_smear_region(values, valid)
    except ImportError:                                  # pragma: no cover
        return None
    if mask is None or not mask.any():
        return None
    if before_write is not None:
        before_write(raster_path)
    record = {
        "masked_pixels": int(mask.sum()),
        "masked_fraction": round(float(mask.mean()), 6),
        "deepest_m": round(float(values[mask].min()), 2),
    }
    nodata = PROVIDER_FILL_NODATA if nodata is None else nodata
    values[mask] = nodata
    scratch = _write_masked_copy(dataset, raster_path, values, nodata)
    band = None
    dataset = None           # release the source before the swap (Windows)
    os.replace(scratch, raster_path)
    return record
