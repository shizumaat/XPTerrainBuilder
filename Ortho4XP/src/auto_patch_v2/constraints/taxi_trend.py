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

THE GROUND ENTERS PAVEMENT ONLY THROUGH LONG-WAVE TRENDS (10v): this is a
window-length fit along a route, never a per-vertex DEM pull (08t (1)) —
the same statement §21.2 (5) makes for the runway.
"""
from __future__ import annotations

import dataclasses as _dc
import math as _math
import typing as _t

from .runway_chord import dem_degraded
from .trend import shift_through, trend_of
from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["TaxiTrendReport", "taxi_trend_targets", "with_taxi_trend",
           "taxi_trend_block", "TAXI_CENTERLINE"]

#: The breakline kind whose chains ARE the taxi routes (the same kind
#: ``solve/design.py`` prices the second-difference profile along).
TAXI_CENTERLINE = "taxi_centerline"


class TaxiTrendReport(_t.TypedDict, total=False):
    """What the taxi trend fit covered."""

    chains: int               # centreline chains given a target profile
    chains_without: int       # chains with too few DEM samples (no target)
    vertices: int             # vertices carrying a trend target
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


def taxi_trend_targets(pm: PlanarMap, law: Law, airport: Airport,
                       report: TaxiTrendReport | None = None
                       ) -> dict[int, float]:
    """Vertex id -> the TARGET PROFILE at its station (module docstring).

    A RUNWAY-CONTACT vertex is never given a target: the runway owns it,
    its contact stays hard and flush, and it serves here only as the pin
    the trend is shifted through."""
    window = float(law.tables.emit.design.runway_profile_window_m)
    degraded = dem_degraded(airport)
    chains = _chains(pm, law)
    if report is not None:
        report.update(window_m=window, chains=0, chains_without=0, vertices=0,
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
        pinned = set(c.pins)
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
    if report is not None:
        report.update(chains=n_ok, chains_without=n_no, vertices=len(out),
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
