"""THE VALID AREA OF A SHAPE: an overlay operand GEOS can always read.

GEOS refuses an overlay on an invalid operand (``TopologyException: side
location conflict``): a self-touching ring, or a shape snap-rounded on a
fixed precision model and handed back with pieces that touch or overlap
(the precision model rides on every result made from it, #952).  Issue
#1098 (EDDF, 2026-10-20) lost a whole airport's patch to one such operand.

:func:`valid_area` reads the AREA of a shape — floating precision (the
coordinates already lie wherever they lie, so dropping the model moves
nothing), ``make_valid`` only where GEOS calls it invalid, and only its
polygonal parts (a repaired self-touching sliver also yields lines and
points, which carry no area).  A valid floating shape is returned as is.
``geom`` imports nothing of v2.
"""
from __future__ import annotations

import shapely
from shapely.geometry import Polygon

__all__ = ["valid_area"]


def valid_area(geom):
    """The polygonal area of ``geom``, valid and in floating precision
    (``None`` / empty -> an empty Polygon)."""
    if geom is None or geom.is_empty:
        return Polygon()
    if shapely.get_precision(geom) != 0.0:
        geom = shapely.set_precision(geom, 0.0)
    if geom.is_valid and geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    fixed = geom if geom.is_valid else shapely.make_valid(geom)
    polys = [p for p in shapely.get_parts(fixed)
             if p.geom_type in ("Polygon", "MultiPolygon") and not p.is_empty]
    if not polys:
        return Polygon()
    return polys[0] if len(polys) == 1 else shapely.union_all(polys)
