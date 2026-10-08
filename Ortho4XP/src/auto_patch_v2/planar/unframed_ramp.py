"""THE RAMP NO OBJECT FRAMES — its DESIGN grade and the cap above it
(owner RULINGS 2026-10-08c (1), 2026-10-08d (1); spec §34 (1a)).

A mapped bore's approach has nothing but the ground to say how long it
is, so its grade is a DESIGN choice: ``[tunnel] ramp_grade``.  The cap
``[tunnel] ramp_max_grade`` is the ceiling the ramp steepens toward only
where the design grade cannot top out in the run it has.  The climb
itself — where a given grade meets the DEM along the route — stays
:func:`structure_approach.ramp_top`'s; this module only chooses the
grade.  An object-framed ramp (a door well, a wall corridor: RULINGS
2026-10-07e) takes its length and depth from the object and reads
neither key.
"""
from __future__ import annotations

import math

import shapely
from shapely.geometry import LineString, Point

from ..airport.dem import dem_z_at
from ..law import Law
from ..model.airport import Airport
from .structure_approach import ramp_top

__all__ = ["unframed_top", "overlap_run_end", "MAX_OVERLAP_PASSES"]

#: How often the build is re-planned for ramps that yield to one another.
MAX_OVERLAP_PASSES = 8


def unframed_top(airport: Airport, law: Law, axis_fn, mouth_z: float, climb_from: float,
                 spacing: float, *, within: float | None = None,
                 max_len: float | None = None
                 ) -> tuple[float | None, float | None, list[float]]:
    """``(grade, s_top, stations)`` of a ramp NO OBJECT FRAMES (a mapped
    bore's approach) — THE CAP IS A CEILING, NEVER THE GRADE A RAMP IS
    BUILT AT (owner RULINGS 2026-10-08c (1): "it's a CAP, not a target,
    it should only allow more flex where needed").

    The ramp climbs at its DESIGN grade ``tunnel.ramp_grade`` (5 %,
    RULINGS 2026-10-08d (1)) and tops where :func:`ramp_top` says that
    climb meets the DEM.  It steepens ONLY where the design grade cannot
    top out in the run it has — the DEM is not met within
    ``max_ramp_length_m``, or the ramp's top would stand beyond station
    ``within`` (the caller's run end: the road's end, a deck across the
    approach, a pad / pavement stop, another corridor) — and then to the
    SMALLEST grade that does: ``min over the stations of |DEM − mouth| /
    route length``, never above ``tunnel.ramp_max_grade``.  ``(None, None,
    stations)`` when no grade up to the cap tops out (the stations are the
    cap's own walk, for the caller's refusal line).

    Measured (sweep ``sww``, 2026-10-08): with the cap read as the climb,
    raising it 8 → 10 % shortened EVERY mapped approach (SPJC 120 → 84 m)
    though none needed the grade; KASE's ``tunnel:-549@0``, which never
    met the ground in 600 m, is the ramp the cap is for (9.84 %)."""
    tn = law.tables.structures.tunnel
    bound = tn.max_ramp_length_m if max_len is None else max_len
    need = None
    s = 0.0
    while s < bound:
        s += spacing
        if within is not None and s + spacing > within + 1e-9:
            break
        if s <= climb_from:
            continue
        d = dem_z_at(airport, axis_fn(s))
        if math.isnan(d):
            break
        g = abs(d - mouth_z) / (s - climb_from)
        need = g if need is None else min(need, g)
    if need is None or need > tn.ramp_max_grade + 1e-12:
        return None, None, ramp_top(airport, law, axis_fn, mouth_z, climb_from, spacing,
                                    grade=tn.ramp_max_grade, max_len=max_len)[1]
    grade = max(need, tn.ramp_grade)
    # the ulp of slack only makes the LEAST grade's own station read as met
    s_top, ss = ramp_top(airport, law, axis_fn, mouth_z, climb_from, spacing,
                         grade=grade * (1.0 + 1e-9), max_len=max_len)
    return (grade, s_top, ss) if s_top is not None else (None, None, ss)


def overlap_run_end(pair, footprints, limits, law: Law, gap: float
                    ) -> tuple[str, tuple[float, str]] | None:
    """ANOTHER STRUCTURE'S CORRIDOR ENDS THE RUN (owner RULINGS 2026-10-08d
    (1): "the run available before an obstruction").  Two structures whose
    corridors overlap were one refusal (the narrower); where one of them
    is a ramp nothing frames, built under the cap, it is the design-grade
    LENGTH that overlaps, and the cap's job to shorten it.  ``(tunnel id,
    (station, why))`` — the pair's LONGER unframed climb and the station
    where its corridor enters the other's, less the gap — or ``None``
    when neither can yield (framed, already at the cap, or its run end of
    the last pass could not be met): the refusal then stands as it was."""
    cap = law.tables.structures.tunnel.ramp_max_grade
    best = None
    for k in (0, 1):
        t, other = pair[k], pair[1 - k]
        climb = t.top_s - t.climb_from_s
        if t.source != "osm" or climb <= 0.0 or t.design_grade >= cap - 1e-9:
            continue
        old = limits.get(t.id)
        if old is not None and t.top_s > old[0] + 1e-6:
            continue                        # no grade up to the cap met it
        inter = footprints[k].intersection(footprints[1 - k])
        if inter.is_empty:
            continue
        axis = LineString(t.axis)
        end = min(axis.project(Point(x, y)) for x, y in shapely.get_coordinates(inter)) - gap
        if end <= t.climb_from_s or (old is not None and end >= old[0] - 1e-6):
            continue
        if best is None or climb > best[0]:
            best = (climb, t.id, (float(end), f"the corridor of {other.id}"))
    return None if best is None else (best[1], best[2])
