"""THE RAMP STANDS ON ITS MOUTH OBJECT'S OPENING (#1917; owner RULINGS
2026-11-06c (5): "the ramp depth and width should be set based on the
mouth object, such that the bottom of the ramp meets the bottom of the
mouth object that faces the ramp").

A portal pin states its opening's two edges across the bore at its end
(``Portal.opening_xy``: an entrance face's gap between its walls,
``trench_objects._wall_opening``; a roofed portal's roof span,
``portal_objects._roof_opening``).  The ramp's half widths either side of
its axis are those edges' offsets from the axis (:func:`opening_halves`),
so the ramp spans the opening edge to edge wherever the mapped road runs
in it, never an opening-wide ramp centred on the road.  MEASURED LOWS west
mouth (tile build on 1.0.474, ``tools/drawn_site.py``): the two
carriageways' midline ran 1.5 m off the opening's middle, and the
symmetric 10.25 m half left the cut wall standing over the opening's
north 1.5 m.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

from ..model.frame import XY

__all__ = ["axis_left_normal", "group_opening", "opening_halves"]


def axis_left_normal(axis) -> XY:
    """The left-hand unit normal of ``axis`` (a LineString, mouth first) at
    its mouth -- the side ``structure_geometry`` offsets a ramp's LEFT
    edge to."""
    (x0, y0), (x1, y1) = axis.coords[0], axis.coords[1]
    L = math.hypot(x1 - x0, y1 - y0) or 1.0
    return (-(y1 - y0) / L, (x1 - x0) / L)


def opening_halves(axis, edges: _t.Sequence[XY]) -> "tuple[float, float] | None":
    """``(left, right)`` half widths of the ramp about ``axis`` (mouth
    first) that span the opening's ``edges`` exactly, or ``None`` with no
    edges or where the axis runs outside the opening (the road would leave
    the ramp: the symmetric width stays)."""
    if len(edges) != 2 or len(axis.coords) < 2:
        return None
    m = axis.coords[0]
    nv = axis_left_normal(axis)
    offs = [(e[0] - m[0]) * nv[0] + (e[1] - m[1]) * nv[1] for e in edges]
    left, right = max(offs), -min(offs)
    if left <= 0.0 or right <= 0.0:
        return None
    return float(left), float(right)


def group_opening(pins: _t.Sequence[_t.Any], axis) -> "tuple[float, tuple[XY, XY]]":
    """``(width, (edge, edge))``: THE OPENING OF A GROUP OF BORES ONE MOUTH
    OBJECT FACES is the hull, across ``axis`` (mouth first), of every
    member's opening (``Portal.opening_xy``) -- the ramp grades to the
    object's full width, never to one member's slot (#1737, owner 2026-11-02
    ENGM: "tunnels should grade to it's full width on the low side";
    MEASURED ENGM ``Ham3.obj``: the four rail bores' faces read 28.0 m, 28.0
    m, 28.1 m and 1.2 m -- the last a slot beside the face's wall -- and the
    group's ramp took the first member's 1.2 m).  ``(0.0, ())`` with fewer
    than two edges."""
    edges = [tuple(e) for p in pins for e in (getattr(p, "opening_xy", ()) or ())]
    if len(edges) < 2 or len(axis.coords) < 2:
        return 0.0, ()
    m = axis.coords[0]
    nv = axis_left_normal(axis)
    offs = sorted(((e[0] - m[0]) * nv[0] + (e[1] - m[1]) * nv[1], e) for e in edges)
    (lo, a), (hi, b) = offs[0], offs[-1]
    return float(hi - lo), (a, b)
