"""THE CENTRELINE OF A RIBBON: the longest path through a polygon's medial
axis (#2065 ``airport/bridge_witness``: a curved ramp plate's own long axis,
which its minimum rotated rectangle does not follow — OTHH's Bridge_03 loop
fills 0.12 of its 252 x 129 m rectangle).

The medial axis is read as the Voronoi edges of the outline, sampled every
``step``, that lie inside the polygon; its DIAMETER (the longest of the
shortest paths, two Dijkstra sweeps) is the centreline.  Along the ribbon it
holds the middle; at each end it runs into a corner of the outline (within
half the width) — a straight rectangle's is its long axis with a corner
branch at each end.
"""
from __future__ import annotations

import heapq

import shapely
from shapely.geometry import LineString, Polygon

__all__ = ["medial_directions", "ribbon_centreline"]

XY = tuple[float, float]


def _graph(poly: Polygon, step: float) -> dict[XY, list[tuple[XY, float]]]:
    """The medial-axis graph: Voronoi edges of the sampled outline inside
    ``poly``, nodes keyed to the millimetre."""
    pts = shapely.get_coordinates(shapely.segmentize(poly.exterior, step))
    edges = shapely.voronoi_polygons(shapely.multipoints(pts), only_edges=True)
    inner = poly.buffer(-1e-6)
    adj: dict[XY, list[tuple[XY, float]]] = {}
    for e in getattr(edges, "geoms", [edges]):
        if not inner.contains(e):
            continue
        (ax, ay), (bx, by) = e.coords[0], e.coords[-1]
        a, b = (round(ax, 3), round(ay, 3)), (round(bx, 3), round(by, 3))
        if a != b:
            adj.setdefault(a, []).append((b, e.length))
            adj.setdefault(b, []).append((a, e.length))
    return adj


def _farthest(adj: dict, start: XY) -> tuple[XY, dict[XY, XY]]:
    """The node farthest from ``start`` along the graph, and the
    shortest-path tree back to it."""
    dist: dict[XY, float] = {start: 0.0}
    prev: dict[XY, XY] = {}
    heap = [(0.0, start)]
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist[n]:
            continue
        for m, w in adj[n]:
            if d + w < dist.get(m, float("inf")):
                dist[m], prev[m] = d + w, n
                heapq.heappush(heap, (d + w, m))
    return max(dist, key=dist.__getitem__), prev


def ribbon_centreline(poly: Polygon, step: float = 2.0) -> "LineString | None":
    """``poly``'s centreline (module doc), or ``None`` with no medial axis."""
    if poly.is_empty or poly.geom_type != "Polygon":
        return None
    adj = _graph(poly, step)
    if not adj:
        return None
    start = next(iter(adj))
    a, _p = _farthest(adj, start)
    b, prev = _farthest(adj, a)
    path: list[XY] = [b]
    while path[-1] != a:
        path.append(prev[path[-1]])
    return LineString(path) if len(path) > 1 else None




def medial_directions(poly: Polygon, step: float = 2.0
                      ) -> list[tuple[XY, XY, XY]]:
    """Every edge of ``poly``'s medial-axis graph as ``(a, b, unit)``: the
    LOCAL direction of a ribbon that branches (#2283: a lot's ring road
    and the road leaving it, where one centreline cannot answer every
    branch).  Empty with no medial axis."""
    if poly.is_empty or poly.geom_type != "Polygon":
        return []
    out: list[tuple[XY, XY, XY]] = []
    seen: set[tuple[XY, XY]] = set()
    for a, nbrs in _graph(poly, step).items():
        for b, length in nbrs:
            if (b, a) in seen or length <= 0.0:
                continue
            seen.add((a, b))
            out.append((a, b, ((b[0] - a[0]) / length, (b[1] - a[1]) / length)))
    return out
