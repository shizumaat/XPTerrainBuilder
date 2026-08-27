"""THE AIRSIDE NO-STEP LAW — §1 of
docs/specs/airside-no-step-law-spec.md (Fable, 2026-08-27).

OWNER RULING (RULINGS 2026-08-27, "NO STEPS IN AIRSIDE PAVEMENT"):
*"If our laws allow a step of 1.5 m, then the law needs to be updated to
prevent that, as it would create an impassable area for aircraft.  No
steps in airside pavement are lawful."*  Refined the same day: *"A 1.5 m
'dip' could be ok assuming it was spread across enough area to be smooth,
like the runway curvature and rate change rules."*

THE GAP THIS CLOSES IS AN ACCUMULATION GAP.  At the round-3 dip site
(``30.1290177,31.4055841``) every pointwise NEIGHBOUR pair was inside its
budget and the surface still carried +0.60 m of relief across 30 m and
+1.07 m across 50-75 m: the low membrane nodes sat 130-137 m from the
nearest anchored station and were coupled to it only through a CHAIN of
50 m x cap budgets, which accumulate.  No law family priced a
NON-NEIGHBOUR airside pair against its DIRECT distance, so both surfaces
were lawful as written.  This module adds that missing population.

WHAT IT IS NOT.  It is not a new cap, not a new grade number and not a
second authority on any profile.  Every budget here comes out of
``grade_law.classify_pair`` — the ONE cap chain — evaluated on a pair
context this module assembles the same way ``grade_graph.shape_
constraints`` assembles a within-shape one, and multiplied by the pair's
DIRECT euclidean distance (the ruling's "not path distance": no route-arc
credit, because the accumulation the ruling forbids is exactly what an
arc credit legalises).

THE SENIORITY LADDER (spec §1.3, the adoption-not-constraint principle
made explicit).  runway profile > taxi centerline profile (spine stations
included — round-3 Amendment 2 made them phase-A constants) > seated pads
> membrane free nodes.  A cross-tier edge constrains the LOWER tier only.
The mechanism is the round-3 Amendment 1 one, reused verbatim: the senior
endpoint is a CONSTANT in the membrane solve (``base_hard`` and preserved
out of the spine-yield set), so the only way the projection can satisfy
the edge is to move the junior side.  Measured basis for insisting on it
(lane round3spine A2/A3): with a SYMMETRIC coupling the projection
satisfied the new edges by lowering the ANCHORED side — the opposite of
airside-is-king.  An edge inside the free tier stays symmetric.
"""
from __future__ import annotations

import math

_GEOM_EXC = Exception

#: Compass sectors the k-nearest selection spreads over (spec §1.3,
#: "k bounded, default 16, spatially spread").  Eight is the coarsest
#: split that still gives a node a neighbour on every side of itself:
#: the nearest 16 nodes of a dense apron ring are all along the ring, so
#: a plain nearest-k would leave the node uncoupled ACROSS the surface —
#: which is the very geometry the dip has.
_SECTORS = 8

#: Provenance stamped on every published record.  ONE spelling: the
#: sidecar key, the census family and the constraint ``ref`` all use it.
PROVENANCE = "airside_no_step"

#: Seniority tiers (spec §1.3).  Lower number = more senior.
TIER_RUNWAY = 1
TIER_CENTERLINE = 2
TIER_SEAT = 3
TIER_FREE = 4


def airside_shape_roles():
    """THE REGISTER, never a hand list (spec §1.1).

    ``enclaves.ENCLAVE_AIRSIDE_ROLES`` is the engine's one enumeration of
    "airside pavement a vehicle cannot cross without being on the
    airfield" — the same eight roles ``clearance._AIRSIDE_PAVEMENT_ROLES``
    and ``pavement_scoring._CHAIN_ROLES`` carry, pinned equal by
    ``tests/test_enclave_region.py``.
    """
    from .enclaves import ENCLAVE_AIRSIDE_ROLES
    return ENCLAVE_AIRSIDE_ROLES


def taxiway_family_roles():
    """THE TIER-2 SURFACE (spec Amendment 1 ruling 1, 2026-08-27).

    *"Every node of taxiway-family pavement (taxiway, junction, stub,
    primary_parallel — ring or interior) is tier 2: that surface is the
    centerline profile's TRANSVERSE WRITEBACK, and letting the no-step
    edges renegotiate it re-creates the round-3 anchored-side disease."*

    The register is the solve's OWN taxi-route role set
    (``route_profile.anchors._ROUTE_ROLES`` — the set
    ``apron_body_nodes`` already partitions "route" from "DEM-follow
    body" with), imported and never re-spelled: a second hand list here
    is the census-wrapper defect in miniature, and the blast index's
    role-literal hazard on top of it.
    """
    from .elevation_per_surface.route_profile.anchors import _ROUTE_ROLES
    return _ROUTE_ROLES


def taxiway_family_nodes(layout, bucket_to_idx, n_nodes):
    """Every solver node carried by a TAXIWAY-FAMILY shape (tier 2)."""
    from .elevation_per_surface.solver_primitives import _open_ring
    roles = taxiway_family_roles()
    cps = layout.canonical_points
    out: set = set()
    for s in (getattr(layout, "shapes", None) or ()):
        if (getattr(s, "role", None) or "") not in roles:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        try:
            ring = _open_ring(list(poly.exterior.coords))
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        for (x, y) in ring:
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None and 0 <= i < n_nodes:
                out.add(int(i))
    return out


def _airside_shapes(layout):
    roles = airside_shape_roles()
    out = []
    for s in (getattr(layout, "shapes", None) or ()):
        if (getattr(s, "role", None) or "") not in roles:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        out.append(s)
    return out


