"""§5a FEASIBILITY BEFORE THE SOLVE — an infeasible hard set is NAMED, never
solved (flat-pad spec v2 §5a; owner RULINGS 2026-09-30be, ratified 30bf).

What minted the 30ba cliffs: the promoted hard set across ``dsf:objpav402``
was a conflict between LAWS (pad holds vs the apron cap vs runway Bands),
and the augmented Lagrangian paid the infeasible relief on the two
cheapest welded pairs (7.33 / 7.13 m).  So, in ``design._solve_stage``
after ``assemble`` and before the QP, the HARD rows alone go through the
existing elastic LP (``project._relax_lp``, HiGHS ``min Σ w·s``,
``A x − s ≤ b``, ``s ≥ 0``), EVERY hard row elastic.  A row whose relaxation exceeds ``hard_tol_m`` is a LAW CONFLICT:

  * THE HIERARCHY (``[design] hard_conflict_tiers`` / ``_ranks``): runway
    (pins, K, caps, flex Bands) > taxi caps > apron cap > pad hold /
    plateau.  The LP prices a tier's relaxation ``hard_conflict_tier_ratio``
    times its lower neighbour's, so the relaxation lands on the LOWEST tier
    a conflict contains (equal rank: the fewer rows — ``min Σ s``).  The
    runway tier is the dearest; a runway row still relaxed beyond
    ``hard_tol_m`` is a §7 STOP: NAMED (``runway_conflict``) and never
    demoted — it stays hard, and the runway machinery that already owns a
    runway's own infeasibility (the projection's elastic arm, the pin
    yield) acts on it as before (lane apronhard: raising here broke five
    standing twins of that machinery — a deviation from the brief's
    "raises", reported for the spec author).  (The
    runway tier was first held INELASTIC: measured at HECA pass 1b the LP
    then read Infeasible while the all-elastic read relaxed no runway row
    beyond ``hard_tol_m`` — a sub-tolerance runway residual, not a law
    conflict.)
  * THE RELAXED ROWS (``s_i > hard_tol_m``) — and only they — are demoted
    to priced (the law's target weight) for this solve; every other hard
    row stays hard.  Each is reported (``hard_conflict``): the row's law,
    the laws it conflicts with (the LP's dual SUPPORT in its connected
    component: the rows the relaxation leans on), its site and ``s_i``.

The DEM trend is never hard, so never in a conflict (30be).  Reads only
the assembled problem; prices nothing; edits no generator.
"""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

import numpy as np
import scipy.sparse as sp

from ..law import Law
from ..law.tables import design as design_law
from ..model.planar import PlanarMap
from .design_report import row_metre_scale
from .design_roles import ruling_head

__all__ = ["ConflictReport", "tier_of", "check_hard_set",
           "HARD_CONFLICT", "publish", "publish_stages", "demote_conflicts",
           "apron_hard_rows", "source_face", "published",
           "promote_missed", "runway_after"]

#: the SHIPPED surface's conflicts (the ``hard_conflict`` sidecar key):
#: set once per ``solve_design`` from its final stages, read by
#: ``pipeline/publication`` (the ``RUNWAY_FLEX`` pattern)
HARD_CONFLICT: list[dict[str, _t.Any]] = []


