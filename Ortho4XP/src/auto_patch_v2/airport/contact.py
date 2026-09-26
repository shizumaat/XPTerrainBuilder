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

Pass 3, THE AUTHORED-FRAME ABUTMENT (owner RULINGS 2026-09-10ay; spec
§17): inside ONE anchor plane (a unit — every placement of it carries
the same ``anchor_z + agl``, so the authored relation between them is
exact) two parts whose plan boxes come within the identity spacing on
both axes, meet over ``abutment_extent_min_m`` of one of them, and whose
authored z intervals lie within ``[rebake] plate_gap_max_m`` ABUT even
though they carry no ε-contact edge — LEMD's T4 departures viaduct, authored 2.24 m
under the terminal kerb it runs along.  An abutment binds NO body; it
GROUPS the two bodies, which then take the senior body's delta.

Pure geometry over numpy; no I/O, no environment.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..model.frame import XY
from . import obj8 as _obj8

__all__ = ["PlacedPart", "Partition", "partition", "BaseIndex", "Extension",
           "base_index", "extend"]


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
    #: §16g (7) (1) THE FOOTPRINT POLYGON (owner RULINGS 2026-09-14c item
    #: 1, attributed 14g): ``(k, 2)`` frame ``(x, z)`` — the CONVEX HULL
    #: of this component's placed vertices in plan.  It is computed HERE,
    #: where the geometry is already placed, so the unit law costs the
    #: plan stage no second OBJ8 parse.  ``None`` for a part whose hull
    #: degenerates (fewer than three distinct points), which reads as its
    #: box.
    #: §16g (7) (1) THE FOOTPRINT OUTLINE (owner RULINGS 2026-09-14c item
    #: 1, amended 14j): ONE RING PER BLOB of the union of this
    #: component's projected triangles, each ``(k, 2)`` frame ``(x, z)``
    #: and each simplified OUTWARD.  Computed HERE, where the geometry is
    #: already placed, so the unit law costs the plan stage no second
    #: OBJ8 parse.  Empty where the outline degenerates — the caller then
    #: reads the part by its box.
    rings: tuple = _dc.field(default=(), repr=False, compare=False)
    #: THE SCATTER PIECE (spec §B.2 (4), issue #29): no ring, one foot,
    #: excluded from the weld / broad / narrow / abutment passes; its only
    #: contact edges are the PIECE edges inside its own member
    scatter: bool = False

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
    #: THE CROSS-PLACEMENT ABUTMENTS (owner RULINGS 2026-09-10ay; spec
    #: §17): ``(pid, pid)`` pairs of ONE SHARED ANCHOR PLANE that ABUT in
    #: the AUTHORED frame — plan boxes meeting, authored z within
    #: ``[rebake] plate_gap_max_m`` — but carry no ε-contact edge.  They
    #: bind no body; they GROUP the bodies they belong to (``emit/
    #: clusters.py``), which then take the senior body's delta.
    abutments: tuple[tuple[int, int], ...] = ()


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


#: §16g (7) (1): how many vertices a footprint ring may carry into the
#: plan.  A hull past this is decimated by every other vertex until it
#: fits — the ring is a CONTACT shape read at ``footprint_touch_m``, not
#: a rendering, and OTHH carries 137,908 of them.
FOOTPRINT_RING_MAX = 16

#: §16g (7) (1): the OUTWARD simplification tolerance, metres — a tenth
#: of ``footprint_touch_m`` at its shipped 0.5 m, so the growth a ring
#: takes is small against the contact it is read at.
OUTLINE_SIMPLIFY_M = 0.05

#: A component past this many plan triangles takes its convex hull
#: instead: the union is the honest shape but a clutter mesh's is not
#: worth its seconds, and the hull is outward.
OUTLINE_TRIS_MAX = 4000


def _outward(poly, tol: float, cap: int):
    """``poly`` simplified to at most ``cap`` vertices and GUARANTEED to
    CONTAIN it (owner RULINGS 2026-09-14j: "never inward — a simplified
    ring must contain the true footprint").

    Buffer OUT by the tolerance, then simplify by it: the simplify error
    is bounded by ``tol`` and the buffer has already paid it, so the
    result covers the original.  The tolerance doubles until the ring
    fits, and the last resort is the convex hull, which contains
    everything by construction."""
    import shapely
    t = tol
    for _ in range(12):
        q = poly.buffer(t, join_style=2).simplify(t)
        if not q.is_valid:
            q = q.buffer(0)
        if not q.is_empty and q.covers(poly) and len(q.exterior.coords) <= cap + 1:
            return q
        t *= 2.0
    return shapely.convex_hull(poly)


