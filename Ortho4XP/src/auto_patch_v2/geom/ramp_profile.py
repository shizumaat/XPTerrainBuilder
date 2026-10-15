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

__all__ = ["ramp_delta", "runout_profile"]


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
