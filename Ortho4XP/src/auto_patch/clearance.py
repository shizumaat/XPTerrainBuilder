"""Wingtip / RESA terrain-clearance grading.

Aircraft wingspans exceed the paved width of taxiways and runways, so
the design standards (FAA AC 150/5300-13 Taxiway Object Free Area;
ICAO Annex 14 graded runway strip + Runway End Safety Area) reserve a
clear, gently-graded band on each side of a surface and a graded area
off each runway end.  A hill that rises into that band — into the
wingtip envelope alongside, or into the approach off the end — must be
graded DOWN so it transitions smoothly to the pavement edge.

This module samples the DEM along each surface edge/centerline and
emits grading polygons.  The LATERAL strips are FLAT shadows of the
surface they protect: at each station the strip sits at the local
pavement-edge altitude and extends out level, so it follows the
surface's longitudinal profile like an extension of the pavement.
Terrain is cut down to that surface level ONLY where the DEM rises
above it within the protected (code-letter wingtip) width; terrain at
or below the surface is left alone (the wingtip clears it).  Because
the cut floor IS the surface level, a lateral strip can never push
terrain below the pavement it protects — so a pavement that sits below
its surroundings (cut into a hillside, or sunk by the elevation solver)
no longer carves a canyon.

The runway-end RESA is the exception: it RAMPS from the runway-end
elevation at a gentle slope and daylights where it meets the DEM, so an
over-run/undershoot meets a slope rather than a wall.

Four passes share one strip builder:
  * taxiway lateral strips   (ROLE_TAXIWAY_CLEARANCE) — flat shadow,
    traced from the apt.dat taxi centerline network (+ enclosed-pocket
    perimeters, Pass A2)
  * airside ring-edge sweep  (Pass A3) — flat shadow off every
    TERRAIN-FACING pavement ring edge (junctions, aprons, per-node
    runway pieces, service roads) at the local rendered edge altitude
  * runway lateral strips    (ROLE_RUNWAY_CLEARANCE)  — flat shadow
  * runway-end RESA areas     (ROLE_RUNWAY_CLEARANCE)  — ramp

The legacy multi-pass clearance emitter described above was RETIRED
(owner ruling 2026-07-26): the adjacent-ground bands + runway-end skirts
supersede it.  Recover ``emit_surface_clearance_cuts`` from git history
if ever needed.

Public API:
    emit_runway_end_skirts(layout, dem, tile_lat, tile_lon)
    road_corridors_from_ways(...) / airport_road_feed_corridors(...)
"""
from __future__ import annotations

import math
import os
from collections import defaultdict

import numpy as np
import shapely
import O4_UI_Utils as UI
from shapely import STRtree
from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import box, LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

# Narrow exception tuple — shapely degeneracy / DEM I/O.  Programming
# errors propagate (see boundary.py for the rationale).
_GEOM_EXC = (ValueError, GEOSException, TopologicalError)

from .config import (
    CLEARANCE_MAX_REACH_M,
    CLEARANCE_OBSTRUCTION_THRESHOLD_M,
    CLEARANCE_STATION_STEP_M,
    CLEARANCE_LATERAL_MAX_SLOPE,
    eat_surface_slope_and_setback,
    runway_code_letter,
    runway_code_number,
    RUNWAY_END_RESA_ENABLED,
    RUNWAY_END_RESA_MAX_SLOPE,
    RUNWAY_END_SKIRT_ENABLED,
    TAIL_HEIGHT_BY_CODE_LETTER,
    runway_end_approach_class,
    runway_strip_half_width_m,
    taxiway_clearance_half_width_for_letter,
    taxiway_clearance_half_width_m,
)
from .grade_law import (
    RUNWAY_END_SKIRT_MAX_DOWN_GRADE,
    runway_end_constrained_length_m,
    runway_end_corridor_half_width_m,
    runway_end_governed_length_beyond_pavement_m,
    runway_end_governed_length_m,
    runway_end_skirt_floor_profile,
    runway_end_skirt_floor_profile_beyond_pavement,
    runway_end_skirt_profile_breakpoints,
    runway_end_skirt_profile_breakpoints_beyond_pavement,
)
from .layout import (
    BuiltShape,
    PavementLayout,
    R_EARTH,
    REF_RUNWAY_END_RESA,
    REF_RUNWAY_END_SKIRT,
    ROLE_APRON,
    ROLE_CROSS_CONNECTOR,
    ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL,
    ROLE_RUNWAY,
    ROLE_RUNWAY_CLEARANCE,
    ROLE_RUNWAY_CROSSING,
    ROLE_SECONDARY_PARALLEL,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
    ROLE_STUB,
    ROLE_TAXIWAY_CLEARANCE,
    SHARED_VERTEX_TOL_M,
    vertex_bucket,
)
from .elevation import _sample_dem, _resample_node_altitudes_nn
from .geom_safe import min_rotated_rect
from .pavement.junctions import _decompose_polygon_with_holes
from .pavement.runways import _sample_runway_segment_elev

__all__ = ["emit_runway_end_skirts",
           "road_corridors_from_ways", "airport_road_feed_corridors"]


_TAXIWAY_ROLES = (
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR,
)
# Minimum emitted cut area; smaller residue is dropped as noise.
_MIN_CUT_AREA_M2 = 25.0
# Minimum area a trimmed groundside-pavement remnant must keep to survive
# the skirt airside-precedence trim (Noah ruling 2026-07-10).  A groundside
# shape reduced below this (or to nothing) by the skirt footprint is dropped
# WHOLE — a sub-50 m² sliver welded onto the skirt chain is exactly the
# near-parallel confetti the mesher Ruppert-explodes on.
_GROUNDSIDE_TRIM_MIN_M2 = 50.0
# Keep every emitted cut vertex this far OUTSIDE pavement so it never
# lands on a sloping rect's edge (``check_vertex_on_sloping_edge`` /
# ``test_no_vertex_on_sloping_rect_edge`` flag a non-rect vertex within
# ``EDGE_PROX_M`` = 0.5 m of a rect edge interior) and never merges with
# a pavement ring vertex (``SHARED_VERTEX_TOL_M`` = 0.5 m).  Reduced from
# 1.5 → 1.0 m (user 2026-07-07: clearance cuts should hug the pavement
# they follow) — still 2× the 0.5 m merge/edge-proximity floor, so the
# inner edge never lands on or merges with pavement, but the visible
# crack band between pavement and cut halves.
_PAVEMENT_GAP_M = 1.0
# Flank pavement-edge reference-step tolerance (SPLP runway-20 flank,
# 2026-07-17): the noise floor above the law down-grade before a jump in
# the tracked pavement-edge altitude between adjacent flank stations is
# treated as a pavement-LEVEL discontinuity the fill must not bridge.
# Matches the emitted-patch reader's ``skirt_edge_noise_m``.
_SKIRT_REF_STEP_NOISE_M = 0.15
# Enclosed-pocket wingtip clearance (Pass A2, user 2026-06-30): ring the full
# perimeter of a small NON-pavement pocket fully enclosed by taxi pavement, so
# sharp terrain a wingtip overhangs is cut even where no centerline reaches it.
# O4_POCKET_CLEARANCE=0 disables it (revert to centerline-only junction clearance).
_POCKET_CLEARANCE = os.environ.get("O4_POCKET_CLEARANCE", "1") == "1"
# LEGACY CLEARANCE CHARTER (Noah ruling 2026-07-10, in-sim round 6):
# surface_clearance is WINGTIP clearance along TAXIWAYS and RUNWAYS ONLY —
# never aprons, never service roads/groundside, never large terminal-area
# pieces.  When ON, the source-edge collection is scoped:
#   * the Pass-A3 airside ring-edge sweep does NOT run off APRON,
#     SERVICE_ROAD, or SERVICE_JUNCTION edges (an apron/service road is
#     not a taxiway or runway); and
#   * the Pass-A centerline trace skips SERVICE centerlines.
# Groundside/building never sourced clearance and keep their 1 m standoff
# for what remains (see static_union).
#
# DEFAULT OFF — this gate does NOT ship on yet.  A 2026-07-10 A/B at CYXY
# (this worktree) shows that turning it ON REGRESSES the build: removing
# the apron/service clearance UNCOVERS steep terminal terrain, which the
# adjacent-ground band-march then backfills with clip-seam artifacts —
# adjacent-ground TEARS 0 → 10 (worst 8.98 m over 0.66 m), one NEW
# apron~graded_strip near-parallel lens, coincident nodes 3 → 70.  That
# is the SAME legacy-off flip blocker STATUS records (just smaller), and
# it fails the charter's own acceptance gates (tears stay 0; zero new
# near-parallel).  The apron/service pieces are, for now, HOLDING terrain
# the adjacent-ground law cannot yet grade cleanly.
#
# NOTE (fresh provenance trace — overturns the handover hypothesis): the
# large terminal blobs Noah flagged (CYXY site-1 notch, hangar) are NOT
# apron-sourced.  They are dominated by JUNCTION ring sweeps (site-1 =
# one 28,215 m² junction sweep) plus RESA and centerline strips; apron
# edges were a minor contributor.  Dissolving the blobs therefore needs
# the JUNCTION sweep gone too, which trips the FULL flip regression
# (nodes +~1,900, coincident →~260).  Both the apron/service scope-shrink
# AND the junction/RESA blob shrink are SLICE-B acceptance criteria
# (adjacent-ground clip-seam coordination / solver absorption), not a
# fix-now (pre-slice-B policy, Noah ruling 4).
#
# The gate exists so slice-B can A/B against the charter target.  It is
# scope FILTERING at source-edge collection — no code path is deleted;
# O4_CLEARANCE_CHARTER=1 enables the (currently regressing) filter.
# The ONE B4 review switch (config.B4_FLIP_DEFAULTS) flips this default ON
# under the flip bundle; an explicit O4_CLEARANCE_CHARTER always wins.
# Applied as a post-assignment override so the gate keeps a plain "0"
# literal (see config.ADJACENT_GROUND_FULL_EXTENT_COVERAGE for the rationale).
from .config import B4_FLIP_DEFAULTS as _B4_FLIP_DEFAULTS
_CLEARANCE_CHARTER = os.environ.get("O4_CLEARANCE_CHARTER", "0") == "1"
if _B4_FLIP_DEFAULTS and "O4_CLEARANCE_CHARTER" not in os.environ:
    _CLEARANCE_CHARTER = True
# CHARTER EXTENSION (Slice B stage B4, Noah ruling 2026-07-10 verbatim:
# "surface_clearance = WINGTIP clearance along taxiways and runways ONLY
# — never aprons, never LARGE-AREA PIECES, never near groundside").  The
# partial charter above scopes out apron/service SOURCES.  This extension
# scopes out the remaining terminal/parking BLOBS: a JUNCTION/RESA ring
# sweep mints a clearance PIECE that is both LARGE (area >= this floor)
# AND CHUNKY (minimum-rotated-rectangle aspect < _MIN_LATERAL_ASPECT).  A
# genuine wingtip strip is ELONGATED by construction (the Pass-A
# centerline trace raycasts perpendicular to a taxiway/runway edge), so
# the aspect gate never touches one; only the chunky junction/RESA blobs
# Noah ruled out of scope (the CYXY 20,628 m² aspect-1.15 taxiway sweep
# and the ~18,400 m² aspect-1.30 runway/RESA sweep) leave.  Threshold
# trace: at CYXY the clearance-piece area/aspect distribution has a clean
# gap — chunky blobs run 5,017–20,628 m² at aspect 1.09–1.30 while the
# elongated strips that STAY are aspect >= 2.8 (the largest, 31,571 m²,
# is aspect 4.04); small chunky corner sweeps sit <= 1,615 m² and are
# below the area floor, so they too stay.  Byte-inert unless the charter
# gate is ON.
_CHARTER_BLOB_MIN_AREA_M2 = float(
    os.environ.get("O4_CHARTER_BLOB_MIN_AREA_M2", "3000.0"))
# Consecutive ring vertices closer than this are a degenerate zero-length
# edge that ``_decimate`` PRESERVES whenever their altitudes differ (it
# reads the altitude step as a real feature).  At emit they become two
# nodes at one spot several metres apart vertically — a torn vertical
# micro-cliff.  Below this tolerance the edge has no real length, so the
# pair is collapsed to one vertex at the mean altitude (see
# ``_merge_coincident_ring_vertices``).  Well under ``_DECIMATE_GEOM_TOL_M``
# so it never merges vertices ``_decimate`` keeps for genuine geometry.
_COINCIDENT_MERGE_TOL_M = 0.1
# Airside pavement a taxi centerline can run over — used to find the
# pavement edge (raycast) and the edge altitude, regardless of whether
# that pavement was emitted as a rect, junction, or apron.
_AIRSIDE_PAVEMENT_ROLES = (
    ROLE_RUNWAY, ROLE_RUNWAY_CROSSING,
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR,
    ROLE_JUNCTION, ROLE_APRON,
)
# Pass A3 ring-edge sweep: a ring-edge station only faces TERRAIN when
# the point this far outward is not covered by any already-emitted
# shape (adjacent pavement / ribbon / building / groundside all own
# their band).  Just past ``_PAVEMENT_GAP_M`` so a shared shape edge is
# reliably detected, well under the narrowest service-road width.
# Tracks the reduced 1.0 m gap (user 2026-07-07 tighter standoff).
_RING_PROBE_M = 1.5
# Pass A3 skips a runway-family ring-edge station whose outward normal
# points mostly ALONG the runway axis (an END edge): the runway end is
# RESA / skirt territory (Pass C / D) and must stay exactly as it is.
_RING_END_NORMAL_DOT = 0.7
# How far past the runway end to search for the outer pavement edge
# (blast-pad / stopway / apron) the RESA should anchor on.
_RESA_PAVEMENT_PROBE_MAX_M = 300.0
# When the RESA end is taken from the authoritative apt.dat row-100
# centreline endpoint, that point sits ON the runway end edge, not in the
# interior — seed the outward pavement-exit march this far INSIDE so it
# starts on pavement.
_RESA_SEED_INSET_M = 3.0
# Window (m) over which the runway's own end grade is measured for the
# Pass D skirt, so a DESCENDING runway hands its grade to the skirt
# without a crease.  Module-level so the ``verification`` reader
# measures the entry grade EXACTLY as the emitter does (lockstep).
_SKIRT_END_GRADE_WINDOW_M = 30.0


