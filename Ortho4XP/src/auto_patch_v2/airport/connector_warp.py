"""A CONNECTOR BETWEEN TWO SEPARATELY SEATED BUILDINGS IS WARPED TO MEET
BOTH (owner RULINGS 2026-11-18h (3), #2129).

Owner 2026-11-18T18:09Z: "Can we use the same code we used for rails, to
keep vertical components vertical, and put the slope into connecting decks,
sky bridges, etc, so that individual buildings still seat straight, and
groups maintain their connecting pieces".  Rule (3): a connector between
two separately seated buildings at different heights -- a sky bridge, a
walkway, a connecting deck: a body whose ends touch two bodies of
different groups or seats -- is WARPED to meet both with the #2144 deck
warp (``deck_profile``: ``y' = y + D(x, z)``, piers and walls stay
vertical), capped at ``[deck] shear_max_grade`` (10 %, §49 (5)).  Above the
cap it keeps today's seat and is listed.

WHO (:func:`bridges`, read by the touch pass over its FINAL zeros): a
touch-graph node that is a CONNECTOR (footless) or a deck body (class
``deck`` / ``elevated``), not stacked on walls (rule (2) carries those),
TOUCHING at least two BUILDING nodes whose final zeros differ by more than
the materiality tolerance (a carrier it does not touch is no end: EDDH
``luft_08__b12``, carried on a host 45 m from it, touches one building).

NODES (:func:`connector_groups`): ``deck_profile._nodes`` per SEAT (a
building's bodies at one zero; a placement split over two zeros is two
seats), and the connector's own CARRIER as a node at its zero where the
connector stands over it in plan (a walkway resting on its host's roof
line reads no drawn-height contact with it, yet it is held there).  Fewer
than two nodes, or nodes within ``float_tol_m`` of each other: nothing.

Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["bridges", "connector_groups"]


def _is_deck(b: _t.Any) -> bool:
    return b.body_class == "deck" or bool(getattr(b, "elevated", False))


def bridges(nodes: _t.Sequence[_t.Any], pairs: _t.Iterable[tuple[int, int]],
            body: _t.Callable[[_t.Any], _t.Any], final: _t.Callable[[int], float],
            *, stacked: _t.AbstractSet[int], tol_m: float, building: str,
            connector: str) -> list[tuple[int, str]]:
    """``[(record, body id)]`` of every connector between two seats (WHO in
    the module doc); ``final(node)`` its final zero."""
    touch: dict[int, set[int]] = {}
    for i, j in pairs:
        touch.setdefault(i, set()).add(j)
        touch.setdefault(j, set()).add(i)
    out = []
    for c, n in enumerate(nodes):
        b = body(n)
        if c in stacked or n.fixed or not (n.kind == connector or _is_deck(b)):
            continue
        ends = {k for k in touch.get(c, ()) if nodes[k].kind == building}
        zs = [final(k) for k in ends]
        if len(zs) >= 2 and max(zs) - min(zs) > tol_m:
            out.append((n.key[0], str(b.body_id)))
    return out


def _carrier_node(pieces: _t.Sequence[_t.Any], k: int, xy: _t.Callable,
                  law: _t.Any, z0: float) -> "tuple | None":
    """The connector's carrier as a node ``(D, contact, piece)``: where the
    connector stands over it in plan, ``reach_m`` around; None with no
    carrier, a carrier of another anchor or no plan overlap."""
    from shapely.ops import unary_union

    from .deck_profile import _polys_of
    pc = pieces[k]
    name = str(getattr(pc.body, "merged_into", "") or "")
    host = [c for c, q in enumerate(pieces)
            if q.frame == pc.frame and q.name == name and q.datum[:2] == pc.datum[:2]]
    if not host:
        return None
    mine = unary_union([g for g, _p in _polys_of(pc, xy)])
    theirs = unary_union([g for c in host for g, _p in _polys_of(pieces[c], xy)])
    at = mine.intersection(theirs.buffer(law.reach_m))
    if at.is_empty:
        return None
    return (pieces[host[0]].zero - pieces[host[0]].datum[2] - (z0 - pc.datum[2]), at, host[0])


def connector_groups(pieces: _t.Sequence[_t.Any], keys: _t.Iterable[tuple[int, str]],
                     xy: _t.Callable, law: _t.Any, skip: _t.AbstractSet[int]
                     ) -> _t.Iterator[tuple]:
    """``(group id, [piece], nodes, riders, zero)`` of every connector of
    ``keys`` (``(record, body id)``) not already in a deck group
    (``skip``) whose nodes stand more than ``law.float_tol_m`` apart."""
    from .deck_profile import _nodes
    at = {(pc.key[0], str(pc.body.body_id)): k for k, pc in enumerate(pieces)}
    for key in sorted(set(keys)):
        k = at.get((int(key[0]), str(key[1])))
        if k is None or k in skip:
            continue
        pc = pieces[k]
        z0 = float(pc.zero)
        nodes, riders = _nodes(pieces, [k], xy, law, per_seat=True)
        host = _carrier_node(pieces, k, xy, law, z0)
        if host is not None and not any(abs(d - host[0]) <= 1e-3 and
                                        pieces[c].key[0] == pieces[host[2]].key[0]
                                        for d, _g, c in nodes):
            nodes = nodes + [host]
        ds = [d for d, _g, _c in nodes]
        if len(ds) < 2 or float(np.ptp(ds)) <= law.float_tol_m:
            continue
        yield f"{pc.frame}|connector:{pc.name}", [k], nodes, riders, z0