def plan_hull(pts: "np.ndarray | None",
              tris: "np.ndarray | None" = None) -> "list[np.ndarray]":
    """§16g (7) (1) THE FOOTPRINT POLYGON: the component's TRUE OUTLINE in
    plan — the UNION of its projected triangles — as one ring per
    connected blob, ``(k, 2)`` frame ``(x, z)``.

    ROUND 4 (owner RULINGS 2026-09-14j).  Round 3 used the CONVEX HULL
    and said so; the measurement refuted it against the bar.  The hull
    killed the deck hop (1,489 HECA bodies at 96.20 -> 0) but it BRIDGES
    A CONCAVE NOTCH, so a courtyard terminal's hull still swallowed the
    bodies standing in it: 20 units whose pads span more than a metre
    survived, the worst 581 bodies over 24 pads spanning 29.56 m.  The
    outline is what §16g (7) (1) asked for first.

    Every simplification is OUTWARD (:func:`_outward`): a ring that does
    not contain the true footprint could SPLIT a unit that genuinely
    abuts, and a unit wrongly split is a body seated on ground that is
    not its own.  Growing a ring can only keep a chain that the true
    outline would break, which is the safe direction and is reported.

    A component whose union comes apart into disjoint blobs returns ONE
    RING PER BLOB — ``rings_touch`` reads a body as a SET of rings
    already, so nothing downstream needs to know.  Holes are dropped
    (outward again).  ``[]`` where the outline degenerates, and the
    caller then reads the part by its box, as it always did."""
    if pts is None or len(pts) < 3:
        return []
    if tris is None or len(tris) == 0:
        return _hull_ring(pts)
    import shapely
    xz = np.column_stack((pts[:, 0], pts[:, 2]))
    t = xz[tris]                                   # (m, 3, 2)
    # a triangle with no plan area contributes nothing to a footprint
    ar = np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1])
                - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
    t = t[ar > 1e-6]
    if len(t) == 0:
        return _hull_ring(pts)
    if len(t) > OUTLINE_TRIS_MAX:
        return _hull_ring(pts)
    try:
        rings = np.concatenate([t, t[:, :1, :]], axis=1)
        u = shapely.union_all(shapely.polygons(rings))
        if u.is_empty:
            return _hull_ring(pts)
        if not u.is_valid:
            u = u.buffer(0)
        out: list = []
        for g in (u.geoms if u.geom_type.startswith("Multi") else [u]):
            if g.is_empty or g.area <= 0.0:
                continue
            q = _outward(g, OUTLINE_SIMPLIFY_M, FOOTPRINT_RING_MAX)
            r = np.asarray(q.exterior.coords[:-1], dtype=float)
            if len(r) >= 3:
                out.append(r)
        return out or _hull_ring(pts)
    except Exception:
        return _hull_ring(pts)


def _hull_ring(pts: np.ndarray) -> "list[np.ndarray]":
    """The component's plan CONVEX HULL as a single ring — round 3's
    reading, kept as the fallback for a component the outline cannot be
    taken over (a degenerate or enormous one).  It CONTAINS the true
    footprint, so the fallback is outward like everything else."""
    if pts is None or len(pts) < 3:
        return []
    xz = np.unique(np.round(np.column_stack((pts[:, 0], pts[:, 2])), 3),
                   axis=0)
    if len(xz) < 3:
        return []
    order = np.lexsort((xz[:, 1], xz[:, 0]))
    p = xz[order]

    def half(seq) -> list:
        out: list = []
        for q in seq:
            while len(out) >= 2:
                a, b = out[-2], out[-1]
                if ((b[0] - a[0]) * (q[1] - a[1])
                        - (b[1] - a[1]) * (q[0] - a[0])) > 0.0:
                    break
                out.pop()
            out.append(q)
        return out

    ring = np.asarray(half(p)[:-1] + half(p[::-1])[:-1], dtype=float)
    if len(ring) < 3:
        return []
    while len(ring) > FOOTPRINT_RING_MAX:
        ring = ring[::2]
    return [ring]


