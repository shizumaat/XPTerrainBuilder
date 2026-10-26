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
yielding_pin_rulings`` is held exactly, as every pin is, UNLESS IT IS IN
CONFLICT ITSELF: the stage is solved once with every such pin it may
release re-stated as a design TARGET at its own value; a pin that trial
moves past ``hard_tol_m`` — its own rows will not hold it — stays released
(the patch stays as near the ribbon as the law lets it), every other pin
is pinned again, and the stage is solved on that release
(:func:`yield_pins`).  Every released pin is REPORTED
(``DesignReport.pin_yield``: the ribbon's level, the patch's, the excess),
and the pipeline publishes the level the ribbon must take
(``emit/road_join.with_pin_yield`` → sidecar ``road_join_yield`` → the
core clamp's join pins).  A pin that holds never moves.

ITS OWN CONFLICT, NEVER ANOTHER ROW'S SETTLING (issue #778).  Until
2026-10-15 the yield ran only while the stage's hard set was UNSETTLED and
released the pins a flood from the unsettled rows reached: a join's fate
followed rows it never touched.  MEASURED (KCLT, PR #768 round 2): an
airside-only change settled more of the airside and stage 2 released 23
fewer joins — each of them held the patch road up to 2.24 m over the level
its own rows set — and groundside grew +101 ``hard_conflict``, +57
``road_cross_section``, +10 ``pavement_over_road_cap`` within 60 m of
them.  The flood (``implicated_pins``, ``own_rows``) is deleted with that
gate.

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
from ..law import Law
from ..law.tables import design as design_law
from ..model.planar import PlanarMap
from .api import Solution
from .design_report import DesignReport, row_metre_scale
from .design_roles import hard_rulings, ruling_head

__all__ = ["row_vertices", "hard_violated", "release_pins", "stage1_read_pins",
           "yield_pins"]

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


def yield_pins(planar: PlanarMap, cs: ConstraintSet, law: Law,
                sol: Solution, rep: DesignReport,
                solve: _t.Callable[[ConstraintSet],
                                   tuple[Solution, DesignReport]], *,
                among: _t.AbstractSet[int] | None = None
                ) -> tuple[Solution, DesignReport, list[dict], ConstraintSet]:
    """One §20b stage AGAIN with the yielding pins IN CONFLICT released —
    EACH PIN DECIDED BY ITS OWN CONFLICT (issue #778, this module's
    docstring), never by whether the stage's hard set happened to settle.

    THE TRIAL: every yielding pin this stage may release (``among``, issue
    #87) is re-stated as a design target at its own value
    (:func:`release_pins`) and the stage is solved once.  A pin the trial
    moves by more than ``hard_tol_m`` is FORCED — its own rows (hard, or
    the law rows priced at the target's own weight) will not hold it — and
    stays released; every other pin is PINNED AGAIN and the stage solved on
    that narrower release (skipped when every candidate is forced).  The
    release is kept unless it leaves the hard set worse than the pinned
    answer by the elevation materiality.  Returns the stage's solution and report, the release records (empty
    when no pin is in conflict) and the constraint set the kept solution
    solved."""
    d = design_law(law)
    yield_heads = frozenset(getattr(d, "yielding_pin_rulings", ()) or ())
    if not yield_heads or not sol.z:
        return sol, rep, [], cs
    cands = sorted({p.v for p in cs.pins if ruling_head(p) in yield_heads
                    and (among is None or p.v in among)})
    if not cands:
        return sol, rep, [], cs
    pinned = {p.v: float(p.z) for p in cs.pins if p.v in set(cands)}
    head_of = {p.v: ruling_head(p) for p in cs.pins if p.v in set(cands)}
    tol = float(d.hard_tol_m)
    mat = float(law.tables.emit.materiality.elevation_m)
    cs_t = release_pins(cs, cands, yield_heads)
    sol_t, rep_t = solve(cs_t)
    if not sol_t.z:
        return sol, rep, [], cs
    forced = [v for v in cands if abs(float(sol_t.z[v]) - pinned[v]) > tol]
    if not forced:
        return sol, rep, [], cs
    sol_y, rep_y, cs_y = sol_t, rep_t, cs_t
    if len(forced) < len(cands):
        cs_y = release_pins(cs, forced, yield_heads)
        sol_y, rep_y = solve(cs_y)
        if not sol_y.z:
            return sol, rep, [], cs
    if not rep_y.hard_settled and (
            rep_y.hard_max_violation_m - rep.hard_max_violation_m) >= mat:
        return sol, rep, [], cs
    recs = [{"v": int(v), "xy": tuple(float(c) for c in planar.vertices[v].xy),
             "pinned_m": round(pinned[v], 4),
             "z_m": round(float(sol_y.z[v]), 4),
             "excess_m": round(float(sol_y.z[v]) - pinned[v], 4),
             "ruling": head_of[v]}
            for v in forced]
    return sol_y, rep_y, recs, cs_y
