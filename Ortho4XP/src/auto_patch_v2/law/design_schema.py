"""emit.toml ``[design]`` — the SCHEMA of THE DESIGN SURFACE's objective
(owner RULINGS 2026-09-08t; spec ``auto-patch-v2/design-surface-spec.md``),
split from ``model.py`` by the 1,000-line file law and re-exported there.
A frozen dataclass and the table's own validation; no numeric value
appears here (the values live in the TOML).  Imports nothing from v2.

Replaces ``[relaxation]`` (``Relaxation``) and ``[yield]``
(``yield_schema.Yield``), both deleted with the tier / IIS / relaxation /
yield machinery they priced.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["Design", "DESIGN_TERMS", "BEND_CLASSES", "check_design"]

#: The objective's terms, in the order the report prints them.  Each is a
#: weight: the price of one metre of that residual (bending is metres of
#: integrated curvature, every other term metres of elevation).
DESIGN_TERMS: tuple[str, ...] = ("bend_runway", "bend_taxi", "bend_apron",
                                 "bend_strip", "bend_road", "chord", "law",
                                 "taxi_profile", "taxi_trend", "road",
                                 "detached_mean", "body_datum", "apron_trend",
                                 "ground_datum", "set_stall_tol")

#: The BENDING CLASSES (RULINGS 2026-09-08v), in the seniority order a
#: vertex touched by two of them is priced under: a vertex of a runway face
#: bends at ``bend_runway`` even where a strip shares it.  Each names the
#: ``[design] bend_<class>`` weight.
BEND_CLASSES: tuple[str, ...] = ("runway", "taxi", "apron", "road", "strip")


@_dc.dataclass(frozen=True)
class Design:
    """The design surface's weights and the active-set iteration's limits.

    ONE sparse least-squares problem (``solve/design.py``): thin-plate
    bending over each connected pavement complex, the runway chord per
    ridge station, every law row as a one-sided quadratic penalty, the DEM
    fit only on the zone rings, roads as smooth chains.  A weight is the
    price of a metre of that term's residual, relative to ``bend``.
    """

    bend_runway: float
    bend_taxi: float
    bend_apron: float
    bend_strip: float
    bend_road: float
    chord: float
    #: THE RUNWAY PROFILE FOLLOWS THE AIRPORT (owner RULINGS 2026-09-10q/
    #: 10r, ruled 10t (3); spec §21): the ``chord`` row's TARGET is the
    #: ground's long-wave trend along the ridge — a moving QUADRATIC
    #: least-squares fit of the production DEM over +/- this window,
    #: shifted by the linear correction that puts it through the two
    #: threshold pins.  The window is the scale of the law: at or above the
    #: largest ruleset ``runway.vertical_curve_k_m`` the target carries only
    #: curvature the K law admits, so the runway bends with the ground's
    #: trend and never undulates with the ground itself (08t (1) / 09b).
    runway_profile_window_m: float
    #: §50.1 (3) THE MARGIN ON A YIELDED RUNWAY CAP (owner RULINGS
    #: 2026-09-18d (3)): where a runway's own HARD PINS demand more grade
    #: than ``rulesets.runway.longitudinal`` allows, that runway's
    #: effective cap is its pin-to-pin grade plus this margin — the
    #: smallest uniform over-grade that FITS (at ``cap == g_pin`` exactly
    #: the feasible set is one straight line, on the LP's own tolerance).
    #: Derived in ``constraints/runway_yield.py``; a value, not a switch.
    runway_yield_margin: float
    law: float
    #: THE TAXI DESIGN PROFILE (owner RULINGS 2026-09-09b (2), "taxiways
    #: should follow terrain less and be more like runways"): the second
    #: difference of z along every taxi CENTRELINE chain, as a strong
    #: curvature target — the runway K pattern read as an objective term
    taxi_profile: float
    #: THE TAXI CHAIN'S TARGET PROFILE (owner RULINGS 2026-09-10v (1);
    #: spec §8.6): the ground's LONG-WAVE TREND along every taxi centreline
    #: chain — the §21 construction at the same window key, shifted
    #: linearly through the chain's runway contacts — as a WEAK level
    #: target per chain vertex (``constraints/taxi_trend.py``, published
    #: through ``PlanarMap.taxi_trend_z``).  Below ``body_datum``: the
    #: trend says WHERE a taxiway runs, and every law, the body plane and
    #: the curvature row all outrank it.  This REPLACES the taxi body mean
    #: row of 10p, which 10v measured as too coarse.
    taxi_trend: float
    #: THE TREND'S REACH ACROSS THE FACE (spec §8.6.1, round 3): a
    #: taxi-family vertex OFF the centreline takes the same ``taxi_trend``
    #: row, valued at the station of its foot on the nearest centreline
    #: chain — within this plan distance.  Past it the vertex is left free
    #: rather than pulled to a chain it does not belong to.  It is a REACH,
    #: not a law value: it bounds which chain may speak for a vertex.
    taxi_trend_face_reach_m: float
    road: float
    #: §20a THE ACTIVE SET'S STALL EXIT (lane ``v2settle`` r2, owner RULINGS
    #: 2026-09-14br).  The damped active-set iteration ends when the set
    #: REPEATS (its fixed point) or when the objective stops falling by this
    #: RELATIVE amount.  The second is a stall, not a solution, and the
    #: module's own comment says so — yet at HECA every one of the six
    #: damped solves exits on it and NONE on the fixed point, which is why a
    #: perturbation at one vertex lands the far field somewhere else.  A law
    #: value so the arm is measurable; 0 disables the stall exit and leaves
    #: ``active_set_max_rounds`` as the only ceiling.
    set_stall_tol: float
    detached_mean: float
    #: THE PER-BODY DATUM (owner RULINGS 2026-09-09p (3), refining 08t
    #: answer 6): every APRON BODY — a connected group of faces whose
    #: bending class is ``apron`` — carries ONE weak row saying its MEAN z
    #: is the MEAN production DEM under its own vertices.  Never per
    #: vertex: the body keeps its designed (bent) shape and only its LEVEL
    #: is told where the ground is, so a body up the hill sits up the hill
    #: and the taxiways climb between bodies at their caps instead of the
    #: whole complex being cut into the hill toward the runway's level.
    #: The runway and taxi families are excluded (they carry the threshold
    #: chord and the taxi design profile).
    body_datum: float
    #: THE APRON BODY'S 2-D TREND (owner RULINGS 2026-09-10ar; spec §8.7):
    #: an apron body whose plan DIAMETER exceeds
    #: ``runway_profile_window_m`` takes ONE row per vertex against the
    #: ground's 2-D long-wave trend under it — a moving quadratic SURFACE
    #: fit of the production DEM over that window — INSTEAD of the three
    #: affine ``body_datum`` rows, which a plane-sized body keeps.  Weak,
    #: at ``taxi_trend``'s price: it says WHERE the apron sits, never how
    #: smoothly, and every law row outranks it.
    apron_trend: float
    #: THE GROUND'S OWN DATUM (owner RULINGS 2026-09-10av; spec §23): every
    #: ADJACENT-GROUND vertex — the ``graded_strip`` family, never a pavement
    #: vertex and never an interior pocket enclosed by pavement (09g (1)) —
    #: carries ONE WEAK row ``z = DEM`` at this weight while its law rows stay
    #: one-sided and ONE-WAY.  The strip therefore EQUALS the natural ground
    #: wherever the ground satisfies the zone law relative to its pavement and
    #: is cut or filled only where a law row binds.  Strictly BELOW ``law``:
    #: a datum that outpriced a law row would cut where the law says fill.
    ground_datum: float
    #: THE PAD PLANE (owner RULINGS 2026-09-09c): a pad's flatness is a
    #: STRONG TARGET (it is no longer a hard ``Flat`` merge), and its tilt
    #: is bounded hard at ``emit.within_shape.pad_slope_max``.
    #: ``pad_flat_rulings`` names the ruling HEADS priced at ``pad_flat``
    #: instead of ``law`` — one register, the same shape as
    #: ``hard_rulings`` / ``one_way_rulings``.
    #: THE FOOT ROWS (owner RULINGS 2026-09-11q, repriced 11ab; spec
    #: §11b (2)): the ruling HEADS whose rows are priced at ``pad_flat``
    #: instead of ``law`` — a bare-ground body's per-foot target, which
    #: IS the pad law's target for a body with no pad polygon.  A
    #: register of its own, not ``pad_flat_rulings``, because the report
    #: counts the two classes apart.  May be empty (the class disarmed).
    foot_row_rulings: tuple[str, ...]
    pad_flat: float
    pad_flat_rulings: tuple[str, ...]
    #: THE PAD TAKES THE PAVEMENT'S EDGE LEVEL (owner RULINGS 2026-09-10l,
    #: 10k-1 = (A)): the ruling HEADS of a pad's frontage LEVEL rows.  A
    #: vertex such a row GOVERNS (its ``follows``) is a pad following the
    #: pavement, so ``solve/design`` §9b takes it out of every per-body
    #: DEM datum mean — a pad's own datum (09p (3)) is for a pad that
    #: fronts NO pavement.
    pad_level_rulings: tuple[str, ...]
    #: A PAD FRONTS BY PROXIMITY (owner RULINGS 2026-09-10ax (1)): the
    #: plan distance within which a pad EDGE fronts a pavement EDGE,
    #: shared vertex or not.  ``constraints.pads.frontage_radius_m`` is
    #: the one derivation site; 0 leaves the identity-only read of 10l.
    pad_frontage_m: float
    #: §28 (6) A HILLSIDE TERRACE IS NOT A FRONTAGE (owner RULINGS
    #: 2026-09-13o/13p): the PER-PAIR median DEM step above which a pad's
    #: groundside neighbour keeps its own ground and mints no frontage
    #: row.  ``constraints.pad_frontage_gs.frontage_step_max_m`` is the one
    #: derivation site; 0 disables the bound.
    frontage_step_max_m: float
    #: jetway-strip spec §1 (2) / §2 (owner RULINGS 2026-09-18t Q3): the
    #: plan distance D from a 23a pad's RIDER EDGE within which the apron
    #: is ONE level (``constraints.jetway_strip.strip_m`` is the one
    #: derivation site; 0 disarms the strip).
    jetway_strip_m: float
    #: spec-author ruling Q-32d (i): a strip forms only on a pad whose
    #: stage-1 airside frontage fits its plane within this (max residual,
    #: metres); elsewhere the 23a weld alone governs.
    jetway_strip_plane_tol_m: float
    #: THE BANK (owner RULINGS 2026-09-09e; spec §9): the patch's own
    #: embankment out to the DEM, because the mesh does not blend.
    #: ``bank_slope`` is the bank's grade (0.33 = 1:3), ``bank_min_width_m``
    #: the narrowest bank, ``bank_foot_smooth`` the second-difference
    #: weight along the foot chain that keeps the toe from zigzagging.
    bank_slope: float
    bank_min_width_m: float
    bank_foot_smooth: float
    #: THE DAYLIGHT LINE (owner RULINGS 2026-09-09g; spec §11): the foot is
    #: the civil-engineering DAYLIGHT (catch) POINT, not the smooth-ground
    #: fixed point — walking outward in ``bank_sample_m`` stations, the first
    #: station where the design slope line meets the DEM within
    #: ``bank_daylight_tol_m``, clamped to ``[bank_min_width_m,
    #: bank_max_width_m]``.  ``bank_toe_break_m`` is the jump in raw daylight
    #: distance between neighbours that CUTS the toe's plan smoothing: the
    #: toe may jump where the ground does.
    #: §37 (3) THE BANK IS EMITTED WHERE IT IS LOAD-BEARING (owner
    #: RULINGS 2026-09-13q item 8): the longest chord of an emitted foot
    #: chain, and the mid-chord stand-off that splits one further.  The
    #: materiality floor itself is DERIVED (``bank_materiality_m``,
    #: ``emit/bank.py``), never typed.
    bank_chord_max_m: float
    bank_split_tol_m: float
    #: THE OMIT ARM (owner request 2026-09-13, via the round's
    #: coordinator: "can we please try completely omitting the bank_foot
    #: shapes altogether to confirm they're necessary?").  ``true`` and
    #: the bank pass emits NOTHING at all.  A MEASUREMENT ARM, default
    #: ``false``; it is deleted the moment the owner rules on the
    #: bank_foot class (13ce / 13cm).  It is a law key and not an
    #: environment gate because ``auto_patch_v2`` reads no environment
    #: by design (``tests/auto_patch_v2/test_model.py``).
    bank_omit: bool
    bank_sample_m: float
    bank_daylight_tol_m: float
    bank_max_width_m: float
    bank_toe_break_m: float
    #: THE MESH MUST HAVE VERTICES TO CARRY THE BLEND (owner RULINGS
    #: 2026-09-09x; spec §13.8).  The bank annulus is handed to Triangle
    #: as a REGION whose maximum triangle area is ``(w / this) ** 2`` for
    #: a local bank width ``w`` — the bank is divided into about this
    #: many triangles across, so the exact ruled field
    #: ``O4_Mesh_Utils.bank_annulus_blend_values`` writes has vertices to
    #: be carried on.
    bank_triangle_divisions: float
    #: THE TERRAIN EDGE (owner RULINGS 2026-09-10b/10c; spec §19): the
    #: adjacent-ground rings END at the physical edge — the CREST where
    #: the DEM's outward downhill slope over ``edge_probe_m`` exceeds
    #: ``bank_slope`` and drops more than ``edge_min_drop_m``, found on an
    #: ``edge_grid_m`` raster; or, where a road runs within
    #: ``edge_road_snap_m`` inside that crest over at least
    #: ``edge_road_run_m``, flush at that road's outer edge.  Beyond the
    #: edge: no patch, no bank, the DEM.
    edge_probe_m: float
    edge_min_drop_m: float
    edge_grid_m: float
    edge_road_snap_m: float
    edge_road_run_m: float
    #: THE ADJACENT GROUND FOLLOWS THE PAVEMENT, NEVER PULLS IT (owner
    #: RULINGS 2026-09-09b (2)/(3)): the ruling heads whose rows are priced
    #: ONE-WAY — the row's ``follows`` vertex stays in the matrix and every
    #: other foot enters the right-hand side at its previous outer-round
    #: value.  ``one_way_max_rounds`` / ``one_way_tol_m`` bound that lag
    one_way_rulings: tuple[str, ...]
    one_way_max_rounds: int
    one_way_tol_m: float
    one_way_relax: float
    #: the one-sided penalties' active-set iteration (module docstring of
    #: ``solve/design.py``)
    #: the ruling heads whose rows are HARD constraints of the active set
    #: (RULINGS 2026-09-08v: the runway family's transverse, vertical curve
    #: K and max grade), enforced exactly — never one-sided targets
    hard_rulings: tuple[str, ...]
    hard_weight: float
    #: THE HARD SET MUST SETTLE (owner RULINGS 2026-09-09r (3)): the polish
    #: iterates the augmented-Lagrangian multipliers until EVERY hard row is
    #: within ``hard_tol_m``, or until ``polish_rounds_max`` rounds are
    #: spent — in which case the report names the failure, never "not
    #: settled" in a shipped patch.  A round that buys less than one
    #: tolerance no longer ENDS the loop (round 1's rule): the multiplier
    #: sequence oscillates while the one-sided active set re-forms, so the
    #: first flat round is nowhere near the answer.
    polish_rounds_max: int
    hard_tol_m: float
    #: THE FINAL PROJECTION (owner RULINGS 2026-09-09y): after the
    #: design solve, every non-runway vertex is fixed and the runway
    #: family's vertices are re-solved as a QP holding every
    #: runway-family hard row EXACTLY (``solve/project.py``), because
    #: the augmented Lagrangian above cannot certify them.  ``false``
    #: is the diagnostic arm and is never shipped.
    runway_projection: bool
    #: THE ZONE PROJECTION (Fable 2026-09-12, RULINGS 2026-09-12ag; spec
    #: §32): after the runway projection, every adjacent-ground zone
    #: vertex is CLAMPED into its own one-way corridor band — a pure
    #: per-vertex projection against feet the solve has already fixed,
    #: no LP.  ``false`` is the diagnostic arm and is never shipped.
    zone_projection: bool
    #: §20b THE STAGED SOLVE (owner RULINGS 2026-09-13dh, ordered
    #: 2026-09-14an): stage 1 solves the AIRSIDE PAVEMENT problem alone,
    #: stage 2 the whole problem with every airside column stage 1
    #: levelled substituted as a CONSTANT — so "airside is king" is an
    #: architecture, not a price.  ``false`` is the single solve, the
    #: DIAGNOSTIC ARM the staged arm is matched against.
    staged_solve: bool
    #: §20c THE ONE-SIDED PROBLEM IS SOLVED AS A CONVEX QP (Fable
    #: 2026-09-14, RULINGS 2026-09-14bw): ``"fixed_point"`` is the damped
    #: active-set iteration (``set_stall_tol`` above describes how it
    #: ends), ``"qp"`` solves the same convex QP to its unique optimum
    #: (``solve/design_qp.py``).  The solver is not a weight and buys no
    #: law: it decides whether the surface IS the minimum of the objective
    #: every law row is priced into, or a point 1.5 % above it.
    solver: str
    active_set_max_rounds: int
    active_set_tol_m: float
    solver_tol: float
    solver_max_iter: int

    def weight(self, term: str) -> float:
        """The weight of one objective term (``DESIGN_TERMS``)."""
        return float(getattr(self, term))

    def bend(self, cls: str) -> float:
        """The bending weight of one class (``BEND_CLASSES``)."""
        return float(getattr(self, f"bend_{cls}"))


def check_design(d: Design, err: type[Exception],
                 max_vertical_curve_k_m: float | None = None) -> None:
    """Every weight positive and finite, every limit positive.

    ``max_vertical_curve_k_m`` is the largest ``runway.vertical_curve_k_m``
    of ANY loaded ruleset — passed in by ``law/model._check_cross_refs``
    (this module imports nothing from v2), because
    ``runway_profile_window_m`` is only lawful at or above it: a shorter
    window would fit curvature the K law forbids and hand the solve a
    target it must refuse (spec §21.2 (1))."""
    for term in DESIGN_TERMS:
        w = d.weight(term)
        if not (w > 0.0) or w != w or w in (float("inf"), float("-inf")):
            raise err(f"emit.design.{term} {w}: a positive, finite weight")
    if not d.runway_profile_window_m > 0.0:
        raise err(f"emit.design.runway_profile_window_m "
                  f"{d.runway_profile_window_m}: positive metres — the "
                  f"half-window of the runway profile's trend fit (§21)")
    if (max_vertical_curve_k_m is not None
            and d.runway_profile_window_m < max_vertical_curve_k_m):
        raise err(f"emit.design.runway_profile_window_m "
                  f"{d.runway_profile_window_m}: at or above the largest "
                  f"rulesets.*.runway.vertical_curve_k_m "
                  f"{max_vertical_curve_k_m} — a shorter window fits "
                  f"curvature the K law forbids (RULINGS 2026-09-10t (3))")
    if not 0.0 <= d.runway_yield_margin < 1.0:
        raise err(f"emit.design.runway_yield_margin {d.runway_yield_margin}: "
                  f"a grade in [0, 1) — the margin a YIELDED runway cap "
                  f"carries over its pin-to-pin grade (§50.1 (3))")
    if d.one_way_max_rounds < 1:
        raise err(f"emit.design.one_way_max_rounds {d.one_way_max_rounds}: at least 1")
    if not 0.0 < d.one_way_relax <= 1.0:
        raise err(f"emit.design.one_way_relax {d.one_way_relax}: an "
                  f"under-relaxation factor in (0, 1]")
    if not d.one_way_tol_m > 0.0:
        raise err(f"emit.design.one_way_tol_m {d.one_way_tol_m}: positive metres")
    if not d.ground_datum > 0.0:
        raise err(f"emit.design.ground_datum {d.ground_datum}: a positive "
                  "weight — the adjacent ground's own DEM datum (09-10av)")
    if not d.ground_datum < d.law:
        raise err(f"emit.design.ground_datum {d.ground_datum}: strictly below "
                  f"the law's weight {d.law} — the ground FOLLOWS its law and "
                  "is cut or filled where a row binds (RULINGS 2026-09-10av)")
    if not d.pad_flat_rulings:
        raise err("emit.design.pad_flat_rulings: at least one ruling "
                  "(RULINGS 2026-09-09c: the pad's flatness is a target)")
    if d.frontage_step_max_m < 0.0:
        raise err(f"emit.design.frontage_step_max_m {d.frontage_step_max_m}: "
                  "a DEM step in metres, never negative (owner RULINGS "
                  "2026-09-13o/13p)")
    if d.jetway_strip_m < 0.0:
        raise err(f"emit.design.jetway_strip_m {d.jetway_strip_m}: a plan "
                  "distance in metres, never negative (jetway-strip spec §1 (2))")
    if d.pad_frontage_m < 0.0:
        raise err(f"emit.design.pad_frontage_m {d.pad_frontage_m}: a plan "
                  "distance in metres, never negative (owner RULINGS "
                  "2026-09-10ax (1))")
    if not d.pad_flat > d.law:
        raise err(f"emit.design.pad_flat {d.pad_flat}: heavier than the law's "
                  f"target weight {d.law} — a pad targets FLAT (09-09c)")
    shared = [r for r in d.foot_row_rulings if r in d.pad_flat_rulings]
    if shared:
        raise err(f"emit.design.foot_row_rulings {shared}: also in "
                  "pad_flat_rulings — the two classes carry the same PRICE "
                  "but stay DISTINCT heads, because the report counts them "
                  "apart (RULINGS 2026-09-11ab)")
    if not d.pad_level_rulings:
        raise err("emit.design.pad_level_rulings: at least one ruling "
                  "(RULINGS 2026-09-10l: the pad takes the pavement's edge "
                  "level and its own DEM datum only where it fronts none)")
    missing = [r for r in d.pad_level_rulings if r not in d.one_way_rulings]
    if missing:
        raise err(f"emit.design.pad_level_rulings {missing}: every level "
                  f"ruling must also be in one_way_rulings — the pad FOLLOWS "
                  f"the pavement and never pulls it (RULINGS 2026-09-10l)")
    if d.bank_chord_max_m <= d.bank_min_width_m:
        raise err(f"emit.design.bank_chord_max_m {d.bank_chord_max_m}: the "
                  "foot chord limit must exceed bank_min_width_m (the split "
                  "floor)")
    if d.bank_split_tol_m <= 0.0:
        raise err(f"emit.design.bank_split_tol_m {d.bank_split_tol_m}: a "
                  "positive mid-chord stand-off")
    if not 0.0 < d.bank_slope <= 1.0:
        raise err(f"emit.design.bank_slope {d.bank_slope}: a bank grade in (0, 1]")
    if not d.bank_min_width_m > 0.0:
        raise err(f"emit.design.bank_min_width_m {d.bank_min_width_m}: positive metres")
    if not d.bank_foot_smooth > 0.0:
        raise err(f"emit.design.bank_foot_smooth {d.bank_foot_smooth}: a positive weight")
    if not d.bank_sample_m > 0.0:
        raise err(f"emit.design.bank_sample_m {d.bank_sample_m}: the daylight "
                  "walk's station, positive metres (09-09g)")
    if not d.bank_daylight_tol_m > 0.0:
        raise err(f"emit.design.bank_daylight_tol_m {d.bank_daylight_tol_m}: "
                  "the slope line MEETS the DEM within this, positive metres")
    if not d.bank_max_width_m > d.bank_min_width_m:
        raise err(f"emit.design.bank_max_width_m {d.bank_max_width_m}: wider "
                  f"than bank_min_width_m {d.bank_min_width_m} — the daylight "
                  "walk has to have somewhere to walk (09-09g)")
    if not d.bank_toe_break_m > 0.0:
        raise err(f"emit.design.bank_toe_break_m {d.bank_toe_break_m}: the toe "
                  "smoothing's break, positive metres")
    if not d.bank_triangle_divisions >= 1.0:
        raise err(f"emit.design.bank_triangle_divisions "
                  f"{d.bank_triangle_divisions}: at least one triangle across "
                  "the bank (09-09x)")
    for key in ("edge_probe_m", "edge_min_drop_m", "edge_grid_m",
                "edge_road_snap_m", "edge_road_run_m"):
        v = float(getattr(d, key))
        if not v > 0.0:
            raise err(f"emit.design.{key} {v}: positive metres — the terrain "
                      "edge (RULINGS 2026-09-10c)")
    if not d.edge_grid_m < d.edge_probe_m:
        raise err(f"emit.design.edge_grid_m {d.edge_grid_m}: finer than the "
                  f"probe {d.edge_probe_m} — the crest is read over the probe, "
                  "marked on the grid (09-10c)")
    if not d.hard_rulings:
        raise err("emit.design.hard_rulings: at least one ruling "
                  "(RULINGS 2026-09-08v: the runway family's laws are hard)")
    if d.polish_rounds_max < 1:
        raise err(f"emit.design.polish_rounds_max {d.polish_rounds_max}: at least 1")
    if not d.hard_tol_m > 0.0:
        raise err(f"emit.design.hard_tol_m {d.hard_tol_m}: positive metres")
    if not d.hard_weight > d.law:
        raise err(f"emit.design.hard_weight {d.hard_weight}: heavier than the "
                  f"law's target weight {d.law} — a constraint, not a target")
    if d.solver not in ("fixed_point", "qp"):
        raise err(f"emit.design.solver {d.solver!r}: 'fixed_point' (the "
                  "damped active set) or 'qp' (§20c's exact convex QP)")
    if d.active_set_max_rounds < 1:
        raise err(f"emit.design.active_set_max_rounds {d.active_set_max_rounds}: at least 1")
    if not d.active_set_tol_m > 0.0:
        raise err(f"emit.design.active_set_tol_m {d.active_set_tol_m}: positive metres")
    if not 0.0 < d.solver_tol < 1.0:
        raise err(f"emit.design.solver_tol {d.solver_tol}: a relative tolerance in (0, 1)")
    if d.solver_max_iter < 1:
        raise err(f"emit.design.solver_max_iter {d.solver_max_iter}: at least 1")