# ──────────────────────────────────────────────────────────────────
# Small geometry helpers
# ──────────────────────────────────────────────────────────────────
# An ALTITUDE needle: a single ring vertex whose altitude differs from
# BOTH of its ring neighbours by more than this, while the two
# neighbours agree with each other to within it.  The finalize resample
# assigns each final-ring vertex the altitude of the NEAREST source
# strip edge; where strips from different bands (e.g. a low apron cut
# beside a higher runway strip, or a thin corridor whose inner and
# outer rows pass within ``EDGE_TOL_M`` of one another at a concave
# jog) meet, one vertex can flip to the far edge and spike metres
# above/below its neighbours — the "terrain spike at a little jog" /
# "pointy cut" the user sees (CYXY carried 3 such needles before the
# part-30f declaw).  A real daylight-contour ramp changes monotonically
# across several vertices; an isolated single-vertex reversal is always
# this artifact, so it is clamped to the neighbour mean.
_NEEDLE_ALT_TOL_M = 3.0


def _open_coords(poly: Polygon) -> list[tuple[float, float]]:
    """Exterior ring as an OPEN coord list (closing repeat dropped)."""
    try:
        coords = list(poly.exterior.coords)
    except _GEOM_EXC:
        return []
    if coords and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [(float(x), float(y)) for x, y in coords]


def _unit(dx: float, dy: float) -> tuple[float, float] | None:
    d = math.hypot(dx, dy)
    if d < 1e-9:
        return None
    return (dx / d, dy / d)


def _outward_normal(poly: Polygon, a: tuple[float, float],
                    b: tuple[float, float]) -> tuple[float, float] | None:
    """Unit normal of edge ``a→b`` pointing AWAY from the polygon
    interior (so marching along it leaves the surface)."""
    u = _unit(b[0] - a[0], b[1] - a[1])
    if u is None:
        return None
    nx, ny = -u[1], u[0]
    mx, my = 0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1])
    try:
        c = poly.centroid
    except _GEOM_EXC:
        return (nx, ny)
    # Flip so the normal points away from the centroid.
    if (mx - c.x) * nx + (my - c.y) * ny < 0.0:
        nx, ny = -nx, -ny
    return (nx, ny)


def _stations(a: tuple[float, float], b: tuple[float, float],
              step: float) -> list[tuple[float, float]]:
    """Sample ``a→b`` (inclusive of both ends) at ≤ ``step`` spacing."""
    d = math.hypot(b[0] - a[0], b[1] - a[1])
    n = max(1, int(math.ceil(d / step)))
    return [(a[0] + (b[0] - a[0]) * k / n,
             a[1] + (b[1] - a[1]) * k / n) for k in range(n + 1)]


def _merge_coincident_ring_vertices(
        coords: list[tuple[float, float]],
        alts: list[float],
        tol_m: float = _COINCIDENT_MERGE_TOL_M,
        frozen_predicate=None):
    """Collapse consecutive near-coincident ring vertices into one.

    ``_decimate`` keeps a vertex sitting a few mm from its neighbour
    whenever their altitudes differ (it preserves altitude features), so
    a zero-length edge across an altitude step survives into the emitted
    polygon — two nodes at one XY metres apart vertically, which X-Plane
    renders as a torn vertical micro-cliff.  Below ``tol_m`` the edge has
    no real length, so merge each coincident run to a single vertex at the
    GROUP-MEAN altitude (open-form ``(coords, alts)`` in, same out).

    ``frozen_predicate(x, y)`` marks welded chain vertices sitting on a
    shared (pavement) boundary; the merge must never move such a vertex.
    When supplied: a coincident pair with BOTH ends frozen is left intact
    (distinct chain nodes); with exactly ONE end frozen the pair collapses
    onto the frozen vertex VERBATIM (its coordinates and altitude win,
    never the mean); with NEITHER end frozen the group-mean merge applies.
    """
    coords = [(float(x), float(y)) for x, y in coords]
    alts = [float(a) for a in alts]
    tol2 = tol_m * tol_m
    changed = True
    while changed and len(coords) > 3:
        changed = False
        n = len(coords)
        for i in range(n):
            j = (i + 1) % n
            dx = coords[i][0] - coords[j][0]
            dy = coords[i][1] - coords[j][1]
            if dx * dx + dy * dy > tol2:
                continue
            if frozen_predicate is not None:
                fi = frozen_predicate(coords[i][0], coords[i][1])
                fj = frozen_predicate(coords[j][0], coords[j][1])
                if fi and fj:
                    continue     # both welded: distinct chain vertices
                if fi:
                    pass         # survivor coords[i]/alts[i] are frozen
                elif fj:
                    coords[i] = coords[j]     # frozen coords win verbatim
                    alts[i] = alts[j]         # frozen altitude wins
                else:
                    coords[i] = ((coords[i][0] + coords[j][0]) / 2.0,
                                 (coords[i][1] + coords[j][1]) / 2.0)
                    alts[i] = round((alts[i] + alts[j]) / 2.0, 1)
            else:
                coords[i] = ((coords[i][0] + coords[j][0]) / 2.0,
                             (coords[i][1] + coords[j][1]) / 2.0)
                alts[i] = round((alts[i] + alts[j]) / 2.0, 1)
            del coords[j]
            del alts[j]
            changed = True
            break
    return coords, alts


def _declaw_alt_needles(alts_open: list[float],
                        tol: float = _NEEDLE_ALT_TOL_M) -> list[float]:
    """Clamp isolated single-vertex altitude spikes to the neighbour mean.

    Operates on an OPEN (unclosed) per-vertex altitude ring.  A vertex is
    a needle when it differs from BOTH ring neighbours by more than
    ``tol`` in the SAME direction while the neighbours agree to within
    ``tol`` (see ``_NEEDLE_ALT_TOL_M``).  Such a vertex is a resample
    flip between the cut's inner (pavement-level) and outer (terrain-
    daylight) edges, not a real surface feature, so it is set to the mean
    of its two neighbours.  Repeats until stable so a two-vertex flip
    resolves.  Returns a new list; positions are untouched (geometry is
    unchanged — only the altitude is corrected)."""
    n = len(alts_open)
    if n < 3:
        return list(alts_open)
    a = [float(v) for v in alts_open]
    for _ in range(n):
        changed = False
        for i in range(n):
            p = a[(i - 1) % n]
            c = a[i]
            q = a[(i + 1) % n]
            d1 = c - p
            d2 = c - q
            if (d1 * d2 > 0.0
                    and min(abs(d1), abs(d2)) > tol
                    and abs(p - q) <= tol):
                a[i] = round((p + q) / 2.0, 1)
                changed = True
        if not changed:
            break
    return a




def _rect_long_short_edges(coords: list[tuple[float, float]]):
    """For a 4-corner ring, return ``(long_edges, short_len)`` where
    ``long_edges`` is the two longest edges as ``((a, b), ...)`` corner
    pairs and ``short_len`` is the mean of the two shortest edges."""
    if len(coords) != 4:
        return None
    edges = []
    for i in range(4):
        a = coords[i]
        b = coords[(i + 1) % 4]
        edges.append((math.hypot(b[0] - a[0], b[1] - a[1]), a, b))
    edges.sort(key=lambda e: e[0])
    short_len = 0.5 * (edges[0][0] + edges[1][0])
    long_edges = [(edges[2][1], edges[2][2]), (edges[3][1], edges[3][2])]
    long_len = 0.5 * (edges[2][0] + edges[3][0])
    return long_edges, short_len, long_len


_WELD_RING_VERTEX_SEARCH_LIMIT = 64   # stations (~320 m at the 5 m step)


def _thin_weld_row_to_ring_vertices(inner_pts, inner_alts, inner_idx,
                                    edge_stations, edge_alts,
                                    is_ring_vertex):
    """Thin a graded strip's inner weld row to EXACT pavement ring
    vertices (user ruling 2026-07-09: a grading shape never MINTS a
    node on a pavement edge).

    Between ring vertices the pavement edge is straight and its rendered
    value profile linear (``node_altitudes`` interpolate along the
    edge), so interior weld stations add nodes without information — the
    mesh lerp reproduces them exactly.  The row keeps only the stations
    the caller marked as exact ring vertices; where a run's end station
    is NOT a ring vertex the weld chain EXTENDS outward along the
    station list to the nearest bracketing ring-vertex station (the far
    corner of the ring edge the run ends on — the stations between are
    collinear subdivisions of that edge, so the extended chain stays
    exactly on the pavement edge), searching up to
    ``_WELD_RING_VERTEX_SEARCH_LIMIT`` stations.  Extension is the SAFE
    direction: shrinking the row to interior ring vertices would chord
    the closing cap across obstructed terrain right at the pavement
    edge (the knife-edge class the weld ruling removed); extending only
    widens the benign taper wedge.  When no bracketing ring vertex is
    within reach, the run-endpoint station is kept as before (a minted
    mid-edge node — the pre-thinning behaviour, the mandated fallback).

    ``inner_idx`` maps each inner-row entry to its station index in
    ``edge_stations``.  Returns the thinned ``(inner_pts, inner_alts)``.
    """
    n = len(edge_stations)

    def _bracket_station(start, direction):
        j = start + direction
        remaining = _WELD_RING_VERTEX_SEARCH_LIMIT
        while 0 <= j < n and remaining > 0:
            if is_ring_vertex[j]:
                return j
            j += direction
            remaining -= 1
        return None

    def _station_entry(j, borrow_alt):
        # An extension station beyond the run may carry no edge altitude
        # (a pavement-facing / skipped station); borrow the nearest
        # run-end value exactly as the taper neighbours do.
        alt = edge_alts[j]
        return (edge_stations[j],
                round(float(alt if alt is not None else borrow_alt), 1))

    kept = [(inner_pts[k], inner_alts[k])
            for k in range(len(inner_idx))
            if is_ring_vertex[inner_idx[k]]]
    if not is_ring_vertex[inner_idx[0]]:
        j = _bracket_station(inner_idx[0], -1)
        kept.insert(0, _station_entry(j, inner_alts[0])
                    if j is not None else (inner_pts[0], inner_alts[0]))
    if not is_ring_vertex[inner_idx[-1]]:
        j = _bracket_station(inner_idx[-1], +1)
        kept.append(_station_entry(j, inner_alts[-1])
                    if j is not None else (inner_pts[-1], inner_alts[-1]))
    # Collapse coincident neighbours (insurance — a degenerate station
    # list could keep two copies of one corner as a zero-length edge).
    pts: list[tuple[float, float]] = []
    alts: list[float] = []
    for p, a in kept:
        if pts and pts[-1] == p:
            continue
        pts.append(p)
        alts.append(a)
    return pts, alts


def _build_graded_strips(edge_stations, edge_alts, outwards,
                         band_caps, slope, trigger, step, sample_dem,
                         is_ring_vertex=None):
    """Build clearance cut-strip rings off an edge / pavement-edge
    polyline.  At each station the ceiling rises from the pavement edge
    altitude at ``slope`` (rise/run):

        ceiling(d) = edge_alt + slope · d

    Two regimes share this code:
      * ``slope == 0`` (LATERAL strips) — the ceiling is FLAT at the
        pavement-edge altitude, so the strip is a level extension of the
        surface following its longitudinal profile (each station carries
        its own ``edge_alt``).  Terrain is cut to surface level only
        where it rises above it; the strip daylights where the DEM drops
        back to the surface.  Never produces a sub-surface floor, so it
        can't carve a canyon beside a pavement that sits below grade.
      * ``slope > 0`` (RESA end-caps) — the ceiling is a gentle ramp, so
        an over-run meets a slope rather than a wall.

    Terrain above the ceiling is cut down to it, and the cut DAYLIGHTS
    where the ceiling meets the DEM — so the graded patch is only as wide
    as it needs to be, capped at ``band_caps[i]`` (the code-letter
    wingtip width minus the pavement half-width).  Cut-only: a station
    contributes a strip ONLY where the terrain rises more than
    ``trigger`` m above the ceiling; flat or falling terrain is left
    untouched.

    ``edge_stations`` / ``edge_alts`` / ``outwards`` / ``band_caps`` are
    matched per-station lists (so the edge may curve, e.g. a centerline).
    Returns ``(ring_open, alts_open)`` pairs.

    ``is_ring_vertex`` (optional, per-station bools) marks the stations
    that are EXACT pavement ring vertices (a ring-edge subdivision's
    ``k == 0`` points); when supplied, the inner weld row is thinned to
    those vertices via ``_thin_weld_row_to_ring_vertices`` (no minted
    mid-edge pavement nodes; user ruling 2026-07-09).  When ``None``,
    full density (unchanged behaviour) — callers whose stations are NOT
    ring-edge subdivisions (centerline raycasts, the RESA end line)
    must pass ``None``.  Outer (daylight) rows always keep full density.
    """
    n = len(edge_stations)
    outer: list[float] = [0.0] * n
    obstructed: list[bool] = [False] * n
    for i, (sx, sy) in enumerate(edge_stations):
        ref = edge_alts[i]
        if ref is None:
            continue
        nx, ny = outwards[i]
        cap = band_caps[i]
        if cap <= _PAVEMENT_GAP_M:
            continue
        nst = max(1, int(math.ceil(cap / step)))
        last = 0.0
        for k in range(1, nst + 1):
            d = min(cap, k * step)
            ceil = ref + slope * d
            dd = sample_dem(sx + nx * d, sy + ny * d)
            if dd is not None and dd > ceil + trigger:
                last = d
        if last > 0.0:
            obstructed[i] = True
            outer[i] = min(cap, last + step)
    # Group consecutive obstructed stations into runs (1-station slack).
    idx = [i for i in range(n) if obstructed[i]]
    if not idx:
        return []
    runs: list[list[int]] = []
    cur = [idx[0]]
    for j in idx[1:]:
        if j - cur[-1] <= 2:
            cur.append(j)
        else:
            runs.append(cur)
            cur = [j]
    runs.append(cur)

    out: list[tuple[list, list]] = []
    for run in runs:
        i0, i1 = run[0], run[-1]
        # Widen the run by one station each side so the cut tapers
        # longitudinally to its neighbours instead of ending in a wall.
        lo = max(0, i0 - 1)
        hi = min(n - 1, i1 + 1)
        inner_pts, inner_alts, inner_idx = [], [], []
        outer_pts, outer_alts = [], []
        for i in range(lo, hi + 1):
            ref = edge_alts[i]
            if ref is None:
                # Widened taper neighbour beyond a skipped (pavement-
                # facing / altitude-less) station: borrow the run-end
                # station's edge altitude so a SHORT run still emits a
                # strip.  A single obstructed station between two
                # skipped ones used to yield a 1-vertex row and drop
                # the whole cut (HECA apron/service-road corridors).
                if i < i0:
                    ref = edge_alts[i0]
                elif i > i1:
                    ref = edge_alts[i1]
                if ref is None:
                    continue
            nx, ny = outwards[i]
            off = outer[i] if outer[i] > 0.0 else step
            sx, sy = edge_stations[i]
            # Inner edge AT the pavement edge, at the pavement edge
            # altitude — the cut WELDS to the surface it protects (weld
            # ruling 2026-07-09; the former 1 m standoff left a groove
            # of raw DEM rendered as a knife-edge blade along the edge).
            inner_alts.append(round(float(ref), 1))
            inner_pts.append((sx, sy))
            inner_idx.append(i)
            # Outer edge: at the daylight point, on the ceiling, so the
            # whole band is graded to the protective surface and the cut
            # meets natural ground where the terrain has daylit.  Where
            # the terrain has NOT daylit within the band cap (pavement
            # dug in below its surroundings) this leaves a cut FACE at
            # the band edge — that is the cut doing its job, not a
            # defect (part 30k, user in-sim ruling: an un-cut cliff
            # beside pavement is the complaint; the excavation is
            # wanted).  Part 30f briefly lifted this row to
            # max(ceiling, DEM): that tilted whole cut surfaces up to
            # the DEM so they capped nothing (HECA: 508/2281 cut
            # vertices rode the DEM vs 40 before; a trapped-station-only
            # lift still left 339 riding above even a 5% ramp allowance
            # because HECA is broadly dug-in) — reverted.  The single-
            # vertex spike class 30f also fixed stays fixed by
            # ``_declaw_alt_needles`` (FIX B) and the tighter standoff
            # (FIX C), both kept.
            ox, oy = sx + nx * off, sy + ny * off
            outer_pts.append((ox, oy))
            outer_alts.append(round(float(ref + slope * off), 1))
        if len(inner_pts) < 2:
            continue
        if is_ring_vertex is not None:
            inner_pts, inner_alts = _thin_weld_row_to_ring_vertices(
                inner_pts, inner_alts, inner_idx,
                edge_stations, edge_alts, is_ring_vertex)
            if len(inner_pts) < 2:
                continue
        ring = inner_pts + outer_pts[::-1]
        alts = inner_alts + outer_alts[::-1]
        out.append((ring, alts))
    return out


