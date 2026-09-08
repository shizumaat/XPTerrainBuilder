"""emit.toml ``[yield]`` — the SCHEMA of the v1 priority model's yielding
families (owner RULINGS 2026-09-08d; spec ``heca-v1-parity-spec.md`` §2-§4),
split from ``model.py`` by the 1,000-line file law and re-exported there.
A frozen dataclass and the table's own validation; no numeric value
appears here (the values live in the TOML).  Imports nothing from v2.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

__all__ = ["Yield", "YIELD_CLASSES", "YIELD_FAMILIES", "check_yield"]

#: The yield classes a family may name: each is the ``<class>_yield_max``
#: key of the table (the escalation ceiling of that class's rows).
YIELD_CLASSES: tuple[str, ...] = ("taxi", "apron", "road")
#: The families the transform (``constraints/yielding.py``) can select —
#: a generator, or a ruling-selected subset of one.
YIELD_FAMILIES: tuple[str, ...] = ("junction_mesh", "taxi_box", "no_step_pairs", "apron",
                                   "apron_edge_portion", "roads")


@_dc.dataclass(frozen=True)
class Yield:
    """The families that YIELD (their rows are preferences with an
    escalation ceiling, junior to the runway chord fit), the ceilings per
    class, the sliver-merge factor and the groundside ramp cap."""

    taxi_yield_max: float
    apron_yield_max: float
    road_yield_max: float
    sliver_area_factor: float
    groundside_ramp_max: float
    #: family name (``constraints/yielding.FAMILY_SELECTORS``) -> class
    families: _t.Mapping[str, str]

    def ceiling(self, cls: str) -> float:
        """The escalation ceiling of a yield class."""
        return float(getattr(self, f"{cls}_yield_max"))


def check_yield(y: Yield, err: type[Exception]) -> None:
    """Every family known to the transform, every class stated, every
    ceiling a grade, the factor and the ramp cap positive."""
    for fam, cls in y.families.items():
        if fam not in YIELD_FAMILIES:
            raise err(f"emit.yield.families: unknown family {fam!r} (allowed: {YIELD_FAMILIES})")
        if cls not in YIELD_CLASSES:
            raise err(f"emit.yield.families.{fam}: unknown class {cls!r} (allowed: {YIELD_CLASSES})")
    for cls in YIELD_CLASSES:
        v = y.ceiling(cls)
        if not 0.0 < v < 1.0:
            raise err(f"emit.yield.{cls}_yield_max {v}: a grade fraction in (0, 1)")
    if y.sliver_area_factor <= 0.0 or not 0.0 < y.groundside_ramp_max < 1.0:
        raise err("emit.yield: sliver_area_factor must be positive and groundside_ramp_max a grade")
