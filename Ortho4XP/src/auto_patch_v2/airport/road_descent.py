"""§37 (6) THE DESCENT FROM AN AIRSIDE CONTACT, AT ITS DESIGN GRADE (owner
RULINGS 2026-10-08c (1), 2026-10-09c (2b), 2026-10-09d (2); spec §37 (6a)).

A groundside road leaves an airside contact (a MOUTH) on a ramp: along
the road's own graph the ramp stands at ``z_contact - grade x distance``,
and the road's target is the higher of that and its floor.

* A RAMP EXISTS ONLY WHERE THE ROAD WOULD OTHERWISE BREAK ITS GRADE LAW
  (09d (2)): a contact the road can leave ON ITS FLOOR inside its cap
  builds none (:func:`_forced`) — the road stays on its ground.
* IT ENDS AT ITS FIRST MEET with the floor (§37 (6a) (iii)): beyond the
  meet the road is on its floor, and a later fall of the floor is the
  floor's own — no cone re-emerges over it.
* IT IS BUILT AT THE DESIGN GRADE ``[road_contact] ramp_grade``.  The
  road's longitudinal cap is the grade it steepens toward ONLY where the
  design grade cannot bring the road down in THE RUN IT HAS, and then at
  the smallest grade that does (``geom/ramp_grade.built_grade`` — the
  rule of the mapped-tunnel ramp, spec §34 (1a)).
* THE GRADE IS PER RUN, NEVER PER CONTACT (§37 (6a) (ii)).  A run is the
  walk from the contact to one END the ramp arrives over:

  - THE ROAD'S OWN END — a vertex at an end of its route that the road's
    graph does not continue past (no neighbour stands farther from the
    contact, bar the other vertices of that same end; a page's far corner
    mid-route is not one, nor an end another route carries on from): the
    ramp must be down on the road's floor there, or the road ends in the
    air;
  - ANOTHER CONTACT — its level is the airside's, so the ramp must have
    come down to it by the time it gets there.

  An end nearer the contact than one lane width is the mouth itself, not
  a run (the end group of §37 (10)).  Only the hops of the walk to that
  end are steepened; where even the cap does not fit they are at the cap
  and the road ends its run above the level there.  Every other run of
  the contact keeps the design grade.

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
#: A vertex STANDS ON A RAMP from this height over its floor (the hard
#: tolerance of the emitted rows, 2 cm); under it it is on its floor.
STAND_M = 0.02


class Descent(_t.NamedTuple):
    """The envelope and what each ramp was built at."""

    #: vertex -> the highest ramp level standing over it
    label: dict[int, float]
    #: vertex -> the route distance that ramp walked to it
    walked: dict[int, float]
    #: one record per ramp standing over the road's floor for a lane width
    #: or more: ``mouth``, ``grade`` (of its GENTLEST run) and ``steepest``
    #: (of its steepest), ``length_m``, ``why`` a run is steeper than the
    #: design grade ("" when none is), ``fits`` (the contact's own
    #: ``_Run.fits``: False where ANY of its runs needs more than the cap
    #: and so ends in the air, whatever its other runs are built at)
    ramps: list[dict[str, _t.Any]]


def envelope(adj: Adjacency, seeds: _t.Mapping[int, float], grade: float,
             lab: dict[int, float] | None = None,
             walked: dict[int, float] | None = None,
             src: dict[int, int] | None = None,
             floors: _t.Mapping[int, float] | None = None
             ) -> tuple[dict[int, float], dict[int, float], dict[int, int]]:
    """THE HIGHER ENVELOPE OF THE SEEDS (§37 (6)): the highest level a
    seed can still be at after descending at ``grade`` along the graph — a
    max-label Dijkstra, exact because every hop only ever LOWERS the
    label.  Returns the labels, the route distance walked and the seed
    each label came from.  Given ``lab`` / ``walked`` / ``src`` it RAISES
    that envelope in place.

    Given ``floors`` A CONE ENDS WHERE IT FIRST MEETS ITS FLOOR (§37 (6a)
    (iii)): a vertex whose label stands at or under its floor carries the
    label and propagates nothing (the seeds excepted) — beyond the meet
    the road is on its floor, and a later fall of the floor is the
    floor's own, no ramp."""
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
        if floors is not None and u not in seeds and z <= floors.get(u, -math.inf) + 1e-9:
            continue                          # the ramp met its floor here
        for w, d in adj.get(u, ()):
            zw = z - grade * d
            if zw > lab.get(w, -math.inf) + 1e-9:
                lab[w], walked[w], src[w] = zw, walked.get(u, 0.0) + d, src[u]
                heapq.heappush(pq, (-zw, w))
    return lab, walked, src


