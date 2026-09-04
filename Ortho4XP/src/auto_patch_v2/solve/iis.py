"""IRREDUCIBLE INFEASIBLE SUBSYSTEM — the seeded deletion filter (solver
benchmark finding 4; RULINGS 2026-09-03g), run ONLY when the LP reports
infeasible, answering "who minted the contradiction" (plan §2, the R1.3
question) as ``(row, source)`` pairs.

Seeded: the structural rows (pins, flats, bands) are the seed; the
generators' row groups are added one at a time until the system turns
infeasible — the first such group is culpable together with what came
before — then QuickXplain (a divide-and-conquer deletion filter,
``O(k · log n)`` feasibility probes for a conflict of size ``k``) finds
a MINIMAL conflict inside that group, and again inside the context.

THE FAST PATH (lane v2relax, RULINGS 2026-09-04t(1) — the IIS is now on
the build path, inside ``emit.relaxation.iis_time_budget_s``): with
``highspy`` present, :func:`ray_candidates` solves the whole set ONCE
with presolve off and reads the DUAL RAY — the Farkas certificate — whose
support (rows, and the bands of the columns it leans on) is an
infeasible set a few dozen rows long; QuickXplain reduces it with tiny
scipy probes.  Measured HECA (1.8 M rows): the seeded filter alone took
73–126 s; the certificate LP 32 s + ~25 probes under a second.  The
seeded filter remains the path without ``highspy``, without a ray, and
``deadline`` (a ``time.perf_counter`` instant) raises
:class:`IISBudgetExceeded` on either path.

THE CACHED CERTIFICATE AND THE BOUNDED NEIGHBOURHOOD (lane v2hecalemd,
2026-09-05; RULINGS 05d "HECA IIS budget: cache the certificate").
Measured HECA (1.30 M rows, 23.8 k columns): the whole-model certificate
LP on the ENVELOPE-FREE set (the reach bands set aside, ``relax.
envelope_free``) costs 107 s cold with presolve off, 142 s with it on,
207 s with the hard model's own objective — the 120 s budget, twice —
while the same LP WITH the reach bands, over the columns the rows touch,
proves infeasibility in 3.0 s (the envelope makes the contradiction
shallow) and names the SITE: the band vertices and the runway row it
leans on.  So :class:`Certificate` keeps that HiGHS model alive across
the relaxation's rounds — the rows a round relaxes are FREED in place
(``changeRowsBounds``, the basis kept) and the next ray hot-starts in
0.1 s — and :func:`neighbourhood_certificate` solves the envelope-free
set only over the rows within a few HOPS of the seed vertices (a row is a
hop; all-pairs face rows make a whole ring one hop): HECA's round-1
certificate came out at 4 hops, 20 k rows, 0.2 s.  A sub-LP that is
infeasible is a certificate for the whole model (its rows are a subset),
so nothing is approximated; a neighbourhood that stays feasible through
the schedule falls back to the whole-model LP under the remaining budget.
"""
from __future__ import annotations

import time
import typing as _t

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

from ..model.constraints import Band, ConstraintSet, Diff, Flat, Linear, Offset, Pin, Row, Source
from ..model.planar import PlanarMap
from .api import Options, Weights
from .assemble import to_sparse

__all__ = ["IISBudgetExceeded", "Certificate", "RowIndex", "row_vertices", "ray_candidates",
           "neighbourhood_certificate", "diagnose", "feasible", "quickxplain",
           "HOP_SCHEDULE"]

#: The neighbourhood growth: hops tried in turn before the whole model
#: (HECA: 4 hops / 20 k rows / 0.2 s found it; 8 hops / 193 k rows cost
#: 14 s and 12 hops / 442 k rows 68 s without one — past 8 the whole
#: model is the cheaper question).
HOP_SCHEDULE: tuple[int, ...] = (1, 2, 3, 4, 6, 8)


def row_vertices(r: Row) -> tuple[int, ...]:
    """The vertices a row binds."""
    if isinstance(r, Pin):
        return (r.v,)
    if isinstance(r, (Diff, Offset)):
        return (r.a, r.b)
    if isinstance(r, Flat):
        return r.group
    if isinstance(r, Linear):
        return tuple(v for v, _c in r.terms)
    return (r.v,)