def airside_pavement_union(layout):
    """PREPARED union of every airside pavement polygon, or ``None``.

    This is the population the §1.1 chord VISIBILITY is priced across —
    "within one shape AND across airside shape boundaries".  It is the
    same construction ``clearance`` already makes for the same role set
    (``unary_union`` over the airside shapes, then ``prep``); a chord
    that leaves it crosses a pavement GAP, and RULINGS 2026-08-24b is
    explicit that a step is lawful exactly there ("unless there is a
    pavement gap there are NO cliffs in aprons").
    """
    shapes = _airside_shapes(layout)
    if not shapes:
        return None
    try:
        from shapely.ops import unary_union
        u = unary_union([s.polygon for s in shapes])
        if u.is_empty:
            return None
        return u
    except _GEOM_EXC:                                     # pragma: no cover
        return None


def _node_shapes(layout, bucket_to_idx, n_nodes):
    """``{node_idx: [shape, ...]}`` over AIRSIDE ring vertices, plus the
    apron interior constructs that are airside membrane by construction
    (the round-2 lattice and the round-3 spine stations — both live
    INSIDE an apron polygon and both carry that apron's own law)."""
    from .elevation_per_surface.solver_primitives import _open_ring
    cps = layout.canonical_points
    out: dict = {}

    def _add(i, s):
        if i is None or not (0 <= i < n_nodes):
            return
        lst = out.get(i)
        if lst is None:
            out[i] = [s]
        elif s not in lst:
            lst.append(s)

    for s in _airside_shapes(layout):
        try:
            ring = _open_ring(list(s.polygon.exterior.coords))
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        for (x, y) in ring:
            _add(bucket_to_idx.get(cps.get_or_add(float(x), float(y))), s)
    # The apron INTERIOR constructs.  A lattice point and a spine station
    # are apron membrane — they are the interior the apron had no
    # vertices for — so they are airside nodes for this law exactly as
    # they are for ``apron_lattice_membrane``.
    for store in ("apron_lattice_presolve", "apron_spine_presolve"):
        for entry in (getattr(layout, store, None) or ()):
            s = entry.get("shape")
            if s is None:
                continue
            for (x, y) in (entry.get("points") or ()):
                _add(bucket_to_idx.get(cps.get_or_add(float(x), float(y))),
                     s)
    return out


def tier_of_nodes(n_nodes, *, runway_nodes=None, centerline_nodes=None,
                  seat_nodes=None):
    """``{node_idx: tier}`` for the SENIOR tiers (spec §1.3).

    A node absent from the result is free-tier.

    THE MAX-TIER RULE (spec Amendment 1 ruling 1): *"a node shared
    between shapes takes the SENIOR tier"* — the ladder's own
    precedence, runway profile over centerline profile over a seated
    pad.  It is what closes the runway+service-road CARVE CORNERS the
    first arm moved (measured: 5 at HECA, worst 1.03 m; 4 at SPJC,
    worst 1.44 m — every one of them a node a runway ring shares with
    another role).  Written by ASSIGNING in ladder order, most junior
    first, so the senior write always lands last.
    """
    out: dict = {}
    for src, tier in ((seat_nodes, TIER_SEAT),
                      (centerline_nodes, TIER_CENTERLINE),
                      (runway_nodes, TIER_RUNWAY)):
        for i in (src or ()):
            k = int(i)
            if 0 <= k < n_nodes:
                out[k] = tier
    return out


def _spread_candidates(pts, window_m, k):
    """``[(i, j), ...]`` — the k-nearest-in-window pairs, SPATIALLY
    SPREAD, over ``pts`` (an ``(n, 2)`` array of local metres).

    Per node: bucket its in-window neighbours into ``_SECTORS`` compass
    sectors by bearing, keep the nearest ``ceil(k / _SECTORS)`` in each,
    then top up to ``k`` from the remaining nearest.  Deterministic —
    ties break on the neighbour's own node ordinal, which is the
    canonical registry's order.
    """
    import numpy as np
    n = len(pts)
    if n < 2 or k <= 0 or window_m <= 0.0:
        return []
    from scipy.spatial import cKDTree
    tree = cKDTree(pts)
    neigh = tree.query_ball_point(pts, r=float(window_m))
    per_sector = max(1, int(math.ceil(k / float(_SECTORS))))
    two_pi = 2.0 * math.pi
    pairs: set = set()
    for i in range(n):
        cand = neigh[i]
        if len(cand) < 2:
            continue
        idx = np.asarray(cand, dtype=np.int64)
        idx = idx[idx != i]
        if idx.size == 0:
            continue
        d = pts[idx] - pts[i]
        dist = np.hypot(d[:, 0], d[:, 1])
        order = np.lexsort((idx, dist))
        idx, dist, d = idx[order], dist[order], d[order]
        sect = np.floor(
            (np.arctan2(d[:, 1], d[:, 0]) % two_pi) / (two_pi / _SECTORS)
        ).astype(np.int64)
        taken = 0
        counts = [0] * _SECTORS
        chosen = []
        for p in range(idx.size):
            s = int(sect[p])
            if counts[s] >= per_sector:
                continue
            counts[s] += 1
            chosen.append(int(idx[p]))
            taken += 1
            if taken >= k:
                break
        if taken < k:
            got = set(chosen)
            for p in range(idx.size):
                j = int(idx[p])
                if j in got:
                    continue
                chosen.append(j)
                taken += 1
                if taken >= k:
                    break
        for j in chosen:
            pairs.add((i, j) if i < j else (j, i))
    return sorted(pairs)