# ──────────────────────────────────────────────────────────────────
# Core: build FILL skirts off one edge (the inverse of the cut strips)
# ──────────────────────────────────────────────────────────────────
def _skirt_lift_alt(analytic_floor: float, dem_alt) -> float:
    """The lawful skirt altitude at a vertex: ``max(floor, DEM)``.

    The skirt is FILL-only (the exact mirror of the cut passes'
    flat-shadow convention — cuts never fill, fills never cut; see
    docs/STANDARDS.md "Lateral (wingtip) clearance").  A band triggers
    only where the terrain falls MORE than the trigger below the floor,
    but the emitted band can still SPAN vertices whose DEM sits AT or
    ABOVE the floor (a bump inside a hollow; the last+step overshoot at
    a run's end).  Grading those DOWN to the analytic floor would carve
    an unnecessary cut ramp — so every skirt vertex lifts to the higher
    of the analytic floor and the DEM.  A vertex at/above the floor that
    descends no lower than the floor profile is lawful; the down-grade
    caps bound how far BELOW the floor is reachable, not how the surface
    rides an existing bump back up.  Shared verbatim by the emitter's
    ring altitudes and its analytic ``alt_at`` closures so shared band
    boundary rows compute the SAME max'ed value and the surface never
    tears."""
    if dem_alt is None:
        return analytic_floor
    return max(analytic_floor, float(dem_alt))


def _resa_cut_alt(analytic_ceiling: float, dem_alt) -> float:
    """The lawful runway-END RESA-cut altitude at a vertex:
    ``min(ceiling, DEM)`` — the exact mirror of the skirt's lift-only
    ``_skirt_lift_alt``.

    The cut is CUT-ONLY (cuts never fill, fills never cut; see
    docs/STANDARDS.md "Lateral (wingtip) clearance").  A strip triggers
    only where the terrain rises MORE than the trigger above the RESA
    ceiling, but the emitted piece can still SPAN vertices whose DEM sits
    AT or BELOW the ceiling (the daylight overshoot at a run's end, a
    hollow inside a ridge, a clip-introduced vertex).  Grading those UP
    to the analytic ceiling would FILL — the skirt's job, on the skirt's
    own law — so every cut vertex drops to the lower of the analytic
    ceiling and the DEM.  Shared verbatim by the emitter's analytic
    ``alt_at`` closure so clip-introduced vertices obey the same rule as
    the raw ring."""
    if dem_alt is None:
        return analytic_ceiling
    return min(analytic_ceiling, float(dem_alt))


def _fill_lateral_refs(raw_refs, scalar_ref, spacing):
    """Dense per-station EXIT-ROW reference profile from sparse local
    pavement reads (KCLT skirt #845, 2026-07-26).

    ``raw_refs`` holds one entry per exit-row station: the local
    pavement-edge altitude where the station touches pavement (the same
    containment-free read the weld row carries), else ``None``.  The
    returned profile anchors the skirt floor so the weld/no-weld
    transition is continuous: interior gaps interpolate linearly
    between their valid neighbours and the row ends HOLD the outermost
    valid value.  An off-pavement station is NEVER given a nearest-
    pavement read of its own — that imports a FOREIGN shape's value
    (the 63 % skirt-edge spike class of the first weld round); holding
    this end's own edge profile laterally cannot.

    Falls back to ``[scalar_ref] * n`` — the single centre-line anchor,
    today's behaviour verbatim — when
      * no station touches pavement (the plain daylighting end), or
      * two valid stations step faster than the skirt's lawful
        down-grade over their separation (the SPLP flank class: a fill
        reference must never bridge a pavement-level wall — see the
        flank's discontinuity split).
    """
    n = len(raw_refs)
    valid = [i for i, v in enumerate(raw_refs) if v is not None]
    if not valid:
        return [float(scalar_ref)] * n
    for a, b in zip(valid, valid[1:]):
        dist = (b - a) * spacing
        if abs(raw_refs[b] - raw_refs[a]) > (
                RUNWAY_END_SKIRT_MAX_DOWN_GRADE * dist
                + _SKIRT_REF_STEP_NOISE_M):
            return [float(scalar_ref)] * n
    refs = [float(v) if v is not None else 0.0 for v in raw_refs]
    first, last = valid[0], valid[-1]
    for i in range(first):
        refs[i] = refs[first]
    for i in range(last + 1, n):
        refs[i] = refs[last]
    for a, b in zip(valid, valid[1:]):
        for i in range(a + 1, b):
            w = (i - a) / (b - a)
            refs[i] = refs[a] + (refs[b] - refs[a]) * w
    return refs


def _build_filled_skirts(edge_stations, edge_alts, outwards,
                         band_caps, floor_depth, band_edges, trigger,
                         step, sample_dem, weld_predicate=None,
                         pav_vertex_at=None):
    """Fill-direction twin of ``_build_graded_strips``: at each station a
    FLOOR descends from the pavement-end altitude,

        floor(d) = edge_alt − floor_depth(d)

    (``floor_depth`` is the law's lowest-lawful-surface profile,
    ``grade_law.runway_end_skirt_floor_profile``, as a per-distance
    callable).  Terrain BELOW the floor is filled up to it, and the fill
    DAYLIGHTS where the floor meets the DEM — so the skirt is only as
    long as it needs to be, capped at ``band_caps[i]`` (the governed
    length; beyond it a drop is lawful).  Fill-only: a station
    contributes ONLY where the terrain falls more than ``trigger`` m
    below the floor; flat or rising terrain is left untouched (that is
    the cut passes' domain).

    Unlike the cut twin (whose linear ceiling a two-row ring renders
    exactly), the floor is CURVED (piecewise quadratic), and a
    ``node_altitudes`` polygon renders as a ruled surface between its
    rows — a single inner/outer ring would sag metres below the law
    floor mid-span.  So the skirt is emitted as ABUTTING BANDS split at
    ``band_edges`` (the law's own grade breakpoints,
    ``grade_law.runway_end_skirt_profile_breakpoints``): within a band
    the floor is one quadratic, bounding the chord sagitta at
    ``rate·L²/8`` (≤ 0.31 m) — far inside the fill trigger.  Adjacent
    bands share their boundary row vertices (same positions, same
    rounded altitudes), so they render as one continuous surface.

    Returns ``(ring_open, alts_open)`` pairs, one per (band × station
    run); the first band's inner edge sits a small gap outside the
    pavement at the floor's start altitude, each band's outer edge at
    the band boundary — or earlier, at the daylight point on the floor
    (= DEM there), so the fill meets natural ground with no step.

    ``weld_predicate`` (optional, ``(x, y) -> bool``) thins the
    innermost band's inner weld row (``d0 == 0``): between its run
    endpoints only the weld TRANSITIONS survive — the row's value
    profile is piecewise-linear with breakpoints only at run ends and
    the points where the predicate FLIPS, so the mesh lerp reproduces
    the dropped interior stations exactly (mirror of the adjacent-ground
    diet, ``adjacent_ground._build_fill_bands``).  When ``None`` the row
    keeps full density (unchanged behaviour).  Deeper bands (``d0 > 0``)
    and every outer row always keep full density.

    A grading shape must never MINT a node on a pavement edge (user
    ruling 2026-07-09): wherever the inner row touches pavement its
    vertices must be EXISTING pavement ring vertices.  So at each weld
    transition, instead of keeping the two bracketing stations, the row
    takes the single EXACT pavement ring vertex nearest the flip
    (``pav_vertex_at(x, y) -> (x, y) | None``, within one station
    spacing); run endpoints that lie ON pavement are snapped the same
    way, endpoints OFF pavement (the ±half ref-floor stretch) stay as
    station points.  If the exact-vertex lookup fails for a transition
    (no pavement vertex within one station spacing) the row falls back
    to keeping the two bracketing stations and the miss is reported.
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
        last = 0.0
        for k in range(1, nst + 1):
            d = min(cap, k * step)
            floor = ref - floor_depth(d)
            dd = sample_dem(sx + nx * d, sy + ny * d)
            if dd is not None and dd < floor - trigger:
                last = d
        if last > 0.0:
            dropped[i] = True
            outer[i] = min(cap, last + step)
    if not any(dropped):
        return []
    # Band boundaries: pavement edge (weld, d = 0) → law breakpoints →
    # governed cap.  The first band's inner row sits ON the pavement it
    # fills off (weld ruling 2026-07-09 — no standoff groove).
    edges = [0.0]
    for b in sorted(band_edges):
        if 1.0 < b < cap_max - 1.0:
            edges.append(float(b))
    edges.append(cap_max)

    out: list[tuple[list, list]] = []
    corner_fallbacks = 0    # weld transitions with no exact pavement vertex
    for b in range(len(edges) - 1):
        d0, d1 = edges[b], edges[b + 1]
        # Stations whose fill reaches into this band.
        idx = [i for i in range(n) if dropped[i] and outer[i] > d0]
        if not idx:
            continue
        runs: list[list[int]] = []
        cur = [idx[0]]
        for j in idx[1:]:
            if j - cur[-1] <= 2:
                cur.append(j)
            else:
                runs.append(cur)
                cur = [j]
        runs.append(cur)
        for run in runs:
            i0, i1 = run[0], run[-1]
            # Widen the FIRST band's runs by one station each side so
            # the fill tapers longitudinally to its neighbours instead
            # of ending in a wall; deeper bands end where their
            # stations do (their width-wise taper is the daylight).
            lo = max(0, i0 - 1) if b == 0 else i0
            hi = min(n - 1, i1 + 1) if b == 0 else i1
            # Thin only the innermost band's inner weld row (see the
            # ``weld_predicate`` docstring); deeper bands and every outer
            # row keep full density.  ``inner_row`` carries each surviving
            # station's (point, altitude, weld-flag) so the thinning can
            # look across neighbours after the sweep.
            thin_inner = d0 == 0.0 and weld_predicate is not None
            inner_row: list[tuple[tuple[float, float], float, bool]] = []
            outer_pts, outer_alts = [], []
            for i in range(lo, hi + 1):
                ref = edge_alts[i]
                if ref is None:
                    continue
                nx, ny = outwards[i]
                if outer[i] > d0:
                    off = min(d1, outer[i])
                elif b == 0:
                    # Taper neighbour of a first-band run.
                    off = step
                else:
                    continue
                sx, sy = edge_stations[i]
                ix, iy = sx + nx * d0, sy + ny * d0
                # Lift-only: the ring rides the HIGHER of the analytic
                # floor and the DEM at each vertex, so a triggered band
                # spanning a bump above the floor never cuts it down.
                inner_alt = round(_skirt_lift_alt(
                    float(ref - floor_depth(d0)),
                    sample_dem(ix, iy)), 1)
                weld = bool(weld_predicate(ix, iy)) if thin_inner else False
                inner_row.append(((ix, iy), inner_alt, weld))
                ox, oy = sx + nx * off, sy + ny * off
                outer_pts.append((ox, oy))
                outer_alts.append(round(_skirt_lift_alt(
                    float(ref - floor_depth(off)),
                    sample_dem(ox, oy)), 1))
            if len(inner_row) < 2:
                continue
            if thin_inner:
                m2 = len(inner_row)
                inner_pts, inner_alts = [], []

                def _emit_inner(pt, alt):
                    # Never mint a duplicate vertex (a snapped endpoint
                    # can coincide with a transition corner).
                    if inner_pts and inner_pts[-1] == pt:
                        return
                    inner_pts.append(pt)
                    inner_alts.append(alt)

                def _resolve_on_pav(a):
                    # A kept vertex ON pavement must be an EXISTING
                    # pavement ring vertex, never a freshly minted node.
                    pt, alt, _w = inner_row[a]
                    if pav_vertex_at is not None:
                        snap = pav_vertex_at(pt[0], pt[1])
                        if snap is not None:
                            return snap, alt
                    return pt, alt

                def _endpoint(a):
                    return (_resolve_on_pav(a) if inner_row[a][2]
                            else (inner_row[a][0], inner_row[a][1]))

                # Run's first surviving station (square cap).
                p, a0 = _endpoint(0)
                _emit_inner(p, a0)
                for a in range(1, m2):
                    if inner_row[a][2] == inner_row[a - 1][2]:
                        continue    # no flip — interior redundant station
                    # WELD TRANSITION.  The flip point IS a pavement
                    # corner: take the single EXACT pavement vertex
                    # nearest it (within one station spacing) and drop
                    # the two bracketing stations — no minted edge node.
                    (x0, y0), _al0, _w0 = inner_row[a - 1]
                    (x1, y1), _al1, _w1 = inner_row[a]
                    snap = (pav_vertex_at(0.5 * (x0 + x1), 0.5 * (y0 + y1))
                            if pav_vertex_at is not None else None)
                    if snap is not None:
                        # The corner rides the pavement bracket's value
                        # (recomputed analytically at emission anyway).
                        alt = (inner_row[a - 1][1] if inner_row[a - 1][2]
                               else inner_row[a][1])
                        _emit_inner(snap, alt)
                    else:
                        # No pavement vertex in reach — keep BOTH
                        # bracketing stations (reported below).
                        corner_fallbacks += 1
                        b0 = _endpoint(a - 1)
                        _emit_inner(b0[0], b0[1])
                        b1 = _endpoint(a)
                        _emit_inner(b1[0], b1[1])
                # Run's last surviving station (square cap).
                p, aL = _endpoint(m2 - 1)
                _emit_inner(p, aL)
                if len(inner_pts) < 2:
                    continue
            else:
                inner_pts = [p for p, _a, _w in inner_row]
                inner_alts = [a for _p, a, _w in inner_row]
            ring = inner_pts + outer_pts[::-1]
            alts = inner_alts + outer_alts[::-1]
            out.append((ring, alts))
    if corner_fallbacks:
        UI.lvprint(1, "  [skirt] weld-transition exact-vertex lookup "
                   f"missed {corner_fallbacks} time(s); kept bracketing "
                   "stations (mid-edge weld nodes) there.")
    return out


# ──────────────────────────────────────────────────────────────────
# Runway-end (RESA) edge detection
# ──────────────────────────────────────────────────────────────────
def _runway_end_edges(runway_shapes):
    """Return the two true extremities of each runway designation as
    ``(shape, end_a, end_b, full_len)``.

    FALLBACK detector — used only when the authoritative apt.dat row-100
    runway list is unavailable (see ``emit_runway_end_skirts``'s
    ``source_runways``).  A runway is usually split into many segments
    (crossings, FAA profile redistribution, tile cuts), so an internal-seam
    test is fragile.  Instead we collect every segment's two short edges per
    ref and pick the PAIR of short-edge midpoints that are FARTHEST apart:
    those are the runway's two thresholds; everything between them is
    interior.  ``full_len`` is that farthest-pair distance (the whole runway
    length), used for the ICAO code number.
    """
    by_ref: dict[str, list] = defaultdict(list)
    for s in runway_shapes:
        coords = _open_coords(s.polygon)
        info = _rect_long_short_edges(coords)
        if info is None:
            continue
        long_edges, _short_len, _long_len = info
        long_set = set()
        for (a, b) in long_edges:
            long_set.add((a, b))
            long_set.add((b, a))
        for i in range(4):
            a = coords[i]
            b = coords[(i + 1) % 4]
            if (a, b) in long_set:
                continue
            mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))
            by_ref[s.ref].append((s, a, b, mid))

    ends = []
    for ref, ses in by_ref.items():
        if len(ses) <= 2:
            # Single segment: both short edges are thresholds.
            full = (math.hypot(ses[0][3][0] - ses[1][3][0],
                               ses[0][3][1] - ses[1][3][1])
                    if len(ses) == 2 else 0.0)
            for s, a, b, _mid in ses:
                ends.append((s, a, b, full))
            continue
        # Farthest-apart short-edge midpoints = the two thresholds.
        best = (-1.0, 0, 1)
        for i in range(len(ses)):
            for j in range(i + 1, len(ses)):
                d = math.hypot(ses[i][3][0] - ses[j][3][0],
                               ses[i][3][1] - ses[j][3][1])
                if d > best[0]:
                    best = (d, i, j)
        full = best[0]
        for k in (best[1], best[2]):
            s, a, b, _mid = ses[k]
            ends.append((s, a, b, full))
    return ends


def _pavement_exit_along(prep_pav, mx, my, dx, dy, max_d, step) -> float:
    """Distance from ``(mx, my)`` (a point ON pavement) along unit
    ``(dx, dy)`` to where the ray leaves the pavement union — i.e. the
    OUTER pavement edge (a blast-pad / stopway / apron end).  ``0.0`` if
    the start isn't on pavement; ``max_d`` if it never exits."""
    if prep_pav is None or not prep_pav.contains(Point(mx, my)):
        return 0.0
    d = step
    while d <= max_d:
        if not prep_pav.contains(Point(mx + dx * d, my + dy * d)):
            return d - 0.5 * step
        d += step
    return max_d


