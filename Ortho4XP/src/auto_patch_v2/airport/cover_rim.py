"""A COVERED TRENCH'S RIM STANDS AT ITS COVER'S EDGE, NEVER PAST IT; THE
ROAD UNDER IT STAYS CLEAR (#2239 / #2241; owner 2026-11-21 "a visible gap
between the bridge and the taxiway means aircraft can't cross"; owner sim
read 2026-11-26T15:02Z on 1.0.585: the strip under the deck's ends "is NOT
support -- the road envelope under/through the bridge must stay clear;
ends must be clean, not jagged").

A signature-B shell (``airport/object_cut``: a shell under a flush hard
cover) is cut with its rim on its own FOOTPRINT (the wall band and the
trench, ``planar/structure_geometry.geometry_from_trench``) and its floor
that footprint eroded by the walls' stand-off.  Where the cover is a deck
the airport's pavement drives across, the cover's SIDES along the trench
are its end lines -- and a footprint reaching past them leaves an open
slot between the deck and the taxiway that the mesh drops into.
MEASURED (CYYZ 1.0.572, as X-Plane draws it): the rim stood 0.83 m past
the cover's edge on one side and 1.28 m on the other.

THE RULE: the footprint (and the trench, by the few centimetres it may
stand past the deck) is cut back to the cover's LATERAL edges -- the
cover's ring edges that run along the trench (their direction nearer the
axis's than square to it) -- by the strip beyond each such edge, as wide
as the wall band can reach (``far``).  Nothing is cut under the cover and
nothing beyond its mouths, so the road under it is never narrowed and the
cut ends square at the deck's corners.  The rim then stands ON the deck's
edge, and the floor ring stands only the arrangement's least band
(``[cutout] ring_floor_m``) inside it there (``geometry_from_trench``'s
``covered``), never the wall's thickness: the wall the shell models stands
OUTSIDE the deck, so under the deck no wall hides a wider band.

MEASURED (lcyyz6's clip, which this replaces): the footprint clipped to the
cover shrunk by ``wall_gap_m`` across the quads between axis stations under
the cover, and the floor then eroded by the wall's thickness from that
rim, left a ground strip ~1.8 m wide along both walls inside the tunnel,
ending jagged at the last station under the cover (CYYZ T deck: cut-cover
46 of 127 samples over its bank, worst 1.29 m).  Pure shape; nothing here
names a pack, a resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..model.frame import XY

__all__ = ["side_lines", "under_cover"]

#: a footprint reaching less than this plan area past its cover is under it
#: (the arrangement's own rounding, never a slot a wheel finds), m2
_HAIR_M2 = 0.01
#: cos 45 deg: an edge runs ALONG the trench when its direction is nearer
#: the axis's than square to it
_ALONG = math.sqrt(0.5)


def _tangent(axis: LineString, p: XY) -> XY:
    """The axis's unit direction at its point nearest ``p``."""
    s = axis.project(Point(p))
    a = axis.interpolate(max(0.0, s - 1.0))
    b = axis.interpolate(min(axis.length, s + 1.0))
    dx, dy = b.x - a.x, b.y - a.y
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def _sides(poly, ax: LineString) -> list[list[tuple[XY, XY, XY]]]:
    """The cover's two SIDES along the trench: per side (left / right of
    the axis), the LONGEST run of consecutive ring edges that run along it
    (module doc), each edge ``(a, b, outward normal)``.  A short run on a
    mouth -- the step of a staircase across the road -- is no side: its
    strip would stand across the road beyond the mouth."""
    ring = list(poly.exterior.coords)[:-1]
    n = len(ring)
    ccw = poly.exterior.is_ccw
    tag: list = []
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        tx, ty = _tangent(ax, ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0))
        if L <= 1e-9 or abs(dx * tx + dy * ty) / L < _ALONG:
            tag.append(None)
            continue
        m = (dy / L, -dx / L) if ccw else (-dy / L, dx / L)          # outward
        tag.append(((a, b, m), m[1] * tx - m[0] * ty > 0.0, L))      # left of the axis?
    runs: list[tuple[bool, float, list]] = []
    start = next((i for i in range(n) if tag[i] is None), None)
    order = range(n) if start is None else [(start + 1 + k) % n for k in range(n)]
    for i in order:
        t = tag[i]
        if t is not None and runs and runs[-1][2] and runs[-1][0] == t[1] \
                and tag[(i - 1) % n] is not None:
            side, L, es = runs[-1]
            runs[-1] = (side, L + t[2], es + [t[0]])
        elif t is not None:
            runs.append((t[1], t[2], [t[0]]))
    out = []
    for side in (True, False):
        mine = [r for r in runs if r[0] == side]
        if mine:
            out.append(max(mine, key=lambda r: r[1])[2])
    return out


def side_lines(cover, axis: _t.Sequence[XY]) -> list[list[XY]]:
    """The cover's two SIDES along the trench (:func:`_sides`) as
    polylines, of its largest polygon; ``[]`` unless it has both."""
    if cover is None or cover.is_empty or len(axis) < 2:
        return []
    polys = [g for g in getattr(cover, "geoms", [cover]) if g.geom_type == "Polygon"]
    if not polys:
        return []
    runs = _sides(max(polys, key=lambda g: g.area), LineString(axis))
    out = [[tuple(run[0][0])] + [tuple(b) for _a, b, _m in run] for run in runs]
    return out if len(out) == 2 else []


def _lateral_strips(cover, axis: _t.Sequence[XY], far: float):
    """The plan strips ``far`` wide beyond the cover's two SIDES
    (:func:`_sides`), less the cover itself; ``None`` where it has none."""
    if cover is None or cover.is_empty or len(axis) < 2 or far <= 0.0:
        return None
    ax = LineString(axis)
    quads = []
    for poly in (g for g in getattr(cover, "geoms", [cover]) if g.geom_type == "Polygon"):
        for run in _sides(poly, ax):
            for a, b, (mx, my) in run:
                q = Polygon([a, b, (b[0] + mx * far, b[1] + my * far),
                             (a[0] + mx * far, a[1] + my * far)])
                if q.is_valid and q.area > 0.0:
                    quads.append(q)
    if not quads:
        return None
    out = unary_union(quads).difference(cover)
    return None if out.is_empty else out


def under_cover(footprint, trench, axis: _t.Sequence[XY], cover, far: float):
    """``(footprint, trench, moved m2)``: both cut back to ``cover``'s
    lateral edges (module doc); unchanged (moved 0.0) where the footprint
    stands under the cover there."""
    if footprint is None or cover is None or cover.is_empty:
        return footprint, trench, 0.0
    strip = _lateral_strips(cover, axis, far)
    if strip is None:
        return footprint, trench, 0.0
    past = footprint.intersection(strip)
    if past.area < _HAIR_M2:
        return footprint, trench, 0.0
    fp = footprint.difference(strip)
    return fp, trench.difference(strip), float(past.area)