@_dc.dataclass
class ConflictReport:
    """One stage's feasibility check (§5a)."""

    rows: int = 0                      # hard rows the LP read (carrying a column)
    relaxed: int = 0                   # rows relaxed = the conflict count
    lp_wall_s: float = 0.0
    status: str = ""
    over_budget: bool = False
    by_head: dict = _dc.field(default_factory=dict)        # relaxed rows per head
    worst_by_head: dict = _dc.field(default_factory=dict)  # worst relaxation (m) per head
    by_tier: dict = _dc.field(default_factory=dict)        # relaxed rows per tier
    support_by_head: dict = _dc.field(default_factory=dict)  # opposing rows per head
    conflicts: list = _dc.field(default_factory=list)      # one record per relaxed row
    #: §7 STOP: RUNWAY rows the LP relaxed beyond ``hard_tol_m`` — never
    #: demoted (they stay hard; the runway projection / pin yield / elastic
    #: arm own a runway's infeasibility), named here and in the line
    runway_conflict: int = 0
    runway_rows: list = _dc.field(default_factory=list)
    runway_idx: list = _dc.field(default_factory=list)     # their ``one`` indices
    #: RULINGS 2026-09-30bj (1): the runway-conflict rows' worst residual
    #: AFTER the projection — > ``hard_tol_m`` is the §7 STOP, else a report
    runway_after_m: float = 0.0
    runway_stop: bool = False
    #: RULINGS 2026-09-30bj: priced strict body chords the solve missed,
    #: promoted to hard pair by pair before the multiplier rounds
    promoted_on_miss: int = 0

    def as_dict(self) -> dict[str, _t.Any]:
        return {"rows": self.rows, "relaxed": self.relaxed,
                "lp_wall_s": round(self.lp_wall_s, 3), "status": self.status,
                "over_budget": self.over_budget, "by_head": dict(self.by_head),
                "worst_by_head": {h: round(float(w), 4)
                                  for h, w in self.worst_by_head.items()},
                "by_tier": dict(self.by_tier),
                "support_by_head": dict(self.support_by_head),
                "runway_conflict": self.runway_conflict,
                "runway_rows": list(self.runway_rows),
                "runway_after_m": round(self.runway_after_m, 4),
                "runway_stop": self.runway_stop,
                "promoted_on_miss": self.promoted_on_miss}

    def by_head_line(self) -> str:
        """The relaxed rows BY HEAD, count and worst metre (spec §55 (5))."""
        return "; ".join(
            f"{h}: {n} (worst {self.worst_by_head.get(h, 0.0):.2f} m)"
            for h, n in sorted(self.by_head.items(), key=lambda kv: (-kv[1], kv[0]))) \
            or "none relaxed"

    def line(self) -> str:
        return (f"hard set feasibility (§5a): {self.rows} hard rows, LP "
                f"{self.lp_wall_s:.2f} s ({self.status})"
                + (" OVER BUDGET" if self.over_budget else "")
                + f", {self.relaxed} relaxed"
                + (f" {dict(sorted(self.by_tier.items()))}" if self.relaxed else "")
                + (f"; {self.runway_conflict} RUNWAY row(s) in a law conflict, "
                   f"kept hard: {self.runway_rows[:3]}" if self.runway_conflict else "")
                + (f"; {self.promoted_on_miss} missed body chord(s) promoted"
                   if self.promoted_on_miss else ""))


def tier_of(law: Law) -> dict[str, int]:
    """Ruling HEAD -> its tier index (0 = the runway, the highest)."""
    d = design_law(law)
    return {h: t for t, heads in enumerate(d.hard_conflict_ranks) for h in heads}


def _site(planar: PlanarMap, terms: _t.Sequence[tuple[int, float]]) -> list[float]:
    keys = [planar.vertices[int(v)].key for v, _c in terms
            if int(v) in planar.vertices]
    if not keys:
        return []
    return [round(sum(float(k[0]) for k in keys) / len(keys), 11),
            round(sum(float(k[1]) for k in keys) / len(keys), 11)]


