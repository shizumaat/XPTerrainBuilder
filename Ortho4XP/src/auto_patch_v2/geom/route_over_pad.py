"""A TAXI ROUTE NEVER CROSSES A BUILDING (owner RULINGS 2026-11-19k (2)).

Owner 2026-11-19T03:49Z: *"a taxi route cannot touch a building, if it
does, it's a strong sign it's a bridge"*.  The apt.dat 1202 network (taxi
and runway edges alike) is where an aircraft rolls; a building pad it
passes over is not a building but the ground under a deck or a trench
frame, so the pad mint refuses it and lists it.

Two readings, and only the first refuses:

* ``"over"`` -- the route PASSES OVER the pad's interior: an edge enters
  and leaves it (its piece inside the pad has both ends on the pad's
  boundary), or a route node stands strictly inside it with two or more
  edges (the route goes on through).
* ``"touch"`` -- the route meets the pad but does not pass over it: it
  ends at its edge or inside it (a taxilane to a hangar door, a pier the
  route ends at), or runs along its boundary.  A real building, KEPT, and
  listed so the reading is visible.

No threshold: the test is topological on the route's own segments.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

__all__ = ["OVER", "TOUCH", "RouteWitness"]

#: what :meth:`RouteWitness.read` answers
OVER = "over"
TOUCH = "touch"


class RouteWitness:
    """The airport's 1202 edges as segments, indexed ONCE per pass and
    asked per pad candidate (planar frame metres, ``TaxiNode.xy``)."""

    def __init__(self, airport: _t.Any) -> None:
        nodes = {nid: tuple(n.xy) for nid, n in
                 (getattr(airport, "taxi_nodes", None) or {}).items()}
        self._segs: list[LineString] = []
        degree: dict[int, int] = {}
        for e in getattr(airport, "taxi_edges", ()) or ():
            a, b = nodes.get(e.a), nodes.get(e.b)
            if a is None or b is None or a == b:
                continue
            self._segs.append(LineString([a, b]))
            for n in (e.a, e.b):
                degree[n] = degree.get(n, 0) + 1
        self._through = [Point(nodes[n]) for n, d in degree.items() if d >= 2]
        self._tree = STRtree(self._segs) if self._segs else None
        self._ptree = STRtree(self._through) if self._through else None

    def __bool__(self) -> bool:
        return self._tree is not None

    def read(self, pad) -> tuple[str, float]:
        """``(OVER | TOUCH | "", route length inside the pad in m)``."""
        if self._tree is None or pad is None or pad.is_empty:
            return "", 0.0
        hits = self._tree.query(pad, predicate="intersects")
        if not len(hits):
            return "", 0.0
        rim = pad.boundary
        inside, over = 0.0, False
        for k in hits:
            cut = self._segs[int(k)].intersection(pad)
            for g in getattr(cut, "geoms", (cut,)):
                if g.geom_type != "LineString" or g.length <= 0.0:
                    continue
                inside += float(g.length)
                if g.within(rim):
                    continue                      # along the edge
                if (Point(g.coords[0]).intersects(rim)
                        and Point(g.coords[-1]).intersects(rim)):
                    over = True                   # in at one side, out at another
        if not over and self._ptree is not None:
            for k in self._ptree.query(pad, predicate="intersects"):
                p = self._through[int(k)]
                if not p.intersects(rim):
                    over = True                   # the route goes on through
                    break
        return (OVER if over else TOUCH), round(inside, 2)
