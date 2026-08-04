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
    "DSF_OBJECT_CLUSTER_SEATING",
    "DSF_OBJECT_CLUSTER_SEAT_TOLERANCE_M",
    "DSF_OBJECT_PAD_MAX_RELIEF_M",
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
    "DSF_OBJECT_PAD_FLAG_SPAN_M",
    "DSF_OBJECT_FOOT_ANCHOR",
    "DSF_OBJECT_FOOT_MIN_REACH_M",
    "DSF_OBJECT_FOOT_BAND_M",
    "DSF_OBJECT_FOOT_CLUSTER_GAP_M",
    "DSF_OBJECT_FOOT_MAX_BASE_SPREAD_M",
    "DSF_OBJECT_FOOT_CONTACT_TOLERANCE_M",
    "DSF_OBJECT_FOOT_PAD_RESIDUAL_M",
    "DSF_OBJECT_FOOT_PAD_MARGIN_M",
    "DSF_BUILDING_OSM_OVERLAP_FRAC",
    "DSF_CLUSTER_SIMPLIFY_TOL_M",
    "BUILDING_OUTLINE_FILL_R",
    "BUILDING_OUTLINE_FILL_GATE_M",
    "BUILDING_CLOSE_MIN_PIECE_M2",
    "TERM_BRIDGE_GROUPING",
    "TERMINAL_SIMPLIFY_TOL_M",
    "SLOPING_EDGE_SNAP_M",
    "EMIT_JUNCTIONS",
    "EMIT_APRONS",
    "ENABLE_SERVICE_ROADS",
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
    "PAVEMENT_SCORE_ENCLAVE_GAP_M",
    "PAINTED_CENTERLINE_FALLBACK",
    "ENABLE_APRON_NECK_SPLIT",
    "HOLE_ROUTER_ENABLED",
    "HOLE_ROUTER_V2",
    "EMIT_BRIDGES_AND_TUNNELS",
    "JUNCTION_CLUSTER_DIST_M",
    "MAX_BOUNDARY_EDGE_M",
    "MIN_SEGMENT_LEN_M",
    "NECK_ABSOLUTE_M",
    "NECK_ABSORB_FRAC",
    "NECK_RELATIVE",
    "ROLE_GRADE_LIMITS",
    "FLATNESS_CERTIFICATE_RATE_FACTOR",
    "FLAT_CERTIFICATE_COVERAGE",
    "FLAT_AIRPORT_FAST_PATH",
    "REACH_BAND_CLUSTERS",
    "REACH_BAND_CLUSTER_SIZE_M",
    "RASTER_REACH_BAND_CELL_M",
    "RASTER_REACH_BAND_CONNECTIVITY",
    "RASTER_REACH_BAND_OFFNET_RADIUS_M",
    "RASTER_REACH_BAND_MAX_CELLS",
    "RASTER_REACH_BAND_GRID_RESIDUAL_M",
    "VECTORIZED_GEOMETRY",
    "HOLE_ROUTER_MID_EDGE_PRUNE",
    "RECT_CROSS_FLATNESS_TOLERANCE_M",
    "BUILDING_SEAT_FLATNESS_TOLERANCE_M",
    "TAXI_MAX_GRADE",
    "APRON_MAX_GRADE",
    "APRON_TERRACE_LAW_ENABLED",
    "APRON_TERRACE_MIN_EXCESS_M",
    "APRON_TERRACE_MAX_STEP_M",
    "APRON_TERRACE_JOINT_CLEARANCE_M",
    "APRON_TERRACE_CORRIDOR_HALF_WIDTH_M",
    "APRON_TERRACE_MIN_JOINT_LEN_M",
    "APRON_TERRACE_OVERFIRE_AREA_FRAC",
    "BUILDING_FRONTAGE_MAX_GRADE",
    "TERMINAL_MAX_GRADE",
    "TERMINAL_PADS_SLOPE",
    "TAXI_CORRIDOR_PROFILE",
    "TAXIWAY_MAX_GRADE_CHANGE_PER_M",
    "CORRIDOR_PROFILE_DAMPING",
    "CORRIDOR_DAMP_ALPHA",
    "FIELD_RUNWAY_ROUTE_BANDS",
    "SERVICE_ROAD_MAX_GRADE",
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
    "RUNWAY_VERTICAL_CURVE_K_M",
    "RUNWAY_MAX_GRADE_CHANGE_PER_M",
    "RUNWAY_DEM_FOLLOW_BAND_M",
    "GRADE_VISIBILITY_BUFFER_M",
    "ELEV_ROUNDING_NOISE_M",
    "SLOPED_QUAD_ROUNDING_NOISE_M",
    "EMIT_QUANTIZATION_MARGIN_M",
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
    "PATCH_SLOPE_CELL_SIZE_M",
    "RUNWAY_CELL_SIZE_M",
    "PATCH_SLOPE_PROFILE",
    "CLEARANCE_OBSTRUCTION_THRESHOLD_M",
    "CLEARANCE_MAX_REACH_M",
    "CLEARANCE_STATION_STEP_M",
    "RUNWAY_END_CLEARANCE_LENGTH_BY_CODE",
    "RUNWAY_END_RESA_MAX_SLOPE",
    "CLEARANCE_LATERAL_MAX_SLOPE",
    "RUNWAY_STRIP_HALF_WIDTH_BY_CODE",
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
    "OPEN_FRONTAGE_SPINE_ENABLED",
    "OPEN_FRONTAGE_CLOSE_M",
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
    "APRON_BEYOND_SHOULDER_MIN_DOWN_SLOPE",
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
    "BRIDGE_ROAD_CARRIED_PAVEMENT_PROXIMITY_M",
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
# Also gates DEBUG ARTIFACTS: the ``<patch>.axes.json`` grade-law sidecar
# is only written when > 0 (user 2026-07-02 — production patch dirs stay
# clean).  Env override O4_LOG_VERBOSITY for dev builds.
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


