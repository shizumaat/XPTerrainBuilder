"""§16g (7) (1) THE FOOTPRINT-POLYGON CONTACT, MANY PAIRS AT ONCE (issue #412).

:func:`placement_contact._polys_touch` answers ONE pair of bodies with a
Python loop over ring pairs, edge pairs (``_seg_gap2``) and two
point-in-ring tests.  The connector topology's latitude sweep
(``footprint_connector._sweep``) asks it of every box-admitted pair of a
cluster — OTHH: 560,596 pairs, 35 M ``_seg_gap2`` calls, 83 of the sweep's
125 profiled seconds — and needs nothing of a verdict but the boolean.

:func:`polys_touch_many` is the SAME relation over a list of pairs, in
numpy: the ring-pair box reject (``_box_apart``), every edge pair's squared
distance by ``_seg_gap2``'s own arithmetic (the same IEEE operations in the
same order, branch by branch), and the even-odd test of ``_inside``.  Every
verdict is an ``any`` over pure predicates, so evaluating all of them
instead of stopping at the first hit changes no answer: the result is
``[_polys_touch(ra, rb, eps) for ra, rb in pairs]``, to the bit.  Twin:
``tests/auto_patch_v2/test_ring_contact_batch.py``.
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["polys_touch_many"]

#: edge pairs evaluated per numpy block (memory, not the answer)
_EDGE_BLOCK = 1 << 21


class _Rings:
    """The rings of the bodies a batch reads, flattened: per ring its
    box and its vertex span in ``v``; per body its ring span."""

    def __init__(self, ring_sets: _t.Sequence, bodies: np.ndarray) -> None:
        self.first = np.zeros(len(ring_sets), dtype=np.int64)
        self.count = np.zeros(len(ring_sets), dtype=np.int64)
        boxes: list = []
        starts: list[int] = []
        sizes: list[int] = []
        verts: list = []
        for p in bodies.tolist():
            rs = ring_sets[p] or ()
            self.first[p] = len(boxes)
            self.count[p] = len(rs)
            for vs, box, _edges in rs:
                boxes.append(box)
                starts.append(len(verts))
                sizes.append(len(vs))
                verts.extend(vs)
        self.box = np.array(boxes, dtype=float).reshape(-1, 4)
        self.start = np.array(starts, dtype=np.int64)
        self.size = np.array(sizes, dtype=np.int64)
        self.v = np.array(verts, dtype=float).reshape(-1, 2)


def _expand(na: np.ndarray, nb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For rows of ``na[k] * nb[k]`` combinations: per combination its
    row, its index in ``range(na[k])`` and in ``range(nb[k])``."""
    tot = na * nb
    row = np.repeat(np.arange(na.shape[0]), tot)
    off = np.arange(row.shape[0]) - np.repeat(np.cumsum(tot) - tot, tot)
    nbr = nb[row]
    return row, off // nbr, off % nbr


def _clip01(x: np.ndarray) -> np.ndarray:
    """``max(0.0, min(1.0, x))`` elementwise."""
    return np.maximum(0.0, np.minimum(1.0, x))


def _seg_gap2(p, q, r, t) -> np.ndarray:
    """``placement_contact._seg_gap2`` over rows of ``(n, 2)`` arrays —
    its arithmetic, operation for operation; a branch not taken is
    computed and discarded (``np.where``), never read."""
    ux, uy = q[:, 0] - p[:, 0], q[:, 1] - p[:, 1]
    vx, vy = t[:, 0] - r[:, 0], t[:, 1] - r[:, 1]
    wx, wy = p[:, 0] - r[:, 0], p[:, 1] - r[:, 1]
    a = ux * ux + uy * uy
    b = ux * vx + uy * vy
    c = vx * vx + vy * vy
    d = ux * wx + uy * wy
    e = vx * wx + vy * wy
    den = a * c - b * b
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.where(den > 1e-18, _clip01((b * e - c * d) / den), 0.0)
        tn = np.where(c > 1e-18, (b * s + e) / c, 0.0)
        lo, hi = tn < 0.0, tn > 1.0
        a_ok = a > 1e-18
        s = np.where(lo, np.where(a_ok, _clip01(-d / a), 0.0), s)
        s = np.where(hi, np.where(a_ok, _clip01((b - d) / a), 0.0), s)
    tn = np.where(lo, 0.0, np.where(hi, 1.0, tn))
    dx = wx + s * ux - tn * vx
    dy = wy + s * uy - tn * vy
    return dx * dx + dy * dy