def check_hard_set(planar: PlanarMap, law: Law, one: list, hard_i: np.ndarray,
                   A: sp.csr_matrix, b: np.ndarray, *, stage: str = "",
                   verbose: bool = False
                   ) -> tuple[np.ndarray, ConflictReport]:
    """The §5a check over the hard rows ``hard_i`` (indices into ``one``)
    of the stage's one-sided stack ``A x ≤ b`` (the FULL rows — leaders
    included, unscaled — over the reduced columns).  Returns the indices of
    ``one`` to DEMOTE (the relaxed rows, never a runway row) and the
    report."""
    from .project import _relax_lp
    d = design_law(law)
    rep = ConflictReport()
    tol = float(d.hard_tol_m)
    hard_i = np.asarray(hard_i, dtype=np.int64)
    if not hard_i.size:
        rep.status = "no hard rows"
        return np.zeros(0, dtype=np.int64), rep
    Ah = A[hard_i].tocsr()
    keep = np.asarray(abs(Ah).sum(axis=1)).ravel() > 0.0   # else a constant
    rows = hard_i[keep]
    Ah = Ah[keep]
    rep.rows = int(rows.size)
    if not rows.size:
        rep.status = "no hard row carries a column"
        return np.zeros(0, dtype=np.int64), rep
    sc = np.fromiter((row_metre_scale(one[int(k)][0]) for k in rows),
                     dtype=float, count=rows.size)
    Am = (sp.diags(sc) @ Ah).tocsr()
    bm = sc * np.asarray(b, float)[rows]
    tiers = tier_of(law)
    n_t = len(d.hard_conflict_tiers)
    heads = [ruling_head(one[int(k)][2]) for k in rows]
    # an unranked head cannot reach here (the schema refuses it); a row
    # promoted by a register the ranks do not know ranks with the pads
    t_row = np.array([tiers.get(h, n_t - 1) for h in heads], dtype=np.int64)
    ratio = float(d.hard_conflict_tier_ratio)
    # EVERY hard row elastic (§5a (a)), priced by its tier: the runway's
    # relaxation costs ``ratio`` times the taxi's, and so on down — a
    # runway row that still carries slack over ``hard_tol_m`` is a STOP
    cost = ratio ** (n_t - 1 - t_row).astype(float)
    duals: list = []
    t0 = time.perf_counter()
    s, st = _relax_lp(Am, bm, np.ones(rows.size, bool), verbose, cost=cost,
                      duals=duals, dual_form=True)
    rep.lp_wall_s = time.perf_counter() - t0
    rep.status = st
    rep.over_budget = rep.lp_wall_s > float(d.hard_conflict_lp_budget_s)
    if st != "optimal":                 # named, nothing demoted
        return np.zeros(0, dtype=np.int64), rep
    bad = np.flatnonzero((s > tol) & (t_row == 0))
    rep.runway_conflict = int(bad.size)
    rep.runway_rows = [f"{heads[i]} at {_site(planar, one[int(rows[i])][0])} "
                       f"s={s[i]:.3f} m" for i in bad[:8]]
    rep.runway_idx = [int(rows[i]) for i in bad]
    rel = np.flatnonzero((s > tol) & (t_row > 0))
    rep.relaxed = int(rel.size)
    if not rel.size:
        return np.zeros(0, dtype=np.int64), rep
    # THE CONFLICT'S SUPPORT: the rows the optimum leans on (non-zero dual)
    # plus the relaxed rows, grouped by shared columns — each relaxed row's
    # opposing laws are the support rows of its own component
    y = duals[0] if duals else np.zeros(rows.size)
    sup = np.flatnonzero((np.abs(y) > 1e-9) | (s > tol))
    sub = Am[sup]
    inc = sp.csr_matrix((np.ones(sub.nnz), sub.indices, sub.indptr),
                        shape=sub.shape)
    from scipy.sparse.csgraph import connected_components
    adj = (inc @ inc.T).tocsr()
    _nc, lab = connected_components(adj, directed=False)
    comp_of = {int(sup[j]): int(lab[j]) for j in range(sup.size)}
    by_comp: dict[int, dict[str, int]] = {}
    for j in range(sup.size):
        i = int(sup[j])
        if s[i] > tol:
            continue
        c = by_comp.setdefault(int(lab[j]), {})
        c[heads[i]] = c.get(heads[i], 0) + 1
        rep.support_by_head[heads[i]] = rep.support_by_head.get(heads[i], 0) + 1
    names_t = list(d.hard_conflict_tiers)
    for i in rel:
        i = int(i)
        k = int(rows[i])
        terms, _hi, row = one[k]
        h = heads[i]
        rep.by_head[h] = rep.by_head.get(h, 0) + 1
        rep.worst_by_head[h] = max(rep.worst_by_head.get(h, 0.0), float(s[i]))
        tn = names_t[int(t_row[i])]
        rep.by_tier[tn] = rep.by_tier.get(tn, 0) + 1
        against = by_comp.get(comp_of.get(i, -1), {})
        rep.conflicts.append({
            "row": h, "ruling": row.source.ruling[:120], "tier": tn,
            "against": dict(sorted(against.items(), key=lambda kv: -kv[1])[:6]),
            "site": _site(planar, terms), "s_m": round(float(s[i]), 4),
            "stage": stage,
            "vertices": [list(planar.vertices[int(v)].key) for v, _c in terms
                         if int(v) in planar.vertices][:4],
            "inputs": [str(t) for t in (row.source.inputs or ())][:3]})
    return rows[rel], rep


