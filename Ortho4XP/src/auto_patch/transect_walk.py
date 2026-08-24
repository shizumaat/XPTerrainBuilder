"""THE TRANSECT WALK — one station set, both readers.

Owner ruling 2026-08-21 (RULINGS "RM's relocated airside debt is paid by
the solver pricing transverse"); spec
``docs/specs/transverse-hyperplane-solve-spec.md`` step 2 / §8.

WHAT A TRANSECT IS.  The ``transverse`` law prices a corridor's
CROSS-SECTION: every ``STEP_M`` along a taxi/service axis, a perpendicular
is dropped to ``HALF_M`` either side, the pavement span bracketing the
station is selected, and the two ends' heights are read by INTERPOLATING
along the ring EDGES the perpendicular crosses.  It is not a vertex pair
and it is not a chord between ring vertices: at CYXY 66 of 75 airside
transverse rows have no ring vertex within the weld tolerance of either
end.

WHY IT LIVES HERE.  The walk was written twice — once in
``tools/check_grade._check_transverse_grade`` (the census) and once, in a
different shape, in ``lateral_spine_nodes._bracket_feet`` (the emitter's
foot planting), with a test asserting that three of their constants
agreed.  The owner has now moved this family into the SOLVE, which makes
the station set a shared LAW OBJECT rather than one reader's internal
detail: the solve must bind exactly the stations the census will price,
or the round buys nothing.  Two walks cannot be asserted equal by
comparing constants; one walk can be asserted equal by construction.  So
the walk is here, the constants are here, and
``tests/test_transect_walk.py`` proves both readers get identical station
sets on a ring that carries collinear inserts (the case that makes two
walks diverge).

WHAT IT DOES NOT DO.  It reads no law and prices nothing: it produces
GEOMETRY (which station, which span, which edges, at what parameters) and
hands back the axis segment's own longitudinal cap.  The budget is
``grade_law.transverse_span_budget_m``; the census adds its encoding
envelope and the declared terrace step; the solve adds nothing.  Keeping
the pricing OUT of the walker is what lets the same station serve a
census row and a solve constraint without either reader's forgiveness
leaking into the other.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .strip_seam_law import point_in_ring

#: Stations along an axis, in metres.  A station every 10 m is the census
#: population of record; two stations on one shape are correlated, which
#: is why every report states the station count beside the row count.
STEP_M = 10.0
#: How far either side of the axis a perpendicular looks for pavement.
HALF_M = 80.0
#: The narrowest cross-section the law prices.
MIN_WIDTH_M = 3.0
#: How far the priced span's NEAR side may sit from the axis.  A span
#: whose near side is further out than this is not the corridor the axis
#: runs down, so the law does not price it.
MAX_GAP_M = 1.0
#: Grid cell for the candidate-edge index.  Pure acceleration: it changes
#: which edges are TESTED, never which are selected.
_CELL_M = 40.0


@dataclass(frozen=True)
class TransectShape:
    """One shape the walk may cross.  ``ring`` is ``[(x, y, z), ...]`` in
    the reader's own layout-local metre frame, already de-duplicated of a
    repeated closing vertex; ``key`` is whatever identity the reader
    joins on (a way id census-side, a shape index solver-side)."""
    role: str
    ring: Sequence[Tuple[float, float, float]]
    key: object


@dataclass(frozen=True)
class TransectAxis:
    """One centreline: ``poly`` = ``[(x, y), ...]``, ``seg_caps`` = the
    LONGITUDINAL cap per segment, ``is_service`` = the sidecar's own
    service flag ("a truck route is not an aircraft spine")."""
    poly: Sequence[Tuple[float, float]]
    seg_caps: Sequence[float]
    is_service: bool = False


@dataclass(frozen=True)
class TransectStation:
    """ONE priced cross-section.

    ``station_id`` is deterministic and reader-independent — the tuple
    ``(axis, segment, station, shape_key)`` — so a solver-bound span and a
    census-priced row JOIN on it without either side inventing an
    identity.  ``edge_lo`` / ``t_lo`` name the ring EDGE the near hit sits
    on and where along it (``ring[edge_lo]`` → ``ring[edge_lo + 1]``,
    wrapping), which is exactly the pair of nodes and the weight a
    weighted 4-node constraint needs; ``z_lo`` is the interpolation the
    census reads.  ``cap_l`` is the axis segment's LONGITUDINAL cap — the
    budget is ``grade_law.transverse_span_budget_m(cap_l, width_m)``."""
    station_id: tuple
    shape_key: object
    role: str
    px: float
    py: float
    nx: float
    ny: float
    u_lo: float
    z_lo: float
    edge_lo: int
    t_lo: float
    u_hi: float
    z_hi: float
    edge_hi: int
    t_hi: float
    width_m: float
    cap_l: float

    @property
    def dz(self) -> float:
        return abs(self.z_hi - self.z_lo)

    def point_lo(self) -> Tuple[float, float]:
        return (self.px + self.nx * self.u_lo, self.py + self.ny * self.u_lo)

    def point_hi(self) -> Tuple[float, float]:
        return (self.px + self.nx * self.u_hi, self.py + self.ny * self.u_hi)


def _edge_index(shapes: Sequence[TransectShape]) -> Dict[Tuple[int, int],
                                                         List[Tuple[int, int]]]:
    grid: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for si, sh in enumerate(shapes):
        ring = sh.ring
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            for gx in range(int(x0 // _CELL_M), int(x1 // _CELL_M) + 1):
                for gy in range(int(y0 // _CELL_M), int(y1 // _CELL_M) + 1):
                    grid.setdefault((gx, gy), []).append((si, i))
    return grid


def walk_transects(shapes: Sequence[TransectShape],
                   axes: Sequence[TransectAxis],
                   priced_roles_for_axis,
                   *,
                   step_m: float = STEP_M,
                   half_m: float = HALF_M,
                   min_width_m: float = MIN_WIDTH_M,
                   max_gap_m: float = MAX_GAP_M,
                   station_count: Optional[list] = None,
                   ) -> Iterable[TransectStation]:
    """Yield every priced cross-section, in a deterministic order.

    ``priced_roles_for_axis(axis) -> set`` is the caller's per-axis-kind
    scope ("a truck route is not an aircraft spine"): the roles THAT axis
    may censure.  ``station_count`` (optional list) receives the number of
    stations WALKED — the population denominator every honest report
    quotes beside the row count.

    Determinism: axes in order, segments in order, stations in order along
    the segment, and — for the several shapes one station can cross —
    shapes in the order they appear in ``shapes``.  Nothing here iterates
    a set or a dict whose order is not the insertion order of that list,
    so two readers holding the same rings and axes cannot produce
    different station sets or a different order.
    """
    if not shapes or not axes:
        return
    grid = _edge_index(shapes)
    n_stations = 0
    for ai, axis in enumerate(axes):
        poly = axis.poly
        if len(poly) < 2:
            continue
        caps = axis.seg_caps
        cap_list = (list(caps) if isinstance(caps, (list, tuple))
                    else [caps] * (len(poly) - 1))
        if not cap_list:
            continue
        priced = priced_roles_for_axis(axis)
        for k in range(len(poly) - 1):
            (x1, y1), (x2, y2) = poly[k], poly[k + 1]
            seg_len = math.hypot(x2 - x1, y2 - y1)
            if seg_len < 1e-6:
                continue
            tx, ty = (x2 - x1) / seg_len, (y2 - y1) / seg_len
            nx, ny = -ty, tx
            cap_l = float(cap_list[k] if k < len(cap_list) else cap_list[-1])
            s = 0.0
            station = 0
            while s <= seg_len + 1e-9:
                px, py = x1 + tx * s, y1 + ty * s
                s += step_m
                n_stations += 1
                si_here = station
                station += 1
                cand: set = set()
                for f in (-half_m, -0.5 * half_m, 0.0,
                          0.5 * half_m, half_m):
                    qx, qy = px + nx * f, py + ny * f
                    gx, gy = int(qx // _CELL_M), int(qy // _CELL_M)
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            cand.update(grid.get((gx + dx, gy + dy), ()))
                # HITS PER SHAPE, in SHAPE ORDER — never set order (a set
                # iteration here would make the station set depend on hash
                # seeding, and two readers would silently diverge).
                hits: Dict[int, List[Tuple[float, float, int, float]]] = {}
                for (si, i) in sorted(cand):
                    sh = shapes[si]
                    if sh.role not in priced:
                        continue
                    ring = sh.ring
                    a, b = ring[i], ring[(i + 1) % len(ring)]
                    ex, ey = b[0] - a[0], b[1] - a[1]
                    den = nx * ey - ny * ex
                    if abs(den) < 1e-12:
                        continue
                    rx, ry = a[0] - px, a[1] - py
                    t = (rx * ny - ry * nx) / den
                    if t < -1e-9 or t > 1.0 + 1e-9:
                        continue
                    # THE ADMISSION TOLERANCE MUST NOT LEAK INTO THE
                    # PARAMETER (2026-08-21, attempt 2).  A hit AT an
                    # endpoint lands at t = -1e-9 or 1+1e-9, and a reader
                    # that turns t into a WEIGHT then carries a tiny
                    # NEGATIVE coefficient — measured on the bound rows:
                    # min(t, 1-t, s, 1-s) reached -1.6e-13 at HECA.  The
                    # tolerance admits the hit; the parameter is the
                    # position, and a position outside its own edge is
                    # not one.
                    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                    u = (rx + t * ex) * nx + (ry + t * ey) * ny
                    if abs(u) > half_m:
                        continue
                    hits.setdefault(si, []).append(
                        (u, a[2] + t * (b[2] - a[2]), i, t))
                for si in sorted(hits):
                    hl = hits[si]
                    if len(hl) < 2:
                        continue
                    hl.sort()
                    sh = shapes[si]
                    ring2 = [(p[0], p[1]) for p in sh.ring]
                    # Every consecutive hit pair is a candidate SPAN; keep
                    # the INSIDE span nearest u=0 (the station can sit
                    # exactly ON a ring edge, so a strict u≤0≤u bracket is
                    # floating-point fragile).
                    span = None
                    best_gap = None
                    for j in range(len(hl) - 1):
                        lo_h, hi_h = hl[j], hl[j + 1]
                        if hi_h[0] - lo_h[0] < min_width_m:
                            continue
                        gap = (0.0 if lo_h[0] <= 0.0 <= hi_h[0]
                               else min(abs(lo_h[0]), abs(hi_h[0])))
                        if gap > max_gap_m:
                            continue
                        mid = 0.5 * (lo_h[0] + hi_h[0])
                        if not point_in_ring(px + nx * mid, py + ny * mid,
                                             ring2):
                            continue
                        if best_gap is None or gap < best_gap:
                            best_gap = gap
                            span = (lo_h, hi_h)
                    if span is None:
                        continue
                    (u_lo, z_lo, e_lo, t_lo), (u_hi, z_hi, e_hi, t_hi) = span
                    yield TransectStation(
                        station_id=(ai, k, si_here, sh.key),
                        shape_key=sh.key, role=sh.role,
                        px=px, py=py, nx=nx, ny=ny,
                        u_lo=u_lo, z_lo=z_lo, edge_lo=e_lo, t_lo=t_lo,
                        u_hi=u_hi, z_hi=z_hi, edge_hi=e_hi, t_hi=t_hi,
                        width_m=u_hi - u_lo, cap_l=cap_l)
    if station_count is not None:
        station_count.append(n_stations)