# Max length of any junction-polygon ring segment.  Long edges get
# subdivided to anchor Triangle4XP's interior triangulation; without
# this the elevation solver leaves the interior un-anchored on long
# straight runs and produces visible cliffs.  Shared between the
# junction-decomposition pass (densification) and the elevation
# layer (vertex-aware grade clamp).
MAX_BOUNDARY_EDGE_M = 50.0


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
# in ``terminals``/``pipeline`` — DSF is PREFERRED (it is where the
# sim physically renders the building, so grading should match it) and
# OSM fills the gaps where the DSF has no facade.  Off = byte-identical
# to the OSM-only behaviour.  Env override ``O4_DSF_BUILDINGS`` is read
# below, next to HANGAR_PADS (where ``import os as _os`` is in scope).

# When merging the two building sources, an OSM building outline is
# treated as ALREADY covered by the DSF (and dropped in favour of the
# DSF footprint) when this fraction of its area overlaps any DSF
# building footprint.  Below the threshold the OSM building is a
# distinct structure the DSF didn't place and is kept (OSM fills the
# gap).  Lowering it makes the DSF more dominant; raising it keeps more
# OSM buildings.
DSF_BUILDING_OSM_OVERLAP_FRAC = 0.2

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
# ICAO Annex 14 Vol I §3.9.3 makes the taxiway longitudinal-grade cap
# SIZE-DEPENDENT: code letters C–F (wide, ≥15 m) cap at 1.5 %, but code
# letters A/B (narrow, <15 m) may grade up to 3 %.  Stock auto_patch held
# every taxiway to 1.5 %, over-flattening small taxiways and spending grade
# budget (corridor flex / apron ramps) to keep them gentler than the spec
# requires.  See ``taxi_grade_cap_for_letter`` + the ``TAXI_GRADE_BY_WIDTH``
# gate below.
TAXI_MAX_GRADE_NARROW = 0.030   # ICAO Annex 14 code A/B taxiway-family
# TRANSVERSE (cross) grade cap — the cT in the anisotropic within-shape allowance
# cL·Δs∥ + cT·Δs⊥ (see ``taxi_transverse_cap_for_letter`` +
# docs/anisotropic_edge_handling_plan.md).  ICAO Annex 14 Vol I Table 3-2 caps the
# taxiway TRANSVERSE slope at 2 % for code A/B and 1.5 % for C–F — so for C–F it
# coincides with the longitudinal cap (isotropic) and only A/B is genuinely
# anisotropic (cT 2 % < cL 3 %).
TAXI_MAX_TRANSVERSE_NARROW = 0.020   # ICAO Annex 14 Table 3-2 code A/B transverse

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
# RUNWAY FLEX displacement budget (user 2026-07-06): the total distance a
# flexed runway profile may move from its FAA-redistributed original,
# summed over all flex rounds.  The flex law is minimum-displacement with
# the deficit SPLIT across the runways pulling on it (envelope-origin
# split in ``_apply_runway_flex_hook``); this cap is the safety net —
# HECA 05C measured a 17.8 m one-sided drop before the split landed
# (Stage A's whole-airport inter-runway deficit was only 7.67 m, so a
# lawful per-runway share stays well under this).
RUNWAY_FLEX_MAX_DISPLACEMENT_M = 4.0
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
# legal ±cap wiggles (the residual-waviness class).  TUNABLE:
# ``O4_TAXIWAY_CURVE_RUN_M`` = metres of run required per unit grade
# change (default 3000; larger ⇒ flatter, longer vertical curves).
TAXIWAY_MAX_GRADE_CHANGE_PER_M = 1.0 / float(
    _os_early.environ.get("O4_TAXIWAY_CURVE_RUN_M", "3000"))
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
# ── Corridor-profile DAMPING (user 2026-06-14) ──────────────────
# The taxi-corridor field SEEDS at the DEM and projects onto the legal
# band, so wherever the DEM is locally legal the profile sits ON the
# terrain — following its noise too closely.  Real airports grade
# taxiways/aprons "as flat as the terrain allows": the DEM is a noisy
# GUIDE, not a target; max grade is RARE (used only where no flatter
# routing satisfies the constraints), and the only HARD anchors are the
# CIFP runway thresholds + tile seams.  This adds a Laplacian (harmonic)
# smoothing term to the corridor Gauss-Seidel: each soft node diffuses
# toward its neighbours' inverse-distance-weighted mean (minimising
# Σ grade² → the smoothest profile), clamped to its legal band, with the
# 1.5 % caps + hard anchors still binding.  ``CORRIDOR_DAMP_ALPHA`` =
# per-sweep relaxation toward that mean (1.0 = full harmonic; lower =
# gentler / more DEM-near).  Gate ``CORRIDOR_PROFILE_DAMPING``
# (``O4_CORRIDOR_DAMP``) — OFF restores the pure DEM-follow.
CORRIDOR_DAMP_ALPHA = 0.5
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
# FAA vertical-curve rule L = K × |Δg|.  K = 305 m for ARC C/D (lighter
# A/B ≈ 76 m, heavy E ≈ 610 m).  ``RUNWAY_MAX_GRADE_CHANGE_PER_M`` is the
# segment-smoother's equivalent: a 1% grade change needs ~305 m of curve,
# i.e. ~1/30000 grade change per metre of pavement.
RUNWAY_VERTICAL_CURVE_K_M = 305.0
RUNWAY_MAX_GRADE_CHANGE_PER_M = 1.0 / 30000.0
# How far the runway profile may follow the raw DEM away from the linear
# baseline through its true anchors (CIFP thresholds, seams, runway crossings).
# 0 = "flat": the runway is the flattest profile its anchors permit and the DEM
# is ignored for the interior (user 2026-06-06).  The original "max DEM
# following" value was 5.0 m, which let mid-runway sections free-float up to 5 m
# off the baseline — e.g. CYXY 14R/32L dipping 4.5 m into a valley between the
# 14R threshold and the 02/20 crossing, which pulled the connecting junction low
# and made stub A 7.4%.  ``faa_joint_solve`` still enforces every grade/curvature
# cap regardless of this value.
RUNWAY_DEM_FOLLOW_BAND_M = 0.0

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
# ── Emit-quantization grade margin (2026-07-04) ──────────────────────────
# ``to_osm`` emits elevations rounded to 0.01 m (2-decimal), so each endpoint
# moves up to ±0.005 m and a pair's |Δelev| can grow by up to 0.01 m — ONE
# full emit grid step (two worst-case half-step roundings in opposite
# directions) — between the solved float field and the emitted file.  On a
# short chord at cap that headroom does not exist: a 2 m chord at 1.5 % has a
# 0.03 m legal delta, so a pair the solver drives exactly TO its budget can
# read over the law in the emitted patch (the "rounding hairline" class —
# CYXY: 126 sub-0.5 % + 38 sub-1 % excesses on 1-4 m chords).  The SOLVER's
# feasibility projection therefore SWEEPS every pair to
# ``budget − EMIT_QUANTIZATION_MARGIN_M`` so the rounded values still fit the
# raw law, while its over-cap TALLY keeps the raw budget (violations are
# reported against the true law; a both-hard pair can never move, so a
# margined tally would manufacture phantom both-hard violations).  3-decimal
# emit was tested and REFUTED (rounding was HIDING pairs — it exposed more
# than it fixed; see status notes 2026-07-03).  Env override
# ``O4_QUANT_MARGIN`` (metres); "0" disables → byte-identical pre-margin
# behaviour.
EMIT_QUANTIZATION_MARGIN_M = float(
    _os_early.environ.get("O4_QUANT_MARGIN", "0.01"))

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
    # parking) follows the DEM but is graded like a ramp to ≤ 5 % slope
    # (owner 2026-08-03, ADA §403.3 / SUDAS §8B-1 / Santa Barbara §D.5 —
    # see GROUNDSIDE_MAX_GRADE above; was 4 %, uncited) so steep terrain
    # is smoothed to a navigable surface rather than tracing raw terrain.
    "groundside_pavement": GROUNDSIDE_MAX_GRADE,
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

