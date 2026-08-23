"""The ONE-PROFILE solve (user spec 2026-06-24; docs/one_profile_solve.md).

The single source of elevation truth for the airside network, and it uses ONE
graph: the reach band on the unified grade graph
(``building_feasibility.reach_band_unified``).
That band sets the building levels AND bounds every apron / spine / rect node, so
they agree by construction — there is no second reachability graph.

Every free node gets ``[floor_i, ceil_i]`` from ``node_band`` (the reach band at
the node) and is pulled to a per-role target, clamped into ``[floor_i, ceil_i] ∩
the neighbour cap slabs`` by a projected Gauss-Seidel pass:

* APRON BODY → closest-to-DEM within the band (it rises to the building it fronts
  through the shared frontage edge, a neighbour cap slab — no building floor
  anchor needed).
* taxi SPINE + RECT ends → smoothest (min curvature); the spine clamps ONLY to
  its centerline-consecutive neighbours (a 1-D feasible chain) so the apron
  yields to it.  A rect tilts as a plane (flat across width via the ``cap=0``
  cross edges + the final couple); it climbs because its band ceiling near a
  high building/terminal is high.

Buildings, runway contacts and tile seams are fixed anchors (buildings flat at
their FRONTAGE-reachable level — see ``anchors.build_building_seats``).
"""
from __future__ import annotations

import math
import os as _os

# PROJECTION SELF-LIMITS — derivation beside the constants in config.py
# (debug lane A 2026-08-05).  The sweep budget is DERIVED per projection
# from its own graph (:func:`derive_sweep_budget`); these are the slack,
# the floor, the absolute ceiling and the no-graph fallback.
from auto_patch.config import (
    PROJECTION_MATERIALITY_M,
    SWEEP_BUDGET_MAX, SWEEP_BUDGET_MIN, SWEEP_BUDGET_SLACK,
    SWEEP_CONVERGENCE_MIN_DROP, SWEEP_CONVERGENCE_PATIENCE)

_INF = float("inf")

# ── THE CERTIFICATE'S CATCH-ALL TAGS — ONE AUTHORITY (cycle-7 fix 5) ────
# Entry tags that name a CONSTRUCTION SITE rather than a law: the unified
# grade graph enters the joint as ONE entry, and the solve's own joint
# never tagged its unified entry at all (so it degrades to ``"?:-"``).
# Both readers — this module's uncertified-exit family axis and
# ``solve.projection_law_certificate`` — resolve exactly these tags per
# edge through a ``family_by_pair`` map; the set is defined HERE because
# ``solve`` imports ``one_solve`` and not the reverse.
_CATCH_ALL_FAMILY_TAGS = frozenset(("unified_graph", "?:-"))

# The label for an over-cap pair the projection's own ``family_by_pair``
# does not carry AT ALL.  Named so the report's unresolved accounting and
# the row label read the same constant (they used to be two literals).
_UNMAPPED_FAMILY_TAG = "<unmapped>"


def _entry_family_tag(entry) -> str:
    """The family tag of one ``shape_constraints`` entry.

    The same rule ``solve.projection_law_certificate`` applies, in one
    place so the two readers can never drift: an explicit ``family``
    wins, otherwise the entry is named ``role:ref`` from its own keys.
    """
    tag = entry.get("family")
    if tag is None:
        tag = f"{entry.get('role') or '?'}:{entry.get('ref') or '-'}"
    return tag


# ── SLAB PRICING — THE ONE SITE (RULINGS 2026-08-06 "Slab budgets floor
# at the law"; docs/specs/cycle75-slab-floor-spec.md) ────────────────────
# A rod slab is a SIGNED difference constraint ``z_i − z_j ∈ [lo, hi]``
# minted from a snapshot Δ with tolerance ε.  Its pair usually ALSO
# carries the symmetric grade-law edge ``|z_i − z_j| ≤ budget``.  Two
# owner rulings bound the slab against that budget, one on each side:
#
#   FLOOR (2026-08-06, owner verbatim: "smoothing beyond law as a
#   constraint makes no sense, that's the point of the law.  Smoothest,
#   minimum grade is the target, but where needed, the budget is
#   certainly the law").  A slab may NEVER price tighter than the law on
#   its own pair — it narrows freedom down TO the law and no further.
#   The measurement that produced the ruling (c7cert fix 4, HECA dem1):
#   7,218 of 7,920 rod slabs bound tighter than their own pair's cap —
#   median 5.26x, p90 26.45x, max 2,305x, slab width p50 0.0233 m — and
#   that 2.6 % of the edge set owned 6,300 over-cap edges, 31.5 % of the
#   converged fp#8 residual.  Smoothness remains the solve's OBJECTIVE
#   (the strung profile is still the seed every projection starts from);
#   it stops being a hard constraint beyond law.
#
#   CLAMP (spec §10.1, 2026-07-29, CYXY service spine 6.2 %).  A slab may
#   never price LOOSER than the law either: a Δ snapshotted beyond the
#   pair's cap — the service corridor's post-``apply_service_road_dem_
#   follow`` re-shape — pinned an over-cap step through every later
#   projection (the worklist satisfies the slab and permanently violates
#   the law edge; 24,000 sweeps change nothing).
#
# Composed, on a pair that carries law, the slab is priced AT the law:
# ``[−budget, +budget]``.  That is written as the resulting interval
# rather than as a ``max``/``min`` sandwich around a raw window both
# bounds then discard — the algebra collapses, and spelling it out is
# how the two rulings stay legible at the one site that applies them.
# The RIDE-THE-CAP branch the clamp used to need (an empty intersection
# when |Δ| − ε exceeded the budget) is gone by construction: the floor
# guarantees the interval is the full law interval, never empty.
#
# A pair with NO symmetric law edge has no budget to floor at (33 of
# HECA's 7,920): it keeps the raw rod window.  There is nothing to
# contradict there, and widening to "unbounded" would DELETE the
# constraint rather than floor it — the ruling reprices slabs, it does
# not retire the channel.
#
# SCOPE is the rod channel, per the ruling's own words ("interval/slab
# (rod-channel) budgets"): the adjacent-ground zone slabs are the zone
# LAW itself, not a smoothing refinement riding on top of one, and
# flooring a law at its own budget is a no-op by definition.
def price_slab_against_law(delta: float, eps: float, law_budget):
    """Price one rod slab against its pair's grade-law budget.

    :param delta: the snapshot Δ = ``z_i − z_j`` the rod holds.
    :param eps: the rod tolerance (``config.SPINE_ROD_EPSILON_M``).
    :param law_budget: the pair's symmetric grade-law budget in metres,
        or ``None`` when the pair carries no symmetric law edge.
    :returns: ``(lo, hi, floored, clamped)`` — the priced slab plus the
        two report flags: ``floored`` when the raw window was TIGHTER
        than the law on either side (the ruling widened it), ``clamped``
        when it reached BEYOND the law on either side (§10.1 narrowed
        it).  Both can be true for one slab.
    """
    lo = delta - eps
    hi = delta + eps
    if law_budget is None:
        return lo, hi, False, False
    floored = (lo > -law_budget) or (hi < law_budget)
    clamped = (lo < -law_budget) or (hi > law_budget)
    return -law_budget, law_budget, floored, clamped


# ── FRAME STAMPS (RULINGS 2026-08-06 "Instrument truth is law", §3) ──────
# "Every reported number carries its frame (tree sha, node space, world,
# crown space).  Equating two numbers without matching stamps is the
# two-instruments trap by construction."
#
# THE STAMP THIS MODULE OWES.  Every node index printed from inside
# ``feasibility_project`` — the env-band conflict rows, the uncertified
# exit's carrier, the family table — is an index into ``elev`` AFTER every
# flat group has been collapsed onto ``min(group)``.  That is NOT the
# solve's original node space, and the difference is measured, not
# hypothetical: the c6attr dossier's two certificate readers ran on
# 142,635 / 144,056 nodes here against ``UnifiedGraph``'s 146,743, and the
# worst residual of the whole HECA solve (60.772738 m, carrier
# ``(962,5037)``) resolves in NEITHER authority (see
# :func:`_exit_residual_by_family`).  An index printed without this stamp
# cannot be joined to either reader, so the disagreement stays invisible.
_NODE_SPACE_FP_REMAPPED = "fp-remapped"


def _node_space_stamp(n, n_edges=None, label=_NODE_SPACE_FP_REMAPPED):
    """The node-space frame stamp for a report line.  Pure string.

    ``fp-remapped`` = ``feasibility_project``'s own index space: an index
    into ``elev`` with every flat-group member aliased onto its
    representative ``min(group)``.  ``n`` is that space's SIZE, which is
    the number a reader joins against.
    """
    tail = "" if n_edges is None else f", edges={n_edges}"
    return f"[node-space {label}: n={n}{tail}]"


# ── THE ENVELOPE GATES — ONE default per flag, DEFINED ONCE ──────────────
# (spec ``docs/specs/route-metric-envelope-spec.md`` §1: "Resolve the
# env-flag default drift while there: one default, defined once,
# documented; the historical '0'/'1' split dies.")
#
# The historical split was real and silent: ``solve.py`` read
# ``O4_ENVELOPE_FROM_BAND`` with default ``"0"`` at BOTH its call sites
# while ``feasibility_project`` read the SAME name with default ``"1"``,
# so the flag's meaning depended on which file asked.  ``blast.py``
# reports it as a conflicting-defaults hazard.  Both files now ask these
# functions, and the surviving default is production's ``"0"``: the band
# envelope is opt-in this round, so gate-off byte identity holds.
#
# ``O4_ROUTE_METRIC_ENVELOPE`` (this spec's gate, default "0") IMPLIES the
# band envelope — the route metric IS the band (spec §1: "the band engine
# is THE metric — no third engine") — and additionally turns on the
# non-route seed-admission clause (spec §2).
#
# DEFAULT FLIPPED TO "1" 2026-08-04 (spec ``docs/specs/kill-half-spec.md``
# §1; evidence: the route-metric-envelope round ``019d0bb``, and the owner
# ruling "band-shaped baseline accepted" (docs/RULINGS.md 2026-08-01) which
# adopts this envelope's two-sided tightening as the baseline surface
# character).  ``O4_ENVELOPE_FROM_BAND``'s own default stays "0" — the
# route-metric gate implies it, so there is still ONE default to flip.
# STANDING LAW 2026-08-05 (``O4_ROUTE_METRIC_ENVELOPE`` and
# ``O4_ENVELOPE_FROM_BAND`` both retired under RULINGS
# "BUILD-COMPLETE-THEN-DEBUG").  THE ROUTE-METRIC BAND IS THE LAW: the
# kill-half flip already made it the shipped default, and the losing arm —
# the pavement-PAIR closure envelope — is one of the three superseded
# second authorities the audit names (REMNANTS part B).  The defaults
# lived in named CONSTANTS, which made them invisible to the provenance
# stamp; both the constants and their env reads are gone.


def route_metric_envelope_enabled() -> bool:
    """The route-metric envelope IS the envelope.  Kept as a predicate
    only because several call sites read it as a condition; it has no
    other arm to select."""
    return True


def envelope_from_band_enabled() -> bool:
    """The feasibility envelope reads THE reach band — every pass,
    including the final.  Implied by the route metric, which is the law."""
    return True


# ── THE PROJECTION STALL REPORT (spec
# ``docs/specs/projection-stall-guard-spec.md``, as amended by the Fable
# ruling 2026-08-04 that CLOSED the early-termination family) ────────────
#
# Attributed mechanism (convergence round 2026-08-04): under the band
# envelope each CAPPED ``_project_chromatic`` call has its max residual
# pinned from ~sweep 2 by ONE genuinely inconsistent pair — the two-sided
# envelope gap ``L − U`` at that pair equals the stalled residual to 6
# decimals — while the solver still reduces tens of thousands of violating
# EDGES.
#
# TERMINATION IS RETIRED, NOT PENDING.  Two metrics were pre-registered
# and both were falsified for the SAME structural reason: progress
# ALTERNATES between the max residual and the active violating-edge count,
# and neither dominates.  Keying termination on the residual doubles the
# shipped violations (attempt 1); keying it on the active-edge count cuts
# CERTIFYING calls short — measured, three feasible chains that prove
# ``worst = 0.0`` when left alone are cut at sweep ~17 with 4-12 violating
# edges still live, and HEAZ CAND call 0 certifies at sweep 89 where the
# detector fired at 30 (attempt 2).  No third attempt: no scalar among the
# three traced metrics is a progress certificate for this POCS.
#
# What survives — and what this module now ships — is the FORENSICS half.
# The detector still runs, but it only WRITES: it names the carrier pair
# whose ``L − U`` gap pins the stall, which is a VALUE defect for the
# drain list.  That is also the performance fix: the sweeps those pairs
# burn disappear when their values are corrected at source, with no
# solver behaviour change and therefore no surface risk at all.
#
# ``O4_PROJECTION_STALL_REPORT`` (default "0") is IMPLIED ON by
# ``route_metric_envelope_enabled()`` — the same implication idiom
# ``O4_ENVELOPE_FROM_BAND`` uses above.  Gate-off arms never take a count
# or a carrier, so their byte identity holds by construction; gate-ON arms
# are byte-identical too, because nothing here can reach ``z``.
PROJECTION_STALL_REPORT_DEFAULT = "0"

# Fable-owned tuning constants (spec: "Constants named, Fable-owned (not
# owner constants)").  A new running minimum of the active violating-edge
# count RESETS the patience only when it improves the previous qualifying
# minimum by at least ``STALL_REL_IMPROVEMENT`` (relative); after
# ``STALL_PATIENCE_SWEEPS`` full passes with no qualifying minimum the
# call is DECLARED stalled and reported.  They no longer gate any
# behaviour — only when the write happens.
STALL_REL_IMPROVEMENT = 0.005
STALL_PATIENCE_SWEEPS = 16

# PERFORMANCE THRESHOLD, NOT A LAW NUMBER (perf 2026-08-13).  The sweep's
# active-row compression trades ~8 extra numpy dispatches for elementwise
# work it no longer does; below this row count the dispatches cost more
# than the work saved, so the colour keeps the full-width form.  Moving it
# changes WHICH of two bit-identical code paths runs, never a value.
COMPRESSION_MIN_ROWS = 128


def projection_stall_report_enabled() -> bool:
    """True when the chromatic sweep loop keeps the stall FORENSICS.

    THE one reader of ``O4_PROJECTION_STALL_REPORT``'s default (``"0"``);
    the route-metric gate implies it (that envelope is what amplifies the
    infeasible-site count ~4x and the gap ~8x, so it is the arm whose
    stalls are worth naming).

    An EXPLICIT value wins over the implication (ratified 2026-08-04).
    ``O4_ENVELOPE_FROM_BAND`` above cannot be forced off inside a
    route-metric arm, which is fine for a flag nobody A/Bs there — but
    this one has to be provable inert INSIDE the CAND arm, and that arm is
    exactly where the implication turns it on, so the override is part of
    the gate rather than a loosening of it."""
    explicit = _os.environ.get("O4_PROJECTION_STALL_REPORT")
    if explicit is not None:
        return explicit == "1"
    return (route_metric_envelope_enabled()
            or PROJECTION_STALL_REPORT_DEFAULT == "1")


# EXPERIMENTAL (user 2026-06-30): vectorise feasibility_project's Gauss-Seidel
# projection with numpy.  This converts it to a DEGREE-NORMALISED JACOBI sweep
# (all edges updated from the same snapshot each iteration, per-node corrections
# averaged for stability) — ~orders faster per iteration, but a DIFFERENT (still
# grade-compliant) feasible surface, so NOT byte-identical.  Default OFF; the
# scalar path stays the byte-identical default until this is validated (elevation
# delta small, residual violations equivalent-or-better) and re-baselined.

# ── EMIT-QUANTIZATION MARGIN — RETIRED (docs/RULINGS.md 2026-08-05) ──────
# ``raw_law_sweeps_enabled``, ``_emit_quantization_margin``,
# ``_margined_budget``, ``_margined_interval`` and
# ``config.EMIT_QUANTIZATION_MARGIN_M`` (with its ``O4_QUANT_MARGIN`` /
# ``O4_RAW_LAW_SWEEPS`` env reads) are ALL DELETED.
#
# STANDING LAW: the sweeps enforce the RAW law budgets and the RAW signed
# intervals.  There is no margin term anywhere in the projection, so there
# is no frame to keep straight: what the sweep enforces, what the reach
# envelope measures, what the break detector adjudicates and what the tally
# reports are ONE law frame by construction.
#
# WHY the margin went, not just its gate: ``to_osm`` rounds to the 0.01 m
# grid, so a pair solved exactly AT budget could read over the law in the
# emitted patch.  Shrinking every SWEEP budget by one grid step fixes that
# per PAIR and breaks it per PATH — the subtraction lands on EVERY edge, so
# an N-hop route loses ``N × margin`` of envelope no law ever took (HEAZ,
# measured: a 69-hop witness route stole 0.63 m and the projection burned
# 3983 sweeps chasing the deficit; the stall adjudication read "593 of 2032
# INFEASIBLE" against a system whose raw envelope is 0/2032).  The 0.01 m
# guarantee now lives at EMIT — :mod:`auto_patch.emit_snap`'s law-aware,
# per-pair grid snap, bounded by ONE grid step per node BY CONSTRUCTION and
# therefore incapable of compounding along a path.


def _hop_eccentricity_bound(iter_edges, n):
    """An upper bound on the law-edge graph's HOP DIAMETER.

    One BFS per connected component, from an arbitrary member (the first
    node the scan reaches).  A BFS from any node ``v`` gives that
    component's eccentricity ``e(v)``, and for any two nodes ``a``, ``b``
    in it ``d(a, b) <= d(a, v) + d(v, b) <= 2*e(v)`` — so ``2*e(v)``
    bounds the component's diameter without the all-pairs walk a true
    diameter needs.  The whole-graph bound is the max over components; a
    DISCONNECTED graph is then handled by construction rather than by
    luck (one arbitrary BFS would only have seen its own component, and
    this graph is routinely disconnected — quarantined pockets,
    interval-only zone leaves, per-shape islands).

    ``iter_edges`` — the projection's own edge list; only slots 0 and 1
    (the endpoints) are read, so BOTH the symmetric entries and the
    interval sentinel entries count, which is right: an interval edge
    propagates a correction exactly like a symmetric one.

    O(V + E), ONE pass, called ONCE per projection and never from inside
    the sweep loop.  Isolated nodes (no incident law edge) are skipped:
    they carry no correction and so cannot lengthen a propagation path.

    Returns ``0`` for an empty graph — :func:`derive_sweep_budget`'s
    floor is what turns that into a usable budget.
    """
    if n <= 0 or not iter_edges:
        return 0
    # Flat CSR-ish adjacency (head / next / dst) rather than a dict of
    # lists: one pass, no per-node allocation, plain integer indexing.
    head = [-1] * n
    nxt: list = []
    dst: list = []
    for edge in iter_edges:
        i = edge[0]
        j = edge[1]
        if i == j or not (0 <= i < n) or not (0 <= j < n):
            continue
        dst.append(j)
        nxt.append(head[i])
        head[i] = len(dst) - 1
        dst.append(i)
        nxt.append(head[j])
        head[j] = len(dst) - 1
    seen = bytearray(n)
    worst = 0
    for start in range(n):
        if seen[start] or head[start] < 0:
            continue
        seen[start] = 1
        frontier = [start]
        depth = 0
        while frontier:
            next_frontier: list = []
            for u in frontier:
                p = head[u]
                while p != -1:
                    v = dst[p]
                    if not seen[v]:
                        seen[v] = 1
                        next_frontier.append(v)
                    p = nxt[p]
            if next_frontier:
                depth += 1
            frontier = next_frontier
        if depth > worst:
            worst = depth
    return 2 * worst


def derive_sweep_budget(iter_edges, n, hyper_rows=None):
    """See below.  ``hyper_rows`` (spec §7) join the basis: a weighted
    transect couples FOUR nodes, so it is a hop between each of its near
    nodes and each of its far ones for propagation purposes.  Leaving
    them out would derive ``max_iters`` from a SMALLER graph than the one
    being solved — the anti-hang guard priced on the wrong diameter."""
    return _derive_sweep_budget(
        list(iter_edges) + [(int(r[0][0]), int(r[0][2]), 0.0)
                            for r in (hyper_rows or ())], n)


def _derive_sweep_budget(iter_edges, n):
    """``(block, hop_bound)`` — the POCS sweep BLOCK size FOR THIS GRAPH.

    CYCLE-7 FIX 1 CHANGED WHAT THIS NUMBER IS.  It used to be the exit:
    the loop swept it and stopped.  Measured (c6attr dossier), that was
    ~2 orders of magnitude short — a hop-diameter bound prices BALLISTIC
    propagation, one correction across one edge per sweep, while a cyclic
    Gauss-Seidel POCS propagates DIFFUSIVELY, so the distance a
    correction travels grows like the SQUARE ROOT of the sweeps and the
    honest bound is quadratic in the diameter.  No multiplier fixes a
    wrong exponent, so the exit moved to a CONVERGENCE CRITERION
    (``_project_chromatic``) and this figure became the BLOCK between two
    measurements of it: still graph-derived, still the propagation
    distance, but now the granularity at which "is it still improving?"
    is asked rather than the answer to "when do we stop?".  The
    ``SWEEP_BUDGET_MAX`` ceiling is the only hard cap left.

    The historical derivation, unchanged and still the reason the block
    is this size and not an arbitrary one:

    A SWEEP CAP IS A NON-TERMINATION GUARD, NOT A LAW QUANTITY.  The law
    demands a CERTIFIED surface and says nothing whatever about a number
    of sweeps, so the only honest magnitude is the propagation distance a
    correction has to travel — and the guard must sit provably ABOVE it,
    or the guard decides the surface.  It used to: at composed SPJC+HECA
    (n = 72,472) a hand-set 2,400 exited UNCERTIFIED at 2400/2400 with
    1,349 edges still over cap, ~30x below that graph's worst case.

        budget = clamp(SWEEP_BUDGET_SLACK * hop_eccentricity_bound,
                       SWEEP_BUDGET_MIN, SWEEP_BUDGET_MAX)

    The SLACK is there because one sweep of a CYCLIC projection does not
    move one correction cleanly across one hop — every node is pulled by
    all its incident edges at once, so a correction needs several passes
    per diameter to settle (``config.SWEEP_BUDGET_SLACK`` carries the
    reasoning).  The FLOOR keeps a tiny or edgeless graph sane; the
    CEILING is the actual anti-hang guard, for a graph pathological
    enough that no derivation should be trusted.

    Returning the bound alongside the budget is deliberate: an
    uncertified exit must be able to report WHICH graph measurement it
    was priced from, so the test phase can attribute the exit without
    re-deriving anything (see :func:`_uncertified_exit_report`).
    """
    hop_bound = _hop_eccentricity_bound(iter_edges, n)
    budget = int(SWEEP_BUDGET_SLACK * hop_bound)
    if budget < SWEEP_BUDGET_MIN:
        budget = SWEEP_BUDGET_MIN
    elif budget > SWEEP_BUDGET_MAX:
        budget = SWEEP_BUDGET_MAX
    return budget, hop_bound


def _build_adjacency(shape_constraints, n):
    """``adj[i] = [(j, budget), ...]`` where ``budget = cap·length`` (the max
    |Δelev| the edge may carry).  ``budget`` may be 0 (a rect flat-cross edge →
    the two corners stay equal).  Unregulated edges (``None``/negative) are
    skipped — they impose no cap and so do not bound the envelope.

    INTERVAL EDGES (Stage B0): a 4-tuple ``(i, j, interval_low, interval_high)``
    carries a SIGNED interval instead of a symmetric budget.  This adjacency
    feeds the neighbour-cap-slab heuristics in ``one_profile_solve`` /
    ``_project_triangle_planes`` / the final-projection edge fairing, all of
    which model an edge as a SYMMETRIC slab ``|z_i − z_j| ≤ budget`` and cannot
    represent an asymmetric or one-sided interval.  A conservative symmetric
    SURROGATE is used here: when both sides are finite, ``budget =
    max(|interval_low|, |interval_high|)`` (the loosest symmetric slab that
    still contains the interval — it never wrongly forbids a lawful level); a
    one-sided interval (either side ``None``) imposes no symmetric bound and is
    skipped, exactly like an unregulated edge.  The AUTHORITATIVE interval
    enforcement is the projection sweep in ``feasibility_project``, not this
    heuristic adjacency.  With every terrain gate off no interval edge is ever
    produced, so this branch is never taken and the adjacency is byte-identical
    to today."""
    adj: dict = {}
    for edge in shape_constraints_edges(shape_constraints):
        if len(edge) >= 4:
            i, j, interval_low, interval_high = (edge[0], edge[1],
                                                 edge[2], edge[3])
            if (interval_low is None or interval_high is None
                    or i >= n or j >= n or i == j):
                continue
            lim = max(abs(interval_low), abs(interval_high))
            if lim < 0:
                continue
            adj.setdefault(i, []).append((j, lim))
            adj.setdefault(j, []).append((i, lim))
            continue
        i, j, lim = edge
        if lim is None or lim < 0 or i >= n or j >= n or i == j:
            continue
        adj.setdefault(i, []).append((j, lim))
        adj.setdefault(j, []).append((i, lim))
    return adj


def shape_constraints_edges(shape_constraints):
    """Flatten every ``sc["edges"]`` list into one iterator.  A trivial helper
    that names the ``shape_constraints`` edge-tuple contract in one place:
    each edge is either a SYMMETRIC 3-tuple ``(i, j, budget)`` (``|z_i − z_j| ≤
    budget``; ``budget`` ``None``/negative = unregulated) or an INTERVAL
    4-tuple ``(i, j, interval_low, interval_high)`` (Stage B0)."""
    for sc in shape_constraints:
        for edge in sc["edges"]:
            yield edge


def shape_constraints_hyper(shape_constraints):
    """Flatten every ``sc["hyper"]`` list into one iterator — the WEIGHTED
    4-NODE transect rows (spec ``transverse-hyperplane-solve-spec.md``
    §3).  Each row is ``(idx4, w4, budget, station_id)``: ``|w . z| <= b``
    over four nodes, which is what a cross-section whose ends are
    INTERPOLATED along ring edges actually is.

    They live in their OWN key, never as a 5-tuple in ``edges``: every
    reader of the edge contract branches on ``len(edge) >= 4`` to detect
    an interval slab (:func:`shape_constraints_edges`, the certificate,
    ``_edge_adjacency``), so a longer tuple there would be read as a slab
    with a station id for a ceiling."""
    for sc in shape_constraints:
        for row in (sc.get("hyper") or ()):
            yield row


def law_edge_limits(shape_constraints, n, *, include_flat_pairs=False):
    """The joint law as canonical per-pair limits, in the UNREMAPPED node
    space: ``(edge_lim, interval_lim, envelope_skip_pairs)``.

    CONSTRUCTIVE-SOLVE round (K1): this is the SAME dedup contract
    :func:`feasibility_project` applies to its own entry stream — tightest
    symmetric budget wins per pair; a signed interval 4-tuple
    (``interval_low <= z_i − z_j <= interval_high``, ``None`` = open side)
    is pair-normalised to ``i < j`` (flipping negates and swaps the sides)
    and intersected tightest-per-side; an ``envelope_skip``-flagged entry
    keeps its interval pairs out of the reach-envelope adjacency (the
    negative-weight Dijkstra blowup class).  The authority for these
    semantics is the in-projection loop in ``feasibility_project`` (search
    "TIGHTEST budget wins") — kept there verbatim because it additionally
    interleaves the flat-group remap and the family axis, which the
    constructive caller has none of (no flat groups: pads are emission-time
    relative, owner 2026-08-14).  ``tests/test_constructive_solve.py``
    twin-asserts the two spellings agree on a shared fixture.

    ``include_flat_pairs``: fold every ``sc["flat_pairs"]`` rigid-level pair
    in as a ZERO-budget symmetric edge (the level-coupling law expressed in
    the envelope's own vocabulary — coupled nodes then share one interval
    and the midpoint selection keeps them co-levelled by construction).
    """
    edge_lim: dict = {}
    interval_lim: dict = {}
    envelope_skip_pairs: set = set()
    for sc in shape_constraints:
        _env_skip = bool(sc.get("envelope_skip"))
        for edge in sc["edges"]:
            if len(edge) >= 4:
                i, j, raw_low, raw_high = (edge[0], edge[1],
                                           edge[2], edge[3])
                if raw_low is None and raw_high is None:
                    continue
                if i >= n or j >= n or i == j:
                    continue
                if _env_skip:
                    envelope_skip_pairs.add((i, j) if i < j else (j, i))
                if i < j:
                    pair, low, high = (i, j), raw_low, raw_high
                else:
                    pair = (j, i)
                    low = None if raw_high is None else -raw_high
                    high = None if raw_low is None else -raw_low
                previous = interval_lim.get(pair)
                if previous is None:
                    interval_lim[pair] = (low, high)
                else:
                    prev_low, prev_high = previous
                    new_low = (low if prev_low is None
                               else low if (low is not None
                                            and low > prev_low)
                               else prev_low)
                    new_high = (high if prev_high is None
                                else high if (high is not None
                                              and high < prev_high)
                                else prev_high)
                    interval_lim[pair] = (new_low, new_high)
                continue
            i, j, lim = edge
            if lim is None or lim < 0 or i >= n or j >= n or i == j:
                continue
            e = (i, j) if i < j else (j, i)
            prev = edge_lim.get(e)
            if prev is None or lim < prev:
                edge_lim[e] = lim
        if include_flat_pairs:
            for (a, b) in sc.get("flat_pairs", ()):
                if a >= n or b >= n or a == b:
                    continue
                e = (a, b) if a < b else (b, a)
                edge_lim[e] = 0.0
    return edge_lim, interval_lim, envelope_skip_pairs


def envelope_radj(edge_lim, interval_lim, envelope_skip_pairs=frozenset(),
                  interval_yield_from=None):
    """Directed reach-envelope adjacencies ``(ceil_radj, floor_radj)`` from
    canonical pair limits (:func:`law_edge_limits`'s output shape).

    Same embedding as the in-projection build in
    :func:`feasibility_project` (search "DIRECTED reach-envelope
    adjacencies"), including its two standing safety clauses, both
    load-bearing:

    * ZONE-LEAF EXCLUSION — an interval pair crossing
      ``interval_yield_from`` is a host-authoritative terrain leaf and is
      excluded (the lazy-Dijkstra re-expand blowup class; the leaf is
      valued directly against its solved host instead);
    * ENVELOPE SIGN DISCIPLINE — only ``high >= 0`` / ``low <= 0``
      directions embed, so every ceiling weight is ≥ 0 and every floor
      weight ≤ 0 and the lazy-deletion Dijkstra stays bounded (the KCLT
      26-56 GB SIGKILL class, memory ``reach-envelope-sign-discipline``).

    Dropping a direction only LOOSENS the envelope — law enforcement of
    every skipped slab stays with its consumer, exactly as in the
    projection.
    """
    ceil_radj: dict = {}
    floor_radj: dict = {}
    for (i, j), lim in edge_lim.items():
        ceil_radj.setdefault(i, []).append((j, lim))
        ceil_radj.setdefault(j, []).append((i, lim))
        floor_radj.setdefault(i, []).append((j, -lim))
        floor_radj.setdefault(j, []).append((i, -lim))
    for (i, j), (low, high) in interval_lim.items():
        zone_slab = (interval_yield_from is not None
                     and ((i >= interval_yield_from)
                          != (j >= interval_yield_from)))
        if zone_slab or (i, j) in envelope_skip_pairs:
            continue
        if high is not None and high >= 0.0:
            ceil_radj.setdefault(j, []).append((i, high))
            floor_radj.setdefault(i, []).append((j, -high))
        if low is not None and low <= 0.0:
            ceil_radj.setdefault(i, []).append((j, -low))
            floor_radj.setdefault(j, []).append((i, low))
    return ceil_radj, floor_radj


def reach_envelope(sign, radj, seeds, values, n, horizon=None):
    """Multi-source cap-bounded envelope: ``best[k] = min over seeds a of
    (values[a] + capdist(a→k))`` for ``sign=+1`` (the ceiling), ``max of
    (values[a] − capdist)`` for ``sign=−1`` (the floor).  Returns
    ``(best, dist)`` — ``dist`` is the budget-metric distance of the
    optimal label.

    This is the module-level spelling of the projection's own
    ``_reach_plain`` (same lazy-deletion Dijkstra, same relaxation
    ``nt = t + w`` with the sign baked into the weights, same horizon
    truncation semantics), taking the value field as a parameter instead
    of a closure.  Both envelopes are cap-Lipschitz by construction, which
    is the constructive solve's C2 premise: ANY selection inside
    ``[floor, ceil]`` that is itself cap-Lipschitz — the interval midpoint
    of two Lipschitz envelopes is — satisfies every embedded pair.
    """
    import heapq
    best: dict = {}
    dist: dict = {}
    pq = [((values[a] if sign > 0 else -values[a]), 0.0, a)
          for a in seeds if a < n]
    heapq.heapify(pq)
    while pq:
        val, dk, k = heapq.heappop(pq)
        t = val if sign > 0 else -val
        if k in best and ((sign > 0 and t >= best[k])
                          or (sign < 0 and t <= best[k])):
            continue
        best[k] = t
        dist[k] = dk
        for (j, w) in radj.get(k, ()):
            ndk = dk + (w if w >= 0.0 else -w)
            if horizon is not None and ndk > horizon:
                continue
            nt = t + w
            pj = best.get(j)
            if pj is None or (sign > 0 and nt < pj) \
                    or (sign < 0 and nt > pj):
                heapq.heappush(pq, ((nt if sign > 0 else -nt), ndk, j))
    return best, dist


