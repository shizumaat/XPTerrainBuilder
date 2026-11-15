"""THE FRONT FLOOR AND THE LATERAL FIT (#2062 spec R3b C, amended R4
C′ + F; owner RULINGS 2026-11-06c (5) applied to an entrance face's wings;
owner 2026-11-15T04:08Z Q1: "expose the whole headwall the object models
(trimmed at airside pavement) for face_front_m in front of it").

An entrance face states its FRONT WALL's two ends across the bore
(``Portal.front_xy``, ``airport/entrance_front``).  A walled ramp's TARGET
half widths are the front's (:func:`front_halves`: the hull of every pin the
group's mouth object faces, as ``mouth_opening.group_opening`` hulls their
openings) for the stations within ``[tunnel.object] face_front_m`` of the
mouth, the opening's beyond -- one square step, at stations protected at
``face_front_m`` and one grid step past it.

THE ONE LATERAL FIT (:func:`lateral_fit`, R4): per side and per station the
half width is the target cut back to stand clear of whatever stands beside
the corridor, never below the mapped road's own half width (at the mouth and
inside the pack's walls never below the opening's).  The fit probes the ring
the clip loop builds, with the clip loop's own hit test; a stop that still
hits at the minimum stands ACROSS the floor and is left to the loop (carry,
clip, refuse), unchanged.  The fit never refuses a mouth and never shortens
a ramp.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import bisect
import math
import typing as _t

from shapely.geometry import Point
from shapely.ops import nearest_points

from .mouth_opening import axis_left_normal, opening_halves

__all__ = ["front_halves", "halves_fn", "lateral_fit"]

XY = tuple[float, float]
Halves = tuple[float, float]

#: the fit's iteration cap (R4 (3)); at the cap the opening's halves stand
FIT_CAP = 400


def front_halves(axis, pins: _t.Sequence[_t.Any]) -> "Halves | None":
    """``(left, right)`` half widths spanning the hull, across ``axis``
    (mouth first), of every pin's ``front_xy``, or ``None``."""
    edges = [tuple(e) for p in pins for e in (getattr(p, "front_xy", ()) or ())]
    if len(edges) < 2 or len(axis.coords) < 2:
        return None
    m = axis.coords[0]
    nv = axis_left_normal(axis)
    offs = sorted(((e[0] - m[0]) * nv[0] + (e[1] - m[1]) * nv[1], e) for e in edges)
    return opening_halves(axis, (offs[0][1], offs[-1][1]))


def halves_fn(table: _t.Mapping[float, Halves]) -> _t.Callable[[float], Halves]:
    """The half-width function of a per-station ``table``: exact at its
    stations, linear between them, the end values beyond."""
    ks = sorted(table)

    def fn(s: float) -> Halves:
        i = bisect.bisect_left(ks, s - 1e-9)
        if i < len(ks) and abs(ks[i] - s) <= 1e-9:
            return table[ks[i]]
        if i <= 0:
            return table[ks[0]]
        if i >= len(ks):
            return table[ks[-1]]
        a, b = ks[i - 1], ks[i]
        t = (s - a) / (b - a)
        la, ra = table[a]
        lb, rb = table[b]
        return (la + t * (lb - la), ra + t * (rb - ra))
    return fn


def _side_and_reach(axis_fn, axis, part) -> "tuple[int, float, float, float]":
    """``(side, d, s0, s1)`` of a stop's ``part``: its side of the axis
    (0 left, 1 right), its least across distance ``d`` from the axis and
    the station span it stands beside."""
    pa, pp = nearest_points(axis, part)
    s = axis.project(pa)
    a, b = axis_fn(max(0.0, s - 0.5)), axis_fn(s + 0.5)
    tx, ty = b[0] - a[0], b[1] - a[1]
    L = math.hypot(tx, ty) or 1.0
    nx, ny = -ty / L, tx / L
    side = 0 if (pp.x - pa.x) * nx + (pp.y - pa.y) * ny >= 0.0 else 1
    ss = [axis.project(Point(q)) for g in getattr(part, "geoms", (part,))
          for q in (g.exterior.coords if hasattr(g, "exterior") else g.coords)]
    return side, float(axis.distance(part)), min(ss), max(ss)


