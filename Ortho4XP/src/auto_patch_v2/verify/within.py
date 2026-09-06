"""``within_shape`` / ``road_cross_section`` / ``plane_gradient`` over the
emitted rings — the v1 census's pair population re-read from the law
tables (``check_grade.iter_shape_grade_constraints`` +
``grade_law.classify_pair``, verify-side):

* PLANE shapes (runway family, taxi family, rigid pads, groundside):
  every vertex pair at the role cap; a ``runway`` ring (``o4_single_poly``)
  only same/adjacent-station pairs (``within_shape.runway_station_cluster_m``,
  user 2026-07-08); a TAXI-FAMILY ring crossed by published ``stretches``
  is priced per stretch exactly as the generator priced it
  (``constraints.stretches.compose_pairs``, RULINGS 2026-09-04t-3), and a
  pair with a pad vertex at the pad's cap (the frontage rule) — BOTH
  overlaid by the published ``taxi_route_pairs`` (RULINGS 2026-09-05ab):
  a published budget is the pair's allowance (``Σ cap·len`` over the
  centreline route, the reading the solve priced), a published null is
  no law edge (no route joins the pair: no row);
* SOFT shapes (apron, junction, service_junction, service_road): ring
  edges, spine chords (a published-axis vertex) and pad-frontage chords
  at the cap; an apron interior body chord within
  ``within_shape.apron_body_chord_max_m`` at ``common.apron_fan_ramp_max``;
* JUNCTION BODIES (``within_shape.junction_mesh_roles``, RULINGS
  2026-09-04y) with published ``mesh_edges``: the population is the ring
  edges, the published mesh edges and the common-stretch pairs — a
  common-stretch pair at that stretch's cap, every other member at the
  cap of the crossing stretch nearest its midpoint
  (``stretches.nearest_line_cap``), a pad endpoint at the pad's cap; a
  chord in none of the three classes produces no row.  A patch without
  ``mesh_edges`` (pre-04y) reads the all-pairs superset as before;
* every pair re-centred on the published ``crown_drops`` (2026-08-05)
  and forgiven the role's instrument envelope;
* a road-family pair at or beyond ``common.road_transverse_axis_min_deg``
  off the ring's long axis is the CROSS-SECTION (2026-08-25g), priced
  at the transverse cap into ``road_cross_section``;
* ``plane_gradient``: a THREE-vertex ring's plane gradient vs its cap
  (user 2026-07-05).
"""
from __future__ import annotations

import itertools
import math

from ..constraints.geometry import long_axis, pair_is_transverse, station_indices
from ..constraints.stretches import compose_pairs, nearest_line_cap
from ..law.tables import role_cap
from .frame import Patch, Row, Shape, noise_m, row

__all__ = ["within_shape", "plane_gradient", "crown_by_vertex"]


def crown_by_vertex(p: Patch) -> dict[int, float]:
    """Published crown drops joined to vertices by identity key."""
    out: dict[int, float] = {}
    key_of = {(round(la, 7), round(lo, 7)): vid for vid, (la, lo) in p.ll.items()}
    for entry in p.publication.get("crown_drops") or []:
        vid = key_of.get((round(float(entry[0]), 7), round(float(entry[1]), 7)))
        if vid is not None:
            out[vid] = float(entry[2])
    return out


def spine_vertices(p: Patch) -> set[int]:
    """Vertices on a published (non-service) axis — spine membership."""
    key_of = {(round(la, 7), round(lo, 7)): vid for vid, (la, lo) in p.ll.items()}
    out: set[int] = set()
    for entry in p.publication.get("axes") or []:
        if len(entry) > 4 and entry[4]:
            continue
        for la, lo in entry[0]:
            vid = key_of.get((round(float(la), 7), round(float(lo), 7)))
            if vid is not None:
                out.add(vid)
    return out


def stretch_lines(p: Patch) -> list[tuple[tuple[int, ...], float]]:
    """Published stretches joined to vertices by identity key:
    ``(vertex chain, cap)`` each (a vertex the patch lacks is skipped)."""
    key_of = {(round(la, 7), round(lo, 7)): vid for vid, (la, lo) in p.ll.items()}
    out: list[tuple[tuple[int, ...], float]] = []
    for entry in p.publication.get("stretches") or []:
        ids = tuple(v for v in (key_of.get((round(float(la), 7), round(float(lo), 7)))
                                for la, lo in entry[0]) if v is not None)
        if len(ids) >= 2:
            out.append((ids, float(entry[1])))
    return out


