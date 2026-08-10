"""Anchors + bounds for the one-profile solve — all from THE ONE graph.

There is a single reachability graph: the reach band computed on THE unified
grade graph (``building_feasibility.reach_band_unified``).  It sets the building
levels AND bounds every apron / spine / rect node, so they agree by
construction.  This module never builds a second graph.

* ``reach_band_for`` — build the band (+ a DEM sampler + the runway-edge anchors)
  once per solve.
* ``build_building_seats`` — seat each airside building FLAT at the level its
  FRONTAGE can reach (the band intersected over the pad ring), not the centroid:
  the band is a per-point envelope and a serving centerline climbs along a pad,
  so the centroid may reach higher than the apron around the pad can grade to.
* ``node_bands`` — the per-node ``(floor, ceiling)`` the solve clamps into.
* ``apron_body_nodes`` — apron-body vs taxi-route role split (target only).
"""
from __future__ import annotations

import math
import os as _os

from auto_patch.layout import (
    ROLE_APRON, ROLE_BUILDING, ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL, ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD, ROLE_STUB,
)
from ..node_space import store_of as _store_of

_INF = float("inf")


# ── THE PART-C MOUTH ALLOWANCE (one definition, two consumers) ───────────
# ``MOUTH_ALLOWANCE_M = 15 m`` — justification (spec
# ``apron-string-and-scheduling-spec.md`` §C): the physical mouth zone is the
# connector throat, whose scale is already named in ``apply_groundside_reach``
# as ``RAISE_W = 14 m`` (the truck-route corridor half-width the raise pass
# uses); 15 m is one throat-width, rounded.
#
# It bounds groundside twice, and the two bounds must never drift apart:
#   * Part C bounds the pin's VALUE — a pin may not sit more than
#     ``cap · MOUTH_ALLOWANCE_M`` above the WELD DATUM it serves
#     (``gs_pin_float_cap``; the datum is a SOLVED pavement variable —
#     see :func:`gs_pin_law_ceiling`);
#   * the groundside FEASIBILITY-WITNESS CLAUSE (owner ruling 2026-07-30,
#     memory ``groundside-terrace-law``) bounds the pin's ROLE — it may
#     witness an airside node's ``[floor, ceiling]`` only inside the same
#     one-throat reach, expressed in the envelope's BUDGET metric
#     (``gs_witness_horizon``, the identical scalar).
# Single-pass principle: one definition, so a change to the allowance moves
# both bounds together.
def gs_mouth_allowance_m() -> float:
    """The Part-C mouth allowance, in metres of route length."""
    return 15.0


def gs_pin_float_cap(cap: float) -> float:
    """Part C's ALLOWANCE: how far above its WELD DATUM a groundside pin
    may float (metres of elevation) — one connector throat of reach at
    ``cap``.

    THE DATUM IS NOT THE DEM (item 3(a), 2026-08-05, RULINGS "DEM's role,
    and the constant-DEM invariant": *"DEM chooses WHERE in the lawful
    band a thing seats.  It never shapes the band, never constrains,
    never blocks."*).  This scalar used to be added to the pin's OWN DEM
    SAMPLE and published as a real solver bound, so raw ground decided
    how high a lawful groundside surface could sit.  The allowance is
    unchanged; the datum is now :func:`gs_pin_law_ceiling`'s solved
    host-pavement variable.

    WHY THE OLD DATUM FAILED THE CONSTANT-DEM ORACLE (the inspection
    argument, kept because it is the reason this function's contract
    changed): on a DEM ≡ c build the ceiling collapsed to the flat
    ``c + cap·15 m`` for every pin — ≈0.75 m above the constant at the
    service-road cap — so any lot that must weld to pavement higher than
    that was clamped below its lawful level and emitted a violation on
    ground with no relief at all.  The replacement contains no DEM term
    whatsoever, so it is IDENTICAL in the plateau and canyon worlds."""
    return cap * gs_mouth_allowance_m()


def gs_pin_law_ceiling(host_datum: float, route_len_m: float,
                       cap: float) -> float:
    """THE groundside mouth ceiling, from a LAW datum only.

    ``host_datum`` — the SOLVED elevation of the pavement the mouth welds
    toward (the apron at the deep end of the truck route, or the
    connector's own apron-ward mouth when no centerline serves it).  A
    solver variable, never a DEM sample.
    ``route_len_m`` — the truck-route length the reach law budgets over.
    ``cap`` — the governing (service-road) grade cap.

    ``host_datum + cap · (route_len + MOUTH_ALLOWANCE_M)`` — the reach law
    from the weld datum, plus exactly one throat of reach
    (:func:`gs_pin_float_cap`) because the weld point is not the datum
    point.  This is the LAW's own statement of how high the mouth may sit
    and contains no terrain term, so:

    CONSTANT-DEM ORACLE, BY INSPECTION.  Every input is either a solved
    pavement variable or a law constant.  With DEM ≡ 1 m and with
    DEM ≡ 10 000 m the ceiling is computed by the same expression from the
    same law, so it cannot differ between the two worlds by anything the
    DEM did; it can only move with the host pavement the airside solve
    placed.  It therefore never clamps a lawful mouth in either world, and
    the seat inside ``[base − cap·route_len, base + cap·route_len]``
    lands on the interval end nearest the seed — the FLOOR in the plateau
    world, the CEILING in the canyon world, which is the ADDENDUM's
    extreme-seating assertion."""
    return float(host_datum) + float(cap) * (
        float(route_len_m) + gs_mouth_allowance_m())


def gs_witness_horizon(cap: float) -> float:
    """The witness clause's ROLE bound: how far a groundside pin's envelope
    label may travel, in metres of BUDGET distance (the reach-envelope
    Dijkstra's own metric, ``Σ cap_e · len_e``).  Numerically the same scalar
    as :func:`gs_pin_float_cap` — one throat of reach at cap — because a
    label that has spent ``cap · MOUTH_ALLOWANCE_M`` of budget has left the
    mouth zone by exactly the distance Part C allows the mouth to float."""
    return gs_pin_float_cap(cap)

# ── Parallel-road station coupling (part 30m OPEN item (a), DEFAULT OFF) ──
# The queued fix for the "two NON-touching parallel service roads seat a
# metre-scale wall across the gap" defect (#576↔#584): widen the spine-station
# merge past its 2 m sliver window (the O4_SVC_PROXIMITY_COUPLE analogue, which
# misses a several-metre gap) so a near-parallel pair a few metres apart shares
# ONE DEM seed + ONE reach-band intersection — a single-valued cross-section the
# wall cannot be seeded on.  A TANGENT guard (|cos∠(tangent_a, tangent_b)| above
# the threshold — antiparallel loop returns count, a crossing road ≈90° never
# does) keeps it to genuine parallel pairs.
#
# SHIPPED OFF (measured 2026-07-08).  The documented #576↔#584 site no longer
# exists at HEAD (intervening commits — the off-source SOURCE CLIP and adjacent-
# ground work — reshaped HECA's service net; the equivalent HECA pair is now
# 0.19 m, resolved).  Where this coupling actually FIRES (CYXY -10045↔-10195,
# 6.7 m apart) the two roads differ by ~1.5 m for GENUINE terrain reasons
# (non-overlapping reach bands — the SAME physics part-30m recorded for
# #576↔#584: "each road on its OWN spine regime"); forcing a shared seed there
# REGRESSED CYXY (worst service tear 22.2→23.2 %, facing step 1.523→1.587 m).
# Proximity + parallelism alone cannot tell a "coincidental wall that should be
# flat" from "two roads terrain genuinely holds apart" — they are identical
# geometry — so no guard makes the coupling both effective and non-regressing.
# Kept behind the gate (idiomatic default-off experiment) for a future revisit
# that carries the missing signal (e.g. a shared groundside connection proving
# the pair SHOULD be co-level).  ``O4_SVC_PARALLEL_STATION_MERGE=1`` enables it;
# default (unset / 0) ⇒ byte-identical to the 2 m window.  Standalone tuning
# knobs (not aerodrome standards; anchors.py owns them per the part-32 split).
# BELIEVED-IN STATE: OFF (2026-08-05).  The experiment above never found
# the missing signal, and a gate is no longer how an unbelieved branch is
# carried — this constant is the switch, and it is False.
PARALLEL_SERVICE_STATION_MERGE = False
# Max XY gap between the two lines' stations to couple them (m).
PARALLEL_SERVICE_STATION_MERGE_MAX_GAP_M = 7.0
# Near-parallel guard: |cos(angle between the host-line tangents)| must be at
# least this (cos 25° ≈ 0.906) — a crossing road (≈90°, cos≈0) never couples.
PARALLEL_SERVICE_STATION_MERGE_MIN_ABS_COS = 0.906

# The TAXI ROUTE (smoothness target, bounded by the reach band): taxi rects +
# junctions.  A node shared by an apron AND a route shape is a route node.
_ROUTE_ROLES = frozenset({
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL, ROLE_STUB,
    ROLE_CROSS_CONNECTOR, ROLE_JUNCTION,
})
# DEM-FOLLOWING body (closest-to-DEM target, NO taxi-band bound): aprons AND
# service roads/junctions.  A service road is NOT a taxiway — it grades at 4% and
# ties to the ground road network / terrain, so it must NOT be clamped to the
# taxi reach band (which would cap it metres below DEM — user 2026-06-25).
_DEM_BODY_ROLES = frozenset({
    ROLE_APRON, ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION,
})


def _open_ring(coords):
    if coords and coords[0] == coords[-1]:
        return list(coords[:-1])
    return list(coords)


def reach_band_for(layout, elev, bucket_to_idx, dem, tile_lat, tile_lon,
                   unified_graph=None):
    """Build the one reach band, a DEM sampler, and the runway-edge anchors.

    The band is computed on THE unified grade graph the spine solves on
    (``reach_band_unified``) — one graph, no route-graph drift, no
    ceiling-consistency bridge.  ``unified_graph`` is the prebuilt
    ``build_unified_graph`` (the caller already needs it); also returned so the
    solve reuses the same object."""
    from auto_patch.elevation import _sample_dem
    from auto_patch.elevation_per_surface.building_feasibility import (
        reach_band_unified)
    from auto_patch.elevation_per_surface.solver_primitives import _runway_edge_pts

    runway_pts = _runway_edge_pts(layout, elev, bucket_to_idx)
    G = unified_graph
    band = reach_band_unified(layout, G)

    def _dem(x, y):
        try:
            lat, lon = layout.m_to_ll(x, y)
            return _sample_dem(dem, tile_lat, tile_lon, lat, lon)
        except Exception:                                     # pragma: no cover
            return None

    return band, _dem, runway_pts, G


def _seat_node_band(ring, band, cps, bucket_to_idx):
    """The NODE-BAND interval at a pad's CONTACT NODES — the intersection of
    ``band(x, y)`` over exactly those ring vertices that are registered solve
    nodes (``bucket_to_idx``), i.e. the nodes the seat is actually stamped on
    and that ``node_bands`` later clamps.

    Read-only on the canonical registry (``cps.get``, never ``get_or_add``):
    interning a point changes which LATER points intern together and would
    move the emitted surface — this is a measurement, so it uses the
    measurement query (``canonical_points.get`` docstring).

    Returns ``(floor, ceiling, contacts)``; ``contacts == 0`` ⇒ nothing to
    say (off-net pad) and the interval is ``(-inf, +inf)``."""
    nlo, nhi, contacts = -_INF, _INF, 0
    for (x, y) in ring:
        k = cps.get(float(x), float(y))
        if k is None or bucket_to_idx.get(k) is None:
            continue
        nb = band(x, y)
        if nb is None:
            continue
        nlo = max(nlo, nb[0])
        nhi = min(nhi, nb[1])
        contacts += 1
    return nlo, nhi, contacts


def _report(line):
    """One line out of a seat-law attribution, on the production channel.

    ``O4_UI_Utils`` is the GUI↔core contract and is what a production build
    reads; a standalone/probe build has no such module, and an attribution
    that disappears there would be exactly the silence these reports exist
    to remove — so it falls back to ``print``."""
    try:
        import O4_UI_Utils as _UI
        _UI.vprint(1, line)
    except Exception:                                    # pragma: no cover
        print(line)


# ── ROUTE-DISTANCE SEAT COUPLING (spec
# ``docs/specs/route-distance-seat-coupling-spec.md``) ────────────────────
# The owner dial for pair admission.  It stays a DISTANCE and mirrors
# ``config.BUILDING_REACH_CORRIDOR_M`` — the spec's "provisional 200 m to
# preserve today's reach intent" — and is converted ONCE, at the apron cap,
# into the metric the projection actually enforces (see
# :func:`route_coupling_horizon_m`).
ROUTE_COUPLING_MAX_DIST_M: float | None = None      # None ⇒ the corridor

# ── THE COUPLER IS ROUTE-PRICED — STANDING LAW ───────────────────────────
# (spec ``docs/specs/route-distance-seat-coupling-spec.md``; formerly gates
# ``O4_SEAT_COUPLE_ROUTE_METRIC`` + ``O4_SEAT_COUPLE_SHARED_SURFACE``, both
# retired 2026-08-05 under RULINGS "BUILD-COMPLETE-THEN-DEBUG".)
#
# THE LAW.  The seat coupler admits and prices pairs on the WITHIN-SHAPE
# LAW GRAPH the projection enforces, never on a straight chord: a pair's
# budget is the per-edge budget sum along the minimum-budget path, priced
# exactly as ``feasibility_project`` prices its edges.  There is ONE
# metric.  The chord corridor cutoff and the pavement-visibility fraction
# are RETIRED as admission predicates — the chord is still MEASURED, purely
# as the census that makes each pair's tightening adjudicable.
#
# THE DEFECT IT CLOSES (dossier §2, HEAZ).  Pads building4↔building5 are
# 17.6 m apart by chord (limit 0.176 m) but bound by the 2-hop chain
# ``35 —0.0578— 1295 —0.1015— 37``: the REAL budget is 0.1593 m, and the
# pair stalled 8 000 sweeps.  The visibility fraction is a FALSE-NEGATIVE
# pair predicate on top of that — those two pads' ring nodes sit on ONE
# apron ring and the projection enforces the chain between them regardless,
# yet the coupler rejected the pair as "separated by grass" at frac=0.057.
# Two instruments over one population: the coupler's adjacency was a
# visible straight chord, the projection's is the within-shape law graph.
# ``O4_SEAT_COUPLE_SHARED_SURFACE`` is SUBSUMED, not merged: ring-sharing
# pads have a through-surface path, so route admission already offers every
# pair that predicate was invented to rescue (measured: byte-identical
# route arms with and without it at CYXY and HEAZ).
#
# MEASURED SURFACE COST IN THE OLD (GATED, PRE-COMPOSED) WORLD: KCLT +121
# law-true ``within`` at the 2026-08-04 tip, breadth not depth — the
# corridor faces around the 63-of-69 pads that moved could not grade to
# their new law-true joint levels.  That number was taken against a
# chord-priced surface that no longer exists; it is a DEBUG-PHASE target,
# not a reason to keep two metrics.  Full arm table: coupling/RESULTS.md.


def route_coupling_horizon_m() -> tuple:
    """``(budget_horizon_m, dial_distance_m)`` for pair admission.

    UNIT NOTE (declared, never silent).  The dial is a DISTANCE — today's
    ``BUILDING_REACH_CORRIDOR_M`` — and admission is tested in the BUDGET
    metric at the apron cap, so the gate is exactly today's rule with route
    distance substituted for chord distance under the same cap
    (``gap ≤ 200 m`` ⇔ ``APRON_MAX_GRADE·gap ≤ 2.0 m``).  Testing
    reachability in metres of LENGTH instead would re-introduce a second
    metric the projection does not enforce, and would reject pairs whose
    budget genuinely binds: a minimum-BUDGET route may take a long detour
    over cheap pavement, and it is that route the law walks."""
    from auto_patch.config import APRON_MAX_GRADE, BUILDING_REACH_CORRIDOR_M
    dial = ROUTE_COUPLING_MAX_DIST_M
    if dial is None:
        dial = float(BUILDING_REACH_CORRIDOR_M)
    return float(APRON_MAX_GRADE) * float(dial), float(dial)


def _pad_route_budgets(law_graph, pad_nodes, n_nodes=None):
    """``(budgets, diag)`` — the min-budget route between every pair of pads
    on the graph ``feasibility_project`` enforces.

    ``law_graph`` — the solve's own ``shape_constraints`` list (the object
    handed to the projection, never a re-derivation).  ``pad_nodes`` — one
    node-index set per pad, in the coupler's pad order.

    THE PRICING IS THE PROJECTION'S OWN, clause for clause
    (``one_solve._build_adjacency``):

      * SYMMETRIC 3-tuple edges only.  An INTERVAL 4-tuple is a one-sided
        slab (adjacent-ground zone, RESA cut) and has no symmetric route
        price; routing a pad↔pad chord through terrain would also
        contradict ``reach-follows-centerlines`` (RULINGS 2026-07-30).
      * ``lim is None`` / negative = unregulated ⇒ dropped; ``i >= n`` when
        the caller states ``n_nodes`` ⇒ dropped.
      * FLAT-GROUP CONTRACTION: each pad collapses to one representative
        (``rep = min(group)``, overlapping groups merged first — two
        touching pads sharing a ring vertex are ONE rigid unit), exactly
        the collapse the projection performs on ``flat_groups``.
      * TIGHTEST-BUDGET-WINS per canonical pair after the remap.
      * the per-edge budget is the RAW law budget — exactly what the
        projection sweeps.  The emit-quantization margin that used to
        split these into two frames is RETIRED (docs/RULINGS.md
        2026-08-05; see the ``one_solve`` module head): there is one law
        frame, so the coupler and the projection agree by construction
        rather than by keeping a subtraction in sync.  The dossier's
        certificate (0.0578 over 6.78 m, 0.1015 over 11.15 m, budget
        0.1593) is that frame.

    The Dijkstra itself is NOT written here: it is
    ``law_graph_budget.build_anchor_envelope``, the seed-fix round's oracle,
    seeded ``{rep_i: 0.0}`` so its ``ceil_route_m[rep_j]`` IS ``d(i, j)``
    (``single-pass-principle`` — one metric, built once, consumed twice).

    ``diag`` carries the census the round reports: pair counts, the
    certified-lazy entry count (those contribute ring edges only — the
    approximation is declared, not hidden), and the BUDGET-IDENTITY
    measurement (§4): every pair is priced from BOTH endpoints and the
    disagreement reported; >1 % is the spec's STOP."""
    from .law_graph_budget import build_anchor_envelope

    horizon, dial = route_coupling_horizon_m()
    # ── flat-group contraction (mirrors one_solve's merge exactly) ──────
    merged: list = []
    owner: list = []                      # pad index -> merged-group index
    for g in pad_nodes:
        g = set(g)
        hit = None
        for mi, mg in enumerate(merged):
            if mg & g:
                mg |= g
                hit = mi
                break
        if hit is None:
            merged.append(set(g))
            hit = len(merged) - 1
        owner.append(hit)
    gmap: dict = {}
    rep_of_group: list = []
    for mg in merged:
        if not mg:
            rep_of_group.append(None)
            continue
        rep = min(mg)
        rep_of_group.append(rep)
        for m in mg:
            gmap[m] = rep
    rep_of_pad = [rep_of_group[owner[k]] for k in range(len(pad_nodes))]

    # ── the projection's edge set, deduped, at RAW law budgets ──────────
    edge_lim: dict = {}
    lazy_entries = 0
    interval_edges = 0
    for sc in law_graph:
        if sc.get("lazy_expand") is not None:
            lazy_entries += 1
        for edge in sc["edges"]:
            if len(edge) >= 4:
                interval_edges += 1
                continue
            i, j, lim = edge
            if lim is None or lim < 0:
                continue
            if n_nodes is not None and (i >= n_nodes or j >= n_nodes):
                continue
            i = gmap.get(i, i)
            j = gmap.get(j, j)
            if i == j:
                continue
            e = (i, j) if i < j else (j, i)
            prev = edge_lim.get(e)
            if prev is None or lim < prev:
                edge_lim[e] = lim
    # ONE FRAME.  The margin that once split this into an enforced
    # (margined) graph and a report-only RAW twin is retired, so the
    # second Dijkstra field is DELETED rather than recomputed to the same
    # answer (single-pass-principle).  ``diag["raw_budgets"]`` is still
    # published — it is now literally the law route price.
    adj: dict = {}
    for (i, j), lim in edge_lim.items():
        adj.setdefault(i, []).append((j, lim))
        adj.setdefault(j, []).append((i, lim))

    # ── one oracle field per pad; the pair budget is read off it ────────
    fields: dict = {}
    for rep in rep_of_pad:
        if rep is None or rep in fields or rep not in adj:
            continue
        fields[rep] = build_anchor_envelope(adj, {rep: 0.0},
                                            horizon_m=horizon)
    budgets: dict = {}
    raw_budgets: dict = {}
    merged_pairs = 0
    ident_worst = 0.0
    ident_worst_pair = None
    ident_over = []
    unreachable = 0
    off_graph = 0
    for a in range(len(pad_nodes)):
        ra = rep_of_pad[a]
        for b in range(a + 1, len(pad_nodes)):
            rb = rep_of_pad[b]
            if ra is None or rb is None:
                off_graph += 1
                continue
            if ra == rb:
                # MERGED RIGID UNIT.  Two pads sharing a ring vertex are ONE
                # flat group in the projection, and the merge is transitive —
                # a chain of touching buildings is a single rigid body that
                # the projection seats at ONE level (it broadcasts the
                # group's mean).  Their coupling budget is 0 by law, at any
                # separation: a chord-priced coupler that let them differ was
                # choosing levels the projection would overwrite.
                budgets[(a, b)] = 0.0
                merged_pairs += 1
                continue
            fa, fb = fields.get(ra), fields.get(rb)
            dab = None if fa is None else fa.ceil_route_m.get(rb)
            dba = None if fb is None else fb.ceil_route_m.get(ra)
            if dab is None and dba is None:
                if ra not in adj or rb not in adj:
                    off_graph += 1
                else:
                    unreachable += 1
                continue
            # ── §4 BUDGET IDENTITY: the same pair priced from both ends.
            if dab is not None and dba is not None:
                scale = max(abs(dab), abs(dba), 1e-9)
                rel = abs(dab - dba) / scale
                if rel > ident_worst:
                    ident_worst, ident_worst_pair = rel, (a, b)
                if rel > 0.01:
                    ident_over.append((a, b, dab, dba))
            d = min(x for x in (dab, dba) if x is not None)
            budgets[(a, b)] = float(d)
            # ONE FRAME: the route price IS the raw law price.
            raw_budgets[(a, b)] = float(d)
    diag = {"horizon_m": horizon, "dial_m": dial,
            "raw_budgets": raw_budgets, "merged_pairs": merged_pairs,
            "merged_groups": sum(1 for gi in set(owner)
                                 if owner.count(gi) > 1),
            "merged_pads": sum(1 for gi in owner if owner.count(gi) > 1),
            "pairs": len(budgets), "unreachable": unreachable,
            "off_graph": off_graph, "lazy_entries": lazy_entries,
            "interval_edges": interval_edges, "graph_nodes": len(adj),
            "graph_edges": len(edge_lim),
            "ident_worst": ident_worst, "ident_worst_pair": ident_worst_pair,
            "ident_over": ident_over}
    return budgets, diag


