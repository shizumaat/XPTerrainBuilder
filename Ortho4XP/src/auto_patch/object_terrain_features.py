"""Recognize tunnel and taxiway-bridge structures from placed OBJ8 geometry.

Workstream W-R3 of ``docs/object_terrain_features_spec.md`` (section 3.1).
This is the shared, PURE classifier that feeds the two gated terrain
features: feature A (tunnel cutouts, W-T) and feature B (bridge
adaptation, W-B).  Geometry and placements in, records out — no file
discovery, no ``DSFTool`` invocation, no mesh sampling.  Callers hand it
already-read placements (``obj8_reader.read_dsf_object_placements``) and
already-loaded geometry (``obj8_reader.load_object_file``).

The physics the recognizers rest on
-----------------------------------
X-Plane places each object rigidly at ``terrain(anchor) + offset``, where
``offset`` is 0 for a plain ``OBJECT``, the signed above-ground metres for
``OBJECT_AGL`` and (absolute, handled separately) for ``OBJECT_MSL``.  A
structure's parts share (very nearly) one anchor terrain, so the classifier
reasons about height in an anchor-independent **effective height**::

    effective_y = placement.above_ground_level_metres + authored_local_y

which drops the unknown, shared ``terrain(anchor)`` constant.  The plane
``effective_y = 0`` is grade.  This is what lets a below-grade tunnel
authored 0..+7 and placed at ``OBJECT_AGL -7`` (EGLL tunnels 6/7/10) be
read on the same footing as a plain tunnel authored 0..-5 and placed at 0:
both have their roof slab at ``effective_y ≈ 0`` and their deck well below
it (spec section 2.1).

The world frame
---------------
All polygons and lines in the emitted records live in ONE per-structure
metre frame, following ``object_anchor``'s convention: an unrotated
east-north-up frame whose origin is the mean of the structure's placement
longitudes/latitudes (a synthetic heading-0 placement at that origin).
Shapely coordinates are ``(x, z)`` = ``(metres east, metres south)`` — so
polygon ``.area`` is already in square metres — and the vertical axis is
``effective_y``.  Convert a frame polygon back to longitude/latitude with
:func:`frame_polygon_to_longitude_latitude` (or a point with
``obj8_reader.local_offset_to_lonlat(origin_latitude, origin_longitude,
0.0, x, z)``).  Every record carries ``frame_origin_longitude_latitude``
so downstream code can make that conversion; this field is additive to the
spec's record sketch, which lists the geometry without saying how to place
it in the world — it cannot be omitted without making the polygons
unusable.

Up-facing, and why winding is not trusted
-----------------------------------------
The EGLL investigation found triangle-winding normals unreliable — flipped
in the deck objects — so the probe code classified faces with the STORED
vertex normals.  ``ObjectGeometry`` (frozen contract) does not carry stored
normals, and the supervisor-granted loader extension was for hardness only,
not normals.  The classifier therefore uses the one face signal that is
INDEPENDENT of winding sign: near-horizontality, ``|n_y| / |n| ≥
NEAR_HORIZONTAL_NORMAL_Y_MIN``.  A winding flip negates every normal
component, leaving that ratio unchanged.  Roof, deck and ceiling are then
separated by their effective height, which needs no normal sign — a roof
slab and its ceiling underside share a footprint, so the covered roof
footprint (roof ∩ deck) and the open mouths (deck − roof) come out right
regardless of which way any single face is wound.

Grouping
--------
A tunnel's shell and deck arrive as separate resources sharing one anchor
area (EGLL ``N.obj`` / ``Na.obj``); a KBNA bridge is six parts on one
shared anchor.  Grouping reuses ``object_anchor.discover_object_pools`` —
the existing world-footprint overlap primitive — so no new gap heuristic is
invented (spec pre-reading, ``docs/obj8_structure_partition.md``).  Parts of
one bridge or tunnel share a footprint and overlap by many metres; distinct
structures are hundreds of metres apart, so the small expansion epsilon is
not sensitive.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field, replace as _replace_dataclass
from statistics import median
from typing import Iterable, NamedTuple, Sequence

import numpy
import shapely
from shapely import affinity as shapely_affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from . import obj8_reader
from .geom_safe import min_rotated_rect
from .object_anchor import discover_object_pools
from .obj8_reader import ObjectGeometry, ObjectPlacement

# Exceptions the shapely combinators here may legitimately raise on
# degenerate input (shapely-domain only — never built-ins, which would
# mask a real bug; the project-standard guard, see object_footprints).
try:  # shapely 2
    from shapely.errors import GEOSException as _GEOS_EXCEPTION
except ImportError:  # pragma: no cover - shapely 1 fallback
    from shapely.errors import TopologicalError as _GEOS_EXCEPTION


# ---------------------------------------------------------------------------
# Detection thresholds (spec section 3.1) — named constants, no magic
# numbers at the call sites (pattern: LEVEL_DRAPED_MAX_ABS in
# dsf_road_network.py).
# ---------------------------------------------------------------------------

# A tunnel body's deck sits at least this far below grade (metres).
TUNNEL_MIN_BODY_DEPTH_M = 2.0

# A tunnel is a structure with at least this much near-horizontal DRIVABLE
# (hard) deck area below grade — the discriminator against both bridges
# with deep piers (below-grade geometry vertical, not horizontal) and
# buried building BASEMENTS.  The EGLL below-grade-versus-author-mesh
# correlation (2026-07-09) is decisive: 100% of below-grade building
# pieces at EGLL are buried by the author's own mesh (deepest: T2_T3_3 at
# −9.22 m) and NONE of the 30 below-grade buildings carries ANY below-grade
# hard area, while 17/20 tunnel objects carry hard_deck with large
# below-grade deck areas (tunnel 2a: 17,046 m²).  Depth alone is exactly
# INVERTED as a signal — the deepest objects are basements; exposed tunnels
# run only −4…−5 m.  The at-grade hard-deck road object (T2_3/ROADT23) is
# excluded by the below-grade requirement, not by hardness.
TUNNEL_MIN_BELOW_GRADE_DECK_AREA_M2 = 200.0

# ── Round-5 feature-A ADMISSION guard 2 (VHHH, owner in-sim on 1.0.230:
# an island-wide trench in the water and −21.38 m canyons through the
# taxiways) ──────────────────────────────────────────────────────────
#
# A TUNNEL IS NOT AN ISLAND.  ``TUNNEL_MIN_BELOW_GRADE_DECK_AREA_M2``
# above is the minimum; this is the maximum that was missing.  A record
# whose deck footprint exceeds this is refused — generous for any real
# cut-and-cover complex, and three orders of magnitude under the thing
# it exists to stop.  Measured on the VHHH pack (2026-08-10, from the
# pack classification sidecar): the five REAL road tunnels carry deck
# footprints of 3,845 / 6,991 / 8,893 / 9,102 / 27,807 m², while the
# ``tunnel/sea.obj`` + ``sea_X.obj`` sea-bed record carries 21,495,901 m²
# — 770x the largest real record — and its trench claimed all unowned
# ground on the island.
TUNNEL_MAX_DECK_FOOTPRINT_AREA_M2 = float(
    os.environ.get("O4_TUNNEL_MAX_DECK_FOOTPRINT_AREA_M2", "150000.0")
)

# The reason guard 2 records on the :class:`RefusedStructure` audit
# trail.  Guard 1 leaves no record: it refuses a RESOURCE before any
# candidate structure exists to attach a reason to, and announces itself
# at verbosity 1 instead.
TUNNEL_REFUSAL_ISLAND_DECK = "tunnel_deck_footprint_island_scale"

# A negative OBJECT_AGL placement offset of at least this magnitude flags a
# below-grade structure on its own — the three EGLL AGL tunnel shells
# (6/7/10) carry no hard triangles at all, and tunnel 10 sits at exactly
# −1.0 m, so the threshold is 1.0, not the body-depth 2.0.
TUNNEL_MIN_BELOW_GRADE_AGL_OFFSET_M = 1.0

# The AGL limb recognizes SHELLS — structures living essentially below the
# effective grade plane.  A building merely SEATED below grade (a negative
# offset to sink its foundation into a slope) stands tall above it, so the
# limb refuses any resource whose solid faces reach higher than this above
# effective grade.  Measured 2026-07-18 (tile +51-001): the EGKR Redhill
# control tower ``lib/airport/control_towers/small/16m_Norway.obj``, placed
# at OBJECT_AGL −4.0 by Global Airports, carried 138.7 m² of below-grade
# deck area and classified as a tunnel — its highest face sits at +15.19 m
# effective.  The three true EGLL AGL shells top out at −1.69 (Tunnel/6),
# −0.66 (Tunnel/7) and +0.84 m (Tunnel/10); 2.0 keeps better than a metre
# of margin over the tallest true shell and rejects every measured
# building.  Note an above-grade AREA test cannot do this job: Tunnel/10
# carries MORE near-horizontal area above grade (128.7 m²) than below
# (55.1 m²) — height, not area, is the discriminator.
TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M = 2.0

# The AGL limb applies only to SINGLE-placement resources (spec section
# 2.1 lists "single placement" among the tunnel signatures) that carry at
# least this much near-horizontal solid area below effective grade.
# Round-5 measurement over every AGL ≤ −1 resource at EGLL: the three
# true AGL tunnels (6/7/10) are single-placement with 50/90/55 m² of
# below-grade deck; the false positives are `Docking_fit_wall_5m5` (36
# placements, offsets mixed −1.0 to +2.0 — the SAME resource above and
# below grade) and three `fit_wall_24x` walls (single placement, 0 m²
# below-grade horizontal area — pure vertical geometry).  Without the
# guard the docking wall seeded a component spanning every gate line and
# cascaded 280+ jetways/marks/terminal pieces onto the R4 exclusion list.
TUNNEL_AGL_MIN_BELOW_GRADE_DECK_AREA_M2 = 25.0

# A roof/deck face counts as "at grade" when its effective height is within
# this tolerance of the grade plane; the deck is everything below it.
TUNNEL_ROOF_TOP_TOLERANCE_M = 0.5

# The near-horizontal HARD plane set must cover at least this area to be a
# bridge deck (rejects railings and clutter).  Amendment A4: "hard" means
# ATTR_hard_deck OR plain ATTR_hard — the KMCO humped bridges (36/112 plain
# ATTR_hard triangles, zero hard_deck) and the EDDF A3 ramp carry no
# hard_deck at all; keying on hard_deck alone misses every humped bridge
# measured.
BRIDGE_MIN_DECK_AREA_M2 = 200.0

# The AGL limb's SECOND above-grade gate, and the one that catches a LOW
# bridge (owner ruling 2026-07-31, "all the bridges you highlighted are
# above ground bridges").  The height cap above catches a structure that
# TOWERS over grade — the EGKR control tower, OTHH Bridge_01 at +10.25 —
# but it cannot catch a road bridge whose deck stands only a metre or two
# up: OTHH Bridge_04 crests at +1.91, inside the 2.0 m cap, and was cut as
# a tunnel.  A below-grade SHELL does not carry a deck's worth of surface
# standing clear above grade; a bridge does — that is what a bridge is.
# Measured on the installed packs, near-horizontal area at or above
# +TUNNEL_ROOF_TOP_TOLERANCE_M:
#   OTHH Bridge_04   1 650.6 m²   <- refused here (8x over the floor)
#   EGLL Tunnel/7        0.0 m²   <- the only real AGL-limb tunnel today
#   EGLL Tunnel/6        0.0 m²
#   EGLL Tunnel/10     128.7 m²   <- kept, 1.55x under the floor
# Tunnel/10's 128.7 m² is exactly the figure
# TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M's comment cites when it warns that
# "an above-grade AREA test cannot do this job".  That warning is about a
# FRACTION test — Tunnel/10 carries more near-horizontal area above grade
# than below — and it stands.  An ABSOLUTE floor is a different test and
# clears Tunnel/10 with margin.  The floor is the bridge-deck floor by
# construction: the question being asked is literally "is there a deck up
# there?", so there is one number, not two.
TUNNEL_AGL_MAX_ABOVE_GRADE_DECK_AREA_M2 = BRIDGE_MIN_DECK_AREA_M2

# Deck-top profile bin length along the bridge axis (spec section 3.1 as
# amended by A2: a single deck plane cannot represent the KMCO/KDFW
# rising-bridge class — ruling R9, the vertical split is derived).
BRIDGE_PROFILE_BIN_LENGTH_M = 10.0

# A deck profile is non-flat (PROFILE_CARRIED candidate, amendment A4) when
# the crest stands at least this far above the LOWER of the two profile
# ends (supervisor ruling, 2026-07-09 round 3: crest − minimum end, not
# crest − maximum end).  This captures both the crowned KMCO humps (crest
# +5.15 over ends ≈ 0) and the MONOTONE EDDF A3 ramp (crest +6 AT one end,
# the other at grade): pavement drapes over the whole slope (35.5% coverage
# measured), so the terrain must follow it — reading a monotone ramp as
# flat/deck-carried would leave its causeway unbuilt.  The flat EDDF/KBNA
# decks rise 0 under either formula.
BRIDGE_PROFILE_NON_FLAT_MIN_M = 1.0

# Per-end abutment test (amendment A4): solid geometry of ANY hardness must
# reach effective grade within this horizontal radius of each deck-profile
# end, or the structure is a piered viaduct and is REFUSED (a deck-end pin
# on a viaduct would build a false causeway).  Measured end-to-nearest-
# grounded-vertex distances on every true bridge in the four packs
# (2026-07-09): EDDF Bridge_4 0.0/0.1 m, KMCO puente 2.2/11.5 m, puente2
# 2.6/9.8 m, KBNA taxiway-L 5.9/6.6 m (the embankment CLADDING grounds —
# the deck itself ends at +6; the test is "solid geometry reaches grade
# NEAR the end", never "the deck reaches grade"), KBNA Crossing 9.0/15.3 m,
# EDDF Bridge_2 15.5/16.0 m, EDDF Tunnel_1 pair 9.3/18.7 m, EDDF Bridge_3
# 26.6/29.4 m (worst case).  35 m covers all measured cases with margin;
# the KMCO via_tren rail viaduct has NO grounded vertex anywhere (global
# minimum y +3.45) and fails at any radius.
ABUTMENT_GRADE_SEARCH_RADIUS_M = 35.0

# The clearance-limiting underside plane must carry at least this area to
# count (filters stray clutter faces hanging below the girder line).
CLEARANCE_PLANE_MINIMUM_AREA_M2 = 10.0

# An underside plane below this height cannot be the ceiling of an opening
# traffic passes through — it is ground furniture (embankment cladding
# footings measured at +0.55/+0.64 under the KBNA decks), not a girder
# line.  Same physical floor as the deck-carried height threshold: an
# opening lower than a deck-carried deck's minimum height is not a
# corridor.
CLEARANCE_MINIMUM_OPENING_HEIGHT_M = 2.0

# A deck standing at least this far above grade is deck-carried on its own
# structure; a deck flush at grade (≈0) is terrain-carried.
BRIDGE_DECK_CARRIED_MIN_HEIGHT_M = 2.0

# Contract by pavement coverage of the mid-deck box (spec section 2.3): at
# or below the first fraction is deck-carried (pavement cut at the
# abutments); at or above the second is terrain-carried (pavement drapes
# across the span); the band between is refused as AMBIGUOUS (ruling R5).
BRIDGE_CONTRACT_PAVEMENT_COVERAGE_DECK_CARRIED_MAX = 0.05
BRIDGE_CONTRACT_PAVEMENT_COVERAGE_TERRAIN_CARRIED_MIN = 0.30

# A face is near-horizontal when the magnitude of its unit normal's
# vertical component reaches this — winding-sign independent (module
# docstring).  0.7 admits the gentle tunnel-mouth ramps as deck faces.
NEAR_HORIZONTAL_NORMAL_Y_MIN = 0.7

# Solid geometry within this height of grade is "ground-touching" — the
# abutment/ground-contact test (mirrors DSF_OBJECT_ELEVATED_BASE_M).
GROUND_CONTACT_TOLERANCE_M = 0.5

# Placements whose expanded world footprints overlap by this margin pool
# into one structure (module docstring, "Grouping").
STRUCTURE_GROUPING_EPSILON_M = 2.0

# ---------------------------------------------------------------------------
# Stock-library exclusion (2026-07-18, tile +51-001).  X-Plane's default
# library exports its virtual paths under ``lib/`` (``lib/airport/...``,
# ``lib/ships/...``, ``lib/cars/...``); a DSF referencing such a path is
# placing a GENERIC catalogue asset — a control tower, an oil rig, ramp
# clutter — never a pack-authored terrain shell, so no terrain feature
# should ever adapt to one.  Two live misclassifications motivated this:
# ``lib/airport/control_towers/small/16m_Norway.obj`` at EGKR Redhill
# (OBJECT_AGL −4.0 → feature-A tunnel) and ``lib/ships/OilRig.obj`` at
# EGKK (deck-and-legs geometry → bridge/deck terrain in the building-pad
# exclusion pass).  Third-party libraries that re-export ``lib/`` paths
# to replace stock assets are equally generic, so the prefix test stays
# correct for them too.
# ---------------------------------------------------------------------------
STOCK_LIBRARY_RESOURCE_PREFIX = "lib/"


def is_stock_library_resource(resource_path: str) -> bool:
    """True when ``resource_path`` is an X-Plane library virtual path
    (``lib/...``) — a stock catalogue asset the terrain classifier must
    never consume.  Case-insensitive, tolerant of backslash separators
    and a leading ``./``."""
    normalized = resource_path.replace("\\", "/").lower()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.startswith(STOCK_LIBRARY_RESOURCE_PREFIX)


def _vprint(level: int, message: str) -> None:
    """Verbosity-gated log line.

    This module is otherwise pure and is imported by tools and tests that
    have no UI module on the path, so the import is local and a missing
    ``O4_UI_Utils`` is silence, never an error."""
    try:
        import O4_UI_Utils
    except ImportError:
        return
    O4_UI_Utils.vprint(level, message)


# ---------------------------------------------------------------------------
# Pool evidence pre-screen (performance round, 2026-07-10).  A pool is
# projected into a structure frame only when it could possibly emit a
# record; measured at KBNA, 3,108 of 4,653 pools are flat clutter that no
# classification path can consume.  The limbs mirror the paths exactly:
#
# * hard triangles — tunnels (below-grade DRIVABLE deck), bridges
#   (hard-face components) and interior cutouts all key on
#   ``ATTR_hard`` / ``ATTR_hard_deck`` geometry;
# * a below-grade ``OBJECT_AGL`` offset — the guarded AGL tunnel limb
#   (the EGLL shells carry no hard triangles at all);
# * solid vertices deep enough below effective grade to seat a bowl or
#   trench interface level (feature C's non-flat classes);
# * a "bridge" resource-name hint — the cosmetic bridge path
#   (Murfreesboro class) works on structures with no hard geometry;
# * enough effective vertical span for a wall column — without one,
#   feature C cannot emit even a FLAT_CONFIRMED record (a wall column
#   needs :data:`WALL_COLUMN_MIN_VERTICAL_EXTENT_M` of vertical extent,
#   and no column can span more than its whole pool does).
#
# Together the limbs are output-preserving: a skipped pool provably
# produces no tunnel, no bridge, no refusal, no exclusion and no ground
# interface.
# ---------------------------------------------------------------------------

# The deepest solid vertex needed before any below-grade interface level
# can exist: TRENCH_SPINE_MIN_DEPTH_M (2.5) is the shallowest non-flat
# level threshold, levels cluster at INTERFACE_LEVEL_CLUSTER_M (0.5), so
# a qualifying level needs wall-column bases at or below -2.25; -2.0
# keeps a quarter-metre margin on top of that.
POOL_EVIDENCE_BELOW_GRADE_VERTEX_MAX_Y_M = -2.0

# ---------------------------------------------------------------------------
# Round-5 mega-pool refinement (A9/A10 worklist).  discover_object_pools
# merges everything whose bounding boxes chain-overlap — at EGLL the 20
# tunnel objects pooled with terminals and clutter into 5 mega-pools,
# diluting every tunnel metric (pool body-depth medians 0.94-1.93 m versus
# the true 4-7 m decks) and ballooning the R4 exclusion list to 812
# objects.  Features are therefore classified per CONTRIBUTING COMPONENT
# inside each pool, and records/exclusions carry only contributing
# resources.
# ---------------------------------------------------------------------------

# Below-grade drivable seeds whose footprints come within this distance
# join one tunnel/cutout component (a shell and its deck overlap; distinct
# tunnels are hundreds of metres apart).
TUNNEL_COMPONENT_JOIN_BUFFER_M = 2.0

# Hard-face seeds within this distance join one bridge component (the six
# KBNA taxiway-L part objects abut within metres; distinct bridges are
# hundreds of metres apart).
BRIDGE_COMPONENT_JOIN_BUFFER_M = 10.0

# A non-seed resource joins a tunnel/cutout component when at least this
# fraction of its own footprint lies over the component's below-grade deck
# (buffered by the join buffer) — the roof SHELL over its deck.  A
# terminal standing over a small tunnel overlaps only fractionally and
# stays out.
TUNNEL_COVER_CONTAINMENT_MIN_FRACTION = 0.5

# Effective heights are clustered into bins of this size to find a
# dominant plane (deck top, girder ceiling).
PLANE_HEIGHT_BIN_M = 0.5

# Morphological close applied to a triangle-footprint union, closing the
# hairline seams the triangle soup leaves (probe value).
FOOTPRINT_CLOSE_M = 0.05

# The roof footprint is dilated by this before subtraction so that a mouth
# is the deck genuinely clear of the slab, not a seam-width sliver.
ROOF_DIFFERENCE_BUFFER_M = 0.2

# A bridge deck is often several part objects (KBNA taxiway-L is six); this
# larger close welds the part seams into one deck footprint.
BRIDGE_DECK_CLOSE_M = 1.0

# Mouth / footprint fragments smaller than this are seam noise, discarded.
MINIMUM_FEATURE_AREA_M2 = 5.0

# A ceiling plane must sit at least this far below the deck top to be the
# clearance underside rather than the deck slab's own bottom face.
CEILING_MINIMUM_GAP_BELOW_DECK_M = 0.5

# Case-insensitive substring that marks a cosmetic (hard-less) bridge
# resource (Murfreesboro class).  Applies ONLY to structures with NO hard
# triangles at all; any structure with hard geometry goes through the
# geometric deck path, name-independent (the KMCO "puente" objects are
# named in Spanish — a name hint must never gate a hard deck).
COSMETIC_BRIDGE_NAME_HINT = "bridge"

# Contract labels (spec sections 2.3 / 3.1 / 3.2, amended by A4).
DECK_CARRIED = "DECK_CARRIED"
TERRAIN_CARRIED = "TERRAIN_CARRIED"
PROFILE_CARRIED = "PROFILE_CARRIED"
AMBIGUOUS = "AMBIGUOUS"

# Which evidence path produced the contract (BridgeStructure.contract_evidence,
# A10 worklist: tools must be able to print it).
CONTRACT_EVIDENCE_PAVEMENT_COVERAGE = "pavement_coverage"
CONTRACT_EVIDENCE_DECK_PROFILE = "deck_profile_fallback"

# ── KDFW CONTRACT REFUSAL BOUNDS (docs/specs/kdfw-bridge-refusal-spec.md
# clause 1; BOUNDS PROVISIONAL — owner ratification rides the round
# report) ────────────────────────────────────────────────────────────
#
# A BRIDGE IS A BRIDGE-SHAPED THING.  The Aerosoft KDFW pack ships its
# whole airport pavement inset as five objects on ONE shared DSF anchor;
# pooled, their near-horizontal hard faces union into a 2,849.6 × 820.6 m
# "deck" of 263,160 m².  With no pavement evidence to read (the deck IS
# the airport, so the coverage band measures nothing and the contract
# falls back to the profile — ``CONTRACT_EVIDENCE_DECK_PROFILE``) the
# crest test alone called it DECK_CARRIED, and 193 hard deck-end pins at
# one DEM sample + 8 m (183.29) inverted the final band (650 nodes /
# 43 pairs, worst 1.996 m).  The building-pad precedent does not apply:
# no footprint exists at which 183.286 is the right answer.
#
# The bounds are the same KIND of instrument as
# ``TUNNEL_MAX_DECK_FOOTPRINT_AREA_M2`` above (a tunnel is not an island)
# and are calibrated the same way — from the corpus, with orders of
# margin.  Sweep of every ``o4_object_terrain_classification`` sidecar in
# the shared data repo, 2026-08-16 (35 bridge records over 14 packs):
#
#   KDFW inset slab   2 849.6 m × 820.6 m   263 160 m²  <- refused here
#   next longest        217.8 m              (KMCI)
#   next widest          49.3 m              (KMCI)
#   next largest                               1 941 m² (OTHH)
#
# — the refused record exceeds every bound by 2.8× / 13.7× / 6.6× while
# the largest real deck in the corpus sits at 4.6× / 1.2× / 20.6× UNDER
# them.  The env overrides exist so the ratification arm is one variable,
# not an edit (the ``TUNNEL_MAX_DECK_FOOTPRINT_AREA_M2`` pattern).
BRIDGE_FALLBACK_MAX_DECK_LENGTH_M = float(
    os.environ.get("O4_BRIDGE_FALLBACK_MAX_DECK_LENGTH_M", "1000.0")
)
BRIDGE_FALLBACK_MAX_DECK_WIDTH_M = float(
    os.environ.get("O4_BRIDGE_FALLBACK_MAX_DECK_WIDTH_M", "60.0")
)
BRIDGE_FALLBACK_MAX_DECK_AREA_M2 = float(
    os.environ.get("O4_BRIDGE_FALLBACK_MAX_DECK_AREA_M2", "40000.0")
)

# The reason tokens the two clause-1 refusals record on the
# :class:`RefusedStructure` audit trail.  Each is a PREFIX: the reason
# string continues with the measurements that fired it, because "logs the
# refusal with its measurements" is the spec's own wording and a bare
# token sends the reader back to the pack to find out what happened.
BRIDGE_REFUSAL_IMPLAUSIBLE_DECK = "bridge_deck_scale_implausible"
BRIDGE_REFUSAL_CLEARANCE_UNDER_MINIMUM = "bridge_girder_clearance_under_minimum"

# The contract coverage band spans the middle third of the deck ALONG the
# axis and — A10 round-5 calibration — the central HALF of the deck ACROSS
# the axis.  Measured at KBNA taxiway-L (the deck-carried flagship): every
# draped-pavement overlap with the 131 × 55 m deck footprint hugs a lateral
# edge (across-axis positions [−15, 0] and [−55, −43] on a [−55, 0] deck) —
# adjacent AT-GRADE taxiways lapping the deck's side, not span-crossing
# pavement — and the full-width band read them as 14.5% coverage, landing
# the flagship in the refusal dead band.  The carried surface runs the deck
# CENTER; the central-half band measures 0% there while keeping the
# genuinely continuous EDDF/KMCO drapes (centered along the deck) intact.
BRIDGE_COVERAGE_BAND_WIDTH_FRACTION = 0.5

# Deck hardness kinds (BridgeStructure.deck_hardness): which OBJ8 collision
# attribute carries the drivable surface.  Ruling R8's flush-seating cut
# keys on genuine ATTR_hard_deck.
DECK_HARDNESS_HARD_DECK = "hard_deck"
DECK_HARDNESS_HARD = "hard"
DECK_HARDNESS_COSMETIC = "cosmetic"

# ---------------------------------------------------------------------------
# Feature C — structure ground interfaces (spec section 3.4, amendments
# A5-A8, rulings R5-as-refined and R10).
# ---------------------------------------------------------------------------

# The footprint boundary is divided into this many radial sectors around
# the structure centroid for the perimeter base profile.  36 sectors of
# 10 degrees make one sector 2.8% of the perimeter, so the 5% share floor
# below is a real filter (with 16 sectors any single occupied sector would
# already pass it).
PERIMETER_SECTOR_COUNT = 36

# A vertex column is a WALL column when its vertical extent reaches this
# (amendment A5, normative): roof-overhang and draped-decal edges otherwise
# dominate the base profile as false levels.
WALL_COLUMN_MIN_VERTICAL_EXTENT_M = 2.5

# Solid vertices are grouped into columns on this horizontal grid.
WALL_COLUMN_GRID_M = 1.0

# The per-sector facade-base low envelope is this percentile of wall-column
# bases (amendment A5: "minimum (≈ 5th percentile)"; never the dominant or
# highest band — the dominant band is exactly the ELLX/LFPG decoy).
FACADE_BASE_LOW_ENVELOPE_PERCENTILE = 5.0

# Interface levels are clustered at this granularity (amendment A5; keeps
# the LFLL −2 m mezzanine and −10 m rail floor distinct).
INTERFACE_LEVEL_CLUSTER_M = 0.5

# A clustered level below this perimeter share is a basement/service
# parasite and is dropped (amendment A5) — UNLESS the level is below grade
# and carried by the structure's dominant-area object (amendment A7, the
# LFPG T1 lesson: the share filter must never kill the main floor).
INTERFACE_LEVEL_MIN_PERIMETER_SHARE = 0.05

# Ground contact: solid faces whose height is within this band of
# effective grade count as ground-contact geometry.
GROUND_CONTACT_BAND_HALF_WIDTH_M = 1.0

# A structure is a BOWL candidate when its overall ground-contact fraction
# falls below this (amendment A7: "essentially no ground-contact
# geometry"; LFPG T1 measured 0-23% per OBJECT — the structure-level cut
# sits at 10%, the least-measured constant of this family, flagged in the
# workstream report)...
BOWL_MAX_GROUND_CONTACT_FRACTION = 0.10

# ...and its at-grade wall-column base share falls below this: a bowl
# structure has essentially NO facade based at grade (measured: LFPG T1
# pool 0.05 versus the LFPG T2A spine pool 0.32 and EGLL buried terminals
# ≈ 0.5 — the trench/buried structures keep their at-grade halls, the
# bowl floats entirely above its sunken floor).  This pair of gates
# implements amendment A7's "dominant-area object bases below grade" in
# the form that actually measures: the LITERAL dominant-area object in
# these packs is a mega-bake whose MEDIAN column base is elevated
# (+32 m at T1, +14 m at T2A — rooftop columns), so the dominant-object
# base is mechanically useless as the bowl key; the at-grade base share
# is the signal A7's evidence (0-23% ground contact, shell base −3.43)
# was actually pointing at.
BOWL_MAX_AT_GRADE_BASE_SHARE = 0.10

# ...OR — the OPEN-PIT limb (owner defect 2026-07-30, OTHH Aeroscape
# ``Buildings/Dewatering Drainage/*``) — the structure has essentially
# NOTHING above grade.  ``BOWL_MAX_GROUND_CONTACT_FRACTION`` cannot
# recognize a shallow open basin: the ground band is ±1 m of grade, and
# a 3.8 m pit with sloped batters necessarily has its own rim and upper
# batter inside that band, so the SHALLOWER the pit the MORE it reads as
# "ground contact" (measured at OTHH: Drainage_04 0.502, Drainage_05
# 0.676, Drainage_06 0.546 — the deep −13 m Dewatering pair scores
# 0.145/0.172 and already classified TRENCH_SPINE).  The signal a pit
# cannot fake is the other side of grade: a bowl has no geometry ABOVE
# it.  Measured above-grade face-area share is 0.000 for all six OTHH
# basins (zero triangles above +1 m); the floor sits just off zero to
# tolerate stray clutter welded into a pool.  This limb REPLACES only
# the ground-contact term — the at-grade wall-base share, floor depth
# and footprint-area gates below still all apply, and they are what
# keep the ELLX/EGLL at-grade halls (base share 0.32-0.5) out.
BOWL_MAX_ABOVE_GRADE_AREA_FRACTION = 0.02

# Open-pit COMPONENT seeding (owner defect 2026-07-30, OTHH Drainage_03
# and _05).  The pit rule above is a whole-STRUCTURE measure, and a pool
# is not a structure: ``discover_object_pools`` groups by world-footprint
# overlap, so at OTHH the Drainage_05 basin landed in one pool with the
# entire Emiri Terminal complex (52 resources) and the merged frame
# measured 0.944 above-grade area — the basin vanished into FLAT_CONFIRMED
# while the geometrically identical Drainage_04, which happened to pool
# alone, classified BOWL_UNDER_DECK.  This is exactly the mega-pool
# dilution the round-5 work fixed for tunnels by classifying per
# COMPONENT (``_below_grade_drivable_components``); these two constants
# are the non-hard analogue of that seed.  A resource seeds a pit
# component when its OWN authored geometry is a pit: nothing above the
# ground band, and a floor at least PIT_SEED_MIN_DEPTH_M below it.  Both
# come from ``_ResourceGeometryCache.evidence`` (already computed for the
# pool pre-screen), so seeding costs no new geometry pass.
PIT_SEED_MIN_DEPTH_M = 2.5
PIT_SEED_MAX_ABOVE_GRADE_Y_M = GROUND_CONTACT_BAND_HALF_WIDTH_M

# ...and the structure carries a below-grade interface level at least
# this deep.  Round-5 calibration against the EGLL full-pack run: every
# TRUE bowl measures −3.41 m or deeper (LFPG T1 shell −3.42, satellite
# ring pools −3.4/−3.9/−4.5), while every false positive is buried
# library-clutter slack between −1.03 and −2.47 (fuel tank −1.50, sheds
# −2.08, truck/factory pair −2.47) — sunk-object slack the A6 oracle says
# to bury under flat terrain.  3.0 sits between the measured sets.
BOWL_MIN_BELOW_GRADE_LEVEL_DEPTH_M = 3.0

# Bowl and trench records are only emitted for structures at least this
# large, guarding against small AGL-placed clutter (jetway slack, sunk
# signage) reading as terrain features.  NOT measurement-derived — a
# conservative invented floor, flagged in the workstream report.
STRUCTURE_INTERFACE_MIN_FOOTPRINT_AREA_M2 = 500.0

# A TRENCH_SPINE interface level sits at least this far below grade (the
# LFLL −2 m mezzanine is NOT a trench floor; the −7.5 m LFPG T2 and −10 m
# LFLL levels are)...
TRENCH_SPINE_MIN_DEPTH_M = 2.5

# ...and must be carried by at least this many objects (LFPG T2: 23
# objects share one −7.5 m level over 3 km; one object's private basement
# is not a spine)...
TRENCH_SPINE_MIN_CONTRIBUTING_OBJECTS = 2

# ...and the trench LEVEL itself must hold at least this perimeter share:
# a spine is the structure's defining below-grade interface, not a
# minority stagger.  Measured: true trench levels hold 0.50 (LFPG K5
# pool) and 0.639 (T2A spine) of their occupied sectors; the false
# positives hold 0.033-0.067 (EGLL basement parasites) and 0.057 (the
# KBNA Metropolitan downtown-skyline bake, whose building bases stagger
# 0 to -2.56 down a real city slope).  0.25 sits a factor of two from
# both measured sets.
TRENCH_SPINE_MIN_LEVEL_PERIMETER_SHARE = 0.25

# ...and the below-grade content footprint's LARGEST CONNECTED PART must
# reach this area.  A trench the terrain must open is one COHERENT
# corridor (the LFPG T2A spine is a single contiguous ribbon over 3 km;
# the smallest true LFPG trench pool measures 8,885 m²), never scattered
# pockets: summing disjoint pieces let 276 EGLL jetway-leg slack specks
# plus hotel basements masquerade as a "multi-object trench" in the
# round-5 full-pack run (the EGLL T2_3 buried-basement group alone is
# 48 m² — A6 oracle: buried, flat).  Largest-part gating, not sum
# gating.
TRENCH_SPINE_MIN_FOOTPRINT_AREA_M2 = 1000.0

# Interior cutout (ruling R10, guards calibrated by amendment A8): the
# below-grade DRIVABLE content must be at least this fraction enclosed
# within the structure's own at-grade plan footprint (KDEN platforms are
# 100% enclosed; EGLL tunnel decks are open at the mouths).
INTERIOR_CUTOUT_ENCLOSURE_MIN_FRACTION = 0.95

# A pool with at least this many wall columns is a BUILDING and never
# enters the bridge path — a terminal with a drivable elevated roadway
# baked in (the ELLX departures ramp is plain ATTR_hard) would otherwise
# be swallowed as a bridge candidate and refused by the viaduct guard,
# leaving no feature-C record.  Measured wall-column counts: every true
# bridge pool across KBNA/KMCO/EDDF has 0-169 (via_tren 0, KBNA
# taxiway-L 132, EDDF Tunnel_1 pair 169); the ELLX terminal pool has
# 6,752 and the LFPG terminal pools 1,968-13,511 — a 40x gap around this
# floor.  The tunnel path is deliberately NOT gated on it: cut-and-cover
# shells legitimately carry long wall rows.
BUILDING_MIN_WALL_COLUMN_COUNT = 500

# The at-grade plan footprint is morphologically closed at this radius —
# building bakes carry larger part seams than bridge decks.
AT_GRADE_FOOTPRINT_CLOSE_M = 2.0

# Interface class labels (StructureGroundInterface.interface_class).
INTERFACE_FLAT_CONFIRMED = "FLAT_CONFIRMED"
INTERFACE_BOWL_UNDER_DECK = "BOWL_UNDER_DECK"
INTERFACE_TRENCH_SPINE = "TRENCH_SPINE"
INTERFACE_INTERIOR_CUTOUT = "INTERIOR_CUTOUT"

# ``TunnelStructure.terrain_feature`` values — which classifier produced
# a trench record (see that field).
TERRAIN_FEATURE_TUNNEL = "tunnel"
TERRAIN_FEATURE_BASIN = "basin"

# The ground-interface classes the basin-trench emitter carves
# (``config.OBJECT_BASIN_TRENCH``).  INTERIOR_CUTOUT is deliberately NOT
# here: ruling R10 cuts it strictly inside the structure's at-grade
# perimeter, which is a different shape from the open trench this feature
# emits, and it has no emitter yet.
CARVED_BASIN_INTERFACE_CLASSES = (
    INTERFACE_BOWL_UNDER_DECK,
    INTERFACE_TRENCH_SPINE,
)


# ---------------------------------------------------------------------------
# Emitted records (spec section 3.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MouthDepthStatistics:
    """Ramp-profile depth statistics for one tunnel mouth, in metres BELOW
    grade (positive down), from the deck faces whose centroid falls inside
    the mouth polygon."""

    minimum_depth_m: float
    maximum_depth_m: float
    mean_depth_m: float
    sample_count: int


@dataclass(frozen=True)
class TunnelStructure:
    """A below-grade cut-and-cover structure (EGLL class, feature A).

    ``roof_footprint`` / ``deck_footprint`` / ``mouth_polygons`` are
    shapely polygons in the structure metre frame (module docstring, "The
    world frame"); ``mouth_polygons`` are the open cuts, ``deck −
    roof``.  ``above_ground_offset_m`` is the (signed) placement offset
    carried into every effective height; ``body_depth_m`` is the depth
    (positive) of the roofed body's deck below grade."""

    object_resources: list[str]
    anchor_longitude_latitude: tuple[float, float]
    frame_origin_longitude_latitude: tuple[float, float]
    heading_degrees: float
    placement_kind: str
    above_ground_offset_m: float
    roof_footprint: Polygon | None
    deck_footprint: Polygon | None
    mouth_polygons: list[Polygon]
    mouth_depth_samples: list[MouthDepthStatistics]
    body_depth_m: float
    # Deepest SOLID effective height across the WHOLE structure (walls
    # included — EGLL shells reach up to ~2 m below their road decks).
    # The trench floor keys on this, never on the deck median: a floor
    # at deck − 0.5 left the shell bottoms buried and ground poking
    # through the side walls (user 2026-07-18, in-sim).
    solid_minimum_y_m: float | None = None
    # Plan outline of EVERY below-grade solid triangle (walls become
    # thin slivers, sloped ramp skins project with real area).  The
    # near-horizontal deck/roof unions under-represent wall-and-ramp
    # shells — the EGLL west-end AGL pair classified 86/45 m2 of "deck"
    # inside 25x19 / 18x16 m structures, so the trench cut a 10x3 m
    # sliver and the rest of the shell stayed buried (user 2026-07-18c,
    # in-sim).  The trench footprint unions this with deck and roof.
    solid_outline_footprint: Polygon | MultiPolygon | None = None
    # Which below-grade terrain feature this record came from:
    # :data:`TERRAIN_FEATURE_TUNNEL` (the feature-A classifier) or
    # :data:`TERRAIN_FEATURE_BASIN` (a feature-C open pit adapted by
    # ``object_terrain_assembly.basin_trench_structures``).  Both cut the
    # same open trench under the same ``grade_law`` functions; the tag
    # only names the emitted plates and log lines so an in-sim defect is
    # traceable to the classifier that produced it.
    terrain_feature: str = "tunnel"
    #: The facility's ENTRANCE-RAMP CORRIDOR in this record's own metre
    #: frame (spec ``docs/specs/lemd-basin-trench-ramp-extension-spec.md``
    #: Amendment 1 §2), or ``None``.  ADDITIVE ONLY: it is never part of
    #: the BODY — ``deck_footprint`` / ``roof_footprint`` /
    #: ``solid_outline_footprint`` are what every law input and the
    #: post-mesh seat band are read from, and Amendment 1 exists because
    #: putting the ramp in there moved all of them.  The layout emitter
    #: joins it to the floor pan and stands the rim band down inside it;
    #: no other consumer reads it.
    ramp_reach_corridor: "Polygon | MultiPolygon | None" = None
    # Ruling R13 (owner 2026-07-30): this trench TAKES THE PAVEMENT WITH
    # IT — airside pavement over the body is cut instead of winning under
    # R2.  Set only for open pits (``is_open_pit_interface``); a tunnel
    # record leaves it False, so a roofed body keeps R2/R8 exactly as
    # before (the roof object, not our terrain, is the surface there).
    cuts_pavement: bool = False


@dataclass(frozen=True)
class BridgeStructure:
    """A taxiway bridge (KBNA / EDDF / KMCO class, feature B).

    ``deck_polygon`` and ``abutment_lines`` are in the structure metre
    frame; ``abutment_lines`` is ordered [start end, far end] along the
    deck axis, matching ``deck_top_profile`` / ``deck_end_elevations_y_m``
    / ``abutment_reaches_grade`` order.

    ``deck_top_profile`` is the deck top's effective height sampled in
    :data:`BRIDGE_PROFILE_BIN_LENGTH_M` bins along the deck's long axis,
    as ``(along_axis_m, y_m)`` pairs from the start end (amendment A2 —
    flat KBNA decks give a constant profile; the KMCO crowned humps and
    sloped ramps give the full shape, ruling R9).

    **Deck extent — the official definition (supervisor ruling, 2026-07-09
    round 3):** the deck is the FULL drivable hard surface, so the profile
    ends where that surface reaches grade, ramps included (KMCO: 392/909 m
    with ends at 0.00, not the 328/820 m between-abutments span).  The pin
    semantics W-B consumes are "profile value at each pavement/terrain
    contact point": a surface whose ramps land at grade pins terrain AT
    grade at the tips, with per-vertex targets along the whole ramp —
    strictly more information than a between-abutments span, and the two
    definitions coincide where a deck has no ramps (KBNA).  Do not
    re-derive a trimmed span downstream.

    ``deck_end_elevations_y_m`` are the first and last profile values (the
    solver pin values at the deck tips); ``deck_top_y_m`` is the profile
    maximum (crest).

    ``ceiling_y_m`` is the LARGEST-area underside plane below the local
    deck top; ``clearance_underside_y_m`` is the LOWEST such plane above
    the opening — the value that limits corridor clearance (KBNA: slab
    underside +4.8 versus girder line +4.2; the corridor emitter needs
    +4.2).  Either is ``None`` when no underside plane was found.

    ``abutment_reaches_grade`` records, per end, whether solid geometry of
    ANY hardness reaches effective grade within
    :data:`ABUTMENT_GRADE_SEARCH_RADIUS_M` of that profile end.  A
    structure failing at either end is a piered viaduct and never becomes
    a ``BridgeStructure`` at all (it lands in
    :attr:`ClassificationResult.refusals`), so on any emitted record both
    entries are ``True``; the field is kept for the audit trail.

    ``deck_hardness`` says which OBJ8 attribute carries the drivable
    surface: :data:`DECK_HARDNESS_HARD_DECK` (genuine ``ATTR_hard_deck``,
    the ruling-R8 flush-seating case), :data:`DECK_HARDNESS_HARD` (plain
    ``ATTR_hard`` — the KMCO/EDDF-ramp class, amendment A4) or
    :data:`DECK_HARDNESS_COSMETIC` (no hard geometry, Murfreesboro class).
    When a deck mixes both hard kinds the dominant kind by face area wins.
    ``hard_deck`` stays the boolean R8 consumers key on: ``True`` ONLY for
    genuine ``ATTR_hard_deck``.

    ``contract`` is one of :data:`DECK_CARRIED`, :data:`TERRAIN_CARRIED`,
    :data:`PROFILE_CARRIED`, :data:`AMBIGUOUS` (spec section 3.2, A4).
    ``absolute_deck_elevation_m`` is the median of the OBJECT_MSL fixtures
    that fall on the deck, else ``None``."""

    object_resources: list[str]
    anchor_longitude_latitude: tuple[float, float]
    frame_origin_longitude_latitude: tuple[float, float]
    heading_degrees: float
    deck_polygon: Polygon | None
    deck_top_profile: list[tuple[float, float]]
    deck_top_y_m: float
    deck_end_elevations_y_m: tuple[float, float]
    deck_length_m: float
    deck_width_m: float
    ceiling_y_m: float | None
    clearance_underside_y_m: float | None
    abutment_lines: list[tuple[tuple[float, float], tuple[float, float]]]
    abutment_reaches_grade: tuple[bool, bool]
    contract: str
    absolute_deck_elevation_m: float | None
    hard_deck: bool
    deck_hardness: str
    # A10 worklist: the measured coverage fraction (None when no pavement
    # evidence was supplied) and which evidence path produced the
    # contract, so audit tools can print both.
    pavement_coverage_fraction: float | None = None
    contract_evidence: str = CONTRACT_EVIDENCE_DECK_PROFILE


@dataclass(frozen=True)
class RefusedStructure:
    """A structure recognized as bridge-like OR tunnel-like but refused a
    terrain feature, with the reason (amendment A4: the KMCO via_tren
    piered viaduct must be refused — a deck-end pin there would build a
    false causeway; round-5 guard 2: an island-scale tunnel deck, VHHH's
    21.5 km² sea-bed shell).  Refused structures are NOT in the R4
    exclusion list: no terrain was adapted to them, so the Phase 2 y-bake
    still applies.

    THE DECK IS STILL MEASURED (round-12 R12-2).  A piered viaduct is
    refused a terrain FEATURE — no deck-end pin, no carved ground — but
    it is still one rigid body, and the classifier has already measured
    its deck axis, its abutment lines and its crest by the time the
    viaduct guard fires.  Those measurements ride along here so the
    post-mesh seat can take the SAME rigid deck-top seat as a classified
    bridge instead of handing the family to the per-structure y-bake,
    which tears one bridge across three grounds (OTHH Bridge_02/03/06:
    0.00 / 1.63 / 3.96 m).  A refusal from any OTHER limb (the tunnel
    island-deck guard, a structure refused before its axis existed)
    leaves them ``None`` — that family genuinely has no measurable deck
    and keeps today's y-bake.

    * ``deck_object_resources`` — the resources carrying the deck faces
      the axis was measured on (a subset of ``object_resources``, which
      is the whole refused component: the family that seats together).
    * ``abutment_lines`` / ``frame_origin_longitude_latitude`` — the two
      deck-end lines in the structure metre frame and the frame origin
      they are measured from, exactly as :class:`BridgeStructure` carries
      them.
    * ``anchor_longitude_latitude`` — the point a DRAPED member seats on.
    * ``deck_top_y_m`` — the authored deck crest in the structure frame.
    * ``deck_members`` — ONE :class:`RefusedDeckMember` PER RESOURCE that
      carries deck faces (round-12 amendment 3).  This is the record the
      seat actually measures from; the whole-component
      ``abutment_lines`` above are the merged min-rect's, which on a
      mega-pool merge is a chord across everything the merge swallowed
      (measured at OTHH: 175.2 m, running ALONG the canal, so the
      landward walk walked into it).  A member deck face's own end lines
      are real bridge ends and touch the banks.
    """

    object_resources: list[str]
    reason: str
    deck_object_resources: list[str] | None = None
    anchor_longitude_latitude: tuple[float, float] | None = None
    frame_origin_longitude_latitude: tuple[float, float] | None = None
    abutment_lines: list | None = None
    deck_top_y_m: float | None = None
    deck_members: tuple = ()

    @property
    def has_measurable_deck(self) -> bool:
        """True when this refusal carries a deck the R12-2 rigid seat can
        stand on: at least one member deck face with two end lines and a
        crest, and the frame to project them out of."""
        return (
            bool(self.deck_members)
            and self.anchor_longitude_latitude is not None
            and self.frame_origin_longitude_latitude is not None
        )


@dataclass(frozen=True)
class RefusedDeckMember:
    """One RESOURCE's own deck face inside a refused structure (round-12
    amendment 3).

    THE OWNER'S RULING.  "If it's really several bridges connected as one
    object, then there should be a seat level that works for all of them
    without splitting."  The split was only ever needed for MEASUREMENT,
    and the classifier already has the measurement: each member's deck
    faces, with their own axis and their own crest.  So the merged
    min-rect is retired from the seat and each member speaks for itself —
    then the assembly has to AGREE with itself, which is a test the merge
    could never offer.

    ``abutment_lines`` are this member's own deck-end lines in the
    structure metre frame (same frame as the parent's
    ``frame_origin_longitude_latitude``); ``deck_top_y_m`` is its own
    EFFECTIVE crest (AGL + authored y), the frame amendment 2's B1
    measures the delta in."""

    resource_path: str
    abutment_lines: list
    deck_top_y_m: float


@dataclass(frozen=True)
class PortalFaceStructure:
    """A bare tunnel-portal FACE (user 2026-07-17, EGGW class).

    Some packs author a road tunnel's portals as nothing but a textured
    face quad HANGING BELOW grade — a handful of SOFT triangles from
    ``y ≈ 0`` down to the road deck (EGGW: one 2-triangle quad per
    mouth, ``y −8.33..+0.06``, plain ``OBJECT``, anchor exactly on the
    face line).  Such a face matches neither the tunnel signature
    (nothing drivable, no ``ATTR_hard``, no negative ``OBJECT_AGL``)
    nor any bridge signature (no deck), so the A6 discriminator is
    silent — yet a matched PAIR of these faces is decisive tunnel
    evidence where OpenStreetMap has no mapped bore.

    Field names deliberately mirror the :class:`BridgeStructure`
    attributes the portal-pair machinery reads (``heading_degrees``,
    ``deck_top_y_m``, ``object_resources``,
    ``anchor_longitude_latitude``), so a face record can ride the same
    pairing code:

    * ``heading_degrees`` — bearing of the implied TUNNEL AXIS: the
      face's long horizontal axis + 90° (the placement's own heading is
      routinely 0 and carries no information).
    * ``deck_top_y_m`` — the face HEIGHT (``face_max_y − face_min_y``):
      standing at the mouth road grade, the face top — and the deck the
      terrain must hold behind it — is this far up.
    * ``face_hangs_below`` — always True for this record type; the
      portal seat contract inverts against the KBNA class (the object
      drapes at ``terrain(anchor)`` and the geometry hangs DOWN, so the
      anchor must sit on the DECK-grade crown, never on the road-grade
      mouth plate)."""

    object_resources: list[str]
    anchor_longitude_latitude: tuple[float, float]
    heading_degrees: float
    face_polygon_longitude_latitude: Polygon
    face_min_y_m: float
    face_max_y_m: float
    face_width_m: float
    deck_top_y_m: float
    # Bearing of the face LINE itself (mod 180).  ★A portal face is NOT
    # necessarily perpendicular to the tunnel axis — it parallels the
    # structure it passes under (EGGW: the taxiway edge crosses the road
    # obliquely; face line 115°, axis 57°).  Pairing therefore tests
    # face-vs-face parallelism and segment-crosses-face, never
    # face-perpendicular-equals-axis.
    face_line_bearing_degrees: float = 0.0
    face_hangs_below: bool = True
    # BridgeStructure-shaped compatibility fields: once a face pair OWNS
    # its crossing (ruling 2026-07-18) the record flows through pair
    # consumers written for bridges — every ``deck_polygon is None``
    # guard then takes its degenerate branch (a face has no deck).
    deck_polygon: Polygon | None = None
    frame_origin_longitude_latitude: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True)