# Whole-airport fast path (spec §3.3 ``O4_FLAT_AIRPORT_FAST_PATH``, Tier 2).
# When a ``FlatAirportCertificate`` holds — every soft shape certifies under
# the Tier-0/1 machinery, every runway's along-axis DEM relief fits the runway
# profile budgets at ``FLATNESS_CERTIFICATE_RATE_FACTOR`` margin, and no
# bridge / tunnel / crossing-terrain / object-pad subsystem claimed geometry —
# the solve's reach bands, spine profile, body fill and feasibility iteration
# collapse: every soft node takes its DEM seed value.  Default ON;
# ``O4_FLAT_AIRPORT_FAST_PATH=0`` forces the normal solve for every airport
# (the env-gate A/B inertness harness, spec §4.1).
FLAT_AIRPORT_FAST_PATH = (
    _os_early.environ.get("O4_FLAT_AIRPORT_FAST_PATH", "1") == "1")

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

# Grid bucket side (m) for the reach-band cluster amortization.  ~24 m keeps a
# bucket small enough that its members share one serving centerline in the
# common case (so the shared-line reuse fires often) while still amortizing the
# scan over the tens of apron/taxiway body nodes a bucket holds.
REACH_BAND_CLUSTER_SIZE_M = 24.0

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
# + the ``to_osm`` soft-strip twin).  The documented residual is sub-0.25 m
# junction ``route_band`` grid-discretization noise
# (``RASTER_REACH_BAND_GRID_RESIDUAL_M``, emitted surface unchanged).
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
# Grid-discretization residual (Tier 3 wave 2b, 2026-07-18) — DOCUMENTED
# TOLERANCE, not a validator relaxation.  At ``RASTER_REACH_BAND_CELL_M`` = 3 m
# the grid-vs-continuous geodesic distance carries a bounded band-edge error
# (≤ cell/√2 per the nearest-cell query plus the anchor-snap and ½-cell
# erosion).  Measured worst case = 0.228 m at SPJC's one dense multi-anchor
# junction complex (23 sub-0.25 m junction ``route_band`` deficits — ceil +
# pinned — with the EMITTED SURFACE unchanged: 0 tears, 0 within-shape, 0
# cross-shape).  ``test_route_band`` accepts junction ``route_band`` violations
# up to this bound WHEN the raster band is active; anything larger, off a
# junction, or any emitted-surface defect is still a real regression.  Finer
# cells would erase the residual at a performance cost not warranted (no
# emitted-surface check is affected, and the whole point of the raster field is
# the OTHH band-machinery win, 74 s → 1.2 s).
RASTER_REACH_BAND_GRID_RESIDUAL_M = 0.25
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

# Phase-1 emit-suppression toggles (kept from the pre-refactor
# baseline; iteration aids that remain useful).
EMIT_JUNCTIONS = True
EMIT_APRONS = False

# Ground-vehicle service-road network — gated OFF (deferred feature).  The
# service_roads.py machinery stays in place, but the OSM small-road lookup
# and the apt.dat 1206 truck-edge parse are skipped while disabled so we
# don't waste cycles loading roads we won't use.  Flip to re-enable.
ENABLE_SERVICE_ROADS = False