class _PairFacts:
    """Per-node law membership, computed ONCE through the SAME readers
    ``grade_graph.shape_constraints`` uses — never a second predicate."""

    def __init__(self, layout, ctx, node_ids, coords, node_shapes):
        from . import grade_graph as GG
        self.ctx = ctx
        self.node_ids = node_ids
        self.coords = coords
        self.node_shapes = node_shapes
        keys = list(node_ids)
        self.frontage = [k in ctx.frontage_keys for k in keys]
        self.building = [k in ctx.building_keys for k in keys]
        self.seam = [k in ctx.seam_keys for k in keys]
        try:
            self.in_strip = list(GG.strip_excluded_flags(coords, ctx))
        except _GEOM_EXC:                                 # pragma: no cover
            self.in_strip = [False] * len(keys)
        try:
            zf = list(GG.interior_zone_flags(coords, ctx))
            self.zone = zf if any(z >= 0 for z in zf) else None
        except _GEOM_EXC:                                 # pragma: no cover
            self.zone = None
        cover = None
        try:
            cover = GG.corridor_cover_prepared(ctx)
        except _GEOM_EXC:                                 # pragma: no cover
            cover = None
        if cover is None:
            self.cover = [False] * len(keys)
        else:
            from shapely.geometry import Point as _P
            self.cover = [bool(cover.intersects(_P(x, y)))
                          for (x, y) in coords]
        road = getattr(ctx, "road_zone", None)
        if road is None:
            self.road = [False] * len(keys)
        else:
            from shapely.geometry import Point as _P2
            self.road = [bool(road.contains(_P2(x, y))) for (x, y) in coords]
        self._cap_memo: dict = {}

    def shape_law(self, s):
        """``(role, body_cap, has_membership)`` for one shape, through
        ``grade_graph``'s OWN ``_body_cap`` / ``_spine_membership`` —
        memoized per shape, because a shape's body cap is a property of
        the shape and not of the pair."""
        key = id(s)
        got = self._cap_memo.get(key)
        if got is not None:
            return got
        from . import grade_graph as GG
        from .elevation_per_surface.solver_primitives import _open_ring
        role = getattr(s, "role", None) or ""
        try:
            ring = _open_ring(list(s.polygon.exterior.coords))
            gs = GG.GradeShape(
                role=role, ring=list(ring),
                keys=list(range(len(ring))),
                fan_ramp_zone=getattr(s, "fan_ramp_zone", False),
                lateral_cap=getattr(s, "lateral_cap", None))
            membership = GG._spine_membership(gs, self.ctx)
            cap = float(GG._body_cap(gs, self.ctx, membership))
        except _GEOM_EXC:                                 # pragma: no cover
            from .config import ROLE_GRADE_LIMITS
            cap = float(ROLE_GRADE_LIMITS.get(role) or 0.015)
            membership = {}
        got = (role, cap, bool(membership))
        self._cap_memo[key] = got
        return got

    def side(self, p):
        """``(role, body_cap, corridor_connected)`` for ONE endpoint —
        the STRICTEST claim among the airside shapes whose ring carries
        it (a welded node is claimed by several)."""
        best = None
        for s in self.node_shapes.get(self.node_ids[p], ()):  # deterministic
            role, cap, membership = self.shape_law(s)
            conn = bool(membership) or bool(self.cover[p])
            if best is None or cap < best[1]:
                best = (role, cap, conn)
            elif cap == best[1] and conn and not best[2]:
                best = (best[0], best[1], True)
        if best is None:                                  # pragma: no cover
            from .config import TAXI_MAX_GRADE
            return ("junction", float(TAXI_MAX_GRADE), bool(self.cover[p]))
        return best


