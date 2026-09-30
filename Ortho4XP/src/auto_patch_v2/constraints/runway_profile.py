"""RUNWAY generator — the profile is the datum (H7 / RULINGS :511-516):
CIFP thresholds are absolute pins, the profile flexes between them within
the runway's longitudinal law only, the slab crowns off the profile.

Rows (all from ``rulesets.<authority>.runway`` and
``common.runway_crown_transverse``):

* ``Pin`` at the profile station nearest each threshold with a CIFP
  elevation (``RunwayEnd.threshold_elev_m``), and — for a runway with
  FEWER THAN TWO CIFP pins — at each unpinned end, the APT.DAT DATUM
  (:func:`datum_pins`, owner RULINGS 2026-09-30z (2), issue #129);
* ``Diff`` along every ``runway_profile`` breakline chord at
  ``runway.longitudinal`` by code number; inside each END ZONE
  (``runway_end_zone_length_m``) at ``runway.end_zone`` where the
  authority states one (code 3 only when precision — recorded, no CIFP
  category is loaded, so code 3 keeps the body cap);
* CROWN (RULINGS 2026-08-05, family ``runway_crown``, solver mode
  ``offset``): every runway-family ring vertex off the ridge sits AT
  LEAST ``crown × lateral offset`` below the ridge's interpolation at its
  foot — a ``Linear`` floor over the two ridge stations bracketing the
  foot.  The sidecar declares the BUILT drop (:func:`crown_drops` with
  the solved ``z``), so the census re-centres every ring pair on the
  surface as built and its crown reader finds the declared fall.
* WITHIN-SHAPE lateral pairs on ``runway`` rings are IMPLIED: with the
  built drop declared, a pair's re-centred difference is the ridge
  profile's own difference between the two feet, bounded by the profile
  caps over an along-axis run no longer than the pair's distance — no
  row is minted (user 2026-07-08 station scoping is the census's own
  narrowing of the same domain; ``o4_single_poly`` is still tagged).
  ``runway_crossing`` rings sit on TWO ridges, so their pairs are stated
  explicitly in foot space (``Linear`` over the feet's interpolations).
* consecutive ridge chains of one runway (split at a crossing) are
  bridged by a ``Diff`` at the body cap so the profile stays one law
  across the crossing.
* TRANSVERSE MAXIMUM (RULINGS 2026-09-05o, family ``runway_transverse``,
  HARD, the runway tier): every off-ridge ``runway`` ring vertex sits
  within ``runway.transverse_max × d`` of the ridge at its foot — no fall
  steeper than the cap and no rise above the ridge steeper than it
  (HECA 05C/23C: half 14's outer edge 18 m under the ridge across 31 m).
  Vertices on a ``runway_crossing`` ring are exempt (Annex 14 §3.1.19
  "except at intersections", the crown reader's own scope).
* THE FACE'S VERTEX SET (lane ``rwyholes``, the RULINGS 2026-09-13dd
  chip): the crown drop, the crown floor and the transverse maximum are
  stated for EVERY vertex of a runway-family face — the outer ring AND
  the hole rings, through ``View.face_vertices`` (``model.planar.
  face_vertex_ids``, the accessor the verifier's ``Shape.vertex_ids``
  shares).  A §40 shoulder ribbon wrapping a zone-strip island is an
  annulus: on the v2roles HECA frame 8 of 33 runway faces carried holes
  and their 490 hole vertices — the runway's own, judged at its cap by
  the census — were priced by no row and declared no drop.
* VERTICAL CURVE (RULINGS 2026-09-06b law 1, family
  ``runway_vertical_curve``, HARD, the runway tier): between consecutive
  profile chords the grade may change by no more than
  ``tables.runway_vertical_curve_bound`` — ``min(max_grade_change,
  mean spacing / vertical_curve_k_m)`` by code (§3.1.15/16) — one
  two-sided three-term ``Linear`` per interior ridge station, the
  chains of one runway read as ONE station sequence across a crossing
  (HECA 05C/23C on 1.0.288: 2.32 pp per 100 m against K's 0.33; both
  keys were declared and priced by nothing).
"""
from __future__ import annotations

import math
import typing as _t

from ..law import Law
from ..law.tables import (role_cap, runway_end_zone_length_m,
                          runway_transverse_bound,
                          runway_transverse_max, runway_vertical_curve_bound)