class StructureGroundInterface:
    """Feature C: what a BUILDING structure's construction says the ground
    must do (spec section 3.4; extraction filters normative per A5, bowl
    rule per A7, interior-cutout rule per R10/A8).

    Emitted for pools that classify as neither tunnel nor bridge and carry
    wall geometry.  ``interface_class`` is one of
    :data:`INTERFACE_FLAT_CONFIRMED` (substantial ground contact — any
    vertical drama above is object-carried, terrain stays flat; the ELLX
    verdict), :data:`INTERFACE_BOWL_UNDER_DECK` (essentially no ground
    contact and the dominant-area object based below grade — LFPG
    Terminal 1), :data:`INTERFACE_TRENCH_SPINE` (a continuous below-grade
    level shared across multiple objects — LFPG Terminal 2 / LFLL rail),
    :data:`INTERFACE_INTERIOR_CUTOUT` (below-grade drivable content
    enclosed within the structure's own at-grade footprint — the KDEN
    train halls, ruling R10).

    ``perimeter_base_profile`` is the facade-base low envelope per
    occupied radial sector, as ``(sector_center_angle_degrees,
    low_envelope_y_m)``; ``interface_levels`` are the surviving clustered
    levels as ``(level_y_m, sector_indices, perimeter_share)`` (the spec
    3.1 sketch).  ``ground_contact_fraction`` is the area share of solid
    faces within :data:`GROUND_CONTACT_BAND_HALF_WIDTH_M` of effective
    grade, overall and per sector (zero-area sectors report 0.0).

    ``at_grade_wall_base_share`` is the fraction of wall columns whose
    base lies within the ground band — the bowl-versus-everything key
    (see :data:`BOWL_MAX_AT_GRADE_BASE_SHARE`).

    ``below_grade_footprint`` (frame metres) is the bowl footprint, the
    trench-spine footprint union, or the enclosed cutout hall, by class
    (``None`` for flat).  ``floor_y_m`` is the matching floor value —
    for a BOWL it is the largest-share below-grade interface level (the
    shell base) and a **bound, not a target**
    (``floor_is_bound_not_target=True``): objects under-specify bowl depth
    (A7: T1 shell base −3.4 m where the reference hand patch cuts −8 m).
    For an INTERIOR_CUTOUT the floor is keyed on the HARD content's
    minimum y — never the deepest solid (KDEN carries non-hard foundation
    piles to −19 m; keying on deepest solid would blow the pocket floor
    9 m past the platform, A8).

    ``elevated_deck_above`` records co-occurring elevated near-horizontal
    geometry over the same footprint — it CONFIRMS a bowl (the T1 helix)
    and is a decoy over a flat structure (the ELLX departures roadway);
    the deciding signal is always the ground-contact fraction (A7).

    KDEN-class ``.agp`` buildings: the classifier is pure and never parses
    ``.agp`` — the CALLER assembles autogen-point part collections
    (``agp_reader`` OBJ_DELTA offsets) into per-part placements sharing
    one anchor, and the ordinary pool grouping absorbs them (A8)."""

    object_resources: list[str]
    anchor_longitude_latitude: tuple[float, float]
    frame_origin_longitude_latitude: tuple[float, float]
    heading_degrees: float
    perimeter_base_profile: list[tuple[float, float]]
    interface_levels: list[tuple[float, tuple[int, ...], float]]
    split_level: bool
    ground_contact_fraction: float
    ground_contact_fraction_by_sector: list[float]
    at_grade_wall_base_share: float
    interface_class: str
    below_grade_footprint: object | None
    floor_y_m: float | None
    floor_is_bound_not_target: bool
    elevated_deck_above: bool
    # Face-area share standing clear ABOVE the ground band — the
    # open-pit limb of the bowl rule (see
    # :data:`BOWL_MAX_ABOVE_GRADE_AREA_FRACTION`).  Defaulted so
    # hand-constructed records in tests stay valid.
    above_grade_area_fraction: float = 0.0
    # THE TRUE DEEPEST SOLID of this structure's frame (effective y,
    # every member pooled) — ``_StructureFrame.minimum_effective_height_m``,
    # the same quantity :attr:`TunnelStructure.solid_minimum_y_m` carries
    # for a feature-A tunnel, and the SAME definition (raw solid vertex
    # set, walls included, AGL folded in).
    #
    # It is NOT ``floor_y_m``.  ``floor_y_m`` is a CLUSTERED interface
    # LEVEL — the largest-perimeter-share below-grade level for a bowl —
    # and a level is a summary: OTHH Drainage_06 clusters to −3.859 m
    # while its deepest solid reaches −4.201 m, so a floor cut to the
    # level less 0.5 m left 0.158 m of the promised clearance and the
    # modelled bottom nearly poked through.  The basin trench floor law
    # (``grade_law.basin_trench_floor_elevation_m``) keys on THIS.
    #
    # Defaulted to ``None`` so hand-constructed records in tests stay
    # valid; consumers fall back to ``floor_y_m`` (the pre-2026-08-09
    # behaviour) when it is absent.
    solid_minimum_y_m: float | None = None


def is_carved_basin_interface(interface: StructureGroundInterface) -> bool:
    """Does the basin-trench feature cut terrain for this interface?

    THE predicate, imported by both consumers so they can never drift
    (the lockstep pattern ruling R1 sets for the trench law itself): the
    classifier uses it to decide which interfaces join the ruling-R4
    y-bake exclusion list, and
    ``object_terrain_assembly.basin_trench_structures`` uses it to decide
    which become trench records.  An interface excluded from the y-bake
    but not carved — or carved but still y-baked — is exactly the
    stacked terrain-to-object/object-to-terrain correction R4 forbids.

    A carved interface is a BOWL_UNDER_DECK or TRENCH_SPINE
    (:data:`CARVED_BASIN_INTERFACE_CLASSES`) that actually carries the
    two things a cut needs: a below-grade footprint to cut, and a floor
    strictly below grade to cut it to.
    """
    if interface.interface_class not in CARVED_BASIN_INTERFACE_CLASSES:
        return False
    footprint = interface.below_grade_footprint
    if footprint is None or getattr(footprint, "is_empty", True):
        return False
    return interface.floor_y_m is not None and interface.floor_y_m < 0.0


def part_has_solid_thickness(minimum_y: float, maximum_y: float) -> bool:
    """THE "a decal is not a solid" predicate (spec ``docs/specs/
    tunnel-trench-law-and-basin-floor-spec.md`` §2.1), in ONE place.

    A part with vertical extent below
    :data:`config.MIN_SOLID_PART_THICKNESS_M` is PAINT: a flat authored
    quad, not a structure.  Both readers of that notion go through this
    function so a second spelling of it cannot drift into existence —
    the FLOOR WITNESS in :func:`_build_structure_frame` (§2.1) and the
    open-pit SEED set in :func:`_open_pit_components`
    (``config.BASIN_POOL_SCOPING``).

    ``minimum_y``/``maximum_y`` are the part's OWN authored bbox bounds.
    A placement's AGL offset is a constant added to both, so the extent
    is the authored one whichever frame the caller measured in.
    """
    from .config import MIN_SOLID_PART_THICKNESS_M
    return (maximum_y - minimum_y) >= MIN_SOLID_PART_THICKNESS_M


def is_open_pit_interface(interface: StructureGroundInterface) -> bool:
    """Is this carved basin an OPEN pit — a hole with nothing of the
    pack's own standing over it?

    Ruling R13 (owner, 2026-07-30: "for below grade drainage objects, cut
    a trench in the pavement") keys on THIS, deliberately NOT on
    :func:`is_carved_basin_interface`.  Removing taxiable pavement is
    only right where the modelled hole is open to the sky; every other
    carved class keeps ruling R2's "pavement always wins", because
    something the pack authored is the visible surface there:

    * a :data:`INTERFACE_BOWL_UNDER_DECK` admitted by the amendment-A7
      ground-contact limb — LFPG Terminal 1's drum floats over its sunken
      floor, and the drum is what a walker sees;
    * a :data:`INTERFACE_TRENCH_SPINE` — LFPG Terminal 2's halls sit at
      grade over one continuous below-grade level (at OTHH: the
      Dewatering pits pooled with their aux buildings and control posts).

    (:data:`INTERFACE_INTERIOR_CUTOUT` never reaches here — ruling R10
    forbids carving pavement outright, and ``is_carved_basin_interface``
    already rejects it.)

    The signal is the bowl rule's own open-pit limb, re-read off the
    record: "essentially nothing above grade IS the pit signal"
    (:data:`BOWL_MAX_ABOVE_GRADE_AREA_FRACTION`).  ``elevated_deck_above``
    is deliberately NOT consulted — amendment A7 records it as a decoy
    that a flat structure also raises (it happens to agree on all eight
    OTHH records, which is why it earns no vote).
    """
    if not is_carved_basin_interface(interface):
        return False
    if interface.interface_class != INTERFACE_BOWL_UNDER_DECK:
        return False
    return (interface.above_grade_area_fraction
            <= BOWL_MAX_ABOVE_GRADE_AREA_FRACTION)


@dataclass(frozen=True)
class BelowGradeRegion:
    """One connected BELOW-GRADE REGION of a pack's placement population
    (spec ``docs/specs/basin-region-footprint-spec.md`` §2.1; owner
    ruling 2026-08-26 "the cut shape is derived from the objects
    themselves — region-level, not structure-level").

    Region-level means POOL-INDEPENDENT: this is derived from every
    placement's solid triangles directly, so it sees a below-grade wall
    whether or not the pool that wall belongs to classified as anything.
    That is the whole point — LEMD's 358-object T4S mega-pool classifies
    FLAT_CONFIRMED and hides four below-grade shells inside itself.

    * ``polygon`` — the region's EXTERIOR ring, in the classification's
      own metre frame (the module docstring's ``(x, z)`` convention),
      with interior holes filled.
    * ``frame_origin_longitude_latitude`` — that frame's origin, so the
      ring can be converted with
      :func:`frame_polygon_to_longitude_latitude` exactly like every
      other record's geometry.  A second projection is a second region.
    * ``solid_minimum_y_m`` — the THICKNESS-GATED minimum solid
      effective y over the clipped geometry inside the region (LEMD:
      −7.087).  Decal components never witness it, for the same reason
      they never witness a structure floor (``part_has_solid_thickness``).
    * ``object_resources`` — the contributing resources, for LOGGING
      only.  Region membership deliberately does NOT widen a record's
      ``object_resources``: that field drives the ruling-R4 exclusions
      and the rim-flush seating grouping (spec §2.2, out of scope).
    * ``above_grade_area_fraction`` — the openness reading FOUNDING keys
      on (spec ``docs/specs/basin-region-founding-spec.md`` §2.1 item 2):
      how much of the region the pack's OWN geometry stands over,
      measured with the same triangle machinery as the region itself but
      clipped ABOVE ``+GROUND_CONTACT_BAND_HALF_WIDTH_M``.  ``None``
      means UNKNOWN (a pre-v23 cached classification), and unknown
      REFUSES founding out loud — never a silent guess.
    * ``contributor_area_m2_by_resource`` — each contributing resource's
      CLIPPED below-grade area inside this region, sorted.  Measured in
      the same pass for the same reason the coverage fraction is: §2.2's
      founded record needs a TIGHT contributor list, and re-deriving
      those areas in the assembly would be a second scan of the same
      geometry (the instrument-duplication class this module refuses).
    * ``ramp_reach_corridor`` — the region's own ENTRANCE RAMP as a
      polygon in the same frame: the ground its shell covers between the
      admitted ring and the point where that shell meets grade (spec
      ``docs/specs/lemd-basin-trench-ramp-extension-spec.md``
      Amendment 1 §2).  It is ADDITIVE INFORMATION and nothing else —
      ``polygon`` and every reading taken on it are untouched, which is
      the whole point of Amendment 1: the ring is the facility's one
      measurement body (floor value, rim value, pad coverage, R_mesh
      band) and moving it moved all four.  ``None`` means NOT DERIVED
      (the gate is off, or a pre-v25 cached classification).
    """

    polygon: Polygon
    frame_origin_longitude_latitude: tuple[float, float]
    solid_minimum_y_m: float
    object_resources: tuple[str, ...] = ()
    above_grade_area_fraction: float | None = None
    contributor_area_m2_by_resource: tuple[tuple[str, float], ...] = ()
    ramp_reach_corridor: "Polygon | MultiPolygon | None" = None


@dataclass(frozen=True)
class ClassificationResult:
    """The classifier's whole output for one pack (spec section 3.1).

    ``exclusions`` is the ruling-R4 feed for the Phase 2 y-bake: every
    consumed tunnel/bridge object, plus — only when the section 3.4
    split-level adapter is on — every object of a NON-FLAT ground
    interface (split-level structures whose terrain is adapted to them
    join the list exactly like tunnels), as ``(pack_root,
    object_resource)``.  FLAT_CONFIRMED interfaces adapt no terrain and
    are never excluded.  ``refusals`` are bridge-like structures denied
    a terrain feature (amendment A4 — piered viaducts); they stay OUT
    of ``exclusions``."""

    tunnels: list[TunnelStructure]
    bridges: list[BridgeStructure]
    exclusions: list[tuple[str, str]] = field(default_factory=list)
    refusals: list[RefusedStructure] = field(default_factory=list)
    ground_interfaces: list[StructureGroundInterface] = field(
        default_factory=list
    )
    portal_faces: list[PortalFaceStructure] = field(default_factory=list)
    # The section-2.1 below-grade REGIONS (spec basin-region-footprint).
    # DEFAULTED so an old cached/hand-built result reads back as "no
    # regions" rather than raising — the cache VERSION is what retires
    # a stale sidecar (``object_terrain_assembly.
    # _CLASSIFICATION_CACHE_VERSION``), never a missing attribute.
    below_grade_regions: list[BelowGradeRegion] = field(
        default_factory=list
    )

    def terrain_material_resources(self) -> set[str]:
        """Every resource the classifier RECOGNIZED as tunnel / bridge /
        deck / split-level terrain material — the Phase-1 building-pool
        drop set (defect 2026-07-17, EGLL Building36: such structures
        must never chain into a building pad).  Deliberately independent
        of ``exclusions``: the R4 y-bake feed is gated on which terrain
        adapters are ON, while a recognized structure stays out of the
        building pool whichever adapter owns it."""
        resources = {resource for _root, resource in self.exclusions}
        for tunnel in self.tunnels:
            resources.update(tunnel.object_resources)
        for bridge in self.bridges:
            resources.update(bridge.object_resources)
        for interface in self.ground_interfaces:
            if interface.interface_class != INTERFACE_FLAT_CONFIRMED:
                resources.update(interface.object_resources)
        for face in self.portal_faces:
            resources.update(face.object_resources)
        return resources


