"""Chord density — the ONE decimator (plan §1: chord density is a law
parameter applied once at planar-map build; memory
``two-decimators-mask-each-other``).

``densify`` inserts vertices so no chord exceeds the cap;
``stations`` lays the runway / spine profile stations at
``law.emit.chords.station_spacing_m`` along a breakline source;
``abeam_stations`` gives a road kerb vertex its opposite on the facing
chord (#1918 R3).  All are pure functions over coordinate sequences; snapping to the identity grid
happens once, at noding (``overlay.py``).
"""
from __future__ import annotations

import math
import typing as _t

from ..model.frame import XY

__all__ = ["densify", "densify_within", "stations", "ring_lines", "abeam_stations"]


def densify(points: _t.Sequence[XY], cap_m: float, closed: bool = False
            ) -> list[XY]:
    """``points`` with extra vertices so every chord is ≤ ``cap_m``;
    a closed ring also densifies its closing chord."""
    pts = list(points)
    if closed and pts and pts[0] != pts[-1]:
        pts.append(pts[0])
    if cap_m <= 0 or len(pts) < 2:
        return pts
    out: list[XY] = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        d = math.hypot(bx - ax, by - ay)
        n = max(1, math.ceil(d / cap_m - 1e-9))
        for k in range(1, n):
            t = k / n
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
        out.append((bx, by))
    return out


def densify_within(points: _t.Sequence[XY], zone, cap_m: float) -> list[XY]:
    """``points`` (an open or closed coordinate list) with extra vertices so
    every chord's stretch inside ``zone`` (a shapely polygon) is <= ``cap_m``:
    each segment that crosses the zone gains a vertex where it enters and
    leaves it and evenly spaced ones between.  Outside the zone nothing
    changes; every new vertex lies on the segment it splits."""
    import shapely
    from shapely.geometry import LineString
    pts = list(points)
    if cap_m <= 0 or len(pts) < 2 or zone is None or zone.is_empty:
        return pts
    out: list[XY] = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:], strict=False):
        d = math.hypot(bx - ax, by - ay)
        seg = LineString([(ax, ay), (bx, by)])
        ts: list[float] = []
        if d > cap_m and zone.intersects(seg):
            for part in shapely.get_parts(zone.intersection(seg)):
                if part.geom_type != "LineString" or part.length <= cap_m:
                    continue
                t0, t1 = sorted(seg.project(shapely.Point(c)) / d for c in
                                (part.coords[0], part.coords[-1]))
                n = math.ceil((t1 - t0) * d / cap_m - 1e-9)
                ts.extend(t0 + (t1 - t0) * k / n for k in range(n + 1))
        for t in sorted(t for t in set(ts) if 1e-9 < t < 1.0 - 1e-9):
            out.append((ax + (bx - ax) * t, ay + (by - ay) * t))
        out.append((bx, by))
    return out


def stations(points: _t.Sequence[XY], spacing_m: float) -> list[XY]:
    """Vertices along a polyline every ``spacing_m`` (measured along the
    line), original vertices kept — the profile station chain."""
    return densify(points, spacing_m, closed=False)


def ring_lines(outer: _t.Sequence[XY], holes: _t.Sequence[_t.Sequence[XY]],
               cap_m: float) -> list[list[XY]]:
    """The closed rings of a face, densified — as line coordinate lists
    for the noding pass."""
    out = [densify(outer, cap_m, closed=True)]
    out.extend(densify(h, cap_m, closed=True) for h in holes if len(h) >= 3)
    return out


def abeam_stations(ring: _t.Sequence[XY], within_m: float, min_gap_m: float,
                   face=None, keep_off: _t.Callable[[XY], bool] | None = None
                   ) -> list[XY]:
    """#1918 R3 ABEAM STATIONS: ``ring`` (a closed or open coordinate list)
    with a vertex added on a chord at the FOOT of the perpendicular from a
    ring vertex across the face — so the per-vertex law, which prices
    vertex pairs, sees the kerb a vertex faces where that kerb has no vertex
    opposite it (MEASURED LGAV 37.92736,23.93425: a pad tip 0.4-1.3 m from a
    31 m road chord stood 0.7-1.0 m over it).  A foot is minted when it is
    ``min_gap_m`` <= d <= ``within_m`` from its vertex, at least ``min_gap_m``
    from every ring vertex, chord end and station already minted (nearest
    first), the segment vertex -> foot lies in ``face`` (default: the ring's
    own polygon) and ``keep_off(foot)`` is false.  Feet are taken from the
    input vertices only (one pass); each lies on the chord it splits."""
    import numpy as np
    import shapely
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree
    pts = [tuple(map(float, p)) for p in ring]
    closed = len(pts) > 1 and pts[0] == pts[-1]
    verts = pts[:-1] if closed else pts
    if len(verts) < 3 or within_m <= 0.0 or len(pts) < 2:
        return list(ring)
    P = np.asarray(pts)
    A, B = P[:-1], P[1:]
    V = np.asarray(verts)
    chords = shapely.linestrings(np.stack([A, B], axis=1))
    vi, cj = STRtree(chords).query(shapely.points(V), predicate="dwithin",
                                   distance=within_m)
    if len(vi) == 0:
        return list(ring)
    a, ab, v = A[cj], B[cj] - A[cj], V[vi]
    L = np.hypot(ab[:, 0], ab[:, 1])
    ok = L >= 2.0 * min_gap_m
    t = np.where(ok, ((v - a) * ab).sum(axis=1) / np.where(ok, L * L, 1.0), -1.0)
    foot = a + ab * t[:, None]
    d = np.hypot(*(v - foot).T)
    ok &= (d >= min_gap_m) & (d <= within_m) & (t * L >= min_gap_m) & ((1.0 - t) * L >= min_gap_m)
    idx = np.flatnonzero(ok)
    if len(idx):                           # off every ring vertex
        near_v, _ = STRtree(shapely.points(V)).query(shapely.points(foot[idx]),
                                                      predicate="dwithin",
                                                      distance=min_gap_m)
        idx = np.delete(idx, np.unique(near_v))
    if len(idx):                           # across the face, not around it
        poly = face if face is not None else Polygon(verts)
        inside = shapely.covers(poly.buffer(1e-6),
                                shapely.linestrings(np.stack([v[idx], foot[idx]], axis=1)))
        idx = idx[inside]
    taken: dict[tuple[int, int], list[tuple[float, float]]] = {}
    by_chord: dict[int, list[tuple[float, XY]]] = {}
    for k in idx[np.argsort(d[idx], kind="stable")]:
        fx, fy = float(foot[k, 0]), float(foot[k, 1])
        cx, cy = math.floor(fx / min_gap_m), math.floor(fy / min_gap_m)
        if any(math.hypot(fx - qx, fy - qy) < min_gap_m
               for i in (-1, 0, 1) for j in (-1, 0, 1)
               for qx, qy in taken.get((cx + i, cy + j), ())):
            continue
        if keep_off is not None and keep_off((fx, fy)):
            continue
        taken.setdefault((cx, cy), []).append((fx, fy))
        by_chord.setdefault(int(cj[k]), []).append((float(t[k]), (fx, fy)))
    if not by_chord:
        return list(ring)
    out: list[XY] = [pts[0]]
    for c in range(len(pts) - 1):
        out.extend(p for _s, p in sorted(by_chord.get(c, ())))
        out.append(pts[c + 1])
    return out