def build_airside_no_step_constraints(
        layout, bucket_to_idx, ctx, *, node_pos, n_nodes,
        tier_of=None, existing_pairs=None, window_m=None, k=None):
    """THE §1.1 / §1.3 EDGE BUILD.

    Returns ``(sc_entries, senior_idx, edge_records, report)``.

    * ``sc_entries`` — within-shape-shaped constraint entries carrying the
      new law edges, ready to EXTEND ``shape_constraints``.  They are
      stage A by construction (every endpoint is airside pavement).
    * ``senior_idx`` — the SENIOR endpoints of every cross-tier edge.
      The caller preserves them out of the spine-yield set, which is what
      makes those edges one-sided in practice (spec §1.3, the round-3
      Amendment 1 mechanism).
    * ``edge_records`` — the sidecar publication the census prices
      (spec §1.6: "prices exactly the sidecar-published §1.3 edge
      enumeration" — solver publishes, census prices the same list).
    * ``report`` — population arithmetic, printed by the caller.

    ``node_pos`` is ``G.pos`` (the solve's OWN positions); no second
    coordinate frame is built here.

    ``existing_pairs`` is the set of ``(min, max)`` node pairs already
    carried by ``shape_constraints``.  A pair stated twice would hand the
    POCS sweep two copies of one law — the round-3 station build drops
    restated pairs for exactly this reason.
    """
    from . import config as _cfg
    from . import grade_law as GL
    from .solve_stage import STAGE_A, STAGE_KEY
    report = {"airside_nodes": 0, "candidates": 0, "already_stated": 0,
              "not_visible": 0, "skipped_by_law": 0, "edges": 0,
              "cross_tier": 0, "senior_nodes": 0, "by_class": {},
              "skipped_long_apron": 0, "tier2_census_only": 0,
              "published": 0}
    if not getattr(_cfg, "AIRSIDE_NO_STEP", False):
        return [], set(), [], report
    if window_m is None:
        window_m = float(getattr(_cfg, "AIRSIDE_NO_STEP_WINDOW_M", 150.0))
    if k is None:
        k = int(getattr(_cfg, "AIRSIDE_NO_STEP_K", 16))
    node_shapes = _node_shapes(layout, bucket_to_idx, n_nodes)
    node_ids = [i for i in sorted(node_shapes) if i in node_pos]
    if len(node_ids) < 2:
        return [], set(), [], report
    report["airside_nodes"] = len(node_ids)
    import numpy as np
    coords = [(float(node_pos[i][0]), float(node_pos[i][1]))
              for i in node_ids]
    pts = np.asarray(coords, dtype=float)
    cand = _spread_candidates(pts, window_m, k)
    report["candidates"] = len(cand)
    if not cand:
        return [], set(), [], report

    existing = existing_pairs or frozenset()
    tier_of = tier_of or {}
    facts = _PairFacts(layout, ctx, node_ids, coords, node_shapes)

    # ── VISIBILITY, BATCHED ──────────────────────────────────────────
    # One GEOS prepared-predicate pass over every surviving chord rather
    # than one Python round trip per chord (the ``grade_graph`` row-batch
    # idiom, same predicate).
    union = airside_pavement_union(layout)
    keep_pairs = []
    for (a, b) in cand:
        ia, ib = node_ids[a], node_ids[b]
        pair = (ia, ib) if ia < ib else (ib, ia)
        if pair in existing:
            report["already_stated"] += 1
            continue
        keep_pairs.append((a, b))
    if union is not None and keep_pairs:
        try:
            import shapely as _sh
            from shapely.geometry import LineString as _LS
            _sh.prepare(union)
            lines = np.array(
                [_LS((coords[a], coords[b])) for (a, b) in keep_pairs],
                dtype=object)
            vis = _sh.covers(union, lines)
            visible = [bool(v) for v in vis]
        except _GEOM_EXC:                                 # pragma: no cover
            visible = [True] * len(keep_pairs)
    else:
        visible = [True] * len(keep_pairs)

    by_role: dict = {}
    edge_records: list = []
    senior_idx: set = set()
    _carry: list = []
    apron_role = GL.APRON_ROLE
    body_gate = float(getattr(GL, "APRON_BODY_CHORD_MAX_M", 0.0) or 0.0)
    for p, (a, b) in enumerate(keep_pairs):
        if not visible[p]:
            report["not_visible"] += 1
            continue
        ia, ib = node_ids[a], node_ids[b]
        (xa, ya), (xb, yb) = coords[a], coords[b]
        d = math.hypot(xb - xa, yb - ya)
        role_a, cap_a, conn_a = facts.side(a)
        role_b, cap_b, conn_b = facts.side(b)
        if cap_a <= cap_b:
            role, body_cap = role_a, cap_a
        else:
            role, body_cap = role_b, cap_b
        pc = GL.PairContext(
            role=role, dist=d, ring_adjacent=False,
            a_seam=facts.seam[a], b_seam=facts.seam[b],
            a_building=facts.building[a], b_building=facts.building[b],
            # NOT a spine pair: a pair whose two ends lie on ONE
            # centerline is that centerline's own longitudinal profile,
            # which this law never re-prices (the round-3 station build
            # drops station<->station pairs for the same reason).
            spine_caps=(), body_cap=min(cap_a, cap_b),
            # VISIBILITY IS ALREADY DECIDED (batched above) — a chord
            # that survived is visible across the airside union, so the
            # thunk would only re-ask the same question per-shape and get
            # a WRONGLY narrow answer for a cross-shape pair.
            visible_fn=None,
            # NOT ASKED, deliberately: "the climb is carried by the
            # SPINE, not this diagonal" is a statement about a SHAPE'S
            # OWN body chord across its own corridor.  This population is
            # the direct-distance neighbourhood the ruling names, and the
            # accumulation it forbids is precisely what deferring to the
            # spine's path distance permits.
            crosses_spine_fn=None,
            mesh_member_fn=None, blend_cap_fn=None,
            both_road=bool(facts.road[a] and facts.road[b]),
            a_frontage=facts.frontage[a], b_frontage=facts.frontage[b],
            a_corridor=facts.cover[a], b_corridor=facts.cover[b],
            nearest_spine=False, nearest_anchor_pad=False,
            a_in_strip=facts.in_strip[a], b_in_strip=facts.in_strip[b],
            in_interior_zone=(
                facts.zone is not None and facts.zone[a] >= 0
                and facts.zone[a] == facts.zone[b]),
            corridor_connected=bool(conn_a and conn_b))
        allow = GL.classify_pair(pc)
        if allow is None:
            report["skipped_by_law"] += 1
            # THE ONE SKIP CLASS THIS LAW'S WINDOW OUTRUNS, counted so it
            # can never be inferred from silence: ``classify_pair`` drops
            # an APRON body chord beyond ``APRON_BODY_CHORD_MAX_M``
            # (60 m).  Reported; NOT overridden here (that would be a
            # spec deviation, and deviations are the owner's call).
            if (role == apron_role and body_gate and d > body_gate):
                report["skipped_long_apron"] += 1
            continue
        # THE DIRECT DISTANCE IS THE BUDGET'S LENGTH — the ruling's own
        # words, "|Δz| <= cap x DIRECT distance (not path distance)".
        # ``Allowance.at(d, 0.0)`` is the flat evaluation every reader
        # uses; no route arc, no anisotropic credit.
        budget = float(allow.at(d, 0.0))
        if budget <= 0.0:                                 # pragma: no cover
            report["skipped_by_law"] += 1
            continue
        ta = int(tier_of.get(ia, TIER_FREE))
        tb = int(tier_of.get(ib, TIER_FREE))
        # ── TIER2 <-> TIER2 IS CENSUS-PRICED, NOT SOLVER-IMPOSED (spec
        # Amendment 1 ruling 1, report-first) ────────────────────────
        # Both endpoints are the taxiway-family surface, i.e. the
        # CENTERLINE PROFILE's own transverse writeback.  A violating
        # pair there is a PROFILE-LAW docket — two authorities
        # disagreeing — and imposing it here would make the membrane
        # law a third authority arbitrating between them, which is the
        # solver tug-of-war the ruling forbids.  The record is still
        # PUBLISHED, so the census prices it and the docket has a
        # number; it simply never becomes a constraint entry.
        imposed = not (ta == TIER_CENTERLINE and tb == TIER_CENTERLINE)
        if not imposed:
            report["tier2_census_only"] += 1
        elif ta != tb:
            report["cross_tier"] += 1
            senior_idx.add(ia if ta < tb else ib)
        cls = GL.apron_pair_class(pc) if role == apron_role else role
        report["by_class"][cls] = report["by_class"].get(cls, 0) + 1
        if imposed:
            by_role.setdefault(role, []).append((ia, ib, budget))
        _carry.append((a, b, budget, imposed))
        try:
            la = layout.m_to_ll(xa, ya)
            lb = layout.m_to_ll(xb, yb)
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        edge_records.append({
            "a": [round(float(la[0]), 11), round(float(la[1]), 11)],
            "b": [round(float(lb[0]), 11), round(float(lb[1]), 11)],
            "budget_m": round(budget, 6),
            "dist_m": round(d, 4),
            "tier_a": ta, "tier_b": tb,
            # Whether the SOLVE built to this pair or only the census
            # prices it (spec Amendment 1 ruling 1).  Published so a
            # reader can never mistake a report-first tier2 pair for a
            # constraint the projection failed to meet.
            "imposed": bool(imposed),
            "provenance": PROVENANCE})
    # THE GEOMETRY CARRY for the pass-2 membrane conform (spec
    # Amendment 2).  Pass 2 runs in a REBUILT node space, so the pairs
    # travel as local-metre GEOMETRY and are re-resolved through the
    # canonical registry there — never as indices (the rod-key lesson,
    # and the same rule the apron terrace plan is re-bound by).
    layout._airside_no_step_pairs_m = [
        (float(coords[a][0]), float(coords[a][1]),
         float(coords[b][0]), float(coords[b][1]), float(bud), bool(imp))
        for (a, b, bud, imp) in _carry]
    sc_out: list = []
    for role, edges in sorted(by_role.items()):
        if not edges:
            continue
        nodes = sorted({a for (a, _b, _c) in edges}
                       | {b for (_a, b, _c) in edges})
        sc_out.append({"nodes": nodes, "edges": edges, "flat": False,
                       "flat_pairs": (), "area": 0.0, "role": role,
                       STAGE_KEY: STAGE_A, "ref": PROVENANCE})
        report["edges"] += len(edges)
    report["senior_nodes"] = len(senior_idx)
    report["published"] = len(edge_records)
    return sc_out, senior_idx, edge_records, report