# ---------------------------------------------------------------------------
# Frame construction and small geometry helpers
# ---------------------------------------------------------------------------

class _FrameTriangle(NamedTuple):
    """One solid triangle projected into the structure metre frame.

    ``corners`` are three ``(x, effective_y, z)`` points; ``height_m`` is
    the mean effective height (the stable per-face height used for
    binning); ``hardness`` is the loader's per-triangle collision state
    (``""`` / ``"hard"`` / ``"hard_deck"``).  The ``(x, z)`` horizontal
    projection polygon is no longer carried per triangle — footprint
    unions build their shapely polygons in bulk from the corners
    (performance round, 2026-07-10) — and the frame's vectorized twin of
    this record lives in the :class:`_StructureFrame` triangle arrays.
    A NamedTuple, not a dataclass: structures materialize millions of
    these and tuple construction is several times cheaper."""

    corners: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    centroid_xz: tuple[float, float]
    height_m: float
    area_m2: float
    horizontality: float
    hardness: str
    resource_path: str

    @property
    def is_hard(self) -> bool:
        """Drivable-hard in the amendment-A4 sense: ATTR_hard_deck OR plain
        ATTR_hard."""
        return self.hardness in ("hard", "hard_deck")


# Hardness is carried through the vectorized paths as small integer codes
# (indexing this tuple decodes them); code order makes ``code > 0`` the
# vectorized twin of :attr:`_FrameTriangle.is_hard`.
_HARDNESS_BY_CODE = ("", "hard", "hard_deck")
_CODE_BY_HARDNESS = {"": 0, "hard": 1, "hard_deck": 2}


class _StructureFrame:
    """One pool's projected geometry: the usable frame triangles, the
    ground-contact evidence, and the frame origin.

    ``grounded_vertices_xz`` holds the frame ``(x, z, resource_path)``
    of every solid vertex whose effective height is at or below
    :data:`GROUND_CONTACT_TOLERANCE_M` — collected from the RAW vertex
    list, not the triangle list, because a perfectly vertical
    pier/abutment face collapses to a zero-area horizontal footprint and
    is dropped from ``triangles``, yet its ground contact is exactly what
    the per-end abutment test must see.

    ``vertex_columns`` groups every solid vertex onto a
    :data:`WALL_COLUMN_GRID_M` horizontal grid: grid key → ``(minimum
    effective y, maximum effective y, contributing resource paths)``.
    Feature C's wall-column extraction reads facade bases from it — again
    from the raw vertex list, because facades ARE the vertical faces the
    triangle list drops.

    The kept triangles live primarily as parallel NUMPY ARRAYS (one row
    per triangle, placement order preserved): corner coordinates,
    centroid, mean height, area, horizontality, hardness code and an
    index into ``triangle_resource_paths``.  The classifier's hot passes
    (sector statistics, per-resource areas, footprint classes) read the
    arrays; :attr:`triangles` materializes the equivalent
    :class:`_FrameTriangle` list LAZILY for the record-building paths
    that walk small frames (tunnel/bridge component frames) — a KBNA
    mega-pool frame holds 6.2 million triangles and must never pay for
    six million Python objects it will not read.

    ``solid_floor_witness_y_m`` is ``minimum_effective_height_m`` with the
    DECAL EXCLUSION applied (spec ``docs/specs/
    tunnel-trench-law-and-basin-floor-spec.md`` §2.1): a pooled part whose
    own authored bbox height is below
    :data:`config.MIN_SOLID_PART_THICKNESS_M` has no vertical extent, so
    it is a ground decal and cannot be a structure's floor.  It is the
    BASIN FLOOR LAW's key and nothing else's —
    ``minimum_effective_height_m`` keeps every part, so the ground-contact
    and cosmetic-bridge tests read exactly what they always read."""

    __slots__ = (
        "origin_latitude",
        "origin_longitude",
        "minimum_effective_height_m",
        "solid_floor_witness_y_m",
        "grounded_vertices_xz",
        "vertex_columns",
        "triangle_count",
        "triangle_corner_x_m",
        "triangle_corner_y_m",
        "triangle_corner_z_m",
        "triangle_centroid_x_m",
        "triangle_centroid_z_m",
        "triangle_height_m",
        "triangle_area_m2",
        "triangle_horizontality",
        "triangle_hardness_codes",
        "triangle_resource_indices",
        "triangle_resource_paths",
        "_materialized_triangles",
    )

    def __init__(
        self,
        *,
        origin_latitude: float,
        origin_longitude: float,
        minimum_effective_height_m: float,
        solid_floor_witness_y_m: float,
        grounded_vertices_xz: list[tuple[float, float, str]],
        vertex_columns: dict[
            tuple[int, int], tuple[float, float, frozenset[str]]
        ],
        triangle_corner_x_m,
        triangle_corner_y_m,
        triangle_corner_z_m,
        triangle_centroid_x_m,
        triangle_centroid_z_m,
        triangle_height_m,
        triangle_area_m2,
        triangle_horizontality,
        triangle_hardness_codes,
        triangle_resource_indices,
        triangle_resource_paths: list[str],
    ) -> None:
        self.origin_latitude = origin_latitude
        self.origin_longitude = origin_longitude
        self.minimum_effective_height_m = minimum_effective_height_m
        self.solid_floor_witness_y_m = solid_floor_witness_y_m
        self.grounded_vertices_xz = grounded_vertices_xz
        self.vertex_columns = vertex_columns
        self.triangle_corner_x_m = triangle_corner_x_m
        self.triangle_corner_y_m = triangle_corner_y_m
        self.triangle_corner_z_m = triangle_corner_z_m
        self.triangle_centroid_x_m = triangle_centroid_x_m
        self.triangle_centroid_z_m = triangle_centroid_z_m
        self.triangle_height_m = triangle_height_m
        self.triangle_area_m2 = triangle_area_m2
        self.triangle_horizontality = triangle_horizontality
        self.triangle_hardness_codes = triangle_hardness_codes
        self.triangle_resource_indices = triangle_resource_indices
        self.triangle_resource_paths = triangle_resource_paths
        self.triangle_count = int(len(triangle_height_m))
        self._materialized_triangles: list[_FrameTriangle] | None = None

    @property
    def triangles(self) -> list[_FrameTriangle]:
        """The frame triangles as :class:`_FrameTriangle` records,
        materialized on first access (see the class docstring)."""
        if self._materialized_triangles is None:
            corner_rows = numpy.stack(
                [
                    self.triangle_corner_x_m,
                    self.triangle_corner_y_m,
                    self.triangle_corner_z_m,
                ],
                axis=2,
            ).tolist()
            resource_paths = self.triangle_resource_paths
            materialized = [
                _FrameTriangle(
                    corners=(
                        tuple(corners[0]),
                        tuple(corners[1]),
                        tuple(corners[2]),
                    ),
                    centroid_xz=(centroid_x, centroid_z),
                    height_m=height,
                    area_m2=area,
                    horizontality=horizontality,
                    hardness=_HARDNESS_BY_CODE[hardness_code],
                    resource_path=resource_paths[resource_index],
                )
                for (
                    corners,
                    centroid_x,
                    centroid_z,
                    height,
                    area,
                    horizontality,
                    hardness_code,
                    resource_index,
                ) in zip(
                    corner_rows,
                    self.triangle_centroid_x_m.tolist(),
                    self.triangle_centroid_z_m.tolist(),
                    self.triangle_height_m.tolist(),
                    self.triangle_area_m2.tolist(),
                    self.triangle_horizontality.tolist(),
                    self.triangle_hardness_codes.tolist(),
                    self.triangle_resource_indices.tolist(),
                )
            ]
            self._materialized_triangles = materialized
        return self._materialized_triangles

    def triangle_corner_coordinates_xz(self, selection=None):
        """Corner ``(x, z)`` coordinates as an ``(n, 3, 2)`` array —
        the bulk-polygon-creation input — optionally restricted to the
        boolean mask or index array ``selection``."""
        corner_x = self.triangle_corner_x_m
        corner_z = self.triangle_corner_z_m
        if selection is not None:
            corner_x = corner_x[selection]
            corner_z = corner_z[selection]
        return numpy.stack([corner_x, corner_z], axis=2)


def _placements_mean_origin(
    placements: Sequence[ObjectPlacement],
) -> tuple[float, float]:
    origin_latitude = sum(
        placement.latitude for placement in placements
    ) / len(placements)
    origin_longitude = sum(
        placement.longitude for placement in placements
    ) / len(placements)
    return origin_latitude, origin_longitude


def _composed_placement_transform(
    placement: ObjectPlacement,
    origin_latitude: float,
    origin_longitude: float,
) -> tuple[float, float, float, float, float]:
    """The placement-local → structure-frame map as six hoisted constants.

    ``obj8_reader.local_offset_to_lonlat`` followed by
    ``obj8_reader.lonlat_to_local_offset`` (heading 0 at the origin) is
    the composition of two linear maps; substituting one into the other
    (algebraically exact, nothing dropped) gives::

        frame_x = base_x + ratio * (x * cosine - z * sine)
        frame_z = base_z + (x * sine + z * cosine)

    with ``base_x = (placement_longitude - origin_longitude) *
    METRES_PER_DEGREE_LATITUDE * cos(origin_latitude)``, ``ratio =
    cos(origin_latitude) / cos(placement_latitude)`` (the two
    metres-per-degree-longitude scales), ``base_z = (origin_latitude -
    placement_latitude) * METRES_PER_DEGREE_LATITUDE`` and sine/cosine of
    the placement heading.  Returns ``(base_x, base_z, ratio, sine,
    cosine)``."""
    heading = math.radians(placement.heading_degrees)
    heading_sine, heading_cosine = math.sin(heading), math.cos(heading)
    metres_per_degree = obj8_reader.METRES_PER_DEGREE_LATITUDE
    origin_latitude_cosine = math.cos(math.radians(origin_latitude))
    base_x = (
        (placement.longitude - origin_longitude)
        * metres_per_degree
        * origin_latitude_cosine
    )
    base_z = (origin_latitude - placement.latitude) * metres_per_degree
    ratio = origin_latitude_cosine / math.cos(
        math.radians(placement.latitude)
    )
    return base_x, base_z, ratio, heading_sine, heading_cosine


def _affine_matrix_for_placement(
    placement: ObjectPlacement,
    origin_latitude: float,
    origin_longitude: float,
) -> list[float]:
    """The :func:`_composed_placement_transform` map in
    ``shapely.affinity.affine_transform`` order ``[a, b, d, e, xoff,
    yoff]`` (``x' = a*x + b*y + xoff``; the shapely ``y`` axis carries
    the frame ``z``)."""
    base_x, base_z, ratio, heading_sine, heading_cosine = (
        _composed_placement_transform(
            placement, origin_latitude, origin_longitude
        )
    )
    return [
        ratio * heading_cosine,
        -ratio * heading_sine,
        heading_sine,
        heading_cosine,
        base_x,
        base_z,
    ]


# Face classes for the per-resource local footprint-union cache (the
# GEOS-union hoist: union once per resource in its own authored frame,
# affine-transform per placement).  Heading rotation is about the
# vertical axis and the longitude-scale ratio is within parts per
# million of 1, so hardness, near-horizontality and the height classes
# (shifted by the placement's above-ground offset) are all decidable in
# the AUTHORED frame.
_FACE_CLASS_ALL = "all"
_FACE_CLASS_HARD_NEAR_HORIZONTAL = "hard_near_horizontal"
_FACE_CLASS_BELOW_GRADE_HARD_NEAR_HORIZONTAL = (
    "below_grade_hard_near_horizontal"
)
_FACE_CLASS_AT_GRADE = "at_grade"
# Which classes shift with the placement's above-ground offset (their
# cache key carries it; the others are placement-independent).
_HEIGHT_DEPENDENT_FACE_CLASSES = frozenset(
    {_FACE_CLASS_BELOW_GRADE_HARD_NEAR_HORIZONTAL, _FACE_CLASS_AT_GRADE}
)


class _ResourceTriangleBasis(NamedTuple):
    """Resource-intrinsic geometry arrays (authored frame), built once
    per resource per classification call."""

    vertices: numpy.ndarray               # (vertex_count, 3) float64
    triangle_vertex_indices: numpy.ndarray  # (triangle_count, 3)
    hardness_codes: numpy.ndarray         # (triangle_count,) uint8
    used_vertex_indices: numpy.ndarray    # unique solid vertices, ascending


class _ResourceFaceTable(NamedTuple):
    """Per-triangle face measurements in the AUTHORED frame, for the
    local footprint-union classes (placement-independent up to the
    above-ground height shift)."""

    keep_mask: numpy.ndarray          # non-degenerate solid faces
    hard_mask: numpy.ndarray
    near_horizontal_mask: numpy.ndarray
    mean_local_y: numpy.ndarray
    corner_coordinates_xz: numpy.ndarray  # (triangle_count, 3, 2)


