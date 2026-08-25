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

from . import fabric_flags
from .config import (
    ADJACENT_GROUND_DAYLIGHT_SLOPE_LIMIT,
    ADJACENT_GROUND_LIP_MAX_DOWN_SLOPE, ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE,
    ADJACENT_GROUND_LIP_WIDTH_M, ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE,
    APRON_MAX_GRADE, APRON_SHOULDER_MAX_DOWN_SLOPE, FAN_RAMP_CAP,
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
    RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_BY_CODE,
    RUNWAY_STRIP_MAX_LONGITUDINAL_SLOPE_FAA,
    SERVICE_ROAD_MAX_GRADE, TAXI_MAX_GRADE, TAXIWAY_STRIP_BAND_MAX_DOWN_SLOPE,
    TAXIWAY_STRIP_BAND_MIN_DOWN_SLOPE, runway_code_number,
    taxiway_strip_graded_half_width_for_letter)
# ── Region rulesets (phase B) ────────────────────────────────────────
# EVERY split family is read through these accessors — never through a
# bare module constant at a law site (owner ruling "Region-specific
# rulesets", 2026-08-02: "NO ``if icao.startswith('K')`` at any law
# site").  Emitter and validator call the SAME accessor with the SAME
# resolved key, which is the lockstep half of the grade-law completeness
# standard.
from .config import (                                          # noqa: E402
    CROWN_MINIMUM_BOUND_RUNWAYS, CROWN_MINIMUM_BOUND_TAXIWAYS,
    DEFAULT_RULESET, FAA_RULESET,
    GROUNDSIDE_MIN_DRAINAGE_GRADE, get_ruleset, resolve_ruleset,
    ruleset_apron_max_grade_change, ruleset_apron_min_drainage_grade,
    ruleset_runway_end_grade, ruleset_runway_end_zone_length_m,
    ruleset_runway_max_grade, ruleset_runway_max_grade_change,
    ruleset_runway_max_grade_change_per_m,
    ruleset_runway_vertical_curve_min_change,
    ruleset_shoulder_edge_dropoff, ruleset_shoulder_transverse_band,
    ruleset_stand_max_grade, ruleset_strip_arc_rate_per_m,
    ruleset_strip_band_max_down_slope, ruleset_strip_half_width_m,
    ruleset_strip_max_longitudinal_slope, ruleset_taxi_max_grade,
    ruleset_taxi_transverse_max, transverse_cap_for_longitudinal_cap)


def ruleset_of(layout_or_icao=None) -> str:
    """THE ruleset key for a build, from a ``PavementLayout`` (or an ICAO
    identifier, or ``None``).

    Resolution happens ONCE per build and is then carried: a layout that
    already carries a ``ruleset`` attribute is believed verbatim (that is
    the value the sidecar records and the validator judges in), and only
    a layout without one is resolved from its ICAO identifier.  A law
    site never re-resolves from the identifier when a resolved key is
    available — the two-instruments law: production emits what it did,
    and the validator judges the same frame.
    """
    if layout_or_icao is None:
        return DEFAULT_RULESET
    if isinstance(layout_or_icao, str):
        return resolve_ruleset(layout_or_icao)
    carried = getattr(layout_or_icao, "ruleset", None)
    if carried:
        return str(carried)
    return resolve_ruleset(getattr(layout_or_icao, "icao", "") or "")

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
# A join is ALSO where a taxi route CROSSES a runway (spec
# ``docs/specs/r8-runway-seeding-spec.md`` stage 1).  A taxi route that runs
# THROUGH a runway (a connector between two parallel runways, a taxiway that
# continues past the strip) contacts the runway surface at each edge crossing
# exactly as a terminating route does at its endpoint — the emitted taxi /
# junction node is welded to the runway edge there in both cases.  Enumerating
# only the ENDPOINTS left every through-crossing free: the runway's DEM-follow
# seating ride survived at the crossing, and each parallel runway rode its own
# cross-field fall independently (KAFW 16L/34R vs 16R/34L: +0.848 / −1.398 m
# off a 0.087 m law spread ⇒ 2.333 m across a 136 m connector whose route
# budget is 2.046 m ⇒ a 9-node inverted band, the build refused).
# Two contacts within this of each other on the SAME runway are ONE join (the
# endpoint of a route ending just inside the edge and the edge crossing it
# resolves to are the same contact).
RUNWAY_JOIN_DEDUP_M = 0.5
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


def taxi_centerline_line_and_ref(entry):
    """Unwrap ONE ``layout.apt_taxi_centerlines`` entry into ``(line, ref)``.

    The collection is heterogeneous by history: ``TaxiCenterline`` objects (with
    ``.line``), ``(line, ref)`` tuples, and bare ``LineString``s all appear.
    Every reader of the collection must unwrap it the SAME way, so this is the
    one place that knows the shapes."""
    ln = (entry.line if hasattr(entry, "line")
          else (entry[0] if isinstance(entry, (tuple, list)) else entry))
    ref = (entry[1] if (isinstance(entry, (tuple, list)) and len(entry) > 1)
           else None)
    return ln, ref


def _runway_edge_crossings(ln, rwy_polygon):
    """Every point where centerline ``ln`` crosses the EDGE of ``rwy_polygon``.

    Returns ``[(x, y), ...]``.  Tangential / collinear overlaps yield non-Point
    intersection geometries; those are not crossings and are skipped."""
    try:
        xing = ln.intersection(rwy_polygon.boundary)
    except Exception:
        return []
    if getattr(xing, "is_empty", True):
        return []
    geoms = ([xing] if getattr(xing, "geom_type", "") == "Point"
             else list(getattr(xing, "geoms", []) or ()))
    return [(float(g.x), float(g.y)) for g in geoms
            if getattr(g, "geom_type", "") == "Point"]


def runway_join_contacts(centerlines, runways, *, edge_contact=None,
                         crossings=None):
    """THE enumeration of taxi-route↔runway JOIN CONTACTS — one authority for
    *where a join is*.

    A taxi route that TERMINATES on a runway (either endpoint within
    ``RUNWAY_CONTACT_M`` of the runway polygon) joins it; the contact point is
    resolved through ``runway_join_contact`` (the runway-EDGE crossing on a wide
    runway, the endpoint itself otherwise).

    A taxi route that CROSSES a runway joins it too, at EVERY edge crossing
    (spec ``docs/specs/r8-runway-seeding-spec.md`` stage 1) — the emitted node
    is welded to the runway edge there exactly as at a terminating endpoint,
    and leaving it out left the runway's DEM-follow seating ride standing at
    every through-crossing.  ``crossings`` defaults to the
    ``O4_RUNWAY_CROSSING_JOIN`` reading (default on); ``False`` reverts to the
    endpoint-only set.  A crossing within ``RUNWAY_JOIN_DEDUP_M`` of a contact
    already reported for the same runway is the SAME join and is not repeated.

    Two consumers share this, and they must not drift apart:
      * ``grade_graph._runway_anchors`` — anchors the nearest EMITTED node to
        the runway surface value sampled at the contact;
      * ``pavement.runway_segments.generate_patch_osm`` — anchors the runway
        PROFILE STATION at the contact to the LAW LINE, so the value the first
        consumer later samples is law and never DEM-follow ride
        (``docs/specs/cycle4-anchor-law-spec.md``).

    ``runways`` is any sequence of objects carrying a shapely ``.polygon``
    (layout shapes).  Returns ``[(runway, (cx, cy), (ex, ey)), ...]`` in
    centerline order, each entry naming the runway joined, the contact point and
    the centerline endpoint it came from.  ``edge_contact`` defaults to the
    ``O4_RUNWAY_EDGE_CONTACT`` reading (default on) so every caller agrees with
    the validator's own read of the same flag; ``False`` reverts to the raw
    endpoint."""
    import os as _os
    from shapely.geometry import Point
    if edge_contact is None:
        edge_contact = _os.environ.get("O4_RUNWAY_EDGE_CONTACT", "1") == "1"
    if crossings is None:
        crossings = _os.environ.get("O4_RUNWAY_CROSSING_JOIN", "1") == "1"
    out = []
    polys = [r for r in (runways or [])
             if getattr(r, "polygon", None) is not None
             and not r.polygon.is_empty]
    if not polys:
        return out
    _dedup2 = RUNWAY_JOIN_DEDUP_M * RUNWAY_JOIN_DEDUP_M
    # Bounding boxes, once — the crossing sweep is centerlines × runway PIECES
    # (a runway is emitted as many sub-rects), so the cheap envelope reject has
    # to happen before any shapely intersection (build-time law).
    bounds = [r.polygon.bounds for r in polys] if crossings else []
    for entry in (centerlines or []):
        ln, ref = taxi_centerline_line_and_ref(entry)
        if (ln is None or ln.is_empty
                or str(ref or "").upper().startswith("SVC")):
            continue
        cs = list(ln.coords)
        if len(cs) < 2:
            continue
        # Per-runway contacts reported for THIS centerline, for the dedup.
        seen: dict = {}

        def _emit(rwy, cx, cy, ex, ey):
            key = id(rwy)
            for (px, py) in seen.get(key, ()):  # noqa: B023
                if (px - cx) ** 2 + (py - cy) ** 2 <= _dedup2:
                    return
            seen.setdefault(key, []).append((cx, cy))  # noqa: B023
            out.append((rwy, (float(cx), float(cy)),
                        (float(ex), float(ey))))

        for (ex, ey) in (cs[0], cs[-1]):
            P = Point(ex, ey)
            rwy = min(polys, key=lambda r: r.polygon.distance(P))
            if rwy.polygon.distance(P) > RUNWAY_CONTACT_M:
                continue
            if edge_contact:
                c = runway_join_contact(ln, (ex, ey), rwy.polygon)
                cx, cy = c if c is not None else (ex, ey)
            else:
                cx, cy = ex, ey
            _emit(rwy, cx, cy, ex, ey)
        if not crossings:
            continue
        lx0, ly0, lx1, ly1 = ln.bounds
        for rwy, (rx0, ry0, rx1, ry1) in zip(polys, bounds):
            if rx1 < lx0 or rx0 > lx1 or ry1 < ly0 or ry0 > ly1:
                continue
            for (cx, cy) in _runway_edge_crossings(ln, rwy.polygon):
                # A crossing IS its own contact: the emitted node sits on the
                # runway edge there, so the contact and the "endpoint it came
                # from" are the same point.
                _emit(rwy, cx, cy, cx, cy)
    return out


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
# limited to ±2 % per 100 ft (30.5 m); ICAO Annex 14 §3.5.10 caps RESA
# downward slopes at 5 %.  Beyond the governed footprint a drop is LAWFUL
# (Madeira-style), so the governed length is also the hard cap on emitted
# fill.  Single source for the Pass D skirt EMITTER
# (``clearance._emit_resa_skirt``) and the ``check_grade`` validator —
# regulatory basis and plan: ``docs/runway_end_skirt_plan.md``.
#
# THE VALUES NOW LIVE ON THE FAA RULESET (config.FAA_RULESET), which is
# where they came from; these names are kept as the FAA ruleset's view so
# every existing importer (clearance, check_grade, the twins) is
# unchanged and there is exactly ONE copy of each number.  Ruleset-aware
# call sites should read ``runway_end_skirt_law(ruleset)`` instead — at
# an ICAO airport there is NO 61 m near zone and no cited rate.
RUNWAY_END_SKIRT_NEAR_ZONE_M = FAA_RULESET.end_skirt_near_zone_m
RUNWAY_END_SKIRT_NEAR_MAX_DOWN_GRADE = FAA_RULESET.end_skirt_near_max_down_grade
RUNWAY_END_SKIRT_MAX_DOWN_GRADE = FAA_RULESET.end_skirt_max_down_grade
RUNWAY_END_SKIRT_MAX_GRADE_CHANGE_PER_M = (
    FAA_RULESET.end_skirt_max_grade_change_per_m)


def runway_end_skirt_law(ruleset=None) -> tuple:
    """``(near_zone_m, near_max_down, max_down, rate_per_m)`` — the
    end-skirt LONGITUDINAL law of ``ruleset`` (§4 row 10).

    FAA (AC §3.16.5 items 2-5): a 61 m near zone falling 0 to −3 %, −5 %
    beyond, grade changes ±2 % per 30.5 m.  ICAO (Annex 14 §3.5.10):
    down ≤5 % with NO near zone and no numeric rate — ``near_zone_m`` is
    ``None`` there, and the rate is the provisional operationalization
    flagged on the ruleset (owner question 2).
    """
    rs = get_ruleset(ruleset)
    return (rs.end_skirt_near_zone_m, rs.end_skirt_near_max_down_grade,
            rs.end_skirt_max_down_grade, rs.end_skirt_max_grade_change_per_m)

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


def _end_skirt_params(ruleset=None) -> tuple:
    """``(near_zone_m, near_max_down, max_down, rate_per_m)`` in a form
    the floor math can consume WITHOUT a per-authority special case.

    ICAO states no near zone (§3.5.10 is a single ≤5 % down cap), so its
    near zone collapses to length 0 with the near cap equal to the far
    cap — the identical piecewise-linear machinery then produces ICAO's
    one-segment law with no branch anywhere below.
    """
    near_zone, near_max, max_down, rate = runway_end_skirt_law(ruleset)
    if near_zone is None or near_max is None:
        return (0.0, float(max_down), float(max_down), float(rate))
    return (float(near_zone), float(near_max), float(max_down), float(rate))


def _runway_end_skirt_signed_grade(
        distance_m: float, start_grade: float, ruleset=None) -> float:
    """Signed grade (positive = climbing) of the LOWEST lawful surface at
    ``distance_m`` beyond the runway end.  The steepest permissible
    descent is bounded by BOTH what the grade-change rate can reach from
    the runway's own end grade AND the zone's down-grade cap; the cap
    itself eases from −3 % to −5 % at the near-zone boundary under the
    same rate limit, so the floor has no curvature kink anywhere.

    Under a ruleset with no near zone (ICAO) the first term is simply the
    single ≤5 % cap from the pavement exit — see ``_end_skirt_params``."""
    near_zone, near_max, max_down, rate = _end_skirt_params(ruleset)
    reachable = start_grade - rate * distance_m
    if distance_m <= near_zone:
        lawful = -near_max
    else:
        lawful = max(-max_down,
                     -near_max - rate * (distance_m - near_zone))
    return max(lawful, reachable)


def runway_end_skirt_profile_breakpoints(
        start_grade: float = 0.0, ruleset=None) -> list[float]:
    """Distances (m, ascending) where the floor profile's GRADE LAW
    changes — the boundaries of its piecewise-linear-grade segments.
    Between consecutive breakpoints the floor is a single quadratic, so
    an emitter rendering it as ruled bands split at these breakpoints
    bounds the chord-vs-floor sagitta at ``rate · L² / 8`` (≤ 0.31 m for
    the 61 m near zone) — far inside the fill trigger.  Single source
    for the Pass D band edges AND the floor integration below."""
    start_grade = min(0.0, start_grade)
    near_zone, near_max, max_down, rate = _end_skirt_params(ruleset)
    return sorted({
        near_zone,
        near_zone + (max_down - near_max) / rate,
        (start_grade + near_max) / rate,
        (start_grade + max_down) / rate,
    })


def runway_end_skirt_floor_profile(
        distances_m: list[float], start_grade: float = 0.0,
        ruleset=None) -> list[float]:
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
    breakpoints = runway_end_skirt_profile_breakpoints(start_grade, ruleset)

    def _depth(distance_m: float) -> float:
        drop = 0.0
        previous = 0.0
        for cut in [b for b in breakpoints if 0.0 < b < distance_m] \
                + [distance_m]:
            segment = cut - previous
            drop -= 0.5 * segment * (
                _runway_end_skirt_signed_grade(previous, start_grade, ruleset)
                + _runway_end_skirt_signed_grade(cut, start_grade, ruleset))
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
        pavement_beyond_end_m: float = 0.0,
        ruleset=None) -> list[float]:
    """``runway_end_skirt_profile_breakpoints`` re-expressed as distances
    beyond the PAVEMENT EXIT when that exit sits ``pavement_beyond_end_m``
    past the runway end: the law profile is anchored at the runway end,
    so its grade-law breakpoints shift inward by the overrun length
    (breakpoints the pavement already consumed drop out)."""
    advance = max(0.0, pavement_beyond_end_m)
    return sorted({
        b - advance
        for b in runway_end_skirt_profile_breakpoints(start_grade, ruleset)
        if b > advance + 1e-9})


def runway_end_skirt_floor_profile_beyond_pavement(
        distances_m: list[float], start_grade: float = 0.0,
        pavement_beyond_end_m: float = 0.0, ruleset=None) -> list[float]:
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
        return runway_end_skirt_floor_profile(
            distances_m, start_grade, ruleset)
    depths = runway_end_skirt_floor_profile(
        [advance] + [advance + d for d in distances_m], start_grade, ruleset)
    return [d - depths[0] for d in depths[1:]]


def runway_end_corridor_half_width_m(runway_width_m: float,
                                     runway_length_m: float,
                                     code_letter=None,
                                     ruleset=None) -> float:
    """Half-width (m) each side of the extended centreline of the governed
    runway-END corridor — the lateral extent of both the skirt fill and the
    RESA cut.

    ICAO Annex 14 §3.5.5: the RESA "shall extend to a width of at least twice
    that of the runway", and §3.5.6 recommends it extend to the width of the
    graded portion of the strip.  As a HALF-width those read
    ``max(runway_width, strip_half)`` — the full corridor is then at least
    2 x the runway width AND at least the graded strip width, satisfying both
    clauses.  (The full apt.dat width standing in for a half-width is
    deliberate, not a units slip: it is the §3.5.5 factor-of-two.)

    Single source for ``clearance.emit_runway_end_skirts`` (both directions)
    and the ``verification`` reader.

    The strip half-width term is RULESET-KEYED (§4 row 6): under the FAA
    ruleset it is the Appendix G RSA half-width (76.2 m at ADG III-VI vs
    ICAO's 75 m), so an FAA end corridor is ~1.2 m wider.
    """
    code = runway_code_number(runway_length_m)
    return max(float(runway_width_m),
               float(ruleset_strip_half_width_m(code, code_letter, ruleset)))


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
        runway_width_m: float, code_letter=None,
        ruleset=None) -> list[list[tuple[float, float]]]:
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
        14 §3.5.5-3.5.6, the RESA/skirt corridor this module already owns),
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
    strip_half = float(ruleset_strip_half_width_m(code, code_letter, ruleset))
    end_half = runway_end_corridor_half_width_m(
        runway_width_m, length, code_letter, ruleset)
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


