"""The graded-strip families over the emitted rings (reg-set 2026-08-08;
v1 ``_check_strip_longitudinal_grade`` / ``_check_strip_arc_rate`` /
``_check_resa_transverse_grade`` / ``_check_raoa_rate`` /
``_check_adjacent_ground_edges`` / ``_check_strip_seam_tears``):

* the footprint per runway from the emitted ``runway`` rings grouped by
  ``ref`` (``constraints.strips`` geometry: principal axis, lateral
  rectangle, end corridors), code from the emitted extent;
* ``strip_longitudinal`` / ``strip_arc``: along-axis runs inside the
  lateral rectangle, pavement-pavement pairs skipped, the strip
  reader's coarse envelope / rate blind spot, one row per physical site;
* ``resa_transverse``: across pairs inside an end corridor;
* ``raoa`` (ICAO): the s-sorted rate law inside the RAOA rectangle,
  EXACTLY as the census walks it (cross-width neighbours included — the
  reading v2 reports as a residual, ``constraints/strips.py``);
* ``adjacent_ground_tear``: a sub-metre strip edge with a metre-plus jump;
* ``strip_seam_tear``: two different strip rings' vertices within the
  seam radius, a metre-plus step at ≥ 50 % (wall exemptions vacuous:
  v2 emits no walls; the open-ground 15 m floor is NOT modelled — v2 has
  no ungraded ground inside its strips).
"""
from __future__ import annotations

import math

from ..constraints.geometry import (longitudinal_runs, point_in_rect_ring,
                                    principal_axis, rect_ring)
from ..law.tables import zone2_half_width_m
from .frame import Patch, Row, Shape, row
from .no_step import rate_breaches

__all__ = ["groups", "strip_longitudinal", "strip_arc", "resa_transverse",
           "raoa", "adjacent_ground_tear", "strip_seam_tear"]

#: The census's seam-tear knobs (``strip_seam_law``): the instrument's own.
SEAM_RADIUS_M = 6.0
SEAM_MIN_STEP_M = 1.0
SEAM_MIN_GRADE = 0.5
SEAM_MIN_DISTANCE_M = 0.01
TEAR_MAX_EDGE_M = 1.0
TEAR_MIN_JUMP_M = 1.0


def _code(length: float) -> int:
    return 4 if length >= 1800 else 3 if length >= 1200 else 2 if length >= 800 else 1


def groups(p: Patch):
    """``[(rings, unit, code, length, letter, axis_a, axis_b)]`` per runway."""
    law = p.law
    pts_by_ref: dict[str, list] = {}
    letter: dict[str, str | None] = {}
    for sh in p.shapes:
        if sh.role == "runway":
            pts_by_ref.setdefault(sh.ref, []).extend(sh.xy)
            letter.setdefault(sh.ref, sh.code_letter)
    out = []
    for ref, pts in pts_by_ref.items():
        ax = principal_axis(pts)
        if ax is None:
            continue
        a, b, width = ax
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1.0:
            continue
        unit = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        code = _code(L)
        half = zone2_half_width_m(law, "runway", code, letter.get(ref)) or 0.0
        end_half = max(width, half)
        cl = law.ruleset.end_skirt.corridor_length_m
        end_len = (cl.value(code, letter.get(ref)) if cl is not None else 0.0) or 0.0
        rings = (rect_ring(a, b, 0.0, L, half), rect_ring(a, b, -end_len, 0.0, end_half),
                 rect_ring(a, b, L, L + end_len, end_half))
        out.append((rings, unit, code, L, letter.get(ref), a, b))
    return out


def _strips(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes if sh.role == "graded_strip" and len(sh.ids) >= 2]


def _pavement_ids(p: Patch) -> set[int]:
    out: set[int] = set()
    for sh in p.shapes:
        if p.cap(sh) is not None:
            out.update(sh.ids)
    return out


def strip_longitudinal(p: Patch) -> list[Row]:
    law = p.law
    q = law.tables.emit.instrument.coarse_noise_m
    pav = _pavement_ids(p)
    out: list[Row] = []
    seen: set = set()
    for rings, unit, code, L, letter, _a, _b in groups(p):
        cap = law.ruleset.strip.longitudinal.value(code, letter)
        if cap is None:
            continue
        for sh in _strips(p):
            inside = [point_in_rect_ring(x, y, rings[0]) for x, y in sh.xy]
            if not any(inside):
                continue
            for run in longitudinal_runs(sh.xy, unit, inside):
                for i, j in zip(run, run[1:]):
                    if sh.ids[i] in pav and sh.ids[j] in pav:
                        continue
                    ds = abs((sh.xy[j][0] - sh.xy[i][0]) * unit[0]
                             + (sh.xy[j][1] - sh.xy[i][1]) * unit[1])
                    if ds < 1.0:
                        continue
                    site = tuple(sorted((tuple(round(c, 3) for c in sh.xy[i]),
                                         tuple(round(c, 3) for c in sh.xy[j]))))
                    if site in seen:
                        continue
                    seen.add(site)
                    dz = abs(sh.z[j] - sh.z[i])
                    if dz <= cap * ds + q:
                        continue
                    out.append(row("strip_longitudinal", ("graded_strip",) * 2,
                                   p.side("graded_strip"), dz, 100 * dz / ds, 100 * cap,
                                   ds, sh.xy[i], sh.xy[j], sh.key, sh.key))
    return out


