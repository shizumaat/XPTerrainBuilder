"""THE CONSTRUCTIVE SOLVE CORE (mode ``constructive``; K1b — the living
band).

Spec: ``docs/specs/constructive-solve-spec.md`` AMENDMENT 1 (owner
correction, 2026-08-14 — supersedes C1/C2's anchor model).  K1's attempt
2 proved the selection/certification tail and the mode gates and FAILED
census acceptance at HECA/CYXY by OVER-ANCHORING: whole runway profiles
frozen, derived minters admitted as hard without mutual validation —
14,104 crossed intervals at HECA in one 19.846 m pair-class.  The
correction, now the model:

A1  TRUE ANCHORS ONLY.  The CIFP runway thresholds
    (``layout._runway_redistributed_profiles[ref]['cifp_pins']``, the
    world-invariant pins carried verbatim) and the tile-seam pins
    (``layout._seam_pin_idx``).  Nothing else is hard before the band
    exists.  True anchors are physically real and mutually consistent
    by reality; a contradiction WITHIN this set is a DATA DEFECT (CIFP
    vs seam) — reported on ``layout._constructive_p0_defects``, never
    absorbed.

A2  THE BAND RUNS FIRST AND LIVES.  ``one_solve.LivingBand`` computes
    the cap-Lipschitz band over the one published law graph from the
    true anchors alone; every other value is minted IN PRIORITY ORDER,
    validated against the CURRENT band, and — when accepted — joins the
    anchor set and locally refines the band before the next mint
    validates.  Consistency holds by induction; every interval is
    non-empty by construction.  Order (stable canonical ids within each
    class):
      P0 true anchors
      P1 runway interiors — 1-D taut strings threaded through the band
         tube (``corridor_profile.solve_run_profile`` →
         ``string_with_pegs``; the CIFP thresholds are the ONLY pegs;
         flex emerges where the band narrows, which is the flex law's
         own definition; a crossing runway's pinch arrives through the
         band, not through a peg)
      P2 seam/DEM ties, seats, EAT pins (the demoted ``base_hard``
         populations, at their stamped values)
      P3 certified region fits (the still-lazy certified entries at
         their flat seeds)
      P4 remainder (midpoint selection).

A3  REFUSAL SEMANTICS (the anchor-placement law, executable).  A mint
    outside the current band is REFUSED and recorded with minter id,
    value, band [lo, hi], deficit and the two bounding anchors; the
    refused feature falls back to its non-anchored path (seat →
    yield-hard: the seat follows the solved surface; pad → y-bake;
    certified fit → smaller region; runway-interior station → free
    midpoint).  No law value is ever silently clamped.  These named
    refusals ARE the anchor-defect findings the round has been missing
    (``layout._constructive_refusals``).

A4  SOURCE TRACKING.  The band carries provenance — every node knows
    its floor-minter and ceiling-minter (``LivingBand.bounding``), so
    every refusal and residual finding names its pair.  Module-level in
    the shared band code (both modes' instrument).

A5  SINGLE PASS.  After minting, K1's landed selection stands: interval
    midpoint + at most one in-interval smoothing sweep
    (``smooth_once``).  No yielding projections exist in this mode.

DEMOTIONS this model makes explicit: the FAA runway profile values, the
runway-join anchor map, EAT pins, seats and the certified seeds are
MINTERS, not anchors — they hold only where the living band admits
them.  The reach band (``node_band``) is seeded from the FAA-profile
anchor values, so intersecting it here would re-admit the demoted
anchors through the back door; the constructive selection reads the
LIVING band instead (the groundside law passes below keep consuming
``node_band`` unchanged — stage B's standing law, untouched by this
round).

Everything around the minting is the one shared frame
``solve_route_profile`` builds for BOTH models; flipping the mode
changes only what happens between the anchor assembly and the tail —
the mode-isolation acceptance gate (an iterative build must stay
byte-identical) depends on that.

Groundside (airside-is-king): unchanged from K1 — groundside pieces,
service roads and detached pads are valued AFTER the airside selection
by the SAME constructive law passes the iterative core uses.

Witness admission is the standing law: route-metric admission removes
non-route anchors from the envelope SEED set; their own values and law
edges still bind (``LivingBand.add(..., seed=False)``).
"""
from __future__ import annotations

import math as _math
import os as _os
import time as _time
from types import SimpleNamespace

#: Tolerance for band-membership validation, the (structurally
#: impossible) empty-interval check and the exit tally, matching the
#: projection's own sweep tolerance frame (``feasibility_project`` tol).
_EMPTY_TOL = 1e-6
_TALLY_TOL = 1e-3

#: In-interval smoothing sweep budget (fixed; a zero-move sweep exits
#: early).  ``O4_CONSTRUCTIVE_SWEEPS`` overrides for measurement arms.
_SMOOTH_SWEEPS = int(_os.environ.get("O4_CONSTRUCTIVE_SWEEPS", "8"))