def _edge_interp_alt(shape, x, y) -> float | None:
    """Pavement-surface altitude near ``(x, y)``, interpolated the way
    Triangle4XP renders it: linearly along the boundary EDGE between the two
    endpoint node altitudes.

    For a ``node_altitudes`` shape (apron / junction / tile-cut piece),
    ``_sample_runway_segment_elev`` returns the NEAREST-NODE value — a
    piecewise-constant Voronoi field that STEPS at cell boundaries.  When the
    clearance shadow samples a pavement edge that way, a point near the edge
    can pick up a distant node's altitude (a 2 m phantom step the apron never
    renders).  Projecting to the nearest boundary edge and interpolating its
    endpoint altitudes mirrors the rendered surface, so the shadow stays
    smooth.  Flat / ``altitude_high``-``low`` shapes fall through to the
    existing sampler (no node_altitudes to interpolate)."""
    na = shape.node_altitudes
    if not na or shape.polygon is None:
        return _sample_runway_segment_elev(shape, x, y)
    try:
        coords = list(shape.polygon.exterior.coords)
    except _GEOM_EXC:
        return _sample_runway_segment_elev(shape, x, y)
    n = min(len(coords), len(na))
    if n < 2:
        return _sample_runway_segment_elev(shape, x, y)
    best_d2 = float("inf")
    best: float | None = None
    for i in range(n - 1):
        sx, sy = coords[i]
        tx, ty = coords[i + 1]
        dx, dy = tx - sx, ty - sy
        seg2 = dx * dx + dy * dy
        if seg2 < 1e-9:
            continue
        t = max(0.0, min(1.0, ((x - sx) * dx + (y - sy) * dy) / seg2))
        px, py = sx + t * dx, sy + t * dy
        d2 = (x - px) ** 2 + (y - py) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best = na[i] + t * (na[i + 1] - na[i])
    return best if best is not None else _sample_runway_segment_elev(shape, x, y)


def _nearest_pav_alt(pav_shapes, x, y,
                     max_distance_m: float = 5.0) -> float | None:
    """Pavement altitude at ``(x, y)`` via the NEAREST shape's
    edge-interpolated read — containment-free.  ``_pav_alt`` requires a
    shape to CONTAIN the point, so a hairline inter-shape gap (or a
    decimated ring grazing the sample) flips the read to ``None`` and a
    caller's fallback silently changes the answer — the Pass D skirt and
    its ``verification`` reader measure the runway END GRADE from two
    such samples and MUST agree (a lost sample flattened the validator's
    entry grade at KCLT 18L and phantom-flagged a lawful skirt).  Points
    farther than ``max_distance_m`` from any pavement return ``None``."""
    pt = Point(x, y)
    best, best_distance = None, max_distance_m
    for s in pav_shapes:
        try:
            d = s.polygon.distance(pt)
        except _GEOM_EXC:
            continue
        if d < best_distance or (best is None and d <= best_distance):
            best_distance, best = d, s
    if best is None:
        return None
    return _edge_interp_alt(best, x, y)


def _pav_alt(pav_shapes, x, y) -> float | None:
    """Altitude of the airside pavement at ``(x, y)`` — the shape
    containing the point, edge-interpolated (see :func:`_edge_interp_alt`)
    so a ``node_altitudes`` apron/junction is shadowed at its RENDERED
    altitude, not a stepped nearest-node sample."""
    pt = Point(x, y)
    for s in pav_shapes:
        try:
            if s.polygon.contains(pt):
                e = _edge_interp_alt(s, x, y)
                if e is not None:
                    return e
        except _GEOM_EXC:
            continue
    return None


_SKIRT_ROAD_SHOULDER_M = 1.0
# OSM railway ways carry no carriageway-width class; a single-track
# corridor with ballast shoulders.
_SKIRT_RAILWAY_CORRIDOR_M = 8.0


def _surface_road_corridors(layout, ll_to_m):
    """Union of SURFACE road / railway corridors near the airport, in
    the layout meter frame — the ground the runway-end skirt must not
    fill over.  One source for the Pass D emitter AND the
    ``verification`` reader (the validator exempts the same corridors
    the emitter leaves unfilled, or every road through a governed zone
    reads as a violation).

    Tunnel-tagged ways are EXCLUDED on purpose: filling over a tunnel
    is lawful and correct (the tunnel emitter owns its portals and
    trenches, and those shapes are already in ``layout.shapes``, which
    the skirt's static clip respects).  Returns ``None`` when the tile
    has no road caches or nothing is near.

    Memoized on the layout (``_surface_road_corridors_cache``): the
    road caches and the anchor projection every caller passes as
    ``ll_to_m`` are fixed for the layout's lifetime, so the first
    caller's union serves the lateral-cut, skirt, and verification
    passes alike.
    """
    cached = getattr(layout, "_surface_road_corridors_cache", None)
    if cached is not None:
        return cached[0]
    result = _surface_road_corridors_uncached(layout, ll_to_m)
    layout._surface_road_corridors_cache = (result,)
    return result


def _surface_road_corridors_uncached(layout, ll_to_m):
    try:
        from .bridges import _load_tunnel_road_network
        nodes_r, ways_r, _big_way_ids, _node_tags_r = (
            _load_tunnel_road_network(layout))
    except _GEOM_EXC:
        return None
    if not ways_r:
        return None
    return road_corridors_from_ways(nodes_r, ways_r, ll_to_m)


def road_corridors_from_ways(nodes, ways, ll_to_m, widths=None):
    """THE corridor-union law, applied to any road/rail way set.

    A surface way becomes ``LineString.buffer(½·carriageway width +
    _SKIRT_ROAD_SHOULDER_M)``; tunnel-tagged ways are EXCLUDED (filling
    over a tunnel is lawful — see :func:`_surface_road_corridors`);
    railways use the fixed ``_SKIRT_RAILWAY_CORRIDOR_M`` corridor.
    Returns the union, or ``None`` when nothing qualified.

    Factored out of :func:`_surface_road_corridors_uncached` (pure
    refactor — that path passes exactly the ways it always did, so its
    result is unchanged) so the airport-region ROAD FEED can build its
    corridors under the SAME law rather than a second copy of it.  One
    buffer rule, three future consumers.

    ``nodes`` maps id → ``(lat, lon)``; ``ways`` is
    ``[(id, [node id, ...], tags)]``; ``widths``, when given (the feed
    resolves them once), supplies the per-way carriageway width instead
    of re-deriving it from the tags."""
    from .bridges import _carriageway_width_from_tags
    corridors = []
    for way_id, node_refs, tags in ways:
        highway_type = tags.get("highway")
        railway_type = tags.get("railway")
        if highway_type is None and railway_type is None:
            continue
        tunnel_tag = tags.get("tunnel", "no")
        if tunnel_tag not in ("", "no"):
            continue
        points = []
        for node_ref in node_refs:
            ll = nodes.get(node_ref)
            if ll is not None:
                points.append(ll_to_m(ll[0], ll[1]))
        if len(points) < 2:
            continue
        width = None if widths is None else widths.get(way_id)
        if width is None:
            if railway_type is not None:
                width = _SKIRT_RAILWAY_CORRIDOR_M
            else:
                width = _carriageway_width_from_tags(
                    highway_type, tags, 6.0)
        try:
            corridors.append(
                LineString(points).buffer(
                    0.5 * width + _SKIRT_ROAD_SHOULDER_M))
        except _GEOM_EXC:
            continue
    if not corridors:
        return None
    try:
        return unary_union(corridors)
    except _GEOM_EXC:
        return None


def airport_road_feed_corridors(layout, ll_to_m):
    """Corridor union of the AIRPORT-REGION ROAD FEED
    (``layout.airport_road_network``), in the layout's meter frame —
    ``None`` when the feed is off or empty.

    The feed's counterpart to :func:`_surface_road_corridors`, memoized
    the same way (``layout._airport_road_feed_corridors_cache``, 1-tuple
    so a computed ``None`` also caches) and built under the same law via
    :func:`road_corridors_from_ways`.

    DELIBERATELY SEPARATE from :func:`_surface_road_corridors`, which
    keeps reading the TILE caches: at default config those hold no minor
    roads at all, so serving clearance from the feed would widen the
    corridor exemption at every airport in the world — a behaviour change
    for the owner features to make explicitly.  Classification refinement
    and inset road grading call THIS one."""
    cached = getattr(layout, "_airport_road_feed_corridors_cache", None)
    if cached is not None:
        return cached[0]
    network = getattr(layout, "airport_road_network", None)
    result = None
    if network is not None and getattr(network, "ways", None):
        result = road_corridors_from_ways(
            network.nodes, network.ways, ll_to_m,
            widths=getattr(network, "widths", None))
    layout._airport_road_feed_corridors_cache = (result,)
    return result


