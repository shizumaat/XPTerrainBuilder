"""§16g (6) A CONNECTOR JOINS TWO UNITS (owner RULINGS 2026-09-13cn;
spec ``object-placement-spec.md`` §16g (6); the owner's own words at 13ce:
cutting is allowed only for "very long connecting pieces like the elevated
rail at HECA").

The §16g footprint unit's ONE exception, lifted out of ``footprint_unit``
for the 1,000-line law.  Three rules and their witness:

1. A CONNECTOR is a body that CONNECTS — span, end-ground step AND a
   TOPOLOGY.  The topology is read by REMOVING the body from its own unit
   and looking at what falls apart (:func:`_connector_ends`): a body that
   chains two groups makes them one unit by existing, so the partition
   WITH it in can never witness the split.  Every contact into ONE
   component means MEMBER, however long the body is — SPJC's 549 m
   access-road viaduct is the terminal's.
2. An identified connector is SEATED on its HIGH end's datum by the
   caller, ``footprint_unit.plan_wide_seats``, which is where the datums
   are; it never falls to §16c's low-side foot.
3. PROVENANCE IS A WITNESS: the shared-datum pack's own DSF row groups the
   placements it authored together (:func:`authored_units`), and a
   partition separating two siblings raises ``unit_split_authored``.

Nothing here reads a design surface or mutates a candidate: it answers
"what is this body, and between what" and hands the answer back.
"""
from __future__ import annotations

import bisect as _bi
import dataclasses as _dc
import typing as _t

from . import anchor_rule as _ar
from . import placement_boxes as _pb
from .placement_contact import (_polys_touch, boxes_touch,
                                m_per_deg_exact, ring_metres)

__all__ = ["PlanConnector", "CONNECTOR_BOXES_MAX", "_span_m",
           "_is_connector", "_connector_ends", "authored_units",
           "authored_unit_census", "ConnectorVerdict", "connector_verdict",
           "solid_connectors", "cut_pids", "verdicts_of", "deck_riders"]


def _span_m(boxes: _t.Sequence[tuple[float, float, float, float]]) -> float:
    """The plan DIAGONAL of a body's footprint, metres (§16g (3))."""
    h = _pb.hull_of(boxes)
    if h is None:
        return 0.0
    ml, mo = _ar._m_per_deg(0.5 * (h[0] + h[2]))
    return (((h[2] - h[0]) * ml) ** 2 + ((h[3] - h[1]) * mo) ** 2) ** 0.5


def _is_connector(c: _t.Any, cc: _t.Sequence[tuple[float, float, float, float]],
                  span_m: float, visual_m: float,
                  ends: "tuple[str, str] | None" = None) -> bool:
    """§16g (6) A CONNECTOR JOINS TWO UNITS (owner RULINGS 2026-09-13cn,
    on the owner's 13ce words: cutting is allowed only for "very long
    connecting pieces like the elevated rail at HECA").

    THREE tests, all of them: a footprint span of at least ``span_m``, two
    ends whose GROUND differs by at least ``visual_m``, AND — the test
    13cn adds — a TOPOLOGY: the body's two ends touch two DIFFERENT
    plan-wide footprint units, or one unit and open ground beyond
    ``span_m`` of it.  ``ends`` is that verdict, read off the plan-wide
    partition by :func:`_connector_ends` (``("", "")`` where the partition
    says nothing); ``None`` means no partition was available and the
    topology cannot be asserted, which is NOT a connector.

    "Long and sloping" alone identifies nothing.  A body whose every
    contact chains into ONE unit is a MEMBER of that unit however long it
    is and however much the ground under it varies — the SPJC access-road
    viaduct ``SPJC_LIMANUEVA_xp11_007__b0`` (span 549 m, end-ground spread
    11.58 m) is the terminal's, and the rule that exists for a kilometre
    of elevated rail threw it out to §16c's low-side foot 7.81 m above the
    unit datum (13cn).

    The ends are the two contacts furthest apart in plan, read on the
    hull's long axis — the cheap reading of "its two ends", and the one
    the span itself is measured on."""
    if span_m <= 0.0 or visual_m <= 0.0 or len(cc) < 2:
        return False
    if ends is None or ends[0] == ends[1]:
        return False
    boxes = list(c.part_boxes) or ([c.box] if c.box else [])
    if _span_m(boxes) < span_m:
        return False
    h = _pb.hull_of(boxes)
    if h is None:
        return False
    along_lat = (h[2] - h[0]) >= (h[3] - h[1])
    key = (lambda q: q[0]) if along_lat else (lambda q: q[1])
    lo = min(cc, key=key)
    hi = max(cc, key=key)
    return abs((lo[3] - lo[2]) - (hi[3] - hi[2])) >= visual_m

