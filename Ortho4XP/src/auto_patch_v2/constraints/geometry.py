"""Pure planar geometry the generators and the verifier share — ring
walks, the runway principal axis, the road long axis, station
clustering, rectangles, point-in-ring and THE TRANSECT WALK.

Everything here is arithmetic over ``(x, y)`` tuples: no shapely, so
the same function serves the constraint generator (planar-map frame) and
``verify/`` (the emitted patch's own frame).  Where a helper mirrors a
v1 law reader it says which one, so the v1 census (the oracle) and v2
price the same geometry:

* :func:`principal_axis`      = ``grade_law.runway_axis_and_width``
* :func:`long_axis`           = ``grade_law.long_axis_of_points``
* :func:`pair_is_transverse`  = ``grade_law.pair_is_transverse``
* :func:`station_indices`     = ``grade_law.runway_axis_station_indices``
* :func:`longitudinal_runs`   = ``grade_law.runway_strip_longitudinal_runs``
* :func:`walk_transects`      = v1 ``transect_walk.walk_transects``
  (owner 2026-08-21: ONE station set, both readers)
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..model.planar import PlanarMap

XY = tuple[float, float]

__all__ = [
    "ring_vertex_ids", "face_outer_ids", "principal_axis", "long_axis",
    "pair_is_transverse", "station_indices", "longitudinal_runs",
    "rect_ring", "point_in_ring", "point_in_rect_ring", "project_to_chain",
    "TransectShape", "TransectAxis", "Transect", "walk_transects",
    "polyline_length",
]


# ── ring walks ───────────────────────────────────────────────────────────

def ring_vertex_ids(pm: PlanarMap, cycle: _t.Sequence[int]) -> list[int]:
    """The vertex ids of an edge cycle in walking order (first not
    repeated) — ``PlanarMap.ring_vertices``."""
    return list(pm.ring_vertices(cycle))


def face_outer_ids(pm: PlanarMap) -> dict[int, list[int]]:
    """Face id -> outer ring vertex ids (open), for every face."""
    return {fid: ring_vertex_ids(pm, f.ring) for fid, f in pm.faces.items()}


def polyline_length(pts: _t.Sequence[XY]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


# ── axes ─────────────────────────────────────────────────────────────────

def principal_axis(points: _t.Sequence[XY]) -> tuple[XY, XY, float] | None:
    """``(axis_a, axis_b, width_m)`` — the largest-variance axis of a
    vertex cloud, its extreme along-axis stations and the transverse
    extent (v1 ``grade_law.runway_axis_and_width``, verbatim math)."""
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
    lam = 0.5 * tr + math.sqrt(disc)
    if abs(sxy) > 1e-9:
        ux, uy = lam - syy, sxy
    else:
        ux, uy = (1.0, 0.0) if sxx >= syy else (0.0, 1.0)
    norm = math.hypot(ux, uy)
    if norm < 1e-12:
        return None
    ux, uy = ux / norm, uy / norm
    along = [(x - cx) * ux + (y - cy) * uy for x, y in pts]
    across = [(x - cx) * -uy + (y - cy) * ux for x, y in pts]
    s0, s1 = min(along), max(along)
    if s1 - s0 <= 0.0:
        return None
    return ((cx + s0 * ux, cy + s0 * uy), (cx + s1 * ux, cy + s1 * uy),
            max(across) - min(across))


def long_axis(pts: _t.Sequence[XY]) -> tuple[XY, float, XY] | None:
    """``((ux, uy), length, mid)`` of the minimum-area rectangle of a
    ring (v1 ``grade_law.long_axis_of_points``): the road's own
    direction (RULINGS 2026-08-25g)."""
    pts = [(float(x), float(y)) for (x, y) in pts]
    if len(pts) < 3:
        return None
    best = None
    for i in range(len(pts)):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % len(pts)]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
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


def pair_is_transverse(axis: XY | None, dx: float, dy: float,
                       min_deg: float) -> bool:
    """A pair at or beyond ``min_deg`` off ``axis`` is ACROSS it
    (``grade_law.pair_is_transverse``)."""
    if axis is None:
        return False
    d = math.hypot(dx, dy)
    if d < 1e-9:
        return False
    cos_t = abs(dx * axis[0] + dy * axis[1]) / d
    return cos_t <= math.cos(math.radians(min_deg))


def station_indices(ring: _t.Sequence[XY], cluster_m: float
                    ) -> list[int] | None:
    """Longitudinal station index per ring vertex along the ring's
    longest vertex pair, clustered at ``cluster_m``
    (``grade_law.runway_axis_station_indices``)."""
    n = len(ring)
    if n < 2:
        return None
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
    st = [((ring[i][0] - ax) * ux + (ring[i][1] - ay) * uy) for i in range(n)]
    order = sorted(range(n), key=lambda i: st[i])
    out = [0] * n
    cluster = 0
    prev = st[order[0]]
    for k in range(1, n):
        i = order[k]
        if st[i] - prev > cluster_m:
            cluster += 1
        out[i] = cluster
        prev = st[i]
    return out


def longitudinal_runs(points: _t.Sequence[XY], axis: XY,
                      inside: _t.Sequence[bool] | None = None
                      ) -> list[list[int]]:
    """Runs of consecutive indices whose steps are predominantly ALONG
    ``axis`` and inside the footprint
    (``grade_law.runway_strip_longitudinal_runs``)."""
    ux, uy = axis
    norm = math.hypot(ux, uy)
    if norm < 1e-12:
        return []
    ux, uy = ux / norm, uy / norm
    px, py = -uy, ux
    runs: list[list[int]] = []
    cur: list[int] = []
    for i in range(len(points)):
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


# ── rectangles and containment ───────────────────────────────────────────

def rect_ring(a: XY, b: XY, s0: float, s1: float, half: float) -> list[XY]:
    """Closed ring of the band ``s ∈ [s0, s1]``, ``|t| ≤ half`` along the
    axis ``a -> b`` (``grade_law.runway_strip_wall_keepout_rings``'s
    ``_rect``)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    px, py = -uy, ux
    corners = ((s0, -half), (s1, -half), (s1, half), (s0, half))
    ring = [(a[0] + ux * s + px * t, a[1] + uy * s + py * t) for (s, t) in corners]
    return ring + [ring[0]]