def _fit_halves(ss: _t.Sequence[float], target: _t.Callable[[float], Halves],
               minimum: _t.Callable[[float], Halves],
               probe_of: _t.Callable[[_t.Callable[[float], Halves]], _t.Any],
               hit_of: _t.Callable[[_t.Any], "str | None"],
               part_of: _t.Callable[[str, _t.Any], _t.Any],
               axis_fn, axis, rim_off: float, gap: float, grid: float, spacing: float,
               fallback: Halves) -> tuple[dict[float, Halves], list[str]]:
    """``(per-station halves, notes)`` (module doc; R4 C′ + F).

    ``probe_of(half_fn)`` is the clip loop's probe of the ring built with
    ``half_fn`` (``None`` where no ring stands); ``hit_of(probe)`` its hit
    test (the stop's ref or ``None``); ``part_of(ref, probe)`` the stop's
    part within ``gap`` of the probe.  A hit whose least across distance is
    within ``minimum + rim_off + gap + grid`` is a REAL stop: the fit returns
    and the loop takes it.  Otherwise that side is cut, at the stations
    within one ``spacing`` of the stop's span, to the grid floor of
    ``d - rim_off - gap - grid`` (a stop still hit after that -- the ring's
    snap to the grid -- one grid step further each time), never below
    ``minimum``."""
    cur = {float(s): tuple(map(float, target(s))) for s in ss}
    notes: list[str] = []
    #: per (stop, side): the last width it was cut to -- a stop still hit
    #: there (the ring's grid snap) is cut one grid step further
    last: dict[tuple[str, int], float] = {}
    for _it in range(FIT_CAP):
        probe = probe_of(halves_fn(cur))
        if probe is None:
            return cur, notes
        ref = hit_of(probe)
        if ref is None:
            return cur, notes
        part = part_of(ref, probe)
        if part is None or part.is_empty:
            return cur, notes
        side, d, s0, s1 = _side_and_reach(axis_fn, axis, part)
        near = [s for s in cur if s0 - spacing - 1e-9 <= s <= s1 + spacing + 1e-9]
        floor = max([minimum(s)[side] for s in near] or [minimum(s0)[side]])
        if d <= floor + rim_off + gap + grid + 1e-9:
            notes.append(f"{ref} stands across the floor (least across {d:.2f} m): "
                         "the clip loop takes it")
            return cur, notes
        want = math.floor((d - rim_off - gap - grid) / grid + 1e-9) * grid
        if (ref, side) in last:
            want = min(want, last[(ref, side)] - grid)
        last[(ref, side)] = want
        moved = False
        for s in near:
            h = list(cur[s])
            new = max(minimum(s)[side], min(h[side], want))
            if new < h[side] - 1e-9:
                h[side], moved = new, True
                cur[s] = (h[0], h[1])
        if not moved:
            notes.append(f"{ref}: no station left to fit (least across {d:.2f} m)")
            return cur, notes
        notes.append(f"{ref}: {'left' if side == 0 else 'right'} side to {want:.1f} m "
                     f"for s {s0:.1f}-{s1:.1f}")
    notes.append(f"fit cap {FIT_CAP} reached: the opening's halves stand")
    return {float(s): tuple(fallback) for s in ss}, notes


def lateral_fit(ss: _t.Sequence[float], span: Halves, front: "Halves | None",
                face_front: float, taper: float, road_half: float, walls_to: float,
                probe_of, pad_hit, stops: _t.Sequence, exclude: set,
                carry, axis_fn, axis, rim_off: float, gap: float, grid: float,
                spacing: float) -> tuple[dict[float, Halves], list[str]]:
    """:func:`_fit_halves` for one mapped ramp of ``planar/structures``: the
    target is ``front`` within ``face_front`` of the mouth, tapering 1:1 to
    the opening's ``span`` over ``taper`` metres (a square step folds the
    rim's stand-off, ``structure_geometry._clear``); the minimum the road's
    own half width (the opening's at the mouth and inside the walls,
    ``walls_to``; #1917, #1938 S2).  ``pad_hit(probe, exclude=...)`` is the
    clip loop's hit test; a stop ``carry(ref, probe, stops)`` carries (E′1)
    is no side to fit."""
    from .ramp_carry import carried_part
    excl = set(exclude)

    def target(s: float) -> Halves:
        if front is None or s >= face_front + taper - 1e-9:
            return span
        t = max(0.0, (s - face_front) / taper)
        return (front[0] + t * (span[0] - front[0]), front[1] + t * (span[1] - front[1]))

    def minimum(s: float) -> Halves:
        if s <= 1e-9 or s <= walls_to + 1e-9:
            return span
        return (min(road_half, span[0]), min(road_half, span[1]))

    def hit_of(pr):
        while True:
            ref = pad_hit(pr, exclude=excl)
            if ref is None or carry is None or not carry(ref, pr, stops)[0]:
                return ref
            excl.add(ref)

    return _fit_halves(ss, target, minimum, probe_of, hit_of,
                      lambda ref, pr: carried_part(ref, pr, stops, gap), axis_fn, axis,
                      rim_off, gap, grid, spacing, span)
