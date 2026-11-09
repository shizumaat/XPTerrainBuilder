"""The inland shore feather ramp, capped by the water's local width.

RULINGS 2026-11-09a (12): lakes and rivers feather at most 25 % of the
way from shore to shore, so roughly half of every water body keeps the
plain ``ratio_water`` look.  The cap is LOCAL: a 40 m river gets a
~10 m feather on each bank while a wide lake keeps the full
``inland_shore_feather_m`` (still the upper bound).

The ramp is a function of the distance to land, ``(1 - s / extent)**2``
with ``s`` the distance from the shoreline — the profile the former
triangular blur of the land indicator gave on a straight shore — and
``extent = min(feather, 0.25 * local width)``.  The local width comes
from the local half-width ``H`` (the radius of the largest disk inside
the water that covers the pixel; width ``2 H - 1`` in pixels), computed
only up to the value where the cap stops binding.
"""

from __future__ import annotations

import numpy
from scipy import ndimage

#: The share of the local shore-to-shore width one shore may feather.
WIDTH_FRACTION = 0.25

#: Block size of the coarse grid the half-width search runs on.  It
#: only widens the search window (by < one block); an isolated river's
#: half-width is exact at any block size.
_BLOCK = 4


def shore_ramp(land_full, crop_margin, feather_pixels,
               width_fraction=WIDTH_FRACTION):
    """The shore feather strength (0..254, ``uint16``) over the cropped
    window ``[crop_margin:-crop_margin]`` of ``land_full``.

    254 at the shoreline easing to 0 at ``extent`` pixels from it;
    ``extent`` is ``feather_pixels`` capped at ``width_fraction`` of the
    local water width.  Only the values over water are meaningful.
    """
    (rows, cols) = land_full.shape
    reach = min(crop_margin, 4 * int(feather_pixels) + 2 * _BLOCK)
    lo = crop_margin - reach
    region = land_full[lo:rows - lo, lo:cols - lo]
    inner = (slice(reach, region.shape[0] - reach),
             slice(reach, region.shape[1] - reach))
    if not region.any():
        return numpy.zeros(
            (rows - 2 * crop_margin, cols - 2 * crop_margin), numpy.uint16)
    depth = ndimage.distance_transform_edt(~region).astype(numpy.float32)
    limit = 2 * int(feather_pixels) + 1
    half_width = local_half_width(depth, limit)[inner]
    depth = depth[inner]
    extent = numpy.minimum(
        numpy.float32(feather_pixels),
        numpy.float32(width_fraction) * (2 * half_width - 1))
    with numpy.errstate(divide="ignore", invalid="ignore"):
        ramp = 1 - (depth - 0.5) / extent
    ramp = numpy.where(extent > 0, numpy.clip(ramp, 0, 1), 0)
    return (254 * ramp * ramp).astype(numpy.uint16)


def local_half_width(depth, limit):
    """Per pixel, the largest ``t <= limit`` such that a pixel with
    ``depth >= t`` lies within chessboard distance ``t`` — the half-width
    of the water around it (``depth``: distance to land in pixels).

    Values at or above ``limit`` read as ``limit``.  Run on a coarse
    grid of ``_BLOCK`` blocks (block maximum of the depth), so the search
    window may reach up to one block further than ``t``.
    """
    clamped = numpy.minimum(numpy.floor(depth), limit).astype(numpy.uint16)
    (rows, cols) = clamped.shape
    pad = ((0, -rows % _BLOCK), (0, -cols % _BLOCK))
    padded = numpy.pad(clamped, pad)
    blocks = padded.reshape(
        padded.shape[0] // _BLOCK, _BLOCK,
        padded.shape[1] // _BLOCK, _BLOCK).max(axis=(1, 3))
    half = numpy.zeros_like(blocks)
    window_max = blocks
    for radius in range(1, -(-limit // _BLOCK) + 1):
        window_max = ndimage.maximum_filter(window_max, size=3)
        reached = window_max > _BLOCK * (radius - 1)
        candidate = numpy.minimum(window_max, _BLOCK * radius)
        half = numpy.where(reached, numpy.maximum(half, candidate), half)
    half = numpy.repeat(numpy.repeat(half, _BLOCK, axis=0), _BLOCK, axis=1)
    return half[:rows, :cols].astype(numpy.float32)
