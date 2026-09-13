"""THE TAXI CHAIN'S TARGET PROFILE — the ground's long-wave trend along
every taxi centreline (owner RULINGS 2026-09-10v (1); spec §8.6).

09b (2) ruled taxiways are DESIGNED LIKE RUNWAYS.  §8.2 (1) gave them the
runway's K pattern — a second difference along the centreline chain, RHS
0 — which is CURVATURE and has no level, so 10o measured CYXY's 1,664 m
parallel extrapolating its level from its far contact while the ground
rose under it, and 10t measured SPJC's `pav49` with the right MEAN and no
TILT.  Round 1's answer (one mean row per taxi BODY) was too coarse: a
taxi body is the whole connected taxi network (CYXY: ONE 853-vertex
body), and an airport-wide level cannot fix a local tilt (10v).

A runway gets its level from its threshold chord.  A taxiway has no
thresholds, so its level comes from the SAME place the runway's shape now
does (§21): the ground's LONG-WAVE TREND along its own chain — a moving
quadratic least-squares fit of the production DEM over
±`[design] runway_profile_window_m` (`constraints/trend.py`, the one
construction), TRICUBE-weighted.  Where the chain touches a RUNWAY the
contact is hard and flush (the runway is senior, its crown is the value),
so the trend is SHIFTED LINEARLY through those contacts exactly as §21
shifts through the threshold pins; a chain touching no runway takes the
fit unshifted.  A linear correction leaves the fit's second derivative
untouched, so a contact costs the profile no curvature.

The targets are published as ``PlanarMap.taxi_trend_z`` — a channel of
its own, never ``preferred_z``, because the two are priced differently:
``preferred_z`` is the runway's ``[design] chord`` (300) and the core's
road profile (``road``), while the taxi trend is WEAK
(``[design] taxi_trend``, below ``body_datum``).  The chain's own
second-difference rows (``taxi_profile``) stay: the trend says WHERE the
chain runs, the curvature row says HOW SMOOTHLY.

THE WHOLE FACE FOLLOWS THE TREND, NOT ONLY ITS SPINE (spec §8.6.1, round
3).  Round 2 priced the trend on the CENTRELINE row only, so the taxi
body's off-centreline vertices carried no binding at all (``why``:
"binding 0 — FREE") and where the ground rises ACROSS the body's width
the edge lagged: CYXY's parallel read −1.80 / −1.93 m against the DEM at
the 320 / 330 m stations of the owner's transect while its centreline sat
inside ±0.9 m.  Every vertex of a taxi-family face now carries the SAME
row family at the SAME weight, its target the chain's trend value at the
vertex's OWN STATION — the station of its FOOT on the nearest chain, so a
cross-section is handed one value and the transverse law (which owns the
crown and the cross-fall) is left to shape it.  The reach is
``[design] taxi_trend_face_reach_m``: a taxi-family vertex further than
that from every centreline is left free rather than pulled to a chain it
does not belong to.

THE GROUND ENTERS PAVEMENT ONLY THROUGH LONG-WAVE TRENDS (10v): this is a
window-length fit along a route, never a per-vertex DEM pull (08t (1)) —
the same statement §21.2 (5) makes for the runway.  Extending it across
the face changes NOTHING about that: the value handed to an edge vertex
is the same window-length fit, read at the same station.
"""
from __future__ import annotations

import dataclasses as _dc
import math as _math
import typing as _t

import numpy as np

from .runway_chord import dem_degraded
from .trend import shift_through, trend_of
from ..law import Law
from ..law.tables import is_value_role
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["TaxiTrendReport", "taxi_trend_targets", "with_taxi_trend",
           "taxi_trend_block", "taxi_chains", "chain_of_face",
           "TAXI_CENTERLINE"]

#: The breakline kind whose chains ARE the taxi routes (the same kind
#: ``solve/design.py`` prices the second-difference profile along).
TAXI_CENTERLINE = "taxi_centerline"


