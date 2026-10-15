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

from .routes import route_neighbours, routes
from ..geom.core_clamp import core_vector_utils
from ..law import Law
from ..model.airport import Airport
from ..model.planar import PlanarMap

if _t.TYPE_CHECKING:                                    # pragma: no cover
    from .taxi_trend import _Chain

__all__ = ["capped_chain", "held_by_contacts"]

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
#: early once no pair exceeds its budget by more than :data:`_SETTLED_M`
_PASSES = 200
_SETTLED_M = 1e-3


def _pairs(g, sources, window_m: float, k: int, targets) -> dict[int, list]:
    """vertex -> ``[(other, budget), ...]`` over the route pairs
    (``routes.route_neighbours``: the ``k`` nearest by route distance
    inside ``window_m``, each with the path's ``Σ cap·len``)."""
    out: dict[int, list] = {}
    for a, b, _d, bud in route_neighbours(g, sources, window_m, k,
                                          targets=targets):
        out.setdefault(a, []).append((b, bud))
        out.setdefault(b, []).append((a, bud))
    return out


def held_by_contacts(pm: PlanarMap, law: Law, airport: Airport | None,
                     targets: dict[int, float],
                     contacts: _t.Mapping[int, float]
                     ) -> tuple[dict[int, float], dict[str, _t.Any]]:
    """HOLD (2), module docstring: ``targets`` projected onto THE NO-STEP
    LAW'S OWN PAIRS — every pair of targets the law prices (the ``k``
    nearest by route inside ``window_m``, ``emit.no_step``) held within its
    route budget, and every target within the budget of the runway
    contacts inside the same window.

    Each pass moves a target to the MID of the interval its pairs allow
    (``max(T_u - b) .. min(T_u + b)`` over its partners, itself included —
    the core clamp's own construction read over the pairs), then clips it
    into its contacts' interval; a vertex whose contacts contradict is not
    clipped (that is the runway's law to settle, not a target's).  A
    window, never the whole network: a contact 3 km away is no pair the
    law prices (HECA: a runway value 52 m higher 3.1 km off set a stub's
    floor 5 m over its own mouth).  Returns the held targets and a report
    ``{agreed, held, contradicted, passes, residual_m, worst_m,
    worst_ll}``."""
    rep: dict[str, _t.Any] = {"agreed": 0, "held": 0, "contradicted": 0,
                              "passes": 0, "residual_m": 0.0,
                              "worst_m": 0.0, "worst_ll": None}
    if not targets:
        return targets, rep
    ns = law.tables.emit.no_step
    g = routes(pm, law, airport)
    own = _pairs(g, targets, float(ns.window_m), int(ns.k), set(targets))
    bound: dict[int, tuple[float, float]] = {}
    if contacts:
        tset = set(targets)
        for v, ps in _pairs(g, contacts, float(ns.window_m), 4 * int(ns.k),
                            tset | set(contacts)).items():
            if v not in tset:
                continue
            got = [(contacts[u], b) for u, b in ps if u in contacts]
            if got:
                bound[v] = (max(z - b for z, b in got),
                            min(z + b for z, b in got))
    rep["contradicted"] = sum(1 for lo, hi in bound.values() if lo > hi)
    out = dict(targets)
    order = sorted(set(own) | set(bound))
    for n in range(_PASSES):
        worst = 0.0
        for v in order:                  # in place (Gauss-Seidel), fixed order
            t = out[v]
            ps = own.get(v, ())
            lo = max([out[u] - b for u, b in ps] + [t])
            hi = min([out[u] + b for u, b in ps] + [t])
            worst = max(worst, lo - t, t - hi)
            t = 0.5 * (lo + hi)
            cb = bound.get(v)
            if cb is not None and cb[0] <= cb[1]:
                worst = max(worst, cb[0] - t, t - cb[1])
                t = min(max(t, cb[0]), cb[1])
            out[v] = t
        rep["passes"] = n + 1
        rep["residual_m"] = round(worst, 4)
        if worst <= _SETTLED_M:
            break
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