def placed_parts(members: _t.Sequence[MemberGeometry], foot_band_m: float = 1.0,
                 foot_samples_max: int = 4,
                 line_members: _t.Collection[int] = (),
                 station_span_m: float = 0.0, stations_max: int = 0,
                 scatter_members: _t.Collection[int] = ()) -> list[PlacedPart]:
    """Every genuine component of every member as a placed part, in
    member order then component order (deterministic pids).  A member in
    ``line_members`` is a LINE OBJECT (RULINGS 2026-09-10bb): its parts
    are flagged and their feet are widened to the DRAPE STATIONS — one
    per ``station_span_m`` of the part's plan length, capped at
    ``stations_max`` — so the segment seat reads the design surface
    along the whole fence and not at four points of a 5 km run."""
    parts: list[PlacedPart] = []
    lines = set(line_members)
    scat = set(scatter_members)
    for mi, (o, geom, comps) in enumerate(members):
        is_line = mi in lines
        is_scat = mi in scat and not is_line
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
            # §B.2 (4): a scatter piece seats by ONE foot and carries no
            # ring (§16g reads it by its box)
            k_max = 1 if is_scat else foot_samples_max
            if is_line and station_span_m > 0.0 and stations_max > 0:
                span = math.hypot(float(pts[:, 0].max() - pts[:, 0].min()),
                                  float(pts[:, 2].max() - pts[:, 2].min()))
                k_max = max(foot_samples_max,
                            min(stations_max, int(math.ceil(span / station_span_m))))
            parts.append(PlacedPart(len(parts), mi, ci, pts, lt, float(c.min_y), total,
                                    (cx, cy), pts.min(axis=0), pts.max(axis=0),
                                    np.minimum(np.minimum(a, b), d), np.maximum(np.maximum(a, b), d),
                                    _feet(pts, float(c.min_y), o.anchor_z + o.agl_m,
                                          foot_band_m, k_max), is_line,
                                    () if is_scat else plan_hull(pts, lt),
                                    is_scat))
    return parts


def _piece_edges(parts: _t.Sequence[PlacedPart], touch_m: float) -> list[tuple[int, int]]:
    """THE PIECE EDGES (spec §B.2 (4)): inside ONE member, two scatter
    parts whose PLAN boxes come within ``touch_m`` (``[placement]
    footprint_touch_m`` — §16g's number) are one PIECE — a palm's trunk
    and fronds, a person's sub-meshes, a cart and its wheels.  Each piece
    is stated as a spanning CHAIN in pid order, so ``bodies_of_plan``
    reads it as one body.  No edge ever crosses members (10bb's sentence
    for the line class: it never forms a rigid body with what it
    touches).  One ``STRtree`` ``dwithin`` query per member."""
    import shapely
    by_member: dict[int, list[PlacedPart]] = {}
    for p in parts:
        if p.scatter:
            by_member.setdefault(p.member, []).append(p)
    edges: list[tuple[int, int]] = []
    for _mi, ps in sorted(by_member.items()):
        if len(ps) < 2:
            continue
        lo = np.array([p.box_min for p in ps])
        hi = np.array([p.box_max for p in ps])
        boxes = shapely.box(lo[:, 0], lo[:, 2], hi[:, 0], hi[:, 2])
        tree = shapely.STRtree(boxes)
        a, b = tree.query(boxes, predicate="dwithin", distance=touch_m)
        keep = a < b
        uf = _UnionFind(len(ps))
        for i, j in zip(a[keep].tolist(), b[keep].tolist()):
            uf.union(i, j)
        groups: dict[int, list[int]] = {}
        for i in range(len(ps)):
            groups.setdefault(uf.find(i), []).append(ps[i].pid)
        for g in groups.values():
            g.sort()
            edges.extend(zip(g[:-1], g[1:]))
    return edges


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
    """The points of ``pts`` inside the ``eps``-grown box.

    AXIS BY AXIS, IN PLACE (lane ``v2cost2``, RULINGS 2026-09-14q item 2):
    ``((pts >= lo - eps) & (pts <= hi + eps)).all(axis=1)`` builds two
    ``(n, 3)`` boolean temporaries and then reduces them — at OTHH this
    runs 2.78 M times and the ``ufunc.reduce`` behind ``.all`` was 58 s of
    the partition.  Six ``(n,)`` comparisons anded in place give the
    SAME booleans with no reduction and no ``(n, 3)`` temporary."""
    x = pts[:, 0]
    m = x >= lo[0] - eps
    np.logical_and(m, x <= hi[0] + eps, out=m)
    y = pts[:, 1]
    np.logical_and(m, y >= lo[1] - eps, out=m)
    np.logical_and(m, y <= hi[1] + eps, out=m)
    z = pts[:, 2]
    np.logical_and(m, z >= lo[2] - eps, out=m)
    np.logical_and(m, z <= hi[2] + eps, out=m)
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
    # the same axis-by-axis screen as :func:`_inside` (14q item 2): no
    # (n, 3) temporary, no ``.all`` reduction, the same booleans
    thi_all, tlo_all = dst.tri_hi, dst.tri_lo
    kmask = thi_all[:, 0] >= lo[0]
    np.logical_and(kmask, tlo_all[:, 0] <= hi[0], out=kmask)
    np.logical_and(kmask, thi_all[:, 1] >= lo[1], out=kmask)
    np.logical_and(kmask, tlo_all[:, 1] <= hi[1], out=kmask)
    np.logical_and(kmask, thi_all[:, 2] >= lo[2], out=kmask)
    np.logical_and(kmask, tlo_all[:, 2] <= hi[2], out=kmask)
    keep = np.nonzero(kmask)[0]
    if keep.shape[0] == 0:
        return None
    if cand.shape[0] * keep.shape[0] > budget:
        return True
    tlo = dst.tri_lo[keep] - eps
    thi = dst.tri_hi[keep] + eps
    # the point x triangle screen, likewise per axis: the (n, k, 3)
    # pair of boolean temporaries and their ``.all(axis=2)`` were the
    # heaviest reduction in the pass
    c0 = cand[:, 0][:, None]
    m = c0 >= tlo[None, :, 0]
    np.logical_and(m, c0 <= thi[None, :, 0], out=m)
    c1 = cand[:, 1][:, None]
    np.logical_and(m, c1 >= tlo[None, :, 1], out=m)
    np.logical_and(m, c1 <= thi[None, :, 1], out=m)
    c2 = cand[:, 2][:, None]
    np.logical_and(m, c2 >= tlo[None, :, 2], out=m)
    np.logical_and(m, c2 <= thi[None, :, 2], out=m)
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