def crossing_stretches(sh: Shape, lines: list[tuple[tuple[int, ...], float]]
                       ) -> list[tuple[tuple[int, ...], float]]:
    """The published stretches crossing ``sh``: those with an edge on its
    ring (two consecutive stretch vertices both on the ring)."""
    ring = set(sh.ids)
    return [(ch, c) for ch, c in lines
            if any(u in ring and w in ring for u, w in zip(ch, ch[1:]))]


def stretch_pair_caps(sh: Shape, lines: list[tuple[tuple[int, ...], float]],
                      xy_all: dict[int, tuple[float, float]], cap: float,
                      min_d: float, common_only: bool = False
                      ) -> dict[tuple[int, int], float]:
    """The per-stretch cap of every pair of ``sh`` (``common_only``: of
    the pairs sharing a stretch, the junction-body reading)."""
    crossing = crossing_stretches(sh, lines)
    if not crossing:
        return {}
    xy = {v: sh.xy[k] for k, v in enumerate(sh.ids)}
    for ch, _c in crossing:
        for v in ch:
            xy.setdefault(v, xy_all[v])
    return {(a, b): c for a, b, c, _d in
            compose_pairs(xy, list(sh.ids), crossing, cap, min_d, common_only)}


def route_pair_budgets(p: Patch) -> dict[tuple[int, int], tuple[float, float] | None]:
    """Published ``taxi_route_pairs`` joined to vertices by identity key:
    ``(min, max) -> (budget, dist)``, or ``None`` for a pair no route
    joins (RULINGS 2026-09-05ab)."""
    pub = p.publication.get("taxi_route_pairs")
    if not pub:
        return {}
    key_of = {(round(la, 7), round(lo, 7)): vid for vid, (la, lo) in p.ll.items()}
    out: dict[tuple[int, int], tuple[float, float] | None] = {}
    for a, b, budget, dist in pub:
        va = key_of.get((round(float(a[0]), 7), round(float(a[1]), 7)))
        vb = key_of.get((round(float(b[0]), 7), round(float(b[1]), 7)))
        if va is None or vb is None or va == vb:
            continue
        out[(min(va, vb), max(va, vb))] = None if budget is None else (float(budget), float(dist))
    return out


def mesh_pairs(p: Patch) -> set[tuple[int, int]] | None:
    """Published ``mesh_edges`` joined to vertices by identity key, as
    ``(min, max)`` pairs; ``None`` when the patch publishes none."""
    pub = p.publication.get("mesh_edges")
    if pub is None:
        return None
    key_of = {(round(la, 7), round(lo, 7)): vid for vid, (la, lo) in p.ll.items()}
    out: set[tuple[int, int]] = set()
    for a, b in pub:
        va = key_of.get((round(float(a[0]), 7), round(float(a[1]), 7)))
        vb = key_of.get((round(float(b[0]), 7), round(float(b[1]), 7)))
        if va is not None and vb is not None and va != vb:
            out.add((min(va, vb), max(va, vb)))
    return out


def junction_pair_caps(sh: Shape, lines: list[tuple[tuple[int, ...], float]],
                       xy_all: dict[int, tuple[float, float]], cap: float,
                       min_d: float, mesh: set[tuple[int, int]]
                       ) -> dict[tuple[int, int], float]:
    """THE JUNCTION-BODY POPULATION (RULINGS 2026-09-04y): ring edges,
    published mesh edges and common-stretch pairs with their caps; a pair
    absent from the result is not a law edge."""
    out = stretch_pair_caps(sh, lines, xy_all, cap, min_d, common_only=True)
    crossing = [([xy_all[v] for v in ch], c) for ch, c in crossing_stretches(sh, lines)]
    n = len(sh.ids)
    xy = {v: sh.xy[k] for k, v in enumerate(sh.ids)}
    for i in range(n):
        a, b = sh.ids[i], sh.ids[(i + 1) % n]
        mesh = mesh | {(min(a, b), max(a, b))}
    for a, b in mesh:
        if a not in xy or b not in xy:
            continue
        key = (min(a, b), max(a, b))
        if key in out or (key[1], key[0]) in out:
            continue
        (ax, ay), (bx, by) = xy[a], xy[b]
        out[key] = nearest_line_cap((0.5 * (ax + bx), 0.5 * (ay + by)), crossing, cap)
    return out