class RowIndex:
    """Vertex -> the rows touching it, over one row list (built once per
    set; 0.5 s at HECA's 674 k envelope-free rows)."""

    def __init__(self, rows: _t.Iterable[Row]):
        self.touch: dict[int, list[Row]] = {}
        for r in rows:
            for v in row_vertices(r):
                self.touch.setdefault(v, []).append(r)

    def neighbourhood(self, seed: _t.Iterable[int], hops: int,
                      exclude: _t.Container[int] = frozenset()
                      ) -> tuple[set[int], list[Row]]:
        """The vertices reached from ``seed`` in ``hops`` row-steps and
        every row touching them (``exclude``: ``id(row)`` set left out)."""
        V: set[int] = set(seed)
        R: dict[int, Row] = {}
        for _ in range(hops):
            for v in list(V):
                for r in self.touch.get(v, ()):
                    if id(r) not in exclude:
                        R.setdefault(id(r), r)
            for r in R.values():
                V.update(row_vertices(r))
        return V, list(R.values())


class Certificate:
    """ONE HiGHS feasibility model (presolve off, zero objective) over
    ``rows``, restricted to the columns they touch, whose dual ray is the
    Farkas certificate; kept alive so rows can be freed (:meth:`free`) and the
    next :meth:`ray` hot-starts from the basis (module docstring)."""

    def __init__(self, n: int, rows: _t.Iterable[Row]):
        import highspy
        cs = ConstraintSet.from_rows(rows)
        S = to_sparse(cs, n)
        self.S = S
        self.nub = S.A_ub.shape[0]
        A = sp.vstack([S.A_ub, S.A_eq], format="csc")
        used = np.nonzero(np.diff(A.indptr))[0]
        extra = np.array([b.v for b in cs.bands] + [p.v for p in cs.pins], int)
        self.used = np.unique(np.concatenate([used, extra])) if extra.size else used
        self.A = A[:, self.used]
        self.col_of = {int(c): j for j, c in enumerate(self.used)}
        self.bands = {b.v: b for b in cs.bands}
        self.row_of: dict[int, list[int]] = {}
        for k, r in enumerate(S.ub_rows):
            self.row_of.setdefault(id(r), []).append(k)
        for k, r in enumerate(S.eq_rows):
            self.row_of.setdefault(id(r), []).append(self.nub + k)
        inf = highspy.kHighsInf
        self.inf = inf
        h = highspy.Highs()
        h.silent()
        h.setOptionValue("presolve", "off")
        lp = highspy.HighsLp()
        lp.num_col_ = len(self.used)
        lp.num_row_ = self.A.shape[0]
        lp.col_cost_ = np.zeros(len(self.used))
        lp.col_lower_ = np.where(np.isfinite(S.lo[self.used]), S.lo[self.used], -inf)
        lp.col_upper_ = np.where(np.isfinite(S.hi[self.used]), S.hi[self.used], inf)
        lp.row_lower_ = np.concatenate([np.full(self.nub, -inf), S.b_eq])
        lp.row_upper_ = np.concatenate([S.b_ub, S.b_eq])
        lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
        lp.a_matrix_.start_ = self.A.indptr
        lp.a_matrix_.index_ = self.A.indices
        lp.a_matrix_.value_ = self.A.data
        h.passModel(lp)
        self.h = h
        self.rows = self.A.shape[0]
        self.cols = len(self.used)
        self.freed = 0

    def free(self, rows: _t.Iterable[Row]) -> int:
        """Withdraw ``rows`` from the model IN PLACE (bounds to ±inf; a
        ``Band`` frees its column) — the basis stays valid, so the next
        :meth:`ray` hot-starts.  Returns the LP rows freed."""
        idx: list[int] = []
        for r in rows:
            idx.extend(self.row_of.get(id(r), ()))
            if isinstance(r, Band) and r.v in self.col_of:
                self.h.changeColBounds(self.col_of[r.v], -self.inf, self.inf)
        if idx:
            a = np.asarray(sorted(set(idx)), dtype=np.int32)
            self.h.changeRowsBounds(len(a), a, np.full(len(a), -self.inf),
                                    np.full(len(a), self.inf))
        self.freed += len(idx)
        return len(idx)

    def ray(self, time_limit_s: float | None = None) -> list[Row] | None:
        """The Farkas support (rows, and the bands of the columns it leans
        on) — ``None`` when the model is feasible or no ray is reported;
        raises :class:`IISBudgetExceeded` on the time limit."""
        import highspy
        if time_limit_s is not None:
            self.h.setOptionValue("time_limit", float(max(1.0, time_limit_s)))
        self.h.run()
        st = self.h.getModelStatus()
        if st == highspy.HighsModelStatus.kTimeLimit:
            raise IISBudgetExceeded("the certificate LP hit the time limit")
        if st != highspy.HighsModelStatus.kInfeasible:
            return None
        got = self.h.getDualRay()
        if not (isinstance(got, tuple) and len(got) == 3 and got[1]):
            return None
        y = np.asarray(got[2], float)
        cand: dict[int, Row] = {}
        for k in np.nonzero(np.abs(y) > 1e-9)[0]:
            r = self.S.ub_rows[k] if k < self.nub else self.S.eq_rows[k - self.nub]
            cand.setdefault(id(r), r)
        w = np.abs(self.A.T @ y)
        for j in np.nonzero(w > 1e-9)[0]:
            v = int(self.used[j])
            b = self.bands.get(v)
            if b is not None:
                cand.setdefault(id(b), b)
        return list(cand.values())


