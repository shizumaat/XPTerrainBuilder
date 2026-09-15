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

    # A CARRIER IS A SOLID — THE CLASS, NOT THE FILL FRACTION (owner
    # RULINGS 2026-09-12j; spec §16 (3) amended).  ``carrier_fill_min``
    # is DELETED, not disarmed.  The CLASS exclusion stays and is the
    # whole of the rule: a line segment, a grass strip and a sign never
    # carry, because a fence's plan box is not a thing to stand on
    # (LEMD's ``green-PKT4__b1`` on ``LEMDzaun__b5``, 11ai).  The FILL
    # FRACTION was the wrong instrument for it and struck the right
    # answers: a terminal's WALL RING is a thin loop, and LEMD's
    # ``LEMD54`` / ``LEMD59`` — the walls the T2 roofs rest on, which
    # overlap every one of them and pass §16a (2)'s ground test — fill
    # 0.005-0.031 of their own boxes and were removed as carriers before
    # the rest-on rule ranked anything, leaving tops 2.5-14.6 m below
    # the roofs (measured, lane v2atom round 2).

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

    #: §16c (7) THE RIGID REACH (owner RULINGS 2026-09-12j).  §16c (6)'s
    #: CONTACT tolerance is millimetres and cannot reach what an
    #: exporter authored as one object in separate pieces: LEMD's
    #: ``OldTerminal_FSX-HANG3`` is a hangar whose four vault arcs stand
    #: 1.507-1.853 m from its two spine components with ZERO ε-contacts
    #: in the rebake plan, and round 2 wrote them at six zeros spanning
    #: 1.37 m — a continuous arcing roof with steps in it, which is what
    #: the owner read at 1.0.320.  SOLID components of ONE resource
    #: whose geometry comes within this CHAIN into one rigid cluster,
    #: and the cluster is the atom of every §16c (1) group.  Line
    #: classes are excluded: a fence's posts are metres apart by design
    #: and chaining them would re-assemble the 2 km run §10 exists to
    #: cut.  0 disarms the reach and leaves §16c (6)'s contact alone.
    rigid_reach_m: float = 2.0

    #: §16f (7) A LARGE TERMINAL CLUSTER IS ONE UNIT ON ONE PAD (owner
    #: RULINGS 2026-09-13bj item 1).  A family (§16f (1)) whose FOOTPRINT
    #: UNION covers more than this is a CLUSTER: every member takes ONE
    #: zero plane — the cluster pad's — with no per-member cut to its own
    #: ground, no pad partition (§16f (4)) and no pavement-is-king
    #: (§16f (5)).  The owner read the alternative at KCLT 1.0.327:
    #: "passengers and seat objects ... sitting on the ground under the
    #: building instead of on the floor inside the building".  5,000 m2
    #: is a terminal, not a hangar: KCLT's terminal complex covers
    #: ~54,000 m2 and the airport's next largest family ~2,000.  0
    #: disarms the clause and leaves 13aq's partition by pad alone.
    cluster_pad_min_m2: float = 5000.0

    #: §16g (1) THE FOOTPRINT UNIT (owner RULINGS 2026-09-13bo,
    #: interviewed): "We always want to keep objects covering the same
    #: footprint together when changing their seat."  Two bodies whose
    #: plan footprints overlap or come within this are ONE UNIT, chained
    #: transitively (deck <-> piers <-> clutter); a body touching nothing
    #: seats alone.  This REPLACES §16f (1)'s shared-authored-datum
    #: condition — overlap alone binds — and it is metres, not the
    #: millimetres of ``contact_eps_m``: an exporter's pier stands beside
    #: its deck, it does not share a vertex with it.  0 disarms §16g.
    footprint_touch_m: float = 0.5

    #: §16g (10) (1) THE PAD IS THE CLUSTER (owner RULINGS 2026-09-14x):
    #: "pads must match building clusters ... they should match exactly."
    #: A CLUSTER is ONE BUILDING, so two bodies chain only if their
    #: footprints touch (§16g (7)) AND their AUTHORED GROUND FLOORS agree
    #: within this; a touching body at a different floor is a different
    #: building, its own cluster, its own pad, and the difference is a
    #: declared terrace step between the two pads (§23).  The floor is
    #: the body's GROUND FLOOR — the lowest GROUND-CONTACT component's
    #: ``base_y`` (RULINGS 2026-09-14z) — and the test is taken between
    #: two GROUND-CONTACT bodies only: read off every component instead,
    #: it splits a tall building per storey (HECA 2,677 -> 20,203
    #: clusters, MEASURED).  0 disarms the split and a touching chain is
    #: one cluster however its floors stand.
    floor_split_m: float = 0.5

    #: §16g (10) (2) (owner RULINGS 2026-09-14x): the design surface's
    #: ``building`` PAD is DERIVED from the cluster — one pad per
    #: cluster, its footprint the cluster's outline union — and the
    #: footprint-cache pads are the fallback only where the plan has no
    #: cluster.  ``false`` restores the pre-14x derivation exactly (every
    #: admitted footprint unioned in ``classify/evidence._pads``) and is
    #: the matched BASE ARM of this law's measurement.
    pad_from_cluster: bool = True

    #: RULINGS 2026-09-14as (i): THE PAD DERIVATION LEAVES THE AIRSIDE
    #: VERTEX SET ALONE.  Every pad — the DERIVED one of §16g (10) (5)
    #: and the footprint-cache FALLBACK alike — is clipped by the airside
    #: union (the runway slabs and every apt.dat pavement page) at the one
    #: derivation site, so ``classify/roles``'s subtraction of the pad
    #: union from the airside region is area-null and the airside polygon
    #: stops being a function of which pads exist.  A pad left wholly
    #: inside airside mints nothing (its bodies seat on the pavement).
    #: ``false`` is the pre-14as derivation, where only the DERIVED half
    #: was clipped and arming ``pad_from_cluster`` at HECA moved 280
    #: airside vertices out and minted 88.
    pad_airside_clip: bool = True

    #: RULINGS 2026-09-14as (i): how far a pad may be moved to put a clip
    #: CROSSING POINT on a rim NODE instead of minting an airside vertex.
    #: Quantising moves the pad along the rim by that rim's own vertex
    #: spacing (HECA p50 4.3 m, max 66 m; a 40 m synthetic shed's corner
    #: travelled 30 m).  Beyond this the crossing point stands and is
    #: counted.  0 disarms the quantisation.
    pad_airside_snap_max_m: float = 5.0

    #: §16g (10) (4) WHAT CHAINS (owner RULINGS 2026-09-14ah): only a
    #: WALLED body links a cluster.  A body whose tallest component's
    #: SOLID HEIGHT (``Part.height_m``) is under this — a floor slab, a
    #: plate, a deck, a canopy, a road, an apron object — is a LEAF: it is
    #: seated on its own ground or its carrier and is NEVER a link between
    #: two walled bodies.  MEASURED at HECA: two single-component
    #: ``T3_4.obj`` plates authored 15.73 m up, solid extent 0.00 m,
    #: carried 1,822 and 1,772 of the T3 district's 9,333 touch edges, and
    #: the district came out as ONE cluster of 9,334 bodies / 541,200 m2.
    #: 2.5 m is a storey: below it nothing can have walls.  0 disarms the
    #: rule and every body chains, as it did before 14ah.
    chain_min_height_m: float = 2.5

    #: §16g (10) (8) REFINED (owner RULINGS 2026-09-14al): THE SKIRT
    #: BAND.  A pad's vertices within this of an edge it SHARES with an
    #: airside face follow the airside ONE-WAY within the pad's slope
    #: ceiling — the airside leads and is never pulled; everything
    #: farther is the pad's cap-0 RIGID CORE and stays flat.  The core is
    #: what keeps the plate a plate: MEASURED, a plate whose EVERY
    #: binding was one-way had no rigid relation in the first lag round
    #: and collapsed 703.56 -> 640.89 m in the §30 twin.  25 m is a
    #: building's own depth from its frontage.  0 is NOT "no skirt": it
    #: is the airside-SHARED vertices alone (round 4's scope), and it is
    #: what SHIPS — the 25 m band was measured WORSE on every airside bar
    #: at HECA (moved 14,263 -> 15,014, the runway 1,021 -> 1,394, worst
    #: 0.41 -> 0.57 m) for the terminal body +0.08 -> +0.00 m.
    pad_skirt_m: float = 0.0

    #: §16g (3) THE ONLY CUT (owner RULINGS 2026-09-13bo): "very long
    #: connecting pieces like the elevated rail at HECA which would
    #: require two buildings kilometers apart to be at the same
    #: elevation".  A body whose footprint span reaches this AND whose
    #: two ends' ground differs by ``[cockpit] visual_m`` is a CONNECTOR:
    #: it is cut at §10's line stations and never holds its unit rigid.
    #: 0 disarms the class and every body stays rigid.
    connector_span_m: float = 200.0