def strip_arc(p: Patch) -> list[Row]:
    law = p.law
    r = law.ruleset.strip.arc_rate
    rate = r.grade / r.per_m
    q = law.tables.emit.instrument.coarse_noise_m
    out: list[Row] = []
    seen: set = set()
    for rings, unit, code, L, letter, _a, _b in groups(p):
        for sh in _strips(p):
            inside = [point_in_rect_ring(x, y, rings[0]) for x, y in sh.xy]
            if not any(inside):
                continue
            for run in longitudinal_runs(sh.xy, unit, inside):
                pts = [(sh.xy[i][0] * unit[0] + sh.xy[i][1] * unit[1], 0.0) for i in run]
                zs = [sh.z[i] for i in run]
                for a, b, c, change, allowed, dp, dn in rate_breaches(pts, zs, False, rate, q):
                    A, B, C = run[a], run[b], run[c]
                    site = tuple(sorted(tuple(round(v, 3) for v in sh.xy[i]) for i in (A, B, C)))
                    if site in seen:
                        continue
                    seen.add(site)
                    out.append(row("strip_arc", ("graded_strip",) * 2, p.side("graded_strip"),
                                   abs(sh.z[C] - sh.z[A]), 100 * change, None,
                                   0.5 * (dp + dn), sh.xy[A], sh.xy[C], sh.key, sh.key))
    return out


def resa_transverse(p: Patch) -> list[Row]:
    law = p.law
    q = law.tables.emit.instrument.coarse_noise_m
    rs = law.ruleset
    out: list[Row] = []
    for rings, unit, code, L, letter, a0, _b in groups(p):
        ux, uy = unit
        px, py = -uy, ux
        for sh in _strips(p):
            for ring_idx in (1, 2):
                ring = rings[ring_idx]
                inside = [point_in_rect_ring(x, y, ring) for x, y in sh.xy]
                if not any(inside):
                    continue
                for i in range(len(sh.xy) - 1):
                    j = i + 1
                    if not (inside[i] and inside[j]):
                        continue
                    dx, dy = sh.xy[j][0] - sh.xy[i][0], sh.xy[j][1] - sh.xy[i][1]
                    along, across = abs(dx * ux + dy * uy), abs(dx * px + dy * py)
                    if across <= along or across < 1.0:
                        continue
                    s_mid = 0.5 * ((sh.xy[i][0] + sh.xy[j][0] - 2 * a0[0]) * ux
                                   + (sh.xy[i][1] + sh.xy[j][1] - 2 * a0[1]) * uy)
                    beyond = abs(s_mid) if ring_idx == 1 else max(0.0, s_mid - L)
                    near = rs.end_skirt.near_zone_m
                    if near is not None and beyond <= near and rs.resa.transverse_near_max:
                        cap = rs.resa.transverse_near_max.value(None, letter)
                    else:
                        cap = rs.resa.transverse_max
                    if not cap:
                        continue
                    dz = abs(sh.z[j] - sh.z[i])
                    if dz <= cap * across + q:
                        continue
                    out.append(row("resa_transverse", ("graded_strip",) * 2,
                                   p.side("graded_strip"), dz, 100 * dz / across,
                                   100 * cap, across, sh.xy[i], sh.xy[j], sh.key, sh.key))
    return out