def neighbourhood_certificate(n: int, index: RowIndex, seed: _t.Iterable[int], *,
                              deadline: float | None = None,
                              exclude: _t.Container[int] = frozenset(),
                              schedule: _t.Sequence[int] = HOP_SCHEDULE,
                              trace: dict | None = None) -> list[Row] | None:
    """The Farkas support of the first infeasible neighbourhood of
    ``seed`` along ``schedule`` (module docstring), or ``None`` when every
    neighbourhood in the schedule is feasible.  ``trace`` (a dict)
    receives ``hops`` / ``rows`` / ``wall_s`` of the LPs run."""
    seed = list(seed)
    if trace is not None:
        trace.setdefault("lps", [])
    for hops in schedule:
        remaining = None if deadline is None else deadline - time.perf_counter()
        if remaining is not None and remaining <= 0.0:
            raise IISBudgetExceeded("no budget left for the neighbourhood certificate")
        _V, rows = index.neighbourhood(seed, hops, exclude)
        if not rows:
            continue
        t = time.perf_counter()
        sup = Certificate(n, rows).ray(remaining)
        if trace is not None:
            trace["lps"].append({"hops": hops, "rows": len(rows),
                                 "wall_s": round(time.perf_counter() - t, 3),
                                 "infeasible": sup is not None})
        if sup:
            if trace is not None:
                trace["hops"] = hops
            return sup
    return None



class IISBudgetExceeded(RuntimeError):
    """The IIS search passed its wall budget."""


def feasible(n: int, rows: list[Row]) -> bool:
    """Is the subsystem ``rows`` feasible over ``n`` variables?  (A fresh
    scipy LP over the subset; the fast path is :func:`ray_candidates`.)"""
    if not rows:
        return True
    S = to_sparse(ConstraintSet.from_rows(rows), n)
    bounds = [(None if not np.isfinite(S.lo[i]) else float(S.lo[i]),
               None if not np.isfinite(S.hi[i]) else float(S.hi[i]))
              for i in range(n)]
    res = linprog(np.zeros(n), A_ub=S.A_ub if S.A_ub.shape[0] else None,
                  b_ub=S.b_ub if S.b_ub.shape[0] else None,
                  A_eq=S.A_eq if S.A_eq.shape[0] else None,
                  b_eq=S.b_eq if S.b_eq.shape[0] else None,
                  bounds=bounds, method="highs")
    return res.status != 2