class LivingBand:
    """THE LIVING BAND (constructive-solve spec AMENDMENT 1, A2 + A4).

    The cap-Lipschitz band over the one published law graph, computed
    FIRST from the true anchors alone (A1: CIFP thresholds + tile-seam
    pins) and then REFINED incrementally as every later value is minted
    against it in priority order.  Two persistent lazy-deletion
    Dijkstras (:func:`reach_envelope`'s relaxation exactly — the seed
    batch is twin-asserted equal to it) hold

      ``ceil[k]  = min over anchors a of (v_a + capdist(a→k))``
      ``floor[k] = max over anchors a of (v_a − capdist(a→k))``

    and :meth:`add` pushes one new anchor's labels and relaxes to
    quiescence, so refinement costs only the labels that actually
    improve.  THE INDUCTION the amendment rests on: an accepted mint is
    inside the current band, and (triangle inequality in the budget
    metric) refining from an in-band value can never invert the band
    anywhere — every interval stays non-empty BY CONSTRUCTION.  A
    contradiction can therefore only enter through the seed batch
    itself, which is A1's data-defect class (CIFP vs seam), audited by
    the caller.

    A4 SOURCE TRACKING: every label carries the ANCHOR NODE that minted
    it (``ceil_src`` / ``floor_src``), and ``minter`` maps each anchor
    node to its minter id — so any refusal or residual finding names
    its two bounding anchors instead of an anonymous field.  Ships at
    module level in the shared band code; the iterative model's
    absorbed-contradiction attribution may consume it unchanged.

    ``add(..., seed=False)`` records an accepted anchor WITHOUT letting
    it propagate — the route-metric witness-admission law (non-route
    witnesses keep their value and their law edges but never seed the
    envelope).

    Determinism: heap entries are ``(key, dist, node, src)`` tuples of
    floats/ints; ties resolve by tuple order, so identical inputs give
    identical labels AND identical provenance.
    """

    def __init__(self, ceil_radj, floor_radj, n, *, track_paths=False):
        self.n = int(n)
        self._radj = {+1: ceil_radj, -1: floor_radj}
        self.ceil: dict = {}
        self.floor: dict = {}
        self.ceil_src: dict = {}
        self.floor_src: dict = {}
        #: anchor node -> value, in acceptance order (dicts preserve it).
        self.anchors: dict = {}
        #: anchor node -> minter id (A4's naming half).
        self.minter: dict = {}
        #: Optional label predecessors (``track_paths=True``): the node
        #: each accepted label was relaxed FROM (``None`` at an
        #: anchor's own label).  The debugging half of A4 — a finding
        #: can then print the WHOLE bounding path, not only its two
        #: endpoint anchors.  Off by default: production carries no
        #: extra tuple element.
        self.track_paths = bool(track_paths)
        self.ceil_pred: dict = {}
        self.floor_pred: dict = {}

    def _relax(self, sign, seeds):
        import heapq
        best = self.ceil if sign > 0 else self.floor
        src = self.ceil_src if sign > 0 else self.floor_src
        pred = self.ceil_pred if sign > 0 else self.floor_pred
        track = self.track_paths
        radj = self._radj[sign]
        pq = []
        for (v, k, s) in seeds:
            cur = best.get(k)
            if cur is None or (sign > 0 and v < cur) \
                    or (sign < 0 and v > cur):
                pq.append(((v if sign > 0 else -v), 0.0, k, s, None))
        heapq.heapify(pq)
        while pq:
            key, dk, k, s, par = heapq.heappop(pq)
            t = key if sign > 0 else -key
            cur = best.get(k)
            if cur is not None and ((sign > 0 and t >= cur)
                                    or (sign < 0 and t <= cur)):
                continue
            best[k] = t
            src[k] = s
            if track:
                pred[k] = par
            for (j, w) in radj.get(k, ()):
                nt = t + w
                pj = best.get(j)
                if pj is None or (sign > 0 and nt < pj) \
                        or (sign < 0 and nt > pj):
                    heapq.heappush(
                        pq, ((nt if sign > 0 else -nt),
                             dk + (w if w >= 0.0 else -w), j, s, k))

    def bounding_path(self, i, side):
        """``track_paths`` only: the label chain from node ``i`` back to
        the anchor that minted its ``side`` (``+1`` ceiling / ``-1``
        floor) bound — ``[i, ..., anchor]``."""
        pred = self.ceil_pred if side > 0 else self.floor_pred
        out = [i]
        seen = {i}
        k = pred.get(i)
        while k is not None and k not in seen:
            out.append(k)
            seen.add(k)
            k = pred.get(k)
        return out

    def seed(self, anchors, minters):
        """P0: one batched multi-source relaxation from the true
        anchors (``anchors``: node -> value; ``minters``: node -> id).
        Stable ascending-node order for determinism."""
        items = sorted(anchors.items())
        for i, v in items:
            self.anchors[i] = float(v)
            self.minter[i] = minters.get(i, "?")
        batch = [(float(v), i, i) for i, v in items if i < self.n]
        self._relax(+1, batch)
        self._relax(-1, batch)

    def add(self, i, value, minter_id, *, seed=True):
        """Record an ACCEPTED mint (the caller validated it against the
        current band) and — unless ``seed=False`` — locally refine the
        band from it before the next mint validates."""
        self.anchors[i] = float(value)
        self.minter[i] = minter_id
        if seed and i < self.n:
            batch = [(float(value), i, i)]
            self._relax(+1, batch)
            self._relax(-1, batch)

    def interval(self, i):
        """The current band ``(lo, hi)`` at node ``i`` (``None`` side =
        unbounded — off-graph from every anchor on that side)."""
        return self.floor.get(i), self.ceil.get(i)

    def bounding(self, i):
        """A4: the two bounding anchors at node ``i`` —
        ``(floor_anchor_node, floor_minter_id, ceil_anchor_node,
        ceil_minter_id)``; ``None`` where that side is unbounded."""
        fs = self.floor_src.get(i)
        cs = self.ceil_src.get(i)
        return (fs, self.minter.get(fs) if fs is not None else None,
                cs, self.minter.get(cs) if cs is not None else None)


def _box_isect(box_a, box_b):
    """Tightest-per-side intersection of two optional ``(lo, hi)`` boxes
    (``None`` = unbounded).  BOUNDED YIELD (owner ruling 2026-07-29): two
    flat groups merged into one rigid unit must satisfy BOTH feasibility
    boxes, so the merged box is the intersection."""
    if box_a is None:
        return box_b
    if box_b is None:
        return box_a
    return (max(box_a[0], box_b[0]), min(box_a[1], box_b[1]))


def _scatter_sub(z, index_column, weight_column, rows, se, win):
    """``z[idx] -= se * w`` over the ACTIVE rows only, honouring which row
    of a repeated index actually lands (see
    :func:`_column_last_write_mask`)."""
    delta = se * weight_column[rows]
    if win is None:
        z[index_column[rows]] -= delta
    else:
        lands = win[rows]
        z[index_column[rows[lands]]] -= delta[lands]


def _scatter_add(z, index_column, weight_column, rows, se, win):
    """The ``+=`` twin of :func:`_scatter_sub`."""
    delta = se * weight_column[rows]
    if win is None:
        z[index_column[rows]] += delta
    else:
        lands = win[rows]
        z[index_column[rows[lands]]] += delta[lands]


def _column_last_write_mask(np, index_column):
    """Which rows of a colour's endpoint column actually LAND?

    ``z[idx] += t`` is gather-add-scatter, so where ``idx`` repeats only
    the LAST row's value survives — the earlier ones are computed and then
    overwritten.  This returns the boolean mask of those surviving rows,
    or ``None`` when the column has no repeats at all (every row lands,
    the common case, and the sweep then skips the mask entirely).

    The sweep needs it to DROP inactive rows safely: a row inside
    tolerance contributes ``±0.0 * weight`` and so writes its endpoint
    back unchanged, but if it is the SURVIVOR of a repeated index,
    dropping it must not resurrect an earlier row's correction — which is
    exactly what restricting the scatter to surviving rows guarantees.
    Immovable endpoints carry weight 0 and are never separated by the
    write-conflict coloring, which is where the repeats come from.
    """
    order = np.argsort(index_column, kind="stable")
    grouped = index_column[order]
    last = np.empty(index_column.size, dtype=bool)
    last[-1] = True
    if index_column.size > 1:
        np.not_equal(grouped[:-1], grouped[1:], out=last[:-1])
        if last.all():
            return None
    mask = np.zeros(index_column.size, dtype=bool)
    mask[order[last]] = True
    return mask


def _node_box_arrays(node_box, np):
    """``(idx, lo, hi)`` numpy columns for a per-node feasibility-box dict
    (BOUNDED YIELD, owner ruling 2026-07-29).  Caller guarantees non-empty."""
    count = len(node_box)
    box_idx = np.fromiter(node_box.keys(), dtype=np.intp, count=count)
    box_lo = np.fromiter((b[0] for b in node_box.values()),
                         dtype=np.float64, count=count)
    box_hi = np.fromiter((b[1] for b in node_box.values()),
                         dtype=np.float64, count=count)
    return box_idx, box_lo, box_hi


# THE §7 REFERENCE PULL IS RETIRED (build-complete-then-debug round,
# docs/RULINGS.md 2026-08-05).  ``_node_ref_arrays`` / ``_ref_pull_weight``
# (``O4_YIELD_REF_WEIGHT``) and the whole reference-rod channel they fed —
# the proximal pull, the ``ref_prev`` equilibrium break and the
# exact-return polish — are DELETED here and at every call site.  The
# least-displacement metric is not a law: a projection now solves "any
# point the caps and the boxes admit", and a node that used to be held at
# a reference is plain free.  What SURVIVES is the forensics half: the
# stall report (below) still names the carrier of any exit that could not
# certify, and ``solve._spine_yield_movement_report`` still reports every
# yielded spine node's movement.


def _project_vectorized(elev, iter_edges, n, max_iters, tol,
                        interval_bounds_by_index=None, node_box=None):
    """Vectorised DEGREE-NORMALISED JACOBI variant of the feasibility projection
    (selected by the ``force_scalar`` argument — ``O4_FP_VECTORIZE`` was
    a DEAD gate, never read, deleted 2026-08-05).  Mutates ``elev`` (a
    list) in place.

    Every iteration updates ALL nodes from the same snapshot (Jacobi, not
    Gauss-Seidel), so it vectorises with numpy — but a node touched by many
    over-cap edges would OVERSHOOT if the corrections were summed, so each node's
    correction is AVERAGED over its active edges (``acc / cnt``).  A hard
    endpoint's weight (``wi``/``wj``) is 0 on every edge it touches, so hard nodes
    never move — same invariant as the scalar path.  Converges to a DIFFERENT
    (still ≤cap) feasible surface than Gauss-Seidel, hence not byte-identical.

    INTERVAL EDGES (Stage B0): entries with the ``None`` budget sentinel carry a
    signed slab ``[s_low, s_high]`` in ``interval_bounds_by_index`` (keyed by
    their position in ``iter_edges``).  They are partitioned out into a parallel
    numpy block whose SIGNED-excess corrections scatter into the SAME per-node
    ``acc``/``cnt`` accumulators in the same iteration, so symmetric and
    interval edges relax simultaneously under one degree-normalised step.  With
    no interval edges the symmetric arrays equal today's and the interval block
    is skipped — behaviour is unchanged (the Jacobi path is not byte-identical
    to the scalar path by design regardless)."""
    import numpy as np
    bounds = interval_bounds_by_index or {}
    sym_edges = []
    int_edges = []                    # (i, j, s_low, s_high, kind)
    for edge_index, e in enumerate(iter_edges):
        if e[2] is None:
            s_low, s_high = bounds.get(edge_index, (None, None))
            int_edges.append((e[0], e[1], s_low, s_high, e[3]))
        else:
            sym_edges.append(e)
    m = len(sym_edges)
    I = np.fromiter((e[0] for e in sym_edges), dtype=np.intp, count=m)
    J = np.fromiter((e[1] for e in sym_edges), dtype=np.intp, count=m)
    B = np.fromiter((e[2] for e in sym_edges), dtype=np.float64, count=m)
    K = np.fromiter((e[3] for e in sym_edges), dtype=np.int8, count=m)
    wi = np.where(K == 0, 0.5, np.where(K == 2, 1.0, 0.0))   # i's share of the fix
    wj = np.where(K == 0, 0.5, np.where(K == 1, 1.0, 0.0))   # j's share
    have_int = bool(int_edges)
    if have_int:
        mi = len(int_edges)
        _POS_INF = float("inf")
        _NEG_INF = float("-inf")
        Ii = np.fromiter((e[0] for e in int_edges), dtype=np.intp, count=mi)
        Ji = np.fromiter((e[1] for e in int_edges), dtype=np.intp, count=mi)
        # ``None`` floor → −inf (never violated below); ``None`` ceiling →
        # +inf (never violated above).
        Lo = np.fromiter(((_NEG_INF if e[2] is None else e[2])
                          for e in int_edges), dtype=np.float64, count=mi)
        Hi = np.fromiter(((_POS_INF if e[3] is None else e[3])
                          for e in int_edges), dtype=np.float64, count=mi)
        Ki = np.fromiter((e[4] for e in int_edges), dtype=np.int8, count=mi)
        wi_int = np.where(Ki == 0, 0.5, np.where(Ki == 2, 1.0, 0.0))
        wj_int = np.where(Ki == 0, 0.5, np.where(Ki == 1, 1.0, 0.0))
    z = np.asarray(elev, dtype=np.float64)
    # BOUNDED YIELD (owner ruling 2026-07-29): every node with a feasibility
    # box stays inside it — clamp at seed and after each Jacobi step, so the
    # exit state always honors the boxes.  ``node_box=None`` (every caller
    # without the yield bounds) is byte-identical: no arrays, no clamps.
    box_idx = box_lo = box_hi = None
    if node_box:
        box_idx, box_lo, box_hi = _node_box_arrays(node_box, np)
        z[box_idx] = np.minimum(np.maximum(z[box_idx], box_lo), box_hi)
    for _it in range(max_iters):
        if m:
            d = z[I] - z[J]
            over = np.abs(d) - B
            active = over > tol
            any_active = bool(active.any())
            # signed excess per ACTIVE edge (0 elsewhere) — scatter-add to
            # endpoints via bincount (true C scatter, far faster than
            # np.add.at).
            se = np.where(active, np.sign(d) * over, 0.0)
            acc = (np.bincount(I, weights=-se * wi, minlength=n)
                   + np.bincount(J, weights=se * wj, minlength=n))
            af = active.astype(np.float64)
            cnt = (np.bincount(I, weights=af, minlength=n)
                   + np.bincount(J, weights=af, minlength=n))
        else:
            # ALL-INTERVAL edge set (every edge carries the ``None`` budget
            # sentinel — EGWN's scoped projection): np.bincount's empty-input
            # fast path returns int64 even when float weights are passed, so
            # deriving ``acc``/``cnt`` from the empty symmetric arrays would
            # birth int64 accumulators and the interval block's ``+=`` below
            # raises a same-kind casting error.  Born float64 instead.
            any_active = False
            acc = np.zeros(n, dtype=np.float64)
            cnt = np.zeros(n, dtype=np.float64)
        if have_int:
            di = z[Ii] - z[Ji]
            above = di - Hi                       # >tol ⇒ over the ceiling
            below = Lo - di                       # >tol ⇒ under the floor
            active_hi = above > tol
            active_lo = below > tol
            active_int = active_hi | active_lo
            any_active = any_active or bool(active_int.any())
            # signed excess: +（di−Hi) when above, −（Lo−di）=di−Lo when below.
            se_int = np.where(active_hi, above,
                              np.where(active_lo, di - Lo, 0.0))
            acc += (np.bincount(Ii, weights=-se_int * wi_int, minlength=n)
                    + np.bincount(Ji, weights=se_int * wj_int, minlength=n))
            afi = active_int.astype(np.float64)
            cnt += (np.bincount(Ii, weights=afi, minlength=n)
                    + np.bincount(Ji, weights=afi, minlength=n))
        if not any_active:
            break
        nz = cnt > 0.0
        z[nz] += acc[nz] / cnt[nz]                          # degree-normalised step
        if box_idx is not None:
            # BOUNDED YIELD: re-clamp after the step (see seed clamp above).
            z[box_idx] = np.minimum(np.maximum(z[box_idx], box_lo), box_hi)
    elev[:] = z.tolist()


# ── Chromatic (graph-colored) Gauss-Seidel projection (Tier 3 wave 2c) ───────
# Routing-survey candidate 1 (docs/research/routing_optimization_survey.md).
# ``_CHROMATIC`` / ``_CHAIN_PREPASS`` are read lazily at call time (one_solve
# keeps config imports call-time, matching the module style) so the gate can be
# flipped per-process and the tests can toggle it without a reload.
def _chromatic_enabled():
    try:
        from auto_patch.config import CHROMATIC_PROJECTION
        return CHROMATIC_PROJECTION
    except Exception:
        return False


def _chain_prepass_enabled():
    try:
        from auto_patch.config import CHROMATIC_CHAIN_PREPASS
        return CHROMATIC_CHAIN_PREPASS
    except Exception:
        return False


def _extend_edge_coloring_by_write(iter_edges: list,
                                   coloring_state: dict) -> tuple:
    """Extend the greedy first-fit WRITE-conflict edge coloring held in
    ``coloring_state`` to cover every edge of ``iter_edges`` (perf 2026-07-18,
    partition-identical to the original per-edge ``forbidden`` union scan).

    ``coloring_state`` (mutated in place; pass ``{}`` to color from scratch)
    carries the coloring of a PREFIX of ``iter_edges``:

    * ``"edge_color"`` — per-edge color list (length = colored prefix);
    * ``"color_count"`` — number of colors used so far;
    * ``"used_colors_by_node"`` — node → set of colors of edges writing it;
    * ``"next_free_color_by_node"`` — node → smallest color index NOT in the
      node's used set (advanced lazily).

    Greedy first-fit is PREFIX-STABLE — an edge's color depends only on
    earlier edges in list order — so extending a carried prefix over appended
    edges (the lazy-expansion rounds, which only ever APPEND) yields exactly
    the coloring a from-scratch run over the full list would.

    HUB ACCELERATION (exact, not approximate): the first-fit color is
    ``c* = min{c ≥ 0 : c ∉ used[a] and c ∉ used[b]}`` over the edge's write
    nodes.  Every ``c < next_free[a]`` lies in ``used[a]`` (and likewise for
    ``b``), so ``c* ≥ max(next_free[a], next_free[b])``; scanning upward from
    that bound and testing membership in BOTH per-node sets directly reaches
    the same ``c*`` as the original scan-from-0 over the union — without
    materialising the O(write-degree) ``forbidden`` union copy per edge that
    made near-clique apron bodies quadratic (the 20.5 s OTHH leaf).  A
    single-write-node edge (``kind`` 1/2) takes ``next_free[w]`` outright —
    the zone→host hub still colors with a single color.

    Returns ``(edge_color, color_count)`` with ``edge_color`` the state's
    (now full-length) per-edge color list."""
    edge_color = coloring_state.setdefault("edge_color", [])
    used = coloring_state.setdefault("used_colors_by_node", {})
    next_free = coloring_state.setdefault("next_free_color_by_node", {})
    color_count = coloring_state.get("color_count", 0)
    colored_prefix = len(edge_color)
    if colored_prefix > len(iter_edges):
        # Defensive: the carried state outran the edge list (caller misuse) —
        # a stale prefix cannot be trusted, so recolor from scratch.
        edge_color.clear()
        used.clear()
        next_free.clear()
        color_count = 0
        colored_prefix = 0
    for edge_index in range(colored_prefix, len(iter_edges)):
        i, j, _budget, kind = iter_edges[edge_index]
        if kind == 0:
            used_i = used.get(i)
            used_j = used.get(j)
            if used_i is None:
                color = 0 if used_j is None else next_free[j]
            elif used_j is None:
                color = next_free[i]
            else:
                free_i = next_free[i]
                free_j = next_free[j]
                color = free_i if free_i > free_j else free_j
                while color in used_i or color in used_j:
                    color += 1
            write_nodes = (i, j)
        else:
            write_node = j if kind == 1 else i
            color = next_free.get(write_node, 0)
            write_nodes = (write_node,)
        edge_color.append(color)
        if color + 1 > color_count:
            color_count = color + 1
        for node in write_nodes:
            s = used.get(node)
            if s is None:
                used[node] = {color}
                next_free[node] = 1 if color == 0 else 0
            else:
                s.add(color)
                free = next_free[node]
                if color == free:
                    free += 1
                    while free in s:
                        free += 1
                    next_free[node] = free
    coloring_state["color_count"] = color_count
    return edge_color, color_count


def _color_edges_by_write(iter_edges):
    """Greedily partition ``iter_edges`` into color classes on the
    WRITE-conflict graph, deterministically.

    An edge WRITES the endpoint(s) the sweep moves — both for ``kind == 0``
    (split the excess), only ``j`` for ``kind == 1`` (``i`` fixed), only ``i``
    for ``kind == 2`` (``j`` fixed).  Two edges conflict iff they write a common
    node.  Within a color no two edges write the same node (a matching in the
    write-conflict graph), so their per-endpoint corrections land on DISJOINT
    entries and can be applied as one vectorized fancy-indexed update — a true
    Gauss-Seidel step, not the stalling degree-normalised Jacobi.

    Immovable endpoints are never written, so they impose no conflict: a hub of
    ``k`` one-directional (``kind`` 1/2) edges — the zone→host cluster — colors
    with a SINGLE color (all write distinct zone endpoints), the survey's
    high-degree-hub mitigation.

    Determinism: edges are processed in ``iter_edges`` order and each takes the
    smallest color not used by an already-colored write-neighbour; the result is
    invariant to intra-color order by construction (disjoint writes).  The
    greedy scan itself lives in :func:`_extend_edge_coloring_by_write` (exact
    hub-accelerated first-fit, perf 2026-07-18).  Returns a list (indexed by
    color) of edge-index lists."""
    edge_color, color_count = _extend_edge_coloring_by_write(iter_edges, {})
    colors: list = [[] for _ in range(color_count)]
    for edge_index in range(len(iter_edges)):
        colors[edge_color[edge_index]].append(edge_index)
    return colors


def _chain_envelope_clamp(elev, chain_nodes, chain_budgets, v_left, v_right):
    """Two-pass Lipschitz RUNNING clamp of ONE chain (survey candidate 2).

    ``chain_nodes`` are the free interior nodes ``c_1 … c_k`` in order;
    ``chain_budgets`` are the ``k + 1`` consecutive edge budgets
    ``b(L,c_1), b(c_1,c_2), …, b(c_k,R)``; ``v_left`` / ``v_right`` are the
    (held) boundary values.  A forward sweep clamps each node into
    ``[v_{i-1} − b, v_{i-1} + b]`` of its already-clamped LEFT neighbour, then a
    backward sweep clamps each into ``[v_{i+1} − b, v_{i+1} + b]`` of its
    already-clamped RIGHT neighbour (the running-clamp / repeated-median form).
    When the chain is feasible (``|v_left − v_right| ≤ Σb``) the two O(k) passes
    land a profile satisfying every consecutive edge with NO iteration — exactly
    the residual class POCS otherwise chains excess through node-by-node.  An
    infeasible chain (the boundaries contradict) is left near-feasible for the
    colored sweep / broken quarantine to own the genuine step.  Mutates
    ``elev`` in place; the boundaries themselves are never written."""
    k = len(chain_nodes)
    if k == 0:
        return
    # FORWARD: clamp against the running left neighbour (starts at v_left).
    prev = v_left
    for t in range(k):
        b = chain_budgets[t]                # budget (prev -> c_t)
        lo = prev - b
        hi = prev + b
        node = chain_nodes[t]
        v = elev[node]
        if v < lo:
            v = lo
        elif v > hi:
            v = hi
        elev[node] = v
        prev = v
    # BACKWARD: clamp against the running right neighbour (starts at v_right).
    prev = v_right
    for t in range(k - 1, -1, -1):
        b = chain_budgets[t + 1]            # budget (c_t -> next-right)
        lo = prev - b
        hi = prev + b
        node = chain_nodes[t]
        v = elev[node]
        if v < lo:
            v = lo
        elif v > hi:
            v = hi
        elev[node] = v
        prev = v


def _project_chain_prepass(elev, iter_edges, n, immovable):
    """Closed-form warm start (survey candidate 2): detect 1-D chain
    substructures in the regulated SYMMETRIC graph — maximal paths whose
    interior nodes are FREE with degree exactly 2 and which touch no interval
    edge — and solve each exactly with :func:`_chain_envelope_clamp`, bounded by
    the current values of its two endpoints.  Interval-touched nodes and free
    nodes of degree ≠ 2 (branch/leaf) bound a chain but are never moved here.

    A warm start only: the colored sweep runs afterward and re-checks every
    edge, so a chain that a later-considered chord would make cyclic can only
    cost sweeps, never correctness.  Returns the number of chains solved.

    Mutates ``elev`` in place; touches only free interior chain nodes."""
    m = len(iter_edges)
    # symmetric-only adjacency + interval-touched marks, tightest budget per pair
    adj: list = [None] * n
    interval_touched = bytearray(n)
    for edge_index in range(m):
        i, j, budget, _kind = iter_edges[edge_index]
        if budget is None:                              # interval edge
            interval_touched[i] = 1
            interval_touched[j] = 1
            continue
        li = adj[i]
        if li is None:
            adj[i] = {j: budget}
        else:
            prev = li.get(j)
            if prev is None or budget < prev:
                li[j] = budget
        lj = adj[j]
        if lj is None:
            adj[j] = {i: budget}
        else:
            prev = lj.get(i)
            if prev is None or budget < prev:
                lj[i] = budget

    def _is_interior(node):
        # a free, non-interval node with exactly two distinct regulated
        # symmetric neighbours (a genuine 1-D chain link).
        if node in immovable or interval_touched[node]:
            return False
        nb = adj[node]
        return nb is not None and len(nb) == 2

    visited = bytearray(n)
    n_chains = 0
    for start in range(n):
        if visited[start] or not _is_interior(start):
            continue
        # walk to one boundary, collecting the chain.  ``walk_seen`` guards
        # against a pure degree-2 RING (no boundary) — without it the walk of
        # an all-interior cycle would never terminate (``visited`` is only
        # stamped after assembly).
        nbrs = list(adj[start].keys())
        walk_seen = {start}
        # walk left from start via nbrs[0]
        left_nodes = []                     # interior nodes to the left (rev)
        prev = start
        cur = nbrs[0]
        while _is_interior(cur) and not visited[cur] and cur not in walk_seen:
            left_nodes.append(cur)
            walk_seen.add(cur)
            nxt = [x for x in adj[cur].keys() if x != prev]
            if len(nxt) != 1:
                break
            prev, cur = cur, nxt[0]
        left_boundary = cur                 # first non-interior (or visited)
        # walk right from start via nbrs[1]
        right_nodes = []
        prev = start
        cur = nbrs[1]
        while _is_interior(cur) and not visited[cur] and cur not in walk_seen:
            right_nodes.append(cur)
            walk_seen.add(cur)
            nxt = [x for x in adj[cur].keys() if x != prev]
            if len(nxt) != 1:
                break
            prev, cur = cur, nxt[0]
        right_boundary = cur
        # assemble ordered interior: left_boundary, rev(left_nodes), start,
        # right_nodes, right_boundary
        interior = list(reversed(left_nodes)) + [start] + right_nodes
        for node in interior:
            visited[node] = 1
        if (left_boundary == right_boundary
                or left_boundary in walk_seen or right_boundary in walk_seen):
            continue                        # degenerate ring — leave to the sweep
        # consecutive budgets along [left_boundary, interior..., right_boundary]
        seq = [left_boundary] + interior + [right_boundary]
        budgets = []
        ok = True
        for a, b in zip(seq[:-1], seq[1:]):
            na = adj[a]
            if na is None or b not in na:
                ok = False
                break
            budgets.append(na[b])
        if not ok or len(budgets) != len(interior) + 1:
            continue
        _chain_envelope_clamp(elev, interior, budgets,
                              elev[left_boundary], elev[right_boundary])
        n_chains += 1
    return n_chains


def _stall_envelope_gap(np, endpoint_i, endpoint_j, raw_budget_column,
                        interval_mask, weight_i, weight_j, z, n, pairs,
                        flat_group_reps=None):
    """``L − U`` at ``pairs`` on the CAP graph — the adjudication that says
    whether a stalled carrier pair is genuinely INFEASIBLE.

    RAW LAW FRAME.  ``raw_budget_column`` carries the RAW per-edge budgets.
    Since the emit-quantization margin was retired (2026-08-05, see the
    module-head note) the sweep budgets ARE the raw budgets, so the two
    coincide; the parameter keeps its name because this adjudication is a
    PATH quantity and must judge the law even if a per-edge frame is ever
    reintroduced.  A subtracted-per-edge term compounds along a path: a
    69-hop witness route through margined edges stole 0.69 m of envelope no
    law ever took, which is how HEAZ read "593 of 2032 INFEASIBLE, max gap
    0.7275" against a system whose RAW envelope is 0/2032 with gap
    0.000000 (measured, ``seed_attrib/`` arms).

    For the difference system ``|z_i − z_j| ≤ b_ij`` with the immovable
    endpoints pinned at their current values ``v_a``, feasibility is decided
    by the two-sided envelope ``U(i) = min_a (v_a + d(a,i))`` and
    ``L(i) = max_a (v_a − d(a,i))`` (``d`` = shortest path under the cap
    weights, all ≥ 0): the system is infeasible exactly where ``L > U``.
    Two multi-source Dijkstras via a virtual source with offset edges.
    Interval (slab) edges and node boxes are OMITTED — that only ever
    REMOVES constraints, so a positive verdict here is conservative and
    certain.

    THE ROUTE FOLLOWS THE REACH LAW (owner ruling 2026-08-06,
    "Certificate routes follow the reach law", verbatim: *"certificate
    routes follow the same law as reach — centerlines and lawful
    surfaces, never through pad interiors, no zero-budget hops"*).  The
    owner reviewed a KML of this function's own specimen route
    (HECA anchors 2864↔7478, 33.377 m priced over 149 edges) and
    adjudicated it INVALID: it crossed a 40-node pad group as a 586 m hop
    at budget 0, 24 of its 149 edges were priced under 0.9 % of their own
    chord, and 29 of its 150 nodes sat more than 100 m from any taxi
    centerline.  Two rules now bind the cap graph, and they are the
    reason the seam-pin "depth" verdict was (d) BROKEN INSTRUMENT rather
    than a law finding:

    * NO ZERO-BUDGET HOP.  An edge whose raw law budget is 0 is not a
      free traversal — it is a rigid coupling, and a route that walks it
      buys unlimited distance for nothing.  Dropped from the cap graph.
    * NEVER THROUGH A PAD INTERIOR.  ``flat_group_reps`` is the set of
      flat-group REPRESENTATIVES: under the group collapse a whole pad is
      ONE node, so a path that enters and leaves it crosses the pad's
      entire footprint at the cost of two short frontage chords.  A pad
      is a SEATED SURFACE, not a free edge (and reach follows centerlines
      — RULINGS 2026-07-30: buildings are ENDPOINTS on frontage chords).
      Each representative is therefore NODE-SPLIT: every edge INTO it
      lands on the receiving half, every edge OUT of it leaves the
      sending half, and the two halves are not joined — so the pad can
      still be reached and bounded by its own frontage chord, and can
      still anchor, but can never be transited.

    Both rules only ever REMOVE routes, so they only ever SHRINK the
    envelope's budget… which makes a positive ``L > U`` verdict MORE
    conservative, not less: the verdict stays conservative-and-certain.
    ``flat_group_reps=None`` restores the pre-ruling graph exactly.

    COST: two Dijkstras over the whole cap graph (HECA's largest system is
    272 k edges), which is why this runs only when the forensics channel is
    open — see ``_stall_guard_report``.  Returns ``None`` when it cannot
    adjudicate (no scipy, no pinned endpoint)."""
    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import dijkstra
    except Exception:                                      # pragma: no cover
        return None
    symmetric = ~interval_mask
    ei = endpoint_i[symmetric]
    ej = endpoint_j[symmetric]
    eb = raw_budget_column[symmetric]
    # RULE 1 — no zero-budget hop (owner 2026-08-06).  A rigid coupling
    # is not a road; walking it buys distance for free.
    _positive = eb > 0.0
    if not bool(_positive.all()):
        ei, ej, eb = ei[_positive], ej[_positive], eb[_positive]
    # IMMOVABLE = a node that NEVER carries positive weight on ANY incident
    # edge (interval edges included).  The earlier "zero weight on SOME
    # edge" reading was wrong and it mattered: a node is routinely the HELD
    # endpoint of one edge (kind 1/2, weight 0.0) and the MOVING endpoint of
    # another (kind 0, weight 0.5), so that set contained genuinely movable
    # nodes which the envelope then anchored at their post-solve ``z`` — an
    # anchor no law declared.  Measured on HEAZ call01: 3300 "pinned" of
    # which 666 had MOVED during the call (max 0.848 m); the strict set is
    # 1597, of which 0 moved.  The verdict is only conservative-and-certain
    # under the strict set: every extra anchor ADDS constraints and can mint
    # an INFEASIBLE class out of a feasible system (HEAZ call07 flipped).
    present = np.zeros(n, dtype=bool)
    present[endpoint_i] = True
    present[endpoint_j] = True
    movable = np.zeros(n, dtype=bool)
    movable[endpoint_i[weight_i > 0.0]] = True
    movable[endpoint_j[weight_j > 0.0]] = True
    pinned = present & ~movable
    anchors = np.flatnonzero(pinned)
    if not anchors.size or not ei.size:
        return None
    v = z[anchors]

    # RULE 2 — never through a pad interior (owner 2026-08-06).  Split
    # every flat-group representative into a RECEIVING half (its own
    # index, so its envelope value is still reported) and a SENDING half
    # (a shadow index past ``n``), with no edge between them.  Directed
    # arcs are rebuilt against the halves; the virtual source keeps
    # sending to the SENDING half of a pad anchor so a pinned pad can
    # still seed.
    reps = ({int(r) for r in flat_group_reps if 0 <= int(r) < n}
            if flat_group_reps else set())
    shadow = {}
    if reps:
        rep_arr = np.zeros(n, dtype=bool)
        rep_arr[sorted(reps)] = True
        shadow = {r: n + 1 + k for k, r in enumerate(sorted(reps))}
        shadow_of = np.arange(n + 1)
        shadow_of = np.concatenate([shadow_of,
                                    np.zeros(len(reps), dtype=shadow_of.dtype)])
        for r, sidx in shadow.items():
            shadow_of[r] = sidx
        # a -> b  becomes  send(a) -> recv(b)
        src_ij = shadow_of[ei]
        dst_ij = ej
        src_ji = shadow_of[ej]
        dst_ji = ei
        anchor_src = shadow_of[anchors]
    else:
        src_ij, dst_ij, src_ji, dst_ji = ei, ej, ej, ei
        anchor_src = anchors
    n_total = n + 1 + len(shadow)

    def _envelope(offsets):
        rows = np.concatenate([src_ij, src_ji,
                               np.full(len(anchors), n)])
        cols = np.concatenate([dst_ij, dst_ji, anchor_src])
        data = np.concatenate([eb, eb, offsets])
        graph = coo_matrix((data, (rows, cols)),
                           shape=(n_total, n_total)).tocsr()
        return dijkstra(graph, directed=True, indices=n)[:n]

    upper = v.min() + _envelope(v - v.min())
    lower = v.max() - _envelope(v.max() - v)
    gap = lower - upper
    finite = np.isfinite(gap)
    bad = finite & (gap > 1e-9)
    return {
        "gap": gap,
        "pinned": pinned,
        "infeasible": int(bad.sum()),
        "reachable": int(finite.sum()),
        "max_gap": float(gap[bad].max()) if bad.any() else 0.0,
        "pairs": [(int(a), int(b), float(gap[a]), float(gap[b]))
                  for (a, b) in pairs if 0 <= a < n and 0 <= b < n],
    }


def _carrier_line(tag, carrier):
    """One human line for a captured carrier tuple (or None)."""
    if not carrier:
        return f"    [stall-report]   {tag} carrier: none"
    kind, a, b, p0, p1, p2, p3 = carrier
    if kind == "sym":
        return (f"    [stall-report]   {tag} carrier symmetric pair "
                f"({a},{b}) budget={p0:.4f} dz={p1:+.4f} "
                f"residual={abs(p1) - p0:.6f} "
                f"mobility={'pinned' if p2 == 0.0 else 'free'}/"
                f"{'pinned' if p3 == 0.0 else 'free'}")
    if kind == "int":
        return (f"    [stall-report]   {tag} carrier interval pair "
                f"({a},{b}) slab=[{p0:.4f},{p1:.4f}] dz={p2:+.4f}")
    if kind == "box":
        return (f"    [stall-report]   {tag} carrier box node ({a}) "
                f"box=[{p0:.4f},{p1:.4f}] clamp move={p2:.6f}")
    return f"    [stall-report]   {tag} carrier: unknown kind {kind!r}"


