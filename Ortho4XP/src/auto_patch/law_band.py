"""THE UNIFIED LAW BAND — the reach band is the projection of the FULL law
graph (spec ``docs/specs/unified-law-band-spec.md``, owner ruling RULINGS
2026-08-27 "REFINE THE REACH BAND FIRST").

OWNER'S WORDS: *"The calculation has to be done at some point, seems as
good or better to refine and narrow the reach bands first, then we
shouldn't need nearly as much convergence later.  Consider how we can
build the fully constrained graph as efficiently as possible."*

WHAT THIS MODULE IS.  A STORE and a RESOLVER, nothing else.  The three law
populations the band could not see —

  * ``frontage_chord``  the pad frontage chords (the 2026-08-25
    chord-anchor law's own population and caps, tagged AT MINT inside
    ``grade_graph.shape_constraints`` from the very ``PairContext``
    ``classify_pair`` judged — never a second predicate here);
  * ``membrane``        the apron membrane law edges (round-2 lattice,
    round-3 spine stations, ring within-shape), from
    ``apron_lattice`` / ``apron_spine_stations``' own builders;
  * ``no_step``         the airside no-step direct-distance enumeration,
    the SAME list the sidecar publishes and the census prices;

— are published here ONCE, by the solve, in the solve's own node space,
and resolved back into whatever node space a later ``UnifiedGraph`` is
built in.  ``building_feasibility.spine_value_fields`` merges the result
into its edge iterator: one engine, one band (spec §1.5b — the
``trace_reach_route`` history is the cautionary tale of the second one).

NON-NEGATIVITY IS A PINNED INVARIANT (spec §1.2).  On 2026-08-13 a SIGNED
slab budget turned the envelope Dijkstra into a negative-cycle search and
took 26-56 GB before SIGKILL.  Every budget entering this store is
asserted ``>= 0`` at graph-BUILD time — before any heap exists — and a
negative one raises :class:`LawBandNegativeBudget` naming the pair.  It is
never clamped: a negative budget is a law defect upstream, and silently
flooring it at zero would hide it.

INDEX SPACES.  Edges travel as GEOMETRY (local metres), never as indices:
``final_grade_projection`` rebuilds the node list and an index-keyed store
does not survive that (the rod-key lesson, and the same rule
``airside_no_step._resolve_carried_pairs`` already follows).  Resolution
into a graph's own space goes through that graph's ``pos`` map first
(exact tuple identity — both sides come from the same shape rings) and
falls back to the CANONICAL REGISTRY's read-only query
(``canonical_points.get``; ``get_or_add`` would intern and move the
emitted surface).  Misses are COUNTED and reported, never silent.
"""
from __future__ import annotations

import heapq

__all__ = [
    "LAW_EDGE_CLASSES", "LawBandNegativeBudget", "LawBandRefusal",
    "publish_law_band_edges", "law_adjacency_for", "law_band_report",
    "IncrementalAnchorField", "MergedAdjacency", "full_anchor_field",
    "refuse_on_inverted_band", "format_law_band_report",
]

#: The three populations spec §1.1 names, in report order.  A class name
#: is spelled ONCE, here: the store, the log line and the refusal message
#: all read this tuple.
LAW_EDGE_CLASSES = ("frontage_chord", "membrane", "no_step")

#: Where the published store lives on the layout.  Geometry + budget +
#: class, never an index.
_STORE = "_law_band_edges_m"
_REPORT = "_law_band_report"
#: Memo of the resolved adjacency, stashed on the GRAPH (one resolution
#: per graph, however many value fields it feeds).
_ADJ_MEMO = "_law_band_adj"


class LawBandNegativeBudget(ValueError):
    """A law edge arrived with a NEGATIVE budget (spec §1.2).

    Deliberately raised at GRAPH-BUILD time, before the heap exists: the
    2026-08-13 blowup is what a signed budget does once it reaches a
    Dijkstra, and the cheap place to stop it is here.
    """