def _abutment_pairs(parts: _t.Sequence[PlacedPart], anchor_of_member: _t.Sequence[int],
                    gap_m: float, extent_min_m: float, spacing_m: float,
                    uf: "_UnionFind") -> list[tuple[int, int]]:
    """THE AUTHORED-FRAME ABUTMENT (owner RULINGS 2026-09-10ay; spec §17).

    Two parts ABUT when their plan boxes come within ``spacing_m``
    (``emit.identity.min_distinct_spacing_m`` — two points closer than it
    are the same point to every emit law) on BOTH plan axes, they meet
    along at least ``extent_min_m`` of one of them (so a corner graze is
    not an abutment), and their authored z intervals lie within ``gap_m``
    of each other — a viaduct deck's kerb edge meeting the terminal's
    kerb 2.2 m above it, a pier standing under its own deck, the next
    deck slab end-to-end with this one.

    THE FRAME.  The test is the AUTHORED one, so it is confined to parts
    whose members share ONE ANCHOR PLANE (``anchor_of_member``, the
    plan's unit key): inside a unit every placement carries the same
    ``anchor_z + agl``, so the placed y HERE differs from the authored y
    by one constant and the authored relation is exact.  Across units the
    anchor ground differs by the DEM — that is what separated LEMD's T4
    viaduct from its terminal in the first place — and nothing about the
    authored relation is known, so no pair is proposed.

    A pair already in one contact component is skipped: it is one body
    already, and grouping it would be a no-op.  The pairs bind no body —
    ``emit/clusters.py`` groups the BODIES they fall in."""
    if gap_m <= 0.0 or extent_min_m <= 0.0 or len(parts) < 2:
        return []
    cand = _broad_pairs(parts, gap_m)
    if cand.shape[0] == 0:
        return []
    lo = np.array([p.box_min for p in parts])
    hi = np.array([p.box_max for p in parts])
    anc = np.array([anchor_of_member[p.member] for p in parts])
    line = np.array([p.line for p in parts])
    a, b = cand[:, 0], cand[:, 1]
    # the signed plan OVERLAP on each axis (negative = a gap) and the
    # authored z gap (negative = the intervals overlap)
    ox = np.minimum(hi[a, 0], hi[b, 0]) - np.maximum(lo[a, 0], lo[b, 0])
    oz = np.minimum(hi[a, 2], hi[b, 2]) - np.maximum(lo[a, 2], lo[b, 2])
    gy = np.maximum(lo[a, 1] - hi[b, 1], lo[b, 1] - hi[a, 1])
    m = ((anc[a] == anc[b]) & ~line[a] & ~line[b]
         & (np.minimum(ox, oz) >= -spacing_m)
         & (np.maximum(ox, oz) >= extent_min_m)
         & (gy <= gap_m))
    if not m.any():
        return []
    pid = np.array([p.pid for p in parts])
    return [(int(pid[x]), int(pid[y])) for x, y in cand[m].tolist()
            if uf.find(int(pid[x])) != uf.find(int(pid[y]))]