def _lu_class(ga, gb):
    """The ``L − U`` class label for one carrier pair — ONE authority for
    both report sites, so the two can never drift.

    THE POSITIVE BRANCH IS A PROOF, AND ONLY THE POSITIVE BRANCH.
    ``L > U`` on RAW-LAW budgets is world-invariant: for the difference
    system ``|z_i − z_j| ≤ b_ij`` with pinned anchors, ``L > U`` at a node
    means no assignment satisfies it, whatever else is true.

    The negative branch used to print the word ``feasible``, which INVERTS
    the guarantee.  :func:`_stall_envelope_gap` OMITS interval (slab)
    edges and node boxes, and its own two route rules (no zero-budget hop,
    never through a pad interior) drop routes as well — every one of those
    omissions only ever REMOVES constraints, which is exactly what makes
    the POSITIVE verdict conservative-and-certain and leaves the negative
    one proving nothing at all.  ``L ≤ U`` here is the ABSENCE of a proof.
    The label now says that and nothing more.
    """
    if max(ga, gb) > 1e-9:
        return "INFEASIBLE (L>U proved)"
    return ("not-proved-infeasible (L<=U; slab edges + node boxes omitted "
            "from this envelope)")


def _stall_guard_report(np, sweeps, max_iters, detect_sweep, detect_active,
                        detect_worst, detect_carrier, active_count, worst,
                        carrier, endpoint_i, endpoint_j, raw_budget_column,
                        interval_mask, weight_i, weight_j, z, n,
                        flat_group_reps=None):
    """WRITE-ONLY forensics for one DECLARED-STALLED projection (spec
    ``projection-stall-guard``, report-only mode): the sweep the stall was
    detected on, the sweeps burned after it, the active violating-edge
    count then and at exit, and the CARRIER PAIR of the max residual with
    its ``L − U`` adjudication class.

    The carrier pairs are the drain-list value defects: a pair whose
    envelope gap equals the stalled residual is not the solver failing, it
    is two anchor VALUES (or a cap) that cannot both hold — standing
    principle ``feasibility-is-guaranteed``.  Correcting them at source is
    simultaneously the correctness fix and the performance fix, because
    the sweeps they burn are the ones this report is counting.

    NOTHING HERE CAN REACH ``z``: the call site runs after the writeback,
    every argument is read-only, and the function's only effects are
    ``print`` and the returned stats.  That is why the gate-ON arm is
    byte-identical to the gate-off one and not merely close to it.

    The ``L − U`` adjudication costs two whole-graph Dijkstras, so it runs
    only when the existing forensics channel is open
    (``O4_BREAK_FORENSICS`` set, or ``O4_STALL_GUARD_ADJUDICATE=1``); the
    pairs themselves are always named.

    ``raw_budget_column`` is the RAW law budget per edge (seed-fix round
    §1a) — the adjudication is a LAW measure and never reads the margined
    sweep budgets; see :func:`_stall_envelope_gap`.  The per-carrier
    ``budget=``/``residual=`` figures in the carrier lines stay in the
    SWEEP frame: they describe the sweep that stalled, not the law."""
    print(f"    [stall-report] "
          f"{_node_space_stamp(n, len(interval_mask))}: STALLED "
          f"at sweep {detect_sweep}/{max_iters}, ran to {sweeps} "
          f"({max(0, sweeps - detect_sweep)} sweep(s) burned after "
          f"detection); active violating edges {detect_active} -> "
          f"{active_count}; worst residual {detect_worst:.6f} -> "
          f"{worst:.6f}")
    print(_carrier_line("detect", detect_carrier))
    same = (detect_carrier is not None and carrier is not None
            and detect_carrier[:3] == carrier[:3])
    if not same:
        print(_carrier_line("exit  ", carrier))
    if not (_os.environ.get("O4_BREAK_FORENSICS")
            or _os.environ.get("O4_STALL_GUARD_ADJUDICATE") == "1"):
        return
    pairs = []
    for cand in (detect_carrier, carrier):
        if not cand or cand[0] not in ("sym", "int"):
            continue
        pair = (cand[1], cand[2])
        if pair[0] >= 0 and pair[1] >= 0 and pair not in pairs:
            pairs.append(pair)
    if not pairs:
        return
    try:
        verdict = _stall_envelope_gap(np, endpoint_i, endpoint_j,
                                      raw_budget_column, interval_mask,
                                      weight_i, weight_j, z, n, pairs,
                                      flat_group_reps=flat_group_reps)
    except Exception as exc:                               # pragma: no cover
        print(f"    [stall-report]   adjudication failed: {exc}")
        return
    if verdict is None:
        print("    [stall-report]   adjudication unavailable "
              "(no scipy / no pinned endpoint)")
        return
    print(f"    [stall-report]   envelope: INFEASIBLE nodes (L>U) "
          f"{verdict['infeasible']} of {verdict['reachable']} reachable, "
          f"max gap {verdict['max_gap']:.6f} m [RAW-LAW budgets]")
    for (pa, pb, ga, gb) in verdict["pairs"]:
        print(f"    [stall-report]   carrier ({pa},{pb}) L-U = "
              f"{ga:.6f} / {gb:.6f} -> {_lu_class(ga, gb)}"
              f"  (stalled residual {worst:.6f}) [RAW-LAW budgets] "
              f"{_node_space_stamp(n)}")


def _exit_residual_census(np, tol, endpoint_i, endpoint_j, budget_column,
                          slab_low_column, slab_high_column, interval_mask,
                          weight_i, weight_j, z):
    """``(active_edge_count, worst_residual, carrier)`` for the state ``z``
    the call is about to return.

    Recomputed from the flat edge columns rather than read off the sweep
    loop's own counters, so the numbers are the WHOLE system's exit
    residual and are available whether or not the stall-forensics gate
    happened to be on.  Read-only; the carrier tuple is the same shape
    ``_carrier_line`` already prints."""
    active = 0
    worst = 0.0
    carrier = None
    symmetric = ~interval_mask
    if symmetric.any():
        i = endpoint_i[symmetric]
        j = endpoint_j[symmetric]
        b = budget_column[symmetric]
        wi = weight_i[symmetric]
        wj = weight_j[symmetric]
        d = z[i] - z[j]
        over = np.abs(d) - b
        active += int((over > tol).sum())
        k = int(over.argmax())
        if float(over[k]) > worst:
            worst = float(over[k])
            carrier = ("sym", int(i[k]), int(j[k]), float(b[k]),
                       float(d[k]), float(wi[k]), float(wj[k]))
    if interval_mask.any():
        i = endpoint_i[interval_mask]
        j = endpoint_j[interval_mask]
        lo = slab_low_column[interval_mask]
        hi = slab_high_column[interval_mask]
        d = z[i] - z[j]
        excess = np.maximum(d - hi, lo - d)
        active += int((excess > tol).sum())
        k = int(excess.argmax())
        if float(excess[k]) > worst:
            worst = float(excess[k])
            carrier = ("int", int(i[k]), int(j[k]), float(lo[k]),
                       float(hi[k]), float(d[k]), 0.0)
    return active, worst, carrier


def _material_over_cap(np, tol, materiality, endpoint_i, endpoint_j,
                       budget_column, slab_low_column, slab_high_column,
                       interval_mask, z):
    """``(n_over, n_material, worst)`` — the EXACT whole-graph residual.

    The convergence criterion's meter (cycle-7 fix 1).  Distinct from the
    sweep loop's own ``stall_active``/``worst``, which are accumulated
    mid-Gauss-Seidel across colour classes and therefore describe a state
    no edge set is ever simultaneously in.  This one is taken at a BLOCK
    BOUNDARY, on the settled ``z``, over every edge in one frame — so two
    consecutive readings are comparable and their difference is a real
    improvement rather than a scheduling artefact.

    ``n_material`` is the count the criterion is priced on: edges at or
    above the campaign elevation floor.  Sub-materiality churn may never
    keep a projection sweeping (owner convergence guard (a), 2026-08-02).
    """
    d = z[endpoint_i] - z[endpoint_j]
    residual = np.where(interval_mask,
                        np.maximum(d - slab_high_column, slab_low_column - d),
                        np.abs(d) - budget_column)
    over_mask = residual > tol
    n_over = int(over_mask.sum())
    if not n_over:
        return 0, 0, 0.0
    n_material = int((residual >= materiality).sum())
    return n_over, n_material, float(residual.max())


def _exit_residual_by_family(np, tol, endpoint_i, endpoint_j, budget_column,
                             slab_low_column, slab_high_column, interval_mask,
                             z, family_by_pair,
                             materiality=PROJECTION_MATERIALITY_M):
    """``{family: (n_over, n_material, worst, n_interval)}`` at the state ``z``.

    THE PROJECTION'S OWN FAMILY AXIS (cycle-7 fix 5, verdict (d) BROKEN
    INSTRUMENT).  Until now the only family-attributed reader in the build
    was ``solve.projection_law_certificate``, which runs OUTSIDE the
    projection, on the ORIGINAL joint in the ORIGINAL node space.  Inside
    ``feasibility_project`` every flat group is collapsed onto a
    representative (``_r``), so the projection's own residual lives on
    REMAPPED pairs — and the c6attr dossier measured what that costs: the
    1,184 structural edges carrying the WORST residual of the whole solve
    (60.772738 m at HECA fp#8, carrier ``(962,5037)``) resolve in neither
    ``UnifiedGraph.family_by_pair`` nor any joint entry, because the
    physical chords that mint them are ``(pad-ring member, apron node)``
    pairs whose member end was aliased away.  An uncertified exit could
    therefore name ONE carrier and a count, and nothing about WHICH LAW
    was left violated.

    ``family_by_pair`` is the map built by ``feasibility_project`` in the
    REMAPPED space — every physical pair keyed by ``(_r(a), _r(b),
    is_interval)`` — so the lookup here is exact, never a proximity or a
    guess.  The KIND is part of the key because one remapped pair
    legitimately carries both a symmetric cap and a signed slab, minted
    by different constructors: without it the slab-class decomposition
    reports a zone slab as its neighbouring junction's law.  Pairs the map
    does not carry keep the honest ``"<unmapped>"`` label rather than
    being folded into a neighbour's bucket.

    ``materiality`` splits each family's count at the campaign elevation
    floor: an edge under it is PASS-with-residual by ruling, and the
    convergence criterion is priced on the ≥-material column only.

    Pure measurement — reads ``z``, writes nothing.
    """
    out: dict = {}
    d = z[endpoint_i] - z[endpoint_j]
    residual = np.where(interval_mask,
                        np.maximum(d - slab_high_column, slab_low_column - d),
                        np.abs(d) - budget_column)
    over = np.flatnonzero(residual > tol)
    if not over.size:
        return out
    ei = endpoint_i[over]
    ej = endpoint_j[over]
    rv = residual[over]
    iv = interval_mask[over]
    for k in range(over.size):
        a = int(ei[k])
        b = int(ej[k])
        key = ((a, b) if a <= b else (b, a)) + (bool(iv[k]),)
        fam = family_by_pair.get(key, _UNMAPPED_FAMILY_TAG)
        row = out.get(fam)
        if row is None:
            row = out[fam] = [0, 0, 0.0, 0]
        excess = float(rv[k])
        row[0] += 1
        if excess >= materiality:
            row[1] += 1
        if excess > row[2]:
            row[2] = excess
        if bool(iv[k]):
            row[3] += 1
    return {k: tuple(v) for k, v in out.items()}


def _report_exit_families(families, top=10, n=None, n_edges=None):
    """Print an :func:`_exit_residual_by_family` result, worst count first.

    ``n`` / ``n_edges`` are the FRAME (RULINGS 2026-08-06 §3): every index
    and every count in this table lives in the ``fp-remapped`` node space,
    and the size of that space is the number a reader joins against.

    THE UNRESOLVED SHARE IS ITS OWN NUMBER (standing-instrument sweep,
    2026-08-06).  Two disjoint things used to disappear into the table's
    rows: a pair the projection's ``family_by_pair`` does not carry at all
    (``_UNMAPPED_FAMILY_TAG``), and a pair whose entry named only a
    CONSTRUCTION SITE (``_CATCH_ALL_FAMILY_TAGS``) that the original-space
    ``family_of`` map did not resolve either — i.e. an edge no law-family
    authority names.  The owner's ruling cites "the certificate's 80.6 %
    catch-all" as one of the falsified premises, so that share is printed
    as a counted number every time the table prints, zero included.  This
    function reports the counts and the membership rule; it draws no
    conclusion from them.
    """
    if not families:
        return
    rows = sorted(families.items(), key=lambda kv: -kv[1][0])
    print(f"    [stall-report]   residual BY FAMILY "
          f"{_node_space_stamp(n, n_edges)} "
          f"({len(rows)} violating family(ies); "
          f"n_over / n≥{PROJECTION_MATERIALITY_M:g} m / worst / interval):")
    for fam, (n_over, n_mat, worst, n_int) in rows[:top]:
        print(f"    [stall-report]     {n_over:8d} {n_mat:8d} "
              f"{worst:11.6f} m {n_int:8d}  {fam}")
    if len(rows) > top:
        rest = sum(v[0] for _, v in rows[top:])
        print(f"    [stall-report]     ... {len(rows) - top} more "
              f"family(ies), {rest} edge(s)")
    total = sum(v[0] for v in families.values())
    n_unmapped = families.get(_UNMAPPED_FAMILY_TAG, (0,))[0]
    n_catch_all = sum(v[0] for k, v in families.items()
                      if k in _CATCH_ALL_FAMILY_TAGS)
    unresolved = n_unmapped + n_catch_all
    share = (100.0 * unresolved / total) if total else 0.0
    # The two tag SETS are named by their constants rather than spelled
    # out: a tag literal in this report's output must mean an actual
    # family ROW, or every negative assertion about a bucket label goes
    # non-specific.
    print(f"    [stall-report]     NAMED BY NEITHER AUTHORITY: "
          f"{unresolved} of {total} over-cap edge(s) ({share:.1f}%) = "
          f"{n_unmapped} absent from family_by_pair + {n_catch_all} left "
          f"on a construction-site tag (_CATCH_ALL_FAMILY_TAGS) that the "
          f"original-space family_of map did not resolve")


def _uncertified_exit_report(np, tol, sweeps, max_iters,
                             endpoint_i, endpoint_j, budget_column,
                             raw_budget_column, slab_low_column,
                             slab_high_column, interval_mask,
                             weight_i, weight_j, z, n,
                             sweep_budget_basis=None,
                             family_by_pair=None,
                             exit_reason="cap", block=None, hard_cap=None,
                             block_trace=None, last_block_drop=None,
                             flat_group_reps=None):
    """LOUD report for ANY sweep loop that exits WITHOUT a certificate.

    THE CONTRACT (build-complete-then-debug round): every exit of the
    chromatic POCS either CERTIFIES — a full sweep that applied no
    correction and no clamp, which proves every cap and every box
    satisfied — or SAYS SO OUT LOUD.  Silence used to be the failure
    mode: the reference-pull equilibrium break returned
    ``certified=False`` with an over-cap residual still live and most of
    the sweep budget abandoned, which downstream was indistinguishable
    from a clean exit (HECA shipped finals that quit at 38 sweeps of
    2400 with a 6.74 m residual).

    WHAT AN UNCERTIFIED EXIT MEANS NOW (cycle-7 fix 1).  It used to say,
    in every build, "this exit is NOT budget exhaustion" — and that
    sentence was FALSE.  The c6attr dossier drove this same function on
    the same fp#8 inputs at 100x and 400x the derived budget and closed a
    third of HECA's and over half of HEAZ's residual with sweeps alone;
    on a subsystem that is FEASIBLE BY CONSTRUCTION the derived budget
    left 11,513 edges over cap and 100x CERTIFIED it.  A hop-diameter
    bound prices BALLISTIC propagation while this POCS propagates
    DIFFUSIVELY, so the derivation was ~2 orders of magnitude short and
    the guard was choosing the surface — the exact failure it exists to
    prevent.

    The derived budget is now a BLOCK, and the loop exits on evidence.
    ``exit_reason`` says which of four events fired, and the report leads
    with it:

      * ``"material"`` — the block-boundary count of edges at or above
        ``config.PROJECTION_MATERIALITY_M`` reached 0.
      * ``"converged"`` — ``SWEEP_CONVERGENCE_PATIENCE`` consecutive
        blocks each bought less than ``max(1, SWEEP_CONVERGENCE_MIN_DROP
        × previous n_material)`` edges.
      * ``"cap"`` — ``sweeps`` reached ``hard_cap``
        (``config.SWEEP_BUDGET_MAX`` in production).
      * ``"certified"`` never reaches this report.

    WHAT THIS REPORT MAY SAY ABOUT THEM: the numbers, the predicate that
    fired, and the constants by name and value — nothing else (RULINGS
    2026-08-06 "Instrument truth is law" §2).  Two claims used to be
    printed here and BOTH are deleted as unlicensed:

      * on ``"converged"``, that the exit "is NOT budget exhaustion" and
        that "the polytope is EMPTY".  The premise is a STOPPING
        HEURISTIC on a diffusive relaxation; slow convergence and an
        empty intersection produce the IDENTICAL trace, and the c6attr
        sweep ladders measured exactly that (100x/400x budgets closed a
        third of HECA's and over half of HEAZ's residual on a system the
        line had already called empty).  This is the sentence the owner's
        own ruling preamble names as the falsified premise.
      * on ``"cap"``, that "THE GUARD DECIDED THIS SURFACE" and an
        instruction on how to read it.  ``sweeps >= hard_cap`` is the
        fact; it is printed, and the reader adjudicates.

    An infeasibility finding is still governed by docs/RULINGS.md
    2026-08-05 (BUG / INCOMPLETE LAW / INCORRECT LAW / BROKEN
    INSTRUMENT) — but that verdict belongs to the law layer reading these
    numbers, not to the print statement producing them.

    ``block_trace`` — one row per block ``(sweeps, n_over, n_material,
    worst, drop)``.  The last three rows are printed: they are the
    evidence for whichever criterion fired, and the reason no reader has
    to re-run the projection to see the shape of its tail.

    ``sweep_budget_basis`` — the ``hop_bound`` half of
    :func:`derive_sweep_budget`, or ``None`` when the caller supplied an
    explicit ``max_iters`` (a test or a deliberately bounded probe); the
    line then says the block was IMPOSED rather than derived, which is
    itself the attribution.

    REPORT-ONLY, by construction: the call site is AFTER the writeback,
    every argument is read-only, and the only effects are ``print`` and
    the returned dict.  The surface is identical with and without it.

    The named carrier is a drain-list VALUE defect, exactly as in
    ``_stall_guard_report``: under the standing ``feasibility-is-
    guaranteed`` principle a live residual means two anchor values (or a
    cap) that cannot both hold — never a legitimate answer.

    ONE BUDGET FRAME.  ``budget_column`` and ``raw_budget_column`` both
    carry the RAW law budget now that the emit-quantization margin is
    retired (module head).  The split parameter survives because the
    ``L − U`` verdict is a LAW measure and a PATH quantity — it must
    never be priced on a per-edge-shrunk frame, which is how HEAZ read
    "593 of 2032 INFEASIBLE" against a system whose raw envelope is
    0/2032 — so the adjudication keeps taking the column that is
    guaranteed raw."""
    active, worst, carrier = _exit_residual_census(
        np, tol, endpoint_i, endpoint_j, budget_column, slab_low_column,
        slab_high_column, interval_mask, weight_i, weight_j, z)
    if sweep_budget_basis is None:
        basis = f"block {block} IMPOSED by the caller (not derived)"
    else:
        basis = (f"block {block} DERIVED = slack {SWEEP_BUDGET_SLACK}"
                 f" x hop-diameter bound {sweep_budget_basis}")
    n_material = 0
    if block_trace:
        n_material = block_trace[-1][2]
    else:
        _, n_material, _ = _material_over_cap(
            np, tol, PROJECTION_MATERIALITY_M, endpoint_i, endpoint_j,
            budget_column, slab_low_column, slab_high_column,
            interval_mask, z)
    imposed = sweep_budget_basis is None
    # The class name stays GREPPABLE — every exit here is still an exit
    # without a KKT certificate — and the criterion is named in it, so a
    # log reader never has to infer which of the four fired.
    headline = {
        "material": "MATERIALLY CERTIFIED EXIT",
        "converged": "UNCERTIFIED EXIT [converged]",
    }.get(exit_reason,
          "UNCERTIFIED EXIT [imposed budget]" if imposed
          else "UNCERTIFIED EXIT [hard cap]")
    print(f"    [stall-report] {_node_space_stamp(n, len(interval_mask))}: "
          f"{headline} at sweep {sweeps}/{hard_cap} "
          f"({max(0, hard_cap - sweeps)} sweep(s) abandoned; "
          f"{len(block_trace or ())} block(s) of {block}); "
          f"active violating edges {active} "
          f"({n_material} >= {PROJECTION_MATERIALITY_M:g} m); "
          f"worst residual {worst:.6f}")
    drop_txt = ("n/a (first block)" if last_block_drop is None
                else f"{last_block_drop:+d} edge(s) >= "
                     f"{PROJECTION_MATERIALITY_M:g} m")
    # ── THE CRITERION PARAGRAPH IS NUMBERS AND CONSTANTS ─────────────────
    # (standing-instrument sweep 2026-08-06, RULINGS "Instrument truth is
    # law" §2: an instrument reports NUMBERS AND FRAMES; a verdict sentence
    # may be printed only by the law layer or from a WORLD-INVARIANT
    # computation.)  Each branch prints the PREDICATE THAT FIRED with its
    # constants by name and value, and the measured trajectory — so a
    # reader applies the criterion themselves rather than being handed a
    # conclusion this code cannot check.
    if exit_reason == "material":
        # The floor itself is a named owner ruling (convergence guard (a),
        # 2026-08-02, ``config.PROJECTION_MATERIALITY_M``); the ADJUDICATION
        # of a sub-floor residual belongs to the law layer, so the report
        # states the count and cites where the constant comes from.
        print(f"    [stall-report]   {basis}; criterion=materiality: "
              f"n_material=0 (materiality {PROJECTION_MATERIALITY_M:g} m = "
              f"config.PROJECTION_MATERIALITY_M, owner convergence guard "
              f"(a) 2026-08-02); n_over={active}; "
              f"worst residual {worst:.6f} m; last block drop {drop_txt}")
    elif exit_reason == "converged":
        # THE MEASURED STOPPING RULE, VERBATIM (one_solve, block boundary):
        #     flat_blocks += 1 when last_block_drop <
        #         max(1, int(SWEEP_CONVERGENCE_MIN_DROP * prev_material))
        #     exit when flat_blocks >= SWEEP_CONVERGENCE_PATIENCE
        # Nothing about the feasible set follows from it: slow diffusive
        # POCS convergence and an empty intersection produce the identical
        # trace (measured — c6attr, 100x/400x sweep ladders).  The old
        # sentence asserted "NOT budget exhaustion … the polytope is EMPTY"
        # from this premise; it is DELETED, and the trajectory that would
        # have to be read to reach any such verdict is printed instead.
        _tr = list(block_trace or ())
        _traj = " -> ".join(str(_row[2]) for _row in
                            _tr[-(SWEEP_CONVERGENCE_PATIENCE + 2):]) or "n/a"
        _prev_material = _tr[-2][2] if len(_tr) >= 2 else None
        _floor_txt = ("n/a" if _prev_material is None else
                      str(max(1, int(SWEEP_CONVERGENCE_MIN_DROP
                                     * _prev_material))))
        print(f"    [stall-report]   {basis}; criterion=convergence: "
              f"flat_blocks >= SWEEP_CONVERGENCE_PATIENCE="
              f"{SWEEP_CONVERGENCE_PATIENCE}, a block counting as flat when "
              f"its drop < max(1, SWEEP_CONVERGENCE_MIN_DROP="
              f"{SWEEP_CONVERGENCE_MIN_DROP:.1%} x previous n_material) = "
              f"{_floor_txt} edge(s); n_material trajectory over the last "
              f"{len(_tr[-(SWEEP_CONVERGENCE_PATIENCE + 2):])} block(s) "
              f"{_traj}; last block drop {drop_txt}; at exit n_material="
              f"{n_material}, n_over={active}, worst residual {worst:.6f} m")
    elif imposed:
        print(f"    [stall-report]   {basis}; criterion=imposed-budget: "
              f"sweeps {sweeps} reached the caller's bound {hard_cap} "
              f"(sweep_budget_basis=None); last block drop {drop_txt}; at "
              f"exit n_material={n_material}, n_over={active}, worst "
              f"residual {worst:.6f} m. This exit reports no property of "
              f"the feasible set.")
    else:
        print(f"    [stall-report]   {basis}; criterion=cap: sweeps "
              f"{sweeps} reached hard_cap {hard_cap} "
              f"(config.SWEEP_BUDGET_MAX in production) with "
              f"last_block_drop {drop_txt}; at exit n_material="
              f"{n_material}, n_over={active}, worst residual "
              f"{worst:.6f} m")
    # The last three blocks are the EVIDENCE for whichever criterion
    # fired.  Under the existing step-debug channel the WHOLE trajectory
    # prints — that is the convergence curve, and it is the difference
    # between auditing this exit and re-running the projection to see it.
    _rows = list(block_trace or ())
    if _os.environ.get("O4_STEP_DEBUG") != "1":
        _rows = _rows[-3:]
    for _row in _rows:
        _bs, _bo, _bm, _bw, _bd = _row
        print(f"    [stall-report]     block @sweep {_bs:7d}: over {_bo:8d} "
              f"| >= {PROJECTION_MATERIALITY_M:g} m {_bm:8d} "
              f"| worst {_bw:11.6f} m | drop "
              f"{'n/a' if _bd is None else f'{_bd:+d}'}")
    print(_carrier_line("exit  ", carrier))
    # THE FAMILY AXIS (cycle-7 fix 5): WHICH LAW the projection could not
    # close, in the projection's own remapped node space.  Absent map ⇒
    # the report reads exactly as it did before.
    families = None
    if family_by_pair:
        families = _exit_residual_by_family(
            np, tol, endpoint_i, endpoint_j, budget_column,
            slab_low_column, slab_high_column, interval_mask, z,
            family_by_pair)
        _report_exit_families(families, n=n, n_edges=len(interval_mask))
    verdict = None
    if (worst > tol and carrier is not None
            and carrier[0] in ("sym", "int")
            and (_os.environ.get("O4_BREAK_FORENSICS")
                 or _os.environ.get("O4_STALL_GUARD_ADJUDICATE") == "1")):
        pair = (carrier[1], carrier[2])
        try:
            verdict = _stall_envelope_gap(np, endpoint_i, endpoint_j,
                                          raw_budget_column, interval_mask,
                                          weight_i, weight_j, z, n, [pair],
                                          flat_group_reps=flat_group_reps)
        except Exception as exc:                           # pragma: no cover
            print(f"    [stall-report]   adjudication failed: {exc}")
            verdict = None
        if verdict is None:
            print("    [stall-report]   adjudication unavailable "
                  "(no scipy / no pinned endpoint)")
        else:
            print(f"    [stall-report]   envelope: INFEASIBLE nodes (L>U) "
                  f"{verdict['infeasible']} of {verdict['reachable']} "
                  f"reachable, max gap {verdict['max_gap']:.6f} m "
                  f"[RAW-LAW budgets]")
            for (pa, pb, ga, gb) in verdict["pairs"]:
                print(f"    [stall-report]   carrier ({pa},{pb}) L-U = "
                      f"{ga:.6f} / {gb:.6f} -> {_lu_class(ga, gb)}"
                      f"  (exit residual {worst:.6f}) [RAW-LAW budgets] "
                      f"{_node_space_stamp(n)}")
    return {"sweep": sweeps, "max_iters": max_iters,
            "exit_reason": exit_reason, "block": block, "hard_cap": hard_cap,
            "block_trace": block_trace, "n_material": n_material,
            "sweeps_abandoned": max(0, (hard_cap or max_iters) - sweeps),
            "active_edges": active, "worst": worst, "carrier": carrier,
            # SELF-LIMIT ACCOUNTING (debug lane A 2026-08-05): an exit on
            # the sweep cap means the NON-TERMINATION GUARD, not
            # convergence, decided this surface.  Flagged in the record so
            # the debug phase can count it instead of grepping logs.
            # ``sweep_budget_basis`` is the hop-diameter bound the budget
            # was derived from (``None`` = the caller imposed a budget),
            # so an exit can be attributed without re-deriving anything.
            "cap_bound": bool(sweeps >= (hard_cap or max_iters)),
            "sweep_budget_basis": sweep_budget_basis,
            # ``None`` when the caller supplied no family map — absent and
            # empty are DIFFERENT findings (no instrument vs nothing to
            # attribute) and the record keeps them apart.
            "families": families}