class LawBandRefusal(RuntimeError):
    """The narrowed band admits NO elevation at some node (spec §1.4).

    An EMPTY or INVERTED interval is not a band to be clamped into — it
    is the statement that two laws contradict each other at a site, which
    under ``feasibility-is-guaranteed`` is a defect in the DATA or the LAW
    and never a property of the ground.  Raised BEFORE any patch is
    written, naming the node's lat/lon, both binding anchors and both
    binding chains, so the owner adjudicates a named site instead of
    reading a silent bad seat off the surface (the building146 class).

    Not a ``ValueError`` and not a shapely error, for the same reason
    ``BandInversionError`` is neither: the pipeline's geometry guards
    swallow those to keep a build alive, and this one must never be
    swallowed.
    """


# ══════════════════════════════════════════════════════════════════════
# PUBLICATION — build once, filter per consumer (spec §1.5c)
# ══════════════════════════════════════════════════════════════════════

def publish_law_band_edges(layout, *, node_pos, classes) -> dict:
    """Publish the law-edge supplement for THIS build.  Returns a report.

    ``node_pos`` — the solve's own ``{idx: (x, y)}`` (``G.pos``); no
    second coordinate frame is built here.
    ``classes`` — ``{class_name: [(i, j, budget), ...]}`` in that node
    space, each list coming from its OWN existing builder.

    Every budget is asserted ``>= 0`` (spec §1.2) before anything is
    stored.  A self-loop, an unpositioned endpoint or a duplicate pair is
    dropped and counted; the FIRST (tightest by construction of the
    caller's ordering, but we take the MINIMUM explicitly so the store
    cannot depend on iteration order) budget wins for a pair stated
    twice — two copies of one law is what the round-3 station build drops
    restated pairs to avoid.
    """
    report = {"by_class": {}, "edges": 0, "dropped_no_pos": 0,
              "dropped_self": 0, "duplicate_pairs": 0, "nodes": 0,
              "enabled": True}
    best: dict = {}
    klass_of: dict = {}
    for klass in LAW_EDGE_CLASSES:
        kept = 0
        for e in (classes.get(klass) or ()):
            try:
                i, j, budget = int(e[0]), int(e[1]), float(e[2])
            except (TypeError, ValueError, IndexError):    # pragma: no cover
                continue
            if not (budget >= 0.0):
                # NEGATIVE (or NaN) — the pinned invariant.  Named, never
                # clamped: see the module docstring.
                pa, pb = node_pos.get(i), node_pos.get(j)
                raise LawBandNegativeBudget(
                    f"law-band edge {i}<->{j} ({klass}) carries budget "
                    f"{budget!r} — every law budget is cap x distance and "
                    f"must be >= 0 (spec unified-law-band §1.2; the "
                    f"2026-08-13 signed-slab Dijkstra blowup is this "
                    f"failure class).  Endpoints at {pa} / {pb}.")
            if i == j:
                report["dropped_self"] += 1
                continue
            pa, pb = node_pos.get(i), node_pos.get(j)
            if pa is None or pb is None:
                report["dropped_no_pos"] += 1
                continue
            key = (i, j) if i < j else (j, i)
            prev = best.get(key)
            if prev is None:
                best[key] = budget
                klass_of[key] = klass
                kept += 1
            else:
                report["duplicate_pairs"] += 1
                if budget < prev:
                    best[key] = budget
                    klass_of[key] = klass
        report["by_class"][klass] = kept
    # THE STORED COORDINATE IS THE CANONICAL ONE where the registry knows
    # the point (``canonical_points.get`` — READ-ONLY; ``get_or_add``
    # interns and would move the emitted surface).  That is the key
    # ``bucket_to_idx`` is spelled in, so a graph carrying its node space
    # resolves EVERY endpoint, including the apron lattice points and the
    # round-3 spine stations, which are interior constructs and appear in
    # no shape ring (and therefore in no ``G.pos``).  Where the registry
    # has no entry the raw position is stored and the position join
    # answers instead.
    cps = getattr(layout, "canonical_points", None)

    def _canon(p):
        if cps is not None:
            try:
                k = cps.get(float(p[0]), float(p[1]))
            except Exception:                              # pragma: no cover
                k = None
            if k is not None:
                return (float(k[0]), float(k[1]))
        return (float(p[0]), float(p[1]))

    edges = []
    touched: set = set()
    for (i, j) in sorted(best):
        (xa, ya) = _canon(node_pos[i])
        (xb, yb) = _canon(node_pos[j])
        edges.append((xa, ya, xb, yb, float(best[(i, j)]),
                      klass_of[(i, j)]))
        touched.add(i)
        touched.add(j)
    report["edges"] = len(edges)
    report["nodes"] = len(touched)
    try:
        setattr(layout, _STORE, edges)
        setattr(layout, _REPORT, report)
    except AttributeError:                                 # pragma: no cover
        pass
    return report


