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

WHERE THE GIVE IS SPENT (spec §57 (3) (ii-b), replacing the depth-1 row
set of the first build): ONE over-cap GRADE ``delta_b`` per misfit block,
uniform over every pavement-tier row (the ``taxi`` and ``apron`` tiers of
``[design] hard_conflict_ranks``) whose vertices all lie in or on the
pavement FACES the block's closing contacts front (:func:`widen_face_rows`);
``delta_b`` is the LEAST value at which the block's admissible set, re-read
on the pair graph with those rows at ``cap + delta_b``, is non-empty
(:func:`least_allowance`, bisection).  MEASURED on the depth-1 build: the
whole give landed in the first row off the pad — HECA ``building147`` 11.58 %
over 7.8 m of 1.5 % apron — and the rest spilled into 62 new airside no-step
rows.  A runway row is never touched (a runway profile is not pavement
welding to a pad), and neither is a pad's own row (the weld stays hard).

THE CONTACTS THAT CLOSE THE SET (:func:`contact_gives`): a frontage contact
whose own interval excludes the level.  They name the faces; and a weld the
feasibility LP relaxed after the solve gives per contact
(:func:`widen_weld_rows`, below).

THE WELD IS SEALED, WITHIN A BOUND (:func:`seal_welds`; spec §57 (3)
(ii-c)).  The solve holds a hard row within its tolerance and cannot certify
more (``[design] polish_rounds_max``: the residual is the solve's, not the
law's), so a weld can stand a few centimetres off its datum.  A weld row
governs ONE contact against a datum column stage 1 has solved, so its
feasible set is a point and the projection onto it is an assignment — the
zone projection's own argument (RULINGS 2026-09-12ag).  Every weld off its
datum by more than the tolerance and at most ``[design] seal_max_m`` (the
measured residual class) takes the datum and is recorded with its move.  A
runway-family or pinned contact and a contact two blocks hold are left as
the solve gave them.

A WELD OFF BY MORE (:func:`welds_off`) — the feasibility LP relaxed it — is
NOT sealed: a post-solve assignment of decimetres moves the step one row
outward into rows nothing re-checks.  It is a misfit the pair graph did not
see: the pavement rows naming that contact give by what it is off
(:func:`widen_weld_rows`) and pass 1b is solved ONCE more; still off, the
solve's release and the warning stand.

The census reads the same thing back (``platforms[].weld_widened`` — the
floor and each contact's coordinates and give; ``tools/check_grade.py``
``weld_widened_nodes``): one number per contact, one site.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..law.tables import design as _design
from ..model.constraints import ConstraintSet, Diff, Linear

_INF = float("inf")

__all__ = ["PAVEMENT_TIERS", "pavement_heads", "widen_weld_rows", "ruling_note",
           "seat_misfit", "contact_gives", "seal_welds", "welds_off",
           "least_allowance", "widen_face_rows", "face_note"]

#: The tiers of ``[design] hard_conflict_tiers`` whose rows are pavement
#: caps (owner 08d (2): "pavement (airside or groundside)"; the runway tier
#: is never pavement welding to a pad, the pad tier is the weld itself).
PAVEMENT_TIERS = ("taxi", "apron")

#: appended to a widened row's ruling text (after its head, which is kept:
#: the row stays in every register its head stands in)
ruling_note = " (widened at a misfit pad's frontage contact by what it is short of the pad, RULINGS 2026-10-08d (2))"


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


def contact_gives(level: float, contacts: _t.Iterable[int],
                  lo: _t.Mapping[int, float], hi: _t.Mapping[int, float],
                  bands: _t.Mapping[int, tuple], tol_m: float) -> dict[int, float]:
    """THE CONTACTS THAT CLOSE THE SET and what each gives: ``{contact:
    shortfall + tol_m}`` for every contact whose own admissible interval —
    its pair-graph bounds ``lo`` / ``hi`` met with its reach band — excludes
    ``level``.  A contact that holds the level is absent."""
    out: dict[int, float] = {}
    for c in contacts:
        b = bands.get(c) or (None, None)
        c_lo = max(lo.get(c, -_INF), b[0] if b[0] is not None else -_INF)
        c_hi = min(hi.get(c, _INF), b[1] if b[1] is not None else _INF)
        short = max(c_lo - level, level - c_hi)
        if short > 0.0:
            out[int(c)] = float(short) + float(tol_m)
    return out


def seal_welds(welds: _t.Iterable[tuple[int, int, str]], levels: dict, z: _t.Any,
               max_m: float, tol_m: float, skip: _t.AbstractSet[int] = frozenset()
               ) -> dict[int, tuple[str, float]]:
    """THE WELD PROJECTION (module docstring): every ``(contact, datum
    column, block)`` of ``welds`` whose contact stands off its datum by more
    than ``tol_m`` and at most ``max_m`` (``[design] seal_max_m`` — the
    solver's residual class) takes the datum's level, in ``levels`` and in
    ``z``; ``{contact: (block, move)}``.  A contact of ``skip`` (a
    runway-family vertex, a pinned one), one held by two datum columns, or
    one whose column or datum stage 1 did not level is left alone — and so
    is one off by MORE than ``max_m`` (:func:`welds_off`)."""
    out: dict[int, tuple[str, float]] = {}
    for c, (pref, move) in _weld_moves(welds, levels, skip).items():
        if tol_m < abs(move) <= max_m + 1e-9:
            levels[c] = levels[c] + move
            if z is not None:
                z[c] = float(levels[c])
            out[c] = (pref, move)
    return out


def _weld_moves(welds, levels, skip) -> dict[int, tuple[str, float]]:
    """``{contact: (block, datum - contact)}`` over the welds a projection
    may read: one datum column, both levelled, not in ``skip``."""
    by_c: dict[int, set] = {}
    for c, dv, _p in welds:
        by_c.setdefault(int(c), set()).add(int(dv))
    out: dict[int, tuple[str, float]] = {}
    for c, dv, pref in welds:
        c, dv = int(c), int(dv)
        if c in skip or c in out or len(by_c[c]) != 1 or c not in levels or dv not in levels:
            continue
        out[c] = (pref, float(levels[dv]) - float(levels[c]))
    return out


def welds_off(welds: _t.Iterable[tuple[int, int, str]], levels: _t.Mapping,
              max_m: float, floor_m: float, tol_m: float,
              skip: _t.AbstractSet[int] = frozenset()) -> dict[int, float]:
    """THE WELDS THE SOLVE LEFT OFF BY MORE THAN THE SEAL'S BOUND and under
    the terrace floor — ``{contact: |off| + tol_m}``, the give of the
    pavement rows naming it (spec §57 (3) (ii-c)): a misfit the pair-graph
    read did not see (the feasibility LP is the finer judge).  It is never
    sealed; the caller widens by it and re-solves pass 1b ONCE."""
    return {c: abs(mv) + float(tol_m)
            for c, (_p, mv) in _weld_moves(welds, levels, skip).items()
            if max_m + 1e-9 < abs(mv) < floor_m}


#: appended to a row widened by its block's face allowance
face_note = " (over its cap by the one allowance of a misfit pad's fronted faces, RULINGS 2026-10-08d (2); spec §57 (3) (ii-b))"


def least_allowance(feasible: _t.Callable[[float], bool], hi: float,
                    steps: int = 8) -> float | None:
    """THE LEAST OVER-CAP GRADE that makes a block's admissible set non-empty
    (spec §57 (3) (ii-b)): bisection on ``feasible(delta)`` over ``(0, hi]``,
    ``steps`` reads after the one at ``hi``; ``None`` when even ``hi`` does
    not open the set.  The returned value is FEASIBLE (the upper end of the
    last bracket), within ``hi / 2**steps`` of the least."""
    if hi <= 0.0 or not feasible(hi):
        return None
    lo = 0.0
    for _ in range(int(steps)):
        mid = 0.5 * (lo + hi)
        if feasible(mid):
            hi = mid
        else:
            lo = mid
    return hi


def _span_m(terms, xy) -> tuple[float, float] | None:
    from .ceiling import _span
    try:
        return _span(terms, xy)
    except KeyError:
        return None


def widen_face_rows(cs: ConstraintSet,
                    faces: _t.Iterable[tuple[_t.AbstractSet[int], float]],
                    heads: _t.AbstractSet[str], never: _t.AbstractSet[int] = frozenset(),
                    xy: "_t.Mapping[int, tuple[float, float]] | None" = None
                    ) -> tuple[ConstraintSet, list[dict]]:
    """``cs`` with every pavement-tier row (``heads``) whose EVERY vertex lies
    in or on a misfit block's fronted faces — ``faces`` is ``(their vertices,
    delta)`` per block — stated at ``cap + delta``: ONE over-cap grade per
    block, uniform over the faces (spec §57 (3) (ii-b); the larger where two
    blocks' faces hold the row).  A ``Diff`` reads ``cap + delta``; a
    point-vs-interpolated-point ``Linear`` (``ceiling._span``) gives ``delta x
    span x head coefficient`` on each side, any other ``Linear`` is not a
    grade and is left.  A row naming a vertex of ``never`` (the runway
    family) is never widened; ``(set, [{"rows", "runway_rows_kept"}] per
    block)``.  ``cs`` itself when no row is widened; idempotent."""
    fs = [(frozenset(int(v) for v in vs), float(d)) for vs, d in faces]
    stats = [{"rows": 0, "runway_rows_kept": 0} for _ in fs]
    if not any(d > 0.0 and vs for vs, d in fs):
        return cs, stats
    out, changed = [], False
    for r in cs.rows():
        vs = ((int(r.a), int(r.b)) if isinstance(r, Diff) else
              tuple(int(v) for v, _c in r.terms) if isinstance(r, Linear) else ())
        hit = [k for k, (f, d) in enumerate(fs) if d > 0.0 and vs and all(v in f for v in vs)]
        if (hit and _head(r) in heads and face_note not in r.source.ruling
                and ruling_note not in r.source.ruling):
            if any(v in never for v in vs):
                for k in hit:
                    stats[k]["runway_rows_kept"] += 1
            else:
                delta = max(fs[k][1] for k in hit)
                src = _dc.replace(r.source, ruling=r.source.ruling + face_note)
                new = None
                if isinstance(r, Diff) and r.d > 0.0:
                    new = _dc.replace(r, cap=r.cap + delta, source=src)
                elif isinstance(r, Linear) and xy is not None:
                    sp = _span_m(r.terms, xy)
                    if sp is not None:
                        give = delta * sp[1] * abs(sp[0])
                        new = _dc.replace(r, lo=None if r.lo is None else r.lo - give,
                                          hi=None if r.hi is None else r.hi + give,
                                          source=src)
                if new is not None:
                    r, changed = new, True
                    for k in hit:
                        stats[k]["rows"] += 1
        out.append(r)
    if not changed:
        return cs, stats
    return ConstraintSet.from_rows(out), stats


def pavement_heads(law: Law) -> frozenset[str]:
    """The ruling heads of the pavement tiers (:data:`PAVEMENT_TIERS`) of
    ``[design] hard_conflict_ranks``."""
    d = _design(law)
    return frozenset(h for tier, heads in zip(d.hard_conflict_tiers, d.hard_conflict_ranks)
                     if tier in PAVEMENT_TIERS for h in heads)


def _head(row) -> str:
    return str(row.source.ruling).split(" (")[0].strip()


def widen_weld_rows(cs: ConstraintSet, gives: _t.Mapping[int, float],
                    heads: _t.AbstractSet[str], never: _t.AbstractSet[int] = frozenset()
                    ) -> tuple[ConstraintSet, dict[int, dict]]:
    """``cs`` with every ``Diff`` / ``Linear`` row of a ``heads`` head that
    names a contact of ``gives`` — and no vertex of ``never`` (the runway
    family) — widened by that contact's give (module docstring; the larger
    give where a row names two); ``(set, {contact: {"rows",
    "runway_rows_kept"}})``.  ``cs`` itself when no row is widened."""
    stats: dict[int, dict] = {}
    gives = {int(c): float(g) for c, g in gives.items() if g > 0.0}
    if not gives:
        return cs, stats

    def _count(vs, key: str) -> None:
        for v in vs:
            stats.setdefault(int(v), {"rows": 0, "runway_rows_kept": 0})[key] += 1

    out, changed = [], False
    for r in cs.rows():
        if isinstance(r, Diff):
            hit = [v for v in (int(r.a), int(r.b)) if v in gives]
            if hit and r.d > 0.0 and _head(r) in heads and ruling_note not in r.source.ruling:
                if int(r.a) in never or int(r.b) in never:
                    _count(hit, "runway_rows_kept")
                else:
                    give = max(gives[v] for v in hit)
                    r = _dc.replace(r, cap=r.cap + give / r.d, source=_dc.replace(
                        r.source, ruling=r.source.ruling + ruling_note))
                    _count(hit, "rows")
                    changed = True
        elif isinstance(r, Linear):
            hit = [(int(v), abs(float(c))) for v, c in r.terms if int(v) in gives]
            if hit and _head(r) in heads and ruling_note not in r.source.ruling:
                if any(int(v) in never for v, _c in r.terms):
                    _count([v for v, _c in hit], "runway_rows_kept")
                else:
                    give = max(gives[v] * c for v, c in hit)
                    r = _dc.replace(
                        r, lo=None if r.lo is None else r.lo - give,
                        hi=None if r.hi is None else r.hi + give,
                        source=_dc.replace(r.source, ruling=r.source.ruling + ruling_note))
                    _count([v for v, _c in hit], "rows")
                    changed = True
        out.append(r)
    if not changed:
        return cs, stats
    return ConstraintSet.from_rows(out), stats