def _project_chromatic(elev, iter_edges, n, max_iters, tol,
                       interval_bounds_by_index=None, *, stats=None,
                       coloring_state=None, run_feasibility_precheck=True,
                       node_box=None,
                       raw_budget_by_index=None,
                       sweep_budget_basis=None,
                       family_by_pair=None,
                       sweep_hard_cap=None,
                       flat_group_reps=None,
                       hyper_rows=None, hard_nodes=None):
    """Colored Gauss-Seidel POCS (survey candidate 1) — the vectorized
    replacement for BOTH legacy inner sweeps.  Mutates ``elev`` in place.

    Precomputes one deterministic write-conflict coloring
    (:func:`_extend_edge_coloring_by_write`); each sweep relaxes the color
    classes in order, every class as a single vectorized fancy-indexed update
    whose writes are disjoint (a valid independent projection batch) and which
    reads the LATEST values from earlier classes — a true Gauss-Seidel step at
    numpy speed, converging where the degree-normalised Jacobi stalls.

    KKT / dual feasibility certificate (survey candidate 4): a full sweep that
    applies NO correction proves every constraint satisfied, so iteration stops
    on proof rather than the ``max_iters`` cap; the avoided sweeps are recorded
    in ``stats``.  ``stats`` (optional dict) receives ``colors``, ``edges``,
    ``sweeps``, ``sweeps_avoided``, ``certified`` and ``worst``.

    FEASIBILITY PRE-CHECK (perf 2026-07-18, byte-identical): one vectorized
    residual pass over the flat edge columns BEFORE the coloring.  Sweep 1
    applies zero corrections iff every edge is already within tolerance at
    entry (the first color class only moves when active, so an all-satisfied
    system passes through every class untouched) — so when no edge violates,
    this returns the exact certified-on-sweep-1 result (``(1, True)``, the
    same counters and writeback) without paying the coloring or the per-color
    array build at all.  The repeated re-projection call sites are usually
    already feasible, which is where the saving lands.  ``stats["colors"]`` is
    unknowable without coloring and reported as ``None`` on this path (it is
    only ever read by the ``O4_STEP_DEBUG`` print, under which the coloring IS
    computed so the line stays faithful).  ``run_feasibility_precheck=False``
    forces the full path (test hook; both paths are value-identical).

    ``coloring_state`` (optional dict, mutated) carries the incremental
    coloring across lazy-expansion rounds — see
    :func:`_extend_edge_coloring_by_write`; rounds only APPEND edges and the
    greedy coloring is prefix-stable, so extending is exact.

    Interval edges (``budget is None``) carry a signed slab
    ``[s_low, s_high]`` in ``interval_bounds_by_index`` (keyed by ``iter_edges``
    position); they relax in the same color classes as the symmetric edges.

    CERTIFY OR SAY SO: the loop exits either on the KKT certificate above
    or on the ``max_iters`` cap, and the cap exit is reported LOUDLY by
    :func:`_uncertified_exit_report` (write-only, after the writeback).
    There is no third, silent exit — the §7 reference pull and its
    equilibrium break, which used to supply one, are retired.

    ``max_iters`` is a NON-TERMINATION GUARD and callers derive it from
    the graph (:func:`derive_sweep_budget`); ``sweep_budget_basis`` is
    that derivation's hop-diameter bound, passed through UNREAD to the
    exit report so an uncertified exit can name what it was priced from.
    ``None`` = the caller imposed the budget.

    ``raw_budget_by_index`` — INSTRUMENT-ONLY (seed-fix round §1a): a list
    parallel to ``iter_edges`` carrying each edge's RAW law budget where
    it differs from the swept one, ``None`` elsewhere.  NOTHING in the
    projection reads it — it is handed to the write-only stall report so
    the ``L − U`` adjudication judges the LAW.  Since the emit-
    quantization margin was retired the two frames coincide, so in
    production this changes nothing; the seam stays because that
    adjudication is a PATH quantity and must never silently inherit a
    per-edge-shrunk frame.  ``None`` ⇒ the adjudication sees the sweep
    budgets exactly as before."""
    import numpy as np
    bounds = interval_bounds_by_index or {}
    _NEG_INF = float("-inf")
    _POS_INF = float("inf")
    edge_count = len(iter_edges)
    # ONE flat pass over ``iter_edges`` (perf 2026-07-18, byte-identical):
    # the endpoint / weight / budget / slab columns feed BOTH the feasibility
    # pre-check and the per-color array build below (stable argsort slicing
    # replaces the former per-color Python append loop; the weight formulas
    # and the None→∓inf slab mapping are verbatim the old per-edge ones).
    flat_endpoint_i = [0] * edge_count
    flat_endpoint_j = [0] * edge_count
    flat_weight_i = [0.0] * edge_count
    flat_weight_j = [0.0] * edge_count
    flat_budget = [0.0] * edge_count        # dummy 0.0 at interval slots
    flat_slab_low = [_NEG_INF] * edge_count
    flat_slab_high = [_POS_INF] * edge_count
    flat_is_interval = [False] * edge_count
    for edge_index in range(edge_count):
        ei, ej, budget, kind = iter_edges[edge_index]
        flat_endpoint_i[edge_index] = ei
        flat_endpoint_j[edge_index] = ej
        flat_weight_i[edge_index] = \
            0.5 if kind == 0 else (1.0 if kind == 2 else 0.0)
        flat_weight_j[edge_index] = \
            0.5 if kind == 0 else (1.0 if kind == 1 else 0.0)
        if budget is None:
            flat_is_interval[edge_index] = True
            s_low, s_high = bounds.get(edge_index, (None, None))
            if s_low is not None:
                flat_slab_low[edge_index] = s_low
            if s_high is not None:
                flat_slab_high[edge_index] = s_high
        else:
            flat_budget[edge_index] = budget
    endpoint_i = np.asarray(flat_endpoint_i, dtype=np.intp)
    endpoint_j = np.asarray(flat_endpoint_j, dtype=np.intp)
    weight_i = np.asarray(flat_weight_i, dtype=np.float64)
    weight_j = np.asarray(flat_weight_j, dtype=np.float64)
    # ── HYPER ROWS — the WEIGHTED 4-NODE TRANSECT CONSTRAINTS ─────────
    # Spec ``transverse-hyperplane-solve-spec.md`` §3-5 (owner ruling
    # 2026-08-21).  A corridor cross-section is not a node pair: its two
    # ends are points INTERPOLATED along ring edges, so the law is
    # ``|w . z| <= b`` with four nodes and four weights
    # ((1-t), t, -(1-s), -s), not ``|z_i - z_j| <= b``.  They ride their
    # own columns — never a 5-tuple in ``iter_edges``, which the
    # ``len(edge) >= 4`` decoders would read as an interval slab.
    # A HARD node's weight is MASKED in the projection step (it absorbs
    # none of the correction and never moves), exactly as ``kind``
    # masks a hard endpoint's ``wi``/``wj`` above.
    H_idx = H_w = H_b = H_free = None
    H_m = 0
    if hyper_rows:
        _hard = hard_nodes or ()
        _rows = [r for r in hyper_rows
                 if all(0 <= int(k) < n for k in r[0])]
        H_m = len(_rows)
        if H_m:
            H_idx = np.asarray([[int(k) for k in r[0]] for r in _rows],
                               dtype=np.intp)
            H_w = np.asarray([[float(w) for w in r[1]] for r in _rows],
                             dtype=np.float64)
            H_b = np.asarray([float(r[2]) for r in _rows],
                             dtype=np.float64)
            H_free = np.ones_like(H_w)
            if _hard:
                _hs = set(int(i) for i in _hard)
                for _r in range(H_m):
                    for _c in range(4):
                        if int(H_idx[_r, _c]) in _hs:
                            H_free[_r, _c] = 0.0
    budget_column = np.asarray(flat_budget, dtype=np.float64)
    # RAW-LAW instrument column (§1a): the sweep budgets with every
    # margined entry restored to its raw law budget.  Write-only — it
    # reaches ``_stall_guard_report`` and nothing else.  Absent (or all
    # ``None``) it IS ``budget_column``, so no array is built.
    raw_budget_column = budget_column
    if raw_budget_by_index:
        _flat_raw = list(flat_budget)
        _any_raw = False
        for _ei in range(min(edge_count, len(raw_budget_by_index))):
            _rb = raw_budget_by_index[_ei]
            if _rb is not None and _rb != _flat_raw[_ei]:
                _flat_raw[_ei] = _rb
                _any_raw = True
        if _any_raw:
            raw_budget_column = np.asarray(_flat_raw, dtype=np.float64)
    slab_low_column = np.asarray(flat_slab_low, dtype=np.float64)
    slab_high_column = np.asarray(flat_slab_high, dtype=np.float64)
    interval_mask = np.asarray(flat_is_interval, dtype=bool)
    z = np.asarray(elev, dtype=np.float64)
    # BOUNDED YIELD (owner ruling 2026-07-29: "Any yield absolutely needs to
    # stay within the feasibility box"): every node with a box stays inside
    # it — clamp at seed (the chain prepass may have moved a bounded node)
    # and after every sweep; a clamp movement > tol keeps the sweep active,
    # so certification proves edges AND boxes jointly satisfied.
    # ``node_box=None`` (every caller without the yield bounds) is
    # byte-identical: no arrays, no clamps.
    box_idx = box_lo = box_hi = None
    if node_box:
        box_idx, box_lo, box_hi = _node_box_arrays(node_box, np)
        z[box_idx] = np.minimum(np.maximum(z[box_idx], box_lo), box_hi)
    # ── THE NEGATIVE-ZERO GATE (perf 2026-08-13, byte-identity premise) ──
    # The sweep below skips writes it can PROVE are value-preserving: an
    # edge inside tolerance contributes ``se = sign(d) * 0.0``, i.e. ±0.0,
    # and ``x - (±0.0)`` / ``x + (±0.0)`` is ``x`` for every double x —
    # with ONE exception, ``x = -0.0``, where ``-0.0 - (-0.0)`` and
    # ``-0.0 + (+0.0)`` are ``+0.0``.  So "skipping a no-op write is
    # value-identical" holds exactly when no z entry is a NEGATIVE ZERO.
    # That is an INVARIANT, not merely an entry condition: every write
    # here is ``a ± b`` with ``a`` a current z value, and IEEE-754
    # round-to-nearest yields -0.0 from ``a - b`` only when ``a`` is -0.0,
    # and from ``a + b`` only when BOTH are -0.0 (equal finite operands
    # cancel to +0.0) — so a z free of -0.0 STAYS free of it.
    # ``np.minimum`` in the box clamp can hand back a -0.0 BOUND, so the
    # bounds are gated with the field.  A field (or bound) that does carry
    # a -0.0 takes the full-width writes below, verbatim.
    _no_neg_zero = not bool(((z == 0.0) & np.signbit(z)).any())
    if _no_neg_zero and box_idx is not None:
        _no_neg_zero = not bool(
            ((box_lo == 0.0) & np.signbit(box_lo)).any()
            or ((box_hi == 0.0) & np.signbit(box_hi)).any())
    # ── feasibility pre-check (see docstring): certified without coloring ──
    if run_feasibility_precheck and max_iters >= 1:
        feasible = True
        symmetric_rows = np.flatnonzero(~interval_mask)
        if symmetric_rows.size:
            d = z[endpoint_i[symmetric_rows]] - z[endpoint_j[symmetric_rows]]
            over = np.abs(d) - budget_column[symmetric_rows]
            feasible = not bool((over > tol).any())
        if feasible:
            interval_rows = np.flatnonzero(interval_mask)
            if interval_rows.size:
                di = (z[endpoint_i[interval_rows]]
                      - z[endpoint_j[interval_rows]])
                above = di - slab_high_column[interval_rows]
                below = slab_low_column[interval_rows] - di
                feasible = not bool(((above > tol) | (below > tol)).any())
        if feasible and H_m:
            # THE TRANSECT ROWS ARE PART OF "FEASIBLE" (spec §5).  Without
            # this the pre-check certifies a field on the PAIR law alone
            # and returns before the sweep — a whole law family skipped in
            # exactly the case it was added for (every pair satisfied,
            # the corridor still leaning: CYXY within_shape airside 0 with
            # 75 transverse airside rows).
            _pre = (H_w * z[H_idx]).sum(1) - H_b
            feasible = not bool((_pre > tol).any())
        if feasible:
            # Mirror the certified-on-sweep-1 exit exactly: same writeback,
            # same counters, same return value (worst resets to 0.0 at sweep
            # start and no edge was active, so it stays 0.0).
            elev[:] = z.tolist()
            if stats is not None:
                color_count_report = None
                if _os.environ.get("O4_STEP_DEBUG") == "1":
                    _, color_count_report = _extend_edge_coloring_by_write(
                        iter_edges,
                        coloring_state if coloring_state is not None else {})
                stats["colors"] = color_count_report
                stats["edges"] = edge_count
                stats["sweeps"] = 1
                stats["sweeps_avoided"] = max(0, max_iters - 1)
                stats["certified"] = True
                stats["exit_reason"] = "certified"
                stats["worst"] = 0.0
            return 1, True
    edge_color, color_count = _extend_edge_coloring_by_write(
        iter_edges, coloring_state if coloring_state is not None else {})
    # per-color numpy arrays, symmetric + interval partitioned, sliced from
    # the flat columns via ONE stable argsort: within a color the members come
    # out in ascending edge order — exactly the order the old per-color append
    # loop produced (and irrelevant to the math anyway: disjoint writes).
    edge_color_array = np.asarray(edge_color, dtype=np.int64)
    stable_order = np.argsort(edge_color_array, kind="stable")
    group_bounds = np.searchsorted(edge_color_array[stable_order],
                                   np.arange(color_count + 1))
    # PER-COLOR BLOCK LIST (perf 2026-08-04, value-identical).  The sweep
    # loop below used to index ``sym[color]`` / ``intv[color]``, unpack both
    # tuples and test ``.size`` for EVERY color on EVERY sweep — at HEAZ that
    # is 273 colors x 27 747 sweeps = 7.6 M unpacks of partitions that are
    # very often empty.  The empty partitions are dropped HERE, once per
    # call, and the survivors keep their original order (color 0 symmetric,
    # color 0 interval, color 1 symmetric, …), so the Gauss-Seidel visit
    # sequence — and therefore the fixpoint — is bit-for-bit unchanged.
    #
    # Each block also stacks the color's ``I`` and ``J`` into one (2, k)
    # index array ``IJ``: ``z[IJ]`` is exactly ``stack(z[I], z[J])`` (a pure
    # gather) in ONE advanced-indexing dispatch instead of two.  When the
    # color's I|J indices are all distinct the two endpoint updates can then
    # be applied to that already-gathered pair and scattered back in a single
    # write, instead of two read-modify-write round trips.  Distinctness is
    # NOT free from the coloring: ``_extend_edge_coloring_by_write`` only
    # conflicts on WRITE nodes, so a ``kind`` 1/2 edge's zero-weight endpoint
    # is unguarded and may repeat inside a color.  It is therefore VERIFIED
    # here, once per call; ``disjoint=False`` falls back to the original
    # two-statement form, which is what makes the rewrite exact rather than
    # merely usually-right.
    blocks: list = []
    for color in range(color_count):
        members = stable_order[group_bounds[color]:group_bounds[color + 1]]
        member_is_interval = interval_mask[members]
        symmetric_members = members[~member_is_interval]
        interval_members = members[member_is_interval]
        symmetric_block = interval_block = None
        if symmetric_members.size:
            si = endpoint_i[symmetric_members]
            sj = endpoint_j[symmetric_members]
            s_wi = weight_i[symmetric_members]
            s_wj = weight_j[symmetric_members]
            s_disjoint = bool(np.unique(np.concatenate((si, sj))).size
                              == si.size + sj.size)
            symmetric_block = (
                si, sj, np.stack((si, sj)), s_disjoint,
                budget_column[symmetric_members], s_wi, s_wj,
                None if s_disjoint else _column_last_write_mask(np, si),
                None if s_disjoint else _column_last_write_mask(np, sj))
        if interval_members.size:
            ii = endpoint_i[interval_members]
            ij = endpoint_j[interval_members]
            i_wi = weight_i[interval_members]
            i_wj = weight_j[interval_members]
            i_disjoint = bool(np.unique(np.concatenate((ii, ij))).size
                              == ii.size + ij.size)
            interval_block = (
                ii, ij, np.stack((ii, ij)), i_disjoint,
                slab_low_column[interval_members],
                slab_high_column[interval_members], i_wi, i_wj,
                None if i_disjoint else _column_last_write_mask(np, ii),
                None if i_disjoint else _column_last_write_mask(np, ij))
        if symmetric_block is not None or interval_block is not None:
            blocks.append((symmetric_block, interval_block))
    sweeps = 0
    certified = False
    worst = 0.0
    # ``worst`` shortcut (value-identical, see the sweep body): with a
    # non-negative tolerance the largest residual is itself active, so
    # ``np.where(active, over, 0.0).max()`` equals ``over.max()`` — which the
    # activity test already computed.  A negative tolerance would let an
    # inactive 0.0 win the max, so that case keeps the original expression.
    worst_is_residual_max = bool(tol >= 0.0)
    np_where = np.where
    np_sign = np.sign
    np_flatnonzero = np.flatnonzero
    # ACTIVE-ROW COMPRESSION gate (see the negative-zero gate above and
    # the sweep body).
    compress = _no_neg_zero
    # ── STALL REPORT state (see ``projection_stall_report_enabled``) ──
    # ``stall_min`` is the running minimum of the per-sweep active
    # violating-edge count; ``stall_ref`` is that minimum's value at the
    # last QUALIFYING improvement (a new minimum counts only when it beats
    # ``stall_ref`` by ≥ ``STALL_REL_IMPROVEMENT`` relative); ``stall_wait``
    # is the number of full passes since.  Detection SNAPSHOTS and lets the
    # sweep loop run on — there is no early exit here, by ruling.  Gate OFF
    # ⇒ none of this is touched and no count is taken.
    stall_on = projection_stall_report_enabled()
    # The interval half additionally needs ``tol >= 0``: that is what makes
    # every ACTIVE row's ``|se|`` strictly positive, hence the full-width
    # ``argmax`` the stall report reads provably an active row (see the
    # compressed branch).  With a negative tolerance an inactive 0.0 could
    # win that argmax, so the compression stands down there.
    compress_int = compress and (worst_is_residual_max or not stall_on)
    stall_min = None
    stall_ref = None
    stall_wait = 0
    stall_carrier = None
    stall_active = 0
    stall_detect_sweep = 0
    stall_detect_active = 0
    stall_detect_worst = 0.0
    stall_detect_carrier = None
    # ── THE CONVERGENCE-CRITERION EXIT (cycle-7 fix 1) ────────────────
    # ``max_iters`` is the BLOCK size now, not the exit.  The loop sweeps
    # a block, measures the EXACT whole-graph residual on the settled
    # field, and decides on evidence:
    #   CERTIFIED — a sweep applied no correction and no clamp (KKT);
    #   MATERIAL  — no edge is ≥ the campaign materiality floor;
    #   CONVERGED — the ≥-material count stopped falling (patience
    #               blocks below the relative-improvement floor);
    #   CAP       — the absolute anti-hang ceiling fired, and says so.
    # An IMPOSED budget (a test, a deliberately bounded probe, a ladder
    # arm) keeps exactly the old semantics: hard cap = the block, one
    # block, no extension — the caller's number is the law.
    block = max_iters if max_iters > 0 else 0
    hard_cap = block if sweep_hard_cap is None else max(block, sweep_hard_cap)
    exit_reason = "cap"
    prev_material = None
    flat_blocks = 0
    block_trace: list = []
    last_block_drop = None
    for _sweep in range(hard_cap):
        sweeps += 1
        any_active = False
        worst = 0.0
        stall_active = 0
        stall_carrier = None
        for symmetric_block, interval_block in blocks:
            if symmetric_block is not None:
                I, J, IJ, disjoint, B, WI, WJ, win_i, win_j = \
                    symmetric_block
                # one gather for both endpoints; ``pair`` is a fresh copy, so
                # ``pair[0]``/``pair[1]`` are the pre-write ``z[I]``/``z[J]``.
                pair = z[IJ]
                d = pair[0] - pair[1]
                over = abs(d) - B
                # ``over.max() > tol`` is exactly ``(over > tol).any()``.
                # ``float()`` once: every test below then compares two
                # PYTHON floats instead of re-entering numpy's scalar type
                # (same value, ~2 M fewer scalar dispatches per call).
                residual_max = float(over.max())
                if residual_max > tol:
                    any_active = True
                    # ONE activity mask per visit: the places that used to
                    # recompute ``over > tol`` read this (or ``rows``).
                    active = over > tol
                    ex = None
                    if worst_is_residual_max:
                        w = residual_max
                    else:
                        ex = np_where(active, over, 0.0)
                        w = float(ex.max())
                    if w > worst:
                        worst = w
                        if stall_on:
                            _k = int(over.argmax() if worst_is_residual_max
                                     else ex.argmax())
                            stall_carrier = ("sym", int(I[_k]), int(J[_k]),
                                             float(B[_k]), float(d[_k]),
                                             float(WI[_k]), float(WJ[_k]))
                    # ``se = sign(d) * ex`` once: ``(-s)*ex*WI`` is exactly
                    # ``-((s*ex)*WI)`` (negation is exact in IEEE 754).
                    # ── ACTIVE-ROW COMPRESSION (perf 2026-08-13) ──────
                    # Only rows with ``over > tol`` carry a correction;
                    # every other row contributes ``se = sign(d) * 0.0``
                    # and so writes its endpoints back UNCHANGED (the
                    # negative-zero gate above is exactly the condition
                    # under which "unchanged" is bit-true).  At HECA 5-6 %
                    # of a colour's rows are active, so the whole
                    # sign / multiply / scatter tail runs on that slice
                    # instead of the full width.  Restricted to DISJOINT
                    # colours on purpose: where I|J repeat, numpy's
                    # ``z[I] += t`` keeps the LAST duplicate's value, and
                    # dropping an inactive duplicate would change WHICH
                    # row wins — not a no-op.  Row values themselves are
                    # untouched: ``over``/``d``/the weights are read at
                    # the same indices, so each surviving correction is
                    # the same double, applied in the same order.
                    rows = (np_flatnonzero(active)
                            if (compress
                                and over.size >= COMPRESSION_MIN_ROWS)
                            else None)
                    if stall_on:
                        # ``rows.size`` IS ``active.sum()`` where the rows
                        # were materialised — one fewer full-width pass.
                        stall_active += (rows.size if rows is not None
                                         else int(active.sum()))
                    if rows is not None and rows.size * 2 <= over.size:
                        se = np_sign(d[rows]) * over[rows]
                        _scatter_sub(z, I, WI, rows, se, win_i)
                        _scatter_add(z, J, WJ, rows, se, win_j)
                    else:
                        if ex is None:
                            ex = np_where(active, over, 0.0)
                        se = np_sign(d) * ex
                        # disjoint writes within a color -> fancy-indexed add
                        # is a valid simultaneous update (immovable slots
                        # carry weight 0).
                        if disjoint:
                            pair[0] -= se * WI
                            pair[1] += se * WJ
                            z[IJ] = pair
                        else:
                            # ``z[I] += t`` re-gathers ``z[I]``, which is
                            # still ``pair[0]`` (nothing wrote z since the
                            # gather); ``a + (-t)`` is exactly ``a - t``.
                            # Duplicate slots still resolve last-wins, on
                            # the same values, so the scatter is unchanged.
                            pair[0] -= se * WI
                            z[I] = pair[0]
                            z[J] += se * WJ
            if interval_block is not None:
                (Ii, Ji, IJi, disjoint_i, Lo, Hi,
                 IWI, IWJ, win_ii, win_ij) = interval_block
                pair = z[IJi]
                di = pair[0] - pair[1]
                above = di - Hi
                below = Lo - di
                # exactly ``(active_hi | active_lo).any()``
                if above.max() > tol or below.max() > tol:
                    any_active = True
                    # ACTIVE-ROW COMPRESSION, interval half.  Same premise
                    # as the symmetric one: an inactive slab row carries
                    # ``se = 0.0`` and writes its endpoints back unchanged.
                    # ``abs(se).max()`` over the full width equals the max
                    # over the active rows (the rest are 0.0 and |se| >= 0),
                    # so ``worst`` is untouched.  The stall report's
                    # ``argmax`` is an index into the FULL row set, so the
                    # compressed form stands down while that gate is on.
                    rows = (np_flatnonzero((above > tol) | (below > tol))
                            if (compress_int
                                and above.size >= COMPRESSION_MIN_ROWS)
                            else None)
                    if rows is not None and rows.size * 2 <= above.size:
                        ra = above[rows]
                        se = np_where(ra > tol, ra, di[rows] - Lo[rows])
                        ase = abs(se)
                        aw = float(ase.max())
                        if aw > worst:
                            worst = aw
                            if stall_on:
                                # ``abs(se)`` is 0.0 on every inactive row
                                # and STRICTLY positive on every active one
                                # (``compress_int`` requires tol >= 0), so
                                # the full-width argmax lands on an active
                                # row — and ``rows`` is ascending, so this
                                # is the same row the full array names.
                                _k = int(rows[ase.argmax()])
                                stall_carrier = ("int", int(Ii[_k]),
                                                 int(Ji[_k]), float(Lo[_k]),
                                                 float(Hi[_k]),
                                                 float(di[_k]), 0.0)
                        if stall_on:
                            stall_active += rows.size
                        _scatter_sub(z, Ii, IWI, rows, se, win_ii)
                        _scatter_add(z, Ji, IWJ, rows, se, win_ij)
                    else:
                        se = np_where(above > tol, above,
                                      np_where(below > tol, di - Lo, 0.0))
                        aw = float(abs(se).max())
                        if aw > worst:
                            worst = aw
                            if stall_on:
                                _k = int(abs(se).argmax())
                                stall_carrier = ("int", int(Ii[_k]),
                                                 int(Ji[_k]), float(Lo[_k]),
                                                 float(Hi[_k]),
                                                 float(di[_k]), 0.0)
                        if stall_on:
                            stall_active += int(((above > tol)
                                                 | (below > tol)).sum())
                        if disjoint_i:
                            pair[0] -= se * IWI
                            pair[1] += se * IWJ
                            z[IJi] = pair
                        else:
                            pair[0] -= se * IWI
                            z[Ii] = pair[0]
                            z[Ji] += se * IWJ
        if box_idx is not None:
            # BOUNDED YIELD: re-clamp after the sweep; movement beyond tol
            # means an edge pushed a node out of its box — stay active so
            # the incident edges re-relax against the clamped value.
            # ONE gather (perf 2026-08-13): ``z[box_idx]`` was fetched
            # twice per sweep — for the clamp and again for the movement —
            # and the same values feed both.
            box_cur = z[box_idx]
            clamped = np.minimum(np.maximum(box_cur, box_lo), box_hi)
            clamp_move = np.abs(clamped - box_cur)
            if (clamp_move > tol).any():
                any_active = True
                w = float(clamp_move.max())
                if w > worst:
                    worst = w
                    if stall_on:
                        _k = int(clamp_move.argmax())
                        stall_carrier = ("box", int(box_idx[_k]), -1,
                                         float(box_lo[_k]), float(box_hi[_k]),
                                         float(clamp_move[_k]), 0.0)
            # Write back only the entries the clamp actually MOVED: the
            # rest would be scattered onto their own value (the
            # negative-zero gate is what makes "own value" bit-true).
            mv_rows = (np_flatnonzero(clamp_move != 0.0)
                       if compress else None)
            if mv_rows is not None and mv_rows.size * 2 <= clamp_move.size:
                z[box_idx[mv_rows]] = clamped[mv_rows]
            else:
                z[box_idx] = clamped
        # ── THE HALF-SPACE PROJECTION (spec §5) ───────────────────
        # ``r = w . z - b``; an over-cap row is projected onto its
        # half-space, the correction spread over its FREE nodes in
        # weight proportion (``step * w / ||w_free||^2``) and scattered
        # into the same degree-normalised accumulator shape the pair
        # rows use.  Two rows (w and -w) express ``|near - far| <= b``,
        # so nothing here needs a sign convention of its own.
        if H_m:
            _hz = z[H_idx]
            _r = (H_w * _hz).sum(1) - H_b
            _act = _r > tol
            if bool(_act.any()):
                any_active = True
                _w = float(_r.max())
                if _w > worst:
                    worst = _w
                    if stall_on:
                        _k = int(_r.argmax())
                        stall_carrier = ("hyp", int(H_idx[_k, 0]),
                                         int(H_idx[_k, 2]), float(H_b[_k]),
                                         float(_r[_k]), 0.0, 0.0)
                _wf = H_w * H_free
                _nrm = (_wf * _wf).sum(1)
                # THE STEP IS CAPPED AT THE ROW'S OWN VIOLATION (attempt
                # 2, 2026-08-21).  ``r / ||w_free||^2`` is the exact
                # projection onto the half-space, and it is exact only
                # while the norm is healthy: a near-degenerate weight
                # vector turns a centimetre of excess into a kilometre of
                # correction (measured attempt 1: a -2608 m apron value
                # the band clamp caught).  The vertex snap upstream now
                # bounds the norm geometrically; this cap is the second
                # belt — with every |w| <= 1, a step of |r| moves no node
                # further than the violation it is answering, so a row
                # can never author more displacement than it measures.
                # Where the norm IS healthy (the overwhelming majority)
                # the cap is inactive and the step is the exact
                # projection.
                _step = np.where(_act & (_nrm > 0.0), _r / np.maximum(
                    _nrm, 1e-30), 0.0)
                _step = np.clip(_step, -np.abs(_r), np.abs(_r))
                _corr = -(_step[:, None] * _wf)
                _flat = H_idx.ravel()
                _acc = np.bincount(_flat, weights=_corr.ravel(),
                                   minlength=n)
                _cnt = np.bincount(
                    _flat,
                    weights=np.repeat(_act.astype(np.float64), 4)
                    * H_free.ravel(),
                    minlength=n)
                _nz = _cnt > 0.0
                z[_nz] += _acc[_nz] / _cnt[_nz]
        if not any_active:
            certified = True
            exit_reason = "certified"
            break
        # ── BLOCK BOUNDARY: decide on evidence (cycle-7 fix 1) ────────
        # The ONLY place the loop may stop short of the hard cap without
        # a KKT certificate.  Measured on the settled field, in one
        # frame, so consecutive readings are comparable.
        if block and sweeps % block == 0:
            _n_over, _n_material, _worst_exact = _material_over_cap(
                np, tol, PROJECTION_MATERIALITY_M, endpoint_i, endpoint_j,
                budget_column, slab_low_column, slab_high_column,
                interval_mask, z)
            last_block_drop = (None if prev_material is None
                               else prev_material - _n_material)
            block_trace.append((sweeps, _n_over, _n_material, _worst_exact,
                                last_block_drop))
            if _n_material == 0:
                # MATERIALLY CERTIFIED — every remaining residual is
                # below the campaign floor, which the law adjudicates as
                # PASS-with-residual.  Sweeping on to chase millimetres
                # is the guard deciding the surface again, from the
                # other side.
                exit_reason = "material"
                break
            if prev_material is not None:
                # "Still improving" is a RELATIVE floor: a block must buy
                # at least MIN_DROP of the standing count.  ``max(1, …)``
                # keeps a tiny standing count from making any drop
                # qualify.
                _floor = max(1, int(SWEEP_CONVERGENCE_MIN_DROP
                                    * prev_material))
                if last_block_drop < _floor:
                    flat_blocks += 1
                    if flat_blocks >= SWEEP_CONVERGENCE_PATIENCE:
                        exit_reason = "converged"
                        break
                else:
                    flat_blocks = 0
            prev_material = _n_material
        if stall_on and not stall_detect_sweep:
            # STALL DETECTION — REPORT ONLY.  There is deliberately no
            # ``break`` here: the early-termination family was closed
            # 2026-08-04 after both candidate metrics were falsified, so
            # the detector's whole job is to SNAPSHOT the state that names
            # the infeasible carrier pair.  The sweep loop then runs
            # exactly as long as it always did.
            if stall_min is None or stall_active < stall_min:
                stall_min = stall_active
            if stall_ref is None or (
                    stall_min < stall_ref
                    and stall_min <= stall_ref * (1.0 - STALL_REL_IMPROVEMENT)):
                stall_ref = stall_min
                stall_wait = 0
            else:
                stall_wait += 1
                if stall_wait >= STALL_PATIENCE_SWEEPS:
                    stall_detect_sweep = sweeps
                    stall_detect_active = stall_active
                    stall_detect_worst = worst
                    stall_detect_carrier = stall_carrier
    elev[:] = z.tolist()
    uncertified = None
    if not certified:
        # CERTIFY OR SAY SO.  WRITE-ONLY (after the writeback): nothing
        # here feeds the solve, which is why the loud exit is inert on
        # the surface.
        uncertified = _uncertified_exit_report(
            np, tol, sweeps, max_iters,
            endpoint_i, endpoint_j, budget_column, raw_budget_column,
            slab_low_column, slab_high_column, interval_mask,
            weight_i, weight_j, z, n, sweep_budget_basis,
            family_by_pair=family_by_pair,
            exit_reason=exit_reason, block=block, hard_cap=hard_cap,
            block_trace=block_trace, last_block_drop=last_block_drop,
            flat_group_reps=flat_group_reps)
    if stall_detect_sweep:
        # WRITE-ONLY (after the writeback): nothing below feeds the solve.
        # ``hard_cap``, not the block: the "ran to" figure must be the
        # loop's actual ceiling or the burned-sweep count is a fiction.
        _stall_guard_report(np, sweeps, hard_cap, stall_detect_sweep,
                            stall_detect_active, stall_detect_worst,
                            stall_detect_carrier, stall_active, worst,
                            stall_carrier, endpoint_i, endpoint_j,
                            raw_budget_column, interval_mask,
                            weight_i, weight_j, z, n,
                            flat_group_reps=flat_group_reps)
    if stats is not None:
        stats["colors"] = color_count
        stats["edges"] = len(iter_edges)
        stats["sweeps"] = sweeps
        stats["sweeps_avoided"] = max(0, hard_cap - sweeps) if certified else 0
        stats["certified"] = certified
        # WHICH CRITERION FIRED (cycle-7 fix 1) — "certified" alone can no
        # longer describe the exit: a materially-certified surface and a
        # converged-but-violating one are different findings.
        stats["exit_reason"] = exit_reason
        stats["block"] = block
        stats["hard_cap"] = hard_cap
        stats["block_trace"] = block_trace
        stats["worst"] = worst
        if uncertified is not None:
            # Present ONLY on an uncertified exit, so a certified call's
            # stats dict is unchanged.
            stats["uncertified_exit"] = uncertified
        if stall_on:
            stats["stalled"] = bool(stall_detect_sweep)
            stats["stall_detect_sweep"] = stall_detect_sweep
            stats["stall_sweeps_burned"] = (max(0, sweeps - stall_detect_sweep)
                                            if stall_detect_sweep else 0)
            stats["active_edges"] = stall_active
            stats["carrier"] = stall_carrier
            stats["detect_carrier"] = stall_detect_carrier
    return sweeps, certified


def _reach_witness(sign, radj, seeds, elev, n, horizon=None):
    """``_reach_plain`` plus the WITNESS: which hard anchor each node's
    envelope value came from.

    Forensics only (spec ``docs/specs/reference-honesty-and-terracing-
    spec.md`` Track 1 step 4).  Kept as a separate function so the
    production Dijkstra is untouched — this one only runs when
    ``O4_BREAK_FORENSICS`` is set.  ``seeds`` / ``horizon`` mirror
    ``_reach_plain`` so the report names the anchors the LIVE envelope
    actually consulted (see the groundside-witness clause)."""
    import heapq
    best: dict = {}
    src: dict = {}
    # Tuple order (value, anchor, distance, node) deliberately keeps ANCHOR
    # ahead of the added distance field: the tie-break order — and therefore
    # which witness a tied label reports — is exactly the pre-horizon one.
    pq = [((elev[a] if sign > 0 else -elev[a]), a, 0.0, a)
          for a in seeds if a < n]
    heapq.heapify(pq)
    while pq:
        val, _tie, dk, k = heapq.heappop(pq)
        anchor = _tie
        t = val if sign > 0 else -val
        if k in best and ((sign > 0 and t >= best[k])
                          or (sign < 0 and t <= best[k])):
            continue
        best[k] = t
        src[k] = anchor
        for (j, w) in radj.get(k, ()):
            ndk = dk + (w if w >= 0.0 else -w)
            if horizon is not None and ndk > horizon:
                continue
            nt = t + w
            pj = best.get(j)
            if pj is None or (sign > 0 and nt < pj) or (sign < 0 and nt > pj):
                heapq.heappush(pq, ((nt if sign > 0 else -nt), anchor,
                                    ndk, j))
    return best, src


def _merge_witness(best_a, src_a, best_b, src_b, sign):
    """Merge a horizon-bounded witness pass into the unrestricted one with
    the same rule the live envelope uses (``min`` for the ceiling, ``max``
    for the floor)."""
    for k, v in best_b.items():
        cur = best_a.get(k)
        if cur is None or (sign > 0 and v < cur) or (sign < 0 and v > cur):
            best_a[k] = v
            src_a[k] = src_b.get(k)
    return best_a, src_a


def _break_forensics_report(path, label, broken, hard, elev, n,
                            ceil_radj, floor_radj, classes, latlon,
                            limited=None, horizon=None):
    """Name every band-inverted node's ``floor > ceiling`` WITNESS PAIR by
    ANCHOR CLASS (spec Track 1 step 4 — a deliverable in its own right).

    This is the honest answer to whether a component is feasible whole: an
    inverted node is not "the solver failing", it is two HARD anchors whose
    values cannot both be reached through the fabric between them.  Naming
    the pair by class says WHICH law or WHICH anchor value is wrong.

    ``t_fallback`` retired 2026-08-04 with the break blend it counted
    (spec kill-half §2) — there is no ``t`` left to fall back on."""
    import statistics as _stats
    try:
        _seeds = (set(hard) - set(limited)) if limited else hard
        _c_best, _c_src = _reach_witness(+1, ceil_radj, _seeds, elev, n)
        _f_best, _f_src = _reach_witness(-1, floor_radj, _seeds, elev, n)
        if limited:
            _merge_witness(_c_best, _c_src,
                           *_reach_witness(+1, ceil_radj, limited, elev, n,
                                           horizon), sign=+1)
            _merge_witness(_f_best, _f_src,
                           *_reach_witness(-1, floor_radj, limited, elev, n,
                                           horizon), sign=-1)
    except Exception as exc:                           # pragma: no cover
        print(f"    [break-forensics] witness pass failed: {exc}")
        return
    rows = []
    buckets: dict = {}
    for i in sorted(broken):
        lo = _f_best.get(i)
        hi = _c_best.get(i)
        if lo is None or hi is None:
            continue
        fw = _f_src.get(i)
        cw = _c_src.get(i)
        fc = classes.get(fw, "unclassified") if fw is not None else "none"
        cc = classes.get(cw, "unclassified") if cw is not None else "none"
        deficit = lo - hi
        rows.append((i, lo, hi, deficit, fw, fc, cw, cc))
        buckets.setdefault((fc, cc), []).append(deficit)
    print(f"    [break-forensics] {label}: {len(rows)} inverted node(s) "
          f"with a witness pair (of {len(broken)} inverted); "
          f"{len(buckets)} floor×ceiling ANCHOR-CLASS pair(s)")
    for (key, deficits) in sorted(buckets.items(),
                                  key=lambda kv: -len(kv[1])):
        print(f"    [break-forensics]   floor={key[0]:<20s} "
              f"ceil={key[1]:<20s} n={len(deficits):<7d} "
              f"deficit p50={_stats.median(deficits):8.3f} m "
              f"max={max(deficits):8.3f} m")
    if not path:
        return
    try:
        out = path
        if label:
            stem, _dot, ext = path.rpartition(".")
            out = (f"{stem}.{label.replace('#', '')}.{ext}"
                   if stem else path)
        with open(out, "w") as fh:
            fh.write("node,lat,lon,floor,ceil,deficit,"
                     "floor_witness,floor_class,ceil_witness,ceil_class\n")
            for (i, lo, hi, deficit, fw, fc, cw, cc) in rows:
                la, lon = (latlon[i] if latlon and i < len(latlon)
                           else (0.0, 0.0))
                fh.write(f"{i},{la:.7f},{lon:.7f},{lo:.4f},{hi:.4f},"
                         f"{deficit:.4f},{fw},{fc},{cw},{cc}\n")
        print(f"    [break-forensics] {label} -> {out} ({len(rows)} row(s))")
    except Exception as exc:                           # pragma: no cover
        print(f"    [break-forensics] dump failed: {exc}")


def partition_constraints_by_receiver(shape_constraints, receiver_nodes):
    """Split a constraint list into ``(giver_side, receiver_side)``.

    A pair belongs to the RECEIVER side as soon as EITHER endpoint is a
    receiver node: an airside↔groundside law edge is the coupling the
    partition exists to make one-directional, so it is enforced in the
    receiver pass (where the airside endpoint is frozen), never in the
    airside one.  Everything else is the giver (airside) side.

    LAZY (flatness-certified) entries are never split: their body pairs
    do not exist yet, and ``feasibility_project`` expands them IN PLACE
    so a later projection sees the expansion.  Such an entry is handed to
    one side WHOLE and BY IDENTITY (never a copy) — receiver side if it
    touches any receiver node, giver side otherwise.  A lazy entry is one
    SHAPE's law, so this is the shape's own side by construction.

    Eager entries are copied per side with their other keys intact
    (``family``, ``envelope_skip``, …) and an empty side is dropped.
    ``receiver_nodes`` empty ⇒ ``(shape_constraints, [])`` with the SAME
    list object, i.e. the un-partitioned call is byte-identical.
    """
    if not receiver_nodes:
        return shape_constraints, []
    givers: list = []
    receivers: list = []
    for sc in shape_constraints:
        edges = sc.get("edges") or ()
        touches = any((e[0] in receiver_nodes or e[1] in receiver_nodes)
                      for e in edges)
        if sc.get("lazy_expand") is not None:
            if not touches:
                touches = any(i in receiver_nodes
                              for i in (sc.get("lazy_nodes") or ()))
            (receivers if touches else givers).append(sc)   # BY IDENTITY
            continue
        if not touches:
            givers.append(sc)
            continue
        g_edges = [e for e in edges
                   if e[0] not in receiver_nodes and e[1] not in receiver_nodes]
        r_edges = [e for e in edges
                   if e[0] in receiver_nodes or e[1] in receiver_nodes]
        if g_edges:
            givers.append(dict(sc, edges=g_edges))
        if r_edges:
            receivers.append(dict(sc, edges=r_edges))
    return givers, receivers