def law_band_report(layout) -> dict:
    return dict(getattr(layout, _REPORT, None) or {})


def format_law_band_report(icao: str, report: dict, *,
                           resolved: dict | None = None) -> str:
    """The build log's one line for the law band."""
    if not report or not report.get("enabled", False):
        return (f"  [law-band] {icao}: OFF (O4_BAND_FULL_LAW_GRAPH=0) — "
                f"the band is the route metric alone, exactly as before "
                f"the 2026-08-27 ruling")
    by = report.get("by_class") or {}
    parts = ", ".join(f"{k} {by.get(k, 0)}" for k in LAW_EDGE_CLASSES)
    tail = ""
    if resolved:
        tail = (f"; resolved into the band's node space: "
                f"{resolved.get('edges', 0)} edge(s) over "
                f"{resolved.get('nodes', 0)} node(s), "
                f"{resolved.get('unresolved', 0)} edge(s) with an endpoint "
                f"not in this graph, {resolved.get('by_pos', 0)} joined by "
                f"position and {resolved.get('by_registry', 0)} by the node "
                f"space ({resolved.get('off_pos_nodes', 0)} of them at "
                f"INTERIOR nodes the graph positions no ring for — the "
                f"lattice and the spine stations)")
    return (f"  [law-band] {icao}: {report.get('edges', 0)} law edge(s) "
            f"over {report.get('nodes', 0)} node(s) ({parts}; "
            f"{report.get('duplicate_pairs', 0)} restated pair(s) collapsed "
            f"to one law, {report.get('dropped_no_pos', 0)} without a "
            f"position) join the "
            f"route-spine metric — the band is now the projection of the "
            f"FULL law graph (RULINGS 2026-08-27)"
            f"{tail}")


# ══════════════════════════════════════════════════════════════════════
# RESOLUTION — into whatever node space a graph was built in
# ══════════════════════════════════════════════════════════════════════

def _key_index(layout, G):
    """``(pos_index, registry_index)`` for this graph's node space.

    ``pos_index`` — exact ``(x, y) -> idx``.  Both the store's coordinates
    and ``G.pos`` come from the same shape rings, so in the common case
    (and in every rebuilt-node-space case where the rings are unchanged)
    this resolves everything with one dict build.

    ``registry_index`` — ``canonical key -> idx``, built LAZILY and only
    when the exact map misses, because it costs one read-only registry
    query per node.  ``canonical_points.get``, never ``get_or_add``: an
    interning read moves which LATER points intern together, and this is
    a measurement (the probe rule).
    """
    pos = getattr(G, "pos", None) or {}
    pos_index = {}
    for i, xy in pos.items():
        try:
            pos_index[(float(xy[0]), float(xy[1]))] = int(i)
        except (TypeError, ValueError, IndexError):        # pragma: no cover
            continue
    return pos_index, None


def _registry_index(layout, G):
    cps = getattr(layout, "canonical_points", None)
    if cps is None:
        return {}
    out = {}
    for i, xy in (getattr(G, "pos", None) or {}).items():
        try:
            k = cps.get(float(xy[0]), float(xy[1]))
        except Exception:                                  # pragma: no cover
            k = None
        if k is not None and k not in out:
            out[k] = int(i)
    return out


