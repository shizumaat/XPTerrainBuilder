"""The law register's UNIT SANITY (a sibling of ``model.py`` under the
1,000-line file law): grades are fractions in ``[0, GRADE_FRACTION_MAX]``
(a percentage typed as a fraction fails loudly), metres / counts /
degrees are non-negative, named fractions lie in ``[0, 1]``.  The one
numeric value here is the register's own bound.
"""
from __future__ import annotations

__all__ = ["GRADE_FRACTION_MAX", "sane", "GRADE_WORDS", "SIGNED_METRES"]

#: Words in a key name that mark it as a GRADE (a fraction, never a percentage).
GRADE_WORDS = ("grade", "longitudinal", "transverse", "down", "up",
               "fan_ramp", "crown", "materiality")
#: The one SIGNED metre key: an authored OBJ8 ``base_y`` threshold (a depth
#: under the placement seat is negative by the file's own convention).
SIGNED_METRES = ("below_grade_base_y_m",)
#: The register's grade-fraction sanity bound (a percentage typed as a
#: fraction fails it).  Was 0.2; RULINGS 2026-09-08n states a 0.25 sanity
#: cap for a pack-authored garage ramp (``cutout.wall_corridor.
#: max_authored_grade`` = the ``garage_ramp`` role's cap), so the bound is
#: that cap — still an order under any percentage.
GRADE_FRACTION_MAX = 0.25


def sane(path: str, name: str, value: float, err: type[Exception]) -> None:
    """Unit sanity for one numeric key (module doc); raises ``err``."""
    if name.endswith(("_m", "_m2", "_deg", "per_m")) or name == "k":
        if value < 0 and name not in SIGNED_METRES:
            raise err(f"{path}: {name} must be >= 0, got {value}")
        return
    if name.endswith("_fraction") or name in ("floor_plate_normal_y_min", "basement_cover_min"):
        if not 0.0 <= value <= 1.0:
            raise err(f"{path}: {name}={value} is not a fraction in [0, 1]")
        return
    if any(w in name for w in GRADE_WORDS) or name in ("default",):
        if not 0.0 <= value <= GRADE_FRACTION_MAX:
            raise err(
                f"{path}: {name}={value} is not a grade fraction in [0, {GRADE_FRACTION_MAX}]"
                " (a fraction, never a percentage)")
