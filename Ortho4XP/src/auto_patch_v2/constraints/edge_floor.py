"""THE EDGE TRENCH'S FLOOR (#1138; owner sim read 2026-10-28T14:26Z points
2 / 4, RULINGS 2026-10-28u Q271 (b)): the floor of a trench an EDGE BRIDGE
frames hangs from that bridge's SEAT — the solved surface where the
object's top meets the airside, less its walls' bottom
(``planar/bridge_span.EdgeBridge.seat``; ``Tunnel.edge_seats``).

A trench shared by TWO edge bridges (``Tunnel.edge_floor_s``: the open
stretch back to back) runs LINEARLY along the trench, from the first
bridge's own bottom at the far end of that object to the second's at its
back — never level at either bottom, so neither object's walls stand into
the floor.  Every station group of the floor is one two-sided pair of
the mouth-depth idiom (head ``tunnel.mouth_depth_m``, a constraint of the
design solve's active set):

    z[v] − (1 − t)·z[seat₀] − t·z[seat₁] = −((1 − t)·d₀ + t·d₁)

with ``t`` the station's fraction of the stretch, clamped to ``[0, 1]``
(under each object its own bottom).

A HARD-DECK BRIDGE (``planar/deck_bridge``, owner RULINGS 2026-10-30a (2))
states its seat as a SET: the stations of its two END LINES, A then B, each
the mean of its stations' nearest airside vertices, and the deck's own seat
is the mean of the two (``½(mean z[A] + mean z[B]) − ½(d_A + d_B)``: the
zero plus the bottom once ``constraints/edge_deck``'s rigid row holds).  A
seat of one vertex is the edge bridge's, byte for byte.  Nothing here names
an airport.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from ..model.structures import Tunnel

__all__ = ["edge_seats_of", "seat_pair", "sloped_floor_rows", "DECK_FLOOR"]

#: a hard-deck bridge's floor rows' ruling — the mouth-depth head (hard), its
#: own string so the shape joints keep it (``pipeline/shapes.apply_joints``:
#: its seat is the mean of the two end lines the deck's cut puts on two shapes)
DECK_FLOOR = "tunnel.mouth_depth_m (2026-10-30a (2): a hard-deck bridge's floor)"


def edge_seats_of(planar: PlanarMap, law: Law, combine: bool = True):
    """``seats_of(tunnel) -> ((vertex, depth), ...)``: the airside vertex
    at the seat of each edge bridge an edge trench meets
    (``Tunnel.edge_seats``, its own bridge first) and that bridge's depth;
    ``()`` for every other tunnel.  A hard-deck bridge's seat is a SET
    (module doc): ``((vertex, weight), ...)`` in the vertex's place, each
    end line's set and — ``combine`` — each deck's two ends as one seat.
    The airside index is built once, on the first edge trench."""
    memo: list = []

    def seats_of(tn: Tunnel) -> tuple[tuple[_t.Any, float], ...]:
        seats = getattr(tn, "edge_seats", ())
        if not seats:
            return ()
        if not memo:
            from ..model.platform import stage_air_vertices
            from .geometry import nearest_vertex_fn
            memo.append(nearest_vertex_fn(planar, stage_air_vertices(planar, law)))
        near = memo[0]
        if near is None:
            return ()
        if not getattr(tn, "deck_bridge", ""):
            return tuple((near(x, y), float(depth)) for _oid, (x, y), depth in seats)
        ends = tuple((_mean_terms([near(x, y) for x, y in st]), float(depth))
                     for _oid, st, depth in seats)
        if not combine:
            return ends
        return tuple((_mean_terms([], ((a[0], 0.5), (b[0], 0.5))), 0.5 * (a[1] + b[1]))
                     for a, b in zip(ends[0::2], ends[1::2], strict=True))
    return seats_of


def _mean_terms(vs: _t.Sequence[int], sets=()) -> tuple[tuple[int, float], ...]:
    """The MEAN of vertices ``vs`` (or the weighted sum of term ``sets``) as
    ``((vertex, weight), ...)`` summing to one, vertex order."""
    acc: dict[int, float] = {}
    for v in vs:
        acc[v] = acc.get(v, 0.0) + 1.0 / len(vs)
    for terms, w in sets:
        for v, c in terms:
            acc[v] = acc.get(v, 0.0) + w * c
    return tuple(sorted(acc.items()))


def _terms(seat) -> tuple[tuple[int, float], ...]:
    return tuple(seat) if isinstance(seat, tuple) else ((seat, 1.0),)


def seat_pair(v: int, seat: tuple[int, float], src: Source) -> list[Row]:
    """``z[v] = z[seat] − depth`` as the two one-sided rows of the
    mouth-depth idiom (``constraints/structures``)."""
    return sloped_floor_rows([(0.0, [v])], (seat, seat), (0.0, 1.0), src)


def sloped_floor_rows(groups: _t.Sequence[tuple[float, _t.Sequence[int]]],
                      seats: tuple[tuple[int, float], tuple[int, float]],
                      span: tuple[float, float], src: Source) -> list[Row]:
    """The module doc's pair for each station group ``(s, vertices)``'s
    first vertex (the group's ``Flat`` ties the rest): the floor runs from
    ``seats[0]``'s bottom at ``span[0]`` to ``seats[1]``'s at ``span[1]``."""
    (v0, d0), (v1, d1) = seats
    s0, s1 = span
    rows: list[Row] = []
    for s, vs in groups:
        if not vs:
            continue
        t = 0.0 if s1 - s0 <= 1e-9 else min(1.0, max(0.0, (s - s0) / (s1 - s0)))
        acc: dict[int, float] = {}
        for k, c in ((vs[0], 1.0), *((a, -(1.0 - t) * w) for a, w in _terms(v0)),
                     *((b, -t * w) for b, w in _terms(v1))):
            if abs(c) > 1e-12:
                acc[k] = acc.get(k, 0.0) + c
        terms = tuple((k, c) for k, c in acc.items() if abs(c) > 1e-12)
        rhs = -((1.0 - t) * d0 + t * d1)
        rows.append(Linear(terms, None, rhs, src))
        rows.append(Linear(tuple((k, -c) for k, c in terms), None, -rhs, src))
    return rows
