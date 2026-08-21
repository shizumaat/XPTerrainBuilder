"""Insert LATERAL corridor nodes on apron/junction edges (user 2026-06-26).

The within-shape grade check (and the solver) are vertex-pair based: a long
apron/junction edge running within taxi-width of a spine, with no intermediate
vertex, has nothing to sample — so a steep drop on the runway side of a risen
spine (CYXY building-19 apron) is invisible to BOTH the check and the solve, and
the apron just drapes to DEM.

This pass projects every spine centerline vertex perpendicularly onto any
apron/junction edge within ±half the taxi-width and inserts a vertex at the foot
(matching the spine nodes — no extra densification, per user).  The grade graph
then gains spine ↔ lateral-foot pairs (the lateral corridor grade is validated),
and the solver gains a node to grade that apron face down from the spine within
cap instead of draping it.

Runs PRE-SOLVE, after the spine is built and BEFORE the airside conformance, so
the inserted vertices are welded/propagated to neighbouring shapes too.

R-a — LATERAL NODES ARE ROUTE-TRANSPARENT (lead ruling 2026-08-08, the direct
application of the owner's 2026-07-30 "Reach follows centerlines"): every foot
this module plants is a CROSS-SECTION sample, never a route.  It must bind the
transverse law (that is the whole point) and it must never mint a ROUTE-GRAPH
edge, because reach/route budgets price along spines and centerlines ONLY.
Each inserted foot is therefore RECORDED here at insertion
(:func:`record_lateral_feet`), and ``grade_graph._build_global_spine`` reads
that record (:func:`lateral_foot_predicate`) to keep the feet out of its
centerline chains — so the arc-ordered on-line node list, and every
``spine_adj`` budget woven from it, is exactly the list the same layout
without laterals would have produced.  The measurement that made this law
necessary: at HECA the station-densified feet welded on BOTH sides of a
corridor minted CROSS edges that shortened routes and shrank the reach band's
route budgets (1,655 inverted nodes, 49.400 m of anchor spread over a
47.723 m budget — the build refused).
"""
from __future__ import annotations

import math
import os
from collections import defaultdict

from shapely.errors import GEOSException, TopologicalError
from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

import O4_UI_Utils as UI

from . import config as _CFG
from . import grade_law as _GL
from . import fabric_flags as _FF
from .layout import (ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION,
                     ROLE_SERVICE_ROAD)

_GEOM_EXC = (ValueError, GEOSException, TopologicalError)

#: Sentinel for "R-b is switched off" — distinct from ``None``, which is
#: the attempt-3 union (no width condition at all).
_RB_DISABLED = object()

__all__ = ["insert_lateral_spine_nodes", "insert_service_lateral_nodes",
           "densify_junction_edges", "record_lateral_feet",
           "lateral_foot_predicate", "lateral_feet",
           "record_lateral_xsection_pairs", "lateral_xsection_pairs",
           "lateral_xsection_law_edges",
           "TAXI_AXIS_PRICED_ROLES", "SERVICE_AXIS_PRICED_ROLES"]

# Body shapes that should sample the lateral corridor grade.
_LATERAL_BODY_ROLES = frozenset({ROLE_APRON, ROLE_JUNCTION, ROLE_SERVICE_JUNCTION})
# WHICH SHAPES AN AXIS PRICES — the census's own rule
# (``check_grade._check_transverse_grade``: an axis whose sidecar
# ``is_service`` flag is set may only censure the ROAD FAMILY's shapes,
# because "a truck route is not an aircraft spine").  Read here for the
# PAIR RECORD; ``check_grade`` IMPORTS these two sets as its own
# per-axis-kind transverse scope, so the shapes the generator plants
# cross-sections on and the shapes the census prices are ONE list.
#
# THE LOCKSTEP USED TO BE A CLAIM, NOT A FACT (S7 escalation, ruled
# 2026-08-14).  The service set said ``{service_junction}`` while
# :func:`insert_service_lateral_nodes` plants feet on ``service_road``
# AND ``service_junction`` from the truck-route spine, and
# ``grade_graph`` binds those road bodies across the route at
# ``SERVICE_ROAD_MAX_TRANSVERSE`` (``SOFT_VISIBILITY_ROLES``, default-ON
# under ``config.SVC_SPINE_FIRST``).  So the generator bound a
# constraint whose validator read nothing: a cross-road tear on a
# service_road censused ZERO.  The set now names the service pass's OWN
# targets, which is what makes the comment above true again.
#
# The TAXI set is unchanged — the taxi pass targets ``_LATERAL_BODY_ROLES``
# and never plants on ``service_road`` (an SVC line must not couple aprons
# to the road law), so the two scopes are deliberately different sets.
TAXI_AXIS_PRICED_ROLES = _LATERAL_BODY_ROLES
SERVICE_AXIS_PRICED_ROLES = frozenset({ROLE_SERVICE_ROAD,
                                       ROLE_SERVICE_JUNCTION})
_TAXI_AXIS_PRICED_ROLES = TAXI_AXIS_PRICED_ROLES
_SERVICE_AXIS_PRICED_ROLES = SERVICE_AXIS_PRICED_ROLES
_DEFAULT_HALF_W_M = 12.0          # fallback taxi half-width (≈ code C/D)
_CORNER_TOL_M = 0.5              # don't insert within this of an existing corner
_MERGE_TOL_M = 0.5              # merge feet closer than this on one edge
# The narrowest cross-section the TRANSVERSE law prices — LOCKSTEP with
# ``tools/check_grade._TRANSVERSE_MIN_WIDTH_M`` (3.0 m).  Restoration
# mode inserts the pair the law will price and nothing narrower, so the
# emitter's span rule and the validator's are the same rule; the twin
# ``tests/test_lateral_cross_section.py`` asserts the two agree.
_BRACKET_MIN_WIDTH_M = 3.0
# The other two halves of the SAME span rule, also lockstep with
# ``tools/check_grade``: how far the priced span's near side may sit from
# the axis (``_TRANSVERSE_MAX_GAP_M``) and how far out the census looks
# at all (``_TRANSVERSE_HALF_M``).  Held here as literals rather than
# imported because ``check_grade`` is a TOOL and the engine may not
# import from ``tools/``; ``tests/test_lateral_cross_section.py`` asserts
# all three agree, which is the lockstep the census-wrapper precedent
# demands.
_SPAN_MAX_GAP_M = 1.0
_SPAN_HALF_M = 80.0
#: Parameter slack for a perpendicular that meets a ring edge AT an
#: endpoint — the case a station standing on an existing ring vertex
#: always produces (see ``_bracket_feet``'s vertex-hit branch).
_T_EPS = 1e-9


def _xsection_bracket_on() -> bool:
    """``O4_XSECTION_BRACKET`` — default OFF (see :func:`_bracket_feet`).

    ATTEMPT 3, authorized by lead ruling R-c and still parked: the PLAIN
    union of the nearest-projection rule and the bracket rule, i.e. the
    bracket with its width condition DROPPED.  R-b (default-ON, below)
    is the width-adaptive half — bracket rows only where the priced
    cross-section exceeds the lateral pass reach; turning this gate on
    additionally inserts the bracket where the reach already covers it.

    Deliberately NOT an ``O4_FABRIC_*`` name: the Phase-B registry
    (``fabric_flags``) is every-flag-DEFAULT-ON by construction and its
    audit claims that prefix, so a parked default-OFF experiment must
    not wear it.
    """
    return os.environ.get("O4_XSECTION_BRACKET", "0") == "1"


