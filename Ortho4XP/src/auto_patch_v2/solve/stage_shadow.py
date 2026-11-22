"""THE STAGE-2 AIRSIDE A GENERATED DECK'S CUT MUST NOT MOVE (owner RULINGS
2026-11-19s (1): "airside is unaffected, solved like there is no bridge";
bar: airside movers against the no-bridge solve <= 0.05 m).

Stage 1 holds the airside pavement it solves; but an airside-class vertex
stage 1 does not solve -- a plateau's apron, a lower level's pad, a
pavement vertex the full map minted -- is stage 2's, and a cut levelled
metres under the ground pulls it through the ground between (KORD 1.0.565:
``pav252#plateau:building31`` 0.80 m, 34-45 m from the cut; KPHX
``building18``'s plateau 0.31 m, 173 m away).

The rewrite (``constraints/deck_floor_follow``) hands ``stage2_shadow``:
the pins, flat groups and constants as they stood WITHOUT the cut, and the
vertices to hold.
:func:`held_levels` solves that shadow once and makes every held vertex a
stage-2 constant at its shadow level, so the cut's rows reach no airside.
Build-time impact: one more stage-2 solve, at an airport with a generated
deck only, warm-started from the same seed.  Nothing here names an airport.
"""
from __future__ import annotations

import time
import typing as _t

__all__ = ["held_levels"]


def held_levels(shadow: _t.Mapping, cs, levels: _t.Mapping[int, float],
                fixed2: _t.Mapping[int, float], to_stage2: _t.Callable,
                solve: _t.Callable, rep: dict) -> dict[int, float]:
    """``fixed2`` with every ``shadow["hold"]`` vertex not already fixed at
    its level in the shadow solve (module doc).  ``cs``: the set the
    caller's rewrites handed stage 2 -- the shadow is it with the pins and
    flat groups as they stood before the cut (``shadow["pins"]`` /
    ``["flats"]``: every other rewrite's rows stay); ``levels``: stage 1's;
    ``to_stage2(cs, free)``: the stage-2 set the caller states (the join's
    hold law, the released pins); ``solve(cs, fixed)``: one stage-2 solve;
    ``rep`` takes the counts."""
    hold = [int(v) for v in shadow.get("hold", ()) if int(v) not in fixed2]
    if not hold:
        return dict(fixed2)
    t0 = time.perf_counter()
    free = frozenset(shadow.get("free") or ())
    fixed = {v: z for v, z in levels.items() if v not in free}
    fixed.update({int(v): float(z) for v, z in (shadow.get("fixed") or {}).items()})
    import dataclasses as _dc
    cs_a = _dc.replace(cs, pins=tuple(shadow["pins"]), flats=tuple(shadow["flats"]))
    sol, _r = solve(to_stage2(cs_a, free), fixed)
    out = dict(fixed2)
    z = getattr(sol, "z", None)
    n = 0
    if z is not None and len(z):
        for v in hold:
            if v < len(z) and z[v] == z[v]:
                out[v] = float(z[v])
                n += 1
    rep["stage2_shadow"] = {"held": n, "wall_s": round(time.perf_counter() - t0, 3)}
    return out