def format_report(icao: str, report: dict) -> str:
    """The build log's one line."""
    return (f"  [airside-no-step] {icao}: {report['published']} "
            f"direct-distance pair(s) published, {report['edges']} of them "
            f"SOLVER-IMPOSED ({report['tier2_census_only']} tier2<->tier2 "
            f"pair(s) census-priced only — a profile-law docket, spec "
            f"Amendment 1) over {report['airside_nodes']} airside node(s) "
            f"from {report['candidates']} k-nearest candidate(s) "
            f"({report['already_stated']} already stated by a within-shape "
            f"entry, {report['not_visible']} crossing a pavement GAP, "
            f"{report['skipped_by_law']} not law under classify_pair "
            f"— {report['skipped_long_apron']} of them apron chords beyond "
            f"the 60 m body gate); {report['cross_tier']} cross-tier edge(s) "
            f"hold {report['senior_nodes']} senior node(s) CONSTANT "
            f"(RULINGS 2026-08-27)")


# ══════════════════════════════════════════════════════════════════════
# §1.4 — DEM DEMOTION FOR THE AIRSIDE MEMBRANE INTERIOR
# ══════════════════════════════════════════════════════════════════════

def dem_demoted_nodes(layout, bucket_to_idx, n_nodes, apron_body,
                      extra_interior=()):
    """The AIRSIDE membrane interior FREE nodes that carry no DEM-
    proximity objective term (spec §1.4).

    RULINGS 2026-08-25 (DEM IS LAST PRIORITY) already demoted DEM to the
    lowest-priority tiebreaker; RULINGS 2026-08-27 clause 3 enforces it
    for this class, because the sag that produced the owner's dip was
    exactly a DEM preference INSIDE the lawful range.

    ``apron_body`` is ``anchors.apron_body_nodes`` (plus the lattice, as
    the caller merges it) — a set that deliberately also carries the
    GROUNDSIDE DEM-follow roles (service roads/junctions), which must
    keep their DEM target: a service road IS terrain-tied.  So the set is
    intersected with the airside register here.
    """
    from .config import AIRSIDE_NO_STEP
    if not AIRSIDE_NO_STEP:
        return set()
    airside = set(_node_shapes(layout, bucket_to_idx, n_nodes))
    airside |= {int(i) for i in extra_interior
                if 0 <= int(i) < n_nodes}
    return {int(i) for i in apron_body
            if 0 <= int(i) < n_nodes and int(i) in airside}


# ══════════════════════════════════════════════════════════════════════
# PASS 2 — THE MEMBRANE CONFORM (spec Amendment 2, 2026-08-27)
# ══════════════════════════════════════════════════════════════════════
#
# THE MECHANISM FINDING THIS ANSWERS.  The one-solve graph expresses
# one-sidedness only against a CONSTANT, and a junction ring vertex is a
# free variable of its OWN within-shape law — so an imposed tier2<->tier4
# edge still moved it (measured A1: HECA taxiway-family movers 3,342 of
# 6,233, worst 1.52 m).  Freezing tier 2 at phase-A values differs from
# the flag-off arm in the OTHER direction; making tier2<->tier4
# report-first deletes the coupling that lifts the membrane.  The staged
# principle (round-3 Amendment 1) is the ruled answer:
#
#   PASS 1  the solve with NO imposed no-step edge and no DEM demotion —
#           byte-identical to the flag-off arm BY CONSTRUCTION.  Nothing
#           in this module touches it; that is the assertion, not an
#           argument.
#   PASS 2  every tier-1/2/3 node is a CONSTANT at its pass-1 value and
#           only tier-4 membrane nodes are free.  The no-step edges
#           (senior<->4 one-sided against the constants by construction,
#           4<->4 symmetric) are imposed TOGETHER WITH the tier-4 nodes'
#           own existing laws and the §1.4 DEM demotion, and the surface
#           is re-projected.  Tier 4 emits pass-2 values; everything else
#           emits pass-1 values, untouched.
#
# Senior byte-identity therefore needs no gate: the senior values ARE the
# flag-off values.  The runway carve-corner movers vanish for the same
# reason — a node a runway ring shares is max-tier tier 1, hence a
# constant, so the emit author cannot flip.


