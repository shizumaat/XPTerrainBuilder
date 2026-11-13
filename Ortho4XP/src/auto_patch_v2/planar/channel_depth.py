"""§45 THE CHANNEL'S FLOOR, BANKS AND REACH FROM A VISIBLE CUT (#1918; owner
RULINGS 2026-11-06d (6), 21:40Z: "trench depth should be based on other
objects like bridges and structures that extend below the surrounding
grade").

Where a hidden cut shell stood over the corridor, the pack's statement of the
cut is what its VISIBLE frame members lying on it state
(``airport/visible_cut.VisibleCut.points``).  Read along the channel's axis,
station by station (``[channel] station_m``), each member's lowest point at a
station is its FOOT there ON EACH SIDE of the axis — a wall's or a pier's
base, a kerb footing, the toe of a bank liner.  The hidden shell's own floor
plates (``VisibleCut.extent``) say where the floor lies, never how deep: a foot
within ``shell_flat_m`` of the shell's floor level at its station stands on
the FLOOR, one over it on a LEDGE of the bank, one under it is BURIED and
states nothing (:func:`_classify`; spec ``object-gate-member-floors-20261113.md``
§4, the members' feet per side).  The feet give

* THE FLOOR PROFILE (§45 (3) (i), a profile and not one flat datum): the
  HIGHEST floor foot at each station (owner Q2, :data:`FLOOR_AT_HIGHEST_FOOT`:
  no wall floats), the level the structures in the cut stand on — the cut
  "to the wall depth" (2026-11-06d (4)); a ledge never sets it — linear
  between witnessed stations, the end values beyond them
  (:func:`_cut_profile`), and within ramp reach of an end where the
  corridor's way runs on, within ``ramp_max_grade`` of the ground it hands
  over to (:func:`rejoin`, §45 (16));
* THE FLOOR'S EDGE (§45 (10) (i)), PER SIDE: the farthest floor foot of that
  side plus ``[channel] foot_margin_m`` or the farthest floor-plate point of
  that side, never nearer than the wall band to that side's innermost
  ledge foot; and THE CREST: that ledge foot where the station has one —
  the crest is PINNED at the foot's height there (``Channel.ledge_pins``,
  2026-11-06d (6) with 2026-11-13i "no visible edge floating") — else the
  farthest below-grade member point (:func:`_cut_halves`);
* THE REACH (§45 (16)'s "extended by a depth witness"): the stations the
  members span (:func:`_cut_span`) — and the AXIS itself runs on along its
  way's own continuation (the next way of its kind, rail after rail, road
  after road, sharing its end node and turning least) while that stays
  inside the cut's bound and within the cap of a member
  (:func:`extend_axis`): a corridor does not stop where one OSM way does.

The floor's edge is enveloped over ``corridor_min_length_m``, the crest
enveloped and smoothed (a bank does not jump from one station to the next).
A member point farther than the corridor cap from the axis, or projecting
onto either end of it, is not this corridor's.  :class:`VisibleFloor` is the
one entry ``planar/channel.py`` reads through.  Nothing here names a pack or
an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString

__all__ = ["extend_axis", "rejoin", "VisibleFloor", "FLOOR", "LEDGE", "BELOW", "END", "UNMET",
           "FLOOR_AT_HIGHEST_FOOT"]

#: OWNER Q2 (spec ``object-gate-member-floors-20261113.md`` §9, RULINGS
#: 2026-11-13q (2) "Yes"): a station's floor is its HIGHEST floor foot (no
#: wall floats; the lower ones are buried by that much); ``False``: the median
FLOOR_AT_HIGHEST_FOOT = True
#: a foot's kind at its station (:func:`_classify`, :func:`_member_feet`)
FLOOR, LEDGE, BELOW, END, UNMET = "floor", "ledge", "below", "end", "unmet"
#: a continuation way turning more than this off the axis is a branch
_TURN_MAX_DEG = 45.0
#: end nodes this close are one node (the feed's own coordinates)
_NODE_M = 1.0


def _cut_points(cuts: _t.Sequence, axis_ln: LineString, cap: float) -> np.ndarray:
    """``(n, 6)``: every visible cut's points as ``(s, off, z, member, x,
    y)`` along ``axis_ln``, those within ``cap`` of it and between its ends.
    ``off`` is SIGNED, positive on the axis's left (the sense of
    ``channel_geometry._sides``); ``member`` counts on across the cuts (the
    index into :func:`_cut_members`)."""
    got, base = [], 0
    for c in cuts or ():
        if len(c.points):
            q = np.array(c.points, float)
            q[:, 3] += base
            got.append(q)
        base += max(len(getattr(c, "members", ()) or ()),
                    int(c.points[:, 3].max()) + 1 if len(c.points) else 0)
    if not got:
        return np.zeros((0, 6))
    p = np.concatenate(got)
    s, off, keep = _project(axis_ln, p[:, :2], cap)
    return np.column_stack([s[keep], off[keep], p[keep, 2], p[keep, 3], p[keep, 0],
                            p[keep, 1]])


def _cut_members(cuts: _t.Sequence) -> list[tuple[str, float]]:
    """``(placement id, authored zero)`` per member index of :func:`_cut_points`."""
    out: list[tuple[str, float]] = []
    for c in cuts or ():
        mem = list(getattr(c, "members", ()) or ())
        n = max(len(mem), int(c.points[:, 3].max()) + 1 if len(c.points) else 0)
        out += mem + [("", 0.0)] * (n - len(mem))
    return out


def _cut_extent(cuts: _t.Sequence, axis_ln: LineString, cap: float) -> np.ndarray:
    """``(m, 3)`` ``(s, off, z)``: the hidden shells' floor-plate points
    (``VisibleCut.extent``) projected as :func:`_cut_points`."""
    got = [np.asarray(c.extent, float) for c in cuts or ()
           if len(getattr(c, "extent", ()))]
    if not got:
        return np.zeros((0, 3))
    p = np.concatenate(got)
    s, off, keep = _project(axis_ln, p[:, :2], cap)
    return np.column_stack([s[keep], off[keep], p[keep, 2]])


def _project(axis_ln: LineString, xy: np.ndarray, cap: float):
    """``(s, signed off, keep)`` of the plan points ``xy`` along ``axis_ln``."""
    pts = shapely.points(xy[:, 0], xy[:, 1])
    s = shapely.line_locate_point(axis_ln, pts)
    a = shapely.get_coordinates(shapely.line_interpolate_point(axis_ln, np.maximum(s - 0.5, 0.0)))
    b = shapely.get_coordinates(shapely.line_interpolate_point(
        axis_ln, np.minimum(s + 0.5, axis_ln.length)))
    c = shapely.get_coordinates(shapely.line_interpolate_point(axis_ln, s))
    t = b - a
    side = np.sign(t[:, 0] * (xy[:, 1] - c[:, 1]) - t[:, 1] * (xy[:, 0] - c[:, 0]))
    off = shapely.distance(axis_ln, pts) * np.where(side < 0, -1.0, 1.0)
    keep = (np.abs(off) <= cap) & (s > 1e-6) & (s < axis_ln.length - 1e-6)
    return s, off, keep


def _cut_feet(points: np.ndarray, ss: _t.Sequence[float], step: float) -> list[np.ndarray]:
    """Per station of ``ss``: the feet — each member's lowest point within
    half a station of it, ON EACH SIDE of the axis (rows of
    :func:`_cut_points`)."""
    out = []
    for s in ss:
        q = points[np.abs(points[:, 0] - s) <= step / 2.0]
        if not len(q):
            out.append(np.zeros((0, points.shape[1])))
            continue
        key = q[:, 3] * 2.0 + (q[:, 1] >= 0.0)
        order = np.lexsort((q[:, 2], key))
        q, key = q[order], key[order]
        out.append(q[np.flatnonzero(np.r_[True, key[1:] != key[:-1]])])
    return out


def _shell_floor(extent: np.ndarray, ss: _t.Sequence[float], step: float) -> np.ndarray:
    """Per station the MEDIAN z of the shell's floor-plate points within
    half a station (its 60 m floor outweighs a ledge's plate); NaN where
    none."""
    out = np.full(len(ss), np.nan)
    for i, s in enumerate(ss):
        m = np.abs(extent[:, 0] - s) <= step / 2.0
        if m.any():
            out[i] = float(np.median(extent[m, 2]))
    return out


def _classify(feet: _t.Sequence[np.ndarray], level: "np.ndarray | None", flat: float
             ) -> list[np.ndarray]:
    """Per station each foot's kind: :data:`FLOOR` within ``flat`` of the
    shell's floor level there, :data:`LEDGE` over it, :data:`BELOW` under it
    (buried: states nothing).  A station with no floor level reads against
    its lowest foot (no foot is then below)."""
    out = []
    for i, f in enumerate(feet):
        if not len(f):
            out.append(np.zeros(0, dtype=object))
            continue
        lv = float(level[i]) if level is not None and np.isfinite(level[i]) else np.nan
        z = f[:, 2]
        if lv != lv:
            lv, lo = float(z.min()), -np.inf
        else:
            lo = lv - flat
        out.append(np.where(z > lv + flat, LEDGE, np.where(z < lo, BELOW, FLOOR)).astype(object))
    return out


def _cut_profile(feet: _t.Sequence[np.ndarray], ss: _t.Sequence[float],
                kinds: "_t.Sequence[np.ndarray] | None" = None, flat: float = 1.0
                ) -> tuple[tuple[float, float], ...] | None:
    """The floor ``(s, z)`` at every station of ``ss`` from its :data:`FLOOR`
    feet only (``kinds``; default: :func:`_classify` against the lowest
    foot): their maximum (:data:`FLOOR_AT_HIGHEST_FOOT`) or median, linear
    between stations, the end values beyond them; ``None`` where no station
    has a floor foot."""
    kinds = _classify(feet, None, flat) if kinds is None else kinds
    stat = np.max if FLOOR_AT_HIGHEST_FOOT else np.median
    got = [(float(s), float(stat(f[k == FLOOR, 2])))
           for s, f, k in zip(ss, feet, kinds, strict=True) if (k == FLOOR).any()]
    if not got:
        return None
    z = np.interp(np.asarray(ss, float), [s for s, _ in got], [v for _, v in got])
    return tuple((float(s), float(v)) for s, v in zip(ss, z, strict=True))


@_dc.dataclass
class _Side:
    """One side of a visible cut's corridor: the floor's edge and the
    crest (half-widths per station) and the crest's LEDGE PINS ``(s, off,
    z)`` — the stations where it runs through a ledge member's foot."""

    edge: np.ndarray
    crest: np.ndarray
    pins: list[tuple[float, float, float]]
    ledge: np.ndarray        # the innermost ledge foot's |off| per station (nan: none)


