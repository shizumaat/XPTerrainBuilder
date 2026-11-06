"""§45 THE CHANNEL'S FLOOR, BANKS AND REACH FROM A VISIBLE CUT (#1918; owner
RULINGS 2026-11-06d (6), 21:40Z: "trench depth should be based on other
objects like bridges and structures that extend below the surrounding
grade").

Where a hidden cut shell stood over the corridor, the pack's statement of the
cut is what its VISIBLE frame members lying on it state
(``airport/visible_cut.VisibleCut.points``).  Read along the channel's axis,
station by station (``[channel] station_m``), each member's lowest point at a
station is its FOOT there — a wall's or a pier's base, a kerb footing, the
toe of a bank liner.  The feet give

* THE FLOOR PROFILE (§45 (3) (i), a profile and not one flat datum): the
  MEDIAN of the members' feet at each station, the level the structures in
  the cut stand on — the cut "to the wall depth" (2026-11-06d (4)) — linear
  between witnessed stations, the end values beyond them
  (:func:`cut_profile`), and within ramp reach of an end where the
  corridor's way runs on, within ``ramp_max_grade`` of the ground it hands
  over to (:func:`rejoin`, §45 (16));
* THE FLOOR'S EDGE (§45 (10) (i), the corridor's half-width): the farthest
  foot from the axis standing on that floor (within ``shell_flat_m`` of it —
  a tree on the bank top is no floor edge); and THE CREST: the farthest
  below-grade member point — a bank liner's top edge — so the bank the mesh
  triangulates between them lies where the pack drew it (:func:`cut_halves`);
* THE REACH (§45 (16)'s "extended by a depth witness"): the stations the
  members span (:func:`cut_span`) — and the AXIS itself runs on along its
  way's own continuation (the next way of its kind, rail after rail, road
  after road, sharing its end node and turning least) while that stays
  inside the cut's bound and within the cap of a member
  (:func:`extend_axis`): a corridor does not stop where one OSM way does.

Both half-widths are enveloped and smoothed over ``corridor_min_length_m``
(a bank does not jump from one station to the next).  A member point farther
than the corridor cap from the axis, or projecting onto either end of it, is
not this corridor's.  Nothing here names a pack or an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString

__all__ = ["cut_points", "cut_feet", "cut_profile", "cut_halves", "cut_span",
           "extend_axis", "rejoin"]

#: a continuation way turning more than this off the axis is a branch
_TURN_MAX_DEG = 45.0
#: end nodes this close are one node (the feed's own coordinates)
_NODE_M = 1.0


def cut_points(cuts: _t.Sequence, axis_ln: LineString, cap: float) -> np.ndarray:
    """``(n, 4)``: every visible cut's points as ``(s, off, z, member)``
    along ``axis_ln``, those within ``cap`` of it and between its ends."""
    got = [c.points for c in cuts or () if len(c.points)]
    if not got:
        return np.zeros((0, 4))
    p = np.concatenate(got)
    pts = shapely.points(p[:, 0], p[:, 1])
    s = shapely.line_locate_point(axis_ln, pts)
    off = shapely.distance(axis_ln, pts)
    keep = (off <= cap) & (s > 1e-6) & (s < axis_ln.length - 1e-6)
    return np.column_stack([s[keep], off[keep], p[keep, 2], p[keep, 3]])


def cut_feet(points: np.ndarray, ss: _t.Sequence[float], step: float) -> list[np.ndarray]:
    """Per station of ``ss``: the ``(m, 3)`` feet ``(s, off, z)`` — each
    member's lowest point within half a station of it."""
    out = []
    for s in ss:
        q = points[np.abs(points[:, 0] - s) <= step / 2.0]
        if not len(q):
            out.append(np.zeros((0, 3)))
            continue
        q = q[np.lexsort((q[:, 2], q[:, 3]))]
        first = np.flatnonzero(np.r_[True, q[1:, 3] != q[:-1, 3]])
        out.append(q[first, :3])
    return out


def cut_profile(feet: _t.Sequence[np.ndarray], ss: _t.Sequence[float]
                ) -> tuple[tuple[float, float], ...] | None:
    """The floor ``(s, z)`` at every station of ``ss`` (module doc), or
    ``None`` where no station has a foot."""
    got = [(float(s), float(np.median(f[:, 2]))) for s, f in zip(ss, feet, strict=True)
           if len(f)]
    if not got:
        return None
    z = np.interp(np.asarray(ss, float), [s for s, _ in got], [v for _, v in got])
    return tuple((float(s), float(v)) for s, v in zip(ss, z, strict=True))


def cut_halves(points: np.ndarray, feet: _t.Sequence[np.ndarray], ss: _t.Sequence[float],
               profile, step: float, flat: float, floor_half: float, cap: float,
               band: float, window: float) -> tuple[list[float], list[float]]:
    """``(floor edge, crest)`` half-widths at every station of ``ss``
    (module doc); the floor never under ``floor_half`` (the road's own),
    the crest at least ``band`` beyond the floor, both under ``cap``."""
    edge_s, edge_h, crest_s, crest_h = [], [], [], []
    for (s, z), f in zip(profile, feet, strict=True):
        on = f[f[:, 2] <= z + flat] if len(f) else f
        if len(on):
            edge_s.append(s)
            edge_h.append(float(on[:, 1].max()))
        m = np.abs(points[:, 0] - s) <= step
        if m.any():
            crest_s.append(s)
            crest_h.append(float(points[m, 1].max()))
    edge = _smooth(ss, edge_s, edge_h, floor_half, step, window)
    crest = _smooth(ss, crest_s, crest_h, floor_half, step, window)
    edge = np.minimum(edge, cap - band)
    crest = np.minimum(np.maximum(crest, edge + band), cap)
    return [float(v) for v in edge], [float(v) for v in crest]