from ..model.airport import Airport
from ..model.constraints import Band, Diff, Linear, Pin, Row, Source
from ..model.planar import PlanarMap
from .geometry import project_to_chain
from .precedence import View, cap_of, view
from .trend import trend_of as _trend_of

__all__ = ["threshold_pins", "datum_pins", "dem_degraded", "runway_profile", "runway_crown", "runway_transverse",
           "runway_vertical_curve", "curve_stations", "runway_within_shape",
           "crown_drops", "ridge_chains"]

GEN = "runway_profile"
RUNWAY_FAMILY = ("runway", "runway_crossing")


def ridge_chains(vw: View) -> dict[str, list[list[int]]]:
    """Runway id -> its ``runway_profile`` breakline chains (a chain may
    be split where the noding broke it)."""
    out: dict[str, list[list[int]]] = {}
    for bid, b in vw.pm.breaklines.items():
        if b.kind == "runway_profile":
            out.setdefault(b.ref, []).append(vw.chains[bid])
    return out


def _runway_code(airport: Airport, ref: str) -> tuple[int | None, str | None]:
    for rw in airport.runways:
        if rw.id == ref:
            return rw.code_number, rw.code_letter
    return None, None


def dem_degraded(airport: Airport) -> str:
    """Why the production DEM frame is DEGRADED, or ``""`` (spec §21.2 (2)).

    The ``--allow-degraded-dem`` FLAG is not the test — the flag only
    ACCEPTS a degradation; ``ProductionDem`` records one under
    ``provenance['degraded']`` only when a frame actually degraded.  A
    degraded frame keeps the STRAIGHT CHORD as the runway's target: a
    trend fitted to a surface the harness has refused is an invented
    value (plan §2).  (Lives here, not in ``runway_chord``, because
    :func:`datum_pins` reads it; ``runway_chord`` re-exports it.)"""
    prov = getattr(getattr(airport, "dem", None), "provenance", None) or {}
    try:
        return str(prov.get("degraded") or "")
    except Exception:                     # a sampler with no mapping provenance
        return ""


def _axis(rw) -> tuple[tuple[float, float], float, float]:
    a_xy, b_xy = rw.ends[0].xy, rw.ends[1].xy
    L = rw.length_m
    ux = (b_xy[0] - a_xy[0]) / L if L > 0 else 0.0
    uy = (b_xy[1] - a_xy[1]) / L if L > 0 else 0.0
    return a_xy, ux, uy


def _end_vertex(vw: View, all_ids: list[int], rw, end, ux: float, uy: float) -> int:
    """The profile station nearest ``end``'s threshold (displacement
    applied) — where that end's pin sits, CIFP or datum."""
    sign = 1.0 if end is rw.ends[0] else -1.0
    tx = end.xy[0] + sign * ux * end.displaced_m
    ty = end.xy[1] + sign * uy * end.displaced_m
    return min(all_ids, key=lambda v: (vw.xy[v][0] - tx) ** 2
               + (vw.xy[v][1] - ty) ** 2)


def _datum_slope_cap(law: Law, rw) -> float | None:
    """The steepest straight line the runway's own caps admit end to end:
    the longitudinal cap, and the end-zone cap where the authority states
    one for this code (``runway_profile``'s own reading of both)."""
    cap = role_cap(law, "runway", rw.code_number, rw.code_letter)
    if cap is None:
        return None
    lim = float(cap.longitudinal)
    rs = law.ruleset.runway
    end_cap = rs.end_zone.value(rw.code_number, rw.code_letter)
    if end_cap is not None and rw.code_number not in rs.end_zone_precision_only_codes:
        lim = min(lim, float(end_cap))
    return lim


