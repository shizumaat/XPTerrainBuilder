"""§49 A PARAPET RIDES THE DECK — the seat of a body standing on an
emitted ``bridge_deck:*`` face (design-surface spec §49; owner RULINGS
2026-09-17u-2 / 17x (2)).

BUDGET-MODE IMPLEMENTATION (owner 2026-09-17 late): §49 (1)–(4) and (6)
as ONE override applied to every body the plan has formed, after every
other seat rule has spoken (PASS 3) and before the cut (PASS 4) — the
three mints §49 (4) names (``segment_anchor``, ``_own_ground_file``,
``anchor_for``) all deliver their body HERE, so one site reads the deck
for all three.  §49 (5)'s SHEAR is NOT implemented: every deck-seated
body takes §49 (6)'s FALLBACK, the deck's LOW END over the body's
on-deck feet / samples, so the wall disappears into the rising deck and
never floats (the owner's sentence).  §49 (7)'s deck-substituted cut is
not implemented either.

EXCLUDED BY CONSTRUCTION (§49 (2)): a BASIN body, a DECK / PLATE class
body, a CARRIED body (its carrier is seated), a body already on a §16e
datum, a footprint-unit / family / connector member.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from . import anchor_rule as _ar
from . import obj8_split as _split

__all__ = ["deck_seat", "DECK_REASON", "SAMPLE_GRID"]

#: the reason prefix every deck-seated body is published with
DECK_REASON = "on deck "
#: a footless body's plan-box sample grid (9 x 9 = 81 samples, the
#: scout's own instrument)
SAMPLE_GRID = 9


def _samples(box: tuple[float, float, float, float]
             ) -> list[tuple[float, float, float]]:
    la0, lo0, la1, lo1 = box
    n = SAMPLE_GRID
    return [(la0 + (la1 - la0) * (i + 0.5) / n,
             lo0 + (lo1 - lo0) * (j + 0.5) / n, 0.0)
            for i in range(n) for j in range(n)]


def deck_seat(body: _t.Any, u: _t.Any, m: _t.Any,
              decks: _t.Sequence[_ar.DeckFace], *, on_fraction: float,
              counts: dict[str, int], edge_m: float = 0.0,
              surface: "_ar.Surface | None" = None,
              under_m: float = 0.0) -> _t.Any:
    """The body re-seated on the deck it stands on (§49 (6): its LOW END),
    or the body unchanged.  ``u`` / ``m`` are the plan's Unit / Member
    (the authored frame the offset is spelled in)."""
    if not decks:
        return body
    a = body.anchor
    if (body.body_class in (_ar.BASIN, _ar.DECK, _ar.PLATE_ONLY)
            or body.merged_into or a.datum or a.family or a.connector_of
            or a.unit_seat):
        return body
    if body.feet:
        pts = [(float(f[0]), float(f[1]), float(f[2])) for f in body.feet]
    elif body.plan_box:
        pts = _samples(body.plan_box)
    else:
        return body
    r = _ar.deck_datum_of([(p[0], p[1]) for p in pts], decks, on_fraction,
                          edge_m)
    if r is None:
        return body
    deck, on = r
    if body.feet and surface is not None and under_m > 0.0:
        # A PIER IS NOT A PARAPET (§49 (2), the Bridge2 b1 exclusion —
        # MEASURED: its feet stand 6.9 m UNDER the deck in the trench and
        # 2 of 4 lie within the edge band).  A footed body is on the deck
        # only where the design surface under its feet IS the deck: a
        # foot whose surface reads more than ``under_m`` below the deck's
        # own z there stands under it, not on it.
        keep = []
        for i, z in on:
            sz = surface(pts[i][0], pts[i][1])
            if sz is not None and float(sz) >= z - under_m:
                keep.append((i, z))
        if len(keep) < on_fraction * len(pts):
            counts["deck_refused_under"] = counts.get("deck_refused_under", 0) + 1
            return body
        on = tuple(keep)
    cands = [(pts[i][0], pts[i][1], pts[i][2], z) for i, z in on]
    # §49 (6) THE FALLBACK: the low end — min keyed on the DECK's surface
    # at the foot, the tie to the foot nearest the body's own zero, then
    # the southern/western one (deterministic over a pack)
    low = min(cands, key=lambda c: (round(c[3], 6), round(abs(c[2]), 6),
                                    c[0], c[1]))
    rise = max(c[3] for c in cands) - low[3]
    from .placement_plan import authored_offset   # circular at import time
    off = authored_offset(low[0], low[1], low[2], u.anchor[0], u.anchor[1],
                          m.heading_deg)
    reason = (f"{DECK_REASON}{deck.ref}: low end (§49 (6) fallback, shear "
              f"not delivered; deck rise {rise:.2f} m over {len(cands)}/"
              f"{len(pts)} on-deck {'feet' if body.feet else 'samples'}; "
              f"was: {a.reason})")
    na = _dc.replace(a, lat=low[0], lon=low[1], y_zero=low[2],
                     surface_z=low[3], offset=off, datum=True, reason=reason)
    counts["deck_on_bodies"] = counts.get("deck_on_bodies", 0) + 1
    counts["deck_fallback"] = counts.get("deck_fallback", 0) + 1
    return _dc.replace(body, anchor=na,
                       new_resource=_split.body_resource_name(
                           m.resource, body.body_id, off))
