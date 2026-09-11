"""THE DESIGN REPORT — what the design surface's one solve says it did.

Split out of ``solve/design.py`` under the 1,000-line law (the same move
``airport/obj8_clip.py`` made for ``obj8.py``): the report is a pure
record and its rendering, with no algebra, so it reads and reviews on its
own.  ``solve.design`` re-exports :class:`DesignReport`, which is the name
every caller uses.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from ..model.constraints import ConstraintSet
from .api import Residual
from .project import ProjectionReport
from .linear import DEFAULT_METHOD

__all__ = ["DesignReport", "residual"]


# ── the report ──────────────────────────────────────────────────────────

@_dc.dataclass
class DesignReport:
    """The residual per family and per objective term — what ``law_tiers``
    used to be, read the design surface's way: a law is a TARGET, so a
    missed target is a residual, never a demotion."""

    rounds: int = 0
    converged: bool = False
    method: str = DEFAULT_METHOD
    unknowns: int = 0
    fixed: int = 0
    rows: int = 0
    triangles: int = 0
    components: int = 0
    detached: int = 0
    #: THE PER-BODY DATUM (RULINGS 2026-09-09p (3); the AFFINE fit of
    #: 2026-09-10t (1) / 10v (2)): THREE rows per APRON BODY — its mean and
    #: its two first moments against the same moments of the DEM under its
    #: own vertices, i.e. its plane follows the ground's plane
    body_datum_rows: int = 0
    #: how many BODIES those rows cover (three rows each where the geometry
    #: carries all three; a collinear body fewer)
    body_datum_bodies: int = 0
    #: one record per datum BODY — ``kind``, the body's ``ll`` identity, how
    #: many vertices its plane is fitted over, the MEAN DEM under it, and
    #: the solved PLANE RESIDUAL: ``residual_m`` (its mean against the DEM
    #: mean) and ``tilt_m`` (the worst of the two moment rows, read as
    #: metres of rise over the body's own RMS half-extent)
    body_datums: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    #: THE TAXI CHAIN TREND (owner RULINGS 2026-09-10v (1); spec §8.6):
    #: per chain the built surface against its published target profile
    #: (RMS and max) and its mean z − DEM — filled by the pipeline after
    #: the projection (``constraints/taxi_trend.taxi_trend_block``)
    taxi_trend: dict[str, _t.Any] = _dc.field(default_factory=dict)
    #: how many vertices carry a trend target row
    taxi_trend_rows: int = 0
    #: THE APRON BODY'S 2-D TREND (owner RULINGS 2026-09-10ar; spec §8.7):
    #: per body carrying a 2-D trend, the built surface against its
    #: published target (RMS and max) and its mean z − DEM — filled by the
    #: pipeline after the projection
    #: (``constraints/apron_trend.apron_trend_block``)
    apron_trend: dict[str, _t.Any] = _dc.field(default_factory=dict)
    #: how many apron vertices carry a 2-D trend row (such a body carries
    #: NO affine ``body_datum`` rows)
    apron_trend_rows: int = 0
    #: THE GROUND'S OWN DATUM (owner RULINGS 2026-09-10av; spec §23): how
    #: many ADJACENT-GROUND vertices carry the weak ``z = DEM`` row — the
    #: ``graded_strip`` family minus the pavement vertices and minus the
    #: interior pockets enclosed by pavement (09g (1))
    ground_datum_rows: int = 0
    #: law rows whose one foot is the terrain beyond the zone's outer ring:
    #: the BANK (08t answers 2/3) — reported, never a design target
    bank_rows: int = 0
    #: THE HARD ROWS (RULINGS 2026-09-08v): the runway family's law rows as
    #: constraints — how many exist, how many the settled active set holds,
    #: how many polish rounds it took and the worst violation left (a
    #: constraint held exactly reads 0 to the solver's tolerance)
    hard_rows: int = 0
    hard_active: int = 0
    hard_rounds: int = 0
    hard_max_violation_m: float = 0.0
    hard_settled: bool = True
    #: the ruling of the worst-held hard row (empty where every row is held)
    hard_worst: str = ""
    #: THE FINAL PROJECTION (owner RULINGS 2026-09-09y): the runway family's
    #: hard rows held EXACTLY by a QP after the solve (``solve/project.py``)
    runway_projection: ProjectionReport = _dc.field(default_factory=ProjectionReport)
    #: THE ONE-WAY ROWS (RULINGS 2026-09-09b (2)/(3)): the adjacent-ground
    #: corridor and strip-tie rows whose pavement feet are LAGGED — how
    #: many, how many lag rounds the outer loop paid, whether the lag
    #: settled and how far the worst leader foot moved in the last round
    one_way_rows: int = 0
    one_way_rounds: int = 0
    one_way_settled: bool = True
    one_way_move_m: float = 0.0
    bend_rows_by_class: dict[str, int] = _dc.field(default_factory=dict)
    #: THE MISSED TARGETS (sidecar ``design_target``, RULINGS 2026-09-08t/v):
    #: one record per law row the design surface did not reach — its family,
    #: the metres it is out by and the lat/lon identities of its vertices, so
    #: the census can report the rows it counts under one heading
    targets: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    solver_wall_s: float = 0.0
    #: THE RUNWAY PROFILE (spec §21.2 (4)): per runway the target kind and
    #: window, the built ridge's residual against its target, its mean
    #: |z - DEM| and the law row that holds it — filled by the pipeline
    #: after the projection (``pipeline/runway_report.runway_profile_block``), and
    #: carried into the sidecar's ``design`` block so the census and the
    #: owner read WHICH target the runway was designed to.
    runway_profile: dict[str, _t.Any] = _dc.field(default_factory=dict)
    families: dict[str, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    terms: dict[str, float] = _dc.field(default_factory=dict)

    def as_dict(self) -> dict[str, _t.Any]:
        return {"rounds": self.rounds, "converged": self.converged,
                "method": self.method, "unknowns": self.unknowns,
                "fixed": self.fixed, "rows": self.rows,
                "triangles": self.triangles, "components": self.components,
                "detached": self.detached,
                "body_datum_rows": self.body_datum_rows,
                "body_datum_bodies": self.body_datum_bodies,
                "body_datums": self.body_datums,
                "taxi_trend": self.taxi_trend,
                "taxi_trend_rows": self.taxi_trend_rows,
                "apron_trend": self.apron_trend,
                "apron_trend_rows": self.apron_trend_rows,
                "bank_rows": self.bank_rows,
                "hard_rows": self.hard_rows, "hard_active": self.hard_active,
                "hard_rounds": self.hard_rounds, "hard_settled": self.hard_settled,
                "hard_max_violation_m": round(self.hard_max_violation_m, 6),
                "hard_worst": self.hard_worst,
                "runway_projection": self.runway_projection.as_dict(),
                "one_way_rows": self.one_way_rows,
                "one_way_rounds": self.one_way_rounds,
                "one_way_settled": self.one_way_settled,
                "one_way_move_m": round(self.one_way_move_m, 6),
                "bend_rows_by_class": self.bend_rows_by_class,
                "targets": len(self.targets),
                "solver_wall_s": round(self.solver_wall_s, 3),
                "runway_profile": self.runway_profile,
                "families": self.families, "terms": self.terms}

    def _taxi_trend_line(self) -> str:
        """THE TAXI CHAINS' TREND RESIDUALS (owner RULINGS 2026-09-10v) —
        the worst three chains by |residual|, each with its length."""
        by = self.taxi_trend.get("by_chain") or []
        if not by:
            return ""
        return (" (worst taxi trends " + ", ".join(
            f"{r['max_m']:.2f} m over {r['length_m']:.0f} m" for r in by[:3])
            + ")")

    def _apron_trend_line(self) -> str:
        """THE APRON BODIES' 2-D TREND RESIDUALS (spec §8.7) — the worst
        three bodies by |residual|, each with its plan diameter."""
        by = self.apron_trend.get("by_body") or []
        if not by:
            return ""
        return (" (worst apron trends " + ", ".join(
            f"{r['max_m']:.2f} m over {r['diameter_m']:.0f} m" for r in by[:3])
            + ")")

    def _body_plane_line(self) -> str:
        """THE APRON BODIES' PLANE RESIDUALS — the worst three by the larger
        of |level| and |tilt| (metres of rise over the body's own radius)."""
        bs = sorted(self.body_datums,
                    key=lambda r: -max(abs(r["residual_m"]),
                                       abs(r.get("tilt_m") or 0.0)))[:3]
        if not bs:
            return ""
        return (" (worst body planes " + ", ".join(
            f"level {r['residual_m']:+.2f} / tilt {(r.get('tilt_m') or 0.0):+.2f} m"
            for r in bs) + ")")

    def line(self) -> str:
        worst = sorted(self.families.items(), key=lambda kv: -kv[1]["max_m"])[:6]
        return (f"design (08t): {self.rounds} active-set round(s)"
                f"{'' if self.converged else ' (SET NOT SETTLED)'}, {self.method}, "
                f"{self.unknowns} unknowns / {self.fixed} fixed, {self.rows} rows, "
                f"{self.triangles} triangles in {self.components} complexes "
                f"({self.detached} detached), {self.body_datum_bodies} apron bodies on "
                f"their own DEM PLANE ({self.body_datum_rows} rows)"
                + self._body_plane_line()
                + f", {self.taxi_trend_rows} taxi trend rows"
                + self._taxi_trend_line()
                + f", {self.apron_trend_rows} apron trend rows"
                + self._apron_trend_line()
                + f", {self.bank_rows} bank rows off the "
                f"terrain edge, {self.hard_active}/{self.hard_rows} hard rows active "
                f"(max violation {self.hard_max_violation_m:.4f} m in "
                f"{self.hard_rounds} polish round(s)"
                f"{', HARD SET SETTLED' if self.hard_settled else ', HARD SET NOT SETTLED'}), "
                f"{self.one_way_rows} one-way rows in {self.one_way_rounds} lag "
                f"round(s) (worst leader move {self.one_way_move_m:.3f} m"
                f"{'' if self.one_way_settled else ', LAG NOT SETTLED'}), "
                f"{self.solver_wall_s:.2f} s solver; "
                + self.runway_projection.line() + "; "
                "worst targets " + ", ".join(
                    f"{k} {v['missed']}/{v['rows']} max {v['max_m']:.3f} m"
                    for k, v in worst if v["missed"]))




def residual(cs: ConstraintSet, z: np.ndarray, objective: float) -> Residual:
    """The certificate: the worst residual of each row kind at ``z`` — the
    same reading the LP's certificate carried, now of TARGETS."""
    mp = md = mf = mb = mo = 0.0
    for p in cs.pins:
        mp = max(mp, abs(float(z[p.v]) - p.z))
    for d in cs.diffs:
        # 11j: the row's relief target shifts its zero (``Diff.rel``)
        md = max(md, abs(float(z[d.a]) - float(z[d.b]) - float(getattr(d, "rel", 0.0)))
                 - d.cap * d.d)
    for f in cs.flats:
        g = z[list(f.group)]
        mf = max(mf, float(g.max() - g.min()))
    for bd in cs.bands:
        if bd.lo is not None:
            mb = max(mb, bd.lo - float(z[bd.v]))
        if bd.hi is not None:
            mb = max(mb, float(z[bd.v]) - bd.hi)
    for o in cs.offsets:
        mo = max(mo, o.min_delta - (float(z[o.a]) - float(z[o.b])))
    ml = 0.0
    for ln in cs.linears:
        s = sum(c * float(z[v]) for v, c in ln.terms)
        if ln.hi is not None:
            ml = max(ml, s - ln.hi)
        if ln.lo is not None:
            ml = max(ml, ln.lo - s)
    return Residual(max_pin_m=mp, max_diff_m=max(md, ml), max_flat_m=mf,
                    max_band_m=mb, max_offset_m=mo, objective=objective)
