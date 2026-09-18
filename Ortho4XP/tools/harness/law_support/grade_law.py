"""The GRADE LAW the census prices pairs with.

COPIED from ``grade_law.py`` on 2026-09-17 (lane ``v1retire`` round 1, ruling (d)
of the stage-B brief: "the census stays engine-neutral BY IMPLEMENTATION").
`tools/check_grade.py` priced v2 patches with law machinery that lived in
modules the v1 deletion takes; what it USES is copied here ONCE, verbatim, and
the census reads it from the harness.  Values that are law live in
``auto_patch/config.py`` (KEEP) or ``auto_patch_v2/law/*.toml`` and are
IMPORTED, never re-spelled.

Do not edit to change behaviour: this is a transcription, and the acceptance
was a census A/B on the same HECA patch bytes reading IDENTICAL.
"""

from __future__ import annotations
from auto_patch.config import ROAD_CROSS_SECTION_LAW

from .roles import AUTHORITY_PRECEDENCE
from .roles import ROLE_SERVICE_ROAD
from .roles import authority_rank
from .strip_seam import paved_unpaved_dropoff_exempt
from auto_patch import config as _cfg
from auto_patch.config import ADJACENT_GROUND_LIP_MAX_DOWN_SLOPE
from auto_patch.config import ADJACENT_GROUND_LIP_MIN_DOWN_SLOPE
from auto_patch.config import ADJACENT_GROUND_LIP_WIDTH_M
from auto_patch.config import ADJACENT_GROUND_UNGRADED_STRIP_MAX_UP_SLOPE
from auto_patch.config import APRON_MAX_GRADE
from auto_patch.config import APRON_SHOULDER_MAX_DOWN_SLOPE
from auto_patch.config import APRON_SHOULDER_MIN_DOWN_SLOPE
from auto_patch.config import APRON_SHOULDER_WIDTH_M
from auto_patch.config import BUILDING_FRONTAGE_MAX_GRADE
from auto_patch.config import BUILDING_REACH_CORRIDOR_M
from auto_patch.config import CLEARANCE_LATERAL_MAX_SLOPE
from auto_patch.config import CLEARANCE_MAX_REACH_M
from auto_patch.config import CROWN_MINIMUM_BOUND_RUNWAYS
from auto_patch.config import CROWN_MINIMUM_BOUND_TAXIWAYS
from auto_patch.config import DRAINAGE_SPINE_MIN_FALL_M
from auto_patch.config import FAA_RULESET
from auto_patch.config import FAN_RAMP_CAP
from auto_patch.config import GAP_PAVEMENT_CONFORM_MARGIN_M
from auto_patch.config import GROUNDSIDE_MIN_DRAINAGE_GRADE
from auto_patch.config import JUNCTION_MESH_CONSTRAINTS
from auto_patch.config import ROAD_TRANSVERSE_AXIS_MIN_DEG
from auto_patch.config import ROLE_GRADE_LIMITS
from auto_patch.config import RUNWAY_END_CLEARANCE_LENGTH_BY_CODE
from auto_patch.config import SERVICE_ROAD_MAX_GRADE
from auto_patch.config import TAXI_MAX_GRADE
from auto_patch.config import get_ruleset
from auto_patch.config import ruleset_apron_min_drainage_grade
from auto_patch.config import ruleset_shoulder_edge_dropoff
from auto_patch.config import ruleset_shoulder_transverse_band
from auto_patch.config import ruleset_strip_arc_rate_per_m
from auto_patch.config import ruleset_strip_band_max_down_slope
from auto_patch.config import ruleset_strip_half_width_m
from auto_patch.config import ruleset_strip_max_longitudinal_slope
from auto_patch.config import ruleset_taxi_transverse_max
from auto_patch.config import runway_code_number
from auto_patch.config import taxiway_strip_graded_half_width_for_letter
from auto_patch.config import transverse_cap_for_longitudinal_cap
from dataclasses import dataclass
from typing import Callable, Optional
import auto_patch.config as _cfg
import math as _math
import os


