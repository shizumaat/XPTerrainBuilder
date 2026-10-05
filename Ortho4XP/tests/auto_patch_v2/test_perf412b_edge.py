"""Lane ``perf412b`` twin, R4 (issue #412): ``planar/terrain_edge.
_segment_ends`` — the segment ends of a seed, read with one
``get_coordinates`` per ring — is the array the per-vertex ``.coords`` reads
built, the nearest-segment index over it is the same index, and ``_outward``
returns the same vectors.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
import shapely
import shapely.affinity
from shapely.geometry import (GeometryCollection, LineString, MultiPolygon, Point,
                              Polygon)
from shapely.strtree import STRtree

from auto_patch_v2.planar import terrain_edge as TE


# ── R4: the terrain edge's segment ends ──────────────────────────────────

def _segments_before(geom) -> list[LineString]:
    """``terrain_edge._segments`` as it stood before the lane."""
    segs: list[LineString] = []
    for g in getattr(geom, "geoms", [geom]):
        if g.is_empty:
            continue
        rings = [g.exterior, *g.interiors] if g.geom_type == "Polygon" else [g]
        for ring in rings:
            cs = list(ring.coords)
            segs.extend(LineString([cs[i], cs[i + 1]]) for i in range(len(cs) - 1))
    return segs


def _ends_before(geom) -> np.ndarray:
    """The ``ab`` array ``_outward`` built from them."""
    return np.asarray([[s.coords[0], s.coords[1]] for s in _segments_before(geom)],
                      dtype=float)


def _seeds() -> list:
    rng = np.random.default_rng(412)
    blob = Polygon([(float(60 * math.cos(t) * (1 + 0.3 * math.sin(5 * t))),
                     float(40 * math.sin(t) * (1 + 0.2 * math.cos(3 * t))))
                    for t in np.linspace(0.0, 2 * math.pi, 97)[:-1]])
    holed = Polygon([(0, 0), (300, 0), (300, 200), (0, 200)],
                    [[(40, 40), (60, 40), (60, 160), (40, 160)],
                     [(120.5, 80.25), (170, 80), (170, 130), (120, 130)]])
    walk = LineString(np.cumsum(rng.normal(0.0, 7.0, size=(40, 2)), axis=0))
    return [blob, holed, MultiPolygon([blob, shapely.affinity.translate(holed, 400, 30)]),
            walk, blob.buffer(3.3).difference(blob.buffer(-7.1)),
            GeometryCollection([holed, walk, Point(5, 5), Polygon()])]


@pytest.mark.parametrize("k", range(6))
def test_segment_ends_are_the_per_vertex_reads(k):
    seed = _seeds()[k]
    before = _ends_before(seed)
    after = TE._segment_ends(seed)
    assert after.shape == before.shape and after.dtype == before.dtype
    assert np.array_equal(after, before)


@pytest.mark.parametrize("k", range(6))
def test_outward_is_unchanged(k):
    seed = _seeds()[k]
    rng = np.random.default_rng(k)
    minx, miny, maxx, maxy = seed.bounds
    px = rng.uniform(minx - 50, maxx + 50, 500)
    py = rng.uniform(miny - 50, maxy + 50, 500)
    # the nearest-segment index over the old segment objects …
    segs = _segments_before(seed)
    idx = np.asarray(STRtree(segs).nearest(shapely.points(px, py)), dtype=int)
    new_idx = np.asarray(STRtree(shapely.linestrings(TE._segment_ends(seed)))
                         .nearest(shapely.points(px, py)), dtype=int)
    assert np.array_equal(idx, new_idx)
    # … and the arithmetic downstream of it, on the old array
    ab = _ends_before(seed)
    a, b = ab[idx, 0, :], ab[idx, 1, :]
    d = b - a
    L2 = (d ** 2).sum(axis=1)
    p = np.stack([px, py], axis=1)
    t = np.where(L2 > 0.0, ((p - a) * d).sum(axis=1) / np.where(L2 > 0.0, L2, 1.0), 0.0)
    u = p - (a + np.clip(t, 0.0, 1.0)[:, None] * d)
    n = np.hypot(u[:, 0], u[:, 1])
    ok = n > 1.0e-9
    ux, uy = TE._outward(px, py, seed)
    assert np.array_equal(ux, np.where(ok, u[:, 0] / np.where(ok, n, 1.0), 0.0))
    assert np.array_equal(uy, np.where(ok, u[:, 1] / np.where(ok, n, 1.0), 0.0))


def test_a_seed_with_no_segment_points_nowhere():
    for seed in (Point(1, 2), Polygon(), GeometryCollection()):
        assert TE._segment_ends(seed).shape == (0, 2, 2)
        ux, uy = TE._outward(np.array([0.0, 1.0]), np.array([0.0, 1.0]), seed)
        assert not ux.any() and not uy.any()
