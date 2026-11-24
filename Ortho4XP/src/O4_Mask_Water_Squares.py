"""Which mask squares each water triangle of a mesh paints into.

The masks step (``O4_Mask_Utils.record_water_tris``) hands every water
triangle to the squares whose padded pre-mask it reaches: its own square
at ``mask_zl`` and, when its barycentre sits in an outer quarter of that
square, the neighbours across that edge or corner.  This module answers
that for a whole mesh at once with numpy (issue #2269: the per-triangle
Python loop read a three-million-triangle mesh one numpy element at a
time).  The answer is the loop's, value for value and in the loop's
order: squares in the order the loop first met them, each square's
triangles in mesh order.
"""
from __future__ import annotations

import numpy
import O4_Geo_Arrays as GEO_ARRAYS

__all__ = ["water_tris_by_square"]

def _square_keys(til_x, til_y, quarter_x, quarter_y):
    """``(key_x, key_y, valid)``, each ``(n, 4)``: per triangle its own
    square, then — where its barycentre's quarter of the square
    (``quarter_x``/``quarter_y``, 0..3) is an outer one — the square
    across that side, across that corner, and above or below, in that
    order (the order the retired per-triangle loop appended them)."""
    west = quarter_x == 0
    east = quarter_x == 3
    north = quarter_y == 0
    south = quarter_y == 3
    step_x = numpy.where(west, -16, numpy.where(east, 16, 0))
    step_y = numpy.where(north, -16, numpy.where(south, 16, 0))
    side_x = west | east
    side_y = north | south
    key_x = numpy.stack([til_x, til_x + step_x, til_x + step_x, til_x], 1)
    key_y = numpy.stack([til_y, til_y, til_y + step_y, til_y + step_y], 1)
    valid = numpy.stack(
        [numpy.ones_like(side_x), side_x, side_x & side_y, side_y], 1)
    return (key_x, key_y, valid)


def water_tris_by_square(coords, triangles, rows, zoomlevel, bounds):
    """The triangles ``rows`` of a mesh grouped by the mask squares they
    paint into.

    ``coords`` is the mesh's ``(n, 5)`` node array (lon, lat first),
    ``triangles`` its ``(m, 3)`` corners, ``bounds`` the tile's
    ``(til_x_min, til_y_min, til_x_max, til_y_max)`` at ``zoomlevel``;
    a triangle whose square lies more than one square outside is left
    out.  Returns ``(kept, groups)``: the rows kept, and a list of
    ``((til_x, til_y), [tri, ...])`` where ``tri`` is the triangle's
    ``(lat1, lon1, lat2, lon2, lat3, lon3)``.
    """
    rows = numpy.asarray(rows, dtype=numpy.int64)
    if not rows.size:
        return (rows, [])
    (til_x_min, til_y_min, til_x_max, til_y_max) = bounds
    corners = triangles[rows]
    lon = coords[:, 0][corners]
    lat = coords[:, 1][corners]
    bary_lat = (lat[:, 0] + lat[:, 1] + lat[:, 2]) / 3
    bary_lon = (lon[:, 0] + lon[:, 1] + lon[:, 2]) / 3
    (til_x, til_y) = GEO_ARRAYS.wgs84_to_orthogrid(
        bary_lat, bary_lon, zoomlevel)
    keep = numpy.flatnonzero(
        (til_x >= til_x_min - 16) & (til_x <= til_x_max + 16)
        & (til_y >= til_y_min - 16) & (til_y <= til_y_max + 16))
    if not keep.size:
        return (rows[keep], [])
    (fine_x, fine_y) = GEO_ARRAYS.wgs84_to_orthogrid(
        bary_lat[keep], bary_lon[keep], zoomlevel + 2)
    (key_x, key_y, valid) = _square_keys(
        til_x[keep], til_y[keep], (fine_x // 16) % 4, (fine_y // 16) % 4)
    valid = valid.ravel()
    key_x = key_x.ravel()[valid]
    key_y = key_y.ravel()[valid]
    owners = numpy.repeat(numpy.arange(keep.size), 4)[valid]
    span_y = int(key_y.max() - key_y.min()) + 1
    codes = (key_x - key_x.min()) * span_y + (key_y - key_y.min())
    order = numpy.argsort(codes, kind="stable")
    ordered = codes[order]
    starts = numpy.flatnonzero(
        numpy.concatenate(([True], ordered[1:] != ordered[:-1])))
    ends = numpy.concatenate((starts[1:], [ordered.size]))
    table = numpy.stack(
        [lat[keep, 0], lon[keep, 0], lat[keep, 1], lon[keep, 1],
         lat[keep, 2], lon[keep, 2]], 1)
    tris = list(map(tuple, table.tolist()))
    groups = []
    # The sort is stable: a group's first member is where the loop first
    # met that square, and its members stay in mesh order.
    for group in numpy.argsort(order[starts], kind="stable").tolist():
        members = order[starts[group]:ends[group]]
        first = int(members[0])
        groups.append(((int(key_x[first]), int(key_y[first])),
                       [tris[k] for k in owners[members].tolist()]))
    return (rows[keep], groups)