# ═══════════════════════════════════════════════════════════════════════
# RUNWAY-STRIP LAW: PRECEDENCE (G-1 general) + ABEAM LONGITUDINAL (G-2)
# ═══════════════════════════════════════════════════════════════════════
# ``runway_strip_wall_keepout_rings`` above is THE strip footprint — the
# wall ruling was its first (special-case) consumer, and the general law is
# that the footprint is SUPREME: inside it no other role's corridor law may
# govern ground — the station stays, its GOVERNING LAW becomes the strip's
# (lead ruling 2026-08-04; "no other role's law may govern" was never "no
# law governs").  The geometry is deliberately NOT re-minted here: the law
# swap's emitter (``adjacent_ground.runway_strip_lateral_zone``) and its
# validator twin both build from the function above, exactly as the wall
# pair already does.  What IS new is the strip's own LONGITUDINAL bound.


def runway_strip_lateral_footprint_ring(
        axis_a: tuple[float, float], axis_b: tuple[float, float],
        runway_width_m: float, code_letter=None,
        ruleset=None) -> "Optional[list]":
    """JUST the LATERAL graded-strip rectangle of the strip footprint —
    centreline ± ``RUNWAY_STRIP_HALF_WIDTH_BY_CODE`` over the runway's own
    length, WITHOUT the two end corridors.

    This is the "BETWEEN THE ENDS" domain, and it is the domain of the
    abeam-longitudinal law specifically: FAA AC 150/5300-13B §3.16.5 gives
    the RSA THREE different longitudinal rules — item 1 (between the ends:
    the runway's own standard) and items 2-4 (beyond an end: 0 to −3 % for
    the first 61 m, −5 % past it).  The end corridors are the runway-END
    regime's ground, already governed by ``runway_end_envelope`` and read by
    ``verification.check_runway_end_skirt``; applying the between-the-ends
    cap there would double-govern it AND over-constrain it (a lawful 3 %
    fall off the end would read as a 1.5 % violation).

    The §1 PRECEDENCE law is different and keeps the FULL footprint (ends
    included) — inside the whole strip footprint no foreign corridor may
    govern; it is only the longitudinal CAP that stops at the ends.

    Derived from ``runway_strip_wall_keepout_rings`` (index 0 is the
    lateral rectangle by that function's own construction) so there is one
    strip geometry, never two."""
    rings = runway_strip_wall_keepout_rings(
        axis_a, axis_b, runway_width_m, code_letter, ruleset)
    return rings[0] if rings else None


def runway_strip_max_longitudinal_slope(code_number: int,
                                        ruleset: str = "icao",
                                        code_letter=None) -> float:
    """The strip's ALONG-RUNWAY slope cap for aerodrome code ``code_number``
    — the G-2 family the repo never bound (spec ``docs/specs/
    rsa-law-round-spec.md`` §2).

    ``ruleset``:

      * ``"icao"`` (live default) — Annex 14 Vol I §3.4.13: a longitudinal
        slope on the GRADED portion of the strip may not exceed 1.5 % at
        code 4, 1.75 % at code 3, 2 % at code 1-2.  The by-code shape is
        ICAO's, so the by-code table is the live constant.
      * ``"faa"`` — AC 150/5300-13B §3.16.5 Standards item 1: between the
        runway ends the RSA's longitudinal grades are "the same as the
        comparable standards for the runway", i.e. ``RUNWAY_MAX_GRADE``
        (1.5 %), code-invariant.  Present so the phase-B ruleset split
        (docs/RULINGS.md "Region-specific rulesets") keys an EXISTING
        constant instead of re-deriving one; nothing selects it yet.

    Note that at code 4 the two authorities agree (1.5 %), which is why the
    FAA fixture (KCLT, six precision code-4 ends) is exercised by the ICAO
    value this round without prejudging the split.

    PHASE B: the two-branch body is gone — the value comes from the
    resolved ruleset's own table (``config.ruleset_strip_max_
    longitudinal_slope``).  The signature and the ``"icao"`` default are
    kept so the RSA round's call sites are unchanged.
    """
    return float(ruleset_strip_max_longitudinal_slope(
        code_number, code_letter, ruleset))


def runway_strip_longitudinal_runs(points, axis, inside=None):
    """Split an ordered chain of strip-band vertices into the LONGITUDINAL
    runs the along-axis law applies to.

    ``points`` are ``(x, y)`` in any planar metre frame; ``axis`` is the
    runway's unit along-axis vector in that same frame; ``inside`` (optional,
    aligned) marks the vertices that lie inside the strip FOOTPRINT.  Returns
    a list of index lists.

    A consecutive pair BREAKS the run when

      * either vertex is outside the footprint (the strip law governs only
        its own ground — outside it the local role's corridor is back in
        charge, which is §1 read from the other side), or
      * the step is predominantly TRANSVERSE (``|Δp·axis| < |Δp·normal|``)
        — a band ring runs "inner row forward, outer row back", so the two
        turn corners are transverse steps.  A transverse step is the
        TRANSVERSE law's business (the graded-strip cross-fall, Annex 14
        §3.4.15); reading it as a longitudinal step would demand the lateral
        corridor's own mandatory drainage fall be flat, which is the
        opposite of the law.

    Shared by the emitter (which clamps) and the validator (which reads), so
    the two can never disagree about WHICH pairs the longitudinal law binds
    — the lockstep pattern ``adjacent_ground_supported_depths`` established.
    """
    ux, uy = float(axis[0]), float(axis[1])
    norm = (ux * ux + uy * uy) ** 0.5
    if norm < 1e-12:
        return []
    ux, uy = ux / norm, uy / norm
    px, py = -uy, ux
    runs: list[list[int]] = []
    cur: list[int] = []
    n = len(points)
    for i in range(n):
        if inside is not None and not inside[i]:
            if len(cur) >= 2:
                runs.append(cur)
            cur = []
            continue
        if not cur:
            cur = [i]
            continue
        ax, ay = points[cur[-1]]
        bx, by = points[i]
        dx, dy = bx - ax, by - ay
        along = abs(dx * ux + dy * uy)
        across = abs(dx * px + dy * py)
        if along <= 1e-9 or along < across:
            if len(cur) >= 2:
                runs.append(cur)
            cur = [i]
            continue
        cur.append(i)
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def _arc_rate_pass(s, z, free, rate_per_m) -> bool:
    """ONE minimal-move sweep making the chain's consecutive GRADES
    change no faster than ``rate_per_m`` per metre — the curvature half
    of a longitudinal law (§A3(b); the same second-difference form the
    runway profile's vertical-curve rule uses and the same form
    ``verification`` already reads: the allowance for the pair straddling
    station ``k`` is ``rate · ½(ds_left + ds_right)``).

    Only the MIDDLE vertex of an offending triple moves, and only by the
    least amount that satisfies the bound — the locality property the
    Lipschitz clamp above documents.  Returns whether anything moved."""
    moved = False
    n = len(z)
    for k in range(1, n - 1):
        if not free[k]:
            continue
        dp = s[k] - s[k - 1]
        dn = s[k + 1] - s[k]
        if abs(dp) < 1e-9 or abs(dn) < 1e-9:
            continue
        g_prev = (z[k] - z[k - 1]) / dp
        g_next = (z[k + 1] - z[k]) / dn
        allowed = rate_per_m * 0.5 * (abs(dp) + abs(dn))
        excess = abs(g_next - g_prev) - allowed
        if excess <= 1e-12:
            continue
        # d(g_next − g_prev)/dz[k] = −(1/dn + 1/dp): move z[k] by the
        # least amount that removes exactly the excess.
        denom = 1.0 / abs(dn) + 1.0 / abs(dp)
        step = excess / denom
        z[k] += step if (g_next - g_prev) > 0 else -step
        moved = True
    return moved


#: Non-termination guard for the Lipschitz SETTLE below.  Not a
#: convergence budget: the settle exits when nothing moves, and the
#: forward+backward Lipschitz pair is the exact 1-D regularization, so on
#: any real chain it terminates in a couple of passes.  A chain that spins
#: past this is a bug report, not a residual to accept.
_LIPSCHITZ_SETTLE_CAP = 64


def runway_strip_longitudinal_clamp(points, alts, axis, max_slope,
                                    pinned=None, inside=None,
                                    max_passes=8, arc_rate_per_m=None):
    """THE generation-binding half of the abeam-longitudinal law: return
    ``alts`` with every strip-band run made ``max_slope``-Lipschitz along
    the runway axis.

    THE LAW (Annex 14 §3.4.13 / AC 150/5300-13B §3.16.5 item 1): between the
    ends, two points of the graded strip at along-axis separation ``Δs`` may
    differ in elevation by at most ``max_slope · Δs``.

    THE CONSTRUCTION — the two-sided neighbour clamp, swept forward and
    backward over each run until it stops moving:

        forward   z[i] = clamp( z[i], z[i-1] − L·ds , z[i-1] + L·ds )
        backward  z[i] = clamp( z[i], z[i+1] − L·ds , z[i+1] + L·ds )

    ``ds`` is the ALONG-AXIS separation of the consecutive pair, so the
    metric is the chain's own along-axis path length — exactly the
    separation the validator's consecutive-pair reader measures, which is
    what lets the two halves agree pair by pair even where a frontage
    doubles back.  Three properties matter:

      * IDENTITY ON LAWFUL GROUND.  A run that already satisfies the law is
        inside every clamp band, so nothing is written — the law moves only
        ground that is actually unlawful and never "smooths" a compliant
        profile.
      * LOCALITY.  A single unlawful spike is brought down (a pit brought
        up) to what its neighbours support; the compliant neighbours do NOT
        move.  This is the same physical model — and the same shape of
        sweep — as ``adjacent_ground_supported_depths``' daylight bench,
        and it is why the L∞-minimal mid-envelope form was rejected: that
        one splits the difference, lifting lawful flat ground halfway to an
        isolated spike.
      * SYMMETRY.  Humps are cut and pits filled by the SAME rule; the law
        has no built-in bias toward cut or fill.

    The sweep pair is iterated to a fixed point (``max_passes``, default 8);
    each pass can only move a value INTO a neighbour's band, so the total
    violation is non-increasing.  The Lipschitz pair ALONE converges (a
    forward and a backward sweep is the exact one-dimensional Lipschitz
    regularization); the cap exists so a pathological chain cannot spin.

    THE ARC COMPOSITION AND ITS SETTLE (2026-08-05).  Interleaving the arc
    sweep breaks that convergence: the arc pass moves the middle vertex out
    of a neighbour band, the next Lipschitz pass pulls it back, and the two
    families cycle.  MEASURED on the composed KCLT patch, unpinned, against
    ``strip_longitudinal_breaches`` over ``check_grade``'s own runs and
    ruleset:

        emitted                        slope 962   arc 992
        this clamp, max_passes 8       slope 482   arc 528
        this clamp, max_passes 64      slope 485   arc 505
        this clamp, max_passes 1000    slope 485   arc 505
        slope law alone                slope   0   arc 930

    The cap was never the limit — the alternation has a NON-FEASIBLE fixed
    point, so raising it buys nothing (485/505 at 64 and at 1000).  A
    "caution limit" that hides a divergent construction is not a budget, it
    is a defect (owner, the caution-limit re-derivation).

    So the composed form ENDS with the Lipschitz pair run to its OWN fixed
    point, no arc pass in the loop and no borrowed cap: the slope law is
    then ATTAINED rather than approached, and the arc residue is honest and
    smaller than the cycling form left (measured: slope 0, arc 484).  The
    settle keeps every documented property — it is the same coordinate-
    restricted, locality-preserving sweep, so lawful neighbours still do
    not move.  The arc residue that survives is the arc LAW's own question
    (its rate constant is the flagged provisional under ICAO, and under FAA
    it is AC §3.16.5 item 5, whose own list is the BEYOND-the-ends regime
    while item 1 sends the between-the-ends ground to the runway's rules) —
    not this construction's.

    ``pinned`` (optional, aligned) marks vertices that may NOT move — the
    pavement-EDGE weld row, whose values are the runway's own solved profile
    and are lawful by that profile's own law (``RUNWAY_MAX_GRADE`` and the
    vertical-curve rules).  A pinned vertex still participates as a SOURCE
    in both envelopes, so free ground is pulled toward the lawful pavement
    line rather than toward the DEM; it is simply written back unchanged.
    (The emitter re-asserts weld and adopted values immediately after this
    call in any case — pinning here is what makes the clamp AGREE with that
    re-assertion instead of fighting it.)

    ``arc_rate_per_m`` (§A3(b), the strip's CURVATURE law — ICAO Annex 14
    §3.4.14 "as gradual as practicable", FAA AC §3.16.5 item 5 ±2 % per
    100 ft) additionally bounds how fast the run's GRADE may change, in
    grade units per metre.  Pass ``config.ruleset_strip_arc_rate_per_m
    (ruleset)``.  The two laws are composed by alternating their sweeps
    to a joint fixed point: the Lipschitz sweep can only pull a value
    INTO a neighbour band and the arc sweep only reduces a
    second-difference excess, so neither re-creates the other's
    violation without bound and the pair converges (the pass cap is the
    same pathological-chain guard).  ``None`` (default) ⇒ the slope law
    alone, exactly as the RSA round landed it.

    ``inside`` and the run splitting are ``runway_strip_longitudinal_runs``
    verbatim.  Pure, deterministic, no geometry dependencies; the validator
    twin (``check_grade._check_strip_longitudinal_grade``) reads the SAME
    runs with the SAME slope, so emitted ground and checked ground cannot
    drift.
    """
    out = [None if a is None else float(a) for a in alts]
    ux, uy = float(axis[0]), float(axis[1])
    norm = (ux * ux + uy * uy) ** 0.5
    if norm < 1e-12:
        return out
    ux, uy = ux / norm, uy / norm
    limit = float(max_slope)
    if limit <= 0.0:
        return out
    for run in runway_strip_longitudinal_runs(points, axis, inside):
        idx = [i for i in run if out[i] is not None]
        if len(idx) < 2:
            continue
        s = [points[i][0] * ux + points[i][1] * uy for i in idx]
        z = [float(out[i]) for i in idx]
        n = len(idx)
        free = [not (pinned is not None and i < len(pinned) and pinned[i])
                for i in idx]
        span = [limit * abs(s[k] - s[k - 1]) for k in range(1, n)]
        for _ in range(int(max_passes)):
            moved = False
            for k in range(1, n):
                if not free[k]:
                    continue
                lo, hi = z[k - 1] - span[k - 1], z[k - 1] + span[k - 1]
                new = lo if z[k] < lo else (hi if z[k] > hi else z[k])
                if new != z[k]:
                    z[k] = new
                    moved = True
            for k in range(n - 2, -1, -1):
                if not free[k]:
                    continue
                lo, hi = z[k + 1] - span[k], z[k + 1] + span[k]
                new = lo if z[k] < lo else (hi if z[k] > hi else z[k])
                if new != z[k]:
                    z[k] = new
                    moved = True
            if arc_rate_per_m and _arc_rate_pass(
                    s, z, free, float(arc_rate_per_m)):
                moved = True
            if not moved:
                break
        if arc_rate_per_m:
            # THE SETTLE (see the docstring).  Run the Lipschitz pair on
            # its own to ITS fixed point, so the slope law is attained
            # instead of left at whatever phase the arc alternation
            # stopped in.  The bound here is the law's own demand — the
            # loop exits when nothing moves — and ``_LIPSCHITZ_SETTLE_CAP``
            # is a non-termination guard against a pathological chain,
            # never a convergence budget.
            for _ in range(_LIPSCHITZ_SETTLE_CAP):
                moved = False
                for k in range(1, n):
                    if not free[k]:
                        continue
                    lo, hi = z[k - 1] - span[k - 1], z[k - 1] + span[k - 1]
                    new = lo if z[k] < lo else (hi if z[k] > hi else z[k])
                    if new != z[k]:
                        z[k] = new
                        moved = True
                for k in range(n - 2, -1, -1):
                    if not free[k]:
                        continue
                    lo, hi = z[k + 1] - span[k], z[k + 1] + span[k]
                    new = lo if z[k] < lo else (hi if z[k] > hi else z[k])
                    if new != z[k]:
                        z[k] = new
                        moved = True
                if not moved:
                    break
        for k, i in enumerate(idx):
            if free[k]:
                out[i] = z[k]
    return out


def runway_end_envelope(
        distance_beyond_pavement_m: float,
        *,
        governed_length_beyond_pavement_m: float,
        entry_grade: float = 0.0,
        pavement_beyond_end_m: float = 0.0,
        resa_reach_m: Optional[float] = None,
        ruleset=None,
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
            [d], entry_grade, pavement_beyond_end_m, ruleset)[0]
        floor = -depth

    ceiling: Optional[float] = None
    if d < float(resa_reach_m):
        ceiling = RUNWAY_END_RESA_MAX_SLOPE * d

    return (floor, ceiling)