def membrane_free_nodes(layout, bucket_to_idx, n_nodes, *, crown_of=None):
    """``(free, constants, tiers)`` for pass 2.

    FREE = the airside nodes that are tier 4 under the MAX-TIER rule: the
    apron membrane (apron ring vertices, the interior lattice) and
    nothing else.  A node any senior shape also carries — a runway ring,
    the taxiway family, a building pad — is a CONSTANT, which is what
    makes every cross-tier edge one-sided without a per-edge facility.

    A CROWNED node is excluded from FREE (and counted): the projection's
    budgets are priced in the crown-lifted z' frame while this pass runs
    in EMITTED space, so a crowned node is not ours to move (memory
    ``crown-zprime-vs-emitted-space``).  The membrane carries no crown
    declaration, so in practice this excludes nothing and is a guard.
    """
    from .elevation_per_surface.solver_primitives import (
        _open_ring, _runway_node_set)
    cps = layout.canonical_points
    airside = set(_node_shapes(layout, bucket_to_idx, n_nodes))
    tier1 = {int(i) for i in _runway_node_set(layout, bucket_to_idx)
             if 0 <= int(i) < n_nodes}
    tier2 = set(taxiway_family_nodes(layout, bucket_to_idx, n_nodes))
    # The round-3 apron spine STATIONS are centerline-valued (round-3
    # Amendment 2: a station's value is its axis profile's own), so they
    # are tier 2 even though they live inside an apron.
    for entry in (getattr(layout, "apron_spine_presolve", None) or ()):
        for (x, y) in (entry.get("points") or ()):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None and 0 <= i < n_nodes:
                tier2.add(int(i))
    tier3: set = set()
    from .layout import ROLE_BUILDING
    for s in (getattr(layout, "shapes", None) or ()):
        if (getattr(s, "role", None) or "") != ROLE_BUILDING:
            continue
        poly = getattr(s, "polygon", None)
        if poly is None or getattr(poly, "is_empty", True):
            continue
        try:
            ring = _open_ring(list(poly.exterior.coords))
        except _GEOM_EXC:                                 # pragma: no cover
            continue
        for (x, y) in ring:
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None and 0 <= i < n_nodes:
                tier3.add(int(i))
    senior = tier1 | tier2 | tier3
    free = airside - senior
    if crown_of:
        free -= {int(i) for i in crown_of}
    tiers = {"tier1": len(tier1), "tier2": len(tier2), "tier3": len(tier3),
             "airside": len(airside), "free": len(free)}
    return free, senior, tiers


def _resolve_carried_pairs(layout, bucket_to_idx, n_nodes):
    """The published pairs, re-resolved into THIS pass's index space
    through the canonical registry — geometry, never an index."""
    cps = layout.canonical_points
    out = []
    lost = 0
    for (xa, ya, xb, yb, bud, imposed) in (
            getattr(layout, "_airside_no_step_pairs_m", None) or ()):
        ia = bucket_to_idx.get(cps.get_or_add(float(xa), float(ya)))
        ib = bucket_to_idx.get(cps.get_or_add(float(xb), float(yb)))
        if (ia is None or ib is None or ia == ib
                or not (0 <= ia < n_nodes) or not (0 <= ib < n_nodes)):
            lost += 1
            continue
        out.append((int(ia), int(ib), float(bud), bool(imposed)))
    return out, lost


def _membrane_interior_nodes(layout, bucket_to_idx, n_nodes):
    """The airside membrane INTERIOR: the round-2 apron LATTICE points.

    They exist precisely because the apron had no interior vertices
    (spec ``heca-apron-round2`` Amendment 1 §1b), so they ARE the
    interior §1.4 names — and nothing on a shape's exterior ring is."""
    cps = layout.canonical_points
    out: set = set()
    for entry in (getattr(layout, "apron_lattice_presolve", None) or ()):
        for (x, y) in (entry.get("points") or ()):
            i = bucket_to_idx.get(cps.get_or_add(float(x), float(y)))
            if i is not None and 0 <= i < n_nodes:
                out.add(int(i))
    return out


def _resolve_published_ll_pairs(layout, bucket_to_idx, n_nodes, records):
    """``[(i, j, budget), ...]`` for a sidecar-published law-edge list
    (``{a: [lat, lon], b: [...], budget_m}``), re-resolved into THIS
    pass's index space through the canonical registry.

    The APRON LATTICE and the round-3 SPINE STATIONS publish their law
    this way and their entries are minted inside ``solve_route_profile``
    — ``final_grade_projection`` rebuilds ``shape_constraints`` from the
    layout and therefore does NOT carry them.  Pass 2 must, because
    Amendment 2 names them: "the tier-4 nodes' own existing laws
    (within-shape, lattice, station edges)".  Measured on the arm that
    omitted them: SPJC ``apron_lattice_membrane`` 25 -> 84 airside rows,
    the membrane conforming at the cost of a budget nothing re-imposed.
    """
    cps = layout.canonical_points
    out = []
    for rec in (records or ()):
        try:
            a_ll, b_ll = rec["a"], rec["b"]
            bud = float(rec["budget_m"])
        except (KeyError, TypeError, ValueError):         # pragma: no cover
            continue
        try:
            xa, ya = layout.ll_to_m(float(a_ll[0]), float(a_ll[1]))
            xb, yb = layout.ll_to_m(float(b_ll[0]), float(b_ll[1]))
        except Exception:                                 # pragma: no cover
            return []
        ia = bucket_to_idx.get(cps.get_or_add(float(xa), float(ya)))
        ib = bucket_to_idx.get(cps.get_or_add(float(xb), float(yb)))
        if (ia is None or ib is None or ia == ib
                or not (0 <= ia < n_nodes) or not (0 <= ib < n_nodes)):
            continue
        out.append((int(ia), int(ib), bud))
    return out


