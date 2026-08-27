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

    A node absent from the result is free-tier.  Precedence is the
    ladder's own: runway profile beats centerline profile beats a seated
    pad — a node that is two of those is the more senior of them.
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
              "skipped_long_apron": 0}
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
        if ta != tb:
            report["cross_tier"] += 1
            senior_idx.add(ia if ta < tb else ib)
        cls = GL.apron_pair_class(pc) if role == apron_role else role
        report["by_class"][cls] = report["by_class"].get(cls, 0) + 1
        by_role.setdefault(role, []).append((ia, ib, budget))
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
            "provenance": PROVENANCE})
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
    return sc_out, senior_idx, edge_records, report


def format_report(icao: str, report: dict) -> str:
    """The build log's one line."""
    return (f"  [airside-no-step] {icao}: {report['edges']} direct-distance "
            f"law edge(s) over {report['airside_nodes']} airside node(s) "
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