def publish(records: _t.Iterable[dict[str, _t.Any]]) -> None:
    """Set the shipped surface's ``hard_conflict`` records (sidecar key)."""
    HARD_CONFLICT[:] = [dict(r) for r in records]


def publish_stages(*reps: _t.Any, pass1a: "dict | None" = None,
                   law: Law | None = None) -> "dict | None":
    """Publish the SHIPPED surface's conflicts — the final stage 1's and
    stage 2's reports (pass 1a's stay in its own stage record) — and return
    the first report's ``as_dict`` (the stage-1 record).  With ``pass1a``
    (its record) and ``law``, every stage-1 LP is judged against §5a's
    budget, min(``hard_conflict_lp_budget_s``, ``_share`` x pass 1a's wall)
    (RULINGS 2026-09-30bj)."""
    feas = [getattr(r, "hard_feasibility", None) for r in reps]
    if pass1a is not None and law is not None:
        d = design_law(law)
        budget = min(float(d.hard_conflict_lp_budget_s),
                     float(d.hard_conflict_lp_budget_share) * float(pass1a.get("wall_s", 0.0)))
        pass1a["lp_budget_s"] = round(budget, 3)
        hf = pass1a.get("hard_feasibility") or {}
        if hf:
            hf["over_budget"] = float(hf.get("lp_wall_s", 0.0)) > budget
        if feas and feas[0] is not None:
            feas[0].over_budget = feas[0].lp_wall_s > budget
    publish([c for f in feas if f is not None for c in f.conflicts])
    return feas[0].as_dict() if feas and feas[0] is not None else None


def demote_conflicts(planar: PlanarMap, law: Law, base: _t.Any,
                     A: sp.csr_matrix, b: np.ndarray, rep: _t.Any, *,
                     stage: str = "", verbose: bool = False) -> None:
    """§5a in ``design._solve_stage`` after ``assemble``, before the QP:
    the hard rows alone (the FULL rows, leaders in — before the one-way
    split) through :func:`check_hard_set`; the relaxed rows leave
    ``base.hard`` (priced for this solve), the report lands in
    ``rep.hard_feasibility``."""
    if not base.hard:
        return
    demote, rep.hard_feasibility = check_hard_set(
        planar, law, base.one, np.asarray(base.hard, dtype=np.int64), A, b,
        stage=stage, verbose=verbose)
    if demote.size:
        gone = set(int(k) for k in demote)
        base.hard = [k for k in base.hard if k not in gone]
    f = rep.hard_feasibility
    if verbose or f.relaxed or f.over_budget or f.runway_conflict:
        print(f"    [design] {f.line()}")


def source_face(row: _t.Any) -> int | None:
    """The face id a row's ``Source`` cites (``face:<id>``), or ``None``."""
    for tag in getattr(row.source, "inputs", ()) or ():
        if isinstance(tag, str) and tag.startswith("face:"):
            try:
                return int(tag[5:])
            except ValueError:
                return None
    return None


def apron_hard_rows(planar: PlanarMap, law: Law) -> _t.Callable[[_t.Any], bool]:
    """§5 THE APRON CAP IS HARD EVERYWHERE (owner RULINGS 2026-09-30be /
    30bf): the apron-only heads are in ``hard_rulings``; a row whose head is
    in ``apron_hard_rulings`` (the role-agnostic ``plane_gradient``) is hard
    where its source face has a role in ``apron_hard_roles``.  Returns that
    predicate (``design.assemble``'s filter)."""
    d = design_law(law)
    heads = frozenset(d.apron_hard_rulings)
    roles = frozenset(d.apron_hard_roles)
    faces = frozenset(fid for fid, f in planar.faces.items()
                      if f.role in roles) if heads else frozenset()
    if not faces:
        return lambda row: False
    return lambda row: ruling_head(row) in heads and source_face(row) in faces


