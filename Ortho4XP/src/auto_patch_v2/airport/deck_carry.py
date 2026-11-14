"""WHAT A STACK DECK CARRIES, AND WHERE (#1971; spec
``interchange-levels-20261113.md`` §3.4-§3.6).

One hard-deck PIECE of a stack member, read on its own plate and on the
map's routes — never a name:

* the AXIS: the piece's minimum rotated rectangle; its two short sides are
  the END edges, its long sides the SIDE edges (a piece squarer than
  ``2 x [bridge] abutment_sample_step_m`` has no axis and is not read);
* CARRIED: a mapped highway route crossing the ring through BOTH end edges
  (or through one, ending within ``abutment_sample_step_m`` of the other);
* ACROSS: a route through both side edges (``airport/deck_stack`` rules it
  under or over by the levels); one end and one side is a note only;
* the END LINES: stations every ``abutment_sample_step_m`` along each end
  edge; ``top`` is the PLATE's own height there (:func:`_plate_top`: the
  plate triangle under each station, ``geom/lowest_face``), never the
  maximum within a reach — an arched plate stands at its ends' height on
  its end lines, not its crown's.

THE WAY REWRITE (§3.5, :func:`bridge_stretches`): the stretch of every
carried way between the piece's end edges becomes a mapped bridge
(``bridge=yes`` plus :data:`DECK_TAG`), same id and kind; the rest keeps its
tags; ``layer`` is never invented.  Every reader of
``deck_signature.is_bridge_way`` then reads it as the deck's, unedited.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring

from ..geom.lowest_face import floor_z_at
from ..model.frame import rotated_rectangle

__all__ = ["Carry", "carry_of", "bridge_stretches", "route_chains", "DECK_TAG"]

XY = tuple[float, float]

#: the synthesized tag naming the deck that carries a stretch
#: (``structure_underpass.UNDERPASS_TAG`` is the precedent)
DECK_TAG = "o4_deck"


@_dc.dataclass(frozen=True)
class Carry:
    """One deck piece's reading (module doc): its end edges ``edge_a`` /
    ``edge_b`` and their stations, the plate's top on each, the way ids it
    carries and those crossing it side to side, and the axis' outward unit
    vector at each end."""

    edge_a: tuple[XY, XY]
    edge_b: tuple[XY, XY]
    end_a: tuple[XY, ...]
    end_b: tuple[XY, ...]
    out_a: XY
    out_b: XY
    top_a: float
    top_b: float
    carried: tuple[int, ...]
    across: tuple[int, ...]
    notes: tuple[str, ...] = ()


def _end_stations(edge: tuple[XY, XY], step: float) -> tuple[XY, ...]:
    """Stations every ``step`` along an end edge, its corners included."""
    (ax, ay), (bx, by) = edge
    n = max(1, int(round(math.dist(edge[0], edge[1]) / step)))
    return tuple((ax + (bx - ax) * k / n, ay + (by - ay) * k / n) for k in range(n + 1))


def _plate_top(plate: np.ndarray, stations: _t.Sequence[XY], inward: XY = (0.0, 0.0),
               edge_m: float = 0.5) -> float:
    """The plate's own height on an end line: the mean over ``stations``
    (moved ``inward`` a hair onto the plate) of the plate triangle under
    each (``plate``: ``(n, 3, 3)`` frame x, y, authored y); ``nan`` where
    no triangle stands under any.  ``edge_m``: how far off a face a station
    still reads it on its plane (``floor_z_at``; 0 for a plate with edge-on
    faces, whose plane extrapolates without bound)."""
    xs = [x + inward[0] for x, _y in stations]
    ys = [y + inward[1] for _x, y in stations]
    zs = floor_z_at(plate, xs, ys, edge_m=edge_m)
    zs = zs[np.isfinite(zs)]
    return float(zs.mean()) if zs.size else math.nan


def _edges(piece: Polygon) -> "tuple | None":
    """``(end a, end b, side, side, long, short)`` of the minimum rotated
    rectangle (end edges = the short sides)."""
    rect = rotated_rectangle(piece)
    if rect.geom_type != "Polygon":
        return None
    c = list(rect.exterior.coords)[:4]
    e = [(c[k], c[(k + 1) % 4]) for k in range(4)]
    la, lb = math.dist(*e[0]), math.dist(*e[1])
    if la <= lb:
        return e[0], e[2], e[1], e[3], lb, la
    return e[1], e[3], e[0], e[2], la, lb


def _seg(e: tuple[XY, XY]) -> LineString:
    return LineString([e[0], e[1]])


def carry_of(piece: Polygon, plate: np.ndarray, routes: _t.Sequence[tuple[_t.Any, LineString]],
             law) -> "Carry | str":
    """Piece ``piece``'s reading (module doc) over ``routes`` — ``(way,
    route)`` for every mapped highway / railway way near it — or why it has
    none."""
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    got = _edges(piece)
    if got is None:
        return "no axis"
    ea, eb, s1, s2, long_m, short_m = got
    if long_m - short_m <= 2.0 * step:
        return f"too square to have an axis ({long_m:.0f} x {short_m:.0f} m)"
    mid = lambda e: ((e[0][0] + e[1][0]) / 2.0, (e[0][1] + e[1][1]) / 2.0)  # noqa: E731
    ma, mb = mid(ea), mid(eb)
    d = math.dist(ma, mb)
    out_a = ((ma[0] - mb[0]) / d, (ma[1] - mb[1]) / d)
    out_b = (-out_a[0], -out_a[1])
    sa, sb = _end_stations(ea, step), _end_stations(eb, step)
    hair = 0.05
    top_a = _plate_top(plate, sa, (-out_a[0] * hair, -out_a[1] * hair))
    top_b = _plate_top(plate, sb, (-out_b[0] * hair, -out_b[1] * hair))
    if not (math.isfinite(top_a) and math.isfinite(top_b)):
        return "its plate stands on neither end line"
    la, lb, l1, l2 = _seg(ea), _seg(eb), _seg(s1), _seg(s2)
    carried: list[int] = []
    across: list[int] = []
    notes: list[str] = []
    for w, route in routes:
        if "highway" not in w.tags and "railway" not in w.tags:
            continue
        hit_a, hit_b = route.intersects(la), route.intersects(lb)
        ends = [Point(route.coords[0]), Point(route.coords[-1])]
        near_a = any(piece.buffer(0.01).contains(p) and la.distance(p) <= step + 0.01
                     for p in ends)
        near_b = any(piece.buffer(0.01).contains(p) and lb.distance(p) <= step + 0.01
                     for p in ends)
        if "highway" in w.tags and ((hit_a and hit_b) or (hit_a and near_b) or (hit_b and near_a)):
            carried.append(int(w.id))
        elif route.intersects(l1) and route.intersects(l2):
            across.append(int(w.id))
        elif (hit_a or hit_b) and (route.intersects(l1) or route.intersects(l2)):
            notes.append(f"way {w.id} runs through one end and one side: unclassified")
    return Carry(ea, eb, sa, sb, out_a, out_b, top_a, top_b,
                 tuple(sorted(set(carried))), tuple(sorted(set(across))), tuple(notes))


def _node(p) -> XY:
    """A way node's join key (millimetres)."""
    return (round(float(p[0]), 3), round(float(p[1]), 3))


