"""A COVERED TRENCH'S SIDE RIM STANDS UNDER ITS COVER, NEVER PAST IT (#2239;
owner 2026-11-21 "a visible gap between the bridge and the taxiway means
aircraft can't cross"; RULINGS 2026-10-30 Q-A "ending ``wall_gap_m`` inside
the deck's edge", 2026-09-08a "the drop must be hidden").

A signature-B shell (``airport/object_cut``: a shell under a flush hard
cover) is cut with its rim on its own FOOTPRINT (the wall band and the
trench, ``planar/structure_geometry.geometry_from_trench``) and its floor
that footprint eroded by the walls' stand-off.  Where the cover is the deck
an airport's pavement drives across, the trench's SIDES under it are the
deck's end lines -- and a footprint reaching past the cover's edge leaves
an open slot between the deck and the taxiway that the mesh drops into.
MEASURED (CYYZ 1.0.572, as X-Plane draws it, along the taxiway through the
deck): the rim stood 0.83 m past the cover's edge on one side (thin wall
solids beyond the deck) and 1.28 m past its hard edge on the other (the
wall's outer face, under a cap that is not hard).

THE RULE: across the stretch of the trench whose axis lies under the cover
(the cross-sections between consecutive stations under it), the footprint
is clipped to the cover shrunk by ``wall_gap_m``, and the trench with it;
the floor then stands the walls' stand-off inside that, out of sight under
the deck.  A footprint already under its cover there is not touched, and
the trench beyond the cover (its mouths, its open ramps) never is.  Pure
shape; nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from ..model.frame import XY

__all__ = ["under_cover"]

#: a footprint reaching less than this plan area past its cover is under it
#: (the arrangement's own rounding, never a slot a wheel finds), m2
_HAIR_M2 = 0.01


def _normal(axis: _t.Sequence[XY], i: int) -> XY:
    """The left-hand unit normal at ``axis[i]`` (``planar/
    structure_geometry.normals``'s convention: left = (-dy, dx))."""
    a, b = axis[max(0, i - 1)], axis[min(len(axis) - 1, i + 1)]
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return (-dy / L, dx / L)


def _covered_strip(axis: _t.Sequence[XY], cover, far: float):
    """The cross-sections ``far`` either side of the axis between every two
    consecutive axis points that both lie under ``cover`` (``None`` where
    none do)."""
    if cover is None or cover.is_empty or len(axis) < 2:
        return None
    under = [cover.contains(Point(p)) for p in axis]
    quads = []
    for i in range(len(axis) - 1):
        if not (under[i] and under[i + 1]):
            continue
        (ax, ay), (bx, by) = axis[i], axis[i + 1]
        (nx, ny), (mx, my) = _normal(axis, i), _normal(axis, i + 1)
        q = Polygon([(ax + nx * far, ay + ny * far), (bx + mx * far, by + my * far),
                     (bx - mx * far, by - my * far), (ax - nx * far, ay - ny * far)])
        if q.is_valid and q.area > 0.0:
            quads.append(q)
    return unary_union(quads) if quads else None


def under_cover(footprint, trench, axis: _t.Sequence[XY], cover, gap: float):
    """``(footprint, trench, moved m2)``: both clipped to ``cover`` shrunk
    by ``gap`` across its covered stretch (module doc); unchanged (moved
    0.0) where the footprint stands under the cover there."""
    if footprint is None or cover is None or cover.is_empty:
        return footprint, trench, 0.0
    far = math.sqrt(footprint.area) + footprint.length
    strip = _covered_strip(axis, cover, far)
    if strip is None or strip.is_empty:
        return footprint, trench, 0.0
    past = footprint.intersection(strip).difference(cover)
    if past.area < _HAIR_M2:
        return footprint, trench, 0.0
    keep = cover.buffer(-gap, join_style="mitre")
    inside = footprint.intersection(strip).intersection(keep)
    fp = unary_union([footprint.difference(strip), inside])
    return fp, trench.intersection(fp), float(footprint.difference(fp).area)