class _Run(_t.NamedTuple):
    """One contact's ramp: the tree its design-grade cone walked and the
    grade each vertex of it is built at."""

    #: vertices in walk order (the contact first), each after its ``pred``
    order: list[int]
    dist: dict[int, float]
    pred: dict[int, int]
    #: vertex -> the grade of the hop INTO it, where steeper than design
    steep: dict[int, float]
    why: str
    fits: bool


def _meets(mouths: _t.Mapping[int, float], floors: _t.Mapping[int, float],
           adj: Adjacency) -> dict[int, float]:
    """vertex -> the level a cone ENDS at when it comes down to it (first
    meet): the road's floor there; another contact's own level (that
    contact's ramp is the higher one from there on); where neither is
    known, the lowest level anything stands at (no ramp goes under it)."""
    lowest = min(min(mouths.values()), min(floors.values(), default=math.inf))
    return {**dict.fromkeys(adj, lowest), **floors, **mouths}


def _forced(adj: Adjacency, m: int, z_m: float, cap: float,
            meets: _t.Mapping[int, float], floors: _t.Mapping[int, float],
            stand: float) -> bool:
    """THE ROAD CANNOT FOLLOW ITS FLOOR FROM CONTACT ``m`` INSIDE ITS CAP
    (owner RULINGS 2026-10-09d (2): "the road should only be graded where
    something would cause it to violate its grade rules"): coming down
    from the contact AT THE CAP — the steepest it lawfully may — it still
    stands ``stand`` or more over its floor somewhere.  Where it does
    not, the floor is followable from the contact and there is no ramp."""
    lab, _w, _s = envelope(adj, {m: z_m}, cap, floors=meets)
    return any(z >= floors[v] + stand for v, z in lab.items() if v in floors and v != m)


def _hop(z_p: float, p: int, u: int, e: float, grade: float, cap: float,
         m: int, floors: _t.Mapping[int, float]) -> float:
    """The ramp's level at ``u``, one hop of ``e`` metres on from ``p``
    where it stands at ``z_p``: down at ``grade`` — and, past the
    contact's first hop, NEVER HIGHER OVER THE ROAD'S FLOOR THAN IT STOOD
    AT ``p`` (RULINGS 2026-10-09d (2): a ramp does not stand on fill over
    ground the road can follow).  Where the floor falls away faster than
    the grade the ramp follows that fall, at the cap at most, instead of
    opening a growing embankment over the hillside."""
    z = z_p - grade * e
    if p != m and p in floors and u in floors:
        z = max(min(z, floors[u] + (z_p - floors[p])), z_p - cap * e)
    return z


