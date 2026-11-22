"""THE TAXI ROUTE RUNS ON ACROSS THE PAVEMENT THE PLANAR STAGE ADDS
(owner 2026-11-21T16:00Z, KRDU taxiway E: "should be sloping the whole way
from one end to the other to be able to make the necessary climb").

The classifier cuts each 1202 taxi chain only where a pavement source holds
it (``classify/roles._cut_lines``: the chain clipped to the airside
region), and that cut line is the planar map's taxi centreline -- the
breakline the taxi trend levels to the ground (``constraints/taxi_trend``).
Pavement the planar stage adds AFTER classify -- a hidden pack deck's plate
paved (``deck_takeover._paved_over``), a cut deck's at-grade plan
(``deck_span_cut.at_grade_cells``), a withheld generated deck's ring
filled (``deck_airside.fill_rings``) -- held no source when the classifier
ran, so the chain across it had no centreline: its vertices took no trend
and the §61 membrane held them level with whatever they touched (MEASURED
KRDU STH_TML obj140, 1.0.571: taxiway E's 460 m between its south bridges
flat at 114.73 m over ground rising 116.8 -> 123.4 m).

:func:`with_route_lines` gives such pavement the centreline the classifier
would have cut: each taxi chain of the airport's network (``classify/
evidence.chains_from_edges``, the classifier's own construction) clipped to
the added cells, less what an existing centreline already runs along.
Nothing here names an airport; build-time impact: one chain walk and a
few line clips where a pass adds pavement (milliseconds).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

__all__ = ["with_route_lines"]

#: the shortest centreline piece added (metres); the overlap an existing
#: centreline already owns is read within :data:`_OWN_M`
_MIN_M = 2.0
_OWN_M = 0.5


def _chains(airport) -> list:
    """The airport's taxi chains, as ``classify/evidence.build_evidence``
    splits them (at runway nodes and network junctions)."""
    from ..classify.evidence import chains_from_edges, runway_rectangle
    nodes = {nid: n.xy for nid, n in (getattr(airport, "taxi_nodes", {}) or {}).items()}
    edges = [e for e in getattr(airport, "taxi_edges", ()) or ()
             if e.a in nodes and e.b in nodes]
    rw_nodes = {n for e in edges if e.is_runway for n in (e.a, e.b)}
    rects = [runway_rectangle(rw) for rw in getattr(airport, "runways", ()) or ()]
    if rects:
        u = unary_union(rects)
        rw_nodes |= {n for n, xy in nodes.items() if u.intersects(Point(xy))}
    taxi = [(e.a, e.b, e.width_class, e.name) for e in edges if not e.is_runway]
    return chains_from_edges(nodes, taxi, rw_nodes, False)


def with_route_lines(classification, airport, added: _t.Sequence) -> tuple[_t.Any, int]:
    """``(classification with a taxi centreline cut line across the
    ``added`` polygons wherever a taxi chain runs over them and no taxi
    centreline does, the pieces added)`` (module doc)."""
    from ..classify.roles import CutLine
    from ..geom.parts import line_parts
    polys = [p for p in added or () if p is not None and not p.is_empty]
    if classification is None or not polys or airport is None:
        return classification, 0
    area = unary_union(polys)
    own = [LineString(c.points) for c in getattr(classification, "cut_lines", ()) or ()
           if c.kind == "taxi_centerline" and len(c.points) >= 2]
    owned = unary_union(own).buffer(_OWN_M) if own else None
    new = []
    for c in _chains(airport):
        if not c.line.intersects(area):
            continue
        g = c.line.intersection(area)
        if owned is not None:
            g = g.difference(owned)
        new += [CutLine("taxi_centerline", f"taxi{c.id}", tuple(ln.coords), c.letter)
                for ln in line_parts(g) if ln.length >= _MIN_M]
    if not new:
        return classification, 0
    return (_dc.replace(classification, cut_lines=tuple(classification.cut_lines) + tuple(new)),
            len(new))