# (2026-07-31) ENABLE_DISCOVERED_TAXIWAYS lived here.  It gated the
# medial-axis discovery of unreferenced taxiway centerlines, whose only two
# consumers — ``_build_taxi_rects`` and ``junction_spine`` — were retired by
# d4f61d6 on 2026-07-29; from then on the gate switched nothing.  Retired
# with the branch (pipeline.py).  The extractor survives, unwired, in
# pavement/discovered_taxiways.py — its header records the re-wiring cost.

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
SCORER_SERVICE_ADJ = _os.environ.get("O4_SCORER_SERVICE_ADJ", "0") == "1"
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
LATERAL_CONTIGUITY_LAW_ENABLED = _os.environ.get(
    "O4_LATERAL_CONTIGUITY_LAW", "1") == "1"
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
SERVICE_LOT_ABSORPTION = _os.environ.get(
    "O4_SERVICE_LOT_ABSORPTION", "1") == "1"
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
# the report IS the disposition.  ``O4_TRIANGLE_PLANE_REPORTS=0`` restores
# the export call, which now lands in a report-only set.
TRIANGLE_PLANE_REPORTS = _os.environ.get(
    "O4_TRIANGLE_PLANE_REPORTS", "1") == "1"
# ── APRON TERRACE LAW (owner ruling 2026-08-04; spec
# ``docs/specs/apron-terrace-law-spec.md``) ─────────────────────────
# "Long aprons on genuinely steep ground MAY terrace into level panels
#  with declared joint steps — but it has to be done in a way that does
#  not interrupt any spine where aircraft have to travel."
# BINDING CONSTRAINT (structural here, not checked-after): a terrace
# joint NEVER crosses a taxi spine/route.  The joint geometry is
# DIFFERENCED against the corridor cover before it exists, so a joint
# that would cross a route is not shortened after the fact — it is
# never minted.  Gate OFF ⇒ no trigger, no panel, no joint, no budget
# change and no sidecar key: byte-identical.
APRON_TERRACE_LAW_ENABLED = _os.environ.get(
    "O4_APRON_TERRACE_LAW", "0") == "1"
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
# Over-fire STOP instrument (spec band 6): panelization touching more
# than this fraction of an airport's apron area is reported as
# OVER-FIRE.  Report-only — the law adjudicates, the instrument counts.
APRON_TERRACE_OVERFIRE_AREA_FRAC = 0.20
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
# G-ENCLAVE (owner ruling 2026-07-28): "groundside can never be
# surrounded by airside pavement unless it has a tunnel or bridge
# service road to get out" — airside and groundside must be separable
# by one continuous boundary.  A groundside shape whose exterior ring
# has less than this length uncovered by airside pavement counts as
# fully surrounded (the gap allowance absorbs vertex noise; a real
# vehicle exit is far wider).
PAVEMENT_SCORE_ENCLAVE_GAP_M = float(
    _os.environ.get("O4_PAVEMENT_SCORE_ENCLAVE_GAP_M", "3.0"))
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
# Corridor-profile Laplacian damping (see CORRIDOR_DAMP_ALPHA above).
# Default ON (user 2026-06-14): with FIELD_RUNWAY_ROUTE_BANDS the bands
# carry real slack, so the harmonic smoothing now halves corridor
# grade-change (HECA kinks >1%: 56→23) and settles aprons toward terrain
# instead of being a no-op.  O4_CORRIDOR_DAMP=0 restores the pure DEM-follow.
CORRIDOR_PROFILE_DAMPING = _os.environ.get("O4_CORRIDOR_DAMP", "1") == "1"
# Junction node-altitude RIPPLE smoothing (user 2026-06-15): the twist
# pass leaves a free junction RING vertex bowed off the line between its
# two ring-neighbours — a grade-CHANGE (curvature) kink under the 1.5 %
# cap, so the grade-magnitude smoother never touches it (user: "the shape
# edges are welded and matched correctly but there's a little ripple
# before getting into the heart of the junction; that second node needs
# to be averaged between the shape edge node and the third one in").  A
# ring-Laplacian pass averages each FREE (un-welded, non-rect-corner)
# vertex toward the distance-linear interpolation of its ring neighbours,
# HOLDING welded/shared and sloping-rect-corner vertices (so no
# cross-shape step).  O4_JCT_RIPPLE=0 disables it.
JUNCTION_RIPPLE_SMOOTH = _os.environ.get("O4_JCT_RIPPLE", "1") == "1"
# Field RUNWAY-anchor route bands (user 2026-06-14): measure the
# network-profile field's runway-anchor feasibility band along the
# centerline TAXI ROUTE (taxi_routing) instead of the field graph.  The
# field graph carries chord + proximity coupling edges that shortcut
# STRAIGHT across apron/junction interiors, so a runway contact reachable
# in 146 m of pavement-geodesic is really ~350 m along the taxiway an
# aircraft (and the graded surface) follows — the field floors the apron
# ~1-3 m too high, lifting it off the terrain (the bump the user reports).
# Mirrors the enforce's _runway_reach_bands (already route-measured); the
# field was the one out of step.  Seam/threshold pins keep the field-graph
# entry.  Default ON (user 2026-06-14); O4_FIELD_RW_ROUTE=0 restores the
# pure field-graph band (byte-identical).
FIELD_RUNWAY_ROUTE_BANDS = _os.environ.get("O4_FIELD_RW_ROUTE", "1") == "1"

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

# SEAM APRON COMPLEX POLISH (user 2026-06-20).  The per-apron isolated polish
# (SPREAD_APRON_GRADE) holds every vertex an apron shares with ANOTHER shape, so
# when a near-seam apron has been sliced into thin slivers (neck-split /
# spine-slice / decompose), each sliver freezes its shared boundary at the
# taxi-network level and the 1.5-2 m drop to the seam DEM has no contiguous free
# interior to ramp through — it dumps into one edge (SPLP -77 aprons #16/#17/#19:
# 7-18 % cliffs against seam verts that are correctly pinned to terrain).  FIX:
# for each CONNECTED apron complex that touches a seam, polish the slivers
# TOGETHER — hold only the seam vertices + vertices shared with NON-apron shapes
# (the taxi-network boundary), FREE the apron<->apron shared interior, so the
# ramp spreads across the complex's full depth.  Non-seam apron complexes keep
# the per-apron polish (byte-identical).  Single-tile airports have no seam → no
# effect.  O4_SEAM_APRON_COMPLEX=0 restores the per-apron-only polish.
SEAM_APRON_COMPLEX_POLISH = _os.environ.get(
    "O4_SEAM_APRON_COMPLEX", "1") == "1"