def _run(adj: Adjacency, m: int, z_m: float, design: float, cap: float,
         level: Level, floors: _t.Mapping[int, float], lane: float,
         mouths: _t.Mapping[int, float], meets: _t.Mapping[int, float],
         end_of: EndOf) -> _Run:
    """Contact ``m``'s ramp, EACH RUN AT ITS OWN GRADE (§37 (6a) (ii)).
    The design-grade cone is walked to its first meet; an END of the
    road it arrives over — the road's own end, the next contact — asks
    the least grade that is down there, of THE WALK TO THAT END ONLY:
    the hops of that one path are steepened (to the cap at most), every
    other run of the contact keeps the design grade."""
    dist: dict[int, float] = {m: 0.0}
    pred: dict[int, int] = {}
    at: dict[int, float] = {m: z_m}
    order: list[int] = []
    done: set[int] = set()
    pq: list[tuple[float, int]] = [(0.0, m)]
    asks: list[tuple[int, float, str]] = []
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.add(u)
        order.append(u)
        if u != m:
            p = pred[u]
            at[u] = _hop(at[p], p, u, d - dist[p], design, cap, m, floors)
        z = at[u]
        if u == m or z > meets.get(u, -math.inf) + 1e-9:
            for w, e in adj.get(u, ()):
                if w not in done and d + e < dist.get(w, math.inf) - 1e-12:
                    dist[w], pred[w] = d + e, u
                    heapq.heappush(pq, (d + e, w))
        lv = level(u)
        if d < lane or lv is None or lv >= z:
            continue
        if u in mouths:
            what = "the next contact"
        elif end_of(u) is not None and all(
                dist.get(w, math.inf) <= d + 1e-9 or end_of(w) == end_of(u)
                for w, _e in adj.get(u, ())):
            what = "the road's end"
        else:
            continue
        g = least_grade([(d, lv - z_m)])
        if g is not None and g > design + 1e-12:
            asks.append((u, g, f"{what} at {d:.0f} m"))
    steep: dict[int, float] = {}
    for u, g, _why in asks:
        b = built_grade(g, design, cap) or cap
        while u != m and steep.get(u, 0.0) < b:
            steep[u] = b
            u = pred[u]
    worst = max(asks, key=lambda a: (a[1], -a[0]), default=None)
    return _Run(order, dist, pred, steep, worst[2] if worst else "",
                all(g <= cap + 1e-12 for _u, g, _w in asks))


def descend(adj: Adjacency, mouths: _t.Mapping[int, float], level: Level,
            floors: _t.Mapping[int, float], design: float, cap: float,
            lane: float, end_of: EndOf, stand: float = STAND_M) -> Descent:
    """THE HIGHER ENVELOPE OF THE MOUTHS, each ramp at the grade it is
    built at.  ``level(v)`` is what stands at a vertex — a contact's own
    level, a road vertex's floor (``floors``), ``None`` where nothing is
    known.  A contact the road can leave on its floor inside its cap
    builds NO ramp (:func:`_forced`); a ramp ENDS at its first meet with
    the floor; ``stand`` is the height over its floor from which a
    vertex counts as standing on a ramp."""
    if not mouths:
        return Descent({}, {}, [])
    meets = _meets(mouths, floors, adj)
    lab: dict[int, float] = {m: float(z) for m, z in mouths.items()}
    walked: dict[int, float] = dict.fromkeys(mouths, 0.0)
    src: dict[int, int] = {m: m for m in mouths}
    grade_at: dict[int, float] = {}
    runs: dict[int, _Run] = {}
    for m in sorted(mouths):
        z_m = float(mouths[m])
        if not _forced(adj, m, z_m, cap, meets, floors, stand):
            continue
        run = runs[m] = _run(adj, m, z_m, design, cap, level, floors, lane, mouths,
                             meets, end_of)
        own: dict[int, float] = {m: z_m}
        for u in run.order[1:]:
            p = run.pred[u]
            if p not in own or (p != m and own[p] <= meets.get(p, -math.inf) + 1e-9):
                continue                      # the ramp met its floor before here
            g = run.steep.get(u, design)
            own[u] = _hop(own[p], p, u, run.dist[u] - run.dist[p], g, cap, m, floors)
            if own[u] > lab.get(u, -math.inf) + 1e-9:
                lab[u], walked[u], src[u], grade_at[u] = own[u], run.dist[u], m, g
    length: dict[int, float] = {}
    least: dict[int, float] = {}
    most: dict[int, float] = {}
    for v, z in lab.items():
        fl = floors.get(v)
        if fl is not None and v not in mouths and z >= fl + stand:
            m = src[v]
            length[m] = max(length.get(m, 0.0), walked[v])
            least[m] = min(least.get(m, math.inf), grade_at[v])
            most[m] = max(most.get(m, 0.0), grade_at[v])
    ramps = [{"mouth": m, "grade": least[m], "steepest": most[m], "length_m": length[m],
              "why": runs[m].why if most[m] > design + 1e-12 else "",
              "fits": runs[m].fits}
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
