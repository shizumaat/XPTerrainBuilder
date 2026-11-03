"""THE ROUTE A PACK DECK CARRIES (deck redesign §1; owner RULINGS
2026-11-03c): read off the airport's own routes — the apt.dat runway axis
(its two ends) or the row-1202 aircraft taxi edges — never the planar
map's chain, which can run 100 m off the deck's end line (MEASURED LFPG
round 3: 21 of 37 taxi ends read a chain >= 10 m off the end line's
middle).

* the FAMILY is the most senior route the deck carries, ONE per deck: a
  runway axis crossing the deck makes it a ``runway`` deck, else it is a
  ``taxi`` deck (round 3 voted it per end line off the cells at the seats,
  and LFPG ``obj13018`` end B read "taxi" beside the runway it carries);
* the ROUTE is that runway's axis, or the taxi edges crossing the deck run
  on along the straightest continuation ``ROUTE_REACH_M`` each way.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import math

from shapely.geometry import LineString, Polygon

__all__ = ["carried_route", "ROUTE_REACH_M"]

XY = tuple[float, float]

#: how far a taxi route runs on past the deck each way (m)
ROUTE_REACH_M = 600.0
#: the widest turn a taxi route takes at a node to stay on its line (deg)
_STRAIGHT_DEG = 45.0


def carried_route(airport, piece: Polygon) -> tuple[str, tuple[XY, ...], str]:
    """``(family, route, runway id)`` of the deck piece ``piece`` (module
    doc); ``("taxi", (), "")`` where no route of the airport crosses it."""
    best = None
    for rw in getattr(airport, "runways", ()) or ():
        if len(rw.ends) != 2:
            continue
        ln = LineString([rw.ends[0].xy, rw.ends[1].xy])
        across = ln.intersection(piece).length
        if across > 1.0 and (best is None or across > best[0]):
            best = (across, rw)
    if best is not None:
        rw = best[1]
        return "runway", (tuple(rw.ends[0].xy), tuple(rw.ends[1].xy)), str(rw.id)
    return "taxi", _taxi_route(airport, piece), ""


def _taxi_route(airport, piece: Polygon) -> tuple[XY, ...]:
    """The taxi edges crossing ``piece`` (the longest crossing first) run on
    :data:`ROUTE_REACH_M` each way along the straightest continuation."""
    nodes = getattr(airport, "taxi_nodes", {}) or {}
    edges = [e for e in getattr(airport, "taxi_edges", ()) or ()
             if not getattr(e, "is_runway", False) and e.a in nodes and e.b in nodes
             and nodes[e.a].xy != nodes[e.b].xy]
    seed = max(edges, key=lambda e: LineString([nodes[e.a].xy, nodes[e.b].xy])
               .intersection(piece).length, default=None)
    if seed is None or LineString([nodes[seed.a].xy, nodes[seed.b].xy]) \
            .intersection(piece).length <= 1.0:
        return ()
    adj: dict[int, list[int]] = {}
    for e in edges:
        adj.setdefault(e.a, []).append(e.b)
        adj.setdefault(e.b, []).append(e.a)
    ahead = _walk(nodes, adj, seed.a, seed.b)
    back = _walk(nodes, adj, seed.b, seed.a)
    return tuple(tuple(nodes[n].xy) for n in [*reversed(back[1:]), *ahead])


def _walk(nodes, adj: dict, prev: int, at: int) -> list[int]:
    """``[prev, at, ...]``: from edge ``prev → at`` on along the straightest
    edge at each node, until :data:`ROUTE_REACH_M` past ``at`` or no edge
    turns less than :data:`_STRAIGHT_DEG`."""
    path, run = [prev, at], 0.0
    while run < ROUTE_REACH_M:
        a, b = nodes[path[-2]].xy, nodes[path[-1]].xy
        nxt = [n for n in adj.get(path[-1], ()) if n not in path]
        if not nxt:
            break
        n = min(nxt, key=lambda q: _turn(a, b, nodes[q].xy))
        if math.degrees(_turn(a, b, nodes[n].xy)) > _STRAIGHT_DEG:
            break
        run += math.dist(nodes[path[-1]].xy, nodes[n].xy)
        path.append(n)
    return path


def _turn(a: XY, b: XY, c: XY) -> float:
    """The turn (rad, ``0..pi``) from ``a → b`` onto ``b → c``."""
    d = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0])
    return abs((d + math.pi) % (2.0 * math.pi) - math.pi)