class TaxiTrendReport(_t.TypedDict, total=False):
    """What the taxi trend fit covered."""

    chains: int               # centreline chains given a target profile
    chains_without: int       # chains with too few DEM samples (no target)
    vertices: int             # vertices carrying a trend target
    centerline_vertices: int  # of those, ON a centreline chain
    face_vertices: int        # of those, off-centreline taxi-face vertices
    face_out_of_reach: int    # taxi-face vertices past `taxi_trend_face_reach_m`
    face_reach_m: float
    max_foot_m: float         # the furthest foot actually used
    pins: int                 # runway contacts the trend was shifted through
    window_m: float
    max_above_dem_m: float    # the largest target − DEM (the fill it asks)
    max_below_dem_m: float    # the largest DEM − target (the cut)
    fallback: str             # why nothing was fitted, where nothing was
    by_chain: list            # [{"chain", "ll", "vertices", "pins", "length_m"}]


@_dc.dataclass(frozen=True)
class _Chain:
    """One taxi centreline chain in its own station frame."""

    bl: int
    vertices: tuple[int, ...]
    stations: tuple[float, ...]
    pins: tuple[int, ...]          # the chain's runway-contact vertices

    @property
    def length_m(self) -> float:
        return self.stations[-1] - self.stations[0] if self.stations else 0.0


def _chains(pm: PlanarMap, law: Law) -> list[_Chain]:
    """Every taxi centreline chain, its stations (cumulative plan distance
    from its first vertex) and its RUNWAY-CONTACT vertices — a chain vertex
    ringing a runway-family face, whose value the runway owns."""
    rwy = frozenset(law.tables.precedence.runway_family.members)
    out: list[_Chain] = []
    for bl in pm.breaklines.values():
        if bl.kind != TAXI_CENTERLINE:
            continue
        ch = bl.vertices(pm)
        if len(ch) < 2:
            continue
        st = [0.0]
        for a, b in zip(ch, ch[1:]):
            (ax, ay), (bx, by) = pm.vertices[a].xy, pm.vertices[b].xy
            st.append(st[-1] + _math.hypot(bx - ax, by - ay))
        pins = tuple(v for v in ch
                     if any(pm.faces[f].role in rwy
                            for f in pm.vertices[v].incident_faces))
        out.append(_Chain(bl.id, tuple(ch), tuple(st), pins))
    return out


def taxi_chains(pm: PlanarMap, law: Law) -> list[_Chain]:
    """EVERY TAXI CENTRELINE CHAIN in its own station frame — the public
    name of this module's one chain derivation (:func:`_chains`).

    Published because the EAT reach (``constraints/eat.py``, spec §36 (5))
    runs its ramp back along THE LOOP'S OWN CENTRELINE and must read the
    same chains, in the same station frame, that this module fitted the
    trend along: two derivations of "the loop's centreline" would withdraw
    a trend row on one frame and price it on another."""
    return _chains(pm, law)


def chain_of_face(pm: PlanarMap, law: Law,
                  chains: list[_Chain]) -> dict[int, int]:
    """face id -> the index in ``chains`` of THE CHAIN THAT SPEAKS FOR IT.

    The apt.dat centreline record (``taxi57``) and the pavement polygon
    (``pav28``) carry different refs, so the map's own incidence (I5) is
    the join.  A face belongs to the chain with the MOST of its vertices
    on it, ties to the longer chain: a chain merely crossing a junction
    fillet touches it at one or two vertices and never becomes its
    authority.  Measured: without this, CYXY's ``taxi_box`` short-pair
    rows go 6 -> 47 (the long parallel valuing a stub's far end at its own
    station gradient).

    ONE derivation, shared with the EAT reach (:func:`taxi_chains`)."""
    taxi = frozenset(law.tables.precedence.taxi_family.members)
    owner: dict[int, tuple[int, int, float]] = {}   # face -> (chain, hits, length)
    for i, c in enumerate(chains):
        hits: dict[int, int] = {}
        for v in c.vertices:
            for fid in pm.vertices[v].incident_faces:
                if pm.faces[fid].role in taxi:
                    hits[fid] = hits.get(fid, 0) + 1
        for fid, n in hits.items():
            cur = owner.get(fid)
            if cur is None or (n, c.length_m) > (cur[1], cur[2]):
                owner[fid] = (i, n, c.length_m)
    return {fid: i for fid, (i, _n, _l) in owner.items()}


