"""THE RUNWAY IS SOLVED FIRST (owner RULINGS 2026-11-02a (4), Q311, issue
#1742): "Mostly a, but runways (like at HECA) do sometimes bend a bit to
allow the whole taxi network to solve".

STAGE 0 is the runway family alone: its own columns, every row whose every
column is one of them (pins, chord, bending, crown, transverse, K,
longitudinal, mean slope), its own polish and projections — §20b's stage
split (``design_stage.stage_split``) over the runway-family vertices instead
of the airside's.  What it returns is the runway as its own laws and its
own ground trend shape it, with no neighbour pulling.

STAGE 1 then HOLDS every free runway column within ``[design]
runway_first_slack_m`` of its stage-0 value: ONE hard ``Band`` per vertex,
head :data:`HOLD_RULING`, ranked in the LAST tier of ``[design]
hard_conflict_ranks``.  So the neighbours fit to the runway, and the runway
bends only where the airside's hard set cannot otherwise be met: §5a
(``solve/feasibility``) relaxes the lowest-ranked rows of a conflict, and
the hold is the lowest of every row stage 1 carries (stage 1 carries no
groundside row), so exactly the hold rows the conflict needs are demoted
to priced for that solve — the bend the owner allows, where the network
asks for it.  The runway's own laws, and the flex budget a held pad's pull is
bounded by (flat-pad spec v2 §1, RULINGS 2026-09-30as), stay in the
runway tier above it.

MEASURED AND NOT KEPT (lane b1742b): a second yield to the PRICED pair
maxima (``interval_pair_rulings``, an elastic LP asking which holds the
taxi caps need relaxed) bent HECA 05C/23C 0.60 m and 05L/23R 0.51 m,
left the census within 0.3 % of the hard-only hold (22,987 vs 23,050
rows), sharpened 05L/23R's worst station grade change to 0.55 % and ran
the §5a LP over its budget; at EPWA it relaxed nothing.

Not a pin: the hold is a band, it yields to any airside hard law, and a
stage-0 value is never a constant of stage 1.

The layer may not import ``constraints`` (M0 §1); the stage-0 solve is the
caller's (``design.solve_design`` binds ``_solve_stage``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from ..law.tables import design as design_law
from ..model.constraints import Band, ConstraintSet, Source
from ..model.planar import PlanarMap
from .design_stage import stage_split
from .flex import runway_stage_roles
from .rows import _reduce

__all__ = ["HOLD_RULING", "GEN", "RunwayFirst"]

#: The ruling HEAD of the hold ``Band`` rows (``[design] hard_rulings`` and
#: the last tier of ``hard_conflict_ranks``).
HOLD_RULING = "rulesets.runway.first_hold"
GEN = "runway_first"

#: ``solve(planar, cs, drop, fixed, levelled_out) -> (Solution, report)``:
#: the caller's stage solve over the runway family's roles.
StageSolve = _t.Callable[[PlanarMap, ConstraintSet, frozenset, dict, dict],
                         tuple[_t.Any, _t.Any]]


def _runway_vertices(planar: PlanarMap, law: Law) -> dict[int, str]:
    """Every vertex of a runway-family face (rings and holes) -> the face's
    runway ref (a crossing's ``a+b`` ref as published)."""
    roles = runway_stage_roles(law)
    out: dict[int, str] = {}
    for f in planar.faces.values():
        if f.role not in roles:
            continue
        for ring in (f.ring, *f.holes):
            for v in planar.ring_vertices(ring):
                out.setdefault(v, f.ref)
    return out


def _stage_zero_split(planar: PlanarMap, cs: ConstraintSet, law: Law,
                     runway_v: frozenset[int]
                     ) -> tuple[frozenset[int], dict[int, float]]:
    """STAGE 0's split: §20b's (``stage_split`` over the runway vertices)
    AND every PINNED vertex of a rigid class with no runway vertex in it,
    fixed at its pin.  A neighbour's pin is the neighbour's law, never the
    runway's: kept as a constant, a taxi or pad pin pulled the runway
    through every row footed on it (the twin's stub pin moved stage 0
    1.6 m), and the runway was no longer solved alone."""
    drop, fixed = stage_split(planar, cs, law, runway_v)
    red = _reduce(planar, cs, {})
    runway_roots = {red.find(int(v)) for v in runway_v}
    out = dict(fixed)
    for vid in range(len(planar.vertices)):
        if vid in out or red.col[vid] >= 0 or vid in runway_v:
            continue
        if red.find(vid) not in runway_roots:
            out[vid] = float(red.value[vid])
    return frozenset(out), out


@_dc.dataclass
class RunwayFirst:
    """Stage 0 solved once (the first stage-1 pass's set: pass 1a when a
    pad is held, the only pass otherwise), then the hold stated on every
    stage-1 pass."""

    law: Law
    solve: StageSolve
    z0: dict[int, float] | None = None
    ref_of: dict[int, str] = _dc.field(default_factory=dict)
    report: dict = _dc.field(default_factory=dict)
    #: the map stage 0 was solved on (its vertex ids key ``z0``)
    planar: PlanarMap | None = None

    def held(self, planar: PlanarMap, cs: ConstraintSet) -> ConstraintSet:
        """``cs`` with the hold rows added (stage 0 solved on first use)."""
        if self.z0 is None:
            self._stage_zero(planar, cs)
        if not self.z0:
            return cs
        slack = float(design_law(self.law).runway_first_slack_m)
        src = Source(GEN, f"{HOLD_RULING} (owner RULINGS 2026-11-02a (4): the "
                     f"runway is solved first, held within {slack:.3f} m)", ())
        rows = [Band(v, z - slack, z + slack, src) for v, z in sorted(self.z0.items())]
        return ConstraintSet.from_rows(list(cs.rows()) + rows)

    def _stage_zero(self, planar: PlanarMap, cs: ConstraintSet) -> None:
        self.planar = planar
        self.ref_of = _runway_vertices(planar, self.law)
        if not self.ref_of:
            self.z0 = {}
            return
        drop, fixed = _stage_zero_split(planar, cs, self.law, frozenset(self.ref_of))
        lv: dict[int, float] = {}
        sol, rep = self.solve(planar, cs, drop, fixed, lv)
        self.z0 = {v: float(z) for v, z in lv.items() if v in self.ref_of}
        self.report = {"vertices": len(self.z0), "status": str(sol.status),
                       "hard_settled": bool(getattr(rep, "hard_settled", True)),
                       "hard_max_violation_m": round(float(
                           getattr(rep, "hard_max_violation_m", 0.0)), 6)}

    def bend(self, z1: _t.Mapping[int, float]) -> dict:
        """Per runway: how far stage 1 bent it off stage 0 — the worst
        ``z1 − z0`` (``z1`` keyed on stage 0's map), where, and how many
        vertices left the slack."""
        if not self.z0 or self.planar is None:
            return dict(self.report)
        d_law = design_law(self.law)
        slack = float(d_law.runway_first_slack_m)
        per: dict[str, dict] = {}
        for v, z in self.z0.items():
            if v not in z1:
                continue
            d = float(z1[v]) - z
            r = per.setdefault(self.ref_of.get(v, "?"),
                               {"vertices": 0, "over_slack": 0, "worst_m": 0.0,
                                "worst_at": None})
            r["vertices"] += 1
            if abs(d) > slack + float(d_law.hard_tol_m):
                r["over_slack"] += 1
            if abs(d) > abs(r["worst_m"]):
                r["worst_m"] = round(d, 4)
                r["worst_at"] = list(self.planar.vertices[v].key)
        return dict(self.report, slack_m=slack, runways=per)

