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

__all__ = ["line_parts", "polygon_parts_with_area", "nonempty_polygon_parts"]


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
