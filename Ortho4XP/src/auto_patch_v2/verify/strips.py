"""The graded-strip families over the emitted rings (reg-set 2026-08-08;
v1 ``_check_strip_longitudinal_grade`` / ``_check_strip_arc_rate`` /
``_check_resa_transverse_grade`` / ``_check_raoa_rate`` /
``_check_adjacent_ground_edges`` / ``_check_strip_seam_tears``):

* the footprint per runway from the emitted ``runway`` rings grouped by
  ``ref`` (``constraints.strips`` geometry: principal axis, lateral
  rectangle, end corridors), code from the emitted extent;
* ``strip_longitudinal`` / ``strip_arc``: along-axis runs inside the
  lateral rectangle, pavement-pavement pairs skipped, the strip
  reader's coarse envelope / rate blind spot, one row per physical site
  — the ``strip_longitudinal`` PAIR POPULATION and its pavement set are
  the generator's own helpers (``constraints.strips.strip_longitudinal_
  pairs`` / ``pavement_ring_vertices``, RULINGS 2026-09-05ae(3));
* ``resa_transverse``: across pairs inside an end corridor;
* ``raoa`` (ICAO): the s-sorted rate law inside the RAOA rectangle,
  EXACTLY as the census walks it (cross-width neighbours included — the
  reading v2 reports as a residual, ``constraints/strips.py``);
* ``adjacent_ground_tear``: a sub-metre strip edge with a metre-plus jump;
* ``strip_seam_tear``: two different strip rings' vertices within the
  seam radius, a metre-plus step at ≥ 50 % (wall exemptions vacuous:
  v2 emits no walls; the open-ground 15 m floor is NOT modelled — v2 has
  no ungraded ground inside its strips);
* ``strip_transverse`` (RULINGS 2026-09-06b law 2; 2026-09-06p (1)/(3)
  THE RUNWAY-EDGE TIE, read GEOMETRICALLY over EVERY vertex): every
  vertex of every ring and hole — any role but the runway family's own
  and a retaining wall's — inside a runway's lateral rectangle and
  runway zone, standing ABOVE its nearest runway-family ring edge
  (interpolated at the foot) by more than
  ``tables.strip_transverse_bound(d)`` plus the quantum; a STRIP-ONLY
  vertex is read either way (its fall side is the zone floor, the
  06b reading).  Generator-independent by construction: the reader
  never consults a published pair list (06o: both instruments read only
  the pairs the generators published and were blind to a pair never
  priced).  :func:`runway_edge_tie` is the one geometric core — the v2
  reader, the v1 oracle (``check_grade``'s ``strip_transverse`` family)
  and ``tools/harness/runway_edge_tie.py`` all call it.
"""
from __future__ import annotations

import math
import typing as _t

from ..constraints.geometry import (longitudinal_runs, point_in_rect_ring,
                                    principal_axis, rect_ring)
from ..constraints.strips import pavement_ring_vertices, strip_longitudinal_pairs
from ..law.tables import strip_transverse_bound, zone2_half_width_m
from .frame import Patch, Row, Shape, row
from .no_step import rate_breaches

__all__ = ["groups", "strip_longitudinal", "strip_arc", "resa_transverse",
           "raoa", "adjacent_ground_tear", "strip_seam_tear", "strip_transverse",
           "runway_edge_tie", "TiePoint", "TieEdge", "TieHit"]

FAMILY_STRIP_TRANSVERSE = "strip_transverse"
RUNWAY_FAMILY = ("runway", "runway_crossing")
#: The role whose ring is a wall CREST: exempt from the tie (06p (1)).
WALL_ROLE = "retaining_wall"

#: One vertex the tie reads: ``both_ways`` for a strip-only vertex (the
#: 06b reading, fall side included); ``label`` is the reader's own tag
#: (a role set, a way id) carried into the hit.
TiePoint = tuple[int, float, float, float, bool, object]
#: One runway-family ring edge: ``((ax, ay, az), (bx, by, bz), ref,
#: code_number, code_letter)``.
TieEdge = tuple[tuple[float, float, float], tuple[float, float, float], str,
                int | None, str | None]


