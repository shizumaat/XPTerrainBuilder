"""``runway_crown``, ``runway_transverse`` and ``runway_end_skirt`` over
the emitted rings.

Crown (RULINGS 2026-08-05; v1 ``_check_runway_crown``): every
runway-family ring vertex carrying a published drop must sit at least
that far below the nearest ``crown_spine`` feature (interpolated along
it), less the instrument envelope; with nothing declared the ruleset's
crown minimum (``runway.transverse_min``) binds on runways against the
law's own axis.  Rows at a ``runway_crossing`` (or a node welded to one)
are OUT OF SCOPE (Annex 14 §3.1.19 "except at intersections").

Transverse maximum (RULINGS 2026-09-05o): a ``runway`` ring vertex
whose built fall under the nearest ``crown_spine`` exceeds
``runway.transverse_max × d`` by more than the instrument envelope — or
which rises above the spine by more than that — is a DEFECT row
(``reading = "transverse_max"``, family ``runway_transverse``, a
``verify.census.DEFECT_KEYS`` member): the hard generator states the
band, so a row can only come from a solver / emit defect.  Rows at a
``runway_crossing`` (or a node welded to one) are out of scope (§3.1.19)
and are not minted.

Vertical curve (RULINGS 2026-09-06b law 1): along each ``crown_spine``
feature (a runway's profile chain), the grade change between
consecutive chords over ``tables.runway_vertical_curve_bound`` by more
than the rate readers' quantum (``coarse_noise_m × (1/d₁ + 1/d₂)``) is a
DEFECT row (``reading = "vertical_curve"``, family
``runway_vertical_curve``, a ``DEFECT_KEYS`` member): the generator
states the same bound as a hard runway-tier row.  Stations are the
generator's own (``constraints.runway_profile.curve_stations``: the
identity floor drops slivers).

End skirt: rings with ``ref == runway_end_skirt`` — v2 emits none, so
the family is vacuous on v2's own product (the corridor ground is
``graded_strip``, bound by ``strips.py``).
"""
from __future__ import annotations

import math

from ..constraints.geometry import principal_axis
from ..constraints.runway_profile import curve_stations
from ..law.tables import runway_transverse_max, runway_vertical_curve_bound
from .frame import Patch, Row, noise_m, row
from .within import crown_by_vertex

__all__ = ["runway_crown", "runway_transverse", "runway_vertical_curve",
           "runway_end_skirt"]

FAMILY_TRANSVERSE = "runway_transverse"
FAMILY_VERTICAL_CURVE = "runway_vertical_curve"

RUNWAY_FAMILY = ("runway", "runway_crossing")


def _nearest_ridge(px: float, py: float, spines):
    """The vertex's PERPENDICULAR foot on its ridge chain and the lateral
    distance to it — INTERIOR feet only.  A vertex beyond a chain's end
    has no lateral distance: clamping it to the end point measures its
    ALONG-AXIS offset and reads the runway's longitudinal fall as a
    transverse one (SPLP, app 1.0.307–1.0.310: 29 "transverse" DEFECT rows
    at d = 229–340 m on a 45 m runway, every one −1.5156 % — the end
    zone's longitudinal grade — the first build whose runway followed the
    ground's trend instead of a straight chord; RULINGS 2026-09-10au).
    Such a vertex is the longitudinal / end-zone readers' business and
    is skipped here (``None``)."""
    best_d, best_z, best_pt = float("inf"), None, None
    for pts in spines:
        for i in range(len(pts) - 1):
            ax, ay, az = pts[i]
            bx, by, bz = pts[i + 1]
            vx, vy = bx - ax, by - ay
            l2 = vx * vx + vy * vy
            if l2 < 1e-12:
                continue
            t = ((px - ax) * vx + (py - ay) * vy) / l2
            if t < 0.0 or t > 1.0:
                continue                      # no perpendicular foot on this segment
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


