"""Provider fill: masking the constant a server serves beyond its data (#1340).

A national coverage service asked for a box that runs past its survey
extent can answer the missing part with a constant FILL -- most often
exactly ``0.0`` -- instead of nodata.  The whole-raster case is the
flat-fill rule (:func:`elevation_access.warp.inset_carries_no_relief`,
#1171).  This module is the PARTIAL case: real terrain over part of the
box and the fill over the rest (YMML from AUSTRALIA5M: 62.7 % of the
pixels exactly 0.0, real ground at 84-138 m beside them, so the airport
was baked into a 0 m pit with ~110 m cliffs).

THE RULE.  A region is the provider's fill, and becomes nodata, when ALL
of these hold:

1. it is ONE 8-connected region of pixels holding EXACTLY one value
   (zero variance) -- ``0.0`` or a value the provider declares as its
   fill (``provider_fill_value=`` in its ``.elv``, ``;``-separated);
2. it is LARGE: at least ``PROVIDER_FILL_MIN_REGION_FRAC`` of the
   raster's pixels;
3. it touches the delivered box EDGE or covers the box CENTRE (the
   airport the box was cut around);
4. it is not the whole raster -- a raster that is one value everywhere is
   the flat-fill rule's, never this one's;
5. the value is DECLARED as the provider's fill, or the ground bordering
   the region stands at least ``PROVIDER_FILL_STEP_M`` away from it (the
   median of a ring ``PROVIDER_FILL_SMEAR_PX`` .. ``+WITNESS_PX`` pixels
   out).  That border step is the airport-far-above-the-fill test read
   from the raster itself, so a cached file can be re-judged without an
   airport record.

WHY COASTAL 0 m TERRAIN SURVIVES.  Genuine lidar sea is often exact 0.0
over a large, edge-connected region -- conditions 1-4 hold for it.  But
its shore rises out of the sea: the ground bordering it sits within a
few metres of 0, so condition 5 fails unless the provider has declared 0
as its fill (a provider that serves 0 for "no survey" everywhere, which
loses nothing over water: the base DEM models the sea there).  A
hydro-flattened lake is constant at its surface height, which is neither
0 nor a declared fill.  The known residue: a fill bordered by ground
within ``PROVIDER_FILL_STEP_M`` of it (a survey edge on a low coast) is
not caught unless the provider declares its fill.

A masked pixel is rewritten as the raster's nodata (``-32768`` when it
declares none) so EVERY reader -- the valid-fraction rule, the bake, the
flat-site and smoothing coverage, the probes -- sees the masked raster;
there is no second reader to keep in step.  ``PROVIDER_FILL_SMEAR_PX``
pixels of the rim go with the region: the warp's bilinear resampling
smears the fill into the first pixels of real ground.
"""

import os

import numpy

from elevation_access.gdal_support import gdal, has_gdal

__all__ = [
    "PROVIDER_FILL_DECLARATION_KEY",
    "PROVIDER_FILL_MIN_REGION_FRAC",
    "PROVIDER_FILL_STEP_M",
    "declared_provider_fills",
    "mask_provider_fill",
    "provider_fill_region",
]

#: The ``.elv`` key a provider declares its fill value(s) with.
PROVIDER_FILL_DECLARATION_KEY = "provider_fill_value"

#: Condition 2: the region's share of the raster's pixels.
PROVIDER_FILL_MIN_REGION_FRAC = 0.01

#: Condition 5: the border step (metres) that marks an undeclared fill.
PROVIDER_FILL_STEP_M = 20.0

#: Pixels of the region's rim taken with it (resampling smear).
PROVIDER_FILL_SMEAR_PX = 3

#: Width (pixels) of the witness ring read beyond the smear.
PROVIDER_FILL_WITNESS_PX = 3

#: Nodata written into a raster that declares none.
PROVIDER_FILL_NODATA = -32768.0

_EIGHT = numpy.ones((3, 3), dtype=bool)


def declared_provider_fills(definition):
    """The fill values ``definition`` declares (``provider_fill_value=``),
    as a tuple of floats; ``()`` when it declares none."""
    raw = str((definition or {}).get(PROVIDER_FILL_DECLARATION_KEY) or "")
    fills = []
    for token in raw.split(";"):
        try:
            fills.append(float(token.strip()))
        except ValueError:
            continue
    return tuple(fills)


def _grow(mask, pixels):
    """``mask`` dilated by ``pixels`` in all 8 directions."""
    from scipy import ndimage

    if pixels <= 0:
        return mask
    return ndimage.binary_dilation(mask, structure=_EIGHT,
                                   iterations=pixels)