#: Apron staged solve kill switch, read through ``grade_law`` so the flag
#: has ONE owner (spec §5; ``O4_APRON_STAGED_SOLVE=0`` == compose-v3).
def _APRON_STAGED_SOLVE_get():
    from auto_patch import grade_law as _GL
    return bool(getattr(_GL, "APRON_STAGED_SOLVE", True))


class _StagedFlag:
    def __bool__(self):
        return _APRON_STAGED_SOLVE_get()


_APRON_STAGED_SOLVE = _StagedFlag()


def _split_apron_interior(entries, interior_pairs):
    """Split constraint ENTRIES into (senior, interior) by the apron staged
    solve's partition (spec ``docs/specs/apron-staged-solve-spec.md`` §2).

    ``interior_pairs`` is ``UnifiedGraph.interior_pairs()`` — the pairs
    ``grade_law.is_apron_interior`` claimed at MINT, never a cap-value guess.

    Entries are SPLIT, never dropped: every interior edge is enforced in the
    A2 pass with the seniors frozen, so no law leaves the system.  An entry
    with no interior edge is returned unchanged (identity, not a copy) so the
    common path allocates nothing; a mixed entry becomes two entries sharing
    every other key, which is how the ``hyper`` transect rows and the stage
    tag ride along with the SENIOR half where they belong.
    """
    if not interior_pairs:
        return list(entries), []
    senior, interior = [], []
    for sc in entries:
        edges = sc.get("edges") or ()
        idx = [i for i, e in enumerate(edges)
               if isinstance(e[0], int) and isinstance(e[1], int)
               and (min(e[0], e[1]), max(e[0], e[1])) in interior_pairs]
        if not idx:
            senior.append(sc)
            continue
        hit = set(idx)
        keep = [e for i, e in enumerate(edges) if i not in hit]
        drop = [edges[i] for i in idx]
        s_ent = dict(sc)
        s_ent["edges"] = keep
        senior.append(s_ent)
        # THE INTERIOR HALF CARRIES ONLY ITS PAIRS.  ``hyper`` (the bound
        # transect rows) stays with the senior half by construction: a
        # transect is a movement-surface law, and its nodes are senior.
        i_ent = {k: v for k, v in sc.items()
                 if k not in ("edges", "hyper", "lazy_nodes", "lazy_seed")}
        i_ent["edges"] = drop
        interior.append(i_ent)
    return senior, interior


def _partition_by_stage(givers, receivers, where):
    """THE STAGE PARTITION (staged-solve round S1b, Fable ruling
    2026-08-13b) — supersedes :func:`_withhold_road_pair_law`.

    Stage A's constraint system contains ONLY airside-tagged entries.
    Every entry carries a FIRST-CLASS STAGE TAG stamped where it was
    minted (:mod:`auto_patch.solve_stage`); an untagged entry RAISES,
    because a partition that defaults an unknown entry to a side is the
    exact blindness this replaces:

    * the predecessor keyed on ``sc["role"] in ROAD_ROLES``, which is
      structurally blind to the live §10 ROD INTERVAL (no role key at
      all — coupling 4 of ``tmp/s1_attribution.md``) and to the whole
      unified graph, which arrived as ONE bare ``{"edges": u_edges}``
      entry carrying every service_road / service_junction /
      groundside_pavement law pair into the airside pass (couplings 3
      and 6);
    * ``ROAD_ROLES`` also omits ``groundside_pavement`` entirely, so a
      groundside lot's pairs on AIRSIDE-CLAIMED (shared) nodes — which
      the receiver partition cannot catch, since neither endpoint is a
      receiver — were enforced against airside rows.

    The entries are MOVED, never deleted: groundside law stays fully
    enforced in the receiver pass, with airside frozen.  That is the
    service-road mouth ruling (RULINGS 2026-08-06) and "airside is king"
    (2026-07-30) in constraint form, now covering every family instead
    of the two road roles.
    """
    from auto_patch.solve_stage import STAGE_A, STAGE_B, assert_tagged
    assert_tagged(givers, where)
    assert_tagged(receivers, where)
    keep = [sc for sc in givers if sc["stage"] == STAGE_A]
    moved = [sc for sc in givers if sc["stage"] == STAGE_B]
    if not moved:
        return givers, receivers
    print(f"  [stage] {len(moved)} of {len(givers)} giver entr(y/ies) are "
          f"GROUNDSIDE-minted and move to the stage-B pass "
          f"(airside is king) at {where}")
    return keep, list(receivers) + moved


def _withhold_road_pair_law(givers, receivers):
    """ROAD PAIR LAW IS RECEIVER-PASS LAW (production default): every
    ROAD-role constraint entry moves from the airside (giver) pass to the
    receiver pass.

    THIS IS ENFORCEMENT OF STANDING LAW, NOT NEW LAW.  A road node WELDED
    to an airside ring has a non-groundside role, so the receiver
    partition does not catch it and its road pairs used to be enforced in
    the AIRSIDE pass — a groundside road's law constraining the airside
    solve, i.e. a PULL BACK, which the ONE-graph ruling (RULINGS
    2026-08-06, binding point 2: "the band flows airside → groundside;
    groundside is receiver-only, ZERO pull back") and "airside is king"
    already forbid.  Cycle-10's M1 measured that channel as the largest
    single carrier of the road feed's airside regression (−262 of +444 at
    HECA 10 000 m; +22 at −500).

    The entries are MOVED, never deleted: the law stays enforced, with
    airside FROZEN, so the road still grades under its own pair law from
    the seat airside settled — which is the service-road mouth ruling
    (RULINGS 2026-08-06) in constraint form.  Roles are the emitter's own
    (``lateral_contiguity.ROAD_ROLES``).

    ``O4_PROBE_ROAD_PAIR_LAW_AIRSIDE=1`` restores the OLD form by skipping
    this call entirely (see ``feasibility_project_partitioned``); it is a
    default-OFF probe gate so the comparison stays one env var away, and
    the arm it names is the M1 CTL arm (bodies ``da78f97768ff`` @10 000 m
    / ``29ed04fcf7bb`` @−500).
    """
    from auto_patch.lateral_contiguity import ROAD_ROLES
    keep, moved = [], []
    for sc in givers:
        (moved if sc.get("role") in ROAD_ROLES else keep).append(sc)
    if not moved:
        return givers, receivers
    print(f"  [receiver-only] road pair law: {len(moved)} road constraint "
          f"entr(y/ies) enforced in the RECEIVER pass, not the airside "
          f"pass (of {len(givers)} giver entries)")
    return keep, list(receivers) + moved


def feasibility_project_partitioned(elev, shape_constraints, hard, *,
                                    receiver_nodes=None, n_nodes=None,
                                    flat_groups=None, group_bounds=None,
                                    forensics=None, probe_out=None, **kw):
    """THE PROJECTION PARTITIONS — airside first, groundside after
    (docs/specs/cycle8-one-graph-spec.md ADDENDUM; derives from the
    owner's receiver-only law, RULINGS 2026-08-06 "ONE graph" clause 2 and
    the standing "airside is king").

    A SHARED PROJECTION IS A COUPLING.  Holding groundside pairs in the
    same constraint set as airside lets an over-cap mouth or lot edge
    SPLIT its excess across both endpoints — the airside one included —
    which is how a groundside round moved airside rows (+6 SPJC / +5 HECA,
    the cycle-7 Q4 debt).  Receiver-only is therefore made STRUCTURAL:

      1. AIRSIDE PASS — every pair with no receiver endpoint, projected
         exactly as before.  No groundside value is in this constraint
         set at all, so none can move an airside node.
      2. GROUNDSIDE PASS — the pairs the first pass excluded, with EVERY
         non-receiver node frozen (``hard``).  The airside values the
         first pass settled are data here, never variables: the mouth is
         seated by airside and the road grades from it, which is the
         mouth ruling in constraint form.

    Freezing the whole non-receiver set (not merely the endpoints of
    mixed pairs) is deliberate: the reach-band clamp inside
    ``feasibility_project`` runs over EVERY movable node, so a
    partially-frozen airside would still be re-clamped by the groundside
    pass — a second author on airside values.

    The measured-worse alternative (running the groundside seats AFTER
    the final projection, 434 → 493 airside at SPJC) is FORBIDDEN by the
    spec addendum; the partition is the ruled cure.

    ``receiver_nodes`` empty/None ⇒ ONE call, byte-identical to
    ``feasibility_project``.  Returns the same ``(remaining_over_cap,
    both_hard)`` pair, summed over the two passes so the exit report
    still counts every violated edge exactly once (the two edge sets
    PARTITION the input).

    ROAD PAIR LAW IS RECEIVER-PASS LAW (default, no gate): the ROAD
    shapes' pair entries are moved out of the AIRSIDE pass into the
    receiver pass, where airside is frozen — every road route EDGE stays
    in the graph, only the road's own pair LAW stops binding airside
    values.  A welded road's role is not groundside, so the receiver
    partition above does not catch it; without this step the road's law
    would author airside values, which is the pull-back the ONE-graph
    ruling forbids.  See ``_withhold_road_pair_law``.

    PROBE GATE, DEFAULT OFF — ``O4_PROBE_ROAD_PAIR_LAW_AIRSIDE=1``
    RESTORES THE OLD FORM (road pair law enforced in the airside pass).
    It exists so the comparison the receiver-only default was ruled on
    stays one env var away; nothing in production sets it.
    """
    if not receiver_nodes:
        _kw0 = dict(kw)
        _kw0.pop("apron_interior_pairs", None)
        _kw0.pop("staged_report", None)
        return feasibility_project(elev, shape_constraints, hard,
                                   flat_groups=flat_groups,
                                   group_bounds=group_bounds,
                                   forensics=forensics, probe_out=probe_out,
                                   **_kw0)
    givers, receivers = partition_constraints_by_receiver(
        shape_constraints, receiver_nodes)
    if _os.environ.get("O4_PROBE_ROAD_PAIR_LAW_AIRSIDE") != "1":
        # THE STAGE PARTITION (S1b) subsumes the road-pair withholding:
        # every ROAD_ROLES entry is groundside-tagged at mint, so the
        # entries the predecessor moved are a strict SUBSET of the ones
        # moved here.  The probe gate still restores the pre-partition
        # form for the M1 comparison arm.
        givers, receivers = _partition_by_stage(
            givers, receivers, "feasibility_project_partitioned")
    # ── THE PARTITION COVERS BOUNDS, NOT ONLY PAIRS (c9air) ───────────
    # A groundside PIN CEILING (``gs_pin_nodes``: weld datum + one throat
    # of reach, authored by the lot) reaches airside through a SHARED
    # node — a mouth vertex carrying an airside role is a GIVER, so its
    # pairs stay in this pass while its groundside-authored box came
    # along in ``node_bounds`` and clamped it here.  The band/box merge
    # only rules BAND WINS on a DECLARED CONFLICT (empty intersection);
    # a ceiling that merely TIGHTENS the airside band was never a
    # conflict and bound airside silently.  Owner law is unconditional —
    # "groundside must have ZERO effect or pull on airside" (RULINGS
    # 2026-07-30 airside-is-king; 2026-08-06 the mouth is seated where
    # the airside apron can meet it, and the road grades from that seat)
    # — so the airside pass drops every groundside-pin bound on a
    # non-receiver node.  Receivers keep theirs: pass B IS groundside law.
    _kw_air = kw
    _pins = kw.get("gs_pin_nodes") or ()
    _nb = kw.get("node_bounds")
    if _nb and _pins:
        _pin_set = {int(i) for i in _pins}
        _drop = {i for i in _nb
                 if i in _pin_set and i not in receiver_nodes}
        if _drop:
            _kw_air = dict(kw)
            _kw_air["node_bounds"] = {i: b for i, b in _nb.items()
                                      if i not in _drop}
            import O4_UI_Utils as _UI_part
            _UI_part.vprint(
                1, f"    [partition] airside pass: {len(_drop)} "
                   f"groundside-pin ceiling(s) withdrawn from "
                   f"{len(_nb)} node bound(s) (airside is king — a "
                   f"non-receiver node never carries a lot-authored "
                   f"box); {len(_nb) - len(_drop)} kept")
    # ── STAGE A HAS NO GROUNDSIDE VARIABLES (S1b) ─────────────────────
    # Withholding groundside ENTRIES is only half the law: the reach-band
    # clamp inside ``feasibility_project`` runs over EVERY MOVABLE NODE,
    # so a groundside node with no pair in this pass was still an airside
    # variable being written by the airside pass — the mirror image of
    # the freeze the groundside pass already applies to airside
    # (``hard_recv`` below), and the same reason that freeze is built
    # explicitly rather than inferred from "it has no edges here".
    # Every receiver node is a stage-B node by construction
    # (``solve._receiver_nodes_from_roles``), and stage B re-frees them
    # against frozen airside values, so nothing loses its author.
    hard_air = set(hard)
    hard_air.update(receiver_nodes)
    # ── THE APRON STAGED SOLVE (spec apron-staged-solve-spec.md §2) ────
    # Stage A runs the apron in TWO sub-stages, reusing exactly the frozen-
    # set mechanism the airside/groundside partition below uses.
    #   A1 SENIOR: strict pairs + transect rows + spine/runway law.  The
    #      interior nodes are FREE (they may absorb senior residue) but
    #      carry NO law edges of their own — their 5 % pairs are withheld.
    #   A2 INTERIOR: seniors FROZEN as data, interior pairs projected,
    #      interior nodes the only movers.
    # Measured basis (lane/compose v1-v3): no violation anywhere is priced
    # at 5 %, yet freeing the interior worsens the strict class
    # monotonically — the single Jacobi/POCS sweep spreads pinned
    # contradictions onto whatever is free, and a freer interior lets more
    # of it land on the movement surfaces.  Precedence is the cure, not a
    # cap.  NO BAND IS REBUILT HERE: ``env_band`` rides through kw exactly
    # as it does for the two passes below, because a band rebuilt after the
    # crown field publishes double-lifts crowned seeds by one crown (the
    # R8-2 writeback-band defect, 2026-08-11).
    _interior = kw.get("apron_interior_pairs") or ()
    _staged = bool(_interior) and _APRON_STAGED_SOLVE
    _kw_air = dict(_kw_air)
    _kw_air.pop("apron_interior_pairs", None)
    _kw_air.pop("staged_report", None)
    if not _staged:
        rem_a, bh_a = feasibility_project(
            elev, givers, hard_air, flat_groups=flat_groups,
            group_bounds=group_bounds, forensics=forensics,
            probe_out=probe_out, **_kw_air)
    else:
        g_senior, g_interior = _split_apron_interior(givers, set(_interior))
        rem_a, bh_a = feasibility_project(
            elev, g_senior, hard_air, flat_groups=flat_groups,
            group_bounds=group_bounds, forensics=forensics,
            probe_out=probe_out, **_kw_air)
        _report = kw.get("staged_report")
        if isinstance(_report, dict):
            _report["a1_over_cap"] = int(rem_a)
            _report["a1_both_hard"] = int(bh_a)
        if g_interior:
            _n_st = int(n_nodes if n_nodes is not None else len(elev))
            # INTERIOR NODES ARE THE ONLY MOVERS — and "interior" is the
            # SENIORITY PARTITION's answer, not "an endpoint of an interior
            # pair".  An interior pair may well touch a SENIOR node (a 5 %
            # chord from a frontage vertex into the ramp is exactly that),
            # and taking its endpoints as movers un-freezes the senior and
            # lets A2 undo A1 — measured on the first pass of this twin,
            # where node 1 went back from its A1 value of 1.0 to 10.0.
            # ONE function decides it (spec section 3), fed with the pairs
            # the law already classified: everything still carrying senior
            # law after the split is a strict pair, and the transect rows
            # ride with the senior half.
            from auto_patch import grade_law as _GLsen
            _cand, _strict_p, _tx = set(), [], set()
            for sc in g_interior:
                for e in (sc.get("edges") or ()):
                    if isinstance(e[0], int) and isinstance(e[1], int):
                        _cand.add(int(e[0]))
                        _cand.add(int(e[1]))
            for sc in g_senior:
                for e in (sc.get("edges") or ()):
                    if isinstance(e[0], int) and isinstance(e[1], int):
                        _strict_p.append((int(e[0]), int(e[1])))
                for _h in (sc.get("hyper") or ()):
                    try:
                        _tx.update(int(_i) for _i in _h[0])
                    except Exception:
                        pass
            _seniority = _GLsen.apron_node_seniority(_cand, _strict_p, _tx)
            _mov = {i for i, v in _seniority.items()
                    if v == _GLsen.APRON_INTERIOR}
            _senior_frozen = _cand - _mov
            # Built explicitly, like ``hard_recv`` below and for the same
            # reason: the reach-band clamp inside ``feasibility_project``
            # runs over every movable node, so "it has no edges here" would
            # not freeze a senior.
            hard_int = set(hard_air)
            hard_int.update(i for i in range(_n_st) if i not in _mov)
            _a1_vals = {i: float(elev[i]) for i in range(_n_st)
                        if i not in _mov}
            rem_i, bh_i = feasibility_project(
                elev, g_interior, hard_int, forensics=forensics,
                probe_out=probe_out, **_kw_air)
            # A SENIOR NODE MOVING IN A2 IS A STOP (spec, last paragraph).
            _moved = [i for i, v in _a1_vals.items()
                      if abs(float(elev[i]) - v) > 1e-9]
            import O4_UI_Utils as _UI_st
            _UI_st.vprint(
                1, f"    [apron-staged] A1 over_cap={rem_a} "
                   f"(both-hard {bh_a}) | A2 over_cap={rem_i} "
                   f"(both-hard {bh_i}); interior movers={len(_mov)}, "
                   f"frozen non-movers={_n_st - len(_mov)}, "
                   f"senior nodes re-frozen in A2={len(_senior_frozen)}, "
                   f"senior nodes MOVED in A2={len(_moved)}")
            if isinstance(_report, dict):
                _report["a2_over_cap"] = int(rem_i)
                _report["a2_both_hard"] = int(bh_i)
                _report["interior_movers"] = len(_mov)
                _report["senior_moved"] = len(_moved)
            if _moved:
                raise AssertionError(
                    f"APRON STAGED SOLVE: {len(_moved)} SENIOR node(s) moved "
                    f"in the interior pass (worst "
                    f"{max(abs(float(elev[i]) - _a1_vals[i]) for i in _moved):.4f}"
                    f" m at node {_moved[0]}) — the freeze is wrong; fix the "
                    f"freeze, never the count (spec, pre-delegated STOP)")
            rem_a += rem_i
            bh_a += bh_i
    if not receivers:
        return rem_a, bh_a
    n = int(n_nodes if n_nodes is not None else len(elev))
    # FROZEN AIRSIDE: everything that is not a receiver is immovable for
    # the groundside pass.  Building the set explicitly (rather than
    # trusting "it has no edges here") is what makes the freeze cover the
    # band clamp as well as the sweeps.
    hard_recv = set(hard)
    hard_recv.update(i for i in range(n) if i not in receiver_nodes)
    # No flat groups in the receiver pass: a pad is never a receiver, so
    # every group is fully frozen above — passing them would only re-do
    # the merge and re-broadcast values that cannot move.
    _kw_b = dict(kw)
    _kw_b.pop("apron_interior_pairs", None)
    _kw_b.pop("staged_report", None)
    rem_b, bh_b = feasibility_project(elev, receivers, hard_recv, **_kw_b)
    return rem_a + rem_b, bh_a + bh_b


