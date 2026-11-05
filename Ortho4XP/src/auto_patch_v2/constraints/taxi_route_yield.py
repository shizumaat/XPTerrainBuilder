"""THE TAXI ROUTE EXCEPTION — a taxi route between two FIXED levels its letter
cap cannot join takes the smallest uniform grade that fits, never above the
ceiling (owner RULINGS 2026-11-05a, issue #1893; the taxi twin of the
runway's §50.1 "smallest uniform over-grade that fits", ``runway_yield``).

Owner, verbatim: "It should be 1.5% everywhere that's physically possible,
allowing exceptions up to 2% when there's no other way and spreading it
across the largest possible distance."

THE WITNESS.  The fixed levels are the runways' own profile targets
(``PlanarMap.preferred_z`` on runway-family vertices, set by
``runway_chord`` through the CIFP pins) — the levels the runway-first stage
solves to.  On THE CHAIN (``routes.build_routes``, the rows RULINGS 05ac
makes the taxi law: the centreline stretches, the runway ridges, the
crossings and the LATERAL hops at the transverse cap — the hop is what ties
a stub's centreline to the runway edge it meets; never a pad contact),
every vertex's lawful interval from the fixed levels is
``[max_r z_r − b(r, v), min_r z_r + b(r, v)]`` with ``b`` the
least ``Σ cap·len`` (two multi-source Dijkstras).  An EMPTY interval is the
proof: the highest and lowest contacts that close it are joined by a route
(the two shortest-budget paths through that vertex) whose stretches cannot
lose their height difference at the letter cap — measured at HECA, the
05C/23C NW stub to the 23R mouth: 3,170 m of T / T4 / U / J3 / G / J1 / J
needing 52.0 m against the 47.6 m 1.5 % grants (1.64 %).

THE YIELD.  Every STRETCH that route runs over takes ``max(own cap, g)``,
``g`` the uniform grade over those stretches' metres that closes the gap
(the route's fixed edges — a runway ridge, a crossing — keep their caps),
plus ``[design] runway_yield_margin`` so the fit is numerically real.  The
whole route is raised, end to end, so the excess is spread over its whole
length rather than dumped on one leg.  ``g`` above ``taxi.longitudinal_
exception_max`` is held at the ceiling and the record says so
(``over_ceiling``): the build prints it, the sidecar ``taxi_route_caps``
names it, and the §5a check names the conflict that is left.  Repeated
until no interval is empty: a raised route can expose the next one.

Read back through ``stretches.build_stretches`` (the stretch's ``cap_l``),
so the centreline rows, the route edges, the box, the transverse axes and
the published ``stretches`` / ``axes`` all price the one value.  Empty —
nothing built — where every route fits its letter.
"""
from __future__ import annotations

import dataclasses as _dc
import heapq
import typing as _t

from ..law import Law
from ..law.tables import role_family
from ..model.airport import Airport
from ..model.planar import PlanarMap

__all__ = ["TaxiRoute", "derive", "edge_key", "route_lines"]

#: an interval shorter than this is the solver's tolerance, not a law gap
#: (metres; ``[design] hard_tol_m`` is the solve's own held bar)
_ROUNDS = 200


@_dc.dataclass(frozen=True)
class TaxiRoute:
    """One yielded route: its two fixed ends, its length, the grade it
    needs, the cap its stretches were raised to and the stretch EDGES it
    runs over, each by its two ends' CANONICAL keys (the shape stage splits
    vertices after this is derived, so ids are no identity; memory
    ``canonical-identity-join``)."""

    high_ll: tuple[float, float]
    low_ll: tuple[float, float]
    high_z: float
    low_z: float
    length_m: float
    needed: float
    cap: float
    table: float
    over_ceiling: bool
    edges: frozenset[tuple[tuple[float, float], tuple[float, float]]]

    def as_dict(self) -> dict[str, _t.Any]:
        """The PUBLISHED record (sidecar ``taxi_route_caps``)."""
        return {"high": [round(self.high_ll[0], 8), round(self.high_ll[1], 8)],
                "low": [round(self.low_ll[0], 8), round(self.low_ll[1], 8)],
                "high_z": round(self.high_z, 3), "low_z": round(self.low_z, 3),
                "length_m": round(self.length_m, 1), "needed": round(self.needed, 6),
                "cap": round(self.cap, 6), "table": self.table,
                "over_ceiling": self.over_ceiling, "edges": len(self.edges)}


def _contacts(pm: PlanarMap, law: Law, nodes: _t.Iterable[int]) -> dict[int, float]:
    """Network vertex -> its FIXED level: a runway-family vertex with a
    profile target (``preferred_z``)."""
    out: dict[int, float] = {}
    pz = pm.preferred_z
    for v in nodes:
        if v not in pz or v not in pm.vertices:
            continue
        if any(role_family(law, pm.faces[f].role) == "runway"
               for f in pm.vertices[v].incident_faces):
            out[v] = float(pz[v])
    return out


def _dijkstra(adj, src: _t.Mapping[int, float], sign: float):
    """``best[v] = min_r (sign·z_r + b(r, v))`` with its predecessor edge."""
    best: dict[int, float] = {}
    prev: dict[int, tuple[int, int]] = {}
    h = [(sign * z, v, v, -1) for v, z in src.items()]
    heapq.heapify(h)
    while h:
        d, v, p, i = heapq.heappop(h)
        if v in best:
            continue
        best[v] = d
        if i >= 0:
            prev[v] = (p, i)
        for u, w, j in adj.get(v, ()):
            if u not in best:
                heapq.heappush(h, (d + w(), u, v, j))
    return best, prev