def law_adjacency_for(layout, G) -> dict:
    """``{idx: [(idx, budget), ...]}`` — the published law edges resolved
    into ``G``'s own node space.  ``{}`` when the flag is off, nothing is
    published, or the graph has no positions.

    Memoised on the GRAPH object: one resolution per graph however many
    value fields it feeds (``spine_value_fields`` runs two Dijkstras over
    it, and several consumers call it per build).
    """
    memo = getattr(G, _ADJ_MEMO, None)
    if memo is not None:
        return memo[0]
    try:
        from auto_patch.config import BAND_FULL_LAW_GRAPH
    except Exception:                                      # pragma: no cover
        BAND_FULL_LAW_GRAPH = True
    stats = {"edges": 0, "nodes": 0, "unresolved": 0, "by_pos": 0,
             "by_registry": 0, "off_pos_nodes": 0}
    adj: dict = {}
    store = getattr(layout, _STORE, None) or ()
    if not BAND_FULL_LAW_GRAPH or not store or not getattr(G, "pos", None):
        try:
            setattr(G, _ADJ_MEMO, (adj, stats))
        except AttributeError:                             # pragma: no cover
            pass
        return adj
    pos_index, _ = _key_index(layout, G)
    # THE NODE SPACE, when the graph carries it (``build_unified_graph``
    # stashes it).  This is the map that resolves the endpoints ``G.pos``
    # cannot: an apron LATTICE point and a round-3 spine STATION are
    # interior constructs belonging to no shape ring, so the assembly
    # never gives them a position — and the apron MEMBRANE law is exactly
    # the population whose edges touch them (measured at CYXY on the
    # first arm: ``membrane 0`` published, every one of them dropped for
    # want of a position).  The registry map is the last resort.
    b2i = getattr(G, "bucket_to_idx", None)
    _graph_pos = getattr(G, "pos", None) or {}
    reg_index = None

    def _resolve(x, y):
        nonlocal reg_index
        key = (x, y)
        if b2i is not None:
            i = b2i.get(key)
            if i is not None:
                stats["by_registry"] += 1
                # HONEST COUNTER: an endpoint the GRAPH gives no position
                # for — a lattice point or a spine station, i.e. exactly
                # the class that made the first arm publish "membrane 0".
                # (Not "the canonical key differs from the ring
                # coordinate", which is common, harmless and says nothing.)
                if int(i) not in _graph_pos:
                    stats["off_pos_nodes"] += 1
                return int(i)
        i = pos_index.get(key)
        if i is not None:
            stats["by_pos"] += 1
            return i
        if reg_index is None:
            reg_index = _registry_index(layout, G)
        cps = getattr(layout, "canonical_points", None)
        if cps is None:
            return None
        try:
            k = cps.get(float(x), float(y))
        except Exception:                                  # pragma: no cover
            return None
        if k is None:
            return None
        i = reg_index.get(k)
        if i is not None:
            stats["by_registry"] += 1
        return i

    for (xa, ya, xb, yb, budget, _klass) in store:
        ia = _resolve(xa, ya)
        ib = _resolve(xb, yb)
        if ia is None or ib is None or ia == ib:
            stats["unresolved"] += 1
            continue
        if not (budget >= 0.0):                            # pragma: no cover
            raise LawBandNegativeBudget(
                f"law-band edge {ia}<->{ib} resolved with budget "
                f"{budget!r} (spec unified-law-band §1.2)")
        adj.setdefault(ia, []).append((ib, float(budget)))
        adj.setdefault(ib, []).append((ia, float(budget)))
        stats["edges"] += 1
    stats["nodes"] = len(adj)
    try:
        setattr(G, _ADJ_MEMO, (adj, stats))
    except AttributeError:                                 # pragma: no cover
        pass
    return adj


def law_adjacency_stats(G) -> dict:
    memo = getattr(G, _ADJ_MEMO, None)
    return dict(memo[1]) if memo else {}


# ══════════════════════════════════════════════════════════════════════
# §1.5(d) — SEATS INCREMENT, NEVER RECOMPUTE
# ══════════════════════════════════════════════════════════════════════