def point_in_ring(px: float, py: float, ring: _t.Sequence[XY]) -> bool:
    """Even-odd containment (open or closed ring)."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > py) != (yj > py):
            x = xj + (py - yj) * (xi - xj) / (yi - yj)
            if px < x:
                inside = not inside
        j = i
    return inside


def point_in_rect_ring(px: float, py: float, ring: _t.Sequence[XY],
                       margin: float = 0.0) -> bool:
    """Inside a 5-point parallelogram ring by at least ``margin``
    (``check_grade._point_in_rect_ring``)."""
    if len(ring) != 5:
        return point_in_ring(px, py, ring[:-1])
    ox, oy = ring[0]
    e1x, e1y = ring[1][0] - ox, ring[1][1] - oy
    e2x, e2y = ring[3][0] - ox, ring[3][1] - oy
    l1 = math.hypot(e1x, e1y)
    l2 = math.hypot(e2x, e2y)
    if l1 <= 2.0 * margin or l2 <= 2.0 * margin:
        return False
    t1 = ((px - ox) * e1x + (py - oy) * e1y) / l1
    t2 = ((px - ox) * e2x + (py - oy) * e2y) / l2
    return (margin <= t1 <= l1 - margin) and (margin <= t2 <= l2 - margin)


def project_to_chain(p: XY, chain: _t.Sequence[XY]
                     ) -> tuple[float, int, float, float]:
    """``(distance, segment index, t, arc length s)`` of the nearest
    point on the polyline ``chain`` to ``p``."""
    best = (float("inf"), 0, 0.0, 0.0)
    s = 0.0
    for k in range(len(chain) - 1):
        (ax, ay), (bx, by) = chain[k], chain[k + 1]
        vx, vy = bx - ax, by - ay
        l2 = vx * vx + vy * vy
        if l2 < 1e-18:
            continue
        t = ((p[0] - ax) * vx + (p[1] - ay) * vy) / l2
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        qx, qy = ax + t * vx, ay + t * vy
        d = math.hypot(p[0] - qx, p[1] - qy)
        if d < best[0]:
            best = (d, k, t, s + t * math.sqrt(l2))
        s += math.sqrt(l2)
    return best


# ── the transect walk (owner 2026-08-21: one station set, both readers) ──

@_dc.dataclass(frozen=True)
class TransectShape:
    """A ring the walk may cross: ``ring`` = ``[(x, y, z), ...]`` open;
    ``key`` the reader's identity (face id / way id)."""

    role: str
    ring: _t.Sequence[tuple[float, float, float]]
    key: object


