"""RUNWAY-STRIP generators (families ``strip_longitudinal``, ``strip_arc``,
``resa_transverse``, ``raoa``, ``runway_end_skirt``; reg-set 2026-08-08;
ICAO Annex 14 §3.4.12-14, §3.5.11, §3.8.4; FAA AC 150/5300-13B §3.16.5).

THE STRIP FOOTPRINT is the census's own (``grade_law.runway_strip_wall_
keepout_rings``, lockstep by construction): per runway, the principal
axis of every ``runway``-role ring vertex of that ``ref``
(:func:`geometry.principal_axis`), the LATERAL rectangle ``axis ±
zones.adjacent_ground.runway.half_width`` over the runway's own extent,
and the two END corridors ``± max(runway width, strip half-width)``
extending ``end_skirt.corridor_length_m`` beyond each end.  The code
number keys off the emitted extent exactly as the census derives it.

Rows over ``graded_strip`` rings (the ground the strip law governs):

* ``strip_longitudinal``: consecutive ring pairs inside the lateral
  rectangle whose step is predominantly ALONG the axis
  (:func:`geometry.longitudinal_runs`), not both pavement vertices, at
  ``strip.longitudinal`` by code over the ALONG-axis run, plus the strip
  reader's own envelope (``emit.instrument.coarse_noise_m``: the zone
  law's mandatory-down band and the abeam law are inconsistent on a
  diagonal pair at chord scale without it — v1's band emitter rounds
  band vertices to that quantum and its reader grants it);
* ``strip_arc``: the rate of change across each run station at
  ``strip.arc_rate`` (+ the rate reader's blind spot
  ``emit.instrument.coarse_noise_m·(1/dp+1/dn)``, see ``no_step.py``);
* ``resa_transverse``: consecutive pairs inside an end corridor whose
  step is predominantly ACROSS at ``resa.transverse_max`` (FAA near zone
  by letter);
* ``runway_end_skirt``: consecutive along-axis pairs inside an end
  corridor at ``end_skirt.max_down_grade`` (the v1 skirt ring is not a
  v2 shape — the end-corridor ground is graded_strip — so the
  longitudinal skirt law binds here instead);
* ``raoa`` (ICAO only, Annex 14 §3.8.4 "grade change along the
  approach"): the rate law over the strip vertices inside the
  ``raoa.length_m × 2·half_width_m`` rectangle before each threshold, in
  along-axis order, over consecutive vertices whose step is
  predominantly ALONG the axis.  The v1 census sorts EVERY vertex of the
  120 m-wide rectangle by station and prices laterally-separated
  neighbours centimetres apart in station as one profile — with a
  taxiway crossing the area under its own zone band that reading is
  infeasible against the tables (measured CYXY 02/20: an IIS of the
  taxi band, the no-step pairs and two raoa rows at 4 cm spacing), so
  those cross-width triples are left to the census as a reported
  residual, never bound.
"""
from __future__ import annotations

import dataclasses as _dc
import math

from ..law import Law
from ..law.tables import zone2_half_width_m
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from .geometry import (XY, longitudinal_runs, point_in_rect_ring,
                       principal_axis, rect_ring)
from .precedence import View, view

__all__ = ["RunwayGroup", "runway_groups", "runway_code_number",
           "strip_longitudinal", "strip_arc", "resa_transverse",
           "end_corridor_longitudinal", "raoa"]

GEN = "strips"


@_dc.dataclass(frozen=True)
class RunwayGroup:
    """One runway's strip footprint in the frame."""

    ref: str
    axis_a: XY
    axis_b: XY
    unit: XY
    length_m: float
    width_m: float
    code_number: int
    code_letter: str | None
    rings: tuple[list[XY], ...]          # lateral rect, approach end, departure end


def runway_code_number(length_m: float, law: Law) -> int:
    """ICAO aerodrome code number from runway length — the class the
    strip tables key by (the same thresholds v1 ``runway_code_number``
    applies: ≥ 1800 → 4, ≥ 1200 → 3, ≥ 800 → 2)."""
    if length_m >= 1800.0:
        return 4
    if length_m >= 1200.0:
        return 3
    if length_m >= 800.0:
        return 2
    return 1


