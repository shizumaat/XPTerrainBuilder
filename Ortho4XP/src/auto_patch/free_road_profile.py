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

The profile OWNS the chain's values, and the written nodes are published
in the limiter's own 2-dp key space (``layout._free_road_profile_keys``).

Those keys ARE the exemption, and since ruling 3 (coordinator
2026-08-29) they finally have their reader: ``groundside._grade_limit_
groundside_chords`` pins every profile-owned node, because ``who_wrote``
caught that limiter overwriting the owner's item-4 ramp twice — once
after the pre-solve (pipeline 6733) and once after the re-solve
(pipeline 6998) — while the apron weld beside it held.  The exemption
had been retired on the METRIC COLLISION (Amendment 1) and that
collision is gone: the path metric prices road pairs along the road's
own ring walk in both readers.  Gate:
``O4_ROAD_PROFILE_OWNS_ITS_STATIONS``.
"""
from __future__ import annotations

import math

__all__ = [
    "solve_free_road_profiles",
    "profile_owned_keys",
    "PROFILE_KEYS_ATTRIBUTE",
    "chain_profile",
    "cap_distance_prefix",
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


def _cumulative_cap_on() -> bool:
    """Is the CUMULATIVE cap-distance armed?  **Default ON, RATIFIED**
    (coordinator ruling 4, 2026-08-29).  OFF is byte-identical to the
    refuted min-over-span arm — proven at CYXY by a ``solve_cut``
    replay: OFF body 1ff1faab4b86 == the control build's.

    Read at CALL time, like every other gate in this family, so a twin
    can flip it without reloading the module.
    """
    from . import config as _cfg
    return bool(getattr(_cfg, "ROAD_PROFILE_CUMULATIVE_CAP", True))


def _weld_outranks_cap() -> bool:
    """RULING 1 (coordinator, 2026-08-29) — **THE WELD OUTRANKS THE CAP**.

    *"Refusal is per-SPAN, never whole-chain (every feasible span
    builds).  For an infeasible pin pair the chain BUILDS the geometric
    grade between the welds — contact-is-value (RULINGS 29c) is the
    senior law, so both welds are met exactly and the over-cap span is
    PRICED as a census row … but never converted into a step or a
    revert.  No tolerance constant is invented; the row is the record."*

    Default ON.  OFF restores the whole-chain revert byte-identically —
    the refutation ledger for the arm that left HECA's chain 13 (both
    owner sites 2 and 3) exactly as the solve made it, cliff included,
    over ONE pin pair needing 8.62 % against the 8 % class.
    """
    from . import config as _cfg
    return bool(getattr(_cfg, "ROAD_PROFILE_WELD_OUTRANKS_CAP", True))


def _chord_two_sided() -> bool:
    """RULING 2 (coordinator, 2026-08-29) — **THE ROAD CHORD BINDS BOTH
    WAYS**.

    *"Raise-only was Amendment 3's terrain-protection rationale; a road
    profile between welds is OUR OWN construction, not terrain.  On road
    chains, interior NON-WELD stations conform to the chord in BOTH
    directions; only weld/authored/crossing-pinned stations hold."*

    THE DISCRIMINATOR, stated explicitly as the ruling requires: this
    pass solves only ROAD-FAMILY chains — ``groundside._road_vertex_graph``
    over ``grade_law.LATERAL_CONTIGUITY_ROAD_ROLES``, stationed along
    ``anchors.service_seed_lines``' service centerlines.  Between two
    pins such a chain's interior is PAVEMENT THIS PASS CONSTRUCTS, so
    there is no hill to protect: a bump there is the solve's residual,
    not ground.  Amendment 3 §2's RAISE-ONLY chord stands unchanged for
    any chain class whose interior is genuine ground; no such class
    reaches this pass today, and this gate is the switch if one ever
    does.  Default ON; OFF restores raise-only byte-identically.
    """
    from . import config as _cfg
    return bool(getattr(_cfg, "ROAD_PROFILE_CHORD_TWO_SIDED", True))


def cap_distance_prefix(stations_s, caps, cap):
    """``C`` — the prefix CAP-DISTANCE of a chain, in metres of altitude.

    ``C[k] − C[i]`` is the greatest ``|Δz|`` a profile may accumulate
    between stations ``i`` and ``k``: each INTERVAL contributes its own
    cap times its own length.  The interval between two stations carries
    the STRICTER of their two caps, so a 1 % station bounds the grade
    THROUGH ITS OWN NEIGHBOURHOOD — and nothing beyond it.

    WHY THIS AND NOT ``min(cap over the span) · span`` (the arm this
    replaces, measured on lane/rampsites' CYXY control): a Lipschitz
    bound whose constant VARIES in space integrates; it does not take a
    minimum.  Taking the minimum makes one 1 % station 200 m away price
    the entire run at 1 %, and every chain whose ends differ by more
    than 1 % of their separation is then declared infeasible and left
    exactly as the solve made it — cliff included.  MEASURED at CYXY:
    all seven refused chains needed 1.3-4.3 % over their own spans
    against cumulative allowances of 2.4-19.2 m; five of the seven are
    feasible by metres and were refused by the metric alone.

    With one cap everywhere this is that cap times the span, which is
    why the scalar path (``caps`` empty) never enters here.
    """
    C = [0.0]
    for m in range(len(stations_s) - 1):
        pair = [c for c in (caps[m], caps[m + 1]) if c is not None]
        cm = min(pair) if pair else float(cap)
        C.append(C[-1] + float(cm)
                 * (float(stations_s[m + 1]) - float(stations_s[m])))
    return C


def chain_profile(stations_s, values, pins, cap, caps=None,
                  cumulative=None, weld_outranks=None, two_sided=None):
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

    ── AND THE TWO RULINGS THAT MADE IT BUILD (coordinator 2026-08-29) ──

    RULING 1, ``weld_outranks`` (default ON): **the weld outranks the
    cap.**  An ``infeasible`` entry is a REPORT, never a revert — every
    span builds, and the span whose two welds no lawful profile connects
    builds the CHORD between them anyway.  Both welds are met exactly
    (contact-is-value, RULINGS 29c, is the senior law) and the excess
    grade is left standing for the census to price as one honest row
    spread along the span, instead of being concentrated into a step or
    thrown away with the other 40 lawful stations of the chain.

    RULING 2, ``two_sided`` (default ON): **the road chord binds both
    ways.**  A station BRACKETED by two pins takes the chord exactly —
    the raise-only clause of Amendment 3 §2 protected terrain, and a
    road profile between welds is this pass's own construction.  Only
    pins hold their own values; an UNBRACKETED station (beyond the first
    or last pin) still keeps its own level under the cap envelope, which
    is where the road genuinely returns to the ground.
    """
    n = len(stations_s)
    target = list(values)
    infeasible: list = []
    if not pins:
        return target, infeasible
    items = sorted(pins.items())
    _cum = _cumulative_cap_on() if cumulative is None else bool(cumulative)
    _weld = (_weld_outranks_cap() if weld_outranks is None
             else bool(weld_outranks))
    _both = _chord_two_sided() if two_sided is None else bool(two_sided)
    _C = (cap_distance_prefix(stations_s, caps, cap)
          if (caps and _cum) else None)

    def _seg_cap(i, j):
        """The cap governing the run between two stations: the STRICTEST
        station cap on it.

        THE REFUTED READING, kept only behind
        ``O4_ROAD_PROFILE_CUMULATIVE_CAP=0`` — see
        :func:`cap_distance_prefix` for what it cost and why a varying
        Lipschitz constant integrates instead."""
        if not caps:
            return float(cap)
        lo, hi = (i, j) if i <= j else (j, i)
        seg = [c for c in caps[lo:hi + 1] if c is not None]
        return min(seg) if seg else float(cap)

    def _allow(i, j):
        """The lawful ``|Δz|`` between two stations — THE one allowance
        every clause below asks for (feasibility, ceiling and floor), so
        the three can never read two different laws."""
        if _C is not None:
            return abs(_C[j] - _C[i])
        return _seg_cap(i, j) * abs(float(stations_s[j])
                                    - float(stations_s[i]))

    for a in range(len(items)):
        ia, za = items[a]
        for b in range(a + 1, len(items)):
            ib, zb = items[b]
            ds = abs(stations_s[ib] - stations_s[ia])
            dz = abs(zb - za)
            if dz > _allow(ia, ib) + 1e-9:
                need = dz / ds if ds > 1e-9 else float("inf")
                infeasible.append((ia, ib, need))
    if infeasible and not _weld:
        # THE REFUTED WHOLE-CHAIN REVERT, kept only behind
        # ``O4_ROAD_PROFILE_WELD_OUTRANKS_CAP=0`` (ruling 1's refutation
        # ledger): one over-cap pin pair discarded every other station's
        # lawful ramp — HECA chain 13, 42 stations and BOTH owner sites,
        # abandoned over a single 8.62 % span.
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
        # THE CHORD RUNS IN THE CAP-DISTANCE COORDINATE, not in raw
        # arclength, whenever the caps vary: the rise distributes in
        # proportion to the cap-distance each stretch can carry, which
        # is the owner's "distributed over its whole path" read when the
        # path's own cap is not one number.  A straight-in-``s`` chord
        # crosses a 1 % stretch at more than 1 % by construction, and
        # the floor would then stand ABOVE the ceiling the same caps
        # generate.  With one cap everywhere ``C`` is proportional to
        # ``s`` and this is the identical linear chord.
        axis = _C if _C is not None else stations_s
        s0, s1 = axis[lo_p], axis[hi_p]
        if abs(s1 - s0) < 1e-9:
            return None
        t = (axis[i] - s0) / (s1 - s0)
        return pins[lo_p] + t * (pins[hi_p] - pins[lo_p])

    for i in range(n):
        if i in pins:
            # Only a WELD (or an authored / crossing pin) holds.
            target[i] = float(pins[i])
            continue
        ch = _chord(i)
        v = values[i]
        if ch is not None and _both:
            # RULING 2 — a BRACKETED interior station conforms to the
            # chord in BOTH directions.  It is not clamped into the cap
            # envelope: the chord already passes through both bracketing
            # pins, so where the pair is feasible the chord IS inside the
            # envelope, and where it is not (ruling 1) the excess is the
            # thing the census is meant to see.
            target[i] = float(ch) if v is not None else None
            continue
        hi = min(z + _allow(i, p) for p, z in pins.items())
        lo = max(z - _allow(i, p) for p, z in pins.items())
        if ch is not None and ch > lo:
            lo = ch                      # Amendment 3 §2, raise-only
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
           "disagreeing_pins": 0, "station_capped": 0, "self_pinned": 0,
           "over_cap_spans": 0, "worst_over_cap_pct": 0.0}
    from . import config as _cfg
    if not bool(getattr(_cfg, "FREE_ROAD_PROFILE_PASS", True)):
        return out
    _SELF_PINS = bool(getattr(_cfg, "FREE_ROAD_PROFILE_SELF_PINS", True))
    _WELD_OUTRANKS = _weld_outranks_cap()
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
    # A chain with NO weld and NO binding still has ENDS (Amendment 3 §2),
    # so the early return only applies when self-pins are off too.
    if not pins_node and not _SELF_PINS:
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

    # ── THE PASS'S OWN DIAGNOSTIC DUMP (instrument, default OFF) ─────
    # ``O4_FRP_DIAG=<path>`` writes one JSONL record per call: every
    # chain's stations (arclength, lat/lon, value, pin, per-station cap,
    # target) and its infeasible pin pairs, plus every road-family node
    # with its frozen/pinned/station state.  It answers the round's own
    # question — WHERE does a chain's ramp fail to build — and it reads
    # only what the pass already computed, so it can never change a
    # value.  Convention: the same env-armed diagnostic
    # ``O4_ENVELOPE_DIAG`` / ``O4_DUMP_SOLVE_STATE`` use.
    import os as _os
    _diag_path = _os.environ.get("O4_FRP_DIAG") or ""
    _diag = {"icao": icao, "chains": []} if _diag_path else None

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
        # ── SELF-PINS: THE CHAIN'S OWN EMITTED END VALUES ────────────
        # (owner ruling 2026-08-28, Amendment 3 §2.)  "A chain's end is
        # where it meets the settled world, and its emitted end value is
        # that consensus, whatever produced it."  The owner's fifth site
        # (CYXY 60.7100244,-135.0727863 -> 60.7087015,-135.0746305) has
        # NO airside weld at either end — 0 shared nodes, none within
        # 8 m; both ends meet a gap_fill_spine graded_strip — so it had
        # no pins at all and its 3.631 m sag (station 59.5 of 190.3,
        # measured on the round-5d control) was invisible to the chord
        # law.  A SELF-PIN reads the chain's OWN first/last station value
        # and nothing else: no adoption, no authority transfer, and the
        # strip's value is never read, so the 2026-08-15 carrier
        # adjudication stands untouched.  Raise-only toward the chord
        # between them keeps hills (twinned).
        if _SELF_PINS and len(sids) >= 2:
            for _end in (0, len(sids) - 1):
                if _end in pins:
                    continue
                v_end = vals[_end]
                if v_end is not None:
                    pins[_end] = float(v_end)
                    out["self_pinned"] += 1
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
        if _diag is not None:
            _rows = []
            for pos, sid in enumerate(sids):
                _mem = list(stations[sid]["members"])
                _xy = node_pos.get(_mem[0]) if _mem else None
                try:
                    _ll = layout.m_to_ll(_xy[0], _xy[1]) if _xy else None
                except Exception:                          # pragma: no cover
                    _ll = None
                _rows.append({
                    "s": round(float(ss[pos]), 3),
                    "ll": ([round(_ll[0], 9), round(_ll[1], 9)]
                           if _ll else None),
                    "v": (None if vals[pos] is None
                          else round(float(vals[pos]), 4)),
                    "pin": (round(float(pins[pos]), 4)
                            if pos in pins else None),
                    "cap": st_caps[pos],
                    "t": (None if target[pos] is None
                          else round(float(target[pos]), 4)),
                    "n": len(_mem),
                })
            _diag["chains"].append({
                "line": int(li), "stations": _rows,
                "infeasible": [[int(a), int(b), round(float(g), 6)]
                               for (a, b, g) in infeasible],
            })
        if infeasible:
            out["infeasible_chains"] += 1
            worst = max(infeasible, key=lambda t: t[2])
            # THE ALLOWANCE THE PAIR ACTUALLY FAILED, named.  Reporting
            # "against the 8 % road class" while a 1 % STATION was what
            # bound the span is how this refusal read as a road-class
            # infeasibility for a whole round; the binding number is the
            # chain's own cap-distance over that span.
            _span = abs(ss[worst[1]] - ss[worst[0]])
            _seg = [c for c in st_caps[min(worst[0], worst[1]):
                                       max(worst[0], worst[1]) + 1]
                    if c is not None]
            _bind = min(_seg) if _seg else float(_CAP)
            if not _WELD_OUTRANKS:
                UI.vprint(1,
                    f"  [pav-builder] {icao}: free-road profile REFUSED on "
                    f"chain {li}: its pinned ends need "
                    f"{100.0 * worst[2]:.1f} % over {_span:.1f} m against a "
                    f"{100.0 * float(_CAP):.0f} % road class whose "
                    f"STRICTEST station on that span is "
                    f"{100.0 * _bind:.1f} % "
                    f"({len(infeasible)} such pair(s)) — the shortfall is "
                    f"REPORTED, the chain is left as the solve made it.")
                continue
            # RULING 1 — THE WELD OUTRANKS THE CAP.  The span BUILDS: both
            # welds are met exactly and the excess stands as a census row.
            out["over_cap_spans"] += len(infeasible)
            out["worst_over_cap_pct"] = max(
                out["worst_over_cap_pct"], 100.0 * float(worst[2]))
            UI.vprint(1,
                f"  [pav-builder] {icao}: free-road profile OVER-CAP SPAN "
                f"BUILT on chain {li}: its welds demand "
                f"{100.0 * worst[2]:.1f} % over {_span:.1f} m against a "
                f"{100.0 * float(_CAP):.0f} % road class whose STRICTEST "
                f"station on that span is {100.0 * _bind:.1f} % "
                f"({len(infeasible)} such pair(s)) — CONTACT IS VALUE "
                f"(RULINGS 29c): both welds are met EXACTLY, the grade "
                f"between them is the one the geometry demands, and the "
                f"excess is PRICED as a census row rather than converted "
                f"into a step or reverted with the chain's lawful spans.")
        for pos, sid in enumerate(sids):
            t = target[pos]
            if t is None:
                continue
            for m in stations[sid]["members"]:
                if m in frozen or m not in cur:
                    continue        # LAW 1: never write a pinned datum
                new[m] = float(t)

    if _diag is not None:
        _nodes = []
        for i in range(len(xy)):
            if i not in cur:
                continue
            try:
                _ll = layout.m_to_ll(xy[i][0], xy[i][1])
            except Exception:                              # pragma: no cover
                continue
            _nodes.append({
                "ll": [round(_ll[0], 9), round(_ll[1], 9)],
                "v": round(float(cur[i]), 4),
                "frozen": bool(i in frozen),
                "pin": (round(float(pins_node[i]), 4)
                        if i in pins_node else None),
                "st": node_station.get(i),
                "cap": node_cap.get(i),
                "new": (round(float(new[i]), 4) if i in new else None),
                "roles": sorted({getattr(s, "role", "?")
                                 for s in (node_shapes.get(i) or ())}),
            })
        _diag["nodes"] = _nodes
        import json as _json
        with open(_diag_path, "a", encoding="utf-8") as _fh:
            _fh.write(_json.dumps(_diag) + "\n")

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
        + (f"carry {out['over_cap_spans']} OVER-CAP SPAN(S) BUILT to "
           f"their welds (worst {out['worst_over_cap_pct']:.1f} %, PRICED "
           f"as census rows — ruling 1, the weld outranks the cap)"
           if _WELD_OUTRANKS else "REFUSED as infeasible") +
        f"; {out['frozen']} vertex/vertices FROZEN "
        f"because a non-road authority carries them — airside is king, "
        f"by construction, and {len(keys)} key(s) are published to the "
        f"chord limiter as profile-owned.")
    return out
