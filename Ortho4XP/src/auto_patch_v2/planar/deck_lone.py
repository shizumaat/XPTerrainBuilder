"""A LONE MOUTH CUTS THE WHOLE DECK (#2239 / #2241, spec cyyz-decks-r3;
owner sim read 2026-11-26T15:02Z: "the road envelope under/through the
bridge must stay clear").

A bore under a pack deck is cut from each of its mouths to the deck's
MIDLINE (``deck_bridge.deck_mouth``): the two mouths of one bore each cut
half the deck.  Where the deck's bore mouths all stand on ONE of its sides
(``deck_bridge.deck_side``) -- the far mouth read as another object's
corridor, or never mapped -- nothing cut the far half: MEASURED CYYZ FA
(tunnel way -902, its NW mouth taken by the infield bridge's tunnel object)
the NW half of the ring stood on the taxiway's pavement at the deck's level
in the control, on the deck's own ground at that level once the ring was the
deck's.  Moving the mouth to the ring's far line instead was refused: the
ramp then reads its mapped road as ending 0 m past it.

THE RULE: such a deck is LONE (:func:`lone_decks`); its corridor's share is
the whole deck (``deck_bridge._keep``'s ``lone``) and its floor runs on from
the mouth across the far half, the corridor's own carriageway wide, at the
mouth's floor (:func:`lone_floor`).  Nothing here names a pack or an airport.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString
from shapely.ops import unary_union

from ..model.structures import is_generated
from .deck_bridge import deck_polygon, deck_side

__all__ = ["lone_decks", "lone_floor"]


def lone_decks(groups, deck_of, edge_of) -> set[int]:
    """The PACK decks (by ``id``) whose bore mouths all stand on ONE of
    their sides (module doc).  A generated deck's cut is its own
    (``planar/deck_carve``), never a lone mouth's: MEASURED KORD (capture
    lbridge2), read as lone, generated deck o4gen_4a473c94 took 17 floor
    vertices pinched to its airside and a service road 4.3 m off."""
    sides: dict[int, set[int]] = {}
    for g in groups:
        if g.corridor is not None or any(edge_of.get(id(m)) is not None for m in g.members):
            continue
        d = next((deck_of[id(m)] for m in g.members if deck_of.get(id(m)) is not None), None)
        if d is not None and not is_generated(d):
            sides.setdefault(id(d), set()).add(deck_side(d, g.members[0].inward))
    return {k for k, v in sides.items() if len(v) == 1}


def lone_floor(db, axis: LineString, inward: _t.Sequence[float], half: float, ramp, outer):
    """``(ramp, outer)`` with the floor run on from the mouth (``axis``'s
    first point) along ``inward`` across the rest of ``db``'s ring,
    ``half`` either side (module doc)."""
    ring = deck_polygon(db)
    L = math.hypot(*inward) or 1.0
    ux, uy = inward[0] / L, inward[1] / L
    m = axis.coords[0]
    xs = [p[0] for p in db.ring]
    ys = [p[1] for p in db.ring]
    big = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) + 1.0
    strip = LineString([m, (m[0] + ux * big, m[1] + uy * big)]).buffer(
        half, cap_style="flat").intersection(ring)
    if strip.is_empty or half <= 0.0:
        return ramp, outer
    return unary_union([ramp, strip]), unary_union([outer, strip])