class MergedAdjacency:
    """``spine_adj`` and the law adjacency read as ONE neighbour map.

    A view, not a copy: merging 140k adjacency lists to add a second
    source would cost the band a full graph duplication for nothing.
    ``get(u, default)`` is the whole contract — the same one a plain dict
    offers the Dijkstras.
    """

    __slots__ = ("_a", "_b")

    def __init__(self, spine_adj, law_adj):
        self._a = spine_adj or {}
        self._b = law_adj or {}

    def get(self, u, default=()):
        a = self._a.get(u)
        b = self._b.get(u)
        if a and b:
            return list(a) + list(b)
        return a or b or default

    def __contains__(self, u):
        return u in self._a or u in self._b

    def __bool__(self):
        return bool(self._a) or bool(self._b)


class IncrementalAnchorField:
    """The two value fields of the law band, with an INCREMENTAL source.

    ``ceiling[i] = min over anchors a ( v_a + d_law(a, i) )`` and the
    floor mirrors with ``-``, over the merged edge iterator (route-spine
    edges + the law edges).  ``add_anchor(node, value)`` re-relaxes ONLY
    the improvement region: a bounded Dijkstra seeded at the new source
    that stops expanding the moment a node's bound is not tightened, which
    is exactly the region where the new anchor could matter.

    THE CORRECTNESS ARGUMENT (and the twin that pins it, spec §2).  The
    fields are a min over anchors of ``v_a + d(a, i)``.  Adding an anchor
    adds one more term to that min, so the new field is
    ``min(old_field, v_s + d(s, .))``.  ``v_s + d(s, .)`` is itself a
    single-source shortest-path field, and Dijkstra computes it correctly
    while pruning any branch whose tentative value already fails to beat
    the incumbent — because edge budgets are ``>= 0`` (spec §1.2), a
    branch that cannot improve at ``u`` cannot improve anything beyond
    ``u`` either.  The twin asserts the incremental result equals a full
    recompute with the anchor in the seed set, dict for dict.
    """

    __slots__ = ("adj", "ceiling", "floor", "anchor_values",
                 "ceil_via", "floor_via", "updates", "relaxations")

    def __init__(self, adj, ceiling, floor, anchor_values,
                 ceil_via=None, floor_via=None):
        self.adj = adj
        self.ceiling = ceiling
        self.floor = floor
        self.anchor_values = dict(anchor_values or {})
        self.ceil_via = dict(ceil_via or {})
        self.floor_via = dict(floor_via or {})
        self.updates = 0
        self.relaxations = 0

    def _relax(self, field, via, sources, sign):
        """ONE bounded MULTI-SOURCE Dijkstra over ``sources``
        (``{node: value}``).  Returns ``{idx: new_value}`` for every node
        whose bound TIGHTENED.

        MULTI-SOURCE, and that is the efficiency contract, not a
        convenience.  Placing seats one at a time is one pruned walk per
        seat; the ceiling is a MIN over sources, so seeding every new
        source into one heap keyed by ``value ± dist`` gives the same
        answer in one walk — the identical commutation
        ``spine_value_fields`` uses for the anchors themselves.  Measured
        on the arm without it: a HECA build passed 20 minutes inside the
        seat loop and was killed.

        The pruning is the ``>= 0`` budget invariant (§1.2): where a
        node's incumbent bound already beats this frontier, nothing
        beyond that node can be tightened through it either, so the
        branch stops.  That is why the twin can assert
        incremental == full recompute.
        """
        changed: dict = {}
        pq = []
        for node, value in sources.items():
            node = int(node)
            value = float(value)
            cur = field.get(node)
            if cur is not None and ((sign > 0 and cur <= value)
                                    or (sign < 0 and cur >= value)):
                # The incumbent already binds at the source itself — the
                # cheapest form of the early exit §1.5(d) names.
                continue
            pq.append((value if sign > 0 else -value, 0.0, value, node,
                       node))
        if not pq:
            return changed
        heapq.heapify(pq)
        best_d: dict = {}
        while pq:
            _key, d, seed, src, u = heapq.heappop(pq)
            prev = best_d.get(u)
            if prev is not None and d >= prev:
                continue
            cand = (seed + d) if sign > 0 else (seed - d)
            cur = field.get(u)
            if cur is not None and ((sign > 0 and cand >= cur)
                                    or (sign < 0 and cand <= cur)):
                # No tightening HERE, and with ``budget >= 0`` none
                # anywhere beyond here through this node either.
                continue
            best_d[u] = d
            field[u] = cand
            via[u] = int(src)
            changed[u] = cand
            self.relaxations += 1
            for (v, budget) in self.adj.get(u, ()):
                nd = d + float(budget)
                heapq.heappush(
                    pq, (((seed + nd) if sign > 0 else -(seed - nd)),
                         nd, seed, src, v))
        return changed

    def add_anchors(self, anchor_values) -> dict:
        """Join every ``{node: value}`` to the anchor set at once.

        ONE pruned walk per bound direction for the whole batch — see
        :meth:`_relax`.  Returns
        ``{"ceiling": {...}, "floor": {...}}``, the nodes whose bounds
        moved, which is what a raster consumer refreshes."""
        src = {int(k): float(v) for k, v in (anchor_values or {}).items()}
        if not src:
            return {"ceiling": {}, "floor": {}}
        self.anchor_values.update(src)
        self.updates += len(src)
        return {"ceiling": self._relax(self.ceiling, self.ceil_via,
                                       src, +1),
                "floor": self._relax(self.floor, self.floor_via,
                                     src, -1)}

    def add_anchor(self, node, value) -> dict:
        """Join ``node`` to the anchor set at ``value`` and re-relax the
        improvement region.  Returns
        ``{"ceiling": {...}, "floor": {...}}`` — the nodes whose bounds
        moved, which is what a raster consumer refreshes.

        CONTRACT: this ADDS a source to the min/max; it does not REVALUE
        an existing one.  Revaluing is not an increment at all — it can
        LOOSEN a bound, and no pruned walk can discover a loosening.
        Seats are new sources by construction (a pad's contact node is
        not a runway anchor), so the contract is the one the solve needs;
        ``tests/test_law_band.py`` states it rather than assuming it.
        """
        return self.add_anchors({int(node): float(value)})


