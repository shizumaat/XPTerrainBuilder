"""A GENERATED TAXIWAY DECK NOBODY PAINTS TAKES ITS ROUTE'S CENTRELINE
(owner 2026-11-21T16:00Z, KRDU: "For some reason the markings are also
missing on the bridges at KRDU").

A generated deck redraws the paint that drew there before it: the apt.dat
``120`` lines it drops (``apt_flatten``) and the pack author's painted
lines over its ring (``deck_author_art.deck_lines``).  A pack whose bridge
OBJECT carried the taxiway's markings in its own texture (MEASURED KRDU
1.0.571: ``CTR_TML.obj`` / ``STH_TML.obj`` on ``BRIDGE1.png``; no apt.dat
line and no pack line over four of its six deck rings) leaves nothing to
redraw once that object is hidden, so the deck drew bare concrete.

:func:`route_centreline` then paints the taxiway centreline the deck's own
carried route states: the 1202 route clipped to the ring, as one apt.dat
``120`` piece of the plain taxiway centreline (line type 1), drawn through
the same X-Plane line art as a dropped line (``deck_objects``).  Only a
taxiway deck, only where no centreline is dropped across it and no author
line runs along its route (an edge line is no centreline): a deck with a
centreline keeps exactly its own paint.  Nothing
here names an airport; build-time impact: one line clip per deck.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString

from .apt_edit import Dropped
from .deck_objects import ring_polygon

__all__ = ["route_centreline"]

#: apt.dat ``120`` line type of the taxiway centreline painted (solid yellow)
_CENTRELINE = 1
#: the centreline types a dropped piece already paints (plain, ``_b``, wide)
_CENTRE_TYPES = frozenset((1, 51, 10, 60))


def route_centreline(rec: _t.Mapping, dropped: _t.Sequence, authored) -> list:
    """``[Dropped]``: the route's centreline over deck record ``rec`` when
    nothing else paints it (module doc), else ``[]``."""
    if str(rec.get("family") or "") not in ("taxi", "taxiway"):
        return []
    if any(int(getattr(d, "line", 0) or 0) in _CENTRE_TYPES for d in dropped or ()):
        return []
    route = [tuple(q) for q in rec.get("route") or ()]
    route = [q for i, q in enumerate(route) if i == 0 or q != route[i - 1]]
    if len(route) < 2:
        return []
    ring = ring_polygon(rec["ring"])
    if any(_along(pts, route, ring) for _page, pts in getattr(authored, "lines", ()) or ()):
        return []
    inside = LineString(route).intersection(ring)
    return [Dropped(-1, tuple(tuple(c) for c in g.coords), _CENTRELINE, 0)
            for g in getattr(inside, "geoms", [inside])
            if g.geom_type == "LineString" and len(g.coords) >= 2 and g.length > 0.0]


#: an author's line within this of the route (metres) paints its centreline
_ALONG_M = 3.0


def _along(pts, route, ring) -> bool:
    """Does the author's line ``pts`` (lon/lat) paint the route's
    centreline: its piece in ``ring`` lies within :data:`_ALONG_M` of
    ``route`` along most of its length (an edge or shoulder line does not)."""
    import math

    from shapely.affinity import scale
    if len(pts) < 2:
        return False
    c = ring.centroid
    k = math.cos(math.radians(c.y))
    def to_m(g):
        return scale(g, xfact=111320.0 * k, yfact=110540.0, origin=(c.x, c.y))
    piece = to_m(LineString(pts).intersection(ring))
    if piece.is_empty or piece.length <= 0.0:
        return False
    near = piece.intersection(to_m(LineString(route)).buffer(_ALONG_M))
    return near.length > 0.5 * piece.length