def feasibility_project(elev, shape_constraints, hard, *,
                        max_iters=None,
                        tol=1e-3, force_scalar=False,
                        flat_groups=None, broken_out=None, pre_broken=None,
                        edge_couple_nodes=None, interval_yield_from=None,
                        group_bounds=None, node_bounds=None,
                        gs_pin_nodes=None,
                        forensics=None,
                        witness_limited=None, witness_excluded=None,
                        env_band=None, family_of=None,
                        sweep_hard_cap=None,
                        probe_out=None, declared_out=None):
    """Drive EVERY grade-graph edge to ``|Δelev| ≤ budget`` by iterative
    constraint projection (user 2026-06-25: nothing may violate a grade cap).

    This is a Gauss-Seidel relaxation of the difference-constraint system
    ``|z_i − z_j| ≤ cap_ij·d_ij`` on the SAME graph the validator checks
    (``shape_constraints`` = ``grade_graph``).  ``hard`` nodes (buildings, runway,
    seams) are immovable; everything else — including the route SKELETON — may
    flex.  An over-cap edge moves its free endpoint(s) just enough to satisfy it
    (split the excess when both are free, all of it onto the free one otherwise);
    repeated sweeps converge to a cap-Lipschitz surface whenever the anchors admit
    one.  Edges between two hard nodes are genuinely infeasible and reported, not
    forced.  Mutates ``elev`` in place; returns ``(remaining_over_cap, both_hard)``.

    RAW LAW BUDGETS: the sweeps, the reach envelope, the break detection and
    the returned over-cap tally ALL run on the raw law budget — one frame,
    no margin term (the emit-quantization margin is retired; see the
    module-head note).  The 0.01 m emit guarantee lives in
    :mod:`auto_patch.emit_snap`.

    ``max_iters`` — the sweep budget, a NON-TERMINATION GUARD.  Leave it
    ``None`` (the default, and what every production call site does) and it
    is DERIVED from this projection's own graph by
    :func:`derive_sweep_budget`, so it is provably above the sweeps the
    graph can need and can never be the thing that decides the surface.
    Passing an int overrides the derivation (tests, and any call that
    deliberately bounds a probe).

    ``flat_groups`` — optional list of node-index sets, each a RIGID FLAT group
    (a building pad): its members share ONE elevation that the projection may
    move as a unit (the feasibility-audit model — buildings are movable flat
    groups; holding every pad hard at its pre-picked seat makes the polytope
    infeasible through chained paths even when no single edge is both-hard).
    Each group collapses to a representative node; member↔member edges vanish,
    member↔outside edges re-anchor to the representative with their own budget,
    and the representative's final level is broadcast back to all members.  A
    group containing a ``hard`` node stays entirely hard (never moved).

    ``broken_out`` — optional set the caller passes to receive the BROKEN
    node indices this call quarantined (genuine anchor contradictions,
    blended + immovable — see below).  ``pre_broken`` — node indices to
    quarantine AT THEIR CURRENT VALUES in addition to the envelope's own
    detections (scoped final projection, user 2026-07-05: the solve's FULL
    graph proved these nodes sit in infeasible pockets; the scoped graph's
    sparser envelope can miss the contradiction and the worklist then grinds
    POCS on the infeasible subsystem to the visit cap, smearing the pocket —
    the exact failure the broken quarantine exists to prevent).  Quarantining
    extra nodes is always law-safe: their over-cap pairs are reported, never
    hidden.

    ``witness_limited`` — ``(node_indices, horizon)``: anchors whose FEASIBILITY-
    WITNESS role is bounded (owner ruling 2026-07-30, memory
    ``groundside-terrace-law``: "groundside values never act as a feasibility
    witness — floor or ceiling — for airside pavement beyond the Part-C mouth
    allowance").  They stay HARD (immovable for the sweeps, so groundside is
    still pinned and every mouth-weld law edge is still enforced) but seed the
    reach envelope only within ``horizon`` metres of BUDGET distance — the
    Part-C mouth allowance expressed in the envelope's own metric.  Beyond the
    throat they contribute nothing to any node's ``[floor, ceiling]`` and so can
    no longer declare a break.  ``None`` ⇒ the single unrestricted envelope pass
    (byte-identical to the pre-clause code).

    ``witness_excluded`` — NON-ROUTE SEED ADMISSION (spec
    ``docs/specs/route-metric-envelope-spec.md`` §2, owner ruling
    2026-07-30 "reach follows centerlines", escalated 2026-08-01).  A hard
    anchor whose node carries NO route-pavement role — its patch roles lie
    entirely inside the ``ROLE_GRADE_LIMITS is None`` family
    (``graded_strip``, ``retaining_wall``, ``runway_clearance``,
    ``taxiway_clearance``, ``ols_cut``, ``boundary``) plus
    ``groundside_pavement`` — MAY NOT SEED the airside feasibility
    envelope, in ANY pass.  Such an anchor is a terrain TRACE welded to
    pavement, not a point on a taxi route: letting it witness is what
    makes a 2.6 km strip vertex declare an apron infeasible.
    Mechanically this is ``witness_limited`` with a zero horizon and no
    re-seeding pass — the anchors are simply removed from the envelope
    seed set.  They stay HARD for the sweeps (their own value and every
    law edge to them is still enforced) and they still anchor their own
    vertex: this clause changes WITNESSING, never VALUES.
    ``None``/empty ⇒ byte-identical to the pre-clause code.

    ``group_bounds`` / ``node_bounds`` — BOUNDED YIELD (owner ruling
    2026-07-29: "Any yield absolutely needs to stay within the feasibility
    box").  ``group_bounds`` is a list parallel to ``flat_groups``: entry k
    is the ``(lo, hi)`` interval group k's rigid level may take (``None`` =
    unbounded); merged groups intersect their boxes.  ``node_bounds`` is
    ``{node_idx: (lo, hi)}`` for individually freed nodes.  A bounded node
    clamps to its box at seed and after every step that moves it, so a
    yielded seat can never be dragged outside the reach-band interval it
    was seated from — a conflict that exceeds a box surfaces as a remaining
    over-cap edge in the final tally instead of burying the seat (HECA
    building199: seated 101.13, parked at 87.94 by the unbounded yield).
    A box is a refinement of the yield, never a new hold: immovable nodes,
    group members (the representative carries the value) and contradictory
    (``lo > hi``) boxes are dropped.  ``None`` for both = today's behavior,
    byte-identical.

    ``gs_pin_nodes`` — the node indices whose ``node_bounds`` entry carries
    a freed GROUNDSIDE PIN's LAW ceiling (weld datum + one throat of reach).
    Read at ONE site: the band/box merge, where a DECLARED CONFLICT between
    the airside reach band and a groundside pin box is resolved BAND WINS —
    the pin box yields, its ceiling re-derived from the airside-conformed
    datum (cycle-6 Part P; standing law "airside is king", the lot conforms
    via the terrace/wall machinery).  A conflict on any other box class is
    reported UNRESOLVED and keeps today's behaviour.  ``None``/empty ⇒ every
    conflict is UNRESOLVED, i.e. byte-identical to the pre-clause code apart
    from the (ungated) report.

    NO REFERENCE RODS.  The §7 reference channel (``group_refs`` /
    ``node_refs``, the proximal pull and the exact-return polish) was
    RETIRED in the build-complete-then-debug round: least displacement
    from a reference field is not a law, and the field was a second
    surface authority next to the caps.  A movable node is plain free —
    it settles wherever the caps, the boxes and the envelope admit — and
    the forensics that used to price displacement live on as
    ``solve._spine_yield_movement_report``.

    ``env_band`` — THE REACH BAND, one entry per node (``(floor, ceiling)``
    or ``None``), in THIS call's elevation space (owner ruling 2026-07-30,
    spec ``envelope-uses-the-centerline-graph``; gate
    ``O4_ENVELOPE_FROM_BAND`` / ``O4_ROUTE_METRIC_ENVELOPE``, ONE default
    ``"0"`` — see ``envelope_from_band_enabled``).  When supplied it is the SOURCE
    of the feasibility interval — both the break declaration and the clamp
    below — replacing the transitive closure over the within-shape pavement
    PAIR graph.  The caller hands in the band the build ALREADY computed
    (``building_feasibility.reach_band_unified`` via ``anchors.node_bands``,
    the same object ``build_building_seats`` and ``route_band_violations``
    consume): nothing is re-derived and no second graph is built
    (``single-pass-principle``).

    *Why.*  The pair closure answers a reach-shaped question with pavement
    adjacency: its argmin binding path at HECA is 119 pavement vertices /
    5,349 m crossing 14 rigid-flat pads at ZERO budget — "neither KML
    represents any sort of route an aircraft could take" (owner).  It is
    also seeded from EVERY hard node, so ``gs_pin``/``pad_detached_dem``
    (that class is retired — item 3(b))/
    terrain pins declare airside infeasible; the band is seeded from
    ``G.runway_anchor`` alone over non-service spine routes.  Measured
    replay (HECA 2026-07-30): broken 13,428 → 0 at fp#8, 9,991 → 0 and
    7,634 → 0 at the two final passes, with ZERO band inversions and zero
    newly-broken nodes — while 11,109 band-feasible fp#8 nodes were
    emitting BELOW their own band floor under the closure.

    *Off-net ⇒ NOT broken.*  A node the band cannot answer for (``None``)
    is left to the LOCAL within-shape law — the tree's own documented
    contract in ``reach_band_unified``, ``one_profile_solve.node_band`` and
    ``route_band_violations``.  The opposite default triples the quarantine
    (42,008 nodes, measured).

    *The clamp moves with the declaration.*  The non-broken branch's
    ``elev[i] = min(max(elev[i], lo), hi)`` used the SAME closure interval;
    for the 13,056 nodes the band frees that interval is still empty and
    the clamp collapses to ``hi``, pinning them anyway.  Re-sourcing only
    the break predicate is NOT isolable, so both read ``env_band``.

    This bounds FEASIBILITY only.  Every pair constraint still enforces in
    the sweeps and in the final RAW-budget tally (which never reads
    ``broken``); the local apron/taxi/visible-geodesic laws are untouched.
    ``None`` (or gate off) = the pair-closure envelope, byte-identical.

    ``family_of`` — THE FAMILY AXIS (cycle-7 fix 5), WRITE-ONLY.  The
    ``{(min(a,b), max(a,b)): family}`` map in ORIGINAL node space
    (``grade_graph.UnifiedGraph.family_by_pair``).  This call re-keys it
    into its OWN remapped space as it reads each raw edge — while the
    original endpoints are still in hand — so an uncertified exit can say
    WHICH LAW it could not close, including on edges whose endpoint was
    aliased into a flat-group representative (the class that carried the
    worst residual of the whole HECA solve and had no name at all).
    Nothing in the projection reads it back; ``None`` allocates nothing
    and the exit report is unchanged.

    ``sweep_hard_cap`` — the projection's absolute sweep ceiling
    (cycle-7 fix 1).  ``None`` + a derived ``max_iters`` ⇒
    ``config.SWEEP_BUDGET_MAX``, the anti-hang guard; ``None`` + an
    IMPOSED ``max_iters`` ⇒ the imposed number is both block and
    ceiling, i.e. exactly the pre-fix behaviour.  Naming both is how the
    replay ladder asks for "this block, that ceiling".

    ``probe_out`` — WRITE-ONLY measurement out-parameter (the ``broken_out``
    idiom; docs/specs/taut-string-probe-spec.md §1, probe A).  When a dict
    carrying a ``"watch"`` key of node indices is passed, this call copies
    ``{i: elev[i] for i in watch}`` into ``probe_out["post_blend"]`` at the
    BLEND/SWEEP boundary — after the reach envelope's clamp + break blend,
    before any sweep moves a node — so the caller can attribute a watched
    node's move to the blend half or the sweep half of THIS call.  Nothing
    is read back and ``elev`` is never written through it; ``None`` (the
    production default) allocates nothing and is byte-identical.

    ``declared_out`` — WRITE-ONLY out-parameter (the same idiom) for fix
    arm §2's DECLARED HARD CONFLICTS: a list the caller passes to receive
    one row per ``(node, low author, high author)`` triple whose hard-
    neighbour interval is EMPTY under ``O4_HARD_NEIGHBOUR_BOUND=1``.  The
    node keeps whatever its own law put it at; the row is the ruling's
    "declared conflict, author-carrying" channel and is never read back.
    ``None`` ⇒ the rows are computed under the gate and dropped.
    """
    import heapq
    n = len(elev)

    # ── flat groups → representative mapping ─────────────────────────────
    gmap: dict = {}
    groups_eff: list = []
    rep_bounds: dict = {}       # representative -> group feasibility box
    if flat_groups:
        # merge overlapping groups (two touching pads sharing a ring node act
        # as one rigid unit), then map member → representative.  BOUNDED
        # YIELD: each group's box rides the merge (intersection — the merged
        # unit must satisfy every constituent box; a group without a box
        # bounds nothing).
        pool = [set(g) for g in flat_groups if g]
        pool_bounds = ([b for g, b in zip(flat_groups, group_bounds) if g]
                       if group_bounds else [None] * len(pool))
        merged: list = []
        merged_bounds: list = []
        for pool_index, g in enumerate(pool):
            attached = None
            for merged_index, mg in enumerate(merged):
                if mg & g:
                    mg |= g
                    merged_bounds[merged_index] = _box_isect(
                        merged_bounds[merged_index], pool_bounds[pool_index])
                    attached = mg
                    break
            if attached is None:
                merged.append(set(g))
                merged_bounds.append(pool_bounds[pool_index])
        for merged_index, g in enumerate(merged):
            g = {i for i in g if 0 <= i < n}
            if len(g) < 2:
                continue
            if g & hard:
                continue                      # runway/seam-welded pad: stays hard
            rep = min(g)
            groups_eff.append((rep, g))
            mb = merged_bounds[merged_index]
            if mb is not None and mb[0] <= mb[1]:
                rep_bounds[rep] = (float(mb[0]), float(mb[1]))
            for m in g:
                if m != rep:
                    gmap[m] = rep
        # a skipped (hard-welded) group must stay rigid: hold all its members.
        hard = set(hard)
        for g in merged:
            g = {i for i in g if 0 <= i < n}
            if len(g) >= 2 and (g & hard):
                hard |= g
        # seed each representative at the group's current (flat) level.
        for rep, g in groups_eff:
            elev[rep] = sum(elev[m] for m in g) / len(g)

    def _r(i):
        return gmap.get(i, i)

    # ── FLATNESS-CERTIFIED LAZY SHAPES (user 2026-07-05 flatness tier) ───
    # A certified entry carries only its O(n) ring-adjacent pairs eagerly;
    # its O(n²) body pairs are proven satisfied AT THE DEM SEED
    # (``solver_primitives._certify_flat_shape``).  Soundness invariant: the
    # moment any of the shape's nodes moves off that seed — BEFORE this call
    # (checked right here) or DURING it (checked in the scalar worklist /
    # after each vectorised pass) — the full pair set is generated and
    # enforced exactly like an eager shape's.  Expansion mutates the entry in
    # place (full edges merged, lazy keys dropped), so every LATER projection
    # call sees the expanded set too.  Final state either way: every
    # generated edge satisfied + every never-expanded shape satisfied by its
    # certificate ⇒ the same law coverage as eager generation.
    def _lazy_nodes_moved(entry):
        # A flat-group member's live value is carried by its REPRESENTATIVE
        # during this call (members are only broadcast back at the end), so
        # the effective elevation to compare against the certificate seed is
        # ``elev[_r(node_index)]``.
        # The movement tolerance is the certificate's SLACK-AWARE bound
        # (user 2026-07-05 tuning): certified pairs sit at ≤ 0.6·rate·d,
        # so both endpoints may drift 0.2·rate·d_min before any body pair
        # can reach its budget — mm-scale smoothing nudges no longer
        # expand every certificate.  Entries from older callers without
        # the field keep the strict 1e-6.
        movement_tolerance = entry.get("lazy_move_tolerance", 1e-6)
        for node_index, seed_value in zip(entry["lazy_nodes"],
                                          entry["lazy_seed"]):
            if 0 <= node_index < n and \
                    abs(elev[_r(node_index)] - seed_value) \
                    > movement_tolerance:
                return True
        return False

    def _expand_lazy_entry(entry):
        """Generate the entry's FULL pair set and merge it in; the lazy keys
        are dropped, so the entry is an ordinary eager entry from now on
        (``lazy_certified`` stays as the hit-rate marker).  A thunk failure
        PROPAGATES: a lazy bookkeeping error must never silently skip
        constraints, and the thunk is the same generation call the eager
        path would have made — it cannot be worked around, only heard."""
        thunk = entry.pop("lazy_expand")
        entry.pop("lazy_nodes", None)
        entry.pop("lazy_seed", None)
        entry.pop("lazy_move_tolerance", None)
        full_edges = list(thunk())
        # Ring pairs come back again inside the full set — the
        # min-budget-wins dedup below absorbs the duplicates.
        entry["edges"] = list(entry["edges"]) + full_edges
        return full_edges

    lazy_entries_pending = []
    for sc in shape_constraints:
        if sc.get("lazy_expand") is None:
            continue
        if _lazy_nodes_moved(sc):
            # Pre-call movement (an earlier pass moved a node off its seed):
            # expand NOW, before edge_lim is built, so the full set flows
            # through the ordinary min-budget-wins pipeline.
            _expand_lazy_entry(sc)
        else:
            lazy_entries_pending.append(sc)

    # TIGHTEST budget wins across duplicate (remapped) pairs.  Every raw edge
    # is a constraint that must hold, so when several land on the same index
    # pair the binding one is the minimum.  This matters most under
    # ``flat_groups``: the group collapse aliases MANY physical chords (every
    # pad-ring vertex ↔ one apron node, budgets spanning 10-25×) onto ONE
    # representative pair — first-edge-wins enforced an arbitrary (usually
    # loose) budget while the validator checks each physical chord at its own
    # allowance (SPJC round 4: 138 of the 153 residual law-true violations
    # were exactly this; min-wins takes SPJC to 0).
    # SIGNED INTERVAL EDGES (Stage B0, docs/slice_b_solver_absorption_
    # design.md): an edge is either the SYMMETRIC 3-tuple ``(i, j, budget)``
    # (``|z_i − z_j| ≤ budget``) — the existing fast path, its arithmetic left
    # literally untouched below — or the INTERVAL 4-tuple ``(i, j,
    # interval_low, interval_high)`` (``interval_low ≤ z_i − z_j ≤
    # interval_high``, either side ``None`` = unbounded).  Interval edges are
    # collected into ``interval_lim`` and enforced by a SEPARATE projection
    # path; symmetric edges flow through ``edge_lim`` exactly as before.  With
    # every terrain gate off no interval edge is produced, so ``interval_lim``
    # stays empty and the whole interval apparatus below is inert — the
    # symmetric solve is byte-identical to today.
    edge_lim: dict = {}
    interval_lim: dict = {}          # canonical pair (a<b) -> (low, high)
    # ENVELOPE-SKIP entries (spec §10 interval rod): an entry flagged
    # ``envelope_skip`` keeps its interval edges OUT of the reach-envelope
    # adjacency below — a signed slab whose |Δ| exceeds ε injects NEGATIVE
    # directed weights, and ``_reach`` is a Dijkstra (the lazy-re-expand
    # blowup class; the EAT one-sided edges were retired for exactly
    # this).  Skipping is law-safe: the sweep still enforces every skipped
    # slab; only the one-shot warm start / break detection loses those
    # (spine nodes keep their symmetric-edge envelope).  No flagged entry
    # ⇒ empty set ⇒ byte-identical.
    envelope_skip_pairs: set = set()
    # ── THE FAMILY AXIS, BUILT IN THE REMAPPED SPACE (cycle-7 fix 5) ─────
    # ``family_of`` is the ORIGINAL-node-space ``{(min,max): family}`` map
    # (``grade_graph.UnifiedGraph.family_by_pair``).  The projection works
    # on REMAPPED pairs, so a physical chord ``(pad-ring member, apron
    # node)`` becomes ``(representative, apron node)`` and no longer keys
    # into that map — which is exactly why the worst residual of the whole
    # HECA solve had no family name (c6attr dossier §3.2).  The map is
    # therefore re-keyed HERE, as each raw edge is read and while its
    # ORIGINAL endpoints are still in hand: entry tag first, per-edge
    # ``family_of`` lookup only for the catch-all construction-site tags,
    # FIRST mint wins (a remapped pair several physical chords alias onto
    # is named by one of them either way — the certificate is a report).
    # ``family_of=None`` ⇒ not one dict store happens and the exit report
    # reads exactly as it did before.
    fam_by_pair: dict = {} if family_of is not None else None
    for sc in shape_constraints:
        _sc_env_skip = bool(sc.get("envelope_skip"))
        _sc_fam = None
        if fam_by_pair is not None:
            _sc_fam = _entry_family_tag(sc)
            _sc_fam_per_edge = _sc_fam in _CATCH_ALL_FAMILY_TAGS
        for edge in sc["edges"]:
            if len(edge) >= 4:
                # INTERVAL EDGE — signed slab on ``z_i − z_j``.
                i, j, raw_low, raw_high = (edge[0], edge[1],
                                           edge[2], edge[3])
                if raw_low is None and raw_high is None:
                    continue         # unregulated (both sides open)
                if i >= n or j >= n:
                    continue
                _oa, _ob = (i, j) if i <= j else (j, i)
                i, j = _r(i), _r(j)
                if i == j:
                    continue
                if fam_by_pair is not None:
                    # KEYED BY KIND (cycle-7, fix-4 attribution): the same
                    # remapped pair legitimately carries BOTH a symmetric
                    # cap (from a junction/apron shape) and a signed SLAB
                    # (from the zone law or a rod), minted by DIFFERENT
                    # constructors and enforced as two separate edges.  A
                    # pair-only key let whichever entry was read first name
                    # both, which reported 2,038 adjacent-ground slabs as
                    # ``junction:-`` — a slab-class decomposition that is
                    # simply wrong.  The kind is part of the identity.
                    _key = ((i, j) if i < j else (j, i)) + (True,)
                    if _key not in fam_by_pair:
                        fam_by_pair[_key] = (
                            family_of.get((_oa, _ob), _sc_fam)
                            if _sc_fam_per_edge else _sc_fam)
                if _sc_env_skip:
                    envelope_skip_pairs.add((i, j) if i < j else (j, i))
                if i < j:
                    pair, low, high = (i, j), raw_low, raw_high
                else:
                    # flipping the pair negates the difference: for (j, i),
                    # z_j − z_i ∈ [−raw_high, −raw_low] (a ``None`` bound maps
                    # to the opposite open side).
                    pair = (j, i)
                    low = None if raw_high is None else -raw_high
                    high = None if raw_low is None else -raw_low
                previous = interval_lim.get(pair)
                if previous is None:
                    interval_lim[pair] = (low, high)
                else:
                    # TIGHTEST wins per side (min-budget-wins analogue for a
                    # signed slab): intersect the intervals — the larger floor
                    # and the smaller ceiling, treating ``None`` as ∓∞.
                    prev_low, prev_high = previous
                    new_low = (low if prev_low is None
                               else low if (low is not None and low > prev_low)
                               else prev_low)
                    new_high = (high if prev_high is None
                                else high if (high is not None
                                              and high < prev_high)
                                else prev_high)
                    interval_lim[pair] = (new_low, new_high)
                continue
            # SYMMETRIC EDGE — existing tightest-budget-wins, untouched.
            i, j, lim = edge
            if lim is None or lim < 0 or i >= n or j >= n:
                continue
            _oa, _ob = (i, j) if i <= j else (j, i)
            i, j = _r(i), _r(j)
            if i == j:
                continue
            e = (i, j) if i < j else (j, i)
            if fam_by_pair is not None and (e + (False,)) not in fam_by_pair:
                fam_by_pair[e + (False,)] = (
                    family_of.get((_oa, _ob), _sc_fam)
                    if _sc_fam_per_edge else _sc_fam)
            prev = edge_lim.get(e)
            if prev is None or lim < prev:
                edge_lim[e] = lim
    if not edge_lim and not interval_lim:
        return 0, 0
    # ONE LAW FRAME (the emit-quantization margin is retired — module-head
    # note).  The SWEEP, the reach envelope, the break detection and the
    # final TALLY all run on the RAW law budget, so the enforced system and
    # the reported system are the same system by construction.  ``edges``
    # keeps its ``(i, j, raw_budget, sweep_budget)`` shape — the two columns
    # now carry equal values — because it is the seam every consumer reads
    # and collapsing it is a separate change.
    edges = []
    adj: dict = {}
    # DIRECTED reach-envelope adjacencies (Stage B3, interval-aware envelope).
    # ``ceil_radj[k]`` / ``floor_radj[k]`` = ``[(j, w), ...]`` where the reach
    # relaxation is ``t_j := t_k + w`` (the sign is BAKED INTO the weight, so
    # both envelopes share one relaxation form and interval edges — whose
    # ceiling-forward and floor-forward weights are INDEPENDENT — embed
    # directly).  For a SYMMETRIC budget the ceiling weight is ``+lim`` both
    # ways and the floor weight ``−lim`` both ways, so with NO interval edge
    # present these reproduce the old single-``adj`` ``t + sign·lim`` /
    # ``dk + lim`` arithmetic BIT-FOR-BIT (``−1·lim`` and ``−lim`` are the
    # identical IEEE negation; ``|−lim| = lim``) — the gates-off byte-identity
    # gate.  ``adj`` (symmetric) is kept unchanged for ``_hard_neighbour_
    # interval`` below, which models symmetric welded neighbours only.
    ceil_radj: dict = {}
    floor_radj: dict = {}
    for (i, j), lim in edge_lim.items():
        sweep_lim = lim                     # RAW law budget — no margin
        edges.append((i, j, lim, sweep_lim))
        adj.setdefault(i, []).append((j, sweep_lim))
        adj.setdefault(j, []).append((i, sweep_lim))
        ceil_radj.setdefault(i, []).append((j, sweep_lim))
        ceil_radj.setdefault(j, []).append((i, sweep_lim))
        floor_radj.setdefault(i, []).append((j, -sweep_lim))
        floor_radj.setdefault(j, []).append((i, -sweep_lim))
    # INTERVAL EDGES (Stage B0): each carries the RAW interval twice — the
    # tally frame and the sweep frame are the SAME raw law interval now that
    # the margin is retired.  ``interval_edges`` items: ``(i, j, raw_low,
    # raw_high, sweep_low, sweep_high)`` with ``i < j`` and the slab on
    # ``z_i − z_j``.
    #
    # DIRECTED ENVELOPE PROPAGATION (Stage B3): a signed slab
    # ``low ≤ z_i − z_j ≤ high`` is the directed generalisation of the
    # symmetric budget and contributes to the envelope exactly as its two
    # implied inequalities do (``None`` side ⇒ that direction imposes no
    # bound, so the edge is skipped there):
    #   ceiling:  z_i ≤ z_j + high  ⇒  ceil_i ≤ ceil_j + high   (j→i, +high)
    #             z_j ≤ z_i − low   ⇒  ceil_j ≤ ceil_i − low    (i→j, −low)
    #   floor:    z_i ≥ z_j + low   ⇒  floor_i ≥ floor_j + low   (j→i, +low)
    #             z_j ≥ z_i − high  ⇒  floor_j ≥ floor_i − high  (i→j, −high)
    # The symmetric case ``low=−lim, high=+lim`` yields exactly the ±lim
    # both-way weights the loop above added, so this apparatus is byte-inert
    # with no interval edges (the loop below does not execute).  Interval-only
    # free nodes now GET the one-shot envelope warm-start AND, when their two
    # (or more) parent slabs cannot be jointly satisfied by the hard-anchor-
    # reachable station elevations, are caught by the ``floor > ceil`` break
    # detection and QUARANTINED — the exact livelock the POCS sweep otherwise
    # ping-pongs on (Stage B2 measured 27.7 M interval moves; the two-parent
    # gap-spine disjoint-slab class — see docs/slice_b_solver_absorption_
    # design.md and the ``_build_gap_spine_constraints`` empty-intersection
    # note, whose SEED-time prune misses slabs that only go disjoint as
    # stations move).
    interval_edges = []
    for (i, j), (raw_low, raw_high) in interval_lim.items():
        sweep_low, sweep_high = raw_low, raw_high    # RAW law — no margin
        interval_edges.append((i, j, raw_low, raw_high,
                               sweep_low, sweep_high))
        # ENVELOPE EXCLUSION FOR ZONE EDGES (Slice B stage B3 solve-side
        # fix, gated by ``interval_yield_from``): a signed slab injects
        # SIGNED (often NEGATIVE) directed weights into the reach-envelope
        # adjacency, but ``_reach`` is a Dijkstra — non-negative weights
        # only.  A zone node is an envelope LEAF (its host is authoritative;
        # it never propagates a bound onward), so its 45k asymmetric slabs
        # add nothing the envelope needs while triggering cascading
        # re-expansion (KBNA gates-ON: the ``_reach`` setup alone runs for
        # tens of minutes; gap-spine's ~1.6k drained fine, but 45k zone
        # slabs blow it up — the lazy-Dijkstra re-expand class).  Skip the
        # zone<->host slabs here; the host-authoritative sweep (kind fix
        # below) positions the zone directly against its solved host, and
        # gap-spine / sub-threshold slabs keep their envelope contribution.
        _zone_slab = (interval_yield_from is not None
                      and ((i >= interval_yield_from)
                           != (j >= interval_yield_from)))
        if _zone_slab or (i, j) in envelope_skip_pairs:
            continue
        # ENVELOPE SIGN DISCIPLINE (KCLT 2026-07-29 memory blowup): ``_reach``
        # is a lazy-deletion Dijkstra — its heap is bounded ONLY while every
        # ceiling weight is ≥ 0 and every floor weight ≤ 0.  A same-sign slab
        # component (``high < 0`` "must drop" / ``low > 0`` "must climb")
        # injects an improving edge, and the moment such slabs are JOINTLY
        # INFEASIBLE with the symmetric cap paths (difference-constraint
        # duality: infeasible ⟺ a net-negative cycle exists) the relaxation
        # loops toward −∞ growing the heap without bound — KCLT's gap-spine
        # corridors (839 negative ceiling weights) hit 56 GB RSS and a silent
        # SIGKILL exactly this way, the same class the EAT anchor-rect
        # rewrite and the ``envelope_skip`` rod flag already dodge.  Dropping
        # a direction here only LOOSENS the envelope (warm start + break
        # detection); the sweep below still enforces the full slab and the
        # tally still reports it, so law coverage is unchanged.
        if sweep_high is not None and sweep_high >= 0.0:
            ceil_radj.setdefault(j, []).append((i, sweep_high))
            floor_radj.setdefault(i, []).append((j, -sweep_high))
        if sweep_low is not None and sweep_low <= 0.0:
            ceil_radj.setdefault(i, []).append((j, -sweep_low))
            floor_radj.setdefault(j, []).append((i, sweep_low))

    # EXACT reachability envelope: ceil_i = min over hard anchors a of
    # (z_a + capdist(a→i)), floor_i = max of (z_a − capdist).  ``budget`` is the
    # edge's cap·length, so this is the steepest-compliant reach of every anchor.
    # Both envelopes are cap-Lipschitz, so clamping into [floor, ceil] removes all
    # gross (anchor-driven) infeasibility in ONE shot — the iterative pass then
    # only resolves free↔free edges, which converges fast.
    # LAZY SHAPES: the envelope + break detection run ONCE, here, on the
    # initial adjacency.  Still-lazy shapes contribute their RING edges to it,
    # so anchor-contradiction paths THROUGH a certified flat zone still exist
    # — at slightly looser ring-path budgets than the direct body chords would
    # give (the residual; fixtures gate it).  Mid-call expansions do NOT
    # recompute the envelope.
    INF = float("inf")

    _env_diag = _os.environ.get("O4_ENVELOPE_DIAG") == "1"
    if _env_diag:
        _neg_c = [(k, j, w) for k, lst in ceil_radj.items()
                  for (j, w) in lst if w < 0.0]
        _neg_f = [(k, j, w) for k, lst in floor_radj.items()
                  for (j, w) in lst if w < 0.0]
        print(f"    [env-diag] n={n} sym={len(edge_lim)} "
              f"interval={len(interval_lim)} iyf={interval_yield_from} "
              f"env_skip={len(envelope_skip_pairs)} "
              f"neg ceil_w={len(_neg_c)} floor_w={len(_neg_f)}", flush=True)
        for (k, j, w) in sorted(_neg_c, key=lambda t: t[2])[:10]:
            print(f"    [env-diag]   ceil {k}->{j} w={w:.3f}", flush=True)
        _ivs = list(interval_lim.items())[:10]
        for ((a, b), (lo, hi)) in _ivs:
            print(f"    [env-diag]   interval ({a},{b}) low={lo} high={hi}",
                  flush=True)

    def _reach(sign, radj, seeds, horizon=None):   # sign +1 → ceil, −1 → floor
        if _env_diag:
            return _reach_diag(sign, radj, seeds, horizon)
        return _reach_plain(sign, radj, seeds, horizon)

    def _reach_diag(sign, radj, seeds, horizon=None):
        # Instrumented twin of ``_reach_plain``: counts pops per node and
        # aborts loudly (instead of eating RAM) when the pop count reveals
        # an improving cycle — printing the most re-expanded nodes and
        # their incident weights so the offending edge family is named.
        from collections import Counter as _Counter
        pop_c: dict = _Counter()
        n_edges = sum(len(v) for v in radj.values())
        pop_cap = max(1_000_000, 20 * (n + n_edges))
        best: dict = {}
        dist: dict = {}
        pops = 0
        pq = [((elev[a] if sign > 0 else -elev[a]), 0.0, a)
              for a in seeds if a < n]
        heapq.heapify(pq)
        while pq:
            val, dk, k = heapq.heappop(pq)
            pops += 1
            if pops > pop_cap:
                top = pop_c.most_common(12)
                print(f"    [env-diag] _reach(sign={1 if sign > 0 else -1}) "
                      f"ABORT: pops>{pop_cap} (n={n} edges={n_edges} "
                      f"pq={len(pq)}); top re-expanded nodes:", flush=True)
                for (nd, cnt) in top:
                    ws = [(j, round(w, 3)) for (j, w) in radj.get(nd, ())][:8]
                    print(f"    [env-diag]   node {nd} pops={cnt} "
                          f"out={ws}", flush=True)
                raise RuntimeError("envelope Dijkstra improving cycle "
                                   "(O4_ENVELOPE_DIAG abort)")
            t = val if sign > 0 else -val
            if k in best and ((sign > 0 and t >= best[k])
                              or (sign < 0 and t <= best[k])):
                continue
            pop_c[k] += 1
            best[k] = t
            dist[k] = dk
            for (j, w) in radj.get(k, ()):
                ndk = dk + (w if w >= 0.0 else -w)
                if horizon is not None and ndk > horizon:
                    continue              # WITNESS HORIZON (see _reach_plain)
                nt = t + w
                pj = best.get(j)
                if pj is None or (sign > 0 and nt < pj) or (sign < 0 and nt > pj):
                    heapq.heappush(pq, ((nt if sign > 0 else -nt), ndk, j))
        return best, dist

    def _reach_plain(sign, radj, seeds, horizon=None):
        # ``radj`` provides directed weights with the sign already baked in
        # (``ceil_radj`` for +1, ``floor_radj`` for −1); the relaxation is
        # ``nt = t + w`` and the budget-metric distance accumulates ``|w|``.
        #
        # ``seeds`` — the anchors whose VALUES seed the envelope.  Normally
        # every hard node; the groundside-witness clause (below) runs a
        # SECOND, horizon-bounded pass whose seeds are the groundside pins.
        # ``horizon`` — drop any label once its budget-metric distance from
        # its seed exceeds this many metres of budget.  Truncation only
        # REMOVES labels, so the resulting envelope is a valid relaxation
        # (looser or equal) — it can never manufacture a break.
        best: dict = {}
        dist: dict = {}                     # budget-metric distance to the
        pq = [((elev[a] if sign > 0 else -elev[a]), 0.0, a)
              for a in seeds if a < n]      # value-optimal anchor
        heapq.heapify(pq)
        while pq:
            val, dk, k = heapq.heappop(pq)
            t = val if sign > 0 else -val
            if k in best and ((sign > 0 and t >= best[k])
                              or (sign < 0 and t <= best[k])):
                continue
            best[k] = t
            dist[k] = dk
            for (j, w) in radj.get(k, ()):
                ndk = dk + (w if w >= 0.0 else -w)
                if horizon is not None and ndk > horizon:
                    continue
                nt = t + w
                pj = best.get(j)
                if pj is None or (sign > 0 and nt < pj) or (sign < 0 and nt > pj):
                    heapq.heappush(pq, ((nt if sign > 0 else -nt), ndk, j))
        return best, dist

    # ``SVC_SPINE_EDGE_COUPLE`` / ``edge_couple_nodes`` — EXPOSED CONSUMER,
    # STOP-AND-REPORT (spec kill-half §2, 2026-08-04).  This feature's ONLY
    # effect site was the deleted break blend (it clamped a BLENDED broken
    # spine node into its hard-neighbour interval), so with the blend gone
    # the flag, the parameter and the caller's ``_svc_couple_nodes`` walk
    # in ``solve.final_grade_projection`` are inert.  Nothing here is
    # deleted on an implementer's own authority: the flag stays defined,
    # the parameter stays accepted and the caller stays as it is, and the
    # exposure is reported to the spec author for a ruling.

    def _hard_neighbour_witness(i):
        """``_hard_neighbour_interval`` plus the two AUTHORS of the bound.

        Same arithmetic, same order — the interval halves are the identical
        floats; the extra returns name the hard node that set each side, so
        a DECLARED conflict can carry its authors (fix arm §2)."""
        nlo, nhi = -INF, INF
        wlo = whi = None
        for (h, lim) in adj.get(i, ()):
            if h in hard:
                if elev[h] - lim > nlo:
                    nlo = elev[h] - lim
                    wlo = h
                if elev[h] + lim < nhi:
                    nhi = elev[h] + lim
                    whi = h
        return nlo, nhi, wlo, whi

    def _hard_neighbour_interval(i):
        """The elevation interval node ``i`` may take while still obeying the
        within-shape grade cap to every one of its HARD welded neighbours:
        ``∩ over hard h of [z_h − budget_ih, z_h + budget_ih]``.  Returns
        ``(lo, hi)``; ``lo > hi`` means the hard neighbours themselves
        contradict (a genuine break the blend must own)."""
        nlo, nhi, _wlo, _whi = _hard_neighbour_witness(i)
        return nlo, nhi

    # ── FIX ARM §2 — RULING 55 NEIGHBOUR BOUNDING (gate
    # ``O4_HARD_NEIGHBOUR_BOUND``, default "0") ──────────────────────────
    # "A yield/blend candidate adjacent to a hard node moves within
    # ``[hard ± cap·d]`` intersected with its own law.  BOUNDING, never
    # freezing — ``cap·d`` is the law's own freedom, so corridors still
    # descend away from hard nodes at cap rate."  The defect the ruling
    # names is ANY stage that MANUFACTURES an over-cap pair against a hard
    # node; the mover ledger attributed 94.0 % of the free-member conflicts
    # to ``proj_u.blend`` and 5.2 % to ``proj_shape.blend`` — i.e. to this
    # function's clamp/blend phase, and to nothing else (zero sweep labels).
    # So the law is applied HERE, at the three sites of that phase: the
    # envelope clamp, the break blend, and the chain-rigid rod blend.
    # The law is stated for ALL hard nodes, pins and truth anchors alike —
    # it is not pin-special, which is why 75 of the 88 anchor conflicts
    # pre-exist with the string gate off and why this needs its own gate.
    # Where the intersection is EMPTY the two hard nodes disagree beyond
    # their budgets THROUGH this node: that is a DECLARED conflict, the
    # node keeps whatever its own law puts it at today, and the triple
    # (node, low author, high author) is emitted write-only through
    # ``declared_out``.  Suppressing it would be the one thing the ruling
    # forbids.
    # PARKED FEATURE — NOT A LAW GATE (integration sweep 2026-08-05).
    # The taut-string machinery is the owner's PAUSED feature: the strings
    # verdict is pending (memory ``string-purpose-statement``: strings are a
    # smoothing refinement for otherwise-correctly-graded taxiways, NOT a
    # surface authority), so this switch is deliberately NOT deleted with
    # the law gates.  It selects whether a PARKED feature runs at all, not
    # which law the build obeys.  Retire or adopt it when the owner rules.
    _hnb_on = _os.environ.get("O4_HARD_NEIGHBOUR_BOUND", "0") == "1"
    _hnb_declared: list = []

    def _hnb_declare(i, nlo, nhi, wlo, whi, site):
        _hnb_declared.append({
            "node": int(i), "site": site,
            "hard_lo_author": (None if wlo is None else int(wlo)),
            "hard_hi_author": (None if whi is None else int(whi)),
            "lo": float(nlo), "hi": float(nhi),
            "deficit_m": float(nlo - nhi),
            "z_at_declare": float(elev[i]),
            "marker": "declared_hard_conflict"})

    def _hnb_isect(i, lo, hi, site):
        """Intersect ``[lo, hi]`` (the node's OWN law) with the hard-
        neighbour interval.  Returns the bounded interval, or the input
        untouched when the intersection is empty (declared conflict) or
        the node has no hard neighbour at all (nothing to bound)."""
        nlo, nhi, wlo, whi = _hard_neighbour_witness(i)
        if wlo is None and whi is None:
            return lo, hi
        blo = nlo if nlo > lo else lo
        bhi = nhi if nhi < hi else hi
        if blo > bhi:
            _hnb_declare(i, blo, bhi, wlo, whi, site)
            return lo, hi
        return blo, bhi

    # ── BOUNDED YIELD boxes → one per-node clamp map ─────────────────────
    # (owner ruling 2026-07-29; see the docstring.)  Built BEFORE the reach
    # envelope: a freed seat the envelope declares BROKEN (hard anchors
    # contradict through it) would otherwise be parked at the distance-
    # weighted blend — measured at HECA the blend sat ~15 m under the
    # seats' band floors, which IS the burial — so the broken branch below
    # clamps the blend of a bounded node into its box (the same pattern as
    # the SVC_SPINE_EDGE_COUPLE hard-neighbour clamp).  Group boxes attach
    # to the representative (the only member the sweeps move); duplicate
    # node boxes intersect (tightest per side).  Hard nodes (held, not
    # yielded), aliased group members and empty boxes drop out: the clamp
    # refines the yield, never adds a hold.
    bound_of: dict = {}
    if node_bounds:
        for bn, bb in node_bounds.items():
            if bb is None or not (0 <= bn < n):
                continue
            bound_of[bn] = _box_isect(bound_of.get(bn), bb)
    if rep_bounds:
        for bn, bb in rep_bounds.items():
            bound_of[bn] = _box_isect(bound_of.get(bn), bb)
    if bound_of:
        bound_of = {bn: (float(bb[0]), float(bb[1]))
                    for bn, bb in bound_of.items()
                    if bn not in hard and bn not in gmap
                    and bb[0] <= bb[1]}

    # ── GROUNDSIDE FEASIBILITY-WITNESS CLAUSE (owner ruling 2026-07-30,
    # memory ``groundside-terrace-law``; gate ``O4_GS_NO_AIRSIDE_WITNESS``
    # is evaluated by the CALLER, which passes ``witness_limited`` or not) ─
    # "Groundside values never act as a feasibility witness (floor or
    # ceiling) for airside pavement beyond the Part-C mouth allowance."
    # Part C (``anchors.apply_groundside_reach``) bounds the groundside
    # pin's VALUE; this bounds its ROLE.  Mechanically: the listed anchors
    # are pulled out of the envelope seed set and re-seeded in a SECOND
    # Dijkstra truncated at the mouth allowance expressed in the envelope's
    # own budget metric (``cap · MOUTH_ALLOWANCE_M`` metres of budget = one
    # connector throat of reach at cap).  Inside that throat the pin still
    # witnesses — the permitted exception, so a genuinely broken mouth weld
    # is still detected; beyond it the pin contributes nothing to any
    # airside node's ``[floor, ceiling]``.
    # It remains HARD for the sweeps (groundside is still pinned, and the
    # mouth-weld law edges are still enforced): only the witness role is
    # withdrawn.  ``witness_limited=None`` ⇒ ``_wl_nodes`` empty ⇒ the
    # single unrestricted pass below, byte-identical to the pre-clause code.
    _wl_nodes: set = set()
    _wl_horizon = 0.0
    if witness_limited:
        _wl_raw, _wl_horizon = witness_limited
        _wl_nodes = {_r(a) for a in (_wl_raw or ()) if a < n}
        _wl_nodes &= set(hard)
        # A limited anchor that is ALSO reachable as an ordinary anchor
        # (aliased into a flat group representative that carries other
        # authority) keeps its unrestricted role — the clause withdraws
        # groundside's authority, not the pad/seam authority it merged with.
        _wl_nodes -= {_r(a) for a in gmap} if gmap else set()

    # ── NON-ROUTE SEED ADMISSION (spec ``route-metric-envelope`` §2;
    # owner ruling "reach follows centerlines") ──────────────────────────
    # The same withdrawal as the groundside clause above, with NO
    # re-seeding pass: a hard anchor carrying no route-pavement role never
    # witnesses at any distance.  Resolved through the same flat-group
    # aliasing (``_r``) and intersected with ``hard`` so a stale index can
    # only ever remove an anchor that is actually seeding.  An anchor that
    # merged into a flat-group representative keeps its authority — the
    # clause withdraws the strip/clearance trace, not the pad it welded to.
    _we_nodes: set = set()
    if witness_excluded:
        _we_nodes = {_r(a) for a in witness_excluded if a < n}
        _we_nodes &= set(hard)
        _we_nodes -= {_r(a) for a in gmap} if gmap else set()

    # ── THE ENVELOPE READS THE CENTERLINE GRAPH (owner ruling 2026-07-30,
    # spec ``envelope-uses-the-centerline-graph``; gate
    # ``O4_ENVELOPE_FROM_BAND``, implied by ``O4_ROUTE_METRIC_ENVELOPE``;
    # ONE default, ``"0"`` — ``envelope_from_band_enabled``) ─────────────
    # "Feasibility and reach must only follow actual taxi route
    # centerlines… We already have the graph, use it, don't duplicate it."
    # ``env_band`` IS that graph's answer, computed once per build by
    # ``reach_band_unified`` and handed in by the caller — see the
    # docstring.  Absent (unit tests, synthetic graphs, gate off) the
    # pair-closure envelope below runs exactly as before.
    _band_env = (env_band
                 if (env_band is not None and envelope_from_band_enabled())
                 else None)
    _band_broken: set = set()
    if _band_env is not None:
        _nbe = len(_band_env)
        for i in range(n):
            if i in hard or (gmap and i in gmap):
                continue
            _b = _band_env[i] if i < _nbe else None
            if _b is not None and _b[0] > _b[1]:
                _band_broken.add(i)

    # ── THE BREAK BLEND IS DELETED (spec ``docs/specs/kill-half-spec.md``
    # §2, 2026-08-04) ────────────────────────────────────────────────────
    # An inverted envelope interval used to mint a QUARANTINE: the node was
    # painted at a distance-weighted blend ``hi + (lo−hi)·t`` and then
    # frozen out of every sweep.  Owner law (docs/RULINGS.md,
    # feasibility-is-guaranteed, ESCALATED 2026-08-01): "quarantine is
    # UNAUTHORIZED; break regions are law defects to attribute, never a
    # legitimate answer."  So the blend, its continuity gate
    # (``O4_BREAK_BLEND_CONTINUOUS``), its witness-source and distance-only
    # Dijkstras (``_reach_src`` / ``_dist_plain``) and the freeze all die
    # together, and an inversion is handled the only two lawful ways:
    #   * it is RECORDED (``band_inverted`` → ``broken_out``) so the
    #     minters keep their REPORT halves and the forensics hook still
    #     names the witness pair, and
    #   * the node takes the SAME clamp line every feasible node takes.
    #     For ``lo > hi`` that expression evaluates to ``hi`` — exactly the
    #     ``t → 0`` end of the blend it replaces, so the value stays inside
    #     the old blend's own ``[hi, lo]`` range and the node stays MOVABLE
    #     for the sweeps that follow.
    # A materially inverted FINAL band is now a build ERROR instead
    # (spec §3, ``building_feasibility.assert_no_final_band_inversion``).
    band_inverted: set = set()
    broken: set = set()
    # THE BAND BINDS PER SWEEP (cycle-5 fix 2): per-node reach-band
    # intervals collected in the envelope loop below and merged into
    # ``bound_of`` after it.  Empty ⇒ nothing merged ⇒ the one-shot
    # behaviour this replaces.
    _band_box: dict = {}
    # THE BAND WINS A DECLARED GROUNDSIDE CONFLICT (cycle-6 Part P):
    # ``{node: (floor, ceiling)}`` for every node whose groundside pin box
    # YIELDED to the band below.  Read once at EXIT to certify that the
    # resolution held (the acceptance instrument), never read back into
    # the projection.
    _band_wins: dict = {}
    if hard:
        # BYTE-INERTNESS: build the seed set with the SAME expression the
        # pre-clause code used whenever nothing is withdrawn — an extra
        # ``- set()`` still copies the set, and a copy can reorder the
        # heapify below.  Each clause only fires when it has work.
        _env_seeds = (set(hard) - _wl_nodes) if _wl_nodes else hard
        if _we_nodes:
            _env_seeds = _env_seeds - _we_nodes
        if _we_nodes and _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [route-metric] withdrew {len(_we_nodes)} non-route "
                  f"anchor(s) from the airside envelope seed set "
                  f"({len(_env_seeds)} of {len(hard)} still seeding)")
        # The pair-closure fields survived band-sourcing for ONE purpose —
        # the distance-weighted ``t`` of the break blend.  With the blend
        # deleted (spec kill-half §2) NOTHING reads them on the band path,
        # so both Dijkstras are skipped whenever the band answers, inverted
        # or not: the single-pass dividend of not computing an envelope
        # nobody consumes.  ``ceil``/``floor`` are read only on the
        # pair-closure path (no band handed in — unit tests, synthetic
        # graphs, ``O4_ROUTE_METRIC_ENVELOPE=0``).
        # ``_reach``'s second return is the budget-metric DISTANCE field.
        # Its only consumer was the deleted blend's ``t``, so it is dropped
        # on the floor here rather than merged — a dead store would read as
        # live state to the next reader.
        if _band_env is not None:
            ceil, floor = {}, {}
        else:
            ceil, _ = _reach(+1, ceil_radj, _env_seeds)
            floor, _ = _reach(-1, floor_radj, _env_seeds)
        if _wl_nodes and _band_env is None:
            _c2, _ = _reach(+1, ceil_radj, _wl_nodes, _wl_horizon)
            _f2, _ = _reach(-1, floor_radj, _wl_nodes, _wl_horizon)
            for _k, _v in _c2.items():
                if _k not in ceil or _v < ceil[_k]:
                    ceil[_k] = _v
            for _k, _v in _f2.items():
                if _k not in floor or _v > floor[_k]:
                    floor[_k] = _v
            if _os.environ.get("O4_STEP_DEBUG") == "1":
                print(f"    [gs-witness] withdrew {len(_wl_nodes)} groundside "
                      f"anchor(s) from the airside envelope "
                      f"(mouth horizon {_wl_horizon:.3f} m of budget)")
        for i in range(n):
            if i in hard:
                continue
            if _band_env is not None:
                # A rigid flat group's members are aliased onto their
                # representative (which carries the level and is broadcast
                # back at the end); the pair closure gives them an empty
                # adjacency and therefore an infinite interval, so the band
                # path skips them for the same reason — clamping a member
                # individually would fight the flatness invariant.
                if gmap and i in gmap:
                    continue
                _bi = (_band_env[i] if i < len(_band_env) else None)
                if _bi is None:
                    # OFF-NET: the band has no answer here, so the LOCAL
                    # within-shape law governs (the documented contract).
                    # Neither broken nor envelope-clamped.
                    continue
                lo, hi = float(_bi[0]), float(_bi[1])
            else:
                lo = floor.get(i, -INF)
                hi = ceil.get(i, INF)
            if lo > hi:
                # BAND INVERSION — the anchors contradict through this node.
                # RECORDED, never blended and never frozen (spec kill-half
                # §2; the deleted blend's rationale is at the top of this
                # clause).  The clamp below is the ONE surviving line and
                # for an inverted interval it evaluates to ``hi`` — the
                # blend's own ``t → 0`` end, so the value stays inside the
                # range the blend could have produced while the node stays
                # movable for the sweeps.  A materially inverted FINAL band
                # is a build ERROR (spec §3).
                band_inverted.add(i)
            # ── FIX ARM §2, SITE 1: THE ENVELOPE CLAMP ─────────────
            if _hnb_on:
                lo, hi = _hnb_isect(i, lo, hi, "envelope_clamp")
            elev[i] = min(max(elev[i], lo), hi)  # clamp into the envelope
            # ── THE BAND BINDS PER SWEEP (cycle-5 spec fix 2) ──────
            # The clamp above is ONE-SHOT: applied here, before any
            # sweep, and then the sweeps relax it away.  Caps bind per
            # sweep, node boxes bind per sweep, and the reach band —
            # the law that decides WHERE on the plateau a pavement
            # seats — bound once.  The tree already said so at
            # ``solve.py``: "the phase-A/B floors alone don't survive
            # the projections (min-displacement POCS knows caps, not
            # floors, and projects the lift away)".
            #
            # DECISIVE MEASUREMENT (attribution dossier §3, fp#8 EXIT,
            # 19,067 banded nodes): 11,144 BELOW their own floor (worst
            # 89.637 m) versus 112 above their ceiling (worst 0.187 m)
            # — 99.5 : 1.  A two-sided band producing a one-sided error
            # at that ratio is a mechanism, not noise: the ceiling
            # binds and the floor does not.  Across all 8 recorded
            # stages the below-floor count never improves; it ends
            # WORSE than it started.
            #
            # So the interval joins the SAME per-node channel the
            # boxes use (``bound_of`` → ``_node_box_arrays``), which
            # clamps at seed and after every sweep in all three
            # kernels.  Per-node by construction, so it can no more
            # pull a neighbour than a seat box can.
            #
            # An INVERTED band (``lo > hi``) gets NO box: an empty box
            # would clamp to ``hi`` silently every sweep and freeze the
            # node.  It keeps the recorded-and-movable handling above.
            if lo <= hi and (lo > -INF or hi < INF):
                _band_box[i] = (lo, hi)
        # ── MERGE THE BAND INTO THE PER-SWEEP BOX CHANNEL (fix 2) ────
        # After the loop so every band interval is known, and with the
        # same guards ``bound_of`` was built under: hard nodes are held
        # not yielded, flat-group members are carried by their
        # representative, and an EMPTY intersection is never written as
        # a box (it would clamp to ``hi`` every sweep and silently
        # freeze the node).  Where a node already carries a box — a
        # building seat — the two laws INTERSECT, and a genuinely empty
        # intersection is a DECLARED CONFLICT: reported, with the
        # tighter pre-existing box kept, because under
        # ``feasibility-is-guaranteed`` two laws that cannot both hold
        # at one vertex is a defect to attribute at source, never a
        # silent resolution.
        #
        # ── AIRSIDE IS KING: THE BAND WINS (cycle-6 Part P) ──────────
        # Attribution (c5auth dossier, HECA plateau): the pre-existing
        # box at every one of the 14 declared conflicts was a freed
        # GROUNDSIDE PIN's per-sweep LAW ceiling — the lot's weld datum
        # plus one throat of reach, ~1 m on a plateau world — and
        # keeping it discarded the airside reach band, parking 14 apron
        # / service_junction nodes up to 87 m BELOW their own band
        # floor.  ``final_grade_projection``, which carries no such box,
        # then lifted them back: the whole second-author extreme class,
        # and the carrier of the stuck ~89 m fp#8 residual.
        #
        # Standing law (docs/RULINGS.md): "Groundside must have ZERO
        # effect or pull on airside; airside solves first, groundside
        # conforms."  A groundside ceiling that cannot be met is
        # therefore not a constraint on the airside band — it is a
        # demand on the LOT, which conforms through the terrace /
        # retaining-wall machinery (groundside terrace law) and, for a
        # freed mouth cluster, through ``adopt_projected_mouths``.
        #
        # So at a declared conflict on a groundside pin box the BAND
        # BINDS and the pin box YIELDS: its ceiling is withdrawn and
        # re-derived from the airside-conformed datum, which IS the band
        # at that node.  (The conflict is always one-sided — a box with
        # ``lo <= hi`` cannot straddle a band with ``lo <= hi`` on both
        # sides — so the surviving half of the pin box is never binding
        # and the resolved box is exactly the band.)  Nothing is
        # discarded silently: every conflict prints a LOUD report line
        # naming both halves and the resolution, ungated, and the
        # resolution is certified again at EXIT.  A conflict on any
        # OTHER box class (a building seat box) is NOT ruled by this
        # clause: it keeps today's behaviour and is reported UNRESOLVED,
        # to be attributed at source rather than resolved here.
        if _band_box:
            _bb_added = _bb_isect = _bb_conflict = _bb_yield = 0
            _bb_rows: list = []
            _gs_pin = gs_pin_nodes or ()
            for _bi, (_blo, _bhi) in _band_box.items():
                if _bi in hard or (gmap and _bi in gmap):
                    continue
                _prev = bound_of.get(_bi)
                if _prev is None:
                    bound_of[_bi] = (_blo, _bhi)
                    _bb_added += 1
                    continue
                _nlo, _nhi = max(_prev[0], _blo), min(_prev[1], _bhi)
                if _nlo > _nhi:
                    _bb_conflict += 1
                    if _bi in _gs_pin:
                        bound_of[_bi] = (_blo, _bhi)
                        _band_wins[_bi] = (_blo, _bhi)
                        _bb_yield += 1
                        _bb_rows.append(
                            (_bi, _prev, (_blo, _bhi), True))
                    else:
                        _bb_rows.append(
                            (_bi, _prev, (_blo, _bhi), False))
                    continue
                bound_of[_bi] = (_nlo, _nhi)
                _bb_isect += 1
            if _bb_rows:
                import O4_UI_Utils as _UI_band
                # THE RULE CITATION STAYS; THE PREDICTION GOES.  "the lot
                # conforms via the terrace/wall machinery" was a
                # forward-looking claim about ANOTHER subsystem
                # (groundside terraces/retaining walls) that nothing here
                # computes or checks — deleted from the report under
                # RULINGS 2026-08-06 §2 and kept only as this comment,
                # which is the design intent, not a measurement.  The
                # UNRESOLVED half is likewise reduced to its MEMBERSHIP
                # FACT (``_bi not in gs_pin_nodes``): it was a catch-all
                # bucket labelled with a cause plus an instruction to the
                # reader, and the box class it actually holds is whatever
                # was there — the per-node rows below print both
                # intervals so the reader attributes it themselves.
                _UI_band.vprint(1,
                    f"    [env-band] {_bb_conflict} DECLARED CONFLICT(S) "
                    f"band vs pre-existing box "
                    f"{_node_space_stamp(n)}: {_bb_yield} resolved "
                    f"BAND WINS (node in gs_pin_nodes; groundside pin box "
                    f"withdrawn — airside is king, RULINGS 2026-07-30), "
                    f"{_bb_conflict - _bb_yield} UNRESOLVED (node not in "
                    f"gs_pin_nodes; pre-existing box kept)")
                for _ri, (_bi, _pv, _bd, _won) in enumerate(_bb_rows):
                    if _ri >= 20:
                        _UI_band.vprint(1,
                            f"      … and {len(_bb_rows) - 20} more "
                            f"declared conflict(s)")
                        break
                    _UI_band.vprint(1,
                        f"      node {_bi} [{_NODE_SPACE_FP_REMAPPED}]: "
                        f"GROUNDSIDE box "
                        f"[{_pv[0]:.3f}, {_pv[1]:.3f}] vs AIRSIDE band "
                        f"[{_bd[0]:.3f}, {_bd[1]:.3f}] -> "
                        + ("BAND WINS (box withdrawn, ceiling re-derived "
                           "from the band)" if _won else
                           "UNRESOLVED (box kept)"))
            if _os.environ.get("O4_STEP_DEBUG") == "1":
                print(f"    [env-band] band bound PER SWEEP "
                      f"{_node_space_stamp(n)}: {_bb_added} "
                      f"node box(es) added, {_bb_isect} intersected with "
                      f"an existing box, {_bb_conflict} DECLARED "
                      f"CONFLICT(S) ({_bb_yield} resolved BAND WINS, "
                      f"{_bb_conflict - _bb_yield} unresolved — existing "
                      f"box kept)")
        if _band_env is not None and _os.environ.get("O4_STEP_DEBUG") == "1":
            _bn_none = _bn_ok = 0
            for i in range(n):
                if i in hard or (gmap and i in gmap):
                    continue
                _b = (_band_env[i] if i < len(_band_env) else None)
                if _b is None:
                    _bn_none += 1
                elif _b[0] <= _b[1]:
                    _bn_ok += 1
            # ``non-inverted`` is the whole predicate: ``_b[0] <= _b[1]``,
            # a NON-EMPTY interval on one node.  It was printed as
            # ``feasible=``, which claims a property of the whole system
            # this loop never evaluates (the same over-claiming word the
            # L−U carrier line carried — see :func:`_lu_class`).
            # ``pair closure skipped`` is a fact about the branch above;
            # "the band answers" was an interpretation of these counts.
            print(f"    [env-band] envelope from THE graph "
                  f"{_node_space_stamp(n)}: "
                  f"band-inverted={len(_band_broken)} "
                  f"non-inverted={_bn_ok} off-net={_bn_none} "
                  f"(pair-closure envelope not computed: env_band supplied)")
        # ── BREAK FORENSICS (spec reference-honesty Track 1 step 4, gate
        # ``O4_BREAK_FORENSICS=<path>``) ─────────────────────────────────
        # Name every inverted node's floor>ceiling WITNESS PAIR by ANCHOR
        # CLASS.  Standing principle ``feasibility-is-guaranteed``: a real
        # airport proves a lawful surface exists, so "infeasible" is never
        # an answer — every inversion must be attributed to a wrong law, a
        # wrong anchor value or a wrong topology, and the witness pair is
        # what names which.  Unset ⇒ nothing runs (the witness Dijkstras
        # are a second pass) ⇒ byte-identical and cost-free.  Reads the
        # REPORT set: with the blend deleted there is no quarantine to
        # read, and the report is what the drain list is built from.
        _forensics_path = _os.environ.get("O4_BREAK_FORENSICS")
        if _forensics_path and band_inverted and forensics is not None:
            _break_forensics_report(
                _forensics_path, forensics.get("label", ""), band_inverted,
                hard, elev, n, ceil_radj, floor_radj,
                forensics.get("classes") or {},
                forensics.get("nodes_ll"),
                limited=_wl_nodes, horizon=_wl_horizon)

    # ── CHAIN-RIGID BROKEN BLEND (spec apron-string-and-scheduling §D.2.1;
    # STANDING LAW) ──────────────────────────────────────────────────────
    # ATTRIBUTED 2026-07-30: the HECA corridor sag is the break-region
    # blend, not the string.  At the spine-yield projection EVERY corridor
    # node is broken (envelope floor > ceiling by 13-18 m), so the law
    # exempts them and the POINTWISE distance-weighted blend above repaints
    # the profile — the sag IS the blend's t-ramp (t 0.936 → 0.731 along
    # the corridor).  A rod slab is a DIFFERENCE constraint, so a strung
    # chain is always satisfiable inside a break region AT ZERO COST IN
    # LEVEL: the chain may translate freely.  Treat each maximal run of
    # broken rod-linked nodes as RIGID — compute the blend per chain and
    # apply the chain's Δ SHAPE at the least-displacement level, instead of
    # letting the pointwise blend bend it.
    #
    # ★ The per-node hard-neighbour clamp is PRESERVED FOR CHAIN ENDPOINTS
    # (the 05C runway-kink guard): the chain's level is first constrained
    # by every endpoint's hard-neighbour interval, and the per-node clamp is
    # then re-applied at the endpoints as a final guard.  A chain whose
    # endpoint intervals and boxes cannot be reconciled by ANY translation
    # keeps today's pointwise result exactly (no regression class).
    #
    # Chains come from the ENVELOPE-SKIP interval edges — the §10 taut-rod
    # slabs, the only entry that carries that flag — so nothing is
    # re-derived or re-strung (single-pass principle).  No rod ⇒ no chain
    # ⇒ this block is inert and the solve is byte-identical.
    if broken and envelope_skip_pairs:
        rod_adj: dict = {}
        _rp_both = _rp_one = _rp_none = 0
        for (_ra, _rb) in envelope_skip_pairs:
            _nb = (_ra in broken) + (_rb in broken)
            if _nb == 2:
                _rp_both += 1
            elif _nb == 1:
                _rp_one += 1
            else:
                _rp_none += 1
            if _nb != 2:
                continue          # chain end: a free/hard neighbour anchors
            _iv = interval_lim.get((_ra, _rb))
            if _iv is None or _iv[0] is None or _iv[1] is None:
                continue
            _mid = 0.5 * (_iv[0] + _iv[1])        # z_a − z_b (the Δ shape)
            # entry (neighbour, Δoffset, slab_lo, slab_hi) on z_nb − z_self.
            rod_adj.setdefault(_ra, []).append(
                (_rb, -_mid, -_iv[1], -_iv[0]))
            rod_adj.setdefault(_rb, []).append(
                (_ra, +_mid, _iv[0], _iv[1]))
        # CHAIN ≠ CONNECTED COMPONENT (measured HECA 2026-07-30): corridors
        # SHARE their junction vertices, so the rod graph is one giant
        # component — 6,176 of 7,346 both-broken slabs in a single blob.
        # A single rigid translation for the whole blob is over-constrained
        # by construction (it was infeasible at HECA and fell back to the
        # pointwise blend, i.e. the pass did nothing).  The spec's "chain"
        # is one STRUNG CORRIDOR: split the graph at BRANCH vertices
        # (rod degree >= 3, the junctions where corridors meet).  A branch
        # vertex keeps today's pointwise value and acts as an anchor: each
        # incident chain's level must still satisfy its own rod slab to it,
        # so the string stays continuous through the junction.
        _rod_deg = {_v: len(_l) for _v, _l in rod_adj.items()}
        _branch = {_v for _v, _d in _rod_deg.items() if _d >= 3}
        _seen: set = set()
        _n_chains = 0
        _n_rigid_nodes = 0
        _n_infeasible = 0
        for _root in rod_adj:
            if _root in _seen or _root in _branch:
                continue
            # BFS the chain (branch vertices bound it), accumulating the
            # rigid Δ offsets.
            _off = {_root: 0.0}
            _order = [_root]
            _seen.add(_root)
            _qi = 0
            while _qi < len(_order):
                _u = _order[_qi]
                _qi += 1
                for (_v, _d, _slo, _shi) in rod_adj.get(_u, ()):
                    if _v in _off or _v in _branch:
                        continue
                    _off[_v] = _off[_u] + _d
                    _seen.add(_v)
                    _order.append(_v)
            if len(_order) < 2:
                continue
            # Least-displacement level: the mean of the pointwise targets
            # de-shaped by the rigid offsets.
            _L = sum(elev[_v] - _off[_v] for _v in _order) / len(_order)
            _ends = [_v for _v in _order
                     if sum(1 for (_w, _dd, _sl, _sh) in rod_adj.get(_v, ())
                            if _w in _off) == 1]
            _lo_L, _hi_L = -INF, INF
            # ── FIX ARM §2, SITE 3: THE CHAIN-RIGID ROD BLEND ──────────
            # A rigid chain moves as one, so Ruling 55's bound is a bound
            # on the chain's LEVEL — and it is owed by EVERY member with a
            # hard neighbour, not only by the two ends (today's rule).
            # Under the gate the range accumulates over the whole run; a
            # member whose own hard neighbours contradict is a declared
            # conflict and contributes no bound (its pointwise value,
            # already bounded at site 2, stands if the chain cannot be
            # placed).  Gate off ⇒ the endpoint-only range, unchanged.
            for _e in (_order if _hnb_on else _ends):
                if _hnb_on:
                    _elo, _ehi, _ewlo, _ewhi = _hard_neighbour_witness(_e)
                    if _elo > _ehi:
                        _hnb_declare(_e, _elo, _ehi, _ewlo, _ewhi,
                                     "chain_rigid")
                else:
                    _elo, _ehi = _hard_neighbour_interval(_e)
                if _elo <= _ehi:
                    _lo_L = max(_lo_L, _elo - _off[_e])
                    _hi_L = min(_hi_L, _ehi - _off[_e])
            # The rod slab to every bounding BRANCH vertex (which keeps its
            # pointwise value) enters as a least-displacement SAMPLE, not a
            # hard bound.  Measured HECA 2026-07-30: as a hard bound it
            # made 440 of 538 chains infeasible and the pass degenerated to
            # the pointwise blend — the branch vertices are themselves bent
            # by that blend, so two bent junctions can contradict any rigid
            # placement of the chain between them.  A sample keeps the
            # string continuous where it can be and still lets the chain
            # straighten where the junctions disagree.
            _samples = [elev[_v] - _off[_v] for _v in _order]
            for _v in _order:
                for (_w, _dd, _slo, _shi) in rod_adj.get(_v, ()):
                    if _w in _branch:
                        _samples.append(
                            elev[_w] - 0.5 * (_slo + _shi) - _off[_v])
            _L = sum(_samples) / len(_samples)
            if bound_of:
                for _v in _order:
                    _bb = bound_of.get(_v)
                    if _bb is not None:
                        _lo_L = max(_lo_L, _bb[0] - _off[_v])
                        _hi_L = min(_hi_L, _bb[1] - _off[_v])
            if _lo_L > _hi_L:
                _n_infeasible += 1
                continue          # no lawful translation → keep pointwise
            _L = min(max(_L, _lo_L), _hi_L)
            for _v in _order:
                elev[_v] = _L + _off[_v]
            # ★ endpoint guard (05C runway kink): the per-node clamp the
            # pointwise branch applied stays in force at the chain ends.
            for _e in _ends:
                _elo, _ehi = _hard_neighbour_interval(_e)
                if _elo <= _ehi:
                    elev[_e] = min(max(elev[_e], _elo), _ehi)
            _n_chains += 1
            _n_rigid_nodes += len(_order)
        # ── RIGID BRANCH VERTICES (spec reference-honesty Track 1 step 3;
        # STANDING LAW) ──────────────────────────────────────────────────
        # The chain split above leaves every BRANCH vertex (rod degree ≥ 3
        # — the junctions corridors share) on its POINTWISE blend value,
        # while the chains around it have been placed rigidly.  That is
        # memory ``rod-chains-split-at-branches``'s named residual: a
        # ~1.2 m step where a rigid chain meets a still-pointwise junction
        # (HECA corridor mouth, s ≈ −5 m).  Place the junction on the
        # string too: its rod slabs to the (now placed) incident chains
        # each imply a level ``z[branch] = z[neighbour] − Δ``, and the
        # least-displacement point among them is their mean.
        # ★ The hard-neighbour clamp is APPLIED HERE TOO (it is the 05C
        # runway-kink guard — a junction welded to a runway must grade into
        # it, never hold a string value against it), and the bounded-yield
        # box still binds.  Branch-to-branch slabs are skipped: neither end
        # has a rigid authority, so using one to place the other would only
        # make the result order-dependent.
        _n_branch_placed = 0
        if _branch:
            for _bv in _branch:
                if _bv in hard:
                    continue
                _bvals = [elev[_w] - _d
                          for (_w, _d, _slo, _shi) in rod_adj.get(_bv, ())
                          if _w not in _branch and _w in _seen]
                if not _bvals:
                    continue
                _bt = sum(_bvals) / len(_bvals)
                # ★ 05C guard — and, under fix arm §2, already exactly
                # Ruling 55's bound for a branch vertex.  The only change
                # under the gate is that an EMPTY interval (which the
                # guard silently skips today) is DECLARED.
                _bnlo, _bnhi, _bwlo, _bwhi = _hard_neighbour_witness(_bv)
                if _bnlo <= _bnhi:
                    _bt = min(max(_bt, _bnlo), _bnhi)
                elif _hnb_on and (_bwlo is not None or _bwhi is not None):
                    _hnb_declare(_bv, _bnlo, _bnhi, _bwlo, _bwhi,
                                 "branch_rigid")
                if bound_of:
                    _bbox = bound_of.get(_bv)
                    if _bbox is not None:
                        _bt = min(max(_bt, _bbox[0]), _bbox[1])
                elev[_bv] = _bt
                _n_branch_placed += 1
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [chain-rigid] rod pairs both/one/no broken end="
                  f"{_rp_both}/{_rp_one}/{_rp_none}; broken={len(broken)}; "
                  f"{_n_chains} chain(s), {_n_rigid_nodes} node(s) placed "
                  f"rigidly; {_n_infeasible} kept the pointwise blend; "
                  f"{_n_branch_placed}/{len(_branch)} branch vertex(es) "
                  f"placed on the string")

    # ── PROBE A, BLEND/SWEEP BOUNDARY (spec §1; write-only) ──────────
    # Everything above is the reach envelope's clamp + break blend;
    # everything below is the sweeps.  One dict comprehension over the
    # caller's watch set, only when the caller passed one.
    if probe_out is not None and probe_out.get("watch"):
        probe_out["post_blend"] = {_pi: elev[_pi]
                                   for _pi in probe_out["watch"]}

    # ── FIX ARM §2 DELIVERY: the declared conflicts of THIS call ─────
    # Write-only, after the whole clamp/blend phase (the only phase that
    # declares).  "Small and author-carrying" is the pre-registered
    # expectation; a LARGE population is a finding, so it is delivered
    # whole and never truncated.
    if declared_out is not None and _hnb_declared:
        declared_out.extend(_hnb_declared)
    if _hnb_declared and _os.environ.get("O4_STEP_DEBUG") == "1":
        _hnb_sites: dict = {}
        for _dr in _hnb_declared:
            _hnb_sites[_dr["site"]] = _hnb_sites.get(_dr["site"], 0) + 1
        print(f"    [hard-neighbour-bound] {len(_hnb_declared)} declared "
              f"hard conflict(s) over "
              f"{len({_dr['node'] for _dr in _hnb_declared})} node(s): "
              + ", ".join(f"{_k}={_v}"
                          for _k, _v in sorted(_hnb_sites.items())))

    # THE FREEZE IS DELETED (spec kill-half §2).  A band-inverted node used
    # to be held at its blended value and dropped from every sweep — the
    # second half of the quarantine the owner's ruling forbids.  It now
    # sweeps like any other free node: the clamp above left it at its
    # ceiling, and the within-shape law is what places it from there.
    # ``band_inverted`` is delivered through ``broken_out`` as a REPORT
    # (the A2/A3/A4/B3 minters' surviving halves read it) and nothing in
    # this function reads it back.
    if broken_out is not None:
        broken_out.update(band_inverted)
    # ``pre_broken`` — the SCOPED final projection's caller-supplied set
    # (gate ``O4_SCOPED_FINAL_PROJECTION``, default "0").  Left standing:
    # it is that feature's own machinery, not the envelope quarantine this
    # spec kills, and with the ``_final_projection_broken_keys`` carry
    # deleted it is empty in every default build.
    if pre_broken:
        # Caller-supplied quarantine (scoped final projection): the solve's
        # FULL graph proved these nodes sit in infeasible pockets.  Merged
        # AFTER the envelope pass: the envelope may first clamp them into
        # its own (sparser) [floor, ceil] exactly as the full rebuild's
        # envelope re-blends its broken set — measured at CYXY this
        # ordering reproduces the full rebuild's surface exactly, while
        # quarantining before the clamp diverges (the final projection's
        # anchor set differs from the solve's, so holding the solve's
        # blend values is NOT what the full rebuild does).
        for _pb in pre_broken:
            if 0 <= _pb < n and _pb not in hard:
                broken.add(_pb)
        if broken_out is not None:
            broken_out.update(broken)
    immovable = hard | broken if broken else hard

    # BOUNDED YIELD, sweep side: quarantined bounded nodes stay put; the
    # sweeps only ever move the
    # remaining (movable) bounded nodes, so the clamp map they carry is
    # filtered to those — and each is clamped once here at seed (the
    # reach-envelope clamp above knows nothing about boxes) and then after
    # every step that moves it inside the sweep paths below.
    if bound_of:
        bound_of = {bn: bb for bn, bb in bound_of.items()
                    if bn not in immovable}
        for bn, (blo, bhi) in bound_of.items():
            if elev[bn] < blo:
                elev[bn] = blo
            elif elev[bn] > bhi:
                elev[bn] = bhi

    # Pre-split the edges ONCE by hard-membership.  The inner loop otherwise ran
    # two ``in hard`` set lookups PER edge PER iteration (up to ~0.5 B lookups on
    # a big airport).  Both-immovable edges can never move, so drop them from the
    # iteration entirely (they are only counted in the final tally below).
    # ``kind``: 0 = both free (split the excess), 1 = i fixed (move j), 2 = j fixed.
    # The iteration enforces the RAW law budget — see above.
    # ``iter_raw_budget`` is the INSTRUMENT-ONLY parallel column (seed-fix
    # round §1a): entry ``k`` is ``iter_edges[k]``'s RAW law budget (``None``
    # at interval slots).  Nothing in the projection reads it; it reaches
    # only the write-only stall report, whose ``L − U`` adjudication is a
    # LAW measure and must never be priced on a per-edge-shrunk frame.
    # With the emit-quantization margin retired the two columns carry the
    # SAME values — the seam is kept, not collapsed, because that
    # adjudication is a PATH quantity and must not silently inherit a
    # frame it did not choose.
    iter_edges = []
    iter_raw_budget = []
    for (i, j, _raw_budget, sweep_budget) in edges:
        hi = i in immovable
        hj = j in immovable
        if hi and hj:
            continue
        iter_edges.append((i, j, sweep_budget, 1 if hi else (2 if hj else 0)))
        iter_raw_budget.append(_raw_budget)
    # INTERVAL EDGES (Stage B0) share the SAME worklist/Jacobi machinery as the
    # symmetric edges so a node moved by one re-triggers the other in lockstep.
    # They enter ``iter_edges`` with the SENTINEL ``budget=None`` in slot 2 and
    # their signed sweep bounds in ``interval_bounds_by_index`` (keyed by the
    # entry's ``iter_edges`` position).  Being real ``iter_edges`` entries, they
    # get stable indices and ride the existing ``incident``/``in_pending``/
    # ``pending`` bookkeeping and the mid-call lazy-append growth for free; the
    # scalar inner loop and the vectorised path branch on the ``None`` sentinel.
    # With gates off there are none, so slot 2 is never ``None`` and both sweep
    # paths run their untouched symmetric arithmetic.  ``kind`` as above (0 both
    # free, 1 i fixed, 2 j fixed); both-immovable pairs are tallied, never swept.
    interval_bounds_by_index: dict = {}
    for (i, j, _rl, _rh, sweep_low, sweep_high) in interval_edges:
        hi = i in immovable
        hj = j in immovable
        if hi and hj:
            continue
        kind = 1 if hi else (2 if hj else 0)
        # HOST-AUTHORITATIVE ZONE EDGES (Slice B stage B3 solve-side fix,
        # gated by ``interval_yield_from`` from the call site): an
        # adjacent-ground zone node (canonical index >= the threshold) is
        # graded TO its host pavement ring vertex — pavement value always
        # wins at a pavement node, an IDENTITY.  Its ONE envelope interval
        # edge to the host must therefore move ONLY the zone endpoint; the
        # default kind=0 (split the excess) instead drags the host, and a
        # host shared by k zones ping-pongs the whole cluster to the visit
        # cap (KBNA gates-ON: 47k such edges livelock the sweep for tens of
        # minutes; gates-OFF the same projection drains <1 s).  Fixing the
        # host (kind that moves the ZONE endpoint) makes it a one-directional
        # follow — the zone tracks the host, never the reverse — so the sweep
        # drains in one neighbourhood pass.  Only zone<->host pairs (exactly
        # one endpoint over the threshold, neither already immovable) are
        # redirected; zone<->zone or sub-threshold (gap-spine) interval edges
        # keep the split.  ``interval_yield_from=None`` restores kind=0 —
        # byte-inert.
        if interval_yield_from is not None and kind == 0:
            i_zone = i >= interval_yield_from
            j_zone = j >= interval_yield_from
            if i_zone and not j_zone:
                kind = 2                 # host j fixed, move zone i
            elif j_zone and not i_zone:
                kind = 1                 # host i fixed, move zone j
        interval_bounds_by_index[len(iter_edges)] = (sweep_low, sweep_high)
        iter_edges.append((i, j, None, kind))
        iter_raw_budget.append(None)        # interval slot — see §1a note

    # ── lazy expansion plumbing for the projection loops ─────────────────
    # node → still-lazy entries, REPRESENTATIVE-keyed (a pad-group member's
    # movement shows on its representative).  Determinism: entries appear in
    # ``shape_constraints`` order and are expanded in that order; each
    # expansion appends edges in thunk order — no set is iterated anywhere.
    lazy_entries_by_node: dict = {}
    for lazy_entry in lazy_entries_pending:
        for node_index in lazy_entry["lazy_nodes"]:
            if 0 <= node_index < n:
                lazy_entries_by_node.setdefault(
                    _r(node_index), []).append(lazy_entry)

    def _expand_lazy_entry_into_projection(entry):
        """MID-CALL expansion: merge the entry's full pair set into the live
        projection state (``edge_lim`` / ``edges`` / ``iter_edges``).
        Returns the new ``iter_edges`` indices so the scalar worklist can
        wire them into ``incident``/``pending`` (the vectorised path instead
        re-runs on the grown ``iter_edges``).  A pair already present at a
        tighter-or-equal budget is skipped; a TIGHTER duplicate is appended
        alongside the looser one — both are enforced, the tightest binds.
        Both-immovable pairs are tallied (``edges``) but never swept, exactly
        like the entry-time path.  The reach envelope is NOT recomputed (see
        the envelope comment above)."""
        new_edge_indices = []
        # Cycle-7 fix 5: a MID-CALL expansion mints pairs the entry-time
        # loop never saw, so the family axis is recorded here too — same
        # rule, same first-wins, and skipped entirely without a map.
        _lz_fam = _entry_family_tag(entry) if fam_by_pair is not None else None
        _lz_per_edge = (_lz_fam in _CATCH_ALL_FAMILY_TAGS
                        if _lz_fam is not None else False)
        for (raw_a, raw_b, raw_budget) in _expand_lazy_entry(entry):
            if raw_budget is None or raw_budget < 0 \
                    or raw_a >= n or raw_b >= n:
                continue
            node_a, node_b = _r(raw_a), _r(raw_b)
            if node_a == node_b:
                continue
            pair = (node_a, node_b) if node_a < node_b else (node_b, node_a)
            if fam_by_pair is not None and (pair + (False,)) not in fam_by_pair:
                _oa, _ob = ((raw_a, raw_b) if raw_a <= raw_b
                            else (raw_b, raw_a))
                fam_by_pair[pair + (False,)] = (
                    family_of.get((_oa, _ob), _lz_fam)
                    if _lz_per_edge else _lz_fam)
            previous_budget = edge_lim.get(pair)
            if previous_budget is not None and previous_budget <= raw_budget:
                continue
            edge_lim[pair] = raw_budget
            sweep_budget = raw_budget            # RAW law budget — no margin
            edges.append((pair[0], pair[1], raw_budget, sweep_budget))
            a_immovable = pair[0] in immovable
            b_immovable = pair[1] in immovable
            if a_immovable and b_immovable:
                continue
            iter_edges.append((pair[0], pair[1], sweep_budget,
                               1 if a_immovable else (2 if b_immovable else 0)))
            iter_raw_budget.append(raw_budget)
            new_edge_indices.append(len(iter_edges) - 1)
        return new_edge_indices

    # POST-ENVELOPE movement check: the reachability clamp (and the broken-
    # node blend) above moves band-infeasible nodes BEFORE any sweep — the
    # worklist only reacts to edge-driven moves and would never see those, so
    # a certified shape whose node was clamped off its seed must expand NOW.
    # New edges land in ``iter_edges`` before either projection path builds
    # its queue, so they are swept from the start.
    if lazy_entries_pending:
        _still_pending_entries = []
        for lazy_entry in lazy_entries_pending:
            if "lazy_expand" not in lazy_entry:
                continue
            if _lazy_nodes_moved(lazy_entry):
                _expand_lazy_entry_into_projection(lazy_entry)
            else:
                _still_pending_entries.append(lazy_entry)
        lazy_entries_pending = _still_pending_entries

    # Under the GLOBAL-SLICE spine the graph is ~4x the rect model's
    # (SPJC 110k edges) and the scalar loop costs ~60 s/build across its
    # call sites — the vectorised Jacobi is the default there (the
    # byte-identity concern only ever applied to the legacy rect path).
    # ``force_scalar`` (the FINAL projection): degree-normalised Jacobi has
    # no convergence guarantee on a difference-constraint system — it stalls
    # with thousands of edges marginally over cap, while the scalar loop is
    # cyclic Gauss-Seidel POCS, which converges to a point of the (non-empty)
    # polytope (the feasibility audit measures 0-fundamental and its own POCS
    # reaches residual ~0 in <100 sweeps).  The last projection before
    # writeback therefore runs scalar — seeded by the fast Jacobi passes, so
    # it needs few sweeps.
    # (2026-07-29) legacy-gate fallback retired: the global slice is the
    # only path, so non-scalar callers always vectorize.
    _vec = not force_scalar
    _sweeps_run = 0
    _last_worst = 0.0
    # ── THE SWEEP BUDGET, DERIVED FROM THIS GRAPH (2026-08-05) ───────────
    # A sweep cap is a NON-TERMINATION GUARD, never a law quantity, and it
    # must never be what decides a surface — which is exactly what the
    # hand-set 2,400 was doing at composed SPJC+HECA.  It is derived HERE,
    # once, now that ``iter_edges`` is complete: this is the first point in
    # the call that owns the actual graph, and the three sweep paths below
    # (chromatic, vectorised Jacobi, scalar worklist) all price off it.
    # ``max_iters`` passed explicitly ⇒ the caller imposed a budget and the
    # derivation is skipped; ``_sweep_basis is None`` then tells the exit
    # report so.  Cost is O(V+E) once per projection, deliberately not
    # micro-optimised and deliberately not priced here (the wall-time arm
    # belongs to the test phase — RULINGS 2026-08-05).
    # The flat-group representatives, for the certificate's route law
    # (owner 2026-08-06): a pad is a SEATED SURFACE, never a free edge.
    _fp_reps = {rep for (rep, _g) in groups_eff} or None
    _sweep_basis = None
    _sweep_hard_cap = sweep_hard_cap
    # THE HYPER ROWS (spec §3-5): collected once, from the same entries
    # the edges come from, so a caller that passes them cannot have them
    # silently dropped — the two paths that cannot carry them REFUSE
    # below rather than solving a smaller law than they were given.
    _hyper = list(shape_constraints_hyper(shape_constraints))
    if _hyper and not (_chromatic_enabled() and iter_edges):
        raise RuntimeError(
            f"{len(_hyper)} weighted transect row(s) were handed to a "
            f"projection path that cannot carry them "
            f"(chromatic={_chromatic_enabled()}, edges={len(iter_edges)}). "
            f"Refusing rather than solving a smaller law than the caller "
            f"passed (spec transverse-hyperplane-solve-spec.md §3-5).")
    if max_iters is None:
        max_iters, _sweep_basis = derive_sweep_budget(
            iter_edges, n, _hyper)
        # CYCLE-7 FIX 1: the derived figure is the BLOCK; the exit is the
        # convergence criterion, and the only hard ceiling left is the
        # absolute anti-hang guard.  A caller that IMPOSES ``max_iters``
        # and no ceiling keeps today's semantics exactly (one block, no
        # extension) — its number is a deliberate bound, not a derivation
        # to improve on.  A caller that names BOTH (the replay ladder) is
        # asking for a stated block at a stated ceiling, and gets it.
        if _sweep_hard_cap is None:
            _sweep_hard_cap = SWEEP_BUDGET_MAX
    # CHROMATIC (graph-colored) Gauss-Seidel (Tier 3 wave 2c, survey candidate
    # 1): a numpy-vectorized TRUE Gauss-Seidel sweep that converges where the
    # Jacobi stalls, so it replaces BOTH legacy inner paths — the
    # ``force_scalar`` final projection (the 2400-sweep worklist) AND the
    # mid-solve vectorised Jacobi.  A DIFFERENT legal fixpoint than the FIFO
    # worklist (counts-not-worse, not byte-identical) — gate ``O4_CHROMATIC_
    # PROJECTION`` (default ON); OFF falls straight through to the legacy split
    # below, byte-identically.  The closed-form chain pre-pass (survey candidate
    # 2) warm-starts 1-D substructures exactly before the sweep.
    if _chromatic_enabled() and iter_edges:
        _chain_prepass = _chain_prepass_enabled()
        _chain_count = 0
        if _chain_prepass:
            _chain_count = _project_chain_prepass(elev, iter_edges, n, immovable)
        _chroma_stats: dict = {}
        # Incremental coloring across the lazy rounds (perf 2026-07-18,
        # partition-identical): expansion only APPENDS to ``iter_edges`` and
        # the greedy coloring is prefix-stable, so the carried state colors
        # just the appended suffix each round instead of the whole grown set.
        _coloring_state: dict = {}
        _project_chromatic(elev, iter_edges, n, max_iters, tol,
                           interval_bounds_by_index, stats=_chroma_stats,
                           coloring_state=_coloring_state,
                           node_box=bound_of or None,
                           raw_budget_by_index=iter_raw_budget,
                           sweep_budget_basis=_sweep_basis,
                           family_by_pair=fam_by_pair,
                           sweep_hard_cap=_sweep_hard_cap,
                           flat_group_reps=_fp_reps,
                           hyper_rows=_hyper, hard_nodes=immovable)
        # Lazy shapes: as for the Jacobi path, only the FINAL state matters for
        # a certificate, so re-warm + re-sweep on the grown edge set until no
        # further shape expands (bounded: each round expands ≥1 entry).
        while lazy_entries_pending:
            still_pending = []
            expanded_any = False
            for lazy_entry in lazy_entries_pending:
                if "lazy_expand" not in lazy_entry:
                    continue
                if _lazy_nodes_moved(lazy_entry):
                    _expand_lazy_entry_into_projection(lazy_entry)
                    expanded_any = True
                else:
                    still_pending.append(lazy_entry)
            lazy_entries_pending = still_pending
            if not expanded_any:
                break
            if _chain_prepass:
                _project_chain_prepass(elev, iter_edges, n, immovable)
            # RE-DERIVE: a lazy round only APPENDS edges, so the graph the
            # next sweep faces can be strictly larger (and its diameter
            # strictly longer) than the one the budget was priced from.
            # Re-deriving keeps the guard above the graph it is guarding.
            if _sweep_basis is not None:
                max_iters, _sweep_basis = derive_sweep_budget(iter_edges, n)
                if sweep_hard_cap is None:
                    _sweep_hard_cap = SWEEP_BUDGET_MAX
            _project_chromatic(elev, iter_edges, n, max_iters, tol,
                               interval_bounds_by_index, stats=_chroma_stats,
                               coloring_state=_coloring_state,
                               node_box=bound_of or None,
                               raw_budget_by_index=iter_raw_budget,
                               sweep_budget_basis=_sweep_basis,
                               family_by_pair=fam_by_pair,
                               sweep_hard_cap=_sweep_hard_cap,
                               flat_group_reps=_fp_reps,
                               hyper_rows=_hyper, hard_nodes=immovable)
        _sweeps_run = _chroma_stats.get("sweeps", 0)
        _last_worst = _chroma_stats.get("worst", 0.0)
        if _os.environ.get("O4_STEP_DEBUG") == "1":
            print(f"    [fp-chromatic] colors={_chroma_stats.get('colors')} "
                  f"edges={_chroma_stats.get('edges')} "
                  f"sweeps={_sweeps_run} "
                  f"avoided={_chroma_stats.get('sweeps_avoided')} "
                  f"certified={_chroma_stats.get('certified')} "
                  f"chains={_chain_count} worst={_last_worst:.4f}")
    elif _vec and iter_edges:
        _project_vectorized(elev, iter_edges, n, max_iters, tol,
                            interval_bounds_by_index,
                            node_box=bound_of or None)
        # Lazy shapes under the vectorised Jacobi: only the FINAL state
        # matters for the certificate (a shape whose nodes END at their seed
        # has its body pairs satisfied at that seed, transient wiggles
        # notwithstanding), so movement is checked after each pass and the
        # projection re-run on the grown edge set until no further shape
        # expands — the same fixpoint the scalar worklist reaches
        # edge-by-edge.  Bounded: each round expands ≥1 entry, entries are
        # finite.
        while lazy_entries_pending:
            still_pending = []
            expanded_any = False
            for lazy_entry in lazy_entries_pending:
                if "lazy_expand" not in lazy_entry:
                    continue
                if _lazy_nodes_moved(lazy_entry):
                    _expand_lazy_entry_into_projection(lazy_entry)
                    expanded_any = True
                else:
                    still_pending.append(lazy_entry)
            lazy_entries_pending = still_pending
            if not expanded_any:
                break
            _project_vectorized(elev, iter_edges, n, max_iters, tol,
                                interval_bounds_by_index,
                                node_box=bound_of or None)
    else:
        # WORKLIST Gauss-Seidel (perf 2026-07-04): the cyclic sweep
        # re-examined EVERY edge up to ``max_iters`` times even when
        # 99 % start satisfied (flat airports: KDFW relief 0.485 % —
        # nearly the whole graph is law-true at the DEM seed).  An
        # edge only needs re-checking after one of its endpoints
        # MOVED, so the queue shrinks to the violation neighbourhoods
        # and the work scales with terrain difficulty, not graph
        # size.  Deterministic: initial order = edge order, FIFO
        # requeue.  The visit cap equals the old worst-case work
        # bound (max_iters full sweeps), so pathological cyclic
        # systems terminate exactly as before.
        # ``incident`` as a per-node list-of-lists indexed by node index
        # (0..n-1) rather than a dict: every edge endpoint is a canonical node
        # < n, so a plain list gives the same per-node adjacency (identical
        # insertion order = edge order) at list-subscript speed instead of a
        # dict hash+get on the hot re-enqueue path.  New lazy-expansion edges
        # reference existing nodes (< n), so their sublists already exist.
        incident: list = [None] * n
        for edge_index in range(len(iter_edges)):
            i = iter_edges[edge_index][0]
            j = iter_edges[edge_index][1]
            li = incident[i]
            if li is None:
                incident[i] = [edge_index]
            else:
                li.append(edge_index)
            lj = incident[j]
            if lj is None:
                incident[j] = [edge_index]
            else:
                lj.append(edge_index)
        from collections import deque
        pending = deque(range(len(iter_edges)))
        in_pending = bytearray(len(iter_edges))
        for edge_index in pending:
            in_pending[edge_index] = 1
        visits = 0
        visit_cap = max_iters * max(1, len(iter_edges))
        # RE-ENTRY DIAGNOSTIC (O4_FP_REENTRY_DEBUG=1, off by default → zero
        # cost and byte-identical): counts pops / no-op pops / moves keyed by
        # edge kind (interval vs symmetric) plus per-edge pop tallies, so the
        # livelock re-entry mechanism can be read off a single gate-ON build
        # (Slice B stage B3 prerequisite trace).  ``force_scalar`` only.
        _reentry_dbg = _os.environ.get("O4_FP_REENTRY_DEBUG") == "1"
        if _reentry_dbg:
            _pops_sym = _pops_int = 0
            _noop_sym = _noop_int = 0
            _edge_pops = [0] * len(iter_edges)
        # HOT-LOOP LOCALS (perf 2026-07-15, byte-identical): bind the bound
        # deque methods to locals and re-index the interval bounds as a
        # parallel list keyed by ``iter_edges`` position (the same key the dict
        # used), so each visit pays a list subscript instead of a deque/dict
        # attribute + hash lookup.  Every interval edge is created before the
        # loop, so a fixed-length list covers every ``budget is None`` index;
        # lazy-expansion edges are symmetric (budget not None) and never index
        # this list.  ``incident`` is now a per-node list (built above), so the
        # re-enqueue reads ``incident[node]`` directly (``None`` = no edges).
        pending_popleft = pending.popleft
        pending_append = pending.append
        # ``interval_bounds_by_index`` is a dict keyed by ``iter_edges``
        # position; re-index it as a parallel list so the hot loop pays a list
        # subscript instead of a dict hash+get on every interval visit.  All
        # interval edges are created before the loop, so a fixed-length list
        # covers every ``budget is None`` index; lazy-expansion edges are
        # symmetric (``budget`` not ``None``) and never index this list.
        # Each slot also carries the tolerance-shifted comparands
        # ``s_low - tol`` / ``s_high + tol`` precomputed ONCE (identical
        # operands ⇒ identical IEEE result ⇒ bit-identical to the inline
        # ``s_high + tol`` / ``s_low - tol``), so the no-op fast-path (the
        # dominant visit class) skips two float additions per interval pop.
        _interval_bounds = [None] * len(iter_edges)
        for _bi, (_sl, _sh) in interval_bounds_by_index.items():
            _interval_bounds[_bi] = (
                _sl, _sh,
                None if _sl is None else _sl - tol,
                None if _sh is None else _sh + tol)
        while pending and visits < visit_cap:
            edge_index = pending_popleft()
            in_pending[edge_index] = 0
            visits += 1
            i, j, budget, kind = iter_edges[edge_index]
            if _reentry_dbg:
                _edge_pops[edge_index] += 1
                if budget is None:
                    _pops_int += 1
                else:
                    _pops_sym += 1
            if budget is None:
                # INTERVAL EDGE (Stage B0): project the difference onto the
                # signed slab ``[s_low, s_high]``.  ``se`` is the SIGNED excess
                # (positive ⇒ z_i − z_j above the ceiling, reduce it; negative
                # ⇒ below the floor, raise it), so the same endpoint-weight
                # split as the symmetric case applies with ``se`` in place of
                # ``s·ex``.  A ``None`` side imposes no bound on that direction.
                s_low, s_high, s_low_tol, s_high_tol = \
                    _interval_bounds[edge_index]
                d = elev[i] - elev[j]
                if s_high is not None and d > s_high_tol:
                    se = d - s_high
                elif s_low is not None and d < s_low_tol:
                    se = d - s_low
                else:
                    if _reentry_dbg:
                        _noop_int += 1
                    continue
                if kind == 0:
                    elev[i] -= se * 0.5
                    elev[j] += se * 0.5
                    moved = (i, j)
                elif kind == 1:
                    elev[j] += se                      # i fixed → move j
                    moved = (j,)
                else:
                    elev[i] -= se                      # j fixed → move i
                    moved = (i,)
                ex = -se if se < 0.0 else se
                if ex > _last_worst:
                    _last_worst = ex
            else:
                d = elev[i] - elev[j]
                ad = -d if d < 0.0 else d              # inline abs() (hot path)
                if ad <= budget + tol:
                    if _reentry_dbg:
                        _noop_sym += 1
                    continue
                ex = ad - budget
                s = 1.0 if d > 0 else -1.0
                if kind == 0:
                    elev[i] -= s * ex * 0.5
                    elev[j] += s * ex * 0.5
                    moved = (i, j)
                elif kind == 1:
                    elev[j] += s * ex                  # i fixed → move j up to i
                    moved = (j,)
                else:
                    elev[i] -= s * ex                  # j fixed → move i
                    moved = (i,)
                if ex > _last_worst:
                    _last_worst = ex
            if bound_of:
                # BOUNDED YIELD (owner ruling 2026-07-29): clamp every moved
                # node back into its feasibility box; the incident-edge
                # re-enqueue below re-relaxes its edges against the clamped
                # value, so a box conflict ends as a reported over-cap edge,
                # never as a seat dragged outside its interval.
                for moved_node in moved:
                    bb = bound_of.get(moved_node)
                    if bb is not None:
                        if elev[moved_node] < bb[0]:
                            elev[moved_node] = bb[0]
                        elif elev[moved_node] > bb[1]:
                            elev[moved_node] = bb[1]
            for moved_node in moved:
                nbrs = incident[moved_node]
                if nbrs is not None:
                    for neighbour_edge in nbrs:
                        if not in_pending[neighbour_edge]:
                            in_pending[neighbour_edge] = 1
                            pending_append(neighbour_edge)
            # MID-CALL lazy expansion: this node just moved — if it belongs
            # to still-certified shapes AND the move exceeds the entry's
            # slack-aware tolerance, the seed premise is gone; generate the
            # full pair set and enqueue the new edges (kind recomputed
            # against the SAME ``immovable`` set).  A move WITHIN the slack
            # keeps the entry lazy and still watched (the mapping is only
            # dropped once expanded), so a later larger drift re-triggers.
            if lazy_entries_by_node:
                for moved_node in moved:
                    entries_here = lazy_entries_by_node.get(moved_node)
                    if not entries_here:
                        continue
                    still_watching = []
                    for lazy_entry in entries_here:
                        if "lazy_expand" not in lazy_entry:
                            continue        # expanded via another node
                        if not _lazy_nodes_moved(lazy_entry):
                            still_watching.append(lazy_entry)
                            continue        # within certificate slack
                        for new_edge_index in \
                                _expand_lazy_entry_into_projection(lazy_entry):
                            edge_a, edge_b, _b2, _k2 = \
                                iter_edges[new_edge_index]
                            _la = incident[edge_a]
                            if _la is None:
                                incident[edge_a] = [new_edge_index]
                            else:
                                _la.append(new_edge_index)
                            _lb = incident[edge_b]
                            if _lb is None:
                                incident[edge_b] = [new_edge_index]
                            else:
                                _lb.append(new_edge_index)
                            in_pending.append(1)
                            pending_append(new_edge_index)
                    if still_watching:
                        lazy_entries_by_node[moved_node] = still_watching
                    else:
                        lazy_entries_by_node.pop(moved_node, None)
        _sweeps_run = visits
        if _reentry_dbg:
            _capped = visits >= visit_cap
            _n_int = len(interval_bounds_by_index)
            print(f"    [fp-reentry] visits={visits} cap={visit_cap} "
                  f"capped={_capped} edges={len(iter_edges)} "
                  f"interval_edges={_n_int}")
            print(f"    [fp-reentry] pops sym={_pops_sym} int={_pops_int} | "
                  f"no-op sym={_noop_sym} int={_noop_int} | "
                  f"moves sym={_pops_sym - _noop_sym} "
                  f"int={_pops_int - _noop_int}")
            # Top re-entered edges (by pop count), split by kind, to name the
            # ping-pong participants.
            _ranked = sorted(range(len(iter_edges)),
                             key=lambda e: _edge_pops[e], reverse=True)
            print("    [fp-reentry] top-20 re-entered edges "
                  "(idx kind i j budget pops):")
            for _e in _ranked[:20]:
                _ei, _ej, _eb, _ek = iter_edges[_e]
                _kind_s = "INT" if _eb is None else "sym"
                _bud_s = (repr(interval_bounds_by_index.get(_e))
                          if _eb is None else repr(round(_eb, 3)))
                print(f"        {_e} {_kind_s} i={_ei} j={_ej} "
                      f"bounds={_bud_s} pops={_edge_pops[_e]}")
            # How many INTERVAL edges were popped more than twice (the
            # re-admission / ping-pong signature).
            _int_reenter = sum(1 for _e in range(len(iter_edges))
                               if iter_edges[_e][2] is None
                               and _edge_pops[_e] > 2)
            _sym_reenter = sum(1 for _e in range(len(iter_edges))
                               if iter_edges[_e][2] is not None
                               and _edge_pops[_e] > 2)
            print(f"    [fp-reentry] edges popped >2x: "
                  f"interval={_int_reenter} symmetric={_sym_reenter}")
    # broadcast each flat group's representative level back to its members.
    for rep, g in (groups_eff if flat_groups else ()):
        for m in g:
            elev[m] = elev[rep]
    # final tally — against the RAW budget (the true law), NOT the margined
    # sweep budget: the margin tightens enforcement only, never reporting.
    rem = bh = 0
    worst_ex = 0.0
    for (i, j, budget, _sweep_budget) in edges:
        ex = abs(elev[i] - elev[j]) - budget
        if ex > tol:
            rem += 1
            worst_ex = max(worst_ex, ex)
            if i in hard and j in hard:
                bh += 1
    # INTERVAL EDGES (Stage B0) tally against their RAW signed bounds (the true
    # law), each ``None`` side never violated.  ``ex`` is the signed slab excess
    # (how far ``z_i − z_j`` sits outside ``[raw_low, raw_high]``).
    for (i, j, raw_low, raw_high, _sl, _sh) in interval_edges:
        d = elev[i] - elev[j]
        if raw_high is not None and d - raw_high > tol:
            ex = d - raw_high
        elif raw_low is not None and raw_low - d > tol:
            ex = raw_low - d
        else:
            continue
        rem += 1
        worst_ex = max(worst_ex, ex)
        if i in hard and j in hard:
            bh += 1
    # ── THE RESOLUTION IS CERTIFIED AT EXIT (cycle-6 Part P) ─────────
    # A conflict resolved BAND WINS is only resolved if the node LEAVES
    # this projection inside the band it was given.  Reported ungated,
    # with the worst deficit named: the whole defect this clause fixes
    # was 14 nodes exiting 82–88 m below their own band floor, so a
    # silent re-appearance must be impossible to miss.  Read-only.
    if _band_wins:
        _bw_below = []
        for _bi, (_blo, _bhi) in _band_wins.items():
            _bd = _blo - elev[_bi]
            if _bd > tol:
                _bw_below.append((_bd, _bi))
        _bw_below.sort(reverse=True)
        import O4_UI_Utils as _UI_bw
        _UI_bw.vprint(1,
            f"    [env-band] conflict resolution EXIT "
            f"{_node_space_stamp(n)}: "
            f"{len(_band_wins)} band-bound node(s), "
            f"{len(_band_wins) - len(_bw_below)} at or above their band "
            f"floor, {len(_bw_below)} BELOW"
            + ("" if not _bw_below else
               f" (worst {_bw_below[0][0]:.3f} m at node "
               f"{_bw_below[0][1]} [{_NODE_SPACE_FP_REMAPPED}])"))
    if _os.environ.get("O4_STEP_DEBUG") == "1" and force_scalar:
        print(f"    [fp-scalar] sweeps={_sweeps_run} last_worst={_last_worst:.4f} "
              f"rem={rem} worst_ex={worst_ex:.3f} groups={len(groups_eff)} "
              f"broken={len(broken)}")
    return rem, bh


