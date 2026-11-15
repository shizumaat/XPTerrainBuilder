"""A STOP CARRIED OVER A RAMP BY AN OBJECT DECK (#2062 spec R3b E, amended
R5 E′1; RULINGS 2026-11-14d/e/f/j, 22d, 22n).

A mapped bore's ramp stops at the pavement and the roads beside its
corridor (``planar/structures``'s clip loop).  A stop whose part inside the
corridor lies under OBJECT DECKS (``obj_ivals``: the pack's hard-deck
footprints crossing it) is the deck's road, carried OVER the ramp -- but
only by a deck that is a BRIDGE: one with a bridge read (a deck of a free
or kept stack of ``Airport.deck_stacks``, or of ``Airport.kept_candidates``,
every end of it on land) whose top (the stack's zero plus the deck's
authored top) stands at least ``[bridge] clearance_m`` over the ramp floor
under it.  Otherwise the stop stands (today's clip), noted
``deck_without_bridge_read`` or ``deck_too_low``.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import typing as _t

from shapely.ops import unary_union

__all__ = ["DeckReads", "carried_part", "carry_of"]


class DeckReads:
    """deck object id -> ``(stack, deck top)`` for every deck with a bridge
    read, every end of it on land (module doc)."""

    def __init__(self, airport, objects) -> None:
        from ..model.deck_stack import FREE, KEPT
        by_id = {str(o.id): o for o in objects or ()}
        self._top: dict[str, tuple[_t.Any, float]] = {}
        stacks = (*(getattr(airport, "deck_stacks", ()) or ()),
                  *(getattr(airport, "kept_candidates", ()) or ()))
        for st in stacks:
            if st.kind not in (FREE, KEPT):
                continue
            for d in st.decks:
                oid = str(d.object_id)
                o = by_id.get(oid)
                lines = [ln for ln in (d.end_a, d.end_b) if ln]
                land = [e for e in st.ends if str(e.object_id) == oid]
                if o is None or getattr(o, "deck_top_z", None) is None \
                        or len(lines) != 2 or len(land) != len(lines) or oid in self._top:
                    continue
                y = float(o.deck_top_z) - float(o.anchor_z) - float(o.agl_m)
                self._top[oid] = (st, float(st.zero_z) + y)

    def top(self, oid: str) -> "float | None":
        """The deck's top on its stack's zero, or ``None`` (no bridge read)."""
        got = self._top.get(str(oid))
        return None if got is None else got[1]

    def stack(self, oid: str):
        got = self._top.get(str(oid))
        return None if got is None else got[0]


def carried_part(ref: str, probe, stops: _t.Sequence, gap: float):
    """The stop ``ref``'s part within ``gap`` of the corridor ``probe``."""
    near = probe.buffer(gap)
    return unary_union([p.intersection(near) for p, r in stops if r == ref])


def carry_of(ref: str, probe, stops: _t.Sequence, obj_ivals: _t.Sequence, gap: float,
             floor_at: _t.Callable[[float, float], float], clearance: float,
             reads: DeckReads) -> "tuple[tuple[str, ...], str]":
    """``(the deck ids carrying the stop, note)``: ``((), "")`` where the
    stop's part in the corridor is not under the object decks (the clip
    stands, as before E); ``((), note)`` where it is, but a deck there has
    no bridge read or stands under ``clearance`` over the floor
    (``floor_at(s0, s1)``: the ramp floor's highest level under the deck's
    stretch ``s0 .. s1``); else the decks."""
    part = carried_part(ref, probe, stops, gap)
    if part.is_empty or not obj_ivals:
        return (), ""
    under = [(o, s0, s1, dp) for o, s0, s1, dp, _z in obj_ivals if dp.distance(part) < gap]
    if not under:
        return (), ""
    cover = unary_union([dp for _o, _s0, _s1, dp in under]).buffer(gap)
    if part.difference(cover).area > gap * gap:
        return (), ""
    ids = []
    for oid, s0, s1, _dp in under:
        top = reads.top(oid)
        if top is None:
            return (), f"{ref}: deck {oid} over it has no bridge read: deck_without_bridge_read"
        floor = float(floor_at(s0, s1))
        if top - floor < clearance - 1e-9:
            return (), (f"{ref}: deck {oid} top {top:.2f} stands {top - floor:.2f} m over the "
                        f"floor {floor:.2f} (< {clearance:.2f}): deck_too_low")
        ids.append(str(oid))
    return tuple(dict.fromkeys(ids)), ""
