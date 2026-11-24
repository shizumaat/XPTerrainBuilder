"""Array forms of ``O4_Geo_Utils`` conversions, exact to the scalar ones.

A tile step that converts every triangle of a mesh one call at a time
spends seconds in the call overhead alone (issues #850, #2269).  The
conversions here take numpy arrays and answer exactly what the scalar
function answers for each element: where an element sits so close to a
grid boundary that a last-bit difference between numpy's and the C
library's ``log``/``tan`` could move it, the scalar function itself
answers for that element.
"""
from __future__ import annotations

import numpy
import O4_Geo_Utils as GEO

__all__ = ["wgs84_to_orthogrid"]

#: A grid coordinate this close to an integer is placed by the scalar
#: function (a last-bit error is about 1e-13 at these magnitudes).
_BOUNDARY_GUARD = 1e-6


def wgs84_to_orthogrid(lat, lon, zoomlevel):
    """``GEO.wgs84_to_orthogrid`` of arrays: ``(til_x, til_y)`` int64."""
    lat = numpy.asarray(lat, dtype=numpy.float64)
    lon = numpy.asarray(lon, dtype=numpy.float64)
    ratio_x = lon / 180
    ratio_y = numpy.log(numpy.tan((90 + lat) * numpy.pi / 360)) / numpy.pi
    mult = 2 ** (zoomlevel - 5)
    grid_x = (ratio_x + 1) * mult
    grid_y = (1 - ratio_y) * mult
    til_x = numpy.trunc(grid_x).astype(numpy.int64) * 16
    til_y = numpy.trunc(grid_y).astype(numpy.int64) * 16
    near = ((numpy.abs(grid_x - numpy.round(grid_x)) < _BOUNDARY_GUARD)
            | (numpy.abs(grid_y - numpy.round(grid_y)) < _BOUNDARY_GUARD))
    for i in numpy.flatnonzero(near).tolist():
        (til_x[i], til_y[i]) = GEO.wgs84_to_orthogrid(
            float(lat[i]), float(lon[i]), zoomlevel)
    return (til_x, til_y)
