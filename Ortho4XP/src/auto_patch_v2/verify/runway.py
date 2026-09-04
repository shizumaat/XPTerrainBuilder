"""``runway_crown`` and ``runway_end_skirt`` over the emitted rings.

Crown (RULINGS 2026-08-05; v1 ``_check_runway_crown``): every
runway-family ring vertex carrying a published drop must sit at least
that far below the nearest ``crown_spine`` feature (interpolated along
it), less the instrument envelope; with nothing declared the ruleset's
crown minimum (``runway.transverse_min``) binds on runways against the
law's own axis.  Rows at a ``runway_crossing`` (or a node welded to one)
are OUT OF SCOPE (Annex 14 §3.1.19 "except at intersections").

End skirt: rings with ``ref == runway_end_skirt`` — v2 emits none, so
the family is vacuous on v2's own product (the corridor ground is
``graded_strip``, bound by ``strips.py``).
"""
from __future__ import annotations

import math

from ..constraints.geometry import principal_axis
from .frame import Patch, Row, noise_m, row
from .within import crown_by_vertex

__all__ = ["runway_crown", "runway_end_skirt"]

RUNWAY_FAMILY = ("runway", "runway_crossing")


def _nearest_ridge(px: float, py: float, spines):
    best_d, best_z, best_pt = float("inf"), None, None
    for pts in spines:
        for i in range(len(pts) - 1):
            ax, ay, az = pts[i]
            bx, by, bz = pts[i + 1]
            vx, vy = bx - ax, by - ay
            l2 = vx * vx + vy * vy
            t = 0.0 if l2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / l2))
            qx, qy = ax + t * vx, ay + t * vy
            d = math.hypot(px - qx, py - qy)
            if d < best_d:
                best_d, best_z, best_pt = d, az + t * (bz - az), (qx, qy)
    return best_d, best_z, best_pt


def runway_crown(p: Patch) -> list[Row]:
    law = p.law
    drops = crown_by_vertex(p)
    spines = [list(sh.closed_ring) for sh in p.features if sh.feature == "crown_spine"]
    xing: set[int] = set()
    for sh in p.shapes:
        if sh.role == "runway_crossing":
            xing.update(sh.ids)
    axis_pts: dict[str, list] = {}
    for sh in p.shapes:
        if sh.role in RUNWAY_FAMILY:
            axis_pts.setdefault(sh.ref, []).extend(sh.xy)
    axes = {ref: principal_axis(pts) for ref, pts in axis_pts.items()}
    floor = law.ruleset.runway.transverse_min
    out: list[Row] = []
    for sh in p.shapes:
        if sh.role not in RUNWAY_FAMILY:
            continue
        declared = any(v in drops for v in sh.ids)
        noise = noise_m(law, sh.role)
        for k, v in enumerate(sh.ids):
            x, y = sh.xy[k]
            z = sh.z[k]
            dist, ridge_z, foot = _nearest_ridge(x, y, spines)
            if ridge_z is None:
                ax = axes.get(sh.ref)
                if ax:
                    (ax0, ay0), (ax1, ay1) = ax[0], ax[1]
                    vx, vy = ax1 - ax0, ay1 - ay0
                    l2 = vx * vx + vy * vy
                    t = ((x - ax0) * vx + (y - ay0) * vy) / l2 if l2 > 1e-12 else 0.0
                    foot = (ax0 + t * vx, ay0 + t * vy)
                    dist = math.hypot(x - foot[0], y - foot[1])
                else:
                    dist, foot = 0.0, (x, y)
                ridge_z, realised = z, 0.0
            else:
                realised = ridge_z - z
            required = float(drops.get(v, 0.0)) if declared else float(floor) * dist
            if required <= 0.0:
                continue
            short = required - realised - noise
            if short <= 0.0:
                continue
            span = max(dist, law.tables.emit.identity.min_distinct_spacing_m)
            out.append(row("runway_crown", (sh.role, sh.role), p.side(sh.role),
                           abs(realised), 100 * realised / span, None, dist,
                           (x, y), foot, sh.key, sh.key,
                           "runway_intersection" if (sh.role == "runway_crossing"
                                                     or v in xing) else None))
    return out


def runway_end_skirt(p: Patch) -> list[Row]:
    law = p.law
    cap = law.ruleset.end_skirt.max_down_grade
    noise = law.tables.emit.instrument.strip_edge_noise_m
    out: list[Row] = []
    for sh in p.shapes:
        if sh.ref != "runway_end_skirt":
            continue
        n = len(sh.ids)
        for i in range(n):
            j = (i + 1) % n
            (xa, ya), (xb, yb) = sh.xy[i], sh.xy[j]
            d = math.hypot(xb - xa, yb - ya)
            if d < 0.5:
                continue
            de = abs(sh.z[i] - sh.z[j])
            if de <= cap * d + noise:
                continue
            out.append(row("runway_end_skirt", (sh.role, sh.role), p.side(sh.role),
                           de, 100 * de / d, 100 * cap, d, sh.xy[i], sh.xy[j],
                           sh.key, sh.key))
    return out
