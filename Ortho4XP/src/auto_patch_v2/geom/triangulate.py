"""ONE TRIANGULATION OF ONE FACE (owner RULINGS 2026-09-11x (4)).

Lifted verbatim from ``solve/rows._face_triangles`` — the routine the
design solve has always integrated its curvature over — with the
``PlanarMap`` taken out of it, so the two readers that may not import
each other can share the one expression:

* ``solve/rows._face_triangles`` — the domain the cotangent Laplacian is
  assembled on (the map's own rings);
* ``constraints/foot_rows._FaceIndex`` — which triangle of a face a
  foot stands in (the PRECEDENCE VIEW's rings, which are the map's rings
  after the senior role has clipped them).

The two feed it different coordinates on purpose; the SHAPE question is
the same one, and it is answered here once.
"""
from __future__ import annotations

import typing as _t

__all__ = ["face_triangles"]

XY = tuple[float, float]


def face_triangles(xy: _t.Mapping[int, XY], ring: _t.Sequence[int],
                   holes: _t.Sequence[_t.Sequence[int]]
                   ) -> list[tuple[int, int, int]]:
    """A triangulation of one face: the Delaunay triangulation of its
    ring and hole vertices, keeping the triangles whose CENTROID lies
    inside the face — so a concave face and a face with holes
    triangulate correctly.

    ``xy`` maps a vertex id to its plan point; ``ring`` is the exterior
    ring's vertex ids and ``holes`` its interior rings'.  Returns
    ``(a, b, c)`` vertex ids.  Empty where there is no triangle to give
    (fewer than three distinct vertices, a degenerate ring, a hull the
    triangulator refuses) — never an exception.
    """
    import numpy as np
    from scipy.spatial import Delaunay, QhullError
    from shapely.geometry import Point, Polygon
    from shapely.prepared import prep

    ids = list(dict.fromkeys([*ring, *(v for h in holes for v in h)]))
    ids = [v for v in ids if v in xy]
    if len(ids) < 3:
        return []
    pts = np.array([xy[v] for v in ids], float)
    try:
        poly = Polygon([xy[v] for v in ring if v in xy],
                       [[xy[v] for v in h if v in xy] for h in holes
                        if len([v for v in h if v in xy]) >= 3])
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            return []
        tri = Delaunay(pts)
    except (QhullError, ValueError):
        return []
    inside = prep(poly)
    out: list[tuple[int, int, int]] = []
    for s in tri.simplices:
        c = pts[s].mean(axis=0)
        if inside.contains(Point(c[0], c[1])):
            out.append((ids[s[0]], ids[s[1]], ids[s[2]]))
    return out
