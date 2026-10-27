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
  authority states one (``tables.runway_end_zone_cap``: ICAO code 3 only
  at an end the witness reads Cat II/III, audit row 13);
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

import dataclasses as _dc
import math
import typing as _t

from ..law import Law, inset_class
from ..law.tables import (
    FLAT_CLASS_FINE,
    FLAT_CLASS_LIDAR,
    role_cap,
    runway_end_zone_cap,
    runway_end_zone_grade_change,
    runway_end_zone_length_m,
    runway_transverse_bound,
    runway_transverse_max,
    runway_vertical_curve_bound,
)
from ..model.airport import PIN_OUTVOTED, Airport
from ..model.constraints import Band, Diff, Linear, Pin, Row, Source
from ..model.planar import PlanarMap
from .geometry import project_to_chain
from .precedence import View, cap_of, view
from .trend import trend_of as _trend_of

__all__ = ["threshold_pins", "datum_pins", "end_pin_cases", "EndPin", "dem_degraded",
           "runway_profile", "runway_crown", "runway_transverse",
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
    """The profile station nearest ``end``'s pin — where that end's pin
    sits, CIFP or datum: the joined CIFP record's OWN landing threshold
    projected onto the axis (issue #1358, ``RunwayEnd.pin_along``), else
    the apt.dat end advanced by its displaced length."""
    sign = 1.0 if end is rw.ends[0] else -1.0
    d = end.pin_along() if hasattr(end, "pin_along") else float(end.displaced_m)
    tx = end.xy[0] + sign * ux * d
    ty = end.xy[1] + sign * uy * d
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
    for e in rw.ends:
        end_cap = runway_end_zone_cap(law, rw.code_number, rw.code_letter,
                                      bool(getattr(e, "cat_ii_iii", False)))
        if end_cap is not None:
            lim = min(lim, end_cap)
    return lim


#: THE CASES of an end the DEM or the datum values (``end_pin_cases``;
#: spec ``docs/findings/lrwypin-runway-end-pins.md`` §3)
CASE_DATUM = "datum"            # F: the apt.dat datum line (30z (2))
CASE_UNMATCHED = "unmatched"    # D / D': no CIFP here, the other end pinned (22a)
CASE_FLAGGED = "flagged"        # C: a flagged CIFP end the DEM decides (25a)
CASE_LIDAR = "lidar"            # E: an apt.dat-only end the lidar outvotes (26e)
CASE_GROUND = "ground"          # E': an apt.dat-only end a fine DEM outvotes (28m, 28o)


@_dc.dataclass(frozen=True)
class EndPin:
    """One end :func:`datum_pins` valued: the pin, its case, the apt.dat
    datum line's value there and the DEM read the case took."""

    z: float
    runway: str
    end: str
    case: str
    datum_z: float | None
    dem_z: float | None


def datum_pins(planar: PlanarMap, law: Law, airport: Airport
               ) -> dict[int, tuple[float, str, str]]:
    """THE ENDS WITH NO SURVEYED VALUE: vertex -> ``(z, runway id, end
    name)`` (:func:`end_pin_cases` is the same map with each end's case)."""
    return {v: (p.z, p.runway, p.end)
            for v, p in end_pin_cases(planar, law, airport).items()}


def end_pin_cases(planar: PlanarMap, law: Law, airport: Airport) -> dict[int, EndPin]:
    """THE ONE SITE THAT VALUES AN END NO SURVEY PINS: vertex -> :class:`EndPin`
    at every end of a runway whose ``threshold_elev_m`` is ``None`` (no CIFP
    record, or a CIFP value ``airport/end_pins`` flagged).

    THE APT.DAT DATUM (owner RULINGS 2026-09-30z (2), issue #129):
    "If there's no CIFP data, runway elevations must be in the apt.dat":
    the LEVEL is the apt.dat airport elevation record (the header row;
    runway rows carry none — ``Airport.elevation_m``), which is the
    HIGHEST point of the landing area, so the runway's HIGHER threshold
    sits at it LESS the ground's fall from the airport's highest point to
    that threshold (issue #941: the record names ONE point; a second
    runway lying 7 m below it was pinned at it, and the hard pin lifted
    the primary runway 4.5 m mid-length) — read off the §21 trends of
    EVERY runway's ridge, CIFP-pinned or not (:func:`_relief_below_top`;
    zero for the runway carrying the highest point, so a one-runway
    airport is unchanged); the TILT is the §21 long-wave DEM trend's mean
    slope along the runway's own ridge, bounded by the runway's own
    longitudinal (and end-zone) cap; on a DEGRADED frame, or a ridge the
    trend cannot fit, the runway is LEVEL at the datum (never an invented
    tilt, §21.2 (2)).

    THE CASES (spec ``docs/findings/lrwypin-runway-end-pins.md`` §3):

    * ``unmatched`` (owner RULINGS 2026-10-22a, issue #1238): with a
      SURVEYED pin on the runway (CIFP, or a cross-check value), an end
      with no CIFP record FOLLOWS THE DEM (:func:`_dem_at_end`), pulled
      toward the surveyed pin until the chord between them sits within the
      cap — never the apt.dat header (CYYJ's header reads 19 ft against
      thresholds of 44 and 58 ft).  Beside a ``flagged`` end, there is no
      survey to pull toward, so the DEM stands.
    * ``flagged`` (owner RULINGS 2026-10-25a, issue #1342): a CIFP end
      verification refused and no cross-check source resolved follows the
      DEM with NO cap clamp — the caps yield to it as to any hard pin
      (09-18d (3)).  VNLK, CBR2: placeholder thresholds at the field
      elevation on runways the DEM shows climbing.  On a DEGRADED frame
      the CIFP value as read stands (a degraded DEM is no witness).
    * ``lidar`` / ``ground`` (owner RULINGS 2026-10-26e, issue #1394;
      2026-10-28m, issue #1348): on a runway with no CIFP record at all,
      an end whose datum line stands off the DEM by more than its source
      class's noise (``runway_ends.dem_noise_m``, the class
      ``law/inset_class.ground_class`` reads — the same class rule
      ``airport/end_pins`` judges CIFP by) follows the DEM: ``lidar`` over
      a credible lidar inset, ``ground`` over a fine one (PAAQ
      16S/34S: 0.9 to 1.7 m under the lidar).  A sampler stating no class
      is no witness of known quality: the datum stands.  An end whose CIFP
      record the terrain witness outvoted (owner RULINGS 2026-10-26v,
      ``PIN_OUTVOTED``) follows the lidar with no noise floor.
      COARSE ground never outvotes the record (owner RULINGS 2026-10-28o:
      on a 30 m DEM the DEM is often the less reliable side) — the
      datum stands there, however far off.
    * ``datum``: otherwise the datum line (30z (2), unchanged).

    These are HARD pins, exactly a CIFP threshold's (``threshold_pins``
    merges them): no stage-1 perturbation moves the runway (the #117
    floating-runway lesson, 30q), and every pin consumer — the pin rows,
    the chord/trend target, the route reach, the §50 cap yield — reads
    them as terminals.

    An airport whose apt.dat carries no finite elevation record REFUSES
    where an end needs the datum line (``ValueError`` naming the airport)
    — never a silently free runway."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    out: dict[int, EndPin] = {}
    degraded = dem_degraded(airport)
    window = float(law.tables.emit.design.runway_profile_window_m)
    needs = any(e.threshold_elev_m is None for rw in airport.runways
                if chains.get(rw.id) for e in rw.ends)
    trends = ({} if degraded or not needs
              else _ridge_trends(planar, vw, airport, chains, window))
    klass = (inset_class.ground_class(airport, law) if not degraded and needs
             else None)
    # 28o: only lidar and fine ground outvote the apt.dat record
    noise = (float(law.tables.runway_ends.dem_noise_m.of(klass))
             if klass in (FLAT_CLASS_LIDAR, FLAT_CLASS_FINE) else None)
    ground_case = CASE_LIDAR if klass == FLAT_CLASS_LIDAR else CASE_GROUND
    for rw in airport.runways:
        chs = chains.get(rw.id)
        L = rw.length_m
        if not chs or L <= 0.0:
            continue
        surveyed = [e for e in rw.ends if e.threshold_elev_m is not None]
        if len(surveyed) >= 2:
            continue
        flagged = [e for e in rw.ends if getattr(e, "pin_source", "") == "dem"]
        a_xy, ux, uy = _axis(rw)

        def along(v: int) -> float:
            x, y = vw.xy[v]
            return (x - a_xy[0]) * ux + (y - a_xy[1]) * uy

        all_ids = [v for ch in chs for v in ch]
        end_v = {e.name: _end_vertex(vw, all_ids, rw, e, ux, uy) for e in rw.ends}
        t = trends.get(rw.id)
        line = (None if surveyed or flagged
                else _datum_line(airport, law, rw, t, trends, end_v, along))
        pinned = [(end_v[e.name], float(e.threshold_elev_m)) for e in surveyed]
        lim = _datum_slope_cap(law, rw)
        for end in rw.ends:
            if end.threshold_elev_m is not None:
                continue
            v = end_v[end.name]
            dem = None if degraded else _dem_at_end(planar, t, along(v), v, None)
            if end in flagged:
                z = (float(getattr(end, "cifp_elev_m", None)) if degraded or dem is None
                     else dem)
                out[v] = EndPin(z, rw.id, end.name, CASE_FLAGGED, None, dem)
                continue
            if surveyed or flagged:
                # 22a: the DEM, else (degraded / no sample) the datum line
                z = dem if dem is not None else _datum_line(
                    airport, law, rw, t, trends, end_v, along)(v)
                for vp, zp in pinned:
                    if lim is None or vp == v:
                        continue
                    reach = lim * abs(along(v) - along(vp))
                    z = max(zp - reach, min(zp + reach, z))
                out[v] = EndPin(z, rw.id, end.name, CASE_UNMATCHED, None, dem)
                continue
            zd = line(v)
            # 26v (#1359): an end whose CIFP record the layout and the imagery
            # outvoted "follows the lidar" — the datum line is no survey,
            # so no noise floor keeps it (KDIJ 22: 0.41 m under the lidar)
            outvoted = (klass == FLAT_CLASS_LIDAR
                        and getattr(end, "pin_flags", "") == PIN_OUTVOTED)
            if noise is not None and dem is not None and (outvoted or abs(zd - dem) > noise):
                out[v] = EndPin(dem, rw.id, end.name, ground_case, zd, dem)
            else:
                out[v] = EndPin(zd, rw.id, end.name, CASE_DATUM, zd, dem)
    return out


def _datum_line(airport: Airport, law: Law, rw, t, trends: dict, end_v: dict,
                along: _t.Callable[[int], float]) -> _t.Callable[[int], float]:
    """THE APT.DAT DATUM LINE of runway ``rw`` (30z (2), :func:`end_pin_cases`):
    vertex -> its value.  Refuses an airport with no elevation record."""
    elev = getattr(airport, "elevation_m", None)
    if elev is None or not math.isfinite(float(elev)):
        raise ValueError(
            f"{airport.icao}: runway {rw.id} has fewer than two CIFP "
            f"threshold pins and the apt.dat airport header carries no "
            f"elevation record ({elev!r}) — RULINGS 2026-09-30z (2) "
            f"refuses a free runway (issue #129)")
    lim = _datum_slope_cap(law, rw)
    slope = 0.0
    if lim is not None and t is not None:
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
    s_top = max((along(v) for v in end_v.values()), key=lambda q: slope * q)
    level = float(elev) - _relief_below_top(trends, rw.id, s_top)
    return lambda v: level + slope * (along(v) - s_top)


def _dem_at_end(planar: PlanarMap, trend, s: float, v: int,
                fallback: float | None) -> float | None:
    """THE GROUND AT AN UNMATCHED END of a runway with one CIFP pin (owner
    RULINGS 2026-10-22a, "I would have expected it to move toward DEM, not
    0"): the §21 trend at the end's station, else the end vertex's own DEM,
    else ``fallback`` (the apt.dat datum line; a DEGRADED frame never comes
    here, §21.2 (2))."""
    if trend is not None:
        z = trend.at(min(max(s, trend.s[0]), trend.s[-1]))
        if z is not None:
            return float(z)
    dz = planar.vertices[v].dem_z
    return float(dz) if dz is not None else fallback


def _ridge_trends(planar: PlanarMap, vw: View, airport: Airport,
                  chains: dict[str, list[list[int]]], window: float) -> dict:
    """Runway id -> the §21 long-wave DEM trend along its ridge (stations
    from the runway's FIRST end), for every runway whose ridge fits one."""
    out = {}
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs or rw.length_m <= 0.0:
            continue
        a_xy, ux, uy = _axis(rw)
        t = _trend_of((((vw.xy[v][0] - a_xy[0]) * ux + (vw.xy[v][1] - a_xy[1]) * uy,
                        float(planar.vertices[v].dem_z))
                       for ch in chs for v in ch
                       if planar.vertices[v].dem_z is not None), window)
        if t is not None:
            out[rw.id] = t
    return out


def _relief_below_top(trends: dict, rid: str, s_top: float) -> float:
    """How far runway ``rid``'s trend at station ``s_top`` lies below the
    HIGHEST trend point of any runway of the airport — where the apt.dat
    elevation record (the highest point of the landing area) belongs.
    Zero when this runway carries that point, or when either is unread."""
    t = trends.get(rid)
    here = t.at(min(max(s_top, t.s[0]), t.s[-1])) if t is not None else None
    tops = [z for tr in trends.values() for q in tr.s
            if (z := tr.at(q)) is not None]
    if here is None or not tops:
        return 0.0
    return max(0.0, max(tops) - float(here))


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
    from .threshold_seam import RULING as SEAM_YIELD_RULING
    from .threshold_seam import seam_thresholds
    vw = view(planar, law)
    rows: list[Row] = []
    chains = ridge_chains(vw)
    # OWNER RULINGS 2026-10-26b: a threshold the tile seam outranks is
    # minted under the yielding head (``threshold_seam``)
    seam_yield = seam_thresholds(planar, law, airport)
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
        # EACH END ITS OWN END-ZONE CAP (audit row 13): at a code the table
        # binds at Cat II/III only (ICAO code 3, §3.1.14) the cap holds at
        # an end the witness reads Cat II/III (RULINGS 2026-10-15m (2))
        cap_a, cap_b = (runway_end_zone_cap(law, rw.code_number, rw.code_letter,
                                            bool(getattr(e, "cat_ii_iii", False)))
                        for e in rw.ends)
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
                    end_cap = cap_a if s_mid < end_len else (cap_b if s_mid > L - end_len else None)
                    if end_cap is not None:
                        rows.append(Diff(a, b, end_cap, d, src_end, soft_g, soft_hi))
                    else:
                        rows.append(Diff(a, b, lon, d, src))
        for ch in chs:
            for a, b in zip(ch, ch[1:]):
                d = vw.dist(a, b)
                if d <= 0.0:
                    continue
                s_mid = 0.5 * (along(a) + along(b))
                end_cap = cap_a if s_mid < end_len else (cap_b if s_mid > L - end_len else None)
                if end_cap is not None:
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
            src_name = getattr(end, "pin_source", "") or "cifp"
            rows.append(Pin(best, float(end.threshold_elev_m),
                            Source(GEN, SEAM_YIELD_RULING if best in seam_yield
                                   else _CASE_RULING.get(src_name, _CASE_RULING["crosscheck"]),
                                   (f"rwy:{rw.id}", f"end:{end.name}",
                                    end.cifp_source if src_name in _CIFP_SOURCES else src_name))))
    # every end no survey pins (``end_pin_cases``: the apt.dat datum, 22a's
    # DEM end, a flagged CIFP end, 26e's lidar yield) — HARD, as a CIFP
    # threshold is
    cifp_v = {r.v for r in rows if isinstance(r, Pin)}
    for v, p in sorted(end_pin_cases(planar, law, airport).items()):
        if v in cifp_v:
            continue
        rows.append(Pin(v, p.z, Source(GEN, _CASE_RULING[p.case],
                                       (f"rwy:{p.runway}", f"end:{p.end}", p.case))))
    return rows


#: The ``pin_source`` values whose value IS a CIFP record's
_CIFP_SOURCES = ("cifp", "cifp_line")

#: The ``Source.ruling`` of each end case's pin row.
_CASE_RULING = {
    "cifp": "RULINGS :511-516 CIFP threshold",
    "cifp_line": "RULINGS :511-516 CIFP threshold line (shifted runway, #1358)",
    CASE_DATUM: "RULINGS 2026-09-30z (2) apt.dat datum",
    CASE_UNMATCHED: "RULINGS 2026-10-22a unmatched end follows the DEM",
    CASE_FLAGGED: "RULINGS 2026-10-25a flagged CIFP end follows the DEM",
    CASE_LIDAR: "RULINGS 2026-10-26e apt.dat end gives way to the lidar",
    CASE_GROUND: "RULINGS 2026-10-28m apt.dat end yields to the survey ground",
    "crosscheck": "RULINGS 2026-10-25a / 26a cross-check source",
}


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
    # RULINGS 2026-10-26n: a steep runway's envelope follows its DESIGNED
    # profile (junction flats eased by vertical curves), not the straight
    # line (``runway_junctions.design``, carried on the record)
    designed = rc.profile_z or {}
    out: list[Row] = []
    for k in range(i + 1, j):
        da = cum[k] - cum[i]
        line = designed.get(st[k], za + g * da)
        w = m * min(da, span - da)
        out.append(Band(st[k], line - w, line + w, src))
    for jn in rc.junctions:
        # every ridge chord inside a junction span at that junction's cap
        # — the joining taxiway's transverse maximum (Q161 (a))
        jsrc = Source(GEN, "rulesets.runway.longitudinal",
                      (f"rwy:{ref}", "junction flat (RULINGS 2026-10-26n)",
                       *(f"face:{f}" for f in jn.faces)))
        for k in range(i, j):
            a0, a1 = cum[k] - cum[i], cum[k + 1] - cum[i]
            d = cum[k + 1] - cum[k]
            if d > 0.0 and a0 >= jn.u0 - 1e-6 and a1 <= jn.u1 + 1e-6:
                out.append(Diff(st[k], st[k + 1], jn.t, d, jsrc))
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


def _transverse_owners(vw, chains: dict, half_of: dict) -> dict[int, str]:
    """A vertex on the faces of TWO runways belongs to the runway whose own
    edge it lies on (#1149): the one it lies least far beyond the
    half-width of (``d − half``, measured to each runway's own ridge).  A
    runway's shoulder that reaches a parallel runway does not hold that
    runway's edge to its own cross-fall.  Vertices on one runway's faces
    only are not listed (their face owns them)."""
    best: dict[int, tuple[float, str]] = {}
    seen: dict[int, set[str]] = {}
    for f in vw.faces_of_role(("runway",)):
        chs = chains.get(f.ref, [])
        if not chs:
            continue
        half = half_of.get(f.ref, 0.0)
        for v in vw.face_vertices(f.id):
            ft = _foot(vw, v, chs)
            if ft is None:
                continue
            seen.setdefault(v, set()).add(f.ref)
            beyond = ft[0] - half
            if v not in best or beyond < best[v][0]:
                best[v] = (beyond, f.ref)
    return {v: best[v][1] for v, refs in seen.items() if len(refs) > 1}


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
    from .shoulder_crossing import crossed_shoulder_caps
    vw = view(planar, law)
    chains = ridge_chains(vw)
    half_of = runway_half_widths(airport)
    crossed = crossed_shoulder_caps(planar, law, airport)   # 16a (i)
    xing: set[int] = set()
    for f in vw.faces_of_role(("runway_crossing",)):
        xing.update(vw.face_vertices(f.id))
    rows: list[Row] = []
    done: set[int] = set()
    owner = _transverse_owners(vw, chains, half_of)
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
            if owner.get(v, f.ref) != f.ref:
                continue           # another runway's own edge (#1149)
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
                                            f.code_number, crossed.get(v))
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
        # RULINGS 2026-10-26n: the K a steep runway's junction curves
        # yielded to (``None``: the law's own)
        yk = getattr((getattr(planar, "runway_caps", None) or {}).get(rw.id),
                     "curve_k_m", None)
        # NO GRADE CHANGE IN THE END ZONES (FAA AC 150/5300-13B §3.16.1 C-E
        # std 2; audit §4 M2): a PREFERENCE under the end-zone head — hard
        # at the curve bound, preferring ``g0`` — one escalation group per
        # runway, as the end-zone cap (owner 2026-07-08 relaxation order)
        g0 = runway_end_zone_grade_change(law, rw.code_number, rw.code_letter)
        end_len = runway_end_zone_length_m(law, rw.length_m)
        src_end = Source(GEN, "rulesets.runway.end_zone (no grade change, AC "
                         "150/5300-13B §3.16.1)", (f"rwy:{rw.id}",))
        for p, c, n in zip(st, st[1:], st[2:]):
            d1 = vw.dist(p, c)
            d2 = vw.dist(c, n)
            if d1 <= 0.0 or d2 <= 0.0:
                continue
            b = runway_vertical_curve_bound(law, 0.5 * (d1 + d2), rw.code_number,
                                            rw.code_letter, yield_k_m=yk)
            if b is None:
                continue
            terms = ((p, 1.0 / d1), (c, -(1.0 / d1 + 1.0 / d2)), (n, 1.0 / d2))
            rows.append(Linear(terms, -b, b, src))
            s_c = along(c)
            if g0 is not None and g0 < b and (s_c < end_len or s_c > L - end_len):
                rows.append(Linear(terms, -g0, g0, src_end,
                                   soft=f"end_zone_curve:{rw.id}", ceiling=b - g0))
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
