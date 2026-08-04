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

_INF = float("inf")

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
ENVELOPE_FROM_BAND_DEFAULT = "0"
ROUTE_METRIC_ENVELOPE_DEFAULT = "1"


def route_metric_envelope_enabled() -> bool:
    """True when ``O4_ROUTE_METRIC_ENVELOPE`` is on (default ``"1"`` since
    the 2026-08-04 kill-half flip; ``O4_ROUTE_METRIC_ENVELOPE=0`` restores
    the pair-closure envelope).

    THE one reader of this flag's default."""
    return (_os.environ.get("O4_ROUTE_METRIC_ENVELOPE",
                            ROUTE_METRIC_ENVELOPE_DEFAULT) == "1")


def envelope_from_band_enabled() -> bool:
    """True when the feasibility envelope reads THE reach band.

    THE one reader of ``O4_ENVELOPE_FROM_BAND``'s default (``"0"``).  The
    route-metric gate implies it: that spec's §1 fix is precisely "every
    pass, including the final, runs its envelope on the band"."""
    return (route_metric_envelope_enabled()
            or _os.environ.get("O4_ENVELOPE_FROM_BAND",
                               ENVELOPE_FROM_BAND_DEFAULT) == "1")


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
_FP_VECTORIZE = _os.environ.get("O4_FP_VECTORIZE", "0") == "1"

# Floor for the emit-quantization margin (see ``_margined_budget``): a budget
# at or below this is NEVER reduced.  Rect flat-cross edges are budget 0 BY
# DESIGN (the two corners stay equal) and must stay 0; and margining a
# coincident / sub-0.1 m chord's already-tiny budget toward 0 would make the
# projection try to FLATTEN genuinely-distinct close vertices, fighting the
# hard anchors.
_QUANT_MARGIN_FLOOR_M = 0.005


def _emit_quantization_margin():
    """The solver-side emit-quantization margin (metres) — lazy config read
    (one_solve keeps config imports call-time, matching the module style)."""
    try:
        from auto_patch.config import EMIT_QUANTIZATION_MARGIN_M
        return EMIT_QUANTIZATION_MARGIN_M
    except Exception:
        return 0.0


def _margined_budget(lim, margin):
    """SWEEP budget for a raw edge budget ``lim``: ``lim − margin``, floored.

    ``to_osm`` rounds each emitted elevation to the 0.01 m grid, so a pair's
    emitted |Δelev| can exceed the solved one by up to one full grid step —
    a pair solved exactly AT its budget then reads over the law in the
    emitted file (config.EMIT_QUANTIZATION_MARGIN_M has the full story).
    Enforcing ``lim − margin`` in the sweeps keeps the ROUNDED values inside
    the raw law.  Budgets at or below ``_QUANT_MARGIN_FLOOR_M`` pass through
    unchanged (0-budget flat-cross edges stay 0), and no budget is ever
    reduced below that floor.  ``margin ≤ 0`` (O4_QUANT_MARGIN=0) returns
    ``lim`` → byte-identical pre-margin behaviour."""
    if margin <= 0.0 or lim <= _QUANT_MARGIN_FLOOR_M:
        return lim
    reduced = lim - margin
    return reduced if reduced > _QUANT_MARGIN_FLOOR_M else _QUANT_MARGIN_FLOOR_M