def _xsection_vertex_hits_on() -> bool:
    """``O4_XSECTION_VERTEX_HITS`` — default OFF.  THE PARKED HALF of
    ruling (1), measured on both sides and refusing at HECA.

    WHAT IT IS.  The near side of a priced cross-section is the axis's
    own pavement edge, and by restoration time the earlier lateral pass
    has already put a node there at every station — so the near hit
    lands ON a ring vertex, which the corner rule (an INSERTION rule)
    dropped outright, leaving ``hits`` at one and selecting NO span.
    Measured on the CYXY specimen's own pre-solve ring (apron
    ``shapeID 115``): 44 of 45 stations within ``_CORNER_TOL_M`` of a
    ring vertex and ZERO spans selected, while the SAME rule on the
    EMITTED ring selects the 33 spans the census prices at 17.1-17.8 m.
    That gap IS the 48-row class the round is about, and it is why the
    R-b round read "the emitter is not the lever" — the emitter was
    never reaching the specimen at all.  With the branch on, a hit on an
    existing vertex is an EXISTING foot: the span completes and only the
    far side is planted.

    WHY IT IS PARKED, and not a registry flag.  It WORKS at CYXY
    (transverse 28 vs the control's 31, worst |de| 1.350 → 0.822,
    ACTIONABLE SITES 9 vs 10, airside 12 vs 17) and it REFUSES at HECA:
    the completion roughly doubles the planted cross-section rows
    (5,918 → 11,742 R-b feet) and the FINAL reach band inverts at 648 of
    4,828 band-covered nodes — three contradictory anchor pairs, worst
    shortfall 1.741 m (spread 49.300 m over a route budget of 47.559 m,
    05C/23C against 05L/23R).  The CIFP-forced spread FITS every one of
    those budgets (33.6-35.8 m against 47.3-48.9 m), so this is a route
    BUDGET contraction, not an infeasible airport.  R-a is intact —
    every planted foot is still recorded route-transparent — so the
    channel is NOT the one R-a closed and is unattributed; naming it is
    the next round's work.  The Phase-B registry is DEFAULT-ON by
    construction and a default-ON flag may not refuse a battery airport,
    so this parks exactly as attempt 3 does above: an ``O4_XSECTION_*``
    name, default OFF, kept because it is measured and because the owner
    does not throw away work.
    """
    return os.environ.get("O4_XSECTION_VERTEX_HITS", "0") == "1"


# ── R-a · THE LATERAL-FOOT RECORD (route transparency) ────────────────
#: Where the record lives on the layout.  A plain attribute, deliberately:
#: it is minted pre-solve, read once at graph-build time, and never
#: crosses a node space (the rod-key lesson) — it is POSITIONS, which is
#: the one identity that survives welding, conformance and re-interning.
_FEET_ATTR = "_lateral_xsection_feet"


def record_lateral_feet(layout, pts) -> int:
    """Record cross-section feet as ROUTE-TRANSPARENT (R-a).

    ``pts`` is an iterable of ``(x, y)`` local-metre positions actually
    inserted into a ring.  Returns the number recorded.  Append-only and
    idempotent per call: the two lateral passes each call it once with
    their own feet, and the fabric-sparse RESTORATION calls them again
    after thinning, so the record accumulates every foot the build ever
    planted — a foot the thinning removed simply matches no node.
    """
    rec = getattr(layout, _FEET_ATTR, None)
    if rec is None:
        rec = []
        setattr(layout, _FEET_ATTR, rec)
    n = 0
    for p in pts:
        rec.append((float(p[0]), float(p[1])))
        n += 1
    return n


def lateral_feet(layout):
    """The recorded feet — ``[(x, y), ...]`` (read-only by contract)."""
    return getattr(layout, _FEET_ATTR, None) or []


# ── RULING (1) · THE CROSS-SECTION PAIR RECORD (priced ⟺ bound) ───────
#: Where the PAIRS live on the layout.  Positions again, for the reason
#: the feet record states: a position is the one identity that survives
#: welding, conformance and re-interning, and the solve resolves it back
#: through the canonical registry the node list was built from.
_PAIRS_ATTR = "_lateral_xsection_pairs"
#: Index-parallel STAGE record for the pairs above (S1b).
_PAIR_STAGES_ATTR = "_lateral_xsection_pair_stages"
from .solve_stage import STAGE_A as _STAGE_A


def record_lateral_xsection_pairs(layout, pairs, stages=None) -> int:
    """Record priced CROSS-SECTION PAIRS (lead ruling 2026-08-08, LEAD
    RULINGS 2 ruling 1: *cross-section pairs enter the solve's law
    context — priced ⟺ bound*).

    ``pairs`` is an iterable of ``((xa, ya), (xb, yb), width_m, cap_l)``:
    the two feet of a span :func:`_bracket_feet` SELECTED BY THE
    VALIDATOR'S OWN RULE and actually PLANTED into the ring, the span it
    was priced over, and the transverse cap that prices it
    (``config.transverse_cap_for_longitudinal_cap`` of the axis
    segment's longitudinal cap — the census's own function).

    The recording happens in the SAME act as the planting, which is what
    makes ``priced ⟺ bound`` structural rather than a hand list: there
    is no second geometry sweep that could select a different span, and
    a pair whose feet did not land is never recorded.  Returns the
    number recorded; append-only, like the feet record.
    """
    rec = getattr(layout, _PAIRS_ATTR, None)
    if rec is None:
        rec = []
        setattr(layout, _PAIRS_ATTR, rec)
    # STAGE RECORD (staged-solve S1b), index-parallel to the pair record
    # and appended in the SAME act: a cross-section pair is APPENDED to
    # the unified edge set, which reaches every projection as one
    # untagged entry, so its stage must be stamped where it is minted.
    # ``_LATERAL_BODY_ROLES`` includes ``service_junction`` — a service
    # cross-section is groundside law and never binds stage A.
    st_rec = getattr(layout, _PAIR_STAGES_ATTR, None)
    if st_rec is None:
        st_rec = []
        setattr(layout, _PAIR_STAGES_ATTR, st_rec)
    n = 0
    stages = list(stages or ())
    for k, (a, b, width_m, cap_l) in enumerate(pairs):
        rec.append(((float(a[0]), float(a[1])),
                    (float(b[0]), float(b[1])),
                    float(width_m), float(cap_l)))
        st_rec.append(stages[k] if k < len(stages) else None)
        n += 1
    return n


def lateral_xsection_pairs(layout):
    """The recorded pairs — ``[((xa,ya), (xb,yb), width_m, cap_l), ...]``
    (read-only by contract)."""
    return getattr(layout, _PAIRS_ATTR, None) or []