def _walk(prev, v: int) -> list[int]:
    """The edge indices from ``v`` back to its source."""
    out: list[int] = []
    while v in prev:
        v, i = prev[v]
        out.append(i)
    return out


def derive(pm: PlanarMap, law: Law, airport: Airport | None) -> tuple[TaxiRoute, ...]:
    """Every yielded route of ``pm`` (module docstring); empty where none."""
    ceiling = getattr(law.ruleset.taxi, "longitudinal_exception_max", None)
    if ceiling is None or not pm.preferred_z:
        return ()
    from .routes import CENTRELINE, CROSSING, LATERAL, routes
    from .stretches import build_stretches
    st = build_stretches(pm, law)
    g = routes(pm, law, airport)
    sid_of: dict[tuple[int, int], int] = {}
    for s in st.items:
        for eid in s.edges:
            e = pm.edges[eid]
            sid_of[(min(e.a, e.b), max(e.a, e.b))] = s.id
    lift: dict[int, float] = {}
    edges: list[tuple[int, int, float, float, int | None]] = []   # a, b, cap, len, sid
    for a, b, c, ln, k in zip(g.a, g.b, g.cap, g.length, g.kind, strict=True):
        if int(k) not in (CENTRELINE, CROSSING, LATERAL):
            continue
        a, b = int(a), int(b)
        pa = g.foot[a][:2] if g.is_foot(a) else None
        pb = g.foot[b][:2] if g.is_foot(b) else None
        seg = (a, b) if pa is None and pb is None else (pa or pb)
        sid = sid_of.get((min(seg), max(seg))) if int(k) == CENTRELINE else None
        edges.append((a, b, float(c), float(ln), sid))
    adj: dict[int, list] = {}
    nodes = {v for e in edges for v in e[:2] if v < g.n_planar}
    fixed = _contacts(pm, law, nodes)
    if len(fixed) < 2:
        return ()

    def weight(j: int) -> _t.Callable[[], float]:
        a, b, c, ln, sid = edges[j]
        return lambda: max(c, lift.get(sid, 0.0)) * ln if sid is not None else c * ln
    for j, (a, b, _c, _ln, _sid) in enumerate(edges):
        if a in fixed and b in fixed:
            continue                      # two fixed levels: the runway's own law
        w = weight(j)
        adj.setdefault(a, []).append((b, w, j))
        adj.setdefault(b, []).append((a, w, j))
    tol = float(law.tables.emit.design.hard_tol_m)
    margin = float(law.tables.emit.design.runway_yield_margin)
    out: list[TaxiRoute] = []
    for _round in range(_ROUNDS):
        up, prev_u = _dijkstra(adj, fixed, 1.0)       # ceiling: min z_r + b
        dn, prev_d = _dijkstra(adj, fixed, -1.0)      # -floor: min -z_r + b
        worst = max(((-dn[v] - up[v], v) for v in up if v in dn), default=(0.0, -1))
        if worst[0] <= tol:
            break
        v = worst[1]
        path = _walk(prev_d, v) + _walk(prev_u, v)
        ends_hi, ends_lo = _source(prev_d, v), _source(prev_u, v)
        z_hi, z_lo = fixed[ends_hi], fixed[ends_lo]
        free = [j for j in path if edges[j][4] is not None]
        fixed_b = sum(edges[j][2] * edges[j][3] for j in path if edges[j][4] is None)
        run = sum(edges[j][3] for j in free)
        if run <= 0.0:
            break
        need = (z_hi - z_lo - fixed_b) / run
        table = min(st.items[edges[j][4]].cap_l for j in free)
        # never above the ceiling, never below what the stretches already
        # carry (a steep runway's yield, 30ah (1), may already exceed it)
        cap = max(table, min(need + margin, float(ceiling)))
        raised = False
        for j in free:
            sid = edges[j][4]
            if cap > max(st.items[sid].cap_l, lift.get(sid, 0.0)):
                lift[sid] = cap
                raised = True
        out.append(TaxiRoute(pm.vertices[ends_hi].key, pm.vertices[ends_lo].key, z_hi, z_lo,
                             sum(edges[j][3] for j in path), need, cap, table,
                             need + margin > float(ceiling),
                             frozenset(edge_key(pm, e) for j in free
                                       for e in st.items[edges[j][4]].edges)))
        if not raised:
            break                                     # held at the ceiling: §5a names the rest
    return tuple(out)


def edge_key(pm: PlanarMap, eid: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """A planar edge by its two ends' canonical keys, ordered."""
    e = pm.edges[eid]
    ka, kb = tuple(pm.vertices[e.a].key), tuple(pm.vertices[e.b].key)
    return (ka, kb) if ka <= kb else (kb, ka)


def _source(prev, v: int) -> int:
    while v in prev:
        v = prev[v][0]
    return v


def route_lines(icao: str, routes_: _t.Sequence[TaxiRoute]) -> list[str]:
    """One loud line per yielded route (the build's console and report)."""
    return [f"[{icao}] TAXI ROUTE EXCEPTION (11-05a): {r.length_m:.0f} m from "
            f"{r.high_ll[0]:.6f},{r.high_ll[1]:.6f} ({r.high_z:.2f} m) to "
            f"{r.low_ll[0]:.6f},{r.low_ll[1]:.6f} ({r.low_z:.2f} m) needs "
            f"{100 * r.needed:.2f} % against {100 * r.table:.2f} %: "
            + (f"OVER THE CEILING, NOT MET (held at {100 * r.cap:.2f} %)" if r.over_ceiling
               else f"raised to {100 * r.cap:.2f} %")
            for r in routes_]