def _cut_halves(points: np.ndarray, feet: _t.Sequence[np.ndarray],
               kinds: _t.Sequence[np.ndarray], extent: np.ndarray, ss: _t.Sequence[float],
               profile, step: float, flat: float, floor_half: float, cap: float,
               band: float, window: float, margin: float) -> tuple[_Side, _Side]:
    """``(left, right)`` :class:`_Side` of the corridor (spec §4.2): the
    floor's edge the farthest FLOOR foot of that side plus ``margin``, or
    the farthest floor-plate point of that side within ``flat`` of the
    profile, whichever is farther, never under ``floor_half``, enveloped
    over ``window`` and never nearer than ``band`` to that side's innermost
    LEDGE foot; the crest that ledge foot where the station has one (a
    pin), else the farthest below-grade member point (today's reading)."""
    return tuple(_side(points, feet, kinds, extent, ss, profile, step, flat, floor_half, cap,
                       band, window, margin, sign) for sign in (1.0, -1.0))


def _side(points, feet, kinds, extent, ss, profile, step, flat, floor_half, cap, band,
          window, margin, sign) -> _Side:
    from scipy.ndimage import maximum_filter1d
    n = len(ss)
    edge_h, crest_h, ledge = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    ledge_z = np.full(n, np.nan)
    for i, ((s, z), f, k) in enumerate(zip(profile, feet, kinds, strict=True)):
        mine = (f[:, 1] * sign >= 0.0) if len(f) else np.zeros(0, bool)
        off = np.abs(f[:, 1]) if len(f) else np.zeros(0)
        cand = list(off[mine & (k == FLOOR)] + margin)
        m = (np.abs(extent[:, 0] - s) <= step / 2.0) & (extent[:, 1] * sign >= 0.0) \
            & (np.abs(extent[:, 2] - z) <= flat) if len(extent) else np.zeros(0, bool)
        if m.any():
            cand.append(float(np.abs(extent[m, 1]).max()))
        if cand:
            edge_h[i] = max(cand)
        lm = mine & (k == LEDGE)
        if lm.any():
            j = int(np.argmin(np.where(lm, off, np.inf)))
            ledge[i], ledge_z[i] = off[j], f[j, 2]
        pm = (np.abs(points[:, 0] - s) <= step) & (points[:, 1] * sign >= 0.0)
        if pm.any():
            crest_h[i] = float(np.abs(points[pm, 1]).max())
    w = max(1, int(round(window / max(step, 1e-6))))
    edge = maximum_filter1d(_fill(ss, edge_h, floor_half), w, mode="nearest")
    edge = np.maximum(np.minimum(edge, cap - band), floor_half)
    held = np.isfinite(ledge) & (ledge - band >= floor_half)
    edge = np.where(held, np.minimum(edge, ledge - band), edge)
    crest = _smooth(ss, [s for s, h in zip(ss, crest_h, strict=True) if h == h],
                    [h for h in crest_h if h == h], floor_half, step, window)
    crest = np.minimum(np.maximum(crest, edge + band), cap)
    crest = np.where(held, ledge, crest)
    pins = [(float(ss[i]), float(sign * ledge[i]), float(ledge_z[i]))
            for i in np.flatnonzero(held)]
    return _Side(edge, crest, pins, np.where(held, ledge, np.nan))


