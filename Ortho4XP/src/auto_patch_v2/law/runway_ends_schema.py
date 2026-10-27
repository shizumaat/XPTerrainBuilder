"""runway_ends.toml — the SCHEMA of THE RUNWAY-END PIN RULE (owner RULINGS
2026-10-25a, 2026-10-26a, 2026-10-26e; issues #1342, #1358, #1394; spec
``docs/findings/lrwypin-runway-end-pins.md`` §3): frozen dataclasses + the
table's own validation.  No numeric value appears here (the values live in
the TOML).  Imports nothing from v2.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["ByDemClass", "RunwayEnds", "check_runway_ends"]


@_dc.dataclass(frozen=True)
class ByDemClass:
    """One number per DEM source class (``law/inset_class``): ``lidar``,
    ``fine``, ``coarse``.  An UNKNOWN class reads ``coarse``."""

    lidar: float
    fine: float
    coarse: float

    def of(self, klass: str | None) -> float:
        """The value for source class ``klass`` (unknown -> ``coarse``)."""
        if klass == "lidar":
            return self.lidar
        if klass == "fine":
            return self.fine
        return self.coarse


@_dc.dataclass(frozen=True)
class RunwayEnds:
    """runway_ends.toml (spec §3, "Thresholds")."""

    #: (a) a CIFP end "equals the field elevation" within this many feet
    field_equal_ft: float
    #: (a) the runway's CIFP ends are "the same number" within this
    placeholder_spread_ft: float
    #: (a) / case E: the DEM tier's noise, metres
    dem_noise_m: ByDemClass
    #: (b) and the resolution's agreement test, metres of end-to-end height
    grade_disagree_m: ByDemClass
    #: (c) a cross-check source disagrees beyond this many feet
    crosscheck_tol_ft: float
    #: (d) a runway whose CIFP ends all read within this many feet of 0 ft
    #: carries placeholders (owner RULINGS 2026-10-26j)
    zero_placeholder_ft: float
    #: the DEM read at a pin: the median over this much centreline
    dem_window_m: float
    #: the cross-check sources, in the order a flagged runway tries them
    #: (owner RULINGS 2026-10-26a); a name with no provider module is skipped
    crosscheck_order: tuple[str, ...]


def check_runway_ends(t: RunwayEnds, error: type[Exception]) -> None:
    """runway_ends.toml's own rules (raised as ``error``, the loader's
    ``LawError``): every tolerance is non-negative, the window positive,
    and the lidar noise no larger than the coarse one."""
    for name in ("field_equal_ft", "placeholder_spread_ft", "crosscheck_tol_ft",
                 "zero_placeholder_ft"):
        if getattr(t, name) < 0.0:
            raise error(f"runway_ends.{name} {getattr(t, name)!r} < 0")
    if not t.dem_window_m > 0.0:
        raise error(f"runway_ends.dem_window_m {t.dem_window_m!r} <= 0")
    for name in ("dem_noise_m", "grade_disagree_m"):
        v = getattr(t, name)
        if min(v.lidar, v.fine, v.coarse) < 0.0 or v.lidar > v.coarse:
            raise error(f"runway_ends.{name} {v!r}: negative, or lidar > coarse")