def datum_pins(planar: PlanarMap, law: Law, airport: Airport
               ) -> dict[int, tuple[float, str, str]]:
    """THE APT.DAT DATUM (owner RULINGS 2026-09-30z (2), issue #129):
    vertex -> ``(z, runway id, end name)`` at every UNPINNED end of a
    runway with fewer than two CIFP threshold pins.

    "If there's no CIFP data, runway elevations must be in the apt.dat":
    the LEVEL is the apt.dat airport elevation record (the header row;
    runway rows carry none — ``Airport.elevation_m``), which is the
    HIGHEST point of the landing area, so the runway's HIGHER threshold
    sits at it; the TILT is the §21 long-wave DEM trend's mean
    slope along the runway's own ridge, bounded by the runway's own
    longitudinal (and end-zone) cap; on a DEGRADED frame, or a ridge the
    trend cannot fit, the runway is LEVEL at the datum (never an invented
    tilt, §21.2 (2)).  With ONE CIFP pin the CIFP end keeps its pin and the
    missing end takes the datum line's value, pulled toward the pin until
    the chord between them sits within that cap (the datum yields to the
    specific witness, never the reverse).  These are HARD pins, exactly a
    CIFP threshold's (``threshold_pins`` merges them): no stage-1
    perturbation moves the runway (the #117 floating-runway lesson, 30q),
    and every pin consumer — the pin rows, the chord/trend target, the
    route reach, the §50 cap yield — reads them as terminals.

    An airport whose apt.dat carries no finite elevation record REFUSES
    (``ValueError`` naming the airport) — never a silently free runway."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    out: dict[int, tuple[float, str, str]] = {}
    degraded = dem_degraded(airport)
    window = float(law.tables.emit.design.runway_profile_window_m)
    for rw in airport.runways:
        chs = chains.get(rw.id)
        L = rw.length_m
        if not chs or L <= 0.0:
            continue
        cifp = [e for e in rw.ends if e.threshold_elev_m is not None]
        if len(cifp) >= 2:
            continue
        elev = getattr(airport, "elevation_m", None)
        if elev is None or not math.isfinite(float(elev)):
            raise ValueError(
                f"{airport.icao}: runway {rw.id} has fewer than two CIFP "
                f"threshold pins and the apt.dat airport header carries no "
                f"elevation record ({elev!r}) — RULINGS 2026-09-30z (2) "
                f"refuses a free runway (issue #129)")
        a_xy, ux, uy = _axis(rw)

        def along(v: int) -> float:
            x, y = vw.xy[v]
            return (x - a_xy[0]) * ux + (y - a_xy[1]) * uy

        all_ids = [v for ch in chs for v in ch]
        lim = _datum_slope_cap(law, rw)
        slope = 0.0
        if not degraded and lim is not None:
            t = _trend_of(((along(v), float(planar.vertices[v].dem_z))
                           for v in all_ids
                           if planar.vertices[v].dem_z is not None), window)
            if t is not None:
                s0, s1 = t.s[0], t.s[-1]
                z0, z1 = t.at(s0), t.at(s1)
                if z0 is not None and z1 is not None and s1 > s0:
                    slope = max(-lim, min(lim, (float(z1) - float(z0)) / (s1 - s0)))
        # THE HIGHEST POINT (arm 2): the apt.dat airport elevation is the
        # elevation of the highest point of the landing area (ICAO Annex 14
        # "aerodrome elevation"; FAA "airport elevation", highest point of
        # the usable runways) — so the line's HIGHER threshold sits at it
        # and the runway falls away from there by its tilt.  Arm 1 anchored
        # the MIDPOINT: KCLT-without-CIFP 18C/36C (0.5 % over 3 km) stood
        # 9.5 m above its real CIFP thresholds.
        end_v = {e.name: _end_vertex(vw, all_ids, rw, e, ux, uy) for e in rw.ends}
        s_top = max((along(v) for v in end_v.values()), key=lambda q: slope * q)
        pinned = [(end_v[e.name], float(e.threshold_elev_m)) for e in cifp]
        for end in rw.ends:
            if end.threshold_elev_m is not None:
                continue
            v = end_v[end.name]
            z = float(elev) + slope * (along(v) - s_top)
            for vp, zp in pinned:
                if lim is None or vp == v:
                    continue
                reach = lim * abs(along(v) - along(vp))
                z = max(zp - reach, min(zp + reach, z))
            out[v] = (z, rw.id, end.name)
    return out


def threshold_pins(planar: PlanarMap, law: Law, airport: Airport) -> dict[int, float]:
    """Vertex -> threshold elevation: the profile station nearest each
    threshold (displacement applied) that carries a CIFP elevation — THE
    hard terminals of the airport (RULINGS :511-516), read here by the pin
    rows and by the route reach (``no_step.reach_bands``) — and, at every
    unpinned end of a runway with fewer than two CIFP pins, the APT.DAT
    DATUM (:func:`datum_pins`, RULINGS 2026-09-30z (2))."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    out: dict[int, float] = {}
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs:
            continue
        _a, ux, uy = _axis(rw)
        all_ids = [v for ch in chs for v in ch]
        for end in rw.ends:
            if end.threshold_elev_m is None:
                continue
            out[_end_vertex(vw, all_ids, rw, end, ux, uy)] = float(end.threshold_elev_m)
    for v, (z, _r, _e) in datum_pins(planar, law, airport).items():
        out.setdefault(v, z)
    return out


