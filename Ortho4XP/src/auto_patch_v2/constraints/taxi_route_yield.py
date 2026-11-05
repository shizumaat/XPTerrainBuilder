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

__all__ = ["TaxiRoute", "apron_yields", "derive", "edge_key", "route_lines"]

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
    #: the APRON faces the route crosses (ruled 06:01Z, option a): they rise
    #: with it, through ``PlanarMap.taxi_caps`` (the 10-10j apron channel)
    aprons: tuple[int, ...] = ()

    def as_dict(self) -> dict[str, _t.Any]:
        """The PUBLISHED record (sidecar ``taxi_route_caps``)."""
        return {"high": [round(self.high_ll[0], 8), round(self.high_ll[1], 8)],
                "low": [round(self.low_ll[0], 8), round(self.low_ll[1], 8)],
                "high_z": round(self.high_z, 3), "low_z": round(self.low_z, 3),
                "length_m": round(self.length_m, 1), "needed": round(self.needed, 6),
                "cap": round(self.cap, 6), "table": self.table,
                "over_ceiling": self.over_ceiling, "edges": len(self.edges),
                "aprons": len(self.aprons)}


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


#: the HARD row heads of the route graph (11-05a, ruled 06:01Z option a):
#: the centreline rows rise with a route (by STRETCH), the apron's hard
#: rows rise with it (by FACE), the lateral hops and crossings never do
_TAXI_RISES = frozenset({"rulesets.taxi.longitudinal centreline"})
_APRON_RISES = frozenset({"common.roles.apron ring edge", "common.roles.apron frontage chord",
                          "common.roles.apron on the shared edge portion",
                          "apron body chord, stationed across the face"})
_FIXED = frozenset({"rulesets.taxi.transverse lateral hop, chain",
                    "rulesets.runway.longitudinal crossing, chain",
                    "common.roles.apron lateral hop, chain"})


def _head(row) -> str:
    return row.source.ruling.split(" (")[0].strip()


def _row_face(row) -> int | None:
    tag = next((t for t in (row.source.inputs or ()) if isinstance(t, str)
                and t.startswith("face:")), None)
    return None if tag is None else int(tag[5:])


def _graph(pm: PlanarMap, law: Law, airport, st) -> list[tuple[int, int, float, float, tuple | None]]:
    """THE HARD PAIR GRAPH the route reads: ``(a, b, cap, metres, key)`` per
    row — ``key`` ``("s", stretch)`` / ``("f", apron face)`` where the row
    rises with a route, ``None`` where it never does.  A lateral hop to a
    centreline FOOT (three terms) is read as two pair edges to the
    segment's ends, ``bound + t·cap·len`` (the hop's own bound and the run
    to that end)."""
    from ..model.constraints import Diff, Linear
    from . import apron, taxi
    sid_of = {}
    for s in st.items:
        for eid in s.edges:
            e = pm.edges[eid]
            sid_of[(min(e.a, e.b), max(e.a, e.b))] = s.id
    rows = [*taxi.taxi_centerlines(pm, law, airport), *taxi.taxi_chain(pm, law, airport),
            *apron.apron_within_shape(pm, law, airport), *apron.apron_edge_portions(pm, law, airport)]
    out: list[tuple[int, int, float, float, tuple | None]] = []
    for r in rows:
        h = _head(r)
        if isinstance(r, Diff):
            a, b = int(r.a), int(r.b)
            if a == b or float(getattr(r, "rel", 0.0) or 0.0):
                continue
            cap = float(r.ceiling) if r.soft is not None and r.ceiling is not None else float(r.cap)
            if h in _TAXI_RISES:
                sid = sid_of.get((min(a, b), max(a, b)))
                out.append((a, b, cap, float(r.d), None if sid is None else ("s", sid)))
            elif h in _APRON_RISES:
                f = _row_face(r)
                out.append((a, b, cap, float(r.d), None if f is None else ("f", f)))
            elif h in _FIXED:
                out.append((a, b, cap, float(r.d), None))
        elif isinstance(r, Linear) and h in _FIXED and len(r.terms) == 3:
            (v, _c), (fa, _ca), (fb, cb) = r.terms
            bound, t = float(r.hi), -float(cb)
            (xa, ya), (xb, yb) = pm.vertices[fa].xy, pm.vertices[fb].xy
            ln = ((xa - xb) ** 2 + (ya - yb) ** 2) ** 0.5
            sid = sid_of.get((min(fa, fb), max(fa, fb)))
            c = st.items[sid].cap_l if sid is not None else 0.0
            out.append((int(v), int(fa), bound + t * c * ln, 1.0, None))
            out.append((int(v), int(fb), bound + (1.0 - t) * c * ln, 1.0, None))
    return out


def derive(pm: PlanarMap, law: Law, airport: Airport | None) -> tuple[TaxiRoute, ...]:
    """Every yielded route of ``pm`` (module docstring); empty where none."""
    ceiling = getattr(law.ruleset.taxi, "longitudinal_exception_max", None)
    if ceiling is None or not pm.preferred_z:
        return ()
    from .precedence import face_cap
    from .stretches import build_stretches
    st = build_stretches(pm, law)
    edges = _graph(pm, law, airport, st)
    fixed = _contacts(pm, law, {v for e in edges for v in e[:2]})
    if len(fixed) < 2:
        return ()

    def table(key: tuple) -> float:
        if key[0] == "s":
            return st.items[key[1]].cap_l
        return face_cap(law, pm.faces[key[1]], pm)[0]
    lift: dict[tuple, float] = {}

    def weight(j: int) -> _t.Callable[[], float]:
        _a, _b, c, ln, key = edges[j]
        return (lambda: max(c, lift.get(key, 0.0)) * ln) if key is not None else (lambda: c * ln)
    adj: dict[int, list] = {}
    for j, (a, b, _c, _ln, _k) in enumerate(edges):
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
        keys = {edges[j][4] for j in free}
        tab = min(table(k) for k in keys)
        # never above the ceiling, never below what the route already
        # carries (a steep runway's yield, 30ah (1), may already exceed it)
        cap = max(tab, min(need + margin, float(ceiling)))
        raised = False
        for k in keys:
            if cap > max(table(k), lift.get(k, 0.0)):
                lift[k] = cap
                raised = True
        out.append(TaxiRoute(pm.vertices[ends_hi].key, pm.vertices[ends_lo].key, z_hi, z_lo,
                             sum(edges[j][3] for j in path), need, cap, tab,
                             need + margin > float(ceiling),
                             frozenset(edge_key(pm, e) for k in keys if k[0] == "s"
                                       for e in st.items[k[1]].edges),
                             tuple(sorted(k[1] for k in keys if k[0] == "f"))))
        if not raised:
            break                                     # held at the ceiling: §5a names the rest
    return tuple(out)


def apron_yields(pm: PlanarMap, law: Law, routes_: _t.Sequence[TaxiRoute],
                 caps: _t.Mapping[int, _t.Any]) -> dict[int, _t.Any]:
    """``caps`` (``PlanarMap.taxi_caps``) with every apron face a route
    crosses at that route's cap — the record ``face_cap`` already reads for
    an apron that follows (10-10j); the larger cap where a face has two."""
    from .precedence import face_cap
    from .runway_yield import TaxiYield
    out = dict(caps)
    for r in routes_:
        for f in r.aprons:
            had = out.get(f)
            if had is not None and had.cap >= r.cap:
                continue
            table = face_cap(law, pm.faces[f], None)[0]
            out[f] = TaxiYield(f, "taxi route (11-05a)", float(r.cap), table, float(r.cap))
    return out


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