@_dc.dataclass(frozen=True)
class PlanConnector:
    """§16g (6): a body that CONNECTS two footprint units.

    ``end_a`` / ``end_b`` are the two ends' UNITS in plan order along the
    hull's long axis — the components its own unit ``unit`` would fall
    into without it, named ``<unit>/cN``; an empty side is OPEN GROUND (no
    body of the unit within ``connector_span_m`` of that end).  ``boxes_a``
    / ``boxes_b`` are those components' plan boxes, which is what the two
    ends' DATUMS are read on.  Which end the piece is SEATED on is the
    HIGH one, and that is a datum reading — made in
    :func:`plan_wide_seats`, where the datums exist."""

    id: str
    key: tuple[int, int, int]
    pids: frozenset[int]
    resource: str
    span_m: float
    unit: str
    end_a: str
    end_b: str
    boxes_a: tuple[tuple[float, float, float, float], ...] = ()
    boxes_b: tuple[tuple[float, float, float, float], ...] = ()
    #: the ``(unit, member, body)`` keys of each end component — what the
    #: DECK branch of :func:`plan_unit_datums` reads the datum off
    keys_a: tuple[tuple[int, int, int], ...] = ()
    keys_b: tuple[tuple[int, int, int], ...] = ()
    #: §16g (7) (2): the CONNECTOR'S OWN boxes at each end — the third of
    #: its footprint nearest that end.  The low-end seat is read HERE and
    #: not over the end unit, because a 1.1 km rail's end component is a
    #: whole terminal district whose median ground says nothing about the
    #: ground the rail's own abutment stands on (HECA: the component
    #: median 95.77 against the rail's north end ~73.4).
    own_a: tuple[tuple[float, float, float, float], ...] = ()
    own_b: tuple[tuple[float, float, float, float], ...] = ()


#: §16g (6): how many of a body's part boxes the end-topology test reads.
#: A clutter member carries thousands, and the question — "does this END
#: touch that unit" — is answered by a sample of the extremes.
CONNECTOR_BOXES_MAX = 256


