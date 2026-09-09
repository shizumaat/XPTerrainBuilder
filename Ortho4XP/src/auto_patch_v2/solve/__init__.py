"""ONE solve (plan §1 row 6): THE DESIGN SURFACE —
``solve.design.solve_design(planar, constraints, law, options) -> (Solution,
DesignReport)``, one sparse least-squares problem (owner RULINGS
2026-09-08t).  ``api`` holds the frozen types."""
from .api import Options, Residual, Solution, Status
from .design import DesignReport, solve_design

__all__ = ["Options", "Residual", "Solution", "Status", "DesignReport",
           "solve_design"]
