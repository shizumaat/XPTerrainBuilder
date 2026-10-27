"""THE ROAD-GRADE RAMP PROFILE — how a road leaves a level it must start
at (a pad's rim, an object ramp's foot) and comes back to its ground.

ONE law, three readers: the pad road's ramp off a pad rim
(``constraints/pad_ramp``, RULINGS 2026-10-13a), the run-out off an object
ramp's graded foot (``constraints/ramp_runout``, 14c (5)), and the run-out
off a viaduct LANDING (``planar/landing_runout``, #711) — the last one in
the planar stage, below the constraints layer, which is why the profile
lives here and ``constraints/pad_ramp`` re-exports :func:`ramp_delta`.
"""
from __future__ import annotations

import typing as _t

__all__ = ["ramp_delta", "runout_profile", "lead_section", "strip_level", "axis_ground"]


def ramp_delta(dv: float, zr: float, dr: float, g: float, d: float) -> float:
    """The ramp's rise from its leader at level ``zr`` (ground ``dr``) to a
    vertex ``d`` along the road over ground ``dv``, at the design grade
    ``g``.  Two profiles leave the leader: toward the ground never past it
    (the level-ground ramp), and closing the leader's own offset over its
    ground (the ramp on a slope falling away, which the first never brings
    down) — the road takes the one nearer its ground."""
    toward = max(-g * d, min(g * d, dv - zr))
    off = zr - dr
    left = max(0.0, abs(off) - g * d)
    closing = dv + (left if off > 0.0 else -left) - zr
    return min((toward, closing), key=lambda t: (abs(zr + t - dv), t))


def runout_profile(z0: float, dem_at: _t.Callable[[float], float], g: float,
                   cap: float, max_run_m: float, step_m: float = 1.0,
                   meet_m: float = 0.05) -> list[tuple[float, float]]:
    """THE RUN-OUT'S LONG SECTION: ``[(s, z)]`` from ``s = 0`` (level
    ``z0``) every ``step_m`` until the profile meets its ground (within
    ``meet_m``) or ``max_run_m``.  ``dem_at(s)`` is the raw ground along the
    run.  The design profile is :func:`ramp_delta` at grade ``g`` off the
    start; it never falls or climbs faster than ``cap`` per metre (the
    road's own longitudinal cap) — where the terrain falls away beside a
    design-grade closing that would pass the cap, the run lengthens instead."""
    d0 = float(dem_at(0.0))
    out = [(0.0, float(z0))]
    s, z = 0.0, float(z0)
    while s < max_run_m:
        s = min(max_run_m, s + step_m)
        dv = float(dem_at(s))
        t = z0 + ramp_delta(dv, z0, d0, g, s)
        lo, hi = z - cap * step_m, z + cap * step_m
        z = min(hi, max(lo, t))
        out.append((s, z))
        if abs(z - dv) <= meet_m:
            break
    return out


def axis_ground(dem, x0: float, y0: float, dx: float, dy: float
                ) -> _t.Callable[[float], float]:
    """``s -> `` the raw ground on a run-out's axis ``s`` metres along its
    travel from ``(x0, y0)``."""
    def at(s: float) -> float:
        return float(dem.z(x0 + dx * s, y0 + dy * s))
    return at


def lead_section(pts: _t.Iterable[tuple[float, float]], bin_m: float = 1.0
                 ) -> list[tuple[float, float]]:
    """THE LEAD's long section ``[(s, z)]``: the standing points of a mapped
    road beside a run-out strip, ``s`` along the strip's travel, one mean
    level per ``bin_m`` station, sorted."""
    acc: dict[int, list[tuple[float, float]]] = {}
    for s, z in pts:
        acc.setdefault(int(round(s / bin_m)), []).append((float(s), float(z)))
    return [(sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v))
            for _k, v in sorted(acc.items())]


def strip_level(s: float, z0: float, d0: float, dem_at: _t.Callable[[float], float],
                g: float, lead: _t.Sequence[tuple[float, float]] = ()) -> float:
    """A RUN-OUT STRIP's level ``s`` metres along its travel (issues #669 /
    #1093).  Beside a LEAD — the mapped road that carries the foot's run-out
    (RULINGS 2026-10-14i), standing when the strip is solved — the strip is
    that road's shoulder: the lead's level at ``s`` (linear between its
    stations), and past the lead's last station the ramp law continued off
    it.  With no lead (fewer than two stations): :func:`ramp_delta` off the
    strip's start ``z0`` over its ground ``d0`` (14c (5)).  ``dem_at(s)`` is
    the raw ground on the strip's axis.  MEASURED (KCLT, lane lramp2): the
    strips beside the departures roadway held their DEM-closing profile while
    the road between them ran straight to a junction 2.3 m over the DEM —
    1.5-2.3 m relaxed at the strip's end, and an open edge there."""
    if len(lead) >= 2 and s >= lead[0][0]:
        if s <= lead[-1][0]:
            for (s0, a), (s1, b) in zip(lead, lead[1:], strict=False):
                if s <= s1:
                    return a if s1 <= s0 else a + (b - a) * (s - s0) / (s1 - s0)
        s1, z1 = lead[-1]
        return z1 + ramp_delta(float(dem_at(s)), z1, float(dem_at(s1)), g, s - s1)
    return z0 + ramp_delta(float(dem_at(s)), z0, d0, g, s)