def raoa(p: Patch) -> list[Row]:
    law = p.law
    ra = law.ruleset.raoa
    if ra is None or not ra.length_m or not ra.half_width_m:
        return []
    rate = ra.max_grade_change.grade / ra.max_grade_change.per_m
    q = law.tables.emit.instrument.coarse_noise_m
    out: list[Row] = []
    seen: set = set()
    for rings, unit, code, L, letter, a0, b0 in groups(p):
        for thr, inward in ((a0, unit), (b0, (-unit[0], -unit[1]))):
            ux, uy = inward
            px, py = -uy, ux
            Lr, W = ra.length_m, ra.half_width_m
            corners = ((0.0, -W), (-Lr, -W), (-Lr, W), (0.0, W))
            ring = [(thr[0] + ux * s + px * t, thr[1] + uy * s + py * t) for (s, t) in corners]
            ring.append(ring[0])
            for sh in _strips(p):
                idx = [i for i, (x, y) in enumerate(sh.xy) if point_in_rect_ring(x, y, ring)]
                if len(idx) < 3:
                    continue
                s = [sh.xy[i][0] * ux + sh.xy[i][1] * uy for i in idx]
                t_lat = [sh.xy[i][0] * px + sh.xy[i][1] * py for i in idx]
                order = sorted(range(len(idx)), key=lambda k: s[k])
                s = [s[k] for k in order]
                t_lat = [t_lat[k] for k in order]
                src = [idx[k] for k in order]
                for k in range(1, len(s) - 1):
                    dp, dn = s[k] - s[k - 1], s[k + 1] - s[k]
                    if dp < 1e-6 or dn < 1e-6:
                        continue
                    # the profile runs ALONG the approach: a hop that is more
                    # across than along is a cross-width neighbour (M3a
                    # adjudication; the oracle reads the same since 91426d6c)
                    if abs(t_lat[k] - t_lat[k - 1]) > dp or abs(t_lat[k + 1] - t_lat[k]) > dn:
                        continue
                    z0, z1, z2 = sh.z[src[k - 1]], sh.z[src[k]], sh.z[src[k + 1]]
                    change = abs((z2 - z1) / dn - (z1 - z0) / dp)
                    allowed = rate * 0.5 * (dp + dn)
                    if change - allowed <= q * (1.0 / dp + 1.0 / dn):
                        continue
                    site = tuple(sorted(tuple(round(v, 3) for v in sh.xy[i])
                                        for i in (src[k - 1], src[k], src[k + 1])))
                    if site in seen:
                        continue
                    seen.add(site)
                    out.append(row("raoa", ("graded_strip",) * 2, p.side("graded_strip"),
                                   abs(z2 - z0), 100 * change, None, 0.5 * (dp + dn),
                                   sh.xy[src[k - 1]], sh.xy[src[k + 1]], sh.key, sh.key))
    return out


def adjacent_ground_tear(p: Patch) -> list[Row]:
    out: list[Row] = []
    for sh in _strips(p):
        n = len(sh.ids)
        for i in range(n):
            j = (i + 1) % n
            (xa, ya), (xb, yb) = sh.xy[i], sh.xy[j]
            d = math.hypot(xb - xa, yb - ya)
            de = abs(sh.z[i] - sh.z[j])
            if not (d < TEAR_MAX_EDGE_M and de > TEAR_MIN_JUMP_M):
                continue
            g = de / d if d > 1e-9 else float("inf")
            out.append(row("adjacent_ground_tear", ("graded_strip",) * 2,
                           p.side("graded_strip"), de, 100 * g, None, d,
                           sh.xy[i], sh.xy[j], sh.key, sh.key))
    return out


def strip_seam_tear(p: Patch) -> list[Row]:
    strips = _strips(p)
    pts: list[tuple[float, float, float, int, int]] = []
    for sh in strips:
        for k, vid in enumerate(sh.ids):
            pts.append((sh.xy[k][0], sh.xy[k][1], sh.z[k], sh.key, vid))
    cell = SEAM_RADIUS_M
    grid: dict[tuple[int, int], list[int]] = {}
    for i, (x, y, *_r) in enumerate(pts):
        grid.setdefault((int(x // cell), int(y // cell)), []).append(i)
    out: list[Row] = []
    for i, (x, y, z, key, vid) in enumerate(pts):
        cx, cy = int(x // cell), int(y // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((cx + dx, cy + dy), ()):
                    if j <= i:
                        continue
                    x2, y2, z2, key2, vid2 = pts[j]
                    if key2 == key or vid2 == vid:
                        continue
                    d = math.hypot(x2 - x, y2 - y)
                    if d > SEAM_RADIUS_M:
                        continue
                    de = abs(z2 - z)
                    if de <= SEAM_MIN_STEP_M or de / max(d, SEAM_MIN_DISTANCE_M) < SEAM_MIN_GRADE:
                        continue
                    out.append(row("strip_seam_tear", ("graded_strip",) * 2,
                                   p.side("graded_strip"), de,
                                   100 * de / max(d, SEAM_MIN_DISTANCE_M), None, d,
                                   (x, y), (x2, y2), key, key2))
    out.sort(key=lambda r: -r["magnitude_m"])
    return out