def _candidate_regions(values, valid, fill_value, min_cells):
    """The 8-connected regions of ``valid`` pixels equal to ``fill_value``
    that are large (condition 2) and touch the edge or the centre
    (condition 3), as boolean masks."""
    from scipy import ndimage

    equal = valid & (values == fill_value)
    if int(equal.sum()) < min_cells:
        return []
    (labels, count) = ndimage.label(equal, structure=_EIGHT)
    if count == 0:
        return []
    sizes = numpy.bincount(labels.ravel())
    anchored = set(numpy.unique(numpy.concatenate((
        labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))).tolist())
    (height, width) = values.shape
    anchored.add(int(labels[height // 2, width // 2]))
    anchored.discard(0)
    return [labels == label for label in sorted(anchored)
            if sizes[label] >= min_cells]


def _border_step_m(values, valid, region, fill_value):
    """Condition 5's witness: |median of the ring beyond the smear - fill|,
    or ``None`` when no valid pixel borders the region there."""
    inner = _grow(region, PROVIDER_FILL_SMEAR_PX)
    outer = _grow(inner, PROVIDER_FILL_WITNESS_PX)
    ring = outer & ~inner & valid & (values != fill_value)
    if not ring.any():
        return None
    return abs(float(numpy.median(values[ring])) - float(fill_value))


def provider_fill_region(values, valid, declared_fills=()):
    """The pixels of ``values`` that are a provider's fill (the module
    rule), as ``(mask, fill_value)``; ``(None, None)`` when none is.

    ``valid`` is the boolean mask of pixels holding data.  ``mask`` covers
    the qualifying regions plus their ``PROVIDER_FILL_SMEAR_PX`` rim,
    restricted to valid pixels."""
    total_valid = int(valid.sum())
    if total_valid == 0:
        return (None, None)
    min_cells = max(1, int(PROVIDER_FILL_MIN_REGION_FRAC * values.size))
    declared = {float(value) for value in declared_fills}
    mask = numpy.zeros(values.shape, dtype=bool)
    found = None
    for fill_value in sorted({0.0} | declared):
        for region in _candidate_regions(values, valid, fill_value,
                                         min_cells):
            if int(region.sum()) >= total_valid:
                continue                    # condition 4: flat-fill rule's
            if fill_value not in declared:
                step = _border_step_m(values, valid, region, fill_value)
                if step is None or step < PROVIDER_FILL_STEP_M:
                    continue
            mask |= _grow(region, PROVIDER_FILL_SMEAR_PX) & valid
            found = fill_value if found is None else found
    if found is None:
        return (None, None)
    return (mask, found)


def mask_provider_fill(raster_path, declared_fills=(), before_write=None):
    """Rewrite the provider fill in ``raster_path`` as nodata, in place.

    Returns the record of what was masked -- ``{"fill_value",
    "masked_fraction", "valid_fraction"}`` (fractions of the raster's
    pixels; ``valid_fraction`` is the TRUE coverage after the mask) -- or
    ``None`` when the raster holds no fill (or cannot be read).
    Idempotent: a masked raster holds no fill, so a second call is a
    read and ``None``.  ``before_write(raster_path)`` is called only when
    the raster IS rewritten (the caller's write declaration)."""
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
    valid = numpy.isfinite(values)
    if nodata is not None:
        valid &= values != nodata
    try:
        (mask, fill_value) = provider_fill_region(values, valid,
                                                  declared_fills)
    except ImportError:                                  # pragma: no cover
        return None
    if mask is None:
        return None
    if before_write is not None:
        before_write(raster_path)
    nodata = PROVIDER_FILL_NODATA if nodata is None else nodata
    values = values.astype(numpy.float32)
    values[mask] = nodata
    scratch = _write_masked_copy(dataset, raster_path, values, nodata)
    band = None
    dataset = None           # release the source before the swap (Windows)
    os.replace(scratch, raster_path)
    remaining = valid & ~mask
    return {
        "fill_value": float(fill_value),
        "masked_fraction": round(float(mask.mean()), 6),
        "valid_fraction": round(float(remaining.mean()), 6),
    }


def _write_masked_copy(dataset, raster_path, values, nodata):
    """Write a copy of ``dataset`` carrying ``values`` and ``nodata`` beside
    ``raster_path`` and return its path -- metadata, georeferencing and the
    vertical-unit stamp kept.  The caller closes ``dataset`` and swaps the
    copy in, so a reader never sees half a file (and Windows, which refuses
    to replace a file with an open handle, can make the swap)."""
    memory = gdal.GetDriverByName("MEM").CreateCopy("", dataset)
    band = memory.GetRasterBand(1)
    band.SetNoDataValue(float(nodata))
    band.WriteArray(values)
    scratch = raster_path + ".fillmask.tif"
    written = gdal.GetDriverByName("GTiff").CreateCopy(
        scratch, memory,
        options=["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"])
    del written                      # close the GTiff handle before the swap
    memory = None
    return scratch
