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
from .project import ProjectionReport, ZoneClampReport
from .linear import DEFAULT_METHOD

__all__ = ["DesignReport", "residual", "settled_flip"]


def settled_flip(viol: np.ndarray, tol: float,
                 active: _t.AbstractSet[int]) -> tuple[bool, int, float]:
    """THE SETTLED CONDITION of the design solve's active set (owner
    RULINGS 2026-09-12u, spec §30 (3c)), stated ONCE: given the current
    one-sided violations, the tolerance and the set that was active,
    return ``(settled, rows that flipped label, the worst violation
    among them)``.

    The set is SETTLED when no row changes label, or when every row that
    does sits inside ONE tolerance band of the threshold (violation
    ``<= 2 * tol``) — a row hovering at its own bound flips without
    moving the surface, and that is the only flip settlement forgives.
    Until 12u ``converged`` was asserted on TWO weaker exits — the
    objective stalling within 1e-6, and the line search buying nothing —
    either of which fires while thousands of rows are still crossing
    their bounds by metres.  Both are still exits (there is nothing
    better to return), but they no longer claim settlement, and the flip
    they exit on is REPORTED (``set_flips`` / ``set_flip_max_m``)."""
    nxt = set(np.flatnonzero(viol > tol).tolist())
    flip = np.asarray(sorted(nxt ^ set(active)), dtype=np.int64)
    if not flip.size:
        return True, 0, 0.0
    worst = float(np.max(np.abs(viol[flip])))
    return worst <= 2.0 * tol, int(flip.size), worst


# ── the report ──────────────────────────────────────────────────────────