# ── §A1 — RESA / END-CORRIDOR TRANSVERSE LAW ─────────────────────────
# The gap the reg-families round names exactly: the LATERAL strip
# transverse law exists (zone 1 lip + zone 2 band above), and the END
# corridor carries only the LONGITUDINAL skirt law — ACROSS-corridor
# grades beyond a runway end were unbound AND unread.

def resa_transverse_band(distance_beyond_pavement_m: float,
                         code_letter=None, ruleset=None) -> tuple:
    """``(min_down, max_abs)`` for the ACROSS-corridor profile of the
    end corridor at ``distance_beyond_pavement_m`` past the runway end.

    ``min_down`` is a MANDATORY fall (``None`` where the authority
    mandates none); ``max_abs`` is the symmetric magnitude cap.

    THE LAW.  FAA AC 150/5300-13B §3.16.5 item 6 puts the RSA's
    transverse under Table 3-6 "along the runway up to 200 feet (61 m)
    beyond the runway end", where S-3 reads 1.5-5.0 % (AAC A/B) and
    1.5-3.0 % (AAC C/D/E).  Beyond 61 m the AC states no transverse
    number in text; Figure 3-35 shows ±5.0 % across the RSA width, which
    is what binds there.  ICAO Annex 14 §3.5.11: "The transverse slopes
    of a runway end safety area should not exceed an upward or downward
    slope of 5 per cent" — ONE symmetric cap, no near-zone column and no
    mandatory fall.
    """
    rs = get_ruleset(ruleset)
    near_zone = rs.end_skirt_near_zone_m
    d = max(0.0, float(distance_beyond_pavement_m))
    if (near_zone is not None and d <= float(near_zone)
            and rs.resa_transverse_near_max is not None):
        near_min = (rs.resa_transverse_near.value(None, code_letter)
                    if rs.resa_transverse_near is not None else None)
        return (near_min,
                rs.resa_transverse_near_max.value(None, code_letter))
    return (None, rs.resa_transverse_max)


def resa_transverse_envelope(distance_beyond_pavement_m: float,
                             distance_from_axis_m: float,
                             code_letter=None,
                             ruleset=None) -> tuple:
    """The lawful ACROSS-corridor corridor as a signed ``(floor_offset,
    ceiling_offset)`` relative to the end corridor's CENTRELINE elevation
    at the same along-station, at lateral offset
    ``distance_from_axis_m``.

    Exactly the shape ``adjacent_ground_envelope`` uses, so one emitter
    and one validator can read both: within a mandatory-down band the
    ceiling is strictly below 0 (a FLAT cross-section is unlawful and is
    regraded to the drainage fall); with no mandated fall the corridor is
    the symmetric ±cap.  Pure, deterministic, no geometry deps.
    """
    t = abs(float(distance_from_axis_m))
    if t <= 0.0:
        return (0.0, 0.0)
    min_down, max_abs = resa_transverse_band(
        distance_beyond_pavement_m, code_letter, ruleset)
    if min_down is None:
        return (-max_abs * t, max_abs * t)
    return (-max_abs * t, -float(min_down) * t)