def published(sol: _t.Any, rep: _t.Any) -> tuple[_t.Any, _t.Any]:
    """The single solve's answer, its conflicts published (§5a)."""
    publish_stages(rep)
    return sol, rep


def _carries_a_column(red: _t.Any, terms: _t.Sequence[tuple[int, float]]) -> bool:
    """Does this law row have anything the solve can MOVE? (lane
    ``v2settle``, spec §20a.)

    The reduced row, not the raw terms: a foot on a fixed vertex (a ``Pin``,
    a threshold, a DEM fix, a §20b stage substitution) folds into the
    right-hand side, and two feet of one rigid ``Flat`` group share a
    column — so a ±1 pair over that group cancels to nothing.  Either way
    the row's residual is a CONSTANT of the surface: it can be reported,
    never enforced.  Same accumulation as :meth:`_Rows.add`, which is what
    decides whether the row reaches the matrix at all."""
    acc: dict[int, float] = {}
    for vid, coef in terms:
        col = int(red.col[vid])
        if col >= 0:
            acc[col] = acc.get(col, 0.0) + coef
    return any(c != 0.0 for c in acc.values())


def promote_missed(one: list, hard_i: np.ndarray, A: sp.csr_matrix, b: np.ndarray,
                   lead: "sp.csr_matrix | None", x: "np.ndarray | None", law: Law,
                   rep: _t.Any) -> tuple[np.ndarray, np.ndarray]:
    """RULINGS 2026-09-30bj (#149 disposition): the STRICT body chords are
    PRICED; a row of ``apron_promote_on_miss_rulings`` the solve's iterate
    ``x`` leaves violated beyond ``hard_tol_m`` (in its own metres) is
    promoted to HARD — exactly those pairs, never the family.  Returns
    their ``one`` indices and the per-row metre scale the caller applies
    (1 elsewhere); records the count in ``rep.hard_feasibility``."""
    d = design_law(law)
    heads = frozenset(d.apron_promote_on_miss_rulings)
    none = (np.zeros(0, dtype=np.int64), np.ones(A.shape[0]))
    if not heads or x is None:
        return none
    hard = set(int(k) for k in hard_i)
    cand = np.fromiter((k for k, (_t_, _h, row) in enumerate(one)
                        if k not in hard and ruling_head(row) in heads), dtype=np.int64)
    if not cand.size:
        return none
    raw = np.asarray(A[cand] @ x).ravel() - b[cand]
    if lead is not None:
        raw = raw + np.asarray(lead[cand] @ x).ravel()
    sc = np.fromiter((row_metre_scale(one[int(k)][0]) for k in cand), float, cand.size)
    rowsum = np.asarray(abs(A[cand]).sum(axis=1)).ravel()
    miss = cand[(raw * sc > float(d.hard_tol_m)) & (rowsum > 0.0)]
    f = getattr(rep, "hard_feasibility", None)
    if f is not None:
        f.promoted_on_miss = int(miss.size)
    out = np.ones(A.shape[0])
    if miss.size:
        out[miss] = 2.0 / np.asarray(abs(A[miss]).sum(axis=1)).ravel()
    return miss, out


def runway_after(rep: _t.Any, one: list, z: np.ndarray, law: Law) -> None:
    """RULINGS 2026-09-30bj (1): read the runway-conflict rows AFTER the
    projection — their worst residual in metres; over ``hard_tol_m`` it is
    the §7 STOP (flagged and printed, the runway machinery's own exit
    stands), at or under it a report."""
    f = getattr(rep, "hard_feasibility", None)
    if f is None or not f.runway_idx:
        return
    worst = 0.0
    for k in f.runway_idx:
        terms, hi, _row = one[int(k)]
        v = (sum(c * float(z[int(vid)]) for vid, c in terms) - float(hi)) * row_metre_scale(terms)
        worst = max(worst, v)
    f.runway_after_m = worst
    f.runway_stop = worst > float(design_law(law).hard_tol_m)
    if f.runway_stop:
        print(f"    [design] §7 STOP (RULINGS 2026-09-30bj (1)): {len(f.runway_idx)} "
              f"runway-conflict row(s) still {worst:.3f} m over after the projection")