def _face_extension(pm: PlanarMap, law: Law, chains: list[_Chain],
                    ats: list[_t.Callable[[float], float | None]],
                    have: _t.AbstractSet[int], reach_m: float,
                    window_m: float) -> tuple[dict[int, float], int, float]:
    """The trend extended from the chain to THE WHOLE TAXI FACE (module
    docstring): every vertex of a taxi-family face that carries no target
    yet takes the trend value at the station of its FOOT on that face's
    OWN centreline chain, within ``reach_m``.

    A CHAIN SPEAKS ONLY FOR THE FACES IT OWNS (the taxi-family faces most
    of whose chain vertices are its own), and only where it is LONG
    (its stations span at least half the fit window — the same test
    ``Trend.at`` puts on the fit's DEGREE).  Both bounds are MEASURED, not
    tidiness:

    * A FOREIGN chain projects the wrong direction.  Valuing a stub's face
      from the long parallel it meets spreads that parallel's own STATION
      gradient ACROSS the stub's width.  MEASURED at CYXY (v1 oracle / v2
      verify ``taxi_box`` short-pair rows, control 6 / 6): nearest long
      chain over every taxi vertex 22 / 36; every face the chain TOUCHES
      (a junction fillet counts) 34 / 47; the faces it OWNS 22 / 30.
    * A SHORT chain's trend is not a long-wave statement at all — it is a
      line through 100 m of ground — and sideways it asserts a level
      cross-section over ground it never sampled.  On the §8.6 stub fixture
      the 101 m junction stub's two side vertices, handed its own flat
      trend while the apron beside them leaned with the ground, pulled the
      junction 0.63 m down and bent the 1 km parallel 3.78x its own
      vertical-curve bound.

    So a stub, a cross connector and a junction fillet keep round 2's
    behaviour exactly (their centreline row, nothing across); a long
    taxiway's whole face follows its trend.  It is ONE value per vertex,
    the same the centreline gets at that station: the cross-section's
    shape stays the transverse law's, which is senior.

    Returns the new targets, how many candidates were out of reach, and the
    furthest foot distance actually used."""
    taxi = frozenset(law.tables.precedence.taxi_family.members)
    faces_of: dict[int, list[int]] = {}
    for fid, i in chain_of_face(pm, law, chains).items():
        faces_of.setdefault(i, []).append(fid)
    out: dict[int, float] = {}
    best: dict[int, float] = {}
    far = 0
    worst = 0.0
    for i, c in enumerate(chains):
        if len(c.vertices) < 2 or c.length_m < 0.5 * window_m:
            continue                     # only a LONG chain speaks across
        own = faces_of.get(i, [])
        cand: list[int] = []
        seen: set[int] = set()
        for fid in own:
            f = pm.faces[fid]
            vs = list(pm.ring_vertices(f.ring))
            for h in f.holes:
                vs += list(pm.ring_vertices(h))
            for v in vs:
                if v in have or v in seen:
                    continue
                seen.add(v)
                roles = pm.roles_at(v)
                # THE TAXI FAMILY MUST OWN THE VERTEX OUTRIGHT.  A vertex
                # the face SHARES with another VALUE surface — a runway
                # contact (hard and flush, the runway's own value) or an
                # apron edge (the apron body's plane, at ten times this
                # weight) — takes no trend row: two authorities on one
                # vertex is the `emit consensus mints violations` class.
                # A non-value role (the graded strip, a clearance) is not
                # an authority and does not disqualify a vertex.
                if any(r not in taxi and is_value_role(law, r) for r in roles):
                    continue
                cand.append(v)
        if not cand:
            continue
        xy = [pm.vertices[v].xy for v in c.vertices]
        A = np.asarray(xy[:-1], dtype=float)
        B = np.asarray(xy[1:], dtype=float)
        S0 = np.asarray(c.stations[:-1], dtype=float)
        S1 = np.asarray(c.stations[1:], dtype=float)
        D = B - A
        LL = np.einsum("ij,ij->i", D, D)
        LL = np.where(LL > 0.0, LL, 1.0)
        P = np.asarray([pm.vertices[v].xy for v in cand], dtype=float)
        for lo in range(0, len(cand), 512):
            blk = P[lo:lo + 512]
            w = blk[:, None, :] - A[None, :, :]
            t = np.clip(np.einsum("nsj,sj->ns", w, D) / LL[None, :], 0.0, 1.0)
            rel = blk[:, None, :] - (A[None, :, :] + t[:, :, None] * D[None, :, :])
            d2 = np.einsum("nsj,nsj->ns", rel, rel)
            j = np.argmin(d2, axis=1)
            n = np.arange(len(blk))
            dist = np.sqrt(d2[n, j])
            st = S0[j] + t[n, j] * (S1[j] - S0[j])
            for k, v in enumerate(cand[lo:lo + 512]):
                d = float(dist[k])
                if d > reach_m:
                    far += 1
                    continue
                if v in best and best[v] <= d:
                    continue             # a nearer chain of the same ref
                z = ats[i](float(st[k]))
                if z is None:
                    far += 1
                    continue
                best[v] = d
                out[v] = float(z)
                worst = max(worst, d)
    return out, far, worst