def resa_transverse_clamp(offsets_m, alts, axis_alt,
                          distance_beyond_pavement_m,
                          code_letter=None, ruleset=None):
    """THE generation-binding half of §A1: return ``alts`` with every
    across-corridor station pulled into
    :func:`resa_transverse_envelope`.

    ``offsets_m`` are signed lateral offsets from the extended centreline
    (same order as ``alts``); ``axis_alt`` is the corridor centreline's
    own elevation at this along-station.  A station already inside the
    corridor is written back UNCHANGED (identity on lawful ground — the
    same property the longitudinal clamp documents); an unlawful one
    moves the LEAST amount that makes it lawful.
    """
    out = []
    for t, z in zip(offsets_m, alts):
        if z is None:
            out.append(None)
            continue
        floor, ceiling = resa_transverse_envelope(
            distance_beyond_pavement_m, t, code_letter, ruleset)
        rel = float(z) - float(axis_alt)
        if floor is not None and rel < floor:
            rel = floor
        if ceiling is not None and rel > ceiling:
            rel = ceiling
        out.append(float(axis_alt) + rel)
    return out


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
        distance_m: float,
        lip_width_m: Optional[float] = None,
        lip_min_down: Optional[float] = None,
        lip_max_down: Optional[float] = None,
        up_slope: Optional[float] = None,
        shoulder: Optional[tuple] = None,
        zone3_ceiling_override=None) -> tuple[Optional[float], Optional[float]]:
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

    ``shoulder`` (§B1) inserts a PAVED-SHOULDER sub-band of
    ``(width_m, min_down, max_down)`` between the pavement edge and zone 1
    where the surface declares a paved shoulder: the shoulder is pavement,
    so it takes the shoulder transverse band (FAA Table 3-6 S-2 1.5-5 %;
    ICAO §3.2.3 flush ≤2.5 %) and the zone-1 lip then starts at the
    SHOULDER's outer edge, which is where the paved surface actually ends.
    ``None`` (default) ⇒ the pre-§B1 profile verbatim.

    ``zone3_ceiling_override`` (§A2) replaces the flat ≤5 % rising cap
    with a callable ``f(d_beyond_band_m) -> ceiling_offset_from_band`` —
    the hook the FAA ROFA back slope binds through.
    """
    lip = (ADJACENT_GROUND_LIP_WIDTH_M if lip_width_m is None
           else float(lip_width_m))
    lip_min = (ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE if lip_min_down is None
               else float(lip_min_down))
    lip_max = (ADJACENT_GROUND_LIP_MAX_DOWN_SLOPE if lip_max_down is None
               else float(lip_max_down))
    up = (ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE if up_slope is None
          else float(up_slope))
    # NO MANDATORY FALL (W2, reg-set ruling 1).  An authority that
    # mandates no downward grading across its graded strip supplies
    # ``None`` for ``band_min_down``, and the corridor answers that by
    # holding the CEILING flat across zone 2 instead of dropping it —
    # flat ground inside the strip becomes lawful, which is precisely
    # what "the ICAO ruleset DROPS the mandatory-DOWN band" means.  The
    # MAXIMUM (``band_max_down``, the floor) is untouched: an authority
    # dropping its minimum has not stopped capping how steep the fall
    # may be.  ``0.0`` is the arithmetic spelling of "no mandate" here,
    # and it keeps every bound continuous in ``d`` exactly as before.
    band_min_down = 0.0 if band_min_down is None else float(band_min_down)
    if distance_m <= 0.0:
        return (0.0, 0.0)                       # flush at the edge
    if distance_m >= reach_m:
        return (None, None)

    # ZONE 0 (§B1) — the PAVED SHOULDER, when one is declared.
    sh_w = sh_ceiling = sh_floor = 0.0
    if shoulder:
        sh_w, sh_min, sh_max = (float(shoulder[0]), shoulder[1],
                                float(shoulder[2]))
        # A flush shoulder (ICAO) has no mandated fall: its ceiling stays
        # at the pavement level and only the MAXIMUM binds.
        sh_min = 0.0 if sh_min is None else float(sh_min)
        if distance_m <= sh_w:
            return (-sh_max * distance_m, -sh_min * distance_m)
        sh_ceiling = -sh_min * sh_w
        sh_floor = -sh_max * sh_w

    d = distance_m - sh_w
    if d <= lip:                                # ZONE 1 — drainage lip
        return (sh_floor - lip_max * d, sh_ceiling - lip_min * d)
    lip_ceiling = sh_ceiling - lip_min * lip
    lip_floor = sh_floor - lip_max * lip
    graded = max(0.0, float(graded_half_width_m) - sh_w)
    if d <= graded:                             # ZONE 2 — graded band
        ceiling = lip_ceiling - band_min_down * (d - lip)
        floor = lip_floor - band_max_down * (d - lip)
        return (floor, ceiling)
    band_ceiling = lip_ceiling - band_min_down * (graded - lip)
    beyond = d - graded                                              # ZONE 3
    if zone3_ceiling_override is not None:
        return (None, band_ceiling + zone3_ceiling_override(beyond))
    return (None, band_ceiling + up * beyond)


def rofa_back_slope_ceiling(code_letter, ruleset=None):
    """§A2 — the FAA ROFA BACK SLOPE as a zone-3 ceiling function, or
    ``None`` where the family does not exist (every non-FAA ruleset).

    Returns ``f(d_beyond_graded_band_m) -> ceiling_offset_m``, measured
    from the graded band's own endpoint ceiling.  THE LAW (AC
    150/5300-13B Table 3-7): S-5 gives a back-slope RATIO by Airplane
    Design Group — 8:1 (ADG I-II), 10:1 (III-IV), 16:1 (V-VI), run:rise,
    so 8:1 is a 12.5 % maximum rise — and D-1 gives the RUN over which it
    is measured (25/40/59/86/107/131 ft = 7.6/12.2/18.0/26.2/32.6/
    39.9 m).  Beyond that run the AC states nothing further, so the
    corridor reverts to the generic ≤5 % rising cap
    (``ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE``) continuing from
    wherever the back slope left off — the bound is CONTINUOUS in ``d``,
    like every other zone transition here.

    S-4, the ≤0 % SIDE slope, is NOT bound: the owner approved the FAA
    existing-runway exemption (docs/RULINGS.md 2026-08-02, "ROFA
    exemption approved").  This function is the RISING side only.
    """
    rs = get_ruleset(ruleset)
    ratios = rs.rofa_back_slope_ratio_by_adg
    runs = rs.rofa_back_slope_run_m_by_adg
    if not ratios or not runs:
        return None
    key = str(code_letter).upper() if code_letter else "C"
    ratio = ratios.get(key)
    run = runs.get(key)
    if not ratio or not run:
        return None
    rise_per_m = 1.0 / float(ratio)
    run = float(run)
    generic = rs.ungraded_strip_max_up_slope

    def _ceiling(beyond_m: float) -> float:
        d = max(0.0, float(beyond_m))
        if d <= run:
            return rise_per_m * d
        return rise_per_m * run + generic * (d - run)

    return _ceiling


def adjacent_ground_envelope(
        role: str, code_number: Optional[int], code_letter: Optional[str],
        distance_from_pavement_edge_m: float,
        ruleset=None, shoulder_width_m: Optional[float] = None,
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

    ``ruleset`` (phase B) keys every value below to the airport's own
    authority: the graded half-width (§4 row 6), the zone-2 band (rows
    7/8 — currently blended on BOTH rulesets, see owner question 1), the
    rising-ground cap (row 9) and, under the FAA ruleset, the ROFA BACK
    SLOPE replacing the flat ≤5 % rise inside its D-1 run (§A2).

    ``shoulder_width_m`` (§B1) declares a PAVED shoulder of that width at
    the pavement edge; within it the cross-section takes the ruleset's
    shoulder transverse band and the zone law starts beyond it.  ``None``
    ⇒ no shoulder sub-band (the pre-§B1 profile).

    Raises ``ValueError`` for an unrecognised role (a law must not silently pick
    a corridor for a surface it does not model).
    """
    d = distance_from_pavement_edge_m
    rs = get_ruleset(ruleset)
    shoulder = None
    if shoulder_width_m and float(shoulder_width_m) > 0.0:
        sh_min, sh_max = ruleset_shoulder_transverse_band(rs)
        if sh_max:
            shoulder = (float(shoulder_width_m), sh_min, sh_max)
    if role in _ADJACENT_RUNWAY_ROLES:
        if code_number is None:
            raise ValueError("runway adjacent-ground envelope needs code_number")
        return _adjacent_strip_envelope(
            ruleset_strip_half_width_m(code_number, code_letter, rs),
            _w2_strip_band_min_down(rs),
            ruleset_strip_band_max_down_slope(code_number, rs),
            CLEARANCE_MAX_REACH_M["runway"], d,
            lip_width_m=rs.strip_lip_width_m,
            lip_min_down=rs.strip_lip_min_down_slope,
            lip_max_down=rs.strip_lip_max_down_slope,
            up_slope=rs.ungraded_strip_max_up_slope,
            shoulder=shoulder,
            zone3_ceiling_override=rofa_back_slope_ceiling(code_letter, rs))
    if role in _ADJACENT_TAXIWAY_ROLES:
        widths = rs.taxiway_strip_graded_half_width_m
        half = (float(widths.get(str(code_letter).upper(), 12.5))
                if widths and code_letter
                else taxiway_strip_graded_half_width_for_letter(code_letter))
        lip_w, lip_lo, lip_hi = _w2_paved_edge_lip(rs)
        return _adjacent_strip_envelope(
            half,
            rs.taxiway_strip_band_min_down_slope,
            rs.taxiway_strip_band_max_down_slope,
            CLEARANCE_MAX_REACH_M["taxiway"], d,
            lip_width_m=lip_w,
            lip_min_down=lip_lo,
            lip_max_down=lip_hi,
            up_slope=rs.ungraded_strip_max_up_slope,
            shoulder=shoulder)
    if role in _ADJACENT_APRON_ROLES:
        # Aprons ride the maneuvering-network reach (taxiway).
        reach = CLEARANCE_MAX_REACH_M["taxiway"]
        if d <= 0.0:
            return (0.0, 0.0)
        if d >= reach:
            return (None, None)
        if fabric_flags.on("O4_FABRIC_W2_RETIRE_APRON_SURROUND"):
            # ── THE APRON SURROUND RETIRES (W2; reg-set §5.1 T2/T3,
            # RULINGS 2026-08-08 reg-set ruling 4) ────────────────────
            # "Nothing mandates them; the drape takes apron surroundings
            # on both rulesets."  AC ¶5.9.2's 3 m 1-3 % shoulder and its
            # 3-5 % beyond-shoulder continuation sit under a *Recommended
            # Practices* heading (read directly, PV-2026-08-08), and
            # Annex 14 §3.13 / CS ADR-DSN Ch. E govern nothing at all
            # beyond an apron edge.
            #
            # WHAT SURVIVES, and this is the verification pass's nuance
            # (reg-set §5.1 closing paragraph — "retiring the apron
            # SHOULDER BAND is not the same act as retiring the apron
            # EDGE"): the FAA ¶4.14.2 item-4 lip, which is written for
            # "an unpaved surface adjacent to a paved surface" and so
            # reaches an apron edge like any other paved edge.  Under a
            # ruleset that states no such lip (ICAO) the corridor is
            # zone-3 from the edge — floor free, ceiling rising at the
            # ungraded cap — i.e. the drape, which is the point.
            lip_w, lip_lo, lip_hi = _w2_paved_edge_lip(rs)
            up = rs.ungraded_strip_max_up_slope
            if not lip_w:
                return (None, up * d)
            if d <= lip_w:
                return (-lip_hi * d, -lip_lo * d)
            return (None, -lip_lo * lip_w + up * (d - lip_w))
        # PRE-W2: the 3 m shoulder, then zone-3 semantics immediately.
        if d <= APRON_SHOULDER_WIDTH_M:
            return (-APRON_SHOULDER_MAX_DOWN_SLOPE * d,
                    -APRON_SHOULDER_MIN_DOWN_SLOPE * d)
        shoulder_ceiling = -APRON_SHOULDER_MIN_DOWN_SLOPE * APRON_SHOULDER_WIDTH_M
        up = rs.ungraded_strip_max_up_slope
        return (None, shoulder_ceiling + up * (d - APRON_SHOULDER_WIDTH_M))
    if role in _ADJACENT_SERVICE_ROLES:
        # ── THE SERVICE-ROAD SHADOW RETIRES (W2; reg-set §5.1 T5) ────
        # ``docs/STANDARDS.md`` states it outright: the 15 m cut-only
        # flat shadow is a "design choice, NOT an AASHTO mandate", and no
        # aviation authority regulates service roads at all.  Under the
        # fabric model unregulated ground is NOTHING, so the corridor is
        # ungoverned in both directions and the drape takes it.
        if fabric_flags.on("O4_FABRIC_W2_RETIRE_SERVICE_SHADOW"):
            return (None, None)
        # PRE-W2 cut-only flat shadow: cut anything above the edge within the
        # 15 m band, never fill (floor free).  CLEARANCE_LATERAL_MAX_SLOPE == 0
        # ⇒ the ceiling stays at the edge level across the whole band.
        if d >= CLEARANCE_MAX_REACH_M["service"]:
            return (None, None)
        return (None, CLEARANCE_LATERAL_MAX_SLOPE * d)
    raise ValueError(f"adjacent_ground_envelope: unmodelled role {role!r}")


def _w2_strip_band_min_down(rs):
    """The RUNWAY graded strip's minimum mandatory DOWN slope — each
    authority's own mandate under W2, the pre-W2 blend with the flag off.

    ``O4_FABRIC_W2_ICAO_STRIP_AUTHORITY`` (default ON) is
    ``config.RULESET_W2_FLIPS`` entry 1: the LIVE field
    ``strip_band_min_down_slope`` carries the 2026-07-08 blended 1.5 % on
    BOTH rulesets; ``strip_band_min_down_slope_authority`` carries what
    each authority actually mandates — 1.5 % for the FAA (Table 3-6 S-3,
    unchanged, so KCLT does not move) and ``None`` for ICAO, which
    mandates no fall across the graded strip at all.

    RULINGS 2026-08-08 reg-set ruling 1, flagged PROVISIONAL and
    explicitly gate-revertable for the owner's sim look at a strip
    without the band.
    """
    if fabric_flags.on("O4_FABRIC_W2_ICAO_STRIP_AUTHORITY"):
        return rs.strip_band_min_down_slope_authority
    return rs.strip_band_min_down_slope


def _w2_paved_edge_lip(rs):
    """``(width_m, min_down, max_down)`` for a TAXIWAY / TAXILANE / APRON
    edge — the second lip family, or ``(0.0, 0.0, 0.0)`` where the
    authority states none.

    ``O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY`` (default ON) is
    ``config.RULESET_W2_FLIPS`` entries 2 and 3.  Reg-set finding F-10:
    the AC states TWO distinct lips and the repo applied the RUNWAY one
    (3 m at 3-5 %, Fig. 3-33 Detail A) to every edge.  The paved→unpaved
    edge of a taxiway, taxilane or apron takes ¶4.14.2 *Standards* item 4
    instead — 5 ±0.5 % over ≥3 m, i.e. 4.5-5.5 % — carved OUT of the TSA
    band by item 5, which is why it is a near zone here and not an
    alternative to the band.  ICAO states no taxiway lip whatever (F-3,
    absence verified by full read of §3.11.5 / D.330(b)), so on that
    ruleset the near zone is ZERO WIDE and zone 2 starts at the edge.

    A zero width is spelled ``0.0``, never ``None``: ``None`` means "not
    stated, use the house default" to ``_adjacent_strip_envelope``, and
    that is the opposite of what an authority's silence means here.
    """
    if not fabric_flags.on("O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY"):
        return (rs.strip_lip_width_m, rs.strip_lip_min_down_slope,
                rs.strip_lip_max_down_slope)
    width = rs.taxiway_lip_width_m
    if not width:
        return (0.0, 0.0, 0.0)
    return (float(width), float(rs.taxiway_lip_min_down_slope),
            float(rs.taxiway_lip_max_down_slope))


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
    # F3b (gap-conformance spec, 2026-08-16): THE STAGED SPINE LAW.
    # Within the pavement-conformance margin the spine is PINNED to the
    # edge value — the owner's ruling ("close to pavement, match the
    # pavement solved elevations") — and the dam clause applies only in
    # the INTERIOR beyond it.  One law, both readers: gap_fill's
    # interval composition and check_grade's dam predicate stage on the
    # same lateral distance this signature already carries.
    from .config import GAP_PAVEMENT_CONFORM_MARGIN_M
    if distance_from_pavement_edge_m <= float(GAP_PAVEMENT_CONFORM_MARGIN_M):
        # CEILING-ONLY in the graph: a (0, 0) hard pin exported the
        # band station as a rigid anchor into the solver's pairwise
        # slab and contradicted other regimes (measured at HECA:
        # 677 nodes, a uniform 1.8009 m inversion).  The pin's
        # EQUALITY lives in the emitter walk and the validator's band
        # predicate; the graph only needs "never above the edge" —
        # the dam clause's in-band form.  The lateral floor (the
        # crater guard) stays.
        floor_off, _lat_ceil = adjacent_ground_envelope(
            role, code_number, code_letter, distance_from_pavement_edge_m)
        ceil_off = 0.0
        if floor_off is not None and float(floor_off) > ceil_off:
            floor_off = ceil_off
        return floor_off, ceil_off
    floor_off, ceil_off = adjacent_ground_envelope(
        role, code_number, code_letter, distance_from_pavement_edge_m)
    fall = -float(DRAINAGE_SPINE_MIN_FALL_M)
    ceil_off = fall if ceil_off is None else min(float(ceil_off), fall)
    if floor_off is not None and float(floor_off) > ceil_off:
        floor_off = ceil_off
    return floor_off, ceil_off


def drainage_spine_parent_family(role, *, long_side_m=None, code_letter=None):
    """``(role, code_number, code_letter)`` — THE family key
    :func:`drainage_spine_envelope` needs for ONE bounding pavement of a
    drainage spine.

    ONE resolution, both readers (``gap_fill._parent_family_code`` and
    ``check_grade``'s dam reader).  Neither reader receives an apt.dat row-100
    axis here, so a runway's code NUMBER is keyed off the shape's own longest
    vertex chord (``long_side_m``); a taxiway takes its code LETTER; an apron
    (and anything else the envelope models) takes neither.  A role the
    envelope does not model is passed through unchanged so the envelope
    raises its own ``ValueError`` rather than being silently re-homed here.
    """
    if role in _ADJACENT_RUNWAY_ROLES:
        return (role, runway_code_number(float(long_side_m or 0.0)), None)
    if role in _ADJACENT_TAXIWAY_ROLES:
        return (role, None, code_letter)
    return (role, None, None)


def drainage_spine_interval(parents, *, bench_slope):
    """THE drainage interval of one spine station —
    ``(lo, hi, residual_m, handoff)``.

    ``parents`` is ``[(distance_m, floor_abs|None, ceil_abs|None), …]``, the
    station's bounding parents (``drainage_spine_parents`` order, nearest
    first) with each parent's :func:`drainage_spine_envelope` offsets already
    added to its own EDGE elevation.  The composition is the historical one —
    ``lo = max(floors)``, ``hi = min(ceils)`` — until the two disagree.

    THE GRADED HANDOFF (owner ruling 2026-08-18, "CRATER-VS-DAM RESOLVES BY
    GRADED HANDOFF"; spec ``docs/specs/gap-conformance-spec.md`` amendment
    F3c).  Far from BOTH parents the higher parent's crater FLOOR (the
    anti-trench guard) can stand above the lower parent's dam CEILING
    ("below the lower adjacent pavement") — the intervals are DISJOINT and
    neither clause hard-wins.  Measured at HECA way ``-13464``
    (30.116941,31.443884): runway floor 140.99 − 1.701 = 139.29 against a dam
    ceiling 0.3 m under an apron 6.0 m lower.  The 2026-07-09 fallback took
    the NEARER parent's own interval and left the spine 4.31 m proud of the
    lower edge — 34 of HECA's 70 surviving ``drainage_spine`` rows.

    The ruled law: the spine DESCENDS from one authority to the other.  The
    station's value target is the monotone handoff — interpolate from the
    higher-floor parent's floor toward the lower-ceiling parent's ceiling by
    relative distance ``w = d_high / (d_high + d_low)`` — clamped to a lawful
    descent from the HIGHER side (``bench_slope``, the clause-3 cone
    constant).  Where the separation is too short to descend the whole drop
    lawfully the descent runs AT the cap and the shortfall against the dam
    ceiling is RETURNED as ``residual_m`` (a PASS-with-residual below the
    materiality floor, a census row above it — never a silent nearer-parent
    value).  The interval collapses to that value: ``lo == hi ==`` the
    handoff, so every consumer's own clamp lands on it and the clause-3
    monotone walk still produces the final profile around it.

    ``handoff`` is True only when the graded handoff was composed, so a
    caller never has to re-derive "were the intervals disjoint" from the
    returned bounds (a pinned parent can make ``lo == hi`` lawfully).
    ``residual_m`` is 0.0 whenever the intervals intersect (the composition is
    byte-identical to the pre-F3c one there) and whenever the handoff descends
    freely — a descent still in progress is lawful, and the validator's cone
    allowance already prices it.
    """
    floors = [p[1] for p in parents if p[1] is not None]
    ceils = [p[2] for p in parents if p[2] is not None]
    lo = max(floors) if floors else None
    hi = min(ceils) if ceils else None
    if lo is None or hi is None or lo <= hi or len(parents) < 2:
        return lo, hi, 0.0, False
    # DISJOINT.  ``drainage_spine_envelope`` already collapses a
    # self-conflicting parent to a pin, so the binding floor and the binding
    # ceiling are necessarily different parents; if a caller hands in bounds
    # that violate that, fall back to the historical nearer-parent interval
    # rather than inventing a handoff across zero separation.
    hi_p = max((p for p in parents if p[1] is not None), key=lambda p: p[1])
    lo_p = min((p for p in parents if p[2] is not None), key=lambda p: p[2])
    if hi_p is lo_p:
        return parents[0][1], parents[0][2], 0.0, False
    d_high = max(0.0, float(hi_p[0]))
    d_low = max(0.0, float(lo_p[0]))
    f_high = float(hi_p[1])
    c_low = float(lo_p[2])
    span = d_high + d_low
    drop = f_high - c_low               # > 0 by construction
    residual = 0.0
    if span <= 0.0:
        value = f_high
    elif drop > float(bench_slope) * span:
        # THE SEPARATION IS TOO SHORT: descend AT the cap from the higher
        # side and report what the dam ceiling is still owed.
        value = f_high - float(bench_slope) * d_high
        residual = max(0.0, value - c_low)
    else:
        value = f_high - drop * (d_high / span)
    return value, value, residual, True


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
    #
    # THE MANDATORY-FALL READ IS THE LATERAL LAW'S (W2, reg-set ruling 1).
    # The anchor value is only continuous with zone 3 if it is computed
    # from the SAME band the zone-3 expression accumulated from — and
    # under ``O4_FABRIC_W2_ICAO_STRIP_AUTHORITY`` that band no longer
    # falls on the ICAO ruleset.  Reading the module constant here left
    # the composed ceiling stepping 0.555 m at the handover (measured:
    # transitional -0.645 vs lateral -0.090 at code 2), which is exactly
    # the wall-between-two-active-cut-bands class the continuity ruling
    # above exists to prevent.  Flag OFF the accessor returns
    # ``strip_band_min_down_slope``, which IS
    # ``RUNWAY_STRIP_BAND_MIN_DOWN_SLOPE`` on both rulesets (pinned by
    # tests/test_fabric_reg_set_w1.py), so the OFF arm is unchanged.
    _floor_at_s, ceiling_at_s = _adjacent_strip_envelope(
        RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code_number],
        _w2_strip_band_min_down(get_ruleset(None)),
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


def crown_pair_offset_interval(drop_a, drop_b):
    """THE crown target of ``z_a − z_b`` as an INTERVAL ``(lo, hi)`` — every
    designed step the field is compatible with.  ``lo == hi`` whenever the
    field states the answer; a WIDER interval means an endpoint is
    UNDECLARED, and an undeclared endpoint is UNKNOWN, NOT ON THE RIDGE.

    ``drop_a`` / ``drop_b`` are the endpoints' drops as READ FROM THE FIELD:
    a float when the node carries a declared drop, ``None`` when the node is
    absent from it.  The distinction is the whole point, so callers must pass
    ``field.get(nid)`` and NOT ``field.get(nid, 0.0)``.

    WHY (measured on the 2026-08-16 HECA battery patch).  Defaulting an
    absent endpoint to 0.0 asserts it sits on the crown RIDGE, which
    manufactures an expected step equal to the other endpoint's full drop.
    HECA's runway rings carry 94 undeclared vertices of 521 — post-solve
    inserts and welds ``crown.extend_field_to_new_ring_nodes`` did not reach,
    with an EMPTY ``crown_centerline`` field so the Phase-0 centreline skip
    never fires either.  920 of that patch's 515,260 constrained pairs pair a
    declared NONZERO drop against an undeclared node, and three of them
    became census rows whose RAW grades (1.004 %, 1.101 %, and an apron's)
    are all comfortably under cap.  Nothing in the SOLVER made that claim:
    ``grade_graph.build_unified_graph`` constrains only
    ``SOFT_VISIBILITY_ROLES`` and ``plane_constraints`` — the runway ring's
    pair set — has no caller outside ``tools/check_grade.py``.  The expected
    step was minted by the reader alone.

    THE INTERVAL, and why it is an interval rather than a skip.  The absent
    endpoint's true drop lies somewhere between 0 (the ridge) and the
    declared neighbour's own drop (a full-drop edge node); every value
    between is a possible declaration, so the designed step lies between
    ``crown_pair_offset(known, 0)`` and ``0``.  A caller CLAMPS the measured
    ``Δz`` into that interval: a pair the field cannot price reports no
    excess, and a pair that is over cap under EVERY compatible declaration
    still reports its excess in full.  Dropping such pairs outright would
    blind the census — measured on the same patch, three of the six affected
    rows are over cap on their raw grade too, and those are real.

      * both endpoints declared     → ``(t, t)``, the crown target, as before;
      * NEITHER declared            → ``(0.0, 0.0)``, as before (an uncrowned
        patch, or an uncrowned region of a crowned one, is byte-identical);
      * one declared at ZERO drop   → ``(0.0, 0.0)``: a declared ridge node
        and an undeclared one imply no step either way;
      * one declared NONZERO, other absent → the ordered pair spanning 0 and
        the full-drop target.
    """
    a_known = drop_a is not None
    b_known = drop_b is not None
    if a_known and b_known:
        t = crown_pair_offset(float(drop_a), float(drop_b))
        return (t, t)
    if not a_known and not b_known:
        return (0.0, 0.0)
    if a_known:
        t = crown_pair_offset(float(drop_a), 0.0)
    else:
        t = crown_pair_offset(0.0, float(drop_b))
    if abs(t) <= 1e-9:
        return (0.0, 0.0)
    return (min(0.0, t), max(0.0, t))


def crown_pair_offset_clamped(drop_a, drop_b, delta_z):
    """``(offset, unpriceable)`` — the crown target to judge ``delta_z``
    (``z_a − z_b``) against, and whether the field left it UNSTATED.

    The offset is ``delta_z`` clamped into
    :func:`crown_pair_offset_interval`, so ``|delta_z − offset|`` is the
    excess under the MOST FAVOURABLE declaration the field is compatible
    with.  ``unpriceable`` is True when the interval is wider than a point
    AND ``delta_z`` fell inside it — the case where a reader that defaulted
    the absent endpoint to the ridge would have minted a row out of a
    declaration gap.  ONE call, both facts, so no reader can take the offset
    without being able to report the gap.
    """
    lo, hi = crown_pair_offset_interval(drop_a, drop_b)
    if lo == hi:
        return lo, False
    z = float(delta_z)
    if z < lo:
        return lo, False
    if z > hi:
        return hi, False
    return z, True


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

# ── THE APRON WITHIN-SHAPE POPULATION (owner ruling RULINGS 2026-08-21b) ─────
# "An apron's cap is owed on its MOVEMENT SURFACES — corridor profiles,
# frontage chords (building→spine) and stand entries — NEVER on a generic
# ring-vertex pair" (owner 2026-08-21, answer "ii"; spec
# ``docs/specs/apron-within-shape-population-spec.md``).
#
# Measured basis: 1,055 of HECA's 1,089 ``within_shape apron|apron`` airside
# rows on the 2026-08-21 battery patch are generic vertex-pair chords (p90
# 412-449 m, max 680 m) that merely CROSS a spine corridor cover; the ruled
# population — frontage chords — is 441.  SPJC 34 → 0; CYXY had none.
#
# STAND ENTRIES fold into frontage: a stand's lead-in IS its frontage chord
# (``apron_terrace.corridor_cover``'s own construction, and
# "reach follows centerlines", RULINGS 2026-07-30), and the engine carries no
# separate stand-entry object.
#
# ── AMENDED BY RULINGS 2026-08-21c / spec AMENDMENT A1: INTERIOR IS LAW ──
# The owner REVERSED the removal half of 2026-08-21b.  An interior apron pair
# is NOT dropped from the law — it is law at the FAN-RAMP CAP
# (``config.FAN_RAMP_CAP``, 5 %, the 2026-08-05 constant
# ``fan_ramp_law_cap`` resolves); only the MOVEMENT SURFACES (frontage
# chords, and the ring-adjacent branch R19-5 exists for) keep the STRICT
# apron cap.  Measured basis for the reversal, on this very lane
# (apronpop + transect, 2026-08-21): with the interior REMOVED the apron
# had no law at all, the transect rows moved the rings by metres and the
# frontage chords absorbed it — SPJC 189 → 551 airside, 201 of 233 new
# rows genuine frontage chords.  The 5 % interior law IS the interior's
# constraint (A1 §5a supersedes the "no replacement regulariser" clause).
#
# THE FLAG WAS RENAMED because "FRONTAGE_ONLY" now misdescribes it: nothing
# is dropped any more, only the interior CAP changes.  The old name
# ``O4_APRON_WITHIN_SHAPE_FRONTAGE_ONLY`` is NOT read — a stale arm using it
# would otherwise silently get the default, and an env flag that quietly
# means something new is exactly the silent-break class.
# ``O4_APRON_INTERIOR_RAMP_CAP=0`` restores THE PRE-RULING ALL-STRICT
# behaviour (every apron pair at the body cap), i.e. the 2026-08-21
# battery.  Since RULINGS 2026-08-24b it gates the WHOLE apron cap chain
# in ``classify_pair`` — back-edge, corridor and stand — because "all
# strict" is what the flag promises and half of it would be flag drift.
APRON_INTERIOR_RAMP_CAP = (
    os.environ.get("O4_APRON_INTERIOR_RAMP_CAP", "1") != "0")

#: The interior apron pair's cap (spec A1 §1a).  ONE constant, both readers
#: — the census reaches it through ``classify_pair`` like every other cap.
#:
#: RESCOPED, RULINGS 2026-08-24: the cap is unchanged (5 %, the fan-ramp
#: constant) but the CLASS that earns it shrank to the fan-ramp BACK-EDGE
#: ZONES plus the pairs the 60 m body gate has always held out of the
#: strict chain — see :func:`is_apron_interior`.
APRON_INTERIOR_CAP = FAN_RAMP_CAP

#: The soft-pavement roles whose ring vertices make a BUILDING ring edge a
#: FRONTAGE edge.  Production's own set, not a re-spelling: it is the
#: ``apron_keys`` of ``elevation_per_surface/route_profile/anchors.py``
#: ``build_building_seats`` (apron + junction — the corridor face a building
#: usually fronts onto is roled ``junction`` under the global slice, and
#: ``service_junction`` LEFT the set with the R7b sink ruling 2026-08-15,
#: "a road never welds to a building").
FRONTAGE_SOFT_ROLES = frozenset({APRON_ROLE, "junction"})


def frontage_vertex_keys(building_rings, soft_keys) -> set:
    """THE frontage-vertex set: every key of a BUILDING ring EDGE whose two
    endpoints are BOTH soft-pavement ring vertices.

    This is production's frontage predicate verbatim — ``anchors._frontage_box``
    ("both endpoints shared with an apron"), the same one
    ``tools/frontage_split.classify_buildings`` reads — expressed on KEYS so
    every reader can supply its own identity space (solver node indices,
    rounded layout coordinates, emitted node ids).  IDENTITY ONLY: never a
    proximity join (memory ``canonical-identity-join``).

    ``building_rings``  an iterable of OPEN key rings, one per building pad.
    ``soft_keys``       the keys of every ``FRONTAGE_SOFT_ROLES`` ring vertex.
    """
    out: set = set()
    for ring in building_rings:
        keys = [k for k in ring]
        n = len(keys)
        if n < 2:
            continue
        for i in range(n):
            a = keys[i]
            b = keys[(i + 1) % n]
            if a is None or b is None or a == b:
                continue
            if a in soft_keys and b in soft_keys:
                out.add(a)
                out.add(b)
    return out


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


# ── THE TRANSVERSE SPAN BUDGET — ONE FUNCTION, BOTH READERS ─────────────
# Owner ruling 2026-08-21 (RULINGS "RM's relocated airside debt is paid by
# the solver pricing transverse"), spec
# ``docs/specs/transverse-hyperplane-solve-spec.md`` step 1.
#
# A corridor CROSS-SECTION is priced over the span the transect actually
# crosses — ``cap_T x width`` — never over a route and never over a chord
# between ring vertices.  Both readers of that law used to spell the
# product themselves: ``check_grade._check_transverse_grade`` (the census)
# and ``lateral_spine_nodes.lateral_xsection_law_edges`` (the solve-side
# binding).  Two spellings of one product is the census-wrapper defect in
# miniature, and this family is precisely the one the owner just moved
# into the solve, so it gets stated once, here, beside the other
# within-shape budget functions.
#
# NO QUANTIZATION, deliberately, exactly as ``pair_grade_budget_m``:
# each reader adds its OWN encoding envelope (the census adds
# ``_pair_quant_noise_m`` on the crossed way and the declared terrace
# step; the solve adds nothing, because an emitted-reading forgiveness
# does not fund a solve target).
def transverse_span_budget_m(cap_l: float, width_m: float) -> float:
    """THE cross-section budget: ``transverse_cap_for_longitudinal_cap(cap_l)
    x width_m``.

    ``cap_l`` is the LONGITUDINAL cap of the axis segment the station sits
    on (the per-letter taxi cap, the apron cap, the service-road rate);
    the transverse cap is a pure function of it — the same one law source
    (``config.transverse_cap_for_longitudinal_cap``) the pair law's ``cT``
    resolves through.  ``width_m`` is the priced span's own width."""
    return transverse_cap_for_longitudinal_cap(cap_l) * float(width_m)


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
    # ── THE APRON MOVEMENT-SURFACE INPUTS (RULINGS 2026-08-21b) ──────────
    # ``a_frontage`` / ``b_frontage``: the endpoint is a FRONTAGE VERTEX — a
    # node this shape's ring shares with a building ring that participates in
    # a frontage EDGE (``frontage_vertex_keys``, production's own predicate).
    # ``a_corridor`` / ``b_corridor``: the endpoint lies inside the SPINE
    # CORRIDOR COVER (``apron_terrace.spine_corridor_cover``, its own radius).
    # Both are computed ONCE PER SHAPE by the reader — the law only DECIDES
    # with them, exactly like ``a_building`` / ``both_road``.  Defaults are
    # False, so a reader that does not supply them (plane shapes, a legacy
    # caller) sees the frontage-only rule refuse every apron pair; the rule
    # is scoped to ``role == APRON_ROLE``, which no plane shape carries.
    a_frontage: bool = False
    b_frontage: bool = False
    a_corridor: bool = False
    b_corridor: bool = False
    # ── AMENDMENT A4 INPUTS ─────────────────────────────────────────────
    # ``nearest_spine``: THIS pair is an endpoint's chord to its NEAREST
    # SPINE NODE (A4.1(i), one per ring vertex).  The reader computes the
    # nearest-spine assignment once per shape, over the spine nodes of
    # ``centerline_specs`` — the ONE enumeration that also produces the
    # sidecar's ``axes_exact`` — so bake and census select the same set.
    # ``a_in_strip`` / ``b_in_strip``: the endpoint lies inside the RUNWAY
    # STRIP footprint (``runway_strip_wall_keepout_rings``, A4.2).  Membership
    # is the reader's, the verdict is the law's, exactly like the fields above.
    nearest_spine: bool = False
    a_in_strip: bool = False
    b_in_strip: bool = False
    # ── THE BACK-EDGE RESCOPE (owner ruling RULINGS 2026-08-24) ─────────
    # ``in_interior_zone``: this pair lies WHOLLY inside ONE fan-ramp
    # back-edge zone — the ground between two adjacent building pads, cut
    # clear of every movement surface (``apron_terrace.plan_fan_ramp_zones``
    # and its ``FanRampPlan.pair_cap`` predicate: both ends in the SAME
    # zone AND the chord covered by it).  It is the ONLY class that still
    # earns the 5 % interior cap.  Membership is the reader's, the verdict
    # is the law's — exactly like ``a_in_strip`` above.
    #
    # DEFAULT FALSE IS THE STRICT DIRECTION: a reader that supplies no
    # zones prices every non-strict apron pair inside the 60 m body gate
    # at the shape's own cap, never looser than the law.
    in_interior_zone: bool = False
    # ── NO PLATEAUS (owner ruling RULINGS 2026-08-24b) ──────────────────
    # ``corridor_connected``: the pair's APRON SHAPE is joined to the taxi
    # CORRIDOR NETWORK — it carries spine membership, or some ring vertex
    # of it lies inside the spine corridor cover.  A SHAPE-level fact, not
    # a pair-level one, because the ruling's reason is about the shape:
    # "an apron spanning between two lawful 1.5 % taxiways lawfully runs
    # ~1.5 % itself".  Both notions are the reader's existing ones (the
    # ``_spine_membership`` map and ``corridor_cover_prepared``, already
    # computed per shape for ``a_corridor``/``b_corridor``) — no new
    # geometry and no new radius.
    #
    # DEFAULT FALSE IS THE STRICT DIRECTION: an apron the reader cannot
    # show is joined to a corridor has no corridor cap to inherit and
    # keeps its own body cap.
    corridor_connected: bool = False


SKIP: Optional[Allowance] = None


def is_frontage_chord(p: "PairContext") -> bool:
    """THE frontage-chord predicate (RULINGS 2026-08-21b, spec §1): the pair
    runs from a building seat contact to the spine it grades to.

    EXACTLY ONE endpoint is a frontage vertex, the OTHER lies inside the spine
    corridor cover, and the chord is within the frontage band's own reach
    (``BUILDING_REACH_CORRIDOR_M``, the ONE building↔spine reach value).

    P1 — both endpoints frontage vertices of one pad — is NOT this predicate's
    business: it is the inter-pad frontage step, and ``classify_pair``'s
    ``a_building and b_building`` skip (which sits BEFORE the apron rule)
    already rules it, so P1 keeps exactly the behaviour it has today.  A
    frontage vertex is by construction a building ring vertex, so a pair
    reaching the apron rule has at most one of them."""
    if p.dist > BUILDING_REACH_CORRIDOR_M:
        return False
    if p.a_frontage and not p.b_frontage:
        return bool(p.b_corridor)
    if p.b_frontage and not p.a_frontage:
        return bool(p.a_corridor)
    return False


def _within_body_chord_gate(p: "PairContext") -> bool:
    """THE BODY-CHORD LENGTH CONDITION (spec AMENDMENT A3): a ring edge or a
    corridor-crossing pair is a MOVEMENT SURFACE only within
    ``APRON_BODY_CHORD_MAX_M``.  Beyond it the pair is interior, because a
    650-857 m "edge" is not a surface an aircraft rolls along at 1 % — it is
    the apron body, and the 60 m gate has excluded that class since long
    before this ruling.  ``0`` / unset disables the gate, matching the way
    ``classify_pair``'s own body-chord skip reads the constant."""
    return not APRON_BODY_CHORD_MAX_M or p.dist <= APRON_BODY_CHORD_MAX_M


def is_apron_corridor_crossing(p: "PairContext") -> bool:
    """A pair lying on the taxi CORRIDOR (spec AMENDMENT A2): inside the spine
    corridor cover at BOTH ends, or sharing a spine centerline outright.  It
    is pavement an aircraft actually taxis over, so it keeps the STRICT cap
    even though neither endpoint fronts a building.

    ``spine_caps`` is the same class stated directly — and it is the reason
    this predicate is NOT gated on ring adjacency: a spine pair's cap is its
    ROUTE's per-letter taxi cap, and raising it to the 5 % interior cap would
    legalise a 5 % grade along a running taxiway.  A synthetic fixture with no
    ``apron_terrace`` cover (``test_grade_graph``'s spine twin) has exactly
    that shape and is what caught it.

    AMENDMENT A3 — THE COVER TEST IS GATED BY THE BODY-CHORD LENGTH.  A
    corridor crossing a LONG edge makes the CROSSING a movement surface,
    priced by the corridor's own longitudinal and transverse laws; it does
    not make the whole 850 m edge one.  A2's ungated clause bypassed
    ``APRON_BODY_CHORD_MAX_M``, the gate that exists to exclude exactly this
    class, and that is measured as HECA's infeasibility: 956 of 2,275
    within-shape apron rows sat on chords > 60 m, the worst being -10612 ring
    edges of 650-857 m at 1.36-1.64 % where the terrain falls 11.7 m and 1 %
    permits 8.4 m.

    THE ``spine_caps`` HALF KEEPS NO LENGTH GATE, deliberately: that pair IS
    the route, its cap is the route's own, and the length gate would raise a
    long taxiway pair from its taxi cap to 5 %.  A3 names the COVER clause as
    the one that bypassed the gate, and that is the one gated here."""
    if p.spine_caps:
        return True
    if not (p.a_corridor and p.b_corridor):
        return False
    return _within_body_chord_gate(p)


def is_apron_frontage_edge(p: "PairContext") -> bool:
    """P1 as it reaches the APRON shape: a ring edge whose BOTH endpoints are
    frontage vertices (spec AMENDMENT A2) — the pavement directly under a
    building face.  STRICT.

    (The inter-pad P1 that both endpoints are BUILDING ring vertices is a
    different pair and is skipped earlier by ``a_building and b_building``.)

    AMENDMENT A3: a RING EDGE is strict only inside the body-chord gate, this
    one included — "a ring edge (or corridor-crossing pair) is STRICT only if
    its chord <= APRON_BODY_CHORD_MAX_M".  A frontage CHORD
    (``is_frontage_chord``) is unchanged and keeps no such gate: it is <=
    ``BUILDING_REACH_CORRIDOR_M`` by construction."""
    return bool(p.a_frontage and p.b_frontage) and _within_body_chord_gate(p)


#: Node seniority literals (apron staged solve, spec
#: ``docs/specs/apron-staged-solve-spec.md`` §3).  ONE spelling, shared by
#: the solve partition, the sidecar export and the census.
APRON_SENIOR = "senior"
APRON_INTERIOR = "interior"
#: A node inside the RUNWAY STRIP footprint (spec AMENDMENT A4.2): it is not
#: apron law at all, so it is neither senior nor interior.  Exported as a
#: third value so the census and the trouble map can show what left.
APRON_EXCLUDED = "excluded"

# Kill switch: ``O4_APRON_STAGED_SOLVE=0`` runs the single-pass apron of
# compose-v3 (byte-for-byte).
APRON_STAGED_SOLVE = (
    os.environ.get("O4_APRON_STAGED_SOLVE", "1") != "0")


def apron_node_seniority(apron_nodes, strict_pairs, transect_nodes=(),
                         excluded_nodes=()) -> dict:
    """THE APRON NODE PARTITION (spec ``apron-staged-solve-spec.md`` §§1, 3):
    ``{node: APRON_SENIOR | APRON_INTERIOR}`` over the apron ring nodes.

    A node is SENIOR when it is an endpoint of a STRICT pair — a frontage
    chord, a ring frontage edge, a corridor-crossing edge or a spine pair,
    i.e. exactly the pairs ``is_apron_interior`` returns False for — or an
    endpoint of a BOUND TRANSECT row.  Everything else on an apron ring is
    INTERIOR.  The movement surfaces are therefore the senior set by
    construction, and the caller never re-spells the predicate: it hands in
    the pairs the law already classified.

    ONE function, both readers (§3): the solve partitions its two sub-stages
    with it and the sidecar exports its result as ``apron_seniority``, so the
    census can assert that no senior node moved in the interior pass.

    ``apron_nodes``     every node on an apron ring (the partition's domain).
    ``strict_pairs``    ``(a, b)`` pairs of apron law edges that are NOT
                        interior.
    ``transect_nodes``  node ids carried by bound transect rows.
    ``excluded_nodes``  nodes inside the runway strip footprint (A4.2); they
                        take ``APRON_EXCLUDED``, which overrides both other
                        values because a strip node carries no apron law.
    """
    out = {int(n): APRON_INTERIOR for n in apron_nodes}
    # EXCLUDED WINS OVER EVERYTHING (A4.2): a strip node carries no apron law,
    # so no pair can make it senior.  Applied last, below.
    excluded = {int(n) for n in excluded_nodes}
    for a, b in strict_pairs:
        for k in (int(a), int(b)):
            if k in out:
                out[k] = APRON_SENIOR
    for n in transect_nodes:
        k = int(n)
        if k in out:
            out[k] = APRON_SENIOR
    for k in excluded:
        if k in out:
            out[k] = APRON_EXCLUDED
    return out


# Kill switch for the conforming mint (spec
# ``docs/specs/creation-order-seniority-spec.md``, owner ruling RULINGS
# 2026-08-21e).  ``O4_CONFORMING_MINT=0`` restores the pre-ruling behaviour.
# PARKED 2026-08-23: the "22 emit-minted" class that motivated this was a
# JOIN ARTIFACT — pair_caps exported lat/lon at 7 dp (half-ulp 0.0056 m) and
# the 26/22 split came from a ~5 mm proximity join against that quantum; at
# 10 mm all 48 SPJC rows join to baked pairs.  The canonical-identity-join
# law fired on our own instrument.  The RULING STANDS and the mechanism is
# kept intact, but it waits for a real measured instance, so the gate is
# DEFAULT OFF: O4_CONFORMING_MINT=1 arms it.
CONFORMING_MINT = (
    os.environ.get("O4_CONFORMING_MINT", "0") == "1")


def conforming_mint(senior_value, junior_values, junior_dists, cap):
    """CREATION-ORDER SENIORITY (owner ruling RULINGS 2026-08-21e, spec
    ``creation-order-seniority-spec.md`` §1): later-minted geometry DEFERS
    to the surface that is already there.

    A pass that mints a vertex against a settled surface gives it the SENIOR
    surface's value at that position; the JUNIOR ring then conforms its own
    neighbourhood by a BOUNDED MONOTONE WALK under its own cap, outward from
    the weld, until it meets the values it already had.  The F3c walk shape.

    Returns the walked junior values as ``[(index, new_value), ...]`` for the
    prefix the walk actually reaches — everything beyond it is already
    reachable at ``cap`` and is left untouched, which is what bounds the
    reach by DEMAND rather than by a constant.

    ``senior_value``  the senior surface's value at the mint position.
    ``junior_values`` the junior ring's existing values, ordered OUTWARD
                      from the mint (the mint's own vertex excluded).
    ``junior_dists``  the segment length to each of those, same order.
    ``cap``           the junior ring's own cap (a grade, e.g. 0.01).

    BY CONSTRUCTION the minted adjacency and every walked sub-edge are
    within ``cap``: each step is clamped to ``cap x segment length`` from the
    previous walked value, and the walk stops at the first vertex already
    inside that envelope.  Nothing senior is ever returned, so no caller can
    move a senior vertex through this function.

    Measured basis (SPJC, the 22-row emit-minted class): every one of those
    rows has an endpoint whose value differs from its OWN ring's linear
    interpolation by 0.21-0.23 m — the donor vertex keeping its value while
    the receiving edge was split at the interpolation, so the consensus pass
    unified them at a step neither ring had priced.
    """
    out = []
    prev = float(senior_value)
    for i, (v, d) in enumerate(zip(junior_values, junior_dists)):
        if v is None or d is None:
            break
        reach = abs(float(cap)) * float(d)
        lo, hi = prev - reach, prev + reach
        v = float(v)
        if lo - 1e-12 <= v <= hi + 1e-12:
            # THE WALK TERMINATES HERE: the ring already reaches this value
            # lawfully from the walked one, so nothing beyond needs moving.
            break
        new = lo if v < lo else hi
        out.append((i, new))
        prev = new
    return out


def is_apron_strict_chord(p: "PairContext") -> bool:
    """THE STRICT APRON POPULATION (spec AMENDMENT A4.1).  An apron pair takes
    the strict cap when it is one of exactly three things:

      (i)   the chord from a ring vertex to its NEAREST SPINE NODE — one per
            vertex, the reach an aircraft actually rolls to the corridor on
            (``nearest_spine``, assigned by the reader);
      (ii)  a FRONTAGE CHORD (section 1, unchanged);
      (iii) a RING EDGE within ``APRON_BODY_CHORD_MAX_M`` (A2 as corrected by
            A3), which includes the ring frontage edge and the
            corridor-crossing edge.

    Everything else on an apron is INTERIOR at ``APRON_INTERIOR_CAP``.

    Measured basis for (i): the A3 arm priced a FAN of 53 chords from one
    -10612 pad vertex, 118-847 m, every one at 1 % — the owner's reading is
    that the only chord owed from that vertex is the ~118 m one to its
    nearest centerline node.  A spine pair (``spine_caps``) is the corridor
    itself and keeps its route cap; it is strict by that route's own law, not
    by this predicate."""
    if p.nearest_spine:
        return True
    if is_frontage_chord(p):
        return True
    # (iii) is worded "ring edges <= APRON_BODY_CHORD_MAX_M PER A2/A3", so it
    # carries A2/A3's own clauses rather than promoting every short ring edge:
    # a ring FRONTAGE edge or a CORRIDOR-CROSSING edge, inside the gate.  A
    # plain ring edge between two non-frontage, non-corridor vertices stays
    # INTERIOR, which is what A3 ruled and what keeps R19-5's catch alive at
    # 5 % (the edge never leaves the domain; only its cap changes).
    if p.ring_adjacent and _within_body_chord_gate(p) and (
            is_apron_frontage_edge(p) or (p.a_corridor and p.b_corridor)):
        return True
    return bool(p.spine_caps)


#: THE APRON PAIR CLASSES (owner ruling RULINGS 2026-08-24b).  The owner's
#: acceptance test is stated as an EXHAUSTIVE taxonomy — "any apron row is
#: either a stand chord over 1 %, a corridor-region chord over 1.5 %, a
#: back-edge chord over 5 %, or solver sag to fix — there is no lawful
#: fourth class" — so the classes are spelled ONCE here and every reader
#: (the cap chain, the seniority partition, the census's own cap column)
#: reaches them through :func:`apron_pair_class`.
APRON_CLASS_SPINE = "spine"          # the corridor itself: its route's cap
APRON_CLASS_STAND = "stand"          # pad ↔ centerline: the strict 1 %
APRON_CLASS_CORRIDOR = "corridor"    # corridor-connected body: 1.5 %
APRON_CLASS_BACK_EDGE = "back_edge"  # the fan-ramp wedges: 5 %
APRON_CLASS_BODY = "body"            # no corridor to inherit from: body cap


def apron_pair_class(p: "PairContext") -> str:
    """THE apron pair's class (owner ruling RULINGS 2026-08-24b).

    ONE predicate, consumed by ``classify_pair`` (which turns it into a
    cap), by ``is_apron_interior`` (which turns it into the staged solve's
    partition) and by every report — so a census column and a baked cap
    cannot describe different populations.

    Precedence, and the reason for each step:

      1. SPINE.  The pair IS the corridor, so it keeps its route's own
         per-letter cap.  First, because raising a running taxiway to any
         apron cap would legalise a grade along the route itself — the
         catch ``is_apron_corridor_crossing`` was written for.
      2. STAND.  The PAD↔centerline chord: a building FRONTAGE chord, or
         the VISIBLE nearest-spine chord (A4.1(i), one per vertex) OF A
         PAD-ANCHORED VERTEX.  "The 1 % stand chords are the PAD-ANCHORED
         vertex→centerline chords; non-pad vertices take the corridor cap"
         (RULINGS 2026-08-24c).  This is the only class that keeps 1 %, and
         it keeps it at any length, which is A4.1 and 2026-08-21d agreeing
         (21d refuted the blanket PAD CLAMP on arbitrary long pairs, never
         the one nearest-spine chord a pad vertex is owed).  A NON-pad
         vertex's nearest-spine chord falls to CORRIDOR.
      3. BACK_EDGE.  Wholly inside one fan-ramp back-edge zone
         (2026-08-24), or beyond ``APRON_BODY_CHORD_MAX_M`` — the latter
         being the A3 / 21d classes the 60 m body gate has always held out
         of the strict chain (HECA -10612's 650-857 m "edges" over an
         11.7 m fall; the 118-847 m fan from one pad vertex).  Below the
         movement surfaces in precedence because a zone is cut CLEAR of
         them by construction.
      4. CORRIDOR.  Everything else on an apron JOINED to the corridor
         network.  This is the ruling's substance: "unless there is a
         pavement gap there are NO cliffs in aprons… an apron spanning
         between two lawful 1.5 % taxiways lawfully runs ~1.5 % itself".
      5. BODY.  An apron the reader cannot show is corridor-connected has
         no corridor cap to inherit and keeps its own body cap.  The
         strict fallback, and what a legacy caller supplying no
         membership sees.
    """
    if p.spine_caps:
        return APRON_CLASS_SPINE
    if is_frontage_chord(p):
        return APRON_CLASS_STAND
    if p.nearest_spine:
        # ── STAND SCOPE IS PAD-ANCHORED (owner ruling RULINGS 2026-08-24c,
        # confirming the proposal this lane measured) ────────────────────
        # A4.1(i) assigns a nearest-spine chord to EVERY apron ring vertex,
        # pad or not.  The owner's 1 % is the PAD↔CENTERLINE (stand) chord:
        # "non-pad vertices take the corridor cap".  So the A4.1(i)
        # population SPLITS here — the chord is still one per vertex and
        # still has no length gate (that is A4.1 and 2026-08-21d agreeing);
        # only its CAP depends on whether the vertex it starts from is a
        # pad vertex.
        #
        # PAD-ANCHORED reuses the FRONTAGE-VERTEX predicate
        # (``frontage_vertex_keys``, production's own ``anchors._frontage_
        # box``) — the same set that already decides ``a_frontage`` — plus
        # a raw building-ring endpoint.  No new notion of "on a pad".
        #
        # MEASURED BASIS (this lane, v2, HECA): the stand class carried
        # 1,751 of 1,752 apron airside rows and ~40 % of them started from
        # a vertex that fronts no building at all.
        if (p.a_frontage or p.b_frontage
                or p.a_building or p.b_building):
            return APRON_CLASS_STAND
        # A non-pad vertex's chord to its centerline IS corridor travel,
        # so it takes the corridor cap directly — it reaches a spine by
        # construction, which is what corridor-connectedness means.
        return APRON_CLASS_CORRIDOR
    if not _within_body_chord_gate(p) or p.in_interior_zone:
        return APRON_CLASS_BACK_EDGE
    if p.corridor_connected:
        return APRON_CLASS_CORRIDOR
    return APRON_CLASS_BODY


def is_apron_in_strip(p: "PairContext") -> bool:
    """The pair has an endpoint inside the RUNWAY STRIP footprint (A4.2).

    Measured basis: synthetic apron sliver -12251 at HECA — 6,782 m2, 666 m
    long, effective width 10 m, THIRTEEN nodes welded straight into runway
    05C/23C's ring, with no OSM source within 200 m — entered the apron law
    population because nothing in ``classify_pair`` consulted the strip
    keep-out that ``adjacent_ground`` and ``groundside`` already read."""
    return bool(p.a_in_strip or p.b_in_strip)


def is_apron_interior(p: "PairContext") -> bool:
    """THE 5 %-CLASS predicate — the pairs priced at ``APRON_INTERIOR_CAP``.

    Its consumers are the cap chain in :func:`classify_pair` and the apron
    STAGED SOLVE's partition (``grade_graph`` records it index-parallel to
    the edges; the staged pass withholds exactly these from its senior
    sub-stage).  Both reach it through the ONE classifier,
    :func:`apron_pair_class`, so the partition and the cap cannot drift.

    ── THE HISTORY THIS PREDICATE HAS TRACKED ──────────────────────────
    RULINGS 2026-08-21c / spec A1 §1a made it "an apron pair that is not a
    MOVEMENT SURFACE", priced at the fan-ramp cap; A2/A3 corrected which
    pairs those were (a ring edge between two non-frontage vertices IS a
    generic pair, and R19-5's catch survives at 5 % — a 148 % ring edge
    still mints its row); A4.1 restated the strict set as its three names.

    RULINGS 2026-08-24 RESCOPED the 5 % class to the fan-ramp BACK-EDGE
    ZONES.  Measured basis (the owner's HECA in-sim review): the broad
    5 % interior let whole rings DRAPE onto the DEM — apron median
    height-above-DEM 2.92 -> 1.99 m, ring relief +19 %, site -10682 down
    7.3 m.  The plateau had no authority.

    RULINGS 2026-08-24b (NO PLATEAUS) then removed the plateau framing
    altogether and with it the last ambiguity here.  With the
    corridor-connected apron body priced at the LOCAL CORRIDOR CAP rather
    than at the shape's body cap, "interior" stops meaning "not a movement
    surface" and starts meaning exactly what every consumer uses it for:
    the 5 % class.  That is ``apron_pair_class == APRON_CLASS_BACK_EDGE``
    — the back-edge zones, plus the pairs beyond
    ``APRON_BODY_CHORD_MAX_M`` that the 60 m body gate has always held out
    of the strict chain (A3's -10612 ring "edges" of 650-857 m over an
    11.7 m fall; 21d's 118-847 m fan from one pad vertex).  Both of those
    are REFUTED classes and neither is re-opened by any of the above.

    Scoped to ``APRON_ROLE``: runway / taxiway / junction within-shape laws
    are UNCHANGED (ruling 2026-08-21b clause 4, unamended).
    """
    if not (APRON_INTERIOR_RAMP_CAP and p.role == APRON_ROLE):
        return False
    return apron_pair_class(p) == APRON_CLASS_BACK_EDGE


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
    # — AN APRON PAIR INSIDE THE RUNWAY STRIP IS NOT APRON LAW (spec
    #   AMENDMENT A4.2; owner ruling RULINGS 2026-08-21d).  The strip has its
    #   own runway-edge terrain law (2026-08-01, "runway surroundings must
    #   grade away smoothly") and its footprint is already a law function —
    #   ``runway_strip_wall_keepout_rings``, which ``adjacent_ground`` and
    #   ``groundside`` read.  Nothing in this path consulted it, so a
    #   synthetic apron sliver welded onto a runway shoulder (HECA -12251)
    #   was graded as apron body.  ONE geometry, no new constant; membership
    #   is the reader's, the verdict is here.
    if p.role == APRON_ROLE and is_apron_in_strip(p):
        return SKIP
    # — AN APRON'S CAP IS OWED ON ITS MOVEMENT SURFACES, NEVER ON A GENERIC
    #   RING-VERTEX PAIR (owner ruling RULINGS 2026-08-21b, answer "ii";
    #   spec ``docs/specs/apron-within-shape-population-spec.md`` §1).  The
    #   corridor surface is priced by its OWN longitudinal and transverse
    #   laws; what an APRON within-shape pair regulates is the FRONTAGE
    #   CHORD — building seat → the spine it grades to.  Every other apron
    #   pair is not law: 1,055 of HECA's 1,089 such rows were generic
    #   vertex-pair chords up to 680 m that merely CROSSED a spine corridor
    #   cover, and the smoothing they were credited with is the warm-start
    #   carrier's, not this law's (RULINGS 2026-08-15, band carrier).
    #   Sits directly after the inter-pad skip so P1 (both endpoints
    #   frontage vertices) keeps that branch's existing behaviour, and
    #   before every EXPENSIVE predicate so a dropped chord never pays for
    #   the polygon-containment or spine-crossing test.
    #   Runway / taxiway / JUNCTION within-shape laws are UNCHANGED (ruling
    #   clause 4) — the rule is scoped to ``APRON_ROLE`` alone.
    #
    #   *** AMENDED, RULINGS 2026-08-21c / spec A1 §1a: THE SKIP IS GONE. ***
    #   The interior pair is LAW at ``APRON_INTERIOR_CAP`` (5 %), applied at
    #   cap-selection time below; the frontage chord keeps the strict cap and
    #   the ring-adjacent branch keeps its own.  Nothing is removed from the
    #   domain here any more, so every EXISTING skip rule below (sub-noise
    #   separation, junction mesh, visibility, spine-crossing and the 60 m
    #   ``APRON_BODY_CHORD_MAX_M`` body gate) still runs on the interior class
    #   exactly as it did before 2026-08-21b — they predate this ruling and are
    #   orthogonal to it.
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
            and not p.nearest_spine
            and not p.a_building and not p.b_building
            and p.dist > APRON_BODY_CHORD_MAX_M):
        return SKIP

    # ── THE INTERIOR BRANCH IS FINAL (spec AMENDMENT A4.1) ────────────
    # An apron pair that is not one of the three strict classes prices at
    # ``APRON_INTERIOR_CAP`` and RETURNS HERE.  It does not fall through to
    # the cap chain, so no post-clamp can re-tighten it — which is the whole
    # correction A4 makes.  MEASURED: under A3 the building clamp below ran
    # as a BLANKET rule and pulled 5,050 long HECA apron pairs back to 1 %
    # after the interior raise had released them (every long pair touching a
    # pad, including the 118-847 m fan from one -10612 vertex).  "Buildings
    # are the heaviest constraint" (user 2026-07-02) is a statement about the
    # chords a building is GRADED TO — the strict classes — not about every
    # chord that happens to touch a pad.
    #
    # RESCOPED, RULINGS 2026-08-24: the branch fires only for a
    # BACK-EDGE-ZONE pair, or for one beyond the 60 m body gate (the A3 /
    # 21d refuted classes).
    #
    # ── NO PLATEAUS (owner ruling RULINGS 2026-08-24b) ─────────────────
    # THE WHOLE APRON CAP CHAIN IS THE CLASSIFIER'S ANSWER.  Owner,
    # verbatim: "unless there is a pavement gap there are NO cliffs in
    # aprons.  The centerline network traverses the terrain within its own
    # caps (1.5 % taxiway); aprons connect to taxiways and conform
    # continuously."  So an interior chord on a CORRIDOR-CONNECTED apron
    # inherits the LOCAL CORRIDOR CAP — an apron spanning between two
    # lawful 1.5 % taxiways lawfully runs ~1.5 % itself — and the strict
    # 1 % belongs to the STAND chords (pad ↔ centerline) alone.
    #
    # MEASURED BASIS FOR THE AMENDMENT (this lane, v1, HECA): pricing the
    # whole non-back-edge interior at the 1 % body cap put HECA at 2,138
    # airside against a 1,487 bar, and it did NOT lift the surface — the
    # apron came up 0.43 m while ring relief and 50 m amplitude both got
    # WORSE.  1,941 apron rows all carried cap 1.00 % and not one carried
    # 5 %.  A cap the surface cannot meet is not authority, it is sag.
    #
    # NO NEW NUMBER: ``TAXI_MAX_GRADE`` is the corridor's own cap, the same
    # constant the apron↔taxi blend credit already hands a ring edge that
    # nears a taxiway, and the same one ``ROLE_GRADE_LIMITS`` gives the
    # junction network.
    # ONE KILL SWITCH, ONE MEANING.  ``O4_APRON_INTERIOR_RAMP_CAP=0``
    # restores the pre-2026-08-21c ALL-STRICT reading (the 2026-08-21
    # battery), so it gates the WHOLE apron chain — back-edge, corridor
    # and stand alike — and every apron pair falls through to the plain
    # spine / blend / body chain below.  Gating only the 5 % branch would
    # leave the flag half-honouring its own documented promise, which is
    # the silent-flag-drift class the rename note above exists for.
    _apron_class = (apron_pair_class(p)
                    if (APRON_INTERIOR_RAMP_CAP and p.role == APRON_ROLE)
                    else None)
    if _apron_class == APRON_CLASS_BACK_EDGE:
        return Allowance.flat(APRON_INTERIOR_CAP)
    if _apron_class == APRON_CLASS_CORRIDOR:
        # The corridor-connected body.  Returned HERE, like the back-edge
        # branch and for the same reason (A4's correction): falling through
        # would let the blanket pad clamp below pull it back to 1 %, which
        # is exactly the "every chord that happens to touch a pad" rule
        # 2026-08-21d refuted.
        return Allowance.flat(TAXI_MAX_GRADE)
    if _apron_class == APRON_CLASS_STAND:
        # "The 1 % strict cap belongs to the pad↔centerline (stand)
        # chords."  Stated as the cap rather than left to the chain below,
        # so a stand chord inside a service-road carve or under a blend
        # cannot be relaxed off it — buildings remain the heaviest
        # constraint (user 2026-07-02) and this is the class that sentence
        # was always about.
        return Allowance.flat(BUILDING_FRONTAGE_MAX_GRADE)

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


