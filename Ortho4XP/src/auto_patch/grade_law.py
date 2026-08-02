"""THE within-shape grade LAW — the single source of truth for *which* vertex
pairs of a soft airside shape are grade-constrained and *at what budget*.

Both readers consume this one law:
  * the SOLVER, via ``grade_graph.shape_constraints`` (builds a ``PairContext``
    from the in-memory ``GradeShape``/``GradeContext``), and
  * the grade TEST, via ``tools/check_grade`` (builds a ``PairContext`` from the
    emitted OSM)  ← wiring in progress (docs/cleanup_consolidation_plan.md M4).
So the surface we BUILD and the surface we CHECK cannot drift: fix a rule here
once and it is both built and verified.

## The allowance model
A pair's grade budget is anisotropic in the local spine (route) frame:

    allowed |Δz|  =  cL · Δs∥  +  cT · Δs⊥

where ``Δs∥`` is the along-route (spine arc-length) separation and ``Δs⊥`` the
perpendicular offset.  This is what lets a rising CURVE be graded correctly: on
the inside of a turn the edge climbs the same Δz over a shorter physical chord
(so it is steeper per metre) yet is compliant, because its longitudinal budget is
the SPINE arc length it spans, not its own chord — see
``docs/m4_constraint_graph_findings.md`` and the curved-junction model.

The law emits an ``Allowance(cL, cT)`` per pair.  Under the ``O4_ANISO_EDGES``
gate (``docs/anisotropic_edge_handling_plan.md``), ``grade_graph.shape_constraints``
decomposes a spine / junction-body / apron-blend pair against its whole chained
ROUTE and BAKES the anisotropic budget ``cL·Δs∥ + cT·Δs⊥`` (Δs∥ = spine arc) into
the allowance — so a climbing CURVE earns its full arc length and stops being
false-flagged at junctions, and A/B taxiways carry the tighter 2 % transverse cap.
With the gate OFF the allowance is flat (``cL == cT``, Δs⊥ = 0) and reduces to the
legacy scalar ``cap·dist`` — byte-identical to the prior in-line logic.  Either
way every reader evaluates ``Allowance.at(Δs∥, Δs⊥)``; the BAKED allowance returns
its precomputed budget so the solver and validator share one decomposition.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

from .config import (
    ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT,
    ADJACENT_GROUND_LIP_MAX_DOWN_SLOPE, ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE,
    ADJACENT_GROUND_LIP_WIDTH_M, ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE,
    APRON_MAX_GRADE, APRON_SHOULDER_MAX_DOWN_SLOPE,
    APRON_SHOULDER_MIN_DOWN_SLOPE, APRON_SHOULDER_WIDTH_M,
    BUILDING_FRONTAGE_MAX_GRADE, BUILDING_FULL_FRONTAGE,
    BUILDING_FULL_FRONTAGE_AREA_M2,
    BUILDING_REACH_CORRIDOR_M, CLEARANCE_LATERAL_MAX_SLOPE,
    CLEARANCE_MAX_REACH_M, DRAINAGE_SPINE_MIN_FALL_M,
    JUNCTION_MESH_CONSTRAINTS,
    OLS_APPROACH_DIVERGENCE, OLS_APPROACH_EMIT_REACH_M,
    OLS_APPROACH_FIRST_SECTION_SLOPE,
    OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M, OLS_APPROACH_SETBACK_M,
    OLS_APPROACH_SETBACK_VISUAL_CODE1_M, OLS_MAX_CUT_DEPTH_M,
    OLS_STRIP_HALF_WIDTH_INSTRUMENT_BY_CODE,
    OLS_TRANSITIONAL_EMIT_REACH_M, OLS_TRANSITIONAL_SLOPE,
    OLS_TRANSITIONAL_SLOPE_STEEP,
    RUNWAY_END_CLEARANCE_LENGTH_BY_CODE, RUNWAY_END_RESA_MAX_SLOPE,
    ROLE_GRADE_LIMITS,
    RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE,
    RUNWAY_STRIP_BAND_MAX_DOWN_SLOPE_BY_CODE, RUNWAY_STRIP_HALF_WIDTH_BY_CODE,
    SERVICE_ROAD_MAX_GRADE, TAXI_MAX_GRADE, TAXIWAY_STRIP_BAND_MAX_DOWN_SLOPE,
    TAXIWAY_STRIP_BAND_MIN_DOWN_SLOPE, runway_code_number,
    taxiway_strip_graded_half_width_for_letter)

# ── Law constants (the adjustable knobs of the law) ──────────────────────────
APRON_ROLE = "apron"
# The junction-family roles the JUNCTION MESH rule in ``classify_pair`` applies
# to.  Defined HERE (the law) and re-exported by ``grade_graph`` so the law and
# its readers share one definition.
JUNCTION_ROLES = ("junction", "service_junction")

# THE single reach/grade rules, surfaced here so every site refers to ONE value
# and cannot drift into local copies (user 2026-06-29).
#  * ``BUILDING_REACH_CORRIDOR_M`` (imported) — max building↔spine apron reach.
#  * ``APRON_MAX_GRADE`` / ``TAXI_MAX_GRADE`` (imported from config) — the apron
#    (1 %) and taxiway (1.5 %) grade caps; re-exported so reach/seat/spine code
#    stops keeping local ``_APRON_CAP`` / ``_ENTRY_CAP`` copies.
#  * runway-CONTACT geometry: a taxi centerline endpoint within
#    ``RUNWAY_CONTACT_M`` of a runway is a contact; the nearest emitted node
#    within ``RUNWAY_JOIN_NEAR_M`` of it is the anchored join node.  One source
#    for ``grade_graph._runway_anchors``, the validator's runway-join check, and
#    ``lateral_spine_nodes`` (was three copies of 12 m / 18 m).
RUNWAY_CONTACT_M = 12.0
RUNWAY_JOIN_NEAR_M = 18.0
# COINCIDENT-join tolerance (user ruling 2026-07-16: taxi joins anchor to
# the RUNWAY EDGE value — the crowned edge — never the centerline/crown
# profile).  A join vertex that COINCIDES with its runway contact must sit
# within this of the crowned-edge value; the validator's old ``d < 1e-6``
# skip hid exactly this class (KBNA 13/31: 0.24-0.31 m steps =
# RUNWAY_CROWN_TRANSVERSE × half-width, joins left at the profile value).
# One source for the join validator AND the build-time verify.
RUNWAY_JOIN_COINCIDENT_TOL_M = 0.05


def runway_join_contact(ln, endpoint, rwy_polygon):
    """THE runway-join contact point for a taxi centerline endpoint (single source
    for ``grade_graph._runway_anchors`` AND the validator's runway-join check, so
    the solver anchors exactly the node the validator checks).

    Returns the ``(x, y)`` where the taxiway↔runway CONTACT node sits, or ``None``
    when ``endpoint`` is not within ``RUNWAY_CONTACT_M`` of the runway.

    A taxi route connects to the runway CENTERLINE, so when the endpoint lies
    INSIDE the runway the real contact is where the centerline crosses the runway
    EDGE — that is where the emitted taxi/junction/runway node is welded, and it
    is what ``RUNWAY_JOIN_NEAR_M`` must reach.  On a WIDE runway the centerline is
    ~half the width from the edge (HECA shoulder-widened to 86 m ⇒ ~43 m ≫ the
    18 m join radius), so anchoring at the deep-interior endpoint finds no emitted
    node and the join is silently missed → the taxiway grades to DEM off the runway
    (a big drop at F→05R, T5→05C).  Using the edge crossing fixes both.  For an
    endpoint at/outside the edge the endpoint is already the contact."""
    from shapely.geometry import Point
    P = Point(endpoint)
    if rwy_polygon.distance(P) > RUNWAY_CONTACT_M:
        return None
    if not rwy_polygon.covers(P):
        return (endpoint[0], endpoint[1])
    try:
        xing = ln.intersection(rwy_polygon.boundary)
    except Exception:
        return (endpoint[0], endpoint[1])
    pts = ([xing] if getattr(xing, "geom_type", "") == "Point"
           else [g for g in getattr(xing, "geoms", [])
                 if g.geom_type == "Point"])
    if not pts:
        return (endpoint[0], endpoint[1])
    ex, ey = endpoint
    best = min(pts, key=lambda p: (p.x - ex) ** 2 + (p.y - ey) ** 2)
    return (best.x, best.y)


def building_requires_full_frontage(area_m2: float) -> bool:
    """THE canonical building-size reach rule (single source for seater AND
    checker).  A building at/above ``BUILDING_FULL_FRONTAGE_AREA_M2`` must have
    its ENTIRE apron-facing frontage reachable from the taxi route within grade
    (a terminal maneuvers along its whole face).  A SMALLER building need only
    reach the spine at its central chord — it is seated at that level and acts as
    a LOCAL reach ANCHOR: its non-central frontage and the apron stepping up to
    it within the apron cap grade FROM the pad, not from the runway route, so
    those points are not runway-reach-constrained.  Honours the
    ``BUILDING_FULL_FRONTAGE`` gate (off ⇒ all buildings use the central-chord
    rule, the pre-2026-06-27 model).

    Consumed by ``route_profile.anchors.build_building_seats`` (which frontage to
    seat at) and ``grade_graph_validate.route_band_violations`` (small pads are
    local anchors; large frontages stay route-reach-checked) — so the level we
    BUILD a building at and the reach we CHECK it against come from one rule."""
    return bool(BUILDING_FULL_FRONTAGE) and area_m2 >= BUILDING_FULL_FRONTAGE_AREA_M2

# ── Runway end skirt law (inverse RESA — downward terrain governance) ────────
# Terrain beyond a runway end may not DROP away arbitrarily: FAA AC
# 150/5300-13B §3.16.5 caps the RSA longitudinal grade at 0…−3 % for the
# first 200 ft (61 m) beyond the end and −5 % beyond, with grade changes
# limited to ±2 % per 100 ft (30.5 m); ICAO Annex 14 §4.7 caps RESA
# downward slopes at 5 %.  Beyond the governed footprint a drop is LAWFUL
# (Madeira-style), so the governed length is also the hard cap on emitted
# fill.  Single source for the Pass D skirt EMITTER
# (``clearance._emit_resa_skirt``) and the ``check_grade`` validator —
# regulatory basis and plan: ``docs/runway_end_skirt_plan.md``.
RUNWAY_END_SKIRT_NEAR_ZONE_M = 61.0             # FAA "first 200 feet"
RUNWAY_END_SKIRT_NEAR_MAX_DOWN_GRADE = 0.03     # 0…−3 % in the near zone
RUNWAY_END_SKIRT_MAX_DOWN_GRADE = 0.05          # −5 % beyond
RUNWAY_END_SKIRT_MAX_GRADE_CHANGE_PER_M = 0.02 / 30.5   # ±2 % per 100 ft

# Governed-length scaling by approach class (per-end, from
# ``config.runway_end_approach_class``).  Visual ends clamp to the ICAO
# 90 m minimum; precision ends extend to the FAA C/D/E footprint
# (1,000 ft ≈ 305 m for code 3/4, the 240 m ICAO recommendation for
# smaller precision runways).  Non-precision uses the by-code base.
RUNWAY_END_SKIRT_VISUAL_MAX_LENGTH_M = 90.0
RUNWAY_END_SKIRT_PRECISION_MIN_LENGTH_M = 240.0
RUNWAY_END_SKIRT_PRECISION_CODE34_LENGTH_M = 305.0


def runway_end_governed_length_m(
        runway_length_m: float, approach_class: str) -> float:
    """THE distance beyond the pavement end within which the down-slope
    floor applies (and beyond which a drop is lawful).  Base footprint by
    ICAO code number (``RUNWAY_END_CLEARANCE_LENGTH_BY_CODE``), scaled by
    the end's approach class — better approaches earn a longer governed
    apron of terrain, per FAA AC 150/5300-13B Appendix G."""
    code = runway_code_number(runway_length_m)
    base = RUNWAY_END_CLEARANCE_LENGTH_BY_CODE[code]
    if approach_class == "visual":
        return min(base, RUNWAY_END_SKIRT_VISUAL_MAX_LENGTH_M)
    if approach_class == "precision":
        if code >= 3:
            return max(base, RUNWAY_END_SKIRT_PRECISION_CODE34_LENGTH_M)
        return max(base, RUNWAY_END_SKIRT_PRECISION_MIN_LENGTH_M)
    return base


# Stop the skirt this far short of a constraining feature (road /
# water) so the feature keeps its own approach embankment.
RUNWAY_END_SKIRT_CONSTRAINT_MARGIN_M = 5.0


def runway_end_constrained_length_m(
        governed_length_m: float,
        constraint_distance_m: float | None) -> float:
    """Clamp the governed length when real infrastructure crosses the
    end zone.  No reliable EMAS data source exists (user ruling
    2026-07-05), but a road, service road or water body close beyond a
    runway end IS the fingerprint of a non-standard end — the real
    world did not build a full-length RSA there (EMAS / declared
    distances instead, e.g. KCLT 18L: perimeter road at the blast-pad
    end).  The skirt ends a margin short of the first constraint; with
    the constraint at the pavement end the skirt vanishes entirely."""
    if constraint_distance_m is None:
        return governed_length_m
    return max(0.0, min(
        governed_length_m,
        constraint_distance_m - RUNWAY_END_SKIRT_CONSTRAINT_MARGIN_M))


def _runway_end_skirt_signed_grade(
        distance_m: float, start_grade: float) -> float:
    """Signed grade (positive = climbing) of the LOWEST lawful surface at
    ``distance_m`` beyond the runway end.  The steepest permissible
    descent is bounded by BOTH what the grade-change rate can reach from
    the runway's own end grade AND the zone's down-grade cap; the cap
    itself eases from −3 % to −5 % at the near-zone boundary under the
    same rate limit, so the floor has no curvature kink anywhere."""
    rate = RUNWAY_END_SKIRT_MAX_GRADE_CHANGE_PER_M
    reachable = start_grade - rate * distance_m
    if distance_m <= RUNWAY_END_SKIRT_NEAR_ZONE_M:
        lawful = -RUNWAY_END_SKIRT_NEAR_MAX_DOWN_GRADE
    else:
        lawful = max(
            -RUNWAY_END_SKIRT_MAX_DOWN_GRADE,
            -RUNWAY_END_SKIRT_NEAR_MAX_DOWN_GRADE
            - rate * (distance_m - RUNWAY_END_SKIRT_NEAR_ZONE_M))
    return max(lawful, reachable)


def runway_end_skirt_profile_breakpoints(
        start_grade: float = 0.0) -> list[float]:
    """Distances (m, ascending) where the floor profile's GRADE LAW
    changes — the boundaries of its piecewise-linear-grade segments.
    Between consecutive breakpoints the floor is a single quadratic, so
    an emitter rendering it as ruled bands split at these breakpoints
    bounds the chord-vs-floor sagitta at ``rate · L² / 8`` (≤ 0.31 m for
    the 61 m near zone) — far inside the fill trigger.  Single source
    for the Pass D band edges AND the floor integration below."""
    start_grade = min(0.0, start_grade)
    rate = RUNWAY_END_SKIRT_MAX_GRADE_CHANGE_PER_M
    return sorted({
        RUNWAY_END_SKIRT_NEAR_ZONE_M,
        RUNWAY_END_SKIRT_NEAR_ZONE_M
        + (RUNWAY_END_SKIRT_MAX_DOWN_GRADE
           - RUNWAY_END_SKIRT_NEAR_MAX_DOWN_GRADE) / rate,
        (start_grade + RUNWAY_END_SKIRT_NEAR_MAX_DOWN_GRADE) / rate,
        (start_grade + RUNWAY_END_SKIRT_MAX_DOWN_GRADE) / rate,
    })


def runway_end_skirt_floor_profile(
        distances_m: list[float], start_grade: float = 0.0) -> list[float]:
    """THE lowest lawful surface beyond a runway end, as DEPTHS (m, ≥ 0)
    below the runway-end elevation at each requested distance.

    The floor starts at the runway's own end grade (``start_grade``,
    signed, positive = the runway climbs toward its end) so a DESCENDING
    runway carries no grade discontinuity into the skirt, then steepens
    under the grade-change rate limit to the near-zone cap (−3 %) and the
    far cap (−5 %).  A CLIMBING end grade clamps to 0 at the pavement
    end: the FAA near zone permits only downward slopes ("between 0 and
    3.0 percent, with any slope being downward from the ends"), so a
    crest legally terminates AT the runway end — and the skirt is
    FILL-only; terrain above the pavement-end elevation is Pass C's
    (cut) domain.

    The grade function is piecewise linear, so trapezoid integration
    between its breakpoints is EXACT — the emitter and the validator
    evaluate identical floors.
    """
    start_grade = min(0.0, start_grade)
    # Breakpoints of the piecewise-linear signed-grade function: the
    # near-zone boundary, the cap's own −3 %→−5 % easing end, and where
    # the curvature-reachable line meets each cap level.
    breakpoints = runway_end_skirt_profile_breakpoints(start_grade)

    def _depth(distance_m: float) -> float:
        drop = 0.0
        previous = 0.0
        for cut in [b for b in breakpoints if 0.0 < b < distance_m] \
                + [distance_m]:
            segment = cut - previous
            drop -= 0.5 * segment * (
                _runway_end_skirt_signed_grade(previous, start_grade)
                + _runway_end_skirt_signed_grade(cut, start_grade))
            previous = cut
        return max(0.0, drop)

    return [_depth(d) for d in distances_m]


def runway_end_governed_length_beyond_pavement_m(
        governed_length_m: float, pavement_beyond_end_m: float) -> float:
    """Governed length REMAINING beyond the overrun-pavement exit.

    The FAA runway safety area is measured from the RUNWAY END, and any
    blast pad / stopway pavement past the end sits INSIDE it (AC
    150/5300-13B §3.16 — the safety area encompasses the stopway), so
    overrun pavement CONSUMES the first ``pavement_beyond_end_m`` of the
    governed footprint.  Before 2026-07-09 the emitter applied the full
    governed length from the pavement exit instead, extending every
    skirt by its blast-pad length (KCLT 18R: 124 m pad → fill to 429 m
    past the end vs the lawful 305 m; user report 'about 70 m too long'
    = the 59-71 m HECA pads).  Returns 0 when pavement covers the whole
    footprint (the skirt vanishes; the KCLT-18L EMAS-end class)."""
    return max(0.0, governed_length_m - max(0.0, pavement_beyond_end_m))


def runway_end_skirt_profile_breakpoints_beyond_pavement(
        start_grade: float = 0.0,
        pavement_beyond_end_m: float = 0.0) -> list[float]:
    """``runway_end_skirt_profile_breakpoints`` re-expressed as distances
    beyond the PAVEMENT EXIT when that exit sits ``pavement_beyond_end_m``
    past the runway end: the law profile is anchored at the runway end,
    so its grade-law breakpoints shift inward by the overrun length
    (breakpoints the pavement already consumed drop out)."""
    advance = max(0.0, pavement_beyond_end_m)
    return sorted({
        b - advance
        for b in runway_end_skirt_profile_breakpoints(start_grade)
        if b > advance + 1e-9})


def runway_end_skirt_floor_profile_beyond_pavement(
        distances_m: list[float], start_grade: float = 0.0,
        pavement_beyond_end_m: float = 0.0) -> list[float]:
    """Floor DEPTHS (m, ≥ 0) below the pavement-EXIT elevation at each
    distance beyond the exit, for an exit ``pavement_beyond_end_m`` past
    the runway end.

    The descent law is anchored at the RUNWAY END (see
    ``runway_end_governed_length_beyond_pavement_m``), so by the exit the
    profile is already ``pavement_beyond_end_m`` into its descent — the
    fill starts FLUSH at the exit-edge elevation (the overrun pavement
    carries its own solved profile) but falls at the ADVANCED profile's
    grade immediately, instead of restarting the gentle 0→−3 % easing a
    second time.  With no overrun pavement this IS
    ``runway_end_skirt_floor_profile``."""
    advance = max(0.0, pavement_beyond_end_m)
    if advance <= 0.0:
        return runway_end_skirt_floor_profile(distances_m, start_grade)
    depths = runway_end_skirt_floor_profile(
        [advance] + [advance + d for d in distances_m], start_grade)
    return [d - depths[0] for d in depths[1:]]


def runway_end_corridor_half_width_m(runway_width_m: float,
                                     runway_length_m: float) -> float:
    """Half-width (m) each side of the extended centreline of the governed
    runway-END corridor — the lateral extent of both the skirt fill and the
    RESA cut.

    ICAO Annex 14 §3.5.3: the RESA "shall extend to a width of at least twice
    that of the runway", and §3.5.2 recommends it extend to the width of the
    graded portion of the strip.  As a HALF-width those read
    ``max(runway_width, strip_half)`` — the full corridor is then at least
    2 x the runway width AND at least the graded strip width, satisfying both
    clauses.  (The full apt.dat width standing in for a half-width is
    deliberate, not a units slip: it is the §3.5.3 factor-of-two.)

    Single source for ``clearance.emit_runway_end_skirts`` (both directions)
    and the ``verification`` reader.
    """
    code = runway_code_number(runway_length_m)
    return max(float(runway_width_m),
               float(RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code]))


def runway_axis_and_width(points) -> "Optional[tuple]":
    """``(axis_a, axis_b, width_m)`` for a runway from its EMITTED ring
    vertices — the centreline axis endpoints (at the two extreme along-axis
    stations) and the ring's full transverse extent.

    The direction is the PRINCIPAL (largest-variance) axis of the vertex
    cloud, which is parallel to the runway centreline by construction for a
    long thin rectangle; the longest-vertex-PAIR alternative picks the
    corner-to-corner DIAGONAL and skews 1–2° (the same reasoning, and the
    same closed form, as ``verification._runway_principal_axis`` — that
    function is NOT reused here on purpose: ``tools/check_grade.py`` is the
    other consumer and must not import the shapely-heavy ``verification``
    module to build a footprint out of four numbers).

    ``points`` should be EVERY ring vertex of every emitted shape carrying
    the runway (a tile cut / crossing split leaves one runway as several
    ways — pass them all so the axis is the runway's, not a fragment's).
    ``None`` when the cloud is degenerate.  Pure math, no geometry deps.
    """
    import math as _math
    pts = [(float(x), float(y)) for (x, y) in points]
    n = len(pts)
    if n < 2:
        return None
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = syy = sxy = 0.0
    for x, y in pts:
        ddx, ddy = x - cx, y - cy
        sxx += ddx * ddx
        syy += ddy * ddy
        sxy += ddx * ddy
    tr = sxx + syy
    det = sxx * syy - sxy * sxy
    disc = max(0.0, (0.5 * tr) ** 2 - det)
    lam = 0.5 * tr + _math.sqrt(disc)                 # largest eigenvalue
    if abs(sxy) > 1e-9:
        ux, uy = lam - syy, sxy
    else:
        ux, uy = (1.0, 0.0) if sxx >= syy else (0.0, 1.0)
    norm = _math.hypot(ux, uy)
    if norm < 1e-12:
        return None
    ux, uy = ux / norm, uy / norm
    along = [(x - cx) * ux + (y - cy) * uy for x, y in pts]
    across = [(x - cx) * -uy + (y - cy) * ux for x, y in pts]
    s0, s1 = min(along), max(along)
    if s1 - s0 <= 0.0:
        return None
    return ((cx + s0 * ux, cy + s0 * uy),
            (cx + s1 * ux, cy + s1 * uy),
            max(across) - min(across))


def runway_strip_wall_keepout_rings(
        axis_a: tuple[float, float], axis_b: tuple[float, float],
        runway_width_m: float) -> list[list[tuple[float, float]]]:
    """THE runway-STRIP footprint inside which a ``retaining_wall`` face is
    INADMISSIBLE (owner ruling 2026-08-01, runway-edge terrain law: "retaining
    walls are NEVER lawful at a runway edge — runway surroundings must grade
    away smoothly").

    Returned as CLOSED RINGS of ``(x, y)`` in whatever planar metre frame the
    caller's ``axis_a`` / ``axis_b`` live in — deliberately geometry-library
    free, so the EMITTER (``adjacent_ground``, layout frame) and the VALIDATOR
    (``tools/check_grade.py``, its own mean-centred frame with the axis
    re-derived from the emitted runway ring) build the IDENTICAL footprint from
    the identical numbers.  Lockstep by construction, exactly as
    ``adjacent_ground_envelope`` is for the corridor.

    Two components, both already law elsewhere — no new constant is minted:

      * the LATERAL graded strip — centreline ± ``RUNWAY_STRIP_HALF_WIDTH_
        BY_CODE[code]`` (ICAO Annex 14 §3.4.9), over the runway's own length;
      * the two END corridors — ± ``runway_end_corridor_half_width_m`` (Annex
        14 §3.5.2-3.5.3, the RESA/skirt corridor this module already owns),
        extending ``runway_end_clearance_length_m`` beyond each end.

    The displaced drop relocates lawfully: the strip corridor grades to the
    75 m edge under ``adjacent_ground_envelope``, and beyond it zone 3's free
    floor makes the terrace lawful (adjacent-ground zone law) — so removing
    the face here needs no new corridor math.
    """
    import math as _math
    ax, ay = float(axis_a[0]), float(axis_a[1])
    bx, by = float(axis_b[0]), float(axis_b[1])
    dx, dy = bx - ax, by - ay
    length = _math.hypot(dx, dy)
    if length < 1.0:
        return []
    ux, uy = dx / length, dy / length
    px, py = -uy, ux                      # unit normal
    code = runway_code_number(length)
    strip_half = float(RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code])
    end_half = runway_end_corridor_half_width_m(runway_width_m, length)
    end_len = float(RUNWAY_END_CLEARANCE_LENGTH_BY_CODE[code])

    def _rect(s0, s1, half):
        """Closed ring of the axis-aligned band ``s ∈ [s0, s1]``, ``|t| ≤
        half`` in the (along, across) runway frame."""
        corners = ((s0, -half), (s1, -half), (s1, half), (s0, half))
        ring = [(ax + ux * s + px * t, ay + uy * s + py * t)
                for (s, t) in corners]
        return ring + [ring[0]]

    return [_rect(0.0, length, strip_half),
            _rect(-end_len, 0.0, end_half),
            _rect(length, length + end_len, end_half)]


def runway_end_envelope(
        distance_beyond_pavement_m: float,
        *,
        governed_length_beyond_pavement_m: float,
        entry_grade: float = 0.0,
        pavement_beyond_end_m: float = 0.0,
        resa_reach_m: Optional[float] = None,
) -> tuple[Optional[float], Optional[float]]:
    """THE lawful corridor for terrain BEYOND a runway end, as a signed
    ``(floor_offset_m, ceiling_offset_m)`` relative to the pavement-EXIT
    elevation (positive = above the exit), at ``d`` metres beyond that exit
    along the extended centreline.

    A terrain point is lawful iff ``floor_offset <= (point - exit) <=
    ceiling_offset``.  ``None`` means UNBOUNDED in that direction: a ``None``
    floor permits any drop (never filled), a ``None`` ceiling permits any rise
    (never cut).  This is the LONGITUDINAL twin of
    ``adjacent_ground_envelope`` and follows the same conventions, so the two
    can be read by one emitter and one validator.

    The two directions and why they differ in extent:

    * FLOOR (fill) — the runway-end skirt law, unchanged:
      ``runway_end_skirt_floor_profile_beyond_pavement`` inside the governed
      length, ``None`` past it (a drop beyond the safety area is lawful).
      ``entry_grade`` and ``pavement_beyond_end_m`` are that law's own
      arguments and keep their meaning verbatim.
    * CEILING (cut) — the RESA ramp: terrain may rise from the pavement-exit
      elevation at up to ``RUNWAY_END_RESA_MAX_SLOPE`` (ICAO Annex 14 §3.5.10
      caps RESA longitudinal slopes at 5 %), so an overrun meets a gentle
      ramp instead of a wall.  Bounded by ``resa_reach_m``
      (``CLEARANCE_MAX_REACH_M["runway"]`` by default — the earthwork safety
      cap the legacy Pass C used).

    NOTE on the ceiling's extent: the RESA proper ends at
    ``governed_length_beyond_pavement_m``; carrying the 5 % ramp on to the
    reach cap is a CONSERVATIVE REPO DESIGN CHOICE (legacy Pass C parity),
    not a regulatory mandate — the codified surface out there is the OLS
    transitional/approach surface, which the OLS arc (gap-audit GAP 1) will
    supersede this tail with.  Documented, like the service-road band, as a
    design value rather than a citation.

    Pure, deterministic, no geometry dependencies.  Both the emitter
    (``clearance.emit_runway_end_skirts``) and the reader
    (``verification.check_runway_end_skirt``) evaluate THIS function, so the
    surface we build and the surface we check cannot drift.
    """
    if resa_reach_m is None:
        resa_reach_m = CLEARANCE_MAX_REACH_M["runway"]
    d = float(distance_beyond_pavement_m)
    if d <= 0.0:
        return (0.0, 0.0)                       # flush at the pavement exit

    floor: Optional[float] = None
    if d <= float(governed_length_beyond_pavement_m):
        depth = runway_end_skirt_floor_profile_beyond_pavement(
            [d], entry_grade, pavement_beyond_end_m)[0]
        floor = -depth

    ceiling: Optional[float] = None
    if d < float(resa_reach_m):
        ceiling = RUNWAY_END_RESA_MAX_SLOPE * d

    return (floor, ceiling)


# ── Adjacent-ground LATERAL grade law (Fable 2026-07-08) ─────────────────────
# The lateral generalization of the runway-END skirt: ground beside a paved
# surface is a two-zone-plus-ungraded CORRIDOR off the pavement EDGE.  The
# regulatory model, the four Noah rulings and the slice plan live in
# docs/adjacent_ground_grade_law_plan.md; the rule VALUES live in config.py
# (single source).  Only the zone MATH — accumulated so the corridor bounds are
# CONTINUOUS functions of the distance d — lives here.
#
# Ruling 1 (ENFORCE FULLY): each graded zone is a mandatory-DOWN band with
# DIRECTION, so a FLAT surface (offset 0) is OUTSIDE the corridor within zones
# 1-2 (its ceiling is strictly below 0).  This is what lets the emitter regrade
# flat surrounds to the lawful drainage slope, and it is the boundary-bridge
# killer: zone-3's floor is UNBOUNDED down, so a cliff beyond the graded band
# renders as DEM (never force-filled).

# Role → strip FAMILY.  Runway ENDS are NOT a family here (the skirt law owns
# them); "runway"/"runway_crossing" mean the LATERAL runway strip.
_ADJACENT_RUNWAY_ROLES = frozenset({"runway", "runway_crossing"})
_ADJACENT_APRON_ROLES = frozenset({"apron", "stand", "terminal"})
_ADJACENT_SERVICE_ROLES = frozenset({"service_road", "service_junction"})
_ADJACENT_TAXIWAY_ROLES = frozenset({
    "taxiway", "primary_parallel", "secondary_parallel", "stub",
    "cross_connector", "junction",
})


def _adjacent_strip_envelope(
        graded_half_width_m: float, band_min_down: float,
        band_max_down: float, reach_m: float,
        distance_m: float) -> tuple[Optional[float], Optional[float]]:
    """The shared runway/taxiway two-zone-plus-ungraded corridor, given the
    family's graded WIDTH, its zone-2 min/max DOWN slopes and its outward reach.

    Returns ``(floor_offset, ceiling_offset)`` in metres relative to the
    pavement-edge elevation (positive = above the edge).  The bounds ACCUMULATE
    across zone boundaries so they are continuous in ``distance_m``:

      * Zone 1 (0 .. lip): mandatory-down lip 3-5 %.
          ceiling = -lip_min_down · d ,  floor = -lip_max_down · d
      * Zone 2 (lip .. W): mandatory-down graded band, continuing from the lip's
        endpoint values (NOT restarted at 0):
          ceiling = ceiling(lip) - band_min_down · (d - lip)
          floor   = floor(lip)   - band_max_down · (d - lip)
      * Zone 3 (W .. reach): ungraded strip — ceiling continues UP at ≤5 % from
        the band's endpoint ceiling, floor = None (cliffs lawful).
      * d ≥ reach: (None, None) — ungoverned (OLS territory / earthwork bound).
    """
    lip = ADJACENT_GROUND_LIP_WIDTH_M
    lip_min = ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE
    lip_max = ADJACENT_GROUND_LIP_MAX_DOWN_SLOPE
    if distance_m <= 0.0:
        return (0.0, 0.0)                       # flush at the edge
    if distance_m >= reach_m:
        return (None, None)
    if distance_m <= lip:                       # ZONE 1 — drainage lip
        return (-lip_max * distance_m, -lip_min * distance_m)
    lip_ceiling = -lip_min * lip
    lip_floor = -lip_max * lip
    if distance_m <= graded_half_width_m:       # ZONE 2 — graded band
        ceiling = lip_ceiling - band_min_down * (distance_m - lip)
        floor = lip_floor - band_max_down * (distance_m - lip)
        return (floor, ceiling)
    band_ceiling = lip_ceiling - band_min_down * (graded_half_width_m - lip)
    up = ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE
    ceiling = band_ceiling + up * (distance_m - graded_half_width_m)  # ZONE 3
    return (None, ceiling)


def adjacent_ground_envelope(
        role: str, code_number: Optional[int], code_letter: Optional[str],
        distance_from_pavement_edge_m: float,
) -> tuple[Optional[float], Optional[float]]:
    """THE lawful corridor for ground adjacent to a paved surface, as a signed
    ``(floor_offset_m, ceiling_offset_m)`` relative to the pavement-EDGE
    elevation (positive = above the edge), at lateral distance
    ``distance_from_pavement_edge_m`` (``d``) out from the edge.

    A terrain point is lawful iff ``floor_offset ≤ (point − edge) ≤ ceiling``.
    ``None`` for a bound means UNBOUNDED in that direction: a ``None`` ceiling
    permits any rise (never cut here); a ``None`` floor permits any drop (never
    filled — a cliff is lawful).

    The corridor is the two-zone-plus-ungraded profile of
    docs/adjacent_ground_grade_law_plan.md, ENFORCED FULLY (ruling 1) as
    mandatory-DOWN graded bands, so within zones 1-2 the ceiling is strictly
    below 0 and a FLAT surround (offset 0) is OUTSIDE the corridor — the emitter
    regrades it to the lawful drainage slope.  All bounds ACCUMULATE across zone
    boundaries, so both are CONTINUOUS functions of ``d`` (no step at the lip
    edge or the band edge; the floor's finite→None transition at the band edge
    only OPENS the corridor downward).  Pure, deterministic, no geometry deps.

    Roles:
      * runway / runway_crossing — LATERAL runway strip.  Keyed by ICAO code
        NUMBER (ruling 2): graded WIDTH = ``RUNWAY_STRIP_HALF_WIDTH_BY_CODE``;
        band down-cap 3 % (code 3/4 ≈ AAC C-E) / 5 % (code 1/2 ≈ AAC A/B),
        min 1.5 % (FAA RSA minimum).  ``code_letter`` is ignored.
      * taxiway family (taxiway, parallels, stub, cross_connector, junction) —
        taxiway strip.  Keyed by ICAO code LETTER (ruling 2): graded WIDTH =
        OMGWS table (``taxiway_strip_graded_half_width_for_letter``); band down
        1.5-5 %.  ``code_number`` is ignored.
      * apron family (apron, stand, terminal) — a 3 m FAA-recommended shoulder
        (1-3 % down), then zone-3 semantics immediately (ceiling ≤5 % up, floor
        free).  Both code args ignored.  The retaining-wall face for a deep drop
        (``APRON_EDGE_WALL_MIN_DROP_M``) is the emitter's job (slice 3).
      * service_road / service_junction — UNCHANGED 15 m cut-only flat shadow
        (ceiling 0 out to ``CLEARANCE_MAX_REACH_M["service"]``, floor free): a
        conservative design choice EXCEEDING the AASHTO 2-3 m low-speed clear
        zone (documented in docs/STANDARDS.md), not a regulatory mandate.

    Runway ENDS are explicitly OUT OF SCOPE: the longitudinal runway-end skirt
    law (``runway_end_skirt_floor_profile`` / ``runway_end_governed_length_m``)
    owns terrain beyond a runway end.  This function is the LATERAL law only.

    Raises ``ValueError`` for an unrecognised role (a law must not silently pick
    a corridor for a surface it does not model).
    """
    d = distance_from_pavement_edge_m
    if role in _ADJACENT_RUNWAY_ROLES:
        if code_number is None:
            raise ValueError("runway adjacent-ground envelope needs code_number")
        return _adjacent_strip_envelope(
            RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code_number],
            RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE,
            RUNWAY_STRIP_BAND_MAX_DOWN_SLOPE_BY_CODE[code_number],
            CLEARANCE_MAX_REACH_M["runway"], d)
    if role in _ADJACENT_TAXIWAY_ROLES:
        return _adjacent_strip_envelope(
            taxiway_strip_graded_half_width_for_letter(code_letter),
            TAXIWAY_STRIP_BAND_MIN_DOWN_SLOPE,
            TAXIWAY_STRIP_BAND_MAX_DOWN_SLOPE,
            CLEARANCE_MAX_REACH_M["taxiway"], d)
    if role in _ADJACENT_APRON_ROLES:
        # Aprons ride the maneuvering-network reach (taxiway); the only governed
        # band is the 3 m shoulder, then zone-3 semantics immediately.
        reach = CLEARANCE_MAX_REACH_M["taxiway"]
        if d <= 0.0:
            return (0.0, 0.0)
        if d >= reach:
            return (None, None)
        if d <= APRON_SHOULDER_WIDTH_M:
            return (-APRON_SHOULDER_MAX_DOWN_SLOPE * d,
                    -APRON_SHOULDER_MIN_DOWN_SLOPE * d)
        shoulder_ceiling = -APRON_SHOULDER_MIN_DOWN_SLOPE * APRON_SHOULDER_WIDTH_M
        up = ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE
        return (None, shoulder_ceiling + up * (d - APRON_SHOULDER_WIDTH_M))
    if role in _ADJACENT_SERVICE_ROLES:
        # UNCHANGED cut-only flat shadow: cut anything above the edge within the
        # 15 m band, never fill (floor free).  CLEARANCE_LATERAL_MAX_SLOPE == 0
        # ⇒ the ceiling stays at the edge level across the whole band.
        if d >= CLEARANCE_MAX_REACH_M["service"]:
            return (None, None)
        return (None, CLEARANCE_LATERAL_MAX_SLOPE * d)
    raise ValueError(f"adjacent_ground_envelope: unmodelled role {role!r}")


def drainage_spine_envelope(
        role: str, code_number: Optional[int], code_letter: Optional[str],
        distance_from_pavement_edge_m: float,
) -> tuple[Optional[float], Optional[float]]:
    """THE lawful corridor for the DRAINAGE SPINE of an ENCLOSED interior,
    as a signed ``(floor_offset_m, ceiling_offset_m)`` relative to ONE
    bounding pavement's EDGE elevation — the enclosed-interior variant of
    :func:`adjacent_ground_envelope` (owner field report 2026-08-02: the
    spine must run BELOW the lower adjacent pavement).

    Two deltas over the lateral corridor, and only two:

      * the CEILING is tightened to at most ``-DRAINAGE_SPINE_MIN_FALL_M``.
        Ground enclosed between two pavements drains INTO the spine, so a
        spine at or above either bounding edge is a dam.  The lateral
        corridor cannot express that on its own: beyond the graded
        half-width its zone-3 ceiling RISES at +5 %/m away from the edge
        (``ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE``), which is correct
        for open terrain — a hill outside the strip is lawful — and wrong
        for an interior whose only outlet is the spine.
      * the FLOOR is the lateral corridor's, UNCHANGED.  It is the crater
        guard: the spine may not sink below the ground the lateral law
        supports.  Where that floor is ``None`` (zone 3 and beyond) the
        corridor is genuinely open downward and this function says so
        rather than inventing a depth.

    Expressed PER PARENT as an offset — which is what makes it one law with
    two readers.  ``gap_fill._spine_interval`` composes it analytically as
    ``hi = min over parents (edge_i + ceil_off_i)``, i.e. exactly
    ``min(edge₁, edge₂) − FALL``; ``gap_fill._freeze_spine_parent_specs``
    hands the SAME tightened offset to the solver's pairwise slab.  No
    second selection, no second geometry.

    A conflicting pair (a floor already above the drainage ceiling, which
    the lateral law can produce inside zone 1's steep lip) collapses to a
    PINNED value at the ceiling: drainage is the binding clause there, and
    an empty interval would send the caller down its
    empty-intersection fallback for a reason that is not a contradiction
    between the two parents.
    """
    floor_off, ceil_off = adjacent_ground_envelope(
        role, code_number, code_letter, distance_from_pavement_edge_m)
    fall = -float(DRAINAGE_SPINE_MIN_FALL_M)
    ceil_off = fall if ceil_off is None else min(float(ceil_off), fall)
    if floor_off is not None and float(floor_off) > ceil_off:
        floor_off = ceil_off
    return floor_off, ceil_off


# THE bounding-parent set of a drainage spine station — the SELECTION half
# of the drainage law (field-report round residual, 2026-08-02).  The
# offsets above were already one law with two readers, but each reader
# CHOSE its own parents: the emitter from an exact two-nearest index over
# the airside shapes, the validator from a grid walk that stopped at the
# first cell ring holding two distinct ways.  Measured at HECA: the
# validator's second parent sat 91.96 m away while the true second parent
# was 67.32 m — the spine read 0.47 m ABOVE its "lower" edge where against
# its real parents it is 0.38 m BELOW.  Same law, different population —
# so the SELECTION moves into the law too, and both readers hand it their
# own candidates and get the same answer by construction.
DRAINAGE_SPINE_PARENT_ROLES = frozenset({
    "runway", "runway_crossing", "primary_parallel", "secondary_parallel",
    "stub", "cross_connector", "junction", "apron",
})
DRAINAGE_SPINE_MAX_PARENTS = 2


def drainage_spine_parents(candidates, max_parents=DRAINAGE_SPINE_MAX_PARENTS):
    """THE bounding parents of one drainage-spine station.

    ``candidates`` is an iterable of ``(distance_m, tie_key, payload)`` over
    pavement shapes of ``DRAINAGE_SPINE_PARENT_ROLES`` whose distance is
    measured to the shape's EXTERIOR RING.  Rules:

      * one entry per DISTINCT parent — a reader that can offer the same
        parent twice (per-edge candidates) keeps only its nearest;
      * ranked on ``(distance, tie_key)`` — tie order is load-bearing, the
        NEARER parent owns the empty-intersection fallback downstream, so
        two parents at equal distance must rank the same way for both
        readers.  ``tie_key`` is the reader's own stable ordering key
        (the emitter's airside index, the validator's way id);
      * at most ``max_parents``.

    Returns ``[(distance_m, tie_key, payload), …]``, nearest first.  The
    caller is responsible for offering a candidate set that CONTAINS the
    true nearest parents — a truncated search is the defect this function
    exists to make impossible to hide.
    """
    best: dict = {}
    for distance_m, tie_key, payload in candidates:
        cur = best.get(tie_key)
        if cur is None or distance_m < cur[0]:
            best[tie_key] = (float(distance_m), tie_key, payload)
    ranked = sorted(best.values(), key=lambda r: (r[0], r[1]))
    return ranked[:max_parents]


# ═══════════════════════════════════════════════════════════════════════════
# LATERAL-CONTIGUITY GRADE LAW (owner-confirmed FINAL, 2026-08-02 —
# docs/RULINGS.md "service-road absorption")
# ═══════════════════════════════════════════════════════════════════════════
# Owner, verbatim clauses:
#   (1) A FREE road — road-width, genuinely unpaved ground on BOTH sides (any
#       real gap counts, however thin; adjacency = literal shared boundary in
#       the sliced arrangement, NEVER proximity) — takes the service-road cap
#       with axial route grading.  [``groundside.free_road_subsegments`` is
#       that clause's emitter: only free sub-segments reach the slice.]
#   (2) At any STATION, the laterally-contiguous paved CROSS-SECTION
#       (side-sharing closure across any number of touching pavements) takes
#       the STRICTEST cap of any class present in it.  The closure NEVER
#       propagates through end-connections/mouths — a road resumes its own cap
#       the moment it leaves lateral contact.
#   (3) Segmentation is per-segment, via the existing mouth-cut machinery.
#   (4) Implementation SHOULD fully ABSORB laterally-contiguous road stretches
#       into the adjacent surface (merge, fewer nodes) rather than carry
#       separate shapes with cap overrides.
#   (5) The runway-strip footprint law SUPERSEDES inside strips.
#
# The station cross-section is what makes clause (2) local and well defined: a
# shape-level "touching" closure would sweep a dense airport into one component
# (every apron touches a junction touches a taxiway) and collapse the whole
# airfield to the strictest cap present anywhere.  The cross-section is taken
# PERPENDICULAR to the road at the station and stops at the first real gap, so
# a road DYING INTO an apron (an end connection) never sees it — the apron is
# ahead of the station, not beside it.

# Cap per pavement class, for the closure.  Keyed on the emitted ROLE and
# sourced from ``ROLE_GRADE_LIMITS`` so there is no second copy of a rule
# number; roles with no within-shape cap (``None``: boundary, walls, clearance
# cuts, graded strips) are not pavement classes and never enter the closure.
LATERAL_CONTIGUITY_ROAD_ROLES = frozenset({"service_road", "service_junction"})


def lateral_contiguity_cap(roles) -> Optional[float]:
    """Clause (2): the cap of a laterally-contiguous paved cross-section —
    the STRICTEST (smallest) within-shape cap of any class present in it.

    ``roles`` is the set of emitted roles the cross-section run passes
    through, INCLUDING the road's own.  Roles carrying no within-shape cap
    are ignored (they are not pavement classes).  Returns ``None`` when no
    class in the run is regulated.
    """
    caps = [ROLE_GRADE_LIMITS.get(r) for r in set(roles)]
    caps = [c for c in caps if c is not None]
    return min(caps) if caps else None


def lateral_contiguity_segments(station_caps):
    """Clause (3): group per-station caps into maximal RUNS of equal cap.

    ``station_caps`` is the ordered list of ``lateral_contiguity_cap``
    answers along a road's axis (``None`` for a station with no verdict —
    off the shape, inside a runway strip, or an unmeasurable cross-section;
    those break a run, they never join one).

    Returns ``[(i_first, i_last, cap), …]`` over the stations that HAVE a
    cap, in order.  This is the segmentation the mouth cuts are made at: a
    road that leaves lateral contact starts a new run at that station, which
    is exactly "a road resumes its own cap the moment it leaves lateral
    contact".
    """
    runs = []
    start = None
    cur = None
    for i, cap in enumerate(list(station_caps) + [None]):
        if cap is not None and cur is not None and cap == cur:
            continue
        if cur is not None:
            runs.append((start, i - 1, cur))
        start, cur = (i, cap) if cap is not None else (None, None)
    return runs


# ── Adjacent-ground DAYLIGHT slope-limit law (user 2026-07-09) ───────────────
# The obstruction scan of the adjacent-ground emitter marches each 5 m station
# outward INDEPENDENTLY: ``outer[i]`` is the furthest lateral distance at which
# the DEM breaches the corridor for that one station.  Nothing couples the
# stations, so one or two stations can lawfully march ~156 m to a terrain
# violation NO neighbouring station corroborates — an ISOLATED DEEP RAY,
# rendered as a 156 m × 7 m blade cutting a knife slot into terrain (CYXY
# shapeID 417, user in-sim report 2026-07-09).  Physical grading BENCHES into a
# hillside: the daylight line (where the graded surface meets terrain) is a
# continuous curve along the frontage — it cannot step discontinuously from one
# station to the next.  This law couples the per-station depths so the emitted
# daylight line obeys that continuity, and — being defined ONCE here — is
# consumed by BOTH the emitter (which clamps ``outer[]`` before laying bands)
# and the validator (which exempts columns beyond the supported depth), in
# lockstep.
def adjacent_ground_supported_depths(depths, positions,
                                     at_continuation_seam=None):
    """Slope-limit the per-station adjacent-ground daylight ``depths`` so the
    daylight line benches along the frontage instead of jumping.

    THE LAW: a station's governed (daylight) depth may exceed a neighbour's by
    at most ``ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT`` times the ALONG-FRONTAGE
    distance between them.  Two symmetric passes enforce it:

        forward   d[i] = min(d[i], d[i-1] + LIMIT * dist(p[i-1], p[i]))
        backward  d[i] = min(d[i], d[i+1] + LIMIT * dist(p[i+1], p[i]))

    ``depths`` are the raw per-station governed depths (metres, 0.0 where the
    station is unobstructed); ``positions`` are the matching per-station
    ``(x, y)`` (same length, same order).  Returns a new list of the limited
    depths (the input is never mutated).

    THE BLADE CLASS IT KILLS: an isolated ray at ~156 m among 0-depth
    neighbours 5 m away is clamped to ``LIMIT * 5 m`` (≈ 10 m at LIMIT = 2) —
    a shallow bench, not a knife slot.  DISTANCE WEIGHTING is deliberate: a
    corner-fan inserts extra stations that all SHARE the corner coordinate
    (dist = 0), so a fan ray gets NO extra allowance over the corner's own
    depth — a fan sweeping toward an unobstructed flank is suppressed to that
    flank's depth (the CYXY 417 fan-blade class).

    TAPER-IN AT RUN BOUNDARIES: a genuine abrupt ridge (a real deep violation
    with truly shallow neighbours) is not erased — it is given a BENCHED ENTRY,
    the depth ramping in at the slope limit from each side.  That is the
    desired physical behaviour (you cannot bench a full cut in one station);
    the ridge is still cut, just entered on a grade.

    SEAM-AWARE (user 2026-07-10, cross-shape run-end taper): a run boundary
    that exists ONLY because of the pavement PARTITION — one airside shape's
    terrain-facing frontage ends at a corner it shares with an abutting airside
    shape whose frontage CONTINUES the graded run — must NOT bench in.  Left
    alone, the terminal station of the ending shape is pulled inward toward its
    own locally-unobstructed neighbour while the abutting shape's band stands at
    full depth, and the two terminal stations (a fraction of a metre apart
    across the seam) form an inward outer-edge NOTCH — a lawful-value but
    artefact jog that mints a post-weld T-junction (CYXY seam dips
    60.7203854,-135.0788903 / 60.7208756,-135.0791845).  ``at_continuation_seam``
    (per-station, aligned with ``depths``; None = off, every station benched
    as before) marks the terminal stations that sit at such a continuation
    seam; a marked station is NEVER lowered by either sweep, so it holds its
    raw scanned depth and BOTH abutting shapes' terminal stations agree on
    outer depth (they read the SAME terrain across the seam).  The marked deep
    station still SUPPORTS its interior neighbours (its high depth is the seed
    the sweeps ramp down from), so the daylight line stays continuous into the
    shape.  At a TRUE frontage end — no abutting airside continuation — no
    station is marked and the bench-in is exactly the daylight law above.

    LOCKSTEP (mandatory): the validator ``verification.check_adjacent_ground``
    flags any un-covered corridor breach, so an emitter-only clamp would leave
    the clamped-away deep columns still breaching and mint findings.  Both
    readers therefore call THIS function over the SAME station sequence — the
    emitter to bound the bands it lays, the validator to treat columns beyond
    the supported depth as EXEMPT.
    """
    limit = ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT
    n = len(depths)
    supported = [float(d) for d in depths]

    def _pinned(i):
        return (at_continuation_seam is not None
                and i < len(at_continuation_seam)
                and bool(at_continuation_seam[i]))

    for i in range(1, n):
        if _pinned(i):
            continue        # continuation seam: hold the raw scanned depth
        (ax, ay), (bx, by) = positions[i - 1], positions[i]
        span = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        supported[i] = min(supported[i], supported[i - 1] + limit * span)
    for i in range(n - 2, -1, -1):
        if _pinned(i):
            continue
        (ax, ay), (bx, by) = positions[i + 1], positions[i]
        span = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        supported[i] = min(supported[i], supported[i + 1] + limit * span)
    return supported


def adjacent_ground_end_pin_flags(end_skipped, usable) -> list[bool]:
    """Stations the daylight bench must NOT lower because their zero-depth
    neighbour is a runway END-edge station (arc A3, gate
    ``ADJACENT_GROUND_END_PIN_ENABLED``).

    ``adjacent_ground_supported_depths`` benches a station's depth down toward
    any neighbour at depth 0.  That is right when the neighbour is genuinely
    unobstructed — you cannot cut a full-depth slot beside lawful ground — but
    WRONG at a runway end: those stations are at depth 0 only because the
    march SKIPS them (their outward normal points along the runway axis; the
    end is skirt/RESA territory, ``adjacent_ground._station_reference``).  The
    band then collapses diagonally into the end corner instead of ending
    square against the end regime (measured SPJC 16R 2026-07-24: band #702's
    outer edge tracks ``2.0 x distance-back-from-corner`` exactly, from 75 m
    depth to 3 m over the last 48 m).

    A station is pinned when it is usable AND immediately adjacent to an
    end-skipped station.  Pinned stations hold their raw scanned depth in
    BOTH bench sweeps (the ``at_continuation_seam`` mechanism, whose semantics
    this reuses verbatim), so the wing terminates at full lawful depth and
    hands off to the skirt / RESA surfaces, which clip and weld it.

    ``end_skipped`` and ``usable`` are per-station bools aligned with the
    march's station list.  Returns a per-station bool list.  Pure — the
    emitter (``adjacent_ground._derive_shape_stations_and_bands``) and the
    validator (``verification.check_adjacent_ground``) both call THIS, so the
    pin set cannot drift between them.
    """
    n = len(end_skipped)
    flags = [False] * n
    for i in range(n):
        if i < len(usable) and not usable[i]:
            continue
        if ((i > 0 and end_skipped[i - 1])
                or (i + 1 < n and end_skipped[i + 1])):
            flags[i] = True
    return flags


def runway_strip_band_width_m(strip_half_width_m: float,
                              distance_to_axis_m: Optional[float],
                              band_cap_m: float) -> float:
    """Lateral band width (m) available to a runway-family station at
    ``distance_to_axis_m`` from the runway CENTERLINE (arc A4, gate
    ``STRIP_WIDTH_FROM_CENTERLINE_ENABLED``).

    ``RUNWAY_STRIP_HALF_WIDTH_BY_CODE`` is an Annex-14 half-width measured
    from the centreline, but the adjacent-ground march spends it as a reach
    from the pavement EDGE — and the emitted runway carries apt.dat shoulders
    (SPJC 16R/34L 45 m -> 81 m), so the band lands 115.5 m from the centreline
    where the strip is 75 m.  Both legacy passes clamped this correctly:
    Pass A3 by ``rw_axis[2] - rw_axis[0].distance(station)``
    (``clearance.py`` Pass A3 station loop) and Pass B by
    ``clear_half - 0.5 * short_len``.  The lateral law inherited neither.

    Returns the remaining strip width outward of the station, never above
    ``band_cap_m``.  ``distance_to_axis_m`` ``None`` (no axis available)
    returns ``band_cap_m`` unchanged, so the clamp is inert without geometry.
    """
    if distance_to_axis_m is None:
        return float(band_cap_m)
    return max(0.0, min(float(band_cap_m),
                        float(strip_half_width_m) - float(distance_to_axis_m)))


# ── Obstacle limitation surfaces — the CUT law (Fable 2026-07-24) ────────────
# docs/specs/obstacle-limitation-surfaces-spec.md; gap-audit GAP 1.  The ruled
# follow-on of the lateral law above: zone 3's ceiling hands over to the OLS
# TRANSITIONAL surface, and terrain beyond a runway end is governed by the
# APPROACH surface's first section.  Rule VALUES live in config.py (single
# source); only the surface MATH lives here.  Cut-only — there is NO floor
# anywhere in this law: an OLS bounds how high terrain may stand, never how
# low it may fall.
#
# Both surfaces are ceilings expressed as signed offsets, exactly like
# ``adjacent_ground_envelope``'s: positive is above the anchor, ``None`` means
# "not this law's domain here" (inside the adjacent-ground corridor, outside
# the approach splay, or beyond the emission reach).
def _ols_is_instrument(approach_class: str) -> bool:
    """Annex 14 treats non-instrument (visual) runways separately from
    instrument ones for BOTH the strip width and the transitional slope."""
    return approach_class in ("non_precision", "precision")


def ols_strip_half_width_m(code_number: int, approach_class: str) -> float:
    """OLS strip half-width (m) from the runway CENTERLINE — the line the
    transitional surface rises from (Annex 14 §3.4.3-3.4.4).

    This is the FULL strip, NOT the graded portion the adjacent-ground law
    models: instrument runways 140 m (code 3/4) / 70 m (code 1/2); a
    non-instrument runway's OLS strip and its graded strip are the same width
    (§3.4.4 == §3.4.9), so that case REUSES
    ``RUNWAY_STRIP_HALF_WIDTH_BY_CODE`` rather than keeping a second copy.
    """
    if _ols_is_instrument(approach_class):
        return float(OLS_STRIP_HALF_WIDTH_INSTRUMENT_BY_CODE[code_number])
    return float(RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code_number])


def ols_transitional_slope(code_number: int, approach_class: str) -> float:
    """Transitional-surface slope: 1:7 (14.3 %) everywhere except
    non-instrument / non-precision code 1-2, which is 1:5 (20 %).
    Annex 14 Table 4-1."""
    if (code_number in (1, 2)
            and approach_class in ("visual", "non_precision")):
        return OLS_TRANSITIONAL_SLOPE_STEEP
    return OLS_TRANSITIONAL_SLOPE


def ols_lateral_handover_distance_m(code_number: int, approach_class: str,
                                    edge_to_centerline_m: float) -> float:
    """``S`` — the from-EDGE lateral distance at which the adjacent-ground
    law hands over to the OLS transitional surface.

    The transitional rises from the OLS strip EDGE, which is measured from the
    centreline; a station on a pavement edge ``edge_to_centerline_m`` off the
    axis therefore reaches it ``ols_half - edge_to_centerline`` further out.

    FLOORED at the graded band width so the transitional can never begin
    inside a still-graded zone 1-2.  That floor matters until arc A4
    (``STRIP_WIDTH_FROM_CENTERLINE_ENABLED``) lands: today the lateral march
    spends the graded half-width as a reach from the pavement EDGE, so on a
    shoulder-widened runway the graded band already extends past the OLS strip
    edge.  Without the floor the two laws would overlap and the composed
    ceiling would step.  With A4 on, the floor stops binding on its own.
    """
    ols_half = ols_strip_half_width_m(code_number, approach_class)
    graded = float(RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code_number])
    return max(ols_half - float(edge_to_centerline_m), graded)


def ols_transitional_ceiling(
        code_number: int, approach_class: str,
        distance_from_pavement_edge_m: float,
        edge_to_centerline_m: float) -> Optional[float]:
    """Ceiling offset (m) relative to the pavement-EDGE elevation, at lateral
    distance ``d`` out from that edge, for the OLS transitional surface.

    ``None`` inside the handover ``S`` (the adjacent-ground corridor owns that
    ground) and at/beyond ``S + OLS_TRANSITIONAL_EMIT_REACH_M``.

    CONTINUITY (the design's central ruling): the transitional is anchored on
    the value the adjacent-ground zone-3 ceiling ALREADY has at ``S``, read
    from the same ``_adjacent_strip_envelope`` helper the lateral law uses —
    so the composed ceiling
    ``zones 1-2 -> zone-3 +5 % on [W, S] -> transitional from C(S)``
    is continuous in ``d`` by construction, with only an upward slope kink at
    ``S``.  A discontinuity here would mint a wall between two active cut
    bands, which is exactly the class the 2026-07-09 weld ruling exists to
    prevent.

    This anchor sits up to ~2 m BELOW the Annex datum (which references the
    nearest centreline elevation, not the pavement edge, so it does not carry
    the accumulated zone-1/2 down-offsets).  Lower = stricter = a
    lawful-conservative cut.  The two rejected alternatives — anchoring at the
    300 m reach cap, or at the true Annex datum — are argued in the spec.
    """
    d = float(distance_from_pavement_edge_m)
    s = ols_lateral_handover_distance_m(
        code_number, approach_class, edge_to_centerline_m)
    if d < s or d >= s + OLS_TRANSITIONAL_EMIT_REACH_M:
        return None
    # Zone-3 ceiling value AT the handover, from the lateral law itself.
    # ``reach`` is passed as s + 1 so the helper never short-circuits to
    # (None, None) at its own reach cap — we want the zone-3 expression
    # evaluated at s, not the "ungoverned" answer.
    _floor_at_s, ceiling_at_s = _adjacent_strip_envelope(
        RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code_number],
        RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE,
        RUNWAY_STRIP_BAND_MAX_DOWN_SLOPE_BY_CODE[code_number],
        s + 1.0, s)
    if ceiling_at_s is None:            # s <= 0 (degenerate geometry)
        return None
    slope = ols_transitional_slope(code_number, approach_class)
    return float(ceiling_at_s) + slope * (d - s)


def ols_approach_ceiling(
        code_number: int, approach_class: str,
        distance_beyond_runway_end_m: float,
        offset_from_extended_centerline_m: float) -> Optional[float]:
    """Ceiling offset (m) relative to the RUNWAY-END elevation, for the
    approach surface's FIRST SECTION off one runway end.

    ``None`` when the point is inside the setback (the inner edge sits
    30 m past a non-instrument code-1 end, 60 m otherwise), outside the
    splayed fan, or beyond ``OLS_APPROACH_EMIT_REACH_M`` past the inner edge.

    The fan half-width grows from the inner-edge half-width at the divergence
    rate; the surface is FLAT transversely (Annex 14 measures approach slopes
    in the vertical plane containing the centreline), so the ceiling depends
    on the along-track distance alone once the point is inside the fan.

    ANCHOR: the SOLVED runway-end elevation — the surface the patch actually
    renders, matching the skirt/RESA anchor discipline rather than the
    published threshold elevation.  Annex 14 puts the inner edge at the
    THRESHOLD; where a threshold is displaced inward our inner edge sits
    farther out along the same rising surface, so our ceiling is lower than
    the Annex's — strictly conservative, never permissive.
    """
    setback = (OLS_APPROACH_SETBACK_VISUAL_CODE1_M
               if (approach_class == "visual" and code_number == 1)
               else OLS_APPROACH_SETBACK_M)
    s = float(distance_beyond_runway_end_m) - setback
    if s <= 0.0 or s > OLS_APPROACH_EMIT_REACH_M:
        return None
    inner_half = float(
        OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M[approach_class][code_number])
    half_at_s = inner_half + OLS_APPROACH_DIVERGENCE[approach_class] * s
    if abs(float(offset_from_extended_centerline_m)) > half_at_s:
        return None
    return OLS_APPROACH_FIRST_SECTION_SLOPE[approach_class][code_number] * s


def eat_pavement_ceiling(D_m: float, slope: float, setback_m: float,
                         tail_height_m: float) -> float:
    """Ceiling offset (m) relative to the RUNWAY-END elevation for
    END-AROUND TAXIWAY pavement at ``D_m`` beyond that end.

    An end-around taxiway crosses the extended centreline beyond a runway
    end, so the tallest aircraft using it stands under the departure /
    take-off-climb surface.  The surface itself sits at
    ``max(0, D − setback) · slope`` above the runway end; the PAVEMENT
    must sit a whole tail height below that, because it is the tail —
    not the wingtip — that penetrates::

        ceiling(D) = max(0, D − setback) · slope − tail_height

    The result is normally NEGATIVE (the pavement is below the runway
    end) and is deliberately NOT clamped at 0: that depression is the
    entire point of the law (KATL taxiway Victor ≈ −9 m).  Only the
    surface's own rise is floored at 0, so a point inside the setback
    reads the inner-edge height rather than a fictitious below-DER
    surface.

    The sibling of ``ols_approach_ceiling``: same anchor discipline (the
    SOLVED runway-end elevation, matching the skirt / RESA / approach
    readers), same "offset relative to the end" contract.  Unlike the OLS
    ceilings this one governs PAVEMENT, not terrain — it is the one place
    where a runway-end surface binds the taxiway network.

    No rule number lives here: ``slope``/``setback_m`` come from
    ``config.eat_surface_slope_and_setback`` (FAA vs EASA by region) and
    ``tail_height_m`` from ``config.TAIL_HEIGHT_BY_CODE_LETTER``.
    """
    rise = max(0.0, float(D_m) - float(setback_m)) * float(slope)
    return rise - float(tail_height_m)


def ols_island_refused(max_cut_depth_m: float) -> bool:
    """Whether a contiguous penetration ISLAND is refused whole.

    Cutting the fringe of a real mountain while leaving its core sculpts a
    moat, and the charter here is DEM-artefact repair (5-15 m lumps), not
    obstacle removal — real aerodromes in terrain operate with assessed OLS
    penetrations and the scenery must keep the mountains.  So an island whose
    deepest required cut exceeds ``OLS_MAX_CUT_DEPTH_M`` emits NOTHING.

    Emitter and validator both call this, so a refused island is exempt in the
    reader for exactly the reason it was skipped in the emitter (the
    ``adjacent_ground_supported_depths`` lockstep pattern).
    """
    return float(max_cut_depth_m) > OLS_MAX_CUT_DEPTH_M


# ── Spine crown offset (user 2026-07-07, part 30) ────────────────────────────
# Crowned pavement is a DESIGNED sub-cap offset: every node carries a crown
# drop c ≥ 0 (``crown.build_crown_drop_field`` — the ONE field; runways get a
# uniform per-piece drop stamped at profile evaluation), and a pair's grade
# budget re-centres on the crown target:
#
#     |Δz − crown_pair_offset(c_a, c_b)| ≤ Allowance.at(Δs∥, Δs⊥)
#
# Both readers evaluate this with the SAME field: the SOLVER by running in
# uncrowned space z′ = z + c (its writeback subtracts c — mathematically
# identical to offset edges, and single-valued per canonical node so welds
# can never tear), the VALIDATOR by reading the field from the axes sidecar
# (``crown_drops``) / ``layout._crown_drop_key`` and re-centring here.  Since
# every crown rate ≤ every transverse cap (1 % ≤ 1.5 %, service 1.5 % ≤ 2 %),
# the re-centred band always still contains the FLAT surface — the offset can
# only restore budget the crown consumed, never flag an uncrowned patch.
def crown_pair_offset(drop_a: float, drop_b: float) -> float:
    """THE crown target of ``z_a − z_b`` for a pair whose endpoints carry
    crown drops ``drop_a`` / ``drop_b`` (0 when unknown/uncrowned)."""
    return (drop_b or 0.0) - (drop_a or 0.0)


# ── Runway within-shape LATERAL scoping (user 2026-07-08) ────────────────────
# A de-segmented runway (``O4_RUNWAY_SINGLE_POLY``, default on) emits ONE polygon
# ring per ref whose FAA profile stations live as interior LONG-EDGE vertices.
# The within-shape all-pair grade check on that ring conflates two DISTINCT laws:
#   * LATERAL — the within-shape check's real domain (cross-section crown / edge
#     roll), measured by SAME-station and ADJACENT-station pairs; and
#   * LONGITUDINAL — owned by the FAA profile law (``check_runway_profile``,
#     ring-aware since ff332e9, + the spine-profile check), measured by a pair
#     spanning 2+ station intervals.
# A multi-station chord IS an at-cap longitudinal grade the profile law already
# governs; counting it in the within-shape all-pair domain double-books it
# against a check with no jurisdiction there (SPLP 02/20: ≤+0.11 % at-cap chords
# spanning stations pushed within 18→31).  So a runway-ring vertex pair is IN the
# within-shape domain iff its endpoints are same- or adjacent-station:
# ``|station_index_a − station_index_b| <= 1``.  This extends the part-30i
# crown-centerline exemption (the crown ridge is the profile's domain; so is the
# whole longitudinal profile).  Stations cluster the ring's OWN vertices along the
# ref axis at ``RUNWAY_STATION_CLUSTER_M`` — the SAME 5.0 m convention
# ``verification._runway_single_poly_cross_stations`` uses to reconstruct the
# profile, so the LATERAL within-shape domain and the LONGITUDINAL profile check
# agree on what a "station" is.
#
# LEGACY INVARIANCE BY CONSTRUCTION: a segmented 4-corner runway piece projects
# to exactly TWO extreme axis stations, so every pair is same- or adjacent-
# station and the scoping is a NO-OP (gate-off within unchanged).  A crowned
# sub-rect's inserted centerline vertex sits at the same station as its cross-edge
# corners, so it stays two stations too.
RUNWAY_STATION_CLUSTER_M = 5.0


def runway_axis_station_indices(ring):
    """Assign each vertex of a runway RING a longitudinal STATION index along the
    runway's ref axis.

    The ref axis is the ring's longest vertex pair (the runway diameter, origin
    at one end); every vertex projects to a station distance along it; a vertex
    more than ``RUNWAY_STATION_CLUSTER_M`` beyond the previous vertex in ascending
    station order opens a new cluster.  Returns a list ``station[i]`` parallel to
    ``ring`` (0 = the end at the axis origin, increasing along the axis), or
    ``None`` when the ring is degenerate (<2 vertices or a zero-length axis — no
    stations to scope by, so the caller keeps every pair).

    Same 5.0 m chained clustering as
    ``verification._runway_single_poly_cross_stations``: the lateral within-shape
    domain and the longitudinal profile check must agree on what a station is.  A
    legacy 4-corner runway piece has its corners at two extreme stations only, so
    it yields station indices in {0, 1} — the adjacency predicate below then
    passes every pair (no-op)."""
    n = len(ring)
    if n < 2:
        return None
    # Longest vertex pair = the runway ref axis (origin at A, unit direction A→B).
    best = -1.0
    ax = ay = bx = by = 0.0
    for i in range(n):
        xi, yi = ring[i]
        for j in range(i + 1, n):
            xj, yj = ring[j]
            d2 = (xj - xi) ** 2 + (yj - yi) ** 2
            if d2 > best:
                best, ax, ay, bx, by = d2, xi, yi, xj, yj
    if best <= 0.0:
        return None
    length = best ** 0.5
    ux, uy = (bx - ax) / length, (by - ay) / length
    stations = [((ring[i][0] - ax) * ux + (ring[i][1] - ay) * uy)
                for i in range(n)]
    order = sorted(range(n), key=lambda i: stations[i])
    station_of = [0] * n
    cluster = 0
    previous = stations[order[0]]
    for k in range(1, n):
        i = order[k]
        if stations[i] - previous > RUNWAY_STATION_CLUSTER_M:
            cluster += 1
        station_of[i] = cluster
        previous = stations[i]
    return station_of


def runway_within_pair_in_domain(station_a: int, station_b: int) -> bool:
    """A runway RING vertex pair is in the WITHIN-SHAPE (lateral) grade domain
    iff its endpoints are the SAME station or ADJACENT stations
    (``|Δ station index| <= 1``).  A pair spanning 2+ station intervals is a
    LONGITUDINAL grade the FAA profile law owns (``check_runway_profile`` + the
    spine-profile check), NOT the lateral within-shape check — counting it here
    double-books an at-cap longitudinal chord against a check with no
    jurisdiction over it (user ruling 2026-07-08; extends the part-30i
    crown-centerline exemption).  On a legacy 4-corner runway piece (two
    stations) every pair is same/adjacent → this is a no-op."""
    return abs(station_a - station_b) <= 1


# Pairs closer than this are ring/relative noise — not a grade constraint.
MIN_PAIR_DIST_M = 0.5

# Max length of an APRON interior body↔body grade chord: beyond this a chord
# across a wide apron is not a real grade path (each point grades to its DIRECT
# spine, not to a far interior point), so it is dropped to decouple the building
# frontages from the route-maxed-low far interior.  Ring-adjacent, spine,
# building-frontage and seam chords are NEVER dropped by this.  0 = unlimited.
APRON_BODY_CHORD_MAX_M = float(os.environ.get("O4_APRON_BODY_CHORD_MAX_M", "60"))


@dataclass(frozen=True)
class Allowance:
    """Max |Δz| budget for a pair: ``cL·Δs∥ + cT·Δs⊥``.  A flat allowance has
    ``cL == cT`` and (with Δs⊥ = 0) is the legacy scalar ``cap·dist``.

    When the pair has been decomposed against its route up front (anisotropic
    edges, ``grade_graph.shape_constraints``), the resulting scalar budget is
    BAKED into ``budget``: ``at()`` then returns it directly, ignoring the
    distance a consumer passes.  This is what lets every consumer keep its
    existing ``cap.at(d, 0.0)`` call yet receive the route-arc budget — the
    decomposition is computed ONCE in the law (no per-site copy, so the solver and
    validator graphs can't drift).  ``budget is None`` ⇒ a plain live allowance."""
    cL: float
    cT: float
    budget: Optional[float] = None

    @classmethod
    def flat(cls, cap: float) -> "Allowance":
        return cls(cap, cap)

    @classmethod
    def baked(cls, cL: float, cT: float, budget: float) -> "Allowance":
        """An allowance whose anisotropic budget is already evaluated (against the
        pair's route).  ``at()`` returns ``budget``; ``flat_cap()`` still reports
        the longitudinal ``cL`` for %-cap messages."""
        return cls(cL, cT, budget)

    def at(self, ds_parallel: float, ds_perp: float = 0.0) -> float:
        if self.budget is not None:
            return self.budget
        # L2 (ellipse) composition: a surface with principal gradient limits
        # (cL, cT) allows |Δz| = √((cL·Δs∥)² + (cT·Δs⊥)²) in an oblique
        # direction.  The old L1 sum over-allowed diagonals by up to √2 —
        # measured: 4 % road-carve pairs read LEGAL at 5.6 % (user-visible
        # steep edges at zero reported violations, 2026-07-03).
        a = self.cL * ds_parallel
        b = self.cT * ds_perp
        return (a * a + b * b) ** 0.5

    @property
    def is_flat(self) -> bool:
        return self.cL == self.cT

    def flat_cap(self) -> float:
        """The longitudinal scalar cap.  For a flat LIVE allowance this is the
        legacy ``(a, b, cap)`` value; for a BAKED allowance it is ``cL`` (the
        %-cap to report).  Asserts only for a live anisotropic allowance — that
        would silently lose its ``cT`` through a scalar consumer."""
        if self.budget is None:
            assert self.is_flat, "anisotropic allowance has no single scalar cap"
        return self.cL


def pair_grade_budget_m(cap_allow: "Allowance", distance_m: float) -> float:
    """The within-shape PAIR law's rise budget for one vertex pair —
    ``max(anisotropic bake, flat cap × run)``, WITHOUT the reader's
    quantization noise (each reader adds its own encoding envelope).

    The flat floor keeps the pair law symmetric with the plane-gradient
    law: a route-arc BAKED allowance can trim the budget BELOW
    ``cap × run``, so an at-cap emitted pair false-flagged by
    sub-millimetres (SPJC service_road #461: 5.006 % = 0.5 mm over the
    flat 5 % cap while the baked budget sat ~5 cm under it).  A LARGER
    baked budget on curves is honoured.  THE single source shared by
    ``tools/check_grade.py`` and ``grade_graph_validate`` — the two
    pair-law readers cannot drift on the budget formula (2026-07-17).
    """
    return max(cap_allow.at(distance_m, 0.0),
               cap_allow.flat_cap() * distance_m)


@dataclass(frozen=True)
class PairContext:
    """Everything the law needs about ONE vertex pair, computed by the reader
    from its own representation (in-memory shape, or emitted OSM).

    The two EXPENSIVE geometry predicates are injected as thunks so the law can
    evaluate them lazily (only for pairs that survive the cheap skips), matching
    the legacy in-line short-circuiting — the reader supplies *how* to test them
    from its representation, the law decides *when*:

    ``visible_fn``       returns whether the chord stays inside the pavement;
                         None ⇒ no visibility constraint (always visible).
    ``crosses_spine_fn`` returns whether the chord crosses a spine the shape owns
                         (the climb is via the spine, not this diagonal); the
                         reader sets it to None unless the pair is non-spine and
                         non-ring-adjacent (where the rule can apply).
    ``mesh_member_fn``   returns whether the pair is a triangle-mesh edge of the
                         shape's ring (junction mesh rule); the reader sets it to
                         None unless the rule can apply (gate on, junction role,
                         non-spine, non-ring-adjacent).  None ⇒ no mesh
                         restriction — a reader that cannot triangulate stays
                         STRICTER (checks every body chord), never looser.
    ``blend_cap_fn``     lazy apron↔taxi blend cap (evaluated ONLY for a surviving
                         non-spine apron pair), or None.
    ``spine_caps``       caps of the centerline(s) BOTH endpoints lie on; () ⇒ not
                         a spine pair (the climb is carried by this pair directly).
    """
    role: str
    dist: float
    ring_adjacent: bool
    a_seam: bool
    b_seam: bool
    a_building: bool
    b_building: bool
    spine_caps: tuple
    body_cap: float
    visible_fn: Optional[Callable[[], bool]] = None
    crosses_spine_fn: Optional[Callable[[], bool]] = None
    mesh_member_fn: Optional[Callable[[], bool]] = None
    blend_cap_fn: Optional[Callable[[], float]] = None
    # ``both_road``: both endpoints sit on a service-road carve through the host
    # (so the pair descends at the ROAD cap, not the host body cap).
    both_road: bool = False


SKIP: Optional[Allowance] = None


def classify_pair(p: PairContext) -> Optional[Allowance]:
    """Apply the within-shape grade law to one pair.  Returns the pair's
    ``Allowance``, or ``SKIP`` (None) if the pair is not a regulated grade path.

    Rules in precedence order (first match wins).  ELIGIBILITY (skip) rules:
    """
    # — an ALONG-SEAM pair (both endpoints DEM-pinned) is terrain-controlled.
    #   A pair with ONE seam endpoint stays IN the law (2026-07-03, user
    #   SPLP report): the blanket skip left the APPROACH to the seam pin
    #   ungraded on both readers — the solver never spread the drop and the
    #   validator never flagged it, so a taxiway crossing a tile line dove
    #   into a V-notch at the pin (SPLP: mirrored 1.2-1.3 m dips both tile
    #   sides, law-true 0).  With the pair kept, the seam node is a hard
    #   anchor the surface must RAMP to at the shape's own cap.
    #   RUNWAY-family pairs keep the full exemption for now: the FAA
    #   profile is solved separately and a mid-runway seam pin can
    #   contradict it locally (SPLP: 4.2 m notch) — the profile-side fix
    #   (seam anchor as a regrade target) is queued.
    if p.a_seam and p.b_seam:
        return SKIP
    if ((p.a_seam or p.b_seam)
            and p.role in ("runway", "runway_crossing")):
        return SKIP
    # — both ends on building pads ⇒ inter-pad frontage = an allowed building
    #   ↔building step, not an apron grade path.
    if p.a_building and p.b_building:
        return SKIP
    # — sub-noise separation is not a grade constraint.
    if p.dist < MIN_PAIR_DIST_M:
        return SKIP
    # — JUNCTION MESH RULE (O4_JUNCTION_MESH_CONSTRAINTS, user 2026-06-30): a
    #   junction's only real grade paths are its SPINE and the triangle-mesh
    #   edges of its ring (what X-Plane's mesh renders); every other body
    #   chord is phantom — an aircraft follows the spine, not the diagonal —
    #   and mesh compliance already implies straight-chord compliance.  So a
    #   junction-role pair that is not ring-adjacent, shares no spine
    #   centerline, and is not a mesh edge is not a regulated grade path.
    #   APRONS are NOT mesh-restricted (their geodesic flatness model catches
    #   aggregate slope a mesh edge misses) — the reader never supplies the
    #   thunk for them.  Sits BEFORE the visibility skip so a phantom chord
    #   never pays for the polygon-containment test.
    if (JUNCTION_MESH_CONSTRAINTS and p.role in JUNCTION_ROLES
            and not p.ring_adjacent and not p.spine_caps
            and p.mesh_member_fn is not None and not p.mesh_member_fn()):
        return SKIP
    # — a non-adjacent chord that leaves the pavement is not a surface path.
    if not p.ring_adjacent and p.visible_fn is not None and not p.visible_fn():
        return SKIP
    # — the climb between the two sides is carried by the SPINE at the taxi cap;
    #   the straight diagonal across it is not an independent grade path.
    #   NEVER for a RING-ADJACENT pair (user 2026-07-04): a ring edge is a
    #   physical stretch of pavement surface, not a chord — skipping it
    #   leaves adjacent emitted vertices with NO law edge, so the final
    #   projection's anchor-reach envelope clamps them independently and
    #   imprints its per-node reach noise on the surface (SPLP seam
    #   approach: ±1 m wiggles at 10-14 % between ring neighbours whose
    #   pin-derived ceilings differed by more than any legal edge).
    if (not p.ring_adjacent
            and p.crosses_spine_fn is not None and p.crosses_spine_fn()):
        return SKIP
    # — a long apron body↔body chord grades to its spine, not to a far interior
    #   point (decouples building frontages from the route-maxed-low interior).
    if (p.role == APRON_ROLE and APRON_BODY_CHORD_MAX_M
            and not p.spine_caps and not p.ring_adjacent
            and not p.a_building and not p.b_building
            and p.dist > APRON_BODY_CHORD_MAX_M):
        return SKIP

    # CAP selection — base cap (first match wins):
    # — a spine pair keeps its route's per-letter taxi cap (looser of the shared
    #   centerlines), the same cap the seater grades that route at.
    if p.spine_caps:
        cap = max(p.spine_caps)
    # — an apron body edge near a taxiway earns the route's blended cap.
    #   NEVER for a pair touching a BUILDING pad: the building↔spine 1 %
    #   rule is the binding constraint (user 2026-07-02) — blending it to
    #   the route cap (or a 4 % service route) silently legalised a 3.5 %
    #   frontage chord at SPJC building-10031.
    elif (p.blend_cap_fn is not None
          and not p.a_building and not p.b_building):
        cap = p.blend_cap_fn()
    # — otherwise the shape's body cap (apron 1%, junction the taxi cap, …).
    else:
        cap = p.body_cap

    # BUILDINGS ARE THE HEAVIEST CONSTRAINT (user 2026-07-02/03): a pair
    # touching a building pad is the frontage 1 % rule regardless of the
    # HOST face's role.  The blend / road-carve relaxations above already
    # exclude building pairs, but a frontage chord inside a
    # ``service_junction`` face (service roads hug terminals) never took
    # those branches — it inherited the host's 4 % BODY cap and legalised
    # the >1 % terminal-side ramps the user sees in the sim (SPJC: 15
    # frontage pairs up to 3.8 % read legal at "cap 4.0%").
    if (p.a_building or p.b_building) and cap > BUILDING_FRONTAGE_MAX_GRADE:
        cap = BUILDING_FRONTAGE_MAX_GRADE

    # SEAM PINS ARE GRADED-TO HARD ANCHORS (user 2026-07-04, "treat the
    # seam like a runway edge or building"): a pair with a seam-pinned
    # endpoint never earns spine/blend credit — those credits describe
    # travel ALONG a route, but the approach to an immovable terrain pin
    # is the shape's own grading problem at its own body cap (SPLP: spine
    # credit legalised a 2.5-2.8 % V-notch approach to a band-edge pin
    # the projection had left 0.7-1.1 m below its neighbours).  The road
    # carve below still relaxes (a service road descends to ITS seam pin
    # at the road grade).
    if (p.a_seam or p.b_seam) and cap > p.body_cap:
        cap = p.body_cap

    # RELAXATIONS — a feature CARVED INTO the host that legitimately grades
    # steeper than the host body.  Applied by BOTH readers (the solver builds to
    # it, the validator confirms it) — never a test-only fudge: the carve corners
    # lie ON the host ring, so without this the host law would wrongly regulate
    # the carved feature's own descent.  Relax only (raise the cap).
    # — both endpoints on a service-road carve → the road's cap.  NEVER for a
    #   pair touching a BUILDING pad: service roads hug terminal frontages, so
    #   the road zone otherwise swallows the building↔spine 1 % rule (SPJC
    #   building-10031: a 3.5 % frontage chord read as a legal 4 % road pair —
    #   user 2026-07-02, buildings are the heaviest constraint).
    if (p.both_road and SERVICE_ROAD_MAX_GRADE > cap
            and not p.a_building and not p.b_building):
        cap = SERVICE_ROAD_MAX_GRADE

    return Allowance.flat(cap)


# ── Object-derived bridge law (feature B, docs/object_terrain_features_spec.md)
# Single source for the solve-side writers in ``bridges.py`` (deck-end pin
# values, crossing-floor producer) and the ``verification.py`` checks
# (``check_bridge_deck_end_pins`` / ``check_bridge_crossing_floor``) — the
# lockstep pattern of the runway-end skirt above.  Pure functions of the
# classified object geometry and a datum; the config constants carry the
# clearance values (amendment A10 narrowed ``BRIDGE_ROAD_CLEARANCE_M`` to
# the crossing-floor law; the deck-carried corridor floor is
# geometry-driven and lives in ``bridges._bridge_corridor_floor_m``).

def bridge_deck_end_pin_elevation_m(
        datum_elevation_m: float,
        deck_end_elevation_y_m: float) -> float:
    """THE hard-pin elevation at a bridge deck end (spec section 3.2
    step 2): the anchor-terrain datum plus the deck-top profile value at
    that end.

    ``datum_elevation_m`` is the absolute elevation of the object's
    anchor-terrain plane: ``absolute_deck_elevation_m − deck_top_y_m``
    when OBJECT_MSL fixtures pin the deck (KBNA: 167.0 − 5.99), else the
    solved/DEM terrain at the anchor.  ``deck_end_elevation_y_m`` is the
    profile value at the end (effective metres above that datum) — for a
    flat KBNA-class deck both ends equal the crest, giving 167.0
    exactly; for a PROFILE_CARRIED ramp the two ends differ.  Pavement
    ring vertices inserted on the abutment line are pinned to this value
    and the network grades up to them under the existing edge budgets."""
    return float(datum_elevation_m) + float(deck_end_elevation_y_m)


def bridge_profile_pin_elevation_m(
        datum_elevation_m: float,
        deck_top_profile: list[tuple[float, float]],
        along_axis_m: float) -> float:
    """THE per-vertex pin elevation across a PROFILE_CARRIED span (spec
    section 3.2, amendment A4): datum plus the deck-top profile linearly
    interpolated at ``along_axis_m``, clamped to the profile's end
    values outside its sampled range.  The object is the authority for
    the vertical shape; pavement nodes inside the deck footprint are
    pinned to this so the rendered object and the solved pavement meet
    exactly (the runway-profile per-vertex mechanism)."""
    if not deck_top_profile:
        return float(datum_elevation_m)
    positions = [along for along, _height in deck_top_profile]
    heights = [height for _along, height in deck_top_profile]
    if along_axis_m <= positions[0]:
        profile_height = heights[0]
    elif along_axis_m >= positions[-1]:
        profile_height = heights[-1]
    else:
        profile_height = heights[-1]
        for index in range(1, len(positions)):
            if along_axis_m <= positions[index]:
                span = positions[index] - positions[index - 1]
                fraction = (
                    (along_axis_m - positions[index - 1]) / span
                    if span > 0.0 else 0.0
                )
                profile_height = (
                    heights[index - 1]
                    + fraction * (heights[index] - heights[index - 1])
                )
                break
    return float(datum_elevation_m) + float(profile_height)


def bridge_crossing_floor_m(
        road_surface_elevation_m: float,
        structure_thickness_m: float) -> float:
    """THE floor under pavement nodes inside a TERRAIN/PROFILE_CARRIED
    span footprint whose road beneath is not (or only partially)
    lowered (spec section 3.2, amendment A2): the crossing must clear
    the traffic under it, so its floor is the road surface plus the
    road-corridor clearance plus the deck's own structural thickness
    (deck top − clearance underside, measured from the object; 0 when
    the object exposes no underside plane).

    Wired as a per-node solver floor (``node_band``/``spine_floor``
    idiom): the one-solve raises the crossing to the floor and the
    existing grade caps and curvature law shape the approach ramps —
    no ramp geometry is authored.  Both the solve-side producer
    (``bridges.bridge_crossing_floor_nodes``) and the validator
    (``verification.check_bridge_crossing_floor``) call THIS function."""
    from .config import BRIDGE_ROAD_CLEARANCE_M
    return (
        float(road_surface_elevation_m)
        + float(BRIDGE_ROAD_CLEARANCE_M)
        + max(0.0, float(structure_thickness_m))
    )


# ── Object-derived tunnel law (feature A, docs/object_terrain_features_spec.md
# section 3.3 + amendment A1).  Single source for the layout emitter
# (``object_terrain_assembly.build_tunnel_layout_shapes``) and any future
# tunnel-trench validator, the same lockstep pattern as the bridge laws and
# the runway-end skirt above.  Pure functions of the classified deck depth
# and the anchor-terrain datum; the strictly-below offset lives in
# ``config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M``.

def tunnel_trench_rim_elevation_m(datum_elevation_m: float) -> float:
    """THE trench rim (top-of-wall) elevation: the anchor-terrain datum
    (spec section 3.3 step 3, amendment A1).  The roof OBJECT renders at
    grade over the roofed body, so the rim welds to the surrounding terrain
    at the datum and the vertical drop to the floor is a node-split wall
    (ruling R2; author-mesh dissection section 2.4)."""
    return float(datum_elevation_m)


def tunnel_trench_floor_elevation_m(
        datum_elevation_m: float,
        deck_level_y_m: float) -> float:
    """THE trench floor (flat pan) elevation: the datum plus the deck's
    effective level minus ``config.TUNNEL_FLOOR_BELOW_OBJECT_DECK_M`` so the
    mesh floor sits STRICTLY below the OBJ8 road deck (spec section 3.3 step
    3, amendment A1; section 2.4 point 3 — the deck carries the visible
    road, the mesh only clears it).

    ``deck_level_y_m`` is the deck's EFFECTIVE height above the datum —
    negative below grade, so the classifier's ``-body_depth_m`` is passed
    directly.  The negative-``OBJECT_AGL`` offset (EGLL tunnels 6/7/10) is
    ALREADY folded into that effective height by the classifier
    (``object_terrain_features``: ``effective_y = above_ground_level_metres
    + authored_y``), so no offset is re-applied here — adding it again would
    double-count and drop those floors 7 m too far."""
    from .config import TUNNEL_FLOOR_BELOW_OBJECT_DECK_M
    return (
        float(datum_elevation_m)
        + float(deck_level_y_m)
        - float(TUNNEL_FLOOR_BELOW_OBJECT_DECK_M)
    )
