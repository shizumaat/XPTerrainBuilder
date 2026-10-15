"""THE TAXI TREND HELD TO THE TAXI LAW — the ground's long-wave trend,
made a target a taxiway may lawfully run on (owner decision 2026-10-15g,
"fix slope cap"; issue #742).

``constraints/taxi_trend`` fits every taxi centreline chain to the
ground's trend.  The trend is WEAK (``[design] taxi_trend``) and the taxi
caps are ``law`` rows, so a trend steeper than the cap is a standing pull
AGAINST the law that the solve settles by trade.  MEASURED at KCLT: the
loop T/V crosses a real drainage valley (lidar 226.2 -> 217.3 m), its
trend runs at 2.5-3.6 % under a 1.5 % cap, and the trade leaves +46
``airside_no_step`` / +7 ``taxi_box`` rows that a zero trend weight does
not.  Two holds make the target lawful, both minimum interventions:

1. ALONG THE CHAIN (:func:`capped_chain`): the trend read at the chain's
   own stations is clamped to the chain's longitudinal cap by THE CORE'S
   CLAMP (``O4_Vector_Utils.cap_lipschitz_profile`` through
   ``geom/core_clamp``, the one authority) — the identity wherever the
   trend already holds the cap.
2. ACROSS THE NETWORK (:func:`held_by_contacts`): the targets are
   projected onto THE NO-STEP LAW'S OWN PAIRS (``emit.no_step``: the ``k``
   nearest by route inside ``window_m``, each at its path's ``Σ cap·len``)
   — every pair of targets inside its budget, and every target inside the
   budget of the runway's values (``preferred_z``) inside the same window.
   A chain's own clamp is not enough: two chains meeting at a junction
   keep their own trends (KCLT: the loop's junction vertex took a 93 m
   chain's target, 3.5 % against the loop's next station), and the trend
   a LONG chain extends across its faces reaches vertices a few metres
   from a runway mouth whose short chain has no fit of its own (KCLT: a
   27 m stub, its runway contact 1.0 m under the loop's trend handed to
   its far end).  Each pass moves a target to the mid of the interval its
   pairs allow — the core clamp's own construction read over the pairs —
   then clips it into its contacts' interval.  A WINDOW, never the whole
   network: a runway value 3 km away is no pair the law prices (HECA: one
   52 m higher 3.1 km off set a stub's floor 5 m over its own mouth when
   the whole network was read).
"""
from __future__ import annotations

import typing as _t

import numpy as np

from .precedence import view
from .routes import route_neighbours, routes
from ..geom.core_clamp import core_vector_utils
from ..law import Law
from ..law.tables import apron_roles
from ..model.airport import Airport
from ..model.planar import PlanarMap

if _t.TYPE_CHECKING:                                    # pragma: no cover
    from .taxi_trend import _Chain

__all__ = ["capped_chain", "held_by_contacts", "stage_one_contacts"]

#: a target moved by less than this is not counted as held (metres)
_MOVED_M = 1e-6


def _chain_caps(c: "_Chain", pm: PlanarMap, law: Law,
                caps_of: _t.Mapping) -> list[float] | None:
    """Per SEGMENT of ``c``, the strictest longitudinal cap of the taxi
    faces at its two vertices (the cap the taxi law grades it at; a runway
    contact's runway face is not the chain's own and is skipped).  ``None``
    when a segment has no governed taxi face (nothing to hold it to)."""
    taxi = set(law.tables.precedence.taxi_family.members)
    per_v: list[float | None] = []
    for v in c.vertices:
        best = None
        for fid in pm.vertices[v].incident_faces:
            if pm.faces[fid].role not in taxi:
                continue
            cap = caps_of.get(fid)
            if cap is not None:
                best = cap[0] if best is None else min(best, cap[0])
        per_v.append(best)
    out: list[float] = []
    for a, b in zip(per_v, per_v[1:]):
        got = [x for x in (a, b) if x is not None]
        if not got:
            return None
        out.append(min(got))
    return out


