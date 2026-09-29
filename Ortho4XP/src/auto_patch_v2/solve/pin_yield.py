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
release is kept only if the hard set is better for it — settled, a worst
row lower by at least the elevation materiality, or the released pins' OWN
rows (:func:`own_rows`) held (issue #89: a sub-materiality change of a far
worst row is solver noise and keeps nothing).  Every released pin
is REPORTED (``DesignReport.pin_yield``: the ribbon's level, the patch's,
the excess), and the pipeline publishes the level the ribbon must take
(``emit/road_join.with_pin_yield`` → sidecar ``road_join_yield`` → the
core clamp's join pins).  A pin that no unsettled row reaches never moves.

WHICH STAGE DECIDES (issue #87; spec-author decision 2026-09-29, RULINGS
2026-09-29d (c)): a yielding pin that a STAGE-1 row reads — a row §20b
stage 1 keeps (no foreign vertex) that couples the pin to a stage-1 column
(:func:`stage1_read_pins`) — is a STAGE-1 FACT.  Stage 1 solved the airside
against its value, so only stage 1's own hard set may release it; stage 2
treats it as the constant stage 1 read, and the flood stops on it
(``implicated_pins(among=...)``).  "Airside is king": nothing stage 2
carries (a pad, a platform, a lot) can change the problem stage 1 solved.
MEASURED before the change (HECA, capture ``unitplatform2b``): the join at
30.13578, 31.41074 (``apron``/``service_road``, v11381-v11384) was held at
the ribbon's 72.138 m with the platform off and released to 71.853 m
(-0.285 m) with it on, because the platform's rows made stage 2's hard set
unsettled — a stage-2 fact moving a vertex stage 1 had read.

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
           "own_rows", "release_pins", "stage1_read_pins"]

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
                    hops: int = HOPS,
                    among: _t.AbstractSet[int] | None = None) -> list[int]:
    """The vertices of the YIELDING pins the unsettled rows reach: a
    breadth-first flood from every vertex of ``violated`` over the hard
    rows and the rigid flats, expanding only through FREE columns (a
    ``fixed`` vertex — stage 1's level — and every other pin stop it), for
    at most ``hops`` hops.  ``among`` (issue #87): only the yielding pins on
    these vertices may be released; any other is a constant that stops
    the flood like every pin.  Sorted."""
    if not violated or not yield_heads:
        return []
    yield_v = {p.v for p in cs.pins if ruling_head(p) in yield_heads}
    if among is not None:
        yield_v &= set(among)
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


def own_rows(cs: ConstraintSet, hard_heads: _t.AbstractSet[str],
             violated: _t.Sequence[Row], pins: _t.Iterable[int],
             fixed: _t.Mapping[int, float] | _t.AbstractSet[int],
             hops: int = HOPS) -> list[Row]:
    """The released pins' OWN rows (issue #89): the rows of ``violated``
    whose flood (:func:`implicated_pins`) reaches one of ``pins`` — the
    same flood run BACKWARD from the pins over the hard rows and rigid
    flats, expanding only through free columns (a ``fixed`` vertex and
    every other pin stop it), within ``hops`` hops.  These are the rows a
    release answers; the keep test judges the release on them, not on a
    global worst row the release never reached."""
    pv = set(pins)
    if not pv or not violated:
        return []
    by_v: dict[int, list[int]] = collections.defaultdict(list)
    for i, r in enumerate(violated):
        for v in row_vertices(r):
            by_v[v].append(i)
    stop = set(fixed) | {p.v for p in cs.pins if p.v not in pv}
    touch: dict[int, list[Row]] = collections.defaultdict(list)
    for r in (*cs.diffs, *cs.bands, *cs.offsets, *cs.linears):
        if ruling_head(r) in hard_heads:
            for v in row_vertices(r):
                touch[v].append(r)
    for f in cs.flats:
        for v in f.group:
            touch[v].append(f)
    hit: set[int] = set()
    seen = set(pv)
    frontier = sorted(pv)
    for _hop in range(hops + 1):
        nxt: list[int] = []
        for v in frontier:
            hit.update(by_v.get(v, ()))
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
    return [violated[i] for i in sorted(hit)]


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


def stage1_read_pins(cs: ConstraintSet, yield_heads: _t.AbstractSet[str],
                     drop: _t.AbstractSet[int]) -> frozenset[int]:
    """The vertices of the YIELDING pins §20b stage 1 READS (issue #87):
    each is named by a row stage 1 keeps — no vertex of it in ``drop``
    (stage 1's foreign set, :func:`solve.design.stage_split`) — together
    with at least one vertex that is not itself a pin (a stage-1 column).
    Stage 1 solved against such a pin's value; only stage 1's hard set may
    release it."""
    yield_v = {p.v for p in cs.pins if ruling_head(p) in yield_heads}
    if not yield_v:
        return frozenset()
    pinned = {p.v for p in cs.pins}
    drop_s = set(drop)
    out: set[int] = set()
    for r in (*cs.diffs, *cs.bands, *cs.offsets, *cs.linears, *cs.flats):
        vs = row_vertices(r)
        hit = [v for v in vs if v in yield_v]
        if not hit or any(v in drop_s for v in vs):
            continue
        if any(v not in pinned for v in vs):
            out.update(hit)
    return frozenset(out)
