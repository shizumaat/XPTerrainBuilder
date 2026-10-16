"""ONE TRIANGULATION OF ONE FACE (owner RULINGS 2026-09-11x (4)).

The one shape routine three readers share, so none keeps a copy:

* ``solve/rows._face_triangles`` — the domain the cotangent Laplacian is
  assembled on (the map's own rings);
* ``constraints/foot_rows._FaceIndex`` — which triangle of a face a
  foot stands in (the PRECEDENCE VIEW's rings, which are the map's rings
  after the senior role has clipped them);
* ``O4_Qt_Preview3D_Shapes.triangulate`` — the patch editor's 3D preview
  (a patch surface's node ids).

The readers feed it different coordinates on purpose; the SHAPE question
is the same one, and it is answered here once.

Issue #752: the routine was an UNconstrained Delaunay of the ring and
hole vertices kept by triangle centroid, which on a concave face both
dropped area (a triangle whose centroid fell outside) and covered ground
outside the face (a kept triangle crossing the ring) — up to 66 % of a
face's area lost on the sweep captures.  It is now GEOS's CONSTRAINED
Delaunay, which keeps every ring edge, so the triangles cover the face
exactly.
"""
from __future__ import annotations

import typing as _t

__all__ = ["face_triangles"]

XY = tuple[float, float]


def face_triangles(xy: _t.Mapping[int, XY], ring: _t.Sequence[int],
                   holes: _t.Sequence[_t.Sequence[int]] = ()
                   ) -> list[tuple[int, int, int]]:
    """A triangulation of one face that covers it exactly: the
    constrained Delaunay triangulation (GEOS, via shapely) of the
    exterior ring minus its holes, every ring edge kept.

    ``xy`` maps a vertex id to its plan point; ``ring`` is the exterior
    ring's vertex ids and ``holes`` its interior rings'.  Returns
    ``(a, b, c)`` vertex ids, orientation unspecified.

    ONLY INPUT VERTEX IDS: a constrained triangulation of a valid polygon
    adds no Steiner point, and each triangle corner is mapped back to its
    id by its exact input coordinate; a corner that is no input vertex (a
    crossing point ``make_valid`` minted on a self-crossing ring) drops
    that triangle rather than invent an id.

    An INVALID face (a hole sharing an edge with the ring — a nested face —
    or a self-touching ring) is rebuilt as the ring minus the union of the
    holes.  Empty where there is no triangle to give (fewer than three
    distinct vertices, a degenerate ring, a polygon GEOS refuses) — never
    an exception.
    """
    import shapely
    from shapely.geometry import Polygon

    def pts(ids: _t.Sequence[int]) -> list[XY]:
        return [xy[v] for v in ids if v in xy]

    lut = {xy[v]: v for r in (ring, *holes) for v in r if v in xy}
    if len(lut) < 3:
        return []
    try:
        hole_rings = [pts(h) for h in holes if len(pts(h)) >= 3]
        poly = Polygon(pts(ring), hole_rings)
        if not poly.is_valid:
            poly = shapely.make_valid(Polygon(pts(ring)))
            if hole_rings:
                poly = poly.difference(shapely.union_all(
                    [shapely.make_valid(Polygon(h)) for h in hole_rings]))
        if poly.is_empty:
            return []
        tris = shapely.constrained_delaunay_triangles(poly)
    except (shapely.errors.GEOSException, ValueError):
        return []
    out: list[tuple[int, int, int]] = []
    for t in shapely.get_parts(tris):
        corners = [lut.get(c) for c in t.exterior.coords[:3]]
        if None not in corners and len(set(corners)) == 3:
            out.append((corners[0], corners[1], corners[2]))  # type: ignore[arg-type]
    return out