# SPREAD APRON GRADE (user 2026-06-20).  The global within-shape projection
# (``_project_within_bands``) doesn't converge on a frustrated apron complex
# — an apron pinned high on one edge (a seam / neighbour at the higher
# terrain) and low elsewhere oscillates over the whole welded belt and falls
# back to the DEM seed, dumping the whole climb into ONE steep edge (SPLP -78
# apron: 8.35 % over 6 m, the rest flat).  Polish each apron / junction in
# ISOLATION after the enforce — hold its HARD + SHARED-with-neighbour vertices
# (so seams and cross-shape joins never move), cap-project only its PRIVATE
# interior on its own visibility edges (``_project_shape``).  A small isolated
# shape converges, so the climb SPREADS across the interior to a smooth ramp
# instead of one wall.  Same machinery as the (gate-off-by-default) terminal
# pad polish; default ON.  O4_SPREAD_APRON_GRADE=0 restores the old behaviour.
SPREAD_APRON_GRADE = _os.environ.get("O4_SPREAD_APRON_GRADE", "1") == "1"

# DSF terminal/hangar building footprints (user 2026-06-12) — see the
# documented block near LOAD_DSF_PAVEMENT above.  Read here because
# ``import os as _os`` only comes into scope at this point in the file.
DSF_BUILDINGS = _os.environ.get("O4_DSF_BUILDINGS", "1") == "1"

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

# (2026-06-17) RUNWAY-SHOULDER SEGMENTATION REACH — docs/runway_
# shoulder_detection.md.  The runway-segmentation breakpoint collector
# splits the runway where adjacent pavement / taxiway polygon edges
# CONTACT it, but its proximity budget is a FIXED generic ~7.6 m FAA
# shoulder allowance.  When apt.dat row-100 declares an EXPLICIT
# shoulder width (``shoulder_code // 100`` ≥ 1, e.g. OMAA's 20 m), the
# real paved edge a taxiway connects to sits at runway-half + that
# shoulder (50 m from a 60 m runway's centerline), well past the 42 m
# the fixed budget reaches — so the exit's contact never becomes a
# seam and the runway segment boundary lands at the wrong longitudinal
# position (the OMAA 13R/31L gap).  ON ⇒ the contact budget for a
# shouldered runway is its apt.dat-coded shoulder + chart tolerance, so
# seams land where pavement meets the shoulder edge as defined in
# apt.dat.  Runways with NO coded shoulder (code < 100) keep the 7.6 m
# budget ⇒ byte-identical.  Env override ``O4_SHOULDER_SEGMENT``.
RUNWAY_SHOULDER_SEGMENT = (
    _os.environ.get("O4_SHOULDER_SEGMENT", "1") == "1")

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


# SHORT-RECT → JUNCTION (user 2026-06-30): a taxi rect shorter than this along
# its axis is a rigid sloping PLANE where the spine wants to CURVE through
# smoothly (HECA's curved taxiways).  Such rects are NOT emitted — the pavement
# stays junction residue (pav_union.difference(rects)) so the centerline grades
# through it continuously instead of as a chain of planar facets.  ``0`` disables
# (restore the prior behaviour where any-length rects are emitted).
MIN_RECT_LENGTH_M = float(_os.environ.get("O4_MIN_RECT_LENGTH_M", "100.0"))

# (s79) ON-PAVEMENT service-road carve — docs/service_road_carve.md.
# ★ USER RULINGS 2026-06-11: roads = apt.dat 1206 routes ONLY (no
# polygon/OSM detection); only pavement narrower than the cross-section
# cap is classified; nothing near a terminal; roads WORK LIKE TAXIWAYS
# — qualifying runs join the centerline set as ``SVC*`` refs and ride
# the single rect → junction → absorption decomposition with role
# ``service_road`` (5 %).  Independent of ``ENABLE_SERVICE_ROADS`` (the
# deferred OSM small-road / off-pavement builder).  DEFAULT ON for the
# user's in-sim evaluation (2026-06-12; Steps C/D landed @b391e27 —
# CYXY roads-on 0/0/0, HECA 57/0/0 invariants held);
# ``O4_SERVICE_ROAD_CARVE=0`` restores the road-less build.
SERVICE_ROAD_CARVE = _os.environ.get("O4_SERVICE_ROAD_CARVE", "1") == "1"
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
# that curve — hence a separate knob.
#
# To find the optimal compromise, sweep these and measure each build with
# ``tools/mesh_region_tris.py`` (triangle count) + the X-Plane load time.
# Historical default 2 m carried a "KBNA finding" note (smooth runway
# vertical transitions) — raise the runway value cautiously.
PATCH_SLOPE_CELL_SIZE_M = 10      # taxiway / apron / boundary sloped rects
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
ADJACENT_GROUND_LAW_ENABLED = (
    _os.environ.get("O4_ADJACENT_GROUND_LAW", "1") == "1")

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

