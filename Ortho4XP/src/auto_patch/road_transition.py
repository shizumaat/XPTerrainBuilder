"""THE ROAD TRANSITION PROFILER — the contact model, and only it.

Spec: ``docs/specs/linear-transport-redesign-spec.md`` §3 (RULINGS
2026-08-31b "LEVERAGE THE CORE"; consumer census §1 rows 5/8/9/13/14/61).

ONE LAW EVERYWHERE (§1): a road FOLLOWS TERRAIN, and where terrain
out-grades its cap it LIFTS or CUTS the minimum needed to hold the cap.
Pins exist ONLY where the road meets airside pavement (29c, contact IS
value).  The core owns the general road course; auto_patch owns the
TRANSITION — the short stretch between the airside contact and the point
where the road is the core's again.

WHAT THIS MODULE IS, AND WHAT IT REPLACES.  ``free_road_profile``
retires with the chord/self-pin model that made every free road a
straight line between its end values (86 % of HECA's stations chorded;
POSTMORTEM-20260831 Task A).  Its KEPT parts move here unchanged in
substance:

* LAW 1, the FREEZE-WELD (census #8): a road vertex a NON-ROAD value
  authority also carries is a Dirichlet datum — read, never written.
  Airside cannot move because no airside value is ever written.  The
  freeze set is ``groundside._road_vertex_graph``'s own (census #13).
* LAW 2, END-ON BINDING (census #9): a road vertex whose own half-width
  reaches settled airside pavement binds to that surface's value
  (``groundside._airside_value_at``, census #14) — geometric, per road,
  no new constant.
* THE ENVELOPE CLAMP (census #5), which is the ONE piece the retirement
  keeps as the algorithm — and it is now literally ONE FUNCTION with the
  core: ``O4_Vector_Utils.cap_lipschitz_profile`` is what the core's
  ``include_roads`` clamp runs on every general road, and it is what
  computes this transition's BASE profile here.  The outer end of a
  transition therefore takes the value the core's own law gives it, so
  THE HANDOFF WELDS BY CONSTRUCTION rather than by a tolerance.

THE SCOPE is ``config.SERVICE_ROAD_PAVEMENT_NEAR_M`` (25 m) of road
graph OUTWARD from a contact pin — the same 25 m the mint uses to decide
what road ground is airport ground at all, so the profiler's domain and
the patch's road population are one region stated once.

THE FRAME, stated because it is not the core's: the DEM sampled here is
auto_patch's airport-SMOOTHED tile DEM, while the core clamps the
lane-width-shifted tile DEM.  The two agree to smoothing, not to the
bit; what welds by construction is the LAW (one clamp function, one cap,
one station convention), and the pin envelope holds the contact exactly
in either frame.
"""
from __future__ import annotations

import math

__all__ = [
    "solve_road_transitions",
    "transition_profile",
    "cap_distance_prefix",
    "TRANSITION_SCOPE_M",
]

#: The repo's standing elevation materiality floor (auto_patch/CLAUDE.md
#: convergence guards) — two values closer than this are one datum.
MATERIALITY_M = 0.01


def TRANSITION_SCOPE_M() -> float:
    """How far outward from a contact a transition runs, in metres.

    ``config.SERVICE_ROAD_PAVEMENT_NEAR_M`` — the SAME constant the mint
    uses to keep a road at all (``pipeline`` keep-region, spec §3.3), so
    the transition's domain cannot drift from the population it governs.
    Read at call time so a twin can state the coupling.
    """
    from .config import SERVICE_ROAD_PAVEMENT_NEAR_M
    return float(SERVICE_ROAD_PAVEMENT_NEAR_M)