def partition(members: _t.Sequence[MemberGeometry], eps: float, weld_mm: float, budget: int,
              pool_overlap_m: float, chunk_rows: int, foot_band_m: float = 1.0,
              foot_samples_max: int = 4, elevated_base_m: float | None = None,
              line_members: _t.Collection[int] = (),
              station_span_m: float = 0.0, stations_max: int = 0,
              anchor_of_member: _t.Sequence[int] = (),
              abutment_gap_m: float = 0.0,
              abutment_extent_min_m: float = 0.0,
              abutment_spacing_m: float = 0.0,
              scatter_members: _t.Collection[int] = (),
              piece_touch_m: float = 0.0) -> Partition:
    """Parts, the spanning contact edges, and the pool / structure counts
    (module doc).  With ``elevated_base_m`` given (RULINGS 2026-09-09s
    (2)) an ELEVATED part's feet are dropped: only the GROUND parts carry
    feet into the plan, and ``emit/clusters`` reads that verdict straight
    off the plan."""
    parts = placed_parts(members, foot_band_m, foot_samples_max,
                         line_members, station_span_m, stations_max,
                         scatter_members)
    uf = _UnionFind(len(parts))
    edges: list[tuple[int, int]] = []
    # §B.2 (4) (issue #29): SCATTER pieces never reach the weld, the
    # broad / narrow ε-contact pass or the abutments — ``solid`` is the
    # rest, pid-addressed exactly as before (with no scatter member it IS
    # ``parts``, so every other airport partitions as it did)
    solid = [p for p in parts if not p.scatter]
    sid = np.array([p.pid for p in solid], dtype=np.int64)
    for a, b in _weld_pairs(solid, weld_mm).tolist():
        if uf.union(a, b) or parts[a].member == parts[b].member:
            edges.append((a, b))
    # 10i (1): an intra-PLACEMENT pair is never dropped for being joined
    # transitively — the seat's "one placement, one body" test reads the
    # edge list, and a spanning subset hides the touch.
    bp = _broad_pairs(solid, eps)
    if len(solid) != len(parts) and bp.shape[0]:
        bp = sid[bp]
    pend = [(int(a), int(b)) for a, b in bp.tolist()
            if uf.find(int(a)) != uf.find(int(b))
            or parts[int(a)].member == parts[int(b)].member]
    found, unproved = _narrow_pass(parts, pend, eps, budget, chunk_rows, uf)
    edges.extend(found)
    # THE PIECE EDGES (§B.2 (4)): the scatter pieces' only contacts
    if len(solid) != len(parts):
        for a, b in _piece_edges(parts, piece_touch_m):
            uf.union(a, b)
            edges.append((a, b))
    # THE ABUTMENTS (owner RULINGS 2026-09-10ay; spec §17), read off the
    # SETTLED contact union-find so a pair already in one body is skipped.
    abut = _abutment_pairs(solid, anchor_of_member or [0] * len(members),
                           abutment_gap_m, abutment_extent_min_m,
                           abutment_spacing_m, uf) if anchor_of_member else []
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
                     uf.groups() if parts else 0, len(pend), unproved,
                     tuple(sorted({(min(a, b), max(a, b)) for a, b in abut})))


# ── THE INCREMENTAL EXTENSION (owner RULINGS 2026-09-11l (1); spec §11a) ──


