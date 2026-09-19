"""§37 (9) THE COVERAGE-EDGE JOIN (Fable 2026-09-13; owner RULINGS
2026-09-13be) — where the patch's road meets the core's ribbon.

Scout ``roadlevel``: the core's ``include_roads`` levelling runs for every
airport-area way and is then REMOVED inside the patch coverage + 6 m
(``O4_Vector_Map.py:1749-1757``), so INSIDE the coverage the patch is the
sole road authority and OUTSIDE it the core's clamped ribbon carries the
road.  The two meet at the coverage edge, and nothing made them agree: at
KCLT way 10826 station 0 (35.2077398, −80.9290045) the patch's kerb stands
2.36 m over the core ribbon across 7.9 m.

THE RULE: a road-family face whose way LEAVES THE COVERAGE takes, at its
last station inside, the core ribbon's altitude at the FIRST STATION
OUTSIDE — the clamp value the core itself would emit there — as an
EQUALITY.  One value per exit, on the section at that station (the same
(route, station) unit §37 (8) binds the ramp on), so the join is a level
join and not a tilt.

The derivation lives here, in ``emit``, because the coverage is
``emit/bank.coverage_polygon`` — ONE implementation of "the union of every
planar face", the same polygon §37 (3)'s bank is cut against.  It is
published as ``PlanarMap.road_coverage_join`` (vertex -> the ribbon
altitude) by the pipeline, minted as ``Pin`` rows by
``constraints/road_ramp.py`` and priced by the census family
``road_coverage_join``.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["road_coverage_joins", "with_road_coverage_join", "JOIN_RULING"]

#: The ruling head the generator stamps (``solve.design.ruling_head``).
JOIN_RULING = ("roads.coverage_edge join "
               "(owner 2026-09-13be; spec §37 (9))")


#: Halvings used to locate the coverage crossing on the exit segment
#: (S.2 (c)).  40 resolves a 20 m station to well under a micrometre.
_CROSSING_HALVINGS = 40


def _crossing_z(way, cov, last_in: int, first_out: int) -> float:
    """The way's profile value AT the coverage boundary — linear in
    ``way.z`` at the arclength where the segment ``last_in → first_out``
    crosses it (spec §2-SUPPLEMENT S.2 (c)).

    The crossing is bisected on ``cov.covers`` rather than intersected
    with the boundary: the segment may clip a re-entrant edge more than
    once, and the value the join wants is the one at the LAST crossing
    on the way out, which is what the bisection between an inside point
    and an outside point converges to.
    """
    from shapely.geometry import Point
    xi, yi = (float(v) for v in way.xy[last_in])
    xo, yo = (float(v) for v in way.xy[first_out])
    zi, zo = float(way.z[last_in]), float(way.z[first_out])
    lo, hi = 0.0, 1.0            # lo: still inside, hi: outside
    for _ in range(_CROSSING_HALVINGS):
        t = 0.5 * (lo + hi)
        p = Point(xi + t * (xo - xi), yi + t * (yo - yi))
        if cov.covers(p):
            lo = t
        else:
            hi = t
    t = 0.5 * (lo + hi)
    return zi + (zo - zi) * t


def road_coverage_joins(pm: PlanarMap, law: Law, profiles,
                        frame: _t.Mapping[int, tuple[int, float, float]],
                        coverage=None
                        ) -> tuple[dict[int, float], dict[str, _t.Any]]:
    """``(vertex -> the core ribbon's altitude at the first station outside
    the coverage, report)`` for every road route that leaves it.

    ``profiles`` is ``preferred_road_z``'s own :class:`RoadProfiles` (its
    ways carry the clamp as ``z``); ``frame`` is §37 (7)'s route frame, so
    the join lands on the vertices of the LAST STATION INSIDE and on no
    others.  ``coverage`` defaults to :func:`emit.bank.coverage_polygon`.
    """
    from shapely.geometry import Point
    from .bank import coverage_polygon
    rep: dict[str, _t.Any] = {"routes": 0, "exits": 0, "vertices": 0,
                              "max_step_m": 0.0}
    cov = coverage_polygon(pm) if coverage is None else coverage
    if cov is None or not frame:
        return {}, rep
    ways = list(profiles.all_ways)
    by_route: dict[int, list[int]] = {}
    for v, (r, _s, _t_) in frame.items():
        by_route.setdefault(int(r), []).append(v)
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    out: dict[int, float] = {}
    for r, verts in sorted(by_route.items()):
        if r < 0 or r >= len(ways):
            continue
        w = ways[r]
        inside = [bool(cov.covers(Point(float(x), float(y)))) for x, y in w.xy]
        if all(inside) or not any(inside):
            continue                      # the way never crosses the edge
        rep["routes"] += 1
        # every EXIT of this way: the last station inside, the first out
        for i in range(len(inside) - 1):
            a, b = i, i + 1
            if inside[a] == inside[b]:
                continue
            last_in, first_out = (a, b) if inside[a] else (b, a)
            # THE JOIN VALUE IS READ AT THE CROSSING, not at the first
            # station outside (spec §2-SUPPLEMENT S.2 (c)): a 20 m
            # station hid up to 1.6 m at the 8 % cap and up to 4 m at a
            # 20 % class cap.  Linear in ``w.z`` at the arclength where
            # the way crosses the coverage boundary.
            z_out = _crossing_z(w, cov, last_in, first_out)
            s_in = float(w.s[last_in])
            rep["exits"] += 1
            # THE SECTION AT THAT STATION (§37 (8)'s unit): the route's
            # own vertices within one grid step of the last station in
            for v in verts:
                if abs(frame[v][1] - s_in) <= max(grid, w.s[-1] * 0.0) + grid:
                    prev = out.get(v)
                    if prev is None or abs(z_out - prev) > 0.0:
                        out[v] = z_out
    rep["vertices"] = len(out)
    for v, z in out.items():
        dz = pm.vertices[v].dem_z
        if dz is not None:
            rep["max_step_m"] = max(rep["max_step_m"], abs(float(z) - float(dz)))
    rep["max_step_m"] = round(rep["max_step_m"], 3)
    return out, rep


def with_road_coverage_join(pm: PlanarMap, law: Law, profiles,
                            report: dict[str, _t.Any] | None = None,
                            coverage=None) -> PlanarMap:
    """Publish §37 (9)'s join as ``PlanarMap.road_coverage_join``.  Runs
    AFTER ``with_road_ramp`` (it reads that pass's route frame) and before
    the constraints; the rows are ``constraints/road_ramp.road_join_rows``.
    """
    joins, rep = road_coverage_joins(pm, law, profiles, pm.road_route_frame,
                                     coverage)
    if report is not None:
        report.update(rep)
    if not joins:
        return pm
    return _dc.replace(pm, road_coverage_join=joins)