# Audit-tool proxy for the road-carried-overpass discriminator (the
# audit has no layout to read taxi/truck routes from): a bridge with no
# draped-pavement polygon within this distance of its deck footprint
# carries a ROAD on its deck, not a taxi/truck route.  MEASURED
# separation (KBNA 2026-07-09): the largest pavement gap at a TRUE
# taxi/truck bridge is 60.9 m (Murfreesboro Oeste; taxiway-L 9.6-9.7 m),
# while the road overpass (Crossing_Bridge) sits 176.2 m from any
# pavement — 100 m splits the families with ~40 % margin both ways.
# The in-pipeline discriminator reads layout taxi/truck shapes instead
# and does not use this constant.
BRIDGE_ROAD_CARRIED_PAVEMENT_PROXIMITY_M = 100.0

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
DRAINAGE_SPINE_LAW_ENABLED = (
    _os.environ.get("O4_DRAINAGE_SPINE_LAW", "1") == "1")

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
# the gate off.
OPEN_FRONTAGE_SPINE_ENABLED = (
    _os.environ.get("O4_OPEN_FRONTAGE_SPINE", "0") == "1")
# Morphological-closing radius used to DETECT open corridors: a closing
# of the airside union (buffer out then back in) bridges any open channel
# up to 2*radius wide.  Half the gap-fill max width, so a corridor up to
# GAP_FILL_MAX_WIDTH_M across is detected; wider regions are legitimately
# ungoverned terrain and stay with the corridor-band / daylight law.
OPEN_FRONTAGE_CLOSE_M = GAP_FILL_MAX_WIDTH_M / 2.0

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
# 18L); runway flex can add up to RUNWAY_FLEX_MAX_DISPLACEMENT_M.
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
B4_FLIP_DEFAULTS = (_os.environ.get("O4_B4_FLIP", "1") == "1")
ADJACENT_GROUND_FULL_EXTENT_COVERAGE = (
    _os.environ.get("O4_ADJACENT_GROUND_FULL_EXTENT_COVERAGE", "0") == "1")
# B4 review switch flips this default ON under the bundle.  Applied as a
# post-assignment override (not an inline conditional default) so the
# gate keeps a plain "0" literal — the provenance source-parser reads
# that literal, so the delivery stamp stays accurate — while an explicit
# O4_ADJACENT_GROUND_FULL_EXTENT_COVERAGE always wins over the switch.
if (B4_FLIP_DEFAULTS
        and "O4_ADJACENT_GROUND_FULL_EXTENT_COVERAGE" not in _os.environ):
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
APRON_BEYOND_SHOULDER_MIN_DOWN_SLOPE = 0.03
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
APRON_WALL_CONTINUITY_ENABLED = (
    _os.environ.get("O4_APRON_WALL_CONTINUITY", "1") == "1")
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
APRON_WALL_SCOPE_ENABLED = (
    _os.environ.get("O4_APRON_WALL_SCOPE", "1") == "1")
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
RUNWAY_STRIP_WALL_LAW_ENABLED = (
    _os.environ.get("O4_RUNWAY_STRIP_WALL_LAW", "1") == "1")

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
# ~:4890), not a tear.  Fixed here at the EMIT side only; the at-source
# variant (per-shape canonical variables in the solver writeback) is
# recorded as future work.  Gate OFF ⇒ byte-identical to the pre-fix
# valuation.
BAND_CORRIDOR_CLAMP_ENABLED = (
    _os.environ.get("O4_BAND_CORRIDOR_CLAMP", "1") == "1")


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


def is_unnamed_taxi_ref(ref) -> bool:
    """True iff ``ref`` carries no real apt.dat taxiway designator — an empty
    ref OR a synthetic ``~U`` serial we assigned to an unnamed route."""
    return (not ref) or str(ref).startswith(SYNTH_TAXI_NAME_PREFIX)


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


# (20260621) ROUTE-BAND WIDTH CAP — apron-spine climb law.  The runway-reach
# feasibility band (``_runway_reach_bands``) propagates a single uniform grade
# cap over the taxi-route graph, so the band ceiling a node can climb to is
# computed at the 1.5 % ``TAXI_MAX_GRADE`` rate even along a narrow code-A/B
# taxiway that is allowed 3 %.  That artificially TIGHTENS the band on narrow
# routes (and can falsely invert a short steep route to the runway — the
# invariant "every taxi-route centerline stays feasible to the runway").  When
# ON, each route-graph edge carries its own cap from its taxiway code letter
# (``taxi_grade_cap_for_letter``): narrow A/B edges 3 %, C–F 1.5 %.  Gate off
# (or ``TAXI_GRADE_BY_WIDTH`` off, which makes every edge cap fall back to
# 1.5 %) is byte-identical to the uniform band.  Default ON.
TAXI_REACH_BAND_BY_WIDTH = _os.environ.get(
    "O4_REACH_BAND_BY_WIDTH", "1") == "1"

# (20260621) JUNCTION NARROW GRADE (PER-AXIS) — apron-spine climb law.  A
# JUNCTION is the moving network the taxiways flow through, held to the uniform
# 1.5 % cap.  But where a narrow code-A/B taxiway runs THROUGH a junction (or a
# junction-tagged corridor sliced out of an apron — CYXY taxiway G), that
# corridor IS the narrow taxiway and must climb at its 3 % code-A/B rate to
# reach high terrain/buildings.  The taxi network's local climb rate is the
# constraint that actually pins the airside complex ~10 m below terrain (the
# aprons are welded to the corridor and cannot rise above it).  When ON, the
# solver's per-axis junction edges that run ALONG a narrow centerline earn the
# 3 % cap; ring/transverse edges keep 1.5 % (matching the validator's per-axis
# cL=0.03 / cT=0.02).  ★ PER-AXIS, NOT isotropic: a blunt isotropic 3 % cap
# destabilises the solve (the corridor tilts transversely; CYXY within 18 → 41).
# Default ON (the corridor climb only manifests with the DEM attraction present).
JUNCTION_NARROW_GRADE = _os.environ.get("O4_JCT_NARROW_GRADE", "1") == "1"

