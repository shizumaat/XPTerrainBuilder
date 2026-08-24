"""Top-level orchestration for the one-profile elevation solve.

``solve_route_profile`` (docs/one_profile_solve.md) is the ONLY pass that sets
airside elevations.  It reuses the proven, elevation-neutral primitives from
``solver_primitives`` (node list, seed, DEM sample, shape grade graph, level
coupling, writeback) and the route-feasibility building levels from
``building_feasibility`` — then runs the single :func:`one_profile_solve`
(one graph: the taxi-route reach band) over them.

Wiring (``solver.solve`` dispatches here unconditionally):

    nodes/seed/dem  →  reach band + building seats  →  one solve  →  writeback
"""
from __future__ import annotations

import heapq as _heapq
import math as _math
import os as _os
import time as _time

# PROJECTION SELF-LIMITS — the derivation lives beside the constants in
# config.py (debug lane A 2026-08-05).  Module-level because they are
# default arguments, which Python binds at def time.
from auto_patch.config import (
    FAIRING_MAX_SWEEPS_APRON, FAIRING_MAX_SWEEPS_CHAIN,
    FAIRING_MAX_SWEEPS_GAP_SPINE, FAIRING_MAX_SWEEPS_SPINE)
from ..node_space import store_of as _store_of
# THE STAGE TAG (staged-solve round S1b) — see auto_patch/solve_stage.py.
from auto_patch.solve_stage import (
    STAGE_A as _STAGE_A, STAGE_B as _STAGE_B, STAGE_KEY as _STAGE_KEY)
from .anchors import (
    apron_body_nodes,
    build_building_seats, detached_pad_nodes, seat_detached_pads_by_law,
    withhold_airside_band_from_detached_pads,
    build_nobuilding_apron_seats,
    reseat_service_mouths as _reseat_service_mouths,
    build_apron_contact_floors, building_spine_floor, node_bands, reach_band_for)
from .one_solve import (envelope_from_band_enabled, one_profile_solve,
                        price_slab_against_law,
                        route_metric_envelope_enabled,
                        _CATCH_ALL_FAMILY_TAGS as _CATCH_ALL_FAMILIES)


def _flex_value_envelope(adjacency, node_owner_ref, seeds, sign):
    """ceil (sign=+1): min over seeds of value + path budget;
    floor (sign=−1): max of value − path budget.  Strict pop guard
    (no epsilon) — the lazy-Dijkstra re-expansion lesson.

    Returns ``{node: (value, origin_ref)}`` where ``origin_ref`` is
    the runway owning the BINDING seed (None = a non-runway anchor:
    seam pin / building seat / other immovable).  The origin decides
    whether a demand may be SPLIT with the pulling runway (user
    2026-07-06: the deficit divides across the runways pulling on
    it) or must be absorbed in full.

    DOMINATED-PUSH SUPPRESSION (perf P3 lane H).  The lazy heap used
    to take EVERY relaxation, so one node accumulated one entry per
    incident edge and the heap carried mostly entries that pop into
    the ``k in best`` guard and are thrown away.  ``pushed`` records
    the smallest heap key ever pushed for a node and a relaxation
    that is not strictly smaller is dropped.  That is not a heuristic
    — it is exactly the entry the original discarded:

      * a STRICTLY LARGER key can only pop after some smaller key for
        the same node, and that smaller pop puts the node in ``best``,
        so the larger one always hit ``if k in best: continue``;
      * an EQUAL key would pop after the earlier equal one, because
        ``_tie`` increases monotonically at every push and the heap
        orders ``(key, _tie)`` — so the earlier push wins the node's
        ``origin`` in both versions.

    ``best`` values, the origins they carry, and the pop ORDER of
    everything that survives are therefore identical; only pops that
    did nothing are gone.  The relaxation ARITHMETIC is left spelled
    exactly as it was (``kv + sign * budget``, negated back for the
    floor pass) — the algebraically equal ``key + budget`` differs on
    one input, a ``-0.0`` key with a ``0.0`` budget, and the
    negative-zero gate lane C had to build is the reason that is not
    worth the two saved flops."""
    best: dict = {}
    pushed: dict = {}           # node -> smallest key ever pushed
    _tie = 0                    # heap tiebreaker: origin is not orderable
    pq = []
    for i, v in seeds.items():
        _k0 = v if sign > 0 else -v
        pq.append((_k0, _tie, i, node_owner_ref.get(i)))
        pushed[i] = _k0
        _tie += 1
    _heapq.heapify(pq)
    _pop = _heapq.heappop
    _push = _heapq.heappush
    _adj_get = adjacency.get
    _positive = sign > 0
    while pq:
        key, _t, k, origin = _pop(pq)
        if k in best:
            continue
        kv = key if _positive else -key
        best[k] = (kv, origin)
        for (j, budget) in _adj_get(k, ()):
            if j in best:
                continue
            nt = kv + sign * budget
            nk = nt if _positive else -nt
            _prev = pushed.get(j)
            if _prev is not None and nk >= _prev:
                continue
            pushed[j] = nk
            _tie += 1
            _push(pq, (nk, _tie, j, origin))
    return best


def _apply_runway_flex_hook(layout, icao, nodes, bucket_to_idx, elev,
                            base_hard, shape_constraints, G) -> int:
    """RUNWAY FLEX Stage B2 (docs/runway_flex_plan.md).  Returns the
    number of envelope demands flexed (0 = nothing to do).

    Per runway: seed a value-propagating envelope from ALL OTHER hard
    anchors (other runways' nodes + tile-seam pins) through the law
    graph at FULL legal budgets — the FLEX-LAST condition (taxiways at
    max cap).  Every own node outside its [floor, ceil] is a DEMAND at
    the interval edge (the minimum move); demands thin to ~80 m axis
    bins, clamp to the profile's certain-anchor slack
    (``flex_slack_at``), stay runway-law-consistent between bins, and
    apply through ``apply_runway_flex`` (FAA gates re-run).  Profiles
    iterate toward mutual feasibility until a round drains under the
    0.01 m materiality floor, capped at ``RUNWAY_FLEX_MAX_ROUNDS``;
    runway node seeds + the runway-join anchor map re-derive from the
    flexed shapes.
    """
    import heapq as _heapq
    from auto_patch import grade_graph as _GGf
    from auto_patch.runway_redistribute import (apply_runway_flex,
                                                flex_slack_at)
    from auto_patch.layout import ROLE_RUNWAY

    profiles = getattr(layout, "_runway_redistributed_profiles", None)
    if not profiles or len(profiles) < 2:
        return 0        # single runway (or no profiles) — nothing flexes

    n = len(elev)
    contacts = {i: float(v) for i, v in G.runway_anchor.items() if i < n}
    if len(contacts) < 2:
        return 0

    # full-budget adjacency (the law graph = taxiways at max cap).
    adjacency: dict = {}

    def _add_edge(i, j, budget):
        if budget is None or budget < 0 or i == j:
            return
        adjacency.setdefault(i, []).append((j, budget))
        adjacency.setdefault(j, []).append((i, budget))

    for _sc in shape_constraints:
        for _edge in _sc.get("edges", ()):
            # INTERVAL EDGES (Stage B0) are the terrain-role signed-slab form
            # (i, j, interval_low, interval_high).  This runway-flex value
            # envelope models symmetric full-budget reach only; a one-sided or
            # asymmetric interval has no symmetric budget, so an interval edge
            # contributes its widest symmetric surrogate (both sides finite) or
            # is skipped (one side open).  With every terrain gate off none are
            # produced and this branch is never taken.
            if len(_edge) >= 4:
                _i, _j, _lo, _hi = _edge[0], _edge[1], _edge[2], _edge[3]
                if _lo is None or _hi is None:
                    continue
                _add_edge(_i, _j, max(abs(_lo), abs(_hi)))
                continue
            i, j, budget = _edge
            _add_edge(i, j, budget)
    for (a, b, cap, _sp) in G.edges:
        if a in G.pos and b in G.pos:
            d = _GGf._dist(G.pos.get(a), G.pos.get(b))
            _add_edge(a, b, cap.at(d, 0.0))

    # ── STAGE B2: envelope-level demands along the WHOLE profile ─────
    # (contact-pair flex drained the contact deficit but the pockets
    # press against every runway node — 2026-07-06 measurement).
    from auto_patch.runway_redistribute import _interp_profile
    from auto_patch.pavement.runway_segments import (
        MAX_RUNWAY_GRADE as _RWY_CAP)

    cps = layout.canonical_points

    def _runway_nodes_for(ref):
        node_set = set()
        for s in layout.shapes:
            if (s.role != ROLE_RUNWAY or (s.ref or "") != ref
                    or s.polygon is None or s.polygon.is_empty):
                continue
            ring = list(s.polygon.exterior.coords)
            for (x, y) in (ring[:-1] if ring and ring[0] == ring[-1]
                           else ring):
                i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
                if i is not None and i < n:
                    node_set.add(i)
        return node_set

    runway_nodes_by_ref = {ref: _runway_nodes_for(ref)
                           for ref in profiles}

    def _reseed_runway_values(ref):
        for s in layout.shapes:
            if (s.role != ROLE_RUNWAY or (s.ref or "") != ref
                    or s.polygon is None or s.polygon.is_empty):
                continue
            ring = list(s.polygon.exterior.coords)
            ring_open = (ring[:-1] if ring and ring[0] == ring[-1]
                         else ring)
            if s.node_altitudes and len(s.node_altitudes) >= len(ring_open):
                per_vertex = s.node_altitudes
            elif (s.altitude_high is not None
                    and s.altitude_low is not None
                    and len(ring_open) == 4):
                per_vertex = [s.altitude_high, s.altitude_low,
                              s.altitude_low, s.altitude_high]
            elif s.altitude is not None:
                per_vertex = [float(s.altitude)] * len(ring_open)
            else:
                continue
            for (x, y), value in zip(ring_open, per_vertex):
                i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
                if i is not None and i < n and base_hard[i]:
                    elev[i] = float(value)

    # ── THE WORLD STAMP (RULINGS 2026-08-06, binding point 3) ─────────
    # Flex numbers were compared ACROSS ARMS by earlier lanes (canyon vs
    # plateau), and a canyon line and a plateau line are identically
    # SHAPED — nothing on them says which world produced them.  The
    # world enters the flex through the SEED VALUES: every demand is a
    # deficit against ``_value_envelope(seeds, ±1)``, and ``seeds`` is
    # ``elev`` at the base-hard nodes, which is where the DEM lands.  So
    # the seed population's extent IS the world, at hook entry, before
    # the flex has moved anything.  One O(n) pass, against the O(n) seed
    # comprehension this hook already runs once per ref per round.
    _w_lo = _w_hi = None
    _w_n = 0
    for _i in range(n):
        if not base_hard[_i]:
            continue
        _v = elev[_i]
        _w_n += 1
        if _w_lo is None or _v < _w_lo:
            _w_lo = _v
        if _w_hi is None or _v > _w_hi:
            _w_hi = _v
    _world_stamp = (
        f"world: {_w_n} seed(s) z∈[{_w_lo:.2f}, {_w_hi:.2f}] m"
        if _w_n else "world: 0 seed(s)")

    # node index → owning runway ref, for envelope-origin attribution
    # (which runway's value is PULLING a demand).
    node_owner_ref = {}
    for _ref, _ns in runway_nodes_by_ref.items():
        for _i in _ns:
            node_owner_ref[_i] = _ref

    def _value_envelope(seeds, sign):
        """The hook's binding of :func:`_flex_value_envelope` — module
        level so the equivalence twin can drive it against the naive
        lazy Dijkstra it replaced (lane D's ``_envelopes_disjoint``
        pattern)."""
        return _flex_value_envelope(adjacency, node_owner_ref, seeds, sign)

    _BIN_M = 80.0
    # ── THE DEAD ZONE (spec ``docs/specs/demfollow-joint-spec.md``;
    # STANDING LAW) ───────────────────────────────────────────────────
    # This tolerance decides which envelope deficits the flex is even
    # ALLOWED to see, so it IS the band's materiality floor (0.01 m).
    # The old 0.05 m sat five times above it, and every demand in
    # [0.01, 0.05) was invisible to the machinery that exists to drain
    # exactly that tension — the flex declined to move and the band then
    # adjudicated the same deficit as a law violation (HEAZ under
    # DEM-follow: a 0.0174 m cross-runway differential inverts the final
    # band on all 47 route nodes of the taxiway between the two
    # runways).
    from auto_patch.config import runway_flex_demand_tol_m
    _DEMAND_TOL_M = runway_flex_demand_tol_m()
    # NO DISPLACEMENT BUDGET (owner ruling 2026-08-05, RULINGS.md "Runway
    # flex: the LAW is the only bound").  The 4.0 m cumulative cap and its
    # pre-flex profile snapshot are DELETED: the lawful bounds are the CIFP
    # pins (absolute), the per-segment runway grade caps priced below as
    # ``slack``, and ``apply_runway_flex``'s verify-and-relax.  Minimum
    # displacement stays the objective through the origin ÷2 split and the
    # drain-what-is-demanded loop, never through an arbitrary bound.
    total_deficit = total_drained = 0.0
    n_demands = 0
    flexed_refs: set = set()
    # ── FIX 4: THE HONEST INSTRUMENT (spec
    # ``docs/specs/runway-flex-completion-spec.md``; UNGATED, report-only)
    # ─────────────────────────────────────────────────────────────────
    # The B2 line above under-reported demand by 45 % and over-reported
    # achievement.  ``total_deficit`` only ever accrued for candidates
    # that SURVIVED the move kill (materiality floor) and the
    # greedy-keep, so the
    # demand the flex could not touch was invisible (HECA measured: true
    # 2380.07 m, logged 1310.60 m); and nothing compared what
    # ``apply_runway_flex`` was asked for against what it returned, so
    # its verify-and-relax silently discarded 9.90 of 333.17 m.  These
    # accumulators are WRITE-ONLY — nothing below reads them to decide
    # anything, so the surface is unchanged.
    # ── THE PARTITION (cycle-7.5 instrument sweep) ────────────────────
    # The B2 line used to print
    #   "TRUE demand X m = <drained> + <killed> + <dropped>"
    # and that "=" was FALSE two independent ways:
    #   (i)  MIXED QUANTITIES.  ``_true_deficit`` accrues ``deficit`` —
    #        the band-envelope deficit at a node.  ``total_drained``
    #        accrues ``_ach`` — the ACHIEVED profile move at the target
    #        station, i.e. the deficit AFTER the origin ÷2 split, AFTER
    #        the slack clamp ``move = min(pull, slack)`` and AFTER
    #        apply's verify-and-relax.  ``_ach ≤ _req ≤ deficit``, so the
    #        left side systematically exceeds the right by construction.
    #   (ii) A MISSING BUCKET.  Retired bins add to ``_true_deficit`` but
    #        appeared only in a later, "+"-less clause, so whenever
    #        anything retired the "=" could not balance even in
    #        principle.
    # THE REAL PARTITION, exhaustive by construction — every presented
    # bin lands in EXACTLY one of these four, all of them ``deficit``:
    #     _true_deficit == total_deficit      (kept by the greedy keep)
    #                    + _killed_deficit    (move <= materiality floor)
    #                    + _dropped_deficit   (dropped by the greedy keep)
    #                    + _retired_deficit   (not re-presented)
    # ``total_drained`` is reported BESIDE it as an ACHIEVEMENT against
    # the kept bucket, never as a member of the partition.
    _true_deficit = 0.0                 # every bin, killed ones included
    _killed_n = 0
    _killed_deficit = 0.0               # killed at move <= materiality
    _dropped_n = 0
    _dropped_deficit = 0.0              # dropped by the greedy-keep
    _requested_total = _achieved_total = 0.0
    _by_ref: dict = {}                  # ref -> per-runway accounting

    def _ref_row(ref):
        return _by_ref.setdefault(ref, {
            "true_deficit": 0.0, "drained": 0.0, "killed_n": 0,
            "killed_deficit": 0.0, "dropped_n": 0, "requested": 0.0,
            "achieved": 0.0, "last_deficit": 0.0, "last_drain": 0.0,
            "rounds": 0, "retired_n": 0, "retired_deficit": 0.0,
            # the partition's remaining two members, per runway, so the
            # per-ref rows sum to the summary the same way the per-ROUND
            # rows already do (the one place binding point 4's pattern
            # was already implemented).
            "kept_deficit": 0.0, "dropped_deficit": 0.0,
            # this round's retired share of ``last_deficit`` — the
            # residual must not double-count it (see the residual note).
            "last_retired": 0.0})

    # ── THE ACHIEVED-STATE LOOP (spec
    # ``docs/specs/flex-convergence-spec.md``) ────────────────────────
    # The loop used to iterate on REQUESTED state.  ``move`` — what the
    # clamp chain decided to ask for — was booked as "drained" the moment
    # a candidate survived the greedy keep, before ``apply_runway_flex``
    # had been called at all; the round-drain convergence test then read
    # that same fiction.  With §2a closing the unlawful end-zone release
    # valve, apply's verify-and-relax refuses ~52 % of the requests, and
    # the fiction became load-bearing: measured at HECA (composed arm),
    # the hook booked 312.76 m drained on 05L/23R where apply landed
    # 116.52 m, and rounds 1-11 re-presented a BIT-IDENTICAL rejected
    # target set (05L/23R t=0.8990: requested 64.417 m twelve times,
    # achieved 60.903→60.918, shortfall +3.499 m every round).  Because
    # the round drain was requested, it never fell under the floor, so
    # the loop always ran to the 12-round cap: 441 demands over the same
    # 12 rounds against the gate-off arm's 285.
    #
    # Three consequences, all fixed here:
    #   * ``total_drained`` / ``_row["drained"]`` / ``_row["last_drain"]``
    #     accumulate what apply ACHIEVED (report-only, so the gate-off
    #     surface is untouched — only the honest line changes);
    #   * the round-drain floor tests achieved drain, so a round that
    #     achieves nothing STOPS the loop instead of spinning;
    #   * a bin whose target apply refuses TWICE is RETIRED for the run
    #     and never re-presented (loud record below).
    # Demand re-derivation already read achieved state and must keep
    # doing so: ``current`` interpolates the LIVE profile arrays (apply
    # rewrites them) and ``elev`` is re-stamped by
    # ``_reseed_runway_values`` from the flexed shapes after every apply.
    _RETIRE_AFTER = 2                   # spec: "rejected … TWICE"
    _reject_count: dict = {}            # (ref, bin_key) -> consecutive
    _retired: dict = {}                 # (ref, bin_key) -> record
    _retired_deficit = 0.0
    _round_rows: list = []              # per-round requested/achieved/retired

    # ── FIX 2: CONVERGE TO MUTUAL FEASIBILITY (same spec; STANDING
    # LAW) ────────────────────────────────────────────────────────────
    # Every HECA demand's binding seed is another flexible runway
    # (277/277 candidates), so the ORIGIN SPLIT halves every pull by
    # design — the two profiles are supposed to meet in the middle.  With
    # a fixed 3 rounds the geometric tail is truncated at 1/8 of the
    # demand still outstanding, which is not a law, just a loop bound;
    # the Stage-C counterfactual measured 2.004 of 2.672 m drained.
    # So: keep the snapshot-simultaneous rounds and the split exactly as
    # they are and iterate until a round drains less than the materiality
    # floor (0.01 m — CLAUDE.md item 3(a)) or the hard cap trips.
    # Everything else — greedy keep, slack clamp, the per-segment
    # threshold law — stands.  (The 4.0 m displacement budget that used to
    # be listed here is DELETED, owner 2026-08-05.)
    from auto_patch.config import (RUNWAY_FLEX_MAX_ROUNDS,
                                   RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M)
    _max_rounds = RUNWAY_FLEX_MAX_ROUNDS
    _rounds_run = 0
    _stop_reason = "no further demand"
    # The base-hard membership the seed comprehension below filters on is
    # fixed for the whole hook (``base_hard`` is never written here), so
    # the O(n) scan it did per runway per round is hoisted.  The list is
    # in ascending index order, which is the order ``range(n)`` produced,
    # so the seed dict's INSERTION order — and therefore the initial heap
    # tiebreakers inside ``_value_envelope`` — is unchanged.
    _base_hard_idx = [i for i in range(n) if base_hard[i]]
    for _round in range(_max_rounds):
        _round_drain = 0.0          # ACHIEVED drain, booked after apply
        _round_requested = 0.0
        _round_retired = 0
        _bin_of_t: dict = {}        # (ref, t) -> bin key, this round only
        _rounds_run = _round + 1
        # SNAPSHOT-SIMULTANEOUS round (user 2026-07-06): demands for ALL
        # runways are computed against the SAME pre-round state, then
        # applied together.  The previous sequential loop re-seeded after
        # each runway, so the FIRST runway absorbed the entire
        # inter-runway deficit (HECA: one-sided 16-17.8 m drops instead
        # of the two profiles meeting in the middle).
        round_targets: dict = {}
        for ref, own_nodes in runway_nodes_by_ref.items():
            if not own_nodes:
                continue
            profile = profiles.get(ref)
            if profile is None:
                continue
            # EAT ANCHOR-RECT pins are DERIVED from the runway-end
            # profile values (owner rulings 2026-07-27) and must never
            # feed back as flex envelope seeds: a regulation pin sits a
            # whole tail height BELOW its end, so seeding from it would
            # demand the runway profile flex DOWN toward its own
            # derivative — bending the datum the EAT law explicitly
            # must never bend (measured HECA: a −15 m EASA pin 316 m
            # off the 23C end).
            _eat_pin_idx = getattr(layout, "_eat_anchor_pin_idx",
                                   None) or ()
            seeds = {i: elev[i] for i in _base_hard_idx
                     if i not in own_nodes
                     and i not in _eat_pin_idx}
            if not seeds:
                continue
            ceil_env = _value_envelope(seeds, +1)
            floor_env = _value_envelope(seeds, -1)
            ax_x, ax_y = profile['axis_a']
            dx, dy = profile['axis_d']
            axis_len2 = profile['axis_len2']
            axis_len = _math.sqrt(axis_len2)
            # per-bin worst demand: (deficit, t, target_value, origin)
            bins: dict = {}
            for i in own_nodes:
                value = elev[i]
                hi, hi_origin = ceil_env.get(i, (None, None))
                lo, lo_origin = floor_env.get(i, (None, None))
                target = origin = None
                if hi is not None and value > hi + _DEMAND_TOL_M:
                    target, origin = hi, hi_origin
                elif lo is not None and value < lo - _DEMAND_TOL_M:
                    target, origin = lo, lo_origin
                if target is None:
                    continue
                x, y = nodes[i]
                t = ((x - ax_x) * dx + (y - ax_y) * dy) / axis_len2
                if not (0.0 < t < 1.0):
                    continue
                deficit = abs(value - target)
                bin_key = int(t * axis_len / _BIN_M)
                if (bin_key not in bins
                        or deficit > bins[bin_key][0]):
                    bins[bin_key] = (deficit, t, target, origin)
            if not bins:
                continue
            # slack-clamp each target, then make consecutive targets
            # runway-law-consistent (anchoring mutually-infeasible
            # targets would bake an over-cap profile).
            candidates = []
            _row = _ref_row(ref)
            _row["rounds"] = _round + 1
            _row["last_deficit"] = sum(b[0] for b in bins.values())
            _row["last_drain"] = 0.0
            # ``last_deficit`` is taken over ALL bins — it is computed
            # BEFORE the retirement filter below, so retired demand is
            # inside it and can never appear in ``last_drain``.  Left
            # alone, the residual ``last_deficit − last_drain`` silently
            # RE-COUNTS the retired bucket the same sentence prints
            # separately.  Book the retired share so it can be
            # subtracted rather than stamped.
            _row["last_retired"] = 0.0
            for (bin_key, (deficit, t, target, origin)) in bins.items():
                # RETIREMENT (spec ``flex-convergence``): a bin whose
                # target apply has already refused ``_RETIRE_AFTER``
                # times is not re-presented — the refusal is a law
                # verdict, not a transient.  The demand is still counted
                # as TRUE demand (it is real, and the airport still has
                # it); it moves into its own bucket so the honest line
                # names what the flex gave up on rather than hiding it
                # inside "drained".
                if (ref, bin_key) in _retired:
                    _true_deficit += deficit
                    _row["true_deficit"] += deficit
                    _retired_deficit += deficit
                    _row["retired_deficit"] += deficit
                    _row["last_retired"] += deficit
                    continue
                current = _interp_profile(profile['fractions'],
                                          profile['elevs'], t)
                # ORIGIN SPLIT (user 2026-07-06): when the binding
                # anchor is ANOTHER FLEXIBLE RUNWAY, the deficit is a
                # joint obligation — this profile moves only its share
                # (deficit / number of runways pulling = 2 for a pair)
                # and the other runway's own round moves the rest, so
                # the profiles meet in the middle.  An immovable origin
                # (seam pin, building seat, CIFP-adjacent) cannot yield
                # — full move.
                pull = abs(target - current)
                if (origin is not None and origin != ref
                        and origin in profiles):
                    pull = pull / 2.0
                direction = 1.0 if target > current else -1.0
                slack = flex_slack_at(profile, t, direction)
                # THE LAW IS THE ONLY BOUND (owner 2026-08-05): the move is
                # what is demanded, clamped only by the grade-law slack the
                # segment prices.  No cumulative displacement budget.
                move = min(pull, slack)
                # FIX 4: count the demand BEFORE the kill, so the line
                # quotes what the airport actually asked for.
                _true_deficit += deficit
                _row["true_deficit"] += deficit
                # MOVE KILL, at the ONE materiality floor: a move this
                # small is below the resolution every other flex floor
                # (the demand tolerance, the round drain floor) and the
                # band-inversion check are priced at, so it is reported
                # as killed rather than applied.  Same constant, not a
                # coincidentally-equal literal.
                if move <= RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M:
                    _killed_n += 1
                    _killed_deficit += deficit
                    _row["killed_n"] += 1
                    _row["killed_deficit"] += deficit
                    continue
                candidates.append((deficit, t,
                                   current + direction * move, move))
                # bin identity for the retirement ledger, carried OUTSIDE
                # the candidate tuple so its sort key is byte-for-byte
                # what it was (``t`` is unique per bin by construction).
                _bin_of_t[(ref, t)] = bin_key
            if not candidates:
                continue
            # Mutual consistency by GREEDY KEEP, largest deficit first:
            # a target inconsistent with an already-kept one (over the
            # runway cap between their axis positions) is DROPPED, not
            # forced — forcing dragged a small flex metres past its own
            # slack (HECA B2 first cut: a 2.8 m step INSIDE 05L/23R).
            # Dropped demands retry next round against moved profiles.
            candidates.sort(reverse=True)
            kept = []
            for (deficit, t, value, move) in candidates:
                consistent = all(
                    abs(value - kept_value)
                    <= _RWY_CAP * abs(t - kept_t) * axis_len + 1e-6
                    for (kept_t, kept_value) in kept)
                if not consistent:
                    continue
                kept.append((t, value))
                total_deficit += deficit
                # NOTE (spec ``flex-convergence``): ``move`` — the
                # REQUESTED move — is deliberately NOT booked as drain
                # here any more.  The drain is booked against what
                # ``apply_runway_flex`` returns, in the apply loop below.
            # FIX 4: the greedy-keep's drops, counted OUTSIDE its loop so
            # the loop body stays byte-for-byte what it was.
            _kept_t = {t for (t, _v) in kept}
            # The KEPT member of the partition, per runway (the global
            # one is ``total_deficit``, booked inside the keep loop).
            _row["kept_deficit"] += sum(c[0] for c in candidates
                                        if c[1] in _kept_t)
            _n_drop = len(candidates) - len(kept)
            if _n_drop:
                _dropped_n += _n_drop
                _row["dropped_n"] += _n_drop
                _dd = sum(c[0] for c in candidates if c[1] not in _kept_t)
                _dropped_deficit += _dd
                _row["dropped_deficit"] += _dd
            if kept:
                round_targets[ref] = sorted(kept)
        if not round_targets:
            break
        for ref, targets in round_targets.items():
            n_demands += len(targets)
            # FIX 4: REQUESTED vs ACHIEVED.  ``apply_runway_flex`` runs a
            # verify-and-relax loop that DROPS targets whose joint
            # re-solve puts a segment over the runway cap — a legitimate
            # law refusal, but until now an invisible one.  Snapshot the
            # profile the targets are measured against, then compare the
            # returned achieved values.  Read-only.
            _pr = profiles.get(ref) or {}
            _pre_fr = list(_pr.get('fractions') or ())
            _pre_el = list(_pr.get('elevs') or ())
            # REFUSAL LEDGER (cycle-5 fix 2 attribution): stamp the round
            # onto whatever this apply call appends, so a refusal can be
            # read against the round that presented it.  Report-only.
            _led_before = len(getattr(layout, "_flex_refusal_ledger",
                                      None) or ())
            _got = dict(apply_runway_flex(layout, {ref: targets}).get(ref)
                        or ())
            for _ev in (getattr(layout, "_flex_refusal_ledger",
                                None) or ())[_led_before:]:
                _ev["round"] = _round + 1
            if _pre_fr and _pre_el:
                _r = _ref_row(ref)
                for (_t, _v) in targets:
                    _before = _interp_profile(_pre_fr, _pre_el, _t)
                    _req = abs(_v - _before)
                    _ach = (abs(_got[_t] - _before) if _t in _got
                            else 0.0)
                    # An apply may only ever fall SHORT of the request;
                    # clamp so a re-solve that overshoots one target
                    # cannot mask a discard at another.
                    _ach = min(_ach, _req)
                    _requested_total += _req
                    _achieved_total += _ach
                    _r["requested"] += _req
                    _r["achieved"] += _ach
                    # ── THE ACHIEVED-STATE BOOKING (spec
                    # ``flex-convergence``) ───────────────────────────
                    # The drain the loop converges on and the drain the
                    # line quotes are now the SAME number apply landed.
                    total_drained += _ach
                    _round_drain += _ach
                    _round_requested += _req
                    _r["drained"] += _ach
                    _r["last_drain"] += _ach
                    # RETIREMENT LEDGER: a request apply did not deliver
                    # to within the materiality floor is a REJECTION.
                    # Two at the same bin and the bin is retired for the
                    # run — the third identical re-presentation is the
                    # fictional-state loop, not convergence.
                    _bk = _bin_of_t.get((ref, _t))
                    if _bk is None:
                        continue
                    _key = (ref, _bk)
                    if (_req > RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M
                            and _ach <= RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M):
                        _n_rej = _reject_count.get(_key, 0) + 1
                        _reject_count[_key] = _n_rej
                        if _n_rej >= _RETIRE_AFTER and _key not in _retired:
                            _retired[_key] = {
                                "ref": ref, "bin": _bk, "t": _t,
                                "station_m": _t * _math.sqrt(
                                    profiles[ref]['axis_len2']),
                                "round": _round + 1,
                                "requested_m": _req}
                            _round_retired += 1
                            _r["retired_n"] += 1
                    else:
                        # progress at this bin — the ledger resets, so a
                        # bin that moves is never retired for two stale
                        # refusals earlier in the run.
                        _reject_count.pop(_key, None)
            _reseed_runway_values(ref)
            flexed_refs.add(ref)
        _round_rows.append((_round + 1, _round_requested, _round_drain,
                            _round_retired))
        # FIX 2's convergence test, on the ACHIEVED drain: a round whose
        # every target apply refused drains 0.0 and STOPS the loop, where
        # the requested-state test spun to the cap.
        if _round_drain < RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M:
            _stop_reason = (f"round achieved-drain {_round_drain:.4f} m < "
                            f"{RUNWAY_FLEX_ROUND_DRAIN_FLOOR_M} m floor")
            break
    else:
        _stop_reason = f"round cap {_max_rounds}"

    if not flexed_refs:
        return 0

    # SHARED-VERTEX PROPAGATION (user 2026-07-06 root-cause): the flex
    # rewrites RUNWAY shapes only, but junctions/aprons stitched to the
    # runway edge carry pre-flex values at the SHARED vertices (stamped
    # by pre-solve reconciliation).  Left stale, the neighbour's value
    # wins the shared bucket at seeding/writeback and re-imposes the
    # pre-flex elevation INTO the flexed runway ring (HECA 05L: one
    # 58.3 vertex in a 61.2 ring = a 24 % runway-internal step).  The
    # flexed runway is the authority at its own edge: re-stamp every
    # coincident vertex on every other shape, and the solver seed.
    flexed_value_by_key: dict = {}
    # sorted(): flexed_refs is a set of STRING runway refs, so its iteration
    # order is PYTHONHASHSEED-dependent.  Where two flexed runways share a
    # canonical vertex (crossing runways — their reconciled node_altitudes can
    # disagree by up to ~2 cm) the LAST writer wins the shared key, so the
    # winner must be pinned or solved edge altitudes differ run to run
    # (observed at KBNA: ±1 cm flips at the 13/31×02C crossing cascading into
    # adjacent-ground band survival).
    for ref in sorted(flexed_refs):
        for s in layout.shapes:
            if (s.role != ROLE_RUNWAY or (s.ref or "") != ref
                    or s.polygon is None or s.polygon.is_empty
                    or not s.node_altitudes):
                continue
            ring = list(s.polygon.exterior.coords)
            for k in range(min(len(ring), len(s.node_altitudes))):
                if s.node_altitudes[k] is None:
                    continue
                key = cps.get_or_add(float(ring[k][0]), float(ring[k][1]))
                flexed_value_by_key[key] = float(s.node_altitudes[k])
    # Flexed runway hard nodes: the join-anchor loop after this hook
    # must not stamp a sampled "local runway elevation" over them — the
    # sampler reads PIECE geometry and disagrees with the flexed profile
    # at piece ends (HECA 05L: 58.30 stamped over the flexed 61.21 hard
    # node → a 24 % runway-internal step).  The flexed profile IS the
    # local runway surface.
    layout._flexed_runway_node_idx = {
        i for ref in flexed_refs
        for i in runway_nodes_by_ref.get(ref, ()) if i < n}
    n_propagated = 0
    for s in layout.shapes:
        if (s.role == ROLE_RUNWAY or s.polygon is None
                or s.polygon.is_empty or not s.node_altitudes):
            continue
        ring = list(s.polygon.exterior.coords)
        alts = list(s.node_altitudes)
        changed = False
        for k in range(min(len(ring), len(alts))):
            key = cps.get_or_add(float(ring[k][0]), float(ring[k][1]))
            value = flexed_value_by_key.get(key)
            if (value is not None and alts[k] is not None
                    and abs(float(alts[k]) - value) > 0.02):
                alts[k] = value
                changed = True
                n_propagated += 1
        if changed:
            s.node_altitudes = alts
    for key, value in flexed_value_by_key.items():
        i = bucket_to_idx.get(key)
        if i is not None and i < n:
            elev[i] = value
    if n_propagated:
        try:
            import O4_UI_Utils as _UIp
            _UIp.vprint(1, f"  [pav-builder] {icao}: runway flex — "
                           f"re-stamped {n_propagated} shared vertex(es) "
                           f"on neighbouring shapes to the flexed edge.")
        except Exception:
            pass

    G.runway_anchor.clear()
    G.runway_anchor_sample.clear()
    _GGf._runway_anchors(layout, G, bucket_to_idx)

    # ── THE HONEST B2 LINE ───────────────────────────────────────────
    # What it says, and why each term is there:
    #   * demand PRESENTED — every bin's deficit, including the ones
    #     killed at the materiality floor (the pre-fix-4 line's "of X m"
    #     was survivors only, 45 % low at HECA).  It is SUMMED OVER
    #     ROUNDS by construction (a bin re-presented in five rounds
    #     contributes five deficits), which is why the line says
    #     "presented", not "TRUE demand": the old wording read as a
    #     single physical quantity the airport has, and it is not one.
    #   * THE PARTITION — kept / killed at the clamp / dropped by
    #     greedy-keep / retired.  These four are exhaustive and are all
    #     the same quantity, so their "=" is a real identity (see the
    #     accumulator block for the proof and for what the old, false
    #     "=" was).
    #   * DRAINED, beside the partition and never inside it: the
    #     ACHIEVED profile move, which is a different quantity from a
    #     deficit and can only ever be ≤ the kept bucket.
    #   * requested vs achieved at ``apply_runway_flex``, naming the
    #     discard its verify-and-relax made.
    #   * per-runway residual: the LAST round's presented demand, MINUS
    #     that round's retired share (which the same sentence reports
    #     separately — leaving it in double-counted it), minus what that
    #     round drained.
    #   * the frame: node space, world (seed extent at hook entry) and
    #     crown space, so two arms' lines are never silently equated.
    #
    # ★ NO SILENT TRUNCATION.  This block used to be one
    # ``try: … except Exception: pass``, so any error mid-report dropped
    # every remaining line with no indication at all — a partial honest
    # line that reads complete.  The stage marker below is advanced as
    # the report proceeds and the handler NAMES where it stopped.
    _flex_stage = "summary"
    try:
        import O4_UI_Utils as _UIf
        _disc = _requested_total - _achieved_total
        _resid_total = sum(
            max(0.0, r["last_deficit"] - r["last_retired"]
                - r["last_drain"])
            for r in _by_ref.values())
        _part = (total_deficit + _killed_deficit + _dropped_deficit
                 + _retired_deficit)
        _UIf.vprint(1, f"  [pav-builder] {icao}: runway flex (B2) — "
                       f"{n_demands} envelope demand(s) applied over "
                       f"{_rounds_run} round(s) ({_stop_reason}) on "
                       f"{', '.join(sorted(flexed_refs))}; demand "
                       f"PRESENTED (summed over rounds) "
                       f"{_true_deficit:.2f} m = {total_deficit:.2f} kept "
                       f"+ {_killed_deficit:.2f} killed at the clamp "
                       f"({_killed_n} bin(s)) + {_dropped_deficit:.2f} "
                       f"dropped by greedy-keep ({_dropped_n} bin(s)) + "
                       f"{_retired_deficit:.2f} retired "
                       f"({len(_retired)} bin(s) after {_RETIRE_AFTER} "
                       f"refusal(s)) [partition sum {_part:.2f} m]; "
                       f"drained (ACHIEVED profile move, not a partition "
                       f"member) {total_drained:.2f} m; apply requested "
                       f"{_requested_total:.2f} m achieved "
                       f"{_achieved_total:.2f} m "
                       f"(discarded {_disc:.2f} m by verify-and-relax); "
                       f"residual (last round, retired demand excluded) "
                       f"{_resid_total:.2f} m "
                       f"[node space n={n}; {_world_stamp}; crown space "
                       f"uncrowned profile z′].")
        # ── THE PER-ROUND LINE (spec ``flex-convergence`` item 3) ─────
        # requested vs achieved vs retired, per round: the shape of the
        # convergence, which the single summary line could not show (a
        # 12-round arm whose rounds 2-12 achieve nothing reads exactly
        # like a 12-round arm that converges slowly).
        _flex_stage = "per-round rows"
        for (_rn, _rq, _ra, _rt) in _round_rows:
            _UIf.vprint(1,
                        f"  [pav-builder]   round {_rn}: requested "
                        f"{_rq:.2f} m, achieved {_ra:.2f} m, retired "
                        f"{_rt} bin(s).")
        _flex_stage = "per-runway rows"
        for _ref in sorted(_by_ref):
            _r = _by_ref[_ref]
            _rpart = (_r['kept_deficit'] + _r['killed_deficit']
                      + _r['dropped_deficit'] + _r['retired_deficit'])
            _UIf.vprint(1,
                        f"  [pav-builder]   {_ref}: demand presented "
                        f"{_r['true_deficit']:.2f} m = "
                        f"{_r['kept_deficit']:.2f} kept + "
                        f"{_r['killed_deficit']:.2f} killed "
                        f"({_r['killed_n']}) + "
                        f"{_r['dropped_deficit']:.2f} greedy-dropped "
                        f"({_r['dropped_n']} bin(s)) + "
                        f"{_r['retired_deficit']:.2f} retired "
                        f"({_r['retired_n']} bin(s)) "
                        f"[partition sum {_rpart:.2f} m]; drained "
                        f"{_r['drained']:.2f} m, "
                        f"apply {_r['achieved']:.2f}/{_r['requested']:.2f} m, "
                        f"residual (retired excluded) "
                        f"{max(0.0, _r['last_deficit'] - _r['last_retired'] - _r['last_drain']):.2f}"
                        f" m after {_r['rounds']} round(s).")
        _flex_stage = "retired records"
        # THE LOUD RECORD: every retired bin, named.  A retirement is the
        # flex conceding a demand it cannot lawfully serve — it must never
        # be a silent give-up (docs/RULINGS.md, feasibility-is-guaranteed:
        # the residual is a law defect to attribute, not a region to hide).
        for _key in sorted(_retired, key=lambda k: (k[0], k[1])):
            _rec = _retired[_key]
            _UIf.vprint(1,
                        f"  [pav-builder]   RETIRED {_rec['ref']} bin "
                        f"{_rec['bin']} @ station {_rec['station_m']:.0f} m "
                        f"(t={_rec['t']:.4f}): apply refused "
                        f"{_rec['requested_m']:.3f} m {_RETIRE_AFTER}x — "
                        f"not re-presented (retired in round "
                        f"{_rec['round']}).")
        # ── WHY APPLY REFUSED (cycle-5 fix 2 attribution) ─────────────
        # A retirement is the flex conceding lawful-looking demand, and
        # the reason lived only inside ``apply_runway_flex``'s
        # verify-and-relax loop.  This prints it: which law the re-solve
        # believed violated (the MAIN cap, or §2a's no-new-end-zone-
        # regression), what the relax believed was lawful at that
        # station, and — decisively — whether the station that BOUND the
        # relax was one the flex itself minted a round earlier (the
        # self-anchor lock; both sides now withdraw those).
        #
        # ★ NO COUNTERFACTUAL.  This block used to end "…{minted} would
        # have been bound by a FLEX-MINTED station, {gain} m of lawful
        # move recovered by the withdrawal."  Both halves overclaimed:
        # ``gain`` is the difference between TWO BOUNDS computed in the
        # same call (``_largest_lawful_move``'s ``slack`` vs
        # ``slack_all``), so "recovered" asserts an outcome no run ever
        # produced; and ``binding_was_minted`` is computed off the
        # minted-INCLUSIVE binder while ``gain`` is a difference of
        # bounds, so the two terms do not describe the same population.
        # Reduced to the three measured numbers, each named for what it
        # is.
        _flex_stage = "apply refusals"
        _refusals = list(getattr(layout, "_flex_refusal_ledger", None) or ())
        if _refusals:
            _by_kind: dict = {}
            for _ev in _refusals:
                _k = (_ev.get("ref"), _ev.get("kind"), _ev.get("action"))
                _row = _by_kind.setdefault(_k, {"n": 0, "req": 0.0,
                                                "minted": 0, "gain": 0.0})
                _row["n"] += 1
                _row["req"] += float(_ev.get("requested_move") or 0.0)
                if _ev.get("binding_was_minted"):
                    _row["minted"] += 1
                _row["gain"] += max(
                    0.0, float(_ev.get("lawful_move") or 0.0)
                    - float(_ev.get("lawful_move_minted_included")
                            or 0.0))
            _UIf.vprint(1,
                        f"  [pav-builder]   apply REFUSALS: "
                        f"{len(_refusals)} event(s) in the verify-and-relax "
                        f"loop.")
            for _k in sorted(_by_kind, key=lambda z: (z[0] or "", z[1] or "",
                                                      z[2] or "")):
                _row = _by_kind[_k]
                _UIf.vprint(1,
                            f"  [pav-builder]     {_k[0]} {_k[1]}/{_k[2]}: "
                            f"{_row['n']} event(s), {_row['req']:.2f} m "
                            f"requested; binder_minted={_row['minted']} "
                            f"event(s); Σ(lawful_move − "
                            f"lawful_move_minted_included) = "
                            f"{_row['gain']:.2f} m (a difference of two "
                            f"BOUNDS, not an observed move).")
            # The retired bins, joined to the refusal that retired them.
            for _key in sorted(_retired, key=lambda k: (k[0], k[1])):
                _rec = _retired[_key]
                _hits = [e for e in _refusals
                         if e.get("ref") == _rec["ref"]
                         and abs(float(e.get("target_t") or -9.0)
                                 - float(_rec["t"])) < 1e-9]
                if not _hits:
                    continue
                _h = _hits[-1]
                _UIf.vprint(1,
                            f"  [pav-builder]     WHY {_rec['ref']} bin "
                            f"{_rec['bin']} (t={_rec['t']:.4f}): "
                            f"{len(_hits)} refusal(s), last "
                            f"{_h.get('kind')}/{_h.get('action')} excess "
                            f"{float(_h.get('excess') or 0.0):.5f} at "
                            f"t={float(_h.get('midpoint_t') or 0.0):.4f}; "
                            f"asked {float(_h.get('requested_move') or 0.0):.3f} m, "
                            f"relax allowed "
                            f"{float(_h.get('lawful_move') or 0.0):.3f} m "
                            f"(minted-inclusive bound "
                            f"{float(_h.get('lawful_move_minted_included') or 0.0):.3f} m; "
                            f"binder minted="
                            f"{bool(_h.get('binding_was_minted'))}, "
                            f"{int(_h.get('n_minted_anchors') or 0)} minted "
                            f"anchor(s) on the profile).")
        _flex_stage = "complete"
    except Exception as _flex_exc:                     # pragma: no cover
        # LOUD, never silent: the reader must be able to tell a report
        # that ENDED from a report that was CUT OFF.
        _msg = (f"  [pav-builder] {icao}: runway flex report TRUNCATED "
                f"after stage '{_flex_stage}' "
                f"({type(_flex_exc).__name__}: {_flex_exc}) — the "
                f"remaining flex numbers were NOT printed.")
        try:
            import O4_UI_Utils as _UIt
            _UIt.vprint(1, _msg)
        except Exception:
            print(_msg)
    return n_demands


# ══ PROBE A — THE MOVER LEDGER (docs/specs/taut-string-probe-spec.md §1)
# Gate ``O4_STRING_MOVER_LEDGER`` (default "0").  A MEASUREMENT
# INSTRUMENT: it reads ``elev`` and copies; it never writes ``elev``, never
# mutates ``u_spine_adj`` / ``_hard_cat`` / ``bucket_to_idx`` / any set the
# solver iterates.  NO MODULE-GLOBAL STATE (spec §0.2 —
# ``feasibility_project`` is re-entered from three call sites): all of it
# lives in ONE dict, created by ``solve_route_profile``, passed DOWN as
# the ``probe_out`` out-parameter and handed ACROSS to the two
# ``final_grade_projection`` passes on the layout — the same handoff
# ``_taut_rod_key_edges`` / ``_crown_drop_key`` already use.
#
# The ledger answers "which stage LAST moved this watched node", by diffing
# a watch set at each ``elev``-writing stage boundary and re-stamping the
# label wherever the value changed since the PREVIOUS boundary.  Exact
# float ``!=`` (spec §1: pointer-identical unless written).
_MOVER_LABEL_LEDGER = (
    "unchanged_since_freeze",   # phase A's frozen value, never re-written
    "svc_dem_follow",           # stage G, apply_service_road_dem_follow
    "proj_shape.blend",         # the :1447 projection, envelope+break blend
    "proj_shape.sweep",         # the :1447 projection, sweeps
    "proj_u.blend",             # the :1452 projection, envelope+break blend
    "proj_u.sweep",             # the :1452 projection, sweeps
)
# The pin-drag TAIL (spec §1 extension): separation (i) proved the G2 drag
# is real and BROAD, so it accrues after the conflict ledger is computed.
# These boundaries carry the same watch set to the emit copy.
_MOVER_LABEL_TAIL = (
    "fp8",                      # the body yield (stamped OUTSIDE _t_fp8)
    "mouth_relax",              # the mouth verify-and-relax re-projection
    "ring_fairing",             # _fair_ring_edges
    "gap_spine_fairing",        # _fair_gap_spine_chains
)
# ── THE FINAL-PROJECTION TAIL (spec amendment, 2026-08-01) ──────────────
# MEASURED at HECA before the amendment: every one of the 3,790 kept pins
# reads |Δz| = 0.0000 at the emit copy — nothing inside
# ``solve_route_profile`` moves a pin after phase A.  The drag is
# downstream, in the TWO ``final_grade_projection`` passes (mid, gate
# ``O4_FINAL_PROJECTION_MID``; late, ``O4_FINAL_PROJECTION_LATE``), where
# pins are NOT Dirichlet and nothing holds them.  Each pass gets two
# boundaries: ``.entry`` (everything between the previous boundary and
# this pass starting — the pipeline work in between) and the bare label
# (what the pass ITSELF did).  Both are read in the UNCROWNED frame z′:
# the pass adds c on entry and subtracts it just before its writeback, so
# the exit boundary is taken BEFORE the crown transform back, and the
# emitted value is ``z′ − crown`` (both are recorded per pin).
_MOVER_LABEL_FINAL = (
    "final_proj_1.entry",
    "final_proj_1",
    "final_proj_2.entry",
    "final_proj_2",
)
MOVER_LABELS = (_MOVER_LABEL_LEDGER + _MOVER_LABEL_TAIL
                + _MOVER_LABEL_FINAL)


def _mover_ledger_new(watch, elev, svc_moved=()):
    """Open a mover ledger over ``watch`` at the current ``elev``.

    Every watched node starts at ``unchanged_since_freeze``; stage G is
    stamped without a diff from the moved set it already returns.
    """
    watch = {int(i) for i in watch}
    label = dict.fromkeys(watch, "unchanged_since_freeze")
    for i in (svc_moved or ()):
        if i in label:
            label[i] = "svc_dem_follow"
    return {"watch": watch,
            "label": label,
            "prev": {i: elev[i] for i in watch}}


def _mover_snapshot(ledger, elev):
    """The watch-set slice of ``elev`` (the caller-side boundary copy)."""
    return {i: elev[i] for i in ledger["watch"]}


def _mover_stamp(ledger, snap, label):
    """Diff ``snap`` against the previous boundary; stamp what moved."""
    if ledger is None or not snap:
        return 0
    prev = ledger["prev"]
    lab = ledger["label"]
    n_moved = 0
    for i, z in snap.items():
        if z != prev[i]:
            lab[i] = label
            prev[i] = z
            n_moved += 1
    return n_moved


def _mover_stamp_probe(ledger, label):
    """Stamp the ``post_blend`` copy ``feasibility_project`` left behind.

    Consumed (popped) so a call that returned early — no edges, no
    snapshot — can never be attributed a stale boundary.
    """
    if ledger is None:
        return 0
    return _mover_stamp(ledger, ledger.pop("post_blend", None), label)


def _mover_rebind(ledger, key_to_idx, n):
    """Re-resolve the watch set into a REBUILT node space, by key.

    ``final_grade_projection`` rebuilds its node list, so a solve INDEX
    means nothing there (the rod-key lesson: an index carry does not
    survive a rebuild).  The ledger carries the canonical key of every
    watched node, taken from the rod export's reverse map; this resolves
    those keys through the new pass's ``bucket_to_idx``.  A watched node
    the rebuild no longer contains (emit decimation deletes strung
    collinear vertices) simply drops out of the map — it is never
    silently attributed to the pass.
    """
    out = {}
    for i, key in (ledger.get("key_of") or {}).items():
        j = key_to_idx.get(key)
        if j is not None and j < n:
            out[i] = j
    return out


def _mover_stamp_rebound(ledger, elev, idx_map, label):
    """Diff-and-stamp a boundary inside a rebuilt node space."""
    if ledger is None or not idx_map:
        return 0
    return _mover_stamp(ledger, {i: elev[j] for i, j in idx_map.items()},
                        label)


def _law_edge_stream(shape_constraints):
    """The within-shape law as SYMMETRIC ``(i, j, budget)`` triples.

    Round-2 §1a.  A ``shape_constraints`` edge is either a symmetric
    3-tuple ``(i, j, budget)`` — ``budget`` ``None``/negative meaning
    UNREGULATED, no law, skipped — or a Stage-B0 INTERVAL 4-tuple
    ``(i, j, lo, hi)`` (``one_solve.shape_constraints_edges`` names that
    contract; this is its only other consumer).

    The grip judges ``|z_i − z_j|`` against one symmetric budget, so an
    interval edge takes the SAME conservative surrogate
    ``one_solve._build_adjacency`` uses: ``max(|lo|, |hi|)``, the loosest
    symmetric slab containing the interval — so the grip can never
    release a pin an asymmetric law would have permitted — and a
    one-sided interval imposes no symmetric bound and is skipped, exactly
    as there.  A generator: the caller streams the solve's OWN
    constraints object in one pass, never a second build.
    """
    from .one_solve import shape_constraints_edges
    for edge in shape_constraints_edges(shape_constraints):
        if len(edge) >= 4:
            lo, hi = edge[2], edge[3]
            if lo is None or hi is None:
                continue
            bud = max(abs(lo), abs(hi))
        else:
            bud = edge[2]
            if bud is None or bud < 0:
                continue
        yield edge[0], edge[1], float(bud)


def is_mover_label(label) -> bool:
    """True for any label the mover ledger may legitimately stamp.

    The base set is closed (``MOVER_LABELS``).  The ``.entry`` windows
    additionally admit ONE sub-boundary level — ``final_proj_<N>.entry.
    <stage>`` — whose stage names are the PIPELINE's own seam names
    (round-2 §2).  They are not enumerated here on purpose: enumerating
    them would mint a second copy of the pipeline's stage list that could
    silently drift from the one the pipeline actually walks.
    """
    if label in MOVER_LABELS:
        return True
    if not isinstance(label, str):
        return False
    return any(label.startswith(base + ".") and len(label) > len(base) + 1
               for base in _MOVER_LABEL_FINAL if base.endswith(".entry"))


#: Sentinel for "this attribute did not exist before the probe ran".
_PROBE_ABSENT = object()

#: Every layout attribute the ``_build_node_list`` / ``_seed_elevations``
#: readback pair PUBLISHES in its own node-index space.  A probe that
#: re-runs that pair at a pipeline seam must restore all of them: the
#: indices it would leave behind name nodes in the PROBE's node space,
#: which downstream production readers (``grade_graph`` seam pins, the
#: solve's yield sets, the terrain-host threshold) would then read as
#: their own.  ``_final_projection_snapshot`` already fences the first
#: three; the two index publications are ``_build_node_list``'s.
_PROBE_PUBLISHED_ATTRS = ("_seam_pin_idx", "_seam_pin_ll",
                          "_seam_pin_residuals", "_eat_anchor_pin_idx",
                          "_eat_anchor_pin_prev", "_eat_anchor_pin_rect",
                          "_object_bridge_pin_idx",
                          "_object_bridge_pin_prev",
                          "_terrain_host_yield_first_index",
                          "_adjacent_ground_first_zone_index")


def mover_stage_boundary(layout, stage: str) -> int:
    """Sub-boundary INSIDE the ``final_proj_N.entry`` window (round-2 §2).

    Round 1 left SPJC with a 51-pin G2 tail (max 4.74 m) attributed to
    ``final_proj_1.entry`` — a window that spans EVERY post-solve pipeline
    stage at once (the solve's writeback through to the first final pass),
    so the label names no writer.  This splits it at the seams the
    pipeline ALREADY marks, labelling each ``final_proj_<N>.entry.
    <stage>``; the residual keeps the bare ``.entry`` label, so nothing is
    attributed by construction.

    REPORT-ONLY, and active only when the ledger exists on the layout —
    i.e. under ``O4_STRING_MOVER_LEDGER=1``, which is the only thing that
    puts it there.  Gate off ⇒ one ``getattr``.  Nothing is written but
    the ledger's own labels.

    FRAME: the watch set crosses into each stage's node space by CANONICAL
    KEY (``_mover_rebind``), exactly as the ``.entry`` boundary does, and
    the values are read in the same UNCROWNED z' frame — the layout value
    plus that node's crown drop, mirroring ``final_grade_projection``'s
    crown-in.  ``extend_field_to_new_ring_nodes`` is NOT called (a probe
    mutates nothing); every watched key predates the solve's writeback and
    therefore already carries its drop.

    PURITY (probe-spec §1x, round 6).  "Report-only" is a property of the
    WHOLE call, not of the ledger helpers: round 6 measured this probe
    moving SPJC's emitted surface (+1 node, 86 altitudes, |dz| <= 0.21 m)
    because the node-list rebuild interned through the MUTATING
    ``canonical_points.get_or_add`` — one extra 0.5 m bucket changes which
    later vertices weld, and the registry feeds the emit consensus.  Both
    halves of the readback therefore run ``readonly=True`` (get-without-
    add; a watched key whose bucket is unclaimed at this seam is counted
    in ``n_unresolved``, never inserted), and every layout attribute the
    pair PUBLISHES in its own node-index space is snapshotted and
    restored — the same fence ``_final_projection_snapshot`` uses, plus
    the two ``_build_node_list`` index publications.  Net effect: the
    registry, the layout and the emitted body are byte-identical with the
    gate on and off.
    """
    ledger = getattr(layout, "_string_mover_ledger", None)
    if ledger is None or not ledger.get("key_of"):
        return 0
    from auto_patch.elevation_per_surface.solver_primitives import (
        _build_node_list, _seed_elevations)
    pass_no = int(ledger.get("n_final_passes", 0)) + 1
    label = f"final_proj_{pass_no}.entry.{stage}"
    saved_pub = [(_a, getattr(layout, _a, _PROBE_ABSENT))
                 for _a in _PROBE_PUBLISHED_ATTRS]
    n_unresolved = 0
    try:
        nodes, b2i = _build_node_list(layout, readonly=True)
        if not nodes:
            return 0
        elev, _bh, _hi = _seed_elevations(layout, nodes, b2i, readonly=True)
        n = len(elev)
        crown_by_key = getattr(layout, "_crown_drop_key", None) or {}
        if crown_by_key:
            for _key, _i in b2i.items():
                _c = crown_by_key.get(_key)
                if _c and _i < n:
                    elev[_i] = elev[_i] + _c
        idx_map = _mover_rebind(ledger, b2i, n)
        n_unresolved = len(ledger.get("key_of") or {}) - len(idx_map)
        # MAGNITUDES, not just a count: a boundary that reports "every
        # watched node moved" is indistinguishable from a frame artefact
        # until the sizes are on the table (the ledger's ``!=`` counts a
        # 1e-16 round-trip as a move).  Taken BEFORE the stamp, which
        # rewrites ``prev``.
        _prev = ledger["prev"]
        _dz = sorted(abs(elev[j] - _prev[i]) for i, j in idx_map.items()
                     if elev[j] != _prev[i])
        moved = _mover_stamp_rebound(ledger, elev, idx_map, label)
    except Exception as exc:                               # pragma: no cover
        # A measurement instrument never breaks a build — but it never
        # fails silently either.
        ledger.setdefault("stage_boundary_errors", {})[label] = repr(exc)
        print(f"  [string-mover] stage boundary {label} skipped: {exc!r}")
        return 0
    finally:
        # PURITY FENCE (§1x): the readback pair publishes node-index-space
        # state on the layout; a probe leaves none of it behind.
        for _a, _saved in saved_pub:
            if _saved is _PROBE_ABSENT:
                try:
                    delattr(layout, _a)
                except AttributeError:
                    pass
            else:
                setattr(layout, _a, _saved)
    ledger.setdefault("stage_moves", {})[label] = {
        "n_moved": moved,
        "n_watched_here": len(idx_map),
        "n_unresolved": n_unresolved,
        "median_abs_dz_m": (_dz[len(_dz) // 2] if len(_dz) % 2 else
                            0.5 * (_dz[len(_dz) // 2 - 1]
                                   + _dz[len(_dz) // 2])) if _dz else None,
        "max_abs_dz_m": (_dz[-1] if _dz else None),
        "n_over_0p01_m": sum(1 for v in _dz if v > 0.01),
    }
    summary = ledger.get("summary")
    if summary is not None:
        summary["entry_window_moves"] = ledger["stage_moves"]
    return moved


def _string_pin_hold_indexes(layout, key_to_idx, n):
    """Resolve the solve's exported kept-pin KEYS into a rebuilt node space.

    Fix arm §3.  ``final_grade_projection`` rebuilds its node list, so the
    kept pin set crosses by CANONICAL KEY — the same rule the mover
    ledger's watch set already follows (``_mover_rebind``), and never an
    index carry.  A pin whose key the rebuild no longer contains (emit
    decimation deletes strung collinear vertices) simply drops out: it is
    never resolved onto some other node.  Returns the index set; empty
    when the solve exported nothing (gate off there).
    """
    out: set = set()
    for key in (getattr(layout, "_string_pin_keys", None) or ()):
        i = key_to_idx.get(key)
        if i is not None and i < n:
            out.add(i)
    return out


# ══════════════════════════════════════════════════════════════════════
# ROUND 4 §1 — PINS LIVE ON THE FROZEN GRAPH
# ══════════════════════════════════════════════════════════════════════
# ★ A PIN THE PHASE-A SOLVE STRUCTURALLY CANNOT HOLD IS NOT A PIN
# (Fable ruling, round-4 spec §1).  ``_solve_spine_profile`` writes EVERY
# kept pin into ``elev`` and joins it to ``anchors`` (:6500-6505), but the
# set it returns as FROZEN — the set the caller stamps into ``base_hard``
# (:1415-1417) — is ``{k for k in spine_adj if k < len(elev)}`` (:6506,
# :6654).  A pin on a node with no ``u_spine_adj`` entry is therefore
# written, immediately overwritten by phase B (nothing froze it), and then
# HELD AT PHASE B's VALUE by Ruling 54.  Round 3 measured the separation
# exactly: 32/32 off-spine kept pins moved (0.46-6.16 m), 1,620/1,620
# on-spine pins held to 0.000000 m, in both arms.
#
# So pins are restricted to the freeze-covered graph.  Off-graph targets
# are LEDGERED, never applied.  The CHORD is untouched — the string still
# exists; it simply does not pin what the phase-A solve does not govern.
def _pins_on_frozen_graph(kept, spine_adj, n):
    """Split the grip's kept pin set on the phase-A freeze.

    Returns ``(applied, off_graph)``.  ``applied`` is exactly the pins the
    phase-A solve both applies AND freezes — membership in ``spine_adj``
    (the freeze's own key set) with an in-range index (its ``k < len(elev)``
    clause, ``n == len(elev)`` at the call site).  Everything else is
    ``off_graph``: a target the solve cannot hold.
    """
    applied: dict = {}
    off_graph: dict = {}
    for v, z in kept.items():
        tgt = applied if (v in spine_adj and 0 <= v < n) else off_graph
        tgt[v] = z
    return applied, off_graph


def _stamp_pin_ledger(pin_rows, applied, off_graph, spine_adj, n):
    """Stamp each pin ledger row with its disposition and ``pin_frozen``.

    ``pin_frozen`` is the ONE BIT the round-4 reading turns on: true iff
    the vertex is in the set the phase-A solve freezes — a pure function of
    the vertex, so it is stamped on released rows too.  Dispositions:
    ``kept`` (applied), ``off_graph`` (kept by the grip, off the frozen
    graph), ``released`` (the grip's own law releases).  Returns
    ``(off_graph_string_ids, n_targets_off_graph)`` — the second is the
    row count with ``pin_frozen`` false, i.e. EVERY off-graph target
    including the ones the grip already released.  Two different
    populations, both named: the disposition split is over KEPT pins
    (§1's ``off_graph``), the bit is over TARGETS.
    """
    strings: set = set()
    n_off_targets = 0
    for row in pin_rows:
        v = row["vertex"]
        row["pin_frozen"] = bool(v in spine_adj and 0 <= v < n)
        if not row["pin_frozen"]:
            n_off_targets += 1
        if v in applied:
            row["grip"] = "kept"
        elif v in off_graph:
            row["grip"] = "off_graph"
            if row.get("string") is not None:
                strings.add(row["string"])
        else:
            row["grip"] = "released"
    return sorted(strings), n_off_targets


def _mover_publish(ledger, layout, elev=None, idx_map=None, crown_of=None,
                   pass_no=None):
    """Refresh the pin-drag delivery and re-write the string sidecar.

    Idempotent and last-call-wins, exactly like ``write_string_sidecar``
    itself.  ``elev`` / ``idx_map`` / ``crown_of`` are supplied by a
    final-projection boundary so each pin row also records the value that
    pass ended on (uncrowned z′) and the crown drop that turns it into
    the emitted number — the amendment's "the last boundary must equal
    the values the .osm will spell (quantisation excluded)".
    """
    if ledger is None:
        return
    rows = ledger.get("pin_rows") or ()
    label = ledger["label"]
    for row in rows:
        v = row["vertex"]
        row["last_writer"] = label.get(v)
        if elev is not None and idx_map is not None:
            j = idx_map.get(v)
            if j is None:
                row[f"z_final_proj_{pass_no}"] = None
                continue
            z = float(elev[j])
            row[f"z_final_proj_{pass_no}"] = z
            row["z_emit_uncrowned"] = z
            row["crown_drop_m"] = float((crown_of or {}).get(j, 0.0))
            row["z_emitted"] = z - row["crown_drop_m"]
    summary = ledger.get("summary")
    if summary is None:
        return

    def _median(vals):
        vals.sort()
        mid = len(vals) // 2
        return (vals[mid] if len(vals) % 2
                else 0.5 * (vals[mid - 1] + vals[mid]))

    buckets: dict = {}
    for row in rows:
        buckets.setdefault(row["last_writer"], []).append(row)
    counts = {}
    for lab, brows in buckets.items():
        # The spec's Δ (z at the solve's emit copy − pin z) AND — once a
        # final pass has run — the drag all the way to the EMITTED value.
        # The first is 0 for every pin (measured), so the second is the
        # one that carries the signal; both ship, neither replaces the
        # other.
        emitted = [abs(r["z_emitted"] - r["pin_z"]) for r in brows
                   if r.get("z_emitted") is not None]
        counts[lab] = {
            "n": len(brows),
            "median_abs_dz_m": _median(
                [abs(r["z_at_emit_copy"] - r["pin_z"]) for r in brows]),
            "median_abs_dz_emitted_m": (_median(emitted) if emitted
                                        else None),
            "max_abs_dz_emitted_m": (max(emitted) if emitted else None)}
    summary["pin_drag_counts"] = counts
    from .taut_string import write_string_sidecar as _ws
    _ws(layout)                                   # last call wins


def _route_pavement_roles():
    """The ROUTE-PAVEMENT role set, derived from the layout's OWN registry.

    Spec ``route-metric-envelope`` §2: "Role membership comes from the
    layout's own shape registry at solve time — never fresh string
    literals (blast.py role-literal hazard)."  So the two tables decide:

    * ``config.ROLE_GRADE_LIMITS`` — a role whose within-shape limit is
      ``None`` has no grade law of its own; it is a terrain TRACE
      (``graded_strip``, ``retaining_wall``, ``runway_clearance``,
      ``taxiway_clearance``, ``ols_cut``, ``boundary``), never a route.
    * ``solver_primitives.PAVEMENT_ROLES`` — the roles the solver grades
      as pavement.  The bridge plates (``bridge_trench`` /
      ``bridge_causeway``) carry no ``ROLE_GRADE_LIMITS`` entry yet ARE
      pavement a route crosses, so the union keeps them.
    * ``groundside_pavement`` HAS a limit (4 %) and is explicitly
      withdrawn: it is groundside, and groundside is never a feasibility
      witness for airside (owner ruling 2026-07-30, `groundside terrace
      law`; the existing ``witness_limited`` clause bounds it to the
      Part-C mouth allowance, which this set does not disturb).

    Returns ``frozenset`` of role values (the registry's own objects)."""
    from auto_patch.config import ROLE_GRADE_LIMITS
    from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
    from auto_patch.elevation_per_surface.solver_primitives import (
        PAVEMENT_ROLES)
    graded = {r for r, lim in ROLE_GRADE_LIMITS.items() if lim is not None}
    return frozenset((graded | set(PAVEMENT_ROLES))
                     - {ROLE_GROUNDSIDE_PAVEMENT})


def _node_role_sets(layout, key_to_idx, n):
    """``{node_index: frozenset(roles)}`` from the layout's shape registry.

    READ-ONLY on the canonical-point registry (``find_nearest``, never
    ``get_or_add``): a role scan must not mint canonical points.  Ring
    vertices only — the same vertices ``_build_shape_constraints`` maps —
    so a node interior to no ring simply carries no role and is reported
    as role-unmatched rather than silently classified."""
    cps = layout.canonical_points
    tol = cps.tol_m
    out: dict = {}
    for s in layout.shapes:
        role = getattr(s, "role", None)
        poly = getattr(s, "polygon", None)
        if role is None or poly is None or poly.is_empty:
            continue
        try:
            rings = ([poly.exterior] if poly.geom_type == "Polygon"
                     else [g.exterior for g in poly.geoms])
        except Exception:                              # pragma: no cover
            continue
        for ring in rings:
            for (x, y) in ring.coords:
                k = cps.find_nearest(float(x), float(y), tol)
                if k is None:
                    continue
                i = key_to_idx.get(k)
                if i is None or i >= n:
                    continue
                prev = out.get(i)
                out[i] = (frozenset((role,)) if prev is None
                          else (prev | {role}))
    return out


def _route_witness_admission(layout, key_to_idx, n):
    """Build the role scan ONCE per pass and return
    ``(roles, route_roles, excluded_by_role)``.

    ``excluded_by_role`` is every node whose roles are ALL non-route — it
    does not depend on any particular ``hard`` set, so one scan serves
    every ``feasibility_project`` call of the pass (``feasibility_project``
    intersects with its own hard set).  Single-pass principle: the O(ring
    vertices) scan is paid once, not once per projection."""
    roles = _node_role_sets(layout, key_to_idx, n)
    route_roles = _route_pavement_roles()
    excluded = {i for i, rs in roles.items() if not (rs & route_roles)}
    return roles, route_roles, excluded


def adj_without_pairs(adj, pairs):
    """``adj`` with every edge whose endpoint pair is in ``pairs`` dropped.

    ONE filter, two readers: the AIRSIDE VIEW of the one graph (airside
    authorities may not ride service edges — ``REACH_NO_SERVICE_SPINES``)
    and the ``O4_PROBE_NO_SERVICE_EDGES`` gate, which withholds the same
    edge set from every consumer.  Empty ``pairs`` ⇒ the SAME object back,
    so the un-gated path is byte-inert by identity, not by comparison.
    """
    if not pairs:
        return adj
    out: dict = {}
    for i, lst in adj.items():
        keep = [(j, b) for (j, b) in lst
                if (min(i, j), max(i, j)) not in pairs]
        if keep:
            out[i] = keep
    return out


def _unified_entries(u_edges, pair_stage, where, family=None):
    """The unified graph as STAGE-TAGGED constraint entries (S1b).

    ONE bare ``{"edges": u_edges}`` entry used to carry EVERY shape's
    within-shape law pairs into EVERY projection with no role and no
    family — which is why ``_withhold_road_pair_law`` (keyed on
    ``sc["role"]``) could never move a service_road pair out of the
    airside pass, and why a groundside lot's pairs on airside-claimed
    nodes were enforced against airside rows (tmp/s1_attribution.md
    couplings 3 and 6).  The split is by MINT-TIME stage: the shape that
    minted each edge, recorded in ``grade_graph.UnifiedGraph.edge_stage``
    and in the appending constructors' own ``stage_out`` maps.  An edge
    missing from the map RAISES — a partition that guessed would be the
    same blindness in a new spelling.
    """
    from auto_patch.solve_stage import (split_edges_by_stage, STAGE_A,
                                        STAGE_B, STAGE_KEY)
    a_edges, b_edges = split_edges_by_stage(u_edges, pair_stage, where)
    out = []
    for edges, stage in ((a_edges, STAGE_A), (b_edges, STAGE_B)):
        if not edges:
            continue
        entry = {"edges": edges, STAGE_KEY: stage}
        if family is not None:
            entry["family"] = family
        out.append(entry)
    return out


def _receiver_nodes_from_roles(roles, stage_b_nodes=()):
    """THE RECEIVER SET of the projection partition — nodes whose EVERY
    role is groundside (``layout.GROUNDSIDE_ROLES``), plus the
    ROLE-LESS stage-B construct nodes named in ``stage_b_nodes``.

    Same role scan every projection already pays for
    (:func:`_route_witness_admission`), read a second way: the witness
    clause asks "may this anchor SEED the airside envelope", this asks
    "is this node a groundside RECEIVER".  One scan, two consumers.

    A node shared with any non-groundside ring — a service-road MOUTH on
    an apron edge above all — is NOT a receiver: airside wins its seat
    (RULINGS 2026-08-06), so it is frozen data for the groundside pass
    rather than one of its variables.  A role-unmatched node (no ring
    vertex resolved to it) is likewise not a receiver: the conservative
    side, since a wrong receiver would FREEZE an airside node out of its
    own pass.

    ``stage_b_nodes`` (S1d) is the exception that proves that last rule:
    a gap-fill drainage spine tagged stage B by its ENCLOSURE HOST
    (``solver_primitives.gap_spine_stage_b_nodes``) is a groundside
    VARIABLE with no ring role at all — role-unmatched by construction,
    since a spine vertex is an interior point on nobody's ring.  Without
    it a correctly stage-B-tagged spine would be frozen on both sides
    (out of the airside pass by its tag, out of this pass by the role
    scan) and its law silently deleted.  Default empty ⇒ every existing
    one-argument call is unchanged."""
    from auto_patch.layout import GROUNDSIDE_ROLES
    recv = {i for i, rs in roles.items() if rs and rs <= GROUNDSIDE_ROLES}
    # THE GUARD IS LOAD-BEARING, not defensive.  A node that DID resolve
    # to a ring role is adjudicated by the role scan ALONE — airside wins
    # a shared seat — so a spine index that collides with a roled node
    # (a rebuilt node space, a spine vertex welded onto a ring by a later
    # conformance pass) is never admitted here.  A wrong receiver would
    # FREEZE AN AIRSIDE NODE OUT OF ITS OWN PASS, which is the failure
    # this whole partition exists to prevent.
    recv.update(i for i in stage_b_nodes if not roles.get(i))
    return recv


def _non_route_witness_nodes(roles, route_roles, hard, n, provenance=None):
    """The hard anchors withdrawn from the airside envelope seed set.

    Spec ``route-metric-envelope`` §2.  Three populations, all reported:

    * ROUTE-ROLE anchors — at least one role in
      :func:`_route_pavement_roles` — keep witnessing.
    * NON-ROUTE anchors — they have roles, and every one of them is
      outside that set — are withdrawn.  These are the strip/clearance/
      boundary traces the owner's directive names.
    * ROLE-UNMATCHED anchors — no ring vertex of any shape resolved to
      them (the counterfactual's 889).  The spec forbids dropping these
      blind, so they are CLASSIFIED from the solver's own provenance map
      (``provenance``: ``{node: class}``, the same classes the break
      forensics emits) and withdrawn ONLY when that class is itself a
      non-route authority — a terrain pin, an agreeing/torn feature weld
      or a groundside weld/pin.  Anything else (runway, pad, spine,
      service ring, seam, unclassified) keeps its witness role: the
      conservative side, since an unwarranted withdrawal LOOSENS the
      envelope and can hide a real contradiction.

    Returns ``(excluded_set, report_dict)``."""
    from collections import Counter
    # Provenance classes that are NOT route authorities.  Names come from
    # the break-forensics class map built by the callers (one author).
    NON_ROUTE_PROVENANCE = frozenset(
        ("terrain_pin", "feature_weld", "gs_weld", "gs_pin",
         "torn_feature_weld"))
    excluded: set = set()
    rep = {"hard": 0, "route_role": 0, "non_route_role": 0,
           "role_unmatched": 0, "unmatched_withdrawn": 0,
           "non_route_roles": Counter(), "unmatched_classes": Counter()}
    for a in hard:
        if a >= n:
            continue
        rep["hard"] += 1
        rs = roles.get(a)
        if rs is None:
            rep["role_unmatched"] += 1
            cls = (provenance or {}).get(a, "<unclassified>")
            rep["unmatched_classes"][cls] += 1
            if cls in NON_ROUTE_PROVENANCE:
                rep["unmatched_withdrawn"] += 1
                excluded.add(a)
            continue
        if rs & route_roles:
            rep["route_role"] += 1
            continue
        rep["non_route_role"] += 1
        rep["non_route_roles"][tuple(sorted(str(r) for r in rs))] += 1
        excluded.add(a)
    return excluded, rep


def _report_witness_admission(icao, label, rep):
    """One line per pass naming the split (spec §2: "report their split")."""
    print(f"    [route-metric] {icao} {label}: {rep['hard']} hard anchor(s) — "
          f"{rep['route_role']} route-role (seed), "
          f"{rep['non_route_role']} non-route-role (withdrawn), "
          f"{rep['role_unmatched']} role-unmatched "
          f"({rep['unmatched_withdrawn']} of them withdrawn by provenance)")
    if rep["non_route_roles"]:
        print(f"    [route-metric]   withdrawn role sets: "
              f"{dict(rep['non_route_roles'].most_common(8))}")
    if rep["unmatched_classes"]:
        print(f"    [route-metric]   role-unmatched provenance: "
              f"{dict(rep['unmatched_classes'].most_common(10))}")


# ══ SPINE-FREEZE ROUND — YIELD-HARD MEMBERSHIP FOR PHASE-A SPINE VALUES ══
# (``docs/specs/spine-freeze-round-spec.md``.  STANDING LAW — the
# ``O4_SPINE_YIELD_HARD`` gate was deleted in the build-complete-then-debug
# round; there is no arm that re-freezes a phase-A estimate.)
#
# THE DEFECT.  ``_solve_spine_profile`` certifies the phase-A spine on its
# OWN 1.5-4.8 k-edge graph, and the freeze below stamps those values into
# ``base_hard`` — IMMOVABLE — for every downstream projection, whose graphs
# carry 64-272 k edges.  Measured (``carrier_attrib/DOSSIER.md`` §9): 85 %
# of HEAZ's and 84 % of HECA's violated anchors are frozen spine nodes,
# median DEM+0.53 / +0.77 m.  A value certified on a subgraph is an
# ESTIMATE against the full law, and ``feasibility-is-guaranteed`` says an
# estimate that contradicts the law is a defect to ATTRIBUTE, never an
# answer.  (DOSSIER §1: HEAZ node 2631 was frozen 1.697 m BELOW the minimum
# the runway 18/36 profile permits, with 11 m of its own band above it.)
#
# THE MECHANISM — RULING 54's MEMBERSHIP, NOW PLAIN.  Ruling 54 held the
# kept string pins by SET MEMBERSHIP in a projection's ``hard``; the
# complementary membership is simply NOT being in it.  A yield-hard spine
# node therefore enters every downstream projection FREE: it settles
# wherever that graph's caps, boxes and envelope admit.  (Until the
# build-complete-then-debug round it was additionally held by a §7
# reference rod — a least-displacement pull toward the phase-A value.
# That channel is retired: a phase-A estimate is not an authority the
# full-graph law has to be talked out of.)  Every movement off the
# phase-A value is still reported, write-only, with its binding
# constraint — ``_spine_yield_movement_report`` below.
#
# THE PRESERVED SET (stays ``base_hard``; law, not phase-A estimate):
# ``truth_hard`` — everything hard BEFORE the freeze, i.e. the
# ``_hard_cat`` classes ``seed_rwy_seam`` (runway/CIFP profile values and
# tile-seam DEM pins), ``rwy_join``, ``rwy_flexed``, ``seat_on_spine``,
# ``seam_spine_anchor`` (the ``pad_detached_dem`` class is RETIRED —
# item 3(b) replaced the detached-pad DEM pins with a law seat) — plus
# ``runway_nodes``,
# ``building_seats``, ``G.runway_anchor`` and ``layout._seam_pin_idx``
# (the last two are subsets of ``truth_hard``; the spec names them, so
# they are enumerated rather than implied).
#
# SCOPE.  Phase B (``one_profile_solve``) is a body FILL, not a
# projection: it keeps the freeze, so the body still twists to meet the
# spine.  Every PROJECTION downstream of the freeze runs the yield.
#
# ── SEAT HARD-STAMP GUARD — STANDING LAW ─────────────────────────────
# (seed-fix round §4; former gate ``O4_SEAT_STAMP_GUARD``, retired
# 2026-08-05 under RULINGS "BUILD-COMPLETE-THEN-DEBUG".)
#
# THE LAW.  A ``seat_on_spine`` value that CAP-CONTRADICTS a hard
# runway/seam anchor within its own route budget does not become
# ``base_hard``: it enters YIELD-HARD, the same Ruling-54 membership the
# spine-freeze fix uses — held at its value wherever the full graph's law
# permits, movable only where the law demands, every movement reported.
#
# THE DEFECT IT CLOSES.  ``feasibility-is-guaranteed`` says a real airport
# has a lawful surface, so two IMMOVABLE values that cannot both hold are a
# law defect to attribute, never an answer.  Stamping a seat immovable
# against a runway truth 0.19 m of budget away manufactures exactly that
# pair, and nothing downstream can undo it (the projection can only report
# it — measured at HECA: 3983 sweeps burned, residual 4.766 m, never
# certified).  The guard needs the hard-anchor envelope to adjudicate
# against; where no envelope exists there is no anchor to contradict.


# ══ ADJACENT-GROUND INGESTION — THE CONSUMPTION SIDE ═══════════════════
# (INGEST lane hand-off, 2026-08-05.  Supply:
# ``adjacent_ground.build_zone_constraint_table`` publishes
# ``layout.adjacent_ground_zone_boxes``, one record per graded band node.
# Contract, verbatim from the supply docstring::
#
#     z[node] - ((1-t)*z[foot.a] + t*z[foot.b]) in [floor_off, ceil_off]
#
# seeded at ``dem_seed``; ``foot.a``/``foot.b`` are ring vertices of
# ``shape_id`` — variables the solve already owns.)
#
# ── THE BOX WAS A SECOND AUTHORITY, AND IT IS DELETED ─────────────────
# (cycle-5 solve-certification spec, fix 1.  The attribution dossier's
# decisive measurement is quoted at the call site.)
#
# The argument this block used to make: the datum is a LERP of two
# variables, which the pairwise projection cannot state exactly, so state
# the law as an ABSOLUTE per-node interval instead —
#
#     z[node] in [D + floor_off, D + ceil_off],  D = (1-t)*z[a] + t*z[b]
#
# — bound through ``one_solve._node_box_arrays``, clamped at seed and
# after every sweep.
#
# WHY IT WAS WRONG.  ``D`` is computed ONCE, from ``elev`` as it stands at
# fp#8's ENTRY, and then fp#8 MOVES the pavement that defines it (measured
# on the same rows: p50 2.340 m, p90 24.949 m, max 88.905 m).  A constraint
# derived from a variable, frozen as a constant, and then enforced every
# sweep — harder than the live relative law it duplicates — is not the same
# law written twice.  It is a second authority, and the frozen one wins:
# 65.6 % of over-cap zone rows sat inside the box implied by the STALE
# entry datum versus 6.7 % inside the live one.
#
# THE ONE AUTHORITY is the RELATIVE interval edge that already exists and
# is already correct: ``solver_primitives.zone_constraint_entries`` builds
# ``edges.append((i, j, floor_off, ceil_off))`` — ground ``i`` against its
# host pavement ring vertex ``j``, TWO VARIABLES, so it moves with ``j``.
# That is the ratified B2 frozen-nearest encoding (the design doc's "ONE
# two-sided envelope interval edge per zone node"), and the dossier's
# verdict on it is explicit: correct as written, nothing about the
# adjacent-ground law needs changing.  Directedness — the property the box
# was reached for — is already carried by ``interval_yield_from``, which
# makes a terrain slab move only its terrain endpoint.
#
# What survives here is the AUDIT: the identity join that used to resolve
# the box rows now only checks that every published zone row is carried by
# a relative edge, so the deletion is proven at every build instead of
# assumed.
def _zone_law_coverage(layout, bucket_to_idx, n, first_zone, edge_nodes):
    """``(stats)`` — is the RELATIVE zone law carrying every published row?

    ``edge_nodes`` — the zone-node indices that actually received a
    relative interval edge (``solver_primitives.zone_constraint_entries``).

    ``stats`` — ``(n_rows, n_resolved, n_carried, n_adopted, n_uncarried)``.
    ``n_uncarried`` is the number that MUST be zero for the box deletion to
    be lossless: a published row with no relative edge would be a zone node
    whose law nothing enforces.  It is reported, never absorbed.

    THE IDENTITY RULE the audit still has to honour, because it is law and
    not implementation: a zone node whose canonical bucket resolved to a
    PRE-EXISTING pavement / gap-spine variable (index < ``first_zone``)
    carries NO band law at all — the pavement value wins at a pavement
    node by identity, and a band law may never constrain a pavement
    variable.  Those rows are counted as ADOPTED, not as uncarried.

    (The cross-shape intersect/conflict arithmetic the box builder did
    here is gone with the box.  Two hosts' zone rows are SEPARATE solve
    variables since the 2026-08-05 zone-node identity decision, and each
    carries its own relative edge, so there is no longer a single
    variable for two corridor laws to collide on.)
    """
    rows = getattr(layout, "adjacent_ground_zone_boxes", None)
    if not rows:
        return (0, 0, 0, 0, 0)
    n_resolved = n_carried = n_adopted = n_uncarried = 0

    from ..solver_primitives import zone_node_index as _zone_idx

    for row in rows:
        # ZONE-NODE IDENTITY: this row belongs to ``shape_id``'s own
        # variable.  Resolving by bucket alone put two hosts' rows on one
        # variable.
        k = _zone_idx(layout, bucket_to_idx, row["xy"], row.get("shape_id"))
        if k is None or k >= n:
            continue
        n_resolved += 1
        if k < first_zone:
            n_adopted += 1
            continue
        if k in edge_nodes:
            n_carried += 1
        else:
            n_uncarried += 1
    return (len(rows), n_resolved, n_carried, n_adopted, n_uncarried)


def _spine_yield_membership(frozen, n, *, truth_hard, runway_nodes,
                            building_seats, runway_anchor, seam_pins,
                            seat_stamp_yield=None):
    """Split the phase-A frozen spine into ``(preserved, yield_hard)``.

    THE PRESERVED SET, ENUMERATED (the spec requires the enumeration, not
    an implication) — these are LAW, never phase-A estimates:

    * ``truth_hard`` — every node hard BEFORE the freeze, i.e. the
      ``_hard_cat`` classes ``seed_rwy_seam`` (the ``_seed_elevations``
      runway/CIFP profile values and the tile-seam DEM pins), ``rwy_join``,
      ``rwy_flexed``, ``seat_on_spine`` and ``seam_spine_anchor``
      (``pad_detached_dem`` was in this list until item 3(b) retired the
      detached-pad DEM pins in favour of a groundside law seat);
    * ``runway_nodes`` — the whole runway ring/vertex set;
    * ``building_seats`` — every seated pad / no-building-apron level;
    * ``runway_anchor`` (``G.runway_anchor``) — a subset of ``truth_hard``,
      restated because the spec names it;
    * ``seam_pins`` (``layout._seam_pin_idx``) — likewise.

    YIELD-HARD = ``{i in frozen : 0 <= i < n}`` minus that union.  The two
    are disjoint and together exhaust the in-range frozen set, so no spine
    node can fall out of both (the silent-loss shape).

    ``seat_stamp_yield`` (seed-fix round §4) — seats the hard-stamp guard
    refused to stamp because they CAP-CONTRADICT a hard runway/seam
    anchor within route budget.  ``building_seats`` is preserved
    UNCONDITIONALLY above, which would hand exactly those values back the
    immovability §4 took away; they are subtracted here.  ``truth_hard``
    cannot re-admit them — the guard never wrote their ``_hard_cat``
    class — but the subtraction is applied to the whole union so no other
    member can smuggle them back either.  Empty / ``None`` ⇒ the
    membership is byte-identical.
    """
    def _in(s):
        return {int(i) for i in (s or ()) if 0 <= int(i) < n}

    frozen_in = _in(frozen)
    preserved = (_in(truth_hard) | _in(runway_nodes) | _in(building_seats)
                 | _in(runway_anchor) | _in(seam_pins))
    preserved -= _in(seat_stamp_yield)
    return preserved, (frozen_in - preserved)


def _spine_yield_adjacency(edge_lists, want, n):
    """``{i: [(j, budget_or_interval), ...]}`` over ``want`` only.

    ONE pass over the projection's own edge lists (``single-pass-principle``
    — no second graph).  Symmetric edges arrive as ``(i, j, budget)`` and
    signed interval edges as ``(i, j, low, high)``; both are carried
    verbatim so the binding-constraint scan reports the law that actually
    bound, not a re-derived approximation.  Write-only."""
    adj: dict = {}
    for entry in (edge_lists or ()):
        for e in (entry.get("edges") or ()):
            a, b = e[0], e[1]
            if not (0 <= a < n and 0 <= b < n):
                continue
            lim = e[2] if len(e) == 3 else (e[2], e[3])
            if a in want:
                adj.setdefault(a, []).append((b, lim))
            if b in want:
                adj.setdefault(b, []).append((a, lim))
    return adj


def _spine_yield_binding(i, elev, adj):
    """The BINDING constraint at node ``i``: the incident law edge with the
    LEAST SLACK (``budget − |Δz|``, or the tighter side of an interval).

    Returns ``(neighbour, budget, dz, slack, kind)``; ``kind`` is
    ``"symmetric"`` / ``"interval"``, or ``(None, ...) / "none"`` when the
    node carries no law edge at all — which is itself a finding (a node
    that moved with nothing binding it), so it is reported, never dropped.
    """
    best = None
    for (j, lim) in adj.get(i, ()):
        d = elev[i] - elev[j]
        if isinstance(lim, tuple):
            lo, hi = lim
            slack = float("inf")
            if hi is not None:
                slack = min(slack, float(hi) - d)
            if lo is not None:
                slack = min(slack, d - float(lo))
            budget, kind = lim, "interval"
        else:
            budget, kind = float(lim), "symmetric"
            slack = budget - abs(d)
        if best is None or slack < best[3]:
            best = (int(j), budget, float(d), float(slack), kind)
    return best if best is not None else (None, None, 0.0, float("inf"),
                                          "none")


def _spine_yield_movement_report(icao, phase_a, elev, n, edge_lists,
                                 preserved, yield_idx, latlon_of=None):
    """WRITE-ONLY movement report for the spine yield (spec: "every movement
    reported — node, phase-A value, shipped value, the binding constraint").

    Rides the EXISTING forensics channel: the printed summary always, and a
    CSV next to ``O4_BREAK_FORENSICS`` when that path is set — the same
    shape ``_break_forensics_report`` already writes.  Nothing here is read
    back by the solve; ``elev`` is never written."""
    moved = [i for i in sorted(yield_idx)
             if i < n and abs(elev[i] - phase_a[i]) > 1e-9]
    adj = _spine_yield_adjacency(edge_lists, set(moved), n) if moved else {}
    rows = []
    for i in moved:
        j, budget, d, slack, kind = _spine_yield_binding(i, elev, adj)
        rows.append({
            "node": int(i),
            "z_phase_a": float(phase_a[i]),
            "z_shipped": float(elev[i]),
            "delta_m": float(elev[i] - phase_a[i]),
            "binding_neighbour": j,
            "binding_kind": kind,
            "binding_budget": budget,
            "binding_dz_m": d,
            "binding_slack_m": slack,
            "binding_neighbour_class": (
                "none" if j is None
                else "preserved_anchor" if j in preserved
                else "spine_yield" if j in yield_idx
                else "free")})
    n_mat = sum(1 for r in rows if abs(r["delta_m"]) >= 0.01)
    n_unbound = sum(1 for r in rows if r["binding_kind"] == "none")
    deltas = sorted(abs(r["delta_m"]) for r in rows)
    p50 = (deltas[len(deltas) // 2] if deltas else 0.0)
    print(f"    [spine-yield] {icao}: {len(yield_idx)} yield-hard spine "
          f"node(s), {len(rows)} moved ({n_mat} by ≥0.01 m); "
          f"|Δ| p50={p50:.4f} m max={(deltas[-1] if deltas else 0.0):.4f} m; "
          f"{n_unbound} moved with NO binding law edge")
    if rows:
        _by_class: dict = {}
        for r in rows:
            _by_class.setdefault(r["binding_neighbour_class"], 0)
            _by_class[r["binding_neighbour_class"]] += 1
        print(f"    [spine-yield]   binding neighbour classes: {_by_class}")
    path = _os.environ.get("O4_BREAK_FORENSICS")
    if not path or not rows:
        return rows
    try:
        stem, _dot, ext = str(path).rpartition(".")
        out = f"{stem}.spine_yield.{ext}" if stem else str(path)
        with open(out, "w") as fh:
            fh.write("node,lat,lon,z_phase_a,z_shipped,delta_m,"
                     "binding_neighbour,binding_neighbour_class,"
                     "binding_kind,binding_budget,binding_dz_m,"
                     "binding_slack_m\n")
            for r in rows:
                try:
                    la, lo = (latlon_of(r["node"]) if latlon_of
                              else (0.0, 0.0))
                except Exception:
                    la, lo = 0.0, 0.0
                fh.write(f"{r['node']},{la:.7f},{lo:.7f},"
                         f"{r['z_phase_a']:.4f},{r['z_shipped']:.4f},"
                         f"{r['delta_m']:.4f},{r['binding_neighbour']},"
                         f"{r['binding_neighbour_class']},"
                         f"{r['binding_kind']},{r['binding_budget']},"
                         f"{r['binding_dz_m']:.4f},"
                         f"{r['binding_slack_m']:.4f}\n")
        print(f"    [spine-yield] {icao} -> {out} ({len(rows)} row(s))")
    except Exception as exc:                           # pragma: no cover
        print(f"    [spine-yield] dump failed: {exc}")
    return rows


def solve_route_profile(layout, icao: str,
                        dem=None, tile_lat: int = 0, tile_lon: int = 0) -> None:
    """Run the one-profile solve and write elevations back onto ``layout``.

    Mutates ``layout`` in place (rect ``altitude_high``/``altitude_low``,
    junction/apron ``node_altitudes``, terminal ``altitude``).  Runway segments
    (HARD anchors) are left untouched.
    """
    from auto_patch.elevation_per_surface.solver_primitives import (
        _build_node_list, _build_shape_constraints, _build_level_coupling,
        _runway_node_set, _sample_node_dem, _seed_elevations, _writeback,
        _report,
    )

    t0 = _time.time()
    # ── THE SOLVE-MODEL SWITCH (constructive-solve round) ────────────
    # ``O4_Solve_Model`` is THE ONE READER (K2's plumbing: env >
    # per-tile cfg > global cfg > default; a typo RAISES).  This deep
    # call site has no Tile — the driver's ``tile_scope`` published the
    # tile's value to the environment for exactly this read, and a lane
    # arm pins the mode the same way (``O4_SOLVE_MODEL``).
    import O4_Solve_Model as _SM
    _solve_constructive = _SM.is_constructive()
    if _solve_constructive:
        import O4_UI_Utils as _UI_sm
        _UI_sm.vprint(1, f"  [solve-model] {icao}: CONSTRUCTIVE solve "
                         f"core (spec constructive-solve; anchor "
                         f"assembly, law objects and the publication "
                         f"tail shared with the iterative model)")
    nodes, bucket_to_idx = _build_node_list(layout)
    if not nodes:
        return

    # ── FLAT-SITE FAST PATH (docs/specs/flat-site-fast-path-spec.md) ──
    # The PARTITION is decided here, before a single elevation is seeded:
    # on a site whose DEM this build actually SUBSTITUTED with a constant
    # Z0 raster (the phase-2 provenance stamp, not merely a flat
    # verdict), every shape the predicate can PROVE is governed by
    # nothing but that constant is BORN at Z0 as a fixed-value member and
    # contributes no free variable.  ``_seed_elevations`` below applies
    # the pins (last of the pin families, demoting any candidate a senior
    # pin disagrees with); the grade-graph builders and the reach band
    # then skip exactly what the partition proved constant.  Gate off, or
    # no substitution ⇒ ``plan_for`` publishes None and every consumer
    # below reads the empty set — byte-identical to before.
    from auto_patch import flat_fast_path as _fast_path
    _fast_path.plan_for(layout)

    elev, base_hard, _have_initial = _seed_elevations(
        layout, nodes, bucket_to_idx, dem=dem,
        tile_lat=tile_lat, tile_lon=tile_lon)
    if not any(base_hard):
        return
    _fp_skip = _fast_path.skip_shape_ids(layout)
    _fp_band_skip = _fast_path.band_skip_idx(layout)
    _fp_cert_exempt = _fast_path.certificate_exempt_idx(layout)
    if _fp_skip:
        import O4_UI_Utils as _UI_fp
        _UI_fp.vprint(0, _fast_path.format_log_line(
            getattr(layout, _fast_path.PLAN_ATTRIBUTE, None), icao))

    # ── ADJACENT-GROUND INGESTION, the SEED ─────────────────────────
    # The published table carries each band node's own DEM sample as
    # ``dem_seed``, and the contract says the variable is seeded there.
    # Done HERE, one statement after the seeder, so no later pass has to
    # ask where a zone node's starting value came from.  Only FREE zone
    # variables are seeded: a bucket that resolved to a pavement or
    # gap-spine node keeps THAT variable's seed, by identity.
    _zone_first_seed = getattr(
        layout, "_adjacent_ground_first_zone_index", None)
    _n_zone_seeded = 0
    if _zone_first_seed is not None:
        _cps_seed = layout.canonical_points
        for _zrow in (getattr(layout, "adjacent_ground_zone_boxes", None)
                      or ()):
            _zs = _zrow.get("dem_seed")
            if _zs is None:
                continue
            _zx, _zy = _zrow["xy"]
            _zi = bucket_to_idx.get(
                _cps_seed.get_or_add(float(_zx), float(_zy)))
            if (_zi is None or _zi >= len(elev)
                    or _zi < _zone_first_seed):
                continue
            elev[_zi] = float(_zs)
            _n_zone_seeded += 1
        if _n_zone_seeded and _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [adjacent-ground-zone] {_n_zone_seeded} band "
                  f"node(s) seeded at their published dem_seed")

    dem_elev = _sample_node_dem(layout, nodes, dem, tile_lat, tile_lon)
    runway_nodes = _runway_node_set(layout, bucket_to_idx)

    # The within-shape grade graph (per-edge cap budgets + rect flat-end pairs)
    # and the rigid flat-across-width coupling — both elevation-neutral.
    from auto_patch.progress import substep as _psub
    _psub(0.20, "Solving elevations — grade graph built")
    # ONE grade context for the whole solve: _build_shape_constraints and
    # build_unified_graph construct identical per-shape GradeShapes, so with a
    # shared ctx the law's pair generation memoises across the two consumers
    # (grade_graph.shape_constraints_cached) instead of running twice.
    from auto_patch import grade_graph as _GG
    # THE FROZEN CTX OBJECT IS *NOT* REUSED HERE — MEASURED AND REJECTED
    # TWICE, each time for a different mechanism, both recorded so the
    # next lane rebuilds neither:
    #
    # (1) S1 attempt 1 (2026-08-13): the ``shape_constraints_cached``
    #     per-ctx memo keyed on ``id(s.polygon)``; a recycled id across
    #     the freeze→solve gap served one shape another shape's pairs
    #     (HECA within_shape 3764 -> 5629, worst 431 %).  CLOSED: the
    #     memo is now keyed BY CONTENT (``grade_graph._sc_ctx_key``),
    #     so this failure class is structurally gone.
    # (2) finalarch item 2 (2026-08-14, fa_0_heca 3ab5a8dfae80 vs
    #     fa_A_heca ed040ecb0e65): with the memo fixed, reusing the
    #     published ctx STILL moved HECA bytes — 72,418 changed lines,
    #     +20 emitted nodes, a node-id renumbering cascade — because
    #     ``build_context`` INTERNS (``canonical_points.get_or_add``)
    #     while it builds its building-key set, and that solve-time
    #     interning side effect is part of the canonical node space the
    #     emitted patch is spelled in.  Skipping the call changes which
    #     later points intern together (the ``law_anchor_key`` warning,
    #     measured), which is the node-space identity change the roster
    #     comment already rejects.  CYXY/OTHH reproduce byte-identically
    #     either way (nothing new to intern there); HECA does not.
    #
    # THE COLLAPSE THAT SURVIVES is the value layer: the freeze's
    # pair-generation work is served to this build through the
    # layout-scoped run memo (``_sc_run_key`` — full value key, node-key
    # space, digest + per-shape law projections), which spans the gap by
    # construction and cannot alter identity.  ``build_context`` itself
    # is the cheap half (its ``centerline_specs`` walk is memoised;
    # dupcensus: 8 calls, 0.0 s CPU) and its rebuild is REQUIRED — the
    # interning it performs is part of the build, not overhead.
    _gg_ctx = _GG.build_context(layout, bucket_to_idx)
    # FLATNESS-CERTIFIED LAZY TIER (user 2026-07-05): pass the DEM (the
    # certificate source) and the currently-hard nodes (runway/seam seeds +
    # runway nodes — a shape touching one sits at profile values, never the
    # DEM seed, so it is never certified).
    # FLAT-SITE FAST PATH exemption (lead ruling 2026-08-10): the born-at-Z0
    # pins are the ONE hard family the sentence above is FALSE of — the
    # substituted raster IS Z0, so such a pin sits exactly AT its own DEM
    # sample.  Leaving them in refused the certificate for a reason that does
    # not hold, and the cost fell on their INELIGIBLE neighbours: any junction
    # or apron sharing a single vertex with a born-at-Z0 shape dropped to eager
    # O(n²) pair generation.  Scoped to THIS family's own pins — a vertex a
    # senior family had already hardened keeps its refusing power (see
    # ``flat_fast_path.certificate_exempt_idx``).
    _hard_for_certificate = (({i for i in range(len(elev)) if base_hard[i]}
                              | {i for i in runway_nodes if i < len(elev)})
                             - _fp_cert_exempt)
    shape_constraints = _build_shape_constraints(
        layout, bucket_to_idx, ctx=_gg_ctx, dem=dem,
        tile_lat=tile_lat, tile_lon=tile_lon,
        hard_nodes=_hard_for_certificate,
        born_flat_shape_ids=_fp_skip or None)
    # ── GAP-FILL SPINE constraints (Slice B stage B2, gated) ─────────
    # docs/slice_b_solver_absorption_design.md §B2.  The pre-solve store
    # ``layout.gap_fill_presolve`` exists ONLY under the B2 gate (the
    # pipeline builds it before this solve); its spine vertices were
    # admitted to the node list by ``_build_node_list`` and now get their
    # envelope INTERVAL edges (the B0 signed-slab primitive) to their
    # frozen-nearest pavement chain stations.  Gate OFF: no store, empty
    # sets, byte-inert.  The longitudinal law is the second-difference
    # fairing pass further down (``_fair_gap_spine_chains``).
    _gap_spine_idx: set = set()
    # The STAGE-B subset (S1d): host-groundside spines are role-less
    # groundside variables, so the projection partition has to be told
    # about them explicitly — see ``_receiver_nodes_from_roles``.
    _gap_spine_b_idx: set = set()
    _gap_spine_chains: list = []
    if getattr(layout, "gap_fill_presolve", None):
        from auto_patch.elevation_per_surface.solver_primitives import (
            _build_gap_spine_constraints, gap_spine_stage_b_nodes)
        _gap_scs, _gap_spine_idx, _gap_spine_chains = (
            _build_gap_spine_constraints(layout, bucket_to_idx,
                                         seed_elev=elev))
        # ``n`` (the field length) is not bound until further down; the
        # field IS ``elev`` and it is never resized between here and
        # ``n = len(elev)``, so this is the same bound.
        _gap_spine_b_idx = gap_spine_stage_b_nodes(
            layout, bucket_to_idx, len(elev))
        shape_constraints.extend(_gap_scs)
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            _n_int_edges = sum(len(_sc["edges"]) for _sc in _gap_scs)
            print(f"    [gap-spine] {len(_gap_scs)} chain(s), "
                  f"{len(_gap_spine_idx)} free spine node(s), "
                  f"{_n_int_edges} envelope interval edge(s)")
    # ── RUNWAY-END RESA CUT constraints (arc R slice R1, gated) ───────
    # The owner ruling: the runway-end envelope is LAW THE SOLVER
    # ENFORCES.  The cut rings were emitted PRE-SOLVE (inside the B1
    # skirt emitter) and their vertices admitted by ``_build_node_list``
    # ABOVE every pavement index; each free one now gets exactly ONE
    # ONE-SIDED envelope interval edge — ``z_cut − z_anchor <=
    # RESA ceiling(d)``, floor open, because the cut never fills — to its
    # end's frozen-nearest pavement anchor node.  Gate OFF: no store, no
    # admitted vertex, empty sets — byte-inert.
    _resa_idx: set = set()
    if getattr(layout, "runway_end_resa_presolve", None):
        from auto_patch.elevation_per_surface.solver_primitives import (
            _build_resa_cut_constraints)
        _resa_scs, _resa_idx, _resa_collisions = (
            _build_resa_cut_constraints(layout, bucket_to_idx))
        shape_constraints.extend(_resa_scs)
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            _n_resa_edges = sum(len(_sc["edges"]) for _sc in _resa_scs)
            print(f"    [runway-end-resa] {len(_resa_scs)} cut piece(s), "
                  f"{len(_resa_idx)} cut node(s), {_n_resa_edges} "
                  f"one-sided envelope interval edge(s), collisions "
                  f"adopted={_resa_collisions[0]} "
                  f"cross={_resa_collisions[1]} "
                  f"no_anchor={_resa_collisions[2]}")
    # ── END-AROUND TAXIWAY (EAT) anchor rect (owner rulings 2026-07-27,
    # gate ``EAT_SURFACE_CEILING_ENABLED``) ───────────────────────────
    # The anchor-rect revision (docs/specs/eat-anchor-rect-spec.md)
    # carries NO constraint entries here: the crossing rect was HARD-
    # PINNED at the regulation value inside ``_seed_elevations`` (so it
    # is already in ``base_hard``), and the pins are registered as
    # runway-class anchors below (after the flex pass re-derives
    # ``G.runway_anchor``).  The first implementation's one-sided
    # pavement↔pavement interval edges — whose negative slab weights
    # blew up the reach-envelope Dijkstra — are retired.
    # ── ADJACENT-GROUND ZONE-ROW constraints (Slice B stage B3 order 2,
    # gated) ──────────────────────────────────────────────────────────
    # The band zone-row vertices admitted by ``_build_node_list`` (from
    # the schema-split construct store ``layout.adjacent_ground_
    # presolve``) get exactly ONE two-sided envelope interval edge each,
    # to their frozen-nearest host pavement ring vertex — the analytic
    # band law verbatim (per-vertex DEM clamp into the corridor; the law
    # has NO neighbour coupling, so there are no transverse edges, no
    # longitudinal edges and no fairing — the order-2 scout refutation,
    # ratified 2026-07-11).  The construct store exists under the
    # order-1 CONSTRUCT gate alone, so the ADMISSION sub-gate is checked
    # explicitly (``admitted_terrain_refs`` also hard-errors on a
    # partial dependency chain).  Admission gate OFF: no zone node was
    # admitted, no constraint is built — byte-inert.
    _zone_idx: set = set()
    if getattr(layout, "adjacent_ground_presolve", None):
        from auto_patch.elevation_per_surface.solver_primitives import (
            ROLE_GRADED_STRIP as _RGS_zone, admitted_terrain_refs
            as _admitted_refs_fn,
            _build_adjacent_ground_zone_constraints)
        if (_RGS_zone, "adjacent_ground") in _admitted_refs_fn():
            _zone_scs, _zone_idx, _zone_collisions = (
                _build_adjacent_ground_zone_constraints(
                    layout, bucket_to_idx))
            shape_constraints.extend(_zone_scs)
            if _os.environ.get("O4_STEP_DEBUG") == "1":
                _n_zone_edges = sum(len(_sc["edges"])
                                    for _sc in _zone_scs)
                print(f"    [adjacent-ground-zone] {len(_zone_scs)} "
                      f"shape entr(ies), {len(_zone_idx)} zone "
                      f"node(s), {_n_zone_edges} envelope interval "
                      f"edge(s), collisions "
                      f"pavement={_zone_collisions[0]} "
                      f"cross={_zone_collisions[1]}")
    # ZONE HOST-AUTHORITATIVE ENVELOPE (Slice B stage B3 solve-side fix,
    # O4_ZONE_HOST_AUTHORITATIVE, default ON): adjacent-ground zone nodes
    # (index >= first-zone) grade TO their host pavement vertex — pavement
    # wins by identity.  Passing this threshold to ``feasibility_project``
    # (a) excludes the 45k asymmetric zone slabs from the reach-envelope
    # Dijkstra (which is non-negative-weight only — the slabs blow it up
    # into tens of minutes at KBNA; gap-spine's ~1.6k drained fine) and
    # (b) makes each zone slab move ONLY the zone endpoint in the sweep
    # (the host never ping-pongs).  KBNA gates-ON: a zone-carrying
    # projection drops from 8+ min to ~24 s.  Gate OFF → None → byte-inert.
    # TERRAIN-LEAF THRESHOLD (arc R slice R1): the RESA-cut rows are the
    # same kind of object as the zone rows — a free terrain variable with
    # ONE envelope edge to an authoritative pavement host — so they ride
    # the same lever.  ``_build_node_list`` sorts BOTH families above
    # every pavement index and publishes the boundary as
    # ``_terrain_host_yield_first_index`` (equal to the zone index when no
    # cut is admitted, so this is byte-inert with the RESA gate off).
    _terrain_first = getattr(layout, "_terrain_host_yield_first_index",
                             None)
    if _terrain_first is None:
        _terrain_first = getattr(
            layout, "_adjacent_ground_first_zone_index", None)
    _iyf = (_terrain_first if (_zone_idx or _resa_idx) else None)
    coupling = _build_level_coupling(shape_constraints)

    # ── THE ONE GRAPH (user 2026-06-27) ──────────────────────────────────────
    # Build the unified grade graph ONCE, FIRST — it is the single graph the reach
    # band, the building seats, the spine solve AND the validator all use.  The
    # reach band is now computed ON it (``reach_band_unified``): reachability is a
    # cap-Dijkstra over ``G.spine_adj`` from ``G.runway_anchor``, so the ceiling is
    # the spine's ACHIEVABLE level and cap-consistent by construction — no separate
    # route graph, no ``spine_adjacency`` re-derivation, no ceiling-consistency
    # bridge.  ``G.spine_adj`` already covers every spine node + edge the old
    # ``spine_adjacency`` produced (verified redundant), so the merge is gone.
    # FLAT-SITE FAST PATH: the born-at-Z0 shapes contribute no within-shape
    # pair to THIS graph either (spec §1: "no grade-graph rows, no reach
    # bands").  ``skip_edge_shape_ids`` is the existing lever for exactly
    # that shape of claim — it still registers every node's POSITION, so the
    # global spine still strings across them and the reach band keeps its
    # connectivity; only their (satisfied-by-construction) pairs are absent.
    # (See the rejected-reuse note above the context build: this build
    # stays local because the context it needs cannot cross the
    # freeze→solve gap while its memo is keyed by ``id(s.polygon)``.)
    G = _GG.build_unified_graph(layout, bucket_to_idx, ctx=_gg_ctx,
                                skip_edge_shape_ids=_fp_skip or None)
    u_spine_adj = G.spine_adj
    # ── THE AIRSIDE VIEW OF THE ONE GRAPH (cycle 9) ─────────────────────
    # ONE graph, but airside authorities may not RIDE service edges: that
    # is the standing ``REACH_NO_SERVICE_SPINES`` law, which reach
    # (``reach_band_unified``) and phase A (``_solve_spine_profile``,
    # cycle 8) already obey and which the remaining consumers of
    # ``spine_adj`` simply predate.  It stopped being cosmetic when the
    # ROAD FEED joined the graph: attributed by probe (roads in the LAW,
    # edges withheld from the GRAPH), ~95 % of HECA -500's airside rise
    # and ~78 % of KCLT -500's is carried by these edges, not by the pair
    # law.  Built ONCE here, consumed by the three airside readers below
    # (the anchor envelope, the building→spine floor, the body solve);
    # groundside's own band still rides the FULL graph, which is the whole
    # point of the roads being in it.
    from auto_patch.config import REACH_NO_SERVICE_SPINES
    _svc_pairs = (getattr(G, "service_spine_pairs", None) or set()
                  if REACH_NO_SERVICE_SPINES else set())
    u_spine_adj_airside = adj_without_pairs(u_spine_adj, _svc_pairs)
    # PROBE GATE ``O4_PROBE_NO_SERVICE_EDGES`` — it used to live HERE and
    # rebind the LOCAL name ``u_spine_adj``, which is why it read inert:
    # ``groundside.groundside_route_band`` builds its own graph and rides
    # ``G.spine_adj``, so the groundside band — the one consumer the
    # service edges exist for — never saw it.  It now acts on
    # ``G.spine_adj`` itself, inside ``grade_graph.build_unified_graph``
    # (``_withhold_service_edges_probe``), so ``u_spine_adj`` above is
    # ALREADY pruned when the gate is on and every consumer of every graph
    # is covered.  Nothing to do here.
    # ── DECK PIN vs SENIOR HARD ANCHOR — THE CONTRADICTION GUARD
    # (docs/specs/kdfw-bridge-refusal-spec.md clause 2) ───────────────
    # A DECK PIN NEVER CONTRADICTS A SENIOR HARD ANCHOR WITHIN ROUTE
    # BUDGET.  Same law, same predicate and same implementation as the
    # EAT guard below it (``pin_contradiction_refusals`` ->
    # ``law_graph_budget``); the only difference is which authority is
    # junior.  Clause 1 refuses the classification defects that ARE
    # visible at classification time; this is the backstop for every
    # future bad pack datum that is not — a pin value is only ever as
    # good as the pack it came from, and the law graph is the one thing
    # that can price it.
    #
    # HERE, and not at the pin site, for the reason spelled out below:
    # the predicate is priced on THE GRAPH PHASE A PROJECTS ON, built two
    # statements above, and this is the first point at which the pins
    # hold any authority (the flex pass, the anchor registration, the
    # hard-truth publication, the reach band, the seats, the envelope and
    # every projection are ALL below).
    #
    # ABOVE the EAT guard deliberately.  Deck pins are seeded BEFORE EAT
    # pins and outrank them, so (a) the EAT pins are passed as ``junior``
    # here and may not bound a deck pin, and (b) running first means a
    # REFUSED deck pin is already released from ``base_hard`` when the
    # EAT guard reads it, so a discredited deck value can never sit in
    # the EAT guard's senior anchor set.
    #
    # The refusal is PER NODE, and RELEASES the node to the seed
    # ``_seed_elevations`` snapshotted, so it solves as ordinary pavement
    # under the caps instead of carrying an immovable value the law
    # cannot reconcile.
    _deck_pins_guard = getattr(
        layout, "_object_bridge_pin_idx", None) or {}
    if _deck_pins_guard:
        _n_deck_pre = len(_deck_pins_guard)
        _n_hard_deck = min(len(base_hard), len(elev))
        _deck_refused = deck_pin_contradiction_refusals(
            _deck_pins_guard, u_spine_adj_airside,
            {_i: float(elev[_i]) for _i in u_spine_adj_airside
             if _i < _n_hard_deck and base_hard[_i]},
            junior=(getattr(layout, "_eat_anchor_pin_idx", None) or {}))
        if _deck_refused:
            _worst_dnode, _worst_d = max(
                _deck_refused.items(), key=lambda r: r[1]["excess_m"])
            _worst_d = dict(_worst_d,
                            pin_m=float(_deck_pins_guard[_worst_dnode]))
            _wd_anchor = _worst_d.get("witness")
            _wd_value = (float(elev[_wd_anchor])
                         if _wd_anchor is not None
                         and _wd_anchor < len(elev) else float("nan"))
            _n_deck_released = release_refused_deck_pins(
                layout, _deck_refused, elev, base_hard, _have_initial)
            publish_deck_refusal_keys(layout, _deck_refused, nodes)
            import O4_UI_Utils as _UI_deckg
            _UI_deckg.vprint(1, format_deck_guard_line(
                icao, _n_deck_released, _n_deck_pre, _worst_dnode,
                _worst_d, _wd_value))
            # A refusal the release could not carry out is a WIRING
            # defect (the seeder publishes both maps in one statement),
            # reported rather than swallowed: a silently under-released
            # count reads exactly like a lawful build.
            if _n_deck_released != len(_deck_refused):
                _UI_deckg.vprint(0,
                    f"  [object-bridge] WARN: {icao}: "
                    f"{len(_deck_refused) - _n_deck_released} refused "
                    f"deck pin(s) had NO pre-pin snapshot and were left "
                    f"stamped — ``_object_bridge_pin_prev`` is out of "
                    f"step with ``_object_bridge_pin_idx``.")
    # ── EAT PIN vs SENIOR HARD ANCHOR — THE CONTRADICTION GUARD
    # (docs/specs/eat-anchor-contradiction-guard-spec.md) ─────────────
    # AN EAT PIN NEVER CONTRADICTS A SENIOR HARD ANCHOR WITHIN ROUTE
    # BUDGET.  The predicate is the seat-guard's, through the seat
    # guard's implementation (``eat_pin_contradiction_refusals`` ->
    # ``law_graph_budget``); there is no second spelling and no new env
    # flag — ``EAT_SURFACE_CEILING`` stays the feature's only switch.
    #
    # HERE, and not at the pin site, because the predicate is priced on
    # THE GRAPH PHASE A PROJECTS ON, which is the line above.  This is
    # the first point at which the pins hold any authority: the runway
    # flex pass, the anchor registration, the hard-truth publication, the
    # reach band, the seats, the envelope and every projection are ALL
    # below.  Two constraint builders upstream did read ``elev`` /
    # ``base_hard`` with the pin in place — the flatness certificate
    # (a hard node REFUSES certification, i.e. MORE law, never less) and
    # the gap-spine disjoint-parent tie-break — and both are recorded in
    # docs/DEFERRED_VERIFICATION.md rather than left unsaid.
    #
    # The refusal is PER NODE (lawful pins in the same rect stand) and
    # RELEASES the node to the seed ``_seed_elevations`` snapshotted, so
    # it solves as ordinary pavement under the caps instead of carrying
    # an immovable value the law cannot reconcile.
    # ── THE UNROUTABLE EAT IS NOT AN EAT (owner ruling 2026-08-12,
    # "CANYON ROOT FIELD-CONFIRMED"; r17d law 1) ──────────────────────
    # AN EAT ANCHOR-RECT WHOSE GOVERNED NODES HAVE NO ROUTE TO ANY
    # RUNWAY ANCHOR IS REFUSED WHOLE-RECT.  The rect is scoped
    # GEOMETRICALLY — a corridor about the extended centreline — so a
    # perimeter road lying there is claimed by it; a road is not an
    # end-around taxiway and the AIRSIDE route graph (the service pairs
    # withheld, ``REACH_NO_SERVICE_SPINES``) says so exactly.
    #
    # HERE, and above its sibling: an unroutable rect is not a facility
    # the contradiction guard should be pricing the VALUE of at all.
    # Same graph, same place in the pass, same release, same carried
    # verdict — one guard site, two laws, no second machinery.
    #
    # ATTRIBUTION-FIRST (instrumented arms 2026-08-12, one report-only
    # line per airport, this tree): KCLT's reference EAT — 11 pins over
    # ONE rect — is TAXI-BOUND (4 of its 11 nodes route to a runway
    # anchor), so the whole-rect law takes NOTHING there.  That margin
    # is the whole reason the law is whole-rect: a PER-NODE spelling
    # would have refused 7 of the reference feature's 11 pins.  KSTJ's
    # single rect binds too (5 of 18) and keeps every pin, so its five
    # contradiction-refusals stand unchanged.  VHHH's 38 pins over SEVEN
    # rects bind NOTHING — zero of 38, against 59 runway anchors on the
    # graph — which is the phantom the field report names.
    _eat_pins_route = getattr(layout, "_eat_anchor_pin_idx", None) or {}
    if _eat_pins_route:
        _eat_rects = getattr(layout, "_eat_anchor_pin_rect", None) or {}
        _n_rects_pre = len({_eat_rects.get(int(_i), -int(_i) - 1)
                            for _i in _eat_pins_route})
        _n_route_pre = len(_eat_pins_route)
        _route_refused = eat_unroutable_rect_refusals(
            _eat_pins_route, _eat_rects,
            eat_pin_taxi_bound(_eat_pins_route, u_spine_adj_airside,
                               G.runway_anchor))
        if _route_refused:
            _n_route_rel = release_refused_eat_pins(
                layout, _route_refused, elev, base_hard, _have_initial)
            publish_eat_refusal_keys(layout, _route_refused, nodes)
            import O4_UI_Utils as _UI_eatr
            _UI_eatr.vprint(1, format_eat_unroutable_line(
                icao, _route_refused, _n_route_pre, _n_rects_pre))
            if _n_route_rel != len(_route_refused):
                _UI_eatr.vprint(0,
                    f"  [eat-anchor-rect] WARN: {icao}: "
                    f"{len(_route_refused) - _n_route_rel} refused pin(s) "
                    f"had NO pre-pin snapshot and were left stamped — "
                    f"``_eat_anchor_pin_prev`` is out of step with "
                    f"``_eat_anchor_pin_idx``.")
    _eat_pins_guard = getattr(layout, "_eat_anchor_pin_idx", None) or {}
    if _eat_pins_guard:
        _n_pins_pre = len(_eat_pins_guard)
        _n_hard_eat = min(len(base_hard), len(elev))
        _eat_unbounded: set = set()
        _eat_priced = eat_pin_contradiction_refusals(
            _eat_pins_guard, u_spine_adj_airside,
            {_i: float(elev[_i]) for _i in u_spine_adj_airside
             if _i < _n_hard_eat and base_hard[_i]},
            unbounded_out=_eat_unbounded)
        # ── THE RECT'S VALUE IS ONE VALUE (KDFW +32-098, instrumented
        # 2026-08-21) ─────────────────────────────────────────────────
        # The predicate above is priced on ``build_anchor_envelope``, a
        # Dijkstra over the SPINE adjacency — so a pin whose node carries
        # no spine edge has NO BOX and is never judged ("a missing bound
        # is honest").  At KDFW's south rect the envelope prices 3 of
        # the 19 pins carrying 196.824 and REFUSES ALL THREE; the other
        # 16 carry the same value unjudged, and one of them (node 3316,
        # box None) then registered as a band anchor and
        # authored the shipped INVERTED band ``[196.824, 175.943]``.
        # ``_build_eat_anchor_rect_pins`` pins a crossing segment FLAT at
        # one value, so the lawfulness of that value is a question about
        # the FACILITY — the same reasoning the unroutable law above
        # already applies, on the other rect-level property.  The priced
        # nodes are the rect's witnesses; the unpriceable ones are not
        # lawful, they are unjudged.
        _eat_refused = eat_rect_value_refusals(
            _eat_pins_guard,
            getattr(layout, "_eat_anchor_pin_rect", None) or {},
            _eat_priced)
        if _eat_refused:
            _worst_node, _worst = max(
                _eat_refused.items(), key=lambda r: r[1]["excess_m"])
            _worst = dict(_worst,
                          pin_m=float(_eat_pins_guard[_worst_node]))
            _w_anchor = _worst.get("witness")
            _w_value = (float(elev[_w_anchor])
                        if _w_anchor is not None and _w_anchor < len(elev)
                        else float("nan"))
            _n_released = release_refused_eat_pins(
                layout, _eat_refused, elev, base_hard, _have_initial)
            publish_eat_refusal_keys(layout, _eat_refused, nodes)
            import O4_UI_Utils as _UI_eatg2
            _UI_eatg2.vprint(1, format_eat_guard_line(
                icao, _n_released, _n_pins_pre, _worst_node, _worst,
                _w_value))
            # PRODUCTION STATES WHAT IT DID, and the number that matters
            # is how many of the pins it took were never judged at all
            # (RULINGS 2026-08-06, instrument truth): an UNPRICEABLE pin
            # used to read exactly like a lawful one.
            _eat_extended = {_i for _i in _eat_refused
                             if _i not in _eat_priced}
            if _eat_extended:
                _eat_rects_v = getattr(
                    layout, "_eat_anchor_pin_rect", None) or {}
                _UI_eatg2.vprint(1, format_eat_rect_value_line(
                    icao, len(_eat_extended),
                    len({_eat_rects_v.get(_i, -_i - 1)
                         for _i in _eat_extended}),
                    len(_eat_extended & _eat_unbounded)))
            # A refusal the release could not carry out is a WIRING
            # defect (the seeder publishes both maps in one statement, so
            # the only path here is a probe that restored one and not the
            # other).  It is reported rather than swallowed: a silently
            # under-released count reads exactly like a lawful build.
            if _n_released != len(_eat_refused):
                _UI_eatg2.vprint(0,
                    f"  [eat-anchor-rect] WARN: {icao}: "
                    f"{len(_eat_refused) - _n_released} refused pin(s) "
                    f"had NO pre-pin snapshot and were left stamped — "
                    f"``_eat_anchor_pin_prev`` is out of step with "
                    f"``_eat_anchor_pin_idx``.")
    # ── RUNWAY FLEX Stage B (user 2026-07-06, docs/runway_flex_plan.md) ──
    # FLEX-LAST: with every route edge at its FULL legal budget (= the
    # taxiways at max cap), find runway-contact pairs whose value gap
    # exceeds the budget-metric shortest path — connections that stay
    # infeasible even with taxiways maxed.  Only CIFP thresholds + tile
    # seams are CERTAIN; the profiles flex toward each other by the
    # MINIMUM (deficit split by available certain-anchor slack), through
    # the same FAA gates the seam redistribute uses.  Runway node seeds
    # and the runway-join anchors are re-derived from the flexed shapes.
    # DEFAULT ON (user 2026-07-06, for in-sim evaluation): Stage B2
    # envelope demands + the inversion fix measured clean at HECA
    # (actionable 11 with ZERO runway pairs; quarantine 11,265 → 2,762)
    # and the flex is a structural no-op on single-runway airports.
    if G.runway_anchor:
        try:
            _n_flexed = _apply_runway_flex_hook(
                layout, icao, nodes, bucket_to_idx, elev, base_hard,
                shape_constraints, G)
        except Exception as _flex_exc:
            import O4_UI_Utils as _UI_flex
            _UI_flex.vprint(1, f"  [pav-builder] WARN: {icao}: runway "
                               f"flex pass failed ({_flex_exc}) — "
                               f"profiles stay frozen.")
    # ── EAT ANCHOR-RECT pins as runway-class anchors (owner rulings
    # 2026-07-27, docs/specs/eat-anchor-rect-spec.md) ─────────────────
    # The crossing-rect pins (hardened in ``_seed_elevations``) join
    # ``G.runway_anchor`` so the reach band propagates their value
    # outward at cap (``E_anchor ± cap·d``) through the EXISTING
    # positive-weight machinery — the same mechanism by which a low
    # runway's ceiling binds distant pavement, and what shapes the
    # descent/climb ramps.  Registered AFTER the flex pass, which
    # clears and re-derives the anchor map.  ``setdefault``: a genuine
    # runway-join anchor at a shared bucket keeps datum authority.
    _eat_anchor_pins = getattr(layout, "_eat_anchor_pin_idx", None) or {}
    register_eat_anchors(G, _eat_anchor_pins, len(elev))
    # ── (THE FLAT-AIRPORT FAST PATH STOOD HERE — DELETED 2026-08-05) ──
    # Fix cycle 2 item 1, verdict (a).  The Tier-2 whole-airport fast path
    # tested a ``FlatAirportCertificate`` at this point and, when it held,
    # seeded every soft node at its DEM VALUE, wrote back and RETURNED —
    # skipping the reach bands, the spine profile, the body fill and the
    # feasibility iteration entirely.
    #
    # That is a SEMANTIC BYPASS, not an optimisation.  Its precondition was
    # measured on the DEM ("is the terrain flat enough that DEM ≈ law?") and
    # its action was to emit the TERRAIN in place of the law — the exact
    # inversion of the owner's ruling that DEM is a seed and never an
    # authority.  A genuinely slack constraint system solves fast through
    # the normal path, so the bypass bought nothing that the solve does not
    # already give: it only removed the law from the airports where it was
    # cheapest to apply.
    #
    # EVIDENCE BASE for deleting rather than repairing it (re-baseline
    # 2026-08-05, BASELINES §1.2): all four flat-world battery airports
    # REFUSED the certificate, each for a different reason — HEAZ and HECA
    # "gap-fill spine present", SPJC "crossing-terrain zone present", KCLT
    # "eat_anchor_rect".  Four airports, three distinct refusal causes, and
    # the outcome was PRINTED ONLY (never written to patch, sidecar, env or
    # frame), so establishing even that much cost a re-run of every build.
    # A path that never fires on the battery, whose only observable is a
    # log line, and whose firing would be a law violation, has no arm that
    # is worth keeping.
    #
    # ``_eat_anchor_pins`` above is NOT part of this: it registers the
    # crossing-rect pins as runway-class anchors and is read by the reach
    # band below.  Only its use as a fast-path refusal test is gone.
    # ── HARD TRUTH PUBLICATION (seed-fix round §2) ───────────────────
    # ``base_hard`` here is exactly the ``seed_rwy_seam`` class (the
    # ``_seed_elevations`` runway/CIFP profile values and tile-seam DEM
    # pins, plus whatever the runway-flex pass hardened) — the SAME set
    # ``_hard_cat`` is derived from a few hundred lines below.  The reach
    # band's value fields need it to seed COMPLETELY: ``G.runway_anchor``
    # is the runway-JOIN anchor map, and at HECA it misses 8 of the 31
    # on-spine hard-truth nodes, which is how the band came to floor a
    # runway node above its own runway value.  Published write-only, so
    # the consumer (``building_feasibility.spine_value_fields``, whose
    # BAND-SEED COMPLETENESS law is standing) never re-derives it.
    #
    # CANONICAL-IDENTITY KEYS (debug lane A 2026-08-05).  The map is keyed
    # by the CANONICAL POINT, never by the solve's node INDEX.  A node
    # index is only meaningful inside ONE ``_build_node_list`` call: the
    # index space is assigned by walking ``layout.shapes``, and every
    # post-solve consumer (``grade_graph_validate.route_band_violations``,
    # the tools, the tests) rebuilds it on a layout that has GROWN —
    # terrain-feature, terrace and clearance shapes are emitted after this
    # point — so index ``i`` no longer names the node it named here.
    # Measured at SPJC: 448 of 455 resolvable seeds landed on the WRONG
    # node under index keys (|published − emitted| p50 7.15 m, max 16.96
    # m), which inverted 795 nodes of the value fields (worst 20.197 m)
    # and minted 1,208 of SPJC's 1,326 route-band violations.  The
    # canonical point is the lossless join (memory: canonical-identity-
    # join — never proximity-join, never index-join across a rebuild).
    _cps_truth = getattr(layout, "canonical_points", None)
    _truth_by_point: dict = {}
    for _i in range(min(len(base_hard), len(elev), len(nodes))):
        if not base_hard[_i]:
            continue
        _nx, _ny = float(nodes[_i][0]), float(nodes[_i][1])
        _key = None
        if _cps_truth is not None:
            try:
                _key = _cps_truth.get(_nx, _ny)
            except Exception:                              # pragma: no cover
                _key = None
        _truth_by_point[_key if _key is not None else (_nx, _ny)] = \
            float(elev[_i])
    layout._seed_hard_truth_values = _truth_by_point
    band, dem_fn, runway_pts, _G = reach_band_for(
        layout, elev, bucket_to_idx, dem, tile_lat, tile_lon, unified_graph=G)
    # ZONE-NODE REACH-BAND SKIP (Slice B stage B3 performance lever,
    # O4_ZONE_NODE_SKIP_REACH_BAND, default ON): the adjacent-ground zone
    # nodes (index >= first-zone) are graded_strip terrain variables whose
    # value is the per-vertex DEM envelope clamp to their host — they never
    # consume a reach band, yet scanning one costs ~74 ms (the off-net
    # skeleton fallback) × 45k at KBNA (~55 min).  Skip them; they take the
    # honest off-net band (None).  Gate OFF restores the all-nodes scan.
    # Arc R slice R1: the RESA-cut rows join the skip for the same reason
    # (a cut vertex's value is the DEM clamped under its host's envelope;
    # it never consumes a reach band).  ``_terrain_first`` equals the zone
    # index with the RESA gate off — byte-inert there.
    _zone_skip = _terrain_first
    # REACH-BAND CLUSTER AMORTIZATION (Tier 3 wave 1, O4_REACH_BAND_CLUSTERS):
    # ``node_bands`` shares the expensive per-node serving-centerline scan
    # across spatial buckets via the band's ``.batch`` method — one scan per
    # bucket, reused by every member the representative's line provably also
    # serves (an EXACT, bit-identical band, no per-member scan).  Gate OFF or a
    # band without ``.batch`` → the exact per-node scan, byte-identical.
    node_band = node_bands(nodes, band, skip_from=_zone_skip,
                           skip_idx=_fp_band_skip or None)
    # ── THE BAND IS CARRIED FROM HERE, UNCONDITIONALLY (round 9, spec
    # ``round9-writeback-band-frame-spec.md`` §1) ────────────────────────
    # THIS list is THE band: the solve's, the validator's, the census's,
    # the envelope's and the writeback clamp's.  It is minted ONCE here,
    # keyed by CANONICAL POINT (the identity every later node space
    # resolves through) and in the uncrowned PROFILE space it was
    # computed in — a second construction anywhere downstream would be a
    # second law, which is exactly the defect round 9 deletes.
    # Unconditional because the writeback clamp reads it on EVERY build;
    # the ENVELOPE's own consumption stays gated at its call site in
    # ``final_grade_projection``.  Born-at-Z0 fast-path nodes are ``None``
    # in ``node_band`` (skip_idx) — they simply carry no key, and every
    # reader's documented default for a missing key is off-net.
    _store_of(layout).mint(
        "env_band", "interval",
        {_bkey: (float(_bb[0]), float(_bb[1]))
         for _bkey, _bi in bucket_to_idx.items()
         if _bi < len(node_band) and (_bb := node_band[_bi]) is not None},
        replace=True)
    # ── THE FEASIBILITY ENVELOPE READS THIS BAND (owner ruling 2026-07-30,
    # spec ``envelope-uses-the-centerline-graph``; gate
    # ``O4_ENVELOPE_FROM_BAND``, default OFF pending the reference field;
    # implied by ``O4_ROUTE_METRIC_ENVELOPE`` — spec
    # ``route-metric-envelope`` §1, where the "0"/"1" default drift dies:
    # BOTH names are now resolved by ``one_solve.envelope_from_band_enabled``
    # and the single surviving default is "0") ────────────────────────────
    # DEFAULT FLIPPED TO OFF 2026-07-30 (taut-string-model-spec step R0).
    # The substitution is CORRECT and measured — broken 13,428 → 0, total
    # over-cap 18,278 → 9,096, corridor sag 0.527 → 0.225 — but ON alone
    # regresses the owner-visible HECA seam gate (108.26 → 102.75, out of
    # the 106-109 class) and the building199 weld (0.49 → 1.40 m), mints
    # 663 pairs that violated under NEITHER arm, and trips the build-time
    # law (+5.47 s "Solving elevations").  Cause, measured: the §7
    # reference hold fires ONLY for broken nodes, so removing the false
    # quarantine also removes an accidental hold — and z_ref is rebuilt
    # per pass from that pass's entry elev, a RATCHET that makes each
    # pass's drift the next pass's reference.  Re-enable in ONE measured
    # change together with the immutable reference field (spec step R3),
    # never alone.
    # MEASURED AGAIN 2026-08-01 under ``O4_ROUTE_METRIC_ENVELOPE`` (with
    # the §7 reference rods now production): HECA α full-severity census
    # 19,591 → 8,240 rows, cliffs 1,023 → 138, the ≥10 m cliff class
    # 93 → 0, groundside rows 864 → 595 / cliffs 249 → 53, and the owner's
    # three sites 8.92 / 0.79 / 1.24 m → 0.07 / 0.13 / 0.10 m.  Cost: the
    # solve phase grew ~20 % on a CONTAMINATED (concurrent-build) clock at
    # both HECA and SPJC — a clean exclusive measurement and the Fable-5
    # whole-pipeline review are owed before any default flip.
    # "We already have the graph, use it, don't duplicate it."  ``node_band``
    # IS ``reach_band_unified`` sampled at these nodes — the route-metric,
    # service-excluded band seeded from ``G.runway_anchor`` that the seats and
    # ``route_band_violations`` already consume.  Handing the SAME list to
    # ``feasibility_project`` replaces its within-shape pavement-PAIR closure
    # (whose binding path is not a route an aircraft could take, and whose
    # every-hard-node seeding lets groundside pins declare airside
    # infeasible).  Nothing is sampled twice: this is the list from the line
    # above (``single-pass-principle``).  Gate off ⇒ ``None`` ⇒ every call
    # below is byte-identical to the pair-closure envelope.
    # ONE default, defined once (spec ``route-metric-envelope`` §1) — the
    # historical "0"/"1" split across solve.py / one_solve.py is dead.
    _ENV_FROM_BAND = envelope_from_band_enabled()
    _env_band = node_band if _ENV_FROM_BAND else None
    _psub(0.55, "Solving elevations — reach bands computed")
    # ``law_graph`` — THE constraints object this solve projects on, handed
    # to the seat coupler, which prices pair admission and limits on the
    # graph the projection enforces — the coupler's ONLY metric (spec
    # ``route-distance-seat-coupling-spec.md``, standing law).  Passing the
    # SAME list object is the point: a re-derived edge set would be the
    # second instrument that law exists to remove.  ``None`` here is a
    # WIRING DEFECT and the coupler says so rather than pricing a chord.
    building_seats = build_building_seats(
        layout, bucket_to_idx, band, dem_fn, runway_pts,
        law_graph=shape_constraints, n_nodes=len(elev))
    # FEEDER CONVERGENCE (user directive #3): seat each NO-BUILDING apron flat at a
    # single level its feeders can all reach (the ring-band intersection, clamped to
    # DEM), so the feeders converge to it instead of arriving incompatible.  Merged
    # below into ``building_seats`` AFTER ``building_spine_floor`` (which is a
    # building-pad chord model) so apron seats ride the same heaviest-anchor
    # machinery without perturbing the building-frontage spine floor.
    # ── THE LAW-GRAPH BUDGET ORACLE (seed-fix round §3/§4 + the spec's
    # RECONCILIATION clause) ──────────────────────────────────────────
    # ONE build, here, consumed by BOTH the apron-contact polytope (§3)
    # and the seat hard-stamp guard (§4) — and by the route-distance
    # seat-coupling round, which cites this object rather than deriving
    # a second metric (``single-pass-principle``; a polytope priced on a
    # metric the projection does not enforce is the defect family both
    # rounds are fixing).  Priced EXACTLY as phase A projects: the
    # unified ``spine_adj`` with its per-edge budgets, SERVICE EDGES
    # EXCLUDED exactly as ``_solve_spine_profile`` excludes them (see the
    # receiver-only note below — this line said "service edges included"
    # until cycle 9 measured what that costs once the graph carries the
    # road network), anchor values in the solve's own (crowned) space —
    # the graph and the frame ``_solve_spine_profile``'s final exact cap
    # projection uses.  Two STANDING laws consume it — the apron-contact
    # anchor cap and the seat hard-stamp guard — so it is always built;
    # ``build_anchor_envelope`` returns None when the graph carries no
    # hard anchors, which is the honest "nothing to bound against".
    from .law_graph_budget import build_anchor_envelope
    _n_hard = min(len(base_hard), len(elev))
    # RECEIVER-ONLY HERE TOO (cycle 9, measured).  The paragraph above used
    # to end "service edges included", and that was harmless while the ONE
    # graph held only the apt.dat row-1206 routes (HECA 5, KCLT 15).  It is
    # not harmless now: this envelope feeds TWO STANDING AIRSIDE LAWS (the
    # apron-contact anchor cap and the seat hard-stamp guard), so every
    # service edge in it prices AIRSIDE against a truck route.  When the
    # road feed joined the graph (HECA 5 -> 705 centerlines) that moved
    # 60-71 % of the PURE-airside nodes at HECA — nodes no groundside way
    # even touches — by a median 9-18 cm and up to 3.7 m, which
    # airside-is-king forbids however the roads got there.
    # The exclusion is not new law: ``REACH_NO_SERVICE_SPINES`` is the
    # standing gate, ``building_feasibility.spine_value_fields`` and
    # ``_solve_spine_profile`` already skip exactly this pair set, and this
    # consumer simply predates them.  Direction, not deletion: every road
    # pair is still enforced as law in the partitioned projections, and the
    # road is still seated afterwards, as a receiver, from its mouth band.
    _env_adj = u_spine_adj_airside
    _anchor_envelope = build_anchor_envelope(
        _env_adj,
        {i: float(elev[i]) for i in _env_adj
         if i < _n_hard and base_hard[i]})
    # Instrument (RULINGS 2026-08-06, "Instrument truth is law"): report the
    # DENOMINATOR with the exclusion, so "the roads changed nothing here"
    # can never read the same as "there were no road edges to exclude".
    import O4_UI_Utils as _UI_env
    _env_all = sum(len(v) for v in u_spine_adj.values())
    _env_dropped = _env_all - sum(len(v) for v in _env_adj.values())
    _UI_env.vprint(1,
        f"  [anchor-envelope] {icao}: {len(_svc_pairs)} service spine "
        f"pair(s) excluded, {_env_dropped} of {_env_all} directed edge(s) "
        f"dropped; {len(_env_adj)} of {len(u_spine_adj)} node(s) keep an "
        f"airside route")
    apron_seats = build_nobuilding_apron_seats(
        layout, bucket_to_idx, band, dem_fn,
        anchor_envelope=_anchor_envelope, icao=icao)
    apron_body = apron_body_nodes(layout, bucket_to_idx)

    # NO-BUILDING APRON FILL (user 2026-06-26): a no-building apron has no pad to
    # anchor it, so where the DEM is wrong-low it sags below the level its feeder
    # taxiways can reach.  Seat each such apron FLAT at the closest-DEM level
    # reachable from ALL its routes (filled above the bad DEM) so the taxiways
    # grade smoothly from their runway anchors to it.  Treated like building seats
    # (heaviest anchors); spine nodes that cross the apron keep their taxi grade.
    # NO-BUILDING APRON FILL (user 2026-06-26): the closest-DEM level reachable
    # from all routes, per no-building apron.  Applied below as a per-node FLOOR
    # (raising node_band) so a no-building apron can't sag below its reachable
    # level into a wrong-low DEM pit, while still rising to follow a higher local
    # network (so it does not drag a high-route junction down).

    # ── THE ONE GRAPH (user 2026-06-26, docs/goal_merge_one_graph.md) ─────────
    # Solve the spine DIRECTLY on the geometry nodes the validator checks
    # (``grade_graph.build_unified_graph``) — there is no separate route graph and
    # no read-by-index bridge.  The spine is smoothed (never hard-frozen at an
    # over-cap profile value), runway-adjacent geometry nodes anchor at their OWN
    # LOCAL runway elevation, and a final feasibility-projection drives every
    # grade-graph edge ≤cap (only edges between two hard anchors — runway/building
    # — are left, the genuine steps).  This is what makes the validator's spine
    # zero: build and validate use the exact same nodes.
    from .one_solve import feasibility_project_partitioned
    # G + u_spine_adj already built above (before seating).
    n = len(elev)
    # Runway anchors: every geometry node a taxi spine joins the runway at is
    # HARD at the LOCAL runway elevation (the single hard anchor; the building
    # floor yields).  Never override an existing CIFP/seam hard value (it IS
    # the local runway surface there).
    # Anchor the node the validator's runway-join picks (nearest to each
    # taxi-centerline runway contact) at the LOCAL runway elevation — even if
    # it is already a hard runway node: at a runway INTERSECTION the crossing
    # node sits at a compromise between the two runways (694.8), but the taxi
    # that contacts ONE of them must meet THAT runway's surface (695.3).  ``re``
    # is the runway profile, so this is a no-op for a true runway-end node and
    # only corrects the intersection-compromised crossing node.
    # ── hard-anchor CATEGORY map — NAMES THE ACTUAL PROVENANCE ────────
    # ⚠ NOT REPORT-ONLY.  The comment that used to stand here — "nothing
    # in the solve consumes it" — was FALSE and is corrected in the
    # cycle-7.5 instrument sweep.  ``_hard_cat`` VALUES are read by
    # equality at TWO production sites, both under ``ENABLE_SPINE_CROWN``
    # (``config.py`` ``O4_SPINE_CROWN``, default "1" — ON), and both feed
    # ``crown.build_crown_drop_field``, whose output is the writeback
    # transform applied to EMITTED elevations:
    #
    #   * the CROWN-FREEZE set (see the ``_crown_freeze`` build below):
    #     ``{i for i, _cat in _hard_cat.items() if _cat in
    #     ("seam_spine_anchor", "seat_on_spine", "gs_pin")}`` — a frozen
    #     node emits at crown drop 0 instead of its family's drop;
    #   * the RUNWAY-JOIN samples: ``{i: s for i, s in
    #     G.runway_anchor_sample.items() if i < n and
    #     _hard_cat.get(i) == "rwy_join"}`` — a join in this map gets a
    #     VALUE-DERIVED drop that lands it on the crowned runway edge.
    #
    # CONSEQUENCE, and the standing constraint on anyone editing this
    # block: changing WHICH NODES CARRY a given class value MOVES THE
    # SURFACE.  Report work here must be membership-identical
    # (``setdefault``, never ``=``, over an already-classified node).
    # The map is ALSO read by the ``O4_DUMP_SOLVE_STATE`` snapshot, the
    # ``O4_BREAK_FORENSICS`` class map and the route-metric witness
    # withdrawal — those three are genuinely report-only.
    #
    # CYCLE-7 FIX 3, verdict (d) BROKEN INSTRUMENT.  This map used to be
    # ``{i: "seed_rwy_seam" for i in base_hard}`` — a BLANKET CONSTANT.
    # Every base-hard node came out with the same class name whatever
    # made it hard, and the two ``setdefault`` calls immediately below
    # (``rwy_join``, ``rwy_flexed``) were consequently DEAD for exactly
    # the nodes they describe, because those nodes were already in the
    # map.  The cost was measured: the c6attr dossier's finding "610
    # strictly-immovable anchors, and 100 % of them are class
    # ``seed_rwy_seam``" is an artefact of this line — the classifier
    # could not have said anything else — and it is why the seam-depth
    # question ("do the pin VALUES carry ride, or is a relief form
    # missing between two TRUE pins?") could not be answered off the
    # class axis at all.  Under RULINGS 2026-08-06 ("Instrument truth is
    # law") a report that cannot distinguish its own populations is a
    # defect, not a convenience.
    #
    # THE ANSWER the fixed axis makes checkable, recorded here because it
    # is what the fix was for: at HECA ``--dem 1`` all 1,077 of these
    # nodes hold 48.50-142.43 m against a DEM of 1.000 and ZERO sit at
    # the DEM value — the pins carry NO ride, so the depth is the second
    # branch (a lawful relief form missing between two true pins), and
    # the law already names that form: RUNWAY FLEX, which this same build
    # reports stopping on its ROUND CAP rather than on convergence.
    #
    # Each class is a set this scope already owns; a node no source
    # claims is named ``base_hard:unattributed`` rather than folded into
    # a neighbouring class, so the residue is visible and countable
    # instead of silently inflating a real population.
    _flexed_idx = getattr(layout, "_flexed_runway_node_idx", None) or ()
    _seam_pin_pre = getattr(layout, "_seam_pin_idx", None) or set()
    # THE RULE lives in ``classify_hard_anchors`` (module level) so the
    # twin drives the classifier the solve actually runs, not a local
    # re-implementation of its precedence.  Body extracted verbatim.
    _hard_cat: dict = classify_hard_anchors(
        n, base_hard, _flexed_idx, _seam_pin_pre, G.runway_anchor,
        runway_nodes)
    # FLEXED runway nodes keep the flexed profile value: the join
    # anchor is SAMPLED from piece geometry and disagrees with the
    # flexed profile at piece ends (user 2026-07-06 root-cause —
    # 58.30 stamped over the flexed 61.21 → 24 % inside 05L).
    # The class map above already named every node that was base-hard on
    # entry, so these assignments cover the nodes this loop HARDENS —
    # which is what the two labels were always meant to describe and
    # what the blanket constant used to swallow.
    for i, re in G.runway_anchor.items():
        if i < n:
            if i in _flexed_idx and base_hard[i]:
                _hard_cat.setdefault(i, "rwy_flexed")
                continue
            elev[i] = float(re)
            base_hard[i] = True
            _hard_cat.setdefault(i, "rwy_join")
    u_spine_nodes = set(u_spine_adj) | G.spine_nodes()
    # Building-frontage spine floor (the serving arm climbs to its pads),
    # cap-Lipschitz on the unified spine chain.
    u_spine_floor = building_spine_floor(
        layout, nodes, bucket_to_idx, building_seats, node_band,
        u_spine_adj_airside)
    # APRON-CONTACT FLOOR (user 2026-06-29): a taxiway/junction that meets a
    # BUILDING-anchored apron's edge FAR from the building gets no building floor
    # (>corridor) and no no-building seat (skipped for building aprons), so it
    # solves to its own low DEM and the senior apron cliffs down to it (OEMA TX8
    # #275 → 96 % apron step).  Floor each such feeder contact at the apron's own
    # reachable level so the taxi spine grades UP to the apron — the apron keeps
    # its cap, the taxi yields (the documented apron-owned authority).  Merged as
    # a floor (max), so it composes with the building-frontage floor.
    for _i, _fl in build_apron_contact_floors(
            layout, bucket_to_idx, band, dem_fn, building_seats).items():
        if _fl > u_spine_floor.get(_i, -float("inf")):
            u_spine_floor[_i] = _fl
    # OBJECT-BRIDGE CROSSING FLOOR (feature B stage 2, gated by
    # O4_OBJECT_BRIDGE_TERRAIN via the cached classification — with
    # the gate off the producer returns {} without reading anything):
    # a TERRAIN/PROFILE_CARRIED span over an un-lowered draped road
    # gets per-node floors = road + clearance + structure thickness
    # (``grade_law.bridge_crossing_floor_m``) so the hump solves
    # itself under the existing grade and curvature caps (spec
    # section 3.2, amendment A2).  Merged by max like the apron
    # floors above.
    from ...bridges import bridge_crossing_floor_nodes
    for _i, _fl in bridge_crossing_floor_nodes(
            layout, nodes, dem, tile_lat, tile_lon).items():
        if _fl > u_spine_floor.get(_i, -float("inf")):
            u_spine_floor[_i] = _fl
    # FEEDER CONVERGENCE (tilt model): a no-building apron is ANCHORED like a
    # building so its feeder SPINES grade to meet it — but at the per-feeder
    # feasible level L_i (the apron tilts ≤cap between contacts, see
    # build_nobuilding_apron_seats), NOT one flat level.  Each L_i is in its
    # feeder's reach band, so the spine reaches it without an over-cap step (the
    # earlier FLAT hard seat forced unreachable levels → regressed
    # cyxy_spine_zero + HECA runway; the per-contact tilt level does not).
    building_seats.update(apron_seats)
    # SEAM PINS ARE NEVER SEATS (user 2026-07-04, "treat the seam like
    # a runway edge or building"): a seat level computed at a tile-seam
    # terrain pin overwrites the pin everywhere seats are applied
    # (spine stamp, body fill) and detaches the boundary from the
    # terrain it must meet — SPLP's band-edge corner was seated 66.3
    # over its 63.5 pin.  The pin anchors that node; the apron's other
    # contacts still seat, and the surface grades between them.
    _seam_pin_idx = getattr(layout, "_seam_pin_idx", None) or set()
    for _i in list(building_seats):
        if _i in _seam_pin_idx:
            del building_seats[_i]
    # ── THE TRUE-ANCHOR BAND, built ONCE for the whole frame (owner
    # ruling 2026-08-15 + the 47-findings fix): the cap-Lipschitz band
    # from the ONLY physically-certain anchors (CIFP thresholds + tile
    # seams).  Three consumers, one construction: the §4 seat-stamp
    # guard below, the report-only band instrument, and the warm start
    # (both in the iterative branch).  ~1.5 s at HECA.
    #
    # ★ THE CARRIER GRAPH IS ROUTE-CONTINUOUS ONLY (owner audit ruling
    # 2026-08-15: "the route must follow a taxiway_centerline").  The
    # first cut propagated over ALL law pairs, and its worst HECA chain
    # audited as unlawful composition: 1,171 m of it rode APRON
    # interiors/edges — pairs a DECLARED TERRACE may lawfully break —
    # so the cone was over-tight (the standing reach-follows-
    # centerlines law, re-learned in a new instrument).  The carrier
    # is now: the airside route-spine edges (taxi CENTERLINES at their
    # route budgets; service excluded per REACH_NO_SERVICE_SPINES) +
    # runway/runway-crossing within-shape pairs (a terrace may never
    # cross a taxi route and never exist inside a runway, so THESE
    # compose unconditionally).  Aprons, service, groundside and taxi
    # edge-chords no longer carry the cone.
    from auto_patch.layout import ROLE_RUNWAY as _R_RWY_tab
    from auto_patch.layout import ROLE_RUNWAY_CROSSING as _R_RXC_tab
    from .constructive import runway_station_chains as _rsc_tab
    from .one_solve import LivingBand as _LB_tab
    from .one_solve import envelope_radj as _era_tab
    from .one_solve import law_edge_limits as _lel_tab
    _tab_entries = [sc for sc in shape_constraints
                    if sc.get("role") in (_R_RWY_tab, _R_RXC_tab)]
    _tab_el, _tab_il, _tab_esk = _lel_tab(
        _tab_entries, n, include_flat_pairs=True)
    for _i, _lst in u_spine_adj_airside.items():
        for (_j, _b) in _lst:
            if _i == _j or _b is None or _b < 0 or _i >= n or _j >= n:
                continue
            _e = (_i, _j) if _i < _j else (_j, _i)
            _prev = _tab_el.get(_e)
            if _prev is None or _b < _prev:
                _tab_el[_e] = float(_b)
    _tab_cra, _tab_fra = _era_tab(
        _tab_el, _tab_il, _tab_esk, interval_yield_from=_iyf)
    _tab_p0: dict = {}
    _tab_p0m: dict = {}
    for _i in sorted(_seam_pin_idx):
        if _i < n:
            _tab_p0[_i] = float(elev[_i])
            _tab_p0m[_i] = "seam"
    for _ch in _rsc_tab(layout, bucket_to_idx, n):
        for _q, _e in sorted(_ch.pegs.items()):
            for _i in _ch.members[_q]:
                if _i < n and _i not in _tab_p0:
                    _tab_p0[_i] = float(_e)
                    _tab_p0m[_i] = f"cifp:{_ch.ref}"
    _tab_band = _LB_tab(
        _tab_cra, _tab_fra, n,
        track_paths=bool(_os.environ.get("O4_BAND_INSTRUMENT_DUMP")))
    _tab_band.seed(_tab_p0, _tab_p0m)
    # A building seat that IS a spine node (a pad node on a taxi centerline)
    # is anchored at its ACTUAL seat level DURING the spine solve — so the
    # spine grades its neighbours to within cap of the building (buildings are
    # heaviest).  Otherwise the spine grades to the softer floor (715.35) and
    # PHASE B then slams the seat to its real level (715.63), breaking the cap
    # to the neighbour (the 5.4% junction).  The seat and the spine now agree.
    # (Seam pins were already removed from ``building_seats`` above —
    # the extra guard here is belt-and-braces.)
    # ── §4 HARD-STAMP GUARD (seed-fix round, STANDING LAW) ───────
    # A seat value that CAP-CONTRADICTS a hard runway/seam anchor
    # within its own route budget must not become ``base_hard``.
    # Stamped, it is a second immovable authority against a runway
    # truth the projection cannot reconcile — HECA's 2861 (seat
    # 65.749) sits 0.1928 m of budget from runway anchor 2863
    # (60.790), a 4.766 m contradiction that the phase-A projection
    # then burns 3983 sweeps on and can never certify.  The seat
    # KEEPS its value as the node's starting elevation (it is still
    # the best estimate of where that apron wants to be) but enters
    # YIELD-HARD: movable by the projection where the law demands,
    # excluded from the spine-yield PRESERVED set (which today
    # preserves ``building_seats`` unconditionally), and every
    # contradiction reported with the anchor that binds it.
    _seat_yield_idx: set = set()
    _seat_guard_rows: list = []
    _seat_band_rows: list = []
    _seat_guard_on = _anchor_envelope is not None
    # §4 EXTENSION (owner-ordered 47-findings fix, 2026-08-15): the
    # TRUE-ANCHOR BAND is a second, tighter refusal frame beside the
    # route-metric envelope — it composes EVERY law edge (strips,
    # cross-sections, near-miss frontage), not just route budgets, so
    # a seat it excludes cannot be held by any lawful surface at all.
    # Same fallback as the route guard: the seat keeps its value as
    # the node's starting elevation and enters YIELD-HARD.  Kill
    # switch ``O4_BAND_SEAT_GUARD=0`` for attribution arms.
    _band_guard_on = _os.environ.get("O4_BAND_SEAT_GUARD", "1") != "0"
    for i, lv in building_seats.items():
        if i < n and lv is not None and i in u_spine_adj \
                and i not in _seam_pin_idx:
            if _seat_guard_on:
                _v = _anchor_envelope.violation(i, float(lv), tol=0.01)
                if _v is not None:
                    elev[i] = float(lv)
                    _seat_yield_idx.add(i)
                    _seat_guard_rows.append((i, float(lv), _v))
                    continue
            if _band_guard_on:
                _blo, _bhi = _tab_band.interval(i)
                _bv = float(lv)
                if ((_blo is not None and _bv < _blo - 0.01)
                        or (_bhi is not None and _bv > _bhi + 0.01)):
                    elev[i] = _bv
                    _seat_yield_idx.add(i)
                    _fa, _fm, _ca, _cm = _tab_band.bounding(i)
                    _seat_band_rows.append(
                        (i, _bv, _blo, _bhi, _fm, _fa, _cm, _ca))
                    continue
            elev[i] = float(lv)
            base_hard[i] = True
            _hard_cat.setdefault(i, "seat_on_spine")
    if _seat_band_rows:
        import O4_UI_Utils as _UI_sbg
        _UI_sbg.vprint(
            1,
            f"  [seat-guard] {icao}: {len(_seat_band_rows)} further "
            f"seat(s) OUTSIDE the true-anchor band (CIFP+seam law "
            f"cones) — NOT stamped base_hard, entering yield-hard.")
        for (_i, _bv, _blo, _bhi, _fm, _fa, _cm, _ca) in sorted(
                _seat_band_rows,
                key=lambda r: -max(
                    (r[2] - r[1]) if r[2] is not None else 0.0,
                    (r[1] - r[3]) if r[3] is not None else 0.0))[:5]:
            _UI_sbg.vprint(
                1,
                f"  [seat-guard]   node {_i}: seat {_bv:.3f} vs band "
                f"[{'-inf' if _blo is None else f'{_blo:.3f}'}, "
                f"{'+inf' if _bhi is None else f'{_bhi:.3f}'}] "
                f"(floor by {_fm}@{_fa}, ceiling by {_cm}@{_ca}).")
    layout._seat_stamp_yield_idx = _seat_yield_idx
    if _seat_guard_on:
        import O4_UI_Utils as _UI_sg
        _UI_sg.vprint(
            1,
            f"  [seat-guard] {icao}: {len(_seat_guard_rows)} of "
            f"{len(building_seats)} seat(s) cap-contradict a hard "
            f"runway/seam anchor within route budget — NOT stamped "
            f"base_hard, entering yield-hard.")
        for (i, lv, _v) in sorted(
                _seat_guard_rows,
                key=lambda r: -r[2]["excess_m"])[:10]:
            _UI_sg.vprint(
                1,
                f"  [seat-guard]   node {i}: seat {lv:.3f} is "
                f"{_v['excess_m']:.3f} m past its {_v['side']} "
                f"{_v['bound']:.3f} (witness anchor {_v['witness']}, "
                f"route budget {_v['route_budget_m']:.4f} m).")

    # DETACHED building pads — THE GROUNDSIDE LAW (item 3(b),
    # 2026-08-05; replaces the 2026-07-17 hard DEM pins).
    #
    # A pad with no airside-served seat is a GROUNDSIDE object.  The
    # deleted block pinned it HARD at its raw-DEM footprint median for the
    # whole solve — DEM as a constraint, which the ruling forbids and the
    # constant-DEM oracle fails outright (DEM ≡ c freezes the pad at c
    # while the groundside pavement it is welded into sits wherever the
    # airside solve put it: an arbitrary step at a shared node on ground
    # with no relief).
    #
    # The pin's stated reason — "the route-profile blend paints them with
    # the surrounding airside level" — was a real measurement (KBNA:
    # 170-172 over 158-167 ground) but the wrong writer.  ATTRIBUTED (see
    # ``anchors``' DETACHED-PAD block for the full read): the AIRSIDE REACH
    # BAND FLOOR writes them.  ``raster_reach_band._domain_geom`` admits
    # every ROLE_BUILDING polygon to the band's propagation domain with no
    # airside-service test, so a pad ``building_feasible_levels`` REFUSED
    # to seat still gets ``node_band`` floors from
    # ``spine_value_fields`` (``max over runway anchors (value − route
    # budget)``); ``one_profile_solve`` then clamps the pad's DEM up to
    # that floor at warm start and holds it there every sweep.
    #
    # THE FIX, AT SOURCE: withhold the airside band from a pad the airside
    # law does not serve.  It then rides its seed through the field solve
    # and is SEATED BY LAW after the groundside passes, on the solved
    # groundside datum it abuts (``seat_detached_pads_by_law``, called
    # there — a groundside object's datum is a solved groundside variable,
    # so it is necessarily the last thing seated).
    _detached_pads = detached_pad_nodes(
        layout, bucket_to_idx, building_seats)
    # ── FRONTAGE COUPLING ⇒ BAND SEATING (owner 2026-08-06) ───────────
    # The withholding keys on FRONTAGE COUPLING, not on touch.  The near-
    # miss frontage edges are computed HERE, once, and carried to the
    # ``u_edges`` build below: they are the near-miss half of the
    # coupling test AND the law edges themselves, and the ruling's own
    # finding is that the two halves were separated (the edge minted, the
    # seat derivation not extended).  One geometry pass, two consumers —
    # the single-pass principle, and it also stops the recognition log
    # firing twice.
    from .anchors import near_miss_building_frontage_edges as _nmfe
    from .anchors import detached_pad_frontage_coupling as _dpfc
    # STAGE MAP for every pair APPENDED to the unified edge set
    # (staged-solve S1b).  Filled by each pair's own constructor;
    # ``split_edges_by_stage`` REFUSES an edge missing from it.
    _u_pair_stage: dict = {}
    _near_miss_edges = _nmfe(layout, bucket_to_idx, building_seats,
                             stage_out=_u_pair_stage)
    _pad_frontage = _dpfc(_detached_pads, G, _near_miss_edges)
    _detached_pad_node_idx, _n_frontage_pads = (
        withhold_airside_band_from_detached_pads(
            node_band, _detached_pads, n, frontage_coupled=_pad_frontage))
    if _detached_pads:
        try:
            import O4_UI_Utils as _UI_dp
            _UI_dp.vprint(1,
                f"  [seats] {len(_detached_pads)} detached building "
                f"pad(s): {_n_frontage_pads} FRONTAGE-COUPLED (band "
                f"KEPT — seated from the route-graph band through the "
                f"frontage chord, owner 2026-08-06), "
                f"{len(_detached_pads) - _n_frontage_pads} with no "
                f"frontage coupling / {len(_detached_pad_node_idx)} "
                f"node(s): airside reach band WITHHELD, seated on their "
                f"groundside datum after the groundside passes.")
        except Exception:
            pass

    # SEAM SPINE ANCHORS (user 2026-06-28): where a taxi centerline crosses a
    # tile seam, pin the nearest SPINE node to the SMOOTHED seam DEM as a HARD
    # anchor — so the spine solve below SPREADS the route→seam drop along the
    # centerline (≤cap over its length) instead of leaving the spine at the
    # plateau level and the body cliffing to the seam.  The seam is terrain-
    # pinned for cross-tile stitching; both tiles' route reaches the same seam
    # value → no cross-tile cliff AND no within-apron cliff.  Wires the
    # otherwise-dead ``SEAM_FIELD_ANCHORS`` concept onto the unified graph.
    from auto_patch.config import SEAM_FIELD_ANCHORS
    _cut_lines = getattr(layout, "_seam_cut_lines", None) or []
    # PUBLISHED, not discarded (cycle-7.5 instrument sweep): the set this
    # pass actually pinned is what attributes the hardening below.  The
    # return value used to be thrown away at this very statement.
    _seam_anchor_idx: set = set()
    if SEAM_FIELD_ANCHORS and dem is not None and _cut_lines:
        _seam_anchor_idx = _seam_spine_anchors(
            layout, G, u_spine_adj, elev, base_hard,
            dem, tile_lat, tile_lon, _cut_lines)

    # TRUTH anchors — everything hard BEFORE the phase-A spine freeze
    # (runway/CIFP + tile-seam DEM pins + runway joins + building spine
    # seats).  The spine-yield projection below may move any node NOT in
    # this set.
    truth_hard = {i for i in range(n) if base_hard[i]}
    # ── THE UNATTRIBUTED HARDENING CHANNEL, MADE COUNTABLE ────────────
    # The published seam set is labelled from its PUBLISHER; the blanket
    # stays exactly as it was (same label, same ``setdefault`` semantics,
    # so crown-freeze membership is byte-identical) and whatever it still
    # absorbs is reported as ``unattributed_hardening`` — the number the
    # campaign rider asked for.
    _hardening = attribute_seam_spine_hardening(
        _hard_cat, truth_hard, _seam_anchor_idx)
    # No ``except: pass`` around this report — a report that cannot print
    # must fail loudly, not vanish (the same defect this sweep is fixing
    # in the flex block).  ``O4_UI_Utils`` is imported unguarded exactly
    # as the seat-guard report above imports it.
    import O4_UI_Utils as _UI_hh
    _n_resid_cls = sum(1 for _c in _hard_cat.values()
                       if _c == "base_hard:unattributed")
    _UI_hh.vprint(
        1,
        f"  [hard-anchor-attribution] {icao}: seam-spine pass pinned "
        f"{_hardening['pinned']} node(s) "
        f"({_hardening['attributed']} newly labelled seam_spine_anchor, "
        f"{_hardening['pre_classified']} already carried another class); "
        f"blanket absorbed {_hardening['unattributed']} more — "
        f"unattributed_hardening={_hardening['unattributed']}; "
        f"classifier residue base_hard:unattributed={_n_resid_cls}; "
        f"truth_hard={len(truth_hard)} of node space n={n} "
        f"(SOLVE node space, pre-freeze, uncrowned z′).")
    # ══ THE SOLVE CORE — MODE-DISPATCHED (constructive-solve round,
    # docs/specs/constructive-solve-spec.md) ══════════════════════════
    # Everything ABOVE this line (node list, seeds, anchors, the one
    # graph, the reach band, seats, floors, EAT guards) and everything
    # BELOW the two branches (crown, writeback, law-store carry,
    # zone/RESA/gap writebacks, reports) is ONE shared frame.  Flipping
    # ``solve_model`` changes ONLY the core between them — the
    # mode-isolation gate (iterative builds byte-identical) rests on the
    # iterative branch below being the pre-round code, unedited, merely
    # indented into the ``else``.
    if _solve_constructive:
        from .constructive import constructive_core as _constructive_core
        _cc = _constructive_core(
            layout=layout, icao=icao, elev=elev, base_hard=base_hard,
            nodes=nodes, bucket_to_idx=bucket_to_idx, n=n,
            dem_elev=dem_elev, runway_nodes=runway_nodes,
            shape_constraints=shape_constraints, G=G,
            u_spine_adj_airside=u_spine_adj_airside,
            u_spine_floor=u_spine_floor, node_band=node_band,
            building_seats=building_seats, hard_cat=_hard_cat,
            near_miss_edges=_near_miss_edges,
            u_pair_stage=_u_pair_stage,
            detached_pads=_detached_pads, pad_frontage=_pad_frontage,
            seam_pin_idx=_seam_pin_idx,
            gap_spine_chains=_gap_spine_chains,
            gap_spine_b_idx=_gap_spine_b_idx,
            zone_idx=_zone_idx, resa_idx=_resa_idx,
            terrain_first=_terrain_first, iyf=_iyf)
        # The locals the shared publication tail reads, bound from the
        # constructive core (the iterative branch binds the same names
        # in its own flow).
        u_edges = _cc.u_edges
        _u_family_of = _cc.u_family_of
        _gs_hard = _cc.gs_hard
        _solve_broken_idx = _cc.solve_broken_idx
        yield_hard = _cc.yield_hard
        rem, bh, n_free = _cc.rem, _cc.bh, _cc.n_free
        frozen = _cc.frozen
        _spine_phase_a = _cc.spine_phase_a
        _spine_preserved = _cc.spine_preserved
        _spine_yield_idx = _cc.spine_yield_idx
        _mover = _cc.mover
        _string_pins = _cc.string_pins
        _summary = _cc.summary
        _fairing_moved_keys = _cc.fairing_moved_keys
        _scoped_gate = _cc.scoped_gate
    else:
        # ── LIVING-BAND INSTRUMENT + CONSTRUCTIVE WARM START (owner
        # ruling 2026-08-15, post in-sim A/B: ITERATIVE IS THE
        # PRODUCTION MODEL; the constructive core is parked behind
        # ``solve_model``.  Two grafts from it live here, in the
        # iterative branch, both kill-switchable:
        #
        # (a) THE INSTRUMENT (``O4_BAND_INSTRUMENT=0`` disables;
        #     REPORT-ONLY, moves no value): the living band from the
        #     TRUE anchors alone (CIFP thresholds + tile-seam pins,
        #     AMENDMENT 1's A1 set) with A4 provenance, auditing every
        #     other hard anchor's stamped value against it.  A hard
        #     anchor outside that band is a contradiction this model
        #     ABSORBS silently at solve time — the K1b A/B showed the
        #     absorbed class at HECA is ~14.5 m deep (rwy 05C/23C
        #     interior vs 05L/23R threshold cone).  Rows on
        #     ``layout._band_instrument_findings``, each naming its
        #     floor- and ceiling-minting anchor.
        #
        # (b) THE WARM START — RETIRED BY MEASUREMENT, default OFF
        #     (``O4_ITER_WARM_START=1`` re-enables for study).  The
        #     owner's in-sim evaluation was the acceptance and it
        #     FAILED: "something is flattening a big area for
        #     kilometers around CYXY."  Measured off-vs-on: |Δemitted|
        #     p90 8.12 m / max 22.71 m at 1.5-2 km from the field,
        #     GROWING with distance — the Lipschitz-regularized
        #     carrier is itself a flattener far from anchors (cone
        #     midpoints, not terrain), graded groundside law (4 %) is
        #     slack enough to keep it, and DEM deviation is
        #     deliberately not a census family so no instrument could
        #     see it.  Scoping the reseed to graded roles changed
        #     NOTHING (byte-identical): the distortion propagates
        #     through graded groundside surfaces, not the traces.
        #     Benefits measured at retirement: census −2 rows at HECA
        #     (noise), final-projection movement p50 −0.06 m at CYXY,
        #     wall time within single-run noise — not worth moving
        #     terrain the owner never asked to move.
        _bi_on = _os.environ.get("O4_BAND_INSTRUMENT", "1") != "0"
        _ws_on = _os.environ.get("O4_ITER_WARM_START", "0") == "1"
        if _bi_on or _ws_on:
            from .one_solve import envelope_radj as _era_ws
            from .one_solve import law_edge_limits as _lel_ws
            from .one_solve import reach_envelope as _re_wb
            _t_wb = _time.time()
            # ONE band (single-pass principle): the true-anchor band
            # was built beside the §4 seat guard above; the instrument
            # reads it, and the warm start clamps into it.  The warm
            # start's CARRIER regularization, by contrast, is a seed
            # SMOOTHER, not a feasibility claim — it keeps the FULL
            # pair-law adjacency (the owner's route ruling narrows
            # what may carry the CONE, not what may smooth a seed).
            _el_ws, _il_ws, _esk_ws = _lel_ws(
                shape_constraints, n, include_flat_pairs=True)
            _cra_wb, _fra_wb = _era_ws(
                _el_ws, _il_ws, _esk_ws, interval_yield_from=_iyf)
            _p0_wb = _tab_p0
            _band_wb = _tab_band
            if _bi_on:
                _bi_rows: list = []
                for _i in range(n):
                    if not base_hard[_i] or _i in _p0_wb:
                        continue
                    _v = float(elev[_i])
                    _lo, _hi = _band_wb.interval(_i)
                    _under = _lo is not None and _v < _lo - 1e-6
                    _over = _hi is not None and _v > _hi + 1e-6
                    if not (_under or _over):
                        continue
                    _fa, _fm, _ca, _cm = _band_wb.bounding(_i)
                    _bi_rows.append({
                        "deficit": float((_lo - _v) if _under
                                         else (_v - _hi)),
                        "node": int(_i), "value": _v,
                        "band_lo": _lo, "band_hi": _hi,
                        "minter": _hard_cat.get(
                            _i, "base_hard:unattributed"),
                        "floor_anchor": _fa, "floor_minter": _fm,
                        "ceil_anchor": _ca, "ceil_minter": _cm,
                        "ll": tuple(layout.m_to_ll(*nodes[_i])),
                    })
                _bi_rows.sort(key=lambda r: (-r["deficit"], r["node"]))
                layout._band_instrument_findings = _bi_rows
                # Full-row dump for the fixing queue (findings are
                # otherwise in-memory only): O4_BAND_INSTRUMENT_DUMP=
                # /path.json writes every row, not the top-5 print.
                _bi_dump = _os.environ.get("O4_BAND_INSTRUMENT_DUMP")
                if _bi_dump:
                    import json as _json_bi
                    # The BOUNDING PATH for the worst rows (A4's
                    # debugging half): the exact law-edge chain that
                    # carries the binding cone, so a tight ceiling can
                    # be attributed to real taxiway chains vs a false
                    # bridge (the wrong-pair-graph class).
                    for _r in _bi_rows[:10]:
                        _i_r = _r["node"]
                        _side = (-1 if (_r["band_lo"] is not None
                                        and _r["value"]
                                        < _r["band_lo"]) else +1)
                        _chain = _band_wb.bounding_path(_i_r, _side)
                        _lab = (_band_wb.floor if _side < 0
                                else _band_wb.ceil)
                        _r["bound_side"] = ("floor" if _side < 0
                                            else "ceil")
                        _r["bound_path"] = [
                            (int(_k), round(nodes[_k][0], 2),
                             round(nodes[_k][1], 2),
                             round(float(_lab.get(_k, 0.0)), 3),
                             tuple(round(_x, 6) for _x in
                                   layout.m_to_ll(*nodes[_k])))
                            for _k in _chain if _k < len(nodes)]
                    with open(_bi_dump, "w") as _fh_bi:
                        _json_bi.dump({"icao": icao, "rows": _bi_rows},
                                      _fh_bi, indent=1)
                if _bi_rows:
                    import O4_UI_Utils as _UI_bi
                    _UI_bi.vprint(1,
                        f"  [band-instrument] {icao}: {len(_bi_rows)} "
                        f"hard anchor(s) OUTSIDE the true-anchor band "
                        f"(absorbed contradictions, named; report-"
                        f"only).  Worst:")
                    for _r in _bi_rows[:5]:
                        _UI_bi.vprint(1,
                            f"  [band-instrument]   {_r['minter']} at "
                            f"node {_r['node']} "
                            f"({_r['ll'][0]:.6f},{_r['ll'][1]:.6f}): "
                            f"value {_r['value']:.3f} vs band, "
                            f"deficit {_r['deficit']:.3f} m (floor by "
                            f"{_r['floor_minter']}@{_r['floor_anchor']}"
                            f", ceiling by "
                            f"{_r['ceil_minter']}@{_r['ceil_anchor']})")
            if _ws_on:
                # ── SCOPE: GRADED-PAVEMENT NODES ONLY (owner in-sim
                # report 2026-08-15: "something is flattening a big
                # area for kilometers around CYXY").  The first cut
                # re-seeded EVERY soft node; measured off-vs-on at
                # CYXY: |Δemitted| p90 8.12 m / max 22.71 m at
                # 1.5-2 km from the field — boundary/zone/clearance
                # TERRAIN TRACES rode the carrier instead of raw DEM
                # (adjacent-ground zone law: beyond the zones, raw DEM
                # governs), and DEM deviation is deliberately not a
                # census family, so only the in-sim eye could catch
                # it.  Re-seeding is now confined to nodes claimed by
                # a shape whose role carries a grade law
                # (ROLE_GRADE_LIMITS non-None — the surfaces the
                # projections iterate on); terrain traces and the
                # zone/RESA leaves keep their raw seeds.
                from auto_patch.config import (
                    ROLE_GRADE_LIMITS as _RGL_ws)
                _graded_roles_ws = {r for r, _lim in _RGL_ws.items()
                                    if _lim is not None}
                _cps_ws = layout.canonical_points
                _ws_scope: set = set()
                for _s in layout.shapes:
                    if (_s.role not in _graded_roles_ws
                            or _s.polygon is None
                            or _s.polygon.is_empty):
                        continue
                    _ring_ws = list(_s.polygon.exterior.coords)
                    for (_x, _y) in (_ring_ws[:-1]
                                     if _ring_ws
                                     and _ring_ws[0] == _ring_ws[-1]
                                     else _ring_ws):
                        _iw = bucket_to_idx.get(
                            _cps_ws.get_or_add(float(_x), float(_y)))
                        if _iw is not None and _iw < n \
                                and (_iyf is None or _iw < _iyf):
                            _ws_scope.add(_iw)
                _src_wb = list(range(n))
                _cr_wb, _ = _re_wb(+1, _cra_wb, _src_wb, elev, n)
                _fr_wb, _ = _re_wb(-1, _fra_wb, _src_wb, elev, n)
                _n_ws = 0
                for _i in range(n):
                    if base_hard[_i] or _i not in _ws_scope:
                        continue
                    _c = _cr_wb.get(_i)
                    _f = _fr_wb.get(_i)
                    if _c is None and _f is None:
                        continue
                    _v = (float(_c) if _f is None else float(_f)
                          if _c is None else 0.5 * (float(_c)
                                                    + float(_f)))
                    _lo, _hi = _band_wb.interval(_i)
                    if _lo is not None and _v < _lo:
                        _v = float(_lo)
                    if _hi is not None and _v > _hi:
                        _v = float(_hi)
                    if _v != elev[_i]:
                        elev[_i] = _v
                        _n_ws += 1
                import O4_UI_Utils as _UI_ws
                _UI_ws.vprint(1,
                    f"  [warm-start] {icao}: {_n_ws} soft seed(s) "
                    f"re-seeded on the constructive carrier "
                    f"(Lipschitz-regularized, band-clamped; "
                    f"{_time.time() - _t_wb:.1f} s incl. instrument) "
                    f"— seeds only, every solve pass still owns the "
                    f"values.")
        # PHASE A — dedicated SMOOTH spine solve on the unified graph (geometry
        # nodes), runway/seam HARD at their LOCAL value, building floors honoured.
        # The spine is min-curvature and ≤cap by construction, then FROZEN so the
        # body grades to it (the body twists to meet the spine, never the reverse).
        # Stage probe (P3 drag attribution) — allocated ONLY when the dump
        # gate is set; ``None`` keeps every production call unchanged.
        _spine_probe = ({} if _os.environ.get("O4_DUMP_SOLVE_STATE")
                        else None)
        # ── S1b: CHORD TARGETS AS DIRICHLET BOUNDARIES (docs/specs/
        # s1b-first-class-chord-boundaries-spec.md §1) ─────────────────
        # The harmonic owns 67.1 % of the corridor's departure from DEM
        # and has NO altitude preference of its own — it interpolates
        # toward whatever the network does.  Giving it the strings as
        # BOUNDARIES is what supplies that preference, so the strings
        # enter phase A ONCE, here, instead of overwriting its interiors
        # afterwards (the α single-pass violation, now closed).
        # ★ PRE-FREEZE ANCHORS: ``base_hard`` has not yet absorbed the
        # spine freeze at this point (that happens below, on ``frozen``),
        # and the hook contract's hazard follows the code — pass the
        # TRUTH set, never a post-freeze one.
        # ★ RULING 52 — the chord is never bent by law; the GRIP is.  A
        # pin joins ``anchors``, so fairing and the exact cap projection
        # can no longer drive a both-pinned pair to its cap; the pin SET
        # is therefore law-filtered first and the released stations are
        # handed back to the solver to ride their cap toward the chord.
        # Gate off ⇒ never imported, never computed ⇒ phase A
        # byte-identical.
        _string_pins = None
        _grip_yields: list = []
        # Bound unconditionally: ``_summary`` is written in the gated
        # block below and read again at the yield site (ruling 54).  A
        # name bound only inside a branch is the UnboundLocalError class
        # the SPLP/CYXY identity build caught in this very function.
        _summary: dict = {}
        # PARKED FEATURE — NOT A LAW GATE (integration sweep 2026-08-05).
        # The taut-string machinery is the owner's PAUSED feature: the strings
        # verdict is pending (memory ``string-purpose-statement``: strings are a
        # smoothing refinement for otherwise-correctly-graded taxiways, NOT a
        # surface authority), so this switch is deliberately NOT deleted with
        # the law gates.  It selects whether a PARKED feature runs at all, not
        # which law the build obeys.  Retire or adopt it when the owner rules.
        if _os.environ.get("O4_TAUT_STRING_CONSTRUCTION", "0") == "1":
            from auto_patch.config import TAXI_MAX_GRADE as _TAUT_CAP_DEF
            from .taut_string import construct_taut_strings as _cts
            from .taut_string import filter_pins_by_grade_law as _grip
            _taut_cap: dict = {}
            for _si, _slst in u_spine_adj.items():
                for (_sj, _sbudget) in _slst:
                    _spk = (_si, _sj) if _si < _sj else (_sj, _si)
                    if _spk in _taut_cap:
                        continue
                    _sdist = _GG._dist(G.pos.get(_si), G.pos.get(_sj))
                    if _sdist > 1e-9:
                        _taut_cap[_spk] = float(_sbudget) / _sdist

            def _taut_cap_of(_a, _b):
                return _taut_cap.get((_a, _b) if _a < _b else (_b, _a),
                                     _TAUT_CAP_DEF)

            _raw_pins = _cts(
                layout, G, elev=elev, bucket_to_idx=bucket_to_idx, n=n,
                node_band=node_band,
                hard=(truth_hard | {i for i in runway_nodes if i < n}
                      | {i for i in building_seats if i < n}),
                # ── STAGE A'S ROUTE GRAPH HAS NO SERVICE CENTERLINES
                # (S1c, couplings 7/8/16) ──────────────────────────────
                # The strings built here become DIRICHLET PINS into phase A,
                # so this is an AIRSIDE authority that WRITES values — the
                # same standing that made ``_solve_spine_profile`` apply the
                # ``service_spine_pairs`` exclusion internally (cycle 8) and
                # that ``reach_band_unified`` has obeyed since
                # REACH_NO_SERVICE_SPINES.  These two consumers simply
                # predate it: ``_build_spine_corridors`` cut its pieces from
                # the RAW graph, and ``taut_string.walk_spine_runs`` builds
                # its walk adjacency from whatever it is handed — it skips
                # service CHAINS but service EDGES stayed walkable, so an
                # airside chain's segmentation (its turns, its gaps) was
                # decided partly by the road network.  Service corridors are
                # stage-B objects entirely and are strung, solved and
                # emitted there.
                corridor_pieces=_build_spine_corridors(u_spine_adj_airside,
                                                       nodes),
                junction_adj=u_spine_adj_airside, cap_of_segment=_taut_cap_of,
                # ── PROBE B (spec §2): pure passengers for the hook-entry
                # state dump.  ``_hard_cat`` is passed as a COPY so the
                # callee cannot alias a set the solver iterates.
                # ⚠ ``_have_initial`` is NOT the warm-start/DEM splitter
                # the spec assumed — every seeding branch sets it, so it
                # reads True for every node (see the constructor's
                # docstring).  It ships as specified; do not read a P0
                # sub-class out of it.  Neither is read by the callee.
                hard_cat=dict(_hard_cat),
                have_initial=_have_initial)
            # ★ ``_store_of`` is imported at MODULE level (line ~20) and
            # used unconditionally later in this function.  Re-importing
            # it HERE would make the name function-LOCAL, so with the gate
            # OFF the later uses raise UnboundLocalError — a gate-off
            # break, which is exactly what the identity build caught.
            # Use the module-level binding; never shadow it.
            _summary = (_store_of(layout).raw("string_domains") or {}).get(
                "__summary__", {})
            # ★ FIX ARM §1 — GRIP COMPLETENESS.  ``elev`` supplies the
            # HARD side's value so the filter can also examine pin-vs-hard
            # pairs (a pin one spine edge from a seat / runway join / seam
            # was never enumerated, and the mover ledger proved those 88
            # ``law_anchor`` conflicts are STATIC — born right here).  The
            # hard set is the one this call already used; the array is read
            # only, and hard values are stamped by P0-P5 well before this
            # point.  Inside the string gate: gate off ⇒ never reached.
            # ★ ROUND 2 §1a — THE GRIP'S PAIR GRAPH IS THE LAW'S.
            # ``shape_constraints`` is the ONE constraints object this
            # solve built at its top (well BEFORE this hook — the round-2
            # spec's premise that the build follows the hook is stale;
            # nothing is reordered and nothing is rebuilt).  Its edges
            # stream through the grip in a single pass, so the pin pair
            # universe also contains the junction/apron RING edges the
            # spine graph does not carry, and (§1b) the two-hop pairs
            # through one free node.  The counter proves no second build.
            from auto_patch.elevation_per_surface import (
                solver_primitives as _sp_audit)
            _sc_builds_before = _sp_audit.SHAPE_CONSTRAINT_BUILDS
            _grip_stats: dict = {}
            # THE LAZY TIER IS A HOLE IN THE STREAM, MEASURED not assumed:
            # a flatness-CERTIFIED apron/junction entry carries only its
            # ring-adjacent pairs eagerly (the body pairs live behind
            # ``lazy_expand``).  Expanding them here would be the second
            # build the spec forbids, so the grip reads what the entry
            # holds — and this counts the entries where that could hide a
            # pin-vs-pin pair, so a residual can be attributed instead of
            # explained away.
            _lazy_entries = 0
            _lazy_multi_pin = 0
            for _sc_e in shape_constraints:
                if _sc_e.get("lazy_expand") is None:
                    continue
                _lazy_entries += 1
                if sum(1 for _li in (_sc_e.get("lazy_nodes") or ())
                       if _li in _raw_pins) >= 2:
                    _lazy_multi_pin += 1
            _grip_stats["n_lazy_entries"] = _lazy_entries
            _grip_stats["n_lazy_entries_with_2plus_pins"] = _lazy_multi_pin
            _t_grip = _time.time()
            _string_pins, _grip_yields = _grip(
                _raw_pins, u_spine_adj,
                hard=(truth_hard | {i for i in runway_nodes if i < n}),
                endpoint_depth=_summary.get("pin_depth") or {},
                elev=elev,
                law_edges=_law_edge_stream(shape_constraints),
                stats_out=_grip_stats)
            _grip_stats["grip_seconds"] = _time.time() - _t_grip
            _grip_stats["shape_constraint_builds_during_grip"] = (
                _sp_audit.SHAPE_CONSTRAINT_BUILDS - _sc_builds_before)
            _grip_stats["n_constraint_entries"] = len(shape_constraints)
            assert _grip_stats["shape_constraint_builds_during_grip"] == 0, (
                "the grip must consume the solve's ONE constraints object")
            # ── ROUND 4 §1: PINS LIVE ON THE FROZEN GRAPH ─────────────
            # The grip has finished; ``_kept_by_grip`` is its answer.  Now
            # drop the targets the phase-A solve structurally cannot hold
            # (see ``_pins_on_frozen_graph``).  ONE rebinding of
            # ``_string_pins`` covers every consumer at once — the phase-A
            # ``string_pins=`` argument, Ruling 54's ``yield_hard``, the
            # mover watch set, the final-hold export and the G2/pin-drag
            # delivery all read this name and nothing else.  Off-graph
            # targets are ledgered below and never applied anywhere.
            _kept_by_grip = _string_pins
            _string_pins, _pins_off_graph = _pins_on_frozen_graph(
                _kept_by_grip, u_spine_adj, n)
            # ── THE PIN LEDGER, stamped with its grip disposition ─────
            # Production is the only place that knows which vertices were
            # pinned and to what value; the offline re-walk has failed to
            # reproduce it three times.  So the disposition ships in the
            # sidecar, and ``max |emitted - chord|`` at kept pins becomes
            # a one-line check on the next build.
            _off_graph_strings, _n_off_targets = _stamp_pin_ledger(
                _summary.get("pins", ()), _string_pins, _pins_off_graph,
                u_spine_adj, n)
            _summary["n_targets"] = len(_raw_pins)
            # ★ ARITHMETIC: n_targets = n_pins_kept + n_pins_off_graph
            #   + n_released.  ``n_pins_kept`` is the APPLIED set (what the
            # solve holds); the release counts keep their old meaning (what
            # the grip's law filter released), so no existing reader's
            # number changes meaning silently — the new third bucket is
            # named, not folded into either.
            _summary["n_pins_kept"] = len(_string_pins)
            _summary["n_pins_off_graph"] = len(_pins_off_graph)
            # the TARGET-level count (rows with ``pin_frozen`` false):
            # off-graph pins the grip already released are counted here and
            # NOT in ``n_pins_off_graph`` — two populations, never mixed.
            _summary["n_targets_off_graph"] = _n_off_targets
            _summary["pins_off_graph_strings"] = _off_graph_strings
            _summary["n_released"] = len(_raw_pins) - len(_kept_by_grip)
            _summary["n_over_cap_pairs"] = len(_grip_yields)
            # kept under their old names too — a renamed key silently
            # breaks whatever already reads the sidecar.
            _summary["n_pins_offered"] = len(_raw_pins)
            _summary["n_pins_released"] = len(_raw_pins) - len(_kept_by_grip)
            _summary["n_grip_yields"] = len(_grip_yields)
            _summary["grip_yields"] = _grip_yields
            # ROUND 2 §3 delivery: the pair universe the grip actually
            # filtered on, its runtime, and the single-build proof.
            _summary["grip_pair_universe"] = _grip_stats
            # ★ WRITE THE SIDECAR LAST.  The constructor no longer writes
            # it: the filter runs here, after the constructor returned, so
            # a write during construction could never carry these counts —
            # which is exactly why the log line proved the treatment ran
            # while the sidecar could not.
            from .taut_string import write_string_sidecar as _write_sidecar
            _write_sidecar(layout)
            if _os.environ.get("O4_STEP_DEBUG") == "1":
                print(f"    [S1b] n_targets={len(_raw_pins)} "
                      f"n_pins_kept={len(_string_pins)} "
                      f"n_pins_off_graph={len(_pins_off_graph)} "
                      f"n_released={len(_raw_pins) - len(_kept_by_grip)} "
                      f"n_over_cap_pairs={len(_grip_yields)} "
                      f"(all five in the domains sidecar)")
                if _pins_off_graph:
                    print(f"    [S1b off-graph] {len(_pins_off_graph)} kept "
                          f"target(s) have no u_spine_adj entry ⇒ the "
                          f"phase-A freeze cannot hold them; ledgered, not "
                          f"applied; string(s) {_off_graph_strings}")
                print(f"    [S1b] grip pair universe: "
                      f"{_grip_stats['n_pairs']} pair(s) from "
                      f"{_grip_stats['n_law_edges_in']} within-shape law "
                      f"edge(s) over {_grip_stats['n_constraint_entries']} "
                      f"constraint entrie(s) + spine_adj; "
                      f"by rule {_grip_stats['n_pairs_by_rule']}; "
                      f"over-cap {_grip_stats['n_over_by_rule']}; "
                      f"two-hop {_grip_stats['n_two_hop_pairs_offered']} "
                      f"pair(s) over "
                      f"{_grip_stats['n_two_hop_free_nodes']} free node(s); "
                      f"tightened {_grip_stats['n_pairs_tightened']}; "
                      f"lazy entries {_grip_stats['n_lazy_entries']} "
                      f"({_grip_stats['n_lazy_entries_with_2plus_pins']} "
                      f"with 2+ pins); "
                      f"{_grip_stats['grip_seconds']:.3f} s; "
                      f"second constraints build(s) during grip="
                      f"{_grip_stats['shape_constraint_builds_during_grip']}")
        frozen, _rod_pieces = _solve_spine_profile(
            elev, base_hard, u_spine_adj, u_spine_floor, node_band,
            nodes_xy=nodes, graph=G, probe_out=_spine_probe,
            string_pins=_string_pins)
        # ── SPINE-FREEZE ROUND: the yield-hard set and the preserved set ──
        # (STANDING LAW; see the module comment above
        # ``_spine_yield_membership``.)  Built BEFORE the freeze loop
        # because ``truth_hard`` is precisely "hard before the freeze" and
        # the loop is what makes the difference invisible.  The preserved
        # set is ENUMERATED here, not implied: a spine node that is also a
        # runway/CIFP value, a runway join, a seat, a detached-pad pin or a
        # tile-seam pin is LAW and never yields.
        _spine_phase_a: dict = {}
        _spine_preserved, _spine_yield_idx = _spine_yield_membership(
            frozen, n,
            truth_hard=truth_hard,
            runway_nodes=runway_nodes,
            building_seats=building_seats,
            runway_anchor=G.runway_anchor,
            seam_pins=_seam_pin_idx,
            seat_stamp_yield=_seat_yield_idx)
        for i in frozen:
            if i < n:
                # §4: a seat the hard-stamp guard refused is not
                # re-frozen by the phase-A freeze either — it was never
                # phase-A TRUTH, only a phase-A estimate the projection
                # was free to move.
                if i in _seat_yield_idx:
                    continue
                base_hard[i] = True
        if _spine_yield_idx:
            # THE phase-A values, snapshotted for the FORENSIC movement
            # report (they are no longer an authority — nothing downstream
            # is pulled toward them).  Taken here, one statement after the
            # freeze: phase B holds these nodes hard (they are
            # ``base_hard``), so this is also their value at the first
            # projection's entry — the honest "phase-A value".
            _spine_phase_a = {i: float(elev[i]) for i in _spine_yield_idx}
            try:
                import O4_UI_Utils as _UI_sy
                _UI_sy.vprint(1,
                    f"  [spine-yield] {icao}: {len(frozen)} frozen spine "
                    f"node(s); {len(_spine_yield_idx)} enter the downstream "
                    f"projections FREE (yield-hard membership), "
                    f"{len({i for i in frozen if i < n} & _spine_preserved)} "
                    f"preserved base_hard (runway/CIFP/seat/seam).")
            except Exception:
                pass
        _psub(0.62, "Solving elevations — spine profile solved")

        # (The sloping-rect flat-end stamp that lived here was RETIRED by
        # spec §10.2 — the global slice emits no rect roles and no end
        # caps; role census across all fixtures measured zero.)
        # PHASE B — body fill (apron/junction interiors + rect bodies + caps) with
        # the spine frozen.  Apron body = 1% VISIBILITY/GEODESIC smoothing within
        # the reach band [floor, ceiling] (apron_smooth=True) — graded ≤1% from its
        # anchored edges/spine, NOT draped on raw DEM bumps (user 2026-06-26).  The
        # band still fills it to the reachable level (west apron → ~693).
        # RECEIVER-ONLY IN THE BODY SOLVE (cycle 9; ATTRIBUTED by probe, not
        # guessed).  ``one_profile_solve`` makes every node of ``spine_adj`` a
        # SPINE node and clamps it to its adjacency — and "the apron body yields
        # to the spine instead of squeezing it out of grade".  With the road feed
        # in the one graph that made TRUCK ROUTES into spines the aprons yield
        # to: withholding the service edges from the graph (and nothing else)
        # returned HECA -500 airside from 4,581 to 4,150 of a 4,129 baseline and
        # KCLT -500 from 522 to 484 of 473 — i.e. ~95 % / ~78 % of the airside
        # rise is carried HERE, by the graph edges, not by the pair law.
        # ``_solve_spine_profile`` (phase A) already drops exactly this pair set
        # (cycle 8); the body solve simply never did.  Direction, not deletion:
        # the road pairs remain law in the partitioned projections and the road
        # is still seated as a receiver from its mouth band.
        _body_adj = u_spine_adj_airside
        # a node left with only road edges is not an aircraft spine node
        _body_nodes = ({i for i in u_spine_nodes if i in _body_adj}
                       if _svc_pairs else u_spine_nodes)
        if _svc_pairs:
            _UI_env.vprint(1,
                f"  [body-solve] {icao}: spine set {len(u_spine_nodes)} -> "
                f"{len(_body_nodes)} node(s), adjacency {len(u_spine_adj)} -> "
                f"{len(_body_adj)} node(s) after excluding "
                f"{len(_svc_pairs)} service spine pair(s)")
        n_free = one_profile_solve(
            elev, shape_constraints, base_hard, nodes, dem_elev,
            runway_nodes, building_seats, apron_body, _body_nodes, _body_adj,
            node_band, u_spine_floor, coupling, apron_smooth=True)
        _psub(0.78, "Solving elevations — body fill solved")
        # Guarantee compliance: project EVERY grade-graph edge ≤cap with the
        # spine + runway + buildings + seams HARD; only the apron/junction body
        # flexes.  Edges left over cap have both ends hard = genuine steps.
        hard = {i for i in range(n) if base_hard[i]}
        hard |= {i for i in runway_nodes if i < n}
        hard |= {i for i in building_seats if i < n}
        # SPINE-FREEZE ROUND: the frozen spine leaves the HARD membership
        # — a value certified on the 1.5-4.8 k-edge phase-A subgraph is an
        # ESTIMATE against this 64-272 k-edge law, so it settles where the
        # full graph admits instead of forcing a contradiction.
        # ``_spine_yield_idx`` already excludes every preserved class, so
        # this subtraction can never release a runway/CIFP value, a seat
        # or a seam pin.
        hard -= _spine_yield_idx
        # ── APRON TERRACE LAW (owner ruling 2026-08-04; spec
        # ``docs/specs/apron-terrace-law-spec.md``; gate
        # ``O4_APRON_TERRACE_LAW``, default off) ──────────────────────
        # THE PANELIZATION IS NOT HERE ANY MORE — it ran before the solve
        # (``pipeline`` -> ``construct_apron_terrace_presolve``), which is
        # what makes the panel boundary a set of SOLVE VARIABLES instead of
        # geometry invented after the surface settled.  What runs here is
        # the BINDER: it resolves that declaration into this pass's index
        # space and hands the projections the actual-step edges.  HERE, and
        # not later, because the plan must bind every downstream projection
        # through the SAME ``shape_constraints`` object.
        _terrace_plan = None
        from .apron_terrace import (apply_terrace_budgets,
                                    plan_apron_terraces)
        try:
            _terrace_plan = plan_apron_terraces(
                layout, shape_constraints, nodes, dem_elev, elev,
                hard, icao=icao, bucket_to_idx=bucket_to_idx)
            _n_relaxed = apply_terrace_budgets(
                _terrace_plan, shape_constraints, nodes)
            layout._apron_terrace_plan = _terrace_plan
            # ── THE FAN-RAMP LAW joins the SAME shape_constraints object
            # (owner RULINGS 21f0980).  The zones were built pre-solve with
            # the panelization; here their interior pairs enter the ONE solve
            # at the 5 % zone cap as ordinary law edges, and a surface
            # fanning between the two building seat levels is what the system
            # solves to.  Movement surfaces are untouched — a pair only
            # relaxes when its whole chord is inside one zone.
            from .apron_terrace import apply_fan_ramp_caps as _apply_fan
            _fan_plan = getattr(layout, "_fan_ramp_plan", None)
            _n_fan = _apply_fan(_fan_plan, shape_constraints, nodes)
            if _n_fan:
                import O4_UI_Utils as _UI_fan
                _UI_fan.vprint(1,
                    f"  [fan-ramp] {icao}: {_n_fan} within-apron law edge(s) "
                    f"raised to the {_fan_plan.zones[0]['cap'] * 100:.0f} % "
                    f"zone cap across {_fan_plan.stats['zones']} zone(s)")
            if _terrace_plan is not None:
                import O4_UI_Utils as _UI_terr
                _UI_terr.vprint(1,
                    f"  [apron-terrace] {icao}: "
                    f"{_terrace_plan.stats['triggered']} apron(s) "
                    f"panelized, {_terrace_plan.stats['joints']} "
                    f"declared joint(s), {_n_relaxed} law edge(s) "
                    f"bound to a joint step; "
                    f"{_terrace_plan.stats['joint_step_pairs']} "
                    f"joint-step pair constraint(s), "
                    f"{_terrace_plan.stats['facing_edges_excluded']} "
                    f"facing-boundary edge(s) held at full law, "
                    f"{_terrace_plan.stats['facing_conformance_pairs']}"
                    f" conformance pair(s), "
                    f"{_terrace_plan.stats['joints_stillborn_keepout']}"
                    f" stillborn; apron area "
                    f"{_terrace_plan.area_fraction() * 100:.1f} % "
                    f"(REPORT ONLY)")
        except Exception as _terr_exc:
            # A production build must never die on an optional law
            # pass — but a MEASUREMENT arm that silently produces the
            # default surface is worse than a crash (it reads as "the
            # law did nothing", which is a result).  Under the debug
            # gate the failure is raised.
            import O4_UI_Utils as _UI_terr
            _UI_terr.vprint(1, f"  [pav-builder] WARN: {icao}: apron "
                               f"terrace plan failed ({_terr_exc}) — "
                               f"no panelization this build.")
            _terrace_plan = None
            if _os.environ.get("O4_APRON_TERRACE_DEBUG") == "1":
                raise
        # ── NON-ROUTE SEED ADMISSION (spec ``route-metric-envelope`` §2;
        # gate ``O4_ROUTE_METRIC_ENVELOPE``, default "1" since the
        # 2026-08-04 kill-half flip) ─────────────────────────────────
        # "A hard anchor whose node carries NO route-pavement role may not
        # seed the airside feasibility envelope in ANY pass."  ONE role
        # scan for this whole solve; ``feasibility_project`` intersects it
        # with each pass's own hard set.  ``_hard_cat`` is the solve's own
        # provenance map for the role-unmatched anchors (spec §2: they are
        # CLASSIFIED, never dropped blind).  Gate off ⇒ ``None`` passed
        # everywhere ⇒ byte-identical.
        _rm_roles, _rm_route_roles, _route_excluded = (
            _route_witness_admission(layout, bucket_to_idx, n))
        if route_metric_envelope_enabled():
            _rm_excl, _rm_rep = _non_route_witness_nodes(
                _rm_roles, _rm_route_roles, hard, n, provenance=_hard_cat)
            _route_excluded |= _rm_excl
            _report_witness_admission(icao, "solve", _rm_rep)
        else:                                              # pragma: no cover
            _route_excluded = None
        # ── THE PROJECTION PARTITIONS, SOLVE SIDE (spec addendum) ─────────
        # The same receiver set the final projection uses, in the SOLVE's node
        # space.  EVERY projection of this solve partitions, not only fp#8:
        # the addendum says "in every projection", and a phase-A/B pass that
        # still co-projects the two sides hands fp#8 an airside seed a
        # groundside pair already moved — measured as a 1-2 row canyon
        # flutter (HEAZ 10 000 +2, KCLT 10 000 +1) that survived partitioning
        # the last three sites alone.
        _solve_receivers = _receiver_nodes_from_roles(_rm_roles,
                                                      _gap_spine_b_idx)
        rem, bh = feasibility_project_partitioned(
                                      elev, shape_constraints, hard,
                                      receiver_nodes=_solve_receivers, n_nodes=n,
                                      interval_yield_from=_iyf,
                                      witness_excluded=_route_excluded,
                                      env_band=_env_band)
        # Project on the UNIFIED graph's OWN edges too (the EXACT pairs/caps the
        # validator checks — rects/caps all-pair, which shape_constraints only
        # approximates with axial edges), so build and validate cannot leave a
        # residual between them.  The spine stays HARD; only body nodes flex.
        u_edges = [(a, b, cap.at(_GG._dist(G.pos.get(a), G.pos.get(b)), 0.0))
                   for (a, b, cap, _sp) in G.edges
                   if a in G.pos and b in G.pos]
        # THE FAMILY AXIS, TAKEN ONCE (cycle-7 fix 5; single-pass principle).
        # ``family_by_pair`` walks the whole unified edge list, and THREE
        # readers want it now: the SOLVE EXIT certificate below, the fp#8
        # projection's own uncertified-exit family table, and the final
        # projection's ENTRY/EXIT certificates (which rebuild their own graph
        # and take their own map).  Taken here, beside the edge list it is
        # derived from, and handed to both consumers in this scope.
        _u_family_of = G.family_by_pair()
        # THE UNIFIED GRAPH'S OWN MINT-TIME STAGES (staged-solve S1b).  Taken
        # beside the family axis it parallels, once, and handed to every
        # projection below through ``_u_entries``.  Before S1b the whole
        # graph reached each projection as ONE bare ``{"edges": u_edges}``
        # entry with no role key, so every service_road / service_junction /
        # groundside_pavement within-shape law pair was enforced in the
        # AIRSIDE pass (tmp/s1_attribution.md couplings 3 and 6 — with
        # coupling 6 measured as a channel of HECA's corridor +130).
        for _pk_, _st_ in G.stage_by_pair().items():
            _u_pair_stage.setdefault(_pk_, _st_)
        # NEAR-MISS BUILDING-FRONTAGE LAW EDGES (2026-07-08): pad ↔ apron
        # near-miss edge endpoints, budget = APRON_MAX_GRADE·d — the value-
        # agreement law across a sub-metre unpaved source-offset sliver (SPJC
        # building29).  The phase-A/B floors alone don't survive the
        # projections (min-displacement POCS knows caps, not floors, and
        # projects the lift away); as u_edges members these pairs are
        # enforced by every projection INCLUDING the movable-pad final yield
        # GS, which settles pad level and apron edge JOINTLY (pad stays a
        # rigid flat group).  Gate O4_BUILDING_FRONTAGE_NEAR_MISS=0 → no
        # edges, byte-identical.  See anchors.near_miss_building_frontage_edges.
        from .anchors import near_miss_building_frontage_edges
        # (PAD ROD COUPLING — the ``weld_refs_out`` contact map and its
        # ``pad_weld_refs`` store carry — was DELETED with the §7
        # reference channel it fed.  The near-miss frontage LAW EDGES
        # stay: they are ordinary law, enforced by every projection.)
        # ONE PASS (2026-08-06): the near-miss recognition already ran at the
        # band-withhold site above, where the frontage-coupling test needs
        # it; these ARE those edges.  ``near_miss_building_frontage_edges``
        # stays imported there for the one call.
        u_edges.extend(_near_miss_edges)
        # ── CROSS-SECTION LAW EDGES (LEAD RULINGS 2 ruling 1, 2026-08-08) ──
        # PRICED ⟺ BOUND.  The TRANSVERSE census walks each taxi axis and
        # prices the ring span BRACKETING it (|Δz| ≤ cT·width); R-b plants
        # exactly that span's two feet.  The R-b round then MEASURED that
        # the solve leaves those feet within 2 cm of the straight chord and
        # the decimator collapses them — the census was pricing a pair the
        # solve never bound (CYXY apron shapeID 115: 35 planted, 2 emitted,
        # 1.51 m over 17.56 m at the 1 % apron transverse cap).  So the
        # pairs join ``u_edges`` here, beside the near-miss frontage law
        # they follow precedent from, and every projection below enforces
        # them.  R-a is untouched: ``u_edges`` is the SURFACE edge set, not
        # the route graph — ``G.spine_adj`` still skips every foot, so a
        # cross-section constrains elevation and mints no route edge.
        from auto_patch.lateral_spine_nodes import (
            lateral_xsection_law_edges as _xsec_edges)
        _xsec = _xsec_edges(layout, bucket_to_idx, stage_out=_u_pair_stage)
        if _xsec:
            u_edges.extend(_xsec)
            import O4_UI_Utils as _UI_XS
            _UI_XS.vprint(1, f"  [xsection-law] {len(_xsec)} priced "
                             f"cross-section pair(s) BOUND in the solve "
                             f"(|dz| <= cT*width)")
        # APRON TERRACE LAW: the unified graph carries its OWN copy of the
        # apron's all-pair law, so the joint budgets have to be bound onto
        # it too — one law, both edge sets (see
        # ``apron_terrace.apply_terrace_budgets_to_edges``).  Done once,
        # here, because ``u_edges`` is reused by every later projection in
        # this function.  No plan ⇒ the list object is returned unchanged.
        if _terrace_plan is not None:
            from .apron_terrace import apply_terrace_budgets_to_edges
            u_edges, _n_u_relaxed = apply_terrace_budgets_to_edges(
                _terrace_plan, u_edges, nodes)
            if _n_u_relaxed and _os.environ.get("O4_STEP_DEBUG") == "1":
                print(f"    [apron-terrace] {_n_u_relaxed} unified-graph "
                      f"edge(s) bound to a joint step")
        # BOTH EDGE SETS OR NEITHER: relief granted only in
        # ``shape_constraints`` is taken straight back by the unified-graph
        # projection.  Same law, same call shape as the terrace budget.
        from .apron_terrace import apply_fan_ramp_caps_to_edges as _apply_fan_u
        u_edges, _n_u_fan = _apply_fan_u(
            getattr(layout, "_fan_ramp_plan", None), u_edges, nodes)
        if _n_u_fan and _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [fan-ramp] {_n_u_fan} unified-graph edge(s) at the "
                  f"zone cap")
        rem, bh = feasibility_project_partitioned(
                                      elev,
                                      _unified_entries(u_edges, _u_pair_stage,
                                                       "solve/unified"), hard,
                                      receiver_nodes=_solve_receivers, n_nodes=n,
                                      witness_excluded=_route_excluded,
                                      env_band=_env_band)
        # (The end-cap planar re-stamp that lived here was RETIRED by spec
        # §10.2 with the rect flat-end stamp above.)
        # GROUNDSIDE REACH + MOUTH WELD (user 2026-06-27).  Done LAST — after the
        # body solve + feasibility project — so buildings + aprons are anchored:
        #   1. Re-level each groundside piece a service road connects to an apron, to
        #      the elevation the connector can REACH within the service-road grade
        #      cap (apron mouth ± cap·route_len, clamped toward DEM) — so the
        #      connector grades <=cap instead of ramping steeply to the raw DEM.  A
        #      piece with no apron-connected service road stays DEM.
        #   2. Weld each service-road connector mouth to the (re-levelled) groundside
        #      altitude, so connector and groundside emit as ONE node (no cliff).
        # Gate off → elev + groundside untouched → byte-identical.
        _gs_hard = set()
        # Stage G's moved set, bound unconditionally so the mover ledger
        # (probe A) can read it whether or not the groundside gate ran.
        # Re-bound below by ``apply_service_road_dem_follow``.
        _svc_moved: set = set()
        # ── GROUNDSIDE FEASIBILITY-WITNESS CLAUSE (owner ruling 2026-07-30,
        # memory ``groundside-terrace-law``; gate
        # ``O4_GS_NO_AIRSIDE_WITNESS``, default ON) ──────────────────────
        # "Groundside values never act as a feasibility witness (floor or
        # ceiling) for airside pavement beyond the Part-C mouth allowance"
        # — the mirror of the standing ruling that airside reachability
        # never rides service roads or groundside
        # (memory ``free-road-ruling``).
        #
        # Part C already bounds what a groundside pin may BE (its value may
        # not exceed its WELD DATUM — a solved pavement variable — by more
        # than the reach law plus ``cap·MOUTH_ALLOWANCE_M``; item 3(a)
        # replaced the old own-DEM datum, the allowance is unchanged).
        # This bounds what it may DO: the pin stays HARD — groundside is
        # still pinned, and every mouth-weld law edge is still enforced by
        # the sweeps — but it is withdrawn from the reach-envelope anchor
        # set that DECLARES BREAK REGIONS for airside nodes, except within
        # one connector throat of the mouth (the permitted exception,
        # ``anchors.gs_witness_horizon`` — the same scalar as Part C's
        # value bound, in the envelope's budget metric).
        #
        # Why (measured 2026-07-30 by witness-pair forensics,
        # ``O4_BREAK_FORENSICS``): of HECA's 13,428 broken nodes at fp#8, a
        # ``gs_pin`` is the floor or ceiling witness for 12,123 = 90.3 %,
        # median deficit ≈24 m.  Groundside was ASSERTING an authority the
        # owner's law does not grant it.
        #
        # ★ WHAT IT IS NOT.  Withdrawing that authority is NOT curative, and
        # the "strip the class and 802 remain" reading of the forensics table
        # was a CATEGORY ERROR — the table partitions broken nodes by their
        # TIGHTEST witness pair, so removing an anchor class RE-WITNESSES
        # those nodes rather than freeing them.  Measured on this change:
        # fp#8 broken 13,428 → 13,258 (−170, zero new), of which 98.6 % of
        # the 12,123 groundside-witnessed nodes are still broken, now
        # ``seed_rwy_seam`` ↔ ``seed_rwy_seam`` (802 → 11,783, deficit p50
        # 4.0 → 19.6 m).  The residual is a RUNWAY-SEAM-anchor contradiction
        # concentrated in a handful of anchors (one ceiling witness accounts
        # for 8,187 of the 11,783) — that, not groundside, is where the
        # ``feasibility-is-guaranteed`` investigation goes next.
        #
        # ★ BUILD-TIME COST (CLAUDE.md item 6, alternating 3-run A/B on one
        # frozen tree): CYXY 35.4 s → 38.6 s (+3.2 s, +9 %); the SAME tree
        # with the gate off runs 35.2 s, so the added code costs nothing —
        # the cost is BEHAVIOURAL.  Withdrawing an anchor loosens the
        # one-shot reach envelope, so fewer nodes are clamped by the warm
        # start and the POCS sweeps do more work.  HECA is unaffected
        # (348-352 s across every arm).  Under budget (60 s) but over the
        # 1 % review trigger — reported, not approved.
        # Gate off ⇒ ``None`` ⇒ the single unrestricted envelope pass ⇒
        # byte-identical (proven: HECA patch body identical to the
        # pre-clause tree, 2026-07-30).
        _gs_witness = None
        from auto_patch.config import SERVICE_ROAD_MAX_GRADE
        from .anchors import apply_groundside_reach, gs_witness_horizon
        _nrl, _gs_hard = apply_groundside_reach(
            layout, bucket_to_idx, elev, SERVICE_ROAD_MAX_GRADE)
        # STANDING LAW (owner 2026-07-30, memory ``airside-is-king`` /
        # ``groundside-terrace-law``; UNGATED in the build-complete-then-
        # debug round).  "Groundside has ZERO effect or pull on airside" —
        # so a groundside pin witnesses the airside envelope only inside the
        # Part-C mouth allowance, and nothing beyond it.  This is the SOLVE
        # half; the final-projection half is the same law one node space
        # later, and both are now on: shipping one half was the compromise
        # the gates encoded, and a half-applied owner law is not a state
        # this architecture has.
        #
        # Measured cost of the solve half, RECORDED (not a reason to gate):
        # CYXY solve +3.4 s (35.2 → 38.6 s, 3 runs/arm same tree), HECA
        # within-shape 460 → 482 against break pairs −631.
        if _gs_hard:
            _gs_witness = (frozenset(_gs_hard),
                           gs_witness_horizon(SERVICE_ROAD_MAX_GRADE))
        if _gs_hard:
            # The truck route (apron arm + connector + groundside mouth) now
            # carries its re-levelled value as a SEED; re-project so the apron
            # BODY grades into the arm and nothing else exceeds its cap.
            #
            # THE PINS ARE NOT HARD HERE (cycle-5 spec fix 3).  ``_gs_hard``
            # used to join this projection's immovable set, which made the
            # groundside weld value an ANCHOR.  On a constant-DEM world that
            # value IS the raw DEM (the reach law re-levels a piece to its
            # closest-to-DEM reachable level), so the anchor was DEM acting as
            # a constraint — forbidden outright by RULINGS 2026-08-05 ("DEM is
            # a SEED, never a constraint, never an authority") — and it was
            # groundside pulling airside, forbidden by "airside is king".
            #
            # Measured at HECA plateau: all 70 out-of-band hard nodes were
            # ``gs_pin``; 25 sat exactly on the constant DEM; 21 of those were
            # below their own band floor, worst deficit 89.369 m.  The single
            # worst over-cap row in the whole solve (93.125 m) was one of them
            # dragging an in-band building seat.
            #
            # What still holds the weld together: every mouth-weld LAW EDGE is
            # in the joint and enforced by the sweeps, and the pin's own law
            # ceiling bounds it from above (below).  Losing the anchor loses
            # no law — it loses an assertion.
            _ghard = hard | {i for i in runway_nodes if i < n}
            feasibility_project_partitioned(
                                elev, shape_constraints, _ghard,
                                receiver_nodes=_solve_receivers, n_nodes=n,
                                interval_yield_from=_iyf,
                                witness_limited=_gs_witness,
                                witness_excluded=_route_excluded,
                                env_band=_env_band)
            feasibility_project_partitioned(
                                elev,
                                _unified_entries(u_edges, _u_pair_stage,
                                                 "solve/groundside"), _ghard,
                                receiver_nodes=_solve_receivers, n_nodes=n,
                                witness_limited=_gs_witness,
                                witness_excluded=_route_excluded,
                                env_band=_env_band)
        # Service roads FOLLOW DEM at <=cap (a ground road climbs toward terrain,
        # anchored only at its airside/groundside welds) — SVC4 was held flat in
        # the bowl ~6-11 m below DEM.
        from .anchors import apply_service_road_dem_follow
        _svc_moved = apply_service_road_dem_follow(
            layout, bucket_to_idx, elev, dem_elev, SERVICE_ROAD_MAX_GRADE,
            anchor_extra=_gs_hard)
        if (_nrl or _svc_moved) and _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"  [groundside-reach] {icao}: re-levelled {_nrl} "
                  f"groundside piece(s); pinned {len(_gs_hard)} route node(s); "
                  f"DEM-followed {len(_svc_moved)} service node(s).")
        # ── DETACHED PADS SEAT BY LAW (item 3(b)) ────────────────────────
        # HERE, not earlier: a detached pad is a groundside object, its datum
        # is a SOLVED groundside variable, and groundside conforms to airside
        # — so the pad is the last thing seated.  The seat is FLAT inside the
        # host-datum box (``anchors.detached_pad_law_box``), at the point of
        # that box nearest the pad's seed; the box is registered in the
        # ``seat_boxes`` store so fp#8 and the final projection bound the pad
        # through the ratified channel.  Merging the seats into
        # ``building_seats`` is what makes each pad an ORDINARY movable FLAT
        # group downstream (flatness is the building law; the deleted DEM
        # pin's exclusion from those groups existed only to protect a value
        # the law did not choose).  ``building_seats`` is read for the spine
        # yield membership ~280 lines ABOVE this point, so this merge cannot
        # retro-preserve anything — keep the call below that read.
        if _detached_pads:
            from auto_patch.config import GROUNDSIDE_MAX_GRADE
            # ── CYCLE-7 FIX 2 (owner ruling 2026-08-06) ───────────────────
            # A FRONTAGE-COUPLED pad is seated from the route-graph band
            # through its frontage chord; the groundside contact datum is not
            # its law and may not bound it.  ``detached_pad_law_box``'s
            # contact march stops at 2.5 m while the LAW GRAPH has no
            # horizon: HECA's building172 sits 6.46 m from an apron node with
            # an ordinary 1 %-cap chord to it, so the march saw only
            # groundside pieces at d = 0 and minted a ZERO-WIDTH box at the
            # groundside/DEM datum — which then held that airside apron edge
            # in a permanent clamp/sweep 2-cycle worth 60.772738 m, the worst
            # residual in the whole solve.  Only a pad with NO frontage
            # coupling keeps the contact-box path.
            _dp_seats, _dp_stats = seat_detached_pads_by_law(
                layout, bucket_to_idx, elev, _detached_pads,
                GROUNDSIDE_MAX_GRADE,
                frontage_coupled=_pad_frontage, node_band=node_band)
            building_seats.update(_dp_seats)
            if any(_dp_stats):
                import O4_UI_Utils as _UI_dl
                _UI_dl.vprint(1,
                    f"  [detached-pad] {_dp_stats[0]} pad(s) seated on a "
                    f"solved groundside datum, {_dp_stats[1]} with NO "
                    f"resolvable host (left unbounded on their seed — a "
                    f"missing datum is never a DEM bound), "
                    f"{_dp_stats[2]} DECLARED CONTACT CONFLICT(S) (an empty "
                    f"box is the split-level-seat law's trigger, RULINGS "
                    f"2026-08-04).")
                _UI_dl.vprint(1,
                    f"  [detached-pad] frontage-band seating (owner "
                    f"2026-08-06): {_dp_stats[3]} pad(s) seated FROM THE "
                    f"ROUTE-GRAPH BAND through their frontage chord (no "
                    f"DEM-datum bound), {_dp_stats[4]} frontage-coupled with "
                    f"NO DERIVABLE BAND (left unbounded on their seed and "
                    f"reported — never a fallback to the datum pin), "
                    f"{_dp_stats[5]} SPLIT-LEVEL CANDIDATE(S) whose frontage "
                    f"couplings no single flat level meets (RULINGS "
                    f"2026-08-04 — reported, never silently resolved).")
        _psub(0.88, "Solving elevations — feasibility projection")
        # ── S1b: THE POST-PHASE-A OVERWRITE IS RETIRED ────────────────
        # It applied the chord values here, AFTER phase A returned, which
        # meant the harmonic computed corridor interiors this hook then
        # discarded (the acknowledged single-pass violation "α").  Under
        # S1b the chord values enter phase A ONCE, as Dirichlet pins on
        # the spine solve above, so the harmonic keeps its interiors and
        # demotes to a residual gap-filler WITH string boundaries — which
        # is what gives it the altitude preference it measurably lacks
        # (it owns 67.1 % of the corridor's departure from DEM and has no
        # height preference of its own).  Nothing overwrites after phase
        # A; the rod below is still minted FROM the strung spine, because
        # the strung spine now carries the chord values by construction.
        # ── STRING-AS-LAW INTERVAL ROD registration (spec §10, owner
        # ruling 2026-07-28 late session — supersedes the §7 holds) ────
        # The corridor string becomes ORDINARY LAW: one signed interval
        # edge ``z_i − z_j ∈ [Δstring − ε, Δstring + ε]`` per
        # consecutive strung spine pair, registered in
        # ``shape_constraints`` like the adjacent-ground envelope edges.
        # Every subsequent projection that reads ``shape_constraints`` /
        # ``joint`` maintains the string's SHAPE automatically: the
        # corridor is a quasi-rigid ROD that translates vertically to
        # meet seats, seams, runways and the body web — the yields keep
        # their feasibility freedom but cannot manufacture dips, and
        # bodies follow through their body↔spine law edges to wherever
        # the rod SETTLED (no value-holds, so nothing is minted where
        # the law graph lacks a body↔spine pair).
        # Δ IS SNAPSHOT HERE — at yield entry — not at phase-A end:
        # every projection between the phase-A freeze and this point
        # holds the spine HARD, so a taxi corridor's Δ here IS the
        # faired phase-A string (spec §10.1) byte-for-byte, while a
        # SERVICE corridor's Δ includes the authoritative
        # ``apply_service_road_dem_follow`` re-shape above (a rod
        # snapshot at phase-A end froze the pre-follow shape and minted
        # 8.95 % service pairs at CYXY).
        # ``envelope_skip``: rod slabs carry signed (often negative)
        # directed weights that the reach-envelope Dijkstra must not
        # see (the retired EAT interval edges' blowup class); the
        # sweeps enforce them fully.  The canonical-key export lets
        # ``final_grade_projection`` carry the SAME edges into its
        # rebuilt node space.  Gate off ⇒ no strung pieces ⇒ no entry,
        # no export — byte-identical.
        # Kept in THIS index space for the projections and the forensic
        # dump; empty ⇒ no strung pieces.
        _rod_edges: list = []
        # The solve-index → canonical-key reverse map, bound unconditionally
        # so the conflict ledger below can carry canonical keys without
        # building a THIRD reverse map (spec §1 identity clause).  Filled by
        # the rod export below when there are strung pieces.
        _rod_key_of: dict = {}
        if _rod_pieces:
            from auto_patch.config import SPINE_ROD_EPSILON_M as _ROD_EPS
            # SLAB PRICING AGAINST THE LAW — the FLOOR (RULINGS 2026-08-06
            # "Slab budgets floor at the law") and the §10.1 CLAMP
            # (2026-07-29, CYXY service spine 6.2 %) are BOTH applied by
            # ``one_solve.price_slab_against_law``, which is the one site
            # that prices a rod slab; read its header for the two rulings
            # and why the composition lands the slab AT the law.  Here we
            # only supply the per-pair law budget it floors and clamps to.
            # Budgets are looked up rod-pairs-first (the rod pair set is
            # tiny) so the one pass over ``shape_constraints`` pays a
            # set-membership test per edge, not a dict insert.
            _rod_pair_keys = {
                (min(_ra, _rb), max(_ra, _rb))
                for _rp in _rod_pieces for _ra, _rb in zip(_rp, _rp[1:])}
            _rod_pair_budget: dict = {}
            for _sc_ent in shape_constraints:
                for _e in _sc_ent.get("edges", ()):
                    if len(_e) >= 4:
                        continue
                    _pk = (_e[0], _e[1]) if _e[0] <= _e[1] \
                        else (_e[1], _e[0])
                    if _pk not in _rod_pair_keys:
                        continue
                    _pb = float(_e[2])
                    _cur = _rod_pair_budget.get(_pk)
                    if _cur is None or _pb < _cur:
                        _rod_pair_budget[_pk] = _pb
            _rod_clamped = 0
            _rod_floored = 0
            _rod_lawless = 0
            # Half-open [start, stop) spans of ``_rod_edges`` per STRUNG
            # PIECE — the chain structure the composition export below
            # needs (consecutive entries within one span share a node, so
            # a run of removed vertices is a contiguous sub-span).
            _rod_piece_spans: list = []
            # ROD STAGE, INHERITED FROM THE OWNING CHAIN (staged-solve S1b,
            # Fable ruling 2026-08-13b).  The rod interval is the live
            # successor of the retired §7 memory and it reaches the final
            # projection as ``family="rod_interval"`` with NO role key — so
            # ``_withhold_road_pair_law`` is structurally blind to it and a
            # SERVICE corridor's rod bound ``z_a - z_b`` against an airside
            # endpoint in the airside pass (coupling 4, and coupling 5 for
            # the ``apply_service_road_dem_follow`` re-shape the snapshot
            # deliberately includes).  A chain is groundside when ANY of its
            # nodes is a stage-B node: a rod is a QUASI-RIGID object, so a
            # chain running through groundside is a groundside corridor and
            # binding it in stage A imports exactly the variable staging
            # removes.  Mouth vertices are stage A (airside is king), so a
            # taxi corridor stays airside.
            _rod_edge_stage: list = []
            for _rp in _rod_pieces:
                _p0 = len(_rod_edges)
                _piece_stage = (_STAGE_B if any(v in _solve_receivers for v in _rp)
                                else _STAGE_A)
                for _ra, _rb in zip(_rp, _rp[1:]):
                    _rd = elev[_ra] - elev[_rb]
                    _pb = _rod_pair_budget.get(
                        (min(_ra, _rb), max(_ra, _rb)))
                    _rlo, _rhi, _rfl, _rcl = price_slab_against_law(
                        _rd, _ROD_EPS, _pb)
                    if _pb is None:
                        _rod_lawless += 1
                    if _rfl:
                        _rod_floored += 1
                    if _rcl:
                        _rod_clamped += 1
                    _rod_edges.append((_ra, _rb, _rlo, _rhi))
                    _rod_edge_stage.append(_piece_stage)
                if len(_rod_edges) > _p0:
                    _rod_piece_spans.append((_p0, len(_rod_edges)))
            if _rod_edges:
                # ONE ENTRY PER STAGE.  ``_taut_rod_key_edges`` below still
                # exports the WHOLE rod (both stages) in canonical-key space
                # — the final projection re-derives each interval's stage in
                # its own node space, so the export stays stage-free.
                _rod_a = [e for e, st in zip(_rod_edges, _rod_edge_stage)
                          if st == _STAGE_A]
                _rod_b = [e for e, st in zip(_rod_edges, _rod_edge_stage)
                          if st == _STAGE_B]
                _n_rod_gs = len(_rod_b)
                for _re_, _rs_ in ((_rod_a, _STAGE_A), (_rod_b, _STAGE_B)):
                    if _re_:
                        shape_constraints.append({"edges": _re_,
                                                  "envelope_skip": True,
                                                  "family": "rod_interval",
                                                  _STAGE_KEY: _rs_})
                if _n_rod_gs:
                    import O4_UI_Utils as _UI_rod_st
                    _UI_rod_st.vprint(
                        1, f"  [stage] rod intervals: {_n_rod_gs} of "
                           f"{len(_rod_edges)} interval(s) belong to a "
                           f"GROUNDSIDE chain and are enforced in stage B "
                           f"(airside is king)")
                # Canonical-key export of the rod's own stage, so the final
                # projection inherits the SAME chain verdict instead of
                # re-deriving it from a node space the solve does not share.
                layout._taut_rod_edge_stage = list(_rod_edge_stage)
                _rod_key_of = {i: k for k, i in bucket_to_idx.items()}
                layout._taut_rod_key_edges = [
                    (_rod_key_of[a], _rod_key_of[b], lo, hi)
                    for (a, b, lo, hi) in _rod_edges
                    if a in _rod_key_of and b in _rod_key_of]
                # STAGE RIDES WITH THE EXPORT (S1b).  The final projection
                # rebuilds the node space, so it cannot re-derive the chain
                # verdict; the solve is the rod store's only writer and the
                # stage is part of the store.
                layout._taut_rod_key_edge_stage = [
                    st for (a, b, lo, hi), st in zip(_rod_edges, _rod_edge_stage)
                    if a in _rod_key_of and b in _rod_key_of]
                # ROD COMPOSITION EXPORT (owner-approved design 2026-07-29,
                # docs/specs/rod-compose-and-band-single-source-spec.md §A).
                # AUDITED FACT: 100 % of the rod's carry loss into
                # ``final_grade_projection`` is ``emit_decimate.
                # decimate_emit_nodes`` DELETING strung 3D-collinear ring
                # vertices between the solve and the projection's node
                # rebuild (HECA 13,680 vertices → 4,068 of 7,034 links
                # dropped).  Those links are not lost information: the
                # decimator's own kept-pair grade is the length-weighted
                # mean of the removed sub-segments, so the removed chain's
                # INTERVAL SUM is the exact rod constraint between the two
                # SURVIVORS.  Export the chain STRUCTURE (not just the flat
                # pair list) so the carry site can replace a removed run
                # S1..S2 by ONE composed link with ``[ΣΔ − Σε, ΣΔ + Σε]``.
                # Single-pass principle: nothing is re-derived, re-strung or
                # transported — the solve stays the rod store's only writer
                # and the carry is a pure consumer.  Chains break wherever a
                # solve node has no canonical key (nothing to compose
                # through); the union of chains is exactly
                # ``_taut_rod_key_edges``.
                _rod_chains: list = []
                _rod_chain_stage: list = []
                for (_p0, _p1) in _rod_piece_spans:
                    _span_stage = (_rod_edge_stage[_p0]
                                   if _p0 < len(_rod_edge_stage) else _STAGE_A)
                    _cur: list = []
                    for (_a, _b, _lo, _hi) in _rod_edges[_p0:_p1]:
                        _ka = _rod_key_of.get(_a)
                        _kb = _rod_key_of.get(_b)
                        if _ka is None or _kb is None:
                            if _cur:
                                _rod_chains.append(_cur)
                                _rod_chain_stage.append(_span_stage)
                                _cur = []
                            continue
                        if _cur and _cur[-1][1] != _ka:
                            _rod_chains.append(_cur)
                            _rod_chain_stage.append(_span_stage)
                            _cur = []
                        _cur.append((_ka, _kb, _lo, _hi))
                    if _cur:
                        _rod_chains.append(_cur)
                        _rod_chain_stage.append(_span_stage)
                layout._taut_rod_key_chains = _rod_chains
                layout._taut_rod_key_chain_stage = _rod_chain_stage
                if _os.environ.get("O4_STEP_DEBUG") == "1":
                    print(f"    [taut-string] rod edges="
                          f"{len(_rod_edges)} ({_rod_floored} law-FLOORED "
                          f"— RULINGS 2026-08-06, a slab may not price "
                          f"tighter than its pair's law; {_rod_clamped} "
                          f"law-clamped §10.1; {_rod_lawless} on pairs "
                          f"with no symmetric law edge, priced raw at "
                          f"±ε; snapshot at yield entry)")
                # ROD CARRY AUDIT (phase-1 probe, gate O4_ROD_CARRY_AUDIT=1
                # — docs/specs/single-space-string-audit-spec.md §2).  Off
                # ⇒ not even imported ⇒ byte-identical.
                if _os.environ.get("O4_ROD_CARRY_AUDIT") == "1":
                    from auto_patch import rod_carry_audit as _rca
                    _rca.record_mint(layout, _rod_edges, nodes,
                                     _rod_key_of, graph=G,
                                     pieces=_rod_pieces, icao=icao)
        # SPINE-YIELD projection (global-slice spine adaptation, 2026-07-02).
        # Under the global slice most graph nodes ARE spine (every face is
        # born from a centerline cut), so "both ends frozen = genuine step"
        # no longer holds: two route chains solved independently in PHASE A
        # can freeze 2.6 m apart one ring-edge from each other (SPJC measured
        # 1622→3034 frozen-spine/spine residual edges).  Re-project with only
        # the TRUTH anchors hard — runway/CIFP, tile-seam DEM pins, building
        # seats, groundside truck-route pins — so the frozen profiles yield
        # minimally where they disagree.  Runs LAST (after the groundside
        # reach block, whose own re-projections hold the full frozen spine
        # and would otherwise re-wall what an earlier yield fixed), right
        # before writeback.  The phase-A profile is the seed, so smooth
        # spines stay smooth wherever they were already feasible.
        # (2026-07-29) the legacy rect-model gate was retired — the
        # global slice is the only path, so this always runs.
        # THE KEPT-HARD SOURCES, each with its law (cycle-5 fix 3 enumerated
        # them and demoted exactly one):
        #   truth_hard      — ``seed_rwy_seam`` (CIFP runway profile values,
        #                     absolute for v1 per RULINGS 2026-08-05, and the
        #                     TILE-SEAM DEM pins, which are cross-tile
        #                     continuity law), ``rwy_join`` / ``rwy_flexed``
        #                     (runway anchors), ``seat_on_spine`` (building
        #                     seat law), ``seam_spine_anchor``;
        #   runway_nodes    — the runway ring/vertex set (CIFP truth);
        #   building_seats  — every seated pad / no-building-apron level
        #                     (the building law: flat seats).
        # DEMOTED: ``_gs_hard`` (``gs_pin``).  A groundside weld is not truth
        # — it is a value groundside ASSERTS onto the route, at raw DEM on a
        # constant-DEM world.  It is now a SEED bounded by its own law
        # ceiling; see the groundside-reach block above and the box below.
        yield_hard = (truth_hard
                      | {i for i in runway_nodes if i < n}
                      | {i for i in building_seats if i < n}
                      # …and the corridor FREE-END DEM ties (corridor-joins
                      # ruling 3): a road's walk to ground is law, and the
                      # measured failure of the soft spelling was this very
                      # pass writing 6.31 m back over the seed.  Stated again
                      # after the pad relaxations below ("never leave the
                      # hard set"), which is where a set subtraction could
                      # otherwise drop it.
                      | {i for i in
                         (getattr(layout, "_svc_free_end_idx", None) or ())
                         if i < n}
                      # …and the corridor MOUTH seats (owner law
                      # 2026-08-15): a road meeting aircraft pavement
                      # ARRIVES at that pavement's value, and the soft
                      # spelling measured the same loss the free-end tie
                      # did — 96 of 141 HECA seats written over, worst
                      # 9.069 m.  Same channel, same reason, stated at
                      # the same two points.
                      | {i for i in
                         (getattr(layout, "_svc_mouth_prox_idx", None) or ())
                         if i < n})
        # ── RULING 54: THE KEPT PIN SET JOINS ``yield_hard`` ───────
        # ★ A BLEND IS NOT GRADE LAW.  Under the owner's invariant a
        # string may be overruled only by LAW; the measured 4.87 m at
        # chord 1's dip was the surface sitting BELOW ITS OWN CEILING
        # with no law author at all — no cap contact, no clamp, no
        # runway, no clip.  The quarantine blend's retained purpose is
        # GENUINE BAND INVERSIONS, which does not cover a station with
        # 4.87 m of admitted headroom, so the blend was overwriting a
        # lawful strung value and §7 then froze the result.
        # ★ WHY THE KEPT PIN SET AND NOT THE FREEZE.  Inheriting the
        # whole ~3.7 k-node phase-A spine freeze is REJECTED: it would
        # over-freeze exactly the unstrung residual domain that has no
        # string authority and MUST yield — the smoother's ground,
        # junctions, sub-min runs.  The kept pins are the vertices S1b
        # holds to a lawful chord value, already Ruling-52 law-filtered
        # so none of them forces an over-cap pair.  Excluding pins from
        # the blend alone is UNDER-SCOPED (1892/1988 consume
        # ``yield_hard`` too), and hard membership is the existing
        # protection idiom — no new mechanism.
        # ★ PRECEDENCE (Ruling 52, carried): law is never released.  A
        # genuine law demand reaching a pin at yield time is a DECLARED
        # CONFLICT for attribution, never a silent un-pin — a pinned
        # node behaves here exactly as a truth anchor already does.
        # ``_string_pins`` is None with the gate off ⇒ byte-identical.
        _pins_in_yield = ({i for i in _string_pins if i < n}
                          if _string_pins else set())
        yield_hard = yield_hard | _pins_in_yield
        # ── PROBE A: OPEN THE MOVER LEDGER (spec §1) ───────────────
        # WATCH SET = the conflict-eligible population: every kept pin
        # ∪ its ``u_spine_adj`` neighbours (~10 k at HECA).  Built
        # ONCE, here, because this is where the pin set is known and
        # nothing has yet re-projected the spine.  Stages B-F cannot
        # move a spine node (the spine is ``base_hard`` from the phase-A
        # freeze), so the only earlier boundary that matters is stage G
        # — and it hands back its own moved set, no diff needed.
        # BASELINE = ``elev`` at this statement.  Nothing between here
        # and the first spine-yield projection below writes ``elev``
        # (the only intervening statement is the ``_elev_entry_A``
        # COPY), so this is exactly the spec's pre-projection baseline.
        # Gate off ⇒ ``None`` ⇒ a handful of ``is None`` checks.
        _mover = None
        if (_pins_in_yield and _os.environ.get(
                "O4_STRING_MOVER_LEDGER", "0") == "1"):
            _ml_watch = set(_pins_in_yield)
            for _wi in _pins_in_yield:
                for _we in (u_spine_adj.get(_wi) or ()):
                    _wj = _we[0] if isinstance(_we, (tuple, list)) else _we
                    if _wj < n:
                        _ml_watch.add(_wj)
            _mover = _mover_ledger_new(_ml_watch, elev,
                                       svc_moved=_svc_moved)
            # CANONICAL KEYS for the final-projection tail (spec
            # amendment): those passes REBUILD the node list, so the
            # watch set must cross by key.  Read off the rod export's
            # reverse map — the same complete ``{i: key}`` inversion
            # of ``bucket_to_idx`` the rod carry already built; never
            # a third map.  Empty (no strung pieces ⇒ no rod export)
            # is reported, never silent: ``n_mover_keyed`` below.
            _mover["key_of"] = {_wi: _rod_key_of[_wi]
                                for _wi in _ml_watch
                                if _wi in _rod_key_of}
        # ── FIX ARM §3: THE KEPT PIN SET CROSSES BY CANONICAL KEY ──
        # (gate ``O4_STRING_PINS_FINAL_HOLD``, default "0"; only ever
        # non-empty when strings are on.)  The mover ledger attributed
        # 85.8 % of the G2 pin drag to ``final_proj_2``: pins are
        # Dirichlet ONLY in phase A and nothing downstream holds them.
        # The two ``final_grade_projection`` passes REBUILD the node
        # list, so the set crosses the way the probe's watch set
        # already does — by canonical key, never by index carry —
        # through the SAME reverse map (``_rod_key_of``; built here
        # only if the rod export did not already build it, so there is
        # still no third map).  The value rides along for the ledger;
        # the HOLD itself is set membership, exactly as Ruling 54
        # joined the pins to the solve's ``yield_hard``.
        # PARKED FEATURE — NOT A LAW GATE (integration sweep 2026-08-05).
        # The taut-string machinery is the owner's PAUSED feature: the strings
        # verdict is pending (memory ``string-purpose-statement``: strings are a
        # smoothing refinement for otherwise-correctly-graded taxiways, NOT a
        # surface authority), so this switch is deliberately NOT deleted with
        # the law gates.  It selects whether a PARKED feature runs at all, not
        # which law the build obeys.  Retire or adopt it when the owner rules.
        if (_string_pins and _os.environ.get(
                "O4_STRING_PINS_FINAL_HOLD", "0") == "1"):
            if not _rod_key_of:
                _rod_key_of = {i: k for k, i in bucket_to_idx.items()}
            layout._string_pin_keys = {
                _rod_key_of[_pi]: float(_pz)
                for _pi, _pz in _string_pins.items()
                if _pi in _rod_key_of}
            if _os.environ.get("O4_STEP_DEBUG") == "1":
                print(f"    [S1b final-hold] exported "
                      f"{len(layout._string_pin_keys)} of "
                      f"{len(_string_pins)} kept pin(s) by canonical "
                      f"key for the final projections")
        # Fast Jacobi first (bulk of the correction), then the FINAL pass
        # as scalar Gauss-Seidel POCS on the joint edge set — Jacobi has no
        # convergence guarantee and stalls with ~2.5k edges marginally over
        # cap (the audit's POCS on the same polytope reaches ~0 in <100
        # sweeps).  Joint set: projecting the two graphs alternately
        # un-does one with the other.
        # REFERENCE HONESTY (spec docs/specs/reference-honesty-and-
        # terracing-spec.md Track 1): these two projections run the
        # quarantine blend, so every reference built AFTER them is
        # sampling a field the law refused to admit.  Capture WHICH
        # nodes were quarantined so the reference builders below can
        # tell a law-true value from a blended one.  ``broken_out`` is
        # write-only inside ``feasibility_project`` (it never reads the
        # set back), so collecting it cannot change the solve —
        # gate-off identity is unaffected either way; it is gated only
        # so the OFF arm allocates nothing.
        # ── FIELD MOMENT "A" (R1/P2-CP1; rides ``O4_DUMP_SOLVE_STATE``) ─
        # Spec §4.1 layer 6's source state: the PRE-PROJECTION phase-A/B
        # value, captured BEFORE the two projections below apply the
        # quarantine blend.  No artifact carried this until P2 added it
        # (the ``/tmp/bandq`` "fp#8" dump is written INSIDE the third
        # projection, after its clamp+blend).  Candidate "B" — the
        # post-projection state today's snapshot reads — needs no field
        # of its own: it is the payload's existing ``elev`` key, since
        # ``elev`` is not written again before the dump below.
        # Read-only: gate unset ⇒ one env read, nothing allocated.
        _elev_entry_A = (
            list(elev) if _os.environ.get("O4_DUMP_SOLVE_STATE")
            else None)
        # (``O4_CORRIDOR_REF_STRING`` — the back door that promoted
        # rod-held string values into ``z_ref`` — was DELETED with the
        # refs channel and the proximal pull, per docs/RULINGS.md
        # "No degradation-shield interims; retire the string back
        # door".)  The quarantine set the two projections declare is
        # still collected: it is the ``O4_DUMP_SOLVE_STATE`` forensic
        # payload and the band-carry input below.
        _yield_broken: set = set()
        _bo = _yield_broken
        # ── FIX ARM §2: THE DECLARED-CONFLICT CHANNEL ─────────────
        # Write-only, allocated only under the gate, one list per
        # call so each row can name the projection that declared it.
        # PARKED FEATURE — NOT A LAW GATE (integration sweep 2026-08-05).
        # The taut-string machinery is the owner's PAUSED feature: the strings
        # verdict is pending (memory ``string-purpose-statement``: strings are a
        # smoothing refinement for otherwise-correctly-graded taxiways, NOT a
        # surface authority), so this switch is deliberately NOT deleted with
        # the law gates.  It selects whether a PARKED feature runs at all, not
        # which law the build obeys.  Retire or adopt it when the owner rules.
        _hnb_on = _os.environ.get("O4_HARD_NEIGHBOUR_BOUND",
                                  "0") == "1"
        _hnb_decl: list = []

        def _hnb_take(rows, call):
            for _r in rows:
                _r["call"] = call
            _hnb_decl.extend(rows)

        _hnb_a: list = [] if _hnb_on else None
        _hnb_b: list = [] if _hnb_on else None
        # SPINE-FREEZE ROUND: the spine is already OUT of ``yield_hard``
        # here (``truth_hard`` was snapshotted before the freeze), but
        # it entered these two passes with NO reference at all — free to
        # settle anywhere feasible.  Under the gate it carries the same
        # phase-A rod as every projection above, so its status is ONE
        # thing from the freeze to writeback: yield-hard.  ``None`` off
        # the gate ⇒ byte-identical.
        rem, bh = feasibility_project_partitioned(
                                      elev, shape_constraints, yield_hard,
                                      receiver_nodes=_solve_receivers, n_nodes=n,
                                      interval_yield_from=_iyf,
                                      witness_limited=_gs_witness,
                                      witness_excluded=_route_excluded,
                                      broken_out=_bo,
                                      env_band=_env_band,
                                      probe_out=_mover,
                                      declared_out=_hnb_a)
        # PROBE A boundaries 1-2: the blend copy the callee left in the
        # ledger, then the post-return state (the sweeps).
        _mover_stamp_probe(_mover, "proj_shape.blend")
        if _mover is not None:
            _mover_stamp(_mover, _mover_snapshot(_mover, elev),
                         "proj_shape.sweep")
        if _hnb_on:
            _hnb_take(_hnb_a, "proj_shape")
        rem, bh = feasibility_project_partitioned(
                                      elev,
                                      _unified_entries(u_edges, _u_pair_stage,
                                                       "solve/yield"),
                                      yield_hard, broken_out=_bo,
                                      receiver_nodes=_solve_receivers, n_nodes=n,
                                      witness_limited=_gs_witness,
                                      witness_excluded=_route_excluded,
                                      env_band=_env_band,
                                      probe_out=_mover,
                                      declared_out=_hnb_b)
        if _hnb_on:
            _hnb_take(_hnb_b, "proj_u")
        # PROBE A boundaries 3-4.
        _mover_stamp_probe(_mover, "proj_u.blend")
        if _mover is not None:
            _mover_stamp(_mover, _mover_snapshot(_mover, elev),
                         "proj_u.sweep")
        # ── RULING 54 INSTRUMENTATION ─────────────────────────────
        # The ruling expects pin-vs-neighbour declarations to be small
        # and AUTHOR-CARRYING; "small and author-carrying" is only
        # checkable if they are emitted.  Read straight off the graph
        # after the yield, so it depends on no projection internal.
        if _pins_in_yield:
            _pin_decl = []
            for _pi, _plst in u_spine_adj.items():
                if _pi not in _pins_in_yield:
                    continue
                for (_pj, _pbudget) in _plst:
                    if _pj >= n or (_pj in _pins_in_yield and _pi > _pj):
                        continue
                    _pdz = abs(elev[_pi] - elev[_pj])
                    if _pdz <= float(_pbudget) + 1e-9:
                        continue
                    _row = {
                        "pin": _pi, "neighbour": _pj,
                        "pin_z": elev[_pi], "neighbour_z": elev[_pj],
                        "budget_m": float(_pbudget),
                        "excess_m": _pdz - float(_pbudget),
                        "neighbour_class": (
                            "law_anchor" if _pj in truth_hard else
                            "pin" if _pj in _pins_in_yield else
                            "free")}
                    # ── PROBE A DELIVERY (spec §1) ────────────────
                    # Identity: ``pin`` / ``neighbour`` / ``elev``
                    # indices are ONE space (raw solver node indices),
                    # so no join is needed — but the CANONICAL key
                    # rides along for offline geometry, read off the
                    # rod export's reverse map (never a third map).
                    if _mover is not None:
                        _row["pin_last_writer"] = \
                            _mover["label"].get(_pi)
                        _row["neighbour_last_writer"] = \
                            _mover["label"].get(_pj)
                        _row["pin_key"] = _rod_key_of.get(_pi)
                        _row["neighbour_key"] = _rod_key_of.get(_pj)
                    _pin_decl.append(_row)
            _summary["n_pins_in_yield_hard"] = len(_pins_in_yield)
            _summary["pins_in_yield_hard"] = sorted(_pins_in_yield)
            _summary["n_pin_yield_conflicts"] = len(_pin_decl)
            _summary["pin_yield_conflicts"] = _pin_decl
            if _hnb_on:
                # FIX ARM §2: the declared population, whole (a LARGE
                # one is a finding, never something to suppress).
                _summary["n_declared_hard_conflict"] = len(_hnb_decl)
                _summary["declared_hard_conflict"] = _hnb_decl
            if _mover is not None:
                # The label histogram over the FREE member — the
                # spec's question is which stage last moved it.  Per-
                # row labels (both sides) carry every finer cut the
                # readings need, offline.
                _mlc: dict = {}
                for _row in _pin_decl:
                    _lbl = _row.get("neighbour_last_writer")
                    _mlc[_lbl] = _mlc.get(_lbl, 0) + 1
                _summary["mover_ledger_counts"] = _mlc
                _summary["n_mover_watch"] = len(_mover["watch"])
                _summary["n_mover_keyed"] = len(_mover["key_of"])
            from .taut_string import write_string_sidecar as _ws
            _ws(layout)                      # last call wins
            if _os.environ.get("O4_STEP_DEBUG") == "1":
                print(f"    [S1b yield] {len(_pins_in_yield)} pin(s) held "
                      f"through the yield; {len(_pin_decl)} declared "
                      f"neighbour conflict(s)")
        # MOVABLE FLAT PADS (user 2026-07-03): building pads leave the
        # hard set and become rigid flat GROUPS the projection may move —
        # the audit proves the polytope is feasible ONLY when buildings
        # can move (holding every pre-picked seat hard is infeasible
        # through chained paths: pad↔spine↔pad, even with 0 both-hard
        # edges).  Each pad stays FLAT (the invariant) at a level the
        # projection chooses jointly with the field.
        from auto_patch.layout import ROLE_BUILDING as _RB
        pad_groups = []
        _cps = layout.canonical_points
        for _s in layout.shapes:
            if (_s.role != _RB or _s.polygon is None
                    or _s.polygon.is_empty):
                continue
            _ring = list(_s.polygon.exterior.coords)
            _g = {bucket_to_idx.get(_cps.get_or_add(float(x), float(y)))
                  for (x, y) in _ring}
            # Seam pins never join a movable group (they are
            # immovable terrain anchors — see yield_hard below).
            _g = {i for i in _g
                  if i is not None and i < n and i in building_seats
                  and i not in _seam_pin_idx}
            if len(_g) >= 2:
                pad_groups.append(_g)
        if pad_groups:
            _pad_nodes = set().union(*pad_groups)
            yield_hard = yield_hard - _pad_nodes
        # NON-PAD SEAT ANCHORS (nobuild-apron tilt seats + contact seats,
        # and seat nodes not on any pad ring) also leave the hard set for
        # the FINAL pass: held hard they oscillate against the runway
        # profile exactly like pads did (measured: worst residual 1.0 m →
        # 0.02, SPJC law-true 406 → ~180).  They still anchored phases
        # A/B, so the surface is already shaped by them; the final GS
        # only relaxes the last-mile conflicts.
        if pad_groups:
            yield_hard = yield_hard - (
                {i for i in building_seats if i < n} - _pad_nodes)
        # SEAM PINS NEVER LEAVE THE HARD SET (user 2026-07-04): the
        # movable-pads / free-apron-seats relaxations above may have
        # freed a node that is ALSO a tile-seam terrain pin — but the
        # seam is a graded-TO anchor exactly like a runway edge; a
        # freed pin lets the final GS park the boundary off the
        # terrain it must meet (SPLP: 0.7 m float at the band edge).
        yield_hard |= {i for i in _seam_pin_idx if i < n}
        # ── FREE-END DEM TIES NEVER LEAVE THE HARD SET EITHER ─────
        # (corridor-joins round, ruling 3, gate
        # ``SERVICE_CORRIDOR_FREE_END_ANCHOR``.)  A corridor terminus over
        # open terrain is a LAW TARGET — the road grades to ambient DEM
        # under its own cap (RULINGS 2026-08-12b) — and the measured
        # failure of the SOFT spelling is exactly this pass: the seed
        # wrote DEM at the KCLT free end and the projections wrote 6.31 m
        # back over it.  Membership only, no value write, exactly like a
        # seam pin: the road's own descent law is what the hold protects,
        # and everything downstream of the terminus still yields.
        _svc_free_ends = {i for i in
                          (getattr(layout, "_svc_free_end_idx", None) or ())
                          if i < n}
        yield_hard |= _svc_free_ends
        # ── NOR DO THE MOUTH SEATS ────────────────────────────────
        # (owner law 2026-08-15, "a service road meeting a taxiway must
        # arrive AT that pavement's elevation"; gate
        # ``SVC_MOUTH_PROX_ANCHOR``.)  The seat IS the law's answer at
        # that node — it is the airside surface's own interpolated
        # value, read-only by ruling — so a pointwise yield here is the
        # law being overwritten, not a relaxation of it.  Membership
        # only, exactly like the free-end tie above.
        _svc_mouths = {i for i in
                       (getattr(layout, "_svc_mouth_prox_idx", None) or ())
                       if i < n}
        yield_hard |= _svc_mouths
        # ── THE WHOLE-RUN CORRIDOR PROFILE NEVER LEAVES THE HARD SET ──
        # (staged-solve round, S2, "WHOLE-RUN CORRIDOR PROFILE".)  A
        # corridor is ONE law object and its profile was solved over the
        # WHOLE run against its own cap and band; a pointwise yield here
        # re-humps it, which is the defect the round closes.  Membership
        # only, exactly like the free-end tie beside it.
        _svc_profile = {i for i in
                        (getattr(layout, "_svc_profile_idx", None) or ())
                        if i < n}
        yield_hard |= _svc_profile
        # BOUNDED YIELD (owner ruling 2026-07-29: "Any yield absolutely
        # needs to stay within the feasibility box").  Everything the
        # yield above released keeps its seat-time reach-band box as a
        # hard clamp inside the projection: a pad flat group translates
        # only within the intersection of its member seats' boxes; a
        # freed non-pad seat clamps to the band interval that seated it
        # (store artifact ``seat_boxes``, recorded by whatever seated the
        # node).  A node with no recorded box keeps the unbounded yield
        # — the clamp refines the yield, never adds a hold.  Conflicts
        # that exceed a box surface as remaining over-cap edges / break
        # regions instead of burying seated structures (HECA
        # building199: seated 101.13 by the reach band, parked at 87.94
        # by the unbounded projection — the south-terminal ~15 m drag;
        # the blunt hard-hold arm instead minted 9 runway grade
        # violations, the anti-goal).  STANDING LAW — there is no
        # unbounded-yield arm.
        _yield_group_bounds = None
        _yield_node_bounds = None
        _seat_box_idx: dict = {}
        # The seat boxes are a NODE-SPACE STORE artifact (U1),
        # canonical-key-keyed; resolve into THIS solve's index
        # space, intersecting keys that alias one node (tightest
        # per side).
        _seat_box_idx = _store_of(layout).view_interval(
            "seat_boxes", bucket_to_idx, n, combine="intersect")
        _pn = _pad_nodes if pad_groups else set()
        if pad_groups:
            _yield_group_bounds = []
            for _g in pad_groups:
                _gb = None
                for _i in _g:
                    _b = _seat_box_idx.get(_i)
                    if _b is not None:
                        _gb = (_b if _gb is None
                               else (max(_gb[0], _b[0]),
                                     min(_gb[1], _b[1])))
                _yield_group_bounds.append(_gb)
        # The freed non-pad seats are exactly the seat nodes no
        # longer in ``yield_hard`` (pads carry the group box above).
        _yield_node_bounds = {
            _i: _seat_box_idx[_i]
            for _i in building_seats
            if _i < n and _i not in yield_hard and _i not in _pn
            and _i in _seat_box_idx}
        # ── THE FREED GROUNDSIDE PINS ARE BOUNDED BY THEIR OWN LAW ────────
        # (cycle-5 fix 3, the other half of the demotion.)  A pin is no longer
        # an anchor, so it must not be unbounded either: it carries the LAW
        # ceiling the reach already computed — the weld datum plus one throat
        # of reach, with NO DEM term (``anchors.apply_groundside_reach`` builds
        # it, and the mouth verify-and-relax below has always used exactly this
        # bound for the pins it frees).  Fix 3 simply frees ALL of them
        # instead of only the ones that already contradicted, so the same
        # bound applies to the same class.
        #
        # Upper side only, matching the existing relax door's contract: a
        # mouth may always settle DOWN toward its seed.  The FLOOR comes from
        # the reach band, which binds per sweep as of fix 2.  A pin with no
        # weld datum has no entry and stays unbounded above — a missing datum
        # never becomes a terrain bound.
        #
        # The bounded pins are also CARRIED (``_gs_pin_bound_idx``) into the
        # projection: where this ceiling and the airside reach band cannot
        # both hold, the merge resolves the declared conflict BAND WINS and
        # the pin box yields (cycle-6 Part P; "airside is king" — the lot
        # conforms via the terrace/wall machinery).  Without the carry the
        # merge cannot tell a groundside ceiling from a building seat box.
        _gs_pin_bound_idx: set = set()
        if _gs_hard:
            _pin_ceil_fp8 = getattr(layout, "_gs_pin_law_ceiling_idx", None) or {}
            if _pin_ceil_fp8:
                _yield_node_bounds = dict(_yield_node_bounds or {})
                _n_pin_bound = 0
                for _gi in _gs_hard:
                    _c = _pin_ceil_fp8.get(_gi)
                    if _c is None or _gi >= n:
                        continue
                    _pb = _yield_node_bounds.get(_gi)
                    _yield_node_bounds[_gi] = (
                        (-1e18, float(_c)) if _pb is None
                        else (_pb[0], min(_pb[1], float(_c))))
                    _gs_pin_bound_idx.add(_gi)
                    _n_pin_bound += 1
                if _os.environ.get("O4_STEP_DEBUG") == "1":
                    print(f"    [groundside-reach] {_n_pin_bound} freed "
                          f"groundside pin(s) bounded by their LAW ceiling "
                          f"(weld datum + one throat of reach, no DEM term)")

        # ── ADJACENT-GROUND: ONE AUTHORITY, AND IT IS THE RELATIVE EDGE ───
        # (cycle-5 spec fix 1.)  This used to ALSO bind the zone law as an
        # absolute per-node box on the bounded-yield channel, snapshotting the
        # pavement foot datum from ``elev`` right here — and then fp#8 moved
        # that foot by p50 2.340 m / p90 24.949 m / max 88.905 m while the
        # frozen box went on clamping at seed and after every sweep.
        #
        # THE DECISIVE MEASUREMENT (attribution dossier §3, over all 20,135
        # over-cap ``graded_strip:adjacent_ground`` rows at fp#8 EXIT):
        #
        #     ground value inside the box implied by the fp#8-ENTRY datum
        #                                                  13,208   65.6 %
        #     ground value inside the box implied by the fp#8-EXIT datum
        #     (what the law actually asks)                  1,346    6.7 %
        #
        # The residual therefore could not go to zero by binding HARDER;
        # binding harder is what produced it.  So the box is DELETED and the
        # RELATIVE interval edge — already built, already correct, and already
        # in this joint — is the only authority.  What remains here is the
        # AUDIT that the deletion lost nothing.
        _zone_edge_nodes = {
            _e[0] for _sc in shape_constraints
            if _sc.get("ref") == "adjacent_ground"
            for _e in (_sc.get("edges") or ())}
        _zone_cov = _zone_law_coverage(
            layout, bucket_to_idx, n,
            getattr(layout, "_adjacent_ground_first_zone_index", 0),
            _zone_edge_nodes)
        if _zone_cov[0]:
            import O4_UI_Utils as _UI_zone
            _UI_zone.vprint(1,
                f"  [adjacent-ground] zone-law COVERAGE: {_zone_cov[2]} of "
                f"{_zone_cov[1]} resolved band node(s) carried by the "
                f"RELATIVE interval edge (the one authority); "
                f"{_zone_cov[3]} adopted a pavement variable by identity; "
                f"{_zone_cov[4]} UNCARRIED"
                + ("" if not _zone_cov[4] else
                   " — a published zone row whose law NOTHING enforces; "
                   "this must be 0")
                + f".  ({_zone_cov[0]} row(s) published.)  The absolute "
                f"foot-datum box is RETIRED (cycle-5 fix 1): it froze a "
                f"constraint derived from variables this same projection "
                f"then moved.")
        # NO REFERENCE RODS (build-complete-then-debug round).  The
        # §7 reference channel this block built — the pre-yield
        # snapshot, the rod-held corridor string, the pad-rod
        # coupling shadow, the apron reference surface R and the R1
        # reference field — is DELETED with the proximal pull that
        # consumed it.  A movable node is plain free here: it settles
        # wherever the caps, the bounded-yield boxes and the reach
        # band admit, under ONE authority (the law edges).
        joint = list(shape_constraints) + _unified_entries(
            u_edges, _u_pair_stage, "solve/joint")
        # DEBUG snapshot (O4_DUMP_SOLVE_STATE=<path>): pickle the final-
        # projection inputs so projection variants iterate OFFLINE (~1 s)
        # instead of via full rebuilds (~115 s).  Node lat/lon included so
        # an offline scorer can map emitted-patch nids to solver indices.
        _dump = _os.environ.get("O4_DUMP_SOLVE_STATE")
        if _dump:
            import pickle
            _ll = [layout.m_to_ll(x, y) for (x, y) in nodes]
            _cat = dict(_hard_cat)
            for i in runway_nodes:
                if i < n:
                    _cat.setdefault(i, "runway_node")
            for i in building_seats:
                if i < n:
                    _cat.setdefault(i, "seat")
            for i in _gs_hard:
                if i < n:
                    _cat.setdefault(i, "gs_pin")
            with open(_dump, "wb") as _fh:
                pickle.dump({
                    "elev": list(elev),
                    "joint_edges": [tuple(e) for sc in joint
                                    for e in sc["edges"]],
                    "yield_hard": set(yield_hard),
                    "pad_groups": [set(g) for g in pad_groups],
                    "nodes_m": list(nodes),
                    "nodes_ll": _ll,
                    "dem_elev": list(dem_elev),
                    "node_band": list(node_band),
                    "hard_cat": _cat,
                    # BOUNDED YIELD (2026-07-29): the live seat boxes
                    # (this solve's index space), so an offline fp#8
                    # replay passes the exact bounds the build did
                    # (node_band is only a proxy).
                    "seat_boxes": {
                        int(_bi): (float(_bl), float(_bh))
                        for _bi, (_bl, _bh) in _seat_box_idx.items()},
                    # Replay fidelity (2026-07-29): the zone-slab
                    # threshold fp#8 actually ran with — without it
                    # an offline replay mis-kinds the zone<->host
                    # slabs and inflates the broken set.
                    "interval_yield_from": _iyf,
                    # Spine graph (per-edge cap budgets) + runway
                    # anchors: lets an offline probe audit whether a
                    # node's solved level equals its cap-reachable
                    # ceiling (Dijkstra over budgets from anchors).
                    "spine_adj": {int(i): [(int(j), float(b))
                                           for (j, b) in lst]
                                  for i, lst in u_spine_adj.items()},
                    "runway_anchor": {int(i): float(a) for i, a
                                      in G.runway_anchor.items()},
                    # ── R1/P2-CP1 field-moment fields ────────────────
                    # ``elev`` above IS candidate B (the post-projection
                    # state today's snapshot reads); this is candidate A,
                    # spec §4.1 layer 6's ruled source state.
                    "elev_entry_A": _elev_entry_A,
                    # §10 rod slabs — the interval law that governs ALL
                    # strung vertices, so an offline replay enforces the
                    # same shape the build did.
                    "rod_edges": [(int(_a), int(_b), float(_lo),
                                   float(_hi))
                                  for (_a, _b, _lo, _hi) in _rod_edges],
                    # Chain identity: half-open [start, stop) spans of
                    # ``rod_edges`` per strung piece (free — already
                    # built for the rod law clamp above).
                    "rod_piece_spans": [(int(_p0), int(_p1))
                                        for (_p0, _p1)
                                        in _rod_piece_spans],
                    # The quarantine set the two projections declared.
                    "yield_broken": sorted(int(_i)
                                           for _i in _yield_broken),
                    "yield_hard": sorted(int(_i) for _i in yield_hard),
                    # Per-node building-frontage floor fed to the phase-A
                    # spine solve (P3 input; local to this scope).
                    "spine_floor": {int(_i): float(_v) for _i, _v
                                    in u_spine_floor.items()},
                    # P3 drag attribution: the five STAGE-LABELLED
                    # ``elev`` copies from inside the phase-A spine
                    # solve + the cross-corridor coupling adjacency,
                    # collected via its ``probe_out`` out-parameter.
                    "spine_stages": _spine_probe,
                    # ── fp#8 REPLAY FIDELITY (cycle-7 chore, 2026-08-06) ──
                    # ``joint_edges`` above is FLATTENED, and the flat list
                    # loses the three things the projection reads off the
                    # ENTRY: its law family, its ``envelope_skip`` flag, and
                    # whether it is still a lazy certificate.  A replay built
                    # from the flat list therefore judges a DIFFERENT
                    # constraint set from production's fp#8 — the exact
                    # instrument gap the c6attr dossier's tool-debt note
                    # names (``interval_reach_replay.py`` "is now
                    # unfaithful").  These keys close it; the flat list stays
                    # for the callers that already read it.
                    "joint_entries": [
                        {"family": _sc.get("family"),
                         "role": _sc.get("role"), "ref": _sc.get("ref"),
                         "envelope_skip": bool(_sc.get("envelope_skip")),
                         # A thunk is not picklable and its body pairs are
                         # not generated yet: the flag is recorded so a
                         # replay can SAY how many entries it could not
                         # carry rather than silently dropping law.
                         "lazy": _sc.get("lazy_expand") is not None,
                         "edges": [tuple(_e) for _e in (_sc.get("edges")
                                                        or ())]}
                        for _sc in joint],
                    # The certificate's family axis, in ORIGINAL node space —
                    # what ``feasibility_project(family_of=...)`` re-keys.
                    "family_by_pair": {(int(_a), int(_b)): _f
                                       for (_a, _b), _f
                                       in _u_family_of.items()},
                    # THE fp#8 KWARGS.  Every argument the production call
                    # passes that is not already a top-level key, so a replay
                    # reconstructs the call verbatim instead of guessing.
                    # ``env_band`` is ``node_band`` itself when the gate is
                    # on (``solve.py`` ``_env_band = node_band if
                    # _ENV_FROM_BAND else None``), so the flag plus the
                    # existing ``node_band`` key carries it losslessly.
                    "fp8_kwargs": {
                        "group_bounds": _yield_group_bounds,
                        "node_bounds": _yield_node_bounds,
                        "gs_pin_nodes": (sorted(int(_i)
                                                for _i in _gs_pin_bound_idx)
                                         if _gs_pin_bound_idx else None),
                        "witness_excluded": (sorted(int(_i) for _i
                                                    in _route_excluded)
                                             if _route_excluded else None),
                        "gs_witness": ((sorted(int(_i)
                                               for _i in _gs_witness[0]),
                                        _gs_witness[1])
                                       if _gs_witness else None),
                        "env_band_is_node_band": _env_band is not None,
                    },
                }, _fh)
            print(f"    [dump] solve state -> {_dump} "
                  f"(+A-copy, {len(_rod_edges)} rod slab(s))")
        # 2400 sweeps: with tightest-budget edge dedup the polytope is
        # consistent and the scalar GS CONVERGES (SPJC: worst residual
        # 0.025 at 800 sweeps → 0.0000 at 1702; the old "oscillation
        # plateau" was the first-edge-wins dedup enforcing conflicting
        # duplicate budgets).  Cap with headroom; the loop exits early
        # at tol.
        _scoped_gate = _scoped_projection_enabled()
        # Capture the BROKEN quarantine (genuine anchor contradictions,
        # full-graph detection) for the scoped final projection — its
        # sparser graph can miss the same contradictions and grind POCS
        # on the infeasible pockets instead (measured: CYXY 66 k → 11.5 M
        # worklist visits).  Keys, not indices: the projection rebuilds
        # its own node list.
        _solve_broken_idx: set = set()
        # (The §7 pre-yield re-string + ``yield_hard`` hold that
        # lived here were DELETED by spec §10 — the string is now
        # ordinary law via the interval-rod entry registered after
        # phase A, so this yield and everything downstream maintain
        # the string's shape without any value-hold to fight.)
        # BREAK FORENSICS (spec reference-honesty Track 1 step 4, gate
        # ``O4_BREAK_FORENSICS=<path>``): the anchor CLASS map + node
        # lat/lons the report names its witness pairs with.  Unset ⇒
        # nothing is built and nothing is passed.
        _fp8_forensics = None
        if _os.environ.get("O4_BREAK_FORENSICS"):
            _fcat = dict(_hard_cat)
            for _i in runway_nodes:
                if _i < n:
                    _fcat.setdefault(_i, "runway_node")
            for _i in building_seats:
                if _i < n:
                    _fcat.setdefault(_i, "seat")
            for _i in _gs_hard:
                if _i < n:
                    _fcat.setdefault(_i, "gs_pin")
            for _i in _seam_pin_idx:
                if _i < n:
                    _fcat.setdefault(_i, "seam_pin")
            for _i in u_spine_nodes:
                if _i < n:
                    _fcat.setdefault(_i, "spine")
            _fp8_forensics = {
                "label": "fp#8",
                "classes": _fcat,
                "nodes_ll": [layout.m_to_ll(_x, _y) for (_x, _y) in nodes],
            }
        _t_fp8 = _time.perf_counter()
        rem, bh = feasibility_project_partitioned(
                                      elev, joint, yield_hard,
                                      receiver_nodes=_solve_receivers, n_nodes=n,
                                      forensics=_fp8_forensics,
                                      witness_limited=_gs_witness,
                                      force_scalar=True,
                                      # SWEEP BUDGET: derived from this
                                      # projection's own graph inside
                                      # ``feasibility_project`` (the hand-set
                                      # 2400 was BINDING and chose surfaces —
                                      # config's derivation note).  No
                                      # ``max_iters`` here BY DESIGN.
                                      flat_groups=pad_groups or None,
                                      interval_yield_from=_iyf,
                                      broken_out=(_solve_broken_idx
                                                  if _scoped_gate
                                                  else None),
                                      group_bounds=_yield_group_bounds,
                                      node_bounds=_yield_node_bounds,
                                      gs_pin_nodes=(_gs_pin_bound_idx
                                                    or None),
                                      witness_excluded=_route_excluded,
                                      env_band=_env_band,
                                      family_of=_u_family_of)
        _t_fp8_end = _time.perf_counter()
        # ── PROBE A, TAIL BOUNDARY 1: fp#8 (spec §1 extension) ────
        # STAMPED OUTSIDE THE ``_t_fp8`` WINDOW (spec §0.3 — the
        # ``[spine-yield]`` line is a published A/B number), and the
        # fp#8 call is NOT given ``probe_out`` for the same reason:
        # one post-call diff, no snapshot inside the timed region.
        if _mover is not None:
            _mover_stamp(_mover, _mover_snapshot(_mover, elev), "fp8")
        # Tagged ``[spine-yield]``, NOT ``[taut-string]``: this line
        # must print on BOTH sides of the gate or the held-vs-baseline
        # delta is unmeasurable, and a gate-OFF run must emit zero
        # ``[taut-string]`` lines.
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [spine-yield] fp#8 body yield "
                  f"{_t_fp8_end - _t_fp8:.3f}s "
                  f"hard={len(yield_hard)}")
        # MOUTH VERIFY-AND-RELAX (user 2026-07-06, HECA #541/#546): the
        # groundside mouth welds (``_gs_hard``) were pinned from lot
        # rings computed BEFORE this movable-pad/free-seat yield — a
        # building pad or apron body that settles at a different level
        # leaves a road-ring edge pad↔mouth over-cap with BOTH ends
        # effectively hard (mutually conflicting weld authorities; the
        # DEM-follow break blend cannot fire on a sliver with no
        # interior nodes).  Verify every welded mouth against the joint
        # law edges; where violated, FREE the whole mouth cluster (ONE
        # authority: the joint solve), re-project warm, and have the
        # LOT adopt the projected mouth profile (exact at freed
        # vertices, cap-decay fill, chord-limited) so road and lot
        # still emit as one lawful welded surface.
        if _gs_hard:
            # Spec kill-prep §1 (owner 2026-08-03): the class-universal
            # absorption ruling governs BOTH exports below — A2's
            # unconditional freed-cluster export and A3's weld↔weld
            # pocket.  See each site.
            from auto_patch.config import (
                SERVICE_LOT_ABSORPTION as _CLASS_UNIVERSAL)
            _VIOL_TOL_M = 0.03
            _conflicted: set = set()
            for _sc in joint:
                for _e in _sc["edges"]:
                    if len(_e) >= 4:
                        continue      # interval edge (Stage B0): not a
                        #               symmetric-budget mouth weld
                    _a, _b, _bud = _e[0], _e[1], _e[2]
                    if (_a >= n or _b >= n
                            or (_a not in _gs_hard
                                and _b not in _gs_hard)):
                        continue
                    # weld↔weld edges are the LOT↔LOT class — the
                    # reach-time reconciliation owns those (both lots
                    # are final there); freeing both welds here lets
                    # the solve drag them apart (HECA #522: 0.8 m →
                    # 2.1 m after a both-weld free).
                    if _a in _gs_hard and _b in _gs_hard:
                        continue
                    if abs(elev[_a] - elev[_b]) > _bud + _VIOL_TOL_M:
                        if _a in _gs_hard:
                            _conflicted.add(_a)
                        if _b in _gs_hard:
                            _conflicted.add(_b)
            if _conflicted:
                from .anchors import (adopt_projected_mouths,
                                      expand_mouth_cluster)
                _freed = expand_mouth_cluster(
                    layout, bucket_to_idx, _conflicted, _gs_hard)
                # ── STAGE B MAY NOT WRITE STAGE A (S1c, coupling 11) ──────
                # This scan frees a mouth CLUSTER from the hard set because a
                # GROUNDSIDE weld violates a law edge — and the cluster
                # expansion walks rings, so it can free AIRSIDE nodes too.
                # Freeing an airside node is a write to stage A authored by a
                # groundside conflict, which the staged law forbids outright
                # ("nothing in stage B may write, re-project or re-blend a
                # stage-A row").  The groundside half of the cluster still
                # frees and still re-projects; the airside half stays hard and
                # the lot adopts the profile it finds, which is the mouth
                # ruling (RULINGS 2026-08-06) unchanged.
                _freed_air = _freed - _solve_receivers
                if _freed_air:
                    import O4_UI_Utils as _UI_f
                    _UI_f.vprint(
                        1, f"    [stage] mouth-cluster conflict: "
                           f"{len(_freed_air)} of {len(_freed)} freed node(s) "
                           f"are AIRSIDE and stay hard (a groundside weld "
                           f"violation never frees an airside variable)")
                    _freed = _freed & _solve_receivers
                yield_hard = yield_hard - _freed
                # GROUNDSIDE PIN LAW BOUND (spec §C.2 ★, datum replaced by
                # item 3(a)): the freed mouth cluster is re-projected and
                # the LOT then ADOPTS the projected profile — so an
                # unbounded re-projection re-imports exactly the float §C
                # removes, through the relax door.  Carry the pin's LAW
                # ceiling (weld datum + one throat of reach; NO DEM term)
                # as a bounded-yield box on every freed mouth node (the
                # landed ``node_bounds`` machinery; upper side only — a
                # mouth may always settle DOWN toward its seed).  A pin
                # with no weld datum has no entry and stays unbounded
                # above: a missing datum never becomes a terrain bound.
                _relax_node_bounds = _yield_node_bounds
                _relax_pin_idx = set(_gs_pin_bound_idx)
                _pin_ceil = getattr(
                    layout, "_gs_pin_law_ceiling_idx", None) or {}
                if _pin_ceil:
                    _relax_node_bounds = dict(_yield_node_bounds or {})
                    for _fi in _freed:
                        _c = _pin_ceil.get(_fi)
                        if _c is None or _fi >= n:
                            continue
                        _pb = _relax_node_bounds.get(_fi)
                        _relax_node_bounds[_fi] = (
                            (-1e18, float(_c)) if _pb is None
                            else (_pb[0], min(_pb[1], float(_c))))
                        # Same carry as fp#8: a pin ceiling installed through
                        # the relax door yields to the band on conflict too,
                        # or the lift returns through exactly that door
                        # (cycle-6 Part P).
                        _relax_pin_idx.add(_fi)
                # Same BOUNDED YIELD boxes as fp#8 above: the
                # mouth-relax re-projection moves the same freed seats
                # and must not un-do the clamp.
                # SWEEP BUDGET derived from the graph (the 1200 this used to
                # pass was half the already-binding final cap; a re-projection
                # over the SAME law graph needs the same propagation distance,
                # so there was never a reason for it to be smaller).
                rem, bh = feasibility_project_partitioned(
                    elev, joint, yield_hard, force_scalar=True,
                    receiver_nodes=_solve_receivers, n_nodes=n,
                    flat_groups=pad_groups or None,
                    interval_yield_from=_iyf,
                    witness_limited=_gs_witness,
                    group_bounds=_yield_group_bounds,
                    node_bounds=_relax_node_bounds,
                    gs_pin_nodes=_relax_pin_idx or None,
                    witness_excluded=_route_excluded,
                    env_band=_env_band)
                _n_adopted = adopt_projected_mouths(
                    layout, bucket_to_idx, elev, _freed, _gs_hard)
                # ── PROBE A, TAIL BOUNDARY 2: mouth_relax ─────────
                # One boundary for the whole stage (re-projection +
                # lot adoption), stamped after both.
                if _mover is not None:
                    _mover_stamp(_mover, _mover_snapshot(_mover, elev),
                                 "mouth_relax")
                # A relaxed mouth is a solver-DECLARED authority-
                # conflict pocket: export it to the break quarantine
                # (a fully reconciled mouth has no over-cap pairs, so
                # the export is inert there; a residual blend — e.g.
                # the lot ring the adoption re-shaped around the
                # solved mouth — is quarantined honestly instead of
                # reading as an actionable solver miss).
                # CLASS-UNIVERSAL ABSORPTION (owner 2026-08-03, spec
                # kill-prep §1): "inert there" was never tested — the
                # export fired UNCONDITIONALLY on the whole freed
                # cluster, and 48 of HECA's + 6 of HEAZ's exported
                # nodes carry ZERO deficit (quarret2 decomposition).
                # Under the gate the mouth is RE-TESTED after the
                # adoption and only a still-deficient node reports;
                # quarantine is unauthorized (docs/RULINGS.md), so a
                # reconciled mouth exports nothing at all.
                if _CLASS_UNIVERSAL:
                    _still_deficient: set = set()
                    for _sc in joint:
                        for _e in _sc["edges"]:
                            if len(_e) >= 4:
                                continue
                            _a, _b, _bud = _e[0], _e[1], _e[2]
                            if (_a >= n or _b >= n
                                    or (_a not in _freed
                                        and _b not in _freed)):
                                continue
                            if abs(elev[_a] - elev[_b]) <= (
                                    _bud + _VIOL_TOL_M):
                                continue
                            if _a in _freed:
                                _still_deficient.add(_a)
                            if _b in _freed:
                                _still_deficient.add(_b)
                    _solve_broken_idx |= {i for i in _still_deficient
                                          if i < n}
                    if _os.environ.get("O4_STEP_DEBUG") == "1":
                        print(f"    [mouth-relax] re-tested "
                              f"{len(_freed)} freed node(s): "
                              f"{len(_still_deficient)} still "
                              f"deficient → exported")
                else:
                    _solve_broken_idx |= {i for i in _freed if i < n}
                if _os.environ.get("O4_STEP_DEBUG") == "1":
                    print(f"    [mouth-relax] {len(_conflicted)} "
                          f"conflicted weld(s) → freed cluster "
                          f"{len(_freed)}; {_n_adopted} lot ring(s) "
                          f"adopted the solved profile")
            # WELD↔WELD residuals (HECA #522): two lots' mouth welds on
            # one road ring can still contradict after the reach-time
            # lot↔lot reconciliation (later passes move the field the
            # reconciliation measured against).  Both ends are truth
            # welds — neither may yield — so a still-violated edge is
            # a genuine break pocket: export both mouths.
            # THE PREMISE DISSOLVES under the class-universal
            # absorption ruling (owner 2026-08-03, spec kill-prep §1):
            # a road welded to a lot IS the lot — the two "authorities"
            # are ONE laterally-contiguous surface taking ONE
            # (strictest) cap, so "neither may yield" describes a
            # topology that no longer exists.  Under the gate the scan
            # stays as a REPORTER and exports nothing; the residual is
            # a visible violation of that one surface's law.
            _n_weld_pocket = 0
            for _sc in joint:
                for _e in _sc["edges"]:
                    if len(_e) >= 4:
                        continue      # interval edge (Stage B0)
                    _a, _b, _bud = _e[0], _e[1], _e[2]
                    if (_a >= n or _b >= n
                            or _a not in _gs_hard
                            or _b not in _gs_hard):
                        continue
                    if abs(elev[_a] - elev[_b]) > _bud + _VIOL_TOL_M:
                        if not _CLASS_UNIVERSAL:
                            _solve_broken_idx.add(_a)
                            _solve_broken_idx.add(_b)
                        _n_weld_pocket += 1
            if _n_weld_pocket and _os.environ.get(
                    "O4_STEP_DEBUG") == "1":
                print(f"    [mouth-relax] {_n_weld_pocket} weld↔weld "
                      f"edge(s) still contradictory → "
                      f"{'REPORT only' if _CLASS_UNIVERSAL else 'break export'}")
        # EDGE FAIRING (user 2026-07-04, CYXY taxiway E): the spine
        # fairing law covers spine CHAINS only — a corridor's ring
        # EDGE still tracks noise in legal ±cap wiggles (E's edge
        # alternated +2.3 %/+0.8 % every 12 m around a 1.55 % mean).
        # Apply the same second-difference POCS to STRAIGHT boundary
        # runs of airside rings (corners are real grade breaks —
        # skipped by the bend test; anchors never move; band-clamped).
        # SCOPED FINAL PROJECTION (user 2026-07-05): the edge fairing is
        # the ONE pass between the yield projection (which enforced every
        # pair) and the writeback that moves nodes WITHOUT re-enforcing
        # their pairs — record which nodes it moved so the scoped
        # projection treats their shapes as changed (the "unchanged ⇒
        # already enforced" proof does not cover fairing-perturbed nodes).
        _pre_fairing_elev = list(elev) if _scoped_gate else None
        from auto_patch.config import TAXIWAY_MAX_GRADE_CHANGE_PER_M
        # RESA-CUT FAIRING EXEMPTION (arc R slice R1): the cut is
        # a free terrain leaf under ONE envelope edge — no
        # within-shape rule, no fairing (the law trace).  Its ring
        # vertices only resolve to FREE nodes once admitted, so
        # with the gate off the set is empty and this is
        # byte-inert.  ADOPTED cut vertices are excluded: those
        # ARE pavement variables and keep the pavement's fairing.
        _resa_no_fair = ({i for i in _resa_idx
                          if i >= (_terrain_first or 0)}
                         if _resa_idx else None)
        _n_ekink = _fair_ring_edges(
            layout, elev, bucket_to_idx, yield_hard, node_band,
            TAXIWAY_MAX_GRADE_CHANGE_PER_M,
            skip_nodes=_resa_no_fair)
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [edge-fairing] residual kinks={_n_ekink}")
        # ── PROBE A, TAIL BOUNDARY 3: ring_fairing ────────────────
        if _mover is not None:
            _mover_stamp(_mover, _mover_snapshot(_mover, elev),
                         "ring_fairing")
        _fairing_moved_keys = None
        if _pre_fairing_elev is not None:
            _fairing_moved_keys = {
                key for key, i in bucket_to_idx.items()
                if elev[i] != _pre_fairing_elev[i]}
        # ── GAP-SPINE longitudinal fairing (Slice B stage B2, ratified
        # 2026-07-10) ─────────────────────────────────────────────────
        # The projection above drove every spine node into its envelope
        # interval (a feasible point, not a smooth one — POCS finds ANY
        # point of the intersection).  The longitudinal law is the
        # project's own spine-curvature law, TAXIWAY_MAX_GRADE_CHANGE_
        # PER_M as a second-difference cap (the ``_fair_spine_chains``
        # form), applied per gap-spine chain with every move clamped
        # back into the node's envelope interval read at the CURRENT
        # (settled) station elevations — so smoothing never exits the
        # law the interval edges enforce.  Spine nodes belong to no
        # shape ring, so this pass cannot perturb the scoped-projection
        # proof or any pavement value.  Gate OFF: no chains, no-op.
        if _gap_spine_chains:
            from auto_patch.config import (
                TAXIWAY_MAX_GRADE_CHANGE_PER_M as _K_GAP_SPINE)
            _n_gap_kink = _fair_gap_spine_chains(
                elev, _gap_spine_chains, _K_GAP_SPINE,
                frozen=base_hard)
            if _os.environ.get("O4_STEP_DEBUG") == "1":
                print(f"    [gap-spine] fairing residual "
                      f"kinks={_n_gap_kink}")
        # ── PROBE A, TAIL BOUNDARY 4: gap_spine_fairing ──────────────
        # Unconditional (a no-op diff when there were no chains) so the
        # ledger's last boundary is always the same statement.
        if _mover is not None:
            _mover_stamp(_mover, _mover_snapshot(_mover, elev),
                         "gap_spine_fairing")
        # (The §7 taut-string witness + final-hold canonical-key export
        # that lived here were DELETED by spec §10.  The interval-rod
        # entry registered after phase A carries the string's shape
        # through every projection above, and its canonical-key form —
        # ``layout._taut_rod_key_edges`` — is what
        # ``final_grade_projection`` maps into its rebuilt node space.)
    _psub(0.97, "Solving elevations — writing back")
    # ── SPINE CROWN v2 (user 2026-07-07, part 30) ────────────────────
    # The whole solve above ran in UNCROWNED space z′.  The crown is a
    # designed sub-cap offset field c (crown.build_crown_drop_field):
    # writeback emits z = z′ − c.  Because c is single-valued per
    # canonical node, welds stay consistent; because the law reads the
    # pair offset o_ab = c_b − c_a (grade_law.crown_pair_offset), the
    # emitted surface satisfies |Δz − o| ≤ budget exactly where the
    # solve satisfied |Δz′| ≤ budget — solver and validator share ONE
    # field (exported via the axes sidecar).  Terrain/value contracts
    # (seam pins, building seats, groundside mouth welds, seam spine
    # anchors) are frozen at c = 0.  RUNWAY ring nodes crown through
    # this same transform (uniform per-ref drop) — every in-solve
    # reader (flex, join anchors, crossings, seam pins) sees the one
    # uncrowned profile space, and the emitted edges sit at
    # profile − drop while the spine breakline carries the profile.
    from auto_patch.config import ENABLE_SPINE_CROWN as _CROWN_ON
    from shapely.errors import (GEOSException as _CrGE,
                                TopologicalError as _CrTE)
    _GEOM_EXC = (ValueError, _CrGE, _CrTE)
    _crown_drop_idx: dict = {}
    if _CROWN_ON:
        try:
            from auto_patch.crown import (build_crown_drop_field,
                                          emit_crown_spines)
            # Frozen VALUE CONTRACTS: seam pins (cross-tile terrain),
            # building seats, groundside mouth welds, seam spine
            # anchors.  Runway nodes are NOT frozen — they crown
            # through the field at their uniform per-ref drop.
            _crown_freeze = (
                {i for i in building_seats if i < n}
                | {i for i in _gs_hard if i < n}
                | {i for i in _seam_pin_idx if i < n}
                # Gap-fill drainage-spine nodes (Slice B stage B2)
                # are frozen at crown drop 0 like every other spine
                # breakline node ("spine nodes never crown") — the
                # emitted open way must carry the solved profile,
                # not a crowned copy the face disagrees with.
                | {i for i in _gap_spine_idx if i < n}
                # Adjacent-ground zone-row nodes (Slice B stage B3
                # order 2) are TERRAIN, not pavement — no crown.
                | {i for i in _zone_idx if i < n}
                # Runway-end RESA CUT rows (arc R slice R1) are
                # TERRAIN too — no crown.  This is REDUNDANT and
                # deliberately so: ``crown.build_crown_drop_field``
                # already freezes them by ROLE (every ring vertex of a
                # non-runway, non-taxi/service shape lands in
                # ``frozen_keys``), exactly as it does the skirt.
                # Stating it here makes the contract explicit at the
                # call site instead of implicit in a role table;
                # ``test_runway_end_resa_cut.TestResaCrownFrontier``
                # pins the role-keyed path independently (the R2
                # "assert it, don't assume it" mandate).  Only the
                # FREE cut nodes are
                # listed: an adopted vertex IS a pavement variable and
                # must keep the pavement's crown.
                | {i for i in _resa_idx
                   if i < n and i >= (_terrain_first or 0)}
                | {i for i, _cat in _hard_cat.items()
                   if _cat in ("seam_spine_anchor", "seat_on_spine",
                               "gs_pin")})
            # RUNWAY-JOIN anchored nodes (user ruling 2026-07-16):
            # they carry the anchored runway value through the
            # uncrowned solve, so the field assigns each the drop
            # that lands its emitted value ON the anchor shape's
            # EMITTED edge at the anchor sample point — the join
            # anchors to the CROWNED EDGE value, never the
            # centerline/crown profile.
            _join_samples = {
                i: s for i, s in G.runway_anchor_sample.items()
                if i < n and _hard_cat.get(i) == "rwy_join"}
            _crown_drop_idx = build_crown_drop_field(
                layout, nodes, bucket_to_idx, _crown_freeze,
                join_anchor_samples=_join_samples, elev=elev)
            # Join-gate diagnostics (probes / forensics): the
            # anchored join nodes with their anchored value, anchor
            # sample point and assigned writeback drop.
            layout._runway_join_anchor_debug = [
                (float(nodes[i][0]), float(nodes[i][1]),
                 float(elev[i]), float(_crown_drop_idx.get(i, 0.0)),
                 float(s[0]), float(s[1]))
                for i, s in _join_samples.items()]
            # solve-time node registry: post-solve ring inserts are
            # recognised (and field-interpolated) against this set.
            layout._crown_solved_keys = set(bucket_to_idx)
        except _GEOM_EXC as _crown_exc:
            import O4_UI_Utils as _UIc
            _UIc.vprint(1, f"  [pav-builder] WARN: {icao}: crown "
                           f"field failed ({_crown_exc!r}) — flat "
                           f"sections emitted.")
            _crown_drop_idx = {}
    # ══ PROBE A DELIVERY, THE PIN-DRAG TAIL (spec §1 extension) ══════
    # Separation (i) proved the G2 pin drag is REAL (identity-joined
    # median 0.2520 m) and BROAD — not concentrated on conflict rows —
    # so the conflict-ledger window above cannot attribute it.  Read
    # every kept pin ONE statement before the emit copy, in the SAME
    # UNCROWNED FRAME the pin value lives in (``elev`` is uncrowned
    # until the writeback below subtracts ``_crown_drop_idx``), and
    # ship the per-pin row plus the last-writer histogram.
    # Write-only: nothing here is read back by the solve.
    if _mover is not None and _string_pins:
        _pd_rows = []
        _pd_lab: dict = {}
        for _pv, _pz in sorted(_string_pins.items()):
            if _pv >= n:
                continue
            _plab = _mover["label"].get(_pv)
            _pd_rows.append({"vertex": int(_pv),
                             "pin_z": float(_pz),
                             "z_at_emit_copy": float(elev[_pv]),
                             "last_writer": _plab})
            _pd_lab.setdefault(_plab, []).append(
                abs(float(elev[_pv]) - float(_pz)))
        _pd_counts = {}
        for _plab, _pds in _pd_lab.items():
            _pds.sort()
            _pm = len(_pds) // 2
            _pd_counts[_plab] = {
                "n": len(_pds),
                "median_abs_dz_m": (_pds[_pm] if len(_pds) % 2
                                    else 0.5 * (_pds[_pm - 1]
                                                + _pds[_pm]))}
        _summary["pin_drag"] = _pd_rows
        _summary["pin_drag_counts"] = _pd_counts
        # ── HAND THE LEDGER TO THE FINAL PROJECTIONS (spec amendment)
        # The two ``final_grade_projection`` passes run AFTER this
        # function returns, from the pipeline, on the same ``layout``
        # — the established solve→final handoff (``_taut_rod_key_
        # edges``, ``_crown_drop_key``, ``_crown_solved_keys`` all
        # travel this way).  Rows are shared by REFERENCE, so a pass
        # that re-stamps them updates the summary in place.  Attached
        # only under the gate; ``getattr(..., None)`` there otherwise.
        _mover["pin_rows"] = _pd_rows
        _mover["summary"] = _summary
        layout._string_mover_ledger = _mover
        from .taut_string import write_string_sidecar as _ws2
        _ws2(layout)                      # last call wins
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [mover-ledger] pin drag over {len(_pd_rows)} "
                  f"kept pin(s): "
                  + ", ".join(f"{_k}={_v['n']}"
                              for _k, _v in sorted(_pd_counts.items(),
                                                   key=lambda kv: str(
                                                       kv[0]))))
    # ── SPINE-FREEZE ROUND: THE MOVEMENT REPORT ──────────────────────
    # "Every yielded movement is reported write-only with its binding
    # constraint."  Taken HERE — one statement before the emit copy, in
    # the SAME UNCROWNED frame the phase-A snapshot was taken in, and
    # spine nodes are crown-frozen (c = 0, see the gap-spine writeback
    # note below), so ``elev`` at a yield node IS its shipped value.
    # The binding scan reads the joint edge set the last projection
    # enforced; nothing is read back by the solve.
    if _spine_phase_a:
        _spine_yield_movement_report(
            icao, _spine_phase_a, elev, n,
            list(shape_constraints) + _unified_entries(
                u_edges, _u_pair_stage, "solve/spine_report"),
            _spine_preserved, _spine_yield_idx,
            latlon_of=lambda i: layout.m_to_ll(*nodes[i]))
    # ── THE SOLVE'S OWN EXIT CERTIFICATE (cycle-5 spec fix 4) ─────────
    # Until now the ONLY ``[proj-law-certificate]`` in the build ran
    # inside ``final_grade_projection``, on that pass's REBUILT
    # constraint set in a DIFFERENT node space (142,635 / 144,056 vs the
    # solve's 146,743 at HECA).  Its own docstring says what it measures:
    # "the solve's values under the projection's law" — which is not the
    # solve's exit state, so the one number the single-solve architecture
    # is judged on had no reader at all.
    #
    # This is that reader: the SOLVE's joint, the SOLVE's ``elev``, the
    # SOLVE's node space, taken one statement before the writeback
    # publishes the field — in the uncrowned z′ frame the law lives in
    # (before the crown drop below, which is an EMIT transform, not a law
    # move).  ``yield_hard`` is the immovable set the last projection ran
    # with, so the both-hard column names genuine anchor↔anchor
    # contradictions.  Pure measurement, no gate: certify-or-fail-loud is
    # kept explicitly by RULINGS 2026-08-05 (BUILD-COMPLETE-THEN-DEBUG
    # item 1) while byte-identity ceremony is retired.
    _solve_exit_joint = list(shape_constraints) + _unified_entries(
        u_edges, _u_pair_stage, "solve/exit_certificate")
    _report_law_certificate(
        icao, "SOLVE EXIT",
        projection_law_certificate(_solve_exit_joint, elev, n, yield_hard,
                                   family_of=_u_family_of),
        # THE FRAME (binding point 3): the SOLVE's node space, and the
        # uncrowned z′ frame the law lives in — this reading is taken
        # before the crown drop below, which is an EMIT transform.  The
        # final passes' ENTRY/EXIT readings stamp their OWN (rebuilt,
        # smaller) node space, so the reader can see at a glance that
        # the three numbers are not comparable.
        n_nodes=n, crown_space="uncrowned z'")
    if _crown_drop_idx:
        _elev_emit = list(elev)
        for _i, _c in _crown_drop_idx.items():
            if _i < n:
                _elev_emit[_i] = _elev_emit[_i] - _c
    else:
        _elev_emit = elev
    n_terms, n_rects, n_juncs = _writeback(layout, _elev_emit,
                                           bucket_to_idx)
    # ── THE CARRIED LAW CONTEXT (cycle-4 ingestion spec requirement 1:
    # "one law, one source") ────────────────────────────────────────
    # Every law input ``final_grade_projection`` needs is captured HERE,
    # ONCE, at the moment the one solve publishes its surface, and keyed
    # by CANONICAL POINT ID — the node identity audited stable across
    # every post-solve pass.  Never by node index (the rod-key lesson),
    # never re-derived downstream from raw shapes and roles where the
    # re-derivation can disagree with what the solve was handed.
    #
    #   ``solved_values``  — the field this solve published, in EMITTED
    #     (uncrowned) space, exactly as ``_writeback`` stamped it.  It is
    #     what makes the projection's idempotence requirement decidable:
    #     a node whose seed still equals its solved value, and whose key
    #     the solve already had, was touched by nothing and must exit the
    #     projection where the solve left it.
    #   ``building_seats`` — the seats the near-miss frontage law is
    #     built from.  The projection cannot re-derive them (they are a
    #     solve-phase artifact), which is exactly why that law family was
    #     missing from its edge set.
    #   ``gs_witness``     — the groundside route pins whose feasibility-
    #     witness role the owner's ruling bounds.  The projection used to
    #     re-derive a DIFFERENT population by geometric proximity.
    # EVERY key of an index, not one per index: two canonical keys can
    # alias to one solve-time variable and split again in a rebuilt node
    # space, and a key that did not travel is a node the projection would
    # read as NEW — i.e. silently outside the hold.  Coverage is the whole
    # point of the carry.
    _keys_of: dict = {}
    for _ck, _ci in bucket_to_idx.items():
        if _ci < n:
            _keys_of.setdefault(_ci, []).append(_ck)
    _law_store = _store_of(layout)
    # THE PUBLISHED SURFACE IS READ BACK THROUGH THE PROJECTION'S OWN
    # READER, not copied out of ``elev``.  Two reasons, both measured:
    #   * ``_writeback`` stamps PAVEMENT roles only, so ``elev`` still
    #     holds the untouched DEM SEED at every node the solve did not
    #     value — carrying those would claim a solved value the solve
    #     never published (measured HEAZ, plateau: 36,828 of 40,284
    #     nodes carried 1.00 m against a layout holding 79.30 m).
    #   * identical readback semantics are what make the comparison
    #     downstream exact: same function, same node space, no dem —
    #     the rule ``_capture_projection_snapshot`` already follows.
    # ``readonly=True`` forbids minting canonical points; the four
    # attributes the seeder publishes are snapshotted and restored,
    # since this call is a MEASUREMENT of the solve's own node space and
    # must not republish anything in it.
    _pub_names = ("_seam_pin_idx", "_seam_pin_ll", "_seam_pin_residuals",
                  "_eat_anchor_pin_idx", "_eat_anchor_pin_prev",
                  "_eat_anchor_pin_rect")
    _pub_saved = {_pn: getattr(layout, _pn, None) for _pn in _pub_names}
    try:
        _published, _, _ = _seed_elevations(layout, nodes, bucket_to_idx,
                                            readonly=True)
    finally:
        for _pn, _pv in _pub_saved.items():
            if _pv is None:
                if hasattr(layout, _pn):
                    try:
                        delattr(layout, _pn)
                    except AttributeError:             # pragma: no cover
                        pass
            else:
                setattr(layout, _pn, _pv)
    _law_store.mint(
        "solved_values", "scalar",
        {_ck: float(_published[_ci])
         for _ci, _cks in _keys_of.items() for _ck in _cks},
        replace=True)
    _law_store.mint(
        "building_seats", "scalar",
        {_ck: float(_lv) for _i, _lv in building_seats.items()
         if _lv is not None for _ck in _keys_of.get(_i, ())},
        replace=True)
    _law_store.mint(
        "gs_witness", "keyset",
        {_ck for _i in (_gs_hard or ()) for _ck in _keys_of.get(_i, ())},
        replace=True)
    # ── GAP-SPINE writeback (Slice B stage B2, ratified 2026-07-10)
    # WHO WRITES WHAT: the solve writes ONLY the spine nodes — their
    # solved values go into the pre-solve store, which the post-solve
    # emitter reads in place of the retired analytic valuation.  The
    # gap-face RING vertices are shared pavement registry nodes:
    # their values are written by their OWN pavement shapes through
    # ``_writeback`` above (pavement identity — one node, one value,
    # never a second writer).  ``_elev_emit`` is used for
    # consistency with the writeback; spine nodes are crown-frozen
    # (c = 0), so it equals ``elev`` at every spine index.
    if _gap_spine_idx:
        _cps_gap = layout.canonical_points
        for _gap_entry in (getattr(layout, "gap_fill_presolve", None)
                           or ()):
            _gap_vals: list = []
            for _gx, _gy in _gap_entry["spine"]:
                _gi = bucket_to_idx.get(
                    _cps_gap.get_or_add(float(_gx), float(_gy)))
                _gap_vals.append(
                    float(_elev_emit[_gi])
                    if _gi is not None and _gi < n else None)
            _gap_entry["values"] = _gap_vals
    # ── ADJACENT-GROUND ZONE-ROW writeback (Slice B stage B3 order 2)
    # THE EMITTED BAND VALUE IS THE SOLVED VALUE.  Nothing is
    # re-derived here: the zone law is carried by the RELATIVE interval
    # edge (``solver_primitives.zone_constraint_entries`` — ground
    # against its host pavement ring vertex, two variables), the
    # variable was seeded at its published ``dem_seed``, and every
    # projection enforces that edge in its sweeps.  This block's only
    # job is to CARRY the solved value, keyed by the millimetre vertex
    # key, into the construct store the emitter reads.
    #
    # THE OLD CLAIM HERE WAS FALSE and is recorded so it is not
    # re-derived: it said the projection "clamped it into that box at
    # seed and after every sweep.  So the solved value already
    # satisfies the corridor."  It did clamp — into a box frozen from a
    # datum the SAME projection then moved up to 88.905 m, which is
    # what manufactured the corridor residual rather than closing it
    # (cycle-5 fix 1; the box is deleted).  A solved value satisfies
    # the corridor when the RELATIVE edge is satisfied, and the
    # certificate is what says whether it is.
    #
    # WHAT WAS DELETED, and why it had to go (INGEST lane report §3,
    # ``seamv2/RESULTS.md`` §1 part 2 — the three independent causes of
    # the v2 box being VACUOUS):
    #   * ``_zv = float(_dem_z)`` — the re-derivation.  For every
    #     edge-owning zone node this DISCARDED the solved value and
    #     recomputed ``clamp(raw DEM, ref + offsets)``.  A box around a
    #     value that IS the datum has no slack to remove, so no
    #     constraint the solve carried could ever be observable.
    #   * the FOOT re-reference — now stated IN the solve, against two
    #     solved ring variables, instead of patched up afterwards.
    #   * the SNAP-TO-BOUND quantization — a post-solve nudge of up to
    #     ``_CORRIDOR_SNAP_TOL_M`` off the solved value; that is a
    #     second valuation wearing a quantization hat, and the emitter
    #     owns quantization (``emit_snap``).
    # The INGEST lane's emit-side reader re-evaluates the SAME
    # ``zone_corridor_box`` against the solved foot and reports any gap
    # as INGESTION RESIDUAL — pre-registered zero, and the check on
    # this block at debug time.
    #
    # WHO WRITES WHAT (the B2 template) is unchanged: the solve writes
    # ONLY the zone-row nodes.  The band INNER (weld) row vertices are
    # pavement ring vertices — written by their OWN pavement shapes
    # through ``_writeback`` above (pavement identity: one node, one
    # value, never a second writer).
    if _zone_idx:
        from auto_patch.emit_decimate import _key as _mm_key
        _cps_zone = layout.canonical_points
        from ..solver_primitives import zone_node_index as _zone_idx_wb
        for _zone_entry in (getattr(layout,
                                    "adjacent_ground_presolve", None)
                            or ()):
            _zone_vals: dict = {}
            # ZONE-NODE IDENTITY: read back THIS host's own variable.
            # ``zone_values`` is per-entry, so two hosts sharing a bucket
            # now carry their own solved value to emit instead of both
            # reading the first claimant's.
            _zone_host_id = id(_zone_entry.get("shape"))
            for _zn in _zone_entry.get("zone_nodes", ()):
                _zx, _zy = _zn["xy"]
                _zi = _zone_idx_wb(layout, bucket_to_idx, (_zx, _zy),
                                   _zone_host_id)
                if _zi is None or _zi >= n:
                    continue
                _zone_vals[_mm_key(float(_zx), float(_zy))] = float(
                    _elev_emit[_zi])
            _zone_entry["zone_values"] = _zone_vals
    # ── RUNWAY-END RESA CUT writeback (arc R slice R2) ────────────
    # THE FOOT RE-REFERENCE DISCIPLINE, the B3 zone twin: identical
    # law, exact reference frame, SOLVED values only.
    #
    # A cut node carries exactly ONE constraint (the one-sided
    # envelope slab) and a DEM seed, so its converged value IS
    # ``min(dem_seed, reference + ceiling_offset(d))``.  The solve's
    # interval edge used the end's frozen-nearest pavement ANCHOR
    # VERTEX (the approximation that keeps the slab pairwise); the
    # law's actual reference is the pavement-EXIT elevation read 1 m
    # inside the exit — and THAT is the read the whole arc exists
    # for, because pre-solve it is stale by a measured median 0.110 m
    # (p90 0.150 m, max 0.164 m at CYXY; the mode is the crown, plus
    # ~0.4 m at overrun-pavement ends, plus whatever the runway grade
    # caps price as lawful slack under runway flex).  Here it
    # is re-read on the pavement shapes ``_writeback`` has just
    # written — solved AND crowned — and the one-slab projection is
    # re-evaluated against it.  ``clearance._resa_alt_at`` therefore
    # RETIRES as the source of emitted values under this gate; the
    # analytic values the emitter stamped pre-solve survive only on a
    # vertex the solve could not resolve (counted below).
    #
    # IDENTITY RULE (the zone rule): a cut vertex that ADOPTED a
    # pre-existing variable — a pavement ring vertex, a runway-end
    # SKIRT pin, a gap spine — or that interned with an earlier cut
    # vertex, takes that variable's solved value VERBATIM.  One node,
    # one value; re-evaluating the cut law there would mint a second
    # value for the same variable and re-open the twin-vertex class
    # this arc closes.
    #
    # NO SNAP-TO-BOUND (deliberate deviation from the zone twin,
    # documented for the lead): the zone corridor is two-sided and its
    # snap moves a value UP onto a floor or DOWN onto a ceiling.  The
    # cut corridor is ONE-SIDED — only a ceiling — and ``min(dem,
    # ceiling)`` already lands EXACTLY on that bound wherever it
    # binds, so the snap has nothing to gain; applying it in the
    # non-binding direction would lift the surface off the terrain by
    # up to ``_CORRIDOR_SNAP_TOL_M`` (0.15 m), i.e. FILL, which the
    # cut-only law and ``test_runway_end_resa_cut`` both forbid.  The
    # emitter's own 0.1 m quantum is kept verbatim so gate-ON and
    # gate-OFF values are directly comparable.
    if _resa_idx:
        from shapely.geometry import Point as _ResaPoint
        from shapely.ops import unary_union as _resa_union
        from auto_patch.clearance import (
            _AIRSIDE_PAVEMENT_ROLES as _RESA_AIRSIDE_ROLES,
            _nearest_pav_alt as _resa_nearest_pav_alt,
            _resa_cut_alt as _resa_cut_value)
        from auto_patch.elevation_per_surface.solver_primitives import (
            _open_ring as _resa_open_ring,
            runway_end_resa_ceiling_offset as _resa_ceiling_off,
            runway_end_resa_end_index as _resa_end_index)
        from auto_patch.layout import (
            REF_RUNWAY_END_RESA as _REF_RESA,
            ROLE_RUNWAY_CLEARANCE as _ROLE_RESA)
        _resa_specs = getattr(
            layout, "runway_end_resa_presolve", None) or []
        _resa_airside = [
            s for s in layout.shapes
            if s.role in _RESA_AIRSIDE_ROLES
            and s.polygon is not None and not s.polygon.is_empty]
        _resa_pav = None
        if _resa_airside:
            try:
                _resa_pav = _resa_union(
                    [s.polygon for s in _resa_airside])
            except _GEOM_EXC:
                _resa_pav = None
        # SOLVED exit reference per end (the law frame).  Fallback
        # chain: the containment-free 1 m-inside read on the solved
        # pavement → the anchor NODE's solved value → the pre-solve
        # analytic ref (never used at a healthy airport; counted).
        _resa_first_free = _terrain_first or 0
        _resa_refs: list = []
        for _rspec in _resa_specs:
            _rx, _ry = _rspec["read_xy"]
            _rr = (_resa_nearest_pav_alt(_resa_airside, _rx, _ry)
                   if _resa_airside else None)
            if _rr is None:
                _ra = _rspec.get("anchor_xy")
                if _ra is not None:
                    _rai = bucket_to_idx.get(
                        layout.canonical_points.get_or_add(
                            float(_ra[0]), float(_ra[1])))
                    if _rai is not None and _rai < n:
                        _rr = float(_elev_emit[_rai])
            if _rr is None:
                _rr = _rspec.get("ref_presolve")
            _resa_refs.append(None if _rr is None else float(_rr))
        _resa_claimed: set = set()
        _n_resa_solved = _n_resa_analytic = 0
        # Per-vertex forensics (O4_RESA_WB_TRACE=<path>, read-only):
        # end index, distance, ceiling offset, reference, DEM, the
        # branch taken and the value.  The arc's whole argument is
        # about WHICH reference a vertex is measured against, so the
        # classification has to be inspectable per vertex.
        _resa_trace_path = _os.environ.get("O4_RESA_WB_TRACE")
        _resa_trace: list = []
        for _rs in layout.shapes:
            if (_rs.role != _ROLE_RESA
                    or getattr(_rs, "ref", None) != _REF_RESA):
                continue
            if _rs.polygon is None or _rs.polygon.is_empty:
                continue
            _rk = _resa_end_index(_resa_specs, _rs.polygon)
            if _rk is None or _resa_refs[_rk] is None:
                continue
            _rspec = _resa_specs[_rk]
            _rref = _resa_refs[_rk]
            _rnx, _rny = _rspec["outward"]
            _rp0 = _rspec["p0"]
            try:
                _rring = _resa_open_ring(
                    list(_rs.polygon.exterior.coords))
            except _GEOM_EXC:
                continue
            _old = _rs.node_altitudes
            if (not _old or any(_a is None for _a in _old)
                    or len(_old) not in (len(_rring),
                                         len(_rring) + 1)):
                continue
            _new: list = []
            for _vi, (_vx, _vy) in enumerate(_rring):
                _ri = bucket_to_idx.get(
                    layout.canonical_points.get_or_add(float(_vx),
                                                       float(_vy)))
                _rd = ((_vx - _rp0[0]) * _rnx
                       + (_vy - _rp0[1]) * _rny)
                if _ri is None or _ri >= n:
                    _new.append(float(_old[_vi]))
                    _n_resa_analytic += 1
                    if _resa_trace_path:
                        _resa_trace.append(
                            (_rk, _vx, _vy, _rd, None, _rref, None,
                             "unresolved", float(_old[_vi]),
                             float(_old[_vi])))
                    continue
                if (_ri < _resa_first_free
                        or _ri in _resa_claimed):
                    # IDENTITY: adopted / already-claimed variable.
                    _new.append(float(_elev_emit[_ri]))
                    _n_resa_solved += 1
                    if _resa_trace_path:
                        _resa_trace.append(
                            (_rk, _vx, _vy, _rd, None, _rref,
                             (dem_elev[_ri]
                              if _ri < len(dem_elev) else None),
                             ("adopted" if _ri < _resa_first_free
                              else "claimed"),
                             float(_elev_emit[_ri]),
                             float(_old[_vi])))
                    continue
                _resa_claimed.add(_ri)
                _rv = None
                _rbranch = "law"
                if _rd <= 0.02 and _resa_pav is not None:
                    # WELD ROW, verbatim from ``_resa_alt_at``: a
                    # vertex ON the pavement exit edge carries the
                    # LOCAL pavement edge value (containment-free
                    # read 1 m inside) so the cut abuts the pavement
                    # with zero step — now read on SOLVED pavement.
                    try:
                        _on_pav = _resa_pav.distance(
                            _ResaPoint(float(_vx),
                                       float(_vy))) <= 0.05
                    except _GEOM_EXC:
                        _on_pav = False
                    if _on_pav:
                        _wp = _resa_nearest_pav_alt(
                            _resa_airside, _vx - _rnx * 1.0,
                            _vy - _rny * 1.0)
                        if _wp is not None:
                            _rv = float(_wp)
                            _rbranch = "weld"
                _rco = None
                _rdem = (dem_elev[_ri]
                         if _ri < len(dem_elev) else None)
                if _rv is None:
                    _rco = _resa_ceiling_off(_rspec, _vx, _vy)
                    if _rco is None:
                        _new.append(float(_old[_vi]))
                        _n_resa_analytic += 1
                        continue
                    _rv = round(_resa_cut_value(_rref + _rco, _rdem), 1)
                _new.append(float(_rv))
                _n_resa_solved += 1
                if _resa_trace_path:
                    _resa_trace.append(
                        (_rk, _vx, _vy, _rd, _rco, _rref, _rdem,
                         _rbranch, float(_rv), float(_old[_vi])))
            if len(_old) == len(_rring) + 1:
                _new.append(_new[0])
            _rs.node_altitudes = _new
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [runway-end-resa] writeback: "
                  f"{_n_resa_solved} vertex(es) valued from the "
                  f"SOLVED crowned exit reference, "
                  f"{_n_resa_analytic} left on the pre-solve "
                  f"analytic value")
        layout._runway_end_resa_writeback_counts = (  # type: ignore
            _n_resa_solved, _n_resa_analytic)
        if _resa_trace_path:
            import json as _resa_json
            try:
                with open(_resa_trace_path, "w") as _rfh:
                    _resa_json.dump(
                        {"specs": _resa_specs, "refs": _resa_refs,
                         "rows": _resa_trace}, _rfh, default=str)
            except OSError:
                pass
    # Spine breaklines from the SOLVED route profiles (z′ ON the spine
    # equals z — spine nodes never crown) + the crowned runway pieces.
    if _CROWN_ON:
        try:
            _n_spine_ways = emit_crown_spines(
                layout, nodes, bucket_to_idx, elev, _crown_drop_idx)
            if _n_spine_ways or _crown_drop_idx:
                import O4_UI_Utils as _UIs
                _UIs.vprint(1, f"  [pav-builder] {icao}: spine crown — "
                               f"{len(_crown_drop_idx)} node(s) crowned, "
                               f"{_n_spine_ways} spine breakline(s) "
                               f"staged.")
        except _GEOM_EXC as _spine_exc:
            import O4_UI_Utils as _UIs2
            _UIs2.vprint(1, f"  [pav-builder] WARN: {icao}: spine "
                            f"breakline emission failed "
                            f"({_spine_exc!r}).")
    # SCOPED FINAL PROJECTION snapshot (user 2026-07-05): capture the
    # post-writeback state (per-canonical-node values as the projection
    # will re-read them + per-shape ring identities) so
    # ``final_grade_projection`` can prove which shapes nothing touched
    # and skip regenerating their law pairs.  Gate off → no snapshot →
    # the projection takes its full-rebuild path (byte-identical).
    # ``_fairing_moved_keys``/``_scoped_gate`` are bound iff the
    # global-slice branch above ran — the same condition
    # ``final_grade_projection`` requires, re-checked here.
    # BREAK-REGION EXPORT — DELETED 2026-08-04 (spec ``docs/specs/
    # kill-half-spec.md`` §2).  This was THE solve-side sink: the
    # broken set's lat/lon went to ``layout._break_node_ll`` → the
    # sidecar's ``break_nodes`` → rows SPLIT OUT of the validator's
    # actionable count.  Owner law (docs/RULINGS.md): quarantine is
    # unauthorized and every count is full-census, so there is no
    # honest reader for a "reported separately" section — the rows
    # are either lawful under the law's own exemptions or they are
    # violations.  ``_solve_broken_idx`` survives as the minters'
    # REPORT (it is logged and carried for reference honesty below);
    # only the sink is gone.
    _solve_broken_idx |= {
        i for i in (getattr(layout, "_service_break_idx", None) or ())
        if i < len(nodes)}
    if _scoped_gate:
        _solve_broken_keys = {key for key, i in bucket_to_idx.items()
                              if i in _solve_broken_idx}
        _capture_projection_snapshot(layout, _fairing_moved_keys,
                                     _solve_broken_keys)
    # (The ``apron_band_broken`` reach-band carry that lived here fed
    # the final pass's reference builder ONLY; it died with the refs
    # channel.  The band the final projection's ENVELOPE needs is
    # carried below, separately and for every node.)
    # (The band the final projection's ENVELOPE reads used to be minted
    # HERE, under ``O4_ENVELOPE_FROM_BAND``.  Round 9 moved that mint up
    # to the line that BUILDS the band (§1) and dropped the gate: one
    # carry, unconditional, for every reader.  The gate never belonged on
    # the CARRIAGE — and minting here was also too late for the stage-6
    # ``_writeback`` above, which runs before this line.)
    if _os.environ.get("O4_STEP_DEBUG") == "1":
        print(f"  [unified] {icao}: {len(frozen)} spine node(s) solved, "
              f"{n_free} body node(s); feasibility-project → {rem} edge(s) "
              f"over cap ({bh} both-hard = genuine).")
        _lazy_certified = sum(1 for _sc in shape_constraints
                              if _sc.get("lazy_certified"))
        if _lazy_certified:
            _still_lazy = sum(1 for _sc in shape_constraints
                              if "lazy_expand" in _sc)
            print(f"  [flat-lazy] {icao}: {_lazy_certified} certified, "
                  f"{_lazy_certified - _still_lazy} expanded during the "
                  f"solve, {_still_lazy} never expanded")
    # FLAT-SITE FAST PATH exit evidence (spec, Tests §3b): every born-at-Z0
    # node is a protected hard pin, so its solved value must still BE Z0.
    # Reported, never asserted — a non-zero residual names the pass that
    # moved a protected node rather than hiding inside the surface.
    if _fp_skip:
        _fp_resid = _fast_path.z0_residual_report(
            getattr(layout, _fast_path.PLAN_ATTRIBUTE, None), elev)
        import O4_UI_Utils as _UI_fp2
        _UI_fp2.vprint(0,
            f"  [flat-fast-path] {icao}: {_fp_resid['n']} born-at-Z0 "
            f"node(s), worst |z − Z0| after the solve "
            f"{_fp_resid['worst_m']} m.")
    _report(icao, n_free, n_free, _time.time() - t0,
            n_terms, n_rects, n_juncs)
    return


# ── SCOPED FINAL PROJECTION (user 2026-07-05, O4_SCOPED_FINAL_PROJECTION) ────
# DEFAULT FLIPPED OFF 2026-07-18 (board T1a verdict): quiet-machine A/B at
# OTHH measured the whole apparatus (solve-side capture + scope pass +
# mid-exit recapture + deferral) NET-NEGATIVE at the target class — 363.3 s
# with scoping vs 325.2 s without, check_grade counts identical except +1
# by-design break pair at SPJC and +1 noise-aware spine kink at OTHH (CYXY
# byte-identical).  Deferral engaged (OTHH late: 124 deferred) but deferred
# shapes were cheap — the constraints stage barely moved — while capture
# rivals the seed stage per call (HECA: 14.4 s for ONE deferred shape).
# GATE DELETED 2026-08-05 (RULINGS "BUILD-COMPLETE-THEN-DEBUG").  The two
# sites disagreed — ``flat_airport_fast_path`` defaulted "1" and captured a
# snapshot on every flat-airport build that this consumer, defaulting "0",
# never read.  Resolved to ONE state, and it is the state production has
# actually run since the T1a verdict: NOT scoped.  This is a DEVIATION from
# the integration brief's "resolve to the 1 arm" — noted rather than
# decided silently (RULINGS 12320bd §2) — because the 1 arm is not a law,
# it is an optimisation the board retired ON MEASUREMENT (OTHH 363.3 s
# scoped vs 325.2 s full, identical grade counts bar 2 by-design rows), so
# adopting it would re-introduce a measured build-time regression and two
# surface rows for no law.
#
# PARKED-FEATURE: the scoping machinery (capture / defer-ids / lazy stubs /
# recapture) is RETAINED, unreferenced by production, for the post-solve-
# churn regime where deferral might pay again.  It is not a gate: nothing
# in the environment can turn it on.
SCOPED_FINAL_PROJECTION = False


def _scoped_projection_enabled() -> bool:
    return SCOPED_FINAL_PROJECTION


# ── TERRAIN-PIN QUARANTINE RETIREMENT (spec ``docs/specs/quarantine-
# retirement-round1-spec.md``, gate O4_RETIRE_TERRAIN_PIN_QUARANTINE) ────────
# Owner law (RULINGS.md): quarantine is UNAUTHORIZED; a real airport with real
# thresholds has a lawful surface, so a break region is a law defect to
# attribute, never an answer.  The terrain-pinned pair export below mints
# 94.2 % of HECA's residual break nodes (4,665 of 4,952) by quarantining BOTH
# endpoints of an over-cap law edge whenever ONE of them is terrain-pinned — a
# node-scope quarantine for a pair-scope failure, taken without consulting any
# envelope.  55 % of its nodes are dragged-in free partners and 36.7 % have no
# violation of their own.
#
# The export had TWO effects, and the gate retired BOTH (Fable ruling
# 2026-08-02, shape (a), after the pre-condition STOP found the second):
#   1. BOOKKEEPING — ``_projection_broken_idx`` → ``layout._break_node_ll`` →
#      the sidecar's ``break_nodes`` → rows hidden from the validator.
#   2. FREEZE — the same set → ``layout._final_projection_broken_keys`` →
#      the NEXT final projection's ``pre_broken`` → ``immovable`` in
#      ``feasibility_project``.  Measured at HECA: the mid run carried 375
#      nodes into the late run, 202 of them minted here, 165 of those NOT
#      hard — free nodes frozen out of every sweep.  They are ~all
#      groundside/service (4 airside), so freezing them as an input to the
#      late airside projection independently violates airside-is-king.
# BOTH SINKS ARE THEMSELVES DELETED as of 2026-08-04 (spec kill-half §2),
# so this gate now decides only whether the terrain-pinned endpoints are
# counted in the surviving REPORT set.  Released nodes fall under the
# band-governed envelope like any other free node.
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: quarantine-retirement round 1 ``ceef13f``, which measured
# both effects — the export minted 94.2 % of HECA's residual break nodes,
# 55 % of them dragged-in free partners, and froze 165 free nodes out of
# the LATE airside projection).  The owner law it enforces is not optional:
# "quarantine is UNAUTHORIZED" (docs/RULINGS.md, feasibility-is-guaranteed,
# ESCALATED 2026-08-01).  ``O4_RETIRE_TERRAIN_PIN_QUARANTINE=0`` restores
# the export into the (now report-only, §2) broken set.
def _retire_terrain_pin_quarantine_enabled() -> bool:
    return True                     # STANDING LAW (the gate is retired)
# Shapely-domain exceptions only (project rule: never catch built-ins here).
def _snapshot_geom_exceptions():
    from shapely.errors import GEOSException, TopologicalError
    return (ValueError, GEOSException, TopologicalError)


def _canonical_ring_key(coords):
    """Rotation- and reflection-invariant identity of a ring's mm-rounded
    geometry — the ``geom_guard._canonical_ring`` comparison (same 3-decimal
    rounding, same invariances) in O(n log n) instead of that helper's
    O(n²) minimal-rotation scan: a simple closed ring IS its undirected
    edge multiset over its vertex cycle, so ``(vertex_count, sorted
    undirected edges)`` changes exactly when a vertex is moved / inserted /
    dropped and never on a ring rotation or direction flip."""
    pts = [(round(x, 3), round(y, 3)) for (x, y) in coords]
    if pts and pts[0] == pts[-1]:
        pts = pts[:-1]
    count = len(pts)
    if count == 0:
        return (0, ())
    edges = tuple(sorted(
        (pts[k], pts[(k + 1) % count])
        if pts[k] <= pts[(k + 1) % count]
        else (pts[(k + 1) % count], pts[k])
        for k in range(count)))
    return (count, edges)


# Roles whose ring geometry feeds the final projection's law graph or the
# grade context's classification inputs (building keys, rect-cap inheritance,
# road-carve / route-contact zones).  ``service_road`` is NOT a pavement role
# but its geometry builds the road-carve zone, so it must be snapshotted too.
def _snapshot_roles():
    from auto_patch.elevation_per_surface.solver_primitives import (
        PAVEMENT_ROLES)
    return set(PAVEMENT_ROLES) | {"service_road"}


# Roles whose geometry feeds a BUFFERED point-membership zone in the grade
# context (``build_context``): road-carve zone (service_road/service_junction,
# buffer ROAD_FRONTAGE_TOL_M) and route-contact zone (taxi-route pavements,
# buffer _ROUTE_CONTACT_TOL_M).  A change to one of these rings can flip the
# zone membership — and therefore the law budget — of an apron/junction node
# that sits NEAR the changed geometry without sharing a vertex with it.
_ZONE_ROLES = frozenset({
    "service_road", "service_junction",
    "junction", "primary_parallel", "secondary_parallel",
    "stub", "cross_connector",
})


def _capture_projection_snapshot(layout, fairing_moved_keys=None,
                                 broken_keys=None):
    """Record the post-writeback state ``final_grade_projection`` scopes
    against (user 2026-07-05):

    * ``values`` — per-canonical-node elevation EXACTLY as the projection
      will re-read it (same ``_build_node_list`` + ``_seed_elevations`` pair,
      no dem — identical readback semantics), keyed by canonical point key.
    * ``rings`` — multiset of ``(role, canonical_ring_key)`` for every shape
      whose geometry feeds the projection graph or the law context (see
      ``_snapshot_roles``); ring identity via ``_canonical_ring_key``
      (mm-rounded, rotation/reflection-invariant — the geom_guard comparison
      in O(n log n)).
    * ``fairing_moved`` — canonical keys the solve's post-projection edge
      fairing moved (their pairs were NOT re-enforced afterwards, so the
      "unchanged ⇒ already enforced" proof excludes them).
    * ``broken`` — canonical keys of the solve's BROKEN quarantine (genuine
      anchor contradictions, blended + immovable — detected on the FULL
      graph).  The scoped projection re-quarantines the unchanged ones so
      its sparser envelope cannot un-quarantine an infeasible pocket.

    ``_seed_elevations`` republishes ``layout._seam_pin_idx``/``_seam_pin_ll``
    (and ``_eat_anchor_pin_idx``) in ITS node-index space; the solve's
    published sets are restored so downstream passes see exactly the
    state they see with the gate off."""
    from auto_patch.elevation_per_surface.solver_primitives import (
        _build_node_list, _seed_elevations)

    geom_exc = _snapshot_geom_exceptions()
    saved_pins = [(attr, getattr(layout, attr, None))
                  for attr in ("_seam_pin_idx", "_seam_pin_ll",
                               "_eat_anchor_pin_idx",
                               "_eat_anchor_pin_prev",
                               "_eat_anchor_pin_rect")]
    values: dict = {}
    try:
        nodes, bucket_to_idx = _build_node_list(layout)
        if nodes:
            elev, _is_hard, _have = _seed_elevations(layout, nodes,
                                                     bucket_to_idx)
            for key, idx in bucket_to_idx.items():
                values[key] = elev[idx]
    finally:
        for attr, saved in saved_pins:
            if saved is not None:
                setattr(layout, attr, saved)
            elif hasattr(layout, attr):
                delattr(layout, attr)

    rings: dict = {}
    roles = _snapshot_roles()
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.role not in roles:
            continue
        if s.polygon.geom_type != "Polygon":
            continue        # never matches at projection time → stays changed
        try:
            ring_key = (s.role,
                        _canonical_ring_key(s.polygon.exterior.coords))
        except geom_exc:
            continue
        rings[ring_key] = rings.get(ring_key, 0) + 1

    layout._final_projection_snapshot = {  # type: ignore[attr-defined]
        "values": values,
        "rings": rings,
        "fairing_moved": set(fairing_moved_keys or ()),
        "broken": set(broken_keys or ()),
    }


def _scoped_projection_defer_ids(layout, nodes, bucket_to_idx, elev,
                                 snapshot):
    """The apron/junction shapes ``final_grade_projection`` may DEFER (pure
    lazy stubs): proven untouched since the solve's writeback.  Returns
    ``(defer_shape_ids, pre_broken_idx)`` — the deferrable shapes (by
    ``id(shape)``) and the solve's broken-quarantine nodes still at their
    blended values (to re-quarantine in the projection).

    A shape is deferrable only when ALL of:
      1. its ring geometry is unchanged (same ``(role, canonical_ring)``
         present in the snapshot, count-aware — the geom_guard comparison);
      2. none of its node VALUES changed (the projection's own seed vs the
         snapshot values, bitwise — same readback path both times);
      3. no node was moved by the solve's edge fairing (pairs not re-enforced
         after that pass);
      4. no law-context input touching it changed:
           * a node shared with ANY geometry-changed/new shape (building-key
             gains, rect-cap inheritance, shared-vertex writes) — marked via
             the changed shapes' current rings;
           * a node at a coordinate a VANISHED ring used to hold (building-
             key/rect-cap LOSSES — old geometry known only mm-rounded, exact
             coordinate match);
           * a node inside the BUFFERED dirty region of changed zone-role
             geometry (road-carve / route-contact membership flips reach
             ``max(ROAD_FRONTAGE_TOL_M, _ROUTE_CONTACT_TOL_M)`` beyond the
             changed ring, old and new).
    Everything the solve's final joint projection enforced on identical
    rings, values and budgets is provably still satisfied — deferring it
    skips regeneration; any node the projection later moves expands the
    shape's full pair set through the lazy machinery (tolerance 0)."""
    from auto_patch.layout import ROLE_APRON, ROLE_JUNCTION

    geom_exc = _snapshot_geom_exceptions()
    cps = layout.canonical_points
    snap_values = snapshot["values"]
    snap_rings = snapshot["rings"]

    # (2) + (3): value drift and fairing-moved nodes.  ``contaminated``
    # collects every changed/contaminated node EXCEPT the broken quarantine
    # (tracked separately: broken nodes contaminate deferral but only the
    # UNcontaminated ones re-quarantine).
    contaminated: set = set()
    for key, i in bucket_to_idx.items():
        previous = snap_values.get(key)
        if previous is None or previous != elev[i]:
            contaminated.add(i)
    for key in snapshot.get("fairing_moved", ()):
        i = bucket_to_idx.get(key)
        if i is not None:
            contaminated.add(i)

    # Solve-broken quarantine: an untouched broken node keeps the solve's
    # blend and stays immovable (``pre_broken`` — the sparser scoped
    # envelope may not re-detect the contradiction; un-quarantined pockets
    # grind the worklist and smear, measured CYXY 66 k → 11.5 M visits).  A
    # touched (value-changed or geometry-contaminated) broken node re-solves
    # normally.  Either way NOTHING touching a pocket defers — the pocket's
    # pairs must be generated, tallied and blended exactly like the full
    # rebuild's.
    broken_idx: set = set()
    for key in snapshot.get("broken", ()):
        i = bucket_to_idx.get(key)
        if i is not None:
            broken_idx.add(i)

    # (1): ring-identity comparison, count-aware.
    current = []        # (shape, ring_key | None, open_coords | None)
    ring_count: dict = {}
    roles = _snapshot_roles()
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.role not in roles:
            continue
        ring_key = None
        coords = None
        if s.polygon.geom_type == "Polygon":
            try:
                coords = _open4(s.polygon)
                ring_key = (s.role,
                            _canonical_ring_key(s.polygon.exterior.coords))
            except geom_exc:
                ring_key = None
        current.append((s, ring_key, coords))
        if ring_key is not None:
            ring_count[ring_key] = ring_count.get(ring_key, 0) + 1

    geom_changed_ids: set = set()
    for (s, ring_key, _coords) in current:
        if ring_key is None \
                or snap_rings.get(ring_key, 0) < ring_count[ring_key]:
            geom_changed_ids.add(id(s))

    # Rings that VANISHED since the snapshot (mutated in place or removed).
    old_missing = [ring_key for ring_key, old_count in snap_rings.items()
                   if ring_count.get(ring_key, 0) < old_count]

    # (4a): nodes of geometry-changed shapes contaminate.
    for (s, _ring_key, coords) in current:
        if id(s) not in geom_changed_ids or not coords:
            continue
        for (x, y) in coords:
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None:
                contaminated.add(i)

    # (4b): exact-coordinate contamination from vanished rings (their
    # geometry survives only as the canonical edge multiset — mm-rounded).
    old_points: set = set()
    for (_role, (_count, canonical_edges)) in old_missing:
        for (point_a, point_b) in canonical_edges:
            old_points.add(point_a)
            old_points.add(point_b)
    if old_points:
        for i, (x, y) in enumerate(nodes):
            if (round(x, 3), round(y, 3)) in old_points:
                contaminated.add(i)

    # (4c): buffered dirty region of changed zone-role geometry (old + new):
    # every ring SEGMENT of a vanished/new zone-role ring, node membership by
    # vectorised dwithin query.
    zone_segments = []
    for (role, (_count, canonical_edges)) in old_missing:
        if role in _ZONE_ROLES:
            zone_segments.extend(canonical_edges)
    for (s, _ring_key, coords) in current:
        if (id(s) in geom_changed_ids and s.role in _ZONE_ROLES
                and coords and len(coords) >= 2):
            closed = list(coords) + [coords[0]]
            zone_segments.extend(zip(closed, closed[1:]))
    if zone_segments:
        from shapely.geometry import LineString, Point
        from shapely.strtree import STRtree
        from auto_patch.config import ROAD_FRONTAGE_TOL_M
        from auto_patch.grade_graph import _ROUTE_CONTACT_TOL_M
        zone_tol = max(ROAD_FRONTAGE_TOL_M, _ROUTE_CONTACT_TOL_M) + 0.01
        segment_tree = STRtree(
            [LineString(seg) for seg in zone_segments])
        node_points = [Point(x, y) for (x, y) in nodes]
        near_pairs = segment_tree.query(node_points, predicate="dwithin",
                                        distance=zone_tol)
        for node_index in near_pairs[0]:
            contaminated.add(int(node_index))

    pre_broken = broken_idx - contaminated
    changed_idx = contaminated | broken_idx

    if _os.environ.get("O4_STEP_DEBUG") == "1":
        _n_value = sum(1 for key, i in bucket_to_idx.items()
                       if snap_values.get(key) is None
                       or snap_values.get(key) != elev[i])
        _n_fair = sum(1 for key in snapshot.get("fairing_moved", ())
                      if key in bucket_to_idx)
        print(f"    [scoped-scope] nodes={len(nodes)} value_changed={_n_value} "
              f"fairing_moved={_n_fair} broken={len(broken_idx)} "
              f"geom_changed_shapes={len(geom_changed_ids)} "
              f"vanished_rings={len(old_missing)} "
              f"zone_segments={len(zone_segments)} "
              f"contaminated_total={len(changed_idx)}")

    # Deferrable = unchanged apron/junction with no changed node.
    defer_ids: set = set()
    for (s, _ring_key, coords) in current:
        if s.role not in (ROLE_APRON, ROLE_JUNCTION):
            continue
        if id(s) in geom_changed_ids or not coords:
            continue
        touched = False
        for (x, y) in coords:
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is None or i in changed_idx:
                touched = True
                break
        if not touched:
            defer_ids.add(id(s))
    return defer_ids, pre_broken


def triangle_plane_disposition(layout, tri_broken, n_fixed=0):
    """Where ``_project_triangle_planes``' UNRESOLVED set goes — the node
    indexes that join the break quarantine (spec kill-prep §2, gate
    ``config.TRIANGLE_PLANE_REPORTS``).

    The projection tries ONE vertex at a time and gives up when no single
    vertex has a lawful move.  That is a limitation of the SEARCH, not a
    proof that the triangle cannot be made lawful — and under the owner's
    standing rulings (feasibility is guaranteed; quarantine is
    unauthorized) a search limitation may not mint a quarantine.  With the
    gate ON the projection itself is untouched (same fixes, same moves) but
    its unresolved set becomes a REPORT: a log line plus the
    ``triangle_plane_unresolved`` sidecar count, and an EMPTY break
    contribution, so those triangles surface as visible violations for the
    solver-convergence work.  Gate OFF returns the set unchanged.
    """
    from auto_patch.config import TRIANGLE_PLANE_REPORTS
    tri_broken = set(tri_broken or ())
    if not TRIANGLE_PLANE_REPORTS:
        return tri_broken
    layout._triangle_plane_unresolved = int(
        getattr(layout, "_triangle_plane_unresolved", 0) or 0
    ) + len(tri_broken)
    if tri_broken:
        try:
            import O4_UI_Utils as _UItri
            _UItri.vprint(1,
                f"  [pav-builder] triangle-plane law: {len(tri_broken)} "
                f"vertex(es) with no lawful SINGLE-vertex move — REPORTED, "
                f"not quarantined (a search limitation is not "
                f"infeasibility); {n_fixed} triangle(s) fixed.")
        except Exception:                          # pragma: no cover
            pass
    return set()


def _project_triangle_planes(layout, bucket_to_idx, elev, immovable,
                             joint, n):
    """Clamp each 3-vertex sloped shape's PLANE gradient to its role cap.

    A triangle renders as one plane; its gradient can exceed the role cap
    while every vertex pair stays inside the pairwise rounding envelope
    (``check_grade._check_plane_gradient``).  For each triangle over cap,
    move ONE free vertex the minimal amount that brings the plane inside
    the cap, clamped into the interval that vertex's own law edges allow
    (the RAW law budgets, exactly what the projection enforces).  Returns
    ``(n_fixed, anchored_idx,
    broken_idx)`` — anchored vertices must not be re-perturbed by later
    passes; broken = no free vertex could lawfully fix the plane (the
    caller quarantines them).

    SHARED-VERTEX SURGERY (debug lane A 2026-08-05, owner directive
    "prefer a ring-private vertex as the free lever, shared only as last
    resort and reported").  A triangle's vertices are CANONICAL solver
    variables: the same node can be a vertex of several shapes' rings, so
    moving it to flatten THIS triangle's plane silently re-shapes every
    other shape that shares it — a plane fix that leaks into a neighbour's
    surface.  A vertex claimed by this ring ALONE is a free lever: moving
    it changes exactly the plane it was chosen for.  The lever is
    therefore chosen in two tiers — least-move among RING-PRIVATE
    candidates first, and only when no private vertex can lawfully fix the
    plane does a shared one move, which is COUNTED and reported
    (``layout._triangle_plane_shared_surgery``) rather than done silently.

    Ownership is read through the registry's READ-ONLY ``get`` (never
    ``get_or_add``): an instrument that interns moves the emitted surface
    (memory: two-decimators / registry-insertion round 6)."""
    import math as _math
    from auto_patch.config import ROLE_GRADE_LIMITS
    from .one_solve import _build_adjacency

    adjacency = _build_adjacency(joint, n)
    cps = layout.canonical_points
    n_fixed = 0
    anchored: set = set()
    broken: set = set()

    # ── ring ownership: node index -> how many shape rings claim it ──
    # One read-only pass over every ring in the layout.  A count of 1
    # means "this triangle is the only shape holding that variable".
    owners: dict = {}
    for _s in layout.shapes:
        _p = getattr(_s, "polygon", None)
        if _p is None or _p.is_empty or _p.geom_type != "Polygon":
            continue
        try:
            _ring = list(_p.exterior.coords)
        except Exception:                                  # pragma: no cover
            continue
        if _ring and _ring[0] == _ring[-1]:
            _ring = _ring[:-1]
        _seen: set = set()
        for (_x, _y) in _ring:
            _k = cps.get(float(_x), float(_y))
            if _k is None:
                continue
            _i = bucket_to_idx.get(_k)
            if _i is None or _i in _seen:
                continue
            _seen.add(_i)
            owners[_i] = owners.get(_i, 0) + 1
    n_shared_surgery = 0

    def _gradient(pts, zs):
        (x1, y1), (x2, y2), (x3, y3) = pts
        z1, z2, z3 = zs
        nz = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
        if abs(nz) < 1e-6:
            return None
        nx = (y2 - y1) * (z3 - z1) - (z2 - z1) * (y3 - y1)
        ny = (z2 - z1) * (x3 - x1) - (x2 - x1) * (z3 - z1)
        return (-nx / nz, -ny / nz)

    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty \
                or s.polygon.geom_type != "Polygon":
            continue
        cap = ROLE_GRADE_LIMITS.get(s.role)
        if not cap:
            continue
        try:
            ring = list(s.polygon.exterior.coords)
        except Exception:
            continue
        if ring and ring[0] == ring[-1]:
            ring = ring[:-1]
        if len(ring) != 3:
            continue
        idxs = [bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
                for (x, y) in ring]
        if any(i is None or i >= n for i in idxs):
            continue
        zs = [elev[i] for i in idxs]
        g = _gradient(ring, zs)
        if g is None:
            continue
        if _math.hypot(*g) <= cap:
            continue
        # Try each free vertex; pick the smallest lawful move, RING-
        # PRIVATE levers first (see the shared-vertex surgery note above).
        best = None                    # (private?, move_size, pos, value)
        for k in range(3):
            i_move = idxs[k]
            if i_move in immovable:
                continue
            others = [(ring[m], zs[m]) for m in range(3) if m != k]
            pts = [others[0][0], others[1][0], ring[k]]
            fixed_z = [others[0][1], others[1][1]]
            g0 = _gradient(pts, fixed_z + [0.0])
            g1 = _gradient(pts, fixed_z + [1.0])
            if g0 is None or g1 is None:
                continue
            bx, by = g1[0] - g0[0], g1[1] - g0[1]
            a = bx * bx + by * by
            if a < 1e-18:
                continue               # gradient insensitive to this vertex
            b = 2.0 * (g0[0] * bx + g0[1] * by)
            c = g0[0] * g0[0] + g0[1] * g0[1] - cap * cap
            disc = b * b - 4.0 * a * c
            if disc < 0.0:
                continue               # no value of this vertex fixes it
            sq = _math.sqrt(disc)
            t_lo, t_hi = (-b - sq) / (2.0 * a), (-b + sq) / (2.0 * a)
            # law-edge interval for the moved vertex (RAW law budgets — the
            # emit-quantization margin is retired, one_solve module head)
            lo_b, hi_b = -float("inf"), float("inf")
            for (other, budget) in adjacency.get(i_move, ()):
                if other >= n:
                    continue
                lo_b = max(lo_b, elev[other] - budget)
                hi_b = min(hi_b, elev[other] + budget)
            lo = max(t_lo, lo_b)
            hi = min(t_hi, hi_b)
            if lo > hi:
                continue               # law edges forbid the fix
            cur = zs[k]
            new_val = min(max(cur, lo), hi)
            move = abs(new_val - cur)
            # rank: ring-private beats shared, then least move.  ``0`` for
            # private sorts ahead of ``1`` for shared in the tuple compare,
            # so no shared vertex is ever chosen while a private one can
            # lawfully do the job.
            shared_rank = 0 if owners.get(i_move, 0) <= 1 else 1
            cand = (shared_rank, move, k, new_val)
            if best is None or cand[:2] < best[:2]:
                best = cand
        if best is None:
            broken.update(i for i in idxs if i is not None)
            continue
        shared_rank, _move, k, new_val = best
        if shared_rank:
            n_shared_surgery += 1
        elev[idxs[k]] = new_val
        anchored.update(i for i in idxs if i is not None)
        n_fixed += 1
    layout._triangle_plane_shared_surgery = int(n_shared_surgery)
    if n_shared_surgery:
        try:
            import O4_UI_Utils as _UI_TPS
            _UI_TPS.vprint(
                1, f"  [pav-builder] triangle-plane law: {n_shared_surgery} "
                   f"of {n_fixed} plane fix(es) had to move a SHARED vertex "
                   f"(no ring-private lever could lawfully flatten the "
                   f"plane) — that move re-shapes every shape holding the "
                   f"same canonical node.")
        except Exception:                                  # pragma: no cover
            pass
    return n_fixed, anchored, broken


def _runway_boundary_freeze_indexes(
        nodes, node_count, already_hard,
        runway_boundary_lines, freeze_tolerance_m):
    """Return the node indexes that lie inside the buffered runway-
    boundary zone and must be frozen by the late projection.

    WHY this freeze exists: a vertex lying ON a runway boundary EDGE
    INTERIOR (a junction/crossing weld between two runway ring vertices)
    is not in ``runway_idx`` (that set is ring-VERTEX keyed) yet carries
    the runway longitudinal profile — the late pass moved one +0.24 m at
    HECA 05L/23R and minted a 3.7 % profile kink.  The runway is the
    datum; nothing on its boundary moves late.

    The membership test is the exact GEOS ``contains`` predicate, run
    C-vectorized over every candidate node in one ``shapely.contains_xy``
    call rather than one prepared-``contains`` call per node (an O(n)
    Python loop with a per-point GEOS crossing was a measurable part of
    the EGLL-class late projection).  ``contains_xy`` on the same
    ``unary_union(...).buffer(tol)`` zone is the identical predicate on
    the identical geometry, so the returned index set is byte-identical.
    Only indexes ``< node_count`` are considered (the ``>= n`` guard),
    and indexes already in ``already_hard`` are skipped (adding an
    already-frozen index would be harmless, but the guard keeps the
    result set minimal exactly as the scalar loop did).
    """
    if not runway_boundary_lines:
        return set()
    import numpy as _np
    import shapely as _shapely
    from shapely.ops import unary_union as _frz_union
    _rwy_zone = _frz_union(runway_boundary_lines).buffer(freeze_tolerance_m)
    _limit = min(node_count, len(nodes))
    if _limit <= 0:
        return set()
    _coords = _np.asarray(nodes[:_limit], dtype=float)
    _inside = _shapely.contains_xy(
        _rwy_zone, _coords[:, 0], _coords[:, 1])
    # Iterate only the matches (flatnonzero), not every candidate index —
    # the zone catches a few hundred nodes of the 131k-class total.
    return {
        int(_index) for _index in _np.flatnonzero(_inside)
        if int(_index) not in already_hard}


def post_solve_mutation_set(carried, elev, n, tol):
    """Partition a projection's node space against the CARRIED solved field.

    The cycle-4 ingestion spec's requirement 2 in one function
    (``docs/specs/cycle4-projection-ingestion-spec.md``): "a node whose
    ring geometry and law context did not change after the solve exits
    this pass within materiality of its solved value.  The projection's
    job is the post-solve mutation set, not a re-solve."

    ``carried`` is ``{index: solved value}`` in the CALLER'S frame (the
    store view already lifted it by the pass's crown map), ``elev`` the
    pass's seed in the same frame.  Returns
    ``(untouched, n_new, moved)`` where

    * a node ABSENT from ``carried`` is NEW — the solve never had this
      canonical key: a planarize insert, a T-weld adoption, a merge, a
      clip rebuild.  Its law pairs are the projection's legitimate job.
    * a node whose seed differs by more than ``tol`` was MOVED by some
      other post-solve pass (band adoption, weld, groundside re-level,
      service DEM-follow), and is in play too.  ``moved`` carries
      ``(|dz|, solved, seed)`` per node so a caller can report the
      distribution rather than a count.
    * everything else is UNTOUCHED.

    No carried field (a layout that never ran the solve — probes, unit
    tests) ⇒ nothing untouched, nothing new: the partition is empty and
    the caller behaves exactly as it did before the carry existed.
    """
    untouched: set = set()
    moved: list = []
    n_new = 0
    if not carried:
        return untouched, n_new, moved
    for i in range(n):
        sv = carried.get(i)
        if sv is None:
            n_new += 1
            continue
        dv = abs(elev[i] - sv)
        if dv > tol:
            moved.append((dv, sv, elev[i]))
        else:
            untouched.add(i)
    return untouched, n_new, moved


def projection_law_certificate(joint, elev, n, hard, tol=1e-3,
                               family_of=None):
    """Over-cap law edges of ``joint`` at the current ``elev``, BY FAMILY.

    The ingestion round's own reader (spec
    ``docs/specs/cycle4-projection-ingestion-spec.md`` requirement 4:
    "enumerate and close every divergence between the two constraint
    builds").  Run at the projection's ENTRY it says which law the
    rebuilt constraint set finds violated in the SOLVED field — a family
    that is over cap at entry is either a genuine post-solve mutation or
    a law input the two builds disagree on.  Run at EXIT it says what the
    projection could not close.

    A family is ``role:ref`` for a shape entry, or the entry's explicit
    ``family`` tag (the unified-graph and rod edge sets).  Interval edges
    (4-tuples) are counted against their own interval, not a cap.

    ``family_of`` — cycle-5 fix 4, THE FAMILY AXIS.  A ``{(min(a,b),
    max(a,b)): family}`` map (``grade_graph.UnifiedGraph.family_by_pair``)
    consulted PER EDGE for entries whose own tag is a construction site
    rather than a law.  Without it the unified-graph entry is one
    catch-all that took 80.6 % of the mass (63,635 of 78,912 at HECA
    final#1) and named nothing; with it every edge is attributed to the
    CONSTRUCTOR that minted it.  A pair the map does not carry keeps the
    entry's own tag, so an unmapped caller reads exactly as before.

    Pure measurement: reads ``elev``, writes nothing — the map is a
    LOOKUP, so the constraint set and its edge order are untouched.
    Returns ``{family: (n_over, worst_excess_m, n_both_hard)}``.
    """
    out: dict = {}
    for entry in joint:
        fam_entry = entry.get("family")
        if fam_entry is None:
            fam_entry = f"{entry.get('role') or '?'}:{entry.get('ref') or '-'}"
        # Per-edge resolution only where the entry tag is the catch-all;
        # a real shape entry (``apron:-``, ``graded_strip:adjacent_ground``)
        # already names its law and is never re-keyed.
        per_edge = family_of if fam_entry in _CATCH_ALL_FAMILIES else None
        row = None if per_edge else out.setdefault(fam_entry, [0, 0.0, 0])
        for e in entry.get("edges") or ():
            a, b = e[0], e[1]
            if a >= n or b >= n:
                continue
            d = elev[a] - elev[b]
            if len(e) >= 4:
                lo, hi = e[2], e[3]
                excess = 0.0
                if lo is not None and d < lo:
                    excess = lo - d
                elif hi is not None and d > hi:
                    excess = d - hi
            else:
                excess = abs(d) - float(e[2])
            if excess <= tol:
                continue
            if per_edge is not None:
                key = (a, b) if a <= b else (b, a)
                row = out.setdefault(per_edge.get(key, fam_entry),
                                     [0, 0.0, 0])
            row[0] += 1
            if excess > row[1]:
                row[1] = excess
            if a in hard and b in hard:
                row[2] += 1
        # ── THE WEIGHTED TRANSECT ROWS (spec §7) ─────────────────────
        # A hyper row is not an edge and this loop's ``e[0]``/``e[1]``
        # would read its weight vector as a node index, so it is counted
        # here, under its own family: an over-cap transect at exit MUST
        # appear in ``over_cap=N`` or the certificate reports a smaller
        # law than the projection was given.  BOTH-HARD means every one
        # of its four nodes is immovable — the transect analogue of an
        # infeasible edge, and the only shape "genuinely infeasible" can
        # take when four nodes share one inequality.
        for row_h in (entry.get("hyper") or ()):
            idx4, w4, b_h = row_h[0], row_h[1], row_h[2]
            if any(int(k) >= n for k in idx4):
                continue
            val = sum(float(w) * elev[int(k)] for w, k in zip(w4, idx4))
            excess = val - float(b_h)
            if excess <= tol:
                continue
            fam_h = "transverse"
            row = out.setdefault(fam_h, [0, 0.0, 0])
            row[0] += 1
            if excess > row[1]:
                row[1] = excess
            if all(int(k) in hard for k in idx4):
                row[2] += 1
    return {k: tuple(v) for k, v in out.items()}


# Entry tags that name a CONSTRUCTION SITE, not a law — the certificate
# resolves these per edge through ``family_of`` when it is given one.
# ``"?:-"`` is what an untagged entry (the SOLVE's own joint, which never
# tagged its unified entry at all) degrades to.
# ONE AUTHORITY (cycle-7 fix 5): the projection's own family axis applies
# the identical rule inside ``feasibility_project``, so the set and the
# tag rule live in ``one_solve`` (which ``solve`` imports, never the
# reverse) and the module-head import aliases it here — not a second copy.


def _apron_staged_certificate(icao, report, n, family_of, pin_sources):
    """Report the apron staged solve's A1/A2 certificate split and print
    A1's both-hard top-20 with their PIN SOURCES (spec section 4).

    A both-hard edge is one neither endpoint of which may move.  In the A1
    (senior) pass that means the movement-surface law is contradicted by the
    PINS themselves — the anchor-placement docket's own population — so each
    row is named with where its pins come from.
    """
    import O4_UI_Utils as _UI_c
    if not report:
        return
    try:
        _pin_src = _pin_source_map(pin_sources, n)
        # THE ROWS ARE A1'S OWN, recorded inside the senior pass where its
        # entry set and its frozen set both exist.  Re-deriving them here
        # from the JOINT list would report groundside families the senior
        # pass never enforced (measured: the first CYXY docket was entirely
        # unified:service_road / service_junction, which are stage B).
        rows = [(float(x), int(u), int(v), str(family_of.get((min(u, v),
                                                              max(u, v)), "?")))
                for (x, u, v) in (report.get("a1_both_hard_raw") or ())]
        rows.sort(reverse=True)
        rows2 = [(float(x), int(u), int(v), str(family_of.get((min(u, v),
                                                               max(u, v)), "?")))
                 for (x, u, v) in (report.get("a2_both_hard_raw") or ())]
        rows2.sort(reverse=True)
        _UI_c.vprint(
            1, f"  [apron-staged] {icao} CERTIFICATE: "
               f"A1 over_cap={report.get('a1_over_cap')} "
               f"(both-hard {report.get('a1_both_hard')}) | "
               f"A2 over_cap={report.get('a2_over_cap', 0)} "
               f"(both-hard {report.get('a2_both_hard', 0)}); "
               f"interior movers={report.get('interior_movers', 0)}; "
               f"senior moved in A2={report.get('senior_moved', 0)}")
        if not rows:
            return
        _UI_c.vprint(
            1, f"  [apron-staged] {icao} A1 BOTH-HARD top "
               f"{min(20, len(rows))} of {len(rows)} — THE PIN DOCKET "
               f"(both endpoints immovable: the pins contradict the "
               f"movement-surface law, spec section 4):")
        for exc, a, b, fam in rows[:20]:
            _UI_c.vprint(
                1, f"      excess {exc:7.3f} m  {fam:28s} "
                   f"nodes {a}/{b}  pins {_pin_src.get(a, '?')}/"
                   f"{_pin_src.get(b, '?')}")
        if rows2:
            _UI_c.vprint(
                1, f"  [apron-staged] {icao} A2 BOTH-HARD top "
                   f"{min(20, len(rows2))} of {len(rows2)} — THE FREEZE "
                   f"DOCKET (an interior pair neither endpoint of which A2 "
                   f"may move: a statement about the freeze, not the law):")
            for exc, a, b, fam in rows2[:20]:
                _UI_c.vprint(
                    1, f"      excess {exc:7.3f} m  {fam:28s} "
                       f"nodes {a}/{b}  pins {_pin_src.get(a, '?')}/"
                       f"{_pin_src.get(b, '?')}")
            report["a2_both_hard_rows"] = [
                {"excess_m": round(float(x), 4), "a": int(u), "b": int(v),
                 "family": str(f), "pin_a": _pin_src.get(u, "?"),
                 "pin_b": _pin_src.get(v, "?")}
                for (x, u, v, f) in rows2[:20]]
        report["a1_both_hard_rows"] = [
            {"excess_m": round(float(x), 4), "a": int(u), "b": int(v),
             "family": str(f), "pin_a": _pin_src.get(u, "?"),
             "pin_b": _pin_src.get(v, "?")}
            for (x, u, v, f) in rows[:20]]
    except Exception as _e:                              # pragma: no cover
        _UI_c.vprint(1, f"  [apron-staged] certificate report failed: {_e}")


def _pin_source_map(sources, n):
    """``{node: pin-source label}`` for the A1 pin docket (spec section 4).

    ``sources`` is an ORDERED list of ``(label, node-set)`` handed in by the
    caller from the very sets that made those nodes hard — the runway datum,
    the tile-seam terrain freeze, the strip freeze, the seed pins.  First
    label wins, so the most specific source named by the caller is the one
    reported.  Nothing is re-derived here: a pin source guessed from geometry
    would be a second authority on what the projection froze."""
    out = {}
    for label, nodes in (sources or ()):
        for i in (nodes or ()):
            try:
                k = int(i)
            except (TypeError, ValueError):
                continue
            if 0 <= k < n:
                out.setdefault(k, label)
    return out


def _report_law_certificate(icao, label, cert, top=8, n_nodes=None,
                            crown_space="uncrowned z'"):
    """Print a :func:`projection_law_certificate` result, worst first.

    FRAME STAMPS (RULINGS 2026-08-06 "Instrument truth is law", binding
    point 3).  ``n_nodes`` is the NODE SPACE the reading was taken in and
    ``crown_space`` the vertical frame.  They are not decoration: three
    readers print a line of this shape — the SOLVE EXIT certificate, the
    final pass's ENTRY and its EXIT — and they run in DIFFERENT node
    spaces (measured at HECA: 146,743 for the solve against 142,635 /
    144,056 for the final passes, which rebuild their own graph).  Two
    labels that read as ENTRY/EXIT of one thing were therefore silently
    two populations, and the numbers are NOT comparable across differing
    ``n``.  Stamping the space is what makes that visible at the line
    instead of in a comment 2,000 lines away.

    ``crown_space`` matters for the same reason: every current caller
    reads in UNCROWNED z′ (the law's own frame — the solve takes its
    certificate one statement before the crown drop, and the final
    passes lift into z′ = z + c on entry and drop back on exit).  A
    reader comparing a certificate number to an emitted .osm value is
    off by ``_crown_of`` at every crowned node, with nothing on the line
    to warn them.

    VERDICT WORD, REMOVED (binding point 2).  This line used to print
    ``CERTIFIED`` / ``UNCERTIFIED``, a world-DEPENDENT interpretation
    (``total`` is a function of ``elev``, hence of the DEM) emitted by a
    report function whose own call-site comment says "Pure measurement,
    no gate".  It read as a gate result and gated nothing.  It is
    replaced by the measurement it restated, ``over_cap=N`` — equally
    greppable, so the fail-loud property RULINGS 2026-08-05 asks for is
    kept, without asserting a verdict the law layer never made."""
    rows = sorted(cert.items(), key=lambda kv: -kv[1][0])
    total = sum(v[0] for v in cert.values())
    both = sum(v[2] for v in cert.values())
    # VIOLATING families, not families PRESENT (cycle-5 fix 4): the old
    # ``len(rows)`` counted every family the constraint set CONTAINS —
    # "across 425 family(ies)" when only 7 of the 425 had a nonzero
    # count, which read as breadth of failure and was breadth of law.
    n_viol = sum(1 for v in cert.values() if v[0])
    try:
        import O4_UI_Utils as _UI_cert
        say = lambda m: _UI_cert.vprint(1, m)          # noqa: E731
    except Exception:                                  # pragma: no cover
        say = print
    _space = "?" if n_nodes is None else str(int(n_nodes))
    say(f"  [proj-law-certificate] {icao} {label}: over_cap={total} law "
        f"edge(s) ({both} both-hard) in {n_viol} violating "
        f"family(ies) of {len(rows)} present "
        f"[node space n={_space}; crown space {crown_space}]")
    for fam, (n_over, worst, n_bh) in rows[:top]:
        if not n_over:
            continue
        say(f"      {n_over:8d}  worst {worst:8.3f} m  both-hard {n_bh:6d}"
            f"  {fam}")


def compose_rod_chains(chains, resolve, want_drop_records=False):
    """Carry the §10 interval rod into a REBUILT node space, COMPOSING the
    links across runs of vertices that space no longer contains.

    Owner-approved semantics (2026-07-29, docs/specs/rod-compose-and-band-
    single-source-spec.md §A).  ``emit_decimate.decimate_emit_nodes``
    deletes 3D-collinear strung ring vertices between the solve and
    ``final_grade_projection``'s node rebuild — the AUDITED cause of 100 %
    of the rod's carry loss (HECA 4,068 of 7,034 links).  A chain
    ``S1 · v · v · S2`` therefore arrives with two surviving endpoints and
    interior keys that resolve to nothing.

    The removed run is not information loss.  Each link constrains
    ``z[a] − z[b] ∈ [loᵢ, hiᵢ]``, and those telescope along the chain, so
    the ONE link ``(S1, S2)`` with the summed interval
    ``[Σloᵢ, Σhiᵢ] = [ΣΔᵢ − Σεᵢ, ΣΔᵢ + Σεᵢ]`` is the EXACT rod constraint
    between the survivors — and it is the constraint on the ring edge the
    decimator actually leaves behind (its kept-pair grade is the
    length-weighted mean of the removed sub-segments).  No re-stringing,
    no transport, no new node space: the solve stays the rod store's only
    writer.

    ``chains``   ``[[(ka, kb, lo, hi), ...], ...]`` — contiguous key chains
                 (``layout._taut_rod_key_chains``);
    ``resolve``  ``key -> node_index | None`` in the REBUILT space.

    Returns ``(edges, dropped, drop_records, composed, absorbed,
    span_max)``: ``edges`` are ``(ia, ib, lo, hi)`` for the projection;
    ``composed`` counts emitted links spanning MORE than one minted link,
    ``absorbed`` the minted links they represent, ``span_max`` the longest
    such run.  Links before a chain's first surviving key or after its
    last, and runs whose two survivors intern to ONE rebuilt node, are
    dropped and counted — never enforced one-sided.  A chain whose
    vertices all survive composes 1:1, i.e. byte-identically to the legacy
    per-pair carry."""
    edges: list = []
    drop_records: list = []
    dropped = composed = absorbed = span_max = 0
    for chain in chains:
        if not chain:
            continue
        keys = [chain[0][0]] + [e[1] for e in chain]
        prev_pos = None
        prev_idx = None
        first_pos = last_pos = 0
        for pos, k in enumerate(keys):
            i = resolve(k)
            if i is None:
                continue
            if prev_pos is None:
                first_pos = last_pos = prev_pos = pos
                prev_idx = i
                continue
            m = pos - prev_pos
            lo = hi = 0.0
            for t in range(prev_pos, pos):
                lo += chain[t][2]
                hi += chain[t][3]
            if i != prev_idx:
                edges.append((prev_idx, i, lo, hi))
                if m > 1:
                    composed += 1
                    absorbed += m
                    if m > span_max:
                        span_max = m
            else:
                # both survivors intern to ONE rebuilt node: the run has
                # no length in this space, so there is nothing to hold.
                dropped += m
                if want_drop_records:
                    for t in range(prev_pos, pos):
                        drop_records.append(
                            (chain[t][0], chain[t][1], False, False,
                             "run_collapsed_to_one_node"))
            prev_pos, prev_idx, last_pos = pos, i, pos
        if prev_pos is None:                # no key in the chain survived
            dead = range(len(chain))
        else:
            dead = list(range(first_pos)) + list(range(last_pos, len(chain)))
        for t in dead:
            dropped += 1
            if want_drop_records:
                ka, kb = chain[t][0], chain[t][1]
                drop_records.append(
                    (ka, kb, resolve(ka) is None, resolve(kb) is None,
                     "chain_end_unresolved"))
    return (edges, dropped, drop_records, composed, absorbed, span_max)


def final_grade_projection(layout, icao: str = "", dem=None,
                           tile_lat: int = 0, tile_lon: int = 0, *,
                           recapture_snapshot: bool = True) -> None:
    """LAST-WORD grade projection on the FINAL emitted geometry (round 4,
    user 2026-07-03).

    ``recapture_snapshot=False`` skips the exit-time scoped-projection
    snapshot recapture — pass it at a call no later projection will ever
    scope against (the snapshot's only reader), where recapturing is pure
    cost (measured OTHH: the recapture rivals the ``seed`` stage,
    ~4-5 s at 131k nodes).

    Post-solve passes (planarize inserts, final T-vertex weld adoptions,
    merges, clip rebuilds) reshape rings AFTER the elevation solve, so the
    law pairs of the FINAL rings are a superset of what the solve projected
    — measured at SPJC: 13 whole long chords + 51 inserted endpoints, most
    of the residual law-true violations.  Rebuild the law graph on the
    final shapes and run one scalar GS projection: runway/CIFP corners,
    tile-seam nodes and nodes welded to already-emitted FEATURE shapes
    (boundary ribbon / bridges / clearance adopted pavement values earlier)
    are HARD; building pads move as rigid flat groups; everything else
    flexes minimally from its solved value (warm seed → only violated
    neighbourhoods move).  Gate ``O4_FINAL_GRADE_PROJECTION=0`` disables.
    """
    # DEFAULT ON (2026-07-04): the 2026-07-03 "no change at SPJC"
    # measurement predated the EXACT-AXES sidecar — the residuals then
    # were reader-divergent pairs no projection could fix.  With unified
    # readers this pass closes exactly the post-solve mutation classes
    # (planarize/T-weld inserts, clip rebuilds, service DEM-follow noise):
    # CYXY within-shape 299 → 97, worst 8.35 % → 6.07 % (one rounding
    # pair).  Costs ~12-15 s.  STANDING LAW — there is no arm that skips
    # the final grade projection.
    from auto_patch.elevation_per_surface.solver_primitives import (
        PAVEMENT_ROLES, _build_node_list, _build_shape_constraints,
        _runway_node_set, _seed_elevations, _writeback,
        gap_spine_stage_b_nodes)
    from auto_patch import grade_graph as _GG
    from auto_patch.config import (
        POST_SOLVE_IDEMPOTENCE_TOL_M as _IDEMPOTENCE_TOL_M)
    from auto_patch.layout import ROLE_BUILDING
    from .one_solve import feasibility_project_partitioned

    t0 = _time.time()
    # THE PROJECTION COUNT (S1e acceptance, RULINGS 2026-08-14 "THE DOUBLE
    # PROJECTION RETIRES").  ONE ``final_grade_projection`` call per build
    # is the ruling's own first acceptance item, so the build LOGS its
    # ordinal — counted on the layout, so concurrent builds in one process
    # never share a counter.  Log-only: it moves no value and no byte.
    _fgp_n = int(getattr(layout, "_final_projection_calls", 0)) + 1
    layout._final_projection_calls = _fgp_n
    import O4_UI_Utils as _UI_fgpn
    _UI_fgpn.vprint(1, f"  [final-projection] {icao}: CALL #{_fgp_n} "
                       f"(acceptance: exactly 1 per build).")
    _stage_t = {}
    _stage_prev = [t0]

    def _stage(name):
        now = _time.time()
        _stage_t[name] = _stage_t.get(name, 0.0) + (now - _stage_prev[0])
        _stage_prev[0] = now

    nodes, b2i = _build_node_list(layout)
    if not nodes:
        return
    # Arc R slice R1: this pass shares ``_build_node_list``, so an
    # admitted RESA-cut ring resolves to nodes HERE too — with no
    # constraint in this graph and no writeback (``_writeback`` skips
    # non-pavement roles).  Collect its FREE nodes once, for the fairing
    # exemption below (the cut carries no fairing law, and a cut-ring
    # triple would drag the pavement vertices its weld row shares).
    # Empty off-gate ⇒ byte-inert.
    from auto_patch.elevation_per_surface.solver_primitives import (
        admitted_terrain_refs as _admitted_refs_fp)
    from auto_patch.layout import (
        REF_RUNWAY_END_RESA as _REF_RESA_FP,
        ROLE_RUNWAY_CLEARANCE as _ROLE_RESA_FP)
    _fp_resa_free_idx: set = set()
    if (_ROLE_RESA_FP, _REF_RESA_FP) in _admitted_refs_fp():
        _fp_first_free = getattr(
            layout, "_terrain_host_yield_first_index", 0) or 0
        _fp_cps = layout.canonical_points
        for _fs in layout.shapes:
            if (_fs.role != _ROLE_RESA_FP
                    or getattr(_fs, "ref", None) != _REF_RESA_FP
                    or _fs.polygon is None or _fs.polygon.is_empty
                    or _fs.polygon.geom_type != "Polygon"):
                continue
            for (_fx, _fy) in _fs.polygon.exterior.coords:
                _fi = b2i.get(_fp_cps.get_or_add(float(_fx), float(_fy)))
                if _fi is not None and _fi >= _fp_first_free:
                    _fp_resa_free_idx.add(_fi)
    elev, base_hard, _have = _seed_elevations(layout, nodes, b2i)
    n = len(elev)
    _stage("seed")

    ctx = _GG.build_context(layout, b2i)
    _stage("ctx")
    runway_idx = _runway_node_set(layout, b2i)
    # SCOPED PROJECTION (user 2026-07-05, gate ``O4_SCOPED_FINAL_PROJECTION``
    # default ON; off = full rebuild): a shape needs re-projection only if
    # its ring geometry changed after the solve, any of its node values
    # changed after the solve's writeback, or a law-context input touching it
    # changed (see ``_scoped_projection_defer_ids``).  Everything else was
    # already projected during the solve on identical rings/values — provably
    # nothing to do; deferred shapes become zero-cost lazy stubs that expand
    # the moment the projection moves one of their nodes.
    snapshot = getattr(layout, "_final_projection_snapshot", None)
    scoped = (snapshot is not None and _scoped_projection_enabled())
    defer_ids: set = set()
    pre_broken: set = set()
    if scoped:
        try:
            defer_ids, pre_broken = _scoped_projection_defer_ids(
                layout, nodes, b2i, elev, snapshot)
        except _snapshot_geom_exceptions():
            defer_ids = set()
            pre_broken = set()
            scoped = False        # geometry hiccup → sound full rebuild
    _stage("scope")
    # ── SPINE CROWN v2 transform (part 30): this projection enforces the
    # law, and the law lives in UNCROWNED space z′ = z + c (the emitted
    # crown is a designed sub-cap offset — see the solve's writeback).
    # Post-solve ring inserts (planarize / T-welds) carry VALUES linearly
    # interpolated along their ring edge, so they join the field at the
    # SAME interpolation of the flanking solve-time drops first
    # (crown.extend_field_to_new_ring_nodes) — value and field stay
    # consistent, and the sidecar export the validator reads is complete.
    # Then: add c, project, subtract before writeback.
    _crown_by_key = getattr(layout, "_crown_drop_key", None) or {}
    _crown_of: dict = {}
    if _crown_by_key:
        try:
            from auto_patch.crown import extend_field_to_new_ring_nodes
            extend_field_to_new_ring_nodes(layout, b2i)
        except _snapshot_geom_exceptions():
            pass
        _crown_by_key = getattr(layout, "_crown_drop_key", None) or {}
        for _key, _i in b2i.items():
            _v = _crown_by_key.get(_key)
            if _v:
                _crown_of[_i] = _v
                elev[_i] = elev[_i] + _v
    # THE POST-SOLVE MUTATION SET (see :func:`post_solve_mutation_set`),
    # read in ONE frame: the seed was crowned in just above and the
    # carried field is lifted by the same map.
    _carried_solved = _store_of(layout).view_scalar(
        "solved_values", b2i, n, crown_of=_crown_of)
    _untouched_hold, _mut_new, _mut_deltas = post_solve_mutation_set(
        _carried_solved, elev, n, tol=_IDEMPOTENCE_TOL_M)
    _mut_moved = len(_mut_deltas)
    # ── PROBE A, FINAL-PROJECTION TAIL: THIS PASS'S ENTRY BOUNDARY ──────
    # (spec amendment 2026-08-01.)  Placed AFTER the crown transform in,
    # so the whole tail is read in ONE frame — the uncrowned z′ the law
    # lives in and the ledger has used since the solve.  A move seen here
    # happened BETWEEN the previous boundary and this pass starting (the
    # solve's writeback, band/gap emission, tile cuts, conformance welds,
    # densify) — it is NOT the pass's doing, hence the ``.entry`` label.
    # Gate off ⇒ no ledger on the layout ⇒ one ``getattr``.
    _ml = getattr(layout, "_string_mover_ledger", None)
    _ml_idx: dict = {}
    _ml_pass = 0
    if _ml is not None:
        _ml_pass = int(_ml.get("n_final_passes", 0)) + 1
        _ml["n_final_passes"] = _ml_pass
        _ml_idx = _mover_rebind(_ml, b2i, n)
        _mover_stamp_rebound(_ml, elev, _ml_idx,
                             f"final_proj_{_ml_pass}.entry")
    if scoped:
        shape_constraints = _build_shape_constraints(
            layout, b2i, ctx=ctx, defer_shape_ids=defer_ids)
        for _entry in shape_constraints:
            if _entry.get("lazy_scoped"):
                _entry["lazy_seed"] = [elev[i] for i in _entry["lazy_nodes"]]
        _stage("constraints")
        G = _GG.build_unified_graph(layout, b2i, ctx=ctx,
                                    skip_edge_shape_ids=defer_ids,
                                    include_spine=False)
    else:
        # FLATNESS-CERTIFIED LAZY TIER (user 2026-07-05): here ``elev`` is the
        # SOLVED surface (warm seed), so a certified shape stays lazy only when
        # the whole pipeline left every one of its nodes exactly at the DEM seed
        # (bitwise — the entry check compares against the same sampler's values);
        # anything the solve touched expands at projection entry.  ``dem`` comes
        # from the pipeline caller (same tile frame as the elevation solve).
        _hard_for_certificate = ({i for i in range(n) if base_hard[i]}
                                 | {i for i in runway_idx if i < n})
        shape_constraints = _build_shape_constraints(
            layout, b2i, ctx=ctx, dem=dem, tile_lat=tile_lat,
            tile_lon=tile_lon, hard_nodes=_hard_for_certificate)
        _stage("constraints")
        G = _GG.build_unified_graph(layout, b2i, ctx=ctx)
    # APRON TERRACE LAW (2026-08-04): re-bind the SOLVE's plan onto this
    # pass's freshly-built constraints.  The node list was rebuilt, so the
    # plan is carried by SHAPE IDENTITY and GEOMETRY (never by index — the
    # rod-key lesson); the joints themselves are unchanged, which is what
    # makes the two passes one law rather than two.  No plan (gate off) ⇒
    # a single dict lookup and byte-identical constraints.
    # SILENT NARROWING IS THE HAZARD (ingestion spec requirement 3).  The
    # relief these two plans grant is LAW; a bare ``except: pass`` around
    # them turns a plan failure into "the zone quietly grades at the strict
    # cap", which reads as a clean result and is the exact shape of the
    # fan-acceptance failure.  Every application is COUNTED and the counts
    # are reported; a failure names itself.
    _fp_law_counts: dict = {}
    _terrace_plan_fp = getattr(layout, "_apron_terrace_plan", None)
    if _terrace_plan_fp is not None:
        from .apron_terrace import (apply_terrace_budgets as _apply_terr_fp,
                                    rebind_terrace_stations)
        try:
            # THE STATIONS ARE INDICES — re-resolve them against THIS
            # pass's node list before any of them is used as an edge
            # endpoint.  Carrying them across the rebuild is the exact
            # shape of the rod-key bug.
            rebind_terrace_stations(_terrace_plan_fp, layout,
                                    shape_constraints, nodes, b2i)
            _fp_law_counts["terrace_sc"] = _apply_terr_fp(
                _terrace_plan_fp, shape_constraints, nodes)
        except Exception as _terr_fp_exc:
            _fp_law_counts["terrace_sc"] = f"FAILED {_terr_fp_exc!r}"
            _terrace_plan_fp = None
    _fan_plan_fp = getattr(layout, "_fan_ramp_plan", None)
    if _fan_plan_fp is not None:
        from .apron_terrace import apply_fan_ramp_caps as _apply_fan_fp
        try:
            _fp_law_counts["fan_sc"] = _apply_fan_fp(
                _fan_plan_fp, shape_constraints, nodes)
        except Exception as _fan_fp_exc:
            _fp_law_counts["fan_sc"] = f"FAILED {_fan_fp_exc!r}"
    u_edges = [(a, b, cap.at(_GG._dist(G.pos.get(a), G.pos.get(b)), 0.0))
               for (a, b, cap, _sp) in G.edges
               if a in G.pos and b in G.pos]
    # THE STAGE MAP, in THIS pass's node space (staged-solve S1b): the
    # graph's own mint-time stages plus each appending constructor's.
    _fp_pair_stage: dict = dict(G.stage_by_pair())
    # ── NEAR-MISS BUILDING-FRONTAGE LAW EDGES, INGESTED (spec
    # requirement 1) ───────────────────────────────────────────────────
    # The solve extends ``u_edges`` with the pad ↔ apron near-miss law
    # (``|z(apron endpoint) − z(pad node)| ≤ APRON_MAX_GRADE·d`` across a
    # sub-metre unpaved sliver) and its own comment claims the pairs are
    # "enforced by every projection INCLUDING the movable-pad final yield
    # GS".  They were not: THIS pass rebuilt ``u_edges`` from the unified
    # graph alone and never added them — the one pass that frees pads to
    # move, running without the law that holds them to their frontage.
    # The builder needs ``building_seats``, a SOLVE-phase artifact, which
    # is why re-derivation here was impossible and the family went
    # missing.  It is now carried by canonical identity and handed to the
    # SAME constructor the solve used — shared code path, not a parallel
    # implementation.
    _carried_seats = _store_of(layout).view_scalar("building_seats", b2i, n)
    if _carried_seats:
        from .anchors import (
            near_miss_building_frontage_edges as _near_miss_fp)
        try:
            _nm_edges = list(_near_miss_fp(layout, b2i, _carried_seats,
                                           stage_out=_fp_pair_stage))
            u_edges.extend(_nm_edges)
            _fp_law_counts["frontage_near_miss"] = len(_nm_edges)
        except Exception as _nm_exc:
            _fp_law_counts["frontage_near_miss"] = f"FAILED {_nm_exc!r}"
    # ── CROSS-SECTION LAW EDGES, INGESTED HERE TOO (ruling 1) ──────────
    # The same lesson the near-miss block above records: THIS pass
    # rebuilds ``u_edges`` from the unified graph alone, so a law family
    # the solve added and this pass does not is a family that stops
    # binding in the one pass that frees the most nodes.  The record is
    # a LAYOUT artifact (positions, minted pre-solve), so unlike
    # ``building_seats`` it needs no carry — it re-resolves through THIS
    # pass's own ``b2i``, which is the point of recording positions.
    try:
        from auto_patch.lateral_spine_nodes import (
            lateral_xsection_law_edges as _xsec_edges_fp)
        _xsec_fp = list(_xsec_edges_fp(layout, b2i,
                                       stage_out=_fp_pair_stage))
        u_edges.extend(_xsec_fp)
        _fp_law_counts["lateral_xsection"] = len(_xsec_fp)
    except Exception as _xsec_exc:
        _fp_law_counts["lateral_xsection"] = f"FAILED {_xsec_exc!r}"
    # ── THE WEIGHTED TRANSECT ROWS (owner ruling 2026-08-21; spec
    # transverse-hyperplane-solve-spec.md §§2-5 + AMENDMENT A1 §8a) ────
    # The pair form above can only bind a cross-section where a foot was
    # planted at BOTH ends; 66 of 75 CYXY airside transverse rows have no
    # ring vertex near either end.  A transect is a WEIGHTED FOUR-NODE
    # inequality over the ring edges its ends interpolate along, so it is
    # bound as one — here, on the ring THIS projection sees, because no
    # projection runs after to_osm begins (A1, measured).
    _hyper_fp: list = []
    _bound_spans_fp: list = []
    try:
        from auto_patch.lateral_spine_nodes import (
            transect_hyper_rows as _transect_rows_fp)
        _hyper_fp = list(_transect_rows_fp(
            layout, b2i, elev, spans_out=_bound_spans_fp))
        _fp_law_counts["transverse_hyper"] = len(_hyper_fp)
    except Exception as _hyp_exc:
        _fp_law_counts["transverse_hyper"] = f"FAILED {_hyp_exc!r}"
    if _terrace_plan_fp is not None:
        from .apron_terrace import (
            apply_terrace_budgets_to_edges as _apply_terr_u_fp)
        try:
            u_edges, _n_terr_u = _apply_terr_u_fp(
                _terrace_plan_fp, u_edges, nodes)
            _fp_law_counts["terrace_u"] = _n_terr_u
        except Exception as _terr_u_exc:
            _fp_law_counts["terrace_u"] = f"FAILED {_terr_u_exc!r}"
    if _fan_plan_fp is not None:
        from .apron_terrace import (
            apply_fan_ramp_caps_to_edges as _apply_fan_u_fp)
        try:
            u_edges, _n_fan_u = _apply_fan_u_fp(_fan_plan_fp, u_edges, nodes)
            _fp_law_counts["fan_u"] = _n_fan_u
        except Exception as _fan_u_exc:
            _fp_law_counts["fan_u"] = f"FAILED {_fan_u_exc!r}"
    joint = list(shape_constraints) + _unified_entries(
        u_edges, _fp_pair_stage, "final_projection/unified",
        family="unified_graph")
    if _hyper_fp:
        # THE TRANSECT ROWS RIDE THEIR OWN ENTRY (spec §3): never a
        # 5-tuple in ``edges``, whose ``len(edge) >= 4`` decoders would
        # read them as an interval slab.  Airside transects are STAGE A
        # (§6) — the shapes they cross are the airside ones the taxi axes
        # price — so they bind in the pass that owns airside values.
        from auto_patch.solve_stage import STAGE_A as _STAGE_A_FP, STAGE_KEY
        joint.append({"edges": [], "hyper": _hyper_fp,
                      STAGE_KEY: _STAGE_A_FP, "family": "transverse"})
    _stage("graph")

    hard = {i for i in range(n) if base_hard[i]}
    hard |= {i for i in runway_idx if i < n}
    # ── CORRIDOR FREE-END DEM TIES, CARRIED BY CANONICAL KEY ──────────
    # (corridor-joins round ruling 3.)  This pass REBUILDS the node list,
    # so the solve's own indices mean nothing here — the tie crosses as a
    # ``keyset`` artifact through the one resolver, exactly like
    # ``gs_witness`` and the seat boxes (node_space's law: an artifact
    # that must survive a node-list rebuild is minted by canonical key
    # and resolved by ``view_*``, never re-derived).  Membership only.
    _fp_free_ends = _store_of(layout).view_keyset("svc_free_end", b2i, n)
    if _fp_free_ends:
        hard |= _fp_free_ends
    # ── CORRIDOR MOUTH SEATS: RE-DERIVED HERE, THEN HELD ──────────────
    # (owner law 2026-08-15 + the timing adjudication on this lane's
    # attempt-2 measurement.)  THE SEAT IS RE-TAKEN BEFORE IT IS FROZEN.
    # A value seat cannot track a surface that keeps moving: taken at
    # DEM-follow time it agreed with the apron edge to within 0.03-0.28 m
    # and the apron then moved 5-9 m before emit, so the hold pinned a
    # stale value with perfect fidelity (measured at HECA, 22 of 23
    # residual sites).  HERE the airside surface has stopped — every
    # prior projection has run — so the seat is re-derived from the
    # CURRENT interpolated value at the same perpendicular foot (a pure
    # lookup on the minted recipe; the geometry is frozen, only values
    # moved) and the keyset below then freezes the FRESH value.  Order is
    # load-bearing: re-derive, then hard, then the W3 seed snapshot, so
    # the re-seated nodes are attributed as ``seed:base_hard`` and not as
    # unclaimed.  This is the OBJECT PADS posture (RULINGS 2026-08-14 —
    # resolve against the surface's own final value, downstream of the
    # movers) applied to road mouths.
    _mouth_reseated, _mouth_worst = _reseat_service_mouths(
        layout, b2i, elev, n, crown_of=_crown_of)
    if _mouth_reseated:
        import O4_UI_Utils as _UI_ms
        _UI_ms.vprint(1,
            f"  [pav-builder] service mouth seats RE-DERIVED at the "
            f"airside-final moment: {_mouth_reseated} seat(s) moved to "
            f"their pavement's current value (worst {_mouth_worst:.3f} m) "
            f"before the hold freezes them.")
    # Same channel and same reason as the free-end tie above — this pass
    # rebuilds the node list, so the seat crosses as a ``keyset`` artifact
    # through the one resolver.  The value it protects is the AIRSIDE
    # surface's own, so holding it here is airside-is-king expressed in
    # the last pass that could move it.
    _fp_mouths = _store_of(layout).view_keyset("svc_mouth", b2i, n)
    if _fp_mouths:
        hard |= _fp_mouths
    # ── THE CORRIDOR PROFILE, CARRIED BY CANONICAL KEY ────────────────
    # (staged-solve round, S2.)  Same channel and same reason as the
    # free-end tie above: the whole-run profile is the corridor's band
    # entering stage B, and this pass rebuilds the node list, so it
    # crosses as a keyset artifact through the one resolver.
    _fp_profile = _store_of(layout).view_keyset("svc_profile", b2i, n)
    if _fp_profile:
        hard |= _fp_profile
    # ── W3 · THE SEEDER RECORD (flag ``O4_FABRIC_W3_FGP_HARD_CAT``,
    # default ON; fabric-phase-b-spec.md W3) ──────────────────────────
    # "9,838 unattributed hard nodes is itself a defect."  This pass
    # hardened between 842 and 9,838 nodes with NO class map AT ALL (pin
    # attribution, lane pinattr 5f4924c) — the channel one node space
    # after the one the cycle-7.5 sweep named — so nothing downstream
    # could say WHY a node was immovable, and ~93 % of them turned out to
    # be welded to a graded strip.  Each site below now records its own
    # membership; :func:`classify_projection_hard` turns the sites into
    # ``{node: class}`` after the last one, and the residue class is
    # NAMED and asserted empty rather than folded into a neighbour.
    #
    # PURE INSTRUMENT: nothing here is read back by the projection, so
    # the emitted surface is identical with the flag either way.  What
    # the flag buys is bisectability of the COST, not of the geometry.
    from auto_patch.fabric_flags import on as _w3_on
    _w3_cat_on = _w3_on("O4_FABRIC_W3_FGP_HARD_CAT")
    _w3_seed = set(hard) if _w3_cat_on else None
    _w3_strip_freeze: set = set()
    _w3_weld: dict = {}
    # ── REQUIREMENT 2 (IDEMPOTENCE) IS **NOT ENFORCED HERE** — STOPPED
    # ON MEASUREMENT, cycle-4 ingestion round, attempt cap reached ─────
    # The spec's structural answer is to JOIN ``_untouched_hold`` to this
    # set: a node the solve valued and nothing moved since would then be
    # immovable, and a second-author move would be impossible rather than
    # merely unlikely.  It was built, measured on the harness, and it
    # does not hold up.  Matched in-tree controls, HECA constant-DEM
    # plateau, law-true census (harness ``census.py``):
    #
    #   control (this pass re-solving the field)      24,258  airside 16,832
    #   hold every untouched node                     48,432  airside 40,902
    #   hold every untouched LAWFUL node              38,681  airside 31,244
    #
    # and HEAZ 1,276 -> 1,360 / 1,312 on the same two arms.  The premise
    # the round was ranked on — that this pass MINTS ~10k of HECA
    # plateau's rows — is not what the instrument says.  It ABSORBS
    # them: the one solve does not yet publish a lawful plateau surface
    # (its own last projection exits UNCERTIFIED, 63,898 active violating
    # edges, worst residual 96.79 m, "the polytope is EMPTY"), and this
    # pass's whole-field re-projection is currently what takes that
    # surface from ~48k adjudicated rows to ~24k.  Freezing the solved
    # values ships the solve's residual verbatim.
    #
    # So the second authorship is REAL (the displacement census below
    # names it: 938-2,055 untouched vertices moved, worst 83 m) but it
    # cannot be closed HERE.  It closes when the solve publishes a
    # lawful surface — RULINGS 2026-08-05, "there is no lawful-infeasible
    # ground": an infeasible solve exit is a law or instrument defect to
    # fix at the solve.  Until then this pass keeps its repair role and
    # the ledger below REPORTS the mutation set and the hold that would
    # apply, so the next attempt starts from a number rather than a
    # premise.  What DID land is the rest of the ingestion: one law, one
    # source, for every input the two constraint builds used to disagree
    # on.
    # EMITTED TERRAIN-BAND FREEZE (2026-07-17, for the LATE
    # pipeline-end re-projection): graded_strip / gap-fill terrain
    # surfaces are emit-derived (per-vertex DEM-into-corridor clamps,
    # healed at emit, NO neighbour coupling) — once emitted they are
    # final.  Their zone vertices are solver variables, so an
    # unconstrained re-projection can move ONE zone vertex to its own
    # re-referenced clamp while its neighbours keep the emitted value
    # (measured SPJC: one vertex 32.9 → 34.0 = a fresh 1.1 m in-band
    # TEAR).  Freeze every already-emitted terrain-band ring vertex;
    # pavement↔band weld rows reconcile at ``to_osm`` (authority
    # consensus — pavement wins, strips bend).  Before band emission
    # the mid-pipeline call finds no such shapes and is unchanged.
    # Freeze ONLY band-exclusive vertices: a weld-row node SHARED with a
    # pavement ring stays free (it must move with the pavement the late
    # projection is fixing; the band's claim reconciles at ``to_osm``).
    _late_projection_run = False
    _rwy_boundary_frozen: set = set()
    try:
        from auto_patch.layout import ROLE_GRADED_STRIP as _R_STRIP
        from auto_patch.clearance import (
            _AIRSIDE_PAVEMENT_ROLES as _FRZ_PAV_ROLES)
        _cps_freeze = layout.canonical_points
        _pav_idx: set = set()
        _strip_shapes = []
        for _s in layout.shapes:
            if (_s.polygon is None or _s.polygon.is_empty
                    or _s.polygon.geom_type != "Polygon"):
                continue
            if _s.role == _R_STRIP:
                _strip_shapes.append(_s)
            elif _s.role in _FRZ_PAV_ROLES:
                for (_px, _py) in _s.polygon.exterior.coords:
                    _pk = _cps_freeze.find_nearest(
                        float(_px), float(_py), _cps_freeze.tol_m)
                    _pi = b2i.get(_pk) if _pk is not None else None
                    if _pi is not None:
                        _pav_idx.add(_pi)
        _late_projection_run = bool(_strip_shapes)
        for _s in _strip_shapes:
            for (_fx, _fy) in _s.polygon.exterior.coords:
                _fk = _cps_freeze.find_nearest(
                    float(_fx), float(_fy), _cps_freeze.tol_m)
                _fi = b2i.get(_fk) if _fk is not None else None
                if _fi is not None and _fi < n and _fi not in _pav_idx:
                    hard.add(_fi)
                    if _w3_cat_on:
                        _w3_strip_freeze.add(_fi)
        if _late_projection_run:
            # RUNWAY-BOUNDARY freeze (late run only): a vertex lying ON
            # a runway boundary EDGE INTERIOR (a junction/crossing weld
            # between two runway ring vertices) is not in ``runway_idx``
            # (that set is ring-VERTEX keyed) yet carries the runway
            # longitudinal profile — the late pass moved one +0.24 m at
            # HECA 05L/23R and minted a 3.7 % profile kink.  The runway
            # is the datum; nothing on its boundary moves late.  The
            # containment scan is C-vectorized in the helper (one GEOS
            # ``contains_xy`` over all candidate nodes, identical
            # predicate on the identical zone geometry).
            from auto_patch.layout import (
                ROLE_RUNWAY as _FRZ_RWY,
                ROLE_RUNWAY_CROSSING as _FRZ_RWX,
                SHARED_VERTEX_TOL_M as _FRZ_TOL)
            _rwy_lines = [
                _s.polygon.exterior for _s in layout.shapes
                if (_s.role in (_FRZ_RWY, _FRZ_RWX)
                    and _s.polygon is not None
                    and not _s.polygon.is_empty
                    and _s.polygon.geom_type == "Polygon")]
            _rwy_boundary_frozen = _runway_boundary_freeze_indexes(
                nodes, n, hard, _rwy_lines, _FRZ_TOL)
            hard |= _rwy_boundary_frozen
    except _snapshot_geom_exceptions():                # pragma: no cover
        pass
    # RUNWAY-JOIN anchored nodes (user ruling 2026-07-16: taxi joins
    # anchor to the RUNWAY EDGE value — the crowned edge): the solve
    # pinned each join hard at the runway value and the drop field lands
    # it on the emitted edge; this projection must keep it pinned or a
    # free join gets dragged off the edge by its uncrowned neighbours
    # (KBNA 13/31: a gap-spine chain pulled a coincident join 0.22 m
    # below the crowned edge THROUGH this pass).  ``include_spine=False``
    # skips the anchor derivation inside build_unified_graph, so derive
    # them here explicitly — indices are this pass's own node list.
    try:
        if not G.runway_anchor:
            _GG._runway_anchors(layout, G, b2i)
    except _snapshot_geom_exceptions():            # pragma: no cover
        pass
    hard |= {i for i in G.runway_anchor if i < n}
    # tile-seam nodes: terrain-pinned for cross-tile stitching.
    # ``terrain_hard`` tracks the TERRAIN-dictated subset of the hard set
    # (seam pins + agreeing feature welds below): a violated law edge
    # between two terrain-pinned nodes is the terrain's own slope, not a
    # solver miss — exported to the break quarantine after the projection.
    terrain_hard: set = set()
    _tile_seam_idx: set = set()
    try:
        for i, (x, y) in enumerate(nodes):
            la, lo = layout.m_to_ll(x, y)
            if (abs(la - round(la)) < 1e-7 or abs(lo - round(lo)) < 1e-7):
                hard.add(i)
                terrain_hard.add(i)
                _tile_seam_idx.add(i)
    except Exception:
        pass
    # nodes welded to already-emitted FEATURE shapes (ribbon/bridge/
    # clearance/groundside copied pavement values BEFORE this pass — moving
    # the pavement side now would tear those welds open).
    #
    # AGREEMENT GATE (user 2026-07-06, HECA service-road cliffs): a weld is
    # only a weld when the two sides AGREE — the feature adopted the
    # pavement's value.  A coincident vertex whose values already DISAGREE
    # is a torn weld or a mere contact (HECA: road nodes the solve's
    # envelope had lifted 3.4 m above their ring sat mm-coincident with
    # raw-DEM groundside verts 5 m below; hardening froze the damage and
    # the projection reported the resulting walls as 16 "genuine" both-hard
    # edges).  Freezing preserves nothing there — leave the pavement node
    # FREE so the projection solves it lawfully.  A feature vertex whose
    # altitude cannot be derived keeps the conservative hardening.
    # ── W3 · THE SCOPE RE-DERIVES FROM SURVIVING GEOMETRY ONLY ────────
    # This map is rebuilt from ``layout.shapes`` AS THEY ARE NOW, on
    # every call — there is no cached feature population and no set
    # carried from the mid-pipeline pass.  That is what makes the
    # convergence thesis mechanical rather than hopeful: retire a family
    # of feature shapes in W2 and the welds that hardened against it
    # simply are not here to find.  ``feat_role_by_key`` records WHICH
    # family, so the census below can say so instead of implying it.
    feat_alt_by_key: dict = {}
    feat_role_by_key: dict = {}
    _w3_feat_shapes: dict = {}
    for s in layout.shapes:
        if (s.role in PAVEMENT_ROLES or s.polygon is None
                or s.polygon.is_empty):
            continue
        if _w3_cat_on:
            _w3_feat_shapes[s.role] = _w3_feat_shapes.get(s.role, 0) + 1
        try:
            ring = list(s.polygon.exterior.coords)
            per_vertex = None
            if s.node_altitudes and len(s.node_altitudes) >= len(ring) - 1:
                per_vertex = [float(a) for a in
                              s.node_altitudes[:len(ring)]]
            elif s.altitude is not None:
                per_vertex = [float(s.altitude)] * len(ring)
            for k, (x, y) in enumerate(ring):
                key = (round(x, 3), round(y, 3))
                value = (per_vertex[k] if per_vertex is not None
                         and k < len(per_vertex) else None)
                if key in feat_alt_by_key and feat_alt_by_key[key] is None:
                    continue          # an unverifiable weld stays hard
                if value is None:
                    feat_alt_by_key[key] = None
                    feat_role_by_key[key] = s.role
                elif key not in feat_alt_by_key:
                    feat_alt_by_key[key] = value
                    feat_role_by_key[key] = s.role
        except Exception:
            continue
    _WELD_AGREE_TOL_M = 0.05
    # WELD-KEY tolerance (user 2026-07-06, CYXY apron #29): a feature
    # contact vertex inserted post-solve (boundary-bridge insert) can sit
    # a few mm off the pavement ring vertex it welds — mm-exact keys miss
    # it and the node wrongly stays free.  Match at the canonical 0.5 m
    # registry tolerance via a coarse grid.
    _WELD_KEY_TOL_M = 0.5
    torn_feature_weld: set = set()
    feat_grid: dict = {}
    for (_kx, _ky), _v in feat_alt_by_key.items():
        feat_grid.setdefault((int(_kx // _WELD_KEY_TOL_M),
                              int(_ky // _WELD_KEY_TOL_M)),
                             []).append((_kx, _ky, _v))
    if feat_alt_by_key:
        for i, (x, y) in enumerate(nodes):
            _wkey = (round(x, 3), round(y, 3))
            feature_value = feat_alt_by_key.get(_wkey, "absent")
            if feature_value == "absent":
                _cx = int(x // _WELD_KEY_TOL_M)
                _cy = int(y // _WELD_KEY_TOL_M)
                _best = None
                for _ox in (-1, 0, 1):
                    for _oy in (-1, 0, 1):
                        for (_fx, _fy, _fv) in feat_grid.get(
                                (_cx + _ox, _cy + _oy), ()):
                            _fd = ((x - _fx) ** 2 + (y - _fy) ** 2) ** 0.5
                            if _fd <= _WELD_KEY_TOL_M and (
                                    _best is None or _fd < _best[0]):
                                _best = (_fd, _fv, (_fx, _fy))
                if _best is None:
                    continue
                feature_value = _best[1]
                _wkey = _best[2]
            # crown transform: elev is in z′ space here — lift the
            # feature's z value by the node's crown drop before comparing.
            if (feature_value is None
                    or abs(feature_value + _crown_of.get(i, 0.0) - elev[i])
                    <= _WELD_AGREE_TOL_M):
                hard.add(i)
                terrain_hard.add(i)
                if _w3_cat_on:
                    # W3 — THE CHANNEL, NAMED.  The seeder record is the
                    # FEATURE FAMILY this node welded to, because that is
                    # the lever: the pin attribution measured graded_strip
                    # at 93/96/90/89 % of the late freeze (HECA/SPJC/HEAZ/
                    # CYXY), and a class map that said only "feature weld"
                    # could not have shown it.
                    _w3_weld[i] = feat_role_by_key.get(_wkey) or "unknown"
            else:
                # TORN WELD: the feature holds a different value than
                # the pavement at the same coordinate — the emit
                # consensus will merge the two nodes toward the feature
                # side, so pairs through this vertex render the
                # feature's terrain value regardless of what the
                # projection solves (CYXY apron #29: bridge 692.85 vs
                # pavement 693.00 emitted the bridge value).  Treated as
                # terrain-dictated for the quarantine scan below.
                torn_feature_weld.add(i)

    # ── STRING-AS-LAW INTERVAL ROD carry (spec §10 — supersedes the §7
    # final hold) ────────────────────────────────────────────────────
    # This pass runs on a REBUILT node list (measured HECA: n = 125549 /
    # 128526 vs the solve's 130290) and has no spine concept, so the
    # solve exported the rod's interval edges as CANONICAL REGISTRY KEY
    # pairs (``layout.canonical_points`` buckets — the same keys
    # ``_build_node_list`` assigns indices to).  Re-map them here and
    # append them to ``joint`` as ordinary law edges: the projection
    # then maintains the string's SHAPE (the rod translates, never
    # sags) with no value-hold to fight — the §7 hold minted both-hard
    # violations wherever the law graph lacked a body↔spine pair.  A
    # pair with EITHER endpoint missing in THIS space (a corridor node
    # whose shape did not survive to the final geometry) is dropped and
    # counted — never enforced one-sided.  ``envelope_skip``: same
    # Dijkstra-safety rule as at registration.  Gate off ⇒ no export ⇒
    # byte-identical.
    from auto_patch.config import SPINE_TAUT_STRING as _TAUT_ON_FP
    if _TAUT_ON_FP:
        _rod_key_edges = getattr(layout, "_taut_rod_key_edges", None) or ()
        _rod_t0 = _time.time()
        _rod_fp_edges: list = []
        _rod_dropped = 0
        # ROD CARRY AUDIT (phase-1 probe, gate O4_ROD_CARRY_AUDIT=1 —
        # docs/specs/single-space-string-audit-spec.md §2): record WHICH
        # endpoint(s) failed to resolve, per dropped link.  Off ⇒ nothing
        # is recorded and nothing is imported ⇒ byte-identical.
        _rod_audit_on = _os.environ.get("O4_ROD_CARRY_AUDIT") == "1"
        _rod_drop_rec: list = []
        # ── COMPOSITION ACROSS DECIMATED RUNS (owner-approved semantics,
        # docs/specs/rod-compose-and-band-single-source-spec.md §A) ──
        # ``emit_decimate`` deletes 3D-collinear strung vertices between
        # the solve and THIS rebuilt node space, so a rod chain
        # S1 · v · v · v · S2 arrives here as two surviving endpoints and
        # three keys that resolve to nothing.  The removed run is not
        # information loss: each link's interval is ``[Δᵢ − εᵢ, Δᵢ + εᵢ]``
        # on ``elev[a] − elev[b]``, and those telescope along the chain, so
        # the single link (S1, S2) with the SUMMED interval
        # ``[ΣΔ − Σε, ΣΔ + Σε]`` is the EXACT rod constraint between the
        # survivors (the decimator's own kept-pair grade is the
        # length-weighted mean of the removed sub-segments — composition is
        # exact, not approximate).  A chain whose vertices all survive
        # composes 1:1 and is byte-identical to the legacy carry.  Links
        # before the chain's first surviving key / after its last, and runs
        # whose survivors collapse onto ONE rebuilt node, are dropped and
        # counted (never enforced one-sided).  STANDING LAW — the
        # ``O4_ROD_COMPOSE`` gate is gone; the per-pair carry below is the
        # no-chains fallback, not an arm.
        _rod_chains = getattr(layout, "_taut_rod_key_chains", None) or ()
        # STAGE OF EACH CARRIED ROD (S1b), read from the solve's export.
        # ``_rod_stage_of`` maps a chain / flat-pair index to its stage;
        # the carry below tags every composed interval with it, so the
        # §10 rod — which reaches this projection with NO role key and is
        # therefore invisible to the road-pair withholding (coupling 4) —
        # cannot bind an airside endpoint from a groundside chain.
        _rod_chain_stage = list(
            getattr(layout, "_taut_rod_key_chain_stage", None) or ())
        _rod_key_edge_stage = list(
            getattr(layout, "_taut_rod_key_edge_stage", None) or ())
        _rod_fp_stage: list = []
        _rod_composed = 0          # composed links (each spans >1 minted)
        _rod_absorbed = 0          # minted links absorbed into those
        _rod_span_max = 0          # longest composed run, in minted links
        if _rod_chains:
            def _rod_resolve(_k):
                _i = b2i.get(_k)
                return None if (_i is None or _i >= n) else _i
            # COMPOSE PER STAGE.  Composition is per-chain, so running
            # the two stage groups separately composes exactly the same
            # links; only the entry they land in differs.
            _rod_fp_edges = []
            _rod_groups = {}
            for _ci_, _ch_ in enumerate(_rod_chains):
                _st_ = (_rod_chain_stage[_ci_]
                        if _ci_ < len(_rod_chain_stage) else _STAGE_A)
                _rod_groups.setdefault(_st_, []).append(_ch_)
            for _st_ in (_STAGE_A, _STAGE_B):
                _grp = _rod_groups.get(_st_)
                if not _grp:
                    continue
                (_ge, _gd, _gr, _gc, _ga, _gs) = compose_rod_chains(
                    _grp, _rod_resolve, want_drop_records=_rod_audit_on)
                _rod_fp_edges.extend(_ge)
                _rod_fp_stage.extend([_st_] * len(_ge))
                _rod_dropped += _gd
                _rod_drop_rec.extend(_gr)
                _rod_composed += _gc
                _rod_absorbed += _ga
                _rod_span_max = max(_rod_span_max, _gs)
        else:
            for _kk_, (_ka, _kb, _rlo, _rhi) in enumerate(_rod_key_edges):
                _ia = b2i.get(_ka)
                _ib = b2i.get(_kb)
                if (_ia is None or _ib is None or _ia >= n or _ib >= n
                        or _ia == _ib):
                    _rod_dropped += 1
                    if _rod_audit_on:
                        _a_bad = _ia is None or _ia >= n
                        _b_bad = _ib is None or _ib >= n
                        if _a_bad and _b_bad:
                            _why = "both_endpoints_unresolved"
                        elif _a_bad or _b_bad:
                            _why = "one_endpoint_unresolved"
                        else:
                            _why = "endpoints_collapsed_to_one_node"
                        _rod_drop_rec.append((_ka, _kb, _a_bad, _b_bad,
                                              _why))
                    continue
                _rod_fp_edges.append((_ia, _ib, _rlo, _rhi))
                _rod_fp_stage.append(
                    _rod_key_edge_stage[_kk_]
                    if _kk_ < len(_rod_key_edge_stage) else _STAGE_A)
        if _rod_fp_edges:
            for _st_ in (_STAGE_A, _STAGE_B):
                _sel = [e for e, st in zip(_rod_fp_edges, _rod_fp_stage)
                        if st == _st_]
                if _sel:
                    joint.append({"edges": _sel, "envelope_skip": True,
                                  "family": "rod_interval",
                                  _STAGE_KEY: _st_})
        if _rod_key_edges and _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [taut-string] rod carried={len(_rod_fp_edges)} "
                  f"(composed={_rod_composed} absorbing={_rod_absorbed}, "
                  f"longest run={_rod_span_max}) "
                  f"dropped={_rod_dropped} "
                  f"({_time.time() - _rod_t0:.3f}s)")
        if _rod_audit_on and _rod_key_edges:
            from auto_patch import rod_carry_audit as _rca
            _rca.report_carry(layout, _rod_drop_rec, len(_rod_fp_edges),
                              nodes, icao=icao, minted=len(_rod_key_edges),
                              composed=_rod_composed,
                              absorbed=_rod_absorbed,
                              span_max=_rod_span_max)

    # building pads: rigid movable FLAT groups (same model as the yield).
    # EVERY pad, detached ones included (item 3(b), 2026-08-05).  The
    # old exclusion existed because a detached pad was a HARD flat DEM
    # pin and freeing it here let the projection park it at the
    # surrounding airside field level.  Both halves of that are gone: the
    # pad no longer carries a DEM value to protect, and it can no longer
    # be pulled to the airside level because the airside reach band is
    # withheld from it and its ``seat_boxes`` box — the solved groundside
    # datum it abuts — bounds this pass through ``_fp_group_bounds``.
    # Flatness IS the building law, so a detached pad belongs in these
    # groups exactly like any other pad.
    cps = layout.canonical_points
    pad_groups = []
    pad_nodes: set = set()
    for s in layout.shapes:
        if (s.role != ROLE_BUILDING or s.polygon is None
                or s.polygon.is_empty):
            continue
        g = {b2i.get(cps.get_or_add(float(x), float(y)))
             for (x, y) in s.polygon.exterior.coords}
        g = {i for i in g if i is not None and i < n}
        if len(g) >= 2:
            pad_groups.append(g)
            pad_nodes |= g
    hard -= pad_nodes

    # ── TORN DATUM-PIN RELEASE (2026-07-26, KCLT junction micro-steps).
    # A post-solve feature weld can put a NON-runway hard pin — a runway-
    # end-skirt birth pin (B1: pinned pre-solve at the inverse-RESA floor)
    # or a runway-boundary-freeze capture — into a pavement ring a metre
    # from a runway-hard vertex, at a value the solve never graded against
    # the runway (measured KCLT 18L/36R: the skirt's lateral-overhang
    # corner pinned 227.54 sits 0.99 m from the runway corner 227.24 in a
    # junction ring = a 30 % ring step; the law pair IS in the projection
    # graph but BOTH endpoints are frozen, so the step ships).  The runway
    # is the datum (2026-07-16 ruling) and a weld that DISAGREES with it
    # is torn, not authoritative (the 2026-07-06 agreement gate).  The
    # repair: FIXPOINT-RE-SEAT the torn cluster — every re-seatable pin
    # with a violated law edge to the datum (or to an already re-seated
    # pin) has its value moved INSIDE the interval its datum-side edges
    # admit, while STAYING HARD.  Staying hard is the load-bearing part:
    # a FREED pin ping-pongs between the datum and the cluster's
    # remaining pins (measured KCLT: one freed node ground the worklist
    # heap 20+ min), and a freed-then-quarantined pin is re-blended by
    # the envelope pass onto the very contradiction being repaired (the
    # ``pre_broken`` merge happens after the envelope, which re-derives
    # its interval from the SAME remaining torn pins).  A hard pin skips
    # both; the writeback then carries the datum-lawful value into every
    # pavement ring holding the node, and at ``to_osm`` the authority
    # consensus carries it into the feature ring (pavement wins; the
    # skirt bends).  Re-seating is the converged projection of the
    # datum pairs applied directly — the sweep budget cannot be relied
    # on to reach them (measured KCLT late run: 42k edges over cap at
    # exit).  Tile-seam pins are the owner's seam law and never move.
    _torn_release_idx: set = set()
    _datum_idx = ({i for i in runway_idx if i < n}
                  | {i for i in G.runway_anchor if i < n})
    from auto_patch.layout import (
        ROLE_RUNWAY_CLEARANCE as _REL_CLR,
        REF_RUNWAY_END_SKIRT as _REL_SKIRT)
    _cps_rel = layout.canonical_points
    _skirt_pin_idx: set = set()
    for _s in layout.shapes:
        if (_s.role != _REL_CLR
                or getattr(_s, "ref", None) != _REL_SKIRT
                or _s.polygon is None or _s.polygon.is_empty
                or _s.polygon.geom_type != "Polygon"):
            continue
        for (_x, _y) in _s.polygon.exterior.coords:
            _i = b2i.get(_cps_rel.get_or_add(float(_x), float(_y)))
            if _i is not None and _i < n:
                _skirt_pin_idx.add(_i)
    # Only true runway RING vertices are unconditionally datum.  A
    # ``G.runway_anchor`` member can be a mis-captured join: the
    # anchor derivation adopts the node AT ITS CURRENT value on the
    # premise that a join carries the runway edge value — but a
    # torn feature pin sitting 0.1 m off the boundary (KCLT: the
    # skirt overhang corner at 227.54 beside the 227.24 corner)
    # gets anchored at the torn value and would then masquerade as
    # datum.  A feature-pinned anchor therefore stays RE-SEATABLE
    # and loses datum status; a genuine join (value already on the
    # edge profile) has no violated datum pair and never moves.
    _releasable = ((_skirt_pin_idx | _rwy_boundary_frozen)
                   - {i for i in runway_idx if i < n}
                   - _tile_seam_idx)
    _datum_idx -= _releasable
    if _releasable:
        # Candidate-edge adjacency, releasable nodes only.  Shape
        # entries carry their node set — skip whole entries that
        # touch no releasable node (the edge lists are the O(n²)
        # all-pair sets; the build-time HARD LAW).
        _rel_adj: dict = {}
        for _sc in joint:
            _sc_nodes = _sc.get("nodes")
            if _sc_nodes is not None and _releasable.isdisjoint(
                    _sc_nodes):
                continue
            for _e in _sc.get("edges") or ():
                if len(_e) >= 4:
                    continue          # interval edge (Stage B0)
                _a, _b, _bud = _e
                if _a >= n or _b >= n:
                    continue
                if _a in _releasable:
                    _rel_adj.setdefault(_a, []).append((_b, _bud))
                if _b in _releasable:
                    _rel_adj.setdefault(_b, []).append((_a, _bud))
        # EMITTED-space comparison (the load-bearing subtlety): the
        # law pairs here live in z′ = z + crown, and a runway ring
        # corner's z′ is its ridge-level value — a torn neighbour
        # holding the RIDGE value with NO crown drop looks LEVEL in
        # z′ while emitting a full crown-drop step (measured KCLT:
        # corner z′ 227.54/drop 0.30 beside the skirt pin z′ 227.537/
        # drop 0 = z′-level, emitted 227.24 vs 227.54 = the 30 %
        # step).  The mesh renders EMITTED values, so the torn test
        # and the re-seat interval both work in z − crown space; the
        # re-seated pin keeps its own crown drop.
        def _emit_val(_i):
            return elev[_i] - _crown_of.get(_i, 0.0)

        _datum_like = set(_datum_idx)
        _progress = True
        while _progress:
            _progress = False
            for _q in sorted(_releasable - _torn_release_idx):
                if _q not in hard:
                    continue
                _q_edges = _rel_adj.get(_q, ())
                if not any(_p in _datum_like
                           and abs(_emit_val(_p) - _emit_val(_q)) - _pb
                           > _WELD_AGREE_TOL_M
                           for (_p, _pb) in _q_edges):
                    continue
                # Re-seat into the intersection of ALL datum-side
                # intervals (violated or not — the move must not
                # break a currently-lawful datum pair).  An empty
                # intersection (contradictory datums) keeps the
                # birth value — that pin's pairs stay in the
                # both-hard report exactly as before.
                _lo, _hi = float("-inf"), float("inf")
                for (_p, _pb) in _q_edges:
                    if _p in _datum_like:
                        _lo = max(_lo, _emit_val(_p) - _pb)
                        _hi = min(_hi, _emit_val(_p) + _pb)
                if _lo <= _hi:
                    _new_emit = min(max(_emit_val(_q), _lo), _hi)
                    elev[_q] = _new_emit + _crown_of.get(_q, 0.0)
                    _torn_release_idx.add(_q)
                    _datum_like.add(_q)
                    _progress = True
                else:
                    # Contradictory datum sides: nothing lawful to
                    # re-seat onto; mark visited so the fixpoint
                    # terminates.
                    _torn_release_idx.add(_q)
    if _os.environ.get("O4_STEP_DEBUG") == "1":
        print(f"    [torn-release-debug] releasable={len(_releasable)} "
              f"skirt_pins={len(_skirt_pin_idx)} "
              f"boundary_frozen={len(_rwy_boundary_frozen)} "
              f"reseated={sorted(_torn_release_idx)}")
        for _dbg_i in sorted(_torn_release_idx):
            print(f"    [torn-release-debug]   idx={_dbg_i} "
                  f"xy={nodes[_dbg_i]} elev={elev[_dbg_i]:.3f}")
    if _torn_release_idx:
        import O4_UI_Utils as _UI_rel
        _UI_rel.vprint(1,
            f"    [route-profile] torn datum-pin re-seat: "
            f"{len(_torn_release_idx)} non-runway hard pin(s) "
            f"re-seated onto the runway datum.")

    # ── FIX ARM §3 — THE KEPT PINS JOIN THIS PASS'S HARD SET ────────────
    # (gate ``O4_STRING_PINS_FINAL_HOLD``; the solve exports the set only
    # when it is also on there, so an unset gate means no attribute and one
    # ``getattr``.)  Mechanism: EXACTLY Ruling 54's — set membership in the
    # pass's ``hard``/yield-hard analog, no value write, so a pin is held
    # here precisely as a truth anchor already is.  It is joined INSIDE the
    # crown window (``elev`` is z′ from the crown-in above until the
    # crown-out before writeback), which is where the probe's boundaries
    # sit, and BEFORE ``hard`` is consumed by the box / reference / dump
    # builders below — the same ordering the solve uses.
    # Law still overrules: a held pin whose neighbourhood the law cannot
    # satisfy surfaces through fix arm §2's bounded-yield / declared-
    # conflict path, which this pass's projection inherits when
    # ``O4_HARD_NEIGHBOUR_BOUND`` is on too.
    _string_pin_hold: set = set()
    # PARKED FEATURE — NOT A LAW GATE (integration sweep 2026-08-05).
    # The taut-string machinery is the owner's PAUSED feature: the strings
    # verdict is pending (memory ``string-purpose-statement``: strings are a
    # smoothing refinement for otherwise-correctly-graded taxiways, NOT a
    # surface authority), so this switch is deliberately NOT deleted with
    # the law gates.  It selects whether a PARKED feature runs at all, not
    # which law the build obeys.  Retire or adopt it when the owner rules.
    if _os.environ.get("O4_STRING_PINS_FINAL_HOLD", "0") == "1":
        _string_pin_hold = _string_pin_hold_indexes(layout, b2i, n)
        hard |= _string_pin_hold
        if _string_pin_hold and _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [S1b final-hold] {len(_string_pin_hold)} kept pin(s) "
                  f"resolved into this pass and held hard "
                  f"({len(_string_pin_hold & pad_nodes)} of them are pad "
                  f"ring vertices)")

    # ── W3 · THE SEEDER RECORD, ASSEMBLED (flag
    # ``O4_FABRIC_W3_FGP_HARD_CAT``) ──────────────────────────────────
    # Built HERE, at ``_stage("hard")`` — the LAST line that can add to
    # the set (the pad-group removal, the torn-datum-pin release and
    # the string-pin hold have all run).  A record assembled one site
    # earlier would describe what a mid-pass snapshot proposed, not what
    # actually froze.  Published on the layout so the census, a replay
    # and the verification round read the SAME map the pass applied —
    # the cycle-7.5 lesson, which is why the rule lives in a module-level
    # function with its own twins rather than inline here.
    #
    # BOTH PASSES ARE KEPT.  This function runs twice (mid-pipeline and
    # late), and the whole finding is the DIFFERENCE between them —
    # "hard 842 (mid) -> 9,838 (late), +9,004 new" — so the per-pass
    # censuses accumulate in a list while ``_fgp_hard_cat`` holds the
    # LAST one, which is the map the emitted surface was frozen under.
    if _w3_cat_on:
        _w3_cat = classify_projection_hard(
            hard,
            seed_hard=_w3_seed or set(),
            runway_nodes={i for i in runway_idx if i < n},
            strip_freeze=_w3_strip_freeze,
            runway_boundary=_rwy_boundary_frozen,
            runway_anchor={i for i in G.runway_anchor if i < n},
            seam_pins=_tile_seam_idx,
            string_pins=_string_pin_hold,
            feature_weld=_w3_weld)
        _w3_census: dict = {}
        for _c in _w3_cat.values():
            _w3_census[_c] = _w3_census.get(_c, 0) + 1
        _w3_unclaimed = _w3_census.get(PROJECTION_HARD_UNCLAIMED, 0)
        layout._fgp_hard_cat = _w3_cat
        layout._fgp_hard_census = {
            "hard": len(hard),
            "classes": dict(_w3_census),
            "unattributed": _w3_unclaimed,
            "feature_shapes_by_role": dict(_w3_feat_shapes),
            "late_projection_run": bool(_late_projection_run),
        }
        _w3_passes = getattr(layout, "_fgp_hard_census_passes", None)
        if _w3_passes is None:
            _w3_passes = []
            layout._fgp_hard_census_passes = _w3_passes
        _w3_passes.append(dict(layout._fgp_hard_census))
        try:
            import O4_UI_Utils as _UI_hc
            _UI_hc.vprint(1,
                          f"  [final-projection-hardcat] {icao}: "
                          f"{len(hard)} hard node(s), "
                          f"{_w3_unclaimed} unattributed; classes "
                          + " ".join(f"{_k}={_v}" for _k, _v
                                     in sorted(_w3_census.items())))
        except Exception:                                  # pragma: no cover
            pass

    _stage("hard")
    # BROKEN-NODE EDGE COUPLING (config.SVC_SPINE_EDGE_COUPLE, round-6 site-4):
    # this pass hardens the road's DEM-following adjacent-ground welds into a
    # wide staircase, so the reach envelope can falsely call a service-road
    # SPINE station broken and the blend drapes the centreline below its own
    # welded edges (CYXY service_road #201: −2.4 m).  Pass the service-road /
    # service-junction ring nodes so ``feasibility_project`` re-clamps only
    # THOSE broken nodes into the interval their hard welded neighbours admit
    # (the within-shape law); every other broken node keeps the untouched
    # blend.  Empty set / gate off ⇒ no-op.
    _svc_couple_nodes: set = set()
    from auto_patch.config import SVC_SPINE_EDGE_COUPLE as _SVC_EC
    if _SVC_EC:
        _cps_ec = layout.canonical_points
        for _s in layout.shapes:
            if (_s.role in ("service_road", "service_junction")
                    and _s.polygon is not None and not _s.polygon.is_empty):
                for (_x, _y) in _s.polygon.exterior.coords:
                    _k = b2i.get(_cps_ec.get_or_add(float(_x), float(_y)))
                    if _k is not None and _k < n:
                        _svc_couple_nodes.add(_k)
    if _svc_couple_nodes:
        # ── STAGE B MAY NOT WRITE STAGE A (S1c, coupling 13) ──────────
        # The selection above is by SHAPE ROLE, so a service ring's MOUTH
        # vertex — shared with an apron and therefore AIRSIDE (airside
        # wins the seat) — was handed in for re-clamping into the
        # interval its welded neighbours admit.  That is a groundside
        # coupling authoring an airside value.  The graph's mint-time
        # node stage is the exact filter, in this pass's own node space.
        _ec_stage = getattr(G, "node_stage", None) or {}
        _ec_air = {_k for _k in _svc_couple_nodes
                   if _ec_stage.get(_k, _STAGE_A) == _STAGE_A}
        if _ec_air:
            import O4_UI_Utils as _UI_ec
            _UI_ec.vprint(
                1, f"    [stage] svc edge-couple: {len(_ec_air)} of "
                   f"{len(_svc_couple_nodes)} service ring node(s) are "
                   f"AIRSIDE (shared mouths) and are NOT re-clamped")
            _svc_couple_nodes -= _ec_air
    # THE REPORT SET of this projection: nodes whose envelope interval this
    # pass found inverted, plus the unresolved triangle planes.  Since §2
    # deleted both of its sinks (the sidecar export and the freeze carry)
    # it is write-only — a count for the logs and the drain list.  Nothing
    # is excluded from the sweeps or from any census because of it.
    _projection_broken_idx: set = set()
    # SWEEP BUDGET: no constant here any more.  The history is the point —
    # 400 exited HECA (158k nodes) with 5,822 edges still over cap and 0
    # both-hard (pure non-convergence, whose worst survivors emitted as the
    # within-shape building/apron violation class); raising it to 2,400
    # still exited UNCERTIFIED at 2400/2400 on composed SPJC+HECA.  A
    # hand-set guard cannot be proved above a graph it has never seen, so
    # the budget is now DERIVED per projection from the graph's own
    # hop-diameter bound (``one_solve.derive_sweep_budget``; the derivation
    # and the measured evidence live in config.py).  The loop still exits
    # early on its certificate, so converged airports pay nothing.
    # THE BROKEN-QUARANTINE CARRY IS DELETED (spec ``docs/specs/kill-half-
    # spec.md`` §2, 2026-08-04).  It re-read the previous projection's
    # declared-broken keys and froze them here as ``pre_broken`` so the
    # late run could not "re-solve them normally".  With the blend gone
    # there is no held value to protect: a node the envelope cannot bound
    # is placed by the within-shape law and swept like any other free
    # node, and a materially inverted FINAL band is a build ERROR (§3)
    # rather than a region to carry forward.
    # LIFT-ONLY PADS in the late run: the mid projection seated every
    # pad at (or above) its route-feasible floor (the no-bowl ruling —
    # CYXY building16 ≥706 / building19 ≥698); the late pass may RAISE
    # a pad toward the final network ("the spine rises to serve a
    # building") but must never SINK one (measured: movable pads let
    # the late pass drop building16's group 0.23 m below its floor;
    # frozen pads instead undid the b19 lift).  Snapshot the seeded
    # group levels; sinks are restored after the projection.
    _pad_seed_levels = ([(g, {i: elev[i] for i in g})
                         for g in pad_groups]
                        if _late_projection_run else [])
    # RUNWAY PROFILE PRESERVE (both runs, 2026-07-17): the runway /
    # runway_crossing shapes carry the authoritative CIFP+flex profile;
    # this projection exists to close apron/junction/building
    # within-shape pairs on the final geometry and must never re-shape a
    # runway.  ``_writeback`` re-reads every runway ring vertex through
    # ``get_or_add`` and re-stamps it from ``elev`` — and on the
    # DENSIFIED final geometry a runway ring vertex spaced under the
    # 0.5 m canonical tolerance from ANOTHER vertex ALIASES to that
    # vertex's grade-graph node, so the writeback stamps the other
    # node's value onto the runway and mints a longitudinal kink.  Two
    # measured instances, one per run: LATE — two densified runway ring
    # vertices alias each other (HECA 05L/23R: a 60.46 boundary vertex
    # re-stamped from an aliased 60.7 neighbour = a 3.70 % > 1.5 %
    # step); MID — a NEIGHBOUR shape's boundary vertex welded onto the
    # runway's beyond-threshold blast-pad corner aliases it (HECA
    # 05L/23R + the object-pavement junction pressed to terrain: corner
    # 57.56 re-stamped 55.31 = a 1.8 % end kink; the corruption then
    # re-seeds as HARD truth in every later pass and the late run's
    # preserve faithfully restores the corrupted value).  The runway
    # nodes are already frozen through the projection (hard via
    # ``runway_idx``); the ONLY corruption is the aliased writeback.
    # Snapshot the runway altitude fields now and restore them verbatim
    # after the writeback — byte-identical to the pre-projection profile
    # in BOTH runs.
    _rwy_alt_snapshot = []
    from auto_patch.layout import (
        ROLE_RUNWAY as _PR_RWY, ROLE_RUNWAY_CROSSING as _PR_RWX)
    for _rs in layout.shapes:
        if _rs.role in (_PR_RWY, _PR_RWX):
            _rwy_alt_snapshot.append((
                _rs,
                list(_rs.node_altitudes)
                if _rs.node_altitudes is not None else None,
                _rs.altitude, _rs.altitude_high, _rs.altitude_low))
    # BOUNDED YIELD (owner ruling 2026-07-29: "Any yield absolutely needs
    # to stay within the feasibility box") — THIS pass releases seated
    # values too (``hard -= pad_nodes`` above), and it is where the HECA
    # burial actually shipped from: with fp#8 bounded, the pads still
    # emitted 87.99 vs seat 101.13 because this rebuilt-graph projection
    # re-freed them unbounded (measured 2026-07-29, /tmp/HECA_bounded.osm
    # first arm).  Same boxes, carried by CANONICAL KEY (this node list is
    # rebuilt — index carry is the rod-key lesson), lifted per node into
    # this pass's z′ = z + c crown space.  Hard nodes (seam pins, feature
    # welds, torn re-seats) are dropped inside ``feasibility_project`` —
    # the clamp refines the yield, never adds a hold.
    # STANDING LAW — there is no unbounded-yield arm.
    _fp_group_bounds = None
    _fp_node_bounds = None
    # Store view (U1): same boxes, resolved into THIS pass's rebuilt
    # node space and lifted into its z′ = z + crown frame in the one
    # resolver (crown is per-index, so lift-then-intersect equals
    # intersect-then-lift).
    _fp_box_idx: dict = _store_of(layout).view_interval(
        "seat_boxes", b2i, n, crown_of=_crown_of, combine="intersect")
    if _fp_box_idx:
        if pad_groups:
            _fp_group_bounds = []
            for _g in pad_groups:
                _gb = None
                for _i in _g:
                    _b = _fp_box_idx.get(_i)
                    if _b is not None:
                        _gb = (_b if _gb is None
                               else (max(_gb[0], _b[0]),
                                     min(_gb[1], _b[1])))
                _fp_group_bounds.append(_gb)
        _fp_node_bounds = {_i: _b for _i, _b in _fp_box_idx.items()
                           if _i not in pad_nodes}
    # ── FINAL-PASS STATE (rides gate ``O4_DUMP_SOLVE_STATE``) ─────────────
    # The final pass's reference-snapshot moment, in THIS pass's rebuilt node
    # space and crowned z′ frame, so checkpoint 1's |z_ref − final elev| table
    # is single-tree instead of spanning two dumps from two days.  Written per
    # invocation (final #1 and #2) under a sequence suffix.  Unset ⇒ inert.
    _fm_fp_path = _os.environ.get("O4_DUMP_SOLVE_STATE")
    if _fm_fp_path:
        import pickle as _pk_fmf
        _fm_seq = globals().get("_FM_FINAL_SEQ", 0) + 1
        globals()["_FM_FINAL_SEQ"] = _fm_seq
        _fm_out = f"{_fm_fp_path}.final{_fm_seq:02d}.pkl"
        with open(_fm_out, "wb") as _fh_fmf:
            _pk_fmf.dump({
                "n": int(n),
                "elev": list(elev),
                "crown": {int(_k): float(_v) for _k, _v in _crown_of.items()},
                "hard": sorted(int(_i) for _i in hard),
                "nodes_ll": [layout.m_to_ll(_x, _y) for (_x, _y) in nodes],
            }, _fh_fmf, protocol=4)
        print(f"    [field-moment] final#{_fm_seq} -> {_fm_out}", flush=True)
    # NO REFERENCE RODS at the final projection either (build-complete-
    # then-debug round).  This pass releases seated values and lets the
    # rebuilt-graph law decide where they land; there is no z_ref to
    # snapshot, no per-pass R to rebuild and no reference field to
    # resolve.  ONE authority: the joint law edges.
    # ── GROUNDSIDE WELDS AT THE FINAL PROJECTION ─────────────────────────
    # ``terrain_hard`` merges THREE different authorities — cross-tile DEM
    # seam pins, welds to GROUNDSIDE rings, and welds to other features
    # (ribbon / bridge / clearance) — and reporting them all as
    # ``terrain_pin`` made the groundside share of this pass's break
    # witnesses a matter of INFERENCE rather than measurement.  Name them.
    #
    # These welds carry groundside's value onto pavement by construction:
    # ``anchors.apply_groundside_reach`` re-levels the lot and (under
    # ``O4_GS_PAV_WELD``) stamps that level onto the coincident pavement
    # node, which this pass then hardens because the two sides AGREE.  So a
    # ``gs_weld`` witness IS a groundside value witnessing airside — the
    # same thing ``gs_pin`` is at fp#8, one node space later.
    #
    # So the clause applies HERE TOO, and since the build-complete-then-
    # debug round BOTH halves are standing law.  The measurement that
    # used to justify shipping only the solve half is recorded below as
    # a DEBT, not as a gate: the delta is
    # this half alone, emitted battery, 2026-07-30:
    #   * HECA within-shape 482 → 459 (baseline 460) — it cancels the +22
    #     the solve half costs at HECA; break pairs 17 530 → 17 823
    #     (baseline 18 161); every step / tear / stacked line unchanged;
    #   * **SPJC within-shape 78 → 121 (baseline 81)** — a +40 regression on
    #     a FLAT FIXTURE, which is a no-regression gate.  CYXY 9 → 8.
    #   * broken nodes at this pass 7 603 → 7 529: as at fp#8, withdrawing
    #     groundside's witness role does not HEAL the nodes it had
    #     witnessed, it re-witnesses them against runway-seam anchors
    #     (``terrain_pin`` ↔ ``terrain_pin`` 363 → 4 085).
    # DEBT for the debug phase: the SPJC 78 -> 121 mint is un-diagnosed
    # and needs the CYXY apron-#29 weld class below.  It is a defect to
    # ATTRIBUTE, not a reason to half-apply an owner law — under
    # ``feasibility-is-guaranteed`` a groundside value witnessing airside
    # is never a legitimate answer, so the regression is a symptom of
    # something else the withdrawal exposed.
    #
    # Why the two halves differ: at fp#8 a ``gs_pin`` is a value groundside
    # ASSERTS onto the route; here the pavement node was hardened because
    # the two sides AGREE, so the held value is also the pavement's own —
    # withdrawing it frees pavement to move away from a weld the emit
    # consensus still renders on the feature side (the CYXY apron #29
    # class).  That is the likely source of the SPJC mint.
    # STANDING LAW, both halves (see the solve half in
    # ``solve_route_profile``).  The gs-weld class is ALSO one of the
    # provenance classes that decides a ROLE-UNMATCHED anchor's
    # admission (route-metric spec §2 — "classified, never dropped
    # blind"), so it is built unconditionally now.
    _gs_weld_idx: set = set()
    _gs_weld_wanted = True
    if _gs_weld_wanted and terrain_hard:
        _gs_ring_grid: dict = {}
        try:
            from auto_patch.layout import (
                ROLE_GROUNDSIDE_PAVEMENT as _RGP_FP)
            for _s in layout.shapes:
                if (_s.role != _RGP_FP or _s.polygon is None
                        or _s.polygon.is_empty):
                    continue
                for (_gx, _gy) in _s.polygon.exterior.coords:
                    _gs_ring_grid.setdefault(
                        (int(_gx // 0.5), int(_gy // 0.5)), []).append(
                            (float(_gx), float(_gy)))
        except Exception:
            _gs_ring_grid = {}

        def _is_gs_weld(_i):
            if not _gs_ring_grid or _i >= len(nodes):
                return False
            _x, _y = nodes[_i]
            _cx, _cy = int(_x // 0.5), int(_y // 0.5)
            for _ox in (-1, 0, 1):
                for _oy in (-1, 0, 1):
                    for (_gx, _gy) in _gs_ring_grid.get(
                            (_cx + _ox, _cy + _oy), ()):
                        if (_x - _gx) ** 2 + (_y - _gy) ** 2 <= 0.25:
                            return True
            return False

        _gs_weld_idx = {_i for _i in terrain_hard
                        if _i < n and _i not in _tile_seam_idx
                        and _is_gs_weld(_i)}
    # ── EXAMINED AND RULED **NOT** A DIVERGENCE (ingestion round,
    # requirement 4) ──────────────────────────────────────────────────
    # The obvious ingestion move here is to replace the scan above with
    # the solve's own ``_gs_hard`` pins, carried by canonical identity
    # (they ARE minted, as ``gs_witness``).  It is the wrong move, and
    # the difference is stated two paragraphs up: at the solve a
    # ``gs_pin`` is a value groundside ASSERTS onto the route, while
    # HERE the pavement node was hardened BECAUSE THE TWO SIDES AGREE.
    # These are two populations of the same law one node space apart,
    # not one population derived twice — so this is not a re-derivation
    # the round is entitled to collapse.
    #
    # MEASURED, so the ruling rests on a number: at HECA plateau the two
    # sets are carried 147 vs re-derived 154 with only ~61 in common
    # (+93/-86), and swapping in the carried set moved the law-true
    # census 24,258 -> 24,756 (airside +495).  Reverted; the divergence
    # is reported at every build so a later round can revisit it with
    # the numbers in hand rather than the premise.
    _carried_gs = _store_of(layout).view_keyset("gs_witness", b2i, n)
    if _carried_gs or _gs_weld_idx:
        import O4_UI_Utils as _UI_gsw
        _UI_gsw.vprint(1,
            f"    [gs-witness] {icao} final projection: {len(_gs_weld_idx)} "
            f"groundside weld(s) withdrawn from the airside envelope; the "
            f"solve's own {len(_carried_gs)} carried pin(s) overlap "
            f"{len(_carried_gs & _gs_weld_idx)} of them (two populations "
            f"of one law, one node space apart — see the note above)")
    _fp_witness_limited = None
    if _gs_weld_idx:
        from .anchors import gs_witness_horizon as _gs_wh
        from auto_patch.config import SERVICE_ROAD_MAX_GRADE as _SRMG
        _fp_witness_limited = (frozenset(_gs_weld_idx), _gs_wh(_SRMG))
    # BREAK FORENSICS (spec reference-honesty Track 1 step 4) — the EMITTED
    # surface comes out of THIS pass, so its witness pairs are the ones that
    # answer the mega-component feasibility question.
    # ONE author for the class map: the break forensics and the route-metric
    # admission clause read the SAME dict, in the same documented order
    # (runway_node, pad, tile_seam, gs_weld, terrain_pin, feature_weld,
    # service_ring, spine, hard_other), so a class name can never mean two
    # things in two reports.
    _fcat_fp = None
    if _os.environ.get("O4_BREAK_FORENSICS") or route_metric_envelope_enabled():
        _fcat_fp = {}
        for _i in (runway_idx or ()):
            if _i < n:
                _fcat_fp.setdefault(_i, "runway_node")
        for _i in pad_nodes:
            if _i < n:
                _fcat_fp.setdefault(_i, "pad")
        for _i in _tile_seam_idx:
            if _i < n:
                _fcat_fp.setdefault(_i, "tile_seam")
        for _i in _gs_weld_idx:
            if _i < n:
                _fcat_fp.setdefault(_i, "gs_weld")
        for _i in (terrain_hard or ()):
            if _i < n:
                _fcat_fp.setdefault(_i, "terrain_pin")
        for _i in (torn_feature_weld or ()):
            if _i < n:
                _fcat_fp.setdefault(_i, "feature_weld")
        for _i in _svc_couple_nodes:
            if _i < n:
                _fcat_fp.setdefault(_i, "service_ring")
        for _i in G.spine_nodes():
            if _i < n:
                _fcat_fp.setdefault(_i, "spine")
        for _i in hard:
            if _i < n:
                _fcat_fp.setdefault(_i, "hard_other")
    _fp_forensics = None
    if _os.environ.get("O4_BREAK_FORENSICS"):
        _fp_forensics = {
            "label": "final",
            "classes": _fcat_fp,
            "nodes_ll": [layout.m_to_ll(_x, _y) for (_x, _y) in nodes],
        }
    # ── NON-ROUTE SEED ADMISSION, FINAL PASS (spec §2: "in ANY pass") ────
    # The emitted surface comes out of THIS projection, so the clause that
    # decides who may witness has to hold here above all.  Role membership
    # from this pass's OWN registry scan (``b2i`` is this pass's node
    # space); the role-unmatched anchors are classified from ``_fcat_fp``.
    # ONE ROLE SCAN, TWO CONSUMERS (single-pass principle): the witness
    # admission below and the PROJECTION PARTITION's receiver set.
    _fp_roles, _fp_route_roles, _fp_witness_excluded = (
        _route_witness_admission(layout, b2i, n))
    if route_metric_envelope_enabled():
        _fp_excl, _fp_rep = _non_route_witness_nodes(
            _fp_roles, _fp_route_roles, hard, n, provenance=_fcat_fp)
        _fp_witness_excluded |= _fp_excl
        _report_witness_admission(icao, "final", _fp_rep)
    else:                                              # pragma: no cover
        _fp_witness_excluded = None
    # ── THE PROJECTION PARTITIONS (spec addendum, 2026-08-06) ──────────
    # This pass is the LAST WORD on the emitted surface, so receiver-only
    # has to hold here above all: airside projects with no groundside pair
    # in its constraint set, groundside projects after against the frozen
    # airside values.  See ``one_solve.feasibility_project_partitioned``.
    # REQUIRED, not an optional mirror of the solve (S1d): this pass
    # REBUILDS the node list and never rebuilds the gap-spine
    # constraints, so a stage-B spine node that is not admitted here is a
    # FREE AIRSIDE VARIABLE — the reach-band clamp moves it inside the
    # airside pass, which is the write the stage tag exists to stop.
    # Resolved by canonical key, so ``b2i``'s rebuilt space is fine.
    _fp_receivers = _receiver_nodes_from_roles(
        _fp_roles, gap_spine_stage_b_nodes(layout, b2i, n))
    # ── THE ENVELOPE, IN THIS PASS'S NODE SPACE AND z′ FRAME (spec
    # ``envelope-uses-the-centerline-graph``, gate
    # ``O4_ENVELOPE_FROM_BAND``) ─────────────────────────────────────────
    # The solve carried THE graph's band by canonical key; resolve it to
    # this rebuilt node list and LIFT it into z′ = z + crown, exactly like
    # the bounded-yield boxes and the reference band above (values here are
    # crown-lifted; the band lives in the uncrowned profile space).  A key
    # that did not survive the rebuild — and every node when the solve took
    # an early return, so no band was carried at all — reads ``None``:
    # off-net, local within-shape law, the documented default.  No carry ⇒
    # ``None`` handed in ⇒ the pair-closure envelope, unchanged.
    _fp_env_band = None
    if envelope_from_band_enabled():
        # Store view (U1): the full band artifact resolved positionally
        # into this pass's node space and z′ frame; absent/empty ⇒ None
        # ⇒ the pair-closure envelope, unchanged.
        _fp_env_band = _store_of(layout).view_positional_interval(
            "env_band", b2i, n, crown_of=_crown_of)
        # PRODUCTION EMITS WHAT IT DID: under the route-metric gate this
        # line is the proof the CARRIAGE resolved (a silently empty carry
        # would read as "off-net everywhere" and look like a clean result).
        if _fp_env_band is not None and (
                route_metric_envelope_enabled()
                or _os.environ.get("O4_STEP_DEBUG") == "1"):
            _env_hit = sum(1 for _b in _fp_env_band if _b is not None)
            print(f"    [env-band] final projection: {_env_hit} of "
                  f"{len(_store_of(layout).raw('env_band'))} carried band "
                  f"key(s) resolved into {n} node(s)")
    # FIX ARM §2's declared-conflict channel for THIS pass (write-only,
    # allocated only under the gate).
    _fp_declared: list = ([] if _os.environ.get(
        "O4_HARD_NEIGHBOUR_BOUND", "0") == "1" else None)
    # ── THE LAW CERTIFICATE, ENTRY (cycle-4 ingestion spec, requirement 4)
    # What this pass's rebuilt constraint set finds violated in the field
    # the solve produced, BY FAMILY.  A family over cap here is either a
    # genuine post-solve mutation or a law input the two constraint builds
    # disagree on — and naming which is the whole round.  Report-only.
    # ``family_of``: this pass's OWN graph, so the catch-all splits by the
    # constructor that minted each edge (cycle-5 fix 4).
    _fp_family_of = G.family_by_pair()
    _report_law_certificate(icao, f"final#{_ml_pass or 1} ENTRY",
                            projection_law_certificate(
                                joint, elev, n, hard,
                                family_of=_fp_family_of),
                            # THIS pass's REBUILT node space (not the
                            # solve's), read in the z′ = z + crown frame
                            # lifted at entry above.
                            n_nodes=n, crown_space="uncrowned z'")
    # ── AIRSIDE-VALUE AUDIT ACROSS THIS PASS (road-chord-limiter lane,
    # lead ruling 2026-08-20) ──────────────────────────────────────────
    # AIRSIDE IS KING: a post-solve GROUNDSIDE/ROAD mutation may move
    # groundside/road nodes only.  The partition below already makes that
    # structural on the CONSTRAINT side (airside projects with no
    # groundside pair in its set), but nothing watched the SEED side: an
    # airside-claimed node whose value a groundside pass rewrote enters
    # the airside pass with a different seed, and the airside pass then
    # re-projects from it.  This is the WATCHER for that channel — the
    # airside node set is the partition's own complement of
    # ``_fp_receivers`` (``layout.GROUNDSIDE_ROLES``, the same registry
    # ``check_grade.row_side`` reads), so there is no second role list.
    # REPORT ONLY: it freezes nothing.  Freezing airside here was built
    # and MEASURED in the cycle-4 ingestion round and is refused — see the
    # hold note above (HECA plateau airside 16,832 → 40,902): this pass is
    # currently what makes the airside surface lawful, so holding it ships
    # the solve's residual verbatim.
    _air_idx = [i for i in range(n) if i not in _fp_receivers]
    _air_entry = [elev[i] for i in _air_idx]
    # ── THE APRON STAGED SOLVE (spec apron-staged-solve-spec.md) ──────
    # The partition is the LAW's own mint-time verdict
    # (``grade_law.is_apron_interior`` via ``UnifiedGraph.edge_interior``),
    # taken beside the family axis it parallels.  ``staged_report`` collects
    # the A1/A2 split for the certificate below.
    _fp_interior = G.interior_pairs()
    _fp_staged_report: dict = {}
    setattr(layout, "_apron_staged_report", _fp_staged_report)
    rem, bh = feasibility_project_partitioned(
                                  elev, joint, hard, force_scalar=True,
                                  receiver_nodes=_fp_receivers, n_nodes=n,
                                  env_band=_fp_env_band,
                                  family_of=_fp_family_of,
                                  apron_interior_pairs=_fp_interior,
                                  staged_report=_fp_staged_report,
                                  forensics=_fp_forensics,
                                  witness_limited=_fp_witness_limited,
                                  witness_excluded=_fp_witness_excluded,
                                  # NO GATES (RULINGS 2026-08-05): the
                                  # O4_FINAL_PROJECTION_MAX_ITERS env
                                  # override is deleted with the rest of
                                  # this territory's.  No ``max_iters``
                                  # either — the sweep budget is DERIVED
                                  # from this projection's own graph (see
                                  # the note above the broken set).
                                  flat_groups=pad_groups or None,
                                  pre_broken=(pre_broken or None),
                                  broken_out=_projection_broken_idx,
                                  edge_couple_nodes=(_svc_couple_nodes or None),
                                  group_bounds=_fp_group_bounds,
                                  node_bounds=_fp_node_bounds,
                                  declared_out=_fp_declared)
    # THE SENIORITY PARTITION, exported for the census (spec section 3).
    # TAKEN AFTER THE PROJECTION (lead 2026-08-23) so it can publish the
    # RUNTIME's own partition from the staged report rather than deriving a
    # second, narrower one — see the ONE PARTITION INPUT note below.
    # ONE function (``grade_law.apron_node_seniority``) fed with the pairs
    # the law already classified — the reader never re-spells the predicate.
    try:
        from auto_patch import grade_law as _GLsen
        _ap_nodes, _strict = set(), []
        for _e4, _it in zip(G.edges, G.edge_interior):
            _a4, _b4 = _e4[0], _e4[1]
            if not isinstance(_a4, int) or not isinstance(_b4, int):
                continue
            _k4 = (min(_a4, _b4), max(_a4, _b4))
            if _k4 in _fp_interior:
                _ap_nodes.update(_k4)
            elif str(_fp_family_of.get(_k4, "")).startswith("unified:apron"):
                _ap_nodes.update(_k4)
                _strict.append(_k4)
        _tx_nodes = set()
        for _h in (getattr(layout, "_transverse_hyper_rows", None) or ()):
            try:
                _tx_nodes.update(int(_i) for _i in _h[0])
            except Exception:
                pass
        # ONE PARTITION INPUT (lead 2026-08-23): prefer the RUNTIME's own
        # partition, published by the staged pass on its report.  The local
        # derivation below is the fallback for a build where the staged
        # solve did not run (flag off, or no interior pairs at all); it
        # counted only ``unified:apron`` families as strict and so exported
        # a DIFFERENT partition from the one that ran — 2,395/751 against
        # the runtime's 2,962/83.  A partition nobody solved is not
        # evidence about the solve.
        _sen = dict(_fp_staged_report.get("seniority") or {}) \
            if isinstance(_fp_staged_report, dict) else {}
        if not _sen:
            _sen = _GLsen.apron_node_seniority(_ap_nodes, _strict, _tx_nodes)
        setattr(layout, "_apron_seniority_ll", [
            [*layout.m_to_ll(float(nodes[_i][0]), float(nodes[_i][1])), _v]
            for _i, _v in sorted(_sen.items()) if 0 <= _i < len(nodes)])
    except Exception as _e_sen:                          # pragma: no cover
        setattr(layout, "_apron_seniority_ll", [])
    # The audit's read-out.  ``>0`` is a STOP LINE, not a failure: the
    # count is the size of the airside second-authorship this pass
    # carries, and it is a PRE-EXISTING number (every post-solve
    # groundside writer feeds it, the lot chord limiter first of all).
    try:
        import O4_UI_Utils as _UI_AIR
        _air_moved = 0
        _air_worst = 0.0
        for _k, _i in enumerate(_air_idx):
            _d = abs(float(elev[_i]) - float(_air_entry[_k]))
            if _d > _IDEMPOTENCE_TOL_M:
                _air_moved += 1
                if _d > _air_worst:
                    _air_worst = _d
        _UI_AIR.vprint(1,
            f"  [airside-value-audit] {icao} final#{_ml_pass or 1}: "
            f"{_air_moved} of {len(_air_idx)} AIRSIDE node(s) moved across "
            f"this projection by > {_IDEMPOTENCE_TOL_M} m "
            f"(worst {_air_worst:.3f} m)"
            + (" — STOP: airside is king, a projection this pass drives "
               "from post-solve groundside seeds is a second author on "
               "airside values" if _air_moved else " — CLEAN"))
    except Exception:                                  # pragma: no cover
        pass
    # ── §4 BAND-3 AUDIT (write-only, env ``O4_TERRACE_FP_AUDIT``) ───────
    # The band-3 instrument is this pass's ``rem`` tally.  It already
    # consumes the terrace-relaxed budgets (both edge sets are rewritten
    # above), so it does NOT share the census frame error — but the spec
    # asks HOW MUCH of the residue crosses a declared joint before the
    # 730 may be treated as a target.  Recompute the over-cap set from
    # the SAME edge lists the tally used and classify it.  No production
    # value is read or written here.
    if _os.environ.get("O4_TERRACE_FP_AUDIT") == "1":
        try:
            from .apron_terrace import _crossed_joints as _xj
            _aj = list(getattr(_terrace_plan_fp, "joints", ())
                       or ()) if _terrace_plan_fp is not None else []
            _n_over = _n_cross = _n_apron = 0
            _worst = []
            for _entry in joint:
                for _e in (_entry.get("edges") or ()):
                    if len(_e) != 3:
                        continue
                    _i, _j, _bud = _e
                    if _i >= n or _j >= n:
                        continue
                    _ex = abs(elev[_i] - elev[_j]) - float(_bud)
                    if _ex <= 1e-3:
                        continue
                    _n_over += 1
                    _pa = nodes[_i] if _i < len(nodes) else None
                    _pb = nodes[_j] if _j < len(nodes) else None
                    if _pa is None or _pb is None or not _aj:
                        continue
                    if _xj(_aj, _pa[0], _pa[1], _pb[0], _pb[1]):
                        _n_cross += 1
                        _worst.append(round(_ex, 3))
            for _sid, _mem in (getattr(_terrace_plan_fp, "node_sets", {})
                               or {}).items():
                _n_apron += len(_mem)
            print(f"    [terrace-fp-audit] over-cap edges={_n_over} "
                  f"joint-crossing={_n_cross} joints={len(_aj)} "
                  f"panelized-nodes={_n_apron} "
                  f"worst-crossing-excess={sorted(_worst, reverse=True)[:8]}")
        except Exception as _aexc:                       # pragma: no cover
            print(f"    [terrace-fp-audit] FAILED: {_aexc}")
    # Deliver into the string sidecar when the mover ledger is carrying it
    # (the summary is shared by reference; ``_mover_publish`` below rewrites
    # the file, last call wins).  ``_ml_pass`` names which pass declared.
    if _fp_declared and _ml is not None and _ml.get("summary") is not None:
        for _dr in _fp_declared:
            _dr["call"] = f"final_proj_{_ml_pass}"
        _fp_sum = _ml["summary"]
        _fp_sum.setdefault("declared_hard_conflict_final", []).extend(
            _fp_declared)
        _fp_sum["n_declared_hard_conflict_final"] = len(
            _fp_sum["declared_hard_conflict_final"])
    # Late-run lift-only pad restore (see the snapshot above): a group
    # the projection SANK reverts to its seeded level; lifts stay.
    # Tolerance 0.15 m: a pad may absorb a small law-driven settle (the
    # welded apron pairs need centimetre moves — restoring those re-mints
    # marginal apron over-caps, measured SPJC apron #81 +0.05 m); only a
    # BOWL-scale sink (>0.15 m, e.g. building16's 0.23 m) is restored.
    for _g, _seed_by_node in _pad_seed_levels:
        if not _g:
            continue
        _now = min(elev[i] for i in _g)
        _was = min(_seed_by_node.values())
        if _now < _was - 0.15:
            for _i in _g:
                elev[_i] = _seed_by_node[_i]
    # TERRAIN-PINNED PAIR EXPORT (user 2026-07-06, CYXY #26/#29 after the
    # apron route-proximity cut): a violated law edge touching a
    # terrain-dictated pin (tile-seam node, agreeing boundary/feature
    # weld) after the projection has CONVERGED is the terrain's own slope
    # winning over the shape law — the free end, had it any slack, would
    # already have moved (a hillside strip welded to the boundary ribbon
    # carries the terrain's 1.25 % between ground-truth pins no 1 % law
    # can beat).  Export those endpoints to the break quarantine.  Scoped
    # to TERRAIN pins only (part-18 ruling: blanket both-hard quarantine
    # hides real anchor bugs — runway/pad/weld classes stay actionable).
    _VIOL_TOL_M = 0.03
    _terrain_like = terrain_hard | torn_feature_weld
    # THE RETIREMENT SINK (see ``_retire_terrain_pin_quarantine_enabled``,
    # default ON since the 2026-08-04 flip).  Gate ON: a separate set that
    # is REPORTED and then dropped, so the law reports what it finds
    # instead of hiding it.  Gate OFF the endpoints land in
    # ``_projection_broken_idx`` — which, since §2 deleted both of its
    # sinks, is itself only a REPORT now.
    _retire_tp = _retire_terrain_pin_quarantine_enabled()
    _tp_sink = set() if _retire_tp else _projection_broken_idx
    if _terrain_like:
        for _sc in joint:
            for _e in _sc["edges"]:
                if len(_e) >= 4:
                    continue              # interval edge (Stage B0)
                _a, _b, _bud = _e[0], _e[1], _e[2]
                if (_a >= n or _b >= n
                        or (_a not in _terrain_like
                            and _b not in _terrain_like)):
                    continue
                if abs(elev[_a] - elev[_b]) > _bud + _VIOL_TOL_M:
                    _tp_sink.add(_a)
                    _tp_sink.add(_b)
        # DEFERRED shapes carry no edges in ``joint`` (the scoped
        # projection proved them untouched), so a terrain-pinned pair
        # inside one is invisible to the scan above (CYXY apron #29: a
        # hillside strip welded to the boundary ribbon, deferred, its
        # 57 m chord 0.25 % over the 1 % law).  Scan such rings directly:
        # every (terrain vertex ↔ ring vertex) chord that stays inside
        # the polygon at the shape's role cap.
        from auto_patch.config import ROLE_GRADE_LIMITS as _RGL
        from shapely.geometry import LineString as _LS
        _cps_t = layout.canonical_points
        for _s in layout.shapes:
            _cap_role = _RGL.get(_s.role)
            if (not _cap_role or _s.polygon is None or _s.polygon.is_empty
                    or _s.polygon.geom_type != "Polygon"):
                continue
            try:
                _ring_t = list(_s.polygon.exterior.coords)[:-1]
            except Exception:
                continue
            _idx_t = [b2i.get(_cps_t.get_or_add(float(x), float(y)))
                      for (x, y) in _ring_t]
            _terrain_on_ring = [(k, i) for k, i in enumerate(_idx_t)
                                if i is not None and i < n
                                and i in _terrain_like]
            if not _terrain_on_ring:
                continue
            _poly_buf = None
            for (_kt, _it) in _terrain_on_ring:
                for _ko, _io in enumerate(_idx_t):
                    if _io is None or _io >= n or _io == _it:
                        continue
                    _dx = _ring_t[_kt][0] - _ring_t[_ko][0]
                    _dy = _ring_t[_kt][1] - _ring_t[_ko][1]
                    _dd = (_dx * _dx + _dy * _dy) ** 0.5
                    if _dd < 0.5:
                        continue
                    if (abs(elev[_it] - elev[_io])
                            <= _cap_role * _dd + _VIOL_TOL_M):
                        continue
                    if _poly_buf is None:
                        try:
                            _poly_buf = _s.polygon.buffer(0.1)
                        except Exception:
                            break
                    try:
                        if not _poly_buf.covers(_LS(
                                [_ring_t[_kt], _ring_t[_ko]])):
                            continue      # chord leaves the shape
                    except Exception:
                        continue
                    _tp_sink.add(_it)
                    _tp_sink.add(_io)
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [terrain-scan] terrain_hard={len(terrain_hard)} "
                  f"broken_now={len(_projection_broken_idx)}")
    # PRODUCTION EMITS WHAT IT DID: under the gate the population this export
    # would have quarantined is REPORTED, never written.  A silent retirement
    # would read as "the defect vanished" instead of "the defect is now
    # visible to the validator" — the whole point of the round.
    if _retire_tp and _tp_sink:
        _tp_free = len(_tp_sink - hard)
        print(f"    [terrain-pin-retired] {icao}: {len(_tp_sink)} node(s) "
              f"REPORTED not quarantined ({_tp_free} free, "
              f"{len(_tp_sink) - _tp_free} hard); neither the break sidecar "
              f"nor the projection carry receives them")
    _dbg_ll = _os.environ.get("O4_PROJ_DEBUG_LL")
    if _dbg_ll:
        try:
            for _part in _dbg_ll.split(";"):
                _dla, _dlo = (float(v) for v in _part.split(","))
                import math as _dbg_math
                _bi = min(range(len(nodes)), key=lambda i: _dbg_math.hypot(
                    (layout.m_to_ll(nodes[i][0], nodes[i][1])[0] - _dla)
                    * 111320,
                    (layout.m_to_ll(nodes[i][0], nodes[i][1])[1] - _dlo)
                    * 54460))
                _bla, _blo = layout.m_to_ll(nodes[_bi][0], nodes[_bi][1])
                _dd = _dbg_math.hypot((_bla - _dla) * 111320,
                                      (_blo - _dlo) * 54460)
                _n_edges = sum(
                    1 for _sc in joint for _e in _sc["edges"]
                    if _e[0] == _bi or _e[1] == _bi)
                print(f"    [proj-dbg] ({_dla},{_dlo}) -> idx={_bi} "
                      f"d={_dd:.2f}m elev={elev[_bi]:.2f} "
                      f"hard={_bi in hard} terrain={_bi in terrain_hard} "
                      f"pad={_bi in pad_nodes} joint_edges={_n_edges} "
                      f"broken={_bi in _projection_broken_idx}")
        except Exception as _e:
            print(f"    [proj-dbg] error {_e!r}")
    # TRIANGLE-PLANE LAW (user 2026-07-06): a 3-vertex sloped shape
    # renders as ONE plane, and can satisfy every vertex-PAIR budget yet
    # tilt beyond its role cap along the plane gradient (skinny slivers:
    # HECA junction #258 at the 05C corner 6.4 %, apron #41 by building7
    # 2.4 % — pairwise all inside the rounding envelope).  The pairwise
    # projection cannot see this, so clamp it here: move the triangle's
    # freest vertex the minimum that brings the plane inside the cap,
    # bounded by the interval its own law edges allow (ORDERING LAW —
    # post-projection moves are law-guarded).  Unfixable triangles are
    # REPORTED (``triangle_plane_disposition``, gate default ON since the
    # 2026-08-04 flip); they no longer have a quarantine to join.  Fixed
    # vertices are anchored through the later edge fairing so nothing
    # re-tilts them.
    _tri_anchor_idx: set = set()
    _n_tri_fixed, _tri_anchor_idx, _tri_broken = \
        _project_triangle_planes(layout, b2i, elev,
                                 hard | pad_nodes, joint, n)
    _projection_broken_idx |= triangle_plane_disposition(
        layout, _tri_broken, _n_tri_fixed)
    _stage("project")
    # THE PROJECTION SINK AND THE FREEZE CARRY — DELETED 2026-08-04 (spec
    # ``docs/specs/kill-half-spec.md`` §2).  What stood here appended this
    # projection's broken set to ``layout._break_node_ll`` (the sidecar
    # sink) and persisted it as ``layout._final_projection_broken_keys``,
    # which the NEXT projection re-read as ``pre_broken`` and froze out of
    # every sweep.  Both halves are the quarantine the owner's ruling
    # forbids — the bookkeeping half hid rows from the census, the freeze
    # half held free nodes (measured at HECA: 375 carried, 165 of them not
    # hard) immovable through the LATE airside projection, which is also an
    # airside-is-king breach.  ``_projection_broken_idx`` survives as the
    # REPORT the log lines and the drain list read.
    _n_deferred = _n_expanded = 0
    if scoped:
        _n_deferred = sum(1 for _sc in shape_constraints
                          if _sc.get("lazy_scoped"))
        _n_expanded = sum(1 for _sc in shape_constraints
                          if _sc.get("lazy_scoped")
                          and "lazy_expand" not in _sc)
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            for _sc in shape_constraints:
                if not _sc.get("lazy_scoped"):
                    continue
                _first = _sc["nodes"][0] if _sc["nodes"] else None
                _at = (f"({nodes[_first][0]:.0f},{nodes[_first][1]:.0f})"
                       if _first is not None else "?")
                print(f"    [scoped] deferred {_sc['role']} "
                      f"ref={_sc['ref'] or '-'} area={_sc['area']:.0f} "
                      f"at={_at} "
                      f"{'EXPANDED' if 'lazy_expand' not in _sc else 'kept'}")
    if _os.environ.get("O4_STEP_DEBUG") == "1":
        _lazy_certified = sum(1 for _sc in shape_constraints
                              if _sc.get("lazy_certified"))
        if _lazy_certified:
            _still_lazy = sum(1 for _sc in shape_constraints
                              if "lazy_expand" in _sc)
            print(f"  [flat-lazy] {icao} final projection: "
                  f"{_lazy_certified} certified, "
                  f"{_lazy_certified - _still_lazy} expanded, "
                  f"{_still_lazy} never expanded")
    # Re-fair the ring edges the projection just perturbed (the GS
    # distributes a cap-grade climb as a sawtooth between alternate
    # nodes; a linear cap-grade profile satisfies the same pairs) —
    # same second-difference law as the solve-time pass.
    #
    # LAW-GUARDED (user 2026-07-05): this is the LAST pass before
    # writeback — nothing re-enforces the pairs it perturbs, and the
    # unguarded POCS moved junction ring nodes over their MESH-chord
    # budgets (pairs crossing between two ring runs, invisible to the
    # ring triples) by a median 1.8 cm — the SPJC 43-pair cm-noise
    # class.  Every move is now clamped into the interval its node's
    # law edges allow, at the same RAW law budgets the projection just
    # enforced; nodes of shapes whose body pairs
    # are still lazy (never expanded ⇒ the projection proved them
    # untouched, so there is no sawtooth to re-fair there) are anchored.
    # SNAPSHOT RECAPTURE input (2026-07-18): mirror the solve-side
    # pre/post-fairing diff (the solve's ``_pre_fairing_elev`` block) —
    # this fairing is the LAST pass before writeback, nothing re-enforces
    # the pairs it perturbs, so the snapshot recaptured below must exclude
    # the moved nodes from the "unchanged ⇒ already enforced" proof.
    _scoped_projection_gate = _scoped_projection_enabled()
    _pre_fairing_elev = (list(elev)
                         if _scoped_projection_gate and recapture_snapshot
                         else None)
    from auto_patch.config import TAXIWAY_MAX_GRADE_CHANGE_PER_M
    from .one_solve import _build_adjacency
    # RAW law budgets — the projection enforces exactly these.
    _law_adjacency = _build_adjacency(joint, n)
    _lazy_guard_nodes: set = set()
    for _sc in shape_constraints:
        if "lazy_expand" in _sc:
            for _node in (_sc.get("lazy_nodes")
                          or _sc.get("nodes") or ()):
                if isinstance(_node, int):
                    _lazy_guard_nodes.add(_node)
    # RESA-CUT FAIRING EXEMPTION (arc R slice R1) — the same law as
    # at the solve-side call.  This pass rebuilds the node list on
    # the FINAL shapes, so the admitted cut rings resolve here too;
    # they carry no constraint in this graph at all, and fairing them
    # would drag the pavement vertices their weld rows share.  Gate
    # off ⇒ the cut resolves to no node and the set is empty anyway,
    # but the exemption is stated explicitly at BOTH call sites.
    # SHARED-CORNER AUTHORITY (standing law,
    # ``emit_snap.shared_corner_authority_nodes``): a vertex owned by
    # 2+ rings that ANY owner sees as a corner is not a ring-local
    # variable.  It joins the ANCHOR set, never ``skip_nodes`` — its
    # neighbours still fair AGAINST it, only the write is removed.
    # SPJC node 10625 was the centre of three different triples and
    # amplified a +0.078 m solve move into +0.310 m emitted (4.0x,
    # a 50.67 % grade row, rank 1 at that airport).
    from auto_patch.emit_snap import shared_corner_authority_nodes
    _corner_authority_idx = shared_corner_authority_nodes(layout, b2i)
    _fair_ring_edges(layout, elev, b2i,
                     hard | _lazy_guard_nodes | _tri_anchor_idx
                     | _corner_authority_idx, None,
                     TAXIWAY_MAX_GRADE_CHANGE_PER_M,
                     law_adjacency=_law_adjacency,
                     skip_nodes=_fp_resa_free_idx)
    # Fairing-moved canonical keys for the snapshot recapture below —
    # computed BEFORE the crown transform back (both sides of the diff in
    # the same z′ space, so only genuine fairing moves register).
    _fairing_moved_keys = None
    if _pre_fairing_elev is not None:
        _fairing_moved_keys = {
            key for key, i in b2i.items()
            if elev[i] != _pre_fairing_elev[i]}
    _stage("fairing")
    # ── THE LAW CERTIFICATE, EXIT: what this pass could not close, by
    # family.  Paired with the ENTRY reading above it separates "the
    # projection minted this" from "the projection inherited this".
    _report_law_certificate(icao, f"final#{_ml_pass or 1} EXIT",
                            projection_law_certificate(
                                joint, elev, n, hard,
                                family_of=_fp_family_of),
                            # Same pass, same node space as its ENTRY
                            # reading above — still BEFORE the crown
                            # transform back, so still uncrowned z′.
                            n_nodes=n, crown_space="uncrowned z'")
    # ── THE A1/A2 SPLIT AND THE PIN DOCKET (spec section 4) ───────────
    # A1's both-hard residue is the honest pin-contradiction number: an
    # edge both of whose endpoints are immovable cannot be projected, so
    # it is a statement about the PINS, not about the surface.  The list
    # below IS the next round's brief.
    _apron_staged_certificate(
        icao, _fp_staged_report, n, _fp_family_of,
        # THE SETS THAT ACTUALLY FROZE THESE NODES, most specific first.
        [("runway-datum", runway_idx),
         ("tile-seam", _tile_seam_idx),
         ("terrain", terrain_hard),
         ("seed-pin", {i for i in range(n) if base_hard[i]})])
    # ── PROBE A, FINAL-PROJECTION TAIL: THIS PASS'S EXIT BOUNDARY ───────
    # (spec amendment 2026-08-01.)  Taken BEFORE the crown transform back,
    # so it is in the SAME uncrowned z′ frame as every other boundary in
    # the tail; a move seen here is this pass's own doing.  This is also
    # the last state before ``_writeback``, so on the LAST pass the row's
    # ``z_emitted`` (= z′ − crown, recorded alongside) is the number the
    # .osm spells, up to emit quantisation.  Write-only.
    if _ml is not None:
        _mover_stamp_rebound(_ml, elev, _ml_idx, f"final_proj_{_ml_pass}")
        _mover_publish(_ml, layout, elev=elev, idx_map=_ml_idx,
                       crown_of=_crown_of, pass_no=_ml_pass)
    # crown transform back: z = z′ − c (see the entry transform above).
    if _crown_of:
        for _i, _v in _crown_of.items():
            elev[_i] = elev[_i] - _v
    _writeback(layout, elev, b2i)
    # Restore the runway profile the aliased writeback may have re-stamped
    # (see the RUNWAY PROFILE PRESERVE snapshot above): both runs.
    for (_rs, _na, _al, _ah, _lo) in _rwy_alt_snapshot:
        _rs.node_altitudes = list(_na) if _na is not None else None
        _rs.altitude = _al
        _rs.altitude_high = _ah
        _rs.altitude_low = _lo
    # ── [transverse-bind] — THE BAND'S KNOWN BLIND SPOT, MEASURED ─────
    # (spec §10.)  ``reach_band_unified`` is a route-edge Dijkstra and
    # cannot carry a hyperplane, so the writeback's band clamp may move a
    # node the transect law had just settled.  Nothing is repaired here —
    # the follow-on is a transect-aware clamp floor/ceiling, its own spec
    # — but the count is taken every build, on the WRITTEN-BACK values,
    # so a re-violation can never be an unmeasured suspicion.
    if _hyper_fp:
        try:
            _rv = _n_worst = 0
            _worst = 0.0
            _seen: set = set()
            for (_idx4, _w4, _b_h, _sid) in _hyper_fp:
                if _sid in _seen:
                    continue          # the (w, -w) pair is ONE transect
                _seen.add(_sid)
                _val = max(
                    sum(float(w) * float(elev[int(k)])
                        for w, k in zip(_w4, _idx4)),
                    -sum(float(w) * float(elev[int(k)])
                         for w, k in zip(_w4, _idx4)))
                _ex = _val - float(_b_h)
                if _ex > 0.02:
                    _rv += 1
                    if _ex > _worst:
                        _worst = _ex
            _bound = len(_seen)
            # THE NAME IS WHAT IT MEASURES (lead correction 2026-08-21).
            # This is read from ``elev`` — the projection's own exit field
            # — and ``_writeback`` stamps the LAYOUT, never ``elev``, so
            # the count was never the clamp's doing: it is the transect
            # residue THIS projection exited with.  The clamp's own
            # footprint is reported beside it, from its own findings.
            _cf = list(getattr(layout, "band_clamp_findings", None) or [])
            _cf_worst = (max(abs(float(f[3])) for f in _cf) if _cf else 0.0)
            import O4_UI_Utils as _UI_TB
            _UI_TB.vprint(
                1, f"  [transverse-bind] {icao}: bound={_bound} "
                   f"rows={len(_hyper_fp)} exit_over_budget={_rv} "
                   f"worst={_worst:.3f} m | band clamp: {len(_cf)} "
                   f"value(s), worst {_cf_worst:.3f} m (the band is a "
                   f"route-edge Dijkstra and cannot carry a hyperplane — "
                   f"spec section 10)")
            setattr(layout, "_transverse_bind_report",
                    {"bound": _bound, "rows": len(_hyper_fp),
                     "exit_over_budget": _rv, "worst_m": _worst,
                     "band_clamp_values": len(_cf),
                     "band_clamp_worst_m": _cf_worst})
        except Exception:                              # pragma: no cover
            pass
    _stage("writeback")
    # SNAPSHOT RECAPTURE (2026-07-18): the solve captures the scoped
    # snapshot ONCE at its writeback, so the LATE projection run compared
    # against SOLVE-time values, saw every mid-projected value as touched,
    # and deferred almost nothing (measured OTHH: 26 deferred of ~350+
    # soft shapes — see the broken-quarantine-carry note above).  Refresh
    # the snapshot from the state THIS run just wrote back, under the SAME
    # guard as the solve-side capture: the next projection run scopes
    # against the PREVIOUS run's output, so only shapes the bounded
    # post-mid churn (welds, band adoptions) actually touched re-project.
    # The snapshot's ``broken`` slot is now always EMPTY: the persisted
    # quarantine it used to carry (``_final_projection_broken_keys``) was
    # deleted with the rest of the machinery (spec kill-half §2).
    # A stale snapshot is SAFE (mismatched values ⇒ nothing defers), so a
    # geometry hiccup here simply keeps the previous snapshot.
    if (_scoped_projection_gate
            and recapture_snapshot):
        try:
            _capture_projection_snapshot(layout, _fairing_moved_keys,
                                         set())
        except _snapshot_geom_exceptions():
            pass
    _stage("snapshot")
    # LOCKSTEP PAIR-CAP FREEZE (2026-07-17): capture the baked pair
    # allowances THIS projection just enforced (grade_graph refreshed
    # ``layout._lockstep_shape_bake`` during the constraint build above)
    # as lat/lon + metre caps, BEFORE any later law-graph rebuild (an
    # in-memory validator run re-bakes on mutated rings and would
    # overwrite the store with tighter, never-enforced caps).  ``to_osm``
    # exports this frozen copy as the sidecar's ``pair_caps``;
    # ``tools/check_grade.py`` consumes it in place of its own re-bake.
    try:
        from auto_patch.verification import lockstep_pair_caps_ll
        layout._lockstep_pair_caps_ll = lockstep_pair_caps_ll(layout)
    except Exception:
        pass
    try:
        import O4_UI_Utils as _UI
        _scope_note = ""
        if scoped:
            _scope_note = (f" [scoped: {_n_deferred} deferred, "
                           f"{_n_expanded} expanded]")
        _UI.vprint(1, f"  [final-projection] {icao}: {len(nodes)} nodes, "
                      f"{len(hard)} hard, {len(pad_groups)} pad group(s) → "
                      f"{rem} edge(s) over cap ({bh} both-hard) "
                      f"in {_time.time() - t0:.1f}s.{_scope_note}")
        # THE INGESTION LEDGER: the mutation set this pass is actually
        # for, the hold that makes the rest idempotent, and every carried
        # law family's application count.  A "FAILED" here is a law that
        # silently did not apply — the thing the bare excepts used to hide.
        # CROSS-SECTION BINDING — INSTRUMENT TRUTH (RULINGS 2026-08-06,
        # "Instrument truth is law").  A law family's APPLICATION COUNT
        # says the edges were handed over; it does not say the surface
        # honours them, and a pair that binds nothing looks exactly like
        # a pair that binds everything in the ledger above.  So the
        # binding reports its own EXIT state against the projection's
        # final values: how many bound pairs are still over budget, the
        # worst |dz| against its own budget, and how many are
        # UNENFORCEABLE because both endpoints are hard — which is the
        # one way a correctly-built edge legitimately cannot act.
        if isinstance(_fp_law_counts.get("lateral_xsection"), int):
            try:
                _xs_over = _xs_bh = 0
                _xs_worst = (0.0, 0.0)
                for (_i, _j, _bud) in _xsec_fp:
                    if _i >= len(elev) or _j >= len(elev):
                        continue
                    _dz = abs(float(elev[_i]) - float(elev[_j]))
                    if _i in hard and _j in hard:
                        _xs_bh += 1
                    if _dz > _bud + 1e-9:
                        _xs_over += 1
                        if _dz - _bud > _xs_worst[0] - _xs_worst[1]:
                            _xs_worst = (_dz, _bud)
                _UI.vprint(1,
                           f"  [xsection-law] {icao}: {len(_xsec_fp)} bound "
                           f"pair(s) at exit — {_xs_over} still over budget "
                           f"({_xs_bh} both-hard, i.e. unenforceable); worst "
                           f"|dz| {_xs_worst[0]:.3f} m vs budget "
                           f"{_xs_worst[1]:.3f} m")
            except Exception as _xs_rep_exc:               # pragma: no cover
                _UI.vprint(1, f"  [xsection-law] {icao}: exit audit FAILED "
                              f"{_xs_rep_exc!r}")
        _law_note = (", ".join(f"{_lk}={_lv}"
                               for _lk, _lv in sorted(_fp_law_counts.items()))
                     or "none on this layout")
        _mut_deltas.sort()
        _mut_note = ""
        if _mut_deltas:
            _md = len(_mut_deltas) // 2
            _mid_sv = sorted(_r[1] for _r in _mut_deltas)[_md]
            _mid_now = sorted(_r[2] for _r in _mut_deltas)[_md]
            _mut_note = (
                f" (moved |dz| p50 {_mut_deltas[_md][0]:.3f} "
                f"p90 {_mut_deltas[int(len(_mut_deltas) * 0.9)][0]:.3f} "
                f"max {_mut_deltas[-1][0]:.3f} m; carried p50 "
                f"{_mid_sv:.2f} vs seed p50 {_mid_now:.2f} m)")
        _UI.vprint(1,
                   f"  [final-projection-ingestion] {icao}: post-solve "
                   f"mutation set {_mut_new} new + {_mut_moved} moved "
                   f"node(s){_mut_note}; {len(_untouched_hold)} untouched "
                   f"node(s) the idempotence requirement would HOLD "
                   f"(REPORT ONLY — see the STOP note at the hard set); "
                   f"carried law {_law_note}")
        if _os.environ.get("O4_PROJ_TIMING") == "1":
            _UI.vprint(1, "  [final-projection-timing] " + " ".join(
                f"{name}={_stage_t.get(name, 0.0):.1f}s"
                for name in ("seed", "ctx", "scope", "constraints",
                             "graph", "hard", "project", "fairing",
                             "writeback", "snapshot")))
    except Exception:
        pass


def _open4(poly):
    c = list(poly.exterior.coords)
    return c[:-1] if c and c[0] == c[-1] else c


def pin_contradiction_refusals(pins, spine_adj, hard_values, *,
                               junior=(), tol: float = 0.01,
                               unbounded_out=None):
    """THE PIN-vs-SENIOR-ANCHOR PREDICATE — ``{node: violation}`` for
    every pin in ``pins`` whose VALUE cap-contradicts a SENIOR hard
    anchor within its own route budget.

    ONE implementation, every pin family.  The EAT anchor-rect guard
    (docs/specs/eat-anchor-contradiction-guard-spec.md) and the
    object-bridge deck-pin guard (docs/specs/kdfw-bridge-refusal-spec.md
    clause 2) ask the identical question of two different junior
    authorities, and the predicate itself is the seat machinery's —
    ``law_graph_budget.build_anchor_envelope`` + ``AnchorEnvelope.
    violation``.  A second spelling of a predicate is the census-wrapper
    defect class: two readers of one law that look identical and are not.

    SENIORITY is expressed by SUBTRACTION.  ``pins`` are removed from the
    anchor set (a pin may never bound itself, and one pin may never bound
    its sibling — same authority), and so is every node named in
    ``junior``: the caller's JUNIOR neighbours, the pin families that
    seed BELOW it.  The deck guard passes the EAT pins there, because a
    deck pin is seeded before an EAT pin and an EAT pin may not bound it;
    the EAT guard passes nothing, because it is the last family seeded
    and every other hard node outranks it.

    Returns ``{}`` when there is nothing to test or no senior anchor to
    test against — a missing bound is honest, never a silent refusal.
    Refusal is PER NODE.

    ``unbounded_out`` — an optional SET the caller passes to be told which
    pins carried NO BOUND AT ALL (``AnchorEnvelope.box`` is ``None``: the
    envelope's Dijkstra runs on the spine adjacency, and a pin off the
    spine graph is never reached).  Write-only, no effect on the verdict;
    it exists because "inside its envelope" and "never judged" used to be
    the same silence, and at KDFW that silence covered 47 of 67 pins —
    16 of them on the one rect whose value was condemned (see
    :func:`eat_rect_value_refusals`).
    """
    if not pins or not spine_adj:
        if unbounded_out is not None:
            unbounded_out.update(int(i) for i in (pins or ()))
        return {}
    from .law_graph_budget import build_anchor_envelope
    demoted = {int(i) for i in pins} | {int(i) for i in junior}
    senior = {int(i): float(v) for i, v in (hard_values or {}).items()
              if int(i) not in demoted}
    env = build_anchor_envelope(spine_adj, senior)
    if env is None:
        if unbounded_out is not None:
            unbounded_out.update(int(i) for i in pins)
        return {}
    refused: dict = {}
    for i, v in pins.items():
        if unbounded_out is not None and env.box(int(i)) is None:
            unbounded_out.add(int(i))
        viol = env.violation(int(i), float(v), tol=tol)
        if viol is not None:
            refused[int(i)] = viol
    return refused


def eat_pin_contradiction_refusals(pins, spine_adj, hard_values,
                                   *, tol: float = 0.01,
                                   unbounded_out=None):
    """THE EAT PIN GUARD — ``{node: violation}`` for every EAT anchor-rect
    pin that CAP-CONTRADICTS a senior hard runway/seam anchor within its
    own route budget (docs/specs/eat-anchor-contradiction-guard-spec.md).

    THE LAW: **an EAT pin never contradicts a senior hard anchor within
    route budget.**  The seat machinery already owns exactly this guard
    (the ``[seat-guard]`` block in :func:`solve_route_profile`, seed-fix
    round §4 hard-stamp guard), so this consumer adopts the SAME
    PREDICATE THROUGH THE SAME IMPLEMENTATION —
    ``law_graph_budget.build_anchor_envelope`` + ``AnchorEnvelope.
    violation`` — rather than spelling ``pin + cap·route < anchor`` a
    second time.  A second spelling of a predicate is the census-wrapper
    defect class: two readers of one law that look identical and are not.

    Attribution (SQ1, KSTJ +39-095, interventional): the pin authored
    241.8184 m into 18 junction nodes at another runway's threshold —
    5.692 m below the RW35 CIFP floor anchor 247.510 over 0.93–1.24 m of
    route budget — which inverted the final band at 31 nodes and dropped
    the whole patch from every build.  ``O4_EAT_SURFACE_CEILING=0`` built
    clean; the DEM and the seed cell were exonerated.

    ``pins`` — ``{node: regulation value}`` (``layout.
    _eat_anchor_pin_idx``).  ``spine_adj`` — the projection's own
    adjacency, AIRSIDE view (service pairs excluded, exactly as the seat
    guard's envelope is built).  ``hard_values`` — ``{node: elev}`` for
    every hard node on that graph.

    THE PINS ARE REMOVED FROM THE ANCHOR SET before the envelope is
    built: the question the law asks is whether the pin contradicts a
    SENIOR anchor, so a pin may never bound itself, and one EAT pin may
    never bound its sibling (they are the same, junior, authority).

    Returns ``{}`` when there is nothing to test or no senior anchor to
    test against — a missing bound is honest, never a silent refusal.
    Refusal is PER NODE: lawful pins in the same rect stand.

    The body is :func:`pin_contradiction_refusals` with no junior set:
    the EAT rect is the LAST family ``_seed_elevations`` pins, so every
    other hard node on the graph outranks it.

    ``unbounded_out`` is passed straight through — the caller uses it to
    report how many pins the per-node predicate could not judge at all,
    which is the population :func:`eat_rect_value_refusals` exists for.
    """
    return pin_contradiction_refusals(pins, spine_adj, hard_values,
                                      tol=tol,
                                      unbounded_out=unbounded_out)


def eat_pin_taxi_bound(pins, spine_adj, runway_anchor):
    """THE ROUTE TEST — the subset of ``pins`` whose node can TAXI to a
    runway anchor over the AIRSIDE route graph.

    An end-around taxiway is a TAXIWAY: an aircraft reaches it from the
    runway it goes around.  So "does a route exist from this pin's node
    to any runway anchor" is the feature's own definition, priced on the
    graph the anchor envelope is priced on (``u_spine_adj_airside`` —
    the unified spine graph with the service pairs excluded, which is
    what ``REACH_NO_SERVICE_SPINES`` means by a taxi route).

    Reachability, not budget: ``build_anchor_envelope`` builds no
    horizon, so a node the anchors can bound is exactly a node the
    anchors can REACH, and the two readings of "within the envelope's
    reach" coincide.  Spelling it as a plain traversal keeps this a
    connectivity question — it asks whether a route exists, never how
    much grade budget lies along it.

    ``runway_anchor`` — ``G.runway_anchor`` at the guard site, which is
    the genuine runway ring anchors: the EAT pins do not join that map
    until AFTER the flex pass, well below the guard, so a phantom pin
    can never certify itself or its sibling as the runway it routes to.

    Returns the SET of bound pin nodes.  Every pin is bound when the
    graph is empty of anchors — a missing bound is honest and the caller
    then refuses nothing.
    """
    if not pins:
        return set()
    seeds = [int(i) for i in (runway_anchor or ()) if int(i) in spine_adj]
    if not spine_adj or not seeds:
        return set(int(i) for i in pins)
    seen = set(seeds)
    stack = list(seeds)
    while stack:
        u = stack.pop()
        for edge in spine_adj.get(u, ()):
            v = edge[0] if isinstance(edge, tuple) else edge
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return {int(i) for i in pins if int(i) in seen}


def eat_unroutable_rect_refusals(pins, pin_rect, bound):
    """THE UNROUTABLE-EAT LAW (owner ruling 2026-08-12, "CANYON ROOT
    FIELD-CONFIRMED"; r17d law 1) — ``{node: rect}`` for every pin of
    every anchor rect NO node of which can taxi to a runway anchor.

    **AN EAT ANCHOR-RECT WHOSE GOVERNED NODES HAVE NO ROUTE TO ANY
    RUNWAY ANCHOR IS NOT AN END-AROUND TAXIWAY.**  The rect's scoping is
    purely GEOMETRIC — a corridor about the extended centreline beyond
    the runway end — so any pavement lying there is claimed, and a
    PERIMETER ROAD lying there is claimed too.  A road is not an
    end-around taxiway: no aircraft taxis onto it, and the airside route
    graph says so exactly (``REACH_NO_SERVICE_SPINES`` withholds the
    service pairs, so a road-only component holds no route to a runway).
    Pinning it at the departure-surface regulation authored the band at
    VHHH's remaining runway ends and the seal enforced it.

    WHOLE-RECT, and not per node, because the question the law asks is
    about the FACILITY: "is this pavement an end-around taxiway?" is
    answered once for the crossing segment, not vertex by vertex.  A
    genuine EAT that happens to carry one node whose spine edges were
    decimated away therefore keeps its whole rect (some node of it
    routes); a road corridor keeps none.  The contradiction guard beside
    it stays PER NODE for the same reason in reverse — that law asks
    whether one VALUE contradicts a senior anchor.

    ``pin_rect`` — ``layout._eat_anchor_pin_rect``, the segmentation the
    pin builder already did.  A pin with no rect identity is treated as
    its own rect, so a missing publication can only ever refuse less.
    """
    if not pins:
        return {}
    rect_of = {int(i): (pin_rect or {}).get(int(i), -int(i) - 1)
               for i in pins}
    routable_rects = {rect_of[int(i)] for i in bound if int(i) in rect_of}
    return {int(i): rect_of[int(i)] for i in pins
            if rect_of[int(i)] not in routable_rects}


def eat_rect_value_refusals(pins, pin_rect, refused):
    """THE RECT'S VALUE IS ONE VALUE — extend a contradiction refusal to
    every pin of the rect that carries it.

    THE DEFECT THIS CLOSES (KDFW +32-098, instrumented 2026-08-21; the
    wave-3 triage dossier's N-5).  ``eat_pin_contradiction_refusals``
    prices a pin on ``build_anchor_envelope``, which is a Dijkstra over
    the SPINE adjacency: a pin whose node carries no spine edge has NO
    BOX, and ``AnchorEnvelope.violation`` then returns ``None`` because
    *a missing bound is honest, never a silent refusal*.  At KDFW's
    18L/36R south rect the envelope can price only 3 of the 19 pins that
    carry 196.824 — and it REFUSES ALL THREE.  Measured, per pin:

        pin 3314 @(-2373,-2022) v=196.824 box=(174.981, 175.599) REFUSED
        pin 3316 @(-2391,-2021) v=196.824 box=None            accepted
        pin 3317 @(-2394,-2021) v=196.824 box=(174.672, 175.908) REFUSED

    Three neighbours, metres apart, ONE value, and the two the graph can
    price are condemned by 20.9-21.2 m against runway anchor 3311 =
    175.290 while the one it cannot keeps full authority.  Node 3316 then
    registers as a runway-class band anchor (``register_eat_anchors``)
    and authors its own band at distance 0 — the shipped, INVERTED
    ``[196.824, 175.943]`` the writeback clamped 72 solved values into,
    134 airside rows, worst 21.74 m.  The release path is NOT at fault:
    the three refused pins came back clean (no value, no hardness, no
    ``runway_anchor`` entry — twin
    ``tests/test_eat_refusal_contributes_nothing.py``).

    THE LAW.  ``_build_eat_anchor_rect_pins`` pins each crossing segment
    FLAT at ONE value (``end_elev + eat_pavement_ceiling(D_mid, ...)``),
    so "is this value lawful?" is a question about the RECT, not about a
    node — every node of the rect carries the same number and therefore
    the same contradiction.  The nodes the spine graph can price are the
    WITNESSES for the facility; the ones it cannot are not lawful, they
    are unpriceable.  This is the unroutable law's own reasoning
    (:func:`eat_unroutable_rect_refusals`, "the question the law asks is
    about the FACILITY"), applied to the other rect-level property.

    Rects are judged INDEPENDENTLY, and the same build shows the law is
    not a blanket: KDFW's other pin values — 174.522 (18 pins, 6 priced),
    167.368 (16 / 5) and 171.712 (14 / 4) — all sit INSIDE their
    envelopes, refuse nothing, and are untouched by this.  The
    unpriceable majority is general (only ~30 % of KDFW's pins carry a
    box at all); what is not general is a contradiction to extend.

    ``pins`` — the surviving ``layout._eat_anchor_pin_idx``.
    ``pin_rect`` — ``layout._eat_anchor_pin_rect``; a pin with no rect
    identity is its own rect (the unroutable law's convention), so a
    missing publication can only ever refuse less.  ``refused`` — the
    priced verdict from :func:`eat_pin_contradiction_refusals`.

    Returns the EXTENDED verdict: ``refused`` plus one entry per
    rect-mate, carrying its witness's violation record with
    ``via_rect`` naming the priced pin the verdict came from (the excess
    is the same number — the values are identical).  ``refused``
    unchanged when it is empty: no witness, no verdict.
    """
    if not refused or not pins:
        return dict(refused or {})
    rect_of = {int(i): (pin_rect or {}).get(int(i), -int(i) - 1)
               for i in pins}
    witness_of: dict = {}
    for i in refused:
        r = rect_of.get(int(i))
        if r is None:
            continue
        # The WORST priced contradiction on the rect is its witness, so
        # the reported excess is the rect's own worst — the same rule
        # the guard's loud line applies across pins.
        cur = witness_of.get(r)
        if cur is None or (float(refused[int(i)]["excess_m"])
                           > float(refused[cur]["excess_m"])):
            witness_of[r] = int(i)
    out = dict(refused)
    for i in pins:
        i = int(i)
        if i in out:
            continue
        w = witness_of.get(rect_of.get(i))
        if w is None:
            continue
        out[i] = dict(refused[w], via_rect=w)
    return out


def format_eat_rect_value_line(icao, n_extended, n_rects, n_unpriceable):
    """THE ONE LOUD LINE the rect-value extension prints — how many pins
    it took with the priced verdict, over how many rects, and how many of
    them the spine graph could not price AT ALL.

    That last number is the instrument truth the round exists to expose:
    an unpriceable pin used to read exactly like a lawful one."""
    return (
        f"  [eat-anchor-rect] {icao}: {n_extended} further pin(s) over "
        f"{n_rects} rect(s) REFUSED WITH THEM — the rect is pinned FLAT "
        f"at ONE value, so a contradiction priced at any node of it "
        f"condemns that value everywhere it is stamped "
        f"({n_unpriceable} of them carry NO senior-anchor bound at all: "
        f"no spine route reaches them, so the per-node predicate could "
        f"never have judged them); released to their seed.")


def format_eat_unroutable_line(icao, refused, n_pins, n_rects):
    """THE ONE LOUD LINE the unroutable-EAT law prints — how many pins
    over how many rects, and which rects they were.  Formatted HERE so
    the twin drives the string the build emits."""
    rects = sorted({int(r) for r in refused.values()})
    return (
        f"  [eat-anchor-rect] {icao}: {len(refused)} of {n_pins} pin(s) "
        f"REFUSED over {len(rects)} of {n_rects} rect(s) "
        f"{rects if len(rects) <= 12 else rects[:12] + ['...']} — NO taxi "
        f"route from any node of the rect to any runway anchor, so it is "
        f"not an end-around taxiway (a perimeter road in the corridor is "
        f"claimed by the rect's geometry and refused by its route); "
        f"released to their seed.")


def deck_pin_contradiction_refusals(pins, spine_adj, hard_values,
                                    *, junior=(), tol: float = 0.01):
    """THE OBJECT-BRIDGE DECK-PIN GUARD (docs/specs/kdfw-bridge-refusal-
    spec.md clause 2) — ``{node: violation}`` for every deck-end pin whose
    value cap-contradicts a senior hard runway/seam anchor within its own
    route budget.

    THE LAW: **a deck pin never contradicts a senior hard anchor within
    route budget** — the EAT pin law, applied to the other pin family that
    carries a VALUE from outside the solve.  A deck pin's value comes from
    a scenery pack (``grade_law.bridge_deck_end_pin_elevation_m`` over one
    DEM sample at the object anchor), so it is only ever as good as the
    pack; clause 1 refuses the classification defects it can see at
    classification time, and this is the backstop for every bad pack datum
    it cannot — which is the generalization the spec asks for.

    Attribution (KDFW +32-098, interventional, 2026-08-16): 193 hard
    deck-end pins at 183.29 m — one DEM sample at the shared Aerosoft
    anchor plus the 8 m authored deck height — entered the band seed set
    and inverted the final band at 650 nodes / 43 pairs, worst 1.996 m.
    The bridge-feature-off arm built clean.

    Same predicate, same implementation, same graph as the EAT guard
    (:func:`pin_contradiction_refusals`).  ``junior`` carries the pin
    families seeded AFTER the deck pins — the EAT anchor rect — so a
    junior pin can never bound a senior one.
    """
    return pin_contradiction_refusals(pins, spine_adj, hard_values,
                                      junior=junior, tol=tol)


def _publish_refusal_keys(layout, refused, nodes, attribute):
    """CARRY a pin guard's verdict by CANONICAL POINT, on ``attribute``.

    The guard can only be priced where the graph phase A projects on
    exists — inside the solve.  But ``_seed_elevations`` runs again at
    every later pass (the crown re-seed, each ``final_grade_projection``)
    on a layout that has GROWN, and would re-pin exactly the nodes the
    solve refused; the writeback band then CLAMPS them back, which is a
    clamp rescuing a law violation rather than the law holding (measured
    KSTJ on the EAT family: 16 clamps, worst +4.76 m, at the refused
    pins' own value).

    The join is the CANONICAL POINT, never the node index — index ``i``
    names a different node after a rebuild (the canonical-identity-join
    law; index keys once landed 448 of 455 SPJC seeds on the wrong node).
    Nodes whose point cannot be resolved are simply not carried, which is
    honest: the guard then re-refuses them on the next pass it can price.

    ONE implementation for both pin families — the EAT rect and the
    object-bridge decks — because "carry a refusal across a re-seed" is
    one mechanism, and two copies of it would drift.
    """
    cps = getattr(layout, "canonical_points", None)
    keys: set = set(getattr(layout, attribute, None) or ())
    if cps is None:
        return keys
    for i in refused:
        if i >= len(nodes):
            continue
        try:
            key = cps.get(float(nodes[i][0]), float(nodes[i][1]))
        except Exception:                                  # pragma: no cover
            key = None
        if key is not None:
            keys.add(key)
    setattr(layout, attribute, keys)
    return keys


def publish_deck_refusal_keys(layout, refused, nodes):
    """CARRY the deck-pin guard's verdict to every later re-seed, by
    canonical point (:func:`_publish_refusal_keys`).  The seeder's
    ``_object_bridge_pin_values`` is a BUCKET dict rebuilt from the
    classification at each pass and knows nothing of the refusal, so this
    key set is the only thing standing between a refused pin and its own
    resurrection."""
    return _publish_refusal_keys(
        layout, refused, nodes, "_object_bridge_pin_refused_keys")


def release_refused_deck_pins(layout, refused, elev, base_hard,
                              have_initial):
    """Put every REFUSED deck-end pin back exactly as ``_seed_elevations``
    found the node, and un-publish it.

    The seeder snapshotted ``(elev, have_initial, is_hard)`` per pinned
    node in ``layout._object_bridge_pin_prev``.  ALL THREE are restored,
    which is where this differs from the EAT release: an EAT pin skips
    every already-hard node, so its release can assume ``is_hard`` was
    False, while a deck pin deliberately OVERWRITES a coinciding seam
    vertex (the weld ruling's "pavement value always wins") — so a
    released deck pin may have to hand the node back to the seam, hard
    and at the seam's own value.

    Returns the number of nodes released.  A node with no snapshot is
    LEFT ALONE and reported by the caller's count mismatch rather than
    guessed at — inventing a seed would be the same class of defect the
    pin itself committed.
    """
    prev = getattr(layout, "_object_bridge_pin_prev", None) or {}
    pins = getattr(layout, "_object_bridge_pin_idx", None) or {}
    seam = getattr(layout, "_seam_pin_idx", None)
    n = 0
    for i in refused:
        row = prev.get(i)
        if row is None:
            continue
        if i < len(elev):
            elev[i] = float(row[0])
        if i < len(base_hard):
            base_hard[i] = bool(row[2])
        if have_initial is not None and i < len(have_initial):
            have_initial[i] = bool(row[1])
        pins.pop(i, None)
        if seam is not None and not row[2]:
            # Only a node this pin ITSELF put under seam-pin protection
            # is released from it; one that arrived already hard was
            # already protected by the family that hardened it.
            seam.discard(i)
        n += 1
    layout._object_bridge_pin_idx = pins  # type: ignore[attr-defined]
    return n


def format_deck_guard_line(icao, n_refused, n_pins, worst_node, worst,
                           anchor_value):
    """THE ONE LOUD LINE the deck-pin guard prints (nodes refused, worst
    shortfall, anchor identity).  Formatted HERE so the twin drives the
    string the build emits."""
    return (
        f"  [object-bridge] {icao}: {n_refused} of {n_pins} deck-end "
        f"pin(s) REFUSED — a deck pin never contradicts a senior hard "
        f"runway/seam anchor within route budget; worst node "
        f"{worst_node} pin {worst['pin_m']:.3f} is {worst['excess_m']:.3f} "
        f"m past its {worst['side']} {worst['bound']:.3f} (witness anchor "
        f"{worst['witness']} = {anchor_value:.3f}, route budget "
        f"{worst['route_budget_m']:.4f} m); released to their seed.")


def register_eat_anchors(G, pins, n_elev):
    """REGISTER the SURVIVING EAT anchor-rect pins as runway-class band
    anchors — THE one place the EAT family becomes a reach-band authority
    (``spine_value_fields`` seeds from ``G.runway_anchor``, so an entry
    here IS a floor/ceiling source at that node, at distance 0).

    EXTRACTED from ``solve_route_profile``'s inline loop so the twins can
    drive the RULE production applies instead of a transcription of it:
    the refusal-contributes-nothing law is a statement about what this
    function is handed, and a test that re-spells the ``setdefault``
    could not fail when the call site changes.  The body is verbatim —
    same iteration order, same ``setdefault`` precedence (a genuine
    runway-JOIN anchor at a shared bucket keeps datum authority), same
    ``pi < n_elev`` guard.

    ``pins`` is ``layout._eat_anchor_pin_idx`` AFTER every guard has
    released what it refused: a refused pin is not in it, and therefore
    never becomes a band anchor.  Returns the number registered.
    """
    n = 0
    for pi, pv in (pins or {}).items():
        if pi < n_elev:
            G.runway_anchor.setdefault(pi, float(pv))
            n += 1
    return n


def publish_eat_refusal_keys(layout, refused, nodes):
    """CARRY the guard's verdict by CANONICAL POINT.

    The guard can only be priced where the graph phase A projects on
    exists — inside the solve.  But ``_seed_elevations`` runs again at
    every later pass (the crown re-seed, each ``final_grade_projection``)
    on a layout that has GROWN, and re-pinned exactly the nodes the solve
    refused; the writeback band then CLAMPED them back, which is a clamp
    rescuing a law violation rather than the law holding (measured KSTJ:
    16 clamps, worst +4.76 m, at the refused pins' own value).

    The join is the CANONICAL POINT, never the node index — index ``i``
    names a different node after a rebuild (the canonical-identity-join
    law; index keys once landed 448 of 455 SPJC seeds on the wrong node).
    Nodes whose point cannot be resolved are simply not carried, which is
    honest: the guard then re-refuses them on the next pass it can price.

    The body is :func:`_publish_refusal_keys` on
    ``_eat_pin_refused_keys``; the deck-pin guard carries its verdict the
    same way, through the same code.
    """
    return _publish_refusal_keys(
        layout, refused, nodes, "_eat_pin_refused_keys")


def release_refused_eat_pins(layout, refused, elev, base_hard,
                             have_initial):
    """Put every REFUSED EAT pin back exactly as ``_seed_elevations``
    found the node, and un-publish it.

    The seeder snapshotted ``(elev, have_initial)`` per pinned node in
    ``layout._eat_anchor_pin_prev``; ``base_hard`` and the seam-pin
    protection set need no snapshot because the pin builder skips every
    already-hard node, so a pinned node was neither.  After this the node
    is an ordinary SOFT node carrying its DEM seed: it is not a phase-A
    truth anchor, not a reach-band anchor (``_eat_anchor_pin_idx`` no
    longer names it), not seam-protected, and not a runway-flex seed.

    Returns the number of nodes released.  A node with no snapshot is
    LEFT ALONE and reported by the caller's count mismatch rather than
    guessed at — inventing a seed would be the same class of defect the
    pin itself committed.
    """
    prev = getattr(layout, "_eat_anchor_pin_prev", None) or {}
    pins = getattr(layout, "_eat_anchor_pin_idx", None) or {}
    seam = getattr(layout, "_seam_pin_idx", None)
    n = 0
    for i in refused:
        row = prev.get(i)
        if row is None:
            continue
        if i < len(elev):
            elev[i] = float(row[0])
        if i < len(base_hard):
            base_hard[i] = False
        if have_initial is not None and i < len(have_initial):
            have_initial[i] = bool(row[1])
        pins.pop(i, None)
        if seam is not None:
            seam.discard(i)
        n += 1
    layout._eat_anchor_pin_idx = pins   # type: ignore[attr-defined]
    return n


def format_eat_guard_line(icao, n_refused, n_pins, worst_node, worst,
                          anchor_value):
    """THE ONE LOUD LINE the guard prints (spec: nodes refused, worst
    shortfall, anchor identity).  Formatted HERE so the twin drives the
    string the build emits."""
    return (
        f"  [eat-anchor-rect] {icao}: {n_refused} of {n_pins} pin(s) "
        f"REFUSED — an EAT pin never contradicts a senior hard "
        f"runway/seam anchor within route budget; worst node "
        f"{worst_node} pin {worst['pin_m']:.3f} is {worst['excess_m']:.3f} "
        f"m past its {worst['side']} {worst['bound']:.3f} (witness anchor "
        f"{worst['witness']} = {anchor_value:.3f}, route budget "
        f"{worst['route_budget_m']:.4f} m); released to their seed.")


def classify_hard_anchors(n, base_hard, flexed_idx, seam_pins,
                          runway_anchor, runway_nodes):
    """THE hard-anchor classifier — ``{node: class}`` for every node that
    is ``base_hard`` at the classification point, named by the source that
    actually hardened it.

    EXTRACTED (cycle-7.5 instrument sweep) from ``solve_route_profile``'s
    inline loop so the twin drives THE RULE the solve applies instead of a
    second transcription of it — ``tests/test_hard_anchor_class_axis.py``
    used to re-implement this precedence locally, so a change here could
    not fail it.  The body is verbatim: same iteration order (ascending
    index), same predicates, same order of tests, same names — so the
    returned dict is identical key-for-key and value-for-value to what the
    inline loop built.

    Precedence is MOST-SPECIFIC FIRST, and a node no source claims is
    NAMED ``base_hard:unattributed`` rather than folded into a
    neighbouring class, so the residue is countable instead of silently
    inflating a real population (the ``seed_rwy_seam`` blanket's cost:
    "610 anchors, 100 % class seed_rwy_seam", an artefact of the label).
    """
    out: dict = {}
    for i in range(n):
        if not base_hard[i]:
            continue
        if i in flexed_idx:
            out[i] = "rwy_flexed"
        elif i in seam_pins:
            out[i] = "seam_pin"
        elif i in runway_anchor:
            out[i] = "rwy_join"
        elif i in runway_nodes:
            out[i] = "rwy_profile"
        else:
            out[i] = "base_hard:unattributed"
    return out


#: The residue class of :func:`classify_projection_hard`.  It exists to
#: be COUNTED, and W3's whole point is that the count is zero: a node
#: this pass freezes with no site claiming it is the defect the record
#: was built to abolish, not a label to live with.
PROJECTION_HARD_UNCLAIMED = "fgp:unattributed"


def classify_projection_hard(hard, *, seed_hard, runway_nodes, strip_freeze,
                             runway_boundary, runway_anchor, seam_pins,
                             feature_weld, string_pins=()):
    """THE late-projection hard-anchor classifier — ``{node: class}`` for
    EVERY node ``final_grade_projection`` freezes, named by the site that
    actually froze it.

    W3 of ``docs/specs/fabric-phase-b-spec.md``.  Before this, that pass
    built no class map at all: its hard set went 842 -> 9,838 between the
    two final projections and every one of those nodes was unattributed
    BY CONSTRUCTION (pin attribution, lane ``pinattr`` 5f4924c).  That is
    what made the freeze impossible to reason about — the population that
    turned out to be ~93 % welded to a graded strip looked, from the
    code, like one anonymous set.

    THE SAME DISCIPLINE AS :func:`classify_hard_anchors`, deliberately:
    the rule lives HERE, at module level, so the twins drive the rule the
    pass applies instead of re-implementing it (the cycle-7.5 instrument
    sweep's lesson — a locally re-transcribed precedence is a twin a
    change cannot fail).  Precedence is MOST-SPECIFIC FIRST, and a node
    no site claims is named :data:`PROJECTION_HARD_UNCLAIMED` rather than
    folded into a neighbouring class.

    THE FEATURE WELD carries its FAMILY (``weld:graded_strip``,
    ``weld:boundary``, …), not a bare ``feature_weld``.  The family IS
    the lever the convergence thesis pulls: retire the geometry in W2 and
    the class empties, which a single blanket label could never show.

    ``feature_weld`` maps node -> the role of the feature shape whose
    ring vertex it welded to; every other argument is a set of node
    indices.  Counts only, no verdict: whether ``fgp:unattributed`` being
    non-zero is a STOP is the caller's judgement, not this function's.
    """
    out: dict = {}
    for i in sorted(hard):
        if i in runway_nodes:
            out[i] = "rwy_profile"
        elif i in runway_boundary:
            out[i] = "rwy_boundary"
        elif i in runway_anchor:
            out[i] = "rwy_join"
        elif i in strip_freeze:
            out[i] = "emitted_band_freeze"
        elif i in seam_pins:
            out[i] = "seam_pin"
        elif i in feature_weld:
            out[i] = f"weld:{feature_weld[i]}"
        elif i in seed_hard:
            out[i] = "seed:base_hard"
        elif i in string_pins:
            out[i] = "string_pin"
        else:
            out[i] = PROJECTION_HARD_UNCLAIMED
    return out


def attribute_seam_spine_hardening(hard_cat, truth_hard, pinned_idx):
    """Label the late hardening between the classifier and the phase-A
    truth snapshot, and COUNT what no source claims.

    THE DEFECT this replaces (cycle-7.5 instrument sweep; the same shape
    commit ``092af7f`` removed one layer up).  ``_seam_spine_anchors``
    hardened nodes, kept its ``seen`` set purely local and had its return
    value DISCARDED at the call site; the only trace was a blanket
    ``for i in truth_hard: hard_cat.setdefault(i, "seam_spine_anchor")``
    that labelled EVERY node hardened since the classifier
    ``seam_spine_anchor`` whatever had actually hardened it — including
    when the seam machinery never ran at all.  The campaign record's
    rider ("444 of 1,077 nodes in the class were hardened with NO seeder
    record — an unattributed hardening channel") is that blanket.

    ``pinned_idx`` is the set ``_seam_spine_anchors`` ACTUALLY pinned, so
    those nodes are attributed from the publisher.  Whatever the blanket
    still absorbs after that is the UNATTRIBUTED RESIDUAL — counted and
    returned, never hidden.

    ★ SURFACE NEUTRALITY.  Both loops use ``setdefault``, never ``=``.
    A node ``_seam_spine_anchors`` pins may ALREADY carry a class (it
    picks the nearest spine node within 30 m of a seam crossing without
    testing hardness, and that node is often already ``rwy_profile`` /
    ``seam_pin`` / ``seat_on_spine``).  The blanket never relabelled such
    a node, and neither may this: ``seam_spine_anchor`` sits in the
    solve's CROWN-FREEZE set, so an overwrite would move nodes into or
    out of that set and MOVE EMITTED ELEVATIONS.  ``setdefault`` makes
    the membership byte-identical to the blanket's.

    Returns ``{"pinned": …, "attributed": …, "pre_classified": …,
    "unattributed": …}`` — counts only, no verdict.
    """
    n_attributed = 0
    for i in pinned_idx:
        if i not in hard_cat:
            hard_cat[i] = "seam_spine_anchor"
            n_attributed += 1
    n_unattributed = 0
    for i in truth_hard:
        if i not in hard_cat:
            hard_cat[i] = "seam_spine_anchor"
            n_unattributed += 1
    return {"pinned": len(pinned_idx),
            "attributed": n_attributed,
            "pre_classified": len(pinned_idx) - n_attributed,
            "unattributed": n_unattributed}


def _seam_spine_anchors(layout, G, spine_adj, elev, base_hard,
                        dem, tile_lat, tile_lon, cut_lines):
    """Pin the nearest SPINE node to each taxi-centerline × tile-seam crossing at
    the SMOOTHED seam DEM (HARD), so ``_solve_spine_profile`` grades the route
    DOWN to the seam over the centerline length instead of leaving the spine at
    the plateau level (the SPLP tile-77 seam: spine stuck ~74.6, seam 72.2 → the
    apron body cliffed).

    PUBLISHES what it pinned (cycle-7.5 instrument sweep): returns the SET
    of node indices and stashes it on ``layout._seam_spine_anchor_idx``.
    It used to return a COUNT that the call site discarded, so the only
    record that this channel had hardened anything was the downstream
    blanket label — see :func:`attribute_seam_spine_hardening`."""
    from shapely.geometry import Point          # noqa: F401  (geom predicates)
    from auto_patch.elevation import _sample_dem
    n = len(elev)
    seen: set = set()
    layout._seam_spine_anchor_idx = seen
    spine_pts = [(i, G.pos[i]) for i in spine_adj if i in G.pos and i < n]
    if not spine_pts:
        return seen
    for entry in (getattr(layout, "apt_taxi_centerlines", []) or []):
        ln = entry.line if hasattr(entry, "line") else (entry[0] if isinstance(entry, (tuple, list)) else entry)
        if ln is None or ln.is_empty:
            continue
        for cut in cut_lines:
            try:
                inter = ln.intersection(cut)
            except Exception:                              # pragma: no cover
                continue
            if inter.is_empty:
                continue
            pts = ([inter] if inter.geom_type == "Point"
                   else [g for g in getattr(inter, "geoms", [])
                         if g.geom_type == "Point"])
            for p in pts:
                bi, (bx, by) = min(
                    spine_pts,
                    key=lambda t: (t[1][0] - p.x) ** 2 + (t[1][1] - p.y) ** 2)
                if bi in seen or (bx - p.x) ** 2 + (by - p.y) ** 2 > 30.0 ** 2:
                    continue
                lat, lon = layout.m_to_ll(bx, by)
                v = _sample_dem(dem, tile_lat, tile_lon, lat, lon)
                if v is None or v != v:
                    continue
                elev[bi] = float(v)
                base_hard[bi] = True
                seen.add(bi)
    return seen


def _build_spine_corridors(spine_adj, nodes_xy):
    """The spine CORRIDOR decomposition — maximal degree-2 runs of the
    spine graph, spliced through welds that continue near-straight-on.

    Extracted verbatim from ``_fair_spine_chains`` (taut-string spec §6,
    2026-07-28) so the FAIRING and the STRINGING operate on the SAME
    corridors: the string's objective and the K-factor's rounding must
    agree on where a route begins and ends, or the fairing re-introduces
    the very bends the string placed at witnessed wall contacts.  The
    extraction is behavior-preserving for fairing (same chains, same
    order) — ``tests/test_spine_fair_through_welds.py`` is the guard.

    Returns the list of chains (node-index lists, length >= 3)."""
    import math
    deg = {i: len(lst) for i, lst in spine_adj.items()}
    visited_edges: set = set()
    chains = []
    for start, lst in spine_adj.items():
        if deg.get(start, 0) == 2:
            continue                       # chains start at break nodes
        for (j, _w) in lst:
            e = (start, j) if start < j else (j, start)
            if e in visited_edges:
                continue
            visited_edges.add(e)
            chain = [start, j]
            prev, cur = start, j
            while deg.get(cur, 0) == 2:
                nxt = [k for (k, _w2) in spine_adj[cur] if k != prev]
                if not nxt:
                    break
                nxt = nxt[0]
                e2 = (cur, nxt) if cur < nxt else (nxt, cur)
                if e2 in visited_edges:
                    break
                visited_edges.add(e2)
                chain.append(nxt)
                prev, cur = cur, nxt
            if len(chain) >= 3:
                chains.append(chain)
            elif len(chain) == 2:
                # Two-node stubs carry no fairable triple on their own,
                # but a through-weld SPLICE below can absorb them into a
                # longer chain (a short connector between two welds).
                chains.append(chain)

    # ── THROUGH-WELD SPLICE (owner defect 2026-07-27, HECA dip) ──────
    # Chains break at degree-≠2 nodes, so the K-factor was blind at
    # junction welds — the exact node a through-route inherits a
    # descending spine's value at (a solver-manufactured 10 m V under a
    # monotone DEM).  Splice chains whose terminal segments continue
    # near-straight through a weld, so the POCS pass fairs across it;
    # genuine turns (tees, corners) keep separate chains.
    from auto_patch.config import (SPINE_FAIR_THROUGH_WELDS,
                                   SPINE_FAIR_WELD_MAX_DEVIATION_DEG)
    if SPINE_FAIR_THROUGH_WELDS and chains:
        _cos_min = math.cos(math.radians(
            SPINE_FAIR_WELD_MAX_DEVIATION_DEG))

        def _end_dir(chain, at_start):
            # Unit vector of the terminal segment pointing INTO the
            # weld (i.e. along the walk direction toward the end).
            a, b = ((chain[1], chain[0]) if at_start
                    else (chain[-2], chain[-1]))
            (xa, ya), (xb, yb) = nodes_xy[a], nodes_xy[b]
            d = math.hypot(xb - xa, yb - ya)
            if d < 1e-9:
                return None
            return ((xb - xa) / d, (yb - ya) / d)

        # weld node -> [(chain_idx, at_start)]
        weld_ends: dict = {}
        for ci, c in enumerate(chains):
            for at_start, node in ((True, c[0]), (False, c[-1])):
                if deg.get(node, 0) != 2:
                    weld_ends.setdefault(node, []).append(
                        (ci, at_start))
        # Union-find over chain indices so multi-weld corridors merge
        # transitively without re-walking.
        parent = list(range(len(chains)))

        def _find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        splices: dict = {}     # (chain_root_end) merges recorded as pairs
        merges = []            # (ci, ai_start, cj, aj_start, weld)
        for weld, ends in weld_ends.items():
            if len(ends) < 2:
                continue
            # Greedy best-continuation pairing: the pair whose incoming
            # directions are most nearly OPPOSITE (straight-through).
            cand = []
            dirs = {}
            for (ci, at_start) in ends:
                v = _end_dir(chains[ci], at_start)
                if v is not None:
                    dirs[(ci, at_start)] = v
            items = list(dirs.items())
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    (ea, va), (eb, vb) = items[i], items[j]
                    if ea[0] == eb[0]:
                        continue      # never splice a chain to itself
                    # va, vb both point INTO the weld: straight-through
                    # means anti-parallel.
                    c = -(va[0] * vb[0] + va[1] * vb[1])
                    if c >= _cos_min:
                        cand.append((c, ea, eb))
            cand.sort(key=lambda t: -t[0])
            used = set()
            for _c, ea, eb in cand:
                if ea in used or eb in used:
                    continue
                if _find(ea[0]) == _find(eb[0]):
                    continue          # already one corridor (loop guard)
                used.add(ea)
                used.add(eb)
                merges.append((ea, eb, weld))
                parent[max(_find(ea[0]), _find(eb[0]))] = min(
                    _find(ea[0]), _find(eb[0]))
        if merges:
            # Assemble spliced node lists: join at the recorded weld,
            # orienting each member so the weld sits between them (the
            # weld node appears once in the result).  ``splices`` maps a
            # consumed chain index to its surviving container so later
            # merges resolve through prior ones.
            for ea, eb, weld in merges:
                ca = ea[0]
                while ca in splices:
                    ca = splices[ca]
                cb = eb[0]
                while cb in splices:
                    cb = splices[cb]
                if ca == cb:
                    continue
                la, lb = chains[ca], chains[cb]
                if not la or not lb:
                    continue
                if la[0] == weld:
                    la = la[::-1]
                if lb[-1] == weld:
                    lb = lb[::-1]
                if la[-1] != weld or lb[0] != weld:
                    continue          # a prior splice consumed this end
                chains[ca] = la + lb[1:]
                chains[cb] = []
                splices[cb] = ca
            chains = [c for c in chains if len(c) >= 3]
    else:
        chains = [c for c in chains if len(c) >= 3]
    return chains


def _build_taut_couple_adj(law_edges, members, wall_extra=()):
    """CROSS-CORRIDOR LAW COUPLING adjacency (spec §6 amendment
    2026-07-28, the measured blocker).

    Two corridors crossing one junction WITHOUT a shared spine node string
    to mutually-inconsistent values (KCLT: 0.2-0.4 m disagreements on
    3-8 m within-junction pairs → 1373 minted law-true violations once the
    hold froze them).  Both hold-boundary pre-legalise variants failed —
    the joint-graph one re-drags the corridor through body edges (2.6 s,
    corridor sag 0.22 → 2.58 m) and the strung-pair-scoped one misses the
    offenders and mints 4 % longitudinal steps instead.  The fix belongs
    at STRING TIME: an already-settled node imposes a MOVING WALL on a
    later-strung one, so crossing corridors come out cap-consistent BY
    CONSTRUCTION and the holds have nothing to mint.

    ``law_edges`` is an iterable of ``(a, b, budget)`` from the UNIFIED
    graph — the validator's own materialized pair set.  Deliberately NOT
    the shape-constraint entries: flat-airport junction all-pairs largely
    live in lazy-certified entries there, so filtering those would miss
    exactly the pairs this exists to couple.

    Kept: pairs with both endpoints in ``members | wall_extra`` and at
    least one in ``members`` — ``wall_extra`` carries the HARD spine nodes
    that are law neighbours of a corridor without lying on one (an
    off-corridor seat 2 m from a corridor still dictates a wall).

    Returns ``(adj, n_edges)`` with ``adj = {i: [(j, budget), ...]}``
    keyed only by ``members``."""
    adj: dict = {}
    walls = set(members)
    walls.update(wall_extra)
    n_edges = 0
    for (a, b, budget) in law_edges:
        if a not in walls or b not in walls:
            continue
        a_m = a in members
        b_m = b in members
        if not (a_m or b_m):
            continue
        n_edges += 1
        if a_m:
            adj.setdefault(a, []).append((b, budget))
        if b_m:
            adj.setdefault(b, []).append((a, budget))
    return adj, n_edges


def _spine_string_walls(i, node_band, spine_floor, frontage_ceil=None):
    """Taut-string tube walls for ONE spine node (spec §6 "per-corridor
    data"): the reach band ``node_band[i] = (floor, ceiling)`` — ``None``
    or off-list ⇒ ±inf (off-network nodes are unbounded; the exact cap
    projection stays the safety net) — with the floor RAISED by the
    building-frontage floor ``spine_floor[i]``, never above the ceiling
    (the ``min(f, hi)`` idiom the harmonic clamp already uses), and the
    ceiling LOWERED by the building-frontage CEILING ``frontage_ceil[i]``
    (owner mint-class closure 2026-07-28: the frontage pair law is
    SYMMETRIC — ``|z_i − seat| ≤ cap·d`` — but only its floor side ever
    existed because the harmonic dragged spines DOWN; the taut string
    LIFTS them, and an over-lifted spine mints unfixable 1 % frontage
    chords against pad-edge body nodes once held.  The mirror idiom
    ``max(fc, lo)`` keeps the ceiling from crossing the floor).

    Returns ``(floor, ceiling, ok)``; ``ok`` is False for a BAND-INVERTED
    node (floor > ceiling — quarantine territory), which SPLITS the
    corridor and keeps its current value."""
    INF = float("inf")
    lo, hi = -INF, INF
    if node_band is not None and i < len(node_band):
        b = node_band[i]
        if b is not None:
            lo, hi = b
    if lo > hi:
        return lo, hi, False
    if spine_floor:
        f = spine_floor.get(i)
        if f is not None and f > lo:
            lo = min(f, hi)
    if frontage_ceil:
        fc = frontage_ceil.get(i)
        if fc is not None and fc < hi:
            hi = max(fc, lo)
    return lo, hi, True


def _string_spine_corridors(elev, corridors, nodes_xy, node_band,
                            spine_floor, pegged, *, passes=2, apply=True,
                            couple_adj=None, frontage_ceil=None,
                            pieces_out=None):
    """Deterministic taut-string NETWORK SETTLE over the spine corridors
    (docs/specs/taut-string-spine-profile-spec.md §6).

    Per corridor: stations are the cumulative straight-line chord length,
    the tube is :func:`_spine_string_walls`, and the pegs are (a) every
    corridor node in ``pegged`` (the genuinely-pinned nodes — runway
    joins, seam pins, seats) at its CURRENT value, (b) every node an
    EARLIER corridor of this pass already strung — the crossing rule,
    "the crossing taxiway meets the through-taxiway's surface" — and (c)
    each free corridor endpoint at its current value clamped into its own
    walls (the provisional junction value).

    ``passes`` fixed sweeps (no convergence loop, spec §6: two).  Each
    sweep processes corridors LONGEST-FIRST (tie: smaller first-node
    index) and writes a corridor's values into ``elev`` immediately, so
    the crossing rule sees them.  A corridor/piece with fewer than two
    pegs strings to ``None`` and keeps its harmonic values.

    ``apply=False`` measures only (nothing is written): that is the §7
    witness — how far the LIVE profile sags below its re-derived string.

    ``couple_adj`` (spec §6 amendment) is the cross-corridor LAW COUPLING
    adjacency from :func:`_build_taut_couple_adj`: while settling, every
    already-settled or hard law-neighbour OFF the corridor imposes a
    moving wall, so crossing corridors are mutually cap-consistent by
    construction.  ``None`` disables it (walls are the reach band alone).

    ``pieces_out`` (spec §10 interval rod): a list that receives, for the
    LAST sweep, each STRUNG piece's node-index list (in corridor order).
    Pieces are already split at band-inverted nodes and zero-length
    stations, so consecutive pairs within one recorded piece are exactly
    the pairs the rod may couple — no interval edge ever crosses a split.

    Returns ``(n_corridors, n_strung, worst_resag, strung_nodes,
    n_inverted)``; ``worst_resag`` is the largest interior
    ``string − live`` deviation of the LAST sweep, clamped at 0, and
    ``n_inverted`` counts nodes whose coupling walls contradicted."""
    from .taut_string import string_with_pegs

    def _seg_len(a, b):
        (xa, ya), (xb, yb) = nodes_xy[a], nodes_xy[b]
        return _math.hypot(xa - xb, ya - yb)

    # Longest-first, tie-broken by the smaller first-node index — the
    # owner's model ("draw the longest straight line first"); the sort
    # key never touches the chain lists, so ordering is total.
    order = []
    for c in corridors:
        total = 0.0
        for t in range(len(c) - 1):
            total += _seg_len(c[t], c[t + 1])
        order.append((-total, c[0], c))
    order.sort(key=lambda t: (t[0], t[1]))

    n_strung = 0
    worst = 0.0
    n_inverted = 0
    strung_nodes: set = set()
    # SETTLED = nodes whose current value may impose a coupling wall.  It
    # accumulates ACROSS sweeps and is never reset: after sweep 1 every
    # corridor holds a settled value, so sweep 2 re-strings each corridor
    # against the FULL mutual walls (spec §6 amendment) instead of only
    # against the corridors that happened to precede it.
    settled: set = set()
    for _sweep in range(passes):
        strung: set = set()
        n_strung = 0
        worst = 0.0
        n_inverted = 0
        sweep_pieces: list = []
        for (_neg_total, _first, c) in order:
            k = len(c)
            stations = [0.0] * k
            acc = 0.0
            for t in range(1, k):
                acc += _seg_len(c[t - 1], c[t])
                stations[t] = acc
            # A corridor never walls ITSELF — its own nodes are the
            # variables being re-solved, not settled data.
            own = set(c)
            # Split into strung PIECES at band-inverted nodes (they keep
            # their value) and at any degenerate zero-length step (the
            # string needs strictly increasing stations).
            pieces = []
            cur: list = []
            for t in range(k):
                lo, hi, ok = _spine_string_walls(c[t], node_band,
                                                 spine_floor,
                                                 frontage_ceil)
                if ok and couple_adj is not None:
                    # MOVING WALLS (spec §6 amendment): every settled or
                    # hard law-neighbour off this corridor pins a slab
                    # [z_j − budget, z_j + budget] the string must honour,
                    # so the crossing pair is cap-consistent BY
                    # CONSTRUCTION and no later hold can mint it.
                    node_i = c[t]
                    for (j, budget) in couple_adj.get(node_i, ()):
                        if j in own:
                            continue
                        if not (j in pegged or j in settled
                                or j in strung):
                            continue
                        zj = elev[j]
                        if zj + budget < hi:
                            hi = zj + budget
                        if zj - budget > lo:
                            lo = zj - budget
                    if lo > hi:
                        # Contradictory neighbours (both-hard class).
                        # Collapse to the midpoint and keep the node in
                        # the corridor — unlike a band inversion this is
                        # NOT a quarantine signal, so it must not split
                        # the string.
                        mid = 0.5 * (lo + hi)
                        lo = hi = mid
                        n_inverted += 1
                if not ok:
                    if len(cur) >= 2:
                        pieces.append(cur)
                    cur = []
                    continue
                if cur and stations[t] - stations[cur[-1][0]] < 1e-6:
                    if len(cur) >= 2:
                        pieces.append(cur)
                    cur = []
                cur.append((t, lo, hi))
            if len(cur) >= 2:
                pieces.append(cur)
            corridor_strung = False
            for piece in pieces:
                st = [stations[t] for (t, _lo, _hi) in piece]
                fl = [lo for (_t, lo, _hi) in piece]
                ce = [hi for (_t, _lo, hi) in piece]
                pegs: dict = {}
                for m, (t, lo, hi) in enumerate(piece):
                    node = c[t]
                    if node in pegged or node in strung:
                        pegs[m] = float(elev[node])
                last_m = len(piece) - 1
                for m in (0, last_m):
                    if m in pegs:
                        continue
                    node = c[piece[m][0]]
                    v = float(elev[node])
                    lo, hi = piece[m][1], piece[m][2]
                    if v < lo:
                        v = lo
                    elif v > hi:
                        v = hi
                    pegs[m] = v
                out = string_with_pegs(st, fl, ce, pegs)
                if out is None:
                    continue          # < 2 pegs: keep harmonic values
                corridor_strung = True
                sweep_pieces.append([c[t] for (t, _lo, _hi) in piece])
                for m, (t, _lo, _hi) in enumerate(piece):
                    node = c[t]
                    d = out[m] - elev[node]
                    if 0 < m < last_m and d > worst:
                        worst = d
                    if node in pegged:
                        continue      # anchors are never overwritten
                    if apply:
                        elev[node] = out[m]
                        strung_nodes.add(node)
                    strung.add(node)
                    settled.add(node)
            if corridor_strung:
                n_strung += 1
    if pieces_out is not None:
        pieces_out.extend(sweep_pieces)
    return len(corridors), n_strung, worst, strung_nodes, n_inverted


def _fair_spine_chains(elev, spine_adj, anchors, node_band, nodes_xy,
                       k_rate, *, max_sweeps=FAIRING_MAX_SWEEPS_SPINE,
                       tol=1e-4):
    """FAIRING (user 2026-07-04, task 3): bound the grade CHANGE between
    consecutive spine segments along every chain —
    ``|g2 − g1| ≤ k_rate·(L1 + L2)/2`` — the taxiway vertical-curve
    K-factor analog (``config.TAXIWAY_MAX_GRADE_CHANGE_PER_M`` =
    ``1 / config.TAXIWAY_CURVE_RUN_M``).  NOT TUNABLE: it is a LAW
    value and lives only as a config constant — the
    ``O4_TAXIWAY_CURVE_RUN_M`` env read is DELETED (docs/RULINGS.md
    2026-08-05, build-complete-then-debug).

    The grade law bounds only the FIRST derivative, so the spine solve
    tracks DEM noise in legal ±cap wiggles (the residual-waviness
    class); real grading is long linear/parabolic profiles.  This is a
    POCS pass on second-difference constraints: a too-sharp sag raises
    its centre vertex, a crest lowers it, split by segment stiffness
    (``δ/(1/L1 + 1/L2)``), clamped into the reach band.  Anchors
    (runway contacts, seam pins) never move — the curve fits BETWEEN
    them.  Chains are maximal degree-2 runs of the spine graph; the
    profile through a junction node (degree ≠ 2) is left to the
    junction's own solve.

    Mutates ``elev``; returns the number of triples still over the
    rate (honest residual — anchors can force a kink)."""
    import math
    # Chain building + through-weld splice live in
    # ``_build_spine_corridors`` (taut-string spec §6): the stringing
    # pass must fair and string the SAME corridors.  Behavior-preserving
    # extraction — same chains, same order.
    chains = _build_spine_corridors(spine_adj, nodes_xy)
    if not chains:
        return 0

    def _seg_len(a, b):
        (xa, ya), (xb, yb) = nodes_xy[a], nodes_xy[b]
        return math.hypot(xa - xb, ya - yb)

    chain_lens = [[_seg_len(c[k], c[k + 1]) for k in range(len(c) - 1)]
                  for c in chains]

    # ── CHORD-SAG FLOOR (owner defect 2026-07-27, HECA dip depth) ────
    # See ``config.SPINE_CHORD_MAX_SAG_M`` — the K-factor cannot bound a
    # long shallow bowl's DEPTH, only its curvature.  One-shot floor at
    # (chord − cap) before the sweeps; the POCS pass then re-fairs any
    # rate kinks the clamp introduces.  Band clamps still win.
    from auto_patch.config import SPINE_CHORD_MAX_SAG_M
    n_band = len(node_band) if node_band is not None else 0
    if SPINE_CHORD_MAX_SAG_M > 0.0:
        for c, lens in zip(chains, chain_lens):
            total = sum(lens)
            if total < 1.0:
                continue
            e0, e1 = elev[c[0]], elev[c[-1]]
            acc = 0.0
            for t in range(1, len(c) - 1):
                acc += lens[t - 1]
                b = c[t]
                if b in anchors:
                    continue
                chord = e0 + (e1 - e0) * (acc / total)
                floor = chord - SPINE_CHORD_MAX_SAG_M
                if elev[b] >= floor:
                    continue
                nb = floor
                band = node_band[b] if b < n_band else None
                if band is not None:
                    lo, hi = band
                    if lo <= hi:
                        nb = min(max(nb, lo), hi)
                if nb > elev[b]:
                    elev[b] = nb
    n_band = len(node_band) if node_band is not None else 0
    for _sweep in range(max_sweeps):
        worst_move = 0.0
        for c, lens in zip(chains, chain_lens):
            for t in range(1, len(c) - 1):
                b = c[t]
                if b in anchors:
                    continue
                l1 = lens[t - 1]
                l2 = lens[t]
                if l1 < 0.5 or l2 < 0.5:
                    continue
                a, d = c[t - 1], c[t + 1]
                g1 = (elev[b] - elev[a]) / l1
                g2 = (elev[d] - elev[b]) / l2
                dg = g2 - g1
                lim = k_rate * 0.5 * (l1 + l2)
                ex = abs(dg) - lim
                if ex <= 1e-6:
                    continue
                delta = math.copysign(ex, dg) / (1.0 / l1 + 1.0 / l2)
                nb = elev[b] + delta
                band = node_band[b] if b < n_band else None
                if band is not None:
                    lo, hi = band
                    if lo <= hi:
                        nb = min(max(nb, lo), hi)
                moved = abs(nb - elev[b])
                if moved:
                    elev[b] = nb
                    if moved > worst_move:
                        worst_move = moved
        if worst_move < tol:
            break
    # honest residual count (anchor- or band-forced kinks)
    n_over = 0
    for c, lens in zip(chains, chain_lens):
        for t in range(1, len(c) - 1):
            l1, l2 = lens[t - 1], lens[t]
            if l1 < 0.5 or l2 < 0.5:
                continue
            g1 = (elev[c[t]] - elev[c[t - 1]]) / l1
            g2 = (elev[c[t + 1]] - elev[c[t]]) / l2
            if abs(g2 - g1) - k_rate * 0.5 * (l1 + l2) > 1e-4:
                n_over += 1
    return n_over


def _fair_gap_spine_chains(elev, chains, k_rate, *,
                           max_sweeps=FAIRING_MAX_SWEEPS_GAP_SPINE,
                           tol=1e-4, frozen=None):
    """GAP-SPINE longitudinal fairing (Slice B stage B2, ratified
    2026-07-10): the ``_fair_spine_chains`` second-difference law —
    ``|g2 − g1| ≤ k_rate·(L1 + L2)/2`` (``TAXIWAY_MAX_GRADE_CHANGE_
    PER_M``, the taxiway vertical-curve K-factor analog) — applied to
    each gap-fill drainage-spine chain, with every centre-vertex move
    clamped INTO the node's envelope interval so smoothing never exits
    the law the interval edges enforce.  The interval is read at the
    CURRENT station elevations: ``[max over parents of (z_station +
    floor_offset), min over parents of (z_station + ceiling_offset)]``,
    ``None`` sides open; an EMPTY intersection falls back to the nearer
    (first) parent's own interval — the same composition rule the
    retired analytic valuation used (``gap_fill._spine_interval``).
    Spine ENDPOINTS never move (no triple centres them), matching the
    analytic smoother's pinned ends.  ``frozen`` (indexable of bool,
    e.g. ``base_hard``): HARD nodes never move either — a gap-spine
    vertex can weld onto a pavement node that is a runway-join anchor
    (the single hard anchor law: everything yields to it, including
    this smoother — KBNA 13/31: the fairing dragged an anchored join
    0.22 m below the crowned runway edge, user ruling 2026-07-16).

    ``chains``: ``solver_primitives._build_gap_spine_constraints``
    output — per chain the node indices (``None`` = unmapped, splits
    the chain into runs), coordinates, and resolved per-node specs
    ``[(station_index, floor_offset, ceiling_offset), ...]``.

    Mutates ``elev``; returns the number of triples still over the
    rate (honest residual — a tight envelope can force a kink)."""
    import math
    n_elev = len(elev)

    def _interval_at(spec):
        lo = None
        hi = None
        for (j, floor_off, ceil_off) in spec:
            if j is None or j >= n_elev:
                continue
            zj = elev[j]
            plo = None if floor_off is None else zj + floor_off
            phi = None if ceil_off is None else zj + ceil_off
            if plo is not None:
                lo = plo if lo is None else max(lo, plo)
            if phi is not None:
                hi = phi if hi is None else min(hi, phi)
        if lo is not None and hi is not None and lo > hi and spec:
            j, floor_off, ceil_off = spec[0]
            if j is not None and j < n_elev:
                zj = elev[j]
                lo = None if floor_off is None else zj + floor_off
                hi = None if ceil_off is None else zj + ceil_off
        return lo, hi

    n_over = 0
    for chain in chains:
        idx = chain["idx"]
        xy = chain["xy"]
        specs = chain["specs"]
        # Contiguous runs of mapped indices (an unmapped node splits
        # the chain — smoothness across a missing variable is unknown).
        runs: list[list[int]] = []
        cur: list[int] = []
        for pos, i in enumerate(idx):
            if i is None or i >= n_elev:
                if len(cur) >= 3:
                    runs.append(cur)
                cur = []
            else:
                cur.append(pos)
        if len(cur) >= 3:
            runs.append(cur)
        for run in runs:
            lens = [math.hypot(xy[run[k + 1]][0] - xy[run[k]][0],
                               xy[run[k + 1]][1] - xy[run[k]][1])
                    for k in range(len(run) - 1)]
            for _sweep in range(max_sweeps):
                worst_move = 0.0
                for t in range(1, len(run) - 1):
                    l1 = lens[t - 1]
                    l2 = lens[t]
                    if l1 < 0.5 or l2 < 0.5:
                        continue
                    a = idx[run[t - 1]]
                    b = idx[run[t]]
                    d = idx[run[t + 1]]
                    if frozen is not None and b < len(frozen) \
                            and frozen[b]:
                        continue        # hard node (anchor/seed): pinned
                    g1 = (elev[b] - elev[a]) / l1
                    g2 = (elev[d] - elev[b]) / l2
                    dg = g2 - g1
                    lim = k_rate * 0.5 * (l1 + l2)
                    ex = abs(dg) - lim
                    if ex <= 1e-6:
                        continue
                    delta = math.copysign(ex, dg) / (1.0 / l1 + 1.0 / l2)
                    nb = elev[b] + delta
                    lo, hi = _interval_at(specs[run[t]])
                    if lo is not None:
                        nb = max(nb, lo)
                    if hi is not None:
                        nb = min(nb, hi)
                    moved = abs(nb - elev[b])
                    if moved:
                        elev[b] = nb
                        if moved > worst_move:
                            worst_move = moved
                if worst_move < tol:
                    break
            for t in range(1, len(run) - 1):
                l1, l2 = lens[t - 1], lens[t]
                if l1 < 0.5 or l2 < 0.5:
                    continue
                g1 = (elev[idx[run[t]]] - elev[idx[run[t - 1]]]) / l1
                g2 = (elev[idx[run[t + 1]]] - elev[idx[run[t]]]) / l2
                if abs(g2 - g1) - k_rate * 0.5 * (l1 + l2) > 1e-4:
                    n_over += 1
    return n_over


def _fair_ring_edges(layout, elev, bucket_to_idx, anchors, node_band,
                     k_rate, *, max_bend_deg=25.0, min_seg_m=3.0,
                     max_sweeps=FAIRING_MAX_SWEEPS_CHAIN, tol=1e-4,
                     law_adjacency=None,
                     skip_nodes=None):
    """Second-difference fairing on STRAIGHT airside boundary runs (user
    2026-07-04, CYXY taxiway E edge): the ``_fair_spine_chains`` law
    covers spine chains only, so a corridor's ring EDGE still tracks DEM
    noise in legal ±cap sawtooth (±0.8 % grade alternation every 12 m).
    Same POCS: a too-sharp sag lifts its centre, a crest lowers it,
    stiffness-split, band-clamped, anchors fixed.  Ring CORNERS are real
    grade breaks — a triple only fairs when the boundary is straight
    through it (bend ≤ ``max_bend_deg``).  Runways/buildings excluded
    (own profile / flat).  Mutates ``elev``; returns residual kinks.

    ``law_adjacency`` (``{node: [(other, budget_m), …]}``) makes the pass
    LAW-GUARDED: every move is clamped into the interval the node's law
    edges allow around the CURRENT neighbour values, and a node already
    outside that interval (a projection-declared residual) or with an
    infeasible interval never moves.  Required when the caller runs this
    AFTER its last feasibility projection — the unguarded pass left
    junction MESH chords (pairs crossing between two ring runs, which no
    triple sees) a median 1.8 cm over budget (SPJC 2026-07-05, the
    43-pair cm-noise class).  ``None`` ⇒ unguarded (solve-time call: the
    final projection re-enforces every pair the fairing perturbs).

    ``skip_nodes`` (node indices, arc R slice R1) — FREE TERRAIN-LEAF
    nodes: a triple with ANY of its three members in this set is dropped.
    ``_SKIP_ROLES`` below is ROLE-keyed, but the runway-end regime
    carries TWO families on ONE role: the skirt FILL (hard pins — every
    triple centre is already an anchor, so the pass is inert on it) and
    the RESA CUT (free variables under one envelope edge).  The cut
    carries no within-shape grade rule
    (``ROLE_GRADE_LIMITS['runway_clearance']`` is ``None``) and no
    fairing BY DESIGN — and, MEASURED at CYXY, a cut-ring triple whose
    CENTRE is the pavement vertex its weld row shares with a junction
    dragged that pavement node 2.1 m, breaking the one-way
    host-authority property the whole absorption rests on.  Dropping on
    ANY member (not just the centre) is what kills that class while
    leaving every triple that exists WITHOUT the admission untouched:
    off-gate no cut vertex resolves to a free node, the set is empty and
    the pass is byte-identical."""
    import math as _math
    from auto_patch.layout import (ROLE_RUNWAY, ROLE_BUILDING,
                                   ROLE_BOUNDARY, ROLE_GROUNDSIDE_PAVEMENT)
    _SKIP_ROLES = {ROLE_RUNWAY, "runway_crossing", ROLE_BUILDING,
                   ROLE_BOUNDARY, ROLE_GROUNDSIDE_PAVEMENT,
                   "retaining_wall", "tunnel_ramp", "clearance",
                   "taxiway_clearance",
                   # Service roads are DEM-follow ramps with genuine
                   # grade breaks at mouths/portals whose weld pins are
                   # not in every caller's hard set — fairing them
                   # minted 0.2-0.9 m bumps against the welds (CYXY
                   # #201: 132 %).  The waviness law is an AIRCRAFT
                   # taxiway ride-quality rule; roads keep their ramps.
                   "service_road", "service_junction"}
    cps = layout.canonical_points
    n = len(elev)
    n_band = len(node_band) if node_band is not None else 0

    # Building pads are FLAT by ruling — fairing must never move a node
    # a pad ring OWNS, even when that node is encountered on a
    # NEIGHBOUR's ring (CYXY building9: fairing the adjacent junction
    # ring dragged the shared corner 0.16 m off the pad level; the pad
    # flat group ran BEFORE this pass and could not restore it).  Pad
    # ring nodes therefore join the anchor set for every caller.
    building_ring_nodes: set = set()
    for s in layout.shapes:
        if (s.role != ROLE_BUILDING or s.polygon is None
                or s.polygon.is_empty):
            continue
        try:
            for (x, y) in s.polygon.exterior.coords:
                i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
                if i is not None and i < n:
                    building_ring_nodes.add(i)
        except Exception:
            continue
    if building_ring_nodes:
        anchors = set(anchors or ()) | building_ring_nodes

    # ── Precompute fairable TRIPLES once (geometry never changes) —
    # the sweeps then run on plain tuples, no per-sweep geometry work.
    triples = []          # (a, b, d, l1, l2) — flat list, for the sweeps
    for s in layout.shapes:
        if s.role in _SKIP_ROLES or s.polygon is None \
                or s.polygon.is_empty or s.polygon.geom_type != "Polygon":
            continue
        coords = list(s.polygon.exterior.coords)
        if coords and coords[0] == coords[-1]:
            coords = coords[:-1]
        m = len(coords)
        if m < 4:
            continue
        idx = [bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
               for (x, y) in coords]
        for t in range(m):
            a, b, d = idx[(t - 1) % m], idx[t], idx[(t + 1) % m]
            if b is None or a is None or d is None:
                continue
            if b >= n or a >= n or d >= n or b in anchors:
                continue
            if skip_nodes and (b in skip_nodes or a in skip_nodes
                               or d in skip_nodes):
                continue          # free terrain leaf — no fairing law
            (xa, ya), (xb, yb) = coords[(t - 1) % m], coords[t]
            (xd, yd) = coords[(t + 1) % m]
            l1 = _math.hypot(xb - xa, yb - ya)
            l2 = _math.hypot(xd - xb, yd - yb)
            if l1 < min_seg_m or l2 < min_seg_m:
                continue
            dot = ((xb - xa) * (xd - xb)
                   + (yb - ya) * (yd - yb)) / (l1 * l2)
            if dot < _math.cos(_math.radians(max_bend_deg)):
                continue                      # corner — real grade break
            triples.append((a, b, d, l1, l2))

    if not triples:
        return 0

    # A direct straight-line fit per run was MEASURED and rejected
    # (2026-07-04, user suggestion): assigning the chord between run
    # endpoints (band-projected, small-move-guarded) reads smoother in
    # theory, but band clamps and cross-run neighbour pairs make the
    # chord not-quite-feasible in practice — CYXY within-shape rose
    # 182 → 237-256 for no visible gain over POCS-from-seed (the solved
    # seed is already near-linear; the POCS converges in a few cheap
    # sweeps on the precomputed triples).
    for _sweep in range(max_sweeps):
        worst = 0.0
        for (a, b, d, l1, l2) in triples:
            g1 = (elev[b] - elev[a]) / l1
            g2 = (elev[d] - elev[b]) / l2
            dg = g2 - g1
            lim = k_rate * 0.5 * (l1 + l2)
            ex = abs(dg) - lim
            if ex <= 1e-6:
                continue
            delta = _math.copysign(ex, dg) / (1.0 / l1 + 1.0 / l2)
            nb = elev[b] + delta
            band = node_band[b] if b < n_band else None
            if band is not None:
                lo, hi = band
                if lo <= hi:
                    nb = min(max(nb, lo), hi)
            if law_adjacency is not None:
                incident = law_adjacency.get(b)
                if incident:
                    law_low = law_high = None
                    for (other, budget) in incident:
                        if other >= n:
                            continue
                        other_value = elev[other]
                        low = other_value - budget
                        high = other_value + budget
                        if law_low is None or low > law_low:
                            law_low = low
                        if law_high is None or high < law_high:
                            law_high = high
                    if law_low is not None:
                        if (law_low > law_high
                                or not (law_low <= elev[b] <= law_high)):
                            continue    # infeasible / already-outside: never move
                        nb = min(max(nb, law_low), law_high)
            moved = abs(nb - elev[b])
            if moved:
                elev[b] = nb
                if moved > worst:
                    worst = moved
        if worst < tol:
            break
    n_over = 0
    for (a, b, d, l1, l2) in triples:
        g1 = (elev[b] - elev[a]) / l1
        g2 = (elev[d] - elev[b]) / l2
        if abs(g2 - g1) - k_rate * 0.5 * (l1 + l2) > 1e-4:
            n_over += 1
    return n_over


def _solve_spine_profile(elev, base_hard, spine_adj, spine_floor,
                         node_band=None, nodes_xy=None,
                         *, max_sweeps=FAIRING_MAX_SWEEPS_APRON, tol=1e-3,
                         curvature=0.25,
                         graph=None, probe_out=None, string_pins=None):
    """Dedicated SMOOTH spine solve on the unified graph's geometry nodes.

    Min-curvature (inverse-budget² harmonic mean blended with the plain mean),
    clamped into the neighbour cap slabs ``[z_j − budget, z_j + budget]``, the
    building-frontage floor, AND the per-node REACH BAND ``node_band[i] =
    (floor, ceiling)`` (user 2026-06-26) — so the spine is closest-DEM-FEASIBLE
    too: it can't sit BELOW its reachable floor (CYXY TX3 at 677 when its floor is
    ~685) nor above its ceiling.  Anchors = the nodes already HARD (runway
    contacts at their LOCAL runway elevation + tile seams).  Mutates ``elev`` in
    place; returns ``(frozen, rod_pieces)``: the set of spine node indices it
    solved (to be frozen for the body fill) and the strung corridor PIECES
    (node-index lists, splits respected) from which the caller derives the
    STRING-AS-LAW interval-rod edges (spec §10) at yield entry.  Gate off or
    no strung corridor ⇒ ``[]``."""
    import math
    INF = float("inf")
    # ── STAGE PROBE (P3 drag attribution; ``probe_out`` OUT-PARAMETER, the
    # same idiom as ``pieces_out`` below) ─────────────────────────────────
    # P3 asks WHICH stage of this function introduces the chord-1 sag, and
    # the answer is not derivable from the returned state alone.  When
    # ``probe_out`` is a dict it receives STAGE-LABELLED copies of ``elev``
    # at the five boundaries, plus the cross-corridor coupling adjacency.
    # ``None`` (every production call) ⇒ one identity test per stage and
    # nothing allocated.
    def _probe(stage: str) -> None:
        """Record a stage-labelled ``elev`` copy into ``probe_out``."""
        if probe_out is not None:
            probe_out.setdefault("elev_stages", []).append(
                (stage, list(elev)))

    # ── THE AIRSIDE PROFILE DOES NOT RIDE SERVICE EDGES (cycle 8, the
    # service-stringing round) ──────────────────────────────────────────
    # This pass is an AIRSIDE authority: a min-curvature harmonic over
    # ``spine_adj`` that WRITES values.  With the road network strung into
    # that graph (the D′ finisher), a service edge puts a groundside node
    # into an airside node's neighbour blend — groundside pulling airside,
    # which the standing law forbids and which measured as +2 airside rows
    # at KCLT 10 000 the moment the roads strung.  The same
    # ``service_spine_pairs`` exclusion the reach law already applies
    # (REACH_NO_SERVICE_SPINES) therefore applies here: the road chain is
    # dropped from THIS solve and its nodes are seated later, as receivers,
    # from the mouth band.  Direction, not deletion — every road pair is
    # still enforced as law in the partitioned projections.
    _svc_pairs_sp = getattr(graph, "service_spine_pairs", None) or ()
    if _svc_pairs_sp:
        _filtered = {}
        for _i, _lst in spine_adj.items():
            _keep = [(_j, _w) for (_j, _w) in _lst
                     if ((_i, _j) if _i < _j else (_j, _i)) not in
                     _svc_pairs_sp]
            if _keep:
                _filtered[_i] = _keep
        spine_adj = _filtered
    _probe("1_entry_dem_seeded")
    anchors = {i for i in spine_adj if i < len(base_hard) and base_hard[i]}
    # ── S1b: STRING PINS ARE DIRICHLET (spec §1 edit 2) ───────────────
    # They join the SAME ``anchors`` set the harmonic, the fairing and the
    # exact cap projection all key on — the solve's existing fixed-value
    # mechanism, no new constraint system.  That is what makes the pin
    # hold through ALL of phase A rather than only through the harmonic
    # (stages 4 and 5 would otherwise move it and G2 would fail by
    # construction).  HARD BEATS STRING: a vertex already anchored by law
    # keeps its law value and the conflict is counted by the caller.
    if string_pins:
        for _pv, _pz in string_pins.items():
            if _pv in anchors or _pv >= len(elev):
                continue
            elev[_pv] = float(_pz)
            anchors.add(_pv)
    nodes = [k for k in spine_adj if k < len(elev)]
    free = [k for k in nodes if k not in anchors]

    def _band(k):
        b = node_band[k] if (node_band is not None and k < len(node_band)) else None
        if b is None:
            return -INF, INF
        lo, hi = b
        return (lo, hi) if lo <= hi else (0.5 * (lo + hi), 0.5 * (lo + hi))

    # ── §5 LOUD MIDPOINT (seed-fix round; ungated, write-only) ────────
    # ``tgt = 0.5*(lo+hi)`` on an EMPTY interval (``lo > hi``) is the
    # silent shape ``feasibility-is-guaranteed`` forbids: the harmonic
    # cannot satisfy the constraints, so it splits the difference and
    # ships a value no law admits, with nothing said.  It becomes a NAMED
    # report — node, the empty interval, and the arg-max constraints that
    # produced each side.  The re-derivation runs ONLY on the empty-
    # interval branch (a rare event), so the hot sweep pays nothing; the
    # value written is unchanged, so this is byte-inert by construction.
    # Escalation to a build error waits until §2/§3 retire the known
    # minters (spec §5).
    _empty_interval: dict = {}

    def _empty_interval_sources(k, lo, hi):
        """Which constraint set each side of the empty interval — the
        band, a neighbour cap slab (with the neighbour), or the spine
        floor.  Re-derived from the same terms the sweep used."""
        b_lo, b_hi = _band(k)
        lo_src, lo_val = ("band_floor", b_lo)
        hi_src, hi_val = ("band_ceiling", b_hi)
        for (j, w) in spine_adj.get(k, ()):
            if elev[j] - w > lo_val:
                lo_src, lo_val = (f"cap_slab_from_{j}", elev[j] - w)
            if elev[j] + w < hi_val:
                hi_src, hi_val = (f"cap_slab_from_{j}", elev[j] + w)
        f = spine_floor.get(k)
        if f is not None and f > lo_val:
            lo_src, lo_val = ("spine_floor", f)
        return lo_src, hi_src

    # warm start free nodes onto their reach-band floor / serving floor (fill UP
    # out of a wrong-low DEM; the serving arm climbs to its pads).
    for k in free:
        bf, _bh = _band(k)
        f = spine_floor.get(k, -INF)
        target = max(bf, f)
        if target > -INF and target > elev[k]:
            elev[k] = target
    for _sweep_no in range(max_sweeps):
        moved = 0.0
        for k in free:
            nb = spine_adj.get(k, ())
            if not nb:
                continue
            sw = acc = 0.0
            for (j, w) in nb:
                wt = 1.0 / max(w, 1e-3) ** 2
                sw += wt
                acc += elev[j] * wt
            harm = acc / sw if sw > 0 else elev[k]
            pm = sum(elev[j] for (j, _w) in nb) / len(nb)
            tgt = (1.0 - curvature) * harm + curvature * pm
            lo, hi = _band(k)
            for (j, w) in nb:
                if elev[j] - w > lo:
                    lo = elev[j] - w
                if elev[j] + w < hi:
                    hi = elev[j] + w
            f = spine_floor.get(k)
            if f is not None and f > lo:
                lo = f
            if lo <= hi:
                tgt = min(max(tgt, lo), hi)
            else:
                # §5: EMPTY polytope — record before splitting it.
                row = _empty_interval.get(k)
                if row is None:
                    lo_src, hi_src = _empty_interval_sources(k, lo, hi)
                    _empty_interval[k] = {
                        "node": k, "first_sweep": _sweep_no, "hits": 1,
                        "lo": float(lo), "hi": float(hi),
                        "deficit_m": float(lo - hi),
                        "lo_source": lo_src, "hi_source": hi_src}
                else:
                    row["hits"] += 1
                    if lo - hi > row["deficit_m"]:
                        lo_src, hi_src = _empty_interval_sources(k, lo, hi)
                        row.update(lo=float(lo), hi=float(hi),
                                   deficit_m=float(lo - hi),
                                   lo_source=lo_src, hi_source=hi_src)
                tgt = 0.5 * (lo + hi)
            d = tgt - elev[k]
            if d:
                elev[k] = tgt
                if abs(d) > moved:
                    moved = abs(d)
        if moved < tol:
            break
    if _empty_interval:
        # §5 report.  ``feasibility-is-guaranteed``: an empty polytope at a
        # free corridor node is a LAW DEFECT to attribute — a wrong metric,
        # a wrong anchor value, a wrong role/cap or a false topology — and
        # the midpoint it ships is a value no constraint admits.
        _rows = sorted(_empty_interval.values(),
                       key=lambda r: -r["deficit_m"])
        _material = [r for r in _rows if r["deficit_m"] > 0.01]
        try:
            import O4_UI_Utils as _UI_ei
            _UI_ei.vprint(
                1,
                f"  [empty-interval] phase-A harmonic split an EMPTY "
                f"polytope at {len(_rows)} node(s) "
                f"({len(_material)} by >0.01 m) — the midpoint of an "
                f"empty interval satisfies NOTHING; attribute the "
                f"binding pair.")
            for r in _rows[:10]:
                _UI_ei.vprint(
                    1,
                    f"  [empty-interval]   node {r['node']}: "
                    f"lo {r['lo']:.3f} ({r['lo_source']}) > hi "
                    f"{r['hi']:.3f} ({r['hi_source']}) by "
                    f"{r['deficit_m']:.4f} m, first at sweep "
                    f"{r['first_sweep']}, {r['hits']} hit(s).")
        except Exception:                                  # pragma: no cover
            pass
    if probe_out is not None:
        probe_out["empty_intervals"] = sorted(
            _empty_interval.values(), key=lambda r: -r["deficit_m"])
    _probe("2_after_harmonic_min_curvature")
    # ── PHASE-A TAUT-STRING PASS (docs/specs/taut-string-spine-profile-
    # spec.md §5 step 2 + §6, owner ruling 2026-07-28) ───────────────
    # The harmonic above minimises CURVATURE and has NO altitude
    # preference, so where the network descends it interpolates a
    # corridor toward that descent and parks it metres under its own
    # lawful ceiling (HECA: 6.3 m below the ceiling, 5.5 m below DEM,
    # spec §1 — the dip is not law-forced; the straight chord fits).
    # The taut string is the shortest path in (station, z) through the
    # feasible tube: symmetric, so it also stops the profile rising more
    # than needed, and every bend has a witnessed wall contact.  The
    # harmonic result stays as the junction seed, the peg values for
    # free corridor endpoints, and the fallback for unstrung nodes.
    # Runs BEFORE the fairing, which then rounds the string's few bends
    # instead of rescuing a wiggly field.  ``nodes_xy is None`` ⇒ no
    # geometry ⇒ no stations ⇒ the pass is skipped entirely.
    from auto_patch.config import SPINE_TAUT_STRING as _TAUT_ON
    _rod_pieces: list = []
    if _TAUT_ON and nodes_xy is not None:
        _t_string = _time.perf_counter()
        _corridors = _build_spine_corridors(spine_adj, nodes_xy)
        # CROSS-CORRIDOR LAW COUPLING (spec §6 amendment): the unified
        # graph's own pair set, filtered to corridor members (+ the hard
        # spine nodes that neighbour one), becomes moving walls during the
        # settle.  Built from ``graph.edges`` — materialized, unlike the
        # shape-constraint entries whose junction all-pairs are lazily
        # certified on flat airports.
        _couple_adj = None
        _n_couple = 0
        if graph is not None:
            _members = {i for c in _corridors for i in c}
            from auto_patch import grade_graph as _GG_c
            _law = []
            for (_a, _b, _cap, _sp) in graph.edges:
                _pa = graph.pos.get(_a)
                _pb = graph.pos.get(_b)
                if _pa is None or _pb is None:
                    continue
                _law.append((_a, _b, _cap.at(_GG_c._dist(_pa, _pb), 0.0)))
            _couple_adj, _n_couple = _build_taut_couple_adj(
                _law, _members, anchors)
        if probe_out is not None:
            probe_out["couple_adj"] = {
                int(_ci): [(int(_cj), float(_cb)) for (_cj, _cb) in _clst]
                for _ci, _clst in (_couple_adj or {}).items()}
            probe_out["n_couple"] = int(_n_couple)
        _t_couple = _time.perf_counter()
        _n_corr, _n_strung, _worst, _, _n_inv = _string_spine_corridors(
            elev, _corridors, nodes_xy, node_band, spine_floor, anchors,
            couple_adj=_couple_adj, pieces_out=_rod_pieces)
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [taut-string] phase-A corridors={_n_corr} "
                  f"strung={_n_strung} lift worst={_worst:.2f}m "
                  f"coupled={_n_couple} inverted={_n_inv} "
                  f"(couple={_t_couple - _t_string:.3f}s "
                  f"string={_time.perf_counter() - _t_couple:.3f}s)")
    # Recorded whether or not the taut pass ran, so the stage list is
    # always the same five labels.
    _probe("3_after_taut_string")
    # FAIRING (task 3): bound the grade CHANGE along every spine chain by
    # the taxiway vertical-curve rate — runs after the harmonic solve
    # (which minimises grade, not grade CHANGE, so it still tracks DEM
    # noise in legal ±cap wiggles) and before the exact cap projection.
    if nodes_xy is not None:
        from auto_patch.config import TAXIWAY_MAX_GRADE_CHANGE_PER_M
        n_kink = _fair_spine_chains(elev, spine_adj, anchors, node_band,
                                    nodes_xy,
                                    TAXIWAY_MAX_GRADE_CHANGE_PER_M)
        if n_kink and _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [fairing] {n_kink} spine triple(s) over the "
                  f"vertical-curve rate after fairing (anchor/band-forced)")
    _probe("4_after_fairing")

    # Final EXACT cap-Lipschitz projection on the spine edges (only the runway/
    # seam anchors are hard) — the Gauss-Seidel's harmonic compromise can leave a
    # ~cap residual where several centerlines meet at a junction node; this drives
    # every free↔free spine pair ≤cap (a both-anchor pair stays = genuine step).
    from .one_solve import feasibility_project
    s_edges = []
    seen = set()
    for i, lst in spine_adj.items():
        for (j, w) in lst:
            e = (i, j) if i < j else (j, i)
            if e in seen:
                continue
            seen.add(e)
            s_edges.append((e[0], e[1], w))
    feasibility_project(elev, [{"edges": s_edges}], anchors)
    _probe("5_after_exact_cap_projection")
    # ``_rod_pieces`` (spec §10.1): the strung corridor pieces, returned
    # so the caller can derive the STRING-AS-LAW interval-rod edges.
    # The Δ snapshot is taken AT YIELD ENTRY, not here: between this
    # freeze and the first spine-yield projection every projection holds
    # the spine HARD, so a taxi corridor's values there ARE this faired
    # string byte-for-byte — but ``apply_service_road_dem_follow``
    # deliberately re-shapes SERVICE spines in between (roads follow
    # DEM ≤cap), and a rod derived HERE would freeze the pre-follow
    # shape and fight it (measured CYXY: 4 minted 8.95 % service pairs).
    return set(nodes), _rod_pieces


