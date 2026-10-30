"""RUNWAY-STRIP generators (families ``strip_longitudinal``, ``strip_arc``,
``resa_transverse``, ``raoa``, ``runway_end_skirt``; reg-set 2026-08-08;
ICAO Annex 14 §3.4.12-14, §3.5.11, §3.8.4; FAA AC 150/5300-13B §3.16.5).

THE STRIP FOOTPRINT is the census's own (``grade_law.runway_strip_wall_
keepout_rings``, lockstep by construction): per runway, the principal
axis of the RUNWAY SLAB's corners (``model.airport.Runway.slab_corners``;
:func:`geometry.principal_axis`, the ring cloud only where no runway
claims the ref — §40 (1)), the LATERAL rectangle ``axis ±
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
* ``runway_end_skirt`` (``end_corridor_longitudinal`` /
  ``end_corridor_rate``): the RUNWAY-END PROFILE (owner RULINGS
  2026-10-12q (1); ``law.tables.runway_end_profile``) over the end
  corridors' ground — falling at most the strip's cap over the strip's
  end length (ICAO) or the near-end cap (FAA), the skirt's 5 % beyond;
  rising at most the take-off climb surface; the FAA rate at the end
  edge and along the corridor;
* ``raoa`` (ICAO only, Annex 14 §3.8.4 "grade change along the
  approach"): the rate law over the strip vertices inside the
  ``raoa.length_m × 2·half_width_m`` rectangle before each PRECISION
  approach threshold (Annex 14 §3.8.1, ``reference_code.raoa_applies``), in
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
import typing as _t

from ..law import Law
from ..law.reference_code import (NON_INSTRUMENT, VISUAL, raoa_applies, runway_code_number,
                                  status_by_ref)
from ..law.tables import (EndProfile, airside_stage_roles, end_profile_noise_m,
                          runway_end_profile, runway_safety_area_length_m, strip_arc_rate_per_m,
                          strip_longitudinal_cap, zone2_half_width_m)
from ..model.airport import Airport
from ..model.end_area import end_area_lengths
from ..model.threshold_datum import threshold_datums
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap
from .geometry import (XY, longitudinal_runs, point_in_rect_ring,
                       principal_axis, rect_ring)
from .end_lip import (end_lip_vertices, natural_bank_vertices, nonrunway_pavement_roles,
                      pavement_edge_junction)
from .precedence import View, curve_k_of, view, yield_cap_of

__all__ = ["RunwayGroup", "runway_groups",
           "pavement_ring_vertices", "strip_longitudinal_pairs",
           "strip_longitudinal", "strip_arc", "resa_transverse",
           "end_corridor_longitudinal", "end_corridor_rate", "end_pair_bounds",
           "end_band_vertices",
           "end_transect_pairs", "end_transect_foot",
           "END_PROFILE_RULING", "END_PROFILE_PAIR_RULING", "END_RATE_RULING",
           "END_RATE_PAIR_RULING", "raoa"]

#: A strip pair shorter than this ALONG the axis carries more rounding
#: than signal (the census's own floor, ``check_grade`` strip readers).
MIN_ALONG_M = 1.0

GEN = "strips"
#: The ruling HEADS (before the parenthesis) ``[design] one_way_rulings``
#: names: the ground follows the runway's end edge, never pulls it.
END_PROFILE_RULING = "rulesets.end_skirt runway-end profile chord (owner RULINGS 2026-10-12q (1))"
#: The same profile over a PAIR of band vertices (both ground, two-way).
END_PROFILE_PAIR_RULING = "rulesets.end_skirt runway-end profile pair (owner RULINGS 2026-10-12q (1))"
END_RATE_RULING = "rulesets.end_skirt.rate end-edge change (FAA AC 150/5300-13B §3.16.5 item 5)"
END_RATE_PAIR_RULING = "rulesets.end_skirt.rate corridor stations (FAA AC 150/5300-13B §3.16.5 item 5)"


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
    #: the runway's INSTRUMENT STATUS (RULINGS 2026-10-15k; #811:
    #: ``reference_code.runway_status``, 0 / 1 / 2 — precision)
    instrument: int = 0
    #: the APPROACH CLASS of the end at ``axis_a`` / ``axis_b``
    #: (``RunwayEnd.approach``, RULINGS 2026-10-15m (2) / 15n)
    end_classes: tuple[str, str] = (VISUAL, VISUAL)
    #: the DISPLACED THRESHOLD length of the end at ``axis_a`` / ``axis_b``
    #: (``RunwayEnd.displaced_m``): the FAA approach surface is measured
    #: from the threshold (RULINGS 2026-10-15m (1); audit row 5)
    end_displaced_m: tuple[float, float] = (0.0, 0.0)
    #: each end's threshold height over the end (``model.threshold_datum``)
    end_datum_m: tuple[float, float] = (0.0, 0.0)


def end_profiles(law: Law, g: RunwayGroup) -> dict[int, EndProfile]:
    """THE END PROFILE OF EACH END of ``g``, keyed by its corridor ring
    (1 = beyond ``axis_a``, 2 = beyond ``axis_b``): ``tables.
    runway_end_profile`` with the end's approach class and displaced
    length (owner RULINGS 2026-10-15m (1), the FAA approach surface)."""
    return {k: runway_end_profile(law, g.code_number, g.code_letter, g.instrument,
                                  g.end_classes[k - 1], g.end_displaced_m[k - 1],
                                  g.end_datum_m[k - 1])
            for k in (1, 2)}


def runway_groups(vw: View, airport: Airport) -> list[RunwayGroup]:
    """Strip footprints from the RUNWAY SLAB of each runway.

    THE AXIS COMES FROM THE RUNWAY, NOT FROM WHAT CARRIES ITS ROLE (§40
    (1), owner RULINGS 2026-09-13co item 1).  A runway's strip footprint
    is its own geometry — the apt.dat ends plus each end's overrun, at the
    declared width (``model.airport.Runway.slab_corners``, the same
    rectangle the slab cells are cut from) — and reading it off the
    runway-role RINGS instead made it a function of everything else that
    carries the role: a §40 SHOULDER joins the runway body at the runway's
    own ref, and a 100 m-wide shoulder would have fattened the fitted
    width and moved the strip rect for every consumer of it.  The ring
    cloud stays the fallback for a ref no runway in the layout claims.
    For a runway with no shoulder the two readings are the same rectangle:
    the slab cells are that rectangle less its crossings, whose extreme
    vertices are the rectangle's own corners."""
    law = vw.law
    pts_by_ref: dict[str, list[XY]] = {}
    for f in vw.faces_of_role(("runway",)):
        pts_by_ref.setdefault(f.ref, []).extend(vw.xy[v] for v in vw.rings[f.id])
    for rw in airport.runways:
        if rw.id in pts_by_ref:
            pts_by_ref[rw.id] = list(rw.slab_corners)
    letter_of = {rw.id: rw.code_letter for rw in airport.runways}
    # THE LOADER'S STAMP (regulation-conformance spec §3.2): one code
    # number per runway, from its apt.dat length — the slab's only for a
    # ref no runway claims
    code_of = {rw.id: rw.code_number for rw in airport.runways}
    class_of = {rw.id: tuple(getattr(e, "approach", VISUAL) for e in rw.ends)
                for rw in airport.runways}
    disp_of = {rw.id: tuple(float(e.displaced_m or 0.0) for e in rw.ends)
               for rw in airport.runways}
    datum_of = {rw.id: threshold_datums(rw) for rw in airport.runways}
    instrument_of = status_by_ref(airport.runways)
    ends_of = {rw.id: (rw.ends[0].xy, rw.ends[1].xy) for rw in airport.runways}
    end_len = end_area_lengths(airport, law)
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
        code = code_of.get(ref) or runway_code_number(law, length)
        letter = letter_of.get(ref)
        ins = instrument_of.get(ref, NON_INSTRUMENT)
        strip_half = zone2_half_width_m(law, "runway", code, letter, ins) or 0.0
        end_half = max(width, strip_half)
        # THE RSA LENGTH FROM THE RUNWAY END (owner RULINGS 2026-10-15c (2)):
        # the corridor runs ``runway_safety_area_length_m`` past the runway's
        # own END (``RunwayEnd.xy``), the blast pad inside it — so past the
        # SLAB end it runs that length less the end's overrun
        # ...or to the top of a drop (RULINGS 2026-10-15g (C);
        # ``model/end_area``): each end its own length, end 0 / end 1 matched
        # to the slab side its END stands on
        rsa = runway_safety_area_length_m(law, code, letter, ins)
        len_a = len_b = rsa
        classes = (VISUAL, VISUAL)
        disp = datum = (0.0, 0.0)
        if ref in ends_of:
            ss = [(p[0] - a[0]) * unit[0] + (p[1] - a[1]) * unit[1] for p in ends_of[ref]]
            e0, e1 = end_len.get(ref, (rsa, rsa))
            near_a = (e0, e1) if ss[0] <= ss[1] else (e1, e0)
            c0, c1 = class_of.get(ref, classes)
            classes = (c0, c1) if ss[0] <= ss[1] else (c1, c0)
            d0, d1 = disp_of.get(ref, disp)
            disp = (d0, d1) if ss[0] <= ss[1] else (d1, d0)
            t0, t1 = datum_of.get(ref, datum)
            datum = (t0, t1) if ss[0] <= ss[1] else (t1, t0)
            len_a = max(0.0, near_a[0] - max(0.0, min(ss)))
            len_b = max(0.0, near_a[1] - max(0.0, length - max(ss)))
        # inflated by the identity spacing: the census fits its own axis in
        # its own (equirectangular) frame, ~0.03 % off this one, and a
        # vertex on the footprint boundary must be bound on both readings
        m = law.tables.emit.identity.min_distinct_spacing_m
        rings = (rect_ring(a, b, -m, length + m, strip_half + m),
                 rect_ring(a, b, -len_a - m, m, end_half + m),
                 rect_ring(a, b, length - m, length + len_b + m, end_half + m))
        out.append(RunwayGroup(ref, a, b, unit, length, width, code, letter, rings, ins,
                               classes, disp, datum))
    return out


