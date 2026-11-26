"""A UNIT'S LANDSIDE KERB LINE, PUBLISHED ON ITS BLOCK (#2279 step 2; spec
``docs/specs/2279-kerb-frontage-spec.md`` §2).

Classify keeps a lot that meets the apron mostly across a unit's upper
storey groundside as the unit's LANDSIDE (``classify/storey_edge``,
``STOREY_LANDSIDE_KEY``), cuts it back from the storey's PLAN (the hull of
its upper parts) and records the plan rings, the storey's units and its
rise (``STOREY_PLAN_KEY`` / ``STOREY_UNIT_KEY`` / ``STOREY_Y_KEY``).  The
constraints need one more fact the cells cannot carry: WHICH held block's
datum the kerb stands a storey over.  That is read here, once the blocks
exist: a held block of the storey's unit (``planar/low_level.unit_share``)
that the plan covers — the block an upper level of that unit was minted
on first (``reg.landings``, ``UP_KIND``), else the one the plan covers
most.  The record goes on the block's ``held`` entry under
:data:`model.registries.LANDSIDE_KERB` (the ``kerbs`` / floor-yard
precedent: a held block's own annotations), read by
``constraints/kerb_frontage``.

THE FRONTAGE LAW, BOTH SIGNS (RULINGS 2026-11-25g (2); spec
``terminal-frontage-split-level-20261125.md`` §3.1, C12): a unit's HELD
two-floor record (``planar/unit_levels_read``, on its block under
:data:`model.registries.UNIT_LEVELS`) publishes the same kerb record --
its plan, its signed rise, its airside ground, and its LANDSIDE FACE
(``airport/frontage_face``: the band is read along the face, not the whole
outline) -- on its block, unless a landside lot of the unit already
carries one (the storey's own lot, PHLI: one generator, one record).  A
record far from our ground (``far``, 25f) or unconfirmed publishes none."""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..model.registries import LANDSIDE_KERB

__all__ = ["publish_kerbs"]


def _unit_records(reg, units_taken: set, airport, law, blocks=None) -> list:
    """``(block, record)`` for every held block carrying a two-floor record
    the frontage law takes (``unit_storey.frontage_held``) of a unit no
    landside lot published (module docstring), carried by its block
    (``unit_storey.carried_by``; ``blocks``: ``{ref: polygon}``, ``None``
    skips the test)."""
    from ..airport.unit_storey import carried_by, frontage_held
    from ..model.registries import UNIT_LEVELS
    out = []
    for block, h in sorted(reg.held.items()):
        u = h.get(UNIT_LEVELS)
        if u is None or u.unit in units_taken or not frontage_held(u, airport, law) \
                or (blocks is not None and not carried_by(u, blocks.get(block))):
            continue
        out.append((block, {"lot": None, "unit": u.unit, "y": round(float(u.rise), 3),
                            "plan": u.plan, "face": u.face, "air_z": u.ground[0]}))
    return out


def _landside_plans(cells) -> dict[str, tuple]:
    """``{lot ref: (plan, rise, units, the airside ground or None)}`` of every LANDSIDE lot cell
    carrying its kerb line (``classify/storey_edge._kerb_evidence``)."""
    from ..classify.storey_edge import (STOREY_AIR_Z_KEY, STOREY_LANDSIDE_KEY,
                                        STOREY_PLAN_KEY, STOREY_UNIT_KEY, STOREY_Y_KEY)
    out: dict[str, tuple] = {}
    for c in cells:
        ev = c.evidence or {}
        if not (ev.get(STOREY_LANDSIDE_KEY) and ev.get(STOREY_PLAN_KEY)
                and STOREY_Y_KEY in ev):
            continue
        rings = [Polygon(r) for r in ev[STOREY_PLAN_KEY] if len(r) >= 4]
        plan = unary_union([p if p.is_valid else p.buffer(0.0) for p in rings])
        if not plan.is_empty:
            out[str(c.ref)] = (plan, float(ev[STOREY_Y_KEY]),
                               tuple(int(u) for u in ev.get(STOREY_UNIT_KEY, ())),
                               ev.get(STOREY_AIR_Z_KEY))
    return out


def publish_kerbs(cells, pad_regions: _t.Sequence, reg, airport, counts: dict,
                  law=None) -> int:
    """Put each landside lot's kerb record on its unit block's ``held``
    entry (module docstring); returns the lots published, the refused
    counted into ``counts`` (``kerb_frontage_refused``)."""
    plans = _landside_plans(cells)
    if airport is None or getattr(airport, "frame", None) is None:
        return 0
    from .low_level import UP_KIND, unit_share
    to_xy = airport.frame.entry()
    blocks: dict[str, list] = {}
    for r in pad_regions:
        if r.polygon is not None and str(r.ref) in reg.held:
            blocks.setdefault(str(r.ref), []).append(r.polygon)
    union = {k: unary_union(v) for k, v in blocks.items()}
    upper = {str(v.get("block")) for v in reg.landings.values() if v.get("kind") == UP_KIND}
    unit_of: dict[str, _t.Any] = {}
    n = 0
    for ref, (plan, y, units, air_z) in sorted(plans.items()):
        cand = []
        for k, B in sorted(union.items()):
            cover = B.intersection(plan).area
            if cover <= 0.0:
                continue
            if k not in unit_of:
                unit_of[k] = unit_share(B, airport, to_xy)[0]
            if unit_of[k] in units:
                cand.append((k not in upper, -cover, k))
        if not cand:
            why = f"{ref}: no held block of its unit"
            counts["kerb_frontage_refused"] = "; ".join(
                filter(None, (counts.get("kerb_frontage_refused"), why)))
            continue
        block = min(cand)[2]
        rec = {"lot": ref, "y": round(y, 3), "plan": plan, "air_z": air_z}
        reg.held[block] = {**reg.held[block],
                           LANDSIDE_KERB: (*reg.held[block].get(LANDSIDE_KERB, ()), rec)}
        n += 1
    taken = {u for _plan, _y, units, _z in plans.values() for u in units}
    k = 0
    for block, rec in (_unit_records(reg, taken, airport, law, union)
                       if law is not None else ()):
        reg.held[block] = {**reg.held[block],
                           LANDSIDE_KERB: (*reg.held[block].get(LANDSIDE_KERB, ()), rec)}
        k += 1
    counts["kerb_frontages"] = n
    if k:
        counts["unit_frontages"] = k
    return n + k
