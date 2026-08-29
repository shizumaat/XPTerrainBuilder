"""THE FREE-ROAD PROFILE PASS — one-way weld + whole-path ramp.

Spec: ``docs/specs/free-road-profile-pass-spec.md`` (HECA round 5b).  It
closes round 5's un-implemented law 3 on round 5's own interventional
evidence (lane/hecar5, merged 52d54c6e):

* the crossing adoption DOES build the ramp at the owner's item-2 cliff
  (106.70 -> 108.383) and ``groundside._grade_limit_groundside_chords``
  flattens it back (pipeline 6692 and again at 6957).  Its binding pair
  is the ring's OWN RETURN SIDE across the U-loop — 5-25 m EUCLIDEAN
  between points far apart along the PATH.  Raising the ring's cap from
  1 % to 8 % did not help, which is why round 5 shipped the contact-cap
  scoping DEFAULT OFF: re-pricing alone builds no profile;
* the owner's four sites bind differently — item 2 welded (0.000 m),
  item 4 by a mouth seat (0.02 m), item 3 NOT AT ALL: its nearest end-on
  approach is 1.538 m against the derived 1.5 m mouth tolerance.

THE THREE LAWS, and where each lives here:

1. ONE-WAY WELD.  A free road's contact with aircraft pavement is a
   DIRICHLET endpoint: the road takes the pavement's SOLVED value and
   the pavement never reads the road.  Enforced BY CONSTRUCTION, not by
   care — this pass runs post-solve, writes ROAD-FAMILY nodes only, and
   every node a non-road value authority also carries is FROZEN
   (``groundside._road_vertex_graph``'s own freeze, the crossing
   adoption's posture).  Airside cannot move because no airside value is
   ever written.
2. END-ON BINDING within the road's OWN HALF-WIDTH (``2·area/perimeter``
   of the binding shape, halved) — geometric, per road, no new constant,
   which is what admits item 3's 1.538 m gap under a ~6 m road.  Refused
   near-misses are published with their numbers
   (``layout._free_road_binding_refusals``).
3. WHOLE-PATH PROFILE per free-road CHAIN, in the chain's own STATION
   coordinate — ``route_profile.anchors.service_station_map``, THE
   station derivation the in-solve seeder uses, extracted rather than
   re-written (spec: "reuse the route-metric-within-shape machinery,
   never a second derivation").  The station coordinate is what makes
   the U-loop a long path instead of a short chord: two legs of a
   U-turn are far apart in ``s`` however close they lie in the plane.

The profile OWNS the chain's values, and the limiter is told so: the
written nodes are published in the limiter's own 2-dp key space
(``layout._free_road_profile_keys``) and pinned there, which is the
spec's "exempts them" branch.  The exemption costs the cross-section law
nothing: a station writes ONE value to its whole cross-section, so a
profile-owned pair is flat by construction and the 2 % transverse law
has nothing left to price.
"""
from __future__ import annotations

import math

__all__ = [
    "solve_free_road_profiles",
    "profile_owned_keys",
    "PROFILE_KEYS_ATTRIBUTE",
    "chain_profile",
]

#: Where the written nodes are published for the chord limiter, in ITS
#: key space (``(round(x, 2), round(y, 2))`` — ``groundside``'s own).
PROFILE_KEYS_ATTRIBUTE = "_free_road_profile_keys"

#: Two pin values closer than this are one datum; further apart, the
#: disagreement is recorded.  The repo's standing elevation materiality
#: floor (auto_patch/CLAUDE.md convergence guards).
MATERIALITY_M = 0.01


def profile_owned_keys(layout) -> set:
    """The 2-dp keys this pass owns, or an empty set."""
    return set(getattr(layout, PROFILE_KEYS_ATTRIBUTE, None) or ())


