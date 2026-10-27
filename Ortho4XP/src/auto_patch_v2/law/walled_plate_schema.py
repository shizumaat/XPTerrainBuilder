"""``structures.toml [walled_plate]`` — A WALLED PLATE CAPS A RUNWAY'S
SAFETY AREA (owner RULINGS 2026-10-27t / 2026-10-27u, #1201; spec
``docs/specs/walled-plate-rsa-spec.md`` §3).

The recognition's own numbers and nothing else.  The plate's face test is
``[bridge] deck_plate_normal_y_min`` and the wall's height floor is
``classify/rules.toml retaining_wall_min_height_m``'s figure, read at their
own sites; the safety area's length and width are the law tables'
(``runway_safety_area_length_m`` / ``zone2_half_width_m``).

Defaulted so a law dir without the table still loads — the ``[deck]`` /
``[scatter]`` / ``[base_profile]`` precedent.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["WalledPlateLaw"]


@_dc.dataclass(frozen=True)
class WalledPlateLaw:
    """§3 witnesses 1–4 and the stations the seat and the ground read."""

    #: 0 disarms the rule (every object reads as before)
    enabled: bool = True
    #: witness 1: the plate bin's near-horizontal face area (m²).  KSEA's
    #: three plates carry 1,905–5,425 m²
    min_area_m2: float = 1000.0
    #: the plate bin (m): faces within this of the largest-area level are
    #: the plate
    bin_m: float = 0.5
    #: witness 2: the inner edge lies at s in [``min_s_share`` × L,
    #: L + ``max_s_beyond_m``] beyond the end (L the safety-area length)
    min_s_share: float = 0.5
    max_s_beyond_m: float = 60.0
    #: witnesses 2/3: the share of the safety area's width (and of the
    #: plate's stations) the plate and its outer wall must cover
    min_cover: float = 0.8
    #: witness 3: |n_y| below this is a WALL face
    wall_normal_y_max: float = 0.3
    #: witness 3: the outer wall's minimum depth under the plate (m) — the
    #: wall classifier's ``retaining_wall_min_height_m``
    wall_min_height_m: float = 2.0
    #: witness 4: the DEM step across the outer edge lies in
    #: [``step_min_share`` × h, h + ``foot_tol_m``] — so a top seated on the
    #: safety area never leaves its foot floating more than ``foot_tol_m``
    #: (RULINGS 2026-10-27u "never floating")
    step_min_share: float = 0.5
    foot_tol_m: float = 0.5
    #: witness 4's two DEM samples: this far inside the inner edge and this
    #: far beyond the outer edge (m)
    step_inside_m: float = 5.0
    step_beyond_m: float = 8.0
    #: the station spacing across the axis (m)
    station_m: float = 5.0
    #: the SEAT's stations stand this far inside the inner edge (m), on the
    #: safety area's own ground rather than in the lidar's smear of the step
    station_inset_m: float = 2.0
    #: §5 (2): the ground under the plate stays this far below its top (m)
    under_clearance_m: float = 0.05
