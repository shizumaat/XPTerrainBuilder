"""RUNWAY generator — the profile is the datum (H7 / RULINGS :511-516):
CIFP thresholds are absolute pins, the profile flexes between them within
the runway's longitudinal law only, the slab crowns off the profile.

Rows (all from ``rulesets.<authority>.runway`` and
``common.runway_crown_transverse``):

* ``Pin`` at the profile station nearest each threshold with a CIFP
  elevation (``RunwayEnd.threshold_elev_m``; an end without one has one
  pin fewer, never an invented one — plan §2);
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
                          runway_transverse_cap,
                          runway_transverse_max, runway_vertical_curve_bound)
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Pin, Row, Source
from ..model.planar import PlanarMap
from .geometry import project_to_chain
from .precedence import View, cap_of, view

__all__ = ["threshold_pins", "runway_profile", "runway_crown", "runway_transverse",
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


def threshold_pins(planar: PlanarMap, law: Law, airport: Airport) -> dict[int, float]:
    """Vertex -> CIFP threshold elevation: the profile station nearest
    each threshold (displacement applied) that carries one — THE hard
    terminals of the airport (RULINGS :511-516), read here by the pin
    rows and by the route reach (``no_step.reach_bands``)."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    out: dict[int, float] = {}
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs:
            continue
        a_xy, b_xy = rw.ends[0].xy, rw.ends[1].xy
        L = rw.length_m
        ux = (b_xy[0] - a_xy[0]) / L if L > 0 else 0.0
        uy = (b_xy[1] - a_xy[1]) / L if L > 0 else 0.0
        all_ids = [v for ch in chs for v in ch]
        for end in rw.ends:
            if end.threshold_elev_m is None:
                continue
            sign = 1.0 if end is rw.ends[0] else -1.0
            tx = end.xy[0] + sign * ux * end.displaced_m
            ty = end.xy[1] + sign * uy * end.displaced_m
            best = min(all_ids, key=lambda v: (vw.xy[v][0] - tx) ** 2
                       + (vw.xy[v][1] - ty) ** 2)
            out[best] = float(end.threshold_elev_m)
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
        # pins: the station nearest each threshold with a CIFP elevation
        all_ids = [v for ch in chs for v in ch]
        for end in rw.ends:
            if end.threshold_elev_m is None:
                continue
            sign = 1.0 if end is rw.ends[0] else -1.0
            tx = end.xy[0] + sign * ux * end.displaced_m
            ty = end.xy[1] + sign * uy * end.displaced_m
            best = min(all_ids, key=lambda v: (vw.xy[v][0] - tx) ** 2
                       + (vw.xy[v][1] - ty) ** 2)
            rows.append(Pin(best, float(end.threshold_elev_m),
                            Source(GEN, "RULINGS :511-516 CIFP threshold",
                                   (f"rwy:{rw.id}", f"end:{end.name}",
                                    end.cifp_source))))
    return rows


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
            # §40 (2) as amended: the runway's 1.5 % inside its own
            # half-width, the SHOULDER's 2.5 % beyond it — the one reading
            # (``law.tables.runway_transverse_cap``) the verify and the v1
            # census price through as well
            cap = runway_transverse_cap(law, d, half, f.code_letter,
                                        f.code_number)
            if cap is None:
                continue
            bound = cap * d
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
