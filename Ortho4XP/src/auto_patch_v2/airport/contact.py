"""THE PARTITION (RULINGS 2026-09-06g; v1 ``object_anchor.discover_object_pools``
/ ``partition_structures`` and ``obj8_partition.contact_graph`` as v2 code —
v2 never imports v1).

The pack's placed objects are pooled by placed-footprint overlap
(``[rebake] pool_overlap_m``), every genuine solid component of every
member is a welded PART placed in the airport frame with its rendered
elevation (``DEM(anchor) + agl + y``), and two parts within
``contact_epsilon_m`` of each other — surface to surface, in 3-D — are in
CONTACT.  The connected components of the contact graph are the
STRUCTURES; the seat cuts them into clusters after the mesh
(``emit/clusters.py``).

Pass 1, vertex to vertex: ONE k-d tree over every part's points answers
every vertex pair within ε across the pack (welded and coincident
geometry — the bulk of real contacts) and unions their parts.  Pass 2,
the broad phase: a uniform grid on the plan (``contact_grid_cell_m``)
over 3-D boxes expanded by ε (sound: a box gap never exceeds a surface
gap); a pair still in different components is tested vertex-to-triangle
in both directions under ``contact_narrow_budget`` point × triangle
operations; a pair the budget cannot prove apart KEEPS its contact (v1
invariant I-20: over-merging costs centimetres, tearing is
unrecoverable).  Pairs already joined transitively are skipped, so the
edges are a connectivity-equivalent SPANNING subset — the set v1's cut
law was calibrated on (``object_clusters`` module doc).  Measured HECA
(415 members, 55,569 parts): 28.7 s with the pairwise quick-accept,
the global pass below cuts the triangle tests to the unwelded remainder.

Pure geometry over numpy; no I/O, no environment.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..model.frame import XY
from . import obj8 as _obj8

__all__ = ["PlacedPart", "Partition", "partition"]


@_dc.dataclass(frozen=True)
class PlacedPart:
    """One welded part in the airport frame: ``pts`` ``(n, 3)`` as
    ``(east, rendered y, north)``, ``tris`` ``(m, 3)`` into ``pts``."""

    pid: int
    member: int
    comp: int
    pts: np.ndarray
    tris: np.ndarray
    base_y: float
    area_m2: float
    centroid: XY
    box_min: np.ndarray
    box_max: np.ndarray
    #: per-triangle boxes ``(m, 3)`` (the narrow phase's prefilter)
    tri_lo: np.ndarray = _dc.field(default=None, repr=False, compare=False)
    tri_hi: np.ndarray = _dc.field(default=None, repr=False, compare=False)
    #: THE GROUND FEET (RULINGS 2026-09-09s (2)): ``(k, 3)`` rows
    #: ``(frame x, frame y, AUTHORED y)`` — the component's lowest solid
    #: vertices within the foot band of its own minimum, spread over the
    #: plan.  Empty for an ELEVATED part (culled in :func:`partition`).
    feet: np.ndarray = _dc.field(default=None, repr=False, compare=False)
    #: THE LINE OBJECT (owner RULINGS 2026-09-10bb; ``airport/line_object``):
    #: a component of a fence / kerb / jet-blast line / light string.  It
    #: forms no body and founds no foot; its ``feet`` are its DRAPE
    #: STATIONS, widened here to one per ``body_feet_span_m``.
    line: bool = False

    @property
    def plan_box(self) -> tuple[float, float, float, float]:
        """``(min_x, min_y, max_x, max_y)`` in the frame."""
        return (float(self.box_min[0]), float(self.box_min[2]),
                float(self.box_max[0]), float(self.box_max[2]))


@_dc.dataclass(frozen=True)
class Partition:
    parts: tuple[PlacedPart, ...]
    contacts: tuple[tuple[int, int], ...]
    pools: int
    structures: int
    pairs_tested: int
    pairs_unproved: int


def _place(geom: _obj8.ObjGeometry, o: _obj8.PlacedObject, ids: np.ndarray) -> np.ndarray:
    """The object's vertices ``ids`` in the frame with rendered y."""
    v = geom.vertices[ids]
    h = math.radians(o.heading_deg)
    sn, cs = math.sin(h), math.cos(h)
    out = np.empty((ids.shape[0], 3), dtype=float)
    out[:, 0] = o.xy[0] + v[:, 0] * cs - v[:, 2] * sn
    out[:, 2] = o.xy[1] - (v[:, 0] * sn + v[:, 2] * cs)
    out[:, 1] = o.anchor_z + o.agl_m + v[:, 1]
    return out