def _merge_rigid_units(pads, cps):
    """MERGED RIGID UNITS (owner law) — collapse ``pads`` into the flat
    groups the projection will enforce, TRANSITIVELY.

    ``pads`` — the coupler's ``(shape, ring, level, lo, hi)`` rows.
    Returns ``(units, unit_of, rows)``:

      * ``units`` — one dict per rigid unit, in ascending order of its
        lowest member index (deterministic): ``members`` (pad indices),
        ``refs``, ``ref`` (the report label), ``polygon`` (the union of the
        member footprints), ``level``, ``lo``, ``hi``;
      * ``unit_of[pad_index]`` — the unit that pad belongs to;
      * ``rows`` — one report row per MULTI-member unit (single pads are
        not news).

    THE RELATION is "shares a ring vertex", read through the CANONICAL
    REGISTRY (``cps.get_or_add``) — the same interning ``build_building_seats``
    uses to stamp seats and the same one ``bucket_to_idx`` is keyed on, so
    two ring vertices that weld to one canonical point count as shared even
    when their raw coordinates differ.  That makes this relation identical
    to the node-set overlap ``_pad_route_budgets`` contracts on for every
    pad whose ring vertices are registered solve nodes, and STRICTLY WIDER
    for pads that touch only at an OFF-NET vertex — which is the owner's
    law as stated ("pads sharing a ring vertex"), not the projection's
    node-graph accident.

    THE UNIT'S BOX is the INTERSECTION of its members' boxes: a rigid body
    may not yield outside a level any member's own frontage can reach.  An
    EMPTY intersection is a genuine law defect (``feasibility-is-guaranteed``
    — two touching pads whose reachable levels do not overlap), so it is
    REPORTED and the unit degenerates to the most-constrained CEILING: the
    lowest member ceiling is the highest level every member's frontage can
    actually grade to, and seating above it is unreachable by construction.

    THE UNIT'S TARGET is the AREA-WEIGHTED mean of its members' independent
    targets, clamped into the unit box.  The projection broadcasts an
    unweighted mean over NODES (i.e. perimeter-weighted); area weighting is
    the deliberate deviation — a shed welded to a terminal must not drag
    the terminal's level — and it is the value the projection then finds
    already satisfied instead of minting one.
    """
    n = len(pads)
    parent = list(range(n))

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:                       # smallest index wins -> stable
            parent[max(ra, rb)] = min(ra, rb)

    owner_of_key: dict = {}
    for k, (_s, ring, *_r) in enumerate(pads):
        for (x, y) in ring:
            key = cps.get_or_add(float(x), float(y))
            prev = owner_of_key.get(key)
            if prev is None:
                owner_of_key[key] = k
            elif prev != k:
                _union(prev, k)

    groups: dict = {}
    for k in range(n):
        groups.setdefault(_find(k), []).append(k)

    units: list = []
    unit_of = [0] * n
    rows: list = []
    for root in sorted(groups):
        members = groups[root]
        for k in members:
            unit_of[k] = len(units)
        if len(members) == 1:
            (s, _ring, level, lo, hi) = pads[members[0]]
            units.append({"members": members,
                          "refs": [s.ref or "?"],
                          "ref": s.ref or "?",
                          "polygon": s.polygon,
                          "level": float(level),
                          "lo": float(lo), "hi": float(hi)})
            continue
        refs = [pads[k][0].ref or "?" for k in members]
        lo = max(float(pads[k][3]) for k in members)
        hi = min(float(pads[k][4]) for k in members)
        empty = lo > hi
        if empty:
            hi = min(float(pads[k][4]) for k in members)
            lo = hi
        wsum = 0.0
        vsum = 0.0
        for k in members:
            w = float(pads[k][0].polygon.area) if pads[k][0].polygon else 0.0
            w = max(w, 1e-9)
            wsum += w
            vsum += w * float(pads[k][2])
        level = min(max(vsum / wsum, lo), hi)
        # The unit's footprint is the UNION of its members — but only when
        # that union is a single Polygon: every consumer here
        # (``polygon.distance``, ``_footprint_dem_relief``) reads
        # ``.exterior``, and pads that touch at a single point can union to
        # a MultiPolygon.  Fall back to the LARGEST member, which is the
        # footprint whose relief the split-level law would threshold on.
        poly = max((pads[k][0].polygon for k in members
                    if pads[k][0].polygon is not None),
                   key=lambda g: g.area, default=None)
        try:
            from shapely.ops import unary_union
            u = unary_union([pads[k][0].polygon for k in members
                             if pads[k][0].polygon is not None])
            if (u is not None and not u.is_empty
                    and getattr(u, "geom_type", "") == "Polygon"):
                poly = u
        except Exception:                            # pragma: no cover
            pass
        units.append({"members": members, "refs": refs,
                      "ref": "{" + "+".join(refs[:3])
                             + ("+…" if len(refs) > 3 else "") + "}",
                      "polygon": poly, "level": float(level),
                      "lo": float(lo), "hi": float(hi)})
        rows.append({"members": members, "refs": refs, "level": float(level),
                     "lo": float(lo), "hi": float(hi), "empty": bool(empty)})
    return units, unit_of, rows