# ── THE PAD LAW (docs/specs/per-cluster-object-seating-spec.md §5.1) ──
# Owner ruling R2, verbatim: "we have to be sure we don't create building
# pads that are then giant cliffs in relation to the graded pavement.  They
# want to generally be as close as feasible to DEM, then some adjustment to
# terrain is acceptable, but particularly for buildings adjacent to airside
# pavement they must not deform the graded pavement."
#
# ONE SOURCE, TWO READERS (R5, the one-solve doctrine): every scalar below
# is imported by BOTH the emitter (``object_pads.emit_object_pads``) and the
# validator (``verification.check_object_pads``).  Neither re-derives a
# number; a lockstep failure is therefore impossible by construction, not
# by discipline.  Pure functions — no geometry, no DEM object, no config
# read except the two named caps passed in by the caller.

def object_pad_relief_m(target_elevation_m: float,
                        ground_elevation_m: float) -> float:
    """The pad's SIGNED relief against THE GROUND IT ADJOINS:
    ``target − ground``.

    ``ground_elevation_m`` is the pad's OWN in-run ground authority — the
    patch's own evaluated surface where the patch authors it, ambient DEM
    only where it does not — the value the emission path computed under
    this pad's parts and carried on the request
    (``object_frame.pad_requests_from_frame``).  It is NEVER raw DEM under
    a graded surface: deviation from DEM is not an error and not reported
    (owner 2026-08-14), and a raw-DEM reference here refused pads for
    standing on our own solved apron (RULINGS, Fable 2026-08-14).

    Positive = the pad FILLS (terrain raised to meet a building seated
    above the ground); negative = the pad CUTS a bench (spec §5.1 clause 1:
    "Pads may RAISE or LOWER terrain ... direction default-symmetric")."""
    return float(target_elevation_m) - float(ground_elevation_m)


