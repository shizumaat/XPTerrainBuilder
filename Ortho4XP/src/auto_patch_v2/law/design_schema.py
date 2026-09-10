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
                                 "taxi_profile", "road", "detached_mean",
                                 "body_datum")

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
    law: float
    #: THE TAXI DESIGN PROFILE (owner RULINGS 2026-09-09b (2), "taxiways
    #: should follow terrain less and be more like runways"): the second
    #: difference of z along every taxi CENTRELINE chain, as a strong
    #: curvature target — the runway K pattern read as an objective term
    taxi_profile: float
    road: float
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
    #: THE PAD PLANE (owner RULINGS 2026-09-09c): a pad's flatness is a
    #: STRONG TARGET (it is no longer a hard ``Flat`` merge), and its tilt
    #: is bounded hard at ``emit.within_shape.pad_slope_max``.
    #: ``pad_flat_rulings`` names the ruling HEADS priced at ``pad_flat``
    #: instead of ``law`` — one register, the same shape as
    #: ``hard_rulings`` / ``one_way_rulings``.
    pad_flat: float
    pad_flat_rulings: tuple[str, ...]
    #: THE PAD TAKES THE PAVEMENT'S EDGE LEVEL (owner RULINGS 2026-09-10l,
    #: 10k-1 = (A)): the ruling HEADS of a pad's frontage LEVEL rows.  A
    #: vertex such a row GOVERNS (its ``follows``) is a pad following the
    #: pavement, so ``solve/design`` §9b takes it out of every per-body
    #: DEM datum mean — a pad's own datum (09p (3)) is for a pad that
    #: fronts NO pavement.
    pad_level_rulings: tuple[str, ...]
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
    if d.one_way_max_rounds < 1:
        raise err(f"emit.design.one_way_max_rounds {d.one_way_max_rounds}: at least 1")
    if not 0.0 < d.one_way_relax <= 1.0:
        raise err(f"emit.design.one_way_relax {d.one_way_relax}: an "
                  f"under-relaxation factor in (0, 1]")
    if not d.one_way_tol_m > 0.0:
        raise err(f"emit.design.one_way_tol_m {d.one_way_tol_m}: positive metres")
    if not d.pad_flat_rulings:
        raise err("emit.design.pad_flat_rulings: at least one ruling "
                  "(RULINGS 2026-09-09c: the pad's flatness is a target)")
    if not d.pad_flat > d.law:
        raise err(f"emit.design.pad_flat {d.pad_flat}: heavier than the law's "
                  f"target weight {d.law} — a pad targets FLAT (09-09c)")
    if not d.pad_level_rulings:
        raise err("emit.design.pad_level_rulings: at least one ruling "
                  "(RULINGS 2026-09-10l: the pad takes the pavement's edge "
                  "level and its own DEM datum only where it fronts none)")
    missing = [r for r in d.pad_level_rulings if r not in d.one_way_rulings]
    if missing:
        raise err(f"emit.design.pad_level_rulings {missing}: every level "
                  f"ruling must also be in one_way_rulings — the pad FOLLOWS "
                  f"the pavement and never pulls it (RULINGS 2026-09-10l)")
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
    if d.active_set_max_rounds < 1:
        raise err(f"emit.design.active_set_max_rounds {d.active_set_max_rounds}: at least 1")
    if not d.active_set_tol_m > 0.0:
        raise err(f"emit.design.active_set_tol_m {d.active_set_tol_m}: positive metres")
    if not 0.0 < d.solver_tol < 1.0:
        raise err(f"emit.design.solver_tol {d.solver_tol}: a relative tolerance in (0, 1)")
    if d.solver_max_iter < 1:
        raise err(f"emit.design.solver_max_iter {d.solver_max_iter}: at least 1")