#: One member for the partition: its placement, geometry and genuine
#: components as ``(index into obj8.solid_components, component)``.
MemberGeometry = tuple[_obj8.PlacedObject, _obj8.ObjGeometry,
                       _t.Sequence[tuple[int, _obj8.Component]]]


def _feet(pts: np.ndarray, min_y: float, base_plane: float, band: float, k_max: int
          ) -> np.ndarray:
    """THE GROUND FEET of one placed part (RULINGS 2026-09-09s (2)): its
    vertices whose AUTHORED y (``rendered − base_plane``) lies within
    ``band`` of the component's own minimum ``min_y``, thinned to
    ``k_max`` by farthest-point over the PLAN so a long component's feet
    span it (a 900 m terminal read at one corner is one sample of a
    slope).  Rows ``(x, y, authored y)``; deterministic (the lowest
    vertex, ties by index, starts the walk)."""
    auth = pts[:, 1] - base_plane
    sel = np.nonzero(auth <= min_y + band)[0]
    if sel.shape[0] == 0:
        sel = np.array([int(np.argmin(auth))])
    if sel.shape[0] <= k_max:
        pick = sel
    else:
        plan = pts[sel][:, [0, 2]]
        start = int(np.argmin(auth[sel]))
        chosen = [start]
        d2 = ((plan - plan[start]) ** 2).sum(1)
        while len(chosen) < k_max:
            nxt = int(np.argmax(d2))
            if d2[nxt] <= 0.0:
                break
            chosen.append(nxt)
            d2 = np.minimum(d2, ((plan - plan[nxt]) ** 2).sum(1))
        pick = sel[np.array(sorted(chosen))]
    out = np.empty((pick.shape[0], 3), dtype=float)
    out[:, 0] = pts[pick, 0]
    out[:, 1] = pts[pick, 2]
    out[:, 2] = auth[pick]
    return out


def placed_parts(members: _t.Sequence[MemberGeometry], foot_band_m: float = 1.0,
                 foot_samples_max: int = 4,
                 line_members: _t.Collection[int] = (),
                 station_span_m: float = 0.0, stations_max: int = 0) -> list[PlacedPart]:
    """Every genuine component of every member as a placed part, in
    member order then component order (deterministic pids).  A member in
    ``line_members`` is a LINE OBJECT (RULINGS 2026-09-10bb): its parts
    are flagged and their feet are widened to the DRAPE STATIONS — one
    per ``station_span_m`` of the part's plan length, capped at
    ``stations_max`` — so the segment seat reads the design surface
    along the whole fence and not at four points of a 5 km run."""
    parts: list[PlacedPart] = []
    lines = set(line_members)
    for mi, (o, geom, comps) in enumerate(members):
        is_line = mi in lines
        for ci, c in comps:
            tris = np.asarray(c.tris)
            ids, inv = np.unique(tris.reshape(-1), return_inverse=True)
            pts = _place(geom, o, ids)
            lt = inv.reshape(tris.shape)
            a, b, d = pts[lt[:, 0]], pts[lt[:, 1]], pts[lt[:, 2]]
            areas = 0.5 * np.linalg.norm(np.cross(b - a, d - a), axis=1)
            total = float(areas.sum())
            cen = (a + b + d) / 3.0
            if total > 0.0:
                cx = float((cen[:, 0] * areas).sum() / total)
                cy = float((cen[:, 2] * areas).sum() / total)
            else:
                cx, cy = float(pts[:, 0].mean()), float(pts[:, 2].mean())
            k_max = foot_samples_max
            if is_line and station_span_m > 0.0 and stations_max > 0:
                span = math.hypot(float(pts[:, 0].max() - pts[:, 0].min()),
                                  float(pts[:, 2].max() - pts[:, 2].min()))
                k_max = max(foot_samples_max,
                            min(stations_max, int(math.ceil(span / station_span_m))))
            parts.append(PlacedPart(len(parts), mi, ci, pts, lt, float(c.min_y), total,
                                    (cx, cy), pts.min(axis=0), pts.max(axis=0),
                                    np.minimum(np.minimum(a, b), d), np.maximum(np.maximum(a, b), d),
                                    _feet(pts, float(c.min_y), o.anchor_z + o.agl_m,
                                          foot_band_m, k_max), is_line))
    return parts


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))

    def find(self, a: int) -> int:
        p = self.p
        while p[a] != a:
            p[a] = p[p[a]]
            a = p[a]
        return a

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.p[ra] = rb
        return True

    def groups(self) -> int:
        return len({self.find(i) for i in range(len(self.p))})


