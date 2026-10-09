"""THE PAVEMENT GIVES BY THE FLOOR TO WELD TO A PAD — the rows a misfit pad's
frontage contacts are widened by, and nothing else.

Owner RULINGS 2026-10-08c (4) and 2026-10-08d (2): "There can't be a step
between pad and pavement" / "For large pads where there's a potential for a
step < 1m, allow the pavement (airside or groundside) to exceed it's cap to
weld to it."  Spec §57 (3) as amended by 08d (2).

WHICH BLOCK.  ``no_step.hold_interval`` reads, per held block, the set of
levels its frontage contacts can all take under the airside's own caps (the
pair-graph interval, met with the contacts' reach bands).  Where that set is
EMPTY the block has a MISFIT — half the gap, the least any one flat level
leaves its worst contact short by.  A misfit under the law's terrace floor
(``[terrace] pad_terrace_floor_m``, the ONE number §55's last stage widens
by) is welded by the pavement: the block's datum prefers the gap's middle
and every frontage weld stays hard.

WHICH ROWS — the minimal statement: a row of a PAVEMENT-tier head (the
``taxi`` and ``apron`` tiers of ``[design] hard_conflict_ranks`` — the law's
own list of the airside caps that rank above a pad's hold and below the
runway) that NAMES A FRONTAGE CONTACT of a misfit block and no
runway-family vertex.  Such a row's bound gives by the floor at that
contact: a ``Diff`` reads ``|dz| <= cap x d + floor`` (``cap + floor / d``,
§55 (5)'s own inequality), a ``Linear`` gives ``floor x |coefficient of the
contact|`` on each side.  A row that names no frontage contact is never
touched (this is not a loosening of the apron or taxi caps), a runway row
is never touched (a runway profile is not pavement welding to a pad), and
neither is a pad's own row (the weld stays hard).

The census reads the same thing back (``platforms[].weld_widened`` — the
floor and the contacts' coordinates; ``tools/check_grade.py``
``weld_widened_nodes``): one number, one site.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..law.tables import design as _design
from ..model.constraints import ConstraintSet, Diff, Linear

__all__ = ["PAVEMENT_TIERS", "pavement_heads", "widen_weld_rows", "ruling_note",
           "seat_misfit"]

#: The tiers of ``[design] hard_conflict_tiers`` whose rows are pavement
#: caps (owner 08d (2): "pavement (airside or groundside)"; the runway tier
#: is never pavement welding to a pad, the pad tier is the weld itself).
PAVEMENT_TIERS = ("taxi", "apron")

#: appended to a widened row's ruling text (after its head, which is kept:
#: the row stays in every register its head stands in)
ruling_note = " (widened by the terrace floor at a misfit pad's frontage contact, RULINGS 2026-10-08d (2))"


def seat_misfit(lo: float, hi: float, r_lo: float, r_hi: float,
                floor_m: float, tol_m: float) -> tuple[float, bool, float | None]:
    """THE SEAT'S VERDICT for one block: ``(misfit, welded by the pavement,
    its level)``.  ``[lo, hi]`` is the pair-graph interval of its frontage
    contacts, ``[r_lo, r_hi]`` the intersection of their reach bands; the
    ADMISSIBLE SET of one flat level is the two met.  Non-empty: no misfit.
    Empty: the misfit is half the gap (the least any one level leaves its
    worst contact short by) and the level that achieves it the gap's middle;
    it is welded by the pavement when over ``tol_m`` and UNDER ``floor_m``
    (owner RULINGS 2026-10-08d (2)).  At the floor or over, nothing is
    decided here (the owner's to rule): ``(misfit, False, None)``."""
    import math
    a_lo, a_hi = max(lo, r_lo), min(hi, r_hi)
    gap = a_lo - a_hi
    if not (gap > 0.0 and math.isfinite(gap)):
        return 0.0, False, None
    misfit = 0.5 * gap
    if tol_m < misfit < floor_m:
        return misfit, True, 0.5 * (a_lo + a_hi)
    return misfit, False, None


def pavement_heads(law: Law) -> frozenset[str]:
    """The ruling heads of the pavement tiers (:data:`PAVEMENT_TIERS`) of
    ``[design] hard_conflict_ranks``."""
    d = _design(law)
    return frozenset(h for tier, heads in zip(d.hard_conflict_tiers, d.hard_conflict_ranks)
                     if tier in PAVEMENT_TIERS for h in heads)


def _head(row) -> str:
    return str(row.source.ruling).split(" (")[0].strip()


def widen_weld_rows(cs: ConstraintSet, contacts: _t.AbstractSet[int], floor_m: float,
                    heads: _t.AbstractSet[str], never: _t.AbstractSet[int] = frozenset()
                    ) -> tuple[ConstraintSet, dict[int, dict]]:
    """``cs`` with every ``Diff`` / ``Linear`` row of a ``heads`` head that
    names a vertex of ``contacts`` — and none of ``never`` (the runway
    family) — widened by ``floor_m`` at that contact (module docstring);
    ``(set, {contact: {"rows", "runway_rows_kept"}})``.  ``cs`` itself when
    there is nothing to widen."""
    stats: dict[int, dict] = {}
    if not contacts or floor_m <= 0.0:
        return cs, stats

    def _count(vs, key: str) -> None:
        for v in vs:
            stats.setdefault(int(v), {"rows": 0, "runway_rows_kept": 0})[key] += 1

    out = []
    for r in cs.rows():
        if isinstance(r, Diff):
            hit = [v for v in (int(r.a), int(r.b)) if v in contacts]
            if hit and r.d > 0.0 and _head(r) in heads and ruling_note not in r.source.ruling:
                if int(r.a) in never or int(r.b) in never:
                    _count(hit, "runway_rows_kept")
                else:
                    r = _dc.replace(r, cap=r.cap + floor_m / r.d, source=_dc.replace(
                        r.source, ruling=r.source.ruling + ruling_note))
                    _count(hit, "rows")
        elif isinstance(r, Linear):
            hit = [(int(v), abs(float(c))) for v, c in r.terms if int(v) in contacts]
            if hit and _head(r) in heads and ruling_note not in r.source.ruling:
                if any(int(v) in never for v, _c in r.terms):
                    _count([v for v, _c in hit], "runway_rows_kept")
                else:
                    give = floor_m * max(c for _v, c in hit)
                    r = _dc.replace(
                        r, lo=None if r.lo is None else r.lo - give,
                        hi=None if r.hi is None else r.hi + give,
                        source=_dc.replace(r.source, ruling=r.source.ruling + ruling_note))
                    _count([v for v, _c in hit], "rows")
        out.append(r)
    if not stats:
        return cs, stats
    return ConstraintSet.from_rows(out), stats