# Emitted-shape roles that mark a runway end as constrained the same
# way a mapped road does (the perimeter road may reach the layout as a
# service_road / groundside shape rather than an OSM way).
_SKIRT_CONSTRAINT_ROLES = frozenset({
    "service_road", "service_junction", "groundside_pavement",
    "tunnel_ramp",
})


def _end_constraint_block(layout, ll_to_m):
    """Geometry whose presence in a runway end zone marks the end as
    NON-STANDARD (EMAS inference, user ruling 2026-07-05): surface
    road / railway corridors (big + small OSM caches — service roads
    included), OSM WATER polygons, and emitted road-like infrastructure
    shapes.  One source for the Pass D emitter AND the ``verification``
    reader.  ``None`` when nothing is available."""
    parts = []
    road_block = _surface_road_corridors(layout, ll_to_m)
    if road_block is not None and not road_block.is_empty:
        parts.append(road_block)
    # OSM water polygons (closed natural=water / riverbank ways from
    # the tile ``water`` cache; multipolygon relations are not carried
    # by the layer loader — acceptable, the primary constraint class is
    # the pond/river beside the overrun).
    try:
        from .osm_load import _load_osm_road_layer
        nodes_w, ways_w, _node_tags_w = _load_osm_road_layer(
            "water", layout.anchor[0], layout.anchor[1])
    except _GEOM_EXC:
        nodes_w, ways_w = {}, []
    for _wid, node_refs, _tags in ways_w:
        if len(node_refs) < 4 or node_refs[0] != node_refs[-1]:
            continue
        points = []
        for node_ref in node_refs[:-1]:
            ll = nodes_w.get(node_ref)
            if ll is not None:
                points.append(ll_to_m(ll[0], ll[1]))
        if len(points) < 3:
            continue
        try:
            poly = Polygon(points)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if not poly.is_empty:
                parts.append(poly)
        except _GEOM_EXC:
            continue
    for s in layout.shapes:
        if (s.role in _SKIRT_CONSTRAINT_ROLES
                and s.polygon is not None and not s.polygon.is_empty):
            parts.append(s.polygon)
    if not parts:
        return None
    try:
        return unary_union(parts)
    except _GEOM_EXC:
        return None


def _end_constraint_distance(p0, outward, max_distance_m,
                             constraint_block) -> float | None:
    """Distance from the pavement exit ``p0`` along ``outward`` to the
    FIRST constraint crossing of the extended centerline, or ``None``
    when nothing constrains within ``max_distance_m``."""
    if constraint_block is None or constraint_block.is_empty:
        return None
    nx, ny = outward
    try:
        ray = LineString([
            (p0[0], p0[1]),
            (p0[0] + nx * max_distance_m, p0[1] + ny * max_distance_m)])
        crossing = ray.intersection(constraint_block)
    except _GEOM_EXC:
        return None
    if crossing.is_empty:
        return None
    nearest = None
    geoms = (list(crossing.geoms)
             if hasattr(crossing, "geoms") else [crossing])
    for geom in geoms:
        for x, y in getattr(geom, "coords", []):
            t = (x - p0[0]) * nx + (y - p0[1]) * ny
            if t >= 0.0 and (nearest is None or t < nearest):
                nearest = t
    return nearest


def _trim_groundside_pavement_around_skirts(
        layout: PavementLayout, skirt_union) -> tuple[int, int]:
    """Trim every ``groundside_pavement`` shape around the emitted
    runway-end-skirt footprint union (skirt airside precedence, Noah
    ruling 2026-07-10).

    The runway-end skirt area is inherently AIRSIDE: the skirt keeps its
    full footprint (it is NOT clipped against groundside — groundside was
    excluded from the skirt clip block), and GROUNDSIDE yields, trimmed
    exactly around the skirt.  For each groundside shape overlapping
    ``skirt_union`` the new outline is ``polygon.difference(skirt_union)``
    — shapely inserts the skirt's boundary coordinates VERBATIM into the
    groundside ring (shared-edge guarantee), so the trimmed groundside
    welds to the skirt chain with zero minted near-parallel geometry and
    no unowned DEM sliver between them.  Per-vertex altitudes are
    re-derived through ``_resample_node_altitudes_nn`` — the same
    edge-interpolation resample every other groundside clip uses
    (``tile_cut``, ``boundary``) — so the remnant keeps groundside's own
    DEM-following field.  A remnant part below ``_GROUNDSIDE_TRIM_MIN_M2``
    (or an emptied shape) is dropped WHOLE.

    Mutates ``layout.shapes`` in place.  Returns
    ``(n_shapes_trimmed, n_shapes_dropped)``.
    """
    import dataclasses
    if skirt_union is None or skirt_union.is_empty:
        return (0, 0)
    groundside_shapes = [s for s in layout.shapes
                         if s.role == "groundside_pavement"
                         and s.polygon is not None
                         and not s.polygon.is_empty]
    if not groundside_shapes:
        return (0, 0)
    n_trimmed = 0
    n_dropped = 0
    removed_ids: set[int] = set()
    new_shapes: list[BuiltShape] = []
    for gs in groundside_shapes:
        try:
            if gs.polygon.intersection(skirt_union).area <= 1e-6:
                continue
            trimmed = gs.polygon.difference(skirt_union)
        except _GEOM_EXC:
            continue
        removed_ids.add(id(gs))
        old_coords = list(gs.polygon.exterior.coords)
        old_open = (old_coords[:-1]
                    if (old_coords and old_coords[0] == old_coords[-1])
                    else old_coords)
        if trimmed.is_empty:
            n_dropped += 1
            continue
        if trimmed.geom_type == "Polygon":
            parts = [trimmed]
        elif trimmed.geom_type in ("MultiPolygon", "GeometryCollection"):
            parts = [g for g in trimmed.geoms
                     if g.geom_type == "Polygon" and not g.is_empty]
        else:
            parts = []
        kept_any = False
        for part in parts:
            if part.area < _GROUNDSIDE_TRIM_MIN_M2:
                continue   # sub-50 m² remnant → drop whole
            new_alts = None
            if gs.node_altitudes:
                new_alts = _resample_node_altitudes_nn(
                    part, old_open, gs.node_altitudes)
            new_shapes.append(dataclasses.replace(
                gs, polygon=part, node_altitudes=new_alts))
            kept_any = True
        if kept_any:
            n_trimmed += 1
        else:
            n_dropped += 1
    if removed_ids:
        layout.shapes[:] = [s for s in layout.shapes
                            if id(s) not in removed_ids]
        layout.shapes.extend(new_shapes)
    return (n_trimmed, n_dropped)


