"""§37 (6) THE DESCENT FROM AN AIRSIDE CONTACT, AT ITS DESIGN GRADE (owner
RULINGS 2026-10-08c (1), 2026-10-09c (2b)).

A groundside road leaves each airside contact (a MOUTH) on a ramp: along
the road's own graph the ramp stands at ``z_contact - grade x distance``,
and the road's target is the higher of that and its floor.  The ramp is
BUILT at the design grade ``[road_contact] ramp_grade``.  The road's
longitudinal cap is the grade it steepens toward ONLY where the design
grade cannot bring the road down in THE RUN IT HAS, and then at the
smallest grade that does (``geom/ramp_grade.built_grade`` — the rule of
the mapped-tunnel ramp, spec §34 (1a)).  The run ends at

* THE ROAD'S OWN END — a vertex at an end of its route that the road's
  graph does not continue past (no neighbour stands farther from the
  contact, bar the other vertices of that same end; a page's far corner
  mid-route is not one, nor an end another route carries on from): the
  ramp must be down on the road's floor there, or the road ends in the
  air;
* ANOTHER CONTACT — its level is the airside's, so the ramp must have
  come down to it by the time it gets there.

An end nearer the contact than one lane width is the mouth itself, not a
run (the end group of §37 (10)).  Where even the cap does not fit, the
ramp is built at the cap and ends its run above the level there, exactly
as when the cap was the grade.

The product is the HIGHER envelope of every contact's ramp: per vertex
the highest ramp standing over it, and the route distance that ramp
walked.  ``airport/road_ramp.road_ramp_targets`` lifts it onto the route
and takes its max with the floor.
"""
from __future__ import annotations

import heapq
import math
import typing as _t

from ..geom.ramp_grade import built_grade, least_grade

__all__ = ["Descent", "descend", "descent_line", "envelope"]

Adjacency = _t.Mapping[int, _t.Sequence[tuple[int, float]]]
Level = _t.Callable[[int], "float | None"]
#: vertex -> the END OF ITS ROUTE it stands at (any hashable), ``None`` mid-route
EndOf = _t.Callable[[int], _t.Hashable]


class Descent(_t.NamedTuple):
    """The envelope and what each ramp was built at."""

    #: vertex -> the highest ramp level standing over it
    label: dict[int, float]
    #: vertex -> the route distance that ramp walked to it
    walked: dict[int, float]
    #: one record per ramp standing over the road's floor for a lane width
    #: or more: ``mouth``, ``grade``, ``length_m``, ``why`` it is steeper
    #: than the design grade ("" when it is not), ``fits`` (False where
    #: even the cap does not bring it down in its run)
    ramps: list[dict[str, _t.Any]]


def envelope(adj: Adjacency, seeds: _t.Mapping[int, float], grade: float,
             lab: dict[int, float] | None = None,
             walked: dict[int, float] | None = None,
             src: dict[int, int] | None = None
             ) -> tuple[dict[int, float], dict[int, float], dict[int, int]]:
    """THE HIGHER ENVELOPE OF THE SEEDS (§37 (6)): the highest level a
    seed can still be at after descending at ``grade`` along the graph — a
    max-label Dijkstra, exact because every hop only ever LOWERS the
    label.  Returns the labels, the route distance walked and the seed
    each label came from.  Given ``lab`` / ``walked`` / ``src`` it RAISES
    that envelope in place — exact when the envelope it continues was
    made at grades no steeper than ``grade`` (a label it cannot raise at
    a vertex it cannot raise beyond it)."""
    lab = {} if lab is None else lab
    walked = {} if walked is None else walked
    src = {} if src is None else src
    pq: list[tuple[float, int]] = []
    for v, z in seeds.items():
        if lab.get(v, -math.inf) < z:
            lab[v], walked[v], src[v] = z, 0.0, v
            heapq.heappush(pq, (-z, v))
    while pq:
        nz, u = heapq.heappop(pq)
        z = -nz
        if z < lab.get(u, -math.inf) - 1e-9:
            continue
        for w, d in adj.get(u, ()):
            zw = z - grade * d
            if zw > lab.get(w, -math.inf) + 1e-9:
                lab[w], walked[w], src[w] = zw, walked.get(u, 0.0) + d, src[u]
                heapq.heappush(pq, (-zw, w))
    return lab, walked, src


