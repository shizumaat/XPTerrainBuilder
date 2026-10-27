"""WHICH FACE, AND WHICH TRIANGLE OF IT, A POINT STANDS IN (owner RULINGS
2026-09-11x (4); moved out of ``constraints/foot_rows`` in #1214 round 7 so
``constraints/group_level`` reads the design surface at a foot the way the
foot rows do, without the foot rows' closure).

ONE STRtree over the map's face polygons -- the PRECEDENCE VIEW's rings,
the map's rings after the senior role has clipped them -- and each face
triangulated on first use by the one shape routine (``geom.face_triangles``,
GEOS's constrained Delaunay: the triangles cover the face exactly).  A
point's row is the barycentric row of the triangle it falls in: the design
surface there, linear in three vertices' heights.
"""
from __future__ import annotations

from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

from ..geom import face_triangles
from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["FaceIndex"]


class FaceIndex:
    """Point -> (face role, the triangle's barycentric row)."""

    def __init__(self, planar: PlanarMap, law: Law) -> None:
        from .precedence import view
        self.pm = planar
        vw = view(planar, law)
        polys: list[Polygon] = []
        fids: list[int] = []
        for fid, _f in planar.faces.items():
            ring = vw.rings[fid]
            if len(ring) < 3:
                continue
            poly = Polygon([vw.xy[v] for v in ring],
                           [[vw.xy[v] for v in h] for h in vw.holes[fid]
                            if len(h) >= 3])
            if not poly.is_valid:
                poly = poly.buffer(0.0)
            if poly.is_empty or not isinstance(poly, Polygon):
                continue
            polys.append(poly)
            fids.append(fid)
        self._polys = polys
        self._fids = fids
        self._at = {fid: i for i, fid in enumerate(fids)}
        self._vw = vw
        self._tree = STRtree(polys) if polys else None
        self._tris: dict[int, list[tuple[int, int, int]]] = {}

    def _face_at(self, p: tuple[float, float]) -> int | None:
        if self._tree is None:
            return None
        pt = Point(p)
        for j in self._tree.query(pt):
            if self._polys[int(j)].covers(pt):
                return self._fids[int(j)]
        return None

    def role_at(self, p: tuple[float, float]) -> str | None:
        fid = self._face_at(p)
        return None if fid is None else self.pm.faces[fid].role

    def terms_at(self, p: tuple[float, float]
                 ) -> tuple[tuple[int, float], ...] | None:
        """The barycentric row of the triangle ``p`` falls in, or
        ``None`` (outside every face, or a face that does not
        triangulate)."""
        fid = self._face_at(p)
        if fid is None:
            return None
        tris = self._tris.get(fid)
        if tris is None:
            # THE ONE TRIANGULATION (11x (4)): ``geom`` is the leaf both
            # this layer and ``solve/rows`` may import — no copy here.
            tris = face_triangles(self._vw.xy, self._vw.rings[fid],
                                  self._vw.holes[fid])
            self._tris[fid] = tris
        xy = self.pm.vertices
        for a, b, c in tris:
            w = _bary(p, xy[a].xy, xy[b].xy, xy[c].xy)
            if w is None:
                continue
            return ((a, w[0]), (b, w[1]), (c, w[2]))
        return None


#: a point this far outside a triangle in barycentric units still counts
#: as inside it — a numeric tolerance on the walk, not a law value
_BARY_EPS = 1e-9


def _bary(p: tuple[float, float], a: tuple[float, float],
          b: tuple[float, float], c: tuple[float, float]
          ) -> tuple[float, float, float] | None:
    """``p``'s barycentric weights in triangle ``abc``, or ``None`` when
    ``p`` lies outside it (or the triangle is degenerate)."""
    v0x, v0y = b[0] - a[0], b[1] - a[1]
    v1x, v1y = c[0] - a[0], c[1] - a[1]
    den = v0x * v1y - v1x * v0y
    if den == 0.0:
        return None
    px, py = p[0] - a[0], p[1] - a[1]
    wb = (px * v1y - v1x * py) / den
    wc = (v0x * py - px * v0y) / den
    wa = 1.0 - wb - wc
    if wa < -_BARY_EPS or wb < -_BARY_EPS or wc < -_BARY_EPS:
        return None
    return (wa, wb, wc)
