"""The map's tile-state band: the ONE drawing rule both apps use for a
tile's colour on the map (owner 2026-11-12T22:01Z; Mac: SceneryKit
``TileBand``, same numbers — ``tests/test_tile_band.py`` twins them).

A tile's colour is a band INSIDE its own edge: inset a little from the
edge so a neighbour's band never overlaps it, a few points wide (wider as
the tile grows on screen, within a min and max), full colour at its outer
side fading to transparent toward the tile's centre.  A dashed or dotted
key keeps its dash as a line along the band's outer side, over a fainter
band.  A tile too small on screen for a gradient gets a plain inset line;
a tiny one a 1 pt line inside its edge.  Every length is in screen points
(pixels); a caller painting in scene units scales by its own unit.

Pure geometry, no Qt: ``O4_Qt_Tile_Band`` paints it.
"""
from __future__ import annotations

from typing import NamedTuple

__all__ = ["INSET_PT", "WIDTH_MIN_PT", "WIDTH_MAX_PT", "WIDTH_FRACTION",
           "GRADIENT_MIN_PX", "LINE_MIN_PX", "LINE_WIDTH_PT", "TINY_LINE_PT",
           "OUTER_ALPHA", "DASHED_OUTER_ALPHA", "DASH_LINE_PT", "INNER_GAP_PT",
           "BAND", "LINE", "Band", "band_for", "trapezoids", "inner_inset"]

#: The gap between the tile's edge and its band, so neighbours never meet.
INSET_PT = 1.5
#: The band's width: WIDTH_FRACTION of the tile's on-screen size, clamped.
WIDTH_MIN_PT = 4.0
WIDTH_MAX_PT = 8.0
WIDTH_FRACTION = 0.06
#: The gradient band from this tile size up; a plain inset line below.
GRADIENT_MIN_PX = 40.0
#: Below this tile size the line is TINY_LINE_PT at the tile's edge.
LINE_MIN_PX = 10.0
LINE_WIDTH_PT = 2.0
TINY_LINE_PT = 1.0
#: The band's opacity at its outer side (it fades to 0 inward); a dashed
#: key's band is fainter so its dash line reads over it.
OUTER_ALPHA = 0.95
DASHED_OUTER_ALPHA = 0.45
#: A dashed key's dash line, along the band's outer side.
DASH_LINE_PT = 2.0
#: An installed tile's inner line sits this far inside the band.
INNER_GAP_PT = 2.0

BAND = "band"
LINE = "line"


class Band(NamedTuple):
    """How a tile ``px`` points wide draws: ``mode`` BAND (gradient) or
    LINE (a stroke of ``width`` centred ``inset + width / 2`` inside)."""
    mode: str
    inset: float
    width: float


def band_for(px: float) -> Band:
    """The band of a tile ``px`` points wide on screen."""
    if px >= GRADIENT_MIN_PX:
        width = min(max(px * WIDTH_FRACTION, WIDTH_MIN_PT), WIDTH_MAX_PT)
        return Band(BAND, INSET_PT, width)
    if px >= LINE_MIN_PX:
        return Band(LINE, INSET_PT, LINE_WIDTH_PT)
    return Band(LINE, 0.0, TINY_LINE_PT)


def trapezoids(left, top, right, bottom, inset, width):
    """The band's four sides of the rect, mitred at the corners: each
    ``(polygon, outer_point, inner_point)`` — the gradient runs from full
    colour at ``outer_point`` to transparent at ``inner_point``.  Units are
    the rect's; ``inset`` and ``width`` already in them."""
    ox0, oy0, ox1, oy1 = left + inset, top + inset, right - inset, bottom - inset
    ix0, iy0, ix1, iy1 = ox0 + width, oy0 + width, ox1 - width, oy1 - width
    mx, my = (left + right) / 2, (top + bottom) / 2
    return [
        (((ox0, oy0), (ox1, oy0), (ix1, iy0), (ix0, iy0)), (mx, oy0), (mx, iy0)),
        (((ox1, oy0), (ox1, oy1), (ix1, iy1), (ix1, iy0)), (ox1, my), (ix1, my)),
        (((ox1, oy1), (ox0, oy1), (ix0, iy1), (ix1, iy1)), (mx, oy1), (mx, iy1)),
        (((ox0, oy1), (ox0, oy0), (ix0, iy0), (ix0, iy1)), (ox0, my), (ix0, my)),
    ]


def inner_inset(px: float) -> float:
    """An installed tile's inner line: its inset in points, inside the
    band (3 % of the tile when there is no gradient band)."""
    band = band_for(px)
    if band.mode == BAND:
        return band.inset + band.width + INNER_GAP_PT
    return px * 0.03