APRON_ROLE = "apron"


JUNCTION_ROLES = ("junction", "service_junction")


ROAD_ROLES = frozenset({"service_road", "service_junction"})


def _road_carve_outranked_by_host(role: str) -> bool:
    """True when ``role`` OUTRANKS the road roles, so the road-carve
    relaxation in :func:`classify_pair` may not re-price its pairs.

    STRICT CLAIM (owner 2026-08-29c, spec
    ``docs/specs/runway-crossing-strict-claim-spec.md`` law 1): at a
    contact the strictest claimant's law wins — runway > taxi family >
    apron > road.  The rank comes from ``layout.AUTHORITY_PRECEDENCE``,
    which is ALREADY that order and is what ``to_osm`` uses to pick the
    one author of a shared node; minting a second rank table here is the
    two-instruments defect this campaign keeps paying for.

    Both readings are done at CALL time (config for the gate, layout for
    the rank) so a twin can flip the gate without a module reload, and
    so the import stays lazy — ``layout`` imports this module.

    Gate ``config.STRICT_CLAIM_CAP``; OFF returns False everywhere,
    which is the unguarded pre-ruling relaxation byte for byte.

    BUILD-TIME: this sits on the all-pair classify loop, so the role set
    is derived from ``AUTHORITY_PRECEDENCE`` ONCE and then answered by a
    frozenset hit.  Only the gate is re-read per call (a twin flips it
    without a module reload), and the caller reaches here only on a pair
    that would otherwise BE relaxed."""
    from auto_patch import config as _cfg
    if not bool(getattr(_cfg, "STRICT_CLAIM_CAP", True)):
        return False
    global _OUTRANKS_ROAD
    if _OUTRANKS_ROAD is None:
        from .roles import (AUTHORITY_PRECEDENCE, ROLE_SERVICE_ROAD,
                             authority_rank)
        _road = authority_rank(ROLE_SERVICE_ROAD)
        _OUTRANKS_ROAD = frozenset(
            r for r in AUTHORITY_PRECEDENCE if authority_rank(r) < _road)
    return role in _OUTRANKS_ROAD


_OUTRANKS_ROAD = None


def ring_path_cumulative(ring):
    """``(cum, total)`` for a closed ring — ``cum[i]`` is the arclength
    from vertex 0 to vertex ``i`` walking forward, ``total`` the whole
    perimeter.  Geometry-library free, like the rest of this module."""
    n = len(ring)
    cum = [0.0] * n
    if n < 2:
        return cum, 0.0
    acc = 0.0
    for i in range(1, n):
        (xa, ya), (xb, yb) = ring[i - 1], ring[i]
        acc += _math.hypot(xb - xa, yb - ya)
        cum[i] = acc
    (xa, ya), (xb, yb) = ring[n - 1], ring[0]
    total = acc + _math.hypot(xb - xa, yb - ya)
    return cum, total


def ring_path_distance(cum, total, i, j):
    """The shorter of the two ring walks between vertices ``i`` and ``j``."""
    fwd = abs(cum[j] - cum[i])
    return min(fwd, total - fwd) if total > 0.0 else fwd


def road_pair_distance(ring, cum, total, i, j, chord):
    """THE road-family within-shape pair distance (Amendment 1 clause 1).

    ``max(chord, ring walk)`` — the walk by construction, and the max is
    belt-and-braces against a degenerate ring whose walk rounds under its
    own chord.  ONE implementation: ``grade_graph.shape_constraints``
    prices every road pair through it and both readers of that function
    (the solver's graph and ``tools/check_grade``'s
    ``iter_shape_grade_constraints``) therefore see the same number —
    the census-wrapper law applied to a metric instead of a family.
    """
    return max(float(chord), ring_path_distance(cum, total, i, j))


