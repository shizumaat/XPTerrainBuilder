"""The ``structures.toml [rebake]`` schema — the object re-seat law's keys
(RULINGS 2026-09-04i 04f-1; the CONTACT-CLUSTER law 2026-09-06g), kept
beside ``model.py`` under the 1,000-line file law.  Values live in the
TOML; no numeric value appears here.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["Rebake"]


@_dc.dataclass(frozen=True)
class Rebake:
    """Object re-seat law (RULINGS 2026-09-04i 04f-1; memory othh-bridge-deck-datum-r12)."""

    restore_before_read: bool
    ground_datum: str
    deck_datum: str
    # the partition (06g; v1 pools / structures / contact graph)
    pool_overlap_m: float
    contact_epsilon_m: float
    contact_weld_m: float
    contact_narrow_budget: int
    contact_batch_rows: int
    elevated_base_m: float
    # the cut and the cluster seat (06g; v1 per-cluster seating spec)
    cluster_seat_tolerance_m: float
    min_delta_m: float
    cluster_span_pad_m: float
    cluster_residual_pad_m: float
    nobake_pad_floor_m: float
    pad_max_relief_m: float
    a3_guard_max_diameter_m: float
    a3_tolerance_m: float
    agreement_window_m: float
    water_founds_seat: bool
    one_anchor_one_seat: bool
    structure_family_excluded: bool
    deck_family_seats_rigid: bool
    facility_requires_at_grade_coalition: bool
    structure_seat_threshold_exempt: bool
    # the flat-site datum at the seat (RULINGS 2026-09-08d; spec
    # othh-seat-artefacts-spec.md §3)
    anchor_water_founds_seat: bool
    flat_site_anchor_datum: bool
    flat_site_ground_datum: bool