def _fill(ss, h: np.ndarray, floor: float) -> np.ndarray:
    """``h`` linear over its NaN stations, never under ``floor``."""
    ok = np.isfinite(h)
    if not ok.any():
        return np.full(len(ss), float(floor))
    x = np.asarray(ss, float)
    return np.maximum(np.interp(x, x[ok], h[ok]), floor)


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


def _member_feet(feet: _t.Sequence[np.ndarray], kinds: _t.Sequence[np.ndarray],
                sides: tuple[_Side, _Side], moved: np.ndarray,
                members: _t.Sequence[tuple[str, float]]) -> list[tuple]:
    """One record per member / side / station: ``(x, y, authored y,
    placement id, kind)`` — :data:`FLOOR` / :data:`LEDGE`, :data:`END` (a
    floor or ledge foot at a station ``rejoin`` moved) or :data:`UNMET` (a
    ledge foot beyond the side's innermost one, or a :data:`BELOW` foot)."""
    out = []
    for i, (f, k) in enumerate(zip(feet, kinds, strict=True)):
        for row, kind in zip(f, k, strict=True):
            side = sides[0] if row[1] >= 0.0 else sides[1]
            if kind == BELOW or (kind == LEDGE and not abs(abs(row[1]) - side.ledge[i]) < 1e-9):
                kind = UNMET
            elif moved[i]:
                kind = END
            pid, zero = members[int(row[3])] if int(row[3]) < len(members) else ("", 0.0)
            out.append((float(row[4]), float(row[5]), float(row[2]) - zero, pid, str(kind)))
    return out