def ray_candidates(n: int, cs: ConstraintSet, time_limit_s: float | None = None
                   ) -> list[Row] | None:
    """THE FARKAS CERTIFICATE of the whole set: the whole set as ONE HiGHS
    LP with presolve OFF (a reduced model carries no ray) and a zero
    objective; when it is infeasible the dual ray ``y`` names the rows in
    its support and, by ``Aᵀy``, the columns whose ``Band`` bounds it
    leans on — together an infeasible set a few dozen rows long (measured
    HECA: 23 rows + 2 bands from 1.8 M, 32 s; 3.0 s over the columns the
    rows touch) that QuickXplain reduces with tiny probes.  ``None`` when
    ``highspy`` is absent, the LP is feasible, or no ray is reported;
    raises :class:`IISBudgetExceeded` on the time limit."""
    try:
        import highspy  # noqa: F401
    except ImportError:
        return None
    return Certificate(n, cs.rows()).ray(time_limit_s)


def quickxplain(n: int, background: list[Row], cand: list[Row],
                probe: _t.Callable[[list[Row]], bool] | None = None) -> list[Row]:
    """A minimal subset of ``cand`` that is infeasible together with
    ``background`` (Junker 2004), assuming ``background + cand`` is
    infeasible and ``background`` alone is feasible.  ``probe(rows)``
    answers feasibility (default: :func:`feasible`)."""
    fz = probe or (lambda rows: feasible(n, rows))

    def qx(bg: list[Row], delta_nonempty: bool, c: list[Row]) -> list[Row]:
        if delta_nonempty and not fz(bg):
            return []
        if len(c) == 1:
            return list(c)
        k = len(c) // 2
        c1, c2 = c[:k], c[k:]
        d2 = qx(bg + c1, bool(c1), c2)
        d1 = qx(bg + d2, bool(d2), c1)
        return d1 + d2

    return qx(list(background), False, list(cand))


def _probe_for(n: int, cs: ConstraintSet, deadline: float | None
               ) -> _t.Callable[[list[Row]], bool]:
    def fz(rows: list[Row]) -> bool:
        if deadline is not None and time.perf_counter() > deadline:
            raise IISBudgetExceeded("scipy probes")
        return feasible(n, rows)

    return fz


def diagnose(planar: PlanarMap, cs: ConstraintSet, weights: Weights,
             options: Options, *, deadline: float | None = None,
             minimal: bool = True) -> tuple[tuple[Row, Source], ...]:
    """The IIS as ``(row, source)`` pairs; ``deadline`` (module docstring).
    ``minimal=False`` returns the Farkas SUPPORT as found — an infeasible
    subsystem, not reduced — which is what the last resort needs: its
    variance program gives a row in no conflict exactly zero slack, so
    the reduction buys nothing there, and a support that IS a 2,500-row
    chain (HECA 23C→05L along junction pav132's apron edge, 2026-09-05)
    costs QuickXplain O(k·log n) probes the IIS budget cannot pay."""
    n = len(planar.vertices)
    remaining = None if deadline is None else deadline - time.perf_counter()
    if remaining is not None and remaining <= 0.0:
        raise IISBudgetExceeded("no budget left before the certificate LP")
    cand = ray_candidates(n, cs, remaining)
    if cand and not feasible(n, cand):
        core = cand if not minimal else quickxplain(n, [], cand)
        return tuple((r, r.source) for r in core)
    fz = _probe_for(n, cs, deadline)
    seed: list[Row] = [*cs.pins, *cs.flats, *cs.bands]
    if not fz(seed):
        core = quickxplain(n, [], seed, fz)
        return tuple((r, r.source) for r in core)
    groups: dict[str, list[Row]] = {}
    for r in (*cs.diffs, *cs.offsets, *cs.linears):
        groups.setdefault(r.source.generator, []).append(r)
    keep = list(seed)
    for name in sorted(groups):
        rows = groups[name]
        if fz(keep + rows):
            keep += rows
            continue
        core = quickxplain(n, keep, rows, fz)
        ctx = quickxplain(n, core, keep, fz) if keep else []
        return tuple((r, r.source) for r in (*ctx, *core))
    return ()
