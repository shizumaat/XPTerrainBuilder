"""WHERE A TILE'S PHOTO MEETS X-PLANE 12 WATER (RULINGS 2026-11-24f).

``water_imagery`` (tile setting):

* ``mask`` (the default until the owner's sim read): today's water.  A
  masked sea triangle is a plain ``terrain_Water`` triangle with a
  non-physical photo overlay on top, blended through the mask PNG
  (``BORDER_TEX``); inland water is an overlay on top too.
* ``under``: the photo is the sea floor, drawn UNDER the water.  A water
  triangle that gets the photo is ONE physical ``WATER_COLOR_MASK`` + ``WET``
  triangle whose vertices carry (fetch ratio, depth ratio, s, t) - no mask
  PNG, no ``BORDER_TEX``, no second ``terrain_Water`` triangle.  Sea
  triangles get it only where the depth-graded mask shows imagery
  (:func:`triangle_has_imagery`); deep water stays plain ``terrain_Water``.
  Every inland water triangle gets it.

``water_imagery_alpha`` (only read with ``under``): how X-Plane uses the
texture's alpha under the water is undocumented, so the owner compares
``opaque`` (DXT1, no alpha) with ``depth`` (DXT5 with the depth-graded mask
imprinted as alpha) in the sim.

``under`` needs X-Plane 12 water (``water_tech`` ``XP12``); with
``XP11 + bathy`` the tile keeps the mask form.
"""
from __future__ import annotations

from math import ceil, floor

__all__ = ["COARSE_MASK_CELLS", "coarse_mask", "draws_under", "imprints_alpha",
           "triangle_has_imagery"]


def draws_under(tile) -> bool:
    """True when ``tile`` draws its photo under the water (``under`` on
    X-Plane 12 water)."""
    return (getattr(tile, "water_imagery", "mask") == "under"
            and getattr(tile, "water_tech", "XP12") == "XP12")


def imprints_alpha(tile) -> bool:
    """True when the masked textures are DXT5 with the mask as alpha: the
    ``depth`` alpha under the water, else ``imprint_masks_to_dds``."""
    if draws_under(tile):
        return getattr(tile, "water_imagery_alpha", "opaque") == "depth"
    return bool(getattr(tile, "imprint_masks_to_dds", False))


def triangle_has_imagery(crop, st_points, floor_value) -> bool:
    """True when the mask ``crop`` (a 2-D uint8 array over one texture,
    255 land, 0 open water) rises above ``floor_value`` anywhere in the
    pixel box of the triangle whose texture coordinates are ``st_points``
    (``(s, t)`` per vertex, ``t`` up).  The box over-covers a slanted
    triangle by at most its own extent: the photo then reaches slightly
    past the mask's last visible pixel, never short of it."""
    rows, cols = crop.shape
    s_values = [s for (s, _t) in st_points]
    t_values = [t for (_s, t) in st_points]
    col0 = max(0, min(cols - 1, floor(min(s_values) * cols)))
    col1 = max(0, min(cols - 1, ceil(max(s_values) * cols)))
    row0 = max(0, min(rows - 1, floor((1 - max(t_values)) * rows)))
    row1 = max(0, min(rows - 1, ceil((1 - min(t_values)) * rows)))
    return bool(crop[row0:row1 + 1, col0:col1 + 1].max() > floor_value)


#: Cells per side of :func:`coarse_mask`: a 4096 px crop pools 16 x 16
#: pixels (about 40 m at zoom 16) into one cell.
COARSE_MASK_CELLS = 256


def coarse_mask(crop):
    """``crop`` (a 2-D uint8 array) max-pooled to at most
    :data:`COARSE_MASK_CELLS` cells per side, so a tile's every masked
    texture can stay in memory through the sea pass; a cell is above a
    floor when any of its pixels is, so :func:`triangle_has_imagery` on
    it never drops imagery the full crop shows."""
    rows, cols = crop.shape
    block = max(1, max(rows, cols) // COARSE_MASK_CELLS)
    if block == 1:
        return crop
    rows_cut, cols_cut = rows // block * block, cols // block * block
    pooled = crop[:rows_cut, :cols_cut].reshape(
        rows_cut // block, block, cols_cut // block, block)
    return pooled.max(axis=(1, 3))
