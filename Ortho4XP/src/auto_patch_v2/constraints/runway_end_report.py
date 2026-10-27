"""THE RUNWAY-END PIN REPORT (owner RULINGS 2026-10-25a "log the decision
loudly … and publish it in the sidecar", 2026-10-26e "publish the yield";
issues #1342, #1358, #1394): one record per runway end — where its pin
sits, what pinned it and the values the rule read — for the sidecar key
``runway_end_pins`` and the build report, plus the loud lines for the
ends the DEM decided.

A READ of the two derivations, never a third: the surveyed pins are the
Airport's (``airport/end_pins``, at load), the DEM / datum ends are
``runway_profile.end_pin_cases``; the vertex is ``_end_vertex``'s.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap
from .precedence import view
from .runway_profile import (
    CASE_FLAGGED,
    CASE_GROUND,
    CASE_LIDAR,
    _axis,
    _end_vertex,
    end_pin_cases,
    ridge_chains,
)

__all__ = ["records", "lines"]


def records(planar: PlanarMap, law: Law, airport: Airport) -> list[dict[str, _t.Any]]:
    """One record per runway end with a ridge: ``runway``, ``end``,
    ``vertex``, ``source`` (``cifp`` / a cross-check name / the
    ``end_pin_cases`` case), ``pin_m``, ``cifp_m`` (as read), ``flags``,
    ``datum_m`` and ``dem_m`` (where a case read them), ``pin_along_m``."""
    vw = view(planar, law)
    chains = ridge_chains(vw)
    cases = end_pin_cases(planar, law, airport)
    out: list[dict[str, _t.Any]] = []
    for rw in airport.runways:
        chs = chains.get(rw.id)
        if not chs:
            continue
        _a, ux, uy = _axis(rw)
        all_ids = [v for ch in chs for v in ch]
        for end in rw.ends:
            v = _end_vertex(vw, all_ids, rw, end, ux, uy)
            p = cases.get(v)
            raw = getattr(end, "cifp_elev_m", None)
            if raw is None and getattr(end, "pin_source", "") == "cifp":
                raw = end.threshold_elev_m
            if end.threshold_elev_m is not None:
                source, z = getattr(end, "pin_source", "") or "cifp", float(end.threshold_elev_m)
            elif p is not None:
                source, z = p.case, p.z
            else:
                source, z = "", None
            out.append({
                "runway": rw.id, "end": end.name, "vertex": int(v), "source": source,
                "pin_m": None if z is None else round(z, 3),
                "cifp_m": None if raw is None else round(float(raw), 3),
                "flags": [f for f in getattr(end, "pin_flags", "").split(",") if f],
                "datum_m": None if p is None or p.datum_z is None else round(p.datum_z, 3),
                "dem_m": None if p is None or p.dem_z is None else round(p.dem_z, 3),
                "pin_along_m": round(float(end.pin_along()), 2),
            })
    return out


def lines(icao: str, recs: _t.Iterable[dict[str, _t.Any]]) -> list[str]:
    """The loud line of every end the DEM decided over a survey or a datum:
    a flagged CIFP end (#1342) and an apt.dat-only end the lidar (#1394)
    or a fine / coarse DEM (#1348, 28m) outvoted."""
    out = []
    for r in recs:
        if r["source"] == CASE_FLAGGED:
            out.append(f"RUNWAY END FOLLOWS THE DEM (#1342, RULINGS 2026-10-25a): {icao} "
                       f"{r['runway']} RWY {r['end']}: CIFP {r['cifp_m']} m flagged "
                       f"({','.join(r['flags'])}) -> pinned {r['pin_m']} m")
        elif r["source"] == CASE_LIDAR:
            out.append(f"RUNWAY END GIVES WAY TO THE LIDAR (#1394, RULINGS 2026-10-26e): "
                       f"{icao} {r['runway']} RWY {r['end']}: apt.dat datum {r['datum_m']} m "
                       f"-> lidar {r['pin_m']} m")
        elif r["source"] == CASE_GROUND:
            out.append(f"RUNWAY END YIELDS TO THE SURVEY GROUND (#1348, RULINGS 2026-10-28m): "
                       f"{icao} {r['runway']} RWY {r['end']}: apt.dat datum {r['datum_m']} m "
                       f"-> DEM {r['pin_m']} m")
    return out