def _pools(parts: _t.Sequence[PlacedPart], n_members: int, overlap_m: float) -> int:
    """Members whose placed solid boxes overlap within ``overlap_m``
    (transitively) are one pool — v1 ``discover_object_pools``; a count
    for the record (the grid broad phase below already bounds the search)."""
    if n_members == 0:
        return 0
    lo = np.full((n_members, 2), np.inf)
    hi = np.full((n_members, 2), -np.inf)
    for p in parts:
        lo[p.member] = np.minimum(lo[p.member], p.box_min[[0, 2]])
        hi[p.member] = np.maximum(hi[p.member], p.box_max[[0, 2]])
    uf = _UnionFind(n_members)
    order = np.argsort(lo[:, 0])
    active: list[int] = []
    for i in order:
        if not np.isfinite(lo[i, 0]):
            continue
        active = [j for j in active if hi[j, 0] + overlap_m >= lo[i, 0]]
        for j in active:
            if lo[i, 1] <= hi[j, 1] + overlap_m and lo[j, 1] <= hi[i, 1] + overlap_m:
                uf.union(int(i), int(j))
        active.append(int(i))
    return uf.groups()


def _broad_pairs(parts: _t.Sequence[PlacedPart], eps: float) -> np.ndarray:
    """Pass 2's candidates: every ``(pid, pid)`` whose 3-D boxes come within
    ``eps`` on every axis — a sort-sweep on the east axis, the other two
    axes filtered per slice in numpy (v1 used a grid; the sweep has no
    cell parameter to tune and no bucket duplicates)."""
    n = len(parts)
    if n < 2:
        return np.zeros((0, 2), dtype=int)
    lo = np.array([p.box_min for p in parts])
    hi = np.array([p.box_max for p in parts])
    order = np.argsort(lo[:, 0], kind="stable")
    smin = lo[order, 0]
    out: list[np.ndarray] = []
    for i in range(n):
        k = int(order[i])
        j = int(np.searchsorted(smin, hi[k, 0] + eps, side="right"))
        if j <= i + 1:
            continue
        cand = order[i + 1:j]
        m = ((lo[cand, 1] - eps <= hi[k, 1]) & (lo[k, 1] - eps <= hi[cand, 1])
             & (lo[cand, 2] - eps <= hi[k, 2]) & (lo[k, 2] - eps <= hi[cand, 2]))
        if m.any():
            c = cand[m]
            out.append(np.stack([np.full(c.shape[0], k), c], axis=1))
    if not out:
        return np.zeros((0, 2), dtype=int)
    pairs = np.unique(np.sort(np.concatenate(out), axis=1), axis=0)
    # touching / overlapping boxes first: their contacts union early and
    # the box-gap pairs behind them mostly skip as already joined
    gap = np.maximum(lo[pairs[:, 0]] - hi[pairs[:, 1]], lo[pairs[:, 1]] - hi[pairs[:, 0]]).max(axis=1)
    return pairs[np.argsort(gap, kind="stable")]


def _weld_pairs(parts: _t.Sequence[PlacedPart], mm: float) -> np.ndarray:
    """Pass 1: parts sharing a vertex POSITION to ``mm`` (v1 ``weld_parts``
    across the pool — exporters duplicate a position per seam, and
    adjoining objects are authored to meet exactly): ``(pid, pid)`` pairs."""
    if not parts:
        return np.zeros((0, 2), dtype=int)
    pts = np.concatenate([p.pts for p in parts])
    owner = np.concatenate([np.full(p.pts.shape[0], p.pid, dtype=np.int64) for p in parts])
    q = np.round(pts / mm).astype(np.int64)
    q -= q.min(axis=0)
    span = q.max(axis=0) + 1
    key = (q[:, 0] * span[1] + q[:, 1]) * span[2] + q[:, 2]
    order = np.argsort(key, kind="stable")
    key, owner = key[order], owner[order]
    same = key[1:] == key[:-1]
    diff = owner[1:] != owner[:-1]
    m = same & diff
    if not m.any():
        return np.zeros((0, 2), dtype=int)
    pairs = np.stack([owner[:-1][m], owner[1:][m]], axis=1)
    return np.unique(np.sort(pairs, axis=1), axis=0)


