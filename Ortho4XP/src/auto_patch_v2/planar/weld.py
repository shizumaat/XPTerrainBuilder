"""THE SLIVER WELD (RULINGS 2026-09-04u; the HECA near-coincident rim of
04s is the same class): two pavement cells whose boundaries lie within
``law.emit.identity.weld_spacing_m`` of each other WELD at the planar
build — they share the edge / the vertices — so no sliver of unowned
ground (a face narrower than the identity spacing the mesh drapes as a
cliff: CYXY cross_connector 101 / junction 211, 0.47 m) can exist
between pavements.

Cells are welded in SENIORITY order (``precedence.authority.order``,
then larger first): a senior cell keeps its geometry, a junior cell is
adjusted against the boundaries of the seniors already placed — (1)
each of its ring vertices within the tolerance of a senior boundary is
moved onto it (to the senior's own vertex when one is within the
tolerance, else to the nearest point of the senior's edge), (2) senior
vertices lying within the tolerance of its ring segments are INSERTED
into the ring, so a senior vertex a hair off a junior edge (the owner's
site) becomes a vertex of both rings and the noding that follows sees
ONE chain.  A vertex the junior already SHARES with any other cell (a
pad it welds to, a neighbour it is noded with) is an identity and never
moves.  Only value-carrying, non-rigid cells of the SAME side weld: a
pad never welds by proximity (09-01i / 04u: groundside keeps its
set-back from every pad), and an airside cell never welds to a
groundside one (the stand-off terraces — memory
``groundside-terrace-law``).
"""
from __future__ import annotations

import dataclasses as _dc

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree

from ..classify.roles import Cell
from ..law import Law
from ..law.tables import authority_rank, is_rigid_role, is_value_role

__all__ = ["WeldStats", "weld_cells"]

#: Convergence guard of the per-cell weld (project + insert repeated until
#: the ring is unchanged): a bound on iterations, never a law value.
MAX_PASSES = 6


@_dc.dataclass
class WeldStats:
    """What the weld pass did."""

    tolerance_m: float = 0.0
    cells_welded: int = 0
    vertices_projected: int = 0
    vertices_inserted: int = 0
    cells_refused: int = 0     # a weld that would have collapsed the cell
    passes_max: int = 0        # the most passes one cell took to converge


def weld_cells(cells: tuple[Cell, ...], law: Law
               ) -> tuple[tuple[Cell, ...], WeldStats]:
    """``cells`` with every pavement cell welded to the seniors within
    the tolerance; ids and order preserved."""
    tol = law.tables.emit.identity.weld_spacing_m
    stats = WeldStats(tolerance_m=tol)
    if tol <= 0.0 or not cells:
        return cells, stats
    eligible = [i for i, c in enumerate(cells)
                if is_value_role(law, c.role) and not is_rigid_role(law, c.role)
                and len(c.ring) >= 3]
    if len(eligible) < 2:
        return cells, stats
    polys = {i: Polygon(cells[i].ring, [h for h in cells[i].holes if len(h) >= 3])
             for i in eligible}
    order = sorted(eligible, key=lambda i: (authority_rank(law, cells[i].role),
                                            -polys[i].area, i))
    tree = STRtree([polys[i] for i in order])
    # every OTHER cell's boundary (pads, structures, the other side): a
    # vertex on one of them is a shared identity and is frozen
    others = [Polygon(c.ring, [h for h in c.holes if len(h) >= 3]).boundary
              for k, c in enumerate(cells) if k not in polys and len(c.ring) >= 3]
    other_tree = STRtree(others) if others else None
    current: dict[int, Polygon] = {}
    out = list(cells)
    for i in order:
        p = polys[i]
        near = [order[int(j)] for j in tree.query(p.buffer(2.0 * tol),
                                                  predicate="intersects")]
        refs = [current[j].boundary for j in near
                if j != i and j in current and cells[j].side == cells[i].side]
        if not refs:
            current[i] = p
            continue
        frozen = [others[int(j)] for j in other_tree.query(
            p.buffer(tol), predicate="intersects")] if other_tree is not None else []
        q, moved, inserted, passes = _weld_one(p, unary_union(refs), tol,
                                               unary_union(frozen) if frozen else None)
        stats.passes_max = max(stats.passes_max, passes)
        if q is None:
            stats.cells_refused += 1
            current[i] = p
            continue
        current[i] = q
        if moved or inserted:
            stats.cells_welded += 1
            stats.vertices_projected += moved
            stats.vertices_inserted += inserted
            out[i] = _dc.replace(
                cells[i], ring=tuple(q.exterior.coords)[:-1],
                holes=tuple(tuple(h.coords)[:-1] for h in q.interiors))
    return tuple(out), stats


