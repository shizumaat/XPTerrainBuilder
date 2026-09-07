"""emit.toml ``[objective]`` — the SCHEMA of the base solve's objective
ORDER (RULINGS 2026-09-06x; ``solve/lexi.py``), split from ``model.py``
by the 1,000-line file law and re-exported there.  A frozen dataclass
and the table's own validation; no numeric value appears here.  Imports
nothing from v2.

The order the owner ruled (04i, 06w (2)): the RUNWAY family's own
objective terms first, the APRON preference second, the DEM fit and
every junior term last — ``"lexicographic"`` holds it as three stages
(A: the runway's terms and every preference senior to them; B: the
apron preference with the runway held within ``[relaxation]
runway_hold_tolerance_m`` of stage A; C: everything, both held);
``"weighted"`` is the single weighted stage, the round's OFF arm
(measured at HECA: the apron's parallel rows outweigh the runway's few
vertices and hold the chain at 1.445 % under the allowed 1.5 %).
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["Objective", "OBJECTIVE_ORDERS", "check_objective"]

OBJECTIVE_ORDERS = ("lexicographic", "weighted")


@_dc.dataclass(frozen=True)
class Objective:
    """The base solve's objective order (module docstring)."""

    order: str
    #: the preference-group PREFIX stage B minimises (``constraints/apron.py``
    #: ``PREFERENCE_GROUP``) — every other prefix is charged in stage A
    stage_b_prefix: str
    #: warm-start stages B and C from the previous stage's HiGHS basis
    warm_start: bool


def check_objective(o: Objective, err: type[Exception]) -> None:
    if o.order not in OBJECTIVE_ORDERS:
        raise err(f"emit.objective.order {o.order!r} (allowed: {OBJECTIVE_ORDERS})")
    if not o.stage_b_prefix or ":" in o.stage_b_prefix:
        raise err(f"emit.objective.stage_b_prefix {o.stage_b_prefix!r}: a bare prefix")