def _strip_rings(vw: View) -> list[tuple[int, list[int], list[XY]]]:
    return [(f.id, vw.rings[f.id], [vw.xy[v] for v in vw.rings[f.id]])
            for f in vw.faces_of_role(("graded_strip",))]


def _along(u: XY, p: XY, q: XY) -> float:
    return abs((q[0] - p[0]) * u[0] + (q[1] - p[1]) * u[1])


def pavement_ring_vertices(faces: _t.Iterable[tuple[object, _t.Sequence[int]]]
                           ) -> frozenset[int]:
    """THE STRIP LAW'S PAVEMENT POPULATION (RULINGS 2026-09-05ae(3)) — ONE
    helper the generator and the verify reader import: every vertex on the
    OUTER ring of a face the law caps (``(cap, outer ring ids)`` pairs; a
    ``None`` cap is ungoverned ground).  A HOLE ring's vertex is not
    pavement here: the census reads the emitted ways' nids
    (``check_grade._STRIP_PAVEMENT_ROLES``) and a covered hole ships no
    way, so a strip face filling a taxiway's hole is priced along its
    ring by the strip law — measured HECA 43d50a53: the generator read
    ``View.pavement_vertices`` (incident faces, holes included) and
    stated 2 rows where the reader priced 133 pairs, 7 of them over cap
    (strip #15 inside stub pav93's hole, #24/#25 inside pav73's)."""
    out: set[int] = set()
    for cap, ids in faces:
        if cap is not None:
            out.update(ids)
    return frozenset(out)