def chain_profile(stations_s, values, pins, cap, caps=None):
    """THE PROFILE LAW, geometry-free so a twin can state it directly.

    ``stations_s`` is the chain's station arclengths (ascending),
    ``values`` the current per-station value, ``pins`` a
    ``{index: value}`` of Dirichlet endpoints, ``cap`` the longitudinal
    grade limit, and ``caps`` the OPTIONAL PER-STATION cap vector
    (Amendment 2 clause 1 — READER 3 of the one derivation): station
    ``i`` may not out-grade ``caps[i]``, so a stretch alongside an apron
    ramps at 1 % over its own stations while the free stretch of the same
    chain ramps at 8 %.  ``None`` ⇒ the scalar ``cap`` everywhere,
    byte-identical.  Returns ``(target, infeasible)`` where ``target`` is
    the new per-station value and ``infeasible`` lists
    ``(i, j, needed_grade)`` for pin pairs no ``cap`` profile connects.

    The law is the pins' cap-Lipschitz envelope:

        ceil(s) = min over pins ( z_p + cap·|s − s_p| )
        floor(s) = max over pins ( z_p − cap·|s − s_p| )
        target(s) = clamp( value(s), floor(s), ceil(s) )

    which is exactly "the climb distributes over the whole run at up to
    the cap, and the road returns to its own level where the envelope
    lets it".  Between a pin and the point where the envelope meets the
    road's own level the result is MONOTONE at the cap — the ramp — and
    beyond it the road is untouched.  A pin keeps its own value.
    """
    n = len(stations_s)
    target = list(values)
    infeasible: list = []
    if not pins:
        return target, infeasible
    items = sorted(pins.items())
    def _seg_cap(i, j):
        """The cap governing the run between two stations: the STRICTEST
        station cap on it — a 1 % station anywhere between two pins binds
        the whole span, which is what "the cap lives at the station"
        means for a profile."""
        if not caps:
            return float(cap)
        lo, hi = (i, j) if i <= j else (j, i)
        seg = [c for c in caps[lo:hi + 1] if c is not None]
        return min(seg) if seg else float(cap)

    for a in range(len(items)):
        ia, za = items[a]
        for b in range(a + 1, len(items)):
            ib, zb = items[b]
            ds = abs(stations_s[ib] - stations_s[ia])
            dz = abs(zb - za)
            if dz > _seg_cap(ia, ib) * ds + 1e-9:
                need = dz / ds if ds > 1e-9 else float("inf")
                infeasible.append((ia, ib, need))
    if infeasible:
        return list(values), infeasible
    # ── THE CHORD OF THE BRACKETING PINS (owner acceptance line, the
    # CYXY site 60.7100244,-135.0727863 -> 60.7087015,-135.0746305) ───
    # A chain whose two ends are BOTH bound may not sag between them:
    # measured on the round-5d control, that road welds correctly at
    # 702.44 and 703.11 and drops to 698.93 in the middle — 3.63 m below
    # the chord of its own pinned ends, with nothing in the pins asking
    # for a dip.  The cap envelope alone cannot see it (a sag well inside
    # +-cap*d is "lawful" to a Lipschitz bound), so the law needs the
    # chord: between two DIRECTLY BRACKETING pins the profile is at least
    # their linear interpolation.  It only ever RAISES — a genuine hill
    # between the pins keeps its own height, bounded by ``hi`` as before —
    # so this cannot flatten terrain the road legitimately climbs.
    pin_idx = sorted(pins)

    def _chord(i):
        lo_p = None
        hi_p = None
        for p in pin_idx:
            if p <= i:
                lo_p = p
            if p >= i and hi_p is None:
                hi_p = p
        if lo_p is None or hi_p is None or lo_p == hi_p:
            return None
        s0, s1 = stations_s[lo_p], stations_s[hi_p]
        if abs(s1 - s0) < 1e-9:
            return None
        t = (stations_s[i] - s0) / (s1 - s0)
        return pins[lo_p] + t * (pins[hi_p] - pins[lo_p])

    for i in range(n):
        s = stations_s[i]
        hi = min(z + _seg_cap(i, p) * abs(s - stations_s[p])
                 for p, z in pins.items())
        lo = max(z - _seg_cap(i, p) * abs(s - stations_s[p])
                 for p, z in pins.items())
        ch = _chord(i)
        if ch is not None and ch > lo:
            lo = ch
        if i in pins:
            target[i] = float(pins[i])
            continue
        v = values[i]
        target[i] = float(min(max(v, lo), hi)) if v is not None else None
    return target, infeasible