RUNWAY_END_SKIRT_MAX_DOWN_GRADE = FAA_RULESET.end_skirt_max_down_grade


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
        if True:    # O4_FABRIC_W2_RETIRE_APRON_SURROUND is DEFAULT-ON (fabric_flags registry)
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
        if True:    # O4_FABRIC_W2_RETIRE_SERVICE_SHADOW is DEFAULT-ON (fabric_flags registry)
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
    if True:    # O4_FABRIC_W2_ICAO_STRIP_AUTHORITY is DEFAULT-ON (fabric_flags registry)
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
    if False:   # O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY is DEFAULT-ON; its OFF arm was pre-W2 v1
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
    from auto_patch.config import GAP_PAVEMENT_CONFORM_MARGIN_M
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


MIN_PAIR_DIST_M = 0.5


APRON_BODY_CHORD_MAX_M = float(os.environ.get("O4_APRON_BODY_CHORD_MAX_M", "60"))


APRON_INTERIOR_RAMP_CAP = (
    os.environ.get("O4_APRON_INTERIOR_RAMP_CAP", "1") != "0")


APRON_INTERIOR_CAP = FAN_RAMP_CAP


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


def transverse_span_budget_m(cap_l: float, width_m: float) -> float:
    """THE cross-section budget: ``transverse_cap_for_longitudinal_cap(cap_l)
    x width_m``.

    ``cap_l`` is the LONGITUDINAL cap of the axis segment the station sits
    on (the per-letter taxi cap, the apron cap, the service-road rate);
    the transverse cap is a pure function of it — the same one law source
    (``config.transverse_cap_for_longitudinal_cap``) the pair law's ``cT``
    resolves through.  ``width_m`` is the priced span's own width."""
    return transverse_cap_for_longitudinal_cap(cap_l) * float(width_m)


def long_axis_of_points(pts) -> "Optional[tuple]":
    """``((ux, uy), length, (mx, my))`` — the unit long axis, length and
    mid-point of the minimum-area rectangle of ``pts``, or ``None``.

    THE ROAD'S OWN DIRECTION, and THE one implementation of it: the
    station walk (``lateral_contiguity.long_axis``) and the pair
    classifier below must not each have their own idea of which way a
    road runs, or the law would price one set of pairs and the walk would
    describe another (this repo's 'two instruments, one assumed
    population').  Geometry-library free — it takes bare ``(x, y)`` — so
    the solver's ring lists and the validator's OSM rings both reach it
    without building a polygon.

    A blobby service JUNCTION has no natural axis; the minimum-area
    rectangle still gives every reader the SAME answer, which is what a
    shared convention is for, and the cross-section is then measured
    across the shape's short dimension — exactly where a laterally
    touching neighbour lies.
    """
    pts = [(float(x), float(y)) for (x, y) in pts]
    if len(pts) < 3:
        return None
    best = None
    for i in range(len(pts)):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % len(pts)]
        dx, dy = bx - ax, by - ay
        L = _math.hypot(dx, dy)
        if L < 1e-9:
            continue
        ux, uy = dx / L, dy / L
        us = [p[0] * ux + p[1] * uy for p in pts]
        vs = [-p[0] * uy + p[1] * ux for p in pts]
        w = max(us) - min(us)
        h = max(vs) - min(vs)
        if best is not None and w * h >= best[0]:
            continue
        umid = 0.5 * (max(us) + min(us))
        vmid = 0.5 * (max(vs) + min(vs))
        mid = (umid * ux - vmid * uy, umid * uy + vmid * ux)
        best = ((w * h), (ux, uy), w, mid) if w >= h else \
               ((w * h), (-uy, ux), h, mid)
    if best is None or best[2] <= 0.0:
        return None
    return best[1], best[2], best[3]