def object_pad_admissible(target_elevation_m: float,
                          ground_elevation_m: float,
                          max_relief_m: float) -> bool:
    """Spec §5.1 clause 1, as re-framed 2026-08-14: a pad is admissible
    only while it stands within ``DSF_OBJECT_PAD_MAX_RELIEF_M`` of the
    ground it ADJOINS (see :func:`object_pad_relief_m` for what that
    ground is; the cap VALUE is unchanged).

    "As close as feasible to the ground, then some adjustment to terrain
    is acceptable."  A pad needing more relief than the cap is REFUSED —
    the requesting cluster keeps its residual and the refusal is a finding
    (§5.5) — never emitted at a truncated height, which would promise a
    seat the terrain does not deliver."""
    return abs(object_pad_relief_m(target_elevation_m,
                                   ground_elevation_m)) <= float(max_relief_m)


def object_pad_pull_toward_pavement(target_elevation_m: float,
                                    pavement_elevation_m: float,
                                    run_m: float,
                                    max_grade: float) -> float:
    """Spec §5.1 clause 3 — PAVEMENT WINS OVER THE BUILDING BASE TOO.

    Between a welded pavement edge (whose solved value the pad ADOPTS,
    ruling R4) and the pad's interior target, the surface must transition
    at a lawful grade over the available run.  Where the run is too short
    for the full step, the TARGET is pulled toward the pavement value
    rather than emitting a cliff at the apron; the shortfall re-appears as
    a residual finding.

    ``run_m`` is the planar distance from the welded pavement contact to
    the pad's interior (target) region; ``max_grade`` is the caller's
    groundside cap (``config.GROUNDSIDE_MAX_GRADE`` — the named constant,
    so there is no second copy of the rate).  A non-positive run pins the
    target to the pavement value exactly (zero available transition)."""
    import math as _math

    pavement = float(pavement_elevation_m)
    target = float(target_elevation_m)
    reach = max(0.0, float(run_m)) * float(max_grade)
    delta = target - pavement
    if abs(delta) <= reach:
        return target
    return pavement + _math.copysign(reach, delta)