@_dc.dataclass(frozen=True)
class TransectAxis:
    """One centreline with ONE longitudinal cap (an axis whose cap
    changes is split into several)."""

    poly: _t.Sequence[XY]
    cap_l: float
    is_service: bool = False
    key: object = None


@_dc.dataclass(frozen=True)
class Transect:
    """One priced cross-section: the two ring EDGES the perpendicular
    crosses and where along each (a weighted 4-node row)."""

    axis_key: object
    shape_key: object
    role: str
    px: float
    py: float
    nx: float
    ny: float
    u_lo: float
    edge_lo: int
    t_lo: float
    z_lo: float
    u_hi: float
    edge_hi: int
    t_hi: float
    z_hi: float
    width_m: float
    cap_l: float

    def point_lo(self) -> XY:
        return (self.px + self.nx * self.u_lo, self.py + self.ny * self.u_lo)

    def point_hi(self) -> XY:
        return (self.px + self.nx * self.u_hi, self.py + self.ny * self.u_hi)


_CELL_M = 40.0


def _edge_index(shapes: _t.Sequence[TransectShape]):
    grid: dict[tuple[int, int], list[tuple[int, int]]] = {}
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


def walk_transects(shapes: _t.Sequence[TransectShape],
                   axes: _t.Sequence[TransectAxis],
                   priced_roles_for_axis: _t.Callable[[TransectAxis], _t.Container[str]],
                   *, step_m: float, half_m: float, min_width_m: float,
                   max_gap_m: float) -> _t.Iterator[Transect]:
    """Every priced cross-section, deterministic order — a verbatim port
    of v1 ``transect_walk.walk_transects`` (the census's own
    station set; ``tests/auto_patch_v2/test_constraints.py`` twins it)."""
    if not shapes or not axes:
        return
    grid = _edge_index(shapes)
    for axis in axes:
        poly = axis.poly
        if len(poly) < 2:
            continue
        priced = priced_roles_for_axis(axis)
        for k in range(len(poly) - 1):
            (x1, y1), (x2, y2) = poly[k], poly[k + 1]
            seg_len = math.hypot(x2 - x1, y2 - y1)
            if seg_len < 1e-6:
                continue
            tx, ty = (x2 - x1) / seg_len, (y2 - y1) / seg_len
            nx, ny = -ty, tx
            s = 0.0
            while s <= seg_len + 1e-9:
                px, py = x1 + tx * s, y1 + ty * s
                s += step_m
                cand: set = set()
                for f in (-half_m, -0.5 * half_m, 0.0, 0.5 * half_m, half_m):
                    qx, qy = px + nx * f, py + ny * f
                    gx, gy = int(qx // _CELL_M), int(qy // _CELL_M)
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            cand.update(grid.get((gx + dx, gy + dy), ()))
                hits: dict[int, list] = {}
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
                        if not point_in_ring(px + nx * mid, py + ny * mid, ring2):
                            continue
                        if best_gap is None or gap < best_gap:
                            best_gap = gap
                            span = (lo_h, hi_h)
                    if span is None:
                        continue
                    (u_lo, z_lo, e_lo, t_lo), (u_hi, z_hi, e_hi, t_hi) = span
                    yield Transect(
                        axis_key=axis.key, shape_key=sh.key, role=sh.role,
                        px=px, py=py, nx=nx, ny=ny,
                        u_lo=u_lo, edge_lo=e_lo, t_lo=t_lo, z_lo=z_lo,
                        u_hi=u_hi, edge_hi=e_hi, t_hi=t_hi, z_hi=z_hi,
                        width_m=u_hi - u_lo, cap_l=axis.cap_l)