def runway_groups(vw: View, airport: Airport) -> list[RunwayGroup]:
    """Strip footprints from the RUNWAY-role rings grouped by ref."""
    law = vw.law
    pts_by_ref: dict[str, list[XY]] = {}
    for f in vw.faces_of_role(("runway",)):
        pts_by_ref.setdefault(f.ref, []).extend(vw.xy[v] for v in vw.rings[f.id])
    letter_of = {rw.id: rw.code_letter for rw in airport.runways}
    out: list[RunwayGroup] = []
    for ref, pts in pts_by_ref.items():
        ax = principal_axis(pts)
        if ax is None:
            continue
        a, b, width = ax
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if length < 1.0:
            continue
        unit = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
        code = runway_code_number(length, law)
        letter = letter_of.get(ref)
        strip_half = zone2_half_width_m(law, "runway", code, letter) or 0.0
        end_half = max(width, strip_half)
        cl = law.ruleset.end_skirt.corridor_length_m
        end_len = cl.value(code, letter) if cl is not None else 0.0
        end_len = end_len or 0.0
        # inflated by the identity spacing: the census fits its own axis in
        # its own (equirectangular) frame, ~0.03 % off this one, and a
        # vertex on the footprint boundary must be bound on both readings
        m = law.tables.emit.identity.min_distinct_spacing_m
        rings = (rect_ring(a, b, -m, length + m, strip_half + m),
                 rect_ring(a, b, -end_len - m, m, end_half + m),
                 rect_ring(a, b, length - m, length + end_len + m, end_half + m))
        out.append(RunwayGroup(ref, a, b, unit, length, width, code, letter, rings))
    return out


def _strip_rings(vw: View) -> list[tuple[int, list[int], list[XY]]]:
    return [(f.id, vw.rings[f.id], [vw.xy[v] for v in vw.rings[f.id]])
            for f in vw.faces_of_role(("graded_strip",))]


def _along(u: XY, p: XY, q: XY) -> float:
    return abs((q[0] - p[0]) * u[0] + (q[1] - p[1]) * u[1])


def _across(u: XY, p: XY, q: XY) -> float:
    return abs((q[0] - p[0]) * -u[1] + (q[1] - p[1]) * u[0])