def strip_longitudinal_pairs(ids: _t.Sequence[int], xy: _t.Sequence[XY], unit: XY,
                             rect: _t.Sequence[XY], pavement: _t.Container[int],
                             owned: _t.Container[int] = frozenset()
                             ) -> list[tuple[int, int, float]]:
    """THE STRIP-LONGITUDINAL PAIR POPULATION of one strip ring (RULINGS
    2026-09-05ae(3): the generator prices every pair the reader reads):
    consecutive vertices of an along-axis run inside the lateral
    rectangle (:func:`geometry.longitudinal_runs`), not both pavement,
    at least ``MIN_ALONG_M`` apart along the axis, and not a pavement-edge
    junction with non-runway pavement (``owned``; :func:`end_lip.
    pavement_edge_junction`) — as ``(i, j, ds)`` ring indices with the
    along-axis distance."""
    inside = [point_in_rect_ring(x, y, rect) for x, y in xy]
    if not any(inside):
        return []
    out: list[tuple[int, int, float]] = []
    for run in longitudinal_runs(xy, unit, inside):
        for i, j in zip(run, run[1:]):
            if ids[i] in pavement and ids[j] in pavement:
                continue
            if pavement_edge_junction((ids[i], ids[j]), owned):
                continue
            ds = _along(unit, xy[i], xy[j])
            if ds < MIN_ALONG_M:
                continue
            out.append((i, j, ds))
    return out


def _across(u: XY, p: XY, q: XY) -> float:
    return abs((q[0] - p[0]) * -u[1] + (q[1] - p[1]) * u[0])


def strip_longitudinal(planar: PlanarMap, law: Law, airport: Airport
                       ) -> list[Row]:
    vw = view(planar, law)
    rows: list[Row] = []
    seen: set[tuple[int, int]] = set()
    # the reader's population helper, on the reader's pavement (05ae-3)
    pav = pavement_ring_vertices((vw.caps[fid], vw.rings[fid]) for fid in planar.faces)
    owned = _nonrunway_pavement_vertices(vw)
    bank = natural_bank_vertices(vw)          # Q52: the bank yields
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    for g in runway_groups(vw, airport):
        # RULINGS 2026-10-30d: the strip along a yielded runway yields with it
        cap = strip_longitudinal_cap(law, g.code_number, g.code_letter,
                                     yield_cap_of(planar, g.ref))
        if cap is None:
            continue
        src = Source(GEN, "rulesets.strip.longitudinal (reg-set 2026-08-08)",
                     (f"rwy:{g.ref}",))
        for fid, ids, xy in _strip_rings(vw):
            for i, j, ds in strip_longitudinal_pairs(ids, xy, g.unit, g.rings[0], pav, owned):
                a, b = ids[i], ids[j]
                key = (min(a, b), max(a, b))
                if key in seen or a in bank or b in bank:
                    continue
                seen.add(key)
                rows.append(Linear(((a, 1.0), (b, -1.0)), -cap * ds - q,
                                   cap * ds + q, src))
    return rows


