"""THE PLAN LATTICE IN RUNS: cells of one frame held as row runs, their
connected regions and the roofed enclosures a region closes
(building-envelope spec ``docs/specs/building-envelope-20261127.md`` §2
B1, B4, B5).

A cell is ``(i, j)`` on a lattice of ``step`` metres aligned to multiples
of the step in the frame (``underside_map.supercover`` names them).  A set
of cells is a list of RUNS ``(i, j0, j1)``: the cells ``j0..j1`` of row
``i``.  A whole airport's wall plan is a few hundred thousand runs where
its cells are millions and its dense grid 10^8; every pass below is a sort
and a search over runs.  A :class:`_Lattice` turns ``(i, j)`` into one
int64 CODE ``i * nj + j + shift`` ordered row-major, with ``link`` free
columns on each side so no neighbour search wraps onto another row.

:func:`merge_runs` unions intervals per row (and per group);
:func:`run_regions` labels the connected components of disjoint runs
(``link`` 1: 8-connectivity; 2: cells two apart still join -- the 0.25 m
cell's two-cell link); :func:`roofed_fill` adds to each region the
enclosures it closes (the 4-connected background reaching no edge of the
region's box) whose cells a caller's cover mask passes for ``min_cover`` of
them; :func:`overlaps` pairs intervals with the runs they meet.

Pure numpy and scipy: no shapely, no engine type, no law.  Nothing here
names a pack, an object or an airport."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

__all__ = ["merge_runs", "run_regions", "roofed_fill", "overlaps"]


@_dc.dataclass(frozen=True)
class _Lattice:
    """The row-major code space of a set of columns (module doc)."""

    nj: int
    shift: int

    @classmethod
    def over(cls, j_lo: int, j_hi: int, link: int = 1) -> "_Lattice":
        """The code space of columns ``j_lo..j_hi`` with ``link`` + 1 free
        columns on each side."""
        pad = int(link) + 1
        return cls(int(j_hi) - int(j_lo) + 2 * pad + 1, pad - int(j_lo))

    def code(self, i: np.ndarray, j: np.ndarray) -> np.ndarray:
        return np.asarray(i, np.int64) * self.nj + np.asarray(j, np.int64) + self.shift


def merge_runs(g: np.ndarray, i: np.ndarray, j0: np.ndarray, j1: np.ndarray
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """The union of the intervals ``(i, j0, j1)`` per group ``g`` and row:
    disjoint, non-adjacent runs sorted by ``(g, i, j0)``."""
    if not len(i):
        return g, i, j0, j1
    o = np.lexsort((j0, i, g))
    g, i, j0, j1 = g[o], i[o], j0[o], j1[o]
    seg = np.r_[0, np.cumsum((g[1:] != g[:-1]) | (i[1:] != i[:-1]))]
    lo = int(min(j0.min(), j1.min()))
    big = int(max(j0.max(), j1.max())) - lo + 3
    e = j1 - lo + seg * big
    s = j0 - lo + seg * big
    cm = np.maximum.accumulate(e)
    new = np.r_[True, (seg[1:] != seg[:-1]) | (s[1:] > cm[:-1] + 1)]
    at = np.flatnonzero(new)
    return g[at], i[at], j0[at], np.maximum.reduceat(j1, at)


def _pairs(qa: np.ndarray, qb: np.ndarray, rs: np.ndarray, re: np.ndarray
           ) -> tuple[np.ndarray, np.ndarray]:
    """``(query, run)`` index pairs: each query code range ``qa..qb``
    against the disjoint sorted runs with start codes ``rs`` and end codes
    ``re`` -- every run that meets it."""
    lo = np.searchsorted(re, qa, side="left")
    hi = np.searchsorted(rs, qb, side="right")
    n = np.maximum(hi - lo, 0)
    q = np.repeat(np.arange(len(qa)), n)
    r = np.repeat(lo, n) + np.arange(len(q)) - np.repeat(np.cumsum(n) - n, n)
    return q, r


def run_regions(i: np.ndarray, j0: np.ndarray, j1: np.ndarray, link: int = 1
                ) -> tuple[np.ndarray, int]:
    """``(label per run, count)``: the connected components of the
    disjoint runs sorted by ``(i, j0)`` (cells within Chebyshev ``link``
    join), labelled in the order of their first run."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(i)
    if not n:
        return np.zeros(0, dtype=np.int64), 0
    lat = _Lattice.over(int(j0.min()), int(j1.max()), link)
    rs, re = lat.code(i, j0), lat.code(i, j1)
    a_all, b_all = [], []
    for d in range(0, link + 1):
        q, r = _pairs(lat.code(i + d, j0 - link), lat.code(i + d, j1 + link), rs, re)
        keep = r > q if d == 0 else np.ones(len(q), dtype=bool)
        a_all.append(q[keep])
        b_all.append(r[keep])
    a, b = np.concatenate(a_all), np.concatenate(b_all)
    gr = coo_matrix((np.ones(len(a), dtype=np.int8), (a, b)), shape=(n, n))
    nlab, lab = connected_components(gr, directed=False)
    first = np.full(nlab, n, dtype=np.int64)
    np.minimum.at(first, lab, np.arange(n))
    rank = np.empty(nlab, dtype=np.int64)
    rank[np.argsort(first, kind="stable")] = np.arange(nlab)
    return rank[lab].astype(np.int64), int(nlab)