#: A CIFP threshold peg snaps to an existing runway ring station within
#: this along-axis distance; farther, it becomes its own (synthetic)
#: station.  Displaced thresholds are interior stations with no ring
#: corner, so the synthetic path is common, not exceptional.
_PEG_SNAP_M = 0.75

#: Along-axis station quantization (mm): two ring vertices closer than
#: this share one station and one minted value.
_STATION_QUANT = 3

#: P2 mint order WITHIN the class axis (spec A2: ties → seats → EAT
#: pins), ``(rank, node id)`` sorted — stable canonical ids within each
#: class.  Runway-derived leftovers (crossing interpolations, join
#: values the strings did not adjudicate) are profile ties.
_P2_CLASS_RANK = {
    "seam_pin": 0,                # a seam pin the P0 pass could not seat
    "seam_spine_anchor": 0,
    "rwy_flexed": 1,
    "rwy_join": 1,
    "rwy_profile": 1,
    "base_hard:unattributed": 2,
    "seat_on_spine": 3,
    "eat_pin": 4,
}
_P2_RANK_DEFAULT = 2


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

    K1b: the core no longer calls this wholesale — certified entries
    are P3 MINTERS, validated per node against the living band
    (:func:`certified_entry_nodes` is the per-entry spelling) — but the
    enumeration rule is THIS one, and the twin drives it here.
    """
    pins: set = set()
    n_lazy = 0
    for sc in shape_constraints:
        if sc.get("lazy_expand") is None:
            continue
        n_lazy += 1
        for i in certified_entry_nodes(sc, n):
            if not base_hard[i]:
                pins.add(i)
    return pins, n_lazy


def certified_entry_nodes(sc, n):
    """ONE certified entry's node set (body ``lazy_nodes`` + the ring
    nodes its eager edges reference), ascending — the stable canonical
    order P3 mints in."""
    nodes: set = set()
    for i in (sc.get("lazy_nodes") or ()):
        if i < n:
            nodes.add(i)
    for edge in sc.get("edges", ()):
        for i in (edge[0], edge[1]):
            if i < n:
                nodes.add(i)
    return sorted(nodes)


def runway_station_chains(layout, bucket_to_idx, n):
    """P1's substrate: per redistributed runway ref (stable sorted
    order), the along-axis station chain of its ``ROLE_RUNWAY`` ring
    vertices and the CIFP threshold pegs.

    Returns a list of ``SimpleNamespace(ref, stations, members, pegs,
    cap)``: ``stations`` strictly increasing along-axis arclengths (m,
    quantized to :data:`_STATION_QUANT` decimals), ``members[q]`` the
    ascending solver node ids at station ``q`` (empty for a synthetic
    peg station), ``pegs`` station index → CIFP threshold value (the
    world-invariant ``cifp_pins``, verbatim — the ONLY pegs), ``cap``
    the runway's own law cap (``max_grade``, resolved once by
    ``grade_law.runway_profile_law`` and carried on the profile).

    The node collection is the runway-flex hook's own rule
    (``_runway_nodes_for``): ``ROLE_RUNWAY`` shapes matching the ref.
    ``ROLE_RUNWAY_CROSSING`` interpolations stay P2 minters — the
    crossing pinch reaches the second runway's string through the band.
    A ref with fewer than two stations or no profile is skipped (its
    nodes stay P2 minters at their stamped values).
    """
    from auto_patch.layout import ROLE_RUNWAY

    profiles = getattr(layout, "_runway_redistributed_profiles",
                       None) or {}
    cps = getattr(layout, "canonical_points", None)
    chains = []
    if cps is None:
        return chains
    for ref in sorted(profiles):
        p = profiles[ref]
        ax, ay = p["axis_a"]
        dx, dy = p["axis_d"]
        len2 = float(p["axis_len2"])
        if len2 < 1.0:
            continue
        axis_len = _math.sqrt(len2)
        by_station: dict = {}
        for s in layout.shapes:
            if (getattr(s, "role", None) != ROLE_RUNWAY
                    or (s.ref or "") != ref
                    or s.polygon is None or s.polygon.is_empty):
                continue
            ring = list(s.polygon.exterior.coords)
            for (x, y) in (ring[:-1] if ring and ring[0] == ring[-1]
                           else ring):
                i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
                if i is None or i >= n:
                    continue
                t = ((float(x) - ax) * dx + (float(y) - ay) * dy) / len2
                st = round(t * axis_len, _STATION_QUANT)
                by_station.setdefault(st, set()).add(i)
        if len(by_station) < 2:
            continue
        # Threshold pegs: snap to an existing station within the frame,
        # else a synthetic (member-less) station of their own.
        peg_stations: list = []
        for (t_p, e_p) in sorted(p.get("cifp_pins") or ()):
            s_p = float(t_p) * axis_len
            near = min(by_station, key=lambda q: abs(q - s_p))
            if abs(near - s_p) <= _PEG_SNAP_M:
                peg_stations.append((near, float(e_p)))
            else:
                s_q = round(s_p, _STATION_QUANT)
                by_station.setdefault(s_q, set())
                peg_stations.append((s_q, float(e_p)))
        stations = sorted(by_station)
        index_of = {st: q for q, st in enumerate(stations)}
        pegs: dict = {}
        for (st, e_p) in peg_stations:
            pegs.setdefault(index_of[st], e_p)
        chains.append(SimpleNamespace(
            ref=ref, stations=stations,
            members=[sorted(by_station[st]) for st in stations],
            pegs=pegs, cap=float(p.get("max_grade") or 0.015)))
    return chains


def smooth_once(elev, n, *, movable, sym_adj, interval_of):
    """AT MOST ONE in-interval smoothing sweep (spec A5, pre-delegated).

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