def capped_chain(at: _t.Callable[[float], float | None], c: "_Chain",
                 pm: PlanarMap, law: Law, caps_of: _t.Mapping
                 ) -> _t.Callable[[float], float | None]:
    """HOLD (1), module docstring: the trend ``at`` read at ``c``'s
    stations, clamped to the chain's cap by the core's clamp, read back
    linearly between stations.  A chain whose trend is unreadable at any
    station, which has no governed taxi segment, or whose trend already
    holds its cap, is returned unchanged."""
    caps = _chain_caps(c, pm, law, caps_of)
    if not caps:
        return at
    vals = [at(s) for s in c.stations]
    if any(v is None for v in vals):
        return at
    st = np.asarray(c.stations, dtype=float)
    z = np.asarray(vals, dtype=float)
    clamped = np.asarray(core_vector_utils().cap_lipschitz_profile(
        st, z, np.asarray(caps, dtype=float)), dtype=float)
    if float(np.abs(clamped - z).max()) <= 1e-9:
        return at

    def lawful_at(q: float) -> float | None:
        if q < st[0] or q > st[-1]:
            return at(q)
        return float(np.interp(q, st, clamped))

    return lawful_at


#: passes of the pair projection (:func:`held_by_contacts`) — it stops
#: once no pair exceeds its budget by more than :data:`_SETTLED_M`, or when
#: :data:`_STALL_PASSES` passes have not cut the worst excess by
#: :data:`_STALL_GAIN` (a pair set that cannot all hold — two contacts a
#: connector is too short for — settles to a fixed residual, never to 0)
_PASSES = 2000
_SETTLED_M = 1e-3
_STALL_PASSES = 50
_STALL_GAIN = 0.01


def _pairs(g, sources, window_m: float, k: int, targets) -> dict[int, list]:
    """vertex -> ``[(other, budget, route metres), ...]`` over the route
    pairs (``routes.route_neighbours``: the ``k`` nearest by route distance
    inside ``window_m``, each with the path's ``Σ cap·len``)."""
    out: dict[int, list] = {}
    for a, b, d, bud in route_neighbours(g, sources, window_m, k,
                                         targets=targets):
        out.setdefault(a, []).append((b, bud, d))
        out.setdefault(b, []).append((a, bud, d))
    return out


def _box_pairs(pm: PlanarMap, law: Law, airport: Airport | None
               ) -> dict[int, list]:
    """vertex -> ``[(other, budget, plan metres), ...]`` over THE TAXI
    SHORT-PAIR POPULATION (``constraints/taxi.short_pairs``: every ring pair
    of a taxi plane face under ``withdrawn_chord_min_m``, the population
    ``taxi.taxi_box`` prices), each at the face's STRICTER cap over the
    plan distance — never above the box's own bound (``cL·|Δs| + cT·|Δt|
    >= min(cL, cT)·d``), and without the axis search that makes the box
    itself cost seconds.  The route metric alone is blind here: at a
    runway mouth a contact 3 m away in plan can be 58 m away by route
    (leaf -> centreline -> leaf), a 0.87 m budget the box prices at 0.05 m
    (KCLT 35.22737, -80.95343)."""
    from .taxi import short_pairs
    vw = view(pm, law)
    members = law.tables.precedence.taxi_family.members
    mesh = frozenset(law.tables.emit.within_shape.junction_mesh_roles)
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    max_d = law.tables.emit.within_shape.withdrawn_chord_min_m
    out: dict[int, list] = {}
    for f in vw.faces_of_role(members):
        cap = vw.caps[f.id]
        if f.role in mesh or cap is None:
            continue
        c = min(float(cap[0]), float(cap[1]))
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            for a, b, d in short_pairs(vw.xy, ring, min_d, max_d):
                out.setdefault(a, []).append((b, c * d, d))
                out.setdefault(b, []).append((a, c * d, d))
    return out