def taxi_trend_targets(pm: PlanarMap, law: Law, airport: Airport,
                       report: TaxiTrendReport | None = None
                       ) -> dict[int, float]:
    """Vertex id -> the TARGET PROFILE at its station (module docstring).

    A RUNWAY-CONTACT vertex is never given a target: the runway owns it,
    its contact stays hard and flush, and it serves here only as the pin
    the trend is shifted through."""
    window = float(law.tables.emit.design.runway_profile_window_m)
    reach = float(law.tables.emit.design.taxi_trend_face_reach_m)
    degraded = dem_degraded(airport)
    chains = _chains(pm, law)
    if report is not None:
        report.update(window_m=window, chains=0, chains_without=0, vertices=0,
                      centerline_vertices=0, face_vertices=0,
                      face_out_of_reach=0, face_reach_m=reach, max_foot_m=0.0,
                      pins=0, max_above_dem_m=0.0, max_below_dem_m=0.0,
                      by_chain=[])
    if degraded:
        if report is not None:
            report["fallback"] = degraded
            report["chains_without"] = len(chains)
        return {}
    out: dict[int, float] = {}
    above = below = 0.0
    by_chain: list[dict[str, _t.Any]] = []
    n_ok = n_no = n_pins = 0
    fitted: list[_Chain] = []
    ats: list[_t.Callable[[float], float | None]] = []
    pinned_all: set[int] = set()
    for c in chains:
        samples = [(s, float(pm.vertices[v].dem_z))
                   for v, s in zip(c.vertices, c.stations)
                   if pm.vertices[v].dem_z is not None]
        tr = trend_of(samples, window)
        if tr is None:
            n_no += 1
            continue
        st_of = dict(zip(c.vertices, c.stations))
        pins = []
        for v in c.pins:
            z = pm.preferred_z.get(v, pm.vertices[v].dem_z)
            if z is not None:
                pins.append((st_of[v], float(z)))
        at = shift_through(tr, pins)
        fitted.append(c)
        ats.append(at)
        pinned = set(c.pins)
        pinned_all |= pinned
        n = 0
        for v, s in zip(c.vertices, c.stations):
            if v in pinned:
                continue
            t = at(s)
            if t is None:
                continue
            # a chain vertex shared by two chains keeps the FIRST target:
            # the chains agree to the fit's own precision and a vote here
            # would make the target depend on breakline id order
            out.setdefault(v, float(t))
            n += 1
            dem = pm.vertices[v].dem_z
            if dem is not None:
                above = max(above, t - float(dem))
                below = max(below, float(dem) - t)
        if n:
            n_ok += 1
            n_pins += len(pins)
            by_chain.append({"chain": c.bl,
                             "ll": [pm.vertices[c.vertices[0]].key[0],
                                    pm.vertices[c.vertices[0]].key[1]],
                             "vertices": n, "pins": len(pins),
                             "length_m": round(c.length_m, 1)})
        else:
            n_no += 1
    # THE WHOLE FACE, NOT ONLY ITS SPINE (round 3, module docstring): the
    # taxi body's off-centreline vertices take the SAME row at the SAME
    # weight, valued at their own station on the chain.
    n_center = len(out)
    face, far, foot = _face_extension(pm, law, fitted, ats,
                                      set(out) | pinned_all, reach, window)
    for v, t in face.items():
        out[v] = t
        dem = pm.vertices[v].dem_z
        if dem is not None:
            above = max(above, t - float(dem))
            below = max(below, float(dem) - t)
    if report is not None:
        report.update(chains=n_ok, chains_without=n_no, vertices=len(out),
                      centerline_vertices=n_center, face_vertices=len(face),
                      face_out_of_reach=far, face_reach_m=reach,
                      max_foot_m=round(foot, 2),
                      pins=n_pins, max_above_dem_m=round(above, 3),
                      max_below_dem_m=round(below, 3),
                      by_chain=sorted(by_chain,
                                      key=lambda r: -r["length_m"])[:12])
    return out