def _margined_interval(interval_low, interval_high, margin):
    """SWEEP bounds for a SIGNED INTERVAL edge (Stage B0, docs/slice_b_solver_
    absorption_design.md): ``interval_low ≤ (z_i − z_j) ≤ interval_high`` with
    either side ``None`` (that side unbounded — a ``None`` ceiling permits any
    rise, a ``None`` floor any drop; the adjacent-ground envelope law's own
    semantics).

    Emit-quantization margin rule (generalises ``_margined_budget``): shrink
    each FINITE side INWARD by ``margin`` so the 0.01 m-rounded emitted
    difference still fits the raw interval — the ceiling moves DOWN
    (``high − margin``), the floor moves UP (``low + margin``), regardless of
    the side's sign (a positive floor 2.0 is still narrowed inward to 2.1).
    ``None`` sides are left untouched (an unbounded side cannot round out of
    the law).  ``_QUANT_MARGIN_FLOOR_M`` floor semantics carry over from the
    symmetric case:
      * a finite side whose magnitude is at or below the floor is left alone
        (mirrors ``_margined_budget`` passing a ≤-floor budget through — a
        near-zero bound stays enforceable rather than being narrowed away);
      * a two-sided interval is never narrowed tighter than the floor WIDTH
        (``2·_QUANT_MARGIN_FLOOR_M``): if the two shrinks would meet or invert,
        the interval collapses to ``[midpoint ∓ _QUANT_MARGIN_FLOOR_M]``
        (mirrors ``_margined_budget`` never reducing a symmetric half-width
        below the floor).
    ``margin ≤ 0`` returns the bounds unchanged.  The symmetric slab
    ``(−budget, +budget)`` fed through this yields ``(−(budget−margin),
    +(budget−margin))`` — identical to ``_margined_budget`` on both sides — but
    symmetric edges NEVER pass through here (they keep the untouched
    ``_margined_budget`` fast path), so symmetric behaviour is byte-identical by
    construction."""
    if margin <= 0.0:
        return interval_low, interval_high
    # A two-sided interval already at or under the floor WIDTH is left entirely
    # unchanged (mirrors ``_margined_budget`` passing a ≤-floor budget through):
    # a genuinely tight slab stays enforceable rather than being narrowed away
    # or widened.
    if (interval_low is not None and interval_high is not None
            and interval_high - interval_low <= 2.0 * _QUANT_MARGIN_FLOOR_M):
        return interval_low, interval_high
    new_high = interval_high
    if interval_high is not None and abs(interval_high) > _QUANT_MARGIN_FLOOR_M:
        new_high = interval_high - margin
    new_low = interval_low
    if interval_low is not None and abs(interval_low) > _QUANT_MARGIN_FLOOR_M:
        new_low = interval_low + margin
    # If the two inward shrinks meet or invert, collapse to the floor width
    # about the midpoint (mirrors ``_margined_budget`` never reducing a
    # half-width below ``_QUANT_MARGIN_FLOOR_M``).
    if (new_low is not None and new_high is not None
            and new_high - new_low < 2.0 * _QUANT_MARGIN_FLOOR_M):
        midpoint = 0.5 * (interval_low + interval_high)
        new_low = midpoint - _QUANT_MARGIN_FLOOR_M
        new_high = midpoint + _QUANT_MARGIN_FLOOR_M
    return new_low, new_high


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


def _node_ref_arrays(node_ref, np):
    """``(idx, z_ref)`` numpy columns for the REFERENCE-ROD proximal pull
    (owner ruling 2026-07-29 #2, spec §7: the yield minimizes displacement
    from the reference field).  Caller guarantees non-empty."""
    count = len(node_ref)
    ref_idx = np.fromiter(node_ref.keys(), dtype=np.intp, count=count)
    ref_val = np.fromiter(node_ref.values(), dtype=np.float64, count=count)
    return ref_idx, ref_val


def _ref_pull_weight():
    """Proximal-pull weight for the reference term — SMALL vs the cap
    projections so the law always wins locally (spec §7); each sweep pulls
    BEFORE its projections, so the exit state is always cap-projected."""
    try:
        return float(_os.environ.get("O4_YIELD_REF_WEIGHT", "0.2"))
    except ValueError:                                    # pragma: no cover
        return 0.2


def _project_vectorized(elev, iter_edges, n, max_iters, tol,
                        interval_bounds_by_index=None, node_box=None,
                        node_ref=None):
    """Vectorised DEGREE-NORMALISED JACOBI variant of the feasibility projection
    (gated by ``_FP_VECTORIZE``).  Mutates ``elev`` (a list) in place.

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
    # REFERENCE RODS (owner ruling 2026-07-29 #2, spec §7): a small
    # proximal pull toward ``z_ref`` BEFORE each iteration's projections
    # (the law wins — the step ends cap-projected); iteration stays active
    # while any pull exceeds tol.  ``node_ref=None`` ⇒ byte-identical.
    ref_idx = ref_val = None
    ref_w = _ref_pull_weight() if node_ref else 0.0
    if node_ref:
        ref_idx, ref_val = _node_ref_arrays(node_ref, np)
    for _it in range(max_iters):
        ref_active = False
        if ref_idx is not None:
            pull = ref_w * (ref_val - z[ref_idx])
            z[ref_idx] += pull
            ref_active = bool((np.abs(pull) > tol).any())
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
        if not any_active and not ref_active:
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


def _stall_envelope_gap(np, endpoint_i, endpoint_j, budget_column,
                        interval_mask, weight_i, weight_j, z, n, pairs):
    """``L − U`` at ``pairs`` on the CAP graph — the adjudication that says
    whether a stalled carrier pair is genuinely INFEASIBLE.

    For the difference system ``|z_i − z_j| ≤ b_ij`` with the immovable
    endpoints pinned at their current values ``v_a``, feasibility is decided
    by the two-sided envelope ``U(i) = min_a (v_a + d(a,i))`` and
    ``L(i) = max_a (v_a − d(a,i))`` (``d`` = shortest path under the cap
    weights, all ≥ 0): the system is infeasible exactly where ``L > U``.
    Two multi-source Dijkstras via a virtual source with offset edges.
    Interval (slab) edges and node boxes are OMITTED — that only ever
    REMOVES constraints, so a positive verdict here is conservative and
    certain.

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
    eb = budget_column[symmetric]
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

    def _envelope(offsets):
        rows = np.concatenate([ei, ej, np.full(len(anchors), n)])
        cols = np.concatenate([ej, ei, anchors])
        data = np.concatenate([eb, eb, offsets])
        graph = coo_matrix((data, (rows, cols)),
                           shape=(n + 1, n + 1)).tocsr()
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


