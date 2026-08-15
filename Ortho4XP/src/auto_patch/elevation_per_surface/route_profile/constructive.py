"""THE CONSTRUCTIVE SOLVE CORE (mode ``constructive``; K1 lane).

Spec: ``docs/specs/constructive-solve-spec.md``.  The owner charter:
CONSTRUCT a lawful surface instead of optimizing toward one, beside the
iterative model behind ``solve_model`` (``auto_patch.solve_model``).  The
law is binary and thin (owner rulings 2026-08-14): caps, welds, crowns,
enclosed drainage spines, adjacent-ground slopes, seam continuity — DEM
deviation is not reported or considered, FLAT is lawful, terraces between
features are free.

This module is ONLY the value-selection core.  Everything around it is the
one shared frame ``solve_route_profile`` builds for BOTH models: node list,
seeds, runway/CIFP/seam/EAT anchors, the one unified graph, the reach band,
the building seats and floors, the crown/writeback/publication tail.
Flipping the mode changes only what happens between the anchor assembly and
the tail — the mode-isolation acceptance gate (an iterative build must stay
byte-identical) depends on that.

The model (spec C1-C3):

C1  RUNWAY SPINES + HARD TIES ARE THE ANCHORS.  The runway FAA profiles
    (CIFP thresholds → regrade → redistribute — the existing 1-D lawful
    profile construction), the seam pins, the EAT pins and the stamped
    building seats all arrive in ``base_hard`` / ``elev`` from the shared
    assembly.  They are immutable here; the crown stays the shared
    writeback transform (C4).

C2  ONE PROPAGATION.  A single multi-source cap-bounded envelope
    (``one_solve.reach_envelope`` — the projection's own cap-Lipschitz
    Dijkstra, module-level) from all admitted anchors over the joint law
    graph (``shape_constraints`` + the unified surface pairs).  Every free
    node takes the DETERMINISTIC midpoint of its feasible interval
    (envelope ∩ reach band ∩ spine floors); the midpoint of two
    cap-Lipschitz envelopes is cap-Lipschitz, so every embedded pair is
    lawful BY CONSTRUCTION.  Then AT MOST ONE smoothing sweep that
    provably moves only within intervals (each move is clamped into the
    node's current neighbour-slack ∩ envelope interval, which contains its
    current value — lawfulness is invariant).  An EMPTY interval is a
    REPORTED feasibility finding (feasibility-is-guaranteed; a STOP class
    at a real airport), never a silent clamp into one authority.

C3  CERTIFIED INTERIORS.  Shapes the flatness certificate proved lawful at
    their DEM seed (the still-``lazy_expand`` entries — pair generation
    skipped by the EXISTING lazy tier) are constructively CHOSEN flat at
    that seed: their nodes are pins, the certificate stays valid, and the
    skipped pair law stays skipped — the certified tier is ridden, not
    forked.  Larger uncertified interiors take the midpoint field, which
    is the low-order envelope midsurface welded to the rims by the same
    pair law as everything else.

Groundside (airside-is-king): groundside pieces, service roads and
detached pads are valued AFTER the airside selection by the SAME
constructive law passes the iterative core uses —
``apply_groundside_reach`` (reach level from the solved mouth, clamped
toward DEM), ``apply_service_road_dem_follow`` and
``seat_detached_pads_by_law`` — so groundside conforms and never pulls.

Witness admission is the standing law: route-metric admission
(``reach follows centerlines``) removes non-route anchors from the
envelope seed set; their own values and law edges still bind.
"""
from __future__ import annotations

import math as _math
import os as _os
import time as _time
from types import SimpleNamespace

#: Tolerance for "empty" intervals and the exit tally, matching the
#: projection's own sweep tolerance frame (``feasibility_project`` tol).
_EMPTY_TOL = 1e-6
_TALLY_TOL = 1e-3


