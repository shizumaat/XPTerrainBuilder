"""Pavement-builder configuration constants.

Single source of truth for every numeric tunable in the airport
pavement builder.  Module-local constants in other O4_Pavement_*
modules should be reserved for values whose meaning is genuinely
specific to that module; anything tuned across the pipeline lives
here so reviewers can audit the whole tuning surface in one place.

For user-facing knobs (GUI / cfg-file persistence) register the
variable in O4_Cfg_Vars.py instead.
"""

__all__ = [
    "LOG_VERBOSITY",
    "AXIS_ALIGN_TOL_DEG",
    "LOAD_DSF_PAVEMENT",
    "DSF_BUILDINGS",
    "AGP_BUILDINGS",
    "DSF_OBJECT_BUILDINGS",
    "DSF_OBJECT_FOOTPRINT_UNION",
    "DSF_OBJECT_REANCHOR",
    "DSF_OBJECT_ALLOW_ANIM",
    "DSF_OBJECT_MIN_REACH_M",
    "DSF_OBJECT_CONTACT_EPSILON_M",
    "DSF_OBJECT_WORKLIST_BBOX_MARGIN_M",
    "DSF_OBJECT_FOOTPRINT_HEIGHT_M",
    "DSF_OBJECT_ELEVATED_BASE_M",
    "DSF_OBJECT_MAX_FOOTPRINT_AREA_M2",
    "DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M",
    "DSF_OBJECT_BAKE_MIN_DELTA_M",
    "DSF_OBJECT_NOBAKE_PAD_FLOOR_M",
    "DSF_OBJECT_CLUSTER_SEATING",
    "DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M",
    "DSF_OBJECT_PAD_MAX_RELIEF_M",
    "DSF_OBJECT_OBJECT_PADS",
    "DSF_OBJECT_SUPPORTER_FATE",
    "DSF_OBJECT_SUPPORTER_SMALLEST",
    "DSF_OBJECT_PAVEMENT",
    "DSF_OBJECT_PAVEMENT_MAX_LAYER_OFFSET",
    "DSF_OBJECT_PAVEMENT_MIN_PATCH_M2",
    "DSF_OBJECT_CONNECTOR_PREFILTER",
    "DSF_OBJECT_CONNECTOR_SPAN_M",
    "DSF_OBJECT_CONNECTOR_MAX_FILL",
    "DSF_OBJECT_MAX_STRUCTURE_SPAN_M",
    "DSF_OBJECT_MIN_BUILDING_HEIGHT_M",
    "DSF_OBJECT_BUILDING_EVIDENCE",
    "DSF_OBJECT_NAME_VOUCH_SCOPED",
    "DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M",
    "DSF_OBJECT_EVIDENCE_MIN_COVERAGE",
    "DSF_OBJECT_PAD_FLAG_SPAN_M",
    "DSF_OBJECT_FOOT_ANCHOR",
    "DSF_OBJECT_FOOT_MIN_REACH_M",
    "DSF_OBJECT_FOOT_BAND_M",
    "DSF_OBJECT_FOOT_CLUSTER_GAP_M",
    "DSF_OBJECT_FOOT_MAX_BASE_SPREAD_M",
    "DSF_OBJECT_FOOT_CONTACT_TOLERANCE_M",
    "DSF_OBJECT_FOOT_PAD_RESIDUAL_M",
    "DSF_OBJECT_FOOT_PAD_MARGIN_M",
    "DSF_OBJECT_PAD_PLAN_BOX_FALLBACK_MAX_M2",
    "DSF_CLUSTER_OSM_ABSORB_FRAC",
    "DSF_CLUSTER_SIMPLIFY_TOL_M",
    "BUILDING_OUTLINE_FILL_R",
    "BUILDING_OUTLINE_FILL_GATE_M",
    "BUILDING_CLOSE_MIN_PIECE_M2",
    "TERM_BRIDGE_GROUPING",
    "TERMINAL_SIMPLIFY_TOL_M",
    "SLOPING_EDGE_SNAP_M",
    "ENABLE_SERVICE_ROADS",
    "SERVICE_SOURCE_DEDUPE",
    "SERVICE_SOURCE_DEDUPE_FRAC",
    "AIRPORT_ROAD_FEED",
    "AIRPORT_ROAD_FEED_CACHE",
    "AIRPORT_ROAD_FEED_PAD_M",
    "PAVEMENT_CLASS_V1",
    "PAVEMENT_CLASS_MOUTH_SPLIT",
    "PAVEMENT_CLASS_AIRSIDE_KEEP_FRAC",
    "PAVEMENT_CLASS_ROAD_DOMINANT_FRAC",
    "PAVEMENT_CLASS_AIRSIDE_WEAK_FRAC",
    "PAVEMENT_CLASS_PARKING_FRAC",
    "PAVEMENT_CLASS_ROAD_PARTIAL_FRAC",
    "PAVEMENT_CLASS_AIRSIDE_NONE_FRAC",
    "PAVEMENT_CLASS_RUNWAY_STANDOFF_M",
    "PAVEMENT_CLASS_STAND_BUFFER_M",
    "PAVEMENT_CLASS_TAXI_BUFFER_M",
    "PAVEMENT_CLASS_AEROWAY_LINE_BUFFER_M",
    "PAVEMENT_CLASS_MIN_AREA_M2",
    "PAVEMENT_CLASS_TAIL_MAX_WIDTH_M",
    "PAVEMENT_CLASS_TAIL_MIN_LENGTH_M",
    "PAVEMENT_CLASS_TAIL_ROAD_FRAC",
    "PAVEMENT_CLASS_TAIL_AXIS_ROAD_FRAC",
    "PAVEMENT_CLASS_FLANK_CLEAR_M",
    "PAVEMENT_CLASS_TAIL_MAX_FLANK_CONTACT",
    "PAVEMENT_CLASS_SPLIT_MIN_BODY_AREA_M2",
    "PAVEMENT_CLASS_SPLIT_MIN_TAIL_AREA_M2",
    "PAVEMENT_CLASS_SPLIT_MAX_RING_VERTICES",
    "PAVEMENT_SCORE_V2",
    "PAVEMENT_SCORE_PURE",
    "SCORER_SERVICE_ADJ",
    "SCORER_CORRIDOR_WIDTH",
    "SCORER_CORRIDOR_WIDTH_MIN_FRAC",
    "LATERAL_CONTIGUITY_LAW_ENABLED",
    "PAVEMENT_SCORE_WEIGHTS",
    "PAVEMENT_SCORE_RELIABILITY",
    "PAVEMENT_SCORE_MIN_AREA_M2",
    "PAVEMENT_SCORE_MARGIN_HIGH",
    "PAVEMENT_SCORE_MARGIN_MED",
    "PAVEMENT_SCORE_VETO_FRAC",
    "PAVEMENT_SCORE_TAXI_MAJOR_MIN",
    "PAVEMENT_SCORE_WIDE_HALF_M",
    "PAVEMENT_SCORE_THREAD_MIN_FRAC",
    "PAVEMENT_SCORE_SPINE_BUFFER_M",
    "PAVEMENT_SCORE_TRUCK_BUFFER_M",
    "PAVEMENT_SCORE_SEVER_MIN_AREA_M2",
    "PAVEMENT_SCORE_SEVER_PINCH_MAX_M",
    "PAVEMENT_SCORE_SEVER_FRONTAGE_W_M",
    "PAVEMENT_SCORE_BOUNDARY_OUT_FRAC",
    "PAVEMENT_SCORE_RUNWAY_CONTACT_TOL_M",
    "PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_M",
    "PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_FRAC",
    "PAVEMENT_SCORE_APRON_MIN_HALF_WIDTH_M",
    "PAVEMENT_SCORE_TUNNEL_VETO_FRAC",
    "PAINTED_CENTERLINE_FALLBACK",
    "ENABLE_APRON_NECK_SPLIT",
    "HOLE_ROUTER_ENABLED",
    "HOLE_ROUTER_V2",
    "EMIT_BRIDGES_AND_TUNNELS",
    "JUNCTION_CLUSTER_DIST_M",
    "MIN_SEGMENT_LEN_M",
    "NECK_ABSOLUTE_M",
    "NECK_ABSORB_FRAC",
    "NECK_RELATIVE",
    "ROLE_GRADE_LIMITS",
    "FLAT_SITE_FAST_PATH",
    "FLAT_SITE_FAST_PATH_QUANTUM_M",
    "FLATNESS_CERTIFICATE_RATE_FACTOR",
    "FLAT_CERTIFICATE_COVERAGE",
    "REACH_BAND_CLUSTERS",
    "RASTER_REACH_BAND_CELL_M",
    "RASTER_REACH_BAND_CONNECTIVITY",
    "RASTER_REACH_BAND_OFFNET_RADIUS_M",
    "RASTER_REACH_BAND_MAX_CELLS",
    "VECTORIZED_GEOMETRY",
    "HOLE_ROUTER_MID_EDGE_PRUNE",
    "RECT_CROSS_FLATNESS_TOLERANCE_M",
    "BUILDING_SEAT_FLATNESS_TOLERANCE_M",
    "BUILDING_FRONTAGE_NEAR_MISS_M",
    "NEAR_MISS_FRONTAGE_SOFT_ROLES",
    "near_miss_frontage_budget",
    "TAXI_MAX_GRADE",
    "APRON_MAX_GRADE",
    "APRON_TERRACE_MIN_EXCESS_M",
    "APRON_TERRACE_MAX_STEP_M",
    "APRON_TERRACE_JOINT_CLEARANCE_M",
    "APRON_TERRACE_CORRIDOR_HALF_WIDTH_M",
    "APRON_TERRACE_MIN_JOINT_LEN_M",
    "APRON_TERRACE_FACING_STEP_M",
    "APRON_TERRACE_FACING_PROXIMITY_M",
    "BUILDING_FRONTAGE_MAX_GRADE",
    "TERMINAL_MAX_GRADE",
    "TERMINAL_PADS_SLOPE",
    "TAXI_CORRIDOR_PROFILE",
    "TAXIWAY_CURVE_RUN_M",
    "TAXIWAY_MAX_GRADE_CHANGE_PER_M",
    "SERVICE_ROAD_MAX_GRADE",
    "SVC_PROFILE_REVERSAL_MIN_M",
    "SERVICE_ROAD_MAX_TRANSVERSE",
    "SERVICE_ROAD_CROWN_TRANSVERSE",
    "SVC_SPINE_FIRST",
    "SVC_SPINE_EDGE_COUPLE",
    "RUNWAY_CROWN_TRANSVERSE",
    "TAXI_CROWN_TRANSVERSE",
    "ENABLE_SPINE_CROWN",
    "CROWN_RUNWAYS",
    "CROWN_TAXI",
    "CROWN_SERVICE",
    "RUNWAY_CROWN_SEAM_TAPER",
    "CROWN_SEAM_RAMP",
    "CROWN_SPINE_SEAM_WELD",
    "SERVICE_ROAD_WIDTH_M",
    "MIN_SERVICE_STRIP_LEN_M",
    "OSM_SMALL_ROAD_HIGHWAY_TYPES",
    "OSM_NON_DRIVABLE_HIGHWAY_TYPES",
    "OSM_RAIL_TRACK_TYPES",
    "SERVICE_ROAD_PAVEMENT_NEAR_M",
    "RUNWAY_MAX_GRADE",
    "RUNWAY_END_GRADE",
    "RUNWAY_END_FRACTION",
    "TUNNEL_RAMP_MAX_GRADE",
    "SKIP_TUNNEL_RAMPS_NEAR_ROADS",
    "TUNNEL_ADJACENT_ROAD_DIST_M",
    "TUNNEL_FORK_THROAT",
    "TUNNEL_DEM_CUT_MIN_DROP_M",
    "TUNNEL_DEM_CUT_WINDOW_M",
    "TUNNEL_MOUTH_PLATE_LENGTH_M",
    "TUNNEL_MOUTH_WINDOW_M",
    "TUNNEL_ROOF_PLATE_MAX_LENGTH_M",
    "GROUNDSIDE_MAX_GRADE",
    "GROUNDSIDE_PAVEMENT_MAX_GRADE",
    "GROUNDSIDE_BAND_OFFNET_RADIUS_M",
    "FAN_RAMP_CAP",
    "FAN_RAMP_LAW",
    "fan_ramp_law_cap",
    "RUNWAY_VERTICAL_CURVE_K_M",
    "RUNWAY_MAX_GRADE_CHANGE_PER_M",
    "RUNWAY_DEM_FOLLOW_LAW_BAND_M",
    "runway_dem_follow_band_m",
    "RUNWAY_FLEX_MAX_ROUNDS",
    "RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M",
    "RUNWAY_FLEX_DEMAND_TOL_M",
    "runway_flex_demand_tol_m",
    "POST_SOLVE_IDEMPOTENCE_TOL_M",
    "RUNWAY_FLEX_ENDZONE_MATERIALITY",
    "GRADE_VISIBILITY_BUFFER_M",
    "ELEV_ROUNDING_NOISE_M",
    "SLOPED_QUAD_ROUNDING_NOISE_M",
    "ROUTE_FIELD_MODEL",
    "ROUTE_FIELD_LOCAL_WINDOW_M",
    "SURFACE_FAIRING",
    "SURFACE_FAIRING_MAX_MOVE_M",
    "APRON_CORRIDOR_SMOOTH_RADIUS_M",
    "APRON_CORRIDOR_SMOOTH_GRADE",
    "APRON_CORRIDOR_GEODESIC",
    "APRON_CORRIDOR_SEED_RADIUS_M",
    "APRON_BACK_EDGE_GRADE",
    "APRON_BACK_EDGE_RAMPS",
    "APRON_TAXI_BLEND",
    "APRON_TAXI_TRANSITION_M",
    "TAXI_SLACK_TERMINALS",
    "WRITE_ARBITRATION",
    "TERMINAL_LEAF_LEVELS",
    "TERMINAL_NATURAL_LEVELS",
    "HANGAR_PADS",
    "RUNWAY_ADJACENCY_TOL_M",
    "RUNWAY_BOUNDARY_TOL_M",
    "RUNWAY_INSIDE_APRON_FRAC",
    "RUNWAY_APRON_AREA_RATIO",
    "SLIVER_ANGLE_THRESHOLD_DEG",
    "RUNWAY_CELL_SIZE_M",
    "PATCH_SLOPE_PROFILE",
    "CLEARANCE_OBSTRUCTION_THRESHOLD_M",
    "CLEARANCE_MAX_REACH_M",
    "CLEARANCE_STATION_STEP_M",
    "RUNWAY_END_CLEARANCE_LENGTH_BY_CODE",
    "RUNWAY_END_RESA_MAX_SLOPE",
    "CLEARANCE_LATERAL_MAX_SLOPE",
    "RUNWAY_STRIP_HALF_WIDTH_BY_CODE",
    "RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_BY_CODE",
    "RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_FAA",
    "STRIP_PRECEDENCE_ENABLED",
    "WINGSPAN_BY_CODE_LETTER",
    "TAIL_HEIGHT_BY_CODE_LETTER",
    "TAXIWAY_WINGTIP_MARGIN_M",
    "EAT_SURFACE_CEILING_ENABLED",
    "EAT_FAA_DEPARTURE_SLOPE",
    "EAT_FAA_SETBACK_M",
    "EAT_EASA_TAKEOFF_CLIMB_SLOPE",
    "EAT_EASA_SETBACK_M",
    "EAT_MIN_CROSSING_DIST_M",
    "EAT_CORRIDOR_HALF_WIDTH_M",
    "EAT_RECT_SEGMENT_GAP_M",
    "EAT_MIN_RUNWAY_CODE_NUMBER",
    "EAT_RECT_MAX_ALONG_M",
    "EAT_FAA_ICAO_PREFIXES",
    "eat_surface_slope_and_setback",
    "runway_code_letter",
    "ADJACENT_GROUND_LIP_WIDTH_M",
    "ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE",
    "ADJACENT_GROUND_LIP_MAX_DOWN_SLOPE",
    "RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE",
    "RUNWAY_STRIP_BAND_MAX_DOWN_SLOPE_BY_CODE",
    "TAXIWAY_STRIP_BAND_MIN_DOWN_SLOPE",
    "TAXIWAY_STRIP_BAND_MAX_DOWN_SLOPE",
    "TAXIWAY_STRIP_GRADED_HALF_WIDTH_BY_LETTER",
    "taxiway_strip_graded_half_width_for_letter",
    "ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE",
    "ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT",
    "GAP_FILL_SPINE_ENABLED",
    "GAP_FILL_SPINE_STEP_M",
    "GAP_FILL_MAX_WIDTH_M",
    "GAP_FILL_MIN_AREA_M2",
    "GAP_FILL_INTERIOR_FLOOR_ENABLED",
    "GAP_FILL_INTERIOR_RINGS_ENABLED",
    "OPEN_FRONTAGE_CLOSE_M",
    "GAP_FILL_RIM_POCKETS_ENABLED",
    "GAP_FILL_RIM_POCKET_GRADED_FRACTION",
    "ONE_SOLVE_TERRAIN",
    "ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT",
    "ONE_SOLVE_TERRAIN_RUNWAY_END_RESA",
    "ONE_SOLVE_TERRAIN_GAP_FILL_SPINE",
    "ONE_SOLVE_TERRAIN_GRADED_STRIP",
    "ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT",
    "ADJACENT_GROUND_FULL_EXTENT_COVERAGE",
    "ADJACENT_GROUND_COVERAGE_DEPTH_STEP_M",
    "ADJACENT_GROUND_ZONE_STATIC_KEEPOUT_M",
    "APRON_SHOULDER_WIDTH_M",
    "APRON_SHOULDER_MIN_DOWN_SLOPE",
    "APRON_SHOULDER_MAX_DOWN_SLOPE",
    "APRON_BEYOND_SHOULDER_MAX_DOWN_SLOPE",
    "APRON_EDGE_WALL_MIN_DROP_M",
    "runway_code_number",
    "runway_strip_half_width_m",
    "runway_end_clearance_length_m",
    "runway_end_approach_class",
    "RUNWAY_END_SKIRT_ENABLED",
    "RUNWAY_END_RESA_ENABLED",
    "ADJACENT_GROUND_END_PIN_ENABLED",
    "STRIP_WIDTH_FROM_CENTERLINE_ENABLED",
    "POCKET_COLLAR_RINGS_ENABLED",
    "CONFORMANCE_CUT_CLAMP_ENABLED",
    "BAND_RAY_OCCLUSION_ENABLED",
    "OLS_CUT_ENABLED",
    "OLS_TRANSITIONAL_SLOPE",
    "OLS_TRANSITIONAL_SLOPE_STEEP",
    "OLS_STRIP_HALF_WIDTH_INSTRUMENT_BY_CODE",
    "OLS_APPROACH_SETBACK_M",
    "OLS_APPROACH_SETBACK_VISUAL_CODE1_M",
    "OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M",
    "OLS_APPROACH_DIVERGENCE",
    "OLS_APPROACH_FIRST_SECTION_SLOPE",
    "OLS_TRANSITIONAL_EMIT_REACH_M",
    "OLS_APPROACH_EMIT_REACH_M",
    "OLS_MAX_CUT_DEPTH_M",
    "OLS_OBSTRUCTION_THRESHOLD_M",
    "OLS_SEAM_TILE_LINE_REFUSAL",
    "OLS_ROAD_REGRADE_ENABLED",
    "OLS_ROAD_REGRADE_FOLLOW_M",
    "OBJECT_BRIDGE_TERRAIN",
    "OBJECT_TUNNEL_TERRAIN",
    "OBJECT_SPLIT_LEVEL_TERRAIN",
    "OBJECT_BASIN_TRENCH",
    "TUNNEL_FLOOR_BELOW_OBJECT_DECK_M",
    "BRIDGE_ROAD_CLEARANCE_M",
    "BRIDGE_ROAD_CLEARANCE_MINIMUM_M",
    "BRIDGE_CORRIDOR_DEPRESSED_LENGTH_M",
    "BRIDGE_ABUTMENT_PIN_CAPTURE_BAND_M",
    "BRIDGE_CAUSEWAY_MAX_LENGTH_M",
    "TUNNEL_PORTAL_PAIR_MIN_SPACING_M",
    "TUNNEL_PORTAL_PAIR_MAX_SPACING_M",
    "TUNNEL_PORTAL_PAIR_HEADING_TOLERANCE_DEGREES",
    "TUNNEL_PORTAL_PAIR_BURIED_MARGIN_M",
    "PORTAL_FACE_PLATE_SHOULDER_M",
    "PORTAL_FACE_PLATE_DEPTH_M",
    "PORTAL_FACE_ANCHOR_SEAT_HALF_WIDTH_M",
    "PORTAL_FACE_ANCHOR_SEAT_OUTWARD_M",
    "PORTAL_FACE_ANCHOR_SEAT_INWARD_M",
    "PORTAL_FACE_ANCHOR_SEAT_CLEARANCE_M",
    "TUNNEL_PORTAL_MOUTH_SAMPLE_RANGE_M",
    "TUNNEL_PORTAL_CROWN",
    "TUNNEL_PORTAL_CROWN_COLLAR_M",
    "BRIDGE_CAUSEWAY_WELD_PIN_BAND_M",
    "BRIDGE_CROSSING_MASK",
    "PRECISION_APPROACH_LIGHT_CODES",
    "PRECISION_MARKINGS_CODES",
    "NON_PRECISION_MARKINGS_CODES",
    "VISUAL_MARKINGS_CODE",
    "taxiway_code_letter",
    "taxiway_clearance_half_width_m",
    "taxiway_clearance_half_width_for_letter",
    # ── region rulesets (phase B) ──
    "CodeTable",
    "Ruleset",
    "RULESETS",
    "DEFAULT_RULESET",
    "ICAO_RULESET",
    "FAA_RULESET",
    "ADG_BY_CODE_LETTER",
    "FAA_RSA_HALF_WIDTH_M_BY_LETTER",
    "FAA_ROFA_HALF_WIDTH_M_BY_LETTER",
    "FAA_RULESET_FIRST_LETTERS",
    "FAA_RULESET_TWO_LETTER_PREFIXES",
    "RULESET_SPLIT_FAMILIES",
    "GROUNDSIDE_MIN_DRAINAGE_GRADE",
    "GROUNDSIDE_MIN_DRAINAGE_GRADE_PROVISIONAL",
    "CROWN_MINIMUM_BOUND_RUNWAYS",
    "CROWN_MINIMUM_BOUND_TAXIWAYS",
    "resolve_ruleset",
    "get_ruleset",
    "ruleset_runway_max_grade",
    "ruleset_runway_end_grade",
    "ruleset_runway_end_zone_length_m",
    "ruleset_runway_max_grade_change",
    "ruleset_runway_vertical_curve_k_m",
    "ruleset_runway_max_grade_change_per_m",
    "ruleset_runway_vertical_curve_min_change",
    "ruleset_strip_max_longitudinal_slope",
    "ruleset_strip_arc_rate_per_m",
    "ruleset_strip_half_width_m",
    "ruleset_strip_band_max_down_slope",
    "ruleset_taxi_max_grade",
    "ruleset_taxi_transverse_max",
    "ruleset_stand_max_grade",
    "ruleset_apron_min_drainage_grade",
    "ruleset_apron_max_grade_change",
    "ruleset_shoulder_transverse_band",
    "ruleset_shoulder_edge_dropoff",
    # ── the fabric-model reg set (W1, 2026-08-08) ────────────────────
    "FAA_VISIBILITY_MINIMA",
    "FAA_VISIBILITY_DEFAULT",
    "FAA_AAC_GROUPS",
    "FAA_ADG_NUMERALS",
    "FAA_RDC_BY_CODE_LETTER",
    "FAA_RSA_WIDTH_FT_BY_RDC",
    "FAA_ROFA_WIDTH_FT_BY_RDC",
    "FAA_ROFA_WIDTH_FT_SMALL_AIRCRAFT",
    "FAA_RSA_LENGTH_BEYOND_END_FT_BY_RDC",
    "FAA_RSA_LENGTH_PRIOR_TO_THRESHOLD_FT_BY_RDC",
    "FAA_TAXIWAY_SHOULDER_WIDTH_FT_BY_TDG",
    "FAA_TAXIWAY_SHOULDER_WIDTH_M_BY_TDG",
    "FAA_TAXIWAY_SHOULDER_WIDTH_FT_TDG6_FOUR_ENGINE",
    "FAA_TAXIWAY_SHOULDER_WIDTH_M_TDG6_FOUR_ENGINE",
    "ICAO_TAXIWAY_PLUS_SHOULDERS_TOTAL_WIDTH_M",
    "faa_rsa_width_ft",
    "faa_rsa_half_width_m",
    "faa_rofa_width_ft",
    "faa_rofa_half_width_m",
    "faa_rsa_end_length_m",
    "faa_rsa_end_datum_offset_m",
    "faa_rsa_governed_length_beyond_runway_end_m",
    "ruleset_strip_half_width_m_instrument",
    "ruleset_strip_band_authority_min_down_slope",
    "ruleset_strip_band_mandatory_down",
    "ruleset_runway_edge_lip",
    "ruleset_taxiway_edge_lip",
    "ruleset_taxiway_lip_carved_out_of_band",
    "ruleset_tofa_back_slope_ratio",
    "ruleset_taxi_transverse_min_provisional",
    "ruleset_taxi_crown_form_binding",
    "ruleset_taxiway_shoulder_width_m",
    "ruleset_taxiway_shoulder_paved_from_adg",
    "ruleset_taxiway_plus_shoulders_total_width_m",
    "ruleset_resa_length_datum",
    "ruleset_strip_beyond_end_m",
    "ruleset_resa_length_m",
    "RULESET_W2_FLIPS",
    "REG_AUTHORITY_CLASSES",
    "RegEntry",
    "REG_SET_ENTRIES",
    "REG_SET_ENTRY_INDEX",
    "reg_entry",
]


# ── Build logging verbosity ─────────────────────────────────────
# Single knob for how chatty an auto-patch build is.  Auto-patch sets
# ``O4_UI_Utils.verbosity`` to this when it runs.  Build-time
# verification ALWAYS runs (it's how we surface "this airport has
# errors") — this only controls how much else is printed.
#   2 = debug  : every progress / diagnostic message.
#   1 = normal : per-airport progress + verification summary.
#   0 = critical: only verification PROBLEMS + errors — the default, so
#                 a normal Ortho4XP run's output window stays quiet
#                 except when an airport patch has issues.
# CHATTER VOLUME ONLY.  It used to also gate the ``<patch>.axes.json``
# grade-law sidecar (user 2026-07-02, to keep production patch dirs
# clean); that gate is GONE (2026-08-05) — a debug-verbosity flag must
# never decide whether measurement is possible, and at the default it
# made every standalone census silently context-free.  The sidecar is
# written on every emit.  Env override O4_LOG_VERBOSITY for dev builds.
# (``import os as _os`` only enters scope further down this file.)
import os as _os_early  # noqa: E402
try:
    LOG_VERBOSITY = int(_os_early.environ.get("O4_LOG_VERBOSITY", "0"))
except ValueError:
    LOG_VERBOSITY = 0


# ── Junction-refinement rule constants (user 2026-05-01) ─────────
# Plan: ``/Users/noah/.claude/plans/kind-meandering-sifakis.md``.

# Rule 2: junction vertex within this distance of a sloping-rect
# edge (any edge — sloping or cross — of a rect with a sloping role)
# gets snapped to the nearest rect corner.
# Per user 2026-05-04: bumped 10 m → 20 m to match the runway snap
# (RUNWAY_ADJACENCY_TOL_M).  10 m left vertices like SPJC junction
# -10153's v5 (17.88 m perpendicular to V3's edge) outside the snap
# radius, which forced the junction polygon to cut across V3 and
# produce a 1012 m² overlap.
SLOPING_EDGE_SNAP_M = 20.0

# Rule 4: a junction polygon is split at its narrowest cross-section
# when that thickness is below NECK_ABSOLUTE_M (in metres) OR is
# below NECK_RELATIVE × the polygon's MRR long-side length
# (whichever fires first per user 2026-05-01).
NECK_ABSOLUTE_M = 5.0
NECK_RELATIVE = 0.10
# A piece resulting from a neck split is absorbed into a neighbouring
# rect / junction / apron when the neighbour shares more than this
# fraction of the piece's perimeter.
NECK_ABSORB_FRAC = 0.70

# Rule 1: a junction vertex is "on the runway boundary" when within
# this distance of the runway polygon edge.  Used to identify the
# runway-adjacent vertex run that gets replaced with the runway's
# exact node sequence.
RUNWAY_BOUNDARY_TOL_M = 1.5

# Rule 1 v2 (user 2026-05-02): the WIDER tolerance for detecting
# vertices in a junction's runway-facing region.  Vertices in this
# band but outside RUNWAY_BOUNDARY_TOL_M still count as part of the
# junction's joining edge that needs to widen out to the next
# runway node.
#
# Bumped 5 m → 20 m per user 2026-05-04: any junction vertex within
# 20 m of the runway boundary should snap 1:1 to a runway segment
# corner — no extra nodes floating near the runway.  The 5 m band
# left vertices that had been pushed off the runway boundary by Rule
# 5 (1 m perp) plus densification (2 m boundary-trace noise) outside
# the snap radius; 20 m comfortably captures both.
RUNWAY_ADJACENCY_TOL_M = 20.0

# Rule 3 test tolerance: a non-pavement, non-anchor junction edge
# must run parallel or perpendicular to the longest runway axis
# within this many degrees.
AXIS_ALIGN_TOL_DEG = 2.0


# Drop emitted line/segment fragments shorter than this length.
# Shared across centerline extraction, taxi-rect splitting, and the
# Phase-A apt.dat-rect chain construction.
MIN_SEGMENT_LEN_M = 15.0


# Cluster of junction-corner candidates: any two within this
# distance get merged when computing the residue's seam points.
JUNCTION_CLUSTER_DIST_M = 40.0

# Interior angles below this threshold count as "needle-tip"
# slivers.  Residue construction can leave thin wedges where
# rect / terminal edges meet the apt.dat boundary at near-collinear
# angles.  The polygon is shapely-valid but a sub-2 deg corner
# forces Triangle4XP to emit a near-degenerate triangle there --
# crashes X-Plane's mesh builder.  Caught at junction-emission
# time by _drop_sliver_corners (drops just the tip vertex), and
# again by a to_osm safety net (drops the whole shape if any
# slipped through).
SLIVER_ANGLE_THRESHOLD_DEG = 2.0


# Apron-merged runway detection: when at least this fraction of a
# runway-segment polygon lies inside an apt.dat / DSF apron polygon
# (and that polygon is much larger than the segment — see
# RUNWAY_APRON_AREA_RATIO), the segment is treated as apron-merged
# and the separate rect is dropped.
RUNWAY_INSIDE_APRON_FRAC = 0.95
# The containing apt.dat / DSF polygon must be >= this ratio times
# the segment area to count as an apron.
RUNWAY_APRON_AREA_RATIO = 3.0
# ABSORB_RUNWAY_IN_APRON gate is defined below, where ``import os as _os`` is in
# scope (search ABSORB_RUNWAY_IN_APRON).

# Bridge / tunnel emission flag.  Gates the four feature emit calls
# in build_airport_pavement: _emit_through_airport_depressed_roads,
# _emit_tunnel_portals, _emit_taxi_bridges,
# _emit_underpass_road_approaches.  Each carves its footprint out of
# overlapping airside / groundside pavement before emitting so
# ``test_no_self_overlap`` stays green.
EMIT_BRIDGES_AND_TUNNELS = True

# Through-airport depressed roads (user 2026-06-10): DISABLED for now —
# instead of depressing a road's entire inside-airport stretch to
# apt_elev−8 m (open trench), only the tunnel-portal ramps are built
# (the road descends at each portal and the tunnel-tagged stretch stays
# under the airport surface).  The pre-solve terminal-gap carve is
# gated on this too (no trench → no gap through the terminals).
EMIT_DEPRESSED_ROADS = False

# Combine apt.dat with DSF pavement polygons: when True the
# smart-apt.dat selector still runs to choose the best custom-pack
# vs global candidate by OSM coverage; DSF polygons supplement
# whichever apt.dat is picked.
LOAD_DSF_PAVEMENT = True

# Pull TERMINAL and HANGAR building footprints from the DSF
# (user 2026-06-12).  X-Plane places airport buildings as draped
# FACADE polygons (``.fac``) in the Global Airports / scenery-pack
# DSF; ``dsf_reader.read_dsf_buildings`` extracts the footprints of
# the terminal (``term_building_*.fac``) and hangar (``*hangar*.fac``)
# facades.  These are UNIONED with the OSM-derived building outlines
# in ``terminals``/``pipeline`` — see the OSM-terminal-way authority law
# below for which source wins where they describe the SAME building.
# Off = byte-identical to the OSM-only behaviour.  Env override
# ``O4_DSF_BUILDINGS`` is read below, next to HANGAR_PADS (where
# ``import os as _os`` is in scope).

# OSM TERMINAL-WAY AUTHORITY (owner 2026-08-09, OTHH bug report;
# docs/specs/osm-terminal-way-authority-spec.md).  An OSM terminal way
# IS the identity of its building: where OSM and the DSF describe the
# same building the OSM way wins the FOOTPRINT and the DSF clusters
# under it are ABSORBED.  A DSF cluster is absorbed when this fraction
# of the CLUSTER's own area lies inside any kept OSM terminal way —
# majority-inside means the way already represents it.  A cluster
# mostly OUTSIDE every way (jet bridge, fixed link, canopy hanging off
# the facade) stays a separate pad, whole — never clipped.  Raising it
# keeps more DSF swarm pads; lowering it absorbs more into the way.
# Retired with this law: DSF_BUILDING_OSM_OVERLAP_FRAC (0.2), which
# DROPPED the OSM way instead — OTHH's 151k m² Concourse C became 32
# flat pads.  Env override ``O4_DSF_CLUSTER_OSM_ABSORB_FRAC`` is read
# below, next to DSF_BUILDINGS (where ``import os as _os`` is in scope).

# DSF facade-cluster cleanup (user 2026-06-15).  Clustering unions the DSF
# facade pieces with a 0.25 m snap-buffer; that buffer ROUNDS every corner,
# so a complex terminal comes out with hundreds-to-thousands of arc
# vertices (HECA's main terminal: 1,280 verts + 2 spurious interior holes;
# a gate-finger pier: 1,669) — noise that wrecks the downstream outline
# close (it splits on the jagged spine) and the overlap-clip.  Each cluster
# is reduced to a SOLID footprint (buffer-artifact holes filled — a grading
# pad is solid) and DP-simplified at this tolerance to strip the arc noise
# while keeping the real corners.  0.5 m → HECA terminal 1,280→139 verts.
DSF_CLUSTER_SIMPLIFY_TOL_M = 0.5

# DSF facade-piece MERGE GAP (user 2026-06-23).  A single building is often
# placed as MANY scattered facade pieces — e.g. a "pier_wooden"-style concourse
# rendered as dozens of ~0.6 m² panels with 1–3 m gaps between them.  The 0.25 m
# snap (DSF_CLUSTER_SIMPLIFY_TOL_M's sibling) only closes hairline seams, so each
# panel stays an isolated sub-min-area piece and is DROPPED — the building gets no
# pad (CYXY: 68/97 recognized facades, the gate string past building5).  Bridge
# gaps up to this distance so the pieces of one building MERGE into one cluster
# (then the outline-close traces the containing pad).  Kept modest so genuinely
# separate buildings (terminal gates are typically > 2× this apart) don't merge.
# User ruling: an approved facade inside/overlapping/unclosed must still be kept
# and get a containing pad.  (Plain consts — ``_os`` is not in scope this early
# in the file; see the import-os note above.)
DSF_FACADE_MERGE_GAP_M = 2.0
# Min cluster area to emit a building pad.  Lowered from 100 (which dropped real
# small hangars/buildings) to keep approved buildings; a degenerate-noise guard only.
DSF_MIN_BUILDING_AREA_M2 = 20.0

# Building-pad outline NARROW-GAP FILL (user 2026-06-15).  Gate stands are
# small fingers extending perpendicular off a pier; the gaps between them
# give a terminal a noisy sawtooth boundary that the apron then has to
# step around.  We fill only those NARROW gaps and leave genuine open
# spaces (a U courtyard, the space between two piers, the open centre of a
# finger comb) untouched:
#     closed = pad.close(R)      # dilate→erode: bridges EVERY gap up to 2R
#     fill   = closed − pad      # all the area the close added
#     wide   = fill.open(GATE)   # the WIDE fills — open courtyards / centres
#     result = closed − wide     # keep only the narrow teeth-gaps filled
# R (FILL_R) sets how far the fill reaches to bridge a teeth gap; a gap
# WIDER than 2×GATE (FILL_GATE_M) is reopened as a genuine open space.
# Subtracting the wide fill from the connected closed shape keeps the pad
# in ONE piece (no floating rinds, no severed spines) — which is why this
# replaces the old plain morphological close that left HECA's sparse,
# wide-gapped stands as a sawtooth.  Applied per-pad, so it never merges
# two separate buildings.  MITRE join → straight square edges.  Robust
# across topologies (U-terminals, blob+pier, bars, long buildings) without
# any limb decomposition.  FILL_R = 0 disables (raw pad kept).
BUILDING_OUTLINE_FILL_R = 110.0
BUILDING_OUTLINE_FILL_GATE_M = 55.0

# If the wide-fill subtraction ever pinches the pad into separate blobs,
# each significant piece ≥ this area is emitted as its own pad (the normal
# result is a single connected piece).
BUILDING_CLOSE_MIN_PIECE_M2 = 2000.0

# Douglas-Peucker tolerance for the building-pad simplification pass
# (pipeline, applied to every OSM/DSF terminal+hangar footprint).  A
# small tolerance removes only sub-pad noise — closely-spaced OSM
# vertices and the arc facets left by the DSF facade-cluster snap-buffer
# — that would otherwise spawn sliver triangles in the ear-clip, while
# PRESERVING the real building corners.  Was 2.0 m (user 2026-06-14:
# "dial that back a bit" — at 2 m the more articulated terminal pads
# lost genuine corners, e.g. SPJC terminal4/6 10→7, terminal7/9 11→9).
# 1.0 m recovers those corners; dropping to 0.5 m recovered a few more
# but over-constrained the apron solve (4 new within-shape apron grade
# violations at SPJC) — 1.0 m is the balance point.  The south-concourse
# DSF slabs (true 4-corner rects) stay ~5 verts regardless.
TERMINAL_SIMPLIFY_TOL_M = 1.0

# SURFACE-attribute classification of DSF draped polygons (user
# 2026-07-05): resolve each POLYGON_DEF ``.pol`` resource (pack file,
# else the library.txt virtual→physical map) and read its declared
# ``SURFACE`` — asphalt/concrete is pavement REGARDLESS of the resource
# name, a declared soft surface (grass/dirt/gravel/…) vetoes it, and
# resources with no SURFACE fall back to the material-token name
# heuristics below.  See ``dsf_reader._classify_pavement_def``.
DSF_SURFACE_POLYGONS = (
    _os_early.environ.get("O4_DSF_SURFACE_POLYGONS", "1") == "1")

# Third-party DSF pavement descriptors (user 2026-06-10, KPHX south
# aprons): a third-party ``.pol`` is trusted as BASE pavement when its
# path contains one of these material descriptors — the common naming
# convention across scenery libraries (ZDP_Library/.../concrete/flat/
# Flat_New_Uniform.pol, MisterX_Library/Ground_Textures/Asphalt_2_
# Base.pol, …).  Per user: "asphalt" and "concrete" plus their French,
# German, Spanish, Italian and Portuguese equivalents.  Decorative /
# non-pavement uses of the same words (lines, markings, stains, …) are
# rejected by the skip-token list in ``dsf_reader``.
DSF_PAVEMENT_MATERIAL_TOKENS = (
    # English
    "asphalt", "concrete",
    # French (asphalte, béton)
    "asphalte", "beton", "béton",
    # German (Asphalt — same spelling — and Beton, covered above)
    # Spanish (asfalto, hormigón / concreto)
    "asfalto", "hormigon", "hormigón", "concreto",
    # Italian (asfalto — same as Spanish — and calcestruzzo)
    "calcestruzzo",
    # Portuguese (asfalto — covered — and betão / concreto — covered)
    "betao", "betão",
)

# ── Extent-based runway shoulder widening (user 2026-06-12, KPHL) ──
# Shoulders carried by a DSF base-texture layer (e.g. KPHL StarSim's
# whole-airport Groundtextures asphalt.pol ring, 3.7 M m²/87 holes)
# have NO discrete row-110 strip polygon for the whole-polygon
# absorber and NO row-100 declared width for the spec pass — the
# strip along the runway edges falls into residue and emits as apron
# pieces hugging the runway.  This pass measures the pavement itself:
# walk perpendicular from each runway edge through the final source
# union per station; a consistent (high-coverage) strip of
# shoulder-range width on a side is a shoulder → widen the rect over
# it BEFORE the runway subtraction, so the strip becomes runway.
# Scoped to the DSF gap: a side only fires when its strip is mostly
# NOT covered by apt.dat row-110 pavement — row-110-carried shoulders
# stay with the established passes (HECA whole-polygon absorption;
# SPJC's envelope shoulders deliberately live in the junction cut,
# see the INTERSECTION_PROX_M budget in pipeline.py).
# Gate is defined with the other env-overridable flags below (after
# the ``import os as _os``): ``RUNWAY_SHOULDER_EXTENT``.
# Station spacing along the centerline for the perpendicular walk.
RUNWAY_SHOULDER_EXTENT_STATION_M = 25.0
# Outward walk resolution.
RUNWAY_SHOULDER_EXTENT_STEP_M = 1.0
# Shoulder width admitted per side.  Upper bound per FAA AC
# 150/5300-13B / EASA CS-ADR-DSN.B.080: runway + shoulders ≤ 75 m at
# code letter F (60 m runway → 7.5 m/side); 15 m/side is a generous
# envelope over every code.  Anything wider adjoining the runway is
# taxiway/apron slab, never absorbed.  Lower bound filters the ~2 m
# pavement-union simplify tolerance.
RUNWAY_SHOULDER_EXTENT_MIN_M = 2.0
RUNWAY_SHOULDER_EXTENT_MAX_M = 15.0
# Fraction of stations on a side that must show pavement immediately
# past the runway edge ("consistent along the runway").
RUNWAY_SHOULDER_EXTENT_MIN_COVERAGE = 0.8
# DSF-attribution gate: fraction of the strip's sample points allowed
# on the apt.dat-only union before the side is considered row-110-
# carried (established passes own it) and skipped.
RUNWAY_SHOULDER_EXTENT_MAX_APT_FRAC = 0.5


# ── Aerodrome longitudinal grade standards (single source of truth) ──
# Every grade / vertical-curve rule VALUE lives here so the whole tuning
# surface is auditable in one place; other modules import these rather
# than redefining literals.  See docs/STANDARDS.md for the citations.
# Values are rise/run (decimal: 0.015 = 1.5%).
#
# These stay separate named constants even where the value currently
# coincides (taxiway, apron and runway are all 1.5% today) because they
# trace to different standards and may diverge — e.g. EASA could tighten
# the runway cap without touching taxiways.
TAXI_MAX_GRADE = 0.015          # FAA AC 150/5300-13 taxiway-family
# ICAO Annex 14 Vol I §3.9.8 makes the taxiway longitudinal-grade cap
# SIZE-DEPENDENT: code letters C–F (wide, ≥15 m) cap at 1.5 %, but code
# letters A/B (narrow, <15 m) may grade up to 3 %.  Stock auto_patch held
# every taxiway to 1.5 %, over-flattening small taxiways and spending grade
# budget (corridor flex / apron ramps) to keep them gentler than the spec
# requires.  See ``taxi_grade_cap_for_letter`` + the ``TAXI_GRADE_BY_WIDTH``
# gate below.
TAXI_MAX_GRADE_NARROW = 0.030   # ICAO Annex 14 code A/B taxiway-family
# TRANSVERSE (cross) grade cap — the cT in the anisotropic within-shape allowance
# cL·Δs∥ + cT·Δs⊥ (see ``taxi_transverse_cap_for_letter`` +
# docs/anisotropic_edge_handling_plan.md).  ICAO Annex 14 Vol I §3.9.11 caps the
# taxiway TRANSVERSE slope at 2 % for code A/B and 1.5 % for C–F — so for C–F it
# coincides with the longitudinal cap (isotropic) and only A/B is genuinely
# anisotropic (cT 2 % < cL 3 %).
TAXI_MAX_TRANSVERSE_NARROW = 0.020   # ICAO Annex 14 §3.9.11 code A/B transverse

# ── SPINE CROWN (user ruling 2026-07-07) ─────────────────────────────
# Everything with a spine — runways, taxiways, service roads — crowns
# for drainage: the spine stays at the solved surface level and the
# EDGES drop by ``rate × lateral distance`` (capped at the shape's
# half-width, tapered to zero at welds to non-crowned shapes and at
# spine ends).  The spine itself is emitted as an OPEN way with
# per-node ``alt_abs`` — ``include_patches`` inserts open patch ways as
# constrained DUMMY breakline edges, so the mesh renders the ridge with
# no polygon splitting.  Values are the GENTLEST-LEGAL crown from
# docs/STANDARDS.md ("Transverse grades", researched 2026-07-07):
#   runway   1.0 %  (FAA AC 150/5300-13B Table 3-6 min, all AACs;
#                    center crown standard per ¶3.16.2)
#   taxiway  1.0 %  (FAA ¶4.14.2(1) min; center crown "ideal")
#   service  1.5 %  (AASHTO Green Book Exh. 4-4 normal crown, low end)
# Gate: O4_SPINE_CROWN=0 disables (emission returns to flat sections).
ENABLE_SPINE_CROWN = _os_early.environ.get("O4_SPINE_CROWN", "1") == "1"
# Per-FAMILY crown scoping (user 2026-07-07, part 30c — in-sim crown eval).
# ENABLE_SPINE_CROWN is the master gate; these three select WHICH spine
# families contribute to the crown drop field.  Default = RUNWAYS ONLY for
# the current in-sim evaluation iteration: the taxi/service crown code is
# kept intact (evaluation scoping, not removal) but its drop contributions
# and its crown_spine breaklines are gated OFF by default.  Env overrides:
# O4_CROWN_TAXI=1 / O4_CROWN_SERVICE=1 re-enable them; O4_CROWN_RUNWAYS=0
# would crown taxi/service only.
CROWN_RUNWAYS = _os_early.environ.get("O4_CROWN_RUNWAYS", "1") == "1"
CROWN_TAXI = _os_early.environ.get("O4_CROWN_TAXI", "0") == "1"
CROWN_SERVICE = _os_early.environ.get("O4_CROWN_SERVICE", "0") == "1"
RUNWAY_CROWN_TRANSVERSE = 0.010
TAXI_CROWN_TRANSVERSE = 0.010
SERVICE_ROAD_CROWN_TRANSVERSE = 0.015

# ── TILE-SEAM CROWN RAMP (owner ruling 2026-07-24) ───────────────────
#   "We need to deal with the crown spine when a seam crosses a runway.
#    Because we have to be at DEM we need to be sure the crown spine
#    connects all the way to the shape edge after the seam cut, and that
#    the spine ramps smoothly down to 0 crown at the seam at less than 1%
#    grade."
#
# Since commit 99f39a6 a tile seam is an ANCHOR in the runway profile
# solve: the tile line and BOTH cut-back lines are sampled and anchored at
# the DEM.  The runway therefore MEETS the terrain at its cut-back edge —
# which is exactly why the CROWN must be zero there.  A crowned edge at
# the cut-back sits ``crown_drop`` BELOW the DEM the 10 m tile-cut gap
# renders at, i.e. the pavement edge drops into a gutter across the seam
# (measured at SPLP before this ruling: 0.20-0.23 m at the two mid-width
# cut-edge nodes on BOTH tiles, with no axial taper at all).
#
# THE RAMP.  A runway node's crown is capped at
# ``RUNWAY_CROWN_SEAM_TAPER x (distance to the nearest tile-CUT edge)``,
# where the distance is measured perpendicular to the integer lat/lon line
# and offset by ``TILE_CUT_HALF_WIDTH_M``.  So the cap is exactly 0 ON a
# cut-back line, rises linearly inboard, and releases (min()) at the
# runway's uniform per-ref drop.  Because it is a function of the node's
# own lat/lon against the graticule — never of "my tile's side of the
# cut" — both tile builds compute the identical value at any shared seam
# position without seeing each other.
#
# THE RATE.  The owner's bound is "less than 1%", i.e. strictly under the
# 0.010 the pre-ruling taper reused from ``TAXI_CROWN_TRANSVERSE`` (which
# is a TRANSVERSE crown rate and has no business setting a longitudinal
# shed rate).  0.5% is half of that — real headroom, not a hairline pass:
#   * the largest crown this code can emit is ``RUNWAY_CROWN_TRANSVERSE x
#     _RUNWAY_HALFW_CAP_M`` = 0.010 x 30 m = 0.30 m, which at 0.5% sheds
#     over 60 m — twice the >30 m the ruling requires;
#   * 0.5% is below BOTH runway grades the standards already permit at a
#     seam: the FAA AC 150/5300-13B Table 3-6 minimum transverse crown
#     (1.0%) and the ``RUNWAY_END_GRADE`` end-zone longitudinal limit
#     (0.8%) — so the ramp can never be the steepest thing in either the
#     cross-section or the profile wherever the seam happens to fall;
#   * it leaves a factor of 3 under ``RUNWAY_MAX_GRADE`` (1.5%), so the
#     ramp alone can never carry a rail pair to the runway longitudinal
#     cap, and the crown-offset validator (``grade_law.crown_pair_offset``
#     re-centres each pair by ``c_b - c_a``) keeps a comfortable band
#     around the FLAT surface instead of the exactly-at-budget band a
#     1.5% shed would leave.
# The ramp is a hard CEILING applied last, so it dominates every other
# crown term (uniform drop, crossing dome, Lipschitz frontier shed) near a
# seam and reaches 0 at the cut-back edge regardless of them.
RUNWAY_CROWN_SEAM_TAPER = 0.005
# Gate: O4_CROWN_SEAM_RAMP=0 restores the pre-ruling behaviour (the crown
# tapered at TAXI_CROWN_TRANSVERSE toward the nearest seam-bucket VERTEX,
# and the spine breakline stopping ``_SPINE_EDGE_CLEAR_M`` short of the
# cut-back edge).  Airports with no tile-cut seam vertices at all are a
# strict no-op either way.
CROWN_SEAM_RAMP = _os_early.environ.get("O4_CROWN_SEAM_RAMP", "1") == "1"
# Gate: O4_CROWN_SPINE_SEAM_WELD=0 restores the pre-ruling emission of the
# re-extended spine TERMINUS (diagnosis 2026-07-25, SPLP -13/-77 and
# -13/-78).  The extension snaps the terminus to axis ∩ cut-back edge = the
# geometric MIDPOINT of that ring edge, while ``densify_long_edges`` splits
# the edge into ``ceil(L/60)`` EQUAL parts — so the terminus coincides with
# a ring vertex iff that count is EVEN.  Both parities were broken:
#   * ODD (SPLP: L = 148.09 m → 3 parts) — the terminus sits mid-edge as an
#     UNWELDED T-VERTEX: same lon bits as the ring edge it lies on, but its
#     own node, and its own (stale) profile value — measured forks of
#     -0.015 m (55.60 spine vs 55.615 ring lerp) and -0.085 m (55.12 vs
#     55.205).  No weld can catch it: crown spines are not ``layout.shapes``
#     (they live on ``layout.crown_spines`` as (latlon, alts) tuples), so
#     ``enforce_conformance`` never sees them.
#   * EVEN — ``to_osm`` minted the spine's node ids unconditionally, with no
#     coordinate lookup, so the terminus emitted as a LITERAL coincident
#     DUPLICATE node (the Triangle4XP degenerate class the
#     ``gap_interior_rings`` first-node reuse already guards against).
# ON: the terminus is inserted into the host ring as a T-vertex valued by
# the ring edge's own lerp (the ring is the value authority — the crown has
# ramped to ZERO at the cut edge by design, so the spine's profile value
# there is the stale party), and ``to_osm`` REUSES the existing node at any
# spine coordinate instead of minting a second one.  OFF: byte-identical
# pre-ruling behaviour.  Strictly narrower than O4_CROWN_SEAM_RAMP, which
# reverts the whole spine-extension feature.
CROWN_SPINE_SEAM_WELD = (
    _os_early.environ.get("O4_CROWN_SPINE_SEAM_WELD", "1") == "1")
# Transverse LAW cap for service roads (AASHTO normal crown high end,
# 2 %; up to 2.5 % only in intense-rainfall areas).  Used as the cT in
# the anisotropic allowance so a service road's cross-section cannot
# legally tilt at its 5 % LONGITUDINAL cap (25 cm across a 5 m road —
# the user-visible ridge/valley budget this replaces).
SERVICE_ROAD_MAX_TRANSVERSE = 0.020
# Aprons + building pads grade at 1% (user 2026-06-18: "both builds and aprons
# should be 1%") — flat is preferred 99% of the time, the cap is the fallback.
# JUNCTIONS stay at the TAXI rate (1.5%): they are part of the moving network
# where 1.5% taxiways flow through, not parking surface (decoupled below).
APRON_MAX_GRADE = 0.01          # apron + building pad, all directions
# RUNWAY FLEX displacement budget: DELETED (owner ruling 2026-08-05,
# RULINGS.md "Runway flex: the LAW is the only bound").  The 4.0 m cap was
# a prototype-era safety net of unclear origin; anything within the law is
# legal by definition, so the arbitrary cumulative bound is gone.  The
# lawful bounds are what they always were: CIFP pins (absolute, v1), the
# runway grade caps per segment incl. end zones (the priced slack, via
# ``flex_slack_at``), and ``apply_runway_flex``'s verify-and-relax check.
# Minimization stays the OBJECTIVE through the flex's minimum-move demand
# design (envelope-origin ÷2 split, drain-what-is-demanded), never through
# a cap.
# USER RULING 2026-07-06: pavement within this distance of a taxi
# centerline or a runway is NOT apron (it is maneuvering surface —
# junction law); only the portion of a shape farther than this may carry
# the apron/stand law.  Enforced by the apron route-proximity CUT in
# pipeline.py (shapes are split at this contour) — "no apron should ever
# touch a runway" follows as a corollary.
APRON_ROUTE_PROXIMITY_M = 50.0
# THROUGH-ROUTE LENGTH BACKSTOP (owner ruling 2026-07-26, KCLT shape
# 186).  The route-proximity cut counts only THROUGH taxi routes (each
# end joins another centerline or the runway — the 2026-07-06 KCLT
# gate-lead-in regression fix).  But a real movement-network taxiway can
# dead-end INSIDE apron pavement at both tips (KCLT taxiway U: a 956 m
# route joining two apron lobes through a 36-56 m neck) — excluded, the
# neck stayed apron, the neck's cross-corridor grade edges were spine-
# SKIPPED, and the two lobes floated 4.7 m apart inside one "apron".  A
# dead-end route at least this long is a through route for the cut: gate
# lead-ins are tens of metres, an inter-apron connector is hundreds.
APRON_ROUTE_THROUGH_MIN_LEN_M = 150.0
# The building-frontage rule (user 2026-07-02/03, buildings-heaviest):
# ANY within-shape pair touching a building pad is capped here no matter
# which face role hosts it (grade_law.classify_pair binds it last).
BUILDING_FRONTAGE_MAX_GRADE = APRON_MAX_GRADE
# APRON↔TAXI GRADE BLEND (user 2026-06-25) — defined below, where ``import os as
# _os`` is in scope: APRON_TAXI_BLEND / APRON_TAXI_TRANSITION_M.
# (2026-06-13) APRON BACK-EDGE RAMPS — docs/apron_back_edge_ramps.md.  The
# back strip of an apron (building frontage + gaps BETWEEN buildings, farthest
# from taxi routes) may grade up to this steeper cap so building pads can stay
# flat on sloping terrain: the apron TWISTS — tight 1% taxi-facing front, a
# steeper back that tracks each pad's flat level, ramps between buildings.  4%
# matches groundside / tunnel ramps (drivable, not smooth-for-taxiing).  Only
# back EDGES (both endpoints in the back band) carry it; front-to-back chords
# keep APRON_MAX_GRADE so the transition stays gradual.
APRON_BACK_EDGE_GRADE = 0.040
# Terminal pads.  0.0 = perfectly FLAT (the default — a terminal building sits on
# one floor altitude); the solver derives its flatness from this cap (cap 0 → the
# flat / rigid-pad code path).  Raise it (e.g. to APRON_MAX_GRADE) to let terminals
# GRADE like aprons — they then follow terrain within the cap through the same
# visibility-graph path as every other surface, no special case.
# Terminal pads are rigid FLAT by default in the SOLVER (a building sits on one
# floor); this value is the MAXIMUM grade a terminal MAY take when it cannot stay
# flat — a pad squeezed between a low and a high runway must SLOPE to stay in grade
# to both (user 2026-06-09: flatness yields to grade).  It is also the cap the
# grade VALIDATOR (tools/check_grade.py, via ROLE_GRADE_LIMITS) holds terminals to,
# so the test always checks whatever the config says for each role.
TERMINAL_MAX_GRADE = APRON_MAX_GRADE
# Let EVERY terminal pad slope (up to TERMINAL_MAX_GRADE) through the same
# visibility-graph path as aprons, instead of the rigid-flat default with
# squeezed-pad exceptions.  The s73-p2 evaluation state had this True so the
# route-justified runway profiles' chain tension could drain into terminals;
# the in-sim verdict (user 2026-06-10, s76) is that sloping pads leave
# BUILDINGS FLOATING (HECA terminal1 spanned 100.2-105.3) — pads must stay
# flat and the connective aprons/taxiways carry the grade.  False = the
# rigid-flat default; squeezed pads still slope via the seed marking
# (_sloped_terminal_nodes), e.g. HECA 6/7/10 straddling two runway levels.
TERMINAL_PADS_SLOPE = False
# Taxi-corridor profile pass (user 2026-06-10): a chain of taxi rects that
# CONTINUES through junctions (same ref, or the best axis-aligned
# continuation - HECA's T through junction -10292, T4 into U) is re-profiled
# as ONE smooth 1-D line, exactly like a runway centerline: grade-capped,
# grade-CHANGE-capped, anchored at hard nodes / runway contacts / corridor
# termini, DEM lowest priority.  Without it the solver settles each shape
# DEM-near and a corridor legally V-notches at a junction (T read 111.7 ->
# 104.5 -> 105.0 -> 103.5 - flat-to-reversed through the junction where one
# steady ~1 % ramp exists).  The corridor's profile then anchors the final
# within-shape enforcement (neighbouring pavement conforms to it - taxi
# routes outrank aprons per the user's priority model).
# ⛔ DEFAULT OFF (s73-close): the pass delivers the corridor continuity
# (T monotone through junction -10292, T4 chained into U) but junctions
# crossed by TWO corridors need a TILTED-PLANE crossing model (both axes
# slope, the user's "roll and yaw near equal") and the corridor seeds
# need route-floor awareness (T's flat seed ignored the 05C-route demand
# entering via T4) — without those, adjacent band writes leave up to 64 %
# internal junction cliffs.  Those two pieces ARE the route-field model
# (STATUS #3).  s73-p5 BUILT route-band threading + the junction TWIST
# blend (+ disagreement guard, stub/wide-only cross-ref merges): the
# named corridors land (T monotone through -10292, T4+U ~2 % steady,
# #291 internal 64%→25%).  s73-p7 BUILT the JOINT corridor-network
# solve: chains coupled at shared junctions as one system (crossing
# equality stations, terminus-projection + mouth geodesic cap ties,
# damped consensus + feasibility-guarded freeze, anchor
# self-consistency, junction hard bands on true in-polygon geodesics,
# enforce band-exemption for corridor junctions) — CYXY gate-on 19→0
# green, HECA #217 → 0, #291 → 13.6 %.  ON for in-sim evaluation
# (user 2026-06-10).  Known gate-on residual: HECA's T4-wall route
# tension (freeze-skipped ties, `O4_CORRIDOR_DEBUG=1` prints them) —
# the runway-flex arbitration, not a corridor bug.  False restores the
# pre-corridor surfaces byte-identically.
TAXI_CORRIDOR_PROFILE = True
# Taxiway vertical-curve rate (rise/run change per metre) — the taxi
# sibling of RUNWAY_MAX_GRADE_CHANGE_PER_M (driver.py re-exports it as
# MAX_TAXIWAY_GRADE_CHANGE_PER_M).  1/3000 ⇒ a full 1 % grade change
# needs ≥ 30 m of run (FAA AC 150/5300-13 taxiway vertical-curve
# guidance).  ENFORCED as the spine-profile FAIRING law (user
# 2026-07-04, task 3): the spine solve bounds every grade CHANGE along
# a route chain by it (``_fair_spine_chains``), and
# ``tools/check_grade.py`` validates the same rate on the emitted
# profile — the grade law alone lets the solve track DEM noise in
# legal ±cap wiggles (the residual-waviness class).
# NOT TUNABLE, and never from the environment (docs/RULINGS.md
# 2026-08-05, build-complete-then-debug: "NO GATES.  Every believed-in
# law becomes standing law; O4_ law gates and their env overrides are
# DELETED as their territory is touched").  This is a LAW value — the
# run required per unit grade change — so it is a plain constant here
# and nowhere else; ``O4_TAXIWAY_CURVE_RUN_M`` is GONE.  3000 m of run
# per unit grade change = 30 m per 1 %, the FAA AC 150/5300-13 §4.14.1
# taxiway vertical-curve rate cited above.
TAXIWAY_CURVE_RUN_M = 3000.0
TAXIWAY_MAX_GRADE_CHANGE_PER_M = 1.0 / TAXIWAY_CURVE_RUN_M
# THROUGH-WELD FAIRING (owner defect 2026-07-27, HECA taxiway dip at
# 30.11221,31.41089).  ``_fair_spine_chains`` breaks its chains at every
# degree-≠2 spine node, so the vertical-curve law was blind exactly at
# junction WELDS — a through-taxiway crossing a descending spine
# inherited the weld value and carved a solver-manufactured 10 m V
# (9.4 m under its own 1019 m chord) that no law measured: the DEM
# along the corridor is strictly monotone.  With this ON, chains whose
# terminal segments meet at a weld within
# ``SPINE_FAIR_WELD_MAX_DEVIATION_DEG`` of straight-on are SPLICED and
# the K-factor fairs across the weld like any interior vertex (band
# clamps and anchors still hold).  Branches that genuinely turn keep
# their own chains — the deviation bound is what keeps a 90° tee from
# fairing around the corner.
SPINE_FAIR_THROUGH_WELDS = (
    _os_early.environ.get("O4_SPINE_FAIR_THROUGH_WELDS", "1") == "1")
SPINE_FAIR_WELD_MAX_DEVIATION_DEG = float(
    _os_early.environ.get("O4_SPINE_FAIR_WELD_MAX_DEVIATION_DEG", "30.0"))
# CHORD-SAG CAP (same HECA dip): the K-factor bounds only the RATE of
# grade change — a 10 m bowl under a 1 km corridor is legal curvature
# at 1/3000 — so through-weld splicing irons the kink but not the
# DEPTH.  With this > 0, every spliced/plain chain's interior free
# nodes are floored at (chord between the chain-end values − this many
# metres) before the POCS sweeps, clamped into each node's reach band
# as always.  DEFAULT 0 (OFF): the interaction with the final grade
# projection is unmeasured at airport scale — enable via
# ``O4_SPINE_CHORD_MAX_SAG_M`` after the HECA A/B, not before.
SPINE_CHORD_MAX_SAG_M = float(
    _os_early.environ.get("O4_SPINE_CHORD_MAX_SAG_M", "0"))
# ── TAUT-STRING SPINE PROFILE (owner ruling 2026-07-28,
# docs/specs/taut-string-spine-profile-spec.md) ──────────────────
# The taut string REPLACES the min-curvature harmonic as the taxi-spine
# LONGITUDINAL objective: per corridor the profile is the shortest path
# in (station, elevation) through the feasible reach tube
# [floor(s), ceiling(s)], pinned at genuinely-pinned nodes.  The
# harmonic minimises curvature and has NO altitude preference, so on a
# real-relief airport it interpolates a corridor toward the network-wide
# descent and parks it metres under its own lawful ceiling (HECA
# corridor: 6.3 m below the ceiling, 5.5 m below DEM — spec §1); the
# string is symmetric (it never rises more than needed either) and every
# bend has a witnessed wall contact.  The harmonic stays as the junction
# seed and the fallback for unstrung nodes; the K-factor fairing becomes
# what it was meant to be — rounding at the string's few bends.  OFF
# restores the harmonic path BYTE-IDENTICALLY (every new code path is
# behind this gate).
SPINE_TAUT_STRING = (
    _os_early.environ.get("O4_SPINE_TAUT_STRING", "1") == "1")
# STRING-AS-LAW interval rod ε (spec §10, owner ruling 2026-07-28 late
# session — supersedes the §7 hold mechanisms): the faired phase-A
# string is registered as SIGNED INTERVAL EDGES ``z_i − z_j ∈
# [Δstring − ε, Δstring + ε]`` per consecutive spine pair, so every
# projection maintains the string's SHAPE while the corridor stays free
# to TRANSLATE vertically (a rod that cannot sag).  ε is the per-edge
# slack: quantization-scale, so accumulated shape drift over a 30-edge
# corridor stays ≤ ~0.6 m.  Inert when SPINE_TAUT_STRING is off (no
# string ⇒ no rod edges).
SPINE_ROD_EPSILON_M = float(
    _os_early.environ.get("O4_SPINE_ROD_EPSILON_M", "0.02"))
# ── S1 TAUT-CHORD CONSTRUCTOR — Stage 0 follow-through threshold
# (docs/specs/s1-taut-chord-constructor-spec.md §2) ───────────────
# Maximal-string assembly walks THROUGH a junction onto the adjoining
# corridor piece whose heading deviates least, while that deviation is
# within this many degrees.  The measured defect it exists for: HECA's
# 3,980 m parallel-taxiway chord is cut by ``_build_spine_corridors``
# into 62 pieces with ZERO hard anchors, and the 59 interior piece
# ENDPOINTS carry inherited draped values — 8 % of the chord's nodes
# carrying 100 % of the movable sag (S1 spec §1a).  Assembling the
# pieces back into one maximal string DISSOLVES those pegs into
# ordinary stations, so "the longest possible straight chord between
# its anchors" (model spec §4.3.1) is attempted at all.
# Initial value 15° is MEASURED, NOT SACRED — reviewed at S1-CP2
# against the assembled inventory (S1 spec §2, §11).  Compare
# ``SPINE_FAIR_WELD_MAX_DEVIATION_DEG`` (30°) above, which governs the
# DIFFERENT and much more fragile per-weld splice inside
# ``_build_spine_corridors``; the two are deliberately independent.
TAUT_STRING_FOLLOW_THROUGH_DEG = float(
    _os_early.environ.get("O4_TAUT_STRING_FOLLOW_THROUGH_DEG", "15.0"))
# Level-2 heading WINDOW (metres).  The heading compared at a junction is
# the WHOLE-FRAGMENT bearing, capped at this length — deliberately
# neither of the two things measured to fail: not the piece-scale
# TERMINAL-SEGMENT heading (jitter: chord-piece terminal segments peel
# perpendicular onto crossers and fillets, median best deviation 36° per
# junction), and not an UNBOUNDED centerline bearing (a long curving
# centerline's overall bearing misrepresents its own end).  37 m is the
# MEASURED median along-extent of HECA's chord-1 authoring fragments, so
# a typical fragment contributes its whole bearing and only the long
# ones are capped.
# §3 class (ii-b) TRUNK END DATUMS (owner-confirmed 2026-07-31).  A
# trunk end adopts the live value of the canonically-adjacent junction-
# complex fabric ONLY IF a clause-1 anchor lies within this many metres
# THROUGH THE SPINE GRAPH.  The gate is what keeps the harmonic-
# contamination door shut: only anchor-governed fabric may hand values
# in.  No anchor in radius ⇒ the end stays FREE and is COUNTED — do not
# widen this to catch more ends; short coverage is a FINDING.
# 250 m is measured cover for the ~107 m nearest-anchor distance at
# chord 1; measured-not-sacred, reviewed at S1-CP2.
# ── TURN: the ONE criterion, both uses (Fable ruling 2026-07-31) ──
# The owner's object is the straight RUN.  A string is cut at a turn,
# and it merges across a junction IFF that junction is NOT a turn — one
# test, not two.  6.0° is calibrated on the owner's 36 clean strings
# (max interior bend 5.0°) and seated in the MEASURED EMPTY interval
# (5.0°, 7.54°), not fitted to a disputed sample.  The 4 outlier strings
# (119.05/90.92/67.39/7.54°) are referred to the owner; do NOT fit here.
# ── RUN MARGIN (owner rule, 2026-07-31) ──────────────────────────
# "each string only has two nodes, one at either end of the longest
# straight run that follows the spine within a small margin."
# 20.0 m is DERIVED from the spine-to-string calibration on the owner's
# own map (clean set p90 11-18 m, max 13-21 m; chord-1 max 18.43 m).
# ★ CORRECTION CHAIN, kept visible (register 21 — "a margin is only as
# valid as its population"): the map's INTERNAL straightness is <=0.06 m,
# a DIFFERENT quantity ~250x tighter, and quoting it here would set a
# tolerance the spine cannot satisfy.  The population that matters is
# spine-node-to-owner-string, never map-node-to-its-own-chord, never
# emitted polygon nodes (those measure pavement half-width).
# Minimum length for STRING DUTY (owner 2026-07-31: "strings under 100m
# are probably not very useful").  Owner-stated, not fitted.  Shorter
# walked segments stay in the inventory as MEASUREMENT — selection is a
# layer above construction, never a suppression at construction time.
TAUT_STRING_MIN_STRING_M = float(
    _os_early.environ.get("O4_TAUT_STRING_MIN_STRING_M", "100.0"))
# ── SPINE TOLERANCE: the owner's margin, ONE constant with TWO jobs ──
# OWNER-SUPPLIED 2026-07-31, verbatim: "+/- 8m is acceptable, and the
# union is fine."  ONLY THE OWNER MOVES THIS — it is not calibrated,
# re-derived, or tuned by us in either direction.
#   job 1 — the SIMPLIFICATION band: how far the spine may wander from
#           the idealized straight line and still be "followed" by it
#           (the owner's strings ARE the route network without the
#           curves and intermediate nodes).
#   job 2 — the string-vs-spine VALIDATION bound: an emitted string
#           lies within this of the spine it was walked from.
# ★ CORRECTION CHAIN, kept visible (register 21 — "a margin is only as
# valid as its population"): 20.0 -> 5.0 -> 8.0, each source recorded.
# The 20.0 below was OURS, calibrated on a spine-to-string population
# that contained the very spine holes a sibling track was investigating
# — the fifth strike, and the shipped-constant edition.  5.0 and then
# 8.0 are the owner's own numbers; ``TAUT_STRING_RUN_MARGIN_M`` is
# SUPERSEDED for the walk and retires with ``assemble_runs`` (a later
# MEASURED step, never a silent deletion).  ``SPINE_PERP_TOL_M`` (1.0)
# sits consistently inside this bound.
# ★ ``walk_spine_runs``' ``bound_m`` stays REQUIRED-EXPLICIT: production
# call sites pass THIS constant, and the pure constructor never reads
# config (the ratified API rule — the mechanism must stay expressible
# and a necessity test must be able to vary it).
TAUT_STRING_SPINE_TOLERANCE_M = float(
    _os_early.environ.get("O4_TAUT_STRING_SPINE_TOLERANCE_M", "8.0"))
# ── RUNWAY CLIP remainder floor (OWNER-SUPPLIED, 2026-07-31) ──────
# His words, verbatim, reason included:
#   "Use the runway outline to clip any strings, discarding anything
#    inside the runway, and if the remainder is less than 50m just drop
#    it, the taxiway's grade will be smooth enough without it"
# ★ OWNER-SUPPLIED: only he moves it.  It is NEVER recalibrated by us in
# either direction, and it is not fitted to any measurement — the reason
# is his (a sub-50 m remainder buys no smoothing), not a tuned effect.
# It also SUBSUMES the along-vs-across discriminator: a string running
# ALONG a runway is mostly interior, so its remainders fall under this
# floor and it drops; a CROSSING is mostly exterior, so its remainders
# survive.  One rule, both classes, no angle test — do not reintroduce
# one (the measured 0-29 deg vs 74-90 deg separation is recorded
# MEASUREMENT history, never construction).
TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M = float(
    _os_early.environ.get(
        "O4_TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M", "50.0"))
TAUT_STRING_RUN_MARGIN_M = float(
    _os_early.environ.get("O4_TAUT_STRING_RUN_MARGIN_M", "20.0"))
# Authored-direction alignment for RUN membership.  ROUTE filter — it
# tests the authored route's own direction against the run chord.  It is
# expressly NOT the retired pairwise join gate (bend between consecutive
# fragments), which is dead and must not be reintroduced.
TAUT_STRING_ROUTE_ALIGN_DEG = float(
    _os_early.environ.get("O4_TAUT_STRING_ROUTE_ALIGN_DEG", "15.0"))
TAUT_STRING_TURN_DEG = float(
    _os_early.environ.get("O4_TAUT_STRING_TURN_DEG", "6.0"))
# MEMBERSHIP near-miss recognition (metres).  Chaining exists only to
# heal the DATA's fragmentation — 36 authored fragments tile the owner's
# single chord-1 string — so membership is collinearity-first:
# collinear within TAUT_STRING_TURN_DEG **and** along-contiguous within
# this tolerance.  Endpoint identity is now ONE EVIDENCE SOURCE, not the
# gate (a 0.86 m source-data near-miss stalled chord 1 at along 1652).
# ★ THE THREE-WAY DISTINCTION IS NORMATIVE — do not collapse it:
#   identity   = the canonical registry.  UNTOUCHED.  Never widen the
#                interning radius (β measured 0: the registry is CLEAN,
#                and holding two nodes 0.86 m apart distinct is RIGHT).
#   membership = may recognize near-misses.  THIS constant.  Mints no
#                identity, exactly like BUILDING_FRONTAGE_NEAR_MISS_M.
#   bridging   = still FORBIDDEN.
TAUT_STRING_MEMBER_NEAR_MISS_M = float(
    _os_early.environ.get("O4_TAUT_STRING_MEMBER_NEAR_MISS_M", "1.5"))
TAUT_STRING_END_DATUM_ANCHOR_RADIUS_M = float(
    _os_early.environ.get("O4_TAUT_STRING_END_DATUM_ANCHOR_RADIUS_M", "250.0"))
TAUT_STRING_HEADING_WINDOW_M = float(
    _os_early.environ.get("O4_TAUT_STRING_HEADING_WINDOW_M", "37.0"))
# ── AIRSIDE REACHABILITY excludes service-road paths (owner ruling
# 2026-07-29: "reachability for all airside should never use any
# groundside or service road paths") ─────────────────────────────
# Service-road centerlines still weave into the unified spine graph —
# the solve grades roads along their own spine at the road cap — but
# ``reach_band_unified``'s ceiling/floor value fields skip edges woven
# from a service centerline, so an airside level can never be justified
# through a truck route.  Groundside was never in the graph.  OFF
# restores the pre-ruling band byte-identically.
REACH_NO_SERVICE_SPINES = (
    _os_early.environ.get("O4_REACH_NO_SERVICE_SPINES", "1") == "1")
# GROUND-VEHICLE SERVICE ROAD longitudinal grade — OWNER CONSTANT, approved
# 2026-08-03 (docs/RULINGS.md "Owner constants: lot 5%, service road 8%";
# docs/STANDARDS.md row "Ground-vehicle service road").  History: 4 % →
# 5 % (user 2026-07-04, design judgement) → 0.080 on the cited standard.
# VDOT Road Design Manual Appendix A1, "Geometric Design Standards for
# SERVICE ROADS (GS-9)", table "Relationship of maximum grades to design
# speed": LEVEL terrain 8 % at 10-20 mph and 7 % at 30-40 mph (rolling
# 9-12 %, mountainous 12-18 %).  An airport service road is the level-
# terrain, low-design-speed case, so 8 % is its standard maximum.  No
# aviation authority regulates it (FAA/ICAO/EASA/ACRP verified silent).
# COUPLING (flagged for the owner, docs/RULINGS.md): ``service_junction``
# rides this SAME constant — ``ROLE_GRADE_LIMITS`` below maps both
# ``service_road`` and ``service_junction`` to it, and so do
# ``grade_graph._body_cap``/``_cap_label`` and the check_grade twin.
# Raising it to 8 % therefore raises service JUNCTIONS to 8 % as well; if
# junctions are to be split from the road body that is a second owner
# ruling and a second constant, not an implementer's call.
SERVICE_ROAD_MAX_GRADE = 0.080
# R5c — GRADED-ROAD CHARACTER (service-road law spec, Fable 2026-08-15;
# owner in-sim on R5 at CYXY 60.7087015,-135.0746305).  R5's tracker
# follows the low-passed terrain faithfully — INCLUDING its wiggles —
# where a road is a GRADED SURFACE: piecewise-monotone ramps between
# real terrain features, not terrain-hugging bumps.  After the tracker,
# a grade REVERSAL (rise-fall-rise or fall-rise-fall) whose interior
# amplitude is below this floor is levelled through — a monotone bridge
# between its endpoints, still clamped to tube ∩ peg cone ∩ cap.  Large
# terrain movement is still tracked: this is a reversal AMPLITUDE floor,
# not a smoothing length.  ONE constant (the spec's own wording); it
# constrains nothing else and mints no second law number.
SVC_PROFILE_REVERSAL_MIN_M = 0.4
# Ground-vehicle ``service_road`` rect geometry (session 47).
SERVICE_ROAD_WIDTH_M = 6.0          # corridor width for a service-road rect
MIN_SERVICE_STRIP_LEN_M = 25.0      # min dedicated-strip length to emit a rect
# OSM small-road inputs: which highway= types count as drivable "small
# roads" (graded with car logic, SERVICE_ROAD_MAX_GRADE).  Inside the airport boundary + a
# small outside buffer.  Excludes major roads (motorway/trunk/primary/
# secondary) and non-car ways (footway/path/cycleway/steps/pedestrian).
OSM_SMALL_ROAD_HIGHWAY_TYPES = frozenset((
    "service", "unclassified", "residential", "living_street",
    "track", "road", "tertiary",
))
# ``highway=`` values the AIRPORT-REGION ROAD FEED drops: pedestrian /
# non-motorised ways and the not-yet-a-road placeholders.  The feed
# selects on the highway KEY (the whole point — it must see the service /
# track / residential classes the tile caches never held), so this is
# where "drivable" is enforced.  Same exclusion spirit as the non-car
# omissions from OSM_SMALL_ROAD_HIGHWAY_TYPES above; at HECA it drops 575
# footways + 48 steps + the path/cycleway tail from a 5.3k-way region.
OSM_NON_DRIVABLE_HIGHWAY_TYPES = frozenset((
    "footway", "path", "cycleway", "steps", "pedestrian", "bridleway",
    "corridor", "elevator", "via_ferrata", "platform", "proposed",
    "construction", "raceway", "bus_guideway", "escape", "rest_area",
    "services",
))
# ``railway=`` values that are actual TRACK (the rest of the key is
# platforms, signals, disused alignments and yard furniture, none of
# which is a rail corridor).  Deliberately the same five classes as
# ``bridges.RAIL_TUNNEL_TYPES`` so "what counts as a railway" reads the
# same everywhere in the builder.
OSM_RAIL_TRACK_TYPES = frozenset((
    "rail", "light_rail", "subway", "narrow_gauge", "tram",
))
# OSM small roads are kept ONLY where they hug airfield pavement: within
# SERVICE_ROAD_PAVEMENT_NEAR_M of any apt.dat/DSF pavement.  This drops
# the deep-interior road grid of large airports (HECA's 28 km² boundary
# held ~852 service shapes otherwise) and keeps only the apron-access /
# crossing roads that join the pavement.  apt.dat 1206 truck routes are
# authoritative and kept unconstrained.
SERVICE_ROAD_PAVEMENT_NEAR_M = 25.0    # keep OSM roads within this of aircraft pavement
RUNWAY_MAX_GRADE = 0.015        # FAA AC 150/5300-13B runway longitudinal (ARC C-E)
RUNWAY_END_GRADE = 0.008        # EASA CS-ADR-DSN / ICAO Annex 14, first/last quarter (code 3/4)
RUNWAY_END_FRACTION = 0.25      # extent of each runway end zone (fraction of length)
# TIERED end-zone relaxation (user 2026-07-16, KBNA 13/31 defect G): when
# hard anchors (CIFP thresholds, tile-seam DEM pins) make the 0.8% end-zone
# preference infeasible, the OUTER part of the end zone escalates toward the
# 1.5% law — but the immediate THRESHOLD VICINITY stays gentle.  The last
# ``RUNWAY_THRESHOLD_STRICT_M`` before each threshold holds the strict 0.8%
# cap (a 0.8% ramp over 90 m costs ≤0.72 m — absorbed deeper in the end zone
# where the escalated cap applies); it relaxes only when the profile is
# genuinely infeasible even with the outer end zone fully at the 1.5% law
# (then the solver WARNs loudly with the achieved threshold-band cap).
RUNWAY_THRESHOLD_STRICT_M = 90.0
TUNNEL_RAMP_MAX_GRADE = 0.040   # navigable ramp grade for tunnel portals (user 2026-05-08)
# Skip tunnel-portal ramp emission where the tunnel runs under / alongside
# OTHER roads (user 2026-06-12, LMML): in a dense road interchange the
# surface walk traces a tangle of parallel carriageways, slip roads and
# roundabouts, and the ramps overlap.  Rather than model that complexity,
# skip ramp emission for any tunnel that has another road CROSSING it or
# running within ``TUNNEL_ADJACENT_ROAD_DIST_M`` of it.  The test excludes
# (a) ``highway=service`` minor roads, (b) other tunnels (a divided
# highway's own clustered carriageway), and (c) shared-node continuations
# (the surface road the ramp is meant to follow) — so an isolated tunnel,
# or one crossed only by service roads / its own carriageway, still emits
# ramps (SPJC's user-approved tunnels are kept; all 6 LMML tunnels skip).
SKIP_TUNNEL_RAMPS_NEAR_ROADS = True
TUNNEL_ADJACENT_ROAD_DIST_M = 15.0
# DEM-CUT PORTALS (user 2026-07-17, EGGW): what a tunnel portal needs
# from the patch DEPENDS ON THE MESH.  With a high-resolution lidar
# elevation inset the digital terrain model is bare-earth: the
# approach ramps to the portal are already carved essentially
# correctly in the DEM, and a bare-earth model also removes the
# taxiway structure ABOVE the tunnel — leaving an open trench through
# the covered bore.  When the DEM near a portal already descends at
# least ``TUNNEL_DEM_CUT_MIN_DROP_M`` below the airport surface, the
# emitter therefore stops synthesising ramps (a 4 %-law linear ramp
# would FIGHT the real, often steeper, lidar cut) and instead emits
# only: the portal face cap at airport grade, a short mouth plate at
# the DEM's own road grade (``TUNNEL_MOUTH_PLATE_LENGTH_M``) so the
# face transition stays crisp, and flat ROOF plates at airport grade
# over the covered bore between the portal face and the airside
# pavement (up to ``TUNNEL_ROOF_PLATE_MAX_LENGTH_M`` per portal) —
# filling the bare-earth trench that the pavement grading does not
# reach.  Coarse-DEM airports (no descent at the portal) keep the
# synthetic-ramp behaviour byte-identically.  ``O4_TUNNEL_DEM_CUT=0``
# disables the mode.
TUNNEL_DEM_CUT_MIN_DROP_M = 3.0
TUNNEL_DEM_CUT_WINDOW_M = 60.0
TUNNEL_MOUTH_PLATE_LENGTH_M = 6.0
TUNNEL_MOUTH_WINDOW_M = 30.0
TUNNEL_ROOF_PLATE_MAX_LENGTH_M = 120.0
# IMPLIED CROSSING TUNNELS (user 2026-07-04): a PUBLIC through-road or a
# railway that crosses taxiway/runway pavement cannot do so at grade —
# assume a tunnel under the pavement even when OSM carries no tunnel
# tag, and emit the standard portal ramps on either side.  The crossing
# way is split at the pavement-edge intersection points into
# approach + (synthetic ``tunnel=yes``) bore + approach pieces, so the
# whole existing tunnel machinery (portal walks, ramps, retaining
# walls, twin-bore clustering, adjacent-road system veto) applies
# unchanged.  Airport service and residential roads are EXCLUDED —
# those legitimately cross taxi routes at grade.  ``O4_IMPLIED_TUNNELS=0``
# restores tag-only tunnel detection.
IMPLIED_CROSSING_TUNNELS = _os_early.environ.get(
    "O4_IMPLIED_TUNNELS", "1") == "1"
# TAG EVIDENCE FOR IMPLIED BORES (owner spec round4-othh-fixes,
# 2026-08-10, R4).  A purely GEOMETRIC crossing is never a tunnel:
# synthesis requires the crossing way — or a way its chain connects to
# within ``IMPLIED_TUNNEL_TAG_EVIDENCE_M`` — to carry ``tunnel=yes``
# (any ``TUNNEL_VALUES`` member) or ``layer`` < 0.  Measured at OTHH on
# 1.0.229: the S1 ramps (25.2531, 51.6209) were engine-FABRICATED under
# untagged tertiary ways with no OSM tunnel on their chain at all.  S4's
# pair — untagged CONTINUATIONS of a mapped bore, sharing its portal
# junction — still qualifies.  ``O4_IMPLIED_TUNNEL_TAG_EVIDENCE=0``
# restores the pre-ruling purely-geometric synthesis.
IMPLIED_TUNNEL_TAG_EVIDENCE = _os_early.environ.get(
    "O4_IMPLIED_TUNNEL_TAG_EVIDENCE", "1") == "1"
IMPLIED_TUNNEL_TAG_EVIDENCE_M = 100.0
# Y-fork throat junction (user 2026-06-12, KPHL RWY 26 north portal:
# road+rail share a bore then fork outside).  When True, the diverging
# end of a Y-split tunnel is modelled like a taxiway sloping-rect +
# junction: a single ``node_altitudes`` "throat" polygon with a V-notch
# bridges the shared bore to the per-arm sloping rects, and a continuous
# retaining wall traces the whole Y (outer fan edges + the inner V
# between the arms).  No pavement is graded between the arms.  When False
# the legacy Y-split (advance each branch clear of its siblings, leaving
# the crotch bare) is byte-identical — only the FORK path is affected;
# parallel-bore clusters (SPJC divided highways) are untouched either way.
TUNNEL_FORK_THROAT = True
# LOW-CONNECTOR OPEN-TRENCH DESIGN CAP (user 2026-07-10, SPJC big
# tunnel): the kinematic bore-merge threshold (2·depth/grade ≈ 457 m —
# "a ramp pair cannot surface and return within the gap") says when the
# road CANNOT surface, not when an OPEN TRENCH is the right built form.
# An open flat low-connector is real-world correct only for narrow
# slots between close parallel pavements (the KDFW double-taxiway
# median, 30-70 m); a wide covered stretch stays COVERED (ground
# bridges over the still-depressed bore, portal mouths at the ends).
# SPJC's ~230 m runway spacing was being dug open into an 8-10 m
# trench.  Gaps above this cap keep the covered/portal form.
TUNNEL_LOW_CONNECTOR_MAX_OPEN_GAP_M = 100.0
# GROUNDSIDE (curbside / parking lot) ramp grade — OWNER CONSTANT, approved
# 2026-08-03 on the primary-source research (docs/RULINGS.md "Owner
# constants: lot 5%, service road 8%"; docs/STANDARDS.md row "Groundside
# pavement").  The old 0.040 was UNCITED (inherited from the tunnel-ramp
# constant, user 2026-05-22).  0.050 is the walking-surface ceiling every
# landside authority converges on:
#   * ADA 2010 Standards §403.3 — running slope of a walking surface shall
#     not be steeper than 1:20 (= 5.0 %);
#   * Iowa SUDAS Design Manual ch. 8 §8B-1 (Parking Lots, Layout and
#     Design) — "Slopes greater than 5% are discouraged";
#   * City of Santa Barbara Parking Design Standards §D.5 — "The slopes of
#     all parking areas shall not exceed 5%, excluding ramps".
# No aviation authority regulates a landside lot grade (FAA AC 150/5300-13B,
# ICAO Annex 14 / Doc 9157, EASA CS-ADR-DSN and ACRP 25 verified SILENT), so
# the value is region-invariant — there is no FAA/ICAO split to apply.
GROUNDSIDE_MAX_GRADE = 0.050
# ── THE CAP GROUNDSIDE **PAVEMENT** GRADES AT (owner 2026-08-12) ─────
# "groundside_pavement's cap moves from GROUNDSIDE_MAX_GRADE 5 % to THE
# ROAD LIMIT (config's ROAD/SERVICE_ROAD cap — one constant, no second
# number)."  A lot carries the same vehicles a service road does, so it
# takes the same number.
#
# THIS IS AN ALIAS, NOT A VALUE: it is ``SERVICE_ROAD_MAX_GRADE``
# itself (asserted by identity in ``tests/test_owner_constants_round``),
# so re-ruling the road limit re-rules the lot with it and no copy can
# drift.  It exists so that every SAME-LAW site — the role table, the
# lot emitter's seat and ring limiter, the post-solve chord (Lipschitz)
# limiter, the lateral strictest-cap min — says WHICH law it obeys
# instead of spelling "the service-road standard" over a car park.
#
# ``GROUNDSIDE_MAX_GRADE`` above keeps its OTHER consumers: they are
# different laws that happened to share the value (the fan-ramp zone
# ``FAN_RAMP_CAP``, the groundside band's off-route pricing, the
# object-pad pull rate, the below-grade transition law).
GROUNDSIDE_PAVEMENT_MAX_GRADE = SERVICE_ROAD_MAX_GRADE
# ── THE GROUNDSIDE BAND's off-route radius (RULINGS 2026-08-06, "ONE
# graph: groundside joins the route graph") ─────────────────────────────
# ``building_feasibility.groundside_reach_band`` answers a groundside
# point from the nearest node the route graph gave a band to, with the
# local off-route leg priced at ``GROUNDSIDE_MAX_GRADE``.  BEYOND THIS
# RADIUS THERE IS NO COUPLING: the ring is the ruling's "truly
# disconnected" geometry — not solved, left at its DEM seed, minting
# nothing — and the SAME answer is what the emitted sidecar carries for
# the census to adjudicate with (lockstep).
#
# It is the groundside sibling of ``RASTER_REACH_BAND_OFFNET_RADIUS_M``
# (30 m, the AIRSIDE band's off-mask radius), and it is larger because
# the surfaces are: an airside query is a metre or two off a paved cell,
# while a lot vertex is legitimately a lot's half-width from the nearest
# graph node.  150 m at the 5 % lot cap is a +-7.5 m interval, which is
# the same order as the lot laws it feeds.
GROUNDSIDE_BAND_OFFNET_RADIUS_M = 150.0
# ── THE FAN-RAMP LAW's cap and law name (owner RULINGS 21f0980) ──────
# "between frontages at the back edge, the fan-ramp zone carries up to
# 5 % continuous grade fanning between building seat levels".  The VALUE
# is the groundside class's, named once here so the solver
# (``grade_graph._body_cap_unbounded``) and the validator
# (``tools/check_grade``) cannot each carry their own copy — the same
# single-source rule every other grade constant in this file follows.
#
# ``FAN_RAMP_LAW`` is the ``o4_grade_law`` way-tag VALUE that carries the
# declaration across the emit boundary, exactly as ``'apron'`` carries
# ``adopts_apron_grade``.  ONE FUNCTION resolves it on both sides
# (:func:`fan_ramp_law_cap`) so a tag rename cannot desync the readers.
FAN_RAMP_CAP = GROUNDSIDE_MAX_GRADE
FAN_RAMP_LAW = "fan_ramp"


def fan_ramp_law_cap(law_value):
    """THE fan-ramp resolver — ``FAN_RAMP_CAP`` for the declared law
    value, ``None`` for anything else.

    Both readers call THIS: the solver through
    ``grade_graph.GradeShape.fan_ramp_zone`` (set from
    ``BuiltShape.fan_ramp_zone`` on the layout side and from this tag on
    the OSM side), the census through ``check_grade._role_grade_limit``.
    A patch predating the law carries no tag, reads ``None``, and is
    judged exactly as before.
    """
    return FAN_RAMP_CAP if law_value == FAN_RAMP_LAW else None


# FAA vertical-curve rule L = K × |Δg|.  K = 305 m for ARC C/D (lighter
# A/B ≈ 76 m, heavy E ≈ 610 m).  ``RUNWAY_MAX_GRADE_CHANGE_PER_M`` is the
# segment-smoother's equivalent: a 1% grade change needs ~305 m of curve,
# i.e. ~1/30000 grade change per metre of pavement.
RUNWAY_VERTICAL_CURVE_K_M = 305.0
RUNWAY_MAX_GRADE_CHANGE_PER_M = 1.0 / 30000.0
# (The 2026-06-06 "0 = flat" band ``RUNWAY_DEM_FOLLOW_BAND_M`` was the
# gate-off arm of the DEM-follow seeding below; it was deleted with the
# gate.  History it must not lose: the ORIGINAL 5.0 m band was UNBOUNDED
# and let mid-runway free-float 4.5 m into a valley at CYXY 14R/32L,
# pulling stub A to 7.4 %.  The band below is bounded by the FAA
# vertical-curve term instead, and ``faa_joint_solve`` still enforces
# every grade/curvature cap regardless.)

# ── DEM-FOLLOW SEEDING (spec docs/specs/runway-flex-completion-spec.md
# fix 3).  STANDING LAW — the ``O4_RUNWAY_DEM_FOLLOW`` gate and its
# band-0 arm were retired in the build-complete-then-debug round. ─────
# The band above being 0 makes every runway seed the STRAIGHT CIFP chord,
# and the flex is then asked to re-derive from taxi feasibility a shape
# the seeder threw away.  Measured on the stress runway (HECA 05R/23L,
# flex-probe 2026-08-04): the profile rides +9.13 m above the ground at
# mid-length while the real ground holds a broad, LAW-FEASIBLE sag.
#
# THE VALUE, from the probe's dip data.  The 40 m-median corridor DEM of
# 05R/23L runs 10.02 m below the CIFP chord at its deepest (s = 2220 m of
# 4130 m; the spec's centreline read of the same dip is 8.64 m).  A band
# below that truncates the real sag — the exact defect this fix exists to
# remove — so the smallest round value that admits the measured sag in
# full is 10.0 m.
#
# WHY THAT IS STILL LAW-BOUNDED, not "free-float 10 m": the band the
# seeder applies is ``min(this, ½·d²/K)`` — the FAA vertical-curve
# deviation a PVI at the nearest anchor can absorb.  That term binds
# everywhere near an anchor (0.17 m at 100 m out, 4.2 m at 500 m) and
# this constant only starts to bind past ~775 m from the nearest CIFP /
# seam / crossing anchor, i.e. only in the deep interior where a real
# sag can live.  ``faa_joint_solve`` (grade cap, end-zone cap,
# K-factor) runs afterwards regardless and is the enforcement.
#
# The 2026-06-06 "0 = flat" ruling and the 5.0 m regression it replaced
# (CYXY 14R/32L free-floating 4.5 m into a valley, stub A at 7.4%) were
# both about an UNBOUNDED band; this one is bounded by the FAA
# vertical-curve term at every station near an anchor.
RUNWAY_DEM_FOLLOW_LAW_BAND_M = 10.0


def runway_dem_follow_band_m() -> float:
    """The DEM-follow band in force for this build (metres).

    ONE value, no arm: the seeder follows the corridor DEM inside the
    law-bounded band.  (Kept as a function rather than a bare constant
    read so ``pavement/runway_segments.py`` keeps its single source of
    truth for the number.)
    """
    return RUNWAY_DEM_FOLLOW_LAW_BAND_M


# ── RUNWAY FLEX: SELF-ANCHOR UNLOCK + CONVERGENCE (same spec, fixes 1
# and 2).  STANDING LAW — the ``O4_FLEX_SELF_UNLOCK`` gate and its
# "flex-minted anchors bound, 3 fixed rounds" arm were retired in the
# build-complete-then-debug round. ────────────────────────────────────
# Fix 1: ``apply_runway_flex`` inserts every applied target as
# ``anchored=True``, and ``flex_slack_at`` bounds against ALL anchored
# samples — so a station the flex touched in round 0 had slack ≡ 0
# (cap·0) in every later round and could never move again.  Measured at
# HECA: 05R/23L's anchored count grows 4 → 9 → 14 and 05C/23C 4 → 48 →
# 54, every new one flex-minted, and rounds 1-2 at the deepest bin read
# slack 0.000 / move 0.000.  A flex-MINTED sample now stays anchored for
# the re-solve (so the FAA gates still smooth around it) but is
# withdrawn from ``flex_slack_at``'s bounding set.  CIFP thresholds,
# physical ends, tile-seam samples and crossing-reconciliation anchors
# are never minted, so they keep bounding.
#
# Fix 2: every HECA demand's binding seed is another flexible runway, so
# the origin split halves every pull; 3 rounds of geometric halving
# leave 25 % of the demand unmet by construction.  Iterate until a round
# drains less than the materiality floor, or the hard cap below.
# ROUND-CAP ARM REFUTED (band-findings fix, 2026-08-15): raising 12 →
# 48 at HECA ran all 48 rounds and drained 84 m more TOTAL demand, but
# the last-round residual (48.51 vs 48.41 m) and all 21 rwy_flexed
# band-instrument findings were UNCHANGED — the same 22 bins re-present
# every round and verify-and-relax refuses them every round (347 m
# discarded).  The cap is not the mechanism; 12 stands.
RUNWAY_FLEX_MAX_ROUNDS = 12
RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M = 0.01


# ── THE FLEX DEAD ZONE (spec ``docs/specs/demfollow-joint-spec.md``).
# STANDING LAW — the ``O4_FLEX_DEMAND_TOL_FINE`` gate and its 0.05 m arm
# were retired in the build-complete-then-debug round. ────────────────
# The envelope demand tolerance decides which deficits the flex is even
# ALLOWED to see.  At 0.05 m it sits five times above the band's own
# materiality floor (0.01 m — CLAUDE.md item 3(a), the floor the final
# band-inversion check adjudicates on), so every demand in [0.01, 0.05)
# is invisible to the machinery that exists to drain exactly that
# tension: the flex declines to move, and the band then calls the same
# deficit a law violation.  Measured at HEAZ under O4_RUNWAY_DEM_FOLLOW:
# a 0.0174 m cross-runway differential (18/36 sinks −0.12 at its join
# anchor, 05/23 −0.14 at its threshold-join) inverts the final band on
# all 47 route nodes of the 292 m taxiway between them — a build abort
# with no lawful demand ever presented.  Aligned with the materiality,
# that deficit enters round 0 and the origin split drains ~9 mm from
# each runway, inside every clamp.
#
# The flip was measured (lead ruling 2026-08-05) and is census-NEUTRAL:
# it MOVES the default surface at HECA (release anchor a1ade8bd →
# 675fc645, deterministic over 3 reps; HEAZ/CYXY/SPJC/SPLP/KCLT all
# byte-identical) by one discrete step — 126 of 32,225 nodes (0.39 %),
# one apron cluster at the 05R/23L end, max |dz| 0.70 m, geometry
# unchanged — with the full law-true census 8865/0/126 class-for-class
# identical on both arms.  The gate protected IDENTITY, never
# lawfulness, so it dies with the rest of them.
RUNWAY_FLEX_DEMAND_TOL_M = 0.01     # aligned with the materiality floor

#: THE IDEMPOTENCE FLOOR of the post-solve projection (cycle-4 ingestion
#: spec, ``docs/specs/cycle4-projection-ingestion-spec.md`` requirement 2;
#: the campaign materiality floor for elevation classes).  A node whose
#: seed still sits within this of the value the one solve published, and
#: whose canonical key the solve already had, counts as UNTOUCHED: the
#: projection holds it instead of re-solving it.  Same 0.01 m the flex
#: demand tolerance and every elevation-class convergence guard use — one
#: floor, stated once.
POST_SOLVE_IDEMPOTENCE_TOL_M = 0.01


def runway_flex_demand_tol_m() -> float:
    """The envelope demand tolerance in force (metres).

    ONE value, aligned with the 0.01 m materiality floor the final
    band-inversion check adjudicates on: every deficit the band would
    call a violation is a deficit the flex is allowed to see."""
    return RUNWAY_FLEX_DEMAND_TOL_M


# ── §2a AMENDMENT: THE APPLY-SIDE PER-SEGMENT CAP (lead adjudication
# 2026-08-04 night, appended to the round's spec) ─────────────────────
# ``apply_runway_flex``'s verify-and-relax loop is the APPLY-side safety
# check, and it tested ``MAX_RUNWAY_GRADE`` only.  The per-segment cap —
# ``runway_segment_grade_cap``, i.e. the FAA 0.8 % END-ZONE cap inside
# the first/last ``RUNWAY_END_FRACTION`` and the tiered threshold band —
# is equally law, so testing only the main cap there was a bug.  (The
# spec's "slack clamp, displacement budget … all stand" froze the
# DEMAND-side clamps; it never froze this check.)
#
# MEASURED, and the reason this is a completion rather than a guess: the
# profile the flex STARTS from has ZERO over-cap segments on every HECA
# runway in every arm — all 17 gate-off end-zone violations, and all of
# the +9 / +15 the fix arms added, are minted by the flex itself.
#
# NO-NEW-REGRESSION FORM: each ref's over-cap segment list is snapshotted
# ONCE, from the profile the first flex call sees, and every later
# candidate solve is compared against that fixed reference by STATION
# (targets insert samples, so segment indices do not correspond).  A
# candidate that creates a new over-cap segment, or worsens an existing
# one by more than the materiality floor below, has its nearest target
# dropped and the solve retried — exactly the machinery the main-cap
# check already used.  An absolute reference, not a per-call one, so 35
# apply calls cannot ratchet the floor into a real violation.  The
# pre-existing gate-off segments are a standing defect recorded for
# their own round, not this round's responsibility.
# UNGATED, as the gate's own docstring said it should become at flip
# time: the amendment is a correctness precondition of both flex fixes,
# and both are standing law now.
RUNWAY_FLEX_ENDZONE_MATERIALITY = 0.0001    # 0.01 percentage points

# Within-shape grade-audit geometry — the SINGLE SOURCE OF TRUTH shared by the
# runtime audit (``elevation._report_within_shape_violations``, the WARN shown
# in the Ortho4XP window) and the validator (``tools/check_grade.py``, what the
# test suite asserts), so the two never diverge:
#   * A within-shape grade constraint exists between two MUTUALLY-VISIBLE
#     vertices — a pair whose straight chord stays inside the polygon (grown by
#     ``GRADE_VISIBILITY_BUFFER_M``).  Visibility is the gate: a chord that
#     cuts across a non-convex notch is a phantom path and excluded.
#   * Under ``ROUTE_FIELD_MODEL`` (below) visibility chords are additionally a
#     LOCAL law only: pairs longer than ``ROUTE_FIELD_LOCAL_WINDOW_M`` are not
#     graded against each other (ring-adjacent pairs — the physical edge —
#     always are); the LONG-RANGE law is the route-band check instead.
#   * ``ELEV_ROUNDING_NOISE_M`` absorbs the EMIT rounding (2-decimal since
#     the V15 quantization fix: +/-0.005 per endpoint) plus the final GS
#     convergence tolerance.  The old 0.15 was sized for 1-decimal emit and
#     on short pairs it dwarfed the cap itself (a 5 m edge could legally
#     step 0.15 m + cap ~ 4.5 % -- user-visible steep edges at 0 reported
#     violations, 2026-07-03).
GRADE_VISIBILITY_BUFFER_M = 1.0
ELEV_ROUNDING_NOISE_M = 0.03
# Coarse-emit sibling of ``ELEV_ROUNDING_NOISE_M`` for SLOPED-QUAD shapes
# (2026-07-17).  A tilted 4-corner way is emitted as ``altitude_high`` /
# ``altitude_low`` quantized to 0.1 m (``bridges.py`` ``_emit_tunnel_portals``
# grade_safety_margin) — 10x coarser than the 0.01-m per-node ``alt_abs`` grid.
# A within-shape pair spanning the high and low corners of such a quad (or a
# per-node shape welded to one) therefore carries up to a full 0.1-m emit step
# on top of the solved field, which the 0.03-m per-node envelope cannot absorb:
# short tunnel_ramp / bridge-portal pairs solved to their 3.5-4 % plan grade
# then read a few hundredths over cap purely from the coarse round (SPJC
# tunnel_ramp #499-502: 4.1-4.2 % vs the 4 % cap).  The SAME 0.1-m envelope is
# reused for JUNCTION-family ring edges (``check_grade._pair_quant_noise_m``):
# junction rings are rebuilt by the conformance / planarization / weld pass
# (T-vertex + unshared-corner inserts, epsilon-wedge welds), which displaces a
# short ring edge by up to a decimetre — the same magnitude — so a short
# junction edge reads over its 1.5 % cap from weld displacement, not a real
# grade defect (SPLP junction #68: 6 cm over 0.85 m).  Sized like the
# runway-end-skirt reader's 0.1-m sloped-quad tolerance
# (``_check_runway_end_skirt_edges``), NOT a per-airport fudge.
SLOPED_QUAD_ROUNDING_NOISE_M = 0.1
# ── Emit-quantization grade margin — RETIRED 2026-08-05 ──────────────────
# ``EMIT_QUANTIZATION_MARGIN_M`` (and its ``O4_QUANT_MARGIN`` env read) are
# DELETED.  The problem was real: ``to_osm`` emits elevations rounded to
# 0.01 m, so a pair solved exactly AT its budget can read over the law in the
# emitted patch.  The FIX was wrong: shrinking every SWEEP budget by one grid
# step is correct PER PAIR but compounds PER PATH — an N-hop route lost
# ``N × margin`` of envelope no law ever took (HEAZ, measured: a 69-hop
# witness route stole 0.63 m and the projection burned 3983 sweeps chasing
# the deficit; the stall adjudication read "593 of 2032 INFEASIBLE" against a
# system whose raw envelope is 0/2032).
# STANDING LAW (docs/RULINGS.md 2026-08-05, build-complete-then-debug): the
# sweeps enforce the RAW law budgets, and the 0.01 m guarantee lives at EMIT
# in :mod:`auto_patch.emit_snap` — a per-pair, law-aware grid snap bounded by
# ONE grid step per node BY CONSTRUCTION, so it cannot compound along a path.

# ── ROUTE-FIELD MODEL (#3, user-approved s73-p3, built s75; see
# docs/route_field_model.md) ─────────────────────────────────────────────
# The long-range within-pavement grade law is the TAXI-ROUTE distance from
# the hard anchors (runway nodes at solved values, seam/threshold pins,
# corridor-held writes): a vertex's feasible band is the intersection over
# anchors a of [E_a ± cap·route_d(a, v)].  Grade
# rules (ICAO Annex 14 §3.9, EASA CS-ADR-DSN.D.265/.280) regulate slope
# along the taxi route; nothing regulates the straight chord between two
# points kilometres apart, and km-scale visibility chords systematically
# UNDER-measure the route (corner cuts, cross-shape chains) — at HECA the
# hard 05C contact reached the taxiway-A apron mouth through ~2.5 km of
# chained chords where the real route is ~3.08 km, an 8.5 m manufactured
# infeasibility (s73-p10g).  Visibility chords survive only as a LOCAL
# smoothness cap (pairs ≤ ROUTE_FIELD_LOCAL_WINDOW_M; ring-adjacent pairs
# always).  The validator (tools/check_grade.py) and the runtime WARN
# change IDENTICALLY with this flag — the definition of a violation
# changes, so the model must never ship solver-only or validator-only.
ROUTE_FIELD_MODEL = True
# Local smoothness window (m): visibility-chord pairs at or under this
# length keep the chord grade law (design start 80, measure 60–100).
ROUTE_FIELD_LOCAL_WINDOW_M = 80.0
# FINAL SURFACE FAIRING (s76, user in-sim feedback): the dense all-pair
# chord web used to act as an implicit smoother — with chords windowed,
# sub-cap DEM noise survives the solve as visible ripples at junctions.
# A final weighted-Laplacian fairing pass irons them: soft uncoupled
# vertices relax toward their grade-graph neighbours, clamped into the
# route bands and a per-node displacement budget (so it smooths ripples
# without re-levelling surfaces), then caps are re-projected.
SURFACE_FAIRING = True
SURFACE_FAIRING_MAX_MOVE_M = 0.5
# APRON CORRIDOR SMOOTHING (s76, user in-sim verdict at CYXY: "the apron is
# much too steep ... use taxi route corridors along the edges or into aprons,
# and ensure apron grade outward from those in maybe a 200 m radius is graded
# at ideally 1 %").  Within this radius of a taxi corridor (apt.dat/OSM
# centerline OR a taxi rect's source axis — discovered taxiways carry no
# apt.dat row), apron vertex pairs are projected toward this grade as a
# best-effort SOLVER PREFERENCE after the enforce.  The LEGAL cap (and the
# validator's law) stays ROLE_GRADE_LIMITS — "ideally" means the projection
# plateaus wherever hard anchors genuinely demand more.  Radius 0 or grade 0
# disables.
APRON_CORRIDOR_SMOOTH_RADIUS_M = 200.0
APRON_CORRIDOR_SMOOTH_GRADE = 0.010
# GEODESIC corridor binding (s77 investigation, user-approved): measure the
# zone by the shortest INTERIOR path through pavement (multi-source Dijkstra
# over the solver's edge graph) instead of straight-line distance — a vertex
# 13 m across grass from a centerline is NOT served by it — and additionally
# clamp in-zone apron vertices into corridor-VALUE bands
# [corridor_alt ± grade·interior_distance] propagated at the smoothing grade,
# so an apron cannot sit on a uniform offset (wall) from the corridor that
# serves it — internal pair-cap scaling alone cannot see that.  Still a
# best-effort preference: bands yield to the legal route-law bands wherever
# they conflict (the squeeze/arbitration families).  False restores the
# straight-line zone test and pair-only smoothing.
APRON_CORRIDOR_GEODESIC = True
# Corridor-adjacent vertices SEED the geodesic field at their own solved
# values: any pavement vertex within this straight-line distance of a
# corridor polyline (≈ on the corridor surface), plus every taxi-rect
# vertex (the rect IS the corridor; wide rects' corners sit beyond any
# small threshold).
APRON_CORRIDOR_SEED_RADIUS_M = 15.0
# WRITE-LAYER ARBITRATION (s77, user-approved): when a corridor tie cannot
# reach its consensus value (route-law anchors block and the blocker
# rescue does not apply), the tie used to be DROPPED entirely — the two
# chains then wrote values metres apart at one junction and the
# disagreement stood in the surface as a wall on whatever spans the seam
# (HECA #256: G@100.9 held against T@104.2 free-pinned, 3.3 m over
# 11.5 m, per-axis exempt but a cliff to the eye).  Instead, accept a
# PARTIAL tie: clamp the consensus value into the member chain's
# anchor-feasible interval and anchor there — each chain moves as close
# to agreement as its own route law allows, shrinking the wall to the
# genuine route-law residual.  The runway-flex demand synthesis still
# fires from the ORIGINAL consensus value, so arbitration never masks a
# legitimate flex demand.  False restores drop-on-skip.
WRITE_ARBITRATION = True
# TERMINAL LEAF LEVELS (s77 user ruling, supersedes "terminals must not
# rise"): terminal pads are natural LEAF nodes — rigid-flat, but their
# LEVEL follows the apron(s) they connect to (up or down) through the
# grade projection, instead of being pre-calculated from taxi-route seed
# bands and locked.  Pads re-level to their median for coherence, are
# band-EXEMPT (their own route bands are graph-entry-noisy; the aprons
# they follow are themselves band-clamped), and move as rigid level
# groups in every projection.  A pad sharing a hard node stays held.
# False restores the s76 seed-ceiling + freeze behaviour.
TERMINAL_LEAF_LEVELS = True
# NETWORK PROFILE MODEL (#4, user-approved
# s77p4: "solve the full centerline taxi network, which includes curves,
# solve every intersection, similar to crossing runways, so they always
# agree, then map that to the geometry").  ONE elevation profile is solved
# over the COMPLETE centerline graph (now folded into the solver primitives'
# within-shape constraint build): intersections are shared vertices
# (agreement by construction — the tie /
# consensus / freeze layer is bypassed), runway contacts are hard anchors
# whose infeasibility against the rest of the field emits the runway-flex
# demand DIRECTLY, jointly-infeasible squeezes spread minimax along the
# route instead of standing as walls at seams, and the corridor write
# layer (stations, rect planes, junction twist) SAMPLES the field.  The
# singleton `_touches_runway` chain gate lifts under this model (taxiway-B
# class stubs profile from the field; there is no tie network to spread a
# squeeze — the s77p3 revert reason).  Requires TAXI_CORRIDOR_PROFILE
# (the corridor pass is the carrier).  False restores the s77 tie-layer
# behaviour byte-identically.
NETWORK_PROFILE_MODEL = True


# Per-role within-shape grade limits (rise / run).  The validator in
# tools/check_grade.py uses this table to decide whether a vertex pair on
# a polygon's ring is in violation.  ``None`` means "skip the within-shape
# grade check for this role" — used for shapes that intentionally trace
# terrain (boundary outline, groundside curbside) or that are vertical
# structures (retaining walls).  Values reference the named caps above so
# there is a single source.
ROLE_GRADE_LIMITS = {
    # Taxiway-like surfaces — 1.5% along centerline (axis), tested
    # here as 1.5% between any pair of ring vertices since the
    # ring follows the axis closely.
    "runway":             RUNWAY_MAX_GRADE,
    "primary_parallel":   TAXI_MAX_GRADE,
    "secondary_parallel": TAXI_MAX_GRADE,
    "stub":               TAXI_MAX_GRADE,
    "cross_connector":    TAXI_MAX_GRADE,
    # Apron — 1% all directions (user 2026-06-18).  Junction stays at the
    # TAXI rate (1.5%): it is the moving network where taxiways flow through,
    # not parking surface.
    "apron":              APRON_MAX_GRADE,
    "junction":           TAXI_MAX_GRADE,
    # Building pads (terminals / hangars / towers): drives the
    # flat-vs-graded code path — see TERMINAL_MAX_GRADE.  The role was
    # renamed from "terminal" (user 2026-06-12); the legacy key stays
    # as a read alias so check_grade still validates pre-rename
    # patches on disk.
    "building":           TERMINAL_MAX_GRADE,
    "terminal":           TERMINAL_MAX_GRADE,  # legacy alias (read-only)
    # Tunnel ramps descend from pavement elevation to the tunnel
    # floor; 4% is the navigable taxi grade for ramped portals
    # (per user 2026-05-08).
    "tunnel_ramp":        TUNNEL_RAMP_MAX_GRADE,
    # Ground-vehicle service roads (apt.dat 1206) grade along their
    # axis like a taxiway but at 8% — VDOT GS-9 level terrain (owner
    # 2026-08-03; see SERVICE_ROAD_MAX_GRADE above).
    "service_road":       SERVICE_ROAD_MAX_GRADE,
    # Service-road network junctions (bends / intersections) — graded
    # all-direction at the SAME car-logic cap as the rects.  This
    # coupling is deliberate and flagged for the owner: splitting the
    # junction rate from the road-body rate needs its own ruling and its
    # own constant.
    "service_junction":   SERVICE_ROAD_MAX_GRADE,
    # ── Skip-list (no grade enforcement) ─────────────────────────
    # Airport boundary is a footprint outline that traces real
    # terrain at 5 m vertex spacing.  No taxiable surface, no
    # grade rule applies.
    "boundary":           None,
    # Retaining walls are vertical 4-vertex polygons with 2 corners
    # at apt elev and 2 at tunnel-floor elev; the wall is vertical
    # by design.  Grade between the high and low corners is the
    # full step over a sub-metre run.
    "retaining_wall":     None,
    # Groundside pavement (cars / buildings, curbside / drop-off /
    # parking) follows the DEM but is graded like a ramp so steep
    # terrain is smoothed to a navigable surface rather than tracing raw
    # terrain.  ITS CAP IS THE ROAD LIMIT (owner 2026-08-12, RULINGS
    # "GROUNDSIDE PAVEMENT GRADES AT THE ROAD LIMIT"): it carries the
    # same vehicles the service road does, so it takes the same number —
    # THE SAME CONSTANT, never a second one (the owner cited "~7 %"; the
    # ruling's substance is the road limit itself, and inventing a 7 %
    # of our own is precisely the second number the ruling forbids).
    # Was GROUNDSIDE_MAX_GRADE (5 %, the ADA §403.3 / SUDAS §8B-1 /
    # Santa Barbara §D.5 walking-surface ceiling, owner 2026-08-03);
    # that constant keeps its other consumers — the fan-ramp law and
    # the groundside band's off-route pricing are different laws that
    # happen to have shared the value.  Specimen: KCLT's hillside lots
    # (ways -11715 / -11729), 5-7 % of real terrain, flat only while
    # apron law was flattening a car park.
    "groundside_pavement": GROUNDSIDE_PAVEMENT_MAX_GRADE,
    # Wingtip / RESA clearance cuts trace the cut terrain surface
    # (per-vertex node_altitudes computed directly against the DEM
    # and a ramped ceiling); like the boundary they carry no
    # within-shape grade rule.
    "taxiway_clearance":  None,
    "runway_clearance":   None,
    # Adjacent-ground graded strips trace the corridor bound (per-vertex
    # node_altitudes against the DEM + the lawful floor/ceiling); like the
    # clearance cuts they carry no within-shape PAVEMENT grade rule — the
    # adjacent-ground validator (slice 4) checks them against the corridor.
    "graded_strip":       None,
    # OLS cuts trace the obstacle-limitation ceiling (transitional /
    # approach first section) the same way — a lawful bound, not
    # pavement; ``verification.check_ols_surfaces`` is their reader.
    "ols_cut":            None,
    # Object-derived bridge terrain (feature B, user ruling R12): the
    # trench is the flat under-deck corridor floor, the causeway the flat
    # abutment approach plate — both born at layout time with per-vertex
    # node_altitudes at the grade-law value and FLAT by law (no
    # within-shape grade rule; the lockstep bridge validators check them
    # against the law functions instead).
    "bridge_trench":      None,
    "bridge_causeway":    None,
    # Terrain-side BUILDING PADS (per-cluster-object-seating-spec section
    # 5.4, gate DSF_OBJECT_OBJECT_PADS): off-pavement terrain raised or
    # lowered to meet a seated building's base, welded to pavement and
    # blended to DEM.  Like the clearance / band / OLS features it is a
    # POST-SOLVE emission whose values are pure law
    # (``grade_law.object_pad_*``), not a taxiable pavement surface, so it
    # carries no within-shape pavement grade rule — its own lockstep
    # reader is ``verification.check_object_pads``.  A pad's outer face is
    # a BENCH by design (up to DSF_OBJECT_PAD_MAX_RELIEF_M over the
    # DSF_OBJECT_FOOT_PAD_MARGIN_M blend ring); capping it here would mint
    # a violation against every lawful bench.
    "object_pad":         None,
}

# ── FLAT-AIRPORT FAST PATH — certificate constants ──────────────────────
# (docs/specs/flat-airport-fast-path-spec.md §2.5, §3.2).  Single source of
# truth for every flatness-certificate rate/tolerance, sitting next to
# ROLE_GRADE_LIMITS because the certificate budgets are derived from those
# same role caps.  See ``solver_primitives._certify_flat_shape`` /
# ``_certify_flat_rect`` and ``building_feasibility.building_feasible_levels``.
#
# The RATE FACTOR is the fraction of a role's tightest applicable grade
# budget a certificate is allowed to consume; the remaining slack funds the
# movement tolerance (``lazy_move_tolerance``) so harmonic smoothing cannot
# void the certificate (the 2026-07-05 "certificates all expanded" lesson).
# 0.6 is the value the existing apron/junction lazy tier already uses
# (previously the in-line ``flat_safety_factor = 0.6`` in
# ``_build_shape_constraints``); hoisted here so rects, seats and the
# existing apron/junction path all read ONE number.
FLATNESS_CERTIFICATE_RATE_FACTOR = 0.6

# Coverage gate (spec §3.2 ``O4_FLAT_CERTIFICATE_COVERAGE``): extends the
# 2026-07-05 apron/junction lazy tier to taxi rects and building seats.
# Default ON; ``O4_FLAT_CERTIFICATE_COVERAGE=0`` reverts every extended class
# to its eager path (the env-gate A/B inertness harness, spec §4.1).
FLAT_CERTIFICATE_COVERAGE = (
    _os_early.environ.get("O4_FLAT_CERTIFICATE_COVERAGE", "1") == "1")

# WHOLE-AIRPORT FAST PATH: DELETED 2026-08-05 (fix cycle 2, item 1, verdict
# (a) BROKEN LAW — a SEMANTIC BYPASS).  ``FLAT_AIRPORT_FAST_PATH`` /
# ``O4_FLAT_AIRPORT_FAST_PATH`` / ``flat_airport_fast_path.py`` /
# ``certify_flat_airport`` / ``apply_flat_airport_fast_path`` are gone.
#
# The Tier-2 path seeded every soft node at its DEM VALUE and skipped the reach
# bands, the spine profile, the body fill and the feasibility iteration.  Under
# the owner's DEM ruling (RULINGS 2026-08-05, "DEM is a SEED, nothing more")
# that is not an optimisation with a provable precondition, it is a second
# grading authority whose precondition is measured ON THE DEM: the certificate
# asked "is the terrain flat enough that DEM ≈ law?" and, when it said yes,
# emitted the TERRAIN instead of the law.  A genuinely slack constraint system
# solves fast on its own; there is nothing to buy.
#
# The Tier-0/1 per-shape machinery it reused is a DIFFERENT thing and stays:
# ``FLAT_CERTIFICATE_COVERAGE`` / ``FLATNESS_CERTIFICATE_RATE_FACTOR`` /
# ``lazy_certified`` defer building a shape's eager edge SET, they never write
# an elevation.  Deferring constraint construction is an optimisation;
# substituting the seed for the solve is a bypass.

# Reach-band cluster amortization (Tier 3 wave 1, ``O4_REACH_BAND_CLUSTERS``).
# The dominant per-node reach-band cost (``building_feasibility.
# reach_band_unified`` sampled through ``anchors.node_bands``) is the
# nearest-visible-centerline serving-line scan.  The serving line is spatially
# coherent, so instead of scanning per node, spatially bucket the consuming
# nodes, run the scan ONCE per bucket (at a representative point), and let every
# member the representative's line PROVABLY also serves reuse it — computing an
# EXACT, bit-identical band via the shared line without its own scan (see
# ``reach_band_unified._batch`` / ``_confirms_line``).  A member the shared line
# does not provably serve takes the exact per-node scan.  The output is
# bit-identical to the per-node scan; only the scan work is amortized.
# Default OFF (lead ruling after the wave-1 A/B): the amortization measured
# PERFORMANCE-NEUTRAL (line-share hit rates 14-28 %, confirmation cost ≈ the
# scan it replaces), and a neutral extra code path violates the
# refinements-must-simplify standing ruling.  The machinery stays for wave 2
# scaffolding (bucketing + consumer map + byte-identity tests);
# ``O4_REACH_BAND_CLUSTERS=1`` enables it.
REACH_BAND_CLUSTERS = (
    _os_early.environ.get("O4_REACH_BAND_CLUSTERS", "0") == "1")

# ── THE reach band's grid lookup (one engine, no selector) ──────────────────
# The band is ROUTE-METRIC and SERVICE-EXCLUDED: value is propagated on the
# unified spine graph minus ``UnifiedGraph.service_spine_pairs``
# (``building_feasibility.spine_value_fields``), and this grid answers only the
# LOOKUP — a point's nearest route ATTACHMENT and the local off-route leg to it
# (``raster_reach_band.solve_attachment_field``).  Grid/raster is a query
# acceleration; it does not carry the metric.
#
# HISTORY (owner directive 2026-07-29, spec ``rod-compose-and-band-single-
# source-spec.md`` §B): there used to be THREE band engines behind an
# ``O4_RASTER_REACH_BAND`` selector — the raster field, a legacy per-query
# nearest-visible-centerline path serving the raster's ``None`` answers (engine
# MIXING inside one building's ring), and a ``_build_skeleton_band`` fallback
# with no service filter at all.  The raster propagated VALUE through the paved
# grid, an AREA metric, and under-credited 8.7 m on the U-fixture whenever a
# service route crossed apron pavement (HECA's shape — biases seats LOW).  The
# legacy paths were DELETED, not gated, and the selector went with them: one
# engine needs none.  ``REACH_NO_SERVICE_SPINES`` stays — it gates the LAW
# (which edges reachability may ride), not the engine.
#
# The tear classes the tighter, correct ceiling opens at adjacent ground are
# reconciled unconditionally now (``adjacent_ground._heal_emitted_band_tears``
# + the ``to_osm`` soft-strip twin).  There is no longer a documented
# "grid-discretization residual" excusing junction ``route_band`` rows — the
# claim was falsified under a cell sweep and the constant is gone (see below).
# Cell side (m).  Fine enough that the narrowest real taxiway corridor (≥15 m)
# spans ≥3 cells and a ½-cell conservative erosion cannot close it; also the
# nearest-cell query error is ≤ cell/√2.  3 m keeps the OTHH grid at a few
# million cells (a few hundred MB of graph) while resolving corridors well.
RASTER_REACH_BAND_CELL_M = 3.0
# Grid connectivity: 8 (axial + diagonal chamfer; staircase over-estimates a
# straight segment by ≤ ~7.6 %, the SAFE band-widening direction) or 16 (adds
# knight moves through paved intermediates; ≤ ~2.8 % error, tighter/more
# faithful).  Default 8 (robust — a knight move never shortcuts a hole).
RASTER_REACH_BAND_CONNECTIVITY = 8
# Off-mask query policy: a point off the paved mask reads the nearest paved
# cell within this radius (its band widened by ``APRON_MAX_GRADE × offset``,
# the skeleton-band slack rule), else None (off-net → local within-shape law).
RASTER_REACH_BAND_OFFNET_RADIUS_M = 30.0
# Safety ceiling on the grid cell count.  Above this the raster build refuses
# and the legacy band runs (a pathological bounding box must never OOM a build).
RASTER_REACH_BAND_MAX_CELLS = 60_000_000
# RASTER_REACH_BAND_GRID_RESIDUAL_M (0.25 m) was DELETED here — cycle-5
# instrument-fix spec item 2.  It excused junction ``route_band`` rows as
# "grid-vs-continuous discretization error", calibrated on a measured worst
# case of 0.228 m over 23 rows.  Its MECHANISM CLAIM IS FALSIFIED: rebuilding
# the band at 3.0 / 2.0 / 1.5 m cells on the SAME emitted layout leaves the
# rows invariant (55 raw rows at every cell size; the ceiling at the worst
# vertex moves 0.023 m while the excess stays ~0.31 m — spjcverd report §2
# F1).  Halving the cell halves the documented bound and does not touch the
# excess, so the excess is not discretization.  By HEAD the constant was
# excusing a ~50-row 0.24-0.32 m continuum it was never calibrated for, and
# the 0.25 m filter cut through the middle of one cluster (5 rows at cell
# 3.0, 6 at 1.5) — an unstable count is the signature of an excuse, not of a
# tolerance.  The rows now REPORT; the SPJC ceil quartet they contain is
# solve/projection work (``final_grade_projection`` is the measured author),
# and the instrument's job is to show it.  Nothing replaces the constant:
# the seam contract's allowance was always a MEASURED per-line quantity and
# never spent this budget (``grade_graph_validate._seam_contract_yield``).
# SEED-CELL EXACTNESS (spec docs/specs/kill-prep-round-spec.md §3).  Two
# route nodes 0.6–4 m apart can land in ONE 3 m cell; the cell then takes
# the min ceiling of one and the max floor of the other, pricing the
# intra-cell route leg between them at ZERO and MANUFACTURING a band
# inversion up to cap × 3√2 ≈ 0.064 m (HEAZ's six inverted-band nodes:
# four of four reproduced by a collapsed cell, quarret2/bandforensics).
# ON, the cell's seed is authored by ONE node — the nearest to the cell
# CENTRE, ties by node key — and every other node seeding that cell
# contributes its interval RELAXED by the local cell cap × its
# straight-line distance to the author.  The seed-cell KEY set, the leg
# field and the ``seed ± leg`` lookup are untouched, so coverage and
# determinism cannot move and a single-node cell (distance 0) is
# byte-identical; straight-line distance under-prices the true in-pavement
# leg, so the relaxation is conservative.  A residual inversion under the
# gate is therefore a genuine node-value inconsistency, not a raster
# artifact.  OFF ⇒ byte-identical.
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: the kill-prep round ``495660a`` — HEAZ band inversions
# 10 → 3 and worst 0.0569 m → 0.0003 m at the final band build, CYXY
# within-shape ±0 and every runway vertex byte-identical, HECA break nodes
# ±0 with every role count identical).  ``O4_BAND_SEED_EXACT=0`` restores
# the collapsed-cell seeding.
BAND_SEED_EXACT = _os_early.environ.get("O4_BAND_SEED_EXACT", "1") == "1"

# ── Chromatic (graph-colored) Gauss-Seidel projection (Tier 3 wave 2c,
# ``O4_CHROMATIC_PROJECTION``) ──────────────────────────────────────────────
# Replace the feasibility projection's inner sweep (``one_solve.
# feasibility_project``) with a numpy-vectorized COLORED Gauss-Seidel POCS
# (routing-survey candidate 1, docs/research/routing_optimization_survey.md).
# The frozen constraint graph's edges are greedily partitioned into color
# classes on their WRITTEN endpoints (the moved endpoint(s) of each edge) so
# that within a class no two edges write the same node — a matching in the
# write-conflict graph.  A sweep then relaxes each class as ONE vectorized
# fancy-indexed update (disjoint writes commute) and uses the latest values
# across classes, so it is a true Gauss-Seidel step (not the stalling
# degree-normalised Jacobi) done at numpy speed.  Determinism: the coloring
# processes edges in construction order and picks the smallest free color, and
# within a class the updates are order-independent by construction — an
# order-independent fixpoint, the "counts-not-worse" acceptance class (a
# DIFFERENT legal feasible surface than the scalar worklist, so NOT
# byte-identical gate-on; validated by ``tools/check_grade.py`` counts, not
# byte-identity).  It also carries a KKT/dual feasibility certificate: a sweep
# that applies no correction PROVES every constraint satisfied, so iteration
# stops on proof and the avoided sweeps (vs the ``max_iters`` cap) are counted.
# DEFAULT ON.  ``O4_CHROMATIC_PROJECTION=0`` restores the legacy inner sweeps
# (the scalar worklist for the final projection, the degree-normalised Jacobi
# for the mid-solve vectorised path) BYTE-IDENTICALLY.
CHROMATIC_PROJECTION = (
    _os_early.environ.get("O4_CHROMATIC_PROJECTION", "1") == "1")
# Closed-form chain pre-pass (routing-survey candidate 2): before the colored
# sweep, detect 1-D chain substructures (interior nodes free with degree 2 in
# the regulated symmetric graph, bounded by immovable / branch endpoints —
# spines, rect couples, service chains) and solve their projection EXACTLY with
# the two-pass Lipschitz running clamp instead of iterating.  Applied as a
# warm-start inside the gated path (the colored GS still runs afterward and
# re-checks everything, so a mis-classified chain can only cost sweeps, never
# correctness).  ``O4_CHROMATIC_CHAIN_PREPASS=0`` disables the pre-pass (colored
# GS still runs) — used by the chain-exactness unit tests as the brute-force
# oracle switch.
CHROMATIC_CHAIN_PREPASS = (
    _os_early.environ.get("O4_CHROMATIC_CHAIN_PREPASS", "1") == "1")
# ── Vectorized geometry & emission (Wave 3, ``O4_VECTORIZED_GEOMETRY``) ──────
# Umbrella gate for the terrain-INDEPENDENT geometry + emission acceleration
# pass (shapely-2 batch predicates, prepared geometries, STRtree bulk queries,
# numpy-vectorized emit/decimation).  Every optimization under this gate is a
# BYTE-IDENTITY replacement of a scalar path — gate-on output must equal
# gate-off on every fixture (geometry is deterministic; there is no tolerance
# story).  Default ON; ``O4_VECTORIZED_GEOMETRY=0`` selects the scalar
# reference path for the A/B byte-identity check.  Individual optimizations may
# add their own finer sub-gates, but all of them are additionally short-circuited
# to the scalar path when this master gate is off.
VECTORIZED_GEOMETRY = (
    _os_early.environ.get("O4_VECTORIZED_GEOMETRY", "1") == "1")

# Hole-router pair-enumeration prune (track T3c / wave-3 R4): the v2
# conforming-cuts planner blocks collinear mid-edge ring vertices in every
# Dijkstra call (they are never sources, waypoints, bridge feet, or targets),
# so visibility edges incident to them are provably dead — skipping those
# pairs at graph-build time removes their O(V^2) share of the prepared-GEOS
# ``contains`` mass without changing a single planned cut.  v1 planner paths
# (``plan_hole_cuts``, ``route_between``, ``route_hole_opening``) always keep
# the full graph.  Default ON; ``O4_HOLE_ROUTER_MID_EDGE_PRUNE=0`` restores
# full enumeration for the cuts-parity A/B.
HOLE_ROUTER_MID_EDGE_PRUNE = (
    _os_early.environ.get("O4_HOLE_ROUTER_MID_EDGE_PRUNE", "1") == "1")

# Taxi-rect CROSS-section flatness reserve (m): a rect's two flat-cross
# (cap≈0) edges want their endpoints EQUAL, so a rect certifies its
# cross-section as already-flat only when the DEM relief across it is within
# this reserve (the flat-cross tolerance plus the smoothing reserve, spec
# §3.2).  Set to the validator's emit-rounding noise (``ELEV_ROUNDING_NOISE_M``
# = 0.03 m) scaled up modestly so a genuinely flat runway/taxiway
# cross-section certifies while any real cross-fall refuses — fail toward
# correctness.
RECT_CROSS_FLATNESS_TOLERANCE_M = 0.10

# Building-SEAT flatness tolerance (m): a building pad is emitted FLAT at one
# level (owner ruling — buildings are flat).  A seat certifies — and skips
# its per-building reach-band frontage construction, taking its DEM MEAN as
# the seated level — only when the DEM relief over the whole footprint is
# within this tolerance (the seat is flat by inspection).  Grounded in the
# post-solve pad-host re-level trigger (``PAD_HOST_LEVEL_TRIGGER_M`` = 0.5 m,
# "a normally-seated pad agrees to ≤ 0.14 m; a genuine pit/hump is metres"):
# 0.6 · 0.5 = 0.30 m keeps a certified seat's DEM-mean within the trigger of
# every footprint point, so seating flat at the mean introduces no step the
# host arbitration would flag.  NOT a grade rate (spec §2.4).
BUILDING_SEAT_FLATNESS_TOLERANCE_M = 0.30

# NEAR-MISS BUILDING-FRONTAGE recognition radius (m).  A soft-pavement
# (apron / junction / service_junction) ring EDGE that passes within this of a
# building pad, with BOTH endpoints canonically unshared with the pad, faces
# that pad across an unpaved SLIVER: the frontage law binds across the gap
# (``|z(endpoint) − z(pad node)| ≤ APRON_MAX_GRADE·d``, ``d`` the endpoint's
# distance to the pad polygon) even though no vertex is shared.
#
# MOVED HERE from ``elevation_per_surface/route_profile/anchors.py`` (cycle-5
# instrument-fix item 6, taking up that constant's own standing TODO: "rule-
# value constants belong in config.py … migrate it to config.py in a
# follow-up").  It had to move because the law now has TWO readers — the
# solve's law edges and the census's ``frontage_near_miss`` family — and a
# rule value read from a solver-internal module is a second copy waiting to
# happen (grade-law completeness: emitter and validator lockstep, never two
# copies).  Value unchanged.
#
# It is greater than observed DSF-vs-apt.dat source offsets (~0.68 m measured
# at SPJC) and well below any real landscaped setback.  It is a VALUE-side
# recognition radius only: it moves no geometry and MINTS NO IDENTITY — the
# canonical interning radius stays ``SHARED_VERTEX_TOL_M`` and is never
# widened.
BUILDING_FRONTAGE_NEAR_MISS_M = 1.0
#: The soft-pavement roles the near-miss frontage law recognizes (the same set
#: ``build_building_seats``' frontage recognition keys on).  One tuple, read by
#: the solve's edge builder and the census twin alike.
#:
#: R7b (owner ruling 2026-08-15, the sink ruling): ``service_junction`` LEFT
#: this set — "a road NEVER welds to a building (a building pad datum is
#: legitimate for its own footprint and must not propagate into the road
#: network)".  The near-miss law is a WELD across a sliver, so a road on this
#: list is a road welded to a building at one remove; it was the second of the
#: three pad→road channels the CYXY lot-377 sink ran through (the first is the
#: authority-order weld in ``groundside.law_anchor_values``, the third the
#: frontage recognition in ``build_building_seats``).  AIRSIDE frontage —
#: ``apron`` and ``junction`` — is untouched: the apron↔building frontage weld
#: is its own standing owner ruling (2026-08-08).
NEAR_MISS_FRONTAGE_SOFT_ROLES = ("apron", "junction")


def near_miss_frontage_budget(distance_m: float) -> float:
    """THE near-miss frontage budget: how far the soft-pavement endpoint's
    value may sit from its pad node's, across a sliver ``distance_m`` wide.

    The building↔apron law across the gap, at the apron cap.  ONE authority:
    ``route_profile.anchors.near_miss_building_frontage_edges`` prices its law
    edges with it and ``tools/check_grade._check_frontage_near_miss`` judges
    the emitted patch with it."""
    return APRON_MAX_GRADE * float(distance_m)

# Ground-vehicle service-road network — DEFAULT ON (owner ruling
# 2026-08-12b, "SERVICE ROADS ENABLED AND BUILT": linear service corridors
# — apt.dat ground-truck routes + OSM small roads — become real road
# pavement end-to-end).  The minter (``pavement/service_roads.
# build_service_road_network``) only ever mints where NO pavement exists
# (pavement-clear), so existing ribbons/aprons are never double-paved.
# ``O4_ENABLE_SERVICE_ROADS=0`` is the kill switch and restores the
# road-less build; the gate is recorded in the patch provenance
# (``o4_provenance_gates_on``) by config introspection.
ENABLE_SERVICE_ROADS = _os_early.environ.get(
    "O4_ENABLE_SERVICE_ROADS", "1") == "1"   # ``_os`` enters scope below
# CENTERLINE-LEVEL SOURCE DEDUPE (service-corridor round ruling 1): apt.dat
# 1206 routes are AUTHORITATIVE where present, OSM small roads complement
# them.  An OSM small-road line whose road-width corridor overlaps a 1206
# route's corridor over more than this fraction of its OWN length is
# suppressed before minting — the 1206 spelling wins.  The downstream
# rect-overlap skip stays as belt.  ``O4_SERVICE_SOURCE_DEDUPE=0`` restores
# the un-deduped union.
SERVICE_SOURCE_DEDUPE = _os_early.environ.get(
    "O4_SERVICE_SOURCE_DEDUPE", "1") == "1"
SERVICE_SOURCE_DEDUPE_FRAC = float(
    _os_early.environ.get("O4_SERVICE_SOURCE_DEDUPE_FRAC", "0.5"))

# (2026-07-31) ENABLE_DISCOVERED_TAXIWAYS lived here.  It gated the
# medial-axis discovery of unreferenced taxiway centerlines, whose only two
# consumers — ``_build_taxi_rects`` and ``junction_spine`` — were retired by
# d4f61d6 on 2026-07-29; from then on the gate switched nothing.  Retired
# with the branch (pipeline.py).  The extractor itself was deleted in the
# dead-code round; pavement/discovered_taxiways.py keeps the retirement
# record (and the rebuild cost) in its header.

# When apt.dat has NO 1201/1202 taxi-route network, synthesize the taxi
# centerline set from its row-120 PAINTED lines (paint codes 1/7/51/57 =
# the solid-yellow centerline family) after basic is-it-really-a-
# centerline checks (on-pavement, not boundary-hugging like an edge
# line, runway footprint clipped) — see
# ``apt_dat_reader.painted_taxi_centerlines``.  Small Global Airports
# fields routinely ship only painted lines; without this they build no
# taxi rects, their aprons read runway-disconnected, and the discovered-
# strip fallback reconstructs a much cruder network (user 2026-06-11;
# KOQN).  Airports WITH a 1201/1202 network are untouched (cross-
# referencing painted curves against the network is future work).
PAINTED_CENTERLINE_FALLBACK = True

# Phase 2: split large apron/junction residue pieces at their narrow NECKS
# (taxi-width pinches / arm mouths) into convex pads joined by short
# connectors.  Keeps each apron all-pair surface convex and feeds the
# directional-solver pad/connector hierarchy.  See pavement/apron_necks.py.
ENABLE_APRON_NECK_SPLIT = True

# (session 61) Open residue holes with the in-pavement VISIBILITY-GRAPH router
# (pavement/hole_router.py) instead of the full-span centroid guillotine in
# `_decompose_polygon_with_holes`: routed two-bridge SPLIT cuts that bend
# around rects corner-to-corner, never plant a mid-edge node, and never shear a
# far corner.  Default OFF while A/B-validating on HECA; flip via env
# ``O4_HOLE_ROUTER=1`` for a single build.
import os as _os  # noqa: E402
HOLE_ROUTER_ENABLED = _os.environ.get("O4_HOLE_ROUTER", "1") == "1"

# BUILD PROGRESS banners (user 2026-06-27).  ``progress.BuildProgress``
# prints a step-counted line to the Ortho4XP window at the start of each
# pavement-builder component so a watching user sees which step is
# running and how many remain.  Output-only — the emitted patch is
# byte-identical regardless.  O4_BUILD_PROGRESS=0 silences the banners.
BUILD_PROGRESS = _os.environ.get("O4_BUILD_PROGRESS", "1") == "1"

# Runtime within-shape grade WARN audit (``elevation._report_within_shape_violations``).
# It recomputes the full unified grade graph + reach bands on EVERY build just to
# print WARN chatter that nothing acts on (~12% of a HECA build).  The real grade
# gate is the CI test (``test_pavement_grade`` runs ``check_grade`` on the emitted
# patch).  Default OFF; set O4_REPORT_GRADE_AUDIT=1 to restore the build-time WARN
# lines for debugging.  Output-only — the emitted patch is identical regardless.
REPORT_GRADE_AUDIT = _os.environ.get("O4_REPORT_GRADE_AUDIT", "0") == "1"

# Parallel per-airport builds within a tile (driver.generate_auto_patches).
# Each airport's build is independent (its own OSM patch), so a ProcessPool over
# them cuts a many-airport tile from the SUM of build times toward ~the MAX.
# The tile DEM + already-extracted tile-level OSM data are shared to workers;
# each worker does its own cheap (~1s) per-airport OSM / apt.dat / DSF loads.
# Default ON (2026-06-30) for real-tile testing; the mechanism is validated
# BYTE-IDENTICAL to serial. Set O4_PARALLEL_AIRPORTS=0 to force the serial path
# (e.g. for debugging, or on a RAM-constrained machine — see the worker cap).
PARALLEL_AIRPORTS = _os.environ.get("O4_PARALLEL_AIRPORTS", "1") == "1"


def parallel_airports_worker_count(n_tasks: int) -> int:
    """Worker count for the per-airport build pool: ``min(tasks, all cores)``.

    The builds are independent and CPU-bound (the elevation solve), and the main
    process just waits on the pool, so use ALL logical cores by default — the
    real limiter is usually the airport count (few per tile).  Memory-constrained
    machines can cap it with ``O4_PARALLEL_AIRPORTS_N`` (each worker holds the
    tile DEM + its OSM + build peak, so a many-airport dense tile can be RAM-heavy)."""
    import os as _o
    env = _os.environ.get("O4_PARALLEL_AIRPORTS_N")
    if env and env.isdigit() and int(env) > 0:
        cap = int(env)
    else:
        cap = _o.cpu_count() or 1
    return max(1, min(n_tasks, cap))


# ── AIRPORT-REGION ROAD FEED (2026-07-26) ──────────────────────────────
# The tile-wide ``<tile>_small_roads.osm.bz2`` cache the small-road loader
# reads is written by the vector step ONLY at ``road_level >= 2``, and the
# default is 1 — so at default config that file exists NOWHERE and every
# consumer of ``_load_osm_small_roads`` silently saw ZERO minor roads at
# EVERY airport (verified 2026-07-26 across the whole data root: not one
# ``*_small_roads.osm.bz2``).  The feed closes that hole from the source
# the tile pipeline already keeps on disk: the regional-extract CLIP for
# this area (``OSM_data/_regional_extracts/clips/clip_+0LL+0LLL_*.pbf``),
# read for the AIRPORT REGION ONLY (boundary/pavement footprint padded by
# ``AIRPORT_ROAD_FEED_PAD_M``) and cached to a per-airport sidecar.
#
# FOUNDATION ONLY: the result is published on the layout
# (``layout.airport_road_network``) for the classification-refinement and
# inset-road-grading features to consume.  NO existing consumer is
# rewired — clearance keeps reading the tile caches through
# ``bridges._load_tunnel_road_network`` and the service-road builder keeps
# reading ``_load_osm_small_roads`` — so ON vs OFF is byte-identical on
# every airport today (see ``osm_load._load_airport_road_network``).
# OFF ⇒ exactly the pre-feed loaders (no extract read, no sidecar, no log).
AIRPORT_ROAD_FEED = _os.environ.get("O4_AIRPORT_ROAD_FEED", "1") == "1"
# Pad (m) around the airport footprint (row-130 boundary ∪ source pavement
# ∪ runways) for the feed's query box.  500 m keeps the perimeter road,
# the approach-road stubs and the level crossings just off the fence.
AIRPORT_ROAD_FEED_PAD_M = float(
    _os.environ.get("O4_AIRPORT_ROAD_FEED_PAD_M", "500"))
# Per-airport sidecar cache of the extracted feed (fingerprinted on the
# clip files + the query box + the feed's schema version).  A cold read of
# the HECA clip costs ~1.1 s (osmium-tool cut + pyosmium filter; ~11.7 s
# without the bundled osmium binary); a warm one is a pickle load.  Set
# ``O4_AIRPORT_ROAD_FEED_CACHE=0`` to disable read AND write.
AIRPORT_ROAD_FEED_CACHE = (
    _os.environ.get("O4_AIRPORT_ROAD_FEED_CACHE", "1") == "1")

# ── PAVEMENT CLASSIFICATION v1 (owner rulings 2026-07-26) ────────────
# ``apron`` is the FALLBACK bucket of the geometry phase
# (``pavement/global_slice.classify_faces``: "everything else").  A
# third-party pack that draws LANDSIDE pavement — perimeter roads, car
# parks, terminal frontage — as ordinary pavement therefore lands the
# whole lot in the airside 1.5 % apron law, which then FLATTENS real
# terrain relief under it.  Measured at HECA (2026-07-26, Tai pack,
# 99 % DSF-sourced): 251 of 318 apron shapes / 904,433 m² (32.1 % of
# apron area) are landside; mean |offset vs DEM| 5.35 m, worst +21 m.
#
# THE EVIDENCE IS BIMODAL.  Every big misclassification has 0.0 % OSM
# aeroway backing and 45-95 % road-corridor overlap; every genuine
# apron has 26-89 % aeroway backing and ≤27 % road.  So the classifier
# votes on positive evidence rather than on the absence of a taxiway.
#
# THE TWO OWNER RULINGS THIS ENCODES.
#   R-VETO  Positive OSM airside evidence keeps a shape apron,
#           absolutely.  "A road inside, or sharing an edge with a real
#           apron must follow the apron's grade."  Service roads
#           along / through aprons absorb into apron grading — never
#           split, never demoted.
#   R-SPLIT "An airport author might … make a single piece of asphalt
#           that covers both a large apron, and 5km of thin roadway.
#           We have to be able to identify where the road leaves the
#           apron … so we can clearly separate roads from aprons. …
#           roads with empty terrain on both sides need to be free to
#           grade as roads and not be classified as aprons."
#
# Implementation: ``pavement_classification.classify_pavement_v1``,
# called from the pipeline AFTER ``_reclassify_apron_junctions`` and
# BEFORE ``_reclassify_runway_disconnected_to_groundside`` so a
# demotion severs the runway touch-chain and the existing cascade
# picks up whatever the demotion orphaned.
# OFF ⇒ the pass returns immediately; the patch is byte-identical to
# the pre-feature build.
PAVEMENT_CLASS_V1 = _os.environ.get("O4_PAVEMENT_CLASS_V1", "1") == "1"
# The R-SPLIT half on its own knob: a mouth split is geometry surgery
# and the owner may want the vote without it.
PAVEMENT_CLASS_MOUTH_SPLIT = (
    _os.environ.get("O4_PAVEMENT_CLASS_MOUTH_SPLIT", "1") == "1")

# R1 — POSITIVE AIRSIDE EVIDENCE (the R-VETO threshold).  Fraction of
# the shape covered by OSM ``aeroway=apron`` polygons, by
# ``parking_position`` stand geometry, or by taxiway/taxilane
# centerline territory.  ≥ this ⇒ ABSOLUTE keep, whole shape.  0.25
# sits in the empty band between the HECA keeps (26-89 %) and the
# flips (0.0 %).
PAVEMENT_CLASS_AIRSIDE_KEEP_FRAC = float(
    _os.environ.get("O4_PAVEMENT_CLASS_AIRSIDE_KEEP_FRAC", "0.25"))
# R2 — ROAD CORRIDOR DOMINATES.  Road-feed corridor overlap ≥ this and
# airside evidence below ``AIRSIDE_WEAK`` ⇒ landside.  (227 of the 251
# HECA flips come from this rule; the flipped shapes sit at 45-95 %.)
PAVEMENT_CLASS_ROAD_DOMINANT_FRAC = float(
    _os.environ.get("O4_PAVEMENT_CLASS_ROAD_DOMINANT_FRAC", "0.30"))
# "No meaningful airside evidence" for R2 / R4.
PAVEMENT_CLASS_AIRSIDE_WEAK_FRAC = float(
    _os.environ.get("O4_PAVEMENT_CLASS_AIRSIDE_WEAK_FRAC", "0.10"))
# R3 — NOWHERE WIDE ENOUGH FOR AN AIRCRAFT.  The morphological opening
# ratio of ``object_footprints.is_vehicle_pavement_patch``, reused
# verbatim at its own constants (``DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_
# WIDTH_M`` / ``..._OPENING_RATIO``) — 24 of the 251 HECA flips.
# R4 — PARKING LOT.  Fraction of the shape covered by OSM parking
# evidence.  The airports OSM layer is an ``aeroway``-only Overpass
# query and the road feed's tag whitelist carries no ``amenity``, so
# the only parking signal available without a NEW extract read is the
# feed's ``service=parking_aisle`` ways; the fraction is measured over
# their corridors.  Fires on nothing at HECA (R2 claims those shapes
# first) — it is here so a lot with no through-road still reads as
# landside.
PAVEMENT_CLASS_PARKING_FRAC = float(
    _os.environ.get("O4_PAVEMENT_CLASS_PARKING_FRAC", "0.40"))
# R5 — PARTIAL ROAD + NO AIRSIDE EVIDENCE AT ALL, well away from any
# runway.  The long-tail catcher; fires on nothing at HECA.
PAVEMENT_CLASS_ROAD_PARTIAL_FRAC = float(
    _os.environ.get("O4_PAVEMENT_CLASS_ROAD_PARTIAL_FRAC", "0.12"))
PAVEMENT_CLASS_AIRSIDE_NONE_FRAC = float(
    _os.environ.get("O4_PAVEMENT_CLASS_AIRSIDE_NONE_FRAC", "0.02"))
PAVEMENT_CLASS_RUNWAY_STANDOFF_M = float(
    _os.environ.get("O4_PAVEMENT_CLASS_RUNWAY_STANDOFF_M", "150"))

# Evidence-geometry buffers.  A ``parking_position`` is a stand LINE
# (or a small polygon) — the aircraft it holds occupies ~20 m either
# side; a taxiway/taxilane centerline carries ~15 m of taxi territory;
# other airside aeroway LINES (runway, holding_position, jet_bridge)
# get the plain 12 m half-width.  These are the diagnosis's own
# numbers.
PAVEMENT_CLASS_STAND_BUFFER_M = float(
    _os.environ.get("O4_PAVEMENT_CLASS_STAND_BUFFER_M", "20"))
PAVEMENT_CLASS_TAXI_BUFFER_M = float(
    _os.environ.get("O4_PAVEMENT_CLASS_TAXI_BUFFER_M", "15"))
PAVEMENT_CLASS_AEROWAY_LINE_BUFFER_M = float(
    _os.environ.get("O4_PAVEMENT_CLASS_AEROWAY_LINE_BUFFER_M", "12"))
# Shapes below this never vote: a sub-100 m² residue sliver is a
# geometry artefact, and demoting it only opens a grade cliff against
# the pavement it was carved out of.
PAVEMENT_CLASS_MIN_AREA_M2 = float(
    _os.environ.get("O4_PAVEMENT_CLASS_MIN_AREA_M2", "100"))

# ── R-SPLIT geometry ────────────────────────────────────────────────
# A TAIL is a corridor nowhere wider than this: erode by half of it and
# nothing survives.  30 m clears the widest mapped carriageway plus
# shoulders while staying well under any aircraft-capable apron neck
# (``pavement/apron_necks`` treats ≤32 m as a taxilane pinch).
PAVEMENT_CLASS_TAIL_MAX_WIDTH_M = float(
    _os.environ.get("O4_PAVEMENT_CLASS_TAIL_MAX_WIDTH_M", "30"))
# …and long enough to be a road rather than an apron nib.
PAVEMENT_CLASS_TAIL_MIN_LENGTH_M = float(
    _os.environ.get("O4_PAVEMENT_CLASS_TAIL_MIN_LENGTH_M", "60"))
# A tail only leaves the body when the ROAD FEED backs it.
PAVEMENT_CLASS_TAIL_ROAD_FRAC = float(
    _os.environ.get("O4_PAVEMENT_CLASS_TAIL_ROAD_FRAC", "0.50"))
# …and it becomes a ``service_road`` (axial grading) rather than
# ``groundside_pavement`` (DEM-following) when a road CENTERLINE tracks
# its long axis for this fraction of the axis length.
PAVEMENT_CLASS_TAIL_AXIS_ROAD_FRAC = float(
    _os.environ.get("O4_PAVEMENT_CLASS_TAIL_AXIS_ROAD_FRAC", "0.60"))
# "Empty terrain on both sides" (R-SPLIT): OTHER built pavement within
# this of the tail's perimeter is a flank contact.  Same 5 m the
# apron-wall scope ruling uses for pavement adjacency.
PAVEMENT_CLASS_FLANK_CLEAR_M = float(
    _os.environ.get("O4_PAVEMENT_CLASS_FLANK_CLEAR_M", "5"))
# A tail qualifies when at most this fraction of its perimeter has a
# flank contact — "empty terrain on both sides … along most of its
# length".  The mouth chord is shared with the BODY, i.e. with the
# tail's own parent shape, and is excluded by construction.
PAVEMENT_CLASS_TAIL_MAX_FLANK_CONTACT = float(
    _os.environ.get("O4_PAVEMENT_CLASS_TAIL_MAX_FLANK_CONTACT", "0.20"))
# Anti-sliver guards on the cut, and a ring-size ceiling so the
# quadratic mouth search can never run away on a pathological ring.
PAVEMENT_CLASS_SPLIT_MIN_BODY_AREA_M2 = float(
    _os.environ.get("O4_PAVEMENT_CLASS_SPLIT_MIN_BODY_AREA_M2", "2000"))
PAVEMENT_CLASS_SPLIT_MIN_TAIL_AREA_M2 = float(
    _os.environ.get("O4_PAVEMENT_CLASS_SPLIT_MIN_TAIL_AREA_M2", "400"))
PAVEMENT_CLASS_SPLIT_MAX_RING_VERTICES = int(
    _os.environ.get("O4_PAVEMENT_CLASS_SPLIT_MAX_RING_VERTICES", "400"))

# ── PAVEMENT SCORING CLASSIFIER v2 (evidence fusion) ─────────────────
# Spec: docs/specs/pavement-scoring-classifier-spec.md (owner decisions
# 2026-07-27: full 4-class scope; 2026-07-28: enactment approved).
# Modes: "off" | "shadow" (score + log at pipeline end, mutate
# nothing) | "on" (Phase B ENACTMENT: the scorer classifies in the
# classify_pavement_v1 slot; the v1 vote, the first unscoped
# runway-disconnected pass, and the groundside route-corridor
# promotion are gated off — their laws live in the scorer).
# DEFAULT "on" — owner approval 2026-07-28 ("turn it on so I can test
# it"), accepting the measured ~1.4 s cost at HECA (builds already
# over the 60 s budget; HARD-LAW written record: spec §10.3).  Low
# legacy agreement at HECA is EXPECTED — the legacy chain is the
# thing being replaced there.
PAVEMENT_SCORE_V2 = _os.environ.get("O4_PAVEMENT_SCORE_V2", "on")
# PURE enactment (owner 2026-07-28: "how will I be able to validate the
# new system if things are falling through to the legacy one?"): LOW
# margins enact the argmax too, so every scored shape takes the
# scorer's verdict — nothing falls through.  0 restores the hybrid
# (LOW → legacy passes) development behavior.  Shapes with NO winner
# (zero evidence) always keep their born role.
PAVEMENT_SCORE_PURE = _os.environ.get("O4_PAVEMENT_SCORE_PURE", "1") == "1"
# SERVICE-ADJACENCY feature (owner lateral-contiguity ruling 2026-08-02,
# classification corollary: "road-width pavement sharing an edge with a
# service-road spine is SERVICE ROAD, never groundside").  Gate OFF ⇒ the
# ``service_adj`` feature is never computed and never scored, so the
# emitted patch is byte-identical.
# DEFAULT FLIPPED TO "1" 2026-08-12b (service-corridor round ruling 5 — the
# RULINGS:128 corollary goes live now that service corridors are built).
SCORER_SERVICE_ADJ = _os.environ.get("O4_SCORER_SERVICE_ADJ", "1") == "1"
# CORRIDOR-AWARE ROAD-WIDTH READ (service-corridor round ruling 5): the
# ``road_corridor`` width predicate decomposes a shape at its mouths before
# judging it, so ONE contiguous widening (a lot entrance) can no longer veto
# a road ribbon — the corridor-width part still reads as a corridor.  The
# widening itself keeps its own (groundside) class: the decomposition is a
# READ, it never re-cuts emitted geometry.  ``O4_SCORER_CORRIDOR_WIDTH=0``
# restores the whole-shape erosion.
SCORER_CORRIDOR_WIDTH = _os.environ.get("O4_SCORER_CORRIDOR_WIDTH", "1") == "1"
# The corridor-width part must carry at least this fraction of the shape's
# area for the ribbon to read as a corridor (a lot with a driveway stub is
# not a road).
SCORER_CORRIDOR_WIDTH_MIN_FRAC = float(
    _os.environ.get("O4_SCORER_CORRIDOR_WIDTH_MIN_FRAC", "0.5"))
# LATERAL-CONTIGUITY GRADE LAW (owner-confirmed FINAL 2026-08-02, clauses
# (2)-(5); the law lives in ``grade_law.lateral_contiguity_cap`` /
# ``…_segments`` and the emitter in
# ``groundside.apply_lateral_contiguity_law``).  ON, the new pass REPLACES
# the two proximity-band grade-adoption passes (apron-edge 2026-07-06 and
# taxi-edge 2026-07-07): they are the same ruling in its earlier,
# class-limited, proximity-delimited form, and running both would double-cap
# the same pieces.  OFF ⇒ those two passes run exactly as before and the
# emitted patch is byte-identical.
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: the classification round ``1e5a781``, which built the law
# and its emitter, and the kill-prep round ``495660a``, whose absorption
# rides it — CYXY break nodes 52 → 22 with absorption alone, strip seam
# tears 8 → 0).  The law is the owner's FINAL 2026-08-02 ruling; a default
# of "0" left the ruling unenforced.  ``O4_LATERAL_CONTIGUITY_LAW=0``
# restores the two legacy proximity-band adoption passes.
# STANDING LAW (owner 2026-08-05, no gates): Lateral-contiguity grade law (owner FINAL 2026-08-02).
# The ``O4_LATERAL_CONTIGUITY_LAW`` gate and its env override are DELETED.
LATERAL_CONTIGUITY_LAW_ENABLED = True
# SERVICE↔LOT ABSORPTION (owner 2026-08-03, docs/RULINGS.md
# "lateral-contiguity absorption is class-universal"; spec
# docs/specs/kill-prep-round-spec.md §1).  The absorption of clause (4)
# applies to a service road welded to ANY paved class — groundside LOTS
# included, not only aprons.  Two consequences, both behind this gate:
#   * a host carrying per-vertex ``node_altitudes`` (a DEM-followed lot) is
#     a legal absorb target — the merge goes through
#     ``groundside._merge_piece_into_apron``, which REBUILDS the host's
#     altitudes for the merged ring, so the 1:1 ring alignment that made
#     those hosts illegal is maintained rather than assumed away;
#   * the absorbed stretch stops being a service shape, so
#     ``route_profile.anchors.apply_service_road_dem_follow``'s private
#     cap-Lipschitz envelope no longer grades it — the second grading
#     authority the A2/A3/A4 residual break family came from.  Where a
#     stretch cannot absorb, that envelope CONSUMES the one law's number
#     (``BuiltShape.lateral_cap``) instead of the service cap.
# PORTION-ONLY (owner amendment 2026-08-03): only the laterally-contiguous
# portion absorbs; the free portion stays a road and the mouth cut between
# them is mandatory — a piece whose stations do not agree on ONE cap is
# never absorbed (it carries the cap and is counted as ``cut_failed``).
# The service SPINE is never touched: absorption removes a SURFACE, not a
# centerline.  Requires ``LATERAL_CONTIGUITY_LAW_ENABLED`` (this gate only
# widens that pass's class set).  OFF ⇒ byte-identical.
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: the kill-prep round ``495660a`` — HECA 306 stretches
# absorbed and 582 laterally-bound anchor contradictions no longer
# quarantined, CYXY break nodes 52 → 22 — and the membership-v2 round
# ``5a94c57``, which made the absorption context-conservative).
# ``O4_SERVICE_LOT_ABSORPTION=0`` restores the apron-only class set.
# STANDING LAW (owner 2026-08-05, no gates): Lateral-contiguity absorption is class-universal (owner 2026-08-03).
# The ``O4_SERVICE_LOT_ABSORPTION`` gate and its env override are DELETED.
SERVICE_LOT_ABSORPTION = True
# TRIANGLE-PLANE DEMOTION (spec docs/specs/kill-prep-round-spec.md §2).
# ``route_profile.solve._project_triangle_planes`` clamps a 3-vertex shape
# whose PLANE tilts past its role cap by moving its freest vertex; where no
# single-vertex move is lawful it currently exports the triangle to the
# break quarantine.  "No single-vertex fix exists" is a SEARCH LIMITATION,
# not infeasibility (docs/RULINGS.md: feasibility is guaranteed; quarantine
# is unauthorized), so ON the export becomes a REPORT — a log line plus the
# ``triangle_plane_unresolved`` sidecar count — and the unresolved
# triangles surface as visible violations for the solver-convergence work.
# The projection itself is unchanged either way.  OFF ⇒ byte-identical.
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: the kill-prep round ``495660a`` — CYXY break nodes 52 → 49
# with this gate alone and only +3 visible within-shape rows, every runway
# vertex byte-identical at every airport).  With §2 deleting the break
# quarantine outright, "export the unresolved triangle" has no sink left:
# the report IS the disposition.
# GATE DELETED 2026-08-05 (audit Tier 2): despite the REPORTS name this
# decided whether unresolved triangle vertices became BREAK REGIONS —
# emitted values, not a report.  Resolved to the "1" arm the default
# build already ran.
TRIANGLE_PLANE_REPORTS = True
# ── APRON TERRACE LAW (owner ruling 2026-08-04; spec
# ``docs/specs/apron-terrace-law-spec.md``) ─────────────────────────
# "Long aprons on genuinely steep ground MAY terrace into level panels
#  with declared joint steps — but it has to be done in a way that does
#  not interrupt any spine where aircraft have to travel."
# BINDING CONSTRAINT (structural here, not checked-after): a terrace
# joint NEVER crosses a taxi spine/route.  The joint geometry is
# DIFFERENCED against the corridor cover before it exists, so a joint
# that would cross a route is not shortened after the fact — it is
# never minted.
#
# STANDING LAW (owner 2026-08-05, BUILD-COMPLETE-THEN-DEBUG): the
# ``O4_APRON_TERRACE_LAW`` gate and its env override are DELETED.  There
# is no "terrace off" arm any more — a panelized apron is what the law
# produces on genuinely steep ground, and the census reports its
# declared joints as declared structures, not as defects.
# Trigger floor (spec §1): an apron constraint component only panelizes
# when its anchor/DEM/cap envelope excess reaches this.  25x the 0.01 m
# elevation materiality floor, so centimetre noise can never panelize.
# PROVISIONAL (owner-adjustable).
APRON_TERRACE_MIN_EXCESS_M = 0.25
# Declared step bound at one joint (spec §3).  PROVISIONAL — flagged
# for the owner: this is the maximum level change a single declared
# terrace joint may carry; more relief than this takes more joints.
APRON_TERRACE_MAX_STEP_M = 2.0
# Joint-to-spine clearance (spec §2, PINNED by lead review).  The
# corridor cover is buffered by the corridor half-width PLUS this
# clearance before the joint is cut out of it, so no joint vertex can
# sit inside a taxi corridor or on its edge.  PROVISIONAL 2.0 m.
APRON_TERRACE_JOINT_CLEARANCE_M = 2.0
# Corridor half-width used for the cover when no per-route width is
# known (OSM centerlines carry no apt.dat size class).  Code-C taxiway
# half width; the cover is a NO-CROSS set, so erring wide is the
# conservative direction (fewer joints, never a joint on a route).
APRON_TERRACE_CORRIDOR_HALF_WIDTH_M = 11.5
# A joint piece shorter than this is not a terrace line — it is a
# sliver between two corridors.  Dropped (and counted).
APRON_TERRACE_MIN_JOINT_LEN_M = 8.0
# FACING-BOUNDARY STEP BUDGET (flip-readiness v2 §3(c)).  A panelized
# apron's OUTER ring against a non-panelized neighbour keeps FULL law:
# the terrace budget is never rewritten there, and those nodes gain a
# generation-side cross-shape step constraint at THIS budget — the step
# READERS' own budget, so emitter and validator judge the identical
# number (``tools/check_grade`` ``--edge-step`` default; the lockstep is
# asserted by ``tests/test_apron_terrace_law.py``).
APRON_TERRACE_FACING_STEP_M = 0.5
# How close another pavement shape must come for a stretch of the
# panelized apron's exterior ring to count as a FACING BOUNDARY RUN.
# The step checks' own contact tolerance (``check_grade``
# ``_STEP_CONTACT_TOL_M``): beyond it the two shapes are gapped and a
# height difference is lawful by design, so there is nothing to conform
# to.  The HECA ``-10519``/``-10520`` pair sits 0.72-0.89 m apart.
APRON_TERRACE_FACING_PROXIMITY_M = 1.0
# Points each feature contributes toward each class, BEFORE the
# per-airport source-reliability scaling (spec §6).  Feature values are
# fractions in [0,1]; negative points are allowed.  Override individual
# rows with O4_PAVEMENT_SCORE_WEIGHTS='{"feature": {"CLASS": pts}}'.
PAVEMENT_SCORE_WEIGHTS: dict = {
    "name_apron":          {"APRON": 3.0},
    "name_taxi":           {"TAXI": 3.0},
    "name_service":        {"SERVICE": 3.0},
    "osm_apron":           {"APRON": 2.5},
    "osm_stand":           {"APRON": 2.0},
    "osm_taxi":            {"TAXI": 2.5},
    # MAPPED-TAXIWAY DOMINANCE (owner HECA burial report 2026-07-29):
    # the OSM aeroway layer maps this shape as taxiway MORE than as
    # apron/stand and nothing names it an apron.  Binary; carries the
    # taxiway mapping past the apron geometry priors (wide_blob +
    # enclosed_by_airside + apron_edge_bound = up to 4.5 APRON), which
    # at dense airports fire on every between-terminal shape and were
    # flipping mapped-taxiway junction fabric to APRON's 1 % all-pair
    # cap — the HECA south-terminal burial chain.
    "osm_taxi_major":      {"TAXI": 2.5},
    "spine_cover":         {"TAXI": 2.0},
    "spine_thread":        {"TAXI": 2.5},
    "truck_cover":         {"SERVICE": 1.5},
    "truck_thread":        {"SERVICE": 2.5},
    # Truck territory ON a road-width corridor is road identity (CYXY
    # #45/#46: service roads beside taxiways sit inside the spine halo;
    # spine_cover is suppressed by truck_cover on corridors and this
    # votes SERVICE in its place).
    "truck_corridor":      {"SERVICE": 2.0},
    "road_cover":          {"SERVICE": 0.5, "GROUNDSIDE": 2.0},
    "road_thread":         {"SERVICE": 2.0},
    # Owner ruling 2026-07-28: narrow (vehicle-only) + road-covered is a
    # SERVICE road even when too short to thread — the HECA 296-fragment
    # shadow bucket.  Outvotes road_cover's GROUNDSIDE 2.0 on narrow
    # shapes (2.5 + 0.5 vs 2.0), leaves wide lots alone.
    "road_narrow":         {"SERVICE": 2.5},
    "parking_cover":       {"GROUNDSIDE": 2.5},
    # Global-airports cross-reference (owner 2026-07-27): the default
    # apt.dat's naming/network, discounted by measured alignment — half
    # the primary name weights because it describes ANOTHER author's
    # layout of the same airport.
    "alt_name_apron":      {"APRON": 1.5},
    "alt_name_taxi":       {"TAXI": 1.5},
    "alt_name_service":    {"SERVICE": 1.5},
    "alt_taxi_cover":      {"TAXI": 1.0},
    "narrow_only":         {"APRON": -2.0, "TAXI": -1.0,
                            "SERVICE": 1.5, "GROUNDSIDE": 1.0},
    "wide_blob":           {"APRON": 1.5},
    "runway_connected":    {"APRON": 1.0, "TAXI": 1.0},
    "runway_disconnected": {"GROUNDSIDE": 2.0},
    "enclosed_by_airside": {"APRON": 1.0},
    "open_perimeter":      {"GROUNDSIDE": 0.5},
    "third_party_source":  {"GROUNDSIDE": 0.5},
    # Owner ruling 2026-07-28: airside never exists outside the OSM
    # aerodrome boundary.  Also a hard gate (G-BOUNDARY) past
    # PAVEMENT_SCORE_BOUNDARY_OUT_FRAC; the weight makes the fraction
    # itself evidence so a gated shape always carries a positive
    # GROUNDSIDE score.
    "outside_boundary":    {"GROUNDSIDE": 2.0},
    # BUILDING-FRONTAGE ruling (owner 2026-07-28, CYXY building4: "the
    # pavement around building4 should all be apron"): a narrow strip
    # fully flanked by other built shapes with NO road/truck evidence
    # is stand/frontage pavement that grades with its surroundings —
    # the vehicle-only narrow penalty does not apply (zeroed when this
    # fires) and the strip leans APRON.
    "pavement_frontage":   {"APRON": 1.5},
    # Set by the enclave re-verdict (G-ENCLAVE): pavement topologically
    # locked inside airside defaults toward the apron law — it grades
    # with what surrounds it.
    "airside_enclave":     {"APRON": 1.5},
    # STANDING FREE-ROAD LAW (owner, canonical text in
    # groundside.free_road_subsegments; scorer restatement 2026-07-28:
    # "any portion of a defined service road running along the edge
    # of, or through an apron, becomes apron").  Fraction of the
    # shape's boundary shared with apron pavement; also gates SERVICE
    # off road corridors past PAVEMENT_SCORE_APRON_EDGE_FRAC.
    "apron_edge_bound":    {"APRON": 2.0},
    # Owner ruling 2026-07-28 (SPJC #182): "apron should always abut
    # the airside side of buildings" — a shape sharing a building edge
    # while aircraft-side votes and gates APRON.
    "building_abut":       {"APRON": 1.5},
    # LATERAL-CONTIGUITY ruling 2026-08-02, classification corollary:
    # road-width pavement sharing a SUBSTANTIAL edge with the
    # service-road network is a service road, never a landside lot.
    # 2.0 is calibrated against the GROUNDSIDE case it must answer: a
    # runway-disconnected road-covered corridor scores GROUNDSIDE 4.0
    # (``road_cover`` 2.0 + ``runway_disconnected`` 2.0) — the two
    # reasons the HECA 41-shape class was demoted — while SERVICE holds
    # ``road_cover`` 0.5 + ``road_narrow`` 2.5.  The feature is only
    # ever non-zero under ``SCORER_SERVICE_ADJ``.
    "service_adj":         {"SERVICE": 2.0},
    "unpaved_cover":       {},          # logged only; tune from shadows
}
_ps_weights_env = _os.environ.get("O4_PAVEMENT_SCORE_WEIGHTS")
if _ps_weights_env:
    import json as _json
    try:
        PAVEMENT_SCORE_WEIGHTS.update(_json.loads(_ps_weights_env))
    except (ValueError, TypeError):
        pass
# Reliability metric denominators (spec §4): how much of a source counts
# as "fully present" at an airport.
PAVEMENT_SCORE_RELIABILITY: dict = {
    "osm_area_ratio": 0.5,     # aeroway area vs half the pavement area
    "osm_ways": 20.0,          # airside aeroway way count
    "road_ways": 25.0,         # road-feed way count
    "truck_len_m": 500.0,      # apt.dat 1206 total length
    "spine_len_m": 1000.0,     # taxi-spine total length
}
# Shapes below this area are not scored.  10 m², not 50 (CYXY gravel
# lot, 2026-07-28): 20-40 m² road-residue slivers left tagged
# ``junction`` by the floor acted as permanent AIRCRAFT bridges in the
# reachability erosion, welding an unreachable lot into the taxiable
# core — their road evidence is decisive, so classify them.
PAVEMENT_SCORE_MIN_AREA_M2 = float(
    _os.environ.get("O4_PAVEMENT_SCORE_MIN_AREA_M2", "10"))
# Confidence bands on the relative margin (s1-s2)/s1 (spec §8).
PAVEMENT_SCORE_MARGIN_HIGH = float(
    _os.environ.get("O4_PAVEMENT_SCORE_MARGIN_HIGH", "0.35"))
PAVEMENT_SCORE_MARGIN_MED = float(
    _os.environ.get("O4_PAVEMENT_SCORE_MARGIN_MED", "0.15"))
# G-VETO: airside evidence fraction that removes landside candidates
# (the R-VETO ruling; same 0.25 as PAVEMENT_CLASS_AIRSIDE_KEEP_FRAC).
PAVEMENT_SCORE_VETO_FRAC = float(
    _os.environ.get("O4_PAVEMENT_SCORE_VETO_FRAC", "0.25"))
# osm_taxi_major noise floor: below this taxiway cover the mapping is
# incidental (a taxiway polygon clipping a corner), not an identity
# claim about the shape.
PAVEMENT_SCORE_TAXI_MAJOR_MIN = float(
    _os.environ.get("O4_PAVEMENT_SCORE_TAXI_MAJOR_MIN", "0.15"))
# "Wide" morphology half-width: a shape surviving buffer(-25) is ≥~50 m
# across somewhere (the global-slice corridor cap), apron-scale.
PAVEMENT_SCORE_WIDE_HALF_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_WIDE_HALF_M", "25"))
# A layer's centerline must thread at least this fraction of a corridor
# shape's long axis to count as *_thread evidence.
PAVEMENT_SCORE_THREAD_MIN_FRAC = float(
    _os.environ.get("O4_PAVEMENT_SCORE_THREAD_MIN_FRAC", "0.6"))
# Aircraft-reachability path width (owner ruling 2026-07-28, CYXY
# #104: groundside = aircraft cannot REACH it — a connection counts
# only when wide enough to fit an aircraft without hitting a
# building).  13, not the 11 m pavement-existence figure: a taxi ROUTE
# needs more than bare gear width — measured at the CYXY lot, the only
# link to the taxiable core is an 11-13 m pinch through one junction
# fragment (7 m² of core contact); the owner's on-the-ground call is
# that no aircraft taxis through it.  Sweep 2026-07-28: 11 m connects,
# 13/15/18 m disconnect.
PAVEMENT_SCORE_AIRCRAFT_PATH_WIDTH_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_AIRCRAFT_PATH_WIDTH_M", "13"))
# Wingtip standoff from building pads in the reachability erosion — the
# owner's "without HITTING a building": pavement passing closer than
# this to a building is not an aircraft path (≈ half a code-A wingspan).
PAVEMENT_SCORE_BUILDING_CLEARANCE_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_BUILDING_CLEARANCE_M", "7.5"))
# SEVERANCE ruling (owner 2026-07-28, CYXY round 4: "we need to sever
# landside from airside so we can classify correctly").  A shape
# straddling the reachability contour is CUT there; an unreachable
# remainder piece splits off as its own shape only at or above this
# area.  Twice PAVEMENT_SCORE_MIN_AREA_M2: a severed piece must be
# scoreable on its own, with margin over the sliver noise a buffer
# contour cut produces along pinches.
PAVEMENT_SCORE_SEVER_MIN_AREA_M2 = float(
    _os.environ.get("O4_PAVEMENT_SCORE_SEVER_MIN_AREA_M2", "20"))
# AEROWAY-EVIDENCE severance (owner axis-A ruling 2026-07-29, HECA
# mega-apron): only shapes at/above this area with MIXED aeroway mapping
# (taxi AND apron/stand each covering ≥ the fraction) are cut at the
# mapped-taxiway zone.  Big blobs only — the slice's welded mega-shapes;
# ordinary mixed shapes score whole via osm_taxi_major.
PAVEMENT_SCORE_AEROWAY_SEVER_MIN_M2 = float(
    _os.environ.get("O4_PAVEMENT_SCORE_AEROWAY_SEVER_MIN_M2", "50000"))
PAVEMENT_SCORE_AEROWAY_SEVER_MIX_FRAC = float(
    _os.environ.get("O4_PAVEMENT_SCORE_AEROWAY_SEVER_MIX_FRAC", "0.2"))
# Severed-piece floor for the aeroway cut — a corridor piece must be a
# real corridor, not contour noise (the reachability cut's 20 m² floor
# is for pinch slivers; an aeroway piece under ~2000 m² carries too
# little of the chain to matter and just mints seams).
PAVEMENT_SCORE_AEROWAY_PIECE_MIN_M2 = float(
    _os.environ.get("O4_PAVEMENT_SCORE_AEROWAY_PIECE_MIN_M2", "2000"))
# G-BOUNDARY (owner ruling 2026-07-28, refined same day): "a shape
# ENTIRELY outside the airport boundary is guaranteed to be groundside
# or road.  If it crosses the boundary it requires further analysis by
# the rest of our rules" — airports are often authored with large
# contiguous pavement spanning the fence (an airside apron connecting
# to a parking lot outside).  The gate therefore fires only when at
# least this fraction of the shape lies outside the aerodrome polygon
# (the missing 5 % absorbs digitization misalignment); a mere crosser
# gets no gate, its outside fraction weighing in as plain GROUNDSIDE
# evidence instead.
PAVEMENT_SCORE_BOUNDARY_OUT_FRAC = float(
    _os.environ.get("O4_PAVEMENT_SCORE_BOUNDARY_OUT_FRAC", "0.95"))
# ── R3 CLASSIFICATION HARD GATES (owner rulings 2026-08-10) ──────────
# G-RUNWAY-CONTACT — "Pavement touching a runway cannot be apron".  The
# legacy near-runway apron rule exists but is DEAD under scorer v2
# (``pipeline`` gates it behind ``_scorer_owns_roles``); this gate is
# its v2 rebirth.  Contact is measured as SHARED PERIMETER: the part of
# the candidate's own ring lying within ``..._TOL_M`` of the runway
# ring.  Either bar qualifies — an absolute length (the same "a mouth
# cannot reach it" argument as ``_SERVICE_ADJ_MIN_M``) or a fraction of
# the candidate's own perimeter.  Measured specimen (OTHH 1.0.229):
# sid102, 376 m², 51 % of its perimeter on the runway.
PAVEMENT_SCORE_RUNWAY_CONTACT_TOL_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_RUNWAY_CONTACT_TOL_M", "0.5"))
PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_M", "1.0"))
PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_FRAC = float(
    _os.environ.get("O4_PAVEMENT_SCORE_RUNWAY_CONTACT_MIN_FRAC", "0.10"))
# G-APRON-WIDTH — "the entire shape narrower than a taxiway cannot be
# apron".  A candidate that VANISHES under this erosion half-width is
# nowhere wider than twice it, i.e. narrower than any taxiway, so no
# aircraft can stand on it.  Measured specimens (OTHH 1.0.229): sid105
# (4.1 m OBB width), sid104 (2.4 m).  Deliberately far below a real
# taxiway width — the gate is a floor no apron can be under, not a
# taxiway-width test.
PAVEMENT_SCORE_APRON_MIN_HALF_WIDTH_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_APRON_MIN_HALF_WIDTH_M", "2.0"))
# G-TUNNEL-ROAD — "tunneled roads are not surface roads".  A candidate
# covered this much by the corridor of a BELOW-GRADE way (``tunnel``
# tagged or ``layer`` < 0) is painted over a bore, not a free surface
# road, so SERVICE is off the table.  Same 0.25 bar as G-VETO — one
# quarter of a shape's area is an identity claim, not a clip.  Measured
# specimen (OTHH 1.0.229): sid103, a 2.5 m "service road" ribbon over
# the mapped tunnel pair -9169/-9170.
PAVEMENT_SCORE_TUNNEL_VETO_FRAC = float(
    _os.environ.get("O4_PAVEMENT_SCORE_TUNNEL_VETO_FRAC",
                    str(PAVEMENT_SCORE_VETO_FRAC)))
# Severance PINCH test (owner CYXY building4, 2026-07-28): a remainder
# is severed only when it hangs off the reachable side through a
# NARROW interface (a true pinch an aircraft cannot pass).  A piece
# sharing a LONG cut edge with the reachable side is merely the
# building-clearance SHADOW band of the same contiguous surface
# ("the pavement around building4 should all be apron") — it stays
# welded and classifies with its parent.  Default: twice the
# aircraft-path width.
PAVEMENT_SCORE_SEVER_PINCH_MAX_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_SEVER_PINCH_MAX_M",
                    str(2.0 * PAVEMENT_SCORE_AIRCRAFT_PATH_WIDTH_M)))
# Severance route-vouch FRONTAGE width (owner CYXY building2,
# 2026-07-28/29 refinement: "the entire airside facia of the building
# should be welded smoothly to airside pavement").  Within a
# route-touched piece, the vouched region floods along building faces
# through channels at least this wide (building FOOTPRINTS as hard
# blockers, not wingtip clearance) — the flood dies at a sub-width
# neck, so the groundside cut lands at the narrowest pavement chord
# off the building corner.  Applies ONLY inside route-touched pieces,
# so the un-routed #104 lot ruling is unaffected.
PAVEMENT_SCORE_SEVER_FRONTAGE_W_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_SEVER_FRONTAGE_W_M", "8.0"))
# G-ENCLAVE's ring-coverage tolerance RETIRED 2026-08-07 (spec
# docs/specs/enclave-region-law-spec.md §2): the enclave test is
# point-in-REGION now (``auto_patch/enclaves.py``), so there is no ring
# to leave uncovered and no tolerance to set.  The knob is gone rather
# than left inert — an unread constant reads as live law.
# Territory buffers: taxi-spine / truck-route evidence half-widths.
PAVEMENT_SCORE_SPINE_BUFFER_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_SPINE_BUFFER_M", "25"))
PAVEMENT_SCORE_TRUCK_BUFFER_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_TRUCK_BUFFER_M", "8"))

# APRON↔TAXI GRADE BLEND (user 2026-06-25).  A taxi route runs THROUGH aprons, so
# the apron cannot be a flat 1 % everywhere: as it approaches a taxi centerline it
# must blend toward that route's (steeper) per-letter cap to make the transition.
# The blend is ANISOTROPIC — only the ALONG-route component of an apron edge earns
# the looser cap (the apron still grades 1 % PERPENDICULAR, from its edges to the
# spine); it decays to APRON_MAX_GRADE past APRON_TAXI_TRANSITION_M from the
# route.  Lives in the shared grade_graph so the solver grades to it AND the
# validator accepts it (one graph).  O4_APRON_TAXI_BLEND=0 reverts to flat 1 %.
APRON_TAXI_BLEND = _os.environ.get("O4_APRON_TAXI_BLEND", "1") == "1"
# 40 m (user 2026-06-30): a route CENTERLINE is offset from the apron edge by the
# taxiway half-width plus the wide-junction pavement it runs through, so a taxi
# route arcing past an apron corner sits ~36 m from the apron edge even though the
# pavement is adjacent — the apron edge must still reach it to decompose against
# the arc (and blend to its cap) rather than fall back to the flat apron 1 %.
APRON_TAXI_TRANSITION_M = float(_os.environ.get("O4_APRON_TAXI_TRANSITION_M", "40"))

# ANISOTROPIC WITHIN-SHAPE EDGES (docs/anisotropic_edge_handling_plan.md).  When
# ON, a spine / junction-body / apron-blend pair's grade budget is the anisotropic
# cL·Δs∥ + cT·Δs⊥ decomposed against the pair's whole chained ROUTE (Δs∥ = spine
# arc) instead of the isotropic cap·(chord).  This credits a climbing CURVE its
# full arc length so it stops being false-flagged at junctions.  DEFAULT-ON (user
# 2026-06-30): net fewer within-shape violations + fewer >8% cliffs on every
# fixture (CYXY 319→268, SPJC 502→418, SPLP 146→133, HECA 8031→7483 body viols;
# cliffs 28→24/20→18/8→8/229→215) and 0 fundamental in the feasibility audit; a
# few residual solver-miss cliffs remain (NOT infeasibilities) — tracked as
# solver-quality follow-ups.  O4_ANISO_EDGES=0 reverts to the isotropic cap·dist
# law, byte-identical to the pre-feature build.
ANISO_EDGES = _os.environ.get("O4_ANISO_EDGES", "1") == "1"

# FORMATION-TIME SOURCE CLIP (KCLT off-source phantom, Fix C).  The global
# slice births every face 100 % on source, but DOWNSTREAM recuts (the
# route-proximity cut, frontage straightening) can sweep an apron / junction
# face off the real source pavement (apt.dat row-110 ∪ DSF ∪ runway) — KCLT
# junction #278 is 8.3 k m² at 35 % on source (a near-runway band the
# route-proximity cut carved off a real 18R-end apron; the 65 % off-source
# remainder is RESA grass).  When ON, a formation-time pass clips every
# apron / junction shape whose on-source fraction < 0.5 back to the source
# union (∪ runway, buffered by the runway-frontage halo so contact survives)
# BEFORE the pre-solve node-unification, so the clipped edges are re-noded /
# welded / solved normally.  The off-source remainder (grass, off-source by
# construction) is DROPPED — re-minting it as groundside pavement would just
# relocate the phantom onto a DEM-following surface.  O4_SOURCE_CLIP=0 reverts
# byte-identically (the pass is inert — no shape is touched).
SOURCE_CLIP_PARTIAL_COVERAGE = (
    _os.environ.get("O4_SOURCE_CLIP", "1") == "1")

# JUNCTION MESH CONSTRAINTS (user 2026-06-30).  A JUNCTION is taxi-centerline
# fill: aircraft travel ALONG the spine through it, so the only grade paths that
# physically exist are the spine (longitudinal) and the triangle-mesh EDGES X-Plane
# facets (the local surface, incl. cross-slope).  A body CHORD between two
# non-adjacent junction vertices is not a path anything traverses, and mesh-edge
# compliance already implies straight-chord compliance — so the ~O(n²) chord
# constraints are phantom: they over-report (they were the bulk of the within-shape
# count and ballooned when a rect became junction fill) AND over-constrain the solve.
# When ON, junction / service_junction shapes emit only spine + mesh-edge (+ ring-
# adjacent) constraints; the chords are dropped.  APRONS are UNCHANGED — their
# visibility-geodesic graph (stand/building → spine) is a deliberate user-ruled
# flatness model that catches AGGREGATE slope a short mesh edge misses (a steadily-
# sloping apron: each 12 m edge < 1 % but the 100 m direct chord > 1 %).  The
# solver + validator + grade test read this together (LOCKSTEP).  DEFAULT-ON
# (user 2026-06-30, for the HECA smooth-climbing-turn visual test): re-baselined
# HECA within 6950→4351 (junction −64%), CYXY 233→89 (junction −80%), aprons
# unchanged, solve −37%/−25%; every remaining violation is real (mesh miss / apron
# geodesic / runway-join).  O4_JUNCTION_MESH_CONSTRAINTS=0 reverts byte-identically.
JUNCTION_MESH_CONSTRAINTS = (
    _os.environ.get("O4_JUNCTION_MESH_CONSTRAINTS", "1") == "1")

# (20260624) ABSORB_RUNWAY_IN_APRON — the apron-merged-runway machine.  When a
# runway passes through a much-larger apron polygon, the overlapping runway
# segments are DROPPED (elevation.py) and only the NON-merged part of the runway
# is subtracted from the pavement union (pipeline.py `effective_runway`), so the
# apron/junction covers the runway footprint.  Side effect (the bug this gate
# exists to test): the runway END is then absent during the solve — the
# centerline route graph dead-ends at the built runway and never reaches the
# absorbed end's threshold, so the feasibility band can't measure the real taxi
# route to it (CYXY 02: threshold 108 m into the apron → route detours / prox
# shortcuts → building16/A2 loose, building19 bowled — see
# memory/route_band_absorbed02_prox_root_cause.md).
# When OFF: the FULL runway is subtracted from the pavement union and NO segments
# are dropped, so the runway stays present through the whole solve (a clean
# runway-shaped void in the apron; the bordering pavement grades to it as a
# junction).  This keeps the absorbed runway END a real taxi↔runway CONTACT so the
# reach band can anchor it — the spine=0 working model (user 2026-06-24).
# ★ DEFAULT OFF (2026-06-24): the plain build keeps full runways (CYXY 02 visible,
# spine clean).  ⚠ FOLLOW-UP: airports with runways GENUINELY under apron concrete
# (KPHX, 65/67 segs) want this ON — replace this global gate with a per-airport
# auto-detect (is the runway end actually paved over?).  Set O4_ABSORB_RUNWAY_IN_
# APRON=1 to restore the old merge behaviour meanwhile.
ABSORB_RUNWAY_IN_APRON = _os.environ.get(
    "O4_ABSORB_RUNWAY_IN_APRON", "0") == "1"

# (session 68) Conforming-cuts hole-router REDESIGN: plan ALL of a polygon's
# hole-opening cuts as a Prim-style MIN-SPANNING-FOREST on ONE shared
# visibility graph (each hole connects to the nearest point of the already-
# connected boundary network — exterior ring or a previously-opened hole —
# via its two shortest node-disjoint bridges).  Replaces the v1 per-hole
# independent two-bridge cuts whose Dijkstra exits all converged on a single
# exterior hub vertex, creating needle-thin (1–2°) wedge slices that the
# downstream sliver guards truncated or dropped → uncovered-source wedges
# (the HECA 670 m² fan gap).  ``O4_HOLE_ROUTER_V2=0`` restores the v1
# planner for A/B comparison.  Only consulted when HOLE_ROUTER_ENABLED.
HOLE_ROUTER_V2 = _os.environ.get("O4_HOLE_ROUTER_V2", "1") == "1"

# (s79) TERMINAL PERPENDICULAR-CHORD LAW — ★ USER RULING 2026-06-12:
# terminals adjust UP OR DOWN so that a perpendicular chord from each
# taxi centerline that intersects the terminal does not exceed this
# grade.  The perpendicular construction naturally selects LATERAL
# serving taxiways (a head-on gate lane's perpendiculars miss the pad),
# which kills the bowl-self-certification that defeated the previous
# adjacent-apron-median and corridor-1%-plane bounds (HECA terminal1
# at 100.1 vs stub B 102.3 only 36 m away).  Under the apron-follows
# model (TERMINAL_NATURAL_LEVELS) the rule holds BY CONSTRUCTION —
# the apron at the pad face sits on the corridor plane and the pad
# inherits it — so it is checked as a VALIDATOR warn, not solved for
# (the s79 solver-side lift was measured-rejected: the pad landed
# right but the apron behind it kept the bowl as within-pairs).
TERMINAL_CHORD_MAX_GRADE = 0.01
# Max perpendicular chord length.  400 m (user 2026-06-12): the
# terminal level must be adjusted so the apron grades at ~1 % to its
# serving taxiways — at 200 m the reach missed HECA's taxiway S
# 350-400 m from the big pad, so its 1 % demand never entered the
# window and the apron between settled at 1.3-1.4 %.  Where two
# taxiways' 1 % demands conflict (window inverts), the construction
# falls back to the APRON_MAX_GRADE law-rate window with the 1 %
# least-violation midpoint — the preference yields to the law, never
# the reverse.
TERMINAL_CHORD_REACH_M = 400.0

# (s80) APRON-FOLLOWS RE-SOLVE — docs/apron_follows_resolve.md (user
# direction 2026-06-12: terminals = a NATURAL RESULT of grading the
# apron correctly).  One-way dependency, no back-edges:
#   network field → taxi rects/junctions → APRONS → TERMINAL PADS.
# Under the gate: (a) pads are TRANSPARENT in the solve — ordinary
# graded nodes (TERMINAL_MAX_GRADE cap), no taxi-route seed ceiling,
# no rigid flat-coupling, no holds through the apron projections (this
# is NOT the twice-rejected rigid-free pad: there is no rigidity to
# drag; flatness is imposed AFTER from the median); (b) inside the
# corridor geodesic zone the apron's attractor is the CORRIDOR-PLANE
# value instead of the DEM (the bowl's second parent); (c) each pad
# INHERITS the median of its own settled nodes, then flattens —
# measured acceptance: a flatten that adds within-violations to its
# apron complex reverts to the settled (sloped) surface, so the pad
# can never out-run its own apron; (d) the outer-rim terrain-break
# retreat may fire beyond the corridor zone even when the apron
# interior is intentionally above the DEM.  OFF = the s79 behaviour
# byte-identically.
TERMINAL_NATURAL_LEVELS = _os.environ.get("O4_TERMINAL_NATURAL", "1") == "1"

# (2026-06-13) APRON BACK-EDGE RAMPS — docs/apron_back_edge_ramps.md (user
# direction: "allow just the back edge of aprons — the ones farthest from taxi
# routes — to go up to grade, so the buildings can be flatter and the apron
# twists slightly to meet them with ramps between, but the majority of the
# apron stays at 1%").  Extends TERMINAL_NATURAL_LEVELS: the apron strip behind
# / between the building pads is allowed to grade at APRON_BACK_EDGE_GRADE (4%)
# instead of the 1.5% apron law, so the pairwise pad resolution no longer drags
# adjacent pads to a compromise level and the FLAT-vs-SLOPE acceptance no longer
# reverts a flatten over a legal back ramp.  The front / interior is never
# relaxed (corridor smoothing still holds it at 1%).  Default ON (user
# 2026-06-13, for in-sim eval); O4_APRON_BACK_RAMPS=0 disables → byte-identical
# to the TERMINAL_NATURAL_LEVELS behaviour (the whole feature is gated).
APRON_BACK_EDGE_RAMPS = _os.environ.get("O4_APRON_BACK_RAMPS", "1") == "1"

# TAXI-NETWORK SLACK for flat terminals (user ruling 2026-06-16, docs/
# taxi_slack_terminals.md).  Replaces the back-edge-ramp philosophy: instead of
# letting the APRON grade at 4% to keep a building flat, the serving taxi
# CORRIDORS flex STEEPER within their runway-anchored route bands so the apron
# stays at 1% (1.5% only when 1% is infeasible even after flexing).  A building
# straddling terrain — whose serving corridors sit at very different elevations
# — stays flat at a level the band-widened chord window allows, raised out of
# any DEM canyon; it slopes only when even the 1.5% band window inverts.
# Default ON (user 2026-06-16, for in-sim eval).  O4_TAXI_SLACK=0 disables →
# byte-identical to the pre-feature behaviour.
TAXI_SLACK_TERMINALS = _os.environ.get("O4_TAXI_SLACK", "1") == "1"

# (apron-edge-retreat REMOVED 2026-06-16, user ruling): a post-solve pass
# (`_retreat_route_pinned_apron_edges`) used to move apron polygons inward
# to break a weld and render a cliff against a high neighbour (HECA #198
# road).  It MUTATED GEOMETRY during the elevation solve and false-fired at
# plain taxiway-rect junctions under a sharp DEM (apt_smoothing_pix=4),
# opening the HECA stub-B↔apron gap.  Deleted outright: the road ramp grades
# fine without it, and nothing should reshape pavement post-solve.

# (s81) HANGAR PADS — docs/hangar_pads.md (user rulings 2026-06-12).
# When ON, ``aeroway=hangar`` buildings are ALWAYS admitted into the
# building-pad list alongside terminals and treated identically (weld,
# apron-follows inherit, groundside).  Previously hangars only entered
# via the no-terminal fallback (user 2026-04-28, HECA mistagging);
# ``aeroway=tower`` keeps that fallback-only behaviour.  Taxi
# centerlines that enter a building footprint stop at the building
# edge and weld to it (rects never contest pad area — the failure
# mode that motivated the old guard).  OFF = fallback-only admission,
# byte-identical to pre-s81.
HANGAR_PADS = _os.environ.get("O4_HANGAR_PADS", "1") == "1"

# SEAM FIELD ANCHORS (user 2026-06-20).  On a tile-seam, pavement vertices
# are pinned to the smoothed DEM for cross-tile continuity
# (seam_anchors.apply_seam_dem_anchors).  But the NETWORK PROFILE field only
# solves to the CIFP runway anchors — it never knew the seam DEM values — so
# it graded a route to the runway, and the seam DEM pin was slapped on AFTER,
# leaving a steep step where the route meets the seam (SPLP west sliver:
# apron 8.35 %, junctions 1.6 % over 340 m).  FIX: feed every seam CROSSING
# (where a centerline crosses a tile-boundary line) into the field as a HARD
# anchor at its DEM value, so the field grades the route SMOOTHLY to the
# seam — exactly like a runway contact.  Single-tile airports have no seam
# lines → no effect (byte-identical).  O4_SEAM_FIELD_ANCHORS=0 restores the
# old behaviour.
SEAM_FIELD_ANCHORS = _os.environ.get("O4_SEAM_FIELD_ANCHORS", "1") == "1"

# RUNWAY SEAM DEM PIN (user 2026-06-20).  When a runway crosses a tile
# boundary, the old model kept the runway on its FAA vertical profile right
# through the seam (runways were excluded from tile_cut's
# ``_PIN_SLICE_ROLES``) — terrain, not profile.  But the FAA profile is a
# smoothed grade that does NOT follow the local terrain bump at the seam, and
# the tile-cut's NN-resampling of the cut piece grabs whichever nearby vertex
# is closest, so the two tiles' setback corners diverged (SPLP RW02/20: -78
# corner solved 52.7 vs -77 corner 57.3 = a 4.6 m cross-seam step, neither at
# its own setback DEM of 54.84 / 55.52).  Per the user's seam model the runway
# is graded like TWO separate runways meeting at the seam, and the seam (+
# setback) is "just another THRESHOLD at DEM": every setback node sits EXACTLY
# at the (Ortho4XP-smoothed) terrain at its OWN position — exactly the
# apron/taxi/junction model.  FIX: include ROLE_RUNWAY in the post-cut
# terrain-pin so each runway setback node is pinned to its own ``dem.alt`` and
# recorded as a seam anchor the solver HARD-holds.  Single-tile / non-crossing
# runways are untouched (no seam) → byte-identical.  O4_RUNWAY_SEAM_PIN=0
# restores the old profile-through-seam behaviour.
RUNWAY_SEAM_DEM_PIN = _os.environ.get("O4_RUNWAY_SEAM_PIN", "1") == "1"

# SEAM CUT-BACK PIN = HARD DEM ANCHOR (owner ruling 2026-07-24: "the nodes
# along a tile seam at the cutback must be anchored [to the DEM] and the
# solver then grades to it — pavement crosses the seam, you can't leave any
# kind of dip there").  ``tile_cut`` leaves a 10 m gap at each integer
# lat/lon line; that strip renders at raw DEM, so a cut-back pin sitting
# ABOVE terrain makes the pavement edge float and the taxiway drop into a
# gutter where it crosses the seam (SPLP -13/-77 + -13/-78, five junction
# pins each, +0.82..+1.16 m measured).
#
# The lift came from ``seam_anchors.runway_clamp_floor``: AIRSIDE seam pins
# were raised to at least ``runway_elev − SEAM_CLAMP_GRADE·d`` so the
# pin<->runway chain was cap-feasible BY CONSTRUCTION, and from the pin<->pin
# POCS projection in ``solver_primitives`` that then re-spread them.  Both
# traded the terrain match for guaranteed feasibility; the ruling reverses
# that trade — the DEM anchor wins and the solver grades the pavement to
# reach it, reporting (never silently midpointing) whatever residual the
# taxi grade law cannot absorb.
#
# ``O4_SEAM_PIN_CLAMP=1`` restores the pre-ruling clamp + projection for
# A/B comparison; the SEAM_CLAMP_* constants and ``runway_clamp_floor``
# stay in ``seam_anchors`` so that path is byte-identical to the old build.
SEAM_PIN_RUNWAY_CLAMP = _os.environ.get("O4_SEAM_PIN_CLAMP", "0") == "1"

# TILE-CUT HALF WIDTH.  ``tile_cut.cut_layout_at_tile_boundaries`` removes a
# ``2 x TILE_CUT_HALF_WIDTH_M`` strip of pavement centred on each integer
# lat/lon line, so the pavement's real END — the CUT-BACK edge the owner's
# 2026-07-24 ruling names — sits this far either side of the seam.  Defined
# here (not at the call site) because the runway seam-contact anchors in
# ``runway_redistribute`` must sample the DEM on exactly those lines; a
# second copy would silently un-anchor the cut-back the day either moved.
TILE_CUT_HALF_WIDTH_M = 5.0

# ── ADJACENT-GROUND SEAM PROLONGATION (owner ruling 2026-07-24) ──────────
#   "It seems like maybe the adjacent ground is being applied after the cut,
#    because it angles away from it rather than forming a clean line along
#    the cut, and we need it to be clean and consistent so it transitions
#    smoothly across the tile boundary."
#
# The owner's ordering hypothesis is CORRECT.  The adjacent-ground corridor
# is marched off pavement rings that ``tile_cut`` has ALREADY clipped back
# ``TILE_CUT_HALF_WIDTH_M`` from the integer line, so a band's frontage
# STOPS at the pavement's cut-back corner and its outer (daylight) row
# converges diagonally into that corner instead of continuing across the
# seam and being trimmed BY the cut.  Two measured consequences at SPLP
# (RW02/20 meets lon -77 at 18 deg):
#   * the strip's boundary near the seam angles away from the cut — a
#     45.5 m outer edge closing at 18 deg onto the corner plus a 3.00 m
#     closing edge at 57.29 deg, in BOTH tile halves;
#   * a COVERAGE HOLE: band material that belongs to this tile but whose
#     parent pavement lies in the NEIGHBOUR tile is emitted by nobody (the
#     neighbour marches it and then drops it as out-of-tile).  Measured:
#     ~260 m of the -13/-77 seam south of the runway corner and ~162 m of
#     the -13/-78 seam north of it carry a full graded strip on one side of
#     the line and raw terrain on the other.
#
# FIX (adjacent_ground ``_seam_prolonged_ring``): before the corridor
# march, splice each pavement ring's tile-cut SEAM run (the run of ring
# vertices sitting on a cut-back line) back out to the pavement's real
# continuation — a straight PROLONGATION of the two flanking frontage
# edges, with linearly extrapolated edge altitudes.  The march then runs
# off an un-cut frontage and the EXISTING post-emit ``cut_layout_at_tile_
# boundaries`` decides where the band ends, so the strip's seam edge is the
# cut line itself, collinear with the pavement's cut-back edge.
#
# The prolongation length is bounded by (a) the geometry — no further than
# the corridor reach can still reach back across the line — (b) the actual
# dropped pavement recorded by ``tile_cut`` on ``layout.tile_seam_offcuts``
# (so a prolongation NEVER invents pavement that is not there), and (c)
# this cap.  No recorded offcut (every single-tile airport) => no
# prolongation => byte-identical output.
ADJACENT_GROUND_SEAM_PROLONG_ENABLED = (
    _os.environ.get("O4_ADJACENT_GROUND_SEAM_PROLONG", "1") == "1")
# Hard cap (m) on one prolongation, measured along the frontage from the
# cut-back corner.  300 m covers a code-4 runway's graded strip crossing a
# seam at the shallowest obliquity we have measured; the offcut bound (b)
# is what actually binds at every airport tested.
ADJACENT_GROUND_SEAM_PROLONG_MAX_M = float(
    _os.environ.get("O4_ADJACENT_GROUND_SEAM_PROLONG_MAX_M", "300.0"))

# PROLONGED FRONTAGE = THE ZONE NODE'S ALTITUDE REFERENCE (defect fix
# 2026-07-25; the stage-3 blocker on ``RUNWAY_SEAM_VERTEX_DEM_PIN``).
#
# The band's zone nodes are encoded for the solver as an envelope interval
# to their FROZEN-NEAREST host pavement ring vertex
# (``solver_primitives._build_adjacent_ground_zone_constraints``:
# ``elev[node] - elev[host] in [floor_off, ceil_off]``).  A zone row
# stationed on a PROLONGED (synthetic) ring vertex cannot host there — the
# vertex is not a solver variable — so ``adjacent_ground`` re-homes it onto
# the nearest REAL ring vertex, which is the CUT-BACK CORNER, up to a whole
# prolongation away IN STATION (300 m at SPLP).  That repair was positional
# only, so the law corridor for the whole prolonged frontage stayed anchored
# to the corner's altitude.  Measured SPLP -13/-078 with the runway seam
# vertex pin ON: band vertices 260 m north of the runway's seam crossing
# emitted 54.60 / 55.10 m (corner 55.80 m + the envelope) between
# seam-pinned neighbours at 59.0 m — a 4.4 m spike that failed
# ``tests/test_tile_cut_parity.py`` at 4.55 m.  The profile-authority path
# MASKED it (the corner's profile altitude sat near the band's own level);
# the wrong SOURCE was there either way.
#
# With this ON the re-homed node's envelope is shifted by
# ``station frontage altitude - re-homed host altitude``, so the corridor is
# centred on the flanking frontage edge's OWN extrapolated altitude — the
# design ruling above — while still referencing a real solver variable.
# Geometry, host choice and envelope width are untouched (value sourcing
# only).  Zero shift wherever the host was already the station's own ring
# vertex, so this is a structural no-op for every airport that prolongs
# nothing.  "0" restores the pre-fix corner-anchored values.
ADJACENT_GROUND_PROLONG_HOST_REF = (
    _os.environ.get("O4_ADJACENT_GROUND_PROLONG_HOST_REF", "1") == "1")

# TERRAIN CUT-BACK EDGE = DEM CONTRACT (same owner ruling; the ELEVATION
# half of the same defect).  ``tile_cut``'s polygon difference mints exactly
# TWO vertices per graded-strip cut-back edge and values them by
# interpolating along whatever band chord crossed the line — measured SPLP
# -13/-78: a single straight 223 m seam edge sitting 3.3 m below its own DEM
# at one end, with the two tile halves disagreeing by up to 2.58 m (mean
# 0.96 m) along the seam.  The 10 m gap the cut opens renders at raw DEM, so
# that is a cliff at the tile line.
#
# With the gate ON, ``tile_cut._pin_terrain_piece_seam_edge`` DENSIFIES each
# cut-back edge onto absolute ``_SEAM_TERRAIN_PIN_STEP_M`` stations and pins
# every node to the DEM at its own position — the same contract every other
# role already honours at a seam.  The pin is a pure function of (cut-back
# line, station spacing, DEM), so adjacent tile builds land on the identical
# terrain line: measured cross-seam agreement 2.58 m -> 0.05 m worst.
# Only fires where a tile cut actually severs a graded strip, so every
# single-tile airport is byte-identical.
TILE_SEAM_TERRAIN_DEM_PIN_ENABLED = (
    _os.environ.get("O4_TILE_SEAM_TERRAIN_DEM_PIN", "1") == "1")

# AIRSIDE CUT-BACK EDGE = DEM CONTRACT (owner ruling 2026-07-25, the
# PAVEMENT half of the rule the graded strips above already honour).  The
# strip pin fixed terrain; the pavement beside it was still only pinned
# where ``tile_cut`` happened to MINT a vertex — the two slice crossings —
# so an airside cut-back edge could run tens of metres between DEM-true
# ends, chording across the terrain the neighbouring 10 m gap renders, and
# the two tiles' independent builds had no shared node to agree on in
# between.
#
# With the gate ON, ``tile_cut.repin_airside_seam_cutbacks`` runs once at
# the end of ``pipeline._unify_airside_geometry`` (the final PRE-solve
# node-set) and, over airside rings:
#   1. DENSIFIES every cut-back edge onto the SAME absolute
#      ``cutback_stations`` the graded-strip pin uses — one source, so a
#      strip and the pavement it abuts meet vertex-for-vertex;
#   2. sets every seam vertex, pre-existing or newly minted, to ``dem.alt``
#      at its own position;
#   3. registers each in ``layout._seam_anchor_keys`` so the per-surface
#      solver HARD-anchors it on writeback (solver_primitives) instead of
#      letting the body fill drag it to the route level.
# Idempotent (a second run finds every station already present) and a
# pure function of (cut-back line, station spacing, DEM), so both tiles
# reproduce the identical node set.  Fires only where a tile cut actually
# severs airside pavement => every single-tile airport is byte-identical.
#
# ROLE_RUNWAY is EXCLUDED from this sweep: see RUNWAY_SEAM_DEM_PIN above
# and RUNWAY_SEAM_VERTEX_DEM_PIN below — the runway carries an FAA
# vertical profile as well as the seam contract, so it gets its own
# reconciled path rather than a raw per-vertex overwrite of this shape.
AIRSIDE_SEAM_DEM_REPIN = (
    _os.environ.get("O4_AIRSIDE_SEAM_DEM_REPIN", "1") == "1")

# ── RUNWAY SEAM CONTACT ANCHORS (owner ruling 2026-07-24) ────────────────
#   "This has never worked, trying to do anything other than DEM at the tile
#    seam causes visual disaster in X-Plane.  We are not giving up the CIFP
#    thresholds, it's just that a tile seam acts like a crossing runway, it's
#    ANOTHER anchor that is part of the runway grading.  The tile seam at ALL
#    points must be anchored at DEM."
#
# The runway arm of the seam-DEM rule.  Every OTHER role takes the DEM
# directly at its seam vertex (``seam_anchors.apply_seam_dem_anchors`` /
# ``tile_cut._terrain_pin_slice_nodes``).  A runway cannot: it also carries
# CIFP threshold elevations and the FAA grade / vertical-curve law, and it is
# laterally FLAT, so its seam contact — a whole LINE across the runway's width,
# 148 m of it at SPLP's 18-degree oblique crossing — reaches the surface
# through the one degree of freedom a runway has, its longitudinal profile.
# The seam therefore enters ``runway_redistribute`` exactly the way a crossing
# runway does: as additional HARD anchored samples in the profile solve, which
# then reconciles CIFP thresholds + seam DEM + the FAA gates in ONE pass
# (``solve_profile_with_minimal_end_zone_cap``) before the single solve.
#
# ``RUNWAY_SEAM_CONTACT_STEP_M`` is the spacing at which the runway's contact
# with the seam LINE is sampled.  Cross-tile determinism: the contact is
# measured on the WHOLE runway (redistribute runs BEFORE ``tile_cut``), the
# step walk starts at the contact's first endpoint, and the DEM is the
# ``preserve_boundary``-blended value at the tile line — so both tile builds
# derive the identical station/elevation list without seeing each other.
RUNWAY_SEAM_CONTACT_STEP_M = 10.0

# Not every sampled contact point can be honoured: where the terrain across
# the seam contact is itself steeper than a runway may be, anchoring all of
# it would emit a law-violating (and visibly jagged) surface.  The accepted
# set is chosen by a deterministic left-to-right sweep that ALWAYS keeps the
# two extreme contacts (the runway's visible terrain contacts at the seam)
# and admits an interior sample only when both of its neighbouring segments
# stay within ``RUNWAY_MAX_GRADE``.  Rejected samples are REPORTED with their
# residual — never silently midpointed.  ``O4_RUNWAY_SEAM_CONTACT=0`` reverts
# to the pre-ruling behaviour (edge contacts filtered to the "hump" class,
# i.e. only where the DEM pokes ABOVE the profile).
RUNWAY_SEAM_CONTACT_ANCHORS = _os.environ.get(
    "O4_RUNWAY_SEAM_CONTACT", "1") == "1"

# ── RUNWAY CUT-BACK VERTICES = DEM (owner ruling 2026-07-25) ─────────────
#   "every node along the tile seam cutback MUST be exactly at DEM ...
#    definitely including the runway."
#
# The last exemption falls.  ``RUNWAY_SEAM_DEM_PIN`` (above) routed a cut
# runway piece's vertices through the REDISTRIBUTED FAA PROFILE instead of
# the DEM, because on 2026-07-03 the raw per-vertex pin was measured to
# carve a 4.2 m V-notch into SPLP's RW02/20: the seam crosses at 18 deg, the
# cut-back edge's two band-edge corners span 141 m of station, and their DEM
# values (55.5 / 59.7 m — read as a ravine wall) implied 2.98 %, twice the
# 1.5 % cap.
#
# THAT MEASUREMENT NO LONGER REPRODUCES.  Re-measured 2026-07-25 at the same
# four cut-back corners, station separation 140.86 m (matching the original
# report's "141 m", so the geometry is the same): worst corner span 2.03 m =
# 1.44 %, INSIDE the cap — and the pre-2026-07-25 nearest-neighbour sampler
# reads the same 1.44 %.  The ravine wall was never in the terrain; it was an
# artifact of the DEM STATE of that day (pre-densification working grid,
# pre-honest-resolution smoothing radius, pre-bilinear inset bake).  With the
# working grid harmonized across the seam and the query reading the surface
# the mesher renders (``O4_DEM_QUERY_BAKED``), both tiles read the identical
# value at every cut-back corner, so the pin is now cross-tile exact.
#
# With the gate ON a cut runway piece takes ``_terrain_pin_slice_nodes`` —
# the same per-vertex DEM pin every other role already takes — and the
# solver stops exempting runway-owned seam buckets from the DEM re-sample.
# ``_pin_runway_piece_to_profile`` remains as the gated fallback and is
# still used whenever the DEM pin cannot value a vertex.
# ``O4_RUNWAY_SEAM_VERTEX_DEM_PIN=0`` restores the profile-authority path
# byte-identically.
#
# ★ DEFAULT **ON** since 2026-07-25 (owner ruling above, blocker cleared).
# The RUNWAY half verified at the flip: SPLP RW02/20's cut-back edge on
# -13/-078 reads 55.80 / 55.29 / 55.03 / 54.78 / 54.27 m — a smooth 1.53 m
# ramp over the edge (~1.09 % of station, inside the 1.5 % cap), no V-notch,
# and cross-tile exact.
#
# HISTORY (kept: it names the defect this pin exposed).  The first flip
# attempt was reverted because the ADJACENT-GROUND bands flanking the runway
# emitted 4.4 m spikes ~270 m NORTH of the seam crossing (SPLP -13/-078:
# band vertices at 55.10 / 54.60 m between neighbours at 59.0 m), failing
# ``tests/test_tile_cut_parity.py::
# test_cross_tile_cut_edge_elevations_consistent`` at 4.55 m.  ROOT CAUSE
# (found 2026-07-25, NOT in this pin): the band's zone nodes are encoded to
# their frozen-nearest host pavement ring vertex, and
# ``adjacent_ground``'s seam-prolongation host repair re-homed a station on
# a PROLONGED frontage onto the cut-back CORNER — hundreds of metres away in
# station — so the corner's altitude anchored the whole prolonged band.  The
# profile path merely MASKED it (the corner's profile altitude sat near the
# band's own level); the wrong source was there either way, and with the pin
# OFF the same fix moves 21 SPLP band vertices by up to 2.20 m.  Fixed by
# ``config.ADJACENT_GROUND_PROLONG_HOST_REF`` (value sourcing only); parity
# with this pin ON is now worst 2.15 m of the 2.5 m tolerance.
RUNWAY_SEAM_VERTEX_DEM_PIN = _os.environ.get(
    "O4_RUNWAY_SEAM_VERTEX_DEM_PIN", "1") == "1"

# ── RUNWAY SEAM CUT-BACK: EVERY NODE AT DEM (owner ruling 2026-07-26) ────
#   "ALL nodes along the seam MUST be at exact DEM and anchored BEFORE the
#    solve, then the solver can grade between them and its other anchors to
#    maintain grade."
#
# The COMPLETION of ``RUNWAY_SEAM_VERTEX_DEM_PIN`` above, which shipped
# 2026-07-25 pinning only the vertices that EXISTED when ``tile_cut`` ran.
# On SPLP that was exactly TWO — the runway's cut-back edge crosses the
# seam obliquely, so the cut mints only the two slice crossings 148 m
# apart — and every node BETWEEN them was minted later (emit-time chord
# densification / the epsilon-wedge weld) and valued by PLAIN LERP between
# the two DEM-pinned ends.  The owner saw exactly that on -13/-077's west
# cut-back: three interior nodes 0.16 / 0.43 / 0.45 m ABOVE the terrain the
# neighbouring 10 m gap renders.  Two halves, both under this gate:
#
#   1. ROLE_RUNWAY joins ``tile_cut.repin_airside_seam_cutbacks`` — the
#      PRE-solve sweep every other airside role already takes.  The runway
#      cut-back edge is densified onto the SAME absolute
#      ``cutback_stations`` the graded strip beside it uses, every station
#      is set to ``dem.alt`` at its own position, and every bucket is
#      registered on ``layout._seam_anchor_keys`` so the solver hard-holds
#      it.  Because the edge then carries a node every 10 m, the emit-time
#      densifier (60 m chord cap) has nothing left to interpolate — the
#      lerp class that produced the defect cannot re-appear.
#   2. ``runway_redistribute._select_feasible_seam_anchors`` stops VETOING
#      seam contact samples the FAA grade law cannot step through.  Under
#      the ruling the DEM anchor wins at every seam sample and the grade
#      residual is REPORTED (same discipline as the 2026-07-24 cut-back
#      ruling and the ``[seam-pins]`` residual report), never silently
#      dropped.  The old sweep kept the two extremes plus 5 of 48 samples
#      at SPLP and let the profile float up to 0.51 m over the rest.
#
# ``O4_RUNWAY_SEAM_CUTBACK_DEM=0`` restores the 2026-07-25 behaviour
# (two-extremes-only pin + feasibility veto) byte-identically.
RUNWAY_SEAM_CUTBACK_DEM_ANCHORS = (
    RUNWAY_SEAM_VERTEX_DEM_PIN
    and _os.environ.get("O4_RUNWAY_SEAM_CUTBACK_DEM", "1") == "1")

# ── SEAM PROFILE ANCHOR COLLAPSE (owner ruling 2026-07-26) ───────────────
# The 2026-07-26 all-nodes-at-DEM ruling above anchored every EDGE-contact
# sample in the LONGITUDINAL profile too — and at an oblique crossing the
# ~48 laterally-spread samples fold the terrain's CROSS-runway slope into
# the 1-DOF profile over ±70 m of station (SPLP RW02/20 at 17.7°: spans
# wobbling 0.41 → 2.07 → 3.07 → 2.65 → 1.66 % against a 1.41 % design
# grade — an unsmoothed terrain trace, not a ramp; anchored samples are
# exempt from every grade cap, ``pavement/runway_segments.py``).  The
# owner's follow-up: the SPINE must grade cleanly from the DEM at the cut
# back to crown height.  With this ON the profile takes ONE anchor per
# boundary line — at the CENTERLINE crossing, valued at that point's own
# DEM — so inter-anchor grades reflect the true longitudinal terrain and
# the joint solve's caps + K-factor own the ramp back to design grade.
# The lateral seam contract is untouched: the cut-back RING stations stay
# DEM-pinned every 10 m (half 1 of the ruling above), and the transverse
# crown taper absorbs the cross-slope, as it should — a 1-DOF profile
# never could.  ``O4_RUNWAY_SEAM_PROFILE_COLLAPSE=0`` restores the
# all-contact-samples profile anchoring byte-identically.
RUNWAY_SEAM_PROFILE_COLLAPSE = (
    RUNWAY_SEAM_CUTBACK_DEM_ANCHORS
    and _os.environ.get("O4_RUNWAY_SEAM_PROFILE_COLLAPSE", "1") == "1")
# How far from a tile cut line the deviation-closure ramp is treated as
# seam-governed by the profile reader (``verification.
# check_runway_profile``): over-cap spans wholly inside the zone are
# REPORTED as ``seam_dem_step`` residuals (the seam anchor sits at raw
# DEM below the design line; closing that deviation on a 1.4 %-class
# design grade cannot stay under 1.5 % — SPLP measures 1.77-1.88 % over
# ~60-120 m).  Consumed only with the collapse gate ON.
RUNWAY_SEAM_RAMP_ZONE_M = float(
    _os.environ.get("O4_RUNWAY_SEAM_RAMP_ZONE_M", "150.0"))

# RUNWAY DE-SEGMENTATION (user mandate 2026-07-07, docs/
# runway_single_polygon_plan.md).  Segments are a hi/lo-era vestige: each
# sub-rect was a 4-corner PLANE, so the curved FAA profile required cutting
# the runway at every profile sample station — and every interior segment
# CROSS-EDGE cut flat across the crowned surface (the centre-dip defect the
# part-30i hotfix tents over).  With per-vertex node_altitudes from birth
# the constraint is gone: emit ONE polygon ring per runway ref, the profile
# carried by long-edge nodes at the SAME stations the segments used
# (physical ends + CIFP thresholds + pav_intersections + crossing anchors;
# seam samples join later via redistribute), no interior cross-edges at
# all.  Tile-SEAM cuts stay (a seam-crossing runway is still split at the
# seam band); refs participating in a runway-runway crossing keep the
# legacy segmented path until the crossing-carve slice lands.
RUNWAY_SINGLE_POLY = _os.environ.get("O4_RUNWAY_SINGLE_POLY", "1") == "1"


# DSF terminal/hangar building footprints (user 2026-06-12) — see the
# documented block near LOAD_DSF_PAVEMENT above.  Read here because
# ``import os as _os`` only comes into scope at this point in the file.
DSF_BUILDINGS = _os.environ.get("O4_DSF_BUILDINGS", "1") == "1"

# OSM terminal-way authority — the DSF-cluster ABSORB fraction (owner
# 2026-08-09; see the documented block near LOAD_DSF_PAVEMENT above).
# Read here because ``import os as _os`` only comes into scope at this
# point in the file.
DSF_CLUSTER_OSM_ABSORB_FRAC = float(
    _os.environ.get("O4_DSF_CLUSTER_OSM_ABSORB_FRAC", "0.5"))

# (20260617) AGP HANGAR BUILDINGS (user 2026-06-17): X-Plane also places
# airport hangars as ``.agp`` AUTOGEN POINTS — a single ``OBJECT`` handle
# + heading in the DSF, with the footprint encoded in the ``.agp`` sidecar
# (TILE/CROP_POLY in texture pixels × TEXTURE_WIDTH/HEIGHT ÷ TEXTURE_SCALE,
# anchored at ANCHOR_PT).  ``dsf_reader.read_dsf_buildings`` resolves the
# sidecar through the X-Plane ``library.txt`` map and projects the footprint
# onto the handle, feeding it into the SAME building pool as the ``.fac``
# facades (role ``"hangar"``).  Scoped initially to the
# ``lib/airport/Common_Elements/Hangars/`` virtual prefix.  Default ON
# (user 2026-06-17, for in-sim testing); O4_AGP_BUILDINGS=0 disables it
# (byte-identical to the prior .fac-only behaviour).  Has no effect
# unless DSF_BUILDINGS is also ON (shares the building path).
AGP_BUILDINGS = _os.environ.get("O4_AGP_BUILDINGS", "1") == "1"

# (20260614-02) TERM-BRIDGE GROUPING (user 2026-06-14): X-Plane's
# Terminal_kit ships ``term_bridge_*.fac`` connector facades (enclosed
# skybridges / link spans) that physically join two ``term_building_*``
# facades.  When ON, these bridge footprints are fed into the DSF
# building clustering as CONNECTORS so a building + bridge + building
# run unions into ONE pad and grades as a single flat group (the
# bridged concourses sit at a common level).  OFF = bridges ignored
# (the prior behaviour, byte-identical to DSF_BUILDINGS alone).  Has
# no effect unless DSF_BUILDINGS is also ON.
TERM_BRIDGE_GROUPING = _os.environ.get("O4_TERM_BRIDGE_GROUPING", "1") == "1"

# (20260708) DSF OBJECT BUILDINGS (user 2026-07-08, ruling R4 in
# docs/dsf_object_integration_spec.md): scenery authors bake many
# buildings into one ``.obj`` whose DSF placement anchor may sit hundreds
# of metres from any geometry.  auto_patch cannot see those buildings at
# all today (``_building_role_for_def`` requires ``.fac`` and
# ``is_agp_building_def`` whitelists ``.agp``) — roughly 105 of them at
# KCLT.  ``dsf_reader.read_dsf_object_buildings`` parses the OBJ8,
# partitions it into structures (connected components of the
# epsilon-contact graph — docs/obj8_structure_partition.md), and feeds
# their footprints into the SAME building pool as the ``.fac`` facades
# (role ``"object"``).  Additive: no source is overridden; the existing
# facade clustering unions any overlap.  Default OFF until measured on
# the gate airports.  Has no effect unless DSF_BUILDINGS is also ON
# (shares the building path).  OFF is byte-identical to the prior build.
DSF_OBJECT_BUILDINGS = _os.environ.get("O4_DSF_OBJECT_BUILDINGS", "1") == "1"

# Convex hull is the shipped footprint ring (user 2026-07-08, ruling R3:
# measure the pad interaction before paying for fidelity).  The union of
# the projected solid triangles is faithful for L-shaped terminals but
# needs a simplify tolerance and a hole policy.  OFF restores the hull.
DSF_OBJECT_FOOTPRINT_UNION = (
    _os.environ.get("O4_DSF_OBJECT_FOOTPRINT_UNION", "0") == "1")

# ── R6-1: A DSF BUILDING PAD NEVER SPANS WATER ────────────────────────
# (docs/specs/round6-othh-residuals-spec.md R6-1, owner in-sim residual.)
# The hull ring above is exactly why: measured at OTHH on the 2026-08-10
# rebuild, ``building1`` (way -10001, 19,466 m²) carried 2,055 m²
# (10.6 %) of open water because its CONVEX HULL bridged a lagoon and its
# shore.  Closing and simplifying the ring added nothing — a hull is
# doing what a hull does — so the DSF-cluster pads are CLIPPED by the OSM
# water ∪ sea union after the close/simplify loop.  OSM-WAY pads are
# NEVER clipped (the mapper owns the footprint they drew).
# OFF is byte-identical to the pre-round-6 build.
DSF_PAD_WATER_CLIP = _os.environ.get("O4_DSF_PAD_WATER_CLIP", "1") == "1"

# How far the SEA reaches inland-of-nothing for the clip above.  Open
# ``natural=coastline`` ways are lines, not polygons: OSM orients them
# with LAND ON THE LEFT, so the sea is the RIGHT-hand single-sided buffer
# of the local coastline.  This is the buffer's half-width AND (halved)
# the margin the coastline is clipped to around the pads, so the band is
# built local and cheap — a whole-tile sea polygon is the vector step's
# job, not a building pad's.  A pad more than this far out to sea from
# any mapped coastline is not clipped by the coastline limb (the water
# layer still applies).
DSF_PAD_WATER_CLIP_SEA_BAND_M = float(
    _os.environ.get("O4_DSF_PAD_WATER_CLIP_SEA_BAND_M", "2000"))

# HULL-FILL FLOOR on the hull-path footprint (owner defect 2026-07-27,
# HECA building188): a convex hull over a handful of SPARSE bases — an
# apron floodlight mast (2.6 × 2.6 m), a few jersey barriers and one
# stray below-grade co-baked fragment that opened the 1.5 m base band —
# minted a phantom 4,638 m² "building" pad punched into a graded apron
# (1.9 m pad↔apron step; no OSM building exists there).  A real
# building's triangulated floor/wall bases fill their own hull (ratio
# ≥ 1 is common); scattered street furniture fills ~0.02.  Below this
# floor the structure gets NO pad — same law family as
# ``DSF_OBJECT_CONNECTOR_MAX_FILL``, applied to the FINAL hull.  0
# disables.  The triangle-union path (``DSF_OBJECT_FOOTPRINT_UNION``)
# is fill-true by construction and skips the gate.
DSF_OBJECT_MIN_FOOTPRINT_FILL = float(
    _os.environ.get("O4_DSF_OBJECT_MIN_FOOTPRINT_FILL", "0.1"))

# TALL-BASE FILL FLOOR, the fill gate's sibling (same HECA defect,
# second composition): a SOLID 0.3 m sidewalk/ground plate welded to a
# 28 m floodlight mast defeats both the height gate (the mast supplies
# 37 m of vertical extent) and the base-fill gate (the plate supplies
# dense base triangles) — yet it is still street furniture on a slab,
# not a building.  The discriminator: a building's TALL member covers
# its own footprint; the weld's tall member (the mast) covers 0.15 % of
# the hull and its covering member (the plate) is 0.3 m tall.  Tall-base
# fill = Σ base-triangle area of resources whose own vertical extent ≥
# ``DSF_OBJECT_MIN_BUILDING_HEIGHT_M`` ÷ hull area; a real terminal
# reads ~1.0, the plate+mast weld ~0.002.  Kept LOW so multi-object
# compositions (a tall core with short annexes welded in) pass.  0
# disables.
# FLOOR CALIBRATION (measured HECA 2026-07-27): the plate+mast weld
# class and sparse street furniture measure < 0.002 (670 of 813 skip
# events; phantom building124 at ~0.0015); THIN-WALL terminal shells —
# material-split wall objects whose 1.5 m footing band projects as thin
# strips — measure ~0.002-0.01 and are REAL buildings that need their
# pads.  The floor sits between the two populations; raising it toward
# 0.05 culled ~140 thin-wall shells (buildings 498 -> 90) and must not
# happen silently.
DSF_OBJECT_MIN_TALL_BASE_FILL = float(
    _os.environ.get("O4_DSF_OBJECT_MIN_TALL_BASE_FILL", "0.002"))
# What counts as a TALL member for the tall-base fill above.  Its own
# constant on purpose: A11's ``DSF_OBJECT_MIN_BUILDING_HEIGHT_M`` is a
# separately owned gate (tests and users legitimately zero it), and the
# tall-base discriminator must not silently degrade to "everything is
# tall" when they do.
DSF_OBJECT_TALL_MEMBER_MIN_EXTENT_M = float(
    _os.environ.get("O4_DSF_OBJECT_TALL_MEMBER_MIN_EXTENT_M", "2.5"))

# ── BUILDING EVIDENCE (R18-2, owner ruling 2026-08-11b) ─────────────
# A DSF-object footprint ring may seed a building pad ONLY with BUILDING
# EVIDENCE — never on solid reach alone.  Two evidence sources, OR-ed:
#
#   (a) an intersecting OSM building / terminal / hangar footprint
#       (the pipeline half — ``_collect_dsf_object_building_footprints``
#       is the only place an OSM polygon exists);
#   (b) a VERTICAL-STRUCTURE test on the object's own solid geometry
#       (the reader half — ``object_footprints.structure_ring``), plus
#       the name-vouching the hull-fill floor already extends.
#
# The defect it closes (HECA Tai Models, measured 2026-08-11): four flat
# pads 11-18 m BELOW their own ground (building172 −10171, 14,672 m² at
# 86.71 m over 104.7 m DEM; 176 −10174; 177 −10175; 186 −10184) whose
# footprints are pack OBJECT rings — apron slabs, jersey barriers, fuel
# trucks and buses — with ZERO OSM buildings under them.  Nothing in the
# admission chain asked whether a BUILDING was there: 25 m solid reach
# admitted them, the 2 m gap bridge and 110 m outline fill in
# ``terminals.py`` fused them, and ``PAD_HOST_PAVEMENT_LEVEL``
# (untouched — correct for real pads) dropped them to the host apron
# median.
DSF_OBJECT_BUILDING_EVIDENCE = (
    _os.environ.get("O4_DSF_OBJECT_BUILDING_EVIDENCE", "1") == "1")

# ── SCOPED NAME-VOUCHING FOR THE TWO HULL FLOORS (r18b, PARKED OFF) ──
# The floors in ``object_footprints.structure_ring`` yield to a resource
# that NAMES itself a building.  Two predicates exist for that:
#
#   OFF (default, shipped): the WIDE path-anywhere match — "hangar" /
#       "term_building" / "/terminal" anywhere in the resource path.
#       HECA's Tai Models pack files its whole airport (apron slabs,
#       jersey barriers, jet-blast fences) under ``Airport/Hangar_Tower/``
#       and ``Airport/Hangar/``, so 667 of its 817 rings vouch on a
#       DIRECTORY name and BOTH floors are disabled across the pack —
#       the deeper cause of the phantom pads (building176's seed ring
#       measures hull fill 0.00036 against the 0.1 floor and is kept).
#   ON: ``object_footprints.evidence_name_vouches`` — basename, or a
#       stock-library virtual path (``lib/airport/…/hangars/…``, the CYXY
#       2026-07-28 case).  ONE predicate with the R18-2 evidence gate.
#
# WHY IT IS PARKED OFF (r18b STOP, 2026-08-12).  ON is measured CORRECT
# on population (HECA 817 → 210 rings, 215 → 73 building pads) and makes
# the HECA build REFUSE ``assert_no_final_band_inversion``: 680 of 4,792
# band-covered nodes, worst pair 05C/23C 110.6100 (law 110.6131) against
# 05L/23R 61.2800 (law 60.9778) — a 49.6353 m law-line spread over a
# 47.5591 m route budget, 2.0762 m short.  A default-ON change may not
# refuse a battery airport (``lateral_spine_nodes.py:150-154``), and the
# remedy the r18b spec named (runway_redistribute's relax-don't-drop) is
# measured INERT for it: every refused flex bin reports "relax allowed
# 0.000 m", 05C/23C's flex is fully converged (drained 126.41 m,
# residual 0.00 m) and 40 flex rounds instead of 12 leave its binding
# anchor at 110.6100 unchanged while the inversion grows (680 → 752
# nodes, worst 1.7709 → 2.0009 m).  So the substitution parks here with
# its STOP report instead of landing default-ON.
DSF_OBJECT_NAME_VOUCH_SCOPED = (
    _os.environ.get("O4_DSF_OBJECT_NAME_VOUCH_SCOPED", "0") == "1")

# What makes a member resource BUILDING-TALL for the vertical test: its
# OWN above-grade vertical extent (the A11 clamp applied per member — a
# 3.9 m drainage pit and a 3.9 m wall are not the same evidence).
#
# 6.0 m IS MEASURED, not chosen (HECA Tai Models, 2026-08-11,
# tools/object_pad_evidence_report.py over the pack's 817 emitted rings
# / 10,746 structures).  The per-member above-grade extents separate
# into a ground-furniture class and a building class with a real gap:
#
#   3.00 m  the barrier / strip class (metal_strip_2.obj and siblings,
#           an exact manufactured height repeated across the field)
#   4.53 m  tallest slab/vehicle-class member measured
#   5.87 m  jet_Blash_02.obj x60 — the JET BLAST DEFLECTORS, the tallest
#           non-building structure on the field
#   ────────────────── the gap ──────────────────
#   6.09 m  Private_hall/palm.obj, 6.10 m interior_glass.obj — building
#           interior members
#   7-113 m every real terminal shell
#
# The four phantom pads' rings top out at 2.85-5.36 m; every real
# terminal shell reaches 6.1 m or more.  Raise it and single-storey
# buildings start falling through to the OSM half; lower it and the
# jet-blast fences vouch themselves.  0 disables the height test.
DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M = float(
    _os.environ.get("O4_DSF_OBJECT_EVIDENCE_MIN_HEIGHT_M", "6.0"))

# How much of the structure's own footprint hull those building-tall
# members must cover.  ARMED AT 0 (= no coverage floor) BY MEASUREMENT,
# and the measurement is the point: a material-split pack authors one
# terminal as a stack of per-material thin wall/strip objects, so its
# TALL members cover 0.000-0.02 of the fused hull — the SAME range as
# the phantom slab class (HECA 2026-08-11: a 22,743 m² ring with a
# 14.98 m member measures 0.0020, a 31,184 m² ring with a 10.81 m
# member 0.0004, while the phantom 61,481 m² ring measures 0.0000).
# Any floor that catches the phantoms deletes the real terminals; the
# HEIGHT does the separation alone.  The coverage-shaped defence is
# already carried, upstream and as a refusal, by
# ``DSF_OBJECT_MIN_TALL_BASE_FILL`` (the plate+mast weld class — 188
# HECA structures refused there before this gate is reached).
# A pack that needs the floor arms it here; it stays a floor on the
# EVIDENCE, never a refusal — a structure below it falls through to
# evidence source (a) and needs an OSM building under it.
DSF_OBJECT_EVIDENCE_MIN_COVERAGE = float(
    _os.environ.get("O4_DSF_OBJECT_EVIDENCE_MIN_COVERAGE", "0.0"))

# (20260708) DSF OBJECT RE-ANCHOR (user 2026-07-08, rulings R1 + R2):
# post-mesh, rewrite the ``y`` column of each structure's vertices by
# ``ground_under(structure) - ground_under(anchor of its own object)`` so
# every structure sits on its own terrain (the offset is per
# (structure, object) pair — spec section 2.4).  Writes IN PLACE into the
# scenery pack, keeping ``<name>.anchor_bak`` originals; geometry is
# always re-read from the backup, so the operation is byte-idempotent and
# cannot stack.  Re-runs after every mesh build (the offsets encode one
# specific built mesh).  Corrected packs MUST NOT be redistributed.
# DEFAULT ON after the three-pack verification (2026-07-08);
# O4_DSF_OBJECT_REANCHOR=0 leaves every pack byte-identical.
DSF_OBJECT_REANCHOR = _os.environ.get("O4_DSF_OBJECT_REANCHOR", "1") == "1"

# Phase 2 worklist pack scan (driver): a scenery pack qualifies for an
# airport when its tile DSF places at least one ``.obj`` OBJECT within
# the airport's CIFP-threshold bounding box expanded by this margin.
# Object discovery is independent of the apt.dat geometry contest (field
# case LSGL 2026-07-23: the custom pack lost the apt.dat contest to
# Global Airports and its objects were never re-seated).  Thresholds
# bound only the runway ends, so the margin must reach the terminal /
# apron clusters where custom objects actually stand; a too-large value
# merely queues a neighbouring airport's pack, which costs one redundant
# (tile-wide-deduped, pack-wide anyway) rebake pass, never correctness.
DSF_OBJECT_WORKLIST_BBOX_MARGIN_M = float(
    _os.environ.get("O4_DSF_OBJECT_WORKLIST_BBOX_MARGIN_M", "3000"))

# Objects containing ``ANIM_begin``: a per-structure offset applied
# inside an animation block can break its rotation pivot.  ON (default,
# owner 2026-07-24) gives each animation block the single offset of the
# structure containing its geometry; a block whose vertices span
# structures with differing offsets still refuses the object (I-11).
# OFF refuses (and reports) every object containing ``ANIM_begin``.
DSF_OBJECT_ALLOW_ANIM = (
    _os.environ.get("O4_DSF_OBJECT_ALLOW_ANIM", "1") == "1")

# Detector floor.  A compact, correctly anchored object has a solid reach
# of a few metres; 57 of KCLT's 334 definitions exceed 25 m.
DSF_OBJECT_MIN_REACH_M = float(
    _os.environ.get("O4_DSF_OBJECT_MIN_REACH_M", "25"))

# Contact tolerance for the structure partition AND the pooling margin
# (amendment A10): two parts whose surfaces come within this distance are
# one structure.  This is a modelling tolerance — "how large a gap did
# the modeller leave between a wall and its roof" — not a
# building-separation heuristic.  Workstream W2's audit showed the count
# IS epsilon-sensitive under the narrow phase (KCLT: 0.02 m -> 890
# structures, 0.25 m -> 220, 1.0 m -> 175); 0.25 m is the knee of that
# curve, with zero hard tears throughout.
DSF_OBJECT_CONTACT_EPSILON_M = float(
    _os.environ.get("O4_DSF_OBJECT_CONTACT_EPSILON_M", "0.25"))

# (amendment A11, from the HECA Tai Models pack) A building has walls; a
# ground plate, sign or decal does not.  A structure whose vertical
# extent is below this contributes NO Phase-1 building pad (Phase 2
# still y-bakes it — a mis-elevated ground plate is exactly a float/sink
# artifact).  HECA's ``heca_ground_polygon.obj`` spans 2.1 km and must
# never become a 2 km flat pad.  0 disables the filter.
DSF_OBJECT_MIN_BUILDING_HEIGHT_M = float(
    _os.environ.get("O4_DSF_OBJECT_MIN_BUILDING_HEIGHT_M", "2.5"))

# Vertices within this height of a structure's own base form its
# footprint; above it, roof overhang would inflate the pad.
DSF_OBJECT_FOOTPRINT_HEIGHT_M = float(
    _os.environ.get("O4_DSF_OBJECT_FOOTPRINT_HEIGHT_M", "1.5"))

# A structure whose lowest vertex sits above this rests on something
# else — rooftop clutter, a canopy, a jetbridge.  It contributes no
# footprint; if the contact graph left it unattached, it inherits the
# offset of the ground-touching structure supporting it.
DSF_OBJECT_ELEVATED_BASE_M = float(
    _os.environ.get("O4_DSF_OBJECT_ELEVATED_BASE_M", "0.5"))

# Skip-and-report a footprint larger than this rather than laying a flat
# pad across half an airfield.  KCLT's terminal complex is 112,230 square
# metres — spec section 2.3.  0 disables the cap.
#
# BACKSTOP DEFAULT 100,000 m² (defect 2026-07-17, UK payware co-baked
# airports): the connector pre-filter and the structure span gate stop
# fences/roads/slabs from chaining real buildings into one field-spanning
# mega-pad, but this area cap is the final net that keeps any residual
# giant hull out of the building pool (its hull would otherwise CANNIBALISE
# the real building pads it overlaps — EGGW dropped from 39 real DSF
# buildings to 10 as two mega-hulls swallowed them).  100,000 keeps EGGW's
# legitimate largest concourse (measured well under this — see the defect
# probe) with generous margin while dropping the airport-sized hulls.
DSF_OBJECT_MAX_FOOTPRINT_AREA_M2 = float(
    _os.environ.get("O4_DSF_OBJECT_MAX_FOOTPRINT_AREA_M2", "100000"))

# ── DSF OBJECT PAVEMENT (user 2026-07-17, HECA Tai Models) ──
# Ground-paint packs draw base pavement as DRAPED-ONLY ``.obj`` files —
# one placement carrying the whole airport's geometry for one texture
# (HECA ``Airport/ground/asphalt.obj``: 31k draped vertices, zero solid
# triangles).  Such objects never enter the building path (no solid
# geometry) and never entered the pavement union either, so
# adjacent-ground bands marched through what the sim shows as
# mid-taxiway asphalt.  When ON, ``dsf_reader.read_dsf_object_pavements``
# admits an object as PAVEMENT when it is draped-only AND declares
# ``ATTR_layer_group_draped`` in group runways/taxiways at an offset no
# greater than DSF_OBJECT_PAVEMENT_MAX_LAYER_OFFSET — the base-pavement
# draw layer; markings, taxi lines, and gate signs sit in group
# ``markings`` or at higher offsets (HECA survey 2026-07-17: base
# asphalt/concrete all at ``runways 1``, every decal at ``markings *``
# or ``runways 2..5``) — AND carries no decorative name token.  The
# draped triangles are unioned into pavement patches (all disjoint
# patches kept, holes honoured) that join the DSF pavement sweep under
# the SAME distance/boundary/overlay gates as ``.pol`` pavement, marked
# third-party.  DEFAULT ON (owner 2026-07-18, for in-sim testing).
# HECA A/B (law-true, axes sidecar): +4.05 km2 real ground-paint
# pavement, inert at every non-HECA fixture pack; within-shape 30→3
# (fixes 27/30 standing terminal-frontage flags); residuals = 3 skirt
# + 6 tears + 3 cross + 55 mid-edge (junction/skirt lawfully meeting
# low terrain beside the preserved runway datum) + ~311 perimeter
# retaining walls awaiting the owner's in-sim verdict.  The one
# genuine regression this coverage exposed — MID final-projection
# writeback aliasing re-stamping the runway blast-pad corner — is
# FIXED (runway profile preserve now unconditional in
# ``final_grade_projection``).  O4_DSF_OBJECT_PAVEMENT=0 restores the
# prior behaviour.
DSF_OBJECT_PAVEMENT = (
    _os.environ.get("O4_DSF_OBJECT_PAVEMENT", "1") == "1")
DSF_OBJECT_PAVEMENT_MAX_LAYER_OFFSET = int(
    _os.environ.get("O4_DSF_OBJECT_PAVEMENT_MAX_LAYER_OFFSET", "1"))
# Patches below this metric area are dropped — texture-page unions shed
# sliver fragments (isolated decal quads, seam slivers) that would bloat
# the pavement pool with noise.
DSF_OBJECT_PAVEMENT_MIN_PATCH_M2 = float(
    _os.environ.get("O4_DSF_OBJECT_PAVEMENT_MIN_PATCH_M2", "20"))
# VEHICLE-PAVEMENT admission filter (owner direction 2026-07-18, HECA
# Tai Models): ground-paint packs paint the airport's SERVICE-ROAD grid
# and drainage channels at the same base layer as the real asphalt
# (HECA road.obj: one 165,820 m2 connected patch spanning 2.7 x 7.4 km
# at ~6 m corridor width — ~27 km of road).  Admitted into the pavement
# union those corridors can only classify as junction/apron (no taxi or
# 1206 route rides them) and drag miles of 1 %-capped airside pavement
# across open terrain (HECA retaining walls 21→332).  Aircraft-capable
# pavement is essentially everywhere wider than any vehicle road; the
# test is a MORPHOLOGICAL OPENING RATIO, not erosion-to-empty: a road
# NETWORK patch has occasional wide pockets (intersections, small
# plazas) that survive plain erosion, so the whole connected snake
# passes an ``is_empty`` test (measured: HECA road.obj kept its
# 165,820 m2 patch on erosion alone).  ``buffer(-w/2).buffer(+w/2)``
# recovers the aircraft-capable cores at full extent; the surviving
# area fraction separates cleanly at HECA (vehicle/drainage <= 0.29,
# real pavement >= 0.37 with the bulk >= 0.96), so 0.35 sits in the
# gap.  A low-ratio patch is vehicle/drainage paint and is dropped at
# ADMISSION (before the union, so it never costs slice/weld/solve
# work; it simply rides the DEM the way the pack renders in stock
# X-Plane).  11 m sits above painted roads (~6 m) and drainage
# (~10 m) and below any real taxiway-with-shoulders at packs of this
# class.  Applies to OBJECT-sourced patches only (apt.dat / ``.pol``
# pavement untouched).  Width 0 disables.
DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M = float(
    _os.environ.get("O4_DSF_OBJECT_PAVEMENT_MIN_AIRCRAFT_WIDTH_M", "11"))
DSF_OBJECT_PAVEMENT_OPENING_RATIO = float(
    _os.environ.get("O4_DSF_OBJECT_PAVEMENT_OPENING_RATIO", "0.35"))
# SHOULDER readmission (owner in-sim report 2026-07-18, HECA round 2):
# ground-paint packs also paint taxiway SHOULDERS as narrow strips, and
# the width test alone reads them as vehicle pavement — dropped, they
# ride the DEM and mint sharp protrusions against the graded taxiway
# beside them.  A shoulder is distinguishable from a road by EDGE
# CONTACT: it abuts the pavement it serves for its whole run, so its
# shared-boundary length is ~its own long side (ratio ~1.0, ~2.0 when
# sandwiched between two pavements), while a road/offset strip only
# meets pavement at crossings (measured HECA: roads <= 0.32, abutting
# strips >= 0.58).  A vehicle-classified patch with contact ratio at or
# above this threshold is READMITTED to the pavement union (absorbed as
# airside shoulder; its grade is anchored by the pavement it abuts).
# See object_footprints.abutting_contact_ratio.
DSF_OBJECT_PAVEMENT_SHOULDER_CONTACT_RATIO = float(
    _os.environ.get("O4_DSF_OBJECT_PAVEMENT_SHOULDER_CONTACT_RATIO", "0.5"))

# ── CONNECTOR pre-filter (defect 2026-07-17, UK payware co-baked airports) ──
# A scenery pack that bakes a whole airport as many ``.obj`` files sharing
# one anchor includes CONNECTOR meshes — perimeter fences, road/rail
# networks, whole-complex ground slabs — whose base geometry touches
# (within DSF_OBJECT_CONTACT_EPSILON_M) every real building.  Left in the
# pool they chain all the buildings into one connected structure whose
# convex hull fills the field, burying the real buildings and the
# below-grade tunnels (EGGW building1 = 2,814,841 m²; EGLL T5 = 537,939 m²;
# EGLL's Airport/Tunnel/8.obj + 8a.obj were pooled into the T2_3 pad).
# A resource is a CONNECTOR — excluded from building pooling/partitioning
# BEFORE weld/contact so it cannot chain components — only when BOTH its
# footprint span (max bbox side of its solid geometry) exceeds
# DSF_OBJECT_CONNECTOR_SPAN_M AND its hull-fill ratio (horizontal
# solid-triangle area ÷ convex-hull area) is below DSF_OBJECT_CONNECTOR_MAX_FILL.
# A large but FILLED footprint (a real mega-terminal) fails the fill test
# and is kept.  See ``object_anchor.is_connector_resource``.  The 300 m
# span floor sits far above any single building or the ~50 m KBNA gantry
# (the multi-foot re-anchor's motivating structure), which must never be
# caught.  Lower the span at your own risk — nothing below ~150 m without
# an owner ruling.
#
# DEFAULT OFF (defect 2026-07-17, verification finding — owner ruling
# pending): a PER-OBJECT span+fill test cannot separate a true bridging
# connector from a co-baked building part.  UK payware packs (EGGW/EGLL)
# bake the whole airport as many texture-page ``.obj`` files that each
# span the field with near-zero horizontal fill (walls are vertical, so
# their footprint projection is ~0), so the pre-filter excludes the real
# building geometry: EGGW dropped from 39 → 6 DSF buildings, EGLL 216 →
# 128, both with the pre-filter on.  The STRUCTURE span gate
# (DSF_OBJECT_MAX_STRUCTURE_SPAN_M) is the sound per-STRUCTURE equivalent
# — it drops the field-spanning CHAINED structure regardless of which
# object bridged it, leaving the real buildings (separate components)
# intact — and with the area backstop it meets the whole acceptance on
# its own.  Set O4_DSF_OBJECT_CONNECTOR_PREFILTER=1 to evaluate the
# per-object pre-filter.
DSF_OBJECT_CONNECTOR_PREFILTER = (
    _os.environ.get("O4_DSF_OBJECT_CONNECTOR_PREFILTER", "0") == "1")
DSF_OBJECT_CONNECTOR_SPAN_M = float(
    _os.environ.get("O4_DSF_OBJECT_CONNECTOR_SPAN_M", "300"))
DSF_OBJECT_CONNECTOR_MAX_FILL = float(
    _os.environ.get("O4_DSF_OBJECT_CONNECTOR_MAX_FILL", "0.20"))

# ── Structure span gate (same defect) ──  A partitioned structure whose
# footprint-ring span (max bbox side) exceeds this is not a building-pad
# seed — skipped-and-reported through the same path as the area cap.  0
# disables it (the ``MAX_``-cap convention shared with the area backstop).
#
# DEFAULT OFF (0) (defect 2026-07-17, verification finding — owner ruling
# pending): at 500 m this gate ALSO removes a real terminal whose convex
# hull is inflated past the threshold — SPJC's ``terminal.obj`` +
# ``terminal_banner.obj`` span 560 m (the banner sign sits far from the
# terminal), so a 500 m gate dropped the terminal pad and opened 15 grade
# steps at SPJC (a clean airport otherwise).  The AREA BACKSTOP alone
# removes every airport-sized mega hull (all ≫ 100,000 m²: EGGW 2.0 M /
# 1.5 M, EGLL 537 k / 368 k / 355 k, HECA 1.9 M, SPJC LIMANUEVA 371 k) and
# keeps every real terminal, so it meets the whole acceptance on its own
# and leaves SPJC's grades at zero.  The span gate only helps against a
# residual SUB-backstop long/thin field-spanner (HECA has a 45,803 m² /
# 601 m one) — but it cannot tell that from a real 560 m terminal by span
# alone.  Set O4_DSF_OBJECT_MAX_STRUCTURE_SPAN_M=500 (or higher, to clear
# real terminals) to evaluate it.
DSF_OBJECT_MAX_STRUCTURE_SPAN_M = float(
    _os.environ.get("O4_DSF_OBJECT_MAX_STRUCTURE_SPAN_M", "0"))

# (amendment A3) A baked structure whose ground elevation span across its
# ground-touching parts exceeds this is still baked with the best single
# offset, but reported ``needs_pad`` — one rigid offset cannot seat it,
# and a Phase-1 building pad is the actual fix (spec section 7.3).
DSF_OBJECT_PAD_FLAG_SPAN_M = float(
    _os.environ.get("O4_DSF_OBJECT_PAD_FLAG_SPAN_M", "2"))

# A structure whose terrain variation under its ground-contact parts
# exceeds this cannot be seated by one rigid vertical offset — one end
# floats or sinks by more than the seating tolerance no matter where the
# single offset lands.  Such structures stay at their AUTHORED elevations
# (their real buildings are carried by Phase-1 pads instead, where the
# terrain meets each building).  This is the per-STRUCTURE guard that
# stops a co-baked payware pack's connector chain (perimeter fences,
# parked-car texture fields) from dragging a whole airport-scale contact
# component to one wrong offset — the EGGW UK2000 pack chained 55 and 44
# real buildings into components spanning 38.2 m and 26.3 m of terrain,
# each of which a single rigid offset floated by tens of metres.  Distinct
# from DSF_OBJECT_PAD_FLAG_SPAN_M, which only FLAGS a still-baked
# structure; past this larger limit the structure is not baked at all.
DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M = float(
    _os.environ.get("O4_DSF_OBJECT_BAKE_MAX_GROUND_SPAN_M", "3.0"))

# ── The reseat threshold ──────────────────────────────────────────────
# (docs/specs/object-reseat-threshold-spec.md section 2.1, owner charter
# 2026-08-09, verbatim: "When it's less than a meter deviation, adapt the
# terrain to the custom objects, rather than reseating the objects.  We
# prefer not to modify an airport if we don't have to.  If it has objects
# that deviate more than a meter, then we will need to reseat them.")
#
# A SEATING UNIT — a cluster on the default path, a structure on the
# non-clustered path, a foot-anchored structure's fitted rigid offset —
# is baked into the pack only when its required correction REACHES this
# threshold:
#
#     bake(unit)  <=>  max over the unit's resources of |delta| >= this
#
# The MAX, not the mean: a unit is one rigid body, so baking some members
# and not others would tear it — one member needing a metre reseats the
# whole unit, and a unit whose every member is under a metre stays
# entirely at its authored elevations while the terrain comes to it
# (DSF_OBJECT_NOBAKE_PAD_FLOOR_M below).  Deviation is measured in
# AUTHORED space (geometry always re-read from the ``.anchor_bak``
# originals, invariant I-15), so the decision is stable across rebuilds:
# an already-baked pack presents the same deltas next run.
#
# Measured at OTHH (2026-08-09 recon): 1,210 of 1,421 pack ``.obj`` files
# carry bakes today, and the reconstructed |delta| over the 774 measurable
# clusters runs p50 0.51 m with at least 74 % under 1 m — the population
# this threshold hands to the terrain side instead of rewriting.  Terrain
# classes (owner correction 2026-08-09, spec section 2.4): OTHH is VERY
# FLAT and is the airport expected to approach zero pack modification;
# KCLT and KBNA sit in HILLY terrain, so their sub-1 m units stop baking
# while their >= 1 m units keep reseating — an unmodified pack is not
# expected there.  0 disables the threshold: every non-zero delta bakes,
# which is byte-for-byte the pre-2026-08-09 behaviour (spec section 5's
# degeneracy gate, and what the older seating witnesses are written
# against).
DSF_OBJECT_BAKE_MIN_DELTA_M = float(
    _os.environ.get("O4_DSF_OBJECT_BAKE_MIN_DELTA_M", "1.0"))

# The materiality floor for the pad requests a BELOW-THRESHOLD unit
# raises (spec section 2.2).  Such a unit is never moved, so its ground
# contacts are routed to the pad system instead of the pack: a contact
# group whose |residual| against the authored, as-draped base is under
# this floor raises no request at all — sub-15 cm float or sink is below
# the visible-seam scale and the mesh quantum, and adapting terrain to it
# would be churn.  Distinct from DSF_OBJECT_FOOT_PAD_RESIDUAL_M (0.75 m),
# which continues to govern the post-seat residuals of BAKED units: a
# baked unit has already spent its rigid correction, so only a coarser
# residue is worth terrain; an unbaked unit has spent nothing, and the
# whole point of leaving it alone is that terrain closes the gap.
# (Owner may tune — spec open question Q-A.)
DSF_OBJECT_NOBAKE_PAD_FLOOR_M = float(
    _os.environ.get("O4_DSF_OBJECT_NOBAKE_PAD_FLOOR_M", "0.15"))

# ── Per-cluster object seating ────────────────────────────────────────
# (docs/specs/per-cluster-object-seating-spec.md, owner ruling R1
# 2026-07-26.)  A heavy payware pack welds its whole terminal complex
# into ONE km-scale contact component; on flat ground (KCLT 0.022 m /
# KBNA 0.005 m of ground-contact relief) that is harmless, but at HECA
# the same topology sits on 26 m of REAL relief and the rigid-seat limit
# above refuses the lot — 385 objects, 6,339 supporter-inheritors, the
# whole Tai Models terminal complex left at authored elevations.  The
# fix is to stop pretending the mega-structure is one rigid body: it is
# many rigid bodies (CLUSTERS) joined at contact edges where the ground
# steps.  With this gate on, ``object_anchor.structure_deltas`` cuts the
# ground-to-ground contact edges whose two ends want seats more than
# DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M apart and seats each remaining
# connected component on its own median ground (spec sections 3.2, 4.1).
# OFF restores per-structure seating byte for byte.  Spec section 7.1
# landed this gated off pending the owner's verdict; the owner ruling
# 2026-07-27 ("all the buildings and big terminals that actually touch
# airside, many are still floating, some by a lot, we have to find a
# way to get them down, even if we have to remove things like the rail
# connector between terminals") IS that verdict — default ON.  Measured
# at flip time: HECA skipped structures 6,386 → 41, Private Hall worst
# float +31.8 → +5.7 m, road_train reported as a bridge; KCLT a strict
# improvement (worst 23.7 → 4.5 m).  ``O4_OBJECT_CLUSTER_SEATING=0``
# reverts.
DSF_OBJECT_CLUSTER_SEATING = (
    _os.environ.get("O4_OBJECT_CLUSTER_SEATING", "1") == "1")

# The cut tolerance T (spec section 3.3).  A ground-to-ground contact
# edge is CUT when the two ends' seat targets — ``ground_under(part) −
# base_y(part)``, the y = 0 elevation that lands each end exactly on the
# mesh — differ by more than this.  Measured on HECA structure 0's 1,634
# ground-to-ground contacts: |Δseat| p50 0.006 / p90 0.258 / p99 1.60 /
# max 4.13 m.  T = 0.05 cuts 38 % of edges (shredding the structure);
# T = 0.5 cuts 3.6 % — exactly the genuine relief transitions, well
# above the modelling-noise shoulder and well below the zone steps.  It
# is also one stair riser plus margin, the scale a seam at a facade base
# reads as deliberate.  0 disables clustering (same as the gate off).
# Guard (spec section 3.3): T must exceed the contact epsilon — a
# tolerance below the modelling gap it partitions across would be
# self-inconsistent.
DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M = float(
    _os.environ.get("O4_DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M", "0.5"))
assert (
    DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M == 0.0
    or DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M > DSF_OBJECT_CONTACT_EPSILON_M
), (
    "DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M must exceed "
    "DSF_OBJECT_CONTACT_EPSILON_M (spec section 3.3 guard)"
)

# (spec section 5.1 clause 1, owner ruling R2: "as close as feasible to
# DEM, then some adjustment to terrain is acceptable".)  A requested
# building pad may deviate from the mesh by at most this; a residual
# group needing more is still RECORDED, flagged over-cap, and reported
# as a finding rather than silently promising terrain nobody will build.
# 3.0 m inherits the rigid-seat limit's scale.
DSF_OBJECT_PAD_MAX_RELIEF_M = float(
    _os.environ.get("O4_DSF_OBJECT_PAD_MAX_RELIEF_M", "3.0"))

# THE PAD EMISSION GATE (per-cluster-object-seating-spec section 5.4 +
# object-reseat-threshold-spec section 2.3).  With this on, the auto-patch
# phase derives building pads IN-RUN from the object pad frame
# (``object_frame`` / ``post_mesh.pad_frames_from_worklist``) and this
# build's own solved patch (``patch_ground``), and emits ``object_pad``
# terrain under them; with it off nothing is derived or emitted and the
# patch is byte-identical to a pre-feature build.
#
# THE CONSUMER FRAMING IS RETIRED (RULINGS "OBJECT PADS: EMISSION-TIME
# RELATIVE", owner 2026-08-14).  This used to be the gate on READING the
# tile's ``o4_object_foot_pads.json`` request sidecar — the cross-build
# read-back that made a pad the product of the PREVIOUS build's mesh.  No
# terrain path reads that file any more; it is the y-bake's write-only
# audit trail.  What the flag gates is emission, and only emission.
#
# DEFAULT ON (object-reseat-threshold-spec section 2.3): the parent spec
# held it off pending an owner in-sim verdict, and the owner's 2026-08-09
# charter — "adapt the terrain to the custom objects, rather than
# reseating the objects" — IS that verdict.  The env kill switch stays.
DSF_OBJECT_OBJECT_PADS = _os.environ.get(
    "O4_DSF_OBJECT_OBJECT_PADS", "1") == "1"

# DEFECT A, MEASURED AND NOT LANDED (2026-07-26).  The limit above is a
# max-min statistic that pre-empts the amendment-A3 arithmetic: a
# structure whose A19 median seat would be a large A3 improvement is
# refused unheard (HECA structure 0: authored ground-part residuals
# median 3.089 m against 0.450 m at the median seat, over 1,821 parts).
# A "robust seat gate" — put every over-span structure to the A3 test
# and bake it when the median seat strictly improves the MEAN residual —
# was implemented and dry-run, and it FAILED its EGGW stop condition:
# all three UK2000 over-span components bake under it, including the
# 662,669 m2 / 9.39 m-span mega component the owner verified in-sim must
# skip, which the mean test accepts on a 0.025 m margin (2.0167 ->
# 1.9919 m) while its residual MEDIAN gets worse (1.854 -> 2.017 m) and
# its worst part goes 5.33 -> 5.78 m.  Any future version of this fix
# needs a test the EGGW components fail — a median/quantile criterion,
# a worst-part cap, or per-cluster seating
# (docs/specs/per-cluster-object-seating-spec.md) — not the A3 mean.

# (2026-07-26, HECA "a ton of floating objects" tear diagnosis) OUTCOME
# CONSISTENCY between a supporter and the structures that inherit its
# ground.  An elevated structure with no ground-touching part of its own
# takes its seating elevation from a SUPPORTER (invariant I-8) — but the
# supporter itself may be left at its authored elevations (the rigid-seat
# span limit above, or any other skip).  Baking the inheritor while its
# supporter does not move is the worst of both worlds: at HECA the Tai
# Models pack's structure 0 (a 1237 x 2480 m, 16,868-part mega-structure
# with a 25.8 m ground span) span-skipped and stayed put, while the 8,102
# elevated structures whose centroids land in its bounding box were baked
# -2.00 .. -2.45 m relative to it — signage, roof clutter and fittings
# sunk through parents that had not moved.  With this gate on, an
# inheritor SHARES ITS SUPPORTER'S FATE: a skipped supporter leaves its
# inheritors at their authored elevations too, with a counted
# ``skip_reason`` naming the parent's reason.  It deliberately does NOT
# re-home them (that is DSF_OBJECT_SUPPORTER_SMALLEST below) and does NOT
# change which structures the span limit itself skips.
# ``O4_SUPPORTER_FATE=0`` restores the pre-fix behaviour byte for byte.
DSF_OBJECT_SUPPORTER_FATE = (
    _os.environ.get("O4_SUPPORTER_FATE", "1") == "1")

# (2026-07-26, defect B — the size guard the supporter-fate note above
# deferred) WHICH containing structure an elevated structure inherits
# from.  Invariant I-8 picks a ground-touching structure whose plan
# bounding box contains the inheritor's centroid; the original code took
# the FIRST such candidate in structure-index order, which is an
# arbitrary choice whenever boxes nest.  Payware mega-structures are
# partitioned early (HECA's Tai Models terminal web is structure 0, a
# 1237 x 2480 m box), so "first in index order" systematically hands
# every nested inheritor to the largest possible parent: at HECA
# structure 0 claimed 8,102 inheritors, and for 1,761 of them a SMALLER
# containing ground-touching structure — the building they actually sit
# on — existed and was ignored.  With this gate on the supporter is the
# SMALLEST containing ground-touching structure by plan bounding-box
# area, ties broken by lowest structure index (determinism).  A tighter
# box is a strictly better statement of "what this thing rests on", and
# with DSF_OBJECT_SUPPORTER_FATE the re-homed inheritors follow their
# NEW supporter's fate — at HECA that moves 1,761 structures off the
# span-skipped mega-structure onto supporters that actually bake.
# ``O4_SUPPORTER_SMALLEST=0`` restores first-containing-in-index-order
# byte for byte.
DSF_OBJECT_SUPPORTER_SMALLEST = (
    _os.environ.get("O4_SUPPORTER_SMALLEST", "1") == "1")

# ── Multi-ground-cluster (foot) re-anchor ─────────────────────────────
# An author-BAKED vertical offset (the KBNA water-treatment stairs carry
# their lowest solid vertex at local y = +6.5 m) defeats the absolute
# DSF_OBJECT_ELEVATED_BASE_M test: the structure is classified as
# rooftop clutter, inherits a neighbour's offset, and every seating path
# — including the audit — is blind to it.  The foot re-anchor detects
# such a structure's ground-contact FEET relative to its own lowest
# band and seats the best rigid offset across all of them (project
# memory kbna-gantry-pond-multi-foot-objects).
DSF_OBJECT_FOOT_ANCHOR = (
    _os.environ.get("O4_DSF_OBJECT_FOOT_ANCHOR", "1") == "1")

# Reduced Phase 2 discovery reach floor for BAKED-OFFSET geometry
# (lowest solid vertex above DSF_OBJECT_ELEVATED_BASE_M).  The standard
# DSF_OBJECT_MIN_REACH_M floor exists because a compact, correctly
# anchored object is X-Plane's business — but a baked vertical offset
# breaks that premise: X-Plane puts the object's y = 0 plane at the
# terrain under its anchor, so the baked base floats or sinks by the
# author-mesh/our-mesh difference no matter how compact the object is.
# The KBNA stairs reach 24.3 m and 20.6 m — under the 25 m floor.
DSF_OBJECT_FOOT_MIN_REACH_M = float(
    _os.environ.get("O4_DSF_OBJECT_FOOT_MIN_REACH_M", "15"))

# A vertex belongs to a foot's contact band when it lies within this of
# the LOCAL minimum in its own horizontal neighbourhood (the
# neighbourhood radius is DSF_OBJECT_FOOT_CLUSTER_GAP_M).  A global
# band fails: the 45 m KBNA stair's two feet sit 1.17 m apart in
# authored y, and the deck underside would flood a band wide enough to
# hold both.
DSF_OBJECT_FOOT_BAND_M = float(
    _os.environ.get("O4_DSF_OBJECT_FOOT_BAND_M", "0.5"))

# Contact-band vertices chain into one foot when within this horizontal
# distance AND within DSF_OBJECT_FOOT_BAND_M vertically per link — the
# vertical constraint keeps a foot from chaining up a stair stringer
# onto the deck underside.
DSF_OBJECT_FOOT_CLUSTER_GAP_M = float(
    _os.environ.get("O4_DSF_OBJECT_FOOT_CLUSTER_GAP_M", "5"))

# A cluster is a FOOT only when its base sits within this of the
# structure's own lowest solid vertex.  Measured on the KBNA stairs:
# genuine second feet at y_min + 1.17 (45 m) and y_min + 1.44 (42 m);
# the lowest mid-span deck clusters begin at y_min + 1.88.  1.65 splits
# the two populations.
DSF_OBJECT_FOOT_MAX_BASE_SPREAD_M = float(
    _os.environ.get("O4_DSF_OBJECT_FOOT_MAX_BASE_SPREAD_M", "1.65"))

# The rigid offset is fitted only over feet whose seat target (ground
# under the foot minus the foot's authored base) lies within this of
# the topmost target — a foot the author meant for terrain the mesh
# does not have (or a mis-detected cluster hanging over a pond) must
# not drag the true feet down with it.
DSF_OBJECT_FOOT_CONTACT_TOLERANCE_M = float(
    _os.environ.get("O4_DSF_OBJECT_FOOT_CONTACT_TOLERANCE_M", "1.5"))

# After the best rigid offset, a foot still off the mesh by more than
# this raises a per-foot terrain-pad REQUEST (recorded in the decision
# and the post-mesh sidecar; a rigid body cannot fix it alone).
DSF_OBJECT_FOOT_PAD_RESIDUAL_M = float(
    _os.environ.get("O4_DSF_OBJECT_FOOT_PAD_RESIDUAL_M", "0.75"))

# A requested foot pad's ring is the convex hull of the foot's contact
# points dilated by this, so the pad reaches past the very edge of the
# foot (``object_footprints.foot_pad_ring``).
DSF_OBJECT_FOOT_PAD_MARGIN_M = float(
    _os.environ.get("O4_DSF_OBJECT_FOOT_PAD_MARGIN_M", "2"))

# THE PLAN-BOX FALLBACK CAP (round-4 spec R1, 2026-08-10).  A part with
# NO triangle inside its contact band raises NO pad request: an elevated
# deck does not want terrain raised to it, and its piers belong to the
# parts that do touch ground.  The plan-box fallback survives only for
# the DEGENERATE mesh case — a part whose own base sits inside the
# contact band, whose plan box is no larger than this.  Measured on the
# owner's OTHH build: 61 fallback rings were 83 % of all pad area and
# the worst (a welded TerminalRoads mega-part, 564.8 x 534.3 m) asked
# for a 224,146 m2 pad around a pier-supported viaduct.
DSF_OBJECT_PAD_PLAN_BOX_FALLBACK_MAX_M2 = float(
    _os.environ.get("O4_DSF_OBJECT_PAD_PLAN_BOX_FALLBACK_MAX_M2", "2000"))

# (s80) Extent-based runway shoulder widening — tuning constants and
# rationale with the other RUNWAY_SHOULDER_EXTENT_* values near the
# DSF block above.  ``O4_SHOULDER_EXTENT=0`` restores the pre-s80
# build (shoulder strips carried only by DSF pavement fall into
# apron residue along the runway).
RUNWAY_SHOULDER_EXTENT = _os.environ.get("O4_SHOULDER_EXTENT", "1") == "1"

# (2026-07-17, KBNA 13/31) BORDER-STRIP-DERIVED runway shoulders.
# Construction style: the runway ships as exact-runway-width draped
# ``.pol`` pieces PLUS a wide draped ``.lin`` border traced along the
# runway's own outline — the border's outer half IS the author's
# shoulder, so the strip's declared width states the shoulder width
# EXACTLY (``width / 2`` per side; KBNA 13/31: 24 m border ⇒ 12 m
# shoulder).  When enough border arc-length runs on a runway edge, that
# per-side width wins and the runway SKIPS the extent walk below
# entirely: on a border-styled runway a side with no border evidence
# has NO shoulder (abutting taxiway pavement stays taxiway — the
# wide-biased extent clamp used to eat its ``max_w`` 15 m of taxiway
# pavement and shred the junctions along KBNA 13/31).
# ``O4_RUNWAY_BORDER_SHOULDER=0`` restores the extent-only behaviour.
RUNWAY_BORDER_SHOULDER = _os.environ.get(
    "O4_RUNWAY_BORDER_SHOULDER", "1") == "1"
# A border sample counts as "on the runway edge" within this
# perpendicular tolerance (matches _BORDER_WRAP_EDGE_TOL_M — the strip
# path traces the ``.pol`` outline, which sits within chart tolerance
# of the apt.dat rect edge).
RUNWAY_BORDER_SHOULDER_EDGE_TOL_M = 3.0
# Arc-length sampling step along each strip path.
RUNWAY_BORDER_SHOULDER_SAMPLE_STEP_M = 5.0
# A single strip must put at least this much arc-length on the edge to
# count as evidence (filters taxiway borders that merely cross the
# runway at exits).
RUNWAY_BORDER_SHOULDER_MIN_STRIP_COVER_M = 40.0
# A side qualifies when its strips jointly cover at least this much of
# the runway edge (KBNA 13/31 left: 1,485 m of 3,364; the right side's
# lone 160 m fragment stays unqualified — taxiway complexes abut there
# and the runway must not eat them).
RUNWAY_BORDER_SHOULDER_MIN_SIDE_COVER_M = 300.0

# (2026-06-27) RUNWAY-CROSSING PHYSICAL-EXTENT RECONCILIATION.
# Two passes handle a runway crossing: the geometric junction builder
# (pavement/runways.py ``_resolve_runway_crossings``) detects crossings
# from the built runway RECT polygons — which include displaced-threshold
# and blast-pad pavement — while the elevation-profile reconciliation
# (pavement/runway_segments.py) detected them from CIFP threshold-to-
# threshold centerlines.  When a crossing falls on the pavement BEYOND a
# landing threshold (displaced threshold / blast pad), the threshold-to-
# threshold centerline misses it, so the junction is built but the two
# runways' profiles are never reconciled — the junction then blends two
# disagreeing profiles into a step (CYXY 02/20 × 14L/32R: 2.2 m / 7.7%
# across a 28 m junction at the 20 end of the short crosswind runway).
# ON ⇒ the reconciliation detects crossings on the FULL pavement extent
# (apt.dat row-100 ends + blast pads, matching the rect footprint) and
# evaluates the agreed altitude by projecting onto the CIFP threshold
# segment (clamped to [0,1], so a beyond-threshold crossing resolves to
# the nearest threshold's flat blast-pad elevation).  Airports whose
# crossings are all interior (threshold-to-threshold) are byte-identical
# (clamp is a no-op there).  Env override ``O4_RW_XING_EXTENT``.
RUNWAY_CROSSING_PHYSICAL_EXTENT = (
    _os.environ.get("O4_RW_XING_EXTENT", "1") == "1")

# Spine node spacing (m) — the target spacing junction exterior edges are
# densified to (lateral_spine_nodes.densify_junction_edges).
SPINE_STEP_M = float(_os.environ.get("O4_JCT_SPINE_STEP_M", "12.0"))


# (20260618 W2) CLEAN ENFORCE BANDS — docs/grade_enforcement_plan.md.
# The legacy within-shape enforce is 3 accreted cap-projections whose
# artificial constraints (field self-anchor + corridor held-write band
# anchors + ±2.5 m movement clamp) EMPTY the feasible polytope → the
# projection stalls and FEASIBLE grade violations can never be fixed.  When
# ON, the hard band is anchored on TRUTH ONLY (runway/seam), the final closure
# box is the clean feasible band (±2.5 m fallback only where genuinely
# infeasible, so POCS can't diverge there), and terminals stay FLAT (coupled)
# but level-free.  Plain POCS then converges to ZERO on the feasible polytope:
# CYXY 17→0, SPJC airside→0; SPLP/HECA improved + bounded (their residual
# violations are genuine terrain-canyon infeasibility = the W3/W5 work).
# Default ON in dev (2026-06-18, user — for in-sim testing); set O4_W2_BANDS=0
# to restore the legacy field-anchored bands.
W2_CLEAN_BANDS = _os.environ.get("O4_W2_BANDS", "1") == "1"


# (s79) ON-PAVEMENT service-road carve — docs/service_road_carve.md.
# ★ USER RULINGS 2026-06-11: roads = apt.dat 1206 routes ONLY (no
# polygon/OSM detection); only pavement narrower than the cross-section
# cap is classified; nothing near a terminal; roads WORK LIKE TAXIWAYS
# — qualifying runs join the centerline set as ``SVC*`` refs and ride
# the single rect → junction → absorption decomposition with role
# ``service_road`` (SERVICE_ROAD_MAX_GRADE).  Independent of
# ``ENABLE_SERVICE_ROADS`` (the OSM small-road / off-pavement
# builder).  DEFAULT ON for the
# user's in-sim evaluation (2026-06-12; Steps C/D landed @b391e27 —
# CYXY roads-on 0/0/0, HECA 57/0/0 invariants held);
# ``O4_SERVICE_ROAD_CARVE=0`` restores the road-less build.
SERVICE_ROAD_CARVE = _os.environ.get("O4_SERVICE_ROAD_CARVE", "1") == "1"
# ONE LAW OBJECT PER CORRIDOR (owner ruling 2026-08-12b, "APT.DAT TRUCK
# ROUTES ARE A SERVICE-CORRIDOR SOURCE": one corridor = ONE continuous law
# object end-to-end, never fragmented per-junction axes).  ON, the grade
# graph's service half registers ONE chain per corridor course — the
# free-road-scoped subsegments are REPLACED by (never duplicated beside)
# their parent corridor, so the corridor's axis coverage has no axis-free
# gap and its profile solves as one chain.  Service centerlines are read
# only by groundside-family shapes (``grade_graph._reads_service_spines``),
# so a corridor crossing an apron never becomes that apron's spine and
# airside law is untouched.  ``O4_SERVICE_CORRIDOR_CHAINS=0`` restores the
# per-subsegment registration.
SERVICE_CORRIDOR_CHAINS = _os.environ.get(
    "O4_SERVICE_CORRIDOR_CHAINS", "1") == "1"
# FREE-END DEM TIE (owner ruling 2026-08-12b, "A ROAD'S OWN COURSE IS NEVER
# TERRACED"): a corridor end that does not terminate on pavement ties to
# ambient DEM under the road cap, and no terrace/retaining wall may cross a
# corridor's course.  ``O4_SERVICE_CORRIDOR_FREE_END=0`` restores the
# pre-ruling behaviour (walls free to cross, ends unseeded).
SERVICE_CORRIDOR_FREE_END = _os.environ.get(
    "O4_SERVICE_CORRIDOR_FREE_END", "1") == "1"
# CORRIDOR MOUTHS JOIN AIRCRAFT PAVEMENT (corridor-joins round, Fable spec
# 2026-08-12c ruling 1, on the owner's in-sim refutation at KCLT
# 35.213852,-80.9406291).  The minter cuts the whole corridor back from
# aircraft pavement by ``_PAV_CLEAR_TOL_M`` = 1.0 m, but conformance welds
# only within ``SHARED_VERTEX_TOL_M`` = 0.5 m — so EVERY road↔taxiway seam
# was unweldable BY CONSTRUCTION (measured gaps 0.999 m at both KCLT sites)
# and the 1 m annulus was filled by a graded_strip carrying both claims.
# ON, the minter additionally fills the annulus AT THE MOUTHS ONLY — where
# the route's own axis crosses into aircraft pavement — with fill whose
# boundary is the PAVEMENT EDGE ITSELF (difference against ``pav_union``,
# not the buffered union), so the corridor's boundary nodes land ON the
# airside edge and ``enforce_conformance`` welds them into one node.  The
# corridor BODY keeps its 1.0 m clearance everywhere else: roads still never
# overlay pavement mid-run.  THE SEAM VALUE IS THE AIRSIDE VALUE — a welded
# mouth node is a service-DEM-follow ANCHOR (it is a corner of a non-service
# pavement shape), so the road grades away from it under its own cap and the
# airside ring's solved value is never moved.
# ``O4_SERVICE_CORRIDOR_MOUTH_JOIN=0`` restores the unweldable 1 m gap.
SERVICE_CORRIDOR_MOUTH_JOIN = _os.environ.get(
    "O4_SERVICE_CORRIDOR_MOUTH_JOIN", "1") == "1"
# PROXIMITY MOUTH ANCHORS (owner law 2026-08-15: "a service road meeting a
# taxiway — or any airside pavement — must arrive AT that pavement's
# elevation, exactly like roads meeting runways"; AIRSIDE IS KING, the road
# conforms and the airside value is read-only).  The weld above closes the
# annulus only where the mouth-join minter reaches; where it does not (a
# terminus mouth, an oblique abutment, a post-solve weld-ordering gap) the
# road node abuts WITHOUT a shared vertex and the DEM-follow's anchor set —
# exact canonical vertices only — never saw it.  Measured at HECA: 34 of 60
# unwelded road<->airside contact sites stepped > 0.3 m, worst 9.135 m,
# against 0.000 m at all 127 welded ones.  ON,
# ``anchors.apply_service_road_dem_follow`` additionally anchors any service
# node within ``_PAV_CLEAR_TOL_M + SHARED_VERTEX_TOL_M`` (1.5 m — DERIVED
# from the cut-back that opens the gap plus the weld tolerance that fails to
# close it, no new number) of a non-service ring EDGE, at that edge's
# interpolated already-solved elevation; the existing reach band then ramps
# the road away under its own cap.  Exact-vertex anchors keep precedence.
# ``O4_SVC_MOUTH_PROX_ANCHOR=0`` restores the exact-vertex-only anchor set
# byte-identically.
SVC_MOUTH_PROX_ANCHOR = _os.environ.get(
    "O4_SVC_MOUTH_PROX_ANCHOR", "1") == "1"
# HARD FREE-END DEM TIE (corridor-joins round ruling 3, on the KCLT free end
# at 35.2077054,-80.9290667: the road descended 2.9 % against an 8 % cap and
# ended 6.31 m proud of DEM).  Two halves, one gate:
#   (a) the spine-first DEM-follow seeder consumes the SAME service
#       centerline set the grade graph registers (``centerline_specs`` —
#       corridor chains, feed chains included), instead of only row-1206
#       ``is_service`` entries, which feed-sourced corridors are invisible to;
#   (b) a corridor chain TERMINUS that does not land on pavement gets an
#       ANCHORED end target at ambient DEM — an anchor of the service reach
#       band (so the profile descends to it within the road cap) that is then
#       held HARD through the projections that follow, because a soft seed is
#       exactly what the measured 6.31 m residue was.
# This is R20-2's walk-to-ground law made general (RULINGS 2026-08-12b, "a
# road's own course is never terraced"): where the wall-course exclusion
# suppresses a wall, the road's own descending surface owns the level change.
# ``O4_SERVICE_CORRIDOR_FREE_END_ANCHOR=0`` restores the soft per-vertex seed.
SERVICE_CORRIDOR_FREE_END_ANCHOR = _os.environ.get(
    "O4_SERVICE_CORRIDOR_FREE_END_ANCHOR", "1") == "1"
# AIRSIDE BAND EXCLUSION AT THE POPULATION SOURCE (AMENDMENT 2, Fable lead
# 2026-08-12b, on this lane's HECA airside attribution): a SERVICE / corridor
# centerline may not weave a spine edge between two AIRSIDE nodes.  It links
# only pairs with at least one ROAD-FAMILY endpoint — which is exactly the
# MOUTH the 2026-08-06 ruling admits ("the one airside node it genuinely
# meets"), and exactly what ``_build_global_spine``'s own docstring already
# claimed the restriction did before corridors were registered end-to-end.
# ONE band law: the exclusion lives at the single population source
# (``_build_global_spine``), so ``reach_band_unified``, the raster field and
# the profile solve inherit it instead of each re-deciding.  Groundside
# corridors keep their own grading law on their own nodes.
# ``O4_SERVICE_BAND_AIRSIDE_EXCLUSION=0`` restores the pre-amendment weave.
SERVICE_BAND_AIRSIDE_EXCLUSION = _os.environ.get(
    "O4_SERVICE_BAND_AIRSIDE_EXCLUSION", "1") == "1"
# SPINE-FIRST service-road grading (USER RULING 2026-07-07, part 30m): the
# truck-route SPINE is graded at the road cap with DEM-follow as a SOFT seed
# sampled at spine stations; the EDGES follow the spine (cross-section
# derived, SERVICE_ROAD_MAX_TRANSVERSE cap), ends welded at mouths as before.
# Three coordinated touch points read this gate: (1) ``service_road`` joins
# ``grade_graph.SOFT_VISIBILITY_ROLES`` so the road gets within-shape LAW
# edges on both readers (solver graph + validator — previously ZERO edges:
# not soft, not a junction_rules sloping rect); (2) service centerlines
# insert lateral cross-section vertices on road/service-junction rings
# (``lateral_spine_nodes.insert_service_lateral_nodes``) so the law binds at
# station spacing, not just at ring corners 70-100 m apart; (3) the
# DEM-follow seed (``route_profile/anchors.apply_service_road_dem_follow``)
# is computed per spine STATION and shared by the whole cross-section
# instead of per-vertex (per-vertex let a road's two long edges bind to
# different anchor regimes — the CYXY 2.49 m cross-road tear at
# 60.7092306,-135.0738928).  Seeds are SOFT: the law edges are the
# authority and the solve remains the sole writer.  ``O4_SVC_SPINE_FIRST=0``
# restores the previous behaviour byte-identically.
SVC_SPINE_FIRST = _os.environ.get("O4_SVC_SPINE_FIRST", "1") == "1"
# BROKEN-NODE EDGE COUPLING (round-6 site-4, user 2026-07-10): when the
# feasibility projection declares a node BROKEN (the cap-Lipschitz reach
# envelope's floor > ceil — genuinely contradictory hard anchors), it drapes
# the node onto a distance-weighted blend between the contradicting anchors
# and then FREEZES it (broken nodes skip the relaxation sweeps, by design, so
# a real terrain contradiction does not smear as POCS noise).  But that blend
# never re-checks the node's OWN within-shape welded edges: at CYXY
# service_road #201 the final projection hardens the road's DEM-following
# adjacent-ground welds into a wide staircase (apron end 709.9 m down to the
# far service-junction node 705.5 m), the spine stations between them read as
# broken, and the blend drapes the CENTERLINE ~2.4 m BELOW its own edge nodes
# (which sit at 709.5 m, welded, hard) — a −55 % within-shape ravine that the
# elevation solve itself never produced (its writeback is coherent).  THE LAW
# (no shape may trench below the edges it is welded to): a broken node's
# blended value is clamped into the interval its HARD welded neighbours admit
# (∩ over hard neighbours h of [z_h − budget, z_h + budget]) whenever that
# interval is non-empty; an EMPTY interval is the genuine contradiction the
# break machinery exists for (e.g. a tile-seam pin below a plateau), so the
# blend stands untouched there — no regression to the seam/plateau blends.
# ``O4_SVC_SPINE_EDGE_COUPLE=0`` restores the pre-clamp blend byte-identically.
SVC_SPINE_EDGE_COUPLE = _os.environ.get("O4_SVC_SPINE_EDGE_COUPLE", "1") == "1"
# Max perpendicular pavement cross-section for ROAD classification.
# User rule "< 10 m"; measured at the HECA #198 switchback legs:
# 8.2-9.4 m and 12.2 m (the fused DSF pavement includes shoulder) →
# 13 m so both legs qualify (pending the user's KML verdict).
ROAD_CARVE_MAX_WIDTH_M = 13.0
# Terminal guard (refined, user 2026-06-11 round 3): drop a road sample
# near a terminal only when the route runs ALONGSIDE it (locally
# parallel within the angle below) — a road passing a terminal CORNER
# perpendicular/diagonally is a real road (HECA terminal4 → junction
# #168 section).  Terminal curbside pavement is already subtracted from
# pav_union by the groundside pass, so this is a second line.
ROAD_CARVE_TERMINAL_CLEAR_M = 30.0
ROAD_CARVE_TERMINAL_PARA_DEG = 35.0
ROAD_CARVE_SAMPLE_M = 6.0           # sampling step along 1206 routes
ROAD_CARVE_MIN_RUN_M = 20.0         # min qualifying run to become road
# Mode C (edge-hugging): a sample within this of the pavement BOUNDARY
# qualifies even when the cross-section is blended-wide — a road along
# the airside rim is "not surrounded by apron" (user round 3; HECA
# terminal-corner section gaps 4.2-8.4 m, CYXY pav[1] 1-7.4 m).
ROAD_CARVE_EDGE_HUG_MAX_M = 8.5
# (s80) ROAD-FRONTAGE GRADE LAW — a within-shape pair (apron/junction)
# whose BOTH endpoints sit within this of a service-road polygon is
# governed by the ROAD's 5 % law, not the shape's 1.5 %: the carve
# welds its corners into the host ring, so the strip alongside the
# road is physically part of the road's descent (CYXY road #30: the
# apron-ring frontage edge read the road's 2.5 % drop as a 3.13 %
# apron violation while every surface obeyed its own law; the squeeze
# is hard-anchored — runway contact 12 m below — so no legal apron
# value exists).  Mirrors the per-axis junction model: the road law
# rides ALONG the carve; pairs reaching away from it stay strict.
# VALIDATOR-ONLY (tools/check_grade._check_within_shape): the solver
# keeps fighting at the strict cap (status quo) — relaxing its edge
# caps too let road-welded rims sag with the road and broke 1.5 %
# pairs against strict nodes just OUTSIDE the zone (HECA apron #258
# grew a 3 m pit, pairs 5-8 %; measured s80) — the in-zone/out-zone
# transition needs a taper before the solver may use this law.
ROAD_FRONTAGE_TOL_M = 3.0
# … but NOT the rim roads that run ALONG the terminal row (user round
# 4: "they would just get absorbed by the apron anyway") — an edge-hug
# sample within this radius of a terminal whose route runs parallel
# (≤ ROAD_CARVE_TERMINAL_PARA_DEG) to the nearest terminal edge is
# dropped.  Perpendicular corner-passers (the HECA terminal4 →
# junction #168 section, 70°) keep.  Modes A/B are unaffected.
ROAD_CARVE_TERMINAL_RIM_M = 300.0

# (2026-06-27) ROAD-ONLY LOT → GROUNDSIDE.  The on-pavement 1206 carve runs
# a truck-route centerline THROUGH a wide paved lot it merely services
# (CYXY 'Crew cars' loops the lot rim, every sample qualified by the edge-
# hugging mode), shredding the lot into an oversized service_road rect +
# narrow service_junction frames.  Each fragment is individually narrow, so
# the wide-lot guard in the service-junction re-role never fires, and the
# service roles are excluded from the runway-disconnected → groundside pass
# — the lot never becomes the single groundside surface it should be.  A
# road hugging a lot's rim is LOCALLY identical to one hugging the airfield
# rim; only connectivity distinguishes them, so the repair runs on the
# UNION of each connected service_road+service_junction component: a
# morphological OPENING (erode by the road half-width, dilate back) keeps
# the genuinely 2-D parts (the lot) and drops the 1-D road strips.  A
# component whose opened core is ≥ ROAD_LOT_AREA_RATIO of its area is a lot;
# member shapes mostly inside the core → groundside (DEM-follow, merged into
# one surface); the narrow connector strips stay service_road.
# ``O4_ROAD_LOT_GROUNDSIDE``.
ROAD_ONLY_LOT_GROUNDSIDE = (
    _os.environ.get("O4_ROAD_LOT_GROUNDSIDE", "1") == "1")
# Morphological-opening radius (m): erode then dilate by this.  Pavement up
# to 2·R = 15 m wide vanishes; only wider 2-D pavement survives as a lot.
# 7.5 m matches the service-junction re-role's own "narrow road < 15 m"
# threshold (``buffer(-7.5)``), so a legal road (≤ the 13 m carve cap) never
# survives the opening while a genuine lot does.
ROAD_LOT_OPEN_RADIUS_M = 7.5
# Minimum opened-core area (m²) for a surviving piece to count as a lot —
# rejects junction-bulge slivers at road bends/crossings.  This + the 15 m
# opening width is the lot-vs-road discriminator (a road network opens to
# nothing); the area ratio below is an extra knob, off by default.
ROAD_LOT_MIN_AREA_M2 = 200.0
# Optional extra guard: require the opened core to be at least this fraction
# of the component area.  OFF by default (0.0) — a lot hanging off a long
# connector road has a low whole-component ratio yet is still a real lot, so
# the opening + min-area test alone decides.
ROAD_LOT_AREA_RATIO = 0.0


# ── Patch mesh-density tuning (X-Plane load-time optimization) ─────────
# Ortho4XP cuts each SLOPED pavement way into ``cell_size``-metre cells
# (``cuts_long = way_length / cell_size``) and interpolates altitude with
# ``profile`` ("spline" or "plane").  This INTERNAL CUT GRID — not the
# patch's vertex count — drives the airport mesh's triangle count, and
# thus X-Plane load time (HECA measured: cell_size=2 m → +2.24 M
# triangles, 75% of the whole tile, 9m40s load vs 39s without the patch).
#
# A 4-corner sloping rect is a flat tilted PLANE, so a cell_size ≥ the
# way length yields ZERO internal cuts and renders the identical surface
# with a fraction of the triangles.  Runways differ: they carry a real
# FAA vertical profile (crests/sags), so coarsening them too far flattens
# that curve — hence the runway knob below.  (The companion taxiway /
# apron / boundary knob ``PATCH_SLOPE_CELL_SIZE_M`` had no reader left and
# was deleted in the dead-code round.)
#
# To find the optimal compromise, sweep this and measure each build with
# ``tools/mesh_region_tris.py`` (triangle count) + the X-Plane load time.
# Historical default 2 m carried a "KBNA finding" note (smooth runway
# vertical transitions) — raise the runway value cautiously.
RUNWAY_CELL_SIZE_M = 10           # runway segments (real vertical profile)
# Longitudinal interpolation curve for altitude_high/low rects in the
# X-Plane mesh builder.  "plane" = constant grade (linear); "spline" =
# 3x^2-2x^3 smoothstep (flat-tangent at both ends).  Per user 2026-05-23
# (multi-airport DEM analysis): spline is the best fit on only ~6/27
# runways and 3/41 taxiways and never by >0.1 m, and its flat-steep-flat
# shape adds a washboard to constant-grade segments (the taxiway-A2 sag).
# A real surface is a constant grade per segment, so "plane" is the
# correct default; long segments crossing a hill are SPLIT at terrain
# extrema instead (the solver grades each piece within the 1.5% cap, so
# the seam between two plane segments is a <3% — typically <1% — fold,
# not a visible bump).  Lateral clearance inherits this so it tracks.
PATCH_SLOPE_PROFILE = "plane"   # "plane" | "spline"


# ── Surface lateral / end clearance (wingtip + RESA) ──────────────
# Aircraft wingspans exceed the paved width of taxiways/runways, and
# the standards (FAA AC 150/5300-13 TOFA, ICAO Annex 14 graded
# strip / RESA) reserve a clear lateral band on each side and a
# graded area off each runway end.  The clearance pass
# (``clearance.emit_surface_clearance_cuts``) samples the DEM inside
# those bands and CUTS terrain that rises more than the threshold
# above the adjacent surface EDGE altitude down to a ramped ceiling,
# so a wingtip overhanging the pavement clears it.  Terrain BELOW
# the surface is left untouched (cut-only — we never fill).
#
# A terrain point is an "obstruction" when it rises more than this
# many metres above the adjacent surface edge altitude.  Keyed by
# surface family ("taxiway" | "runway" | "service").
CLEARANCE_OBSTRUCTION_THRESHOLD_M = {
    "taxiway": 1.0,
    "runway":  1.0,
    # Service (ground-vehicle) roads: same rise test for the roadside
    # band the ring-edge sweep protects (part 30).
    "service": 1.0,
}

# Runway end skirt (inverse RESA): govern terrain that DROPS beyond a
# runway end, mirroring the cut-only RESA ramp that governs terrain that
# rises.  The law itself (down-grade caps, grade-change rate, governed
# length by approach class) lives in ``grade_law`` — this is only the
# feature gate.  DEFAULT ON since 2026-07-05 (M4: KCLT calibration 0
# findings, flank slivers resolved, EMAS constraint inference in).
RUNWAY_END_SKIRT_ENABLED = (
    _os.environ.get("O4_RUNWAY_END_SKIRT", "1") == "1")

# Runway end RESA CUT (the skirt's rising-terrain twin, arc A2 2026-07-24).
# The skirt above is FILL-only by ruling (STATUS part 30e: "the RESA cut
# (Pass C) separately handles terrain that RISES").  Pass C lived in the
# legacy ``emit_surface_clearance_cuts`` chain, which ``B4_FLIP_DEFAULTS``
# gates OFF — so between the flip (2026-07-15) and this gate NOTHING cut
# rising terrain beyond a runway end (measured SPJC 16R 2026-07-24: 4
# runway_clearance shapes airport-wide, all skirts, zero RESA; no coverage
# of any kind from 70 m to 320 m past the end).  The cut is emitted by
# ``clearance.emit_runway_end_skirts`` — the same anchor, exit march,
# constraint block and weld discipline as the fill — against the ceiling of
# ``grade_law.runway_end_envelope``.  Default OFF until the SPJC/HECA/KCLT
# in-sim battery signs off; flip together with ADJACENT_GROUND_END_PIN.
# ★ FLIPPED DEFAULT ON — OWNER RULING 2026-07-25 ("Turn them all on now, I
# will test in X-Plane").  This is the explicit owner approval the HARD LAW
# requires for gated-but-default-on code; the in-sim battery IS the review.
# The six gates flipped together: O4_RUNWAY_END_RESA,
# O4_ADJACENT_GROUND_END_PIN, O4_STRIP_WIDTH_FROM_CENTERLINE,
# O4_POCKET_COLLAR_RINGS, O4_OLS_CUT, O4_ONE_SOLVE_TERRAIN_RUNWAY_END_RESA.
# Set any env var to 0 to fall back — every arc was proven byte-identical
# gate-off at its landing, so a single 0 isolates one arc cleanly.
#
# SEQUENCING NOTE, now moot but recorded: the recommended order was
# A2 -> A3 -> A4 -> OLS precisely because A3 (the end pin) makes the
# lateral wing terminate SQUARE at full depth, and without A2's cut
# present that square face abuts un-cut rising terrain — a wall the old
# diagonal collapse happened to avoid.  Flipping together satisfies it.
RUNWAY_END_RESA_ENABLED = (
    _os.environ.get("O4_RUNWAY_END_RESA", "1") == "1")

# Adjacent-ground LATERAL grade law feature gate (slice 3, Fable
# 2026-07-08; docs/adjacent_ground_grade_law_plan.md).  DEFAULT ON
# (Noah directive 2026-07-08, flipped after the emitter round-2
# battery — see the flip commit): graded_strip corridor bands replace
# BOTH the boundary→DEM bridge and the full boundary ribbon (the
# at-DEM ribbon path included — the terrain transition beside pavement
# is the per-role lateral law everywhere).  Set
# O4_ADJACENT_GROUND_LAW=0 to restore the ribbon/bridge model.
# STANDING LAW (owner 2026-08-05, no gates): Adjacent-ground zone law (owner 2026-08-01, PROVISIONAL but live).
# The ``O4_ADJACENT_GROUND_LAW`` gate and its env override are DELETED.
ADJACENT_GROUND_LAW_ENABLED = True

# Gap-fill + drainage spine: the authoritative gate + constants live in
# the "GAP-FILL + DRAINAGE SPINE" block further down (search
# GAP_FILL_SPINE_ENABLED).  A duplicate definition block that lived here
# (with a stale GAP_FILL_MAX_WIDTH_M = 160.0 the later block overrode at
# 175.0) was removed 2026-07-11 — one definition only.

# Object-derived BRIDGE terrain feature (feature B of
# docs/object_terrain_features_spec.md).  DEFAULT ON (owner confirmation
# 2026-07-23; the historic DEFAULT-OFF-until-W-V-audits note below is
# retained for provenance).  With the gate OFF no classifier runs and
# every legacy bridge/underpass path is byte-identical to the
# pre-feature build.
#   Historic gating note: the classifier assembler, the
#   classifier-driven replacement of the ``_scenery_has_bridge_objects``
#   name-grep, and the object-sourced depressed-road corridor stayed
#   dormant until the three-pack audits (KBNA / EDDF / KMCO, workstream
#   W-V) were green (project lockstep discipline, spec section 4).
# KNOWN ISSUE 2026-07-23: with either object-terrain gate on, the
# ruling-R4 exclusion set over-consumes (265/266 LSGG structures) and
# starves the Phase 2 y-bake — tracked for a classifier-breadth fix;
# the gate default is NOT the bug.
OBJECT_BRIDGE_TERRAIN = (
    _os.environ.get("O4_OBJECT_BRIDGE_TERRAIN", "1") == "1")

# Feature A — object-derived tunnel terrain (docs/object_terrain_features_
# spec.md section 3.3 + amendment A1, ruling R12).  DEFAULT ON (user
# 2026-07-18, for in-sim testing at EGLL/CYYZ after the oracle audit).
# Trench depth authority = THE OBJECT'S OWN GEOMETRY (user ruling
# 2026-07-18: never the author's custom mesh, which served only as the
# validation oracle).  With O4_OBJECT_TUNNEL_TERRAIN=0 no tunnel-trench
# shape is born and the emitted patch is byte-identical to the
# pre-feature build.  Independent of the bridge gate above so either
# family can be exercised alone.
OBJECT_TUNNEL_TERRAIN = (
    _os.environ.get("O4_OBJECT_TUNNEL_TERRAIN", "1") == "1")

# Feature C — split-level structure terrain (docs/object_terrain_features_
# spec.md section 3.4).  DEFAULT OFF, the spec's own gate: the v1
# split-level terrain adapter is UNBUILT (nothing consumes the
# classifier's ground-interface records), so no structure's terrain is
# ever "adapted to it" and none may join the ruling-R4 exclusion feed —
# excluding without adapting starved the Phase 2 y-bake of plainly
# bakeable terminal buildings (LSGG 2026-07-23, 265/266 objects
# excluded).  Flip on only together with a real feature-C emitter.
OBJECT_SPLIT_LEVEL_TERRAIN = (
    _os.environ.get("O4_OBJECT_SPLIT_LEVEL_TERRAIN", "0") == "1")

# Feature C, open-pit limb — object-derived BASIN trenches (owner defect
# 2026-07-30, OTHH Aeroscape drainage basins).  DEFAULT ON.  This is the
# NARROW slice of feature C that has a real emitter: a BOWL_UNDER_DECK or
# TRENCH_SPINE interface carrying a below-grade footprint and floor is
# adapted by ``object_terrain_assembly.basin_trench_structures`` into a
# feature-A trench record and cut by the SAME emitter under the SAME
# ``grade_law.tunnel_trench_*`` functions — an open pit whose rim is at
# grade is geometrically the tunnel case with no roof.  Only those
# interfaces join the ruling-R4 exclusion feed (predicate:
# ``object_terrain_features.is_carved_basin_interface``), so the
# LSGG y-bake starvation that keeps OBJECT_SPLIT_LEVEL_TERRAIN off
# cannot recur here: an interface is excluded exactly when it is carved.
# The parked ELLX/LFPG depressed-frontage seating stays behind
# OBJECT_SPLIT_LEVEL_TERRAIN.  With O4_OBJECT_BASIN_TRENCH=0 no basin
# plate is born and the emitted patch is byte-identical to the
# pre-feature build.
OBJECT_BASIN_TRENCH = (
    _os.environ.get("O4_OBJECT_BASIN_TRENCH", "1") == "1")

# Feature B, W1b — DECK-FLUSH deck-end pins for road-carried overpasses
# (owner ruling 2026-07-31: "all the bridges you highlighted are above
# ground bridges … they just need to be set so their top edge (the road
# deck) at either end is flush with grade").  DEFAULT ON per the ruling.
#
# A ``road_carried`` span already takes no causeway, no corridor and no
# trench — the road machinery owns the crossing — but it also took no
# PINS, so nothing made the terrain meet the deck where it lands.  This
# gate adds exactly those two pins and nothing else.
#
# Pinning cannot build a false causeway: amendment A4's abutment test
# refuses any structure without solid geometry reaching effective grade
# within ABUTMENT_GRADE_SEARCH_RADIUS_M of BOTH deck ends, so every
# surviving BridgeStructure has grounded abutments by construction.
#
# With O4_OBJECT_BRIDGE_DECK_FLUSH=0 no road-carried span is pinned and
# the emitted patch is byte-identical to the pre-feature build.
OBJECT_BRIDGE_DECK_FLUSH = (
    _os.environ.get("O4_OBJECT_BRIDGE_DECK_FLUSH", "1") == "1")

# W1b's EMITTER — the bridge ramp (owner ruling 2026-07-31: "a bridge
# ramp, that follows a road and just ramps up to the object, rather than
# down to it like a tunnel").  DEFAULT ON per the ruling.
#
# Deck-end pinning alone cannot satisfy the flush ruling for a span
# standing in unpaved ground — there is no pavement ring to pin (OTHH:
# nearest pinnable shape 139-790 m from the six deck ends).  This emits
# the terrain instead: the surface road out of each deck end is ramped UP
# to the deck-end elevation under a grade-capped FILL envelope.
#
# The grade cap is TUNNEL_RAMP_MAX_GRADE — one navigable-ramp number for
# both directions, so a bridge ramp and a tunnel ramp can never drift
# apart.  With O4_OBJECT_BRIDGE_RAMP=0 no ramp quad is born and the
# emitted patch is byte-identical to the pre-feature build.
OBJECT_BRIDGE_RAMP = (
    _os.environ.get("O4_OBJECT_BRIDGE_RAMP", "1") == "1")

# Ramp chain step (m) along the road, and the full width of the ramp
# surface.  The step matches the tunnel-portal chain's granularity; the
# width is one carriageway — the ramp carries the road the bridge
# carries, not the whole crossing opening.
BRIDGE_RAMP_STEP_M = 10.0
BRIDGE_RAMP_WIDTH_M = 16.0

# A ramp never runs further than this even if the grade cap asks for it
# (a 20 m deck end at 4 % would otherwise walk 500 m down the road).
BRIDGE_RAMP_MAX_LENGTH_M = 250.0

# Below this rise the deck end is already flush and a ramp would be a
# no-op plate.  Same order as GROUND_CONTACT_TOLERANCE_M.
BRIDGE_RAMP_MIN_RISE_M = 0.5

# Amendment A1: the tunnel-trench mesh floor sits this far (m) BELOW the
# OBJ8 road deck the object renders.  The deck carries the visible road;
# the mesh only stays safely beneath it (author-mesh dissection section 2.4
# point 3 — the author floors ~1.0 m below the deck at integer-quantised
# precision; 0.5 m satisfies the same strictly-below contract at finer
# precision).  Single source read by ``grade_law.tunnel_trench_floor_
# elevation_m`` (the emitter and any future validator, in lockstep).
TUNNEL_FLOOR_BELOW_OBJECT_DECK_M = 0.5

# BASIN seat-estimate margin (m): extra depth the OPEN-PIT floor law adds
# beneath the modelled bottom, on top of TUNNEL_FLOOR_BELOW_OBJECT_DECK_M
# (spec docs/specs/basin-rim-flush-seating-spec.md section 2.1 item 3).
#
# WHY A SECOND CONSTANT AND NOT A BIGGER FIRST ONE.  The basin floor no
# longer keys on a point DEM sample at the placement anchor; it keys on
# ``R_est``, the MEDIAN DEM sample around the facility's own body outline
# (section 2.1 item 2).  ``R_est`` is an ESTIMATE of the rim the built
# mesh will settle at, and the estimate has measured error: the surface
# the rim must match is the SOLVED one, not the DEM, and the DEM-versus-
# solved gaps measured at OTHH 2026-08-09 reach 0.79 m (Drainage_04: DEM
# 3.41 against a solved apron 2.62).  1.0 m covers that band with room.
# The extra depth sits UNDER the object's own deepest solid, invisible
# from above — the cost of being wrong the other way is a floor cutting
# up through the modelled bottom, which is the visible defect.
#
# Read ONLY by ``grade_law.basin_trench_floor_elevation_m``; the tunnel
# floor law is untouched by it, so the EGLL tunnel class cannot move.
TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M = float(
    _os.environ.get("O4_TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M", "1.0"))

# Vertical clearance (m) the ``grade_law.bridge_crossing_floor`` law adds
# above a road surface for a TERRAIN/PROFILE_CARRIED span that must RISE
# (the EDDF class, where WE choose the vertical split — spec section 3.2).
# Amendment A10 narrowed this constant to the crossing-floor law ONLY:
# the DECK_CARRIED corridor floor is GEOMETRY-DRIVEN (absolute deck
# elevation − hard-deck height above anchor terrain = the anchor-terrain
# datum; a clearance-driven floor over-digs by ~0.9 m at the KBNA
# calibration site).  5.1 m is the upper end of the "real road corridor
# wants 4.5-5.1 m" band (open question 6).
BRIDGE_ROAD_CLEARANCE_M = 5.1

# Validator acceptance bound (m) for the DECK_CARRIED corridor: the
# floor-to-girder-underside clearance must reach at least this.  4.2 m is
# the measured in-the-wild value at the KBNA taxiway-L calibration site
# (deck 167.0, girder line +4.2 over the 161.0 corridor floor — amendment
# A10): the check constant, not the floor driver.
BRIDGE_ROAD_CLEARANCE_MINIMUM_M = 4.2

# How far (m) the depressed road corridor extends per side beyond a
# DECK_CARRIED span before rejoining grade — the approach-walk extent for
# object-sourced corridors.  240 m is the author-mesh measurement at the
# KBNA calibration site (amendment A10 point iv; also the open-question-4
# datum for the corridor-versus-adjacent-ground handoff).
BRIDGE_CORRIDOR_DEPRESSED_LENGTH_M = 240.0

# Deck-end pin capture band (m): pavement ring vertices within this
# distance of a bridge abutment line are hard-pinned at the deck-end
# elevation.  MEASURED (KBNA 2026-07-09, DSF draped pavement versus the
# classified abutment lines): the pack cuts pavement 9.62-9.69 m short
# of the taxiway-L abutments at both ends, so the original 0.25 m
# on-line tolerance captured NOTHING (the stage-2b silent-zero defect).
# 12 m covers the measured cut with margin; amendment A10 makes the
# pinned value exact anywhere in the band — the causeway is FLAT at
# deck-end elevation to the abutment lip, so a vertex 10 m behind the
# lip belongs at the lip's own elevation.
BRIDGE_ABUTMENT_PIN_CAPTURE_BAND_M = 12.0

# Longest flat causeway plate (m) emitted from an abutment line back
# along the approach axis when NO pavement ring lies within the pin
# capture band (the Murfreesboro class: MEASURED pavement gaps 36.7 /
# 45.1 / 57.6 / 60.9 m at the four ends of the two bridges).  65 m
# covers every measured gap; the plate is clipped at the first pavement
# edge it meets (weld, ruling R2).
BRIDGE_CAUSEWAY_MAX_LENGTH_M = 65.0

# ── Tunnel portal pairs (the KBNA runway-02C class, user 2026-07-10) ──
# RESTORED 2026-07-14: the gap_fill round-8 config revision (05bf09f)
# deleted this block while ``bridges.py`` still reads every constant —
# portal pairing then died with a swallowed AttributeError on every
# build (KBNA symptom: channels carved between the two portals under
# the runway, mouth grading degraded).  Two classified structures on
# the SAME road corridor with terrain rising above their tops between
# them are the two PORTALS of one buried tunnel, not two bridges:
# nothing is emitted between them (the hill keeps carrying the runway
# at grade), each mouth's terrain is seated at the ROAD elevation so
# the portal object sits partly submerged, and the road corridor
# climbs AWAY from each mouth.  Pairing requires: centroid spacing
# inside [MIN, MAX]; the connecting segment aligned with both objects'
# headings within the tolerance (parallel side-by-side decks fail this
# — their connecting segment is PERPENDICULAR to their headings); and
# the digital elevation model between the mouths reaching at least the
# lower portal's top plus the buried margin (a bridge pair over open
# ground fails this).
TUNNEL_PORTAL_PAIR_MIN_SPACING_M = 20.0
TUNNEL_PORTAL_PAIR_MAX_SPACING_M = 600.0
TUNNEL_PORTAL_PAIR_HEADING_TOLERANCE_DEGREES = 30.0
TUNNEL_PORTAL_PAIR_BURIED_MARGIN_M = 1.0
# Portal-FACE plate synthesis (owner ruling 2026-07-18, EGGW class): a
# bare face quad's horizontal projection is a sliver, so the KBNA-style
# mouth/crown/collar plates are built on a synthesized rectangle
# CENTERED ON THE FACE ANCHOR — face width plus a shoulder each side,
# half the depth outward (the road-grade mouth half) and half inward
# (the deck-grade crown half over the buried bore).  Shoulder 3 -> 4 m
# (user screenshots 2026-07-18e): the cut's lateral side walls stood
# just proud of the portal object's flared wing walls and hid them —
# one extra metre tucks the terrain behind the object.
PORTAL_FACE_PLATE_SHOULDER_M = 4.0
PORTAL_FACE_PLATE_DEPTH_M = 16.0
# (user screenshots 2026-07-18b, EGGW) A hanging-face portal seats its
# ANCHOR at deck grade — the object drapes at terrain(anchor) and the
# face hangs BELOW its origin — but the anchor sits mid-road ON the
# face line.  A 5 m ROUND disk there rendered as a ~10 m arc-shaped
# tower in the middle of the road at both EGGW mouths, and the v20
# rectangle's 1 m outward lip still rendered as a squared fin (user
# screenshots 2026-07-18e).  The seat is a FACE-ALIGNED rectangle
# ENTIRELY BEHIND the face: its front edge passes exactly THROUGH the
# anchor along the face line, so the drape at the anchor interpolates
# between that edge's two deck-grade nodes no matter which triangle
# claims the point — zero terrain stands outward of the face.  The
# inward reach fuses it with the crown across the crown's 1 m face
# setback.  The road-grade mouth plate is cut back an extra CLEARANCE
# margin around the seat so no seat node shares a ~0.5 m mesh node
# bucket with a mouth node (first-writer interning would otherwise
# decide the wall height at random — the v18 face-meeting trap).
PORTAL_FACE_ANCHOR_SEAT_HALF_WIDTH_M = 2.5
PORTAL_FACE_ANCHOR_SEAT_OUTWARD_M = 0.0
PORTAL_FACE_ANCHOR_SEAT_INWARD_M = 4.0
PORTAL_FACE_ANCHOR_SEAT_CLEARANCE_M = 0.9
# Outward ray from each mouth sampled over this range for the mouth
# floor (the MINIMUM wins — the descending road's grade at the face,
# robust against the embankment skirt inflating near samples).  150 m
# because the smoothed airport raster decays embankment flattening
# slowly (measured KBNA 02C: still falling 0.09 m per 5 m at 60 m out).
TUNNEL_PORTAL_MOUTH_SAMPLE_RANGE_M = 150.0

# (user ruling 2026-07-14b) Pavement rings within this band of a
# causeway plate's boundary are hard-pinned at the deck-end elevation:
# the approaches on BOTH sides of an object bridge anchor at the deck
# height and grade smoothly away from it.  Wider than the abutment
# capture band — the resumed pavement across the KBNA Donelson Pike
# road-exit cut measures 13.3-13.6 m from the plate exterior (the
# unpinned side solved 6.3 m above the deck before this).
BRIDGE_CAUSEWAY_WELD_PIN_BAND_M = 16.0

# (user ruling 2026-07-14b) Width of the flat COLLAR band emitted
# around the back and sides of a paired portal's buried half, held at
# the crown (object top) elevation: the ground behind the portal keeps
# the deck/roof height while the road grades down into the mouth.
TUNNEL_PORTAL_CROWN_COLLAR_M = 10.0

# (user ruling 2026-07-14) A paired portal's footprint is SPLIT at its
# centroid perpendicular to the mouth direction: the open-mouth half is
# born at the road grade (as before), and the BURIED half — the side
# facing the runway over the tunnel body — is born as a CROWN plate at
# the object's top elevation (mouth floor + deck top).  Before this,
# the whole footprint sat at road grade and the terrain runway-side of
# each portal dipped to the road instead of riding over the tunnel
# roof.  O4_TUNNEL_PORTAL_CROWN=0 restores the single road-grade plate.
TUNNEL_PORTAL_CROWN = (
    _os.environ.get("O4_TUNNEL_PORTAL_CROWN", "1") == "1")

# (user ruling 2026-07-17) THE PORTAL OBJECT IS THE TERRAIN AUTHORITY:
# the portal's large flat top surface (below its safety-wall parapet)
# is the divider between the below-grade road and the at-grade back
# terrain, and it sits close to level with the adjacent taxiway.  Two
# consequences:
# * PRE-SOLVE, the crown plate seats no lower than the object's roof
#   plane (``mouth_floor + deck_top`` — the cosmetic classifier's
#   dominant elevated plane already excludes small-area parapet caps).
#   The smoothed DEM stays only as an UPWARD override (a genuinely
#   buried hillside portal keeps the higher terrain).  KBNA
#   Murfreesboro west: DEM said 171.2 where the object roof is 176.8 —
#   the collar sat at road level and the portal-mouth backside was
#   visible from the runway.
# * POST-SOLVE, crown and collar RISE (never fall) to the surrounding
#   solved airside level where that is higher (raise pass in
#   ``bridges.raise_portal_terrain_to_airside``, called from
#   finalize after the solve).  KBNA Murfreesboro east: airside
#   junctions at 176.4-178.5 over a 173.15 object roof.
# ``O4_TUNNEL_PORTAL_AIRSIDE_RAISE=0`` disables the post-solve raise.
TUNNEL_PORTAL_AIRSIDE_RAISE = (
    _os.environ.get("O4_TUNNEL_PORTAL_AIRSIDE_RAISE", "1") == "1")
# Radius around a crown/collar vertex within which solved airside ring
# vertices define the local airside level (median of samples).
TUNNEL_PORTAL_AIRSIDE_SAMPLE_RADIUS_M = 80.0

# (user ruling 2026-07-14) Adjacent-ground bands and surface-clearance
# cuts are masked OUT of every crossing Feature B owns (corridor deck
# boxes and tunnel-portal-pair regions): the objects provide the
# terrain story there, and bands/cuts marching into the crossing fight
# the object cut (measured KBNA Donelson Pike).
# O4_BRIDGE_CROSSING_MASK=0 restores the unmasked march.
BRIDGE_CROSSING_MASK = (
    _os.environ.get("O4_BRIDGE_CROSSING_MASK", "1") == "1")

# Safety cap (m) on how far a clearance band reaches outward from the
# pavement edge, bounding earthwork.  Must be >= the largest band we
# actually want: a code-4 runway-end RESA is 240 m, so the runway cap
# sits above that; taxiway wingtip bands are <= ~43 m.
CLEARANCE_MAX_REACH_M = {
    "taxiway": 100.0,
    "runway":  300.0,
    # Service (ground-vehicle) roads have no wingtip envelope, so the
    # band IS the reach: a fixed roadside clearance corridor beyond the
    # road edge (AASHTO clear-zone-informed design value) inside which
    # terrain rising above the road edge + threshold is cut down to the
    # edge level (flat shadow, cut-only — the part-30 ring-edge sweep).
    "service": 15.0,
}

# Vertex spacing (m) along a surface edge when sampling/building the
# clearance band.  Matches ``ELEVATION_GRID_STEP_M`` (5 m) so the cut
# resolves the same terrain detail the elevation solver does.
CLEARANCE_STATION_STEP_M = 5.0

# RESA / runway-end graded distance (m) beyond the runway end, by
# ICAO Annex 14 code number (derived from runway length).  ICAO RESA
# min is 90 m (240 m recommended for code 3/4); these defaults fold
# the strip-end portion in and stay conservative-but-tunable.
RUNWAY_END_CLEARANCE_LENGTH_BY_CODE = {1: 60.0, 2: 90.0, 3: 150.0, 4: 240.0}

# Maximum longitudinal slope (rise/run) of the graded runway-end safety
# area.  ICAO Annex 14 caps RESA longitudinal slopes at 5%; the RESA
# ramp rises from the runway-end pavement elevation at this slope and
# daylights where it meets natural ground, so an undershooting /
# overrunning aircraft meets a gentle slope rather than a wall.
RUNWAY_END_RESA_MAX_SLOPE = 0.05

# Transverse slope (rise/run) of the LATERAL clearance strip alongside
# a runway/taxiway.  These strips are FLAT shadows of the surface they
# protect: at each station the strip sits at the local pavement-edge
# altitude (so it follows the surface's longitudinal profile) and
# extends out level — an extension of the pavement, not a ramp.  Terrain
# is cut down to this surface level ONLY where the DEM rises above it
# within the protected (code-letter wingtip) width; everything at or
# below the surface is left untouched (cut-only).  This is intentionally
# 0: a non-zero lateral slope grades the band down to a SUB-surface ramp,
# which carves canyons wherever the pavement sits below its surroundings
# (cut into a hillside / solver-sunk).  RESA end-caps still ramp — see
# RUNWAY_END_RESA_MAX_SLOPE.
CLEARANCE_LATERAL_MAX_SLOPE = 0.0

# Lateral graded-strip half-width (m) from the runway centerline, by
# ICAO code number (Annex 14 graded portion of the runway strip).
RUNWAY_STRIP_HALF_WIDTH_BY_CODE = {1: 30.0, 2: 40.0, 3: 75.0, 4: 75.0}

# Maximum aircraft wingspan (m) per ICAO code letter (Annex 14).  The
# taxiway clearance band is based on the WINGTIP REACH — half the
# wingspan from the centerline plus a small margin — i.e. how far a
# wingtip overhangs, which is the terrain a wingtip could actually
# strike.  (The Table-3-1 "centre-line → object" distances — A 16.25 …
# F 57.5 — are far larger; they protect against objects/buildings and
# include lateral-deviation allowances, which over-grade terrain.)
WINGSPAN_BY_CODE_LETTER = {
    "A": 15.0, "B": 24.0, "C": 36.0, "D": 52.0, "E": 65.0, "F": 80.0,
}

# Margin (m) added beyond the wingtip (FAA-style wingtip clearance).
TAXIWAY_WINGTIP_MARGIN_M = 3.0

# Maximum aircraft TAIL HEIGHT (m) per ADG / ICAO code letter.  FAA AC
# 150/5300-13B Table 1-1 keys the Airplane Design Group by tail height
# AND wingspan (ADG I ≤20 ft, II <30, III <45, IV <60, V <66, VI <80 ft);
# the ICAO code letters map A↔I, B↔II, C↔III, D↔IV, E↔V, F↔VI, so the
# table is keyed by LETTER here to match ``WINGSPAN_BY_CODE_LETTER``
# above.  20 ft = 6.1, 30 = 9.1, 45 = 13.7, 60 = 18.3, 66 = 20.1,
# 80 = 24.4 m.  Used by the END-AROUND TAXIWAY ceiling below: it is the
# TAIL, not the wingtip, that penetrates a departure surface.
TAIL_HEIGHT_BY_CODE_LETTER = {
    "A": 6.1, "B": 9.1, "C": 13.7, "D": 18.3, "E": 20.1, "F": 24.4,
}


# ── END-AROUND TAXIWAY (EAT) departure/approach surface ceiling ───────
# Owner ruling 2026-07-27.  An end-around taxiway loops BEYOND a runway
# end and crosses the extended centreline, so an aircraft on it stands
# directly under the departure (take-off climb) surface.  The surface
# must clear the aircraft's TAIL, which forces the EAT PAVEMENT below
# the runway-end elevation — KATL taxiway Victor runs ~30 ft (≈9 m)
# below its runway end for exactly this reason.
#
# This is the first grade law that binds TAXI PAVEMENT to a runway-end
# surface: ``ols.py`` is a terrain-CUT law and pavement is explicitly
# exempt from it (``solver_primitives._build_resa_cut_constraints``'s
# identity-collision rule), so before this nothing tied taxi pavement
# beyond a runway end to any surface at all.
#
# Gate OFF ⇒ no per-end store, no pins, no verification reader —
# byte-identical to the pre-feature build.
#
# DEFAULT ON — ANCHOR-RECT REVISION (owner rulings 2026-07-27,
# docs/specs/eat-anchor-rect-spec.md).  The FIRST implementation encoded
# the surface as one-sided pavement↔pavement interval edges
# (``_build_eat_ceiling_constraints``); their strongly NEGATIVE (≈ −10 m)
# slab weights blew up the lazy (non-negative-weight) reach-envelope
# Dijkstra in ``one_solve.feasibility_project`` — KCLT killed at 15 min
# CPU / 20.3 GB RSS in a ``heappop`` storm — so it shipped gated off.
# The ACTIVE mechanism is now a HARD ANCHOR RECT
# (``solver_primitives._build_eat_anchor_rect_pins``, applied inside
# ``_seed_elevations``): the runway-width × EAT-crossing-width rectangle
# on the extended centreline is PINNED at the regulation value
# (``end_elev + eat_pavement_ceiling(D_mid)``) unconditionally — even
# where it must fill DEM — and the solver grades the ramps to it through
# the EXISTING positive-weight anchor machinery, exactly as it grades to
# crossing runways and tile seams.  No negative edge exists anywhere, so
# the envelope blow-up class is structurally gone.  A loop too short to
# ramp lawfully surfaces in the both-hard step report and the
# ``check_eat_ceiling`` audit — never a silent grade break.
EAT_SURFACE_CEILING_ENABLED = (
    _os.environ.get("O4_EAT_SURFACE_CEILING", "1") == "1")

# FAA (North America).  AC 150/5300-13B §4.12 + FAA Order 8260.3 (TERPS)
# departure surface: 40:1 (2.5 %) rising FROM the departure end of runway
# (DER) AT the DER elevation — no setback.
EAT_FAA_DEPARTURE_SLOPE = 0.025
EAT_FAA_SETBACK_M = 0.0

# EASA (everywhere else).  CS-ADR-DSN H.435 / Table J-2 + J.480(e)
# take-off climb surface, code 3/4: 2 % from an inner edge 60 m beyond
# the runway end.
EAT_EASA_TAKEOFF_CLIMB_SLOPE = 0.02
EAT_EASA_SETBACK_M = 60.0

# SCOPING GUARD — minimum along-centreline distance beyond the runway end
# at which the ceiling binds.  Taxi pavement CLOSER than this is an
# ordinary runway-end connector (a rapid exit, a threshold link), not an
# end-around taxiway; applying the surface there is violently infeasible
# (at 60 m the FAA ceiling for a code-E tail is 60·0.025 − 20.1 = −18.6 m
# below the runway end).  A real EAT crosses the extended centreline
# hundreds of metres out — KCLT's 18C-end loop crosses at 439–482 m.
EAT_MIN_CROSSING_DIST_M = 300.0

# Lateral half-width (m) of the corridor about the extended centreline
# inside which the ceiling binds.  Deliberately a single conservative
# constant rather than the departure surface's true splayed extent: the
# real FAA/EASA surfaces flare outward with distance, and reproducing the
# splay is a refinement.  90 m is the runway OFZ-ish corridor — wider than
# the code-4 graded strip half-width (75 m) and comfortably covering the
# centreline crossing of a real end-around loop, narrow enough that the
# apron/taxi network to either side of the extended centreline is not
# swept in.
EAT_CORRIDOR_HALF_WIDTH_M = 90.0

# ANCHOR-RECT segmentation (m): governed pavement vertices are clustered
# into connected CROSSING SEGMENTS (one per end-around taxiway) by their
# along-centreline distance; a gap larger than this splits two segments.
# Must exceed the 60 m emit-decimation chord cap (consecutive ring
# vertices of ONE crossing can be up to a chord apart in ``s``) while
# staying well under the separation of two genuinely distinct crossings
# (a second EAT sits at least a runway-strip width further out).  Each
# segment is pinned FLAT at its own mid-distance regulation value; where
# two ends' corridors overlap one segment, the LOWER value wins.
EAT_RECT_SEGMENT_GAP_M = 75.0

# FALSE-EAT SCOPING GUARDS (measured 2026-07-27, first default-ON run —
# ⚠ scoping refinements pending owner ratification; the value law and
# the rect mechanism are the owner's rulings verbatim, these two guards
# only decide WHICH pavement counts as an end-around taxiway):
#
# 1. Minimum runway CODE NUMBER whose ends can own an EAT.  End-around
#    taxiways exist at transport-category runways (FAA AC 150/5300-13B
#    builds them for air-carrier hubs; every real example — KATL, KCLT,
#    KDFW — is a code 3-4 runway).  CYXY's 700 m code-1 crosswind strip
#    02/20 aims its extension across the GA apron 300-630 m out; without
#    this guard those 23 apron/junction vertices were PINNED ~5 m into
#    the ground as a phantom EAT.
EAT_MIN_RUNWAY_CODE_NUMBER = 3
#
# 2. Maximum ALONG-centreline extent (m) of one crossing segment.  A
#    real EAT CROSSES the corridor transversely — the owner's ruling
#    itself: "the rect is short along the direction of EAT travel"
#    (KCLT's crossing spans 43 m of ``s``; an oblique crossing plus its
#    junction fan stays well inside 150 m).  Pavement that RUNS ALONG
#    the extended centreline (CYXY: a 327 m apron smear) is another
#    facility under the surface, not an end-around taxiway — refused
#    whole, counted, and reported; never pinned.
EAT_RECT_MAX_ALONG_M = 150.0

# ICAO prefixes that select the FAA ruleset (North America).  "K" = the
# contiguous USA, "C" = Canada, "P" = Alaska / Hawaii / US Pacific,
# "M" = Mexico + Central America.  Everything else takes EASA.  The
# owner ruling is "FAA for North America, EASA everywhere else"; keying
# on the ICAO location-indicator first letter is the cheapest faithful
# expression of that split and needs no external region database.
EAT_FAA_ICAO_PREFIXES = frozenset({"K", "C", "P", "M"})


def eat_surface_slope_and_setback(icao) -> tuple:
    """``(slope, setback_m)`` of the departure / take-off-climb surface
    that governs an end-around taxiway at airport ``icao``.

    FAA (AC 150/5300-13B §4.12, FAA Order 8260.3 TERPS) in North America
    — 40:1 from the DER with no setback; EASA (CS-ADR-DSN H.435 /
    Table J-2, J.480(e)) everywhere else — 2 % from a 60 m inner edge.
    Region is decided from the ICAO location indicator's first letter
    (see ``EAT_FAA_ICAO_PREFIXES``); an empty/unknown ICAO falls to EASA,
    which is the STRICTER (lower) ceiling at every distance beyond
    ~240 m, so missing data never buys a permissive surface.
    """
    letter = (str(icao or "").strip().upper() or " ")[0]
    if letter in EAT_FAA_ICAO_PREFIXES:
        return (EAT_FAA_DEPARTURE_SLOPE, EAT_FAA_SETBACK_M)
    return (EAT_EASA_TAKEOFF_CLIMB_SLOPE, EAT_EASA_SETBACK_M)


def runway_code_letter(width_m: float) -> str:
    """ICAO code LETTER of the design aircraft a RUNWAY is built for,
    inferred from its declared width (m).

    ``taxiway_code_letter`` above is the TAXIWAY table and must not be
    reused here — runway width standards are a different table.  FAA AC
    150/5300-13B Table 3-3 runway widths by ADG: I 18.3 m, II 22.9 m,
    III 30.5 m, IV/V 45.7 m, VI 61.0 m (ICAO Annex 14 Table 3-1 agrees
    at code 4: C/D/E 45 m, F 60 m).  ADG IV and V share the 150 ft width,
    so a 45 m runway is ambiguous between letters D and E; it resolves to
    **E**, the taller tail — for a CEILING law the taller aircraft is the
    conservative reading (a lower ceiling), and 45 m runways at
    ADG-V airports (KCLT, KATL) are the case this law exists for.
    """
    w = float(width_m or 0.0)
    if w >= 55.0:
        return "F"
    if w >= 42.0:
        return "E"
    if w >= 28.0:
        return "D"
    if w >= 21.0:
        return "C"
    if w >= 15.0:
        return "B"
    return "A"


# ── Adjacent-ground grade law — lateral corridor off a pavement edge ──
# (Fable design 2026-07-08, docs/adjacent_ground_grade_law_plan.md; the
# LATERAL generalization of the runway-END skirt law.)  Ground next to a
# paved surface is governed as a two-zone-plus-ungraded CORRIDOR off the
# pavement EDGE: a signed-height [floor, ceiling] envelope relative to
# the edge elevation, as a function of lateral distance d.  These are
# the RULE VALUES; the zone MATH — accumulated so the corridor bounds
# are CONTINUOUS functions of d — lives in
# ``grade_law.adjacent_ground_envelope``.  Runway ENDS are NOT here: the
# longitudinal runway-end skirt law (``grade_law.runway_end_skirt_*``)
# owns them.
#
# NOAH RULED 2026-07-08 (ruling 1, ENFORCE FULLY): the envelope is a
# corridor WITH DIRECTION — each graded zone is a mandatory-DOWN band
# [min_slope, max_slope] exactly as the FAA writes it, so a FLAT surround
# beside pavement is regraded to at least the minimum fall (a code-4
# runway's graded band falls ≥1.1 m over its 75 m half-width).  Where FAA
# mandates DOWN and ICAO merely permits UP, FAA wins (maximal conformance,
# one blended global ruleset).

# ZONE 1 — drainage lip, shared by the runway & taxiway strips.  The
# first 3 m (FAA 10 ft) must fall AWAY from the edge at 3–5 % so water
# sheds off the pavement: FAA AC 150/5300-13B Fig 3-33 Detail A (3–5 %
# negative for the first 10 ft); FAA TSA §4.14.2 (5 %±0.5 %); ICAO
# Annex 14 Vol I §3.4.15 (strip transverse negative ≤5 %); the strip
# abuts flush (§3.4.10).  A flat lip (0 %) is UNLAWFUL here (mandatory
# down) — this is what makes the envelope a corridor, not a bare cap.
ADJACENT_GROUND_LIP_WIDTH_M = 3.0
ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE = 0.03
ADJACENT_GROUND_LIP_MAX_DOWN_SLOPE = 0.05

# ZONE 2 — RUNWAY graded strip.  Transverse fall bounded 1.5 % (FAA
# MINIMUM — ICAO has none) … 3 % (AAC C–E) / 5 % (AAC A/B): FAA AC
# 150/5300-13B Table 3-6 S-3 (RSA side slope 1.5–5 % A/B, 1.5–3 % C–E);
# cross-checked against ICAO Annex 14 §3.4.15 (transverse ≤2.5 % code
# 3/4, ≤3 % code 1/2).  Keyed by ICAO code NUMBER (ruling 2 — the repo's
# runway keying; numbers agree with AAC): code 3/4 ≈ AAC C–E (3 % cap),
# code 1/2 ≈ AAC A/B (5 % cap).  The graded WIDTH reuses
# RUNWAY_STRIP_HALF_WIDTH_BY_CODE (do NOT duplicate) as the from-edge
# band bound (a slight over-reach vs the strict from-centerline strip,
# per the plan's "≤75 m at code 3/4").
RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE = 0.015
RUNWAY_STRIP_BAND_MAX_DOWN_SLOPE_BY_CODE = {1: 0.05, 2: 0.05, 3: 0.03, 4: 0.03}

# ZONE 2 — TAXIWAY graded strip.  Transverse DOWN ≤5 %, UP ≤2.5 % (C–F)
# / 3 % (A/B): ICAO Annex 14 §3.11.5 / EASA CS-ADR-DSN.D.280; FAA TSA
# grades 1.5–5 % (AC 150/5300-13B §4.5.3, §4.14.2).  Enforced as a
# mandatory-DOWN band 1.5 % … 5 % (ruling 1).  The graded WIDTH is the
# OMGWS-derived graded half-width of the taxiway strip, keyed by ICAO
# code LETTER (ICAO Annex 14 §3.11.4 / EASA CS-ADR-DSN.D.325(b), current
# editions): OMGWS <4.5 / 4.5–6 / 6–9 m → 10.25 / 11 / 12.5 m (letters
# A/B/C), letters D/E/F → 18.5 / 19 / 22 m (ruling 2).  FAA's
# TSA-wingspan width is deliberately NOT used — wingtip clearance governs
# that envelope separately (``taxiway_clearance_half_width_*``).
TAXIWAY_STRIP_BAND_MIN_DOWN_SLOPE = 0.015
TAXIWAY_STRIP_BAND_MAX_DOWN_SLOPE = 0.05
TAXIWAY_STRIP_GRADED_HALF_WIDTH_BY_LETTER = {
    "A": 10.25, "B": 11.0, "C": 12.5, "D": 18.5, "E": 19.0, "F": 22.0,
}


def taxiway_strip_graded_half_width_for_letter(letter) -> float:
    """OMGWS-derived graded half-width (m) of the taxiway strip for ICAO
    code ``letter`` — the zone-2 outer bound of the adjacent-ground
    corridor (``TAXIWAY_STRIP_GRADED_HALF_WIDTH_BY_LETTER``).  An
    unknown / None letter (unclassified OSM taxiway) falls back to the
    widest NARROW-band value (code C, 12.5 m) — never a wide-body D–F
    width for a taxiway we could not size."""
    return TAXIWAY_STRIP_GRADED_HALF_WIDTH_BY_LETTER.get(
        str(letter).upper() if letter else "", 12.5)


# ZONE 3 — ungraded portion (beyond the graded band, still inside the
# reach).  NO downward mandate: a cliff beyond the graded portion is
# LAWFUL (the boundary-bridge killer — the DEM wins below).  Only RISING
# ground is capped, at ≤5 % upward toward the pavement: ICAO Annex 14
# §3.4.16 (runway strip) / §3.11.6 (taxiway strip).  The outward reach
# bound reuses CLEARANCE_MAX_REACH_M (runway 300 m / taxiway 100 m);
# beyond it the ground is ungoverned here (the OLS transitional surface
# takes over — docs/grade_law_gap_audit.md GAP 1).
ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE = 0.05

# DAYLIGHT SLOPE LIMIT (user ruling 2026-07-09; engineering judgment,
# no external citation): the governed (daylight) depth of the
# adjacent-ground march may grow by at most this factor times the
# along-frontage distance between neighbouring stations — physical
# grading benches into terrain; an isolated deep ray would cut a
# 150 m knife slot no bench could build (CYXY shape 417).  Consumed
# by grade_law.adjacent_ground_supported_depths (emitter + validator
# in lockstep).
ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT = 2.0

# END-SKIP BENCH PIN (arc A3, 2026-07-24).  The daylight limit above
# benches a band's depth down toward any neighbour at depth 0 — and a
# runway END-edge station is at depth 0 not because the terrain is lawful
# there but because the march SKIPS it (``_RING_END_NORMAL_DOT``: the end
# is skirt/RESA territory).  So the lateral wing collapses diagonally into
# the end corner: measured SPJC 16R 2026-07-24, band #702's outer edge runs
# from 75 m depth at 20 m before the corner to 3 m at the corner, and every
# vertex sits exactly on ``2.0 x distance-back-from-corner`` — the clamp,
# not the terrain (the DEM there is obstructed to the full cap).  With this
# ON, the terminal station adjacent to an end-skip run is PINNED exactly as
# a continuation seam is (``adjacent_ground_supported_depths``'s
# ``at_continuation_seam``): it holds its raw scanned depth, the wing ends
# square, and it clips/welds onto the end-regime surfaces.  Emitter and
# validator march must set this identically (lockstep).
ADJACENT_GROUND_END_PIN_ENABLED = (
    _os.environ.get("O4_ADJACENT_GROUND_END_PIN", "1") == "1")

# RUNWAY STRIP WIDTH MEASURED FROM THE CENTERLINE (arc A4, 2026-07-24).
# ``RUNWAY_STRIP_HALF_WIDTH_BY_CODE`` is an Annex-14 half-width from the
# runway CENTERLINE, but the adjacent-ground march applies it as a reach
# from the pavement EDGE — and the emitted runway carries apt.dat shoulders
# (SPJC 16R/34L: 45 m -> 81 m), so the band reaches 115.5 m from the
# centerline where the strip is 75 m.  Both legacy passes clamped this
# correctly (Pass A3 by distance-from-centerline, Pass B by subtracting the
# half-width); the lateral law inherited neither.  With this ON, a
# runway-family station's band width is clamped to
# ``strip_half - dist(station, runway axis)``.  Default OFF pending the
# SPJC/CYXY/SPLP A/B — it is a POLICY change (less earthwork), not a bug
# fix, and it also REDUCES build time (fewer deep stations).
STRIP_WIDTH_FROM_CENTERLINE_ENABLED = (
    _os.environ.get("O4_STRIP_WIDTH_FROM_CENTERLINE", "1") == "1")

# ── Obstacle limitation surfaces — terrain-penetration CUT law ──────
# docs/specs/obstacle-limitation-surfaces-spec.md (Fable, 2026-07-24);
# gap-audit GAP 1.  The ruled FOLLOW-ON of the adjacent-ground lateral
# law: zone 3's ceiling comment above promises that "beyond it the OLS
# transitional surface takes over" — these constants are that surface.
#
# An OLS is an OBSTACLE limitation surface: the codes forbid new
# obstacles above it and require assessment of existing ones; they do
# NOT mandate grading terrain down to it.  Cutting terrain to it is a
# deliberate scenery-repair reinterpretation (exactly like the skirt) —
# where a surface-model DEM pokes through the volume a real aerodrome
# keeps clear, we cut it back.  That framing is why only TWO surfaces
# are modelled (transitional + approach first section) and why
# inner-horizontal / conical are REFUSED as cut surfaces: as cuts they
# decapitate every hill within 4 km above +45 m, which at SPLP is a
# mountain range.  See the spec's scope ruling.
OLS_CUT_ENABLED = _os.environ.get("O4_OLS_CUT", "1") == "1"

# Classic ICAO Annex 14 Vol I (8th ed) Table 4-1, adopted over FAA Part
# 77 §77.19 (a NOTIFICATION surface set — weaker near-field: approach
# 34:1 = 2.94 % vs ICAO 2 %) and over Amendment-18's ADG-keyed OFS/OES
# (applicable 2028-11-26; the repo has no ADG plumbing — WATCH item in
# docs/STANDARDS.md).  Keyed by the repo's own approach classes
# (``runway_end_approach_class``): "visual" = non-instrument,
# "non_precision" = NPA, "precision" = CAT I (apt.dat cannot tell
# II/III apart, and their geometry is identical at code 3/4 for the
# surfaces built here).
OLS_TRANSITIONAL_SLOPE = 0.143          # 1:7 — every class except:
OLS_TRANSITIONAL_SLOPE_STEEP = 0.20     # 1:5 — visual / NPA code 1-2
# OLS strip half-width from the CENTERLINE (Annex 14 §3.4.3-3.4.4) —
# the FULL strip the transitional surface rises from, NOT the graded
# portion.  Non-instrument reuses RUNWAY_STRIP_HALF_WIDTH_BY_CODE
# (30/40/75/75) — §3.4.4 and §3.4.9 give the same widths, so there is
# no second copy to drift.
OLS_STRIP_HALF_WIDTH_INSTRUMENT_BY_CODE = {
    1: 70.0, 2: 70.0, 3: 140.0, 4: 140.0}

# Approach surface, FIRST SECTION only (the rest is out of cut scope).
OLS_APPROACH_SETBACK_M = 60.0                 # inner edge beyond the end
OLS_APPROACH_SETBACK_VISUAL_CODE1_M = 30.0
# Inner-edge HALF widths (m).  Full widths per Table 4-1: non-instrument
# 60/80/150/150; NPA code 1/2 150; NPA code 3/4 and precision code 3/4
# 300; precision code 1/2 150.  ICAO's 300 m is adopted over EASA
# CS-ADR-DSN.H's 280 m for NPA 3/4 — wider is stricter for a cut law.
OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M = {
    "visual":        {1: 30.0, 2: 40.0, 3: 75.0, 4: 75.0},
    "non_precision": {1: 75.0, 2: 75.0, 3: 150.0, 4: 150.0},
    "precision":     {1: 75.0, 2: 75.0, 3: 150.0, 4: 150.0},
}
OLS_APPROACH_DIVERGENCE = {
    "visual": 0.10, "non_precision": 0.15, "precision": 0.15}
# First-section slopes.  NOTE (primary re-verification 2026-07-24): NPA
# code 3/4 is 2 %, the SAME as precision 3/4 — 3.33 % is NPA code 1/2.
# docs/grade_law_gap_audit.md carried the compressed/incorrect form
# until this arc corrected it.
OLS_APPROACH_FIRST_SECTION_SLOPE = {
    "visual":        {1: 0.05, 2: 0.04, 3: 0.0333, 4: 0.025},
    "non_precision": {1: 0.0333, 2: 0.0333, 3: 0.02, 4: 0.02},
    "precision":     {1: 0.025, 2: 0.025, 3: 0.02, 4: 0.02},
}

# EMISSION BOUNDS — design values bounding earthwork and the visual
# blast radius, NOT regulatory lengths (the CLEARANCE_MAX_REACH_M
# philosophy; documented as design choices in docs/STANDARDS.md).
# Table 4-1's first section runs 3 000 m; that is a LAW length, not a
# cut reach — beyond ~1 km the ceiling is already +20 m and any
# DEM-artefact terrain has daylighted long since.
OLS_TRANSITIONAL_EMIT_REACH_M = 300.0   # beyond the handover distance S.
    # The 45 m inner-horizontal cap sits at ~315 m of 14.3 % rise, so
    # within this reach the cap is unreachable — deliberately unmodelled.
OLS_APPROACH_EMIT_REACH_M = 1000.0      # beyond the inner edge.
# MOUNTAIN REFUSAL: a contiguous penetration island needing more than
# this cut depth anywhere is refused WHOLE.  Shaving the fringe of a
# real mountain while leaving its core sculpts a moat; the charter is
# DEM-artefact repair (5-15 m lumps), not obstacle removal.
OLS_MAX_CUT_DEPTH_M = 15.0
# Cut trigger — terrain must exceed the ceiling by this much before any
# cut is emitted.  Same value and meaning as
# CLEARANCE_OBSTRUCTION_THRESHOLD_M, named separately so the OLS reach
# can be retuned without touching the clearance passes.
OLS_OBSTRUCTION_THRESHOLD_M = 1.0

# ── OLS SEAM REFUSAL MEASURED AT THE TILE LINE (fix 2026-07-25) ─────────
# The OLS spec's cross-tile determinism rule refuses whole any penetration
# island "touching the covering DEM's tile-boundary edge"; ``ols._dem_raster``
# implements that as the rows/columns where the raster WINDOW WAS CLAMPED by
# the DEM's own extent.  An airport DEM usually covers well past the tile it
# is keyed to, so at SPLP -13/-078 the raster runs 1088 m EAST of lon -77 and
# nothing near the seam was ever flagged: two islands — one sitting exactly
# ON the meridian, one 5 m inside the cut-back line — were admitted, and the
# post-emit ``cut_layout_at_tile_boundaries`` sliced their bands, leaving four
# ``ols_cut`` cut-back nodes 0.35 / 1.06 / 1.47 / 2.18 m BELOW the DEM that
# the 10 m seam gap renders (measured; the -13/-077 build cuts nothing there,
# so the wall is one-sided as well).
#
# Those nodes cannot be repaired by the universal seam DEM pin: an OLS cut is
# ``min(ceiling, DEM)``, so lifting a node to the DEM would UN-CUT a real
# obstruction at the seam — the seam law and the cut-only law genuinely
# conflict AT the node.  They agree one step earlier: the OLS must not reach
# the seam at all.  With this ON the refusal is measured against the CURRENT
# TILE's own boundary (what the cut actually slices) as well as the data
# extent — a cell within ``TILE_CUT_HALF_WIDTH_M`` + one raster cell of the
# tile boundary, or outside it, is a seam cell, and any island touching one is
# refused whole and reported (``refused_reason`` "tile_line").  Both tile
# builds apply the same geometric test to the shared line, so the verdict
# cannot disagree — the determinism property the spec's rule is FOR.
#
# The trade is the spec's own ("some lawful cuts near seams are given up to
# buy a verdict that cannot disagree across a seam"), now actually in force.
# "0" restores the data-extent-only test byte-identically.
OLS_SEAM_TILE_LINE_REFUSAL = (
    _os.environ.get("O4_OLS_SEAM_TILE_LINE_REFUSAL", "1") == "1")

# ── OLS ROAD REGRADE (owner direction 2026-07-28, SPJC 16R fan) ─────────
# The corridor mask (2026-07-25) makes the OLS cut ABSENT over surface
# road/rail corridors, so the road keeps its own embankment.  Where the
# corridor crosses an admitted penetration ISLAND that is exactly wrong:
# the DEM hill the law cuts back everywhere else is left standing as a
# road-width causeway 3-6 m proud of the fan, carrying grades far beyond
# what a ground vehicle route allows (measured SPJC 16R: 12.8 % and
# 13.2 % over 10 m steps on the two flanking service roads).  With this
# ON, such a road is REGRADED instead: the OSM way is the road SPINE,
# carrying a continuous longitudinal profile — cut-only against the
# DEM, capped at ``SERVICE_ROAD_MAX_GRADE`` (the ground-vehicle grade
# law, single source), bounded by the composed OLS ceiling over
# admitted cells — so the road descends THROUGH the hill with the cut.
# Emitted as TWO matching ``service_junction`` half-shapes (ref
# ``ols_road``), half a corridor width outward each side of the spine,
# welded along it, outer edges under the service-road LATERAL rule
# (``SERVICE_ROAD_MAX_TRANSVERSE``); the graded segment follows the
# spine at least ``OLS_ROAD_REGRADE_FOLLOW_M`` past the OLS in both
# directions and lands ON the DEM at both ends.  Sub-gate of
# ``OLS_CUT_ENABLED``; "0" restores the embankment behavior
# byte-identically.
OLS_ROAD_REGRADE_ENABLED = (
    _os.environ.get("O4_OLS_ROAD_REGRADE", "1") == "1")
# The graded road follows the spine AT LEAST this far past the OLS
# surface footprint in both directions before blending into the DEM
# (owner 2026-07-28: "at least 100m past the OLS in both directions,
# DEM on both ends") — extended further where the service-road grade
# needs more length to meet the terrain, clamped at the way's end when
# the way itself stops sooner (an end already at the DEM is a lawful
# blend point).
OLS_ROAD_REGRADE_FOLLOW_M = 100.0

# GAP-FILL + DRAINAGE SPINE (user design ruling 2026-07-09,
# docs/chain_identity_one_solve_plan.md): ground ENCLOSED between
# pavements grades as ONE unit — boundary = the pavement chains
# verbatim, interior = a drainage spine emitted as an open
# constrained way.  Node economy per the performance ruling: the
# spine is the only new geometry.
GAP_FILL_SPINE_ENABLED = (
    _os.environ.get("O4_GAP_FILL_SPINE", "1") == "1")
GAP_FILL_SPINE_STEP_M = 15.0
# Gaps wider than this stay with the corridor-band emitter (the
# facing graded corridors no longer overlap — the middle is
# legitimately ungoverned terrain).
GAP_FILL_MAX_WIDTH_M = 175.0
GAP_FILL_MIN_AREA_M2 = 100.0
# ENCLOSED-POCKET INTERIOR DEPTH FLOOR (owner ruling 2026-07-19, HECA
# round 2 "steep pits in enclosed pavement areas"): pockets the gap-fill
# emitter SKIPS (wider than GAP_FILL_MAX_WIDTH_M, foreign shape inside,
# parent straddle) ride raw DEM — and at HECA the DEM inside enclosed
# infields carries surface-model pits down to 13.9 m below the pavement
# lip (measured survey 2026-07-19: 131 pockets, worst -13.88 m over a
# 3.4 km2 infield).  Flat desert infields do not genuinely drop that
# far; these are artifacts.  ``emit_gap_interior_floor`` clamps pocket
# interiors to no lower than (pavement-lip median - this depth),
# emitting flat pit-fill patches ONLY where the DEM actually violates
# the floor (no-op economy: lawful terrain rides the ground untouched,
# so the owner's "large infields follow terrain" ruling holds down to
# drainage depth).  0 disables the pass entirely.
GAP_FILL_INTERIOR_FLOOR_DEPTH_M = float(
    _os.environ.get("O4_GAP_FILL_INTERIOR_FLOOR_DEPTH_M", "2.5"))

# ── DRAINAGE-SPINE LAW (owner field report 2026-08-02) ────────────────
# Owner: the drainage spine of an enclosed interior must run BELOW the
# LOWER of the two pavements bounding it — ground enclosed between
# pavements drains INTO the spine, so a spine at or above either edge is
# a dam, not a drain.  Measured at HECA before the fix: 182 spine
# vertices at or above their lower bounding pavement edge, on 21 spines
# that block drainage outright; the mechanism is the lateral corridor
# ceiling, which in zone 3 rises at +5 %/m away from the edge and so
# permits an interior HILL once the spine is far enough from both
# parents (a code-E taxiway's ceiling crosses back above the pavement
# edge at d ≈ 25 m; HECA's spines sit at d ≈ 67 m).
#
# THE LAW: ``grade_law.drainage_spine_envelope`` — the same corridor
# FLOOR as ``adjacent_ground_envelope`` (the crater guard: a spine may
# never sink below the ground the lateral law supports), and a CEILING
# tightened to at most this far below EACH bounding pavement edge, which
# composes over the two parents to ``min(edge₁, edge₂) − FALL``.  ONE law
# with TWO readers — the analytic interval (``gap_fill._spine_interval``)
# and the solver's frozen parent specs
# (``gap_fill._freeze_spine_parent_specs``) — plus the post-projection
# re-clamp, so the emitted spine cannot drift above the pavement the
# LATE ``final_grade_projection`` leaves behind.
#
# 0.30 m is PROVISIONAL — the owner may move it.  It is a drainage
# fall, not a standards figure: no FAA/EASA/ICAO clause fixes a minimum
# depth for an interior swale, so this is the smallest fall that reads
# as a drain rather than as emit-rounding noise (the patch quantises
# altitudes at 0.1 m, so 0.30 m is three quanta).
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: the field-report fix batch ``0b9efaf``, which built both
# halves in lockstep — the solver-side minimum fall and the
# ``check_grade`` twin — against the owner's flown drainage report).
# ``O4_DRAINAGE_SPINE_LAW=0`` restores the un-clamped gap spines.
# STANDING LAW (owner 2026-08-05, no gates): Drainage-spine law.
# The ``O4_DRAINAGE_SPINE_LAW`` gate and its env override are DELETED.
DRAINAGE_SPINE_LAW_ENABLED = True

# ── SOURCE-COVERAGE INVARIANT, WIRED (owner field report 2026-08-02) ──
# ``verification.check_source_coverage`` — emitted pavement must COVER the
# source pavement, with no INTERIOR hole for X-Plane to interpolate
# terrain across — has existed since the coverage work and has ZERO call
# sites: nothing has ever run it on a build.  The owner flew four such
# holes at HECA (the largest 839.9 m²).  With this gate ON the build's
# verification pass runs it and reports every enclosed uncovered piece
# ≥ ``SOURCE_COVERAGE_MIN_AREA_M2`` with ≥
# ``SOURCE_COVERAGE_MIN_ENCLOSED_FRAC`` of its perimeter against emitted
# pavement.
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: the field-report fix batch ``0b9efaf`` wired it, and the
# flip battery measured its cost — the whole-airport union + difference the
# comment below worried about does not move any airport's verification
# phase (the flip's entire delta is inside the solve phase).  It is a
# REPORTING instrument: per docs/RULINGS.md "the goal is LAW COMPLIANCE,
# not instrument-zero", the rows it adds are visibility, not violations.
# ``O4_SOURCE_COVERAGE_CHECK=0`` returns it to zero call sites.
SOURCE_COVERAGE_CHECK_ENABLED = (
    _os.environ.get("O4_SOURCE_COVERAGE_CHECK", "1") == "1")
SOURCE_COVERAGE_MIN_AREA_M2 = 5.0
SOURCE_COVERAGE_MIN_ENCLOSED_FRAC = 0.70
DRAINAGE_SPINE_MIN_FALL_M = float(
    _os.environ.get("O4_DRAINAGE_SPINE_MIN_FALL_M", "0.30"))

# INTERIOR FLOOR PASS — DISABLED BY OWNER RULING 2026-07-24.
#
#   "The adjacent ground law should enforce a gentle slope down from
#    pavement; once we're past the grade law zones on a large infield, we
#    want to blend back into DEM.  Let's disable trying to override the
#    DEM once we're past the grade law zones for now."
#
# This RESTORES the round-8 interior-rings design, which already said
# "Terrain INSIDE ring 2 stays open-floor (large infields lawfully follow
# terrain)" (see GAP_FILL_INTERIOR_RINGS_ENABLED below).  The 2026-07-19
# floor pass contradicted that: it is the ONLY thing in the subsystem that
# overrides the DEM beyond the graded zones, and at SPJC it raised 172,810
# of a 235,167 m2 pocket — 73 % of a 15-hectare infield — toward the
# pavement law surface, standing ~3 m proud of the taxiways ringing it.
#
# What SURVIVES the ruling: the collar rings (ring 1 at the drainage lip,
# ring 2 at the parent's graded band edge) still carry the per-zone
# drainage law off the pocket's own pavement ring, so the "gentle slope
# down from pavement" is unchanged.  Only the CORE INSIDE ring 2 reverts
# to terrain.
#
# What it COSTS: the pass was added for HECA's surface-model pits (131
# pockets, worst -13.88 m below the lip).  Those ride raw DEM again.  If
# in-sim shows genuine artifact craters that matter, the answer is a
# narrower re-enable — an ENCLOSURE test so only a real bounded depression
# fills, rather than every square metre sitting below the law surface —
# not simply flipping this back on.
#
# "for now" per the ruling: this is the reversible switch.  The depth
# constant above is retained for the re-enable.
GAP_FILL_INTERIOR_FLOOR_ENABLED = (
    _os.environ.get("O4_GAP_FILL_INTERIOR_FLOOR", "0") == "1")

# GAP INTERIOR RINGS (ratified design 2026-07-11, STATUS commit
# dde6d3c; REVISED per Noah's in-sim round-8 ruling): a single mid-gap
# drainage spine cannot enforce the lawful graded-band profile off
# pavement when the enclosed interior genuinely drops — the mesh spans
# pavement edge to spine in one leg, so a low spine puts the whole
# drop AT the pavement edge (CYXY evidence node
# 60.7210897,-135.0776149: 73 % at the edge where the band law allows
# 5 %).  Gaps therefore additionally emit interior offset RINGS as
# constrained breaklines inside the (still verbatim) gap face,
# mirroring the exterior adjacent-ground band cross-section bent
# around the gap: ring 1 at the drainage-lip breakpoint
# (ADJACENT_GROUND_LIP_WIDTH_M) and ring 2 at the parent's graded
# band-edge breakpoint (runway strip half-width / taxiway OMGWS
# half-width / apron shoulder).  ROUND-8 SEMANTICS: both rings are
# ALWAYS complete, unbroken, concentric closed loops (per-arc
# violation gating created ragged walls at every arc end in-sim); the
# gating lives in the VALUES — each station carries
# clamp(terrain, floor, ceiling) at its point-law distances, so the
# ring rides lawful terrain invisibly and pins only where the law
# demands, with along-ring continuity by construction.  A gap whose
# every station of both rings is a value no-op skips its rings
# entirely (all-or-nothing node economy).  Terrain INSIDE ring 2
# stays open-floor (large infields lawfully follow terrain).
# DEFAULT ON for Noah's in-sim review (the round-8 flip, commit
# 53da9c2 at HEAD; env O4_GAP_FILL_INTERIOR_RINGS=0 restores the
# ring-less gap fill).  REQUIRES the gap-fill spine gate: rings are
# constructed by the gap emitter, so enabling them with
# O4_GAP_FILL_SPINE=0 is a configuration error (hard error in
# gap_fill.emit_gap_fill_spines, the fail-loudly doctrine).
GAP_FILL_INTERIOR_RINGS_ENABLED = (
    _os.environ.get("O4_GAP_FILL_INTERIOR_RINGS", "1") == "1")

# POCKET COLLAR RINGS (arc B1, 2026-07-24).  The interior rings above are
# built only inside ``_emit_one_gap``, so a pocket the spine emitter SKIPS
# — wider than GAP_FILL_MAX_WIDTH_M — gets no drainage collar at all, and
# the only thing that ever reached it was ``emit_gap_interior_floor``'s
# flat pit clamp.  Measured SPJC 2026-07-24: a 235,167 m2 pocket (461 m
# short dimension vs the 175 m gate) received a single FLAT 158,651 m2
# patch at 16.1 m — 2.7-3.4 m ABOVE the taxiway junctions ringing it, on
# an 8 m axis-aligned sample staircase, standing 0.50 m off the pavement
# instead of welded to it.  Owner ruling 2026-07-24: a skipped pocket must
# first get the SAME two closed collar rings (zone drainage law off its own
# pavement ring), and only THEN a pit treatment for a genuine central drop.
# With this ON, ring construction runs for width-skipped pockets too.
# Foreign-shape / parent-straddle pockets stay excluded (they already carry
# partial coverage by design).  Default OFF pending in-sim.
POCKET_COLLAR_RINGS_ENABLED = (
    _os.environ.get("O4_POCKET_COLLAR_RINGS", "1") == "1")

# CONFORMANCE CUT-LAW CLAMP (2026-07-25).  The final epsilon-wedge weld
# (``conformance.enforce_conformance(tol=0.01)``) values every T-vertex it
# inserts by a plain lerp of the host edge's emitted altitudes.  On a
# CUT-ONLY shape whose two host vertices are both ceiling-limited, that
# lerp reproduces the analytic ceiling — which floats ABOVE the terrain
# wherever the DEM dips between the hosts, breaking the shape's own
# "cuts never fill" law (measured SPJC 2026-07-25: two inserted vertices
# +2.12 / +2.22 m over the DEM envelope on the ``runway_end_resa``
# daylight row; the emitter itself was lawful at n = 24, the weld took it
# to n = 32).  With this ON, an insert into a cut-only receiver is bounded
# by ``min(lerp, DEM)`` — the receiver's OWN law re-applied, not a foreign
# claim.  Gate OFF ⇒ byte-identical to the pre-fix emit.
CONFORMANCE_CUT_CLAMP_ENABLED = (
    _os.environ.get("O4_CONFORMANCE_CUT_CLAMP", "1") == "1")

# ADJACENT-GROUND BAND RAY OCCLUSION (2026-07-25).  An adjacent-ground
# band's outward station scan
# (``adjacent_ground._build_cut_bands`` / ``_build_fill_bands``) sampled
# the DEM out to the full family reach (100 m) with NO test for pavement
# standing IN the ray.  Diagnosed at CYXY shapeID 395: junction 129's deep
# cut slab marched straight THROUGH apron 132 + junction 131 — the lidar
# reads the built apron bench (~703 m) as "terrain needing a cut", so
# daylight never closes — and the after-the-fact exact clip
# ``poly.difference(static_union)`` left the band wrapping the apron's NE
# corner with a ~1 m drop hugging its edge.  Owner ruling 2026-07-25:
# "Yes for adjacent ground using a ray occlusion, it should stop at
# pavement" — i.e. A LATERAL BAND'S OUTWARD REACH IS MEASURED THROUGH FREE
# GROUND ONLY: the scan terminates at the first pavement hit and the
# station's band depth is the last free-ground sample before it.  The
# occluding pavement grades its own frontage (its bands march outward
# toward the stopped band), so no ground is left ungoverned.  Mirrored in
# ``verification.check_adjacent_ground`` (MIRROR 5) off the SAME helper and
# the SAME published geometry, so the validator never mints a
# should_cut/should_fill against ground the emitter lawfully stopped short
# of.  Gate OFF ⇒ byte-identical to the pre-fix march.
BAND_RAY_OCCLUSION_ENABLED = (
    _os.environ.get("O4_BAND_RAY_OCCLUSION", "1") == "1")

# HALF-CORRIDOR CUT CAP (owner ruling 2026-07-26, CYXY shape 337).  Ray
# occlusion alone stops a cut band AT the facing pavement's edge, so the
# zone-3 cut of one frontage steamrolls the whole corridor between two
# pavements and terminates as a wall 0-5 m short of the neighbour (CYXY:
# junction 130's zone-3 band reached to taxiway 132's edge, shaving
# 1.3-2.9 m off the natural cross-slope).  With this ON, each station's
# CUT cap is additionally clamped to HALF its occlusion distance, so two
# facing frontages meet mid-corridor and the terrain between them keeps
# its natural transition.  Occlusion is +inf where no pavement faces the
# station (and everywhere with ray occlusion OFF), so the clamp is a
# no-op outside true pavement-to-pavement corridors.
ADJACENT_GROUND_CUT_HALF_CORRIDOR_ENABLED = (
    _os.environ.get("O4_ADJACENT_GROUND_CUT_HALF_CORRIDOR", "1") == "1")

# OPEN-FRONTAGE DRAINAGE SPINE (slice B pilot, user design ruling 3
# 2026-07-09; docs/chain_identity_one_solve_plan.md §Slice B).  The
# OPEN corridor generalization of the enclosed-gap spine: ground BETWEEN
# two facing airside pavement chains that is bounded on its long sides by
# pavement but OPEN at the ends (a runway ↔ parallel-taxiway corridor and
# similar) — NOT an interior ring, so the enclosed-gap path never owns it.
# Emit ONE face per corridor (long sides = the two pavement chains
# verbatim, ends = straight closures across the mouth — TRUE outer edges)
# + ONE drainage spine (the crown/valley), superseding the per-pavement
# corridor-band march there (which tears at band-vs-band clip seams once
# the legacy strips vacate the open frontage).  DEFAULT OFF — this is a
# pilot Noah has not reviewed in-sim; every emission must be a no-op with
# the gate off.  The gate ``O4_OPEN_FRONTAGE_SPINE`` is read at its call
# site (``gap_fill.py``); the config mirror constant had no reader and was
# deleted in the dead-code round.
#
# Morphological-closing radius used to DETECT open corridors: a closing
# of the airside union (buffer out then back in) bridges any open channel
# up to 2*radius wide.  Half the gap-fill max width, so a corridor up to
# GAP_FILL_MAX_WIDTH_M across is detected; wider regions are legitimately
# ungoverned terrain and stay with the corridor-band / daylight law.
OPEN_FRONTAGE_CLOSE_M = GAP_FILL_MAX_WIDTH_M / 2.0

# ── EXCAVATION-RIM POCKETS (owner/Fable ruling 2026-08-12b, ruling 3) ──
# "A coverage hole whose boundary is >= 75 % graded features (apron /
# roads / junctions / groundside pavement / pads) is ENCLOSED for
# gap-fill purposes even with an open segment."
#
# The measured site: HECA's knoll at 30.1136676,31.4086362 — a ~1,000 m2
# coverage hole at the rim of an apron excavated ~13 m below natural
# grade, bounded by apron E/S, groundside W, service road/junction +
# building pad N and OPEN to the SW.  It is inside both gap-fill floors
# (min 100 m2, max width 175 m) and was refused by ONE test: it is not an
# interior ring of the airside union, so it was never a candidate at all
# (measured: no `[gap-fill] candidate` line within 40 m of it in either
# arm).  R19-2 closed the ENCLOSED-hole case; this is the open-boundary
# one, and a pocket whose rim is graded on three sides drains to those
# features exactly as an enclosed one does.
#
# THE FRACTION IS THE LAW.  Below it the region is open terrain that the
# corridor-band / daylight law owns; at or above it the ground is
# surrounded by graded features that already fix its rim values.
GAP_FILL_RIM_POCKET_GRADED_FRACTION = 0.75
# DEFAULT ON (owner ruling 2026-08-14, closing the staged-solve round's
# S4/s4rim2 arc; supersedes the 2026-08-12b park).  The 2026-08-12b
# off-face channel (1,238/1,330 airside rows, median 63 m) was
# attributed and closed in two increments: the stage partition made
# rim-pocket spines UNCONDITIONALLY stage B (RULINGS 2026-08-14 —
# an airside rim arm is READ as immutable boundary, never written),
# and the enclosure-host stamp replaced the false "enclosed gap of the
# airside union" premise.  Measured at the flip (lane/s4rim2): the
# knoll grades (93.7-class), HECA law-true 7221->7139, OTHH airside
# unchanged, and the remaining airside churn is the lawful near-cap
# membership band (82<->82 rows at 1.006-1.015% vs the 1.0% cap),
# vertex moves <=0.33 m.  The owner ruled the flip with the in-sim
# pass at the knoll site as the final judge.
GAP_FILL_RIM_POCKETS_ENABLED = (
    _os.environ.get("O4_GAP_FILL_RIM_POCKETS", "1") == "1")

# RIM-POCKET ABSORPTION GATE — RETIRED (owner ruling 2026-08-13, RULINGS
# "OTHH -639 ADJUDICATED"; S3 dossier §6, lane S4).  `O4_RIM_PRESOLVE_ABSORB`
# used to withhold rim-pocket spine vertices from the one solve.  It was
# measured INERT IN PRODUCTION: `gap_fill._rim_pocket_polys` returns []
# when GAP_FILL_RIM_POCKETS_ENABLED is false (the shipped default), so
# `rim_ids` is empty and the branch never ran — the 29→9 OTHH airside
# claim behind it was never shipped.  It is also the wrong SHAPE of
# boundary: a per-construct opt-out of one groundside family from the one
# solve is exactly the ad-hoc form the staged partition
# (`solve_stage.py`) replaces.  Under staging, a construct's admission is
# decided by its STAGE TAG, not by a flag.

# ── SLICE B — solver absorption of terrain roles (staged) ──────────────
# docs/slice_b_solver_absorption_design.md, Stage B0.  The absorption moves
# the three post-solve terrain emitters (runway-end skirt, gap-fill spine,
# adjacent-ground graded strip) PRE-SOLVE so their ring vertices become
# first-class solver variables the way the object-bridge plate roles
# already are (solver_primitives.PAVEMENT_ROLES).  These gates are the
# ADMISSION scaffolding only: the per-role constraint builders are stages
# B1-B3 and do NOT exist yet.
#
# ONE_SOLVE_TERRAIN is the MASTER gate; the three per-role sub-gates select
# which terrain graph roles are admitted to the canonical node registry and
# the solver node list (solver_primitives.admitted_terrain_roles).  With the
# master gate off (the default) the admitted set is EMPTY, so the node list,
# the constraint graph and the solve are byte-identical to today.  With the
# master gate on but every sub-gate off (equally the default) the admitted
# set is still empty — admission of an empty role set is a structural no-op
# — which is exactly Stage B0's landing condition: the primitive and the
# scaffolding exist, nothing is admitted yet.
# ROUND-7 REVIEW DEFAULTS (Noah, 2026-07-11): the whole slice-B bundle is
# ON BY DEFAULT for the in-sim ratification build.  Set any gate's env var
# to 0 to fall back to the pre-absorption path (every stage was proven
# byte-identical gates-off at its landing).
ONE_SOLVE_TERRAIN = (
    _os.environ.get("O4_ONE_SOLVE_TERRAIN", "1") == "1")
ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT = (
    _os.environ.get("O4_ONE_SOLVE_TERRAIN_RUNWAY_END_SKIRT", "1") == "1")
# RESA CUT admission (owner ruling 2026-07-24, arc R).  The owner's
# framing: the runway-end envelope is LAW the solver should enforce —
# "ensuring terrain within a given area relative to a runway is within an
# envelope, doesn't rise too steeply, or sink too quickly" — rather than
# geometry stamped after the fact.  The cut is the skirt's twin (one
# ``grade_law.runway_end_envelope``, one anchor, one corridor; they differ
# only in which bound they read).
#
# The measurement that settled it (instrumented CYXY build, gates at
# defaults): the cut's anchor is NOT the immutable CIFP threshold, it is
# the pavement-EXIT elevation — and that read MOVES after the pre-solve
# emission slot.  212 anchor-class reads; the 106 numeric ones drifted
# median 0.110 m / p90 0.150 m / max 0.164 m, with 88 of 106 over 0.05 m;
# the other 106 returned None pre-solve and resolve to real solved values
# post-solve.  The 0.15 m mode is the CROWN (the solve runs uncrowned and
# writeback emits z = z' - c).  Overrun-pavement ends add ~0.4 m (KCLT
# 18L); runway flex adds whatever the runway grade caps price as slack
# (no displacement budget — owner ruling 2026-08-05).
#
# So a pre-solve stamp bakes a stale reference at essentially every
# airport.  Admitting the cut B3-style (free variable + a ONE-SIDED
# interval edge to its frozen-nearest anchor, writeback re-evaluated
# against the solved crowned reference) tracks it by construction — and
# makes the cut/fill twin-vertex disagreement at d = 0 UNREPRESENTABLE,
# since a shared vertex resolves to one variable and one variable cannot
# disagree with itself.
#
# Nothing floats: the encoding gives these nodes no force (no within-shape
# grade rule, no fairing) and coupling is one-way host-authoritative, so a
# terrain node can never pull pavement.  Same grade the adjacent-ground
# bands already ride, default ON today.
#
# HARD DEPENDENCY: requires the skirt sub-gate above (the cut is emitted
# inside the skirt emitter's pre-solve call) AND RUNWAY_END_RESA_ENABLED
# (no cut, nothing to admit).  A partial gate set is a misconfiguration —
# fail LOUDLY, per the GRADED_STRIP precedent below.  Default OFF; flips
# together with O4_RUNWAY_END_RESA on one owner sign-off.
ONE_SOLVE_TERRAIN_RUNWAY_END_RESA = (
    _os.environ.get("O4_ONE_SOLVE_TERRAIN_RUNWAY_END_RESA", "1") == "1")
ONE_SOLVE_TERRAIN_GAP_FILL_SPINE = (
    _os.environ.get("O4_ONE_SOLVE_TERRAIN_GAP_FILL_SPINE", "1") == "1")
ONE_SOLVE_TERRAIN_GRADED_STRIP = (
    _os.environ.get("O4_ONE_SOLVE_TERRAIN_GRADED_STRIP", "1") == "1")
# Slice B stage B3 ORDER 1 (construction move) sub-gate, DEFAULT OFF and
# deliberately SEPARATE from the B0 admission sub-gate ``ONE_SOLVE_TERRAIN_
# GRADED_STRIP`` above (which stays OFF until B3 order 2, variable
# admission).  This gate moves the adjacent-ground band FOOTPRINT
# derivation (the frontage/march/zone-split/clip geometry) PRE-SOLVE onto
# ``layout.adjacent_ground_presolve`` from a DEM-seeded pavement-edge
# estimate; the post-solve emitter then CONSUMES those frozen footprints
# instead of re-marching, but still VALUES every vertex analytically
# through the existing resampler (so gate-ON output is value-equivalent to
# gate-OFF up to the enumerated seed/late-feature footprint deltas).  It
# does NOT admit any band vertex to the solver — that is order 2 under the
# admission gate.  Requires the adjacent-ground law itself
# (``ADJACENT_GROUND_LAW_ENABLED``) to be ON to have any effect.
ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT = (
    _os.environ.get("O4_ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT", "1")
    == "1")

# Slice B stage B3 ORDER 3 FULL-EXTENT COVERAGE sub-gate, DEFAULT OFF (a
# B4 prerequisite; docs/slice_b_solver_absorption_design.md §B3).  Closes
# the analytic-fallback coverage gap that opens with legacy
# surface_clearance OFF: the post-solve emitter RE-MARCHES each band on the
# FINAL SOLVED pavement edge, but the pre-solve construct march references
# the reach-band worst case, which for junction/apron edges the connecting
# solve grades DOWN into terrain is BOTH a poor kind predictor (the band
# floor is often ABOVE the eventual solved edge — a degenerate route-reach
# interval) AND leaves the deep-cut zone rows spaced only at the band
# breakpoints (a >``_ROW_RANGE_M`` depth gap the resampler cannot bridge).
# With the gate ON the construct stages a FULL coverage GRID — every
# non-skipped station's zone rows span the whole family reach in BOTH cut
# and fill directions, densified to <= ``ADJACENT_GROUND_COVERAGE_DEPTH_
# STEP_M`` in depth — so whatever kind/depth the emit re-march produces on
# the solved edge, a solved zone row lies within range (over-coverage is
# unused solved variables — the established e1ff071 worst-case pattern).
# Only the ZONE-ROW GRID widens; the analytic band footprint the emitter
# actually emits is unchanged (it re-marches on the solved edge, never on
# this grid), so widening coverage cannot change a legacy-ON valuation.
# Requires the ADMISSION sub-gate ``ONE_SOLVE_TERRAIN_GRADED_STRIP`` (the
# only path that solves the zone nodes and reads them back); a no-op
# without it.  DEFAULT OFF: the current defaults must stay byte-identical
# because a widened grid changes the legacy-ON valuation lookups (the
# fallback count would drop) — that output change rides with B4, not with
# the construct move.
# ── SLICE B STAGE B4 — the flip bundle (Noah, round-10 ratification) ──
# ONE review switch that stages the B4 configuration as flip-ready
# DEFAULTS, following the fad621d / 53da9c2 review-defaults convention
# (Noah edits ONE line to flip; every constituent env var still overrides
# so a single gate can be pinned OFF under the bundle).  The B4 bundle is:
#   * legacy surface_clearance OFF  (O4_LEGACY_SURFACE_CLEARANCE)
#   * extended clearance charter ON (O4_CLEARANCE_CHARTER — wingtip strips
#     only; junction/RESA large-area blobs excluded)
#   * full-extent coverage grid ON  (O4_ADJACENT_GROUND_FULL_EXTENT_COVERAGE)
# on top of the round-7 slice-B bundle (already ON).  DEFAULT ON since
# 2026-07-15.  History: the 2026-07-15 KBNA perf round's first flip
# attempt was REVERTED — constituent bisection found two grade-law
# blockers the CYXY-only flip-gate bake (staged 2026-07-11) missed on
# post-KBNA-round-4 dev:
#   1. coverage grid ⇒ SPJC runway 16L/34R 8.60 % longitudinal spike: a
#      grid zone-row point 0.49 m off the runway edge became a solver
#      variable and interned onto the runway ring through the canonical
#      registry's 0.5 m radius.  Fixed by the zone-node static keep-out
#      (``ADJACENT_GROUND_ZONE_STATIC_KEEPOUT_M``, adjacent_ground
#      ``_split_zone_rows_off_static``).
#   2. legacy deletion ⇒ CYXY 4 junction spine violations (worst 11 %):
#      band clip vertices ON a foreign pavement edge took zone-row values
#      instead of that pavement's solved edge value, and the final weld
#      stamped them into the junction rings — sites the legacy clearance
#      strips used to occupy.  Fixed by the static-edge value weld in the
#      band resampler plus the post-weld crown field completion
#      (pipeline; band-minted ring vertices previously read crown drop 0,
#      so the validator measured pairs against the wrong crown target).
# With both mechanisms fixed the flip battery (test_pavement_grade,
# test_single_graph_acceptance, test_route_reach at SPJC/CYXY/HECA/SPLP)
# matches the pre-flip baseline failure set.
# THE B4 GATE-OF-GATES IS GONE (``O4_B4_FLIP``, retired 2026-08-05 under
# RULINGS "BUILD-COMPLETE-THEN-DEBUG").  It was the audit's worst
# provenance defect: a meta-gate that rewrote OTHER gates' defaults as a
# POST-ASSIGNMENT override, deliberately structured to leave a plain "0"
# literal in the source "so the delivery stamp stays accurate" — with the
# effect that every default build REPORTED these laws off in
# ``o4_provenance_gates_on`` while RUNNING them on.  Its two live targets
# are resolved here to the state the default build already ran:
# full-extent coverage ON, and the extended clearance charter ON (see
# ``clearance.py``).  Nothing selects the other arm any more.
ADJACENT_GROUND_FULL_EXTENT_COVERAGE = True
# Depth-direction spacing (m) of the full-extent coverage grid's zone
# rows.  Must be <= the resampler's ``_ROW_RANGE_M`` (30 m) so every
# emit-time band vertex, at any lateral depth, finds a solved row of its
# kind within range.  Also the design's node-budget DIET lever: a coarser
# step trades coverage density for fewer solver variables at deep-reach
# airports (KBNA).  Byte-inert unless the coverage gate is ON.
ADJACENT_GROUND_COVERAGE_DEPTH_STEP_M = float(
    _os.environ.get("O4_ADJACENT_GROUND_COVERAGE_DEPTH_STEP_M", "25.0"))
# Zone-node static keep-out (B4 flip defect 1, 2026-07-15).  A band-corridor
# zone-row point that lands ON or NEXT TO static pavement must never become a
# solver variable: the band footprint is clipped away there, its DEM-clamped
# value is meaningless under pavement, and — the measured defect — a point
# within the canonical-point registry's 0.5 m merge radius of a pavement
# ring vertex INTERNS onto that vertex's bucket, stamping the zone value
# onto the pavement ring (SPJC 16L/34R: a depth-50 m grid row point 0.49 m
# off the runway edge wrote 27.76 into the runway profile — an 8.6 %
# longitudinal spike).  Zone points inside pavement, or within this margin
# of any static-shape boundary, are dropped at construction (the margin
# clears the 0.5 m registry radius with headroom).
ADJACENT_GROUND_ZONE_STATIC_KEEPOUT_M = float(
    _os.environ.get("O4_ADJACENT_GROUND_ZONE_STATIC_KEEPOUT_M", "0.75"))

# APRON edges.  NO code mandates grading beyond an apron edge (positive
# research finding): the only governed band is the FAA-RECOMMENDED
# shoulder — 10 ft (3 m) at 1–3 % down, then 3–5 % beyond (FAA AC
# 150/5300-13B §5.9.2, a RECOMMENDATION, not a requirement; ICAO §3.13 /
# EASA E.360 bound only apron-SURFACE slopes + rising stand-clearance
# obstacles).  Beyond the shoulder the corridor takes zone-3 semantics
# (rising ground ≤5 %, floor free); the tighter stand-clearance / wingtip
# ceiling is applied separately where stricter.
APRON_SHOULDER_WIDTH_M = 3.0
APRON_SHOULDER_MIN_DOWN_SLOPE = 0.01
APRON_SHOULDER_MAX_DOWN_SLOPE = 0.03
# The FAA "then 3–5 %" continuation beyond the shoulder (§5.9.2): the
# DOWN-fill RENDER TARGET the emitter (slice 3) uses inside the zone-3
# free-floor region where the DEM has fallen away — analogous to the
# zone-1 mid-band render target, NOT a mandatory corridor (the law's
# zone-3 ceiling is the ≤5 % UP cap above; the floor stays free).
APRON_BEYOND_SHOULDER_MAX_DOWN_SLOPE = 0.05
# Retaining-WALL threshold (ruling 3): a vertical wall face replaces
# graded fill where the DEM sits more than this many metres below the
# apron shoulder edge (reuse the tunnel ``retaining_wall`` emitter; tune
# at KSVH / KEXX — slice 3).
APRON_EDGE_WALL_MIN_DROP_M = 1.5

# ── APRON WALL CONTINUITY (owner in-sim report "ramps and sharp drops",
# diagnosed 2026-07-25 at SPJC apron -10153's SW frontage) ─────────────
# Two defects broke ONE 237 m apron frontage into a scatter of confetti
# walls and bare, un-walled ground:
#   1. MULTIPART DROP.  ``adjacent_ground._emit_apron_walls`` clipped each
#      wall run against the static union, the just-emitted graded strips
#      and the boundary, then emitted only when the residue was a single
#      ``Polygon`` — any run a neighbouring junction band NICKED became a
#      MultiPolygon and was discarded WHOLE.  Measured at SPJC: a 173 m /
#      167.9 m² run lost to two nicks totalling 5.29 m² (3 %); airport-wide
#      4 runs / 240.4 m² of owed wall face silently vanished.  The graded-
#      band emitter 500 lines up already decomposes its own clip residue —
#      the wall path simply never adopted the idiom.
#   2. THRESHOLD FLAP.  A station qualifies for a wall at a drop strictly
#      greater than ``APRON_EDGE_WALL_MIN_DROP_M``; SPJC stations sitting
#      at 1.4988 m / 1.4936 m — millimetres under the 1.5 m line — split
#      one continuous frontage into two runs with a bare notch between.
# The gate covers both fixes (they interlock: hysteresis merges runs, and
# a merged run is exactly the long run most likely to be nicked into a
# MultiPolygon).  Gate OFF ⇒ byte-identical to the pre-fix emitter.
# STANDING LAW (owner 2026-08-05, no gates): Apron wall continuity (owner 2026-07-25).
# The ``O4_APRON_WALL_CONTINUITY`` gate and its env override are DELETED.
APRON_WALL_CONTINUITY_ENABLED = True
# CONFETTI GATE (fix 1's companion).  Decomposing the clip residue also
# surfaces the genuinely tiny pieces the whole-run drop used to hide — at
# SPJC three surviving walls were 2.8–3.9 m² slivers.  A wall part shorter
# along the frontage than this, or smaller in area than
# ``APRON_WALL_MIN_AREA_M2``, protects nothing a neighbouring band does not
# already cover and reads in-sim as a spike; it is skipped and COUNTED (the
# emitter logs the tally — no silent caps).  6 m ≈ one 5 m station step
# plus slack, the shortest run that can carry a readable vertical face.
APRON_WALL_MIN_RUN_M = 6.0
# Companion area floor for the same gate: the face is a thin strip one
# ``_PAVEMENT_GAP_M`` (1 m) deep, so ~4 m² is the 6 m run's own area with
# clip slack — it catches wedge-shaped residue that is long but vanishing.
APRON_WALL_MIN_AREA_M2 = 4.0
# RUN HYSTERESIS (fix 2).  A wall run only STARTS at a drop above the full
# ``APRON_EDGE_WALL_MIN_DROP_M``, but an already-open run CONTINUES through
# stations down to ``APRON_EDGE_WALL_MIN_DROP_M - APRON_WALL_RUN_HYSTERESIS_M``.
# Classic Schmitt-trigger discipline: the wall's EXISTENCE decision stays at
# the ruled threshold, only its continuation is tolerant, so no wall is ever
# created where the law does not ask for one.  0.3 m spans the DEM's own
# station-to-station jitter at an apron edge with margin.
APRON_WALL_RUN_HYSTERESIS_M = 0.3

# ── APRON WALL SCOPE — pavement adjacency (owner ruling 2026-07-25) ───
# Owner, on the same "ramps and sharp drops" report: "narrowing the scope of
# apron walls so that they only occur if there's adjacent pavement within
# 5m, then we need a wall; if it's open terrain just let the raw Ortho4XP
# dem grade up to the apron edge."  LEAD READING (stated back to the owner
# for confirmation, 2026-07-25):
#   * An apron frontage station qualifies for a retaining WALL only when
#     ANOTHER pavement shape lies within ``APRON_WALL_PAVEMENT_ADJACENCY_M``
#     of it.  There the drop-based wall machinery applies unchanged — there
#     is no room to grade between two built surfaces, so a vertical face is
#     the only lawful answer.
#   * Where the frontage faces OPEN TERRAIN (no pavement inside that
#     radius) the law DECLINES TO GOVERN THE FILL SIDE: no wall AND no
#     shoulder/fill band, and the raw (Ortho4XP-smoothed) DEM is allowed to
#     grade right up to the apron edge.  This is lawful — no code mandates
#     grading beyond an apron edge (see ``APRON_SHOULDER_WIDTH_M``: the
#     shoulder is an FAA RECOMMENDATION, not a requirement).
#   * CUT-side stations are UNAFFECTED.  "Grade up to the apron edge" is the
#     terrain-BELOW case; terrain standing ABOVE the clearance ceiling is a
#     wingtip-clearance obstruction and its cut still applies everywhere.
#   * APRON frontage only — runway / taxiway / junction bands unchanged.
# Mirrored in ``verification.check_adjacent_ground`` (MIRROR 6) off the SAME
# helper (``adjacent_ground.apron_wall_frontage_qualifier``), so the
# validator never mints a ``should_fill`` against apron frontage this ruling
# leaves ungoverned.  Gate OFF ⇒ byte-identical to the pre-ruling scope.
# STANDING LAW (owner 2026-08-05, no gates): Apron wall scope — apron frontage only (owner 2026-07-25).
# The ``O4_APRON_WALL_SCOPE`` gate and its env override are DELETED.
APRON_WALL_SCOPE_ENABLED = True
APRON_WALL_PAVEMENT_ADJACENCY_M = 5.0

# ── RUNWAY-STRIP WALL INADMISSIBILITY (owner ruling 2026-08-01) ───────
# Owner, verbatim class: retaining walls are NEVER lawful at a runway
# edge — "there's very specific requirements for the terrain all around
# runways"; runway surroundings must grade away smoothly (docs/RULINGS.md,
# "Runway-edge terrain law").  Measured at HECA before the fix: 4
# ``retaining_wall`` ways / 19 vertex sites standing inside the code-4
# graded strip (75 m from the 05R/23L and 05C/23C centrelines).
#
# THE LAW: inside the runway STRIP FOOTPRINT
# (``grade_law.runway_strip_wall_keepout_rings`` — CL ±
# ``RUNWAY_STRIP_HALF_WIDTH_BY_CODE`` over the runway, plus the
# ``runway_end_corridor_half_width_m`` end corridors)
# ``ROLE_RETAINING_WALL`` is INADMISSIBLE: all three wall emitters skip
# faces there, and a runway never QUALIFIES an apron wall (the runway
# roles leave ``_WALL_SCOPE_PAVEMENT_ROLES``).  No new corridor math —
# the displaced drop relocates into the strip corridor law, which already
# grades to the 75 m edge; beyond it zone 3's free floor makes the terrace
# lawful (adjacent-ground zone law).
# The VALIDATOR half is ``check_grade._check_no_wall_in_runway_strip``,
# built from the SAME law function (lockstep).  Gate OFF ⇒ byte-identical.
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: the field-report fix batch ``0b9efaf``, built from the
# owner's verbatim runway-edge terrain law — "retaining walls are NEVER
# lawful at a runway edge" (docs/RULINGS.md) — with the emitter and the
# ``check_grade._check_no_wall_in_runway_strip`` twin in lockstep.  A law
# this categorical cannot ship behind a default-off gate.
# ``O4_RUNWAY_STRIP_WALL_LAW=0`` restores wall admission inside strips.
# STANDING LAW (owner 2026-08-05, no gates): Runway-edge terrain law: walls are never lawful in a strip (owner 2026-08-01).
# The ``O4_RUNWAY_STRIP_WALL_LAW`` gate and its env override are DELETED.
RUNWAY_STRIP_WALL_LAW_ENABLED = True

# ── RUNWAY-STRIP LAW: PRECEDENCE + ABEAM LONGITUDINAL ─────────────────
# (standards-gap review 2026-08-02 items G-1 general and G-2; spec
# docs/specs/rsa-law-round-spec.md.  ONE gate for both halves — they are
# one law family: the strip's OWN law, on both axes.)
#
# §1 PRECEDENCE (the general form of the wall ruling above).  The runway
# STRIP FOOTPRINT — the same geometry the wall law already owns,
# ``grade_law.runway_strip_wall_keepout_rings`` — is SUPREME: inside it no
# other role's corridor/envelope law may govern ground.  The wall ruling
# was the special case ("no retaining wall face here"); the general law is
# that the STRIP CORRIDOR governs any station in the footprint regardless
# of which shape's frontage the march started from.  The class it kills is
# an APRON corridor whose (much shallower, 3 m-shoulder) envelope reached
# into the strip and stood a 9.7 m wall inside it.  Emitter half: the
# adjacent-ground march DEFERS — a non-runway family's station inside the
# footprint is dropped exactly as the crossing / collared-pocket zones are
# dropped, and the runway family's own march governs that ground.
# Validator half: ``check_grade`` judges ground inside the footprint by the
# STRIP law (zones / transverse / longitudinal), never by the local role's.
#
# §2 ABEAM LONGITUDINAL (the MISSING family).  Between the runway ends the
# strip's ground has a LONGITUDINAL standard of its own, which this repo
# never read or bound:
#   * ICAO Annex 14 Vol I §3.4.13 — "A longitudinal slope along that
#     portion of a strip to be graded should not exceed: 1.5 per cent
#     where the code number is 4; 1.75 per cent where the code number is
#     3; and 2 per cent where the code number is 1 or 2."  (the by-code
#     table below, and the LIVE value: the ICAO shape is by-code.)
#   * FAA AC 150/5300-13B §3.16.5 Standards item 1 — "Longitudinal
#     grades, longitudinal grade changes, vertical curves, and distance
#     between changes in grades for that part of the RSA between the
#     runway ends are the same as the comparable standards for the runway
#     and stopway" — i.e. the runway's own longitudinal cap,
#     ``RUNWAY_MAX_GRADE``, code-invariant.  NAMED here so the phase-B
#     ruleset split (docs/RULINGS.md "Region-specific rulesets") has the
#     FAA constant to key without re-deriving it.
#   * ICAO Annex 14 §3.4.14 — slope CHANGES on the graded strip "should be
#     as gradual as practicable and abrupt changes or sudden reversals of
#     slopes avoided".  Recorded; the rate-of-change half is not bound
#     this round (it needs the vertical-curve machinery the runway
#     profile already owns, and it is a separate gap entry).
RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_BY_CODE = {
    1: 0.020, 2: 0.020, 3: 0.0175, 4: 0.015}
RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_FAA = RUNWAY_MAX_GRADE
# STANDING LAW as of the build-complete-then-debug ruling (docs/RULINGS.md
# 2026-08-05: "NO GATES.  Every believed-in law becomes standing law; O4_
# law gates and their env overrides are DELETED as their territory is
# touched").  ``O4_STRIP_PRECEDENCE`` is GONE — the strip footprint is
# supreme and the abeam-longitudinal law binds, always.  The name is kept
# as a True constant so the march / validator call sites read one text;
# their now-dead gate-off branches are dead code for their owning lane to
# remove.
STRIP_PRECEDENCE_ENABLED = True

# ── SOLVED-BAND EMIT-SIDE CORRIDOR CLAMP (diagnosed 2026-07-25, SPJC) ──
# The GATE-ON band valuation (``adjacent_ground._make_solved_band_resampler``)
# reads the SOLVED band surface: a band vertex within the canonical-point
# registry tolerance (0.5 m) of a solved zone node adopts that variable's
# value.  Defect: the registry interns ACROSS SHAPES.  At SPJC an apron
# 3 m-shoulder zone-row point and a junction 25–30 m CUT zone-row point lie
# 0.19 m apart and intern to ONE canonical variable; the junction's corridor
# claims the clamp, and the apron's writeback then carries that value —
# 34.49 m where the apron's OWN corridor at d=3 m is [36.00, 36.06].  The
# result is a 1.56 m notch in the shoulder at the owner's reported point
# (-12.0339451, -77.1057292); 367 such cross-shape collisions at SPJC.
# The ANALYTIC valuation path is immune BY CONSTRUCTION (it clamps the DEM
# into the corridor), so this gate simply restores that invariant on the
# solved path: every solved value is clamped into THIS shape's own
# ``grade_law.adjacent_ground_envelope`` corridor at the vertex's true
# lateral depth before it is emitted.  A clamp can make two shapes emit
# different values at one canonical point — that is the emitter's supported
# "deliberate wall of two separate nodes" convention (adjacent_ground
# ~:4890), not a tear.
#
# STANDING LAW + INGESTION (owner 2026-08-05): the gate is DELETED.  The
# SAME corridor box this clamp evaluates is now supplied to the ONE
# solve as a directed constraint per band node
# (``adjacent_ground.build_zone_constraint_table`` →
# ``layout.adjacent_ground_zone_boxes``), so the solved value already
# lies inside it.  The emit-side evaluation therefore stops being a
# second valuation and becomes the LOCKSTEP reader of the same law: one
# derivation (``adjacent_ground.zone_corridor_box``), and every metre it
# still has to move is counted as an ingestion residual
# (``band_corridor_clamped_vertices``) — a number that goes to zero when
# the solve consumes the table.
BAND_CORRIDOR_CLAMP_ENABLED = True


def runway_code_number(length_m: float) -> int:
    """ICAO Annex 14 aerodrome reference code NUMBER from runway
    length: 1 (<800 m), 2 (800–1199), 3 (1200–1799), 4 (≥1800)."""
    if length_m >= 1800.0:
        return 4
    if length_m >= 1200.0:
        return 3
    if length_m >= 800.0:
        return 2
    return 1


def runway_strip_half_width_m(length_m: float) -> float:
    """Graded runway-strip half-width (m) from the centerline."""
    return RUNWAY_STRIP_HALF_WIDTH_BY_CODE[runway_code_number(length_m)]


def runway_end_clearance_length_m(length_m: float) -> float:
    """RESA / runway-end graded distance (m) beyond the runway end."""
    return RUNWAY_END_CLEARANCE_LENGTH_BY_CODE[runway_code_number(length_m)]


# Approach-lighting systems (apt.dat row-100 end field) that imply a
# precision instrument approach: ALSF-I (1), ALSF-II (2), Calvert (3),
# Calvert ILS Cat II/III (4), SSALR (5), MALSR (8).  The remaining
# codes (SSALF/SALS/MALSF/MALS/ODALS/RAIL) also serve non-precision
# approaches, so they do not upgrade the class on their own.
PRECISION_APPROACH_LIGHT_CODES = frozenset((1, 2, 3, 4, 5, 8))

# apt.dat row-100 runway markings codes (per end): 0 none, 1 visual,
# 2 non-precision, 3 precision, 4 UK non-precision, 5 UK precision.
PRECISION_MARKINGS_CODES = frozenset((3, 5))
NON_PRECISION_MARKINGS_CODES = frozenset((2, 4))
VISUAL_MARKINGS_CODE = 1


def runway_end_approach_class(
        markings_code: int, approach_lights_code: int) -> str:
    """Approach class of ONE runway end: ``"visual"``,
    ``"non_precision"`` or ``"precision"``.

    Classification ladder: explicit precision markings, else a
    precision-grade approach lighting system, else explicit
    non-precision / visual markings.  Gateway apt.dat data frequently
    leaves both fields 0 on runways that plainly have instrument
    approaches, so a blank row defaults to ``"non_precision"`` — never
    let missing data pick the SHORT end-clearance footprint; only an
    explicit visual marking does that.
    """
    if markings_code in PRECISION_MARKINGS_CODES:
        return "precision"
    if approach_lights_code in PRECISION_APPROACH_LIGHT_CODES:
        return "precision"
    if markings_code in NON_PRECISION_MARKINGS_CODES:
        return "non_precision"
    if markings_code == VISUAL_MARKINGS_CODE:
        return "visual"
    return "non_precision"


def taxiway_code_letter(width_m: float) -> str:
    """ICAO code LETTER inferred from taxiway pavement width (m).
    Widths: A 7.5, B 10.5, C 15/18, D 18/23, E 23, F 25 m."""
    if width_m >= 25.0:
        return "F"
    if width_m >= 23.0:
        return "E"
    if width_m >= 18.0:
        return "D"
    if width_m >= 15.0:
        return "C"
    if width_m >= 10.5:
        return "B"
    return "A"


# ── Size-dependent taxiway grade cap (ICAO Annex 14) ──────────────────
# Narrow taxiways (code letters A/B, pavement width < 15 m) may grade up
# to TAXI_MAX_GRADE_NARROW (3 %); wider taxiways (C–F) stay at the 1.5 %
# TAXI_MAX_GRADE.  Gate default ON in dev (user 2026-06-20: small taxiways
# at CYXY were being held flat when the spec lets them be steeper).  Gate
# OFF restores the uniform 1.5 % taxiway cap — byte-identical to the
# pre-feature build (the cap collapses to TAXI_MAX_GRADE for every letter
# and the emitter skips the code_letter tag).
TAXI_GRADE_BY_WIDTH = _os.environ.get("O4_TAXI_GRADE_BY_WIDTH", "1") == "1"
# ICAO code letters that earn the steeper narrow-taxiway grade cap.
NARROW_TAXI_CODE_LETTERS = frozenset({"A", "B"})

# Prefix for the SYNTHETIC name we assign to a taxi route that has no apt.dat
# designator, so its apt.dat ICAO size code travels WITH it (by name) instead of
# being dropped when grouping edges by name (apt_dat_reader._unnamed_edge_
# component_names).  ``~U1``, ``~U2``, … — one per connected component of unnamed
# taxiway edges.  These ARE real, sized taxi routes (not diagonal sub-stubs), so
# the geometry heuristics that special-case a numeric SUB-ref (``A1``, ``B2`` —
# diagonal connectors) must exclude this prefix — see ``taxi_ref_is_sub_index``.
SYNTH_TAXI_NAME_PREFIX = "~U"


def taxi_ref_is_sub_index(ref) -> bool:
    """True iff ``ref`` is a numeric SUB-reference (``A1``, ``B2`` — a diagonal
    connector / rapid-exit off a main taxiway), which several geometry passes
    handle more conservatively than a main taxiway.  A synthetic ``~U`` serial
    contains a digit but is a MAIN route, so it is explicitly excluded."""
    if not ref or str(ref).startswith(SYNTH_TAXI_NAME_PREFIX):
        return False
    return any(c.isdigit() for c in str(ref))
# Shape roles the size-dependent cap applies to: the taxiway-family rects.
# Junctions, aprons and runways are intentionally excluded — a junction is
# the moving network the taxiways flow THROUGH (kept at the tighter rate),
# not a sized taxiway in the longitudinal-grade sense.
TAXI_GRADE_WIDTH_ROLES = frozenset({
    "primary_parallel", "secondary_parallel", "stub", "cross_connector",
})


# (20260624) VISIBLE_CHORD_CONNECT — a building connects to the taxi route by a
# VISIBLE CHORD (line-of-sight that stays within the pavement), NOT the closest
# centerline by straight-line distance.  The building-feasibility metric picked
# `min(cls, key=L.distance)`, which can pick a centerline reachable only by
# crossing grass / a service road (CYXY building16: the `~A` arm is 55 m away
# but its chord is 45% off-pavement; A2 is 70 m but its chord stays on the
# apron → A2 is the real route, giving ~707.8 not the loose ~A-loop ~712).  A
# spine counts as a taxi centerline, so building→apron-spine→taxiway is valid.
# When ON, the metric picks the nearest centerline whose chord to the building
# is contained in the airside pavement union.  Default ON (2026-06-24): part of
# the spine=0 working model (a building connects to the taxiway it can really
# reach without crossing grass).  Set O4_VISIBLE_CHORD_CONNECT=0 to restore the
# straight-line-nearest behaviour.
VISIBLE_CHORD_CONNECT = _os.environ.get(
    "O4_VISIBLE_CHORD_CONNECT", "1") == "1"

# (UNNAMED TAXI SIZE — formerly plan P3a, now removed.)  Unnamed taxi routes
# carry their real apt.dat ICAO size class directly: apt_dat_reader.unnamed_edge_
# component_names assigns each unnamed route a synthetic ``~U`` name (one per
# connected component), and taxi_size_letters keys it to the row-1202 size code,
# so every ref→cap consumer sees the true per-letter cap with no geometry
# recovery.  This subsumes the old A/B-only ~A/~B recovery hack.


# (20260627) LARGE-BUILDING FULL-FRONTAGE FEASIBILITY (user 2026-06-27): the
# route-feasibility band is sampled at a SINGLE CENTRAL CHORD — the building
# centroid → nearest taxi centerline — only for SMALL buildings.  A building at or
# above this footprint area must instead have its ENTIRE apron-facing FRONTAGE
# reachable within grade: the band is intersected over samples taken along every
# frontage edge (endpoints + midpoints), so a large terminal can never be seated at
# a level only its CENTRE can grade to the spine at 1 % — every frontage point must.
# m².  Gate ``O4_BUILDING_FULL_FRONTAGE`` off → single central chord for ALL
# buildings (byte-identical to the pre-2026-06-27 centroid-only model).
BUILDING_FULL_FRONTAGE_AREA_M2 = 2000.0
BUILDING_FULL_FRONTAGE = _os.environ.get(
    "O4_BUILDING_FULL_FRONTAGE", "1") == "1"

# (2026-07-17, KBNA SE lot) AIRSIDE-SERVED gate significance: a building
# pad counts as airside-served (and takes the reach-band floor clamp)
# only when the airside pavement COMPONENT it touches is at least this
# large.  KBNA building23 (26 m²) touched an ISOLATED 66 m² apron scrap
# and inherited the runway reach floor — 11.6 m above its own ground and
# 4.7 m above the groundside pavement 7 m away.  An isolated scrap that
# small serves no aircraft; the pad it touches is groundside furniture
# and must seat at local ground.  Scale mirrors the sub-2000 m² "small
# apron" convention (pipeline apron demotion note, user 2026-06-30).
BUILDING_AIRSIDE_CONTACT_MIN_COMPONENT_M2 = 2000.0

# DETACHED building pads: ``DETACHED_PAD_DEM_PIN`` / the
# ``O4_DETACHED_PAD_DEM_PIN`` gate are DELETED (item 3(b), 2026-08-05).
# A pad touching no qualifying airside pavement used to be HARD-PINNED
# flat at its footprint DEM median for the whole solve — DEM as a
# constraint, which RULINGS "DEM's role, and the constant-DEM invariant"
# forbids.  The plateau defect that pin masked is fixed at source (the
# airside reach band is withheld from a pad the airside law does not
# serve) and the pad now seats on its SOLVED groundside datum:
# ``route_profile.anchors.seat_detached_pads_by_law``.
# THE single building↔spine REACH corridor (user 2026-06-29): the max apron span
# over which a building reaches a taxi spine, gated by a VISIBLE on-pavement chord
# (no grass / one continuous apron) — the visibility gate, not the distance, is
# the real limit, but this caps it.  ONE value referenced by EVERY reach site so
# they cannot drift: the large-building frontage qualifier (``_frontage_band``),
# the small-pad route-band exemption (``grade_graph_validate``), and the
# building→spine lift (``_spine_floor_per_node``).  Exposed as the canonical reach
# rule via ``grade_law.BUILDING_REACH_CORRIDOR_M``.  200 m is the established
# default.  ⚠ OPEN (2026-06-29): a building beyond this across one continuous apron
# (CYXY building22, 208 m from ~U12) is not lifted to — making it a true spine
# anchor needs the REGION it serves lifted consistently (see the handover), not a
# point anchor or a wider corridor.
BUILDING_REACH_CORRIDOR_M = 200.0

# (20260710) PAD-IN-SOLVED-PAVEMENT HOST LEVEL (in-sim round 6 site 3): a
# building pad embedded in / abutting SOLVED pavement (apron, junction, taxi
# rect) must sit FLAT at the level the HOST PAVEMENT solved to at the contact —
# NOT at the raw-DEM frontage seat.  The frontage seat is a route-reachability
# envelope; when the apron around a pad solves ABOVE that envelope (its own DEM
# is higher / its body couples up), a DEM-low seat leaves the flat pad in a pit
# and the apron humps around it (CYXY apron #129 solved 708.65 while building8's
# pad pinned a run of shared ring nodes to the 705.0 DEM seat — a -333 % step
# over 1.1 m; "a big hump in this apron").  User ruling unchanged (buildings are
# FLAT at an authoritative value) — this only changes WHICH flat value an
# embedded pad carries: after the solve, re-level such a pad to the MEDIAN of
# the host pavement's solved values at the nearest non-shared boundary nodes.
# ARBITRATION: the pad adopts FROM the host, never the reverse; a pad NOT near
# solved pavement, or already within ``PAD_HOST_LEVEL_TRIGGER_M`` of its host,
# keeps today's behaviour (no-op).  Gate off → byte-identical.
PAD_HOST_PAVEMENT_LEVEL = _os.environ.get(
    "O4_PAD_HOST_PAVEMENT_LEVEL", "1") == "1"
# Radius (m) around a pad ring node within which host-pavement nodes are sampled
# — for the host-BODY median (nodes that differ from the pad by more than the
# trigger) and for the shared-LIP lift (nodes at the pad's pit value).  Must
# reach the apron's first non-shared body ring (CYXY building8: nearest body
# apron node ~2 m off the pad boundary).
PAD_HOST_LEVEL_CONTACT_M = 2.5
# Reach (m) of the shared-LIP lift: a wider skirt than the body-detection radius
# so the WHOLE local pit region the old seat dragged down (the pad's shared lip
# AND the apron transition nodes stepping toward it) rises to the body level
# before the adjacent-ground band re-drapes from it — otherwise a left-behind
# pit node steps against the lifted pad / tears the graded strip.  Only nodes AT
# the pit value (within the trigger of the pad's old level) inside this reach are
# lifted, so a legitimately-lower apron elsewhere is untouched.
PAD_HOST_LEVEL_LIFT_M = 6.0
# A host node within the contact radius counts as the BODY (triggers a re-level)
# when it differs from the current pad level by more than this (m); a node at or
# below it is a shared-boundary lip that carries the pad's own value.  Well above
# the sub-decimetre agreement of a normally-seated pad (CYXY residual deltas
# ≤ 0.14 m) and far below a genuine pit/hump (building8 = 3.67 m).
PAD_HOST_LEVEL_TRIGGER_M = 0.5
# (20260812, R19-1) RETIRED — DEAD CONSTANT, kept as a signpost.
# This was the reach of a LIP-RUN WALK: how far past a pad's own welded
# frontage a host-body probe could hunt for a vertex.  Both vertex-hunting
# mechanisms MISSED their measured target (HECA building114, whose host
# body sits 16.59 m out), and the owner re-ruled the law to sample the
# HOST'S SOLVED SURFACE at the pad ring instead
# (``anchors._surface_value_at``).  A surface has a value everywhere, so
# there is no reach to choose — and the neighbour-swap class this cap was
# minted for cannot occur, because every sample comes from ONE host
# polygon's own field with every pad's welded lips removed.  Nothing reads
# this constant; it stays so a reader who finds the old number in the
# history lands on the law that replaced it.
PAD_HOST_BODY_REACH_M = 10.0

# (20260812, R19-4) THE WALLS RULING's carve radius.  Owner 2026-08-07:
# "retaining walls emit ONLY at carve structures" — tunnel/bridge portals
# and abutments.  A portal's wall sits BESIDE its structure rather than
# on it, so the admission is a neighbourhood, and this is its one number
# (``adjacent_ground._carve_structure_zone``).  50 m is the distance the
# HECA attribution measured the mid-road wall to be CLEAR of any tunnel
# or bridge — the population the ruling retires (56 of that airport's 58
# walls) is not within an order of magnitude of it.
WALL_CARVE_SITE_RADIUS_M = 50.0


def taxi_grade_cap_for_letter(letter, *, enabled: bool = None,
                              ruleset=None) -> float:
    """Max longitudinal grade (rise/run) for a taxiway of ICAO code
    ``letter``.  Code A/B (narrow, <15 m) → ``TAXI_MAX_GRADE_NARROW``
    (3 %, ICAO Annex 14 §3.9.8); code C-F (and any unknown/None letter) →
    ``TAXI_MAX_GRADE`` (1.5 %).  When the ``TAXI_GRADE_BY_WIDTH`` gate is
    off, always returns ``TAXI_MAX_GRADE`` so the build is byte-identical
    to the uniform-cap baseline.  Pass ``enabled`` to override the gate
    (used by the validator to honour the same flag the build ran under).

    ``ruleset`` (phase B, §4 row 13) keys the value to the airport's own
    authority.  The A/B relaxation is ICAO's: FAA AC 150/5300-13B
    §4.14.1.1.1 gives 1.5 % for EVERY taxiway (its ≤30,000 lb 2 %
    relaxation is not taken — the builder does not know a taxiway's
    fleet), so an FAA-ruleset narrow taxiway TIGHTENS 3.0 % → 1.5 %.
    ``None`` keeps the legacy blended reading."""
    on = TAXI_GRADE_BY_WIDTH if enabled is None else enabled
    if ruleset is not None:
        cap = ruleset_taxi_max_grade(letter if on else None, ruleset)
        return TAXI_MAX_GRADE if cap is None else float(cap)
    if on and letter and str(letter).upper() in NARROW_TAXI_CODE_LETTERS:
        return TAXI_MAX_GRADE_NARROW
    return TAXI_MAX_GRADE


def taxi_transverse_cap_for_letter(letter, *, enabled: bool = None,
                                   ruleset=None) -> float:
    """Max TRANSVERSE (cross) grade for a taxiway of ICAO code ``letter`` — the
    ``cT`` in the anisotropic within-shape allowance ``cL·Δs∥ + cT·Δs⊥``.

    Code A/B (narrow) → ``TAXI_MAX_TRANSVERSE_NARROW`` (2 %, ICAO Annex 14
    §3.9.11); code C–F (and any unknown/None letter) → the LONGITUDINAL cap
    (:func:`taxi_grade_cap_for_letter`, 1.5 %), i.e. ISOTROPIC there.  Honours the
    same ``TAXI_GRADE_BY_WIDTH`` gate as the longitudinal cap, so when
    width-grading is off ``cT`` collapses to ``cL`` for EVERY letter and the
    allowance is the legacy isotropic ``cap·dist``.  ``enabled`` overrides the gate
    (the validator passes the flag the build ran under, for lockstep)."""
    on = TAXI_GRADE_BY_WIDTH if enabled is None else enabled
    if ruleset is not None:
        cap = ruleset_taxi_transverse_max(letter if on else None, ruleset)
        return (taxi_grade_cap_for_letter(letter, enabled=enabled,
                                          ruleset=ruleset)
                if cap is None else float(cap))
    if on and letter and str(letter).upper() in NARROW_TAXI_CODE_LETTERS:
        return TAXI_MAX_TRANSVERSE_NARROW
    return taxi_grade_cap_for_letter(letter, enabled=enabled)


def transverse_cap_for_longitudinal_cap(cap_l: float) -> float:
    """THE transverse cap ``cT`` of a corridor whose LONGITUDINAL cap is
    ``cap_l`` — one law source, three readers.

    The transverse cap is a pure function of the same role/letter the
    longitudinal cap came from (:func:`taxi_transverse_cap_for_letter` /
    ``SERVICE_ROAD_MAX_TRANSVERSE``): code A/B 3 %∥ → 2 %⊥, service road
    5 %∥ → 2 %⊥ (owner constant 2026-08-03), everything else ISOTROPIC
    (C–F 1.5 %, apron 1 %, every blended gradient).  Stated as a function
    OF THE CAP rather than of the letter because the two readers that
    need it downstream only ever hold the cap: the emitted sidecar
    carries a per-SEGMENT longitudinal cap (no letter), and the solver's
    within-shape ``Allowance`` carries ``cL``.

    Three readers, and every one of them delegates here rather than
    re-typing the three branches:
      * ``grade_graph._bake_edge``   — the solver's anisotropic budget;
      * ``lateral_spine_nodes``      — the emitter's cross-section pair
        budget (the pair it plants IS the pair the census prices, so it
        must be planted against the same cap);
      * ``tools/check_grade._transverse_cap_for_seg_cap`` — the
        TRANSVERSE validator.
    Two copies of a cap rule drifting is the census-wrapper defect class;
    the twin is ``tests/test_lateral_cross_section.py``."""
    if abs(float(cap_l) - TAXI_MAX_GRADE_NARROW) < 1e-9:
        return TAXI_MAX_TRANSVERSE_NARROW
    if abs(float(cap_l) - SERVICE_ROAD_MAX_GRADE) < 1e-9:
        return SERVICE_ROAD_MAX_TRANSVERSE
    return float(cap_l)


def taxiway_clearance_half_width_for_letter(letter: str) -> float:
    """Taxiway clearance half-width (m) from the centerline for a given
    ICAO code LETTER = wingtip reach (½ max wingspan) + margin."""
    return (0.5 * WINGSPAN_BY_CODE_LETTER[letter.upper()]
            + TAXIWAY_WINGTIP_MARGIN_M)


def taxiway_clearance_half_width_m(width_m: float) -> float:
    """Taxiway clearance half-width (m) from the centerline = wingtip
    reach (½ max wingspan for the width-inferred code letter) + margin.

    Fallback for taxiways with no apt.dat size class (OSM networks);
    prefer :func:`taxiway_clearance_half_width_for_letter`."""
    return taxiway_clearance_half_width_for_letter(
        taxiway_code_letter(width_m))


# ══════════════════════════════════════════════════════════════════════
# REGION RULESETS — the FAA / ICAO split, phase B
# (spec docs/specs/DRAFT-rulesets-phase-b-spec.md; owner ruling
#  docs/RULINGS.md "Region-specific rulesets", 2026-08-02: "FAA applies
#  within the USA, and ICAO everywhere else.  So we should support
#  region specific regulations and provide the code structure to allow
#  the possibility to choose and/or support multiple rulesets in the
#  future.")
# ══════════════════════════════════════════════════════════════════════
#
# THE STRUCTURE (spec §1, first-class — never `if icao.startswith("K")`
# at a law site).  ``RULESETS`` maps an open-ended ruleset KEY to a
# frozen ``Ruleset`` record holding that authority's own PRIMARY-VERIFIED
# values.  A law site never reads a bare module constant for a split
# family: it calls the family's accessor with the layout's resolved key,
# and emitter + validator call the SAME accessor (lockstep, grade-law
# completeness standard).
#
# WHY A DATACLASS AND NOT A DICT (spec §1 asks the implementer to say
# why): the field list IS the family inventory.  A new authority that
# forgets a column fails at construction, and a typo at a law site is an
# AttributeError on the first call instead of a silent ``.get()``
# default that quietly ships the wrong regulation.  ``dataclasses.
# fields`` also lets the lockstep twin enumerate every split family
# without a hand-maintained list.
#
# JURISDICTIONAL FIDELITY (owner 2026-08-02) supersedes "take the
# stricter": each ruleset carries its OWN authority's number even when
# that is the more permissive one.  Where a family exists in only one
# authority the other's field is ``None`` and the law is a no-op there
# (ICAO has no ROFA; FAA has no radio-altimeter operating area).
#
# BUILD-COMPLETE-THEN-DEBUG (docs/RULINGS.md 2026-08-05): this lands
# UNGATED.  The draft spec's ``O4_RULESET_SPLIT`` gate is NOT
# implemented — the split is standing law from the moment it lands, and
# the airports the spec predicted would move (ICAO code-4 runways under
# the 1.25 % cap) re-solve.  ``O4_RULESET`` survives ONLY as a testing
# override, because the resolver twin and the cross-authority twins need
# to force a key on a fixture airport; it is not a law gate (empty =
# resolve, which is the production path).

import dataclasses as _dc  # noqa: E402
from typing import Mapping as _Mapping, Optional as _Optional  # noqa: E402


@_dc.dataclass(frozen=True)
class CodeTable:
    """A regulatory value that an authority keys by aerodrome reference
    CODE NUMBER (ICAO's runway keying) or by code LETTER (the repo's
    proxy for FAA's AAC / ADG columns — see ``runway_code_letter`` and
    the Table 1-1 note on ``TAIL_HEIGHT_BY_CODE_LETTER``).

    Exactly one of ``by_code`` / ``by_letter`` is populated per
    authority, so the branch is on DATA PRESENCE, never on the
    authority's identity.  ``default`` is used when the caller has no
    key at all (an unclassified OSM taxiway, a runway with no length).

    A value may be ``None``: that means the authority states no number
    for that class (ICAO code 1-2 runways have no end-zone rule), and
    the law is a no-op there.
    """

    by_code: _Optional[_Mapping[int, _Optional[float]]] = None
    by_letter: _Optional[_Mapping[str, _Optional[float]]] = None
    default: _Optional[float] = None

    def value(self, code_number=None, code_letter=None):
        """The authority's value for this class, or ``None``."""
        if self.by_code is not None:
            if code_number is None:
                return self.default
            return self.by_code.get(int(code_number), self.default)
        if self.by_letter is not None:
            if not code_letter:
                return self.default
            return self.by_letter.get(str(code_letter).upper(), self.default)
        return self.default


def _letters(*, narrow: _Optional[float], wide: _Optional[float]) -> dict:
    """Code-letter table split at the ICAO A/B ("narrow", light-aircraft)
    vs C-F ("wide") boundary the FAA columns follow."""
    return {"A": narrow, "B": narrow,
            "C": wide, "D": wide, "E": wide, "F": wide}


@_dc.dataclass(frozen=True)
class Ruleset:
    """One authority's grade-law constants.  Every field carries its
    citation in the ``RULESETS`` construction below."""

    key: str
    name: str
    authority: str

    # ── §4 row 1 — runway longitudinal maximum ───────────────────────
    runway_max_grade: CodeTable = _dc.field(default_factory=CodeTable)
    # ── §4 row 2 — runway end-zone longitudinal cap ──────────────────
    runway_end_grade: CodeTable = _dc.field(default_factory=CodeTable)
    runway_end_zone_fraction: float = 0.25
    #: FAA bounds the end zone at the LESSER of the quarter and this
    #: length; ICAO states the quarter with no absolute bound.
    runway_end_zone_max_length_m: _Optional[float] = None
    #: Code numbers whose end-zone cap applies ONLY to precision
    #: approach Cat II/III runways (ICAO code 3).
    runway_end_grade_precision_only_codes: frozenset = frozenset()
    # ── §4 row 3 — runway maximum grade CHANGE ───────────────────────
    runway_max_grade_change: CodeTable = _dc.field(default_factory=CodeTable)
    # ── §4 row 4 — runway vertical curve ─────────────────────────────
    #: Metres of vertical curve per 1 % of grade change (the repo's
    #: ``RUNWAY_VERTICAL_CURVE_K_M`` unit).
    runway_vertical_curve_k_m: CodeTable = _dc.field(default_factory=CodeTable)
    #: Grade change below which no vertical curve is required
    #: (FAA §3.16.1.1 "0.40 percent", stated for AAC A/B only); a
    #: ``None`` value means the authority grants no such relief and the
    #: curve rule binds at every grade change.
    runway_vertical_curve_min_change: CodeTable = _dc.field(
        default_factory=CodeTable)
    # ── §4 row 5 — runway-strip longitudinal ─────────────────────────
    strip_max_longitudinal_slope: CodeTable = _dc.field(
        default_factory=CodeTable)
    #: §A3(b) — rate of longitudinal slope change on the graded strip,
    #: as grade change per metre.
    strip_arc_rate_per_m: _Optional[float] = None
    strip_arc_rate_provisional: bool = False
    # ── §4 row 6 — graded-strip half-width ───────────────────────────
    strip_half_width_m: CodeTable = _dc.field(default_factory=CodeTable)
    # ── §4 rows 7/8 — strip transverse zones (DEFERRED, see below) ───
    strip_lip_width_m: float = 3.0
    strip_lip_min_down_slope: float = 0.03
    strip_lip_max_down_slope: float = 0.05
    strip_band_min_down_slope: float = 0.015
    strip_band_max_down_slope: CodeTable = _dc.field(
        default_factory=CodeTable)
    # ── §4 row 9 — rising ground beyond the graded strip ─────────────
    ungraded_strip_max_up_slope: float = 0.05
    # ── §4 row 10 — RESA / end-skirt LONGITUDINAL ────────────────────
    #: Length of the FAA near zone beyond the end (``None`` = the
    #: authority states no near zone).
    end_skirt_near_zone_m: _Optional[float] = None
    end_skirt_near_max_down_grade: _Optional[float] = None
    end_skirt_max_down_grade: float = 0.05
    #: Grade change per metre along the end skirt.
    end_skirt_max_grade_change_per_m: _Optional[float] = None
    end_skirt_rate_provisional: bool = False
    # ── §4 row 11 / §A1 — RESA / end-corridor TRANSVERSE ─────────────
    #: ``(min_down, max_down)`` inside the near zone, keyed like the
    #: FAA Table 3-6 S-3 columns; ``None`` = no near-zone distinction.
    resa_transverse_near: _Optional[CodeTable] = None
    resa_transverse_near_max: _Optional[CodeTable] = None
    #: Symmetric ±cap beyond the near zone (and everywhere, for ICAO).
    resa_transverse_max: float = 0.05
    # ── §4 row 13 — taxiway longitudinal ─────────────────────────────
    taxi_max_grade: CodeTable = _dc.field(default_factory=CodeTable)
    # ── §4 row 14 — taxiway transverse ───────────────────────────────
    taxi_transverse_max: CodeTable = _dc.field(default_factory=CodeTable)
    #: RECORDED, NOT BOUND (owner question 5) — the crown minimum.
    taxi_transverse_min: _Optional[float] = None
    runway_transverse_min: _Optional[float] = None
    runway_transverse_max: CodeTable = _dc.field(default_factory=CodeTable)
    # ── §4 row 15/16 — stand + apron ─────────────────────────────────
    stand_max_grade: float = 0.01
    apron_min_drainage_grade: _Optional[float] = None
    apron_max_grade_change: _Optional[float] = None
    # ── §4 row 17 — taxiway strip ────────────────────────────────────
    taxiway_strip_band_min_down_slope: float = 0.015
    taxiway_strip_band_max_down_slope: float = 0.05
    taxiway_strip_graded_half_width_m: _Optional[_Mapping[str, float]] = None
    # ── §4 row 18 / §B1 — shoulders ──────────────────────────────────
    #: ``(min, max)`` transverse for a PAVED runway/taxiway shoulder.
    shoulder_transverse_min: _Optional[float] = None
    shoulder_transverse_max: _Optional[float] = None
    #: Mandated paved→unpaved edge drop-off (m) and its tolerance;
    #: ``None`` where the authority mandates flush instead.
    shoulder_edge_dropoff_m: _Optional[float] = None
    shoulder_edge_dropoff_tol_m: _Optional[float] = None
    # ── §4 row 19 / §A4 — radio altimeter operating area ─────────────
    raoa_length_m: _Optional[float] = None
    raoa_half_width_m: _Optional[float] = None
    raoa_max_grade_change_per_m: _Optional[float] = None
    # ── §A2 — ROFA back slope (FAA only) ─────────────────────────────
    #: ADG → run:rise ratio (8 means 8:1, i.e. a 12.5 % maximum rise).
    rofa_back_slope_ratio_by_adg: _Optional[_Mapping[str, float]] = None
    #: ADG → the run (m) over which the back slope is measured.
    rofa_back_slope_run_m_by_adg: _Optional[_Mapping[str, float]] = None
    #: ADG → ROFA half-width (m) from the runway centreline.
    rofa_half_width_m_by_adg: _Optional[_Mapping[str, float]] = None

    # ══════════════════════════════════════════════════════════════════
    # THE FABRIC-MODEL REG SET (W1, 2026-08-08).  Source of values:
    # ``docs/specs/fabric-model-reg-set.md``, every row PV-2026-08-08.
    # Owner law: RULINGS 2026-08-08 "Reg-set rulings" (1-4), "105 m
    # precision strip DROPPED" (which REVERSES the same-day adoption —
    # SPECIFICATION VALUES ONLY), "THE FABRIC MODEL".
    # Spec: ``docs/specs/fabric-phase-b-spec.md`` W1.
    #
    # EVERY field below carries a ``RegEntry`` in ``REG_SET_ENTRIES``
    # (value · citation · authority class · PV date), and a twin asserts
    # that it does — a constant with no provenance record fails the
    # suite rather than shipping as folklore.
    #
    # W1 IS CONSTANTS ONLY.  Where the authority-true value differs from
    # what an emitter reads TODAY the live blended field is left exactly
    # as it was and the authority's own number lands beside it under a
    # distinct name; ``RULESET_W2_FLIPS`` records which flag flipped
    # each consumer, and a twin pins the two halves so neither can
    # drift silently.
    # ══════════════════════════════════════════════════════════════════

    # ── F-1 (R3) — ICAO graded strip is keyed by (code, instrument) ───
    #: Annex 14 §3.4.8 / CS ADR-DSN.B.175(a) — the INSTRUMENT-runway
    #: graded half-width.  ``strip_half_width_m`` above is the
    #: NON-instrument table (§3.4.9), which is what the emitter reads
    #: today; the two differ only at code 1 (40 m vs 30 m).  ``None``
    #: where the authority does not split on instrument status (the FAA
    #: keys AAC × ADG × visibility instead).
    strip_half_width_m_instrument: _Optional[CodeTable] = None

    # ── Q5 — the 105 m precision-approach strip: NOT ENCODED ──────────
    # RULINGS 2026-08-08 "105 m precision strip DROPPED (owner;
    # supersedes the same-day adoption)".  Owner, on learning the 105 m
    # has no FAA anchor: "If there's no FAA citation for the 105 m
    # precision strip, we can drop it as well."  The guidance adoption
    # is REVERSED on both rulesets — SPECIFICATION VALUES ONLY, and the
    # Annex 14 §3.4.8 Note stays recorded in
    # docs/specs/fabric-model-reg-set.md §2.1 as UNADOPTED guidance.
    # Consistent with rulings 1 and 4 of the same day: shape nothing the
    # specification does not mandate.  Deliberately NO field here — a
    # None field would still be a place for the value to creep back.

    # ── Reg-set ruling 1 — the graded-strip mandatory DOWN ────────────
    #: Whether THIS authority mandates a downward fall across the graded
    #: strip.  FAA: yes, Table 3-6 S-3's 1.5 % floor (a Standard).
    #: ICAO: NO — §3.4.15 / B.185(a) state a ceiling and the 3 m lip
    #: only.  Ruling 1 DROPS the blended fall on the ICAO ruleset,
    #: flagged PROVISIONAL (revisit at the owner's sim look).
    strip_band_mandatory_down: bool = True
    #: The authority's OWN zone-2 minimum fall (``None`` = none stated).
    #: NOT the same field as ``strip_band_min_down_slope``, which is the
    #: LIVE BLEND the emitter still reads — see the W2 flip list.
    strip_band_min_down_slope_authority: _Optional[float] = None
    #: True where dropping/keeping the fall is the owner's PROVISIONAL
    #: call rather than the authority's own text.
    strip_band_drop_provisional: bool = False

    # ── F-10 — the TWO lip families ───────────────────────────────────
    # ``strip_lip_*`` above is the RUNWAY-edge lip (Annex 14 §3.4.15
    # final clause; AC Fig. 3-33 Detail A note 2 — 3 m at 3-5 %).  The
    # taxiway/taxilane/apron edge is a DIFFERENT band and the repo
    # collapsed the two; these fields carry the second family.
    #: FAA ¶4.14.2 Standards item 4: "5 ±0.5 percent … for a minimum
    #: distance of 10 feet (3 m)" ⇒ 4.5-5.5 % over 3 m at ANY
    #: paved→unpaved edge (taxiway, taxilane, apron).  ICAO: ``None`` —
    #: §3.11.5 / D.330(b) state flush + caps and NO lip (absence
    #: verified by full read), so the ICAO taxiway lip is unsourced.
    taxiway_lip_width_m: _Optional[float] = None
    taxiway_lip_min_down_slope: _Optional[float] = None
    taxiway_lip_max_down_slope: _Optional[float] = None
    #: ¶4.14.2 item 5 states the TSA band "except as noted in
    #: subparagraph 4 above" — the lip is CARVED OUT of the strip band,
    #: a near-zone/far-zone pair exactly like the RSA's, never an
    #: alternative to it.
    taxiway_lip_carved_out_of_band: bool = False

    # ── R24 — TOFA back slope (FAA only, new this round) ──────────────
    #: AC ¶4.14.2 Standards item 6b + Figure 4-29: a taxiway/taxilane
    #: object free area back slope, where one is necessary, is ≤4:1
    #: (run:rise ⇒ a 25 % maximum rise).  A CEILING (cut), never a
    #: mandate to shape — same discipline as R10/R22.  ``None`` under
    #: ICAO, which has no object-free-area family (its analogue is
    #: §3.11.6, already ``ungraded_strip_max_up_slope``).
    #: The TOFA's own transverse (side) gradient is QUALITATIVE in the
    #: AC — ¶4.14.2 item 6a asks only for "positive drainage away from
    #: the TSA", no number, unlike the runway ROFA's S-4.  That absence
    #: is recorded in ``REG_SET_ENTRIES`` rather than as a field: the
    #: registry carries BOUNDS, and a named side-slope field here would
    #: read as one (the S-4 exemption twin polices exactly that).
    tofa_back_slope_ratio: _Optional[float] = None

    # ── R20 / reg-set ruling 2 — the taxiway cross-fall MINIMUM ───────
    #: True where ``taxi_transverse_min`` is a repo HOUSE CONSTANT
    #: rather than that authority's own number.  ICAO states NO taxiway
    #: minimum anywhere (§3.9.11 / D.280(b) are ceiling-only); ruling 2
    #: adopts the FAA 1.0 % as a named PROVISIONAL house constant
    #: satisfying "sufficient to prevent the accumulation of water",
    #: with the ICAO text quoted at the construction site.
    taxi_transverse_min_provisional: bool = False
    #: The AC states the 1.0-1.5 % cross-fall under *Standards*
    #: (¶4.14.2 item 1a) but the CENTRE CROWN only under *Recommended
    #: Practices* (item 2, "the ideal configuration").  So the MINIMUM
    #: is primary-sourced and bindable; the crown FORM is not.  W2 binds
    #: the minimum and must not infer the crown from it.
    taxi_crown_form_binding: bool = False

    # ── F-11 / §4.4 — taxiway shoulders ───────────────────────────────
    #: AC Table 4-2 (¶4.13.1 item 1): shoulder width per side keyed by
    #: TAXIWAY DESIGN GROUP, not ADG — the repo carried it as ADG.
    taxiway_shoulder_width_m_by_tdg: _Optional[_Mapping[str, float]] = None
    #: Table 4-2 fn 3: 40 ft (12.2 m) where the most demanding aircraft
    #: has four engines and is TDG 6.
    taxiway_shoulder_width_m_tdg6_four_engine: _Optional[float] = None
    #: ¶4.13.1 Standards item 2 — PROVISION stays ADG-keyed: paved
    #: shoulders for ADG-IV and larger.  Width TDG, provision ADG.
    taxiway_shoulder_paved_from_adg: _Optional[str] = None
    #: ICAO §3.10.1 / CS ADR-DSN.D.305(a) give no per-side width at all,
    #: only an OVERALL taxiway-plus-shoulders width by code letter.
    taxiway_plus_shoulders_total_width_m: _Optional[
        _Mapping[str, float]] = None

    # ── R11 / F-12 — the RESA / RSA end corridor, per source ──────────
    #: Where this authority MEASURES the end corridor from.
    #: ``"strip_end"`` (ICAO §3.5.3 — the strip itself already runs
    #: beyond the runway end) or ``"runway_or_stopway_end"``
    #: (AC App. G fn 9).  Reg-set ruling 3: fix both per source.
    resa_length_datum: _Optional[str] = None
    #: ICAO §3.4.2 — how far the STRIP extends beyond the runway/stopway
    #: end, by code number.  This is the ICAO datum's offset.
    strip_beyond_end_m: _Optional[CodeTable] = None
    #: Annex 14 §3.4.2 gives 30 m at code 1 NON-instrument and 60 m at
    #: code 1 instrument; the table above is the non-instrument reading.
    strip_beyond_end_m_instrument: _Optional[CodeTable] = None
    #: ICAO §3.5.3 (**shall**) — the hard floor, measured from the datum.
    resa_length_min_m: _Optional[float] = None
    #: ICAO §3.5.4 (recommendation), NON-instrument runways; the FAA
    #: publishes no separate "recommended" length (App. G values are
    #: Standards, and the only relief is fn 10's EMAS shortening).
    resa_length_recommended_m: _Optional[CodeTable] = None
    #: §3.5.4 again, INSTRUMENT runways — 120 m at code 1/2 where the
    #: non-instrument recommendation is 30 m.
    resa_length_recommended_m_instrument: _Optional[CodeTable] = None
    #: FAA only: the per-end Appendix G length is a FUNCTION of
    #: (RDC, visibility minimum, vertical guidance, stopway), not a
    #: constant — see :func:`faa_rsa_end_length_m`.  This flag records
    #: that the function, not a flattened number, is the law here.
    resa_length_is_per_end_function: bool = False


# ── ADG ↔ ICAO code-letter proxy ──────────────────────────────────────
# FAA keys its object-free-area and design-group tables by Airplane
# Design Group (I..VI); the repo carries the ICAO code LETTER.  The
# mapping A↔I, B↔II, C↔III, D↔IV, E↔V, F↔VI is already the repo's own
# (``TAIL_HEIGHT_BY_CODE_LETTER`` Table 1-1 note); the ADG tables below
# are therefore stored RE-KEYED BY LETTER so no law site has to convert.
ADG_BY_CODE_LETTER = {
    "A": "I", "B": "II", "C": "III", "D": "IV", "E": "V", "F": "VI",
}


def _by_adg(**kw) -> dict:
    """ADG-keyed table written in letter space (A..F) so it can be read
    with the repo's own code letter — see ``ADG_BY_CODE_LETTER``."""
    return {letter: kw[ADG_BY_CODE_LETTER[letter]]
            for letter in ADG_BY_CODE_LETTER}


# ══════════════════════════════════════════════════════════════════════
# FAA APPENDIX G — THE THREE-AXIS MATRIX (reg-set F-9 / F-12, W1)
# ══════════════════════════════════════════════════════════════════════
#
# Source: docs/specs/fabric-model-reg-set.md §2.1, §3, §3.1 — read off
# AC 150/5300-13B Chg 1 (w/ errata) Appendix G Tables G-1 … G-12 and
# footnotes 9-14, PRIMARY-VERIFIED 2026-08-08.
#
# THE DEFECT THIS CLOSES (F-9): Appendix G is keyed on THREE axes —
# AAC group (A/B vs C/D/E) × ADG (I…VI) × VISIBILITY MINIMUM — and the
# repo carried a single column.  Two consequences, both primary-verified:
# A/B-III (300 ft) and A/B-IV (500 ft) were missing outright, and the
# visibility axis was absent (at minimums lower than 3/4 mile the RSA
# widens to 300 ft for A/B-I and A/B-II and 400 ft for A/B-III; C/D/E is
# flat at 500 ft across all four columns, which is why the omission has
# never shown at KCLT).  "Not a wrong number — a missing axis."
#
# UNITS: feet are the AC's own; metres are ``ft × 0.3048`` rounded to
# 0.1 m, which is exactly how the repo's carried half-widths were
# written (a twin pins each carried value against this derivation, so
# the matrix REPLACES the literals rather than duplicating them).

#: The AC's four approach-visibility columns, in table order.  The
#: builder has no per-end visibility minimum today, so every legacy
#: accessor takes ``FAA_VISIBILITY_DEFAULT`` — recorded, never silently
#: widened.
FAA_VISIBILITY_MINIMA = ("visual", "ge_1mi", "ge_3_4mi", "lt_3_4mi")
FAA_VISIBILITY_DEFAULT = "ge_3_4mi"

#: The AAC groups the Appendix G tables split on.
FAA_AAC_GROUPS = ("A/B", "C/D/E")
FAA_ADG_NUMERALS = ("I", "II", "III", "IV", "V", "VI")

_FT_M = 0.3048


def _ft_cols(visual, ge_1mi, ge_3_4mi, lt_3_4mi) -> dict:
    """One Appendix G row, written in the AC's own four columns."""
    return {"visual": visual, "ge_1mi": ge_1mi,
            "ge_3_4mi": ge_3_4mi, "lt_3_4mi": lt_3_4mi}


def _ft_flat(ft) -> dict:
    """An Appendix G row whose value does not vary with visibility."""
    return _ft_cols(ft, ft, ft, ft)


#: RDC → visibility column → RSA WIDTH in feet (App. G dim **C**).
#: G-1/G-2 A/B-I 120 ft; G-3/G-4 A/B-II 150 ft; G-5 A/B-III 300 ft;
#: G-6 A/B-IV 500 ft; G-7…G-12 C/D/E-I…VI 500 ft.  fn 13: 400 ft is
#: permissible for C/D/E-I and C/D/E-II where 500 ft "is not practical"
#: — a RELIEF, not a value, so it is recorded in ``REG_SET_ENTRIES``
#: and never taken automatically.
FAA_RSA_WIDTH_FT_BY_RDC = {
    ("A/B", "I"): _ft_cols(120, 120, 120, 300),
    ("A/B", "II"): _ft_cols(150, 150, 150, 300),
    ("A/B", "III"): _ft_cols(300, 300, 300, 400),
    ("A/B", "IV"): _ft_flat(500),
    ("C/D/E", "I"): _ft_flat(500),
    ("C/D/E", "II"): _ft_flat(500),
    ("C/D/E", "III"): _ft_flat(500),
    ("C/D/E", "IV"): _ft_flat(500),
    ("C/D/E", "V"): _ft_flat(500),
    ("C/D/E", "VI"): _ft_flat(500),
}

#: RDC → visibility column → ROFA WIDTH in feet (App. G dim **Q**).
#: 400 ft A/B-I, 500 ft A/B-II, 800 ft everywhere else, and 800 ft in
#: every table's <3/4-mile column.  The A/B-I SMALL-AIRCRAFT table
#: (G-1) is 250 ft — see ``FAA_ROFA_WIDTH_FT_SMALL_AIRCRAFT``.
FAA_ROFA_WIDTH_FT_BY_RDC = {
    ("A/B", "I"): _ft_cols(400, 400, 400, 800),
    ("A/B", "II"): _ft_cols(500, 500, 500, 800),
    ("A/B", "III"): _ft_flat(800),
    ("A/B", "IV"): _ft_flat(800),
    ("C/D/E", "I"): _ft_flat(800),
    ("C/D/E", "II"): _ft_flat(800),
    ("C/D/E", "III"): _ft_flat(800),
    ("C/D/E", "IV"): _ft_flat(800),
    ("C/D/E", "V"): _ft_flat(800),
    ("C/D/E", "VI"): _ft_flat(800),
}

#: Table G-1 (A/B-I **small aircraft** exclusively) — the one row whose
#: ROFA width differs from its non-small twin.  The reg-set table
#: records no separate RSA width for the small-aircraft tables, so none
#: is invented here (a value the verified table does not state would be
#: MINTED).
FAA_ROFA_WIDTH_FT_SMALL_AIRCRAFT = {("A/B", "I"): _ft_cols(250, 250, 250, 800)}

#: RDC → visibility column → **R**, RSA/ROFA length BEYOND the
#: departure end, in feet.  Per runway END (App. G; the ROFA's dim R is
#: identical to the RSA's in all twelve tables).
FAA_RSA_LENGTH_BEYOND_END_FT_BY_RDC = {
    ("A/B", "I", True): _ft_cols(240, 240, 240, 600),      # G-1, small
    ("A/B", "I", False): _ft_cols(240, 240, 240, 600),     # G-2
    ("A/B", "II", True): _ft_cols(300, 300, 300, 600),     # G-3, small
    ("A/B", "II", False): _ft_cols(300, 300, 300, 600),    # G-4
    ("A/B", "III", False): _ft_cols(600, 600, 600, 800),   # G-5
    ("A/B", "IV", False): _ft_flat(1000),                  # G-6
    ("C/D/E", "I", False): _ft_flat(1000),                 # G-7
    ("C/D/E", "II", False): _ft_flat(1000),                # G-8
    ("C/D/E", "III", False): _ft_flat(1000),               # G-9
    ("C/D/E", "IV", False): _ft_flat(1000),                # G-10
    ("C/D/E", "V", False): _ft_flat(1000),                 # G-11
    ("C/D/E", "VI", False): _ft_flat(1000),                # G-12
}

#: RDC → visibility column → **P**, RSA length PRIOR TO THRESHOLD, in
#: feet.  App. G **fn 11**: this value applies only where that runway
#: end has electronic or visual vertical guidance (ILS, GLS, LPV, VNAV,
#: RNP lines of minima; PAPI or VASI); with no such guidance the end
#: takes the "beyond departure end" value instead.
FAA_RSA_LENGTH_PRIOR_TO_THRESHOLD_FT_BY_RDC = {
    ("A/B", "I", True): _ft_cols(240, 240, 240, 600),
    ("A/B", "I", False): _ft_cols(240, 240, 240, 600),
    ("A/B", "II", True): _ft_cols(300, 300, 300, 600),
    ("A/B", "II", False): _ft_cols(300, 300, 300, 600),
    ("A/B", "III", False): _ft_flat(600),
    ("A/B", "IV", False): _ft_flat(600),
    ("C/D/E", "I", False): _ft_flat(600),
    ("C/D/E", "II", False): _ft_flat(600),
    ("C/D/E", "III", False): _ft_flat(600),
    ("C/D/E", "IV", False): _ft_flat(600),
    ("C/D/E", "V", False): _ft_flat(600),
    ("C/D/E", "VI", False): _ft_flat(600),
}

#: The repo's code LETTER is a SIZE proxy; this is the RDC row it reads
#: as.  A narrow runway (letter A/B) is a light-aircraft runway and
#: takes the A/B column at its own ADG; letters C-F take the C/D/E
#: column, which is identical (500 ft RSA / 800 ft ROFA) for every ADG.
#: The A/B-III and A/B-IV rows F-9 restores are NOT reachable through
#: this proxy — they need a real RDC, which is why the matrix above is
#: keyed on the RDC and the proxy is only a view of it.
FAA_RDC_BY_CODE_LETTER = {
    "A": ("A/B", "I"), "B": ("A/B", "II"),
    "C": ("C/D/E", "III"), "D": ("C/D/E", "IV"),
    "E": ("C/D/E", "V"), "F": ("C/D/E", "VI"),
}


def _faa_visibility_key(visibility_minimum=None) -> str:
    """Normalise a visibility-minimum key, defaulting to the column the
    builder takes when it has no per-end minimum."""
    key = str(visibility_minimum or FAA_VISIBILITY_DEFAULT)
    if key not in FAA_VISIBILITY_MINIMA:
        raise ValueError(
            f"unknown FAA visibility minimum {visibility_minimum!r} "
            f"(known: {list(FAA_VISIBILITY_MINIMA)})")
    return key


def _faa_rdc_key(aac_group, adg) -> tuple:
    key = (str(aac_group), str(adg).upper())
    if key not in FAA_RSA_WIDTH_FT_BY_RDC:
        raise ValueError(
            f"unknown FAA runway design code {key!r} (known: "
            f"{sorted(FAA_RSA_WIDTH_FT_BY_RDC)})")
    return key


def faa_rsa_width_ft(aac_group, adg, visibility_minimum=None) -> float:
    """App. G dim **C** — full RSA width in FEET for one RDC and one
    visibility column (F-9's three axes)."""
    return FAA_RSA_WIDTH_FT_BY_RDC[_faa_rdc_key(aac_group, adg)][
        _faa_visibility_key(visibility_minimum)]


def faa_rsa_half_width_m(aac_group, adg, visibility_minimum=None) -> float:
    """App. G dim **C**, halved and in metres — the graded-strip / RSA
    half-width from the runway centreline."""
    return round(faa_rsa_width_ft(aac_group, adg, visibility_minimum)
                 * _FT_M / 2.0, 1)


def faa_rofa_width_ft(aac_group, adg, visibility_minimum=None,
                      small_aircraft: bool = False) -> float:
    """App. G dim **Q** — full ROFA width in FEET.  ``small_aircraft``
    selects the G-1 (A/B-I, small aircraft exclusively) row."""
    key = _faa_rdc_key(aac_group, adg)
    col = _faa_visibility_key(visibility_minimum)
    if small_aircraft and key in FAA_ROFA_WIDTH_FT_SMALL_AIRCRAFT:
        return FAA_ROFA_WIDTH_FT_SMALL_AIRCRAFT[key][col]
    return FAA_ROFA_WIDTH_FT_BY_RDC[key][col]


def faa_rofa_half_width_m(aac_group, adg, visibility_minimum=None,
                          small_aircraft: bool = False) -> float:
    """App. G dim **Q**, halved and in metres."""
    return round(faa_rofa_width_ft(aac_group, adg, visibility_minimum,
                                   small_aircraft) * _FT_M / 2.0, 1)


def faa_rsa_end_length_m(aac_group, adg, *, visibility_minimum=None,
                         vertical_guidance: bool = False,
                         small_aircraft: bool = False) -> float:
    """The RSA length beyond ONE runway end, in metres — App. G dims
    **R** / **P** (reg-set §3.1, F-12).

    This is a FUNCTION, never a flattened constant: the FAA end-corridor
    length depends on (a) the runway design code, (b) that end's
    approach VISIBILITY MINIMUM and (c) whether that end has vertical
    guidance.  CIFP already gives the builder approach type per end
    (RULINGS "Instrument truth is law", 2026-08-06), so key (c) and most
    of (b) are available without new data.

    App. G **fn 11** is the dispatch: dim P ("length prior to
    threshold") applies only where that end is equipped with electronic
    or visual vertical guidance — ILS, GLS, LPV, VNAV and RNP lines of
    minima give electronic vertical guidance, a PAPI or VASI visual —
    and "if there is no such guidance for that runway, use the value for
    'length beyond departure end'".

    NOT the datum.  Where the corridor STARTS is fn 9, encoded by
    :func:`faa_rsa_end_datum_offset_m`; ``vertical_guidance`` and
    ``stopway`` are independent keys and must not be conflated.
    """
    key = (*_faa_rdc_key(aac_group, adg), bool(small_aircraft))
    table = (FAA_RSA_LENGTH_PRIOR_TO_THRESHOLD_FT_BY_RDC if vertical_guidance
             else FAA_RSA_LENGTH_BEYOND_END_FT_BY_RDC)
    if key not in table:
        key = (key[0], key[1], False)     # no separate small-aircraft row
    return round(table[key][_faa_visibility_key(visibility_minimum)]
                 * _FT_M, 1)


def faa_rsa_end_datum_offset_m(stopway_length_m=0.0) -> float:
    """App. G **fn 9**, verbatim: "The RSA length beyond the runway end
    begins at the runway end when a stopway is not present.  When a
    stopway is present, the length begins at the stopway end."

    So the corridor's datum sits ``stopway_length_m`` past the runway
    end — the FAA's per-source datum under reg-set ruling 3, against
    ICAO's strip-end datum (§3.5.3)."""
    return max(0.0, float(stopway_length_m or 0.0))


def faa_rsa_governed_length_beyond_runway_end_m(
        aac_group, adg, *, visibility_minimum=None,
        vertical_guidance: bool = False, small_aircraft: bool = False,
        stopway_length_m=0.0) -> float:
    """The whole FAA end corridor measured from the RUNWAY end: the fn-9
    datum offset plus the fn-11 per-end length.  One reader, so an
    emitter and a validator cannot disagree about where the corridor
    starts or how long it is."""
    return (faa_rsa_end_datum_offset_m(stopway_length_m)
            + faa_rsa_end_length_m(
                aac_group, adg, visibility_minimum=visibility_minimum,
                vertical_guidance=vertical_guidance,
                small_aircraft=small_aircraft))


# ── FAA taxiway shoulder widths — Table 4-2, keyed by TDG (F-11) ──────
# The AC keys taxiway SHOULDER WIDTH by TAXIWAY DESIGN GROUP; the repo
# carried it as ADG.  PROVISION stays ADG-keyed (¶4.13.1 Standards item
# 2: paved shoulders for ADG-IV and larger), so the two axes are kept
# apart here rather than blended into one table.
FAA_TAXIWAY_SHOULDER_WIDTH_FT_BY_TDG = {
    "1A": 10, "1B": 10,
    "2A": 15, "2B": 15,
    "3": 20, "4": 20,
    "5": 30, "6": 30,
}
#: Table 4-2 fn 3 — four-engine aircraft at TDG 6.
FAA_TAXIWAY_SHOULDER_WIDTH_FT_TDG6_FOUR_ENGINE = 40
FAA_TAXIWAY_SHOULDER_WIDTH_M_BY_TDG = {
    tdg: round(ft * _FT_M, 1)
    for tdg, ft in FAA_TAXIWAY_SHOULDER_WIDTH_FT_BY_TDG.items()
}
FAA_TAXIWAY_SHOULDER_WIDTH_M_TDG6_FOUR_ENGINE = round(
    FAA_TAXIWAY_SHOULDER_WIDTH_FT_TDG6_FOUR_ENGINE * _FT_M, 1)

#: ICAO §3.10.1 / CS ADR-DSN.D.305(a) — OVERALL taxiway-plus-shoulders
#: width by code letter.  ICAO states no per-side shoulder width, so the
#: two authorities are not interconvertible here either.
ICAO_TAXIWAY_PLUS_SHOULDERS_TOTAL_WIDTH_M = {
    "C": 25.0, "D": 34.0, "E": 38.0, "F": 44.0,
}


# ══════════════════════════════════════════════════════════════════════
# ICAO / EASA — Annex 14 Volume I (incl. Amdt 18) + CS-ADR-DSN Issue 7
# ══════════════════════════════════════════════════════════════════════
ICAO_RULESET = Ruleset(
    key="icao",
    name="ICAO Annex 14 Vol I / EASA CS-ADR-DSN",
    authority="ICAO",

    # §3.1.14: "1.25 per cent where the code number is 4 … 1.5 per cent
    # where the code number is 3 … 2 per cent where the code number is
    # 1 or 2".  PRIMARY-VERIFIED (annex14_bazl.txt §3.1.14).  This is
    # the largest surface change phase B lands: code-4 runways at
    # HECA / SPJC / CYXY tighten 1.5 % → 1.25 % and their profiles
    # re-solve within the runway-flex law (CIFP thresholds immovable).
    runway_max_grade=CodeTable(
        by_code={1: 0.020, 2: 0.020, 3: 0.015, 4: 0.0125},
        default=0.0125),

    # §3.1.14 same paragraph: the 0.8 % first/last-quarter limit applies
    # at code 4 unconditionally, and at code 3 ONLY "for the first and
    # last quarter of the length of a precision approach runway category
    # II or III".  Code 1-2: no end-zone rule at all (None).
    runway_end_grade=CodeTable(
        by_code={1: None, 2: None, 3: 0.008, 4: 0.008}),
    runway_end_zone_max_length_m=None,          # ICAO states no cap
    runway_end_grade_precision_only_codes=frozenset({3}),

    # §3.1.15: slope change ≤1.5 % (code 3-4) / 2 % (code 1-2).
    runway_max_grade_change=CodeTable(
        by_code={1: 0.020, 2: 0.020, 3: 0.015, 4: 0.015},
        default=0.015),

    # §3.1.16: rate of change ≤0.1 %/30 m (code 4), 0.2 %/30 m (code 3),
    # 0.4 %/30 m (code 1-2) → metres of curve per 1 % = 30/0.1 = 300,
    # 30/0.2 = 150, 30/0.4 = 75.  ICAO gives no "below X % no curve"
    # relief, so ``runway_vertical_curve_min_change`` stays None.
    runway_vertical_curve_k_m=CodeTable(
        by_code={1: 75.0, 2: 75.0, 3: 150.0, 4: 300.0}, default=300.0),
    runway_vertical_curve_min_change=CodeTable(default=None),

    # §3.4.13: strip longitudinal ≤1.5 % (code 4), 1.75 % (code 3),
    # 2 % (code 1-2).  This is the repo's live blended table.
    strip_max_longitudinal_slope=CodeTable(
        by_code=dict(RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_BY_CODE),
        default=0.015),
    # §3.4.14 is QUALITATIVE ("Slope changes … should be as gradual as
    # practicable and abrupt changes or sudden reversals of slopes
    # avoided") — no number.  DECIDE-AND-NOTE (owner question 2, spec
    # §10.2): operationalized at the FAA beyond-ends rate ±2 % per
    # 30.5 m (AC §3.16.5 item 5).  Flagged provisional so the report and
    # the twin can both see it is a repo choice, not a citation.
    strip_arc_rate_per_m=0.02 / 30.5,
    strip_arc_rate_provisional=True,

    # §3.4.8-3.4.9 frame (and the repo's live table): graded strip half-width
    # 30 / 40 / 75 / 75 m by code number.
    strip_half_width_m=CodeTable(
        by_code=dict(RUNWAY_STRIP_HALF_WIDTH_BY_CODE), default=75.0),

    # ROWS 7/8 — DEFERRED BY OWNER QUESTION (spec §5 last bullet, §10.1).
    # ICAO §3.4.15 caps the graded-strip transverse at 2.5 % (code 3-4) /
    # 3 % (code 1-2) and MANDATES nothing downward except the first 3 m
    # ("should be negative … and may be as great as 5 per cent").  The
    # owner's 2026-07-08 ruling 1 (enforce the FAA mandatory-DOWN band
    # globally) was premised on ONE blended ruleset; under jurisdictional
    # fidelity it may or may not survive.  UNTIL THE OWNER ANSWERS, BOTH
    # RULESETS KEEP THE BLENDED MANDATORY-DOWN VALUES — the deferral is
    # visible law here, not silent drift.
    strip_lip_width_m=ADJACENT_GROUND_LIP_WIDTH_M,
    strip_lip_min_down_slope=ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE,
    strip_lip_max_down_slope=ADJACENT_GROUND_LIP_MAX_DOWN_SLOPE,
    strip_band_min_down_slope=RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE,
    strip_band_max_down_slope=CodeTable(
        by_code=dict(RUNWAY_STRIP_BAND_MAX_DOWN_SLOPE_BY_CODE),
        default=0.03),

    # §3.4.16 / §3.11.6: beyond the graded portion, rising ground ≤5 %.
    ungraded_strip_max_up_slope=ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE,

    # §3.5.10: RESA longitudinal "should not exceed a downward slope of
    # 5 per cent"; slope changes "as gradual as practicable" — NO near
    # zone, NO numeric rate.  The rate is the same provisional
    # operationalization as the strip arc (owner question 2).
    end_skirt_near_zone_m=None,
    end_skirt_near_max_down_grade=None,
    end_skirt_max_down_grade=0.05,
    end_skirt_max_grade_change_per_m=0.02 / 30.5,
    end_skirt_rate_provisional=True,

    # §3.5.11: RESA transverse "should not exceed an upward or downward
    # slope of 5 per cent" — one symmetric cap, no near-zone column.
    resa_transverse_near=None,
    resa_transverse_near_max=None,
    resa_transverse_max=0.05,

    # §3.9.8: taxiway longitudinal 1.5 % (C-F) / 3 % (A-B).
    taxi_max_grade=CodeTable(
        by_letter=_letters(narrow=TAXI_MAX_GRADE_NARROW,
                           wide=TAXI_MAX_GRADE),
        default=TAXI_MAX_GRADE),
    # §3.9.11: taxiway transverse 1.5 % (C-F) / 2 % (A-B).
    taxi_transverse_max=CodeTable(
        by_letter=_letters(narrow=TAXI_MAX_TRANSVERSE_NARROW,
                           wide=TAXI_MAX_GRADE),
        default=TAXI_MAX_GRADE),
    # RECORDED, NOT BOUND (owner question 5).  §3.9.11 states no taxiway
    # minimum; §3.1.19 states the RUNWAY transverse "should not exceed
    # 1.5 per cent or 2 per cent, as applicable, nor be less than 1 per
    # cent except at runway or taxiway intersections".
    # 2026-08-08 (reg-set ruling 2, W1): the taxiway field is no longer
    # None — it carries 1.0 % as a NAMED PROVISIONAL HOUSE CONSTANT.
    # The ICAO clause it stands in for is quoted at the reg-set block
    # further down, together with the provisional flag; the value stays
    # RECORDED, NOT BOUND (``CROWN_MINIMUM_BOUND_TAXIWAYS`` is False),
    # so nothing in the emitter or the census reads it yet.
    taxi_transverse_min=0.010,
    runway_transverse_min=0.010,
    runway_transverse_max=CodeTable(
        by_letter=_letters(narrow=0.020, wide=0.015), default=0.015),

    # §3.13.5: "On an aircraft stand the maximum slope should not exceed
    # 1 per cent."
    stand_max_grade=0.01,
    # §3.13.4 is QUALITATIVE ("sufficient to prevent accumulation of
    # water … kept as level as drainage requirements permit") — there is
    # NO numeric ICAO apron minimum.  A number here would be MINTED, not
    # cited, so the field stays None and the §B3 apron law is a no-op at
    # ICAO airports (jurisdictional fidelity).
    apron_min_drainage_grade=None,
    apron_max_grade_change=None,

    # §3.11.5: taxiway strip graded portion, upward transverse ≤2.5 %
    # (C-F) / 3 % (A-B), downward ≤5 %.  Live blended values (the
    # mandatory-down minimum rides owner question 1 with rows 7/8).
    taxiway_strip_band_min_down_slope=TAXIWAY_STRIP_BAND_MIN_DOWN_SLOPE,
    taxiway_strip_band_max_down_slope=TAXIWAY_STRIP_BAND_MAX_DOWN_SLOPE,
    taxiway_strip_graded_half_width_m=dict(
        TAXIWAY_STRIP_GRADED_HALF_WIDTH_BY_LETTER),

    # §3.2.3: "The surface of the shoulder that abuts the runway should
    # be flush with the surface of the runway and its transverse slope
    # should not exceed 2.5 per cent."  FLUSH ⇒ no mandated drop-off and
    # no minimum; §3.10 gives taxiway shoulders width/strength only, so
    # a taxiway shoulder rides the same flush + strip-band law.
    shoulder_transverse_min=None,
    shoulder_transverse_max=0.025,
    shoulder_edge_dropoff_m=None,
    shoulder_edge_dropoff_tol_m=None,

    # §3.8 — RADIO ALTIMETER OPERATING AREA.  §3.8.2 "at least 300 m"
    # before the threshold; §3.8.3 "60 m" each side of the extended
    # centre line (the 30 m aeronautical-study reduction is NOT taken —
    # it requires a study this builder cannot perform); §3.8.4 "The rate
    # of change between two consecutive slopes should not exceed 2 per
    # cent per 30 m".  CS ADR-DSN.B.205 corroborates verbatim.
    raoa_length_m=300.0,
    raoa_half_width_m=60.0,
    raoa_max_grade_change_per_m=0.02 / 30.0,

    # ICAO has no runway object free area; the analogous rising-ground
    # limit is §3.4.16, already ``ungraded_strip_max_up_slope`` above.
    rofa_back_slope_ratio_by_adg=None,
    rofa_back_slope_run_m_by_adg=None,
    rofa_half_width_m_by_adg=None,

    # ══════════════════════════════════════════════════════════════════
    # THE FABRIC-MODEL REG SET — ICAO side (W1, PV-2026-08-08)
    # ══════════════════════════════════════════════════════════════════

    # F-1 (R3).  ``strip_half_width_m`` above is Annex 14 §3.4.9, the
    # NON-INSTRUMENT table {1: 30, 2: 40, 3: 75, 4: 75}.  §3.4.8 / CS
    # ADR-DSN.B.175(a) give the INSTRUMENT-runway graded half-width, and
    # it is 40 m at CODE 1, not 30 m.  Encoded, not yet consumed: the
    # emitter still reads the non-instrument table (W2 flip list), and
    # the split affects code-1 instrument runways only — none in the
    # five-airport battery, so it is a correctness fix, not a mover.
    strip_half_width_m_instrument=CodeTable(
        by_code={1: 40.0, 2: 40.0, 3: 75.0, 4: 75.0}, default=75.0),

    # Q5 — the 105 m precision-approach graded half-width is NOT
    # encoded.  Annex 14 §3.4.8 Note + Attachment A §9 and EASA GM1
    # ADR-DSN.B.175(a) Fig. GM-B-4 describe 105 m tapering to 75 m over
    # the last 150 m at each end, but it is GUIDANCE, not specification,
    # and the owner's same-day adoption was REVERSED (RULINGS
    # 2026-08-08 "105 m precision strip DROPPED").  Recorded as
    # unadopted guidance in the reg-set table only.

    # Reg-set ruling 1 — the graded-strip mandatory DOWN is DROPPED on
    # the ICAO ruleset, flagged PROVISIONAL.  Annex 14 §3.4.15 and CS
    # ADR-DSN.B.185(a) state a transverse slope "adequate to prevent the
    # accumulation of water on the surface but should not exceed" 2.5 %
    # (code 3/4) / 3 % (code 1/2) — a CEILING and the 3 m negative lip,
    # and NO minimum anywhere (F-2).  The 1.5 % floor the repo carries
    # on both rulesets is FAA Table 3-6 S-3.  Owner: revisit at the sim
    # look at a strip without the band.
    strip_band_mandatory_down=False,
    strip_band_min_down_slope_authority=None,
    strip_band_drop_provisional=True,

    # F-10 / F-3 — the ICAO taxiway-strip clause (§3.11.5 / CS
    # ADR-DSN.D.330(b)) states flush at the edge, an upward cap and a
    # 5 % downward cap, and NO lip.  Absence verified by full read, so
    # the ICAO taxiway lip the repo applies today is UNSOURCED.
    taxiway_lip_width_m=None,
    taxiway_lip_min_down_slope=None,
    taxiway_lip_max_down_slope=None,
    taxiway_lip_carved_out_of_band=False,

    # R24 — no ICAO taxiway object free area.  §3.11.6 / D.330(c) cap
    # ground beyond the graded portion at 5 % up or down, which is
    # already ``ungraded_strip_max_up_slope``.
    tofa_back_slope_ratio=None,

    # R20 / reg-set ruling 2 — the taxiway cross-fall MINIMUM.  ICAO
    # states NONE.  Annex 14 8th ed. §3.9.11 (and CS ADR-DSN.D.280(b)),
    # verbatim, is the clause the house constant stands in for: the
    # transverse slope "should be sufficient to prevent the accumulation
    # of water on the surface of the taxiway but should not exceed"
    # 1.5 per cent (code letter C, D, E, F) or 2 per cent (A, B).  NO
    # MINIMUM IS STATED ANYWHERE IN THE ICAO OR EASA TEXT, and no crown
    # is mandated.  The owner took reading (b) of Q2: the FAA's 1.0 %
    # becomes a named PROVISIONAL HOUSE CONSTANT here — house, not
    # cited; a future ICAO amendment stating a real floor REPLACES it
    # rather than merely re-blessing it.  1.0 % sits inside the ICAO
    # 1.5 % ceiling with 0.5 pp of headroom.
    # (The 0.010 itself is set above, beside ``runway_transverse_min``,
    # where the recorded-not-bound family already lives — one field, one
    # assignment.)
    taxi_transverse_min_provisional=True,
    taxi_crown_form_binding=False,

    # F-11 / §4.4 — ICAO gives taxiway shoulders width, erosion
    # resistance and strength only, as an OVERALL taxiway-plus-shoulders
    # width by code letter (§3.10.1 / CS ADR-DSN.D.305(a)); there is no
    # per-side width and no slope number (§3.10.1-3.10.2 / D.305).
    taxiway_shoulder_width_m_by_tdg=None,
    taxiway_shoulder_width_m_tdg6_four_engine=None,
    taxiway_shoulder_paved_from_adg=None,
    taxiway_plus_shoulders_total_width_m=dict(
        ICAO_TAXIWAY_PLUS_SHOULDERS_TOTAL_WIDTH_M),

    # R11 / reg-set ruling 3 — the RESA datum, per source.  §3.5.3
    # (**shall**): the RESA "shall extend from the END OF THE RUNWAY
    # STRIP" at least 90 m; the strip itself already runs 60 m past the
    # runway end (§3.4.2; 30 m at code 1 non-instrument).  §3.5.4
    # (recommendation): 240 m (code 3/4), 120 m (code 1/2 instrument),
    # 30 m (code 1/2 non-instrument).  Encoded, not yet consumed —
    # ``RUNWAY_END_CLEARANCE_LENGTH_BY_CODE`` is still the live blend
    # measured from the RUNWAY end (F-4, W2 flip list).
    resa_length_datum="strip_end",
    strip_beyond_end_m=CodeTable(
        by_code={1: 30.0, 2: 60.0, 3: 60.0, 4: 60.0}, default=60.0),
    strip_beyond_end_m_instrument=CodeTable(
        by_code={1: 60.0, 2: 60.0, 3: 60.0, 4: 60.0}, default=60.0),
    resa_length_min_m=90.0,
    resa_length_recommended_m=CodeTable(
        by_code={1: 30.0, 2: 30.0, 3: 240.0, 4: 240.0}, default=240.0),
    resa_length_recommended_m_instrument=CodeTable(
        by_code={1: 120.0, 2: 120.0, 3: 240.0, 4: 240.0}, default=240.0),
    resa_length_is_per_end_function=False,
)


# ══════════════════════════════════════════════════════════════════════
# FAA — AC 150/5300-13B chg 1
# ══════════════════════════════════════════════════════════════════════
#
# APPENDIX G WIDTHS (primary-verified, tables G-1 … G-12).  The AC keys
# its runway design standards by RUNWAY DESIGN CODE = AAC letter +
# ADG numeral; the repo carries only a SIZE proxy (``runway_code_letter``
# from declared runway width).  The faithful mapping, and the one used
# here: a narrow runway (code letter A/B, i.e. ADG I/II) is a
# light-aircraft runway and takes the A/B-I / A/B-II column; letters C-F
# take the C/D/E column, which is 500 ft RSA / 800 ft ROFA for EVERY ADG
# from I to VI (tables G-7 … G-12 are identical in these two columns).
# Visibility-minimum sub-columns: the ≥3/4-mile column is taken (the
# builder has no per-end visibility minimum); the <3/4-mile column is
# wider at A/B-I…III and is NOT taken — recorded, not silently applied.
#
#   G-1/G-2  A/B-I    RSA width 120 ft (36.6 m)  ROFA width 400 ft
#   G-3/G-4  A/B-II   RSA width 150 ft (45.7 m)  ROFA width 500 ft
#   G-5      A/B-III  RSA width 300 ft (91.4 m)  ROFA width 800 ft
#   G-6      A/B-IV   RSA width 500 ft (152.4 m) ROFA width 800 ft
#   G-7..12  C/D/E-*  RSA width 500 ft (152.4 m) ROFA width 800 ft
#
# HALF-widths (from the runway centreline) are half of the above.  Note
# the C/D/E half-width 76.2 m vs the live ICAO 75 m: the strip footprint
# widens ~1.2 m at FAA airports, which is the predicted KCLT row-6 delta.
#
# W1 (2026-08-08): these two tables are no longer hand-written literals.
# They are the CODE-LETTER VIEW of ``FAA_RSA_WIDTH_FT_BY_RDC`` /
# ``FAA_ROFA_WIDTH_FT_BY_RDC`` at the ``FAA_VISIBILITY_DEFAULT``
# (≥3/4-mile) column — one copy of every Appendix G number, and the
# three-axis matrix is where the missing A/B-III / A/B-IV rows and the
# visibility axis now live (F-9).  ``tests/test_fabric_reg_set_w1.py``
# pins each derived value against the literal the repo carried before
# the derivation, so this is a re-rooting, never a re-valuing.
FAA_RSA_HALF_WIDTH_M_BY_LETTER = {
    letter: faa_rsa_half_width_m(*rdc)
    for letter, rdc in FAA_RDC_BY_CODE_LETTER.items()
}
FAA_ROFA_HALF_WIDTH_M_BY_LETTER = {
    letter: faa_rofa_half_width_m(*rdc)
    for letter, rdc in FAA_RDC_BY_CODE_LETTER.items()
}

FAA_RULESET = Ruleset(
    key="faa",
    name="FAA AC 150/5300-13B",
    authority="FAA",

    # §3.16.1: maximum longitudinal grade 2.0 % for AAC A/B, 1.5 % for
    # AAC C/D/E.  Keyed here by the repo's runway CODE LETTER (the AAC
    # proxy — see ADG_BY_CODE_LETTER); at code letter C and above this
    # equals the live blended ``RUNWAY_MAX_GRADE``, which is why KCLT
    # (ADG V) sees no row-1 change.
    runway_max_grade=CodeTable(
        by_letter=_letters(narrow=0.020, wide=RUNWAY_MAX_GRADE),
        default=RUNWAY_MAX_GRADE),

    # §3.16.1: grades exceeding 0.8 % are not acceptable within the
    # LESSER of the first/last quarter and 2,500 ft (762 m), AAC C/D/E.
    # A/B carries no end-zone rule.
    runway_end_grade=CodeTable(
        by_letter=_letters(narrow=None, wide=RUNWAY_END_GRADE),
        default=RUNWAY_END_GRADE),
    runway_end_zone_max_length_m=762.0,
    runway_end_grade_precision_only_codes=frozenset(),

    # §3.16.1: maximum grade CHANGE ±2.0 % (A/B), ±1.5 % (C/D/E).
    runway_max_grade_change=CodeTable(
        by_letter=_letters(narrow=0.020, wide=0.015), default=0.015),

    # §3.16.1: vertical curve length 1,000 ft (305 m) per 1 % of grade
    # change for C/D/E, 300 ft (91.4 m) per 1 % for A/B; no vertical
    # curve is required where the grade change is less than 0.4 %.
    runway_vertical_curve_k_m=CodeTable(
        by_letter=_letters(narrow=91.4, wide=RUNWAY_VERTICAL_CURVE_K_M),
        default=RUNWAY_VERTICAL_CURVE_K_M),
    # §3.16.1.1 (AAC A/B) states "a vertical curve is not necessary when
    # the grade change is less than 0.40 percent"; §3.16.1.2 (C/D/E)
    # states NO such relief.  Jurisdictional fidelity ⇒ the relief is
    # granted only where the AC grants it; C-F get None (stricter
    # contained reading, same discipline as the ≤30,000 lb taxiway
    # relaxation below).
    runway_vertical_curve_min_change=CodeTable(
        by_letter=_letters(narrow=0.004, wide=None), default=None),

    # §3.16.5 Standards item 1: between the runway ends the RSA's
    # longitudinal grades, grade changes, vertical curves and distance
    # between changes "are the same as the comparable standards for the
    # runway and stopway" — i.e. the runway's own cap, code-invariant in
    # number but AAC-keyed exactly as row 1 is.
    strip_max_longitudinal_slope=CodeTable(
        by_letter=_letters(narrow=0.020,
                           wide=RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_FAA),
        default=RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_FAA),
    # §3.16.5 item 5: "Limitations on longitudinal grade changes are
    # ±2.0 percent per 100 feet (30.5 m)."  Cited, not provisional.
    strip_arc_rate_per_m=0.02 / 30.5,
    strip_arc_rate_provisional=False,

    # RSA half-width from AC Appendix G — see
    # ``FAA_RSA_HALF_WIDTH_M_BY_LETTER`` below for the per-table pull and
    # the AAC-column reasoning.
    strip_half_width_m=CodeTable(
        by_letter=FAA_RSA_HALF_WIDTH_M_BY_LETTER, default=76.2),

    # ROWS 7/8 — DEFERRED (owner question 1), blended values retained on
    # BOTH rulesets.  The FAA numbers these fields hold are also the
    # blend's source: Fig 3-33 Detail A (3-5 % for the first 10 ft) and
    # Table 3-6 S-3 (RSA side slope 1.5-5 % A/B, 1.5-3 % C/D/E).
    strip_lip_width_m=ADJACENT_GROUND_LIP_WIDTH_M,
    strip_lip_min_down_slope=ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE,
    strip_lip_max_down_slope=ADJACENT_GROUND_LIP_MAX_DOWN_SLOPE,
    strip_band_min_down_slope=RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE,
    strip_band_max_down_slope=CodeTable(
        by_code=dict(RUNWAY_STRIP_BAND_MAX_DOWN_SLOPE_BY_CODE),
        default=0.03),

    # Rising ground beyond the graded strip: the FAA form of this limit
    # is the ROFA BACK SLOPE (Table 3-7 S-5), bound per-ADG below; the
    # 5 % here remains the fallback outside the ROFA band.
    ungraded_strip_max_up_slope=ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE,

    # §3.16.5 items 2-5: the first 200 ft (61 m) beyond the runway end
    # falls 0 to −3 %; beyond that −5 %; grade changes ±2 % per 100 ft
    # (30.5 m).  These are the repo's LIVE end-skirt constants.
    # These four numbers are the repo's LIVE end-skirt law; ``grade_law``
    # re-exports them from HERE under its existing
    # ``RUNWAY_END_SKIRT_*`` names, so there is exactly one copy.
    end_skirt_near_zone_m=61.0,
    end_skirt_near_max_down_grade=0.03,
    end_skirt_max_down_grade=0.05,
    end_skirt_max_grade_change_per_m=0.02 / 30.5,
    end_skirt_rate_provisional=False,

    # §3.16.5 item 6 + Table 3-6 S-3: within the first 200 ft (61 m)
    # beyond the end the RSA transverse takes the S-3 band —
    # 1.5-5 % (A/B), 1.5-3 % (C/D/E).  Beyond 61 ft the AC states no
    # transverse number in text; Figure 3-35 shows ±5.0 % across the RSA
    # width, which is what ``resa_transverse_max`` binds.
    resa_transverse_near=CodeTable(
        by_letter=_letters(narrow=0.015, wide=0.015), default=0.015),
    resa_transverse_near_max=CodeTable(
        by_letter=_letters(narrow=0.05, wide=0.03), default=0.03),
    resa_transverse_max=0.05,

    # §4.14.1: taxiway longitudinal grade 1.5 %.  The AC permits 2 % on
    # pavement serving exclusively airplanes ≤30,000 lb; that relaxation
    # is NOT taken — the builder does not know a taxiway's fleet, so the
    # stricter contained reading applies (noted, not silent).
    taxi_max_grade=CodeTable(
        by_letter=_letters(narrow=TAXI_MAX_GRADE, wide=TAXI_MAX_GRADE),
        default=TAXI_MAX_GRADE),
    # §4.14.2 item 1a: taxiway transverse grade 1.0-1.5 %.
    taxi_transverse_max=CodeTable(
        by_letter=_letters(narrow=TAXI_MAX_GRADE, wide=TAXI_MAX_GRADE),
        default=TAXI_MAX_GRADE),
    # RECORDED, NOT BOUND (owner question 5): the 1.0 % lower bound of
    # §4.14.2 item 1a, and Table 3-6 S-1's runway transverse minimum.
    taxi_transverse_min=0.010,
    runway_transverse_min=0.010,
    runway_transverse_max=CodeTable(
        by_letter=_letters(narrow=0.020, wide=0.015), default=0.015),

    # §5.9.2 (recommendation): aircraft parking positions ≤1 %.
    stand_max_grade=0.01,
    # §5.9.1 Standards: "Provide a minimum 0.5 percent apron gradient"
    # and a maximum apron grade change of 2 %.
    apron_min_drainage_grade=0.005,
    apron_max_grade_change=0.02,

    # §4.14.2 item 5: TSA transverse 1.5-5 %.  The graded half-width
    # comes from the AC's TSA width tables; until those columns are
    # pulled per group the ICAO/EASA OMGWS widths stand (they are the
    # repo's live geometry and are the narrower, contained reading).
    taxiway_strip_band_min_down_slope=0.015,
    taxiway_strip_band_max_down_slope=0.05,
    taxiway_strip_graded_half_width_m=dict(
        TAXIWAY_STRIP_GRADED_HALF_WIDTH_BY_LETTER),

    # Table 3-6 S-2 / §4.14.2 item 3: paved shoulders 1.5-5.0 % down.
    # §4.14.2 item 2 (repeated for aprons at §5.9.1): the paved-to-
    # unpaved edge drop-off is 1.5 in ± 0.5 in = 38 ± 13 mm — a MANDATED
    # small step, which is why the step checks carry an FAA-only
    # exemption for it (§B1).
    shoulder_transverse_min=0.015,
    shoulder_transverse_max=0.05,
    shoulder_edge_dropoff_m=0.038,
    shoulder_edge_dropoff_tol_m=0.013,

    # NO FAA EQUIVALENT of the radio altimeter operating area: the
    # string "radio altimeter" does not appear in AC 150/5300-13B.  The
    # §A4 family is therefore a no-op under this ruleset — KCLT is
    # unaffected by it (jurisdictional fidelity).
    raoa_length_m=None,
    raoa_half_width_m=None,
    raoa_max_grade_change_per_m=None,

    # Table 3-7 — RUNWAY OBJECT FREE AREA.  The owner APPROVED the
    # existing-runway exemption (docs/RULINGS.md 2026-08-02): S-4, the
    # ≤0 % side-slope rule, does NOT bind.  S-5, the BACK SLOPE, does:
    # 8:1 (ADG I-II), 10:1 (III-IV), 16:1 (V-VI) — run:rise, so 8:1 is a
    # 12.5 % maximum rise.  D-1 is the run over which it is measured.
    rofa_back_slope_ratio_by_adg=_by_adg(
        I=8.0, II=8.0, III=10.0, IV=10.0, V=16.0, VI=16.0),
    rofa_back_slope_run_m_by_adg=_by_adg(
        I=7.6, II=12.2, III=18.0, IV=26.2, V=32.6, VI=39.9),
    rofa_half_width_m_by_adg=FAA_ROFA_HALF_WIDTH_M_BY_LETTER,

    # ══════════════════════════════════════════════════════════════════
    # THE FABRIC-MODEL REG SET — FAA side (W1, PV-2026-08-08)
    # ══════════════════════════════════════════════════════════════════

    # F-1 is an ICAO finding: the AC has no instrument/non-instrument
    # split at all — Appendix G keys AAC × ADG × VISIBILITY MINIMUM, and
    # that third axis is ``FAA_RSA_WIDTH_FT_BY_RDC`` above.
    strip_half_width_m_instrument=None,

    # Q5 — NOT encoded here either.  The AC has NO precision-approach
    # widening at all: its RSA width is a flat 500 ft (76.2 m
    # half-width) for every C/D/E code, and the only visibility-driven
    # widening is in the A/B families (F-9).  That missing anchor is the
    # owner's stated reason for the reversal — "If there's no FAA
    # citation for the 105 m precision strip, we can drop it as well"
    # (RULINGS 2026-08-08 "105 m precision strip DROPPED").

    # Reg-set ruling 1 — the FAA side KEEPS the mandatory fall, and it
    # is that authority's own Standard: Table 3-6 row S-3, RSA side
    # slope 1.5 %-5.0 % (AAC-A, AAC-B) and 1.5 %-3.0 % (AAC-C, D, E) —
    # a real MINIMUM of 1.5 %.  KCLT keeps the FAA form.
    strip_band_mandatory_down=True,
    strip_band_min_down_slope_authority=0.015,
    strip_band_drop_provisional=False,

    # F-10 — THE SECOND LIP FAMILY.  ¶4.14.2 *Standards* item 4, on
    # p. 4-46, verbatim: "For an unpaved surface adjacent to a paved
    # surface, design a 5 ±0.5 percent transverse gradient for a minimum
    # distance of 10 feet (3 m) from the paved surface" ⇒ 4.5 %-5.5 %
    # over the first 3 m at ANY paved→unpaved edge — taxiway, taxilane
    # and (because the clause is written for "an unpaved surface
    # adjacent to a paved surface") apron edges too.
    # THIS IS NOT THE RUNWAY LIP.  The runway/shoulder/stopway edge is
    # Figure 3-33 Detail A note 2, "Maintain between a 3% -5% negative
    # grade for 10 ft (3 m)".  The widths agree (3 m); the bands differ
    # in BOTH directions — steeper at the floor (4.5 vs 3.0) and above
    # the runway ceiling (5.5 vs 5.0).  The repo consumes the runway
    # band on both branches today (W2 flip list).
    taxiway_lip_width_m=3.0,
    taxiway_lip_min_down_slope=0.045,
    taxiway_lip_max_down_slope=0.055,
    # ¶4.14.2 item 5 states the TSA band "except as noted in
    # subparagraph 4 above" — the lip is carved OUT of the 1.5-5 % TSA
    # band, so the two are a near-zone/far-zone pair like the RSA's.
    taxiway_lip_carved_out_of_band=True,

    # R24 — TOFA back slope, FAA ONLY, new this round.  ¶4.14.2
    # *Standards* item 6b + Figure 4-29 (p. 4-45): where a back slope is
    # necessary it is ≤4:1, "provided the area immediately adjacent to
    # the TSA edge permits positive drainage of surface water away from
    # the TSA".  Item 6a leaves the TOFA SIDE slope qualitative —
    # "design transverse gradient to promote positive drainage away from
    # the TSA", no number, unlike the runway ROFA's S-4.  A ceiling
    # (cut), never a mandate to shape; 4:1 is far steeper than any ROFA
    # value so it will rarely bind, but its absence left the FAA taxiway
    # branch with NO far-zone ceiling at all.
    tofa_back_slope_ratio=4.0,

    # R20 / reg-set ruling 2 — the taxiway cross-fall MINIMUM is the
    # FAA's own Standard.  ¶4.14.2 *Taxiway/Taxilane Transverse
    # Gradient*, Standards, item 1 (p. 4-46), verbatim: "Design
    # taxiway/taxilane pavement transverse gradient as follows: a. 1.0 to
    # 1.5 percent from centerline to pavement edge. b. For
    # taxiways/taxilanes exclusively serving aircraft weighing less than
    # 30,000 lbs (13,605 kg), it is acceptable to apply a cross-slope of
    # 1 to 2 percent. c. A constant slope section (aka shed section) may
    # be more suitable: i. For high-speed exit taxiways. ii. When
    # existing terrain makes it impractical to provide a crown and slope
    # cross section."  The ≤30,000 lb relaxation is NOT taken (the
    # builder does not know a taxiway's fleet).
    # BIND THE MINIMUM, NOT THE CROWN FORM: the cross-fall is a
    # *Standard*; the centre crown is only a *Recommended Practice* on
    # the same page ("The ideal configuration is a center crown with
    # equal, constant transverse grades on either side"), and item 1c
    # explicitly admits a constant-slope shed section.  So 1.0 % is
    # primary-sourced and bindable while a mandated crown is not.
    taxi_transverse_min_provisional=False,
    taxi_crown_form_binding=False,

    # F-11 / §4.4 — taxiway shoulder WIDTH is keyed by TDG (Table 4-2
    # row *Taxiway Shoulder Width* + fn 3, p. 4-10, reached via ¶4.13.1
    # *Standards* item 1), while PROVISION stays ADG-keyed (¶4.13.1
    # item 2: paved for ADG-IV and larger).  The repo carried the width
    # "by ADG"; that key was wrong even though no number was.
    taxiway_shoulder_width_m_by_tdg=dict(
        FAA_TAXIWAY_SHOULDER_WIDTH_M_BY_TDG),
    taxiway_shoulder_width_m_tdg6_four_engine=(
        FAA_TAXIWAY_SHOULDER_WIDTH_M_TDG6_FOUR_ENGINE),
    taxiway_shoulder_paved_from_adg="IV",
    taxiway_plus_shoulders_total_width_m=None,

    # R11 / F-12 / reg-set ruling 3 — the FAA end corridor.  DATUM:
    # App. G fn 9, the runway end, or the STOPWAY end where a stopway is
    # present.  LENGTH: dims R and P, PER END, a function of RDC ×
    # visibility minimum × vertical guidance (fn 11) — see
    # :func:`faa_rsa_end_length_m`.  It is deliberately NOT a constant:
    # flattening it is exactly the hole F-12 names, where an FAA
    # airport's end-corridor length is today the ICAO-derived blend.
    resa_length_datum="runway_or_stopway_end",
    strip_beyond_end_m=None,        # the FAA has no separate "strip"
    strip_beyond_end_m_instrument=None,
    resa_length_min_m=None,
    resa_length_recommended_m=None,
    resa_length_recommended_m_instrument=None,
    resa_length_is_per_end_function=True,
)


# ══════════════════════════════════════════════════════════════════════
# THE REGISTRY + REGION RESOLUTION (spec §1, §2)
# ══════════════════════════════════════════════════════════════════════
#: Ruleset key → constants record.  Open-ended by construction: "tp312"
#: (Canada), "casa" (Australia) etc. are added by appending a
#: ``Ruleset(...)`` here, with no structural change and no new branch at
#: any law site (the owner's "multiple rulesets in the future" clause).
RULESETS = {
    ICAO_RULESET.key: ICAO_RULESET,
    FAA_RULESET.key: FAA_RULESET,
}

#: The fail-safe key.  The owner's own words are "FAA applies within the
#: USA, and ICAO everywhere else", so "everywhere else" is also what an
#: unparseable identifier gets.
DEFAULT_RULESET = "icao"

#: ICAO location-indicator prefixes that select the FAA ruleset.
#: "K" = the contiguous United States.  The two-letter P-prefixes are the
#: US territories that keep FAA jurisdiction: PA (Alaska), PH (Hawaii),
#: PG (Guam / Northern Marianas), PJ (Johnston Atoll), PM (Midway),
#: PW (Wake).  Other P… indicators (PK Marshall Is., PT Micronesia/
#: Palau, PL Kiribati) are sovereign states and stay ICAO.
FAA_RULESET_FIRST_LETTERS = frozenset({"K"})
FAA_RULESET_TWO_LETTER_PREFIXES = frozenset({
    "PA", "PH", "PG", "PJ", "PM", "PW"})

#: TESTING OVERRIDE ONLY — not a law gate.  The resolver twin and the
#: cross-authority twins force a key on a fixture airport with this; an
#: empty/unset value is the production path (resolve from the ICAO
#: identifier).  Read at call time, never cached, so a monkeypatched
#: environment takes effect inside one process.
_RULESET_ENV = "O4_RULESET"


def resolve_ruleset(icao) -> str:
    """The RULESET KEY that governs airport ``icao`` — owner ruling
    2026-08-02, "FAA applies within the USA, and ICAO everywhere else".

    USA = the contiguous states (K…) plus the FAA-jurisdiction Pacific
    and Alaskan territories (PA/PH/PG/PJ/PM/PW).  Everything else —
    including Canada (C…) and Mexico (M…) — is ICAO under the owner's
    own text; an empty or unparseable identifier is ICAO too, which is
    the owner's stated default rather than a stricter-of guess.

    NOT the same resolver as ``eat_surface_slope_and_setback`` /
    ``EAT_FAA_ICAO_PREFIXES`` ({K, C, P, M}).  That set implements a
    DIFFERENT and earlier owner ruling — "FAA for North America" —
    scoped to the end-around-taxiway departure surface, and it is
    deliberately untouched here.  The two coexist, each citing its own
    ruling; harmonizing them is an owner question, not an assumption.
    """
    forced = _os.environ.get(_RULESET_ENV, "").strip().lower()
    if forced:
        if forced not in RULESETS:
            raise ValueError(
                f"{_RULESET_ENV}={forced!r} is not a known ruleset "
                f"({sorted(RULESETS)})")
        return forced
    code = str(icao or "").strip().upper()
    if not code:
        return DEFAULT_RULESET
    if code[0] in FAA_RULESET_FIRST_LETTERS:
        return "faa"
    if code[:2] in FAA_RULESET_TWO_LETTER_PREFIXES:
        return "faa"
    return DEFAULT_RULESET


def get_ruleset(ruleset=None) -> Ruleset:
    """Coerce ``ruleset`` — a key, a :class:`Ruleset`, or ``None`` — to
    the record.  ``None`` means the default ruleset; callers that have an
    ICAO identifier should pass ``resolve_ruleset(icao)`` instead so the
    law they read is the law the airport is governed by.

    An unknown key raises: a law must never silently fall back to
    another authority's numbers.
    """
    if ruleset is None:
        return RULESETS[DEFAULT_RULESET]
    if isinstance(ruleset, Ruleset):
        return ruleset
    key = str(ruleset).strip().lower()
    try:
        return RULESETS[key]
    except KeyError:
        raise ValueError(
            f"unknown ruleset {ruleset!r} (known: {sorted(RULESETS)})")


#: Every SPLIT family, as ``(accessor name, keying)``.  The lockstep twin
#: iterates this so a family added to :class:`Ruleset` without an
#: accessor — or an accessor that reads a bare module constant instead of
#: the ruleset — is caught by a test rather than by an airport.
RULESET_SPLIT_FAMILIES = (
    ("runway_max_grade", "code_number|code_letter"),
    ("runway_end_grade", "code_number|code_letter"),
    ("runway_max_grade_change", "code_number|code_letter"),
    ("runway_vertical_curve_k_m", "code_number|code_letter"),
    ("runway_vertical_curve_min_change", "code_number|code_letter"),
    ("strip_max_longitudinal_slope", "code_number|code_letter"),
    ("strip_half_width_m", "code_number|code_letter"),
    ("strip_half_width_m_instrument", "code_number"),
    ("strip_band_max_down_slope", "code_number"),
    ("strip_beyond_end_m", "code_number"),
    ("strip_beyond_end_m_instrument", "code_number"),
    ("resa_length_recommended_m", "code_number"),
    ("resa_length_recommended_m_instrument", "code_number"),
    ("resa_transverse_near", "code_letter"),
    ("resa_transverse_near_max", "code_letter"),
    ("taxi_max_grade", "code_letter"),
    ("taxi_transverse_max", "code_letter"),
    ("runway_transverse_max", "code_letter"),
)


# ── Family accessors — the ONLY way a law site reads a split constant ──
# Each takes the class keys it needs plus ``ruleset`` (a key or record),
# and both the emitter and the validator call the same one.

def ruleset_runway_max_grade(code_number=None, code_letter=None,
                             ruleset=None) -> float:
    """§4 row 1 — runway longitudinal grade cap."""
    return get_ruleset(ruleset).runway_max_grade.value(
        code_number, code_letter)


def ruleset_runway_end_grade(code_number=None, code_letter=None,
                             approach_class=None, ruleset=None):
    """§4 row 2 — the first/last-quarter longitudinal cap, or ``None``
    where this authority states none for the class.

    ICAO applies the 0.8 % limit unconditionally at code 4 but at code 3
    only on a PRECISION APPROACH CATEGORY II OR III runway (§3.1.14);
    ``approach_class`` is the per-end class from
    :func:`runway_end_approach_class`.  Passing ``None`` for it means
    "unknown", which resolves to the CAP APPLYING — missing data must
    never buy the permissive reading.
    """
    rs = get_ruleset(ruleset)
    cap = rs.runway_end_grade.value(code_number, code_letter)
    if cap is None:
        return None
    if (code_number is not None
            and int(code_number) in rs.runway_end_grade_precision_only_codes
            and approach_class is not None
            and str(approach_class) != "precision"):
        return None
    return cap


def ruleset_runway_end_zone_length_m(runway_length_m: float,
                                     ruleset=None) -> float:
    """§4 row 2 — the LENGTH of one end zone.  ICAO says "the first and
    last quarter of the length"; FAA §3.16.1.2 says the LESSER of that
    quarter and 2,500 ft (762 m)."""
    rs = get_ruleset(ruleset)
    quarter = rs.runway_end_zone_fraction * float(runway_length_m or 0.0)
    if rs.runway_end_zone_max_length_m is None:
        return quarter
    return min(quarter, rs.runway_end_zone_max_length_m)


def ruleset_runway_max_grade_change(code_number=None, code_letter=None,
                                    ruleset=None) -> float:
    """§4 row 3 — maximum change between two consecutive runway slopes."""
    return get_ruleset(ruleset).runway_max_grade_change.value(
        code_number, code_letter)


def ruleset_runway_vertical_curve_k_m(code_number=None, code_letter=None,
                                      ruleset=None) -> float:
    """§4 row 4 — metres of vertical curve per 1 % of grade change."""
    return get_ruleset(ruleset).runway_vertical_curve_k_m.value(
        code_number, code_letter)


def ruleset_runway_max_grade_change_per_m(code_number=None, code_letter=None,
                                          ruleset=None) -> float:
    """§4 row 4, in the segment-smoother's unit: grade change (as a
    fraction, not a percent) per metre of pavement — the ruleset-keyed
    replacement for ``RUNWAY_MAX_GRADE_CHANGE_PER_M``.

    ``K`` metres per 1 % ⇒ 0.01 grade per K metres ⇒ 0.01/K per metre.
    (ICAO code 4: K = 300 ⇒ 1/30000, which is the live blended value.)
    """
    k = ruleset_runway_vertical_curve_k_m(code_number, code_letter, ruleset)
    if not k:
        return RUNWAY_MAX_GRADE_CHANGE_PER_M
    return 0.01 / float(k)


def ruleset_runway_vertical_curve_min_change(code_number=None,
                                             code_letter=None, ruleset=None):
    """§4 row 4 — grade change below which the authority requires no
    vertical curve, or ``None`` where it grants no such relief."""
    return get_ruleset(ruleset).runway_vertical_curve_min_change.value(
        code_number, code_letter)


def ruleset_strip_max_longitudinal_slope(code_number=None, code_letter=None,
                                         ruleset=None) -> float:
    """§4 row 5 — the graded strip's along-runway slope cap."""
    return get_ruleset(ruleset).strip_max_longitudinal_slope.value(
        code_number, code_letter)


def ruleset_strip_arc_rate_per_m(ruleset=None):
    """§A3(b) — rate of longitudinal slope change on the graded strip
    (grade change per metre).  PROVISIONAL under ICAO: see
    ``Ruleset.strip_arc_rate_provisional`` and owner question 2."""
    return get_ruleset(ruleset).strip_arc_rate_per_m


def ruleset_strip_half_width_m(code_number=None, code_letter=None,
                               ruleset=None) -> float:
    """§4 row 6 — graded runway-strip / RSA half-width from the
    centreline."""
    return get_ruleset(ruleset).strip_half_width_m.value(
        code_number, code_letter)


def ruleset_strip_band_max_down_slope(code_number=None, ruleset=None) -> float:
    """§4 row 7 — zone-2 maximum down slope.  BOTH rulesets currently
    carry the blended value; owner question 1 gates the split."""
    return get_ruleset(ruleset).strip_band_max_down_slope.value(code_number)


def ruleset_taxi_max_grade(code_letter=None, ruleset=None) -> float:
    """§4 row 13 — taxiway longitudinal grade cap."""
    return get_ruleset(ruleset).taxi_max_grade.value(None, code_letter)


def ruleset_taxi_transverse_max(code_letter=None, ruleset=None) -> float:
    """§4 row 14 — taxiway transverse (cross-slope) cap."""
    return get_ruleset(ruleset).taxi_transverse_max.value(None, code_letter)


def ruleset_stand_max_grade(ruleset=None) -> float:
    """§4 row 15 — aircraft-stand maximum slope (IDENT across
    authorities; the accessor exists so a future ruleset can differ)."""
    return get_ruleset(ruleset).stand_max_grade


def ruleset_apron_min_drainage_grade(ruleset=None):
    """§B3 — minimum apron gradient, or ``None`` where the authority
    states no number (ICAO §3.13.4 is qualitative)."""
    return get_ruleset(ruleset).apron_min_drainage_grade


def ruleset_apron_max_grade_change(ruleset=None):
    """§B3 — maximum apron grade change (FAA §5.9.1.3, 2 %)."""
    return get_ruleset(ruleset).apron_max_grade_change


def ruleset_shoulder_transverse_band(ruleset=None):
    """§B1 — ``(min, max)`` transverse for a PAVED shoulder.  ``min`` is
    ``None`` where the authority mandates flush instead of a fall."""
    rs = get_ruleset(ruleset)
    return (rs.shoulder_transverse_min, rs.shoulder_transverse_max)


def ruleset_shoulder_edge_dropoff(ruleset=None):
    """§B1 — ``(drop_m, tolerance_m)`` of the MANDATED paved→unpaved edge
    step, or ``(None, None)`` where the authority mandates flush."""
    rs = get_ruleset(ruleset)
    return (rs.shoulder_edge_dropoff_m, rs.shoulder_edge_dropoff_tol_m)


# ══════════════════════════════════════════════════════════════════════
# THE FABRIC-MODEL REG SET — accessors (W1, 2026-08-08)
# ══════════════════════════════════════════════════════════════════════
# ONE accessor per family, exactly as the 2026-08-02 rulesets ruling
# requires: "Emitters and validators read the SAME ruleset (lockstep)."
# Every W1 family gets its reader HERE even where W2 will be the first
# caller — a family whose emitter and validator each grow their own
# reader is the census-wrapper defect in a different costume.

def ruleset_strip_half_width_m_instrument(code_number=None, ruleset=None):
    """F-1 — the INSTRUMENT-runway graded half-width (Annex 14 §3.4.8 /
    CS ADR-DSN.B.175(a)), or ``None`` where the authority does not split
    on instrument status.

    :func:`ruleset_strip_half_width_m` is the NON-instrument table
    (§3.4.9); the two differ only at code 1 (40 m vs 30 m)."""
    table = get_ruleset(ruleset).strip_half_width_m_instrument
    return None if table is None else table.value(code_number)


# NO ``ruleset_strip_precision_*`` accessor: Q5's 105 m graded strip is
# NOT part of this reg set.  RULINGS 2026-08-08 "105 m precision strip
# DROPPED" reversed the same-day adoption — specification values only.


def ruleset_strip_band_authority_min_down_slope(ruleset=None):
    """Reg-set ruling 1 — the authority's OWN mandatory fall across the
    graded strip, or ``None`` where it mandates none.

    NOT ``Ruleset.strip_band_min_down_slope``, which is the LIVE BLEND
    the emitter reads with W2's ``O4_FABRIC_W2_ICAO_STRIP_AUTHORITY`` flag
    OFF; see ``RULESET_W2_FLIPS``."""
    return get_ruleset(ruleset).strip_band_min_down_slope_authority


def ruleset_strip_band_mandatory_down(ruleset=None) -> bool:
    """Whether this authority mandates a DOWNWARD graded-strip band at
    all (FAA yes, Table 3-6 S-3; ICAO no, ruling 1 — PROVISIONAL)."""
    return bool(get_ruleset(ruleset).strip_band_mandatory_down)


def ruleset_runway_edge_lip(ruleset=None):
    """F-10, lip family 1 — ``(width_m, min_down, max_down)`` of the lip
    at a RUNWAY / shoulder / stopway edge.

    ICAO §3.4.15 final clause: the first 3 m outward "shall be negative"
    and "may be as great as 5 per cent".  FAA Figure 3-33 Detail A note
    2: "Maintain between a 3% -5% negative grade for 10 ft (3 m) of
    unpaved surface adjacent to the paved surface." """
    rs = get_ruleset(ruleset)
    return (rs.strip_lip_width_m, rs.strip_lip_min_down_slope,
            rs.strip_lip_max_down_slope)


def ruleset_taxiway_edge_lip(ruleset=None):
    """F-10, lip family 2 — ``(width_m, min_down, max_down)`` of the lip
    at a TAXIWAY / TAXILANE / APRON (any paved→unpaved) edge, or
    ``(None, None, None)`` where the authority states none.

    FAA ¶4.14.2 *Standards* item 4: 5 ±0.5 % over ≥10 ft (3 m) ⇒
    4.5-5.5 %.  ICAO: no lip clause at all (§3.11.5 / D.330(b) — absence
    verified by full read), so the ICAO taxiway lip is UNSOURCED."""
    rs = get_ruleset(ruleset)
    return (rs.taxiway_lip_width_m, rs.taxiway_lip_min_down_slope,
            rs.taxiway_lip_max_down_slope)


def ruleset_taxiway_lip_carved_out_of_band(ruleset=None) -> bool:
    """¶4.14.2 item 5's "except as noted in subparagraph 4 above" — the
    taxiway lip is carved OUT of the TSA band (a near-zone/far-zone
    pair), never an alternative to it."""
    return bool(get_ruleset(ruleset).taxiway_lip_carved_out_of_band)


def ruleset_tofa_back_slope_ratio(ruleset=None):
    """R24 — the taxiway/taxilane object-free-area BACK slope ceiling as
    a run:rise ratio (FAA 4.0 ⇒ 25 % maximum rise), or ``None`` where
    the authority has no object-free-area family.

    A CEILING (cut), never a mandate to shape."""
    return get_ruleset(ruleset).tofa_back_slope_ratio


def ruleset_taxi_transverse_min_provisional(ruleset=None) -> bool:
    """Reg-set ruling 2 — True where ``taxi_transverse_min`` is a named
    repo HOUSE CONSTANT rather than that authority's own number."""
    return bool(get_ruleset(ruleset).taxi_transverse_min_provisional)


def ruleset_taxi_crown_form_binding(ruleset=None) -> bool:
    """Whether a centre CROWN is mandated (as against the cross-fall
    MINIMUM being mandated).  False on both rulesets: the FAA crown is a
    *Recommended Practice* and ICAO mandates no crown at all."""
    return bool(get_ruleset(ruleset).taxi_crown_form_binding)


def ruleset_taxiway_shoulder_width_m(tdg=None, ruleset=None, *,
                                     four_engine: bool = False):
    """F-11 — paved taxiway-shoulder width PER SIDE, keyed by TAXIWAY
    DESIGN GROUP (AC Table 4-2), or ``None`` where the authority states
    no per-side width (ICAO gives an overall taxiway-plus-shoulders
    width instead — :func:`ruleset_taxiway_plus_shoulders_total_width_m`).

    Table 4-2 fn 3: a TDG-6 taxiway whose most demanding aircraft has
    four or more engines takes 40 ft (12.2 m)."""
    rs = get_ruleset(ruleset)
    widths = rs.taxiway_shoulder_width_m_by_tdg
    if widths is None:
        return None
    key = str(tdg).upper() if tdg is not None else None
    if (four_engine and key == "6"
            and rs.taxiway_shoulder_width_m_tdg6_four_engine is not None):
        return rs.taxiway_shoulder_width_m_tdg6_four_engine
    return widths.get(key)


def ruleset_taxiway_shoulder_paved_from_adg(ruleset=None):
    """F-11 — PROVISION stays ADG-keyed: the smallest ADG at which paved
    taxiway shoulders are a Standard (FAA ¶4.13.1 item 2: "IV"), or
    ``None``.  Width TDG, provision ADG — two axes, kept apart."""
    return get_ruleset(ruleset).taxiway_shoulder_paved_from_adg


def ruleset_taxiway_plus_shoulders_total_width_m(code_letter=None,
                                                 ruleset=None):
    """ICAO §3.10.1 / CS ADR-DSN.D.305(a) — OVERALL taxiway-plus-
    shoulders width by code letter, or ``None`` (the FAA states a
    per-side width instead)."""
    widths = get_ruleset(ruleset).taxiway_plus_shoulders_total_width_m
    if widths is None or not code_letter:
        return None
    return widths.get(str(code_letter).upper())


def ruleset_resa_length_datum(ruleset=None):
    """Reg-set ruling 3 — where THIS authority measures the end corridor
    from: ``"strip_end"`` (ICAO §3.5.3) or ``"runway_or_stopway_end"``
    (AC App. G fn 9)."""
    return get_ruleset(ruleset).resa_length_datum


def ruleset_strip_beyond_end_m(code_number=None, ruleset=None,
                               instrument: bool = False):
    """ICAO §3.4.2 — how far the runway STRIP extends beyond the runway
    or stopway end (the ICAO datum's offset), or ``None`` where the
    authority has no separate strip (the FAA)."""
    rs = get_ruleset(ruleset)
    table = (rs.strip_beyond_end_m_instrument if instrument
             else rs.strip_beyond_end_m)
    return None if table is None else table.value(code_number)


def ruleset_resa_length_m(code_number=None, ruleset=None, *,
                          instrument: bool = False,
                          mandate: str = "shall"):
    """The ICAO end-corridor length measured from ITS OWN datum (the
    strip end), or ``None`` where the authority states no such constant.

    ``mandate="shall"`` returns the §3.5.3 hard floor (90 m);
    ``mandate="recommended"`` the §3.5.4 recommendation (240 m at code
    3/4; 120 m at code 1/2 instrument; 30 m at code 1/2 non-instrument).
    Mandate-vs-recommendation is handled as a KEY, per ruling 3, so a
    caller can never silently take the softer number.

    The FAA returns ``None`` here on purpose: its length is a per-end
    FUNCTION (:func:`faa_rsa_end_length_m`), and
    ``Ruleset.resa_length_is_per_end_function`` records that."""
    rs = get_ruleset(ruleset)
    if mandate == "shall":
        return rs.resa_length_min_m
    if mandate == "recommended":
        table = (rs.resa_length_recommended_m_instrument if instrument
                 else rs.resa_length_recommended_m)
        return None if table is None else table.value(code_number)
    raise ValueError(
        f"unknown RESA length mandate {mandate!r} "
        f"(known: 'shall', 'recommended')")


# ── WHAT W2 FLIPPED ───────────────────────────────────────────────────
# W1 was CONSTANTS ONLY (fabric-phase-b-spec.md: "W1 first (constants;
# offline + twins)"): three W1 entries were authority-true numbers whose
# live consumers still read a BLEND, listed here as a hand-off checklist
# under the name ``RULESET_W2_PENDING_FLIPS`` (now retired).
#
# W2 FLIPPED ALL THREE.  ``grade_law.adjacent_ground_envelope`` now reads
# the AUTHORITY-TRUE entry, each behind its own default-ON flag
# (``fabric_flags``), so the flip is bisectable one family at a time and
# reg-set ruling 1's PROVISIONAL status stays literally gate-revertable
# for the owner's sim look.
#
# BOTH FIELDS SURVIVE, and that is deliberate: the LIVE field is what the
# flag-OFF arm reads, so it is the byte-identity proof, not dead weight.
# The twin still pins that the two DISAGREE — a live constant quietly
# edited to match its authority twin would move the flag-OFF arm, which
# is emitted geometry and therefore a STOP, not a landing.
#
# (family, live field, authority-true entry, who, the flag that selects)
RULESET_W2_FLIPS = (
    ("graded-strip mandatory down",
     "strip_band_min_down_slope", "strip_band_min_down_slope_authority",
     "icao", "O4_FABRIC_W2_ICAO_STRIP_AUTHORITY"),
    ("taxiway/apron edge lip",
     "strip_lip_min_down_slope", "taxiway_lip_min_down_slope", "faa",
     "O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY"),
    ("taxiway/apron edge lip",
     "strip_lip_max_down_slope", "taxiway_lip_max_down_slope", "faa",
     "O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY"),
)


# ══════════════════════════════════════════════════════════════════════
# REG-SET PROVENANCE — value · citation · authority class · PV date
# ══════════════════════════════════════════════════════════════════════
# fabric-phase-b-spec.md W1 requires every entry to carry all four.
# Comments carry them for the reader; this table carries them for the
# MACHINE, so "a constant with no citation" is a test failure rather
# than a code-review opinion.  Source of every row:
# docs/specs/fabric-model-reg-set.md (fully primary-verified
# 2026-08-08) — never memory, never a summary.

#: The AC's own normative hierarchy (§1.2.1) plus ICAO's shall/should
#: split plus the two owner-adoption labels this reg set needs.
REG_AUTHORITY_CLASSES = frozenset({
    "Standard",                      # FAA ¶1.2.1 — the benchmark level
    "Recommended Practice",          # FAA ¶1.2.1 — discretionary
    "Design Consideration",          # FAA ¶1.2.1 — weakest
    "shall",                         # ICAO/EASA specification
    "should",                        # ICAO/EASA recommendation
    "guidance",                      # Annex 14 Notes / Attachments, GM
    "absent",                        # the authority states nothing
    # The two owner-adoption labels below are UNUSED as of 2026-08-08:
    # the one entry that carried them, Q5's 105 m precision strip, was
    # dropped by the owner's reversal the same day ("specification
    # values only").  They stay in the vocabulary because the reg set
    # must be able to SAY "this exceeds its citation" the moment
    # another ruling adopts guidance — an unlabelled exceedance is
    # exactly the failure the labels exist to prevent.
    "owner-adopted (guidance)",      # RULINGS adopts guidance as law
    "owner-adopted-beyond-citation",  # RULINGS goes past the source
    "house constant (PROVISIONAL)",  # a repo choice, labelled as one
})


@_dc.dataclass(frozen=True)
class RegEntry:
    """The provenance of one reg-set constant.

    ``field`` is a :class:`Ruleset` field name or a module-level
    constant; ``ruleset`` is ``"faa"``, ``"icao"`` or ``"both"``.
    ``citation`` is the document, section, table and page as the
    verified reg-set table records them — a pointer that resolves to
    another surface silently defeats the provenance contract in
    ``regs/README.md`` (that is finding F-11), so it is spelled out.
    """

    field: str
    ruleset: str
    value: str
    citation: str
    authority_class: str
    pv_date: str = "2026-08-08"
    note: str = ""

    def __post_init__(self):
        if self.authority_class not in REG_AUTHORITY_CLASSES:
            raise ValueError(
                f"unknown authority class {self.authority_class!r} for "
                f"{self.field!r} (known: {sorted(REG_AUTHORITY_CLASSES)})")
        if self.ruleset not in ("faa", "icao", "both"):
            raise ValueError(
                f"unknown ruleset {self.ruleset!r} for {self.field!r}")


REG_SET_ENTRIES = (
    # ── F-9 · the three-axis RSA / ROFA width matrix ──────────────────
    RegEntry(
        field="FAA_RSA_WIDTH_FT_BY_RDC", ruleset="faa",
        value="RSA width by AAC group × ADG × visibility minimum: "
              "A/B-I 120 ft, A/B-II 150 ft, A/B-III 300 ft, A/B-IV and "
              "all C/D/E 500 ft; at minimums lower than 3/4 mile "
              "A/B-I→300, A/B-II→300, A/B-III→400 ft (C/D/E flat)",
        citation="AC 150/5300-13B Chg 1, App. G Tables G-1…G-12 row "
                 "'RSA Width' (dim C), via ¶3.10.1 Dimensions",
        authority_class="Standard",
        note="Closes F-9: the repo carried correct numbers off a "
             "one-column table. A/B-III and A/B-IV were missing "
             "outright and the visibility axis was absent. fn 13 gives "
             "a relief (400 ft where 500 ft 'is not practical', "
             "C/D/E-I and C/D/E-II only) which is NOT taken "
             "automatically."),
    RegEntry(
        field="FAA_ROFA_WIDTH_FT_BY_RDC", ruleset="faa",
        value="ROFA width: 400 ft A/B-I, 500 ft A/B-II, 800 ft "
              "elsewhere, 800 ft in every <3/4-mile column; 250 ft for "
              "the A/B-I small-aircraft table",
        citation="AC 150/5300-13B Chg 1, App. G Tables G-1…G-12 row "
                 "'ROFA Width' (dim Q)",
        authority_class="Standard"),
    RegEntry(
        field="FAA_RSA_HALF_WIDTH_M_BY_LETTER", ruleset="faa",
        value="the code-letter VIEW of the matrix at the ≥3/4-mile "
              "column: 18.3 / 22.9 / 76.2 / 76.2 / 76.2 / 76.2 m",
        citation="AC 150/5300-13B Chg 1, App. G (as above); the letter "
                 "proxy is this repo's own runway_code_letter",
        authority_class="Standard",
        note="Derived, not re-valued — the twin pins every entry "
             "against the literal carried before W1."),
    # ── F-12 / R11 · the per-end RSA length function ──────────────────
    RegEntry(
        field="FAA_RSA_LENGTH_BEYOND_END_FT_BY_RDC", ruleset="faa",
        value="dim R per END: 240 ft A/B-I, 300 ft A/B-II, 600 ft "
              "A/B-III, 1,000 ft A/B-IV and all C/D/E; the <3/4-mile "
              "column raises A/B-I and A/B-II to 600 ft and A/B-III to "
              "800 ft",
        citation="AC 150/5300-13B Chg 1, App. G Tables G-1…G-12 + "
                 "footnotes 9, 10, 11 (p. G-13)",
        authority_class="Standard",
        note="Never a flattened constant (F-12): the length is a "
             "function of RDC × visibility × vertical guidance, and "
             "the datum is fn 9's runway-or-stopway end."),
    RegEntry(
        field="FAA_RSA_LENGTH_PRIOR_TO_THRESHOLD_FT_BY_RDC", ruleset="faa",
        value="dim P per END: 240 / 300 / 600 / 600 ft, 600 ft for "
              "every C/D/E row; applies only where that end has "
              "electronic or visual vertical guidance (fn 11)",
        citation="AC 150/5300-13B Chg 1, App. G + fn 11 (p. G-13)",
        authority_class="Standard",
        note="CIFP supplies the guidance key per end (RULINGS "
             "'Instrument truth is law', 2026-08-06). With no such "
             "guidance the end takes dim R."),
    RegEntry(
        field="resa_length_datum", ruleset="faa",
        value="runway end, or the STOPWAY end where a stopway is present",
        citation="AC 150/5300-13B Chg 1, App. G footnote 9 (p. G-13)",
        authority_class="Standard"),
    RegEntry(
        field="resa_length_datum", ruleset="icao",
        value="the END OF THE RUNWAY STRIP (itself 60 m past the runway "
              "end; 30 m at code 1 non-instrument)",
        citation="ICAO Annex 14 Vol I 8th ed. §3.5.3 with §3.4.2; "
                 "CS ADR-DSN.C.215(a)(1), B.155",
        authority_class="shall"),
    RegEntry(
        field="resa_length_min_m", ruleset="icao",
        value="90 m from the strip end",
        citation="ICAO Annex 14 Vol I 8th ed. §3.5.3; CS "
                 "ADR-DSN.C.215(a)(1)",
        authority_class="shall"),
    RegEntry(
        field="resa_length_recommended_m", ruleset="icao",
        value="240 m (code 3/4); 30 m (code 1/2 non-instrument)",
        citation="ICAO Annex 14 Vol I 8th ed. §3.5.4; CS "
                 "ADR-DSN.C.215(a)",
        authority_class="should"),
    RegEntry(
        field="resa_length_recommended_m_instrument", ruleset="icao",
        value="240 m (code 3/4); 120 m (code 1/2 instrument)",
        citation="ICAO Annex 14 Vol I 8th ed. §3.5.4; CS "
                 "ADR-DSN.C.215(a)",
        authority_class="should"),
    RegEntry(
        field="strip_beyond_end_m", ruleset="icao",
        value="60 m (code 2, 3, 4); 30 m (code 1 non-instrument)",
        citation="ICAO Annex 14 Vol I 8th ed. §3.4.2; CS ADR-DSN.B.155",
        authority_class="shall"),
    RegEntry(
        field="strip_beyond_end_m_instrument", ruleset="icao",
        value="60 m at every code, including code 1 instrument",
        citation="ICAO Annex 14 Vol I 8th ed. §3.4.2; CS ADR-DSN.B.155",
        authority_class="shall"),
    # ── F-10 · the two lip families ───────────────────────────────────
    RegEntry(
        field="strip_lip_min_down_slope", ruleset="faa",
        value="runway / shoulder / stopway edge: 3 %-5 % negative over "
              "10 ft (3 m)",
        citation="AC 150/5300-13B Chg 1, Figure 3-33 Detail A note 2 "
                 "(p. 3-57)",
        authority_class="Standard",
        note="Lip family 1. Verbatim: 'Maintain between a 3% -5% "
             "negative grade for 10 ft (3 m) of unpaved surface "
             "adjacent to the paved surface.'"),
    RegEntry(
        field="strip_lip_min_down_slope", ruleset="icao",
        value="runway / shoulder / stopway edge: the first 3 m shall be "
              "negative and may be as great as 5 %",
        citation="ICAO Annex 14 Vol I 8th ed. §3.4.15 final clause; "
                 "CS ADR-DSN.B.185(a)",
        authority_class="shall"),
    RegEntry(
        field="taxiway_lip_min_down_slope", ruleset="faa",
        value="taxiway / taxilane / apron edge: 5 ±0.5 % ⇒ 4.5 %-5.5 % "
              "over a minimum of 10 ft (3 m)",
        citation="AC 150/5300-13B Chg 1, ¶4.14.2 Standards item 4 "
                 "(p. 4-46)",
        authority_class="Standard",
        note="Lip family 2, and NOT the runway band: steeper at the "
             "floor (4.5 vs 3.0) and above the runway ceiling (5.5 vs "
             "5.0). Written for 'an unpaved surface adjacent to a "
             "paved surface', so it reaches apron edges too."),
    RegEntry(
        field="taxiway_lip_min_down_slope", ruleset="icao",
        value="none — the taxiway-strip clause states flush, an up cap "
              "and a down cap, and no lip",
        citation="ICAO Annex 14 Vol I 8th ed. §3.11.5; CS "
                 "ADR-DSN.D.330(b) — absence verified by full read",
        authority_class="absent",
        note="F-3: the ICAO taxiway lip the repo applies today is "
             "UNSOURCED."),
    RegEntry(
        field="taxiway_lip_carved_out_of_band", ruleset="faa",
        value="the lip is carved OUT of the 1.5-5 % TSA band",
        citation="AC 150/5300-13B Chg 1, ¶4.14.2 Standards item 5 "
                 "(p. 4-46) — 'except as noted in subparagraph 4 above'",
        authority_class="Standard"),
    # ── F-11 · taxiway shoulder width by TDG ──────────────────────────
    RegEntry(
        field="taxiway_shoulder_width_m_by_tdg", ruleset="faa",
        value="per side: 10 ft (3.0 m) TDG 1A/1B, 15 ft (4.6 m) 2A/2B, "
              "20 ft (6.1 m) 3/4, 30 ft (9.1 m) 5/6",
        citation="AC 150/5300-13B Chg 1, Table 4-2 row 'Taxiway "
                 "Shoulder Width' (p. 4-10), via ¶4.13.1 Standards "
                 "item 1",
        authority_class="Standard",
        note="DISCREPANT KEY (F-11): the repo carried this 'by ADG'. "
             "Width is TDG-keyed; PROVISION stays ADG-keyed."),
    RegEntry(
        field="taxiway_shoulder_width_m_tdg6_four_engine", ruleset="faa",
        value="40 ft (12.2 m) where the most demanding aircraft has "
              "four engines and is TDG 6",
        citation="AC 150/5300-13B Chg 1, Table 4-2 footnote 3 (p. 4-10)",
        authority_class="Standard"),
    RegEntry(
        field="taxiway_shoulder_paved_from_adg", ruleset="faa",
        value="paved taxiway shoulders for ADG-IV and larger",
        citation="AC 150/5300-13B Chg 1, ¶4.13.1 Standards item 2",
        authority_class="Standard"),
    RegEntry(
        field="taxiway_plus_shoulders_total_width_m", ruleset="icao",
        value="overall taxiway + shoulders ≥25 m (C), 34 m (D), 38 m "
              "(E), 44 m (F); no per-side width, no slope number",
        citation="ICAO Annex 14 Vol I 8th ed. §3.10.1; CS "
                 "ADR-DSN.D.305(a)",
        authority_class="should"),
    # ── R24 · TOFA back slope ─────────────────────────────────────────
    RegEntry(
        field="tofa_back_slope_ratio", ruleset="faa",
        value="≤4:1 (25 % rise) where a TOFA back slope is necessary",
        citation="AC 150/5300-13B Chg 1, ¶4.14.2 Standards item 6b "
                 "(p. 4-46) + Figure 4-29 (p. 4-45)",
        authority_class="Standard",
        note="R24, new at the 2026-08-08 primary read. A ceiling "
             "(cut), never a mandate to shape. Its absence left the "
             "FAA taxiway branch with no far-zone ceiling at all. The "
             "TOFA SIDE slope, item 6a, stays QUALITATIVE — 'design "
             "transverse gradient to promote positive drainage away "
             "from the TSA', no number, unlike the runway ROFA's S-4 — "
             "so no field encodes it."),
    RegEntry(
        field="tofa_back_slope_ratio", ruleset="icao",
        value="none — ICAO has no object-free-area family; §3.11.6 caps "
              "ground beyond the graded portion at 5 % up or down",
        citation="ICAO Annex 14 Vol I 8th ed. §3.11.6; CS "
                 "ADR-DSN.D.330(c)",
        authority_class="absent"),
    # ── R20 / ruling 2 · the 1.0 % taxiway cross-fall ─────────────────
    RegEntry(
        field="taxi_transverse_min", ruleset="faa",
        value="1.0 % minimum cross-fall, centreline to pavement edge "
              "(the band is 1.0-1.5 %)",
        citation="AC 150/5300-13B Chg 1, ¶4.14.2 Standards item 1a "
                 "(p. 4-46); Table 3-6 row S-1 for the runway twin",
        authority_class="Standard",
        note="BIND THE MINIMUM, NOT THE CROWN FORM: the cross-fall is "
             "a Standard, the centre crown only a Recommended Practice "
             "on the same page, and item 1c admits a constant-slope "
             "shed section."),
    RegEntry(
        field="taxi_crown_form_binding", ruleset="faa",
        value="the centre crown is NOT binding",
        citation="AC 150/5300-13B Chg 1, ¶4.14.2 Recommended Practices "
                 "item 2 (p. 4-46) — 'The ideal configuration is a "
                 "center crown…'",
        authority_class="Recommended Practice"),
    RegEntry(
        field="taxi_transverse_min", ruleset="icao",
        value="1.0 %, adopted as a named house constant; ICAO itself "
              "states NO minimum and no crown, only 'sufficient to "
              "prevent the accumulation of water' and a 1.5 % (C-F) / "
              "2 % (A/B) ceiling",
        citation="RULINGS 2026-08-08 reg-set ruling 2, standing in for "
                 "ICAO Annex 14 Vol I 8th ed. §3.9.11 / CS "
                 "ADR-DSN.D.280(b)",
        authority_class="house constant (PROVISIONAL)",
        note="F-6: the owner took reading (b) of Q2. House, not "
             "cited — a future ICAO amendment stating a real floor "
             "REPLACES this rather than re-blessing it. 1.0 % sits "
             "inside the ICAO ceiling with 0.5 pp of headroom."),
    # ── Q5 · the 105 m precision strip is DROPPED, not encoded ────────
    # RULINGS 2026-08-08 "105 m precision strip DROPPED (owner;
    # supersedes the same-day adoption)" — specification values only.
    # There is deliberately NO RegEntry: a provenance row would make the
    # value look encodable.  The Annex 14 §3.4.8 Note stays recorded as
    # UNADOPTED guidance in docs/specs/fabric-model-reg-set.md §2.1.
    # ── ruling 1 · the graded-strip mandatory DOWN ────────────────────
    RegEntry(
        field="strip_band_min_down_slope_authority", ruleset="faa",
        value="1.5 % minimum fall across the graded strip (band 1.5-5 % "
              "AAC-A/B, 1.5-3 % AAC-C/D/E)",
        citation="AC 150/5300-13B Chg 1, Table 3-6 row S-3 (p. 3-60) + "
                 "¶3.16.5 item 6",
        authority_class="Standard",
        note="KCLT keeps the FAA form (ruling 1)."),
    RegEntry(
        field="strip_band_min_down_slope_authority", ruleset="icao",
        value="none — a 2.5 % (code 3/4) / 3 % (code 1/2) CEILING and "
              "the 3 m negative lip, with no minimum stated anywhere",
        citation="ICAO Annex 14 Vol I 8th ed. §3.4.15; CS "
                 "ADR-DSN.B.185(a); dropped by RULINGS 2026-08-08 "
                 "reg-set ruling 1 (PROVISIONAL)",
        authority_class="absent",
        note="F-2. PROVISIONAL: the owner revisits at the sim look at "
             "a strip without the band. Strip bands stop being emitted "
             "at SPJC/SPLP/CYXY/HECA once W2 flips the consumer."),
    # ── F-1 · the ICAO instrument graded-strip key ────────────────────
    RegEntry(
        field="strip_half_width_m_instrument", ruleset="icao",
        value="graded half-width 40 m (code 1 and 2), 75 m (code 3 and "
              "4) on an INSTRUMENT runway",
        citation="ICAO Annex 14 Vol I 8th ed. §3.4.8; CS "
                 "ADR-DSN.B.175(a)",
        authority_class="should",
        note="F-1: the live table is the NON-instrument one (§3.4.9), "
             "which gives 30 m at code 1. Affects code-1 instrument "
             "runways only — none in the five-airport battery."),
    RegEntry(
        field="strip_half_width_m_instrument", ruleset="faa",
        value="none — the AC has no instrument/non-instrument split; "
              "Appendix G keys AAC × ADG × visibility minimum instead",
        citation="AC 150/5300-13B Chg 1, App. G Tables G-1…G-12",
        authority_class="absent"),
)

#: ``(ruleset, field)`` → :class:`RegEntry`.  The lookup a twin uses to
#: prove every W1 field has provenance.
REG_SET_ENTRY_INDEX = {(e.ruleset, e.field): e for e in REG_SET_ENTRIES}


def reg_entry(field: str, ruleset: str = "both"):
    """The :class:`RegEntry` for ``field`` under ``ruleset``, falling
    back to a ``"both"`` entry.  ``None`` when the constant carries no
    provenance record — which, for a W1 field, is a test failure."""
    return (REG_SET_ENTRY_INDEX.get((ruleset, field))
            or REG_SET_ENTRY_INDEX.get(("both", field)))


# ── GROUNDSIDE DRAINAGE MINIMUM (§B3, region-invariant) ───────────────
# The lot/service-road precedent (docs/RULINGS.md 2026-08-03): no
# aviation authority regulates a landside grade, so there is no FAA/ICAO
# split to apply and the constant stays out of the registry.  Every
# civil source carries a minimum in the 0.6-2 % range (the constants
# round's research trail cites Iowa SUDAS §8B-1 among others); 1.0 % is
# the PROVISIONAL mid-range value.  OWNER QUESTION 3 — the owner
# approves the number exactly as he approved lot 5 % / service 8 %.
#
# OWNER QUESTION 3 IS ANSWERED, AND THE ANSWER IS NO LAW (RULINGS
# 2026-08-13b, amended by the 2026-08-14 scope clarification: what
# retires is "ADDING drainage curvature (crown / minimum-slope
# requirements) to TAXIWAY and ROAD pavement surfaces; those may be flat
# for the sim").  This constant IS that landside requirement, so nothing
# reads it any more — ``grade_law._DRAINAGE_MIN_GROUNDSIDE_ROLES`` is the
# empty set.  The APRON minimum (the rulesets' own
# ``apron_min_drainage_grade``, FAA §5.9.1.1) did NOT retire and binds as
# before.
#
# KEPT, not deleted: the owner withdrew the LAW, not the constants
# round's research trail, and a later version that re-opens landside
# drainage should find the number and its citations here rather than
# re-derive them.  Reading it again re-instates a retired law and needs
# its own ruling.
GROUNDSIDE_MIN_DRAINAGE_GRADE = 0.010
GROUNDSIDE_MIN_DRAINAGE_GRADE_PROVISIONAL = True

# ── RECORDED, NOT BOUND — the crown minimum (owner question 5) ────────
# FAA Table 3-6 S-1 puts a 1.0 % MINIMUM on the runway transverse grade
# (1.0-2.0 % AAC A/B, 1.0-1.5 % AAC C/D/E) and §4.14.2 item 1a puts the
# same 1.0 % minimum on taxiways; ICAO §3.1.19 says the runway transverse
# "should not exceed 1.5 per cent or 2 per cent, as applicable, nor be
# less than 1 per cent except at runway or taxiway intersections".
# BINDING IT MODELS A REAL CROWN ON EVERY RUNWAY AND TAXIWAY — a visible
# cross-section change at every airport (~22 cm of rise on a 45 m runway
# at 1 %).  That is an owner-intent question, not an implementation
# choice, so the values are CARRIED on the rulesets
# (``runway_transverse_min`` / ``taxi_transverse_min``) and READ by the
# validator as an informational class, but no generation-binding
# constraint asserts them.  Flip = give the transverse solver rows a
# lower bound as well as an upper one (§B2 machinery, one line).
# BOUND ON RUNWAYS (owner ruling d48bc0a, 2026-08-05): "this version
# implements ONLY (1) runway crowns and (2) pavement-edge (unpaved areas)
# drainage… RUNWAY CROWNS: generated and bound (this answers open question
# Q5 for runways — the crown minimum BINDS on runways; taxiway/apron
# crowns stay recorded-unbound with citations)."  So the answer is
# PER-FAMILY, not one global flag: generation may not emit a runway crown
# flatter than the ruleset minimum, while the taxiway minimum stays an
# informational class with its citation intact.
CROWN_MINIMUM_BOUND_RUNWAYS = True
CROWN_MINIMUM_BOUND_TAXIWAYS = False

# ── RECORDED, NOT BOUND — the honest inventory tail (spec §"Recorded") ─
# Each has its citation so the gap census stays complete; none is
# silently dropped.
#   * ICAO effective slope ≤1 %/2 % (§3.1.13).
#   * Runway sight distance (ICAO §3.1.17) and taxiway sight distance
#     (§3.9.10).
#   * PVI spacing: ICAO §3.1.18 max(K·Σ|Δg|, 45 m) with K =
#     30 000/15 000/5 000 by code number; FAA §3.16.1 250 ft × Σ|Δg%|
#     (AAC A/B) and 1 000 ft × Σ|Δg%| (AAC C/D/E).
#   * Taxiway vertical curves: ICAO §3.9.9 1 %/30 m (C-F), 1 %/25 m
#     (A/B); FAA §4.14.1.1.3 100 ft (30.5 m) per 1 %, max change 3.0 %,
#     none below 0.40 %.
#   * Stopway arc relaxation: ICAO §3.7.2(b) 0.3 % per 30 m.
#   * Runway/runway intersections: FAA §3.16.4 — 3 in (76 mm) maximum
#     crown-to-edge difference on the higher-category runway, 150 ft
#     (46 m) minimum transition, 0.5 % minimum transverse for positive
#     drainage.
#   * TOFA back slope max 4:1 (FAA §4.14.2 item 6).
#   * Apron taxilane recommended maxima 1.5 % / 2.0 % by weight
#     (FAA §5.9.2.1.2-.3) — the repo binds the stricter 1 % apron cap
#     (owner constant), which contains them.
#   * NFPA 415 fuelling-pavement slope (FAA §5.9.1.2 cross-reference).


# ── PROJECTION SELF-LIMITS, RE-DERIVED (debug lane A 2026-08-05) ────────
# Owner directive relayed 2026-08-05: "every loop cap, retry bound and
# self-limit constant in route_profile/* gets re-derived from what the law
# demands, not what prototype fear chose — change it or document why the
# law itself sets it."
#
# WHAT THE LAW DEMANDS.  The projection is a POCS / Gauss-Seidel sweep over
# the law-edge graph.  The law demands a CERTIFIED surface — every edge
# inside its slab to ``tol`` — and says nothing whatever about a number of
# sweeps.  A sweep cap is therefore NOT a law quantity: it is a
# NON-TERMINATION GUARD, and the only honest derivation of its magnitude is
# the propagation distance a correction must travel, which for a
# nearest-neighbour sweep is ONE law edge per sweep.  The bound the law
# implies is thus the longest law-edge path in the graph (its diameter);
# the node count ``n`` is that path's trivial upper bound.
#
# WHERE WE WERE — measured, not asserted (debug lane A, integrate/
# evidence, composed SPJC and HECA):
#     [stall-report] edges=127520 n=72472: UNCERTIFIED EXIT at sweep
#     2400/2400 ... active violating edges 1349; worst residual 0.146
# The hand-set guard was BINDING — the loop spent its whole budget and
# still exited with 1,349 edges over cap, so on those airports the SURFACE
# WAS DECIDED BY THE GUARD rather than by convergence.  A non-termination
# guard that chooses a surface is a defect, not a tuning question, and no
# hand-set number can be proved above a graph it has never seen.
#
# BE PRECISE ABOUT THE "~30x" IN THE LANE-A WRITE-UP: it compared 2,400 to
# ``n`` = 72,472 — the TRIVIAL bound on a path length, not that graph's
# diameter.  The BFS bound below is far tighter, and it is entirely
# possible that on this graph it lands NEAR 2,400.  That would not make
# the change cosmetic — it would mean the 2400/2400 exit was never budget
# exhaustion at all but an EMPTY POLYTOPE wearing a cap's clothing, which
# is precisely the confusion a derived budget removes and the new exit
# report names.
#
# WHAT LANDED (2026-08-05).  The four per-role constants are DELETED.  The
# budget is DERIVED PER PROJECTION, FROM THE PROJECTION'S OWN GRAPH:
#
#     budget = clamp(SWEEP_BUDGET_SLACK × hop_eccentricity_bound(edges, n),
#                    SWEEP_BUDGET_MIN, SWEEP_BUDGET_MAX)
#
# ``hop_eccentricity_bound`` is one BFS per connected component from an
# arbitrary member (``one_solve._hop_eccentricity_bound``, O(V+E), run once
# per projection, never inside the sweep loop): a BFS from any node gives
# that component's eccentricity ``e``, and the hop-diameter is at most
# ``2e``, so ``2·max_c e_c`` bounds the propagation distance of the WHOLE
# graph including a disconnected one.
#
# CONSEQUENCE, and the point of the change: an UNCERTIFIED EXIT no longer
# means "we ran out of the number someone typed" — the budget is derived
# rather than typed.
#
# ⚠ THE INFERENCE THAT USED TO STAND HERE IS FALSE, AND THIS FILE ALREADY
# RECORDS ITS FALSIFICATION ~70 LINES BELOW.  The old text read: "With the
# budget provably above the graph's propagation distance, it means the
# polytope is EMPTY."  The sweeps ladder measured otherwise — ~33 % of
# HECA's and ~57 % of HEAZ's fp#8 residual closes with sweeps ALONE — and
# the derivation's SHAPE is why: a hop-diameter bound prices BALLISTIC
# propagation while cyclic Gauss-Seidel POCS propagates DIFFUSIVELY
# (distance ~ √sweeps), so the bound is quadratic in the diameter, not
# linear.  Being above a ballistic bound therefore says nothing about the
# polytope.  Keeping the claim here while the measurement sat below it is
# the shape of defect the cycle-7.5 instrument sweep exists to remove
# (RULINGS 2026-08-06, "Instrument truth is law", binding point 2).
#
# WHAT AN UNCERTIFIED EXIT ACTUALLY MEANS: the sweep loop stopped without
# a KKT certificate, by one of four MEASURED criteria (materiality,
# convergence-patience, caller's bound, hard cap).
# ``one_solve._uncertified_exit_report`` now prints that criterion, the
# constants that define it, the n_material trajectory and the derived
# budget with the eccentricity bound it came from — numbers the debug
# phase can attribute without re-deriving anything, and WITHOUT a claim
# about the feasible set.  The one licensed infeasibility statement in
# that module is the ``L > U`` envelope gap on raw-law budgets, which is a
# proof and is frame-stamped as one.
#
# COST is deliberately NOT priced here.  The sweep loop exits on its KKT
# certificate, so a converging graph pays for convergence and not for the
# budget; only a genuinely non-converging projection spends the extra
# sweeps, and that projection is a defect report.  The wall-time arm
# belongs to the test phase (docs/RULINGS.md 2026-08-05,
# build-complete-then-debug).

# SLACK — why the diameter bound alone is not the budget.  In a CYCLIC
# projection one sweep does not propagate one correction cleanly across one
# hop: a node is pulled by every incident edge at once, so a correction
# needs SEVERAL passes per diameter to settle rather than exactly one.
# 4 is the honest small integer for that: enough that the budget is above
# what the graph can need, small enough that a pathological graph is caught
# by SWEEP_BUDGET_MAX rather than by a runaway multiplier.
# THIS IS A GUARD, NOT LAW.  It may never decide a surface; if it ever
# does, the uncertified-exit report fires and the number is not the fix.
SWEEP_BUDGET_SLACK = 4
# FLOOR — a tiny or empty graph still gets a sane budget (and a graph whose
# BFS bound is 0 because it has no edges must not get a 0-sweep budget).
SWEEP_BUDGET_MIN = 200
# ABSOLUTE CEILING — the actual non-termination guard.  No graph, however
# pathological, may hang a build forever.  Sized 3.4x the composed
# SPJC+HECA NODE COUNT (72,472), which is the trivial upper bound on any
# path length in that graph: a graph would have to be one single 72k-node
# chain — which airport pavement is not, its hop diameter is orders below
# n — before this could bind.  So on real geometry it never does, and when
# it does the uncertified-exit report SAYS it was the ceiling, which is the
# signal that the graph, not the law, is the thing to look at.
SWEEP_BUDGET_MAX = 250000
# NO FALLBACK CONSTANT EXISTS, deliberately.  The brief for this change
# reserved one for "a call site with no edge list in hand"; auditing the
# call sites, there is none — every projection owns its graph at the moment
# it must name a budget, because the budget is named INSIDE
# ``feasibility_project`` / ``one_profile_solve`` after the edge list is
# built, not at the call.  A caller may still pass an explicit ``max_iters``
# (tests, deliberately bounded probes) and the uncertified-exit report then
# says the budget was IMPOSED rather than derived.  Adding an unused
# fallback here would just be a magic number waiting to be picked up.

# ── MATERIALITY (campaign convergence guard (a), owner 2026-08-02) ─────
# The elevation materiality floor: a residual below it is PASS-with-
# residual, never a defect and never a thing to iterate on.  ONE
# authority for the projection side of that floor — the exit report
# counts over-cap edges BOTH ways (raw, and ≥ this), and the convergence
# criterion below is priced on the ≥-material count so that sub-
# millimetre churn can never keep a projection sweeping.
PROJECTION_MATERIALITY_M = 0.01

# ── THE CONVERGENCE-CRITERION EXIT (cycle-7 fix 1, 2026-08-06) ─────────
# MEASURED FALSIFICATION of the derivation above.  The c6attr attribution
# dossier drove the identical ``_project_chromatic`` on the identical fp#8
# inputs at 1x / 10x / 100x / 400x the derived budget.  On a subsystem
# that is FEASIBLE BY CONSTRUCTION (pure symmetric difference
# constraints, every node free, no boxes — ``z ≡ const`` satisfies it, so
# any residual is convergence by construction):
#
#     HEAZ  320 = derived  ->  1,245 edges over cap
#     HEAZ  32,000 (100x)  ->      0  — CERTIFIED
#     HECA  496 = derived  -> 11,513 edges over cap
#     HECA  198,400 (400x) ->    401, ZERO ≥ 0.01 m — materially certified
#
# So ``SWEEP_BUDGET_SLACK × hop-diameter`` is ~2 ORDERS OF MAGNITUDE
# below what this relaxation needs, and the uncertified-exit report's
# sentence "this exit is NOT budget exhaustion" was FALSE in every build:
# ~33 % of HECA's and ~57 % of HEAZ's fp#8 residual closes with sweeps
# alone.  The error is in the SHAPE of the derivation, not its slack: a
# hop-diameter bound prices BALLISTIC propagation (one correction, one
# edge, one sweep) while a cyclic Gauss-Seidel POCS propagates
# DIFFUSIVELY — the distance a correction travels grows like √sweeps, so
# the honest bound is quadratic in the diameter, not linear.  No constant
# multiplier fixes a wrong exponent.
#
# WHAT REPLACES IT.  The law demands a CERTIFIED surface and says nothing
# about sweeps, so the loop now exits on the only two honest events:
#   * CERTIFIED — a full sweep applying no correction and no clamp; or
#   * CONVERGED — the ≥-materiality over-cap count has stopped falling.
# The derived budget survives as the BLOCK size: the loop sweeps a block,
# measures the exact whole-graph residual, and compares.  A block that
# fails to buy ``SWEEP_CONVERGENCE_MIN_DROP`` relative improvement counts
# against ``SWEEP_CONVERGENCE_PATIENCE``; when patience runs out the
# projection has converged to a point that violates N constraints, which
# is a LAW/ANCHOR defect report under RULINGS 2026-08-05, not a budget
# story.  ``SWEEP_BUDGET_MAX`` remains the absolute anti-hang ceiling and
# is now the ONLY hard cap; an exit there says so.
#
# THE THREE CONSTANTS ARE GUARDS, NOT LAW.  MIN_DROP is a relative floor
# on "still improving" — 0.5 % of the standing count per block, the same
# magnitude the stall detector already uses (``STALL_REL_IMPROVEMENT``),
# chosen so that the measured HECA tail (net drift +27 over 10,000 sweeps
# on a standing set of ~19,000 — 0.14 % per 496-sweep block) reads as
# converged and the measured HEAZ approach to zero does not.  PATIENCE
# absorbs the POCS churn (~24 edges per 100 sweeps turn over at 100x, so
# a single flat block is noise and two in a row is a trend).
SWEEP_CONVERGENCE_MIN_DROP = 0.005
SWEEP_CONVERGENCE_PATIENCE = 2

# The FAIRING family is UNCHANGED and is a different problem: a
# second-difference smoother run PER CHAIN, so its propagation distance is
# one chain's station count (tens), not the graph's.  These caps are
# law-adequate at their current values and are named here for one home.
FAIRING_MAX_SWEEPS_SPINE = 400              # per-chain second-difference fairing
FAIRING_MAX_SWEEPS_GAP_SPINE = 200          # per gap-fill chain
FAIRING_MAX_SWEEPS_CHAIN = 200              # per generic chain
FAIRING_MAX_SWEEPS_APRON = 5000             # apron smoother, per apron body


# ══════════════════════════════════════════════════════════════════════
# FLAT-SITE DETECTOR (report-only)
# ══════════════════════════════════════════════════════════════════════
# docs/specs/flat-site-detector-spec.md (2026-08-09, FROZEN), phase 1 of
# the owner's charter "we want to see if we can implement a
# simplification for airports like OTHH that are pretty much at sea
# level, and are genuinely flat".  The detector (auto_patch/flat_site.py)
# MEASURES and RECORDS; no solver, emitter or law reads these values.
#
# THE MEASURED FOUNDATION (spec section 1, 2026-08-09 — cited, never
# re-derived).  OTHH, the type specimen: all four CIFP thresholds 13 ft =
# 3.96 m, spread 0; apt.dat 13 ft; the pack's 9,226 non-drainage object
# seat requests median 4.00 m (|delta| vs CIFP 0.04 m, p95-p5 2.17 m);
# and the raw DEM (Viewfinder 3-arcsec, 93 m posts, integer metres) over
# the airport extent reads median 0 m — 4 m BELOW instrument truth, 69 %
# exactly 0 (coastal/reclaimed void-fill) — with p95-p5 6.0 m, plane-fit
# slope 0.067 % and residual std 1.82 m.  Every metre of "relief" the
# solver chases there is DEM noise.  The negative type specimen is HECA:
# ~85 m of REAL relief, DEM and CIFP agreeing, which must never classify
# flat.

# S1.  CIFP threshold CONSENSUS: max - min over the airport's threshold
# elevations, compared STRICTLY (spread < this).  OTHH reads 0.00 m
# (four identical 13 ft thresholds).
#
# 5.0 m IS AN OWNER RULING (2026-08-09, docs/RULINGS.md "Flat-site S1
# spread and the flat test set"), verbatim: "CIFP threshold spread < 5m
# should be a flat candidate".  The 0.5 m this replaces was the lead's
# PROVISIONAL value, chosen to absorb only the ARINC-424 one-foot
# quantum; it excluded real sea-level airports whose ends differ by a
# metre or two of survey, which is the population the owner is after.
# Phase-2 note (spec section 2): at nonzero spread the RUNWAYS keep
# their CIFP-absolute profiles under the standing ruling — the flat
# elevation applies off-runway, and the phase-2 spec owns that seam.
FLAT_SITE_THRESHOLD_SPREAD_M = 5.0

# S2a.  THE SEA-BAND EXCLUSION (spec section 2 S2a, v2 amendment
# 2026-08-09, from the six-airport sweep).  At a site whose instrument
# truth sits meaningfully above sea level, a DEM sample at or below 0 m
# is SEA SURFACE or VOID FILL, not terrain testimony: it is excluded
# from S2's relief percentiles AND from the plane fit, and the excluded
# fraction rides in the record as ``s2_sea_excluded_frac``.
#
# ONE CONTAMINANT CLASS EXPLAINS EVERY REFUSAL the owner's six-airport
# sweep produced (measured 2026-08-09, base rasters): VHHH judged at DEM
# median 0.33 m against instrument truth 7.32; YSSY carrying p5 -2.67 m
# INSIDE the reclaimed airport; KSFO's "slope" being the land-to-bay-zero
# gradient rather than any tilt of the airfield; and OTHH itself passing
# only by DILUTION — 69 % of its samples are literal zeros.  Excluding
# the band measures the LAND the airport is built on.
#
# THE Z0 GUARD IS THE WHOLE SAFETY OF IT.  Below this consensus
# elevation the site's zeros ARE plausible terrain — Schiphol sits at
# -3 m and every one of its samples is real ground — so a below-sea or
# at-sea site keeps EVERY sample and this exclusion never runs.  1.0 m
# is the owner's own 1 m law scale (DSF_OBJECT_BAKE_MIN_DELTA_M): below
# a metre of separation from the sea surface, "is this water or ground?"
# is not answerable from elevation alone and the detector does not guess.
FLAT_SITE_SEA_BAND_MIN_Z0_M = 1.0

# The sea surface itself, in the DEM's own vertical datum.  This is a
# DATUM, not a tuning knob: raising it would start discarding real
# low-lying land, and the whole justification for the exclusion is that
# a sample at or under the sea surface carries no terrain information.
# Named here so there is one home for it and so any future change is a
# visible edit to a rule value rather than a literal at a call site.
FLAT_SITE_SEA_BAND_MAX_M = 0.0

# S2b.  THE DSM-STRUCTURE TRIM (spec section 2 (b), v3 amendment, owner
# 2026-08-09).  The 3-arcsec sources are SURFACE models: a 93 m cell over
# a terminal reports the ROOF, and a roof is not the ground the airport
# is graded to.  After the sea band is gone, samples above
#
#     median + FLAT_SITE_DSM_TRIM_FRACTION_OF_FLOOR * relief_floor
#
# are DSM-structure suspects and take no part in the relief percentiles
# OR the plane fit; the trimmed share rides in ``s2_dsm_trimmed_frac``.
#
# CLASS-RELATIVE BY CONSTRUCTION, which is why it is a fraction of the
# floor and not a metre value: the cut is +4 m on a 3-arcsec source
# (floor 8 m), +1 m on a sub-10 m raster (floor 2 m).  A source trusted
# to a metre gets a trim measured in metres.
#
# THE MEASURED BASIS (2026-08-09, base rasters, sea band already
# removed): VHHH, YSSY and KSFO carry medians ON instrument truth
# (S3 0.65 / 0.04 / 0.05 m) with p95 reaching 17.0 / 10.3 / 8.0 m
# against truth of 7.3 / 4.4 / 3.0 — an UPWARD skew, (p95-median) /
# (median-p5), of 1.96 / 1.69 / 2.25 where passing OTHH reads 1.2.  The
# central tendency is right and the tail is buildings; a symmetric
# statistic cannot tell those apart, so the tail is cut and counted.
FLAT_SITE_DSM_TRIM_FRACTION_OF_FLOOR = 0.5

# S2.  The MARGIN RING around (pavement u boundary).  REPORT-ONLY since
# the v3 amendment (spec section 2 (a), owner 2026-08-09): the gate
# statistics are taken over PAVEMENT u BOUNDARY alone, and the ring is
# kept as audit context in the record's ``s2_ring_*`` fields.
#
# WHY IT LOST ITS VETO.  The flat-site mode flattens the AIRPORT and
# feathers outward, so surrounding terrain has no standing to refuse it:
# VMMC's flat 1.73 km2 strip was being refused by Taipa's hills sitting
# in a 3.03 km2 ring — measured 2026-08-09 at ring relief 38.11 m and
# slope 0.70 % against pavement figures of 7.31 m and 0.165 % that would
# have passed.  The case the ring guarded — an airport whose own
# surfaces hide relief — is carried by the pavement statistics, S1 and
# S4.  200 m remains the scale at which the adjacent-ground zones stop
# grading and raw DEM resumes, so the reported ring is still the band
# the mode's feather has to cross.
FLAT_SITE_MARGIN_M = 200.0

# S2.  Plane-fit slope cap over that extent.  OTHH reads 0.067 %; the cap
# sits at roughly twice it and an order of magnitude under the 1.5 %
# taxiway grade cap, so a site the solver would have to WORK to flatten
# can never read flat here.
FLAT_SITE_MAX_SLOPE_PCT = 0.15

# S2.  The p95-p5 relief a DEM SOURCE CLASS can produce out of pure
# noise.  Relief at or under its own source's floor is not evidence of
# terrain.  3-arcsec sources (~93 m posts, integer metres, void-filled
# coastlines) carry metres of it — OTHH measures 6.0 m over genuinely
# flat reclaimed land; a sub-10 m raster is close to credible and gets a
# floor barely above its own quantisation.
#
# THE 1-ARCSEC FLOOR IS 8.0 m, NOT 5.0 (LEAD RULING 2026-08-09, closing a
# spec gap the detector's own sweep surfaced).  Copernicus GLO-30 class
# products carry ~4 m 90 % linear vertical error and are SURFACE models
# that bake built structures into coastal/urban ground, so a p95-p5 of
# 5-8 m over a 21 km² extent is inside the source's own noise envelope,
# not evidence of terrain.  The discriminative burden for every negative
# case is carried elsewhere and measurably so: at the 5.0 m floor OTHH
# read 5.014 m on the Copernicus inset production actually bakes — a
# 14 mm miss that flipped the type specimen between its base-tile and
# its production surface.  Measured 2026-08-09: raising this floor flips
# NO row of the section-3 sweep (all nine not_flat rows fail S1 threshold
# spread outright, most also the slope gate), and the PLATEAU case is
# caught by the margin ring's relief regardless of the floor's value.
FLAT_SITE_RELIEF_FLOOR_BY_CLASS = {
    "ge3arcsec": 8.0,
    "1arcsec": 8.0,
    "sub10m": 2.0,
}

# S2.  Native-resolution boundaries mapping a DECLARED source resolution
# to a class, ascending, first match wins; anything coarser than the last
# bound is FLAT_SITE_COARSE_SOURCE_CLASS.  1 arc-second is ~30.9 m and
# 3 arc-second ~92.6 m, so the 60 m split cannot confuse the two, and
# COPERNICUSGLO30 (30 m, the provider cached for the Qatar tile) lands in
# the 1-arcsec class.  A source at or under 2 m is METRE-CREDIBLE
# (LIDAR-class): the detector short-circuits to ``lidar_credible`` there,
# because that DEM is trustworthy and the normal path already handles a
# flat site correctly under a truthful DEM.
FLAT_SITE_SOURCE_CLASS_BOUNDS_M = (
    (2.0, "lidar"),
    (10.0, "sub10m"),
    (60.0, "1arcsec"),
)
FLAT_SITE_COARSE_SOURCE_CLASS = "ge3arcsec"

# S2.  What the BASE TIER's resolution is, per the tile's own elevation
# level (O4_Elevation_Level.base_prefers_coarse: "auto"/"90"/coastline
# take the 3 arc-second base class, numeric levels the 1 arc-second one).
# These are the nominal postings of those two tiers, used only to name
# the class — never to resample anything.  The DEM raster's own posting
# is deliberately NOT consulted: O4_DEM_Utils UPSAMPLES a 1201x1201
# 3-arcsec .hgt to 3601x3601 with no record of the native size, so the
# array would report a 1-arcsec grid over 3-arcsec data and put OTHH
# under the wrong floor.
FLAT_SITE_BASE_COARSE_RESOLUTION_M = 92.6    # 3 arc-second
FLAT_SITE_BASE_FINE_RESOLUTION_M = 30.9      # 1 arc-second

# S4.  Pack-object consensus, CONFIRMATORY only and never a fail: the
# median non-below-grade seat target must sit within
# FLAT_SITE_PACK_OFFSET_MAX_M of the CIFP consensus Z0, with a p95-p5
# spread at or under FLAT_SITE_PACK_SPREAD_MAX_M.  OTHH measures 0.04 m
# and 2.17 m against these.
FLAT_SITE_PACK_OFFSET_MAX_M = 1.0
FLAT_SITE_PACK_SPREAD_MAX_M = 3.0

# S4.  A pad request whose object base sits this far or more BELOW its
# own anchor datum is a BELOW-GRADE request — an open-pit drainage basin
# asking for a trench floor, not a ground-level seat (OTHH's Aeroscape
# "Dewatering Drainage" pits reach ~3.8 m below grade).  The value is the
# owner's 1 m law (DSF_OBJECT_BAKE_MIN_DELTA_M, ruling 2026-08-09): below
# a metre the pack is not modified and terrain adapts, so a sub-metre
# base offset is a ground-level seat by that same measure.
FLAT_SITE_PACK_BELOW_GRADE_M = 1.0


# ══════════════════════════════════════════════════════════════════════
# FLAT-SITE MODE (phase 2) — the DEM SOURCE SUBSTITUTION
# ══════════════════════════════════════════════════════════════════════
# docs/specs/flat-site-mode-spec.md (2026-08-09, FROZEN).  When the
# detector above returns ``flat_candidate`` for an airport, DEM prep
# manufactures a SYNTHETIC CONSTANT INSET at the threshold-consensus Z0
# over the detector's own extent and feeds it through the EXISTING
# airport-inset feathering machinery — the same path a Copernicus/LIDAR
# inset takes today.  It is a DEM SOURCE SUBSTITUTION, not a new solve
# path: everything downstream is unchanged and runs against a truthful
# flat input.  ``not_flat`` / ``lidar_credible`` / ``no_data`` airports
# take the normal path byte-identically (spec §3.1).
#
# DEFAULT ON (spec §2.2).  ``O4_FLAT_SITE_MODE=0`` restores pre-change
# behaviour everywhere — the whole-feature kill switch, and the arm the
# degeneracy twins measure byte-identity against.
FLAT_SITE_MODE = _os.environ.get("O4_FLAT_SITE_MODE", "1") == "1"

# R11-1 (docs/specs/round11-kmci-flat-claim-spec.md) — the BELT-AND-
# SUSPENDERS bound on a claimed-object CLUSTER extension.  A cluster
# whose centroid lies further than this from the claiming airport's own
# apt.dat extent is refused with a counted finding, whatever the claim
# machinery said: HZMB, the motivating VHHH case, is ~1 km out, while
# KFLV (Z0 234.24 m) reached 19 km to claim the KMCI pack's placements
# and flattened KMCI's real ~300 m terrain under 12 synthetic insets.
# Distance, not count, is what separates those two.
FLAT_SITE_CLUSTER_MAX_KM = float(
    _os.environ.get("O4_FLAT_SITE_CLUSTER_MAX_KM", "5.0"))


# ══════════════════════════════════════════════════════════════════════
# FLAT-SITE FAST PATH (phase 3) — the SOLVE PARTITION
# ══════════════════════════════════════════════════════════════════════
# docs/specs/flat-site-fast-path-spec.md (2026-08-10, FROZEN).  On a
# ``flat_candidate`` / ``flat_declared`` site the answer is known before
# the solve starts: 71 % of OTHH's emitted nodes already sit within
# 0.05 m of Z0, and the solver spends ~4.5 min of grade-graph / reach-
# band machinery re-deriving a constant field.  The fast path PARTITIONS
# the solve: shapes the predicate can PROVE are governed by nothing but
# the constant field are BORN at Z0 as fixed-value members (the
# ``bridges.born_flat_solver_plate`` idiom — hard pins, boundary values,
# no free variables), and everything else solves fully against them.
#
# CONSERVATIVE BY LAW (spec §1): any shape the predicate cannot prove
# eligible solves fully.  Partition, never approximate.
#
# DEFAULT ON.  ``O4_FLAT_SITE_FAST_PATH=0`` restores pre-change
# behaviour everywhere; a non-flat site is byte-identical either way
# (the predicate needs a substituting flat verdict to admit anything).
FLAT_SITE_FAST_PATH = (
    _os.environ.get("O4_FLAT_SITE_FAST_PATH", "1") == "1")

# The solver quantum the fast path proves equivalence to (spec §"Tests":
# "every shared node within 0.01 m (solver quantum)").  It is also the
# demotion threshold: a candidate shape carrying a SENIOR hard pin
# (runway / tile seam / bridge deck / skirt / EAT) whose value differs
# from Z0 by more than this is not provably constant, so the whole shape
# falls back to the full solve.
FLAT_SITE_FAST_PATH_QUANTUM_M = 0.01