@_dc.dataclass
class DesignReport:
    """The residual per family and per objective term — what ``law_tiers``
    used to be, read the design surface's way: a law is a TARGET, so a
    missed target is a residual, never a demotion."""

    rounds: int = 0
    #: THE ACTIVE SET SETTLED (owner RULINGS 2026-09-12u, spec §30 (3c)):
    #: asserted ONLY where no row changed label, or where every row that did
    #: hovers within one tolerance band of its own bound
    #: (``solve.design._settled``).  The objective stalling and the line
    #: search buying nothing are EXITS, not settlement.
    converged: bool = False
    #: the rows that changed label at the exit, and the worst violation
    #: among them — the flip an unsettled exit is reported by
    set_flips: int = 0
    set_flip_max_m: float = 0.0
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
    #: THE LEVEL BELT (RULINGS 2026-09-13, lane ``v2zerocrater``; spec §23.4):
    #: how many vertices reached the solve in a piece with NO LEVEL AT ALL —
    #: bending and relative rows only, whose least-squares minimiser is the
    #: sentinel 0.0 m — and took their own terrain plane instead.  A non-zero
    #: count is worth reading: it names geometry no law levels.
    level_belt_rows: int = 0
    #: THE FOOT ROWS (owner RULINGS 2026-09-11q, repriced 11ab; spec
    #: §11b (2)): the per-foot placement targets of every bare-ground
    #: body, priced at ``pad_flat`` (``constraints/foot_rows.py``)
    foot_rows: int = 0
    #: WHY a foot row is missed (round 8's attribution surface): the
    #: per-FOOT residual distribution, how many feet stand on a triangle
    #: with no free column at all, and how many share one triangle with
    #: another foot asking for a different level — a sheet is LINEAR over
    #: a triangle, so two feet in one face cannot both be carried
    foot_row_diag: dict[str, _t.Any] = _dc.field(default_factory=dict)
    #: law rows whose one foot is the terrain beyond the zone's outer ring:
    #: the BANK (08t answers 2/3) — reported, never a design target
    bank_rows: int = 0
    #: THE HARD ROWS (RULINGS 2026-09-08v): the runway family's law rows as
    #: constraints — how many exist, how many the settled active set holds,
    #: how many polish rounds it took and the worst violation left (a
    #: constraint held exactly reads 0 to the solver's tolerance)
    hard_rows: int = 0
    #: THE VIOLATED ROWS OF THE SHIPPED SURFACE (owner RULINGS 2026-09-12u,
    #: spec §30 (3b)).  Until 12u this was phase C's MULTIPLIER count — how
    #: many rows the augmented Lagrangian had ever charged, read before the
    #: final projection — which at LEMD read 1,457 where the surface that
    #: shipped violated 725.  A count nobody can act on is not an
    #: instrument; the number reported is now the rows over ``hard_tol_m``
    #: on the surface the build emits, re-read after the projection like
    #: the worst violation beside it.
    hard_active: int = 0
    hard_rounds: int = 0
    hard_max_violation_m: float = 0.0
    hard_settled: bool = True
    #: the ruling of the worst-held hard row (empty where every row is held)
    hard_worst: str = ""
    #: THE FINAL PROJECTION (owner RULINGS 2026-09-09y): the runway family's
    #: hard rows held EXACTLY by a QP after the solve (``solve/project.py``)
    runway_projection: ProjectionReport = _dc.field(default_factory=ProjectionReport)
    #: THE ZONE PROJECTION (RULINGS 2026-09-12ag; spec §32): every
    #: adjacent-ground zone vertex clamped into its own corridor band
    #: after the runway projection (``solve/project.project_zone_bands``)
    zone_projection: ZoneClampReport = _dc.field(default_factory=ZoneClampReport)
    #: THE ONE-WAY ROWS (RULINGS 2026-09-09b (2)/(3)): the adjacent-ground
    #: corridor and strip-tie rows whose pavement feet are LAGGED — how
    #: many, how many lag rounds the outer loop paid, whether the lag
    #: settled and how far the worst leader foot moved in the last round
    one_way_rows: int = 0
    one_way_rounds: int = 0
    one_way_settled: bool = True
    one_way_move_m: float = 0.0
    #: §20a THE LAG IS A CONVERGENCE CONDITION (Fable 2026-09-13; owner
    #: RULINGS 2026-09-13ac).  When the lag exhausts ``one_way_max_rounds``
    #: without reaching ``one_way_tol_m`` the report NAMES the failure —
    #: how many rows still move, the worst row's generator and ruling, its
    #: LEADER vertex (id and lat/lon) and that leader's last move.  Until
    #: 13ac the cap was a silent stop at three rounds and the polish ran
    #: inside a lag that had not converged.
    one_way_failure: dict[str, _t.Any] = _dc.field(default_factory=dict)
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

    def record_flip(self, res: tuple[bool, int, float]) -> bool:
        """Record one active-set EXIT's flip (§30 (3c), ``settled_flip``) and
        return whether that exit SETTLED."""
        ok, n, worst = res
        self.set_flips = max(self.set_flips, int(n))
        self.set_flip_max_m = max(self.set_flip_max_m, round(float(worst), 4))
        return bool(ok)

    def read_hard_set(self, viol: np.ndarray, tol: float,
                      ruling: _t.Callable[[int], str]) -> float:
        """THE HARD SET READ OFF THE SHIPPED SURFACE (owner RULINGS
        2026-09-12u, spec §30 (3b)): the worst violation, whether the set is
        settled, HOW MANY ROWS ARE VIOLATED and the worst row's ruling.

        ``hard_active`` used to be phase C's MULTIPLIER count, taken before
        the final projection — at LEMD it read 1,457 where the surface that
        shipped violated 725.  A count nobody can act on is not an
        instrument.  Returns the worst violation."""
        worst = float(np.max(viol)) if viol.size else 0.0
        self.hard_max_violation_m = worst
        self.hard_settled = worst <= tol
        self.hard_active = int(np.count_nonzero(viol > tol))
        self.hard_worst = "" if self.hard_settled else ruling(int(np.argmax(viol)))
        return worst

    def read_lag_failure(self, ow_i: np.ndarray, move: np.ndarray, tol: float,
                         cap: int, one: list, one_way: dict, planar: _t.Any
                         ) -> dict[str, _t.Any]:
        """§20a: NAME the lag's failure (owner RULINGS 2026-09-13ac).

        ``one_way_max_rounds`` is a SAFETY CEILING, not a schedule: hitting
        it means the leader/follower fixed point did not contract, and the
        augmented-Lagrangian polish that follows is then iterating inside a
        problem that is still moving under it — which is how LEMD's 2-3 cm
        pad-ceiling shortfall crossed ``hard_tol_m`` while the report said
        only ``LAG NOT SETTLED``.

        ``move`` is the last round's per-row leader motion, positionally
        over ``ow_i``.  Records the rows still moving, the worst row's
        generator / ruling, its LEADER vertices (the terms that are not the
        row's ``one_way`` followers) with their canonical lat/lon, and that
        leader's move."""
        if not move.size:
            return self.one_way_failure
        k = int(np.argmax(move))
        row_i = int(ow_i[k])
        _terms, _b, row = one[row_i]
        followers = set(one_way.get(row_i) or ())
        leaders = [v for v, _c in _terms if v not in followers]
        self.one_way_failure = {
            "rounds": self.one_way_rounds, "cap": cap, "tol_m": tol,
            "rows_moving": int(np.count_nonzero(move > tol)),
            "rows": int(move.size),
            "worst_move_m": round(float(move[k]), 6),
            "worst_row": row_i,
            "generator": row.source.generator,
            "ruling": row.source.ruling[:120],
            "leaders": [{"v": v,
                         "lat": planar.vertices[v].key[0],
                         "lon": planar.vertices[v].key[1]} for v in leaders[:4]],
            "followers": sorted(followers)[:4]}
        return self.one_way_failure

    def lag_failure_line(self) -> str:
        """The named failure, one line (empty where the lag settled)."""
        f = self.one_way_failure
        if not f:
            return ""
        led = ", ".join(f"v{r['v']} at {r['lat']:.11f},{r['lon']:.11f}"
                        for r in f["leaders"]) or "(no leader column)"
        return (f"LAG NOT SETTLED after {f['rounds']} of {f['cap']} round(s): "
                f"{f['rows_moving']} of {f['rows']} one-way rows still move "
                f"more than {f['tol_m']} m; worst {f['worst_move_m']:.4f} m on "
                f"row {f['worst_row']} ({f['generator']}: {f['ruling']}), "
                f"leader {led}")

    def as_dict(self) -> dict[str, _t.Any]:
        return {"rounds": self.rounds, "converged": self.converged,
                "set_flips": self.set_flips,
                "set_flip_max_m": round(self.set_flip_max_m, 4),
                "method": self.method, "unknowns": self.unknowns,
                "fixed": self.fixed, "rows": self.rows,
                "triangles": self.triangles, "components": self.components,
                "detached": self.detached,
                "level_belt_rows": self.level_belt_rows,
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
                "zone_projection": self.zone_projection.as_dict(),
                "one_way_rows": self.one_way_rows,
                "one_way_rounds": self.one_way_rounds,
                "one_way_settled": self.one_way_settled,
                "one_way_move_m": round(self.one_way_move_m, 6),
                "one_way_failure": self.one_way_failure,
                "bend_rows_by_class": self.bend_rows_by_class,
                "targets": len(self.targets),
                "solver_wall_s": round(self.solver_wall_s, 3),
                "runway_profile": self.runway_profile,
                "families": self.families, "terms": self.terms,
                "foot_row_diag": self.foot_row_diag}

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
                f"{'' if self.converged else f' (SET NOT SETTLED: {self.set_flips} rows flipped, worst {self.set_flip_max_m:.3f} m)'}, {self.method}, "
                f"{self.unknowns} unknowns / {self.fixed} fixed, {self.rows} rows, "
                f"{self.triangles} triangles in {self.components} complexes "
                f"({self.detached} detached"
                + (f", {self.level_belt_rows} LEVEL-BELT vertices"
                   if self.level_belt_rows else "")
                + f"), {self.body_datum_bodies} apron bodies on "
                f"their own DEM PLANE ({self.body_datum_rows} rows)"
                + self._body_plane_line()
                + f", {self.taxi_trend_rows} taxi trend rows"
                + self._taxi_trend_line()
                + f", {self.apron_trend_rows} apron trend rows"
                + self._apron_trend_line()
                + f", {self.bank_rows} bank rows off the "
                f"terrain edge, {self.hard_active}/{self.hard_rows} hard rows violated "
                f"(max violation {self.hard_max_violation_m:.4f} m in "
                f"{self.hard_rounds} polish round(s)"
                f"{', HARD SET SETTLED' if self.hard_settled else ', HARD SET NOT SETTLED'}), "
                f"{self.one_way_rows} one-way rows in {self.one_way_rounds} lag "
                f"round(s) (worst leader move {self.one_way_move_m:.3f} m"
                + ('' if self.one_way_settled
                   else ', ' + (self.lag_failure_line() or 'LAG NOT SETTLED'))
                + "), "
                f"{self.solver_wall_s:.2f} s solver; "
                + self.runway_projection.line() + "; "
                + self.zone_projection.line() + "; "
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


