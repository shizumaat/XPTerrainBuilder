"""ONE solver — the interface (plan §1 row 6, §2).  M0 freezes the
signature; M2 implements it.

    solve(planar, constraints, weights, options) -> Solution

Variables z over planar-map vertices; objective
``Σ w_i (z_i − dem_i)² + λ · Σ_breaklines (second differences)²``;
subject to the linear rows of the :class:`ConstraintSet`.  Phase 1 is an
LP feasibility check; if infeasible the solver extracts an irreducible
infeasible subsystem and reports it as ``(row, source)`` — the solver
never invents a value and never smears a contradiction (plan §2).
Backends: scipy HiGHS (in the freeze) and OSQP (RULINGS 2026-09-03d:
added to the freeze if it measurably beats HiGHS on the v2 QP).
"""
from __future__ import annotations

import dataclasses as _dc
import enum
import typing as _t

from ..model.constraints import ConstraintSet, Row, Source
from ..model.planar import PlanarMap

__all__ = ["Backend", "Status", "Weights", "Options", "Residual",
           "Solution", "solve"]


class Backend(str, enum.Enum):
    """Numeric backends the interface admits."""

    HIGHS = "highs"     # scipy.optimize.linprog / milp (LP phase, QP via SLSQP-free path)
    OSQP = "osqp"       # ADMM QP; adopted only if measured faster (2026-09-03d)


class Status(str, enum.Enum):
    """Solve outcome."""

    OPTIMAL = "optimal"
    FEASIBLE = "feasible"          # feasible, objective not converged to tolerance
    INFEASIBLE = "infeasible"      # IIS populated
    ERROR = "error"                # backend failure; message in ``Solution.message``


@_dc.dataclass(frozen=True)
class Weights:
    """Objective weights.  ``by_role`` maps a law role to the DEM-fit
    weight of its vertices (airside high, groundside 1); ``zone3`` is the
    weight of vertices the law leaves to the DEM (large: they are
    pinned by preference, not by constraint); ``smoothness`` is λ."""

    by_role: _t.Mapping[str, float]
    zone3: float
    smoothness: float
    default: float


@_dc.dataclass(frozen=True)
class Options:
    """Solver options — a config object, never an env gate."""

    backend: Backend = Backend.HIGHS
    feasibility_tol_m: float = 1e-6
    max_iterations: int = 20000
    time_limit_s: float | None = None
    diagnose_iis: bool = True
    verbose: bool = False


@_dc.dataclass(frozen=True)
class Residual:
    """The certificate: the worst violation of each row kind at the
    returned ``z`` (metres), and the objective value."""

    max_pin_m: float
    max_diff_m: float
    max_flat_m: float
    max_band_m: float
    max_offset_m: float
    objective: float

    @property
    def max_m(self) -> float:
        """The single worst residual."""
        return max(self.max_pin_m, self.max_diff_m, self.max_flat_m,
                   self.max_band_m, self.max_offset_m)


@_dc.dataclass(frozen=True)
class Solution:
    """``z`` per vertex id (dense tuple in id order), the status, the
    residual certificate, and — when infeasible — the IIS as
    ``(row, source)`` pairs naming who minted the contradiction."""

    z: tuple[float, ...]
    status: Status
    residual: Residual | None
    iis: tuple[tuple[Row, Source], ...] = ()
    backend: Backend = Backend.HIGHS
    iterations: int = 0
    wall_s: float = 0.0
    message: str = ""


def solve(planar: PlanarMap, constraints: ConstraintSet, weights: Weights,
          options: Options | None = None) -> Solution:
    """Solve the LP (see module docstring) — ``highs.solve`` (M2)."""
    from .highs import solve as _solve
    return _solve(planar, constraints, weights, options)
