"""flat_pack.toml — the SCHEMA of the flat-pack witness (owner direction
2026-10-20; answers 59-66; spec ``docs/specs/flat-pack-terracing-spec.md``
§1): frozen dataclasses + the table's own validation.  No numeric value
appears here (the values live in the TOML).  Imports nothing from v2.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["FlatPackDetector", "FlatPack", "check_flat_pack"]


@_dc.dataclass(frozen=True)
class FlatPackDetector:
    """The detector's own constants (spec §1.1).  The level window and the
    relief floor are NOT here: they are read from ``flat_site.toml``
    (``seat_spread_max_m``, ``relief_floor_m``) so one number is never
    stated twice."""

    level_share_min: float
    grounded_band_m: float
    min_members: int


@_dc.dataclass(frozen=True)
class FlatPack:
    """flat_pack.toml.  ``terrace`` is the phase gate (spec §5): false
    while the detector only REPORTS."""

    detector: FlatPackDetector
    terrace: bool


def check_flat_pack(fp: FlatPack, error: type[Exception]) -> None:
    """flat_pack.toml's own rules (raised as ``error``, the loader's
    ``LawError``): the share is a fraction in (0, 1], the grounded band is
    non-negative and at least one member is needed."""
    d = fp.detector
    if not 0.0 < d.level_share_min <= 1.0:
        raise error(f"flat_pack.detector.level_share_min {d.level_share_min!r}"
                    " not in (0, 1]")
    if d.grounded_band_m < 0.0:
        raise error(f"flat_pack.detector.grounded_band_m {d.grounded_band_m!r} < 0")
    if d.min_members < 1:
        raise error(f"flat_pack.detector.min_members {d.min_members!r} < 1")