def _thin(boxes: _t.Sequence[_t.Any], cap: int) -> list:
    step = max(1, len(boxes) // cap)
    return list(boxes[::step])


def _axis_of(h: tuple[float, float, float, float]):
    """The hull's LONG axis as a box -> position function (§16g (6): "its
    two ends", read on the axis the span is measured on)."""
    if (h[2] - h[0]) >= (h[3] - h[1]):
        return lambda b: 0.5 * (b[0] + b[2])
    return lambda b: 0.5 * (b[1] + b[3])


class ClusterTopology:
    """ONE DFS per unit cluster: the contact graph, its ARTICULATION
    POINTS and the components each of them separates (Hopcroft-Tarjan).

    WHY IT EXISTS (owner RULINGS 2026-09-14e; the owner's 1.0.331 OTHH
    tile was killed after 42 min in this code).  §16g (6) asks of each
    long body "remove me and see what my unit falls into", and round 1
    answered it by RE-CLUSTERING the whole unit per body: at OTHH the
    plan carries 62,406 bodies / 137,908 part boxes, its largest unit
    **43,334 bodies**, and **160 of that unit's bodies clear
    ``connector_span_m``** — 160 re-derivations of a clustering that
    costs ~7 s each.  The question is the textbook one and has a
    linear answer: the articulation points of the contact graph, and for
    each of them the branches its removal leaves, computed ONCE for the
    whole cluster in O(V + E).

    The components a vertex separates are read off the DFS tree, not
    recomputed: the preorder ``order`` makes every subtree a CONTIGUOUS
    SLICE (``order[tin[c] : tout[c] + 1]``), so a separating child's
    component is a list slice and the REST is the cluster minus those
    slices.  A vertex with no separating child is not an articulation
    point and its unit does not fall apart at all.
    """

    __slots__ = ("nodes", "adj", "order", "tin", "tout", "sep", "tree",
                 "spans")

    def __init__(self, nodes, adj, order, tin, tout, sep, tree, spans):
        self.nodes = nodes
        self.adj = adj
        self.order = order
        self.tin = tin
        self.tout = tout
        #: vertex -> the DFS children whose subtree it separates
        self.sep = sep
        #: vertex -> the DFS tree it belongs to (its root)
        self.tree = tree
        #: root -> its tree's ``(first, last)`` slice of ``order``
        self.spans = spans

    def components_without(self, u: int) -> list[list[int]]:
        """The connected components of ``cluster - {u}``, in the order
        :func:`_components` produced them (multi-body components by their
        least body, then the singletons ascending) so the component IDS
        this law publishes do not move."""
        cut = self.sep.get(u, ())
        parts = [self.order[self.tin[c]:self.tout[c] + 1] for c in cut]
        taken = {u}
        for g in parts:
            taken.update(g)
        # the REST is what ``u``'s OWN tree holds outside the separated
        # branches — for a DFS root whose every child is separated it is
        # empty, which is exactly right and needs no special case.  It is
        # read inside the tree because a cluster is connected by
        # construction but this table is not only asked about clusters:
        # another tree is its own component whatever ``u`` does.
        own = self.tree[u]
        lo, hi = self.spans[own]
        rest = [w for w in self.order[lo:hi + 1] if w not in taken]
        if rest:
            parts.append(rest)
        for r, (a, b) in self.spans.items():
            if r != own:
                parts.append(list(self.order[a:b + 1]))
        multi = sorted((sorted(g) for g in parts if len(g) > 1),
                       key=min)
        singles = sorted((g[0] for g in parts if len(g) == 1))
        return multi + [[j] for j in singles]


def contact_graph(cl: _t.Sequence[int], shims: _t.Sequence[_PShim],
                  touch_m: float) -> dict[int, list[int]]:
    """THE CLUSTER'S FULL CONTACT GRAPH at ``touch_m``.

    :func:`placement_family._clusters` records only the edges that UNION
    two components — its ``_adj`` is a spanning FOREST (OTHH: 61,604
    edges over 62,406 bodies), and articulation points read off a tree
    would call every interior body a cut vertex.  The topology needs
    every edge, so the same latitude sweep and the same
    :func:`placement_family.boxes_touch` predicate are run again over
    THIS cluster with no union-find short-circuit.  One derivation, one
    predicate: the partition and the topology can never disagree."""
    hull = {i: shims[i].box for i in cl if shims[i].box is not None}
    order = sorted(hull, key=lambda i: hull[i][0])
    slack = touch_m / 111_132.0
    adj: dict[int, list[int]] = {i: [] for i in order}
    boxes = {i: (list(shims[i].part_boxes) or [hull[i]]) for i in order}
    # §16g (7) (1): the SAME footprint-polygon predicate the partition
    # chains on — the topology and the partition are one relation
    ml, mo = m_per_deg_exact(hull[order[0]][0]) if order else (1.0, 1.0)
    rings = {i: [ring_metres(r, ml, mo)
                 for r in (getattr(shims[i], "rings", ()) or ()) if len(r) >= 3]
             for i in order}
    for ai, a in enumerate(order):
        north = hull[a][2] + slack
        ha = hull[a]
        for b in order[ai + 1:]:
            hb = hull[b]
            if hb[0] > north:
                break
            if (_pb.box_gap_m(ha, hb) <= touch_m
                    and boxes_touch(boxes[a], boxes[b], ha, hb, touch_m)
                    and _polys_touch(rings[a], rings[b], touch_m)):
                adj[a].append(b)
                adj[b].append(a)
    return adj


def cluster_topology(cl: _t.Sequence[int], shims: _t.Sequence[_PShim],
                     touch_m: float) -> ClusterTopology:
    """:class:`ClusterTopology` for one unit cluster — the contact graph
    and ONE iterative Hopcroft-Tarjan pass over it.

    Iterative on purpose: a 43,334-body cluster is far past Python's
    recursion limit, and the DFS is where the whole law now lives."""
    adj = contact_graph(cl, shims, touch_m)
    nodes = sorted(adj)
    disc: dict[int, int] = {}
    low: dict[int, int] = {}
    parent: dict[int, int] = {}
    tin: dict[int, int] = {}
    tout: dict[int, int] = {}
    sep: dict[int, list[int]] = {}
    tree: dict[int, int] = {}
    spans: dict[int, tuple[int, int]] = {}
    order: list[int] = []
    timer = 0
    for start in nodes:
        if start in disc:
            continue
        parent[start] = -1
        disc[start] = low[start] = timer
        timer += 1
        first = len(order)
        tin[start] = first
        tree[start] = start
        order.append(start)
        kids = 0
        stack = [(start, iter(adj[start]))]
        while stack:
            u, it = stack[-1]
            down = -1
            for v in it:
                if v not in disc:
                    down = v
                    break
                if v != parent[u] and disc[v] < low[u]:
                    low[u] = disc[v]
            if down >= 0:
                parent[down] = u
                disc[down] = low[down] = timer
                timer += 1
                tin[down] = len(order)
                tree[down] = start
                order.append(down)
                if u == start:
                    kids += 1
                stack.append((down, iter(adj[down])))
                continue
            stack.pop()
            tout[u] = len(order) - 1
            if stack:
                pa = stack[-1][0]
                if low[u] < low[pa]:
                    low[pa] = low[u]
                # a NON-ROOT parent is separated from this child exactly
                # when nothing in the child's subtree reaches above it
                if pa != start and low[u] >= disc[pa]:
                    sep.setdefault(pa, []).append(u)
        # the ROOT is a cut vertex iff it has two or more DFS children,
        # and then every child's subtree is its own component
        if kids >= 2:
            sep[start] = [w for w in adj[start] if parent.get(w) == start]
        spans[start] = (first, len(order) - 1)
    return ClusterTopology(nodes, adj, order, tin, tout, sep, tree, spans)


def _touches(i: int, group: _t.Sequence[int], shims: _t.Sequence[_PShim],
             touch_m: float, pos) -> "tuple[float, float] | None":
    """Where along ``i``'s long axis does it touch ``group``?  ``(lowest,
    highest)`` axis position of ITS OWN boxes that meet the group, or
    ``None``."""
    mine = _thin(shims[i].part_boxes, CONNECTOR_BOXES_MAX)
    lo = hi = None
    for j in group:
        s = shims[j]
        if s.box is None or _pb.box_gap_m(shims[i].box, s.box) > touch_m:
            continue
        theirs = _thin(s.part_boxes, CONNECTOR_BOXES_MAX)
        for b in mine:
            if any(_pb.box_gap_m(b, y) <= touch_m for y in theirs):
                p = pos(b)
                lo = p if lo is None or p < lo else lo
                hi = p if hi is None or p > hi else hi
    return None if lo is None else (lo, hi)


def _near_index(in_a_unit: _t.Sequence[int], shims: _t.Sequence[_PShim]
                ) -> "tuple[list[float], list[int]]":
    """Every body that is IN a unit, ordered by its hull's south edge —
    the window :func:`_free_end_is_open` searches.  Built ONCE per plan:
    the free-end test used to scan all 62,406 of OTHH's bodies per
    candidate."""
    live = [j for j in in_a_unit if shims[j].box is not None]
    live.sort(key=lambda j: shims[j].box[0])
    return [shims[j].box[0] for j in live], live


def _free_end_is_open(end: tuple, i: int, span_m: float,
                      shims: _t.Sequence[_PShim], index) -> bool:
    """§16g (6) (1)'s second clause: is there NOTHING within ``span_m`` of
    this end?  Only bodies whose hull starts inside the latitude window
    can be, so the sorted index is bisected instead of swept."""
    lats, live = index
    d = span_m / 111_132.0
    lo = _bi.bisect_left(lats, end[0] - d - (end[2] - end[0]) - d)
    hi = _bi.bisect_right(lats, end[2] + d)
    for k in range(lo, hi):
        j = live[k]
        if j != i and _pb.box_gap_m(end, shims[j].box) <= span_m:
            return False
    return True


def _connector_ends(i: int, uid: str, shims: _t.Sequence[_PShim],
                    touch_m: float, span_m: float, topo: ClusterTopology,
                    index) -> "PlanConnector | None":
    """§16g (6) (1): is body ``i`` of unit ``uid`` a CONNECTOR, and
    between what?  See ``footprint_unit.plan_units_and_connectors`` for
    the three cases.

    THE COMPONENTS COME FROM THE TABLE, NEVER FROM A RE-CLUSTERING
    (RULINGS 2026-09-14e): ``topo`` was built once for the whole cluster,
    and a body its removal does not separate is not a link at all — it
    goes straight to the open-ground clause without touching a box.  The
    bodies asked "do you touch this end" are ``i``'s own NEIGHBOURS in
    the contact graph and nothing else: at ``touch_m`` nothing further
    away can touch it, so the whole-component scan round 1 did was work
    for an answer it already had."""
    h = shims[i].box
    if h is None:
        return None
    pos = _axis_of(h)
    nbrs = topo.adj.get(i, ())
    if not nbrs:
        return None
    comps = topo.components_without(i)
    where = {}
    for k, g in enumerate(comps):
        for w in g:
            where[w] = k
    hit = []
    for k, g in enumerate(comps):
        grp = [v for v in nbrs if where.get(v) == k]
        if not grp:
            continue
        t = _touches(i, grp, shims, touch_m, pos)
        if t is not None:
            hit.append((t[0], t[1], k, g))
    if not hit:
        return None

    mine_all = _thin(shims[i].part_boxes, CONNECTOR_BOXES_MAX)
    _p = sorted(pos(b) for b in mine_all)
    _lo3 = _p[0] + (_p[-1] - _p[0]) / 3.0
    _hi3 = _p[-1] - (_p[-1] - _p[0]) / 3.0
    own_lo = tuple(b for b in mine_all if pos(b) <= _lo3) or tuple(mine_all[:1])
    own_hi = tuple(b for b in mine_all if pos(b) >= _hi3) or tuple(mine_all[-1:])

    def _made(a: str, b: str) -> PlanConnector:
        return PlanConnector(
            id=f"cn:{shims[i].key[0]}:{i}", key=shims[i].key,
            pids=shims[i].pids, resource=shims[i].resource,
            span_m=_span_m(shims[i].part_boxes), unit=uid,
            end_a=a, end_b=b,
            boxes_a=(() if not a else
                     tuple(x for j in _by[a] for x in shims[j].part_boxes)),
            boxes_b=(() if not b else
                     tuple(x for j in _by[b] for x in shims[j].part_boxes)),
            keys_a=(() if not a else tuple(shims[j].key for j in _by[a])),
            keys_b=(() if not b else tuple(shims[j].key for j in _by[b])),
            own_a=own_lo, own_b=own_hi)

    _by = {f"{uid}/c{k}": g for _lo, _hi, k, g in hit}
    if len(hit) >= 2:
        a = min(hit, key=lambda q: q[0])
        b = max((q for q in hit if q[2] != a[2]), key=lambda q: q[1])
        ia, ib = f"{uid}/c{a[2]}", f"{uid}/c{b[2]}"
        return _made(ia, ib) if a[0] <= b[1] else _made(ib, ia)
    # ONE component: is the other end free, and free of every unit body?
    lo, hi, k, _g = hit[0]
    mine = _thin(shims[i].part_boxes, CONNECTOR_BOXES_MAX)
    a0 = min(pos(b) for b in mine)
    a1 = max(pos(b) for b in mine)
    free_low = (lo - a0) >= (a1 - hi)
    end = min(mine, key=pos) if free_low else max(mine, key=pos)
    if not _free_end_is_open(end, i, span_m, shims, index):
        return None
    u = f"{uid}/c{k}"
    return _made("", u) if free_low else _made(u, "")


def connectors_of_cluster(cl: _t.Sequence[int], uid: str,
                          shims: _t.Sequence[_PShim], touch_m: float,
                          span_m: float, index) -> list[PlanConnector]:
    """§16g (6) (1) for ONE unit cluster: its CONNECTORS, over ONE
    Hopcroft-Tarjan pass (:func:`cluster_topology`).

    A cluster with no body over ``span_m`` never builds a graph at all,
    which is 168 of OTHH's 185 clusters."""
    longs = [i for i in cl if _span_m(shims[i].part_boxes) >= span_m]
    if not longs:
        return []
    topo = cluster_topology(cl, shims, touch_m)
    out = []
    for i in longs:
        got = _connector_ends(i, uid, shims, touch_m, span_m, topo, index)
        if got is not None:
            out.append(got)
    return out


# ── unit-platform spec §2: THE SOLID-CONNECTOR DISCRIMINATOR ─────────────
#
# Owner RULINGS 2026-09-28a (2): a SOLID CONNECTOR makes the units it joins
# ONE contiguous building with one flat pad, unless that creates an airside
# law violation.  Every other §16g (6) connector is CUT out of its chain.
# ONE verdict, computed HERE once per plan and stamped on it
# (``PackPartition.connectors`` -> ``RebakePlan.connectors``), read by BOTH
# ``placement_family.plan_clusters`` (the design surface) and
# ``footprint_unit`` (the object stage) — §16g (9) one population.

@_dc.dataclass(frozen=True)
class ConnectorVerdict:
    """One §16g (6) connector and its §2 verdict.

    ``solid`` = S1 walled along its whole length AND S3 not a deck AND S4
    the join's end-ground step within ``step_max_m``.  A connector that is
    not solid is CUT: it is removed from its unit's chain by both readers
    and seated on its LOW end's contact (§16g (7) (2)).  ``own_a`` /
    ``own_b`` are the connector's own boxes at each end (PlanConnector's),
    carried so the object stage seats a cut connector without re-deriving
    the topology."""

    pids: tuple[int, ...]
    resource: str
    span_m: float
    end_a: str
    end_b: str
    step_m: float
    walled_gap_m: float
    walled: bool
    deck: bool
    solid: bool
    own_a: tuple[tuple[float, float, float, float], ...] = ()
    own_b: tuple[tuple[float, float, float, float], ...] = ()

    @property
    def verdict(self) -> str:
        return "solid" if self.solid else "cut"

    def why(self) -> str:
        """S1/S3/S4, each named — the line a census posts per connector."""
        return (f"S1 walled={'yes' if self.walled else 'no'} "
                f"(worst plate-only run {self.walled_gap_m:.1f} m) "
                f"S3 deck={'yes' if self.deck else 'no'} "
                f"S4 end step {self.step_m:.2f} m")

    def to_dict(self) -> dict[str, _t.Any]:
        return {"pids": list(self.pids), "resource": self.resource,
                "span_m": self.span_m, "end_a": self.end_a,
                "end_b": self.end_b, "step_m": self.step_m,
                "walled_gap_m": self.walled_gap_m,
                "walled": self.walled, "deck": self.deck,
                "solid": self.solid,
                "own_a": [list(b) for b in self.own_a],
                "own_b": [list(b) for b in self.own_b]}

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "ConnectorVerdict":
        return cls(tuple(int(q) for q in d.get("pids", ())),
                   str(d.get("resource", "")), float(d.get("span_m", 0.0)),
                   str(d.get("end_a", "")), str(d.get("end_b", "")),
                   float(d.get("step_m", 0.0)),
                   float(d.get("walled_gap_m", 0.0)),
                   bool(d.get("walled", False)), bool(d.get("deck", False)),
                   bool(d.get("solid", False)),
                   tuple(tuple(float(x) for x in b) for b in d.get("own_a", ())),
                   tuple(tuple(float(x) for x in b) for b in d.get("own_b", ())))


def _plate_gap_m(parts: _t.Sequence[_t.Any], chain_min_height_m: float
                 ) -> tuple[float, float, bool]:
    """S1: ``(worst plate-only run along the long axis (m), axis length,
    along_lat)`` over a body's non-line parts.  The axis is the metric
    long side of the body's hull; every component of solid height >=
    ``chain_min_height_m`` covers its box's interval on it, and the worst
    uncovered run — both ends included — is what a deck on piers shows
    between its piers."""
    boxes = [p.box for p in parts if not p.line]
    h = _pb.hull_of(boxes)
    if h is None:
        return 0.0, 0.0, True
    ml, mo = m_per_deg_exact(0.5 * (h[0] + h[2]))
    along_lat = (h[2] - h[0]) * ml >= (h[3] - h[1]) * mo
    if along_lat:
        a0, sc, L = h[0], ml, (h[2] - h[0]) * ml
        iv = lambda b: ((b[0] - a0) * sc, (b[2] - a0) * sc)   # noqa: E731
    else:
        a0, sc, L = h[1], mo, (h[3] - h[1]) * mo
        iv = lambda b: ((b[1] - a0) * sc, (b[3] - a0) * sc)   # noqa: E731
    tall = sorted(iv(p.box) for p in parts if not p.line
                  and float(getattr(p, "height_m", 0.0)) >= chain_min_height_m)
    cur = gap = 0.0
    for lo, hi in tall:
        if lo > cur:
            gap = max(gap, lo - cur)
        cur = max(cur, hi)
    return max(gap, L - cur), L, along_lat


def _end_step_m(parts: _t.Sequence[_t.Any], ground, along_lat: bool
                ) -> "float | None":
    """S4's plan-time proxy: the connector's END-GROUND STEP — the median
    ``ground`` under its own outline vertices and feet in the third of its
    long axis nearest each end, differenced.  ``ground(lat, lon)`` is the
    DEM at planar time (the only ground there is)."""
    pts: list[tuple[float, float]] = []
    for p in parts:
        if p.line:
            continue
        rings = [r for r in (getattr(p, "rings", ()) or ()) if len(r) >= 3]
        for r in rings:
            pts.extend((float(q[0]), float(q[1])) for q in r)
        if not rings:
            # a part with no outline: its box corners are its extent
            b = p.box
            pts.extend(((b[0], b[1]), (b[0], b[3]), (b[2], b[1]),
                        (b[2], b[3])))
        pts.extend((float(f[0]), float(f[1])) for f in (p.feet or ()))
    if len(pts) < 2:
        return None
    k = 0 if along_lat else 1
    lo = min(q[k] for q in pts)
    hi = max(q[k] for q in pts)
    third = (hi - lo) / 3.0

    def _med(sel) -> "float | None":
        z = sorted(v for v in (ground(q[0], q[1]) for q in pts if sel(q[k]))
                   if v is not None)
        return z[len(z) // 2] if z else None
    za = _med(lambda x: x <= lo + third)
    zb = _med(lambda x: x >= hi - third)
    return None if za is None or zb is None else abs(za - zb)


def connector_verdict(cn: PlanConnector, parts: _t.Sequence[_t.Any],
                      member: _t.Any, ground, *, chain_min_height_m: float,
                      gap_max_m: float, step_max_m: float
                      ) -> "tuple[float | None, ConnectorVerdict]":
    """``(end step, verdict)`` for one topology-connector (§2 S1/S3/S4).
    The step is returned apart so the caller applies §16g (6)'s own
    ``visual_m`` identification test first — a body whose ends do not
    step is a MEMBER and gets no verdict at all."""
    gap, _L, along_lat = _plate_gap_m(parts, chain_min_height_m)
    step = _end_step_m(parts, ground, along_lat)
    walled = gap_max_m <= 0.0 or gap <= gap_max_m
    # S3 (spec-author ruling on #66, 2026-09-28): ``member_is_deck`` ONLY —
    # the object stage's own deck VERDICT.  ``deck_kind == 'candidate'`` is
    # not a verdict (spjcpads) and ``elevated_deck`` alone is not either:
    # both cut SPJC ``LIMANUEVA_xp11_010`` (the 13cn viaduct MEMBER) and
    # HECA ``T3_7`` out of their units.
    from .placement_family import member_is_deck
    deck = member_is_deck(member)
    s4 = step is not None and step <= step_max_m
    return step, ConnectorVerdict(
        tuple(sorted(cn.pids)), cn.resource, cn.span_m, cn.end_a, cn.end_b,
        -1.0 if step is None else step, gap, walled, deck,
        bool(walled and not deck and s4), tuple(cn.own_a), tuple(cn.own_b))


_VERDICT_MEMO: list[tuple[int, _t.Any, tuple, tuple]] = []


def solid_connectors(plan: _t.Any, ground, *, touch_m: float, span_m: float,
                     visual_m: float, chain_min_height_m: float,
                     gap_max_m: float, step_max_m: float,
                     sheet_chain_min_fraction: float = 0.0,
                     counts: "dict | None" = None
                     ) -> tuple[ConnectorVerdict, ...]:
    """unit-platform spec §2: EVERY §16g (6) connector of ``plan`` with its
    SOLID / CUT verdict — computed ONCE and stamped on the plan.

    A connector is §16g (6)'s: the TOPOLOGY (``footprint_unit.
    plan_units_and_connectors``, the articulation reading), a span of
    ``span_m`` AND an end-ground step of ``visual_m`` — read here on
    ``ground`` (the DEM at planar time).  Then S1 walled along its whole
    length (no plate-only run over ``gap_max_m``), S3 not a deck, S4 the
    step within ``step_max_m`` (``platform_collar_max_m x bank_slope``).
    ``()`` where the law is disarmed or the plan carries no unit."""
    if touch_m <= 0.0 or span_m <= 0.0 or not getattr(plan, "units", ()):
        return ()
    key = (touch_m, span_m, visual_m, chain_min_height_m, gap_max_m,
           step_max_m, sheet_chain_min_fraction)
    for k, p0, k0, got in _VERDICT_MEMO:
        if k == id(plan) and p0 is plan and k0 == key:
            return got
    from .footprint_unit import plan_units_and_connectors
    _u, conns = plan_units_and_connectors(
        plan, touch_m, span_m, None, chain_min_height_m, 0.0,
        sheet_chain_min_fraction)
    parts: dict[int, tuple[_t.Any, _t.Any]] = {}
    for u in plan.units:
        for m in u.members:
            for p in m.parts:
                parts[p.pid] = (p, m)
    out: list[ConnectorVerdict] = []
    n_member = 0
    for cn in conns:
        ps = [parts[q][0] for q in sorted(cn.pids) if q in parts]
        if not ps:
            continue
        m = parts[next(q for q in sorted(cn.pids) if q in parts)][1]
        step, v = connector_verdict(cn, ps, m, ground,
                                    chain_min_height_m=chain_min_height_m,
                                    gap_max_m=gap_max_m, step_max_m=step_max_m)
        if step is None or step < visual_m:
            n_member += 1          # §16g (6): ends that do not step -> MEMBER
            continue
        out.append(v)
    got = tuple(out)
    if counts is not None:
        counts["connectors_topology"] = len(conns)
        counts["connectors_member_no_step"] = n_member
        counts["connectors_solid"] = sum(1 for v in got if v.solid)
        counts["connectors_cut"] = sum(1 for v in got if not v.solid)
    _VERDICT_MEMO.append((id(plan), plan, key, got))
    del _VERDICT_MEMO[:-2]
    return got


def verdicts_of(plan: _t.Any) -> "tuple[ConnectorVerdict, ...] | None":
    """The verdict STAMPED on ``plan`` (a load partition carries
    :class:`ConnectorVerdict` objects, a rebake plan their JSON form), or
    ``None`` where nothing was stamped."""
    got = getattr(plan, "connectors", None)
    if got is None:
        return None
    return tuple(v if isinstance(v, ConnectorVerdict)
                 else ConnectorVerdict.from_dict(v) for v in got)


def cut_pids(verdicts: _t.Iterable[ConnectorVerdict]) -> frozenset[int]:
    """The part ids of every CUT connector — what both readers remove from
    their chains (§2: "CUTS every non-solid connector out of its chain")."""
    return frozenset(q for v in verdicts if not v.solid for q in v.pids)


def _plan_shape(parts: _t.Iterable[_t.Any]):
    """The plan footprint of ``parts`` in the (lat, lon) plane: their
    outline rings where the plan carries them, else their boxes."""
    from shapely.geometry import Polygon, box as _box
    from shapely.ops import unary_union
    polys = []
    for p in parts:
        rings = [r for r in (getattr(p, "rings", ()) or ()) if len(r) >= 3]
        if rings:
            for r in rings:
                q = Polygon([(float(v[0]), float(v[1])) for v in r])
                polys.append(q if q.is_valid else q.buffer(0))
        else:
            b = getattr(p, "box", None)
            if b is not None and b[2] > b[0] and b[3] > b[1]:
                polys.append(_box(b[0], b[1], b[2], b[3]))
    polys = [q for q in polys if not q.is_empty]
    return unary_union(polys) if polys else None


def deck_riders(plan: _t.Any, ui: int, staged: _t.Sequence[_t.Any],
                cands: _t.Sequence[_t.Any], cut: _t.AbstractSet[int],
                contacts: _t.Iterable[tuple[int, int]] = (),
                touch_m: float = 0.0, level_tol_m: float = 0.0,
                counts: "dict | None" = None
                ) -> dict[tuple[int, int], int]:
    """RULINGS 2026-09-29q (#98): A CUT CONNECTOR'S RAIL TOP AND FLOOR
    FOLLOW THE DECK, never a station unit.

    ``(member index, raw body index) -> candidate index`` of the DECK body
    (a candidate carrying cut-connector pids) that an ELEVATED or FOOTLESS
    body of the same unit rides, where the body is written at the deck's
    own authored heading (:func:`authored_units` — the pack's witness of
    one rigid object) and it is ON the deck by either reading:

    1. it carries an ε-CONTACT edge with one of the deck's parts (the
       plan's own graph — HECA's rail top `road_train/metal_strip_2.obj`,
       3 edges); or
    2. its plan footprint comes within ``touch_m`` of a deck part AND its
       lowest authored base stands within ``level_tol_m`` of that part's
       base — it is authored AT THE DECK'S LEVEL at the deck's edge (the
       station platform `road_train/floor.obj`, y 8.11 against the slab's
       8.24, 0 m in plan from the N leg).

    §16c (7)'s contact bind had put both on the station unit's senior
    (`titles_1__b6`, `fu:42:4636` on `building60`).  Several decks: the
    one with the most contact edges, then the nearest.  A body holding
    cut pids itself (the deck) is never a rider."""
    if not cut or not cands:
        return {}
    decks = [k for k, c in enumerate(cands) if c.pids & cut]
    if not decks:
        return {}
    au = authored_units(plan)
    by_mi = {st.mi: st for st in staged}
    deck_parts: dict[int, list] = {}
    for k in decks:
        c = cands[k]
        st = by_mi.get(c.member)
        if st is not None:
            deck_parts[k] = [p for r in st.raw for p in r[0] if p.pid in c.pids]
    owner = {p.pid: k for k, ps in deck_parts.items() for p in ps}
    touch: dict[int, dict[int, int]] = {}
    for a, b in contacts:
        for x, y in ((a, b), (b, a)):
            k = owner.get(x)
            if k is not None and y not in cut:
                touch.setdefault(y, {})
                touch[y][k] = touch[y].get(k, 0) + 1
    out: dict[tuple[int, int], int] = {}
    shapes: dict[int, _t.Any] = {}
    for st in staged:
        a = au.get((ui, st.mi))
        mine = [k for k in deck_parts
                if au.get((ui, cands[k].member)) == a and a is not None]
        if not mine:
            continue
        idx = range(len(st.raw)) if st.footless else sorted(st.elevated)
        for i in idx:
            parts = st.raw[i][0]
            if not parts or any(p.pid in cut for p in parts):
                continue
            edges: dict[int, int] = {}
            for p in parts:
                for k, n in touch.get(p.pid, {}).items():
                    if k in mine:
                        edges[k] = edges.get(k, 0) + n
            if edges:
                out[(st.mi, i)] = max(edges, key=lambda k: (edges[k], -k))
                continue
            if touch_m <= 0.0:
                continue
            g = _plan_shape(parts)
            if g is None:
                continue
            base = min(float(p.base_y) for p in parts)
            ml, mo = _ar._m_per_deg(float(parts[0].lat))
            deg = touch_m / max(1.0, min(ml, mo))
            best = None
            for k in mine:
                for q in deck_parts[k]:
                    if abs(float(q.base_y) - base) > level_tol_m:
                        continue
                    sq = shapes.get(q.pid)
                    if sq is None:
                        sq = shapes[q.pid] = _plan_shape([q])
                    if sq is None:
                        continue
                    d = g.distance(sq)
                    if d <= deg and (best is None or d < best[0]):
                        best = (d, k)
            if best is not None:
                out[(st.mi, i)] = best[1]
    if counts is not None and out:
        counts["bodies_ride_cut_connector_deck"] = \
            counts.get("bodies_ride_cut_connector_deck", 0) + len(out)
    return out


# ── §16g (6) (3) PROVENANCE IS A WITNESS ─────────────────────────────────

def authored_units(plan: _t.Any) -> dict[tuple[int, int], str]:
    """§16g (6) (3): the SHARED-DATUM PACK groups — ``(unit index, member
    index) -> authored unit id``.

    The pack's own row is the witness: placements written at ONE DSF
    origin (lat, lon to 1e-7) and ONE heading are one authored unit, which
    is how a shared-datum pack says "these eleven pieces are one
    building".  SPJC's eleven ``LIMANUEVA`` rows are one such group and
    §16g (3) threw two of them out of the unit the other nine formed
    (13cn) — this is the measurement that would have named that at plan
    time.

    It is a WITNESS, never a rule: nothing here moves a body."""
    key_of: dict[tuple[float, float, float], str] = {}
    out: dict[tuple[int, int], str] = {}
    rows: list[tuple[tuple[float, float, float], tuple[int, int]]] = []
    for ui, u in enumerate(getattr(plan, "units", ()) or ()):
        ll = getattr(u, "anchor", None) or (0.0, 0.0)
        la, lo = (float(ll[0]), float(ll[1]))
        for mi, m in enumerate(u.members):
            rows.append(((round(la, 7), round(lo, 7),
                          round(float(getattr(m, "heading_deg", 0.0)),
                                4)), (ui, mi)))
    for i, k in enumerate(sorted({k for k, _v in rows})):
        key_of[k] = f"au:{i}"
    for k, v in rows:
        out[v] = key_of[k]
    return out


def authored_unit_census(plan: _t.Any, pid_units: _t.Mapping[int, tuple]
                         ) -> dict[str, int]:
    """§16g (6) (3): does the footprint partition SEPARATE two siblings of
    one authored unit?  ``unit_split_authored`` is the cockpit's WARN —
    the count of shared-datum-pack groups whose bodies landed in more than
    one plan-wide footprint unit."""
    au = authored_units(plan)
    seen: dict[str, set[str]] = {}
    for ui, u in enumerate(getattr(plan, "units", ()) or ()):
        for mi, m in enumerate(u.members):
            a = au.get((ui, mi))
            if a is None:
                continue
            for p in m.parts:
                row = pid_units.get(p.pid)
                if row is not None:
                    seen.setdefault(a, set()).add(str(row[0]))
    return {"authored_units": len(set(au.values())),
            "authored_units_in_a_unit": len(seen),
            "unit_split_authored": sum(1 for v in seen.values()
                                       if len(v) > 1)}