# (20260622) CORRIDOR SPINE CHAINS — plan P2 (docs/taxi_centerline_grading_plan
# .md §5): extend the corridor profile to cover EVERY apt.dat taxi centerline,
# not only the stretches that have taxi RECTS.  Where a centerline runs through
# an apron as a stretch of promoted ROLE_JUNCTION pieces (SPINE_PIECE_ROLE_REEVAL
# — CYXY taxiway G crosses its apron as ~7 such pieces) there is no rect, so no
# corridor station samples/writes the NETWORK PROFILE field along it and the
# stretch settles to raw relief (the airside "bowl").  When ON, the corridor
# pass adds a STATION CHAIN over each such centerline's spine nodes (canonical
# nodes within ~2 m of the line, ordered by projection) so the already-solved
# field value is written onto those nodes and HELD — making every centerline
# route one continuous, field-consistent profile that the surrounding apron then
# conforms to.  Built ONLY for a centerline with ≥1 node no rect station covers
# (the promoted-apron case); a fully rect-covered centerline is skipped, so an
# airport without such stretches stays byte-identical.  Requires
# NETWORK_PROFILE_MODEL + TAXI_CORRIDOR_PROFILE (the field that supplies the
# spine values).
CORRIDOR_SPINE_CHAINS = _os.environ.get("O4_CORRIDOR_SPINE_CHAINS", "1") == "1"

# (20260622) FIELD ROUTE-BAND BY WIDTH — plan P3 (docs/taxi_centerline_grading_
# plan.md §5).  The NETWORK PROFILE field's per-node feasibility band
# [floor, ceiling] is the runway-anchor reach measured along the taxi route.
# Its field-graph leg already honours the per-letter cap (narrow_lines stretch
# the edge length so the uniform-cap Dijkstra applies 3 %), BUT the
# FIELD_RUNWAY_ROUTE_BANDS override (`_runway_route_band`, measured over the
# plain `rw_route_graph`) recomputed the band at the UNIFORM 1.5 % and REPLACED
# the field-graph band where it reached — re-pinning a narrow code-A/B route's
# ceiling ~1.5 m/100 m below where the taxiway may legally climb (CYXY taxiway G:
# field ceiling 727 → route-override 712, ~6 m below the DEM rim → G band-pinned
# in the "bowl").  When ON, `_runway_route_band` consumes the route graph's
# per-edge cap (`TaxiRouteGraph.edge_cap`, the same 3 % data `_runway_reach_bands`
# uses under TAXI_REACH_BAND_BY_WIDTH), so a narrow route's ceiling rises to its
# real 3 % reach and the DEM-seeded centerline can climb to terrain (minimal-
# deviation: closest-to-DEM within the band).  Gate off → uniform `eff` →
# byte-identical to the prior route override.  Requires FIELD_RUNWAY_ROUTE_BANDS.
# ★ DEFAULT OFF (2026-06-22): the band fix is CORRECT (the route override no
# longer wrongly clips a narrow route's ceiling to 1.5 %), but loosening the
# ceiling STANDALONE regresses — the held centerline climbs ~2-3 m higher while
# its apron/junction neighbours stay at their lower DEM/relief level, so the
# within-shape grade across those junctions spikes (CYXY test-mirror within
# 0→10, build 6→14, a new 8.8 % junction).  The climb must be ABSORBED by
# conforming neighbours = plan P4 (aprons/buildings conform up to the held
# centerlines).  Flip ON together with P4; OFF keeps the clean P2 baseline.
# Default ON (2026-06-23): part of the single-grade-graph stack — the per-edge
# cap-weighted route band the connecting solve relies on.  O4_FIELD_ROUTE_BAND_BY_WIDTH=0
# restores the legacy uniform-1.5% band.
FIELD_ROUTE_BAND_BY_WIDTH = _os.environ.get(
    "O4_FIELD_ROUTE_BAND_BY_WIDTH", "1") == "1"

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

# (20260622) FIELD-TARGET CONFORMANCE — plan P4/P5 (docs §9): make the final
# within-shape enforce implement the user's stated objective — *minimise
# |elev − DEM| within the feasibility band* — instead of movement-minimising from
# a relief-bowled seed.  Before the final difference-constraint projection, lift
# each soft (non-hard, non-held, non-band-pinned) node toward its closest-to-DEM
# feasible level ``clamp(DEM, lo, hi)``, **LIFT-ONLY** (never lower; never above
# the ceiling).  With the per-letter bands now correct (P3a recovers the unnamed
# arms' 3 %; P3 the field route-band), this lifts the bowled airside — buildings
# to their reachable-DEM (min(DEM, ceiling)), aprons/junctions with them — so the
# held corridor's neighbours rise WITH it and the within-shape steps close.  The
# subsequent projection (held corridor + hard anchors immovable) drives the lifted
# surface grade-compliant; all-ceiling is Lipschitz-compliant so the lift is
# grade-safe.  Pairs with UNNAMED_TAXI_SIZE (P3a) + FIELD_ROUTE_BAND_BY_WIDTH (P3).
# ★ DEFAULT OFF + INCOMPLETE (2026-06-22): this lift is the conformance VEHICLE
# but is NOT sufficient alone for the wide-apron terminal.  Measured (CYXY,
# P3a+P3+this): buildings DIRECTLY on a narrow arm un-bowl, but the MAIN terminal
# (building1/3/6) does NOT lift — its WIDE APRON is lifted by the field only
# toward the LOW corridor (the apron-plane pass is lift-only-toward-taxi), so the
# pad is gated to ~corridor+1%·apron-width, not its arm-route ceiling; lifting the
# corridor to its raw route-CEILING instead explodes within-shape (89) because the
# ceiling is Lipschitz along the ROUTE, not the geometry (route-vs-geom steps at
# held junctions).  THE MISSING PIECE: the BUILDING must be the DRIVER — band via
# per-edge `edge_cap` (NOT the uniform cap `_anchor_buildings_at_feasible_dem`
# uses), placed at min(DEM, that band), with the apron conforming UP to the
# *building* (not the corridor) and the corridor→apron transition taken by the
# arm/an explicit ramp.  Until that lands this gate is net-neutral-to-negative
# (CYXY within 8→12) — kept gated OFF as the vehicle.
FIELD_TARGET_CONFORMANCE = _os.environ.get(
    "O4_FIELD_TARGET_CONFORMANCE", "0") == "1"