def cap_distance_prefix(stations_s, caps, cap):
    """``C`` — the prefix CAP-DISTANCE of a chain, in metres of altitude.

    ``C[k] − C[i]`` is the greatest ``|Δz|`` a profile may accumulate
    between stations ``i`` and ``k``: each INTERVAL contributes its own
    cap times its own length, and the interval between two stations
    carries the STRICTER of their two caps.  A 1 % station (a road in
    apron contact — RULINGS 25b/25h) therefore bounds the grade THROUGH
    ITS OWN NEIGHBOURHOOD and nothing beyond it.

    A Lipschitz bound whose constant VARIES in space INTEGRATES; it does
    not take a minimum.  ``min(cap over the span) · span`` made one 1 %
    station price a whole run at 1 % and refused five of seven feasible
    CYXY chains outright — the measurement that produced this function
    (lane/rampsites).  With one cap everywhere this is that cap times the
    span, which is why the scalar path never enters here.

    Ported from the retired ``free_road_profile`` (census #6): the
    per-station cap vector's third reader moves with the law that reads
    it, so ``lateral_contiguity``'s ONE derivation still has exactly
    three readers.
    """
    C = [0.0]
    for m in range(len(stations_s) - 1):
        pair = [c for c in (caps[m], caps[m + 1]) if c is not None]
        cm = min(pair) if pair else float(cap)
        C.append(C[-1] + float(cm)
                 * (float(stations_s[m + 1]) - float(stations_s[m])))
    return C


def transition_profile(stations_s, base, pins, cap, caps=None):
    """THE TRANSITION LAW, geometry-free so a twin can state it directly.

    ``stations_s`` are the chain's arclengths from the contact outward,
    ``base`` the value the road would take with no contact at all (the
    core's own clamp — see :func:`solve_road_transitions`), ``pins`` a
    ``{index: value}`` of airside contacts, ``cap`` the road's grade cap
    and ``caps`` the OPTIONAL per-station cap vector.  Returns
    ``(target, over_cap)``.

    THE LAW is the pins' cap-Lipschitz ENVELOPE, and NOTHING ELSE:

        ceil(s)  = min over pins ( z_p + allow(s, p) )
        floor(s) = max over pins ( z_p − allow(s, p) )
        target(s) = clamp( base(s), floor(s), ceil(s) )

    A pin keeps its own value EXACTLY (contact is value, RULINGS 29c).
    Away from the pins the road returns to ``base`` as fast as the cap
    lets it and then simply IS ``base`` — which is the core's answer, so
    the transition ends welded to the road the core levels.

    WHAT IS NOT HERE, deliberately: the CHORD (a bracketed station taking
    the pin-to-pin interpolation exactly, discarding terrain) and the
    SELF-PINS (every ≥2-station chain pinned at its own ends).  Together
    they made 86 % of HECA's road stations a straight line between end
    values and turned an 8 %-lawful hill into a dead-flat cutting — the
    2026-08-30 regression, root-caused in POSTMORTEM-20260831 Task A and
    retired by RULINGS 2026-08-31b.  Deleted, not gated (29f).

    ``over_cap`` reports pin pairs no cap-lawful profile connects.  It is
    a REPORT, never a revert: both contacts are met exactly (29c is the
    senior law) and the excess grade stands for the census to price.
    """
    n = len(stations_s)
    target = [None if v is None else float(v) for v in base]
    over_cap: list = []
    if not pins:
        return target, over_cap
    _C = (cap_distance_prefix(stations_s, caps, cap)
          if caps and any(c is not None for c in caps) else None)

    def _allow(i, j):
        """The lawful ``|Δz|`` between two stations — THE one allowance
        both the feasibility report and the envelope ask for, so the two
        can never read different laws."""
        if _C is not None:
            return abs(_C[j] - _C[i])
        return float(cap) * abs(float(stations_s[j])
                                - float(stations_s[i]))

    items = sorted(pins.items())
    for a in range(len(items)):
        ia, za = items[a]
        for b in range(a + 1, len(items)):
            ib, zb = items[b]
            dz = abs(zb - za)
            if dz > _allow(ia, ib) + 1e-9:
                ds = abs(stations_s[ib] - stations_s[ia])
                over_cap.append((ia, ib,
                                 dz / ds if ds > 1e-9 else float("inf")))

    for i in range(n):
        if i in pins:
            target[i] = float(pins[i])          # contact IS value
            continue
        v = target[i]
        if v is None:
            continue
        hi = min(z + _allow(i, p) for p, z in pins.items())
        lo = max(z - _allow(i, p) for p, z in pins.items())
        if lo > hi:                 # an over-cap pin pair (reported above)
            lo = hi = 0.5 * (lo + hi)
        target[i] = float(min(max(float(v), lo), hi))
    return target, over_cap


