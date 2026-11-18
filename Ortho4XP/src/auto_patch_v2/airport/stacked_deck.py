"""A DECK STACKED ON WALLS RIDES THOSE WALLS (owner RULINGS 2026-11-18h (2),
#2129).

Owner 2026-11-18T18:09Z: "Can we use the same code we used for rails, to
keep vertical components vertical, ... so that individual buildings still
seat straight, and groups maintain their connecting pieces".  Rule (2): a
deck stacked on walls rides those walls at its AUTHORED relative height,
whatever the gap -- 16v's 1-2 m judgement band does not apply to it.

THE WITNESS, read off the touch pass's nodes (``touch_graph``: one frame,
one zero, so the authored relation of two of its bodies is their spans
over the frame's one zero): a DECK (the plan's class ``deck``; an elevated
piece the carrier law already carries rides its carrier, and is not read
again here -- HECA's material-split hangar pieces, ``metal_net`` /
``metal_strip`` riding their own hosts, would otherwise be re-seated on a
neighbour's wall top) STANDS ON a BUILDING when one of its non-line parts P is
ELEVATED (its authored bottom at least ``walled_m`` over the zero: a slab,
not a ramp on the ground) and a part Q of the building overlaps P in plan
(their plan polygons share area) and rises from below P (Q's bottom at
least ``walled_m`` under P's) to P's own span (Q's top within ``tol_m`` of
P's bottom..top): the slab bears on the wall top.  EDDH's car park: the
top deck ``park_05__b2``'s slab (authored 7.60-8.48) on the walls
``park_04__b6`` (0.00-8.48), seated 1.40 m apart (b2 on its own ramp feet,
b6 on its own ground).

THE DECK'S UNIT.  The bodies the deck's seat holds with it -- one §16g unit
or 22o group in the frame, at the deck's zero -- move with it, so a unit is
never torn (the deck's ramps stay at its ends).  A support is never one of
them.  The caller (``touch_seat``) moves deck and unit to the support's
final zero.

A PIECE CARRIED FAR OVER ITS CARRIER RIDES THE DECK IT CONTINUES
(:func:`rehosted`; master 2026-11-18, extending rule (2)): a carried piece
whose lowest part stands more than a storey (``walled_m``) over its
carrier's top is not resting on it; where it touches, in plan, a building
holding an ELEVATED part at its own authored height (bottoms within
``tol_m``: it continues that deck), it rides that building, not the
carrier.  EDDH ``park_03__b4`` (a 3 x 2 m slab at authored y 8.70, carried
on ``park_04__b9`` whose top is 5.65 m under it) continues ``park_03__b0``'s
deck (slabs at 8.65-8.76): it stepped 1.21 m over it once b0 was levelled.

Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import typing as _t

__all__ = ["stacked_on", "unit_of", "rehosted"]


def _bears(n: _t.Any, s: _t.Any, xy: _t.Callable, walled_m: float, tol_m: float) -> bool:
    """Does an elevated part of node ``n`` rest on a part of node ``s``
    (module doc)?"""
    from .deck_profile import _polys
    mine = [(g, p) for g, p in _polys(n.parts, xy) if n.span(p)[0] >= walled_m]
    if not mine:
        return False
    theirs = _polys(s.parts, xy)
    for g, p in mine:
        lo, hi = n.span(p)
        for h, q in theirs:
            qlo, qhi = s.span(q)
            if (qlo <= lo - walled_m and lo - tol_m <= qhi <= hi + tol_m
                    and g.intersection(h).area > 0.0):
                return True
    return False


def _carried_by(b: _t.Any, s: _t.Any) -> bool:
    """Is deck body ``b`` already carried by the node ``s`` (it rides it)?"""
    return str(getattr(b, "merged_into", "") or "") == s.name


def stacked_on(nodes: _t.Sequence[_t.Any], pairs: _t.Iterable[tuple[int, int]],
               body: _t.Callable[[_t.Any], _t.Any], *, walled_m: float,
               tol_m: float, kind_building: str) -> dict[int, int]:
    """``{deck node: the building node it stands on}`` over the touching
    ``pairs`` whose zeros differ by more than ``tol_m`` (``body(node)``:
    the node's final body).  A deck standing on several takes the lowest:
    no wall top pokes under a floating slab."""
    from .touch_graph import local_metres
    if not nodes:
        return {}
    p0 = nodes[0].parts[0]
    xy = local_metres(float(p0.lat), float(p0.lon))
    out: dict[int, int] = {}
    for i, j in pairs:
        for d, s in ((i, j), (j, i)):
            D, B = nodes[d], nodes[s]
            if (B.kind != kind_building or abs(D.zero - B.zero) <= tol_m or B.fixed
                    or D.fixed or body(D).body_class != "deck" or _carried_by(body(D), B)):
                continue
            if _bears(D, B, xy, walled_m, tol_m):
                if d not in out or nodes[out[d]].zero > B.zero:
                    out[d] = s
    return out


def unit_of(nodes: _t.Sequence[_t.Any], d: int, supports: _t.AbstractSet[int],
            tol_m: float) -> list[int]:
    """The deck ``d`` and the nodes its seat holds with it: one unit or 22o
    group of its frame at its zero, never a support."""
    n = nodes[d]
    keys = {n.unit, n.family, n.grouped} - {""}
    return [d] + [k for k, m in enumerate(nodes)
                  if k != d and k not in supports and not m.fixed and m.frame == n.frame
                  and abs(m.zero - n.zero) <= tol_m
                  and keys & ({m.unit, m.family, m.grouped} - {""})]


def _coplanar(n: _t.Any, d: _t.Any, walled_m: float, tol_m: float) -> bool:
    """Has ``d`` an elevated part whose bottom is within ``tol_m`` of one
    of ``n``'s part bottoms (authored, one frame)?"""
    mine = [n.span(p)[0] for p in n.parts]
    return any(abs(lo - m) <= tol_m for q in d.parts
               for lo in (d.span(q)[0],) if lo >= walled_m for m in mine)


def rehosted(nodes: _t.Sequence[_t.Any], pairs: _t.Iterable[tuple[int, int]], *,
             walled_m: float, tol_m: float, kind_building: str) -> dict[int, int]:
    """``{carried piece: the building whose deck it continues}`` (module
    doc); a piece touching several such takes the lowest."""
    by_name = {(n.frame, n.name): k for k, n in enumerate(nodes)}
    out: dict[int, int] = {}
    for i, j in pairs:
        for p, d in ((i, j), (j, i)):
            P, D = nodes[p], nodes[d]
            c = by_name.get((P.frame, P.carrier)) if P.carrier else None
            if (c is None or c == d or D.kind != kind_building or P.fixed or D.fixed
                    or abs(P.zero - D.zero) <= tol_m):
                continue
            top = max(nodes[c].span(q)[1] for q in nodes[c].parts)
            if (P.bottom() - top > walled_m and _coplanar(P, D, walled_m, tol_m)
                    and (p not in out or nodes[out[p]].zero > D.zero)):
                out[p] = d
    return out