@_dc.dataclass(frozen=True)
class BaseIndex:
    """What :func:`extend` needs to know about a partition it did not
    keep the geometry of: every part's 3-D box, which member and
    component it is, its line verdict and which contact COMPONENT it
    already belongs to.

    The full ``PlacedPart`` set of a real pack is the whole OBJ geometry
    placed (OTHH: 152 k parts), so it is NOT retained across a build.
    The boxes are (152 k × 48 B × 2 ≈ 15 MB) and they are enough to find
    the handful of neighbours an added member can touch; those
    neighbours' geometry is re-placed on demand from the resource cache,
    which is the same parse the load partition read."""

    box_lo: np.ndarray          # (n_parts, 3)
    box_hi: np.ndarray          # (n_parts, 3)
    member: np.ndarray          # (n_parts,) member index
    comp: np.ndarray            # (n_parts,) component index in the file
    line: np.ndarray            # (n_parts,) bool
    root: np.ndarray            # (n_parts,) contact-component id
    #: (n_parts,) bool — a SCATTER piece is never an extension's
    #: neighbour (§B.6 row 8); ``None`` on an index built before #29
    scatter: _t.Any = None


def base_index(part: Partition) -> BaseIndex:
    """``part``'s :class:`BaseIndex` — built while its geometry is still
    in hand, at the end of the LOAD partition."""
    n = len(part.parts)
    lo = np.zeros((n, 3)); hi = np.zeros((n, 3))
    mem = np.zeros(n, dtype=np.int64); cmp_ = np.zeros(n, dtype=np.int64)
    ln = np.zeros(n, dtype=bool)
    sc = np.zeros(n, dtype=bool)
    uf = _UnionFind(n)
    for a, b in part.contacts:
        uf.union(int(a), int(b))
    for p in part.parts:
        lo[p.pid] = p.box_min
        hi[p.pid] = p.box_max
        mem[p.pid] = p.member
        cmp_[p.pid] = p.comp
        ln[p.pid] = bool(p.line)
        sc[p.pid] = bool(p.scatter)
    root = np.array([uf.find(i) for i in range(n)], dtype=np.int64)
    return BaseIndex(lo, hi, mem, cmp_, ln, root, sc)


@_dc.dataclass(frozen=True)
class Extension:
    """What :func:`extend` adds: the new parts (global pids), the edges
    and abutments they bring, and the recomputed structure count."""

    parts: tuple[PlacedPart, ...]
    contacts: tuple[tuple[int, int], ...]
    abutments: tuple[tuple[int, int], ...]
    structures: int
    pairs_tested: int
    pairs_unproved: int
    neighbours: int


