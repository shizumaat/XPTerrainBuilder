"""A gridded geometry's pickle and deep copy carry its precision grid (#1092).

shapely 2.x pickles a geometry as its WKB alone, so ``pickle`` and
``copy.deepcopy`` hand back the shape with ``get_precision == 0``: the grid
set by ``shapely.set_precision(g, grid)`` is dropped, and a later overlay of
the copy nodes differently from the original.  Every stage-cache record
(``airport/stage_cache``), every arrangement-memo front copy
(``planar/arrangement_memo``) and every worker hand-off pickles or deep-copies
such geometry, so a cache hit could differ from the fresh computation.

Importing this module registers, once and process-wide, a ``copyreg``
reducer for each concrete geometry class: a geometry with a grid reduces to
``(regrid, (wkb, grid))``; a geometry without one keeps shapely's own reduce,
so its bytes are unchanged.  Only shape lives here.
"""
from __future__ import annotations

import copyreg

import shapely

__all__ = ["regrid"]

_CLASSES = (shapely.Point, shapely.LineString, shapely.LinearRing,
            shapely.Polygon, shapely.MultiPoint, shapely.MultiLineString,
            shapely.MultiPolygon, shapely.GeometryCollection)


def regrid(wkb: bytes, grid: float):
    """The geometry of ``wkb`` with its precision grid ``grid`` restored (the
    vertices are on that grid already, so this only re-attaches it)."""
    return shapely.set_precision(shapely.from_wkb(wkb), grid, mode="pointwise")


def _reduce(geom):
    grid = shapely.get_precision(geom)
    if grid:
        return regrid, (shapely.to_wkb(geom, include_srid=True), float(grid))
    return geom.__reduce__()


for _cls in _CLASSES:
    copyreg.pickle(_cls, _reduce)