def certified_pins(shape_constraints, base_hard, n):
    """C3: the node set the constructor pins at its certified seed —
    every node a still-``lazy_expand`` entry names (deferred body via
    ``lazy_nodes`` AND the ring nodes its eager edges reference), minus
    anything already hard.  Returns ``(pins, n_lazy_entries)``.

    The whole shape is pinned because the body↔ring chords are exactly
    the pairs the certified tier skipped: a ring that drifted off the
    certified seed would face the census on pairs no projection priced.
    Pinning keeps the certificate's own premise true (the shape sits at
    its flat seed) — the lazy tier is ridden, never expanded.
    """
    pins: set = set()
    n_lazy = 0
    for sc in shape_constraints:
        if sc.get("lazy_expand") is None:
            continue
        n_lazy += 1
        for i in (sc.get("lazy_nodes") or ()):
            if i < n and not base_hard[i]:
                pins.add(i)
        for edge in sc.get("edges", ()):
            for i in (edge[0], edge[1]):
                if i < n and not base_hard[i]:
                    pins.add(i)
    return pins, n_lazy


def smooth_once(elev, n, *, movable, sym_adj, interval_of):
    """AT MOST ONE in-interval smoothing sweep (spec C2, pre-delegated).

    Sequential (Gauss-Seidel) in index order: each movable node moves to
    the mean of its symmetric-law neighbours, clamped into
    ``[max(interval.lo, max_j(z_j − lim_j)), min(interval.hi,
    min_j(z_j + lim_j))]`` read at the CURRENT values.  Because the
    node's current value is always inside that clamp interval whenever
    the field is edge-lawful, the sweep PRESERVES pairwise lawfulness
    and envelope containment as loop invariants — the containment twin
    (``tests/test_constructive_solve.py``) asserts both.  A node whose
    clamp interval is empty (an already-reported infeasibility) is left
    untouched, never forced.  Returns the number of nodes moved.
    """
    n_moved = 0
    for i in range(n):
        if not movable(i):
            continue
        neigh = sym_adj.get(i)
        if not neigh:
            continue
        lo, hi = interval_of(i)
        s_lo = -_math.inf if lo is None else float(lo)
        s_hi = _math.inf if hi is None else float(hi)
        tot = 0.0
        for (j, lim) in neigh:
            zj = float(elev[j])
            tot += zj
            s_lo = max(s_lo, zj - lim)
            s_hi = min(s_hi, zj + lim)
        if s_lo > s_hi:
            continue
        target = tot / len(neigh)
        new = min(max(target, s_lo), s_hi)
        if new != elev[i]:
            elev[i] = new
            n_moved += 1
    return n_moved


def _interval_of(i, ceil, floor, node_band, u_spine_floor):
    """The feasible interval ``(lo, hi)`` for node ``i`` — envelope ∩ reach
    band ∩ spine floor; ``None`` side = unbounded."""
    lo = floor.get(i)
    hi = ceil.get(i)
    nb = node_band[i] if (node_band is not None
                          and i < len(node_band)) else None
    if nb is not None:
        b_lo, b_hi = float(nb[0]), float(nb[1])
        lo = b_lo if lo is None else max(lo, b_lo)
        hi = b_hi if hi is None else min(hi, b_hi)
    sf = u_spine_floor.get(i)
    if sf is not None:
        lo = float(sf) if lo is None else max(lo, float(sf))
    return lo, hi