def constructive_core(*, layout, icao, elev, base_hard, nodes,
                      bucket_to_idx, n, dem_elev, runway_nodes,
                      shape_constraints, G, u_spine_adj_airside,
                      u_spine_floor, node_band, building_seats,
                      hard_cat, near_miss_edges, u_pair_stage,
                      detached_pads, pad_frontage, seam_pin_idx,
                      gap_spine_chains, gap_spine_b_idx, zone_idx,
                      resa_idx, terrain_first, iyf) -> SimpleNamespace:
    """Run the constructive selection (AMENDMENT 1 — the living band).
    Mutates ``elev`` (and, through the shared groundside law passes,
    ``layout``/``building_seats``) in place; returns the locals the
    shared publication tail reads."""
    import O4_UI_Utils as UI
    from auto_patch import grade_graph as _GG
    from auto_patch.progress import substep as _psub
    from .corridor_profile import solve_run_profile
    from .one_solve import LivingBand, envelope_radj, law_edge_limits
    # The stage/witness/report helpers are module-level in ``solve`` —
    # imported lazily HERE (this module is imported from ``solve``).
    from .solve import (_non_route_witness_nodes, _receiver_nodes_from_roles,
                        _report_witness_admission, _route_witness_admission,
                        _unified_entries, _fair_gap_spine_chains)

    t0 = _time.time()

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

    # ── witness admission (standing route-metric law) over the FULL
    # prospective minter population (the demoted base_hard set + the
    # runway chains — the same population K1 seeded) ─────────────────
    from .one_solve import route_metric_envelope_enabled
    prospective = ({i for i in range(n) if base_hard[i]}
                   | {i for i in runway_nodes if i < n})
    _rm_roles, _rm_route_roles, route_excluded = (
        _route_witness_admission(layout, bucket_to_idx, n))
    if route_metric_envelope_enabled():
        _rm_excl, _rm_rep = _non_route_witness_nodes(
            _rm_roles, _rm_route_roles, prospective, n,
            provenance=hard_cat)
        route_excluded |= _rm_excl
        _report_witness_admission(icao, "constructive", _rm_rep)
    else:                                              # pragma: no cover
        route_excluded = set()

    # ── THE STAGE PARTITION (staged-solve architecture, ruled) ───────
    # Stage A is structurally free of groundside variables: the
    # RECEIVERS (every-role-groundside nodes + role-less stage-B
    # constructs) take NO part in the airside band, minting, selection
    # or smoothing — they hold their seed until the groundside
    # constructors below value them from the solved airside mouths
    # (airside-is-king; attempt 1 measured what mixing costs: CYXY +70
    # adjudicated rows, every worst row a service-road pair torn
    # between the midpoint field and the groundside re-level).
    receivers = _receiver_nodes_from_roles(_rm_roles, gap_spine_b_idx)

    # ── the stage-A law adjacency the band propagates over ───────────
    joint = list(shape_constraints) + _unified_entries(
        u_edges, u_pair_stage, "constructive/envelope")
    edge_lim, interval_lim, env_skip = law_edge_limits(
        joint, n, include_flat_pairs=True)
    edge_lim_a = {(i, j): lim for (i, j), lim in edge_lim.items()
                  if i not in receivers and j not in receivers}
    interval_lim_a = {(i, j): iv for (i, j), iv in interval_lim.items()
                      if i not in receivers and j not in receivers}
    ceil_radj, floor_radj = envelope_radj(
        edge_lim_a, interval_lim_a, env_skip, interval_yield_from=iyf)
    leaf_from = iyf if (zone_idx or resa_idx) else None

    def _stage_a(i):
        return (i not in receivers
                and (leaf_from is None or i < leaf_from))

    # ── P0: THE TRUE ANCHORS (A1) — CIFP thresholds + tile seams ─────
    chains = runway_station_chains(layout, bucket_to_idx, n)
    band = LivingBand(ceil_radj, floor_radj, n)
    refusals: list = []
    p0_defects: list = []

    def _refuse(minter_id, i, v, lo, hi):
        f_a, f_m, c_a, c_m = band.bounding(i)
        deficit = 0.0
        if lo is not None and v < lo:
            deficit = lo - v
        elif hi is not None and v > hi:
            deficit = v - hi
        refusals.append({
            "minter": minter_id, "node": int(i),
            "ll": tuple(layout.m_to_ll(*nodes[i])),
            "value": float(v),
            "band_lo": None if lo is None else float(lo),
            "band_hi": None if hi is None else float(hi),
            "deficit": float(deficit),
            "floor_anchor": f_a, "floor_minter": f_m,
            "ceil_anchor": c_a, "ceil_minter": c_m,
        })

    def _in_band(i, v):
        lo, hi = band.interval(i)
        ok = ((lo is None or v >= lo - _EMPTY_TOL)
              and (hi is None or v <= hi + _EMPTY_TOL))
        return ok, lo, hi

    # seam pins first (owner 2026-05-13: seam overrides CIFP at a
    # shared vertex), then the threshold-station members at the CIFP
    # value; a disagreement between the two surfaces in the A1 audit
    # and at the string's clamped peg, never silently.
    p0_seed: dict = {}
    p0_minter: dict = {}
    for i in sorted(seam_pin_idx):
        if i < n and _stage_a(i):
            p0_seed[i] = float(elev[i])
            p0_minter[i] = "seam"
    thr_nodes: set = set()
    for ch in chains:
        for q, e_p in sorted(ch.pegs.items()):
            for i in ch.members[q]:
                if not _stage_a(i) or i in p0_seed:
                    continue
                p0_seed[i] = float(e_p)
                p0_minter[i] = f"cifp:{ch.ref}"
                thr_nodes.add(i)
    seeding = {i: v for i, v in p0_seed.items()
               if i not in route_excluded}
    band.seed(seeding, p0_minter)
    for i in sorted(p0_seed):
        if i in seeding:
            continue
        band.add(i, p0_seed[i], p0_minter[i], seed=False)
    for i, v in sorted(p0_seed.items()):
        elev[i] = v
    # A1 audit: a true anchor outside the band the OTHER true anchors
    # propagate is a data defect (CIFP vs seam) — reported, never
    # absorbed.
    for i in sorted(p0_seed):
        ok, lo, hi = _in_band(i, p0_seed[i])
        if not ok:
            f_a, f_m, c_a, c_m = band.bounding(i)
            p0_defects.append({
                "kind": "p0_contradiction", "node": int(i),
                "minter": p0_minter[i], "value": float(p0_seed[i]),
                "band_lo": lo, "band_hi": hi,
                "floor_anchor": f_a, "floor_minter": f_m,
                "ceil_anchor": c_a, "ceil_minter": c_m,
                "ll": tuple(layout.m_to_ll(*nodes[i])),
            })

    # ── P1: RUNWAY INTERIORS — taut strings through the band tube ────
    # (thresholds are the ONLY pegs; a crossing runway's already-minted
    # stations pinch the next ref's tube through the band itself).
    p1_nodes: set = set()
    p1_conflicts: list = []
    n_p1_minted = 0
    n_p1_refused = 0
    n_p1_fallback_refs = 0
    for ch in chains:
        walls_lo: list = []
        walls_hi: list = []
        for q in range(len(ch.stations)):
            lo = -_math.inf
            hi = _math.inf
            for i in ch.members[q]:
                if not _stage_a(i):
                    continue
                b_lo, b_hi = band.interval(i)
                if b_lo is not None:
                    lo = max(lo, float(b_lo))
                if b_hi is not None:
                    hi = min(hi, float(b_hi))
            walls_lo.append(lo)
            walls_hi.append(hi)
        run = solve_run_profile(ch.stations, walls_lo, walls_hi,
                                ch.pegs, ch.cap)
        if run is None:
            # under-pegged ref (fewer than two thresholds in data): its
            # nodes stay P2 minters at their stamped values — the
            # non-anchored fallback, recorded.
            n_p1_fallback_refs += 1
            continue
        for c in run.conflicts:
            p1_conflicts.append((ch.ref, c))
        # a peg the walls clamped off its CIFP value is a P0-class
        # contradiction (CIFP vs whatever pinched the band there).
        for q, e_p in sorted(ch.pegs.items()):
            if abs(run.z[q] - e_p) > _EMPTY_TOL:
                p0_defects.append({
                    "kind": "cifp_peg_clamped", "ref": ch.ref,
                    "station_s_m": float(ch.stations[q]),
                    "value": float(e_p), "strung": float(run.z[q]),
                    "deficit": float(abs(run.z[q] - e_p)),
                })
        for q in range(len(ch.stations)):
            z_q = float(run.z[q])
            for i in ch.members[q]:
                p1_nodes.add(i)
                if not _stage_a(i) or i in band.anchors:
                    continue
                ok, lo, hi = _in_band(i, z_q)
                if ok:
                    elev[i] = z_q
                    band.add(i, z_q, f"rwy:{ch.ref}",
                             seed=(i not in route_excluded))
                    n_p1_minted += 1
                else:
                    _refuse(f"rwy:{ch.ref}", i, z_q, lo, hi)
                    n_p1_refused += 1
        # ── C4: the CONSTRUCTED profile becomes the ref's persisted
        # centerline authority.  The crown-spine ridge, the tile-cut
        # rewrite and the seam clamp floor all read
        # ``_runway_redistributed_profiles`` — leaving the FAA profile
        # there would emit a ridge over a DIFFERENT surface than the
        # ring (measured at CYXY: 113 runway_crown shortfall rows,
        # worst 1.170 m, ridge at the stale profile).  ``cifp_pins``,
        # ``seam_t`` and every law/cap field stay verbatim — they are
        # data, not profile.
        _prof = layout._runway_redistributed_profiles.get(ch.ref)
        if _prof is not None:
            _alen = _math.sqrt(float(_prof["axis_len2"]))
            _prof["fractions"] = [float(s) / _alen for s in ch.stations]
            _prof["elevs"] = [float(z) for z in run.z]
            _prof["anchored"] = [q in ch.pegs
                                 for q in range(len(ch.stations))]
            _prof["flex_minted"] = [False] * len(ch.stations)

    # ── P2: THE DEMOTED MINTERS — seam/DEM ties, seats, EAT pins ─────
    # (every remaining base_hard node, at its stamped value, in
    # (class rank, canonical id) order).
    eat_pins = getattr(layout, "_eat_anchor_pin_idx", None) or {}

    def _p2_class(i):
        if i in eat_pins:
            return "eat_pin"
        return hard_cat.get(i, "base_hard:unattributed")

    p2_candidates = sorted(
        (i for i in range(n)
         if base_hard[i] and _stage_a(i)
         and i not in band.anchors and i not in p1_nodes),
        key=lambda i: (_P2_CLASS_RANK.get(_p2_class(i),
                                          _P2_RANK_DEFAULT), i))
    n_p2_minted = 0
    p2_refused_by_class: dict = {}
    seat_refused: set = set()
    for i in p2_candidates:
        cls = _p2_class(i)
        v = float(elev[i])
        ok, lo, hi = _in_band(i, v)
        if ok:
            band.add(i, v, cls, seed=(i not in route_excluded))
            n_p2_minted += 1
        else:
            _refuse(cls, i, v, lo, hi)
            p2_refused_by_class[cls] = (
                p2_refused_by_class.get(cls, 0) + 1)
            if cls == "seat_on_spine" or i in building_seats:
                seat_refused.add(i)

    # ── P3: CERTIFIED REGION FITS — per-entry, per-node, at the flat
    # seed; a refused node shrinks the region (the fallback), the
    # certificate's premise stays true for what remains ──────────────
    cert_accepted: set = set()
    n_lazy_entries = 0
    n_p3_refused = 0
    for e_idx, sc in enumerate(shape_constraints):
        if sc.get("lazy_expand") is None:
            continue
        n_lazy_entries += 1
        for i in certified_entry_nodes(sc, n):
            # base_hard nodes were adjudicated in P2 (minted there or
            # refused there — a P2 refusal is not re-tried as a
            # certified fit; the original ``certified_pins`` excluded
            # hard nodes for the same reason).
            if (not _stage_a(i) or i in band.anchors
                    or i in cert_accepted or base_hard[i]):
                continue
            v = float(elev[i])
            ok, lo, hi = _in_band(i, v)
            if ok:
                cert_accepted.add(i)
                band.add(i, v, f"cert:{e_idx}",
                         seed=(i not in route_excluded))
            else:
                _refuse(f"cert:{e_idx}", i, v, lo, hi)
                n_p3_refused += 1
    _psub(0.62, "Solving elevations — living band minted")

    # ── P4: THE REMAINDER — deterministic in-band selection against
    # the living band (∩ the drainage spine floors, themselves
    # refused-not-clamped where the band cannot hold them) ───────────
    # THE CARRIER FIELD (measured alternative under the spec's
    # pre-delegated clause — "alternatives are measured only if
    # acceptance 1 fails"; the pure midpoint failed CYXY parity by 62
    # adjudicated rows, all in the groundside conformance to mouths the
    # midpoint had lifted off the terrain).  ``R`` is the DEM seed
    # field regularized to cap-Lipschitz over the same law adjacency
    # (midpoint of its lower and upper Lipschitz regularizations), and
    # the selection is ``clamp(R, band)`` — the median of three
    # cap-Lipschitz fields, itself cap-Lipschitz, so every embedded
    # pair stays lawful BY CONSTRUCTION exactly as the midpoint was.
    # Where the band pinches, the selection is the band (flat/midpoint
    # behaviour re-emerges); where it is wide, the surface hugs lawful
    # terrain and the stage-B mouths land where the iterative model's
    # do.  ``O4_CONSTRUCTIVE_SELECT=mid`` keeps the pure-midpoint arm
    # measurable.
    from .one_solve import reach_envelope as _reach_envelope
    _select_mid = _os.environ.get("O4_CONSTRUCTIVE_SELECT") == "mid"

    # (A per-surface seed flattening — C3's planar interiors expressed
    # as a pre-regularization median fill — was built and MEASURED
    # WORSE here at CYXY: adjudicated 380 vs 373, the rim bend
    # concentrating the terrain differential into spans the census
    # prices.  The carrier alone stands; the certified tier remains the
    # planar-interior mechanism.)
    ceil_r: dict = {}
    floor_r: dict = {}
    if not _select_mid:
        _seed0 = list(elev)
        _r_sources = [i for i in range(n) if _stage_a(i)]
        ceil_r, _ = _reach_envelope(+1, ceil_radj, _r_sources, _seed0, n)
        floor_r, _ = _reach_envelope(-1, floor_radj, _r_sources,
                                     _seed0, n)

    def _carrier(i):
        c = ceil_r.get(i)
        f = floor_r.get(i)
        if c is None and f is None:
            return None
        if c is None:
            return float(f)
        if f is None:
            return float(c)
        return 0.5 * (float(c) + float(f))

    immovable = set(band.anchors)          # cert_accepted ⊆ anchors
    spine_ok: dict = {}
    n_spine_floor_refused = 0
    empty_rows: list = []
    solve_broken_idx: set = set()
    n_free = 0
    n_unlabeled = 0

    def _interval_of(i):
        lo, hi = band.interval(i)
        sf = spine_ok.get(i)
        if sf is not None:
            lo = sf if lo is None else max(lo, sf)
        return lo, hi

    for i in range(n):
        if i in immovable or not _stage_a(i):
            continue
        lo, hi = band.interval(i)
        sf = u_spine_floor.get(i)
        if sf is not None:
            sf = float(sf)
            if hi is not None and sf > hi + _EMPTY_TOL:
                # the drainage floor cannot hold against the band here:
                # A3 refusal of the FLOOR (one-sided mint), the
                # gap-spine fairing below remains the drainage path.
                _refuse("spine_floor", i, sf, lo, hi)
                n_spine_floor_refused += 1
            else:
                spine_ok[i] = sf
                lo = sf if lo is None else max(lo, sf)
        if lo is None and hi is None:
            n_unlabeled += 1              # off-graph: keeps its DEM seed
            continue
        if lo is None:
            # One-sided interval: the deterministic selection is the
            # carrier (Lipschitz-regularized seed; the raw seed on the
            # midpoint arm) clamped under the bound — FLAT/at-seed is
            # lawful and the midpoint of a half-line is undefined.
            r = None if _select_mid else _carrier(i)
            if r is not None:
                elev[i] = float(r)
            if elev[i] > hi:
                elev[i] = float(hi)
            n_free += 1
            continue
        if hi is None:
            r = None if _select_mid else _carrier(i)
            if r is not None:
                elev[i] = float(r)
            if elev[i] < lo:
                elev[i] = float(lo)
            n_free += 1
            continue
        if lo > hi + _EMPTY_TOL:
            # STRUCTURALLY IMPOSSIBLE except through a P0 data defect
            # (the band-refinement induction: every accepted mint was
            # in-band).  Recorded on the same channel the K1 fixtures
            # assert EMPTY, with the deterministic midpoint of the
            # crossed bounds.
            empty_rows.append((i, float(lo), float(hi),
                               float(lo - hi)))
            solve_broken_idx.add(i)
            elev[i] = 0.5 * (float(lo) + float(hi))
            n_free += 1
            continue
        r = None if _select_mid else _carrier(i)
        if r is None:
            elev[i] = 0.5 * (float(lo) + float(hi))
        else:
            elev[i] = min(max(float(r), float(lo)), float(hi))
        n_free += 1

    # seat → yield-hard (A3 fallback): a refused seat FOLLOWS the
    # solved surface instead of anchoring it.
    for i in sorted(seat_refused):
        if i in building_seats and i < len(elev):
            building_seats[i] = float(elev[i])

    # ── at most ONE in-interval smoothing sweep (``smooth_once``) ────
    # Stage-A adjacency only (receivers are not smoothed and never
    # pull); interval-edge endpoints do not move here (a symmetric
    # surrogate could exit a signed slab).
    sym_adj: dict = {}
    for (i, j), lim in edge_lim_a.items():
        sym_adj.setdefault(i, []).append((j, lim))
        sym_adj.setdefault(j, []).append((i, lim))
    interval_locked = set()
    for (i, j) in interval_lim:
        interval_locked.add(i)
        interval_locked.add(j)

    def _movable(i):
        return (i not in immovable and i not in interval_locked
                and _stage_a(i))

    # A BOUNDED number of in-interval sweeps (measured alternative
    # under the same acceptance-1-failure clause as the carrier: each
    # sweep preserves containment and pairwise lawfulness as loop
    # invariants — the twin's proof is per-sweep — so iterating them
    # converges toward the in-band harmonic, the field character whose
    # absence priced the unbound census spans).  FIXED count, early
    # exit only on a zero-move sweep: deterministic.
    n_smoothed = 0
    for _sweep in range(_SMOOTH_SWEEPS):
        _moved = smooth_once(
            elev, n, movable=_movable, sym_adj=sym_adj,
            interval_of=_interval_of)
        n_smoothed += _moved
        if not _moved:
            break
    _psub(0.72, "Solving elevations — constructive selection smoothed")

    # ── STAGE B: the receivers take their own constructive valuation ─
    # (airside-is-king: the airside field above is finished and is the
    # AUTHORITY; groundside conforms).  The iterative core values this
    # population with its partitioned projection — holding it at raw
    # seed instead measured +22 within_shape::service_junction rows at
    # CYXY (a family the iterative model fires ZERO of).  Same
    # machinery as stage A, over the receiver-side law adjacency: band
    # seeded by the STAGE BOUNDARY (every non-receiver endpoint of a
    # receiver-touching pair, at its solved airside value) and the hard
    # receivers (seam/DEM pins at their stamped values); selection =
    # the receiver-stage carrier clamped into the band (lawful by
    # construction, exactly as stage A); one smoothing sweep.  The
    # groundside law passes below then re-level pieces from the mouths
    # ON TOP of this lawful base — their authority is preserved, they
    # just no longer start from raw terrain.  A crossed interval here
    # is a mouth-vs-pin contradiction (the airside surface against a
    # groundside truth pin) — counted and reported, but it is NOT the
    # A2 empty-interval class (no band induction spans the stage
    # boundary).
    edge_lim_b = {p: l for p, l in edge_lim.items()
                  if p[0] in receivers or p[1] in receivers}
    interval_lim_b = {p: iv for p, iv in interval_lim.items()
                      if p[0] in receivers or p[1] in receivers}
    n_b_valued = n_b_smoothed = n_b_crossed = 0
    if edge_lim_b or interval_lim_b:
        ceil_radj_b, floor_radj_b = envelope_radj(
            edge_lim_b, interval_lim_b, env_skip,
            interval_yield_from=iyf)
        b_mouths: set = set()
        for (i, j) in list(edge_lim_b) + list(interval_lim_b):
            for k_ in (i, j):
                if k_ < n and k_ not in receivers:
                    b_mouths.add(k_)
        b_hard = {i for i in receivers
                  if i < n and base_hard[i]
                  and (leaf_from is None or i < leaf_from)}
        b_seeds = sorted(b_mouths | b_hard)
        ceil_b, _ = _reach_envelope(+1, ceil_radj_b, b_seeds, elev, n)
        floor_b, _ = _reach_envelope(-1, floor_radj_b, b_seeds, elev, n)
        _seed0_b = list(elev)
        _b_all = [i for i in sorted(receivers)
                  if i < n and (leaf_from is None or i < leaf_from)]
        ceil_rb, _ = _reach_envelope(+1, ceil_radj_b, _b_all,
                                     _seed0_b, n)
        floor_rb, _ = _reach_envelope(-1, floor_radj_b, _b_all,
                                      _seed0_b, n)

        def _carrier_b(i):
            c = ceil_rb.get(i)
            f = floor_rb.get(i)
            if c is None and f is None:
                return None
            if c is None:
                return float(f)
            if f is None:
                return float(c)
            return 0.5 * (float(c) + float(f))

        b_free = set()
        for i in _b_all:
            if base_hard[i]:
                continue
            lo, hi = floor_b.get(i), ceil_b.get(i)
            if lo is None and hi is None:
                continue                  # off-graph: keeps its seed
            b_free.add(i)
            if lo is not None and hi is not None and lo > hi + _EMPTY_TOL:
                n_b_crossed += 1
                elev[i] = 0.5 * (float(lo) + float(hi))
                n_b_valued += 1
                continue
            r = _carrier_b(i)
            v = 0.5 * (float(lo) + float(hi)) if r is None else float(r)
            if lo is not None and v < lo:
                v = float(lo)
            if hi is not None and v > hi:
                v = float(hi)
            elev[i] = v
            n_b_valued += 1
        sym_adj_b: dict = {}
        for (i, j), lim in edge_lim_b.items():
            sym_adj_b.setdefault(i, []).append((j, lim))
            sym_adj_b.setdefault(j, []).append((i, lim))
        n_b_smoothed = 0
        for _sweep in range(_SMOOTH_SWEEPS):
            _moved_b = smooth_once(
                elev, n,
                movable=lambda i: (i in b_free
                                   and i not in interval_locked),
                sym_adj=sym_adj_b,
                interval_of=lambda i: (floor_b.get(i), ceil_b.get(i)))
            n_b_smoothed += _moved_b
            if not _moved_b:
                break
    _psub(0.80, "Solving elevations — groundside stage valued")

    # ── gap-fill drainage spines: the longitudinal law ───────────────
    # (Enclosed-area water escape stays law — owner 2026-08-14 drainage
    # scope.)  The shared second-difference fairing, every move clamped
    # into the slab intervals at current station values.  Frozen =
    # the ACCEPTED anchor set (a refused former-hard node is free and
    # may be faired), plus the receivers' held seeds.
    frozen_flags = [False] * n
    for i in band.anchors:
        if i < n:
            frozen_flags[i] = True
    for i in receivers:
        if i < n and base_hard[i]:
            frozen_flags[i] = True
    n_gap_kinks = 0
    if gap_spine_chains:
        from auto_patch.config import (
            TAXIWAY_MAX_GRADE_CHANGE_PER_M as _K_GAP)
        n_gap_kinks = _fair_gap_spine_chains(
            elev, gap_spine_chains, _K_GAP, frozen=frozen_flags)

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

    # ── the honest exit tally (raw law frame, both edge kinds) ───────
    from .one_solve import shape_constraints_edges
    rem = 0
    bh = 0
    yield_hard = set(band.anchors)
    yield_hard.update(i for i in receivers if i < n and base_hard[i])
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

    # ── the constructive record (A3/A4: the findings ARE the product) ─
    layout._constructive_refusals = refusals
    layout._constructive_p0_defects = p0_defects
    layout._constructive_p1_conflicts = [
        (ref, getattr(c, "kind", "?"),
         float(getattr(c, "station_s_m", 0.0) or 0.0))
        for (ref, c) in p1_conflicts]
    layout._constructive_empty_intervals = [
        (int(i), float(lo), float(hi), float(d),
         tuple(layout.m_to_ll(*nodes[i])))
        for (i, lo, hi, d) in empty_rows]

    n_p2_refused = sum(p2_refused_by_class.values())
    UI.vprint(1,
        f"  [constructive] {icao}: living band from {len(seeding)} "
        f"true anchor(s) ({len(seam_pin_idx & set(p0_seed))} seam, "
        f"{len(thr_nodes)} CIFP threshold node(s) over "
        f"{len(chains)} runway(s), "
        f"{len(p0_seed) - len(seeding)} witness-excluded); minted "
        f"P1 {n_p1_minted} runway station node(s) "
        f"({n_p1_refused} refused, {n_p1_fallback_refs} under-pegged "
        f"ref(s) fell back), P2 {n_p2_minted} tie/seat/pin(s) "
        f"({n_p2_refused} refused), P3 {len(cert_accepted)} certified "
        f"pin(s) over {n_lazy_entries} entr(ies) ({n_p3_refused} "
        f"refused); {n_free} node(s) midpoint-selected, {n_smoothed} "
        f"smoothed in-interval, {n_unlabeled} off-graph at seed, "
        f"{n_spine_floor_refused} spine floor(s) refused; stage B "
        f"{n_b_valued} receiver(s) valued from the mouths "
        f"({n_b_smoothed} smoothed, {n_b_crossed} mouth-vs-pin "
        f"crossing(s)); {n_leaves} terrain leaf(ves) slab-valued, "
        f"{n_gap_kinks} gap-spine kink(s) residual; exit tally {rem} "
        f"edge(s) over cap ({bh} both-hard).")
    if refusals:
        UI.vprint(1,
            f"  [constructive] {icao}: {len(refusals)} NAMED "
            f"REFUSAL(S) (A3 — the anchor-defect findings; each fell "
            f"back to its non-anchored path, no value clamped).  "
            f"Worst by deficit:")
        for r in sorted(refusals, key=lambda r: -r["deficit"])[:10]:
            _lo = ("-inf" if r["band_lo"] is None
                   else f"{r['band_lo']:.3f}")
            _hi = ("+inf" if r["band_hi"] is None
                   else f"{r['band_hi']:.3f}")
            UI.vprint(1,
                f"  [constructive]   {r['minter']} at node "
                f"{r['node']} ({r['ll'][0]:.6f},{r['ll'][1]:.6f}): "
                f"value {r['value']:.3f} outside [{_lo}, {_hi}] "
                f"(deficit {r['deficit']:.3f} m; floor by "
                f"{r['floor_minter']}@{r['floor_anchor']}, ceiling "
                f"by {r['ceil_minter']}@{r['ceil_anchor']})")
    if p0_defects:
        UI.vprint(0,
            f"  [constructive] {icao}: {len(p0_defects)} TRUE-ANCHOR "
            f"DATA DEFECT(S) (A1 — a contradiction WITHIN the "
            f"CIFP+seam set; reported, never absorbed).")
        for d in p0_defects[:10]:
            UI.vprint(0, f"  [constructive]   {d}")
    if empty_rows:
        UI.vprint(0,
            f"  [constructive] {icao}: STOP-CLASS FINDING — "
            f"{len(empty_rows)} EMPTY feasibility interval(s) "
            f"despite the living band (possible only through a "
            f"P0 data defect; spec AMENDMENT 1 says zero by "
            f"construction).  Rows on "
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
        svc_moved=_svc_moved,
        # The projection partition's receiver set, for the airside-scoped
        # exit certificate (air7; RULINGS 2026-09-01l/r).
        receivers=receivers)