class TieHit(_t.NamedTuple):
    """One vertex over the tie: ``dz = z_v − z_foot`` (signed)."""

    vid: int
    x: float
    y: float
    z: float
    d: float
    z_foot: float
    dz: float
    bound: float
    foot: tuple[float, float]
    ref: str
    code_number: int | None
    code_letter: str | None
    label: object


def runway_edge_tie(points: _t.Iterable[TiePoint], edges: _t.Sequence[TieEdge],
                    axes: _t.Mapping[str, tuple[tuple[float, float], tuple[float, float], float]],
                    law, q: float, edge_tol: float,
                    all_hits: bool = False) -> list[TieHit]:
    """THE RUNWAY-EDGE TIE, geometric (module docstring; RULINGS
    2026-09-06p (1)/(3)): for every point its nearest runway-family ring
    edge whose runway's lateral extent holds it abeam (``axes[ref] =
    (a, unit, L)``: ``0 ≤ s ≤ L``; an edge with no axis is abeam
    everywhere) inside that class's zone-2 half width less ``edge_tol``
    (the corridor's outer ring sits at the half width to the identity
    floor); the foot interpolates the edge's elevation; the vertex is a
    hit when ``dz = z − z_foot > bound + q`` — or, for a ``both_ways``
    point, ``|dz| > bound + q`` — with ``bound =
    strip_transverse_bound(law, d, code)``.  ``all_hits`` returns every
    point in reach with its reading (the harness tool's table)."""
    if not edges:
        return []
    cell = max(zone2_half_width_m(law, "runway", e[3], e[4]) or 0.0 for e in edges)
    if cell <= 0.0:
        return []
    grid: dict[tuple[int, int], list[int]] = {}
    for k, (a, b, *_r) in enumerate(edges):
        for gx in range(int(min(a[0], b[0]) // cell), int(max(a[0], b[0]) // cell) + 1):
            for gy in range(int(min(a[1], b[1]) // cell), int(max(a[1], b[1]) // cell) + 1):
                grid.setdefault((gx, gy), []).append(k)
    half_of: dict[tuple, float | None] = {}
    out: list[TieHit] = []
    for vid, x, y, z, both, label in points:
        cx, cy = int(x // cell), int(y // cell)
        best = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in grid.get((cx + dx, cy + dy), ()):
                    a, b, ref, cn, cl = edges[k]
                    key = (cn, cl)
                    if key not in half_of:
                        half_of[key] = zone2_half_width_m(law, "runway", cn, cl)
                    half = half_of[key]
                    if half is None:
                        continue
                    vx, vy = b[0] - a[0], b[1] - a[1]
                    l2 = vx * vx + vy * vy
                    t = 0.0 if l2 < 1e-18 else max(0.0, min(1.0, ((x - a[0]) * vx + (y - a[1]) * vy) / l2))
                    d = math.hypot(x - (a[0] + t * vx), y - (a[1] + t * vy))
                    if d > half - edge_tol or d <= 0.0:
                        continue
                    ax_ = axes.get(ref)
                    if ax_ is not None:
                        (a0x, a0y), (ux, uy), L = ax_
                        s_ = (x - a0x) * ux + (y - a0y) * uy
                        if not (0.0 <= s_ <= L):
                            continue
                    if best is None or d < best[0]:
                        best = (d, a[2] + t * (b[2] - a[2]), ref, cn, cl,
                                (a[0] + t * vx, a[1] + t * vy))
        if best is None:
            continue
        d, z_foot, ref, cn, cl, foot = best
        bound = strip_transverse_bound(law, d, cn, cl)
        if bound is None:
            continue
        dz = z - z_foot
        over = (abs(dz) if both else dz) > bound + q
        if over or all_hits:
            out.append(TieHit(vid, x, y, z, d, z_foot, dz, bound, foot, ref, cn, cl, label))
    return out

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


def _pavement_ids(p: Patch) -> frozenset[int]:
    """The generator's own pavement population (``constraints.strips.
    pavement_ring_vertices``, RULINGS 2026-09-05ae(3))."""
    return pavement_ring_vertices((p.cap(sh), sh.ids) for sh in p.shapes)


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
            # ONE population with the generator (05ae-3)
            for i, j, ds in strip_longitudinal_pairs(sh.ids, sh.xy, unit, rings[0], pav):
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


def strip_transverse(p: Patch) -> list[Row]:
    """The tie read on the built surface (module docstring): EVERY
    vertex of every shape and feature — the runway family's own and the
    wall crests excluded — against its nearest abeam runway-family ring
    edge; a strip-only vertex either way, any other vertex on the rise
    side (06p (1)); one row per vertex, the roles ``(vertex's role,
    runway)``."""
    law = p.law
    q = law.tables.emit.instrument.coarse_noise_m
    # the corridor's OUTER ring sits at the half width to the identity
    # floor: the census frame and the planar frame disagree there by the
    # frame's own rounding (measured 74.93 vs 75.08 m on the crown twin),
    # so the reader stops one identity floor short of the generator's edge
    edge_tol = law.tables.emit.identity.min_distinct_spacing_m
    exempt: set[int] = set()
    role_of: dict[int, str] = {}
    key_of: dict[int, int] = {}
    strip_only: set[int] = set()
    other: set[int] = set()
    for sh in p.shapes:
        if sh.role in RUNWAY_FAMILY or sh.role == WALL_ROLE:
            exempt.update(sh.ids)
            continue
        if sh.role == "graded_strip":
            strip_only.update(sh.ids)
        else:
            other.update(sh.ids)
        for vid in sh.ids:
            role_of.setdefault(vid, sh.role)
            key_of.setdefault(vid, sh.key)
    host_role = {sh.key: sh.role for sh in p.shapes}
    for sh in p.features:
        if sh.feature == "crown_spine":
            continue
        if sh.feature == "structure_rim":
            other.update(sh.ids)
        for vid in sh.ids:
            role_of.setdefault(vid, host_role.get(sh.host, sh.feature or "feature"))
            key_of.setdefault(vid, sh.host if sh.host is not None else sh.key)
    strip_only -= other
    # ABEAM is along the axis only (the generator's ``abeam``: 0 ≤ s ≤ L);
    # the lateral extent is the class's own zone-2 half width
    axes: dict[str, tuple] = {}
    for rings, unit, _code, L, _letter, a, _b in groups(p):
        axes[_ref_of(p, rings)] = (a, unit, L)
    edges: list[TieEdge] = []
    for sh in p.shapes:
        if sh.role not in RUNWAY_FAMILY:
            continue
        ref = sh.ref.split("+")[0]
        n = len(sh.ids)
        for i in range(n):
            j = (i + 1) % n
            edges.append(((*sh.xy[i], sh.z[i]), (*sh.xy[j], sh.z[j]), ref,
                          sh.code_number, sh.code_letter))
    pts: list[TiePoint] = [(vid, xy[0], xy[1], p.z[vid], vid in strip_only, role_of.get(vid, "?"))
                           for vid, xy in p.xy.items() if vid not in exempt and vid in role_of]
    pts.sort()
    out: list[Row] = []
    for h in runway_edge_tie(pts, edges, axes, law, q, edge_tol):
        role = str(h.label)
        r = row(FAMILY_STRIP_TRANSVERSE, (role, "runway"),
                p.side(role) if role in law.tables.precedence.roles else p.side("graded_strip"),
                abs(h.dz), 100 * h.dz / h.d, 100 * h.bound / h.d, h.d, (h.x, h.y), h.foot,
                key_of.get(h.vid, h.vid), h.ref)
        r.update({"reading": "strip_transverse", "direction": "above" if h.dz > 0.0 else "below"})
        out.append(r)
    out.sort(key=lambda r: -r["magnitude_m"])
    return out


def _ref_of(p: Patch, rings) -> str:
    """The runway ref whose ``runway`` rings lie in ``rings[0]`` (the
    lateral rectangle ``groups`` built from them)."""
    for sh in p.shapes:
        if sh.role == "runway" and all(point_in_rect_ring(x, y, rings[0]) for x, y in sh.xy[:3]):
            return sh.ref
    return ""