def _stall_guard_report(np, sweeps, max_iters, detect_sweep, detect_active,
                        detect_worst, detect_carrier, active_count, worst,
                        carrier, endpoint_i, endpoint_j, budget_column,
                        interval_mask, weight_i, weight_j, z, n):
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
    pairs themselves are always named."""
    print(f"    [stall-report] edges={len(interval_mask)} n={n}: STALLED "
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
                                      budget_column, interval_mask,
                                      weight_i, weight_j, z, n, pairs)
    except Exception as exc:                               # pragma: no cover
        print(f"    [stall-report]   adjudication failed: {exc}")
        return
    if verdict is None:
        print("    [stall-report]   adjudication unavailable "
              "(no scipy / no pinned endpoint)")
        return
    print(f"    [stall-report]   envelope: INFEASIBLE nodes (L>U) "
          f"{verdict['infeasible']} of {verdict['reachable']} reachable, "
          f"max gap {verdict['max_gap']:.6f} m")
    for (pa, pb, ga, gb) in verdict["pairs"]:
        klass = ("INFEASIBLE" if max(ga, gb) > 1e-9 else "feasible")
        print(f"    [stall-report]   carrier ({pa},{pb}) L-U = "
              f"{ga:.6f} / {gb:.6f} -> {klass}"
              f"  (stalled residual {worst:.6f})")


def _project_chromatic(elev, iter_edges, n, max_iters, tol,
                       interval_bounds_by_index=None, *, stats=None,
                       coloring_state=None, run_feasibility_precheck=True,
                       node_box=None, node_ref=None):
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

    ``node_ref`` — REFERENCE RODS (owner ruling 2026-07-29 #2, spec §7):
    ``{node: z_ref}``.  Each sweep starts with a small proximal pull of
    every referenced node toward its reference, THEN runs the cap
    projections and the box clamp — the law always wins locally and the
    exit state is always cap-projected.  Convergence: certified when a
    sweep applies no cap correction, no clamp move AND every pull is
    ≤ tol; a conflicted region instead reaches a pull↔projection
    EQUILIBRIUM, detected as a whole-sweep state change ≤ tol (the
    steady-state exit) — the caller's exact-return polish then settles
    slack nodes onto their references exactly.  ``None`` ⇒ byte-identical
    (and the feasibility pre-check shortcut stays available; with refs it
    is skipped — an all-satisfied system may still owe reference
    pulls)."""
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
    budget_column = np.asarray(flat_budget, dtype=np.float64)
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
    # REFERENCE RODS arrays (spec §7; see docstring).  The pre-check
    # shortcut is skipped with refs present: an all-satisfied edge system
    # may still owe reference pulls.
    ref_idx = ref_val = None
    ref_w = _ref_pull_weight() if node_ref else 0.0
    if node_ref:
        ref_idx, ref_val = _node_ref_arrays(node_ref, np)
        run_feasibility_precheck = False
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
            symmetric_block = (
                si, sj, np.stack((si, sj)),
                bool(np.unique(np.concatenate((si, sj))).size
                     == si.size + sj.size),
                budget_column[symmetric_members],
                weight_i[symmetric_members], weight_j[symmetric_members])
        if interval_members.size:
            ii = endpoint_i[interval_members]
            ij = endpoint_j[interval_members]
            interval_block = (
                ii, ij, np.stack((ii, ij)),
                bool(np.unique(np.concatenate((ii, ij))).size
                     == ii.size + ij.size),
                slab_low_column[interval_members],
                slab_high_column[interval_members],
                weight_i[interval_members], weight_j[interval_members])
        if symmetric_block is not None or interval_block is not None:
            blocks.append((symmetric_block, interval_block))
    sweeps = 0
    certified = False
    worst = 0.0
    ref_prev = z.copy() if ref_idx is not None else None
    # ``worst`` shortcut (value-identical, see the sweep body): with a
    # non-negative tolerance the largest residual is itself active, so
    # ``np.where(active, over, 0.0).max()`` equals ``over.max()`` — which the
    # activity test already computed.  A negative tolerance would let an
    # inactive 0.0 win the max, so that case keeps the original expression.
    worst_is_residual_max = bool(tol >= 0.0)
    np_where = np.where
    np_sign = np.sign
    # ── STALL REPORT state (see ``projection_stall_report_enabled``) ──
    # ``stall_min`` is the running minimum of the per-sweep active
    # violating-edge count; ``stall_ref`` is that minimum's value at the
    # last QUALIFYING improvement (a new minimum counts only when it beats
    # ``stall_ref`` by ≥ ``STALL_REL_IMPROVEMENT`` relative); ``stall_wait``
    # is the number of full passes since.  Detection SNAPSHOTS and lets the
    # sweep loop run on — there is no early exit here, by ruling.  Gate OFF
    # ⇒ none of this is touched and no count is taken.
    stall_on = projection_stall_report_enabled()
    stall_min = None
    stall_ref = None
    stall_wait = 0
    stall_carrier = None
    stall_active = 0
    stall_detect_sweep = 0
    stall_detect_active = 0
    stall_detect_worst = 0.0
    stall_detect_carrier = None
    for _sweep in range(max_iters):
        sweeps += 1
        any_active = False
        worst = 0.0
        ref_active = False
        stall_active = 0
        stall_carrier = None
        if ref_idx is not None:
            # REFERENCE RODS: pull BEFORE the projections (the law wins —
            # the sweep ends cap-projected + box-clamped).
            pull = ref_w * (ref_val - z[ref_idx])
            z[ref_idx] += pull
            ref_active = bool((np.abs(pull) > tol).any())
        for symmetric_block, interval_block in blocks:
            if symmetric_block is not None:
                I, J, IJ, disjoint, B, WI, WJ = symmetric_block
                # one gather for both endpoints; ``pair`` is a fresh copy, so
                # ``pair[0]``/``pair[1]`` are the pre-write ``z[I]``/``z[J]``.
                pair = z[IJ]
                d = pair[0] - pair[1]
                over = abs(d) - B
                # ``over.max() > tol`` is exactly ``(over > tol).any()``.
                residual_max = over.max()
                if residual_max > tol:
                    any_active = True
                    ex = np_where(over > tol, over, 0.0)
                    w = residual_max if worst_is_residual_max else ex.max()
                    if w > worst:
                        worst = float(w)
                        if stall_on:
                            _k = int(over.argmax() if worst_is_residual_max
                                     else ex.argmax())
                            stall_carrier = ("sym", int(I[_k]), int(J[_k]),
                                             float(B[_k]), float(d[_k]),
                                             float(WI[_k]), float(WJ[_k]))
                    if stall_on:
                        stall_active += int((over > tol).sum())
                    # ``se = sign(d) * ex`` once: ``(-s)*ex*WI`` is exactly
                    # ``-((s*ex)*WI)`` (negation is exact in IEEE 754).
                    se = np_sign(d) * ex
                    # disjoint writes within a color -> fancy-indexed add is a
                    # valid simultaneous update (immovable slots carry weight 0).
                    if disjoint:
                        pair[0] -= se * WI
                        pair[1] += se * WJ
                        z[IJ] = pair
                    else:
                        z[I] += -(se * WI)
                        z[J] += se * WJ
            if interval_block is not None:
                Ii, Ji, IJi, disjoint_i, Lo, Hi, IWI, IWJ = interval_block
                pair = z[IJi]
                di = pair[0] - pair[1]
                above = di - Hi
                below = Lo - di
                # exactly ``(active_hi | active_lo).any()``
                if above.max() > tol or below.max() > tol:
                    any_active = True
                    se = np_where(above > tol, above,
                                  np_where(below > tol, di - Lo, 0.0))
                    aw = abs(se).max()
                    if aw > worst:
                        worst = float(aw)
                        if stall_on:
                            _k = int(abs(se).argmax())
                            stall_carrier = ("int", int(Ii[_k]), int(Ji[_k]),
                                             float(Lo[_k]), float(Hi[_k]),
                                             float(di[_k]), 0.0)
                    if stall_on:
                        stall_active += int(((above > tol)
                                             | (below > tol)).sum())
                    if disjoint_i:
                        pair[0] -= se * IWI
                        pair[1] += se * IWJ
                        z[IJi] = pair
                    else:
                        z[Ii] += -(se * IWI)
                        z[Ji] += se * IWJ
        if box_idx is not None:
            # BOUNDED YIELD: re-clamp after the sweep; movement beyond tol
            # means an edge pushed a node out of its box — stay active so
            # the incident edges re-relax against the clamped value.
            clamped = np.minimum(np.maximum(z[box_idx], box_lo), box_hi)
            clamp_move = np.abs(clamped - z[box_idx])
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
            z[box_idx] = clamped
        if not any_active and not ref_active:
            certified = True
            break
        if ref_prev is not None:
            # REFERENCE-ROD steady state (spec §7): a conflicted node's
            # pull is cancelled by the projections every sweep, so
            # ``ref_active`` alone never quiets there — exit when the
            # whole sweep left the state unchanged (pull ↔ projection
            # equilibrium = the least-displacement fixpoint; the exit
            # state is cap-projected + clamped, and the caller's polish
            # settles slack nodes exactly onto their references).
            if float(np.abs(z - ref_prev).max()) <= tol:
                break
            np.copyto(ref_prev, z)
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
    if stall_detect_sweep:
        # WRITE-ONLY (after the writeback): nothing below feeds the solve.
        _stall_guard_report(np, sweeps, max_iters, stall_detect_sweep,
                            stall_detect_active, stall_detect_worst,
                            stall_detect_carrier, stall_active, worst,
                            stall_carrier, endpoint_i, endpoint_j,
                            budget_column, interval_mask, weight_i, weight_j,
                            z, n)
    if stats is not None:
        stats["colors"] = color_count
        stats["edges"] = len(iter_edges)
        stats["sweeps"] = sweeps
        stats["sweeps_avoided"] = max(0, max_iters - sweeps) if certified else 0
        stats["certified"] = certified
        stats["worst"] = worst
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