def build_building_seats(layout, bucket_to_idx, band, dem_fn, runway_pts,
                         *, law_graph=None, n_nodes=None):
    """``{pad_node_idx: flat_level}`` for every airside-touching building, seated
    at the level its FRONTAGE can reach (the band intersected over the pad ring)
    closest to DEM.

    ``law_graph`` / ``n_nodes`` — the solve's own ``shape_constraints`` and
    node count, consumed ONLY by the route-distance coupling gate
    (:func:`seat_couple_route_metric_enabled`).  Absent, the gate cannot
    price on the law graph and says so rather than pricing on a chord in
    silence."""
    import os as _os
    from auto_patch.layout import ROLE_APRON
    from auto_patch.elevation_per_surface.building_feasibility import (
        building_feasible_levels)

    cps = layout.canonical_points
    # BOUNDED YIELD box registry (owner ruling 2026-07-29: "Any yield
    # absolutely needs to stay within the feasibility box"): whatever seats
    # a node also records the reach-band interval the seat was chosen from,
    # keyed by CANONICAL KEY (the ``canonical_points`` registry point) —
    # never by node index: the final projection runs on a REBUILT node
    # list (the rod-key lesson), so only the key survives.  Lives in the
    # NODE-SPACE STORE (U1, ``node_space.py``): consumers (solve.py fp#8 +
    # final_grade_projection) resolve it through ``view_interval`` into
    # their own index space and clamp every freed value inside its box.
    # Reset here — this is the first seat producer of a solve;
    # ``build_nobuilding_apron_seats`` merges its contact boxes into the
    # same payload afterwards.
    _store_of(layout).open_map("seat_boxes", "interval", reset=True)
    # ``building_feasible_levels`` decides WHICH buildings are airside-served (its
    # touch test) + gives the centroid level as a fallback for off-network pads.
    levels = building_feasible_levels(layout, runway_pts, dem_fn, band=band)

    # FRONTAGE-EDGE seat (user 2026-06-27): seat the flat pad at the feasible level
    # reachable at the CENTRE of its FRONTAGE edge — the apron-shared building edge
    # facing the MOST-CONSTRAINED taxi route (the lowest band ceiling among the
    # apron-shared edges).  The straight route from that centre to the binding
    # taxiway IS what ``band`` measures, so the apron can grade ≤1 % from the
    # frontage down to the taxiway and the far frontages descend to the pad.  This
    # supersedes the whole-ring MEDIAN, which over-pinned the low (route-limited)
    # frontage corner by averaging in the far high corners — CYXY building15 was
    # seated 709.4 (median over 707.6..712.5) while its A2 frontage centre reaches
    # only 708.4, pinning the A2-end apron 1.8 m high → the 20 % apron cliff.
    # STANDING LAW (owner 2026-06-27; former gate O4_BUILDING_FRONTAGE_SEAT
    # retired 2026-08-05): the whole-ring MEDIAN fallback survives only for
    # a pad with NO apron-shared edge, where there is no frontage to read.
    # ── SEAT-vs-BAND CONSISTENCY — STANDING LAW ─────────────────────────
    # (spec dossier-fixes §2; former gate ``O4_SEAT_BAND_CONSISTENT``,
    # retired 2026-08-05.)
    # Two band instruments over one population: a large pad's seat is
    # chosen inside ``_frontage_band`` (a corridor band sampled along the
    # frontage), but the projection bounds the pad's ring nodes by
    # ``node_bands`` = the SAME band sampled PER NODE.  The two disagree:
    # HECA building181 ships seated 105.772 while 2 of its 12 ring nodes
    # have a node-band ceiling of 103.914 — the seat is 1.858 m above a
    # level the band the solve enforces cannot reach, so no surface can
    # honour it anywhere (carrier_attrib/DOSSIER.md §5).
    # Per ``band-lawful-displacement-trumps-DEM`` there is ONE band: the
    # seat clamps into the INTERSECTION of the frontage interval and the
    # node-band interval at its contact nodes.  An EMPTY intersection is
    # not silently resolved — it is the split-level-seat law's trigger
    # (RULINGS 2026-08-04) and is reported, with today's value kept.
    # Measured when it flipped ON (2026-08-04): HECA 9 952 → 9 649 law-true
    # within (−303; ``building|building`` 440→393 AND the surrounding
    # ``apron`` 6822→6665 / ``junction`` 1856→1781 follow it down), every
    # other battery airport byte-identical.
    _sb_moved: list = []
    _sb_empty: list = []
    # Large buildings (≥ area) seat at the FULL-FRONTAGE feasible level (user
    # 2026-06-27): the entire frontage must grade to the spine ≤1 %, so the seat is
    # the band intersected over the whole frontage (computed by
    # ``building_feasible_levels``), not the single lowest-ceiling frontage edge.
    from auto_patch.grade_law import building_requires_full_frontage
    apron_keys: set = set()
    # Frontage = a building edge shared with any SOFT pavement ring.
    # Under the route-arc GLOBAL SLICE the face a building fronts onto is
    # usually ROLE_JUNCTION (a corridor face), not ROLE_APRON — apron-only
    # keys silently dropped every such frontage back to the legacy
    # whole-ring MEDIAN seat, re-creating the over-pinned frontage
    # conflicts the frontage seat was built to fix (CYXY pads seated
    # 1-2 m apart at close quarters).
    from auto_patch.layout import (
        ROLE_JUNCTION as _RJ, ROLE_SERVICE_JUNCTION as _RSJ)
    for a in layout.shapes:
        if (a.role in (ROLE_APRON, _RJ, _RSJ) and a.polygon is not None
                and not a.polygon.is_empty):
            for (x, y) in _open_ring(list(a.polygon.exterior.coords)):
                apron_keys.add((round(x, 2), round(y, 2)))

    def _median(ring, de):
        ceils = sorted(b[1] for (x, y) in ring if (b := band(x, y)) is not None)
        if not ceils:
            return None
        m = len(ceils)
        med = (ceils[m // 2] if m % 2
               else 0.5 * (ceils[m // 2 - 1] + ceils[m // 2]))
        return min(de, med) if de is not None else med

    def _frontage_box(ring):
        """Feasible seat interval from the centres of the building's apron-shared
        edges (both endpoints shared with an apron): ``(max floor, min ceiling)``
        — the ceiling is the most-constrained frontage (the legacy seat rule),
        the floor the highest any frontage must stay above.  None when no edge
        is apron-shared (→ caller falls back)."""
        n = len(ring)
        flo, fhi = None, None
        for i in range(n):
            a = (round(ring[i][0], 2), round(ring[i][1], 2))
            b = (round(ring[(i + 1) % n][0], 2), round(ring[(i + 1) % n][1], 2))
            if a in apron_keys and b in apron_keys:
                cx = 0.5 * (ring[i][0] + ring[(i + 1) % n][0])
                cy = 0.5 * (ring[i][1] + ring[(i + 1) % n][1])
                bc = band(cx, cy)
                if bc is not None:
                    flo = bc[0] if flo is None else max(flo, bc[0])
                    fhi = bc[1] if fhi is None else min(fhi, bc[1])
        if fhi is None:
            return None
        return (min(flo, fhi) if flo is not None else -_INF, fhi)

    # ── Per-pad independent target + feasible box ────────────────────────────
    # target = the legacy independent seat (DEM biased into the frontage band);
    # box    = the reach-band interval the seat may move within when the JOINT
    #          projection below reconciles neighbouring pads.
    pads: list = []             # (shape, ring, target_level, lo, hi)
    for s in layout.shapes:
        lv = levels.get(id(s))
        if lv is None or s.polygon is None or s.polygon.is_empty:
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        de = dem_fn(s.polygon.centroid.x, s.polygon.centroid.y)
        if building_requires_full_frontage(s.polygon.area):
            # ``lv`` IS the full-frontage feasible level for a large building;
            # its box is the frontage-band intersection ``lv`` was clamped into.
            from auto_patch.grade_law import BUILDING_REACH_CORRIDOR_M
            from auto_patch.elevation_per_surface.building_feasibility import (
                _frontage_band, _pavement_visibility)
            from auto_patch.config import VISIBLE_CHORD_CONNECT
            level = float(lv)
            _cls = [cl.line for cl in
                    (getattr(layout, "apt_taxi_centerlines", None) or [])
                    if cl.line is not None and not cl.line.is_empty
                    and not cl.is_service]
            _vis = _pavement_visibility(layout) if VISIBLE_CHORD_CONNECT else None
            fb = (_frontage_band(s.polygon, band, _cls, _vis,
                                 BUILDING_REACH_CORRIDOR_M) if _cls else None)
            if fb is None:
                fb = band(s.polygon.centroid.x, s.polygon.centroid.y)
            lo, hi = (min(*fb), max(*fb)) if fb is not None else (level, level)
            nlo, nhi, _nc = _seat_node_band(ring, band, cps, bucket_to_idx)
            if _nc:
                ilo, ihi = max(lo, nlo), min(hi, nhi)
                if ilo > ihi:
                    # LOUD, never silently shipped: the frontage band and
                    # the node band have no common level, which is
                    # precisely the split-level-seat trigger.
                    _sb_empty.append((s.ref or "?", lo, hi, nlo, nhi,
                                      level, _nc))
                else:
                    new = min(max(level, ilo), ihi)
                    if new != level:
                        _sb_moved.append((s.ref or "?", level, new,
                                          nlo, nhi, _nc))
                    # The box is documented as "the interval the seat was
                    # chosen from"; narrowing it with the level is what
                    # stops the coupler putting the seat straight back
                    # above the node ceiling.
                    level, lo, hi = new, ilo, ihi
        else:
            box = _frontage_box(ring)
            if box is not None:
                lo, hi = box
                level = min(de, hi) if de is not None else hi
            else:                                    # no apron-shared edge / off
                level = _median(ring, de)
                if level is None:
                    level = float(lv)                # off-network → fallback
                # Box = the band intersected over the pad's own ring, so the
                # coupling can still move a fallback pad within its reachable
                # range (an immovable DEM-low seat forced the serving spine
                # 5 m below its own profile — building26).
                blos = [b[0] for (x, y) in ring
                        if (b := band(x, y)) is not None]
                bhis = [b[1] for (x, y) in ring
                        if (b := band(x, y)) is not None]
                if bhis:
                    lo, hi = min(max(blos), min(bhis)), min(bhis)
                else:
                    lo = hi = level                  # off-network: immovable
        pads.append((s, ring, float(level), lo, hi))

    if _sb_moved or _sb_empty:
        _report(f"  [seat-band] clamped {len(_sb_moved)} full-frontage seat(s)"
                f" into their own node band; {len(_sb_empty)} pad(s) have NO "
                f"common level (split-level-seat trigger)")
        for (ref, was, now, nlo, nhi, nc) in sorted(
                _sb_moved, key=lambda r: -abs(r[2] - r[1]))[:12]:
            _report(f"  [seat-band]   {ref}: {was:.3f} -> {now:.3f} "
                    f"({now - was:+.3f} m) node band [{nlo:.3f},{nhi:.3f}] "
                    f"over {nc} contact node(s)")
        for (ref, lo_, hi_, nlo, nhi, lvl, nc) in _sb_empty:
            _report(f"  [seat-band]   EMPTY {ref}: frontage [{lo_:.3f},"
                    f"{hi_:.3f}] vs node band [{nlo:.3f},{nhi:.3f}] over "
                    f"{nc} contact node(s); seat kept at {lvl:.3f} "
                    f"— NOT a lawful level, needs sectioned seats")

    # ── MERGED RIGID UNITS — STANDING LAW (owner; the coupling lane's
    # recorded defect class) ────────────────────────────────────────────
    # Pads that share a ring vertex are ONE flat group in the projection,
    # and the relation is TRANSITIVE — a chain of touching buildings is a
    # single rigid body.  The projection seats such a body at ONE level (it
    # broadcasts the group's mean), so a coupler that let its members take
    # different levels was choosing values the projection would overwrite.
    # KCLT: one 6-pad chain, 15 pairs at budget 0.  HECA: more.
    #
    # The law is enforced STRUCTURALLY here, not as an inequality the POCS
    # has to converge to: the members collapse into ONE seat variable with
    # ONE box, so there is no |L_i − L_j| ≤ 0 pair left to approximate and
    # no group mean for the projection to mint afterwards.
    units, unit_of, _u_rows = _merge_rigid_units(pads, cps)
    if _u_rows:
        _report(f"  [seat-rigid] {len(_u_rows)} MERGED RIGID unit(s) "
                f"covering {sum(len(r['members']) for r in _u_rows)} pad(s) "
                f"seated at ONE level each (pads sharing a ring vertex, "
                f"transitively)")
        for r in sorted(_u_rows, key=lambda r: -len(r["members"]))[:12]:
            _report(f"  [seat-rigid]   {{{', '.join(r['refs'])}}} target "
                    f"{r['level']:.3f} m, box [{r['lo']:.3f},{r['hi']:.3f}]"
                    f"{'  EMPTY member-box intersection' if r['empty'] else ''}")

    # ── SEAT COUPLING (user 2026-07-03): jointly-feasible unit levels ────────
    # Each pad pins nearby spine/apron nodes to ``seat ± 1%·d`` (the building↔
    # spine law, never blended/relaxed), so two units across shared pavement
    # must satisfy ``|L_i − L_j| ≤ budget`` — independent seats left
    # neighbouring pads ≤2.6 m apart and made the surrounding faces infeasible
    # (the SPJC >3% class; the feasibility audit proves joint levels exist).
    # Project the independent targets onto the coupled polytope (POCS, same
    # solver as the no-building apron seats).
    #
    # THE BUDGET IS THE ROUTE BUDGET — the min-budget path on the
    # within-shape law graph ``feasibility_project`` enforces (see the
    # ROUTE-PRICED banner at the top of this module).  Admission is route
    # reachability inside the horizon; the chord corridor and the
    # pavement-visibility fraction are RETIRED as predicates and survive
    # only as the census that makes each pair's tightening adjudicable.
    if len(units) >= 2:
        from auto_patch.config import APRON_MAX_GRADE
        from auto_patch.grade_law import BUILDING_REACH_CORRIDOR_M
        if law_graph is None:
            # NOT a fallback.  The coupler has exactly one metric; without
            # the law graph it cannot price at all, and pricing on a chord
            # instead is the two-instrument defect this law removed.
            _report("  [seat-couple] WIRING DEFECT: the solve passed no law "
                    "graph — the coupler cannot price on the metric the "
                    "projection enforces, so NO pair is coupled this build")
            pairs: dict = {}
            _rdiag = None
        else:
            _unit_nodes = [set() for _ in units]
            for k, (_s, _ring, *_r) in enumerate(pads):
                _g = _unit_nodes[unit_of[k]]
                for (x, y) in _ring:
                    _i = bucket_to_idx.get(
                        cps.get_or_add(float(x), float(y)))
                    if _i is not None:
                        _g.add(_i)
            pairs, _rdiag = _pad_route_budgets(law_graph, _unit_nodes,
                                               n_nodes=n_nodes)
        _chord_lim: dict = {}
        if _rdiag is not None:
            # THE CHORD CENSUS (report only — it admits nothing).  The
            # rejection frame the dossier quoted (HECA 2 613 `gap>corridor`,
            # HEAZ 7) is re-quoted here against route admission, and
            # `not_visible` is 0 BY CONSTRUCTION: the predicate is gone.
            _chord_far = 0
            _far_admitted = 0
            _far_worst = 0.0
            for i in range(len(units)):
                pi = units[i]["polygon"]
                for j in range(i + 1, len(units)):
                    gap = pi.distance(units[j]["polygon"])
                    if gap > BUILDING_REACH_CORRIDOR_M:
                        _chord_far += 1
                    if (i, j) in pairs:
                        _chord_lim[(i, j)] = APRON_MAX_GRADE * gap
                        if gap > BUILDING_REACH_CORRIDOR_M:
                            _far_admitted += 1
                            _far_worst = max(_far_worst, gap)
            _tight = [(k, pairs[k], _chord_lim[k]) for k in pairs
                      if k in _chord_lim and pairs[k] < _chord_lim[k] - 1e-9]
            _loose = [k for k in pairs
                      if k in _chord_lim and pairs[k] > _chord_lim[k] + 1e-9]
            _npairs_all = len(units) * (len(units) - 1) // 2
            _report(
                f"  [seat-couple] ROUTE METRIC: {len(units)} unit(s) over "
                f"{len(pads)} pad(s), {len(pairs)} coupled pair(s) of "
                f"{_npairs_all} (horizon {_rdiag['horizon_m']:.2f} m of "
                f"budget = {_rdiag['dial_m']:.0f} m at the apron cap; law "
                f"graph {_rdiag['graph_nodes']} node(s) / "
                f"{_rdiag['graph_edges']} edge(s), RAW law budgets)")
            _report(
                f"  [seat-couple]   rejection census: route-unreachable "
                f"{_rdiag['unreachable']}, unit off the law graph "
                f"{_rdiag['off_graph']}, not_visible 0 (predicate retired); "
                f"the chord frame would have rejected {_chord_far} as "
                f"gap>corridor")
            if _rdiag["merged_pairs"]:
                # The rigid-unit collapse above already merged every pad
                # pair that shares a ring vertex, so the projection's own
                # node-set contraction must find nothing left to merge.
                # If it does, the two relations disagree — name it.
                _report(
                    f"  [seat-couple]   WIRING DEFECT: the law graph's "
                    f"flat-group contraction merged {_rdiag['merged_pairs']} "
                    f"further pair(s) across {_rdiag['merged_groups']} "
                    f"group(s) that the rigid-unit law did not — the two "
                    f"share-relations disagree")
            # THE DIAL'S UNITS, MEASURED (never assumed).  Admission is the
            # 200 m corridor expressed in the BUDGET metric, so a route over
            # cheap pavement — flat-cross edges, and the FLAT shapes and
            # merged pad chains that cost nothing at all — can reach far past
            # 200 m of ground distance.  That population is counted here so
            # the dial's unit choice is adjudicable on evidence.
            _report(
                f"  [seat-couple]   reach: {_far_admitted} admitted pair(s) "
                f"lie beyond the {BUILDING_REACH_CORRIDOR_M:.0f} m chord "
                f"corridor (worst {_far_worst:.0f} m apart)")
            _report(
                f"  [seat-couple]   budget vs chord: {len(_tight)} "
                f"TIGHTENED, {len(_loose)} loosened, "
                f"{len(pairs) - len(_tight) - len(_loose)} equal; "
                f"{_rdiag['lazy_entries']} certified-lazy entry(ies) "
                f"contribute ring edges only, {_rdiag['interval_edges']} "
                f"interval edge(s) excluded (one-sided slabs)")
            # TIGHTENING, ATTRIBUTED (never consumed).  The margin frame is
            # retired, so there is nothing left to split: every metre of
            # tightening below is the LAW's route being shorter than the
            # chord.  The line stays because the magnitude is the evidence
            # that the route metric — not the chord — is what binds.
            _tot_tight = sum(cb - rb for (_k, rb, cb) in _tight)
            _report(
                f"  [seat-couple]   tightening attribution: "
                f"{_tot_tight:.3f} m total across {len(_tight)} pair(s), "
                f"ALL of it the RAW law route (no margin frame exists)")
            for ((i, j), rb, cb) in sorted(_tight,
                                           key=lambda r: r[1] - r[2])[:12]:
                _report(f"  [seat-couple]     tightened "
                        f"{units[i]['ref']} <-> {units[j]['ref']}"
                        f" route {rb:.4f} m vs chord {cb:.4f} m "
                        f"({rb - cb:+.4f})")
            # ── BUDGET IDENTITY — the coupler's own certificate ─────────
            if _rdiag["ident_over"]:
                _report(f"  [seat-couple]   BUDGET-IDENTITY VIOLATION: "
                        f"{len(_rdiag['ident_over'])} pair(s) disagree by "
                        f">1 % between their two endpoints — this is a STOP, "
                        f"not a tolerance to widen")
                for (i, j, dab, dba) in _rdiag["ident_over"][:12]:
                    _report(f"  [seat-couple]     {units[i]['ref']} "
                            f"<-> {units[j]['ref']}: {dab:.6f} vs "
                            f"{dba:.6f} m")
            else:
                _report(f"  [seat-couple]   budget identity OK: worst "
                        f"disagreement {100.0 * _rdiag['ident_worst']:.4f} % "
                        f"over {len(pairs)} pair(s) (limit 1 %)")
        if pairs:
            targets = [u["level"] for u in units]
            boxes = [(u["lo"], u["hi"]) for u in units]
            L = _pocs_project_levels(targets, boxes, pairs)
            _dbg = _os.environ.get("O4_SEAT_DEBUG") == "1"
            if _dbg:
                pre = sorted(
                    ((abs(targets[i] - targets[j]) - lim, i, j, lim)
                     for (i, j), lim in pairs.items()), reverse=True)
                print(f"  [seats] {len(units)} units, {len(pairs)} coupled "
                      f"pairs, polytope "
                      f"{'FEASIBLE' if L is not None else 'EMPTY'}")
                for ex, i, j, lim in pre[:8]:
                    if ex <= 0:
                        break
                    print(f"    pre-conflict {ex:+.2f}m over lim {lim:.2f}: "
                          f"{units[i]['ref']} t={targets[i]:.2f} "
                          f"box=({units[i]['lo']:.2f},{units[i]['hi']:.2f})"
                          f"  vs  {units[j]['ref']} t={targets[j]:.2f} "
                          f"box=({units[j]['lo']:.2f},{units[j]['hi']:.2f})")
            if L is not None:
                moved = sum(1 for k in range(len(units))
                            if abs(L[k] - targets[k]) > 0.01)
                if moved:
                    _report(f"  [seats] coupled {len(units)} unit(s) / "
                            f"{len(pairs)} pairs: moved {moved}, max "
                            f"{max(abs(L[k] - targets[k]) for k in range(len(units))):.2f} m")
                for k in range(len(units)):
                    units[k]["level"] = float(L[k])
            else:
                # ── EMPTY POLYTOPE → LOUD ATTRIBUTION (spec dossier-fixes
                # §4; RULINGS 2026-08-04 split-level building seats: "an
                # empty coupling polytope is LOUD attribution, never a
                # silent ship") ────────────────────────────────────────
                # The values are UNCHANGED — the fix is the sectioned seat,
                # its own spec.  What changes is that the ship is no longer
                # silent: ``feasibility-is-guaranteed`` forbids
                # infeasibility as an ANSWER, so the units, the gap and the
                # footprint RELIEF (the quantity the split-level law
                # thresholds on) are named.
                if _dbg:
                    print("  [seats] EMPTY polytope -> independent seats kept")
                from auto_patch.elevation_per_surface.building_feasibility \
                    import _footprint_dem_relief
                _relief: dict = {}

                def _rel(k):
                    if k not in _relief:
                        r = _footprint_dem_relief(units[k]["polygon"], dem_fn)
                        _relief[k] = None if r is None else float(r[1])
                    return _relief[k]

                conflicts = sorted(
                    ((abs(targets[i] - targets[j]) - lim, i, j, lim)
                     for (i, j), lim in pairs.items()
                     if abs(targets[i] - targets[j]) - lim > 0.0),
                    reverse=True)
                _report(f"  [seat-couple] EMPTY POLYTOPE: {len(units)} "
                        f"unit(s) / {len(pairs)} coupled pair(s) admit NO "
                        f"jointly-feasible seat set; independent seats kept, "
                        f"so {len(conflicts)} pair(s) SHIP violating their "
                        f"own coupling limit")
                # Every conflict row also carries the CHORD limit it would
                # have had, so a rise in shipping-in-violation is accounted
                # pair by pair as honestly-tightened budget rather than
                # waved through.
                for (ex, i, j, lim) in conflicts[:200]:
                    ri, rj = _rel(i), _rel(j)
                    gap_ij = units[i]["polygon"].distance(units[j]["polygon"])
                    cb = _chord_lim.get((i, j))
                    if cb is None:
                        split = ""
                    else:
                        if lim < cb - 1e-9:
                            _tag = "TIGHTENED"
                        elif lim > cb + 1e-9:
                            _tag = "loosened"
                        else:
                            _tag = "equal"
                        split = f" chord_lim={cb:.3f} ({_tag})"
                    _report(
                        f"  [seat-couple]   {units[i]['ref']} "
                        f"{targets[i]:.3f} <-> {units[j]['ref']} "
                        f"{targets[j]:.3f}  gap={gap_ij:.1f} m "
                        f"|dL|={abs(targets[i] - targets[j]):.3f} "
                        f"lim={lim:.3f}{split} excess={ex:+.3f} m  ring relief"
                        f" {'n/a' if ri is None else format(ri, '.2f')} / "
                        f"{'n/a' if rj is None else format(rj, '.2f')} m")

    # THE UNIT'S LEVEL IS THE PAD'S LEVEL.  A merged rigid unit broadcasts
    # ONE value to every member pad — that IS the law; the box narrows to
    # the unit's box for the same reason (a member may not yield outside
    # the interval the unit was seated from).
    pads = [(s, ring, float(units[unit_of[k]]["level"]),
             units[unit_of[k]]["lo"], units[unit_of[k]]["hi"])
            for k, (s, ring, _t, _lo, _hi) in enumerate(pads)]

    seats: dict = {}
    seat_boxes = _store_of(layout).raw("seat_boxes")
    for (s, ring, level, lo, hi) in pads:
        # BOUNDED YIELD box (owner ruling 2026-07-29): the pad's box is the
        # ``[lo, hi]`` its seat was chosen from, WIDENED to include the
        # chosen level — an uncoupled seat is ``min(DEM, hi)`` and may rest
        # below ``lo``, and the box must never move a resting seat (the
        # clamp refines the yield, it is not a new hold).  A ring node
        # shared by two pads keeps the tighter interval per side.
        blo = min(float(lo), float(level))
        bhi = max(float(hi), float(level))
        for (x, y) in ring:
            k = cps.get_or_add(float(x), float(y))
            i = bucket_to_idx.get(k)
            if i is not None:
                seats[i] = float(level)
            prev = seat_boxes.get(k)
            seat_boxes[k] = ((blo, bhi) if prev is None
                             else (max(prev[0], blo), min(prev[1], bhi)))
    return seats


# ══════════════════════════════════════════════════════════════════════
# DETACHED (NON-AIRSIDE-SERVED) BUILDING PADS — THE GROUNDSIDE LAW
# ══════════════════════════════════════════════════════════════════════
# Item 3(b), 2026-08-05.  ``build_detached_pad_dem_pins`` lived here: it
# HARD-pinned every non-airside-served ROLE_BUILDING pad at the MEDIAN of
# its raw DEM samples for the whole solve.  That is DEM as a constraint by
# the ruling's own definition ("DEM chooses WHERE in the lawful band a
# thing seats.  It never shapes the band, never constrains, never
# blocks."), and it fails the constant-DEM oracle head-on: with DEM ≡ c
# every detached pad is frozen at ``c`` while the groundside pavement it
# is welded into sits wherever the airside solve put it — an arbitrarily
# large step at a shared node, on ground with no relief.
#
# ── THE DEFECT THE PIN WAS MASKING, ATTRIBUTED ───────────────────────
# The pin's justification was measured and real: unpinned, "the
# route-profile blend paints them with the surrounding airside level"
# (KBNA: pads emitted flat at 170-172 over 158-167 ground).  The writer
# is NOT the blend.  Read in order:
#
#   1. ``raster_reach_band._domain_geom`` puts ROLE_BUILDING in the reach
#      band's PROPAGATION DOMAIN unconditionally — with no airside-service
#      test of any kind — and the propagation is a GRID walk over the
#      paved mask (plus a bounded off-mask radius,
#      ``RASTER_REACH_BAND_OFFNET_RADIUS_M``).
#   2. ``building_feasibility.spine_value_fields`` gives that grid its
#      values: ``floor[i] = max over runway anchors (value_a − route
#      budget)`` — the level a node must be AT LEAST for the runway to be
#      reachable within grade.  An airside law, about airside pavement.
#   3. So a pad that ``building_feasible_levels`` REFUSED to seat (its
#      airside-touch test: distance to a ≥``BUILDING_AIRSIDE_CONTACT_MIN_
#      COMPONENT_M2`` airside component ≤ ``_TOUCH_TOL_M``) still receives
#      a ``node_band`` whose FLOOR is that airside floor.  Two instruments,
#      one assumed population — the seat's notion of "served" is a route /
#      component test, the band's is grid connectivity over a mask the pad
#      is itself a member of.
#   4. ``one_solve.one_profile_solve`` then WRITES it, twice: the warm
#      start ``elev[i] = _dem_target(i) = clamp(DEM, floor, ceil)`` lifts
#      the pad's DEM straight to that airside floor, and every sweep
#      re-clamps into ``lo_e = max(n_lo, floor[i])`` so it stays there.
#      The pad emits FLAT at the airside level because all its ring nodes
#      share (nearly) the same floor.
#
# The harmonic/mean blend has no altitude preference of its own (solve.py
# says so where it owns 67.1 % of the corridor's DEM departure); the BAND
# FLOOR is the writer.  Fixing it at source therefore means: a pad the
# airside law does not serve does not get the airside band.
#
# ── THE LAW THAT REPLACES THE PIN ────────────────────────────────────
# A detached pad is a GROUNDSIDE object (owner: groundside terrace law +
# adjacent-ground zone law).  Its datum is the surface it actually abuts —
# the groundside pavement / service road / apron ring it welds into — read
# as SOLVED VARIABLES, the same datum family as the groundside mouth
# ceiling (item 3(a)) and the same resolution pattern as
# the adjacent-ground FOOT rule (foot on the host ring, interpolated between
# two solved ring variables; identity when the pad shares the host's
# vertex).  Buildings are FLAT, so the pad's lawful levels are the
# INTERSECTION over its contacts of ``[datum − cap·d, datum + cap·d]``,
# and the DEM seed picks the point inside it.
#
# CONSTANT-DEM ORACLE, BY INSPECTION.  Every term of the box is a solved
# pavement variable or a law constant — no DEM appears in it, so the box
# is whatever the law grants in BOTH worlds.  The only DEM-dependent step
# is which point of the box the pad seats at, which is precisely the role
# the ruling assigns the DEM: with DEM ≡ 1 m the seed is below the box and
# the pad seats at ``lo`` (its FLOOR); with DEM ≡ 10 000 m it seats at
# ``hi`` (its CEILING) — the ADDENDUM's extreme-seating assertion, and the
# band-width field at those nodes reads exactly ``hi − lo``.  A pad with NO
# resolvable host has an unbounded box and simply keeps its seed: no law
# binds it, and a missing datum never becomes a terrain bound.

#: Solved pavement roles a DETACHED pad may take its datum from.  Wider
#: than ``_PAD_HOST_ROLES`` (which serves the post-solve airside re-level)
#: by exactly the groundside classes — a detached pad's host is normally a
#: lot or a service road, which is why that pass never found one for it.
_DETACHED_PAD_HOST_ROLES = None       # bound lazily (import cycle-free)


def _detached_pad_host_roles():
    from auto_patch.layout import (
        ROLE_APRON, ROLE_CROSS_CONNECTOR, ROLE_GROUNDSIDE_PAVEMENT,
        ROLE_JUNCTION, ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
        ROLE_SERVICE_JUNCTION, ROLE_SERVICE_ROAD, ROLE_STUB)
    global _DETACHED_PAD_HOST_ROLES
    if _DETACHED_PAD_HOST_ROLES is None:
        _DETACHED_PAD_HOST_ROLES = frozenset({
            ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD,
            ROLE_SERVICE_JUNCTION, ROLE_APRON, ROLE_JUNCTION,
            ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
            ROLE_STUB, ROLE_CROSS_CONNECTOR})
    return _DETACHED_PAD_HOST_ROLES


#: Contact radius (m) for the pad→host datum march.  The pad and its host
#: normally share ring geometry outright (d = 0); this only has to bridge
#: the slice's weld tolerance, so it is the same 2.5 m the landed
#: ``PAD_HOST_LEVEL_CONTACT_M`` uses for the airside twin.
DETACHED_PAD_HOST_CONTACT_M = 2.5


def detached_pad_nodes(layout, bucket_to_idx, building_seats):
    """``[(shape, [node_idx, ...])]`` — every ROLE_BUILDING pad that is NOT
    airside-served (no ring node in ``building_seats``).

    The membership test is unchanged from the deleted DEM-pin builder: the
    seat producer (``building_feasible_levels``) owns the airside-service
    decision, and this reads its verdict rather than re-deriving it (one
    instrument, one population)."""
    from auto_patch.layout import ROLE_BUILDING
    cps = layout.canonical_points
    out: list = []
    for s in layout.shapes:
        if (s.role != ROLE_BUILDING or s.polygon is None
                or s.polygon.is_empty):
            continue
        ring = _open_ring(list(s.polygon.exterior.coords))
        idx = [bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
               for (x, y) in ring]
        idx = [i for i in idx if i is not None]
        if not idx:
            continue
        if any(i in building_seats for i in idx):
            continue                        # airside-served → seated
        out.append((s, sorted(set(idx))))
    return out


#: Shape roles whose law edges constitute AIRSIDE FRONTAGE for a building
#: (owner ruling 2026-08-06, "Frontage coupling ⇒ band seating").  A
#: building chord to one of these is the frontage relationship the apron
#: has to grade smoothly to; groundside lots and service roads are NOT —
#: a building that only abuts those is the pure groundside citizen the
#: ruling exempts.
_FRONTAGE_AIRSIDE_FAMILY_PREFIXES = (
    "unified:apron", "unified:junction", "unified:runway",
    "unified:primary_parallel", "unified:secondary_parallel",
    "unified:stub", "unified:cross_connector", "unified:taxiway",
    "unified:graded_strip",
)


def detached_pad_frontage_coupling(pads, unified_graph, near_miss_edges=None):
    """``{pad_ordinal: ((partner_node, budget_m), ...)}`` — each detached
    pad's FRONTAGE COUPLING to airside, or an absent entry when it has
    none.

    OWNER RULING 2026-08-06 ("Frontage coupling ⇒ band seating"): *"A
    building close enough to have frontage and be coupled with the apron
    has to be seated based on the route graph that allows the apron to
    grade smoothly to its frontage within the apron's grade law."*  The
    ruling also re-keys the band withholding itself: it keys on FRONTAGE
    COUPLING, not on touch.

    Two couplings count, and the ruling names both:

    * TOUCHING — the pad's ring node carries a law chord owned by an
      airside pavement shape (``_FRONTAGE_AIRSIDE_FAMILY_PREFIXES``).
      That chord IS the frontage chord: the unified graph mints it from
      the owning shape's own all-pair law.
    * NEAR-MISS — the pad↔apron edge the near-miss frontage law mints
      across a sub-metre unpaved sliver
      (:func:`near_miss_building_frontage_edges`).  Ruling item 3 names
      this as the half-landed law: the EDGE was minted without extending
      the SEAT derivation.  This function is that missing half's input.

    The budget carried back is the edge's own — the apron cap over the
    chord — so the caller can price exactly how far off the partner's
    band the pad may lawfully sit.  Tightest budget wins on a duplicate
    pair, the same rule the projection applies.

    Pure lookup over edge lists already built; no geometry pass.
    """
    pad_of: dict = {}
    for ordinal, (_s, idx) in enumerate(pads):
        for i in idx:
            pad_of[i] = ordinal
    if not pad_of:
        return {}
    out: dict = {}

    def _note(ordinal, partner, budget):
        if budget is None or budget < 0:
            return
        row = out.setdefault(ordinal, {})
        prev = row.get(partner)
        if prev is None or budget < prev:
            row[partner] = float(budget)

    edges = getattr(unified_graph, "edges", None) or ()
    families = getattr(unified_graph, "edge_family", None) or ()
    for (a, b, cap, _sp), fam in zip(edges, families):
        if not str(fam).startswith(_FRONTAGE_AIRSIDE_FAMILY_PREFIXES):
            continue
        pa, pb = pad_of.get(a), pad_of.get(b)
        if (pa is None) == (pb is None):
            continue                    # both pad nodes, or neither
        pos = getattr(unified_graph, "pos", {})
        if a not in pos or b not in pos:
            continue
        from auto_patch import grade_graph as _GGf
        budget = cap.at(_GGf._dist(pos[a], pos[b]), 0.0)
        if pa is not None:
            _note(pa, b, budget)
        else:
            _note(pb, a, budget)
    for (apron_node, pad_node, budget) in (near_miss_edges or ()):
        ordinal = pad_of.get(pad_node)
        if ordinal is not None:
            _note(ordinal, apron_node, budget)
    return {k: tuple(v.items()) for k, v in out.items()}


def withhold_airside_band_from_detached_pads(node_band, pads, n=None,
                                             frontage_coupled=None):
    """Hand every detached-pad node ``None`` in ``node_band`` — the AIRSIDE
    reach band is not its law.  Returns ``(withheld_nodes, n_kept_pads)``.

    This was the source fix for the plateau defect attributed above: the
    band floor is what wrote the surrounding airside level onto a pad no
    airside route serves.  ``None`` is the band's own established value
    for "this node's law is elsewhere" — the identical treatment
    ``node_bands(skip_from=...)`` gives adjacent-ground zone vertices.

    CYCLE-7 FIX 2, OWNER RULING 2026-08-06: the withholding KEYS ON
    FRONTAGE COUPLING, NOT ON TOUCH.  The unconditional form was
    over-broad — HECA's ``building172`` carries an ordinary 1 %-cap apron
    chord (budget 0.0646 m over 6.46 m) and still had its band withheld,
    which left it seated on a groundside/DEM datum at 1.6576 m against an
    apron banded from 62.495 m: a permanent clamp/sweep 2-cycle worth
    60.772738 m, the worst residual in the whole solve.  A pad WITH
    frontage coupling keeps its band and is seated from it
    (:func:`seat_detached_pads_by_law`); only a pad with NO frontage
    coupling is the pure groundside citizen the ruling exempts — it seats
    at DEM, terraces freely and affects nothing airside.

    ``frontage_coupled=None`` restores the unconditional pre-ruling
    behaviour (no coupling information ⇒ nothing can be exempted).
    """
    limit = len(node_band) if n is None else min(n, len(node_band))
    withheld: set = set()
    kept = 0
    for ordinal, (_s, idx) in enumerate(pads):
        if frontage_coupled and frontage_coupled.get(ordinal):
            kept += 1
            continue                    # frontage-coupled: the band IS its law
        for i in idx:
            if 0 <= i < limit:
                node_band[i] = None
                withheld.add(i)
    return withheld, kept


def _foot_on_ring(px, py, coords):
    """``(t, ia, ib, d)`` — the nearest point on a closed ring polyline to
    ``(px, py)``: the bracketing vertex INDEXES into ``coords`` (open
    ring), the segment parameter, and the distance.  ``None`` for a
    degenerate ring."""
    n = len(coords)
    if n < 2:
        return None
    best = None
    for a in range(n):
        b = (a + 1) % n
        ax, ay = coords[a]
        bx, by = coords[b]
        vx, vy = bx - ax, by - ay
        vv = vx * vx + vy * vy
        if vv <= 1e-12:
            t = 0.0
            fx, fy = ax, ay
        else:
            t = ((px - ax) * vx + (py - ay) * vy) / vv
            t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
            fx, fy = ax + t * vx, ay + t * vy
        d = math.hypot(px - fx, py - fy)
        if best is None or d < best[3]:
            best = (t, a, b, d)
    return best


def detached_pad_law_box(layout, bucket_to_idx, elev, pad_shape, pad_idx,
                         cap, contact_m=None):
    """``(lo, hi, n_contacts, n_conflict)`` — the lawful FLAT levels of one
    detached pad, from SOLVED host-pavement variables only.

    For every pad ring vertex the march finds the nearest point on a
    neighbouring non-building pavement ring within ``contact_m`` and reads
    the datum as ``(1−t)·elev[a] + t·elev[b]`` — two solved ring variables,
    exactly the adjacent-ground foot rule (and its identity case
    when the pad shares the host's vertex, where ``t`` lands on an end and
    ``d`` is 0).  Each contact contributes ``[datum − cap·d, datum + cap·d]``
    and the box is their INTERSECTION.

    An EMPTY intersection is a DECLARED CONFLICT, never silently resolved:
    it is the split-level-seat law's trigger (RULINGS 2026-08-04 — a pad
    whose contacts cannot all be met by one flat level needs sectioning).
    As the retired zone box did, the first claimant's box is kept and
    the conflict is counted for the caller to report.

    ``(None, None, 0, 0)`` when no host resolves — NO BOX, not a DEM
    fallback."""
    cps = layout.canonical_points
    contact = (DETACHED_PAD_HOST_CONTACT_M if contact_m is None
               else float(contact_m))
    poly = pad_shape.polygon
    # BBOX PREFILTER before the shapely distance: a big airport carries
    # thousands of candidate-role shapes and this runs per pad, so the
    # exact test is only paid by the handful that could possibly touch.
    p_minx, p_miny, p_maxx, p_maxy = poly.bounds
    p_minx -= contact
    p_miny -= contact
    p_maxx += contact
    p_maxy += contact
    hosts = []
    for h in layout.shapes:
        if h.role not in _detached_pad_host_roles():
            continue
        if h.polygon is None or h.polygon.is_empty or h is pad_shape:
            continue
        h_minx, h_miny, h_maxx, h_maxy = h.polygon.bounds
        if (h_minx > p_maxx or h_maxx < p_minx
                or h_miny > p_maxy or h_maxy < p_miny):
            continue
        try:
            if poly.distance(h.polygon) > contact:
                continue
        except Exception:                              # pragma: no cover
            continue
        hcoords = _open_ring(list(h.polygon.exterior.coords))
        if len(hcoords) < 2:
            continue
        hidx = [bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
                for (x, y) in hcoords]
        hosts.append((hcoords, hidx))
    if not hosts:
        return None, None, 0, 0

    n_elev = len(elev)
    lo = hi = None
    n_contacts = n_conflict = 0
    ring = _open_ring(list(poly.exterior.coords))
    for (px, py) in ring:
        best = None
        for (hcoords, hidx) in hosts:
            foot = _foot_on_ring(px, py, hcoords)
            if foot is None:
                continue
            t, ia, ib, d = foot
            if d > contact:
                continue
            i_a, i_b = hidx[ia], hidx[ib]
            if i_a is None or i_b is None or i_a >= n_elev or i_b >= n_elev:
                continue
            datum = (1.0 - t) * elev[i_a] + t * elev[i_b]
            if best is None or d < best[1]:
                best = (float(datum), float(d))
        if best is None:
            continue
        datum, d = best
        n_contacts += 1
        c_lo, c_hi = datum - cap * d, datum + cap * d
        if lo is None:
            lo, hi = c_lo, c_hi
            continue
        n_lo, n_hi = max(lo, c_lo), min(hi, c_hi)
        if n_lo > n_hi:
            n_conflict += 1                 # declared, first claimant kept
            continue
        lo, hi = n_lo, n_hi
    if lo is None:
        return None, None, 0, 0
    return lo, hi, n_contacts, n_conflict


def frontage_band_seat_interval(pad_idx, coupling, node_band):
    """``(lo, hi, n_couplings)`` — the flat levels the FRONTAGE BAND admits
    for one detached pad, or ``(None, None, 0)`` when nothing resolves.

    CYCLE-7 FIX 2, and the measurement that forced it.  A detached pad's
    seat box is built by ``detached_pad_law_box``'s CONTACT MARCH, whose
    horizon is ``DETACHED_PAD_HOST_CONTACT_M`` = 2.5 m.  The LAW GRAPH has
    no such horizon: HECA's ``building172`` sits 6.46 m from apron node
    5037 and carries an ordinary 1 %-cap law edge to it (budget 0.0646 m)
    — outside the march, inside the law.  The march therefore saw only
    groundside pieces at d ≈ 0, minted the box ``[datum, datum]`` (ZERO
    WIDTH, at 1.6576 m in a DEM ≡ 1 world), and the projection then had a
    groundside/DEM datum installed as a HARD bound on an airside apron
    edge whose own band floors at 62.495 m.  Every sweep moved both ends
    by ±30.4 m and the clamps restored them exactly: a permanent 2-cycle,
    residual 60.772738 m, bit-identical at sweep 1 and at sweep 49,600 —
    100 % of the worst residual in the whole HECA solve, and invisible to
    any amount of convergence work.

    That box violates two standing rulings at once — "DEM is a seed,
    never a constraint" and "groundside must never pull airside" — and
    cycle-6 Part P's band-wins door does not cover it, because the pad
    has no band AT ALL (``withhold_airside_band_from_detached_pads``
    hands every detached pad ``None``).

    THE LAW THIS FUNCTION STATES (owner ruling 2026-08-06, "Frontage
    coupling ⇒ band seating"): *"A building close enough to have frontage
    and be coupled with the apron has to be seated based on the route
    graph that allows the apron to grade smoothly to its frontage within
    the apron's grade law."*  Read forward, that is arithmetic: a pad
    coupled to a banded partner by a frontage chord of budget ``B`` may
    lawfully sit anywhere in ``[band_lo − B, band_hi + B]`` — any level
    in there lets the chord grade within the apron's own law to some
    in-band partner value — and the pad's seat is the INTERSECTION of
    that over all its frontage couplings.

    ONE band (``reach_band_unified``) is the authority for a partner's
    lawful range — never its current VALUE, which is a solve state and
    not a law.  ``coupling`` is the pad's frontage set from
    :func:`detached_pad_frontage_coupling`, which has already excluded
    intra-pad pairs (a rigid flat group cannot constrain its own level).

    An EMPTY intersection (``lo > hi``) means two frontage couplings no
    single flat level can meet — the SPLIT-LEVEL SEAT law's trigger
    (RULINGS 2026-08-04), reported LOUD by the caller, never silently
    resolved.  ``n_couplings == 0`` with a non-empty ``coupling`` means
    the frontage band could not be DERIVED (no banded partner): also
    loud, and never a fallback to the DEM datum pin.
    """
    lo = hi = None
    n_couplings = 0
    for (j, budget) in coupling or ():
        band = node_band[j] if 0 <= j < len(node_band) else None
        if band is None or band[0] is None or band[1] is None:
            continue
        n_couplings += 1
        b_lo = float(band[0]) - float(budget)
        b_hi = float(band[1]) + float(budget)
        lo = b_lo if lo is None else max(lo, b_lo)
        hi = b_hi if hi is None else min(hi, b_hi)
    if not n_couplings:
        return None, None, 0
    return lo, hi, n_couplings


def seat_detached_pads_by_law(layout, bucket_to_idx, elev, pads, cap,
                              frontage_coupled=None, node_band=None):
    """Seat every detached pad FLAT at the law level nearest its seed.

    Runs AFTER the groundside passes (``apply_groundside_reach`` /
    ``apply_service_road_dem_follow``), because a groundside object's datum
    is a SOLVED groundside variable and groundside conforms to airside —
    the pad is therefore the last thing seated, which is the architectural
    order, not a convenience.

    Writes ``elev`` for the pad's ring nodes, registers the lawful box in
    the ``seat_boxes`` node-space store (the ratified bounded-yield channel
    — the pad then rides fp#8's and the final projection's group bounds
    with no new machinery), and returns
    ``({node_idx: level}, stats)`` with ``stats = (n_seated, n_unhosted,
    n_conflict)``.

    NOT HARD.  The pad joins the ordinary movable FLAT pad groups — it is a
    building, flatness is its law, and its box is what keeps it lawful.
    The deleted DEM pin's ``layout._detached_pad_node_idx`` exclusion
    existed only to protect a value the law did not choose.

    ``frontage_coupled`` / ``node_band`` — CYCLE-7 FIX 2, OWNER RULING
    2026-08-06 ("Frontage coupling ⇒ band seating").  A pad that carries
    a FRONTAGE COUPLING (touching or near-miss) is not a groundside
    citizen at all: it is seated FROM THE ROUTE-GRAPH BAND through its
    frontage chord (:func:`frontage_band_seat_interval`), and **no
    DEM-datum value may be a bound on it** — the contact box is not
    intersected in, it is not consulted, it is simply not its law.  DEM
    still chooses WHERE inside the derived range, which is the standing
    seed-not-bound rule.

    A frontage-coupled pad whose band interval cannot be DERIVED (no
    banded partner) or is EMPTY (two couplings no single flat level
    meets) is a LOUD DEFECT REPORT, and the pad is left UNBOUNDED on its
    seed — never falling back to the datum pin, which is the failure this
    fix exists to delete.  An empty interval is additionally the
    split-level sectioned-seat law's trigger (RULINGS 2026-08-04), which
    remains the relief for large intra-footprint relief.

    Omit either argument and no pad is treated as frontage-coupled, which
    is exactly the pre-ruling behaviour.

    Returns ``stats = (n_seated, n_unhosted, n_conflict, n_frontage_seated,
    n_frontage_underivable, n_split_level)``."""
    seats: dict = {}
    boxes = _store_of(layout).open_map("seat_boxes", "interval")
    cps = layout.canonical_points
    n_seated = n_unhosted = n_conflict = 0
    n_frontage = n_underivable = n_split = 0
    reconcile = frontage_coupled is not None and node_band is not None
    for ordinal, (s, idx) in enumerate(pads):
        coupling = (frontage_coupled or {}).get(ordinal) if reconcile else None
        if coupling:
            # ── THE FRONTAGE-COUPLED PATH: the band is its law ────────
            f_lo, f_hi, n_cpl = frontage_band_seat_interval(
                idx, coupling, node_band)
            if not n_cpl:
                n_underivable += 1      # LOUD; unbounded on its seed
                continue
            if f_lo > f_hi:
                n_split += 1            # LOUD; unbounded on its seed
                continue
            lo, hi = f_lo, f_hi
            n_frontage += 1
        else:
            lo, hi, n_c, n_x = detached_pad_law_box(
                layout, bucket_to_idx, elev, s, idx, cap)
            n_conflict += n_x
            if lo is None:
                n_unhosted += 1             # no datum → no box, no write
                continue
        vals = [elev[i] for i in idx if i < len(elev)]
        if not vals:
            continue
        seed = sum(vals) / len(vals)        # the DEM-seeded free value
        level = min(max(seed, lo), hi)      # DEM picks WHERE in the box
        for i in idx:
            if i < len(elev):
                elev[i] = level
                seats[i] = level
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            k = cps.get_or_add(float(x), float(y))
            prev = boxes.get(k)
            boxes[k] = ((lo, hi) if prev is None
                        else (max(prev[0], lo), min(prev[1], hi)))
        n_seated += 1
    return seats, (n_seated, n_unhosted, n_conflict,
                   n_frontage, n_underivable, n_split)


def _pocs_project_levels(targets, boxes, pairs, max_iter=300, tol=1e-4):
    """Project per-item target levels onto (box ∩ pairwise-coupling polytope).

    Find ``L_i`` minimising ``Σ(L_i − t_i)²`` s.t. ``|L_i − L_j| ≤ pairs[(i,j)]``
    and ``f_i ≤ L_i ≤ ce_i``.  Cyclic projection (POCS): push each violated pair
    together by half the excess, then re-clamp to the boxes; repeat.  Returns
    ``[L_i]`` on convergence, or ``None`` when the polytope is EMPTY (boxes
    incompatible with the couplings = the FUNDAMENTAL case)."""
    n = len(targets)
    L = [min(max(targets[i], boxes[i][0]), boxes[i][1]) for i in range(n)]
    for _ in range(max_iter):
        worst = 0.0
        for (i, j), lim in pairs.items():
            d = L[i] - L[j]
            if d > lim:
                e = 0.5 * (d - lim)
                L[i] -= e
                L[j] += e
                worst = max(worst, d - lim)
            elif -d > lim:
                e = 0.5 * (-d - lim)
                L[i] += e
                L[j] -= e
                worst = max(worst, -d - lim)
        for i in range(n):
            L[i] = min(max(L[i], boxes[i][0]), boxes[i][1])
        if worst <= tol:
            break
    ok = all(abs(L[i] - L[j]) <= lim + 1e-3
             for (i, j), lim in pairs.items())
    return L if ok else None


def _project_apron_contacts(targets, boxes, positions, cap,
                            max_iter=300, tol=1e-4):
    """Project per-feeder target levels onto (box ∩ apron-cap polytope):
    ``|L_i − L_j| ≤ cap·d_ij`` with ``d_ij`` = straight gap (a LOWER bound on
    the in-apron route, so the cap constraint is conservative).  See
    :func:`_pocs_project_levels` for the projection itself."""
    import math
    n = len(targets)
    pairs = {(i, j): cap * math.hypot(positions[i][0] - positions[j][0],
                                      positions[i][1] - positions[j][1])
             for i in range(n) for j in range(i + 1, n)}
    return _pocs_project_levels(targets, boxes, pairs,
                                max_iter=max_iter, tol=tol)


# Minimum apron area to ANCHOR a no-building apron (user 2026-06-30).  A
# sub-threshold apron is a decomposition fragment of a larger apron-blob, not a
# real expanse; pinning it to its DEM-feasible level over-constrains the network
# for no benefit, so it is left to flex with its feeders instead.  This replaces
# the old apron→junction demotion (which mutated role purely to dodge anchoring
# and broke the junction invariants on non-HECA airports).
_NOBUILD_APRON_SEAT_MIN_AREA_M2 = 2000.0


# ── APRON-CONTACT ANCHOR CAP — STANDING LAW ───────────────────────
# (seed-fix round §3; former gate ``O4_APRON_CONTACT_ANCHOR_CAP``, retired
# 2026-08-05 under RULINGS "BUILD-COMPLETE-THEN-DEBUG".)
#
# THE LAW.  :func:`build_nobuilding_apron_seats` prices every feeder
# contact against the HARD RUNWAY/SEAM ANCHORS on the SAME spine graph
# phase A projects on (``law_graph_budget.build_anchor_envelope``), and the
# silent clamp-up is gone: a DEM target clamped into the band by more than
# the materiality floor is REPORTED, and an EMPTY band ∩ envelope is
# reported as the contradiction it is.
#
# THE DEFECT IT CLOSES (HECA, measured from the phase-A npz).  Feeder
# 2861's DEM is 60.200; it is clamped UP into a band floor of 62.119 and
# then PROJECTED to 65.749 by a polytope whose only cap constraints are
# feeder↔feeder at straight gap — with NO constraint against hard runway
# anchor 2863, which sits at 60.790 only 0.1928 m of route budget away.
# The seat is then stamped immovable, and the phase-A projection burns
# 3983 sweeps on an anchor pair that cannot both hold (residual 4.766 m).
# An anchor 0.19 m of budget away is not a distant consideration; it is
# the binding constraint.
#
# OLD-WORLD MEASURED COST: one severity item at +1.27 (recorded when the
# gate was flipped in the pre-composed world).  DEBUG-PHASE TARGET — noted,
# not a reason to keep the gate.
#
# The law is INACTIVE only where it has no input: ``anchor_envelope=None``
# means the caller holds no hard anchors on the spine graph, and an
# envelope that does not exist cannot bound anything.


def build_nobuilding_apron_seats(layout, bucket_to_idx, band, dem_fn,
                                 anchor_envelope=None, icao=""):
    """``{feeder_contact_node_idx: feasible_level}`` for every NO-BUILDING apron —
    the FEEDER-CONVERGENCE rule (user 2026-06-26 directive #3; tilt model
    2026-06-28).

    A no-building apron has no pad to anchor it, so its feeder taxiways each grade
    to their own DEM-driven level and can arrive INCOMPATIBLE (the ``route_reach``
    violation: feeder contacts whose elevation gap exceeds the apron cap over their
    separation).  Rather than force the apron FLAT (one level for all feeders, which
    over-constrains and wastes the apron's own grade budget), anchor EACH feeder
    contact at the level feasible THERE — its reach band, biased to DEM — projected
    onto the apron-cap polytope so the apron TILTS ≤cap between contacts:

        minimise Σ(L_i − t_i)²  s.t.  |L_i − L_j| ≤ cap·d_ij  and  f_i ≤ L_i ≤ ce_i

    (:func:`_project_apron_contacts`).  ``t_i = clamp(DEM_i, band_i)`` pulls a feeder
    floating ABOVE its reach band back down to a reachable level; the projection
    then shares the apron's cap so close feeders need not be equal, only gradeable.
    A solution clears ``route_reach`` BY CONSTRUCTION (the constraints ARE its
    condition); an EMPTY polytope (a feeder's band can't reconcile with another's
    across the cap) is FUNDAMENTAL → skipped (documented transition, not a gate).

    Aprons that abut a building are skipped (the pad anchors the level).  The caller
    (``solve.py``) ANCHORS the returned ``{contact_node: L_i}`` like a building seat
    (heaviest), so the feeder SPINES grade to meet the apron (user 2026-06-28 — the
    apron must anchor for the spines to adjust to it; a SOFT ``node_band`` clamp let
    whatever pinned a feeder win and didn't converge).  Only the per-feeder CONTACTS
    are anchored — at their OWN reachable level — so the apron body still flexes and
    the feeder reaches L_i without an over-cap step (the earlier FLAT whole-ring seat
    forced unreachable levels → regressed ``cyxy_spine_zero`` + HECA runway).  Gate

    ``anchor_envelope`` (seed-fix round §3, STANDING LAW) — a
    ``law_graph_budget.AnchorEnvelope`` over the HARD runway/seam anchors
    on the SAME spine graph phase A projects on.  Each feeder's box is
    intersected with its envelope, which is the EXACT intersection of the
    cap constraints ``|L_i − v_a| ≤ d(a, i)`` over every hard anchor
    within reach (the anchor values are FIXED, so each such constraint is
    an interval on ``L_i``).  Two things follow, both required by the
    spec: a feeder can no longer be projected metres away from a runway
    truth it is centimetres of budget from; and the DEM target's clamp
    into the band stops being SILENT — a clamp beyond the materiality
    floor is reported with the bound that demanded it, and an EMPTY box
    (band ∩ envelope) is reported as the contradiction it is instead of
    being skipped without a word.  ``None`` ⇒ the caller holds no hard
    anchors on the spine graph, so there is no envelope to intersect."""
    import os as _os
    _cap_on = anchor_envelope is not None
    _clamp_rows: list = []
    _empty_rows: list = []
    from shapely.geometry import Point
    from auto_patch.layout import ROLE_APRON, ROLE_BUILDING, ROLE_JUNCTION
    from auto_patch.config import APRON_MAX_GRADE
    cps = layout.canonical_points
    buildings = [b.polygon for b in layout.shapes
                 if b.role == ROLE_BUILDING and b.polygon is not None
                 and not b.polygon.is_empty]
    # The taxi-network shapes whose contact feeds an apron (the SAME set
    # ``route_reach_violations`` measures): corridor junctions, not SVC
    # (the rect roles are retired, owner 2026-07-29).
    route_roles = {ROLE_JUNCTION}
    routes = [t for t in layout.shapes
              if t.role in route_roles and t.polygon is not None
              and not t.polygon.is_empty
              and not str(t.ref or "").upper().startswith("SVC")]
    seats: dict = {}
    for s in layout.shapes:
        if (s.role != ROLE_APRON or s.polygon is None or s.polygon.is_empty):
            continue
        if s.polygon.area <= _NOBUILD_APRON_SEAT_MIN_AREA_M2:
            continue            # too small to anchor — flexes with its feeders
        if any(s.polygon.distance(b) < 1.0 for b in buildings):
            continue                            # a building anchors the level
        # Each feeder's CONTACT = its nearest vertex to the apron (what route_reach
        # measures), with its reach band + DEM-biased target.
        idxs, tgts, boxes, poss, keys = [], [], [], [], []
        for t in routes:
            if t is s or s.polygon.distance(t.polygon) > 1.5:
                continue
            best = None
            for (x, y) in _open_ring(list(t.polygon.exterior.coords)):
                d2 = s.polygon.exterior.distance(Point(x, y))
                if best is None or d2 < best[0]:
                    best = (d2, (x, y))
            if best is None:
                continue
            px, py = best[1]
            b = band(px, py)
            if b is None:
                continue
            k = cps.get_or_add(float(px), float(py))
            i = bucket_to_idx.get(k)
            if i is None:
                continue
            de = dem_fn(px, py)
            tgt = de if de is not None else 0.5 * (b[0] + b[1])
            # ── §3: the anchor-cap box + the LOUD clamp ────────────────
            if _cap_on:
                env = anchor_envelope.box(i)
                if env is not None:
                    lo_b = max(float(b[0]), float(env[0]))
                    hi_b = min(float(b[1]), float(env[1]))
                    if lo_b > hi_b:
                        # band ∩ hard-anchor envelope is EMPTY.  Report it
                        # (feasibility-is-guaranteed: a contradiction is a
                        # law defect to attribute), and take the ANCHOR
                        # envelope — it is the constraint the phase-A
                        # projection will actually enforce, and seating
                        # inside the band instead is precisely what mints
                        # the immovable-vs-runway pair.
                        _empty_rows.append((i, float(b[0]), float(b[1]),
                                            float(env[0]), float(env[1])))
                        lo_b, hi_b = float(env[0]), float(env[1])
                    b = (lo_b, hi_b)
            clamped = min(max(tgt, b[0]), b[1])
            if _cap_on and abs(clamped - tgt) > 0.01:
                _clamp_rows.append((i, float(tgt), float(clamped),
                                    float(b[0]), float(b[1])))
            idxs.append(i)
            tgts.append(clamped)
            boxes.append(b)
            poss.append((px, py))
            keys.append(k)
        if len(idxs) < 2:
            continue
        L = _project_apron_contacts(tgts, boxes, poss, APRON_MAX_GRADE)
        if L is None:
            continue                            # fundamental → documented transition
        # BOUNDED YIELD box (owner ruling 2026-07-29): a contact seat's box
        # is the band interval that seated it (``band(x, y)`` at the contact
        # — the same lookup), widened to include the projected level (POCS
        # keeps ``L_i`` in-box; the widen is a no-op guard).  Keyed by
        # CANONICAL KEY (see ``build_building_seats``); merged into the
        # registry that function reset (it runs first).
        seat_boxes = _store_of(layout).open_map("seat_boxes", "interval")
        for i, Li, b, k in zip(idxs, L, boxes, keys):
            seats[i] = float(Li)
            blo = min(float(b[0]), float(Li))
            bhi = max(float(b[1]), float(Li))
            prev = seat_boxes.get(k)
            seat_boxes[k] = ((blo, bhi) if prev is None
                             else (max(prev[0], blo), min(prev[1], bhi)))
    if _cap_on:
        _report(f"  [apron-contact] {icao or 'airport'}: hard-anchor cap ON "
                f"({anchor_envelope.anchor_count} anchor(s) over "
                f"{anchor_envelope.node_count} spine node(s)); "
                f"{len(_clamp_rows)} DEM target(s) clamped by >0.01 m, "
                f"{len(_empty_rows)} feeder box(es) EMPTY "
                f"(band vs hard-anchor envelope).")
        for (i, lo_band, hi_band, lo_env, hi_env) in _empty_rows[:10]:
            _report(f"  [apron-contact]   node {i}: band "
                    f"[{lo_band:.3f}, {hi_band:.3f}] does not meet the "
                    f"hard-anchor envelope [{lo_env:.3f}, {hi_env:.3f}] — "
                    f"seated against the ENVELOPE (the constraint phase A "
                    f"enforces); attribute the band.")
        for (i, tgt, clamped, lo_b, hi_b) in sorted(
                _clamp_rows, key=lambda r: -abs(r[2] - r[1]))[:10]:
            _report(f"  [apron-contact]   node {i}: DEM target {tgt:.3f} "
                    f"clamped to {clamped:.3f} ({clamped - tgt:+.3f} m) by "
                    f"box [{lo_b:.3f}, {hi_b:.3f}].")
    return seats


# NEAR-MISS building-frontage recognition tolerance (2026-07-08).  A DSF
# building-pad outline and the apt.dat apron edge it fronts can be offset by a
# sub-metre source mismatch (SPJC building29 vs its SW apron: 0.68 m measured),
# leaving a thin unpaved sliver that defeats EVERY exact-identity reconciler
# (pre-solve weld, stitch_pavement_to_terminals, the 2-dp frontage-key match) —
# all of which correctly key off ``SHARED_VERTEX_TOL_M`` (0.5 m, the ONE
# canonical identity; never widened per the solver+validator single-registry
# ruling).
#
# THE VALUE NOW LIVES IN ``config.py`` — the standards single source — taking
# this constant's own standing TODO (cycle-5 instrument-fix item 6).  It had to
# move the moment the law grew a SECOND reader: ``tools/check_grade``'s
# ``frontage_near_miss`` census family judges emitted patches against exactly
# this radius and this budget, and a rule value read from a solver-internal
# module is the two-copies defect the lockstep standard forbids.  Re-exported
# here under its historical name so every existing reader (and
# ``tests/test_building_frontage_near_miss.py``) is unaffected.
from auto_patch.config import (                            # noqa: E402
    BUILDING_FRONTAGE_NEAR_MISS_M,                         # noqa: F401
    near_miss_frontage_budget as _near_miss_frontage_budget)


def near_miss_building_frontage_floors(layout, bucket_to_idx, band,
                                       building_seats):
    """``{apron_node_idx: floor_level}`` for soft-pavement edges that face a
    building pad across a NEAR-MISS gap — so the pavement grades UP to the flat
    pad instead of cliffing ~0.5–1 m below it across a thin unpaved sliver.

    THE DEFECT (SPJC pavement_grade step gate, 2026-07-08): building29's flat
    pad (seat 25.56) runs parallel to a large apron 0.68 m away at ~24.9 — a
    0.66 m visible step.  The 0.68 m source offset (DSF pad outline vs apt.dat
    apron edge) is just over ``SHARED_VERTEX_TOL_M`` (0.5 m), so no vertices
    are shared: the pre-solve weld and ``stitch_pavement_to_terminals`` never
    fire, the pad's frontage-seat recognition (exact 2-dp key match in
    ``build_building_seats``) never sees the edge, and
    ``build_nobuilding_apron_seats`` SKIPS the apron ("a building anchors the
    level" — within 1 m of a pad) even though the pad anchors nothing there.
    The apron falls through every regime and solves to its own low DEM.

    THE FIX is raise-biased and value-side only, and it is per-EDGE: the
    solve-time ring is SPARSE along a long frontage (SPJC's apron faces the
    90 m pad with one 49 m straight edge whose endpoints sit 1.5 m and 10 m
    away — no ring vertex lies inside any sub-metre radius; the near-pad OSM
    vertices are post-solve planarize/T-weld inserts that INTERPOLATE along
    that edge).  So the value-controlling nodes are the near-miss edge's
    ENDPOINTS.  For every soft-pavement ring edge whose segment passes within
    ``BUILDING_FRONTAGE_NEAR_MISS_M`` of a pad and whose endpoints are BOTH
    canonically unshared with the pad (a true near-miss run — an edge with a
    pad-shared endpoint is already reconciled by weld/stitch/seat identity
    and legitimately grades away from the seat), floor BOTH endpoints at
    ``seat − APRON_MAX_GRADE·d`` with ``d`` each endpoint's own distance to
    the pad (the building↔apron law: the level the pavement must reach to
    grade ≤cap up to the flat pad; the floor decays at the apron-law rate, so
    a far endpoint gets a proportionally lower floor and the interpolated
    near-pad run lands at ~seat), clamped to the endpoint's reach-band
    ceiling so it stays runway-reachable.  ORDERING: the pad seat is read from
    ``building_seats`` AS ALREADY CHOSEN by ``build_building_seats`` (seats +
    POCS coupling run first; ``solve.py`` calls this afterwards, before the
    no-building apron seats merge) — the near-miss edge must NEVER feed the
    pad's ``_frontage_box`` ceiling, so the pad seat cannot be pulled DOWN by
    the lower apron (which would just move the step to the pad's other,
    genuinely-shared frontage).  SOFT floors through the one ``spine_floor``
    channel (never hard seats): one raise-biased regime the solver resolves
    with its neighbour cap slabs — per-vertex hard anchors from a second
    regime are the documented unresolvable-tear pattern.  Feasibility is not
    at risk: floors are ≤ seat by construction (cap·d ≥ 0), decay at the
    apron-law rate, and are band-ceiling-clamped.

    STANDING LAW (former gate ``O4_BUILDING_FRONTAGE_NEAR_MISS``, retired
    2026-08-05); recognition is unconditional (was: no floors,
    byte-identical)."""
    from auto_patch.config import APRON_MAX_GRADE
    floors: dict = {}
    for contact in _near_miss_frontage_contacts(layout, bucket_to_idx,
                                                building_seats):
        (i, _pad_node, d, seat, x, y) = contact
        floor_level = seat - APRON_MAX_GRADE * d    # ≤ seat by construction
        bnd = band(x, y)
        if bnd is not None:                         # stay runway-reachable
            floor_level = min(floor_level, bnd[1])
        if floor_level > floors.get(i, -_INF):
            floors[i] = float(floor_level)
    return floors


def near_miss_building_frontage_edges(layout, bucket_to_idx, building_seats,
                                      weld_refs_out=None):
    """``[(apron_node_idx, pad_node_idx, budget_m)]`` — the near-miss frontage
    relationship as LAW EDGES for the joint feasibility projections.

    The floors above shape phases A/B, but every ``feasibility_project`` pass
    (cap edges only, floors unknown) resolves by MINIMUM DISPLACEMENT — one
    floor-lifted endpoint against several low free neighbours loses, and the
    lift is projected away before writeback (measured at SPJC: phase B honours
    the floor at 25.30, the first projection pulls it to 25.05, the final
    yield GS lands back at 24.84).  The durable expression of "feature-weld
    needs VALUE AGREEMENT" is therefore an EDGE in the projections' own edge
    set: ``|z(apron_endpoint) − z(pad_node)| ≤ APRON_MAX_GRADE·d`` with ``d``
    the endpoint's distance to the pad polygon (the building↔apron law across
    the sliver).  The pad node is the pad's nearest ring node — pads are hard
    through phases A/B and MOVABLE FLAT GROUPS in the final yield GS, so the
    joint projection settles pad level and apron edge together (min
    displacement, pad stays flat) instead of un-doing the floor.

    Same recognition and gate as :func:`near_miss_building_frontage_floors`
    (STANDING LAW; the former ``O4_BUILDING_FRONTAGE_NEAR_MISS`` gate is gone.)

    ``weld_refs_out`` — PAD ROD COUPLING (owner approval 2026-07-29,
    ``docs/specs/pad-rod-coupling-spec.md``; completes bounded-yield-spec §7.3
    at building faces).  When a dict is passed it is filled with
    ``{apron_node_idx: (pad_seat_level, pad_node_idx)}`` over THIS SAME
    contact set: the §7 reference value (``z_ref``) of a soft-fabric vertex
    welded to a pad face IS the pad's seat, not the fabric's yield-entry state
    (the pad-weld ruling — "airside pavement welds SMOOTH to a building's
    airside face" — and "the seat is the rod for the building").  A vertex
    facing TWO pads takes the NEARER contact (pads may legitimately differ;
    the inter-pad step exemption is unchanged).  The PAD NODE rides along
    because the seat level recorded here is read BEFORE the no-building apron
    seat merge and the groundside/service passes: the value the pad's own §7
    rod holds at yield entry is the one the weld must reference, and the call
    site resolves it through this node (measured 2026-07-29: 21 of 25 HECA
    pads emit off this scalar, by up to 8.7 m — referencing the scalar OPENS
    the frontage it is supposed to weld).  Filled from the ONE recognition
    pass the edges already run — no second geometry sweep, no measurable
    build-time cost."""
    edges: list = []
    nearest: dict = {}          # apron node -> (distance_m, seat, pad_node)
    for contact in _near_miss_frontage_contacts(layout, bucket_to_idx,
                                                building_seats,
                                                log_firings=True):
        (i, pad_node, d, seat, _x, _y) = contact
        if weld_refs_out is not None:
            prev = nearest.get(i)
            if prev is None or d < prev[0]:
                nearest[i] = (float(d), float(seat), pad_node)
        if pad_node is None:
            continue
        # THE BUDGET, from the law's one authority (config) — the same
        # function ``check_grade._check_frontage_near_miss`` judges with.
        edges.append((i, pad_node, float(_near_miss_frontage_budget(d))))
    if weld_refs_out is not None:
        for i, (_d, seat, pad_node) in nearest.items():
            weld_refs_out[i] = (seat, pad_node)
    return edges


def _near_miss_frontage_contacts(layout, bucket_to_idx, building_seats,
                                 log_firings=False):
    """The shared NEAR-MISS recognition (see the two consumers above).

    Yields one contact per (soft-pavement near-miss edge endpoint, pad):
    ``(endpoint_node_idx, nearest_pad_node_idx, distance_to_pad_m,
    pad_seat_level, endpoint_x, endpoint_y)``.  ``log_firings`` prints the
    per-pad firing line (the EDGES consumer passes True — it runs once per
    solve, so each recognized pad↔pavement pair logs once)."""
    from shapely.geometry import LineString, Point
    cps = layout.canonical_points
    near_miss_m = BUILDING_FRONTAGE_NEAR_MISS_M

    # Building pads with a CHOSEN seat (post-coupling), with their canonical
    # ring-node index sets for the shared-vertex (already-reconciled) test.
    pads: list = []       # (shape, pad_node_idx_set, seat_level, ring_nodes)
    for b in layout.shapes:
        if (b.role != ROLE_BUILDING or b.polygon is None
                or b.polygon.is_empty):
            continue
        ring = _open_ring(list(b.polygon.exterior.coords))
        ring_nodes = [((x, y), bucket_to_idx.get(
            cps.get_or_add(float(x), float(y)))) for (x, y) in ring]
        idxs = {i for (_pt, i) in ring_nodes if i is not None}
        seat = next((building_seats[i] for i in idxs
                     if building_seats.get(i) is not None), None)
        if seat is not None:
            pads.append((b, idxs, float(seat), ring_nodes))
    if not pads:
        return

    # The frontage-bearing soft-pavement roles (the same set
    # ``build_building_seats``' frontage recognition keys on) — read from the
    # law's one authority so the census twin
    # (``check_grade._check_frontage_near_miss``) recognizes the same
    # population.  ``tests/test_harness.py`` twin-asserts the tuple still
    # equals ``(ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION)``, which is
    # what makes a ROLE_* rename loud instead of silent.
    from auto_patch.config import NEAR_MISS_FRONTAGE_SOFT_ROLES as soft_roles
    for s in layout.shapes:
        if (s.role not in soft_roles or s.polygon is None
                or s.polygon.is_empty):
            continue
        ring = None
        ring_idx = None
        for (pad, pad_idx_set, seat, pad_ring_nodes) in pads:
            if pad.polygon.distance(s.polygon) > near_miss_m:
                continue
            if ring is None:
                ring = _open_ring(list(s.polygon.exterior.coords))
                ring_idx = [bucket_to_idx.get(
                    cps.get_or_add(float(x), float(y))) for (x, y) in ring]
            fired: list = []
            emitted: set = set()
            ring_length = len(ring)
            for edge_start in range(ring_length):
                edge_end = (edge_start + 1) % ring_length
                # A near-miss FRONTAGE edge: passes within the radius, with
                # BOTH endpoints canonically unshared with the pad.  A
                # pad-shared endpoint means identity already reconciles that
                # corner (weld / stitch / seat anchor) and the edge
                # legitimately grades away from the seat — not a near miss.
                if (ring_idx[edge_start] in pad_idx_set
                        or ring_idx[edge_end] in pad_idx_set):
                    continue
                segment = LineString([ring[edge_start], ring[edge_end]])
                if segment.distance(pad.polygon) > near_miss_m:
                    continue
                for endpoint in (edge_start, edge_end):
                    i = ring_idx[endpoint]
                    if (i is None or i in building_seats
                            or (i, id(pad)) in emitted):
                        continue    # unregistered / hard-anchored / done
                    emitted.add((i, id(pad)))
                    x, y = ring[endpoint]
                    point = Point(x, y)
                    d = pad.polygon.distance(point)
                    pad_node = min(
                        (pn for pn in pad_ring_nodes if pn[1] is not None),
                        key=lambda pn: ((pn[0][0] - x) ** 2
                                        + (pn[0][1] - y) ** 2),
                        default=(None, None))[1]
                    if _os.environ.get("O4_NEAR_MISS_DEBUG") == "1":
                        print(f"    [near-miss dbg] node {i} ({x:.1f},{y:.1f})"
                              f" d={d:.2f} seat={seat:.3f}"
                              f" pad_node={pad_node}")
                    fired.append(d)
                    yield (i, pad_node, d, seat, x, y)
            if fired and log_firings:
                try:
                    import O4_UI_Utils as _UI
                    _UI.vprint(
                        1, f"  [near-miss frontage] pad "
                        f"{pad.ref or '?'} seat {seat:.2f} <-> "
                        f"{s.role} ({s.polygon.area:.0f} m2) gap "
                        f"{pad.polygon.distance(s.polygon):.2f} m: "
                        f"{len(fired)} edge endpoint(s), d "
                        f"{min(fired):.2f}..{max(fired):.2f} m")
                except Exception:               # pragma: no cover
                    pass


def build_apron_contact_floors(layout, bucket_to_idx, band, dem_fn, building_seats):
    """``{feeder_contact_node_idx: floor_level}`` for taxiways/junctions that meet a
    BUILDING-ANCHORED apron's edge — so the feeder SPINE grades UP to the apron
    instead of the (senior) apron sagging down to the feeder's DEM-low mouth.

    The complement of :func:`build_nobuilding_apron_seats`, which handles ONLY
    no-building aprons (it bails on any apron within 1 m of a building).  A building
    apron is held high by its pad seat, but where the apron edge is FAR from the
    building (beyond ``BUILDING_REACH_CORRIDOR_M``, so the building-frontage spine
    floor never reaches it) a feeder taxiway contacting that edge falls through every
    floor rule and solves to its own low DEM — dragging the apron edge into a cliff
    (OEMA TX8 #275: apron #198 held at 639 by a building 310 m away, TX8 mouth at the
    DEM 629 → a 96 % within-apron step).  This was the documented authority inverted:
    "a taxiway/apron node is apron-owned; the taxi yields", not the reverse.

    The floor is the apron's OWN guaranteed-reachable level at the contact: the apron
    grades ≤ ``APRON_MAX_GRADE`` from each adjacent building seat, so at a contact
    ``d`` metres from a building seated at ``S`` the apron is at least ``S − cap·d``.
    Taking the max over the apron's buildings and clamping to the contact's reach band
    gives the level the feeder must rise to (never above the band ceiling, so it stays
    runway-reachable; never below the band floor).  A FLOOR (not a hard seat) so the
    feeder spine still grades smoothly up from its runway anchor and the apron body
    flexes — the taxi yields UP, the apron keeps its cap.  Gate
    STANDING LAW: the former ``O4_APRON_CONTACT_FLOOR`` gate is gone.

    Also carries the NEAR-MISS building-frontage floors
    (:func:`near_miss_building_frontage_floors`, its own gate) — the same soft
    ``spine_floor`` channel, merged max-wise like every floor."""
    near_miss_floors = near_miss_building_frontage_floors(
        layout, bucket_to_idx, band, building_seats)
    from shapely.geometry import Point
    from auto_patch.layout import ROLE_APRON, ROLE_BUILDING, ROLE_JUNCTION
    from auto_patch.config import APRON_MAX_GRADE
    cps = layout.canonical_points
    cap = APRON_MAX_GRADE

    # Each building's seat level (its pad nodes all share one seat in building_seats)
    # paired with its polygon, for the seat − cap·d reach bound.
    bseats: list = []
    for b in layout.shapes:
        if (b.role != ROLE_BUILDING or b.polygon is None or b.polygon.is_empty):
            continue
        lv = None
        for (x, y) in _open_ring(list(b.polygon.exterior.coords)):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None and building_seats.get(i) is not None:
                lv = building_seats[i]
                break
        if lv is not None:
            bseats.append((b.polygon, float(lv)))
    if not bseats:
        return near_miss_floors

    route_roles = {ROLE_JUNCTION}
    routes = [t for t in layout.shapes
              if t.role in route_roles and t.polygon is not None
              and not t.polygon.is_empty
              and not str(t.ref or "").upper().startswith("SVC")]

    floors: dict = dict(near_miss_floors)
    for s in layout.shapes:
        if (s.role != ROLE_APRON or s.polygon is None or s.polygon.is_empty):
            continue
        # Only BUILDING-anchored aprons (no-building ones use the seat path above).
        near = [(poly, lv) for (poly, lv) in bseats if s.polygon.distance(poly) < 1.0]
        if not near:
            continue
        for t in routes:
            if t is s or s.polygon.distance(t.polygon) > 1.5:
                continue
            # contact = the feeder vertex nearest the apron (what route_reach measures)
            best = None
            for (x, y) in _open_ring(list(t.polygon.exterior.coords)):
                d2 = s.polygon.exterior.distance(Point(x, y))
                if best is None or d2 < best[0]:
                    best = (d2, (x, y))
            if best is None:
                continue
            px, py = best[1]
            bnd = band(px, py)
            if bnd is None:
                continue
            cpt = Point(px, py)
            # the apron's guaranteed-reachable level here: max_b(seat_b − cap·d_b),
            # i.e. the lowest level the apron still grades to each building within cap.
            reach = max(lv - cap * poly.distance(cpt) for (poly, lv) in near)
            floor = min(max(reach, bnd[0]), bnd[1])         # clamp into reach band
            i = bucket_to_idx.get(cps.get_or_add(float(px), float(py)))
            if i is None:
                continue
            if floor > floors.get(i, -float("inf")):
                floors[i] = float(floor)
    return floors


def node_bands(nodes, band, skip_from=None, skip_idx=None):
    """Per-node ``(floor, ceiling)`` from the one reach band (``None`` off-net).

    ``skip_idx`` (flat-site fast path, docs/specs/flat-site-fast-path-spec.md
    §3): an explicit SET of node indices handed ``None`` instead of a scan —
    the born-at-Z0 nodes used by no shape outside the partition.  Same
    argument as ``skip_from`` below, on a set rather than a threshold: such a
    node is a HARD PIN no pass may move, so nothing ever consumes its band,
    and scanning it is the cost the partition exists to remove.  A node
    SHARED with an ineligible shape is deliberately NOT in the set — that
    shape's own law reads it.  ``None`` ⇒ byte-identical to before.

    ``skip_from`` (Slice B stage B3 performance lever, gated at the call
    site): indices ``>= skip_from`` are the adjacent-ground ZONE nodes —
    graded_strip terrain variables whose value law is a pure per-vertex DEM
    envelope clamp to their host pavement edge (``ROLE_GRADE_LIMITS
    ['graded_strip'] is None`` — no reach coupling), encoded as the zone
    interval edge in ``_build_adjacent_ground_zone_constraints``.  Their reach
    band is NEVER consumed by that law, yet computing it is the KBNA gate-ON
    scaling wall: a zone node sits OFF the pavement net, so ``band()`` takes
    the expensive skeleton-``_fallback`` path (~74 ms/node vs ~12 ms on-net),
    and there are 45k of them (node_bands ≈ 60 min at KBNA, ~55 min of it the
    zone tail).  Handing those nodes ``None`` (off-net, the honest value for a
    terrain vertex) skips the scan.  ``skip_from=None`` restores the
    all-nodes scan (the gate-OFF path, byte-inert).

    CLUSTER AMORTIZATION (Tier 3 wave 1, ``O4_REACH_BAND_CLUSTERS``): when the
    band closure exposes a ``.batch`` method (``building_feasibility.
    reach_band_unified``), the per-node serving-centerline scan — the dominant
    reach-band cost — is amortized across spatial buckets: it runs once per
    bucket and every member the representative's line PROVABLY also serves
    reuses it, computing an EXACT, bit-identical band without its own scan (see
    ``reach_band_unified._batch``).  The result is identical to the per-node
    scan below; only the scan work is shared.  Gate OFF
    (``config.REACH_BAND_CLUSTERS`` off) or a band without ``.batch`` → the
    exact per-node scan, byte-identical.  The env override died 2026-08-05;
    the config constant is the switch."""
    from auto_patch.config import REACH_BAND_CLUSTERS
    batch = getattr(band, "batch", None)
    if batch is not None and REACH_BAND_CLUSTERS:
        return batch(nodes, skip_from, skip_idx)
    if skip_from is None and not skip_idx:
        return [band(x, y) for (x, y) in nodes]
    limit = len(nodes) if skip_from is None else min(skip_from, len(nodes))
    out = [None] * len(nodes)
    for i in range(limit):
        if skip_idx and i in skip_idx:
            continue
        out[i] = band(nodes[i][0], nodes[i][1])
    return out


def _spine_floor_per_node(layout, nodes, bucket_to_idx, building_seats,
                          node_band, spine_adj):
    """``{spine_node_idx: floor}`` — floor EVERY spine node directly from its own
    VISIBLE chord to the nearest spine-facing building edge (user 2026-06-27,
    replacing the single centroid foot).

    For each spine node, take the straight chord to the closest point on each
    building within the frontage corridor; if that chord stays on pavement (a real
    apron path, not across grass / through another building) the node is floored at
    ``seat − 1%·chord`` — the elevation the spine must reach so the apron grades
    ≤1 % up to the flat pad.  A node takes the MAX over the buildings it faces.
    No centroid, no cap-decay propagation: ``seat − 1%·dist`` sampled per node is
    already cap-Lipschitz along the spine (adjacent nodes differ by ≤1 %·spacing ≤
    cap·spacing), so a big terminal's WHOLE frontage lifts the spine, not just one
    foot.  Each floor is clamped to the node's band ceiling (never above what the
    runway route reaches)."""
    from shapely.geometry import Point, LineString
    from shapely.ops import nearest_points
    from auto_patch.config import APRON_MAX_GRADE, VISIBLE_CHORD_CONNECT
    from auto_patch.grade_law import BUILDING_REACH_CORRIDOR_M
    from auto_patch.layout import ROLE_BUILDING
    from auto_patch.elevation_per_surface.building_feasibility import (
        _pavement_visibility, _VIS_ON_PAV_FRAC)

    cps = layout.canonical_points
    vis = _pavement_visibility(layout) if VISIBLE_CHORD_CONNECT else None
    # The lift reaches a building over a VISIBLE on-pavement chord at any range up
    # to THE single reach corridor (the visibility gate below, not the distance, is
    # the real limit) — so a building anchors its serving spine even across a wide
    # single apron (CYXY building22 at 219 m).  ONE rule, shared with the seat band.
    corridor = BUILDING_REACH_CORRIDOR_M

    builds = []
    for s in layout.shapes:
        if (s.role != ROLE_BUILDING or s.polygon is None
                or s.polygon.is_empty):
            continue
        lv = None
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i in building_seats:
                lv = building_seats[i]
                break
        if lv is not None:
            builds.append((s.polygon, float(lv)))
    if not builds:
        return {}

    floor: dict = {}
    for i in spine_adj:
        if i >= len(nodes):
            continue
        px, py = nodes[i]
        p = Point(px, py)
        best = None
        for (poly, lv) in builds:
            d = poly.distance(p)
            if d > corridor:
                continue
            near = nearest_points(poly, p)[0]   # spine-facing building edge point
            chord = LineString([(px, py), (near.x, near.y)])
            if vis is not None and chord.length > 1e-6 and not vis.contains(chord):
                try:                            # tolerate tiny weld-seam gaps
                    frac = chord.intersection(vis.context).length / chord.length
                except Exception:               # pragma: no cover
                    frac = 0.0
                if frac < _VIS_ON_PAV_FRAC:
                    continue                    # chord leaves pavement → not facing
            t = lv - APRON_MAX_GRADE * d        # 1 % apron from spine up to the pad
            if best is None or t > best:
                best = t
        if best is None:
            continue
        nb = node_band[i] if i < len(node_band) else None
        if nb is not None and best > nb[1]:
            best = nb[1]                        # never above the reachable ceiling
        floor[i] = best
    return floor


def building_spine_floor(layout, nodes, bucket_to_idx, building_seats,
                         node_band, spine_adj):
    """``{spine_node_idx: floor}`` — make the serving spine RISE to serve its
    buildings (user 2026-06-25): the taxi arm exists to serve its pads, so the
    SAME trace that set a building's feasible level anchors the spine at the
    precise elevation it must reach there, and that anchor is GRADED SMOOTHLY
    along the centerline chain ("grade smoothly between anchors").

    User 2026-06-27: the default is now :func:`_spine_floor_per_node` — every
    spine node floored directly from its own visible chord to the spine-facing
    building edge (the centroid foot under-covered large terminals).  The legacy
    centroid/full-frontage-foot path below is kept for A/B
    (the former ``O4_SPINE_FLOOR_PER_NODE`` gate is retired; the per-node
    floor is the standing law and the legacy body is deleted).

    For each airside building, the serving centerline is the one the reach band
    used (``_nearest_visible_centerline`` across the continuous apron — NOT the
    geometric nearest, so the anchor is exactly the point the building was made
    consistent with).  The spine node nearest the building's perpendicular FOOT
    is anchored at ``seat − APRON_MAX_GRADE·dist`` — the elevation the spine needs
    so the apron grades ≤1 % up to the flat pad.

    That foot anchor is then propagated along the CONSECUTIVE centerline chain
    (``spine_adj``, budget ``cap·dist``) as a floor that DECREASES at exactly the
    cap rate: ``floor_j = anchor − capdist(foot → j)``.  This builds the whole
    climbing ramp, and because the floor is cap-Lipschitz along the chain it is
    grade-consistent BY CONSTRUCTION — it can never force a spine grade break, and
    (since every chain node's neighbour is also floored) the solve's "envelope
    yields" fallback no longer drops it.  A single un-propagated floor was dropped
    whenever the foot's flat runway-side neighbour capped it low → the arm stayed
    flat (CYXY ~U12 694.5 vs building19 700.2, 106 m away).  Each floor is clamped
    to the node's band ceiling (never above what the runway route reaches)."""
    return _spine_floor_per_node(
        layout, nodes, bucket_to_idx, building_seats, node_band, spine_adj)

    # THE LEGACY WHOLE-GRAPH SPINE FLOOR was deleted 2026-08-05: the
    # per-node floor is the standing law and the old body was unreachable
    # dead code behind the retired ``O4_SPINE_FLOOR_PER_NODE`` gate.


def apply_groundside_reach(layout, bucket_to_idx, elev, cap):
    """Re-level each groundside piece a service road connects to an apron, to the
    elevation the connector can REACH within the service-road grade cap — so the
    connector grades <=cap instead of ramping steeply to the groundside's raw DEM
    (user 2026-06-27, refining the accept-the-ramp model).

    "After buildings and aprons are anchored, check groundside pieces: if they have
    a service road, and if that road reaches an apron, follow that route to find
    what elevation the groundside can reach within grade and anchor it there.  If it
    has no service roads they just stay DEM."

    The service road that meets a groundside piece may reach the apron through a
    CHAIN of service roads/junctions (an out-and-back route, a yard loop), so the
    binding reference is the connector's OWN apron-ward mouth elevation (already
    solved), not the distant apron: the groundside mouth can sit at most
    ``cap * route_len`` from it (``route_len`` = the binding apron-ward->groundside
    edge).  Whether to re-level at all is gated by APRON REACHABILITY — the piece's
    service road must connect (directly or through the service network) to an apron;
    a groundside-only yard road never re-levels its piece.

    The piece is shifted by a UNIFORM offset (preserving its DEM relief) so its
    mouth(s) sit at the closest-to-DEM reachable level; the connector then grades the
    short climb at <=cap.  A piece reached by several connectors must satisfy them
    ALL (interval INTERSECTION of the per-connector shift bounds).

    Mutates groundside ``node_altitudes`` in place and returns ``(n_relevelled,
    welds)`` where ``welds = {node_idx: shifted_groundside_alt}`` for the mouths of
    the APRON-REACHABLE connectors only (the caller pins ``elev`` to these so the
    connector and groundside emit as one welded node).  A service road that does NOT
    reach an apron is left untouched — its piece stays DEM and its mouth is not
    pinned (the user's "stays DEM" case).  Safe to shift a whole piece because a
    groundside lot shares no nodes with airside (a clearance gap separates them) —
    only the connector mouth, which is welded to the shifted level."""
    import math
    import os as _os
    from auto_patch.layout import (
        ROLE_GROUNDSIDE_PAVEMENT, ROLE_APRON,
        ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)

    cps = layout.canonical_points

    def _key(x, y):
        return cps.get_or_add(float(x), float(y))

    # apron-owned canonical node keys (a service road TOUCHES the apron here).
    apron_keys: set = set()
    for s in layout.shapes:
        if s.role != ROLE_APRON or s.polygon is None or s.polygon.is_empty:
            continue
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            apron_keys.add(_key(x, y))

    # groundside pieces: per-key DEM altitude (the connector mouth shares a key);
    # plus the UNION of every groundside key (to split a connector's nodes into
    # groundside-mouth vs apron-ward).
    gs_pieces = []
    gs_all_keys: set = set()
    for g in layout.shapes:
        if (g.role != ROLE_GROUNDSIDE_PAVEMENT or g.polygon is None
                or g.polygon.is_empty or not g.node_altitudes):
            continue
        gcoords = list(g.polygon.exterior.coords)
        galts = list(g.node_altitudes)
        kalt: dict = {}
        for k in range(min(len(gcoords), len(galts))):
            if galts[k] is not None:
                kalt.setdefault(_key(*gcoords[k]), float(galts[k]))
        if kalt:
            gs_pieces.append((g, kalt))
            gs_all_keys |= set(kalt)
    if not gs_pieces:
        return 0, set()

    # Service-road network: each shape's node keys, an apron-touch flag, and an
    # adjacency (two service shapes are adjacent when they share a node key).  BFS
    # from the apron-touching shapes marks every APRON-REACHABLE service shape.
    svc = []                   # [(shape, keyset)]
    for c in layout.shapes:
        if c.role not in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
            continue
        if c.polygon is None or c.polygon.is_empty:
            continue
        ks = {_key(x, y) for (x, y) in _open_ring(list(c.polygon.exterior.coords))}
        svc.append((c, ks))
    if not svc:
        return 0, set()
    key_to_svc: dict = {}
    for si, (_c, ks) in enumerate(svc):
        for k in ks:
            key_to_svc.setdefault(k, []).append(si)
    reachable: set = set()
    stack = [si for si, (_c, ks) in enumerate(svc) if ks & apron_keys]
    reachable.update(stack)
    while stack:
        si = stack.pop()
        for k in svc[si][1]:
            for sj in key_to_svc.get(k, ()):
                if sj not in reachable:
                    reachable.add(sj)
                    stack.append(sj)

    from shapely.geometry import Point

    MAX_ROUTE = 90.0           # cap the route distance budgeted (m)
    RAISE_W = 14.0             # half-width of the truck-route corridor to raise

    # ── GROUNDSIDE PIN LAW BOUND (item 3(a); was the §C DEM bound) ───────
    # Measured defect 2026-07-30: ``gs_pin`` anchors sit +7.76 m MEDIAN
    # above their own DEM (max +9.88), and they are independently the floor
    # witness for 4,213 broken nodes.  Mechanism: ``lo = base_elev −
    # cap·route_len − dem_gs`` below caps ``route_len`` at ``MAX_ROUTE``
    # but leaves the LIFT ITSELF unbounded — a high apron launders its own
    # error into a HARD pin that then locks the error in.
    #
    # THE BOUND IS ON THE VALUE, AND ITS DATUM IS THE WELD.  §C answered
    # the defect with "a pin may not exceed its OWN DEM by more than
    # ``cap · MOUTH_ALLOWANCE_M``".  That made raw ground a solver bound,
    # which the 2026-08-05 ruling forbids and which the constant-DEM oracle
    # fails by inspection (DEM ≡ c ⇒ every pin ceilinged at c + 0.75 m, so
    # a lot welding to pavement above that is clamped BELOW its lawful
    # level and emits a violation on ground with no relief).  The datum is
    # now the surface the pin welds to — ``base_elev``, the SOLVED apron /
    # connector variable at the deep end of the truck route — carrying the
    # reach law plus the SAME one-throat allowance
    # (:func:`gs_pin_law_ceiling`).  Where the connector cannot reach the
    # apron mouth inside that bound the deficit still surfaces AIRSIDE (an
    # over-cap connector chord / mouth step) and is never resolved by
    # lifting groundside.
    #
    # ``MOUTH_ALLOWANCE_M`` is defined ONCE at module level
    # (:func:`gs_mouth_allowance_m`) because the groundside FEASIBILITY-
    # WITNESS CLAUSE reads the same scalar — see the module header.
    _gs_float_cap = gs_pin_float_cap(cap)

    # Apron nodes (x, y, idx) — for the route ANCHOR elevation (apron at the deep
    # end of the truck route) and for the apron-arm RAISE along the route; plus the
    # connector/service nodes (the corridor includes the connector itself).
    apron_pts = []
    pav_pts = []
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.role == ROLE_APRON:
            tgt_apron = True
        elif s.role in (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION):
            tgt_apron = False
        else:
            continue
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            i = bucket_to_idx.get(_key(x, y))
            if i is not None and i < len(elev):
                pav_pts.append((x, y, i))
                if tgt_apron:
                    apron_pts.append((x, y, i))
    centerlines = [cl.line for cl in
                   (getattr(layout, "apt_service_centerlines", None) or [])
                   if cl.line is not None and not cl.line.is_empty]

    def _nearest_apron_elev(px, py, tol=16.0):
        best = None
        for (ax, ay, ai) in apron_pts:
            d = math.hypot(ax - px, ay - py)
            if d <= tol and (best is None or d < best[0]):
                best = (d, elev[ai])
        return best[1] if best else None

    # ── Per apron-reachable connector: follow its TRUCK ROUTE to the apron ────
    # The route is the truck centerline through the connector; budget the reach
    # over its FULL length (groundside edge → apron base, ~55 m) against the apron's
    # elevation at that base — NOT just the connector's own span — so the groundside
    # can sit ``cap·route_len`` above the apron (user 2026-06-27).  Stash each route
    # (with its groundside-mouth arc + direction) for the RAISE pass.
    bounds: dict = {}          # id(g) -> [g, lo, hi]
    routes = []                # (id(g), ln, gm_s, apron_dir, route_len, dem_mouth)
    # THE LAW CEILING per piece (item 3(a)): ``min`` over the serving
    # routes of :func:`gs_pin_law_ceiling` — an ABSOLUTE elevation built
    # from ``base_elev`` (a SOLVED apron / connector variable) and the
    # reach law.  A piece with no serving route never gets an entry, and a
    # missing entry means NO CEILING (see the enforcement pass below) —
    # never a fall back to the DEM sample.
    law_ceiling: dict = {}     # id(g) -> absolute ceiling (m)
    for si in reachable:
        c, _ks = svc[si]
        cnodes = [(x, y, bucket_to_idx.get(_key(x, y)))
                  for (x, y) in _open_ring(list(c.polygon.exterior.coords))]
        cen = c.polygon.centroid
        # the SHORTEST centerline that actually runs through this connector (avoid a
        # long through-airport route whose far end is hundreds of metres away).
        local = [L for L in centerlines if L.distance(cen) <= 8.0]
        ln = min(local, key=lambda L: L.length) if local else None
        for (g, kalt) in gs_pieces:
            gmouth = [(x, y) for (x, y, _i) in cnodes if _key(x, y) in kalt]
            if not gmouth:
                continue
            gmx = sum(p[0] for p in gmouth) / len(gmouth)
            gmy = sum(p[1] for p in gmouth) / len(gmouth)
            dem_gs = sum(kalt[_key(x, y)] for (x, y) in gmouth) / len(gmouth)
            gm_s = apron_dir = route_len = base_elev = None
            if ln is not None:
                gm_s = ln.project(Point(gmx, gmy))
                # apron side = the centerline end FARTHER from the groundside piece.
                e0, e1 = ln.coords[0], ln.coords[-1]
                apron_end_s = (0.0 if g.polygon.distance(Point(e0))
                               >= g.polygon.distance(Point(e1)) else ln.length)
                apron_dir = 1.0 if apron_end_s > gm_s else -1.0
                route_len = min(abs(apron_end_s - gm_s), MAX_ROUTE)
                bp = ln.interpolate(max(0.0, min(ln.length,
                                                 gm_s + apron_dir * route_len)))
                base_elev = _nearest_apron_elev(bp.x, bp.y)
            if base_elev is None:
                # Fallback: no usable centerline → reference the connector's own
                # apron-ward mouth, budget over its span (the earlier model).
                ref_nodes = [i for (x, y, i) in cnodes
                             if i is not None and i < len(elev)
                             and _key(x, y) not in gs_all_keys]
                if not ref_nodes:
                    continue
                base_elev = sum(elev[i] for i in ref_nodes) / len(ref_nodes)
                route_len = min(math.hypot(x - gmx, y - gmy)
                                for (x, y, i) in cnodes if i in ref_nodes)
                ln = None
            if route_len < 1e-6:
                continue
            budget = cap * route_len
            lo = base_elev - budget - dem_gs
            hi = base_elev + budget - dem_gs
            b = bounds.get(id(g))
            if b is None:
                bounds[id(g)] = [g, lo, hi]
            else:
                b[1] = max(b[1], lo)
                b[2] = min(b[2], hi)
            # LAW CEILING (item 3(a)): the weld datum is ``base_elev`` — a
            # SOLVED pavement variable — never ``dem_gs``.  Several routes
            # serve one piece; the ceiling is the tightest of them (the
            # same INTERSECTION rule the shift bounds use one line above).
            _lc = gs_pin_law_ceiling(base_elev, route_len, cap)
            _prev_lc = law_ceiling.get(id(g))
            law_ceiling[id(g)] = (_lc if _prev_lc is None
                                  else min(_prev_lc, _lc))
            routes.append((id(g), ln, gm_s, apron_dir, route_len, dem_gs,
                           (gmx, gmy)))

    n = 0
    # Groundside-mouth points per piece (stashed with each route above) —
    # the anchor geometry for the mouth-decay relevel below.
    mouth_pts: dict = {}
    for (gid, _ln, _gm_s, _dir, _rl, _dm, (gmx, gmy)) in routes:
        mouth_pts.setdefault(gid, []).append((gmx, gmy))
    _mouth_decay = _os.environ.get(
        "O4_GROUNDSIDE_MOUTH_DECAY", "1") == "1"
    deltas: dict = {}
    for gid, (g, lo, hi) in bounds.items():
        # Closest-to-DEM shift inside the feasible band; if the connectors'
        # reaches don't overlap (no uniform shift keeps them all <=cap) fall back
        # to the band midpoint, which minimises the worst residual.
        delta = (min(max(0.0, lo), hi) if lo <= hi else 0.5 * (lo + hi))
        # LAW BOUND (item 3(a), replacing the §C.2 DEM bound): the shift
        # may never lift the piece past the REACH CEILING its connectors
        # justify, plus one throat of allowance.  ``hi`` is already that
        # ceiling expressed in shift space (``min`` over the serving
        # routes of ``base_elev + cap·route_len − dem_mouth``), so the
        # bound is ``hi + cap·MOUTH_ALLOWANCE_M`` — the same allowance,
        # measured from the SOLVED weld datum instead of the ground.
        # ``min`` only: a LOWERING shift (the apron sits below the lot's
        # seed) is honest and stays.
        #
        # WHAT ACTUALLY BINDS.  For a consistent piece (``lo <= hi``) the
        # shift is already ``<= hi``, so this is inert — the reach law is
        # the bound, as it should be.  It binds exactly the contradictory
        # case (``lo > hi``, connectors that cannot all be satisfied),
        # whose mid-point fallback was the widest float in the measured
        # set; that case is now capped by law rather than by terrain.
        _shift_ceiling = hi + _gs_float_cap
        if delta > _shift_ceiling:
            delta = _shift_ceiling
        deltas[gid] = delta
        if abs(delta) < 1e-6:
            continue
        mpts = mouth_pts.get(gid) or []
        if _mouth_decay and mpts:
            # MOUTH-DECAY relevel (user 2026-07-04, CYXY lot #35): the
            # UNIFORM shift sank a 12 k m² lot 3.8 m below terrain
            # everywhere because its 53 m route can only climb
            # ``cap·53`` — but only the MOUTH must meet the road; the
            # lot interior is existing terrain-level pavement.  Each
            # node takes the shift the mouth needs, decayed toward zero
            # at ``cap`` per metre of distance from the nearest mouth —
            # the mouth still sits exactly at the reachable level (the
            # weld + RAISE below read the shifted ring), the interior
            # stays at DEM, and the in-between ramps at ≤cap.  A small
            # piece (everything within ``|delta|/cap`` of its mouth)
            # degenerates to the uniform shift.
            coords = list(g.polygon.exterior.coords)
            new_alts = []
            for k, a in enumerate(g.node_altitudes):
                if a is None:
                    new_alts.append(None)
                    continue
                x, y = coords[min(k, len(coords) - 1)]
                d = min(math.hypot(x - mx, y - my) for (mx, my) in mpts)
                mag = max(0.0, abs(delta) - cap * d)
                new_alts.append(a + math.copysign(mag, delta)
                                if mag > 0.0 else a)
            g.node_altitudes = new_alts
        else:
            g.node_altitudes = [
                (a + delta) if a is not None else None
                for a in g.node_altitudes]
        n += 1

    # CHORD-LIMIT every welded piece BEFORE the weld reads it (lockstep
    # with the post-solve ``_grade_limit_groundside_chords``): the weld
    # pins service-road nodes to these ring values, and the late limiter
    # rewrites the LOT ring only — two writers for the same physical
    # node left the road pinned 1.5 m off the emitted lot (CYXY #41,
    # 15 % road chords after emit consensus).  Limiting here makes the
    # solve-time field the FINAL field (the late pass is idempotent on
    # an already-limited ring).
    from auto_patch.groundside import chord_limit_ring_altitudes
    from auto_patch.config import GROUNDSIDE_MAX_GRADE
    for (g, _lo, _hi) in bounds.values():
        if not g.node_altitudes:
            continue
        g.node_altitudes = chord_limit_ring_altitudes(
            list(g.polygon.exterior.coords), g.node_altitudes,
            cap=GROUNDSIDE_MAX_GRADE)

    # ── LOT↔LOT WELD RECONCILIATION on service rings ─────────────────────
    # (user 2026-07-06, HECA service_road #522).  One road ring can weld to
    # TWO different lots whose re-levelled mouth values disagree beyond the
    # road cap * distance — an unfixable step between two hard welds (the
    # DEM-follow break blend only evaluates INTERIOR nodes, and both ends
    # are anchors).  Lots are FINAL at this point (only the connector reach
    # above moves them), so reconciling here is sound: the SMALLER lot
    # adopts the larger's ±cap·d band (largest-piece-first precedent
    # below), applied as a decay cone (fading at the groundside cap toward
    # the lot interior) so the ring stays Lipschitz and the chord limiter
    # stays idempotent.  Conflicts against BUILDING PADS / APRON bodies are
    # NOT handled here — those move later in the movable-pad yield
    # projection, so they are verified and relaxed post-yield instead
    # (``solve.py`` mouth verify-and-relax).
    _BAND_MARGIN_M = 0.01      # stay inside the band after emit rounding
    svc_ring_pts = []          # per service shape: [(key, (x, y)), ...]
    for (_c, _ks) in svc:
        _pts = [(_key(x, y), (x, y))
                for (x, y) in _open_ring(list(_c.polygon.exterior.coords))]
        svc_ring_pts.append(_pts)
    # Current (post-decay, post-limit) lot value per key; largest lot
    # owns a shared key, mirroring the gs_key_alt precedence below.
    lot_key_val: dict = {}     # key -> (area, lot shape, current value)
    for (g, _kalt) in sorted(gs_pieces,
                             key=lambda t: -t[0].polygon.area):
        gcoords = list(g.polygon.exterior.coords)
        galts = list(g.node_altitudes or [])
        for kidx in range(min(len(gcoords), len(galts))):
            if galts[kidx] is None:
                continue
            kk = _key(*gcoords[kidx])
            if kk not in lot_key_val:
                lot_key_val[kk] = (g.polygon.area, g, float(galts[kidx]))
    # Collect per-lot clamp deltas from lot↔lot pairs that share a
    # service ring (the pair the within-shape law measures).
    adjustments: dict = {}     # id(lot) -> [lot, [((x, y), delta)]]

    def _clamp_into(target_list, pt, cur, lo_b, hi_b):
        tgt = min(max(cur, lo_b), hi_b)
        if abs(tgt - cur) > 1e-4:
            target_list.append((pt, tgt, tgt - cur))

    for _pts in svc_ring_pts:
        lots = [(k, p, lot_key_val[k]) for (k, p) in _pts
                if k in lot_key_val]
        if len({id(v[1]) for (_k, _p, v) in lots}) < 2:
            continue
        for ai in range(len(lots)):
            for bi in range(ai + 1, len(lots)):
                (_ka, pa, (aa, ga, va)) = lots[ai]
                (_kb, pb, (ab, gb, vb)) = lots[bi]
                if ga is gb:
                    continue   # same ring: its own chord limit governs
                d = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
                band = max(0.0, cap * d - _BAND_MARGIN_M)
                if abs(va - vb) <= band:
                    continue
                if aa >= ab:   # smaller lot adopts the larger's band
                    entry = adjustments.setdefault(id(gb), [gb, []])
                    _clamp_into(entry[1], pb, vb, va - band, va + band)
                else:
                    entry = adjustments.setdefault(id(ga), [ga, []])
                    _clamp_into(entry[1], pa, va, vb - band, vb + band)
    n_reconciled = 0
    for (g, adjs) in adjustments.values():
        if not adjs:
            continue
        gcoords = list(g.polygon.exterior.coords)
        new_alts = list(g.node_altitudes)
        # ABSOLUTE Lipschitz support around each moved mouth (not a
        # relative delta cone): the ring near a mouth typically sits
        # exactly at the cap already, so ``old + (delta − cap·d)``
        # under-raises neighbours by the pre-existing slope and leaves
        # the mouth pair over cap (CYXY #184: an at-cap 4.00 % pair
        # re-emitted at 4.64 %).  Support = the new mouth value minus
        # (plus) cap·distance — the tightest field containing the
        # adopted mouth.
        for j in range(min(len(gcoords), len(new_alts))):
            if new_alts[j] is None:
                continue
            xj, yj = gcoords[j]
            val = new_alts[j]
            for ((ax, ay), tgt, dv) in adjs:
                dd = math.hypot(xj - ax, yj - ay)
                if dv > 0.0:
                    val = max(val, tgt - GROUNDSIDE_MAX_GRADE * dd)
                else:
                    val = min(val, tgt + GROUNDSIDE_MAX_GRADE * dd)
            new_alts[j] = val
        g.node_altitudes = chord_limit_ring_altitudes(
            gcoords, new_alts, cap=GROUNDSIDE_MAX_GRADE)
        n_reconciled += 1
    if n_reconciled and _os.environ.get("O4_STEP_DEBUG") == "1":
        print(f"  [groundside-reach] mouth reconciliation adjusted "
              f"{n_reconciled} lot ring(s).")

    # ── ENFORCE THE LAW CEILING ON THE FINAL RING (item 3(a)) ────────────
    # The shift clamp above bounds the RELEVEL; two later writers can still
    # push a ring vertex up — the lot↔lot mouth reconciliation (a smaller
    # lot adopts a larger lot's band) and the absolute-Lipschitz support it
    # paints.  The bound is a VALUE bound, so enforce it on the value that
    # is actually welded.
    #
    # THE DATUM IS THE WELD, NOT THE GROUND.  The ceiling at a ring vertex
    # is ``law_ceiling[piece] + GROUNDSIDE_MAX_GRADE · d`` where ``d`` is
    # the distance to the piece's nearest MOUTH — the tightest field that
    # contains the lawful mouth value and grades away from it at the lot's
    # own cap (the same absolute-Lipschitz support the lot↔lot
    # reconciliation above paints, so the two agree by construction).  A
    # vertex above that field is over-cap from its own mouth and would be
    # cut by ``chord_limit_ring_altitudes`` anyway; the lot INTERIOR, which
    # the terrace law leaves free, is never clamped by a distant mouth.
    #
    # NO DATUM ⇒ NO CEILING (owner-directed disposition, item 3(a)): a
    # piece with no serving route has no weld datum, so nothing bounds it
    # from above.  It must NEVER fall back to its DEM sample — that is the
    # exact defect this replaces.  Such a piece is also never re-levelled
    # (it is not in ``bounds``), so it simply stays at its seed.
    #
    # ``law_ceiling_key`` is stashed per canonical key for the post-yield
    # mouth-relax, whose re-projection would otherwise re-open the same
    # door (spec §C.2 ★).
    law_ceiling_key: dict = {}
    for (g, _kalt) in gs_pieces:            # the piece's DEM map is not read
        gid = id(g)
        base_ceil = law_ceiling.get(gid)
        mpts = mouth_pts.get(gid) or []
        if base_ceil is None or not mpts:
            continue                       # no weld datum → unbounded above
        gcoords = list(g.polygon.exterior.coords)
        galts = list(g.node_altitudes or [])
        new_alts = list(galts)
        touched = False
        for k in range(min(len(gcoords), len(galts))):
            if galts[k] is None:
                continue
            gx, gy = gcoords[k]
            d = min(math.hypot(gx - mx, gy - my) for (mx, my) in mpts)
            ceil_k = base_ceil + GROUNDSIDE_MAX_GRADE * d
            kk = _key(gx, gy)
            if kk not in law_ceiling_key or ceil_k < law_ceiling_key[kk]:
                law_ceiling_key[kk] = ceil_k
            if galts[k] > ceil_k:
                new_alts[k] = ceil_k
                touched = True
        if touched:
            g.node_altitudes = chord_limit_ring_altitudes(
                gcoords, new_alts, cap=GROUNDSIDE_MAX_GRADE)

    # (now-shifted) groundside altitude per key, for the weld.  LARGEST
    # piece first: where a big lot and a sliver connector piece share a
    # mouth key with different altitudes, the mouth serves the LOT
    # (user 2026-07-04, CYXY P4: welding to the 100 m² demoted
    # connector at 698.5 left the road 3 m under the 49 k m² lot).
    gs_key_alt: dict = {}
    gs_key_owner: dict = {}
    for (g, _kalt) in sorted(gs_pieces,
                             key=lambda t: -t[0].polygon.area):
        gcoords = list(g.polygon.exterior.coords)
        galts = list(g.node_altitudes)
        for k in range(min(len(gcoords), len(galts))):
            if galts[k] is not None:
                kk = _key(*gcoords[k])
                if kk not in gs_key_alt:
                    gs_key_alt[kk] = float(galts[k])
                    gs_key_owner[kk] = id(g)

    # ``hard`` = the returned truth-pin set.  Only WELDS go in it (shared
    # road/apron↔lot geometry takes the lot's value — physical identity).
    # The RAISE below writes elevation SEEDS but does NOT pin: a raised
    # taper value is a heuristic floor, and pinning it hard froze arm
    # nodes 1.3 m under the adjacent welded mouth (CYXY route D, 61 %
    # chord after planarize mixed the two fields into one ring) — the
    # post-reach projections grade the arm into the welds instead.
    hard: set = set()

    # ── RAISE the apron arm + connector along the truck route ────────────────
    # The narrow apron arm is welded to the connector, so as the connector climbs at
    # <=cap to the (now higher) groundside, that climb is carried BACK along the
    # truck route: every apron/connector node in the route corridor takes the
    # SELF-TAPERING profile ``gs_level − cap·(arc back from the groundside mouth)``.
    # The taper auto-stops where it drops below the apron's own elevation (the base),
    # so the raise is confined to the arm; the caller grades the apron body into it.
    for (gid, ln, gm_s, apron_dir, route_len, dem_mouth, (gmx, gmy)) in routes:
        delta = deltas.get(gid, 0.0)
        gs_level = dem_mouth + delta
        # The arm must rise whenever the groundside ends up ABOVE the apron base —
        # even when the piece was LOWERED toward a reachable level (delta < 0, its
        # DEM was higher than reachable).  The self-taper raises only where needed.
        if ln is None:
            continue
        for (px, py, pi) in pav_pts:
            p = Point(px, py)
            if ln.distance(p) > RAISE_W:
                continue
            # corridor membership = along the route (apron side, within route_len);
            # but the PROFILE tapers by STRAIGHT distance from the groundside mouth,
            # so the connector rect (graded on its straight span, not the curved
            # centerline arc) comes out at exactly <=cap, not the arc-inflated rate.
            s = ln.project(p)
            if (s - gm_s) * apron_dir < -2.0 or (s - gm_s) * apron_dir \
                    > route_len + 5.0:
                continue
            straight = math.hypot(px - gmx, py - gmy)
            tgt = gs_level - cap * straight
            if tgt > elev[pi] + 1e-3:
                elev[pi] = tgt

    # ── WELD each connector's groundside mouth to the shifted groundside ─────
    # Reachable connectors weld as before.  An UNREACHABLE connector still
    # welds where its truck ROUTE ENDS at the lot — a destination road must
    # CLIMB to the lot it serves (user 2026-07-04, CYXY P4: the road emitted
    # 3.1 m below the lot at coincident nodes).  Blanket-welding every
    # unreachable lot-touching connector measured +215 within-shape pairs
    # (mouth pins fighting DEM-followed road surfaces mid-network); the
    # route-END scope pins only the served destination mouth.
    route_end_points = []
    for ln in centerlines:
        try:
            route_end_points.append(Point(*ln.coords[0]))
            route_end_points.append(Point(*ln.coords[-1]))
        except (ValueError, IndexError):
            continue
    # Coordinate keys this pass welded (rounded like the emit consensus) —
    # persisted on the layout so the POST-solve groundside chord limiter
    # can re-adopt its re-limited values onto exactly these nodes (and no
    # others: a road passing a DEM-stay lot keeps its by-design seam).
    weld_coord_keys: set = set()
    for si in range(len(svc)):
        c, _ks = svc[si]
        is_reachable = si in reachable
        for (x, y) in _open_ring(list(c.polygon.exterior.coords)):
            k = _key(x, y)
            a = gs_key_alt.get(k)
            if a is None:
                continue
            if not is_reachable:
                p = Point(x, y)
                if not any(p.distance(ep) <= 15.0
                           for ep in route_end_points):
                    continue
            i = bucket_to_idx.get(k)
            if i is not None and i < len(elev):
                elev[i] = a
                hard.add(i)
                weld_coord_keys.add((round(x, 2), round(y, 2)))

    # ── WELD every pavement node ON a re-levelled lot ring ───────────────────
    # The svc-ring weld above misses the MOUTH vertex when it lives on the
    # APRON arm instead of a service shape (CYXY route D: the shared lot
    # vertex belonged to the apron at solve time, the RAISE floored it
    # 1.3 m under the lot's welded level, and post-solve planarize copied
    # that value into the road ring → 15 % mixed-field chords).  The
    # road↔lot connection is FIRST-CLASS shared geometry no matter which
    # role carries the vertex: any solver node whose canonical key lies on
    # a re-levelled piece's ring takes that ring's value.  Scoped to
    # pieces the reach actually processed (``bounds``) — pieces with no
    # reachable connector stay DEM and pin nothing (the blanket-weld
    # regression class, +215).
    relevelled_gids = {gid for gid in bounds}
    for (px, py, pi) in pav_pts:
        k = _key(px, py)
        a = gs_key_alt.get(k)
        if a is None or gs_key_owner.get(k) not in relevelled_gids:
            continue
        if pi < len(elev):
            elev[pi] = a
            hard.add(pi)
            weld_coord_keys.add((round(px, 2), round(py, 2)))
    layout._groundside_weld_keys = weld_coord_keys
    # Per-PIN LAW ceiling in solver-index space — consumed by the post-yield
    # mouth verify-and-relax (spec §C.2 ★: a bounded pin's ADOPTED profile
    # must be bounded the same way or the lift returns through that door).
    # Also the measurement handle for the §C acceptance gate.
    #
    # RENAMED from ``_gs_pin_dem_ceiling_idx`` (item 3(a)): the datum is no
    # longer the DEM, so the name may not say so.  A pin whose piece has no
    # weld datum carries NO entry — the consumer leaves it unbounded above
    # rather than inventing a terrain bound.
    _pin_ceiling_idx: dict = {}
    for kk, ceil_k in law_ceiling_key.items():
        i = bucket_to_idx.get(kk)
        if i is None or i not in hard:
            continue
        if i not in _pin_ceiling_idx or ceil_k < _pin_ceiling_idx[i]:
            _pin_ceiling_idx[i] = float(ceil_k)
    layout._gs_pin_law_ceiling_idx = _pin_ceiling_idx
    # GROUNDSIDE FEASIBILITY-WITNESS CLAUSE (owner ruling 2026-07-30) — the
    # pinned mouth/weld nodes by CANONICAL KEY, so the later passes that
    # rebuild the node space (``final_grade_projection``) can still name the
    # anchors whose witness role the clause withdraws.  A key set only; it
    # asserts nothing on its own.
    _key_of = {i: k for k, i in bucket_to_idx.items()}
    layout._gs_pin_keys = {_key_of[i] for i in hard if i in _key_of}
    if _os.environ.get("O4_STEP_DEBUG") == "1" and _pin_ceiling_idx:
        # SLACK against the LAW ceiling (item 3(a)): the old line reported
        # float above DEM, a number the law no longer has an opinion about.
        floats = sorted(elev[i] - c for i, c in _pin_ceiling_idx.items()
                        if i < len(elev))
        if floats:
            _m50 = floats[len(floats) // 2]
            _nover = sum(1 for f in floats if f > 1e-6)
            print(f"  [gs-pin-law] {len(floats)} pin(s) with a law "
                  f"ceiling: value−ceiling median={_m50:+.2f} "
                  f"max={floats[-1]:+.2f} "
                  f"min={floats[0]:+.2f}; allowance="
                  f"{_gs_float_cap:.2f} over-ceiling={_nover}")
    return n, hard


def _line_unit_tangent(line, s):
    """Unit tangent (dx, dy) of a shapely ``LineString`` at arclength ``s``,
    from a symmetric ±(¼-length, capped 1 m) difference; ``None`` for a
    degenerate line.  Used by the parallel-road station merge's tangent guard."""
    import math
    length = line.length
    if length <= 1e-6:
        return None
    eps = min(1.0, length * 0.25)
    a = line.interpolate(max(0.0, s - eps))
    b = line.interpolate(min(length, s + eps))
    dx, dy = b.x - a.x, b.y - a.y
    norm = math.hypot(dx, dy)
    return (dx / norm, dy / norm) if norm > 1e-9 else None


def _parallel_station_merge_pairs(st_xy, station_line, tangent_at,
                                  max_gap, min_abs_cos):
    """Station-id pairs ``[(a, b), …]`` to couple for the WIDE parallel-road
    station merge (part 30m follow-up, candidate (a)).

    A pair qualifies iff the two stations are on DIFFERENT host lines, their XY
    gap is ``<= max_gap``, and their host-line tangents are NEAR-PARALLEL
    (``|cos∠(tangent_a, tangent_b)| >= min_abs_cos``).  The absolute cosine
    admits an antiparallel loop-return leg (|cos|≈1) while a distinct crossing
    road (≈90°, |cos|≈0) never qualifies — the guard that keeps the coupling to
    genuine parallel pairs.  Pure: no elevation, no I/O — unit-testable."""
    import math
    pairs = []
    grid: dict = {}
    for sid, (x, y) in st_xy.items():
        grid.setdefault((int(x // max_gap), int(y // max_gap)), []).append(sid)
    for (cx, cy), cell in grid.items():
        neigh = []
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                neigh.extend(grid.get((cx + ox, cy + oy), ()))
        for a in cell:
            ax, ay = st_xy[a]
            ta = tangent_at.get(a)
            if ta is None:
                continue
            for b in neigh:
                if b <= a or station_line[b] == station_line[a]:
                    continue
                bx, by = st_xy[b]
                if math.hypot(ax - bx, ay - by) > max_gap:
                    continue
                tb = tangent_at.get(b)
                if tb is None:
                    continue
                if abs(ta[0] * tb[0] + ta[1] * tb[1]) < min_abs_cos:
                    continue                # crossing / divergent → distinct
                pairs.append((a, b))
    return pairs


def _svc_spine_station_seeds(layout, svc_nodes, node_pos, anchors,
                             dem_elev, cap, node_ceil, node_floor,
                             node_ceil_dist, node_floor_dist,
                             prox_pairs=()):
    """SPINE-FIRST seed field (config.SVC_SPINE_FIRST, part 30m): the service
    network's DEM-follow computed per spine STATION and shared by the whole
    cross-section, instead of per ring vertex.

    Per-vertex DEM-follow let a road's two long edges bind to DIFFERENT
    anchor regimes (each side clamps into the reach band of ITS nearest
    welds), which rendered a cross-road tear — CYXY 2.49 m at
    60.7092306,-135.0738928.  Here the ROAD HUGS TERRAIN LONGITUDINALLY
    within its cap along the spine, and every ring vertex of a cross-section
    takes the SAME station value, so a tear across the road cannot even be
    seeded.  These are SEEDS ONLY (soft): the road's within-shape law edges
    (``grade_graph.SOFT_VISIBILITY_ROLES`` + the service lateral pass, same
    gate) are the authority and the solve's final projections remain the
    sole writer.

    Mechanism, mirroring the per-vertex operator 1:1 but on stations:
      * stations = clusters of the service ring vertices' perpendicular
        projections onto the service (truck-route) centerlines — the spine
        arclength is the station coordinate, so opposite-edge partners
        (aligned by ``insert_service_lateral_nodes``) share one station;
      * station DEM = mean vertex DEM of the cluster, LOW-PASSED along the
        line (±~1.5 station steps) — the seed follows terrain at station
        wavelength, not raster noise (a lone unpaired station otherwise
        imprints its own DEM sample as a cross/diagonal step);
      * station band = the INTERSECTION of the member vertices' node-graph
        reach bands (``[max member floor, min member ceil]``) — the SAME
        cap-Lipschitz reach the per-vertex operator used, so connectivity
        to the mouth welds is inherited from the proven node graph (an
        earlier separate station-graph Dijkstra left whole chains
        anchor-unreachable), while the INTERSECTION makes both edges obey
        BOTH sides' anchors at once;
      * clamp + the SAME distance-weighted break blend as the per-vertex
        path (an empty intersection is exactly the old two-regime
        contradiction, now surfaced once per cross-section); broken
        stations quarantine their members through the existing
        ``service_break`` machinery.

    Returns ``(node_target, broken_nodes)``: seed values for the non-anchor
    vertices that found a station (vertices with no spine within reach — wide
    service-junction yards — keep the legacy per-vertex path), and the subset
    belonging to genuinely broken stations."""
    import math as _m
    from auto_patch.config import ROAD_CARVE_MAX_WIDTH_M, SPINE_STEP_M

    try:
        from shapely.geometry import LineString, Point
        from shapely.strtree import STRtree
    except Exception:                                   # pragma: no cover
        return {}, set()

    lines = []
    for cl in (getattr(layout, "apt_taxi_centerlines", None) or []):
        if not getattr(cl, "is_service", False):
            continue
        ln = getattr(cl, "line", None)
        if ln is None or getattr(ln, "is_empty", True):
            continue
        try:
            cs = list(ln.coords)
        except Exception:
            continue
        if len(cs) >= 2:
            lines.append(LineString(cs))
    if not lines:
        return {}, set()

    R = ROAD_CARVE_MAX_WIDTH_M / 2.0 + 2.0
    tree = STRtree(lines)

    # node → (line_idx, arclength) for the nearest service line within R.
    node_station_raw: dict = {}
    for i in sorted(svc_nodes):
        p = node_pos.get(i)
        if p is None:
            continue
        P = Point(p)
        try:
            cand = tree.query(P.buffer(R))
        except Exception:
            continue
        best = None
        for qi in cand:
            li = int(qi)
            d = lines[li].distance(P)
            if d <= R and (best is None or d < best[0]):
                best = (d, li, lines[li].project(P))
        if best is not None:
            node_station_raw[i] = (best[1], best[2])
    if not node_station_raw:
        return {}, set()

    # Cluster per-line arclengths into stations (cross-section partners
    # project to near-identical s; 2.0 m absorbs foot/weld noise while
    # staying far under the ~12 m station spacing).
    _CLUSTER_GAP_M = 2.0
    by_line: dict = {}
    for i, (li, s) in node_station_raw.items():
        by_line.setdefault(li, []).append((s, i))
    stations: list = []          # station → dict(line, s, members)
    node_station: dict = {}
    for li, lst in by_line.items():
        lst.sort()
        cur = None
        for (s, i) in lst:
            if cur is None or s - cur["s_max"] > _CLUSTER_GAP_M:
                cur = {"line": li, "s_sum": 0.0, "s_max": s, "n": 0,
                       "members": []}
                stations.append(cur)
            cur["s_sum"] += s
            cur["s_max"] = max(cur["s_max"], s)
            cur["n"] += 1
            cur["members"].append(i)
            node_station[i] = len(stations) - 1
    for st in stations:
        st["s"] = st["s_sum"] / st["n"]

    # Station XY + per-line ordered station lists.
    st_xy = {}
    for sid, st in enumerate(stations):
        q = lines[st["line"]].interpolate(st["s"])
        st_xy[sid] = (q.x, q.y)
    by_line_sid: dict = {}
    for sid, st in enumerate(stations):
        by_line_sid.setdefault(st["line"], []).append(sid)

    # PARALLEL-ROAD STATION MERGE — the station-level analogue of the node
    # graph's O4_SVC_PROXIMITY_COUPLE (part 27, HECA #510↔#517): two service
    # lines running < ~2 m apart carry separate station chains, so each
    # road's cross-section would seed from ITS line alone and the pair can
    # re-open the metre-scale wall the node coupling closed (measured at
    # HECA #576↔#584: cross-shape 0.16 m → 0.84 m without this merge).
    # Stations of DIFFERENT lines within the window share ONE merged member
    # set → one DEM mean, one band intersection, one target.  Union-find;
    # the merged station keeps the first sid as root.
    _PROX_M = 2.0
    parent = list(range(len(stations)))

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    _grid: dict = {}
    for sid, (x, y) in st_xy.items():
        _grid.setdefault((int(x // _PROX_M), int(y // _PROX_M)),
                         []).append(sid)
    for (cx, cy), cell in _grid.items():
        neigh = []
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                neigh.extend(_grid.get((cx + ox, cy + oy), ()))
        for a in cell:
            ax, ay = st_xy[a]
            for b in neigh:
                if b <= a or stations[b]["line"] == stations[a]["line"]:
                    continue
                bx, by = st_xy[b]
                if _m.hypot(ax - bx, ay - by) <= _PROX_M:
                    ra, rb = _find(a), _find(b)
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
    # … and through the NODE couples (the exact part-27 proximity notion):
    # two parallel lines' stations are longitudinally OFFSET in general, so
    # the XY merge above can miss them (HECA #576↔#584 stayed 0.84 m apart
    # with XY-merge alone) — but their RING nodes across the sliver are
    # coupled, and coupled nodes' stations must share one cross-section.
    for (i, j) in prox_pairs:
        si, sj = node_station.get(i), node_station.get(j)
        if si is None or sj is None or si == sj:
            continue
        ra, rb = _find(si), _find(sj)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # WIDE PARALLEL-ROAD STATION MERGE (part 30m follow-up, candidate (a)):
    # the 2 m XY window and the node proximity couple (both ~2 m) MISS a
    # several-metre rendered gap, so two NON-touching but near-parallel service
    # ways a few metres apart still seed from SEPARATE spine regimes and seat a
    # metre-scale wall across the gap (HECA -10494 service_road ↔ -10108
    # service_junction, ~6.7 m gap: per-vertex 0.845 m).  Couple their stations
    # out to ``PARALLEL_SERVICE_STATION_MERGE_MAX_GAP_M`` when the two host
    # lines run NEAR-PARALLEL at those stations — a TANGENT guard so a distinct
    # crossing road (≈90°) never couples, only a genuine parallel pair (a loop
    # road's return leg counts: antiparallel, |cos|≈1).  The merge shares one
    # DEM seed + one band INTERSECTION across the cross-section, so the wall is
    # single-valued (unseedable), not merely reduced.  Gate off ⇒ untouched.
    if PARALLEL_SERVICE_STATION_MERGE and len(stations) > 1:
        tangent_at = {
            sid: _line_unit_tangent(lines[st["line"]], st["s"])
            for sid, st in enumerate(stations)}
        station_line = {sid: st["line"] for sid, st in enumerate(stations)}
        for (a, b) in _parallel_station_merge_pairs(
                st_xy, station_line, tangent_at,
                PARALLEL_SERVICE_STATION_MERGE_MAX_GAP_M,
                PARALLEL_SERVICE_STATION_MERGE_MIN_ABS_COS):
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

    _merged = 0
    for sid in range(len(stations)):
        r = _find(sid)
        if r != sid:
            stations[r]["members"].extend(stations[sid]["members"])
            for i in stations[sid]["members"]:
                node_station[i] = r
            stations[sid]["members"] = []
            _merged += 1

    # Raw station DEM = mean member DEM; then LOW-PASS along each line so a
    # lone unpaired station cannot imprint a raster-noise step on the seed
    # (measured at CYXY -10193: adjacent raw stations 718.86/719.07/718.99
    # → a 4.4 % diagonal pair the projections had already frozen into the
    # clearance welds by emit time).
    raw_de: dict = {}
    for sid, st in enumerate(stations):
        dems = [dem_elev[i] for i in st["members"]
                if i < len(dem_elev) and dem_elev[i] is not None]
        if dems:
            raw_de[sid] = sum(dems) / len(dems)
    _SMOOTH_M = 1.5 * SPINE_STEP_M
    smooth_de: dict = {}
    for li, sids in by_line_sid.items():
        sids.sort(key=lambda k: stations[k]["s"])
        with_de = [k for k in sids if k in raw_de]
        for k in with_de:
            s0 = stations[k]["s"]
            window = [raw_de[j] for j in with_de
                      if abs(stations[j]["s"] - s0) <= _SMOOTH_M]
            smooth_de[k] = sum(window) / len(window)

    # Station reach band = INTERSECTION of the member vertices' node-graph
    # bands — the same anchors, the same cap-Lipschitz metric, the proven
    # connectivity (ring edges + proximity couples), but binding BOTH edges
    # of the cross-section to BOTH sides' anchors at once.
    import os as _os
    _dbg_spec = _os.environ.get("O4_SVC_SPINE_DEBUG_LL")
    _dbg_xy = None
    if _dbg_spec:
        try:
            _dla, _dlo = (float(v) for v in _dbg_spec.split(","))
            _dbg_xy = layout.ll_to_m(_dla, _dlo)
        except Exception:
            _dbg_xy = None

    node_target: dict = {}
    broken_nodes: set = set()
    for sid, st in enumerate(stations):
        de = smooth_de.get(sid)
        if de is None:
            continue                    # no DEM sample → legacy per-vertex
        m_ceil = [node_ceil[i] for i in st["members"] if i in node_ceil]
        m_floor = [node_floor[i] for i in st["members"] if i in node_floor]
        c = min(m_ceil) if m_ceil else None
        f = max(m_floor) if m_floor else None
        broken = False
        if c is None:                   # unreachable from any anchor → DEM
            tgt = de
        elif f is not None and f > c + 1e-9:
            # genuine break — SAME distance-weighted blend as the
            # per-vertex operator, computed once for the cross-section
            # (weights = mean member reach distances to each regime).
            dcs = [node_ceil_dist[i] for i in st["members"]
                   if i in node_ceil_dist]
            dfs = [node_floor_dist[i] for i in st["members"]
                   if i in node_floor_dist]
            dc = (sum(dcs) / len(dcs)) if dcs else 0.0
            df = (sum(dfs) / len(dfs)) if dfs else 0.0
            t = dc / (dc + df) if (dc + df) > 1e-9 else 0.5
            tgt = c + (f - c) * t
            broken = True
        else:
            lo = f if f is not None else -float("inf")
            tgt = min(max(de, lo), c)
        for i in st["members"]:
            node_target[i] = tgt
            if broken:
                broken_nodes.add(i)
        if _dbg_xy is not None:
            sx, sy = st_xy[sid]
            if _m.hypot(sx - _dbg_xy[0], sy - _dbg_xy[1]) < 12.0:
                print(f"    [svc-spine-dbg] sid={sid} line={st['line']} "
                      f"s={st['s']:.1f} n={st['n']} de_raw={raw_de.get(sid)} "
                      f"de={de:.2f} ceil={c} floor={f} "
                      f"tgt={tgt:.2f} broken={broken} "
                      f"members={sorted(st['members'])}")
    return node_target, broken_nodes


def apply_service_road_dem_follow(layout, bucket_to_idx, elev, dem_elev, cap,
                                  anchor_extra=()):
    """Grade the service-road network to FOLLOW DEM at <=cap (user 2026-06-27).

    A ground-vehicle road is NOT airside: it rises/falls toward terrain, anchored
    only where it WELDS to the airside (taxi/apron/runway, kept at their solved
    bowl elevation) or to a groundside piece (``anchor_extra``).  Every other
    service node sits at ``clamp(DEM, reach-band-from-anchors-at-cap)`` where the
    reach band is the cap-Lipschitz envelope along the SERVICE graph (axial, edge by
    edge) — so a road ramps from its airside connection toward DEM at <=4% instead
    of being held flat in the bowl (SVC4 was ~6-11 m below terrain).  The
    road-vs-airside seam is by design (``check_grade._airside_groundside_pair``), so
    rising past a flat neighbour is not a step.

    SPINE-FIRST (config.SVC_SPINE_FIRST, default ON, part 30m): the DEM target
    is computed per spine STATION (shared by the whole cross-section) instead
    of per vertex — see ``_svc_spine_station_seeds``.  ``O4_SVC_SPINE_FIRST=0``
    restores the per-vertex behaviour below byte-identically.

    Mutates ``elev`` in place; returns the set of node indices it moved."""
    import heapq
    import os as _os
    from collections import defaultdict
    from auto_patch.layout import (
        ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION, ROLE_GROUNDSIDE_PAVEMENT)

    cps = layout.canonical_points

    def _key(x, y):
        return cps.get_or_add(float(x), float(y))

    SVC = (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION)
    # THE ONE LAW'S CAP (owner 2026-08-03, docs/RULINGS.md
    # "lateral-contiguity absorption is class-universal"; spec §1).  A road
    # stretch that is laterally contiguous with another paved class is part
    # of THAT surface: the stretch the emitter could absorb is not a service
    # shape at all any more, and a stretch it could only CAP carries the
    # cross-section's strictest cap in ``BuiltShape.lateral_cap``.  This
    # envelope consumes that number instead of its private service cap — one
    # surface, one cap, one authority — and stops exporting those nodes to
    # the break quarantine (a residual there is the contiguous surface's
    # law, i.e. a VISIBLE violation, not a second authority's pocket).
    # Gate off ⇒ ``lat_cap`` stays empty ⇒ the scalar ``cap`` arithmetic and
    # the export are unchanged, byte for byte.
    from auto_patch.config import SERVICE_LOT_ABSORPTION as _CLASS_UNIVERSAL
    lat_cap: dict = {}
    svc_nodes: set = set()
    adj = defaultdict(list)
    node_pos: dict = {}
    node_shape: dict = {}
    for s in layout.shapes:
        if s.role not in SVC or s.polygon is None or s.polygon.is_empty:
            continue
        _lc = getattr(s, "lateral_cap", None) if _CLASS_UNIVERSAL else None
        ring = _open_ring(list(s.polygon.exterior.coords))
        idxs = [bucket_to_idx.get(_key(x, y)) for (x, y) in ring]
        for k in range(len(ring)):
            i, j = idxs[k], idxs[(k + 1) % len(ring)]
            if i is None or i >= len(elev):
                continue
            svc_nodes.add(i)
            if _lc is not None:
                _prev = lat_cap.get(i)
                lat_cap[i] = (float(_lc) if _prev is None
                              else min(_prev, float(_lc)))
            node_pos.setdefault(i, ring[k])
            node_shape.setdefault(i, id(s))
            if j is not None and j != i and j < len(elev):
                import math as _m
                dd = _m.hypot(ring[k][0] - ring[(k + 1) % len(ring)][0],
                              ring[k][1] - ring[(k + 1) % len(ring)][1])
                adj[i].append((j, dd))
                adj[j].append((i, dd))
    if not svc_nodes:
        return set()

    # PROXIMITY COUPLING between near-parallel roads (user 2026-07-06,
    # HECA #510↔#517): two service shapes whose free edges run < ~2 m
    # apart carry NO shared node, so each grades to its OWN anchors and
    # the pair can emit a metre-scale wall across an unrenderable sliver
    # (measured 1.8 m over 0.9 m).  Couple nodes of DIFFERENT service
    # shapes within the window into the reach graph — both roads then
    # grade against the union of their anchors at ≤cap across the gap,
    # and genuinely contradictory anchors resolve through the same
    # break blend as any interior node.
    prox_pairs: list = []       # (i, j) couples — also merges spine stations
    import math as _m
    _PROX_M = 2.0
    _cell = _PROX_M
    _grid: dict = {}
    for i, (px, py) in node_pos.items():
        _grid.setdefault((int(px // _cell), int(py // _cell)),
                         []).append(i)
    for (cx, cy), members in _grid.items():
        neighbors = []
        for ox in (-1, 0, 1):
            for oy in (-1, 0, 1):
                neighbors.extend(_grid.get((cx + ox, cy + oy), ()))
        for i in members:
            (ix, iy) = node_pos[i]
            for j in neighbors:
                if (j <= i
                        or node_shape.get(j) == node_shape.get(i)):
                    continue
                (jx, jy) = node_pos[j]
                dd = _m.hypot(ix - jx, iy - jy)
                if 1e-6 < dd <= _PROX_M:
                    adj[i].append((j, dd))
                    adj[j].append((i, dd))
                    prox_pairs.append((i, j))

    # Anchors = service nodes that are ALSO a corner of a NON-service pavement shape
    # (the road welds to the airside there), held at their solved elevation; plus
    # any groundside-welded nodes passed in.
    anchors: dict = {}
    for s in layout.shapes:
        if (s.role in SVC or s.role == ROLE_GROUNDSIDE_PAVEMENT
                or s.polygon is None or s.polygon.is_empty):
            continue
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            i = bucket_to_idx.get(_key(x, y))
            if i in svc_nodes:
                anchors[i] = elev[i]
    for i in anchor_extra:
        if i in svc_nodes and i < len(elev):
            anchors[i] = elev[i]

    def _reach(sign):                       # +1 → ceil, −1 → floor
        # Lazy Dijkstra over the (positive) cap·distance metric: the heap
        # pops each node first at its OPTIMAL value, so every later pop
        # is skipped (>= / <=, NO epsilon — an epsilon-tolerant skip lets
        # equal-value duplicates re-expand, which goes combinatorial on
        # service networks with many equal-length parallel paths: CYXY
        # hung for 27 min here).  Each node therefore expands exactly
        # once and pushes are bounded by the edge count.
        best: dict = {}
        dist: dict = {}                     # graph distance to the
        pq = [((av if sign > 0 else -av), 0.0, a)   # value-optimal anchor
              for a, av in anchors.items()]
        heapq.heapify(pq)
        while pq:
            v, dk, k = heapq.heappop(pq)
            t = v if sign > 0 else -v
            if k in best:
                continue
            best[k] = t
            dist[k] = dk
            for (j, dd) in adj[k]:
                if j in best:
                    continue
                # ONE cap: where the lateral-contiguity law bound either end
                # of this edge to a contiguous surface, that surface's
                # (strictest) cap prices the leg.  Empty map ⇒ the service
                # cap, exactly as before.
                e_cap = cap
                if lat_cap:
                    e_cap = min(lat_cap.get(k, cap), lat_cap.get(j, cap))
                nt = t + sign * e_cap * dd
                heapq.heappush(pq, ((nt if sign > 0 else -nt),
                                    dk + dd, j))
        return best, dist

    ceil, ceil_dist = _reach(+1) if anchors else ({}, {})
    floor, floor_dist = _reach(-1) if anchors else ({}, {})
    _dbg_spec = _os.environ.get("O4_SVC_DEBUG_LL")
    if _dbg_spec:
        try:
            import math as _dbg_m
            _dla, _dlo = (float(v) for v in _dbg_spec.split(","))
            _dx, _dy = layout.ll_to_m(_dla, _dlo)
            for _i in sorted(svc_nodes):
                _p = node_pos.get(_i)
                if _p is None or _dbg_m.hypot(_p[0] - _dx,
                                              _p[1] - _dy) > 8.0:
                    continue
                print(f"    [svc-dbg] i={_i} pos=({_p[0]:.1f},{_p[1]:.1f})"
                      f" anchor={_i in anchors}"
                      f" elev={elev[_i]:.2f}"
                      f" dem={dem_elev[_i] if _i < len(dem_elev) else None}"
                      f" ceil={ceil.get(_i)} floor={floor.get(_i)}")
        except Exception as _e:
            print(f"    [svc-dbg] error {_e!r}")
    changed: set = set()
    # BREAK-BLEND EXPORT (user 2026-07-06, handover fix (b)): nodes whose
    # welded anchors contradict (floor > ceil) render the designed blend
    # below — persist them so the caller can quarantine their over-cap
    # pairs/steps instead of reporting the contained blend as actionable
    # (HECA #578↔#64: a junction weld 1 m from a road capped 0.8 m lower).
    service_break: set = getattr(layout, "_service_break_idx", None) or set()
    layout._service_break_idx = service_break
    # SPINE-FIRST (config.SVC_SPINE_FIRST, part 30m): DEM-follow computed per
    # spine STATION and shared by the whole cross-section — see
    # ``_svc_spine_station_seeds``.  Vertices with no station (wide
    # service-junction yards beyond spine reach) keep the legacy per-vertex
    # path below; anchor (weld) vertices are never reseeded on either path.
    from auto_patch.config import SVC_SPINE_FIRST as _SPINE_FIRST
    spine_target: dict = {}
    spine_broken: set = set()
    if _SPINE_FIRST:
        spine_target, spine_broken = _svc_spine_station_seeds(
            layout, svc_nodes, node_pos, anchors, dem_elev, cap,
            ceil, floor, ceil_dist, floor_dist, prox_pairs)
    _lat_bound_breaks = 0
    for i in svc_nodes:
        if i in anchors:
            continue
        if i in spine_target:
            tgt = spine_target[i]
            if i in spine_broken:
                # Laterally bound (spec §1): this node belongs to the
                # contiguous surface, whose law adjudicates it — the
                # envelope has no standing to quarantine it.  The blend
                # target below is still applied; the deficit, if any, is
                # visible to the validator.
                if i in lat_cap:
                    _lat_bound_breaks += 1
                else:
                    service_break.add(i)
            if abs(tgt - elev[i]) > 1e-3:
                elev[i] = tgt
                changed.add(i)
            continue
        de = dem_elev[i] if i < len(dem_elev) else None
        if de is None:
            continue
        c = ceil.get(i)
        f = floor.get(i)
        if c is None:                       # unreachable from any anchor → DEM
            tgt = de
        elif f is not None and f > c + 1e-9:
            # GENUINE break: the road's welded anchors (airside mouth vs
            # groundside/other weld) contradict through this node — no
            # <=cap profile connects them (user 2026-07-04: break-blend
            # support for service roads).  Same operator as
            # ``feasibility_project``'s broken-node fill: the
            # distance-weighted blend puts the surface ON the descent
            # field of each anchor at that anchor (t→0 ⇒ z=ceil field,
            # t→1 ⇒ z=floor field, continuous at the region boundary)
            # and spreads the deficit between them as one gentle
            # over-cap ramp.  Ceiling-clamping instead (the previous
            # behaviour, silently) parked the WHOLE deficit as a wall
            # at the floor-side anchor — typically the groundside mouth.
            dc = ceil_dist.get(i, 0.0)
            df = floor_dist.get(i, 0.0)
            t = dc / (dc + df) if (dc + df) > 1e-9 else 0.5
            tgt = c + (f - c) * t
            if i in lat_cap:                # laterally bound — see above
                _lat_bound_breaks += 1
            else:
                service_break.add(i)
        else:
            lo = f if f is not None else -float("inf")
            tgt = min(max(de, lo), c)
        if abs(tgt - elev[i]) > 1e-3:
            elev[i] = tgt
            changed.add(i)
    if _lat_bound_breaks:
        import O4_UI_Utils as _UI
        _UI.vprint(1,
            f"  [pav-builder] service DEM-follow: {_lat_bound_breaks} "
            f"contradiction(s) at laterally-bound node(s) NOT quarantined "
            f"— the contiguous surface's law owns them (of "
            f"{len(lat_cap)} node(s) carrying a lateral cap).")
    return changed


def _groundside_lot_rings(layout, bucket_to_idx):
    """Per groundside lot with per-vertex altitudes: the ring vertex list
    ``[(ring_index, solver_index_or_None, (x, y)), ...]`` (open ring)."""
    from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
    cps = layout.canonical_points
    out = []
    for g in layout.shapes:
        if (g.role != ROLE_GROUNDSIDE_PAVEMENT or g.polygon is None
                or g.polygon.is_empty or not g.node_altitudes):
            continue
        coords = list(g.polygon.exterior.coords)
        verts = []
        for j in range(min(len(coords), len(g.node_altitudes))):
            x, y = coords[j]
            idx = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            verts.append((j, idx, (float(x), float(y))))
        out.append((g, verts))
    return out


def expand_mouth_cluster(layout, bucket_to_idx, conflicted, welded_idx,
                         window_m: float = 12.0):
    """Grow a conflicted-mouth set to the full mouth CLUSTER: every welded
    solver node on the SAME groundside lot ring within ``window_m`` of a
    conflicted node.  Freeing the whole cluster lets the joint solve place
    one consistent mouth profile instead of wedging a single freed vertex
    between its still-hard neighbours."""
    import math as _m
    freed = set(conflicted)
    for (_g, verts) in _groundside_lot_rings(layout, bucket_to_idx):
        ring_welded = [(j, idx, p) for (j, idx, p) in verts
                       if idx is not None and idx in welded_idx]
        seeds = [(j, idx, p) for (j, idx, p) in ring_welded
                 if idx in conflicted]
        if not seeds:
            continue
        for (_j, idx, p) in ring_welded:
            if idx in freed:
                continue
            if any(_m.hypot(p[0] - sp[0], p[1] - sp[1]) <= window_m
                   for (_sj, _si, sp) in seeds):
                freed.add(idx)
    return freed


def adopt_projected_mouths(layout, bucket_to_idx, elev, freed, welded_idx):
    """LOT ADOPTS THE SOLVED MOUTH (user 2026-07-06, HECA #541/#546): after
    the mouth verify-and-relax re-projection, write the projected values of
    the freed mouth vertices back onto their groundside lot rings — exact at
    each freed vertex, cap-decay filled across non-welded ring vertices.
    Non-freed welded vertices are held fixed during the fill (their solver
    values did not move).  Deliberately NO chord-limit here: the downward-
    only limiter would drag an adopted-high mouth toward the lot's low DEM
    interior (measured: HECA #522 mouth 103.9 → 101.8, a 2.1 m weld tear);
    ring lawfulness stays with the post-solve groundside chord limiter,
    which re-adopts welded values properly.  Returns the count of adopted
    lot rings."""
    import math as _m
    from auto_patch.config import GROUNDSIDE_MAX_GRADE
    n_adopted = 0
    for (g, verts) in _groundside_lot_rings(layout, bucket_to_idx):
        alts = list(g.node_altitudes)
        freed_verts = [(j, idx, p) for (j, idx, p) in verts
                       if idx is not None and idx in freed
                       and j < len(alts) and alts[j] is not None]
        if not freed_verts:
            continue
        held = {j for (j, idx, _p) in verts
                if idx is not None and idx in welded_idx
                and idx not in freed}
        # ABSOLUTE Lipschitz support around each adopted mouth (see the
        # reach-time reconciliation for why a relative delta cone is
        # wrong: an at-cap ring re-emits over cap).
        sources = [(p, float(elev[idx]), float(elev[idx]) - float(alts[j]))
                   for (j, idx, p) in freed_verts]
        new_alts = list(alts)
        for (j, _idx, p) in [(j, i, p) for (j, i, p) in verts
                             if j < len(alts) and alts[j] is not None]:
            if j in held:
                continue
            val = float(alts[j])
            for (fp, tgt, dv) in sources:
                dd = _m.hypot(p[0] - fp[0], p[1] - fp[1])
                if dv > 0.0:
                    val = max(val, tgt - GROUNDSIDE_MAX_GRADE * dd)
                elif dv < 0.0:
                    val = min(val, tgt + GROUNDSIDE_MAX_GRADE * dd)
            new_alts[j] = val
        # exact adoption at the freed vertices themselves
        for (j, idx, _p) in freed_verts:
            new_alts[j] = float(elev[idx])
        # keep a closed ring closed (mirrors chord_limit's own handling)
        coords = list(g.polygon.exterior.coords)
        if (len(new_alts) == len(coords) and len(coords) > 1
                and tuple(coords[0]) == tuple(coords[-1])
                and new_alts[0] is not None):
            new_alts[-1] = new_alts[0]
        g.node_altitudes = new_alts
        n_adopted += 1
    return n_adopted


def apron_body_nodes(layout, bucket_to_idx):
    """Node indices that follow DEM (apron bodies + service roads/junctions) and
    are NOT part of the taxi route — closest-to-DEM target, no taxi-band bound.
    The rest of airside is the taxi route (smooth, band-bounded)."""
    cps = layout.canonical_points
    body: set = set()
    route: set = set()
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            continue
        if s.role in _DEM_BODY_ROLES:
            tgt = body
        elif s.role in _ROUTE_ROLES:
            tgt = route
        else:
            continue
        for (x, y) in _open_ring(list(s.polygon.exterior.coords)):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None:
                tgt.add(i)
    return body - route


# Solved-pavement roles a building pad may be embedded in / abut.  A pad's flat
# value adopts the HOST level from any of these; buildings and terrain-follow
# roles are excluded (a pad never adopts from another pad, and DEM-follow bodies
# are the pad's own frontage terrain, not a solved host surface).
_PAD_HOST_ROLES = frozenset({
    ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION,
    ROLE_PRIMARY_PARALLEL, ROLE_SECONDARY_PARALLEL,
    ROLE_STUB, ROLE_CROSS_CONNECTOR,
})


def _shape_vertex_alt(s, idx, n_open):
    """Solved altitude at ring-vertex ``idx`` of a pavement shape, or None.

    Reads whichever elevation representation the writeback left on the shape:
    per-vertex ``node_altitudes`` (apron/junction), a single flat ``altitude``,
    or a 4-corner ``altitude_high``/``altitude_low`` plane (mean is a sound
    local proxy for a pad-adjacency reference — rects rarely embed a pad)."""
    na = s.node_altitudes
    if na:
        na_open = na[:-1] if len(na) == n_open + 1 else na
        if 0 <= idx < len(na_open) and na_open[idx] is not None:
            return float(na_open[idx])
    if s.altitude is not None:
        return float(s.altitude)
    if s.altitude_high is not None and s.altitude_low is not None:
        return 0.5 * (float(s.altitude_high) + float(s.altitude_low))
    return None


def _building_flat_level(s):
    """Current flat level of a building pad (post-writeback), or None."""
    if s.altitude is not None:
        return float(s.altitude)
    na = s.node_altitudes
    if na:
        vals = [float(v) for v in na if v is not None]
        if vals:
            return sum(vals) / len(vals)
    return None


def relevel_pads_to_host_pavement(layout):
    """POST-SOLVE: re-level every building pad embedded in / abutting SOLVED
    pavement to the level the HOST pavement solved to at the contact.

    The frontage seat (``build_building_seats``) is a route-reachability
    envelope biased toward raw DEM.  When the host apron/junction around a pad
    solves ABOVE that envelope, a DEM-low seat leaves the flat pad in a pit and
    the host humps around it (CYXY apron #129 → building8, a -333 %/1.1 m step).

    For each pad, sample the host pavement's solved vertex altitudes within
    ``PAD_HOST_LEVEL_CONTACT_M`` of the pad ring and classify them BY VALUE: a
    node whose level agrees with the pad's current (pit) level is a shared-
    boundary lip (already carries the pad's own value — the contamination); a
    node that DIFFERS by more than ``PAD_HOST_LEVEL_TRIGGER_M`` is the genuine
    step partner = the HOST BODY.  When such a body exists, seat the pad FLAT at
    its median and lift the pit-value lip (within ``PAD_HOST_LEVEL_LIFT_M``) to
    the same level so pad and host weld at one flat level (no emit cliff).  The
    pad adopts FROM the host, never the reverse; the host BODY is untouched.

    ``config.PAD_HOST_PAVEMENT_LEVEL`` off → no-op (byte-identical; the env
    override died 2026-08-05).  Returns
    the count of pads re-levelled."""
    from auto_patch.config import (
        PAD_HOST_PAVEMENT_LEVEL, PAD_HOST_LEVEL_CONTACT_M,
        PAD_HOST_LEVEL_LIFT_M, PAD_HOST_LEVEL_TRIGGER_M,
    )
    if not PAD_HOST_PAVEMENT_LEVEL:
        return 0

    # Host pavement vertices with a solved altitude: (x, y, alt).
    host_verts: list = []
    for s in layout.shapes:
        if s.role not in _PAD_HOST_ROLES:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            ring = _open_ring(list(s.polygon.exterior.coords))
        except (ValueError, TypeError):
            continue
        n_open = len(ring)
        for idx, (x, y) in enumerate(ring):
            a = _shape_vertex_alt(s, idx, n_open)
            if a is not None:
                host_verts.append((float(x), float(y), a))
    if not host_verts:
        return 0

    r = float(PAD_HOST_LEVEL_CONTACT_M)
    r2 = r * r
    lift_r2 = float(PAD_HOST_LEVEL_LIFT_M) ** 2
    trigger = float(PAD_HOST_LEVEL_TRIGGER_M)

    # Host shapes indexed by role for the shared-boundary lift below.
    host_shapes = [s for s in layout.shapes
                   if s.role in _PAD_HOST_ROLES
                   and s.polygon is not None and not s.polygon.is_empty]

    n_relevelled = 0
    for s in layout.shapes:
        if s.role != ROLE_BUILDING:
            continue
        if s.polygon is None or s.polygon.is_empty:
            continue
        cur = _building_flat_level(s)
        if cur is None:
            continue
        try:
            ring = _open_ring(list(s.polygon.exterior.coords))
        except (ValueError, TypeError):
            continue
        if not ring:
            continue
        # Host pavement nodes within reach of the pad ring.  The pad ring and
        # the host share a boundary, and after the post-solve welds/decimation
        # a shared "lip" node may drift a few decimetres off the pad vertex —
        # so a GEOMETRIC coincidence test is unreliable here.  Classify by
        # VALUE instead: a host node whose level agrees with the pad's current
        # (possibly pit) level is a shared-boundary lip (the contamination); a
        # host node that DIFFERS by more than the trigger is the genuine step
        # partner = the HOST BODY the pad must adopt.
        body_vals: list = []
        for (px, py) in ring:
            for (hx, hy, ha) in host_verts:
                dx = hx - px
                dy = hy - py
                if dx * dx + dy * dy > r2:
                    continue
                if abs(ha - cur) > trigger:
                    body_vals.append(ha)
        if not body_vals:                     # agrees with host / not adjacent
            continue
        body_vals.sort()
        m = len(body_vals)
        med = (body_vals[m // 2] if m % 2
               else 0.5 * (body_vals[m // 2 - 1] + body_vals[m // 2]))
        new_level = round(float(med), 2)
        # (1) The pad seats FLAT at the host body level.
        s.altitude = new_level
        if s.node_altitudes:
            closed = (s.node_altitudes[0] == s.node_altitudes[-1]
                      and len(s.node_altitudes) > 1)
            s.node_altitudes = [new_level] * len(s.node_altitudes)
            if closed:
                s.node_altitudes[-1] = new_level
        s.altitude_high = None
        s.altitude_low = None
        n_relevelled += 1
        # (2) Un-contaminate the host's SHARED boundary lip: every host ring
        # vertex within reach of the pad ring that still carries the pad's old
        # pit value is a shared-boundary node dragged down by the old DEM seat.
        # Lift it to ``new_level`` (= the host body level) — otherwise the
        # emit's per-bucket merge sees the pad's new value and the host's stale
        # pit value disagree by > merge tol and mints a fresh cliff node at the
        # shared lat/lon (a vertical wall at the pad edge).  Lifting the lip to
        # the body level welds pad and host at one flat level — the step goes.
        for h in host_shapes:
            try:
                hcoords = list(h.polygon.exterior.coords)
            except (ValueError, TypeError):
                continue
            hring = hcoords[:-1] if (hcoords and hcoords[0] == hcoords[-1]) \
                else hcoords
            n_hopen = len(hring)
            hna = h.node_altitudes
            for hidx, (hx, hy) in enumerate(hring):
                hval = _shape_vertex_alt(h, hidx, n_hopen)
                if hval is None or abs(hval - cur) > trigger:
                    continue                  # not a pit-lip node → leave it
                near_pad = False
                for (px, py) in ring:
                    ddx = hx - px
                    ddy = hy - py
                    if ddx * ddx + ddy * ddy <= lift_r2:
                        near_pad = True
                        break
                if not near_pad:
                    continue
                if hna and len(hna) >= n_hopen:
                    hna[hidx] = new_level
                    if len(hna) == n_hopen + 1 and hidx == 0:
                        hna[-1] = new_level
                elif h.altitude is not None:
                    # Flat host shape: promote to per-vertex so the shared lip
                    # carries the body level without flattening the whole host.
                    base = [float(h.altitude)] * n_hopen
                    base[hidx] = new_level
                    h.node_altitudes = base + [base[0]]
                    hna = h.node_altitudes
                    h.altitude = None
    return n_relevelled
