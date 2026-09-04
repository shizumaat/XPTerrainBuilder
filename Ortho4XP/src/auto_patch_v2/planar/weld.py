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
PROJECTED onto it, (2) ``shapely.snap`` then snaps its vertices to
senior vertices within the tolerance and INSERTS senior vertices lying
within the tolerance of its ring segments, so a senior vertex a hair
off a junior edge (the owner's site) becomes a vertex of both rings and
the noding that follows sees ONE chain.  Only value-carrying,
non-rigid cells of the SAME side weld: a pad never welds by proximity
(09-01i / 04u: groundside keeps its set-back from every pad), and an
airside cell never welds to a groundside one (the stand-off terraces —
memory ``groundside-terrace-law``).
"""
from __future__ import annotations

import dataclasses as _dc

import shapely
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree

from ..classify.roles import Cell
from ..law import Law
from ..law.tables import authority_rank, is_rigid_role, is_value_role

__all__ = ["WeldStats", "weld_cells"]


@_dc.dataclass
class WeldStats:
    """What the weld pass did."""

    tolerance_m: float = 0.0
    cells_welded: int = 0
    vertices_projected: int = 0
    vertices_inserted: int = 0
    cells_refused: int = 0     # a weld that would have collapsed the cell


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
        q, moved, inserted = _weld_one(p, unary_union(refs), tol)
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


def _weld_one(poly: Polygon, ref, tol: float
              ) -> tuple[Polygon | None, int, int]:
    """``poly`` welded to the boundary set ``ref``: ``(polygon, vertices
    projected, vertices inserted)``; ``None`` when the weld would leave
    no valid polygon (the cell is narrower than the tolerance)."""
    n_before = len(poly.exterior.coords) + sum(len(h.coords) for h in poly.interiors)
    ext, moved = _project(poly.exterior.coords, ref, tol)
    holes = []
    for h in poly.interiors:
        ring, m = _project(h.coords, ref, tol)
        holes.append(ring)
        moved += m
    try:
        q = Polygon(ext, [h for h in holes if len(h) >= 3])
    except (ValueError, TypeError):
        return None, 0, 0
    q = shapely.snap(q, ref, tol)
    if not q.is_valid:
        q = q.buffer(0)
    if q.is_empty:
        return None, 0, 0
    if q.geom_type != "Polygon":
        parts = [g for g in getattr(q, "geoms", ()) if g.geom_type == "Polygon"]
        if not parts:
            return None, 0, 0
        q = max(parts, key=lambda g: g.area)
    if q.area < 0.5 * poly.area:
        return None, 0, 0
    n_after = len(q.exterior.coords) + sum(len(h.coords) for h in q.interiors)
    return q, moved, max(0, n_after - n_before)


def _project(coords, ref, tol: float) -> tuple[list[tuple[float, float]], int]:
    """Ring coordinates with every vertex within ``tol`` of ``ref`` (and
    not already on it) moved to its nearest point on ``ref``."""
    out: list[tuple[float, float]] = []
    moved = 0
    pts = list(coords)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    for x, y in pts:
        pt = Point(x, y)
        d = ref.distance(pt)
        if 1e-9 < d <= tol:
            q = nearest_points(pt, ref)[1]
            out.append((float(q.x), float(q.y)))
            moved += 1
        else:
            out.append((float(x), float(y)))
    return out, moved