def foot_row_diagnostic(one: _t.Sequence[_t.Any], viol: _t.Sequence[float],
                        idx: _t.Sequence[int],
                        col: _t.Sequence[int]) -> dict[str, _t.Any]:
    """ROUND 8's attribution (owner RULINGS 2026-09-11ab): the foot rows
    were repriced from ``ground_datum`` (3) to ``pad_flat`` (3000) and
    LEMD's missed count barely moved — so the price is not what binds.
    This reads WHAT does, per FOOT (a foot is TWO one-sided rows sharing
    one target), without costing a second solve:

    * the residual distribution — how many feet land inside 0.01 / 0.1 /
      0.3 / 1.0 m of their target;
    * ``feet_no_free_column`` — the foot's triangle is entirely FIXED, so
      no price can move it;
    * ``feet_sharing_a_triangle`` and ``worst_triangle_spread_m`` — two
      feet inside ONE face asking for different levels.  The sheet is
      LINEAR over a triangle: their difference is unpayable at any price.
    """
    feet: dict[tuple, dict[str, _t.Any]] = {}
    for i in idx:
        terms, hi, row = one[i]
        key = (row.source.inputs, tuple(sorted((v, round(abs(c), 9))
                                               for v, c in terms)))
        f = feet.setdefault(key, {"r": 0.0, "z": 0.0, "vs": tuple(
            sorted(v for v, _c in terms))})
        f["r"] = max(f["r"], float(viol[i]))
        if hi >= 0.0:
            f["z"] = float(hi)
    res = sorted(max(0.0, f["r"]) for f in feet.values())
    n = len(res) or 1
    by_tri: dict[tuple, list[float]] = {}
    fixed = 0
    for f in feet.values():
        by_tri.setdefault(f["vs"], []).append(f["z"])
        if all(col[v] < 0 for v in f["vs"]):
            fixed += 1
    shared = sum(len(zs) for zs in by_tri.values() if len(zs) > 1)
    spread = max((max(zs) - min(zs) for zs in by_tri.values() if len(zs) > 1),
                 default=0.0)
    def _q(p: float) -> float:
        return round(res[min(n - 1, int(p * n))], 4) if res else 0.0
    return {"feet": len(feet),
            "within_0.01_m": sum(1 for r in res if r <= 0.01),
            "within_0.1_m": sum(1 for r in res if r <= 0.1),
            "within_0.3_m": sum(1 for r in res if r <= 0.3),
            "within_1.0_m": sum(1 for r in res if r <= 1.0),
            "p50_m": _q(0.5), "p90_m": _q(0.9),
            "max_m": round(res[-1], 4) if res else 0.0,
            "feet_no_free_column": fixed,
            "triangles": len(by_tri),
            "feet_sharing_a_triangle": shared,
            "worst_triangle_spread_m": round(spread, 4)}
