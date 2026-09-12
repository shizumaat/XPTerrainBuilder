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

import typing as _t

import numpy as np

__all__ = ["comp_of", "comp_cluster", "comp_blocks"]


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
    if (cut.rigid_reach_m > eps and n > 1
            and not cut.is_line_object()):
        eps = float(cut.rigid_reach_m)
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
                ti, tj = _tree(i0), _tree(j0)
                if ti is None or tj is None:
                    continue
                if ti.count_neighbors(tj, eps) > 0:
                    _union(i0, j0)
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