class _ResourceGeometryCache:
    """Per-classification-call cache of resource-intrinsic work.

    Everything here depends only on an ``ObjectGeometry``, never on a
    placement or a pool, so it is computed once per resource and reused
    across every pool, component frame and evidence frame of the call:

    * ``evidence`` — the pool pre-screen flags (pure Python, no arrays,
      so skipped pools never pay for array construction);
    * ``basis`` — vertex/triangle numpy arrays for the vectorized frame
      build;
    * ``local_class_union`` — the footprint union of a face class in the
      resource's own authored frame (see the ``_FACE_CLASS_*``
      constants), the fix that collapses the GEOS union count from one
      union per placed triangle to one per resource."""

    __slots__ = (
        "geometry_by_resource",
        "_evidence",
        "_basis",
        "_face_tables",
        "_local_class_unions",
        "_solid_components",
        "_below_grade_unions",
        "_above_grade_unions",
        "_local_xz_bounds",
    )

    def __init__(
        self, geometry_by_resource: dict[str, ObjectGeometry]
    ) -> None:
        self.geometry_by_resource = geometry_by_resource
        self._evidence: dict[str, tuple[bool, bool, float, float]] = {}
        self._basis: dict[str, _ResourceTriangleBasis | None] = {}
        self._face_tables: dict[str, _ResourceFaceTable | None] = {}
        self._local_class_unions: dict[tuple, object] = {}
        self._solid_components: dict[str, list] = {}
        self._below_grade_unions: dict[tuple, object] = {}
        self._above_grade_unions: dict[tuple, object] = {}
        self._local_xz_bounds: dict[str, tuple | None] = {}

    def evidence(
        self, resource_path: str
    ) -> tuple[bool, bool, float, float]:
        """``(has_hard_triangle, has_solid_geometry, minimum_vertex_y,
        maximum_vertex_y)`` for the pool pre-screen.  The vertical bounds
        cover ALL authored vertices (a superset of the solid ones), so
        the pre-screen can only err towards classifying a pool."""
        cached = self._evidence.get(resource_path)
        if cached is not None:
            return cached
        geometry = self.geometry_by_resource.get(resource_path)
        if geometry is None or not geometry.solid_triangles:
            flags = (False, False, 0.0, 0.0)
        else:
            has_hard = any(geometry.solid_triangle_hardness)
            if geometry.vertices:
                minimum_y = min(vertex[1] for vertex in geometry.vertices)
                maximum_y = max(vertex[1] for vertex in geometry.vertices)
            else:
                minimum_y = maximum_y = 0.0
            flags = (has_hard, True, minimum_y, maximum_y)
        self._evidence[resource_path] = flags
        return flags

    def basis(self, resource_path: str) -> _ResourceTriangleBasis | None:
        cached = self._basis.get(resource_path, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return cached
        geometry = self.geometry_by_resource.get(resource_path)
        if geometry is None or not geometry.solid_triangles:
            self._basis[resource_path] = None
            return None
        vertices = numpy.asarray(geometry.vertices, dtype=numpy.float64)
        triangle_vertex_indices = numpy.asarray(
            geometry.solid_triangles, dtype=numpy.intp
        )
        hardness_codes = numpy.zeros(
            len(geometry.solid_triangles), dtype=numpy.uint8
        )
        for index, state in enumerate(geometry.solid_triangle_hardness):
            if index >= hardness_codes.size:
                break
            hardness_codes[index] = _CODE_BY_HARDNESS.get(state, 0)
        basis = _ResourceTriangleBasis(
            vertices=vertices,
            triangle_vertex_indices=triangle_vertex_indices,
            hardness_codes=hardness_codes,
            used_vertex_indices=numpy.unique(triangle_vertex_indices),
        )
        self._basis[resource_path] = basis
        return basis

    def face_table(self, resource_path: str) -> _ResourceFaceTable | None:
        cached = self._face_tables.get(resource_path, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return cached
        basis = self.basis(resource_path)
        if basis is None:
            self._face_tables[resource_path] = None
            return None
        corners = basis.vertices[basis.triangle_vertex_indices]
        edge_one = corners[:, 1, :] - corners[:, 0, :]
        edge_two = corners[:, 2, :] - corners[:, 0, :]
        normal_x = (
            edge_one[:, 1] * edge_two[:, 2]
            - edge_one[:, 2] * edge_two[:, 1]
        )
        normal_y = (
            edge_one[:, 2] * edge_two[:, 0]
            - edge_one[:, 0] * edge_two[:, 2]
        )
        normal_z = (
            edge_one[:, 0] * edge_two[:, 1]
            - edge_one[:, 1] * edge_two[:, 0]
        )
        normal_length = numpy.sqrt(
            normal_x * normal_x
            + normal_y * normal_y
            + normal_z * normal_z
        )
        # Degenerate faces: zero 3D area, or a vanishing horizontal
        # projection (a perfectly vertical face — its footprint polygon
        # would be empty; ``normal_y`` IS the horizontal cross product).
        keep_mask = (normal_length > 0.0) & (normal_y != 0.0)
        with numpy.errstate(invalid="ignore", divide="ignore"):
            horizontality = numpy.where(
                normal_length > 0.0,
                numpy.abs(normal_y) / normal_length,
                0.0,
            )
        table = _ResourceFaceTable(
            keep_mask=keep_mask,
            hard_mask=basis.hardness_codes > 0,
            near_horizontal_mask=(
                horizontality >= NEAR_HORIZONTAL_NORMAL_Y_MIN
            ),
            mean_local_y=(
                corners[:, 0, 1] + corners[:, 1, 1] + corners[:, 2, 1]
            )
            / 3.0,
            corner_coordinates_xz=corners[:, :, 0::2],
        )
        self._face_tables[resource_path] = table
        return table

    def local_class_union(
        self,
        resource_path: str,
        face_class: str,
        above_ground_level_metres: float,
    ):
        """Footprint union of the face class in the resource's authored
        frame, or ``None`` when no face qualifies."""
        height_offset = (
            above_ground_level_metres
            if face_class in _HEIGHT_DEPENDENT_FACE_CLASSES
            else 0.0
        )
        key = (resource_path, face_class, height_offset)
        cached = self._local_class_unions.get(key, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return cached
        union = self._compute_local_class_union(
            resource_path, face_class, height_offset
        )
        self._local_class_unions[key] = union
        return union

    def _compute_local_class_union(
        self, resource_path: str, face_class: str, height_offset: float
    ):
        if face_class in (
            _FACE_CLASS_HARD_NEAR_HORIZONTAL,
            _FACE_CLASS_BELOW_GRADE_HARD_NEAR_HORIZONTAL,
        ) and not self.evidence(resource_path)[0]:
            return None  # no hard triangles — skip the array work
        table = self.face_table(resource_path)
        if table is None:
            return None
        if face_class == _FACE_CLASS_ALL:
            mask = table.keep_mask
        elif face_class == _FACE_CLASS_HARD_NEAR_HORIZONTAL:
            mask = (
                table.keep_mask
                & table.hard_mask
                & table.near_horizontal_mask
            )
        elif face_class == _FACE_CLASS_BELOW_GRADE_HARD_NEAR_HORIZONTAL:
            mask = (
                table.keep_mask
                & table.hard_mask
                & table.near_horizontal_mask
                & (
                    table.mean_local_y
                    <= -TUNNEL_MIN_BODY_DEPTH_M - height_offset
                )
            )
        elif face_class == _FACE_CLASS_AT_GRADE:
            mask = table.keep_mask & (
                table.mean_local_y
                >= -TUNNEL_ROOF_TOP_TOLERANCE_M - height_offset
            )
        else:  # pragma: no cover - programming error, not data
            raise ValueError(f"unknown face class {face_class!r}")
        if not mask.any():
            return None
        try:
            union = shapely.union_all(
                shapely.polygons(table.corner_coordinates_xz[mask])
            )
            if not union.is_valid:
                union = union.buffer(0)
        except (ValueError, _GEOS_EXCEPTION):
            return None
        return None if union.is_empty else union

    # ── the below-grade REGION instrument's per-resource half ────────
    # (spec docs/specs/basin-region-footprint-spec.md §2.1)

    def solid_components(self, resource_path: str) -> list:
        """The resource's SOLID CONNECTED COMPONENTS as ``(triangles,
        minimum_authored_y, maximum_authored_y)``, in the authored frame.

        Connectivity is ``obj8_partition.weld_parts`` — THE repo's one
        spelling of "connected solid component" (position-welded, so an
        exporter's per-seam duplicate vertices do not shatter a wall).
        Only ever called for a resource that survived the region
        pre-scan, so the union-find never runs on a pack's at-grade bulk.
        """
        cached = self._solid_components.get(resource_path)
        if cached is not None:
            return cached
        geometry = self.geometry_by_resource.get(resource_path)
        if geometry is None or not geometry.solid_triangles:
            self._solid_components[resource_path] = []
            return []
        from .obj8_partition import weld_parts

        vertices = geometry.vertices
        components = []
        for triangles in weld_parts(vertices, geometry.solid_triangles):
            heights = [
                vertices[index][1]
                for triangle in triangles
                for index in triangle
            ]
            if not heights:
                continue
            components.append((triangles, min(heights), max(heights)))
        self._solid_components[resource_path] = components
        return components

    def below_grade_local_union(
        self, resource_path: str, plane_local_y: float
    ):
        """The resource's below-``plane_local_y`` footprint in its own
        AUTHORED frame, as ``(union polygon, minimum authored y)``, or
        ``None`` when nothing qualifies.

        TRIANGLES ARE CLIPPED, NEVER KEPT WHOLE (spec §2.1, explicit): a
        long ramp panel running +1 → −6 contributes only the part of
        itself that is actually below the plane, so its at-grade half
        never joins the cut.  A min-vertex test on whole triangles would
        claim the whole panel.

        DECAL COMPONENTS ARE EXCLUDED FIRST — a connected solid component
        whose own vertical extent is under
        ``config.MIN_SOLID_PART_THICKNESS_M`` has no vertical extent of
        its own and is ground paint (:func:`part_has_solid_thickness`,
        the ONE spelling).  Measured at LEMD: without the gate the two
        ``AESlite-LEMD-VOR-15-T4S-*.obj`` −50 m quads take the union to
        2.08 M m².
        """
        key = (resource_path, plane_local_y)
        cached = self._below_grade_unions.get(key, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return cached
        result = self._compute_below_grade_local_union(
            resource_path, plane_local_y
        )
        self._below_grade_unions[key] = result
        return result

    def _compute_below_grade_local_union(
        self, resource_path: str, plane_local_y: float
    ):
        geometry = self.geometry_by_resource.get(resource_path)
        if geometry is None or not geometry.solid_triangles:
            return None
        vertices = geometry.vertices
        rings_by_length: dict[int, list] = {}
        minimum_y = math.inf
        for triangles, component_minimum_y, component_maximum_y in (
            self.solid_components(resource_path)
        ):
            if component_minimum_y > plane_local_y:
                continue
            if not part_has_solid_thickness(
                component_minimum_y, component_maximum_y
            ):
                continue
            if component_minimum_y < minimum_y:
                minimum_y = component_minimum_y
            for triangle in triangles:
                ring = _clip_triangle_below_plane(
                    (
                        vertices[triangle[0]],
                        vertices[triangle[1]],
                        vertices[triangle[2]],
                    ),
                    plane_local_y,
                )
                if ring is not None:
                    rings_by_length.setdefault(len(ring), []).append(ring)
        if not rings_by_length or minimum_y is math.inf:
            return None
        parts = []
        for rings in rings_by_length.values():
            try:
                part = shapely.union_all(
                    shapely.polygons(
                        numpy.asarray(rings, dtype=numpy.float64)
                    )
                )
            except (ValueError, _GEOS_EXCEPTION):
                continue
            part = _repaired_area_polygon(part)
            if part is not None:
                parts.append(part)
        if not parts:
            return None
        union = _union_all_repairing(parts)
        if union is None:
            return None
        return union, float(minimum_y)

    def local_xz_bounds(self, resource_path: str):
        """``(min_x, min_z, max_x, max_z)`` over the resource's SOLID
        vertices in its own authored frame, or ``None``.  Purely a
        pre-filter datum (see :func:`_placement_frame_bounds`)."""
        cached = self._local_xz_bounds.get(resource_path, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return cached
        basis = self.basis(resource_path)
        bounds = None
        if basis is not None and basis.used_vertex_indices.size:
            used = basis.vertices[basis.used_vertex_indices]
            bounds = (
                float(used[:, 0].min()),
                float(used[:, 2].min()),
                float(used[:, 0].max()),
                float(used[:, 2].max()),
            )
        self._local_xz_bounds[resource_path] = bounds
        return bounds

    def above_grade_local_union(
        self, resource_path: str, plane_local_y: float
    ):
        """The resource's ABOVE-``plane_local_y`` footprint in its own
        AUTHORED frame, or ``None`` when nothing qualifies.

        THE MIRROR of :meth:`below_grade_local_union`, deliberately
        clause for clause (spec ``basin-region-founding-spec.md`` §2.1
        item 2: "the SAME triangle machinery as the region itself...
        decal gate identical"): the same welded solid components, the
        same ``part_has_solid_thickness`` decal exclusion, the same
        Sutherland-Hodgman clip — only the half-space is flipped, to
        ``y >= plane_local_y``.  Two different instruments reading
        "what stands over the pit" and "what the pit is" is exactly the
        two-instruments-one-population defect class.

        The caller's plane is ``+GROUND_CONTACT_BAND_HALF_WIDTH_M``
        (less the placement's AGL offset), the module's ONE spelling of
        "clear of the ground band" — the same plane
        ``is_open_pit_interface``'s above-grade fraction is measured
        against, so the region-level openness test and the
        structure-level one ask the same question.
        """
        key = (resource_path, plane_local_y)
        cached = self._above_grade_unions.get(key, _CACHE_MISS)
        if cached is not _CACHE_MISS:
            return cached
        result = self._compute_above_grade_local_union(
            resource_path, plane_local_y
        )
        self._above_grade_unions[key] = result
        return result

    def _compute_above_grade_local_union(
        self, resource_path: str, plane_local_y: float
    ):
        geometry = self.geometry_by_resource.get(resource_path)
        if geometry is None or not geometry.solid_triangles:
            return None
        vertices = geometry.vertices
        rings_by_length: dict[int, list] = {}
        for triangles, component_minimum_y, component_maximum_y in (
            self.solid_components(resource_path)
        ):
            if component_maximum_y < plane_local_y:
                continue
            if not part_has_solid_thickness(
                component_minimum_y, component_maximum_y
            ):
                continue
            for triangle in triangles:
                ring = _clip_triangle_above_plane(
                    (
                        vertices[triangle[0]],
                        vertices[triangle[1]],
                        vertices[triangle[2]],
                    ),
                    plane_local_y,
                )
                if ring is not None:
                    rings_by_length.setdefault(len(ring), []).append(ring)
        if not rings_by_length:
            return None
        parts = []
        for rings in rings_by_length.values():
            try:
                part = shapely.union_all(
                    shapely.polygons(
                        numpy.asarray(rings, dtype=numpy.float64)
                    )
                )
            except (ValueError, _GEOS_EXCEPTION):
                continue
            part = _repaired_area_polygon(part)
            if part is not None:
                parts.append(part)
        if not parts:
            return None
        return _union_all_repairing(parts)


# Distinguishes "cached None" from "not yet computed" in the cache maps.
_CACHE_MISS = object()


def _repaired_area_polygon(geometry):
    """``geometry`` made VALID and non-degenerate, or ``None``.

    The module's standard repair (``buffer(0)``, as in
    :func:`_close_and_reduce_union`), plus the drop of ZERO-AREA results.
    Both matter to the region union: a wall-only resource clips to
    polygons with no horizontal extent (LEMD's ``Terminal4sBlue-LEMD35``
    is exactly this — 0 m² of pure vertical faces), and feeding those
    into ``union_all`` beside real rings is what produced the measured
    ``TopologyException: side location conflict`` at LEMD.  They also
    contribute nothing by construction, so dropping them changes no
    footprint.
    """
    if geometry is None or geometry.is_empty:
        return None
    try:
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty or geometry.area <= 0.0:
            return None
        if geometry.geom_type not in ("Polygon", "MultiPolygon"):
            return None
    except (ValueError, _GEOS_EXCEPTION):
        return None
    return geometry


def _union_all_repairing(polygons):
    """``shapely.union_all`` that cannot fail SILENTLY.

    GEOS raises ``TopologyException`` on a set whose members are
    individually valid but jointly degenerate, and the region derivation
    used to catch that and return "no regions" — which is the silent-zero
    failure mode this project treats as a defect in its own right
    (measured at LEMD 2026-08-26: the whole T4S ring vanished, and the
    only trace was an absent log line).  So the bulk union is tried
    first, and on a topology failure the parts are accumulated ONE AT A
    TIME with a repair between, which is slower and cannot hit the joint
    degeneracy.  A part that still refuses is DROPPED BY NAME at
    verbosity 1, never in silence.
    """
    if not polygons:
        return None
    try:
        return _repaired_area_polygon(shapely.union_all(polygons))
    except (ValueError, _GEOS_EXCEPTION):
        pass
    _vprint(
        1,
        "   [object-terrain] below-grade region union: the bulk union "
        f"refused {len(polygons)} part(s) (GEOS topology) — accumulating "
        "them one at a time with a repair between",
    )
    accumulated = None
    dropped = 0
    for polygon in polygons:
        repaired = _repaired_area_polygon(polygon)
        if repaired is None:
            continue
        if accumulated is None:
            accumulated = repaired
            continue
        try:
            accumulated = _repaired_area_polygon(
                shapely.union_all([accumulated, repaired])
            )
        except (ValueError, _GEOS_EXCEPTION):
            dropped += 1
    if dropped:
        _vprint(
            1,
            f"   [object-terrain] below-grade region union: {dropped} "
            "part(s) could not be unioned even singly and are DROPPED — "
            "the region is that much smaller than the objects describe",
        )
    return accumulated


def _clip_triangle_below_plane(
    corners: Sequence[tuple[float, float, float]],
    plane_y: float,
) -> list[tuple[float, float]] | None:
    """Sutherland-Hodgman clip of one triangle against the half-space
    ``y <= plane_y``, returned as the sub-polygon's ``(x, z)`` ring (3 or
    4 points), or ``None`` when the triangle is wholly above the plane
    or its below-part degenerates.

    THE CLIP, NOT A TEST (spec §2.1): keeping a whole triangle on a
    min-vertex test would hand a ramp panel's at-grade half to the cut.
    Purely local arithmetic — no shapely, because this runs once per
    below-grade triangle of every qualifying resource.
    """
    ring: list[tuple[float, float]] = []
    for index in range(3):
        current = corners[index]
        following = corners[(index + 1) % 3]
        current_inside = current[1] <= plane_y
        following_inside = following[1] <= plane_y
        if current_inside:
            ring.append((current[0], current[2]))
        if current_inside != following_inside:
            span = following[1] - current[1]
            if span == 0.0:  # pragma: no cover - inside flags would agree
                continue
            fraction = (plane_y - current[1]) / span
            ring.append((
                current[0] + fraction * (following[0] - current[0]),
                current[2] + fraction * (following[2] - current[2]),
            ))
    return ring if len(ring) >= 3 else None


def _clip_triangle_above_plane(
    corners: Sequence[tuple[float, float, float]],
    plane_y: float,
) -> list[tuple[float, float]] | None:
    """:func:`_clip_triangle_below_plane` with the half-space flipped to
    ``y >= plane_y`` — the openness half of the region instrument (spec
    ``basin-region-founding-spec.md`` §2.1 item 2).

    Same reason for clipping rather than testing: a ramp panel running
    −6 → +4 stands over the pit only where it is actually above the
    ground band, and a whole-triangle test would report the pit covered
    by its own access ramp.
    """
    ring: list[tuple[float, float]] = []
    for index in range(3):
        current = corners[index]
        following = corners[(index + 1) % 3]
        current_inside = current[1] >= plane_y
        following_inside = following[1] >= plane_y
        if current_inside:
            ring.append((current[0], current[2]))
        if current_inside != following_inside:
            span = following[1] - current[1]
            if span == 0.0:  # pragma: no cover - inside flags would agree
                continue
            fraction = (plane_y - current[1]) / span
            ring.append((
                current[0] + fraction * (following[0] - current[0]),
                current[2] + fraction * (following[2] - current[2]),
            ))
    return ring if len(ring) >= 3 else None


def _class_footprints_by_resource(
    placements: Sequence[ObjectPlacement],
    origin_latitude: float,
    origin_longitude: float,
    cache: _ResourceGeometryCache,
    face_class: str,
    *,
    full_footprint_resources: frozenset | set = frozenset(),
    restrict_resources: set | None = None,
) -> dict[str, object]:
    """Frame-space footprint union of a face class, per resource — the
    cached replacement for unioning every placed triangle: each
    resource's local class union is affine-transformed per placement and
    the (few) per-placement polygons are unioned.  Resources with no
    qualifying face are absent, exactly like the union-per-triangle
    predecessor.  ``full_footprint_resources`` widens the class to ALL
    faces for the named resources (the AGL tunnel seeds, whose whole
    footprint seeds a component)."""
    transformed_by_resource: dict[str, list] = {}
    for placement in placements:
        resource = placement.resource_path
        if (
            restrict_resources is not None
            and resource not in restrict_resources
        ):
            continue
        placement_face_class = (
            _FACE_CLASS_ALL
            if resource in full_footprint_resources
            else face_class
        )
        local_union = cache.local_class_union(
            resource,
            placement_face_class,
            placement.above_ground_level_metres,
        )
        if local_union is None:
            continue
        try:
            transformed = shapely_affinity.affine_transform(
                local_union,
                _affine_matrix_for_placement(
                    placement, origin_latitude, origin_longitude
                ),
            )
        except (ValueError, _GEOS_EXCEPTION):
            continue
        transformed_by_resource.setdefault(resource, []).append(transformed)
    footprints: dict[str, object] = {}
    for resource, parts in transformed_by_resource.items():
        try:
            union = parts[0] if len(parts) == 1 else shapely.union_all(parts)
            if not union.is_valid:
                union = union.buffer(0)
        except (ValueError, _GEOS_EXCEPTION):
            continue
        if not union.is_empty:
            footprints[resource] = union
    return footprints


def _build_structure_frame(
    placements: Sequence[ObjectPlacement],
    geometry_by_resource: dict[str, ObjectGeometry],
    cache: _ResourceGeometryCache | None = None,
) -> _StructureFrame:
    """Project every object's solid triangles into the shared structure
    frame, carrying effective height and per-triangle hardness (module
    docstring).

    Each vertex is placed through ITS OWN object's placement to
    longitude/latitude, then into the pool-mean-origin frame — the exact
    ``object_anchor`` pool-frame construction — with ``effective_y =
    above_ground_level_metres + authored_y``.  The two projections are
    applied as their composition (:func:`_composed_placement_transform`,
    algebraically identical, constants hoisted out of the vertex loop)
    over whole per-resource vertex arrays at once.

    Ground-contact evidence (``minimum_effective_height_m`` and
    ``grounded_vertices_xz``) is collected from the raw solid vertex set,
    not the triangle list: a perfectly VERTICAL pier or abutment face
    collapses to a zero-area horizontal footprint and is dropped from the
    triangle list, yet it is exactly the geometry the abutment tests must
    see (see :class:`_StructureFrame`)."""
    if cache is None:
        cache = _ResourceGeometryCache(geometry_by_resource)
    origin_latitude, origin_longitude = _placements_mean_origin(placements)
    grounded_vertices_xz: list[tuple[float, float, str]] = []
    column_accumulator: dict[tuple[int, int], list] = {}
    minimum_effective_height = math.inf
    # A DECAL IS NOT A SOLID (spec §2.1): the FLOOR WITNESS minimum skips
    # every part with no vertical extent of its own.  Tracked beside the
    # full minimum, never instead of it.  The predicate is
    # :func:`part_has_solid_thickness` — the ONE spelling of the notion,
    # shared with the open-pit seed set.
    solid_floor_witness = math.inf
    corner_x_parts: list[numpy.ndarray] = []
    corner_y_parts: list[numpy.ndarray] = []
    corner_z_parts: list[numpy.ndarray] = []
    area_parts: list[numpy.ndarray] = []
    horizontality_parts: list[numpy.ndarray] = []
    hardness_parts: list[numpy.ndarray] = []
    resource_index_parts: list[numpy.ndarray] = []
    resource_paths: list[str] = []
    resource_index_by_path: dict[str, int] = {}
    for placement in placements:
        geometry = geometry_by_resource.get(placement.resource_path)
        if geometry is None or not geometry.solid_triangles:
            continue
        basis = cache.basis(placement.resource_path)
        if basis is None:
            continue
        base_x, base_z, ratio, heading_sine, heading_cosine = (
            _composed_placement_transform(
                placement, origin_latitude, origin_longitude
            )
        )
        vertex_x = basis.vertices[:, 0]
        vertex_y = basis.vertices[:, 1]
        vertex_z = basis.vertices[:, 2]
        frame_x = base_x + ratio * (
            vertex_x * heading_cosine - vertex_z * heading_sine
        )
        frame_z = base_z + (
            vertex_x * heading_sine + vertex_z * heading_cosine
        )
        effective_y = placement.above_ground_level_metres + vertex_y

        used = basis.used_vertex_indices
        used_effective_y = effective_y[used]
        placement_minimum = float(used_effective_y.min())
        if placement_minimum < minimum_effective_height:
            minimum_effective_height = placement_minimum
        # THE FLOOR WITNESS (spec §2.1).  The part's OWN authored bbox
        # height — max_y − min_y over its used vertices.  Below
        # MIN_SOLID_PART_THICKNESS_M the part is a flat ground decal
        # (LEMD's 4-vertex VOR quads at y = −48.244, extent exactly 0.0)
        # and cannot witness a floor.
        if (part_has_solid_thickness(
                placement_minimum, float(used_effective_y.max()))
                and placement_minimum < solid_floor_witness):
            solid_floor_witness = placement_minimum
        grounded = used[used_effective_y <= GROUND_CONTACT_TOLERANCE_M]
        if grounded.size:
            resource = placement.resource_path
            grounded_vertices_xz.extend(
                (x, z, resource)
                for x, z in zip(
                    frame_x[grounded].tolist(), frame_z[grounded].tolist()
                )
            )
        column_grid_x = numpy.rint(
            frame_x[used] / WALL_COLUMN_GRID_M
        ).astype(numpy.int64)
        column_grid_z = numpy.rint(
            frame_z[used] / WALL_COLUMN_GRID_M
        ).astype(numpy.int64)
        packed_keys = column_grid_x * 4294967296 + column_grid_z
        order = numpy.argsort(packed_keys, kind="stable")
        sorted_keys = packed_keys[order]
        group_starts = numpy.flatnonzero(
            numpy.concatenate(
                ([True], sorted_keys[1:] != sorted_keys[:-1])
            )
        )
        sorted_effective_y = used_effective_y[order]
        group_minimum = numpy.minimum.reduceat(
            sorted_effective_y, group_starts
        )
        group_maximum = numpy.maximum.reduceat(
            sorted_effective_y, group_starts
        )
        representatives = order[group_starts]
        for grid_x, grid_z, low, high in zip(
            column_grid_x[representatives].tolist(),
            column_grid_z[representatives].tolist(),
            group_minimum.tolist(),
            group_maximum.tolist(),
        ):
            column = column_accumulator.get((grid_x, grid_z))
            if column is None:
                column_accumulator[(grid_x, grid_z)] = [
                    low,
                    high,
                    {placement.resource_path},
                ]
            else:
                if low < column[0]:
                    column[0] = low
                if high > column[1]:
                    column[1] = high
                column[2].add(placement.resource_path)

        triangle_vertex_indices = basis.triangle_vertex_indices
        corner_x = frame_x[triangle_vertex_indices]
        corner_y = effective_y[triangle_vertex_indices]
        corner_z = frame_z[triangle_vertex_indices]
        edge_one_x = corner_x[:, 1] - corner_x[:, 0]
        edge_one_y = corner_y[:, 1] - corner_y[:, 0]
        edge_one_z = corner_z[:, 1] - corner_z[:, 0]
        edge_two_x = corner_x[:, 2] - corner_x[:, 0]
        edge_two_y = corner_y[:, 2] - corner_y[:, 0]
        edge_two_z = corner_z[:, 2] - corner_z[:, 0]
        normal_x = edge_one_y * edge_two_z - edge_one_z * edge_two_y
        normal_y = edge_one_z * edge_two_x - edge_one_x * edge_two_z
        normal_z = edge_one_x * edge_two_y - edge_one_y * edge_two_x
        normal_length = numpy.sqrt(
            normal_x * normal_x
            + normal_y * normal_y
            + normal_z * normal_z
        )
        # Keep faces with 3D area AND a non-vanishing horizontal
        # projection (``normal_y`` is exactly the horizontal cross
        # product) — the same two drops the per-triangle Polygon path
        # made through GEOS emptiness.
        keep = (normal_length > 0.0) & (normal_y != 0.0)
        if not keep.any():
            continue
        kept = numpy.flatnonzero(keep)
        corner_x_parts.append(corner_x[kept])
        corner_y_parts.append(corner_y[kept])
        corner_z_parts.append(corner_z[kept])
        area_parts.append(0.5 * normal_length[kept])
        horizontality_parts.append(
            numpy.abs(normal_y[kept]) / normal_length[kept]
        )
        hardness_parts.append(basis.hardness_codes[kept])
        resource_index = resource_index_by_path.get(placement.resource_path)
        if resource_index is None:
            resource_index = len(resource_paths)
            resource_index_by_path[placement.resource_path] = resource_index
            resource_paths.append(placement.resource_path)
        resource_index_parts.append(
            numpy.full(kept.size, resource_index, dtype=numpy.int32)
        )
    if minimum_effective_height is math.inf:
        minimum_effective_height = 0.0
    if solid_floor_witness is math.inf:
        # No part with vertical extent anywhere in the pool: there is no
        # solid to witness a floor, and the same 0.0 the full minimum
        # falls back to says exactly that (the basin floor then derives
        # from the deck-face population — spec §2.2).
        solid_floor_witness = 0.0
    if corner_x_parts:
        corner_x_all = numpy.concatenate(corner_x_parts)
        corner_y_all = numpy.concatenate(corner_y_parts)
        corner_z_all = numpy.concatenate(corner_z_parts)
        area_all = numpy.concatenate(area_parts)
        horizontality_all = numpy.concatenate(horizontality_parts)
        hardness_all = numpy.concatenate(hardness_parts)
        resource_index_all = numpy.concatenate(resource_index_parts)
    else:
        corner_x_all = numpy.empty((0, 3))
        corner_y_all = numpy.empty((0, 3))
        corner_z_all = numpy.empty((0, 3))
        area_all = numpy.empty(0)
        horizontality_all = numpy.empty(0)
        hardness_all = numpy.empty(0, dtype=numpy.uint8)
        resource_index_all = numpy.empty(0, dtype=numpy.int32)
    return _StructureFrame(
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
        minimum_effective_height_m=minimum_effective_height,
        solid_floor_witness_y_m=solid_floor_witness,
        grounded_vertices_xz=grounded_vertices_xz,
        vertex_columns={
            key: (values[0], values[1], frozenset(values[2]))
            for key, values in column_accumulator.items()
        },
        triangle_corner_x_m=corner_x_all,
        triangle_corner_y_m=corner_y_all,
        triangle_corner_z_m=corner_z_all,
        triangle_centroid_x_m=(
            corner_x_all[:, 0] + corner_x_all[:, 1] + corner_x_all[:, 2]
        )
        / 3.0,
        triangle_centroid_z_m=(
            corner_z_all[:, 0] + corner_z_all[:, 1] + corner_z_all[:, 2]
        )
        / 3.0,
        triangle_height_m=(
            corner_y_all[:, 0] + corner_y_all[:, 1] + corner_y_all[:, 2]
        )
        / 3.0,
        triangle_area_m2=area_all,
        triangle_horizontality=horizontality_all,
        triangle_hardness_codes=hardness_all,
        triangle_resource_indices=resource_index_all,
        triangle_resource_paths=resource_paths,
    )


def _close_and_reduce_union(
    union,
    close_m: float,
    keep_all_parts: bool,
) -> Polygon | None:
    """Shared tail of the footprint-union builders: morphological close,
    validity repair, and the dominant-polygon reduction (see
    :func:`_union_horizontal` for the ``keep_all_parts`` semantics)."""
    try:
        if close_m > 0.0:
            union = union.buffer(close_m).buffer(-close_m)
        if not union.is_valid:
            union = union.buffer(0)
    except (ValueError, _GEOS_EXCEPTION):
        return None
    if union.is_empty:
        return None
    if keep_all_parts:
        return union if union.geom_type in ("Polygon", "MultiPolygon") else None
    if union.geom_type == "MultiPolygon":
        union = max(union.geoms, key=lambda geometry: geometry.area)
    if union.geom_type != "Polygon":
        return None
    return Polygon(union.exterior)


def _union_horizontal_coordinates(
    corner_coordinates_xz: numpy.ndarray,
    *,
    close_m: float = FOOTPRINT_CLOSE_M,
    keep_all_parts: bool = False,
) -> Polygon | None:
    """Footprint union from an ``(n, 3, 2)`` corner-coordinate array —
    polygons created in bulk on the C side, never one Python ``Polygon``
    per triangle."""
    if len(corner_coordinates_xz) == 0:
        return None
    try:
        union = shapely.union_all(
            shapely.polygons(corner_coordinates_xz)
        )
    except (ValueError, _GEOS_EXCEPTION):
        return None
    return _close_and_reduce_union(union, close_m, keep_all_parts)


def _union_horizontal(
    triangles: Iterable[_FrameTriangle],
    *,
    close_m: float = FOOTPRINT_CLOSE_M,
    keep_all_parts: bool = False,
) -> Polygon | None:
    """Morphologically closed union of the triangles' ``(x, z)`` footprints,
    or ``None`` when empty.

    ``keep_all_parts=False`` (tunnel roof/deck) reduces the result to its
    dominant exterior polygon — one tunnel object welds into one footprint
    and the reduction strips seam noise.  ``keep_all_parts=True`` (a bridge
    deck built from several part objects — KBNA taxiway-L is six) keeps the
    whole union, so a segmented deck is measured across all its parts
    rather than collapsed to the largest single piece."""
    triangle_list = (
        triangles if isinstance(triangles, list) else list(triangles)
    )
    if not triangle_list:
        return None
    corner_coordinates_xz = numpy.empty((len(triangle_list), 3, 2))
    for index, triangle in enumerate(triangle_list):
        first, second, third = triangle.corners
        corner_coordinates_xz[index, 0, 0] = first[0]
        corner_coordinates_xz[index, 0, 1] = first[2]
        corner_coordinates_xz[index, 1, 0] = second[0]
        corner_coordinates_xz[index, 1, 1] = second[2]
        corner_coordinates_xz[index, 2, 0] = third[0]
        corner_coordinates_xz[index, 2, 1] = third[2]
    return _union_horizontal_coordinates(
        corner_coordinates_xz, close_m=close_m, keep_all_parts=keep_all_parts
    )


def _split_polygons(geometry) -> list[Polygon]:
    """Flatten a shapely geometry to its polygon parts above the noise
    area, largest first."""
    if geometry is None or geometry.is_empty:
        return []
    parts = (
        list(geometry.geoms)
        if geometry.geom_type == "MultiPolygon"
        else [geometry]
    )
    kept = [
        part
        for part in parts
        if part.geom_type == "Polygon" and part.area >= MINIMUM_FEATURE_AREA_M2
    ]
    kept.sort(key=lambda part: part.area, reverse=True)
    return kept


def _dominant_height_plane(
    triangles: Sequence[_FrameTriangle],
) -> tuple[float, list[_FrameTriangle]] | None:
    """Cluster faces into :data:`PLANE_HEIGHT_BIN_M` height bins and return
    the area-weighted mean height and members of the largest-area bin."""
    if not triangles:
        return None
    area_by_bin: dict[int, float] = {}
    members_by_bin: dict[int, list[_FrameTriangle]] = {}
    for triangle in triangles:
        bin_key = round(triangle.height_m / PLANE_HEIGHT_BIN_M)
        area_by_bin[bin_key] = area_by_bin.get(bin_key, 0.0) + triangle.area_m2
        members_by_bin.setdefault(bin_key, []).append(triangle)
    dominant_bin = max(area_by_bin, key=lambda key: area_by_bin[key])
    members = members_by_bin[dominant_bin]
    total_area = sum(triangle.area_m2 for triangle in members)
    mean_height = (
        sum(triangle.height_m * triangle.area_m2 for triangle in members)
        / total_area
    )
    return mean_height, members


def frame_polygon_to_longitude_latitude(
    polygon,
    frame_origin_longitude_latitude: tuple[float, float],
):
    """Convert a structure-frame ``(x, z)`` polygon (or MultiPolygon) to
    ``(longitude, latitude)`` for downstream emitters (inverse of the frame
    map)."""
    from shapely.geometry import MultiPolygon

    origin_longitude, origin_latitude = frame_origin_longitude_latitude

    def _convert_ring(coordinates):
        converted = []
        for frame_x, frame_z in coordinates:
            latitude, longitude = obj8_reader.local_offset_to_lonlat(
                origin_latitude, origin_longitude, 0.0, frame_x, frame_z
            )
            converted.append((longitude, latitude))
        return converted

    if polygon.geom_type == "MultiPolygon":
        return MultiPolygon(
            [
                Polygon(_convert_ring(part.exterior.coords))
                for part in polygon.geoms
            ]
        )
    return Polygon(_convert_ring(polygon.exterior.coords))


# ---------------------------------------------------------------------------
# The below-grade REGION instrument (spec docs/specs/
# basin-region-footprint-spec.md §2.1; owner ruling 2026-08-26)
# ---------------------------------------------------------------------------

def below_grade_regions(
    placements: Sequence[ObjectPlacement],
    geometry_by_resource: dict[str, ObjectGeometry],
    *,
    cache: "_ResourceGeometryCache | None" = None,
) -> list[BelowGradeRegion]:
    """The pack's connected BELOW-GRADE REGIONS — pure, pool-independent.

    "We should be able to determine the exact shape needed from the
    objects" (owner 2026-08-26).  The recipe, in full:

    1. stock-library resources are dropped, exactly as
       :func:`classify_object_terrain_features` drops them;
    2. per placement, the grade plane in the resource's AUTHORED frame is
       ``−TRENCH_SPINE_MIN_DEPTH_M − above_ground_level_metres`` (the
       module's effective-height convention: ``effective_y = agl +
       authored_y``).  A resource whose deepest authored vertex is at or
       above that plane contributes nothing and is skipped before ANY
       triangle work — the perf guard, and the reason a pack with no
       below-grade geometry pays essentially zero;
    3. every solid triangle of every non-decal connected component is
       CLIPPED to its below-plane sub-polygon
       (:func:`_clip_triangle_below_plane`); decal components — vertical
       extent under ``config.MIN_SOLID_PART_THICKNESS_M`` — are excluded
       before the clip;
    4. the per-resource authored-frame union is affine-transformed once
       per placement into the classification frame (the same
       union-once-per-resource hoist :func:`_class_footprints_by_resource`
       uses), everything is unioned, morphologically closed at
       :data:`AT_GRADE_FOOTPRINT_CLOSE_M`, split into connected parts and
       reduced to exterior rings (interior holes filled);
    5. parts under :data:`TRENCH_SPINE_MIN_FOOTPRINT_AREA_M2` are dropped;
    6. each surviving region records, IN THE SAME PASS, its contributors'
       clipped areas inside it and its ABOVE-grade coverage fraction —
       the same machinery run against the opposite half-space, clipped
       above ``+GROUND_CONTACT_BAND_HALF_WIDTH_M`` (spec
       ``docs/specs/basin-region-founding-spec.md`` §2.1).  Both feed
       FOUNDING, and both are measured here so no consumer ever scans
       this geometry a second time.

    VALIDATED against the pack's own shipped mesh patch (LEMD T4S,
    2026-08-26): 92.7-93.0 % IoU with the authored 27,612 m² ring across
    depth thresholds 1.5-3.0 m — the recipe is insensitive to the
    threshold, which is what makes ``TRENCH_SPINE_MIN_DEPTH_M`` the right
    constant to reuse rather than a new knob.

    Returns the regions largest-first.  Empty list when nothing is below
    grade — the common case for an ordinary pack.
    """
    placements = [
        placement
        for placement in placements
        if not is_stock_library_resource(placement.resource_path)
    ]
    if not placements:
        return []
    if cache is None:
        cache = _ResourceGeometryCache(geometry_by_resource)
    origin_latitude, origin_longitude = _placements_mean_origin(placements)

    # (transformed frame polygon, minimum effective y, resource path)
    contributions: list[tuple[object, float, str]] = []
    for placement in placements:
        resource_path = placement.resource_path
        _has_hard, has_solid, minimum_vertex_y, _maximum_vertex_y = (
            cache.evidence(resource_path)
        )
        if not has_solid:
            continue
        above_ground = float(placement.above_ground_level_metres)
        plane_local_y = -TRENCH_SPINE_MIN_DEPTH_M - above_ground
        # THE PRE-SCAN (perf guard): the resource's deepest AUTHORED
        # vertex cannot reach the plane, so no triangle of it can.
        if minimum_vertex_y > plane_local_y:
            continue
        local = cache.below_grade_local_union(resource_path, plane_local_y)
        if local is None:
            continue
        local_union, local_minimum_y = local
        try:
            transformed = shapely_affinity.affine_transform(
                local_union,
                _affine_matrix_for_placement(
                    placement, origin_latitude, origin_longitude
                ),
            )
        except (ValueError, _GEOS_EXCEPTION):
            continue
        # REPAIR AT THE CONTRIBUTION, not only at the end: the affine
        # transform carries a resource's own self-touching seams into the
        # shared frame, and one invalid member is enough to make the bulk
        # union of the whole set refuse (LEMD, measured).
        transformed = _repaired_area_polygon(transformed)
        if transformed is None:
            continue
        contributions.append(
            (transformed, above_ground + local_minimum_y, resource_path)
        )
    if not contributions:
        return []

    union = _union_all_repairing(
        [contribution[0] for contribution in contributions]
    )
    if union is None:
        return []
    try:
        union = union.buffer(AT_GRADE_FOOTPRINT_CLOSE_M).buffer(
            -AT_GRADE_FOOTPRINT_CLOSE_M
        )
    except (ValueError, _GEOS_EXCEPTION):
        return []
    union = _repaired_area_polygon(union)
    if union is None:
        return []

    parts = (
        list(union.geoms)
        if union.geom_type == "MultiPolygon"
        else [union]
    )
    # (exterior ring, thickness-gated minimum y, per-resource clipped area)
    derived: list[tuple[object, float, dict[str, float]]] = []
    for part in parts:
        if part.geom_type != "Polygon" or part.is_empty:
            continue
        # EXTERIOR RING ONLY: a pit's interior columns and plinths punch
        # holes in the union, and terrain must not be left standing in
        # them ("we don't want any terrain poking up in the middle").
        try:
            exterior = Polygon(part.exterior)
            if not exterior.is_valid:
                exterior = exterior.buffer(0)
        except (ValueError, _GEOS_EXCEPTION):
            continue
        if exterior.geom_type != "Polygon" or exterior.is_empty:
            continue
        if exterior.area < TRENCH_SPINE_MIN_FOOTPRINT_AREA_M2:
            continue
        member_minimum_y = math.inf
        member_area_m2: dict[str, float] = {}
        for polygon, minimum_y, resource_path in contributions:
            try:
                if not polygon.intersects(exterior):
                    continue
                # The CLIPPED area inside this region — what §2.2 of the
                # founding spec ranks a contributor by.  Measured here,
                # where the clipped polygons already exist.
                inside_area = float(polygon.intersection(exterior).area)
            except (ValueError, _GEOS_EXCEPTION):
                continue
            member_area_m2[resource_path] = (
                member_area_m2.get(resource_path, 0.0) + inside_area
            )
            if minimum_y < member_minimum_y:
                member_minimum_y = minimum_y
        if member_minimum_y is math.inf:  # pragma: no cover - defensive
            continue
        derived.append((exterior, float(member_minimum_y), member_area_m2))
    if not derived:
        return []

    regions: list[BelowGradeRegion] = []
    for exterior, member_minimum_y, member_area_m2 in derived:
        regions.append(
            BelowGradeRegion(
                polygon=exterior,
                frame_origin_longitude_latitude=(
                    origin_longitude,
                    origin_latitude,
                ),
                solid_minimum_y_m=member_minimum_y,
                object_resources=tuple(sorted(member_area_m2)),
                # THE OPENNESS READING IS NOT TAKEN HERE (spec Amendment
                # 1, 2026-08-27): it is consumed only when a region is
                # UNMATCHED, and paying 12-33 s at LEMD for a number no
                # consumer reads is the eager-instrument defect.
                # ``regions_with_lazy_above_grade_coverage`` fills it for
                # the regions that can actually reach founding.
                above_grade_area_fraction=None,
                contributor_area_m2_by_resource=tuple(
                    sorted(member_area_m2.items())
                ),
            )
        )
    regions.sort(key=lambda region: region.polygon.area, reverse=True)
    return regions


def region_polygon_in_frame(region, frame_origin_longitude_latitude):
    """One :class:`BelowGradeRegion` ring in another record's metre
    frame, or ``None``.

    THE ONE PROJECTION PATH, and the ONE implementation of it
    (``object_terrain_assembly._region_polygon_in_frame`` delegates
    here).  The ring goes region frame → longitude/latitude through
    :func:`frame_polygon_to_longitude_latitude` — the converter
    ``_tunnel_footprint_longitude_latitude_parts`` uses — and then into
    the target frame through ``obj8_reader.lonlat_to_local_offset``,
    that converter's documented inverse.  A hand-rolled frame-to-frame
    translation would be a second projection of the same body.
    """
    return polygon_between_frames(
        region.polygon, region.frame_origin_longitude_latitude,
        frame_origin_longitude_latitude)


def polygon_between_frames(polygon, source_frame_origin, target_frame_origin):
    """One metre-frame polygon re-read in ANOTHER metre frame, or
    ``None``.

    :func:`region_polygon_in_frame` is this function applied to a
    region's ring; the ramp CORRIDOR (spec lemd-basin-trench-ramp-
    extension Amendment 1 §2) travels the same road, and it travels it
    through this one implementation rather than a second copy — the ring
    and the corridor beside it must never be projected two different
    ways.
    """
    if polygon is None or polygon.is_empty:
        return None
    longitude_latitude = frame_polygon_to_longitude_latitude(
        polygon, source_frame_origin)
    origin_longitude, origin_latitude = target_frame_origin
    parts = (
        list(longitude_latitude.geoms)
        if longitude_latitude.geom_type == "MultiPolygon"
        else [longitude_latitude]
    )
    converted = []
    for part in parts:
        ring = [
            obj8_reader.lonlat_to_local_offset(
                origin_latitude, origin_longitude, 0.0, latitude, longitude)
            for longitude, latitude in part.exterior.coords
        ]
        if len(ring) < 3:
            continue
        try:
            piece = Polygon(ring)
            if not piece.is_valid:
                piece = piece.buffer(0)
        except (ValueError, _GEOS_EXCEPTION):
            continue
        if piece.is_empty or piece.geom_type not in (
                "Polygon", "MultiPolygon"):
            continue
        converted.append(piece)
    if not converted:
        return None
    if len(converted) == 1:
        return converted[0]
    try:
        merged = unary_union(converted)
    except (ValueError, _GEOS_EXCEPTION):
        return None
    if merged.is_empty or merged.geom_type not in (
            "Polygon", "MultiPolygon"):
        return None
    return merged


def _region_prematched_to_an_interface(region, ground_interfaces) -> bool:
    """Whether ``region`` reaches any ground interface's own below-grade
    footprint — i.e. whether a basin record will EXTEND to it in
    assembly rather than found from it (spec Amendment 1)."""
    for interface in ground_interfaces:
        footprint = getattr(interface, "below_grade_footprint", None)
        if footprint is None or footprint.is_empty:
            continue
        frame_origin = getattr(
            interface, "frame_origin_longitude_latitude", None)
        if frame_origin is None:
            continue
        in_frame = region_polygon_in_frame(region, frame_origin)
        if in_frame is None:
            continue
        try:
            if in_frame.intersects(footprint):
                return True
        except (ValueError, _GEOS_EXCEPTION):
            continue
    return False


def regions_with_lazy_above_grade_coverage(
    regions: Sequence[BelowGradeRegion],
    ground_interfaces: Sequence[object],
    placements: Sequence[ObjectPlacement],
    geometry_by_resource: dict[str, ObjectGeometry],
    *,
    cache: "_ResourceGeometryCache | None" = None,
) -> list[BelowGradeRegion]:
    """Fill in the openness reading — LAZILY, BY PREMATCH (spec
    ``docs/specs/basin-region-founding-spec.md`` §2.1 Amendment 1,
    Fable ruling 2026-08-27).

    The coverage fraction gates FOUNDING, and founding can only happen
    for a region that matches NO record.  A region that already
    intersects a ground interface's ``below_grade_footprint`` will be
    EXTENDED onto that interface's basin record in assembly, so its
    coverage is a number nobody reads — and reading it is not free:
    MEASURED at LEMD 2026-08-27, the eager pass cost 33.4 s CPU (12.3 s
    with the bbox pre-filter) against 0.65 s for the region derivation
    itself, all of it for the one region that was prematched anyway.

    So a prematched region keeps ``above_grade_area_fraction=None``.
    That is not a silent guess: ``None`` means NOT COMPUTED, and the
    founding admission REFUSES on it with a loud line.  The corner that
    matters — a region prematched here whose record is then dropped
    upstream — therefore degrades to a reported refusal, never to a
    fabricated openness.

    Returns a new list (the regions are frozen); the un-prematched ones
    carry a real fraction, everything else is unchanged.  When NOTHING
    is un-prematched the above-grade machinery is never entered at all.
    """
    if not regions:
        return list(regions)
    needing = [
        index
        for index, region in enumerate(regions)
        if not _region_prematched_to_an_interface(region, ground_interfaces)
    ]
    if not needing:
        return list(regions)
    if cache is None:
        cache = _ResourceGeometryCache(geometry_by_resource)
    placements = [
        placement
        for placement in placements
        if not is_stock_library_resource(placement.resource_path)
    ]
    origin_longitude, origin_latitude = (
        regions[0].frame_origin_longitude_latitude)
    above_grade_union = _above_grade_union_in_frame(
        placements, cache, origin_latitude, origin_longitude,
        region_bounds=_bounds_union(
            [regions[index].polygon.bounds for index in needing]
        ),
    )
    filled = list(regions)
    for index in needing:
        region = regions[index]
        region_area = float(region.polygon.area)
        coverage = 0.0
        if above_grade_union is not None and region_area > 0.0:
            try:
                coverage = float(
                    above_grade_union.intersection(region.polygon).area
                ) / region_area
            except (ValueError, _GEOS_EXCEPTION):
                coverage = 0.0
        filled[index] = _replace_dataclass(
            region, above_grade_area_fraction=coverage)
    return filled


#: Spec ``docs/specs/lemd-basin-trench-ramp-extension-spec.md`` — the
#: plane the RAMP REACH pass follows an admitted region's own shell up
#: to.  It is the top of the GROUND-CONTACT BAND, i.e. the height at
#: which the pack's own geometry has MET grade, and it is the exact
#: mirror of the openness reading, which clips ABOVE the same plane.
#: ALIASED, never re-numbered (the discipline
#: :data:`PIT_SEED_MAX_ABOVE_GRADE_Y_M` already uses): one band, read
#: from both sides.
REGION_RAMP_REACH_PLANE_Y_M = GROUND_CONTACT_BAND_HALF_WIDTH_M

#: A ramp corridor under this area is not carried.  The emitter's own
#: plate floor is 4 m² and a corridor is a CORRIDOR — geometry a person
#: walks down, not a numerical remainder of the ring difference.  Kept
#: an order of magnitude above the plate floor so a 6 m² boundary
#: artefact of the morphological close never becomes a plate.
RAMP_REACH_CORRIDOR_MIN_AREA_M2 = 40.0

#: How far a corridor lobe must REACH beyond the admitted ring to be a
#: RAMP rather than the shell's own BATTER.  DERIVED, not calibrated:
#: the reach pass spans exactly
#: ``TRENCH_SPINE_MIN_DEPTH_M + REGION_RAMP_REACH_PLANE_Y_M`` of height
#: (−2.5 m up to +1.0 m), so a side at 45° or steeper — the module's own
#: model of a basin's batters, "≤45° earth slopes" — can travel at most
#: that far in plan over it.  Anything reaching further is FLATTER than a
#: batter, which is what a ramp is.
#:
#: MEASURED at LEMD (2026-08-28), the two lobes of the same delta: the
#: batter annulus reaches 2.25 m and runs 24 % of the ring's perimeter;
#: the entrance ramp reaches 11.22 m over 11 %.  The bound sits 1.25 m
#: above the batter and 3.2x under the ramp.  WITHOUT this test the
#: corridor is the annulus TOO — 1,779 m² wrapping half the pit — and
#: emitting it would widen the pan and stand the rim band down all the
#: way round, which is the ring-widening Amendment 1 refuted, arriving
#: by the back door.
RAMP_REACH_CORRIDOR_MIN_REACH_M = (
    TRENCH_SPINE_MIN_DEPTH_M + REGION_RAMP_REACH_PLANE_Y_M)


def _region_ring_completed_to(base_polygon, reach_parts):
    """``base_polygon`` grown to the CONNECTED reach geometry around it,
    as an exterior ring, or ``None`` when nothing grows.

    The base is unioned in first, so "the component that touches the
    admitted ring" is simply the component that CONTAINS it — there is
    no second connectivity spelling.  Closing and exterior-ring
    reduction are :func:`below_grade_regions`' own two steps, applied to
    the same numbers: a completion must be the same KIND of ring as the
    thing it completes.
    """
    if not reach_parts:
        return None
    union = _union_all_repairing(list(reach_parts) + [base_polygon])
    if union is None:
        return None
    try:
        union = union.buffer(AT_GRADE_FOOTPRINT_CLOSE_M).buffer(
            -AT_GRADE_FOOTPRINT_CLOSE_M
        )
    except (ValueError, _GEOS_EXCEPTION):
        return None
    union = _repaired_area_polygon(union)
    if union is None:
        return None
    parts = (
        list(union.geoms) if union.geom_type == "MultiPolygon" else [union]
    )
    best = None
    for part in parts:
        if part.geom_type != "Polygon" or part.is_empty:
            continue
        try:
            if not part.intersects(base_polygon):
                continue
            overlap = float(part.intersection(base_polygon).area)
        except (ValueError, _GEOS_EXCEPTION):
            continue
        if best is None or overlap > best[0]:
            best = (overlap, part)
    if best is None:
        return None
    try:
        ring = Polygon(best[1].exterior)
        if not ring.is_valid:
            ring = ring.buffer(0)
    except (ValueError, _GEOS_EXCEPTION):
        return None
    if ring.geom_type != "Polygon" or ring.is_empty:
        return None
    # A completion may only GROW.  Anything else is a numerical accident
    # of the close, and the admitted ring stands.
    if ring.area <= base_polygon.area:
        return None
    return ring


def _region_ramp_reach_rings(
    regions: Sequence[BelowGradeRegion],
    placements: Sequence[ObjectPlacement],
    geometry_by_resource: dict[str, ObjectGeometry],
    *,
    cache: "_ResourceGeometryCache | None" = None,
) -> "tuple[dict[int, object], set[int]]":
    """``({region index: completed ring}, {refused index})`` — THE ONE
    ramp-reach derivation.

    Both consumers read it: the RETIRED region-completion pass
    (:func:`regions_completed_to_ramp_reach`, refuted by measurement and
    default-off) and the LIVE corridor pass
    (:func:`regions_with_ramp_reach_corridor`, spec Amendment 1 §2).
    They must never disagree about where a pit's entrance ramp is —
    two spellings of one ramp is the census-wrapper class — so the
    geometry is derived here once and each consumer only decides what to
    DO with it.

    An admitted region's ring is grown to the CONNECTED part of its OWN
    contributors' shell clipped below :data:`REGION_RAMP_REACH_PLANE_Y_M`
    (the top of the ground-contact band, the exact mirror of the openness
    reading, which clips ABOVE the same plane).  A resource that
    contributed nothing to an admitted region contributes nothing here,
    which is the scope guard AND the perf guard.

    ONE BODY, ONE CUT: a ring that reaches into another region — its
    admitted ring or its own completion — is REFUSED on both sides and
    named, never silently cut twice.  Refused indices are returned so
    each consumer can report them in its own words.
    """
    members_by_index = [set(region.object_resources) for region in regions]
    wanted: set[str] = set()
    for members in members_by_index:
        wanted |= members
    if not wanted:
        return {}, set()
    if cache is None:
        cache = _ResourceGeometryCache(geometry_by_resource)
    # ONE FRAME.  ``below_grade_regions`` builds every region it returns
    # about one mean origin, so the reach geometry is transformed into
    # that frame once and compared with the rings directly.
    origin_longitude, origin_latitude = (
        regions[0].frame_origin_longitude_latitude)

    reach_by_resource: dict[str, list] = {}
    for placement in placements:
        resource_path = placement.resource_path
        if resource_path not in wanted:
            continue
        if is_stock_library_resource(resource_path):
            continue
        _has_hard, has_solid, minimum_vertex_y, _maximum_vertex_y = (
            cache.evidence(resource_path)
        )
        if not has_solid:
            continue
        above_ground = float(placement.above_ground_level_metres)
        plane_local_y = REGION_RAMP_REACH_PLANE_Y_M - above_ground
        if minimum_vertex_y > plane_local_y:
            continue
        local = cache.below_grade_local_union(resource_path, plane_local_y)
        if local is None:
            continue
        try:
            transformed = shapely_affinity.affine_transform(
                local[0],
                _affine_matrix_for_placement(
                    placement, origin_latitude, origin_longitude
                ),
            )
        except (ValueError, _GEOS_EXCEPTION):
            continue
        transformed = _repaired_area_polygon(transformed)
        if transformed is None:
            continue
        reach_by_resource.setdefault(resource_path, []).append(transformed)
    if not reach_by_resource:
        return {}, set()

    candidates: dict[int, object] = {}
    for index, region in enumerate(regions):
        parts = [
            part
            for resource_path in sorted(members_by_index[index])
            for part in reach_by_resource.get(resource_path, ())
        ]
        ring = _region_ring_completed_to(region.polygon, parts)
        if ring is not None:
            candidates[index] = ring

    refused: set[int] = set()
    ordered = sorted(candidates)
    for position, index in enumerate(ordered):
        for other in ordered[position + 1:]:
            try:
                if candidates[index].intersection(
                        candidates[other]).area > 0.0:
                    refused.add(index)
                    refused.add(other)
            except (ValueError, _GEOS_EXCEPTION):
                refused.add(index)
                refused.add(other)
    for index in ordered:
        if index in refused:
            continue
        for other, region in enumerate(regions):
            if other == index:
                continue
            try:
                if candidates[index].intersection(region.polygon).area > 0.0:
                    refused.add(index)
            except (ValueError, _GEOS_EXCEPTION):
                refused.add(index)
    return candidates, refused


def _ramp_lobes_of(delta, admitted_ring):
    """``([ramp lobe, ...], dropped count)`` — the RAMPS in a
    ``completed − admitted`` difference, and nothing else.

    THE DELTA IS NOT THE RAMP.  Clipping the shell at the ground-contact
    band instead of the depth admission widens the ring EVERYWHERE its
    sides are battered, so the raw difference at LEMD is 1,779 m² of
    which roughly two fifths is a thin annulus wrapping half the pit,
    plus a dust of sub-m² slivers from the shared boundary.  Emitting
    that would widen the floor pan and stand the rim band down all the
    way round — the ring-widening Amendment 1 refuted, arriving by the
    back door.

    Two tests, both reading constants this module already owns:

    1. SHAPE — the delta is opened at :data:`AT_GRADE_FOOTPRINT_CLOSE_M`,
       the radius at which this module decides what is one shape, and
       each surviving core is re-dilated and clipped back to the delta.
       That splits the annulus from the ramp and drops the slivers in
       one step.
    2. REACH — a lobe survives only if it reaches further from the
       admitted ring than :data:`RAMP_REACH_CORRIDOR_MIN_REACH_M`, i.e.
       further than a 45° batter could travel over the height the reach
       pass spans.  A lobe that does not is the shell's own side.

    …and the emitter's plate floor, as area, so nothing under a plate is
    carried as one.
    """
    if delta is None or delta.is_empty:
        return [], 0
    parts = (
        list(delta.geoms) if delta.geom_type == "MultiPolygon" else [delta]
    )
    total_parts = len(parts)
    try:
        opened = delta.buffer(-AT_GRADE_FOOTPRINT_CLOSE_M)
    except (ValueError, _GEOS_EXCEPTION):
        return [], total_parts
    if opened.is_empty:
        return [], total_parts
    cores = (
        list(opened.geoms) if opened.geom_type == "MultiPolygon"
        else [opened]
    )
    ring_boundary = admitted_ring.exterior
    kept: list = []
    for core in cores:
        if core.geom_type != "Polygon" or core.is_empty:
            continue
        # THE REACH IS THE CORE'S, never the re-dilated lobe's: the
        # dilation is how the lobe is put back together, and letting it
        # count would credit every lobe with an extra
        # ``AT_GRADE_FOOTPRINT_CLOSE_M`` of travel it does not have
        # (measured at LEMD: the batter reads 2.25 m as a core and 4.25 m
        # as a lobe, which is the difference between dropping it and
        # emitting it).
        try:
            reach = max(
                ring_boundary.distance(Point(coordinate))
                for coordinate in core.exterior.coords
            )
        except (ValueError, _GEOS_EXCEPTION):
            continue
        try:
            lobe = core.buffer(AT_GRADE_FOOTPRINT_CLOSE_M).intersection(delta)
        except (ValueError, _GEOS_EXCEPTION):
            continue
        if lobe.is_empty or lobe.area < RAMP_REACH_CORRIDOR_MIN_AREA_M2:
            continue
        if reach <= RAMP_REACH_CORRIDOR_MIN_REACH_M:
            _vprint(
                2,
                "   [object-terrain] ramp lobe dropped: "
                f"{lobe.area:,.0f} m² reaching only {reach:.2f} m "
                f"from the ring (<= {RAMP_REACH_CORRIDOR_MIN_REACH_M:.1f}"
                " m, a 45° batter's own travel) — the shell's side, "
                "not its ramp",
            )
            continue
        pieces = (
            list(lobe.geoms) if lobe.geom_type == "MultiPolygon" else [lobe]
        )
        for piece in pieces:
            if piece.geom_type != "Polygon" or piece.is_empty:
                continue
            if piece.area < RAMP_REACH_CORRIDOR_MIN_AREA_M2:
                continue
            kept.append(piece)
    return kept, total_parts - len(kept)


def regions_with_ramp_reach_corridor(
    regions: Sequence[BelowGradeRegion],
    placements: Sequence[ObjectPlacement],
    geometry_by_resource: dict[str, ObjectGeometry],
    *,
    cache: "_ResourceGeometryCache | None" = None,
) -> list[BelowGradeRegion]:
    """Attach each admitted region's ENTRANCE-RAMP CORRIDOR (spec
    ``docs/specs/lemd-basin-trench-ramp-extension-spec.md`` Amendment 1
    §2; gate ``config.BASIN_RAMP_REACH_PLATE``).

    THE RING IS NOT TOUCHED, and that is the whole ruling.  Amendment 1
    was written because the lane MEASURED what growing it costs: the
    facility ring is the single measurement body — the floor value, the
    rim value, the building-pad coverage test and R_mesh's group-seat
    sample band are all read off it — so widening it moved floor
    587.75→588.69, rim 600.51→600.47, un-flattened the building8 pad and
    drifted G 596.682→597.492, and the widened pan was differenced away
    by earlier-born shapes regardless.

    So the ramp is carried as SEPARATE, ADDITIVE geometry:
    ``corridor = completed ring − admitted ring``, the ground the pit's
    own shell covers between where the depth admission stopped and where
    that shell meets grade.  Every reading in this module still comes off
    ``polygon``; the corridor is consumed at EMIT and nowhere else
    (``object_terrain_assembly.build_tunnel_layout_shapes``).

    Returns a new list (the regions are frozen); with the gate off, or
    with no ramp to carry, the input regions come back unchanged.
    """
    from . import config as _config

    # ONE READER for "is a corridor carried at all" (``config.
    # basin_ramp_corridor_carried``): the retired plate arm
    # (``BASIN_RAMP_REACH_PLATE``) and the owner-sanctioned PAD-AUTHORITY
    # CARVE (``BASIN_PAD_AUTHORITY_CARVE``, spec
    # ``docs/specs/lemd-pad-authority-carve-spec.md`` §1) consume the
    # SAME corridor and differ only in what they do with it.  A second
    # derivation for the carve would be two spellings of one ramp — the
    # census-wrapper class this module's own docstring names.
    if not regions or not _config.basin_ramp_corridor_carried():
        return list(regions)
    candidates, refused = _region_ramp_reach_rings(
        regions, placements, geometry_by_resource, cache=cache)
    if not candidates:
        return list(regions)

    out = list(regions)
    for index in sorted(candidates):
        region = regions[index]
        if index in refused:
            _vprint(
                1,
                "   [object-terrain] RAMP CORRIDOR REFUSED: the ramp of "
                f"the {region.polygon.area:,.0f} m² below-grade region "
                "would OVERLAP another region — one body cut twice; no "
                "corridor is carried",
            )
            continue
        try:
            corridor = candidates[index].difference(region.polygon)
        except (ValueError, _GEOS_EXCEPTION):
            continue
        if corridor is None or corridor.is_empty:
            continue
        kept, dropped = _ramp_lobes_of(corridor, region.polygon)
        if kept:
            try:
                corridor = (kept[0] if len(kept) == 1
                            else unary_union(kept))
            except (ValueError, _GEOS_EXCEPTION):
                continue
        if not kept or corridor.area < RAMP_REACH_CORRIDOR_MIN_AREA_M2:
            _vprint(
                2,
                "   [object-terrain] ramp corridor of the "
                f"{region.polygon.area:,.0f} m² region keeps no part at "
                f"or over the {RAMP_REACH_CORRIDOR_MIN_AREA_M2:.0f} m² "
                "plate floor — not carried",
            )
            continue
        _vprint(
            1,
            "   [object-terrain] RAMP CORRIDOR: "
            f"{corridor.area:,.0f} m² in {len(kept)} part(s) carried "
            f"beside the {region.polygon.area:,.0f} m² admitted ring "
            f"({dropped} batter/sliver piece(s) dropped; the entrance "
            "ramp the depth admission clipped off; the RING IS "
            "UNTOUCHED — spec Amendment 1 §2)",
        )
        out[index] = _replace_dataclass(
            region, ramp_reach_corridor=corridor)
    return out


def regions_completed_to_ramp_reach(
    regions: Sequence[BelowGradeRegion],
    placements: Sequence[ObjectPlacement],
    geometry_by_resource: dict[str, ObjectGeometry],
    *,
    cache: "_ResourceGeometryCache | None" = None,
) -> list[BelowGradeRegion]:
    """Follow each admitted region up its own RAMP to grade (spec
    ``docs/specs/lemd-basin-trench-ramp-extension-spec.md``; gate
    ``config.BASIN_REGION_RAMP_REACH``).

    :func:`below_grade_regions` clips at −:data:`TRENCH_SPINE_MIN_DEPTH_M`
    because that plane is the DEPTH ADMISSION — "is this a trench?".  A
    pit's entrance ramp crosses it on the way up, so the admitted ring
    stops half way up the ramp and the mesh stands at grade over the
    rest of it: the authored ramp has terrain through it, which is the
    owner's 2026-08-28 LEMD read (poke-through 0.60 m outside the ring,
    the ramp's own top 11.00 m outside).

    This is COMPLETION, not admission.  It runs AFTER
    :func:`regions_with_lazy_above_grade_coverage`, so every number that
    gates founding — depth, openness, the contributor list and their
    clipped areas — is measured on the ADMITTED ring and is untouched
    here; only ``polygon`` grows.  It grows only into the region's OWN
    contributors' shell clipped below
    :data:`REGION_RAMP_REACH_PLANE_Y_M`, and only into the part of it
    CONNECTED to the admitted ring, so a resource that contributed
    nothing contributes nothing now — which is also the perf guard.

    Two completions that would OVERLAP are BOTH refused, loudly: one
    body cut twice is worse than a ramp left uncut, and the pair is
    named so it is attributable.

    Returns a new list (the regions are frozen); with the gate off, or
    with nothing to grow, the input regions come back unchanged.
    """
    from .config import BASIN_REGION_RAMP_REACH

    if not regions or not BASIN_REGION_RAMP_REACH:
        return list(regions)
    candidates, refused = _region_ramp_reach_rings(
        regions, placements, geometry_by_resource, cache=cache)
    if not candidates:
        return list(regions)

    completed = list(regions)
    for index in sorted(candidates):
        region = regions[index]
        if index in refused:
            _vprint(
                1,
                "   [object-terrain] RAMP REACH REFUSED: the completion of "
                f"the {region.polygon.area:,.0f} m² below-grade region "
                "would OVERLAP another region — one body cut twice; the "
                "admitted ring stands",
            )
            continue
        ring = candidates[index]
        _vprint(
            1,
            "   [object-terrain] RAMP REACH: below-grade region "
            f"{region.polygon.area:,.0f} m² -> {ring.area:,.0f} m² "
            "(followed its own shell up to the ground-contact band at "
            f"+{REGION_RAMP_REACH_PLANE_Y_M:.1f} m — the entrance ramp "
            "the depth admission clipped off)",
        )
        completed[index] = _replace_dataclass(region, polygon=ring)
    return completed


def _bounds_union(bounds_list):
    """``(min_x, min_z, max_x, max_z)`` over shapely ``bounds`` tuples."""
    if not bounds_list:
        return None
    minimum_x = min(bounds[0] for bounds in bounds_list)
    minimum_z = min(bounds[1] for bounds in bounds_list)
    maximum_x = max(bounds[2] for bounds in bounds_list)
    maximum_z = max(bounds[3] for bounds in bounds_list)
    return (minimum_x, minimum_z, maximum_x, maximum_z)


def _placement_frame_bounds(
    placement: ObjectPlacement,
    cache: "_ResourceGeometryCache",
    origin_latitude: float,
    origin_longitude: float,
):
    """Frame-space bounding box of a placement's WHOLE solid geometry, or
    ``None``.  A SUPERSET of anything the placement can contribute, built
    from four transformed corners — no triangle work, no GEOS."""
    local_bounds = cache.local_xz_bounds(placement.resource_path)
    if local_bounds is None:
        return None
    minimum_x, minimum_z, maximum_x, maximum_z = local_bounds
    a, b, d, e, x_offset, z_offset = _affine_matrix_for_placement(
        placement, origin_latitude, origin_longitude
    )
    corners = [
        (a * x + b * z + x_offset, d * x + e * z + z_offset)
        for x, z in (
            (minimum_x, minimum_z),
            (maximum_x, minimum_z),
            (maximum_x, maximum_z),
            (minimum_x, maximum_z),
        )
    ]
    return (
        min(corner[0] for corner in corners),
        min(corner[1] for corner in corners),
        max(corner[0] for corner in corners),
        max(corner[1] for corner in corners),
    )


def _bounds_overlap(first, second) -> bool:
    if first is None or second is None:
        return True
    return not (
        first[2] < second[0]
        or second[2] < first[0]
        or first[3] < second[1]
        or second[3] < first[1]
    )


def _above_grade_union_in_frame(
    placements: Sequence[ObjectPlacement],
    cache: "_ResourceGeometryCache",
    origin_latitude: float,
    origin_longitude: float,
    *,
    region_bounds=None,
):
    """Frame-space union of everything the pack's own solids put ABOVE
    the ground band — the openness instrument of spec
    ``basin-region-founding-spec.md`` §2.1 item 2, or ``None``.

    Same pass, same placements, same cache, same decal gate and the same
    per-resource PRE-SCAN as the below-grade half: a resource whose
    highest AUTHORED vertex cannot reach ``+GROUND_CONTACT_BAND_
    HALF_WIDTH_M`` is skipped before any triangle work.  Called only
    when at least one region exists, so a pack with nothing below grade
    never reaches it.

    TWO SKIPS, not one.  The reading is only ever used INTERSECTED WITH
    A REGION, so a placement whose whole geometry lies outside every
    region's bounding box contributes nothing to it by construction and
    is skipped on four transformed corners — no clip, no union, no GEOS.
    Without it this pass runs the whole airport's above-grade geometry
    to measure one pit: MEASURED at LEMD 2026-08-27, 33.4 s CPU against
    0.65 s for the region itself, versus 12.3 s with the skip, for the
    IDENTICAL reading (0.10008247282569119 either way — 927 placements
    tested, 31 resources clipped).  The bounding box is a
    SUPERSET of the placement's contribution, so the skip cannot change
    the answer — the same argument as the below-grade pre-scan's.
    """
    transformed_parts = []
    for placement in placements:
        resource_path = placement.resource_path
        _has_hard, has_solid, _minimum_vertex_y, maximum_vertex_y = (
            cache.evidence(resource_path)
        )
        if not has_solid:
            continue
        if not _bounds_overlap(
            _placement_frame_bounds(
                placement, cache, origin_latitude, origin_longitude
            ),
            region_bounds,
        ):
            continue
        above_ground = float(placement.above_ground_level_metres)
        plane_local_y = GROUND_CONTACT_BAND_HALF_WIDTH_M - above_ground
        # THE PRE-SCAN, mirrored: nothing of this resource can reach the
        # band's top, so no triangle of it stands over anything.
        if maximum_vertex_y < plane_local_y:
            continue
        local_union = cache.above_grade_local_union(
            resource_path, plane_local_y
        )
        if local_union is None:
            continue
        try:
            transformed = shapely_affinity.affine_transform(
                local_union,
                _affine_matrix_for_placement(
                    placement, origin_latitude, origin_longitude
                ),
            )
        except (ValueError, _GEOS_EXCEPTION):
            continue
        transformed = _repaired_area_polygon(transformed)
        if transformed is not None:
            transformed_parts.append(transformed)
    if not transformed_parts:
        return None
    return _union_all_repairing(transformed_parts)


# ---------------------------------------------------------------------------
# Tunnel recognition (feature A)
# ---------------------------------------------------------------------------

def _agl_tunnel_seed_resources(
    placements: Sequence[ObjectPlacement],
    frame: _StructureFrame,
) -> set[str]:
    """Resources whose below-grade ``OBJECT_AGL`` placement is a credible
    tunnel signal (the guarded AGL limb — see
    :data:`TUNNEL_AGL_MIN_BELOW_GRADE_DECK_AREA_M2`): single placement,
    offset at or below −:data:`TUNNEL_MIN_BELOW_GRADE_AGL_OFFSET_M`, real
    below-effective-grade horizontal deck area, and nothing standing more
    than :data:`TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M` above grade (a shell
    lives below the grade plane; a buried BUILDING towers over it).

    THE ABOVE-GRADE CAP IS JUDGED ON THE WHOLE STRUCTURE (owner ruling
    2026-07-31, "all the bridges you highlighted are above ground
    bridges").  It used to be read per RESOURCE, and a multi-part
    structure could therefore be seeded by ONE low sub-object while the
    rest of it towered overhead: measured at OTHH, Bridge_01 (12
    resources, pool crest **+10.25 m**) and Bridge_04 (5 resources, crest
    +1.91 m) were each seeded by a single ``*_LOD0_002.obj`` and cut as
    tunnels — Bridge_01's trench then ran to −6.34 m and left its ramp
    floating above the hole.  A structure that crests ten metres over
    grade is not a below-grade shell, whatever one of its twelve parts
    looks like.  The pool-wide floor on below-grade deck area travels
    with it for the same reason (Bridge_04 carries 8 m² pool-wide against
    the 25 m² gate).

    A SINGLE-PLACEMENT structure is unaffected by the pool-wide reading —
    pool equals resource — so every one-object AGL tunnel (the EGLL 6/7/10
    shells, and the fixtures pinning them) reads as it did before it.

    THE HEIGHT CAP ALONE CANNOT CATCH A LOW BRIDGE.  Bridge_04 crests at
    +1.91 m, inside the 2.0 m cap, and its below-grade "deck" is the
    UNDERSIDE of an at-grade slab: 1,022 m² of near-horizontal face between
    −0.5 and −1.0 m, and 8.4 m² below −1.0 — slab thickness, not a floor.
    Deepening the below-grade floor to catch that was measured and
    REJECTED: at −2.0 m (the plan's candidate) EGLL Tunnel/7 falls to
    19.4 m², under the 25 m² gate, and stops being a tunnel.  The gate that
    separates them is the area standing clear ABOVE grade
    (:data:`TUNNEL_AGL_MAX_ABOVE_GRADE_DECK_AREA_M2`): Bridge_04 1,650.6 m²
    against Tunnel/7's 0.0 and Tunnel/10's 128.7."""
    placement_count: dict[str, int] = {}
    for placement in placements:
        placement_count[placement.resource_path] = (
            placement_count.get(placement.resource_path, 0) + 1
        )
    below_grade_mask = (
        frame.triangle_horizontality >= NEAR_HORIZONTAL_NORMAL_Y_MIN
    ) & (frame.triangle_height_m <= -TUNNEL_ROOF_TOP_TOLERANCE_M)
    below_grade_area_by_index = numpy.bincount(
        frame.triangle_resource_indices[below_grade_mask],
        weights=frame.triangle_area_m2[below_grade_mask],
        minlength=len(frame.triangle_resource_paths),
    )
    below_grade_area = {
        resource: area
        for resource, area in zip(
            frame.triangle_resource_paths,
            below_grade_area_by_index.tolist(),
        )
    }
    highest_face_by_index = numpy.full(
        len(frame.triangle_resource_paths), -numpy.inf
    )
    numpy.maximum.at(
        highest_face_by_index,
        frame.triangle_resource_indices,
        frame.triangle_height_m,
    )
    highest_face = {
        resource: height
        for resource, height in zip(
            frame.triangle_resource_paths,
            highest_face_by_index.tolist(),
        )
    }
    # Whole-structure gates (see the docstring): the tallest face, the deck
    # area standing clear above grade, and the total below-grade deck area
    # over EVERY part, not the seeding part.
    structure_highest_face = (
        float(frame.triangle_height_m.max())
        if frame.triangle_count else -numpy.inf
    )
    structure_below_grade_area = float(
        frame.triangle_area_m2[below_grade_mask].sum()
    )
    above_grade_deck_mask = (
        frame.triangle_horizontality >= NEAR_HORIZONTAL_NORMAL_Y_MIN
    ) & (frame.triangle_height_m >= TUNNEL_ROOF_TOP_TOLERANCE_M)
    structure_above_grade_deck_area = float(
        frame.triangle_area_m2[above_grade_deck_mask].sum()
    )
    if (structure_highest_face > TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M
            or structure_above_grade_deck_area
            >= TUNNEL_AGL_MAX_ABOVE_GRADE_DECK_AREA_M2
            or structure_below_grade_area
            < TUNNEL_AGL_MIN_BELOW_GRADE_DECK_AREA_M2):
        return set()
    return {
        placement.resource_path
        for placement in placements
        if placement.above_ground_level_metres
        <= -TUNNEL_MIN_BELOW_GRADE_AGL_OFFSET_M
        and placement_count[placement.resource_path] == 1
        and below_grade_area.get(placement.resource_path, 0.0)
        >= TUNNEL_AGL_MIN_BELOW_GRADE_DECK_AREA_M2
        and highest_face.get(placement.resource_path, -numpy.inf)
        <= TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M
    }


def _is_tunnel_signature(
    placements: Sequence[ObjectPlacement],
    frame: _StructureFrame,
) -> bool:
    """A structure is a tunnel when it has a substantial near-horizontal
    DRIVABLE deck below grade, or is placed below grade by its OBJECT_AGL
    offset (spec section 3.1; discriminator validated against the EGLL
    author mesh, 0 wrong on 30 below-grade buildings + 20 tunnel objects).

    Two entries, matching the two below-grade signals:

    1. At least :data:`TUNNEL_MIN_BELOW_GRADE_DECK_AREA_M2` of
       near-horizontal HARD (``ATTR_hard`` / ``ATTR_hard_deck``) face area
       at or below :data:`TUNNEL_MIN_BODY_DEPTH_M` beneath grade.  The
       hardness requirement excludes buried building basements (which are
       never drivable — see the area constant's comment); the below-grade
       requirement excludes at-grade hard roads; the near-horizontal
       requirement excludes bridge piers.
    2. A negative OBJECT_AGL placement offset of magnitude
       :data:`TUNNEL_MIN_BELOW_GRADE_AGL_OFFSET_M` or more — the EGLL AGL
       shells (6/7/10) carry no hard triangles, and their offset is the
       unambiguous below-grade signal.
    """
    if frame.triangle_count == 0:
        return False
    drivable_mask = (
        (frame.triangle_hardness_codes > 0)
        & (frame.triangle_horizontality >= NEAR_HORIZONTAL_NORMAL_Y_MIN)
        & (frame.triangle_height_m <= -TUNNEL_MIN_BODY_DEPTH_M)
    )
    below_grade_drivable_area = float(
        frame.triangle_area_m2[drivable_mask].sum()
    )
    if below_grade_drivable_area >= TUNNEL_MIN_BELOW_GRADE_DECK_AREA_M2:
        return True
    return bool(_agl_tunnel_seed_resources(placements, frame))


def _solid_outline_footprint(
    triangles: Sequence[_FrameTriangle],
) -> Polygon | MultiPolygon | None:
    """Plan outline of every SOLID triangle reaching grade or below.

    The near-horizontal deck/roof unions under-represent wall-and-ramp
    shells: the EGLL west-end AGL pair (Tunnel/6+7) is built from
    vertical walls and a sloped approach-ramp skin, so its "deck" came
    to 45/86 m2 inside 18x16 / 25x19 m structures and the trench cut a
    sliver (user 2026-07-18c, in-sim: object below grade, not fully cut
    out).  Here EVERY solid triangle whose lowest effective corner
    reaches grade projects to plan — sloped skins with their true area,
    verticals as thin buffered slivers — the union is morphologically
    closed and its exterior rings filled (a closed shell ring encloses
    its floor plan).  Triangles entirely above grade (parapets, signs)
    stay out so the outline remains a below-grade cut."""
    pieces = []
    for triangle in triangles:
        if min(corner[1] for corner in triangle.corners) > 0.0:
            continue
        flat = [(corner[0], corner[2]) for corner in triangle.corners]
        try:
            polygon = Polygon(flat)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty or polygon.area < 0.05:
                polygon = LineString(
                    list(flat) + [flat[0]]).buffer(0.05)
            if not polygon.is_empty:
                pieces.append(polygon)
        except (ValueError, _GEOS_EXCEPTION):
            continue
    if not pieces:
        return None
    try:
        union = unary_union(pieces)
        closed = union.buffer(1.0).buffer(-1.0)
        parts = (
            closed.geoms if hasattr(closed, "geoms") else [closed]
        )
        filled = unary_union([
            Polygon(part.exterior) for part in parts
            if part.geom_type == "Polygon" and not part.is_empty
        ])
    except (ValueError, _GEOS_EXCEPTION):
        return None
    if filled.is_empty:
        return None
    if filled.geom_type not in ("Polygon", "MultiPolygon"):
        return None
    return filled


def _classify_tunnel(
    placements: Sequence[ObjectPlacement],
    origin_latitude: float,
    origin_longitude: float,
    triangles: Sequence[_FrameTriangle],
) -> TunnelStructure:
    near_horizontal = [
        triangle
        for triangle in triangles
        if triangle.horizontality >= NEAR_HORIZONTAL_NORMAL_Y_MIN
    ]
    roof_faces = [
        triangle
        for triangle in near_horizontal
        if triangle.height_m >= -TUNNEL_ROOF_TOP_TOLERANCE_M
    ]
    deck_faces = [
        triangle
        for triangle in near_horizontal
        if triangle.height_m < -TUNNEL_ROOF_TOP_TOLERANCE_M
    ]
    roof_footprint = _union_horizontal(roof_faces)
    deck_footprint = _union_horizontal(deck_faces)

    mouth_polygons: list[Polygon] = []
    if deck_footprint is not None:
        if roof_footprint is not None:
            try:
                mouth_geometry = deck_footprint.difference(
                    roof_footprint.buffer(ROOF_DIFFERENCE_BUFFER_M)
                )
            except (ValueError, _GEOS_EXCEPTION):
                mouth_geometry = deck_footprint
        else:
            # No roofed section: the whole deck is open cut.
            mouth_geometry = deck_footprint
        mouth_polygons = _split_polygons(mouth_geometry)

    mouth_depth_samples: list[MouthDepthStatistics] = []
    for mouth in mouth_polygons:
        depths = [
            -triangle.height_m
            for triangle in deck_faces
            if mouth.contains(Point(triangle.centroid_xz))
        ]
        if depths:
            mouth_depth_samples.append(
                MouthDepthStatistics(
                    minimum_depth_m=min(depths),
                    maximum_depth_m=max(depths),
                    mean_depth_m=sum(depths) / len(depths),
                    sample_count=len(depths),
                )
            )
        else:
            mouth_depth_samples.append(
                MouthDepthStatistics(0.0, 0.0, 0.0, 0)
            )

    # Body depth: the deck level under the roofed (covered) section.
    if roof_footprint is not None:
        covered_deck_heights = [
            triangle.height_m
            for triangle in deck_faces
            if roof_footprint.contains(Point(triangle.centroid_xz))
        ]
    else:
        covered_deck_heights = []
    if not covered_deck_heights:
        covered_deck_heights = [triangle.height_m for triangle in deck_faces]
    body_depth_m = (
        -median(covered_deck_heights) if covered_deck_heights else 0.0
    )
    solid_minimum_y_m = min(
        (corner[1] for triangle in triangles for corner in triangle.corners),
        default=None,
    )

    reference_placement = placements[0]
    return TunnelStructure(
        object_resources=sorted(
            {placement.resource_path for placement in placements}
        ),
        anchor_longitude_latitude=(
            reference_placement.longitude,
            reference_placement.latitude,
        ),
        frame_origin_longitude_latitude=(origin_longitude, origin_latitude),
        heading_degrees=reference_placement.heading_degrees,
        placement_kind=reference_placement.placement_kind,
        above_ground_offset_m=reference_placement.above_ground_level_metres,
        roof_footprint=roof_footprint,
        deck_footprint=deck_footprint,
        mouth_polygons=mouth_polygons,
        mouth_depth_samples=mouth_depth_samples,
        body_depth_m=body_depth_m,
        solid_minimum_y_m=solid_minimum_y_m,
        solid_outline_footprint=_solid_outline_footprint(triangles),
    )


# ---------------------------------------------------------------------------
# Bridge recognition (feature B)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _DeckAxis:
    """The deck's minimum-rotated-rectangle long axis and its two ends.

    ``abutment_lines`` is ordered [start end, far end] along the axis
    (``axis_origin_xz`` + t * ``axis_unit_xz``, t in [0, length]), so
    profile order, end-elevation order and abutment order all agree."""

    length_m: float
    width_m: float
    axis_origin_xz: tuple[float, float]
    axis_unit_xz: tuple[float, float]
    abutment_lines: list[tuple[tuple[float, float], tuple[float, float]]]

    def along_axis(self, x: float, z: float) -> float:
        return (x - self.axis_origin_xz[0]) * self.axis_unit_xz[0] + (
            z - self.axis_origin_xz[1]
        ) * self.axis_unit_xz[1]


def _deck_axis(polygon: Polygon) -> _DeckAxis | None:
    """Long axis + short-edge deck ends of the polygon's minimum rotated
    rectangle.  ``None`` on degenerate geometry."""
    try:
        rectangle = min_rotated_rect(polygon)
    except (ValueError, _GEOS_EXCEPTION):
        return None
    if rectangle.geom_type != "Polygon":
        return None
    corners = list(rectangle.exterior.coords)[:4]
    if len(corners) < 4:
        return None
    edges = [
        (corners[index], corners[(index + 1) % 4]) for index in range(4)
    ]
    lengths = [
        math.hypot(end[0] - start[0], end[1] - start[1])
        for start, end in edges
    ]
    long_index = max(range(4), key=lambda index: lengths[index])
    length_m = lengths[long_index]
    width_m = min(lengths)
    if length_m <= 0.0:
        return None
    start, end = edges[long_index]
    axis_unit = (
        (end[0] - start[0]) / length_m,
        (end[1] - start[1]) / length_m,
    )
    # Canonicalize the axis direction (positive x, tie-broken on z) so
    # the [start end, far end] ordering is a property of the deck's
    # GEOMETRY, not of which corner GEOS happens to enumerate first on
    # the rotated rectangle's ring.
    if axis_unit[0] < 0.0 or (axis_unit[0] == 0.0 and axis_unit[1] < 0.0):
        start, end = end, start
        axis_unit = (-axis_unit[0], -axis_unit[1])
    # The two short edges are the deck ends; order them along the axis by
    # midpoint projection so [start end, far end] is well defined.
    ordered_by_length = sorted(range(4), key=lambda index: lengths[index])
    short_edges = [edges[ordered_by_length[0]], edges[ordered_by_length[1]]]

    def _midpoint_projection(edge) -> float:
        midpoint_x = (edge[0][0] + edge[1][0]) / 2.0
        midpoint_z = (edge[0][1] + edge[1][1]) / 2.0
        return (midpoint_x - start[0]) * axis_unit[0] + (
            midpoint_z - start[1]
        ) * axis_unit[1]

    short_edges.sort(key=_midpoint_projection)
    abutment_lines = [
        ((edge[0][0], edge[0][1]), (edge[1][0], edge[1][1]))
        for edge in short_edges
    ]
    return _DeckAxis(
        length_m=length_m,
        width_m=width_m,
        axis_origin_xz=(start[0], start[1]),
        axis_unit_xz=axis_unit,
        abutment_lines=abutment_lines,
    )


def _deck_top_profile(
    deck_faces: Sequence[_FrameTriangle],
    axis: _DeckAxis,
) -> list[tuple[float, float]]:
    """Deck TOP effective height in :data:`BRIDGE_PROFILE_BIN_LENGTH_M`
    bins along the deck axis, as ``(along_axis_m, y_m)`` pairs.

    Sampled from deck-face CORNERS (a planar face's height is linear, so
    corners bound it; the end and crest elevations live exactly at
    corners), taking the per-bin MAXIMUM — the top surface — which also
    discards any hard-marked slab UNDERSIDE corners sharing a bin (the
    whole ``ATTR_hard`` range of a slab includes its bottom faces).  Empty
    bins are filled by linear interpolation between their non-empty
    neighbours."""
    corner_samples: list[tuple[float, float]] = []  # (along, y)
    for face in deck_faces:
        for corner_x, corner_y, corner_z in face.corners:
            corner_samples.append(
                (axis.along_axis(corner_x, corner_z), corner_y)
            )
    if not corner_samples:
        return []
    along_positions = [sample[0] for sample in corner_samples]
    along_minimum = min(along_positions)
    along_maximum = max(along_positions)
    span = max(along_maximum - along_minimum, 1e-9)
    bin_count = max(1, int(math.ceil(span / BRIDGE_PROFILE_BIN_LENGTH_M)))
    maximum_by_bin: dict[int, float] = {}
    for along, height in corner_samples:
        bin_index = min(
            bin_count - 1, int((along - along_minimum) / span * bin_count)
        )
        known = maximum_by_bin.get(bin_index)
        if known is None or height > known:
            maximum_by_bin[bin_index] = height
    # Fill empty bins by interpolating between the nearest filled bins.
    filled_indices = sorted(maximum_by_bin)
    profile: list[tuple[float, float]] = []
    bin_width = span / bin_count
    for bin_index in range(bin_count):
        along_center = along_minimum + (bin_index + 0.5) * bin_width
        if bin_index in maximum_by_bin:
            profile.append((along_center, maximum_by_bin[bin_index]))
            continue
        earlier = [index for index in filled_indices if index < bin_index]
        later = [index for index in filled_indices if index > bin_index]
        if earlier and later:
            left, right = earlier[-1], later[0]
            fraction = (bin_index - left) / (right - left)
            interpolated = maximum_by_bin[left] + fraction * (
                maximum_by_bin[right] - maximum_by_bin[left]
            )
        elif earlier:
            interpolated = maximum_by_bin[earlier[-1]]
        else:
            interpolated = maximum_by_bin[later[0]]
        profile.append((along_center, interpolated))
    return profile


def _abutment_reaches_grade_per_end(
    axis: _DeckAxis,
    grounded_vertices_xz: Sequence[tuple[float, float, str]],
) -> tuple[bool, bool]:
    """Amendment A4's viaduct guard, per deck end: does solid geometry of
    ANY hardness reach effective grade within
    :data:`ABUTMENT_GRADE_SEARCH_RADIUS_M` of the end?

    The test point is the abutment line's MIDPOINT (the radius constant
    was calibrated against midpoint distances — see its comment).  The
    DECK need not reach grade: at deck-carried KBNA the deck ends at +6
    while the abutment EMBANKMENT cladding grounds at 0 a few metres away
    — grounded geometry NEAR the end is the signature; a piered viaduct
    (KMCO via_tren, global minimum +3.45) has none anywhere."""
    results = []
    for (start_point, end_point) in axis.abutment_lines:
        midpoint_x = (start_point[0] + end_point[0]) / 2.0
        midpoint_z = (start_point[1] + end_point[1]) / 2.0
        reaches = any(
            math.hypot(grounded_x - midpoint_x, grounded_z - midpoint_z)
            <= ABUTMENT_GRADE_SEARCH_RADIUS_M
            for grounded_x, grounded_z, _resource in grounded_vertices_xz
        )
        results.append(reaches)
    while len(results) < 2:
        results.append(False)
    return results[0], results[1]


def _pavement_coverage_of_mid_deck(
    deck_polygon: Polygon,
    axis: _DeckAxis,
    pavement_frame_union: Polygon | None,
) -> float | None:
    """Fraction of the deck's mid-span band covered by pavement (spec
    section 2.3).  ``None`` when no pavement is supplied.

    The band is the middle THIRD along the deck axis and the central
    :data:`BRIDGE_COVERAGE_BAND_WIDTH_FRACTION` of the deck ACROSS it —
    the across-axis narrowing is the round-5 KBNA calibration (see the
    constant's comment: lateral at-grade taxiways lap the deck's side
    edges and are not span-crossing evidence)."""
    if pavement_frame_union is None:
        return None
    try:
        along_center = axis.length_m / 2.0
        along_half = axis.length_m / 6.0
        unit = axis.axis_unit_xz
        perpendicular = (-unit[1], unit[0])
        origin = axis.axis_origin_xz
        # Centre the band's across coordinate on the deck centroid — the
        # axis origin is a rectangle corner and the deck may extend to
        # either perpendicular side of it.
        centroid = deck_polygon.centroid
        across_center = (centroid.x - origin[0]) * perpendicular[0] + (
            centroid.y - origin[1]
        ) * perpendicular[1]
        across_half = (
            axis.width_m * BRIDGE_COVERAGE_BAND_WIDTH_FRACTION / 2.0
        )
        band_corners = []
        for along in (along_center - along_half, along_center + along_half):
            for across in (
                across_center - across_half,
                across_center + across_half,
            ):
                band_corners.append(
                    (
                        origin[0]
                        + along * unit[0]
                        + across * perpendicular[0],
                        origin[1]
                        + along * unit[1]
                        + across * perpendicular[1],
                    )
                )
        band = Polygon(
            [
                band_corners[0],
                band_corners[1],
                band_corners[3],
                band_corners[2],
            ]
        )
        mid_deck = deck_polygon.intersection(band)
        if mid_deck.is_empty or mid_deck.area <= 0.0:
            return None
        covered = mid_deck.intersection(pavement_frame_union).area
        return covered / mid_deck.area
    except (ValueError, _GEOS_EXCEPTION):
        return None


def _profile_is_non_flat(
    crest_y_m: float,
    deck_end_elevations_y_m: tuple[float, float],
) -> bool:
    """Amendment A4's non-flat test, per the round-3 supervisor ruling: the
    crest stands at least :data:`BRIDGE_PROFILE_NON_FLAT_MIN_M` above the
    LOWER profile end.  Crowned KMCO humps AND monotone ramps (EDDF A3)
    qualify; flat KBNA/EDDF decks do not — see the constant's comment."""
    return (
        crest_y_m - min(deck_end_elevations_y_m)
        >= BRIDGE_PROFILE_NON_FLAT_MIN_M
    )


def _classify_contract(
    crest_y_m: float,
    deck_end_elevations_y_m: tuple[float, float],
    coverage_fraction: float | None,
) -> str:
    """Deck-carried / terrain-carried / profile-carried / ambiguous (spec
    sections 2.3 and 3.2, amended by A4; refusal-not-guessing per R5).

    With pavement coverage: near-zero coverage (pavement cut at the
    abutments) is deck-carried, cross-checked against crest height;
    continuous coverage splits on the measured profile — non-flat ⇒
    PROFILE_CARRIED (the deck profile is the pavement's elevation target;
    flat-across handling would erase the KMCO humps), flat ⇒
    TERRAIN_CARRIED, cross-checked (a flat deck standing high above grade
    with pavement draping across contradicts itself ⇒ AMBIGUOUS).  The
    dead band between the coverage thresholds is AMBIGUOUS.

    Without pavement (coverage ``None``): a non-flat profile with grounded
    abutments (guaranteed upstream — viaducts are refused before this
    point) ⇒ PROFILE_CARRIED; otherwise the crest-height cross-check
    alone."""
    non_flat = _profile_is_non_flat(crest_y_m, deck_end_elevations_y_m)
    height_says_deck_carried = crest_y_m >= BRIDGE_DECK_CARRIED_MIN_HEIGHT_M

    if coverage_fraction is None:
        if non_flat:
            return PROFILE_CARRIED
        return DECK_CARRIED if height_says_deck_carried else TERRAIN_CARRIED

    if coverage_fraction <= BRIDGE_CONTRACT_PAVEMENT_COVERAGE_DECK_CARRIED_MAX:
        return DECK_CARRIED if height_says_deck_carried else AMBIGUOUS
    if (
        coverage_fraction
        >= BRIDGE_CONTRACT_PAVEMENT_COVERAGE_TERRAIN_CARRIED_MIN
    ):
        if non_flat:
            return PROFILE_CARRIED
        return AMBIGUOUS if height_says_deck_carried else TERRAIN_CARRIED
    return AMBIGUOUS


def contract_refusal_reason(
    contract: str,
    contract_evidence: str,
    deck_hardness: str,
    deck_length_m: float,
    deck_width_m: float,
    deck_area_m2: float,
    girder_clearance_m: float | None,
) -> str | None:
    """THE CONTRACT REFUSAL (docs/specs/kdfw-bridge-refusal-spec.md
    clause 1) — the reason this verdict may not become a terrain feature,
    or ``None`` when it may.

    Two laws, both judged HERE, at classification, because a refused
    contract emits NOTHING (no trench, no corridor, no pins) and every
    one of those is downstream of the record's existence.  The caller
    turns a reason into a :class:`RefusedStructure`, which is the module's
    established "recognized but refused a terrain FEATURE" channel
    (amendment A4's piered viaduct, round-5's island tunnel deck).

    **1. IMPLAUSIBLE DECK SCALE ON PROFILE-FALLBACK EVIDENCE.**  A
    :data:`DECK_CARRIED` verdict reached WITHOUT pavement evidence
    (:data:`CONTRACT_EVIDENCE_DECK_PROFILE`) rests on the crest test
    alone, and the crest test cannot tell a bridge from an airport-sized
    slab authored 8 m above its anchor.  So the scale bounds are the
    missing evidence: over
    :data:`BRIDGE_FALLBACK_MAX_DECK_LENGTH_M` long, over
    :data:`BRIDGE_FALLBACK_MAX_DECK_WIDTH_M` wide, or over
    :data:`BRIDGE_FALLBACK_MAX_DECK_AREA_M2` in plan is not a deck.
    SCOPED TO THE FALLBACK deliberately: a span with measured pavement
    coverage has real evidence for its contract and is not judged on its
    size.

    **2. GIRDER CLEARANCE UNDER THE MINIMUM (amendment A10 becomes a
    gate).**  ``BRIDGE_ROAD_CLEARANCE_MINIMUM_M`` was an emit-time WARN
    that emitted anyway ("audit required").  A structure whose modelled
    girder line stands less than that above the floor its own deck datum
    implies is not a crossing traffic passes under, and pinning terrain
    to it digs a corridor no vehicle fits through.  ``girder_clearance_m``
    is the caller's ``clearance_underside_y_m`` — IDENTICALLY the
    quantity the emit-time check computes, since
    ``_bridge_girder_underside_m`` − ``_bridge_corridor_floor_m`` cancels
    the deck datum and the crest and leaves exactly the underside height
    in the structure frame.  ``None`` refuses nothing: a missing
    measurement is honest, and the WARN it replaces was likewise skipped.

    A GIRDER LINE, NOT ANY UNDERSIDE.  The emit-time check falls back to
    the slab ``ceiling_y_m`` when no girder line was found; a REFUSAL may
    not, and the corpus is why.  ``clearance_underside_y_m`` is by
    construction a plane above :data:`CLEARANCE_MINIMUM_OPENING_HEIGHT_M`
    — one that could roof an opening — while ``ceiling_y_m`` is merely
    the largest-area underside, which on the cosmetic road-bridge class
    is soft geometry lying AT or BELOW grade.  Measured over every cached
    classification in the shared data repo (2026-08-16): all three OTHH
    viaduct records and one KMCI record expose NO girder line and carry
    ceiling values of −5.84 / −0.93 / −0.49 / −0.92 m, so a fallback
    reading would refuse the bridge FIXTURE airport's REAL viaducts on a
    number that is not a clearance at all.  That is the "two instruments,
    one assumed population" trap; the law says girder.

    SCOPE of law 2 is the CORRIDOR SET — the contracts A10's warning
    could ever fire on (``bridges._partition_bridges_for_corridors``:
    DECK_CARRIED plus every cosmetic deck).  A terrain- or
    profile-carried span has pavement draping across it and no corridor
    is ever dug beneath, so its underside height limits nothing and
    refusing it on that number would be a new law, not this one."""
    corridor_shaped = (
        contract == DECK_CARRIED or deck_hardness == DECK_HARDNESS_COSMETIC
    )
    if (
        contract == DECK_CARRIED
        and contract_evidence == CONTRACT_EVIDENCE_DECK_PROFILE
    ):
        over = []
        if deck_length_m > BRIDGE_FALLBACK_MAX_DECK_LENGTH_M:
            over.append(
                f"length {deck_length_m:,.1f} m over "
                f"{BRIDGE_FALLBACK_MAX_DECK_LENGTH_M:,.0f} m"
            )
        if deck_width_m > BRIDGE_FALLBACK_MAX_DECK_WIDTH_M:
            over.append(
                f"width {deck_width_m:,.1f} m over "
                f"{BRIDGE_FALLBACK_MAX_DECK_WIDTH_M:,.0f} m"
            )
        if deck_area_m2 > BRIDGE_FALLBACK_MAX_DECK_AREA_M2:
            over.append(
                f"area {deck_area_m2:,.0f} m² over "
                f"{BRIDGE_FALLBACK_MAX_DECK_AREA_M2:,.0f} m²"
            )
        if over:
            return (
                f"{BRIDGE_REFUSAL_IMPLAUSIBLE_DECK}: DECK_CARRIED on "
                f"{CONTRACT_EVIDENCE_DECK_PROFILE} evidence at "
                f"implausible deck scale ({'; '.join(over)}) — refused, "
                "no terrain feature (KDFW inset-slab class)"
            )
    if corridor_shaped and girder_clearance_m is not None:
        from .config import BRIDGE_ROAD_CLEARANCE_MINIMUM_M
        minimum = float(BRIDGE_ROAD_CLEARANCE_MINIMUM_M)
        if float(girder_clearance_m) < minimum - 1e-6:
            return (
                f"{BRIDGE_REFUSAL_CLEARANCE_UNDER_MINIMUM}: girder "
                f"clearance {float(girder_clearance_m):.2f} m under the "
                f"{minimum} m minimum — refused, no corridor and no "
                "terrain feature (amendment A10 is a gate)"
            )
    return None


def _refused_deck_members(deck_faces) -> tuple:
    """One :class:`RefusedDeckMember` per RESOURCE contributing deck
    faces, each with its OWN axis end lines and its OWN effective crest
    (round-12 amendment 3).

    Measured exactly as the whole-structure record is — same union, same
    axis, same profile helpers — only per resource, so nothing here is a
    second way of finding a deck end.  A member whose faces will not
    close into a polygon or will not yield an axis (a sliver, a single
    triangle) is simply absent: it contributes no grade, and the family's
    other members still speak.  Sorted by resource path so the record,
    the cache and the twins all agree on order."""
    faces_by_resource: dict = {}
    for face in deck_faces:
        faces_by_resource.setdefault(face.resource_path, []).append(face)

    members: list = []
    for resource_path in sorted(faces_by_resource):
        member_faces = faces_by_resource[resource_path]
        polygon = _union_horizontal(
            member_faces, close_m=BRIDGE_DECK_CLOSE_M, keep_all_parts=True
        )
        if polygon is None:
            continue
        member_axis = _deck_axis(polygon)
        if member_axis is None:
            continue
        profile = _deck_top_profile(member_faces, member_axis)
        if not profile:
            continue
        members.append(
            RefusedDeckMember(
                resource_path=resource_path,
                abutment_lines=list(member_axis.abutment_lines),
                deck_top_y_m=max(height for _along, height in profile),
            )
        )
    return tuple(members)


def _widen_refusal_to_component(
    refusal: "RefusedStructure", component
) -> "RefusedStructure":
    """The refusal record as the result carries it: the reason and the
    deck measurements from :func:`_classify_bridge`, over the WHOLE
    refused component.

    The component is the family (R12-2): every resource the pool pass
    judged together, deck parts and piers and railings alike.  A seat
    that took only the deck parts would leave the piers behind at a
    different altitude — the very tear this record exists to prevent."""
    return RefusedStructure(
        object_resources=sorted(component),
        reason=refusal.reason,
        deck_object_resources=refusal.deck_object_resources,
        anchor_longitude_latitude=refusal.anchor_longitude_latitude,
        frame_origin_longitude_latitude=(
            refusal.frame_origin_longitude_latitude),
        abutment_lines=refusal.abutment_lines,
        deck_top_y_m=refusal.deck_top_y_m,
        deck_members=refusal.deck_members,
    )


def _classify_bridge(
    placements: Sequence[ObjectPlacement],
    frame: _StructureFrame,
    pavement_frame_union: Polygon | None,
    mean_sea_level_placements: Sequence[ObjectPlacement],
) -> tuple[BridgeStructure | None, "RefusedStructure | None"]:
    """Classify one pool as a bridge.

    Returns ``(bridge, None)`` on success, ``(None, None)`` when the pool
    is simply not bridge-like, and ``(None, refusal)`` when the pool IS
    bridge-like but must be REFUSED a terrain feature (amendment A4's
    piered-viaduct guard).

    The refusal record carries the deck measurements taken before the
    guard fired (R12-2) and a PROVISIONAL ``object_resources`` — the deck
    faces.  The caller widens it to the whole refused component, which is
    the family that seats together."""
    near_horizontal = [
        triangle
        for triangle in frame.triangles
        if triangle.horizontality >= NEAR_HORIZONTAL_NORMAL_Y_MIN
    ]
    if not near_horizontal:
        return None, None

    # Amendment A4: drivable decks may be plain ATTR_hard (KMCO, the EDDF
    # A3 ramp) — accept both hard kinds as first-class deck faces.
    hard_faces = [
        triangle for triangle in near_horizontal if triangle.is_hard
    ]
    structure_has_hard_geometry = any(
        triangle.is_hard for triangle in frame.triangles
    )
    # ``deck_faces`` is the whole drivable surface (union → deck polygon,
    # corner samples → profile).  A sloped/crowned deck spans many height
    # bins, so the polygon must never be cut to one bin — that fragmented
    # KBNA taxiway-L to 55 m of its 131 m length.
    deck_faces: list[_FrameTriangle]

    if sum(face.area_m2 for face in hard_faces) >= BRIDGE_MIN_DECK_AREA_M2:
        deck_faces = hard_faces
        hard_deck_area = sum(
            face.area_m2
            for face in hard_faces
            if face.hardness == "hard_deck"
        )
        plain_hard_area = sum(
            face.area_m2 for face in hard_faces if face.hardness == "hard"
        )
        # Dominant kind by area; ``hard_deck`` (the R8 flush-seating key)
        # is True only for genuine ATTR_hard_deck decks.
        deck_hardness = (
            DECK_HARDNESS_HARD_DECK
            if hard_deck_area >= plain_hard_area
            else DECK_HARDNESS_HARD
        )
    elif not structure_has_hard_geometry:
        # Cosmetic path (Murfreesboro class), for structures with NO hard
        # triangles anywhere: a broad near-horizontal surface well above
        # grade, ground contact, and a "bridge" name hint.
        name_hint = any(
            COSMETIC_BRIDGE_NAME_HINT in placement.resource_path.lower()
            for placement in placements
        )
        grounds = (
            frame.minimum_effective_height_m <= GROUND_CONTACT_TOLERANCE_M
        )
        if not name_hint or not grounds:
            # Tested BEFORE any face pass: on a mega-pool frame each pass
            # walks millions of triangles, and a structure failing these
            # two can never be a cosmetic bridge whatever its faces say.
            return None, None
        elevated_faces = [
            triangle
            for triangle in near_horizontal
            if triangle.height_m >= BRIDGE_DECK_CARRIED_MIN_HEIGHT_M
        ]
        if (
            sum(face.area_m2 for face in elevated_faces)
            < BRIDGE_MIN_DECK_AREA_M2
        ):
            # LOW-BRIDGE LIMB (owner ruling 2026-07-31: "all the bridges
            # you highlighted are above ground bridges … they just need to
            # be set so their top edge at either end is flush with
            # grade").  The +2 m floor asks "is there a deck standing well
            # ABOVE grade?", which is the wrong question for a road bridge
            # that crosses at grade: measured at OTHH, Bridge_04 carries
            # 0 m² above +2 m and Bridge_05 46 m² — yet 1 937 and 3 036 m²
            # of deck at or above grade.  Bridge_01, the owner's headline
            # case, carries 43 m² above +2 m against 6 333 m² of deck.
            # Retry against the AT-GRADE band, which is what "flush with
            # grade" means.
            #
            # STRICTLY ADDITIVE: the retry runs only when the +2 m set has
            # already failed, so every structure that classifies today
            # classifies identically (verified byte-for-byte on KBNA's two
            # Murfreesboro cosmetic decks and every other installed pack).
            elevated_faces = [
                triangle
                for triangle in near_horizontal
                if triangle.height_m >= -GROUND_CONTACT_TOLERANCE_M
            ]
        if (
            sum(face.area_m2 for face in elevated_faces)
            < BRIDGE_MIN_DECK_AREA_M2
        ):
            return None, None
        # With no hard attribute to say WHICH elevated surface is drivable,
        # the causeway top is the dominant elevated plane; taking all
        # elevated faces would let truss tops and superstructure rails
        # inflate the profile crest (KBNA Murfreesboro: rails at +11.8 over
        # a +7.4 causeway).
        plane = _dominant_height_plane(elevated_faces)
        if plane is None:
            return None, None
        _plane_height, deck_faces = plane
        deck_hardness = DECK_HARDNESS_COSMETIC
    else:
        # Hard geometry exists but under the deck-area floor: railings and
        # clutter, not a bridge.
        return None, None

    deck_polygon = _union_horizontal(
        deck_faces, close_m=BRIDGE_DECK_CLOSE_M, keep_all_parts=True
    )
    if deck_polygon is None:
        return None, None

    axis = _deck_axis(deck_polygon)
    if axis is None:
        return None, None

    deck_top_profile = _deck_top_profile(deck_faces, axis)
    if not deck_top_profile:
        return None, None
    deck_end_elevations_y_m = (
        deck_top_profile[0][1],
        deck_top_profile[-1][1],
    )
    crest_y_m = max(height for _along, height in deck_top_profile)

    # Amendment A4's viaduct guard: refuse (never emit) a structure whose
    # solid geometry fails to reach grade near EITHER deck end — a deck-end
    # pin there would build a false causeway (KMCO via_tren).
    abutment_reaches_grade = _abutment_reaches_grade_per_end(
        axis, frame.grounded_vertices_xz
    )
    if not all(abutment_reaches_grade):
        failing_ends = [
            "start" if index == 0 else "far"
            for index, reaches in enumerate(abutment_reaches_grade)
            if not reaches
        ]
        reason = (
            "piered viaduct: no solid geometry reaches effective grade "
            f"(≤ {GROUND_CONTACT_TOLERANCE_M} m) within "
            f"{ABUTMENT_GRADE_SEARCH_RADIUS_M:.0f} m of the "
            f"{' and '.join(failing_ends)} deck end(s) — refused, no "
            "terrain feature (amendment A4)"
        )
        # R12-2: the deck WAS measured before the guard fired — axis,
        # abutment lines, crest — so the refusal carries them and the
        # post-mesh law can seat this family as one rigid body instead
        # of leaving it to the per-structure y-bake.  Refusing a terrain
        # FEATURE and refusing to know where the deck is are two
        # different acts; only the first one is amendment A4's.
        deck_resources = sorted({face.resource_path for face in deck_faces})
        reference_placement = next(
            (
                placement
                for placement in placements
                if placement.resource_path in set(deck_resources)
            ),
            placements[0],
        )
        return None, RefusedStructure(
            object_resources=deck_resources,
            reason=reason,
            deck_object_resources=deck_resources,
            anchor_longitude_latitude=(
                reference_placement.longitude,
                reference_placement.latitude,
            ),
            frame_origin_longitude_latitude=(
                frame.origin_longitude,
                frame.origin_latitude,
            ),
            abutment_lines=list(axis.abutment_lines),
            deck_top_y_m=crest_y_m,
            # AMENDMENT 3: what the SEAT measures from.  Per member, in
            # the same frame — its own deck footprint, its own axis, its
            # own crest.
            deck_members=_refused_deck_members(deck_faces),
        )

    # Underside planes: candidates are near-horizontal faces under the deck
    # footprint that sit a clear gap below the LOCAL deck top (the profile
    # value at their axis position — a crowned deck's own ramp faces are AT
    # the profile and must not read as their own ceiling).
    along_positions = [along for along, _height in deck_top_profile]
    profile_heights = [height for _along, height in deck_top_profile]

    def _local_deck_top(x: float, z: float) -> float:
        along = axis.along_axis(x, z)
        best_index = min(
            range(len(along_positions)),
            key=lambda index: abs(along_positions[index] - along),
        )
        return profile_heights[best_index]

    underside_candidates = [
        triangle
        for triangle in near_horizontal
        if deck_polygon.contains(Point(triangle.centroid_xz))
        and triangle.height_m
        <= _local_deck_top(*triangle.centroid_xz)
        - CEILING_MINIMUM_GAP_BELOW_DECK_M
    ]
    # ceiling_y_m: the LARGEST-area underside plane (the slab underside).
    ceiling_plane = _dominant_height_plane(underside_candidates)
    ceiling_y_m = ceiling_plane[0] if ceiling_plane is not None else None
    # clearance_underside_y_m: the LOWEST underside plane above the opening
    # with real area — the value that limits corridor clearance (KBNA:
    # girder line +4.2 versus slab underside +4.8).
    clearance_underside_y_m = _lowest_underside_plane(underside_candidates)

    coverage_fraction = _pavement_coverage_of_mid_deck(
        deck_polygon, axis, pavement_frame_union
    )
    contract = _classify_contract(
        crest_y_m, deck_end_elevations_y_m, coverage_fraction
    )
    contract_evidence = (
        CONTRACT_EVIDENCE_PAVEMENT_COVERAGE
        if coverage_fraction is not None
        else CONTRACT_EVIDENCE_DECK_PROFILE
    )

    # ── CONTRACT REFUSAL (docs/specs/kdfw-bridge-refusal-spec.md clause
    # 1) ─────────────────────────────────────────────────────────────
    # The last gate before the record exists, and therefore the only
    # place "emits nothing — no trench, no corridor, no pins" can be
    # spelled once: every emitter downstream reads the classification,
    # and none of them can un-emit.  Same channel as amendment A4's
    # viaduct guard above.
    # THE GIRDER LINE ONLY (never the ``ceiling_y_m`` slab fallback the
    # emit-time A10 check accepts) — see the predicate's docstring: the
    # fallback is not a clearance on the cosmetic road-bridge class and
    # would refuse OTHH's real viaducts on a below-grade number.
    girder_clearance_m = clearance_underside_y_m
    refusal_reason = contract_refusal_reason(
        contract,
        contract_evidence,
        deck_hardness,
        float(axis.length_m),
        float(axis.width_m),
        float(deck_polygon.area),
        girder_clearance_m,
    )
    if refusal_reason is not None:
        deck_resources = sorted({face.resource_path for face in deck_faces})
        reference_placement = next(
            (
                placement
                for placement in placements
                if placement.resource_path in set(deck_resources)
            ),
            placements[0],
        )
        clearance_text = (
            "none" if girder_clearance_m is None
            else f"{float(girder_clearance_m):.2f} m"
        )
        _vprint(
            1,
            "   [object-bridge] contract REFUSED for "
            f"{', '.join(deck_resources)} — {refusal_reason} "
            f"[deck {axis.length_m:,.1f} x {axis.width_m:,.1f} m, "
            f"{deck_polygon.area:,.0f} m², crest {crest_y_m:.2f} m, "
            f"clearance {clearance_text}, contract {contract} on "
            f"{contract_evidence}]",
        )
        # WHICH MEASUREMENTS RIDE ALONG (R12-2).  A clearance refusal is
        # still a bridge — a real deck whose modelled crossing is too
        # tight — so its family keeps the rigid deck-top seat, exactly as
        # the refused piered viaduct does.  A SCALE refusal is the
        # opposite claim: the premise is that this union is not a deck at
        # all, so carrying its axis and crest into the post-mesh seat
        # would feed the seat the very measurement the refusal rejects
        # (the round-5 island-tunnel refusal carries none either, for the
        # same reason).  ``has_measurable_deck`` then routes it to the
        # generic y-bake, which is where an unrecognized structure
        # belongs.
        if refusal_reason.startswith(BRIDGE_REFUSAL_IMPLAUSIBLE_DECK):
            return None, RefusedStructure(
                object_resources=deck_resources,
                reason=refusal_reason,
            )
        return None, RefusedStructure(
            object_resources=deck_resources,
            reason=refusal_reason,
            deck_object_resources=deck_resources,
            anchor_longitude_latitude=(
                reference_placement.longitude,
                reference_placement.latitude,
            ),
            frame_origin_longitude_latitude=(
                frame.origin_longitude,
                frame.origin_latitude,
            ),
            abutment_lines=list(axis.abutment_lines),
            deck_top_y_m=crest_y_m,
            deck_members=_refused_deck_members(deck_faces),
        )

    absolute_deck_elevation_m = _median_msl_on_deck(
        deck_polygon,
        frame.origin_latitude,
        frame.origin_longitude,
        mean_sea_level_placements,
    )

    # Round-5 mega-pool refinement: the record carries — and the R4
    # exclusion list receives — ONLY the resources whose geometry actually
    # contributes to the bridge: the deck faces and the underside planes
    # (the latter capture the trench cladding lining the corridor beneath
    # the span — EDDF's Tunnel_N).  Pool co-members (jetways, clutter,
    # passing ground slabs near the abutments) never ride along; grounded
    # geometry stays abutment-test EVIDENCE without becoming a record
    # member, because any grounded clutter within the search radius of an
    # end would otherwise be excluded from the Phase 2 y-bake.
    contributing_resources = {face.resource_path for face in deck_faces}
    contributing_resources.update(
        triangle.resource_path
        for triangle in underside_candidates
        # Structure undersides only: girder/slab planes above the opening
        # (elevated decks) or below-grade trench cladding (flush decks,
        # EDDF Tunnel_N floors at −1).  The band between is at-grade
        # ground furniture passing beneath the span — terrain, not
        # structure, and it must stay y-bakeable.
        if triangle.height_m > CLEARANCE_MINIMUM_OPENING_HEIGHT_M
        or triangle.height_m < -GROUND_CONTACT_TOLERANCE_M
    )

    reference_placement = next(
        (
            placement
            for placement in placements
            if placement.resource_path in contributing_resources
        ),
        placements[0],
    )
    return (
        BridgeStructure(
            object_resources=sorted(contributing_resources),
            anchor_longitude_latitude=(
                reference_placement.longitude,
                reference_placement.latitude,
            ),
            frame_origin_longitude_latitude=(
                frame.origin_longitude,
                frame.origin_latitude,
            ),
            heading_degrees=reference_placement.heading_degrees,
            deck_polygon=deck_polygon,
            deck_top_profile=deck_top_profile,
            deck_top_y_m=crest_y_m,
            deck_end_elevations_y_m=deck_end_elevations_y_m,
            deck_length_m=axis.length_m,
            deck_width_m=axis.width_m,
            ceiling_y_m=ceiling_y_m,
            clearance_underside_y_m=clearance_underside_y_m,
            abutment_lines=list(axis.abutment_lines),
            abutment_reaches_grade=abutment_reaches_grade,
            contract=contract,
            absolute_deck_elevation_m=absolute_deck_elevation_m,
            hard_deck=deck_hardness == DECK_HARDNESS_HARD_DECK,
            deck_hardness=deck_hardness,
            pavement_coverage_fraction=coverage_fraction,
            contract_evidence=contract_evidence,
        ),
        None,
    )


def _lowest_underside_plane(
    underside_candidates: Sequence[_FrameTriangle],
) -> float | None:
    """The LOWEST height bin among underside candidates that (a) carries at
    least :data:`CLEARANCE_PLANE_MINIMUM_AREA_M2` of face area and (b) sits
    high enough to roof an opening
    (above :data:`CLEARANCE_MINIMUM_OPENING_HEIGHT_M` — planes near grade
    are embankment/ground furniture, not a girder line) — the
    clearance-limiting value for the corridor emitter."""
    area_by_bin: dict[int, float] = {}
    members_by_bin: dict[int, list[_FrameTriangle]] = {}
    for triangle in underside_candidates:
        if triangle.height_m <= CLEARANCE_MINIMUM_OPENING_HEIGHT_M:
            continue
        bin_key = round(triangle.height_m / PLANE_HEIGHT_BIN_M)
        area_by_bin[bin_key] = (
            area_by_bin.get(bin_key, 0.0) + triangle.area_m2
        )
        members_by_bin.setdefault(bin_key, []).append(triangle)
    qualifying = [
        bin_key
        for bin_key, area in area_by_bin.items()
        if area >= CLEARANCE_PLANE_MINIMUM_AREA_M2
    ]
    if not qualifying:
        return None
    lowest_bin = min(qualifying)
    members = members_by_bin[lowest_bin]
    total_area = sum(triangle.area_m2 for triangle in members)
    return (
        sum(triangle.height_m * triangle.area_m2 for triangle in members)
        / total_area
    )


def _median_msl_on_deck(
    deck_polygon: Polygon,
    origin_latitude: float,
    origin_longitude: float,
    mean_sea_level_placements: Sequence[ObjectPlacement],
) -> float | None:
    """Median absolute elevation of the OBJECT_MSL fixtures inside the deck
    polygon (KBNA taxiway-L: twelve fixtures cluster at 166.9994 m)."""
    on_deck: list[float] = []
    for placement in mean_sea_level_placements:
        if placement.mean_sea_level_elevation_m is None:
            continue
        frame_x, frame_z = obj8_reader.lonlat_to_local_offset(
            origin_latitude,
            origin_longitude,
            0.0,
            placement.latitude,
            placement.longitude,
        )
        if deck_polygon.contains(Point((frame_x, frame_z))):
            on_deck.append(placement.mean_sea_level_elevation_m)
    if not on_deck:
        return None
    return median(on_deck)


# ---------------------------------------------------------------------------
# Feature C — structure ground interfaces (spec section 3.4, A5-A8, R10)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _BelowGradeHardEnclosure:
    """The interior-cutout trigger evidence (R10/A8): the below-grade
    drivable content, the at-grade plan footprint, and how much of the
    former the latter encloses."""

    enclosure_fraction: float
    below_grade_hard_union: object   # shapely geometry, frame metres
    at_grade_footprint: object       # shapely geometry, frame metres
    hard_content_minimum_y_m: float


def _below_grade_hard_enclosure(
    frame: _StructureFrame,
) -> _BelowGradeHardEnclosure | None:
    """Evidence for the R10 interior-cutout trigger, or ``None`` when the
    structure has no meaningful below-grade drivable content.

    The below-grade hard content is the same face set the tunnel signature
    tests (hard faces at or below :data:`TUNNEL_MIN_BODY_DEPTH_M`, area at
    least :data:`TUNNEL_MIN_BELOW_GRADE_DECK_AREA_M2`) — deliberately, so
    ENCLOSURE is the single discriminator between the two rules (A8: the
    same drivable-below-grade signature fires on EGLL tunnels and KDEN
    train halls; the decks are open at the mouths, the platforms are 100%
    enclosed).  The floor value is the HARD content's minimum corner y —
    never the deepest solid (the KDEN −19 m foundation-pile trap)."""
    below_grade_hard_mask = (
        (frame.triangle_hardness_codes > 0)
        & (frame.triangle_horizontality >= NEAR_HORIZONTAL_NORMAL_Y_MIN)
        & (frame.triangle_height_m <= -TUNNEL_MIN_BODY_DEPTH_M)
    )
    if (
        float(frame.triangle_area_m2[below_grade_hard_mask].sum())
        < TUNNEL_MIN_BELOW_GRADE_DECK_AREA_M2
    ):
        return None
    below_union = _union_horizontal_coordinates(
        frame.triangle_corner_coordinates_xz(below_grade_hard_mask),
        keep_all_parts=True,
    )
    if below_union is None:
        return None
    hard_content_minimum_y_m = float(
        frame.triangle_corner_y_m[below_grade_hard_mask].min()
    )
    at_grade_mask = frame.triangle_height_m >= -TUNNEL_ROOF_TOP_TOLERANCE_M
    if not at_grade_mask.any():
        at_grade_footprint = None
    else:
        # Every consumer of the at-grade footprint intersects it with
        # the below-grade union, so only at-grade faces near that union
        # can influence any output.  The morphological close reads
        # geometry within twice its radius of any point it shapes; a
        # five-radius margin is a strict superset of that influence
        # zone, so the restricted union is EXACT wherever it is
        # evaluated.
        margin = 5.0 * AT_GRADE_FOOTPRINT_CLOSE_M
        minimum_x, minimum_z, maximum_x, maximum_z = below_union.bounds
        near_mask = (
            at_grade_mask
            & (frame.triangle_corner_x_m.min(axis=1) <= maximum_x + margin)
            & (frame.triangle_corner_x_m.max(axis=1) >= minimum_x - margin)
            & (frame.triangle_corner_z_m.min(axis=1) <= maximum_z + margin)
            & (frame.triangle_corner_z_m.max(axis=1) >= minimum_z - margin)
        )
        if near_mask.any():
            at_grade_footprint = _union_horizontal_coordinates(
                frame.triangle_corner_coordinates_xz(near_mask),
                close_m=AT_GRADE_FOOTPRINT_CLOSE_M,
                keep_all_parts=True,
            )
        else:
            # At-grade faces exist but none near the below-grade union:
            # a computed-and-disjoint footprint, never an "absent" one
            # (absence would hand the record the WHOLE below union).
            at_grade_footprint = Polygon()
    if at_grade_footprint is None:
        enclosure_fraction = 0.0
    else:
        try:
            enclosed_area = below_union.intersection(at_grade_footprint).area
        except (ValueError, _GEOS_EXCEPTION):
            enclosed_area = 0.0
        enclosure_fraction = (
            enclosed_area / below_union.area if below_union.area > 0 else 0.0
        )
    return _BelowGradeHardEnclosure(
        enclosure_fraction=enclosure_fraction,
        below_grade_hard_union=below_union,
        at_grade_footprint=at_grade_footprint,
        hard_content_minimum_y_m=hard_content_minimum_y_m,
    )


def _cluster_interface_levels(
    sector_low_envelopes: dict[int, float],
    wall_column_bases: Sequence[tuple[float, frozenset[str]]],
    dominant_area_resource: str | None,
) -> list[tuple[float, tuple[int, ...], float]]:
    """Cluster per-sector low envelopes into interface levels (A5) with
    the A7 dominant-area exception.

    ``sector_low_envelopes`` maps occupied sector index → low-envelope y.
    Levels are clustered at :data:`INTERFACE_LEVEL_CLUSTER_M`; a level
    below :data:`INTERFACE_LEVEL_MIN_PERIMETER_SHARE` of the occupied
    sectors is dropped as a parasite — EXCEPT a below-grade level carried
    by the dominant-area object (its wall columns include a base within
    the cluster band), which must survive (A7: the T1 main floor died to
    this filter before the exception).  Returns ``(level_y_m,
    sector_indices, perimeter_share)`` tuples, deepest level first."""
    if not sector_low_envelopes:
        return []
    members_by_bucket: dict[int, list[int]] = {}
    for sector_index, low_envelope in sector_low_envelopes.items():
        bucket = round(low_envelope / INTERFACE_LEVEL_CLUSTER_M)
        members_by_bucket.setdefault(bucket, []).append(sector_index)
    occupied_sector_count = len(sector_low_envelopes)
    levels: list[tuple[float, tuple[int, ...], float]] = []
    for bucket, sector_indices in members_by_bucket.items():
        level_y_m = sum(
            sector_low_envelopes[index] for index in sector_indices
        ) / len(sector_indices)
        perimeter_share = len(sector_indices) / occupied_sector_count
        if perimeter_share < INTERFACE_LEVEL_MIN_PERIMETER_SHARE:
            dominant_carries_level = (
                dominant_area_resource is not None
                and level_y_m <= -INTERFACE_LEVEL_CLUSTER_M
                and any(
                    abs(base - level_y_m) <= INTERFACE_LEVEL_CLUSTER_M
                    and dominant_area_resource in resources
                    for base, resources in wall_column_bases
                )
            )
            if not dominant_carries_level:
                continue
        levels.append(
            (level_y_m, tuple(sorted(sector_indices)), perimeter_share)
        )
    levels.sort(key=lambda level: level[0])
    return levels


def _classify_structure_ground_interface(
    placements: Sequence[ObjectPlacement],
    frame: _StructureFrame,
    enclosure: _BelowGradeHardEnclosure | None,
    cache: _ResourceGeometryCache | None = None,
) -> StructureGroundInterface | None:
    """Extract and classify one building structure's ground interface
    (spec section 3.4).  Returns ``None`` for structures with no wall
    geometry and no below-grade drivable content (ground clutter)."""
    # Wall columns (A5): vertical extent filters out roof overhangs and
    # decals, whose edges otherwise dominate the base profile.
    wall_columns: list[tuple[float, float, float, frozenset[str]]] = []
    # (frame x, frame z, base y, resources)
    for (grid_x, grid_z), (
        minimum_y,
        maximum_y,
        resources,
    ) in frame.vertex_columns.items():
        if maximum_y - minimum_y >= WALL_COLUMN_MIN_VERTICAL_EXTENT_M:
            wall_columns.append(
                (
                    grid_x * WALL_COLUMN_GRID_M,
                    grid_z * WALL_COLUMN_GRID_M,
                    minimum_y,
                    resources,
                )
            )
    cutout_triggered = (
        enclosure is not None
        and enclosure.enclosure_fraction
        >= INTERIOR_CUTOUT_ENCLOSURE_MIN_FRACTION
    )
    if not wall_columns and not cutout_triggered:
        return None

    # Sector frame: angles around the wall-column centroid (or the face
    # centroid when a cutout fires on a column-less structure).
    if wall_columns:
        centroid_x = sum(column[0] for column in wall_columns) / len(
            wall_columns
        )
        centroid_z = sum(column[1] for column in wall_columns) / len(
            wall_columns
        )
    else:
        total_area = float(frame.triangle_area_m2.sum()) or 1.0
        centroid_x = float(
            (frame.triangle_centroid_x_m * frame.triangle_area_m2).sum()
            / total_area
        )
        centroid_z = float(
            (frame.triangle_centroid_z_m * frame.triangle_area_m2).sum()
            / total_area
        )

    def _sector_of(x: float, z: float) -> int:
        angle = math.atan2(z - centroid_z, x - centroid_x)
        sector = int(
            (angle + math.pi) / (2.0 * math.pi) * PERIMETER_SECTOR_COUNT
        )
        return min(sector, PERIMETER_SECTOR_COUNT - 1)

    bases_by_sector: dict[int, list[float]] = {}
    for column_x, column_z, base_y, _resources in wall_columns:
        bases_by_sector.setdefault(
            _sector_of(column_x, column_z), []
        ).append(base_y)
    sector_low_envelopes: dict[int, float] = {}
    for sector_index, bases in bases_by_sector.items():
        sector_low_envelopes[sector_index] = float(
            numpy.percentile(
                numpy.asarray(bases), FACADE_BASE_LOW_ENVELOPE_PERCENTILE
            )
        )

    # Dominant-area resource (A7 exception key): by solid face area.
    if frame.triangle_count:
        area_by_resource_index = numpy.bincount(
            frame.triangle_resource_indices,
            weights=frame.triangle_area_m2,
            minlength=len(frame.triangle_resource_paths),
        )
        dominant_area_resource = frame.triangle_resource_paths[
            int(area_by_resource_index.argmax())
        ]
    else:
        dominant_area_resource = None

    wall_column_bases = [
        (base_y, resources)
        for _x, _z, base_y, resources in wall_columns
    ]
    interface_levels = _cluster_interface_levels(
        sector_low_envelopes, wall_column_bases, dominant_area_resource
    )

    # Ground-contact fractions (work order round 4), by face area —
    # vectorized over the frame triangle arrays.
    total_face_area = float(frame.triangle_area_m2.sum())
    triangle_angles = numpy.arctan2(
        frame.triangle_centroid_z_m - centroid_z,
        frame.triangle_centroid_x_m - centroid_x,
    )
    triangle_sectors = (
        (triangle_angles + numpy.pi)
        / (2.0 * numpy.pi)
        * PERIMETER_SECTOR_COUNT
    ).astype(numpy.int64)
    numpy.minimum(
        triangle_sectors, PERIMETER_SECTOR_COUNT - 1, out=triangle_sectors
    )
    area_by_sector = numpy.bincount(
        triangle_sectors,
        weights=frame.triangle_area_m2,
        minlength=PERIMETER_SECTOR_COUNT,
    )
    contact_mask = (
        numpy.abs(frame.triangle_height_m)
        <= GROUND_CONTACT_BAND_HALF_WIDTH_M
    )
    contact_area_by_sector = numpy.bincount(
        triangle_sectors[contact_mask],
        weights=frame.triangle_area_m2[contact_mask],
        minlength=PERIMETER_SECTOR_COUNT,
    )
    contact_area_total = float(contact_area_by_sector.sum())
    ground_contact_fraction = (
        contact_area_total / total_face_area if total_face_area > 0 else 0.0
    )
    # The open-pit signal (see BOWL_MAX_ABOVE_GRADE_AREA_FRACTION): face
    # area standing clear ABOVE the ground band.  Same band half-width as
    # the contact test, so the two partition the structure with the band
    # itself shared: contact ∪ above ∪ below covers every triangle.
    above_grade_area_total = float(
        frame.triangle_area_m2[
            frame.triangle_height_m > GROUND_CONTACT_BAND_HALF_WIDTH_M
        ].sum()
    )
    above_grade_area_fraction = (
        above_grade_area_total / total_face_area
        if total_face_area > 0
        else 0.0
    )
    ground_contact_fraction_by_sector = [
        (
            float(contact_area_by_sector[index] / area_by_sector[index])
            if area_by_sector[index] > 0
            else 0.0
        )
        for index in range(PERIMETER_SECTOR_COUNT)
    ]

    # Elevated deck/road above the footprint: confirms a bowl (T1 helix),
    # is a decoy over a flat structure (ELLX roadway) — recorded, never
    # deciding (A7).
    elevated_deck_mask = (
        frame.triangle_horizontality >= NEAR_HORIZONTAL_NORMAL_Y_MIN
    ) & (frame.triangle_height_m >= BRIDGE_DECK_CARRIED_MIN_HEIGHT_M)
    elevated_deck_area = float(
        frame.triangle_area_m2[elevated_deck_mask].sum()
    )
    elevated_deck_above = elevated_deck_area >= BRIDGE_MIN_DECK_AREA_M2

    # The whole-structure footprint union is expensive on mega-pool
    # frames and is consumed ONLY by the bowl and trench branches below
    # (a FLAT record never carries it), so it is computed lazily.
    structure_footprint_memo: list = []

    def _structure_footprint():
        if not structure_footprint_memo:
            if cache is not None:
                class_footprints = _class_footprints_by_resource(
                    placements,
                    frame.origin_latitude,
                    frame.origin_longitude,
                    cache,
                    _FACE_CLASS_ALL,
                )
                if class_footprints:
                    try:
                        footprint = _close_and_reduce_union(
                            shapely.union_all(
                                list(class_footprints.values())
                            ),
                            AT_GRADE_FOOTPRINT_CLOSE_M,
                            True,
                        )
                    except (ValueError, _GEOS_EXCEPTION):
                        footprint = None
                else:
                    footprint = None
            else:
                footprint = _union_horizontal_coordinates(
                    frame.triangle_corner_coordinates_xz(),
                    close_m=AT_GRADE_FOOTPRINT_CLOSE_M,
                    keep_all_parts=True,
                )
            structure_footprint_memo.append(footprint)
        return structure_footprint_memo[0]

    def _structure_footprint_area() -> float:
        footprint = _structure_footprint()
        return footprint.area if footprint is not None else 0.0

    # --- classification, in evidence order ---------------------------------
    interface_class = INTERFACE_FLAT_CONFIRMED
    below_grade_footprint = None
    floor_y_m: float | None = None
    floor_is_bound_not_target = False

    # The bowl key (A7, as measured — see BOWL_MAX_AT_GRADE_BASE_SHARE):
    # share of wall columns based within the ground band.
    at_grade_column_count = sum(
        1
        for base_y, _resources in wall_column_bases
        if abs(base_y) <= GROUND_CONTACT_BAND_HALF_WIDTH_M
    )
    at_grade_wall_base_share = (
        at_grade_column_count / len(wall_column_bases)
        if wall_column_bases
        else 0.0
    )

    # Below-grade interface levels, deepest first (list is sorted).
    below_grade_levels = [
        level
        for level in interface_levels
        if level[0] <= -BOWL_MIN_BELOW_GRADE_LEVEL_DEPTH_M
    ]
    # The bowl floor bound is the largest-share below-grade level — the
    # shell base (T1: −3.42 at 39% share), not the deepest stray column.
    bowl_floor_level = (
        max(below_grade_levels, key=lambda level: level[2])
        if below_grade_levels
        else None
    )

    trench_level: tuple[float, tuple[int, ...], float] | None = None
    trench_footprint = None
    for level_y_m, sector_indices, perimeter_share in interface_levels:
        if level_y_m > -TRENCH_SPINE_MIN_DEPTH_M:
            continue
        if perimeter_share < TRENCH_SPINE_MIN_LEVEL_PERIMETER_SHARE:
            continue
        contributing_resources = {
            resource
            for base_y, resources in wall_column_bases
            if abs(base_y - level_y_m) <= INTERFACE_LEVEL_CLUSTER_M
            for resource in resources
        }
        if (
            len(contributing_resources)
            < TRENCH_SPINE_MIN_CONTRIBUTING_OBJECTS
        ):
            continue
        candidate_footprint = _union_horizontal_coordinates(
            frame.triangle_corner_coordinates_xz(
                frame.triangle_height_m <= -TRENCH_SPINE_MIN_DEPTH_M
            ),
            close_m=AT_GRADE_FOOTPRINT_CLOSE_M,
            keep_all_parts=True,
        )
        if candidate_footprint is None:
            continue
        # Largest CONNECTED part, never the sum: a coherent corridor is
        # the trench signature; scattered below-grade specks (EGLL jetway
        # slack) summed past the floor in the round-5 full-pack run.
        candidate_parts = (
            list(candidate_footprint.geoms)
            if candidate_footprint.geom_type == "MultiPolygon"
            else [candidate_footprint]
        )
        largest_part = max(candidate_parts, key=lambda part: part.area)
        if largest_part.area < TRENCH_SPINE_MIN_FOOTPRINT_AREA_M2:
            continue
        trench_level = (level_y_m, sector_indices, perimeter_share)
        trench_footprint = largest_part
        break  # levels are sorted deepest first

    if cutout_triggered:
        interface_class = INTERFACE_INTERIOR_CUTOUT
        try:
            below_grade_footprint = (
                enclosure.below_grade_hard_union.intersection(
                    enclosure.at_grade_footprint
                )
                if enclosure.at_grade_footprint is not None
                else enclosure.below_grade_hard_union
            )
        except (ValueError, _GEOS_EXCEPTION):
            below_grade_footprint = enclosure.below_grade_hard_union
        floor_y_m = enclosure.hard_content_minimum_y_m
    elif (
        (
            # The A7 limb: essentially no ground-contact geometry (LFPG
            # T1's drum floats above its sunken floor)...
            ground_contact_fraction <= BOWL_MAX_GROUND_CONTACT_FRACTION
            # ...or the OPEN-PIT limb: essentially nothing above grade
            # (the OTHH drainage basins, whose own rim IS the ground
            # band — see BOWL_MAX_ABOVE_GRADE_AREA_FRACTION).  It YIELDS
            # to a trench spine: the LFPG-T2 pattern (halls at grade over
            # one continuous −7.5 m level) also has nothing above +1 m,
            # and the trench branch below is its correct, narrower
            # verdict.  The A7 ground-contact limb keeps its original
            # precedence over trench — this limb only claims structures
            # nothing else does.
            or (
                trench_level is None
                and above_grade_area_fraction
                <= BOWL_MAX_ABOVE_GRADE_AREA_FRACTION
            )
        )
        and at_grade_wall_base_share <= BOWL_MAX_AT_GRADE_BASE_SHARE
        and bowl_floor_level is not None
        and _structure_footprint_area()
        >= STRUCTURE_INTERFACE_MIN_FOOTPRINT_AREA_M2
    ):
        interface_class = INTERFACE_BOWL_UNDER_DECK
        below_grade_footprint = _structure_footprint()
        # Objects under-specify bowl depth (A7: T1 shell base −3.4 m where
        # the reference hand patch cuts −8 m) — a BOUND, never a target.
        floor_y_m = bowl_floor_level[0]
        floor_is_bound_not_target = True
    elif (
        trench_level is not None
        and _structure_footprint_area()
        >= STRUCTURE_INTERFACE_MIN_FOOTPRINT_AREA_M2
    ):
        interface_class = INTERFACE_TRENCH_SPINE
        below_grade_footprint = trench_footprint
        floor_y_m = trench_level[0]

    perimeter_base_profile = [
        (
            (sector_index + 0.5) * 360.0 / PERIMETER_SECTOR_COUNT,
            sector_low_envelopes[sector_index],
        )
        for sector_index in sorted(sector_low_envelopes)
    ]

    reference_placement = placements[0]
    return StructureGroundInterface(
        object_resources=sorted(
            {placement.resource_path for placement in placements}
        ),
        anchor_longitude_latitude=(
            reference_placement.longitude,
            reference_placement.latitude,
        ),
        frame_origin_longitude_latitude=(
            frame.origin_longitude,
            frame.origin_latitude,
        ),
        heading_degrees=reference_placement.heading_degrees,
        perimeter_base_profile=perimeter_base_profile,
        interface_levels=interface_levels,
        split_level=len(interface_levels) > 1,
        ground_contact_fraction=ground_contact_fraction,
        ground_contact_fraction_by_sector=ground_contact_fraction_by_sector,
        at_grade_wall_base_share=at_grade_wall_base_share,
        interface_class=interface_class,
        below_grade_footprint=below_grade_footprint,
        floor_y_m=floor_y_m,
        floor_is_bound_not_target=floor_is_bound_not_target,
        elevated_deck_above=elevated_deck_above,
        above_grade_area_fraction=above_grade_area_fraction,
        # The frame already carries the deepest SOLID vertex it saw (raw
        # vertex set, so vertical liner walls that collapse out of the
        # triangle list still count) — the basin floor law's own key.
        # THE FLOOR WITNESS, not the bare minimum (spec §2.1): a pooled
        # part with no vertical extent is a ground decal and never digs a
        # facility's floor (LEMD's VOR quads at −50.0 effective, which
        # keyed a 51.5 m trench under a 7.02 m body).
        solid_minimum_y_m=float(frame.solid_floor_witness_y_m),
    )


# ---------------------------------------------------------------------------
# Round-5 mega-pool component refinement
# ---------------------------------------------------------------------------

def _resources_with_triangles_near(
    frame: _StructureFrame,
    geometry,
    margin_m: float = 0.0,
) -> set[str]:
    """Resources owning at least one frame triangle whose bounding box
    overlaps ``geometry``'s bounding box (expanded by ``margin_m``) — the
    cheap exact prefilter for footprint-overlap questions: a resource
    with no triangle near the geometry cannot intersect it."""
    if frame.triangle_count == 0:
        return set()
    minimum_x, minimum_z, maximum_x, maximum_z = geometry.bounds
    near_mask = (
        (frame.triangle_corner_x_m.min(axis=1) <= maximum_x + margin_m)
        & (frame.triangle_corner_x_m.max(axis=1) >= minimum_x - margin_m)
        & (frame.triangle_corner_z_m.min(axis=1) <= maximum_z + margin_m)
        & (frame.triangle_corner_z_m.max(axis=1) >= minimum_z - margin_m)
    )
    return {
        frame.triangle_resource_paths[index]
        for index in numpy.unique(
            frame.triangle_resource_indices[near_mask]
        ).tolist()
    }


def _open_pit_components(
    placements: Sequence[ObjectPlacement],
    frame: _StructureFrame,
    cache: _ResourceGeometryCache,
) -> list[set[str]]:
    """Open-pit candidate components inside one pool.

    The non-hard analogue of :func:`_below_grade_drivable_components`, and
    for the same reason (owner defect 2026-07-30, OTHH Drainage_03/_05): a
    pool is a world-footprint overlap group, not a structure, so a basin
    that happens to sit inside a terminal complex's footprint has its
    whole-structure pit metrics averaged away by the terminal.  Feature A
    solved this in round 5 by classifying per component; feature C never
    did, and the identical Drainage_04 (pooled alone) and Drainage_05
    (pooled with 52 Emiri Terminal resources) classified differently.

    Seeds are resources whose OWN authored geometry is a pit — nothing
    above the ground band, a floor at least
    :data:`PIT_SEED_MIN_DEPTH_M` below it — read straight from
    ``cache.evidence``, so this costs no geometry pass.  A terminal with a
    basement never seeds: its roof is far above the band.  Seeds are then
    joined into components by footprint proximity, the same union-find and
    the same buffer the tunnel components use.

    A DECAL IS NOT A SOLID, AND SO IS NOT A PIT
    (``config.BASIN_POOL_SCOPING``, default ON): a seed contributes its
    FULL footprint and chains every other seed within the join buffer to
    it, so a flat authored quad with no vertical extent is the one shape
    that can make a basin arbitrarily large.  It measured exactly that at
    LEMD — five ``AESlite-LEMD-VOR-*.obj`` decals, each a single
    4-vertex quad 1.4–1.6 km on a side at y = −50.0 (bbox height 0.000),
    seeded three pit components of 2.0–2.6 million m² and dragged the
    real 11,705 m² tower cutout into a 2,078,883 m² basin.  The
    predicate is :func:`part_has_solid_thickness`, the same one §2.1
    uses for the floor witness — paint is not structure, in either law.

    SCOPE IS THE SEED SET, NOT THE FRAME (measured; see
    ``config.BASIN_POOL_SCOPING``): thin parts stay in the pool and in
    the structure frame.  ``_agl_tunnel_seed_resources`` reads its
    above-grade cap off the WHOLE structure (owner ruling 2026-07-31),
    so dropping them from the frame re-seeded OTHH ``Bridge_04`` as a
    tunnel — the very defect that ruling closed.
    """
    from .config import BASIN_POOL_SCOPING
    pit_resources: set[str] = set()
    for placement in placements:
        _has_hard, has_solid, minimum_vertex_y, maximum_vertex_y = (
            cache.evidence(placement.resource_path)
        )
        if not has_solid:
            continue
        if BASIN_POOL_SCOPING and not part_has_solid_thickness(
            minimum_vertex_y, maximum_vertex_y
        ):
            continue
        offset = placement.above_ground_level_metres
        if offset + maximum_vertex_y > PIT_SEED_MAX_ABOVE_GRADE_Y_M:
            continue
        if offset + minimum_vertex_y > -PIT_SEED_MIN_DEPTH_M:
            continue
        pit_resources.add(placement.resource_path)
    if not pit_resources:
        return []
    seed_footprints = _class_footprints_by_resource(
        placements,
        frame.origin_latitude,
        frame.origin_longitude,
        cache,
        _FACE_CLASS_ALL,
        restrict_resources=pit_resources,
    )
    if not seed_footprints:
        return []
    return _footprint_components(
        seed_footprints, TUNNEL_COMPONENT_JOIN_BUFFER_M
    )


def _footprint_components(
    footprint_by_resource: dict[str, object],
    join_buffer_m: float,
) -> list[set[str]]:
    """Union-find components over resources whose footprints come within
    ``join_buffer_m`` of each other."""
    resources = sorted(footprint_by_resource)
    parent = list(range(len(resources)))

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root

    buffered = {}
    for resource in resources:
        try:
            buffered[resource] = footprint_by_resource[resource].buffer(
                join_buffer_m
            )
        except (ValueError, _GEOS_EXCEPTION):
            buffered[resource] = footprint_by_resource[resource]
    for first_index in range(len(resources)):
        for second_index in range(first_index + 1, len(resources)):
            try:
                touches = buffered[resources[first_index]].intersects(
                    footprint_by_resource[resources[second_index]]
                )
            except (ValueError, _GEOS_EXCEPTION):
                touches = True  # doubt merges, never tears (I-20 spirit)
            if touches:
                union(first_index, second_index)

    members_by_root: dict[int, set[str]] = {}
    for index, resource in enumerate(resources):
        members_by_root.setdefault(find(index), set()).add(resource)
    return list(members_by_root.values())


def _below_grade_drivable_components(
    placements: Sequence[ObjectPlacement],
    frame: _StructureFrame,
    cache: _ResourceGeometryCache,
) -> list[set[str]]:
    """Tunnel/interior-cutout candidate components inside one pool.

    Seeds: resources owning near-horizontal HARD faces below
    :data:`TUNNEL_MIN_BODY_DEPTH_M` (their below-grade deck footprints),
    plus resources placed with a below-grade ``OBJECT_AGL`` offset (whole
    footprint — the EGLL AGL shells carry no hard).  Non-seed resources
    are attached when at least
    :data:`TUNNEL_COVER_CONTAINMENT_MIN_FRACTION` of their own footprint
    lies over the component's seed footprint — the roof shell over its
    deck — so mouths (deck − roof) still compute per tunnel."""
    below_grade_agl_resources = _agl_tunnel_seed_resources(
        placements, frame
    )
    seed_footprints = _class_footprints_by_resource(
        placements,
        frame.origin_latitude,
        frame.origin_longitude,
        cache,
        _FACE_CLASS_BELOW_GRADE_HARD_NEAR_HORIZONTAL,
        full_footprint_resources=below_grade_agl_resources,
    )
    if not seed_footprints:
        return []
    components = _footprint_components(
        seed_footprints, TUNNEL_COMPONENT_JOIN_BUFFER_M
    )

    # Attach cover (roof shell) resources.  Containment needs each
    # candidate's FULL footprint union, so the bounding-box prefilter
    # first drops every resource that cannot overlap the component at
    # all (a resource with no triangle near it has containment zero).
    attached_components: list[set[str]] = []
    for component in components:
        try:
            component_footprint = unary_union(
                [seed_footprints[resource] for resource in component]
            ).buffer(TUNNEL_COMPONENT_JOIN_BUFFER_M)
        except (ValueError, _GEOS_EXCEPTION):
            attached_components.append(component)
            continue
        attached = set(component)
        candidate_resources = (
            _resources_with_triangles_near(frame, component_footprint)
            - attached
        )
        candidate_footprints = _class_footprints_by_resource(
            placements,
            frame.origin_latitude,
            frame.origin_longitude,
            cache,
            _FACE_CLASS_ALL,
            restrict_resources=candidate_resources,
        )
        for resource, footprint in candidate_footprints.items():
            if resource in attached or footprint.area <= 0.0:
                continue
            try:
                contained = footprint.intersection(component_footprint).area
            except (ValueError, _GEOS_EXCEPTION):
                continue
            if (
                contained / footprint.area
                >= TUNNEL_COVER_CONTAINMENT_MIN_FRACTION
            ):
                attached.add(resource)
        attached_components.append(attached)
    return attached_components


def _cosmetic_bridge_components(
    placements: Sequence[ObjectPlacement],
    frame: _StructureFrame,
    cache: _ResourceGeometryCache,
) -> list[set[str]]:
    """Cosmetic (hard-less) bridge candidate components inside one pool.

    The name-hinted analogue of :func:`_hard_face_components`, and the
    third instance of the same lesson (owner ruling 2026-07-31, the six
    OTHH road bridges): a pool is a world-footprint OVERLAP group, not a
    structure, so a bridge pooled with anything else has its whole-pool
    metrics decided by that anything else.  Feature A fixed this for
    tunnels in round 5 (:func:`_below_grade_drivable_components`),
    feature C for basins on 2026-07-30 (:func:`_open_pit_components`);
    the cosmetic bridge path still read the whole pool, and at OTHH that
    cost every one of the owner's bridges:

    * Bridge_01 pooled with 2 250 other placements, whose 57 299 wall
      columns read the pool as a BUILDING — ``_classify_bridge`` was
      never called on it at all;
    * Bridge_02, _03 and _06 share one 239-placement pool, so the three
      of them were classified as ONE structure whose minimum rotated
      rectangle spans all three and ends in mid-air — duly refused as a
      piered viaduct, a verdict about the merge rather than about any
      bridge.

    Seeds are resources that are name-hinted AND carry no hard triangle
    anywhere, read from ``cache.evidence`` at no geometry cost.  The
    hard-less requirement is :data:`COSMETIC_BRIDGE_NAME_HINT`'s own
    standing law — a name must never gate a hard deck (the KMCO
    ``puente`` objects are named in Spanish) — so nothing that reaches
    the geometric deck path can be diverted here.  Seeds join into
    components by footprint proximity, the same union-find and buffer the
    hard path uses, which is what separates three bridges 10 m apart.
    """
    seed_resources: set[str] = set()
    for placement in placements:
        if (
            COSMETIC_BRIDGE_NAME_HINT
            not in placement.resource_path.lower()
        ):
            continue
        has_hard, has_solid, _minimum_y, _maximum_y = cache.evidence(
            placement.resource_path
        )
        if has_hard or not has_solid:
            continue
        seed_resources.add(placement.resource_path)
    if not seed_resources:
        return []
    seed_footprints = _class_footprints_by_resource(
        placements,
        frame.origin_latitude,
        frame.origin_longitude,
        cache,
        _FACE_CLASS_ALL,
        restrict_resources=seed_resources,
    )
    if not seed_footprints:
        return []
    return _footprint_components(
        seed_footprints, BRIDGE_COMPONENT_JOIN_BUFFER_M
    )


def _hard_face_components(
    placements: Sequence[ObjectPlacement],
    frame: _StructureFrame,
    cache: _ResourceGeometryCache,
) -> list[set[str]]:
    """Bridge candidate components: resources owning near-horizontal hard
    faces, grouped by footprint adjacency
    (:data:`BRIDGE_COMPONENT_JOIN_BUFFER_M`)."""
    seed_footprints = _class_footprints_by_resource(
        placements,
        frame.origin_latitude,
        frame.origin_longitude,
        cache,
        _FACE_CLASS_HARD_NEAR_HORIZONTAL,
    )
    if not seed_footprints:
        return []
    return _footprint_components(
        seed_footprints, BRIDGE_COMPONENT_JOIN_BUFFER_M
    )


def _bridge_evidence_resources(
    component: set[str],
    placements: Sequence[ObjectPlacement],
    frame: _StructureFrame,
    cache: _ResourceGeometryCache,
    face_class: int = _FACE_CLASS_HARD_NEAR_HORIZONTAL,
) -> set[str]:
    """The component plus every pool resource whose footprint intersects
    the component's own footprint buffered by the abutment search radius
    — the grounding cladding the per-end test must see (EDDF's Tunnel_N
    trench walls belong to their Bridge_N deck).

    ``face_class`` selects which of the component's faces define that
    footprint.  The default is the hard near-horizontal deck, which is
    what a hard-path component is seeded on.  A COSMETIC component has no
    hard face at all, so it passes :data:`_FACE_CLASS_ALL` — otherwise the
    seed footprint is empty and the widening silently returns the bare
    component, leaving the abutment test blind to the very cladding that
    grounds it.

    A resource's footprint union intersects the buffered seed footprint
    exactly when SOME face of it does, so membership is decided by a
    bulk per-triangle intersection test (bounding-box prefiltered) — no
    per-resource footprint unions are ever built here."""
    component_seed = _class_footprints_by_resource(
        placements,
        frame.origin_latitude,
        frame.origin_longitude,
        cache,
        face_class,
        restrict_resources=component,
    )
    if not component_seed:
        return set(component)
    try:
        buffered = unary_union(list(component_seed.values())).buffer(
            ABUTMENT_GRADE_SEARCH_RADIUS_M
        )
    except (ValueError, _GEOS_EXCEPTION):
        return set(component)
    evidence = set(component)
    resource_index_by_path = {
        path: index
        for index, path in enumerate(frame.triangle_resource_paths)
    }
    evidence_indices = [
        resource_index_by_path[resource]
        for resource in evidence
        if resource in resource_index_by_path
    ]
    candidate_mask = ~numpy.isin(
        frame.triangle_resource_indices,
        numpy.asarray(evidence_indices, dtype=numpy.int32),
    )
    if candidate_mask.any():
        minimum_x, minimum_z, maximum_x, maximum_z = buffered.bounds
        candidate_mask &= (
            (frame.triangle_corner_x_m.min(axis=1) <= maximum_x)
            & (frame.triangle_corner_x_m.max(axis=1) >= minimum_x)
            & (frame.triangle_corner_z_m.min(axis=1) <= maximum_z)
            & (frame.triangle_corner_z_m.max(axis=1) >= minimum_z)
        )
    if candidate_mask.any():
        candidate_resource_indices = frame.triangle_resource_indices[
            candidate_mask
        ]
        try:
            shapely.prepare(buffered)
            intersecting = shapely.intersects(
                shapely.polygons(
                    frame.triangle_corner_coordinates_xz(candidate_mask)
                ),
                buffered,
            )
            hit_indices = numpy.unique(
                candidate_resource_indices[intersecting]
            )
        except (ValueError, _GEOS_EXCEPTION):
            # Doubt merges, never tears (I-20 spirit): on a bulk-test
            # failure every bounding-box candidate joins the evidence.
            hit_indices = numpy.unique(candidate_resource_indices)
        evidence.update(
            frame.triangle_resource_paths[index]
            for index in hit_indices.tolist()
        )
    return evidence


def _wall_column_count(frame: _StructureFrame) -> int:
    return sum(
        1
        for minimum_y, maximum_y, _resources in frame.vertex_columns.values()
        if maximum_y - minimum_y >= WALL_COLUMN_MIN_VERTICAL_EXTENT_M
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _pavement_union_in_frame(
    pavement_polygons_longitude_latitude,
    origin_latitude: float,
    origin_longitude: float,
) -> Polygon | None:
    """Project caller-supplied lon/lat pavement polygons into the structure
    frame and union them (for the contract coverage test).

    Accepts shapely Polygons, MultiPolygons (a self-crossing draped ring
    repaired by ``buffer(0)`` upstream arrives as one — real KBNA input),
    or raw ``(longitude, latitude)`` rings."""
    if not pavement_polygons_longitude_latitude:
        return None
    exterior_rings: list[list[tuple[float, float]]] = []
    for polygon in pavement_polygons_longitude_latitude:
        geometry_type = getattr(polygon, "geom_type", None)
        if geometry_type == "MultiPolygon":
            for part in polygon.geoms:
                exterior_rings.append(list(part.exterior.coords))
        elif geometry_type == "Polygon":
            exterior_rings.append(list(polygon.exterior.coords))
        else:
            exterior_rings.append(list(polygon))
    frame_polygons = []
    for ring in exterior_rings:
        frame_ring = []
        for longitude, latitude in ring:
            frame_x, frame_z = obj8_reader.lonlat_to_local_offset(
                origin_latitude, origin_longitude, 0.0, latitude, longitude
            )
            frame_ring.append((frame_x, frame_z))
        if len(frame_ring) < 3:
            continue
        candidate = Polygon(frame_ring)
        if not candidate.is_valid:
            candidate = candidate.buffer(0)
        if not candidate.is_empty:
            frame_polygons.append(candidate)
    if not frame_polygons:
        return None
    try:
        union = unary_union(frame_polygons)
    except (ValueError, _GEOS_EXCEPTION):
        return None
    return None if union.is_empty else union


def _pool_has_classification_evidence(
    placements: Sequence[ObjectPlacement],
    cache: _ResourceGeometryCache,
) -> bool:
    """The evidence pre-screen (see the ``POOL_EVIDENCE_*`` constant
    block): may a pool possibly emit a record?  ``False`` is PROVEN
    silence — no tunnel, bridge, refusal, exclusion or ground interface
    can come out of a pool with no hard triangle, no below-grade
    ``OBJECT_AGL`` placement, no vertex deep enough to seat a below-grade
    interface level, no cosmetic-bridge name hint, and too little
    vertical span for a single wall column."""
    pool_minimum_effective_y = math.inf
    pool_maximum_effective_y = -math.inf
    for placement in placements:
        has_hard, has_solid, minimum_vertex_y, maximum_vertex_y = (
            cache.evidence(placement.resource_path)
        )
        if not has_solid:
            continue
        if has_hard:
            return True
        if COSMETIC_BRIDGE_NAME_HINT in placement.resource_path.lower():
            return True
        offset = placement.above_ground_level_metres
        if offset <= -TUNNEL_MIN_BELOW_GRADE_AGL_OFFSET_M:
            return True
        lowest = offset + minimum_vertex_y
        if lowest <= POOL_EVIDENCE_BELOW_GRADE_VERTEX_MAX_Y_M:
            return True
        if lowest < pool_minimum_effective_y:
            pool_minimum_effective_y = lowest
        highest = offset + maximum_vertex_y
        if highest > pool_maximum_effective_y:
            pool_maximum_effective_y = highest
    return (
        pool_maximum_effective_y - pool_minimum_effective_y
        >= WALL_COLUMN_MIN_VERTICAL_EXTENT_M
    )


# Portal-face signature calibrations (user 2026-07-17, EGGW: each face
# is a single soft quad, 2 triangles, y −8.33..+0.06, 21-45 m wide).
# The triangle cap keeps real structures (KBNA portal towers, buried
# basements — dozens to thousands of triangles) out; the depth/height
# floors keep signage and fence panels out; the width band keeps both
# tiny decals and field-spanning texture pages out.
PORTAL_FACE_MAX_SOLID_TRIANGLES = 8
PORTAL_FACE_MIN_DEPTH_M = 2.0
PORTAL_FACE_MAX_TOP_M = 1.0
PORTAL_FACE_MIN_HEIGHT_M = 2.0
PORTAL_FACE_MIN_WIDTH_M = 4.0
PORTAL_FACE_MAX_WIDTH_M = 60.0


def _detect_portal_faces(
    placements: Sequence[ObjectPlacement],
    geometry_by_resource: dict[str, ObjectGeometry],
) -> list[PortalFaceStructure]:
    """Recognize bare below-grade portal-face objects (EGGW class).

    Resource-level (pool-independent): the signature is entirely a
    property of one object's own geometry plus its being placed exactly
    once — a face shared by N placements cannot mark N distinct mouths
    any more than the Phase 2 bake can correct N of them."""
    placements_by_resource: dict[str, list[ObjectPlacement]] = {}
    for placement in placements:
        placements_by_resource.setdefault(
            placement.resource_path, []).append(placement)
    faces: list[PortalFaceStructure] = []
    for resource, resource_placements in placements_by_resource.items():
        if len(resource_placements) != 1:
            continue
        placement = resource_placements[0]
        if placement.placement_kind != "OBJECT":
            # Negative-AGL placements already carry the A6 tunnel
            # signature; MSL rows are absolute fixtures.
            continue
        geometry = geometry_by_resource.get(resource)
        if geometry is None:
            continue
        triangles = geometry.solid_triangles
        if not triangles or len(triangles) > PORTAL_FACE_MAX_SOLID_TRIANGLES:
            continue
        hardness = getattr(geometry, "solid_triangle_hardness", None)
        if hardness and any(kind for kind in hardness):
            continue  # anything drivable is the A6 signature's business
        used_indices = sorted({i for tri in triangles for i in tri})
        vertices = geometry.vertices
        face_ys = [vertices[i][1] for i in used_indices]
        face_min_y = min(face_ys)
        face_max_y = max(face_ys)
        if face_min_y > -PORTAL_FACE_MIN_DEPTH_M:
            continue
        if face_max_y > PORTAL_FACE_MAX_TOP_M:
            continue
        if (face_max_y - face_min_y) < PORTAL_FACE_MIN_HEIGHT_M:
            continue
        projected = []
        for index in used_indices:
            x, _y, z = vertices[index]
            latitude, longitude = obj8_reader.local_offset_to_lonlat(
                placement.latitude, placement.longitude,
                placement.heading_degrees, x, z)
            projected.append((longitude, latitude))
        try:
            hull = shapely.geometry.MultiPoint(projected).convex_hull
            if hull.geom_type != "Polygon":
                # A perfectly vertical face projects to a line — pad it
                # to a thin footprint (~2 m) so downstream centroid /
                # split geometry works.
                hull = hull.buffer(2.0 / 111320.0)
            if hull.geom_type != "Polygon" or hull.is_empty:
                continue
        except (ValueError, _GEOS_EXCEPTION):
            continue
        # The FACE LINE is the long side of the footprint's minimum
        # rotated rectangle (the most-distant vertex pair would give a
        # DIAGONAL on a sloped face); the implied tunnel axis is its
        # perpendicular.  Work in local-metre offsets to keep the
        # anisotropic degrees out of the angle.
        cos_latitude = math.cos(math.radians(placement.latitude))
        try:
            metre_ring = [
                ((lon - placement.longitude) * 111320.0 * cos_latitude,
                 (lat - placement.latitude) * 111320.0)
                for lon, lat in hull.exterior.coords]
            rect = min_rotated_rect(Polygon(metre_ring))
            corners = list(rect.exterior.coords)[:4]
        except (ValueError, _GEOS_EXCEPTION):
            continue
        side_a = math.hypot(corners[1][0] - corners[0][0],
                            corners[1][1] - corners[0][1])
        side_b = math.hypot(corners[2][0] - corners[1][0],
                            corners[2][1] - corners[1][1])
        if side_a >= side_b:
            long_east = corners[1][0] - corners[0][0]
            long_north = corners[1][1] - corners[0][1]
        else:
            long_east = corners[2][0] - corners[1][0]
            long_north = corners[2][1] - corners[1][1]
        if abs(long_east) < 1e-9 and abs(long_north) < 1e-9:
            continue
        face_width = max(side_a, side_b)
        if not (PORTAL_FACE_MIN_WIDTH_M
                <= face_width <= PORTAL_FACE_MAX_WIDTH_M):
            continue
        face_line_bearing = math.degrees(
            math.atan2(long_east, long_north)) % 180.0
        tunnel_axis_bearing = (face_line_bearing + 90.0) % 180.0
        faces.append(PortalFaceStructure(
            object_resources=[resource],
            anchor_longitude_latitude=(
                placement.longitude, placement.latitude),
            heading_degrees=tunnel_axis_bearing,
            face_polygon_longitude_latitude=hull,
            face_min_y_m=face_min_y,
            face_max_y_m=face_max_y,
            face_width_m=face_width,
            deck_top_y_m=face_max_y - face_min_y,
            face_line_bearing_degrees=face_line_bearing,
        ))
    return faces


def classify_object_terrain_features(
    placements: Sequence[ObjectPlacement],
    geometry_by_resource: dict[str, ObjectGeometry],
    *,
    pavement_polygons_longitude_latitude=None,
    mean_sea_level_placements: Sequence[ObjectPlacement] | None = None,
    pack_root: str = "",
    epsilon_metres: float = STRUCTURE_GROUPING_EPSILON_M,
    split_level_terrain_enabled: bool = False,
    basin_trench_enabled: bool = False,
) -> ClassificationResult:
    """Classify tunnels and bridges from placements and per-object geometry.

    Pure: nothing is read from disk here.  ``placements`` are the
    tunnel/bridge candidate placements the caller wishes to consider (a
    thin caller can pass every placement — a pool that matches no signature
    is simply ignored).  ``geometry_by_resource`` maps each placement's
    ``resource_path`` to its :class:`ObjectGeometry`.  Optional
    ``pavement_polygons_longitude_latitude`` (shapely polygons or ``(lon,
    lat)`` rings) drives the bridge terrain contract; ``mean_sea_level_
    placements`` (read upstream with ``include_object_msl=True``) supply
    absolute deck elevations.  ``pack_root`` is paired with each consumed
    resource in :attr:`ClassificationResult.exclusions` (ruling R4).

    Grouping reuses ``object_anchor.discover_object_pools``; each pool is
    tried as a tunnel first (below-grade signature) then as a bridge.

    ``split_level_terrain_enabled`` mirrors the spec section 3.4 gate
    (``config.OBJECT_SPLIT_LEVEL_TERRAIN``, default off): feature-C
    ground interfaces are always MEASURED and recorded, but their
    resources join the ruling-R4 exclusion list only when the
    split-level terrain adapter is actually on — R4 excludes structures
    whose terrain IS adapted to them, and with the adapter off none is
    (LSGG 2026-07-23: unconditional interface exclusions plus the
    anchor-family widening starved the Phase 2 y-bake of 265/266
    objects, terminal buildings included).

    Stock library assets (``lib/...`` virtual paths — see
    :func:`is_stock_library_resource`) are dropped up front: a catalogue
    object is never a pack-authored terrain shell, whatever its shape or
    placement offset (2026-07-18, the EGKR control tower and EGKK oil
    rig)."""
    mean_sea_level_placements = [
        placement
        for placement in (mean_sea_level_placements or [])
        if not is_stock_library_resource(placement.resource_path)
    ]
    placements = [
        placement
        for placement in placements
        if not is_stock_library_resource(placement.resource_path)
    ]
    resolved_paths = {
        placement.resource_path: placement.resource_path
        for placement in placements
        if placement.resource_path in geometry_by_resource
    }
    pools = discover_object_pools(
        list(placements),
        resolved_paths,
        geometry_by_resource,
        epsilon_metres=epsilon_metres,
    )

    tunnels: list[TunnelStructure] = []
    bridges: list[BridgeStructure] = []
    exclusions: list[tuple[str, str]] = []
    refusals: list[RefusedStructure] = []
    ground_interfaces: list[StructureGroundInterface] = []

    cache = _ResourceGeometryCache(geometry_by_resource)
    skipped_pool_count = 0

    for pool in pools:
        if not _pool_has_classification_evidence(pool.placements, cache):
            skipped_pool_count += 1
            continue
        frame = _build_structure_frame(
            pool.placements, geometry_by_resource, cache
        )
        if frame.triangle_count == 0:
            continue
        consumed_resources: set[str] = set()

        # --- stage 1: below-grade drivable components (round 5) ---------
        # Tunnels and interior cutouts are classified per contributing
        # component, never per pool: mega-pools diluted every tunnel
        # metric and ballooned the R4 exclusion list (812 at EGLL).
        # Within a component, R10/A8 precedence holds: ENCLOSURE
        # discriminates the interior cutout from the tunnel.
        for component in _below_grade_drivable_components(
            pool.placements, frame, cache
        ):
            component_placements = [
                placement
                for placement in pool.placements
                if placement.resource_path in component
            ]
            if not component_placements:
                continue
            component_frame = _build_structure_frame(
                component_placements, geometry_by_resource, cache
            )
            if component_frame.triangle_count == 0:
                continue
            component_enclosure = _below_grade_hard_enclosure(
                component_frame
            )
            if (
                component_enclosure is not None
                and component_enclosure.enclosure_fraction
                >= INTERIOR_CUTOUT_ENCLOSURE_MIN_FRACTION
            ):
                ground_interface = _classify_structure_ground_interface(
                    component_placements,
                    component_frame,
                    component_enclosure,
                    cache,
                )
                if ground_interface is not None:
                    ground_interfaces.append(ground_interface)
                    consumed_resources |= component
                    if split_level_terrain_enabled:
                        # Interior cutouts are feature C's domain
                        # (section 3.4 1b): excluded only when the
                        # split-level adapter will carve their terrain.
                        for resource in ground_interface.object_resources:
                            exclusions.append((pack_root, resource))
                continue
            if _is_tunnel_signature(
                component_placements, component_frame
            ):
                tunnel = _classify_tunnel(
                    component_placements,
                    component_frame.origin_latitude,
                    component_frame.origin_longitude,
                    component_frame.triangles,
                )
                # Round-5 admission guard 2: a tunnel is not an island.
                deck_footprint_area_m2 = (
                    tunnel.deck_footprint.area
                    if tunnel.deck_footprint is not None
                    else 0.0
                )
                if (
                    deck_footprint_area_m2
                    > TUNNEL_MAX_DECK_FOOTPRINT_AREA_M2
                ):
                    _vprint(
                        1,
                        "   [object-terrain] tunnel admission: refused "
                        f"{', '.join(tunnel.object_resources)} — deck "
                        f"footprint {deck_footprint_area_m2:,.0f} m² over "
                        "the "
                        f"{TUNNEL_MAX_DECK_FOOTPRINT_AREA_M2:,.0f} m² "
                        "maximum; a tunnel is not an island",
                    )
                    refusals.append(
                        RefusedStructure(
                            object_resources=sorted(component),
                            reason=TUNNEL_REFUSAL_ISLAND_DECK,
                        )
                    )
                    # Consumed, like the refused-bridge path above it: the
                    # component was recognized and judged, so it must not
                    # be re-offered to the bridge/interface stages.  It
                    # takes NO exclusion — ruling R4 excludes structures
                    # whose terrain was adapted to them, and none was, so
                    # the Phase 2 y-bake owns it as ordinary scenery.
                    consumed_resources |= component
                    continue
                tunnels.append(tunnel)
                consumed_resources |= component
                for resource in tunnel.object_resources:
                    exclusions.append((pack_root, resource))

        remaining_placements = [
            placement
            for placement in pool.placements
            if placement.resource_path not in consumed_resources
        ]
        if not remaining_placements:
            continue
        remaining_frame = (
            frame
            if not consumed_resources
            else _build_structure_frame(
                remaining_placements, geometry_by_resource, cache
            )
        )
        if remaining_frame.triangle_count == 0:
            continue

        # --- stage 2: bridge components ----------------------------------
        # Each hard-face component is tried separately (a mega-pool can
        # hold several bridges).  The evidence sub-frame adds the nearby
        # grounding cladding; the building-likeness gate applies per
        # EVIDENCE set, so a terminal's own drivable roadway (ELLX) routes
        # to feature C while a freestanding bridge next to clutter
        # (KBNA Crossing_Bridge) is classified — never silently absent.
        pavement_frame_union = _pavement_union_in_frame(
            pavement_polygons_longitude_latitude,
            remaining_frame.origin_latitude,
            remaining_frame.origin_longitude,
        )
        bridge_components = _hard_face_components(
            remaining_placements, remaining_frame, cache
        )
        for component in bridge_components:
            evidence_resources = _bridge_evidence_resources(
                component, remaining_placements, remaining_frame, cache
            )
            evidence_placements = [
                placement
                for placement in remaining_placements
                if placement.resource_path in evidence_resources
            ]
            if not evidence_placements:
                continue
            evidence_frame = _build_structure_frame(
                evidence_placements, geometry_by_resource, cache
            )
            if evidence_frame.triangle_count == 0:
                continue
            if (
                _wall_column_count(evidence_frame)
                >= BUILDING_MIN_WALL_COLUMN_COUNT
            ):
                # Building-carried drivable surface: feature C's domain
                # (the pool remainder below emits the interface record).
                continue
            bridge, refusal = _classify_bridge(
                evidence_placements,
                evidence_frame,
                pavement_frame_union,
                mean_sea_level_placements,
            )
            if bridge is not None:
                bridges.append(bridge)
                consumed_resources |= set(bridge.object_resources)
                for resource in bridge.object_resources:
                    exclusions.append((pack_root, resource))
            elif refusal is not None:
                refusals.append(
                    _widen_refusal_to_component(refusal, component)
                )
                consumed_resources |= component

        # Cosmetic bridges carry no hard faces at all (Murfreesboro):
        # when the remaining pool has no hard components and is not a
        # building, the whole-pool cosmetic path still applies.  A
        # structure can only come out of ``_classify_bridge`` through
        # the hard-deck path (needs near-horizontal hard faces) or the
        # cosmetic limb (needs the name hint on a hard-less structure);
        # pools with neither provably classify to nothing and are
        # pre-checked here so they never materialize their triangle
        # lists.
        remaining_has_hard = bool(
            (remaining_frame.triangle_hardness_codes > 0).any()
        )
        remaining_cosmetic_possible = not remaining_has_hard and any(
            COSMETIC_BRIDGE_NAME_HINT in placement.resource_path.lower()
            for placement in remaining_placements
        )
        remaining_hard_deck_possible = remaining_has_hard and bool(
            (
                (remaining_frame.triangle_hardness_codes > 0)
                & (
                    remaining_frame.triangle_horizontality
                    >= NEAR_HORIZONTAL_NORMAL_Y_MIN
                )
            ).any()
        )
        # Cosmetic bridges are classified per COMPONENT first, for the
        # reason spelled out in _cosmetic_bridge_components: the whole-pool
        # read let one pool's other 2 250 placements decide a bridge's
        # verdict.  Where the pool IS the bridge the component plus its
        # evidence widening is the same placement set, so the Murfreesboro
        # class reads exactly as before.  When components exist there is
        # NO whole-pool fallback — falling back would restore the merged
        # frame whose bogus axis is the defect.
        cosmetic_components = (
            _cosmetic_bridge_components(
                remaining_placements, remaining_frame, cache
            )
            if not bridge_components and remaining_cosmetic_possible
            else []
        )
        for component in cosmetic_components:
            evidence_resources = _bridge_evidence_resources(
                component,
                remaining_placements,
                remaining_frame,
                cache,
                face_class=_FACE_CLASS_ALL,
            )
            component_placements = [
                placement
                for placement in remaining_placements
                if placement.resource_path in evidence_resources
            ]
            if not component_placements:
                continue
            component_frame = _build_structure_frame(
                component_placements, geometry_by_resource, cache
            )
            if component_frame.triangle_count == 0:
                continue
            if (
                _wall_column_count(component_frame)
                >= BUILDING_MIN_WALL_COLUMN_COUNT
            ):
                continue
            bridge, refusal = _classify_bridge(
                component_placements,
                component_frame,
                pavement_frame_union,
                mean_sea_level_placements,
            )
            if bridge is not None:
                bridges.append(bridge)
                consumed_resources |= set(bridge.object_resources)
                for resource in bridge.object_resources:
                    exclusions.append((pack_root, resource))
            elif refusal is not None:
                refusals.append(
                    _widen_refusal_to_component(refusal, component)
                )
                consumed_resources |= component

        if not cosmetic_components and not bridge_components and (
            remaining_cosmetic_possible or remaining_hard_deck_possible
        ) and (
            _wall_column_count(remaining_frame)
            < BUILDING_MIN_WALL_COLUMN_COUNT
        ):
            bridge, refusal = _classify_bridge(
                remaining_placements,
                remaining_frame,
                pavement_frame_union,
                mean_sea_level_placements,
            )
            if bridge is not None:
                bridges.append(bridge)
                consumed_resources |= set(bridge.object_resources)
                for resource in bridge.object_resources:
                    exclusions.append((pack_root, resource))
            elif refusal is not None:
                whole_pool = {
                    placement.resource_path
                    for placement in remaining_placements
                }
                refusals.append(
                    _widen_refusal_to_component(refusal, whole_pool)
                )
                consumed_resources |= whole_pool

        # --- stage 2b: open-pit components (round-5 refinement, feature C)
        # A basin pooled with a terminal complex has its pit metrics
        # averaged away (OTHH Drainage_05 in the Emiri pool: 0.944
        # above-grade area).  Classify pit components FIRST, on their own
        # frames, and take the verdict only when it is one this feature
        # actually carves — a component that measures FLAT is released
        # back to the whole-pool pass below, unconsumed, so this can only
        # ADD interfaces the pool pass would have diluted.  Gated with the
        # adapter that consumes them.
        if basin_trench_enabled:
            for component in _open_pit_components(
                pool.placements, frame, cache
            ):
                component_placements = [
                    placement
                    for placement in pool.placements
                    if placement.resource_path in component
                    and placement.resource_path not in consumed_resources
                ]
                if not component_placements:
                    continue
                component_frame = _build_structure_frame(
                    component_placements, geometry_by_resource, cache
                )
                if component_frame.triangle_count == 0:
                    continue
                pit_interface = _classify_structure_ground_interface(
                    component_placements,
                    component_frame,
                    _below_grade_hard_enclosure(component_frame),
                    cache,
                )
                if pit_interface is None or not is_carved_basin_interface(
                    pit_interface
                ):
                    continue
                ground_interfaces.append(pit_interface)
                consumed_resources |= {
                    placement.resource_path
                    for placement in component_placements
                }
                for resource in pit_interface.object_resources:
                    exclusions.append((pack_root, resource))

        # --- stage 3: feature C on what remains --------------------------
        building_placements = [
            placement
            for placement in pool.placements
            if placement.resource_path not in consumed_resources
        ]
        if not building_placements:
            continue
        building_frame = (
            remaining_frame
            if len(building_placements) == len(remaining_placements)
            else _build_structure_frame(
                building_placements, geometry_by_resource, cache
            )
        )
        if building_frame.triangle_count == 0:
            continue
        ground_interface = _classify_structure_ground_interface(
            building_placements,
            building_frame,
            _below_grade_hard_enclosure(building_frame),
            cache,
        )
        if ground_interface is not None:
            ground_interfaces.append(ground_interface)
            if (
                split_level_terrain_enabled
                and ground_interface.interface_class
                != INTERFACE_FLAT_CONFIRMED
            ) or (
                # The basin-trench adapter (config.OBJECT_BASIN_TRENCH)
                # carves this interface's terrain, so R4 excludes it from
                # the Phase 2 y-bake for exactly the same reason a tunnel
                # is excluded — the two corrections must never stack.
                basin_trench_enabled
                and is_carved_basin_interface(ground_interface)
            ):
                # Split-level structures whose terrain is adapted to them
                # join the R4 exclusion list exactly like tunnels (§3.4);
                # FLAT_CONFIRMED adapts nothing and stays bakeable.  With
                # the split-level adapter off NO interface terrain is
                # adapted, so every interface stays bakeable.
                for resource in ground_interface.object_resources:
                    exclusions.append((pack_root, resource))

    if skipped_pool_count:
        _vprint(
            2,
            "   [object-terrain] evidence pre-screen skipped "
            f"{skipped_pool_count} of {len(pools)} pool(s) with no "
            "classifiable geometry",
        )

    # Portal faces (EGGW class) — resource-level, pool-independent.
    # A recognized face joins the R4 exclusion feed unconditionally:
    # the Phase 2 y-bake would fit the face's BASE (its deepest below-
    # grade vertex) to the ground and shove the whole quad up by the
    # face height; whether or not a pair is later matched, seating a
    # terrain-feature face is the terrain's job, never the bake's.
    portal_faces = _detect_portal_faces(placements, geometry_by_resource)

    # The section-2.1 BELOW-GRADE REGIONS (spec basin-region-footprint).
    # Derived from the placement population, never from the pools — see
    # :func:`below_grade_regions`.  Computed only when the adapter that
    # consumes them is on AND the feature gate is on, so a gate-off build
    # pays nothing and emits a byte-identical patch.
    regions: list[BelowGradeRegion] = []
    if basin_trench_enabled:
        from .config import BASIN_REGION_FOOTPRINT

        if BASIN_REGION_FOOTPRINT:
            regions = below_grade_regions(
                placements, geometry_by_resource, cache=cache
            )
            # The openness reading, LAZILY (spec basin-region-founding
            # Amendment 1): only regions that intersect NO interface's
            # own below-grade footprint can ever reach founding, and the
            # interfaces are in hand right here.  Everything else keeps
            # ``None`` = NOT COMPUTED, which founding refuses out loud.
            regions = regions_with_lazy_above_grade_coverage(
                regions, ground_interfaces, placements,
                geometry_by_resource, cache=cache,
            )
            # ...and only THEN the RAMP REACH completion (spec
            # lemd-basin-trench-ramp-extension).  Order is law: every
            # number that gates founding — depth, openness, contributor
            # areas — is read above, on the ADMITTED ring, so completing
            # a region can never admit one.
            regions = regions_completed_to_ramp_reach(
                regions, placements, geometry_by_resource, cache=cache,
            )
            # ...and the LIVE lever (spec Amendment 1 §2): the ramp is
            # carried BESIDE the ring, never folded into it.  Same
            # derivation, opposite disposition.
            regions = regions_with_ramp_reach_corridor(
                regions, placements, geometry_by_resource, cache=cache,
            )
            for region in regions:
                centroid = region.polygon.centroid
                origin_longitude, origin_latitude = (
                    region.frame_origin_longitude_latitude
                )
                latitude, longitude = obj8_reader.local_offset_to_lonlat(
                    origin_latitude,
                    origin_longitude,
                    0.0,
                    centroid.x,
                    centroid.y,
                )
                names = [
                    resource.split("/")[-1]
                    for resource in region.object_resources
                ]
                _vprint(
                    1,
                    "   [object-terrain] below-grade region "
                    f"{region.polygon.area:,.0f} m² at "
                    f"{latitude:.7f},{longitude:.7f}, deepest solid "
                    f"{region.solid_minimum_y_m:.3f} m, from "
                    f"{len(names)} resource(s): {names[:6]}",
                )

    excluded_resources = {resource for _root, resource in exclusions}
    for face in portal_faces:
        for resource in face.object_resources:
            if resource not in excluded_resources:
                exclusions.append((pack_root, resource))
                excluded_resources.add(resource)

    return ClassificationResult(
        tunnels=tunnels,
        bridges=bridges,
        exclusions=exclusions,
        refusals=refusals,
        ground_interfaces=ground_interfaces,
        portal_faces=portal_faces,
        below_grade_regions=regions,
    )
