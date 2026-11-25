"""A CENTRELINE THAT IS A HOLE'S ONLY TIE IS A BRIDGE, AND POLYGONIZE
DROPS A BRIDGE (follow-up of #2244).

The slice (``classify/roles._slice``) polygonizes the airside region's
rings and the centreline cuts.  ``_keyholes`` already spurs a centreline
that ENDS INSIDE the pavement to the nearest boundary, because
polygonize drops a dangle.  It drops a BRIDGE too — a cut edge, the
same face on both sides: a centreline whose one end stands on a HOLE of
the region (a runway, which the region excludes) that no other cut
reaches ties that hole to the rest of the network exactly once, bounds
no face, and so reaches neither the cells nor the planar map.

MEASURED at EKVG (tile +62-008, pack Faroes4XPlane, which paints one
pavement polygon ``dsf:pol33`` over the whole field): the runway is a
hole inside that polygon, taxiway C's one cut runs from the runway edge
to the apron's chain node, and the planar map carried no edge of it —
the 08p line read ``0 connected stations, 28 unconnected centreline
edges``, ``network_by_role`` held the runway alone.

:func:`island_spurs` gives such a hole a SECOND tie: the shortest
straight cut from the hole's ring to another ring of the same polygon
(its exterior or another hole), inside the region and no longer than
``keyhole.max_spur_m`` — the keyhole's own reach, so nothing new is
tuned.  The bridge then separates two faces and is a boundary like any
cut.  Nothing here names an airport; build-time impact: one ring walk
per hole that a cut touches (milliseconds).
"""
from __future__ import annotations

import shapely.ops
from shapely.geometry import LineString, Point

from .rules import Rules

__all__ = ["island_spurs"]


def _parts(region) -> list:
    return list(region.geoms) if hasattr(region, "geoms") else [region]


def island_spurs(lines: list[LineString], region, rules: Rules) -> list[LineString]:
    """The spurs that give each hole of ``region`` tied to the network by
    exactly ONE of ``lines`` (an endpoint within
    ``keyhole.deadend_boundary_tol_m`` of its ring) a second tie (module
    doc).  ``[]`` when no such hole exists."""
    if not lines or region is None or region.is_empty:
        return []
    kh = rules.keyhole
    ends = [Point(c) for ln in lines for c in (ln.coords[0], ln.coords[-1])]
    owner = [i for i, _ln in enumerate(lines) for _k in range(2)]
    inside = region.buffer(0.01)
    out: list[LineString] = []
    for poly in _parts(region):
        if poly.geom_type != "Polygon" or not poly.interiors:
            continue
        rings = [LineString(poly.exterior.coords)] + \
            [LineString(h.coords) for h in poly.interiors]
        for k in range(1, len(rings)):
            ring = rings[k]
            ties = {owner[j] for j, p in enumerate(ends)
                    if ring.distance(p) <= kh.deadend_boundary_tol_m}
            if len(ties) != 1:
                continue
            others = shapely.ops.unary_union(rings[:k] + rings[k + 1:])
            a, b = shapely.ops.nearest_points(ring, others)
            spur = LineString([a, b])
            if 0.0 < spur.length <= kh.max_spur_m and inside.contains(spur):
                out.append(spur)
    return out
