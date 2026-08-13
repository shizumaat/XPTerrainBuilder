"""Adjacent-ground grade law — the LATERAL banded emitter (slice 3).

The lateral generalization of the runway-END skirt: ground beside a
paved surface is a two-zone-plus-ungraded CORRIDOR off the pavement
EDGE (``grade_law.adjacent_ground_envelope``, single law source).  This
module MARCHES that corridor outward from every airside pavement edge
that faces unpaved ground and emits ``graded_strip`` surface polygons
wherever the smoothed DEM sits OUTSIDE the corridor:

  * DEM ABOVE the ceiling  → CUT down to the ceiling (rising terrain;
    under the enforce-fully mandate the zone-1/2 ceiling is BELOW the
    edge, so a flat surround is excavated to the lawful drainage slope).
  * DEM BELOW the floor     → FILL up to the floor (falling terrain,
    only inside zones 1-2 where the floor is finite — zone 3's floor is
    ``None``, so a cliff beyond the graded band renders as DEM: the
    boundary-bridge killer).
  * DEM INSIDE the corridor → emit NOTHING (the terrain is lawful).

The machinery is the runway-end skirt's banded emission, with both
directions inline-duplicated MINIMALLY from clearance.py (flagged for
the cleanup slice): ``_build_fill_bands`` twins ``_build_filled_skirts``
(all-band run widening, no skirt-lift ring values), ``_build_cut_bands``
mirrors it for the corridor's piecewise-continuous ceiling (the skirt's
cut twin ``_build_graded_strips`` takes a single linear slope).  Bands are
split at the law's zone breakpoints, carry per-band ``node_altitudes``,
and are clipped EXACTLY against every existing shape + the airport
boundary (weld ruling 2026-07-09: the band's inner row sits ON the
pavement ring with the pavement edge values verbatim — no standoff
groove; shared boundaries weld by shared coordinates + the guarded
value adoption below).

Runway ENDS are OUT OF SCOPE (the runway-end skirt law owns them, and
the skirt shapes are already in the static block, so the cut/fill bands
clip against them and never double-write); runway-END ring edges are
skipped by the outward-normal test the ring-edge sweep uses.

Behind ``config.ADJACENT_GROUND_LAW_ENABLED`` (env
``O4_ADJACENT_GROUND_LAW``, default off).  With the gate off this module
is never imported (the pipeline import is inside the gated block), so it
is byte-inert.
"""
from __future__ import annotations

import bisect
import math
import os

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

import O4_UI_Utils as UI

_GEOM_EXC = (ValueError, GEOSException, TopologicalError)

from .config import (
    ADJACENT_GROUND_END_PIN_ENABLED,
    ADJACENT_GROUND_LIP_WIDTH_M,
    ADJACENT_GROUND_PROLONG_HOST_REF,
    ADJACENT_GROUND_SEAM_PROLONG_ENABLED,
    ADJACENT_GROUND_SEAM_PROLONG_MAX_M,
    APRON_BEYOND_SHOULDER_MAX_DOWN_SLOPE,
    APRON_EDGE_WALL_MIN_DROP_M,
    APRON_SHOULDER_WIDTH_M,
    APRON_WALL_MIN_AREA_M2,
    APRON_WALL_MIN_RUN_M,
    APRON_WALL_PAVEMENT_ADJACENCY_M,
    APRON_WALL_RUN_HYSTERESIS_M,
    CLEARANCE_MAX_REACH_M,
    CLEARANCE_OBSTRUCTION_THRESHOLD_M,
    CLEARANCE_STATION_STEP_M,
    RUNWAY_STRIP_HALF_WIDTH_BY_CODE,
    ruleset_strip_half_width_m as _ruleset_strip_half_width_m,
    RUNWAY_STRIP_WALL_LAW_ENABLED,
    STRIP_PRECEDENCE_ENABLED,
    STRIP_WIDTH_FROM_CENTERLINE_ENABLED,
    TILE_CUT_HALF_WIDTH_M,
    runway_code_number,
    runway_end_approach_class,
    taxiway_strip_graded_half_width_for_letter,
)
from .grade_law import (
    adjacent_ground_end_pin_flags,
    adjacent_ground_envelope,
    adjacent_ground_supported_depths,
    ols_lateral_handover_distance_m,
    runway_axis_and_width,
    runway_strip_band_width_m,
    runway_strip_lateral_footprint_ring,
    runway_strip_longitudinal_clamp,
    runway_strip_longitudinal_runs,
    runway_strip_wall_keepout_rings,
    ruleset_of as grade_law_ruleset_of,
    strip_longitudinal_breaches,
    strip_longitudinal_law,
)
from .layout import (
    BuiltShape,
    PavementLayout,
    R_EARTH,
    SHARED_VERTEX_TOL_M,
    ROLE_APRON,
    ROLE_BUILDING,
    ROLE_CROSS_CONNECTOR,
    ROLE_GRADED_STRIP,
    ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL,
    ROLE_RETAINING_WALL,
    ROLE_RUNWAY,
    ROLE_RUNWAY_CROSSING,
    ROLE_SECONDARY_PARALLEL,
    ROLE_STUB,
    ROLE_TUNNEL_RAMP,
    ROLE_TUNNEL_TRENCH,
    ROLE_BRIDGE_TRENCH,
    ROLE_BRIDGE_CAUSEWAY,
    RUNWAY_END_REGIME_REFS,
    VERTEX_ALT_MERGE_TOL_M,
    taxi_shape_code_letter,
)
from .elevation import _sample_dem
from .pavement.junctions import _decompose_polygon_with_holes
from .pavement.runways import _sample_runway_segment_elev
# READ-ONLY reuse of the runway-end skirt machinery (clearance.py).  The
# fill direction is IDENTICAL to the skirt's, so its builder + shared
# constants are imported rather than re-implemented (the plan: reuse the
# skirt's patterns; inline-duplicate only what genuinely differs).
from .clearance import (
    _declaw_alt_needles,
    _open_coords,
    _PAVEMENT_GAP_M,
    _RING_END_NORMAL_DOT,
    _RING_PROBE_M,
    _unit,
)
# Shared with the layout-wide emit decimation: the group decimation for the
# late-emitted bands and the millimetre vertex-identity key the
# value-agreement registry uses (one identity convention everywhere).
from .emit_decimate import (
    Z_TOL_BOUNDARY_M,
    _key as _vertex_key,
    decimate_shape_group,
)
# THE one home for the graded-strip seam law (spec seam-continuity-v2 §1,
# v3 §1 "third-copy absorption").  ``blend_cross_strip_seam_steps`` — the
# EMITTER half of this law — used to carry its own equal-valued copies
# under the banned bare-"seam" spelling (a local radius and step-floor
# pair, the THIRD copy of these numbers); the healer and the census
# (``check_grade._check_strip_seam_tears``) now read ONE definition, so
# the emitter provably sees exactly the pair population the validator
# reports (docs/RULINGS.md, grade-law completeness: emitter and validator
# lockstep, never two copies).  Import-light by construction (stdlib only).
#
# v4 §1 absorbs the FOURTH copy — the healer's own cliff-grade floor —
# and takes the census PAIR PREDICATE itself
# (``seam_guard_allowance_m`` / ``seam_pair_is_tear``), so the
# non-worsening guard's per-neighbour allowance and
# ``check_grade._check_strip_seam_tears`` are computed by ONE function.
from .strip_seam_law import (
    STRIP_SEAM_TEAR_MIN_GRADE,
    STRIP_SEAM_TEAR_MIN_STEP_M,
    STRIP_SEAM_TEAR_RADIUS_M,
    STRIP_SEAM_WALL_STRADDLE_TOL_M,
    seam_guard_allowance_m,
    seam_pair_is_tear,
)

# An adjacent-ground band is a SHALLOW corridor surface (a code-4 runway
# fill falls ≈2.3 m over 75 m, monotonically across many vertices), so a
# single-vertex altitude reversal larger than this is always a
# clip-introduced resample flip on a concave ring, not a real feature —
# ``_declaw_alt_needles`` clamps it to the neighbour mean.  Tighter than
# the runway-end skirt's 3 m needle tolerance because the lateral bands
# are shallower than an end skirt.
_ADJACENT_NEEDLE_TOL_M = 1.5
# Snap-to-bound band (round 2, triangle diet): a clamped band value within
# this of a corridor bound emits the BOUND itself, so near-bound runs are
# piecewise-linear and decimate away instead of tracing DEM jitter.  At
# the emit-quantization noise floor (values round to 0.1 m; the validator
# allows 0.15 m edge noise) — the emitted surface stays in the corridor.
_CORRIDOR_SNAP_TOL_M = 0.15
# Corner-fan resolution: intermediate fan stations are inserted at convex
# ring corners so consecutive normals never differ by more than this (the
# residual chord sagitta at the runway reach, R·(1−cos(θ/2)) ≈ 2.6 m at
# 15° / R=300, is inside one band step of coverage).
_FAN_MAX_STEP_RAD = math.radians(15.0)
# Cross-shape run-end taper seam pin (user 2026-07-10, default ON): suppress
# the daylight bench-in at pavement-PARTITION seams so abutting shapes' terminal
# stations agree on outer depth (no seam notch).  O4_SEAM_TAPER_PIN=0 disables
# it (A/B lever); the validator reads the SAME env so the lockstep pair stays
# aligned.
_SEAM_TAPER_PIN = os.environ.get("O4_SEAM_TAPER_PIN", "1") != "0"
# Slice B stage B3 order 3, SCOPE A — taxiway-end WRAP (Noah ruling
# 2026-07-10, site 60.6972471,-135.0608669; O4_ADJACENT_GROUND_END_WRAP,
# default OFF — new coverage = new terrain output, flips at B4).  The
# terrain-facing probe in ``_station_reference`` skips any station whose
# outward ray lands on an existing shape; at a taxiway end that abuts a
# runway-END skirt that skip halts coverage before the taxiway end.  With
# the wrap ON, a TAXIWAY station whose probe lands ONLY on a
# ``runway_end_skirt`` is NOT skipped (the skirt is the JOIN target, not an
# obstruction): the corridor marches around the taxiway end at the family's
# clearance distance, then the exact ``difference(static_union)`` clip +
# ``_snap_ring_to_static`` land the wrap ring ON the skirt chain verbatim
# (shared vertices; the to_osm skirt-tier consensus supplies the value —
# the same identity/adoption bands read pavement with today).  Runways keep
# the END-edge skip (their skirt law owns them); aprons are unaffected.
# (Round-7 review default ON, Noah 2026-07-11 — judged in-sim with the
# slice-B bundle; env var 0 falls back.)
_END_WRAP = os.environ.get("O4_ADJACENT_GROUND_END_WRAP", "1") == "1"
# Slice B stage B3 order 3, SCOPE B — tunnel-ramp STANDOFF (acceptance
# criterion 6; the ledgered SPJC strip-onto-mouth-ramp tears;
# O4_ADJACENT_GROUND_TUNNEL_STANDOFF, default OFF).  Band construction
# excludes a ``_PAVEMENT_GAP_M`` standoff around tunnel mouth pieces
# (``tunnel_ramp`` sloped rects + the ``retaining_wall`` U-walls the tunnel
# portal emits pre-band) — the building/groundside standoff pattern — so a
# strip never welds onto the steep tunnel-mouth floor.  Object-bridge plates
# (``bridge_trench`` / ``bridge_causeway``) are HARD graph members bands
# treat as pavement and are deliberately NOT stood off.  The block is built
# from ``layout.shapes`` at emit entry, before ``_emit_apron_walls`` appends
# its own ``retaining_wall`` pieces, so apron-edge walls are naturally
# excluded (only pre-existing tunnel walls are captured).  Independently
# flippable from the wrap (they may gate differently at B4).
# (Round-7 review default ON, Noah 2026-07-11 — inert everywhere probed;
# fires only where tunnel ramps emit, e.g. the CYUL mapped-portal class.)
_TUNNEL_STANDOFF = os.environ.get(
    "O4_ADJACENT_GROUND_TUNNEL_STANDOFF", "1") == "1"
# Arc A3 — END-AWARE BENCH PIN (O4_ADJACENT_GROUND_END_PIN, default OFF;
# the VALUE lives in config.py, this is only the module-local binding the
# march reads, so a test can flip it without re-importing config).  A
# runway END-edge station is at depth 0 only because ``_station_reference``
# SKIPS it (the end is skirt / RESA territory) — the daylight bench then
# collapses the lateral wing diagonally into the end corner.  With the pin
# ON the station NEXT to an end-skip run holds its raw scanned depth,
# exactly as a pavement-partition continuation seam does.  See
# ``grade_law.adjacent_ground_end_pin_flags``.
_END_PIN = ADJACENT_GROUND_END_PIN_ENABLED
# Arc A4 — RUNWAY STRIP WIDTH MEASURED FROM THE CENTERLINE
# (O4_STRIP_WIDTH_FROM_CENTERLINE, default OFF; value in config.py).  The
# Annex-14 strip half-width is measured from the runway CENTERLINE, but the
# march spends it as a reach off the pavement EDGE and the emitted runway
# carries apt.dat shoulders — so the band overshoots the strip by the
# shoulder width.  With this ON a runway-family station's caps are clamped
# by ``grade_law.runway_strip_band_width_m``.
_STRIP_WIDTH_FROM_CENTERLINE = STRIP_WIDTH_FROM_CENTERLINE_ENABLED
# OLS handover (docs/specs/obstacle-limitation-surfaces-spec.md): with the
# OLS cut law ON the runway-family lateral CUT stops at the transitional
# surface's handover S instead of marching the zone-3 ceiling to the
# earthwork reach cap.  Read once, like every sibling gate.
from .config import OLS_CUT_ENABLED as _OLS_CUT              # noqa: E402
# BAND RAY OCCLUSION (owner ruling 2026-07-25, "Yes for adjacent ground
# using a ray occlusion, it should stop at pavement"; the rationale and the
# CYXY shapeID 395 diagnosis live in the config block).  The module-local
# binding the two band builders read, so a test can flip it without
# re-importing config.  OFF ⇒ the occlusion limits are all +inf and every
# ``min(..., occ)`` / ``d > occ`` below is a structural no-op —
# byte-identical to the pre-fix march.
from .config import (                                        # noqa: E402
    BAND_RAY_OCCLUSION_ENABLED as _RAY_OCCLUSION)
from .config import (                                        # noqa: E402
    ADJACENT_GROUND_CUT_HALF_CORRIDOR_ENABLED as _CUT_HALF_CORRIDOR)
# APRON WALL CONTINUITY (2026-07-25 diagnosis — see the config block
# ``APRON_WALL_CONTINUITY_ENABLED``).  Module-local binding so a test can
# flip it without re-importing config.  OFF ⇒ ``_emit_apron_walls`` takes
# its pre-fix single-Polygon / no-hysteresis path verbatim.
from .config import (                                        # noqa: E402
    APRON_WALL_CONTINUITY_ENABLED as _APRON_WALL_CONTINUITY)
# APRON WALL SCOPE — pavement adjacency (owner ruling 2026-07-25, lead
# reading; see the config block ``APRON_WALL_SCOPE_ENABLED``).  Kept on a
# gate SEPARATE from the continuity fixes above: this one narrows the LAW's
# scope (and carries a validator mirror), those repair emission mechanics,
# so the owner can back either out without losing the other.
from .config import (                                        # noqa: E402
    APRON_WALL_SCOPE_ENABLED as _APRON_WALL_SCOPE)
# SOLVED-BAND EMIT-SIDE CORRIDOR CLAMP (2026-07-25 diagnosis — see the
# config block ``BAND_CORRIDOR_CLAMP_ENABLED``).  OFF ⇒ the solved
# resampler returns its raw solved value, byte-identical to the pre-fix
# valuation.
from .config import (                                        # noqa: E402
    BAND_CORRIDOR_CLAMP_ENABLED as _BAND_CORRIDOR_CLAMP)
# TILE-SEAM PROLONGATION (owner ruling 2026-07-24 — see the config block
# ``ADJACENT_GROUND_SEAM_PROLONG_ENABLED`` for the full rationale and the
# SPLP measurements).  The module-local bindings the march reads.
_SEAM_PROLONG = ADJACENT_GROUND_SEAM_PROLONG_ENABLED
_SEAM_PROLONG_MAX_M = ADJACENT_GROUND_SEAM_PROLONG_MAX_M
# Value-sourcing half of the prolongation (config
# ``ADJACENT_GROUND_PROLONG_HOST_REF``): a re-homed zone-node host carries
# the station's own frontage altitude as the law reference instead of the
# cut-back corner's.  OFF ⇒ every host shift is 0.0 — the pre-fix values.
_PROLONG_HOST_REF = ADJACENT_GROUND_PROLONG_HOST_REF
# A ring vertex is ON a tile cut-back line within this distance.  ``tile_cut``
# places them EXACTLY on the line; the tolerance only absorbs the local-metre
# <-> lat/lon round trip (micrometres) and emit rounding.
_SEAM_CUTBACK_TOL_M = 0.20
# Floor on |edge direction . tile-line normal|: below it the flanking
# frontage runs (near-)PARALLEL to the tile line and the geometric
# prolongation length diverges — clamped here, then bounded by the recorded
# offcut and the config cap like every other case.
_SEAM_PROLONG_MIN_COS = 0.05
# Halo (m) around the recorded neighbour-tile offcut used when measuring how
# far the pavement really continues: the probe ray runs down the middle of
# the continuing pavement, and this absorbs the 10 m cut gap plus the
# offcut's own cut-back setback so a genuine continuation is never measured
# as zero.  (2 x TILE_CUT_HALF_WIDTH_M + 1 m of slack.)
_SEAM_OFFCUT_HALO_M = 2.0 * TILE_CUT_HALF_WIDTH_M + 1.0
# Cap on the altitude gradient extrapolated onto a prolonged vertex.  The
# steepest lawful airside longitudinal grade is 1.5 %; 2 % leaves headroom
# for a rounding-quantised short flanking edge without letting a degenerate
# edge fling the reference altitude.
_SEAM_PROLONG_MAX_GRADE = 0.02
# CROSSING INFLUENCE ZONE (Phase 1, docs/specs/crossing-terrain-
# ownership.md): every crossing-specific exclusion this module used to
# build itself — the crossing-union branch of the standoff block, the
# road-lane station drop and emit-time lane clip, and the buried-span
# carve-out (O4_ADJACENT_GROUND_WRAP_LANE_EXCLUSION /
# O4_ADJACENT_GROUND_BURIED_BODY_BAND, whose semantics now live in
# ``crossing_terrain``) — is replaced by the ONE zone the pipeline
# publishes pre-solve.  The march drops stations inside it and the
# emitter differences band pieces against it; ``None`` (nothing
# published — no crossings, no depressed road) is byte-inert.
# Lab forensics: O4_ADJACENT_GROUND_DEBUG=1 logs per-shape band counts and
# every dropped piece, for chasing validator coverage findings.
_ADJACENT_DEBUG = os.environ.get("O4_ADJACENT_GROUND_DEBUG") == "1"
# O4_ADJACENT_GROUND_DEBUG_POINTS="x,y;x,y" (local metres): per-shape
# station/coverage decisions near each point, for replaying a validator
# coverage finding against the emitter's exact choices.
_ADJACENT_DEBUG_POINTS: list[tuple[float, float]] = []
for _pair in (os.environ.get("O4_ADJACENT_GROUND_DEBUG_POINTS") or "") \
        .split(";"):
    if "," in _pair:
        _px, _py = _pair.split(",", 1)
        try:
            _ADJACENT_DEBUG_POINTS.append((float(_px), float(_py)))
        except ValueError:
            pass
__all__ = ["emit_adjacent_ground_bands"]

# ── Apparatus hit counters (Slice B stage B3 order 2 instrumentation;
# coordinator ruling 2026-07-11: measure the weld / adoption / seam-taper
# apparatus OFF vs ON admission.  Registry identity is expected to retire
# the two VALUE-AGREEMENT rows — value-changing adoptions and band-corner
# weld snaps — to zero, while the seam-taper pin is FOOTPRINT machinery
# (it pins daylight DEPTHS at pavement-partition seams, it never touches
# a value) and must stay unchanged; if it moves at all, investigate.) ──
_APPARATUS_KEYS = (
    "value_changing_adoptions", "band_corner_weld_snaps",
    "seam_taper_flagged_stations", "solved_exact_variable",
    "solved_row_on", "solved_row_interpolated",
    "solved_beyond_coverage", "solved_analytic_fallback",
    "solved_store_missing_shape", "zone_static_keepout_dropped",
    "static_edge_weld_vertices", "wrap_crossing_zone_excluded_stations",
    # Arc A3: stations the runway-END bench pin flagged (0 with the gate
    # OFF, by construction).  Reported beside the seam-taper row so the
    # two pin populations can be read apart.
    "end_pin_flagged_stations",
    # Arc B1: stations stood down because they face a COLLARED POCKET
    # (0 with nothing collared, by construction).
    "collar_zone_excluded_stations",
    # ENCLAVE LAW (owner 2026-08-07; SCOPING v2, spec
    # docs/specs/enclave-region-law-spec.md).  The keep-out acts on band
    # GEOMETRY, so what is counted is the geometry it took: band rings
    # and wall faces the pocket-region clip REDUCED (0 when no
    # pocket-width region is published, by construction).  It replaces
    # the v1 STATION counter deliberately — a station anchor inside a
    # pocket used to delete the whole row it anchored, including the
    # part marching over WIDE ground the keep-out does not cover
    # (measured at HECA: 11,274 stations, 150,438 m² of Annex 14 §3.4.11-13
    # graded strip removed from regions the keep-out provably does not
    # reach), and a counter of stations cannot see that the loss landed
    # outside its own territory.  An AREA counter can.
    "enclave_zone_clipped_bands",
    "enclave_zone_clipped_walls",
    # RAY OCCLUSION (2026-07-25): stations whose outward march hit
    # pavement and was terminated there (0 with the gate OFF, by
    # construction).
    "band_ray_occluded_stations",
    # EMIT-SIDE CORRIDOR CLAMP (2026-07-25): solved band vertices whose
    # value sat OUTSIDE this shape's own law corridor and was clamped
    # back into it (0 with O4_BAND_CORRIDOR_CLAMP off, by construction).
    # A non-zero count is the cross-shape canonical-variable collision
    # population — see the config block ``BAND_CORRIDOR_CLAMP_ENABLED``.
    "band_corridor_clamped_vertices",
    # APRON WALL SCOPE (owner ruling 2026-07-25): apron frontage stations
    # facing OPEN TERRAIN (no built pavement within
    # ``APRON_WALL_PAVEMENT_ADJACENCY_M``) whose FILL side the ruling
    # leaves ungoverned — no wall, no shoulder band, raw DEM up to the
    # apron edge.  0 with O4_APRON_WALL_SCOPE off, by construction.
    "apron_open_frontage_stations",
    # STRIP PRECEDENCE §1 (O4_STRIP_PRECEDENCE): non-runway-family
    # stations whose GOVERNING LAW was swapped to the strip family
    # because they fall inside the lateral runway strip — the strip
    # corridor law governs that ground, whatever shape's frontage the
    # march started from.  0 with the gate off.
    "strip_law_governed_stations",
    # ABEAM LONGITUDINAL §2 (same gate): emitted band vertices the
    # along-axis Lipschitz clamp actually MOVED (> 1 mm).  0 with the
    # gate off, and 0 on a strip whose ground already complies.
    "strip_longitudinal_clamped_vertices",
    # ABEAM/ARC §A3(a): strip stations the march emitted a band at because
    # the ground breached the strip's LONGITUDINAL law, not the lateral
    # corridor — the trigger term that had no production caller until
    # 2026-08-05.  0 on a strip whose ground is already along-axis lawful.
    "strip_longitudinal_demanded_stations",
)
_APPARATUS_HITS: dict[str, int] = {}
# Largest single clamp magnitude (m) applied by the emit-side corridor
# clamp this emission — reported beside the counter above.  Kept OUT of
# ``_APPARATUS_HITS`` so that table stays integer-valued (the OFF-vs-ON
# retirement report parses it).
_BAND_CLAMP_MAX_DELTA_M = 0.0
# Largest single along-axis longitudinal clamp magnitude (m) applied this
# emission (§2).  Same convention as ``_BAND_CLAMP_MAX_DELTA_M``.
_STRIP_LONGITUDINAL_MAX_DELTA_M = 0.0


def _reset_apparatus_hits():
    global _BAND_CLAMP_MAX_DELTA_M, _STRIP_LONGITUDINAL_MAX_DELTA_M
    _BAND_CLAMP_MAX_DELTA_M = 0.0
    _STRIP_LONGITUDINAL_MAX_DELTA_M = 0.0
    for _hit_key in _APPARATUS_KEYS:
        _APPARATUS_HITS[_hit_key] = 0


_reset_apparatus_hits()

# The emitted role's OSM ref (a terrain-grading overlay, NOT pavement).
_ADJACENT_REF = "adjacent_ground"
_ADJACENT_WALL_REF = "adjacent_ground_wall"
# Minimum emitted band area (m²); smaller freestanding residue is noise.
_MIN_BAND_AREA_M2 = 25.0

# Role → strip family (mirrors grade_law's ``_ADJACENT_*_ROLES`` so the
# emitter and the law agree on which corridor each surface takes).
_RUNWAY_ROLES = (ROLE_RUNWAY, ROLE_RUNWAY_CROSSING)
_TAXIWAY_ROLES = (
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
)
_APRON_ROLES = (ROLE_APRON,)

# APRON WALL SCOPE (owner ruling 2026-07-25).  The roles that count as
# "adjacent PAVEMENT" for the 5 m qualification: every BUILT surface — the
# airside pavement the emitter marches plus the groundside / service /
# tunnel-ramp surfaces that are equally impossible to grade over.  Terrain
# roles are deliberately absent (``graded_strip`` bands, ``retaining_wall``
# faces, the boundary ribbon, clearance shadows and building pads), so the
# emitter (pre-emit) and the validator (post-emit) derive the identical set
# from ``layout.shapes`` — lockstep by construction, exactly as
# ``airside_seam_vertex_keys`` does.
#
# RUNWAY-STRIP WALL LAW (owner ruling 2026-08-01, gate
# ``RUNWAY_STRIP_WALL_LAW_ENABLED``): a runway NEVER qualifies a wall.  The
# owner's law is that runway surroundings grade away smoothly, so counting a
# runway as the "adjacent pavement within 5 m" that makes a vertical face the
# only lawful answer is exactly backwards — the apron↔runway frontage is the
# one place the corridor law MUST be allowed to grade.  Gate OFF keeps the
# runway roles in scope, i.e. byte-identical.
_WALL_SCOPE_PAVEMENT_ROLES = frozenset(
    ((_TAXIWAY_ROLES + _APRON_ROLES) if RUNWAY_STRIP_WALL_LAW_ENABLED
     else (_RUNWAY_ROLES + _TAXIWAY_ROLES + _APRON_ROLES))) | frozenset({
        "groundside_pavement", "service_road", "service_junction",
        "tunnel_ramp",
    })


# How far either side of a corridor's CENTERLINE counts as "on the course"
# for the wall law: enough that a wall lying along the course is caught,
# small enough that a kerbside terrace beside the carriageway is not.
_COURSE_HALO_M = 0.5


def service_corridor_wall_keepout(layout, *, require_gate: bool = True):
    """The union of every SERVICE CORRIDOR's own COURSE — the ground on
    which a terrace / retaining wall is INADMISSIBLE (owner ruling
    2026-08-12b, verbatim: "walls/terraces may not cut across a road's
    course"; "terrace freedom applies to the ground BETWEEN graded
    features, never to the feature's own run").

    THE COURSE IS THE CENTERLINE, NOT THE CARRIAGEWAY.  The ruling forbids
    a wall CUTTING ACROSS the road's run; a terrace standing ALONGSIDE a
    road's edge is the ordinary ground-between-features terrace the
    standing groundside terrace law allows, and a wall crossing the road
    necessarily crosses its centerline.  So the keep-out is the corridor
    COURSES the pipeline stashed (``layout._service_corridor_lines`` —
    apt.dat 1206 routes + linemerged feed chains) plus the emitted
    ``service_road`` rects' own axes, each widened by a hair
    (``_COURSE_HALO_M``) so a wall lying ON the course is caught too.

    The narrower predicate was chosen on the ruling's own words, not on a
    measurement: CYXY builds BYTE-IDENTICALLY under either spelling
    (body_sha 539b6c838531 with the polygon keep-out and with this one),
    so nothing there distinguishes them — but a kerbside terrace 2 m from
    a service junction is inside the road POLYGON's keep-out and outside
    the course's, and refusing it would leave its lot to carry the level
    change itself.

    ``None`` with the gate off or when the layout carries no corridor.
    """
    from .config import SERVICE_CORRIDOR_FREE_END
    from .layout import ROLE_SERVICE_ROAD
    if require_gate and not SERVICE_CORRIDOR_FREE_END:
        return None
    courses: list = []
    courses.extend(ln for ln in
                   (getattr(layout, "_service_corridor_lines", None) or [])
                   if ln is not None and not getattr(ln, "is_empty", True))
    for s in layout.shapes:
        if s.role != ROLE_SERVICE_ROAD:
            continue
        axis = getattr(s, "source_axis", None)
        if axis is not None and not getattr(axis, "is_empty", True):
            courses.append(axis)
    parts: list = []
    for ln in courses:
        try:
            parts.append(ln.buffer(_COURSE_HALO_M, cap_style=2,
                                   join_style=2))
        except _GEOM_EXC:
            continue
    if not parts:
        return None
    try:
        block = unary_union(parts)
    except _GEOM_EXC:
        return None
    if block.is_empty:
        return None
    return block


def runway_strip_wall_keepout(layout, *, require_gate: bool = True):
    """The prepared union of every runway's STRIP FOOTPRINT — the ground on
    which ``ROLE_RETAINING_WALL`` is INADMISSIBLE (owner ruling 2026-08-01;
    the law geometry is ``grade_law.runway_strip_wall_keepout_rings``).
    ``None`` with the gate off, or when the layout carries no runway.
    ``require_gate=False`` builds the footprint regardless — the
    lateral-contiguity law's clause (5) ("the runway-strip footprint law
    supersedes inside strips") needs the SAME geometry under its own gate.

    Built ONCE per emitter pass (three passes emit walls) and derived from
    the EMITTED runway rings grouped by ``ref`` — a tile cut or a runway
    crossing leaves one runway as several ways, and a fragment's own
    principal axis is not the runway's.  ``tools/check_grade`` re-derives
    the identical footprint from the identical rings in its own frame:
    same law function, same grouping, lockstep by construction."""
    if require_gate and not RUNWAY_STRIP_WALL_LAW_ENABLED:
        return None
    groups: dict = {}
    for s in layout.shapes:
        if s.role != ROLE_RUNWAY:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            coords = _open_coords(s.polygon)
        except _GEOM_EXC:
            continue
        if len(coords) < 3:
            continue
        groups.setdefault(getattr(s, "ref", "") or id(s), []).extend(coords)
    rings = []
    for pts in groups.values():
        axis = runway_axis_and_width(pts)
        if axis is None:
            continue
        rings.extend(runway_strip_wall_keepout_rings(
            axis[0], axis[1], axis[2]))
    if not rings:
        return None
    try:
        block = unary_union([Polygon(r) for r in rings])
    except _GEOM_EXC:
        return None
    if block.is_empty:
        return None
    return block


def runway_strip_lateral_zone(layout):
    """The PREPARED LATERAL graded-strip rectangles — the §2
    abeam-longitudinal law's domain (BETWEEN the ends; see
    ``grade_law.runway_strip_lateral_footprint_ring`` for why the end
    corridors are excluded from the CAP while §1's precedence keeps them).
    ``None`` with the gate off or with no runway.

    Same runway grouping and the same law function as
    ``runway_strip_wall_keepout``; only the ring selection differs."""
    if not STRIP_PRECEDENCE_ENABLED:
        return None
    groups: dict = {}
    for s in layout.shapes:
        if s.role != ROLE_RUNWAY:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            coords = _open_coords(s.polygon)
        except _GEOM_EXC:
            continue
        if len(coords) < 3:
            continue
        groups.setdefault(getattr(s, "ref", "") or id(s), []).extend(coords)
    rings = []
    for pts in groups.values():
        axis = runway_axis_and_width(pts)
        if axis is None:
            continue
        ring = runway_strip_lateral_footprint_ring(
            axis[0], axis[1], axis[2])
        if ring:
            rings.append(ring)
    if not rings:
        return None
    try:
        block = unary_union([Polygon(r) for r in rings])
        if block.is_empty:
            return None
        return prep(block)
    except _GEOM_EXC:
        return None


def apron_wall_pavement_adjacency_index(layout):
    """``(STRtree, polys, owner_ids)`` over every BUILT pavement shape, or
    ``None`` — the shared geometry source for the apron-wall scope ruling
    (owner 2026-07-25; see ``config.APRON_WALL_SCOPE_ENABLED``).

    Built once per emission / per validation, never per shape: the test it
    serves runs on every apron station of the airport.  ``owner_ids`` holds
    ``id(shape)`` per polygon so a shape is never counted as adjacent to
    ITSELF."""
    from shapely.strtree import STRtree
    polys = []
    owners = []
    for s in layout.shapes:
        if s.role not in _WALL_SCOPE_PAVEMENT_ROLES:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        polys.append(s.polygon)
        owners.append(id(s))
    if not polys:
        return None
    try:
        return (STRtree(polys), polys, owners)
    except _GEOM_EXC:
        return None


def apron_wall_frontage_qualifier(shape, index):
    """``qualifies(sx, sy) -> bool`` for one APRON shape, or ``None`` when
    the scope gate is off / there is nothing to test against (caller then
    governs every station exactly as before — byte-identical).

    True when ANOTHER built pavement shape lies within
    ``APRON_WALL_PAVEMENT_ADJACENCY_M`` of the station: the owner's "there's
    adjacent pavement within 5 m, then we need a wall".  False = OPEN
    TERRAIN frontage, which the ruling leaves ungoverned on the FILL side
    (no wall, no shoulder band; the raw DEM grades up to the apron edge).

    Cost discipline (the ray-occlusion / collar standard): one STRtree box
    query plus a distance test per DISTINCT station, memoized on the
    millimetre vertex key so the march and the wall pass — which walk the
    same station list — pay for it once."""
    if not _APRON_WALL_SCOPE or index is None:
        return None
    from shapely.geometry import box as _box
    tree, polys, owners = index
    r = APRON_WALL_PAVEMENT_ADJACENCY_M
    me = id(shape)
    cache: dict[tuple[int, int], bool] = {}

    def qualifies(sx, sy):
        key = _vertex_key(sx, sy)
        hit = cache.get(key)
        if hit is not None:
            return hit
        p = Point(sx, sy)
        hit = False
        try:
            for gi in tree.query(_box(sx - r, sy - r, sx + r, sy + r)):
                if owners[gi] == me:
                    continue
                if polys[gi].distance(p) <= r:
                    hit = True
                    break
        except _GEOM_EXC:
            hit = True     # degrade toward the pre-ruling behaviour
        cache[key] = hit
        return hit

    return qualifies


def airside_seam_vertex_keys(layout):
    """Millimetre vertex keys shared between TWO OR MORE airside pavement
    shapes — the CONTINUATION SEAMS where one shape's terrain-facing frontage
    hands off to an abutting shape (user 2026-07-10, cross-shape run-end
    taper).  A band station adjacent to one of these corners sits at a run
    boundary that exists because of the pavement PARTITION, not because the
    frontage ends, so the daylight bench-in is suppressed there (see
    ``grade_law.adjacent_ground_supported_depths``).

    Computed over the SAME airside pavement roles the emitter marches
    (``_RUNWAY_ROLES + _TAXIWAY_ROLES + _APRON_ROLES`` ==
    ``clearance._AIRSIDE_PAVEMENT_ROLES``); the emitted ``graded_strip`` bands
    are NOT counted, so the emitter (pre-emit) and the validator (post-emit)
    derive the identical seam set — lockstep by construction.  A shape's ring
    is de-duplicated first so its own closing vertex is not miscounted as a
    second shape."""
    from collections import Counter
    in_scope = _RUNWAY_ROLES + _TAXIWAY_ROLES + _APRON_ROLES
    counts: "Counter[tuple[int, int]]" = Counter()
    for s in layout.shapes:
        if s.role not in in_scope:
            continue
        if s.polygon is None or s.polygon.is_empty \
                or s.polygon.geom_type != "Polygon":
            continue
        try:
            ring = list(s.polygon.exterior.coords)[:-1]
        except _GEOM_EXC:
            continue
        for k in {_vertex_key(vx, vy) for vx, vy in ring}:
            counts[k] += 1
    return {k for k, c in counts.items() if c >= 2}


def _dedup_ring(ring, alts):
    """Drop consecutive duplicate ring coordinates, keeping any aligned
    altitude list in step.  With the inner boundary AT the pavement edge
    (d0 = 0) every corner-fan station shares the corner coordinate, so a
    fan's inner row degenerates to one point — deduplicated, the band is
    the valid fan SECTOR polygon instead of a self-touching ring."""
    if not ring:
        return ring, alts
    kept_ring = [ring[0]]
    kept_alts = [alts[0]] if alts else []
    for i in range(1, len(ring)):
        if ring[i] == kept_ring[-1]:
            continue
        kept_ring.append(ring[i])
        if alts:
            kept_alts.append(alts[i])
    if len(kept_ring) > 1 and kept_ring[0] == kept_ring[-1]:
        kept_ring.pop()
        if kept_alts:
            kept_alts.pop()
    return kept_ring, kept_alts


def _repair_self_lenses(g):
    """Split near-degenerate self-pinches in a band polygon.

    A band rail snapped onto a static chain can double back over its
    OWN other rail sub-µm apart (thin cut residue collapsed onto the
    runway line) — an in-ring near-parallel lens Triangle4XP Ruppert-
    refines catastrophically (the CYXY 60.717 hotspot: 182k triangles
    from ONE pinched ring).  Insert the ring's own vertices into edges
    they graze (≤5 mm), forcing the pinch into an EXACT self-touch
    that ``buffer(0)`` resolves into clean lobes; the zero-width
    excursion vanishes, the real lobe keeps its adopted chain."""
    try:
        ring = list(g.exterior.coords)[:-1]
    except _GEOM_EXC:
        return [g]
    n = len(ring)
    if n < 4:
        return [g]
    out: list[tuple[float, float]] = []
    changed = False
    for i in range(n):
        ax, ay = ring[i]
        bx, by = ring[(i + 1) % n]
        out.append((ax, ay))
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            continue
        L = math.sqrt(L2)
        ins = []
        for j in range(n):
            if j == i or j == (i + 1) % n:
                continue
            px, py = ring[j]
            t = ((px - ax) * dx + (py - ay) * dy) / L2
            if t <= 0.0 or t >= 1.0:
                continue
            if t * L < 0.005 or (1.0 - t) * L < 0.005:
                continue
            perp = abs((px - ax) * dy - (py - ay) * dx) / L
            if perp < 0.005:
                ins.append((t, (px, py)))
        for _t, p in sorted(ins):
            if out[-1] != p:
                out.append(p)
                changed = True
    if not changed:
        return [g]
    try:
        rep = Polygon(out, [list(h.coords) for h in g.interiors])
        if not rep.is_valid:
            rep = rep.buffer(0)
        if rep.geom_type == "Polygon":
            parts = [rep]
        else:
            parts = [q for q in getattr(rep, "geoms", [])
                     if q.geom_type == "Polygon"]
        parts = [q for q in parts if not q.is_empty]
        return parts or [g]
    except _GEOM_EXC:
        return [g]


# Sentinel occlusion limit — "this ray is clear all the way to the cap".
# Every consumer spends it through ``min(..., occ)`` / ``d > occ``, so the
# gate-OFF path (which returns nothing but this value) is byte-identical.
_OCCLUSION_CLEAR = float("inf")


def _station_occlusion_limits(edge_stations, outwards, band_caps, step,
                              prep_static, wrap_skirt_prep=None):
    """RAY OCCLUSION — the per-station maximum band depth measured through
    FREE GROUND ONLY (gate ``O4_BAND_RAY_OCCLUSION``; owner ruling
    2026-07-25: "Yes for adjacent ground using a ray occlusion, it should
    stop at pavement").

    THE LAW: a lateral band's outward reach is measured through free ground
    only — a station's outward march TERMINATES at the first sample
    distance whose point falls inside the static pavement union, and the
    station's band depth becomes the LAST FREE-GROUND sample before that
    hit.  Beyond an occluding pavement the ground is that pavement's own
    frontage: its bands march outward from ITS edge and cover it, so
    stopping here leaves nothing ungoverned (and the emitted band never
    wraps a foreign pavement's corner — the CYXY shapeID 395 defect, where
    junction 129's deep cut slab marched straight through apron 132 +
    junction 131 because the lidar reads the built apron bench as terrain
    needing a cut, so daylight never closed).

    Returns one float per station — the largest lawful depth, or
    ``_OCCLUSION_CLEAR`` (+inf) where that ray is clear; a station whose
    FIRST sample is already occluded gets 0.0 (no band at all).  Returns
    ``None`` when NOTHING is occluded (and always with the gate off), which
    is the builders' structural no-op path: byte-identical.

    Sampled on the SAME ``k * step`` grid the two band builders march
    (``d = min(cap, k * step)``, ``k = 1 … ceil(cap / step)``), with
    ``band_caps`` the per-station MAX of the fill and cut caps so one march
    serves both directions.  (The cut builder samples one millimetre
    inside its cap; that 1e-3 is immaterial to a containment test and is
    deliberately not reproduced here — one march, one law.)

    ``wrap_skirt_prep`` — the taxiway-end WRAP exemption, verbatim from
    ``_station_reference_ex``: a runway-END skirt is the corridor's JOIN
    target, not an obstruction, so a hit that lies on the skirt does not
    occlude.  ``None`` (runways, aprons, wrap gate OFF): every static hit
    occludes.

    BUILD-TIME: the naive form (one prepared ``contains`` + one ``Point``
    per sample) measured 2.45 s per 700k samples — SPJC scale — against
    a 0.6 s budget, so the whole station x sample grid is tested in ONE
    vectorized ``shapely.contains_xy`` call against the same prepared
    union (measured 0.084 s for the same 700k samples, a 29x cut, and
    exactly equivalent by construction: ``contains_xy(g, x, y)`` IS
    ``g.contains(Point(x, y))``).  This is the collar-zone guard's
    precedent (450 ms naive -> 35 ms guarded) taken to the same standard.
    """
    n = len(edge_stations)
    if not _RAY_OCCLUSION or n == 0 or prep_static is None:
        return None
    static = getattr(prep_static, "context", None)
    if static is None or static.is_empty:
        return None
    import numpy as _np
    from shapely import contains_xy as _contains_xy
    caps = _np.asarray([float(c) for c in band_caps], dtype=float)
    cap_max = float(caps.max()) if n else 0.0
    if not (cap_max > 0.0):
        return None
    kmax = max(1, int(math.ceil(cap_max / float(step))))
    ks = _np.arange(1, kmax + 1, dtype=float)[None, :]
    # d[i, j] and the per-station validity mask: k runs 1 … ceil(cap/step),
    # i.e. exactly the builders' ``nst`` (equivalently (k-1)*step < cap).
    dgrid = _np.minimum(caps[:, None], ks * float(step))
    valid = (ks - 1.0) * float(step) < caps[:, None]
    seeds = _np.asarray([(float(sx), float(sy))
                         for sx, sy in edge_stations], dtype=float)
    norms = _np.asarray([(float(nx), float(ny))
                         for nx, ny in outwards], dtype=float)
    xs = seeds[:, 0][:, None] + norms[:, 0][:, None] * dgrid
    ys = seeds[:, 1][:, None] + norms[:, 1][:, None] * dgrid
    try:
        hit = _contains_xy(static, xs, ys) & valid
    except _GEOM_EXC:
        return None
    if wrap_skirt_prep is not None:
        skirt = getattr(wrap_skirt_prep, "context", None)
        if skirt is not None and not skirt.is_empty:
            try:
                hit &= ~_contains_xy(skirt, xs, ys)
            except _GEOM_EXC:
                pass
    any_hit = hit.any(axis=1)
    if not any_hit.any():
        return None
    limits = [_OCCLUSION_CLEAR] * n
    first = hit.argmax(axis=1)
    for i in _np.nonzero(any_hit)[0]:
        j = int(first[i])
        # The last FREE-GROUND sample before the hit (0.0 when the very
        # first sample is already inside pavement).
        limits[int(i)] = float(dgrid[i, j - 1]) if j > 0 else 0.0
    _APPARATUS_HITS["band_ray_occluded_stations"] += int(any_hit.sum())
    return limits


def _build_cut_bands(edge_stations, edge_alts, outwards, band_caps,
                     ceiling_offset, band_edges, trigger, step,
                     sample_dem, is_ring_vertex=None,
                     at_continuation_seam=None, zone_collect=None,
                     force_full_reach=False, occlusion=None,
                     longitudinal_demand=None):
    """CUT-direction mirror of ``clearance._build_filled_skirts``.

    At each station a CEILING sits at ``edge_alt + ceiling_offset(d)``
    (the corridor's upper bound, a piecewise-CONTINUOUS function of the
    lateral distance ``d`` — negative in the graded zones under the
    enforce-fully mandate, rising in the ungraded zone).  Terrain ABOVE
    the ceiling by more than ``trigger`` is cut down to it; the cut
    DAYLIGHTS where the ceiling meets the DEM, capped at ``band_caps[i]``
    (the family reach).  Cut-only — flat-or-below terrain is left to the
    fill twin.

    Emitted as ABUTTING BANDS split at ``band_edges`` (the law's zone
    breakpoints), so within a band the ceiling is one LINEAR piece and a
    two-row ring renders it exactly (no chord sag across a zone kink).
    Adjacent bands share their boundary row (same positions, same rounded
    altitudes) → one continuous surface.  Returns ``(ring_open,
    alts_open)`` pairs.

    ``is_ring_vertex`` (per station, aligned with ``edge_stations``; None =
    off) thins the d0 == 0 WELD row to the pavement-chain subsequence: at
    the edge the inner altitude IS the pavement value, which interpolates
    identically along the ring's own straight edges, so a mid-edge station
    adds a node (a T-vertex the conformance pass must insert into the
    pavement ring) without adding information.  Only ring vertices +
    each run's surviving endpoints are kept on that row; the outer row and
    every d0 > 0 row keep full station density.

    ``occlusion`` (per station, aligned with ``edge_stations``; None = off,
    byte-identical) — RAY OCCLUSION (``_station_occlusion_limits``, gate
    ``O4_BAND_RAY_OCCLUSION``): the station's maximum depth through FREE
    GROUND, i.e. the last sample before its outward ray enters pavement.
    The scan STOPS there, the daylight depth is clamped to it, and so is
    the widened taper neighbour's row — no band vertex ever lands beyond an
    occluding pavement (owner ruling 2026-07-25; CYXY shapeID 395).

    ``longitudinal_demand`` (per station, aligned; None = off,
    byte-identical) — §A3(a) THE OTHER TRIGGER TERM.  The scan above is
    LATERAL only: it asks whether the ground at depth ``d`` leaves the
    corridor at THIS station.  Ground that sits inside the corridor at
    every depth but breaches the strip's own LONGITUDINAL slope / arc law
    against its NEIGHBOURING stations was therefore never emitted, so the
    §2 clamp never saw it and the validator read it on raw DEM.  A station
    the longitudinal predicate demands is obstructed to its full cap, so
    the band exists and the clamp shapes it.  See
    ``_strip_longitudinal_demand``.
    """
    n = len(edge_stations)
    outer: list[float] = [0.0] * n
    obstructed: list[bool] = [False] * n
    cap_max = 0.0
    for i, (sx, sy) in enumerate(edge_stations):
        ref = edge_alts[i]
        if ref is None:
            continue
        nx, ny = outwards[i]
        cap = band_caps[i]
        if cap <= _PAVEMENT_GAP_M:
            continue
        cap_max = max(cap_max, cap)
        nst = max(1, int(math.ceil(cap / step)))
        # RAY OCCLUSION: +inf with the gate off, so every ``min``/``>``
        # below is a structural no-op there.
        occ = _OCCLUSION_CLEAR if occlusion is None else occlusion[i]
        last = 0.0
        for k in range(1, nst + 1):
            # Clamp INSIDE the cap: at exactly d == reach the corridor is
            # ungoverned (ceiling None) and the sample would be skipped,
            # leaving terrain in the last (reach − step, reach) ring
            # unprotected — the validator samples reach − 1e-3 and flags
            # it (CYXY round-2 addendum findings at d ≈ reach).
            d = min(cap - 1e-3, k * step)
            if d > occ:
                # RAY OCCLUSION: pavement stands in the ray — the march
                # terminates here and every deeper sample belongs to the
                # occluder's own frontage, not this band's.
                break
            co = ceiling_offset(d)
            if co is None:      # unbounded up at/beyond the reach — no cut
                continue
            ceil = ref + co
            dd = sample_dem(sx + nx * d, sy + ny * d)
            if dd is not None and dd > ceil + trigger:
                last = d
        if force_full_reach or (longitudinal_demand is not None
                                and longitudinal_demand[i]):
            # Full-extent coverage grid (ADJACENT_GROUND_FULL_EXTENT_
            # COVERAGE): obstruct every stationed edge to the whole family
            # reach regardless of the worst-case terrain trigger, so the
            # staged zone-row grid bounds any solved-edge cut the emit
            # re-march produces (over-coverage = unused solved variables).
            # Occlusion binds the staged grid too, so the pre-solve
            # construct and the emit re-march bound the SAME ground.
            # §A3(a): a longitudinally-demanded station takes the same
            # full-cap obstruction — the abeam/arc law governs the whole
            # graded cross-section at that station, not a sliver of it.
            last = min(cap - 1e-3, occ)
        if last > 0.0:
            obstructed[i] = True
            outer[i] = min(cap - 1e-3, last + step, occ)
    if not any(obstructed):
        return []
    # DAYLIGHT slope-limit (grade_law.adjacent_ground_supported_depths, user
    # 2026-07-09): couple the independently-scanned per-station depths so the
    # daylight line benches along the frontage — an isolated deep ray no
    # neighbour corroborates is clamped to a shallow benched entry instead of
    # a knife-slot blade (CYXY 417).  A station whose clamped depth falls to
    # <= a slab's d0 simply drops out of that slab's runs via the
    # ``outer[i] > d0`` tests below (``obstructed[i]`` stays True, but the run
    # membership test already gates on the clamped ``outer``).  Fan stations
    # share the corner coordinate (dist = 0), so a fan ray earns no allowance
    # and is suppressed to the corner's depth.  Continuation-seam terminal
    # stations (``at_continuation_seam``) are pinned to their raw depth so the
    # daylight line stays continuous across a pavement partition (user
    # 2026-07-10; see grade_law).
    outer = adjacent_ground_supported_depths(
        outer, edge_stations, at_continuation_seam)
    # Inner boundary AT the pavement edge (d = 0): the band WELDS to the
    # pavement ring it grades off (user ruling 2026-07-09 — no standoff
    # gap; a 1 m groove of raw DEM rendered as a knife-edge wall/trench
    # along the pavement at CYXY).  Weld-row values are the pavement
    # edge values themselves (corridor at d = 0 is [0, 0]).
    edges = [0.0]
    for b in sorted(band_edges):
        if 1.0 < b < cap_max - 1.0:
            edges.append(float(b))
    edges.append(cap_max)

    out: list[tuple[list, list]] = []
    for b in range(len(edges) - 1):
        d0, d1 = edges[b], edges[b + 1]
        idx = [i for i in range(n) if obstructed[i] and outer[i] > d0]
        if not idx:
            continue
        runs: list[list[int]] = []
        cur = [idx[0]]
        for j in idx[1:]:
            # Bridge by PHYSICAL distance, not index count: on a ring
            # with long edges one station index can be 50-150 m from
            # the next, and an index-gap bridge spans that whole
            # unobstructed frontage as a spike band far beyond the
            # graded corridor (CYXY shapeIDs 447-449, user 2026-07-09).
            jx, jy = edge_stations[j]
            cx_, cy_ = edge_stations[cur[-1]]
            if (j - cur[-1] <= 2
                    and math.hypot(jx - cx_, jy - cy_) <= 2.5 * step):
                cur.append(j)
            else:
                runs.append(cur)
                cur = [j]
        runs.append(cur)
        for run in runs:
            i0, i1 = run[0], run[-1]
            # Widen EVERY band's runs by one station each side (the skirt
            # widens only its first band): the lateral law is a COVERAGE
            # mandate, and a deep band ending exactly at its last
            # obstructed station leaves the half-station wedge past the
            # run end out-of-corridor and ungraded (the round-2 addendum
            # coverage class).  The widened neighbour tapers to d0+step.
            lo = max(0, i0 - 1)
            hi = min(n - 1, i1 + 1)
            # The d0 == 0 weld row uses EXISTING pavement ring vertices
            # ONLY (user ruling 2026-07-09: grading shapes never create
            # a node on a pavement edge — a mid-edge value is the lerp
            # between pavement vertices, identical on both sides by
            # definition).  A segment whose stations include no ring
            # vertex EXTENDS to the nearest bracketing ring-vertex
            # stations; the outer row keeps every surviving station.
            thin_inner = d0 == 0.0 and is_ring_vertex is not None
            inner_row: list[tuple[int, tuple, float, bool]] = []
            outer_pts, outer_alts = [], []
            # Zone-row provenance (Slice B stage B3 order 2): (station
            # index, lateral depth) aligned 1:1 with ``outer_pts`` (the
            # loop below appends both in lockstep, and the outer-jump
            # flush fires BEFORE appending) — the free-variable grid the
            # pre-solve constructor admits to the solver.  ``zone_collect``
            # None (the default, and every post-solve caller): dead lists,
            # byte-identical geometry.
            outer_prov: list[tuple[int, float]] = []

            def _ring_vertex_entry(from_i, direction):
                """Nearest ring-vertex station outward of ``from_i``
                with a usable reference — the weld chain's extension
                point (an EXISTING pavement vertex)."""
                j = from_i + direction
                for _ in range(64):
                    if j < 0 or j >= n:
                        return None
                    if is_ring_vertex[j] and edge_alts[j] is not None:
                        co0_ = ceiling_offset(d0)
                        if co0_ is None:
                            return None
                        sx_, sy_ = edge_stations[j]
                        return (j, (sx_, sy_),
                                round(float(edge_alts[j] + co0_), 1),
                                True)
                    j += direction
                return None

            def _flush_segment():
                if not inner_row:
                    return
                if zone_collect is not None:
                    # Collect BEFORE the thin-inner mutations below: the
                    # d0 == 0 inner (weld) row is pavement, never a zone
                    # row — the collector drops it; every d0 > 0 row and
                    # every outer row is free-variable grid.
                    zone_collect(
                        d0,
                        [(e[0], e[1][0], e[1][1]) for e in inner_row],
                        [(pi, px, py, pd)
                         for (px, py), (pi, pd)
                         in zip(outer_pts, outer_prov)])
                if thin_inner:
                    kept = [e for e in inner_row if e[3]]
                    if not kept or kept[0][0] != inner_row[0][0]:
                        ext = _ring_vertex_entry(inner_row[0][0], -1)
                        if ext is not None:
                            inner_row.insert(0, ext)
                        else:
                            inner_row[0] = (inner_row[0][0],
                                            inner_row[0][1],
                                            inner_row[0][2], True)
                    if not kept or kept[-1][0] != inner_row[-1][0]:
                        ext = _ring_vertex_entry(inner_row[-1][0], 1)
                        if ext is not None:
                            inner_row.append(ext)
                        else:
                            inner_row[-1] = (inner_row[-1][0],
                                             inner_row[-1][1],
                                             inner_row[-1][2], True)
                else:
                    inner_row[0] = (inner_row[0][0], inner_row[0][1],
                                    inner_row[0][2], True)
                    inner_row[-1] = (inner_row[-1][0], inner_row[-1][1],
                                     inner_row[-1][2], True)
                inner_pts = [p for _i, p, _a, k in inner_row if k]
                inner_alts = [a for _i, _p, a, k in inner_row if k]
                if len(inner_pts) >= 2:
                    ring, alts = _dedup_ring(
                        inner_pts + outer_pts[::-1],
                        inner_alts + outer_alts[::-1])
                    if len(ring) >= 3:
                        out.append((ring, alts))
                inner_row.clear()
                outer_pts.clear()
                outer_alts.clear()
                outer_prov.clear()

            for i in range(lo, hi + 1):
                ref = edge_alts[i]
                if ref is None:
                    # Taper neighbour beyond a skipped station: borrow the
                    # run-end station's edge altitude (the skirt's own
                    # short-run rescue).
                    if i < i0:
                        ref = edge_alts[i0]
                    elif i > i1:
                        ref = edge_alts[i1]
                    if ref is None:
                        continue
                nx, ny = outwards[i]
                if outer[i] > d0:
                    off = min(d1, outer[i])
                else:
                    off = min(d1, d0 + step)    # widened taper neighbour
                # The ceiling is unbounded exactly AT the reach; keep the
                # outer row a hair inside so it stays finite.
                off = min(off, cap_max - 1e-3)
                # RAY OCCLUSION also binds the WIDENED taper neighbour: its
                # ``d0 + step`` row is not scanned, so without this a taper
                # station standing against pavement would still place an
                # outer vertex inside it (+inf off-gate — no-op).
                if occlusion is not None:
                    off = min(off, occlusion[i])
                if off <= d0:
                    continue
                co0 = ceiling_offset(d0)
                co1 = ceiling_offset(off)
                if co0 is None or co1 is None:
                    continue
                sx, sy = edge_stations[i]
                ix, iy = sx + nx * d0, sy + ny * d0
                ox, oy = sx + nx * off, sy + ny * off
                # OUTER-JUMP FLUSH (user in-sim report 2026-07-09,
                # CYXY shapeIDs 447-449): at a corner FAN adjacent to
                # a skipped sweep (runway-end rays), two surviving
                # rays sit at index gap 1 and station distance 0 —
                # both bridge tests pass — while their OUTER points
                # land 100-220 m apart, and the ring chords straight
                # across the un-graded end zone as a spike triangle.
                # Any outer jump beyond 4 stations closes the ring;
                # the next station starts a fresh one.
                if outer_pts and math.hypot(
                        ox - outer_pts[-1][0],
                        oy - outer_pts[-1][1]) > 4.0 * step:
                    _flush_segment()
                outer_pts.append((ox, oy))
                outer_alts.append(round(float(ref + co1), 1))
                outer_prov.append((i, float(off)))
                keep = (not thin_inner) or bool(is_ring_vertex[i])
                inner_row.append((i, (ix, iy),
                                  round(float(ref + co0), 1), keep))
            _flush_segment()
    return out


def _build_fill_bands(edge_stations, edge_alts, outwards, band_caps,
                      floor_depth, band_edges, trigger, step, sample_dem,
                      is_ring_vertex=None, at_continuation_seam=None,
                      zone_collect=None, force_full_reach=False,
                      occlusion=None, longitudinal_demand=None):
    """FILL-direction band geometry — clearance._build_filled_skirts,
    inline-duplicated MINIMALLY (flagged for the cleanup slice) with two
    lateral-law differences the shared skirt builder must not inherit:

      * runs widen by one taper station in EVERY band (the skirt widens
        only its first band; a deep lateral band ending exactly at its
        last obstructed station leaves the half-station wedge past the
        run end out-of-corridor — the round-2 addendum coverage class);
      * ring altitudes are NOT computed (returned empty): the emitter
        values every vertex through the corridor-clamp resampler, so the
        builder's ``max(floor, DEM)`` skirt-lift rows would be dead work
        (and are the round-2 UNLAWFUL value rule besides).

    Same contract otherwise: ``(ring_open, alts_open)`` pairs, abutting
    bands split at ``band_edges``, daylight at the floor∧DEM meeting.

    ``is_ring_vertex`` thins the d0 == 0 weld row to ring vertices + run
    endpoints exactly as in ``_build_cut_bands`` (see there).

    ``occlusion`` — RAY OCCLUSION, the cut twin's verbatim (see there):
    the march terminates at the first pavement hit and the depth (and the
    widened taper neighbour's row) is clamped to the last free-ground
    sample.  None = off, byte-identical.

    ``longitudinal_demand`` — §A3(a), the cut twin's verbatim (see there):
    a station whose ground conforms LATERALLY but breaches the strip's own
    longitudinal slope / arc law against its neighbours is obstructed to
    its full cap, so the band exists and the §2 clamp can shape it.
    """
    n = len(edge_stations)
    outer: list[float] = [0.0] * n
    dropped: list[bool] = [False] * n
    cap_max = 0.0
    for i, (sx, sy) in enumerate(edge_stations):
        ref = edge_alts[i]
        if ref is None:
            continue
        nx, ny = outwards[i]
        cap = band_caps[i]
        if cap <= _PAVEMENT_GAP_M:
            continue
        cap_max = max(cap_max, cap)
        nst = max(1, int(math.ceil(cap / step)))
        occ = _OCCLUSION_CLEAR if occlusion is None else occlusion[i]
        last = 0.0
        for k in range(1, nst + 1):
            d = min(cap, k * step)
            if d > occ:
                break               # RAY OCCLUSION (see the cut twin)
            _fd = floor_depth(d)
            if _fd is None:
                # NO FLOOR AT THIS DEPTH — the corridor is open downward,
                # so no depth of terrain below the edge is unlawful and
                # there is nothing to fill.  Always true beyond the
                # graded width; true from the EDGE under a family W2
                # retired (reg-set §5.1 T2/T3/T5 — the apron surround and
                # the service-road shadow), which is exactly the drape.
                # ``break``, not ``continue``: the floor only ever OPENS
                # with distance, so no larger ``d`` can demand fill.
                break
            floor = ref - _fd
            dd = sample_dem(sx + nx * d, sy + ny * d)
            if dd is not None and dd < floor - trigger:
                last = d
        if force_full_reach or (longitudinal_demand is not None
                                and longitudinal_demand[i]):
            # Full-extent coverage grid (see _build_cut_bands): drop the
            # whole reach so the fill zone-row grid bounds any solved-edge
            # fill the emit re-march produces.  §A3(a) demanded stations
            # take the same full-cap treatment (see the cut twin).
            last = min(cap, occ)
        if last > 0.0:
            dropped[i] = True
            outer[i] = min(cap, last + step, occ)
    if not any(dropped):
        return []
    # DAYLIGHT slope-limit — the fill twin of the cut clamp (see
    # _build_cut_bands): bench the fill daylight line along the frontage so an
    # isolated deep fill ray no neighbour corroborates drops out of the deep
    # slabs' runs via the ``outer[i] > d0`` tests below (``dropped[i]`` stays
    # True; the run membership already gates on the clamped ``outer``).
    # Continuation-seam terminal stations are pinned (see _build_cut_bands).
    outer = adjacent_ground_supported_depths(
        outer, edge_stations, at_continuation_seam)
    # Inner boundary AT the pavement edge — the fill welds to the ring
    # (see _build_cut_bands; same user ruling).
    edges = [0.0]
    for b in sorted(band_edges):
        if 1.0 < b < cap_max - 1.0:
            edges.append(float(b))
    edges.append(cap_max)

    out: list[tuple[list, list]] = []
    for b in range(len(edges) - 1):
        d0, d1 = edges[b], edges[b + 1]
        idx = [i for i in range(n) if dropped[i] and outer[i] > d0]
        if not idx:
            continue
        runs: list[list[int]] = []
        cur = [idx[0]]
        for j in idx[1:]:
            # Physical-distance bridge (see the cut twin): an index
            # bridge on long ring edges mints spike bands.
            jx, jy = edge_stations[j]
            cx_, cy_ = edge_stations[cur[-1]]
            if (j - cur[-1] <= 2
                    and math.hypot(jx - cx_, jy - cy_) <= 2.5 * step):
                cur.append(j)
            else:
                runs.append(cur)
                cur = [j]
        runs.append(cur)
        for run in runs:
            i0, i1 = run[0], run[-1]
            lo = max(0, i0 - 1)
            hi = min(n - 1, i1 + 1)
            # The d0 == 0 weld row thins to the pavement-chain subsequence
            # (see _build_cut_bands); the outer row keeps full density.
            thin_inner = d0 == 0.0 and is_ring_vertex is not None
            inner_row: list[tuple[int, tuple[float, float], bool]] = []
            outer_pts: list[tuple[float, float]] = []
            # Zone-row provenance — see ``_build_cut_bands``.
            outer_prov: list[tuple[int, float]] = []

            def _ring_vertex_point(from_i, direction):
                # Nearest ring-vertex station outward of ``from_i`` —
                # the weld chain extends to an EXISTING pavement vertex
                # (user ruling 2026-07-09: never create a node on a
                # pavement edge).
                j = from_i + direction
                for _ in range(64):
                    if j < 0 or j >= n:
                        return None
                    if is_ring_vertex[j] and edge_alts[j] is not None:
                        return (j, edge_stations[j], True)
                    j += direction
                return None

            def _flush_segment():
                if not inner_row:
                    return
                if zone_collect is not None:
                    # See ``_build_cut_bands``: collect before the
                    # thin-inner mutations; the collector drops the
                    # d0 == 0 (pavement weld) inner row itself.
                    zone_collect(
                        d0,
                        [(e[0], e[1][0], e[1][1]) for e in inner_row],
                        [(pi, px, py, pd)
                         for (px, py), (pi, pd)
                         in zip(outer_pts, outer_prov)])
                if thin_inner:
                    kept = [e for e in inner_row if e[2]]
                    if not kept or kept[0][0] != inner_row[0][0]:
                        ext = _ring_vertex_point(inner_row[0][0], -1)
                        if ext is not None:
                            inner_row.insert(0, ext)
                        else:
                            inner_row[0] = (inner_row[0][0],
                                            inner_row[0][1], True)
                    if not kept or kept[-1][0] != inner_row[-1][0]:
                        ext = _ring_vertex_point(inner_row[-1][0], 1)
                        if ext is not None:
                            inner_row.append(ext)
                        else:
                            inner_row[-1] = (inner_row[-1][0],
                                             inner_row[-1][1], True)
                else:
                    inner_row[0] = (inner_row[0][0], inner_row[0][1],
                                    True)
                    inner_row[-1] = (inner_row[-1][0], inner_row[-1][1],
                                     True)
                inner_pts = [p for _i, p, k in inner_row if k]
                if len(inner_pts) >= 2:
                    ring, _ = _dedup_ring(
                        inner_pts + outer_pts[::-1], [])
                    if len(ring) >= 3:
                        out.append((ring, []))
                inner_row.clear()
                outer_pts.clear()
                outer_prov.clear()

            for i in range(lo, hi + 1):
                ref = edge_alts[i]
                if ref is None:
                    if i < i0:
                        ref = edge_alts[i0]
                    elif i > i1:
                        ref = edge_alts[i1]
                    if ref is None:
                        continue
                nx, ny = outwards[i]
                if outer[i] > d0:
                    off = min(d1, outer[i])
                else:
                    off = min(d1, d0 + step)    # widened taper neighbour
                # RAY OCCLUSION binds the widened taper neighbour too —
                # see the cut twin (+inf off-gate — no-op).
                if occlusion is not None:
                    off = min(off, occlusion[i])
                if off <= d0:
                    continue
                sx, sy = edge_stations[i]
                ox, oy = sx + nx * off, sy + ny * off
                # Outer-jump flush — see the cut twin (corner-fan rays
                # flanking a skipped sweep chord across the gap).
                if outer_pts and math.hypot(
                        ox - outer_pts[-1][0],
                        oy - outer_pts[-1][1]) > 4.0 * step:
                    _flush_segment()
                outer_pts.append((ox, oy))
                outer_prov.append((i, float(off)))
                keep = (not thin_inner) or bool(is_ring_vertex[i])
                inner_row.append((i, (sx + nx * d0, sy + ny * d0),
                                  keep))
            _flush_segment()
    return out


def _declaw_short_needle_runs(piece_ring, alts, tol, max_run=2,
                              max_span_m=3.0):
    """Clamp SHORT runs (≤ ``max_run`` consecutive vertices) of altitude
    needles to their flanking mean — the two-vertex extension of
    ``clearance._declaw_alt_needles`` (which by design only clamps single
    vertices).  A run qualifies when its flanking vertices agree within
    ``tol``, every run vertex deviates from the flank mean by more than
    ``tol`` in the same direction, and the flank-to-flank horizontal
    extent is under ``max_span_m`` — a metre-scale reversal packed into a
    couple of sub-metre ring edges is always a resampler foot-flip on a
    notched parent ring (SPJC round-2: a 1.5 m two-vertex dip over
    0.68 m edges), never a real corridor feature (the corridor is a
    ≤5 % surface: 3 m of run can lawfully carry ~0.15 m, not 1.5 m)."""
    n = len(alts)
    if n < max_run + 2:
        return list(alts)
    out = [float(a) for a in alts]
    for start in range(n):
        for run_length in range(1, max_run + 1):
            before = out[(start - 1) % n]
            after = out[(start + run_length) % n]
            if abs(before - after) > tol:
                continue
            flank_mean = 0.5 * (before + after)
            deltas = [out[(start + k) % n] - flank_mean
                      for k in range(run_length)]
            if not all(abs(d) > tol for d in deltas):
                continue
            if not (all(d > 0 for d in deltas)
                    or all(d < 0 for d in deltas)):
                continue
            bx, by = piece_ring[(start - 1) % n]
            ax, ay = piece_ring[(start + run_length) % n]
            if math.hypot(ax - bx, ay - by) > max_span_m:
                continue
            for k in range(run_length):
                out[(start + k) % n] = round(flank_mean, 1)
            break
    return out


def _heal_band_tears(ring, alts, weld, tear_max, min_jump,
                     wall_max=CLEARANCE_STATION_STEP_M):
    """Collapse SUB-METRE near-vertical ring edges a band clip/cap leaves
    behind — the TEAR sentinel class (``check_grade._check_adjacent_ground
    _edges``): a ring edge shorter than ``tear_max`` whose two endpoints'
    altitudes differ by more than ``min_jump``.

    SECOND class (``wall_max``, 2026-07-17): a WELD-ADJACENT WALL edge —
    one endpoint on the pavement weld row, the other a zone vertex, edge
    shorter than a station step (``wall_max``) with a jump exceeding both
    ``min_jump`` and the edge length (grade > 100 %).  No corridor slope
    reaches 100 %; the zone value is a resampler / solved-store escape
    riding raw DEM against the pavement row (CYXY apron #677: weld 706.4
    vs zone 712.7 over 4.0 m).  The sub-metre sentinel misses it at emit,
    but any conformance insert splitting the edge mints a flagged
    sub-metre segment.  Weld-adjacent ONLY: a fill band's outer row
    lawfully rides raw DEM, so two NON-weld vertices across a real
    terrain cliff are never collapsed.

    Cause: the ``difference()`` clips and the band END caps can pinch a
    band's INNER (pavement weld) row to within a metre of its OUTER
    (terrain) row while each keeps its own lawful value, minting a
    near-vertical face no lateral corridor slope produces (the lateral law
    tops out at ~5 %, so a >1 m step over <1 m is impossible by
    construction; it is always a clip residue / pinch, never a graded
    row).  The DEM-aware corridor validator accepts the WIDE band edges
    that ride terrain up a hillside, so the ONLY unlawful thing here is the
    sub-metre pinch edge — remove it geometrically.

    Resolution: drop ONE endpoint of each flagged edge, preferring to
    keep a weld vertex (its position is ON the pavement boundary and its
    value is the pavement weld value the conformance pass welds to —
    never move it).  Between two OUTER vertices (a clip-minted
    near-duplicate) drop the bigger spike.  Iterated to a fixed point so
    a collapse that exposes a fresh short edge is healed too.  Returns
    the healed open ring + aligned altitudes (input objects returned
    unchanged when nothing collapses).  NOTE: both classes key on the
    VALUE jump, so the healed footprint is value-dependent — the
    construct-move footprint-equality acceptance neutralizes this heal
    (see ``test_emit_admission_footprints_equal_gate_off``)."""
    n = len(ring)
    if n < 4:
        return ring, alts
    keep = [True] * n
    changed = True
    guard = 0
    while changed and guard < 2 * n:
        guard += 1
        changed = False
        idxs = [i for i in range(n) if keep[i]]
        m = len(idxs)
        if m <= 3:
            break
        for a in range(m):
            i = idxs[a]
            j = idxs[(a + 1) % m]
            ax, ay = ring[i]
            bx, by = ring[j]
            d = math.hypot(bx - ax, by - ay)
            de = abs(float(alts[i]) - float(alts[j]))
            wi, wj = bool(weld[i]), bool(weld[j])
            is_tear = (d < tear_max and de > min_jump)
            # Weld-adjacent wall edge (see docstring): exactly one weld
            # end, station-scale length, grade over 100 %.
            is_wall = (wall_max is not None and (wi != wj)
                       and d < wall_max and de > min_jump and de > d)
            if not (is_tear or is_wall):
                continue
            if wi and not wj:
                drop = j
            elif wj and not wi:
                drop = i
            elif not wi and not wj:
                # Two outer vertices: drop the spike (the one whose value
                # deviates more from its OTHER ring neighbour).
                pi = idxs[(a - 1) % m]
                nj = idxs[(a + 2) % m]
                dev_i = abs(float(alts[i]) - float(alts[pi]))
                dev_j = abs(float(alts[j]) - float(alts[nj]))
                drop = i if dev_i >= dev_j else j
            else:
                # Two weld vertices sub-metre apart at a >1 m step is a
                # pavement-side discontinuity, not a band pinch — leave it
                # (moving a weld vertex would unweld the pavement seam).
                continue
            keep[drop] = False
            changed = True
            break
    if all(keep):
        return ring, alts
    new_ring = [ring[i] for i in range(n) if keep[i]]
    new_alts = [alts[i] for i in range(n) if keep[i]]
    return new_ring, new_alts


def _heal_emitted_band_tears(emitted_shapes, layout):
    """FINAL tear-heal over the emitted ``graded_strip`` group (2026-07-18).

    The per-piece ``_heal_band_tears`` at emit runs BEFORE the piece's own
    re-deconflict ``difference()`` / remap and before neighbour bands settle,
    so a tear the LATER geometry mints escapes it.  Two classes the raster
    reach band exposes (an apron/junction the tighter, CORRECT ceiling clamps
    ~2 m down, its strips then bridging the resulting step) survive to emit:

      1. WITHIN-STRIP PINCH: a strip clips against a NOT-dropped abutting
         pavement and pinches its own host-weld row and the clip row
         sub-metre apart.
      2. CROSS-STRIP SEAM: two neighbour strips grading off pavements now
         ~2 m apart share a seam node through the emit VALUE CONSENSUS
         (``to_osm``: a shared node carries the mean of the strips touching
         it), so one strip inherits the other's value and tears against its
         own adjacent vertex — a tear invisible in the strip's OWN
         ``node_altitudes`` (it lives only in the shared consensus).

    Under the legacy band the two references sat within the tear jump, so
    neither fired; this is a raster-band reconciliation, not a new law.  The
    ruled resolution is unchanged (``_heal_band_tears`` doctrine: the sub-metre
    near-vertical edge is the ONLY unlawful thing — the DEM-aware corridor
    validator accepts the wide terrain-riding edges — so it is removed
    geometrically).  This pass detects the tear against the EFFECTIVE emitted
    value (the cross-strip shared-coordinate consensus, so class 2 is visible)
    and collapses it by dropping an UNSHARED, non-donor vertex — never a vertex
    another strip or a donor pavement also owns (moving it would un-weld that
    seam).  Runs before the group decimation (healed rings decimate cleanly)
    and before the pipeline's final epsilon-wedge weld (which re-conforms the
    dropped-vertex seam).  Returns the number of strips healed.
    """
    from collections import defaultdict
    from shapely.strtree import STRtree
    from .layout import WELD_DONOR_ROLES
    # RETAINING WALLS protect like donors (no-stacked-nodes unit): a
    # strip vertex welded onto a wall row must never be dropped — the
    # heal's spring-back straightens the strip edge ACROSS the wall
    # face (measured SPJC: a 2.5 m² strip∩wall overlap, zero-tolerance
    # self-overlap invariant).
    donor_ext = [s.polygon.exterior for s in layout.shapes
                 if ((s.role or "") in WELD_DONOR_ROLES
                     or s.role == ROLE_RETAINING_WALL)
                 and s.polygon is not None and not s.polygon.is_empty
                 and s.polygon.geom_type == "Polygon"]
    try:
        tree = STRtree(donor_ext) if donor_ext else None
    except _GEOM_EXC:
        tree = None
    _WELD_TOL_M = 0.05

    def _on_donor(x, y):
        if tree is None:
            return False
        try:
            hit = tree.query_nearest(Point(x, y), max_distance=_WELD_TOL_M)
        except _GEOM_EXC:
            return False
        return len(hit) > 0

    # Cross-strip shared-coordinate consensus (mirrors ``to_osm``'s soft-mean
    # rule): millimetre vertex key -> list of contributing strip values, so a
    # vertex two strips share resolves to the value the patch actually emits
    # there (class 2).  NO-STACKED-NODES (owner ruling 2026-07-19): to_osm
    # hard-merges EVERY same-canonical-point claim into one node whose soft
    # consensus is the mean — there is no "clean wall" split any more, so a
    # same-key spread of ANY size resolves to the mean and is a tear risk
    # against the ring neighbours.
    strip_vals: "defaultdict[tuple, list]" = defaultdict(list)
    strip_rings: list = []
    for sh in emitted_shapes:
        if (sh.ref != _ADJACENT_REF or sh.polygon is None
                or sh.polygon.is_empty
                or sh.polygon.geom_type != "Polygon"
                or sh.node_altitudes is None):
            continue
        try:
            ring = list(sh.polygon.exterior.coords)[:-1]
        except _GEOM_EXC:
            continue
        alts = list(sh.node_altitudes[:len(ring)])
        if len(ring) != len(alts) or len(ring) < 4:
            continue
        keys = [_vertex_key(vx, vy) for (vx, vy) in ring]
        for k, a in zip(keys, alts):
            strip_vals[k].append(float(a))
        strip_rings.append((sh, ring, alts, keys))

    # AUTHORITY value table (no-stacked-nodes hard merge): a strip
    # vertex coincident with any pavement/solver shape EMITS at the
    # authority consensus, not at its own value — the heal must judge
    # tears against the value the patch will actually carry (a strip
    # step of exactly the threshold can emit ABOVE it after adoption:
    # the CYXY #392 shoulder read 1.00 m in strip values but 1.03 m
    # emitted).
    from .layout import SOFT_RECEIVER_ROLES as _SOFT_ROLES
    authority_vals: "defaultdict[tuple, list]" = defaultdict(list)
    for sh in layout.shapes:
        if (sh.role or "") in _SOFT_ROLES:
            continue
        if (sh.polygon is None or sh.polygon.is_empty
                or sh.polygon.geom_type != "Polygon"):
            continue
        try:
            a_ring = list(sh.polygon.exterior.coords)[:-1]
        except _GEOM_EXC:
            continue
        if sh.node_altitudes is not None:
            a_alts = list(sh.node_altitudes[:len(a_ring)])
            if len(a_alts) != len(a_ring):
                continue
        elif sh.altitude is not None:
            a_alts = [float(sh.altitude)] * len(a_ring)
        else:
            continue
        for (vx, vy), a in zip(a_ring, a_alts):
            authority_vals[_vertex_key(vx, vy)].append(float(a))

    def _effective(k, own):
        # to_osm precedence: authority claims win the node outright.
        av = authority_vals.get(k)
        if av:
            return sum(av) / float(len(av))
        vals = strip_vals.get(k)
        if not vals or len(vals) <= 1:
            return own
        # Same-key values ALWAYS intern to one node whose emitted soft
        # consensus is their mean (to_osm hard merge, ruling 2026-07-19).
        return sum(vals) / float(len(vals))

    healed = 0
    for (sh, ring, alts, keys) in strip_rings:
        n = len(ring)
        on_donor = [_on_donor(vx, vy) for (vx, vy) in ring]
        # SHARED = another strip owns this exact coordinate, or a donor
        # pavement edge does: dropping it would un-weld that seam, so it is
        # protected; the tear is resolved by dropping the strip's OWN vertex.
        shared = [on_donor[i] or len(strip_vals.get(keys[i], ())) >= 2
                  for i in range(n)]
        eff = [_effective(keys[i], alts[i]) for i in range(n)]
        keep = [True] * n
        changed = True
        guard = 0
        while changed and guard < 2 * n:
            guard += 1
            changed = False
            idxs = [i for i in range(n) if keep[i]]
            m = len(idxs)
            if m <= 3:
                break
            for a in range(m):
                i = idxs[a]
                j = idxs[(a + 1) % m]
                d = math.hypot(ring[j][0] - ring[i][0],
                               ring[j][1] - ring[i][1])
                de = abs(eff[i] - eff[j])
                if not (d < 0.2 * CLEARANCE_STATION_STEP_M and de > 1.0):
                    continue
                # Drop an UNSHARED endpoint (prefer the larger spike relative
                # to its far ring neighbour); never a shared/donor vertex.
                cand = []
                if not shared[i]:
                    pi = idxs[(a - 1) % m]
                    cand.append((abs(eff[i] - eff[pi]), i))
                if not shared[j]:
                    nj = idxs[(a + 2) % m]
                    cand.append((abs(eff[j] - eff[nj]), j))
                if not cand:
                    continue                       # both protected — leave it
                keep[max(cand)[1]] = False
                changed = True
                break
        if all(keep):
            continue
        new_ring = [ring[i] for i in range(n) if keep[i]]
        new_alts = [alts[i] for i in range(n) if keep[i]]
        if len(new_ring) < 3:
            continue
        try:
            # Interior rings ride along (exterior-only fills the holes).
            poly = Polygon(new_ring + [new_ring[0]],
                           [list(h.coords)
                            for h in sh.polygon.interiors])
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty or poly.geom_type != "Polygon":
                continue
        except _GEOM_EXC:
            continue
        rebuilt = _open_coords(poly)
        if len(rebuilt) < 3:
            continue
        if len(rebuilt) == len(new_ring):
            out_alts = new_alts
        else:
            out_alts = [round(float(_nearest_alt(
                new_ring, new_alts, vx, vy)), 1) for vx, vy in rebuilt]
        sh.polygon = poly
        sh.node_altitudes = out_alts + [out_alts[0]]
        healed += 1
    return healed


# Cross-strip SEAM-STEP blend thresholds (2026-07-18, SPJC east-side
# cliffs): two strips grading off DIFFERENT host pavements run side by
# side, and their near-adjacent — but not coordinate-shared — boundary
# vertices disagree by the host delta.  Measured SPJC: 152 pairs, worst
# 4.4 m over 1.26 m (348 %), at 1-6 m spacing — ABOVE the sub-metre
# pinch class ``_heal_emitted_band_tears`` collapses, and invisible to
# it because each tear spans TWO rings.  Legitimate terracing steps are
# ~0.3 m, so a 1.0 m step floor cleanly separates the classes.
#
# THE RADIUS AND STEP FLOOR ARE THE LAW MODULE'S (v3 §1, third-copy
# absorption): this pass used to declare 6.0 m and 1.0 m locally under
# bare-"seam" names — equal values, third copy.  They are now
# ``strip_seam_law.STRIP_SEAM_TEAR_RADIUS_M`` /
# ``STRIP_SEAM_TEAR_MIN_STEP_M`` (imported above), so healer and census
# cannot drift apart.  Byte-inert: the values are identical.
#
# FOURTH COPY ABSORBED (spec seam-continuity-v4 §1): the cliff-grade
# floor this pass used to declare locally as its own 0.5 IS
# ``strip_seam_law.STRIP_SEAM_TEAR_MIN_GRADE``, imported above.  v3 §1
# flagged it and deferred the coupling to "the round that owns the
# healer's law"; that is this one, and the ruling is to couple.
# Grade floor, for the record: on steep relief (CYXY) neighbour strips
# LEGITIMATELY differ by >1 m at 4-6 m spacing — real hillside drape tops
# out around 30-40 %, while genuine seam cliffs run 100-350 %.  Requiring
# the step to ALSO imply >50 % keeps lawful terrain-following untouched
# (measured CYXY without the floor: 1404 vertices moved, 5 new sub-metre
# pinches minted; with it the blend touches only true cliffs).


# ── THE v4 HEALER LAW — STANDING ──────────────────────────────────────
# The v4 healer law (§1 grade-aware guard, §2 authority-split clusters,
# §3 cluster-level guard) is UNCONDITIONAL (owner 2026-08-05, no gates):
# ``O4_STRIP_HEAL_LAW`` and its predicate are deleted, and the pre-v4
# arms below them are gone with them.  For the record, measured when the
# law landed at the 06:00 release train (lead verdict 31a87b0): HECA
# seam 28→4, CYXY 6→0, pavement byte-identical.

# ── DECLINE LOUDNESS (spec seam-continuity-v3 §2, adjudication item 3) ──
# The healer's every-node-anchored ⇒ genuine-step rule is CORRECT
# non-authority behaviour — a healer must never silently regrade fabric
# whose every node is welded to a pavement authority or is a cross-tile
# seam contract.  Its SILENCE was the defect: those clusters are exactly
# the census rows that survive to ``check_grade``'s ``seam::seam`` class,
# and until now nothing in the build said so.  Every declined cluster
# therefore emits ONE named forensics row — site, step height, anchored
# sides — UNCONDITIONALLY (no gate, no verbosity trick beyond the
# pipeline's own level-1 channel).  Pre-registered invariant: report rows
# == declined clusters, zero silent declines.
#
# MEASURED, v3 lane 2026-08-04 (CYXY + HECA, tip anchors, in-healer
# instrumentation): the all-anchored population is EMPTY at both airports
# (0 declined clusters) while the census reports 34 surviving
# ``seam::seam`` rows — so the spec's assumed decline path is NOT the one
# that leaves those steps standing.  The one that does is the
# NON-WORSENING GUARD below, which has two silent exits of its own:
#
#   * BLOCKED  — the outside-neighbour bounds invert (``lo > hi``) and the
#     free node is left exactly where it was (CYXY's only seam site; HECA
#     (-135,88));
#   * CLAMPED  — the node moves, but to a bound instead of the cluster
#     target, so a step above the floor survives (HECA (-102,30):
#     target 100.53, clamped to 96.27, residual 4.26 m = the census row).
#
# Both are "left alone" outcomes under a different rule, and band 5 is
# "ZERO silent declines".  They are therefore reported too, as their own
# row kinds.  The guard-exit extension was RATIFIED by the v3 lead
# adjudication (spec seam-continuity-v3, item 1).
#
# v4 adds a FOURTH left-alone kind, the DEFERRED AUTHORITY JOINT (§2): a
# pair the healer refuses to blend across because the two sides are
# disagreeing weld authorities or a declared/stacked wall SITE.  It is
# not a failure — it is the healer handing the level change to the wall
# machinery — but it is still a step this pass did not close, so it is
# loud on the same channel.  Band 4's invariant becomes
# ``report rows == declined + guarded + deferred joints``.
_STRIP_SEAM_DECLINE_TAG = "[strip-seam]"


# ── THE SHARED WALL-SITE PREDICATE (spec seam-continuity-v4 §2) ───────
# THE ORDERING RULING, verbatim: "wall-AWARE healer via one shared
# predicate — NOT wall passes reordered before the healer."  The existing
# ORDER CONTRACT (heal → pinch-heal → walls) is measured law
# (pipeline.py, the CYXY 2.16 m² strip∩wall overlap), so nothing moves.
# What is hoisted is the SITE PREDICATE: which strip vertices coincide
# with a designed-split AUTHORITY corner or chain, and by how much.  That
# is derivable from layout state before any wall is emitted, and it is
# INVARIANT across the reconcile unit — the three passes between the
# healer and ``emit_stacked_conflict_walls`` touch ``graded_strip``
# shapes only, never the non-donor authority shapes this index reads.
#
# Single-pass: built ONCE (by whichever of the two consumers runs first,
# i.e. the healer), cached on the layout, consumed by
# ``emit_stacked_conflict_walls`` when it runs after.  One code path, no
# second derivation.
#
# INTERNING SAFETY (measured, v4 band-0 instrumented arm, HECA + CYXY):
# building this table inserts ZERO canonical points at both airports
# (``registry.size`` unchanged across ``emit_stacked_conflict_walls``),
# so hoisting the ``get_or_add`` calls earlier cannot change which later
# points intern together.
class _StripWallSiteIndex:
    """Authority claims over canonical points + authority exteriors.

    ``value_at(vx, vy)`` is the authority level at a point: the mean of
    the vertex claims interned at its canonical point, else the
    edge-interpolated value where the point lies ON a non-donor
    authority exterior, else ``None``.  ``is_site(vx, vy, own)`` is the
    v4 §2 predicate: does a designed-split authority hold a level here
    that differs from the strip's own by more than the emit merge
    tolerance (i.e. will this vertex become WALL geometry)?"""

    __slots__ = ("claims", "edges", "edge_tree", "registry", "tol_m")

    def __init__(self, claims, edges, edge_tree, registry, tol_m):
        self.claims = claims
        self.edges = edges
        self.edge_tree = edge_tree
        self.registry = registry
        self.tol_m = tol_m

    def value_at(self, vx, vy):
        if self.registry is not None:
            key = self.registry.get_or_add(float(vx), float(vy))
            claims = self.claims.get(key)
            if claims:
                return sum(claims) / len(claims)
        return self._edge_value(vx, vy)

    def _edge_value(self, vx, vy):
        if self.edge_tree is None:
            return None
        try:
            idxs = self.edge_tree.query_nearest(
                Point(vx, vy), max_distance=self.tol_m)
        except _GEOM_EXC:
            return None
        if idxs is None or len(idxs) == 0:
            return None
        _exterior, coords_a, alts_a = self.edges[int(idxs[0])]
        return _interp_on_ring_law(coords_a, alts_a, vx, vy, self.tol_m)

    def is_site(self, vx, vy, own):
        """v4 §2 boundary (b): a stacked-wall SITE."""
        top = self.value_at(vx, vy)
        if top is None:
            return False
        return abs(float(top) - float(own)) > VERTEX_ALT_MERGE_TOL_M


def _interp_on_ring_law(coords_a, alts_a, vx, vy, tol_m):
    """Edge-interpolated ring value at (vx, vy), or None past ``tol_m``.
    Shared by the index and ``emit_stacked_conflict_walls`` — one
    derivation."""
    best = None
    na = len(coords_a)
    for i in range(na):
        ax, ay = coords_a[i]
        bx, by = coords_a[(i + 1) % na]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            continue
        t = ((vx - ax) * dx + (vy - ay) * dy) / L2
        t = min(1.0, max(0.0, t))
        px, py = ax + dx * t, ay + dy * t
        d = math.hypot(vx - px, vy - py)
        if best is None or d < best[0]:
            best = (d, (1.0 - t) * alts_a[i] + t * alts_a[(i + 1) % na])
    if best is None or best[0] > tol_m:
        return None
    return best[1]


_EDGE_COINCIDE_TOL_M = 0.01


def strip_wall_site_index(layout, tol_m: float = _EDGE_COINCIDE_TOL_M):
    """Build — or return the cached — shared wall-SITE index for
    ``layout``.  Read-only w.r.t. shape values; the only mutation is the
    canonical-point interning ``emit_stacked_conflict_walls`` already
    performed at this same point in the pipeline (measured: zero
    insertions)."""
    cached = getattr(layout, "_strip_wall_site_index", None)
    if cached is not None:
        return cached
    from shapely.strtree import STRtree
    from .layout import SOFT_RECEIVER_ROLES, WELD_DONOR_ROLES
    registry = getattr(layout, "canonical_points", None)
    claims: dict = {}
    edges: list = []
    for shape in getattr(layout, "shapes", ()) or ():
        role = shape.role or ""
        if (role == ROLE_GRADED_STRIP or role in SOFT_RECEIVER_ROLES
                or role in WELD_DONOR_ROLES):
            continue
        rv = _ring_values_for_walls(shape)
        if rv is None:
            continue
        coords, alts = rv
        if registry is not None:
            for (vx, vy), value in zip(coords, alts):
                key = registry.get_or_add(float(vx), float(vy))
                claims.setdefault(key, []).append(value)
        try:
            edges.append((shape.polygon.exterior, coords, alts))
        except _GEOM_EXC:
            pass
    edge_tree = None
    if edges:
        try:
            edge_tree = STRtree([e[0] for e in edges])
        except _GEOM_EXC:
            edge_tree = None
    index = _StripWallSiteIndex(claims, edges, edge_tree, registry, tol_m)
    try:
        layout._strip_wall_site_index = index
    except Exception:                                   # noqa: BLE001
        pass
    return index


def _ring_values_for_walls(shape):
    """Open exterior ring + aligned per-vertex values, mirroring
    ``to_osm``'s derivation (node_altitudes > flat altitude broadcast >
    sloped-rect high/low corners).  ``None`` when the shape carries no
    elevation or the lists misalign.  ONE derivation, shared by the
    wall-site index and ``emit_stacked_conflict_walls``."""
    from .layout import corner_alts_from_high_low
    poly = shape.polygon
    if poly is None or poly.is_empty or poly.geom_type != "Polygon":
        return None
    try:
        coords = list(poly.exterior.coords)
    except _GEOM_EXC:
        return None
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    if len(coords) < 3:
        return None
    if shape.node_altitudes is not None:
        alts = list(shape.node_altitudes)
        if len(alts) == len(coords) + 1:
            alts = alts[:-1]
        if len(alts) != len(coords):
            return None
        return coords, [float(a) for a in alts]
    if shape.altitude is not None:
        return coords, [float(shape.altitude)] * len(coords)
    if (shape.altitude_high is not None
            and shape.altitude_low is not None
            and len(coords) == 4):
        return coords, corner_alts_from_high_low(
            float(shape.altitude_high), float(shape.altitude_low))
    return None


def _strip_seam_joint_record(kind, a, b, node_xy, node_value, planar,
                             allowance, reasons=("", "")):
    """Forensics record for ONE DEFERRED AUTHORITY JOINT (v4 §2): a pair
    the healer refused to blend across.  ``kind`` is ``anchor_split``
    (two disagreeing weld authorities) or ``wall_site`` (a strip vertex
    coincident with a designed-split authority corner beyond
    ``VERTEX_ALT_MERGE_TOL_M``).  Pure/read-only."""
    (ax, ay), (bx, by) = node_xy[a], node_xy[b]
    return {
        "kind": kind,
        "x": round(float((ax + bx) / 2.0), 2),
        "y": round(float((ay + by) / 2.0), 2),
        "a": (round(float(ax), 2), round(float(ay), 2),
              round(float(node_value[a]), 3)),
        "b": (round(float(bx), 2), round(float(by), 2),
              round(float(node_value[b]), 3)),
        "step_m": round(abs(float(node_value[a] - node_value[b])), 3),
        "planar_m": round(float(planar), 3),
        "allowance_m": round(float(allowance), 3),
        "anchors": (reasons[0] or "free", reasons[1] or "free"),
    }


def _strip_seam_decline_record(members, anchor_reason, node_xy, node_value,
                               node_strips, entries, shape_index):
    """Forensics record for ONE cluster the cross-strip healer declined.

    Pure/read-only: it inspects the healer's own tables and returns a
    dict.  ``anchor_reason`` maps every member node to a NON-EMPTY reason
    (a declined cluster has no free node by definition)."""
    lo = min(members, key=lambda m: (node_value[m], m))
    hi = max(members, key=lambda m: (node_value[m], m))
    reasons: dict = {}
    for m in members:
        reasons[anchor_reason[m]] = reasons.get(anchor_reason[m], 0) + 1
    shape_ids = set()
    for m in members:
        for entry_index in node_strips[m]:
            shape = entries[entry_index][0]
            sid = shape_index.get(id(shape))
            shape_ids.add(sid if sid is not None else -1)
    return {
        "x": round(float(node_xy[hi][0]), 2),
        "y": round(float(node_xy[hi][1]), 2),
        "step_m": round(float(node_value[hi] - node_value[lo]), 3),
        "nodes": len(members),
        "strips": len({e for m in members for e in node_strips[m]}),
        "shape_ids": sorted(shape_ids),
        "anchors": dict(sorted(reasons.items())),
        "lo": (round(float(node_xy[lo][0]), 2),
               round(float(node_xy[lo][1]), 2),
               round(float(node_value[lo]), 3)),
        "hi": (round(float(node_xy[hi][0]), 2),
               round(float(node_xy[hi][1]), 2),
               round(float(node_value[hi]), 3)),
    }


def _strip_seam_guard_record(kind, node_index, node_xy, node_value,
                             target, tgt, lo, hi):
    """Forensics record for ONE non-worsening-guard outcome that leaves a
    step standing: ``blocked`` (bounds inverted, the node does not move at
    all) or ``clamped`` (the node moves to a bound, not to the cluster's
    law target).  Pure/read-only."""
    return {
        "kind": kind,
        "x": round(float(node_xy[node_index][0]), 2),
        "y": round(float(node_xy[node_index][1]), 2),
        "z": round(float(node_value[node_index]), 3),
        "target_m": round(float(target), 3),
        "applied_m": None if tgt is None else round(float(tgt), 3),
        "residual_m": round(float(
            target - (node_value[node_index] if tgt is None else tgt)), 3),
        "bound_lo": None if lo is None else round(float(lo), 3),
        "bound_hi": None if hi is None else round(float(hi), 3),
    }


def report_strip_seam_declines(declined, layout, guarded=(),
                               joints=()) -> int:
    """Emit the v3 §2 / v4 §2 decline report — ONE row per LEFT-ALONE
    outcome, plus a count line so "nothing declined" is distinguishable
    from "the pass did not run".

    Four row kinds, all unconditional (the whole point of the section):

    * ``DECLINED``       — the spec's all-anchored cluster;
    * ``GUARD-DECLINED`` — a free node (v4: a whole sub-cluster) the
      non-worsening guard left exactly where it was;
    * ``GUARD-CLAMPED``  — moved to a guard bound instead of the law
      target, so a step survives;
    * ``DEFERRED-JOINT`` — v4 §2: an authority joint the healer refuses
      to average across, handed to the wall machinery.

    Returns the total number of report ROWS, which is the pre-registered
    equality: rows == left-alone outcomes."""
    icao = str(getattr(layout, "icao", "?") or "?")
    m_to_ll = getattr(layout, "m_to_ll", None)
    guarded = list(guarded)
    joints = list(joints)
    blocked = [g for g in guarded if g["kind"].endswith("blocked")]
    clamped = [g for g in guarded if g["kind"] == "clamped"]

    def _ll(x, y):
        if m_to_ll is None:
            return "?"
        try:
            lat, lon = m_to_ll(x, y)
        except Exception:                           # noqa: BLE001
            return "?"
        return f"{lat:.8f},{lon:.8f}"

    UI.vprint(1, f"  {_STRIP_SEAM_DECLINE_TAG} {icao}: cross-strip seam "
                 f"healer left {len(declined) + len(guarded) + len(joints)} "
                 f"step(s) standing — DECLINED {len(declined)} cluster(s) "
                 f"(every node anchored), GUARD-DECLINED {len(blocked)} "
                 f"node(s) (bounds inverted), GUARD-CLAMPED "
                 f"{len(clamped)} node(s) (moved to a bound), "
                 f"DEFERRED-JOINT {len(joints)} authority joint(s) "
                 f"(handed to the wall machinery).")
    for position, row in enumerate(declined, start=1):
        anchors = ",".join(f"{k or 'free'}:{v}"
                           for k, v in row["anchors"].items())
        UI.vprint(1,
                  f"  {_STRIP_SEAM_DECLINE_TAG} DECLINED {icao} "
                  f"{position}/{len(declined)}: "
                  f"site=({row['x']:.2f},{row['y']:.2f}) "
                  f"ll={_ll(row['x'], row['y'])} "
                  f"step={row['step_m']:.3f}m nodes={row['nodes']} "
                  f"strips={row['strips']} anchored={anchors} "
                  f"shapeIDs={row['shape_ids']} "
                  f"lo=({row['lo'][0]:.2f},{row['lo'][1]:.2f},"
                  f"z={row['lo'][2]:.3f}) "
                  f"hi=({row['hi'][0]:.2f},{row['hi'][1]:.2f},"
                  f"z={row['hi'][2]:.3f})")
    for position, row in enumerate(guarded, start=1):
        label = ("GUARD-DECLINED" if row["kind"].endswith("blocked")
                 else "GUARD-CLAMPED")
        extra = ""
        if row.get("lawful") is not None:
            # v4 §3: an empty CLUSTER interval carries its
            # lawful-assignment attribution (feasibility-is-guaranteed —
            # a survivor is attribution, never tolerance).
            extra = (f" nodes={row.get('nodes')} "
                     f"lawful={row['lawful']} "
                     f"binding_lo={row.get('binding_lo')} "
                     f"binding_hi={row.get('binding_hi')}")
        UI.vprint(1,
                  f"  {_STRIP_SEAM_DECLINE_TAG} {label} {icao} "
                  f"{position}/{len(guarded)}: "
                  f"site=({row['x']:.2f},{row['y']:.2f}) "
                  f"ll={_ll(row['x'], row['y'])} z={row['z']:.3f} "
                  f"target={row['target_m']:.3f} "
                  f"applied={'-' if row['applied_m'] is None else format(row['applied_m'], '.3f')} "
                  f"residual={row['residual_m']:.3f}m "
                  f"bounds=[{'-' if row['bound_lo'] is None else format(row['bound_lo'], '.3f')},"
                  f"{'-' if row['bound_hi'] is None else format(row['bound_hi'], '.3f')}]"
                  f"{extra}")
    for position, row in enumerate(joints, start=1):
        UI.vprint(1,
                  f"  {_STRIP_SEAM_DECLINE_TAG} DEFERRED-JOINT {icao} "
                  f"{position}/{len(joints)}: kind={row['kind']} "
                  f"site=({row['x']:.2f},{row['y']:.2f}) "
                  f"ll={_ll(row['x'], row['y'])} "
                  f"step={row['step_m']:.3f}m "
                  f"planar={row['planar_m']:.3f}m "
                  f"allowance={row['allowance_m']:.3f}m "
                  f"a=({row['a'][0]:.2f},{row['a'][1]:.2f},z={row['a'][2]:.3f}) "
                  f"b=({row['b'][0]:.2f},{row['b'][1]:.2f},z={row['b'][2]:.3f}) "
                  f"anchored={row['anchors'][0]}/{row['anchors'][1]}")
    return len(declined) + len(guarded) + len(joints)


def blend_cross_strip_seam_steps(strip_shapes, layout):
    """Reconcile metre-scale value steps between NEAR-ADJACENT vertices of
    different ``graded_strip`` shapes (2026-07-18, SPJC in-sim cliffs).

    Model: ``to_osm`` interns same-millimetre-key vertices whose values
    sit within the emit merge tolerance into ONE node, so the blend
    operates on that LOGICAL node graph — a logical node (the key plus
    its agreeing twins across strips) moves as a unit; same-key vertices
    whose spread EXCEEDS the tolerance emit as stacked separate nodes (a
    bare vertical terrain wall, the SPJC 3.8 m class) and are separate
    logical nodes that may blend against each other.  Qualifying pairs —
    planar distance under ``STRIP_SEAM_TEAR_RADIUS_M`` (zero included: the
    stacked-wall case), altitude delta over ``STRIP_SEAM_TEAR_MIN_STEP_M``,
    not both exclusively owned by the same single strip — are clustered
    by union-find.  Donor-pavement-welded logical nodes are immovable
    ANCHORS; free logical nodes snap to the anchors\' mean, or to the
    cluster mean when no anchor exists.  A cluster whose every node is
    anchored is left alone (a genuine step — retaining-wall territory,
    never silently flattened) — and since spec seam-continuity-v3 §2 every
    LEFT-ALONE outcome is LOUD: the all-anchored decline, and (measured
    addition, see the section note above) the two non-worsening-guard
    exits, each emit one named forensics row through ``UI.vprint``,
    unconditionally.  ``strip_shapes`` must be the COMPLETE
    final strip population (every emitter: adjacent-ground bands,
    gap-fill spines) — running per emitter group misses exactly the
    cross-family seams that tear.  Returns the number of ring vertices
    re-levelled.

    THE v4 LAW (STANDING since 2026-08-05, unconditional; spec
    ``docs/specs/seam-continuity-v4-spec.md`` §1-§3, ONE interlocking
    law), in three clauses:

    §1 GRADE-AWARE GUARD.  The non-worsening guard's per-neighbour
    allowance stops being a bare ``STRIP_SEAM_TEAR_MIN_STEP_M - 0.05``
    and becomes the CENSUS PAIR PREDICATE
    (``strip_seam_law.seam_guard_allowance_m``).  The bounds-attribution
    verdict measured both inverted bounds coming from that one constant
    quoted against two different excluded neighbours — over-strict by up
    to 3x at the measured 2.2-6.0 m distances, and the
    inversion-creating neighbours are drapes this law's own grade
    conjunct already calls lawful.

    §2 AUTHORITY-SPLIT CLUSTERS.  The healer must NEVER average across
    disagreeing weld authorities or a declared/stacked wall.  Cluster
    membership SPLITS at authority boundaries: (a) a pair of anchored
    nodes whose values disagree beyond the §1 allowance, (b) a pair
    touching a stacked-wall SITE (the shared predicate
    ``strip_wall_site_index``, which ``emit_stacked_conflict_walls``
    consumes when it runs after — one evaluation, two consumers).  Each
    sub-cluster then takes a single lawful target: the mean of its own
    anchors, which is only computed once that population is verified to
    agree PAIRWISE under the census predicate — the only condition under
    which the healer may average at all.  A joint is DEFERRED to the
    wall machinery with a named forensics record.

    §3 CLUSTER-LEVEL GUARD.  Per-node clamping dies.  ONE feasible
    interval is computed for the whole sub-cluster — the intersection of
    every mover's per-neighbour §1 allowances against every non-member
    within ``STRIP_SEAM_TEAR_RADIUS_M`` — and the movers take ONE level
    inside it, so the 4.26 m cliff-between-mates-1.5 m-apart class is
    impossible by construction.  An empty interval is a loud guarded
    record carrying its lawful-assignment attribution."""
    from collections import defaultdict
    from shapely.strtree import STRtree
    from .crown import _point_in_seam_band
    from .layout import WELD_DONOR_ROLES

    wall_index = strip_wall_site_index(layout)

    donor_ext = [s.polygon.exterior for s in layout.shapes
                 if (s.role or "") in WELD_DONOR_ROLES
                 and s.polygon is not None and not s.polygon.is_empty
                 and s.polygon.geom_type == "Polygon"]
    try:
        donor_tree = STRtree(donor_ext) if donor_ext else None
    except _GEOM_EXC:
        donor_tree = None

    # Per-strip vertex tables.
    entries = []            # (shape, ring, alts) — alts open (no closing twin)
    by_key: "defaultdict[tuple, list]" = defaultdict(list)
    for sh in strip_shapes:
        if ((sh.role or "") != "graded_strip" or sh.polygon is None
                or sh.polygon.is_empty
                or sh.polygon.geom_type != "Polygon"
                or sh.node_altitudes is None):
            continue
        try:
            ring = list(sh.polygon.exterior.coords)[:-1]
        except _GEOM_EXC:
            continue
        alts = [float(a) for a in sh.node_altitudes[:len(ring)]]
        if len(ring) != len(alts) or len(ring) < 4:
            continue
        entry_index = len(entries)
        entries.append((sh, ring, alts))
        for position, (vx, vy) in enumerate(ring):
            by_key[_vertex_key(vx, vy)].append(
                (entry_index, position, alts[position], vx, vy))
    if len(entries) < 2:
        return 0

    # LOGICAL nodes: per key, greedy-cluster members by value within the
    # merge tolerance (ascending — deterministic).  Same-key groups whose
    # values disagree beyond it become SEPARATE logical nodes (stacked
    # wall) and may blend against each other at distance zero.
    logical = []    # dict: members [(entry,pos)], strips set, value, xy
    for key in sorted(by_key):
        members = sorted(by_key[key], key=lambda m: (m[2], m[0], m[1]))
        group: list = []
        for member in members:
            if group and member[2] - group[0][2] > VERTEX_ALT_MERGE_TOL_M:
                logical.append(group)
                group = []
            group.append(member)
        if group:
            logical.append(group)
    node_xy = []
    node_value = []
    node_strips = []
    for group in logical:
        node_xy.append((group[0][3], group[0][4]))
        node_value.append(sum(m[2] for m in group) / float(len(group)))
        node_strips.append({m[0] for m in group})

    # Shape index = the ``shapeID`` tag ``layout.to_osm`` emits (index in
    # ``layout.shapes``), so a decline row joins EXACTLY to the emitted
    # patch instead of by proximity.
    shape_index = {
        id(sh): idx
        for idx, sh in enumerate(getattr(layout, "shapes", ()) or ())}

    def _anchor_reason(node_index):
        """Anchor REASON ("" when free) — the boolean this used to return
        is ``bool(reason)``; the reason itself is what the v3 §2 decline
        report names as the anchored side.  Call order unchanged."""
        (vx, vy) = node_xy[node_index]
        # TILE-SEAM protection (2026-07-18 SPLP regression): seam-band
        # vertices are cross-tile terrain contracts — each tile builds
        # independently with a different strip population, so a blended
        # seam value diverges between neighbour tiles and emits a step
        # AT the tile boundary (measured: two -78-side vertices moved
        # +2.00 m against the immutable seam DEM).  Same predicate the
        # crown and tile_cut use.
        if _point_in_seam_band(layout, vx, vy):
            return "tile_seam"
        if donor_tree is None:
            return ""
        try:
            hit = donor_tree.query_nearest(Point(vx, vy), max_distance=0.05)
        except _GEOM_EXC:
            return ""
        return "weld" if len(hit) > 0 else ""

    points = [Point(vx, vy) for (vx, vy) in node_xy]
    try:
        vertex_tree = STRtree(points)
        left, right = vertex_tree.query(points, predicate="dwithin",
                                        distance=STRIP_SEAM_TEAR_RADIUS_M)
    except _GEOM_EXC:
        return 0
    parent = list(range(len(points)))

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    _anchor_memo: dict = {}

    def _reason(node_index):
        """Memoised ``_anchor_reason`` — same population, same values, one
        evaluation per node instead of one per cluster membership."""
        reason = _anchor_memo.get(node_index)
        if reason is None:
            reason = _anchor_reason(node_index)
            _anchor_memo[node_index] = reason
        return reason

    _wall_site_memo: dict = {}

    def _is_wall_site(node_index):
        """v4 §2 boundary (b), through the SHARED predicate."""
        hit = _wall_site_memo.get(node_index)
        if hit is None:
            (vx, vy) = node_xy[node_index]
            hit = bool(wall_index.is_site(vx, vy, node_value[node_index]))
            _wall_site_memo[node_index] = hit
        return hit

    paired = False
    joints: list = []
    # Radius adjacency over ALL pairs (BEFORE the Δ/grade filter) — the
    # NON-WORSENING guard below needs every near neighbour, including
    # the ones excluded from clustering precisely because they already
    # AGREE with a member (Δ < the step floor).
    nbrs: "defaultdict[int, list]" = defaultdict(list)
    for a, b in zip(left.tolist(), right.tolist()):
        if a != b:
            nbrs[a].append(b)
            nbrs[b].append(a)
        if a >= b:
            continue
        delta = abs(node_value[a] - node_value[b])
        (ax, ay), (bx, by) = node_xy[a], node_xy[b]
        planar = math.hypot(ax - bx, ay - by)
        # §1: the healer's pairing test IS the census predicate.
        if not seam_pair_is_tear(delta, planar):
            continue
        if (len(node_strips[a]) == 1 and node_strips[a] == node_strips[b]):
            continue        # within one ring: the pinch healer\'s domain
        # §2: cluster membership SPLITS at an authority boundary.
        allowance = seam_guard_allowance_m(planar)
        reason_a, reason_b = _reason(a), _reason(b)
        if reason_a and reason_b and delta > allowance:
            joints.append(_strip_seam_joint_record(
                "anchor_split", a, b, node_xy, node_value, planar,
                allowance, (reason_a, reason_b)))
            continue
        if _is_wall_site(a) or _is_wall_site(b):
            joints.append(_strip_seam_joint_record(
                "wall_site", a, b, node_xy, node_value, planar,
                allowance, (reason_a, reason_b)))
            continue
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
        paired = True
    clusters: "defaultdict[int, list]" = defaultdict(list)
    if paired:
        for node_index in range(len(points)):
            clusters[_find(node_index)].append(node_index)

    moved = 0
    changed_entries: set = set()
    declined: list = []
    guarded: list = []
    for root in sorted(clusters):
        members = clusters[root]
        if len(members) < 2:
            continue                # never paired: not a seam cluster
        anchor_reason = {m: _reason(m) for m in members}
        anchors = [m for m in members if anchor_reason[m]]
        free_nodes = [m for m in members if not anchor_reason[m]]
        if not free_nodes:
            # ALL ANCHORED: a genuine step, left alone — correct
            # non-authority behaviour, but v3 §2 forbids it being SILENT.
            declined.append(_strip_seam_decline_record(
                members, anchor_reason, node_xy, node_value, node_strips,
                entries, shape_index))
            continue
        source = anchors if anchors else members
        member_set = set(members)
        if anchors:
            # §2, STATED AS LAW: the healer may average ONLY over a
            # population that agrees PAIRWISE under the census predicate
            # — such a mean cannot mint a row.  The pairing loop already
            # refused to union across a disagreeing anchor pair; this
            # catches the TRANSITIVE case (two disagreeing anchors joined
            # through free nodes), where the whole sub-cluster is a
            # deferred authority joint rather than an averaging site.
            split = None
            for i in range(len(anchors)):
                for j in range(i + 1, len(anchors)):
                    a_i, a_j = anchors[i], anchors[j]
                    (ax, ay), (bx, by) = node_xy[a_i], node_xy[a_j]
                    planar = math.hypot(ax - bx, ay - by)
                    if planar >= STRIP_SEAM_TEAR_RADIUS_M:
                        continue    # cannot be a census pair at all
                    delta = abs(node_value[a_i] - node_value[a_j])
                    if delta > seam_guard_allowance_m(planar):
                        split = (a_i, a_j, planar,
                                 seam_guard_allowance_m(planar))
                        break
                if split is not None:
                    break
            if split is not None:
                a_i, a_j, planar, allowance = split
                joints.append(_strip_seam_joint_record(
                    "target_split", a_i, a_j, node_xy, node_value, planar,
                    allowance,
                    (anchor_reason[a_i], anchor_reason[a_j])))
                continue
        target = round(
            sum(node_value[m] for m in source) / float(len(source)), 2)
        # ── §3 CLUSTER-LEVEL GUARD (the radius fix) ───────────────────
        # WHY A GUARD AT ALL (CYXY tear diagnosis 2026-07-26): the
        # cluster mean can hoist a mover away from a near neighbour that
        # was EXCLUDED from the cluster because it already AGREED (Δ
        # below the step floor) — the re-level then MINTS a fresh step
        # under this pass's own law (measured: a daylight-line node
        # lifted +1.15 m to the bench mean, its 2.2 m neighbour
        # untouched → 1.25 m tear).  Hence: no move may open a new
        # over-floor step against a radius neighbour left outside the
        # cluster.
        #
        # ONE feasible interval for the whole sub-cluster: the
        # intersection of every MOVER's per-neighbour §1 allowances
        # against every non-member within the tear radius.  A bound
        # found through one mover binds the CLUSTER, because every
        # mover takes the SAME level — which is what makes the
        # 4.26 m cliff-between-mates class impossible.
        lo = hi = None
        binding_lo = binding_hi = None
        per_node: dict = {}
        for m in free_nodes:
            m_lo = m_hi = None
            (mx, my) = node_xy[m]
            for n in nbrs.get(m, ()):
                if n in member_set:
                    continue
                (nx, ny) = node_xy[n]
                planar = math.hypot(mx - nx, my - ny)
                allowance = seam_guard_allowance_m(planar)
                hi_n = node_value[n] + allowance
                lo_n = node_value[n] - allowance
                if m_hi is None or hi_n < m_hi:
                    m_hi = hi_n
                if m_lo is None or lo_n > m_lo:
                    m_lo = lo_n
                if hi is None or hi_n < hi:
                    hi = hi_n
                    binding_hi = (round(float(nx), 2),
                                  round(float(ny), 2),
                                  round(float(node_value[n]), 3),
                                  round(float(planar), 2))
                if lo is None or lo_n > lo:
                    lo = lo_n
                    binding_lo = (round(float(nx), 2),
                                  round(float(ny), 2),
                                  round(float(node_value[n]), 3),
                                  round(float(planar), 2))
            per_node[m] = (m_lo, m_hi)
        worst = max(free_nodes,
                    key=lambda m: (abs(node_value[m] - target), m))
        if lo is not None and hi is not None and lo > hi:
            # EMPTY CLUSTER INTERVAL after §1+§2 — a loud guarded
            # record carrying its LAWFUL-ASSIGNMENT check
            # (feasibility-is-guaranteed: a survivor is attribution,
            # never tolerance).  ``per_node_feasible`` means a lawful
            # assignment exists but only by letting the mates take
            # DIFFERENT levels — which is exactly what §3 forbids, so
            # the record names the trade rather than hiding it.
            node_feasible = all(
                not (a is not None and b is not None and a > b)
                for (a, b) in per_node.values())
            record = _strip_seam_guard_record(
                "cluster_blocked", worst, node_xy, node_value, target,
                None, lo, hi)
            record["nodes"] = len(free_nodes)
            record["lawful"] = ("per_node_feasible" if node_feasible
                                else "node_empty")
            record["binding_lo"] = binding_lo
            record["binding_hi"] = binding_hi
            guarded.append(record)
            continue
        tgt = target
        if hi is not None and tgt > hi:
            tgt = hi
        if lo is not None and tgt < lo:
            tgt = lo
        tgt = round(tgt, 2)
        if abs(tgt - target) > 1e-9:
            # Moved, but to a BOUND — the law target was not reached,
            # so a step above the floor can survive (HECA (-102,30)).
            record = _strip_seam_guard_record(
                "clamped", worst, node_xy, node_value, target, tgt,
                lo, hi)
            record["nodes"] = len(free_nodes)
            record["lawful"] = "cluster_clamped"
            record["binding_lo"] = binding_lo
            record["binding_hi"] = binding_hi
            guarded.append(record)
        # RIGID MOVE: every mover takes the one clamped level.
        for m in free_nodes:
            if abs(node_value[m] - tgt) < 1e-9:
                continue
            node_value[m] = tgt
            for (entry_index, position, _a, _x, _y) in logical[m]:
                entries[entry_index][2][position] = tgt
                changed_entries.add(entry_index)
                moved += 1
    # v3 §2: the declines are reported BEFORE the writeback, so a
    # writeback failure cannot swallow them.  Read-only w.r.t. geometry.
    report_strip_seam_declines(declined, layout, guarded, joints)
    # v4 §2: the deferred joints travel to the wall pass, which
    # reports (pre-registered ZERO) any it does not pick up.
    try:
        layout._strip_seam_deferred_joints = joints
    except Exception:                                   # noqa: BLE001
        pass
    # Write back ONLY the touched strips — untouched shapes keep their
    # exact original altitude lists (byte-identity everywhere no seam
    # cluster exists).
    for entry_index in sorted(changed_entries):
        (sh, _ring, alts) = entries[entry_index]
        sh.node_altitudes = list(alts) + [alts[0]]
    return moved


# ── Stacked-conflict wall emission (owner ruling 2026-07-19) ──────
# NO-STACKED-NODES INVARIANT: the emitter hard-merges every coincident
# vertex into ONE node with ONE consensus elevation (layout.to_osm),
# so a strip vertex that coincides with a designed-split authority
# corner (building pad, service road, terminal, groundside — the
# WELD_DONOR_ROLES complement) can no longer render its level change
# as a stacked "clean wall" twin.  This pass resolves the residue AS
# GEOMETRY before emit: the strip's conflicting boundary run retreats
# horizontally into its own interior, and a ``retaining_wall`` face
# fills the vacated band — top row ON the old boundary at the
# authority values (welds to the designed shape's chain), bottom row
# at the retreated strip edge at the strip's own values.  The level
# change survives as deliberate, horizontally-extended wall geometry.
#
# The retreat must exceed the emitter's canonical-point proximity
# tolerance (SHARED_VERTEX_TOL_M = 0.5 m) or the moved vertex would
# re-intern into the very node it retreats from.
STACKED_WALL_RETREAT_M = 0.6
# Run-extension floor: ring neighbours of a primary conflict join the
# wall run whenever they are coincident with the authority boundary at
# all (any spread above emit-rounding noise) — the run must terminate
# at a NON-coincident vertex, where the strip's own drape is
# continuous.  Terminating at a still-coincident neighbour leaves that
# neighbour silently merged UP to the authority value beside a
# retreated vertex at the strip's own value: a shoulder step of the
# full conflict height (the CYXY #392 tear, 1.03 m over 0.99 m,
# survived a 0.3 m floor exactly this way — the shoulder's own spread
# was small but its merged value was not).
STACKED_WALL_TAPER_MIN_M = 0.05
# ── THE WALLS RULING, EXECUTED (R19-4; owner 2026-08-07 "retaining walls
# emit ONLY at carve structures") ────────────────────────────────────
# Owner, verbatim: "I can't think of a reason we need to emit retaining
# walls except around tunnels."  Walls are lawful ONLY at tunnel/bridge
# CARVE structures (portals, abutments); everywhere else "the
# replacement form is FEATHER: graded transitions under grade caps, NO
# explicit relief feature ... tight spots get steep slopes, never walls".
#
# Measured at HECA on the owner's artifact: 56 of 58 emitted walls are
# authority_retreat faces resolving a lot-vs-road authority split of
# 2.3-2.7 m with NO tunnel or bridge within 50 m — the mid-road wall the
# owner reported.  So a retreat run at a carve structure keeps its wall
# (unchanged geometry, unchanged ref); every other retreat run vacates a
# band WIDE ENOUGH for the step to grade at the loser's own cap, and the
# band emits as the LOSER'S OWN ROLE — a graded feather the census then
# judges under that role's law, instead of a relief feature no law reads.
_CARVE_STRUCTURE_ROLES = frozenset((
    ROLE_TUNNEL_RAMP, ROLE_TUNNEL_TRENCH,
    ROLE_BRIDGE_TRENCH, ROLE_BRIDGE_CAUSEWAY,
))
_CARVE_STRUCTURE_REFS = frozenset((
    "tunnel_wall", "tunnel_portal", "bridge_abutment",
))
# The feather run is ``spread / cap`` with this much margin, so the
# emitted transition lands strictly INSIDE its cap rather than exactly
# on it (emit quantisation would otherwise flag the law's own remedy).
_FEATHER_RUN_MARGIN = 1.1


def emit_stacked_conflict_walls(layout) -> int:
    """Resolve strip-vs-authority coincident level conflicts as offset
    wall geometry (owner ruling 2026-07-19: nodes are never stacked; a
    genuine level change is horizontal wall geometry).

    For every ``graded_strip`` ring vertex whose canonical point also
    carries a NON-donor authority claim differing by more than
    ``VERTEX_ALT_MERGE_TOL_M``: retreat the strip vertex
    ``STACKED_WALL_RETREAT_M`` into the strip's interior and emit a
    ``retaining_wall`` face over the vacated band.  Tile-seam-band
    vertices are cross-tile contracts and are never moved (their
    conflicts fall back to the emit consensus merge).  Returns the
    number of wall faces emitted.

    v4 §2 (STANDING, unconditional): the AUTHORITY half of the site
    table is not rebuilt here — it is the SHARED index the cross-strip
    healer already consulted (``strip_wall_site_index``), evaluated once
    and passed forward on the layout.  The pass ORDER is unchanged (the
    ordering ruling: the heal-before-retreat contract is measured law);
    only the derivation is single-pass.  The STRIP half is still read
    here, because the healer moved strip values after the index was
    built — that is the point of running after it.
    """
    from .crown import _point_in_seam_band

    registry = getattr(layout, "canonical_points", None)
    if registry is None:
        return 0
    wall_index = strip_wall_site_index(layout)
    # RUNWAY-STRIP WALL LAW (owner ruling 2026-08-01): a face inside a
    # runway strip footprint is inadmissible.  Skipping the RUN also
    # cancels its vertex retreat, i.e. the conflict falls back to the emit
    # consensus merge — the emitter's own documented fallback, not a new
    # path.
    _strip_keepout = runway_strip_wall_keepout(layout)
    # ROAD-COURSE WALL LAW (owner 2026-08-12b; wired here by the
    # corridor-joins round's ruling 2).  ``service_corridor_wall_keepout``
    # was consulted by the TERRACE pass alone, so this emitter walled the
    # road↔taxiway mouth conflict the terrace pass would have refused —
    # measured at KCLT 35.213852,-80.9406291 (way -13314, a 2.3 m face
    # standing across the corridor's own course).  With ruling 1's mouth
    # join the conflict should not arise at a mouth at all; this is the
    # belt, and it still stops an edge-parallel conflict wall along the
    # corridor's run.  Same drop test as the terrace pass, same geometry.
    _corridor_keepout = service_corridor_wall_keepout(layout)

    # ONE derivation of "the ring and its aligned values", shared with
    # the wall-site index (module-level ``_ring_values_for_walls``).
    _ring_values = _ring_values_for_walls

    # Authority claim table over canonical points: value claims from
    # NON-donor, non-soft shapes (the designed-split classes whose
    # corners the strip adoption never welded to).  Donor-pavement and
    # soft claims merge fine through the emit consensus and need no
    # wall.  Alongside the vertex table, each shape's exterior +
    # aligned values serve the EDGE-coincident case: a strip boundary
    # clipped along a designed shape shares the CHAIN, not necessarily
    # the vertices — its vertices lie ON the foreign edge, the weld
    # pass splices them into it, and the consensus then bends the
    # strip mid-edge (the CYXY #392 service-road class).  BOTH halves
    # come from the shared v4 §2 index; nothing is re-derived here.
    from shapely.strtree import STRtree
    authority_claims: dict = wall_index.claims
    authority_edges: list = wall_index.edges  # (exterior, coords, alts)
    # Soft strip-vs-strip claims (the ALL-ANCHORED residue): the seam
    # blend levels every FREE vertex first, so a coincident strip-strip
    # spread still exceeding the merge tolerance afterwards is two
    # host-welded (anchored) strips holding a genuine level change —
    # exactly the class the ruling turns into wall geometry.  The
    # LOWER strip retreats; the top holder keeps the point.
    strip_claims: dict = {}
    strip_edges: list = []   # (exterior, coords, alts, id(shape))
    # STRIP claims only: every non-strip role is either already in the
    # shared index (authority) or excluded from walling by role
    # (soft / weld-donor), so this loop reads the strip half alone.
    for shape in layout.shapes:
        if (shape.role or "") != ROLE_GRADED_STRIP:
            continue
        rv = _ring_values(shape)
        if rv is None:
            continue
        coords, alts = rv
        for (vx, vy), value in zip(coords, alts):
            key = registry.get_or_add(float(vx), float(vy))
            strip_claims.setdefault(key, []).append(
                (value, id(shape)))
        try:
            strip_edges.append(
                (shape.polygon.exterior, coords, alts, id(shape)))
        except _GEOM_EXC:
            pass

    if (not authority_claims and not authority_edges
            and not strip_claims):
        return 0
    edge_tree = wall_index.edge_tree

    def _edge_conflict_value(vx, vy):
        """Authority value at (vx, vy) when the point lies ON a
        non-donor authority exterior (edge-interpolated); None when no
        edge passes through the point.  Same arithmetic the shared
        wall-site index runs (``_interp_on_ring_law``)."""
        if edge_tree is None:
            return None
        try:
            idxs = edge_tree.query_nearest(
                Point(vx, vy), max_distance=_EDGE_COINCIDE_TOL_M)
        except _GEOM_EXC:
            return None
        if idxs is None or len(idxs) == 0:
            return None
        _exterior, coords_a, alts_a = authority_edges[int(idxs[0])]
        return _interp_on_ring_law(coords_a, alts_a, vx, vy,
                                   _EDGE_COINCIDE_TOL_M)

    strip_edge_tree = None
    if strip_edges:
        try:
            strip_edge_tree = STRtree([e[0] for e in strip_edges])
        except _GEOM_EXC:
            strip_edge_tree = None

    def _interp_on_ring(coords_a, alts_a, vx, vy):
        """Edge-interpolated value of a ring at (vx, vy), or None when
        the point is farther than the coincidence tolerance.  ONE
        derivation (``_interp_on_ring_law``)."""
        return _interp_on_ring_law(coords_a, alts_a, vx, vy,
                                   _EDGE_COINCIDE_TOL_M)

    def _strip_edge_conflict_value(vx, vy, own_id):
        """Highest OTHER-strip chain value at (vx, vy) when the point
        lies on another strip's exterior; None otherwise."""
        if strip_edge_tree is None:
            return None
        try:
            idxs = strip_edge_tree.query(
                Point(vx, vy), predicate="dwithin",
                distance=_EDGE_COINCIDE_TOL_M)
        except _GEOM_EXC:
            return None
        best = None
        for k in idxs:
            exterior, coords_a, alts_a, sid = strip_edges[int(k)]
            if sid == own_id:
                continue
            val = _interp_on_ring(coords_a, alts_a, vx, vy)
            if val is not None and (best is None or val > best):
                best = val
        return best

    emitted = 0
    new_walls: list = []
    for shape in layout.shapes:
        if shape.role != ROLE_GRADED_STRIP:
            continue
        rv = _ring_values(shape)
        if rv is None or shape.node_altitudes is None:
            continue
        coords, alts = rv
        n = len(coords)
        if n < 4:
            continue
        # Coincidence spread per vertex (vertex- or edge-coincident with
        # a non-donor authority).  PRIMARY conflicts (spread beyond the
        # merge tolerance) seed wall runs; each run then EXTENDS along
        # ring neighbours holding smaller-but-real spreads
        # (> STACKED_WALL_TAPER_MIN_M) so the level change tapers
        # INSIDE the wall face — without the extension, the run's
        # shoulder (a neighbour that merged silently) steps against the
        # first retreated vertex by the full conflict height (the CYXY
        # #392 shoulder tear).
        coincident_top: list = [None] * n
        spread: list = [0.0] * n
        for i, ((vx, vy), own) in enumerate(zip(coords, alts)):
            key = registry.get_or_add(float(vx), float(vy))
            claims = authority_claims.get(key)
            if claims:
                top = sum(claims) / len(claims)
            else:
                top = _edge_conflict_value(vx, vy)
            if top is None:
                # Soft strip-vs-strip cluster: this strip retreats only
                # when another strip holds a HIGHER value at the point
                # (the top holder keeps the weld; equal values are the
                # ordinary shared seam).
                cluster = strip_claims.get(key)
                if cluster and len(cluster) > 1:
                    others_max = max(
                        (v for (v, sid) in cluster if sid != id(shape)),
                        default=None)
                    if others_max is not None and others_max > own:
                        top = others_max
                if top is None:
                    # Edge-coincident soft case: this vertex lies mid-
                    # edge on a HIGHER strip's chain (the weld would
                    # splice a valley node into that chain).
                    se = _strip_edge_conflict_value(vx, vy, id(shape))
                    if se is not None and se > own:
                        top = se
                if top is None:
                    continue
            sp = abs(top - own)
            if sp <= 0.05:
                continue
            if _point_in_seam_band(layout, vx, vy):
                continue  # cross-tile contract — consensus merge only
            coincident_top[i] = top
            spread[i] = sp
        clipped_walls = _retreat_run_walls(shape, coords, alts,
                                           coincident_top, spread,
                                           _strip_keepout,
                                           corridor_keepout=_corridor_keepout)
        new_walls.extend(clipped_walls)
        emitted += len(clipped_walls)
    layout.shapes.extend(new_walls)
    report_strip_seam_joint_pickup(layout, new_walls)
    return emitted


def _retreat_run_walls(shape, coords, alts, coincident_top, spread,
                       keepout, retreat_m=None, face_spec=None,
                       corridor_keepout=None):
    """THE RETREAT MACHINE — one derivation, two callers.

    Given a shape's open ring (``coords``/``alts``), the value a HIGHER
    authority holds at each vertex (``coincident_top[i]`` or ``None``)
    and that vertex's spread, retreat every conflicting vertex
    ``STACKED_WALL_RETREAT_M`` into this shape's own interior and return
    the ``retaining_wall`` faces that cover the vacated band.  Mutates
    ``shape.polygon`` / ``shape.node_altitudes`` only when at least one
    face built cleanly and the retreated ring is still a valid simple
    polygon; otherwise the shape is left untouched and no wall is
    returned (the conflict falls back to the emitter's own adopt).

    Callers: ``emit_stacked_conflict_walls`` (strip vs authority, owner
    ruling 2026-07-19) and ``emit_authority_retreat_walls``
    (consensus-retirement §2: any LOSING claimant beyond tol retreats).

    ``retreat_m(i)`` (R19-4) is the per-vertex retreat distance, default
    ``STACKED_WALL_RETREAT_M``; ``face_spec(run)`` returns the
    ``(role, ref)`` of the face that fills the vacated band, default the
    ``retaining_wall`` / ``stacked_conflict_wall`` pair.  Together they
    are how the WALLS RULING is executed without a second copy of the
    retreat machine: a FEATHER is the same vacated band, made wide enough
    to grade and emitted under the loser's own role.

    ``corridor_keepout`` (corridor-joins round ruling 2) is the SERVICE
    CORRIDOR course keep-out (``service_corridor_wall_keepout``), applied
    with exactly the drop test the terrace pass already applies to it and
    the runway strip: a face intersecting it is not built, so the conflict
    falls back to the emit consensus.  The terrace emitter consulted it and
    this one did not, which is how the KCLT mouth conflict (way -13314) was
    walled — measured 2026-08-12c.  ``None`` ⇒ untouched.
    """
    n = len(coords)
    _dbg = (os.environ.get("O4_RETREAT_DIAG")
            and (shape.role or "") in os.environ.get("O4_RETREAT_DIAG", "")
            and any(s > VERTEX_ALT_MERGE_TOL_M for s in spread))

    def _d(msg):
        if _dbg:
            print(f"  [retreat-run] {msg}", flush=True)
    primary = [i for i in range(n)
               if spread[i] > VERTEX_ALT_MERGE_TOL_M]
    _d(f"coords={[(round(x, 2), round(y, 2)) for x, y in coords]} "
       f"primary={primary} keepout={'yes' if keepout is not None else 'no'}")
    if not primary:
        return []
    _strip_keepout = keepout
    selected: set = set(primary)
    for i in primary:
        for step in (1, -1):
            j = i
            while True:
                j = (j + step) % n
                if (j in selected
                        or coincident_top[j] is None
                        or spread[j] <= STACKED_WALL_TAPER_MIN_M):
                    break
                selected.add(j)
    conflict_top = [coincident_top[i] if i in selected else None
                    for i in range(n)]
    # Inward retreat per conflict vertex: candidate normals are the
    # ±perpendicular of the adjacent-edge mean direction; keep the
    # one whose probe point lands inside the strip.
    poly = shape.polygon
    moved_pos: list = [None] * n
    for i in range(n):
        if conflict_top[i] is None:
            continue
        ax, ay = coords[(i - 1) % n]
        bx, by = coords[i]
        cx, cy = coords[(i + 1) % n]
        tx, ty = (cx - ax), (cy - ay)
        norm = math.hypot(tx, ty)
        if norm < 1e-9:
            continue
        tx, ty = tx / norm, ty / norm
        _rm = (float(retreat_m(i)) if retreat_m is not None
               else STACKED_WALL_RETREAT_M)
        # BACK OFF TO WHAT FITS (R19-4).  The wall's 0.6 m always landed
        # inside; a FEATHER's run is ``spread / cap`` — tens of metres —
        # and at a ring CORNER the inward normal is the diagonal of two
        # edges, so the full run can leave the shape.  Take the widest
        # run that fits, never narrower than the retreat that has always
        # fitted.  The ruling is explicit that this is the right
        # direction: "tight spots get steep slopes, never walls" (no
        # tight-spot exception) — a shortened feather reads as the steep
        # face it is, where a wall would hide it from every grade law.
        _tries = [_rm]
        while _tries[-1] > STACKED_WALL_RETREAT_M * 2.0:
            _tries.append(max(_tries[-1] * 0.5, STACKED_WALL_RETREAT_M))
        if _tries[-1] > STACKED_WALL_RETREAT_M:
            _tries.append(STACKED_WALL_RETREAT_M)
        for _try in _tries:
            for (nx_, ny_) in ((-ty, tx), (ty, -tx)):
                px = bx + nx_ * _try
                py = by + ny_ * _try
                try:
                    if poly.contains(Point(px, py)):
                        moved_pos[i] = (px, py)
                        break
                except _GEOM_EXC:
                    continue
            if moved_pos[i] is not None:
                break
    run_indices = [i for i in range(n) if moved_pos[i] is not None]
    _d(f"moved_pos set at {run_indices}")
    if not run_indices:
        return []
    # Group into consecutive ring runs (wrap-aware).
    runs: list[list[int]] = []
    current = [run_indices[0]]
    for i in run_indices[1:]:
        if (i - current[-1]) % n == 1:
            current.append(i)
        else:
            runs.append(current)
            current = [i]
    runs.append(current)
    if (len(runs) > 1 and runs[0][0] == 0
            and (runs[-1][-1] + 1) % n == 0):
        runs[0] = runs[-1] + runs[0]
        runs.pop()
    # Build one wall face per run; commit the retreat only for the
    # runs whose face built cleanly, and only if the retreated ring
    # stays a valid simple polygon (else the whole shape falls back
    # to the emit consensus merge, walls withdrawn).
    new_coords = list(coords)
    new_alts = list(alts)
    shape_walls: list = []
    # The parent's footprint BEFORE the retreat.  A retreat face is, by
    # construction, exactly the band the shape VACATED — see the clip
    # below, which is stated against this.
    before_poly = shape.polygon
    for run in runs:
        top_pts = [coords[i] for i in run]
        top_alts_run = [round(float(conflict_top[i]), 1) for i in run]
        bot_pts = [moved_pos[i] for i in run]
        bot_alts_run = [round(float(alts[i]), 1) for i in run]
        # Pinch the wall closed with the ring neighbours on the TOP
        # row (unmoved, at the strip's own value — zero face height
        # at the taper stations).
        prev_i = (run[0] - 1) % n
        next_i = (run[-1] + 1) % n
        ring_pts = ([coords[prev_i]] + top_pts + [coords[next_i]]
                    + bot_pts[::-1])
        ring_alts = ([round(float(alts[prev_i]), 1)] + top_alts_run
                     + [round(float(alts[next_i]), 1)]
                     + bot_alts_run[::-1])
        try:
            wall_poly = Polygon(ring_pts)
            if not wall_poly.is_valid:
                wall_poly = wall_poly.buffer(0)
            if (wall_poly.is_empty
                    or wall_poly.geom_type != "Polygon"):
                _d(f"run={run} FACE DROPPED: geom={wall_poly.geom_type} "
                   f"empty={wall_poly.is_empty}")
                continue
        except _GEOM_EXC as _e:
            _d(f"run={run} FACE EXC {_e!r}")
            continue
        rebuilt = _open_coords(wall_poly)
        if len(rebuilt) < 3:
            continue
        if len(rebuilt) == len(ring_pts):
            wall_alts = ring_alts
        else:
            wall_alts = [round(float(_nearest_alt(
                ring_pts, ring_alts, vx, vy)), 1)
                for (vx, vy) in rebuilt]
        if (_strip_keepout is not None
                and wall_poly.intersects(_strip_keepout)):
            _d(f"run={run} FACE DROPPED: runway-strip keepout")
            continue            # runway-strip wall law (see above)
        if (corridor_keepout is not None
                and wall_poly.intersects(corridor_keepout)):
            _d(f"run={run} FACE DROPPED: service-corridor course keepout")
            continue            # road-course wall law (owner 2026-08-12b)
        _role, _ref = ((ROLE_RETAINING_WALL, "stacked_conflict_wall")
                       if face_spec is None else face_spec(run))
        shape_walls.append(BuiltShape(
            polygon=wall_poly, role=_role, ref=_ref,
            node_altitudes=wall_alts + [wall_alts[0]]))
        for i in run:
            new_coords[i] = moved_pos[i]
    if not shape_walls:
        _d("NO FACES BUILT -> retreat withdrawn")
        return []
    try:
        # Interior rings ride along (exterior-only fills the holes).
        moved_poly = Polygon(new_coords + [new_coords[0]],
                             [list(h.coords)
                              for h in shape.polygon.interiors])
        if not moved_poly.is_valid:
            moved_poly = moved_poly.buffer(0)
        # DEGENERACY TEST.  The retreat must not deform the shape — but
        # "vertex count unchanged" is the WRONG test for that, and it was
        # measured wrong: a ring may carry two vertices closer together
        # than ``SHARED_VERTEX_TOL_M``, which the EMITTER interns to one
        # node regardless.  Retreating both welds them, the count drops by
        # one, and the old test withdrew an otherwise perfect retreat —
        # dropping the shape back onto the emit-consensus adopt.  Measured:
        # KCLT tunnel_ramp #1658 at the taxiway-bridge portal, ring
        # vertices 0.10 m apart, a 12.02 m authority conflict against
        # junction #650 correctly detected at three vertices, three faces
        # correctly built, and the whole retreat withdrawn here — the ramp
        # then adopted the deck's 215.00 m and emitted an 80.5 % / 12.02 m
        # within-shape row (plus its five siblings and the step rows).
        #
        # The law-shaped test: a retreat may weld together only vertices
        # the emitter would already have welded; ANY other vertex loss is a
        # real degeneration and withdraws the retreat.
        _weldable = sum(
            1 for _k in range(n)
            if math.hypot(coords[_k][0] - coords[(_k + 1) % n][0],
                          coords[_k][1] - coords[(_k + 1) % n][1])
            < SHARED_VERTEX_TOL_M)
        _rebuilt_n = (len(_open_coords(moved_poly))
                      if moved_poly.geom_type == "Polygon" else -1)
        if (moved_poly.is_empty
                or moved_poly.geom_type != "Polygon"
                or _rebuilt_n < 3
                or _rebuilt_n > n
                or (n - _rebuilt_n) > _weldable):
            _d(f"RING DEGENERATED: geom={moved_poly.geom_type} "
               f"n_after={_rebuilt_n} vs {n} "
               f"(weldable pairs {_weldable}) -> retreat withdrawn")
            return []  # retreat degenerated the ring — fall back
        shape.polygon = moved_poly
        rebuilt_open = _open_coords(moved_poly)
        if rebuilt_open != new_coords:
            # buffer(0) may rotate the ring start; re-map the
            # altitude list to the rebuilt vertex order.
            new_alts = [float(_nearest_alt(
                new_coords, new_alts, vx, vy))
                for (vx, vy) in rebuilt_open]
        shape.node_altitudes = (
            [round(a, 2) for a in new_alts]
            + [round(new_alts[0], 2)])
    except _GEOM_EXC:
        return []
    # A RETREAT FACE IS EXACTLY THE BAND THE SHAPE VACATED:
    #
    #       face = wall_ring  ∩  footprint_BEFORE  −  footprint_AFTER
    #
    # The subtraction alone was the old rule ("clip out of the RETREATED
    # footprint", the ``_emit_apron_walls`` discipline): it removes the
    # concave-boundary wedge that laps area the retreat KEPT.  It does not
    # remove the wedge that lands OUTSIDE the parent entirely — the wall
    # ring is pinched shut with the run's two ring NEIGHBOURS, and on a
    # concave ring (or a run ending at a corner) the triangle they close
    # can leave the shape altogether and lap whatever stands there.  That
    # is a zero-tolerance self-overlap (``verification.check_self_overlap``
    # scores every emitted polygon, walls included) and it is exactly the
    # class the composed world made reachable: the §2 retreat is standing
    # law now, three wall passes run per build, and the sub-tolerance-weld
    # fix earlier in this session makes retreats FIRE where they used to be
    # withdrawn.
    #
    # Intersecting with the BEFORE footprint states the invariant directly
    # instead of patching its symptoms: the face is the vacated band, so it
    # is contained in the parent's own former footprint and cannot lap any
    # other shape (the parents themselves do not overlap — that is the same
    # invariant one level up).
    clipped_walls: list = []
    for wall in shape_walls:
        try:
            clipped = wall.polygon.difference(shape.polygon)
            if before_poly is not None and not before_poly.is_empty:
                clipped = clipped.intersection(before_poly)
            if clipped.is_empty:
                continue
            if clipped.geom_type == "MultiPolygon":
                clipped = max(clipped.geoms, key=lambda g: g.area)
            if (clipped.geom_type != "Polygon"
                    or clipped.is_empty or clipped.area < 1e-6):
                continue
            pr = _open_coords(clipped)
            if len(pr) < 3:
                continue
            src_ring = list(wall.polygon.exterior.coords)[:-1]
            src_alts = wall.node_altitudes[:len(src_ring)]
            walts = [round(float(_nearest_alt(
                src_ring, src_alts, vx, vy)), 1) for (vx, vy) in pr]
            wall.polygon = clipped
            wall.node_altitudes = walts + [walts[0]]
            clipped_walls.append(wall)
        except _GEOM_EXC as _ce:
            _d(f"CLIP EXC {_ce!r}")
            continue
    _d(f"returned {len(clipped_walls)} clipped face(s) of "
       f"{len(shape_walls)} built")
    return clipped_walls


# ── DEFERRED-JOINT PICKUP (spec seam-continuity-v4 §2 (iii)) ──────────
# "The deferred joints then get their declared wall in the existing pass
#  order ... A joint the wall pass does NOT pick up is a loud record and
#  a pre-registered zero."
#
# PICKUP PREDICATE (pre-registered in the lane's PRE_REG, one number, no
# fitting): a joint is picked up when a face this pass emitted lies
# within ``STACKED_WALL_RETREAT_M + STRIP_SEAM_WALL_STRADDLE_TOL_M`` of
# the joint site — the retreat distance plus the census's own straddle
# slack, i.e. exactly the reach over which the census's straddle
# exemption will recognise the face as spanning the joint.  Lockstep by
# construction: both numbers are the shared law module's / this module's,
# never a third constant.
_STRIP_SEAM_JOINT_PICKUP_M = (
    STACKED_WALL_RETREAT_M + STRIP_SEAM_WALL_STRADDLE_TOL_M)


def _carve_structure_zone(layout):
    """The prepared union of every CARVE STRUCTURE at this airport,
    buffered by ``WALL_CARVE_SITE_RADIUS_M`` — or ``None`` when the
    airport has none (R19-4).

    A carve structure is a tunnel/bridge cut and its portal furniture
    (``_CARVE_STRUCTURE_ROLES`` / ``_CARVE_STRUCTURE_REFS``): the ONE
    place the owner's 2026-08-07 ruling still admits a retaining wall.
    The radius is the portal's own neighbourhood — an abutment wall sits
    beside its structure, not on it — and is a config constant so the
    ruling has one number, not one per call site."""
    from .config import WALL_CARVE_SITE_RADIUS_M
    polys = []
    for sh in (getattr(layout, "shapes", ()) or ()):
        if (sh.role in _CARVE_STRUCTURE_ROLES
                or getattr(sh, "ref", None) in _CARVE_STRUCTURE_REFS):
            if sh.polygon is not None and not sh.polygon.is_empty:
                polys.append(sh.polygon)
    if not polys:
        return None
    try:
        return prep(unary_union(polys).buffer(
            float(WALL_CARVE_SITE_RADIUS_M)))
    except _GEOM_EXC:
        return None


def emit_authority_retreat_walls(layout) -> int:
    """CONSENSUS RETIREMENT §2 — the losing claimant RETREATS.

    ``docs/specs/consensus-retirement-spec.md`` §2, standing law since
    2026-08-05 (the ``O4_SINGLE_AUTHORITY_EMIT`` gate is deleted): at a
    node claimed by several value authorities, ``layout.to_osm`` now
    emits the PRECEDENCE WINNER's value verbatim instead of the tier
    mean.  That is only half the law.  Without the other half a losing
    claimant beyond the merge tolerance is silently DRAGGED to the
    winner's value — the same defect the mean had, minus the averaging;
    it is the measured cause of the groundside tear family.

    THE OTHER HALF, and it already exists: a loser differing by more
    than ``VERTEX_ALT_MERGE_TOL_M`` retreats ``STACKED_WALL_RETREAT_M``
    into its OWN interior and ships the difference as a
    ``retaining_wall`` face (the machine that took HECA's 1 497
    groundside violations to 419).  A loser WITHIN tol adopts, exactly
    as before.  One derivation: the retreat is
    ``_retreat_run_walls``, shared with
    ``emit_stacked_conflict_walls``; the authority half of the site
    table is seam v4's SHARED ``strip_wall_site_index``, extended here
    with the weld-donor (pavement / solver-owned) claims the strip
    index deliberately omits.

    SCOPE, and why it cannot pull airside (airside-is-king).  Only the
    LOSER moves, and the loser is by construction the lower-precedence
    claimant — the runway family outranks everything, so a runway vertex
    is never the retreating party.  Where two solver-owned pavement
    shapes meet they hold the SAME solved value (the canonical identity
    join), so the spread is ~0 and nothing fires: the population this
    reaches is the non-solve collisions §2 names (lot vs ribbon, plate
    lip, pad vs road).

    EXCLUSIONS (each a law of its own, not a tuning knob):
      * tile-seam band vertices — cross-tile contract, consensus merge
        only (``crown._point_in_seam_band``);
      * anything inside a runway-strip footprint — walls at runway edges
        are NEVER lawful (owner 2026-08-01), so the run is skipped and
        the conflict falls back to adoption;
      * soft receivers — they adopt by design and own no value to
        defend;
      * ``graded_strip`` — owned by ``emit_stacked_conflict_walls``,
        which runs first and must see its own population.

    Returns the number of faces emitted.
    """
    from .crown import _point_in_seam_band
    from .layout import (SOFT_RECEIVER_ROLES, WELD_DONOR_ROLES,
                         authority_rank)

    registry = getattr(layout, "canonical_points", None)
    if registry is None:
        return 0
    keepout = runway_strip_wall_keepout(layout)
    # ── THE SITE TABLE ───────────────────────────────────────────────
    # Non-donor authorities come from the SHARED index (built once per
    # layout, already consulted by the cross-strip healer and the
    # stacked-wall pass).  Its ``claims`` are values only, so the ranked
    # table is rebuilt here from the same predicate — but the shared
    # index's EDGE tree is reused verbatim for the edge-coincident case.
    wall_index = strip_wall_site_index(layout)
    ranked: dict = {}
    order_of: dict = {}
    for order, shape in enumerate(getattr(layout, "shapes", ()) or ()):
        role = shape.role or ""
        if role in SOFT_RECEIVER_ROLES or role == ROLE_GRADED_STRIP:
            continue
        rv = _ring_values_for_walls(shape)
        if rv is None:
            continue
        order_of[id(shape)] = order
        coords, alts = rv
        rank = authority_rank(role)
        for (vx, vy), value in zip(coords, alts):
            key = registry.get_or_add(float(vx), float(vy))
            ranked.setdefault(key, []).append(
                (rank, order, float(value), id(shape)))
    if not ranked:
        return 0

    def _winner_over(key, rank, order):
        """The claim that OUTRANKS ``(rank, order)`` at ``key``, or
        ``None`` when this shape is itself the winner."""
        claims = ranked.get(key)
        if not claims or len(claims) < 2:
            return None
        best = min(claims, key=lambda c: (c[0], c[1]))
        if (best[0], best[1]) >= (rank, order):
            return None
        return best[2]

    # THE WALLS RULING (R19-4).  Carve sites keep their wall; every
    # other retreat run becomes a graded FEATHER.
    carve_zone = _carve_structure_zone(layout)
    from .config import ROLE_GRADE_LIMITS, GROUNDSIDE_MAX_GRADE

    emitted = 0
    new_walls: list = []
    _diag = os.environ.get("O4_RETREAT_DIAG") or ""
    for shape in list(getattr(layout, "shapes", ()) or ()):
        role = shape.role or ""
        if role in SOFT_RECEIVER_ROLES or role == ROLE_GRADED_STRIP:
            continue
        rv = _ring_values_for_walls(shape)
        if _diag and role in _diag:
            print(f"  [retreat-diag] role={role} ref={getattr(shape,'ref','')} "
                  f"rv={'None' if rv is None else len(rv[0])} "
                  f"node_alts={'None' if shape.node_altitudes is None else len(shape.node_altitudes)} "
                  f"hi={shape.altitude_high} lo={shape.altitude_low} "
                  f"alt={shape.altitude} "
                  f"nring={0 if shape.polygon is None else len(shape.polygon.exterior.coords)-1} "
                  f"c=({shape.polygon.centroid.x:.1f},{shape.polygon.centroid.y:.1f})",
                  flush=True)
        if rv is None or shape.node_altitudes is None:
            continue
        coords, alts = rv
        n = len(coords)
        if n < 4:
            continue
        rank = authority_rank(role)
        order = order_of.get(id(shape))
        if order is None:
            continue
        coincident_top: list = [None] * n
        spread: list = [0.0] * n
        for i, ((vx, vy), own) in enumerate(zip(coords, alts)):
            key = registry.get_or_add(float(vx), float(vy))
            top = _winner_over(key, rank, order)
            if top is None and role not in WELD_DONOR_ROLES:
                # EDGE-COINCIDENT: this vertex lies ON a designed-split
                # authority's chain rather than on one of its vertices.
                # The shared index's own reader — one derivation.
                top = wall_index.value_at(vx, vy)
                if top is not None and abs(top - own) <= \
                        VERTEX_ALT_MERGE_TOL_M:
                    top = None
            if top is None:
                continue
            sp = abs(top - own)
            if sp <= 0.05:
                continue
            if _point_in_seam_band(layout, vx, vy):
                continue        # cross-tile contract — adopt, no wall
            coincident_top[i] = top
            spread[i] = sp
        # Per-vertex: is this retreat run at a CARVE STRUCTURE?  A wall
        # there is lawful and keeps today's geometry exactly; anywhere
        # else the band must be wide enough to GRADE the step at the
        # loser's own cap (the ruling's own remedy: "where ground must
        # change height it grades").
        _cap = ROLE_GRADE_LIMITS.get(role)
        if not _cap:
            _cap = float(GROUNDSIDE_MAX_GRADE)
        _is_carve = [False] * n
        if carve_zone is not None:
            for i in range(n):
                if coincident_top[i] is None:
                    continue
                try:
                    _is_carve[i] = carve_zone.contains(
                        Point(coords[i][0], coords[i][1]))
                except _GEOM_EXC:
                    _is_carve[i] = False

        def _retreat_m(i, _c=_cap, _carve=_is_carve, _sp=spread):
            if _carve[i]:
                return STACKED_WALL_RETREAT_M
            return max(STACKED_WALL_RETREAT_M,
                       _sp[i] / _c * _FEATHER_RUN_MARGIN)

        def _face_spec(run, _carve=_is_carve, _role=role):
            if any(_carve[i] for i in run):
                return (ROLE_RETAINING_WALL, "authority_retreat_wall")
            # THE FEATHER: the vacated band emits as the LOSER'S OWN
            # surface, so the transition is regulated by that role's
            # grade law instead of hidden inside a relief feature.
            return (_role, "authority_retreat_feather")

        walls = _retreat_run_walls(shape, coords, alts, coincident_top,
                                   spread, keepout,
                                   retreat_m=_retreat_m,
                                   face_spec=_face_spec)
        if _diag and role in _diag:
            print(f"  [retreat-diag]   own={[round(a, 2) for a in alts]} "
                  f"top={[None if t is None else round(t, 2) for t in coincident_top]} "
                  f"spread={[round(s, 2) for s in spread]} "
                  f"walls={len(walls)}", flush=True)
        new_walls.extend(walls)
        emitted += len(walls)
    if new_walls:
        layout.shapes.extend(new_walls)
    return emitted


def report_strip_seam_joint_pickup(layout, new_walls) -> int:
    """Report every DEFERRED AUTHORITY JOINT the wall pass did not pick
    up.  Returns the number of UNPICKED joints (pre-registered zero).
    Read-only."""
    joints = list(getattr(layout, "_strip_seam_deferred_joints", ()) or ())
    if not joints:
        return 0
    icao = str(getattr(layout, "icao", "?") or "?")
    faces = [w.polygon for w in new_walls
             if getattr(w, "polygon", None) is not None
             and not w.polygon.is_empty]
    unpicked = []
    for row in joints:
        point = Point(float(row["x"]), float(row["y"]))
        hit = False
        for face in faces:
            try:
                if face.distance(point) <= _STRIP_SEAM_JOINT_PICKUP_M:
                    hit = True
                    break
            except _GEOM_EXC:
                continue
        if not hit:
            unpicked.append(row)
    UI.vprint(1, f"  {_STRIP_SEAM_DECLINE_TAG} {icao}: deferred authority "
                 f"joints — {len(joints) - len(unpicked)} of {len(joints)} "
                 f"picked up by {len(faces)} stacked-conflict face(s) "
                 f"within {_STRIP_SEAM_JOINT_PICKUP_M:.2f} m; "
                 f"{len(unpicked)} UNPICKED.")
    for position, row in enumerate(unpicked, start=1):
        UI.vprint(1,
                  f"  {_STRIP_SEAM_DECLINE_TAG} JOINT-UNPICKED {icao} "
                  f"{position}/{len(unpicked)}: kind={row['kind']} "
                  f"site=({row['x']:.2f},{row['y']:.2f}) "
                  f"step={row['step_m']:.3f}m "
                  f"planar={row['planar_m']:.3f}m "
                  f"anchored={row['anchors'][0]}/{row['anchors'][1]}")
    return len(unpicked)


# ── GROUNDSIDE TERRACE FACES (owner ruling 2026-07-30) ──────────────────
# "Accept groundside terracing — only pavement and roads need to be graded
#  there, terraces between are acceptable."  (memory ``groundside-terrace-law``;
#  spec docs/specs/reference-honesty-and-terracing-spec.md §2a.)
#
# THE LAW.  Within groundside the GRADED objects are the pavement surfaces
# and the ROADS, each graded along itself under its own cap.  The ground
# BETWEEN them may TERRACE — step without limit, EMITTED AS RETAINING WALLS.
# A groundside region is therefore not required to be one continuous graded
# surface, and a lot whose span exceeds its cap x extent MUST terrace rather
# than hold one level.
#
# WHAT WAS ACTUALLY HAPPENING (measured HECA 2026-07-30, this tree).  The
# 1,497 emitted groundside-internal within-shape violations (worst 390 % =
# 14.78 m over 3.79 m) are NOT a layout-level grading failure: instrumenting
# every groundside pass showed ``_grade_limit_groundside_chords`` leaves the
# rings 4 %-lawful to within 0.02 m, and they are still lawful in the instant
# BEFORE ``to_osm``.  The steps are minted INSIDE the emit consensus.
# ``groundside_pavement`` is not a SOFT_RECEIVER role, so where a graded
# ribbon (service road / junction, apron, terminal, building pad) shares a
# canonical point with a lot, BOTH claims are AUTHORITIES and the consensus
# takes their MEAN — a value belonging to neither law.  HECA lot #1771 (a
# 4.5 m x 141 m band between service_junction #1979 above and lots #780/#786
# below) emitted 89.74 at one long edge and 74.96 at the other: the mean of
# the junction's level and the lot's own, on a ring the limiter had made
# lawful.  Averaging is exactly what the owner's 2026-07-19 no-stacked-nodes
# ruling forbids resolving ("a genuine level change is horizontal wall
# geometry"), and the 2026-07-30 terrace ruling names the geometry: a wall.
#
# THE PASS.  Same machine as ``emit_stacked_conflict_walls`` and the same two
# constants: where a groundside ring vertex is coincident (vertex- or
# edge-wise) with a GRADED RIBBON claim differing by more than
# ``VERTEX_ALT_MERGE_TOL_M``, the LOT retreats ``STACKED_WALL_RETREAT_M`` into
# its own interior and a ``retaining_wall`` face is emitted over the vacated
# band — top row at the ribbon's level, bottom row at the lot's own lawful
# level.  The ribbon keeps its level and its cap (it is a GRADED object); the
# lot keeps its own 4 %-lawful field (it is the ground BETWEEN); the step
# between them is a designated TERRACE LINE and ships as wall geometry.
#
# The terrace lines are therefore a DESIGNATED set — "the boundary where a
# graded ribbon meets the ground at a level the ground's own cap cannot
# reach" — not "wherever the solver struggles"; and the graded ribbons are
# untouched, so they stay continuous along themselves under their own caps.
#
# Gate ``O4_GROUNDSIDE_TERRACE`` (default on).  OFF ⇒ the pass returns 0
# before reading anything ⇒ byte-identical to the pre-ruling emit.
# STANDING LAW (owner 2026-08-05, no gates): the groundside terrace
# ruling (owner 2026-07-30) — only pavement and roads inside groundside
# are graded; the ground between them terraces freely behind retaining
# walls.  The ``O4_GROUNDSIDE_TERRACE`` gate is DELETED.
_GROUNDSIDE_TERRACE = True


def _shape_ring_values(shape):
    """Open exterior ring + aligned per-vertex values, mirroring
    ``to_osm``'s derivation (node_altitudes > flat altitude broadcast >
    sloped-rect high/low corners).  ``None`` when the shape carries no
    elevation or the lists misalign.  (Module-level twin of the closure
    inside ``emit_stacked_conflict_walls`` — the terrace pass needs the
    identical reading, and two readings of "what will emit" would drift.)"""
    from .layout import corner_alts_from_high_low
    poly = shape.polygon
    if poly is None or poly.is_empty or poly.geom_type != "Polygon":
        return None
    try:
        coords = list(poly.exterior.coords)
    except _GEOM_EXC:
        return None
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    if len(coords) < 3:
        return None
    if shape.node_altitudes is not None:
        alts = list(shape.node_altitudes)
        if len(alts) == len(coords) + 1:
            alts = alts[:-1]
        if len(alts) != len(coords):
            return None
        return coords, [float(a) for a in alts]
    if shape.altitude is not None:
        return coords, [float(shape.altitude)] * len(coords)
    if (shape.altitude_high is not None
            and shape.altitude_low is not None and len(coords) == 4):
        return coords, corner_alts_from_high_low(
            float(shape.altitude_high), float(shape.altitude_low))
    return None


def _ring_point_value(coords_a, alts_a, vx, vy, tol):
    """Edge-interpolated value of a ring at ``(vx, vy)``, or ``None`` when
    the point lies farther than ``tol`` from every ring segment."""
    best = None
    na = len(coords_a)
    for i in range(na):
        ax, ay = coords_a[i]
        bx, by = coords_a[(i + 1) % na]
        dx, dy = bx - ax, by - ay
        len2 = dx * dx + dy * dy
        if len2 < 1e-12:
            continue
        t = ((vx - ax) * dx + (vy - ay) * dy) / len2
        t = min(1.0, max(0.0, t))
        px, py = ax + dx * t, ay + dy * t
        d = math.hypot(vx - px, vy - py)
        if best is None or d < best[0]:
            best = (d, (1.0 - t) * alts_a[i] + t * alts_a[(i + 1) % na])
    if best is None or best[0] > tol:
        return None
    return best[1]


def emit_groundside_terrace_walls(layout) -> int:
    """Emit the designated groundside TERRACE FACES (owner ruling
    2026-07-30 — see the block comment above for the law, the measurement
    and the mechanism).  Returns the number of wall faces emitted."""
    if not _GROUNDSIDE_TERRACE:
        return 0
    from .crown import _point_in_seam_band
    from .layout import (
        ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD,
        WELD_DONOR_ROLES)
    from shapely.strtree import STRtree

    registry = getattr(layout, "canonical_points", None)
    if registry is None:
        return 0
    # RUNWAY-STRIP WALL LAW (owner ruling 2026-08-01), the stacked-wall
    # twin: a terrace face inside a runway strip footprint is
    # inadmissible; skipping the run cancels its retreat and the level
    # change falls back to the emit consensus merge.
    _strip_keepout = runway_strip_wall_keepout(layout)
    # ROAD-COURSE WALL LAW (owner ruling 2026-08-12b): a wall may never cut
    # across a service corridor's own course.  Same mechanism as the strip
    # keep-out above — the ruled KCLT lot-road wall dies by construction.
    _corridor_keepout = service_corridor_wall_keepout(layout)

    # GRADED RIBBONS: the objects the law keeps graded inside groundside —
    # the pavement surfaces (apron / taxi / runway families, terminals,
    # building pads) and the ROADS (service road + service junction).  Every
    # one of them is a value AUTHORITY the lot must yield to.
    ribbon_roles = frozenset(WELD_DONOR_ROLES | {
        ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION, ROLE_BUILDING})
    ribbon_claims: dict = {}
    ribbon_edges: list = []          # (exterior, coords, alts)
    # LOT-vs-LOT terraces: two groundside lots meeting on different levels
    # are ALSO a terrace under the ruling — the ground between the graded
    # pieces is not required to be one surface.  Both are AUTHORITIES, so
    # the emit consensus averaged them exactly as it averaged lot-vs-ribbon.
    # Measured at HECA once the ribbon class was resolved: every remaining
    # worst emitted groundside pair, and every new mid-edge step, was
    # lot-vs-lot (#1769 vs #1770, 8.68 m over 0.43 m).  Same rule as the
    # strip pass's soft branch — the TOP holder keeps the point and the
    # LOWER lot retreats, so each terrace gets ONE face, not two.
    lot_claims: dict = {}
    lot_edges: list = []             # (exterior, coords, alts, id(shape))
    for shape in layout.shapes:
        role = shape.role or ""
        if role == ROLE_GROUNDSIDE_PAVEMENT:
            rv = _shape_ring_values(shape)
            if rv is None:
                continue
            coords, alts = rv
            for (vx, vy), value in zip(coords, alts):
                key = registry.get_or_add(float(vx), float(vy))
                lot_claims.setdefault(key, []).append((value, id(shape)))
            try:
                lot_edges.append(
                    (shape.polygon.exterior, coords, alts, id(shape)))
            except _GEOM_EXC:
                pass
            continue
        if role not in ribbon_roles:
            continue
        rv = _shape_ring_values(shape)
        if rv is None:
            continue
        coords, alts = rv
        for (vx, vy), value in zip(coords, alts):
            key = registry.get_or_add(float(vx), float(vy))
            ribbon_claims.setdefault(key, []).append(value)
        try:
            ribbon_edges.append((shape.polygon.exterior, coords, alts))
        except _GEOM_EXC:
            pass
    if not ribbon_claims and not ribbon_edges and not lot_claims:
        return 0
    edge_tree = None
    if ribbon_edges:
        try:
            edge_tree = STRtree([e[0] for e in ribbon_edges])
        except _GEOM_EXC:
            edge_tree = None
    _EDGE_TOL_M = 0.01

    def _ribbon_edge_value(vx, vy):
        if edge_tree is None:
            return None
        try:
            idxs = edge_tree.query_nearest(
                Point(vx, vy), max_distance=_EDGE_TOL_M)
        except _GEOM_EXC:
            return None
        if idxs is None or len(idxs) == 0:
            return None
        _ext, coords_a, alts_a = ribbon_edges[int(idxs[0])]
        return _ring_point_value(coords_a, alts_a, vx, vy, _EDGE_TOL_M)

    lot_edge_tree = None
    if lot_edges:
        try:
            lot_edge_tree = STRtree([e[0] for e in lot_edges])
        except _GEOM_EXC:
            lot_edge_tree = None

    def _lot_edge_value(vx, vy, own_id):
        """Highest OTHER-lot chain value at ``(vx, vy)`` when the point
        lies on another lot's exterior; ``None`` otherwise."""
        if lot_edge_tree is None:
            return None
        try:
            idxs = lot_edge_tree.query(
                Point(vx, vy), predicate="dwithin", distance=_EDGE_TOL_M)
        except _GEOM_EXC:
            return None
        best = None
        for k in idxs:
            _ext, coords_a, alts_a, sid = lot_edges[int(k)]
            if sid == own_id:
                continue
            val = _ring_point_value(coords_a, alts_a, vx, vy, _EDGE_TOL_M)
            if val is not None and (best is None or val > best):
                best = val
        return best

    emitted = 0
    new_walls: list = []
    for shape in layout.shapes:
        if shape.role != ROLE_GROUNDSIDE_PAVEMENT:
            continue
        rv = _shape_ring_values(shape)
        if rv is None or shape.node_altitudes is None:
            continue
        coords, alts = rv
        n = len(coords)
        if n < 4:
            continue
        ribbon_top: list = [None] * n
        spread: list = [0.0] * n
        for i, ((vx, vy), own) in enumerate(zip(coords, alts)):
            key = registry.get_or_add(float(vx), float(vy))
            claims = ribbon_claims.get(key)
            top = (sum(claims) / len(claims) if claims
                   else _ribbon_edge_value(vx, vy))
            if top is None:
                # LOT-vs-LOT terrace: this lot retreats only where another
                # lot holds a HIGHER value at the point (the top holder
                # keeps the weld; equal values are the ordinary shared
                # boundary the chord limiter already unified).
                cluster = lot_claims.get(key)
                if cluster and len(cluster) > 1:
                    others_max = max(
                        (v for (v, sid) in cluster if sid != id(shape)),
                        default=None)
                    if others_max is not None and others_max > own:
                        top = others_max
                if top is None:
                    le = _lot_edge_value(vx, vy, id(shape))
                    if le is not None and le > own:
                        top = le
                if top is None:
                    continue
            sp = abs(top - own)
            if sp <= 0.05:
                continue
            if _point_in_seam_band(layout, vx, vy):
                continue        # cross-tile contract — consensus merge only
            ribbon_top[i] = top
            spread[i] = sp
        primary = [i for i in range(n)
                   if spread[i] > VERTEX_ALT_MERGE_TOL_M]
        if not primary:
            continue
        # Extend each terrace run along ring neighbours still coincident
        # with the ribbon at a real (above emit-rounding) spread, so the
        # level change tapers INSIDE the face instead of stepping against
        # the run's shoulder (the shoulder-tear class the strip pass names).
        selected: set = set(primary)
        for i in primary:
            for step in (1, -1):
                j = i
                while True:
                    j = (j + step) % n
                    if (j in selected or ribbon_top[j] is None
                            or spread[j] <= STACKED_WALL_TAPER_MIN_M):
                        break
                    selected.add(j)
        conflict_top = [ribbon_top[i] if i in selected else None
                        for i in range(n)]
        poly = shape.polygon
        moved_pos: list = [None] * n
        for i in range(n):
            if conflict_top[i] is None:
                continue
            ax, ay = coords[(i - 1) % n]
            bx, by = coords[i]
            cx, cy = coords[(i + 1) % n]
            tx, ty = (cx - ax), (cy - ay)
            norm = math.hypot(tx, ty)
            if norm < 1e-9:
                continue
            tx, ty = tx / norm, ty / norm
            for (nx_, ny_) in ((-ty, tx), (ty, -tx)):
                px = bx + nx_ * STACKED_WALL_RETREAT_M
                py = by + ny_ * STACKED_WALL_RETREAT_M
                try:
                    if poly.contains(Point(px, py)):
                        moved_pos[i] = (px, py)
                        break
                except _GEOM_EXC:
                    continue
        run_indices = [i for i in range(n) if moved_pos[i] is not None]
        if not run_indices:
            continue
        runs: list[list[int]] = []
        current = [run_indices[0]]
        for i in run_indices[1:]:
            if (i - current[-1]) % n == 1:
                current.append(i)
            else:
                runs.append(current)
                current = [i]
        runs.append(current)
        if (len(runs) > 1 and runs[0][0] == 0
                and (runs[-1][-1] + 1) % n == 0):
            runs[0] = runs[-1] + runs[0]
            runs.pop()
        new_coords = list(coords)
        new_alts = list(alts)
        shape_walls: list = []
        for run in runs:
            top_pts = [coords[i] for i in run]
            top_alts_run = [round(float(conflict_top[i]), 1) for i in run]
            bot_pts = [moved_pos[i] for i in run]
            bot_alts_run = [round(float(alts[i]), 1) for i in run]
            prev_i = (run[0] - 1) % n
            next_i = (run[-1] + 1) % n
            ring_pts = ([coords[prev_i]] + top_pts + [coords[next_i]]
                        + bot_pts[::-1])
            ring_alts = ([round(float(alts[prev_i]), 1)] + top_alts_run
                         + [round(float(alts[next_i]), 1)]
                         + bot_alts_run[::-1])
            try:
                wall_poly = Polygon(ring_pts)
                if not wall_poly.is_valid:
                    wall_poly = wall_poly.buffer(0)
                if wall_poly.is_empty or wall_poly.geom_type != "Polygon":
                    continue
            except _GEOM_EXC:
                continue
            rebuilt = _open_coords(wall_poly)
            if len(rebuilt) < 3:
                continue
            if len(rebuilt) == len(ring_pts):
                wall_alts = ring_alts
            else:
                wall_alts = [round(float(_nearest_alt(
                    ring_pts, ring_alts, vx, vy)), 1)
                    for (vx, vy) in rebuilt]
            if (_strip_keepout is not None
                    and wall_poly.intersects(_strip_keepout)):
                continue            # runway-strip wall law (see above)
            if (_corridor_keepout is not None
                    and wall_poly.intersects(_corridor_keepout)):
                continue            # road-course wall law (owner 2026-08-12b)
            shape_walls.append(BuiltShape(
                polygon=wall_poly, role=ROLE_RETAINING_WALL,
                ref="groundside_terrace_wall",
                node_altitudes=wall_alts + [wall_alts[0]]))
            for i in run:
                new_coords[i] = moved_pos[i]
        if not shape_walls:
            continue
        try:
            moved_poly = Polygon(new_coords + [new_coords[0]],
                                 [list(h.coords)
                                  for h in shape.polygon.interiors])
            if not moved_poly.is_valid:
                moved_poly = moved_poly.buffer(0)
            if (moved_poly.is_empty or moved_poly.geom_type != "Polygon"
                    or len(_open_coords(moved_poly)) != n):
                continue        # retreat degenerated the ring — fall back
            shape.polygon = moved_poly
            rebuilt_open = _open_coords(moved_poly)
            if rebuilt_open != new_coords:
                new_alts = [float(_nearest_alt(
                    new_coords, new_alts, vx, vy))
                    for (vx, vy) in rebuilt_open]
            shape.node_altitudes = ([round(a, 2) for a in new_alts]
                                    + [round(new_alts[0], 2)])
        except _GEOM_EXC:
            continue
        clipped_walls: list = []
        for wall in shape_walls:
            try:
                clipped = wall.polygon.difference(shape.polygon)
                if clipped.is_empty:
                    continue
                if clipped.geom_type == "MultiPolygon":
                    clipped = max(clipped.geoms, key=lambda g: g.area)
                if (clipped.geom_type != "Polygon" or clipped.is_empty
                        or clipped.area < 1e-6):
                    continue
                pr = _open_coords(clipped)
                if len(pr) < 3:
                    continue
                src_ring = list(wall.polygon.exterior.coords)[:-1]
                src_alts = wall.node_altitudes[:len(src_ring)]
                walts = [round(float(_nearest_alt(
                    src_ring, src_alts, vx, vy)), 1) for (vx, vy) in pr]
                wall.polygon = clipped
                wall.node_altitudes = walts + [walts[0]]
                clipped_walls.append(wall)
            except _GEOM_EXC:
                continue
        new_walls.extend(clipped_walls)
        emitted += len(clipped_walls)
    layout.shapes.extend(new_walls)
    return emitted


def _ring_edge_reference(coords, ring_alts):
    """The shared ring linear-reference (code motion out of
    ``_make_edge_projection_resampler``, Slice B stage B3 order 2 — the
    solved-surface resampler needs the identical weld-row detection and
    pavement-edge read): returns ``(line, edge_alt_at)`` where ``line``
    is the closed ring ``LineString`` and ``edge_alt_at(s)`` the
    pavement edge altitude at arc length ``s``."""
    pts = list(coords)
    if pts and pts[0] == pts[-1]:
        pass  # keep closed for a continuous LineString
    line = LineString(pts)
    # Cumulative arc length at each coord + a value-filled alt array.
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + math.hypot(pts[i + 1][0] - pts[i][0],
                                        pts[i + 1][1] - pts[i][1]))
    alt = [ring_alts[i] if i < len(ring_alts) else None
           for i in range(len(pts))]
    # Fill None entries (pavement-facing / unsampled ring vertices) so every
    # arc position resolves.  An INTERIOR None run is the LOCAL pavement-edge
    # read: LINEARLY interpolated by arc length between the bracketing known
    # vertices, NOT the previous known value carried forward.  A constant
    # carry-forward borrows the run-END reference across the whole None run,
    # so a band vertex whose foot lands there steps off the pavement line at
    # a seam (shadow rows must mirror the pavement line).  Leading/trailing
    # None runs have no bracket and extend the nearest known value.
    known = [i for i in range(len(alt)) if alt[i] is not None]
    if known:
        lo_ptr = 0
        for i in range(len(alt)):
            if alt[i] is not None:
                continue
            while lo_ptr + 1 < len(known) and known[lo_ptr + 1] < i:
                lo_ptr += 1
            lo = known[lo_ptr] if known[lo_ptr] < i else None
            hi = next((j for j in known if j > i), None)
            if lo is not None and hi is not None:
                span = cum[hi] - cum[lo]
                t = 0.0 if span <= 0 else (cum[i] - cum[lo]) / span
                alt[i] = alt[lo] + t * (alt[hi] - alt[lo])
            else:
                alt[i] = alt[lo if lo is not None else hi]

    def _edge_alt_at(s):
        # Locate the ring segment containing arc length s.
        k = bisect.bisect_right(cum, s) - 1
        k = max(0, min(k, len(pts) - 2))
        seg = cum[k + 1] - cum[k]
        t = 0.0 if seg <= 0 else (s - cum[k]) / seg
        a0, a1 = alt[k], alt[k + 1]
        if a0 is None or a1 is None:
            return a0 if a0 is not None else a1
        return a0 + t * (a1 - a0)

    return line, _edge_alt_at


def _make_edge_projection_resampler(coords, ring_alts, envelope_at,
                                    graded_width_m, sample_dem):
    """Return ``resample(x, y, kind) -> (alt, is_weld_row)`` for band
    vertices of one shape: the DEM **CLAMPED INTO the corridor** at the
    vertex's true lateral distance ``d`` to the pavement edge (shapely
    projection); ``is_weld_row`` marks a vertex ON the ring (d ≤ 2 cm),
    whose value is the pavement edge value verbatim (unrounded),

        alt = min(max(dem, edge + floor(d)), edge + ceiling(d)).

    This is the corridor law applied verbatim (round 2, coordinator
    ruling): the adjacent-ground envelope bounds BOTH sides of the
    emitted surface — unlike the runway-end skirt law, which is a FLOOR
    only, the band may NOT ride a DEM bump above the ceiling (the round-1
    "skirt lift" convention produced 100%+ internal band slopes; unlawful
    here).  Where the DEM sits inside the corridor the clamp returns the
    DEM itself, so the band meets lawful terrain with no step at
    daylight.  Values within ``_CORRIDOR_SNAP_TOL_M`` of a bound emit the
    bound (triangle diet; see the constant).

    ``kind`` keeps the piece's value function CONTINUOUS across the
    corridor's floor discontinuity at the graded width W (finite → None):

      * ``"fill"`` pieces live in zones 1-2 by construction (their band
        cap IS W), so ``d`` clamps to W — outer-row vertices whose
        projection jitters past W stay on the shelf edge instead of
        plunging to the DEM (the round-2 CYXY 25 m in-piece cliff).
      * ``"cut"`` pieces are CEILING-only (floor unapplied): below-floor
        terrain inside a cut piece belongs to the FILL machinery (the
        fill bands emit first and own that footprint — the cut/fill split
        of the flat-shadow convention), and the ceiling is continuous
        over all three zones, so a cut piece spanning the W boundary has
        no value step.

    ``envelope_at(d) -> (floor_offset, ceiling_offset)`` is the family's
    law corridor (``grade_law.adjacent_ground_envelope`` partial).  The
    edge elevation is read by linear-referencing the query's foot along
    the ring against the per-vertex ``ring_alts`` (``None`` entries —
    pavement-facing / unsampled vertices — filled from their nearest
    known neighbour so a foot landing there still resolves).
    """
    line, _edge_alt_at = _ring_edge_reference(coords, ring_alts)

    def resample(x, y, kind):
        p = Point(x, y)
        s = line.project(p)
        edge_alt = _edge_alt_at(s)
        if edge_alt is None:
            return (0.0, False)
        d = p.distance(line)
        if d <= 0.02:
            # WELD ROW (user ruling 2026-07-09): a vertex ON the
            # pavement ring carries the pavement edge value EXACTLY —
            # unrounded, so the emit consensus at the shared node is a
            # no-op and the band abuts the pavement with zero step.
            return (float(edge_alt), True)
        if kind == "fill":
            # Zones 1-2 only (band cap = W); outer-row projection jitter
            # past W must not cross the floor discontinuity.
            d = min(d, graded_width_m)
        floor_offset, ceiling_offset = envelope_at(d)
        if kind == "cut":
            floor_offset = None     # fill bands own below-floor terrain
        dd = sample_dem(x, y)
        if dd is not None:
            value = float(dd)
        elif floor_offset is not None:
            value = float(edge_alt) + floor_offset      # no DEM: law floor
        elif ceiling_offset is not None:
            value = float(edge_alt) + ceiling_offset
        else:
            value = float(edge_alt)
        if floor_offset is not None:
            floor = float(edge_alt) + floor_offset
            # SNAP-TO-BOUND (triangle diet): a DEM within the emit noise
            # band of a corridor bound rides the BOUND, not the jitter —
            # the corridor functions are piecewise-linear, so long
            # near-bound runs become 3D-collinear and decimate away
            # (flat-airport bands otherwise keep every DEM-jitter vertex).
            # Well inside the validator's 0.15 m edge-noise allowance and
            # the DEM's own noise floor; the value stays in the corridor.
            if value <= floor + _CORRIDOR_SNAP_TOL_M:
                value = floor
            value = max(value, floor)
        if ceiling_offset is not None:
            ceiling = float(edge_alt) + ceiling_offset
            if value >= ceiling - _CORRIDOR_SNAP_TOL_M:
                value = ceiling
            value = min(value, ceiling)
        return (round(value, 1), False)

    return resample


def _make_solved_band_resampler(entry, coords, ring_alts,
                                analytic_resample,
                                envelope_at=None, graded_width_m=None):
    """Slice B stage B3 order 2 GATE-ON band valuation: every emitted
    band vertex reads the SOLVED band surface instead of the analytic
    corridor clamp (which runs only gate-OFF — the valuation dies
    gate-ON).  ``entry`` is this shape's construct-store record
    (``zone_rows`` + the writeback's ``zone_values``); ``coords`` /
    ``ring_alts`` are the FINAL solved pavement ring the emit-time march
    ran on.

    Value rule, in precedence order (coordinator ruling 2026-07-11):
      1. WELD ROW (lateral distance <= 2 cm): the pavement edge value
         verbatim — pavement identity, unchanged from the analytic path.
      2. EXACT VARIABLE: a vertex within the canonical-registry
         tolerance (0.5 m) of a solved zone node takes that variable's
         solved value — registry identity, the mechanism that retires
         the adoption/weld apparatus.
      3. ROW INTERPOLATION: otherwise the vertex takes LINEAR
         INTERPOLATION ALONG THE SOLVED ROW it lands on (arc-length
         weighted between the bracketing solver-valued stations —
         the ruled clip-minted-vertex valuation), and where it sits
         BETWEEN two rows, the depth-weighted blend of the two rows'
         interpolants (the value the solved, piecewise-linear band
         surface already implies at that point; the pavement edge
         itself serves as the depth-0 row).  Sound BECAUSE the band law
         has no neighbour coupling — every zone value is independent,
         so regrouping independently-valued vertices onto the emit-time
         footprint cannot violate anything (the order-2 scout
         refutation, ratified).
      4. NO SOLVED ROW in range (an emit-time run the pre-solve
         estimate did not cover): the analytic resampler values the
         vertex and the case is COUNTED loudly
         (``solved_analytic_fallback`` — the B2 degrade convention).

    EMIT-SIDE CORRIDOR READER (2026-07-25, ungated 2026-08-05 —
    full rationale in the config block ``BAND_CORRIDOR_CLAMP_ENABLED``).
    Rules 2-4 above take their value from the SOLVED field, which the
    canonical-point registry interns ACROSS SHAPES: a foreign shape's zone
    node within 0.5 m of this shape's own can claim the variable, and this
    shape's band then emits a value its OWN corridor forbids (SPJC: 34.49 m
    where the apron shoulder corridor is [36.00, 36.06] — a 1.56 m notch).
    So every solved value is finally clamped into this shape's analytic
    corridor ``[edge_alt + floor_off(d), edge_alt + ceil_off(d)]`` — the
    IDENTICAL bounds ``_make_edge_projection_resampler`` enforces by
    construction, read from the same ``grade_law.adjacent_ground_envelope``
    partial and with the same ``kind`` continuity treatment (fill clamps
    ``d`` to the graded width; cut drops the floor).  The weld row (rule 1)
    is pavement identity and is never clamped; the analytic fallback
    (rule 4) is already inside the corridor by construction.  Where the
    clamp bites, this shape and its neighbour emit different values at one
    canonical point — the emitter's supported "deliberate wall of two
    separate nodes" node-split convention (see the adoption block's own
    comment further down this module), not a tear.

    ``envelope_at`` / ``graded_width_m`` are this shape's family corridor
    closure and band cap (``_band_family_closures``); ``None`` (or the gate
    off) disables the clamp and restores the pre-fix values verbatim.
    """
    line, _edge_alt_at = _ring_edge_reference(coords, ring_alts)
    zone_values = entry.get("zone_values") or {}
    # Exact-variable spatial hash at the canonical registry tolerance.
    _EXACT_CELL_M = 0.5
    exact_cells: dict[tuple[int, int],
                      list[tuple[float, float, float]]] = {}
    rows_prepared: list[dict] = []
    for row in entry.get("zone_rows", ()):
        pts = row.get("pts") or []
        vals = [zone_values.get(_vertex_key(px, py)) for px, py in pts]
        keep = [(p, v) for p, v in zip(pts, vals) if v is not None]
        if not keep:
            continue
        for (px, py), v in keep:
            cx = int(math.floor(px / _EXACT_CELL_M))
            cy = int(math.floor(py / _EXACT_CELL_M))
            exact_cells.setdefault((cx, cy), []).append((px, py, v))
        if len(keep) < 2:
            continue
        row_pts = [p for p, _v in keep]
        row_vals = [v for _p, v in keep]
        cum = [0.0]
        for i in range(len(row_pts) - 1):
            cum.append(cum[-1] + math.hypot(
                row_pts[i + 1][0] - row_pts[i][0],
                row_pts[i + 1][1] - row_pts[i][1]))
        try:
            row_line = LineString(row_pts)
        except _GEOM_EXC:
            continue
        depths = row.get("depths") or []
        row_depths = [d for (_p, _v), d in zip(zip(pts, vals), depths)
                      if _v is not None]
        if len(row_depths) != len(row_pts):
            row_depths = [row.get("d0", 0.0)] * len(row_pts)
        rows_prepared.append({"kind": row["kind"], "line": row_line,
                              "cum": cum, "vals": row_vals,
                              "depths": row_depths})

    def _lerp_along(cum, vals, s):
        k = bisect.bisect_right(cum, s) - 1
        k = max(0, min(k, len(cum) - 2))
        seg = cum[k + 1] - cum[k]
        t = 0.0 if seg <= 0 else (s - cum[k]) / seg
        return vals[k] + t * (vals[k + 1] - vals[k])

    # Beyond this lateral distance a row is not a plausible value source
    # for the query (reach-scale sanity bound).
    _ROW_RANGE_M = 30.0
    # A projected row depth within this of the query's own lateral
    # distance means the query sits ON that row (the on-edge lerp case).
    _ON_ROW_TOL_M = 0.5

    # EMIT-SIDE CORRIDOR CLAMP (see the docstring).  Structurally inert
    # with the gate off or without a corridor closure: ``_clamp`` is then
    # the identity on its ``value`` argument and costs one predicate.
    _clamp_on = bool(_BAND_CORRIDOR_CLAMP) and envelope_at is not None

    def _clamp(p, d, kind, value):
        """THE LOCKSTEP READER of the zone-law box at depth ``d``.

        Since the ingestion this is NOT a second valuation: the SAME box
        (``zone_corridor_box``, one derivation) is supplied to the solve
        as a directed constraint through
        ``layout.adjacent_ground_zone_boxes``, so a solved value already
        lies inside it and this reader returns it untouched.  Every
        metre it still has to move is an INGESTION RESIDUAL — counted
        (``band_corridor_clamped_vertices``), and a number that goes to
        zero when the solve consumes the table.  Until then it is also
        the only guard on the measured cross-shape collision (SPJC: the
        canonical registry interns two shapes' zone nodes 0.19 m apart
        into ONE variable, and this shape's band then emits a value its
        OWN corridor forbids — a 1.56 m notch).  The at-source fix is
        the ``shape_id`` the box table carries.

        No snap-to-bound: a value already inside the corridor is
        returned untouched, so the reader only ever bites on the
        population it targets.
        """
        global _BAND_CLAMP_MAX_DELTA_M
        if not _clamp_on:
            return value
        edge_alt = _edge_alt_at(line.project(p))
        if edge_alt is None:
            return value
        floor_offset, ceiling_offset = zone_corridor_box(
            envelope_at, graded_width_m, kind, d)
        out = value
        if floor_offset is not None:
            out = max(out, float(edge_alt) + floor_offset)
        if ceiling_offset is not None:
            out = min(out, float(edge_alt) + ceiling_offset)
        delta = abs(out - value)
        if delta > 1e-9:
            _APPARATUS_HITS["band_corridor_clamped_vertices"] += 1
            if delta > _BAND_CLAMP_MAX_DELTA_M:
                _BAND_CLAMP_MAX_DELTA_M = delta
        return out

    def resample(x, y, kind):
        p = Point(x, y)
        d = p.distance(line)
        if d <= 0.02:
            # Weld row: pavement edge value verbatim (identity).
            edge_alt = _edge_alt_at(line.project(p))
            if edge_alt is None:
                return (0.0, False)
            return (float(edge_alt), True)
        # 1) exact variable adoption (registry-tolerance hash).
        cx = int(math.floor(x / _EXACT_CELL_M))
        cy = int(math.floor(y / _EXACT_CELL_M))
        best_v = None
        best_d = _EXACT_CELL_M
        for ox in (cx - 1, cx, cx + 1):
            for oy in (cy - 1, cy, cy + 1):
                for px, py, v in exact_cells.get((ox, oy), ()):
                    dd = math.hypot(x - px, y - py)
                    if dd < best_d:
                        best_d, best_v = dd, v
        if best_v is not None:
            _APPARATUS_HITS["solved_exact_variable"] += 1
            return (round(_clamp(p, d, kind, float(best_v)), 1), False)
        # 2) row interpolation on the solved band surface.
        candidates = []
        for row in rows_prepared:
            if row["kind"] != kind:
                continue
            try:
                s = row["line"].project(p)
                dist = row["line"].distance(p)
            except _GEOM_EXC:
                continue
            if dist > _ROW_RANGE_M:
                continue
            candidates.append(
                (dist, _lerp_along(row["cum"], row["depths"], s),
                 _lerp_along(row["cum"], row["vals"], s)))
        if not candidates:
            _APPARATUS_HITS["solved_analytic_fallback"] += 1
            return analytic_resample(x, y, kind)
        candidates.sort(key=lambda c: c[0])
        prim_dist, prim_depth, prim_val = candidates[0]
        if abs(prim_depth - d) <= _ON_ROW_TOL_M:
            _APPARATUS_HITS["solved_row_on"] += 1
            return (round(_clamp(p, d, kind, float(prim_val)), 1), False)
        below = None      # deepest row not deeper than the query
        above = None      # shallowest row not shallower than the query
        for dist, depth, val in candidates:
            if depth <= d and (below is None or dist < below[0]):
                below = (dist, depth, val)
            if depth >= d and (above is None or dist < above[0]):
                above = (dist, depth, val)
        if below is None:
            # The pavement edge is the depth-0 row.
            edge_alt = _edge_alt_at(line.project(p))
            if edge_alt is None:
                _APPARATUS_HITS["solved_analytic_fallback"] += 1
                return analytic_resample(x, y, kind)
            below = (0.0, 0.0, float(edge_alt))
        if above is None:
            # Outward of the deepest solved row: clamp to it (counted —
            # the geometry is reported rather than a fallback invented).
            _APPARATUS_HITS["solved_beyond_coverage"] += 1
            return (round(_clamp(p, d, kind, float(below[2])), 1), False)
        span = above[1] - below[1]
        t = 0.0 if span <= 0 else (d - below[1]) / span
        value = below[2] + t * (above[2] - below[2])
        _APPARATUS_HITS["solved_row_interpolated"] += 1
        return (round(_clamp(p, d, kind, float(value)), 1), False)

    return resample


def _runway_end_skirt_prep(layout):
    """Prepared union of the runway-END REGIME polygons, or ``None`` — the
    WRAP join target (scope A).  The regime is BOTH refs on the
    ``runway_clearance`` role (``layout.RUNWAY_END_REGIME_REFS``): the fill
    skirt and, with arc A2's gate on, the RESA cut.  Both are end-regime
    surfaces the taxiway corridor must JOIN, not treat as an obstruction —
    a taxiway end abutting the cut is the same geometry problem as one
    abutting the skirt.  Prepared once per emission/construction and passed
    to the taxiway march so the terrain-facing probe can tell an end-regime
    surface (join) from real pavement (skip)."""
    polys = [s.polygon for s in layout.shapes
             if getattr(s, "ref", None) in RUNWAY_END_REGIME_REFS
             and s.polygon is not None and not s.polygon.is_empty]
    if not polys:
        return None
    try:
        return prep(unary_union(polys))
    except _GEOM_EXC:
        return None


def _crossing_zone_union(layout):
    """The published crossing influence zone union, or ``None`` (Phase 1,
    docs/specs/crossing-terrain-ownership.md).  Replaces every crossing
    reconstruction this module used to do itself: the crossing-union
    branch of the standoff block, the road-lane exclusion, and the
    buried-span carve-out (the buried roof is bandable BY CONSTRUCTION —
    the published zone contains only the road bore over the buried span)."""
    from .crossing_terrain import crossing_influence_zone_union
    return crossing_influence_zone_union(layout)


def _crossing_zone_prep(layout):
    """Prepared form of the published crossing zone for the march's
    station test, or ``None``."""
    from .crossing_terrain import crossing_influence_zone_prepared
    return crossing_influence_zone_prepared(layout)


def _collar_zone_union(layout):
    """The published COLLARED-POCKET zone union, or ``None`` (arc B1,
    ``gap_fill.collared_pocket_zone_union``).  A width-skipped pocket
    whose collar rings EMITTED is the collar's ground: the rings already
    carry the drainage law across it, so no band may march in beside them
    (two governing surfaces over one patch of terrain — the X-Plane crash
    class).  Unlike a treated gap, such a pocket has no gap FACE, so the
    band march's 1.5 m covered-frontage probe cannot see it — hence this
    explicit zone, consumed exactly like the crossing zone."""
    from .gap_fill import collared_pocket_zone_union
    return collared_pocket_zone_union(layout)


def _collar_zone_prep(layout):
    """Prepared form of the published collared-pocket zone for the
    march's station test, or ``None``."""
    from .gap_fill import collared_pocket_zone_prepared
    return collared_pocket_zone_prepared(layout)


def _enclave_zone_union(layout):
    """The published AIRSIDE-ENCLAVE band keep-out union, or ``None``
    (``enclaves.enclave_band_keepout_union``).

    Owner 2026-08-07: everything inside an airside-surrounded enclave —
    paved or bare — is airside-interior and takes the gap interior ring +
    spine treatment; "a retaining wall or groundside terrace there is a
    defect regardless of which mechanism minted it".  So no band and no
    retaining face may OCCUPY that ground.

    Scoped by ``enclaves`` to the POCKET-width regions of the GAP LAW'S
    OWN union (pavement only) — the keep-out must agree with the ruled
    treatment about which ground it OWNS.  An airfield INFIELD is a
    bounded complement component too, and its graded strips are Annex 14
    §3.4.11-13 ground the bands own, so the width test is what keeps the
    keep-out off it.

    CONSUMED AS GEOMETRY, never as a station predicate (SCOPING v2).
    There is deliberately no prepared-geometry twin of this function any
    more: a ``prep(...).contains(station)`` test is only available to a
    consumer that stands STATIONS down, and that consumer is exactly what
    the HECA measurement retired (``_station_reference_ex``).  The two
    live consumers are the band clip in ``emit_adjacent_ground_bands``
    and ``_emit_apron_walls``' ``enclave_keepout``; the VALIDATOR keeps
    its own prepared form (``verification._airside_enclave_zone_prep``),
    where a station predicate is the right shape — it suppresses a
    coverage flag at a station whose band this clip removed, and it
    cannot delete anything."""
    from .enclaves import enclave_band_keepout_union
    return enclave_band_keepout_union(layout)


def _tunnel_ramp_standoff_block(layout):
    """1 m buffered union of the tunnel mouth pieces to stand strips off
    (scope B), or ``None``.  The set is ``tunnel_ramp`` sloped rects + the
    ``retaining_wall`` U-walls the tunnel portal emits BEFORE the band
    stage; object-bridge PLATES (bridge_trench / bridge_causeway) are
    excluded by construction (they are pavement-equivalent graph members).
    Built from the current ``layout.shapes`` at emit entry, so the apron-edge
    ``retaining_wall`` pieces ``_emit_apron_walls`` appends later are not yet
    present and are naturally excluded.

    LEGACY pieces only: recognized crossings (corridor deck boxes,
    tunnel-portal-pair regions, collar rings, the depressed-road corridor)
    are covered by the published crossing influence zone
    (``_crossing_zone_union``), not reconstructed here — Phase 1 of
    docs/specs/crossing-terrain-ownership.md."""
    polys = [s.polygon for s in layout.shapes
             if s.role in (ROLE_TUNNEL_RAMP, ROLE_RETAINING_WALL)
             and s.polygon is not None and not s.polygon.is_empty]
    if not polys:
        return None
    try:
        block = unary_union(polys).buffer(_PAVEMENT_GAP_M)
        return None if block.is_empty else block
    except _GEOM_EXC:
        return None


def seam_offcut_union(layout):
    """Union of the neighbour-tile pavement OFFCUTS ``tile_cut`` recorded on
    ``layout.tile_seam_offcuts`` (see ``tile_cut._SEAM_OFFCUT_ROLES``), or
    ``None`` when this build cut nothing away — every single-tile airport,
    where the seam prolongation is therefore a strict no-op.

    This is the ONLY evidence a tile build has of where its pavement really
    continues past the seam, and it is exact (the dropped pieces ARE the
    neighbour's halves), so a prolongation can never invent pavement."""
    if not _SEAM_PROLONG:
        return None
    offcuts = getattr(layout, "tile_seam_offcuts", None)
    if not offcuts:
        return None
    try:
        u = unary_union([p for p in offcuts
                         if p is not None and not p.is_empty])
    except _GEOM_EXC:
        return None
    return None if (u is None or u.is_empty) else u


def _tile_cutback_lines(layout, coords, half_width_m):
    """The tile CUT-BACK lines this ring sits on, as
    ``(axis, line_coord, inward_sign)`` triples in LOCAL METRES —
    ``axis`` 0 for the x (integer LONGITUDE) family, 1 for y (integer
    LATITUDE); ``inward_sign`` points from the line INTO the current tile.

    ``tile_cut`` subtracts a ``2 * half_width_m`` band centred on each
    integer line, so a shape that crossed one ends on the line
    ``x_int +/- half_width_m`` — that is the cut-back edge the owner's
    "clean line along the cut" names."""
    if layout.anchor is None:
        return []
    lat0, lon0 = layout.anchor
    cos0 = math.cos(math.radians(lat0))
    out: list[tuple[int, float, int]] = []
    for axis in (0, 1):
        vals = [c[axis] for c in coords]
        lo, hi = min(vals), max(vals)
        # Local metres -> degrees on this axis, and the inverse scale.
        per_deg = (math.radians(1.0) * R_EARTH * cos0 if axis == 0
                   else math.radians(1.0) * R_EARTH)
        if per_deg <= 0.0:
            continue
        origin = lon0 if axis == 0 else lat0
        d_lo = origin + lo / per_deg
        d_hi = origin + hi / per_deg
        for n in range(int(math.floor(d_lo)) - 1, int(math.ceil(d_hi)) + 2):
            c_int = (n - origin) * per_deg
            for sgn in (1, -1):
                c = c_int + sgn * half_width_m
                if not any(abs(v - c) <= _SEAM_CUTBACK_TOL_M for v in vals):
                    continue
                # The ring must live on the INWARD side of its own
                # cut-back line (a piece bounded by ``x_int + half`` is the
                # +x piece); otherwise this is a coincidence, not a cut.
                mean = sum(vals) / float(len(vals))
                if sgn * (mean - c) < 0.0:
                    continue
                out.append((axis, c, sgn))
    return out


def _seam_prolong_length(u, n, axis, sgn, depth_cap):
    """Geometric prolongation length (m) for one flanking frontage edge:
    how far past the cut-back corner the pavement must be continued before
    a corridor of depth ``depth_cap`` off that edge can no longer reach
    BACK across the cut line into this tile.

    ``u`` is the prolongation direction (away from the ring interior along
    the flanking edge), ``n`` that edge's OUTWARD normal.  Points on the
    prolonged corridor are ``A + s*u + d*n``; the in-tile test
    ``sgn * ((A + s*u + d*n)[axis] - c) >= 0`` with ``A`` on the line
    reduces to ``s * (sgn*u[axis]) + d * (sgn*n[axis]) >= 0``, so the
    largest useful ``s`` is ``depth_cap * (sgn*n[axis]) / -(sgn*u[axis])``.
    Zero when the corridor faces AWAY from the line (nothing to recover) or
    the edge does not actually cross it."""
    cu = sgn * u[axis]
    cn = sgn * n[axis]
    if cu >= 0.0 or cn <= 0.0:
        return 0.0
    return float(depth_cap) * cn / max(-cu, _SEAM_PROLONG_MIN_COS)


def _seam_prolong_run(ring, alt_arrays, i0, i1, axis, sgn, ccw,
                      depth_cap, offcut_union):
    """Prolong ONE cut-back run ``ring[i0..i1]`` (its vertices all sit on
    the cut line).  Returns ``(a_pt, b_pt, a_alts, b_alts)`` — the two new
    ring vertices continuing the flanking frontage edges and their
    extrapolated altitudes, one per array in ``alt_arrays`` — or ``None``
    when nothing should be prolonged."""
    m = len(ring)
    p_pt = ring[(i0 - 1) % m]
    a_pt = ring[i0]
    b_pt = ring[i1]
    q_pt = ring[(i1 + 1) % m]
    ua = _unit(a_pt[0] - p_pt[0], a_pt[1] - p_pt[1])
    ub = _unit(b_pt[0] - q_pt[0], b_pt[1] - q_pt[1])
    if ua is None or ub is None:
        return None
    # Outward normals of the two flanking RING edges (P->A and B->Q).
    na = (ua[1], -ua[0]) if ccw else (-ua[1], ua[0])
    ubq = (-ub[0], -ub[1])
    nb = (ubq[1], -ubq[0]) if ccw else (-ubq[1], ubq[0])
    length = max(_seam_prolong_length(ua, na, axis, sgn, depth_cap),
                 _seam_prolong_length(ub, nb, axis, sgn, depth_cap))
    if length <= 0.0:
        return None
    length = min(length, _SEAM_PROLONG_MAX_M)
    # OFFCUT BOUND: probe down the MIDDLE of the continuing pavement (the
    # cut-back run's midpoint, along the mean prolongation direction) and
    # keep only as much length as real dropped pavement supports.
    umid = _unit(ua[0] + ub[0], ua[1] + ub[1])
    if umid is None:
        return None
    mid = (0.5 * (a_pt[0] + b_pt[0]), 0.5 * (a_pt[1] + b_pt[1]))
    try:
        probe = LineString([mid, (mid[0] + umid[0] * length,
                                  mid[1] + umid[1] * length)])
        hit = probe.intersection(offcut_union.buffer(_SEAM_OFFCUT_HALO_M))
    except _GEOM_EXC:
        return None
    if hit.is_empty:
        return None
    reach = 0.0
    for geom in (getattr(hit, "geoms", None) or [hit]):
        try:
            xs, ys = geom.coords.xy
        except (AttributeError, NotImplementedError, _GEOM_EXC):
            continue
        for hx, hy in zip(xs, ys):
            reach = max(reach, (hx - mid[0]) * umid[0]
                        + (hy - mid[1]) * umid[1])
    length = min(length, reach)
    if length <= _SEAM_CUTBACK_TOL_M:
        return None
    a_new = (a_pt[0] + ua[0] * length, a_pt[1] + ua[1] * length)
    b_new = (b_pt[0] + ub[0] * length, b_pt[1] + ub[1] * length)

    def _extrapolate(values, i_end, i_prev, anchor):
        """Reference altitude at the prolonged vertex: the flanking edge's
        own gradient continued (grade-capped), so the corridor keeps
        referencing the pavement profile rather than jumping to terrain."""
        v_end = values[i_end] if i_end < len(values) else None
        v_prev = values[i_prev] if i_prev < len(values) else None
        if v_end is None:
            return None
        if v_prev is None:
            return v_end
        span = math.hypot(ring[i_end][0] - ring[i_prev][0],
                          ring[i_end][1] - ring[i_prev][1])
        if span < 1e-6:
            return v_end
        grade = (v_end - v_prev) / span
        grade = max(-_SEAM_PROLONG_MAX_GRADE,
                    min(_SEAM_PROLONG_MAX_GRADE, grade))
        return v_end + grade * anchor

    a_alts = [_extrapolate(v, i0, (i0 - 1) % m, length) for v in alt_arrays]
    b_alts = [_extrapolate(v, i1, (i1 + 1) % m, length) for v in alt_arrays]
    return a_new, b_new, a_alts, b_alts


def _seam_prolonged_ring(layout, coords, ccw, alt_arrays, depth_cap,
                         offcut_union, half_width_m=TILE_CUT_HALF_WIDTH_M):
    """Splice every tile-cut CUT-BACK run of a pavement ring back out to the
    pavement's real continuation, so the adjacent-ground corridor marches
    off an UN-CUT frontage and the tile cut — not the march — decides where
    the band ends (owner ruling 2026-07-24).

    Returns ``(coords, alt_arrays, n_prolonged)``; the inputs are returned
    UNCHANGED (same objects) whenever nothing is prolonged, so every
    non-seam-crossing airport is byte-identical.

    The splice is deliberately LOCAL: the ring keeps every real pavement
    vertex (the band's inner weld row is untouched) and only the run of
    cut-back vertices is replaced by ``A -> A' -> B' -> B``, where ``A'``
    and ``B'`` continue the two flanking frontage edges.  The corridor the
    march then builds beyond the cut line is removed by the post-emit
    ``cut_layout_at_tile_boundaries``, leaving the band bounded BY the cut
    line — collinear with the pavement's own cut-back edge."""
    if (not _SEAM_PROLONG or offcut_union is None
            or layout.anchor is None or len(coords) < 5):
        return coords, alt_arrays, 0
    lines = _tile_cutback_lines(layout, coords, half_width_m)
    if not lines:
        return coords, alt_arrays, 0
    ring = list(coords[:-1])
    arrays = [list(v[:len(ring)]) for v in alt_arrays]
    n_done = 0
    for axis, c, sgn in lines:
        on = [abs(v[axis] - c) <= _SEAM_CUTBACK_TOL_M for v in ring]
        if not any(on) or all(on):
            continue
        # Rotate so index 0 is OFF the line — runs then never wrap.
        k = on.index(False)
        ring = ring[k:] + ring[:k]
        arrays = [v[k:] + v[:k] for v in arrays]
        on = on[k:] + on[:k]
        runs: list[tuple[int, int]] = []
        i = 0
        while i < len(ring):
            if on[i]:
                j = i
                while j + 1 < len(ring) and on[j + 1]:
                    j += 1
                if j > i:            # a lone on-line vertex is a corner
                    runs.append((i, j))
                i = j + 1
            else:
                i += 1
        for i0, i1 in reversed(runs):
            spliced = _seam_prolong_run(ring, arrays, i0, i1, axis, sgn,
                                        ccw, depth_cap, offcut_union)
            if spliced is None:
                continue
            a_new, b_new, a_alts, b_alts = spliced
            head, tail = ring[i0], ring[i1]
            head_a = [v[i0] for v in arrays]
            tail_a = [v[i1] for v in arrays]
            ring[i0:i1 + 1] = [head, a_new, b_new, tail]
            for ai, v in enumerate(arrays):
                v[i0:i1 + 1] = [head_a[ai], a_alts[ai],
                                b_alts[ai], tail_a[ai]]
            n_done += 1
    if not n_done:
        return coords, alt_arrays, 0
    try:
        poly = Polygon(ring)
        if poly.is_empty or not poly.is_valid:
            return coords, alt_arrays, 0
    except _GEOM_EXC:
        return coords, alt_arrays, 0
    return (ring + [ring[0]],
            [v + [v[0]] for v in arrays],
            n_done)


def _family_params(layout, shape, rw_axes):
    """Resolve ``(family, code_number, code_letter, reach, width, axis,
    axis_line)`` for one airside ``shape``; ``None`` if the shape is out of
    scope.

    ``axis`` is the nearest runway-axis unit vector (runway shapes only)
    used to skip END ring edges; ``width`` is the graded-band half-width
    (fill cap).  ``axis_line`` is that same nearest runway axis as a
    ``LineString`` (runway shapes only, else ``None``) — arc A4 measures
    each station's distance to the CENTERLINE off it, because the
    Annex-14 half-width ``width`` is defined from the centreline while the
    march spends it from the pavement edge."""
    role = shape.role
    if role in _RUNWAY_ROLES:
        if not rw_axes:
            return None
        try:
            cen = shape.polygon.centroid
            axis = min(rw_axes, key=lambda a: a[0].distance(cen))
        except (_GEOM_EXC + (ValueError,)):
            return None
        code_number = runway_code_number(axis[2])
        # PHASE B: ruleset-keyed graded half-width (§4 row 6).
        width = _ruleset_strip_half_width_m(
            code_number, None, grade_law_ruleset_of(layout))
        # Slot 4 (optional, "one S"): the runway's two END approach
        # classes.  Absent on legacy 3-tuple axes records — the march
        # falls back to the conservative instrument geometry then.
        classes = axis[3] if len(axis) > 3 else None
        return ("runway", code_number, None,
                CLEARANCE_MAX_REACH_M["runway"], width, axis[1], axis[0],
                classes)
    if role in _TAXIWAY_ROLES:
        letter = taxi_shape_code_letter(layout, shape)
        width = taxiway_strip_graded_half_width_for_letter(letter)
        return ("taxiway", None, letter,
                CLEARANCE_MAX_REACH_M["taxiway"], width, None, None,
                None)
    if role in _APRON_ROLES:
        return ("apron", None, None,
                CLEARANCE_MAX_REACH_M["taxiway"], APRON_SHOULDER_WIDTH_M,
                None, None, None)
    return None


def _nearest_alt(points, alts, x, y):
    """Altitude of the nearest ``(points, alts)`` sample to ``(x, y)`` —
    the resampler for clip-introduced band vertices.  Bands are stationed
    at ``step`` (5 m) and adjacent bands share boundary rows, so the
    nearest source vertex reproduces the graded surface to within a
    fraction of the fill trigger and never tears at a band seam."""
    best_d = None
    best_a = 0.0
    for (px, py), a in zip(points, alts):
        dd = (px - x) * (px - x) + (py - y) * (py - y)
        if best_d is None or dd < best_d:
            best_d = dd
            best_a = a
    return best_a


def _band_family_closures(family, code_number, code_letter, width):
    """The three family-parameterized corridor closures the march + value
    passes share (``ceil_off``/``envelope_at`` unbounded on ``d``,
    ``floor_depth`` clamped to the graded width so the fill floor stays
    finite — see the inline docstrings the emitter carried).  Single-sourced
    so the pre-solve construction and the post-solve emitter read the corridor
    identically."""
    def ceil_off(d):
        return adjacent_ground_envelope(family, code_number, code_letter, d)[1]

    def envelope_at(d):
        return adjacent_ground_envelope(family, code_number, code_letter, d)

    def floor_depth(d):
        f = adjacent_ground_envelope(
            family, code_number, code_letter, min(d, width))[0]
        return None if f is None else -f

    return ceil_off, envelope_at, floor_depth


def zone_corridor_box(envelope_at, graded_width_m, kind: str, d: float):
    """THE ZONE-LAW BOX at lateral depth ``d`` — ONE derivation.

    Returns ``(floor_off, ceil_off)`` relative to the band node's DATUM
    (the pavement-edge elevation at its foot).  ``kind == "fill"`` clamps
    ``d`` to the graded width so an outer-row vertex whose projection
    jitters past W stays on the shelf; ``kind == "cut"`` drops the floor
    (below-floor terrain inside a cut piece belongs to the fill
    machinery).

    THREE CONSUMERS, ONE FUNCTION — this is the point of it:
      1. ``build_zone_constraint_table`` — the SOLVE-TIME constraint
         supply (``layout.adjacent_ground_zone_boxes``);
      2. the pre-solve zone-node envelope offsets;
      3. ``_make_solved_band_resampler``'s emit-side reader, which since
         the ingestion is a LOCKSTEP check of the same numbers rather
         than a second valuation.
    A fourth copy of these bounds is how the cross-shape corridor
    collision (SPJC, 1.56 m notch) was argued about for a week.
    """
    dd = float(d)
    if kind == "fill" and graded_width_m is not None:
        dd = min(dd, float(graded_width_m))
    floor_off, ceil_off = envelope_at(dd)
    if kind == "cut":
        floor_off = None
    return floor_off, ceil_off


def _ring_foot_reference(coords, x: float, y: float):
    """The FOOT of a band node on its host shape's ring, as an IDENTITY
    rather than a value: ``(i, t)`` such that the foot is
    ``(1-t)·coords[i] + t·coords[i+1]``.

    This is the datum the zone law is actually written against
    (``grade_law.adjacent_ground_envelope`` references the pavement-EDGE
    elevation at the node's foot).  The solve currently approximates it
    with the frozen-nearest host VERTEX, which on a long steep edge sits
    metres off the local foot lerp (measured 12 m at the CYXY trench
    wall) — and the B3 writeback then patched that up POST-solve by
    re-deriving the value from raw DEM.  Carrying the foot as two ring
    vertices and a parameter lets the constraint be stated exactly, in
    the solve, against variables the solve already owns.
    """
    best = None
    n = len(coords)
    if n < 2:
        return None
    for i in range(n - 1):
        (ax, ay), (bx, by) = coords[i], coords[i + 1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            continue
        t = ((x - ax) * dx + (y - ay) * dy) / L2
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        px, py = ax + dx * t, ay + dy * t
        d = math.hypot(x - px, y - py)
        if best is None or d < best[0]:
            best = (d, i, t)
    if best is None:
        return None
    return (best[1], best[2], best[0])


def _strip_law_params(layout, shape, rw_axes, trigger_by_family,
                      with_envelope=False):
    """The STRIP family's corridor parameters for a NON-runway ``shape``
    whose frontage reaches into a lateral runway strip (§1 law swap).

    ``(floor_depth, ceil_off, width, reach, trigger, axis_line)`` — the same
    six values ``_family_params`` + ``_band_family_closures`` give the
    runway family, keyed on the NEAREST runway (its code number sets the
    graded half-width, its axis line is what the per-station width clamp
    measures from).  ``with_envelope=True`` appends the family's
    ``envelope_at`` closure, which the EMITTER needs to value the strip-law
    bands through the strip corridor rather than the shape's own.

    ``None`` when there is no runway to key on — the caller then leaves the
    shape's own law in charge, which is the honest fallback.

    ONE resolver for the pre-solve constructor, the emitter and (through
    the same numbers) the validator: a second copy would let the three
    disagree about which law owns a station."""
    if not rw_axes:
        return None
    try:
        cen = shape.polygon.centroid
        near = min(rw_axes, key=lambda a: a[0].distance(cen))
    except (_GEOM_EXC + (ValueError, AttributeError)):
        return None
    code = runway_code_number(near[2])
    # PHASE B: the graded half-width is RULESET-KEYED (§4 row 6 — FAA
    # Appendix G 76.2 m vs ICAO 75 m at code 4), never a bare constant
    # read at a law site.
    width = float(_ruleset_strip_half_width_m(
        code, None, grade_law_ruleset_of(layout)))
    ceil_off, envelope_at, floor_depth = _band_family_closures(
        "runway", code, None, width)
    params = (floor_depth, ceil_off, width,
              CLEARANCE_MAX_REACH_M["runway"],
              trigger_by_family["runway"], near[0])
    return params + (envelope_at,) if with_envelope else params


def _strip_longitudinal_law_for(layout, shape, rw_axes):
    """``(max_slope, arc_rate_per_m)`` of the NEAREST runway's strip, or
    ``None``.  Same nearest-runway resolution as ``_strip_law_params`` —
    one law resolver for the march trigger, the clamp and the validator."""
    if not rw_axes:
        return None
    try:
        cen = shape.polygon.centroid
        near = min(rw_axes, key=lambda a: a[0].distance(cen))
    except (_GEOM_EXC + (ValueError, AttributeError)):
        return None
    return strip_longitudinal_law(runway_code_number(near[2]),
                                  ruleset=grade_law_ruleset_of(layout))


def _strip_longitudinal_demand(stations, strip_mask, axis_line, sample_dem,
                               law):
    """§A3(a) — THE MISSING TRIGGER TERM, as a per-station boolean.

    THE GAP THIS CLOSES.  The adjacent-ground march emits a band where the
    ground leaves the corridor LATERALLY — that is the only question its
    per-station ray scan asks.  Ground that sits inside the corridor at
    every depth but breaches the strip's OWN longitudinal law
    (Annex 14 §3.4.13/§3.4.14, AC §3.16.5) against its neighbouring
    stations was therefore never emitted at all: no band, so no vertex,
    so the §2 clamp (``runway_strip_longitudinal_clamp``) never saw it,
    and ``check_grade`` read raw DEM.  ``strip_longitudinal_breaches``
    was written for exactly this trigger and had no production caller.

    ONE DERIVATION.  The run splitting is
    ``grade_law.runway_strip_longitudinal_runs`` and the predicate is
    ``grade_law.strip_longitudinal_breaches`` — the same two functions the
    clamp and ``check_grade._check_strip_longitudinal_grade`` /
    ``_check_strip_arc_rate`` use, so the trigger, the shaping and the
    judgment cannot disagree about which stations the law governs.

    A breach at station ``k`` implicates the PAIR (and, for the arc term,
    the triple) it is read on, so ``k-1``, ``k`` and ``k+1`` are all
    demanded: shaping one end of an unlawful pair without the other just
    moves the step.

    ``None`` when there is no strip law, no axis, or nothing breaches —
    the callers then pass ``None`` through and the builders are
    byte-identical.
    """
    if law is None or axis_line is None or not stations:
        return None
    max_slope, arc_rate = law
    if not max_slope:
        return None
    try:
        (ax, ay) = axis_line.coords[0]
        (bx, by) = axis_line.coords[-1]
    except (_GEOM_EXC + (IndexError, AttributeError)):
        return None
    length = math.hypot(bx - ax, by - ay)
    if length < 1e-9:
        return None
    ux, uy = (bx - ax) / length, (by - ay) / length
    inside = [bool(m) for m in strip_mask]
    if not any(inside):
        return None
    zs = [sample_dem(sx, sy) for (sx, sy) in stations]
    demand = [False] * len(stations)
    hit = False
    for run in runway_strip_longitudinal_runs(stations, (ux, uy), inside):
        s_axis = [stations[i][0] * ux + stations[i][1] * uy for i in run]
        z_run = [zs[i] for i in run]
        for k in strip_longitudinal_breaches(
                s_axis, z_run, max_slope, arc_rate):
            for j in (k - 1, k, k + 1):
                if 0 <= j < len(run):
                    demand[run[j]] = True
                    hit = True
    if not hit:
        return None
    _APPARATUS_HITS["strip_longitudinal_demanded_stations"] += sum(
        1 for d in demand if d)
    return demand


def _shape_ring_alts(s, coords, sample_dem=None, seed=False):
    """Per-CLOSED-ring node altitudes aligned with ``coords`` (the
    ``node_altitudes`` contract), else the shape's plane sampler.

    ``seed=True`` (pre-solve construction): entries the shape does not yet
    carry — the taxi/apron/junction rings are unsolved before
    ``per_surface_solve`` — are filled from the smoothed DEM
    (``sample_dem``) rather than left ``None``, so the pre-solve MARCH scans
    the corridor off the DEM-seeded pavement-edge estimate (the design's
    directive; runway rings are already CIFP-solved and keep their real
    values).  ``seed=False`` reproduces the emitter's exact solved-value
    read (byte-identical gate-OFF)."""
    na = s.node_altitudes
    if na:
        nm = min(len(na), len(coords))
        ring_alts = [None if na[i] is None else float(na[i])
                     for i in range(nm)]
        ring_alts += [None] * (len(coords) - nm)
    elif s.altitude is not None:
        ring_alts = [float(s.altitude)] * len(coords)
    else:
        ring_alts = [_sample_runway_segment_elev(s, x, y)
                     for x, y in coords]
    if seed and sample_dem is not None:
        for i, (x, y) in enumerate(coords):
            if ring_alts[i] is None:
                dd = sample_dem(x, y)
                if dd is not None:
                    ring_alts[i] = float(dd)
    return ring_alts


def _build_construct_reach_band(layout):
    """Slice B stage B3 ORDER 3 (coverage-gap closure): the pavement REACH
    BAND, built at PRE-SOLVE construct time.

    The band contract is ``band(x, y) -> (floor, ceiling) | None`` — the
    interval every solved pavement/spine node's elevation is confined to by
    the unified grade graph (``reach_band_unified``, the SAME band the solve
    and the validator use).  It is a pure function of the pavement geometry,
    the taxi centerlines and the CIFP runway anchors — none of which the
    solve has yet moved at construct time (runway profiles carry real values
    from birth; ``build_unified_graph`` derives its runway anchors from the
    shapes, not from a solved ``elev`` vector) — so the band is computable
    BEFORE ``per_surface_solve``.  Building it is cheap (~1 s at CYXY: the
    graph build dominates; the Dijkstra reach fields and the closure are
    sub-0.1 s).  Returns the closure, or ``None`` on any failure (the caller
    then keeps the DEM-seeded march — a loud degrade, never a crash).

    NOTE the double build: the solve builds the same band again inside
    ``reach_band_for``.  The band is a pure geometry closure (index-
    independent), so the two agree; sharing it across the pre-solve/solve
    boundary would couple the construct to the runway-flex re-anchoring the
    solve performs after this point, so the construct deliberately keeps its
    own (pre-flex) band — a valid bound on the solved value regardless (flex
    only tightens the reachable interval).

    MEASURED AND REJECTED (perf P3 lane F, 2026-08-13): sharing this band
    with the OTHER pre-solve band —
    ``route_profile.apron_terrace.presolve_anchor_envelope``, three
    statements earlier — through a fingerprint-guarded memo.  The premise
    was that the panelizer usually splits nothing (HECA declares ZERO
    joints), so the second graph would be the first graph.  It is not:
    ``gap_fill.construct_gap_fill_presolve`` runs BETWEEN the two slots and
    its spine vertices ARE admitted to ``_build_node_list``, so the node
    space, the building-key set and the gap-fill store all move and the two
    builds are two DIFFERENT graphs.  A memo (built, twinned on 24 guard
    inputs, byte-identical at HECA) missed 100 % of the time and was
    reverted.  The duplication here is real work, not repeated work; the
    lever on ``grade_graph.shape_constraints`` — 108.6 s over 14,465
    computations in six graph builds per HECA solve, because its per-shape
    memo lives on the CONTEXT and every build gets a fresh one — is inside
    ``grade_graph`` itself, not in this caller.
    """
    try:
        from .elevation_per_surface.solver_primitives import _build_node_list
        from . import grade_graph as _GG
        from .elevation_per_surface.building_feasibility import (
            reach_band_unified)
        _nodes, bucket_to_idx = _build_node_list(layout)
        ctx = _GG.build_context(layout, bucket_to_idx)
        G = _GG.build_unified_graph(layout, bucket_to_idx, ctx=ctx)
        return reach_band_unified(layout, G)
    except Exception as _band_exc:                            # pragma: no cover
        UI.vprint(1, f"  [adjacent-ground] WARN: construct reach-band build "
                     f"FAILED ({_band_exc!r}) — DEM-seeded march kept "
                     f"(coverage degrade).")
        return None


def _worst_case_ring_alts(s, coords, band, sample_dem):
    """Slice B stage B3 ORDER 3 worst-case pavement-edge references for the
    pre-solve construct march.

    Returns ``(ring_alts_cut, ring_alts_fill)`` — two per-vertex edge-altitude
    arrays that bound the SOLVED edge value from the two violating sides, so
    the marched band FOOTPRINT is a SUPERSET of any solved outcome BY
    CONSTRUCTION (no magic margin — the bound IS the reach band):

      * ``ring_alts_cut`` uses the band FLOOR: a CUT fires where terrain rises
        above ``edge + ceiling_offset``; the solved edge can drop no lower
        than the floor, so the floor maximises the cut set — every solved
        cut station is covered (``solved_edge >= floor`` ⇒
        ``{terrain > solved+ceil} ⊆ {terrain > floor+ceil}``).
      * ``ring_alts_fill`` uses the band CEILING: a FILL fires where terrain
        falls below ``edge − floor_depth``; the solved edge can rise no higher
        than the ceiling, so the ceiling maximises the fill set.

    (SCOUT CORRECTION 2026-07-11: the work-order's parenthetical had these
    swapped — "band CEILING for cut … band FLOOR for fill" — which yields the
    SUBSET, not the superset.  Cut needs the LOWEST edge, fill the HIGHEST.
    Derived above and confirmed against the marchers' detection tests
    ``dd > ref + ceil`` / ``dd < ref − floor``.)

    Only entries the shape does NOT yet carry a real value for (the unsolved
    taxi/apron/junction rings, ``node_altitudes[i] is None``) are substituted;
    runway rings keep their CIFP values in both arrays.  Where the band is
    ``None`` (an unreachable vertex) the DEM seed is kept — the pre-order-3
    behaviour, no regression."""
    base = _shape_ring_alts(s, coords)     # no seed → None where unsolved
    ring_alts_cut = list(base)
    ring_alts_fill = list(base)
    for i, (x, y) in enumerate(coords):
        if base[i] is not None:
            continue
        bv = band(x, y) if band is not None else None
        if bv is not None and bv[0] is not None and bv[1] is not None:
            ring_alts_cut[i] = float(bv[0])       # floor  → cut coverage
            ring_alts_fill[i] = float(bv[1])      # ceiling → fill coverage
        else:
            dd = sample_dem(x, y)
            if dd is not None:
                ring_alts_cut[i] = float(dd)
                ring_alts_fill[i] = float(dd)
    return ring_alts_cut, ring_alts_fill


def _coverage_grid_edges(base_edges, cap):
    """Densify a band-edge set with intermediate depths every
    ``ADJACENT_GROUND_COVERAGE_DEPTH_STEP_M`` out to ``cap`` — the depth
    grid the full-extent coverage grid stages so a solved zone row of each
    kind sits within the resampler's ``_ROW_RANGE_M`` of every emit-time
    band vertex.  Off the coverage gate this is never called."""
    edges = set(base_edges)
    from .config import ADJACENT_GROUND_COVERAGE_DEPTH_STEP_M as _dstep
    d = _dstep
    while d < cap:
        edges.add(float(d))
        d += _dstep
    return edges


def _derive_shape_stations_and_bands(coords, ccw, ring_alts, axis, width,
                                     reach, trigger, floor_depth, ceil_off,
                                     step, prep_static, seam_keys,
                                     sample_dem, zone_rows_out=None,
                                     wrap_skirt_prep=None, ring_alts_fill=None,
                                     coverage_grid=False,
                                     crossing_zone_prep=None,
                                     collar_zone_prep=None,
                                     strip_zone_prep=None,
                                     strip_law=None,
                                     strip_longitudinal=None,
                                     strip_bands_out=None,
                                     axis_line=None,
                                     axis_classes=None,
                                     prolonged_keys=None,
                                     fill_station_filter=None):
    """Frontage detection + corridor MARCH for one airside shape — the band
    FOOTPRINT geometry (everything that decides WHERE the bands are, given the
    edge-altitude references ``ring_alts``).  Returns
    ``(fill_bands, cut_bands, stations, st_alts, outs)``; the two band lists
    are the raw ``(ring_open, alts_open)`` pairs the emitter later clips and
    values.  Extracted verbatim from the emitter's per-shape setup so the
    pre-solve constructor and the post-solve emitter march identically (the
    B2 shared-helper pattern — parity single-sourced, not duplicated).

    ``zone_rows_out`` (Slice B stage B3 order 2, pre-solve constructor
    only): a list that receives one dict per band ZONE ROW —
    ``{"kind", "d0", "pts", "depths", "hosts", "ref_alts"}`` — where a
    zone row is
    every band row at lateral depth > 0 (the d0 == 0 weld row is the
    pavement chain itself, never a zone row) and ``hosts`` is the
    frozen-nearest pavement RING VERTEX per station (the B2
    frozen-nearest pattern: every ring vertex is a solver variable, so
    the envelope interval edge is mappable to a node index at
    constraint-build time).  ``ref_alts`` is the station's OWN frontage
    altitude — the value the band's analytic surface is built on — kept
    beside the host so a consumer can tell the two apart (the seam
    prolongation's host repair needs exactly that difference).  ``None``
    (every post-solve caller): no collection, byte-identical.

    ``wrap_skirt_prep`` (Slice B stage B3 order 3, scope A — taxiway-end
    wrap; passed only for TAXIWAY shapes with O4_ADJACENT_GROUND_END_WRAP
    ON): a prepared runway-END skirt union.  A station whose terrain-facing
    probe lands ONLY on a skirt is then kept (the skirt is the wrap's join
    target, not an obstruction) so the corridor wraps the taxiway end onto
    the skirt.  ``None`` (default; runways, aprons, gate OFF): the probe
    skips every static hit exactly as before — byte-identical.

    ``ring_alts_fill`` (Slice B stage B3 order 3, coverage closure; passed
    only by the pre-solve construct march under band admission): a SECOND
    per-vertex edge-altitude array — the reach-band CEILING — used for FILL
    detection, while the positional ``ring_alts`` carries the reach-band
    FLOOR used for CUT detection (see ``_worst_case_ring_alts``).  ``None``
    (default; every post-solve/emit caller): both directions read the single
    ``ring_alts`` — byte-identical to before order 3.

    ``crossing_zone_prep`` (Phase 1, docs/specs/crossing-terrain-
    ownership.md; supersedes the round-6 road-lane exclusion): the
    PREPARED published crossing influence zone (``_crossing_zone_prep``).
    A station whose seed point OR outward probe falls inside the zone is
    dropped exactly like the end-edge / covered-probe skips, so the
    taxiway-end wrap fan never sweeps into a crossing or its depressed
    road corridor (bands never wrap a ramp/approach end — user ruling
    2026-07-15).  ``None`` (default; nothing published — no crossings, no
    depressed road): no zone test — byte-identical.

    ``prolonged_keys`` (tile-seam prolongation, pre-solve constructor
    only): the vertex keys of the SYNTHETIC ring vertices
    ``_seam_prolonged_ring`` spliced in.  Purely informational — each zone
    row records, per point, whether its station sits on a PROLONGED ring
    edge (``host_pro``), which is what the constructor's host repair needs
    to know to keep the law corridor referenced to the prolonged frontage
    rather than to the cut-back corner.  ``None`` (default; every emit
    caller, every ring with no prolongation): all flags False —
    byte-identical.

    ``collar_zone_prep`` (arc B1, ``_collar_zone_prep``): the PREPARED
    published COLLARED-POCKET zone — the pockets whose drainage collar
    rings actually emitted.  Tested exactly like the crossing zone, for
    EVERY family (a pocket is ringed by mixed roles — runway, taxiway and
    apron edges all face the same hole), so the collar and the bands
    never govern the same ground.  ``None`` (default; nothing collared):
    no zone test — byte-identical.

    The AIRSIDE-ENCLAVE keep-out takes NO parameter here, deliberately
    (SCOPING v2): it is a keep-out over GROUND and is differenced out of
    the band GEOMETRY at emission, never applied to the station anchors
    — see ``_station_reference_ex`` for the measurement that ruled it.

    ``strip_zone_prep`` / ``strip_law`` / ``strip_bands_out`` (STRIP
    PRECEDENCE §1, ``O4_STRIP_PRECEDENCE``; passed only for NON-RUNWAY
    families — see ``runway_strip_lateral_zone``).  ``strip_zone_prep`` is
    the prepared LATERAL strip footprint; a station whose seed OR outward
    probe falls inside it is governed by the STRIP family instead of this
    shape's own — the station is KEPT, its law is swapped.  ``strip_law``
    carries that family's ``(floor_depth, ceil_off, width, reach, trigger,
    axis_line)``; ``strip_bands_out``, when given, receives the strip-law
    bands as ``(kind, band)`` pairs instead of merging them into the
    returned lists, so the emitter can value them through the STRIP
    corridor (the pre-solve constructor passes ``None`` and takes them
    merged — its consumer is the tagged zone-row store).  ``None``
    (default; runway family, gate off): no zone test, single build —
    byte-identical.

    ``strip_longitudinal`` (§A3(a), ``(max_slope, arc_rate_per_m)`` from
    ``_strip_longitudinal_law_for``): completes the march's emission
    TRIGGER.  The lateral scan alone never emitted a band over ground that
    stays inside the corridor at every depth but breaches the strip's own
    along-axis slope / arc law, so that ground reached the validator
    unshaped — the §A3(a) gap.  With this the strip arm additionally
    obstructs every station ``_strip_longitudinal_demand`` names, and the
    §2 clamp then shapes it.  ``None`` (default): no second term —
    byte-identical.

    ``fill_station_filter`` (APRON WALL SCOPE, owner ruling 2026-07-25 —
    passed only for APRON shapes with ``O4_APRON_WALL_SCOPE`` ON; see
    ``apron_wall_frontage_qualifier``): ``qualifies(sx, sy) -> bool``.  A
    station it rejects faces OPEN TERRAIN, which the ruling leaves
    UNGOVERNED ON THE FILL SIDE — the raw DEM grades right up to the apron
    edge — so its FILL reference is nulled and no fill band, and therefore
    no fill zone row, is built there.  The CUT side is untouched: terrain
    standing above the clearance ceiling is a wingtip obstruction wherever
    it stands.  ``None`` (default; every other family, gate off): no
    filtering — byte-identical."""
    if ring_alts_fill is None:
        ring_alts_fill = ring_alts

    # Reasons ``_station_reference`` may skip a station.  Only the END
    # reason is exported (arc A3): such a station sits at depth 0 because
    # the END REGIME owns it, not because the terrain there is lawful —
    # so its neighbours must not be benched down toward it.
    _SKIP_END = "end"

    # BUILD-TIME GUARD for the collared-pocket test below (mirrored in
    # ``verification._adjacent_ground_stations``).  A prepared containment
    # is ~1 µs and the seed ``Point`` another ~2 µs, and this march runs
    # over EVERY airside station of the airport (SPJC: ~35,000) while a
    # collared pocket spans a few hundred metres — measured 199 ms of pure
    # zone test per march, cut to 18 ms by rejecting the seed against each
    # zone PART's bounding box first (per PART, not the union bbox: two
    # pockets at opposite ends of the field give a union box covering the
    # whole airport, which prunes nothing).
    #
    # Exactly equivalent to the raw test: the probe lies ``_RING_PROBE_M``
    # from the seed, so a seed outside every part box inflated by that
    # distance cannot have either point inside the zone.
    _collar_boxes = None
    if collar_zone_prep is not None:
        try:
            _zone = collar_zone_prep.context
            _parts = list(getattr(_zone, "geoms", [])) or [_zone]
            _collar_boxes = [(b[0] - _RING_PROBE_M, b[1] - _RING_PROBE_M,
                              b[2] + _RING_PROBE_M, b[3] + _RING_PROBE_M)
                             for b in (g.bounds for g in _parts)]
        except (AttributeError, IndexError, ValueError):
            _collar_boxes = None

    def _station_reference_ex(sx, sy, out, alt_value):
        # The station's edge altitude and, when it is SKIPPED, the reason
        # — the END-edge rule (skirt / RESA territory) + the
        # terrain-facing probe, applied per station exactly as the
        # validator does.  Returns ``(alt_or_None, reason_or_None)``;
        # ``_station_reference`` below is the value-only view of this one
        # body, so the value and the reason can never diverge.
        if alt_value is None:
            return (None, "no_alt")
        if (axis is not None
                and abs(out[0] * axis[0] + out[1] * axis[1])
                > _RING_END_NORMAL_DOT):
            return (None, _SKIP_END)
        probe = Point(sx + out[0] * _RING_PROBE_M,
                      sy + out[1] * _RING_PROBE_M)
        # CROSSING-ZONE EXCLUSION (Phase 1): a station whose seed or
        # outward probe falls inside the published crossing influence
        # zone is dropped — bands never wrap a ramp/approach end and
        # never march into a crossing.  Inert without a published zone
        # (``crossing_zone_prep is None``).
        if crossing_zone_prep is not None and (
                crossing_zone_prep.contains(Point(sx, sy))
                or crossing_zone_prep.contains(probe)):
            _APPARATUS_HITS["wrap_crossing_zone_excluded_stations"] += 1
            return (None, "crossing_zone")
        # COLLARED-POCKET EXCLUSION (arc B1): a station whose seed or
        # outward probe falls inside a pocket whose drainage COLLAR RINGS
        # emitted is dropped — the collar governs that ground and a band
        # marching in beside it would double-govern it.  The
        # covered-frontage probe below cannot catch this: a width-skipped
        # pocket has no gap face to stand the bands down.  Inert without a
        # published zone (``collar_zone_prep is None``).
        if (collar_zone_prep is not None
                and (_collar_boxes is None
                     or any(bx0 <= sx <= bx1 and by0 <= sy <= by1
                            for bx0, by0, bx1, by1 in _collar_boxes))
                and (collar_zone_prep.contains(Point(sx, sy))
                     or collar_zone_prep.contains(probe))):
            _APPARATUS_HITS["collar_zone_excluded_stations"] += 1
            return (None, "collared_pocket")
        # AIRSIDE ENCLAVE: NOT A STATION SKIP (SCOPING v2, spec
        # docs/specs/enclave-region-law-spec.md; the v1 test lived
        # exactly here).  The enclave keep-out is a statement about
        # GROUND — the pocket regions the gap ring + spine owns — and a
        # STATION is not ground: it is the anchor of a row that marches
        # ``reach`` metres outward, so standing a station down deletes
        # band over everything that row covers, most of which the
        # keep-out does not own.  Measured at HECA: 11,274 stations stood
        # down took 150,438 m² of Annex 14 §3.4.11-13 graded strip out of
        # WIDE regions (short side 1,264 m) the keep-out never claimed,
        # against 10,840 m² inside its own pocket territory — a 14:1
        # overreach, and adjudicated airside rose in both worlds.  The
        # keep-out is applied to the band GEOMETRY instead, clipped at
        # the region boundary, in ``emit_adjacent_ground_bands`` (and to
        # the wall faces in ``_emit_apron_walls``): a row spanning
        # pocket→WIDE keeps its WIDE extent by construction.
        # RUNWAY-STRIP PRECEDENCE (§1) is NOT a station skip — see the
        # ``strip_law`` block below.  The station is KEPT and its
        # GOVERNING LAW is swapped to the strip family (lead ruling
        # 2026-08-04: "no other role's law may govern" was never "no law
        # governs"; deferring left ground inside a strip Annex 14
        # §3.4.11-13 says must be prepared at raw DEM).
        if prep_static.contains(probe):
            # WRAP (scope A): a taxiway station whose outward probe lands
            # ONLY on a runway-END skirt is the JOIN target, not an
            # obstruction — keep it so the corridor wraps the taxiway end
            # and lands on the skirt chain (the exact clip + snap-to-static
            # weld the wrap ring onto the skirt verbatim).  Any other static
            # hit (pavement, another junction) still skips.
            if not (wrap_skirt_prep is not None
                    and wrap_skirt_prep.contains(probe)):
                return (None, "static")
        return (alt_value, None)

    def _station_reference(sx, sy, out, alt_value):
        """The station's edge altitude, or ``None`` when it is skipped."""
        return _station_reference_ex(sx, sy, out, alt_value)[0]

    stations, st_alts, outs = [], [], []
    # FILL-direction reference per station (order 3 worst-case coverage).
    # Identical object as ``st_alts`` when ``ring_alts_fill is ring_alts``
    # (the default) so the fill/cut split is a structural no-op off order 3.
    st_alts_fill: list = st_alts if ring_alts_fill is ring_alts else []
    _split_refs = st_alts_fill is not st_alts
    is_ring_vertex: list[bool] = []
    at_seam: list[bool] = []
    # Arc A3: per-station "skipped by the END-NORMAL test SPECIFICALLY"
    # (not by the terrain-facing probe, the crossing-zone test, or a
    # missing altitude).  Built unconditionally — it is one string compare
    # per station off a call the march already makes — and consumed only
    # under ``_END_PIN``, so the gate-OFF march is byte-identical.
    end_skipped: list[bool] = []
    # Frozen-nearest host pavement ring vertex per station (zone-row
    # admission; built unconditionally — cheap — consumed only through
    # ``zone_rows_out``).  A fan station sits AT its corner (a ring
    # vertex); an edge station takes the nearer edge endpoint.
    hosts: list[tuple[float, float]] = []
    # Per-station "this station sits on a tile-seam PROLONGED ring edge"
    # (either endpoint synthetic).  All False without ``prolonged_keys``.
    host_pro: list[bool] = []
    previous_out = None
    for i in range(len(coords) - 1):
        eax, eay = coords[i]
        ebx, eby = coords[i + 1]
        u = _unit(ebx - eax, eby - eay)
        if u is None:
            continue
        out = (u[1], -u[0]) if ccw else (-u[1], u[0])
        a0 = ring_alts[i]
        a1 = ring_alts[i + 1]
        a0f = ring_alts_fill[i]
        a1f = ring_alts_fill[i + 1]
        edge_pro = bool(prolonged_keys) and (
            _vertex_key(eax, eay) in prolonged_keys
            or _vertex_key(ebx, eby) in prolonged_keys)
        # CORNER FAN (coverage): at a CONVEX ring corner insert stations AT
        # the corner with normals interpolated across the turn so the band
        # outer row follows the fan arc piecewise (see the emitter's inline
        # docstring for the sagitta rationale).
        if previous_out is not None:
            cross = previous_out[0] * out[1] - previous_out[1] * out[0]
            convex = (cross > 1e-9) if ccw else (cross < -1e-9)
            # NO fan across a SKIPPED flank (runway END edge / covered
            # probe): interpolated fan rays would sweep into skipped
            # territory as blade spikes.
            #
            # ARC A3 RE-DERIVATION (deliberate, keep as is): the end pin
            # gives the LAST EDGE station full lawful depth at a runway
            # end corner, so one might argue the fan could now sweep that
            # corner too.  It must NOT.  A fan's stations all SHARE the
            # corner coordinate, so ``adjacent_ground_supported_depths``'
            # distance weighting grants them NO depth allowance over the
            # corner's own depth — the exact geometry that made the
            # CYXY-417 fan blade, and a fan sweeping INTO the end zone
            # would re-mint that class inside the wedge the skirt / RESA
            # regime already owns.  The end regime owns that wedge; the
            # lateral band ends square against it (which is precisely what
            # the pin buys) and the two surfaces meet at the clip.
            if convex and (
                    _station_reference(eax, eay, previous_out,
                                       a0) is None
                    or _station_reference(eax, eay, out,
                                          a0) is None):
                convex = False
            if convex:
                angle_previous = math.atan2(previous_out[1],
                                            previous_out[0])
                delta = math.atan2(out[1], out[0]) - angle_previous
                while delta > math.pi:
                    delta -= 2.0 * math.pi
                while delta < -math.pi:
                    delta += 2.0 * math.pi
                fan_steps = int(math.ceil(abs(delta)
                                          / _FAN_MAX_STEP_RAD))
                for f in range(1, fan_steps):
                    fan_angle = (angle_previous
                                 + delta * f / fan_steps)
                    fan_out = (math.cos(fan_angle),
                               math.sin(fan_angle))
                    stations.append((eax, eay))
                    _fan_ref, _fan_reason = _station_reference_ex(
                        eax, eay, fan_out, a0)
                    st_alts.append(_fan_ref)
                    if _split_refs:
                        st_alts_fill.append(_station_reference(
                            eax, eay, fan_out, a0f))
                    outs.append(fan_out)
                    is_ring_vertex.append(True)
                    at_seam.append(False)
                    end_skipped.append(_fan_reason == _SKIP_END)
                    hosts.append((eax, eay))
                    host_pro.append(edge_pro)
        previous_out = out
        nseg = max(1, int(math.ceil(
            math.hypot(ebx - eax, eby - eay) / step)))
        edge_a_seam = _vertex_key(eax, eay) in seam_keys
        edge_b_seam = _vertex_key(ebx, eby) in seam_keys
        for k in range(nseg):    # next edge owns the far corner
            t = k / nseg
            sx = eax + (ebx - eax) * t
            sy = eay + (eby - eay) * t
            ref = None
            reason = "no_alt"
            if a0 is not None and a1 is not None:
                ref, reason = _station_reference_ex(
                    sx, sy, out, a0 + t * (a1 - a0))
            stations.append((sx, sy))
            st_alts.append(ref)
            if _split_refs:
                ref_f = None
                if a0f is not None and a1f is not None:
                    ref_f = _station_reference(
                        sx, sy, out, a0f + t * (a1f - a0f))
                st_alts_fill.append(ref_f)
            outs.append(out)
            is_ring_vertex.append(k == 0)
            at_seam.append((k == 0 and edge_a_seam)
                           or (k == nseg - 1 and edge_b_seam))
            end_skipped.append(reason == _SKIP_END)
            hosts.append((eax, eay) if t < 0.5 else (ebx, eby))
            host_pro.append(edge_pro)
    if len(stations) < 2:
        return [], [], stations, st_alts, outs
    m = len(stations)
    # Seam-taper pin instrumentation (order-2 confirmation row): the
    # count of stations flagged AT a pavement-partition seam — the pin's
    # input firing set (the pin itself acts on footprint depths inside
    # ``grade_law.adjacent_ground_supported_depths``).  Expected
    # UNCHANGED between admission OFF and ON.
    _APPARATUS_HITS["seam_taper_flagged_stations"] += sum(
        1 for _f in at_seam if _f)

    # ── ARC A3: END-AWARE BENCH PIN ─────────────────────────────────
    # A runway END-edge station carries depth 0 only because the march
    # SKIPS it (``_SKIP_END``) — the end is skirt / RESA territory — but
    # ``adjacent_ground_supported_depths`` cannot tell that from genuinely
    # unobstructed ground, so it benches the lateral wing diagonally down
    # into the end corner (measured SPJC 16R 2026-07-24: 75 m of depth
    # collapsing to 3 m over the last 48 m, every vertex exactly on
    # ``2.0 x distance-back-from-corner``).  The fix reuses the EXISTING
    # pin mechanism verbatim — the ``at_continuation_seam`` semantics
    # ("never lowered by either sweep, holds its raw scanned depth") — by
    # OR-ing the end-pin flags into the same per-station list.  No second
    # mechanism; the law decides WHICH stations, ``grade_law`` owns both.
    # Counted AFTER the seam-taper row above so that row keeps meaning
    # exactly "stations at a pavement-partition seam".
    if _END_PIN:
        _end_pin = adjacent_ground_end_pin_flags(
            end_skipped, [a is not None for a in st_alts])
        _APPARATUS_HITS["end_pin_flagged_stations"] += sum(
            1 for _f in _end_pin if _f)
        at_seam = [bool(_s) or bool(_p)
                   for _s, _p in zip(at_seam, _end_pin)]

    # ── ARC A4: RUNWAY STRIP WIDTH MEASURED FROM THE CENTERLINE ─────
    # ``width`` is the Annex-14 graded-strip HALF-WIDTH from the runway
    # CENTERLINE, but the march spends it (and the family reach) outward
    # from the pavement EDGE — and the emitted runway carries apt.dat
    # shoulders (SPJC 16R/34L: 45 m -> 81 m), so the band lands 115.5 m
    # from the centreline where the strip is 75 m.  With the gate ON each
    # station's caps become the strip width REMAINING outward of it, via
    # ``grade_law.runway_strip_band_width_m`` — the same clamp legacy
    # Pass A3 applied (``rw_axis[2] - rw_axis[0].distance(station)``).
    # Applied to BOTH directions as each is currently derived: the fill
    # cap stays bounded by ``width``, the cut cap by the family ``reach``.
    fill_caps = [width] * m
    cut_caps = [reach] * m
    # A4 clamps the FILL ONLY.  Filling is a GRADED-strip mandate, so the
    # graded half-width is the right bound for it — and applying that same
    # bound to the CUT (as A4 first did) erases zone 3 entirely: ICAO
    # Annex 14 §3.4.16 governs the UNGRADED strip too (ceiling ≤5 % up, out
    # to the FULL strip edge), so a cut stopping at the graded edge is a
    # functional regression, not a tightening.  At a station 40.5 m off the
    # axis that cap was 34.5 m where the law reaches 99.5 m.  The cut cap
    # belongs to the OLS handover block below, which measures S on the full
    # strip; with OLS off the cut keeps today's zone-3-to-reach stand-in.
    # Each gate is then independently sound, so they need no coupling.
    if _STRIP_WIDTH_FROM_CENTERLINE and axis_line is not None:
        for _i, (_sx, _sy) in enumerate(stations):
            try:
                _d_axis = axis_line.distance(Point(_sx, _sy))
            except _GEOM_EXC:
                continue
            fill_caps[_i] = runway_strip_band_width_m(
                width, _d_axis, width)

    # ── OLS HANDOVER (docs/specs/obstacle-limitation-surfaces-spec.md) ──
    # The lateral CUT is bounded by the OLS transitional surface, which
    # takes over at the handover S.  The spec's continuity ruling SHRINKS
    # the runway-family cut reach to S, so the two laws abut exactly
    # instead of the zone-3 +5 % ceiling marching on to the earthwork cap
    # with nothing beyond it.  This block OWNS the cut cap outright —
    # assignment, not ``max()``.  (An earlier ``max()`` over caps
    # initialised to ``reach`` never shrank anything: it implemented the
    # ruling only as a parasitic composition with A4's since-removed cut
    # clamp, so OLS-alone did not do what its own spec says.)
    #
    # ``axis_line`` is threaded ONLY for runway-family shapes, so its
    # presence is the family test; the code number comes off its length
    # exactly as ``_family_params`` derives it.  ``axis_classes`` carries
    # the runway's two apt.dat END classes: S is taken as the MINIMUM over
    # them, matching how ``ols._flank_law`` min-composes the surfaces, so
    # the two emitters cannot disagree about where the handover is (a
    # split would overlap the OLS flank band with this cut band on
    # differently-anchored surfaces — a wall).  Missing metadata falls
    # back to the conservative instrument geometry, the same direction
    # ``config.runway_end_approach_class`` takes for blank rows.
    if _OLS_CUT and axis_line is not None:
        try:
            _code = runway_code_number(axis_line.length)
        except (ValueError, KeyError, AttributeError):
            _code = None
        if _code is not None:
            _classes = tuple(axis_classes or ()) or ("non_precision",)
            for _i, (_sx, _sy) in enumerate(stations):
                try:
                    _d_axis = axis_line.distance(Point(_sx, _sy))
                except _GEOM_EXC:
                    continue
                _s = min(ols_lateral_handover_distance_m(
                    _code, _cls, _d_axis) for _cls in _classes)
                cut_caps[_i] = min(reach, _s)

    # ── RAY OCCLUSION (owner ruling 2026-07-25) ─────────────────────
    # A lateral band's outward reach is measured through FREE GROUND ONLY.
    # Computed ONCE here — the single station march both the pre-solve
    # constructor and the post-solve emit re-march run through — off the
    # SAME ``prep_static`` the terrain-facing probe reads, over the MAX of
    # the two directions' caps, so the fill and cut builders bound
    # themselves against identical geometry.  All +inf with the gate off.
    occlusion = _station_occlusion_limits(
        stations, outs,
        [f if f > c else c for f, c in zip(fill_caps, cut_caps)],
        step, prep_static, wrap_skirt_prep)

    # ── HALF-CORRIDOR CUT CAP (owner ruling 2026-07-26) ─────────────
    # Where a station's outward ray is occluded by facing pavement, the
    # CUT may claim at most HALF the corridor — the facing frontage owns
    # the other half — so two pavements' cut slabs meet mid-corridor
    # instead of one marching to the neighbour's edge and ending in a
    # wall (CYXY shape 337 against taxiway 132).  Implemented by HALVING
    # the occlusion limit handed to the CUT builder — not by shrinking
    # ``cut_caps`` — so the builder's scan-break, daylight clamp and
    # taper row all honour the same half-corridor bound and the
    # cap-derived zone breakpoints stay as designed (a per-station cap
    # shrink silently dropped whole-shape zone edges).  ``occlusion`` is
    # +inf off-corridor and with ray occlusion off, so this is a no-op
    # there.  CUT only: the FILL mandate is a graded-strip law bounded
    # by ``width``/A4 and does not steamroll corridors.
    cut_occ = occlusion
    if _CUT_HALF_CORRIDOR and occlusion:
        cut_occ = [o if (o is None or o == float("inf")) else o * 0.5
                   for o in occlusion]

    # Zone-row collectors (order 2): translate the builders' per-run
    # provenance into row dicts with frozen-nearest hosts.  The d0 == 0
    # INNER row is the pavement weld chain — dropped here (pavement
    # variables already exist; a band never mints one).
    # ── APRON WALL SCOPE (owner ruling 2026-07-25) ──────────────────
    # An apron frontage station with no built pavement within
    # ``APRON_WALL_PAVEMENT_ADJACENCY_M`` faces OPEN TERRAIN: the ruling
    # declines to govern its FILL side, so the raw DEM grades up to the
    # apron edge.  Implemented as a nulled FILL REFERENCE — the one input
    # ``_build_fill_bands`` skips a station on — which leaves the CUT
    # march, the daylight law and every other station untouched, and
    # therefore also mints no fill ZONE ROW (no solver variable) there.
    # ``fill_station_filter is None`` (every non-apron family, gate off)
    # leaves ``st_alts_fill`` the same object it already was.
    fill_refs = st_alts_fill
    if fill_station_filter is not None:
        _open = [i for i, (sx, sy) in enumerate(stations)
                 if st_alts_fill[i] is not None
                 and not fill_station_filter(sx, sy)]
        if _open:
            _open_set = set(_open)
            fill_refs = [None if i in _open_set else a
                         for i, a in enumerate(st_alts_fill)]
            _APPARATUS_HITS["apron_open_frontage_stations"] += len(_open)

    def _make_zone_collector(kind):
        # The band law's OWN reference per station — the frontage altitude
        # the analytic surface is built on (``_build_*_bands`` reads exactly
        # this array).  Recorded alongside the frozen-nearest host so the
        # seam-prolongation host repair can tell how far a re-homed host's
        # altitude is from the station's real frontage altitude (see
        # ``construct_adjacent_ground_presolve``); every other consumer
        # ignores it, so collecting it changes nothing.
        _ref_alts = fill_refs if kind == "fill" else st_alts

        def _collect(d0, inner_entries, outer_entries):
            if d0 > 0.0 and len(inner_entries) >= 1:
                zone_rows_out.append({
                    "kind": kind, "d0": float(d0),
                    "pts": [(float(x), float(y))
                            for _i, x, y in inner_entries],
                    "depths": [float(d0)] * len(inner_entries),
                    "hosts": [hosts[i] for i, _x, _y in inner_entries],
                    "ref_alts": [_ref_alts[i]
                                 for i, _x, _y in inner_entries],
                    "host_pro": [host_pro[i]
                                 for i, _x, _y in inner_entries]})
            if outer_entries:
                zone_rows_out.append({
                    "kind": kind, "d0": float(d0),
                    "pts": [(float(x), float(y))
                            for _i, x, y, _d in outer_entries],
                    "depths": [float(dd)
                               for _i, _x, _y, dd in outer_entries],
                    "hosts": [hosts[i]
                              for i, _x, _y, _d in outer_entries],
                    "ref_alts": [_ref_alts[i]
                                 for i, _x, _y, _d in outer_entries],
                    "host_pro": [host_pro[i]
                                 for i, _x, _y, _d in outer_entries]})
        return _collect

    _collect_fill = (_make_zone_collector("fill")
                     if zone_rows_out is not None else None)
    _collect_cut = (_make_zone_collector("cut")
                    if zone_rows_out is not None else None)

    # FILL (DEM below floor, zones 1-2) then CUT (DEM above ceiling): the
    # runway-end skirt fill/cut builders' lateral twins.  ORDER 3 worst-case
    # coverage: FILL detects against the reach-band CEILING (``st_alts_fill``),
    # CUT against the reach-band FLOOR (``st_alts``); off order 3 the two
    # arrays are the same object, so this is byte-identical.
    fill_edges = {ADJACENT_GROUND_LIP_WIDTH_M}
    cut_edges = {ADJACENT_GROUND_LIP_WIDTH_M, width}
    if coverage_grid:
        fill_edges = _coverage_grid_edges(fill_edges, width)
        cut_edges = _coverage_grid_edges(cut_edges, reach)
    # ── STRIP PRECEDENCE §1: THE LAW SWAP (lead ruling 2026-08-04) ──
    # Inside the LATERAL strip the strip's OWN corridor law governs the
    # ground, whatever frontage the march started from.  The station is
    # kept (an earlier draft DEFERRED it, which left that ground at raw
    # DEM — measured: HECA −2.98 ha of graded strip, HEAZ −14.6 %); what
    # changes is WHICH law values it.
    #
    # Implemented as a SPLIT BUILD over the same station sequence: the
    # station's reference is nulled in the pass that does not own it, which
    # is the one input ``_build_*_bands`` skips a station on (the apron
    # wall scope's idiom verbatim).  No builder changes, no second march,
    # one occlusion computation shared by both passes — and the two passes
    # cannot double-govern a station because the masks are complementary.
    strip_mask = None
    if strip_law is not None and strip_zone_prep is not None:
        strip_mask = []
        for (sx, sy), out in zip(stations, outs):
            probe = Point(sx + out[0] * _RING_PROBE_M,
                          sy + out[1] * _RING_PROBE_M)
            strip_mask.append(
                bool(strip_zone_prep.contains(Point(sx, sy))
                     or strip_zone_prep.contains(probe)))
        if not any(strip_mask):
            strip_mask = None
    if strip_mask is None:
        fill_bands = _build_fill_bands(
            stations, fill_refs, outs, fill_caps, floor_depth,
            fill_edges, trigger, step, sample_dem,
            is_ring_vertex, at_seam, zone_collect=_collect_fill,
            force_full_reach=coverage_grid, occlusion=occlusion)
        cut_bands = _build_cut_bands(
            stations, st_alts, outs, cut_caps, ceil_off,
            cut_edges, trigger, step, sample_dem,
            is_ring_vertex, at_seam, zone_collect=_collect_cut,
            force_full_reach=coverage_grid, occlusion=cut_occ)
        return fill_bands, cut_bands, stations, st_alts, outs

    (s_floor_depth, s_ceil_off, s_width, s_reach, s_trigger,
     s_axis_line) = strip_law
    _APPARATUS_HITS["strip_law_governed_stations"] += sum(
        1 for m in strip_mask if m)
    own_fill_refs = [None if m else a
                     for m, a in zip(strip_mask, fill_refs)]
    own_cut_refs = [None if m else a for m, a in zip(strip_mask, st_alts)]
    str_fill_refs = [a if m else None
                     for m, a in zip(strip_mask, fill_refs)]
    str_cut_refs = [a if m else None for m, a in zip(strip_mask, st_alts)]
    # Strip-family caps: the FILL cap is the graded strip width REMAINING
    # outward of the station (``runway_strip_band_width_m`` — the same A4
    # clamp the runway family's own march spends), the CUT cap the runway
    # family's reach.  Both per station, exactly as the own-law caps are.
    s_fill_caps = [s_width] * m
    s_cut_caps = [s_reach] * m
    if s_axis_line is not None:
        for _i, (_sx, _sy) in enumerate(stations):
            if not strip_mask[_i]:
                continue
            try:
                _d_axis = s_axis_line.distance(Point(_sx, _sy))
            except _GEOM_EXC:
                continue
            s_fill_caps[_i] = runway_strip_band_width_m(
                s_width, _d_axis, s_width)
    s_occlusion = _station_occlusion_limits(
        stations, outs,
        [f if f > c else c for f, c in zip(s_fill_caps, s_cut_caps)],
        step, prep_static, wrap_skirt_prep)
    s_cut_occ = s_occlusion
    if _CUT_HALF_CORRIDOR and s_occlusion:
        s_cut_occ = [o if (o is None or o == float("inf")) else o * 0.5
                     for o in s_occlusion]
    s_fill_edges = {ADJACENT_GROUND_LIP_WIDTH_M}
    s_cut_edges = {ADJACENT_GROUND_LIP_WIDTH_M, s_width}
    if coverage_grid:
        s_fill_edges = _coverage_grid_edges(s_fill_edges, s_width)
        s_cut_edges = _coverage_grid_edges(s_cut_edges, s_reach)
    # §A3(a) — the trigger's LONGITUDINAL term (see
    # ``_strip_longitudinal_demand``).  Computed ONCE for both strip
    # passes off the same stations, the same axis and the same DEM the
    # lateral scan reads.
    s_long_demand = _strip_longitudinal_demand(
        stations, strip_mask, s_axis_line, sample_dem, strip_longitudinal)

    def _strip_collector(base):
        # Zone rows built under the strip law are TAGGED, so the pre-solve
        # constructor bounds them with the strip envelope instead of this
        # shape's own (the two halves must agree on which law owns a row).
        if base is None:
            return None

        def _collect(d0, inner_entries, outer_entries):
            before = len(zone_rows_out)
            base(d0, inner_entries, outer_entries)
            for row in zone_rows_out[before:]:
                row["strip_law"] = True
        return _collect

    fill_bands = _build_fill_bands(
        stations, own_fill_refs, outs, fill_caps, floor_depth,
        fill_edges, trigger, step, sample_dem,
        is_ring_vertex, at_seam, zone_collect=_collect_fill,
        force_full_reach=coverage_grid, occlusion=occlusion)
    cut_bands = _build_cut_bands(
        stations, own_cut_refs, outs, cut_caps, ceil_off,
        cut_edges, trigger, step, sample_dem,
        is_ring_vertex, at_seam, zone_collect=_collect_cut,
        force_full_reach=coverage_grid, occlusion=cut_occ)
    s_fill = _build_fill_bands(
        stations, str_fill_refs, outs, s_fill_caps, s_floor_depth,
        s_fill_edges, s_trigger, step, sample_dem,
        is_ring_vertex, at_seam,
        zone_collect=_strip_collector(_collect_fill),
        force_full_reach=coverage_grid, occlusion=s_occlusion,
        longitudinal_demand=s_long_demand)
    s_cut = _build_cut_bands(
        stations, str_cut_refs, outs, s_cut_caps, s_ceil_off,
        s_cut_edges, s_trigger, step, sample_dem,
        is_ring_vertex, at_seam,
        zone_collect=_strip_collector(_collect_cut),
        force_full_reach=coverage_grid, occlusion=s_cut_occ,
        longitudinal_demand=s_long_demand)
    if strip_bands_out is not None:
        strip_bands_out.extend([("fill", b) for b in s_fill])
        strip_bands_out.extend([("cut", b) for b in s_cut])
    else:
        # No separate valuation channel (the pre-solve constructor, whose
        # consumer is the zone-row store): the footprints still belong to
        # this shape's band lists.
        fill_bands = fill_bands + s_fill
        cut_bands = cut_bands + s_cut
    return fill_bands, cut_bands, stations, st_alts, outs


def _split_zone_rows_off_static(zone_rows, prep_static, static_boundary):
    """Drop every zone-row point that lies INSIDE static pavement or within
    ``ADJACENT_GROUND_ZONE_STATIC_KEEPOUT_M`` of any static-shape boundary
    (B4 flip defect 1 — see the constant's rationale in ``config.py``: such
    a point can intern onto a pavement ring vertex's canonical bucket and
    stamp its DEM-clamped value onto the pavement profile).  A row whose
    interior points are dropped is SPLIT into its surviving contiguous runs
    (one row dict per run) so the emit-time resampler never interpolates a
    row polyline straight across the pavement it used to cross."""
    from .config import ADJACENT_GROUND_ZONE_STATIC_KEEPOUT_M as _margin
    import numpy as _np
    from shapely import points as _sh_points, dwithin as _sh_dwithin
    out: list[dict] = []
    n_dropped = 0
    for row in zone_rows:
        pts = row.get("pts") or []
        if not pts:
            continue
        arr = _sh_points(_np.asarray(pts, dtype=float))
        try:
            near = _sh_dwithin(static_boundary, arr, _margin)
        except _GEOM_EXC:
            near = _np.zeros(len(pts), dtype=bool)
        runs: list[list[int]] = []
        current: list[int] = []
        for j in range(len(pts)):
            bad = bool(near[j])
            if not bad:
                try:
                    bad = prep_static.contains(arr[j])
                except _GEOM_EXC:
                    bad = False
            if bad:
                n_dropped += 1
                if current:
                    runs.append(current)
                    current = []
            else:
                current.append(j)
        if current:
            runs.append(current)
        if len(runs) == 1 and len(runs[0]) == len(pts):
            out.append(row)
            continue
        depths = row.get("depths") or []
        hosts = row.get("hosts") or []
        # Per-point parallel arrays carried through the split in lockstep
        # with ``pts`` (a desync would mis-pair a station's law reference
        # with another station's point).
        refs = row.get("ref_alts") or [None] * len(pts)
        deltas = row.get("host_delta") or [0.0] * len(pts)
        pro = row.get("host_pro") or [False] * len(pts)
        for run in runs:
            out.append({
                "kind": row["kind"], "d0": row["d0"],
                "pts": [pts[j] for j in run],
                "depths": [depths[j] for j in run],
                "hosts": [hosts[j] for j in run],
                "ref_alts": [refs[j] for j in run],
                "host_pro": [pro[j] for j in run],
                "host_delta": [deltas[j] for j in run]})
    if n_dropped:
        _APPARATUS_HITS["zone_static_keepout_dropped"] += n_dropped
    return out


def construct_adjacent_ground_presolve(layout: PavementLayout, dem,
                                       tile_lat: int, tile_lon: int,
                                       source_runways=None) -> int:
    """Slice B stage B3 ORDER 1 PRE-SOLVE construction (gate
    ``ONE_SOLVE_TERRAIN`` + ``ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT``).

    Moves the adjacent-ground band FOOTPRINT march
    (``_derive_shape_stations_and_bands``) BEFORE ``per_surface_solve`` from a
    DEM-seeded pavement-edge estimate (``_shape_ring_alts(seed=True)``), and
    stages the raw band rings on ``layout.adjacent_ground_presolve`` for the
    post-solve emitter to CONSUME instead of re-marching.  Values are NOT
    computed here — the emitter values every stored footprint vertex through
    the existing analytic resampler off the SOLVED pavement altitudes, and the
    foreign-shape clip stays at emission (so gate-ON output is value-equivalent
    to gate-OFF up to the enumerated seed/late-feature footprint deltas).

    Stores ``layout.adjacent_ground_presolve = [{"shape": s, "fill": [...],
    "cut": [...], "zone_rows": [...], "zone_nodes": [...],
    "zone_values": None}, ...]`` (the ``shape`` reference is preserved across
    the layout pickle — same object as the ``layout.shapes`` element — so the
    emitter rebuilds the resampler from the by-then-solved shape).  The
    ``zone_rows`` / ``zone_nodes`` fields are the ORDER-2 schema split: the
    free-variable zone-row grid (row polylines with per-vertex depth +
    frozen-nearest host), admitted to the solver under the ADMISSION sub-gate
    ``ONE_SOLVE_TERRAIN_GRADED_STRIP``; ``zone_values`` is filled by the
    solve's writeback ({millimetre key: solved value}).  Returns the
    number of shapes with at least one raw band."""
    if dem is None:
        return 0
    if layout.anchor is None:
        return 0
    lat0, lon0 = layout.anchor
    cos0 = math.cos(math.radians(lat0))
    R = R_EARTH
    step = CLEARANCE_STATION_STEP_M

    def _ll_to_m(lat: float, lon: float) -> tuple[float, float]:
        return (math.radians(lon - lon0) * R * cos0,
                math.radians(lat - lat0) * R)

    def sample_dem(x: float, y: float):
        try:
            lat = lat0 + math.degrees(y / R)
            lon = lon0 + math.degrees(x / (R * cos0))
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            return None

    in_scope = _RUNWAY_ROLES + _TAXIWAY_ROLES + _APRON_ROLES
    # THE FABRIC MODEL (owner RULINGS 2026-08-08): "Unregulated ground:
    # NOTHING — the drape is the feather."  ``bands_declined`` is the ONE
    # predicate that answers which HOSTS get no band, wall or feather:
    # under W2 the APRON family (reg-set T2/T3, ruling 4 — nothing in
    # either authority governs ground beyond an apron edge), under the
    # Phase-A gate the declared cluster verbatim.  Runway and taxiway
    # strips are REG SET and stay in scope on both paths; what changes
    # for ICAO runways is the band's VALUE, in ``grade_law``.
    from .fabric_sparse import bands_declined as _bands_declined
    scoped = [s for s in layout.shapes
              if s.role in in_scope and s.polygon is not None
              and not s.polygon.is_empty
              and s.polygon.geom_type == "Polygon"
              and not _bands_declined(s)]
    if not scoped:
        layout.adjacent_ground_presolve = []
        return 0

    # Terrain-facing probe reference: the union of the shapes PRESENT
    # pre-solve (pavement + pre-solve skirts under B1), minus groundside —
    # the same static block the emitter's ``_station_reference`` probe reads,
    # here at its pre-solve state (post-solve features are absent; their clip
    # is applied at emission, not here).
    try:
        static_union = unary_union(
            [s.polygon for s in layout.shapes
             if s.polygon is not None and not s.polygon.is_empty
             and s.role != "groundside_pavement"])
    except _GEOM_EXC:
        static_union = None
    if static_union is None or static_union.is_empty:
        layout.adjacent_ground_presolve = []
        return 0
    try:
        prep_static = prep(static_union)
    except _GEOM_EXC:
        layout.adjacent_ground_presolve = []
        return 0
    # APRON WALL SCOPE (owner ruling 2026-07-25): built ONCE for the whole
    # construction, consumed per apron shape below.  ``None`` with the gate
    # off / no pavement — the march is then unfiltered, byte-identical.
    _wall_scope_index = (apron_wall_pavement_adjacency_index(layout)
                         if _APRON_WALL_SCOPE else None)
    # Zone-node static keep-out (B4 flip defect 1): the boundary of the
    # SAME static block the march probes, prepared once for the vectorized
    # dwithin test in ``_split_zone_rows_off_static``.
    try:
        from shapely import prepare as _sh_prepare
        _zone_static_boundary = static_union.boundary
        _sh_prepare(_zone_static_boundary)
    except _GEOM_EXC:
        _zone_static_boundary = None

    rw_axes: list[tuple] = []
    if source_runways:
        for r in source_runways:
            try:
                rax, ray = _ll_to_m(r.lat_a, r.lon_a)
                rbx, rby = _ll_to_m(r.lat_b, r.lon_b)
            except _GEOM_EXC:
                continue
            rlen = math.hypot(rbx - rax, rby - ray)
            if rlen < 1.0:
                continue
            # 4th slot: the runway's two apt.dat END approach classes.
            # ``_family_params`` hands them to the march so the OLS
            # handover S is computed from the SAME classes ``ols.py``
            # uses (slice 4, "one S") instead of a hardcoded default.
            rw_axes.append((LineString([(rax, ray), (rbx, rby)]),
                            ((rbx - rax) / rlen, (rby - ray) / rlen),
                            rlen,
                            (runway_end_approach_class(
                                getattr(r, "markings_a", 0),
                                getattr(r, "approach_lights_a", 0)),
                             runway_end_approach_class(
                                getattr(r, "markings_b", 0),
                                getattr(r, "approach_lights_b", 0)))))

    trigger_by_family = {
        "runway": CLEARANCE_OBSTRUCTION_THRESHOLD_M["runway"],
        "taxiway": CLEARANCE_OBSTRUCTION_THRESHOLD_M["taxiway"],
        "apron": CLEARANCE_OBSTRUCTION_THRESHOLD_M["taxiway"],
    }
    seam_keys = (airside_seam_vertex_keys(layout)
                 if _SEAM_TAPER_PIN else set())
    # Taxiway-end WRAP join target (scope A): built once, passed only for
    # taxiway shapes with the gate ON (byte-inert otherwise).
    wrap_skirt_prep = (_runway_end_skirt_prep(layout)
                       if _END_WRAP else None)
    # Crossing-zone exclusion (Phase 1): the published zone, prepared
    # once, passed for taxiway shapes (byte-inert when nothing published).
    crossing_zone_prep = _crossing_zone_prep(layout)
    # ENCLAVE keep-out: NOT consumed here (SCOPING v2).  It is a
    # keep-out over GROUND, applied to the band geometry at emission
    # (``emit_adjacent_ground_bands``), so this march and the emit march
    # build the IDENTICAL station sequence — which is the parity the
    # pre-solve store's coordinate join depends on.  The cost is named:
    # a zone row inside a pocket becomes a solver variable whose emitted
    # geometry is then clipped away.  That is the collar zone's existing
    # bargain under the frozen-footprint state, and it is the cheap side
    # of the trade the v1 station stand-down lost 150,438 m² of graded
    # strip to.
    # STRIP PRECEDENCE §1 (``O4_STRIP_PRECEDENCE``): the LATERAL strip,
    # built once, passed for NON-runway shapes; ``None`` with the gate off
    # (byte-inert).  Between the ends only — the end corridors keep the
    # runway-END regime's own law (see runway_strip_lateral_footprint_ring).
    strip_lateral_prep = runway_strip_lateral_zone(layout)

    # ── ORDER 3 WORST-CASE COVERAGE (coverage-gap closure) ──────────────
    # The pre-solve march seeds unsolved pavement edges from the DEM, which
    # tracks the in-corridor terrain and so emits NO band exactly where the
    # SOLVED edge departs from the DEM (flattened taxiways, raised aprons,
    # the taxiway end onto a skirt) — the 1,285 analytic-fallback vertices
    # and 24 store-missing shapes.  Under band ADMISSION (the only path that
    # solves the zone nodes and reads them back), march instead against the
    # reach-band WORST CASE per edge (``_worst_case_ring_alts``): floor for
    # cut, ceiling for fill.  The band bounds every solved edge, so the
    # footprint is a SUPERSET of any solved outcome by construction and the
    # emit-time resampler always finds a covering row.  Gate OFF (order-1
    # construct-only, no admission): DEM seed kept, byte-identical.
    from .config import (ONE_SOLVE_TERRAIN_GRADED_STRIP as _ADMIT_COVERAGE,
                         ADJACENT_GROUND_FULL_EXTENT_COVERAGE
                         as _FULL_EXTENT_COVERAGE)
    _reach_band = (_build_construct_reach_band(layout)
                   if _ADMIT_COVERAGE else None)
    # Full-extent coverage grid (B4 prerequisite): only meaningful under
    # band admission (the path that solves + reads back the zone nodes);
    # a no-op otherwise, so the flag stays False without admission.
    _coverage_grid = bool(_FULL_EXTENT_COVERAGE and _ADMIT_COVERAGE)

    # TILE-SEAM PROLONGATION (owner ruling 2026-07-24): the neighbour-tile
    # pavement ``tile_cut`` dropped, which bounds every prolongation.
    # ``None`` on a single-tile airport -> the splice is a strict no-op.
    _offcut_union = seam_offcut_union(layout)
    _n_prolonged = 0

    entries: list[dict] = []
    for s in scoped:
        params = _family_params(layout, s, rw_axes)
        if params is None:
            continue
        family, code_number, code_letter, reach, width, axis, \
            axis_line, axis_classes = params
        trigger = trigger_by_family[family]
        ceil_off, envelope_at, floor_depth = _band_family_closures(
            family, code_number, code_letter, width)
        try:
            coords = list(s.polygon.exterior.coords)
            ccw = bool(s.polygon.exterior.is_ccw)
        except _GEOM_EXC:
            continue
        if len(coords) < 4:
            continue
        if _reach_band is not None:
            # Worst-case coverage: floor-referenced CUT ring + ceiling-
            # referenced FILL ring (runway edges keep CIFP values in both).
            ring_alts, ring_alts_fill = _worst_case_ring_alts(
                s, coords, _reach_band, sample_dem)
        else:
            ring_alts = _shape_ring_alts(s, coords, sample_dem, seed=True)
            ring_alts_fill = None
        # SEAM PROLONGATION: march off the UN-CUT frontage (the corridor's
        # end is then decided by the tile cut, not by where tile_cut already
        # stopped the pavement).  ``depth_cap`` is the deepest the corridor
        # can be at this shape — the same clamp ``_derive_shape_stations_
        # and_bands`` applies through ``runway_strip_band_width_m``.
        _pre_coords = coords
        # ``reach`` in every gate state.  The ``width`` tightening was
        # only valid while A4 clamped the CUT as well; now that A4 owns
        # the fill cap alone, a ``width``-capped prolongation would
        # under-prolong the CUT frontage at a tile seam.  ``reach`` is a
        # safe upper bound in all four gate combinations.
        _depth_cap = reach
        _pro_arrays = ([ring_alts] if ring_alts_fill is None
                       else [ring_alts, ring_alts_fill])
        coords, _pro_arrays, _npro = _seam_prolonged_ring(
            layout, coords, ccw, _pro_arrays, _depth_cap, _offcut_union)
        _real_keys: set = set()
        _pro_keys: set = set()
        if _npro:
            ring_alts = _pro_arrays[0]
            if ring_alts_fill is not None:
                ring_alts_fill = _pro_arrays[1]
            _n_prolonged += _npro
            # The SYNTHETIC vertices this splice minted — the march flags
            # every station on an edge touching one, and the host repair
            # below re-homes the hosts that ARE one.
            _real_keys = {_vertex_key(px, py) for px, py in _pre_coords}
            _pro_keys = {_vertex_key(px, py)
                         for px, py in coords} - _real_keys
        # STRIP PRECEDENCE §1: the strip family this shape's
        # strip-interior stations are governed by (``None`` for runway
        # shapes and with the gate off — then nothing below fires).
        _strip_full = (
            _strip_law_params(layout, s, rw_axes, trigger_by_family,
                              with_envelope=True)
            if (strip_lateral_prep is not None and family != "runway")
            else None)
        _strip_law = _strip_full[:6] if _strip_full else None
        _strip_env = _strip_full[6] if _strip_full else None
        _strip_width = _strip_full[2] if _strip_full else None
        zone_rows: list[dict] = []
        fill_bands, cut_bands, _st, _sa, _ou = \
            _derive_shape_stations_and_bands(
                coords, ccw, ring_alts, axis, width, reach, trigger,
                floor_depth, ceil_off, step, prep_static, seam_keys,
                sample_dem, zone_rows_out=zone_rows,
                wrap_skirt_prep=(wrap_skirt_prep
                                 if family == "taxiway" else None),
                ring_alts_fill=ring_alts_fill,
                coverage_grid=_coverage_grid,
                crossing_zone_prep=(crossing_zone_prep
                                    if family == "taxiway" else None),
                # STRIP PRECEDENCE §1: inside the lateral strip a
                # NON-runway family's stations are governed by the STRIP
                # law.  Passed in the PRE-SOLVE construct as well as at
                # emit so both marches build the same rows under the same
                # law (a construct-only or emit-only swap would bound a
                # solver variable by a law the emitter does not use).
                strip_zone_prep=(strip_lateral_prep
                                 if family != "runway" else None),
                strip_law=_strip_law,
                # §A3(a): the trigger's LONGITUDINAL term, so the
                # PRE-SOLVE construct stages rows for the stations the
                # strip's own along-axis law demands (a construct-only or
                # emit-only term would stage variables one march builds
                # and the other does not).
                strip_longitudinal=(
                    _strip_longitudinal_law_for(layout, s, rw_axes)
                    if _strip_law else None),
                axis_line=axis_line,
                axis_classes=axis_classes,
                prolonged_keys=_pro_keys,
                # APRON WALL SCOPE — apron frontage only (owner ruling
                # 2026-07-25).  Applied in the PRE-SOLVE construct as
                # well as at emit so the two marches stay identical and
                # no solver variable is minted for ground the ruling
                # leaves ungoverned.
                fill_station_filter=(
                    apron_wall_frontage_qualifier(s, _wall_scope_index)
                    if family == "apron" else None))
        if not fill_bands and not cut_bands:
            continue
        # FROZEN-NEAREST HOST REPAIR: a zone row stationed on a PROLONGED
        # (synthetic) ring vertex would name a host that is not a pavement
        # ring vertex and therefore not a solver variable.  Re-home those
        # rows onto the nearest REAL ring vertex — the cut-back corner —
        # so the B3 frozen-nearest contract still holds.
        #
        # ★ VALUE DEFECT FIXED 2026-07-25 (the stage-3 blocker on
        # ``config.RUNWAY_SEAM_VERTEX_DEM_PIN``).  The re-home is a
        # positional repair, but the host is ALSO the law's altitude
        # reference: ``solver_primitives.adjacent_ground_zone_constraints``
        # encodes each zone node as ``elev[node] - elev[host] in
        # [floor_off, ceil_off]``.  Frozen-nearest is a sound proxy for the
        # station's frontage altitude while the host is metres away on a
        # densely-vertexed ring — but a re-homed host is the CUT-BACK
        # CORNER, up to a whole prolongation (300 m at SPLP) away in
        # station, so the band 270 m up the prolonged frontage was
        # anchored to the corner's altitude.  Measured SPLP -13/-078 with
        # the runway pin ON: zone node (-148.8, -141.5), host
        # (-142.3, -364.4) at 55.80 m, ceil_off -1.17 -> 54.63 m emitted,
        # while the station's OWN frontage altitude there is 58.52 m
        # (the analytic resampler read exactly that) and the neighbouring
        # seam vertices sit at 59.0 m — the 4.4 m spike that failed
        # ``test_tile_cut_parity`` at 4.55 m.
        #
        # FIX (value-sourcing only — the geometry, the host and the
        # envelope are untouched): carry the station's own frontage
        # altitude (``ref_alts``, the very array ``_build_*_bands`` values
        # the analytic surface from) and shift the node's envelope by
        # ``ref_alt - host_alt``, so the corridor is centred on the
        # FLANKING FRONTAGE EDGE's own extrapolated altitude — the
        # ADJACENT_GROUND_SEAM_PROLONGATION design ruling — while the
        # constraint still references a real solver variable.
        #
        # Applied to every station ON a prolonged edge (``host_pro``), not
        # only to the re-homed half: a prolonged edge carries NO interior
        # vertices, so frozen-nearest hands its first half the cut-back
        # corner and its second half the synthetic tip, and shifting only
        # the second half would step the corridor by half the
        # prolongation's rise at the changeover (measured 2.0 m at SPLP).
        # Shifting the whole edge makes the reference the linearly
        # interpolated frontage altitude — continuous into the real ring
        # at the corner, where the shift goes to zero by construction.
        # Untouched everywhere else, so a ring with no prolongation (every
        # single-tile airport) is byte-identical.
        if _npro and zone_rows:
            # Ring altitude by vertex identity, per band direction (the
            # two arrays are the SAME object off order-3 coverage).  Read
            # off the PROLONGED ring, so a real host and a synthetic host
            # resolve through one map.
            def _alt_map(values):
                out: dict[tuple[int, int], float] = {}
                for (px, py), av in zip(coords, values):
                    if av is None:
                        continue
                    out.setdefault(_vertex_key(px, py), float(av))
                return out

            _alt_by_key = {"cut": _alt_map(ring_alts),
                           "fill": _alt_map(ring_alts if ring_alts_fill
                                            is None else ring_alts_fill)}
            # The synthetic hosts are the (at most 2-per-run) prolonged
            # vertices, repeated across every row they host — memoise the
            # nearest-real scan per exact coordinate pair instead of
            # re-scanning the ring per row (same ``min`` over the same
            # list: identical result, returned as the same tuple).
            _near_memo: dict[tuple, tuple] = {}

            def _nearest_real(hx, hy):
                hit = _near_memo.get((hx, hy))
                if hit is None:
                    hit = min(_pre_coords,
                              key=lambda p: (p[0] - hx) ** 2
                              + (p[1] - hy) ** 2)
                    _near_memo[(hx, hy)] = hit
                return hit

            for _row in zone_rows:
                _pro_flags = _row.get("host_pro") or ()
                if not any(_pro_flags) and all(
                        _vertex_key(hx, hy) in _real_keys
                        for hx, hy in _row["hosts"]):
                    continue
                _alts = _alt_by_key[_row["kind"]]
                _refs = _row.get("ref_alts") or [None] * len(_row["hosts"])
                _flags = list(_pro_flags) or [False] * len(_row["hosts"])
                _new_hosts = []
                _deltas = []
                for (hx, hy), _ref, _flag in zip(_row["hosts"], _refs,
                                                 _flags):
                    if _vertex_key(hx, hy) in _real_keys:
                        _real = (hx, hy)
                    else:
                        _real = _nearest_real(hx, hy)
                    _new_hosts.append(_real)
                    # The station's frontage altitude vs its host's own:
                    # the shift the law corridor needs to stay referenced
                    # to the prolonged frontage.  Unknown on either side
                    # (a skipped station, an unvalued ring vertex) => no
                    # shift, i.e. the pre-fix behaviour.
                    _hal = _alts.get(_vertex_key(*_real))
                    _deltas.append(
                        0.0 if (not _PROLONG_HOST_REF or not _flag
                                or _ref is None or _hal is None)
                        else float(_ref) - _hal)
                _row["hosts"] = _new_hosts
                _row["host_delta"] = _deltas
        # Zone-node static keep-out (B4 flip defect 1): no zone point on,
        # inside, or hugging static pavement ever becomes a solver variable.
        if zone_rows and _zone_static_boundary is not None:
            zone_rows = _split_zone_rows_off_static(
                zone_rows, prep_static, _zone_static_boundary)
        # ZONE-NODE GRID (order 2, schema split): the free-variable
        # admission list — one record per unique zone-row vertex
        # (millimetre dedup; a row vertex shared between two abutting
        # band slabs is ONE variable), each with its frozen-nearest
        # host pavement ring vertex and the law's envelope offsets at
        # the vertex's construction-time lateral depth:
        #   * "cut" rows: ceiling only (fill bands own below-floor
        #     terrain — the analytic resampler's own kind rule);
        #   * "fill" rows: both bounds at depth clamped to the graded
        #     width (zones 1-2 by construction — same rule).
        zone_nodes: list[dict] = []
        # ── THE CONSTRAINT SUPPLY (single-solve ingestion) ───────────
        # Built in THIS loop, from THIS row's own depth/kind/law — the
        # single-pass place, because everything the constraint needs is
        # already in hand here and nothing has to be re-derived from
        # geometry later.  Consumed by the solve (KILL lane) and by the
        # seat coupler (SEATS lane); see ``build_zone_constraint_table``
        # for the record shape and the contract.
        zone_boxes: list[dict] = []
        seen_zone_keys: set[tuple[int, int]] = set()
        for row in zone_rows:
            # Seam-prolongation host shift (see the repair block above):
            # 0.0 everywhere the host is the station's own real ring
            # vertex, so this is a structural no-op for every row that was
            # not re-homed — and for every airport with no prolongation.
            _row_delta = row.get("host_delta") or [0.0] * len(row["pts"])
            for (zx, zy), zd, zhost, zdelta in zip(
                    row["pts"], row["depths"], row["hosts"], _row_delta):
                zkey = _vertex_key(zx, zy)
                if zkey in seen_zone_keys:
                    continue
                seen_zone_keys.add(zkey)
                _dem_seed = sample_dem(zx, zy)
                # STRIP PRECEDENCE §1 (law swap): a row the march built
                # under the STRIP family is bounded by the STRIP envelope,
                # so the solver variable and the emitter's corridor clamp
                # are the same law.  Tagged by the march itself, never
                # re-derived here from geometry (one owner per row).
                _row_env, _row_width = envelope_at, width
                if row.get("strip_law") and _strip_env is not None:
                    _row_env, _row_width = _strip_env, _strip_width
                zone_floor, zone_ceil = zone_corridor_box(
                    _row_env, _row_width, row["kind"], zd)
                if zdelta:
                    if zone_floor is not None:
                        zone_floor += zdelta
                    if zone_ceil is not None:
                        zone_ceil += zdelta
                zone_nodes.append({
                    "xy": (float(zx), float(zy)),
                    "host": (float(zhost[0]), float(zhost[1])),
                    "floor_off": (None if zone_floor is None
                                  else float(zone_floor)),
                    "ceil_off": (None if zone_ceil is None
                                 else float(zone_ceil))})
                # THE BOX, stated against the LAW's own datum.
                _foot = _ring_foot_reference(coords, zx, zy)
                zone_boxes.append({
                    "shape_id": id(s),
                    "ref": getattr(s, "ref", "") or "",
                    "key": zkey,
                    "xy": (float(zx), float(zy)),
                    "kind": row["kind"],
                    "depth_m": float(zd),
                    "floor_off": (None if zone_floor is None
                                  else float(zone_floor)),
                    "ceil_off": (None if zone_ceil is None
                                 else float(zone_ceil)),
                    "snap_tol_m": float(_CORRIDOR_SNAP_TOL_M),
                    # DATUM, as an identity the solve can bind:
                    # (1-t)·ring[i] + t·ring[i+1] on the host shape's
                    # own exterior.  ``host`` is the legacy
                    # frozen-nearest vertex, kept as the degrade path.
                    "foot": (None if _foot is None else {
                        "a": (float(coords[_foot[0]][0]),
                              float(coords[_foot[0]][1])),
                        "b": (float(coords[_foot[0] + 1][0]),
                              float(coords[_foot[0] + 1][1])),
                        "t": float(_foot[1]),
                        "gap_m": round(float(_foot[2]), 4)}),
                    "host": (float(zhost[0]), float(zhost[1])),
                    "host_delta": float(zdelta or 0.0),
                    "dem_seed": (None if _dem_seed is None
                                 else float(_dem_seed)),
                })
        entries.append({"shape": s, "fill": fill_bands, "cut": cut_bands,
                        "zone_rows": zone_rows,
                        "zone_nodes": zone_nodes,
                        "zone_boxes": zone_boxes,
                        "zone_values": None})
    layout.adjacent_ground_presolve = entries
    build_zone_constraint_table(layout)
    if _n_prolonged:
        UI.vprint(1, f"  [adjacent-ground] tile-seam prolongation: "
                     f"{_n_prolonged} cut-back run(s) marched off the "
                     f"un-cut frontage (owner ruling 2026-07-24).")
    if entries:
        n_bands = sum(len(e["fill"]) + len(e["cut"]) for e in entries)
        UI.vprint(1, f"  [adjacent-ground] PRE-SOLVE constructed raw bands "
                     f"for {len(entries)} shape(s), {n_bands} raw band(s) "
                     f"(one-solve terrain absorption, stage B3 order 1).")
    return len(entries)


def build_zone_constraint_table(layout) -> int:
    """ADJACENT-GROUND INGESTION — the CONSTRAINT SUPPLY.

    Publishes ``layout.adjacent_ground_zone_boxes``: one record per
    graded band node, carrying the zone law as a SOLVE-TIME constraint
    instead of a post-solve valuation.  This is the supply half of the
    single-solve ruling's "adjacent-ground band values" ingestion (owner
    2026-08-03: *ingest → refine geometry → ONE solve carrying ALL grade
    law → emit verbatim*).  The consumption half is the solve's
    (KILL lane) and the coupler's (SEATS lane); this side owns the
    numbers and their derivation.

    RECORD SHAPE — the contract, same family as the strip-fabric boxes
    (``one_solve._node_box_arrays`` consumes ``{index: (lo, hi)}``; these
    are keyed positionally because the pre-solve construct runs before
    the node list exists, exactly as ``zone_nodes`` already does)::

        {"shape_id": int,          # the OWNING pavement shape (identity)
         "ref":      str,
         "key":      (int, int),   # millimetre vertex key — the join
         "xy":       (x, y),       # layout metre frame
         "kind":     "cut" | "fill",
         "depth_m":  float,        # lateral depth the law was read at
         "floor_off": float|None,  # box, RELATIVE TO THE DATUM
         "ceil_off":  float|None,  #   (cut rows are ceiling-only)
         "snap_tol_m": float,      # quantization, not valuation
         "foot": {"a": (x, y), "b": (x, y), "t": float, "gap_m": float}
                  | None,          # THE DATUM, as an identity
         "host": (x, y),           # legacy frozen-nearest vertex
         "host_delta": float,      # seam-prolongation reference shift
         "dem_seed": float|None}   # the node's own DEM sample

    HOW THE SOLVE BINDS IT (the interface the KILL lane implements)::

        z[node] − ((1−t)·z[foot.a] + t·z[foot.b]) ∈ [floor_off, ceil_off]

    seeded at ``dem_seed``.  ``foot.a`` / ``foot.b`` are ring vertices of
    ``shape_id`` — variables the solve already owns — so the constraint
    is stated exactly in the law's own frame, with no post-solve
    re-reference.  Where ``foot`` is ``None`` the legacy pairwise slab
    against ``host`` is the degrade path.

    WHY THIS EXISTS — the v2 box was VACUOUS and the reason was measured
    (``seamv2/RESULTS.md`` §1 part 2), three independent causes, each
    sufficient:
      1. THE WRITEBACK RE-DERIVED.  ``solve.py``'s B3 zone writeback
         discards the solved value for every edge-owning zone node and
         recomputes ``clamp(raw DEM, ref + offsets)``.  A box around a
         value that IS the datum has no slack to remove.
      2. DATUM IDENTITY.  The spec's datum was "the writer's lawful
         value", i.e. the writeback's own expression — so the constraint
         and the value it constrained were the same formula.
      3. ORDERING + CHANNEL.  ``zone_values`` are written inside
         ``solve_route_profile``; the final projections that carried the
         box run strictly later, and no projection can write band values
         at all (``_writeback`` skips non-pavement roles).
    This table fixes (2) and (3) by construction: the datum is the FOOT
    (a pair of solved pavement variables, not a value the band writer
    produced), and the constraint is supplied BEFORE the solve rather
    than to a post-solve projection.  (1) is the KILL lane's handoff —
    the writeback's ``_zv = float(_dem_z)`` re-derivation must go, and
    the emitted band value must be the solved one.

    Returns the number of boxes published.
    """
    boxes: list = []
    for entry in (getattr(layout, "adjacent_ground_presolve", None) or ()):
        boxes.extend(entry.get("zone_boxes") or ())
    try:
        layout.adjacent_ground_zone_boxes = boxes
    except Exception:                                   # noqa: BLE001
        return 0
    if boxes:
        _footed = sum(1 for b in boxes if b.get("foot") is not None)
        UI.vprint(1,
            f"  [adjacent-ground] zone-law constraint SUPPLY: "
            f"{len(boxes)} band node box(es) "
            f"({_footed} with an exact foot datum, "
            f"{len(boxes) - _footed} on the frozen-nearest degrade "
            f"path) published on layout.adjacent_ground_zone_boxes.")
    return len(boxes)


def emit_adjacent_ground_bands(layout: PavementLayout, dem,
                               tile_lat: int, tile_lon: int,
                               source_runways=None) -> int:
    """Emit the adjacent-ground graded bands (gate
    ``ADJACENT_GROUND_LAW_ENABLED``).  Mutates ``layout.shapes``; returns
    the number of ``graded_strip`` / ``retaining_wall`` shapes emitted.

    Called as one of the LAST emissions (after the runway-end skirts, so
    the skirt geometry is in the static block and the bands clip against
    it at runway ends).  The bands bake the corridor from edge-
    interpolated pavement reads (the same containment-free reads the
    skirt uses), so nothing later re-solves them.
    """
    if dem is None:
        return 0
    # Order-2 apparatus instrumentation: emit-phase counters only (the
    # pre-solve construct march also increments the seam counter — the
    # reset here scopes the reported numbers to THIS emission).
    _reset_apparatus_hits()
    lat0, lon0 = layout.anchor
    cos0 = math.cos(math.radians(lat0))
    R = R_EARTH
    step = CLEARANCE_STATION_STEP_M

    def _ll_to_m(lat: float, lon: float) -> tuple[float, float]:
        return (math.radians(lon - lon0) * R * cos0,
                math.radians(lat - lat0) * R)

    def sample_dem(x: float, y: float):
        try:
            lat = lat0 + math.degrees(y / R)
            lon = lon0 + math.degrees(x / (R * cos0))
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            return None

    in_scope = _RUNWAY_ROLES + _TAXIWAY_ROLES + _APRON_ROLES
    # THE FABRIC MODEL — see the identical scoping in
    # ``construct_adjacent_ground_presolve``.  Inert when nothing armed.
    from .fabric_sparse import bands_declined as _bands_declined
    scoped = [s for s in layout.shapes
              if s.role in in_scope and s.polygon is not None
              and not s.polygon.is_empty
              and s.polygon.geom_type == "Polygon"
              and not _bands_declined(s)]
    if not scoped:
        return 0

    # Static block: EVERY existing shape, clipped EXACTLY (user ruling
    # 2026-07-09: the bands WELD to the pavement / features they grade
    # next to — the former 1 m standoff left a groove of raw DEM that
    # rendered as a knife-edge wall or trench along every constrained
    # edge at CYXY).  Shared boundaries carry the same coordinates and
    # (via the weld rows + value registry) agreeing values, so the mesh
    # welds them into one surface instead of minting wedges.
    # GROUNDSIDE EXCLUSION (user ruling 2026-07-09): no grading strip
    # touches groundside pavement — groundside follows the DEM (it IS
    # effectively terrain), so welding a law-floor strip onto its ring
    # imports conflicting values (the CYXY south-hangar violations); a
    # small standoff against it renders harmlessly (no cliff).
    # Groundside leaves the EXACT static union (no welded coordinates
    # against it) and instead blocks bands through a 1 m buffer.
    _gs_polys = [s.polygon for s in layout.shapes
                 if s.role == "groundside_pavement"
                 and s.polygon is not None and not s.polygon.is_empty]
    groundside_block = None
    if _gs_polys:
        try:
            groundside_block = unary_union(_gs_polys).buffer(1.0)
        except _GEOM_EXC:
            groundside_block = None
    # BUILDING STANDOFF block (2026-07-17): a building footprint sits at
    # its PAD altitude — often metres below the terrain the band rides
    # (a building in a graded pit).  The exact ``static_union`` clip makes
    # the band abut the building edge and share its corners, so the
    # ``to_osm`` nid-weld + authority-consensus stamps the pad value onto
    # a single band corner while its terrain neighbours stay high — a
    # sub-metre near-vertical TEAR (CYXY building1: 705.5 pad welded into
    # a 714.6 band edge, 9 m over 0.9 m).  A building is a DESIGNED SPLIT,
    # not a weld partner (the same ruling ``_WELD_DONOR_ROLES`` encodes:
    # bands never adopt a building/pad/terminal value), so the band stands
    # 1 m off the footprint — the tunnel-ramp / groundside standoff pattern
    # — and the pad corner never lands in a band vertex's canonical bucket.
    # A 1 m raw-DEM groove at the building base renders harmlessly (the
    # building occupies it).
    _bld_polys = [s.polygon for s in layout.shapes
                  if s.role == ROLE_BUILDING
                  and s.polygon is not None and not s.polygon.is_empty]
    building_block = None
    if _bld_polys:
        try:
            building_block = unary_union(_bld_polys).buffer(_PAVEMENT_GAP_M)
        except _GEOM_EXC:
            building_block = None
    # Tunnel-ramp STANDOFF block (scope B): 1 m around the tunnel mouth
    # pieces, so a strip stands off the steep mouth-ramp floor exactly like
    # a building.  Built here (before ``_emit_apron_walls`` adds its own
    # retaining_wall pieces) and only with the gate ON.  Empty (None) at
    # airports without a mapped tunnel — CYXY carries no tunnel_ramp or
    # pre-band retaining_wall, so gate-ON is byte-identical there.
    tunnel_ramp_block = (_tunnel_ramp_standoff_block(layout)
                         if _TUNNEL_STANDOFF else None)
    static_union = None
    _static_polys = [s.polygon for s in layout.shapes
                     if s.polygon is not None and not s.polygon.is_empty
                     and s.role != "groundside_pavement"]
    # ── RESERVED APRON-TERRACE SLOTS (item 4, 2026-08-05) ────────────
    # The apron-terrace pre-solve SPLIT cuts a ``STACKED_WALL_RETREAT_M``
    # band out of an apron for every declared joint, and the
    # ``retaining_wall`` that fills it is minted at the very END of the
    # build — inside the strip reconcile unit, which by standing owner
    # ruling runs after the LATE final grade projection, because the face
    # reads its two panels' FINAL settled values by identity.  So at THIS
    # point the slot is ground no shape covers, and the march would
    # happily grade a strip into it: measured at HECA, a strip marched
    # into 12.9% of the published slot area (381 m² over 32 of 79 bands)
    # and would then be overwritten, or averaged against, a wall standing
    # on the same ground.
    #
    # Reordering cannot fix this — the faces genuinely cannot be minted
    # earlier without reading pre-projection values.  The march instead
    # reads the LIVE reservation: ``apron_terrace_wall_bands`` is
    # published at plan time, where the band geometry is first known, for
    # exactly this reader.  Ground that is spoken for is not marchable.
    _slot_bands = [b for b in
                   (getattr(layout, "apron_terrace_wall_bands", None) or ())
                   if b is not None and not b.is_empty
                   and b.geom_type == "Polygon"]
    if _slot_bands:
        _static_polys.extend(_slot_bands)
    try:
        static_union = unary_union(_static_polys)
    except _GEOM_EXC:
        static_union = None
    if static_union is None or static_union.is_empty:
        return 0
    try:
        prep_static = prep(static_union)
    except _GEOM_EXC:
        return 0
    # APRON WALL SCOPE (owner ruling 2026-07-25): built ONCE for the whole
    # emission — over PAVEMENT roles only, so it is the same index the
    # validator's MIRROR 6 rebuilds after the bands land.  ``None`` with
    # the gate off — the march and the wall pass are then unfiltered.
    _wall_scope_index = (apron_wall_pavement_adjacency_index(layout)
                         if _APRON_WALL_SCOPE else None)
    # RAY-OCCLUSION PUBLICATION (2026-07-25, the crossing-zone pattern):
    # the validator's MIRROR 5 must occlude against the EXACT geometry the
    # emitter marched through, and it cannot rebuild it — by verify time
    # ``layout.shapes`` also carries this pass's own ``graded_strip`` bands
    # (which weld to the pavement edge, so rebuilding would occlude every
    # ray at the first sample and blind the reader) plus the apron
    # ``retaining_wall`` pieces ``_emit_apron_walls`` appends BELOW.
    # Published here, at the state the march reads.  Absent (this emitter
    # never ran / gate off) the validator simply does not occlude — the
    # pre-mirror reader verbatim.
    if _RAY_OCCLUSION:
        layout.adjacent_ground_occlusion = static_union
    boundary = layout.airport_boundary
    # Taxiway-end WRAP join target (scope A): built once, passed to the
    # inline (legacy-path) march for taxiway shapes with the gate ON.  The
    # gate-ON solver path consumes pre-built footprints
    # (``construct_adjacent_ground_presolve`` already wrapped there), so this
    # only feeds the inline re-march; byte-inert with the gate OFF.
    wrap_skirt_prep = (_runway_end_skirt_prep(layout)
                       if _END_WRAP else None)
    # CROSSING INFLUENCE ZONE (Phase 1, docs/specs/crossing-terrain-
    # ownership.md): the ONE published zone replaces the crossing-union
    # branch of the standoff block AND the road-lane exclusion — the band
    # pieces are DIFFERENCED against it below and the station-level drop
    # feeds the inline re-march path.  Published pre-solve, so construct
    # and emit consult the identical geometry.  Byte-inert when nothing
    # is published (both are None).
    crossing_zone_union = _crossing_zone_union(layout)
    crossing_zone_prep = (_crossing_zone_prep(layout)
                          if crossing_zone_union is not None else None)
    if (os.environ.get("O4_CROSSING_ZONE_DEBUG") == "1"
            and crossing_zone_union is not None):
        # (The zone WKT dump lives at PUBLICATION — O4_CROSSING_ZONE_DUMP
        # in ``crossing_terrain`` — never here: two writers to one path
        # clobbered the publication dump.)
        _area = (crossing_zone_union.area
                 if not crossing_zone_union.is_empty else 0.0)
        print(f"  [crossing-zone-debug] band-emit crossing zone union "
              f"area = {_area:.1f} m2")
    # The clip block carries a margin over the zone itself (the buffered-
    # standoff pattern, ``_PAVEMENT_GAP_M``): a band stands off the zone
    # boundary rather than welding onto it, and the post-clip ring
    # decimation/simplification cannot bow a long clipped edge back INTO
    # the zone (measured KBNA: a 7 m2 sliver on a 36,000 m2 merged strip
    # from a 0-margin lane clip).
    crossing_zone_clip_block = None
    if crossing_zone_union is not None:
        try:
            crossing_zone_clip_block = crossing_zone_union.buffer(
                _PAVEMENT_GAP_M)
        except _GEOM_EXC:
            crossing_zone_clip_block = crossing_zone_union

    # COLLARED-POCKET ZONE (arc B1).  Two halves, both needed: the march
    # test below stands the pocket-facing STATIONS down, and this clip
    # block removes any band POLYGON that still reaches into the pocket —
    # which is the only protection under the frozen-footprint gate state
    # (``_presolve_bands``), where the station march is not re-run.
    #
    # EXACT geometry, ZERO buffer (weld ruling 2026-07-09): a band and a
    # collar ring must meet on shared coordinates or not at all; buffering
    # them apart would mint a standoff groove of raw DEM between two
    # graded surfaces.
    collar_zone_union = _collar_zone_union(layout)
    collar_zone_prep = (_collar_zone_prep(layout)
                        if collar_zone_union is not None else None)
    collar_zone_clip_block = collar_zone_union
    # AIRSIDE-ENCLAVE keep-out (owner 2026-08-07; SCOPING v2).  ONE form
    # only — the exact-geometry clip below and the wall emitter's twin of
    # it.  The v1 prepared-zone STATION stand-down is gone: it saw only a
    # station's seed and its 1.5 m probe, yet deleted the whole row those
    # anchored, which marches ``reach`` metres over ground the keep-out
    # does not own (HECA measurement in ``_station_reference_ex``).
    enclave_zone_clip_block = _enclave_zone_union(layout)
    _enclave_band_area_taken = 0.0
    # The wall emitter is a separate function, so its share of the area
    # comes back through a one-slot sink (the module's existing idiom for
    # per-emission tallies that cross a helper boundary).
    _enclave_area_sink = [0.0]
    # STRIP PRECEDENCE §1 + §2 (``O4_STRIP_PRECEDENCE``): the prepared
    # LATERAL strip, built once per emission; ``None`` with the gate off.
    # Between the ends only — the end corridors keep the runway-END
    # regime's own law, both for the §1 swap and the §2 cap.
    strip_lateral_prep = runway_strip_lateral_zone(layout)

    # CONFORM-TO-STATIC (chain identity, 2026-07-09): a band row that
    # runs just OUTSIDE a foreign shape's edge (10-15 cm — daylight
    # rows, taper stations, clip residue) is never cut by the exact
    # difference (no overlap) and never welded by the 1 cm conformance
    # pass — it survives as a near-parallel constrained pair, and ONE
    # such lens Ruppert-refines to ~10⁵-10⁶ tile triangles (measured
    # at CYXY).  Two moves make the soft ring ADOPT the static chain
    # wherever it runs within ``_SNAP_TO_STATIC_M`` of it:
    #   1. SPLIT every ring edge at the projections of nearby static
    #      VERTICES (a mid-span edge next to a static corner has no
    #      ring vertex to snap — the 88 mm skirt-corner lens class);
    #   2. SNAP every ring vertex (original + inserted) onto the
    #      nearest static exterior.
    # After both, the ring boundary follows the static chain
    # vertex-for-vertex and the final weld unifies them.  Under-
    # pavement grading needs no centimetre fidelity (user 2026-07-09),
    # so a ≤0.2 m lateral adopt is free.
    _SNAP_TO_STATIC_M = 0.2
    from shapely import STRtree as _STRtree
    _static_ext = []
    _static_ext_shape = []   # owner shape per exterior (edge-weld values)
    for _s in layout.shapes:
        if _s.role == "groundside_pavement":
            continue        # never adopt groundside chains (ruling)
        if _s.polygon is not None and not _s.polygon.is_empty:
            try:
                _static_ext.append(_s.polygon.exterior)
            except _GEOM_EXC:
                continue
            _static_ext_shape.append(_s)
    try:
        _static_ext_tree = _STRtree(_static_ext)
    except _GEOM_EXC:
        _static_ext_tree = None
    _static_verts = []
    for _ext in _static_ext:
        _static_verts.extend(list(_ext.coords)[:-1])
    try:
        _static_vert_tree = _STRtree(
            [Point(vx, vy) for vx, vy in _static_verts])
    except _GEOM_EXC:
        _static_vert_tree = None

    def _snap_ring_to_static(ring):
        if _static_ext_tree is None:
            return ring
        # 1. split edges at nearby static-vertex projections
        if _static_vert_tree is not None:
            split_ring = []
            n = len(ring)
            for i in range(n):
                ax, ay = ring[i]
                bx, by = ring[(i + 1) % n]
                split_ring.append((ax, ay))
                dx, dy = bx - ax, by - ay
                L2 = dx * dx + dy * dy
                if L2 < 1e-12:
                    continue
                try:
                    cand = _static_vert_tree.query(
                        LineString([(ax, ay), (bx, by)]).buffer(
                            _SNAP_TO_STATIC_M))
                except _GEOM_EXC:
                    continue
                inserts = []
                for gi in cand:
                    vx, vy = _static_verts[gi]
                    t = ((vx - ax) * dx + (vy - ay) * dy) / L2
                    if t <= 1e-6 or t >= 1.0 - 1e-6:
                        continue
                    px_, py_ = ax + t * dx, ay + t * dy
                    perp = math.hypot(vx - px_, vy - py_)
                    L = math.sqrt(L2)
                    if (perp > _SNAP_TO_STATIC_M or t * L < 0.05
                            or (1.0 - t) * L < 0.05):
                        continue
                    inserts.append((t, vx, vy))
                # insert the static VERTEX itself (not the foot):
                # the snapped ring must pass through the static
                # chain's own points to share its constrained edges.
                for _t, vx, vy in sorted(inserts):
                    if split_ring[-1] != (vx, vy):
                        split_ring.append((vx, vy))
            ring = split_ring
        # 2. snap all vertices onto the nearest static exterior
        snapped = []
        for x, y in ring:
            pt = Point(x, y)
            best_d, best_pt = None, None
            try:
                cand = _static_ext_tree.query(
                    pt.buffer(_SNAP_TO_STATIC_M + 0.01))
            except _GEOM_EXC:
                snapped.append((x, y))
                continue
            for gi in cand:
                ext = _static_ext[gi]
                try:
                    d = ext.distance(pt)
                except _GEOM_EXC:
                    continue
                if d <= _SNAP_TO_STATIC_M and (
                        best_d is None or d < best_d):
                    best_d, best_pt = d, ext.interpolate(
                        ext.project(pt))
            if best_pt is not None and best_d > 1e-9:
                snapped.append((best_pt.x, best_pt.y))
            else:
                snapped.append((x, y))
        return snapped

    # STATIC-EDGE VALUE WELD (B4 flip defect 2, 2026-07-15).  A band clip
    # vertex lying ON a FOREIGN static shape's edge (the exact
    # ``difference`` clip and ``_snap_ring_to_static`` both mint them) is
    # part of THAT surface's chain — its value is that surface's solved
    # edge altitude, never the band's own corridor/zone reading.  The
    # solved-band resampler's weld test knows only the band's HOST ring,
    # so before this weld a junction-edge clip vertex took a zone-row
    # value up to the corridor envelope away from the junction's solved
    # surface (CYXY: 709.8 vs 709.94), and the final epsilon-wedge weld
    # then stamped that value into the junction ring — the B4 junction
    # spine-grade violations the legacy clearance strips used to mask by
    # occupying the ground.  Lazy per-exterior edge references (the same
    # ``_ring_edge_reference`` read every resampler uses).
    _STATIC_WELD_TOL_M = 0.02
    _static_edge_ref_cache: dict = {}
    # Value-donor scope: the surfaces the band law grades TO — airside
    # pavement plus the pavement-pinned clearance family (runway-end
    # skirts, legacy clearance strips).  Bridge plates, tunnel walls/
    # ramps, pads, terminals never donate: a band meeting one of those is
    # a DESIGNED split (deck cliff / wall / standoff), not a weld.
    from .layout import (ROLE_RUNWAY_CLEARANCE as _R_RWCL,
                         ROLE_TAXIWAY_CLEARANCE as _R_TWCL)
    # THE single donor-role source lives in layout.py (WELD_DONOR_ROLES,
    # 2026-07-17) — shared with to_osm's strip-adoption consensus so the
    # static-edge weld and the emit consensus can never disagree on who
    # may donate a value to a soft strip.
    from .layout import WELD_DONOR_ROLES as _WELD_DONOR_ROLES

    def _static_edge_weld_alt(x, y):
        if _static_ext_tree is None:
            return None
        pt = Point(x, y)
        try:
            cand = _static_ext_tree.query_nearest(
                pt, max_distance=_STATIC_WELD_TOL_M)
        except _GEOM_EXC:
            return None
        cand = [gi for gi in cand
                if (_static_ext_shape[gi].role or "") in _WELD_DONOR_ROLES]
        if not cand:
            return None
        best_gi = int(min(cand))    # deterministic among exact ties
        ref = _static_edge_ref_cache.get(best_gi)
        if ref is None:
            ext_coords = list(_static_ext[best_gi].coords)
            ref = _ring_edge_reference(
                ext_coords,
                _shape_ring_alts(_static_ext_shape[best_gi], ext_coords))
            _static_edge_ref_cache[best_gi] = ref
        ref_line, ref_alt_at = ref
        alt = ref_alt_at(ref_line.project(pt))
        return None if alt is None else float(alt)

    # Row-100 runway axes (authoritative length + direction) for runway
    # code-number keying and END-edge skipping — as the ring-edge sweep.
    rw_axes: list[tuple] = []
    if source_runways:
        for r in source_runways:
            try:
                rax, ray = _ll_to_m(r.lat_a, r.lon_a)
                rbx, rby = _ll_to_m(r.lat_b, r.lon_b)
            except _GEOM_EXC:
                continue
            rlen = math.hypot(rbx - rax, rby - ray)
            if rlen < 1.0:
                continue
            # 4th slot: the runway's two apt.dat END approach classes.
            # ``_family_params`` hands them to the march so the OLS
            # handover S is computed from the SAME classes ``ols.py``
            # uses (slice 4, "one S") instead of a hardcoded default.
            rw_axes.append((LineString([(rax, ray), (rbx, rby)]),
                            ((rbx - rax) / rlen, (rby - ray) / rlen),
                            rlen,
                            (runway_end_approach_class(
                                getattr(r, "markings_a", 0),
                                getattr(r, "approach_lights_a", 0)),
                             runway_end_approach_class(
                                getattr(r, "markings_b", 0),
                                getattr(r, "approach_lights_b", 0)))))

    trigger_by_family = {
        "runway": CLEARANCE_OBSTRUCTION_THRESHOLD_M["runway"],
        "taxiway": CLEARANCE_OBSTRUCTION_THRESHOLD_M["taxiway"],
        "apron": CLEARANCE_OBSTRUCTION_THRESHOLD_M["taxiway"],
    }
    # RUNWAY-STRIP WALL KEEP-OUT (owner ruling 2026-08-01): built once for
    # the whole pass; ``None`` with the gate off (the apron-wall emitter
    # then differences nothing — byte-identical).
    _strip_keepout = runway_strip_wall_keepout(layout)

    # Accumulate per-shape (ring, alts) bands + wall shapes, then clip +
    # emit once.  TWO overlap unions with DIFFERENT clip rules (round 2,
    # the strip↔strip wedge fix):
    #   * ``previous_shapes_union`` — bands of EARLIER parent shapes.
    #     Their corridors are computed off DIFFERENT edge references, so
    #     where two shapes' bands meet the values genuinely disagree;
    #     coincident traced boundaries then emit same-XY node pairs whose
    #     wall ENDPOINTS mint zero-angle duplicate-edge wedges (HECA
    #     round-2: 32).  Later shapes clip a full PAVEMENT-GAP standoff
    #     from earlier shapes' bands — a 1 m terrain groove instead of a
    #     shared boundary (no shared geometry, no wedge; the DEM reader
    #     exempts columns within the gap of any shape, so coverage holds).
    #   * ``current_shape_union`` — pieces of the SAME shape (fill vs cut
    #     vs zone splits).  One corridor, one resampler: values agree at
    #     shared coordinates, so these seams stay EXACT and weld into one
    #     continuous surface.
    emitted = 0
    previous_shapes_union = None
    current_shape_union = None
    emitted_shapes: list[BuiltShape] = []
    # VALUE-AGREEMENT registry (feature-weld rule): same-shape pieces abut
    # along clip boundaries coordinate-exactly; first writer wins so a
    # shared coordinate never carries two values (guarded adoption below).
    vertex_value_registry: dict[tuple[int, int], float] = {}
    # AUTHORITY keys (user ruling 2026-07-09, round 2: the PAVEMENT
    # value ALWAYS wins at a pavement node): keys registered by a
    # non-soft shape adopt UNCONDITIONALLY — no tolerance guard.  The
    # guard below stays only for soft↔soft coincidences (a skirt/strip
    # value a band happens to land on).  Without this, a band carrying
    # a skirt-derived value onto a junction ring vertex minted a
    # second node 1.71 m below the junction's — an unmerged-node cliff
    # (CYXY 60.6971601,-135.0592654, junction #111).
    authority_value_keys: set[tuple[int, int]] = set()
    # DONOR-GATED (2026-07-17, the WELD_DONOR_ROLES ruling applied to
    # this registry — the third foreign-value writer alongside the
    # static-edge weld and to_osm's strip adoption): unconditional
    # adoption is reserved for keys registered by a WELD_DONOR_ROLES
    # shape (runway/taxi/apron/clearance families).  A designed split
    # (service road, building pad, terminal, groundside, bridge plate)
    # is an authority for its OWN nodes but never donates: a band clip
    # vertex landing on its ring corner keeps the band's lawful value —
    # the value step renders as the designed wall (measured CYXY strip
    # #518: service-road 709.5 spliced into a 705.7 band edge = 3.9 m
    # over 1.3 m, collapsing to a 0-length in-ring tear at emit).
    donor_value_keys: set[tuple[int, int]] = set()
    # EMITTED-VERTEX POSITION weld (chain identity, site-2 fix 2026-07-10):
    # a later band trimmed against an earlier band's union by the exact
    # ``difference()`` clip is cut along the earlier band's EDGE, so GEOS
    # mints an intersection vertex a few millimetres from the earlier
    # band's CORNER rather than adopting the corner itself.  The two
    # graded_strip writers then emit a 5-6 mm near-parallel / T-vertex
    # pair (the site-2 residual: 60.7208676,-135.0790956).  The mm-keyed
    # ``vertex_value_registry`` cannot unify them (P and its 6 mm twin Q
    # hash to different millimetre keys) and ``_snap_ring_to_static`` does
    # not either — it snaps only to the PRE-EXISTING pavement/junction
    # shapes captured before the loop, never to a sibling band emitted
    # during it.  So keep a coarse spatial hash of every emitted-band
    # vertex and snap each freshly-clipped ring vertex onto a prior
    # emitted-band vertex within a TIGHT distance (the epsilon-wedge
    # class only).  GATED ON VALUE AGREEMENT: only weld when the two
    # bands' altitudes match within ``VERTEX_ALT_MERGE_TOL_M`` — that is
    # exactly the "should agree by construction" class the sub-centimetre
    # seam represents.  Where the two bands' corridors genuinely step
    # (>1 m, a lawful vertical wall between two taxiways' fills), leaving
    # the vertices at their clip positions preserves the pre-existing
    # ``to_osm`` distance-merge (one interned node); forcing them exactly
    # coincident there would instead mint a two-node wall ``to_osm`` keeps
    # (the ``VERTEX_ALT_MERGE_TOL_M`` split rule).  Insert-only in effect
    # (≤1 cm move); the same identity convention the mm value registry
    # uses.
    _BAND_CORNER_WELD_TOL_M = 0.01
    _WELD_CELL_M = 0.02
    # cell -> list of (x, y, altitude) for prior emitted-band vertices.
    emitted_vertex_cells: \
        dict[tuple[int, int], list[tuple[float, float, float]]] = {}

    def _weld_cell(vx, vy):
        return (int(math.floor(vx / _WELD_CELL_M)),
                int(math.floor(vy / _WELD_CELL_M)))

    def _weld_ring_to_prior_bands(ring_coords, own_alts):
        """Snap each ring vertex onto the nearest prior emitted-band
        vertex within ``_BAND_CORNER_WELD_TOL_M`` whose altitude agrees
        within ``VERTEX_ALT_MERGE_TOL_M``; return the snapped,
        consecutive-deduplicated open ring (unchanged object identity
        when nothing snaps)."""
        if not emitted_vertex_cells:
            return ring_coords
        snapped = []
        moved = False
        for (vx, vy), ov in zip(ring_coords, own_alts):
            cx, cy = _weld_cell(vx, vy)
            best = None
            best_d = _BAND_CORNER_WELD_TOL_M
            for ox in (cx - 1, cx, cx + 1):
                for oy in (cy - 1, cy, cy + 1):
                    for px, py, pv in emitted_vertex_cells.get(
                            (ox, oy), ()):
                        d = math.hypot(vx - px, vy - py)
                        if d < best_d and (
                                ov is None or pv is None
                                or abs(pv - ov) <= VERTEX_ALT_MERGE_TOL_M):
                            best_d, best = d, (px, py)
            if best is not None and best != (vx, vy):
                snapped.append(best)
                moved = True
                _APPARATUS_HITS["band_corner_weld_snaps"] += 1
            else:
                snapped.append((vx, vy))
        if not moved:
            return ring_coords
        dedup: list[tuple[float, float]] = []
        for p in snapped:
            if not dedup or dedup[-1] != p:
                dedup.append(p)
        if len(dedup) >= 2 and dedup[0] == dedup[-1]:
            dedup.pop()
        return dedup

    def _register_emitted_vertices(ring_coords, ring_alts):
        for (vx, vy), va in zip(ring_coords, ring_alts):
            emitted_vertex_cells.setdefault(
                _weld_cell(vx, vy), []).append((vx, vy, va))

    # PRIOR-BAND FOOTPRINT INDEX (robust deconflict, 2026-07-17): a coarse
    # bbox-cell bucket of every band polygon emitted so far, so each new
    # piece can subtract the FEW earlier bands it actually meets one at a
    # time (robust) instead of trusting the giant accumulated union's
    # ``difference`` (which GEOS silently no-ops once the union is large —
    # the band∩band overlap source).  Keyed by 32 m cells over each band's
    # bounding box.
    _PRIOR_BAND_CELL_M = 32.0
    _prior_band_index: dict[tuple[int, int], list] = {}

    def _band_cells(bounds):
        x0, y0, x1, y1 = bounds
        cx0 = int(math.floor(x0 / _PRIOR_BAND_CELL_M))
        cy0 = int(math.floor(y0 / _PRIOR_BAND_CELL_M))
        cx1 = int(math.floor(x1 / _PRIOR_BAND_CELL_M))
        cy1 = int(math.floor(y1 / _PRIOR_BAND_CELL_M))
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                yield (cx, cy)

    def _register_prior_band(band_poly):
        try:
            b = band_poly.bounds
        except _GEOM_EXC:
            return
        for cell in _band_cells(b):
            _prior_band_index.setdefault(cell, []).append(band_poly)

    def _nearby_prior_bands(poly):
        try:
            cells = set(_band_cells(poly.bounds))
        except _GEOM_EXC:
            return []
        seen: set[int] = set()
        out = []
        for cell in cells:
            for bp in _prior_band_index.get(cell, ()):
                if id(bp) not in seen:
                    seen.add(id(bp))
                    out.append(bp)
        return out

    # STATIC-FOOTPRINT INDEX (same robustness class as the band index):
    # ``poly.difference(static_union)`` above shares the GEOS overlay
    # no-op failure once ``static_union`` is large, so a band can survive
    # lapping a foreign pavement / junction by a sliver (CYXY: 0.14 m² over
    # a service_junction).  Index the individual static footprints so the
    # deconflict can re-subtract the few the piece actually meets (robust).
    _static_poly_index: dict[tuple[int, int], list] = {}
    for _sp in _static_polys:
        if _sp is None or _sp.is_empty or _sp.geom_type != "Polygon":
            continue
        try:
            for _cell in _band_cells(_sp.bounds):
                _static_poly_index.setdefault(_cell, []).append(_sp)
        except _GEOM_EXC:
            continue

    def _nearby_static_polys(poly):
        try:
            cells = set(_band_cells(poly.bounds))
        except _GEOM_EXC:
            return []
        seen: set[int] = set()
        out = []
        for cell in cells:
            for sp in _static_poly_index.get(cell, ()):
                if id(sp) not in seen:
                    seen.add(id(sp))
                    out.append(sp)
        return out

    # WELD-VALUE PRELOAD (user ruling 2026-07-09): every EXISTING shape's
    # ring vertices register their exact solved values first, so a band
    # vertex landing on a pavement / skirt / strip vertex ADOPTS that
    # value verbatim — value authorities never move, the band adopts.
    from .layout import SOFT_RECEIVER_ROLES as _SOFT_ROLES
    for s in layout.shapes:
        if s.role == "groundside_pavement":
            continue        # groundside values never adopted (ruling)
        if s.polygon is None or s.polygon.is_empty \
                or s.polygon.geom_type != "Polygon":
            continue
        try:
            existing_coords = list(s.polygon.exterior.coords)
        except _GEOM_EXC:
            continue
        na = s.node_altitudes
        s_is_authority = (s.role or "") not in _SOFT_ROLES
        s_is_donor = (s.role or "") in _WELD_DONOR_ROLES
        for i, (vx, vy) in enumerate(existing_coords):
            if na and i < len(na) and na[i] is not None:
                value = float(na[i])
            elif not na and s.altitude is not None:
                value = float(s.altitude)
            else:
                continue
            k = _vertex_key(vx, vy)
            if s_is_authority and k not in authority_value_keys:
                # Authority value WINS the registry even over an
                # earlier soft registration.
                vertex_value_registry[k] = value
                authority_value_keys.add(k)
                if s_is_donor:
                    donor_value_keys.add(k)
            elif (s_is_authority and s_is_donor
                    and k not in donor_value_keys):
                # A DONOR authority (pavement the band welds to)
                # outranks an earlier non-donor authority at a shared
                # seam corner — the band must adopt the pavement side
                # of the seam, not the designed split's.
                vertex_value_registry[k] = value
                donor_value_keys.add(k)
            elif k not in vertex_value_registry:
                vertex_value_registry[k] = value

    # CONTINUATION-SEAM keys (user 2026-07-10): vertices shared between two
    # airside pavement shapes.  A terminal band station adjacent to one is a
    # run boundary from the pavement PARTITION, not a frontage end, so the
    # daylight bench-in is suppressed there (grade_law) — the two abutting
    # runs' terminal stations then agree on outer depth (no seam notch).
    seam_keys = airside_seam_vertex_keys(layout) if _SEAM_TAPER_PIN else set()

    # PRE-BUILT FOOTPRINT store (Slice B stage B3 order 1): gate-ON the raw
    # band rings were marched pre-solve; index them by source-shape identity so
    # the loop consumes them instead of re-marching.  Gate-OFF (default, or no
    # store) ``_presolve_bands`` stays None and the loop marches inline.
    #
    # ORDER 2 (variable ADMISSION, gate ``ONE_SOLVE_TERRAIN_GRADED_STRIP``
    # — hard-error-chained onto construct + B1 + B2 in
    # ``solver_primitives.admitted_terrain_refs``): the pre-built
    # footprints are NOT consumed.  The loop marches inline over the
    # FINAL solved, decimated, densified pavement ring — so the emitted
    # band inner (weld) chain is BY CONSTRUCTION the final pavement
    # chain (the order-1 82-band census inflation collapses back to the
    # gate-OFF footprint), and the construct store's role narrows to the
    # ZONE-NODE VARIABLE GRID plus its solved values.  Re-deriving the
    # run/band segmentation over the final chain and re-mapping the
    # solved values onto the re-derived rows is SOUND because the band
    # law has no neighbour coupling — every zone value is independent
    # (clamp of the DEM into its own host-referenced corridor), so
    # regrouping independently-valued vertices cannot violate anything
    # (order-2 scout refutation 1, ratified 2026-07-11).
    from .config import (ONE_SOLVE_TERRAIN as _OST,
                         ONE_SOLVE_TERRAIN_GRADED_STRIP as _OST_ADMIT,
                         ONE_SOLVE_TERRAIN_GRADED_STRIP_CONSTRUCT as _OST_C)
    _presolve_bands = None
    _solved_store = None
    if _OST and _OST_ADMIT:
        # Reuses the hard dependency chain: reading the admitted set
        # raises loudly on a partial gate configuration.
        from .elevation_per_surface.solver_primitives import (
            admitted_terrain_refs as _admitted_refs_fn)
        if (ROLE_GRADED_STRIP, _ADJACENT_REF) in _admitted_refs_fn():
            _store = getattr(layout, "adjacent_ground_presolve", None)
            if _store:
                _solved_store = {id(e["shape"]): e for e in _store}
    elif _OST and _OST_C:
        _store = getattr(layout, "adjacent_ground_presolve", None)
        if _store:
            _presolve_bands = {id(e["shape"]): e for e in _store}

    # TILE-SEAM PROLONGATION (owner ruling 2026-07-24) — see
    # ``_seam_prolonged_ring``.  Applied here too (not only in the pre-solve
    # construct) so the gate-OFF inline march AND the resampler's edge
    # projection both reference the same un-cut frontage as the footprint.
    _offcut_union = seam_offcut_union(layout)
    _n_prolonged = 0

    for s in scoped:
        current_shape_union = None
        params = _family_params(layout, s, rw_axes)
        if params is None:
            continue
        family, code_number, code_letter, reach, width, axis, \
            axis_line, axis_classes = params
        trigger = trigger_by_family[family]

        ceil_off, envelope_at, floor_depth = _band_family_closures(
            family, code_number, code_letter, width)

        # Per-CLOSED-ring node altitudes aligned with the ring coords (the
        # node_altitudes contract), else the shape's plane sampler.  Read
        # from the SOLVED shape (values are always analytic post-solve, both
        # configurations).
        try:
            coords = list(s.polygon.exterior.coords)
            ccw = bool(s.polygon.exterior.is_ccw)
        except _GEOM_EXC:
            continue
        if len(coords) < 4:
            continue
        ring_alts = _shape_ring_alts(s, coords)
        # ``reach`` in every gate state.  The ``width`` tightening was
        # only valid while A4 clamped the CUT as well; now that A4 owns
        # the fill cap alone, a ``width``-capped prolongation would
        # under-prolong the CUT frontage at a tile seam.  ``reach`` is a
        # safe upper bound in all four gate combinations.
        _depth_cap = reach
        coords, _pro_arrays, _npro = _seam_prolonged_ring(
            layout, coords, ccw, [ring_alts], _depth_cap, _offcut_union)
        if _npro:
            ring_alts = _pro_arrays[0]
            _n_prolonged += _npro

        # FOOTPRINT SOURCE.  Gate-ON (B3 order 1) the raw band rings were
        # marched PRE-SOLVE from the DEM-seeded estimate
        # (``construct_adjacent_ground_presolve``) and staged on
        # ``layout.adjacent_ground_presolve``; consume them here instead of
        # re-marching.  The emitter still CLIPS them against the (post-solve)
        # static block and VALUES every vertex off the solved altitudes
        # below, so gate-ON is value-equivalent to gate-OFF up to the
        # enumerated seed/late-feature footprint deltas.  Gate-OFF the march
        # runs inline exactly as today through the shared helper
        # (byte-identical).
        # APRON WALL SCOPE (owner ruling 2026-07-25): ONE qualifier per
        # shape, shared by the march and the wall pass below — they walk
        # the same station list, and the qualifier memoizes per station,
        # so the STRtree query is paid once per station per airport.
        _apron_q = (apron_wall_frontage_qualifier(s, _wall_scope_index)
                    if family == "apron" else None)
        # STRIP PRECEDENCE §1 (law swap): this shape's governing strip
        # parameters, and the channel the march returns strip-law bands on
        # so they can be VALUED through the strip corridor below.
        _strip_full = (
            _strip_law_params(layout, s, rw_axes, trigger_by_family,
                              with_envelope=True)
            if (strip_lateral_prep is not None and family != "runway")
            else None)
        _strip_law = _strip_full[:6] if _strip_full else None
        _strip_bands: list = [] if _strip_law else None
        _pre = _presolve_bands.get(id(s)) if _presolve_bands else None
        if _pre is not None:
            fill_bands, cut_bands = _pre["fill"], _pre["cut"]
            stations, st_alts, outs = [], [], []
        else:
            (fill_bands, cut_bands,
             stations, st_alts, outs) = _derive_shape_stations_and_bands(
                coords, ccw, ring_alts, axis, width, reach, trigger,
                floor_depth, ceil_off, step, prep_static, seam_keys,
                sample_dem,
                wrap_skirt_prep=(wrap_skirt_prep
                                 if family == "taxiway" else None),
                crossing_zone_prep=(crossing_zone_prep
                                    if family == "taxiway" else None),
                # ALL families (unlike the taxiway-only crossing zone): a
                # width-skipped pocket is ringed by MIXED roles, so runway
                # and apron frontage face it just as taxiway frontage does.
                collar_zone_prep=collar_zone_prep,
                # STRIP PRECEDENCE §1 — NON-runway families only (see the
                # construct-side call and ``runway_strip_lateral_zone``).
                strip_zone_prep=(strip_lateral_prep
                                 if family != "runway" else None),
                strip_law=_strip_law,
                # §A3(a) — same term at emit (see the construct call).
                strip_longitudinal=(
                    _strip_longitudinal_law_for(layout, s, rw_axes)
                    if _strip_law else None),
                strip_bands_out=_strip_bands,
                axis_line=axis_line,
                axis_classes=axis_classes,
                # APRON WALL SCOPE — apron frontage only (owner ruling
                # 2026-07-25): open-terrain stations take no fill band.
                fill_station_filter=_apron_q)
        if not fill_bands and not cut_bands:
            continue

        # Band-vertex value rule.  Every emitted (possibly clipped) vertex
        # gets its altitude ANALYTICALLY from its TRUE lateral distance to
        # the pavement edge (shapely projection onto the shape's ring): the
        # DEM CLAMPED INTO the law corridor at that distance (see
        # ``_make_edge_projection_resampler``).  Robust for both edge and
        # INTERIOR clip vertices and on concave rings, so a clip introduces
        # no step; law-true by construction (the surface can never leave
        # the corridor).
        resample_alt = _make_edge_projection_resampler(
            coords, ring_alts, envelope_at, width, sample_dem)
        # ORDER-2 gate-ON valuation swap: the analytic corridor clamp
        # above becomes the per-vertex FALLBACK only (counted); every
        # reachable vertex reads the SOLVED band surface instead.
        if _solved_store is not None:
            _solved_entry = _solved_store.get(id(s))
            if (_solved_entry is not None
                    and _solved_entry.get("zone_values")):
                resample_alt = _make_solved_band_resampler(
                    _solved_entry, coords, ring_alts, resample_alt,
                    # EMIT-SIDE CORRIDOR CLAMP (2026-07-25): the SAME
                    # corridor closure + band cap the analytic resampler
                    # above was built with, so the solved path cannot
                    # emit a value the analytic path would have refused.
                    envelope_at=envelope_at, graded_width_m=width)
            else:
                # LOUD COMPLETENESS (single-solve architecture): a graded
                # band whose values the solve never produced is a hole in
                # the ingestion, not a degrade mode to live with.  Every
                # vertex of this shape will be valued ANALYTICALLY — a
                # second grading authority at emit — so it is named at
                # vprint(0), with its shape, and counted.  Pre-registered
                # zero once the solve consumes the box table.
                _APPARATUS_HITS["solved_store_missing_shape"] += 1
                UI.vprint(0, f"  [adjacent-ground] INGESTION HOLE: no "
                             f"solved zone values for shape role={s.role} "
                             f"ref={s.ref} — its whole band is valued "
                             f"analytically at emit (a second grading "
                             f"authority; must read 0).")
        # STATIC-EDGE VALUE WELD (B4 flip defect 2): a band vertex ON any
        # static shape's edge takes THAT surface's solved edge value
        # (weld precedence), with the host-corridor/zone valuation above
        # as the fallback for every off-edge vertex.
        _corridor_resample = resample_alt

        def resample_alt(vx, vy, kind, _base=_corridor_resample):
            weld_alt = _static_edge_weld_alt(vx, vy)
            if weld_alt is not None:
                _APPARATUS_HITS["static_edge_weld_vertices"] += 1
                return (weld_alt, True)
            return _base(vx, vy, kind)

        # STRIP-LAW VALUATION (§1 law swap).  The bands the march built
        # under the strip family must be VALUED by that family too — the
        # corridor clamp is what actually writes the law into the surface,
        # so valuing them through this shape's own (e.g. 3 m apron
        # shoulder) envelope would put strip-law FOOTPRINT under
        # apron-law VALUES.  Same resampler construction, same weld
        # precedence; only the envelope and the graded width differ.
        strip_resample_alt = None
        if _strip_bands and _strip_full is not None:
            _strip_env = _strip_full[6]
            _strip_width = _strip_full[2]
            _strip_corridor = _make_edge_projection_resampler(
                coords, ring_alts, _strip_env, _strip_width, sample_dem)

            def strip_resample_alt(vx, vy, kind, _base=_strip_corridor):
                weld_alt = _static_edge_weld_alt(vx, vy)
                if weld_alt is not None:
                    _APPARATUS_HITS["static_edge_weld_vertices"] += 1
                    return (weld_alt, True)
                return _base(vx, vy, kind)

        # ── ABEAM-LONGITUDINAL LAW (§2, ``O4_STRIP_PRECEDENCE``) ────────
        # The lateral corridor bounds a band vertex against the pavement
        # EDGE at its own lateral depth; nothing in that law couples two
        # stations ALONG the runway, so the DEM is free to ride up and down
        # the strip inside the corridor.  ICAO Annex 14 §3.4.13 (and FAA AC
        # 150/5300-13B §3.16.5 item 1) say it may not: the graded strip has
        # a longitudinal cap of its own.  This closure is the
        # generation-binding half — every band piece of a shape whose
        # ground lies in a strip footprint has its emitted values made
        # along-axis Lipschitz by ``grade_law.runway_strip_longitudinal_
        # clamp`` before they are rounded and registered.
        #
        # SCOPE: any family, keyed on the NEAREST runway axis, but only for
        # vertices actually INSIDE the footprint (the ``inside`` mask) —
        # §1 defers most non-runway stations out of the strip, and the
        # residue that clips in is still the strip's ground and takes the
        # strip's law.  WELD vertices are pinned: they carry the runway's
        # own solved profile, which is lawful under the runway's own
        # longitudinal law, and the emitter re-asserts them a few lines
        # later regardless.
        _strip_long = None
        if STRIP_PRECEDENCE_ENABLED and strip_lateral_prep is not None \
                and rw_axes:
            try:
                _cen = s.polygon.centroid
                _near = min(rw_axes, key=lambda a: a[0].distance(_cen))
            except (_GEOM_EXC + (ValueError,)):
                _near = None
            if _near is not None:
                _long_axis = _near[1]
                # PHASE B + §A3(b): the cap is RULESET-KEYED and the
                # strip's own CURVATURE law (ICAO §3.4.14 / FAA §3.16.5
                # item 5) rides the same clamp — one law resolver
                # (``grade_law.strip_longitudinal_law``) for the trigger,
                # the clamp and the validator.
                _long_slope, _long_arc = strip_longitudinal_law(
                    runway_code_number(_near[2]),
                    ruleset=grade_law_ruleset_of(layout))

                def _strip_long(ring, ring_alts_in, weld_flags,
                                _axis=_long_axis, _slope=_long_slope,
                                _arc=_long_arc,
                                _zone=strip_lateral_prep):
                    global _STRIP_LONGITUDINAL_MAX_DELTA_M
                    inside = [_zone.contains(Point(px, py))
                              for px, py in ring]
                    if not any(inside):
                        return ring_alts_in
                    out = runway_strip_longitudinal_clamp(
                        ring, ring_alts_in, _axis, _slope,
                        pinned=weld_flags, inside=inside,
                        arc_rate_per_m=_arc)
                    for _a, _b in zip(ring_alts_in, out):
                        if _a is None or _b is None:
                            continue
                        _d = abs(float(_b) - float(_a))
                        if _d > 1e-3:
                            _APPARATUS_HITS[
                                "strip_longitudinal_clamped_vertices"] += 1
                            if _d > _STRIP_LONGITUDINAL_MAX_DELTA_M:
                                _STRIP_LONGITUDINAL_MAX_DELTA_M = _d
                    return out

        if _ADJACENT_DEBUG and (fill_bands or cut_bands):
            UI.vprint(1, f"  [adjacent-debug] shape role={s.role} "
                         f"ref={s.ref} family={family}: "
                         f"{len(fill_bands)} fill / {len(cut_bands)} cut "
                         f"raw band(s)")
        for qx, qy in (_ADJACENT_DEBUG_POINTS if stations else ()):
            # Lab forensics replay the marched stations; consumed pre-built
            # footprints carry no station arrays, so this scan is skipped
            # gate-ON (the pre-solve construct log covers that path).
            try:
                dq = s.polygon.distance(Point(qx, qy))
            except _GEOM_EXC:
                continue
            if dq > reach + 10.0:
                continue
            nearest = min(range(len(stations)),
                          key=lambda i: (stations[i][0] - qx) ** 2
                          + (stations[i][1] - qy) ** 2)
            sx, sy = stations[nearest]
            fl, ce = envelope_at(max(_PAVEMENT_GAP_M, dq))
            dem_q = sample_dem(qx, qy)
            raw_dist = None
            for band_list in (fill_bands, cut_bands):
                for ring, _ in band_list:
                    try:
                        rd = Polygon(ring).buffer(0).distance(Point(qx, qy))
                    except _GEOM_EXC:
                        continue
                    if raw_dist is None or rd < raw_dist:
                        raw_dist = rd
            # Replicate the builders' outward scan at the nearest station.
            scan = ""
            ref_alt = st_alts[nearest]
            if ref_alt is not None:
                nx_, ny_ = outs[nearest]
                last_fill = last_cut = 0.0
                nst = max(1, int(math.ceil(max(width, reach) / step)))
                for k in range(1, nst + 1):
                    dk = k * step
                    dd = sample_dem(sx + nx_ * dk, sy + ny_ * dk)
                    if dd is None:
                        continue
                    if dk <= width:
                        fd = floor_depth(dk)
                        if fd is not None and dd < ref_alt - fd - trigger:
                            last_fill = dk
                    if dk < reach:
                        co = ceil_off(min(dk, reach - 1e-3))
                        if co is not None and dd > ref_alt + co + trigger:
                            last_cut = dk
                scan = (f" scan(last_fill={last_fill:.0f},"
                        f"last_cut={last_cut:.0f})")
            UI.vprint(1,
                f"  [adjacent-debug-point] q=({qx:.0f},{qy:.0f}) "
                f"shape role={s.role} ref={s.ref} d={dq:.1f} "
                f"nearest_station=({sx:.0f},{sy:.0f}) "
                f"station_ref={st_alts[nearest]} dem={dem_q} "
                f"floor={fl} ceiling={ce} raw_band_dist={raw_dist}"
                f"{scan}")
        _emit_groups = [("fill", fill_bands, resample_alt),
                        ("cut", cut_bands, resample_alt)]
        if _strip_bands and strip_resample_alt is not None:
            _emit_groups += [
                ("fill", [b for k, b in _strip_bands if k == "fill"],
                 strip_resample_alt),
                ("cut", [b for k, b in _strip_bands if k == "cut"],
                 strip_resample_alt)]
        for kind, band_list, _group_resample in _emit_groups:
            # The group's own valuation (the strip-law groups read the
            # strip corridor); the body below calls ``resample_alt``.
            resample_alt = _group_resample
            for ring, _ralts in band_list:
                try:
                    ring = _snap_ring_to_static(ring)
                    poly = Polygon(ring)
                    raw_area = poly.area if poly.is_valid else None
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                        raw_area = poly.area
                    # EXACT clips everywhere (weld ruling 2026-07-09):
                    # shared boundaries keep shared coordinates, and the
                    # guarded adoption below welds agreeing values while
                    # a genuine disagreement emits the deliberate
                    # node-split wall — never a groove of raw DEM.
                    poly = poly.difference(static_union)
                    if (groundside_block is not None
                            and not groundside_block.is_empty):
                        # Buffered, NOT exact: strips never abut
                        # groundside (user ruling 2026-07-09).
                        poly = poly.difference(groundside_block)
                    if (building_block is not None
                            and not building_block.is_empty):
                        # Buffered standoff: a strip never welds onto a
                        # building's pad value (designed split, tear source
                        # — see building_block).
                        poly = poly.difference(building_block)
                    if (tunnel_ramp_block is not None
                            and not tunnel_ramp_block.is_empty):
                        # Buffered standoff (scope B): a strip stands 1 m
                        # off the tunnel mouth ramp/wall rather than welding
                        # onto its steep floor — the building standoff
                        # pattern.  A groove of raw DEM renders harmlessly.
                        poly = poly.difference(tunnel_ramp_block)
                    if (crossing_zone_clip_block is not None
                            and not crossing_zone_clip_block.is_empty):
                        # CROSSING INFLUENCE ZONE (Phase 1): no band piece
                        # may enter a published crossing zone — crossings,
                        # collar rings, and the depressed-road corridor —
                        # bands stay along the taxiway edge and never wrap
                        # a ramp/approach end (user ruling 2026-07-15).
                        # Same buffered-standoff render argument as above.
                        poly = poly.difference(crossing_zone_clip_block)
                    if (collar_zone_clip_block is not None
                            and not collar_zone_clip_block.is_empty):
                        # COLLARED POCKET (arc B1): no band piece may enter
                        # a pocket whose drainage collar rings emitted —
                        # the collar governs that ground and an overlapping
                        # band crashes X-Plane.  EXACT clip, ZERO buffer
                        # (weld ruling 2026-07-09: no standoff grooves) —
                        # unlike the buffered blocks above, this surface
                        # ABUTS the collar's outer ring rather than
                        # standing off it.  This is also the ONLY collar
                        # protection under the frozen-footprint gate state,
                        # where the station march above is not re-run.
                        poly = poly.difference(collar_zone_clip_block)
                    if (enclave_zone_clip_block is not None
                            and not enclave_zone_clip_block.is_empty):
                        # AIRSIDE ENCLAVE (owner 2026-08-07; SCOPING v2).
                        # THE WHOLE of the enclave keep-out is this line:
                        # no band piece may occupy ground inside a
                        # POCKET-width region of the gap law's own union
                        # — that ground is airside-interior and the ring
                        # + spine treats it — and a row that merely
                        # PASSES THROUGH such a region keeps every part
                        # of itself that lies outside it, because a
                        # difference is clipped at the region boundary
                        # by construction.  EXACT clip, ZERO buffer, for
                        # the collar's reason: this surface ABUTS the
                        # enclave's rim (which is pavement it is already
                        # welded to) rather than standing off it.
                        _pre_area = poly.area
                        poly = poly.difference(enclave_zone_clip_block)
                        if poly.area < _pre_area - 1e-9:
                            _APPARATUS_HITS[
                                "enclave_zone_clipped_bands"] += 1
                            _enclave_band_area_taken += (
                                _pre_area - poly.area)
                    if (previous_shapes_union is not None
                            and not previous_shapes_union.is_empty):
                        poly = poly.difference(previous_shapes_union)
                    if (current_shape_union is not None
                            and not current_shape_union.is_empty):
                        # Same-shape exact clip (welded seam).
                        poly = poly.difference(current_shape_union)
                    if boundary is not None and not boundary.is_empty:
                        poly = poly.intersection(boundary)
                    # ROBUST DECONFLICT (2026-07-17): the accumulated
                    # ``previous_shapes_union`` grows into a large multipart
                    # whose ``difference`` intermittently returns the input
                    # UNCHANGED under GEOS overlay robustness failure — the
                    # clip above silently no-ops and the band laps a sibling
                    # (CYXY: 139 m² of #567 over #367, both valid, yet
                    # ``poly.difference(prev_union)`` removed nothing while
                    # differencing the single sibling removed it cleanly).
                    # Re-subtract the individual EARLIER band footprints poly
                    # actually meets (small, robust operands) so no band∩band
                    # overlap survives regardless of the union's robustness.
                    if not poly.is_empty and _prior_band_index:
                        for _pb in _nearby_prior_bands(poly):
                            try:
                                if poly.intersects(_pb):
                                    poly = poly.difference(_pb)
                            except _GEOM_EXC:
                                continue
                            if poly.is_empty:
                                break
                    if not poly.is_empty and _static_poly_index:
                        for _sp in _nearby_static_polys(poly):
                            try:
                                if poly.intersects(_sp):
                                    poly = poly.difference(_sp)
                            except _GEOM_EXC:
                                continue
                            if poly.is_empty:
                                break
                    if poly.is_empty:
                        if _ADJACENT_DEBUG and raw_area:
                            b = Polygon(ring).bounds
                            UI.vprint(1,
                                f"  [adjacent-debug] {kind} band clipped "
                                f"to EMPTY (raw {raw_area:.0f} m2) "
                                f"bbox={b}")
                        continue
                except _GEOM_EXC:
                    continue
                if poly.geom_type == "Polygon":
                    comps = [poly]
                elif poly.geom_type in ("MultiPolygon",
                                        "GeometryCollection"):
                    comps = [g for g in poly.geoms
                             if g.geom_type == "Polygon"]
                else:
                    continue
                comps = [r for c in comps
                         for r in _repair_self_lenses(c)]
                for comp in comps:
                    for simple in _decompose_polygon_with_holes(
                            comp, min_area_m2=1.0):
                        if simple.is_empty:
                            continue
                        # CRESCENT-SLIVER gate (user in-sim report
                        # 2026-07-09, CYXY shapeIDs 447-449): a clip
                        # residue can survive as a ~200 m long ribbon
                        # nowhere wider than a metre or two — it reads
                        # as a spike triangle far outside the visibly
                        # graded area and protects nothing a
                        # neighbouring band does not already cover.
                        # A genuine band slab is at least the 3 m lip
                        # wide somewhere; drop pieces that vanish
                        # under a 0.75 m erosion regardless of area.
                        try:
                            if simple.buffer(-0.75).is_empty:
                                if _ADJACENT_DEBUG:
                                    b = simple.bounds
                                    UI.vprint(1,
                                        f"  [adjacent-debug] dropped "
                                        f"crescent sliver area="
                                        f"{simple.area:.1f} bbox={b}")
                                continue
                        except _GEOM_EXC:
                            pass
                        if simple.area < _MIN_BAND_AREA_M2:
                            # The min-area gate rejects freestanding
                            # confetti — but a small fragment ATTACHED to
                            # existing geometry is a legitimate corner
                            # patch of continuous coverage (the runway-end
                            # skirt's own rule; dropping attached
                            # fragments left validator-visible coverage
                            # notches).  Keep attached; drop isolated.
                            attached = False
                            if simple.area >= 1.0:
                                try:
                                    attached = (simple.distance(
                                        static_union) <= 1.0)
                                except _GEOM_EXC:
                                    attached = False
                            if not attached:
                                if _ADJACENT_DEBUG:
                                    b = simple.bounds
                                    UI.vprint(1,
                                        f"  [adjacent-debug] dropped "
                                        f"isolated fragment area="
                                        f"{simple.area:.1f} bbox={b}")
                                continue
                        piece_ring = _open_coords(simple)
                        if len(piece_ring) < 3:
                            continue
                        # BAND-CORNER WELD (site-2 fix): collapse any
                        # clip-minted seam vertex onto a sibling band's
                        # exact corner (within 1 cm, value-agreeing) so
                        # abutting graded_strip bands share the vertex by
                        # construction instead of emitting a 6 mm
                        # near-parallel twin.  Rebuild ``simple`` from the
                        # snapped ring so the emitted polygon and the
                        # per-vertex value/key computation below agree.
                        # (No prior emitted vertices ⇒ the weld is a
                        # structural no-op; skip the per-vertex resample.)
                        if emitted_vertex_cells:
                            _pre_own = [resample_alt(vx, vy, kind)[0]
                                        for vx, vy in piece_ring]
                            welded_ring = _weld_ring_to_prior_bands(
                                piece_ring, _pre_own)
                        else:
                            welded_ring = piece_ring
                        if welded_ring is not piece_ring \
                                and len(welded_ring) >= 3:
                            try:
                                welded_poly = Polygon(welded_ring)
                                if not welded_poly.is_valid:
                                    welded_poly = welded_poly.buffer(0)
                                if (welded_poly.geom_type == "Polygon"
                                        and not welded_poly.is_empty):
                                    simple = welded_poly
                                    piece_ring = _open_coords(simple)
                                    if len(piece_ring) < 3:
                                        continue
                            except _GEOM_EXC:
                                pass
                        keys = [_vertex_key(vx, vy)
                                for vx, vy in piece_ring]
                        resampled = [resample_alt(vx, vy, kind)
                                     for vx, vy in piece_ring]
                        own = [value for value, _ in resampled]
                        weld = [is_weld for _, is_weld in resampled]
                        # GUARDED adoption (round 2): adopt a previously
                        # registered value at this coordinate only when it
                        # agrees with this band's OWN law value within the
                        # node-merge tolerance — that is exactly the case
                        # that would otherwise mint two coincident nodes /
                        # a zero-angle wedge.  A larger disagreement means
                        # the two bands' corridors genuinely differ here
                        # (different edge references); adopting it tears
                        # THIS band's surface (HECA round-2: a 4.8 m
                        # adopted step), while keeping our own value emits
                        # a deliberate wall of two separate nodes — the
                        # emitter's node-split convention, no wedge.
                        # Unconditional adoption is DONOR-gated (see
                        # ``donor_value_keys``): a non-donor authority
                        # key (service road / building / terminal /
                        # groundside corner) only welds when the values
                        # already agree — otherwise the band keeps its
                        # own lawful value and the step renders as the
                        # designed wall.
                        adopted = [
                            (k in vertex_value_registry
                             and (k in donor_value_keys
                                  or abs(vertex_value_registry[k] - o)
                                  <= VERTEX_ALT_MERGE_TOL_M))
                            for k, o in zip(keys, own)]
                        # Order-2 retirement row: an adoption only
                        # MATTERS when it changes the value (identity
                        # makes own == registry, so gate-ON this count
                        # is expected to fall to zero).
                        _APPARATUS_HITS["value_changing_adoptions"] += \
                            sum(1 for k, a, o in zip(keys, adopted, own)
                                if a and abs(vertex_value_registry[k]
                                             - o) > 1e-6)
                        alts = [vertex_value_registry[k] if a else o
                                for k, a, o in zip(keys, adopted, own)]
                        # Clamp any residual single-vertex resample spike,
                        # then metre-scale SHORT dip runs a foot-flip
                        # mints on notched parent rings (≤2 vertices over
                        # ≤3 m — see _declaw_short_needle_runs).
                        alts = _declaw_alt_needles(
                            alts, tol=_ADJACENT_NEEDLE_TOL_M)
                        # Run threshold = the fill/cut trigger: over ≤3 m
                        # the corridor changes ≲0.15 m lawfully, so a >1 m
                        # short-run reversal is always the foot-flip class.
                        alts = _declaw_short_needle_runs(
                            piece_ring, alts, tol=trigger)
                        # ABEAM-LONGITUDINAL LAW (§2): the along-axis
                        # Lipschitz clamp, applied AFTER the declaw passes
                        # (so it works on the values that will actually be
                        # emitted) and BEFORE the 0.1 m rounding and the
                        # weld/adoption re-assertion (so the pinned
                        # pavement values still win and the registry sees
                        # the lawful number).  ``None`` gate-off — the
                        # statement is then a single name test.
                        if _strip_long is not None:
                            alts = _strip_long(piece_ring, alts, weld)
                        alts = [round(a, 1) for a in alts]
                        # Re-assert adopted AND pavement-weld values
                        # (declaw/rounding must not move a shared-
                        # coordinate agreement or a pavement edge
                        # adoption), then register this piece's values
                        # for later bands.
                        for j, (k, a) in enumerate(zip(keys, adopted)):
                            if a:
                                alts[j] = vertex_value_registry[k]
                            elif weld[j]:
                                alts[j] = own[j]
                                if k not in vertex_value_registry:
                                    vertex_value_registry[k] = own[j]
                            elif k not in vertex_value_registry:
                                vertex_value_registry[k] = alts[j]
                        # TEAR HEAL (2026-07-17): collapse any sub-metre
                        # near-vertical ring edge the clips / band cap left
                        # — a pinch where the inner (pavement weld) row and
                        # the outer (terrain) row come within a metre while
                        # carrying their lawful >1 m step (the DEM-free TEAR
                        # sentinel class; no lateral corridor slope makes
                        # it).  Keep weld vertices (pavement seam), drop the
                        # pinched outer / spike vertex, then rebuild simple.
                        healed_ring, healed_alts = _heal_band_tears(
                            piece_ring, alts, weld,
                            0.2 * CLEARANCE_STATION_STEP_M, 1.0,
                            wall_max=CLEARANCE_STATION_STEP_M)
                        if healed_ring is not piece_ring:
                            if len(healed_ring) < 3:
                                continue
                            try:
                                healed_poly = Polygon(
                                    healed_ring + [healed_ring[0]])
                                if not healed_poly.is_valid:
                                    healed_poly = healed_poly.buffer(0)
                                if (healed_poly.is_empty
                                        or healed_poly.geom_type
                                        != "Polygon"):
                                    continue
                                # RE-DECONFLICT (2026-07-17): dropping a
                                # concave pinch vertex reconnects the
                                # ring across it, and the new closing
                                # edge can swing INTO an earlier band /
                                # static footprint the pre-heal clip had
                                # already deconflicted (measured CYXY:
                                # 0.22 m² band∩band re-minted by the
                                # heal).  Re-subtract the few nearby
                                # operands (robust, per-piece).
                                _redeconflicted = False
                                for _hp in (_nearby_prior_bands(
                                                healed_poly)
                                            + _nearby_static_polys(
                                                healed_poly)):
                                    try:
                                        if healed_poly.intersects(_hp):
                                            healed_poly = \
                                                healed_poly.difference(_hp)
                                            _redeconflicted = True
                                    except _GEOM_EXC:
                                        continue
                                    if healed_poly.is_empty:
                                        break
                                if (healed_poly.is_empty
                                        or healed_poly.area < 1e-6):
                                    continue
                                if healed_poly.geom_type != "Polygon":
                                    _hparts = [g for g in getattr(
                                        healed_poly, "geoms", [])
                                        if g.geom_type == "Polygon"]
                                    if not _hparts:
                                        continue
                                    healed_poly = max(
                                        _hparts, key=lambda g: g.area)
                            except _GEOM_EXC:
                                continue
                            rebuilt = _open_coords(healed_poly)
                            if len(rebuilt) < 3:
                                continue
                            if _redeconflicted:
                                # A difference() can keep the vertex
                                # COUNT while shifting vertices (a
                                # positional ``alts = healed_alts``
                                # copy then misaligns — measured SPJC:
                                # a 34.0 spike onto a 32.9 row = a
                                # fresh 1.1 m in-band tear), and its
                                # minted intersection vertices have no
                                # healed partner at all.  Identity-
                                # gated remap: an unchanged vertex
                                # (within 1 cm) keeps its own healed
                                # value; a minted vertex takes the
                                # band's OWN lawful valuation.
                                _remapped = []
                                for _vx, _vy in rebuilt:
                                    _bestv = None
                                    _bestd = 1e9
                                    for _hi, (_hx, _hy) in enumerate(
                                            healed_ring):
                                        _hd = math.hypot(_hx - _vx,
                                                         _hy - _vy)
                                        if _hd < _bestd:
                                            _bestd = _hd
                                            _bestv = healed_alts[_hi]
                                    if _bestd > 0.01 or _bestv is None:
                                        _bestv = resample_alt(
                                            _vx, _vy, kind)[0]
                                    _remapped.append(
                                        round(float(_bestv), 1))
                                alts = _remapped
                            elif len(rebuilt) == len(healed_ring):
                                alts = healed_alts
                            else:
                                # buffer(0) reshaped the ring — remap by
                                # nearest so alts stay aligned.
                                alts = [round(float(_nearest_alt(
                                    healed_ring, healed_alts, vx, vy)), 1)
                                    for vx, vy in rebuilt]
                            piece_ring = rebuilt
                            simple = healed_poly
                        shape = BuiltShape(
                            polygon=simple, role=ROLE_GRADED_STRIP,
                            ref=_ADJACENT_REF,
                            node_altitudes=alts + [alts[0]])
                        layout.shapes.append(shape)
                        emitted_shapes.append(shape)
                        emitted += 1
                        # Register this band's final vertices + altitudes
                        # so LATER bands weld their clip seams onto this
                        # corner only where the values also agree.
                        _register_emitted_vertices(piece_ring, alts)
                        # Register the footprint for the robust per-piece
                        # deconflict of later bands (see _prior_band_index).
                        _register_prior_band(simple)
                        try:
                            current_shape_union = (
                                simple if current_shape_union is None
                                else unary_union(
                                    [current_shape_union, simple]))
                        except _GEOM_EXC:
                            pass

        # APRON retaining wall (ruling 3): where the DEM at the shoulder
        # OUTER edge sits more than the wall threshold below the shoulder
        # edge altitude, a vertical face replaces graded fill (aprons have
        # no fill mandate beyond the 3 m shoulder — the floor is free).
        if family == "apron":
            wall_clip = current_shape_union
            if previous_shapes_union is not None:
                try:
                    wall_clip = (previous_shapes_union
                                 if wall_clip is None
                                 else unary_union([wall_clip,
                                                   previous_shapes_union]))
                except _GEOM_EXC:
                    pass
            # BUILT-PAVEMENT KEEPOUT for the wall face (owner defect
            # 2026-07-27, HECA wall #1668): the wall SCOPE counts
            # groundside/service pavement as the qualifying neighbour
            # (``_WALL_SCOPE_PAVEMENT_ROLES``), but the CLIP set excluded
            # groundside — so a wall owed at a 4-5 m apron↔groundside
            # step emitted ON TOP of the groundside surface it steps
            # down to (93 % of #1668 inside groundside #1135; 17 of 25
            # HECA verify overlaps were this class).  Scope and clip
            # must agree: the wall face is clipped out of the buffered
            # groundside block the strip path already uses, plus the
            # service pavement footprints.
            _wall_pav_parts = ([groundside_block]
                               if groundside_block is not None
                               and not groundside_block.is_empty else [])
            _svc_polys = [s.polygon for s in layout.shapes
                          if s.role in ("service_road", "service_junction")
                          and s.polygon is not None
                          and not s.polygon.is_empty]
            if _svc_polys:
                try:
                    _wall_pav_parts.append(
                        unary_union(_svc_polys).buffer(1.0))
                except _GEOM_EXC:
                    pass
            try:
                _wall_pav_block = (unary_union(_wall_pav_parts)
                                   if _wall_pav_parts else None)
            except _GEOM_EXC:
                _wall_pav_block = None
            n_wall, wall_union = _emit_apron_walls(
                layout, stations, st_alts, outs, ceil_off, step,
                sample_dem, static_union, boundary, wall_clip,
                emitted_shapes,
                # APRON WALL SCOPE (owner ruling 2026-07-25): a wall only
                # where another built pavement stands within
                # ``APRON_WALL_PAVEMENT_ADJACENCY_M``.
                station_filter=_apron_q,
                pavement_block=_wall_pav_block,
                strip_keepout=_strip_keepout,
                # AIRSIDE ENCLAVE (SCOPING v2): the band clip's twin on
                # the wall face.  With the station stand-down retired,
                # this is what keeps a retaining wall out of a pocket the
                # ruled ring + spine owns — the owner's "a retaining wall
                # or groundside terrace there is a defect regardless of
                # which mechanism minted it" — while a run that only
                # STRADDLES the region keeps its outside part.
                enclave_keepout=enclave_zone_clip_block,
                enclave_area_taken=_enclave_area_sink)
            emitted += n_wall
            if n_wall and wall_union is not None:
                current_shape_union = wall_union

        # Fold this shape's pieces into the cross-shape union (groove
        # clip for every LATER shape).
        if current_shape_union is not None:
            try:
                previous_shapes_union = (
                    current_shape_union if previous_shapes_union is None
                    else unary_union([previous_shapes_union,
                                      current_shape_union]))
            except _GEOM_EXC:
                pass

    # TRIANGLE DIET (round 2): 3D-collinear decimation over the emitted
    # group.  The pipeline's layout-wide ``decimate_emit_nodes`` ran BEFORE
    # this emitter, so the bands' 5 m-stationed rows would otherwise reach
    # the triangulator undecimated (KCLT gate-on tripled the input nodes).
    # Post-clamp the band surface is piecewise-linear wherever the DEM is
    # outside the corridor, so straight lawful runs collapse to their zone
    # breakpoints.  Group-scoped: bands keep a 1 m standoff from all
    # earlier geometry, so their vertices are shared only among themselves
    # (the vote discipline then guarantees no T-vertex is minted).
    # Boundary-class Z tolerance (±0.1 m): band values carry smoothed-DEM
    # jitter, the same noise family as the boundary ribbon.
    if emitted_shapes:
        # WELD PROTECTION (2026-07-09): a band vertex ON a non-band
        # shape's boundary traces that constrained edge exactly —
        # chord-cutting it diverges the chains and Ruppert-explodes the
        # tile (see decimate_shape_group).  Keeping it is triangle-free.
        from shapely.geometry import box as _box
        from shapely.strtree import STRtree as _STRtree
        _emitted_ids = {id(es) for es in emitted_shapes}
        _static_exteriors = [s.polygon.exterior for s in layout.shapes
                             if s.polygon is not None
                             and not s.polygon.is_empty
                             and s.polygon.geom_type == "Polygon"
                             and id(s) not in _emitted_ids]
        _ext_tree = None
        try:
            _ext_tree = _STRtree(_static_exteriors)
        except _GEOM_EXC:
            _ext_tree = None

        def _on_foreign_boundary(x, y):
            if _ext_tree is None:
                return False
            p = Point(x, y)
            try:
                cand = _ext_tree.query(
                    _box(x - 0.06, y - 0.06, x + 0.06, y + 0.06))
            except _GEOM_EXC:
                return False
            for gi in cand:
                try:
                    if _static_exteriors[gi].distance(p) <= 0.05:
                        return True
                except _GEOM_EXC:
                    continue
            return False

        # FINAL TEAR HEAL (reach-band reconciliation, 2026-07-18): collapse
        # any sub-metre near-vertical pinch the per-piece heal could not see
        # because a later geometry op (this piece's re-deconflict, a
        # neighbour band's clip) minted it — the class a tighter, correct
        # reach ceiling exposes at an apron/junction it clamps down.  Runs
        # before decimation so the healed rings decimate cleanly.
        # UNCONDITIONAL since 2026-07-29: it used to be scoped to the
        # ``O4_RASTER_REACH_BAND`` gate, and that gate is gone with the
        # legacy band engines (one engine needs no selector).
        # (The cross-strip SEAM-STEP blend runs at PIPELINE level, after
        # every strip emitter — this group is only one strip family, and
        # the tearing seams are precisely the cross-family ones.)
        _n_final_heal = _heal_emitted_band_tears(emitted_shapes, layout)
        if _n_final_heal:
            UI.vprint(1, f"  [adjacent-ground] final tear heal: collapsed "
                         f"pinch edge(s) in {_n_final_heal} strip(s).")
        removed = decimate_shape_group(
            emitted_shapes, Z_TOL_BOUNDARY_M,
            protect_predicate=_on_foreign_boundary)
        if removed:
            UI.vprint(1, f"  [pav-builder] adjacent-ground: decimated "
                         f"{removed} 3D-collinear band vertex(es) "
                         f"(±{Z_TOL_BOUNDARY_M} m).")

    if _n_prolonged:
        UI.vprint(1, f"  [adjacent-ground] tile-seam prolongation: "
                     f"{_n_prolonged} cut-back run(s) marched off the "
                     f"un-cut frontage (owner ruling 2026-07-24).")
    # AIRSIDE-ENCLAVE keep-out ledger (SCOPING v2).  The area the
    # keep-out OWNS beside the area it actually TOOK, in one line and in
    # one frame: an overreach is then visible as a number here rather
    # than only in a downstream void census.  A take larger than the
    # keep-out's own area is arithmetically impossible under a
    # difference — which is the whole point of moving the law onto the
    # geometry.
    if enclave_zone_clip_block is not None:
        UI.vprint(1,
            f"  [adjacent-ground] airside-enclave keep-out: took "
            f"{_enclave_band_area_taken:.0f} m2 of band and "
            f"{_enclave_area_sink[0]:.0f} m2 of wall face out of a "
            f"{enclave_zone_clip_block.area:.0f} m2 pocket-region "
            f"keep-out [frame=gap-law pavement-only union, settled].")
    # Order-2 apparatus hit report (always printed — the OFF-vs-ON
    # retirement table reads these from both configurations).
    UI.vprint(1, "  [adjacent-ground] apparatus hits: "
                 + " ".join(f"{k}={_APPARATUS_HITS[k]}"
                            for k in _APPARATUS_KEYS))
    # ── INGESTION RESIDUALS — both of these are pre-registered ZEROS ──
    # once the solve consumes ``layout.adjacent_ground_zone_boxes``.
    # They are reported LOUDLY rather than absorbed, because each names
    # a place where the emitted band value is NOT the solved value —
    # which is exactly what the single-solve architecture forbids
    # (EMITTERS EMIT, NEVER GRADE).
    if _APPARATUS_HITS["band_corridor_clamped_vertices"]:
        UI.vprint(1, f"  [adjacent-ground] INGESTION RESIDUAL — corridor "
                     f"box read at emit: "
                     f"{_APPARATUS_HITS['band_corridor_clamped_vertices']} "
                     f"solved band vertex(es) still outside their own law "
                     f"box (worst {_BAND_CLAMP_MAX_DELTA_M:.2f} m).  "
                     f"MEASURED AGAINST A THIRD DATUM — the pavement value "
                     f"at EMIT, after both final_grade_projection passes "
                     f"have moved it again — so this is a valid ALARM but "
                     f"its magnitude mixes the solve's residual with "
                     f"post-solve pavement motion; split per vertex before "
                     f"attributing it.  (The old claim that it 'goes to 0 "
                     f"when the solve binds the supplied boxes' is "
                     f"FALSIFIED: the boxes were bound, per sweep, harder "
                     f"than the relative law — that is what produced the "
                     f"residual.  Cycle-5 fix 1 deleted them.)")
    if _APPARATUS_HITS["solved_analytic_fallback"]:
        UI.vprint(0, f"  [adjacent-ground] INGESTION RESIDUAL — "
                     f"COMPLETENESS: "
                     f"{_APPARATUS_HITS['solved_analytic_fallback']} "
                     f"emitted band vertex(es) had NO solved row in range "
                     f"and were valued analytically.  Every emitted value "
                     f"must be a solved value; these name the band nodes "
                     f"the pre-solve construct did not cover.")
    return emitted


def _emit_apron_walls(layout, stations, st_alts, outs, ceil_off, step,
                      sample_dem, static_union, boundary,
                      emitted_union=None, emitted_shapes=None,
                      station_filter=None, pavement_block=None,
                      strip_keepout=None, enclave_keepout=None,
                      enclave_area_taken=None):
    """Emit ``retaining_wall`` faces along an apron edge where the DEM
    drops more than ``APRON_EDGE_WALL_MIN_DROP_M`` below the shoulder
    outer-edge altitude (reuses the ``ROLE_RETAINING_WALL`` emit contract
    — a thin vertical band, top row at the shoulder edge, bottom row at
    the DEM).  Grouped into runs of consecutive dropped stations.

    RETIRED UNDER W2 (flag ``O4_FABRIC_W2_RETIRE_APRON_EDGE_WALLS``, default
    ON).  Reg-set §5.1 T4 + RULINGS 2026-08-08 reg-set ruling 4: this
    family is pure design — the 2026-07-25 scoping ruling already
    narrowed it because "no code mandates grading beyond an apron edge",
    and the fabric model's standing walls-to-carves ruling leaves walls
    only at CARVE STRUCTURES.  Under the drape the raw DEM meets the
    apron edge and Triangle blends it, which is the owner's whole
    two-squares thought experiment.  Set the flag to 0 for the pre-W2
    behaviour.

    APRON WALL CONTINUITY (``O4_APRON_WALL_CONTINUITY``, 2026-07-25; full
    diagnosis in the config block ``APRON_WALL_CONTINUITY_ENABLED``) adds
    two things the owner's "ramps and sharp drops" report traced to:

      * MULTIPART-SAFE emission.  The clip against static pavement, the
        just-emitted graded strips and the boundary can split ONE wall run
        into several pieces — a neighbouring junction band nicking 5.29 m²
        out of a 173 m frontage was enough.  The pre-fix code emitted only
        a single ``Polygon`` residue and dropped every other run WHOLE
        (SPJC: 4 runs / 240.4 m² of owed wall face).  The residue is now
        decomposed exactly the way the graded-band emitter decomposes its
        own (``_repair_self_lenses`` → ``_decompose_polygon_with_holes``)
        and every surviving part is emitted; ``_nearest_alt`` values each
        part against the run's own top/bottom rows unchanged.  Parts below
        ``APRON_WALL_MIN_RUN_M`` / ``APRON_WALL_MIN_AREA_M2`` are confetti
        and are skipped and COUNTED (never silently capped).
      * RUN HYSTERESIS.  A run STARTS only above the full
        ``APRON_EDGE_WALL_MIN_DROP_M``, but CONTINUES through stations down
        to ``… - APRON_WALL_RUN_HYSTERESIS_M`` — stations millimetres under
        the threshold (SPJC: 1.4988 m, 1.4936 m) no longer chop a
        continuous frontage into pieces with a bare notch between.

    Gate OFF ⇒ ``join`` collapses onto ``start`` and the single-Polygon
    emission returns, i.e. byte-identical to the pre-fix emitter.

    ``station_filter`` (APRON WALL SCOPE, owner ruling 2026-07-25 —
    ``apron_wall_frontage_qualifier``, gated by ``O4_APRON_WALL_SCOPE``):
    ``qualifies(sx, sy) -> bool``.  A wall is emitted ONLY at stations with
    another built pavement shape within
    ``APRON_WALL_PAVEMENT_ADJACENCY_M`` — between two built surfaces there
    is no room to grade, so a vertical face is the only lawful answer.
    Frontage facing OPEN TERRAIN takes no wall at all (and, in the march
    above, no fill band either): the raw DEM grades up to the apron edge.
    ``None`` (gate off): every station is eligible, as before.

    ``strip_keepout`` (RUNWAY-STRIP WALL LAW, owner ruling 2026-08-01 —
    ``runway_strip_wall_keepout``, gated by ``O4_RUNWAY_STRIP_WALL_LAW``):
    ground on which a retaining face is INADMISSIBLE.  Differenced out of
    each wall run exactly like the ramp-mouth and groundside keep-outs
    above it, so a run straddling the strip edge keeps its lawful outside
    part and loses only the part inside the strip.  ``None`` (gate off):
    nothing is differenced — byte-identical.

    ``enclave_keepout`` (AIRSIDE ENCLAVE, owner 2026-08-07; SCOPING v2 of
    ``docs/specs/enclave-region-law-spec.md``): the POCKET-width regions
    of the gap law's own union — ground the ruled gap interior ring +
    spine treats, where "a retaining wall or groundside terrace is a
    defect regardless of which mechanism minted it".  Differenced out of
    each wall run exactly like ``strip_keepout``, and for the same
    reason a straddling run keeps its outside part: the keep-out is a
    statement about GROUND, so it is applied to geometry and clipped at
    the region boundary — never to the stations, which anchor rows
    reaching far outside it.  ``enclave_area_taken``, when given, is a
    one-slot list the removed area accumulates into (the emitter's
    apparatus row).  ``None``: nothing is differenced — byte-identical.
    """
    # ── T4 RETIRES (W2 ``O4_FABRIC_W2_RETIRE_APRON_EDGE_WALLS``, default ON) ──
    # Refused HERE rather than at the one call site so a retired family
    # cannot be re-opened by a second caller; the return is the
    # emitter's own "nothing emitted" pair, so caller arithmetic is
    # unchanged.
    from .fabric_flags import on as _w2_wall_on
    if _w2_wall_on("O4_FABRIC_W2_RETIRE_APRON_EDGE_WALLS"):
        return 0, None
    w = APRON_SHOULDER_WIDTH_M
    n = len(stations)
    top_alt: list = [None] * n
    dem_alt: list = [None] * n
    dropped = [False] * n
    joinable = [False] * n
    # Hysteresis floor: the drop at which an ALREADY-OPEN run continues.
    # Equal to the start threshold with the gate off, so ``joinable`` is
    # then ``dropped`` and the grouping below is unchanged.
    join_drop = (APRON_EDGE_WALL_MIN_DROP_M - APRON_WALL_RUN_HYSTERESIS_M
                 if _APRON_WALL_CONTINUITY else APRON_EDGE_WALL_MIN_DROP_M)
    n_out_of_scope = 0
    for i, (sx, sy) in enumerate(stations):
        ref = st_alts[i]
        if ref is None:
            continue
        # APRON WALL SCOPE: open-terrain frontage takes no wall.
        if station_filter is not None and not station_filter(sx, sy):
            n_out_of_scope += 1
            continue
        nx, ny = outs[i]
        ox, oy = sx + nx * w, sy + ny * w
        shoulder_edge = ref + ceil_off(w)
        dd = sample_dem(ox, oy)
        if dd is None:
            continue
        drop = shoulder_edge - float(dd)
        if drop > join_drop:
            # Rows are prepared for every JOINABLE station; only a
            # ``dropped`` one may START a run.
            joinable[i] = True
            dropped[i] = drop > APRON_EDGE_WALL_MIN_DROP_M
            top_alt[i] = shoulder_edge
            dem_alt[i] = float(dd)
    if n_out_of_scope:
        UI.vprint(1, f"  [adjacent-ground] apron wall scope: "
                     f"{n_out_of_scope} open-terrain station(s) skipped "
                     f"(no pavement within "
                     f"{APRON_WALL_PAVEMENT_ADJACENCY_M:g} m — owner "
                     f"ruling 2026-07-25).")
    if not any(dropped):
        return 0, emitted_union
    idx = [i for i in range(n) if joinable[i]]
    runs: list[list[int]] = []
    cur = [idx[0]] if dropped[idx[0]] else []
    for j in idx[1:]:
        # Physical-distance bridge (see _build_cut_bands): an index
        # bridge on long ring edges mints spike walls.
        jx, jy = stations[j]
        contiguous = False
        if cur:
            cx_, cy_ = stations[cur[-1]]
            contiguous = (j - cur[-1] <= 2
                          and math.hypot(jx - cx_, jy - cy_) <= 2.5 * step)
        if cur and contiguous:
            # An open run absorbs its neighbour at the RELAXED threshold.
            cur.append(j)
        elif dropped[j]:
            # A fresh run may only be STARTED by a full-threshold station.
            if cur:
                runs.append(cur)
            cur = [j]
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    # RAMP-MOUTH KEEPOUT (owner ruling 2026-07-26): an implied tunnel
    # under an APRON pierces the apron edge with its ramp corridor — a
    # wall built across the mouth would seal the tunnel (tunnel ramps
    # are not pavement, so the adjacency scope alone cannot see them).
    # Walls never cover ground a tunnel ramp owns.
    try:
        _ramp_block = unary_union(
            [s.polygon.buffer(1.0) for s in layout.shapes
             if s.role == ROLE_TUNNEL_RAMP
             and s.polygon is not None and not s.polygon.is_empty])
        if _ramp_block.is_empty:
            _ramp_block = None
    except _GEOM_EXC:
        _ramp_block = None
    emitted = 0
    n_confetti = 0
    n_multipart_parts = 0
    n_strip_clipped = 0
    n_enclave_clipped = 0
    for run in runs:
        if len(run) < 2:
            continue
        top_pts, top_alts = [], []
        bot_pts, bot_alts = [], []
        for i in run:
            sx, sy = stations[i]
            nx, ny = outs[i]
            ox, oy = sx + nx * w, sy + ny * w
            top_pts.append((ox, oy))
            top_alts.append(round(float(top_alt[i]), 1))
            # Bottom row a hair further out so the face has extent.
            bx, by = sx + nx * (w + _PAVEMENT_GAP_M), sy + ny * (w + _PAVEMENT_GAP_M)
            bot_pts.append((bx, by))
            bot_alts.append(round(float(dem_alt[i]), 1))
        ring = top_pts + bot_pts[::-1]
        alts = top_alts + bot_alts[::-1]
        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if static_union is not None and not static_union.is_empty:
                poly = poly.difference(static_union)
            if _ramp_block is not None:
                poly = poly.difference(_ramp_block)
            # RUNWAY-STRIP WALL LAW (owner 2026-08-01): a retaining face
            # is inadmissible inside a runway's strip footprint — the
            # runway surround grades away smoothly instead.
            if strip_keepout is not None and not strip_keepout.is_empty:
                if poly.intersects(strip_keepout):
                    poly = poly.difference(strip_keepout)
                    n_strip_clipped += 1
            # AIRSIDE-ENCLAVE KEEP-OUT (owner 2026-08-07): the ruled ring
            # + spine owns this ground, so no retaining face stands on
            # it.  Same exact-clip form as the strip keep-out above.
            if enclave_keepout is not None and not enclave_keepout.is_empty:
                if poly.intersects(enclave_keepout):
                    _pre = poly.area
                    poly = poly.difference(enclave_keepout)
                    if poly.area < _pre - 1e-9:
                        n_enclave_clipped += 1
                        if enclave_area_taken is not None:
                            enclave_area_taken[0] += _pre - poly.area
            if (pavement_block is not None
                    and not pavement_block.is_empty):
                # Groundside/service keepout (owner defect 2026-07-27,
                # HECA #1668) — see the call site: the wall steps DOWN
                # TO that pavement; it must never cover it.
                poly = poly.difference(pavement_block)
            # Clip the wall out of the just-emitted graded strips'
            # footprint EXACTLY (weld ruling 2026-07-09): a shared
            # boundary welds at shared coordinates; a standoff would
            # leave a groove of raw DEM at the shoulder edge.
            if emitted_union is not None and not emitted_union.is_empty:
                poly = poly.difference(emitted_union)
            if boundary is not None and not boundary.is_empty:
                poly = poly.intersection(boundary)
            if poly.is_empty:
                continue
            if not _APRON_WALL_CONTINUITY:
                if poly.geom_type != "Polygon":
                    continue
                parts = [poly]
            else:
                # MULTIPART-SAFE decomposition — the band emitter's own
                # idiom (see the ``comps`` block in the graded-strip
                # loop): every lobe of the clip residue is a real piece
                # of the owed wall face, not a reason to drop the run.
                if poly.geom_type == "Polygon":
                    comps = [poly]
                elif poly.geom_type in ("MultiPolygon",
                                        "GeometryCollection"):
                    comps = [g for g in poly.geoms
                             if g.geom_type == "Polygon"]
                else:
                    continue
                comps = [r for c in comps for r in _repair_self_lenses(c)]
                parts = [simple for c in comps
                         for simple in _decompose_polygon_with_holes(
                             c, min_area_m2=1.0)
                         if not simple.is_empty]
                if len(parts) > 1:
                    n_multipart_parts += len(parts)
        except _GEOM_EXC:
            continue
        for part in parts:
            if _APRON_WALL_CONTINUITY:
                # CONFETTI GATE: a face too short along the frontage, or
                # too small, protects nothing a neighbouring band does not
                # already cover and reads in-sim as a spike triangle.
                if (_wall_part_run_length(part) < APRON_WALL_MIN_RUN_M
                        or part.area < APRON_WALL_MIN_AREA_M2):
                    n_confetti += 1
                    continue
            pr = _open_coords(part)
            if len(pr) < 3:
                continue
            # ROW-AWARE clip-vertex valuation (owner defect 2026-07-26,
            # KCLT wall #1070 → strip #1046 tear): the wall face is
            # ``_PAVEMENT_GAP_M`` (1 m) thin, so a plain nearest-vertex
            # read across the merged ring let a TOP-row clip vertex
            # adopt the BOTTOM row's DEM value whenever the run-end
            # geometry put a bottom vertex closer than the next top
            # station (measured 210.3 claimed at a 215.3 top corner;
            # the soft consensus mean then dragged the shared strip
            # node to 211.98 — a 3.4 m mid-air tear).  Project onto
            # each ROW's polyline, take the nearer row, interpolate
            # ALONG it.
            walts = [round(float(_wall_row_alt(
                top_pts, top_alts, bot_pts, bot_alts, ring, alts,
                vx, vy)), 1) for vx, vy in pr]
            wall_shape = BuiltShape(
                polygon=part, role=ROLE_RETAINING_WALL,
                ref=_ADJACENT_WALL_REF,
                node_altitudes=walts + [walts[0]])
            layout.shapes.append(wall_shape)
            if emitted_shapes is not None:
                emitted_shapes.append(wall_shape)
            emitted += 1
            try:
                emitted_union = (
                    part if emitted_union is None
                    else unary_union([emitted_union, part]))
            except _GEOM_EXC:
                pass
    if n_multipart_parts or n_confetti:
        UI.vprint(1, f"  [adjacent-ground] apron walls: "
                     f"{n_multipart_parts} part(s) from multipart clip "
                     f"residue kept, {n_confetti} sub-minimum part(s) "
                     f"skipped (<{APRON_WALL_MIN_RUN_M:g} m run / "
                     f"<{APRON_WALL_MIN_AREA_M2:g} m2).")
    if n_strip_clipped:
        UI.vprint(1, f"  [adjacent-ground] runway-strip wall law: "
                     f"{n_strip_clipped} apron wall run(s) clipped out of a "
                     f"runway strip footprint (owner ruling 2026-08-01).")
    if n_enclave_clipped:
        _APPARATUS_HITS["enclave_zone_clipped_walls"] += n_enclave_clipped
        UI.vprint(1, f"  [adjacent-ground] airside-enclave wall law: "
                     f"{n_enclave_clipped} apron wall run(s) clipped out "
                     f"of a pocket-width enclave the gap ring + spine "
                     f"owns (owner ruling 2026-08-07).")
    return emitted, emitted_union


def _wall_row_alt(top_pts, top_alts, bot_pts, bot_alts, ring, alts,
                  vx, vy):
    """Row-aware altitude for one apron-wall clip vertex — see the call
    site in ``_emit_apron_walls``.  Falls back to the legacy merged-ring
    nearest-vertex read when the rows are degenerate."""
    best_d = None
    best_v = None
    p = Point(vx, vy)
    for pts, alts_row in ((top_pts, top_alts), (bot_pts, bot_alts)):
        if len(pts) < 2 or len(alts_row) != len(pts):
            continue
        try:
            ls = LineString(pts)
            d = ls.distance(p)
            s = ls.project(p)
        except _GEOM_EXC:
            continue
        if best_d is not None and d >= best_d:
            continue
        acc = 0.0
        val = alts_row[-1]
        for k in range(len(pts) - 1):
            seg = math.hypot(pts[k + 1][0] - pts[k][0],
                             pts[k + 1][1] - pts[k][1])
            if s <= acc + seg or k == len(pts) - 2:
                f = (0.0 if seg <= 1e-9
                     else max(0.0, min(1.0, (s - acc) / seg)))
                val = alts_row[k] + f * (alts_row[k + 1] - alts_row[k])
                break
            acc += seg
        best_d, best_v = d, val
    if best_v is None:
        return _nearest_alt(ring, alts, vx, vy)
    return best_v


def _wall_part_run_length(poly):
    """Along-frontage LENGTH (m) of one emitted apron-wall part.

    A wall face is a thin strip — its top row sits at the shoulder edge
    and its bottom row one ``_PAVEMENT_GAP_M`` further out — so the LONG
    side of the part's minimum rotated rectangle is the frontage run it
    actually covers.  Used by the confetti gate; ``0.0`` for anything
    shapely cannot rectangle (which the gate then rejects)."""
    import warnings
    try:
        with warnings.catch_warnings():
            # GEOS' oriented_envelope raises a spurious "divide by zero"
            # RuntimeWarning on a PERFECT rectangle — which an unclipped
            # wall face always is.  Suppressed here rather than left to
            # spam every build log; the returned rectangle is correct.
            warnings.simplefilter("ignore", RuntimeWarning)
            mrr = poly.minimum_rotated_rectangle
        ext = getattr(mrr, "exterior", None)
        if ext is None:
            return 0.0
        xs = list(ext.coords)[:-1]
        if len(xs) < 3:
            return 0.0
        return max(math.hypot(xs[(k + 1) % len(xs)][0] - xs[k][0],
                              xs[(k + 1) % len(xs)][1] - xs[k][1])
                   for k in range(len(xs)))
    except (_GEOM_EXC + (AttributeError, ValueError)):
        return 0.0