def pair_is_transverse(axis, dx: float, dy: float) -> bool:
    """Is the pair ``(dx, dy)`` the road's CROSS-SECTION rather than a run
    along it?  ``axis`` is the ``(ux, uy)`` of :func:`long_axis_of_points`.

    True when the pair's own axis stands at or beyond
    ``ROAD_TRANSVERSE_AXIS_MIN_DEG`` (45 °) to the road axis — the angle
    at which a pair stops being more along the road than across it.  The
    test is on the UNSIGNED angle (a chord and its reverse are the same
    chord), and the partition is EXHAUSTIVE: every pair is on one side of
    it, so no pair falls between the two laws.

    ``axis`` ``None`` (a degenerate ring the axis reader could not read)
    ⇒ False: with no road direction there is no cross-section to price,
    and the pair keeps its longitudinal cap — the pre-ruling reading, and
    never a tighter cap asserted on geometry we could not measure.
    """
    if axis is None:
        return False
    ux, uy = float(axis[0]), float(axis[1])
    d = _math.hypot(float(dx), float(dy))
    if d < 1e-9:
        return False
    # |cos θ| against the axis; θ ≥ 45 ° ⟺ |cos θ| ≤ cos 45 °.
    cos_t = abs(float(dx) * ux + float(dy) * uy) / d
    return cos_t <= _math.cos(_math.radians(ROAD_TRANSVERSE_AXIS_MIN_DEG))