def runway_profile(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Threshold pins + longitudinal caps along each profile chain."""
    vw = view(planar, law)
    rows: list[Row] = []
    chains = ridge_chains(vw)
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs:
            continue
        cap = role_cap(law, "runway", rw.code_number, rw.code_letter)
        if cap is None:
            continue
        # §50.1 (3) THE CAP YIELDS TO ITS PINS: where this runway's own
        # hard pins demand more grade than the table allows, THIS is the
        # row that was infeasible — it is priced at the EFFECTIVE cap.
        # The ruling head is unchanged (``rulesets.runway.longitudinal``,
        # a ``hard_rulings`` head): the law is the same law, at the cap
        # the thresholds leave it.
        lon = cap_of(planar, law, rw.id, rw.code_number, rw.code_letter)
        if lon is None:
            lon = cap.longitudinal
        rs = law.ruleset.runway
        end_cap = rs.end_zone.value(rw.code_number, rw.code_letter)
        if rw.code_number in rs.end_zone_precision_only_codes:
            end_cap = None            # no CIFP category loaded: body cap
        end_len = runway_end_zone_length_m(law, rw.length_m)
        a_xy, b_xy = rw.ends[0].xy, rw.ends[1].xy
        L = rw.length_m
        ux = (b_xy[0] - a_xy[0]) / L if L > 0 else 0.0
        uy = (b_xy[1] - a_xy[1]) / L if L > 0 else 0.0

        def along(v: int) -> float:
            x, y = vw.xy[v]
            return (x - a_xy[0]) * ux + (y - a_xy[1]) * uy

        src = Source(GEN, "rulesets.runway.longitudinal", (f"rwy:{rw.id}",))
        src_end = Source(GEN, "rulesets.runway.end_zone (preference, owner "
                         "2026-07-08 relaxation order)", (f"rwy:{rw.id}",))
        # THE END-ZONE CAP IS A PREFERENCE (owner 2026-07-08): the main cap
        # is law; the first/last-quarter cap yields MINIMALLY, per runway,
        # up to the main cap, when the hard anchors (CIFP pins, seam DEM
        # pins) make both unsatisfiable.  One escalation group per runway.
        soft_g = f"end_zone:{rw.id}"
        # §50.2 Y2: the end-zone preference escalates up to the MAIN cap,
        # and the main cap is the EFFECTIVE one — otherwise a yielded
        # runway is infeasible in its end quarters at a ceiling its own
        # thresholds already refused.
        soft_hi = lon
        chs = sorted(chs, key=lambda c: min(along(c[0]), along(c[-1])))
        chs = [c if along(c[0]) <= along(c[-1]) else list(reversed(c)) for c in chs]
        for prev, nxt in zip(chs, chs[1:]):
            a, b = prev[-1], nxt[0]
            if a != b:
                d = vw.dist(a, b)
                if d > 0.0:
                    s_mid = 0.5 * (along(a) + along(b))
                    in_end = s_mid < end_len or s_mid > L - end_len
                    if in_end and end_cap is not None:
                        rows.append(Diff(a, b, end_cap, d, src_end, soft_g, soft_hi))
                    else:
                        rows.append(Diff(a, b, lon, d, src))
        for ch in chs:
            for a, b in zip(ch, ch[1:]):
                d = vw.dist(a, b)
                if d <= 0.0:
                    continue
                s_mid = 0.5 * (along(a) + along(b))
                in_end = s_mid < end_len or s_mid > L - end_len
                if in_end and end_cap is not None:
                    rows.append(Diff(a, b, end_cap, d, src_end, soft_g, soft_hi))
                else:
                    rows.append(Diff(a, b, lon, d, src))
        # §50 THE YIELDED RUNWAY IS BUILT UNIFORMLY (issue #133)
        rows.extend(yield_envelope(planar, law, vw, rw.id, chs, along))
        # pins: the station nearest each threshold with a CIFP elevation
        all_ids = [v for ch in chs for v in ch]
        for end in rw.ends:
            if end.threshold_elev_m is None:
                continue
            best = _end_vertex(vw, all_ids, rw, end, ux, uy)
            rows.append(Pin(best, float(end.threshold_elev_m),
                            Source(GEN, "RULINGS :511-516 CIFP threshold",
                                   (f"rwy:{rw.id}", f"end:{end.name}",
                                    end.cifp_source))))
    # the apt.dat datum at every unpinned end of a runway with fewer than
    # two CIFP pins (RULINGS 2026-09-30z (2), issue #129) — HARD, as a
    # CIFP threshold is
    cifp_v = {r.v for r in rows if isinstance(r, Pin)}
    for v, (z, rid, ename) in sorted(datum_pins(planar, law, airport).items()):
        if v in cifp_v:
            continue
        rows.append(Pin(v, z, Source(GEN, "RULINGS 2026-09-30z (2) apt.dat datum",
                                     (f"rwy:{rid}", f"end:{ename}", "apt.dat"))))
    return rows


def yield_envelope(planar: PlanarMap, law: Law, vw: View, ref: str,
                   chs: _t.Sequence[_t.Sequence[int]],
                   along: _t.Callable[[int], float]) -> list[Row]:
    """§50 THE YIELDED RUNWAY IS BUILT UNIFORMLY (issue #133; RULINGS
    2026-09-18d (3) "the cap yields, uniformly", 2026-09-30ad): one
    ``Band`` per ridge station strictly between the GOVERNING pins of a
    YIELDED runway, around the pin-to-pin line at the pin grade ``g_pin``
    and no wider than the yield margin reaches from the NEARER pin,

        |z − (z_a + g_pin·d_a)| ≤ runway_yield_margin · min(d_a, d_b)

    with ``d`` the ridge-chord distance (``curve_stations``' own sequence,
    the span §50.1 (3) measured).  The upper side toward either pin is the
    effective cap's own reach (``cap = g_pin + margin``), implied by the
    profile ``Diff`` chain at its bound; the lower side toward the NEARER
    pin is what "uniformly" adds — the ruling's runway takes ONE grade pin
    to pin, the margin being the numerical room around it (§50.1 (3)), not
    a budget the surface may spend on one end.

    WHY IT IS STATED AS A BAND: every profile row is held at ``[design]
    hard_tol_m`` (0.02 m, 0.17 pp over a 12 m chord) — eight times the
    0.02 pp margin — so the rows alone let the ridge spend that tolerance
    on every chord and drift metres off the line the thresholds demand
    (KASE 15/33: 94 rows over the bar, the north end 3.30 m under the
    chord, 2.03–2.39 % built; with the cap's reach alone the design's DEM
    pull still spent the whole 0.43 m of margin at the RWY 15 end, 1.2 %
    off the pin).  A band has no per-chord tolerance to accumulate.  An
    un-yielded runway carries none: its surface does not move."""
    caps = getattr(planar, "runway_caps", None) or {}
    rc = caps.get(ref)
    if rc is None or not rc.yielded or rc.pin_a is None or rc.pin_b is None:
        return []
    min_d = float(law.tables.emit.identity.min_distinct_spacing_m)
    st = curve_stations(vw.xy, chs, along, min_d)
    if len(st) < 3:
        return []

    def station(v: int) -> int:
        try:
            return st.index(v)
        except ValueError:                # merged by the identity floor
            return min(range(len(st)),
                       key=lambda k: (vw.xy[st[k]][0] - vw.xy[v][0]) ** 2
                       + (vw.xy[st[k]][1] - vw.xy[v][1]) ** 2)

    i, j = station(rc.pin_a.vertex), station(rc.pin_b.vertex)
    za, zb = float(rc.pin_a.z), float(rc.pin_b.z)
    if i > j:
        i, j, za, zb = j, i, zb, za
    cum = [0.0]
    for k in range(len(st) - 1):
        cum.append(cum[-1] + vw.dist(st[k], st[k + 1]))
    span = cum[j] - cum[i]
    if span <= 0.0:
        return []
    g = (zb - za) / span
    m = float(law.tables.emit.design.runway_yield_margin)
    src = Source(GEN, "rulesets.runway.longitudinal (§50 yield envelope, "
                 "issue #133)", (f"rwy:{ref}",))
    out: list[Row] = []
    for k in range(i + 1, j):
        da = cum[k] - cum[i]
        line = za + g * da
        w = m * min(da, span - da)
        out.append(Band(st[k], line - w, line + w, src))
    return out


def _foot(vw: View, v: int, chains: list[list[int]]
          ) -> tuple[float, int, int, float] | None:
    """``(lateral distance, ridge a, ridge b, t)`` of the nearest ridge
    point to vertex ``v`` over the runway's chains."""
    best: tuple[float, int, int, float] | None = None
    p = vw.xy[v]
    for ch in chains:
        if len(ch) < 2:
            continue
        d, k, t, _s = project_to_chain(p, [vw.xy[c] for c in ch])
        if best is None or d < best[0]:
            best = (d, ch[k], ch[k + 1], t)
    return best


def runway_half_widths(airport: Airport) -> dict[str, float]:
    """Runway ref -> its own HALF WIDTH (``Runway.slab_corners``' own
    source).  §40 (2) as amended: the line beyond which a runway-family
    vertex is a SHOULDER vertex and takes the shoulder's cross-slope.
    Published in the sidecar (``pipeline.publication``) so the v1 census
    reads the same line the generator did."""
    return {rw.id: rw.width_m / 2.0 for rw in airport.runways}


def crown_drops(planar: PlanarMap, law: Law, airport: Airport,
                z: _t.Sequence[float] | None = None) -> dict[int, float]:
    """Vertex -> crown drop (m) for every runway-family FACE vertex —
    outer and hole rings (``View.face_vertices``) — 0.0 on the ridge: the
    DESIGNED drop ``crown × d`` without ``z``, the BUILT drop
    ``z_foot − z_v`` with it — the sidecar ``crown_drops`` field declares
    the built one."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    crown = law.tables.common.runway_crown_transverse
    half_of = runway_half_widths(airport)
    every = [c for chs in chains.values() for c in chs]
    out: dict[int, float] = {}
    for f in vw.faces_of_role(RUNWAY_FAMILY):
        ref_ids = [f.ref] if f.role == "runway" else f.ref.split("+")
        # §40 (2): THE CROWN STOPS AT THE RUNWAY EDGE — the designed
        # cross-fall is the runway's, between its own edges; a SHOULDER
        # vertex's declared drop is the EDGE's (it keeps the runway's
        # datum), never the crown continued to its own offset
        half = max((half_of.get(r, 0.0) for r in ref_ids), default=0.0)
        own = [c for r in ref_ids for c in chains.get(r, [])]
        if not own:
            continue
        on_ridge = {v for c in every for v in c}
        for v in vw.face_vertices(f.id):
            if v in out:
                continue
            if v in on_ridge:
                out[v] = 0.0
                continue
            # the census reads the NEAREST crown spine of ANY runway
            ft = _foot(vw, v, every if z is not None else own)
            if ft is None:
                continue
            if z is None:
                d0 = min(ft[0], half) if half > 0.0 else ft[0]
                out[v] = round(crown * d0, 6)
            else:
                d, a, b, t = ft
                out[v] = round((1.0 - t) * z[a] + t * z[b] - z[v], 6)
    return out


def runway_crown(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Every off-ridge runway-family FACE vertex — outer and hole rings
    (``View.face_vertices``) — sits at least ``crown × d`` below the ridge
    at its foot (family ``runway_crown``, 2026-08-05; solver mode
    ``offset``)."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    crown = law.tables.common.runway_crown_transverse
    half_of = runway_half_widths(airport)
    rows: list[Row] = []
    done: set[int] = set()
    for f in vw.faces_of_role(RUNWAY_FAMILY):
        ref_ids = [f.ref] if f.role == "runway" else f.ref.split("+")
        # §40 (2): the crown floor stops at the runway edge (see
        # ``crown_drops``); beyond it the shoulder keeps the edge's datum
        half = max((half_of.get(r, 0.0) for r in ref_ids), default=0.0)
        chs = [c for r in ref_ids for c in chains.get(r, [])]
        if not chs:
            continue
        own_ridge = {v for c in chs for v in c}
        src = Source(GEN, "common.runway_crown_transverse", (f"face:{f.id}", f.ref))
        for v in vw.face_vertices(f.id):
            if v in done or v in own_ridge:
                continue
            ft = _foot(vw, v, chs)
            if ft is None or ft[0] <= 0.0:
                continue
            done.add(v)
            d, a, b, t = ft
            drop = crown * (min(d, half) if half > 0.0 else d)
            terms = ((v, 1.0), (a, -(1.0 - t)), (b, -t))
            if t <= 0.0:
                terms = ((v, 1.0), (a, -1.0))
            elif t >= 1.0:
                terms = ((v, 1.0), (b, -1.0))
            # THE CROWN FLOOR IS A PREFERENCE (M2 dev. 4 declared the built
            # drop; M3a: where a seam DEM pin holds the edge higher than the
            # floor allows, the floor yields — per vertex, by the minimum —
            # and the built drop is what v2 declares)
            rows.append(Linear(terms, None, -drop, src, f"crown:{v}", drop))
    return rows


def runway_transverse(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The runway TRANSVERSE MAXIMUM as HARD law (RULINGS 2026-09-05o; spec
    ``runway-transverse-max-spec.md`` §3): for every off-ridge ``runway``
    FACE vertex ``v`` (outer and hole rings, ``View.face_vertices``) with
    foot ``(a, b, t)`` at lateral distance ``d`` on
    its OWN ridge chain (the crown's ``_foot``), one two-sided ``Linear``

        −cap·d ≤ (1 − t)·z_a + t·z_b − z_v ≤ cap·d

    (``cap = rulesets.runway.transverse_max`` by code letter).  The row
    carries the runway face, so the tier machinery holds it in tier 0 and
    the last resort never relaxes it; a taxiway sharing the edge conforms
    and carries the relief into its body at its own cap (owner 03k/04i).
    Crossing-ring vertices are exempt (§3.1.19; the verify scope)."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    half_of = runway_half_widths(airport)
    xing: set[int] = set()
    for f in vw.faces_of_role(("runway_crossing",)):
        xing.update(vw.face_vertices(f.id))
    rows: list[Row] = []
    done: set[int] = set()
    for f in vw.faces_of_role(("runway",)):
        chs = chains.get(f.ref, [])
        if not chs:
            continue
        half = half_of.get(f.ref, 0.0)
        own_ridge = {v for c in chs for v in c}
        src = Source(GEN, "rulesets.runway.transverse_max (2026-09-05o)",
                     (f"face:{f.id}", f.ref))
        for v in vw.face_vertices(f.id):
            if v in done or v in own_ridge or v in xing:
                continue
            ft = _foot(vw, v, chs)
            if ft is None or ft[0] <= 0.0:
                continue
            done.add(v)
            d, a, b, t = ft
            # §40 (2) as amended (13dd) and RULINGS 2026-09-30ak: the
            # runway's cross-fall over its own half-width, the SHOULDER's
            # only for the distance beyond it — ONE continuous bound in
            # metres (``law.tables.runway_transverse_bound``), the reading
            # the verify prices through as well
            bound = runway_transverse_bound(law, d, half, f.code_letter,
                                            f.code_number)
            if bound is None:
                continue
            if t <= 0.0:
                terms = ((a, 1.0), (v, -1.0))
            elif t >= 1.0:
                terms = ((b, 1.0), (v, -1.0))
            else:
                terms = ((a, 1.0 - t), (b, t), (v, -1.0))
            rows.append(Linear(terms, -bound, bound, src))
    return rows


def curve_stations(xy: _t.Sequence[tuple[float, float]], chains: _t.Sequence[_t.Sequence[int]],
                   along: _t.Callable[[int], float], min_d: float) -> list[int]:
    """ONE station sequence for a runway's profile: its chains ordered
    and oriented along the axis, joined end to end (a chain split at a
    crossing continues the law, as the profile's bridging ``Diff``
    does), stations closer than ``min_d`` to the last kept one dropped
    (the identity floor — a noding sliver would otherwise state a rate
    over a metre).  Shared by the generator and the verify reader."""
    chs = sorted((list(c) for c in chains if len(c) >= 2),
                 key=lambda c: min(along(c[0]), along(c[-1])))
    chs = [c if along(c[0]) <= along(c[-1]) else list(reversed(c)) for c in chs]
    out: list[int] = []
    for ch in chs:
        for v in ch:
            if out and (v == out[-1] or math.dist(xy[v], xy[out[-1]]) < min_d):
                continue
            out.append(v)
    return out


def runway_vertical_curve(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The vertical-curve law as HARD runway-tier rows (module docstring):
    for stations ``(p, c, n)`` with spacings ``d1``, ``d2``,

        −b ≤ (z_n − z_c)/d2 − (z_c − z_p)/d1 ≤ b,
        b = runway_vertical_curve_bound(law, (d1 + d2)/2, code)

    — a three-term ``Linear`` whose vertices are all ridge stations, so
    the tier machinery holds it in the runway tier and the last resort
    never relaxes it."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rows: list[Row] = []
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs:
            continue
        a_xy, b_xy = rw.ends[0].xy, rw.ends[1].xy
        L = rw.length_m
        ux = (b_xy[0] - a_xy[0]) / L if L > 0 else 0.0
        uy = (b_xy[1] - a_xy[1]) / L if L > 0 else 0.0

        def along(v: int) -> float:
            x, y = vw.xy[v]
            return (x - a_xy[0]) * ux + (y - a_xy[1]) * uy

        st = curve_stations(vw.xy, chs, along, min_d)
        src = Source(GEN, "rulesets.runway.vertical_curve_k_m / max_grade_change "
                     "(§3.1.15-16, 2026-09-06b)", (f"rwy:{rw.id}",))
        for p, c, n in zip(st, st[1:], st[2:]):
            d1 = vw.dist(p, c)
            d2 = vw.dist(c, n)
            if d1 <= 0.0 or d2 <= 0.0:
                continue
            b = runway_vertical_curve_bound(law, 0.5 * (d1 + d2), rw.code_number,
                                            rw.code_letter)
            if b is None:
                continue
            terms = ((p, 1.0 / d1), (c, -(1.0 / d1 + 1.0 / d2)), (n, 1.0 / d2))
            rows.append(Linear(terms, -b, b, src))
    return rows


def runway_within_shape(planar: PlanarMap, law: Law, airport: Airport
                        ) -> list[Row]:
    """``runway_crossing`` ring pairs in FOOT space: with the built drop
    declared, the census prices ``|z_foot(a) − z_foot(b)|`` against the
    cap over the pair's distance — stated here over the feet's ridge
    interpolations (``runway`` rings are implied by the profile caps)."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rows: list[Row] = []
    # ``runway`` rings: the ADJACENT ring chords at the longitudinal cap
    # (M3a: the profile implies them only while the crown floor holds; at
    # a tile seam the floor yields to the DEM and the census still prices
    # the adjacent-station ring pair at the body cap)
    for f in vw.faces_of_role(("runway",)):
        # §50.2 Y3: the ring chords are TARGETS pulling the ring onto the
        # profile — un-yielded they would pull it OFF the line its own
        # pins demand.  ``vw.caps`` already carries the effective cap
        # (``precedence.face_cap`` with the map), so this reads it.
        caps = vw.caps[f.id]
        if caps is None:
            continue
        ring = vw.rings[f.id]
        src = Source(GEN, "rulesets.runway.longitudinal ring chord", (f"face:{f.id}", f.ref))
        n = len(ring)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            d = vw.dist(a, b)
            if d >= min_d and a != b:
                rows.append(Diff(a, b, caps[0], d, src))
    for f in vw.faces_of_role(("runway_crossing",)):
        # §50.2 Y3 / §50.1 (4): a crossing face reads the MAX over its two
        # runways, which ``face_cap`` composed into ``vw.caps``.
        caps = vw.caps[f.id]
        if caps is None:
            continue
        chs = [c for r in f.ref.split("+") for c in chains.get(r, [])]
        if not chs:
            continue
        ring = vw.rings[f.id]
        own_ridge = {v for c in chs for v in c}
        foot: dict[int, tuple[tuple[int, float], ...]] = {}
        for v in ring:
            if v in own_ridge:
                foot[v] = ((v, 1.0),)
                continue
            ft = _foot(vw, v, chs)
            if ft is None:
                foot[v] = ((v, 1.0),)
            else:
                _d, a, b, t = ft
                foot[v] = ((a, 1.0 - t), (b, t)) if 0.0 < t < 1.0 else \
                    ((a, 1.0),) if t <= 0.0 else ((b, 1.0),)
        src = Source(GEN, "rulesets.runway.longitudinal within_shape (crossing)",
                     (f"face:{f.id}", f.ref))
        n = len(ring)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = ring[i], ring[j]
                d = vw.dist(a, b)
                if d < min_d:
                    continue
                terms: dict[int, float] = {}
                for v, c in foot[a]:
                    terms[v] = terms.get(v, 0.0) + c
                for v, c in foot[b]:
                    terms[v] = terms.get(v, 0.0) - c
                terms = {v: c for v, c in terms.items() if abs(c) > 1e-12}
                if not terms:
                    continue
                bound = caps[0] * d
                rows.append(Linear(tuple(terms.items()), -bound, bound, src))
    return rows
