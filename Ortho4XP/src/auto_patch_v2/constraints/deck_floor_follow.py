"""THE FLOOR UNDER A GENERATED DECK FOLLOWS THE DECK AS SOLVED (owner
2026-11-17 18:30Z: "Be sure the cut goes all the way under anywhere we add
a bridge"; spec 2123 A1 Q6).

A generated deck's floor (``planar/deck_generated``) stands ``thickness_m +
[tunnel] clearance_m`` under its top.  The planar stage sets it from the
deck's PRE-SOLVE estimate (``DeckBridge.deck_z``, the survey beside its end
lines) and ``constraints/structures`` pins every datum station at it (the
ladder floor, #2072 B1: the solve has nothing to trade between the floor and
airside).  The airside solve then puts the end lines where the routes make
them feasible -- MEASURED ESSA ``o4gen_95e0e654``: ends 28.68 / 28.97, the
floor pinned 23.25 from an estimate of 29.39, 0.53 m shallow.

The end lines are stage 1 columns, constants of stage 2 (``constraints/
deck_anchor``: a taxi deck's stations are held rigid in the airside solve).
So between the two stages (``solve_design``'s ``stage2_rewrite``) each
generated deck's floor pins move to ``min(end level - its depth)`` over the
deck's end lines, read off stage 1's levels -- never higher than the planar
floor (a deeper pin stands: the deck solved higher than estimated keeps its
clearance).  A pack hard deck's floor is the object's own and stays.
Pure: a new set, the original untouched; no generated deck, no change.
Nothing here names an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import statistics
import typing as _t

from .edge_floor import DECK_FLOOR

__all__ = ["floor_follow_rewrite"]


def _floor_targets(pm, levels: _t.Mapping[int, float]) -> dict[str, float]:
    """Per generated deck id: ``min(end level - end depth)`` over its end
    lines' stations as stage 1 solved them."""
    from ..model.structures import is_generated
    decks = {d.object_id: d for d in getattr(pm, "decks", ()) or () if is_generated(d)}
    out: dict[str, float] = {}
    for a in getattr(pm, "deck_anchors", ()) or ():
        d = decks.get(a.object_id)
        zs = [float(levels[s]) for s in a.stations if s in levels]
        if d is None or not zs:
            continue
        depth = d.depth_a if a.end == "a" else d.depth_b
        t = statistics.median(zs) - float(depth)
        out[a.object_id] = min(out.get(a.object_id, t), t)
    return out


def floor_follow_rewrite(pm, cs, levels: _t.Mapping[int, float]) -> tuple[_t.Any, dict]:
    """``(cs with each generated deck's floor pins lowered to the floor its
    solved end lines need, the report)`` (module doc)."""
    target = _floor_targets(pm, levels)
    rep: dict = {"decks": 0, "pins": 0, "max_drop_m": 0.0}
    if not target:
        return cs, rep
    deck_of = {tn.id: getattr(tn, "deck_bridge", "") for tn in getattr(pm, "structures", ()) or ()}
    by_tn: dict[str, float] = {}
    for p in cs.pins:
        if p.source.ruling == DECK_FLOOR and p.source.inputs:
            tid = p.source.inputs[0]
            if deck_of.get(tid) in target:
                by_tn[tid] = max(by_tn.get(tid, -float("inf")), float(p.z))
    drop = {tid: target[deck_of[tid]] - z for tid, z in by_tn.items()
            if target[deck_of[tid]] < z - 1e-6}
    if not drop:
        return cs, rep
    pins = []
    for p in cs.pins:
        tid = p.source.inputs[0] if p.source.ruling == DECK_FLOOR and p.source.inputs else None
        if tid in drop:
            p = _dc.replace(p, z=float(p.z) + drop[tid])
            rep["pins"] += 1
        pins.append(p)
    rep["decks"] = len({deck_of[t] for t in drop})
    rep["max_drop_m"] = round(-min(drop.values()), 3)
    return _dc.replace(cs, pins=tuple(pins)), rep