def with_taxi_trend(pm: PlanarMap, law: Law, airport: Airport,
                    report: TaxiTrendReport | None = None) -> PlanarMap:
    """``pm`` with the taxi chains' target profiles published in
    ``taxi_trend_z`` (its own channel — see the module docstring)."""
    targets = taxi_trend_targets(pm, law, airport, report)
    if not targets:
        return pm
    return _dc.replace(pm, taxi_trend_z=dict(targets))


def taxi_trend_block(pm: PlanarMap, law: Law,
                     z: _t.Sequence[float]) -> dict[str, _t.Any]:
    """THE REPORT the round owes (RULINGS 2026-09-10v): per taxi chain its
    TREND RESIDUAL — the built surface against the published target along
    that chain (RMS and max), and the chain's own |z − DEM|.  Read after
    the solve and the projection, from the SAME channel the rows were
    priced from, so the number is the residual of the row that exists."""
    tt = pm.taxi_trend_z
    if not tt:
        return {}
    chains = _chains(pm, law)
    rows: list[dict[str, _t.Any]] = []
    worst = 0.0
    for c in chains:
        d2 = []
        dem2 = []
        for v in c.vertices:
            t = tt.get(v)
            if t is None:
                continue
            d2.append(float(z[v]) - float(t))
            dem = pm.vertices[v].dem_z
            if dem is not None:
                dem2.append(float(z[v]) - float(dem))
        if not d2:
            continue
        rms = _math.sqrt(sum(x * x for x in d2) / len(d2))
        mx = max(abs(x) for x in d2)
        worst = max(worst, mx)
        rows.append({"chain": c.bl,
                     "ll": [pm.vertices[c.vertices[0]].key[0],
                            pm.vertices[c.vertices[0]].key[1]],
                     "length_m": round(c.length_m, 1),
                     "vertices": len(d2), "pins": len(c.pins),
                     "rms_m": round(rms, 3), "max_m": round(mx, 3),
                     "mean_off_dem_m": round(sum(dem2) / len(dem2), 3)
                     if dem2 else None})
    rows.sort(key=lambda r: -r["max_m"])
    return {"chains": len(rows), "vertices": len(tt),
            "worst_residual_m": round(worst, 3),
            "rms_m": round(_math.sqrt(sum(r["rms_m"] ** 2 * r["vertices"]
                                          for r in rows)
                                      / max(1, sum(r["vertices"] for r in rows))), 3),
            "by_chain": rows[:12]}