def _edges_close(rg: _Rings, ra: np.ndarray, rb: np.ndarray, e2: float) -> np.ndarray:
    """Per ring pair ``(ra[k], rb[k])``: does any edge pair come within
    ``e2`` (squared)?  ``ring_metres``' edges: ``(vs[i], vs[(i + 1) % n])``."""
    out = np.zeros(ra.shape[0], dtype=bool)
    tot = rg.size[ra] * rg.size[rb]
    ends = np.cumsum(tot)
    lo = 0
    while lo < ra.shape[0]:
        base = ends[lo] - tot[lo]
        hi = max(lo + 1, int(np.searchsorted(ends, base + _EDGE_BLOCK, side="right")))
        sa, na = rg.start[ra[lo:hi]], rg.size[ra[lo:hi]]
        sb, nb = rg.start[rb[lo:hi]], rg.size[rb[lo:hi]]
        k, i, j = _expand(na, nb)
        sa, na, sb, nb = sa[k], na[k], sb[k], nb[k]
        hit = _seg_gap2(rg.v[sa + i], rg.v[sa + (i + 1) % na],
                        rg.v[sb + j], rg.v[sb + (j + 1) % nb]) <= e2
        if hit.any():
            out[lo + np.unique(k[hit])] = True
        lo = hi
    return out


def _inside(rg: _Rings, ring: np.ndarray, pt: np.ndarray) -> np.ndarray:
    """``placement_contact._inside(ring, x, y)`` per row: ``pt`` the
    ``(n, 2)`` points, ``ring`` their rings.  Its edge order is
    ``(ring[i], ring[i - 1])`` and its arithmetic is kept as written."""
    k, _z, i = _expand(np.ones(ring.shape[0], dtype=np.int64), rg.size[ring])
    s, n = rg.start[ring][k], rg.size[ring][k]
    ai, aj = rg.v[s + i], rg.v[s + (i - 1) % n]
    x, y = pt[k, 0], pt[k, 1]
    cross = (ai[:, 1] > y) != (aj[:, 1] > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        xx = ai[:, 0] + (y - ai[:, 1]) * (aj[:, 0] - ai[:, 0]) / (aj[:, 1] - ai[:, 1])
    flips = np.bincount(k[cross & (x < xx)], minlength=ring.shape[0])
    return (flips % 2) == 1


def polys_touch_many(ring_sets: _t.Sequence, pairs: _t.Sequence[tuple[int, int]],
                     eps_m: float) -> np.ndarray:
    """``[_polys_touch(ring_sets[a], ring_sets[b], eps_m) for a, b in pairs]``
    as a boolean array (module doc).  ``ring_sets[p]`` is a body's list of
    ``ring_metres`` rings, or empty / ``None`` (no ring: the box verdict
    stands, so the pair TOUCHES)."""
    pr = np.asarray(pairs, dtype=np.int64).reshape(-1, 2)
    out = np.ones(pr.shape[0], dtype=bool)
    if not pr.shape[0]:
        return out
    rg = _Rings(ring_sets, np.unique(pr))
    na, nb = rg.count[pr[:, 0]], rg.count[pr[:, 1]]
    both = np.nonzero((na > 0) & (nb > 0))[0]
    out[both] = False
    if not both.shape[0]:
        return out
    k, i, j = _expand(na[both], nb[both])
    ra = rg.first[pr[both, 0]][k] + i
    rb = rg.first[pr[both, 1]][k] + j
    bx, by = rg.box[ra], rg.box[rb]
    apart = ((bx[:, 0] - by[:, 2] > eps_m) | (by[:, 0] - bx[:, 2] > eps_m)
             | (bx[:, 1] - by[:, 3] > eps_m) | (by[:, 1] - bx[:, 3] > eps_m))
    live = np.nonzero(~apart)[0]
    ra, rb, k = ra[live], rb[live], k[live]
    touch = _edges_close(rg, ra, rb, eps_m * eps_m)
    rest = np.nonzero(~touch)[0]
    if rest.shape[0]:
        # rings_touch's containment: ring a's first vertex inside ring b,
        # or ring b's first vertex inside ring a
        a0 = rg.v[rg.start[ra[rest]]]
        b0 = rg.v[rg.start[rb[rest]]]
        touch[rest] = _inside(rg, rb[rest], a0) | _inside(rg, ra[rest], b0)
    out[both[np.unique(k[touch])]] = True
    return out
