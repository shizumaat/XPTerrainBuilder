"""A DUAL RAMP'S EDGES ARE ITS CARRIAGEWAYS' EDGES, STATION BY STATION
(#807; lane ``ltramp``, ``docs/findings/tunnel-ramps-ltramp.md``).

Two bores whose mouths stand within ``dual_carriageway_max_separation_m``
with parallel approaches are ONE ramp spanning both (2026-08-31h,
``structure_approach.merge_duals``).  ``merge_duals`` gives that ramp ONE
width — the widest span of the carriageways over the nominal ramp length
before they part (``_dual_span_m``) — and two carriageways that spread
apart cannot be held by one width: MEASURED KCLT's south ramp (two 2-lane
``tertiary`` carriageways into a roundabout, main 59fa7241d) stood
+5.3..+5.8 m beyond each carriageway's outer edge at its mouth, where they
run 8.8 m apart, and both carriageways left it in its last 10 m (−3.8 /
−2.9 m), where they run 25 m apart.  The owner: "A ramp should run along
its road's centreline at the road's full width."

THE RULE: per station, the ramp's half width on each side of the axis is
the farthest member carriageway's outer edge on that side — its lateral
offset from the axis plus its own half width — and never less than the
widest member's own half.  A station past the end of a member's mapped
approach does not read that member; a station no member reads keeps the
group's constant half.  This is the per-station ``half_fn`` the
pavement-traced ramp (2026-09-06b (2)) and the object corridors already
build with; a pavement tracing the road stays senior where it reads
(:func:`compose_half_fn`).  Where the per-station edges fold the ring at a
bend the caller keeps the one constant span (MEASURED LFPG: 2 of 18 duals,
``-27468…`` / ``-27470…``, fold; with one span both build as before).
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point

from ..model.frame import XY

__all__ = ["dual_half_fn", "compose_half_fn"]


def dual_half_fn(axis_fn: _t.Callable[[float], XY], members: _t.Sequence, half: float
                 ) -> _t.Callable[[float], tuple[float, float]] | None:
    """``s -> (left, right)`` half widths for a dual group's ramp along
    ``axis_fn`` (module doc), or ``None`` for a single carriageway."""
    routes = [(LineString(m.approach), float(m.width_m) / 2.0) for m in members
              if len(getattr(m, "approach", ()) or ()) >= 2]
    if len(routes) < 2:
        return None
    floor = max(h for _r, h in routes)
    memo: dict[float, tuple[float, float]] = {}

    def fn(s: float) -> tuple[float, float]:
        if s in memo:
            return memo[s]
        p = axis_fn(s)
        a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        nv = (-dy / L, dx / L)
        left = right = None
        for route, h in routes:
            t = route.project(Point(p))
            if t <= 0.0 or t >= route.length:
                continue                       # past this carriageway's mapped end
            q = route.interpolate(t)
            lat = (q.x - p[0]) * nv[0] + (q.y - p[1]) * nv[1]
            left = max(left if left is not None else -math.inf, lat + h)
            right = max(right if right is not None else -math.inf, h - lat)
        out = (half, half) if left is None else (max(left, floor), max(right, floor))
        memo[s] = out
        return out
    return fn


def compose_half_fn(pav_hw: dict, dual, half: float, base
                    ) -> _t.Callable[[float], tuple[float, float]] | None:
    """The ramp's ``half_fn``: the pavement tracing the road where it reads
    (``pav_hw``, 2026-09-06b (2)), else the dual's carriageways (``dual``),
    else the constant ``half``; ``base`` (the group's own) when neither
    reads anywhere."""
    if not pav_hw and dual is None:
        return base

    def fn(s: float) -> tuple[float, float]:
        got = pav_hw.get(s)
        if got is not None:
            return got
        return dual(s) if dual is not None else (half, half)
    return fn
