"""``underside_seat._pad_beside`` with its pads projected once per pads
object (#2206): the same ref as the per-call projection it replaced, on
random pads and points (the old spelling is kept here as the reference)."""
from __future__ import annotations

import numpy as np
import shapely
from auto_patch_v2.airport import anchor_rule as ar
from auto_patch_v2.airport import underside_seat as us
from shapely.geometry import Polygon


def _old(e, n, pads, to_xy, reach_m):
    refs, polys = [], []
    x0, x1, y0, y1 = e.min() - reach_m, e.max() + reach_m, n.min() - reach_m, n.max() + reach_m
    for p in pads:
        xy = [to_xy(lo, la) for la, lo in p.ring]
        xs, ys = [q[0] for q in xy], [q[1] for q in xy]
        if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1:
            continue
        g = Polygon(xy).buffer(0.0)
        if not g.is_empty:
            refs.append(str(p.ref))
            polys.append(g)
    if not polys:
        return None
    near, dist = shapely.STRtree(polys).query_nearest(
        shapely.points(e, n), max_distance=reach_m, return_distance=True, all_matches=False)
    if not len(dist):
        return None
    hits: dict[str, int] = {}
    for k in near[1]:
        hits[refs[int(k)]] = hits.get(refs[int(k)], 0) + 1
    return max(sorted(hits), key=lambda r: hits[r])


def _to_xy(lo, la):
    return (lo * 1e5, la * 1e5)


def test_projected_once_same_answer():
    rng = np.random.default_rng(2206)
    pads = []
    for i in range(60):
        x, y = rng.uniform(0, 500, 2)
        w, h = rng.uniform(5, 40, 2)
        ring = tuple((yy * 1e-5, xx * 1e-5) for xx, yy in
                     ((x, y), (x + w, y), (x + w, y + h), (x, y + h)))
        pads.append(ar.PadRing(f"p{i % 23}", ring, (0.0,) * 4))
    pads.append(ar.PadRing("flat", ((0.0, 0.0), (0.0, 1e-4), (0.0, 2e-4)), (0.0,) * 3))
    pads = tuple(pads)
    for _ in range(200):
        c = rng.uniform(0, 500, 2)
        e, n = c[0] + rng.uniform(-30, 30, 12), c[1] + rng.uniform(-30, 30, 12)
        reach = float(rng.uniform(0.5, 6.0))
        assert us._pad_beside(e, n, pads, _to_xy, reach) == _old(e, n, pads, _to_xy, reach)
    assert us._BESIDE["pads"] is pads
