"""THE FRONT FLOOR (#2062 spec R3b C; owner RULINGS 2026-11-06c (5) applied
to an entrance face's wings; owner 2026-11-15T04:08Z Q1: "expose the whole
headwall the object models (trimmed at airside pavement) for face_front_m
in front of it").

An entrance face states its FRONT WALL's two ends across the bore
(``Portal.front_xy``, ``airport/entrance_front``).  For the stations within
``[tunnel.object] face_front_m`` of the mouth the ramp's half widths are
the front's (:func:`front_halves`: the hull of every pin the group's mouth
object faces, as ``mouth_opening.group_opening`` hulls their openings);
beyond it the opening's -- ONE step, at a station protected at
``face_front_m`` (:func:`stepped`).  The band is trimmed ACROSS the bore,
per side (:func:`trim`): a side widens past the opening only as far as no
airside pavement, runway-family face, other structure or non-host pad
stands within ``gap`` of it.  It never shortens the ramp.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import typing as _t

from shapely.geometry import Point

from .mouth_opening import axis_left_normal, opening_halves

__all__ = ["front_halves", "trim", "stepped"]

#: the lateral step a trimmed side is read at
_STEP_M = 0.5


def front_halves(axis, pins: _t.Sequence[_t.Any]) -> "tuple[float, float] | None":
    """``(left, right)`` half widths spanning the hull, across ``axis``
    (mouth first), of every pin's ``front_xy``, or ``None``."""
    edges = [tuple(e) for p in pins for e in (getattr(p, "front_xy", ()) or ())]
    if len(edges) < 2 or len(axis.coords) < 2:
        return None
    m = axis.coords[0]
    nv = axis_left_normal(axis)
    offs = sorted(((e[0] - m[0]) * nv[0] + (e[1] - m[1]) * nv[1], e) for e in edges)
    return opening_halves(axis, (offs[0][1], offs[-1][1]))


def trim(axis_fn, axis, front: tuple[float, float], base: tuple[float, float],
         depth: float, stop, gap: float) -> tuple[float, float]:
    """``front`` with each side cut back, toward ``base`` (the opening's
    halves, never less), to the last lateral offset at which no ``stop``
    geometry (prepared) stands within ``gap`` on the stations ``0`` ..
    ``depth`` of the band (``axis_fn(s)``: the axis point at ``s``)."""
    if stop is None:
        return front
    nv = axis_left_normal(axis)
    ss = [0.0, 0.5 * depth, depth]
    out = []
    for side, (f, b) in zip((1.0, -1.0), zip(front, base, strict=True), strict=True):
        w = b
        while w + _STEP_M <= f + 1e-9:
            wn = w + _STEP_M
            pts = [axis_fn(s) for s in ss]
            hit = any(stop.intersects(Point(x + side * wn * nv[0], y + side * wn * nv[1])
                                      .buffer(gap)) for x, y in pts)
            if hit:
                break
            w = wn
        out.append(max(b, min(f, w)))
    return out[0], out[1]


def stepped(base_fn, front: tuple[float, float], depth: float):
    """The half-width function: ``front`` for stations within ``depth`` of
    the mouth, ``base_fn`` (or its constant) beyond."""
    def fn(s: float):
        return front if s <= depth + 1e-9 else base_fn(s)
    return fn