class VisibleFloor:
    """The ONE entry ``planar/channel.py`` reads a visible cut through
    (spec §4.2): the points along the axis and their reach
    (:attr:`span`), then :meth:`profile` over the stations, then
    :meth:`sides` over the final (rejoined) profile."""

    def __init__(self, cuts: _t.Sequence, axis_ln: LineString, cap: float) -> None:
        self.points = _cut_points(cuts, axis_ln, cap)
        self.extent = _cut_extent(cuts, axis_ln, cap)
        self.members = _cut_members(cuts)
        self.span = _cut_span(self.points)
        self.feet = self.kinds = self.raw = None

    def profile(self, ss: _t.Sequence[float], step: float, flat: float):
        """The floor profile over ``ss`` (:func:`_cut_profile`), or ``None``."""
        if not len(self.points):
            return None
        self.ss, self.step, self.flat = list(ss), step, flat
        self.feet = _cut_feet(self.points, ss, step)
        lv = _shell_floor(self.extent, ss, step) if len(self.extent) else None
        self.kinds = _classify(self.feet, lv, flat)
        self.raw = _cut_profile(self.feet, ss, self.kinds, flat)
        return self.raw

    def sides(self, profile, axis_fn, floor_half: float, cap: float, band: float,
              window: float, margin: float):
        """``(left halves, right halves), (left crests, right crests),
        ledge pins (x, y, z), member feet`` over the final ``profile``."""
        ss = self.ss
        sides = _cut_halves(self.points, self.feet, self.kinds, self.extent, ss, profile,
                           self.step, self.flat, floor_half, cap, band, window, margin)
        moved = np.array([abs(a[1] - b[1]) > 0.01 for a, b in zip(self.raw, profile, strict=True)])
        pins = []
        for s, off, z in sides[0].pins + sides[1].pins:
            p = axis_fn(s)
            u = np.subtract(axis_fn(s + 1.0), axis_fn(max(0.0, s - 1.0)))
            u = u / (np.hypot(*u) or 1.0)
            pins.append((float(p[0] - u[1] * off), float(p[1] + u[0] * off), float(z)))
        feet = _member_feet(self.feet, self.kinds, sides, moved, self.members)
        return ((tuple(map(float, sides[0].edge)), tuple(map(float, sides[1].edge))),
                (tuple(map(float, sides[0].crest)), tuple(map(float, sides[1].crest))),
                tuple(pins), tuple(feet))


def _cut_span(points: np.ndarray) -> tuple[float, float] | None:
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
