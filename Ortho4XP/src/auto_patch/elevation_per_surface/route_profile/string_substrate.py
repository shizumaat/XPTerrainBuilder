"""THE STRING SUBSTRATE — apt.dat-first assembly of the string-construction
input (Fable RULING 1, 2026-07-31).

What this module answers
========================
The string constructor (:func:`..taut_string.walk_spine_runs`) walks a
SUBSTRATE.  Spec §2's COMMITTED block rules that substrate to be

    the S2 snapshot (the ``taxi_centerlines`` state at
    ``pipeline.py:2253`` — apt.dat rows 1201/1202, connectivity routes,
    bend-split into pieces) ∪ OSM linear taxiways per D1,
    **apt.dat-first dedup**

and this module is the dedup.  It is deliberately pure and
dependency-free (stdlib + :mod:`math`; no numpy, no shapely, no
``auto_patch`` imports beyond the one owner constant) so it can be
unit-tested headless and called from
:func:`..taut_string.spine_walk_chains` — which explicitly delegates
here rather than duplicating the assembly.

★ THE GRANULARITY IS SUBSEGMENT, NOT WAY — and that is a RULING, not a
tuning choice (Fable, 2026-07-31).  The committed sentence is LOCATIVE:
"OSM stands WHERE apt.dat is absent" names locations, not way ids.  The
per-WAY reading was measured on HECA and turns the clause against
itself: 275 of 282 standing ways were only PARTIALLY inside the
corridor, so a way-granular dedup yielded just 28 of 310 ways and left
**75 % of the emitted metres duplicated** — OSM standing where apt.dat
is PRESENT, the exact opposite of "apt.dat-first".  Subsegment
granularity drops duplication to 4 % and lands the emitted total at
101 % of the owner's own drawn map.  Do not "simplify" this back to a
per-way test.

★ RECOGNITION, NEVER BRIDGING.  Cutting a standing OSM run where
apt.dat covers the ground mints a :class:`SeamJoint` recording WHICH
apt.dat piece covers the cut — that is recognition of an adjacency.  It
never extends geometry across the cut and never blends a value across
it.  The identity ≠ membership ≠ bridging distinction (★-noted in
``config.py``) binds here exactly as it binds in the constructor:
membership may recognise a near-miss, identity is the canonical
registry's business alone, and bridging stays FORBIDDEN.

★ ONE CONSTANT, NO NEW NUMBERS.  ``tol_m`` is the owner's
``TAUT_STRING_SPINE_TOLERANCE_M`` (8.0 m, his ruling of 2026-07-31
superseding 5.0) and it does three jobs here: the corridor half-width,
the anti-chatter absorption threshold, and the seam-joint radius.  The
anti-chatter rule is *derived* from his constant precisely so that it
introduces no fitted number of its own — a standing run shorter than
the corridor it escaped is corridor chatter, not a real absence of
apt.dat.  Do not add a second threshold here.

``station_m`` is REQUIRED-EXPLICIT and carries no default, following
``walk_spine_runs``' ``bound_m`` precedent: it is a sampling resolution,
not a law constant, and a silent default is exactly the shipped-constant
trap register 21 has now been paid for five times.  It must satisfy
``0 < station_m <= tol_m``.

Build-time statement (HARD LAW item 6)
======================================
The apt.dat geometry is indexed into a uniform grid keyed on ``tol_m``,
so membership is O(stations) with a small constant rather than
O(stations × segments).  Measured on HECA (196 apt pieces / 46,145 m
against 310 OSM ways / 65,453 m, ``station_m`` = 5.0): **~0.10 s**, i.e.
~0.17 % of the 60 s per-airport budget — under the 1 % review line.  The
un-indexed form was ~3 s (5 %) and would have needed the Fable-5 review.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, NamedTuple, Sequence, Tuple

__all__ = [
    "Point", "Polyline", "SeamJoint", "StandingRun", "StringSubstrate",
    "resample_polyline", "polyline_length", "build_string_substrate",
    "ClipResult", "clip_strings_to_runways",
]

Point = Tuple[float, float]
Polyline = Sequence[Point]


# ══════════════════════════════════════════════════════════════════════
# Result shapes
# ══════════════════════════════════════════════════════════════════════

class SeamJoint(NamedTuple):
    """A cut end of a standing OSM run, and the apt.dat piece covering it.

    RECOGNITION ONLY.  ``covering_piece`` says "apt.dat owns the ground
    immediately past this end"; it licenses no geometric extension and no
    value transport across the joint.  ``distance_m`` is the separation
    from the cut point to that piece and is always ``<= tol_m`` by
    construction (the joint exists because a station there was covered).
    """

    run_index: int          # index into StringSubstrate.standing
    at_end: str             # "head" | "tail"
    point: Point
    covering_piece: int     # index into the apt_pieces the caller passed
    distance_m: float


class StandingRun(NamedTuple):
    """A maximal stretch of an OSM way where apt.dat is ABSENT."""

    source: str             # the caller's key for the parent OSM way
    ordinal: int            # 0-based index of this run within that way
    coords: Tuple[Point, ...]
    length_m: float


class StringSubstrate(NamedTuple):
    """The walk's input: apt.dat pieces unchanged, plus what OSM adds.

    ``polylines()`` is the assembled substrate in apt.dat-first order —
    every apt.dat piece exactly as given, then the standing OSM runs.
    """

    apt_pieces: Tuple[Tuple[Point, ...], ...]
    standing: Tuple[StandingRun, ...]
    seams: Tuple[SeamJoint, ...]
    stats: Dict[str, float]

    def polylines(self) -> List[Tuple[str, Tuple[Point, ...]]]:
        """``(key, coords)`` pairs, apt.dat first.  Deterministic order."""
        out: List[Tuple[str, Tuple[Point, ...]]] = [
            (f"apt:{i}", p) for i, p in enumerate(self.apt_pieces)]
        out.extend((f"osm:{r.source}#{r.ordinal}", r.coords)
                   for r in self.standing)
        return out


# ══════════════════════════════════════════════════════════════════════
# Geometry helpers (pure stdlib)
# ══════════════════════════════════════════════════════════════════════

def polyline_length(coords: Polyline) -> float:
    """Arc length of a polyline in metre space."""
    return math.fsum(math.dist(coords[i], coords[i + 1])
                     for i in range(len(coords) - 1))


def resample_polyline(coords: Polyline, station_m: float) -> List[Point]:
    """Stations at a UNIFORM ``station_m`` interval along arc length.

    The final station is the polyline's own end point, so a run's extent
    is never silently truncated by the sampling grid.  A degenerate
    (zero-length) polyline yields its single point.
    """
    if station_m <= 0.0:
        raise ValueError("station_m must be > 0")
    pts = [tuple(map(float, p)) for p in coords]
    if len(pts) < 2:
        return list(pts)
    cum = [0.0]
    for i in range(len(pts) - 1):
        cum.append(cum[-1] + math.dist(pts[i], pts[i + 1]))
    total = cum[-1]
    if total <= 0.0:
        return [pts[0]]
    out: List[Point] = []
    n = int(total // station_m)
    seg = 0
    for k in range(n + 1):
        s = k * station_m
        while seg < len(cum) - 2 and cum[seg + 1] < s:
            seg += 1
        span = cum[seg + 1] - cum[seg]
        t = 0.0 if span <= 0.0 else (s - cum[seg]) / span
        ax, ay = pts[seg]
        bx, by = pts[seg + 1]
        out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    if math.dist(out[-1], pts[-1]) > 1e-9:
        out.append(pts[-1])
    return out


def _point_segment_distance(p: Point, a: Point, b: Point) -> float:
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy
    if den <= 1e-18:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / den
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


class _SegmentGrid:
    """Uniform-grid index over the apt.dat segments.

    Cell size is ``tol_m`` and each segment is rasterised at ``tol_m / 2``
    steps, so a query point within ``tol_m`` of a segment always finds a
    registered sample within 2 cells: the nearest point ``c`` on the
    segment is ``<= tol_m`` from the query, some sample lies ``<=
    tol_m/4`` from ``c`` (half a step), hence a sample lies within
    ``1.25 * tol_m`` — inside a 5x5 cell window.  These are INDEX
    parameters derived from ``tol_m``, provably conservative, and carry
    no law meaning; the membership answer is exact segment distance.
    """

    __slots__ = ("cell", "radius", "_bins", "_segs")

    def __init__(self, pieces: Sequence[Polyline], tol_m: float) -> None:
        self.cell = tol_m
        self.radius = 2
        self._bins: Dict[Tuple[int, int], List[int]] = {}
        self._segs: List[Tuple[Point, Point, int]] = []
        step = tol_m / 2.0
        for pi, coords in enumerate(pieces):
            for k in range(len(coords) - 1):
                a = (float(coords[k][0]), float(coords[k][1]))
                b = (float(coords[k + 1][0]), float(coords[k + 1][1]))
                si = len(self._segs)
                self._segs.append((a, b, pi))
                seg_len = math.dist(a, b)
                n = max(1, int(seg_len // step))
                for j in range(n + 1):
                    t = min(1.0, (j * step) / seg_len) if seg_len > 0 else 0.0
                    key = self._key((a[0] + (b[0] - a[0]) * t,
                                     a[1] + (b[1] - a[1]) * t))
                    bucket = self._bins.setdefault(key, [])
                    if not bucket or bucket[-1] != si:
                        bucket.append(si)

    def _key(self, p: Point) -> Tuple[int, int]:
        return (int(math.floor(p[0] / self.cell)),
                int(math.floor(p[1] / self.cell)))

    def nearest(self, p: Point) -> Tuple[float, int]:
        """``(distance, piece_index)`` to the nearest indexed segment.

        Exact whenever the true distance is ``<= tol_m`` (the guarantee
        the window size is chosen for).  Beyond that it may return a
        larger distance or ``(inf, -1)`` — which is all a membership test
        at ``tol_m`` needs.
        """
        cx, cy = self._key(p)
        best, best_pi = math.inf, -1
        r = self.radius
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for si in self._bins.get((cx + dx, cy + dy), ()):
                    a, b, pi = self._segs[si]
                    d = _point_segment_distance(p, a, b)
                    if d < best:
                        best, best_pi = d, pi
        return best, best_pi


# ══════════════════════════════════════════════════════════════════════
# The dedup
# ══════════════════════════════════════════════════════════════════════

def build_string_substrate(
        apt_pieces: Iterable[Polyline],
        osm_lines: Iterable[Tuple[str, Polyline]],
        *,
        tol_m: float,
        station_m: float,
) -> StringSubstrate:
    """Assemble the string substrate: apt.dat pieces ∪ what OSM ADDS.

    Ruled mechanics, in this exact order (Fable, 2026-07-31):

    1. **per-station membership** at ``tol_m`` — each station of an OSM
       way is COVERED iff some apt.dat segment lies within ``tol_m``;
    2. **maximal runs** — consecutive UNCOVERED stations group into
       maximal runs, which stand;
    3. **sub-``tol_m`` runs absorbed** — a standing run shorter than
       ``tol_m`` is corridor chatter, not an absence of apt.dat; it is
       absorbed (dropped).  Derived from the owner's constant; no new
       number;
    4. **every cut mints a seam joint** to the covering apt.dat piece —
       recognition, never bridging.  A run boundary that is the OSM way's
       OWN endpoint is not a cut and mints nothing.

    A covered station is never bridged over: a covered stretch always
    cuts, however short, because bridging across ground apt.dat owns is
    exactly the forbidden operation.  Absorption only ever DELETES a
    standing run; it never joins two.

    :param apt_pieces: metre-space polylines, apt.dat-first and returned
        unchanged.  Order is preserved and is the ``covering_piece``
        index space.
    :param osm_lines: ``(key, polyline)`` pairs in metre space.
    :param tol_m: the owner's ``TAUT_STRING_SPINE_TOLERANCE_M``.
    :param station_m: sampling resolution; required-explicit, and must
        satisfy ``0 < station_m <= tol_m``.
    :raises ValueError: on a non-positive ``tol_m`` or an out-of-range
        ``station_m`` (a resolution coarser than the corridor cannot
        resolve the corridor).
    """
    if tol_m <= 0.0:
        raise ValueError("tol_m must be > 0")
    if not (0.0 < station_m <= tol_m):
        raise ValueError(
            f"station_m must satisfy 0 < station_m <= tol_m "
            f"(got station_m={station_m!r}, tol_m={tol_m!r}): a sampling "
            f"resolution coarser than the corridor cannot resolve it")

    pieces: Tuple[Tuple[Point, ...], ...] = tuple(
        tuple((float(x), float(y)) for x, y in c) for c in apt_pieces)
    usable = [c for c in pieces if len(c) >= 2]
    grid = _SegmentGrid(usable, tol_m) if usable else None

    standing: List[StandingRun] = []
    seams: List[SeamJoint] = []
    n_ways = 0
    osm_m = 0.0
    absorbed_n = 0
    absorbed_m = 0.0
    covered_m = 0.0
    stations_total = 0
    stations_covered = 0

    for key, coords in osm_lines:
        pts = [(float(x), float(y)) for x, y in coords]
        if len(pts) < 2:
            continue
        n_ways += 1
        osm_m += polyline_length(pts)
        stations = resample_polyline(pts, station_m)
        if grid is None:
            cov = [False] * len(stations)
            near: List[Tuple[float, int]] = [(math.inf, -1)] * len(stations)
        else:
            near = [grid.nearest(s) for s in stations]
            cov = [d <= tol_m for d, _pi in near]
        stations_total += len(stations)
        stations_covered += sum(1 for c in cov if c)

        # (2) maximal runs of UNCOVERED stations
        runs: List[Tuple[int, int]] = []
        start = None
        for i, c in enumerate(cov):
            if not c and start is None:
                start = i
            elif c and start is not None:
                runs.append((start, i - 1))
                start = None
        if start is not None:
            runs.append((start, len(cov) - 1))

        ordinal = 0
        for lo, hi in runs:
            run_pts = tuple(stations[lo:hi + 1])
            if len(run_pts) < 2:
                absorbed_n += 1
                continue
            length = polyline_length(run_pts)
            # (3) anti-chatter absorption — derived from tol_m
            if length < tol_m:
                absorbed_n += 1
                absorbed_m += length
                continue
            run_index = len(standing)
            standing.append(StandingRun(str(key), ordinal, run_pts, length))
            ordinal += 1
            # (4) seam joints at CUTS only (never at the way's own ends)
            if lo > 0:
                d, pi = near[lo - 1]
                seams.append(SeamJoint(run_index, "head", run_pts[0],
                                       pi, float(d)))
            if hi < len(cov) - 1:
                d, pi = near[hi + 1]
                seams.append(SeamJoint(run_index, "tail", run_pts[-1],
                                       pi, float(d)))

    apt_m = math.fsum(polyline_length(c) for c in usable)
    stand_m = math.fsum(r.length_m for r in standing)
    covered_m = osm_m - stand_m - absorbed_m
    stats: Dict[str, float] = {
        "apt_pieces": float(len(usable)),
        "apt_m": apt_m,
        "osm_ways": float(n_ways),
        "osm_m": osm_m,
        "standing_runs": float(len(standing)),
        "standing_m": stand_m,
        "yielded_m": covered_m,
        "absorbed_runs": float(absorbed_n),
        "absorbed_m": absorbed_m,
        "seams": float(len(seams)),
        "stations": float(stations_total),
        "stations_covered": float(stations_covered),
        "substrate_m": apt_m + stand_m,
        "tol_m": float(tol_m),
        "station_m": float(station_m),
    }
    return StringSubstrate(pieces, tuple(standing), tuple(seams), stats)


# ══════════════════════════════════════════════════════════════════════
# THE RUNWAY CLIP — owner ruling, 2026-07-31
# ══════════════════════════════════════════════════════════════════════

class ClipResult(NamedTuple):
    """Emitted strings after the owner's runway clip, plus its census.

    ``in_duty_band`` are surviving remainders in
    ``[min_remainder_m, TAUT_STRING_MIN_STRING_M)``.

    ★ 50-vs-100 RESOLVED BY SCOPE (Fable, 2026-07-31) — and a remainder
    in that band **SURVIVES**.  The two owner constants never actually
    compete because they govern different moments:
      * ``TAUT_STRING_MIN_STRING_M`` (100) is CONSTRUCTION-EXISTENCE law
        — it decides what the WALK may emit, and it is applied pre-clip;
      * ``min_remainder_m`` (50) is EMISSION-REMAINDER law — it decides
        what survives the clip, and it is applied post-clip.
    Reading 100 over a remainder would make the owner's "less than 50m"
    clause a dead letter, since every sub-100 remainder would already be
    gone.  So this band is **TELEMETRY, labelled remainder-class**, not a
    gate: it travels to him, and if he dislikes the population his own
    rule kept, his constant moves.  Never filter on it here.
    """

    strings: Tuple[tuple, ...]
    dropped: Tuple[Tuple[tuple, float], ...]      # (source string, rem length)
    in_duty_band: Tuple[Tuple[tuple, float], ...]
    stats: Dict[str, float]


def clip_strings_to_runways(strings, pos, runway_polys, *, min_remainder_m):
    """Clip EMITTED strings by the runway outline (owner, 2026-07-31).

        "Use the runway outline to clip any strings, discarding anything
         inside the runway, and if the remainder is less than 50m just
         drop it, the taxiway's grade will be smooth enough without it"

    ★ THE STRINGS ARE CLIPPED, NOT THE SUBSTRATE — his words, and the
    model agrees with his words.  A string is an IDEALIZED ELEVATION
    TARGET, so growing it across the runway and then discarding the
    interior leaves both remainders ON THE SAME SINGLE STRAIGHT LINE.
    Clipping the substrate instead would split the route into two chains
    that solve INDEPENDENTLY and can diverge — two target lines where he
    intends one.  That is an elevation consequence, not bookkeeping.
    Measured on HECA: substrate-clip and string-clip agree on the gates
    but differ in exactly this property.  Do not "simplify" this into the
    substrate stage.

    ★ THE OUTLINE IS REQUIRED-EXPLICIT AND NEVER DERIVED HERE.  "The
    runway outline" has more than one candidate in this tree and they
    price differently (HECA: 88 strings / 86.6 % vs 85 / 86.2 %), so a
    pure module must not pick one silently — the caller passes the
    pipeline's own object.  See ``bound_m``'s precedent.

    ★ WHICH OUTLINE — OWNER RULING (2026-07-31): the SHOULDER-WIDENED
    union, i.e. ``layout.runway_union`` (75.6/75.6/75.9 m at HECA), not
    the raw apt.dat row-100 rect (60.0 m).  His reason is the load-
    bearing one: **shoulders are PAVED and the runway profile grades
    them, so the widened union is where runway elevation AUTHORITY
    actually ends** — which is exactly what the clip protects.
    Provenance agrees independently: the shoulder widening runs in
    phase 2, BEFORE the ``:2252`` substrate snapshot, so the union the
    carriage captures already IS the widened one (verified offline
    against the recorded build log, 75.6/75.6/75.9).
    CONSIDERED AND SUPERSEDED: ``pipeline.py:955-958`` warns that "rules
    keyed on 'the runway width' must not be handed runway+shoulders"
    (ICAO Annex 14 §3.5.3) and preserves ``published_width_m`` for that.
    The distinction that resolves it: **that warning governs a width
    used as a MULTIPLIER (the RESA factor of two); this is an outline
    used as a REGION.**  A region asks "where does runway authority
    end", a multiplier asks "how wide is the runway" — different
    questions, different objects.  ``ROLE_RUNWAY_CLEARANCE`` is a
    clearance surface, not an outline; not a candidate.

    ★ BIND POINT RATIFIED (Fable): clipping the EMITTED strings is
    required by committed design, not merely by his wording — §2 step 1
    seats runway-crossing values as clause-1 anchors ON THE CHAIN, so the
    chain must span the crossing.  Substrate clipping would sever every
    crossing into two independently-solving strings exactly where
    continuity is hardest law.

    :param strings: ``(a, b, nodes, length, chain_id)`` tuples as emitted
        by the constructor.  A string not meeting any runway is returned
        UNCHANGED (identical tuple), so airports without runway contact
        are byte-identical.
    :param pos: node -> ``(x, y)``, for re-attributing nodes to remainders.
    :param runway_polys: shapely polygon(s) — one, an iterable, or a
        pre-unioned geometry.  Required.
    :param min_remainder_m: the owner's
        ``TAUT_STRING_RUNWAY_CLIP_MIN_REMAINDER_M``.  Required-explicit.
    """
    from shapely.geometry import LineString
    from shapely.ops import unary_union

    if min_remainder_m is None or min_remainder_m <= 0.0:
        raise ValueError("min_remainder_m is required and must be > 0")
    if runway_polys is None:
        raise ValueError(
            "runway_polys is required — this module never derives the "
            "runway outline (rect vs shoulder-widened differ materially)")
    geoms = (list(runway_polys) if isinstance(runway_polys, (list, tuple))
             else [runway_polys])
    geoms = [g for g in geoms if g is not None and not g.is_empty]
    if not geoms:
        return ClipResult(tuple(strings), (), (), {
            "clipped": 0.0, "dropped": 0.0, "dropped_m": 0.0,
            "in_duty_band": 0.0, "split_in_two": 0.0,
            "min_remainder_m": float(min_remainder_m)})
    union = unary_union(geoms)

    from auto_patch.config import TAUT_STRING_MIN_STRING_M as _DUTY

    out: List[tuple] = []
    dropped: List[Tuple[tuple, float]] = []
    band: List[Tuple[tuple, float]] = []
    n_clipped = n_split = 0
    dropped_m = 0.0

    for s in strings:
        a0, b0, nodes, ln, cid = s
        chord = LineString([a0, b0])
        if not chord.intersects(union):
            out.append(s)                       # untouched, identical tuple
            continue
        n_clipped += 1
        rest = chord.difference(union)
        parts = ([rest] if rest.geom_type == "LineString"
                 else [g for g in getattr(rest, "geoms", ())])
        parts = [p for p in parts if p.length > 1e-9]
        ux = (b0[0] - a0[0]) / ln if ln > 1e-9 else 0.0
        uy = (b0[1] - a0[1]) / ln if ln > 1e-9 else 0.0
        kept = 0
        for p in parts:
            if p.length < min_remainder_m:
                dropped.append((s, float(p.length)))
                dropped_m += float(p.length)
                continue
            pa = (float(p.coords[0][0]), float(p.coords[0][1]))
            pb = (float(p.coords[-1][0]), float(p.coords[-1][1]))
            lo = (pa[0] - a0[0]) * ux + (pa[1] - a0[1]) * uy
            hi = (pb[0] - a0[0]) * ux + (pb[1] - a0[1]) * uy
            if lo > hi:
                lo, hi = hi, lo
            sub = [v for v in nodes
                   if lo - 1e-6 <= ((pos[v][0] - a0[0]) * ux
                                    + (pos[v][1] - a0[1]) * uy) <= hi + 1e-6]
            L = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
            out.append((pa, pb, sub, L, cid))
            kept += 1
            if L < float(_DUTY):
                band.append((s, L))
        if kept >= 2:
            n_split += 1

    stats: Dict[str, float] = {
        "clipped": float(n_clipped),
        "dropped": float(len(dropped)),
        "dropped_m": dropped_m,
        "in_duty_band": float(len(band)),
        "split_in_two": float(n_split),
        "min_remainder_m": float(min_remainder_m),
        "strings_in": float(len(strings)),
        "strings_out": float(len(out)),
    }
    return ClipResult(tuple(out), tuple(dropped), tuple(band), stats)