def _smooth(ss, got_s, got_h, floor: float, step: float, window: float) -> np.ndarray:
    """The half-widths ``got_h`` at ``got_s`` over every station: linear
    between, enveloped then averaged over ``window``, never under ``floor``."""
    if not got_s:
        return np.full(len(ss), float(floor))
    from scipy.ndimage import maximum_filter1d, uniform_filter1d
    h = np.maximum(np.interp(np.asarray(ss, float), got_s, got_h), floor)
    n = max(1, int(round(window / max(step, 1e-6))))
    return np.maximum(uniform_filter1d(maximum_filter1d(h, n, mode="nearest"), n,
                                       mode="nearest"), floor)


def cut_span(points: np.ndarray) -> tuple[float, float] | None:
    """The stations the members span along the axis, or ``None``."""
    return (float(points[:, 0].min()), float(points[:, 0].max())) if len(points) else None


def extend_axis(line: LineString, ways: _t.Sequence, cuts: _t.Sequence, cap: float,
                kind: _t.Callable[[object], str]) -> tuple[LineString, list[int]]:
    """``(axis, way ids)``: ``line`` run on at both ends along its
    continuation (module doc); ``kind(way)`` names a way's kind (``""`` for
    none), the lead's kind being that of the way whose geometry IS ``line``.
    Unchanged where no visible cut bounds the corridor."""
    live = [c for c in cuts or () if c.bound is not None and len(c.points)]
    if not live:
        return line, []
    from shapely.ops import unary_union
    bound = unary_union([c.bound for c in live]).buffer(_NODE_M)
    pts = np.concatenate([c.points for c in live])
    near = shapely.points(pts[:, 0], pts[:, 1])
    coords = [tuple(p) for p in line.coords]
    lead = next((w for w in ways if list(map(tuple, w.points)) in (coords, coords[::-1])),
                None)
    want = kind(lead) if lead is not None else ""
    if not want:
        return line, []
    pool = [w for w in ways if w is not lead and kind(w) == want and len(w.points) >= 2]
    used: list[int] = []
    for end in (1, 0):
        while True:
            nxt = _next_way(coords, end, pool, used)
            if nxt is None:
                break
            w, seg = nxt
            run = LineString(seg)
            if not bound.contains(run) or float(shapely.distance(run, near).min()) > cap:
                break
            used.append(int(w.id))
            coords = coords + seg[1:] if end else seg[::-1][:-1] + coords
    return LineString(coords), used


def _next_way(coords: list, end: int, pool: _t.Sequence, used: list[int]):
    """The way continuing ``coords`` at its ``end`` (1 = last point) with
    the least turn, oriented away from it, or ``None``."""
    p, q = (coords[-1], coords[-2]) if end else (coords[0], coords[1])
    u = np.subtract(p, q)
    u = u / (np.hypot(*u) or 1.0)
    best = None
    for w in pool:
        if int(w.id) in used:
            continue
        seg = [tuple(c) for c in w.points]
        if np.hypot(*np.subtract(seg[-1], p)) <= _NODE_M:
            seg = seg[::-1]
        elif np.hypot(*np.subtract(seg[0], p)) > _NODE_M:
            continue
        v = np.subtract(seg[1], seg[0])
        v = v / (np.hypot(*v) or 1.0)
        turn = float(np.degrees(np.arccos(np.clip(np.dot(u, v), -1.0, 1.0))))
        if turn <= _TURN_MAX_DEG and (best is None or turn < best[0]):
            best = (turn, w, seg)
    return None if best is None else (best[1], best[2])


def rejoin(profile: tuple[tuple[float, float], ...], length: float,
           ground_at: _t.Callable[[float], float], grade: float, run_on: float
           ) -> tuple[tuple[float, float], ...]:
    """§45 (16) "beyond the ends §37 governs and the floor rejoins the road's
    own profile at ≤ ``ramp_max_grade``": where the axis runs on at least
    ``run_on`` past an end of the profile (the corridor's way continues
    outside), the floor
    within ramp reach of that end stays within ``grade`` of the ground
    there — the road it hands over to.  An end that is the axis's own end
    hands over to nothing and is left as the members state it."""
    out = list(profile)
    for k, beyond in ((0, profile[0][0] >= run_on), (-1, profile[-1][0] <= length - run_on)):
        g = ground_at(profile[k][0]) if beyond else float("nan")
        if g != g:
            continue
        s_end = profile[k][0]
        out = [(s, min(max(z, g - grade * abs(s - s_end)), g + grade * abs(s - s_end)))
               for s, z in out]
    return tuple((float(s), float(z)) for s, z in out)