def constructive_core(*, layout, icao, elev, base_hard, nodes,
                      bucket_to_idx, n, dem_elev, runway_nodes,
                      shape_constraints, G, u_spine_adj_airside,
                      u_spine_floor, node_band, building_seats,
                      hard_cat, near_miss_edges, u_pair_stage,
                      detached_pads, pad_frontage, seam_pin_idx,
                      gap_spine_chains, zone_idx, resa_idx,
                      terrain_first, iyf) -> SimpleNamespace:
    """Run the constructive selection.  Mutates ``elev`` (and, through the
    shared groundside law passes, ``layout``/``building_seats``) in place;
    returns the locals the shared publication tail reads."""
    import O4_UI_Utils as UI
    from auto_patch import grade_graph as _GG
    from auto_patch.progress import substep as _psub
    from .one_solve import (envelope_radj, law_edge_limits, reach_envelope,
                            shape_constraints_edges)
    # The stage/witness/report helpers are module-level in ``solve`` —
    # imported lazily HERE (this module is imported from ``solve``).
    from .solve import (_non_route_witness_nodes, _report_witness_admission,
                        _route_witness_admission, _unified_entries,
                        _fair_gap_spine_chains)

    t0 = _time.time()

    # ── C1: the anchor set (all immutable) ───────────────────────────
    hard = {i for i in range(n) if base_hard[i]}
    hard |= {i for i in runway_nodes if i < n}

    # C3: certified-lazy entries — pair generation skipped by the lazy
    # tier; the constructor CHOOSES their certified seed (flat is
    # lawful), keeping the certificate valid and the tier ridden.
    cert_pins, n_lazy_entries = certified_pins(
        shape_constraints, base_hard, n)

    # ── the unified surface pairs (the validator's own edge set), built
    # exactly as the iterative core builds them ──────────────────────
    u_edges = [(a, b, cap.at(_GG._dist(G.pos.get(a), G.pos.get(b)), 0.0))
               for (a, b, cap, _sp) in G.edges
               if a in G.pos and b in G.pos]
    u_family_of = G.family_by_pair()
    for _pk, _st in G.stage_by_pair().items():
        u_pair_stage.setdefault(_pk, _st)
    u_edges.extend(near_miss_edges)
    from auto_patch.lateral_spine_nodes import (
        lateral_xsection_law_edges as _xsec_edges)
    _xsec = _xsec_edges(layout, bucket_to_idx, stage_out=u_pair_stage)
    if _xsec:
        u_edges.extend(_xsec)
        UI.vprint(1, f"  [xsection-law] {len(_xsec)} priced "
                     f"cross-section pair(s) BOUND in the solve "
                     f"(|dz| <= cT*width)")
    from .apron_terrace import apply_fan_ramp_caps_to_edges as _apply_fan_u
    u_edges, _n_u_fan = _apply_fan_u(
        getattr(layout, "_fan_ramp_plan", None), u_edges, nodes)

    # ── witness admission (standing route-metric law) ────────────────
    from .one_solve import route_metric_envelope_enabled
    _rm_roles, _rm_route_roles, route_excluded = (
        _route_witness_admission(layout, bucket_to_idx, n))
    if route_metric_envelope_enabled():
        _rm_excl, _rm_rep = _non_route_witness_nodes(
            _rm_roles, _rm_route_roles, hard, n, provenance=hard_cat)
        route_excluded |= _rm_excl
        _report_witness_admission(icao, "constructive", _rm_rep)
    else:                                              # pragma: no cover
        route_excluded = set()

    # ── C2: ONE multi-source cap-bounded envelope over the joint law ─
    joint = list(shape_constraints) + _unified_entries(
        u_edges, u_pair_stage, "constructive/envelope")
    edge_lim, interval_lim, env_skip = law_edge_limits(
        joint, n, include_flat_pairs=True)
    ceil_radj, floor_radj = envelope_radj(
        edge_lim, interval_lim, env_skip, interval_yield_from=iyf)
    leaf_from = iyf if (zone_idx or resa_idx) else None
    seeds = [i for i in sorted(hard | cert_pins)
             if i not in route_excluded
             and (leaf_from is None or i < leaf_from)]
    ceil, _cdist = reach_envelope(+1, ceil_radj, seeds, elev, n)
    floor, _fdist = reach_envelope(-1, floor_radj, seeds, elev, n)
    _psub(0.62, "Solving elevations — constructive envelope propagated")

    # ── deterministic selection: the interval midpoint ───────────────
    immovable = hard | cert_pins
    empty_rows: list = []
    solve_broken_idx: set = set()
    n_free = 0
    n_unlabeled = 0
    for i in range(n):
        if i in immovable:
            continue
        if leaf_from is not None and i >= leaf_from:
            continue                      # terrain leaf — valued below
        lo, hi = _interval_of(i, ceil, floor, node_band, u_spine_floor)
        if lo is None and hi is None:
            n_unlabeled += 1              # off-graph: keeps its DEM seed
            continue
        if lo is None:
            # One-sided interval: the deterministic selection is the
            # node's own seed clamped under the bound — FLAT/at-seed is
            # lawful and the midpoint of a half-line is undefined.
            if elev[i] > hi:
                elev[i] = float(hi)
            n_free += 1
            continue
        if hi is None:
            if elev[i] < lo:
                elev[i] = float(lo)
            n_free += 1
            continue
        if lo > hi + _EMPTY_TOL:
            # REPORTED feasibility finding — never a silent clamp.  The
            # symmetric midpoint of the crossed bounds is the recorded,
            # deterministic least-max-deficit selection; the finding is
            # the product (feasibility-is-guaranteed: the anchors, not
            # this node, own the defect).
            empty_rows.append((i, float(lo), float(hi),
                               float(lo - hi)))
            solve_broken_idx.add(i)
        elev[i] = 0.5 * (float(lo) + float(hi))
        n_free += 1

    # ── at most ONE in-interval smoothing sweep (``smooth_once``) ────
    # Interval-edge endpoints do not move here (a symmetric surrogate
    # could exit a signed slab).
    sym_adj: dict = {}
    for (i, j), lim in edge_lim.items():
        sym_adj.setdefault(i, []).append((j, lim))
        sym_adj.setdefault(j, []).append((i, lim))
    interval_locked = set()
    for (i, j) in interval_lim:
        interval_locked.add(i)
        interval_locked.add(j)

    def _movable(i):
        return (i not in immovable and i not in interval_locked
                and (leaf_from is None or i < leaf_from))

    n_smoothed = smooth_once(
        elev, n, movable=_movable, sym_adj=sym_adj,
        interval_of=lambda i: _interval_of(i, ceil, floor, node_band,
                                           u_spine_floor))
    _psub(0.72, "Solving elevations — constructive selection smoothed")

    # ── terrain leaves: host-authoritative slab valuation ────────────
    # Zone rows / RESA cut rows are envelope LEAVES (the standing
    # host-authoritative law): each takes its own DEM seed clamped into
    # its slab(s) against the SOLVED host — the analytic band law
    # verbatim, exact and deterministic.  (The shared writeback tail
    # re-derives the emitted zone/RESA values on the crowned surface;
    # this keeps the solve-state consistent for every reader between.)
    n_leaves = 0
    if leaf_from is not None:
        leaf_bounds: dict = {}
        for (i, j), (low, high) in interval_lim.items():
            # slab is low <= z_i − z_j <= high
            i_leaf = i >= leaf_from
            j_leaf = j >= leaf_from
            if i_leaf == j_leaf:
                continue
            if i_leaf:
                b_lo = None if low is None else float(elev[j]) + low
                b_hi = None if high is None else float(elev[j]) + high
                k = i
            else:
                b_lo = (None if high is None
                        else float(elev[i]) - high)
                b_hi = (None if low is None
                        else float(elev[i]) - low)
                k = j
            cur = leaf_bounds.get(k)
            if cur is None:
                leaf_bounds[k] = (b_lo, b_hi)
            else:
                c_lo, c_hi = cur
                leaf_bounds[k] = (
                    b_lo if c_lo is None else
                    (c_lo if b_lo is None else max(c_lo, b_lo)),
                    b_hi if c_hi is None else
                    (c_hi if b_hi is None else min(c_hi, b_hi)))
        for k in sorted(leaf_bounds):
            if k >= n or k in immovable:
                continue
            b_lo, b_hi = leaf_bounds[k]
            v = float(elev[k])            # the DEM seed
            if b_lo is not None and v < b_lo:
                v = b_lo
            if b_hi is not None and v > b_hi:
                v = b_hi
            elev[k] = v
            n_leaves += 1

    # ── gap-fill drainage spines: the longitudinal law ───────────────
    # (Enclosed-area water escape stays law — owner 2026-08-14 drainage
    # scope.)  The shared second-difference fairing, every move clamped
    # into the slab intervals at current station values.
    n_gap_kinks = 0
    if gap_spine_chains:
        from auto_patch.config import (
            TAXIWAY_MAX_GRADE_CHANGE_PER_M as _K_GAP)
        n_gap_kinks = _fair_gap_spine_chains(
            elev, gap_spine_chains, _K_GAP, frozen=base_hard)

    # ── groundside conforms (airside-is-king), by the SAME law passes ─
    from auto_patch.config import (GROUNDSIDE_MAX_GRADE,
                                   SERVICE_ROAD_MAX_GRADE)
    from .anchors import (apply_groundside_reach,
                          apply_service_road_dem_follow)
    from .anchors import seat_detached_pads_by_law
    _nrl, gs_hard = apply_groundside_reach(
        layout, bucket_to_idx, elev, SERVICE_ROAD_MAX_GRADE)
    _svc_moved = apply_service_road_dem_follow(
        layout, bucket_to_idx, elev, dem_elev, SERVICE_ROAD_MAX_GRADE,
        anchor_extra=gs_hard)
    if (_nrl or _svc_moved) and _os.environ.get("O4_STEP_DEBUG") == "1":
        print(f"  [groundside-reach] {icao}: re-levelled {_nrl} "
              f"groundside piece(s); pinned {len(gs_hard)} route "
              f"node(s); DEM-followed {len(_svc_moved)} service "
              f"node(s).")
    if detached_pads:
        _dp_seats, _dp_stats = seat_detached_pads_by_law(
            layout, bucket_to_idx, elev, detached_pads,
            GROUNDSIDE_MAX_GRADE,
            frontage_coupled=pad_frontage, node_band=node_band)
        building_seats.update(_dp_seats)
        if any(_dp_stats):
            UI.vprint(1,
                f"  [detached-pad] {_dp_stats[0]} pad(s) seated on a "
                f"solved groundside datum, {_dp_stats[1]} with no "
                f"resolvable host, {_dp_stats[2]} declared contact "
                f"conflict(s), {_dp_stats[3]} seated from the "
                f"route-graph band, {_dp_stats[4]} with no derivable "
                f"band, {_dp_stats[5]} split-level candidate(s).")
    _psub(0.88, "Solving elevations — groundside conformed")

    # ── the honest exit tally (raw law frame, both edge kinds) ───────
    rem = 0
    bh = 0
    yield_hard = hard | cert_pins
    for edge in shape_constraints_edges(joint):
        if len(edge) >= 4:
            i, j, low, high = edge[0], edge[1], edge[2], edge[3]
            if i >= n or j >= n or i == j:
                continue
            d = float(elev[i]) - float(elev[j])
            over = ((low is not None and d < low - _TALLY_TOL)
                    or (high is not None and d > high + _TALLY_TOL))
        else:
            i, j, lim = edge
            if lim is None or lim < 0 or i >= n or j >= n or i == j:
                continue
            over = abs(float(elev[i]) - float(elev[j])) > lim + _TALLY_TOL
        if over:
            rem += 1
            if i in yield_hard and j in yield_hard:
                bh += 1

    # ── the constructive report (+ the STOP-class finding, loud) ─────
    UI.vprint(1,
        f"  [constructive] {icao}: {len(seeds)} anchor seed(s) "
        f"({len(hard)} hard, {len(cert_pins)} certified pin(s) over "
        f"{n_lazy_entries} certified entr(ies), "
        f"{len(route_excluded)} witness-excluded), {n_free} node(s) "
        f"midpoint-selected, {n_smoothed} smoothed in-interval, "
        f"{n_unlabeled} off-graph at seed, {n_leaves} terrain "
        f"leaf(ves) slab-valued, {n_gap_kinks} gap-spine kink(s) "
        f"residual; exit tally {rem} edge(s) over cap ({bh} "
        f"both-hard).")
    layout._constructive_empty_intervals = [
        (int(i), float(lo), float(hi), float(d),
         tuple(layout.m_to_ll(*nodes[i])))
        for (i, lo, hi, d) in empty_rows]
    if empty_rows:
        UI.vprint(0,
            f"  [constructive] {icao}: STOP-CLASS FINDING — "
            f"{len(empty_rows)} EMPTY feasibility interval(s) at a "
            f"real airport (spec ``constructive-solve`` pre-registered "
            f"STOP; feasibility-is-guaranteed says the ANCHORS own "
            f"this).  Selected the deterministic midpoint of the "
            f"crossed bounds; every row recorded on "
            f"layout._constructive_empty_intervals.")
        for (i, lo, hi, d) in sorted(empty_rows,
                                     key=lambda r: -r[3])[:10]:
            _lat, _lon = layout.m_to_ll(*nodes[i])
            UI.vprint(0,
                f"  [constructive]   node {i} at {_lat:.6f},"
                f"{_lon:.6f}: floor {lo:.3f} > ceiling {hi:.3f} "
                f"(deficit {d:.3f} m)")

    if _os.environ.get("O4_STEP_DEBUG") == "1":
        print(f"    [constructive] core {_time.time() - t0:.2f} s")

    return SimpleNamespace(
        u_edges=u_edges, u_family_of=u_family_of, gs_hard=gs_hard,
        solve_broken_idx=solve_broken_idx, yield_hard=yield_hard,
        rem=rem, bh=bh, n_free=n_free,
        frozen=set(), spine_phase_a=None, spine_preserved=set(),
        spine_yield_idx=set(), mover=None, string_pins=None,
        summary={}, fairing_moved_keys=None, scoped_gate=False,
        svc_moved=_svc_moved)
