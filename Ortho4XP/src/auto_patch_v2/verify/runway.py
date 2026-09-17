"""``runway_crown``, ``runway_transverse`` and ``runway_end_skirt`` over
the emitted rings.

THE POPULATION (lane ``rwyholes``, the RULINGS 2026-09-13dd chip): both
readers below price EVERY vertex of a runway-family face — its outer ring
AND its hole rings, ``Shape.vertex_ids`` = ``model.planar.face_vertex_ids``,
the accessor the generator's ``View.face_vertices`` reads through — so the
verifier and the generator count one vertex set (v2roles HECA: 490 hole
vertices on 8 of 33 runway faces were declared nothing and read by nobody).

Crown (RULINGS 2026-08-05; v1 ``_check_runway_crown``): every
runway-family face vertex carrying a published drop must sit at least
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
from ..law.tables import (cliff_grade, runway_transverse_cap,
                          runway_vertical_curve_bound)
from .frame import Patch, Row, noise_m, row
from .steps import _edges, _step_rows
from .within import crown_by_vertex

__all__ = ["runway_crown", "runway_transverse", "runway_vertical_curve",
           "runway_end_skirt", "runway_step"]

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
            xing.update(sh.vertex_ids)
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
        # THE FACE'S VERTEX SET (lane ``rwyholes``): outer AND hole rings,
        # the population the generator's ``crown_drops`` declares
        declared = any(v in drops for v in sh.vertex_ids)
        noise = noise_m(law, sh.role)
        for v in sh.vertex_ids:
            x, y = p.xy[v]
            z = p.z[v]
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
            xing.update(sh.vertex_ids)
    out: list[Row] = []
    seen: set[int] = set()
    # §40 (2) as amended (owner RULINGS 2026-09-13dd): each runway's own
    # half width, published by the solve (``pipeline.publication``'s
    # ``runway_axes``) — beyond it the vertex is a SHOULDER vertex and the
    # cap is the shoulder's, through the ONE accessor the generator prices
    # at.  A patch predating §40 carries no key: every vertex then reads
    # the runway cap, exactly as before.
    half_of = {str(r[0]): float(r[5])
               for r in (p.publication.get("runway_axes") or []) if len(r) >= 6}
    for sh in p.shapes:
        if sh.role != "runway":
            continue
        half = half_of.get(sh.ref, 0.0)
        noise = noise_m(law, sh.role)
        ridge = own.get(sh.ref, spines)
        # outer AND hole rings — the generator's population (``rwyholes``)
        for v in sh.vertex_ids:
            if v in xing or v in seen:
                continue
            seen.add(v)
            x, y = p.xy[v]
            dist, ridge_z, foot = _nearest_ridge(x, y, ridge)
            if ridge_z is None or dist <= 0.0:
                continue
            cap = runway_transverse_cap(law, dist, half, sh.code_letter,
                                        sh.code_number)
            if cap is None:
                continue
            fall = ridge_z - p.z[v]
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


def runway_step(p: Patch) -> list[Row]:
    """§40 (5) (4) A STEP BETWEEN TWO FACES OF THE RUNWAY FAMILY IS A
    DEFECT (Fable 2026-09-15; owner RULINGS 2026-09-15az) — family
    ``runway_step``, a ``verify.census.DEFECT_KEYS`` member.

    THE HOLE IT CLOSES.  ``runway_transverse`` is the CROWN reading: it
    judges a vertex against the runway's own AXIS at its lateral offset,
    so a pair of vertices 490 m off-axis is not a crown pair and the
    family never sees it.  No other DEFECT family prices a step between
    two faces of ONE role.  MEASURED (lane ``v2lemdstruct2`` r5): LEMD
    40.4613609,-3.5446852 steps **0.950 m over 1 m** between two faces of
    the same ``runway`` role, on rolled-on pavement, and the census saw
    it only as ``mid_edge_step`` — a REPORT family with no axis notion —
    while every DEFECT family read ZERO.

    THE READING is the step readers' own (:func:`steps._step_rows`, with
    its ``roles`` and ``allow_of`` options, never a second copy): each
    ring vertex and each edge midpoint of a runway-family face against
    the nearest edge of ANOTHER runway-family face inside the contact
    tolerance.  THE ALLOWANCE is the runway's own law over the geometry
    between them — ``runway_transverse_cap(d, half_width) x d``, the ONE
    reading the generator and ``tools/check_grade`` price through —
    floored at ``materiality.runway_step_m`` (0.10 m), because a WELDED
    pair has d ~ 0 and a cap over zero metres forgives everything.  The
    cap beyond the runway's own half width is the SHOULDER's (§40 (2)),
    which is exactly the pair this family exists for.

    Declared terrace joints are forgiven as in every step reader; a pair
    at a ``runway_crossing`` is NOT exempt here (Annex 14 §3.1.19 exempts
    the CROSS-FALL at an intersection, not a step in the surface).

    THE SPAN RULE AND THE CLIFF ESCAPE (owner RULINGS 2026-09-12ad /
    12af, ruled for this family 2026-09-16; lane ``v2hecastep``).  This
    family prices a WALL between runway-role faces, and its floor exists
    because a WELDED pair has d ~ 0.  A pair with a SPAN — d > 0 — whose
    implied grade ``|dz| / d`` is under the ruleset's own cliff line
    (:func:`law.tables.cliff_grade`, the design surface's 1:3 bank,
    imported and never re-spelled) is a SLOPE, not a discontinuity: it
    stays a census row and is REPORTED, never a DEFECT.  At or over the
    cliff line it is a cut or a rise and stays a DEFECT whatever d.
    The reading is published on the row itself, in the terms the gate
    already prices (``verify.census.defect_excess_m``): a SLOPE row
    states its own grade against the cliff line as its cap, so its
    excess is zero and ``defect_gate`` files it under the floor; a CLIFF
    row states neither, so its whole magnitude is the excess, exactly as
    before.  MEASURED at HECA (app 1.0.344's four rows): the three face
    37 rows read 187 % / 126 % / 188 % and stay DEFECTs; the survivor at
    30.1076486,-31.4083338 reads 17 % over 0.992 m between two faces
    that SHARE vertex 1748 — a continuous surface — and becomes REPORT.
    §40 (5) (3)'s band LEVEL rows are NOT minted (v2shoulderband r3/r4
    measured that hardening a runway row set over-determines the sheet)."""
    law = p.law
    floor = float(law.tables.emit.materiality.runway_step_m)
    ins = law.tables.emit.instrument
    half_of: dict[str, float] = {}
    for sh in p.shapes:
        if sh.role in RUNWAY_FAMILY:
            half_of.setdefault(sh.ref, 0.0)
    # the runway's own half width, read off the emitted rings' principal
    # axis (the census frame has no apt.dat): the largest perpendicular
    # offset of a ``runway`` face's vertices from its own axis
    for sh in p.shapes:
        if sh.role != "runway" or not sh.xy:
            continue
        ax = principal_axis(list(sh.xy))
        if not ax:
            continue
        (ox, oy), (ux, uy) = ax[0], ax[1]
        far = max(abs(-(x - ox) * uy + (y - oy) * ux) for x, y in sh.xy)
        half_of[sh.ref] = max(half_of.get(sh.ref, 0.0), far)
    letter = {sh.ref: sh.code_letter for sh in p.shapes if sh.role in RUNWAY_FAMILY}
    number = {sh.ref: sh.code_number for sh in p.shapes if sh.role in RUNWAY_FAMILY}
    half = max(half_of.values(), default=0.0)
    ref = max(half_of, key=lambda r: half_of[r], default=None) if half_of else None
    cap = runway_transverse_cap(law, half + 1.0, half,
                                letter.get(ref), number.get(ref)) if ref else None

    def allow_of(d: float) -> float:
        return max(floor, (cap or 0.0) * d)

    edges = _edges(p)
    probes = [(sh, sh.xy[k], sh.z[k]) for sh in p.shapes
              if sh.role in RUNWAY_FAMILY for k in range(len(sh.ids))]
    probes += [(sh, (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1])), 0.5 * (za + zb))
               for sh, a, b, za, zb in edges if sh.role in RUNWAY_FAMILY]
    rows = _step_rows(p, "runway_step", probes, edges, ins.edge_search_m,
                      ins.step_contact_tol_m, floor, roles=RUNWAY_FAMILY,
                      allow_of=allow_of)
    return [_span_rule(r, cliff_grade(law)) for r in rows]


def _span_rule(r: Row, cliff: float) -> Row:
    """The 12ad / 12af reading of one ``runway_step`` row (see
    :func:`runway_step`): a SPANNED pair under the cliff line is a
    SLOPE — it states its grade and the cliff line as its cap, so the
    gate prices zero excess and REPORTS it; anything else is a CLIFF and
    keeps its magnitude as its excess."""
    d = float(r.get("distance_m") or 0.0)
    mag = abs(float(r.get("magnitude_m") or 0.0))
    if d > 0.0 and cliff > 0.0 and mag / d < cliff:
        r.update({"reading": "slope", "grade_pct": 100.0 * mag / d,
                  "cap_pct": 100.0 * cliff})
    else:
        r["reading"] = "cliff"
    return r
