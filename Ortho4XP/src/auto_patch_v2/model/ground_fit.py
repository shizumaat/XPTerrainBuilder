"""THE BODY'S LEVEL ON BARE GROUND (owner RULINGS 2026-09-11q; spec
``object-placement-spec.md`` §11b (2)/(3)) — ONE expression in the model
because two layers read it and neither may import the other:
``planar/group.derive`` (every foot, the group's own ``infeasible``
verdict) and ``constraints/foot_rows`` (the GROUND-CONTACT subset, the
target rows).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

__all__ = ["GroundFit", "ground_fit"]

#: metres per degree of latitude — the plane reading a body's feet are
#: compared in (they span tens of metres, never a projection's worth)
_M_PER_DEG_LAT = 111_132.0


def _m_per_deg(lat: float) -> tuple[float, float]:
    return _M_PER_DEG_LAT, _M_PER_DEG_LAT * math.cos(math.radians(lat))


class Foot(_t.Protocol):
    """What the fit needs of a ground contact: where it stands and the
    ``y`` it is authored at (``planar/group.Foot``)."""

    lat: float
    lon: float
    y: float


@_dc.dataclass(frozen=True)
class GroundFit:
    """THE BODY'S LEVEL ON BARE GROUND, and the feasibility verdict that
    goes with it (owner RULINGS 2026-09-11q; spec ``object-placement-
    spec.md`` §11b (2)/(3)) — ONE expression, two callers:
    ``planar/group.derive`` (every foot, the group's own verdict) and
    ``constraints/foot_rows.py`` (the GROUND-CONTACT subset, the rows).

    ``level`` is the least-squares fit of ``dem(foot) - (y_foot -
    y_zero)`` over the feet — for one unknown that is exactly the MEAN,
    the level at which the authored relief sits closest to the ground it
    was authored over.  ``residual_m`` is ``max |dem(foot) - target|``,
    ``limit_m`` the bank the terrain may lawfully make to meet it
    (``bank_slope`` x the distance to the nearest OTHER foot: the fall
    has to happen between two contacts, and the nearest one is the
    shortest run it has).  ``feasible`` is residual within limit at EVERY
    foot: a body whose authored relief matches the ground's fall is
    feasible at zero cost, one that fights it is not."""

    level: float
    residual_m: float
    limit_m: float
    feasible: bool
    #: index into the feet sequence of the foot whose residual binds
    worst: int = -1
    #: the feet that carried a DEM sample, as indices into ``feet`` —
    #: ``targets`` and ``dem`` are over THESE, in this order
    keep: tuple[int, ...] = ()
    targets: tuple[float, ...] = ()
    dem: tuple[float, ...] = ()


def ground_fit(feet: _t.Sequence[Foot], y_zero: float,
               dem_at: _t.Callable[[float, float], float | None],
               bank_slope: float) -> GroundFit | None:
    """:class:`GroundFit` over ``feet``, or ``None`` when the DEM has no
    sample under them (nothing to fit, and no verdict to give)."""
    if not feet:
        return None
    zs: list[float] = []
    offs: list[float] = []
    keep: list[int] = []
    for i, f in enumerate(feet):
        z = dem_at(f.lat, f.lon)
        if z is None:
            continue
        keep.append(i)
        zs.append(float(z))
        offs.append(float(f.y) - float(y_zero))
    if not keep:
        return None
    level = sum(z - o for z, o in zip(zs, offs)) / float(len(keep))
    targets = [level + o for o in offs]
    n = len(keep)
    if n == 1:
        # ONE foot: the fit is exact by construction (one unknown, one
        # reading) and there is no "nearest other foot" to bank over
        return GroundFit(level, 0.0, 0.0, True, keep[0],
                         tuple(keep), tuple(targets), tuple(zs))
    ml, mo = _m_per_deg(sum(feet[i].lat for i in keep) / n)
    worst, worst_res, worst_lim, ok = -1, 0.0, 0.0, True
    for a in range(n):
        fa = feet[keep[a]]
        nn = min(math.hypot((fa.lat - feet[keep[b]].lat) * ml,
                            (fa.lon - feet[keep[b]].lon) * mo)
                 for b in range(n) if b != a)
        res = abs(zs[a] - targets[a])
        lim = bank_slope * nn
        if res > lim:
            ok = False
        if res > worst_res:
            worst, worst_res, worst_lim = keep[a], res, lim
    return GroundFit(level, worst_res, worst_lim, ok, worst,
                     tuple(keep), tuple(targets), tuple(zs))
