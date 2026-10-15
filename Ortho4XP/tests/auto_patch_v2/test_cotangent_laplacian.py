"""Twin of ``solve/rows._cotangent_laplacian`` (issue #762): the bending
operator is a property of the triangles' GEOMETRY, never of the order a
triangle lists its vertices in or the vertex a face ring starts at.

The third edge ``(c, a)`` read its opposite angle at ``b`` with the wrong
sign, so an acute triangle lost that edge's weight and which edge was lost
followed the vertex order (CYXY: a rotation alone moved 539 nodes, worst
0.42 m).
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.geom import face_triangles
from auto_patch_v2.solve.rows import _cotangent_laplacian


class _Map:
    """The slice of ``PlanarMap`` the Laplacian reads: ``vertices[v].xy``."""

    class _V:
        __slots__ = ("xy",)

        def __init__(self, xy):
            self.xy = xy

    def __init__(self, xy):
        self.vertices = {v: _Map._V(p) for v, p in xy.items()}


def _weights(xy, tris):
    L, _area = _cotangent_laplacian(_Map(xy), tris, len(xy))
    L = L.tocoo()
    return {(int(i), int(j)): -float(v) for i, j, v in zip(L.row, L.col, L.data)
            if i < j and v != 0.0}


def test_acute_triangle_weights_are_half_the_opposite_cotangents():
    """(0,0) (2,0) (1,1.5): cot at vertex 2 = 1.25 / 3, at 0 and 1 = 2 / 3;
    every edge carries half the cotangent of the angle opposite it, in
    every vertex order."""
    xy = {0: (0.0, 0.0), 1: (2.0, 0.0), 2: (1.0, 1.5)}
    want = {(0, 1): 1.25 / 6.0, (0, 2): 1.0 / 3.0, (1, 2): 1.0 / 3.0}
    for tri in [(0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1), (2, 1, 0), (1, 0, 2)]:
        got = _weights(xy, [tri])
        assert got.keys() == want.keys(), tri
        for e, w in want.items():
            assert got[e] == pytest.approx(w, rel=1e-12), (tri, e)


def test_obtuse_triangle_clamps_only_the_edge_opposite_the_obtuse_angle():
    """(0,0) (4,0) (2,0.5): the angle at vertex 2 is obtuse, so edge 0-1
    carries no weight (the PSD clamp); the angles at 0 and 1 have cot 4,
    so edges 1-2 and 0-2 carry 2 each."""
    xy = {0: (0.0, 0.0), 1: (4.0, 0.0), 2: (2.0, 0.5)}
    for tri in [(0, 1, 2), (1, 2, 0), (2, 0, 1), (0, 2, 1)]:
        got = _weights(xy, [tri])
        assert set(got) == {(0, 2), (1, 2)}, tri
        assert got[(0, 2)] == pytest.approx(2.0, rel=1e-12)
        assert got[(1, 2)] == pytest.approx(2.0, rel=1e-12)


#: A concave face with a hole, points in general position (no four
#: cocircular), so its constrained triangulation is unique whatever vertex
#: the rings start at.
_RING = [(0.0, 0.0), (41.3, 2.1), (47.9, 30.4), (29.2, 22.7), (18.6, 44.9),
         (-3.7, 35.2)]
_HOLE = [(8.1, 9.3), (17.4, 8.2), (14.9, 19.6)]


def test_the_operator_is_identical_for_every_vertex_order_and_ring_start():
    xy = {k: p for k, p in enumerate(_RING)}
    xy.update({100 + k: p for k, p in enumerate(_HOLE)})
    ids = sorted(xy)
    pos = {v: k for k, v in enumerate(ids)}
    dense = {pos[v]: xy[v] for v in ids}
    ring = list(range(len(_RING)))
    hole = [100 + k for k in range(len(_HOLE))]

    def matrix(r, h, rot):
        tris = [tuple(pos[v] for v in t[rot:] + t[:rot])
                for t in face_triangles(xy, r, [h])]
        L, area = _cotangent_laplacian(_Map(dense), tris, len(dense))
        return L.toarray(), area

    L0, a0 = matrix(ring, hole, 0)
    assert np.count_nonzero(L0) > 0
    for s in range(len(ring)):
        for t in range(len(hole)):
            for rot in range(3):
                L, a = matrix(ring[s:] + ring[:s], hole[t:] + hole[:t], rot)
                np.testing.assert_allclose(L, L0, rtol=1e-12, atol=1e-12)
                np.testing.assert_allclose(a, a0, rtol=1e-12, atol=1e-12)
