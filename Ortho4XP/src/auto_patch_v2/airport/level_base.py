"""A UNIT STANDING ON TWO LEVELS SEATS EACH PIECE BY ITS OWN WALLS (#2195 /
#2196; owner sim read 2026-11-20T14:20Z on a fuel farm cut into a hillside:
"Fuel farm tanks are being raised, still locked to the upper parking area
as one pad" and "the large object ... which models the building and the
actual pavement is floating instead of seated on the ground").

``footprint_unit.plan_unit_datums`` seats a unit's pad pieces (the pieces
the pad-level pass cut, one per pad, one root id) at ``median(pad) - base``
with ONE base for the whole root: the median authored ``y`` of every walled
foot of the unit (RULINGS 2026-10-22b), so the pieces of one building take
one zero.  A unit authored on TWO LEVELS -- a pit floor a storey or more
under the floor its upper pieces stand on -- whose pads stand at those two
levels (a held terrace, ``classify/pad_sunk``) reads a base between the
two, and its pieces' zeros then disagree by the full step between the
pads (MEASURED: a fuel farm with walls' feet at y -16.7 on its pit pad and
+0.03 on its upper pad, root base -6.3: zeros 366.4 / 381.4 on pads at
360.5 / 375.6 -- the 22o group took the lower and buried the pavement).

:func:`level_zeros` re-reads such a root: a LOW piece -- its pad a storey
or more under the root's highest pad piece -- takes ``median(its pad) -
its own base`` (its own walled feet only) where that brings its zero
closer to the high pieces' (their median, root base) by more than a
storey.  The high pieces keep the root's base; the touching-group pass
(22o) then keeps them one group, as the author drew them.  Any other
root is untouched.

Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import typing as _t

__all__ = ["level_zeros"]


def _spread(zs: _t.Sequence[float]) -> float:
    return max(zs) - min(zs) if zs else 0.0


def level_zeros(pieces: _t.Mapping[str, tuple[str, float, float, float]],
                storey_m: float, counts: dict) -> dict[str, float]:
    """``{piece id: its new zero}`` (module doc).  ``pieces`` maps a pad
    piece's unit id to ``(root id, its pad's median level, the root's
    base, its own walls' base)``."""
    import statistics as _st
    by_root: dict[str, list[tuple[str, float, float, float]]] = {}
    for uid, (root, level, root_base, own_base) in pieces.items():
        by_root.setdefault(root, []).append((uid, level, root_base, own_base))
    out: dict[str, float] = {}
    for _root, rows in sorted(by_root.items()):
        top = max(lv for _u, lv, _rb, _ob in rows)
        high = [lv - rb for _u, lv, rb, _ob in rows if lv > top - storey_m]
        if len(rows) < 2 or len(high) == len(rows):
            continue
        hz = _st.median(high)
        for u, lv, rb, ob in rows:
            if lv > top - storey_m:
                continue
            if abs(lv - ob - hz) < abs(lv - rb - hz) - storey_m:
                out[u] = lv - ob
                counts["unit_level_bases"] = counts.get("unit_level_bases", 0) + 1
    return out
