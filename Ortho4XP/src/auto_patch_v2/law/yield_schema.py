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
                                   "apron_edge_portion", "roads", "taxi_chain_at_runway")


@_dc.dataclass(frozen=True)
class Yield:
    """The families that YIELD (their rows are preferences with an
    escalation ceiling, junior to the runway chord fit), the ceilings per
    class — a class whose ``<class>_yield_max`` key is ABSENT yields
    without a ceiling (owner RULINGS 2026-09-08k (3): the apron inside a
    shape) — the sliver-merge factor and the groundside ramp cap."""

    sliver_area_factor: float
    groundside_ramp_max: float
    #: family name (``constraints/yielding.FAMILY_SELECTORS``) -> class
    families: _t.Mapping[str, str]
    taxi_yield_max: float | None = None
    apron_yield_max: float | None = None
    road_yield_max: float | None = None
    #: THE NETWORK IS HARD (owner RULINGS 2026-09-08p (2), lane v2shapes
    #: round 2): the classes whose rows wholly on the taxiway network (the
    #: vertices of the runway family and of the taxi-family faces carrying a
    #: runway-connected centreline) stay HARD; the runway-contact chain
    #: family yields regardless (08i-1).  The round's experiment knob awaiting
    #: the spawner's ruling on the two replay arms (spec §11): ["taxi"] = the
    #: brief's literal (HECA bows −4.99 / −9.44 / −0.47), [] = round 1's
    #: yielding network (−2.21 / −7.10 / −0.36).
    network_hard_classes: tuple[str, ...] = ("taxi",)

    def ceiling(self, cls: str) -> float | None:
        """The escalation ceiling of a yield class, ``None`` = unbounded."""
        v = getattr(self, f"{cls}_yield_max")
        return None if v is None else float(v)


def check_yield(y: Yield, err: type[Exception]) -> None:
    """Every family known to the transform, every class stated, every
    ceiling that is stated a grade, the factor and the ramp cap positive."""
    for fam, cls in y.families.items():
        if fam not in YIELD_FAMILIES:
            raise err(f"emit.yield.families: unknown family {fam!r} (allowed: {YIELD_FAMILIES})")
        if cls not in YIELD_CLASSES:
            raise err(f"emit.yield.families.{fam}: unknown class {cls!r} (allowed: {YIELD_CLASSES})")
    for cls in y.network_hard_classes:
        if cls not in YIELD_CLASSES:
            raise err(f"emit.yield.network_hard_classes: unknown class {cls!r} (allowed: {YIELD_CLASSES})")
    for cls in YIELD_CLASSES:
        v = y.ceiling(cls)
        if v is not None and not 0.0 < v < 1.0:
            raise err(f"emit.yield.{cls}_yield_max {v}: a grade fraction in (0, 1)")
    if y.sliver_area_factor <= 0.0 or not 0.0 < y.groundside_ramp_max < 1.0:
        raise err("emit.yield: sliver_area_factor must be positive and groundside_ramp_max a grade")