def object_pad_pull_shortfall_m(target_elevation_m: float,
                                pulled_target_m: float) -> float:
    """The residual the pull-toward-pavement left unabsorbed (spec §5.1
    clause 3: "the shortfall re-appears as a residual finding rather than
    a cliff at the apron").  Zero when the run was long enough."""
    return abs(float(target_elevation_m) - float(pulled_target_m))


def object_pad_blend_width_m(pad_area_m2: float, pad_perimeter_m: float,
                             margin_m: float) -> float:
    """THE PER-REQUEST BLEND WIDTH (spec §5.1 clause 4: the blend crosses
    "a ``DSF_OBJECT_FOOT_PAD_MARGIN_M``-class margin, **per-request**").

    The nominal margin is what ``object_footprints.foot_pad_ring`` dilated
    the contact hull BY, so a pad whose hull is large keeps the full 2 m
    ring and eroding it back recovers the hull exactly.  But a request
    whose ground contact is a metre across is a ring that is ALL margin:
    eroding by the full 2 m leaves no interior at all, and a pad with no
    interior holds the building base nowhere.  (Measured on the OTHH
    corpus: the median cluster request's ring is 18 m² — a ~1 m hull
    dilated to a 12-gon — and full-margin erosion empties every one of
    them.)

    So the blend never claims more than HALF the pad's own inradius,
    estimated from the shape's area and perimeter (``2A/P`` is exact for a
    disc and close for the convex hulls this ring family produces).  A
    generous pad is unaffected — ``min`` returns the nominal margin — and a
    tight one keeps a real interior at the target with a real, if shorter,
    ramp to DEM.  Nothing here enlarges a pad: the width only ever
    SHRINKS inside the ring the request already recorded.

    Returns 0.0 for a degenerate shape (the caller refuses the pad)."""
    area = float(pad_area_m2)
    perimeter = float(pad_perimeter_m)
    if area <= 0.0 or perimeter <= 0.0:
        return 0.0
    inradius = 2.0 * area / perimeter
    return max(0.0, min(float(margin_m), 0.5 * inradius))


def object_pad_blend_elevation(target_elevation_m: float,
                               dem_elevation_m: float,
                               distance_from_core_m: float,
                               margin_m: float) -> float:
    """Spec §5.1 clause 4 — THE OPEN-SIDE BLEND.

    On sides not touching pavement the pad blends from its interior target
    ``b`` to raw DEM across the margin ring grown from the contact hull
    (``DSF_OBJECT_FOOT_PAD_MARGIN_M``).  The adjacent-ground convention is
    kept verbatim: the value is stated as a SIGNED OFFSET from the pad's
    edge anchor (here the target under the contact hull) that decays with
    distance out from that anchor, so at ``d = 0`` the surface holds the
    target and at ``d ≥ margin`` it IS raw DEM — the pad meets untouched
    ground exactly, with no standoff groove and no unbounded tail.

    Deliberately NOT grade-capped, and this is the one place the pad law
    departs from the band law's shape: with a 3 m relief cap over a 2 m
    margin a pad's outer face is a BENCH (up to 150 %), which is what a
    building dug into or standing proud of a slope must look like (spec
    §8 Q3 states the trade in those terms).  Grade-capping here would
    either strand the pad above the DEM at its own outer edge — a cliff
    with no vertex on it, the exact defect ruling R2 forbids — or shrink
    the pad's reach without owner authority.  The bench's height is
    bounded by ``object_pad_admissible`` instead, which is where the owner
    put the cap."""
    margin = float(margin_m)
    dem = float(dem_elevation_m)
    target = float(target_elevation_m)
    if margin <= 0.0:
        return dem
    t = float(distance_from_core_m) / margin
    if t <= 0.0:
        return target
    if t >= 1.0:
        return dem
    return target + t * (dem - target)

def basin_trench_floor_elevation_m(
        rim_estimate_elevation_m: float,
        solid_minimum_y_m: float) -> float:
    """THE OPEN-PIT (basin) trench floor elevation — the basin limb of the
    trench law (spec ``docs/specs/basin-rim-flush-seating-spec.md``
    section 2.1 item 3; owner ruling 2026-08-09, docs/RULINGS.md "the
    basin experiment").

    THE ONE LAW, imported by the emitter
    (``object_terrain_assembly.build_tunnel_layout_shapes``) and by any
    validator that has to reproduce a basin floor — the same lockstep
    ruling R1 sets for :func:`tunnel_trench_floor_elevation_m`.  A second
    copy of this arithmetic is the census-wrapper defect in miniature.

    THREE DIFFERENCES from the tunnel law above, each measured:

    * ``rim_estimate_elevation_m`` (``R_est``) is the MEDIAN DEM sample
      around the facility's own body outline, NOT the point sample at the
      placement anchor.  The anchor is an arbitrary point inside the pit:
      at OTHH Dewatering_01 it read 0.80 m against a rim-band DEM range
      of 0.71-2.96 m, so the datum-keyed floor was keyed to the shallow
      end of its own rim.
    * ``solid_minimum_y_m`` is the structure's TRUE deepest solid
      (``_StructureFrame.minimum_effective_height_m``), never the
      largest-perimeter-share interface level the bowl rule reports:
      Drainage_06's true minimum is −4.201 m against a −3.859 m floor
      key, which left 0.158 m of the promised 0.5 m clearance.
    * ``config.TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M`` covers the estimate
      error in ``R_est`` — the built mesh settles at the SOLVED surface,
      not the DEM (0.79 m of measured DEM-versus-solved gap at OTHH).

    Both offsets are SUBTRACTED, so the floor always sits strictly below
    the modelled bottom; the extra depth is under the object and
    invisible from above.
    """
    from .config import (
        TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M,
        TUNNEL_FLOOR_BELOW_OBJECT_DECK_M,
    )
    return (
        float(rim_estimate_elevation_m)
        + float(solid_minimum_y_m)
        - float(TUNNEL_FLOOR_BELOW_OBJECT_DECK_M)
        - float(TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M)
    )


# ══════════════════════════════════════════════════════════════════════
# THE REMAINING REGULATORY FAMILIES
# (spec docs/specs/DRAFT-reg-families-round-spec.md, rounds A and B)
#
# COMPLETENESS STANDARD (owner 2026-08-02, verbatim: "our grade law must
# not allow us to generate an airport patch that violates any of the
# region appropriate regulations"): every family below is a GENERATION-
# BINDING clamp/envelope AND has a validator twin reading the SAME
# function.  A validator-only check is visibility, not law.
#
# ARCHITECTURE NOTE (decide-and-note, build-complete-then-debug): the
# draft specced each family as a new parameter threaded into the
# adjacent-ground march.  Instead every family binds by EXTENDING THE
# LAW FUNCTION THE EMITTER ALREADY CALLS — ``adjacent_ground_envelope``
# (§A2, §B1), ``runway_end_envelope`` / ``resa_transverse_clamp`` (§A1),
# ``runway_strip_longitudinal_clamp`` (§A3(b)), ``classify_pair`` (§B2).
# One law, one call site, no second authority; it is also the
# single-pass reading of the owner's single-solve architecture ("EMITTERS
# EMIT, NEVER GRADE").
# ══════════════════════════════════════════════════════════════════════


# ── THE RUNWAY PROFILE'S OWN LAW, ruleset-keyed (§4 rows 1-4) ────────
# The runway profile modules (``runway_regrade``, ``runway_redistribute``,
# ``pavement/runway_segments``) and the validator
# (``verification.check_runway_profile``) read the caps through THESE
# functions, so an FAA and an ICAO runway are solved and judged by their
# own authority's numbers rather than by one blended constant.

def runway_profile_law(code_number, code_letter=None, approach_class=None,
                       runway_length_m=None, ruleset=None) -> dict:
    """THE complete longitudinal law of one runway under one ruleset.

    Keys: ``max_grade`` (§3.1.14 / §3.16.1), ``end_grade`` (the
    first/last-quarter cap, ``None`` where the authority states none for
    this class), ``end_zone_m`` (the length of ONE end zone — ICAO's
    quarter, FAA's lesser-of-quarter-and-762 m), ``max_grade_change``
    (§3.1.15 / §3.16.1), ``vertical_curve_k_m`` (metres of curve per 1 %,
    §3.1.16 / §3.16.1), ``max_grade_change_per_m`` (the same rule in the
    segment smoother's unit) and ``vertical_curve_min_change`` (the
    grade change below which no curve is required, ``None`` where the
    authority grants no relief).

    ONE resolver for the solver and the validator: a second copy would
    let the surface we build and the surface we check disagree about
    which authority governs.
    """
    return {
        "max_grade": ruleset_runway_max_grade(
            code_number, code_letter, ruleset),
        "end_grade": ruleset_runway_end_grade(
            code_number, code_letter, approach_class, ruleset),
        "end_zone_m": (None if runway_length_m is None
                       else ruleset_runway_end_zone_length_m(
                           runway_length_m, ruleset)),
        "max_grade_change": ruleset_runway_max_grade_change(
            code_number, code_letter, ruleset),
        "max_grade_change_per_m": ruleset_runway_max_grade_change_per_m(
            code_number, code_letter, ruleset),
        "vertical_curve_min_change": ruleset_runway_vertical_curve_min_change(
            code_number, code_letter, ruleset),
    }


def taxi_longitudinal_cap(code_letter=None, ruleset=None) -> float:
    """§4 row 13 — the taxiway family's longitudinal cap, ruleset-keyed.
    ICAO Annex 14 §3.9.8 gives A/B 3 %; FAA §4.14.1.1.1 gives 1.5 % for
    every letter (the ≤30,000 lb 2 % relaxation is NOT taken — the
    builder does not know a taxiway's fleet)."""
    return ruleset_taxi_max_grade(code_letter, ruleset)


# ── §A3(a) — the longitudinal-aware breach trigger ───────────────────

def strip_longitudinal_breaches(stations_s, stations_z, max_slope,
                                arc_rate_per_m=None):
    """Indices of strip stations whose RESULTING surface breaches the
    strip's own LONGITUDINAL law — the completeness half of the
    breach-trigger design (§A3(a)).

    ``stations_s`` are along-axis positions (m), ``stations_z`` the
    resulting surface elevations at them (``None`` = no reading).  A
    station is returned when either
      * the pair it forms with its predecessor exceeds ``max_slope``, or
      * (with ``arc_rate_per_m``) the grade CHANGE across it exceeds the
        rate over the mean of its two spacings — the same
        second-difference form ``_arc_rate_pass`` binds.

    WHY THIS EXISTS.  The adjacent-ground march emits a band when ground
    breaches the corridor LATERALLY.  Ground that conforms laterally but
    breaches longitudinally was therefore never emitted, so the §2 clamp
    never saw it — the HEAZ 146-row population (worst 7.59 % against the
    1.50 % cap, 88 rows raw-DEM at both ends).  Wiring this predicate
    into the march's trigger makes the trigger stop being blind on one
    axis; it does NOT introduce a fill mandate (ground that is lawful on
    both axes is still left alone).

    POPULATION CAVEAT (dispatch note, honest): the 146-row measurement
    was taken at 5eaf1e2 and a later flip adjudication FALSIFIED its
    reproduction at the current base.  The mechanism is implemented as
    designed; the population it fires on is a DEBUGGING question, and
    the first read at the current tree is owed before any effect size is
    quoted.
    """
    hits = []
    n = min(len(stations_s), len(stations_z))
    for k in range(1, n):
        a, b = stations_z[k - 1], stations_z[k]
        if a is None or b is None:
            continue
        ds = abs(float(stations_s[k]) - float(stations_s[k - 1]))
        if ds < 1e-9:
            continue
        if abs(float(b) - float(a)) > float(max_slope) * ds + 1e-12:
            hits.append(k)
    if arc_rate_per_m:
        for k in range(1, n - 1):
            a, b, c = stations_z[k - 1], stations_z[k], stations_z[k + 1]
            if a is None or b is None or c is None:
                continue
            dp = abs(float(stations_s[k]) - float(stations_s[k - 1]))
            dn = abs(float(stations_s[k + 1]) - float(stations_s[k]))
            if dp < 1e-9 or dn < 1e-9:
                continue
            change = abs((float(c) - float(b)) / dn
                         - (float(b) - float(a)) / dp)
            if change > float(arc_rate_per_m) * 0.5 * (dp + dn) + 1e-12:
                hits.append(k)
    return sorted(set(hits))


def strip_longitudinal_law(code_number, code_letter=None, ruleset=None):
    """``(max_slope, arc_rate_per_m)`` — the strip's complete
    longitudinal law for one runway class under one ruleset.  ONE
    resolver for the march's trigger, the clamp and the validator."""
    return (ruleset_strip_max_longitudinal_slope(
                code_number, code_letter, ruleset),
            ruleset_strip_arc_rate_per_m(ruleset))


# ── §A4 — RADIO ALTIMETER OPERATING AREA (ICAO/EASA only) ────────────

def raoa_footprint_ring(threshold_xy, inward_axis, ruleset=None):
    """THE RAOA rectangle as a CLOSED ring of ``(x, y)`` in the caller's
    planar metre frame, or ``None`` where the ruleset has no such family
    (every FAA airport — the string "radio altimeter" does not occur in
    AC 150/5300-13B, verified).

    ``threshold_xy`` is the runway threshold; ``inward_axis`` the unit
    vector pointing FROM the threshold INTO the runway, so the rectangle
    is laid out on the APPROACH side (before the threshold), which is
    where Annex 14 §3.8.2 puts it.  Geometry-library free, exactly like
    ``runway_strip_wall_keepout_rings``, so the emitter and
    ``tools/check_grade`` build the identical footprint.

    Annex 14 §3.8.2/§3.8.3: at least 300 m before the threshold, 60 m
    each side of the extended centreline.
    """
    rs = get_ruleset(ruleset)
    if not rs.raoa_length_m or not rs.raoa_half_width_m:
        return None
    import math as _math
    ux, uy = float(inward_axis[0]), float(inward_axis[1])
    norm = _math.hypot(ux, uy)
    if norm < 1e-12:
        return None
    ux, uy = ux / norm, uy / norm
    px, py = -uy, ux
    ax, ay = float(threshold_xy[0]), float(threshold_xy[1])
    L = float(rs.raoa_length_m)
    W = float(rs.raoa_half_width_m)
    corners = ((0.0, -W), (-L, -W), (-L, W), (0.0, W))
    ring = [(ax + ux * s + px * t, ay + uy * s + py * t)
            for (s, t) in corners]
    return ring + [ring[0]]


def raoa_applies(approach_class, ruleset=None) -> bool:
    """Whether the RAOA family binds for a runway END.

    Annex 14 §3.8.1 scopes it to PRECISION APPROACH runways; CS
    ADR-DSN.B.205 corroborates (Cat II/III mandatory-ish, Cat I where
    practicable).  Bound here for ALL precision approaches — the
    stricter CONTAINED reading, since the builder cannot know an end's
    ILS category.  The approach class comes from the repo's ONE
    classifier, ``config.runway_end_approach_class``; no second
    classification is minted.
    """
    rs = get_ruleset(ruleset)
    if not rs.raoa_length_m:
        return False
    return str(approach_class) == "precision"


def raoa_rate_clamp(stations_s, alts, ruleset=None, pinned=None,
                    max_passes=8):
    """THE generation-binding half of §A4: return ``alts`` with the
    RAOA's along-approach profile made rate-of-change compliant.

    Annex 14 §3.8.4: "The rate of change between two consecutive slopes
    should not exceed 2 per cent per 30 m."  This is exactly the §A3(b)
    curvature machinery on a second footprint, which is why the two
    families share a round and share ``_arc_rate_pass`` rather than
    growing a second implementation.

    COMPOSITION (pre-registered as a named twin): the RAOA clamp
    COMPOSES with the end-corridor floors, never overrides them — on a
    conflict the STRICTER bound governs, which is what running this
    clamp on a profile the skirt law already bounded produces (the
    clamp only reduces second differences; it never lifts a value out of
    the skirt corridor by more than the excess it removes, and the
    caller re-asserts the skirt floor afterwards).
    """
    rs = get_ruleset(ruleset)
    rate = rs.raoa_max_grade_change_per_m
    if not rate:
        return list(alts)
    idx = [i for i, a in enumerate(alts) if a is not None]
    if len(idx) < 3:
        return list(alts)
    s = [float(stations_s[i]) for i in idx]
    z = [float(alts[i]) for i in idx]
    free = [not (pinned is not None and i < len(pinned) and pinned[i])
            for i in idx]
    for _ in range(int(max_passes)):
        if not _arc_rate_pass(s, z, free, float(rate)):
            break
    out = list(alts)
    for k, i in enumerate(idx):
        if free[k]:
            out[i] = z[k]
    return out


