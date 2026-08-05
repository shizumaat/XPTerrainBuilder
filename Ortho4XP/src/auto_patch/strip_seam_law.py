"""strip_seam_law — THE one home for the GRADED-STRIP seam law.

Spec: ``docs/specs/seam-continuity-v2-spec.md`` §1 ("one vocabulary, one
home").  Two unrelated notions of "seam" coexisted in this codebase and
the v1 seam-continuity round died of the conflation
(``docs/specs/seam-continuity-constraint-spec.md`` round verdict):

* **STRIP seam** — the fabric tear between two DIFFERENT ``graded_strip``
  shapes (adjacent-ground bands, gap-fill spines) that meet along a weld
  seam and disagree in elevation.  Nothing to do with tiles: the measured
  population sits 11-14 km from any graticule line.  **THIS MODULE.**
* **TILE seam** — the graticule (integer lat/lon) tile-cut corridor, where
  a patch must match the neighbouring tile's terrain.  Its constants live
  in ``tools/check_grade.py`` and ``auto_patch/grade_graph_validate.py``
  and are named ``TILE_SEAM_*`` since the v2 round.

**Naming rule for this lane (binding): a bare "seam" identifier is banned
in new code — every new name says STRIP_SEAM or TILE_SEAM.**

The values and predicates below are the CENSUS instrument's own — moved
here verbatim from ``tools/check_grade.py`` so that the validator
(``_check_strip_seam_tears``) and any generation-binding law read ONE
definition (docs/RULINGS.md, grade-law completeness standard: emitter and
validator must be lockstep, never two copies).

THIRD COPY ABSORBED (seam-continuity v3 §1, 2026-08-04).  The EMITTER
half of this law — ``adjacent_ground.blend_cross_strip_seam_steps``, run
unconditionally from ``pipeline._strip_reconcile_passes`` — used to
declare its own 6.0 m radius and 1.0 m step floor locally, under
bare-"seam" names.  It now imports ``STRIP_SEAM_TEAR_RADIUS_M`` and
``STRIP_SEAM_TEAR_MIN_STEP_M`` from here.  The absorption was byte-inert
(the values were already identical) and it makes structural what was
previously only a coincidence: **the healer sees EXACTLY the pair
population this law's census reports**.

What that population turns out to be was MEASURED in the same round
(CYXY + HECA at the tip anchors, in-healer instrumentation) and it is NOT
what v2 inferred.  The "a cluster whose every node is anchored is left
alone" rule fires on NOTHING at either airport (0 declined clusters
against 34 census rows).  The rows that survive are the healer's
NON-WORSENING GUARD residuals: a free node it cannot move without minting
a fresh step against a neighbour it deliberately excluded (5 of HECA's 7
sites and CYXY's only site join a guard row exactly; the other 2 HECA
sites are not a healer pair at all, i.e. minted after this pass).  Since
v3 §2 all three left-alone outcomes are LOUD — one ``[strip-seam]``
forensics row each, unconditionally.  The decline itself is correct
non-authority behaviour; the SILENCE was the defect.

FOURTH COPY ABSORBED (seam-continuity v4 §1, 2026-08-04).  The design
decision v3 §1 flagged and deferred is now RULED: the healer's own
locally-declared cliff-grade floor (0.5, in ``adjacent_ground``) IS
``STRIP_SEAM_TEAR_MIN_GRADE`` and is imported from here.  With it, the
healer's non-worsening guard stops quoting a bare 1.0 m allowance
against excluded neighbours and quotes the CENSUS PAIR PREDICATE
instead (``seam_guard_allowance_m`` below) — the bounds-attribution
verdict's mechanism 1: both inverted bounds came from ONE constant
quoted against two different neighbours, over-strict by up to 3x at the
measured 2.2-6.0 m distances, and the inversion-creating neighbours are
drapes this law's own grade conjunct already declares lawful.

``seam_pair_is_tear`` is the ONE arithmetic both halves now run:
``check_grade._check_strip_seam_tears`` calls it for its verdict, and
``seam_guard_allowance_m`` is its exact inverse — the largest |Δalt| at
a given planar distance that CANNOT be a tear, less a fixed margin.
Test twin: ``tests/test_strip_seam_law_module.py`` sweeps the pair space
and asserts the two never disagree.

Deliberately dependency-free (stdlib only): ``tools/check_grade.py`` runs
standalone, and a law module that can fail to import is not a law.

NOTE (blast role-literal hazard): ``STRIP_SEAM_ROLE`` and
``STRIP_SEAM_GRADED_ROLES`` are role VALUE literals.  They are kept as
literals (not imports of ``auto_patch.layout.ROLE_*``) so this module
stays import-free for the standalone validator; renaming a ``ROLE_*``
value in ``auto_patch/layout.py`` silently empties the set.  The census
row key ``seam::seam`` is NOT renamed (baseline continuity — every
historical matrix quotes it); it means STRIP seam.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

__all__ = [
    "STRIP_SEAM_TEAR_RADIUS_M",
    "STRIP_SEAM_TEAR_MIN_STEP_M",
    "STRIP_SEAM_TEAR_MIN_GRADE",
    "STRIP_SEAM_TEAR_MIN_DISTANCE_M",
    "STRIP_SEAM_WALL_STRADDLE_TOL_M",
    "STRIP_SEAM_ROLE",
    "STRIP_SEAM_OPEN_GROUND_MIN_M",
    "STRIP_SEAM_OPEN_GROUND_SAMPLES",
    "STRIP_SEAM_GRADED_ROLES",
    "STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M",
    "STRIP_SEAM_GUARD_MARGIN_M",
    "seam_pair_is_tear",
    "seam_guard_allowance_m",
    "point_in_ring",
    "GradedDomain",
    "point_segment_distance",
    "segment_segment_closest",
    "open_ground_between",
    "WallFaces",
]


# ── Cross-shape graded-strip SEAM tear thresholds ───────────────
# A ``graded_strip`` drapes raw terrain and legitimately has NO
# within-shape grade cap (``check_grade._check_adjacent_ground_edges``
# only proves the SUB-METRE within-shape tear).  The one DEM-free-provable
# defect that class misses is a large vertical STEP between the nodes of
# two DIFFERENT strips: a clip / weld seam the in-sim renderer draws as a
# sharp cliff.  Thresholds chosen from the SPJC inventory, where real
# seam tears are Δalt 1.8-4.4 m at 1-6 m node spacing — safely above the
# ~0.3 m steps lawful terracing between adjacent strips produces.
STRIP_SEAM_TEAR_RADIUS_M = 6.0         # only NEAR-adjacent strip nodes pair
STRIP_SEAM_TEAR_MIN_STEP_M = 1.0       # Δalt at/under this = lawful terrace / noise
# Grade floor: steep-relief airports (CYXY) hold LAWFUL >1 m deltas between
# strips 4-6 m apart (hillside drape, ~30-40 % max); genuine seam cliffs and
# stacked same-coordinate walls run 100-350 %.  Only steps implying >50 %
# are tears.  Exactly-interned shared nodes carry ONE value (Δ = 0), so no
# planar-distance floor is needed — a same-coordinate pair with Δalt > the
# step floor is a stacked bare wall and MUST be flagged.
STRIP_SEAM_TEAR_MIN_GRADE = 0.5
STRIP_SEAM_TEAR_MIN_DISTANCE_M = 0.01  # grade denominator clamp (stacked walls)
# Planar slack for "the wall face passes BETWEEN the two nodes": the wall
# row and the strip chain it welds are separate emissions, so a crossing
# is not exact to the millimetre.
STRIP_SEAM_WALL_STRADDLE_TOL_M = 0.5
STRIP_SEAM_ROLE = "graded_strip"

# ── OPEN-GROUND clause for the straddle exemption (2026-08-01) ──
# The owner's law exempts terraces at the graded→DEM boundary in OPEN
# ground: only zones 1-2 of the adjacent-ground corridor are graded, and
# where grading ENDS the surface may lawfully step down to raw terrain
# behind an emitted wall face.  A pair whose connecting segment never
# leaves the graded domain is NOT at that boundary — it is an interior
# tear of the graded corridor (zones 1-2) or of a filled pocket, both of
# which stay defects however many wall faces cross them.  Round-5
# measurement (438 tear rows, four airports, both arms): 9 of the
# exemption's 21 firings dissolved zone-1/2 tears, worst Δalt 10.33 m.
#
# The ungraded-gap distribution over that population is BIMODAL — 6e-15…
# 3e-7 m (polygon-boundary floating point: no ungraded ground at all) vs
# ≥ 0.02 m — with nothing in between, so any threshold in [1 µm, 1 cm]
# gives the same split; 1 cm is the conservative end.
STRIP_SEAM_OPEN_GROUND_MIN_M = 0.01
# Interior samples along the pair's connecting segment (the two endpoints
# are strip vertices and therefore lie ON the graded domain's boundary —
# sampling them would read every pair as open).
STRIP_SEAM_OPEN_GROUND_SAMPLES = 21    # ⇒ 19 interior samples
# The GRADED DOMAIN: graded_strip ∪ the pavement polygons.  This is the
# round-5 instrument's set verbatim (scratchpad round5/geom.py), kept
# identical so the v1-vs-v2 quantification is one instrument.  The three
# further areal roles the battery patches carry — ``runway_crossing``,
# ``ols_cut``, ``runway_clearance`` — are NOT in it; adding all three
# changes the graded/open verdict on 0 of the 438 measured tear rows
# (round-6 pre-flight), so the choice is not load-bearing on this
# population.
STRIP_SEAM_GRADED_ROLES = frozenset({
    "graded_strip",
    "runway", "primary_parallel", "secondary_parallel", "stub",
    "junction", "cross_connector", "apron", "terminal", "building",
    "service_road", "service_junction", "groundside_pavement",
    "tunnel_ramp", "bridge_trench", "bridge_causeway", "hangar_pad",
})

# ── PROVISIONAL open-boundary floor (owner 2026-08-01) ──────────
# OWNER RULING, PROVISIONAL, PENDING IN-SIM REVIEW: "I want to see it
# with no wall, raise it to 15 m until I can view some test cases in the
# sim".  A tear pair at the OPEN BOUNDARY — ungraded ground lies in the
# pair's interior, i.e. the same clause the straddle exemption uses — is
# the graded→DEM terrace, and the owner is deciding in the simulator how
# large an unwalled terrace is acceptable there.  Until that review, such
# pairs are flagged only past this floor instead of past
# ``STRIP_SEAM_TEAR_MIN_STEP_M`` (1.0 m, the pre-ruling value and still
# the floor for every OTHER pair).
#
# SCOPE, exactly: this floor applies ONLY where the open-ground test
# fires.  Tears INTERIOR to the graded domain — corridor zones 1-2 and
# filled pockets — keep the 1.0 m floor; they are real defects and the
# owner's ruling does not touch them.  Every other rule is unchanged, in
# particular the wall-straddle exemption still runs (it is what will
# dissolve zone-boundary rows once the owner lowers this floor again).
#
# Measured at the ruling (round-6 population, 438 tear rows, 4 airports,
# both arms): the open-boundary class tops out at Δalt 10.48 m, so 15.0
# clears all of it — the number is the owner's, not a fitted threshold.
STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M = 15.0

# ── THE PAIR PREDICATE, and the emitter's allowance derived from it ──
# (seam-continuity v4 §1; bounds-attribution verdict mechanism 1.)
#
# ``seam_pair_is_tear`` is the census verdict for ONE pair, extracted
# verbatim from ``check_grade._check_strip_seam_tears`` so the emitter
# and the validator cannot drift: over the step floor AND over the grade
# floor.  ``seam_guard_allowance_m`` is its inverse, the number the
# healer's NON-WORSENING GUARD needs: the largest |Δalt| that provably
# CANNOT be a tear at a given planar distance.  Since the predicate is
#
#     tear  <=>  de > min_step  AND  de >= min_grade * max(d, min_dist)
#
# a pair is safe as soon as EITHER conjunct fails, i.e. whenever
#
#     de <= max(min_step, min_grade * max(d, min_dist)) - margin
#
# with a strictly positive margin to keep the inequality strict under
# the emitter's 0.01 m value rounding.  The margin is the guard's own
# historical 0.05 m, kept so the change is the GRADE conjunct alone.
STRIP_SEAM_GUARD_MARGIN_M = 0.05


def seam_pair_is_tear(de_m: float, planar_m: float,
                      min_step_m: float = STRIP_SEAM_TEAR_MIN_STEP_M,
                      min_grade: float = STRIP_SEAM_TEAR_MIN_GRADE,
                      min_distance_m: float = STRIP_SEAM_TEAR_MIN_DISTANCE_M
                      ) -> bool:
    """Is a strip-seam pair with |Δalt| ``de_m`` at planar distance
    ``planar_m`` a TEAR?  The census's own two conjuncts, nothing else
    (the wall / open-ground exemptions are the instrument's, applied
    around this call)."""
    if de_m <= min_step_m:
        return False
    return (de_m / max(planar_m, min_distance_m)) >= min_grade


def seam_guard_allowance_m(planar_m: float,
                           min_step_m: float = STRIP_SEAM_TEAR_MIN_STEP_M,
                           min_grade: float = STRIP_SEAM_TEAR_MIN_GRADE,
                           min_distance_m: float
                           = STRIP_SEAM_TEAR_MIN_DISTANCE_M,
                           margin_m: float = STRIP_SEAM_GUARD_MARGIN_M
                           ) -> float:
    """The largest |Δalt| at ``planar_m`` that ``seam_pair_is_tear``
    provably rejects, less ``margin_m``.  The healer's non-worsening
    guard quotes THIS against every excluded neighbour."""
    return max(min_step_m,
               min_grade * max(planar_m, min_distance_m)) - margin_m


def point_in_ring(px: float, py: float,
                  pts: Sequence[Tuple[float, float]]) -> bool:
    """Even-odd crossing test: is (px, py) inside the closed ring
    ``pts`` (given WITHOUT the closing repeat)?  Degenerate (zero-area)
    rings never contain a point, which is the honest answer for them."""
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > py) != (yj > py):
            x_cross = xi + (py - yi) * (xj - xi) / (yj - yi)
            if px < x_cross:
                inside = not inside
        j = i
    return inside


def point_segment_distance(px: float, py: float, ax: float, ay: float,
                           bx: float, by: float) -> Tuple[float, float]:
    """Distance from P to segment A–B, and the clamped parameter of
    the achieving point along A–B."""
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 <= 0.0 else max(0.0, min(
        1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return (math.hypot(px - (ax + t * vx), py - (ay + t * vy)), t)


def segment_segment_closest(px: float, py: float, qx: float, qy: float,
                            ax: float, ay: float, bx: float, by: float
                            ) -> Tuple[float, float]:
    """Closest approach between segments P–Q and A–B: the distance
    and the parameter along P–Q of the achieving point.  Disjoint
    segments always achieve it at an endpoint of one of the two, so
    the crossing test plus the four point-segment cases is exact."""
    ux, uy = qx - px, qy - py
    vx, vy = bx - ax, by - ay
    den = vx * uy - ux * vy
    if abs(den) > 1e-12:
        rx, ry = ax - px, ay - py
        s = (vx * ry - rx * vy) / den
        t = (ux * ry - rx * uy) / den
        if 0.0 <= s <= 1.0 and 0.0 <= t <= 1.0:
            return (0.0, s)
    best = point_segment_distance(px, py, ax, ay, bx, by)[0], 0.0
    cand = point_segment_distance(qx, qy, ax, ay, bx, by)[0], 1.0
    if cand[0] < best[0]:
        best = cand
    for wx, wy in ((ax, ay), (bx, by)):
        d_w, t_w = point_segment_distance(wx, wy, px, py, qx, qy)
        if d_w < best[0]:
            best = (d_w, t_w)
    return best


class GradedDomain:
    """Point membership in the union of the graded rings, with a planar
    slack: a point counts as GRADED when it is inside any ring OR within
    ``tol`` of any ring's boundary (rings meet along shared edges, and a
    sample landing on such an edge is graded ground, not a gap).

    Indexed by a uniform grid over each ring's inflated bounding box, so
    a query is O(local rings), never O(all rings)."""

    CELL_M = 32.0

    def __init__(self, rings: List[List[Tuple[float, float]]],
                 tol: float) -> None:
        self._rings = rings
        self._tol = tol
        self._bbox: List[Tuple[float, float, float, float]] = []
        self._grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        c = self.CELL_M
        for ri, pts in enumerate(rings):
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            bb = (min(xs) - tol, min(ys) - tol,
                  max(xs) + tol, max(ys) + tol)
            self._bbox.append(bb)
            for cx in range(int(math.floor(bb[0] / c)),
                            int(math.floor(bb[2] / c)) + 1):
                for cy in range(int(math.floor(bb[1] / c)),
                                int(math.floor(bb[3] / c)) + 1):
                    self._grid[(cx, cy)].append(ri)

    def covers(self, px: float, py: float) -> bool:
        if not self._rings:
            return False
        c = self.CELL_M
        tol = self._tol
        for ri in self._grid.get((int(math.floor(px / c)),
                                  int(math.floor(py / c))), ()):
            x0, y0, x1, y1 = self._bbox[ri]
            if px < x0 or px > x1 or py < y0 or py > y1:
                continue
            pts = self._rings[ri]
            if point_in_ring(px, py, pts):
                return True
            n = len(pts)
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % n]
                vx, vy = bx - ax, by - ay
                l2 = vx * vx + vy * vy
                t = 0.0 if l2 <= 0.0 else max(0.0, min(
                    1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
                if math.hypot(px - (ax + t * vx),
                              py - (ay + t * vy)) <= tol:
                    return True
        return False


def open_ground_between(domain: GradedDomain,
                        ax: float, ay: float, bx: float, by: float,
                        samples: int = STRIP_SEAM_OPEN_GROUND_SAMPLES
                        ) -> bool:
    """Does UNGRADED ground lie between the two nodes?  True when any
    INTERIOR sample of the pair's connecting segment is outside the
    graded domain by more than ``STRIP_SEAM_OPEN_GROUND_MIN_M`` (the
    slack ``domain`` was built with).

    THE OWNER'S TERRACE CLAUSE.  It is both (a) the wall-straddle
    exemption's precondition and (b) the selector for the PROVISIONAL
    open-boundary step floor — one predicate, two consumers, evaluated
    once per pair by the caller."""
    for k in range(1, samples - 1):
        f = k / (samples - 1)
        if not domain.covers(ax + (bx - ax) * f, ay + (by - ay) * f):
            return True
    return False


class WallFaces:
    """The emitted ``retaining_wall`` faces, indexed for the STRADDLE
    exemption: a level change rendered as DELIBERATE wall geometry is the
    ruling's sanctioned form, not a bare tear.

    ``segments`` are ``(x1, y1, x2, y2, way_idx)`` face segments (ring
    CLOSING segment included — see the caller's ring-closing note), and
    ``elev_range`` maps ``way_idx -> (lo, hi)`` for that wall way.
    """

    def __init__(self,
                 segments: Sequence[Tuple[float, float, float, float, int]],
                 elev_range: Dict[int, Tuple[float, float]],
                 cell_m: float) -> None:
        self._segs = list(segments)
        self._elev_range = elev_range
        self._cell = cell_m
        self._grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for i, (x1, y1, x2, y2, _wi) in enumerate(self._segs):
            for cx in range(int(math.floor(min(x1, x2) / cell_m)),
                            int(math.floor(max(x1, x2) / cell_m)) + 1):
                for cy in range(int(math.floor(min(y1, y2) / cell_m)),
                                int(math.floor(max(y1, y2) / cell_m)) + 1):
                    self._grid[(cx, cy)].append(i)

    def __bool__(self) -> bool:
        return bool(self._segs)

    def straddles(self, ax: float, ay: float, az: float,
                  bx: float, by: float, bz: float, *,
                  open_ground: bool,
                  min_step_m: float = STRIP_SEAM_TEAR_MIN_STEP_M,
                  min_distance_m: float = STRIP_SEAM_TEAR_MIN_DISTANCE_M
                  ) -> bool:
        """Does a wall FACE cross the pair's INTERIOR (within
        ``STRIP_SEAM_WALL_STRADDLE_TOL_M``, the contact point off both
        endpoints) with an elevation range that brackets both pair
        altitudes to within one step floor — AND ungraded ground between
        the two nodes (``open_ground``, the owner's law: the exemption is
        for the graded→DEM terrace in OPEN ground)?"""
        if not self._segs:
            return False
        if not open_ground:
            return False  # interior to graded ground: zones 1-2 / pocket
        cell = self._cell
        e_lo = min(az, bz)
        e_hi = max(az, bz)
        length = math.hypot(bx - ax, by - ay)
        if length <= 2 * min_distance_m:
            return False  # no interior to straddle (stacked pair)
        tol = STRIP_SEAM_WALL_STRADDLE_TOL_M
        seen: set = set()
        for cx in range(int(math.floor((min(ax, bx) - tol) / cell)),
                        int(math.floor((max(ax, bx) + tol) / cell)) + 1):
            for cy in range(
                    int(math.floor((min(ay, by) - tol) / cell)),
                    int(math.floor((max(ay, by) + tol) / cell)) + 1):
                for i in self._grid.get((cx, cy), ()):
                    if i in seen:
                        continue
                    seen.add(i)
                    x1, y1, x2, y2, w_idx = self._segs[i]
                    rng = self._elev_range.get(w_idx)
                    if rng is None:
                        continue
                    if (e_lo < rng[0] - min_step_m
                            or e_hi > rng[1] + min_step_m):
                        continue  # face cannot account for the level change
                    d_w, t_w = segment_segment_closest(ax, ay, bx, by,
                                                       x1, y1, x2, y2)
                    if d_w > tol:
                        continue
                    along = t_w * length
                    if (along >= min_distance_m
                            and (length - along) >= min_distance_m):
                        return True
        return False