def one_profile_solve(
        elev, shape_constraints, base_hard, nodes, dem_elev,
        runway_nodes, building_seats, apron_body, spine_nodes, spine_adj,
        node_band, spine_floor, coupling, *,
        max_sweeps=None, tol=0.001,
        omega=None, curvature=0.25,
        apron_smooth=None):
    """Run the one-profile solve.  Mutates ``elev`` in place; returns #free nodes.

    ``base_hard`` — runway + seam HARD mask (anchors at their seeded elevation).
    ``runway_nodes`` — runway / runway-crossing node indices (anchors).
    ``building_seats`` — ``{pad_node: flat_level}`` (anchors, the heaviest).
    ``dem_elev`` — per-node DEM (the closest-to-DEM target).
    ``node_band`` — per-node ``(floor, ceiling)`` reachability from THE ONE graph
      (``building_feasibility.reach_band_unified`` — the SAME band that
      sets the building levels, so building and apron/spine agree by construction)
      or ``None`` (off-network → unconstrained, the neighbour cap slabs bound it).
    ``coupling`` — rect flat-end groups (members share one elevation).
    """
    n = len(elev)
    if omega is None:
        omega = float(_os.environ.get("O4_RP_OMEGA", "1.0"))
    # Apron body target: closest-to-DEM (default) vs SMOOTH (grade between the
    # apron's anchored edges + spine — user model "aprons grade building→edge/
    # spine, NOT DEM").
    # (``O4_RP_APRON_SMOOTH`` deleted 2026-08-05 — the fallback was
    # unreachable: the sole production caller passes ``apron_smooth=True``,
    # which is the owner model "aprons grade building->edge/spine, NOT DEM".)
    _apron_smooth = True if apron_smooth is None else bool(apron_smooth)
    adj = _build_adjacency(shape_constraints, n)
    if not adj:
        return 0
    # THE SWEEP BUDGET, DERIVED FROM THIS GRAPH (2026-08-05).  Same law as
    # ``feasibility_project``: this body relaxation also propagates one law
    # edge per sweep, so its guard is priced off the same hop-diameter
    # bound rather than off a hand-set constant.  ``adj`` is the law-edge
    # graph, flattened to the ``(i, j)`` pairs the bound reads.
    if max_sweeps is None:
        max_sweeps, _ = derive_sweep_budget(
            [(i, j) for i, incident in adj.items() for (j, _lim) in incident],
            n)

    # ANCHORS — fixed elevations: runway contacts, tile seams, and the building
    # pads (the heaviest, flat at their FRONTAGE-reachable level).  Everything
    # else is bounded by ``node_band`` (the ONE taxi-route reach band) and graded
    # ≤cap to its neighbours by the projection — the apron rises to the building
    # it fronts through the shared frontage edge (a neighbour cap slab), so no
    # second reachability graph is needed.
    anchors: dict = {}
    for i in range(n):
        if base_hard[i]:
            anchors[i] = elev[i]
    for i in runway_nodes:
        if i < n:
            anchors[i] = elev[i]
    for i, lv in building_seats.items():            # buildings win (heaviest)
        if lv is not None and i < n:
            elev[i] = float(lv)
            anchors[i] = float(lv)

    # Per-node reachability bounds from the ONE graph (the reach band) — applied
    # to EVERY node, the apron body included (user 2026-06-26): an apron node sits
    # at CLOSEST-DEM-FEASIBLE = its DEM clamped into [floor, ceiling], so a
    # wrong-LOW DEM fills UP to the floor (the west apron 662–685 → ~693) and a
    # wrong-HIGH DEM pulls DOWN to the ceiling (#156's terminal 715 → 707–710,
    # graded toward runway 02).  The apron does NOT inherit the band ceiling's 3 %
    # climb directly because the within-shape 1 % NEIGHBOUR cap slab (below) also
    # bounds each node — so it grades ≤1 % within the band, exactly the model.
    floor: dict = {}
    ceil: dict = {}
    for i in range(n):
        b = node_band[i] if i < len(node_band) else None
        if b is not None:
            lo, hi = b
            if lo > hi:                              # rare band inversion
                lo = hi = 0.5 * (lo + hi)
            floor[i], ceil[i] = lo, hi
    # BUILDING-FRONTAGE SPINE FLOORS (user 2026-06-25): the serving spine RISES
    # to serve its pads.  ``spine_floor`` is a cap-LIPSCHITZ floor propagated
    # along the consecutive centerline chain from each building's foot anchor
    # (``anchors.building_spine_floor``) — decreasing at exactly the cap rate, so
    # it is grade-consistent BY CONSTRUCTION and can never force a spine break.
    # Because each chain node's neighbour is also floored, the "envelope yields"
    # fallback below no longer drops it (the single-node floor it replaced was
    # dropped whenever the flat runway-side neighbour capped it low → arm stayed
    # flat, CYXY ~U12 694.5 vs building19 700.2).
    for i, f in spine_floor.items():
        if i < n:
            hi = ceil.get(i, _INF)
            cur = floor.get(i, -_INF)
            ff = min(f, hi) if hi < _INF else f
            if ff > cur:
                floor[i] = ff

    free = [k for k in adj if k not in anchors]
    if not free:
        return 0
    free_set = set(free)

    # inverse-budget² weights for the ROUTE (smoothness / min-curvature) target.
    wadj: dict = {}
    for i in free:
        wadj[i] = [(j, lim, 1.0 / max(lim, 1e-3) ** 2) for (j, lim) in adj[i]]
    # SPINE nodes clamp ONLY to their centerline-CONSECUTIVE neighbours (a 1-D,
    # always-feasible chain within the envelope) — so the apron body yields to
    # the spine instead of squeezing it out of grade.  Consecutive-only is
    # essential: pulling in the non-consecutive within-shape spine pairs
    # re-couples the spine to the apron squeeze it must stay clear of.
    wspine: dict = {}
    for i in spine_nodes:
        if i in free_set:
            nb = [(j, lim, 1.0 / max(lim, 1e-3) ** 2)
                  for (j, lim) in spine_adj.get(i, ())
                  if j in free_set or j in anchors]
            if nb:
                wspine[i] = nb

    def _dem_target(i):
        """Closest-to-DEM within the node's reachable envelope (the APRON BODY
        target).  Midpoint when DEM is missing or the envelope is degenerate."""
        lo = floor.get(i, -_INF)
        hi = ceil.get(i, _INF)
        de = dem_elev[i] if i < len(dem_elev) else None
        if lo > hi:                                  # unreachable conflict
            return 0.5 * (lo + hi)
        if de is None:
            if lo == -_INF or hi == _INF:
                return elev[i]                       # unconstrained → hold seed
            return 0.5 * (lo + hi)
        return min(max(de, lo), hi)

    # INITIALISE every free node at its closest-DEM-in-envelope value (a warm
    # start near the answer; route nodes then smooth toward min curvature).
    for i in free:
        elev[i] = _dem_target(i)

    # Coupled groups (rect flat-ends) restricted to free members.
    groups: list = []
    seen_g: set = set()
    for i in free:
        grp = coupling.get(i)
        if not grp or i in seen_g:
            continue
        members = [m for m in grp if m in free_set]
        for m in grp:
            seen_g.add(m)
        if len(members) > 1:
            groups.append(members)

    # ── THE SWEEP PLAN (perf P3 lane H) ───────────────────────────────
    # The Gauss-Seidel body below is the solve's hottest pure-Python loop
    # (P1 HECA: ~25 s of ``one_profile_solve`` SELF time on four lines).
    # Everything it re-derived per node PER SWEEP is loop-invariant:
    # ``wspine.get(i)`` / ``wadj[i]`` select the SAME neighbour list every
    # sweep, ``sum(w)`` over that list is the same sum in the same order,
    # ``len(lst)`` is the same length, and ``floor``/``ceil`` are not
    # written anywhere inside the sweep.  Derive them ONCE, in ``free``
    # order, so the Gauss-Seidel visit order — which IS part of the
    # answer — is byte-for-byte the order it was.
    #
    # BIT-EXACTNESS, the only thing that matters here:
    #   * ``sw`` accumulates the same ``w`` values in the same list order,
    #     just earlier, so it is the same double.
    #   * the three passes over ``lst`` (weighted mean, plain mean,
    #     neighbour cap slab) MERGE into one.  Nothing in the loop body
    #     writes ``elev[j]`` for a neighbour ``j`` — only ``elev[i]``,
    #     after all three passes — so each pass read exactly the values
    #     the merged pass reads, and ``acc`` still adds its own terms
    #     left-to-right in list order.
    #   * the plain mean's ``sum(...)`` IS KEPT (see the note at ``pm``):
    #     it is compensated, and a running ``+=`` is a different number.
    #   * ``1.0 - curvature`` is hoisted: one subtraction, same value.
    _plan = []
    for i in free:
        spine = wspine.get(i)
        _is_spine = spine is not None
        lst = spine if _is_spine else wadj[i]
        _sw = 0.0
        for (_pj, _pl, _pw) in lst:
            _sw += _pw
        _plan.append((i, lst, _sw, len(lst),
                      floor.get(i, -_INF), ceil.get(i, _INF), _is_spine,
                      (not _is_spine) and i in apron_body
                      and not _apron_smooth))
    _one_minus_curv = 1.0 - curvature

    moved = _INF
    for _it in range(max_sweeps):
        moved = 0.0
        for (i, lst, sw, n_lst, f_i, c_i, _is_spine, _dem_body) in _plan:
            # neighbour cap slab (spine: centerline chain only; else all edges)
            n_lo, n_hi = -_INF, _INF
            if _dem_body:
                tgt = _dem_target(i)                 # apron body → closest-DEM
                for (j, lim, _w) in lst:
                    ej = elev[j]
                    if ej - lim > n_lo:
                        n_lo = ej - lim
                    if ej + lim < n_hi:
                        n_hi = ej + lim
            else:
                # spine + rect ends → smoothest (min curvature): inverse-budget²
                # harmonic mean blended with the plain mean.
                acc = 0.0
                vals = []
                _app = vals.append
                for (j, lim, w) in lst:
                    ej = elev[j]
                    acc += ej * w
                    _app(ej)
                    if ej - lim > n_lo:
                        n_lo = ej - lim
                    if ej + lim < n_hi:
                        n_hi = ej + lim
                harm = acc / sw if sw > 0 else elev[i]
                # ``sum`` STAYS ``sum`` — CPython's builtin runs Neumaier
                # COMPENSATED summation on an all-float sequence, so a
                # hand-rolled ``pacc += ej`` is a DIFFERENT number (the
                # lane's twin caught it on 9 of 25 random neighbour
                # lists).  The gather is what the merge buys: the values
                # are read once, here, instead of a second generator pass
                # re-indexing ``elev``; ``sum`` then sees the same floats
                # in the same order and compensates them identically.
                pm = sum(vals) / n_lst
                tgt = _one_minus_curv * harm + curvature * pm
            lo_e = max(n_lo, f_i)
            hi_e = min(n_hi, c_i)
            if lo_e > hi_e and _is_spine:
                # the 1-D spine chain is paramount: where the DEM-reach envelope
                # conflicts with the centerline within-grade, the envelope YIELDS
                # (the apron/building frontage takes the step, not the spine).
                lo_e, hi_e = n_lo, n_hi
            if lo_e <= hi_e:
                tgt = min(max(tgt, lo_e), hi_e)
            else:
                tgt = 0.5 * (lo_e + hi_e)            # locally over-constrained
            d = omega * (tgt - elev[i])
            if d:
                elev[i] = elev[i] + d
                if abs(d) > moved:
                    moved = abs(d)
        if moved < tol:
            break
    # Equalise each rect flat-end group ONCE at convergence (the cap=0 cross
    # edges hold them near-equal during iteration; this cleans the sub-mm
    # residual so the rect emits as an exact tilted plane).  A spine node in the
    # group is AUTHORITATIVE — the rect corner conforms to the spine (averaging
    # would pull the spine off its solved profile → a spine grade break); a group
    # with several spine nodes uses their mean (already ≤cap along the chain).
    for members in groups:
        sp = [m for m in members if m in spine_nodes]
        src = sp if sp else members
        mv = sum(elev[m] for m in src) / len(src)
        for m in members:
            elev[m] = mv

    if _os.environ.get("O4_STEP_DEBUG") == "1":
        _report_residual(elev, adj, nodes, free_set, building_seats,
                         runway_nodes, base_hard, floor, ceil, n,
                         _it + 1, moved)
        # SPINE residual (internal, pre-writeback): how many centerline-
        # consecutive pairs are still over cap in the solved field.
        sworst: list = []
        seen_s: set = set()
        for i, lst in spine_adj.items():
            for (j, w) in lst:
                e = (min(i, j), max(i, j))
                if e in seen_s:
                    continue
                seen_s.add(e)
                ex = abs(elev[i] - elev[j]) - w
                if ex > 1e-3:
                    sworst.append((ex, i, j, elev[i], elev[j], w))
        sworst.sort(reverse=True)
        big = [s for s in sworst if s[0] > 0.05]      # ignore convergence noise
        print(f"  [one-profile] internal spine residual: {len(big)} pair(s) "
              f">0.05m ({len(sworst)} total)")
        for (ex, i, j, ei, ej, w) in big[:6]:
            print(f"    [spine-resid] {i}@({nodes[i][0]:.0f},{nodes[i][1]:.0f})"
                  f"={ei:.2f} {j}@({nodes[j][0]:.0f},{nodes[j][1]:.0f})={ej:.2f}"
                  f" budget={w:.2f} ex={ex:.2f}m")
    return len(free)