def _offset(drops: dict[int, float], a: int, b: int, dz: float) -> float:
    """``crown_pair_offset_clamped``: the target of ``z_a − z_b``."""
    da, db = drops.get(a), drops.get(b)
    if da is not None and db is not None:
        return db - da
    if da is None and db is None:
        return 0.0
    t = (0.0 - da) if da is not None else (db - 0.0)
    if abs(t) <= 1e-9:
        return 0.0
    lo, hi = min(0.0, t), max(0.0, t)
    return lo if dz < lo else (hi if dz > hi else dz)


def within_shape(p: Patch) -> tuple[list[Row], list[Row]]:
    """``(within_shape rows, road_cross_section rows)``."""
    law = p.law
    ws = law.tables.emit.within_shape
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    fan = law.tables.common.apron_fan_ramp_max
    min_deg = law.tables.common.road_transverse_axis_min_deg
    roads = set(law.tables.families["road_cross_section"].roles)
    soft = {"apron", "junction", "service_junction", "service_road"}
    drops = crown_by_vertex(p)
    spine = spine_vertices(p)
    lines = stretch_lines(p)
    taxi = set(law.tables.precedence.taxi_family.members)
    pad_cap = law.tables.common.roles["building"].longitudinal
    mesh_roles = set(ws.junction_mesh_roles)
    mesh = mesh_pairs(p)
    routed = route_pair_budgets(p)
    rigid_v: set[int] = set()
    for sh in p.shapes:
        if p.is_rigid(sh.role):
            rigid_v.update(sh.ids)
    # THE FRAME'S WHOLE VERTEX MAP, never the outer rings alone: a stretch
    # chain runs through hole-ring vertices too (a taxi centreline entering
    # a gap-interior ring — LEMD face 145 / taxi660, 2026-09-05), exactly
    # as the generator prices it through ``pm.vertices``.
    xy_all = p.xy
    within: list[Row] = []
    xsec: list[Row] = []
    for sh in p.shapes:
        cap = p.cap(sh)
        if cap is None:
            continue
        meshed = sh.role in mesh_roles and mesh is not None
        if meshed:
            pc = junction_pair_caps(sh, lines, xy_all, cap, min_d, mesh)
        else:
            pc = stretch_pair_caps(sh, lines, xy_all, cap, min_d) if sh.role in taxi else {}
        rc = role_cap(law, sh.role, sh.code_number, sh.code_letter)
        cap_t = min(cap, rc.transverse) if rc else cap
        q = noise_m(law, sh.role)
        n = len(sh.ids)
        if n < 3:
            continue
        st = station_indices(sh.xy, ws.runway_station_cluster_m) \
            if sh.single_poly else None
        axis = None
        if sh.role in roads:
            ax = long_axis(sh.xy)
            axis = ax[0] if ax else None
        strict = spine | rigid_v
        for i in range(n):
            a = sh.ids[i]
            for j in range(i + 1, n):
                b = sh.ids[j]
                (xa, ya), (xb, yb) = sh.xy[i], sh.xy[j]
                d = math.hypot(xa - xb, ya - yb)
                if d < min_d:
                    continue
                if st is not None and abs(st[i] - st[j]) > 1:
                    continue
                adjacent = (j == i + 1) or (i == 0 and j == n - 1)
                if meshed and (a, b) not in pc and (b, a) not in pc:
                    continue                       # not a law edge (04y)
                pair_cap = pc.get((a, b), pc.get((b, a), cap))
                route = None
                if sh.role in taxi:
                    if a in rigid_v or b in rigid_v:
                        pair_cap = min(pair_cap, pad_cap)      # frontage (09-01g)
                    key = (min(a, b), max(a, b))
                    if key in routed:
                        route = routed[key]
                        if route is None:
                            continue                   # no route: no law edge (05ab)
                if sh.role in soft and not adjacent and a not in strict \
                        and b not in strict:
                    if sh.role == "apron":
                        if d > ws.apron_body_chord_max_m:
                            continue
                        # strict inside the body gate (owner 2026-08-24);
                        # ``fan`` is the back-edge zones' cap (none modelled)
                        pair_cap = cap
                transverse = axis is not None and pair_is_transverse(
                    axis, xb - xa, yb - ya, min_deg)
                if transverse:
                    pair_cap = min(pair_cap, cap_t)
                dz = sh.z[i] - sh.z[j]
                de = abs(dz - _offset(drops, a, b, dz))
                if route is not None:                  # the route reading (05ab)
                    budget, d = route
                    pair_cap = budget / d
                allowance = pair_cap * d + q
                if de <= allowance:
                    continue
                grade = de / d
                r = row("road_cross_section" if transverse else "within_shape",
                        (sh.role, sh.role), p.side(sh.role), de, 100 * grade,
                        100 * pair_cap, d, sh.xy[i], sh.xy[j], sh.key, sh.key,
                        lat=0.5 * (p.ll[a][0] + p.ll[b][0]),
                        lon=0.5 * (p.ll[a][1] + p.ll[b][1]))
                (xsec if transverse else within).append(r)
    return within, xsec