# ── §B1 — SHOULDER TRANSVERSE (crown) LAW ────────────────────────────

def shoulder_transverse_envelope(distance_from_pavement_edge_m: float,
                                 shoulder_width_m: float,
                                 ruleset=None) -> tuple:
    """The lawful ``(floor_offset, ceiling_offset)`` for a point on a
    PAVED shoulder, relative to the pavement edge it abuts.

    FAA Table 3-6 S-2 / §4.14.2 item 3: paved shoulders fall 1.5-5.0 %
    away from the pavement — a mandatory-DOWN band, so a FLAT shoulder is
    unlawful and the ceiling is strictly below 0.  ICAO §3.2.3: the
    shoulder "should be flush with the surface of the runway and its
    transverse slope should not exceed 2.5 per cent" — no mandated fall,
    so the corridor is the symmetric ±2.5 % about flush.

    Returns ``(None, None)`` where the ruleset states no shoulder
    transverse law at all.
    """
    sh_min, sh_max = ruleset_shoulder_transverse_band(ruleset)
    if not sh_max:
        return (None, None)
    d = min(max(0.0, float(distance_from_pavement_edge_m)),
            max(0.0, float(shoulder_width_m)))
    if sh_min is None:
        return (-float(sh_max) * d, float(sh_max) * d)
    return (-float(sh_max) * d, -float(sh_min) * d)


def shoulder_edge_dropoff_allowance_m(ruleset=None) -> float:
    """The MAXIMUM lawful vertical step at a paved→unpaved boundary.

    FAA §4.14.2 item 2 (and §5.9.1.5 for aprons) MANDATES a 1.5 in ±
    0.5 in (38 ± 13 mm) drop-off between paved and unpaved surfaces —
    which means an emitted step of up to 51 mm there is the regulation
    being obeyed, not a tear.  The step checks
    (``_check_vertex_to_edge_step`` / ``_check_edge_midpoint_step``) and
    the seam law take this as an exemption UNDER THE FAA RULESET ONLY and
    ONLY at paved/unpaved boundaries.

    Returns 0.0 where the authority mandates flush instead (ICAO
    §3.2.3), so the exemption is a no-op at every ICAO airport.

    PROSPECTIVE LAW, stated honestly: no emitter mints a 38 mm step
    today, so this exemption changes zero rows at present.  It exists so
    that when the shoulder band does emit one, the census does not call
    the regulation a defect.
    """
    drop, tol = ruleset_shoulder_edge_dropoff(ruleset)
    if not drop:
        return 0.0
    return float(drop) + float(tol or 0.0)


def shoulder_edge_dropoff_exempt(step_m: float, paved_to_unpaved: bool,
                                 ruleset=None) -> bool:
    """Whether a vertical ``step_m`` at a boundary is the MANDATED
    paved→unpaved drop-off rather than a defect.

    The ruleset resolves the NUMBER here; the PREDICATE itself lives in
    ``strip_seam_law.paved_unpaved_dropoff_exempt``, which the seam
    healer, the step checks and the census all read (one text, per the
    round's interaction fence).  That module is deliberately stdlib-only
    — it sits on a hot solve path and is imported by the standalone
    ``tools/check_grade.py`` — so the dependency runs THIS way and never
    the other."""
    if not paved_to_unpaved:
        return False
    from .strip_seam_law import paved_unpaved_dropoff_exempt
    return paved_unpaved_dropoff_exempt(
        step_m, shoulder_edge_dropoff_allowance_m(ruleset))


# ── §B2 — TRANSVERSE SOLVER-BINDING COMPLETION ───────────────────────
# The caps EXIST and the validator reads them (``check_transverse_grade``
# at 10 m stations over the sidecar axes); what was missing is a
# CONSTRAINT on the interpolated SURFACE between the constrained vertex
# pairs.  The station generator below is imported by BOTH the solver's
# constraint builder and the validator's transect reader, so the two are
# in lockstep BY CONSTRUCTION rather than by matching numbers.

TRANSVERSE_STATION_STEP_M = 10.0


def transverse_transect_stations(axis_a, axis_b, half_width_m,
                                 step_m: float = TRANSVERSE_STATION_STEP_M):
    """THE transect stations of one corridor: a list of
    ``(centre_xy, normal_xy, offsets)`` — for each along-axis station,
    its centre point, the unit cross-axis direction, and the signed
    lateral offsets sampled across the surface.

    ONE generator, two consumers (solver constraint rows + validator
    transect reader).  Deterministic and geometry-library free.
    """
    import math as _math
    ax, ay = float(axis_a[0]), float(axis_a[1])
    bx, by = float(axis_b[0]), float(axis_b[1])
    dx, dy = bx - ax, by - ay
    length = _math.hypot(dx, dy)
    if length < 1e-6 or half_width_m <= 0.0:
        return []
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    half = float(half_width_m)
    offsets = [-half, -0.5 * half, 0.0, 0.5 * half, half]
    n = max(1, int(length // max(1e-6, float(step_m))))
    out = []
    for k in range(n + 1):
        s = min(length, k * float(step_m))
        out.append(((ax + ux * s, ay + uy * s), (px, py), tuple(offsets)))
    return out


def transverse_cap_for_role(role: str, code_letter=None, ruleset=None):
    """The TRANSVERSE (cross-slope) cap a surface's role takes, or
    ``None`` where the role carries no transverse law of its own.

    Taxiway family: ICAO §3.9.11 1.5 % (C-F) / 2 % (A-B); FAA §4.14.2
    item 1a 1.0-1.5 % — the ≤30,000 lb 2 % relaxation is NOT taken (the
    builder does not know a taxiway's fleet; stricter contained
    reading).  Runway: ICAO §3.1.19 / FAA Table 3-6 S-1.  Apron / stand:
    the owner's 1 % cap, region-invariant, which contains both
    authorities' apron numbers.
    """
    rs = get_ruleset(ruleset)
    if role in _ADJACENT_RUNWAY_ROLES:
        return rs.runway_transverse_max.value(None, code_letter)
    if role in _ADJACENT_TAXIWAY_ROLES:
        return ruleset_taxi_transverse_max(code_letter, rs)
    if role in _ADJACENT_APRON_ROLES:
        return APRON_MAX_GRADE
    return None


def transverse_minimum_for_role(role: str, ruleset=None):
    """The transverse MINIMUM (the crown mandate) — BOUND ON RUNWAYS,
    recorded-only on taxiways (owner ruling d48bc0a).

    FAA Table 3-6 S-1 and §4.14.2 item 1a both put a 1.0 % floor on the
    cross-slope, and ICAO §3.1.19 says the runway transverse should
    "[not] be less than 1 per cent except at runway or taxiway
    intersections".  Owner question 5 is ANSWERED for runways: this
    version implements runway crowns and BINDS their minimum.  The
    taxiway floor stays an informational class with its citation — the
    owner scoped this version's drainage work to runway crowns and
    pavement-edge shaping only.

    This returns the ruleset value for BOTH families, because a
    recorded-unbound law is still a law that reports; whether it BINDS is
    :func:`transverse_minimum_binds`.
    """
    rs = get_ruleset(ruleset)
    if role in _ADJACENT_RUNWAY_ROLES:
        return rs.runway_transverse_min
    if role in _ADJACENT_TAXIWAY_ROLES:
        return rs.taxi_transverse_min
    return None


def transverse_minimum_binds(role: str) -> bool:
    """Whether the crown minimum is a CONSTRAINT for ``role`` (owner
    d48bc0a) — runways yes, taxiways recorded-only.

    ONE reader for the scope, so the generator's bound, the validator's
    band and the twins cannot each carry their own idea of which families
    the owner actually turned on."""
    if role in _ADJACENT_RUNWAY_ROLES:
        return bool(CROWN_MINIMUM_BOUND_RUNWAYS)
    if role in _ADJACENT_TAXIWAY_ROLES:
        return bool(CROWN_MINIMUM_BOUND_TAXIWAYS)
    return False


def runway_crown_rate(ruleset=None, code_letter=None) -> float:
    """THE runway crown rate generation must build to, from the LAW.

    The generated crown used to be a free-standing tuning constant
    (``config.RUNWAY_CROWN_TRANSVERSE``) that happened to equal the
    ruleset minimum; nothing asserted the two, so a change to either
    silently produced a runway crown below its own mandated floor.  With
    the minimum BOUND (owner d48bc0a) the rate is derived: at least the
    ruleset's transverse MINIMUM, never above its transverse MAX.

    Raises ``ValueError`` when a ruleset's own minimum exceeds its own
    maximum — a genuine contradiction, LOUD, never silently softened
    (``feasibility-is-guaranteed``; the same discipline
    :func:`drainage_minimum_band` applies)."""
    from auto_patch.config import RUNWAY_CROWN_TRANSVERSE
    rate = float(RUNWAY_CROWN_TRANSVERSE)
    low = transverse_minimum_for_role("runway", ruleset)
    high = transverse_cap_for_role("runway", code_letter, ruleset)
    if low is not None and high is not None and float(low) > float(high):
        raise ValueError(
            f"runway transverse minimum {low} exceeds the maximum {high} "
            f"under ruleset {get_ruleset(ruleset).key!r}")
    if low is not None and transverse_minimum_binds("runway"):
        rate = max(rate, float(low))
    if high is not None:
        rate = min(rate, float(high))
    return rate


def transverse_surface_bounds(role, code_letter, offset_m, ruleset=None):
    """The lawful ``(min_dz, max_dz)`` of a transect sample at signed
    lateral ``offset_m`` relative to the corridor centreline — the
    CONSTRAINT ROW the solver adds, and the same bound the validator's
    transect reader judges against.

    Where the crown minimum does NOT bind (taxiways, this version) this
    is the symmetric ``±cap·|offset|`` band; where it BINDS (runways,
    owner d48bc0a) it is the mandatory-down crown band
    ``[-cap·|t|, -min·|t|]`` — the surface must FALL away from the
    centreline at between the minimum and the maximum rate.
    """
    cap = transverse_cap_for_role(role, code_letter, ruleset)
    if cap is None:
        return (None, None)
    t = abs(float(offset_m))
    if not transverse_minimum_binds(role):
        return (-float(cap) * t, float(cap) * t)
    low = transverse_minimum_for_role(role, ruleset)
    if low is None:
        return (-float(cap) * t, float(cap) * t)
    return (-float(cap) * t, -float(low) * t)


# ── §B3 — DRAINAGE MINIMUM (apron + groundside) ──────────────────────

# ── §B3's GROUNDSIDE HALF — RETIRED (owner 2026-08-14) ───────────────
# RULINGS 2026-08-14, "DRAINAGE RULING SCOPE CLARIFIED": what retires is
# "ADDING drainage curvature (crown / minimum-slope requirements) to
# TAXIWAY and ROAD pavement surfaces; those may be flat for the sim …
# the drainage_minimum census family retires only where it demanded
# curvature ON taxiway/road/groundside pavement surfaces."
#
# So this set — the LANDSIDE PAVEMENT domain of §B3 — is EMPTY, by law.
# ``groundside_pavement``, ``service_road`` and ``service_junction`` are
# exactly the road-family surfaces the ruling exempts (the first grades at
# the ROAD limit by owner ruling 2026-08-12, "it carries the same vehicles
# the service road does"), and no taxiway role was ever in it.  The
# PROVISIONAL 1.0 % ``config.GROUNDSIDE_MIN_DRAINAGE_GRADE`` — owner
# question 3, version-deferred, never adjudicated — is the number that
# stops binding; it stays in ``config`` with its research trail.
#
# WHAT DID NOT RETIRE, and is untouched here (same ruling): the APRON half
# below (FAA §5.9.1.1's cited 0.5 %), the DRAINAGE SPINE in enclosed areas
# (``drainage_spine_envelope`` / ``DRAINAGE_SPINE_PARENT_ROLES``), the
# DRAINAGE SLOPE on ADJACENT GROUND beside runways and taxiways
# (``adjacent_ground_envelope`` and the strip/RSA bands), and the RUNWAY
# CROWN (``transverse_surface_bounds`` under CROWN_MINIMUM_BOUND_RUNWAYS).
#
# THE SET IS KEPT, EMPTY, RATHER THAN DELETED — deliberately.  It is what
# ``check_grade._DRAINAGE_MIN_ROLES`` derives from, and an empty set the
# census still derives from states "the law grants this family no landside
# surface" in the one place both halves read.  Deleting it would put the
# apron-only walk back to naming its own roles — the hand-typed-tuple
# shape that produced the original §B3 defect.
#
# HOW IT GOT HERE, because the difference is the whole point (S3 dossier;
# RULINGS 2026-08-13b, "OTHH −639 ADJUDICATED: CENSUS BLINDNESS"): these
# three roles were ALREADY absent from this walk — not by law, but because
# the corridor round re-roled ~15.5 km of landside pavement perimeter out
# of ``groundside_pavement`` into ``service_junction`` / ``service_road``
# and the set named only the old role.  11,932 rows across the five
# baseline airports went unread, and OTHH's −750 was quoted as an
# improvement.  S7 half 1 restored them (aba74b7) so the count could be
# READ; the owner then ruled the law away.  Zero-because-exempt and
# zero-because-unread print the same number, and only one of them comes
# from an instrument that works.
#
# DEAD LITERALS REMOVED (S7 audit, retained through the retirement).
# ``groundside``, ``parking``, ``lot`` and ``curbside`` appear in no
# ``layout.ROLE_*`` constant — this engine has never emitted any of them.
# They were the civil sources' PROSE categories, not role values.
_DRAINAGE_MIN_GROUNDSIDE_ROLES: frozenset = frozenset()


def drainage_minimum_grade(role: str, ruleset=None,
                           terrace_panel: bool = False,
                           building_pad: bool = False):
    """The MINIMUM fall a surface must carry toward its drainage edge, or
    ``None`` where none binds.

    * APRON family — FAA §5.9.1.1 Standards: "Provide a minimum 0.5
      percent apron gradient".  ICAO §3.13.4 is qualitative and states NO
      number, so the ICAO-side constant is ``None`` and this law is a
      no-op at every ICAO airport (jurisdictional fidelity; a numeric
      ICAO minimum would be MINTED, not cited).
    * GROUNDSIDE / ROAD pavement — RETIRED (owner 2026-08-14, see the
      block above).  The landside minimum was region-invariant and
      PROVISIONAL (owner question 3, never adjudicated); the owner
      answered it by withdrawing it, so
      :data:`_DRAINAGE_MIN_GROUNDSIDE_ROLES` is empty and this function
      returns ``None`` for every road-family surface.

    EXCLUSIONS, named and twin-tested:
    * ``building_pad`` — building-pad seats stay FLAT
      (``TERMINAL_PADS_SLOPE=False`` is owner law).
    * ``terrace_panel`` — the apron terrace law (owner 2026-08-04) makes
      "level panels" lawful; whether a level panel must nevertheless
      carry the 0.5 % drainage fall is OWNER QUESTION 4.  Until it is
      answered the minimum does NOT bind inside a declared terrace panel.
    """
    if building_pad or terrace_panel:
        return None
    if role in _ADJACENT_APRON_ROLES:
        return ruleset_apron_min_drainage_grade(ruleset)
    if role in _DRAINAGE_MIN_GROUNDSIDE_ROLES:      # empty since 2026-08-14
        return GROUNDSIDE_MIN_DRAINAGE_GRADE
    return None


def drainage_minimum_band(role: str, ruleset=None, **kw):
    """``(min_grade, max_grade)`` — the full drainage BAND of a surface.

    The upper bound is the surface's own within-shape cap
    (``ROLE_GRADE_LIMITS``), so a stand under the FAA ruleset reads
    ``[0.005, 0.010]`` — the §B3 pre-registration's "no stand exceeds
    1.0 %" upper twin and the 0.5 % lower twin are ONE band, never two
    laws that could disagree.
    """
    low = drainage_minimum_grade(role, ruleset, **kw)
    high = ROLE_GRADE_LIMITS.get(role)
    if high is None and role == "stand":
        # ``stand`` is an apron sub-role with no ROLE_GRADE_LIMITS row of
        # its own; its cap is the aircraft-stand maximum (ICAO §3.13.5 /
        # FAA §5.9.2.1.1, both 1 %).
        high = ruleset_stand_max_grade(ruleset)
    if low is not None and high is not None and low > high:
        # A minimum above the surface's own cap is a genuine
        # contradiction — LOUD, never silently softened (feasibility is
        # guaranteed; a real airport admits a lawful surface).
        raise ValueError(
            f"drainage minimum {low} exceeds the {role!r} cap {high} "
            f"under ruleset {get_ruleset(ruleset).key!r}")
    return (low, high)


def apron_max_grade_change(ruleset=None):
    """FAA §5.9.1.3: maximum apron grade change 2 %.  ``None`` under
    ICAO, which states no number."""
    return ruleset_apron_max_grade_change(ruleset)


def drainage_minimum_shortfall(grade: float, role: str, ruleset=None, **kw):
    """How far below its drainage minimum a measured ``grade`` sits (0.0
    when compliant or when no minimum binds) — the validator twin's one
    reading, so emitter and census cannot disagree about what "too flat"
    means."""
    low = drainage_minimum_grade(role, ruleset, **kw)
    if low is None:
        return 0.0
    return max(0.0, float(low) - abs(float(grade)))
