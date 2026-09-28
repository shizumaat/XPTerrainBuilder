"""THE PIN THAT YIELDS (owner RULINGS 2026-09-27a (10); issue #21, GEML).

§37 (9) pins a patch road at the CORE ribbon's level where its way leaves
the coverage.  At GEML the pack service road ``dsf:objpav5`` leaves it at
two stations the ribbon holds at 56.46 / 54.63 m, ~60 m across a parking
lot from an apron edge stage 1 solves 3.5 m under its DEM (50.84 m), and
the 5 % pavement ceiling (09-09b (4)) cannot bridge the two: 17 hard rows,
an infeasible set.  Three hard laws, one must give; the owner ruled that
the RIBBON yields — its 1.0 m deviation budget (§2-SUPPLEMENT S.3) is
exceeded so the join and the ceiling both hold.

THE MECHANISM, and its scope.  A ``Pin`` whose ruling head is in ``[design]
yielding_pin_rulings`` is held exactly, as every pin is, UNLESS stage 2's
hard set fails to settle with it.  Then only the yielding pins the UNSETTLED
hard rows reach — a flood over the hard rows (and rigid flats) through FREE
columns, stopped at every constant, within :data:`HOPS` hops — are
released: each becomes a design TARGET at its own value (the patch stays as
near the ribbon as the hard law lets it), stage 2 is solved again, and the
release is kept only if the hard set is better for it.  Every released pin
is REPORTED (``DesignReport.pin_yield``: the ribbon's level, the patch's,
the excess), and the pipeline publishes the level the ribbon must take
(``emit/road_join.with_pin_yield`` → sidecar ``road_join_yield`` → the
core clamp's join pins).  A pin that no unsettled row reaches never moves.

This module is the solve layer's: it reads rows and ruling heads only
(M0 §1 — no ``constraints`` import).
"""
from __future__ import annotations

import collections
import dataclasses as _dc
import typing as _t

import numpy as np

from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear,
                                 Offset, Pin, Row)
from .design_report import row_metre_scale
from .design_roles import ruling_head

__all__ = ["HOPS", "row_vertices", "hard_violated", "implicated_pins",
           "release_pins"]

#: The flood's reach, in hard-row hops from an unsettled row — the same
#: horizon the infeasibility certificate floods (``design_report
#: ._infeasible_set``'s ``limit``), so "the pin the unsettled set reaches"
#: means the same neighbourhood the certificate reads.
HOPS = 12


def row_vertices(r: Row) -> tuple[int, ...]:
    """Every vertex a row names."""
    if isinstance(r, (Pin, Band)):
        return (r.v,)
    if isinstance(r, (Diff, Offset)):
        return (r.a, r.b)
    if isinstance(r, Flat):
        return tuple(r.group)
    return tuple(v for v, _c in r.terms)


def _violation_m(r: Row, z: np.ndarray) -> float:
    """The row's violation at ``z`` in METRES of surface (``<= 0`` held)."""
    if isinstance(r, Diff):
        return (abs(float(z[r.a]) - float(z[r.b]) - float(r.rel))
                - r.cap * r.d)
    if isinstance(r, Band):
        v = float(z[r.v])
        out = -np.inf
        if r.lo is not None:
            out = max(out, r.lo - v)
        if r.hi is not None:
            out = max(out, v - r.hi)
        return float(out)
    if isinstance(r, Offset):
        return r.min_delta - (float(z[r.a]) - float(z[r.b]))
    if isinstance(r, Linear):
        s = sum(c * float(z[v]) for v, c in r.terms)
        out = -np.inf
        if r.hi is not None:
            out = max(out, s - r.hi)
        if r.lo is not None:
            out = max(out, r.lo - s)
        return float(out) * row_metre_scale(r.terms)
    return -np.inf


def hard_violated(cs: ConstraintSet, z: _t.Sequence[float],
                  hard_heads: _t.AbstractSet[str], tol: float) -> list[Row]:
    """The HARD rows (ruling head in ``hard_heads``) violated at ``z`` by
    more than ``tol`` metres."""
    zz = np.asarray(z, dtype=float)
    return [r for r in (*cs.diffs, *cs.bands, *cs.offsets, *cs.linears)
            if ruling_head(r) in hard_heads and _violation_m(r, zz) > tol]


def implicated_pins(cs: ConstraintSet, hard_heads: _t.AbstractSet[str],
                    yield_heads: _t.AbstractSet[str],
                    violated: _t.Sequence[Row],
                    fixed: _t.Mapping[int, float] | _t.AbstractSet[int],
                    hops: int = HOPS) -> list[int]:
    """The vertices of the YIELDING pins the unsettled rows reach: a
    breadth-first flood from every vertex of ``violated`` over the hard
    rows and the rigid flats, expanding only through FREE columns (a
    ``fixed`` vertex — stage 1's level — and every other pin stop it), for
    at most ``hops`` hops.  Sorted."""
    if not violated or not yield_heads:
        return []
    yield_v = {p.v for p in cs.pins if ruling_head(p) in yield_heads}
    if not yield_v:
        return []
    stop = set(fixed) | {p.v for p in cs.pins if p.v not in yield_v}
    touch: dict[int, list[Row]] = collections.defaultdict(list)
    for r in (*cs.diffs, *cs.bands, *cs.offsets, *cs.linears):
        if ruling_head(r) in hard_heads:
            for v in row_vertices(r):
                touch[v].append(r)
    for f in cs.flats:
        for v in f.group:
            touch[v].append(f)
    out: set[int] = set()
    seen: set[int] = set()
    frontier: list[int] = []
    for r in violated:
        for v in row_vertices(r):
            if v not in seen:
                seen.add(v)
                frontier.append(v)
    for _hop in range(hops + 1):
        nxt: list[int] = []
        for v in frontier:
            if v in yield_v:
                out.add(v)
                continue
            if v in stop:
                continue
            for r in touch.get(v, ()):
                for w in row_vertices(r):
                    if w not in seen:
                        seen.add(w)
                        nxt.append(w)
        if not nxt:
            break
        frontier = nxt
    return sorted(out)


def release_pins(cs: ConstraintSet, verts: _t.Iterable[int],
                 yield_heads: _t.AbstractSet[str]) -> ConstraintSet:
    """``cs`` with each yielding ``Pin`` on ``verts`` re-stated as a DESIGN
    TARGET at its own value (a one-vertex ``Linear`` equality with the same
    source, priced at ``[design] law`` like every law target)."""
    vs = set(verts)
    keep: list[Pin] = []
    targets: list[Linear] = []
    for p in cs.pins:
        if p.v in vs and ruling_head(p) in yield_heads:
            targets.append(Linear(((p.v, 1.0),), float(p.z), float(p.z),
                                  p.source))
        else:
            keep.append(p)
    return _dc.replace(cs, pins=tuple(keep),
                       linears=tuple(cs.linears) + tuple(targets))