def road_cross_section_cap(cap_l: float) -> float:
    """The cap a TRANSVERSE road pair prices at, given the longitudinal
    cap ``cap_l`` the rest of the chain selected for it.

    Delegates to ``config.transverse_cap_for_longitudinal_cap`` — the ONE
    law source the solver's anisotropic ``cT``, the emitter's
    cross-section pair budget and the transverse validator all resolve
    through.  Never a literal (the spec's own words), and never LOOSER
    than what came in: for every cap that is not a road/narrow-taxi rate
    the function is the identity, so a pair the rest of the law already
    tightened (a building frontage at 1 %) is untouched.
    """
    return min(float(cap_l), transverse_cap_for_longitudinal_cap(cap_l))


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
    #: ``claim_role``: the STRICTEST CLAIMANT among the pair's endpoints,
    #: by ``layout.AUTHORITY_PRECEDENCE`` (owner 2026-08-29c).  ``role``
    #: is the pair's pricing host, chosen by the reader — for a CROSS-
    #: SHAPE pair ``airside_no_step`` picks whichever side carries the
    #: smaller body cap, which is a cap question and therefore says
    #: nothing about who CLAIMS the contact.  A ``runway|service_junction``
    #: pair priced under the service junction's host role took the road
    #: carve's 8 % relaxation on a RUNWAY contact (measured at HECA: 1 row
    #: survived the within-shape guard).  Readers that know both roles set
    #: this; a within-shape reader leaves it None, where ``role`` already
    #: IS the claim (both endpoints are the same shape).
    claim_role: Optional[str] = None
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
    # ── THE CHORD-TARGET LAW (owner ruling RULINGS 2026-08-25, spec
    # ``apron-chord-anchor-target-spec.md`` §1) ─────────────────────────
    # ``nearest_anchor_pad``: THIS pair is that chord AND its far end is a
    # BUILDING PAD boundary vertex rather than a centerline node.  The
    # anchor set is the union of both populations and the NEAREST VISIBLE
    # one wins, so ``nearest_spine`` stays the strict-population flag (both
    # kinds are strict) and this one carries only the KIND.  The reader
    # (``grade_graph.nearest_spine_pairs``, the ONE enumeration both the
    # census and the bake consume) assigns it; the verdict is the law's,
    # exactly like every field above.
    #
    # DEFAULT FALSE IS TODAY'S READING: a reader that does not supply it —
    # or one running with ``O4_APRON_CHORD_ANCHOR_TARGET=0`` — sees the
    # pre-ruling cap assignment unchanged.
    nearest_anchor_pad: bool = False
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
    # ── THE ROAD CROSS-SECTION (owner ruling RULINGS 2026-08-25g) ───────
    # ``transverse_road``: this pair is a ROAD ring's CROSS-SECTION — its
    # own axis stands at or beyond 45 ° to the ring's long axis
    # (:func:`pair_is_transverse` over :func:`long_axis_of_points`).  The
    # ring axis is computed ONCE PER SHAPE by the reader and the verdict
    # is the law's, exactly like ``a_in_strip`` / ``in_interior_zone``
    # above.
    #
    # DEFAULT FALSE IS TODAY'S READING: a reader that does not supply it
    # — or one running with ``O4_ROAD_CROSS_SECTION_LAW=0`` — prices
    # every road pair at its longitudinal cap, exactly as before 25g.
    transverse_road: bool = False


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
        # FRONTAGE-ONLY (lead ruling 2026-08-24, narrowing this lane's
        # first cut).  ``building_keys`` is NOT consulted: ``build_context``
        # widens that set by SNAPPING every soft vertex within a tolerance
        # of a pad boundary into it, so "or a building key" re-admitted
        # most of the apron and the stand class did not shrink at all
        # (HECA v3 measured 1,793 of 1,795 apron rows still at 1 %, against
        # 1,751 before the split).  The frontage-vertex set is the
        # predicate the spec named and the only one that means "this vertex
        # is part of a pad's frontage".
        # ── THE CHORD TARGET (owner ruling RULINGS 2026-08-25) ────────
        # "The anchor set is BOTH the building pads and the taxiway
        # centerline nodes — whichever is closer wins… the pad is a
        # first-class chord target, not merely an interceptor when it
        # happens to lie in the path."  A chord whose target IS a pad is
        # therefore a PAD↔apron stand chord and prices in THIS class —
        # the same class the 2026-08-21f interception already priced its
        # replacement chord to, now reached by the target rather than by
        # the accident of standing in the path.  A chord to a CENTERLINE
        # keeps the 2026-08-24c reading below unchanged.
        if p.nearest_anchor_pad:
            return APRON_CLASS_STAND
        if p.a_frontage or p.b_frontage:
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
    #   AND NEVER FOR A HOST THAT OUTRANKS THE ROAD (owner 2026-08-29c,
    #   "A CONTACT IS A VALUE QUESTION, NEVER A CAP QUESTION"): where a
    #   road meets or crosses airside pavement the STRICTEST claimant's
    #   law wins, so the carve may not re-price the HOST's own pairs at
    #   the road class.  Measured at HECA: the service corridor -12136
    #   crossing runway 05C/23C put THREE ``runway|runway`` pairs of ring
    #   -12210 at cap 8.0 (101.53 %, 85.19 %, 59.26 %) while the same
    #   ring 22-30 m away priced at the lawful 1.5 — a runway row at a
    #   foreign cap.  The carved feature's OWN ring is unaffected: its
    #   role does not outrank the road roles, so its descent still grades
    #   at the road class between contacts, which is the only thing this
    #   relaxation was built for.
    if (p.both_road and SERVICE_ROAD_MAX_GRADE > cap
            and not p.a_building and not p.b_building
            and not _road_carve_outranked_by_host(p.claim_role or p.role)):
        cap = SERVICE_ROAD_MAX_GRADE

    # ── THE ROAD CROSS-SECTION IS LAW (owner ruling RULINGS 2026-08-25g).
    # LAST, and deliberately so: the cap this prices against is the
    # LONGITUDINAL cap the whole chain above just settled on (the road
    # rate, the frontage 1 %, a seam-pinned body cap), and the transverse
    # cap is a pure function OF THAT cap — never of a role re-read here.
    # ``road_cross_section_cap`` is ``min``-shaped, so this branch can
    # only ever TIGHTEN: a frontage chord across a road keeps its 1 %,
    # and every relaxation above that the law meant to grant survives
    # longitudinally.  Crown declarations exempt exactly as elsewhere —
    # the crown offset re-centres the pair's Δz before either reader
    # compares it to this budget, and nothing here touches that offset.
    #
    # A SPINE PAIR IS NEVER A CROSS-SECTION.  The spine IS the road's
    # own travel path — that is what a centerline is — while the ring's
    # minimum-area axis is only a PROXY for that direction, and
    # ``long_axis_of_points`` says so itself: "a blobby service JUNCTION
    # has no natural axis; the minimum-area rectangle still gives every
    # reader the SAME answer, which is what a shared convention is for."
    # A shared convention is not an authority.  Where the two disagree
    # the CENTERLINE wins, because it is measured route geometry rather
    # than a bounding-box artefact.
    #
    # MEASURED (CYXY, ``test_single_graph_acceptance::test_cyxy_spine_zero``,
    # a zero-tolerance gate that passes on main): without this clause the
    # classifier priced 8 service_junction SPINE edges as cross-sections
    # — the through-route of a junction whose bounding box happens to be
    # wider than it is long — and the solve then could not meet even the
    # road's own LONGITUDINAL cap there (two edges at 14.6 % against
    # cap 8.0).  Capping a road's travel direction at its cross-section
    # rate is not the ruling; it is the proxy failing, and this is where
    # it is caught.
    if p.transverse_road and not p.spine_caps:
        cap = road_cross_section_cap(cap)

    return Allowance.flat(cap)


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