def plane_gradient(p: Patch) -> list[Row]:
    """Three-vertex rings: plane gradient vs cap in crown-lifted space,
    the v1 reader's arithmetic exactly (``check_grade.plane_reading``):
    an UNDECLARED vertex is unknown, not on the ridge (judged under both
    ends of ``[0, max declared drop]``), and the allowance carries the
    PLANE-FIT ROUNDING ENVELOPE ``(q/2)·Σ 1/h_i`` — the 0.01 m emit
    quantum on an identity-spacing sliver is a grade by itself (12 of 15
    rows across SPJC/OTHH/LEMD, 2026-09-04)."""
    law = p.law
    drops = crown_by_vertex(p)
    noise = law.tables.emit.instrument.rounding_noise_m
    half_q = 0.5 * law.tables.emit.materiality.elevation_m
    out: list[Row] = []
    for sh in p.shapes:
        cap = p.cap(sh)
        if cap is None or len(sh.ids) != 3:
            continue
        pts = [(sh.xy[k][0], sh.xy[k][1], sh.z[k]) for k in range(3)]
        declared = [drops.get(sh.ids[k]) for k in range(3)]
        reading = _plane_reading(pts, declared, cap, noise, half_q)
        if reading is None:
            continue
        grad, dist, de, lo_pt, hi_pt = reading
        out.append(row("plane_gradient", (sh.role, sh.role), p.side(sh.role), de,
                       100 * grad, 100 * cap, dist if dist > 0.5 else 1.0,
                       lo_pt[:2], hi_pt[:2], sh.key, sh.key))
    return out


def plane_fit_noise(pts: list[tuple[float, float, float]]) -> float:
    """``Σ_i 1/h_i`` over the triangle's three altitudes (0 if degenerate):
    the rounding radius times this bounds the fitted gradient's error."""
    (x1, y1, _), (x2, y2, _), (x3, y3, _) = pts
    area2 = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1))
    if area2 < 1e-9:
        return 0.0
    total = 0.0
    for (ax, ay), (bx, by) in (((x2, y2), (x3, y3)), ((x1, y1), (x3, y3)),
                               ((x1, y1), (x2, y2))):
        edge = math.hypot(bx - ax, by - ay)
        if edge < 1e-9:
            return 0.0
        total += edge / area2
    return total


def _plane_reading(pts, drops, cap: float, noise: float, half_q: float):
    known = [d for d in drops if d is not None]
    top = max(known) if known else 0.0
    choices = [[float(d)] if d is not None else ([0.0, float(top)] if known else [0.0])
               for d in drops]
    fit_noise = plane_fit_noise(pts) * half_q
    best = None
    for lift in itertools.product(*choices):
        lifted = [(x, y, z + dz) for (x, y, z), dz in zip(pts, lift)]
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = lifted
        ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
        vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        if abs(nz) < 1e-6:
            return None
        gx, gy = -nx / nz, -ny / nz
        grad = math.hypot(gx, gy)
        if grad < 1e-9:
            return None
        ghx, ghy = gx / grad, gy / grad
        proj = sorted((q[0] * ghx + q[1] * ghy, q[2], q) for q in lifted)
        dist = proj[-1][0] - proj[0][0]
        de = abs(proj[-1][1] - proj[0][1])
        allowance = cap * dist + noise + fit_noise * dist
        if de <= allowance:
            return None
        excess = de - allowance
        if best is None or excess < best[0]:
            best = (excess, (grad, dist, de, proj[0][2], proj[-1][2]))
    return None if best is None else best[1]