def overlaps(qi: np.ndarray, qj0: np.ndarray, qj1: np.ndarray,
             ri: np.ndarray, rj0: np.ndarray, rj1: np.ndarray
             ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(query, run, cells)``: each interval ``q`` against the disjoint
    runs ``r`` sorted by ``(i, j0)``, one row per run it shares cells with
    and how many."""
    if not len(qi) or not len(ri):
        z = np.zeros(0, dtype=np.int64)
        return z, z, z
    lat = _Lattice.over(int(min(qj0.min(), rj0.min())), int(max(qj1.max(), rj1.max())), 0)
    q, r = _pairs(lat.code(qi, qj0), lat.code(qi, qj1), lat.code(ri, rj0), lat.code(ri, rj1))
    n = np.minimum(qj1[q], rj1[r]) - np.maximum(qj0[q], rj0[r]) + 1
    keep = n > 0
    return q[keep], r[keep], n[keep]


def _mask_runs(m: np.ndarray, a0: int, b0: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The runs ``(i, j0, j1)`` of the true cells of the dense mask ``m``
    whose cell ``[0, 0]`` is lattice cell ``(a0, b0)``."""
    p = np.pad(m.astype(np.int8), ((0, 0), (1, 1)))
    d = np.diff(p, axis=1)
    si, sj = np.nonzero(d == 1)
    ei, ej = np.nonzero(d == -1)
    return si + a0, sj + b0, ej - 1 + b0


def _dense(i, j0, j1, a0, b0, h, w) -> np.ndarray:
    """The runs painted on an ``h`` x ``w`` mask whose ``[0, 0]`` is cell
    ``(a0, b0)``."""
    m = np.zeros((h, w), dtype=bool)
    n = j1 - j0 + 1
    rr = np.repeat(i - a0, n)
    cc = np.repeat(j0 - b0, n) + np.arange(int(n.sum())) - np.repeat(np.cumsum(n) - n, n)
    m[rr, cc] = True
    return m


def roofed_fill(i: np.ndarray, j0: np.ndarray, j1: np.ndarray, lab: np.ndarray, count: int,
                cover: _t.Callable[[int, int, int, int, int], np.ndarray],
                min_cover: float, link: int = 1
                ) -> tuple[tuple[np.ndarray, ...], np.ndarray, dict[str, int]]:
    """``((i, j0, j1, label), joins, counts)``: the regions' runs grown by
    their ROOFED enclosures (module doc).  For each region, the holes of
    its own cells (dilated by ``link - 1``, so a two-cell link closes what
    it joins) -- the 4-connected background components that reach no edge
    of its box -- join it where ``cover(region, a0, b0, h, w)`` (a dense
    bool mask over the hole box, cell ``[0, 0]`` at lattice ``(a0, b0)``)
    is true on at least ``min_cover`` of their cells.  The runs come back
    sorted by ``(i, j0)``, NOT merged; ``joins`` ``(k, 2)`` names each pair
    of labels whose runs overlap (one region's roofed enclosure holding the
    other's cells), for the caller to join."""
    from scipy import ndimage as ndi
    counts = {"holes": 0, "roofed": 0, "unroofed": 0}
    if not count:
        return (i, j0, j1, lab), np.zeros((0, 2), dtype=np.int64), counts
    order = np.argsort(lab, kind="stable")
    bounds = np.searchsorted(lab[order], np.arange(count + 1))
    cross = ndi.generate_binary_structure(2, 1)
    grow = link - 1
    out = [[i], [j0], [j1], [lab]]
    for c in range(count):
        sel = order[bounds[c]:bounds[c + 1]]
        ii, a, b = i[sel], j0[sel], j1[sel]
        a0, b0 = int(ii.min()) - 1 - grow, int(a.min()) - 1 - grow
        h, w = int(ii.max()) - a0 + 2 + grow, int(b.max()) - b0 + 2 + grow
        if h < 3 or w < 3:
            continue
        m = _dense(ii, a, b, a0, b0, h, w)
        if grow:
            m = ndi.binary_dilation(m, structure=np.ones((2 * grow + 1,) * 2, dtype=bool))
        holes = ndi.binary_fill_holes(m, structure=cross) & ~m
        if not holes.any():
            continue
        hl, nh = ndi.label(holes, structure=cross)
        counts["holes"] += nh
        ok = np.asarray(cover(c, a0, b0, h, w), dtype=bool) & holes
        tot = np.bincount(hl.ravel(), minlength=nh + 1)
        cov = np.bincount(hl[ok], minlength=nh + 1)
        roof = np.flatnonzero((tot > 0) & (cov >= min_cover * tot))
        roof = roof[roof > 0]
        counts["roofed"] += len(roof)
        if len(roof):
            hi_, hj0, hj1 = _mask_runs(np.isin(hl, roof), a0, b0)
            for o, v in zip(out, (hi_, hj0, hj1, np.full(len(hi_), c, dtype=np.int64))):
                o.append(v)
    counts["unroofed"] = counts["holes"] - counts["roofed"]
    i, j0, j1, lab = (np.concatenate(o) for o in out)
    o = np.lexsort((j0, i))
    i, j0, j1, lab = i[o], j0[o], j1[o], lab[o]
    # a run starting inside the widest run before it in its row overlaps it
    big = int(j1.max()) - int(j0.min()) + 2
    row = np.r_[0, np.cumsum(i[1:] != i[:-1])]
    e = (j1 - int(j0.min()) + row * big) * len(i) + np.arange(len(i))
    cm = np.maximum.accumulate(e)
    prev_end = cm // len(i) - row * big + int(j0.min())
    prev_at = cm % len(i)
    hit = np.flatnonzero((np.r_[False, row[1:] == row[:-1]])
                         & (j0 <= np.r_[0, prev_end[:-1]]))
    pa = lab[prev_at[hit - 1]]
    pb = lab[hit]
    diff = pa != pb
    joins = np.unique(np.sort(np.column_stack([pa[diff], pb[diff]]), axis=1), axis=0) \
        if diff.any() else np.zeros((0, 2), dtype=np.int64)
    return (i, j0, j1, lab), joins, counts