def lateral_xsection_law_edges(layout, bucket_to_idx, stage_out=None):
    """``[(node_i, node_j, budget_m)]`` — the recorded cross-section
    pairs as LAW EDGES for the solve's joint feasibility projections.

    THE BINDING (LEAD RULINGS 2 ruling 1).  R-b plants the pair the
    TRANSVERSE census prices; the R-b round then measured that the solve
    leaves those feet within 2 cm of the straight chord and the
    decimator losslessly collapses them (CYXY apron ``shapeID 115``: 35
    planted, 2 emitted; the census prices |Δz| 1.51 m over 17.56 m at
    the apron's 1 % transverse cap).  A pair the law prices and the
    solve never binds is the lockstep-gap class — the near-miss-frontage
    precedent — so the pair enters the solve's law context exactly the
    way ``anchors.near_miss_building_frontage_edges`` does: as an
    ``(i, j, budget)`` member of ``u_edges``, enforced by every
    feasibility projection including the final movable-pad yield.

    ``budget_m`` is ``grade_law.transverse_span_budget_m(cap_l, width)``
    — THE one law function both readers call (spec
    ``transverse-hyperplane-solve-spec.md`` step 1; the census's own
    allowance
    (``check_grade._check_transverse_grade``) with its quantization and
    terrace slack left OUT: those forgive an emitted reading, they do
    not fund a solve target.

    ROUTE TRANSPARENCY IS UNTOUCHED (R-a): these are SURFACE
    constraints in the projections' edge set.  ``u_edges`` is not the
    route graph — the reach band prices along ``G.spine_adj``, which
    ``grade_graph._build_global_spine`` still builds with every foot
    skipped.  A cross-section pair therefore constrains elevation and
    mints no route edge, which is exactly the split R-a established.

    Identity: each foot resolves through the layout's own canonical
    point registry (``get_or_add`` → ``bucket_to_idx``), the SAME join
    ``solver_primitives._build_shape_constraints`` and the near-miss
    frontage builder use — never a proximity match.  A foot the
    thinning, a re-ring or a merge removed resolves to no node and its
    pair is dropped (reported by the caller's count), because binding a
    node that is something else is worse than binding nothing.
    """
    pairs = lateral_xsection_pairs(layout)
    if not pairs:
        return []
    pair_stages = getattr(layout, _PAIR_STAGES_ATTR, None) or []
    from . import fabric_flags as _ff
    if not _ff.on("O4_FABRIC_RB_XSECTION_SOLVE_BIND"):
        return []
    cps = getattr(layout, "canonical_points", None)
    if cps is None or not bucket_to_idx:
        return []
    best: dict = {}
    sites: dict = {}
    stage_of: dict = {}
    for _k, (a, b, width_m, cap_l) in enumerate(pairs):
        if width_m <= 0.0 or cap_l <= 0.0:
            continue
        try:
            i = bucket_to_idx.get(cps.get_or_add(float(a[0]), float(a[1])))
            j = bucket_to_idx.get(cps.get_or_add(float(b[0]), float(b[1])))
        except Exception:                              # pragma: no cover
            continue
        if i is None or j is None or i == j:
            continue
        key = (i, j) if i < j else (j, i)
        budget = _GL.transverse_span_budget_m(cap_l, width_m)
        # ONE PAIR, ONE EDGE, THE TIGHTEST BUDGET.  Two stations 12 m
        # apart can resolve to the SAME node pair once the 0.5 m merge
        # tolerance folds their feet together; the law prices BOTH
        # stations, so the edge that stands for them must satisfy the
        # stricter one — taking whichever arrived first would let the
        # station order pick the law.
        prev = best.get(key)
        if prev is None or budget < prev:
            best[key] = budget
            sites[key] = (a, b, width_m, cap_l)
        # STAGE OF A PAIR TWO STATIONS FOLDED TOGETHER: AIRSIDE WINS.
        # The budget rule above takes the STRICTER law; the stage rule
        # takes the AIRSIDE one, because a pair an airside shape also
        # owns is airside law and must be enforced in stage A (airside
        # is king — the mirror of ``UnifiedGraph.stage_by_pair``).
        _st = (pair_stages[_k] if _k < len(pair_stages) else None)
        if _st is not None and stage_of.get(key) != _STAGE_A:
            stage_of[key] = _st
    edges = [(i, j, budget) for (i, j), budget in best.items()]
    if stage_out is not None:
        for key in best:
            st = stage_of.get(key)
            if st is not None:
                stage_out[key] = st
    _dump = os.environ.get("O4_XSECTION_DUMP")
    if _dump:                                              # pragma: no cover
        # DIAGNOSTIC ONLY (default absent ⇒ byte-inert).  Every bound
        # pair with its two plan positions, span, cap and budget, so a
        # census row can be JOINED to the edge that was supposed to
        # bind it — the question "is this priced pair in the bound set"
        # is a join, never a guess.
        import json as _json
        try:
            with open(_dump, "a") as fh:
                for key, budget in best.items():
                    (a, b, w, c) = sites[key]
                    fh.write(_json.dumps({
                        "i": key[0], "j": key[1], "a": list(a), "b": list(b),
                        "width_m": w, "cap_l": c, "budget_m": budget}) + "\n")
        except OSError:
            pass
    return edges


