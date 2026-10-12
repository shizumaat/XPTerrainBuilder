"""The seam between a substituted base cell and its configured neighbours.

A base cell taken from a fallback source (``base_fallback``) is a
different measurement of the same ground: where the configured source is
bare earth and the fallback is a surface model, the two differ by the
canopy.  Measured 2026-10-12 on the row both N47W123 and N48W123 hold
(lat 48): Copernicus GLO-30 minus Viewfinderpanoramas is +7.6 m mean,
12.7 m RMS, 39 m at worst, where two Viewfinderpanoramas cells differ by
2.5 m RMS on that same row.  Untied, that is a step along the tile edge.

THE TIE: on each side whose neighbour is a cached configured cell, the
substituted cell's shared row or column is SET to the neighbour's posts,
and the difference fades linearly to nothing over
:data:`TIE_FEATHER_POSTS` posts into the substituted cell.  Sides are
applied in the fixed order of :data:`SIDES`, so every build that reads
the cell with the same neighbours cached gets the same array.

A CORNER post belongs to two sides, and two configured neighbours need
not agree on it (two Viewfinderpanoramas cells differ by up to 31 m on
a post they both hold).  The row tied first keeps it: a later side
leaves the end posts that lie on an already tied side alone, so every
tied row and column equals its neighbour post for post, the corner
posts of the west and east columns excepted.

Numbers only: this module reads no file and knows no provider.
"""

from typing import Callable, List, Optional

import numpy

__all__ = [
    "SIDES",
    "TIE_FEATHER_POSTS",
    "shared_edge_of_neighbour",
    "tie_cell_to_neighbours",
    "tie_side",
]

#: The four sides of a cell, in the order the tie applies them.
SIDES = ("north", "south", "west", "east")

#: Posts over which the edge difference fades into the substituted cell:
#: 240 posts of a 3601-post cell is 4 arc-minutes, about 7.4 km of
#: latitude.  The worst measured edge difference (39 m) then adds a
#: slope of about half a percent, well under the terrain's own.
TIE_FEATHER_POSTS = 240


def shared_edge_of_neighbour(neighbour, side):
    """The posts a neighbour shares with the cell on the cell's ``side``.

    Whole-degree post grids repeat their edge posts: the cell to the
    NORTH holds this cell's north row as its own bottom row, and so on.
    Row 0 is north, column 0 is west.
    """
    if side == "north":
        return neighbour[-1, :]
    if side == "south":
        return neighbour[0, :]
    if side == "west":
        return neighbour[:, -1]
    return neighbour[:, 0]


def tie_side(cell, side, edge, nodata=-32768, feather=TIE_FEATHER_POSTS,
             keep_ends=(False, False)):
    """Tie one side of ``cell`` (in place) to ``edge``; the largest
    absolute edge difference that was closed, in metres.

    A post that is void on either side of the seam is left alone, and no
    void post of the cell is ever given a height.  ``keep_ends`` names
    the first / last post of the side as already tied by another side.
    """
    if side in ("north", "south"):
        own = cell[0, :] if side == "north" else cell[-1, :]
        depth = cell.shape[0]
    else:
        own = cell[:, 0] if side == "west" else cell[:, -1]
        depth = cell.shape[1]
    edge = numpy.asarray(edge, dtype=numpy.float64)
    known = (own != nodata) & (edge != nodata) & numpy.isfinite(edge)
    difference = numpy.where(known, edge - own, 0.0)
    if keep_ends[0]:
        difference[0] = 0.0
    if keep_ends[1]:
        difference[-1] = 0.0
    reach = max(1, min(int(feather), depth))
    fade = 1.0 - numpy.arange(reach, dtype=numpy.float64) / float(reach)
    if side == "north":
        band = cell[:reach, :]
        correction = fade[:, None] * difference[None, :]
    elif side == "south":
        band = cell[-reach:, :]
        correction = fade[::-1, None] * difference[None, :]
    elif side == "west":
        band = cell[:, :reach]
        correction = difference[:, None] * fade[None, :]
    else:
        band = cell[:, -reach:]
        correction = difference[:, None] * fade[None, ::-1]
    band += numpy.where(band != nodata, correction, 0.0).astype(cell.dtype)
    return float(numpy.abs(difference).max()) if difference.size else 0.0


def tie_cell_to_neighbours(
    cell,
    neighbour_edge: Callable[[str], Optional[numpy.ndarray]],
    nodata=-32768,
    feather=TIE_FEATHER_POSTS,
) -> List[tuple]:
    """Tie ``cell`` (in place) on every side ``neighbour_edge`` answers.

    ``neighbour_edge(side)`` returns the configured neighbour's shared
    posts on that side, or ``None`` when there is nothing to tie to.
    Returns ``[(side, largest difference closed in metres), ...]`` for
    the sides that were tied.
    """
    tied = []
    for side in SIDES:
        edge = neighbour_edge(side)
        if edge is None:
            continue
        across = side in ("north", "south")
        if len(edge) != (cell.shape[1] if across else cell.shape[0]):
            continue
        done = [name for (name, _closed) in tied]
        keep_ends = ((False, False) if across
                     else ("north" in done, "south" in done))
        tied.append((side, tie_side(cell, side, edge, nodata, feather,
                                    keep_ends)))
    return tied
