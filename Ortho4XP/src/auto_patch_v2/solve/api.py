"""THE SOLVE's frozen types (plan §1 row 6, §2) — the status, the options,
the residual certificate and the solution.

THE DESIGN SURFACE (owner RULINGS 2026-09-08t) replaced the LP: the solve
is ``solve.design.solve_design(planar, constraints, law, options)``, ONE
sparse least-squares problem that is never infeasible.  ``Backend``,
``Weights``, the preference ladder and the IIS are DELETED with the tier /
relaxation / yield machinery they served.
"""
from __future__ import annotations

import dataclasses as _dc
import enum

__all__ = ["Status", "Options", "Residual", "Solution"]


class Status(str, enum.Enum):
    """Solve outcome."""

    OPTIMAL = "optimal"            # the active set settled
    FEASIBLE = "feasible"          # solved, the active set had not settled at the cap
    ERROR = "error"                # solver failure; message in ``Solution.message``


@_dc.dataclass(frozen=True)
class Options:
    """Solver options — a config object, never an env gate."""

    feasibility_tol_m: float = 1e-6
    time_limit_s: float | None = None
    verbose: bool = False


@_dc.dataclass(frozen=True)
class Residual:
    """The certificate: the worst residual of each row kind at the returned
    ``z`` (metres), and the objective value.  Under the design surface a
    row is a TARGET, so a residual is a missed target, never a defect of
    the solve."""

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
    """``z`` per vertex id (dense tuple in id order), the status and the
    residual certificate."""

    z: tuple[float, ...]
    status: Status
    residual: Residual | None
    iterations: int = 0
    wall_s: float = 0.0
    message: str = ""
