"""WHERE TWO MESHES MEET: does any vertex of one come within a gap of a
triangle of the other, in 3D (owner RULINGS 2026-11-20l: the ``OBJECT_MSL``
sets of one anchor that meet are one rigid frame; ``airport/msl_feet``).

A vertex-to-vertex test misses two pieces that meet face to vertex (a sky
bridge's end wall against a terminal's long facade: KDFW's sets meet at
0.00-0.04 m face gaps where their nearest vertices are 0.6-1.1 m apart), so
the distance is to the triangle.  Candidates come from an STRtree over the
triangles' plan boxes; the exact distance is the closest point on each
candidate triangle (its interior projection, else its nearest edge).
"""
from __future__ import annotations

import numpy as np

__all__ = ["Soup", "meshes_meet"]

#: candidate pairs judged per batch (bounds the memory of one query)
_CHUNK = 20000


def _point_triangle_distance(p: np.ndarray, tris: np.ndarray) -> np.ndarray:
    """``(n,)`` 3D distance from each point ``p[k]`` (``(n, 3)``) to its
    triangle ``tris[k]`` (``(n, 3, 3)``).  A degenerate triangle is read by
    its edges."""
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    ab, ac, ap = b - a, c - a, p - a
    n = np.cross(ab, ac)
    nn = (n * n).sum(1)
    ok = nn > 1e-12
    safe = np.where(ok, nn, 1.0)
    u = (np.cross(ap, ac) * n).sum(1) / safe
    w = (np.cross(ab, ap) * n).sum(1) / safe
    inside = ok & (u >= 0.0) & (w >= 0.0) & (u + w <= 1.0)
    plane = np.abs((ap * n).sum(1)) / np.sqrt(safe)
    edge = np.minimum(np.minimum(_segment(p, a, b), _segment(p, b, c)),
                      _segment(p, a, c))
    return np.where(inside, plane, edge)


def _segment(p: np.ndarray, s0: np.ndarray, s1: np.ndarray) -> np.ndarray:
    d = s1 - s0
    dd = (d * d).sum(1)
    t = np.clip(((p - s0) * d).sum(1) / np.where(dd > 0.0, dd, 1.0), 0.0, 1.0)
    return np.linalg.norm(p - (s0 + d * t[:, None]), axis=1)


class Soup:
    """A triangle soup (``(n, 3, 3)``) with its plan index and its unique
    vertices built once, for a soup judged against many others."""

    def __init__(self, tris: np.ndarray) -> None:
        self.tris = tris
        v = tris.reshape(-1, 3)
        self.lo = v.min(0) if v.shape[0] else np.zeros(3)
        self.hi = v.max(0) if v.shape[0] else np.zeros(3)
        self._tree = None
        self._points = None

    @property
    def tree(self):
        if self._tree is None:
            import shapely
            lo, hi = self.tris.min(axis=1), self.tris.max(axis=1)
            self._tree = shapely.STRtree(
                shapely.box(lo[:, 0], lo[:, 2], hi[:, 0], hi[:, 2]))
        return self._tree

    @property
    def points(self) -> np.ndarray:
        if self._points is None:
            self._points = np.unique(self.tris.reshape(-1, 3), axis=0)
        return self._points


def _one_way(points: np.ndarray, soup: Soup, gap_m: float) -> bool:
    """Any of ``points`` within ``gap_m`` of any triangle of ``soup`` (the
    plan axes are OBJ8's x and z: columns 0 and 2)."""
    import shapely
    for start in range(0, points.shape[0], _CHUNK):
        chunk = points[start:start + _CHUNK]
        pi, ti = soup.tree.query(shapely.points(chunk[:, 0], chunk[:, 2]),
                                 predicate="dwithin", distance=gap_m)
        for s in range(0, pi.shape[0], _CHUNK):
            k, t = pi[s:s + _CHUNK], ti[s:s + _CHUNK]
            if (_point_triangle_distance(chunk[k], soup.tris[t]) <= gap_m).any():
                return True
    return False


def meshes_meet(a: "Soup | np.ndarray", b: "Soup | np.ndarray", gap_m: float) -> bool:
    """Whether two triangle soups (one frame) come within ``gap_m`` of each
    other: a vertex of either within ``gap_m`` of a triangle of the other
    (two faces crossing with every vertex clear are not read -- a pack's
    pieces meet at their edges and ends)."""
    a = a if isinstance(a, Soup) else Soup(a)
    b = b if isinstance(b, Soup) else Soup(b)
    if not a.tris.shape[0] or not b.tris.shape[0]:
        return False
    if ((a.lo - gap_m > b.hi) | (b.lo - gap_m > a.hi)).any():
        return False
    return _one_way(a.points, b, gap_m) or _one_way(b.points, a, gap_m)
