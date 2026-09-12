"""The ``structures.toml [rebake]`` schema — the object re-seat law's keys
(RULINGS 2026-09-04i 04f-1; the CONTACT-CLUSTER law 2026-09-06g), kept
beside ``model.py`` under the 1,000-line file law.  Values live in the
TOML; no numeric value appears here.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["Rebake", "Placement"]


@_dc.dataclass(frozen=True)
class Rebake:
    """Object re-seat law (RULINGS 2026-09-04i 04f-1; memory othh-bridge-deck-datum-r12)."""

    #: RULINGS 2026-09-11e (3): the object stage's ONE gate — ``"agl"``
    #: (the placement path: conversions, coarsened split bodies, placed
    #: anchors, no seat) or ``"seat"`` (the pre-11b re-seat, unchanged).
    placement: str
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


@_dc.dataclass(frozen=True)
class Placement:
    """``structures.toml [placement]`` — the object PLACEMENT law (owner
    RULINGS 2026-09-11e (1)/(2); spec ``object-placement-spec.md`` §9)."""

    #: bodies of one placement whose intended-zero terrain heights agree
    #: within this are ONE file (the senior body's anchor), and a body
    #: with no ground-contact vertex whose surface reads within this of
    #: its own zero plane anchors at its low-side foot and is REPORTED.
    split_tol_m: float

    #: THE SEGMENT CUT (11f (2)): a line object's triangles are assigned
    #: by centroid to stations this far apart and each station becomes
    #: its own body / file / placement at its mid-foot.  0 disarms it.
    line_segment_m: float = 100.0

    #: THE CANOPY-AND-BUILDING GROUP (owner RULINGS 2026-09-11i; spec
    #: §11 (4)): a group whose plan span exceeds this is the HECA
    #: railway class — the only group whose connecting deck an
    #: INFEASIBLE pad may RELEASE.  A shorter infeasible group is
    #: reported with its residual and never split.  0 disarms the
    #: exception (no group is ever releasable).  Per airport in
    #: ``airports.toml`` (``Affordances.group_span_max_m``).
    group_span_max_m: float = 150.0

    #: THE RELIEF TARGET'S REACH (owner RULINGS 2026-09-11j; spec §11a
    #: (2)).  The terrain under a body's ground-contact FOOT is asked for
    #: ``level + (y_foot - y_zero)``; a pad vertex this far from a foot
    #: takes that foot's target, and a vertex no foot is that close to
    #: keeps the pad's LEVEL — which is today's flat pad.  Nearest, never
    #: interpolated: only the object's own contacts are places where the
    #: terrain is constrained to a value.  0 disarms the relief target
    #: (every pad targets flat, the pre-11j law).
    relief_radius_m: float = 12.0

    #: A CARRIER IS A SOLID (owner RULINGS 2026-09-11ai; spec §16 (3)).
    #: The FOOTPRINT FILL — the area a body's PART boxes cover over the
    #: area of its own plan box — a candidate must reach before it may
    #: carry another body's zero.  A line segment, a grass strip and a
    #: sign fill a few thousandths of their boxes and carry nothing.
    #: 0 disarms the test (every footed body a carrier, the pre-11ai
    #: reading).
    carrier_fill_min: float = 0.2

    #: PLAN CONTIGUITY (owner RULINGS 2026-09-11ap; spec §16b (1)).  §9
    #: joined bodies of one placement into ONE file whenever their
    #: intended zeros agreed, with NO distance limit: LEMD's taxi-sign
    #: resource put 80 signs over 835 x 2,319 m into files by height
    #: alone, and ``SENRG__b10`` took its zero from a sign 1,590 m away
    #: (+4.58 m at the owner's site).  Two bodies join only when their
    #: plan boxes stand within this of each other; 0 disarms the test
    #: (the pre-11ap reading, zero agreement alone).
    #:
    #: IT IS NEVER BELOW ``line_segment_m`` (Fable's §16b (1) amendment):
    #: §10 cuts a line object into stations THAT far apart on purpose, so
    #: a shorter reach makes every station its own file by construction —
    #: measured at 30 m, LEMD's line-segment files went 300 -> 1,755 and
    #: the airport 1,371 -> 4,050.  Chaining a body onto one a kilometre
    #: away is forbidden by the TERRAIN-GROUP test beside this one (the
    #: design surface under each must agree too), never by the reach.
    coarsen_reach_m: float = 100.0

    #: §16c (6) COMPONENTS IN CONTACT BIND (owner RULINGS 2026-09-12h).
    #: §16c (1) made the connected COMPONENT the atom of every group, and
    #: an exporter's "one solid" is often several components that TOUCH:
    #: OTHH's ``OTHH_Fuel_02_LOD0_007`` has two 0.4 mm apart — under the
    #: millimetre key ``obj8.solid_components`` welds on they are two
    #: components, and written at two zeros they showed a 2.70 m seam.
    #: Components of ONE resource whose geometry comes within this are
    #: ONE RIGID BODY for anchoring: one zero, the senior component's
    #: carrier.  It is a CONTACT tolerance, not a reach — the plan's own
    #: ε-contact graph binds the rest — so it is millimetres, and raising
    #: it welds things that merely stand near each other (measured at
    #: LEMD, see spec §16c MEASURED).  0 disarms the distance test and
    #: leaves the plan's contact graph alone.
    contact_eps_m: float = 0.002