def _mean_half_width(shape) -> float | None:
    """The shape's own half-width — ``area/perimeter`` (``2·A/P`` halved).

    The SAME width statistic ``apply_service_road_dem_follow``'s run/yard
    scoping uses, so there is one width convention for roads.
    """
    poly = getattr(shape, "polygon", None)
    if poly is None or getattr(poly, "is_empty", True):
        return None
    try:
        per = float(poly.length)
        if per <= 0.0:
            return None
        return float(poly.area) / per
    except Exception:                                      # pragma: no cover
        return None


def _chains_from(pins, adj, scope_m):
    """The transition chains: pin → outward, at most ``scope_m`` of road.

    A multi-source Dijkstra over the road vertex graph gives every vertex
    its NEAREST contact and the path back to it; the maximal paths of
    that tree (root → leaf) are the chains.  Each chain is
    ``(root, [vertex indices from the root outward], [distance each])``.

    Nearest-contact ownership is the tie-break by construction: a vertex
    reached from two contacts belongs to the closer one, which is the
    same "strictest claimant by value at the contact" posture 29c states.
    """
    import heapq

    dist: dict = {i: 0.0 for i in pins}
    prev: dict = {}
    root: dict = {i: i for i in pins}
    heap = [(0.0, i) for i in pins]
    heapq.heapify(heap)
    seen: set = set()
    while heap:
        d, i = heapq.heappop(heap)
        if i in seen:
            continue
        seen.add(i)
        for (j, w) in adj.get(i, ()):
            if j in seen:
                continue
            nd = d + float(w)
            if nd > scope_m + 1e-9:
                continue
            if nd < dist.get(j, float("inf")) - 1e-12:
                dist[j] = nd
                prev[j] = i
                root[j] = root[i]
                heapq.heappush(heap, (nd, j))
    if not dist:
        return [], dist
    interior = {prev[j] for j in prev}
    chains = []
    for leaf in sorted(dist):
        if leaf in interior or leaf in pins:
            continue                    # only the tips end a chain
        path = [leaf]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        path.reverse()
        stations = [dist[i] for i in path]
        # A TRANSITION BETWEEN TWO CONTACTS IS BOUND BY BOTH.  The tree
        # roots every vertex at its NEAREST contact, so a road running
        # from one apron to another ends its path one edge short of the
        # far contact — that contact is a Dirichlet datum for this chain
        # and is carried onto it, or the far half of a crossing road
        # would profile against one end only.
        far = None
        for (j, w) in adj.get(path[-1], ()):
            if j in pins and (len(path) < 2 or j != path[-2]):
                if far is None or w < far[1]:
                    far = (j, float(w))
        if far is not None:
            path.append(far[0])
            stations.append(stations[-1] + far[1])
        chains.append((path[0], path, stations))
    return chains, dist