def _contact_bounds(pm: PlanarMap, g, law: Law, targets, contacts,
                    box: _t.Mapping[int, list] | None = None
                    ) -> tuple[dict[int, tuple[float, float]], list[dict]]:
    """Per target, ``(floor, ceiling)`` from the contacts inside the no-step
    window, and THE SHORT CONNECTORS: every pair of contacts whose interval
    at a target is empty — the pavement between them is too short to lose
    their height difference at the cap.  One record per contact pair, the
    worst target: its run (route metres through the target), the height,
    the grade it would need and the grade the caps allow."""
    ns = law.tables.emit.no_step
    tset = set(targets)
    bound: dict[int, tuple[float, float]] = {}
    short: dict[tuple[int, int], dict] = {}
    # partners are TARGETS only: a contact's own neighbours (the runway's
    # other vertices) would spend its ``k`` before the mouth's targets
    by_v = _pairs(g, contacts, float(ns.window_m), 4 * int(ns.k), tset)
    for v, ps in (box or {}).items():
        if v in tset:
            by_v.setdefault(v, []).extend(r for r in ps if r[0] in contacts)
    for v, ps in by_v.items():
        if v not in tset:
            continue
        got = [(contacts[u], b, d, u) for u, b, d in ps if u in contacts]
        if not got:
            continue
        lo = max(got, key=lambda r: r[0] - r[1])
        hi = min(got, key=lambda r: r[0] + r[1])
        bound[v] = (lo[0] - lo[1], hi[0] + hi[1])
        if bound[v][0] <= bound[v][1]:
            continue
        run = lo[2] + hi[2]
        height = lo[0] - hi[0]
        key = (lo[3], hi[3])
        excess = bound[v][0] - bound[v][1]
        if key not in short or excess > short[key]["excess_m"]:
            short[key] = {
                "ll": [pm.vertices[v].key[0], pm.vertices[v].key[1]],
                "high_ll": [pm.vertices[lo[3]].key[0], pm.vertices[lo[3]].key[1]],
                "low_ll": [pm.vertices[hi[3]].key[0], pm.vertices[hi[3]].key[1]],
                "run_m": round(run, 1), "height_m": round(height, 3),
                "grade_needed_pct": round(100.0 * height / run, 2) if run else None,
                "grade_allowed_pct": round(100.0 * (lo[1] + hi[1]) / run, 2)
                if run else None,
                "excess_m": round(excess, 3)}
    return bound, sorted(short.values(), key=lambda r: -r["excess_m"])


def _senior_first(senior: dict[int, tuple[float, float]],
                  junior: dict[int, tuple[float, float]]
                  ) -> dict[int, tuple[float, float]]:
    """The bound per target with the SENIOR contacts first: a junior bound
    (an apron level) narrows a senior one (the runway's) only where the two
    intersect; where they do not, the runway holds and the apron's is
    dropped (the runway is senior, precedence table).  An empty senior
    interval is kept as it is (reported, never clipped)."""
    out = dict(senior)
    for v, (lo, hi) in junior.items():
        if lo > hi:
            continue
        s = out.get(v)
        if s is None:
            out[v] = (lo, hi)
        elif s[0] <= s[1] and max(lo, s[0]) <= min(hi, s[1]):
            out[v] = (max(lo, s[0]), min(hi, s[1]))
    return out


def _project(targets: dict[int, float], own: _t.Mapping[int, list],
             bound: _t.Mapping[int, tuple[float, float]]
             ) -> tuple[dict[int, float], int, float, bool]:
    """THE PROJECTION, vectorised (Jacobi over every pair at once): each
    pass sets every target to the mid of ``max(T_u - b) .. min(T_u + b)``
    over its pairs (itself included), then clips it into its contacts'
    non-empty interval.  Stops when no pair exceeds its budget by more than
    :data:`_SETTLED_M`, or on a STALL (:data:`_STALL_PASSES` passes without
    :data:`_STALL_GAIN` of progress — a pair set that cannot all hold).
    Returns ``(targets, passes, residual_m, stalled, residual vertex)``."""
    ids = sorted(targets)
    at = {v: i for i, v in enumerate(ids)}
    T = np.asarray([targets[v] for v in ids], dtype=float)
    ia, ib, bb = [], [], []
    for v, ps in own.items():
        i = at.get(v)
        if i is None:
            continue
        for u, b in ps:
            j = at.get(u)
            if j is not None and j != i:
                ia.append(i); ib.append(j); bb.append(float(b))
    I = np.asarray(ia, dtype=np.int64)
    J = np.asarray(ib, dtype=np.int64)
    B = np.asarray(bb, dtype=float)
    lo_c = np.full(len(ids), -np.inf)
    hi_c = np.full(len(ids), np.inf)
    for v, (lo, hi) in bound.items():
        i = at.get(v)
        if i is not None and lo <= hi:
            lo_c[i], hi_c[i] = lo, hi
    passes, worst, stalled, k = 0, 0.0, False, 0
    seen: list[float] = []
    for n in range(_PASSES):
        lo = T.copy()
        hi = T.copy()
        np.maximum.at(lo, I, T[J] - B)
        np.minimum.at(hi, I, T[J] + B)
        ex = np.maximum(np.maximum(lo - T, T - hi), 0.0)
        T = np.minimum(np.maximum(0.5 * (lo + hi), lo_c), hi_c)
        ex = np.maximum(ex, np.maximum(lo_c - T, T - hi_c))
        k = int(np.argmax(ex)) if len(ex) else 0
        worst = float(ex[k]) if len(ex) else 0.0
        passes = n + 1
        if worst <= _SETTLED_M:
            break
        seen.append(worst)
        if (len(seen) > _STALL_PASSES
                and worst > (1.0 - _STALL_GAIN) * seen[-1 - _STALL_PASSES]):
            stalled = True
            break
    return ({v: float(T[i]) for v, i in at.items()}, passes,
            round(worst, 4), stalled, ids[k] if ids and worst > 0 else None)