def runway_transverse(p: Patch) -> list[Row]:
    """The transverse MAXIMUM read on the built surface (module docstring):
    ``|z_spine(foot) − z_v| > cap × d + noise`` on a ``runway`` ring
    vertex off any crossing is one DEFECT row."""
    law = p.law
    spines = [list(sh.closed_ring) for sh in p.features if sh.feature == "crown_spine"]
    if not spines:
        return []
    # THE ROW IS AGAINST THE VERTEX'S OWN RUNWAY (RULINGS 2026-09-05o, spec
    # ``runway-transverse-max-spec.md`` §3: "at lateral distance d on its OWN
    # ridge chain" — the generator's scope).  Reading the NEAREST spine of any
    # runway measured a 14L/32R edge against 14R/32L's crown 196 m away and
    # called the cross-fall between two runways a transverse defect (CYXY,
    # measured 2026-09-08: 2 of 2 DEFECT rows, up to 1.15 m, on pairs the
    # solve never states — the two instruments were not twins).  The nearest
    # spine remains the fallback where a runway ships no crown spine of its own.
    own: dict[str, list] = {}
    for sh in p.features:
        if sh.feature == "crown_spine" and sh.ref not in own:
            own[sh.ref] = [list(sh.closed_ring)]
    xing: set[int] = set()
    for sh in p.shapes:
        if sh.role == "runway_crossing":
            xing.update(sh.ids)
    out: list[Row] = []
    seen: set[int] = set()
    for sh in p.shapes:
        if sh.role != "runway":
            continue
        cap = runway_transverse_max(law, sh.code_letter, sh.code_number)
        if cap is None:
            continue
        noise = noise_m(law, sh.role)
        ridge = own.get(sh.ref, spines)
        for k, v in enumerate(sh.ids):
            if v in xing or v in seen:
                continue
            seen.add(v)
            x, y = sh.xy[k]
            dist, ridge_z, foot = _nearest_ridge(x, y, ridge)
            if ridge_z is None or dist <= 0.0:
                continue
            fall = ridge_z - sh.z[k]
            over = abs(fall) - cap * dist - noise
            if over <= 0.0:
                continue
            r = row(FAMILY_TRANSVERSE, (sh.role, sh.role), p.side(sh.role),
                    abs(fall), 100 * fall / dist, 100 * cap, dist,
                    (x, y), foot, sh.key, sh.key)
            r.update({"reading": "transverse_max", "face": sh.key,
                      "direction": "fall" if fall > 0.0 else "rise"})
            out.append(r)
    return out


def runway_vertical_curve(p: Patch) -> list[Row]:
    """The vertical-curve law read on the built ridge (module docstring):
    per interior station the change of grade against the bound at the
    mean spacing; a breach beyond the quantum is one DEFECT row."""
    law = p.law
    q = law.tables.emit.instrument.coarse_noise_m
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    code: dict[str, tuple[int | None, str | None]] = {}
    for sh in p.shapes:
        if sh.role == "runway" and sh.ref not in code:
            code[sh.ref] = (sh.code_number, sh.code_letter)
    out: list[Row] = []
    for sh in p.features:
        if sh.feature != "crown_spine" or len(sh.ids) < 3:
            continue
        cn, cl = code.get(sh.ref, (None, None))
        st = curve_stations(sh.xy, [list(range(len(sh.ids)))], lambda i: float(i), min_d)
        for a, b, c in zip(st, st[1:], st[2:]):
            d1 = math.dist(sh.xy[a], sh.xy[b])
            d2 = math.dist(sh.xy[b], sh.xy[c])
            if d1 <= 0.0 or d2 <= 0.0:
                continue
            bound = runway_vertical_curve_bound(law, 0.5 * (d1 + d2), cn, cl)
            if bound is None:
                continue
            change = (sh.z[c] - sh.z[b]) / d2 - (sh.z[b] - sh.z[a]) / d1
            allowed = bound + q * (1.0 / d1 + 1.0 / d2)
            if abs(change) <= allowed:
                continue
            span = 0.5 * (d1 + d2)
            r = row(FAMILY_VERTICAL_CURVE, ("runway", "runway"), p.side("runway"),
                    (abs(change) - bound) * span, 100 * change, 100 * bound, span,
                    sh.xy[a], sh.xy[c], sh.key, sh.key)
            r.update({"reading": "vertical_curve", "face": sh.ref,
                      "station": [round(v, 3) for v in sh.xy[b]]})
            out.append(r)
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
