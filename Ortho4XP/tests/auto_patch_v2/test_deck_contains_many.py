"""Issue #1213: ``DeckPrint.contains_many`` answers EXACTLY what
``DeckPrint.contains`` answers, point for point — the batched candidate
query may change the cost, never a boolean (KMCI's placement output is
byte-identical through it).  Points are drawn inside, on, just outside
(within and beyond the 0.5 m reach) and far from a dense mesh of small
triangles plus one large one, at both reaches."""
from __future__ import annotations

import random

from auto_patch_v2.airport import bridge_family as BF


def _print(seed: int) -> BF.DeckPrint:
    rnd = random.Random(seed)
    tris = []
    for _ in range(400):
        la, lo = 39.3 + rnd.uniform(0, 0.002), -94.7 + rnd.uniform(0, 0.003)
        s = rnd.uniform(2e-6, 4e-5)
        tris.append(((la, lo), (la + s, lo + rnd.uniform(-s, s)),
                     (la + rnd.uniform(-s, s), lo + s)))
    tris.append(((39.3, -94.7), (39.302, -94.7), (39.3, -94.697)))  # large
    tris.append(((39.301, -94.699), (39.301, -94.699), (39.301, -94.699)))
    las = [q[0] for t in tris for q in t]
    los = [q[1] for t in tris for q in t]
    ys = tuple(tuple(rnd.choice((0.0, 1.0, 2.5)) for _ in range(3))
               for _ in tris)
    p = BF.DeckPrint(key="d.obj", unit=0, member=0, under_y=0.0,
                     box=(min(las), min(los), max(las), max(los)),
                     tris=tuple(tris), ys=ys)
    p.index()
    return p


def _points(p: BF.DeckPrint, seed: int):
    rnd = random.Random(seed + 1)
    pts = []
    for t in p.tris[:200]:
        for q in t:                               # vertices and near them
            for d in (0.0, 2e-6, 4.4e-6, 4.6e-6, 6e-6):
                pts.append((q[0] + rnd.choice((-1, 1)) * d,
                            q[1] + rnd.choice((-1, 1)) * d))
    for _ in range(3000):
        pts.append((39.2995 + rnd.uniform(0, 0.0035),
                    -94.7005 + rnd.uniform(0, 0.0045)))
    pts.append((10.0, 10.0))
    return pts


def test_contains_many_is_contains_point_for_point():
    for seed in (1, 2, 3):
        p = _print(seed)
        pts = _points(p, seed)
        las, los = [q[0] for q in pts], [q[1] for q in pts]
        for tol in (BF.CONTACT_M, 0.0, 2.0):
            want = [p.contains(a, b, tol) for a, b in pts]
            assert p.contains_many(las, los, tol) == want
            assert any(want) and not all(want)
            # top_at: the same value, the reach's ties broken in walk order
            tops = [p.top_at(a, b, tol) for a, b in pts]
            assert p.top_at_many(las, los, tol) == tops
            assert any(t is not None for t in tops)


def test_contains_many_empty():
    p = BF.DeckPrint(key="e", unit=0, member=0, under_y=0.0,
                     box=(0.0, 0.0, 0.0, 0.0))
    assert p.contains_many([1.0], [2.0]) == [False]
    assert p.top_at_many([1.0], [2.0]) == [None]
    assert _print(1).contains_many([], []) == []


def _full_query_partition(p: BF.DeckPrint, gap_m: float) -> list:
    """The pre-#1213 reading: ``dwithin`` from EVERY triangle."""
    import numpy as np
    import shapely
    xy = np.array([[(q[0] * p._ml, q[1] * p._mo) for q in t] for t in p.tris])
    geo = shapely.polygons(np.concatenate([xy, xy[:, :1]], axis=1))
    a, b = shapely.STRtree(geo).query(geo, predicate="dwithin", distance=gap_m)
    root = list(range(len(p.tris)))

    def find(i):
        while root[i] != i:
            i = root[i]
        return i
    for i, j in zip(a.tolist(), b.tolist()):
        ri, rj = find(i), find(j)
        if ri != rj:
            root[max(ri, rj)] = min(ri, rj)
    groups: dict = {}
    for i in range(len(p.tris)):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=lambda g: g[0])


def test_deck_components_partition_is_the_full_query():
    for seed in (1, 2, 3):
        p = _print(seed)
        # a shared-vertex strip, so the vertex chaining is exercised
        la, lo = 39.31, -94.69
        strip = [((la, lo + k * 1e-5), (la + 1e-5, lo + k * 1e-5),
                  (la, lo + (k + 1) * 1e-5)) for k in range(30)]
        # a triangle collapsed to a POINT 0.2 m off the strip: the tree's
        # prepared ``dwithin`` reads no distance from it (KMCI Trimsheet-2)
        strip.append(((la - 1.8e-6, lo),) * 3)
        p = BF.DeckPrint(key="d.obj", unit=0, member=0, under_y=0.0,
                         box=p.box, tris=p.tris + tuple(strip))
        p.index()
        for gap in (BF.CONTACT_M, 0.05, 3.0):
            want = _full_query_partition(p, gap)
            lab = BF._touch_components(p, gap)
            got: dict = {}
            for i, k in enumerate(lab):
                got.setdefault(k, []).append(i)
            assert sorted(got.values(), key=lambda g: g[0]) == want
            assert 1 < len(want) < len(p.tris)