def _need(adj: Adjacency, m: int, z_m: float, design: float, level: Level,
          lowest: float, lane: float, contacts: _t.AbstractSet[int],
          end_of: EndOf) -> tuple[float | None, str]:
    """``(the least grade that brings contact m's ramp down at every end
    of its run, the end that asks the most)`` — ``(None, "")`` where the
    design grade already does.  The walk stops where the design-grade
    ramp is under ``lowest``, the lowest level any vertex stands at: no
    end beyond can ask for more."""
    dist: dict[int, float] = {m: 0.0}
    done: set[int] = set()
    pq: list[tuple[float, int]] = [(0.0, m)]
    need, why = None, ""
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.add(u)
        if z_m - design * d <= lowest:
            continue
        for w, e in adj.get(u, ()):
            if w not in done and d + e < dist.get(w, math.inf) - 1e-12:
                dist[w] = d + e
                heapq.heappush(pq, (d + e, w))
        lv = level(u)
        if d < lane or lv is None or lv >= z_m:
            continue
        if u in contacts:
            what = "the next contact"
        elif end_of(u) is not None and all(
                dist.get(w, math.inf) <= d + 1e-9 or end_of(w) == end_of(u)
                for w, _e in adj.get(u, ())):
            what = "the road's end"
        else:
            continue
        g = least_grade([(d, lv - z_m)])
        if g is not None and g > design + 1e-12 and (need is None or g > need):
            need, why = g, f"{what} at {d:.0f} m"
    return need, why


def descend(adj: Adjacency, mouths: _t.Mapping[int, float], level: Level,
            floors: _t.Mapping[int, float], design: float, cap: float,
            lane: float, end_of: EndOf) -> Descent:
    """THE HIGHER ENVELOPE OF THE MOUTHS, each ramp at the grade it is
    built at.  ``level(v)`` is what stands at a vertex — a contact's own
    level, a road vertex's floor (``floors``), ``None`` where nothing is
    known."""
    if not mouths:
        return Descent({}, {}, [])
    lowest = min(min(mouths.values()), min(floors.values(), default=math.inf))
    # ONE PASS names the contacts the design grade may not fit: an end's
    # level, carried UP the road at the design grade, is the highest a
    # contact there may stand for its ramp to be down at that end
    ends = {v: -float(z) for v, z in mouths.items()}
    ends.update((v, -float(z)) for v, z in floors.items() if v not in mouths and end_of(v) is not None)
    _lab, _walk, by = envelope(adj, ends, design)
    grades: dict[int, tuple[float, str, bool]] = {}
    for m in sorted(mouths):
        if by.get(m, m) == m:
            continue                          # no end stands under its ramp
        need, why = _need(adj, m, float(mouths[m]), design, level, lowest, lane,
                          mouths.keys(), end_of)
        if need is not None:
            grades[m] = (built_grade(need, design, cap) or cap, why, need <= cap + 1e-12)
    # the envelope, gentlest ramps first (see :func:`envelope`)
    lab, walked, src = envelope(adj, {m: float(z) for m, z in mouths.items()
                                      if m not in grades}, design)
    for m in sorted(grades, key=lambda m: (grades[m][0], m)):
        envelope(adj, {m: float(mouths[m])}, grades[m][0], lab, walked, src)
    length: dict[int, float] = {}
    for v, z in lab.items():
        fl = floors.get(v)
        if fl is not None and z > fl + 1e-9:
            length[src[v]] = max(length.get(src[v], 0.0), walked[v])
    ramps = [{"mouth": m, "grade": grades.get(m, (design,))[0], "length_m": length[m],
              "why": grades[m][1] if m in grades else "",
              "fits": grades[m][2] if m in grades else True}
             for m in sorted(length) if length[m] >= lane]
    return Descent(lab, walked, ramps)


def descent_line(rep: _t.Mapping[str, _t.Any]) -> str:
    """The build log's line for the ramps (the report keys
    ``road_ramp_targets`` publishes)."""
    return (f"ramps built: {rep.get('ramps', 0)} of a lane width or more at the "
            f"design grade {100.0 * (rep.get('design') or 0.0):.1f} % "
            f"({rep.get('ramps_at_design', 0)} at it, "
            f"{rep.get('ramps_steepened', 0)} steepened under the cap, "
            f"{rep.get('ramps_at_cap', 0)} at the cap "
            f"{100.0 * (rep.get('cap') or 0.0):.0f} % of which "
            f"{rep.get('ramps_over_cap', 0)} the cap does not bring down), "
            f"{rep.get('ramp_total_m', 0.0):.0f} m of ramp, longest "
            f"{rep.get('ramp_longest_m', 0.0):.0f} m")
