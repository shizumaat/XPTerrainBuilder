"""THE BODY'S LEVEL ON BARE GROUND (owner RULINGS 2026-09-11q, amended
2026-09-11x (2); spec ``object-placement-spec.md`` §11b (2)/(3)) — ONE
expression in the model because two layers read it and neither may
import the other: ``planar/group.derive`` (every foot, the group's own
``infeasible`` verdict) and ``constraints/foot_rows`` (the
GROUND-CONTACT subset, the target rows).

FEASIBILITY IS A SLOPE BETWEEN TWO FEET, NOT A SCALAR AT ONE (11x (2)).
Round 6 priced each foot's own residual against ``bank_slope`` x the
distance to its NEAREST other foot, which binds backwards: two feet
100 m apart bought 33 m of licence for a residual that is not shared
with them, and two feet 0.5 m apart refused 0.17 m that the sheet never
had to make between them.  What the terrain actually has to do is get
from one foot's target to its NEIGHBOUR's over the ground between them,
so the reading is per PAIR of neighbouring feet:

    |(target_a - target_b) - (dem_a - dem_b)| <= bank_slope x dist(a, b)

The level cancels out of that difference — a body's feasibility is a
property of its authored RELIEF against the ground's own fall, and the
level it is finally fitted at cannot change it.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

__all__ = ["GroundFit", "ground_fit", "neighbour_pairs"]

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
    goes with it (module doc) — ONE expression, two callers.

    ``level`` is the least-squares fit of ``dem(foot) - (y_foot -
    y_zero)`` over the feet — for one unknown that is exactly the MEAN,
    the level at which the authored relief sits closest to the ground it
    was authored over.

    ``residual_m`` is the worst NEIGHBOUR-PAIR residual ``|(target_a -
    target_b) - (dem_a - dem_b)|`` and ``limit_m`` the bank the terrain
    may lawfully make over that pair's own spacing (``bank_slope`` x
    ``dist(a, b)``); ``feasible`` is residual within limit on EVERY pair.
    A body whose authored relief matches the ground's fall is feasible at
    zero cost however steep both are; one that fights it is infeasible
    however gentle both are.
    """

    level: float
    residual_m: float
    limit_m: float
    feasible: bool
    #: index into the feet sequence of the foot whose pair binds (the
    #: ``a`` side of the worst neighbour pair)
    worst: int = -1
    #: the feet that carried a DEM sample, as indices into ``feet`` —
    #: ``targets`` and ``dem`` are over THESE, in this order
    keep: tuple[int, ...] = ()
    targets: tuple[float, ...] = ()
    dem: tuple[float, ...] = ()
    #: the binding pair as indices into ``feet`` (``(-1, -1)`` where
    #: there is no pair: one sampled foot, or no sample at all)
    worst_pair: tuple[int, int] = (-1, -1)


def neighbour_pairs(pts: _t.Sequence[tuple[float, float]]
                    ) -> list[tuple[int, int, float]]:
    """THE NEIGHBOUR GRAPH over feet in plan: ``(a, b, distance)`` for
    each edge of the feet's Euclidean MINIMUM SPANNING TREE.

    11x (2) allows "Delaunay or nearest-neighbour"; the EMST is the
    nearest-neighbour graph made CONNECTED — every foot's own nearest
    neighbour is an EMST edge, and the extra edges are exactly the ones
    that join otherwise separate clusters of feet (two columns' corner
    pairs, say), which a bare nearest-neighbour graph leaves untested
    and therefore always feasible.  It is a subgraph of the Delaunay
    triangulation, so no pair it reads is a pair the Delaunay would call
    non-adjacent.

    Pure Python, O(n^2) Prim — the feet of one body, never a corpus; and
    ``model`` may import neither ``scipy`` nor ``numpy`` (M0 §1).
    """
    n = len(pts)
    if n < 2:
        return []
    INF = float("inf")
    best = [INF] * n
    link = [-1] * n
    seen = [False] * n
    best[0] = 0.0
    out: list[tuple[int, int, float]] = []
    for _ in range(n):
        u, du = -1, INF
        for i in range(n):
            if not seen[i] and best[i] < du:
                u, du = i, best[i]
        if u < 0:
            break                      # unreachable: distances are finite
        seen[u] = True
        if link[u] >= 0:
            out.append((link[u], u, du))
        ux, uy = pts[u]
        for v in range(n):
            if seen[v]:
                continue
            vx, vy = pts[v]
            d = math.hypot(ux - vx, uy - vy)
            if d < best[v]:
                best[v], link[v] = d, u
    return out


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
        # reading) and there is no NEIGHBOUR to make a fall to
        return GroundFit(level, 0.0, 0.0, True, keep[0],
                         tuple(keep), tuple(targets), tuple(zs))
    ml, mo = _m_per_deg(sum(feet[i].lat for i in keep) / n)
    pts = [((feet[i].lon) * mo, (feet[i].lat) * ml) for i in keep]
    worst, worst_res, worst_lim, ok = -1, 0.0, 0.0, True
    worst_pair = (-1, -1)
    for a, b, d in neighbour_pairs(pts):
        # THE PAIR READING (11x (2)): the fall the sheet has to make
        # between these two feet, against the fall it is allowed over
        # the ground between them.  ``level`` cancels.
        res = abs((targets[a] - targets[b]) - (zs[a] - zs[b]))
        lim = bank_slope * d
        if res > lim:
            ok = False
        if worst < 0 or res > worst_res:
            # the first pair seeds the report, so a body whose relief
            # matches the ground EXACTLY still names the pair its bar
            # was read over (residual 0 against that pair's own limit)
            worst, worst_res, worst_lim = keep[a], res, lim
            worst_pair = (keep[a], keep[b])
    return GroundFit(level, worst_res, worst_lim, ok, worst,
                     tuple(keep), tuple(targets), tuple(zs), worst_pair)
