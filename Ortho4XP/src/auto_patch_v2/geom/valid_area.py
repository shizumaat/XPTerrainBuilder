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

:func:`_covered_area` reads the area a shape COVERS — the union of its
parts' valid areas — for a shape whose parts overlap or nest, where
``make_valid`` would read a nested part as a HOLE.  :func:`minus` is the
difference that cannot abort a build: the exact overlay, and only where
GEOS refuses it, the covered areas of both operands.
"""
from __future__ import annotations

import shapely
from shapely.geometry import Polygon

__all__ = ["minus", "valid_area"]


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


def _covered_area(geom):
    """The area ``geom`` covers: each part's :func:`valid_area`, unioned.
    A valid shape is returned as is.  MEASURED KHOU (#2051): a mitre
    ``buffer`` of a valid landing came back as an outer shell with a
    41.7 m2 copy NESTED inside it (``Nested shells``); its area is the
    outer shell's, not the outer shell less a hole."""
    if geom is None or geom.is_empty:
        return Polygon()
    if geom.is_valid and shapely.get_precision(geom) == 0.0:
        return geom
    parts = [valid_area(p) for p in shapely.get_parts(geom)]
    parts = [p for p in parts if not p.is_empty]
    if not parts:
        return Polygon()
    return parts[0] if len(parts) == 1 else shapely.union_all(parts)


def minus(a, b):
    """``a.difference(b)``; where GEOS refuses it (``TopologyException``
    on an invalid operand, #2051), the difference of their
    :func:`_covered_area`.  A difference GEOS answers is returned as GEOS
    answers it, so no build that did not throw changes."""
    try:
        return a.difference(b)
    except shapely.errors.GEOSException:
        return _covered_area(a).difference(_covered_area(b))
