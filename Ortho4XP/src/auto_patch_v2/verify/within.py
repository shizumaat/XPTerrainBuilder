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
  an APRON CHORD ONLY WHEN IT STAYS INSIDE ITS FACE (RULINGS
  2026-09-05ae(1): the ring with its holes at the snap tolerance,
  ``constraints.geometry.face_cover`` — the generator's own gate); a
  chord across a hole or the exterior is no law edge;
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

from ..constraints.geometry import (chords_covered, face_cover, long_axis,
                                    pair_is_transverse, station_indices)
from ..constraints.roads import NO_FRAME, NOT_A_PAIR, road_pair_reading
from ..constraints.stretches import AxisIndex, compose_pairs, nearest_line_cap
from ..constraints.taxi import short_pairs
from ..law.tables import role_cap, snap_margin_m
from .frame import Patch, Row, Shape, noise_m, row
from .steps import joint_index

__all__ = ["apron_over_preference", "within_shape", "plane_gradient", "crown_by_vertex", "taxi_box",
           "FAMILY_TAXI_BOX", "published_axis_index"]

FAMILY_TAXI_BOX = "taxi_box"


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


def road_frames(p: Patch) -> dict[int, tuple[int, float, float]]:
    """§37 (7) the published ``road_route_frame`` joined to vertices by
    identity key (owner RULINGS 2026-09-13av): vertex -> ``(route, s, t)``.
    Empty on a patch that publishes none — the chord law."""
    pub = p.publication.get("road_route_frame")
    if not pub:
        return {}
    key_of = {(round(la, 7), round(lo, 7)): vid for vid, (la, lo) in p.ll.items()}
    out: dict[int, tuple[int, float, float]] = {}
    for rec in pub:
        v = key_of.get((round(float(rec[0]), 7), round(float(rec[1]), 7)))
        if v is not None:
            out[v] = (int(rec[2]), float(rec[3]), float(rec[4]))
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


def chords_outside_face(p: Patch, sh: Shape, min_d: float) -> set[tuple[int, int]]:
    """The index pairs of ``sh``'s NON-ADJACENT chords that leave the face
    (its ring with its hole features, ``face_cover`` at the snap
    tolerance) — RULINGS 2026-09-05ae(1); empty for a degenerate face."""
    holes = [f.xy for f in p.features if f.feature == "gap_interior_ring" and f.host == sh.key]
    cover = face_cover(sh.xy, holes, snap_margin_m(p.law))
    if cover is None:
        return set()
    n = len(sh.xy)
    pairs: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            (xa, ya), (xb, yb) = sh.xy[i], sh.xy[j]
            if math.hypot(xa - xb, ya - yb) >= min_d:
                pairs.append((i, j))
    ok = chords_covered(cover, [(sh.xy[i], sh.xy[j]) for i, j in pairs])
    return {pr for pr, k in zip(pairs, ok) if not k}


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
    rframe = road_frames(p)          # §37 (7)
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
    joints = joint_index(p)      # APRON TERRACE LOCKSTEP (06n / 07g): the declared step across a joint
    for sh in p.shapes:
        cap = p.cap(sh)
        if cap is None:
            continue
        meshed = sh.role in mesh_roles and mesh is not None
        if meshed:
            pc = junction_pair_caps(sh, lines, xy_all, cap, min_d, mesh)
        else:
            pc = stretch_pair_caps(sh, lines, xy_all, cap, min_d) if sh.role in taxi else {}
        # §37 (1): the lateral-contiguity binding is the TRANSVERSE cap
        # (``Patch.cap_t``); ``cap`` above is the role's own longitudinal
        cap_t = p.cap_t(sh)
        if cap_t is None:
            cap_t = cap
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
        outside = chords_outside_face(p, sh, min_d) if sh.role == "apron" else set()
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
                if (i, j) in outside:
                    continue                       # a chord leaving its face (05ae-1)
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
                # §37 (7) A ROAD PAIR IS PRICED ALONG THE ROUTE (owner
                # RULINGS 2026-09-13av): the generator's own reading,
                # imported — never a second spelling of the rule here.
                road_read = None
                if sh.role in roads and rframe:
                    road_read = road_pair_reading(cap, min(cap_t, cap), min_deg,
                                                  rframe.get(a), rframe.get(b), d)
                if road_read == NOT_A_PAIR:
                    if not adjacent:
                        continue            # a switchback's two branches
                    road_read = NO_FRAME
                if road_read not in (None, NO_FRAME):
                    bound, transverse = road_read
                    pair_cap = bound / d
                else:
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
                if joints:
                    allowance += joints.allowance(sh.xy[i], sh.xy[j])
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


def apron_over_preference(p: Patch) -> dict:
    """THE APRON PREFERENCE FIGURE read off the emitted patch (RULINGS
    2026-09-06w (2)): over the apron within-shape population
    ``within_shape`` prices (ring edges, spine / rigid-endpoint chords,
    body chords inside the gate, the chords through the face cover), per
    shape and in all: the pairs whose built grade exceeds the PREFERRED
    cap (``role_preferred_cap``) by more than the grade materiality plus
    the role's quantisation envelope, and the max built grade.  A report
    figure beside the census, never a violation; the generator-side
    reading is ``constraints.apron.apron_preference_report``."""
    from ..law.tables import role_preferred_cap
    law = p.law
    pref = role_preferred_cap(law, "apron")
    out = {"preferred": None if pref is None else pref.longitudinal,
           "max": None, "rows": 0, "over_preference": 0, "max_grade": 0.0, "faces": {}}
    if pref is None:
        return out
    ws = law.tables.emit.within_shape
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    tol = law.tables.emit.materiality.grade
    strict = spine_vertices(p) | {v for sh in p.shapes if p.is_rigid(sh.role) for v in sh.ids}
    for sh in p.shapes:
        if sh.role != "apron":
            continue
        cap = p.cap(sh)
        if cap is None or len(sh.ids) < 3:
            continue
        out["max"] = cap
        q = noise_m(law, sh.role)
        outside = chords_outside_face(p, sh, min_d)
        n = len(sh.ids)
        f = {"rows": 0, "over_preference": 0, "max_grade": 0.0}
        for i in range(n):
            a = sh.ids[i]
            for j in range(i + 1, n):
                b = sh.ids[j]
                (xa, ya), (xb, yb) = sh.xy[i], sh.xy[j]
                d = math.hypot(xa - xb, ya - yb)
                if d < min_d or (i, j) in outside:
                    continue
                adjacent = (j == i + 1) or (i == 0 and j == n - 1)
                if not (adjacent or a in strict or b in strict or d <= ws.apron_body_chord_max_m):
                    continue
                de = abs(sh.z[i] - sh.z[j])
                g = max(0.0, de - q) / d
                f["rows"] += 1
                if de > (pref.longitudinal + tol) * d + q:
                    f["over_preference"] += 1
                f["max_grade"] = max(f["max_grade"], g)
        f["max_grade"] = round(f["max_grade"], 6)
        out["faces"][str(sh.key)] = f
        out["rows"] += f["rows"]
        out["over_preference"] += f["over_preference"]
        out["max_grade"] = max(out["max_grade"], f["max_grade"])
    return out


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


def published_axis_index(p: Patch) -> AxisIndex:
    """The published ``stretches`` (``[[[lat, lon]…], cL, letter, ref]``)
    as the box's :class:`AxisIndex` in the census frame — ``cT`` the
    letter's taxi transverse cap, exactly as the generator and the v1
    oracle (``_StretchBox``) read it."""
    law = p.law
    taxi_role = law.tables.precedence.taxi_family.members[0]
    axes = []
    for entry in p.publication.get("stretches") or []:
        letter = entry[2] if len(entry) > 2 else None
        rc = role_cap(law, taxi_role, None, letter)
        if rc is None or len(entry[0]) < 2:
            continue
        axes.append(([p.to_m(float(la), float(lo)) for la, lo in entry[0]],
                     float(entry[1]), rc.transverse))
    return AxisIndex(axes, law.tables.emit.within_shape.withdrawn_chord_min_m)


def taxi_box(p: Patch) -> list[Row]:
    """THE SHORT-PAIR BOX reader (RULINGS 2026-09-06s; ``constraints.taxi``
    module docstring): every taxi-family pair of one ring — a face's
    outer ring, a hole ring hosted by a taxi-family face (judged at the
    host's role, the oracle's population), a junction-mesh face's mesh
    edges and common-stretch pairs (04y) — under ``withdrawn_chord_min_m``
    against ``cL·|Δs| + cT·|Δt|`` on the nearest published stretch axis,
    forgiven the role's instrument envelope.  Lockstep with the oracle's
    ``taxi_box`` family and with the generator's population; a patch
    publishing no ``stretches`` reads none."""
    drops = crown_by_vertex(p)
    law = p.law
    ws = law.tables.emit.within_shape
    index = published_axis_index(p)
    if not index:
        return []
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    max_d = ws.withdrawn_chord_min_m
    taxi = set(law.tables.precedence.taxi_family.members)
    mesh_roles = set(ws.junction_mesh_roles)
    mesh = mesh_pairs(p)
    lines = stretch_lines(p)
    xy_all = p.xy
    host_of = {sh.key: sh for sh in p.shapes}
    out: list[Row] = []
    joints = joint_index(p)
    rings: list[tuple[Shape, Shape]] = [(sh, sh) for sh in p.shapes if sh.role in taxi]
    rings += [(fe, host_of[fe.host]) for fe in p.features
              if fe.feature == "gap_interior_ring" and fe.host in host_of
              and host_of[fe.host].role in taxi]
    for sh, host in rings:
        if p.cap(host) is None or len(sh.ids) < 2:
            continue
        pos = {v: k for k, v in enumerate(sh.ids)}
        xy = {v: sh.xy[k] for k, v in enumerate(sh.ids)}
        meshed = host.role in mesh_roles and mesh is not None
        if meshed:
            pop: dict[tuple[int, int], float] = {}
            n = len(sh.ids)
            for i in range(n):
                a, b = sh.ids[i], sh.ids[(i + 1) % n]
                if a != b:
                    pop[(min(a, b), max(a, b))] = math.dist(xy[a], xy[b])
            for a, b in mesh:
                if a in xy and b in xy:
                    pop.setdefault((a, b), math.dist(xy[a], xy[b]))
            if host is sh:
                for (a, b), _c in stretch_pair_caps(sh, lines, xy_all, p.cap(host), min_d,
                                                    common_only=True).items():
                    pop.setdefault((min(a, b), max(a, b)), math.dist(xy[a], xy[b]))
            pairs = [(a, b, d) for (a, b), d in pop.items() if min_d <= d < max_d]
        else:
            pairs = short_pairs(xy, list(sh.ids), min_d, max_d)
        q = noise_m(law, host.role)
        for a, b, d in pairs:
            (xa, ya), (xb, yb) = xy[a], xy[b]
            bb = index.box_bound(xa, ya, xb, yb)
            if bb is None:
                continue
            bound, _cl, _ct = bb
            # RE-CENTRED ON THE PUBLISHED CROWN like ``within_shape`` (:308)
            # and the oracle's box reader (``check_grade.py`` ~:6202,
            # ``de = |(ea − eb) − offset|``): a crowned pair's designed drop
            # is not a grade.  RULINGS 2026-09-10al — CYXY read 22 (oracle)
            # vs 30 (this reader) on seven lawful crowned pairs.
            dz = sh.z[pos[a]] - sh.z[pos[b]]
            de = abs(dz - _offset(drops, a, b, dz))
            if de <= bound + q + (joints.allowance(xy[a], xy[b]) if joints else 0.0):
                continue
            cap = bound / d
            out.append(row(FAMILY_TAXI_BOX, (host.role, host.role), p.side(host.role), de,
                           100 * de / d, 100 * cap, d, xy[a], xy[b], host.key, host.key,
                           lat=0.5 * (p.ll[a][0] + p.ll[b][0]),
                           lon=0.5 * (p.ll[a][1] + p.ll[b][1])))
    return out
