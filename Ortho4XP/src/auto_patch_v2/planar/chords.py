"""Chord density — the ONE decimator (plan §1: chord density is a law
parameter applied once at planar-map build; memory
``two-decimators-mask-each-other``).

``densify`` inserts vertices so no chord exceeds the cap;
``stations`` lays the runway / spine profile stations at
``law.emit.chords.station_spacing_m`` along a breakline source.  Both are
pure functions over coordinate sequences; snapping to the identity grid
happens once, at noding (``overlay.py``).
"""
from __future__ import annotations

import math
import typing as _t

from ..model.frame import XY

__all__ = ["densify", "stations", "ring_lines"]


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
