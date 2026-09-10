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
    #: THE BANK (owner RULINGS 2026-09-09e; spec §9): the patch's own
    #: embankment out to the DEM, because the mesh does not blend.
    #: ``bank_slope`` is the bank's grade (0.33 = 1:3), ``bank_min_width_m``
    #: the narrowest bank, ``bank_foot_smooth`` the second-difference
    #: weight along the foot chain that keeps the toe from zigzagging.
    bank_slope: float
    bank_min_width_m: float
    bank_foot_smooth: float
    #: ``bank_ring_spacing_m`` is the plan spacing of the INTERMEDIATE
    #: rings that AUTHOR the bank face (owner RULINGS 2026-09-09f-1) —
    #: the mesh interpolates nothing it has no vertices for.
    bank_ring_spacing_m: float
    #: ``bank_first_ring_m`` is where the FIRST intermediate ring stands
    #: (owner RULINGS 2026-09-09i (1)) — inside the first spacing, because
    #: the innermost band is where the mesh's harmonic squeeze reads.
    bank_first_ring_m: float
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
    hard_max_rounds: int
    hard_tol_m: float
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


def check_design(d: Design, err: type[Exception]) -> None:
    """Every weight positive and finite, every limit positive."""
    for term in DESIGN_TERMS:
        w = d.weight(term)
        if not (w > 0.0) or w != w or w in (float("inf"), float("-inf")):
            raise err(f"emit.design.{term} {w}: a positive, finite weight")
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
    if not 0.0 < d.bank_slope <= 1.0:
        raise err(f"emit.design.bank_slope {d.bank_slope}: a bank grade in (0, 1]")
    if not d.bank_min_width_m > 0.0:
        raise err(f"emit.design.bank_min_width_m {d.bank_min_width_m}: positive metres")
    if not d.bank_foot_smooth > 0.0:
        raise err(f"emit.design.bank_foot_smooth {d.bank_foot_smooth}: a positive weight")
    if not d.bank_ring_spacing_m > 0.0:
        raise err(f"emit.design.bank_ring_spacing_m {d.bank_ring_spacing_m}: positive metres "
                  "(RULINGS 2026-09-09j: the spacing is the width of the band the mesh "
                  "interpolates across — measured, only a 3 m band reads the 1:3 cleanly)")
    if not 0.0 < d.bank_first_ring_m < d.bank_min_width_m:
        raise err(f"emit.design.bank_first_ring_m {d.bank_first_ring_m}: "
                  f"positive and inside bank_min_width_m {d.bank_min_width_m} "
                  "— the first level ring stands within the narrowest bank "
                  "(09-09i (1))")
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
    if not d.hard_rulings:
        raise err("emit.design.hard_rulings: at least one ruling "
                  "(RULINGS 2026-09-08v: the runway family's laws are hard)")
    if d.hard_max_rounds < 1:
        raise err(f"emit.design.hard_max_rounds {d.hard_max_rounds}: at least 1")
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
