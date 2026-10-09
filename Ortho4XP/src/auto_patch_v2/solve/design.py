"""THE DESIGN SURFACE — ONE sparse least-squares solve (owner RULINGS
2026-09-08t; spec ``docs/specs/auto-patch-v2/design-surface-spec.md`` §1-§3).

Pavement is a DESIGNED surface: minimum curvature, unbounded cut and fill,
flush and tangent at every contact, the DEM a datum only, every law a
TARGET.  One convex quadratic program, no tiers, no IIS, no relaxation, no
yield groups — those are deleted.

    minimise  w_bend  ‖ L z ‖²          thin-plate bending over each connected
                                        pavement complex (the cotangent
                                        Laplacian of its faces' triangulation:
                                        bending is minimised in EVERY direction
                                        and tangency holds across shared edges)
            + w_chord ‖ z − chord ‖²    the runway's threshold chord per ridge
                                        station (``constraints/runway_chord.py``,
                                        published through ``preferred_z``)
            + w_law   ‖ max(0, viol) ‖² every law row of every generator as a
                                        ONE-SIDED quadratic penalty
            + w_dem   ‖ z − DEM ‖²      ONLY on zone vertices, ramped 0 at the
                                        pavement edge to 1 at the outer ring
            + w_road  ‖ L_chain z ‖²    road chains' own bending
            + w_det   ‖ z − DEM ‖²      a component with no datum at all
    subject to  Pin  → the vertex is FIXED (eliminated from the unknowns)
                Flat → the group is ONE unknown (merged)
                beyond the zone's outer ring the vertex IS the DEM (fixed)
                THE RUNWAY FAMILY'S LAW ROWS (``[design] hard_generators``)
                → CONSTRAINTS, enforced EXACTLY as a KKT block, never a
                  penalty (owner 05s/06b within 08t, RULINGS 2026-09-08v)

``w_bend`` is PER CLASS (``bend_runway`` / ``bend_taxi`` / ``bend_apron`` /
``bend_road`` / ``bend_strip``, RULINGS 2026-09-08v): one weight for the
whole sheet traded the pavement against the strip, so a bending row is
priced by the class of its own vertex (:func:`bend_class`).

The one-sided penalties are met by an ACTIVE SET iteration (a semismooth
Newton step): solve, take the rows the surface violates, re-solve with those
rows active, to a fixed point of the set.  The HARD rows run their own active
set inside the same loop — a violated one enters the KKT block, one whose
multiplier turns negative leaves it — and a bounded polish after it, so the
returned surface satisfies every runway law to the solver's tolerance.  Every
weight and limit is a law value (``law/emit.toml [design]``,
``law/design_schema.py``).

Joints (08k/08r-2) carry no bending term and no row: the shape stage split
their vertices and dropped their rows before the set reached here, so the
components below simply do not touch.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import time
import typing as _t

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import LinearOperator, cg, lsqr, splu

from ..law import Law
from ..law.design_schema import BEND_CLASSES
from ..law.tables import (design as design_law, is_value_role,
                          pavement_roles as _pavement_roles,
                          role_side, zone2_half_width_m, zone_class)
from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear, Offset,
                                 Pin, Row)
from ..model.planar import PlanarMap
from .api import Options, Solution, Status
from .linear import (DEFAULT_LOW_RANK, DEFAULT_METHOD, LOW_RANK_MODES,
                     METHODS, _linear_solve, _objective, _term_energies)
from .design_report import (DesignReport, foot_row_diagnostic, hard_exceeds, hard_metres,
                            residual, settled_flip)
from .design_qp import DEFAULT_SOLVER, SOLVERS, solve_one_sided
from .feasibility import (_carries_a_column, apron_hard_rows, demote_conflicts,  # noqa: F401
                          promote_missed, published, publish_stages, runway_after)
from .flex import _held_at_ref, runway_columns, runway_stage_roles, stage_one  # noqa: F401
from .project import ProjectionReport, ZoneClampReport, project_after_solve
from .pin_yield import yield_pins as _yield_pins  # (re-export: test_surfacesettle2)
from .rows import (_cotangent_laplacian, _face_triangles, _law_sides, _level_free_columns,
                   _one_matrix,
                   apply_level_belt, _plane_rows, _plane_targets, _reduce, _Reduction, _role_bodies,
                   _role_bodies_faced, _Rows, _shape_bodies,
                   _sheet_components, _Side, _violation, _zone_weights)

__all__ = ["DesignReport", "Base", "assemble", "solve_design", "residual",
           "stage_split", "airside_stage_roles", "airside_stage_vertices",
           "conforming_rulings", "groundside_pin_rulings",
           "bend_roles", "pavement_roles", "bend_class", "apron_roles",
           "taxi_body_roles", "datum_roles", "hard_rulings",
           "one_way_rulings", "pad_flat_rulings", "pad_level_rulings",
           "ground_roles", "ground_datum_vertices", "foot_row_rulings",
           "is_hard", "ruling_head",
           "METHODS", "DEFAULT_METHOD", "LOW_RANK_MODES", "DEFAULT_LOW_RANK",
           "SOLVERS", "DEFAULT_SOLVER"]

#: The backtracking line search's smallest step (a numeric floor of the
#: solver, not a law value): below it the Newton direction buys nothing and
#: the previous point IS the minimiser.
_ALPHA_FLOOR = 1.0e-6

#: The shift that switches a ONE-WAY row OFF for the warm-up solve (its
#: leaders have no value before the first solve): a target so far away
#: that the row can never be violated.  A solver constant, not a law value.
_LAG_OFF = 1.0e9


# ── role / ruling readers: ``solve/design_roles`` (the 1,000-line file law) ──
from .design_ground import ground_datum_vertices, ground_rim_vertices, ground_roles  # noqa: E402
from .design_stage import stage_split  # noqa: E402  (re-export: the §20b split)
from .design_stage import _groundside_minter, _welded_faces, stage_one_on  # noqa: E402
from .design_roles import (  # noqa: E402  (re-export)
    airside_stage_roles, airside_stage_vertices, conforming_rulings, groundside_pin_rulings, bend_roles, pavement_roles, bend_class, apron_roles, taxi_body_roles, datum_roles, one_way_rulings, foot_row_rulings, pad_flat_rulings, pad_level_rulings, hard_rulings, ruling_head, is_hard)

# ── the assembled problem: ``solve/design_assemble`` (issue #303, the
# 1,500-line split point); re-exported, every caller's path unchanged ──
from .design_assemble import Base, _BodyDatum, assemble  # noqa: E402,F401



def solve_design(planar: PlanarMap, cs: ConstraintSet, law: Law,
                 options: Options | None = None, *,
                 size_out: dict | None = None,
                 method: str = DEFAULT_METHOD,
                 low_rank: str = DEFAULT_LOW_RANK,
                 strips: _t.Any = None,
                 stage2_rewrite: _t.Callable[
                     [_t.Mapping[int, float]],
                     tuple[ConstraintSet, dict]] | None = None,
                 hold: _t.Any = None,
                 stage1: _t.Any = None
                 ) -> tuple[Solution, DesignReport]:
    """THE DESIGN SURFACE, in ONE stage or TWO (§20b).

    ``stage1`` (#100 option (c), ``design_stage.stage_one_on``): stage 1
    assembled on the RIBBON-FREE map; ``None``: on ``planar`` itself.""

    ``stage2_rewrite`` (owner RULINGS 2026-09-27a (11)): the caller's
    rewrite of the constraint set from STAGE 1's solved levels, applied
    before stage 2 is assembled — ``constraints/road_ramp
    .reach_seed_rewrite`` bound to the map and law (this layer may not
    import ``constraints``, M0 §1).  Its report lands in
    ``DesignReport.reach_seed``.  Ignored by the single solve.

    THE PINS THAT YIELD (owner RULINGS 2026-09-27a (10), ``[design]
    yielding_pin_rulings``; ``solve/pin_yield.py``): when a stage's hard set
    does not settle, the yielding pins the unsettled rows reach are
    released to design targets and that stage is solved once more; the
    release is kept only when the hard set is better for it, and every
    released pin is reported (``DesignReport.pin_yield``).  WHICH STAGE
    (issue #87, RULINGS 2026-09-29d (c)): a yielding pin a stage-1 row reads
    (``pin_yield.stage1_read_pins``) is decided by STAGE 1's hard set alone
    — stage 2 holds it as the constant stage 1 solved against; stage 2 may
    release only the pins stage 1 never read.

    ``[design] staged_solve`` false is the single solve this module has
    always been: one problem, one report.  True is §20b THE STAGED SOLVE
    (owner RULINGS 2026-09-13dh, ordered 14an) — "airside solves first,
    everything else conforms" as an ARCHITECTURE and not a price:

      stage 1  the AIRSIDE PAVEMENT problem alone (:func:`stage_split`):
               its columns, every row whose every column is one of them,
               its own polish and BOTH projections.  What it returns is the
               certified airside surface.
      stage 2  the WHOLE problem with every airside column stage 1 LEVELLED
               substituted as a constant (the reduction eliminates it,
               exactly as a ``Pin``).  A pad / road / ground row coupling to
               airside then has a CONSTANT on its airside side: one-way by
               construction, no lag, no skirt, and airside moved between the
               stages is zero BY CONSTRUCTION.

    The returned ``z`` is stage 2's (airside values ARE stage 1's), the
    status the worse of the two, the report stage 2's with stage 1's
    counters in ``stages`` and the hard set COMBINED (§20b's census table).
    """
    if not bool(design_law(law).staged_solve):
        return _with_facade_strips(planar, law, *published(*_solve_stage(
            planar, cs, law, options, size_out=size_out, method=method,
            low_rank=low_rank)))
    t_all = time.perf_counter()
    # PASS 1a / THE INTERVAL / PASS 1b (flat-pad spec v2 §1-§2, owner
    # RULINGS 2026-09-30as; ``solve/flex.stage_one``): ``hold`` is the
    # caller's binding (``constraints/no_step.HoldPass`` — this layer may not
    # import ``constraints``, M0 §1); no hold row = pass 1a IS stage 1.

    def _s1(pm_x: PlanarMap, cs_x: ConstraintSet):
        d_x, f_x = stage_split(pm_x, cs_x, law)
        lv: dict[int, float] = {}
        sz: dict = {}
        so, rp = _solve_stage(pm_x, cs_x, law, options, size_out=sz,
                              method=method, low_rank=low_rank, drop=d_x,
                              fixed=f_x, levelled_out=lv,
                              stage_roles=airside_stage_roles(law))
        return so, rp, d_x, f_x, lv, sz
    t1 = time.perf_counter()
    from .pin_yield import stage1_read_pins
    yield_heads = frozenset(
        getattr(design_law(law), "yielding_pin_rulings", ()) or ())
    strip_rep = None
    if stage1 is not None:              # #100 option (c): the ribbon-free map
        (sol1, rep1, drop, foreign, levels1, size1), pass1a, yielded1, levels, \
            s1_read, strip_rep = stage_one_on(stage1, law, _s1, yield_heads)
        planar, hold, strips = stage1.planar_of_full(planar), stage1.hold, None
    else:
        # issue #87's stage-1 pin yield runs INSIDE each pass (``flex.stage_one``)
        planar, cs, (sol1, rep1, drop, foreign, levels, size1), pass1a, yielded1 = \
            stage_one(planar, cs, law, hold, _s1)
        s1_read = (stage1_read_pins(cs, yield_heads, drop) | {int(r["v"]) for r in yielded1}
                   if yield_heads else frozenset())
    w1 = time.perf_counter() - t1
    # THE JETWAY STRIP (owner RULINGS 2026-09-18t Q3; jetway-strip spec §2
    # (4)): a PROJECTION of stage 1's airside answer, applied before stage
    # 2 substitutes it — so the pads read the levelled apron as their
    # constants and "airside moved outside the strips + transitions" is
    # zero by construction.  ``strips`` is ``model.jetway.StripSet``,
    # derived by the caller (``constraints.jetway_strip``: this layer may
    # not import ``constraints``).
    if strips:
        from .project_strip import project_strips
        strip_rep = project_strips(planar, law, strips, levels, sol1.z,
                                   cs.flats)
    seed_rep: dict = {}
    if stage2_rewrite is not None:
        cs, seed_rep = stage2_rewrite(levels)
        # the caller's rewrite re-reads the set it was BOUND to (the un-
        # yielded one): a pin stage 1 RELEASED stays released in stage 2
        # (lane ``joinyield128``: HECA v28332 was re-pinned 0.32 m off the
        # level the sidecar told the core ribbon to take)
        if yielded1:
            from .pin_yield import release_pins
            cs = release_pins(cs, {int(r["v"]) for r in yielded1}, yield_heads)
    elif stage1 is not None and yielded1 and yield_heads:
        from .pin_yield import release_pins
        cs = release_pins(cs, {int(r["v"]) for r in yielded1}, yield_heads)
    if stage1 is not None:
        cs = stage1.apply_full(cs)  # pass 1b's hold law, carried by the join
    elif pass1a is not None and hasattr(hold, "apply"):
        cs = hold.apply(cs)        # stage 2 states pass 1b's hold law (§4)
    t2 = time.perf_counter()
    sol2, rep2 = _solve_stage(planar, cs, law, options, size_out=size_out,
                              method=method, low_rank=low_rank, fixed=levels)
    yielded: list[dict] = []
    if not rep2.hard_settled and sol2.z and yield_heads:
        def _stage2(cs_x: ConstraintSet):
            return _solve_stage(planar, cs_x, law, options, size_out=size_out,
                                method=method, low_rank=low_rank, fixed=levels)
        among2 = {p.v for p in cs.pins} - set(s1_read)
        sol2, rep2, yielded, _cs2 = _yield_pins(planar, cs, law, sol2, rep2,
                                                levels, _stage2, among=among2)
        for r in yielded:
            r["stage"] = 2
    rep2.reach_seed = seed_rep
    # issue #143: the §37 (9) joins the rewrite released because their road
    # row is welded to a stage-1 constant (``road_ramp.welded_join_release``)
    # — published with the level stage 2 gave them, like every yielded join
    welded = [dict(r) for r in (seed_rep.get("welded_join") or ())]
    for r in welded:
        if sol2.z and len(sol2.z) > r["v"]:
            r["z_m"] = round(float(sol2.z[r["v"]]), 4)
            r["excess_m"] = round(r["z_m"] - float(r["pinned_m"]), 4)
    rep2.pin_yield = yielded1 + yielded + welded
    if strip_rep is not None:
        rep2.jetway_strip = strip_rep
    w2 = time.perf_counter() - t2
    rep2.staged = True
    rep2.stage1_wall_s, rep2.stage2_wall_s = w1, w2
    rep2.stage1_fixed = len(levels)
    rep2.stage1_unlevelled = rep1.stage1_unlevelled
    rep2.stage_dropped_rows = rep1.stage_dropped_rows
    if hold is not None:
        rep2.runway_flex = hold.finish(levels if stage1 is None else levels1, sol1.z,
                                       caps_held=bool(rep1.hard_settled))
    rep2.stages = {"stage1": dict(rep1.as_dict(), wall_s=round(w1, 3),
                                  projection_line=rep1.runway_projection.line(),
                                  lag_line=(rep1.lag_failure_line()
                                            if not rep1.one_way_settled else ""),
                                  hard_line=(rep1.hard_failure_line()
                                             if not rep1.hard_settled else "")),
                   "stage2": {"unknowns": rep2.unknowns, "rows": rep2.rows,
                              "hard_rows": rep2.hard_rows,
                              "hard_active": rep2.hard_active,
                              "hard_max_violation_m": round(rep2.hard_max_violation_m, 6),
                              "hard_settled": rep2.hard_settled,
                              "rounds": rep2.rounds, "wall_s": round(w2, 3)}}
    if pass1a is not None:
        rep2.stages["stage1a"] = pass1a
    if stage1 is not None:
        rep2.stages["stage1_map"] = dict(stage1.report)   # #100 option (c)
    rep2.stages["stage1"]["hard_feasibility"] = publish_stages(rep1, rep2, pass1a=pass1a, law=law)
    # THE HARD SET IS THE COMBINATION (§20b's census table): an airside hard
    # row carries no column in stage 2 — it was enforced and read in stage 1,
    # where it is scaled to metres — so the shipped surface's hard set is
    # stage 1's plus stage 2's, and SETTLED is the conjunction.
    rep2.hard_rows += rep1.hard_rows
    rep2.hard_active += rep1.hard_active
    rep2.hard_rounds += rep1.hard_rounds
    if rep1.hard_max_violation_m > rep2.hard_max_violation_m:
        rep2.hard_max_violation_m = rep1.hard_max_violation_m
        rep2.hard_worst = rep1.hard_worst
    rep2.hard_settled = bool(rep1.hard_settled and rep2.hard_settled)
    # THE ASSEMBLY COUNTERS ARE THE TWO STAGES' (§20b's census table, the
    # report row).  A counter that says how many rows of a kind the problem
    # carried describes ONE assembly, and under §20b there are two: the
    # apron bodies' datum planes, the taxi and apron trends, the ground
    # datum, the level belt, the bank filter, the foot rows and the bending
    # rows per class all live in the stage that owns their vertices.  Left
    # as stage 2's they read 0 for everything airside — the report would
    # say "0 apron bodies on their own DEM PLANE" of a build that fitted
    # 271 of them in stage 1.
    rep2.body_datum_rows += rep1.body_datum_rows
    rep2.body_datum_bodies += rep1.body_datum_bodies
    rep2.body_datums = list(rep1.body_datums) + list(rep2.body_datums)
    rep2.taxi_trend_rows += rep1.taxi_trend_rows
    rep2.taxi_xsec_rows += rep1.taxi_xsec_rows
    rep2.free_membrane_rows += rep1.free_membrane_rows
    rep2.apron_trend_rows += rep1.apron_trend_rows
    rep2.ground_datum_rows += rep1.ground_datum_rows
    rep2.level_belt_rows += rep1.level_belt_rows
    rep2.foot_rows += rep1.foot_rows
    rep2.bank_rows += rep1.bank_rows
    rep2.one_way_rows += rep1.one_way_rows
    rep2.rounds += rep1.rounds
    rep2.detached += rep1.detached
    rep2.components = max(rep2.components, rep1.components)
    rep2.triangles = max(rep2.triangles, rep1.triangles)
    rep2.converged = bool(rep1.converged and rep2.converged)
    rep2.set_flips = max(rep2.set_flips, rep1.set_flips)
    rep2.set_flip_max_m = max(rep2.set_flip_max_m, rep1.set_flip_max_m)
    for c, n in rep1.bend_rows_by_class.items():
        rep2.bend_rows_by_class[c] = rep2.bend_rows_by_class.get(c, 0) + n
    # THE RUNWAY PROJECTION RAN IN STAGE 1, where the runway family is free;
    # in stage 2 it is a no-op on a fixed family (``if not rep.columns``),
    # so the report carries stage 1's certificate — the one that describes
    # the shipped runway.
    if not rep2.runway_projection.ran:
        rep2.runway_projection = rep1.runway_projection
    if not rep2.zone_projection.ran and rep1.zone_projection.ran:
        rep2.zone_projection = rep1.zone_projection
    if rep1.one_way_rows and not rep1.one_way_settled and rep2.one_way_settled:
        rep2.one_way_settled = False
        rep2.one_way_failure = rep1.one_way_failure
        rep2.one_way_move_m = max(rep2.one_way_move_m, rep1.one_way_move_m)
    if size_out is not None:
        size_out.update({"stage1_columns": size1.get("columns", 0),
                         "stage1_rows": size1.get("rows", 0),
                         "stage1_fixed_into_stage2": len(levels)})
    status = (Status.ERROR if Status.ERROR in (sol1.status, sol2.status)
              else Status.FEASIBLE if Status.FEASIBLE in (sol1.status, sol2.status)
              else sol2.status)
    sol = _dc.replace(sol2, status=status,
                      iterations=sol1.iterations + sol2.iterations,
                      wall_s=time.perf_counter() - t_all,
                      message=f"staged design surface (20b): stage 1 {sol1.message}; "
                              f"stage 2 {sol2.message}")
    return _with_facade_strips(planar, law, sol, rep2)


def _with_facade_strips(planar: PlanarMap, law: Law, sol: Solution,
                        rep: DesignReport) -> tuple[Solution, DesignReport]:
    """§52: THE FACADE STRIPS TAKE THEIR HOST PADS' FINAL PLANE — after the
    whole solve, so no pad and no airside value can move for them.  BOTH
    exits of :func:`solve_design` pass through here (the staged solve and
    the single one): a strip is minted whichever path solves the map, and
    unprojected it stands on its own terrain, metres off the dock."""
    from .project_strip import project_facade_strips
    if not sol.z:
        return sol, rep
    z, rep.facade_strip = project_facade_strips(planar, law, sol.z)
    return _dc.replace(sol, z=z), rep


def solve_late_stage(planar: PlanarMap, cs: ConstraintSet, law: Law,
                     fixed: _t.Mapping[int, float],
                     options: Options | None = None, *,
                     size_out: dict | None = None,
                     method: str = DEFAULT_METHOD,
                     low_rank: str = DEFAULT_LOW_RANK
                     ) -> tuple[Solution, DesignReport]:
    """THE LAST STAGE (spec §53 (9)): the full map with every level the
    earlier stages gave substituted as a constant — ``fixed``, the caller's
    coordinate join (``pipeline/stage_one_map.late_fixed``) — so only the
    followers are unknowns and every row between a follower and a leader has
    a constant on the leader's side: one-way by construction."""
    return published(*_solve_stage(planar, cs, law, options, size_out=size_out,
                                   method=method, low_rank=low_rank, fixed=fixed))


def _solve_stage(planar: PlanarMap, cs: ConstraintSet, law: Law,
                 options: Options | None = None, *,
                 size_out: dict | None = None,
                 method: str = DEFAULT_METHOD,
                 low_rank: str = DEFAULT_LOW_RANK,
                 drop: _t.AbstractSet[int] | None = None,
                 fixed: _t.Mapping[int, float] | None = None,
                 levelled_out: dict[int, float] | None = None,
                 stage_roles: _t.AbstractSet[str] | None = None
                 ) -> tuple[Solution, DesignReport]:
    """ONE solve of the design surface (module docstring) — the whole thing
    when ``staged_solve`` is off, one stage of §20b when it is not.

    ``drop`` / ``fixed`` are :func:`assemble`'s.  ``levelled_out`` collects
    §20b (4)'s answer for the next stage: the solved value of every vertex
    whose column carried an ALWAYS-ON row (bending, chord, trend, datum,
    level belt) — a column with none has no level here and is left free.
    """
    opt = options or Options()
    d = design_law(law)
    rep = DesignReport(method=method)
    t0 = time.perf_counter()
    n = len(planar.vertices)
    base_p = assemble(planar, cs, law, rep, drop=drop, fixed=fixed,
                      stage_roles=stage_roles)
    rows, red, one, eqs = base_p.rows, base_p.red, base_p.one, base_p.eqs
    # §20b (4): a column with NO LEVEL is not this stage's answer.  The level
    # belt (§23.4) normally leaves none — it gives every level-free piece its
    # own terrain plane or refuses by name — so this reads 0 and is the guard
    # that keeps a sentinel 0.0 m from being SUBSTITUTED into the next stage.
    unlevelled: set[int] = set()
    if levelled_out is not None:
        unlevelled = set(_level_free_columns(rows, base_p.body, red, one))
        rep.stage1_unlevelled = len(unlevelled)
    chord_v, road_v = base_p.chord_vertices, base_p.road_fit_vertices
    if red.n_cols == 0:
        z = np.array([float(red.value[v]) for v in range(n)])
        return (Solution(z=tuple(z), status=Status.OPTIMAL,
                         residual=residual(cs, z, 0.0),
                         wall_s=time.perf_counter() - t0,
                         message="every vertex fixed"), rep)

    # 10. THE ACTIVE SET: solve, take the violated one-sided rows, re-solve.
    #     The one-sided rows are stacked ONCE (``_one_matrix``) so a round is
    #     a row-slice and a matrix-vector product, never a Python re-assembly:
    #     at HECA that is 210k rows the loop would otherwise rebuild 60 times.
    #
    #     THE HARD ROWS (the runway family's transverse, vertical curve K and
    #     max grade — ``[design] hard_rulings``, RULINGS 2026-09-08v) ride the
    #     same stack at the CONSTRAINT weight ``ρ = hard_weight`` and are made
    #     EXACT by an outer AUGMENTED-LAGRANGIAN loop: the inner active set
    #     runs to its damped fixed point with the multipliers held, then each
    #     violated runway row's multiplier rises by ``ρ · violation`` and
    #     tightens that row's target by ``μ/ρ``.  The multipliers converge, so
    #     the runway laws end HELD, not traded — which a weight alone cannot
    #     do (RULINGS 2026-09-08v: "a weight cannot buy a law").
    A0f, b0f = rows.matrix(red.n_cols)      # the ALWAYS-ON rows (the base)
    # THE PER-BODY DATUM as the LOW-RANK term (RULINGS 2026-09-09r (1)): one
    # row per body, never factorised — ``_linear_solve`` applies it by the
    # Woodbury identity (:data:`LOW_RANK_MODES`).
    Ub, cb = ((base_p.body.matrix(red.n_cols)) if base_p.body is not None
              and base_p.body.n else (None, None))
    A1, b1 = _one_matrix(one, red)
    # §5a FEASIBILITY BEFORE THE SOLVE (RULINGS 2026-09-30be/30bf), conflicts named
    demote_conflicts(planar, law, base_p, A1, b1, rep, verbose=opt.verbose,
                     stage="2" if fixed and drop is None else "1" if drop else "")
    # THE ONE-WAY SPLIT (RULINGS 2026-09-09b (2)/(3)).  A corridor row
    # ``z_ground − z_foot ≤ bound`` priced two-way pulls the PAVEMENT down
    # toward the ground it is meant to shape.  For a one-way row only the
    # FOLLOWER's column stays in ``A1``; its leader coefficients move to
    # ``A1_lead``, whose product with the previous outer round's ``x``
    # enters the right-hand side through ``shift`` — the ground follows,
    # the pavement never feels it.  The lag is iterated to a fixed point
    # (``one_way_max_rounds`` / ``one_way_tol_m``), exactly as the hard
    # rows' multipliers are.
    ow_i = np.asarray(sorted(base_p.one_way), dtype=np.int64)
    A1_lead: sp.csr_matrix | None = None
    if ow_i.size:
        # THE FOLLOWER IS A COLUMN SET (owner RULINGS 2026-09-10y): a pad
        # plane's three degrees of freedom cannot be one column, so the
        # split is by (row, column) MEMBERSHIP, not by a single column id.
        is_ow = np.zeros(len(one), dtype=bool)
        is_ow[ow_i] = True
        ncol = int(red.n_cols)
        keep_keys = np.array(sorted({int(k) * ncol + int(c)
                                     for k, cs in base_p.one_way.items()
                                     for c in cs}), dtype=np.int64)
        coo = A1.tocoo()
        key = coo.row.astype(np.int64) * ncol + coo.col.astype(np.int64)
        lead = is_ow[coo.row] & ~np.isin(key, keep_keys)
        A1_lead = sp.csr_matrix((coo.data[lead], (coo.row[lead], coo.col[lead])),
                                shape=A1.shape)
        keep = ~lead
        A1 = sp.csr_matrix((coo.data[keep], (coo.row[keep], coo.col[keep])),
                           shape=A1.shape)
    hard_i = np.asarray(base_p.hard, dtype=np.int64)
    if fixed and drop is None and hard_i.size:
        # §20b STAGE 2's HARD SET (the census table): an AIRSIDE hard row
        # now carries no column — stage 1 enforced it and read it there, in
        # its own metre scaling — and its reduced row sum is 0, which the
        # scaling below cannot divide by.  Reading it here would report a
        # vertical-curve row in RAW units against ``hard_tol_m``.  Stage 2's
        # hard set is the rows that still carry a column; the report
        # COMBINES the two stages.
        rowsum0 = np.asarray(abs(A1).sum(axis=1)).ravel()
        hard_i = hard_i[rowsum0[hard_i] > 0.0]
    rep.hard_rows = int(hard_i.size)
    # THE HARD ROWS ARE SCALED TO METRES.  A law row is stated in its own
    # units: a grade cap's row is a Δz (metres), but a VERTICAL CURVE row is a
    # difference of grades (dimensionless), and a rate row a curvature.  One
    # constraint weight and one tolerance can only price them together if the
    # residual means the same thing, so each hard row (and its target) is
    # divided by ``Σ|c| / 2`` — 1 for a two-vertex Δz row, ``≈ d/2`` for a K
    # row, so every hard violation the report and the multipliers see is
    # METRES of surface.  Measured: without it a K row's penalty was ~1/d²
    # weaker than a transverse row's and the K law never closed (CYXY 0.0093
    # left at ρ = 3e6; spec §6 deviation 9).
    if hard_i.size:
        rowsum = np.asarray(abs(A1).sum(axis=1)).ravel()
        sc = np.ones(A1.shape[0])
        good = rowsum[hard_i] > 0.0
        sc[hard_i[good]] = 2.0 / rowsum[hard_i[good]]
        # THE READING IS THE ROW'S OWN METRES (lane ``surfacesettle``,
        # issues #21/#22).  ``sc`` above divides by the REDUCED row sum —
        # the free columns only, leaders split off — and that is the
        # solve's weight, left as it is.  But a row with one PINNED side
        # (a coverage-edge join, a stage-1 airside level) reduces to one
        # free term and reads DOUBLE, and a row whose free term is a
        # small interpolation weight reads up to 20x: GEML's worst row
        # read 3.5369 m where the surface misses it by 0.1719 m, TFFJ's
        # 13.6115 where it misses by 6.8058.  ``why-hard`` has always
        # scaled by the FULL term sum; the report's re-read now does too,
        # through :func:`hard_metres`, so the two readers are ONE.
        sc_red = sc.copy()
        A1 = sp.diags(sc) @ A1
        b1 = sc * b1
        A1 = A1.tocsr()
    rho = float(d.hard_weight)
    w_row = np.full(len(one), float(d.law))
    # THE PAD TARGETS FLAT (owner RULINGS 2026-09-09c): its flatness rows are
    # priced at ``pad_flat``, above the law's target weight and far below the
    # hard constraint weight — flat wherever a flat solution exists, tilting
    # (to at most the 1 % hard ceiling) where the contacts leave none.
    pad_i = np.asarray(base_p.pad_flat, dtype=np.int64)
    if pad_i.size:
        w_row[pad_i] = float(d.pad_flat)
    # THE FOOT ROWS ARE THE PAD LAW'S TARGET (owner RULINGS 2026-09-11ab,
    # spec §11b (2)): a body with no pad polygon states its placement
    # through its feet, so those rows pay the PAD's price, not the ADJACENT
    # GROUND's (round 7 at 3.0: 715 of 1,434 missed, 5.70 m; pair bar kept).
    fr_i = np.asarray(base_p.foot_row_i, dtype=np.int64)
    if fr_i.size:
        w_row[fr_i] = float(d.pad_flat)
    w_row[hard_i] = rho
    sw = np.sqrt(w_row)
    #: ``μ/ρ`` per one-sided row — zero everywhere but the hard rows, where it
    #: tightens the target by the multiplier the constraint has earned
    shift = np.zeros(len(one))
    tol = float(d.active_set_tol_m)
    x: np.ndarray | None = None
    z = np.zeros(n)
    t_solver = 0.0
    A, b = A0f, b0f
    active_i = np.zeros(0, dtype=np.int64)
    active: set[int] = set()

    def _stack(sel: np.ndarray) -> tuple[sp.csr_matrix, np.ndarray]:
        """The base rows plus the ACTIVE one-sided rows at their own weights
        (the law's for a target, ``ρ`` for a runway constraint) against their
        shifted targets."""
        if not sel.size:
            return A0f, b0f
        W = sp.diags(sw[sel])
        return (sp.vstack([A0f, W @ A1[sel]], format="csr"),
                np.concatenate([b0f, sw[sel] * (b1[sel] - shift[sel])]))

    def _settled(x_):    # §30 (3c): ONE derivation, ``design_report.settled_flip``
        return settled_flip(A1 @ x_ - (b1 - shift), tol, active)

    def _inner_qp(x0: np.ndarray | None) -> np.ndarray:
        """§20c: the SAME one-sided problem at the CURRENT multipliers,
        solved to its unique optimum (``solve/design_qp.py``) instead of
        iterated to a stall.  ``set_exits`` is the fixed point's instrument
        and stays empty here (the brief's item 3); the QP's own status,
        rounds, solves and wall are what the report prints."""
        nonlocal A, b, active, active_i, t_solver
        t1 = time.perf_counter()
        res = solve_one_sided(A0f, b0f, A1, b1, w_row, shift, x0, Ub, cb,
                              method=method, solver_tol=float(d.solver_tol),
                              solver_max_iter=int(d.solver_max_iter),
                              low_rank=low_rank,
                              rel_tol=float(d.qp_rel_tol), active_tol=0.0,
                              verbose=opt.verbose)
        t_solver += time.perf_counter() - t1
        active_i = np.flatnonzero(A1 @ res.x - (b1 - shift) > tol)
        active = set(active_i.tolist())
        A, b = _stack(active_i)
        rep.rows = int(A.shape[0]) + (0 if Ub is None else int(Ub.shape[0]))
        rep.note_qp(res.status, res.rounds, res.solves, res.objective,
                    res.grad_norm, res.wall_s)
        rep.rounds += res.rounds
        rep.converged = bool(res.status == "optimal" or res.status == "no_descent")
        rep.record_flip(_settled(res.x))
        return res.x

    def _inner_fixed_point(x0: np.ndarray | None) -> np.ndarray:
        """One damped active-set solve at the CURRENT multipliers."""
        nonlocal A, b, active, active_i, t_solver
        x_ = x0
        x_prev: np.ndarray | None = None
        f_prev = math.inf
        f_last = math.inf
        for rnd in range(1, int(d.active_set_max_rounds) + 1):
            A, b = _stack(active_i)
            rep.rows = int(A.shape[0]) + (0 if Ub is None else int(Ub.shape[0]))
            t1 = time.perf_counter()
            x_full = _linear_solve(A, b, x_, method, float(d.solver_tol),
                                   int(d.solver_max_iter), Ub, cb, low_rank)
            x_ = x_full
            t_solver += time.perf_counter() - t1
            # DAMPING (a semismooth Newton step with a backtracking line search
            # on the TRUE objective): the plain fixed point can cycle between
            # two active sets, and a cycling set is not a solution.  ``F`` is
            # convex and C¹, so a step that does not decrease it is halved.
            if x_prev is not None:
                f_new = _objective(A0f, b0f, A1, b1, w_row, shift, x_, Ub, cb)
                alpha = 1.0
                while f_new > f_prev and alpha > _ALPHA_FLOOR:
                    alpha *= 0.5
                    x_ = x_prev + alpha * (x_full - x_prev)
                    f_new = _objective(A0f, b0f, A1, b1, w_row, shift, x_, Ub, cb)
                if f_new > f_prev:
                    x_ = x_prev          # the step buys nothing: this is it
                    rep.note_set_exit("line_search_stalled", rnd, len(active))
                    rep.converged = rep.record_flip(_settled(x_))
                    rep.rounds += rnd
                    return x_
                f_prev = f_new
            else:
                f_prev = _objective(A0f, b0f, A1, b1, w_row, shift, x_, Ub, cb)
            x_prev = x_.copy()
            viol = A1 @ x_ - (b1 - shift)
            nxt_i = np.flatnonzero(viol > tol)
            nxt = set(nxt_i.tolist())
            # SETTLED (§30 (3c), ONE derivation in ``_settled``): the same set,
            # or a flip every row of which hovers at its own bound.  The
            # objective STALLING is an exit, NOT settlement — it fires with
            # thousands of rows still crossing their bounds by metres.
            same = nxt == active
            stall = float(d.set_stall_tol)
            if same or (stall > 0.0 and f_prev < math.inf and
                        abs(f_last - f_prev) <= stall * max(1.0, f_prev)):
                rep.note_set_exit("same_set" if same else "objective_stalled",
                                  rnd, len(nxt ^ active))
                rep.converged = rep.record_flip(_settled(x_))
                rep.rounds += rnd
                return x_
            if opt.verbose:
                print(f"    [design] round {rnd}: F {f_prev:.6g}  active {len(nxt)} "
                      f"(was {len(active)}, changed {len(nxt ^ active)})")
            f_last = f_prev
            active, active_i = nxt, nxt_i
        rep.converged = False            # the round cap: NEVER settlement
        rep.note_set_exit("round_cap", int(d.active_set_max_rounds), len(active))
        rep.record_flip(_settled(x_) if x_ is not None else (False, 0, 0.0))
        rep.rounds += int(d.active_set_max_rounds)
        return x_ if x_ is not None else np.zeros(red.n_cols)

    #: §20c ``[design] solver``: ONE dispatch, so the lag, the multiplier
    #: polish, both projections and every counter below are the same code
    #: on either arm and the pair is matched by construction.
    _inner = (_inner_qp if str(d.solver) == "qp" else _inner_fixed_point)

    # THE WARM-UP: the one-way rows are OFF for the first solve (their
    # leaders have no value yet), then lagged from the surface it gives.
    if ow_i.size:
        shift[ow_i] = -_LAG_OFF
        rep.one_way_settled = False
    x = _inner(None)

    # PHASE B — THE LAG IS A CONVERGENCE CONDITION (09-09b (2)/(3); §20a,
    # RULINGS 2026-09-13ac).  The one-way leaders are re-read from the
    # surface, UNDER-RELAXED by ``one_way_relax`` (the plain fixed point
    # does not contract), and the set re-solved — to ``one_way_tol_m`` or
    # to a NAMED failure, always BEFORE the multipliers (interleaved, each
    # lag round undid the previous one and the runway laws drifted OUT:
    # HECA, a 0.52 m ``runway_transverse`` DEFECT).  ``one_way_max_rounds``
    # is a SAFETY CEILING, and its hit is that named failure: the polish
    # ran inside an unconverged lag at LEMD and the wobble crossed
    # ``hard_tol_m`` (13ac).
    theta = float(d.one_way_relax)
    dmove = np.zeros(0)
    for outer in range(1, (int(d.one_way_max_rounds) if ow_i.size else 0) + 1):
        target = np.asarray(A1_lead @ x).ravel()[ow_i]
        cur = shift[ow_i]
        new_shift = target if outer == 1 else cur + theta * (target - cur)
        dmove = (np.abs(new_shift - cur) if outer > 1
                 else np.full(ow_i.size, math.inf))
        move = float(np.max(dmove)) if dmove.size else 0.0
        shift[ow_i] = new_shift
        rep.one_way_rounds = outer
        rep.one_way_move_m = 0.0 if move == math.inf else move
        x = _inner(x)                  # always solve AT the shift just set
        if opt.verbose:
            print(f"    [design/lag] round {outer}: worst leader move "
                  f"{rep.one_way_move_m:.4f} m")
        if move <= float(d.one_way_tol_m):
            rep.one_way_settled = True
            break
    if ow_i.size and not rep.one_way_settled:       # §20a: NAME the failure
        rep.read_lag_failure(ow_i, dmove, float(d.one_way_tol_m),
                             int(d.one_way_max_rounds), one, base_p.one_way,
                             planar)

    miss, sc_m = promote_missed(one, hard_i, A1, b1, A1_lead, x, law, rep)
    if miss.size:          # RULINGS 2026-09-30bj: a missed body chord joins the hard set
        A1, b1 = (sp.diags(sc_m) @ A1).tocsr(), sc_m * b1
        sc_red = (sc_red if hard_i.size else np.ones(len(one))) * sc_m
        hard_i, base_p.hard = np.concatenate([hard_i, miss]), [*base_p.hard, *miss.tolist()]
        w_row[miss] = rho
        sw = np.sqrt(w_row)
    # PHASE C — THE HARD ROWS' MULTIPLIERS, the lag now FROZEN (spec §6
    # deviation 7; owner RULINGS 2026-09-09r (3)).  Runs to ``hard_tol_m``
    # or ``polish_rounds_max``; the sequence is NOT monotone (it oscillates
    # while the one-sided set re-forms), so a flat round ends nothing, the
    # BEST iterate is returned, and the cap's hit is a NAMED failure.
    # ``law/emit.toml`` [design] carries the measurements.
    if hard_i.size:
        Ah, bh = A1[hard_i], b1[hard_i]
        mu = np.zeros(hard_i.size)
        tol_h = float(d.hard_tol_m)
        worst = float(np.max(np.maximum(Ah @ x - bh, 0.0)))
        best_x, best_worst = x, worst
        for pr in range(1, int(d.polish_rounds_max) + 1):
            if not hard_exceeds(worst, tol_h):
                break
            rep.hard_rounds = pr
            mu = np.maximum(0.0, mu + rho * (Ah @ x - bh))
            shift[hard_i] = mu / rho
            x = _inner(x)
            worst = float(np.max(np.maximum(Ah @ x - bh, 0.0)))
            if worst < best_worst:
                best_x, best_worst = x, worst
            if opt.verbose:
                print(f"    [design/hard] multiplier round {pr}: "
                      f"{int(np.count_nonzero(mu > 0.0))} hard rows carry a "
                      f"multiplier, max hard violation {worst:.5f} m")
            if not hard_exceeds(worst, tol_h):
                break
        if best_worst < worst:
            x, worst = best_x, best_worst      # never return a worse surface
        rep.hard_active = int(np.count_nonzero(mu > 0.0))
        rep.hard_max_violation_m = worst
        rep.hard_settled = not hard_exceeds(worst, tol_h)
        if hard_exceeds(worst, tol_h):
            k = int(np.argmax(Ah @ x - bh))
            rep.hard_worst = one[int(hard_i[k])][2].source.ruling[:70]
    # PHASE D — THE FINAL PROJECTION (owner RULINGS 2026-09-09y, closing
    # 09v (3)).  The Lagrangian above cannot CERTIFY the hard set, so every
    # non-runway vertex is FIXED and the runway family re-solved as a small
    # QP holding its hard rows exactly (``solve/project.py``, which carries
    # the rationale and §32 (4)'s purity test).
    if x is not None:
        # ... then PHASE E, the ZONE projection (12ag, §32): one entry,
        x, rep.runway_projection, rep.zone_projection = project_after_solve(
            planar, law, base_p, x, stacked=(A1, b1), verbose=opt.verbose)
        # RE-READ AFTER THE PROJECTION (§30 (3b), ``rep.read_hard_set``): its
        # own rows are held exactly now; what is left is what it does not own.
        if hard_i.size:
            # in the row's OWN metres (``hard_metres``): un-scale the
            # solve's reduced reading, put the lagged leader terms back
            # (the matrix the solve factorises holds only the followers)
            raw_h = (A1[hard_i] @ x - b1[hard_i]) / sc_red[hard_i]
            if A1_lead is not None:
                raw_h = raw_h + np.asarray(A1_lead[hard_i] @ x).ravel()
            viol_h = np.maximum(hard_metres(one, hard_i, raw_h), 0.0)
            worst = rep.read_hard_set(
                viol_h, float(d.hard_tol_m),
                lambda k: one[int(hard_i[k])][2].source.ruling[:70])
            # §20a: a cap's hit is a NAMED failure, never a silent stop —
            # and for the HARD set the name must say whether what is left
            # is a residual the solve owes or a set of rows NO SURFACE
            # satisfies (lane ``v2settle``; the brief's (b), owner
            # RULINGS 13y (B) / 13ab / 14as).
            if not rep.hard_settled:
                z_now = np.where(red.col >= 0, x[np.clip(red.col, 0, None)],
                                 red.value)
                rep.read_hard_failure(hard_i, viol_h, one, planar, red,
                                      float(d.hard_tol_m), z_now)
    if x is not None:
        z = np.where(red.col >= 0, x[np.clip(red.col, 0, None)], red.value)
        runway_after(rep, one, z, law)     # RULINGS 2026-09-30bj (1)
    if levelled_out is not None and x is not None:
        for vid in range(n):
            col = int(red.col[vid])
            if col >= 0 and col not in unlevelled:
                levelled_out[vid] = float(z[vid])
    rep.solver_wall_s = t_solver

    # 11. the residual per family (a missed TARGET, not a demotion)
    fam: dict[str, dict[str, _t.Any]] = {}
    # the REPORTED violation is the row's TRUE one — the one-way rows'
    # leader columns are back for the reading (they are lagged only in the
    # matrix the solve factorises)
    viol_all = (A1 @ x - b1) if x is not None else np.zeros(len(one))
    if x is not None and A1_lead is not None:
        viol_all = viol_all + np.asarray(A1_lead @ x).ravel()
    tol = float(d.active_set_tol_m)
    for k, (_terms, _hi, row) in enumerate(one):
        g = row.source.generator
        rec = fam.setdefault(g, {"rows": 0, "missed": 0, "max_m": 0.0, "energy": 0.0})
        rec["rows"] += 1
        v = float(viol_all[k])
        if v > tol:
            rec["missed"] += 1
            rec["max_m"] = max(rec["max_m"], v)
            rec["energy"] += d.law * v * v
    for terms, hi, row in eqs:
        g = row.source.generator
        rec = fam.setdefault(g, {"rows": 0, "missed": 0, "max_m": 0.0, "energy": 0.0})
        rec["rows"] += 1
        v = abs(sum(c * float(z[vid]) for vid, c in terms) - hi)
        if v > float(d.active_set_tol_m):
            rec["missed"] += 1
            rec["max_m"] = max(rec["max_m"], v)
            rec["energy"] += d.law * v * v
    for rec in fam.values():
        rec["max_m"] = round(rec["max_m"], 4)
        rec["energy"] = round(rec["energy"], 3)
    rep.families = dict(sorted(fam.items()))
    rep.foot_row_diag = foot_row_diagnostic(one, viol_all, base_p.foot_row_i, red.col)
    # THE PUBLISHED TARGETS: every row missed beyond the elevation
    # materiality, with its vertices' canonical identities (RULINGS
    # 2026-09-08t: "a target missed is a row, the census counts it")
    mat = float(law.tables.emit.materiality.elevation_m)
    tgt: list[dict[str, _t.Any]] = []
    for k, (terms, _hi, row) in enumerate(one):
        v = float(viol_all[k])
        if v <= mat:
            continue
        tgt.append({"family": row.source.generator, "miss_m": round(v, 4),
                    "ll": [[planar.vertices[vid].key[0], planar.vertices[vid].key[1]]
                           for vid, _c in terms]})
    rep.targets = tgt
    obj = float(np.sum((A @ x - b) ** 2)) if x is not None else 0.0
    rep.terms = _term_energies(rows, A, b, x)
    if Ub is not None and x is not None:
        rep.terms["body_datum"] = round(float(np.sum((Ub @ x - cb) ** 2)), 3)
        rep.terms = dict(sorted(rep.terms.items()))
    # EACH BODY'S DATUM RESIDUAL (owner RULINGS 2026-09-10p): the solved
    # mean of the body's own vertices against the mean production DEM
    # under them — the number the owner's CYXY read is about.
    rep.body_datums = [
        {"kind": m.kind,
         "ll": [planar.vertices[m.vertices[0]].key[0],
                planar.vertices[m.vertices[0]].key[1]],
         "vertices": len(m.vertices),
         "rows": m.rows,
         "dem_mean_m": round(m.dem_mean, 3),
         "residual_m": round(
             sum(float(z[v]) for v in m.vertices) / len(m.vertices)
             - m.dem_mean, 3),
         "tilt_m": round(max((abs(sum(w * float(z[v]) for v, w in coefs) - rhs)
                              for name, coefs, rhs in _plane_rows(
                                  planar, m.vertices,
                                  [float(planar.vertices[v].dem_z)
                                   for v in m.vertices])
                              if name != "mean"), default=0.0), 3)}
        for m in base_p.body_meta]
    if size_out is not None:
        size_out.update({"columns": red.n_cols, "z": n, "rows": rep.rows,
                         "nnz": int(A.nnz), "triangles": rep.triangles,
                         "chord_vertices": chord_v, "road_fit_vertices": road_v,
                         "one_way_rows": rep.one_way_rows,
                         "ground_datum_rows": rep.ground_datum_rows,
                         "foot_rows": rep.foot_rows,
                         "active": len(active), "rounds": rep.rounds})
    cert = residual(cs, z, obj)
    wall = time.perf_counter() - t0
    return (Solution(z=tuple(float(v) for v in z),
                     status=Status.OPTIMAL if rep.converged else Status.FEASIBLE,
                     residual=cert, iterations=rep.rounds, wall_s=wall,
                     message=f"design surface: {rep.rounds} active-set round(s), "
                             f"{red.n_cols} unknowns, {rep.rows} rows, "
                             f"{method}"), rep)
