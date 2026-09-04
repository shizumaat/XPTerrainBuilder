"""``within_shape`` / ``road_cross_section`` / ``plane_gradient`` over the
emitted rings — the v1 census's pair population re-read from the law
tables (``check_grade.iter_shape_grade_constraints`` +
``grade_law.classify_pair``, verify-side):

* PLANE shapes (runway family, taxi family, rigid pads, groundside):
  every vertex pair at the role cap; a ``runway`` ring (``o4_single_poly``)
  only same/adjacent-station pairs (``within_shape.runway_station_cluster_m``,
  user 2026-07-08);
* SOFT shapes (apron, junction, service_junction, service_road): ring
  edges, spine chords (a published-axis vertex) and pad-frontage chords
  at the cap; an apron interior body chord within
  ``within_shape.apron_body_chord_max_m`` at ``common.apron_fan_ramp_max``;
  junction bodies at the cap (the census's junction-mesh rule prices a
  SUBSET of these — v2 verifies the superset it solved);
* every pair re-centred on the published ``crown_drops`` (2026-08-05)
  and forgiven the role's instrument envelope;
* a road-family pair at or beyond ``common.road_transverse_axis_min_deg``
  off the ring's long axis is the CROSS-SECTION (2026-08-25g), priced
  at the transverse cap into ``road_cross_section``;
* ``plane_gradient``: a THREE-vertex ring's plane gradient vs its cap
  (user 2026-07-05).
"""
from __future__ import annotations

import math

from ..constraints.geometry import long_axis, pair_is_transverse, station_indices
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
    rigid_v: set[int] = set()
    for sh in p.shapes:
        if p.is_rigid(sh.role):
            rigid_v.update(sh.ids)
    within: list[Row] = []
    xsec: list[Row] = []
    for sh in p.shapes:
        cap = p.cap(sh)
        if cap is None:
            continue
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
                pair_cap = cap
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
    """Three-vertex rings: plane gradient vs cap in crown-lifted space."""
    law = p.law
    drops = crown_by_vertex(p)
    noise = law.tables.emit.instrument.rounding_noise_m
    out: list[Row] = []
    for sh in p.shapes:
        cap = p.cap(sh)
        if cap is None or len(sh.ids) != 3:
            continue
        pts = [(sh.xy[k][0], sh.xy[k][1], sh.z[k] + drops.get(sh.ids[k], 0.0))
               for k in range(3)]
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = pts
        ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
        vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        if abs(nz) < 1e-6:
            continue
        gx, gy = -nx / nz, -ny / nz
        grad = math.hypot(gx, gy)
        if grad < 1e-9:
            continue
        ghx, ghy = gx / grad, gy / grad
        proj = sorted((q[0] * ghx + q[1] * ghy, q[2], q) for q in pts)
        dist = proj[-1][0] - proj[0][0]
        de = abs(proj[-1][1] - proj[0][1])
        if de <= cap * dist + noise:
            continue
        out.append(row("plane_gradient", (sh.role, sh.role), p.side(sh.role), de,
                       100 * grad, 100 * cap, dist if dist > 0.5 else 1.0,
                       proj[0][2][:2], proj[-1][2][:2], sh.key, sh.key))
    return out