def full_anchor_field(adj, anchor_values):
    """The NON-incremental reference the twin compares against: the same
    two multi-source Dijkstras ``spine_value_fields`` runs, over ``adj``.

    Deliberately a plain function on a plain adjacency — the twin must be
    able to state "incremental == full recompute" without a layout, a
    graph or a build.
    """
    def _field(sign):
        best: dict = {}
        via: dict = {}
        pq = [((v if sign > 0 else -v), 0.0, v, k, k)
              for (k, v) in anchor_values.items()]
        heapq.heapify(pq)
        while pq:
            _key, dd, ae, src, u = heapq.heappop(pq)
            if u in best:
                continue
            best[u] = (ae + dd) if sign > 0 else (ae - dd)
            via[u] = src
            for (v, budget) in adj.get(u, ()):
                if v in best:
                    continue
                nd = dd + float(budget)
                heapq.heappush(pq, (((ae + nd) if sign > 0 else -(ae - nd)),
                                    nd, ae, src, v))
        return best, via
    ceiling, ceil_via = _field(+1)
    floor, floor_via = _field(-1)
    return IncrementalAnchorField(adj, ceiling, floor, anchor_values,
                                  ceil_via, floor_via)


# ══════════════════════════════════════════════════════════════════════
# §1.4 — EMPTY OR INVERTED INTERVAL IS A LOUD PRE-SOLVE REFUSAL
# ══════════════════════════════════════════════════════════════════════

