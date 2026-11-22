"""A ROAD DECK SPANS THE WHOLE CUT (owner RULINGS 2026-11-19s (8) (d),
KPHX 1.0.566: "The two road bridges to the east of the eastern most taxiway
bridge, done reach across their whole span, leaving floating ends ... the
bridges are the same length as the taxiway ones they are paralleling, just
narrower").

A road bridge whose axis crosses a generated taxiway deck's cut (one of the
deck's carve paths) and runs within :data:`ALONG_DEG` of that deck's axis
runs on, straight past its mapped ends, to the deck's two END LINES -- the
cut's crests: end A through ``o`` along ``w``, end B through ``o + u``
(the deck's parallelogram ``o + s u + t w``).  Of several such decks, the
nearest.  The publication draws the road deck that long
(``pipeline/road_deck``); the carve lands the ground at each of its ends at
the taxiway deck's end level (``constraints/deck_carve``).

Pure plan geometry; nothing here names an airport.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Polygon

__all__ = ["ALONG_DEG", "DeckSpan", "span_to_cut"]

XY = tuple[float, float]
#: a road bridge runs along a taxiway deck within this angle of its axis (deg)
ALONG_DEG = 30.0


class DeckSpan(_t.NamedTuple):
    """A generated deck as the span reads it: its id, ring, carve paths'
    lines and parallelogram ``(o, u, w)``."""

    object_id: str
    ring: _t.Sequence[XY]
    paths: _t.Sequence[_t.Sequence[XY]]
    frame: tuple[XY, XY, XY]


def _param(p: XY, d: XY, q: XY, w: XY) -> "float | None":
    """``s`` where the line ``p + s d`` meets the line through ``q`` along ``w``."""
    det = d[0] * w[1] - d[1] * w[0]
    if abs(det) < 1e-9:
        return None
    return ((q[0] - p[0]) * w[1] - (q[1] - p[1]) * w[0]) / det


def span_to_cut(axis: LineString, decks: _t.Iterable[DeckSpan]
                ) -> "tuple[LineString, str] | None":
    """``(axis run on to the end lines, the deck's id)`` (module doc);
    ``None`` where it crosses no deck's cut or already reaches both."""
    c = list(axis.coords)
    (ax, ay), (bx, by) = c[0], c[-1]
    L = math.hypot(bx - ax, by - ay)
    if L <= 1e-9:
        return None
    d = ((bx - ax) / L, (by - ay) / L)
    cos_t = math.cos(math.radians(ALONG_DEG))
    best = None
    for dk in decks:
        if not any(len(p) >= 2 and LineString(p).intersects(axis) for p in dk.paths):
            continue
        o, u, w = dk.frame
        lu = math.hypot(*u)
        if lu <= 1e-9 or abs(d[0] * u[0] + d[1] * u[1]) / lu < cos_t:
            continue
        ts = [_param((ax, ay), d, q, w) for q in (o, (o[0] + u[0], o[1] + u[1]))]
        if None in ts:
            continue
        s0, s1 = min(0.0, *ts), max(L, *ts)
        if s0 < -1e-3 or s1 > L + 1e-3:
            # two decks over one road share a cut: the nearest (KJFK -833
            # ran to the farther)
            near = Polygon(dk.ring).distance(axis)
            if best is None or near < best[0]:
                best = (near, s0, s1, dk.object_id)
    if best is None:
        return None
    _n, s0, s1, oid = best
    pts = [(ax + d[0] * s0, ay + d[1] * s0)] if s0 < -1e-3 else []
    pts += c
    pts += [(ax + d[0] * s1, ay + d[1] * s1)] if s1 > L + 1e-3 else []
    return LineString(pts).simplify(0.01), oid