def _own_law_band(elev, adjacency, nodes, n_nodes):
    """``[(lo, hi) | None] * n`` — the interval each node's OWN law
    edges admit from its neighbours' CURRENT (pass-1) values.

    This is the engine's own neighbour cap slab, the one
    ``one_profile_solve``'s sweep computes per node; it is written here
    as a BAND so ``scaffold_seed`` can clamp into it with no second
    notion of what the law permits."""
    inf = float("inf")
    band = [None] * n_nodes
    for i in nodes:
        lo, hi = -inf, inf
        for (j, lim) in adjacency.get(i, ()):
            if not (0 <= j < n_nodes) or lim is None:
                continue
            try:
                zj = float(elev[j])
                b = float(lim)
            except (TypeError, ValueError):               # pragma: no cover
                continue
            if b < 0:                                     # pragma: no cover
                continue
            if zj - b > lo:
                lo = zj - b
            if zj + b < hi:
                hi = zj + b
        if lo <= hi and (lo > -inf or hi < inf):
            band[i] = (lo if lo > -inf else float(elev[i]),
                       hi if hi < inf else float(elev[i]))
    return band


def membrane_conform(layout, bucket_to_idx, elev, n_nodes, *,
                     shape_constraints, icao="", crown_of=None):
    """PASS 2.  Mutates ``elev`` in place over the tier-4 membrane only;
    returns a report dict.  Nothing is printed here.

    Flag OFF, or no published pair, or no free membrane node ⇒ every
    branch is vacuous and ``elev`` is untouched — byte-inert.
    """
    from . import config as _cfg
    from .elevation_per_surface.route_profile.one_solve import (
        feasibility_project, _build_adjacency)
    from .elevation_per_surface.route_profile import scaffold_seed as _sc
    from .solve_stage import STAGE_A, STAGE_KEY
    report = {"free": 0, "constants": 0, "pairs": 0, "lost_pairs": 0,
              "own_law_edges": 0, "reseeded": 0, "reseed_worst_m": 0.0,
              "moved": 0, "worst_move_m": 0.0, "over_cap_left": 0,
              "both_hard_left": 0, "tiers": {}, "crown_skipped": 0,
              "interval_skipped": 0, "interior": 0,
              "own_law_over_cap_left": 0,
              "membrane_published_edges": 0}
    if not getattr(_cfg, "AIRSIDE_NO_STEP", False):
        return report
    carried, lost = _resolve_carried_pairs(layout, bucket_to_idx, n_nodes)
    report["lost_pairs"] = lost
    if not carried:
        return report
    free, senior, tiers = membrane_free_nodes(
        layout, bucket_to_idx, n_nodes, crown_of=crown_of)
    report["tiers"] = tiers
    report["free"] = len(free)
    report["constants"] = n_nodes - len(free)
    if not free:
        return report
    # ── THE PASS-2 EDGE SET ──────────────────────────────────────────
    # (a) the IMPOSED no-step pairs that touch the membrane.  A tier2 <->
    #     tier2 pair is report-first (Amendment 1) and never enters here;
    #     a senior <-> free pair is one-sided BY CONSTRUCTION because the
    #     senior end is not in ``free`` and therefore is hard below.
    ns_edges = [(a, b, bud) for (a, b, bud, imp) in carried
                if imp and (a in free or b in free)]
    report["pairs"] = len(ns_edges)
    # (b) the tier-4 nodes' OWN EXISTING LAWS — every edge of this pass's
    #     constraint set with a free endpoint (within-shape, lattice,
    #     station, band…).  Carried VERBATIM, budgets included: pass 2
    #     may not relax a law pass 1 built to.
    #     A CROWNED endpoint is dropped with its edge: this pass runs in
    #     EMITTED space and those budgets were priced in the crown-lifted
    #     z' frame, so comparing them here would be a frame error
    #     (memory ``crown-zprime-vs-emitted-space``).  The membrane
    #     carries no crown, so in practice this drops nothing.
    crowned = {int(i) for i in (crown_of or ())}
    own: list = []
    for entry in (shape_constraints or ()):
        for e in (entry.get("edges") or ()):
            try:
                a, b = int(e[0]), int(e[1])
            except (TypeError, ValueError):               # pragma: no cover
                continue
            if a in crowned or b in crowned:
                report["crown_skipped"] += 1
                continue
            if len(e) != 3:
                # A SIGNED INTERVAL edge (the B0 4-tuple) is not this
                # pass's to re-impose: its floor/ceiling are the host
                # law's, stated against a node this pass holds constant.
                report["interval_skipped"] += 1
                continue
            if a in free or b in free:
                own.append(tuple(e))
    # …and the LATTICE / STATION law, which ``final_grade_projection``'s
    # rebuilt constraint set does not carry (their entries are minted
    # inside the solve).  Resolved from their own sidecar publication —
    # the same list the census prices — so pass 2 re-imposes exactly the
    # budget the solve built to.
    lat_edges = _resolve_published_ll_pairs(
        layout, bucket_to_idx, n_nodes,
        getattr(layout, "_apron_lattice_edges_ll", None))
    lat_edges = [(a, b, bud) for (a, b, bud) in lat_edges
                 if a in free or b in free]
    report["membrane_published_edges"] = len(lat_edges)
    own = own + lat_edges
    report["own_law_edges"] = len(own)
    if not ns_edges and not own:
        return report
    entries = []
    if ns_edges:
        entries.append({"nodes": sorted({a for (a, _b, _c) in ns_edges}
                                        | {b for (_a, b, _c) in ns_edges}),
                        "edges": ns_edges, "flat": False, "flat_pairs": (),
                        "area": 0.0, "role": "apron",
                        STAGE_KEY: STAGE_A, "ref": PROVENANCE})
    if own:
        entries.append({"nodes": sorted({int(e[0]) for e in own}
                                        | {int(e[1]) for e in own}),
                        "edges": own, "flat": False, "flat_pairs": (),
                        "area": 0.0, "role": "apron",
                        STAGE_KEY: STAGE_A, "ref": "membrane_own_law"})
    before = {i: float(elev[i]) for i in free}
    # ── §1.4 DEM DEMOTION, APPLIED HERE (Amendment 2 puts it in pass 2,
    # so pass 1 stays byte-identical) ─────────────────────────────────
    # The membrane is re-seeded on the TAUT SCAFFOLD of the constants —
    # the Chebyshev centre of the cap-Lipschitz envelope the law edges
    # admit from them — instead of keeping the DEM-warm-started value
    # pass 1 left.  ONE implementation, ``scaffold_seed``: the 24c
    # re-seed and this one are the same statement about the same surface.
    adjacency = _build_adjacency(entries, n_nodes)
    anchors = {i: float(elev[i]) for i in senior
               if 0 <= i < n_nodes and i in adjacency}
    # SCOPE IS §1.4's OWN WORDS — "airside membrane INTERIOR free nodes".
    # The apron RING vertices in ``free`` are not interior: they are the
    # shape's own boundary, shaped by the ring law and by the transverse
    # (cross-corridor) law, and re-seeding them replaces a settled
    # boundary with an interpolation no pair budget can restore.
    # MEASURED (this lane's first A2 cut, which re-seeded all of
    # ``free``): CYXY airside 88 -> 186 with `transverse` alone 4 -> 67,
    # against 88 -> 117 when only the interior moves.  The interior is
    # the round-2 LATTICE — the nodes that exist precisely because the
    # apron had no interior vertices — so that is the population.
    interior = free & _membrane_interior_nodes(layout, bucket_to_idx,
                                               n_nodes)
    report["interior"] = len(interior)
    if anchors and interior and getattr(_cfg, 'AIRSIDE_NO_STEP_RESEED',
                                        False):
        # …AND "SUBJECT TO LAW" IS §1.4's OWN SENTENCE.  The taut level
        # is CLAMPED into the interval this node's own law edges already
        # admit from its settled neighbours — the newest authority in the
        # build yields to every older one (creation-order seniority,
        # RULINGS 2026-08-21e), so the re-seed can never hand the repair
        # below a surface it has to undo.  MEASURED on the unclamped arm:
        # SPJC re-seeded 170 interior nodes by up to 3.97 m and the arm
        # came back at airside 1,920 with ``within_shape`` 309 and 594
        # edges still over cap after the repair, against 1,359 / 9 / 24
        # when the re-seed could not reach.
        band = _own_law_band(elev, adjacency, interior, n_nodes)
        rep = _sc.scaffold_seed_apron_interior(
            elev, adjacency=adjacency, anchor_values=anchors,
            interior_nodes=interior, node_band=band)
        report["reseeded"] = int(rep.get("seeded", 0))
        report["reseed_worst_m"] = float(rep.get("worst_move_m", 0.0))
    hard = {i for i in range(n_nodes) if i not in free}
    rem, both = feasibility_project(elev, entries, hard)
    report["over_cap_left"] = int(rem or 0)
    report["both_hard_left"] = int(both or 0)
    # ── CREATION-ORDER SENIORITY, ENFORCED (owner ruling RULINGS
    # 2026-08-21e: "anything created later defers to what exists before
    # it") ─────────────────────────────────────────────────────────────
    # Where the two laws CONFLICT — a membrane the no-step edges pull
    # toward constants its own ring cap cannot reach — the projection
    # above has no priority and splits the excess, breaking the OLDER
    # law.  Measured on the arm without this repair: SPJC apron
    # ``within_shape`` 8 -> 1,537 airside rows, 1,531 of them NEW
    # ``apron|apron``, beside 1,869 no-step edges still over cap — i.e.
    # it broke the pre-existing law AND did not satisfy the new one.
    # So the membrane is re-projected against its OWN LAWS ALONE,
    # starting from the conformed surface: the conform survives wherever
    # it is compatible, and the older law is restored wherever it is
    # not.  A no-step pair left over cap after this is the honest
    # report-first residual the census prices — never a licence to break
    # a law that predates it.
    if own and ns_edges:
        own_only = [e for e in entries if e.get("ref") != PROVENANCE]
        rem2, both2 = feasibility_project(elev, own_only, hard)
        report["own_law_over_cap_left"] = int(rem2 or 0)
    for i, v0 in before.items():
        d = abs(float(elev[i]) - v0)
        if d > 0.01:
            report["moved"] += 1
        if d > report["worst_move_m"]:
            report["worst_move_m"] = d
    return report


