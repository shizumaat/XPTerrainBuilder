"""WHICH TRIANGLES OF A DECK FOOTPRINT TOUCH — the connected pieces of
:func:`bridge_family.deck_components` (issue #1179), read per SHARED-VERTEX
GROUP (issue #2177).

The partition is the one every reading of it has used: triangles chained
where they share a plan vertex, or come within ``gap_m`` of each other in
plan (GEOS ``dwithin`` over the triangles themselves, the source prepared,
either way round).  Two shared-vertex groups are one piece exactly when
SOME pair of their triangles is within the gap, so the pieces are the
connected components of the GROUP graph, and each group pair is asked once:

- plan-coincident triangles (the same three plan vertices: a wall's
  quads seen from above, a floor drawn twice) are ONE geometry and read
  once — the same polygon answers the same predicate, and they share
  their vertices, so their group is the same;
- the candidate group pairs are those whose plan boxes come within the
  gap (a pair of triangles within it lies in two such boxes);
- a pair is skipped once its two groups are already one piece, and an
  asked pair stops at its first touching triangle pair;
- a triangle pair whose plan projections on one of their own edge normals
  lie more than the gap (and a millimetre) apart is never asked of GEOS:
  the gap of the projections on ANY axis is a lower bound of the distance,
  so such a pair cannot be within the gap, whatever its shape (a triangle
  collapsed to a segment or a point included).

issue #2177: RJTT's ``T3INTER.obj`` (1.95 M triangles of stacked floors,
3,317 groups) read ~10 G box-near TRIANGLE pairs through the per-triangle
query and ran 11+ min to 39 GB in the owner's build; the same question
asked per group pair is a few thousand tests.  Private to the ``airport``
package: the caller is ``bridge_family.deck_components``.
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["touch_components"]

#: the triangle pairs one candidate query may hold (a batch size, not a
#: law): a query of ``k`` source boxes against a group of ``m`` triangles
#: holds at most ``k * m`` pairs, so ``k`` is sized to keep that under this
_PAIR_BATCH = 1 << 20

#: the first slice of surviving pairs asked of GEOS; each next slice is
#: four times the last (a touching pair is usually found in the first)
_FIRST_ASK = 64


def touch_components(xy: np.ndarray, gap_m: float) -> list[int]:
    """The piece label of each triangle — ``xy`` the ``(n, 3, 2)`` plan
    triangles in metres — under the partition of the module docstring.
    A piece is labelled by the lowest shared-vertex group label in it."""
    import shapely
    n = int(xy.shape[0])
    if n == 0:
        return []
    u, vid = np.unique(xy.reshape(-1, 2), axis=0, return_inverse=True)
    vid = vid.reshape(n, 3)
    # plan-coincident triangles: one representative each (``inv`` maps a
    # triangle to its representative's row)
    _k, rep, inv = np.unique(np.sort(vid, axis=1), axis=0, return_index=True,
                             return_inverse=True)
    inv = inv.reshape(-1)
    lab0 = _vertex_groups(vid[rep], len(u))
    order = np.argsort(lab0, kind="stable")
    cuts = np.r_[0, np.nonzero(np.diff(lab0[order]))[0] + 1, order.size]
    members = [order[cuts[g]:cuts[g + 1]] for g in range(cuts.size - 1)]
    pts = xy[rep]
    geo = shapely.polygons(np.concatenate([pts, pts[:, :1]], axis=1))
    shapely.prepare(geo)
    r = gap_m + 1e-3                     # a millimetre over: a superset
    lo, hi = pts.min(axis=1), pts.max(axis=1)
    boxes = shapely.box(lo[:, 0] - r, lo[:, 1] - r, hi[:, 0] + r, hi[:, 1] + r)
    axes = _edge_axes(pts)
    glo = np.minimum.reduceat(lo[order], cuts[:-1], axis=0)
    ghi = np.maximum.reduceat(hi[order], cuts[:-1], axis=0)
    ga, gb = shapely.STRtree(shapely.box(glo[:, 0], glo[:, 1], ghi[:, 0], ghi[:, 1])
                             ).query(shapely.box(glo[:, 0] - r, glo[:, 1] - r,
                                                 ghi[:, 0] + r, ghi[:, 1] + r))
    keep = ga < gb
    parent = list(range(len(members)))
    trees: dict[int, _t.Any] = {}

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _tree(g: int):
        t = trees.get(g)
        if t is None:
            t = trees[g] = shapely.STRtree(geo[members[g]])
        return t

    def _touch(a: int, b: int) -> bool:
        sa, sb = members[a], members[b]
        if sa.size > sb.size:
            a, b, sa, sb = b, a, sb, sa
        # only the source triangles whose padded box reaches ``b``'s box
        # can find a pair in ``b`` (the tree query's own first test)
        near = ((lo[sa, 0] - r <= ghi[b, 0]) & (hi[sa, 0] + r >= glo[b, 0])
                & (lo[sa, 1] - r <= ghi[b, 1]) & (hi[sa, 1] + r >= glo[b, 1]))
        sa = sa[near]
        t = _tree(b)
        step = max(1, _PAIR_BATCH // max(1, sb.size))
        for c0 in range(0, sa.size, step):
            src = sa[c0:c0 + step]
            qa, qb = t.query(boxes[src])
            if not qa.size:
                continue
            ia, ib = src[qa], sb[qb]
            near = ~(_apart(axes, ia, ib) > r)
            if _asked(geo, ia[near], ib[near], gap_m):
                return True
        return False

    for a, b in zip(ga[keep].tolist(), gb[keep].tolist(), strict=True):
        x, y = _find(a), _find(b)
        if x != y and _touch(a, b):
            parent[max(x, y)] = min(x, y)
    root = np.array([_find(g) for g in range(len(members))], dtype=np.int64)
    return root[lab0[inv]].tolist()


def _asked(geo: np.ndarray, ia: np.ndarray, ib: np.ndarray,
           gap_m: float) -> bool:
    """Whether any pair ``(geo[ia[k]], geo[ib[k]])`` is within ``gap_m``
    (GEOS ``dwithin`` either way round), asked in growing slices."""
    import shapely
    k0, k = 0, _FIRST_ASK
    while k0 < ia.size:
        ta, tb = geo[ia[k0:k0 + k]], geo[ib[k0:k0 + k]]
        if (shapely.dwithin(ta, tb, gap_m)
                | shapely.dwithin(tb, ta, gap_m)).any():
            return True
        k0 += k
        k *= 4
    return False


def _edge_axes(pts: np.ndarray) -> tuple:
    """Each triangle's three unit edge normals ``(n, 3, 2)``, which of them
    exist (an edge of no length has none), its own projection range on
    each ``(n, 3, 2)`` and its points — what :func:`_apart` reads."""
    e = np.roll(pts, -1, axis=1) - pts
    ln = np.hypot(e[..., 0], e[..., 1])
    ok = ln > 0.0
    nrm = np.zeros_like(e)
    nrm[ok] = np.stack([-e[..., 1][ok], e[..., 0][ok]], axis=-1) / ln[ok][:, None]
    pr = np.einsum("nkd,nvd->nkv", nrm, pts)
    return nrm, ok, np.stack([pr.min(axis=2), pr.max(axis=2)], axis=-1), pts


def _apart(axes: tuple, ia: np.ndarray, ib: np.ndarray) -> np.ndarray:
    """The largest gap between the plan projections of each pair's two
    triangles over the six edge normals — a lower bound of their distance
    (``-inf`` where no edge has a normal)."""
    nrm, ok, own, pts = axes

    def _on(i: np.ndarray, j: np.ndarray) -> np.ndarray:
        pr = np.einsum("mkd,mvd->mkv", nrm[i], pts[j])
        g = np.maximum(pr.min(axis=2) - own[i, :, 1], own[i, :, 0] - pr.max(axis=2))
        g[~ok[i]] = -np.inf
        return g.max(axis=1)
    return np.maximum(_on(ia, ib), _on(ib, ia))


def _vertex_groups(tri_vid: np.ndarray, n_vertices: int) -> np.ndarray:
    """The shared-vertex group of each triangle (triangle-vertex graph)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = int(tri_vid.shape[0])
    g = coo_matrix((np.ones(3 * n, dtype=np.int8),
                    (np.repeat(np.arange(n), 3), n + tri_vid.reshape(-1))),
                   shape=(n + n_vertices, n + n_vertices))
    return connected_components(g, directed=False)[1][:n]