def extend(base: BaseIndex, base_members: _t.Sequence[MemberGeometry],
           new_members: _t.Sequence[MemberGeometry],
           eps: float, weld_mm: float, budget: int, chunk_rows: int,
           foot_band_m: float = 1.0, foot_samples_max: int = 4,
           elevated_base_m: float | None = None,
           line_members: _t.Collection[int] = (),
           station_span_m: float = 0.0, stations_max: int = 0,
           anchor_of_member: _t.Sequence[int] = (),
           abutment_gap_m: float = 0.0, abutment_extent_min_m: float = 0.0,
           abutment_spacing_m: float = 0.0) -> Extension:
    """Partition ``new_members`` INTO an existing reading (module doc).

    The new members' parts and feet are computed exactly as
    :func:`partition` computes them; their ε-contacts and abutments are
    sought ONLY against the parts whose boxes come within ``eps`` of one
    of them — a spatial query over ``base``'s boxes, not a repartition.
    Every base–base edge already stands, so a pair of two base parts is
    never re-tested; the union-find is seeded with ``base.root`` so a new
    pair already joined THROUGH the base is skipped exactly as the whole
    pass would skip it.

    ``anchor_of_member`` covers base members first, then the new ones
    (the caller's own numbering).  ``line_members`` indexes ``new_members``.
    """
    n_base_parts = int(base.box_lo.shape[0])
    n_base_members = len(base_members)
    fresh = placed_parts(new_members, foot_band_m, foot_samples_max,
                         line_members, station_span_m, stations_max)
    if not fresh:
        return Extension((), (), (), int(np.unique(base.root).size) if n_base_parts else 0,
                         0, 0, 0)
    # ── the neighbourhood: base parts within ε of a new part's box ──────
    flo = np.array([p.box_min for p in fresh])
    fhi = np.array([p.box_max for p in fresh])
    near: set[int] = set()
    if n_base_parts:
        for i in range(flo.shape[0]):
            m = ((base.box_lo - eps <= fhi[i]) & (flo[i] - eps <= base.box_hi)).all(axis=1)
            if getattr(base, "scatter", None) is not None:
                m &= ~base.scatter
            near.update(np.flatnonzero(m).tolist())
    # ── re-place just those members' geometry from the resource cache ──
    by_member: dict[int, list[int]] = {}
    for pid in sorted(near):
        by_member.setdefault(int(base.member[pid]), []).append(pid)
    nb: list[PlacedPart] = []
    nb_global: list[int] = []
    nb_member: list[int] = []
    for mi, pids in by_member.items():
        got = {p.comp: p for p in placed_parts([base_members[mi]], foot_band_m, 1)}
        for pid in pids:
            p = got.get(int(base.comp[pid]))
            if p is None:
                continue
            nb.append(_dc.replace(p, pid=len(nb), member=mi,
                                  line=bool(base.line[pid]),
                                  feet=np.zeros((0, 3), dtype=float)))
            nb_global.append(pid)
            nb_member.append(mi)
    # local pids 0..L-1: the neighbours first, then the new parts
    local: list[PlacedPart] = []
    local_member: list[int] = []          # local member index per local part
    member_ix: dict[int, int] = {}
    for p, mi in zip(nb, nb_member):
        li = member_ix.setdefault(mi, len(member_ix))
        local.append(_dc.replace(p, pid=len(local), member=li))
        local_member.append(li)
    n_nb = len(local)
    for p in fresh:
        li = member_ix.setdefault(n_base_members + p.member, len(member_ix))
        local.append(_dc.replace(p, pid=len(local), member=li))
        local_member.append(li)
    globals_of = list(nb_global) + [n_base_parts + p.pid for p in fresh]
    is_new = np.array([i >= n_nb for i in range(len(local))])
    # the union-find is seeded with the base's own components so a pair
    # already joined THROUGH the base is skipped, as the whole pass skips it
    uf = _UnionFind(len(local))
    seed: dict[int, int] = {}
    for li in range(n_nb):
        r = int(base.root[globals_of[li]])
        if r in seed:
            uf.union(seed[r], li)
        else:
            seed[r] = li
    edges: list[tuple[int, int]] = []

    def _keep(a: int, b: int) -> bool:
        return bool(is_new[a] or is_new[b])

    for a, b in _weld_pairs(local, weld_mm).tolist():
        a, b = int(a), int(b)
        if not _keep(a, b):
            continue
        if uf.union(a, b) or local[a].member == local[b].member:
            edges.append((a, b))
    pend = [(int(a), int(b)) for a, b in _broad_pairs(local, eps).tolist()
            if _keep(int(a), int(b))
            and (uf.find(int(a)) != uf.find(int(b))
                 or local[int(a)].member == local[int(b)].member)]
    found, unproved = _narrow_pass(local, pend, eps, budget, chunk_rows, uf)
    edges.extend(found)
    abut: list[tuple[int, int]] = []
    if anchor_of_member:
        anc_local = [0] * len(member_ix)
        for gi, li in member_ix.items():
            anc_local[li] = int(anchor_of_member[gi])
        abut = [(a, b) for a, b in
                _abutment_pairs(local, anc_local, abutment_gap_m,
                                abutment_extent_min_m, abutment_spacing_m, uf)
                if _keep(a, b)]
    out_parts = [_dc.replace(p, pid=n_base_parts + p.pid,
                             member=n_base_members + p.member) for p in fresh]
    if elevated_base_m is not None:
        out_parts = [p if (p.line or p.base_y <= elevated_base_m)
                     else _dc.replace(p, feet=np.zeros((0, 3), dtype=float))
                     for p in out_parts]
    # the structure count over base ∪ new
    total = n_base_parts + len(out_parts)
    uf2 = _UnionFind(total)
    for i in range(n_base_parts):
        uf2.union(i, int(base.root[i]))
    for a, b in edges:
        uf2.union(globals_of[a], globals_of[b])
    return Extension(tuple(out_parts),
                     tuple(sorted({(min(globals_of[a], globals_of[b]),
                                    max(globals_of[a], globals_of[b]))
                                   for a, b in edges})),
                     tuple(sorted({(min(globals_of[a], globals_of[b]),
                                    max(globals_of[a], globals_of[b]))
                                   for a, b in abut})),
                     uf2.groups(), len(pend), unproved, n_nb)