def _mean_half_width(shape) -> float | None:
    """The shape's own half-width — ``area/perimeter`` (``2·A/P`` halved).

    The SAME width statistic ``apply_service_road_dem_follow``'s run/yard
    scoping uses (``2·area/perimeter`` against ``ROAD_CARVE_MAX_WIDTH_M``)
    — one width convention for roads, not a second one here.
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


def solve_free_road_profiles(layout, icao: str = "") -> dict:
    """Solve the whole-path profile of every free-road chain.  POST-SOLVE.

    Returns a summary dict; ``layout`` gains
    ``_free_road_profile_keys`` (the limiter's exemption set) and
    ``_free_road_binding_refusals`` (the published near-misses).
    """
    out = {"on": False, "chains": 0, "stations": 0, "pinned": 0,
           "bound_end_on": 0, "refused_near_miss": 0, "moved": 0,
           "worst_m": 0.0, "infeasible_chains": 0, "frozen": 0,
           "disagreeing_pins": 0, "station_capped": 0}
    from . import config as _cfg
    if not bool(getattr(_cfg, "FREE_ROAD_PROFILE_PASS", True)):
        return out
    out["on"] = True
    from .config import SERVICE_ROAD_MAX_GRADE as _CAP
    from .groundside import (_road_vertex_graph, _airside_value_at)
    from .elevation_per_surface.route_profile.anchors import (
        service_seed_lines, service_station_map)
    from .config import ROAD_CARVE_MAX_WIDTH_M as _CARVE_W
    import O4_UI_Utils as UI

    idx, xy, adj, frozen, rings = _road_vertex_graph(layout)
    if not xy:
        return out
    out["frozen"] = len(frozen)
    lines = service_seed_lines(layout)
    if not lines:
        UI.vprint(1, f"  [pav-builder] {icao}: free-road PROFILE pass — "
                     f"no service centerline chain to solve along.")
        return out

    # Current values + the shapes each node belongs to (the station map's
    # co-level rehome reads the latter, exactly as the seeder feeds it).
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
            node_shapes.setdefault(i, [])
            if not any(o is s for o in node_shapes[i]):
                node_shapes[i].append(s)
            if a is not None and i not in cur:
                cur[i] = float(a)
    if not cur:
        return out
    node_pos = {i: xy[i] for i in range(len(xy))}
    # THE PER-STATION CAPS, per node, from the shapes' published vector.
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

    # ── LAW 1: the DIRICHLET pins ────────────────────────────────────
    # A frozen node is one a NON-ROAD value authority carries — airside
    # welds first of all.  Its value is READ and never written: that is
    # the one-way weld, by construction rather than by care.
    pins_node: dict = {i: cur[i] for i in frozen if i in cur}

    # ── LAW 2: END-ON BINDING within the road's own half-width ───────
    refusals: list = []
    for i in range(len(xy)):
        if i in pins_node or i not in cur:
            continue
        shapes_here = node_shapes.get(i) or []
        if not shapes_here:
            continue
        hw = max((w for w in (_mean_half_width(s) for s in shapes_here)
                  if w is not None), default=None)
        if hw is None or hw <= 0.0:
            continue
        # The road's own half-width, bounded by the widest thing the
        # road carve itself treats as a road — a service YARD's mean
        # width is not a binding reach.
        hw = min(float(hw), float(_CARVE_W) / 2.0)
        z, gap = _airside_value_at(xy[i], layout, reach=hw, with_gap=True)
        if z is None:
            continue
        if gap is not None and gap > hw + 1e-9:            # pragma: no cover
            refusals.append({"xy": xy[i], "gap_m": round(float(gap), 4),
                             "half_width_m": round(hw, 4)})
            continue
        pins_node[i] = float(z)
        out["bound_end_on"] += 1
    # Refused near-misses: an airside ring that is close but OUTSIDE the
    # road's own half-width.  Published, never silently dropped.
    for i in range(len(xy)):
        if i in pins_node or i not in cur:
            continue
        shapes_here = node_shapes.get(i) or []
        hw = max((w for w in (_mean_half_width(s) for s in shapes_here)
                  if w is not None), default=None)
        if hw is None:
            continue
        hw = min(float(hw), float(_CARVE_W) / 2.0)
        z, gap = _airside_value_at(xy[i], layout, reach=hw * 3.0,
                                   with_gap=True)
        if z is None or gap is None or gap <= hw:
            continue
        refusals.append({"xy": xy[i], "gap_m": round(float(gap), 4),
                         "half_width_m": round(hw, 4),
                         "value_m": round(float(z), 3)})
    out["refused_near_miss"] = len(refusals)
    out["pinned"] = len(pins_node)
    layout._free_road_binding_refusals = refusals
    if not pins_node:
        return out

    # ── LAW 3: the whole-path profile, in the STATION coordinate ─────
    R = float(_CARVE_W) / 2.0 + 2.0
    stations, node_station = service_station_map(
        lines, set(cur.keys()), node_pos, node_shapes, pins_node, R)
    if not stations:
        return out
    out["stations"] = len(stations)

    by_line: dict = {}
    for sid, st in enumerate(stations):
        by_line.setdefault(st["line"], []).append(sid)

    new: dict = {}
    for li, sids in by_line.items():
        sids.sort(key=lambda k: stations[k]["s"])
        ss = [stations[k]["s"] for k in sids]
        vals: list = []
        pins: dict = {}
        for pos, sid in enumerate(sids):
            members = [m for m in stations[sid]["members"] if m in cur]
            if not members:
                vals.append(None)
                continue
            vals.append(sum(cur[m] for m in members) / len(members))
            pin_vals = [pins_node[m] for m in members if m in pins_node]
            if pin_vals:
                if max(pin_vals) - min(pin_vals) > MATERIALITY_M:
                    out["disagreeing_pins"] += 1
                pins[pos] = sum(pin_vals) / len(pin_vals)
        if not pins:
            continue
        out["chains"] += 1
        # Amendment 2 clause 1 — the PER-STATION caps of this chain, read
        # from the shapes' published vector (ONE derivation, this being
        # its third reader).  A station governed by an apron carries the
        # apron's cap; the free stations carry SERVICE_ROAD_MAX_GRADE.
        st_caps: list = []
        for sid in sids:
            members = [m for m in stations[sid]["members"]]
            cs = [node_cap.get(m) for m in members]
            cs = [c for c in cs if c is not None]
            st_caps.append(min(cs) if cs else None)
        if any(c is not None and c < float(_CAP) for c in st_caps):
            out["station_capped"] += 1
        target, infeasible = chain_profile(ss, vals, pins, float(_CAP),
                                           caps=st_caps)
        if infeasible:
            out["infeasible_chains"] += 1
            worst = max(infeasible, key=lambda t: t[2])
            UI.vprint(1,
                f"  [pav-builder] {icao}: free-road profile REFUSED on "
                f"chain {li}: its pinned ends need "
                f"{100.0 * worst[2]:.1f} % against the "
                f"{100.0 * float(_CAP):.0f} % road class over "
                f"{abs(ss[worst[1]] - ss[worst[0]]):.1f} m "
                f"({len(infeasible)} such pair(s)) — the shortfall is "
                f"REPORTED, the chain is left as the solve made it.")
            continue
        for pos, sid in enumerate(sids):
            t = target[pos]
            if t is None:
                continue
            for m in stations[sid]["members"]:
                if m in frozen or m not in cur:
                    continue        # LAW 1: never write a pinned datum
                new[m] = float(t)

    if not new:
        return out

    # ── WRITE BACK, values only, road-family rings only ──────────────
    keys: set = set()
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
            nv = new.get(i)
            if nv is None or body[t] is None:
                continue
            d = abs(float(nv) - float(body[t]))
            (x, y) = xy[i]
            keys.add((round(x, 2), round(y, 2)))
            if d <= 1e-9:
                continue
            out["worst_m"] = max(out["worst_m"], d)
            body[t] = float(nv)
            out["moved"] += 1
            touched = True
        if touched:
            s.node_altitudes = (body + [body[0]]) if closed else body
    setattr(layout, PROFILE_KEYS_ATTRIBUTE,
            profile_owned_keys(layout) | keys)
    UI.vprint(1,
        f"  [pav-builder] {icao}: FREE-ROAD PROFILE (round 5b) — "
        f"{out['chains']} chain(s) over {out['stations']} station(s) "
        f"solved between {out['pinned']} pinned end(s) "
        f"({out['bound_end_on']} bound END-ON inside the road's own "
        f"half-width, {out['refused_near_miss']} near-miss(es) refused "
        f"and published); {out['moved']} road vertex/vertices re-levelled "
        f"at up to {100.0 * float(_CAP):.0f} % along the PATH (worst "
        f"{out['worst_m']:.3f} m); {out['infeasible_chains']} chain(s) "
        f"REFUSED as infeasible; {out['frozen']} vertex/vertices FROZEN "
        f"because a non-road authority carries them — airside is king, "
        f"by construction, and {len(keys)} key(s) are published to the "
        f"chord limiter as profile-owned.")
    return out