def emit_runway_end_skirts(layout: PavementLayout, dem,
                           tile_lat: int, tile_lon: int,
                           source_runways=None) -> int:
    """Emit the runway-end down-slope skirts (gate ``O4_RUNWAY_END_SKIRT``).
    Mutates ``layout.shapes``; returns the number of skirt shapes emitted.

    The exact mirror of the Pass C RESA cut: where Pass C cuts terrain
    that RISES above the 5 % up-ramp, the skirt fills terrain that DROPS
    away beyond the end, so a runway ending at a hillside brow meets a
    lawful ≤3 %/≤5 % descent instead of a cliff at the pavement edge
    (FAA AC 150/5300-13B §3.16.5 / ICAO Annex 14 §4.7 — the law lives in
    ``grade_law``; plan: docs/runway_end_skirt_plan.md).

    Called once ``final_grade_projection`` has settled the pavement
    profile:
    the skirt bakes the law floor from the pavement-end elevation and
    entry grade, and the final projection may move pad/junction
    altitudes at a blast-pad end AFTER the cuts are emitted (KCLT 18L
    rose 0.4 m, leaving an emit-time skirt too short under the settled
    floor).  Emitting here also means the static clip below sees every
    earlier shape — cuts, boundary ribbon, groundside, tunnels.

    The skirt is emitted as ABUTTING BANDS split at the law's grade
    breakpoints: the floor is piecewise quadratic and a two-row
    ``node_altitudes`` ring renders as a ruled chord that would sag
    metres below it mid-span; per-band the sagitta is ≤ rate·L²/8
    (≈ 0.31 m).  Bands are clipped against the static geometry and
    previously-emitted skirt pieces (crossing-runway ends; first wins),
    with per-vertex altitudes recomputed ANALYTICALLY from the outward
    projection so clipping can introduce vertices freely.
    """
    if not RUNWAY_END_SKIRT_ENABLED or dem is None:
        return 0
    lat0, lon0 = layout.anchor
    cos0 = math.cos(math.radians(lat0))
    R = R_EARTH
    step = CLEARANCE_STATION_STEP_M
    trigger = CLEARANCE_OBSTRUCTION_THRESHOLD_M["runway"]

    def _ll_to_m(lat: float, lon: float) -> tuple[float, float]:
        return (math.radians(lon - lon0) * R * cos0,
                math.radians(lat - lat0) * R)

    def sample_dem(x: float, y: float) -> float | None:
        try:
            lat = lat0 + math.degrees(y / R)
            lon = lon0 + math.degrees(x / (R * cos0))
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except _GEOM_EXC:
            return None

    airside = [s for s in layout.shapes
               if s.role in _AIRSIDE_PAVEMENT_ROLES
               and s.polygon is not None and not s.polygon.is_empty]
    if not airside:
        return 0
    try:
        pav_union = unary_union([s.polygon for s in airside])
        prep_pav = prep(pav_union)
    except _GEOM_EXC:
        return 0

    def _pav_weld_at(vx: float, vy: float) -> bool:
        # The pavement-proximity half of ``_end_alt_at``'s weld predicate
        # (its axial ``d <= 0.02`` half is satisfied by construction for
        # every inner-row point — those lie in the p0-perpendicular plane
        # at d = 0 on the end strip, and on the pavement exit edge at
        # d = 0 on the flanks — so only the on-pavement test drives the
        # weld transition that thins the inner row).
        return pav_union.distance(Point(vx, vy)) <= 0.05

    # Existing pavement ring vertices (verbatim coordinates).  A grading
    # shape must never MINT a node on a pavement edge (user ruling
    # 2026-07-09): where the skirt's inner weld row touches pavement it
    # snaps to the nearest EXISTING vertex within one station spacing.
    def _iter_ring_xy(geom):
        gt = geom.geom_type
        if gt == "Polygon":
            yield from geom.exterior.coords
            for r in geom.interiors:
                yield from r.coords
        elif gt in ("MultiPolygon", "GeometryCollection"):
            for g in geom.geoms:
                yield from _iter_ring_xy(g)

    _pav_vx = np.array(
        [(float(x), float(y)) for s in airside
         for x, y in _iter_ring_xy(s.polygon)], dtype=float)

    def _pav_vertex_at(vx: float, vy: float):
        if _pav_vx.size == 0:
            return None
        d2 = ((_pav_vx[:, 0] - vx) ** 2 + (_pav_vx[:, 1] - vy) ** 2)
        j = int(np.argmin(d2))
        if d2[j] <= step * step:
            return (float(_pav_vx[j, 0]), float(_pav_vx[j, 1]))
        return None

    def _nearest_pav_vertex(vx: float, vy: float):
        """The nearest airside pavement RING VERTEX, unbounded (arc R
        slice R1).  ``_pav_vertex_at`` above is the WELD snap and is
        deliberately capped at one station spacing; the RESA cut's
        solver ANCHOR is a different object — the graph node whose
        solved value tracks the pavement-exit elevation the envelope is
        referenced to — and at a plain runway end the nearest ring
        vertex is an end corner half a runway width away.  Frozen at
        construction time (the B2/B3 frozen-nearest coupling pattern)."""
        if _pav_vx.size == 0:
            return None
        d2 = ((_pav_vx[:, 0] - vx) ** 2 + (_pav_vx[:, 1] - vy) ** 2)
        j = int(np.argmin(d2))
        return (float(_pav_vx[j, 0]), float(_pav_vx[j, 1]))
    # Every existing shape (pavement, cuts, ribbon, buildings, tunnels, …),
    # clipped EXACTLY (weld ruling 2026-07-09): the skirt WELDS to the
    # pavement it fills off — the former 1 m standoff left a groove of
    # raw DEM that rendered as a knife-edge wall/trench at the runway
    # end (the worst CYXY cliffs, 11.9 m, were pavement↔skirt grooves).
    #
    # SKIRT AIRSIDE PRECEDENCE (Noah ruling 2026-07-10): the runway-end
    # skirt area is inherently AIRSIDE — nothing there can legitimately be
    # groundside.  The skirt must NEVER clip its footprint against
    # groundside pavement; where the two approach, GROUNDSIDE is trimmed
    # AROUND the skirt (exact footprint, shared chain verbatim, no buffer
    # gap — see the groundside trim pass after emission).  So groundside
    # pavement is EXCLUDED from the clip block here.  Buildings STAY in the
    # block (they are value authorities; skirt-vs-building precedence is
    # unchanged, per the ruling).
    groundside_shapes = [s for s in layout.shapes
                         if s.role == "groundside_pavement"
                         and s.polygon is not None
                         and not s.polygon.is_empty]
    _gs_ids = {id(s) for s in groundside_shapes}
    static_block = None
    try:
        static_block = unary_union(
            [s.polygon for s in layout.shapes
             if s.polygon is not None and not s.polygon.is_empty
             and id(s) not in _gs_ids])
    except _GEOM_EXC:
        static_block = None
    # ATTACHMENT reference for the small-fragment keep test below.  It
    # still counts groundside: a skirt corner-wedge resting ON groundside
    # is a legitimate attached fragment (airside precedence), not the
    # freestanding confetti the min-area gate rejects.  Keeping groundside
    # here preserves the pre-ruling attachment behaviour verbatim.
    attach_block = static_block
    if groundside_shapes:
        try:
            _gs_union = unary_union([s.polygon for s in groundside_shapes])
            attach_block = (_gs_union if static_block is None
                            else unary_union([static_block, _gs_union]))
        except _GEOM_EXC:
            attach_block = static_block

    # FRESH TRACE (O4_SKIRT_GS_TRACE=1, read-only): measure how much
    # groundside pavement the CURRENT (backwards) clip removes from the
    # skirt footprint, per raw strip and in total.  Pure reporting — does
    # not touch geometry — so it is byte-inert.
    _gs_trace = os.environ.get("O4_SKIRT_GS_TRACE") == "1"
    _gs_union_trace = None
    if _gs_trace:
        try:
            _gs_union_trace = unary_union(
                [s.polygon for s in layout.shapes
                 if s.role == "groundside_pavement"
                 and s.polygon is not None and not s.polygon.is_empty])
        except _GEOM_EXC:
            _gs_union_trace = None
    _gs_fire_area = 0.0
    _gs_fire_strips = 0

    # Each collected strip carries its own analytic altitude function
    # (``alt_at(x, y)``), so clipping in the finalize below can
    # introduce vertices freely: END strips descend from one reference
    # along the outward axis; FLANK strips (alongside the blast pad /
    # stopway between the runway end and the pavement exit) descend
    # from a per-station pavement-EDGE altitude along the side normal.
    # Constraint geometry for the EMAS inference (roads / water /
    # emitted road-like infrastructure) — built once, shared by every
    # end (and identically by the verification reader).
    constraint_block = _end_constraint_block(layout, _ll_to_m)

    skirt_strips: list[tuple] = []
    # RESA CUT twin (arc A2, gate ``RUNWAY_END_RESA_ENABLED``).  The cut
    # rides in the SAME per-end collection as the fill — same apt.dat
    # row-100 anchor, same ``_pavement_exit_along`` march, same corridor
    # half-width, same weld discipline — and is emitted in its own pass
    # below (after the fill, so it can be clipped against the fill's
    # settled footprint).  Empty with the gate OFF.
    resa_strips: list[tuple] = []
    resa_reach = CLEARANCE_MAX_REACH_M["runway"]
    # ── RESA CUT SOLVER ADMISSION (arc R slice R1, gate
    # ``ONE_SOLVE_TERRAIN_RUNWAY_END_RESA``) ─────────────────────────
    # The owner ruling: the runway-end envelope is LAW THE SOLVER
    # ENFORCES, not geometry stamped after the fact.  The cut's anchor is
    # the pavement-EXIT elevation, and that read MOVES after this
    # pre-solve emission slot (measured at CYXY: median 0.110 m, p90
    # 0.150 m, max 0.164 m over 106 numeric anchor reads, 88 of them over
    # 0.05 m; the mode is the CROWN, which writeback applies as
    # z = z' − c).  So the analytic stamp below bakes a STALE reference.
    #
    # Under the gate this emitter additionally publishes a per-END SPEC
    # (anchor point, outward axis, corridor half-width, reach, and the
    # floor-law arguments) on ``layout.runway_end_resa_presolve``.  The
    # solver reads it to (a) give every admitted cut vertex ONE ONE-SIDED
    # envelope interval edge to the end's frozen-nearest pavement anchor
    # NODE and (b) re-evaluate the one-slab projection at writeback
    # against the SOLVED, CROWNED exit reference.  Gate OFF: no store, no
    # admission, and ``_resa_alt_at`` below remains the sole valuation —
    # byte-identical.
    _resa_solver_admitted = False
    if RUNWAY_END_RESA_ENABLED:
        from .elevation_per_surface.solver_primitives import (
            admitted_terrain_refs as _admitted_refs_fn)
        _resa_solver_admitted = (
            (ROLE_RUNWAY_CLEARANCE, REF_RUNWAY_END_RESA)
            in _admitted_refs_fn())
    resa_end_specs: list[dict] = []

    # ── END-AROUND TAXIWAY (EAT) CEILING per-end spec (owner ruling
    # 2026-07-27, gate ``EAT_SURFACE_CEILING_ENABLED``) ───────────────
    # Published beside the RESA store below.  Unlike the RESA spec this
    # one is anchored at the ROW-100 RUNWAY END, not at the pavement
    # exit: FAA AC 150/5300-13B §4.12 / Order 8260.3 start the departure
    # surface AT the departure end of runway, and CS-ADR-DSN J.480(e)
    # measures its 60 m setback from the runway end too.  It is also
    # published independently of whether this end produced a RESA cut —
    # an end-around taxiway exists (or not) regardless of the overrun
    # earthworks.
    from .config import EAT_SURFACE_CEILING_ENABLED as _eat_gate
    eat_end_specs: list[dict] = []
    _eat_slope, _eat_setback = eat_surface_slope_and_setback(
        getattr(layout, "icao", None))

    def _collect_eat_end(end_pt, outward, runway_width, full_len):
        """One EAT-ceiling record for one runway end.

        ``anchor_xy`` is the FROZEN-NEAREST airside pavement ring vertex
        to the row-100 endpoint (the same coupling pattern the RESA cut
        uses): the runway-end ELEVATION the ceiling is referenced to must
        be the end's SOLVED profile value, so the solver reads it off
        that node rather than off the DEM.
        """
        if not _eat_gate:
            return
        anchor = _nearest_pav_vertex(end_pt[0], end_pt[1])
        if anchor is None:
            return
        letter = runway_code_letter(runway_width)
        eat_end_specs.append({
            "p0": (float(end_pt[0]), float(end_pt[1])),
            "outward": (float(outward[0]), float(outward[1])),
            "code_letter": letter,
            "code_number": int(runway_code_number(full_len)),
            "slope": float(_eat_slope),
            "setback_m": float(_eat_setback),
            "tail_height_m": float(TAIL_HEIGHT_BY_CODE_LETTER[letter]),
            "anchor_xy": (float(anchor[0]), float(anchor[1])),
        })

    def _floor_depth_for(entry_grade: float,
                         pavement_beyond_end_m: float = 0.0):
        depth_cache: dict[float, float] = {}

        def _floor_depth(distance_m: float) -> float:
            depth = depth_cache.get(distance_m)
            if depth is None:
                depth = runway_end_skirt_floor_profile_beyond_pavement(
                    [distance_m], entry_grade, pavement_beyond_end_m)[0]
                depth_cache[distance_m] = depth
            return depth
        return _floor_depth

    def _emit_one_end(outward, runway_width, full_len, seed,
                      elev_fallback, approach_class):
        """Collect the down-slope skirt bands off one runway end.  Same
        anchor geometry as Pass C's ``_emit_resa``; the governed length
        scales with the end's approach class (better approaches earn a
        longer smoothed apron of terrain)."""
        nx, ny = outward
        start = _pavement_exit_along(prep_pav, seed[0], seed[1], nx, ny,
                                     _RESA_PAVEMENT_PROBE_MAX_M, step)
        p0 = (seed[0] + nx * start, seed[1] + ny * start)
        # Containment-free reads (``_nearest_pav_alt``): the skirt's law
        # floor and the verification reader MUST measure the same end
        # elevation and entry grade — a containment miss on a hairline
        # gap would silently flatten one side's entry grade.
        ref = _nearest_pav_alt(airside, p0[0] - nx * 1.0, p0[1] - ny * 1.0)
        if ref is None and elev_fallback is not None:
            ref = elev_fallback()
        if ref is None:
            return
        # The runway's own end grade (signed, positive = climbing toward
        # the end), sampled over a short window inside the pavement.
        inside = _nearest_pav_alt(
            airside,
            p0[0] - nx * (1.0 + _SKIRT_END_GRADE_WINDOW_M),
            p0[1] - ny * (1.0 + _SKIRT_END_GRADE_WINDOW_M))
        entry_grade = 0.0
        if inside is not None:
            entry_grade = (float(ref) - float(inside)) \
                / _SKIRT_END_GRADE_WINDOW_M
            entry_grade = max(-0.05, min(0.05, entry_grade))
        # The governed footprint is anchored at the RUNWAY END (FAA: the
        # safety area is measured from the end, blast pad / stopway
        # INSIDE it), so the overrun pavement between the end and the
        # exit consumes its first ``pavement_beyond_end`` metres and the
        # floor profile arrives at the exit already that far into its
        # descent (user 2026-07-09: skirts ran ~70 m long — the pad
        # length — at HECA/KCLT when the full length restarted at the
        # exit).
        pavement_beyond_end = max(0.0, start - _RESA_SEED_INSET_M)
        governed = runway_end_governed_length_beyond_pavement_m(
            runway_end_governed_length_m(full_len, approach_class),
            pavement_beyond_end)
        # EMAS inference (user 2026-07-05): a road / service road /
        # water crossing the end zone marks a NON-standard end — the
        # skirt stops short of the first constraint (or vanishes when
        # the constraint sits at the pavement end, KCLT 18L).
        governed = runway_end_constrained_length_m(
            governed,
            _end_constraint_distance(
                p0, outward, governed, constraint_block))
        _floor_depth = _floor_depth_for(entry_grade, pavement_beyond_end)

        # The governed END corridor half-width — ICAO Annex 14 §3.5.3's
        # "twice the runway width" expressed as a half-width, single-sourced
        # in ``grade_law`` so the fill, the RESA cut and the verification
        # reader cannot drift.  Numerically identical to the inline
        # ``max(runway_width, runway_strip_half_width_m(full_len))`` it
        # replaces.
        half = runway_end_corridor_half_width_m(runway_width, full_len)
        perp = (-ny, nx)
        ea = (p0[0] - perp[0] * half, p0[1] - perp[1] * half)
        eb = (p0[0] + perp[0] * half, p0[1] + perp[1] * half)
        stations = _stations(ea, eb, step)
        m = len(stations)
        band_edges = runway_end_skirt_profile_breakpoints_beyond_pavement(
            entry_grade, pavement_beyond_end)

        # PER-STATION LATERAL REFERENCE across the exit row (KCLT skirt
        # #845, 2026-07-26): where the abutting pavement varies
        # laterally across the runway end, a floor anchored to the
        # single centre-line ``ref`` steps against the weld row at every
        # weld/no-weld transition (KCLT junction #313 at 226.40 m under
        # the weld vs ref 227.1 m ⇒ 0.70 m over 7 m).  Each station that
        # touches pavement (the weld predicate) takes the SAME
        # containment-free read the weld row carries at that station, so
        # the floor and the weld agree wherever they meet;
        # ``_fill_lateral_refs`` densifies the profile (gap lerp, end
        # hold, scalar fallback — see its docstring for the
        # foreign-value and pavement-wall guards).
        row_spacing = ((2.0 * half) / (m - 1)) if m > 1 else 1.0
        raw_refs: list = []
        for (sx, sy) in stations:
            v = None
            if pav_union.distance(Point(sx, sy)) <= 0.05:
                v = _nearest_pav_alt(airside, sx - nx * 1.0, sy - ny * 1.0)
            raw_refs.append(None if v is None else float(v))
        row_refs = _fill_lateral_refs(raw_refs, float(ref), row_spacing)

        def _end_alt_at(vx, vy, p0=p0, nx=nx, ny=ny, ea=ea, perp=perp,
                        row_refs=row_refs, row_spacing=row_spacing,
                        floor_depth=_floor_depth,
                        cap=governed, sample_dem=sample_dem):
            d = (vx - p0[0]) * nx + (vy - p0[1]) * ny
            if d <= 0.02 and pav_union.distance(Point(vx, vy)) <= 0.05:
                # WELD ROW (user ruling 2026-07-09): a vertex ON the
                # pavement exit edge carries the LOCAL pavement edge
                # value verbatim (containment-free read 1 m inside, the
                # shared reader) — never lifted onto the DEM, so the
                # skirt abuts the pavement with zero step.  ONLY where
                # the vertex actually touches pavement: the inner row
                # spans the full strip half-width, and its off-pavement
                # stretch keeps the row-profile floor (never a nearest-
                # pavement read of its own — a FOREIGN shape's value,
                # the 63 % skirt-edge spikes of the first weld round).
                pav = _nearest_pav_alt(
                    airside, vx - nx * 1.0, vy - ny * 1.0)
                if pav is not None:
                    return float(pav)
            # Lateral position on the exit row → the local reference
            # (piecewise-linear between stations; exact at stations, so
            # this closure and _build_filled_skirts' ring altitudes
            # agree wherever both evaluate).
            if len(row_refs) > 1:
                u = ((vx - ea[0]) * perp[0]
                     + (vy - ea[1]) * perp[1]) / row_spacing
                u = max(0.0, min(float(len(row_refs) - 1), u))
                j = min(int(u), len(row_refs) - 2)
                ref_t = row_refs[j] + (row_refs[j + 1] - row_refs[j]) \
                    * (u - j)
            else:
                ref_t = row_refs[0]
            floor = ref_t - floor_depth(max(0.0, min(cap, d)))
            # Lift-only, exactly as _build_filled_skirts' ring altitudes
            # (clip-introduced vertices ride the DEM where it is above
            # the analytic floor rather than cutting it down).
            return round(_skirt_lift_alt(floor, sample_dem(vx, vy)), 1)

        for ring, _ralts in _build_filled_skirts(
                stations, row_refs, [outward] * m, [governed] * m,
                _floor_depth, band_edges, trigger, step, sample_dem,
                weld_predicate=_pav_weld_at,
                pav_vertex_at=_pav_vertex_at):
            skirt_strips.append((ring, _end_alt_at))

        # ── RESA CUT (arc A2, gate ``RUNWAY_END_RESA_ENABLED``) ──
        # The fill's twin in the OTHER direction: where the skirt fills
        # terrain that drops below the floor, the RESA cut takes down
        # terrain that rises above the ceiling of
        # ``grade_law.runway_end_envelope`` — a gentle
        # ``RUNWAY_END_RESA_MAX_SLOPE`` ramp off the pavement-exit
        # elevation (ICAO Annex 14 §3.5.10), so an overrun meets a ramp
        # instead of a wall.  It is emitted HERE, inside the skirt
        # emitter, because this is where the authoritative end anchor,
        # the pavement-exit march, the corridor half-width and the weld
        # discipline already live (the legacy Pass C ``_emit_resa`` is
        # NOT resurrected — its whole chain is gated off).
        #
        # SCALAR SLOPE, not a per-station law call: inside the reach the
        # envelope's ceiling IS exactly ``RUNWAY_END_RESA_MAX_SLOPE * d``
        # (see ``test_runway_end_resa_cut``'s lockstep assertion), which
        # is precisely ``_build_graded_strips``' ``ceiling(d) = ref +
        # slope*d``.  The builder's ``band_caps`` supplies the reach
        # bound the envelope's ``None`` past ``resa_reach_m`` expresses.
        # NO PAVEMENT EXIT ⇒ NO END ZONE ⇒ NO CUT (2026-07-24).  When the
        # outward march runs the whole ``_RESA_PAVEMENT_PROBE_MAX_M``
        # without leaving the pavement union there IS no pavement exit,
        # so the anchor this whole regime references does not exist: p0
        # lands 300 m out in the middle of pavement and the reference
        # read there is meaningless (at CYXY end 1 it returned None
        # pre-solve and resolved 6.3 m higher post-solve — measured
        # +1.68…+7.47 m across 44 vertices, which is what tripped the
        # arc-R stop condition).
        #
        # The FILL already vanishes here by law: ``pavement_beyond_end``
        # consumes the entire governed length, so
        # ``runway_end_governed_length_beyond_pavement_m`` returns 0.
        # The cut is the fill's twin and must agree with it about whether
        # an end zone exists at all — the two may differ in EXTENT (the
        # cut's reach is deliberately the earthwork cap, not the governed
        # length) but not about existence.  Physically: pavement
        # continuing 300 m past the runway end is pavement, governed by
        # its own law and the adjacent-ground law, not an overrun area
        # owed a RESA ramp.
        _no_pavement_exit = start >= _RESA_PAVEMENT_PROBE_MAX_M - step
        if RUNWAY_END_RESA_ENABLED and _no_pavement_exit:
            if os.environ.get("O4_SKIRT_DEBUG") == "1":
                print(f"  [resa-debug] end at ({seed[0]:.1f},{seed[1]:.1f})"
                      f" — outward march never exited pavement in "
                      f"{_RESA_PAVEMENT_PROBE_MAX_M:.0f} m; no end zone, "
                      f"no cut.")
        elif RUNWAY_END_RESA_ENABLED:
            def _resa_alt_at(vx, vy, p0=p0, nx=nx, ny=ny,
                             ref=float(ref), cap=resa_reach,
                             sample_dem=sample_dem):
                d = (vx - p0[0]) * nx + (vy - p0[1]) * ny
                if d <= 0.02 and pav_union.distance(Point(vx, vy)) <= 0.05:
                    # WELD ROW, verbatim from ``_end_alt_at``: a vertex ON
                    # the pavement exit edge carries the LOCAL pavement
                    # edge value (containment-free read 1 m inside), so the
                    # cut abuts the pavement with zero step exactly as the
                    # fill does.
                    pav = _nearest_pav_alt(
                        airside, vx - nx * 1.0, vy - ny * 1.0)
                    if pav is not None:
                        return float(pav)
                ceiling = ref + RUNWAY_END_RESA_MAX_SLOPE * max(
                    0.0, min(cap, d))
                # Cut-only (see ``_resa_cut_alt``): a vertex whose DEM is
                # already under the ramp rides the DEM — the cut never
                # fills and never floats above the terrain.
                return round(_resa_cut_alt(ceiling, sample_dem(vx, vy)), 1)

            _n_resa_before = len(resa_strips)
            for ring, _ralts in _build_graded_strips(
                    stations, [ref] * m, [outward] * m, [resa_reach] * m,
                    RUNWAY_END_RESA_MAX_SLOPE, trigger, step, sample_dem,
                    # No ``is_ring_vertex``: ``stations`` is the SYNTHETIC
                    # line ea→eb across the pavement exit, not a ring-edge
                    # subdivision, so its stations have no exact-ring-vertex
                    # correspondence and the weld-row thinning cannot apply
                    # (the legacy ``_emit_resa`` carried the same note).
                    is_ring_vertex=None):
                resa_strips.append((ring, _resa_alt_at))

            # PER-END SPEC for the solver (arc R slice R1).  Everything the
            # law needs, sourced from THIS end's own march so the solver and
            # this emitter cannot drift: the exit anchor ``p0``, the outward
            # axis, the reach cap, the corridor half-width, and the FLOOR
            # law's own arguments (carried verbatim even though the ceiling
            # ignores them — ``runway_end_envelope`` takes both bounds and a
            # future law revision must see the same inputs here as in the
            # fill).  ``anchor_xy`` is the frozen-nearest pavement ring
            # vertex the interval edge couples to; ``read_xy`` is the exact
            # point the analytic ``ref`` was read at, which the writeback
            # re-reads on the SOLVED, CROWNED pavement.
            # Published ONLY when this end actually produced cut geometry,
            # so a truthy ``layout.runway_end_resa_presolve`` always means
            # "this airport HAS a RESA cut" — the same store semantics the
            # gap-fill / adjacent-ground stores carry (the flat-airport
            # fast path keys its refusals on exactly that property).
            if _resa_solver_admitted and len(resa_strips) > _n_resa_before:
                resa_end_specs.append({
                    "p0": (float(p0[0]), float(p0[1])),
                    "outward": (float(nx), float(ny)),
                    "cap": float(resa_reach),
                    "half": float(half),
                    "governed": float(governed),
                    "entry_grade": float(entry_grade),
                    "pavement_beyond_end": float(pavement_beyond_end),
                    "read_xy": (float(p0[0] - nx * 1.0),
                                float(p0[1] - ny * 1.0)),
                    "anchor_xy": _nearest_pav_vertex(p0[0], p0[1]),
                    "ref_presolve": float(ref),
                })

        if os.environ.get("O4_SKIRT_DEBUG") == "1":
            _n_row_valid = sum(1 for v in raw_refs if v is not None)
            print(f"  [skirt-debug] end at ({seed[0]:.1f},{seed[1]:.1f}) "
                  f"outward ({nx:.3f},{ny:.3f}) start={start:.1f} "
                  f"ref={ref} entry={entry_grade:.4f} "
                  f"governed={governed} strips_so_far={len(skirt_strips)} "
                  f"row_refs={_n_row_valid}/{len(raw_refs)} valid"
                  + (" (scalar fallback)"
                     if _n_row_valid and row_refs == [float(ref)] * m
                     else ""))

        # ── Blast-pad / stopway FLANK wrap (user 2026-07-05) ──
        # The end strip governs beyond the pavement exit; the FLANKS of
        # the overrun pavement between the runway end point and that
        # exit sit inside the same governed end zone, and a lateral drop
        # there is the same violation.  Fill strips hug the pavement
        # side edges out to the end-zone corridor (± ``half``), with a
        # flat-entry law floor (lateral cross-grades are small and a
        # climbing entry clamps to flat anyway).
        if start < 2.0 * step:
            return   # no meaningful overrun pavement — nothing to wrap
        flank_floor_depth = _floor_depth_for(0.0)
        flank_band_edges = runway_end_skirt_profile_breakpoints(0.0)
        n_axis = max(2, int(math.floor(start / step)) + 1)
        axis_distances = [min(start, float(k) * step)
                          for k in range(n_axis)]
        for side in (perp, (-perp[0], -perp[1])):
            sxn, syn = side
            edge_stations, edge_alts, edge_offsets, caps = [], [], [], []
            axis_kept = []
            for t in axis_distances:
                cx, cy = seed[0] + nx * t, seed[1] + ny * t
                lateral_exit = _pavement_exit_along(
                    prep_pav, cx, cy, sxn, syn, half, step)
                if lateral_exit >= half - 2.0 * _PAVEMENT_GAP_M:
                    continue   # pavement fills the corridor here
                ex, ey = cx + sxn * lateral_exit, cy + syn * lateral_exit
                edge_alt = _nearest_pav_alt(
                    airside, ex - sxn * 1.0, ey - syn * 1.0)
                if edge_alt is None:
                    continue
                edge_stations.append((ex, ey))
                edge_alts.append(float(edge_alt))
                edge_offsets.append(lateral_exit)
                caps.append(half - lateral_exit)
                axis_kept.append(t)
            if len(edge_stations) < 2:
                continue

            # PAVEMENT-EDGE DISCONTINUITY SPLIT (SPLP runway-20 flank,
            # 2026-07-17): the flank references the pavement side-edge
            # altitude sampled per axial station.  Where the runway edge
            # abuts a HIGHER adjacent pavement (SPLP: the runway at
            # ~48.7 m runs beside an apron/pad at ~53.3 m) the tracked
            # reference STEPS ~4.6 m over one 5 m station — a longitudinal
            # jump far above the skirt down-grade cap.  A single band
            # interpolates its fill reference (``_flank_alt_at``)
            # CONTINUOUSLY across that step, so the emitted surface
            # descends 63 %/23 % between adjacent vertices — a signature
            # ``max(floor, DEM)`` can never produce, which the emitted-
            # patch reader reads as post-emission corruption.  A fill must
            # never BRIDGE a pavement-level step: split the flank into
            # contiguous axial runs wherever the reference altitude changes
            # faster than the law down-grade allows over the inter-station
            # distance, and build each run off its OWN continuous reference
            # closure.  The gap left at the step is the real pavement-to-
            # pavement transition (a wall between two levels), not a
            # graded skirt.  End bands (constant reference) never split.
            seg_bounds = [0]
            for _i in range(len(edge_stations) - 1):
                (_px, _py) = edge_stations[_i]
                (_qx, _qy) = edge_stations[_i + 1]
                _seg_len = math.hypot(_qx - _px, _qy - _py)
                if abs(edge_alts[_i + 1] - edge_alts[_i]) > (
                        RUNWAY_END_SKIRT_MAX_DOWN_GRADE * _seg_len
                        + _SKIRT_REF_STEP_NOISE_M):
                    seg_bounds.append(_i + 1)
            seg_bounds.append(len(edge_stations))

            for _sb in range(len(seg_bounds) - 1):
                _a, _b = seg_bounds[_sb], seg_bounds[_sb + 1]
                if _b - _a < 2:
                    continue
                seg_stations = edge_stations[_a:_b]
                seg_alts = edge_alts[_a:_b]
                seg_offsets = edge_offsets[_a:_b]
                seg_caps = caps[_a:_b]
                seg_axis = axis_kept[_a:_b]

                def _flank_alt_at(vx, vy, seed=seed, nx=nx, ny=ny,
                                  sxn=sxn, syn=syn,
                                  axis_kept=seg_axis,
                                  edge_offsets=seg_offsets,
                                  edge_alts=seg_alts,
                                  floor_depth=flank_floor_depth,
                                  half=half, sample_dem=sample_dem):
                    # Along-axis position → interpolate the pavement edge
                    # offset and altitude between the two nearest stations
                    # of THIS run (its reference is continuous).
                    s = (vx - seed[0]) * nx + (vy - seed[1]) * ny
                    s = max(axis_kept[0], min(axis_kept[-1], s))
                    j = 1
                    while j < len(axis_kept) - 1 and axis_kept[j] < s:
                        j += 1
                    span = axis_kept[j] - axis_kept[j - 1]
                    w = 0.0 if span <= 0.0 else (s - axis_kept[j - 1]) / span
                    offset = (edge_offsets[j - 1]
                              + (edge_offsets[j] - edge_offsets[j - 1]) * w)
                    edge_alt = (edge_alts[j - 1]
                                + (edge_alts[j] - edge_alts[j - 1]) * w)
                    lateral = (vx - seed[0]) * sxn + (vy - seed[1]) * syn
                    d = max(0.0, min(half - offset, lateral - offset))
                    if d <= 0.02:
                        # WELD ROW: a vertex on the flank pavement edge
                        # carries the interpolated edge value verbatim
                        # (weld ruling 2026-07-09).
                        return float(edge_alt)
                    # Lift-only (see _skirt_lift_alt): a flank vertex on a
                    # bump above the local floor rides the DEM, not a cut.
                    return round(_skirt_lift_alt(
                        edge_alt - floor_depth(d), sample_dem(vx, vy)), 1)

                flank_rings = _build_filled_skirts(
                    seg_stations, seg_alts, [side] * len(seg_stations),
                    seg_caps, flank_floor_depth, flank_band_edges,
                    trigger, step, sample_dem, weld_predicate=_pav_weld_at,
                    pav_vertex_at=_pav_vertex_at)
                if os.environ.get("O4_SKIRT_DEBUG") == "1":
                    print(f"  [skirt-debug]   flank side "
                          f"({sxn:.3f},{syn:.3f}) run {_sb} "
                          f"stations={len(seg_stations)} "
                          f"caps={min(seg_caps):.1f}..{max(seg_caps):.1f} "
                          f"rings={len(flank_rings)}")
                    for ring, _ralts in flank_rings:
                        ts = [(vx - seed[0]) * nx + (vy - seed[1]) * ny
                              for vx, vy in ring]
                        ls = [(vx - seed[0]) * sxn + (vy - seed[1]) * syn
                              for vx, vy in ring]
                        print(f"  [skirt-debug]     ring t "
                              f"{min(ts):.1f}..{max(ts):.1f} lateral "
                              f"{min(ls):.1f}..{max(ls):.1f}")
                for ring, _ralts in flank_rings:
                    skirt_strips.append((ring, _flank_alt_at))

    if source_runways:
        # AUTHORITATIVE: anchor each end at the apt.dat row-100
        # centreline endpoint + width (as Pass C does).
        for r in source_runways:
            try:
                ax, ay = _ll_to_m(r.lat_a, r.lon_a)
                bx, by = _ll_to_m(r.lat_b, r.lon_b)
            except _GEOM_EXC:
                continue
            dx, dy = bx - ax, by - ay
            full_len = math.hypot(dx, dy)
            # DECLARED width, not the shoulder-widened one: the end corridor
            # is ICAO Annex 14 §3.5.3's "twice that of the runway", and
            # shoulders are a separate feature (§3.2).  ``pipeline``
            # overwrites ``width_m`` in place with runway+shoulders (SPJC
            # 16R/34L 45 -> 81 m), which sized this corridor at 81 m instead
            # of the lawful max(45, strip 75) = 75 m.
            width = float(getattr(r, "declared_width_m", None)
                          or getattr(r, "width_m", 0.0) or 0.0)
            if full_len < 1.0 or width <= 0.0:
                continue
            ux, uy = dx / full_len, dy / full_len
            end_metadata = (
                (getattr(r, "markings_a", 0),
                 getattr(r, "approach_lights_a", 0)),
                (getattr(r, "markings_b", 0),
                 getattr(r, "approach_lights_b", 0)),
            )
            for (end_pt, outward), (markings, lights) in zip(
                    (((ax, ay), (-ux, -uy)), ((bx, by), (ux, uy))),
                    end_metadata):
                seed = (end_pt[0] - outward[0] * _RESA_SEED_INSET_M,
                        end_pt[1] - outward[1] * _RESA_SEED_INSET_M)
                _emit_one_end(
                    outward, width, full_len, seed,
                    lambda s=seed: _pav_alt(airside, s[0], s[1]),
                    runway_end_approach_class(markings, lights))
                # AUTHORITATIVE anchor for the EAT ceiling: the row-100
                # endpoint itself (the DER), not the pavement exit.
                _collect_eat_end(end_pt, outward, width, full_len)
    else:
        # FALLBACK: detect ends from the emitted runway rects.  No
        # apt.dat metadata on this path — the blank-data ladder
        # classifies the end non_precision (errs long).
        def _usable(s) -> bool:
            if s.polygon is None or s.polygon.is_empty:
                return False
            if len(_open_coords(s.polygon)) != 4:
                return False
            return (s.altitude is not None
                    or (s.altitude_high is not None
                        and s.altitude_low is not None))

        runway_shapes = [s for s in layout.shapes
                         if s.role == ROLE_RUNWAY and _usable(s)]
        for s, a, b, full_len in _runway_end_edges(runway_shapes):
            outward = _outward_normal(s.polygon, a, b)
            if outward is None:
                continue
            mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))
            info = _rect_long_short_edges(_open_coords(s.polygon))
            runway_width = (info[1] if info
                            else math.hypot(b[0] - a[0], b[1] - a[1]))
            _emit_one_end(
                outward, runway_width, full_len, mid,
                lambda s=s, mid=mid:
                _sample_runway_segment_elev(s, mid[0], mid[1]),
                runway_end_approach_class(0, 0))
            # No apt.dat here — the rect's own end-edge midpoint IS the
            # runway end on this path (no seed inset is applied above).
            _collect_eat_end(mid, outward, runway_width, full_len)

    # Publish the per-end RESA specs BEFORE the early return so a build
    # whose ends produced no strip at all still leaves a well-defined
    # (empty) store rather than a stale one from an earlier call.
    if _resa_solver_admitted:
        layout.runway_end_resa_presolve = resa_end_specs
    # Same store discipline for the EAT ceiling: written whenever the gate
    # is on (even empty), never left stale from an earlier call.  Gate off
    # ⇒ no attribute at all ⇒ the solve-side block is byte-inert.
    if _eat_gate:
        layout.eat_ceiling_presolve = eat_end_specs
    if not skirt_strips and not resa_strips:
        return 0
    boundary = layout.airport_boundary
    # SURFACE roads / railways crossing the governed zones stay at
    # their own grade — the skirt clears their corridors instead of
    # burying them (the validator exempts the same corridors, via the
    # shared ``_surface_road_corridors``).
    road_block = _surface_road_corridors(layout, _ll_to_m)
    # CROSSING INFLUENCE ZONE (Phase 1, docs/specs/crossing-terrain-
    # ownership.md): a runway-end skirt across a crossing or its depressed
    # road corridor laid its floor ACROSS the buried public road (measured
    # KBNA: skirt pieces 1067-1069 overlap object_bridge_approach 1105-1108
    # by up to 201 m², 8.53 % down-grades into the trench).  The
    # skirt-airside precedence ruling (2026-07-10) makes the skirt override
    # airside pavement, groundside, and RESA cuts — but it does NOT extend
    # into a crossing's influence zone: the skirt clears it, exactly as it
    # already clears surface roads.  The zone is published PRE-solve
    # (superseding the round-8 mapped-road corridor rework, which existed
    # because the old emitted-piece lane clip was a no-op on the pre-solve
    # skirt path), so this clip fires identically on both skirt phases.
    from .crossing_terrain import crossing_influence_zone_union
    zone_block = crossing_influence_zone_union(layout)
    if os.environ.get("O4_CROSSING_ZONE_DEBUG") == "1":
        _zb_area = (zone_block.area
                    if zone_block is not None and not zone_block.is_empty
                    else 0.0)
        print(f"  [crossing-zone-debug] skirt-emit crossing zone union "
              f"area = {_zb_area:.1f} m2 "
              f"({'NON-EMPTY' if _zb_area > 0 else 'EMPTY'})")
    emitted_fill = None
    n = 0
    skirt_debug = os.environ.get("O4_SKIRT_DEBUG") == "1"
    # Lab forensics (O4_SKIRT_DEBUG_DUMP=<path>): record every raw
    # strip ring, every emitted piece and every DROPPED piece from THIS
    # in-pipeline run, so sliver analysis overlays like-for-like
    # geometry (post-hoc probe rebuilds have shown per-process
    # divergence in pavement-exit anchoring — never compare across
    # builds).
    skirt_dump_path = os.environ.get("O4_SKIRT_DEBUG_DUMP")
    skirt_dump = None
    if skirt_dump_path:
        skirt_dump = {"anchor": list(layout.anchor),
                      "strips": [], "pieces": [], "dropped": []}
    for strip_index, (ring, alt_at) in enumerate(skirt_strips):
        if skirt_dump is not None:
            skirt_dump["strips"].append(
                {"index": strip_index,
                 "ring": [[float(x), float(y)] for x, y in ring]})
        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if (_gs_trace and _gs_union_trace is not None
                    and not _gs_union_trace.is_empty):
                try:
                    _ov = poly.intersection(_gs_union_trace).area
                except _GEOM_EXC:
                    _ov = 0.0
                if _ov > 1e-6:
                    _gs_fire_area += _ov
                    _gs_fire_strips += 1
            stage_areas = [("raw", poly.area)]
            for name, block in (("static", static_block),
                                ("road", road_block),
                                ("crossing_zone", zone_block),
                                ("prior_fill", emitted_fill)):
                if block is not None and not block.is_empty:
                    poly = poly.difference(block)
                    stage_areas.append((name, poly.area))
            if boundary is not None and not boundary.is_empty:
                # No emitted shape may cross the airport boundary (the
                # post-clearance boundary clip has already run by now).
                poly = poly.intersection(boundary)
                stage_areas.append(("boundary", poly.area))
            if skirt_debug and stage_areas[-1][1] < 0.98 * stage_areas[0][1]:
                print(f"  [skirt-debug] strip {strip_index} clip: "
                      + " -> ".join(f"{nm} {ar:.0f}"
                                    for nm, ar in stage_areas))
            if poly.is_empty:
                continue
        except _GEOM_EXC:
            continue
        if poly.geom_type == "Polygon":
            components = [poly]
        elif poly.geom_type in ("MultiPolygon", "GeometryCollection"):
            components = [g for g in poly.geoms
                          if g.geom_type == "Polygon"]
        else:
            continue
        for comp in components:
            for simple in _decompose_polygon_with_holes(
                    comp, min_area_m2=1.0):
                if simple.is_empty:
                    continue
                if simple.area < _MIN_CUT_AREA_M2:
                    # The min-area gate exists to reject freestanding
                    # confetti — but a small fragment ATTACHED to the
                    # pavement or existing geometry is a legitimate
                    # corner patch of a continuous fill (the pad-corner
                    # wedges at KCLT are 9–21 m² and dropping them left
                    # validator-visible notches).  Keep attached
                    # fragments; drop isolated ones.
                    attached = False
                    if simple.area >= 1.0 and attach_block is not None:
                        try:
                            attached = simple.distance(attach_block) <= 1.0
                        except _GEOM_EXC:
                            attached = False
                    if not attached:
                        if skirt_dump is not None:
                            skirt_dump["dropped"].append(
                                {"strip": strip_index,
                                 "area": float(simple.area),
                                 "ring": [[float(x), float(y)] for x, y
                                          in _open_coords(simple)]})
                        continue
                piece_ring = _open_coords(simple)
                if len(piece_ring) < 3:
                    continue
                # ``alt_at`` returns final values: weld-row vertices
                # carry the pavement edge value UNROUNDED (so the emit
                # consensus at a shared node is a no-op — the pavement
                # value never moves), interior vertices arrive rounded.
                alts = [float(alt_at(vx, vy)) for vx, vy in piece_ring]
                layout.shapes.append(BuiltShape(
                    polygon=simple, role=ROLE_RUNWAY_CLEARANCE,
                    ref=REF_RUNWAY_END_SKIRT,
                    node_altitudes=alts + [alts[0]]))
                if skirt_dump is not None:
                    skirt_dump["pieces"].append(
                        {"strip": strip_index,
                         "area": float(simple.area),
                         "ring": [[float(x), float(y)]
                                  for x, y in piece_ring]})
                try:
                    emitted_fill = (
                        simple if emitted_fill is None
                        else unary_union([emitted_fill, simple]))
                except _GEOM_EXC:
                    pass
                n += 1

    # ── RESA CUT EMISSION (arc A2) ──────────────────────────────────
    # Emitted AFTER the fill so ``emitted_fill`` is settled: at a given
    # station the terrain either rises above the RESA ceiling or drops
    # below the skirt floor — never both — so the two footprints cannot
    # genuinely overlap, but they CAN meet at their daylight lines.
    # Differencing the cut against the fill makes them ABUT there (the
    # fill's coordinates land in the cut ring verbatim, shapely's
    # shared-edge guarantee) instead of double-covering a sliver.
    #
    # CLIP BLOCK: ``attach_block`` — every pre-existing shape INCLUDING
    # groundside pavement.  The skirt-airside-precedence ruling
    # (2026-07-10) is about the FILL (which trims groundside around
    # itself below); the cut has no such precedence and yields to
    # groundside exactly as the legacy Pass C ``_finalize`` did.
    emitted_cut = None
    n_resa = 0
    for ring, alt_at in resa_strips:
        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            for block in (attach_block, road_block, zone_block,
                          emitted_fill, emitted_cut):
                if block is not None and not block.is_empty:
                    poly = poly.difference(block)
            if boundary is not None and not boundary.is_empty:
                poly = poly.intersection(boundary)
            if poly.is_empty:
                continue
        except _GEOM_EXC:
            continue
        if poly.geom_type == "Polygon":
            components = [poly]
        elif poly.geom_type in ("MultiPolygon", "GeometryCollection"):
            components = [g for g in poly.geoms
                          if g.geom_type == "Polygon"]
        else:
            continue
        for comp in components:
            for simple in _decompose_polygon_with_holes(
                    comp, min_area_m2=1.0):
                if simple.is_empty or simple.area < _MIN_CUT_AREA_M2:
                    continue
                piece_ring = _open_coords(simple)
                if len(piece_ring) < 3:
                    continue
                alts = [float(alt_at(vx, vy)) for vx, vy in piece_ring]
                layout.shapes.append(BuiltShape(
                    polygon=simple, role=ROLE_RUNWAY_CLEARANCE,
                    ref=REF_RUNWAY_END_RESA,
                    node_altitudes=alts + [alts[0]]))
                try:
                    emitted_cut = (
                        simple if emitted_cut is None
                        else unary_union([emitted_cut, simple]))
                except _GEOM_EXC:
                    pass
                n += 1
                n_resa += 1
    if n_resa:
        UI.vprint(1,
            f"  [pav-builder] runway-end RESA cut: emitted {n_resa} "
            f"polygon(s), {emitted_cut.area:.0f} m2.")

    # ── GROUNDSIDE TRIM (skirt airside precedence, Noah ruling
    # 2026-07-10) ── The skirt no longer yields to groundside (it was
    # excluded from the clip block above).  Now enforce the OTHER half of
    # the ruling: every groundside pavement shape that a final skirt
    # footprint overlaps is trimmed AROUND the skirt.  ``emitted_fill`` is
    # already the union of every emitted skirt piece, so it is the exact
    # subtrahend — differencing against it inserts the skirt's boundary
    # coordinates VERBATIM into the groundside ring (shapely's shared-edge
    # guarantee), so the trimmed groundside welds to the skirt chain with
    # zero minted near-parallel geometry and no unowned DEM sliver.  The
    # trimmed vertices' altitudes are re-derived through the same
    # ``_resample_node_altitudes_nn`` edge-interpolation path every other
    # groundside clip uses (tile_cut, boundary), so the remnant keeps
    # groundside's own DEM-following field.
    if (groundside_shapes and emitted_fill is not None
            and not emitted_fill.is_empty):
        _gs_trimmed, _gs_dropped = _trim_groundside_pavement_around_skirts(
            layout, emitted_fill)
        if _gs_trimmed or _gs_dropped:
            UI.vprint(1,
                f"  [pav-builder] runway-end skirt airside precedence: "
                f"trimmed {_gs_trimmed} groundside pavement shape(s) around "
                f"skirt footprints, dropped {_gs_dropped} to residue.")

    # RULING ASSERTION (reporting, not gating — validator convention):
    # after the trim, no groundside pavement shape may intersect a skirt
    # footprint interior.  A non-zero count here is a trim miss, surfaced
    # like every other skirt verification line.
    if emitted_fill is not None and not emitted_fill.is_empty:
        _skirt_union2 = emitted_fill
        _viol = 0
        for s in layout.shapes:
            if (s.role != "groundside_pavement" or s.polygon is None
                    or s.polygon.is_empty):
                continue
            try:
                if s.polygon.intersection(_skirt_union2).area > 1e-3:
                    _viol += 1
            except _GEOM_EXC:
                continue
        if _viol:
            UI.vprint(1,
                f"  [pav-builder] WARN runway-end skirt airside precedence: "
                f"{_viol} groundside pavement shape(s) still overlap a skirt "
                f"footprint (trim miss).")

    if skirt_dump is not None:
        import json
        try:
            with open(skirt_dump_path, "w") as handle:
                json.dump(skirt_dump, handle)
        except OSError:
            pass
    if _gs_trace:
        print(f"[skirt-gs-trace] raw skirt strips overlapping groundside: "
              f"{_gs_fire_strips} strip(s); total groundside area under "
              f"raw skirt footprint: {_gs_fire_area:.1f} m^2")
    return n
