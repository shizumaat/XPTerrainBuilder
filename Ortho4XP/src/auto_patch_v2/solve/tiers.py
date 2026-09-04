"""THE LAW-ORDERED SOLVE (RULINGS 2026-09-04i, answering 03k: "the DEM is
not always reliable; a feasible solution exists for every airport; ALL
pavement must comply with the law and always overrides terrain when
needed; the LAW's priority order decides which governed surface yields").

One HARD solve; a SEARCH over the demotion depth only when it cannot:

1. **HARD.**  Every law row as the generators minted it — every governed
   pavement law row hard, the DEM only in the objective (M2) and in the
   seam / end-zone / crown preference groups (M3a).  OPTIMAL here means no
   surface yielded to any other: the shipped behaviour of the five
   zero airports, byte for byte.
2. **DEMOTE**, when 1 is infeasible.  ``demote(k_min)`` turns every row
   of every tier ``≥ k_min`` (``constraints.precedence.tiers``; tier 0 =
   the runway family) into a PREFERENCE with an unbounded slack, charged
   ``Weights.preference["law"] × ratio ** rank`` per metre of relief
   (``assemble.preference_weight``; rank 0 = the LOWEST tier, the
   ungoverned and rigid surfaces; ``ratio`` is ``Weights.tier_ratio``
   capped so the top stays under ``Weights.tier_top`` — HiGHS loses the
   solve past ~1e10 of objective range), so among the demoted tiers the
   relief lands on the most junior surfaces by preference.  Tier 0 is
   never demoted; nor are the structural equalities (``Flat``: a pad or
   a wall band is ONE value, movable as a whole) and the object ``Band``
   bounds.  Every DEM-derived pin off tier 0 (a wall crest, a basin rim,
   a mouth datum) is thereby a preference too, never a hard row — the
   DEM yields to every governed surface.
3. **THE DEPTH SEARCH.**  Feasibility is monotone in ``k_min`` (a deeper
   demotion relaxes a superset), so the LARGEST feasible ``k_min`` — the
   fewest tiers soft, every tier above them HARD — is found by bisection:
   the lowest tier alone first (the cheap, common case: measured KCLT,
   one DEM-derived structure row 1.97 m closes it), then the midpoints.
   A feasible attempt whose most senior yielding tier is ``ky > k_min``
   PROVES ``k_min = ky`` feasible with the same solution (every tier
   below ``ky`` held hard in it), so the search jumps there without a
   solve.  The result is exact at tier granularity — a surface is soft
   only when every tier junior to it could not close the contradiction —
   in ``≤ 1 + log2(tiers)`` solves, each carrying slacks for the demoted
   rows only (a full ladder over every row cost 524 s at KCLT; the
   search's first attempt there is a fraction).  ``k_min = 1`` infeasible
   ⇒ the IIS, which can only name hard↔hard contradictions inside tier 0
   (CIFP pins against the runway cap) or among the structural rows.

A row's TIER: a row minted for a face (``Source.inputs`` ``face:<id>``)
belongs to that face's role — an apron ring edge shared with a taxiway is
still the APRON's 1 % row and yields with the apron; any other row (a
no-step pair, a centreline chord, a zone band, a pin) belongs to the most
JUNIOR of its vertices, a vertex being owned by the most SENIOR surface
touching it (``precedence.vertex_tier``) — a runway↔taxi pair yields with
the taxiway, a strip band with the strip.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..constraints.precedence import tiers, vertex_tier, view
from ..law import Law
from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear,
                                 Offset, Pin, Row)
from ..model.planar import PlanarMap
from .api import Options, Solution, Status, Weights
from .highs import solve as solve_hard

__all__ = ["GROUP", "row_tier", "demote", "ladder_ratio", "TierReport",
           "solve_law_ordered"]

#: The preference-group prefix of a demoted law row: ``law:<rank>:<index>``.
GROUP = "law"


def row_tier(vw, row: Row, tier_of: _t.Mapping[str, int], lowest: int) -> int:
    """See the module docstring."""
    for inp in row.source.inputs:
        if inp.startswith("face:"):
            try:
                return tier_of[vw.pm.faces[int(inp[5:])].role]
            except (KeyError, ValueError):
                break
    if isinstance(row, Pin):
        vs: tuple[int, ...] = (row.v,)
    elif isinstance(row, (Diff, Offset)):
        vs = (row.a, row.b)
    elif isinstance(row, Linear):
        vs = tuple(v for v, _c in row.terms)
    elif isinstance(row, Flat):
        vs = row.group
    else:
        vs = (row.v,)
    return max((vertex_tier(vw, v, tier_of, lowest) for v in vs), default=lowest)


@_dc.dataclass(frozen=True)
class Demoted:
    """One row turned into a preference: its tier and the row it came from."""

    tier: int
    row: Row


def demote(planar: PlanarMap, law: Law, cs: ConstraintSet, k_min: int = 1
           ) -> tuple[ConstraintSet, dict[int, Demoted]]:
    """The tiered set: every ``Pin`` / ``Diff`` / ``Offset`` / ``Linear``
    of a tier ``≥ k_min`` becomes an unbounded preference row in group
    ``law:<rank>:<index>`` (rank 0 = the LOWEST tier); a row that is
    already a preference (seam, end zone, crown) keeps its own group;
    ``Flat`` and ``Band`` stay; tiers below ``k_min`` stay hard.  Returns
    the set and ``index -> Demoted`` for the yield report."""
    vw = view(planar, law)
    tt = tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    lowest = len(tt) - 1
    k_min = max(1, k_min)
    out: list[Row] = []
    demoted: dict[int, Demoted] = {}
    idx = 0
    for r in cs.rows():
        if isinstance(r, (Flat, Band)):
            out.append(r)
            continue
        if isinstance(r, (Diff, Linear)) and r.soft is not None:
            out.append(r)
            continue
        k = row_tier(vw, r, tier_of, lowest)
        if k < k_min:
            out.append(r)
            continue
        g = f"{GROUP}:{lowest - k}:{idx}"
        if isinstance(r, Pin):
            nr: Row = Linear(((r.v, 1.0),), r.z, r.z, r.source, g, None)
        elif isinstance(r, Offset):
            nr = Linear(((r.a, 1.0), (r.b, -1.0)), r.min_delta, None, r.source, g, None)
        else:
            nr = _dc.replace(r, soft=g, ceiling=None)
        out.append(nr)
        demoted[idx] = Demoted(k, r)
        idx += 1
    return ConstraintSet.from_rows(out), demoted


def ladder_ratio(weights: Weights, n_ranks: int) -> float:
    """``tier_ratio`` capped so ``law × ratio ** (n_ranks - 1) ≤ tier_top``."""
    base = float(weights.preference.get(GROUP, 1.0))
    if n_ranks <= 1 or base >= weights.tier_top:
        return 1.0
    return min(float(weights.tier_ratio),
               (weights.tier_top / base) ** (1.0 / (n_ranks - 1)))


@_dc.dataclass
class TierReport:
    """What the law-ordered solve did."""

    mode: str                                   # "hard" | "tiered"
    tiers: tuple[tuple[str, ...], ...]
    #: the most senior tier demoted (every tier from it down is soft)
    k_min: int | None = None
    demoted: int = 0
    #: per tier index: rows that yielded (> 1 mm), their max metres
    yielded: dict[int, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    ratio: float = 1.0
    wall_hard_s: float = 0.0
    #: the demotion attempts: ``(k_min, status, wall_s)``
    attempts: list[tuple[int, str, float]] = _dc.field(default_factory=list)

    def as_dict(self) -> dict[str, _t.Any]:
        return {"mode": self.mode, "tiers": [list(t) for t in self.tiers],
                "k_min": self.k_min, "demoted": self.demoted, "ratio": round(self.ratio, 4),
                "yielded": {str(k): v for k, v in sorted(self.yielded.items())},
                "wall_hard_s": round(self.wall_hard_s, 3),
                "attempts": [{"k_min": k, "status": st, "wall_s": round(w, 3)}
                             for k, st, w in self.attempts]}

    def line(self) -> str:
        if self.mode == "hard":
            return "law tiers: hard set feasible, no surface yielded"
        parts = [f"tier {k} {' '.join(self.tiers[k][:2])}{'…' if len(self.tiers[k]) > 2 else ''}: "
                 f"{v['rows']} rows, max {v['max_m']:.3f} m"
                 for k, v in sorted(self.yielded.items())]
        att = ", ".join(f"k_min {k} {st} {w:.1f} s" for k, st, w in self.attempts)
        return (f"law tiers: hard set INFEASIBLE; soft from tier {self.k_min} down "
                f"({self.demoted} rows, ratio {self.ratio:.3g}; {att}); "
                + ("; ".join(parts) if parts else "nothing yielded"))


def _yields(demoted: dict[int, Demoted], escalation: dict[str, float]
            ) -> dict[int, dict[str, _t.Any]]:
    acc: dict[int, dict[str, _t.Any]] = {}
    for g, e in escalation.items():
        if not g.startswith(GROUP + ":") or e <= 1e-9:
            continue
        i = int(g.rsplit(":", 1)[1])
        d = demoted.get(i)
        if d is None:
            continue
        metres = e * d.row.d if isinstance(d.row, Diff) else e
        if metres <= 1e-3:
            continue
        rec = acc.setdefault(d.tier, {"rows": 0, "max_m": 0.0, "by_generator": {}})
        rec["rows"] += 1
        rec["max_m"] = max(rec["max_m"], metres)
        gen = d.row.source.generator
        rec["by_generator"][gen] = rec["by_generator"].get(gen, 0) + 1
    for rec in acc.values():
        rec["max_m"] = round(rec["max_m"], 4)
    return acc


def _min_yield_tier(yielded: dict[int, dict[str, _t.Any]]) -> int | None:
    ks = [k for k, v in yielded.items() if v["rows"] > 0]
    return min(ks) if ks else None


def solve_law_ordered(planar: PlanarMap, cs: ConstraintSet, law: Law,
                      weights: Weights, options: Options | None = None, *,
                      size_out: dict | None = None
                      ) -> tuple[Solution, TierReport]:
    """Hard first; the depth search on infeasibility (module docstring)."""
    opt = options or Options()
    tt = tiers(law)
    quiet = _dc.replace(opt, diagnose_iis=False)
    sol = solve_hard(planar, cs, weights, quiet, size_out=size_out)
    rep = TierReport("hard", tt, wall_hard_s=sol.wall_s)
    if sol.status is not Status.INFEASIBLE:
        return sol, rep
    rep = TierReport("tiered", tt, wall_hard_s=sol.wall_s)
    lowest = len(tt) - 1
    best: tuple[int, Solution, dict, dict[int, Demoted]] | None = None

    def attempt(k_min: int) -> tuple[Solution, dict[int, Demoted], dict, float]:
        cs2, demoted = demote(planar, law, cs, k_min)
        ratio = ladder_ratio(weights, lowest - k_min + 1)
        size2: dict = {}
        s2 = solve_hard(planar, cs2, _dc.replace(weights, tier_ratio=ratio),
                        opt if k_min == 1 else quiet, size_out=size2)
        rep.attempts.append((k_min, s2.status.value, s2.wall_s))
        if s2.status is Status.ERROR and ratio > 1.0:
            # HiGHS "numerical difficulties" (measured HECA, k_min 4, ratio
            # 5.8): the same rows on a FLAT ladder — every demoted tier at
            # the base charge — still holds every senior tier hard, which
            # is the exact part; the ranking among the demoted tiers is
            # the part given up, and the report says so (ratio 1)
            ratio = 1.0
            size2 = {}
            s2 = solve_hard(planar, cs2, _dc.replace(weights, tier_ratio=1.0),
                            opt if k_min == 1 else quiet, size_out=size2)
            rep.attempts.append((k_min, s2.status.value + " (flat ladder)", s2.wall_s))
        return s2, demoted, size2, ratio

    lo, hi = 1, lowest                # lo: assumed feasible; hi: not yet refuted
    k = lowest                        # the lowest tier alone, first
    while True:
        s2, demoted, size2, ratio = attempt(k)
        if s2.status in (Status.OPTIMAL, Status.FEASIBLE):
            y = _yields(demoted, size2.get("escalation", {}))
            ky = _min_yield_tier(y)
            proven = k if ky is None else max(k, ky)
            if best is None or proven > best[0]:
                best = (proven, s2, size2, demoted)
                rep.k_min, rep.demoted, rep.ratio, rep.yielded = proven, len(demoted), ratio, y
            lo = proven
        elif s2.status is Status.INFEASIBLE:
            if k == 1:
                return s2, rep            # the IIS names tier 0 / structural rows
            hi = k - 1
        else:
            if best is None:
                return s2, rep            # backend error, nothing to fall back on
            break
        if lo >= hi:
            break
        k = (lo + hi + 1) // 2
    if best is None:                      # lo == 1 assumed, never solved
        s2, demoted, size2, ratio = attempt(1)
        if s2.status not in (Status.OPTIMAL, Status.FEASIBLE):
            return s2, rep
        y = _yields(demoted, size2.get("escalation", {}))
        best = (1, s2, size2, demoted)
        rep.k_min, rep.demoted, rep.ratio, rep.yielded = 1, len(demoted), ratio, y
    _k, sol, size2, demoted = best
    if size_out is not None:
        esc = size2.pop("escalation", {})
        size_out.update({f"tiered_{kk}": v for kk, v in size2.items()})
        size_out["escalation"] = {g: e for g, e in esc.items()
                                  if not g.startswith(GROUP + ":")}
    msg = sol.message.split("; preferences yielded")[0]
    return _dc.replace(sol, message=msg + "; " + rep.line()), rep
