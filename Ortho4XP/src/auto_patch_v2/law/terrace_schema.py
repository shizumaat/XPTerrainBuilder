"""emit.toml ``[terrace]`` — the SCHEMA of the apron terrace joints
(RULINGS 2026-09-06n; ``planar/terraces.py``), split from ``model.py`` by
the 1,000-line file law and re-exported there.  A frozen dataclass and
the table's own validation; no numeric value appears here (the values
live in the TOML).  Imports nothing from v2.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["Terrace", "check_terrace"]


@_dc.dataclass(frozen=True)
class Terrace:
    """The apron terrace joints: the roles a joint is declared FOR
    (``cell_roles``) and AGAINST (``neighbour_roles``), the retreating
    ring's gap into its own cell, v1's declared-step bound (report)."""

    cell_roles: tuple[str, ...]
    neighbour_roles: tuple[str, ...]
    joint_gap_m: float
    max_step_m: float


def check_terrace(tr: Terrace, roles: _t.Container[str], min_spacing_m: float,
                  err: type[Exception]) -> None:
    """Every role registered; a cell role stated; the gap exceeds the
    identity spacing (the retreated copy would re-intern otherwise)."""
    for r in (*tr.cell_roles, *tr.neighbour_roles):
        if r not in roles:
            raise err(f"emit.terrace: unknown role {r!r}")
    if not tr.cell_roles:
        raise err("emit.terrace.cell_roles: empty")
    if tr.joint_gap_m <= min_spacing_m:
        raise err(f"emit.terrace.joint_gap_m {tr.joint_gap_m} must exceed "
                  f"identity.min_distinct_spacing_m {min_spacing_m}")