# (20260622) BUILDING ROUTE FEASIBILITY — plan P4 (the building DRIVER, docs §9).
# Seat each building that touches airside pavement FLAT at the elevation closest
# to its DEM that keeps it reachable WITHIN GRADE from EVERY runway threshold
# along the real taxi route (user metric, validated on CYXY): a perpendicular
# from the building centroid to the nearest taxi centerline (taxiway-corridor
# part at the taxiway cap, apron part at 1%), then the per-edge per-letter-capped
# centerline route to all thresholds; band = intersection over thresholds;
# level = clamp(DEM, floor, ceiling).  Buildings NOT touching airside pavement
# stay at DEM.  Unlike the retired uniform-cap building anchor (bowled),
# this uses TaxiRouteGraph.edge_cap, so it pairs with UNNAMED_TAXI_SIZE (P3a) —
# the unnamed arms must carry their real size for the band to be right.  The
# seated pads become hard anchors the rest of the network grades to.
# `elevation_per_surface/building_feasibility.py`.  ★ DEFAULT OFF until the
# network conforms to the anchors (the min-grade network solve is the next step).
BUILDING_ROUTE_FEASIBILITY = _os.environ.get(
    "O4_BUILDING_ROUTE_FEASIBILITY", "0") == "1"

# (20260622) MIN-GRADE NETWORK SOLVE — plan P5 (docs §9), the user's stage 2.
# With buildings (P4) + runway thresholds/interior + tile seams as HARD anchors,
# re-solve the airside taxi/apron/junction network as the SMOOTHEST profile that
# connects them — minimise Σ grade² (a harmonic / inverse-distance² Gauss-Seidel
# step) subject to the per-shape within-shape grade caps as bounds — so the
# network CONFORMS to the anchors instead of discovering its own bowled levels.
# Runs as a final override of the free airside nodes (anchors fixed) after the
# existing solve.  Pairs with BUILDING_ROUTE_FEASIBILITY (P4) — without the
# building anchors there is nothing new to conform to.  ★ DEFAULT OFF
# (prototype): replaces field/relief/enforce for the airside; validate before
# defaulting on.  Gate off → byte-identical.
MIN_GRADE_NETWORK = _os.environ.get("O4_MIN_GRADE_NETWORK", "0") == "1"

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

# (2026-07-17) DETACHED building pads (touching NO qualifying airside
# pavement) are HARD-PINNED flat at their footprint DEM (median over
# ring + centroid samples) for the whole solve.  Without the pin their
# ring nodes are free field nodes: the route-profile blend paints them
# with the surrounding airside level (KBNA SE lot: pads emitted at
# 170-172 over 158-167 ground — flat plateaus 6-11 m above the DEM and
# the abutting groundside).  ``O4_DETACHED_PAD_DEM_PIN=0`` restores the
# free-field behaviour.
DETACHED_PAD_DEM_PIN = _os.environ.get(
    "O4_DETACHED_PAD_DEM_PIN", "1") == "1"
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


def taxi_grade_cap_for_letter(letter, *, enabled: bool = None) -> float:
    """Max longitudinal grade (rise/run) for a taxiway of ICAO code
    ``letter``.  Code A/B (narrow, <15 m) → ``TAXI_MAX_GRADE_NARROW``
    (3 %, ICAO Annex 14 §3.9.3); code C–F (and any unknown/None letter) →
    ``TAXI_MAX_GRADE`` (1.5 %).  When the ``TAXI_GRADE_BY_WIDTH`` gate is
    off, always returns ``TAXI_MAX_GRADE`` so the build is byte-identical
    to the uniform-cap baseline.  Pass ``enabled`` to override the gate
    (used by the validator to honour the same flag the build ran under)."""
    on = TAXI_GRADE_BY_WIDTH if enabled is None else enabled
    if on and letter and str(letter).upper() in NARROW_TAXI_CODE_LETTERS:
        return TAXI_MAX_GRADE_NARROW
    return TAXI_MAX_GRADE


def taxi_grade_cap_for_width(width_m: float, *, enabled: bool = None) -> float:
    """Convenience wrapper: resolve the code letter from a pavement width
    (m) via :func:`taxiway_code_letter`, then the grade cap."""
    return taxi_grade_cap_for_letter(
        taxiway_code_letter(width_m), enabled=enabled)


def taxi_transverse_cap_for_letter(letter, *, enabled: bool = None) -> float:
    """Max TRANSVERSE (cross) grade for a taxiway of ICAO code ``letter`` — the
    ``cT`` in the anisotropic within-shape allowance ``cL·Δs∥ + cT·Δs⊥``.

    Code A/B (narrow) → ``TAXI_MAX_TRANSVERSE_NARROW`` (2 %, ICAO Annex 14 Table
    3-2); code C–F (and any unknown/None letter) → the LONGITUDINAL cap
    (:func:`taxi_grade_cap_for_letter`, 1.5 %), i.e. ISOTROPIC there.  Honours the
    same ``TAXI_GRADE_BY_WIDTH`` gate as the longitudinal cap, so when
    width-grading is off ``cT`` collapses to ``cL`` for EVERY letter and the
    allowance is the legacy isotropic ``cap·dist``.  ``enabled`` overrides the gate
    (the validator passes the flag the build ran under, for lockstep)."""
    on = TAXI_GRADE_BY_WIDTH if enabled is None else enabled
    if on and letter and str(letter).upper() in NARROW_TAXI_CODE_LETTERS:
        return TAXI_MAX_TRANSVERSE_NARROW
    return taxi_grade_cap_for_letter(letter, enabled=enabled)


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