def _report_residual(elev, adj, nodes, free_set, building_seats, runway_nodes,
                     base_hard, floor, ceil, n, sweeps, moved):
    """O4_STEP_DEBUG diagnostics: residual over-cap edges + envelope coverage."""
    def _typ(k):
        if k in building_seats:
            return "bldg"
        if k >= n or k in runway_nodes:
            return "rwy"
        if base_hard[k]:
            return "seam"
        return "free"
    seen: set = set()
    bh = hf = 0
    worst: list = []
    for i in adj:
        for (j, lim) in adj[i]:
            e = (min(i, j), max(i, j))
            if e in seen:
                continue
            seen.add(e)
            ex = abs(elev[i] - elev[j]) - lim
            if ex > 1e-3:
                if (i not in free_set) and (j not in free_set):
                    bh += 1
                else:
                    hf += 1
                d = math.hypot(nodes[i][0] - nodes[j][0],
                               nodes[i][1] - nodes[j][1])
                worst.append((ex, _typ(i), _typ(j), d, elev[i], elev[j], lim))
    worst.sort(reverse=True)
    n_inv = sum(1 for k in free_set
                if floor.get(k, -_INF) > ceil.get(k, _INF))
    print(f"  [one-profile] {len(free_set)} free node(s), {sweeps} sweep(s), "
          f"anchors={len(base_hard) and sum(base_hard)}+bldg{len(building_seats)} "
          f"moved={moved:.4f}; band-inverted={n_inv}; "
          f"residual edges both-hard={bh} has-free={hf}")
    from collections import Counter
    c = Counter((t1, t2) for (_e, t1, t2, *_r) in worst)
    print(f"    [resid by type] {dict(c)}")
    for (ex, t1, t2, d, ei, ej, lim) in worst[:12]:
        print(f"    [resid] {t1}/{t2} ex={ex:.2f}m d={d:.1f}m "
              f"lev {ei:.1f}/{ej:.1f} lim={lim:.2f}")
