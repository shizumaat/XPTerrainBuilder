"""THE PARTS OF A SHAPELY RESULT: what an overlay op returned, as a list.

A difference / intersection / union hands back a Polygon, a LineString, a
Multi*, a GeometryCollection or nothing; every caller wants "the lines" or
"the polygons" of it.  ONE implementation per reading (lane ``v2trim``,
owner RULINGS 2026-10-04c (2)).  The two polygon readings are NOT the
same filter and are named for what they keep.  ``geom`` imports nothing
of v2.
"""
from __future__ import annotations

import shapely
from shapely.geometry import LineString, Polygon

__all__ = ["areal_part", "line_parts", "polygon_parts_with_area",
           "nonempty_polygon_parts"]


def line_parts(geom) -> list[LineString]:
    """The LineStrings of ``geom`` — itself, or its members of positive
    length (``None`` / empty -> ``[]``)."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    return [g for g in getattr(geom, "geoms", ()) if g.geom_type == "LineString"
            and g.length > 0]


def polygon_parts_with_area(geom) -> list[Polygon]:
    """The Polygons of ``geom`` that carry AREA (over 1e-6 m2): slivers an
    overlay leaves behind are dropped (``None`` / empty -> ``[]``)."""
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and g.area > 1e-6]


def nonempty_polygon_parts(g) -> list[Polygon]:
    """The Polygons of ``g`` — itself, or its non-empty Polygon members,
    whatever their area (``None`` / empty -> ``[]``)."""
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [q for q in getattr(g, "geoms", []) if isinstance(q, Polygon) and not q.is_empty]


def areal_part(geom):
    """The AREA of an overlay result, as ONE geometry: a Polygon or
    MultiPolygon as is, a collection as its Polygons (an empty Polygon for
    none).  GEOS's overlay is non-strict: a difference or intersection of
    two areas also hands back the edges and points where a sliver collapsed
    or two shapes only touch, in a GeometryCollection the NEXT overlay
    refuses (``Overlay input is mixed-dimension``, ``Unable to determine
    overlay result geometry dimension``).  MEASURED #1136 HEAZ: runway
    18/36's zone 2 carried two collapsed lines (15.3 m, 0.8 m) into the
    #951 road cut; #1147 KCLT: a road ribbon carried two into the next
    way's held-apart cut.  The polygons of one overlay result are disjoint,
    so they are kept as they lie — never re-unioned."""
    if geom is None or geom.is_empty:
        return Polygon()
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    polys = [q for g in shapely.get_parts(geom) for q in shapely.get_parts(g)
             if q.geom_type == "Polygon" and not q.is_empty]
    if not polys:
        return Polygon()
    return polys[0] if len(polys) == 1 else shapely.multipolygons(polys)