def feasibility_project(elev, shape_constraints, hard, *,
                        max_iters=4000, tol=1e-3, force_scalar=False,
                        flat_groups=None, broken_out=None, pre_broken=None,
                        edge_couple_nodes=None, interval_yield_from=None,
                        group_bounds=None, node_bounds=None,
                        group_refs=None, node_refs=None, forensics=None,
                        witness_limited=None, witness_excluded=None,
                        env_band=None,
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

    EMIT-QUANTIZATION MARGIN: the sweeps (and the reach envelope) enforce
    ``budget − config.EMIT_QUANTIZATION_MARGIN_M`` (floored, see
    ``_margined_budget``) so the 0.01 m-rounded emitted elevations still satisfy
    the raw law; the returned over-cap tally is measured against the RAW budget
    (the true law — reporting is never tightened).

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

    ``group_refs`` / ``node_refs`` — REFERENCE RODS (owner ruling
    2026-07-29 #2, spec §7): the yield solves "minimum displacement from
    the reference field, subject to the caps and the boxes", never "any
    feasible point".  ``group_refs`` is a list parallel to
    ``flat_groups`` (a merged rigid unit takes the size-weighted mean of
    its constituent references — the least-total-displacement level);
    ``node_refs`` is ``{node: z_ref}``.  Mechanically: the chromatic /
    Jacobi sweeps add a small proximal pull toward ``z_ref`` before each
    sweep's projections (the law always wins — see ``_project_chromatic``),
    and an EXACT-RETURN POLISH after the sweeps projects each reference
    onto the interval the node's own (current-neighbour) constraints and
    box admit — a node with no binding pair ends AT its reference
    exactly (owner clarification 2026-07-29: cap-lawful sag below the
    string is a forbidden answer; the surface leaves its reference only
    where a constraint forces it, minimally, in-box).  The legacy scalar
    worklist has no sweep structure, so with refs it enforces caps+boxes
    only and the polish supplies the reference semantics.  ``None`` for
    both = today's behavior, byte-identical.

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
    also seeded from EVERY hard node, so ``gs_pin``/``pad_detached_dem``/
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
    rep_refs: dict = {}         # representative -> group reference level
    if flat_groups:
        # merge overlapping groups (two touching pads sharing a ring node act
        # as one rigid unit), then map member → representative.  BOUNDED
        # YIELD: each group's box rides the merge (intersection — the merged
        # unit must satisfy every constituent box; a group without a box
        # bounds nothing).  REFERENCE RODS: each group's reference rides it
        # too, as a size-weighted running mean — the least-total-
        # displacement level for the merged rigid unit.
        pool = [set(g) for g in flat_groups if g]
        pool_bounds = ([b for g, b in zip(flat_groups, group_bounds) if g]
                       if group_bounds else [None] * len(pool))
        pool_refs = ([r for g, r in zip(flat_groups, group_refs) if g]
                     if group_refs else [None] * len(pool))
        merged: list = []
        merged_bounds: list = []
        merged_refs: list = []       # [weighted_ref_sum, weight] or None
        for pool_index, g in enumerate(pool):
            g_ref = pool_refs[pool_index]
            g_ref_acc = ([float(g_ref) * len(g), float(len(g))]
                         if g_ref is not None else None)
            attached = None
            for merged_index, mg in enumerate(merged):
                if mg & g:
                    mg |= g
                    merged_bounds[merged_index] = _box_isect(
                        merged_bounds[merged_index], pool_bounds[pool_index])
                    if g_ref_acc is not None:
                        prev_ref = merged_refs[merged_index]
                        if prev_ref is None:
                            merged_refs[merged_index] = g_ref_acc
                        else:
                            prev_ref[0] += g_ref_acc[0]
                            prev_ref[1] += g_ref_acc[1]
                    attached = mg
                    break
            if attached is None:
                merged.append(set(g))
                merged_bounds.append(pool_bounds[pool_index])
                merged_refs.append(g_ref_acc)
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
            mr = merged_refs[merged_index]
            if mr is not None and mr[1] > 0.0:
                rep_refs[rep] = mr[0] / mr[1]
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
            # through the ordinary min-budget-wins + margin pipeline.
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
    for sc in shape_constraints:
        _sc_env_skip = bool(sc.get("envelope_skip"))
        for edge in sc["edges"]:
            if len(edge) >= 4:
                # INTERVAL EDGE — signed slab on ``z_i − z_j``.
                i, j, raw_low, raw_high = (edge[0], edge[1],
                                           edge[2], edge[3])
                if raw_low is None and raw_high is None:
                    continue         # unregulated (both sides open)
                if i >= n or j >= n:
                    continue
                i, j = _r(i), _r(j)
                if i == j:
                    continue
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
            i, j = _r(i), _r(j)
            if i == j:
                continue
            e = (i, j) if i < j else (j, i)
            prev = edge_lim.get(e)
            if prev is None or lim < prev:
                edge_lim[e] = lim
    if not edge_lim and not interval_lim:
        return 0, 0
    # EMIT-QUANTIZATION MARGIN: the SWEEP (and the reach envelope + break
    # detection, so the enforced system stays self-consistent) runs on
    # ``budget − margin`` — the rounded emit still fits the raw law — while
    # the final TALLY below keeps the RAW budget: violations are reported
    # against the true law, and a both-hard pair (never movable) can not be
    # tipped into a phantom violation by the margin.  ``edges`` carries both:
    # ``(i, j, raw_budget, sweep_budget)``.
    quant_margin = _emit_quantization_margin()
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
        sweep_lim = _margined_budget(lim, quant_margin)
        edges.append((i, j, lim, sweep_lim))
        adj.setdefault(i, []).append((j, sweep_lim))
        adj.setdefault(j, []).append((i, sweep_lim))
        ceil_radj.setdefault(i, []).append((j, sweep_lim))
        ceil_radj.setdefault(j, []).append((i, sweep_lim))
        floor_radj.setdefault(i, []).append((j, -sweep_lim))
        floor_radj.setdefault(j, []).append((i, -sweep_lim))
    # INTERVAL EDGES (Stage B0): each carries the RAW interval (for the final
    # tally, measured against the true law) and the SWEEP interval (raw shrunk
    # inward by the emit-quantization margin — see ``_margined_interval``).
    # ``interval_edges`` items: ``(i, j, raw_low, raw_high, sweep_low,
    # sweep_high)`` with ``i < j`` and the slab on ``z_i − z_j``.
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
        sweep_low, sweep_high = _margined_interval(raw_low, raw_high,
                                                   quant_margin)
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

    # ── REFERENCE RODS → one per-node reference map ──────────────────────
    # (owner ruling 2026-07-29 #2, spec §7; see the docstring.)  Built
    # BEFORE the reach envelope, like the boxes: the broken branch below
    # must know a node's reference to keep it there instead of at the
    # anchor blend.  Group references attach to the representative;
    # hard nodes and aliased members drop out.
    ref_of: dict = {}
    if node_refs:
        for rn, rv in node_refs.items():
            if rv is not None and 0 <= rn < n:
                ref_of[rn] = float(rv)
    if rep_refs:
        ref_of.update(rep_refs)
    if ref_of:
        ref_of = {rn: rv for rn, rv in ref_of.items()
                  if rn not in hard and rn not in gmap}

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
            print(f"    [env-band] envelope from THE graph: "
                  f"band-inverted={len(_band_broken)} feasible={_bn_ok} "
                  f"off-net={_bn_none} (pair closure skipped — the band "
                  f"answers)")
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

    # ── CHAIN-RIGID BROKEN BLEND (spec apron-string-and-scheduling §D.2.1,
    # gate ``O4_CHAIN_RIGID_BLEND``) ─────────────────────────────────────
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
    if (broken and envelope_skip_pairs
            and _os.environ.get("O4_CHAIN_RIGID_BLEND", "1") == "1"):
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
        # ── RIGID BRANCH VERTICES (spec reference-honesty Track 1 step 3,
        # gate ``O4_BRANCH_RIGID_BLEND``) ────────────────────────────────
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
        if (_branch
                and _os.environ.get("O4_BRANCH_RIGID_BLEND", "1") == "1"):
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

    # REFERENCE RODS, sweep side: broken referenced nodes were parked at
    # their reference above and stay quarantined; the sweeps and the
    # exact-return polish only ever move the remaining (movable)
    # referenced nodes.
    if ref_of:
        ref_of = {rn: rv for rn, rv in ref_of.items()
                  if rn not in immovable}

    # Pre-split the edges ONCE by hard-membership.  The inner loop otherwise ran
    # two ``in hard`` set lookups PER edge PER iteration (up to ~0.5 B lookups on
    # a big airport).  Both-immovable edges can never move, so drop them from the
    # iteration entirely (they are only counted in the final tally below).
    # ``kind``: 0 = both free (split the excess), 1 = i fixed (move j), 2 = j fixed.
    # The iteration enforces the MARGINED (sweep) budget — see above.
    iter_edges = []
    for (i, j, _raw_budget, sweep_budget) in edges:
        hi = i in immovable
        hj = j in immovable
        if hi and hj:
            continue
        iter_edges.append((i, j, sweep_budget, 1 if hi else (2 if hj else 0)))
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
        for (raw_a, raw_b, raw_budget) in _expand_lazy_entry(entry):
            if raw_budget is None or raw_budget < 0 \
                    or raw_a >= n or raw_b >= n:
                continue
            node_a, node_b = _r(raw_a), _r(raw_b)
            if node_a == node_b:
                continue
            pair = (node_a, node_b) if node_a < node_b else (node_b, node_a)
            previous_budget = edge_lim.get(pair)
            if previous_budget is not None and previous_budget <= raw_budget:
                continue
            edge_lim[pair] = raw_budget
            sweep_budget = _margined_budget(raw_budget, quant_margin)
            edges.append((pair[0], pair[1], raw_budget, sweep_budget))
            a_immovable = pair[0] in immovable
            b_immovable = pair[1] in immovable
            if a_immovable and b_immovable:
                continue
            iter_edges.append((pair[0], pair[1], sweep_budget,
                               1 if a_immovable else (2 if b_immovable else 0)))
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
                           node_ref=ref_of or None)
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
            _project_chromatic(elev, iter_edges, n, max_iters, tol,
                               interval_bounds_by_index, stats=_chroma_stats,
                               coloring_state=_coloring_state,
                               node_box=bound_of or None,
                               node_ref=ref_of or None)
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
                            node_box=bound_of or None,
                            node_ref=ref_of or None)
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
                                node_box=bound_of or None,
                                node_ref=ref_of or None)
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
    # ── REFERENCE RODS: exact-return polish (owner clarification
    # 2026-07-29: cap-lawful sag below the string is a FORBIDDEN answer —
    # a node with no binding pair must end AT its reference, not near
    # it).  Sequential per-node projection of ``z_ref`` onto the interval
    # the node's own incident constraints (at current neighbour values)
    # and box admit: slack nodes land exactly on their reference,
    # binding nodes at the nearest lawful point (least local
    # displacement), and no pass ever violates a constraint it can see
    # (the value stays inside every incident interval).  Runs to a small
    # fixpoint; nodes still watched by an unexpanded lazy certificate
    # are skipped (moving them off the certified seed would uncover
    # unenforced body pairs).  Enforces the MARGINED sweep budgets, like
    # the sweeps — the raw-law tally below is unaffected.
    if ref_of:
        lazy_watch: set = set()
        for lazy_entry in lazy_entries_pending:
            if "lazy_expand" in lazy_entry:
                for lazy_node in lazy_entry.get("lazy_nodes", ()):
                    lazy_watch.add(_r(lazy_node))
        ref_adj: dict = {}
        for (ai, aj, _rb, sweep_b) in edges:
            if ai in ref_of:
                ref_adj.setdefault(ai, []).append((aj, -sweep_b, sweep_b))
            if aj in ref_of:
                ref_adj.setdefault(aj, []).append((ai, -sweep_b, sweep_b))
        for (ii, jj, _rl, _rh, s_lo, s_hi) in interval_edges:
            # slab s_lo ≤ z_ii − z_jj ≤ s_hi (None = open side):
            #   z_ii ∈ [z_jj + s_lo, z_jj + s_hi]
            #   z_jj ∈ [z_ii − s_hi, z_ii − s_lo]
            if ii in ref_of:
                ref_adj.setdefault(ii, []).append((jj, s_lo, s_hi))
            if jj in ref_of:
                ref_adj.setdefault(jj, []).append(
                    (ii, None if s_hi is None else -s_hi,
                     None if s_lo is None else -s_lo))
        # Pass cap: each pass walks the return one neighbour layer up a
        # chain, so deep drift needs many (measured HECA: 8 left 3.9k
        # slack nodes ≤0.25 m off reference; the loop exits early at the
        # fixpoint and each pass is O(ref nodes · degree)).
        for _polish_pass in range(64):
            polish_moved = False
            for rn, rv in ref_of.items():
                if rn in lazy_watch:
                    continue
                allow_lo, allow_hi = -_INF, _INF
                for (nb, lo_off, hi_off) in ref_adj.get(rn, ()):
                    znb = elev[nb]
                    if lo_off is not None and znb + lo_off > allow_lo:
                        allow_lo = znb + lo_off
                    if hi_off is not None and znb + hi_off < allow_hi:
                        allow_hi = znb + hi_off
                bb = bound_of.get(rn)
                if bb is not None:
                    if bb[0] > allow_lo:
                        allow_lo = bb[0]
                    if bb[1] < allow_hi:
                        allow_hi = bb[1]
                if allow_lo > allow_hi:
                    continue          # contradictory: keep the swept value
                target = min(max(rv, allow_lo), allow_hi)
                if target != elev[rn]:
                    if abs(target - elev[rn]) > 1e-12:
                        polish_moved = True
                    elev[rn] = target
            if not polish_moved:
                break

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
    if _os.environ.get("O4_STEP_DEBUG") == "1" and force_scalar:
        print(f"    [fp-scalar] sweeps={_sweeps_run} last_worst={_last_worst:.4f} "
              f"rem={rem} worst_ex={worst_ex:.3f} groups={len(groups_eff)} "
              f"broken={len(broken)}")
    return rem, bh


