"""THE RUNWAY'S FLEX AND THE HOLD'S TWO PASSES (flat-pad spec v2 §1 / §2,
owner RULINGS 2026-09-30y, 30as; issue #128) — split out of
``solve/design.py`` for its 1,500-line budget.

PASS 1a is §20b stage 1 with every frontage-hold row DROPPED: the runway's
UNPULLED profile (the one the sw1002 references carry).  Between the passes
the caller's ``hold`` binding (``constraints/no_step.HoldPass``: ``solve``
may not import ``constraints``, M0 §1) derives the pair-graph feasibility
interval of every held block, the runway's hard deviation budget and the
fronting set; PASS 1b is stage 1 again with the holds, the datum Bands and
the runway Bands, on the map the fronting set is published on.  No hold
row = pass 1a IS stage 1 and nothing else runs (byte-identical).
"""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

from ..law import Law
from ..model.constraints import ConstraintSet
from ..model.planar import PlanarMap
from .rows import _reduce

__all__ = ["runway_stage_roles", "runway_columns", "stage_one"]


def _held_at_ref(terms, hi: float, ref: _t.Mapping[int, float],
                 tol: float) -> bool:
    """Does the one-sided row ``Σ c z ≤ hi`` hold at ``ref`` within ``tol``
    metres (``2 / Σ|c|`` scaling)?  A foot ``ref`` lacks: no (RULINGS
    2026-09-30bb F2: a fronting cap is promoted only where pass 1a holds it)."""
    try:
        v = sum(c * float(ref[t]) for t, c in terms) - hi
    except KeyError:
        return False
    s = sum(abs(c) for _t, c in terms)
    return s <= 0.0 or v * 2.0 / s <= tol


def runway_stage_roles(law: Law) -> frozenset[str]:
    """The RUNWAY FAMILY's roles — ``precedence.toml``'s ``family =
    "runway"`` roles, one derivation from the law tables (flat-pad spec
    v2 §1 (4), kept from lane ``flatpad128v2``)."""
    from ..law.tables import role_family
    return frozenset(r for r in law.tables.precedence.roles
                     if role_family(law, r) == "runway")


def runway_columns(planar: PlanarMap, cs: ConstraintSet, law: Law
                   ) -> dict[int, int]:
    """THE RUNWAY'S COLUMNS (flat-pad spec v2 §1 (4)): every FREE vertex of
    a runway-family face, mapped to its reduced column — the set the flex
    budget's ``Band`` rows and the sidecar's ``runway_flex`` are keyed on.
    A vertex the reduction already fixed (a ``Pin``: threshold, seam, EAT)
    carries no column and is not listed — its Band would be moot.
    Vertices of one rigid ``Flat`` group share a column; each is listed (a
    Band on any of them bounds the column)."""
    red0 = _reduce(planar, cs, {})
    rw_roles = runway_stage_roles(law)
    out: dict[int, int] = {}
    for f in planar.faces.values():
        if f.role not in rw_roles:
            continue
        for ring in (f.ring, *f.holes):
            for v in planar.ring_vertices(ring):
                c = int(red0.col[v])
                if c >= 0:
                    out[v] = c
    return out


def stage_one(planar: PlanarMap, cs: ConstraintSet, law: Law, hold: _t.Any,
              solve1: _t.Callable[[PlanarMap, ConstraintSet], tuple]
              ) -> tuple[PlanarMap, ConstraintSet, tuple, "dict | None"]:
    """§20b STAGE 1 under the hold: ``(planar, cs, solve1's answer, pass-1a
    record)`` — the map and the problem stage 1 SOLVED (pass 1b's when a
    block is held) and ``solve1(planar, cs) -> (sol, rep, drop, foreign,
    levels, size)``'s answer for them.  The record (``stages["stage1a"]``)
    carries pass 1a's size, hard set and wall, the interval's wall and its
    statistics; ``None`` when no hold row exists."""
    cs1a = hold.strip(cs) if hold is not None else None
    t1 = time.perf_counter()
    got = solve1(planar, cs1a if cs1a is not None else cs)
    if cs1a is None:
        return planar, cs, got, None
    _sol, rep, _d, _f, levels, _sz = got
    w1a = time.perf_counter() - t1
    cs1b = hold.derive(cs1a, dict(levels), runway_columns(planar, cs1a, law))
    rec = {"unknowns": rep.unknowns, "rows": rep.rows, "hard_rows": rep.hard_rows,
           "hard_max_violation_m": round(rep.hard_max_violation_m, 6),
           "hard_settled": rep.hard_settled, "wall_s": round(w1a, 3),
           "interval_s": round(time.perf_counter() - t1 - w1a, 3),
           # §5a (RULINGS 2026-09-30be/30bf): pass 1a's own feasibility read
           "hard_feasibility": (rep.hard_feasibility.as_dict()
                                if getattr(rep, "hard_feasibility", None)
                                is not None else None)}
    if cs1b is None:
        return planar, cs1a, got, rec
    res = getattr(hold, "result", None)
    rec["interval"] = dict(getattr(res, "stats", None) or {})
    # §5: the fronting set is published on the map pass 1b solves
    fr = getattr(res, "fronting", None)
    if fr:
        planar = _dc.replace(planar, fronting_vertices=frozenset(fr),
                             fronting_ref=getattr(res, "fronting_ref", {}) or {})
    return planar, cs1b, solve1(planar, cs1b), rec