def lateral_foot_predicate(layout, tol_m: float = None):
    """``is_lateral(x, y) -> bool`` over the recorded feet, or ``None``
    when this layout planted none (so a caller can skip the work
    entirely and stay byte-identical).

    ``tol_m`` defaults to ``layout.SHARED_VERTEX_TOL_M`` — the canonical
    registry's own bucket radius, which is exactly the right match
    radius and NOT a fudge: a ring vertex is interned through
    ``CanonicalPointRegistry.get_or_add``, so the graph node's position
    is the canonical point within ``tol_m`` of the foot, and the same
    registry guarantees no SECOND canonical point sits that close.  One
    foot therefore resolves to at most one node, and the match cannot
    sweep a genuine spine node in beside it.
    """
    pts = lateral_feet(layout)
    if not pts:
        return None
    from .layout import SHARED_VERTEX_TOL_M
    tol = float(SHARED_VERTEX_TOL_M if tol_m is None else tol_m)
    cell = max(tol, 1e-6)
    grid: dict = {}
    for (x, y) in pts:
        grid.setdefault((int(math.floor(x / cell)),
                         int(math.floor(y / cell))), []).append((x, y))
    t2 = tol * tol

    def is_lateral(x, y) -> bool:
        cx, cy = int(math.floor(x / cell)), int(math.floor(y / cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py) in grid.get((cx + dx, cy + dy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 <= t2:
                        return True
        return False

    is_lateral.n_feet = len(pts)          # type: ignore[attr-defined]
    is_lateral.tol_m = tol                # type: ignore[attr-defined]
    return is_lateral


def _axis_segment_caps(entry, n_seg: int, is_service: bool) -> list:
    """The axis's per-SEGMENT LONGITUDINAL cap, read exactly the way
    ``grade_graph.centerline_specs`` reads it.

    That function is THE law's centerline enumeration — the solver's
    context and ``verification.taxi_axes_exact_ll`` (the sidecar the
    census reads back as its axes) are both built from it — so its rule
    is the one this emitter must apply when it prices a cross-section:
    a SERVICE route takes the road cap and has no per-letter table; an
    aircraft route takes ``taxi_grade_cap_for_letter`` of the segment's
    own apt.dat row-1202 size letter, padded with the last letter when
    the size list is short (that padding IS ``centerline_specs``').
    Returns ``[]`` when the caps cannot be resolved — the caller then
    records no pair rather than guessing a cap.
    """
    if n_seg <= 0:
        return []
    if is_service:
        return [_CFG.SERVICE_ROAD_MAX_GRADE] * n_seg
    sizes = list(getattr(entry, "seg_sizes", []) or [])
    return [_CFG.taxi_grade_cap_for_letter(
                sizes[i] if i < len(sizes) else (sizes[-1] if sizes else None))
            for i in range(n_seg)]


def _landed_pairs(spans, landed_by_shape, si_out=None):
    """Yield ``(foot_lo, foot_hi, width_m, cap_l)`` for every selected
    span BOTH of whose feet are NODES of the shape's final ring —
    reported at the position that actually landed.

    THE MERGE IS WHY THIS IS NOT AN EQUALITY TEST, and the reason is the
    law's own, not a fudge.  The insertion pass drops a foot lying within
    ``_MERGE_TOL_M`` of the previous one on the same edge, and the case
    that always collides is the wide-corridor class itself: with the axis
    ON the near edge (CYXY apron ``shapeID 115``: 0.000-0.004 m), the
    span's near foot and the nearest-projection rule's foot are the same
    point computed two ways, so one of them is merged away and an
    equality test loses the pair — measured, on the very specimen the
    ruling names (105 pairs recorded, ZERO of them the specimen's).
    ``_MERGE_TOL_M`` is ``SHARED_VERTEX_TOL_M``: a merged foot and its
    survivor are ONE canonical node BY THE REGISTRY'S OWN DEFINITION, so
    resolving to the survivor is the same identity the solve will use,
    not a proximity match invented here.  Beyond that radius there is no
    node and the pair is dropped.
    """
    cell = max(_MERGE_TOL_M, 1e-6)
    grids: dict = {}
    for si, pts in landed_by_shape.items():
        g: dict = {}
        for (x, y) in pts:
            g.setdefault((int(math.floor(x / cell)), int(math.floor(y / cell))),
                         []).append((x, y))
        grids[si] = g

    def _snap(grid, p):
        best = None
        best_d2 = _MERGE_TOL_M * _MERGE_TOL_M
        cx, cy = int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q in grid.get((cx + dx, cy + dy), ()):
                    d2 = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2
                    if d2 <= best_d2:
                        best_d2 = d2
                        best = q
        return best

    for (si, a, b, width_m, cap_l) in spans:
        grid = grids.get(si)
        if not grid:
            continue
        qa, qb = _snap(grid, a), _snap(grid, b)
        if qa is None or qb is None or qa == qb:
            continue
        # ``si_out`` (staged-solve S1b) collects the OWNING SHAPE INDEX of
        # every pair that actually landed, in the SAME act and the same
        # order as the pair itself — so the stage record cannot drift
        # from the pair record.  Absent ⇒ byte-identical.
        if si_out is not None:
            si_out.append(si)
        yield (qa, qb, width_m, cap_l)


def _open(poly):
    cs = list(poly.exterior.coords)
    if len(cs) > 1 and cs[0] == cs[-1]:
        cs = cs[:-1]
    return cs


def densify_junction_edges(layout, icao: str = "", step: float = None) -> int:
    """Densify every JUNCTION's exterior edges to ~the spine node spacing (user
    2026-06-26).

    A junction is a taxiway that follows its spine, but a long exterior edge with
    only its two end corners interpolates FLAT between them and cannot track the
    spine's rise (CYXY junction #97: a 500 m edge stayed flat at 695.6 while the
    spine rose 694→699).  Subdividing every junction edge to the spine step gives
    the solver nodes to grade along that edge, so the whole junction surface tilts
    with its centerline.  Pure geometry; runs pre-solve next to the lateral pass.
    Returns the number of nodes inserted."""
    from .config import SPINE_STEP_M
    if step is None:
        step = SPINE_STEP_M
    # The spine edge already has its nodes (from junction_spine); densifying it
    # would add nodes WITHIN the spine perp-tolerance of the centerline, which
    # become NEW spine nodes and perturb the spine solve (CYXY: raised a
    # junction/A piece 0.5 m → stub/A 3.2 %).  So skip any edge that runs ON a
    # centerline; only densify the OFF-spine edges that drape flat.
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    from .layout import ROLE_RUNWAY
    from .grade_law import RUNWAY_JOIN_NEAR_M
    _SPINE_EDGE_TOL_M = 3.0
    _RUNWAY_TOL_M = RUNWAY_JOIN_NEAR_M   # ONE source = the runway-join _NEAR_M
    cls = [cl.line for cl in (getattr(layout, "apt_taxi_centerlines", None) or [])
           if cl.line is not None and not cl.line.is_empty
           and not cl.is_service]
    cl_union = None
    if cls:
        try:
            cl_union = unary_union(cls)
        except _GEOM_EXC:
            cl_union = None
    rwy_union = None
    try:
        rwys = [s.polygon for s in layout.shapes if s.role == ROLE_RUNWAY
                and s.polygon is not None and not s.polygon.is_empty]
        if rwys:
            rwy_union = unary_union(rwys)
    except _GEOM_EXC:
        rwy_union = None

    def _skip_edge(ax, ay, bx, by):
        """Skip densifying an edge that runs ON a centerline (its nodes would
        become spine nodes and perturb the spine solve) or ABUTS a runway (its
        nodes must match the runway surface, not the spine — runway-join check)."""
        e = LineString([(ax, ay), (bx, by)])
        try:
            if cl_union is not None and cl_union.distance(e) < _SPINE_EDGE_TOL_M:
                return True
            if rwy_union is not None and rwy_union.distance(e) < _RUNWAY_TOL_M:
                return True
        except _GEOM_EXC:
            return False
        return False

    n_junc = n_added = 0
    for s in layout.shapes:
        if (s.role != ROLE_JUNCTION or s.polygon is None or s.polygon.is_empty
                or s.polygon.geom_type != "Polygon"):
            continue
        ring = _open(s.polygon)
        if len(ring) < 3:
            continue
        new_ring = []
        added = 0
        for ei in range(len(ring)):
            ax, ay = ring[ei]
            bx, by = ring[(ei + 1) % len(ring)]
            new_ring.append((ax, ay))
            d = math.hypot(bx - ax, by - ay)
            k = max(0, int(round(d / step)) - 1)   # ~step spacing; 0 if already ≤step
            if k and _skip_edge(ax, ay, bx, by):
                k = 0                              # spine/runway edge → leave alone
            for j in range(1, k + 1):
                f = j / (k + 1)
                new_ring.append((ax + f * (bx - ax), ay + f * (by - ay)))
                added += 1
        if added:
            try:
                poly = Polygon(new_ring)
                if poly.is_valid and not poly.is_empty:
                    s.polygon = poly
                    n_junc += 1
                    n_added += added
            except _GEOM_EXC:
                continue
    if n_added:
        UI.vprint(1, f"  [pav-builder] {icao}: densified {n_junc} junction "
                  f"ring(s) (+{n_added} node(s)) to ~{step:.0f} m spine spacing "
                  f"so junction edges can follow the spine.")
    return n_added


def _densify_to_step(cs, step: float, seg_index_out: list = None):
    """``cs`` (a centerline's vertex list) subdivided to ≤ ``step`` spacing.

    ONE implementation, two callers.  A centerline's own vertices are an
    OSM/apt.dat authoring artefact, not a station spacing: CYXY carries a
    single 470 m straight taxi leg with no intermediate vertex, and a
    1206 truck route can run kilometres the same way.  Both lateral
    passes below project STATIONS onto pavement edges, so both need the
    same subdivision; :func:`insert_service_lateral_nodes` has always
    done it and :func:`insert_lateral_spine_nodes` does it only when it
    is asked to (see that function's ``station_step_m``).

    ``seg_index_out`` — when a list is passed it is filled with the
    SOURCE SEGMENT index of every emitted station, so a caller holding
    per-segment law (the per-letter longitudinal cap a cross-section's
    transverse cap is a function of) can resolve a densified station
    back to the segment whose law governs it.  Parallel to ``out`` by
    construction, filled in the same loop — a second walk that
    re-derived the mapping is exactly the drift this module keeps
    lockstep against.
    """
    out = []
    for k in range(len(cs) - 1):
        ax, ay = cs[k]
        bx, by = cs[k + 1]
        out.append((ax, ay))
        if seg_index_out is not None:
            seg_index_out.append(k)
        d = math.hypot(bx - ax, by - ay)
        n_sub = max(0, int(math.ceil(d / step)) - 1)
        for j in range(1, n_sub + 1):
            f = j / (n_sub + 1)
            out.append((ax + f * (bx - ax), ay + f * (by - ay)))
            if seg_index_out is not None:
                seg_index_out.append(k)
    out.append(cs[-1])
    if seg_index_out is not None:
        seg_index_out.append(max(0, len(cs) - 2))
    return out


def _bracket_feet(vx, vy, cs, vi, tree, rings, polys, inserts,
                  min_span_m: float = None, cap_l: float = None,
                  pairs_out: list = None, priced_roles=None,
                  target_roles=None, vertex_hits: bool = False) -> None:
    """Cast the perpendicular at station ``vi`` and record the NEAREST
    ring hit on EACH SIDE — the transverse law's own span selection
    (``tools/check_grade._check_transverse_grade``: the hits are sorted
    by signed offset and the span BRACKETING the axis is the one priced).

    Records into ``inserts[shape][edge]`` in the same ``(t, (x, y))``
    form the nearest-projection rule uses, so one insertion pass serves
    both.  Nothing is recorded unless a shape offers hits of BOTH signs:
    a bracket is a cross-section, and a shape the station merely passes
    NEAR cannot produce one.

    ``min_span_m`` — R-b, THE WIDTH-ADAPTIVE CONDITION (lead ruling
    2026-08-08).  When given, a bracket is recorded only where the
    PRICED span exceeds it, i.e. only where the nearest-projection
    rule's fixed reach cannot have reached the far side.  That reach is
    ``_DEFAULT_HALF_W_M`` (12 m) and it is a DEAD LOOKUP's fallback —
    nothing has populated ``hw_by_ref`` since the rects retired — so on
    a corridor wider than it the far edge gets no node at any station
    and the emitted surface interpolates a lean across the whole width
    (CYXY apron ``shapeID 115``: axis on the near edge, far edge
    17-24 m out, ~8 % lateral cross-fall over a 449 m extent; the HECA
    junction class is the same shape past 24 m).  ``None`` drops the
    condition — the plain union, attempt 3, gated by
    ``O4_XSECTION_BRACKET``.

    ``cap_l`` / ``pairs_out`` — RULING (1), the solve-side binding.  When
    both are given, each SELECTED span is appended to ``pairs_out`` as
    ``(shape_index, foot_lo, foot_hi, width_m, cap_l)`` so the caller can
    keep the ones whose feet actually LAND and record them through
    :func:`record_lateral_xsection_pairs`.  Same act, same selection,
    same span — which is what makes the priced pair and the bound pair
    the same pair by construction rather than by inspection.

    ``priced_roles`` / ``target_roles`` — the census's OWN axis-scope
    rule (``check_grade._check_transverse_grade``: a SERVICE axis may
    only censure the road family's shapes, "a truck route is not an
    aircraft spine").  ``priced_roles`` is the role set this axis may
    price; ``target_roles[si]`` is the shape's role.  A span outside the
    scope is still PLANTED (this ruling changes no geometry) but never
    RECORDED — binding a pair the census does not price would break
    ``priced ⟺ bound`` in the other direction.  ``None`` for either ⇒
    no scope filter (the unit-fixture path).
    """
    # Tangent from the station's own segment (the densified list is
    # collinear inside a segment, so either neighbour gives the same
    # direction; the endpoints take their one available neighbour).
    if vi + 1 < len(cs):
        ax0, ay0 = cs[vi]
        bx0, by0 = cs[vi + 1]
    else:
        ax0, ay0 = cs[vi - 1]
        bx0, by0 = cs[vi]
    tlen = math.hypot(bx0 - ax0, by0 - ay0)
    if tlen < 1e-9:
        return
    tx, ty = (bx0 - ax0) / tlen, (by0 - ay0) / tlen
    nx, ny = -ty, tx
    try:
        cand = tree.query(Point(vx, vy).buffer(_SPAN_HALF_M))
    except _GEOM_EXC:
        return
    for qi in cand:
        si = int(qi)
        ring = rings[si]
        n = len(ring)
        hits = []                         # (u, ei, t, (fx, fy), existing)
        for ei in range(n):
            ax, ay = ring[ei]
            bx, by = ring[(ei + 1) % n]
            ex, ey = bx - ax, by - ay
            den = nx * ey - ny * ex
            if abs(den) < 1e-12:
                continue                  # edge parallel to the section
            rx, ry = ax - vx, ay - vy
            t = (rx * ny - ry * nx) / den
            if vertex_hits:
                if t < -_T_EPS or t > 1.0 + _T_EPS:
                    continue
            elif t <= 0.0 or t >= 1.0:
                continue
            u = (rx + t * ex) * nx + (ry + t * ey) * ny
            if abs(u) > _SPAN_HALF_M:
                continue                  # outside the censused half-width
            L = math.hypot(ex, ey)
            if not vertex_hits:
                # THE PRE-RULING BEHAVIOUR, byte-for-byte (flag OFF).
                if t * L < _CORNER_TOL_M or (1.0 - t) * L < _CORNER_TOL_M:
                    continue              # too near a corner (house rule)
                hits.append((u, ei, t, (ax + t * ex, ay + t * ey), False))
                continue
            # ── A HIT ON AN EXISTING VERTEX IS STILL A CROSS-SECTION ───
            # (ruling 1's completion; MEASURED at the specimen.)  The
            # corner rule below is an INSERTION rule — you may not plant
            # a new vertex on top of one that is already there — and it
            # used to drop the hit outright.  On the wide-corridor class
            # that discards the whole cross-section: the near side of the
            # priced span is the axis's own edge, which the earlier
            # lateral pass has ALREADY given a node at every station, so
            # the near hit always lands on a vertex, ``hits`` never
            # reaches two, and no span is selected at all (measured at
            # CYXY apron ``shapeID 115``: 44 of 45 stations within
            # ``_CORNER_TOL_M`` of a ring vertex, 0 spans selected on the
            # pre-solve ring — while the SAME rule on the emitted ring
            # selects the 33 spans the census prices at 17.1-17.8 m.
            # That gap is the whole 48-row class, and it is why R-b
            # measured as "the emitter is not the lever": the emitter
            # was never reaching the specimen).  A hit within the corner
            # tolerance of a ring vertex is therefore kept as an
            # EXISTING foot — the node is already there, so the span is
            # complete and only the OTHER side needs planting.
            if t * L < _CORNER_TOL_M:
                hits.append((u, ei, t, (ax, ay), True))
            elif (1.0 - t) * L < _CORNER_TOL_M:
                hits.append((u, ei, t, (bx, by), True))
            else:
                hits.append((u, ei, t, (ax + t * ex, ay + t * ey), False))
        if len(hits) < 2:
            continue                      # not a cross-section here
        hits.sort(key=lambda h: h[0])
        # THE VALIDATOR'S OWN SPAN SELECTION, verbatim
        # (``check_grade._check_transverse_grade``): every CONSECUTIVE
        # hit pair is a candidate span; the one whose near side sits
        # closest to the axis wins, and a span whose nearest side is
        # further out than ``_SPAN_MAX_GAP_M`` is not the corridor the
        # axis runs down, so the law does not price it.  A STRICT
        # both-signs bracket is NOT the rule and was the miss: the wide-
        # corridor class is an axis running ALONG a pavement edge, where
        # every hit can land on ONE side of the section and the emitter
        # then inserted nothing at all (measured at CYXY: apron|apron
        # transverse stayed at 52 of the control's 3).
        span = None
        best_gap = None
        for j in range(len(hits) - 1):
            lo_h, hi_h = hits[j], hits[j + 1]
            width = hi_h[0] - lo_h[0]
            if width < _BRACKET_MIN_WIDTH_M:
                continue                  # narrower than the law prices
            gap = (0.0 if lo_h[0] <= 0.0 <= hi_h[0]
                   else min(abs(lo_h[0]), abs(hi_h[0])))
            if gap > _SPAN_MAX_GAP_M:
                continue                  # not this axis's corridor
            if min_span_m is not None and width <= float(min_span_m):
                continue                  # R-b: the fixed reach covers it
            mid = 0.5 * (lo_h[0] + hi_h[0])
            try:
                if not polys[si].contains(Point(vx + nx * mid,
                                                vy + ny * mid)):
                    continue              # the span is OUTSIDE the shape
            except _GEOM_EXC:
                continue
            if best_gap is None or gap < best_gap:
                best_gap = gap
                span = (lo_h, hi_h)
        if span is None:
            continue
        for h in span:
            if h[4]:
                continue          # already a ring vertex — nothing to plant
            inserts[si][h[1]].append((h[2], h[3]))
        # RULING (1): the span just SELECTED is the pair the census
        # prices — hand it to the caller so the pair that gets planted
        # is the pair that gets bound.
        if pairs_out is not None and cap_l is not None:
            if (priced_roles is not None and target_roles is not None
                    and target_roles[si] not in priced_roles):
                continue                  # not this axis's population
            pairs_out.append((si, span[0][3], span[1][3],
                              span[1][0] - span[0][0], float(cap_l)))


def insert_lateral_spine_nodes(layout, icao: str = "", *,
                               station_step_m: float = None) -> int:
    """Insert lateral-corridor vertices; returns the number inserted.

    ``station_step_m`` (default ``None`` = OFF, the pre-2026-08-08
    behaviour byte-for-byte) subdivides each centerline to that spacing
    BEFORE projecting, so the feet land at station spacing rather than
    at whatever spacing the source data happened to author.  Only the
    fabric-model RESTORATION call passes it: the pre-solve call above
    runs before the generic stationing that used to supply those nodes,
    while the restoration call runs after the fabric thinning has
    removed them and nothing else puts them back (measured at CYXY: a
    449 m apron edge beside a 470 m single-segment axis kept 4 vertices,
    and the transverse law then priced a 1.48 m cross-fall over 17.5 m).
    """
    centerlines = getattr(layout, "apt_taxi_centerlines", None) or []
    targets = [s for s in layout.shapes
               if s.role in _LATERAL_BODY_ROLES and s.polygon is not None
               and not s.polygon.is_empty
               and s.polygon.geom_type == "Polygon"]
    if not targets or not centerlines:
        return 0

    # (2026-07-29) The per-ref half-width lookup was fed by taxi-rect
    # shapes; with the rect roles retired no shape populates it, so every
    # centerline takes the default half-width (same as before by data).
    hw_by_ref: dict = {}

    polys = [s.polygon for s in targets]
    tree = STRtree(polys)

    # shape index -> {edge_index -> [(t, (fx, fy))]}
    inserts: dict = defaultdict(lambda: defaultdict(list))
    rings = [_open(p) for p in polys]
    n_rb = 0        # feet the R-b width-adaptive row rule contributed
    # RULING (1) · the priced spans, awaiting their landing check:
    # ``(shape_index, foot_lo, foot_hi, width_m, cap_l)``.
    xsec_spans: list = []
    target_roles = [s.role for s in targets]
    _vertex_hits = _xsection_vertex_hits_on()

    for entry in centerlines:
        ln = entry.line if hasattr(entry, "line") else (entry[0] if isinstance(entry, (tuple, list)) else entry)
        ref = (entry[1] if (isinstance(entry, (tuple, list)) and len(entry) > 1)
               else None)
        if ln is None or ln.is_empty or str(ref or "").upper().startswith("SVC"):
            continue
        hw = hw_by_ref.get(str(ref), _DEFAULT_HALF_W_M)
        try:
            cs = list(ln.coords)
        except _GEOM_EXC:
            continue
        # THE AXIS'S OWN LAW, read the way ``grade_graph.centerline_specs``
        # reads it (the ONE enumeration both the solver context and the
        # sidecar the census reads back are built from): per-SEGMENT
        # longitudinal cap from the route's per-segment ICAO size, or the
        # road cap for a SERVICE route.  Needed only for the pair record —
        # the planting geometry does not consult it.
        _is_svc = bool(getattr(entry, "is_service", False))
        _seg_caps = _axis_segment_caps(entry, len(cs) - 1, _is_svc)
        _seg_of: list = []
        if station_step_m and len(cs) >= 2:
            cs = _densify_to_step(cs, float(station_step_m),
                                  seg_index_out=_seg_of)
        # A TRUCK ROUTE IS NOT AN AIRCRAFT SPINE (the census's own rule,
        # ``check_grade._check_transverse_grade``): a service axis prices
        # the ROAD FAMILY's shapes only.  Scope for the RECORD; the
        # planting below is untouched by this ruling.
        _priced = (_SERVICE_AXIS_PRICED_ROLES if _is_svc
                   else _TAXI_AXIS_PRICED_ROLES)
        # ── R-b · WIDTH-ADAPTIVE LATERAL ROWS (lead ruling 2026-08-08) ──
        # The sparse floor's third member — spines, curves, AND
        # cross-sections.  The nearest-projection rule below finds a foot
        # only where the ring passes within ``hw``, and ``hw`` is a DEAD
        # LOOKUP's fallback (``_DEFAULT_HALF_W_M`` 12 m; nothing has
        # populated ``hw_by_ref`` since the rects retired).  That is not
        # the corridor the transverse law censuses: it walks the axis and
        # prices the ring SPAN that BRACKETS the axis, so an axis running
        # ALONG a pavement edge (CYXY apron ``shapeID 115``: axis on the
        # near edge, far edge 17-24 m out, one 449 m extent) is priced
        # with a far side the emitter never gave a node — an ~8 % lateral
        # cross-fall, a parked-aircraft lean, exactly the sharp-surface
        # class the fabric model must not ship.  So WHERE THE PRICED SPAN
        # EXCEEDS THE REACH the row is completed with the law's own
        # selection: cast the perpendicular, keep the NEAREST hit on EACH
        # side.  Bounded by construction: a bracket needs hits of BOTH
        # signs on ONE ring, which only a shape the station is INSIDE can
        # offer, and at most two feet per station per shape are inserted.
        # The rows ride the EXISTING 12 m station step (``station_step_m``
        # = ``config.SPINE_STEP_M``, R-c) and are ROUTE-TRANSPARENT by
        # R-a — they are recorded as cross-section feet below, so they
        # mint no route-graph edge.
        # ``O4_XSECTION_BRACKET`` (attempt 3, R-c-authorized, still
        # default OFF) drops the width condition: the plain union of the
        # two rules, which as an ALTERNATIVE to nearest-projection was
        # measured to trade one population for the other (CYXY transverse
        # 88 -> 89, apron|apron 57 both ways).
        _rb_span = (None if _xsection_bracket_on()
                    else (hw if _FF.on("O4_FABRIC_RB_WIDTH_ADAPTIVE_ROWS")
                          else _RB_DISABLED))
        for _vi, (vx, vy) in enumerate(cs):
            if station_step_m and _rb_span is not _RB_DISABLED:
                _before = sum(len(v) for e in inserts.values()
                              for v in e.values())
                _k = _seg_of[_vi] if _vi < len(_seg_of) else 0
                _cap_l = (_seg_caps[_k] if _k < len(_seg_caps)
                          else (_seg_caps[-1] if _seg_caps else None))
                _bracket_feet(vx, vy, cs, _vi, tree, rings, polys, inserts,
                              min_span_m=_rb_span,
                              cap_l=_cap_l,
                              pairs_out=xsec_spans,
                              priced_roles=_priced,
                              target_roles=target_roles,
                              vertex_hits=_vertex_hits)
                n_rb += (sum(len(v) for e in inserts.values()
                             for v in e.values()) - _before)
            P = Point(vx, vy)
            try:
                cand = tree.query(P.buffer(hw))
            except _GEOM_EXC:
                continue
            for qi in cand:
                si = int(qi)
                ring = rings[si]
                n = len(ring)
                for ei in range(n):
                    ax, ay = ring[ei]
                    bx, by = ring[(ei + 1) % n]
                    dx, dy = bx - ax, by - ay
                    seg2 = dx * dx + dy * dy
                    if seg2 < 1e-9:
                        continue
                    t = ((vx - ax) * dx + (vy - ay) * dy) / seg2
                    if t <= 0.0 or t >= 1.0:
                        continue
                    fx, fy = ax + t * dx, ay + t * dy
                    if math.hypot(fx - vx, fy - vy) > hw:    # within taxi-width
                        continue
                    L = math.sqrt(seg2)
                    if t * L < _CORNER_TOL_M or (1.0 - t) * L < _CORNER_TOL_M:
                        continue                              # too near a corner
                    inserts[si][ei].append((t, (fx, fy)))

    if not inserts:
        return 0

    n_added = 0
    # RULING (1): si -> the shape's FINAL ring vertices.  Not just the
    # planted feet: a span's near side is routinely a vertex the ring
    # already carried (the vertex-hit branch above), and a pair foot's
    # test is "is this a NODE of the emitted ring", whatever put it
    # there.  Seeded with the pre-insert ring for every shape a span
    # touched, then overwritten with the rebuilt ring where one landed.
    landed_by_shape: dict = {si: list(rings[si])
                             for (si, _a, _b, _w, _c) in xsec_spans
                             if si < len(rings)}
    for si, by_edge in inserts.items():
        ring = rings[si]
        n = len(ring)
        new_ring = []
        planted: list = []      # R-a: this shape's feet, if the ring lands
        for ei in range(n):
            new_ring.append(ring[ei])
            feet = sorted(by_edge.get(ei, []), key=lambda r: r[0])
            last = None
            for (_t, (fx, fy)) in feet:
                if last is not None and math.hypot(fx - last[0],
                                                   fy - last[1]) < _MERGE_TOL_M:
                    continue
                new_ring.append((fx, fy))
                planted.append((fx, fy))
                last = (fx, fy)
                n_added += 1
        if len(new_ring) <= n:
            continue
        try:
            poly = Polygon(new_ring)
            if poly.is_valid and not poly.is_empty:
                targets[si].polygon = poly
                # R-a: record only the feet that ACTUALLY LANDED.  A shape
                # whose rebuilt polygon is invalid keeps its old ring, so
                # its feet were never planted, and claiming route
                # transparency for a node that is something else would
                # silently delete a real route edge.
                record_lateral_feet(layout, planted)
                landed_by_shape[si] = list(new_ring)
        except _GEOM_EXC:
            continue

    # ── RULING (1) · THE PAIR RECORD, LANDING-FILTERED ────────────────
    # The same discipline R-a states for the feet, applied to the pairs:
    # a span is recorded as BOUND only where BOTH of its feet are nodes
    # of the shape's rebuilt ring.  A foot the merge tolerance folded
    # into its neighbour, or a shape whose rebuilt polygon was invalid,
    # yields no pair — the solve must never bind a node that is
    # something else.
    n_pairs = 0
    if xsec_spans:
        # STAGE AT MINT (S1b): the owning shape's LAWFUL role decides the
        # pair's stage, collected by the landing filter itself so the two
        # records are one act.
        from .solve_stage import stage_of_role as _sor
        _landed_si: list = []
        _pairs = list(_landed_pairs(xsec_spans, landed_by_shape,
                                    si_out=_landed_si))
        n_pairs = record_lateral_xsection_pairs(
            layout, _pairs,
            stages=[_sor(target_roles[si]) if si < len(target_roles) else None
                    for si in _landed_si])
    _dump = os.environ.get("O4_XSECTION_DUMP")
    if _dump:                                              # pragma: no cover
        import json as _json
        try:
            with open(_dump + ".spans", "a") as fh:
                for si, s in enumerate(targets):
                    _r = rings[si] if si < len(rings) else []
                    _el = sorted(math.hypot(_r[(k + 1) % len(_r)][0] - _r[k][0],
                                            _r[(k + 1) % len(_r)][1] - _r[k][1])
                                 for k in range(len(_r))) if _r else []
                    fh.write(_json.dumps({
                        "kind": "target", "si": si, "role": s.role,
                        "bbox": [round(v, 1) for v in s.polygon.bounds],
                        "n_ring": len(_r),
                        "edge_len_p50": (round(_el[len(_el) // 2], 2)
                                         if _el else None),
                        "edge_len_max": round(_el[-1], 2) if _el else None,
                        "n_landed": len(landed_by_shape.get(si, ()))}) + "\n")
                for (si, a, b, w, c) in xsec_spans:
                    fh.write(_json.dumps({
                        "kind": "span", "si": si, "a": list(a), "b": list(b),
                        "width_m": w, "cap_l": c}) + "\n")
        except OSError:
            pass

    if n_added:
        UI.vprint(1, f"  [pav-builder] {icao}: inserted {n_added} lateral "
                  f"corridor node(s) on apron/junction edges within taxi-width "
                  f"of a spine"
                  + (f" ({n_rb} of them from the R-b width-adaptive row rule, "
                     f"on {len(inserts)} shape(s); {n_pairs} priced "
                     f"cross-section pair(s) recorded for the solve)."
                     if station_step_m else "."))
    return n_added


def insert_service_lateral_nodes(layout, icao: str = "") -> int:
    """SPINE-FIRST service roads (config.SVC_SPINE_FIRST, part 30m): insert
    lateral cross-section vertices on SERVICE shape edges from the SERVICE
    centerlines — the REGISTERED chains (``grade_graph.service_chain_lines``)
    unioned with the apt.dat row-1206 truck-route courses (R2, service-road
    law spec 2026-08-15) — which :func:`insert_lateral_spine_nodes`
    deliberately skips (SVC lines must not couple APRONS to the road law).

    A service road's law edges (it joins ``grade_graph.SOFT_VISIBILITY_ROLES``
    under the gate) are vertex-pair based, and a road's long edges can run
    70-100 m with no intermediate vertex (the CYXY in-sim "ridge" report) —
    the 2 % transverse law then binds only at the far-apart corners, whose
    budget dwarfs the road width.  Projecting each spine STATION (centerline
    vertices, densified to ~SPINE_STEP_M) onto both road edges gives the law
    aligned cross-section pairs at station spacing: |Δz| across the road is
    then capped at SERVICE_ROAD_MAX_TRANSVERSE × width everywhere — the
    cross-road tear becomes unrepresentable.

    Same foot-insertion mechanics as :func:`insert_lateral_spine_nodes`
    (perpendicular foot, corner/merge tolerances); targets are the SERVICE
    roles only.  Runs pre-solve immediately after the taxi lateral pass, so
    conformance welds the new vertices into neighbouring shapes.  Returns the
    number of vertices inserted."""
    from .config import ROAD_CARVE_MAX_WIDTH_M, SPINE_STEP_M
    # R2 (service-road law spec, 2026-08-15): THE LATERAL PASS READS THE
    # REGISTERED CHAINS.  ``grade_graph.service_chain_lines`` is THE
    # service centerline set (corridor chains + scoped feed roads where
    # the slice ran; the row-1206 originals in unit fixtures) — the same
    # source the DEM-follow seeder was fixed to by the corridor-joins
    # round's ruling 3.  Reading ``apt_taxi_centerlines`` filtered on
    # ``is_service`` here saw the apt.dat row-1206 courses ONLY, so
    # cross-sections on feed-chain roads were never planted and lateral
    # co-leveling had no substrate (measured at HECA: 24 courses vs 816
    # registered chains; 492 cross-section nodes airport-wide).  The
    # 1206 courses stay in as chains too — union, deduped by the
    # existing chain dedupe (``_corridor_cover``/``_covered_by_corridor``,
    # the "is this the same physical road" halo test) — so nothing
    # mapped is dropped.  Function-local import: ``grade_graph`` imports
    # this module at module level.
    from .grade_graph import (_corridor_cover, _covered_by_corridor,
                              service_chain_lines)
    centerlines = getattr(layout, "apt_taxi_centerlines", None) or []
    targets = [s for s in layout.shapes
               if s.role in SERVICE_AXIS_PRICED_ROLES
               and s.polygon is not None and not s.polygon.is_empty
               and s.polygon.geom_type == "Polygon"]
    chains = [ln for ln in service_chain_lines(layout)
              if ln is not None and not ln.is_empty]
    courses = [cl.line for cl in centerlines
               if getattr(cl, "is_service", False)
               and getattr(cl, "line", None) is not None
               and not cl.line.is_empty]
    cover = _corridor_cover(chains) if chains else None
    svc_lines = chains + [ln for ln in courses
                          if not _covered_by_corridor(ln, cover)]
    if not targets or not svc_lines:
        return 0

    # Cross-section half-width: the widest pavement the road carve classifies
    # (+ margin) so edge-hugging carved shapes still catch their feet.
    hw = ROAD_CARVE_MAX_WIDTH_M / 2.0 + 2.0

    polys = [s.polygon for s in targets]
    tree = STRtree(polys)
    inserts: dict = defaultdict(lambda: defaultdict(list))
    rings = [_open(p) for p in polys]

    def _stations(cs):
        """Centerline vertices densified to ≤ SPINE_STEP_M spacing (a 1206
        truck route can run long straight legs with sparse vertices — the
        exact stretches that tear).  ONE implementation, shared with the
        taxi pass's ``station_step_m`` mode (``_densify_to_step``)."""
        return _densify_to_step(cs, SPINE_STEP_M)

    for ln in svc_lines:
        try:
            cs = list(ln.coords)
        except _GEOM_EXC:
            continue
        if len(cs) < 2:
            continue
        for (vx, vy) in _stations(cs):
            P = Point(vx, vy)
            try:
                cand = tree.query(P.buffer(hw))
            except _GEOM_EXC:
                continue
            for qi in cand:
                si = int(qi)
                ring = rings[si]
                n = len(ring)
                for ei in range(n):
                    ax, ay = ring[ei]
                    bx, by = ring[(ei + 1) % n]
                    dx, dy = bx - ax, by - ay
                    seg2 = dx * dx + dy * dy
                    if seg2 < 1e-9:
                        continue
                    t = ((vx - ax) * dx + (vy - ay) * dy) / seg2
                    if t <= 0.0 or t >= 1.0:
                        continue
                    fx, fy = ax + t * dx, ay + t * dy
                    if math.hypot(fx - vx, fy - vy) > hw:
                        continue
                    L = math.sqrt(seg2)
                    if t * L < _CORNER_TOL_M or (1.0 - t) * L < _CORNER_TOL_M:
                        continue
                    inserts[si][ei].append((t, (fx, fy)))

    if not inserts:
        return 0

    n_added = 0
    for si, by_edge in inserts.items():
        ring = rings[si]
        n = len(ring)
        new_ring = []
        planted: list = []      # R-a: this shape's feet, if the ring lands
        for ei in range(n):
            new_ring.append(ring[ei])
            feet = sorted(by_edge.get(ei, []), key=lambda r: r[0])
            last = None
            for (_t, (fx, fy)) in feet:
                if last is not None and math.hypot(fx - last[0],
                                                   fy - last[1]) < _MERGE_TOL_M:
                    continue
                new_ring.append((fx, fy))
                planted.append((fx, fy))
                last = (fx, fy)
                n_added += 1
        if len(new_ring) <= n:
            continue
        try:
            poly = Polygon(new_ring)
            if poly.is_valid and not poly.is_empty:
                targets[si].polygon = poly
                record_lateral_feet(layout, planted)   # R-a
        except _GEOM_EXC:
            continue

    if n_added:
        UI.vprint(1, f"  [pav-builder] {icao}: inserted {n_added} service "
                  f"cross-section node(s) on road/service-junction edges from "
                  f"the truck-route spine (spine-first law sampling).")
    return n_added