def _inside(pts: np.ndarray, lo: np.ndarray, hi: np.ndarray, eps: float) -> np.ndarray:
    m = ((pts >= lo - eps) & (pts <= hi + eps)).all(axis=1)
    return pts[m]


def _point_tri_dist2_rows(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Row-wise squared point-to-triangle distance for ``(n, 3)`` rows."""
    ab, ac, ap = b - a, c - a, p - a
    d1 = (ab * ap).sum(1); d2 = (ac * ap).sum(1)
    bp = p - b
    d3 = (ab * bp).sum(1); d4 = (ac * bp).sum(1)
    cp = p - c
    d5 = (ab * cp).sum(1); d6 = (ac * cp).sum(1)
    vc = d1 * d4 - d3 * d2
    vb = d5 * d2 - d1 * d6
    va = d3 * d6 - d5 * d4
    denom = va + vb + vc
    with np.errstate(divide="ignore", invalid="ignore"):
        v = np.where(denom != 0, vb / denom, 0.0)
        w = np.where(denom != 0, vc / denom, 0.0)
        s_ab = np.clip(np.where(d1 - d3 != 0, d1 / (d1 - d3), 0.0), 0.0, 1.0)
        s_ac = np.clip(np.where(d2 - d6 != 0, d2 / (d2 - d6), 0.0), 0.0, 1.0)
        den_bc = (d4 - d3) + (d5 - d6)
        s_bc = np.clip(np.where(den_bc != 0, (d4 - d3) / den_bc, 0.0), 0.0, 1.0)
    inside = (va >= 0) & (vb >= 0) & (vc >= 0)
    q = a + v[:, None] * ab + w[:, None] * ac
    q = np.where(inside[:, None], q, a + s_ab[:, None] * ab)
    on_ac = (~inside) & (d2 >= 0) & (d6 <= 0)
    q = np.where(on_ac[:, None], a + s_ac[:, None] * ac, q)
    on_bc = (~inside) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0) & (vc <= 0)
    q = np.where(on_bc[:, None], b + s_bc[:, None] * (c - b), q)
    d = ((p - q) ** 2).sum(1)
    dv = np.minimum(np.minimum(((p - a) ** 2).sum(1), ((p - b) ** 2).sum(1)),
                    ((p - c) ** 2).sum(1))
    return np.minimum(d, dv)


def _narrow_rows(src: PlacedPart, dst: PlacedPart, eps: float, budget: int
                 ) -> tuple[np.ndarray, np.ndarray] | None | bool:
    """The ``(points, triangle indices)`` rows testing ``src``'s vertices
    inside ``dst``'s box against the ``dst`` triangles whose own boxes
    reach within ``eps`` of each point; ``True`` when the candidate ×
    triangle screen would exceed ``budget`` (unproved), ``None`` when
    nothing is left to test (proved apart in this direction)."""
    cand = _inside(src.pts, dst.box_min, dst.box_max, eps)
    if cand.shape[0] == 0:
        return None
    lo = cand.min(axis=0) - eps
    hi = cand.max(axis=0) + eps
    keep = np.nonzero(((dst.tri_hi >= lo) & (dst.tri_lo <= hi)).all(axis=1))[0]
    if keep.shape[0] == 0:
        return None
    if cand.shape[0] * keep.shape[0] > budget:
        return True
    tlo = dst.tri_lo[keep] - eps
    thi = dst.tri_hi[keep] + eps
    m = ((cand[:, None, :] >= tlo[None]) & (cand[:, None, :] <= thi[None])).all(axis=2)
    pi, ki = np.nonzero(m)
    if pi.shape[0] == 0:
        return None
    return cand[pi], keep[ki]


def _narrow_pass(parts: _t.Sequence[PlacedPart], pairs: _t.Sequence[tuple[int, int]],
                 eps: float, budget: int, chunk_rows: int, uf: _UnionFind
                 ) -> tuple[list[tuple[int, int]], int]:
    """Vertex-to-triangle both ways for the ``pairs`` still apart in
    ``uf``, BATCHED: the rows of many pairs are stacked and reduced in one
    numpy call (the per-pair small-array overhead was the cost: HECA
    152 k pairs); a batch's contacts are unioned before the next, so a
    pair joined transitively by an earlier batch is skipped untested (v1
    ``contact_graph``: the spanning subset).  Returns the contact edges
    found and the number of pairs left unproved."""
    e2 = eps * eps
    edges: list[tuple[int, int]] = []
    unproved = 0
    buf: list[list[np.ndarray]] = [[], [], [], [], []]
    batch: list[tuple[int, int]] = []
    rows = 0

    def flush() -> None:
        nonlocal rows
        if buf[0]:
            d = _point_tri_dist2_rows(*(np.concatenate(x) for x in buf[:4]))
            ids = np.concatenate(buf[4])
            for i in np.unique(ids[d <= e2]).tolist():
                a, b = batch[i]
                if uf.union(a, b) or parts[a].member == parts[b].member:
                    edges.append((a, b))
        for x in buf:
            x.clear()
        batch.clear()
        rows = 0

    for x, y in pairs:
        # RULINGS 2026-09-10i (1): a pair of ONE PLACEMENT is tested and
        # RECORDED even when the two are already joined transitively — the
        # spanning subset (v1's law) left the seat unable to see that two
        # components of one file TOUCH, and the across-placement cut then
        # ran along the path between them (LEMD ZNTWR c0/c4: 16 mm apart,
        # no direct edge, 2.767 m apart after the seat).
        if uf.find(x) == uf.find(y) and parts[x].member != parts[y].member:
            continue
        pa, pb = parts[x], parts[y]
        doubt = False
        idx = len(batch)
        batch.append((x, y))
        for src, dst in ((pa, pb), (pb, pa)):
            r = _narrow_rows(src, dst, eps, budget)
            if r is None:
                continue
            if r is True:
                doubt = True
                continue
            pts, ti = r
            t = dst.tris[ti]
            buf[0].append(pts); buf[1].append(dst.pts[t[:, 0]])
            buf[2].append(dst.pts[t[:, 1]]); buf[3].append(dst.pts[t[:, 2]])
            buf[4].append(np.full(pts.shape[0], idx))
            rows += pts.shape[0]
        if doubt:
            unproved += 1
            if uf.union(x, y) or pa.member == pb.member:   # merge on doubt (I-20)
                edges.append((x, y))
        if rows >= chunk_rows:
            flush()
    flush()
    return edges, unproved


def partition(members: _t.Sequence[MemberGeometry], eps: float, weld_mm: float, budget: int,
              pool_overlap_m: float, chunk_rows: int, foot_band_m: float = 1.0,
              foot_samples_max: int = 4, elevated_base_m: float | None = None,
              line_members: _t.Collection[int] = (),
              station_span_m: float = 0.0, stations_max: int = 0) -> Partition:
    """Parts, the spanning contact edges, and the pool / structure counts
    (module doc).  With ``elevated_base_m`` given (RULINGS 2026-09-09s
    (2)) an ELEVATED part's feet are dropped: only the GROUND parts carry
    feet into the plan, and ``emit/clusters`` reads that verdict straight
    off the plan."""
    parts = placed_parts(members, foot_band_m, foot_samples_max,
                         line_members, station_span_m, stations_max)
    uf = _UnionFind(len(parts))
    edges: list[tuple[int, int]] = []
    for a, b in _weld_pairs(parts, weld_mm).tolist():
        if uf.union(a, b) or parts[a].member == parts[b].member:
            edges.append((a, b))
    # 10i (1): an intra-PLACEMENT pair is never dropped for being joined
    # transitively — the seat's "one placement, one body" test reads the
    # edge list, and a spanning subset hides the touch.
    pend = [(int(a), int(b)) for a, b in _broad_pairs(parts, eps).tolist()
            if uf.find(int(a)) != uf.find(int(b))
            or parts[int(a)].member == parts[int(b)].member]
    found, unproved = _narrow_pass(parts, pend, eps, budget, chunk_rows, uf)
    edges.extend(found)
    if elevated_base_m is not None and parts:
        # THE FEET travel in the plan for the GROUND parts only (RULINGS
        # 2026-09-09s (2)): an ELEVATED part never votes and never founds
        # a seat, so its feet would be dead weight in a 152 k-part plan
        # a LINE part keeps its stations whatever its base_y: it drapes
        # on its own ground, it never votes in a body (10bb, spec §16)
        parts = [p if (p.line or p.base_y <= elevated_base_m)
                 else _dc.replace(p, feet=np.zeros((0, 3), dtype=float))
                 for p in parts]
    return Partition(tuple(parts), tuple(sorted(set(edges))),
                     _pools(parts, len(members), pool_overlap_m),
                     uf.groups() if parts else 0, len(pend), unproved)