def route_chains(ways: _t.Sequence, reach: Polygon) -> list[tuple[int, ...]]:
    """THE CHAIN JOIN (#2035; ``planar/overpass_deck._own_route`` and
    ``airport/bridge_witness`` read it): ``ways`` (each with ``points`` and
    ``tags``) joined END TO END into chains, as index tuples into ``ways``.
    Two ways join at an end node inside ``reach`` — at a mapped bridge's
    end node (every way ending there stands at the bridge's level), or
    where exactly two ways meet and both end (the way merely split there);
    a junction of roads at grade ends a chain."""
    from .deck_signature import is_bridge_way
    at: dict[XY, set[int]] = {}
    for k, w in enumerate(ways):
        for p in w.points:
            at.setdefault(_node(p), set()).add(k)
    root = list(range(len(ways)))

    def find(k: int) -> int:
        while root[k] != k:
            root[k] = root[root[k]]
            k = root[k]
        return k
    for k, w in enumerate(ways):
        for p in (w.points[0], w.points[-1]):
            ks = at[_node(p)]
            if not reach.contains(Point(p)) or len(ks) < 2:
                continue
            ends = [j for j in ks if _node(ways[j].points[0]) == _node(p)
                    or _node(ways[j].points[-1]) == _node(p)]
            if len(ks) == 2 and len(ends) == 2 or any(is_bridge_way(ways[j].tags or {})
                                                      for j in ends):
                for j in ends:
                    root[find(j)] = find(k)
    chains: dict[int, list[int]] = {}
    for k in range(len(ways)):
        chains.setdefault(find(k), []).append(k)
    return [tuple(ks) for ks in chains.values()]


def _span(line: LineString, region: Polygon) -> "tuple[float, float] | None":
    """``(s_in, s_out)`` along ``line`` of its stretch inside ``region``."""
    got = line.intersection(region)
    if got.is_empty or got.length <= 1e-6:
        return None
    pts = [p for g in getattr(got, "geoms", [got]) if g.geom_type == "LineString"
           for p in g.coords]
    ss = [line.project(Point(p)) for p in pts]
    return (min(ss), max(ss)) if ss else None


def bridge_stretches(ways: _t.Sequence, cuts: _t.Mapping[int, _t.Sequence[tuple[str, Polygon]]]
                     ) -> tuple:
    """``ways`` with every carried way's stretch over its deck a mapped
    bridge (module doc).  ``cuts``: way id -> ``(deck id, deck piece
    rectangle)`` per deck carrying it.  A way no deck carries is returned
    as it is (the same object)."""
    out = []
    for w in ways:
        mine = cuts.get(int(w.id))
        if not mine or len(w.points) < 2:
            out.append(w)
            continue
        line = LineString(w.points)
        spans = sorted((sp[0], sp[1], did) for did, region in mine
                       if (sp := _span(line, region)) is not None)
        merged: list[list] = []
        for a, b, did in spans:
            if merged and a <= merged[-1][1] + 1e-6:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b, did])
        if not merged:
            out.append(w)
            continue
        cur = 0.0
        for a, b, did in merged:
            if a - cur > 1e-3:
                out.append(_piece(w, line, cur, a, None))
            out.append(_piece(w, line, a, b, did))
            cur = b
        if line.length - cur > 1e-3:
            out.append(_piece(w, line, cur, line.length, None))
    return tuple(out)


def _piece(w, line: LineString, a: float, b: float, deck: "str | None"):
    """The stretch ``a..b`` of way ``w`` (same id and kind); a deck's own
    stretch tagged a mapped bridge of that deck."""
    pts = tuple((float(x), float(y)) for x, y in substring(line, a, b).coords)
    tags = dict(w.tags)
    if deck is not None:
        if not tags.get("bridge") or tags.get("bridge") == "no":
            tags["bridge"] = "yes"
        tags[DECK_TAG] = deck
    return _dc.replace(w, points=pts, closed=False, tags=tags)