def solve_road_transitions(layout, icao: str = "", dem=None,
                           tile_lat: int = 0, tile_lon: int = 0) -> dict:
    """Profile every AIRSIDE-CONTACT TRANSITION of the road family.

    Runs at the airside-final moment (the solver's final writeback seam —
    spec §3.5, the census-named natural home of the pinned-transition
    law), so the contact values it reads are the ones that emit.

    Writes ROAD-FAMILY vertices only, and never a frozen one: airside is
    king BY CONSTRUCTION, not by care.  Returns a summary dict and
    publishes it as ``layout._road_transition_report``.
    """
    out = {"on": True, "chains": 0, "pins": 0, "bound_end_on": 0,
           "frozen": 0, "in_scope": 0, "moved": 0, "worst_m": 0.0,
           "over_cap_pairs": 0, "worst_over_cap_pct": 0.0,
           "dem_stations": 0, "scope_m": TRANSITION_SCOPE_M()}
    from .config import (SERVICE_ROAD_MAX_GRADE as _CAP,
                         ROAD_CARVE_MAX_WIDTH_M as _CARVE_W)
    from .groundside import _road_vertex_graph, _airside_value_at
    from O4_Vector_Utils import cap_lipschitz_profile
    import O4_UI_Utils as UI

    idx, xy, adj, frozen, rings = _road_vertex_graph(layout)
    if not xy:
        out["on"] = False
        return out
    out["frozen"] = len(frozen)

    cur: dict = {}
    node_shapes: dict = {}
    for (s, ids) in rings:
        alts = list(getattr(s, "node_altitudes", None) or [])
        if not alts:
            continue
        body = alts[:-1] if len(alts) == len(ids) + 1 else alts
        if len(body) != len(ids):
            continue
        for i, a in zip(ids, body):
            lst = node_shapes.setdefault(i, [])
            if not any(o is s for o in lst):
                lst.append(s)
            if a is not None and i not in cur:
                cur[i] = float(a)
    if not cur:
        out["on"] = False
        return out

    # ── THE PER-STATION CAPS (census #100, the vector's third reader) ──
    from .lateral_contiguity import cap_at as _cap_at
    node_cap: dict = {}
    for (s_shape, ids) in rings:
        vec = list(getattr(s_shape, "station_cap_vector", None) or ())
        if not vec:
            continue
        for i in ids:
            c = _cap_at(vec, xy[i][0], xy[i][1], None)
            if c is None:
                continue
            prev = node_cap.get(i)
            node_cap[i] = float(c) if prev is None else min(prev, float(c))

    # ── LAW 1: THE FREEZE-WELD ────────────────────────────────────────
    pins: dict = {i: cur[i] for i in frozen if i in cur}
    # ── LAW 2: END-ON BINDING within the road's OWN half-width ────────
    for i in range(len(xy)):
        if i in pins or i not in cur:
            continue
        hw = max((w for w in (_mean_half_width(s)
                              for s in (node_shapes.get(i) or ()))
                  if w is not None), default=None)
        if hw is None or hw <= 0.0:
            continue
        hw = min(float(hw), float(_CARVE_W) / 2.0)
        z, gap = _airside_value_at(xy[i], layout, reach=hw, with_gap=True)
        if z is None or (gap is not None and gap > hw + 1e-9):
            continue
        pins[i] = float(z)
        out["bound_end_on"] += 1
    out["pins"] = len(pins)
    if not pins:
        UI.vprint(1, f"  [pav-builder] {icao}: road TRANSITION profiler — "
                     f"no airside contact on the road family; every road "
                     f"shape here is the core's.")
        setattr(layout, "_road_transition_report", out)
        return out

    chains, dist = _chains_from(pins, adj, out["scope_m"])
    out["in_scope"] = len(dist)

    # ── THE TERRAIN UNDER THE TRANSITION ──────────────────────────────
    # The base profile is the road with NO contact: terrain, clamped by
    # the core's own function.  Where no DEM answers, the vertex's
    # current solved value stands in — the pass never invents ground.
    ground: dict = {}
    if dem is not None:
        from .elevation import _sample_dem
        for i in dist:
            try:
                lat, lon = layout.m_to_ll(xy[i][0], xy[i][1])
                e = _sample_dem(dem, tile_lat, tile_lon, lat, lon)
            except Exception:                              # pragma: no cover
                e = None
            if e is not None:
                ground[i] = float(e)
    out["dem_stations"] = len(ground)

    # ── THE CHAINS ────────────────────────────────────────────────────
    best: dict = {}          # vertex -> (distance from its contact, value)
    # THE CONTACT IS THE LAW WHETHER OR NOT A CHAIN RUNS FROM IT (29c).
    # A stub whose every vertex is a contact has no interior to profile
    # and still owes the airside value at its own vertices — the END-ON
    # bound ones especially, which are the road taking the value across
    # the gap.  Distance 0, so no chain can outrank a contact.
    for i, z in pins.items():
        if i not in frozen:
            best[i] = (0.0, float(z))
    for (rt, path, dists) in chains:
        vals = [ground.get(i, cur.get(i)) for i in path]
        if any(v is None for v in vals):
            vals = [cur.get(i) if ground.get(i) is None else ground[i]
                    for i in path]
        if any(v is None for v in vals):
            continue
        # THE SHARED CLAMP — the core's own function, on this chain's
        # stations.  Its value at the OUTER END is what the core would
        # give the road there, which is why the handoff welds.
        base = list(cap_lipschitz_profile(dists, vals, float(_CAP)))
        chain_pins = {k: pins[i] for k, i in enumerate(path) if i in pins}
        st_caps = [node_cap.get(i) for i in path]
        target, over = transition_profile(dists, base, chain_pins,
                                          float(_CAP), caps=st_caps)
        out["chains"] += 1
        if over:
            out["over_cap_pairs"] += len(over)
            finite = [g for (_a, _b, g) in over if math.isfinite(g)]
            if finite:
                out["worst_over_cap_pct"] = max(out["worst_over_cap_pct"],
                                                100.0 * max(finite))
        for k, i in enumerate(path):
            # NEVER a frozen vertex (LAW 1 — a non-road authority carries
            # it and reads it).  An END-ON BOUND vertex is NOT frozen: it
            # is the road's own vertex taking the airside value across the
            # gap, which is what LAW 2 exists to do, so it IS written.
            if i in frozen or target[k] is None:
                continue
            prev = best.get(i)
            if prev is None or dists[k] < prev[0]:
                best[i] = (dists[k], float(target[k]))

    if not best:
        setattr(layout, "_road_transition_report", out)
        return out

    # ── WRITE BACK, values only, road-family rings only ───────────────
    for (s, ids) in rings:
        alts = list(getattr(s, "node_altitudes", None) or [])
        if not alts:
            continue
        closed = (len(alts) == len(ids) + 1)
        body = alts[:-1] if closed else alts
        if len(body) != len(ids):
            continue
        touched = False
        for t, i in enumerate(ids):
            rec = best.get(i)
            if rec is None or body[t] is None:
                continue
            d = abs(rec[1] - float(body[t]))
            if d <= 1e-9:
                continue
            out["worst_m"] = max(out["worst_m"], d)
            body[t] = rec[1]
            out["moved"] += 1
            touched = True
        if touched:
            s.node_altitudes = (body + [body[0]]) if closed else body

    UI.vprint(1,
        f"  [pav-builder] {icao}: ROAD TRANSITIONS (spec §3.2) — "
        f"{out['chains']} chain(s) run outward from {out['pins']} airside "
        f"contact pin(s) ({out['bound_end_on']} bound END-ON inside the "
        f"road's own half-width, {out['frozen']} vertex/vertices FROZEN "
        f"because a non-road authority carries them); "
        f"{out['in_scope']} road vertex/vertices lie inside the "
        f"{out['scope_m']:.0f} m transition scope and {out['moved']} were "
        f"re-levelled (worst {out['worst_m']:.3f} m) onto the SHARED core "
        f"clamp's profile ({out['dem_stations']} station(s) on terrain); "
        f"{out['over_cap_pairs']} contact pair(s) demand more than the "
        f"{100.0 * float(_CAP):.0f} % cap (worst "
        f"{out['worst_over_cap_pct']:.1f} %) and BUILD to their contacts "
        f"— contact is value (RULINGS 29c), the excess is a census row.")
    setattr(layout, "_road_transition_report", out)
    return out
