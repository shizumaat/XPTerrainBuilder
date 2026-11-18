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

Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import typing as _t

__all__ = ["stacked_on", "unit_of"]


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
