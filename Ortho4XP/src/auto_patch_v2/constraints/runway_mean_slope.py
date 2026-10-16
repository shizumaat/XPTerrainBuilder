"""THE MEAN RUNWAY SLOPE (family ``runway_mean_slope``; ICAO Annex 14
§3.1.13, audit ``docs/findings/law-table-audit-20261015.md`` §4 M1, owner
RULINGS 2026-10-15l (1)): the highest minus the lowest centreline
elevation of a runway, over its length, at most
``tables.runway_mean_slope_max`` — 1 % at code 3/4, 2 % at code 1/2.

Stated on the runway's own ridge stations (``runway_profile.
curve_stations`` between the two ends, thinned to ``runway.
mean_slope_station_m``) as ALL-PAIRS ``Diff`` rows ``|z_i - z_j| <= m · L``
(spec §4: no auxiliary columns), HARD in the runway tier beside the
longitudinal cap.

THE PINS GOVERN (the §50.1 (3) class, owner RULINGS 2026-09-18d (3)):
where the runway's own hard pins — its thresholds (CIFP or apt.dat datum),
its §17 crossing anchors and its §38 seam DEM pins (``runway_yield.
_pin_sources``) — stand within ``[design] runway_yield_margin`` of
``m · L`` apart or further, or its longitudinal cap yielded to them, the
mean slope is the pins' and no row is stated: a yielded cap here met the
vertical-curve rows and the yield envelope as a hard conflict (the
crossing fixture of ``test_v2cyxy``).  :func:`mean_slope_caps` is the ONE
derivation; the sidecar ``runway_axes`` slot 19 publishes it (``None``
where the pins govern) and v2 verify (``verify.runway_mean_slope``) reads
it back.
"""
from __future__ import annotations

from ..law import Law
from ..law.tables import runway_mean_slope_max
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .precedence import view
from .runway_profile import _axis, curve_stations, ridge_chains
from .runway_yield import _pin_sources

__all__ = ["RULING", "mean_slope_caps", "runway_mean_slope"]

GEN = "runway_mean_slope"
#: the row head (``[design] hard_rulings``)
RULING = "rulesets.runway.mean_slope_max (Annex 14 §3.1.13)"


def _stations(vw, rw, chs, min_d: float) -> list[int]:
    """The runway's ridge stations between its two ends (an overrun is
    not runway)."""
    a_xy, ux, uy = _axis(rw)

    def along(v: int) -> float:
        x, y = vw.xy[v]
        return (x - a_xy[0]) * ux + (y - a_xy[1]) * uy
    tol = min_d
    st = [v for v in curve_stations(vw.xy, chs, along, min_d)
          if -tol <= along(v) <= rw.length_m + tol]
    step = vw.law.ruleset.runway.mean_slope_station_m
    if not step or len(st) < 3:
        return st
    out = [st[0]]
    for v in st[1:-1]:
        if along(v) - along(out[-1]) >= float(step):
            out.append(v)
    return out + [st[-1]]


def mean_slope_caps(planar: PlanarMap, law: Law, airport: Airport
                    ) -> dict[str, float]:
    """Runway ref -> its EFFECTIVE mean-slope cap (module docstring), for
    every runway the authority states a cap for."""
    key = (id(planar), id(law), id(airport))
    if _LAST and _LAST[0] == key:
        return dict(_LAST[1])
    rws = [rw for rw in airport.runways
           if runway_mean_slope_max(law, rw.code_number, rw.code_letter) is not None
           and rw.length_m > 0.0]
    out: dict[str, float] = {}
    if rws:
        vw = view(planar, law)
        chains = ridge_chains(vw)
        margin = float(law.tables.emit.design.runway_yield_margin)
        # every HARD PIN on the ridge (threshold, crossing anchor, seam DEM;
        # the §50.1 (3) derivation's own reading)
        pins = _pin_sources(planar, law, airport, vw, chains)
        for rw in rws:
            m = float(runway_mean_slope_max(law, rw.code_number, rw.code_letter))
            chs = chains.get(rw.id)
            if not chs:
                continue
            ridge = {v for ch in chs for v in ch}
            zs = [float(p.z) for v, p in pins.items() if v in ridge]
            spread = (max(zs) - min(zs)) / rw.length_m if len(zs) >= 2 else 0.0
            rc = (getattr(planar, "runway_caps", None) or {}).get(rw.id)
            if spread + margin > m or (rc is not None and getattr(rc, "yielded", False)):
                continue              # THE PINS GOVERN (module docstring)
            out[rw.id] = m
    _LAST[:] = [key, dict(out)]
    return out


#: the last derivation (the generator and the publication read one map)
_LAST: list = []


def runway_mean_slope(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """All-pairs ``Diff`` rows over each runway's ridge stations at the
    effective cap over the runway LENGTH (module docstring)."""
    caps = mean_slope_caps(planar, law, airport)
    if not caps:
        return []
    vw = view(planar, law)
    chains = ridge_chains(vw)
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    rows: list[Row] = []
    for rw in airport.runways:
        cap = caps.get(rw.id)
        if cap is None:
            continue
        st = _stations(vw, rw, chains[rw.id], min_d)
        src = Source(GEN, RULING, (f"rwy:{rw.id}",))
        L = float(rw.length_m)
        for i in range(len(st)):
            for j in range(i + 1, len(st)):
                rows.append(Diff(st[i], st[j], cap, L, src))
    return rows
