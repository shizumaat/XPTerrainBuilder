"""The ``structures.toml [basin]`` schema — the below-grade FACILITY law
(RULINGS 2026-08-26, 2026-09-04i, 2026-09-06b/c/f, 2026-09-09ag,
2026-09-10ba, 2026-09-11t; spec ``design-surface-spec.md`` §22.1c / §24).
Kept beside ``model.py`` under the 1,000-line file law, exactly as
``cutout_schema`` / ``rebake_schema`` are, and re-exported there.  Values
live in the TOML; no numeric value appears here.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["Basin"]


@_dc.dataclass(frozen=True)
class Basin:
    """Basin facility law (RULINGS 2026-08-26; M4b)."""

    floor: str
    seat: str                          # "floor_plate": the family seats its plate on the floor (2026-09-06b)
    min_solid_thickness_m: float
    admission_depth_m: float
    contact_band_m: float
    footprint_close_m: float
    min_area_m2: float                 # diagnostic only (04i)
    rim_sample_step_m: float
    max_covered_fraction: float        # diagnostic only (04i)
    basement_cover_min: float          # 2026-09-06c (1): own cover at or above this = a BASEMENT; less = a PIT
    floor_disagreement_m: float
    rim: str
    shell_reaches_grade: bool
    cuts_pads: bool
    cuts_runway_family: bool
    floor_plate_normal_y_min: float    # 04i: the floor-plate gate
    rim_reaches_grade: bool            # 04i: the closed-region test
    rim_protrusion_max_fraction: float # 2026-09-06f: this share of a component's face area may stand above the band (a tower in the pit is not the rim)
    authored_depth_min_m: float        # 2026-09-09ag: the floor plate stands this far under the placement's OWN render datum too — the depth is AUTHORED (spec §13)
    floor_clearance_m: float           # 2026-09-11t (spec §24 (2)): the trench floor stands this far UNDER the object's floor plate, so the plate renders and the terrain never shows through
