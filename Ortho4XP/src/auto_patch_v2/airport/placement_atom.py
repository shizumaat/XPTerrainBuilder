"""§16c THE ATOM OF EVERY GROUP (spec ``object-placement-spec.md``
§16c (1)/(6)/(8); owner RULINGS 2026-09-12d/12h/12j).

The connected COMPONENT is the atom of every terrain, foot and carrier
group, and components of one resource that TOUCH — or, for a solid, that
come within the RIGID REACH — bind into one cluster that is the atom
instead.  It lives apart from ``placement_cut`` for the 1,000-line law
only; the cutter's ``comp_of`` / ``comp_cluster`` / ``_comp_blocks`` are
these functions, and every caller and every twin reads them there.

NO LAW CONSTANT LIVES HERE: the tolerances are the cutter's
(``contact_eps_m`` / ``rigid_reach_m``, from ``[placement]``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

#: §16c (8): the reach is asked only of a member with at most this many
#: components.  An AFFORDABILITY bound, measured and not a law: the reach
#: exists for an object an exporter authored in PIECES — a hangar's seven,
#: a deck's dozen — and a member with thousands of them is CLUTTER whose
#: pieces are meant to stand apart.  Unbounded, the pair search took the
#: LEMD plan stage 9.3 -> 26.3 s and did not finish OTHH in 43 minutes
#: (its clutter objects publish thousands of components inside one 2 m
#: box).  A member over the bound keeps §16c (6)'s CONTACT binding, which
#: is millimetres and cheap.
RIGID_REACH_COMPONENTS_MAX = 64

#: §16c (8): a rigid cluster never grows wider than this in PLAN.  A
#: cluster is ONE RIGID BODY and no cut may divide it, so a chain of 2 m
#: hops that walks a whole terminal makes a body wider than any terrain
#: it can stand on — which is what §16b (1) exists to forbid.  Measured
#: at OTHH: unbounded, the reach chains `OTHH_Terminal_Base_*` into
#: clusters spanning 1,042-1,175 m over 3-15 components.  Set well above
#: what a single authored object needs (LEMD's `Terminal4_48` is
#: 289 x 1,168 m and its fix depends on chaining across it) and below a
#: runaway.  Cost is NOT the reason for it: OTHH's plan stage is 64.33 s
#: at this cap, 64.45 s at 100 m and 63.46 s with the reach disarmed.
RIGID_CLUSTER_SPAN_MAX_M = 1200.0

#: §16c (7): a UNIT-WIDE contact cluster never grows wider than this in
#: PLAN.  The unit's ε-contact graph is not the member's: it chains 90 of
#: LEMD's 327 members into one component through unit 25's 11,365
#: cross-member pairs, and at ``RIGID_CLUSTER_SPAN_MAX_M`` it made
#: clusters 1,190 m wide that collapsed a 10.46 m range of honest terrain
#: readings onto ONE zero (measured, this lane).  What (7) is FOR is a
#: building — "walls + roofs + skylights in contact is one building" —
#: and a building is the scale this bounds.  Measured at LEMD: 1,200 m
#: collapses fences and grass mats, 100 m leaves the T2 block in two
#: clusters; 300 m is the block whole and nothing larger.
UNIT_CLUSTER_SPAN_MAX_M = 300.0

__all__ = ["comp_of", "comp_cluster", "comp_blocks", "unit_clusters",
           "unit_rigid", "RigidNode", "bind_unit", "RIGID_REACH_COMPONENTS_MAX",
           "RIGID_CLUSTER_SPAN_MAX_M", "UNIT_CLUSTER_SPAN_MAX_M"]


def comp_of(cut, tris) -> "list[int]":
    """§16c (1): THE COMPONENT EACH TRIANGLE BELONGS TO.

    The connected component is the ATOM of every group (owner
    RULINGS 2026-09-12d): a terrain, foot or carrier boundary that
    falls INSIDE a welded solid writes its two halves at two zeros,
    and the owner's 1.0.320 read found exactly that in the `HANG3`
    vault, `Bridge2`'s deck and `green-STRT4`'s approach slabs.  So
    every cut below groups COMPONENTS, and this is the map it groups
    them by: the authored triangle (its sorted vertex triple, the
    key ``obj8_split`` spells) -> its component index.  A triangle
    belonging to no component reads ``-1`` and is its own atom.

    The lookup is VECTORISED (one packed key per triangle and one
    ``searchsorted``): the cuts ask it once per cut per member, and a
    Python dict over 40,000 triangles costs more than the cut."""
    if cut._tri_keys is None:
        n = int(cut._geom.vertices.shape[0]) + 1 if cut._read() else 1
        cut._tri_base = np.int64(n)
        rows = [np.sort(np.asarray(c.tris, dtype=np.int64), axis=1)
                for c in cut._comps if len(c.tris)]
        ids = np.concatenate([np.full(len(c.tris), ci, dtype=np.int64)
                              for ci, c in enumerate(cut._comps)
                              if len(c.tris)]) if rows else \
            np.zeros(0, dtype=np.int64)
        if rows:
            r = np.concatenate(rows)
            keys = (r[:, 0] * cut._tri_base + r[:, 1]) * cut._tri_base \
                + r[:, 2]
        else:
            keys = np.zeros(0, dtype=np.int64)
        order = np.argsort(keys, kind="stable")
        cut._tri_keys = keys[order]
        cut._tri_ids = ids[order]
    q = np.sort(np.asarray(tris, dtype=np.int64).reshape(-1, 3), axis=1)
    qk = (q[:, 0] * cut._tri_base + q[:, 1]) * cut._tri_base + q[:, 2]
    if cut._tri_keys.shape[0] == 0:
        return [-1] * int(qk.shape[0])
    pos = np.searchsorted(cut._tri_keys, qk)
    pos = np.clip(pos, 0, cut._tri_keys.shape[0] - 1)
    hit = cut._tri_keys[pos] == qk
    out = np.where(hit, cut._tri_ids[pos], -1)
    return [int(x) for x in out.tolist()]

def comp_cluster(cut) -> "list[int]":
    """§16c (6)/(7): THE RIGID CLUSTER of each component.

    §16c (1) made the connected COMPONENT the atom, and an
    exporter's "one solid" is often several: OTHH's
    ``OTHH_Fuel_02_LOD0_007`` carries two 0.4 mm apart (the
    millimetre weld key reads them as two) and LEMD's `HANG3` is a
    hangar whose vault arcs stand 1.5-1.9 m from its spines with no
    contact at all.  Components of ONE resource bind into one rigid
    body — one zero, one carrier — when the PLAN's ε-contact graph
    links their parts (``contact_pairs``), when they come within
    ``[placement] contact_eps_m``, or, for a resource that is NOT a
    line object, within ``[placement] rigid_reach_m``.

    Built once per member; the distance test is ONE radius pair query
    over the member's vertices labelled by component, and is skipped
    when the epsilon is 0 or the member has one component."""
    if cut._clusters is not None:
        return cut._clusters
    if not cut._read():
        cut._clusters = []
        return cut._clusters
    n = len(cut._comps)
    par = list(range(n))

    def _find(a: int) -> int:
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def _union(a: int, b: int) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            par[ra] = rb

    for a, b in cut.contact_pairs:
        if 0 <= a < n and 0 <= b < n:
            _union(a, b)
    # §16c (7) THE RIGID REACH: a hangar's vault arcs stand metres
    # from its spines with no contact at all (LEMD `HANG3`,
    # 1.507-1.853 m, ZERO plan ε-contacts) and step where the roof is
    # continuous.  SOLID components chain at the reach; a LINE
    # object's never do — §10 cuts a fence into stations ON PURPOSE.
    eps = float(cut.contact_eps_m)
    span_max = 0.0
    if (cut.rigid_reach_m > eps and 1 < n <= RIGID_REACH_COMPONENTS_MAX
            and not cut.is_line_object()):
        eps = float(cut.rigid_reach_m)
        span_max = float(getattr(cut, "rigid_span_max_m", 0.0)
                         or RIGID_CLUSTER_SPAN_MAX_M)
    if n > 1 and eps > 0.0:
        # THE PAIRS ARE FOUND BY A SWEEP, NOT BY ALL-PAIRS.  A radius
        # query over every vertex of the member returns MILLIONS of pairs
        # at the 2 m reach and took the LEMD plan stage 9.3 -> 117 s
        # (measured); a KD-tree per component and an n^2 loop is
        # quadratic in a clutter object's thousands of components (it did
        # not finish OTHH).  So: sort the components by the low corner of
        # their box, walk the pairs whose boxes come within the reach
        # (one sweep, O(n log n) plus hits), skip anything already
        # unioned, and ask the trees only then.
        from scipy.spatial import cKDTree
        v = cut._geom.vertices
        pts = [v[np.unique(np.asarray(c.tris).reshape(-1))]
               for c in cut._comps]
        lo = np.asarray([p.min(axis=0) if p.size else np.zeros(3)
                         for p in pts])
        hi = np.asarray([p.max(axis=0) if p.size else np.zeros(3)
                         for p in pts])
        order = np.argsort(lo[:, 0]).tolist()
        # the running box of each cluster ROOT, for the span bound
        clo = {i: lo[i].copy() for i in range(n)}
        chi = {i: hi[i].copy() for i in range(n)}
        trees: dict[int, _t.Any] = {}

        def _tree(k: int):
            if k not in trees:
                trees[k] = cKDTree(pts[k]) if pts[k].size else None
            return trees[k]

        for a in range(n):
            i0 = order[a]
            for b in range(a + 1, n):
                j0 = order[b]
                if lo[j0][0] > hi[i0][0] + eps:
                    break                      # the sweep's own bound
                if _find(i0) == _find(j0):
                    continue
                if (lo[i0][1] > hi[j0][1] + eps or lo[j0][1] > hi[i0][1] + eps
                        or lo[i0][2] > hi[j0][2] + eps
                        or lo[j0][2] > hi[i0][2] + eps):
                    continue
                # THE TEST IS A NEAREST-NEIGHBOUR QUERY, NOT A PAIR
                # COUNT.  ``count_neighbors`` counts EVERY pair within
                # the radius — at 2 m between two dense clouds that is
                # billions, and it is what made OTHH's plan stage not
                # finish in 45 minutes (measured).  What the union needs
                # is whether ONE pair exists, so the smaller cloud is
                # queried against the larger with an upper bound.
                # §16c (8) BOUNDED BY THE TERRAIN LAW.  A cluster is
                # ONE RIGID BODY and no cut may divide it, so a chain of
                # 2 m hops that walks a whole terminal makes a body
                # wider than any terrain it can stand on — exactly what
                # §16b (1) exists to forbid.  Measured at OTHH: the five
                # largest clusters span 1,042-1,175 m over 3-15
                # components (`OTHH_Terminal_Base_*`), and that chaining
                # is also what made its plan stage unaffordable.  A
                # union is refused when the merged cluster's plan
                # diagonal would exceed ``span_max``.
                if span_max > 0.0:
                    ra, rb = _find(i0), _find(j0)
                    m0 = np.minimum(clo[ra], clo[rb])
                    m1 = np.maximum(chi[ra], chi[rb])
                    if float(np.hypot(m1[0] - m0[0], m1[2] - m0[2])) > span_max:
                        continue
                a_pts, b_pts = pts[i0], pts[j0]
                if a_pts.shape[0] > b_pts.shape[0]:
                    i0, j0 = j0, i0
                    a_pts, b_pts = b_pts, a_pts
                tj = _tree(j0)
                if tj is None or not a_pts.size:
                    continue
                d, _ix = tj.query(a_pts, k=1,
                                  distance_upper_bound=eps)
                if np.isfinite(d).any():
                    ra, rb = _find(i0), _find(j0)
                    box_lo = np.minimum(clo[ra], clo[rb])
                    box_hi = np.maximum(chi[ra], chi[rb])
                    _union(i0, j0)
                    r = _find(i0)
                    clo[r], chi[r] = box_lo, box_hi
    cut._clusters = [_find(i) for i in range(n)]
    return cut._clusters

def comp_blocks(cut, tris) -> "list[list[int]]":
    """§16c (1): the triangle indices of ``tris`` grouped by the
    ATOM each belongs to — its component, or, under §16c (6), the
    CLUSTER of components its own touches.  A triangle no component
    owns is an atom of its own."""
    cl = cut.comp_cluster()
    blocks: dict[int, list[int]] = {}
    loose: list[list[int]] = []
    for i, ci in enumerate(cut.comp_of(tris)):
        if ci < 0:
            loose.append([i])
        else:
            blocks.setdefault(cl[ci] if ci < len(cl) else ci,
                              []).append(i)
    return [blocks[k] for k in sorted(blocks)] + loose


def unit_clusters(cands: _t.Sequence[_t.Any],
                  contacts: _t.Iterable[tuple[int, int]],
                  span_max_m: float = UNIT_CLUSTER_SPAN_MAX_M,
                  bindable: "_t.Callable[[_t.Any], bool] | None" = None
                  ) -> tuple[list[int], dict[int, list[int]]]:
    """§16c (7): THE UNIT BINDS BY CONTACT (owner RULINGS 2026-09-12q).

    §16c (6) bound components of ONE MEMBER that touch; a terminal is
    authored as walls, roofs and skylights in SEPARATE RESOURCES that
    touch each other, and nothing bound those.  LEMD's T2: ``LEMD47``
    and ``LEMD48`` share 228 ε-contacts in the rebake plan and are
    written at four zeros; the block's walls stand at 602.89 ... 603.35
    and every roof inherits whichever the ranking hands it.

    The unit's FOOTED candidate groups are unioned wherever the plan's
    own ε-contact graph links a part of one to a part of another —
    intra-member pairs included, since a member's own groups are the
    same rigid thing — and the union is refused where the merged
    cluster's PLAN diagonal would exceed ``span_max_m``: a cluster is
    ONE rigid body at ONE zero, and a chain of contacts that walks a
    terminal makes a body wider than any terrain it can stand on
    (§16b (1)).  The contact graph alone chains 90 of LEMD's members in
    one component through unit 25's 11,365 cross-member pairs.

    Returns ``(root, pid_index)`` — the cluster root per candidate
    index, and the candidate indices each part id belongs to."""
    from . import anchor_rule as _ar
    n = len(cands)
    par = list(range(n))

    def _find(a: int) -> int:
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    pid_index: dict[int, list[int]] = {}
    for i, c in enumerate(cands):
        for p in c.pids:
            pid_index.setdefault(p, []).append(i)
    if n < 2:
        return ([_find(i) for i in range(n)], pid_index)
    # A LINE OBJECT NEVER BINDS (§16c (8)'s own exclusion, for the same
    # reason): §10 cuts a fence or a grass mat into stations ON PURPOSE,
    # every station reading its own ground, and the contact graph links
    # them end to end — unbound they were 11 `LEMDzaun` bodies over
    # 1,190 m forced onto one zero across 10.46 m of real relief.
    ok = [True if bindable is None else bool(bindable(c)) for c in cands]
    box = [tuple(c.box) if c.box is not None else None for c in cands]
    cbox: dict[int, tuple] = {i: box[i] for i in range(n) if box[i] is not None}

    def _span(b: tuple) -> float:
        ml, mo = _ar._m_per_deg(0.5 * (b[0] + b[2]))
        return float(((b[2] - b[0]) * ml) ** 2
                     + ((b[3] - b[1]) * mo) ** 2) ** 0.5

    for a, b in contacts:
        ia, ib = pid_index.get(a), pid_index.get(b)
        if not ia or not ib:
            continue
        for i in ia:
            for j in ib:
                if not (ok[i] and ok[j]):
                    continue
                ra, rb = _find(i), _find(j)
                if ra == rb:
                    continue
                ba, bb = cbox.get(ra), cbox.get(rb)
                if ba is not None and bb is not None and span_max_m > 0.0:
                    m0 = (min(ba[0], bb[0]), min(ba[1], bb[1]),
                          max(ba[2], bb[2]), max(ba[3], bb[3]))
                    if _span(m0) > span_max_m:
                        continue
                else:
                    m0 = ba if bb is None else bb
                par[ra] = rb
                if m0 is not None:
                    cbox[rb] = m0
    return ([_find(i) for i in range(n)], pid_index)


@_dc.dataclass(frozen=True)
class RigidNode:
    """§16c (7): one BODY of a unit as the rigid-cluster law sees it."""

    #: the member this body belongs to
    member: int
    #: its part ids (the ε-contact graph's own keys)
    pids: frozenset
    #: its plan box, ``(lat0, lon0, lat1, lon1)``
    box: "tuple[float, float, float, float] | None"
    #: its FOOTPRINT in m2 — the union area of the boxes it actually
    #: stands on, not its hull box: a kiosk whose parts are scattered
    #: over a terminal has a hull box bigger than the terminal's own
    #: walls and took the seniority of `Terminal4_48`'s cluster
    #: (measured, this lane).  0 where the plan publishes none.
    footprint_m2: float = 0.0
    #: does it stand on the ground?  Only a FOOTED body can be a
    #: cluster's senior — a cluster of roofs has no zero of its own.
    footed: bool = False
    #: may it bind at all (a LINE object never does)
    bindable: bool = True
    #: its own zero plane in world height, for the §9 low-side tie
    zero: "float | None" = None
    #: how many GROUND-CONTACT vertices it publishes — §9's own
    #: seniority, which decides the senior inside a file already
    feet: int = 0


def unit_rigid(nodes: _t.Sequence[RigidNode],
               contacts: _t.Iterable[tuple[int, int]],
               span_max_m: float = UNIT_CLUSTER_SPAN_MAX_M,
               near_m: float = 0.0, bind_ground_m: float = 0.0,
               counts: dict | None = None
               ) -> tuple[list[int], list[tuple[float, int, int]]]:
    """§16c (7): THE UNIT BINDS BY CONTACT (owner RULINGS 2026-09-12q).

    §16c (6) bound the components of ONE MEMBER that touch.  A terminal
    is authored as walls, roofs and skylights in SEPARATE RESOURCES that
    touch each other, and nothing bound those: LEMD's ``LEMD47`` and
    ``LEMD48`` share 228 ε-contacts in the rebake plan and were written
    at four zeros, and the T2 block's walls stood at 602.89 ... 603.35
    with every roof inheriting whichever the carrier ranking handed it.

    The bodies of one unit the plan's own ε-contact graph links — walls
    to walls, roofs to walls, a roof of one resource to the roof of the
    next — are ONE RIGID CLUSTER, and an ELEVATED body joins its own
    member's footed cluster whether or not the graph records an edge
    between them (a member is one authored object).  The cluster's zero
    is its SENIOR FOOTED body's: the largest footprint, ties to the LOW
    side (§9).  Every other body of the cluster rides that zero at its
    AUTHORED offset — which is what "the roof stays on its walls" means
    when the walls are the only thing any of them can read.

    THE CHAIN IS BOUNDED IN PLAN (``span_max_m``).  The unit's contact
    graph is not a building: at ``RIGID_CLUSTER_SPAN_MAX_M`` it made
    clusters 1,190 m wide that collapsed 10.46 m of honest terrain
    reading onto one zero (fences and grass mats, chained station to
    station).  A LINE object never binds at all, for §10's reason.

    ``contacts`` are the unit's ε-contact PART pairs.  Returns
    ``(senior, census)`` — the senior node of each node (``-1`` where
    the node is its own, or its cluster holds no footed body) and
    ``(plan span, bodies, members)`` per cluster of more than one body,
    largest span first."""
    from . import anchor_rule as _ar
    n = len(nodes)
    par = list(range(n))

    def _find(a: int) -> int:
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    pid_node: dict[int, list[int]] = {}
    for i, q in enumerate(nodes):
        if not q.bindable:
            continue
        for p in q.pids:
            pid_node.setdefault(p, []).append(i)
    cbox = {i: (tuple(q.box) if q.box is not None else None)
            for i, q in enumerate(nodes)}

    def _span(b: tuple) -> float:
        ml, mo = _ar._m_per_deg(0.5 * (b[0] + b[2]))
        return float(((b[2] - b[0]) * ml) ** 2
                     + ((b[3] - b[1]) * mo) ** 2) ** 0.5

    def _union(i: int, j: int) -> None:
        ra, rb = _find(i), _find(j)
        if ra == rb:
            return
        ba, bb = cbox.get(ra), cbox.get(rb)
        m0 = None
        if ba is not None and bb is not None:
            m0 = (min(ba[0], bb[0]), min(ba[1], bb[1]),
                  max(ba[2], bb[2]), max(ba[3], bb[3]))
            if span_max_m > 0.0 and _span(m0) > span_max_m:
                return
        elif ba is not None or bb is not None:
            m0 = ba if bb is None else bb
        par[ra] = rb
        cbox[rb] = m0
    # (a) THE MEMBER IS ONE AUTHORED OBJECT: its ELEVATED bodies join
    # the footed body of their own member they stand over.  The plan's
    # graph records contacts between PARTS, and a roof welded into its
    # own walls often shares no part with them (LEMD `LEMD47`: 228
    # ε-contacts with `LEMD48` and not one with its own walls).
    #
    # TWO FOOTED BODIES OF ONE MEMBER ARE NEVER UNIONED HERE: they were
    # cut apart because the ground under them differs (§9 / §16b (1)),
    # and unioning them forced `Terminal4-LEMD01`'s two bodies 20.5 m
    # onto one zero (measured, this lane).  An elevated body with NO
    # footed body of its own member under it is left to the carrier
    # search, which is what §15 is for.
    by_member: dict[int, list[int]] = {}
    for i, q in enumerate(nodes):
        if q.bindable:
            by_member.setdefault(q.member, []).append(i)
    for _m, idx in by_member.items():
        feet_i = [i for i in idx if nodes[i].footed and nodes[i].box is not None]
        if not feet_i:
            continue
        # WHICH footed body, AND HOW FAR IS TOO FAR.  The one it STANDS
        # OVER — the largest plan overlap — and, where it overlaps none,
        # the NEAREST within ``near_m``.  Both halves are measured:
        # `LEMD47`'s roof pieces stand BESIDE its walls, not over them
        # (0-12 m, and binding only the overlapping ones left the
        # resource at two zeros 0.491 m apart), while a member's own
        # ground body can be hundreds of metres from its roof — LEMD's
        # `LEMD38` roof took a carrier 250 m off and floated 6.11 m,
        # which is §15 (1)'s law and its twin, and an unconditional
        # union hands it back.  ``near_m`` is ``coarsen_reach_m``: the
        # distance at which bodies of ONE member are already one thing.
        # 12z's one-footed fast path made no test at all; it could not
        # show while the rule was dead (RULINGS 2026-09-12am (1)).
        for i in idx:
            if nodes[i].footed or nodes[i].box is None:
                continue
            b = nodes[i].box
            best, best_ov, near, near_d = -1, 0.0, -1, near_m
            for j in feet_i:
                q = nodes[j].box
                ov = (max(0.0, min(b[2], q[2]) - max(b[0], q[0]))
                      * max(0.0, min(b[3], q[3]) - max(b[1], q[1])))
                if ov > best_ov:
                    best, best_ov = j, ov
                if best_ov > 0.0 or near_m <= 0.0:
                    continue
                ml, mo = _ar._m_per_deg(0.5 * (b[0] + b[2]))
                d = float(np.hypot(
                    max(0.0, max(b[0] - q[2], q[0] - b[2])) * ml,
                    max(0.0, max(b[1] - q[3], q[1] - b[3])) * mo))
                if d < near_d:
                    near, near_d = j, d
            if best < 0:
                best = near
            if best >= 0:
                _union(i, best)
    # (b) AND THE ε-CONTACT GRAPH BINDS ACROSS MEMBERS
    for a, b in contacts:
        ia, ib = pid_node.get(a), pid_node.get(b)
        if not ia or not ib:
            continue
        for i in ia:
            for j in ib:
                _union(i, j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(_find(i), []).append(i)

    def _area(i: int) -> float:
        if nodes[i].footprint_m2:
            return float(nodes[i].footprint_m2)
        b = nodes[i].box
        if b is None:
            return 0.0
        ml, mo = _ar._m_per_deg(0.5 * (b[0] + b[2]))
        return float((b[2] - b[0]) * ml * (b[3] - b[1]) * mo)

    senior = [-1] * n
    census: list[tuple[float, int, int]] = []
    for _r, idx in groups.items():
        if len(idx) < 2:
            continue
        # THE SENIOR MUST HAVE A ZERO TO GIVE.  A body whose anchor
        # reads no design surface (off-sheet, §15 (5)) has none, and
        # binding a cluster to it put LEMD's `Cargo-EAT` 599 m down onto
        # its authored row (measured, this lane).
        footed = [i for i in idx if nodes[i].footed and nodes[i].zero is not None]
        if not footed:
            continue
        b = [nodes[i].box for i in idx if nodes[i].box is not None]
        if b:
            lo0 = min(x[0] for x in b); lo1 = min(x[1] for x in b)
            hi0 = max(x[2] for x in b); hi1 = max(x[3] for x in b)
            census.append((_span((lo0, lo1, hi0, hi1)), len(idx),
                           len({nodes[i].member for i in idx})))
        # §9's OWN SENIORITY FIRST, then the footprint: the body with
        # the most ground-contact vertices is the one whose reading of
        # the terrain the cluster should ride, and it is the rule
        # ``senior_of`` already applies inside a file.  Footprint alone
        # gave `Terminal4_48`'s cluster to a KIOSK whose parts are
        # scattered over the terminal (hull box) and the T2 block to a
        # body 0.9 m below (area); measured both ways, this lane.
        top = max(footed, key=lambda i: (nodes[i].feet, _area(i),
                                         -(nodes[i].zero or 0.0), -nodes[i].member))
        # (A), owner RULINGS 2026-09-12ap: A BIND ACROSS MEMBERS HOLDS
        # ONLY WHILE THE BOUND BODY'S OWN GROUND AGREES.  §16c (7) hands
        # a body the SENIOR'S ZERO whole, with no height test at all, and
        # 12ap measured what that costs: 41 of LEMD's 76 sunk bodies were
        # anchored MORE THAN 2 m from their own feet (median 37.5 m, max
        # 270 m), the plainest being the `TABOX`/`TABOXzwei`/`TAPSL` row
        # of 12 GSE boxes bound over 154 m of apron and each standing
        # ~1.9 m INTO it.  A box a metre under its apron is a visible
        # burial; what §16c (7) is FOR is a body with no ground of its
        # own, not one whose own ground says something else.
        #
        # So: a FOOTED body of ANOTHER MEMBER keeps the cluster only
        # while its own zero stands within ``bind_ground_m``
        # (``[cockpit] visual_m``) of the senior's.  Beyond it the body
        # keeps its own anchor and is COUNTED.  The test is
        # cross-member by construction — a refused bind is a seam
        # between two different RESOURCES, never a cut inside a solid,
        # and within one member 12z's own veto already stands.  An
        # ELEVATED body has no zero to test and is never refused: it is
        # exactly the class (7) exists for.
        _sz = nodes[top].zero
        for i in idx:
            if i == top:
                continue
            if (bind_ground_m > 0.0 and _sz is not None
                    and nodes[i].footed and nodes[i].zero is not None
                    and nodes[i].member != nodes[top].member
                    and abs(float(nodes[i].zero) - float(_sz))
                    > float(bind_ground_m)):
                if counts is not None:
                    counts["bind_refused_for_ground"] = \
                        counts.get("bind_refused_for_ground", 0) + 1
                    counts["bind_refused_worst_m"] = max(
                        counts.get("bind_refused_worst_m", 0.0),
                        round(abs(float(nodes[i].zero) - float(_sz)), 3))
                continue
            senior[i] = top
    census.sort(reverse=True)
    return (senior, census)


def bind_unit(cands: _t.Sequence[_t.Any], staged: _t.Sequence[_t.Any],
          surface: _t.Any, contacts: _t.Iterable[tuple[int, int]],
          counts: dict, near_m: float = 0.0,
          bind_ground_m: float = 0.0) -> tuple[dict, list]:
    """§16c (7) APPLIED TO ONE UNIT (owner RULINGS 2026-09-12q).

    Builds the unit's rigid nodes — every footed CANDIDATE and every
    elevated or footless BODY — asks :func:`unit_rigid` for the
    clusters, and applies the answer:

    * a FOOTED body of a cluster is re-anchored on the cluster's SENIOR
      (its file stays its own, standing where the cluster stands);
    * an ELEVATED body of a cluster RIDES the senior — the returned
      ``forced`` map, which ``placement_plan``'s pass 3 takes INSTEAD of
      the carrier search, because the question for such a body is not
      what it stands over but what it is part of.

    ``cands`` is mutated in place (the re-anchored candidates) and so is
    each ``staged`` member's ``raw`` / ``ground_off``.  Returns
    ``(forced, cluster census)``."""
    from . import anchor_rule as _ar
    from . import placement_carrier as _pc
    import dataclasses as _dc0
    _never_bind = (_ar.LINE_SEGMENT, _ar.BASIN)
    # the nodes: every footed CANDIDATE, then every elevated body
    nodes: list[RigidNode] = []
    cand_of_node: list[int] = []
    node_of: dict[tuple[int, int], int] = {}
    # EVERY FIELD IS NAMED, AND THAT IS THE LAW HERE (RULINGS 12am (1)).
    # The first form of this call passed them POSITIONALLY and put the
    # footprint where ``footed`` is declared: every node then read
    # ``footed`` TRUE (its own area) and ``footprint_m2`` 1.0, and rule
    # (a) below — an ELEVATED body joins its own member's footed cluster
    # — never fired at all: a member's ``feet_i`` held every one of its
    # bodies and not one was "not footed".  LEMD's `LEMD47` was the
    # residue the owner read at 1.0.320: its footed walls carry ZERO
    # recorded ε-contacts (all 114 with `LEMD48` are on its ELEVATED
    # parts), nothing else bound them, and the resource was written at
    # two zeros 0.804 m apart — over §31's 0.5 m visual threshold.
    for _ci, c in enumerate(cands):
        _z = (None if c.anchor.surface_z is None else
              float(c.anchor.surface_z) - float(c.anchor.y_zero))
        node_of[(c.member, ~c.group)] = len(nodes)
        cand_of_node.append(_ci)
        nodes.append(RigidNode(
            member=c.member, pids=frozenset(c.pids), box=c.box,
            footprint_m2=sum(_pc.box_area_m2(b) for b in c.part_boxes),
            footed=True, bindable=c.body_class not in _never_bind,
            zero=_z, feet=c.feet))
    for st in staged:
        for _bi, _r in enumerate(st.raw):
            if not (_r[4] or st.footless):
                continue
            node_of[(st.mi, _bi)] = len(nodes)
            cand_of_node.append(-1)
            nodes.append(RigidNode(
                member=st.mi,
                pids=frozenset(p.pid for p in _r[0]),
                box=_pc.hull_of(st.part_boxes[_bi]),
                footprint_m2=sum(_pc.box_area_m2(b)
                                 for b in st.part_boxes[_bi]),
                footed=False, bindable=_r[1] not in _never_bind,
                zero=None))
    senior_node, cl_census = unit_rigid(
        nodes, contacts, span_max_m=UNIT_CLUSTER_SPAN_MAX_M, near_m=near_m,
        bind_ground_m=bind_ground_m, counts=counts)
    # (A): the cluster's ZERO-PLANE SPAN, capped the same way and
    # reported — every retained footed member stands within
    # ``bind_ground_m`` of its senior, so this is what the cap bought.
    if bind_ground_m > 0.0:
        _byz: dict[int, list[float]] = {}
        for _i, _sn in enumerate(senior_node):
            if _sn >= 0 and nodes[_i].footed and nodes[_i].zero is not None:
                _byz.setdefault(_sn, []).append(float(nodes[_i].zero))
        for _sn, _zz in _byz.items():
            _z0 = nodes[_sn].zero
            if _z0 is not None:
                _zz.append(float(_z0))
            _sp = max(_zz) - min(_zz)
            counts["bind_zero_span_worst_m"] = max(
                counts.get("bind_zero_span_worst_m", 0.0), round(_sp, 3))
    counts["unit_clusters"] = counts.get("unit_clusters", 0) + len(cl_census)
    by_mi0 = {st.mi: st for st in staged}
    # (a) a FOOTED body of the cluster takes the senior's zero: its
    #     file stays its own, anchored where the cluster is
    for (mi0, key), ni in node_of.items():
        sn = senior_node[ni]
        if sn < 0 or key >= 0 or cand_of_node[sn] < 0:
            continue
        ci, si = cand_of_node[ni], cand_of_node[sn]
        c, sc = cands[ci], cands[si]
        # (E)/12ap: THE REASON NAMES THIS BODY'S OWN READING, not the
        # senior's.  A bound body used to inherit the senior's whole
        # Anchor including the sentence that explains it, and 12ao's
        # "4,454 feet on low-side anchors" table was built on that
        # field.  It says what it is — bound, to whom — and carries the
        # body's own zero against the one it takes.
        _own = (None if (c.anchor.surface_z is None
                         or sc.anchor.surface_z is None) else
                (float(c.anchor.surface_z) - float(c.anchor.y_zero))
                - (float(sc.anchor.surface_z) - float(sc.anchor.y_zero)))
        a = _dc0.replace(sc.anchor, body_class=c.anchor.body_class,
                        reason=f"§16c (7) bound to {sc.resource} (the "
                               f"unit's rigid cluster, senior by feet then "
                               f"footprint; own ground "
                               + ("off-sheet)" if _own is None
                                  else f"{_own:+.2f} m)"))
        st0 = by_mi0.get(mi0)
        if st0 is None or not (0 <= c.group < len(st0.groups)):
            continue
        grp0 = st0.groups[c.group]
        if not grp0:
            continue
        k0 = _pc.senior_of(st0.raw, grp0)
        r0 = st0.raw[k0]
        st0.raw[k0] = (r0[0], r0[1], a) + tuple(r0[3:])
        _off0 = _pc.anchor_ground_off(
            a, tuple(f for j0 in grp0 for f in st0.raw[j0][3]), surface)
        if c.group < len(st0.ground_off):
            st0.ground_off[c.group] = _off0
        cands[ci] = _dc0.replace(c, anchor=a, ground_off=_off0)
        counts["bodies_bound_by_unit_contact"] = \
            counts.get("bodies_bound_by_unit_contact", 0) + 1
    # (b) an ELEVATED body of the cluster RIDES its senior — the
    #     carrier search is not asked, because the answer is not
    #     "what does it stand over" but "what is it part of"
    forced: dict[tuple[int, int], int] = {}
    for (mi0, key), ni in node_of.items():
        sn = senior_node[ni]
        if sn < 0 or key < 0 or cand_of_node[sn] < 0:
            continue
        forced[(mi0, key)] = cand_of_node[sn]


    return (forced, cl_census)
