"""The STRIP-SEAM law the census's seam readers price.

COPIED from ``strip_seam_law.py`` on 2026-09-17 (lane ``v1retire`` round 1, ruling (d)
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

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple
import math


STRIP_SEAM_TEAR_RADIUS_M = 6.0         # only NEAR-adjacent strip nodes pair


STRIP_SEAM_TEAR_MIN_STEP_M = 1.0       # Δalt at/under this = lawful terrace / noise


STRIP_SEAM_TEAR_MIN_GRADE = 0.5


STRIP_SEAM_TEAR_MIN_DISTANCE_M = 0.01  # grade denominator clamp (stacked walls)


STRIP_SEAM_WALL_STRADDLE_TOL_M = 0.5


STRIP_SEAM_ROLE = "graded_strip"


STRIP_SEAM_OPEN_GROUND_MIN_M = 0.01


STRIP_SEAM_OPEN_GROUND_SAMPLES = 21    # ⇒ 19 interior samples


STRIP_SEAM_GRADED_ROLES = frozenset({
    "graded_strip",
    "runway", "primary_parallel", "secondary_parallel", "stub",
    "junction", "cross_connector", "apron", "terminal", "building",
    "service_road", "service_junction", "groundside_pavement",
    "tunnel_ramp", "bridge_trench", "bridge_causeway", "hangar_pad",
})


STRIP_SEAM_OPEN_BOUNDARY_FLOOR_M = 15.0


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


def paved_unpaved_dropoff_exempt(de_m: float, allowance_m: float) -> bool:
    """§B1 — is a step at a PAVED→UNPAVED boundary the MANDATED edge
    drop-off (FAA AC 150/5300-13B §4.14.2 item 2, repeated for aprons at
    §5.9.1.5: 1.5 in ± 1/2 in = 38 ± 13 mm) rather than a defect?

    THE SHARED PREDICATE HOME (round-B interaction fence): seam v4, the
    step checks and the census all call THIS, so there is one text.  The
    NUMBER is the caller's — ``grade_law.shoulder_edge_dropoff_exempt``
    resolves it from the ruleset and calls straight through, which keeps
    this module stdlib-only (it is imported on a hot solve path and by
    the standalone ``tools/check_grade.py``).  ``allowance_m`` is 0 under
    an authority that mandates FLUSH instead (ICAO §3.2.3), so the
    exemption is a no-op at every ICAO airport.

    PROSPECTIVE: no emitter mints a 38 mm step today, so this exempts
    zero rows at present.  It exists so that when the §B1 shoulder band
    does emit one, the census does not call the regulation a defect.
    """
    return allowance_m > 0.0 and abs(float(de_m)) <= float(allowance_m) + 1e-9


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

