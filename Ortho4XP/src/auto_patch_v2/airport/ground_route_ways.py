"""THE AIRPORT'S OWN GROUND ROUTES AS WAYS (#2062 spec R3b E; owner
2026-11-15T04:08Z Q5: "a pack hard deck carrying an apt.dat service route
is a bridge like one carrying a mapped road").

apt.dat row 1206 (``Airport.ground_routes``: a service vehicle edge between
two ``taxi_nodes``) is the authoritative service-road routing (RULINGS
free-road).  The free bridge's W1 (``airport/bridge_witness``) and its
ends' path walk (``airport/bridge_end_state``) read mapped ways; this
module states each ground-route EDGE as one :class:`~..model.airport.
OsmWay` (``highway=service``, ``o4:ground_route``), so ``deck_carry.
route_chains`` joins them end to end as it joins mapped ways.  Over a
``flag`` deck the bridge stretch is the part inside its plate
(:func:`bridged`): an apt.dat route states no ``bridge`` tag.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString
from shapely.ops import split

from ..model.airport import OsmWay

__all__ = ["ground_route_ways", "bridged"]

#: the tag every ground-route way carries
GROUND_ROUTE_TAG = "o4:ground_route"
#: ground-route way ids start here (no mapped way id reaches it)
ID_BASE = 2_000_000_000


def ground_route_ways(airport) -> tuple[OsmWay, ...]:
    """One ``highway=service`` way per apt.dat ground-route edge."""
    nodes = getattr(airport, "taxi_nodes", None) or {}
    out = []
    for k, r in enumerate(getattr(airport, "ground_routes", ()) or ()):
        a, b = nodes.get(r.a), nodes.get(r.b)
        if a is None or b is None or tuple(a.xy) == tuple(b.xy):
            continue
        out.append(OsmWay(ID_BASE + k, "ground_route", (tuple(a.xy), tuple(b.xy)), False,
                          {"highway": "service", GROUND_ROUTE_TAG: "1"}))
    return tuple(out)


def bridged(ways: _t.Sequence[OsmWay], ring) -> list[OsmWay]:
    """``ways`` cut at the plate outline ``ring`` (a flag deck's): each piece
    keeps its way's id, the pieces inside the plate tagged ``bridge=yes``."""
    out: list[OsmWay] = []
    cut = LineString(ring.exterior.coords)
    inner = ring.buffer(1e-6)
    for w in ways:
        line = LineString(w.points)
        if not line.intersects(ring):
            continue
        for g in getattr(split(line, cut), "geoms", ()):
            tags = dict(w.tags)
            if inner.contains(g):
                tags["bridge"] = "yes"
            out.append(OsmWay(w.id, w.kind, tuple(tuple(c) for c in g.coords), False, tags))
    return out
