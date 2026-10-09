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

__all__ = ["runway_stage_roles", "runway_columns", "stage_one", "yield_stage_one"]


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


def yield_stage_one(planar: PlanarMap, cs: ConstraintSet, law: Law, got: tuple,
                    solve1: _t.Callable[[PlanarMap, ConstraintSet], tuple]
                    ) -> tuple[ConstraintSet, tuple, list[dict]]:
    """THE PINS STAGE 1 READS YIELD IN STAGE 1 (issue #87): ``got`` (one
    ``solve1`` answer) re-solved with the yielding pins its unsettled hard
    rows reach released — ``(cs, got, release records)``, the input itself
    when nothing is released.  Decided from stage 1's own hard set, so
    nothing stage 2 carries can change the problem stage 1 solved."""
    from ..law.tables import design as design_law
    from .pin_yield import row_vertices, stage1_read_pins, yield_pins
    heads = frozenset(getattr(design_law(law), "yielding_pin_rulings", ()) or ())
    sol, rep, drop, foreign, _lv, _sz = got
    among = stage1_read_pins(cs, heads, drop) if heads else frozenset()
    if not (among and not rep.hard_settled and sol.z):
        return cs, got, []
    last: dict[int, tuple] = {}

    def _again(cs_x: ConstraintSet):
        out = solve1(planar, cs_x)
        last[id(out[1])] = out
        return out[0], out[1]
    _s, rep_y, recs, cs_y = yield_pins(
        planar, cs, law, sol, rep, foreign, _again, among=among,
        keep_row=lambda r: not any(v in drop for v in row_vertices(r)))
    if not recs:
        return cs, got, []
    for r in recs:
        r["stage"] = 1
    return cs_y, last[id(rep_y)], recs


def stage_one(planar: PlanarMap, cs: ConstraintSet, law: Law, hold: _t.Any,
              solve1: _t.Callable[[PlanarMap, ConstraintSet], tuple]
              ) -> tuple[PlanarMap, ConstraintSet, tuple, "dict | None", list[dict]]:
    """§20b STAGE 1 under the hold: ``(planar, cs, solve1's answer, pass-1a
    record, pin releases)`` — the map and the problem stage 1 SOLVED (pass
    1b's when a block is held), ``solve1(planar, cs) -> (sol, rep, drop,
    foreign, levels, size)``'s answer for them and the issue #87 releases
    (:func:`yield_stage_one`) both passes kept.  The record
    (``stages["stage1a"]``) carries pass 1a's size, hard set and wall, the
    interval's wall and its statistics; ``None`` when no hold row exists.

    PASS 1a IS TODAY'S STAGE 1 — ITS PIN YIELD INCLUDED (lane
    ``rwyband128``, issue #128): the runway Bands are centred on pass 1a's
    levelled values, so a pass 1a read BEFORE the yield centred them on a
    profile the shipped stage 1 never carries (HECA 05L/23R: a released
    pin dropped the runway 3.2 m at 30.13103, 31.39586 — pass 1b then held
    it within β of the UN-yielded 64.55 m, 3.47 m off sw1002's 61.17)."""
    cs1a = hold.strip(cs) if hold is not None else None
    t1 = time.perf_counter()
    if cs1a is None:
        cs, got, y1 = yield_stage_one(planar, cs, law, solve1(planar, cs), solve1)
        return planar, cs, got, None, y1
    cs1a, got, y1 = yield_stage_one(planar, cs1a, law, solve1(planar, cs1a), solve1)
    _sol, rep, _d, _f, levels, _sz = got
    w1a = time.perf_counter() - t1
    cs1b = hold.derive(cs1a, dict(levels), runway_columns(planar, cs1a, law))
    rec = {"unknowns": rep.unknowns, "rows": rep.rows, "hard_rows": rep.hard_rows,
           "hard_max_violation_m": round(rep.hard_max_violation_m, 6),
           **rep.settle_record(), "wall_s": round(w1a, 3),
           "pins_yielded": len(y1),
           "interval_s": round(time.perf_counter() - t1 - w1a, 3),
           # §5a (RULINGS 2026-09-30be/30bf): pass 1a's own feasibility read
           "hard_feasibility": (rep.hard_feasibility.as_dict()
                                if getattr(rep, "hard_feasibility", None)
                                is not None else None)}
    if cs1b is None:
        return planar, cs1a, got, rec, y1
    res = getattr(hold, "result", None)
    rec["interval"] = dict(getattr(res, "stats", None) or {})
    # §5: the fronting set is published on the map pass 1b solves
    fr = getattr(res, "fronting", None)
    if fr:
        planar = _dc.replace(planar, fronting_vertices=frozenset(fr),
                             fronting_ref=getattr(res, "fronting_ref", {}) or {})
    cs1b, got, y1b = yield_stage_one(planar, cs1b, law, solve1(planar, cs1b), solve1)
    return planar, cs1b, got, rec, y1 + y1b
