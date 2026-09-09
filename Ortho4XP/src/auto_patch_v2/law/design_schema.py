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

__all__ = ["Design", "DESIGN_TERMS", "check_design"]

#: The objective's terms, in the order the report prints them.  Each is a
#: weight: the price of one metre of that residual (bending is metres of
#: integrated curvature, every other term metres of elevation).
DESIGN_TERMS: tuple[str, ...] = ("bend", "chord", "law", "dem_zone", "road",
                                 "detached_mean")


@_dc.dataclass(frozen=True)
class Design:
    """The design surface's weights and the active-set iteration's limits.

    ONE sparse least-squares problem (``solve/design.py``): thin-plate
    bending over each connected pavement complex, the runway chord per
    ridge station, every law row as a one-sided quadratic penalty, the DEM
    fit only on the zone rings, roads as smooth chains.  A weight is the
    price of a metre of that term's residual, relative to ``bend``.
    """

    bend: float
    chord: float
    law: float
    dem_zone: float
    road: float
    detached_mean: float
    #: the one-sided penalties' active-set iteration (module docstring of
    #: ``solve/design.py``)
    active_set_max_rounds: int
    active_set_tol_m: float
    solver_tol: float
    solver_max_iter: int

    def weight(self, term: str) -> float:
        """The weight of one objective term (``DESIGN_TERMS``)."""
        return float(getattr(self, term))


def check_design(d: Design, err: type[Exception]) -> None:
    """Every weight positive and finite, every limit positive."""
    for term in DESIGN_TERMS:
        w = d.weight(term)
        if not (w > 0.0) or w != w or w in (float("inf"), float("-inf")):
            raise err(f"emit.design.{term} {w}: a positive, finite weight")
    if d.active_set_max_rounds < 1:
        raise err(f"emit.design.active_set_max_rounds {d.active_set_max_rounds}: at least 1")
    if not d.active_set_tol_m > 0.0:
        raise err(f"emit.design.active_set_tol_m {d.active_set_tol_m}: positive metres")
    if not 0.0 < d.solver_tol < 1.0:
        raise err(f"emit.design.solver_tol {d.solver_tol}: a relative tolerance in (0, 1)")
    if d.solver_max_iter < 1:
        raise err(f"emit.design.solver_max_iter {d.solver_max_iter}: at least 1")