def airside_arc_rate_per_m(ruleset=None):
    """THE AIRSIDE RATE-OF-CHANGE LAW — spec
    ``airside-no-step-law-spec.md`` §1.2, owner ruling RULINGS 2026-08-27
    clause 2 ("grade change per unit length limited, the vertical-curve /
    K-factor analogue the runway and strip_arc laws already implement for
    their families").

    NO NEW NUMBER, and deliberately so: the aerodrome's vertical-curve
    rate is ONE quantity — FAA AC 150/5300-13B §3.16.5 item 5 gives
    ±2 % per 30.5 m and ICAO Annex 14 §3.4.14 is the qualitative "as
    gradual as practicable" whose PROVISIONAL operationalization the
    ruleset already carries (owner question 2).  The strip family reads
    it through :func:`strip_longitudinal_law`; the airside pavement
    family reads it here.  Two readers, one constant — which is the whole
    point of extending the machinery instead of forking it.

    The owner's own refinement is what this bounds: *"A 1.5 m 'dip' could
    be ok assuming it was spread across enough area to be smooth."*  At
    this rate a 1.5 m bowl over 200 m passes and the same bowl over 30 m
    does not.
    """
    return ruleset_strip_arc_rate_per_m(ruleset)


def strip_longitudinal_law(code_number, code_letter=None, ruleset=None):
    """``(max_slope, arc_rate_per_m)`` — the strip's complete
    longitudinal law for one runway class under one ruleset.  ONE
    resolver for the march's trigger, the clamp and the validator."""
    return (ruleset_strip_max_longitudinal_slope(
                code_number, code_letter, ruleset),
            ruleset_strip_arc_rate_per_m(ruleset))


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
    from .strip_seam import paved_unpaved_dropoff_exempt
    return paved_unpaved_dropoff_exempt(
        step_m, shoulder_edge_dropoff_allowance_m(ruleset))


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


def drainage_minimum_shortfall(grade: float, role: str, ruleset=None, **kw):
    """How far below its drainage minimum a measured ``grade`` sits (0.0
    when compliant or when no minimum binds) — the validator twin's one
    reading, so emitter and census cannot disagree about what "too flat"
    means."""
    low = drainage_minimum_grade(role, ruleset, **kw)
    if low is None:
        return 0.0
    return max(0.0, float(low) - abs(float(grade)))

