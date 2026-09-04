"""THE LAW-ORDERED SOLVE (RULINGS 2026-09-04i, answering 03k: "the DEM is
not always reliable; a feasible solution exists for every airport; ALL
pavement must comply with the law and always overrides terrain when
needed; the LAW's priority order decides which governed surface yields").

One HARD solve; a LADDER solve and a TIGHTENING only when it cannot:

1. **HARD.**  Every law row as the generators minted it — every governed
   pavement law row hard, the DEM only in the objective (M2) and in the
   seam / end-zone / crown preference groups (M3a).  OPTIMAL here means no
   surface yielded to any other: the shipped behaviour of the five
   zero airports, byte for byte.
2. **LADDER**, when 1 is infeasible.  Every row of every tier but 0
   (``constraints.precedence.tiers``; tier 0 = the runway family) becomes
   a PREFERENCE with an unbounded slack, charged
   ``Weights.preference["law"] × ratio ** rank`` per metre of relief
   (``assemble.preference_weight``; rank 0 = the LOWEST tier, the
   ungoverned and rigid surfaces; ``ratio`` is ``Weights.tier_ratio``
   capped so the top stays under ``Weights.tier_top`` — HiGHS loses the
   solve past ~1e10 of objective range), so the relief lands on the most
   junior surfaces by preference.  Tier 0 is never demoted; nor are the
   structural equalities (``Flat``: a pad or a wall band is ONE value,
   movable as a whole) and the object ``Band`` bounds.  Every DEM-derived
   pin off tier 0 (a wall crest, a basin rim, a mouth datum) is thereby a
   preference too, never a hard row — the DEM yields to every governed
   surface.  Infeasible HERE ⇒ the IIS, which can only name hard↔hard
   contradictions inside tier 0 (CIFP pins against the runway cap) or
   among the structural rows.
3. **TIGHTEN.**  A weighted ladder is not lexicographic: a senior tier
   with few rows can be cheaper to bend than a junior tier with many.  So
   the most senior tier that yielded (> 1 mm) in step 2, and every tier
   above it, are re-HARDENED and the LP runs again; feasible ⇒ that
   solution stands (the senior surface truly held) and the tightening
   repeats one tier further down; infeasible ⇒ the previous solution
   stands (that tier had to yield).  At most one solve per tier; in
   practice one or two.  The result is exact at tier granularity: a
   surface is soft only when every tier junior to it could not close the
   contradiction.

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
    """Hard first; the ladder and the tightening on infeasibility
    (module docstring)."""
    opt = options or Options()
    tt = tiers(law)
    quiet = _dc.replace(opt, diagnose_iis=False)
    sol = solve_hard(planar, cs, weights, quiet, size_out=size_out)
    rep = TierReport("hard", tt, wall_hard_s=sol.wall_s)
    if sol.status is not Status.INFEASIBLE:
        return sol, rep
    rep = TierReport("tiered", tt, wall_hard_s=sol.wall_s)
    lowest = len(tt) - 1
    best: tuple[Solution, dict, dict[int, Demoted]] | None = None
    k_min = 1
    for _attempt in range(len(tt)):
        cs2, demoted = demote(planar, law, cs, k_min)
        ratio = ladder_ratio(weights, lowest - k_min + 1)
        w = _dc.replace(weights, tier_ratio=ratio)
        size2: dict = {}
        sol = solve_hard(planar, cs2, w, opt if best is None else quiet, size_out=size2)
        rep.attempts.append((k_min, sol.status.value, sol.wall_s))
        if sol.status not in (Status.OPTIMAL, Status.FEASIBLE):
            if best is None:
                return sol, rep       # the ladder itself failed: IIS / error
            break                     # the tightening failed: keep the last
        best = (sol, size2, demoted)
        rep.k_min, rep.demoted, rep.ratio = k_min, len(demoted), ratio
        rep.yielded = _yields(demoted, size2.get("escalation", {}))
        ky = _min_yield_tier(rep.yielded)
        if ky is None or ky >= lowest:
            break                     # nothing senior left to re-harden
        k_min = ky + 1                # re-harden that tier and every tier above
    assert best is not None
    sol, size2, demoted = best
    if size_out is not None:
        esc = size2.pop("escalation", {})
        size_out.update({f"tiered_{k}": v for k, v in size2.items()})
        size_out["escalation"] = {g: e for g, e in esc.items()
                                  if not g.startswith(GROUP + ":")}
    msg = sol.message.split("; preferences yielded")[0]
    return _dc.replace(sol, message=msg + "; " + rep.line()), rep