def one_profile_solve(
        elev, shape_constraints, base_hard, nodes, dem_elev,
        runway_nodes, building_seats, apron_body, spine_nodes, spine_adj,
        node_band, spine_floor, coupling, *,
        max_sweeps=3000, tol=0.001, omega=None, curvature=0.25,
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
    _apron_smooth = (apron_smooth if apron_smooth is not None
                     else _os.environ.get("O4_RP_APRON_SMOOTH", "0") == "1")
    adj = _build_adjacency(shape_constraints, n)
    if not adj:
        return 0

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

    moved = _INF
    for _it in range(max_sweeps):
        moved = 0.0
        for i in free:
            spine = wspine.get(i)
            if spine is not None:
                lst = spine                          # spine: centerline only
            else:
                lst = wadj[i]                         # body / rect: all neighbours
            if spine is None and i in apron_body and not _apron_smooth:
                tgt = _dem_target(i)                 # apron body → closest-DEM
            else:
                # spine + rect ends → smoothest (min curvature): inverse-budget²
                # harmonic mean blended with the plain mean.
                sw = acc = 0.0
                for (j, _l, w) in lst:
                    sw += w
                    acc += elev[j] * w
                harm = acc / sw if sw > 0 else elev[i]
                pm = sum(elev[j] for (j, _l, _w) in lst) / len(lst)
                tgt = (1.0 - curvature) * harm + curvature * pm
            # neighbour cap slab (spine: centerline chain only; else all edges)
            n_lo, n_hi = -_INF, _INF
            for (j, lim, _w) in lst:
                ej = elev[j]
                if ej - lim > n_lo:
                    n_lo = ej - lim
                if ej + lim < n_hi:
                    n_hi = ej + lim
            lo_e = max(n_lo, floor.get(i, -_INF))
            hi_e = min(n_hi, ceil.get(i, _INF))
            if lo_e > hi_e and spine is not None:
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