def strip_arc(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    vw = view(planar, law)
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    owned = _nonrunway_pavement_vertices(vw)
    bank = natural_bank_vertices(vw)          # Q52: the bank yields
    rows: list[Row] = []
    seen: set[tuple[int, int, int]] = set()
    for g in runway_groups(vw, airport):
        src = Source(GEN, "rulesets.strip.arc_rate (reg-set 2026-08-08)",
                     (f"rwy:{g.ref}",))
        # RULINGS 2026-10-26n: the strip along a steep runway follows its
        # yielded curves
        rate = strip_arc_rate_per_m(law, curve_k_of(planar, g.ref))
        for fid, ids, xy in _strip_rings(vw):
            inside = [point_in_rect_ring(x, y, g.rings[0]) for x, y in xy]
            if not any(inside):
                continue
            for run in longitudinal_runs(xy, g.unit, inside):
                s = [xy[i][0] * g.unit[0] + xy[i][1] * g.unit[1] for i in run]
                for k in range(1, len(run) - 1):
                    a, b, c = ids[run[k - 1]], ids[run[k]], ids[run[k + 1]]
                    key = tuple(sorted((a, b, c)))
                    if key in seen or len(set(key)) < 3 or pavement_edge_junction(key, owned) \
                            or any(v in bank for v in key):
                        continue
                    dp, dn = abs(s[k] - s[k - 1]), abs(s[k + 1] - s[k])
                    if dp < 1e-6 or dn < 1e-6:
                        continue
                    seen.add(key)
                    bound = rate * 0.5 * (dp + dn) + q * (1.0 / dp + 1.0 / dn)
                    terms = ((c, 1.0 / dn), (b, -(1.0 / dn + 1.0 / dp)), (a, 1.0 / dp))
                    rows.append(Linear(terms, -bound, bound, src))
    return rows


def _nonrunway_pavement_vertices(vw: View) -> frozenset[int]:
    """The vertices of every non-runway pavement face (``end_lip.
    nonrunway_pavement_roles``) — the ``owned`` set of
    :func:`end_lip.pavement_edge_junction`."""
    return frozenset(v for f in vw.faces_of_role(tuple(nonrunway_pavement_roles(vw.law)))
                     for v in vw.face_vertices(f.id))


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
    # ROAD CAP GOVERNS (owner RULINGS 2026-10-02ag (2): "the strip's
    # transverse tie rows are withdrawn under the ribbon") — the end
    # corridor's transverse rows too (NLWF 25: a strip vertex against a
    # service-road vertex on its DEM ramp, 5.6 % over 26 m once the end
    # profile lowered the strip beside it)
    # ... and a non-runway pavement's own lip (2026-10-15j, ``_end_yields``)
    road_cap = _end_yields(vw)
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
                    if key in seen or a in road_cap or b in road_cap:
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


def _beyond_of(g: RunwayGroup, ring_idx: int):
    """``d(p)``: the along-axis distance of ``p`` beyond the pavement end
    the corridor ring ``ring_idx`` (1 = before the start, 2 = past the
    end) belongs to; 0 abeam the runway."""
    ux, uy = g.unit
    ax, ay = g.axis_a

    def d(p: XY) -> float:
        s = (p[0] - ax) * ux + (p[1] - ay) * uy
        return max(0.0, -s) if ring_idx == 1 else max(0.0, s - g.length_m)
    return d


def end_pair_bounds(prof: EndProfile, d_in: float, d_out: float, q: float
                    ) -> tuple[float | None, float]:
    """``(lo, hi)`` on ``z_in − z_out`` for a pair of end-band vertices
    ``d_in ≤ d_out`` beyond the end (ONE reading, generator and readers;
    :class:`law.tables.EndProfile`): the drop may not exceed the
    profile's fall between the two stations, the rise not the climb
    surface's; ``lo = None`` where rising ground is unbound."""
    hi = prof.fall_m(d_out) - prof.fall_m(d_in) + q
    r_out, r_in = prof.rise_m(d_out), prof.rise_m(d_in)
    lo = None if r_out is None else -(r_out - (r_in or 0.0)) - q
    return lo, hi


def end_transect_pairs(stations: _t.Sequence[tuple[int, float, float]],
                       tol_m: float) -> list[tuple[int, int]]:
    """THE TRANSECT PAIRS of an end band (owner RULINGS 2026-10-12q (1),
    design point 1 "measured how"): ``stations`` are ``(key, d, t)`` —
    every band vertex's distance beyond the end and its lateral offset.
    For each vertex the NEAREST vertex inward on the same extended line
    (``|Δt| ≤ tol_m``, ``d`` smaller by at least ``MIN_ALONG_M``) is its
    partner, so the profile along every line parallel to the centre line
    is priced station to station — the break at the strip's end length
    mints a vertex the ring walk never pairs with the outer ring (they
    are not ring-consecutive: the ring runs along the break and along the
    outer edge), and without this pair the chords alone allowed KASE 15 a
    −9.2 % step over the last 15 m while both vertices sat inside their
    chord bounds.  Returns ``(inner_key, outer_key)`` pairs."""
    out: list[tuple[int, int]] = []
    pts = sorted(stations, key=lambda p: p[1])
    for k, (key, d, t) in enumerate(pts):
        best = None
        for key2, d2, t2 in pts[:k]:
            if d - d2 < MIN_ALONG_M or abs(t - t2) > tol_m:
                continue
            if best is None or d2 > best[1]:
                best = (key2, d2)
        if best is not None:
            out.append((best[0], key))
    return out


def end_transect_foot(d: float, t: float,
                      edges: _t.Sequence[tuple[tuple[float, float], tuple[float, float]]],
                      min_m: float) -> tuple[int, float, float] | None:
    """THE TRANSECT FOOT of an end-band vertex at ``(d, t)`` (distance
    beyond the end, lateral offset): the NEAREST point inward on its own
    line where that line crosses one of ``edges`` — ``((d_a, t_a), (d_b,
    t_b))`` ring edges of the runway's own pavement — more than ``min_m``
    beyond the end (the end edge itself is the chord's,
    :func:`_end_foot_rows`).  Returns ``(edge index, tau, d_foot)`` with
    ``tau`` the foot's parameter along the edge, or ``None``.

    Why: runway-role pavement that CONTINUES PAST THE END (a paved pad
    that joined the runway body as a §40 shoulder) lies between the end
    and the ground behind it, and :func:`end_transect_pairs` pairs
    VERTICES on one line — the pad's corners stand on other lines.  With
    no row from the pad's far edge the break at the profile's first
    length landed 0.85 m behind a 60 m pad and the ground stepped 0.44 m
    down across it (KASE 15, lane kase620); one reading for the
    generator and both readers."""
    best = None
    for k, ((da, ta), (db, tb)) in enumerate(edges):
        if ta == tb or (ta - t) * (tb - t) > 0.0:
            continue
        tau = (t - ta) / (tb - ta)
        de = da + tau * (db - da)
        if de <= min_m or d - de < 0.01:
            continue
        if best is None or de > best[2]:
            best = (k, tau, de)
    return best


def _end_pavement_edges(vw: View, g: RunwayGroup, ring_idx: int
                        ) -> list[tuple[int, int, tuple[float, float], tuple[float, float]]]:
    """The OUTER-ring edges ``(a, b, (d_a, t_a), (d_b, t_b))`` of every
    runway-role face of ``g``'s own ref, in the end frame of corridor
    ``ring_idx`` (``d`` signed: negative abeam the runway)."""
    ux, uy = g.unit
    ax, ay = g.axis_a

    def dt(v: int) -> tuple[float, float]:
        x, y = vw.xy[v]
        s = (x - ax) * ux + (y - ay) * uy
        return (-s if ring_idx == 1 else s - g.length_m), -(x - ax) * uy + (y - ay) * ux

    out = []
    for f in vw.faces_of_role(("runway",)):
        if f.ref != g.ref:
            continue
        ring = vw.rings[f.id]
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            pa, pb = dt(a), dt(b)
            if max(pa[0], pb[0]) > 0.0:
                out.append((a, b, pa, pb))
    return out


def _unbound_end_vertices(vw: View) -> set[int]:
    """Strip vertices NO end row from the runway binds: a wall vertex
    carries the crest (the DEM, RULINGS 2026-09-03b L1 — the zones stop at
    the wall), and under a mapped-road ribbon THE ROAD CAP GOVERNS (owner
    RULINGS 2026-10-02ag (2), #100; ``PlanarMap.ribbon_vertices``)."""
    walls = {v for f in vw.faces_of_role(("retaining_wall",)) for v in vw.rings[f.id]}
    return walls | _end_yields(vw)


def _end_yields(vw: View) -> set[int]:
    """The vertices whose level another law states, so that no end row of
    any form prices them:

    * the road cap (owner RULINGS 2026-10-02ag (2));
    * a non-runway pavement's own lip (2026-10-15j, :mod:`.end_lip`);
    * the natural-shore bank (owner answer Q52 under 2026-10-20k,
      :func:`.end_lip.natural_bank_vertices`).

    The build publishes the first two as ``road_cap_governs`` and
    ``end_profile_yields`` and the bank as ``natural_shore``; the readers
    skip all three."""
    return (set(vw.pm.road_cap_vertices(airside_stage_roles(vw.law)))
            | end_lip_vertices(vw) | natural_bank_vertices(vw))


def end_corridor_longitudinal(planar: PlanarMap, law: Law, airport: Airport
                              ) -> list[Row]:
    """THE RUNWAY-END PROFILE (owner RULINGS 2026-10-12q (1) (a)-(c);
    ``tables.runway_end_profile``): along the end corridors the ground
    may FALL from the runway end by at most the profile's fall — the
    strip's own cap over the strip's end length (ICAO) or the near-end
    cap over the near zone (FAA), the end skirt's beyond — and may RISE
    by at most the take-off climb surface with no tail height.  Ring
    pairs along the axis (both strip) carry the profile's increment
    between their stations; the chord from the end edge
    (:func:`_end_foot_rows`) the profile at the vertex's own distance.
    The 5 % was two-sided from 0 m beyond the end until this ruling."""
    vw = view(planar, law)
    q = end_profile_noise_m(law)
    rows: list[Row] = []
    seen: set[tuple[int, int]] = set()
    unbound = _unbound_end_vertices(vw)
    # ROAD CAP GOVERNS (owner RULINGS 2026-10-02ag (2)): under a mapped-road
    # ribbon the road's own cap and its ramp to the DEM state the level —
    # no end row of any form prices that vertex (NLWF 25: a service road
    # across the band, its DEM ramp an equality the pair row lost to by
    # 0.16 m; the readers skip the published ``road_cap_governs`` set)
    # ... and a non-runway pavement's own lip (owner RULINGS 2026-10-15j):
    # the pavement leads that ground, the end profile governs the rest
    road_cap = _end_yields(vw)
    for g in runway_groups(vw, airport):
        profs = end_profiles(law, g)
        src = Source(GEN, END_PROFILE_PAIR_RULING, (f"rwy:{g.ref}",))
        chord_src = Source(GEN, END_PROFILE_RULING, (f"rwy:{g.ref}",))
        for fid, ids, xy in _strip_rings(vw):
            for ring_idx in (1, 2):
                inside = [point_in_rect_ring(x, y, g.rings[ring_idx]) for x, y in xy]
                if not any(inside):
                    continue
                beyond = _beyond_of(g, ring_idx)
                for run in longitudinal_runs(xy, g.unit, inside):
                    for i, j in zip(run, run[1:]):
                        a, b = ids[i], ids[j]
                        ds = _along(g.unit, xy[i], xy[j])
                        key = (min(a, b), max(a, b))
                        if ds < 1.0 or key in seen or a in road_cap or b in road_cap:
                            continue
                        seen.add(key)
                        di, dj = beyond(xy[i]), beyond(xy[j])
                        vin, vout = (a, b) if di <= dj else (b, a)
                        lo, hi = end_pair_bounds(profs[ring_idx], min(di, dj), max(di, dj), q)
                        # AIRSIDE IS KING: a strip ring runs along the edge
                        # of whatever pavement stands in the end band.  Two
                        # pavement vertices are that pavement's own (KBFI: an
                        # apron edge beside a runway end moved 0.06 m to this
                        # profile); one pavement vertex LEADS and the ground
                        # follows it, one-way, as it follows the end edge
                        pa, pb = a in vw.pavement_vertices, b in vw.pavement_vertices
                        if pa and pb:
                            continue
                        if pa or pb:
                            rows.append(Linear(((vin, 1.0), (vout, -1.0)), lo, hi, chord_src,
                                               follows=b if pa else a))
                            continue
                        rows.append(Linear(((vin, 1.0), (vout, -1.0)), lo, hi, src))
        # the TRANSECT pairs (``end_transect_pairs``): every band vertex
        # against the nearest vertex inward on its own line — at BOTH ends
        # (until lane kase620 this block read the ring loop's leaked index
        # and so priced the far end only: KASE 15's break → outer-ring pair
        # had no row and shipped −9.2 % over the last 15 m)
        for ring_idx in (1, 2):
            st = {v: dt for v, dt in _end_stations(vw, g, ring_idx).items()
                  if v not in road_cap}
            for vin, vout in end_transect_pairs([(v, d, t) for v, (d, t) in st.items()],
                                                law.tables.emit.identity.min_distinct_spacing_m):
                key = (min(vin, vout), max(vin, vout))
                if key in seen:
                    continue
                seen.add(key)
                lo, hi = end_pair_bounds(profs[ring_idx], st[vin][0], st[vout][0], q)
                rows.append(Linear(((vin, 1.0), (vout, -1.0)), lo, hi, src))
            # the TRANSECT FEET (``end_transect_foot``): the ground behind
            # runway pavement that continues past the end follows that
            # pavement's far edge by the profile's increment — one-way
            edges = _end_pavement_edges(vw, g, ring_idx)
            if not edges:
                continue
            m = law.tables.emit.identity.min_distinct_spacing_m
            for v, (d, t) in st.items():
                hit = None if v in unbound else end_transect_foot(
                    d, t, [(e[2], e[3]) for e in edges], m)
                if hit is None:
                    continue
                k, tau, de = hit
                lo, hi = end_pair_bounds(profs[ring_idx], de, d, q)       # on z_foot − z_v
                rows.append(Linear(((v, 1.0), (edges[k][0], -(1.0 - tau)), (edges[k][1], -tau)),
                                   -hi, None if lo is None else -lo, chord_src, follows=v))
        rows.extend(_end_foot_rows(vw, g, profs, q, chord_src, seen))
    return rows


def _end_stations(vw: View, g: RunwayGroup, ring_idx: int) -> dict[int, tuple[float, float]]:
    """``{vertex: (d, t)}`` for every strip vertex inside end rect
    ``ring_idx`` beyond the pavement end (``d > 0``), pavement excluded."""
    ux, uy = g.unit
    beyond = _beyond_of(g, ring_idx)
    out: dict[int, tuple[float, float]] = {}
    for fid, ids, xy in _strip_rings(vw):
        for k, v in enumerate(ids):
            if v in vw.pavement_vertices or v in out:
                continue
            x, y = xy[k]
            if not point_in_rect_ring(x, y, g.rings[ring_idx]):
                continue
            d = beyond((x, y))
            if d <= 0.0:
                continue
            t = -(x - g.axis_a[0]) * uy + (y - g.axis_a[1]) * ux
            out[v] = (d, t)
    return out


def end_band_vertices(vw: View, groups: _t.Iterable[RunwayGroup]) -> set[int]:
    """THE END BOX (RULINGS 2026-10-15c, the master's bug (b)): every strip
    vertex the runway-end profile governs — inside an end corridor beyond
    the pavement end (:func:`_end_stations`), less the vertices no end row
    binds (:func:`_unbound_end_vertices`).  There the RUNWAY's end profile
    is the ground's ceiling and a taxi class contributes its floor only
    (``constraints/zones.zone_bands``)."""
    unbound = _unbound_end_vertices(vw)
    out: set[int] = set()
    for g in groups:
        for ring_idx in (1, 2):
            out.update(v for v in _end_stations(vw, g, ring_idx) if v not in unbound)
    return out


def _runway_end_edges(vw: View, g: RunwayGroup) -> list[tuple[int, int, int]]:
    """The runway face's END EDGES ``(a, b, end index)``: ring edges whose
    two vertices both stand at the start (``end`` 1) or the end (2)
    station, within the identity spacing."""
    ux, uy = g.unit
    m = vw.law.tables.emit.identity.min_distinct_spacing_m

    def s_of(p: XY) -> float:
        return (p[0] - g.axis_a[0]) * ux + (p[1] - g.axis_a[1]) * uy

    out: list[tuple[int, int, int]] = []
    for f in vw.faces_of_role(("runway",)):
        if f.ref != g.ref:
            continue
        ring = vw.rings[f.id]
        for i in range(len(ring)):
            a, b = ring[i], ring[(i + 1) % len(ring)]
            sa, sb = s_of(vw.xy[a]), s_of(vw.xy[b])
            for end, s0 in ((1, 0.0), (2, g.length_m)):
                if abs(sa - s0) <= m and abs(sb - s0) <= m:
                    out.append((a, b, end))
    return out


def _end_feet(vw: View, g: RunwayGroup, end_edges, seen: set[tuple[int, int]]
              ) -> list[tuple[int, int, int, float, float, int]]:
    """Every end-band strip vertex ``v`` with its FOOT on the nearest end
    edge: ``(v, a, b, t, d, end)`` — ``t`` the foot's parameter along ``a→b``
    CLAMPED to [0, 1] (the §35 corner rule), ``d`` the true plan distance
    to the foot.  Pavement, wall-crest and road-cap vertices are never
    feet (RULINGS 2026-09-03b L1; 2026-10-02ag (2))."""
    unbound = _unbound_end_vertices(vw)
    out: list[tuple[int, int, int, float, float, int]] = []
    for fid, ids, xy in _strip_rings(vw):
        for k, v in enumerate(ids):
            if v in vw.pavement_vertices or v in unbound:
                continue
            x, y = xy[k]
            cands: list[tuple[float, int, int, float, int]] = []
            for a, b, end in end_edges:
                if not point_in_rect_ring(x, y, g.rings[end]):
                    continue
                (ax, ay), (bx, by) = vw.xy[a], vw.xy[b]
                ex, ey = bx - ax, by - ay
                l2 = ex * ex + ey * ey
                if l2 < 1e-9:
                    continue
                t = ((x - ax) * ex + (y - ay) * ey) / l2
                t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                dx, dy = x - (ax + t * ex), y - (ay + t * ey)
                cands.append((math.hypot(dx, dy), a, b, t, end))
            # the NEAREST edge states the law; a nearer edge whose (vertex,
            # foot) pair is ALREADY stated yields to the next one rather
            # than dropping the vertex — the pre-§35 loop walked the edges
            # in ring order for exactly this reason, and taking only the
            # nearest cost LEMD 1,234 rows (measured 2026-09-13, arms
            # b27faf5ce243 / ce7299094661: verify 1,354 -> 1,596)
            for d, a, b, t, end in sorted(cands):
                key = (min(v, a), max(v, a))
                if d < 1.0 or key in seen:
                    continue
                seen.add(key)
                out.append((v, a, b, t, d, end))
                break
    return out


def _end_foot_rows(vw: View, g: RunwayGroup, profs: dict[int, EndProfile], q: float,
                   src: Source, seen: set[tuple[int, int]]) -> list[Row]:
    """THE CHORD FORM of the end profile, from the runway END EDGE: every
    strip vertex in an end corridor is bound to the interpolation along
    the end edge over its plan distance beyond the end — below it by at
    most ``prof.fall_m(d)``, above it by at most ``prof.rise_m(d)``.  The
    ring-pair form above binds only consecutive ring vertices whose step
    is along the axis; the 3 m lip ring around an end has none (its
    vertices step ACROSS), so the lip's outer ring was tied to the runway
    only through 33 m transverse rows and the DEM pull took it 2.44 m
    under the runway end centre 3 m away (measured LEMD 18R/36L, the
    2026-09-04e seam tear).

    THE RUNWAY-END CORNER (§35, RULINGS 2026-09-13q item 1): a vertex
    laterally OUTSIDE the runway's width binds to the NEAREST POINT of
    the end edge (``t`` clamped to [0, 1]) over its TRUE PLAN DISTANCE —
    the end corridor's rect is already as wide as the zone-2 half-width
    (``runway_groups``), so clamping ``t`` is the whole gap.

    ONE-WAY (``follows = v``; ``[design] one_way_rulings``): the runway's
    end edge LEADS and the ground follows — the runway never moves to
    satisfy its end band (owner RULINGS 2026-10-12q (1), point 2)."""
    end_edges = _runway_end_edges(vw, g)
    if not end_edges:
        return []
    rows: list[Row] = []
    for v, a, b, t, d, end in _end_feet(vw, g, end_edges, seen):
        prof = profs[end]
        r = prof.rise_m(d)
        rows.append(Linear(((v, 1.0), (a, -(1.0 - t)), (b, -t)),
                           -prof.fall_m(d) - q, None if r is None else r + q,
                           src, follows=v))
    return rows


def _runway_inward_neighbour(vw: View, g: RunwayGroup, a: int
                             ) -> tuple[int, float] | None:
    """The runway ring vertex adjacent to end-edge vertex ``a`` whose step
    from ``a`` runs ALONG the axis (the side edge), with its along-axis
    distance — the runway's own last chord at that end."""
    ux, uy = g.unit
    best = None
    for f in vw.faces_of_role(("runway",)):
        if f.ref != g.ref or a not in vw.rings[f.id]:
            continue
        ring = vw.rings[f.id]
        i = ring.index(a)
        for nb in (ring[i - 1], ring[(i + 1) % len(ring)]):
            dx, dy = vw.xy[nb][0] - vw.xy[a][0], vw.xy[nb][1] - vw.xy[a][1]
            along, across = abs(dx * ux + dy * uy), abs(dx * -uy + dy * ux)
            if along > across and along >= 1.0 and (best is None or along < best[1]):
                best = (nb, along)
    return best


def end_corridor_rate(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE GRADE-CHANGE RATE BEYOND THE END, where the authority states a
    number (FAA AC 150/5300-13B §3.16.5 item 5: ±2 % per 100 ft;
    ``end_skirt.rate`` with ``rate_provisional`` false — ICAO's text is
    qualitative and gets no number, RULINGS 2026-10-12q (1) point 3):

    * three consecutive along-axis stations in an end corridor at the
      rate (the ``strip_arc`` form, rate reader's blind spot included);
    * AT THE END EDGE, the chord from the end foot to a zone-2 vertex at
      distance ``d`` against the runway's OWN last chord: a grade that may
      change by ``rate`` per metre reaches at most ``g_end ± rate·d`` at
      ``d``, so the chord's average grade is within ``½·rate·d`` of the
      runway's — ``|z_v − z_foot − g_end·d| ≤ ½·rate·d² + q``, the runway
      vertices leading (``follows = v``).  Lip (zone-1) vertices are the
      lip law's and are not read here."""
    vw = view(planar, law)
    prof = runway_end_profile(law)
    rate = prof.rate
    if rate is None:
        return []
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    lip = law.tables.zones.adjacent_ground.lip_width_m
    yields = _end_yields(vw)
    rows: list[Row] = []
    seen3: set[tuple[int, ...]] = set()
    seen: set[tuple[int, int]] = set()
    for g in runway_groups(vw, airport):
        src = Source(GEN, END_RATE_PAIR_RULING, (f"rwy:{g.ref}",))
        for fid, ids, xy in _strip_rings(vw):
            for ring_idx in (1, 2):
                inside = [point_in_rect_ring(x, y, g.rings[ring_idx]) for x, y in xy]
                if not any(inside):
                    continue
                for run in longitudinal_runs(xy, g.unit, inside):
                    s = [xy[i][0] * g.unit[0] + xy[i][1] * g.unit[1] for i in run]
                    for k in range(1, len(run) - 1):
                        a, b, c = ids[run[k - 1]], ids[run[k]], ids[run[k + 1]]
                        key = tuple(sorted((a, b, c)))
                        if key in seen3 or len(set(key)) < 3:
                            continue
                        # AIRSIDE IS KING: the rate is the GROUND's — a
                        # station on pavement (an apron edge the strip ring
                        # runs along) is that pavement's and enters no row
                        # (KBFI: three apron-edge vertices in one rate row)
                        if any(v in vw.pavement_vertices or v in yields for v in key):
                            continue      # ... and a vertex another law levels (``_end_yields``)
                        dp, dn = abs(s[k] - s[k - 1]), abs(s[k + 1] - s[k])
                        if dp < 1e-6 or dn < 1e-6:
                            continue
                        seen3.add(key)
                        bound = rate * 0.5 * (dp + dn) + q * (1.0 / dp + 1.0 / dn)
                        terms = ((c, 1.0 / dn), (b, -(1.0 / dn + 1.0 / dp)), (a, 1.0 / dp))
                        rows.append(Linear(terms, -bound, bound, src))
        end_edges = _runway_end_edges(vw, g)
        src = Source(GEN, END_RATE_RULING, (f"rwy:{g.ref}",))
        for v, a, b, t, d, _end in _end_feet(vw, g, end_edges, seen):
            if d < lip:
                continue
            na, nb = _runway_inward_neighbour(vw, g, a), _runway_inward_neighbour(vw, g, b)
            if na is None or nb is None:
                continue
            (pa, dpa), (pb, dpb) = na, nb
            # z_foot = (1-t) z_a + t z_b ; g_end = ((1-t)(z_a - z_pa)/dpa + t (z_b - z_pb)/dpb)
            terms = ((v, 1.0),
                     (a, -(1.0 - t) * (1.0 + d / dpa)), (b, -t * (1.0 + d / dpb)),
                     (pa, (1.0 - t) * d / dpa), (pb, t * d / dpb))
            bound = 0.5 * rate * d * d + q
            rows.append(Linear(tuple((i, c) for i, c in terms if c != 0.0),
                               -bound, bound, src, follows=v))
    return rows


def raoa(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """ICAO Annex 14 §3.8.4 rate law before each threshold."""
    vw = view(planar, law)
    ra = law.ruleset.raoa
    if ra is None or not ra.length_m or not ra.half_width_m:
        return []
    rate = ra.max_grade_change.grade / ra.max_grade_change.per_m
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    # RULINGS 2026-10-15j: a non-runway pavement's own lip follows it
    lip = end_lip_vertices(vw, runway_groups(vw, airport))   # the published set
    rows: list[Row] = []
    seen: set[tuple[int, int, int]] = set()
    for g in runway_groups(vw, airport):
        src = Source(GEN, "rulesets.raoa.max_grade_change (reg-set 2026-08-08)",
                     (f"rwy:{g.ref}",))
        for thr, inward, cls in ((g.axis_a, g.unit, g.end_classes[0]),
                                 (g.axis_b, (-g.unit[0], -g.unit[1]), g.end_classes[1])):
            # Annex 14 §3.8.1: before a PRECISION approach end only (audit
            # row 8; ``law.reference_code.raoa_applies``, the one filter)
            if not raoa_applies(law, cls):
                continue
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
                    if key in seen or len(set(key)) < 3 or any(v in lip for v in key):
                        continue
                    seen.add(key)
                    bound = rate * 0.5 * (dp + dn) + q * (1.0 / dp + 1.0 / dn)
                    terms = ((c, 1.0 / dn), (b, -(1.0 / dn + 1.0 / dp)), (a, 1.0 / dp))
                    rows.append(Linear(terms, -bound, bound, src))
    return rows
