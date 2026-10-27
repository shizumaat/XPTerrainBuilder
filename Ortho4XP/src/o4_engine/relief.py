"""The terrain view's raster (issue #1320, owner Q134: hillshade plus
contours): an elevation grid in, an RGBA picture out.

Pure numpy, no I/O; ``relief_commands`` samples the grid and serves the
PNG.  Grid layout: row 0 at the NORTH edge (the picture's top), column 0
at the WEST edge; NaN where no source covers the point (transparent).

Hillshade is the standard Lambertian one: the sun at ``azimuth`` degrees
clockwise from north (315: north-west) and ``altitude`` degrees above the
horizon, shade = surface normal · sun, clipped to [0, 1].  Contours sit
on the multiples of ``step`` metres: a pixel is on a contour when the
step band it is in differs from its east or south neighbour's.  Every
fifth level (an index contour) is drawn brighter.
"""
from __future__ import annotations

import io
import math
from typing import NamedTuple

import numpy as np

__all__ = ["Relief", "contour_step", "hillshade", "png_bytes", "relief_rgba"]

#: Minor and index contour colours (RGB): warm, so they read over the
#: grey hillshade and over imagery.
CONTOUR_RGB = (214, 120, 30)
INDEX_RGB = (255, 196, 64)
#: Every this-many levels is an index contour.
INDEX_EVERY = 5
#: More contour levels than this in one picture and the default step
#: coarsens (1, 2, 5, 10, ... m): the lines would merge into a fill.
MAX_LEVELS = 150


class Relief(NamedTuple):
    rgba: np.ndarray            # (rows, cols, 4) uint8
    levels: frozenset           # the contour levels drawn, in metres
    min_m: float | None         # the grid's finite range
    max_m: float | None


def hillshade(z: np.ndarray, dx_m: float, dy_m: float,
              azimuth: float = 315.0, altitude: float = 45.0) -> np.ndarray:
    """Shade in [0, 1] per pixel (NaN where ``z`` or a neighbour is NaN);
    ``dx_m`` / ``dy_m`` are the pixel's east / south extent in metres."""
    z = np.asarray(z, dtype=np.float64)
    if min(z.shape) < 2:
        return np.where(np.isfinite(z), math.sin(math.radians(altitude)), np.nan)
    d_south, d_east = np.gradient(z, dy_m, dx_m)
    d_north = -d_south
    az, alt = math.radians(azimuth), math.radians(altitude)
    sun_e, sun_n, sun_up = (math.cos(alt) * math.sin(az), math.cos(alt) * math.cos(az),
                            math.sin(alt))
    # normal (-dz/de, -dz/dn, 1), normalised
    shade = (-d_east * sun_e - d_north * sun_n + sun_up) / np.sqrt(1.0 + d_east ** 2 + d_north ** 2)
    return np.clip(shade, 0.0, 1.0)


def contour_step(pixel_m: float, z_min: float | None, z_max: float | None) -> float:
    """The default contour interval: 1 m, 0.5 m when a pixel is under
    0.25 m, coarsened through 1-2-5 steps while the relief would draw
    more than :data:`MAX_LEVELS` lines."""
    step = 0.5 if pixel_m < 0.25 else 1.0
    if z_min is None or z_max is None:
        return step
    while (z_max - z_min) / step > MAX_LEVELS:
        step = _next(step)
    return step


def _next(step: float) -> float:
    """The next step of the 0.5, 1, 2, 5, 10, 20, 50 ... ladder."""
    exponent = math.floor(math.log10(step))
    mantissa = round(step / 10 ** exponent)
    return float({1: 2, 2: 5, 5: 10}[mantissa] * 10.0 ** exponent)


def relief_rgba(z: np.ndarray, dx_m: float, dy_m: float, step: float) -> Relief:
    """The hillshade with ``step``-metre contours over it."""
    z = np.asarray(z, dtype=np.float64)
    finite = np.isfinite(z)
    shade = hillshade(z, dx_m, dy_m)
    grey = np.where(np.isfinite(shade), shade, 0.0) * 255.0
    rgba = np.zeros(z.shape + (4,), dtype=np.uint8)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = np.round(grey).astype(np.uint8)
    rgba[..., 3] = np.where(finite, 255, 0)

    band = np.where(finite, np.floor(np.where(finite, z, 0.0) / step), np.nan)
    top = np.full(z.shape, np.nan)          # the level a contour pixel draws
    for a, b in (((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
                 ((slice(None, -1), slice(None)), (slice(1, None), slice(None)))):
        here, there = band[a], band[b]
        cross = np.isfinite(here) & np.isfinite(there) & (here != there)
        level = np.maximum(here, there)
        top[a] = np.where(cross, np.fmax(top[a], level), top[a])
    on = np.isfinite(top)
    index = on & (np.mod(top, INDEX_EVERY) == 0)
    rgba[on & ~index, :3] = CONTOUR_RGB
    rgba[index, :3] = INDEX_RGB
    levels = frozenset(float(v) * step for v in np.unique(top[on]))
    if finite.any():
        lo, hi = float(np.nanmin(z)), float(np.nanmax(z))
    else:
        lo = hi = None
    return Relief(rgba, levels, lo, hi)


def png_bytes(rgba: np.ndarray) -> bytes:
    """``rgba`` as PNG file bytes."""
    from PIL import Image
    out = io.BytesIO()
    Image.fromarray(np.ascontiguousarray(rgba), "RGBA").save(out, format="PNG", compress_level=3)
    return out.getvalue()