def _weld_one(poly: Polygon, ref, tol: float, frozen=None
              ) -> tuple[Polygon | None, int, int, int]:
    """``poly`` welded to the boundary set ``ref``: ``(polygon, vertices
    moved, vertices inserted, passes)``; ``None`` when the weld would leave
    no valid polygon (the cell is narrower than the tolerance).  Vertices
    on ``frozen`` (another cell's boundary) never move."""
    rpts = [Point(c) for g in getattr(ref, "geoms", [ref]) for c in g.coords]
    rtree = STRtree(rpts) if rpts else None
    ext = list(poly.exterior.coords)
    holes = [list(h.coords) for h in poly.interiors]
    moved = inserted = 0
    # TO A FIXED POINT: every projection or insertion bends the ring, and a
    # senior vertex that was a hair OUTSIDE the tolerance of the old edge
    # can lie inside it of the new one (HECA pav81 / pav129 2026-09-05: the
    # corner welded 0.9 m onto pav131, one pav129 vertex inserted, and the
    # next pav129 vertex sat 0.88 m off the bent edge — un-welded by the
    # single pass, a 0.4-0.9 m sliver of graded strip and 14 rim steps)
    for _pass in range(MAX_PASSES):
        ext, m = _project(ext, ref, rtree, rpts, tol, frozen)
        hs = []
        for h in holes:
            ring, mh = _project(h, ref, rtree, rpts, tol, frozen)
            hs.append(ring)
            m += mh
        n_before = len(ext) + sum(len(h) for h in hs)
        ext = _insert(ext, rtree, rpts, tol)
        hs = [_insert(h, rtree, rpts, tol) for h in hs]
        ins = len(ext) + sum(len(h) for h in hs) - n_before
        holes = hs
        moved += m
        inserted += ins
        if m == 0 and ins == 0:
            break
    passes = _pass + 1
    try:
        q = Polygon(ext, [h for h in holes if len(h) >= 3])
    except (ValueError, TypeError):
        return None, 0, 0, passes
    if not q.is_valid:
        q = q.buffer(0)
    if q.is_empty:
        return None, 0, 0, passes
    if q.geom_type != "Polygon":
        parts = [g for g in getattr(q, "geoms", ()) if g.geom_type == "Polygon"]
        if not parts:
            return None, 0, 0, passes
        q = max(parts, key=lambda g: g.area)
    if q.area < 0.5 * poly.area:
        return None, 0, 0, passes
    return q, moved, max(0, inserted), passes


def _project(coords, ref, rtree, rpts, tol: float, frozen
             ) -> tuple[list[tuple[float, float]], int]:
    """Ring coordinates with every vertex within ``tol`` of ``ref`` (not
    on it, not on ``frozen``) moved onto ``ref``: to its nearest vertex
    when one is within ``tol``, else to the nearest point of its edge."""
    out: list[tuple[float, float]] = []
    moved = 0
    pts = list(coords)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    for x, y in pts:
        pt = Point(x, y)
        d = ref.distance(pt)
        if d <= 1e-9 or d > tol or (frozen is not None and frozen.distance(pt) <= 1e-9):
            out.append((float(x), float(y)))
            continue
        q = None
        if rtree is not None:
            cand = [rpts[int(j)] for j in rtree.query(pt.buffer(tol), predicate="intersects")]
            cand = [c for c in cand if c.distance(pt) <= tol]
            if cand:
                q = min(cand, key=lambda c: c.distance(pt))
        if q is None:
            q = nearest_points(pt, ref)[1]
        out.append((float(q.x), float(q.y)))
        moved += 1
    return out, moved


def _insert(ring: list[tuple[float, float]], rtree, rpts, tol: float
            ) -> list[tuple[float, float]]:
    """``ring`` with every ``ref`` vertex within ``tol`` of one of its
    segments (and not already a vertex) inserted into that segment, in
    order along it — and the sub-segments an insertion makes examined
    again (a worklist per segment): inserting a vertex bends the
    segment toward the senior boundary, and the next senior vertex along
    it is often inside the tolerance of the bent piece though it was
    outside of the straight one.  Every ref vertex enters at most once,
    so the worklist terminates."""
    if rtree is None or len(ring) < 3:
        return ring
    out: list[tuple[float, float]] = []
    n = len(ring)
    present = {(float(x), float(y)) for x, y in ring}   # already a vertex: never twice

    def between(a, b) -> list[tuple[float, float]]:
        """The chain of vertices to insert strictly between ``a`` and ``b``."""
        seg = LineString([a, b])
        if seg.length <= 1e-9:
            return []
        found: list[tuple[float, tuple[float, float]]] = []
        for j in rtree.query(seg.buffer(tol), predicate="intersects"):
            c = rpts[int(j)]
            d = seg.distance(c)
            if d > tol or d <= 1e-9:
                continue                      # off the horizon, or already ON
                                              # the segment (the noding sees it)
            t = seg.project(c)
            if t <= 1e-9 or t >= seg.length - 1e-9:
                continue                      # an endpoint (or beyond)
            xy = (float(c.x), float(c.y))
            if xy in present:
                continue
            found.append((t, xy))
        if not found:
            return []
        chain: list[tuple[float, float]] = []
        for _t, xy in sorted(found):
            if xy not in present:
                chain.append(xy)
                present.add(xy)
        # the bent pieces, examined again
        pts = [a, *chain, b]
        full: list[tuple[float, float]] = []
        for u, v in zip(pts, pts[1:]):
            full.extend(between(u, v))
            full.append(v)
        return full[:-1]

    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        out.append(a)
        out.extend(between(a, b))
    return out