def format_conform_report(icao: str, r: dict) -> str:
    t = r.get("tiers") or {}
    return (f"  [membrane-conform] {icao}: PASS 2 over {r['free']} tier-4 "
            f"membrane node(s) ({r['constants']} constant, of "
            f"{t.get('airside', 0)} airside: tier1 {t.get('tier1', 0)} / "
            f"tier2 {t.get('tier2', 0)} / tier3 {t.get('tier3', 0)}); "
            f"{r['pairs']} imposed no-step pair(s) + {r['own_law_edges']} "
            f"of the membrane's OWN law edge(s) "
            f"({r.get('membrane_published_edges', 0)} of them the published "
            f"lattice/station law); {r['reseeded']} node(s) "
            f"re-seeded on the taut scaffold (worst "
            f"{r['reseed_worst_m']:.2f} m over the {r.get('interior', 0)} "
            f"INTERIOR of them, spec §1.4); {r['moved']} node(s) "
            f"moved > 1 cm, worst {r['worst_move_m']:.2f} m; "
            f"{r['over_cap_left']} edge(s) left over cap after the "
            f"conform, {r.get('own_law_over_cap_left', 0)} after the "
            f"creation-order repair (2026-08-21e); every non-tier-4 value is "
            f"pass 1's, untouched (spec Amendment 2)")