def strip_longitudinal(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    vw = view(planar, law)
    rows: list[Row] = []
    seen: set[tuple[int, int]] = set()
    for g in runway_groups(vw, airport):
        cap = law.ruleset.strip.longitudinal.value(g.code_number, g.code_letter)
        if cap is None:
            continue
        q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
        src = Source(GEN, "rulesets.strip.longitudinal (reg-set 2026-08-08)",
                     (f"rwy:{g.ref}",))
        for fid, ids, xy in _strip_rings(vw):
            inside = [point_in_rect_ring(x, y, g.rings[0]) for x, y in xy]
            if not any(inside):
                continue
            for run in longitudinal_runs(xy, g.unit, inside):
                for i, j in zip(run, run[1:]):
                    a, b = ids[i], ids[j]
                    if a in vw.pavement_vertices and b in vw.pavement_vertices:
                        continue
                    ds = _along(g.unit, xy[i], xy[j])
                    key = (min(a, b), max(a, b))
                    if ds < 1.0 or key in seen:
                        continue
                    seen.add(key)
                    rows.append(Linear(((a, 1.0), (b, -1.0)), -cap * ds - q,
                                       cap * ds + q, src))
    return rows


def strip_arc(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    vw = view(planar, law)
    r = law.ruleset.strip.arc_rate
    rate = r.grade / r.per_m
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    rows: list[Row] = []
    seen: set[tuple[int, int, int]] = set()
    for g in runway_groups(vw, airport):
        src = Source(GEN, "rulesets.strip.arc_rate (reg-set 2026-08-08)",
                     (f"rwy:{g.ref}",))
        for fid, ids, xy in _strip_rings(vw):
            inside = [point_in_rect_ring(x, y, g.rings[0]) for x, y in xy]
            if not any(inside):
                continue
            for run in longitudinal_runs(xy, g.unit, inside):
                s = [xy[i][0] * g.unit[0] + xy[i][1] * g.unit[1] for i in run]
                for k in range(1, len(run) - 1):
                    a, b, c = ids[run[k - 1]], ids[run[k]], ids[run[k + 1]]
                    key = tuple(sorted((a, b, c)))
                    if key in seen or len(set(key)) < 3:
                        continue
                    dp, dn = abs(s[k] - s[k - 1]), abs(s[k + 1] - s[k])
                    if dp < 1e-6 or dn < 1e-6:
                        continue
                    seen.add(key)
                    bound = rate * 0.5 * (dp + dn) + q * (1.0 / dp + 1.0 / dn)
                    terms = ((c, 1.0 / dn), (b, -(1.0 / dn + 1.0 / dp)), (a, 1.0 / dp))
                    rows.append(Linear(terms, -bound, bound, src))
    return rows


def _resa_max(law: Law, beyond: float, letter: str | None) -> float | None:
    rs = law.ruleset
    near = rs.end_skirt.near_zone_m
    if near is not None and beyond <= near and rs.resa.transverse_near_max is not None:
        return rs.resa.transverse_near_max.value(None, letter)
    return rs.resa.transverse_max


def resa_transverse(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    vw = view(planar, law)
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    rows: list[Row] = []
    seen: set[tuple[int, int]] = set()
    for g in runway_groups(vw, airport):
        src = Source(GEN, "rulesets.resa.transverse_max (reg-set 2026-08-08)",
                     (f"rwy:{g.ref}",))
        ux, uy = g.unit
        for fid, ids, xy in _strip_rings(vw):
            for ring_idx in (1, 2):
                ring = g.rings[ring_idx]
                inside = [point_in_rect_ring(x, y, ring) for x, y in xy]
                if not any(inside):
                    continue
                for i in range(len(xy) - 1):
                    j = i + 1
                    if not (inside[i] and inside[j]):
                        continue
                    along = _along(g.unit, xy[i], xy[j])
                    across = _across(g.unit, xy[i], xy[j])
                    if across <= along or across < 1.0:
                        continue
                    s_mid = 0.5 * ((xy[i][0] + xy[j][0] - 2 * g.axis_a[0]) * ux
                                   + (xy[i][1] + xy[j][1] - 2 * g.axis_a[1]) * uy)
                    beyond = abs(s_mid) if ring_idx == 1 else max(0.0, s_mid - g.length_m)
                    cap = _resa_max(law, beyond, g.code_letter)
                    if not cap:
                        continue
                    a, b = ids[i], ids[j]
                    key = (min(a, b), max(a, b))
                    if key in seen:
                        continue
                    seen.add(key)
                    # the census reads ``across`` in its own frame; a pair near
                    # the along/across boundary can read a few dm shorter
                    # there (measured CYXY 14R/32L: 49.4 vs 49.08 m) — bound
                    # over the span less the identity spacing
                    span = max(1.0, across - law.tables.emit.identity.min_distinct_spacing_m)
                    rows.append(Linear(((a, 1.0), (b, -1.0)), -cap * span - q,
                                       cap * span + q, src))
    return rows


def end_corridor_longitudinal(planar: PlanarMap, law: Law, airport: Airport
                              ) -> list[Row]:
    """Down-grade cap along the end corridors (``end_skirt.max_down_grade``)."""
    vw = view(planar, law)
    cap = law.ruleset.end_skirt.max_down_grade
    q = law.tables.emit.instrument.strip_edge_noise_m - law.tables.emit.materiality.elevation_m
    rows: list[Row] = []
    seen: set[tuple[int, int]] = set()
    for g in runway_groups(vw, airport):
        src = Source(GEN, "rulesets.end_skirt.max_down_grade (reg-set 2026-08-08)",
                     (f"rwy:{g.ref}",))
        for fid, ids, xy in _strip_rings(vw):
            for ring_idx in (1, 2):
                inside = [point_in_rect_ring(x, y, g.rings[ring_idx]) for x, y in xy]
                if not any(inside):
                    continue
                for run in longitudinal_runs(xy, g.unit, inside):
                    for i, j in zip(run, run[1:]):
                        a, b = ids[i], ids[j]
                        ds = _along(g.unit, xy[i], xy[j])
                        key = (min(a, b), max(a, b))
                        if ds < 1.0 or key in seen:
                            continue
                        seen.add(key)
                        rows.append(Linear(((a, 1.0), (b, -1.0)), -cap * ds - q,
                                           cap * ds + q, src))
        rows.extend(_end_foot_rows(vw, g, cap, q, src, seen))
    return rows


def _end_foot_rows(vw: View, g: RunwayGroup, cap: float, q: float, src: Source,
                   seen: set[tuple[int, int]]) -> list[Row]:
    """THE CHORD FORM of the same law, from the runway END EDGE: every
    strip vertex in an end corridor abeam the runway's width is bound to
    the interpolation along the end edge over its along-axis distance
    beyond the end.  The ring-pair form above binds only consecutive
    ring vertices whose step is along the axis; the 3 m lip ring around
    an end has none (its vertices step ACROSS), so the lip's outer ring
    was tied to the runway only through 33 m transverse rows and the DEM
    pull took it 2.44 m under the runway end centre 3 m away (measured
    LEMD 18R/36L, the 2026-09-04e seam tear).  A vertex laterally outside
    the runway's width has no end-edge foot and keeps the transverse
    rows."""
    ux, uy = g.unit
    m = vw.law.tables.emit.identity.min_distinct_spacing_m

    def s_of(p: XY) -> float:
        return (p[0] - g.axis_a[0]) * ux + (p[1] - g.axis_a[1]) * uy

    end_edges: list[tuple[int, int, int]] = []          # (a, b, end index)
    for f in vw.faces_of_role(("runway",)):
        if f.ref != g.ref:
            continue
        ring = vw.rings[f.id]
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            sa, sb = s_of(vw.xy[a]), s_of(vw.xy[b])
            for end, s0 in ((1, 0.0), (2, g.length_m)):
                if abs(sa - s0) <= m and abs(sb - s0) <= m:
                    end_edges.append((a, b, end))
    if not end_edges:
        return []
    # a wall vertex carries the crest (the DEM, 2026-09-03b L1) and no
    # chord from the runway end binds it — the zones stop at the wall
    walls = {v for f in vw.faces_of_role(("retaining_wall",)) for v in vw.rings[f.id]}
    rows: list[Row] = []
    for fid, ids, xy in _strip_rings(vw):
        for k, v in enumerate(ids):
            if v in vw.pavement_vertices or v in walls:
                continue
            x, y = xy[k]
            for a, b, end in end_edges:
                if not point_in_rect_ring(x, y, g.rings[end]):
                    continue
                (ax, ay), (bx, by) = vw.xy[a], vw.xy[b]
                ex, ey = bx - ax, by - ay
                l2 = ex * ex + ey * ey
                if l2 < 1e-9:
                    continue
                t = ((x - ax) * ex + (y - ay) * ey) / l2
                if t < 0.0 or t > 1.0:
                    continue                    # beside the corner, not abeam
                s_v = s_of((x, y))
                beyond = abs(s_v) if end == 1 else s_v - g.length_m
                key = (min(v, a), max(v, a))
                if beyond < 1.0 or key in seen:
                    continue
                seen.add(key)
                rows.append(Linear(((v, 1.0), (a, -(1.0 - t)), (b, -t)),
                                   -cap * beyond - q, cap * beyond + q, src))
                break
    return rows


def raoa(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """ICAO Annex 14 §3.8.4 rate law before each threshold."""
    vw = view(planar, law)
    ra = law.ruleset.raoa
    if ra is None or not ra.length_m or not ra.half_width_m:
        return []
    rate = ra.max_grade_change.grade / ra.max_grade_change.per_m
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    rows: list[Row] = []
    seen: set[tuple[int, int, int]] = set()
    for g in runway_groups(vw, airport):
        src = Source(GEN, "rulesets.raoa.max_grade_change (reg-set 2026-08-08)",
                     (f"rwy:{g.ref}",))
        for thr, inward in ((g.axis_a, g.unit), (g.axis_b, (-g.unit[0], -g.unit[1]))):
            m = law.tables.emit.identity.min_distinct_spacing_m
            L, W = ra.length_m + m, ra.half_width_m + m
            ux, uy = inward
            px, py = -uy, ux
            corners = ((m, -W), (-L, -W), (-L, W), (m, W))
            ring = [(thr[0] + ux * s + px * t, thr[1] + uy * s + py * t)
                    for (s, t) in corners]
            ring.append(ring[0])
            for fid, ids, xy in _strip_rings(vw):
                idx = [i for i, (x, y) in enumerate(xy)
                       if point_in_rect_ring(x, y, ring)]
                if len(idx) < 3:
                    continue
                s = [xy[i][0] * ux + xy[i][1] * uy for i in idx]
                order = sorted(range(len(idx)), key=lambda k: s[k])
                s = [s[k] for k in order]
                src_ids = [ids[idx[k]] for k in order]
                pts_o = [xy[idx[k]] for k in order]
                for k in range(1, len(s) - 1):
                    dp, dn = s[k] - s[k - 1], s[k + 1] - s[k]
                    if dp < 1e-6 or dn < 1e-6:
                        continue
                    if any(abs((q[0] - p_[0]) * px + (q[1] - p_[1]) * py)
                           > abs((q[0] - p_[0]) * ux + (q[1] - p_[1]) * uy)
                           for p_, q in ((pts_o[k - 1], pts_o[k]), (pts_o[k], pts_o[k + 1]))):
                        continue          # a cross-width neighbour, not a profile step
                    a, b, c = src_ids[k - 1], src_ids[k], src_ids[k + 1]
                    key = (a, b, c)
                    if key in seen or len(set(key)) < 3:
                        continue
                    seen.add(key)
                    bound = rate * 0.5 * (dp + dn) + q * (1.0 / dp + 1.0 / dn)
                    terms = ((c, 1.0 / dn), (b, -(1.0 / dn + 1.0 / dp)), (a, 1.0 / dp))
                    rows.append(Linear(terms, -bound, bound, src))
    return rows
