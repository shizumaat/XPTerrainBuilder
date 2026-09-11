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
    #: RULINGS 2026-09-09s (2): a GROUND part's seat target is read at
    #: its own FEET, at most this many.
    foot_samples_max: int
    # the cut and the cluster seat (06g; v1 per-cluster seating spec)
    cluster_seat_tolerance_m: float
    #: RULINGS 2026-09-10i (2): a BODY wider than this carrying fewer
    #: than one measured foot per that span samples the design surface
    #: under every ground-contact part.  0 disables the sampling.
    body_feet_span_m: float
    #: RULINGS 2026-09-10u (2): a free component with no carrier within
    #: the identity spacing joins the wall it OVERLAPS IN PLAN whose top
    #: is within this of its bottom (the eave / parapet gap), instead of
    #: the nearest carrier in 3-D.  0 = the pre-10u pure-nearest rule.
    plate_gap_max_m: float
    #: RULINGS 2026-09-10bb (spec §16): a LINE OBJECT — a resource every
    #: genuine component of which is a low plan RIBBON (plan-box diagonal
    #: over plan-area width above ``line_object_ratio``, height under
    #: ``line_object_max_h``) — forms no body, founds no foot and DRAPES:
    #: it is seated per SEGMENT at up to ``line_object_stations_max``
    #: stations spread at ``body_feet_span_m``.  ``line_object_ratio = 0``
    #: disables the class (the pre-10bb reading).
    line_object_ratio: float
    line_object_max_h: float
    line_object_stations_max: int
    #: owner RULINGS 2026-09-10ay (spec §17): the minimum plan EXTENT
    #: along which two parts of ONE anchor plane must meet to ABUT —
    #: their plan boxes within ``emit.identity.min_distinct_spacing_m``
    #: on both axes, meeting over at least this on one of them, their
    #: authored z within ``plate_gap_max_m``, and no ε-contact edge.  It
    #: binds no body; it GROUPS the two bodies, which take the SENIOR
    #: body's delta.  0 disables the class (the pre-10ay reading).
    abutment_extent_min_m: float
    abutment_deck_share_min: float
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
    deck_family_seats_rigid: bool
    facility_requires_at_grade_coalition: bool
    structure_seat_threshold_exempt: bool
    #: RULINGS 2026-09-08u (1): the threshold of a PLATE-datum structure
    #: seat (tunnel wall crest / basin floor), below ``min_delta_m``.
    plate_seat_min_delta_m: float
    # the flat-site datum at the seat (RULINGS 2026-09-08d; spec
    # othh-seat-artefacts-spec.md §3)
    anchor_water_founds_seat: bool
    flat_site_anchor_datum: bool
    flat_site_ground_datum: bool
