"""THE WALL LINES of a tunnel wall object (RULINGS 2026-09-05n-2; spec
``docs/specs/auto-patch-v2/tunnel-wall-objects-round2-spec.md`` §3.1;
law ``structures.toml [tunnel.object]``): the trench is the region
between the walls' INNER faces, following their curves; the wall band
is each wall's own plan footprint — never a hull rectangle.

MEASURED (OTHH, the seven Aeroscape tunnel objects, 2026-09-04): every
object is ONE welded solid component — the spec's "wall solids = the
components whose plan footprint is a thin band" has no component to
read.  What IS a thin band per wall is the CREST PLATE in plan: the
near-horizontal faces at the plate height are the walls' tops, and
their plan union is a U (two side walls joined by one end wall, the
other end open: six objects), an O (a box of four walls: ``tunnel west
1``), or two separate bands (two walls open at both ends — no OTHH
object, the synthetic twin).  This module reads THAT ring: the plate's
plan polygon in the airport frame → the two side walls' inner chains,
the end walls, the free (open) ends, the band thickness by station.

Geometry only; the datums (mouth, floor, ground) are
``tunnel_objects.py``'s.  Every number is a law-table value.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..model.frame import XY

__all__ = ["WallLines", "Station", "read_wall_lines", "stations_along", "midline"]

#: A ring vertex turning more than this is a CORNER (a side wall meeting
#: an end wall); curved side walls turn a few degrees per vertex.
_CORNER_DEG = 45.0
#: A FREE END is a ring edge no longer than this many wall thicknesses
#: across which the ring REVERSES (outer face → inner face of one wall).
_FREE_END_THICKNESS_FACTOR = 1.5
_REVERSAL_COS = -math.cos(math.radians(30.0))


@_dc.dataclass(frozen=True)
class WallLines:
    """The walls in the AIRPORT frame.  ``inner_a`` / ``inner_b`` are the
    two side walls' inner faces as polylines, BOTH running from end 0 to
    end 1; ``closed`` says whether an end wall stands across each end,
    ``end_thickness_m`` its plan thickness there; ``thickness_m`` the
    side bands' mean plan thickness; ``plate`` the walls' plan footprint
    (the crest plate's union); ``kind`` ``"U"`` / ``"O"`` / ``"II"``."""

    plate: Polygon
    inner_a: list[XY]
    inner_b: list[XY]
    closed: tuple[bool, bool]
    end_thickness_m: tuple[float, float]
    thickness_m: float
    kind: str
    #: The end walls' INNER faces as polylines from ``inner_a``'s end to
    #: ``inner_b``'s end (2026-09-06f: LEMD's Bridge4 closes its far end
    #: with THREE wall segments — an 11 m end wall, a 32 m oblique wall
    #: and a 10.6 m return); ``()`` at an open end.  The trench is closed
    #: along them, never along the chord between the side walls' ends.
    end_walls: tuple[tuple[XY, ...], tuple[XY, ...]] = ((), ())

    def trench_ring(self) -> list[XY]:
        """The region between the walls' inner faces, closed along the
        end walls where they stand."""
        ring = list(self.inner_a)
        ring += list(self.end_walls[1])[1:-1] if self.end_walls[1] else []
        ring += list(reversed(self.inner_b))
        ring += list(reversed(self.end_walls[0]))[1:-1] if self.end_walls[0] else []
        return ring

    def end_line(self, k: int) -> tuple[XY, XY]:
        """The segment across the corridor at end ``k`` (the inner faces'
        end vertices)."""
        return (self.inner_a[0], self.inner_b[0]) if k == 0 else (self.inner_a[-1], self.inner_b[-1])

    def end_point(self, k: int) -> XY:
        a, b = self.end_line(k)
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


@_dc.dataclass(frozen=True)
class Station:
    """One station along the corridor axis: ``s`` metres from the axis
    start, the inner faces ``half_l`` / ``half_r`` off the axis (left /
    right of the direction of travel), the side walls' plan thickness
    ``thick_l`` / ``thick_r`` there."""

    s: float
    half_l: float
    half_r: float
    thick_l: float
    thick_r: float


# ── ring analysis ────────────────────────────────────────────────────────

def _ring(poly_ring) -> list[XY]:
    c = [(float(x), float(y)) for x, y in poly_ring.coords]
    if len(c) > 1 and c[0] == c[-1]:
        c = c[:-1]
    return c


def _dir(a: XY, b: XY) -> XY:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def _length(pts: _t.Sequence[XY]) -> float:
    return sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


def _free_ends(ring: list[XY], max_len: float) -> list[int]:
    """Indices ``i`` of ring edges ``ring[i] → ring[i+1]`` that are FREE
    ENDS: short, and the ring reverses across them."""
    n = len(ring)
    out = []
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        if math.hypot(b[0] - a[0], b[1] - a[1]) > max_len:
            continue
        d_prev = _dir(ring[(i - 1) % n], a)
        d_next = _dir(b, ring[(i + 2) % n])
        if d_prev[0] * d_next[0] + d_prev[1] * d_next[1] <= _REVERSAL_COS:
            out.append(i)
    return out


def _corners(chain: list[XY]) -> list[int]:
    """Interior vertex indices of an open polyline where the direction
    turns more than ``_CORNER_DEG``."""
    out = []
    cos_lim = math.cos(math.radians(_CORNER_DEG))
    for i in range(1, len(chain) - 1):
        d0 = _dir(chain[i - 1], chain[i])
        d1 = _dir(chain[i], chain[i + 1])
        if d0[0] * d1[0] + d0[1] * d1[1] < cos_lim:
            out.append(i)
    return out


def _drop_jogs(chain: list[XY], corners: list[int], jog_max: float) -> list[int]:
    """The corners that are not JOGS: two consecutive corners closer
    than ``jog_max`` along the chain across which the direction RESUMES
    (LEMD's Bridge4: a 1.73 m sideways offset of the inner face mid-wall)
    are a jog of one wall, never an end wall."""
    cos_lim = math.cos(math.radians(_CORNER_DEG))
    keep: list[int] = []
    i = 0
    while i < len(corners):
        c = corners[i]
        if i + 1 < len(corners):
            d = corners[i + 1]
            if _length(chain[c: d + 1]) <= jog_max:
                d0 = _dir(chain[c - 1], chain[c])
                d1 = _dir(chain[d], chain[d + 1])
                if d0[0] * d1[0] + d0[1] * d1[1] >= cos_lim:
                    i += 2
                    continue
        keep.append(c)
        i += 1
    return keep


def _dedupe(pts: list[XY]) -> list[XY]:
    out: list[XY] = []
    for p in pts:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    return out


def _cut_ring(ring: list[XY], e1: int, e2: int) -> tuple[list[XY], list[XY]]:
    """The two open chains of ``ring`` between free-end edges ``e1`` and
    ``e2``: from ``ring[e1+1]`` forward to ``ring[e2]``, and from
    ``ring[e2+1]`` forward to ``ring[e1]``."""
    n = len(ring)

    def walk(i0: int, i1: int) -> list[XY]:
        out = [ring[i0]]
        i = i0
        while i != i1:
            i = (i + 1) % n
            out.append(ring[i])
        return out
    return walk((e1 + 1) % n, e2), walk((e2 + 1) % n, e1)


def _inner_of(chains: list[list[XY]], plate: Polygon) -> int:
    """The chain whose closed polygon overlaps the plate LEAST is the
    inner face (the outer face's polygon contains the whole band)."""
    best, best_area = 0, math.inf
    for k, ch in enumerate(chains):
        if len(ch) < 3:
            continue
        poly = Polygon(ch)
        if not poly.is_valid:
            poly = poly.buffer(0)
        ov = poly.intersection(plate).area if not poly.is_empty else math.inf
        if ov < best_area:
            best, best_area = k, ov
    return best


def _thickness_at(p: XY, outward: XY, plate: Polygon, reach: float) -> float | None:
    """The plate band's plan thickness from ``p`` (on its inner face)
    along ``outward``."""
    ray = LineString([p, (p[0] + outward[0] * reach, p[1] + outward[1] * reach)])
    x = ray.intersection(plate)
    if x.is_empty:
        return None
    return float(x.length) or None


def read_wall_lines(plate, law) -> WallLines | str:
    """The wall lines of a placed crest-plate polygon (airport frame), or
    the REASON it is not a readable pair of walls."""
    ob = law.tables.structures.tunnel.object
    tmax = ob.wall_face_max_thickness_m
    parts = [g for g in shapely.get_parts(plate) if g.geom_type == "Polygon" and g.area > 1e-6]
    if not parts:
        return "no plate polygon"
    plate_u = unary_union(parts)
    mean_t = 2.0 * plate_u.area / max(plate_u.length, 1e-9)
    # a box's rectangular ring measures EXACTLY its wall thickness by
    # 2A/P (OTHH tunnel west 1: 2.000 m walls at the 2.0 m law): the
    # comparison is at the materiality floor, never at floating noise
    if mean_t > tmax + law.tables.emit.materiality.elevation_m:
        return (f"the crest plate is a slab {mean_t:.2f} m thick in plan "
                f"(> wall_face_max_thickness_m {tmax}): a deck, not walls")
    if len(parts) == 1:
        part = shapely.simplify(parts[0], 0.01)
        ext = _dedupe(_ring(part.exterior))
        if len(part.interiors) == 1:
            # THE O: four walls, the hole ring is the inner faces
            hole = _dedupe(_ring(max(part.interiors, key=lambda h: Polygon(h).area)))
            hole_closed = hole + [hole[0]]
            corners = _corners([hole[-1]] + hole_closed)      # wrap so index i → hole[i-1]
            corners = sorted({(c - 1) % len(hole) for c in corners})
            if len(corners) != 4:
                return f"an O plate whose inner ring has {len(corners)} corners, not 4"
            sides = []
            for k in range(4):
                i0, i1 = corners[k], corners[(k + 1) % 4]
                seg = [hole[i0]]
                i = i0
                while i != i1:
                    i = (i + 1) % len(hole)
                    seg.append(hole[i])
                sides.append(seg)
            order = sorted(range(4), key=lambda k: -_length(sides[k]))
            ka = order[0]
            kb = (ka + 2) % 4                          # the opposite side
            a = sides[ka]
            b = list(reversed(sides[kb]))              # traversed the other way round the ring
            end_walls = [sides[(ka + 3) % 4], sides[(ka + 1) % 4]]      # at a[0] and a[-1]
            th = []
            for ew, p0 in zip(end_walls, (a[0], a[-1])):
                mid = ((ew[0][0] + ew[-1][0]) / 2.0, (ew[0][1] + ew[-1][1]) / 2.0)
                u = _dir(mid, a[0] if p0 is a[-1] else a[-1])
                t = _thickness_at(mid, (-u[0], -u[1]), plate_u, 3.0 * tmax)
                th.append(t if t else mean_t)
            # the end walls' inner faces from a's end to b's end
            ew0 = tuple(reversed(end_walls[0]))          # ends at a[0]: a[0] … b[0]
            ew1 = tuple(end_walls[1])                    # starts at a[-1]: a[-1] … b[-1]
            return WallLines(plate_u, a, b, (True, True), (th[0], th[1]), mean_t, "O",
                             (ew0, ew1))
        if part.interiors:
            return f"a plate with {len(part.interiors)} holes"
        free = _free_ends(ext, _FREE_END_THICKNESS_FACTOR * tmax)
        if len(free) != 2:
            return (f"a one-piece plate with {len(free)} free ends (a U has 2, "
                    f"an O a hole)")
        c1, c2 = _cut_ring(ext, free[0], free[1])
        chains = [c1, c2]
        ki = _inner_of(chains, plate_u)
        inner = chains[ki]
        corners = _drop_jogs(inner, _corners(inner), _FREE_END_THICKNESS_FACTOR * tmax)
        if len(corners) == 0:
            return "a single wall (a half object): two side walls are needed"
        if len(corners) < 2:
            return f"a U plate whose inner face has {len(corners)} corner, not 2"
        # THE END WALL is the run between the first and the last corner:
        # one segment (OTHH's box ends) or several (2026-09-06f: Bridge4's
        # end wall + oblique wall + return) — the side walls lie outside it
        i1, i2 = corners[0], corners[-1]
        side_a = list(reversed(inner[: i1 + 1]))        # from the end wall to the free end
        end_wall = inner[i1: i2 + 1]
        side_b = inner[i2:]
        mid = ((end_wall[0][0] + end_wall[-1][0]) / 2.0, (end_wall[0][1] + end_wall[-1][1]) / 2.0)
        u = _dir(mid, ((side_a[-1][0] + side_b[-1][0]) / 2.0, (side_a[-1][1] + side_b[-1][1]) / 2.0))
        t = _thickness_at(mid, (-u[0], -u[1]), plate_u, 3.0 * tmax)
        return WallLines(plate_u, side_a, side_b, (True, False), (t if t else mean_t, 0.0),
                         mean_t, "U", (tuple(end_wall), ()))
    if len(parts) == 2:
        # TWO SEPARATE WALLS (open at both ends): each band's inner face is
        # the chain nearer the other band
        inners: list[list[XY]] = []
        for k, part in enumerate(parts):
            part = shapely.simplify(part, 0.01)
            if part.interiors:
                return "a two-piece plate with a hole"
            ext = _dedupe(_ring(part.exterior))
            free = _free_ends(ext, _FREE_END_THICKNESS_FACTOR * tmax)
            if len(free) != 2:
                return f"a two-piece plate whose piece {k} has {len(free)} free ends, not 2"
            chains = list(_cut_ring(ext, free[0], free[1]))
            other = parts[1 - k]
            ki = min(range(2), key=lambda j: sum(other.distance(Point(p)) for p in chains[j])
                     / max(len(chains[j]), 1))
            inners.append(chains[ki])
        a, b = inners
        da, db = _dir(a[0], a[-1]), _dir(b[0], b[-1])
        if da[0] * db[0] + da[1] * db[1] < 0.0:
            b = list(reversed(b))
        return WallLines(plate_u, a, b, (False, False), (0.0, 0.0), mean_t, "II")
    return f"a plate in {len(parts)} pieces (two walls are one U/O piece or two bands)"


# ── the axis and its stations ────────────────────────────────────────────

def _resample(pts: _t.Sequence[XY], n: int) -> list[XY]:
    ln = LineString(pts)
    return [(p.x, p.y) for p in (ln.interpolate(k / (n - 1), normalized=True) for k in range(n))]


def midline(walls: WallLines, sample_m: float) -> list[XY]:
    """The corridor AXIS: the mean of the two inner faces resampled at
    equal fractions, from end 0 to end 1."""
    n = max(3, int(math.ceil(max(_length(walls.inner_a), _length(walls.inner_b)) / sample_m)) + 1)
    a, b = _resample(walls.inner_a, n), _resample(walls.inner_b, n)
    return [((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0) for p, q in zip(a, b)]


def stations_along(axis: _t.Sequence[XY], walls: WallLines, sample_m: float, grid_m: float
                   ) -> list[Station]:
    """Per station along ``axis`` (every ``sample_m``, the last ON the
    end): the inner faces' distances left / right of the axis (the
    station normal intersected with each inner chain; the chain's
    nearest point where the normal misses it, at the ends) and the side
    bands' thickness there.  Left is the side ``inner_a`` lies on."""
    ln = LineString(axis)
    A, B = LineString(walls.inner_a), LineString(walls.inner_b)
    L = ln.length
    ss = [sample_m * k for k in range(int(L // sample_m) + 1)]
    if L - ss[-1] > 1e-6:
        ss.append(L)
    # which side is A on? (the cross product at the axis midpoint)
    pm = ln.interpolate(0.5, normalized=True)
    q0, q1 = ln.interpolate(max(0.0, L * 0.5 - 1.0)), ln.interpolate(min(L, L * 0.5 + 1.0))
    u = _dir((q0.x, q0.y), (q1.x, q1.y))
    pa = A.interpolate(A.project(pm))
    cross = u[0] * (pa.y - pm.y) - u[1] * (pa.x - pm.x)
    left, right = (A, B) if cross >= 0.0 else (B, A)
    reach = 3.0 * max(A.distance(pm), B.distance(pm), 1.0)
    tmax = 3.0 * max(walls.thickness_m, grid_m)

    def at(s: float) -> Station | None:
        """The station at ``s``, or ``None`` where its normal misses an
        inner chain (past a wall's end: the free ends are oblique)."""
        p = ln.interpolate(s)
        a0, a1 = ln.interpolate(max(0.0, s - 1.0)), ln.interpolate(min(L, s + 1.0))
        u = _dir((a0.x, a0.y), (a1.x, a1.y))
        n = (-u[1], u[0])
        halves = []
        thicks = []
        for chain, sign in ((left, 1.0), (right, -1.0)):
            ray = LineString([(p.x, p.y), (p.x + sign * n[0] * reach, p.y + sign * n[1] * reach)])
            x = ray.intersection(chain)
            pts = [g for g in shapely.get_parts(x) if g.geom_type == "Point"] \
                if not x.is_empty else []
            h = min((math.hypot(g.x - p.x, g.y - p.y) for g in pts), default=None)
            if h is None:
                return None
            halves.append(h)
            ip = (p.x + sign * n[0] * h, p.y + sign * n[1] * h)
            t = _thickness_at(ip, (sign * n[0], sign * n[1]), walls.plate, tmax)
            thicks.append(max(grid_m, t) if t else max(grid_m, walls.thickness_m))
        return Station(float(s), halves[0], halves[1], thicks[0], thicks[1])

    hits = [(s, at(s)) for s in ss]
    good = [k for k, (_s, st) in enumerate(hits) if st is not None]
    if not good:
        return []
    out = [st for _s, st in hits[good[0]: good[-1] + 1] if st is not None]
    # THE TERMINAL STATIONS: bisect from the last hit toward each miss so
    # the trench ends where the SHORTER wall does (an oblique free end),
    # never past a wall
    for lo, hi, front in ((ss[good[0] - 1] if good[0] > 0 else None, ss[good[0]], True),
                          (ss[good[-1]], ss[good[-1] + 1] if good[-1] + 1 < len(ss) else None, False)):
        if lo is None or hi is None:
            continue
        a, b = (hi, lo) if front else (lo, hi)      # a hits, b misses
        for _k in range(12):
            m = (a + b) / 2.0
            if at(m) is None:
                b = m
            else:
                a = m
        st = at(a)
        if st is not None and abs(a - (out[0].s if front else out[-1].s)) > grid_m:
            if front:
                out.insert(0, st)
            else:
                out.append(st)
    return out
