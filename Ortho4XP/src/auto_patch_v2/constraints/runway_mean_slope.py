"""THE MEAN RUNWAY SLOPE (family ``runway_mean_slope``; ICAO Annex 14
§3.1.13, audit ``docs/findings/law-table-audit-20261015.md`` §4 M1, owner
RULINGS 2026-10-15l (1)): the highest minus the lowest centreline
elevation of a runway, over its length, at most
``tables.runway_mean_slope_max`` — 1 % at code 3/4, 2 % at code 1/2.

Stated on the runway's own ridge stations (``runway_profile.
curve_stations`` between the two ends) as ALL-PAIRS ``Diff`` rows
``|z_i - z_j| <= m · L`` (spec §4: no auxiliary columns), HARD in the
runway tier beside the longitudinal cap.

THE CAP YIELDS TO ITS PINS (the §50.1 (3) class, owner RULINGS
2026-09-18d (3)): where the runway's own hard pins — its thresholds (CIFP
or apt.dat datum) and its §38 seam DEM pins — already stand further apart
than ``m · L``, the effective cap is their spread over ``L`` plus
``[design] runway_yield_margin``.  :func:`mean_slope_caps` is the ONE
derivation; the sidecar ``runway_axes`` slot 19 publishes it and v2 verify
(``verify.runway.runway_mean_slope``) reads it back.
"""
from __future__ import annotations

from ..law import Law
from ..law.tables import runway_mean_slope_max
from ..model.airport import Airport
from ..model.constraints import Diff, Row, Source
from ..model.planar import PlanarMap
from .precedence import view
from .runway_profile import _axis, curve_stations, ridge_chains, threshold_pins

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
    return [v for v in curve_stations(vw.xy, chs, along, min_d)
            if -tol <= along(v) <= rw.length_m + tol]


def mean_slope_caps(planar: PlanarMap, law: Law, airport: Airport
                    ) -> dict[str, float]:
    """Runway ref -> its EFFECTIVE mean-slope cap (module docstring), for
    every runway the authority states a cap for."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    margin = float(law.tables.emit.design.runway_yield_margin)
    pins = threshold_pins(planar, law, airport)
    seam = getattr(planar, "seam_vertices", None) or ()
    out: dict[str, float] = {}
    for rw in airport.runways:
        m = runway_mean_slope_max(law, rw.code_number, rw.code_letter)
        chs = chains.get(rw.id)
        if m is None or not chs or rw.length_m <= 0.0:
            continue
        ridge = {v for ch in chs for v in ch}
        zs = [float(z) for v, z in pins.items() if v in ridge]
        zs += [float(planar.vertices[v].dem_z) for v in ridge
               if v in seam and v not in pins and planar.vertices[v].dem_z is not None]
        spread = (max(zs) - min(zs)) / rw.length_m if len(zs) >= 2 else 0.0
        out[rw.id] = max(float(m), spread + margin) if spread > float(m) else float(m)
    return out


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