def held_by_contacts(pm: PlanarMap, law: Law, airport: Airport | None,
                     targets: dict[int, float],
                     contacts: _t.Mapping[int, float],
                     junior: _t.Mapping[int, float] | None = None
                     ) -> tuple[dict[int, float], dict[str, _t.Any]]:
    """HOLD (2), module docstring: ``targets`` projected onto THE NO-STEP
    LAW'S OWN PAIRS — every pair of targets the law prices (the ``k``
    nearest by route inside ``window_m``, ``emit.no_step``) held within its
    route budget, and every SHORT PAIR of a taxi face within its box
    (:func:`_box_pairs`), and every target within the budget of the contacts
    (the runway's values; ``junior``: the apron levels of the second pass,
    which yield to the runway where the two disagree — :func:`_senior_first`)
    inside the same window.

    Each pass moves a target to the MID of the interval its pairs allow
    (``max(T_u - b) .. min(T_u + b)`` over its partners, itself included —
    the core clamp's own construction read over the pairs), then clips it
    into its contacts' interval.  A target whose contacts contradict is not
    clipped, and the pair of contacts is REPORTED as a short connector
    (:func:`_contact_bounds`) — never resolved silently.  A window, never
    the whole network: a contact 3 km away is no pair the law prices
    (HECA: a runway value 52 m higher 3.1 km off set a stub's floor 5 m
    over its own mouth).  Returns the held targets and a report ``{agreed,
    held, contradicted, short_connectors, passes, stalled, residual_m,
    worst_m, worst_ll}``."""
    rep: dict[str, _t.Any] = {"agreed": 0, "held": 0, "contradicted": 0,
                              "short_connectors": [], "passes": 0,
                              "stalled": False, "residual_m": 0.0,
                              "worst_m": 0.0, "worst_ll": None}
    if not targets:
        return targets, rep
    ns = law.tables.emit.no_step
    g = routes(pm, law, airport)
    own = {v: [(u, b) for u, b, _d in ps] for v, ps in
           _pairs(g, targets, float(ns.window_m), int(ns.k), set(targets)).items()}
    box = _box_pairs(pm, law, airport)
    for v, ps in box.items():
        if v in targets:
            own.setdefault(v, []).extend((u, b) for u, b, _d in ps if u in targets)
    bound, short = (_contact_bounds(pm, g, law, targets, contacts, box)
                    if contacts else ({}, []))
    if junior:
        jb, jshort = _contact_bounds(pm, g, law, targets, junior, box)
        bound = _senior_first(bound, jb)
        short = sorted(short + jshort, key=lambda r: -r["excess_m"])
    rep["contradicted"] = sum(1 for lo, hi in bound.values() if lo > hi)
    rep["short_connectors"] = short
    out, rep["passes"], rep["residual_m"], rep["stalled"], rv = _project(
        targets, own, bound)
    if rv is not None:
        rep["residual_ll"] = [pm.vertices[rv].key[0], pm.vertices[rv].key[1]]
    for v, t in out.items():
        moved = abs(t - targets[v])
        if moved <= _MOVED_M:
            continue
        lo, hi = bound.get(v, (t, t))
        rep["held" if lo <= hi and (abs(t - lo) <= _MOVED_M
                                     or abs(t - hi) <= _MOVED_M)
            and v in bound else "agreed"] += 1
        if moved > rep["worst_m"]:
            rep["worst_m"] = round(moved, 3)
            rep["worst_ll"] = [pm.vertices[v].key[0], pm.vertices[v].key[1]]
    return out, rep


def stage_one_contacts(pm: PlanarMap, law: Law,
                       levels: _t.Mapping[int, float]) -> dict[int, float]:
    """THE APRON LEVELS AS CONTACTS (owner RULINGS 2026-10-15i (3), option
    (b)): every vertex of an apron-body face (``law.tables.apron_roles``)
    that STAGE 1 levelled, at that level — the apron's own answer, which a
    pad's frontage hold or the apron's caps may set far from its ground
    (KCLT v2445: 1.35 m under its DEM), so the taxi trend can start its
    descent early enough to meet it within the cap."""
    roles = apron_roles(law)
    return {int(v): float(z) for v, z in levels.items()
            if v in pm.vertices
            and any(pm.faces[f].role in roles
                    for f in pm.vertices[v].incident_faces)}