def _chain_of(parents, node, anchor, limit=12):
    """The binding CHAIN as a node list, source-first, truncated."""
    if parents is None:
        return None
    out = [int(node)]
    seen = {int(node)}
    u = int(node)
    for _ in range(4096):
        p = parents.get(u)
        if p is None or int(p) in seen:
            break
        u = int(p)
        seen.add(u)
        out.append(u)
        if anchor is not None and u == int(anchor):
            break
    out.reverse()
    if len(out) > limit:
        out = out[:limit // 2] + ["..."] + out[-(limit // 2):]
    return out


def refuse_on_inverted_band(layout, icao="", tol=None):
    """SPEC §1.4 — raise :class:`LawBandRefusal` when the narrowed band
    admits no elevation at some node.  Returns the number of
    sub-materiality crossings tolerated (PASS-with-residual).

    Reads the rows ``building_feasibility._record_band_inversions`` has
    just stashed for THIS band build — one instrument, not a second scan.
    Every named row carries the node's lat/lon, both binding anchors with
    their values, both route budgets and both binding chains.
    """
    from auto_patch.config import (BAND_FULL_LAW_GRAPH, BAND_LAW_REFUSE)
    if not BAND_FULL_LAW_GRAPH:
        return 0
    try:
        from auto_patch.elevation_per_surface.building_feasibility import (
            FINAL_BAND_INVERSION_TOL_M)
    except Exception:                                      # pragma: no cover
        FINAL_BAND_INVERSION_TOL_M = 0.01
    if tol is None:
        tol = FINAL_BAND_INVERSION_TOL_M
    rows = [r for r in (getattr(layout, "_final_band_inversions", None) or ())
            if r.get("klass") == "floor_above_ceiling"]
    material = [r for r in rows if float(r.get("deficit_m", 0.0)) > tol]
    residual = len(rows) - len(material)
    if not material:
        return residual
    parents_c = getattr(layout, "_band_ceil_parent", None)
    parents_f = getattr(layout, "_band_floor_parent", None)
    lines = []
    for r in material[:20]:
        try:
            lat, lon = layout.m_to_ll(float(r["x"]), float(r["y"]))
            where = f"{lat:.7f},{lon:.7f}"
        except Exception:                                  # pragma: no cover
            where = f"local x={r.get('x')} y={r.get('y')}"
        ca, fa = r.get("ceil_anchor"), r.get("floor_anchor")
        lines.append(
            f"    node {r['node']} at {where}: floor {r['floor']:.3f} > "
            f"ceiling {r['ceiling']:.3f} (empty by "
            f"{r['deficit_m']:.3f} m).\n"
            f"      CEILING binds from anchor {ca} at "
            f"{r.get('ceil_anchor_value')} over {r.get('ceil_route_m', 0.0):.2f} m "
            f"of budget; chain {_chain_of(parents_c, r['node'], ca)}\n"
            f"      FLOOR   binds from anchor {fa} at "
            f"{r.get('floor_anchor_value')} over {r.get('floor_route_m', 0.0):.2f} m "
            f"of budget; chain {_chain_of(parents_f, r['node'], fa)}")
    more = ("" if len(material) <= 20
            else f"\n    ... and {len(material) - 20} more")
    msg = (
        f"[law-band] {icao}: the NARROWED reach band admits NO elevation at "
        f"{len(material)} node(s) (spec unified-law-band §1.4).  This is a "
        f"pre-solve REFUSAL, before any patch is written: under "
        f"feasibility-is-guaranteed a real airport with real thresholds HAS "
        f"a lawful surface, so an empty interval is a defect in the DATA or "
        f"the LAW at a NAMED site — the building146 class — and seating "
        f"into it would mint the silent bad seat this ruling exists to "
        f"stop.  The owner adjudicates data vs law.\n" + "\n".join(lines)
        + more +
        f"\n    ({residual} further crossing(s) below the {tol} m "
        f"materiality floor were tolerated.)"
        f"\n    O4_BAND_LAW_REFUSE=0 reports these and continues, which is "
        f"the arm for adjudicating a site before its data is fixed.")
    if not BAND_LAW_REFUSE:
        try:
            import O4_UI_Utils as _UI
            _UI.vprint(1, "  " + msg.replace("\n", "\n  "))
        except Exception:                                  # pragma: no cover
            pass
        return residual
    raise LawBandRefusal(msg)


def band_width_at(band, x, y):
    """``ceiling - floor`` at a point, or ``None`` — the one-liner the
    acceptance tables read so a report never re-derives the band."""
    b = band(x, y) if band is not None else None
    if b is None:
        return None
    return float(b[1]) - float(b[0])
