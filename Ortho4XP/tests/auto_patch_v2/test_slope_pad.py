"""Owner RULINGS 2026-10-19w: a walled cluster under ``cluster_pad_min_m2``
whose seat would float more than ``[placement] slope_pad_float_m`` over the
ground under its outline gets a pad (``geom/slope_pad``)."""
from __future__ import annotations

import types

from auto_patch_v2.geom import cluster_outlines
from auto_patch_v2.geom.slope_pad import seat_float_m, slope_witness
from auto_patch_v2.law import Law
from shapely.geometry import box


def _cl(cid, x0, x1, area=400.0):
    ring = ((0.0, x0), (0.0, x1), (20.0, x1), (20.0, x0))   # (lat, lon) = (y, x)
    return types.SimpleNamespace(id=cid, rings=(ring,), area_m2=area, floors=(0.0,),
                                 boxes=(), bodies=1, footed=1, walled=1, bridges=())


def _ident(lo, la):
    return float(lo), float(la)


def test_the_float_is_the_median_less_the_lowest_ground():
    assert seat_float_m(box(0, 0, 20, 20), lambda x, y: 100.0) == 0.0
    # 0.1 m per metre east: ground 100..102 over 20 m, median ~101
    f = seat_float_m(box(0, 0, 20, 20), lambda x, y: 100.0 + 0.1 * x)
    assert 0.9 < f < 1.1


def test_a_small_floating_cluster_is_padded_a_flat_one_is_not():
    flat, slope = _cl("flat", 0.0, 20.0), _cl("slope", 100.0, 120.0)

    def dem(x, y):
        return 100.0 + (0.1 * (x - 100.0) if x >= 100.0 else 0.0)
    got, counts = cluster_outlines([flat, slope], _ident, 0.0, min_m2=5000.0,
                                   slope=(lambda u: seat_float_m(u, dem), 0.5))
    assert [cid for cid, _c, _g in got] == ["slope"]
    assert counts["slope_padded"] == 1 and counts["under_min_m2"] == 1
    # disarmed: neither is padded, and the count reads as before
    got0, c0 = cluster_outlines([flat, slope], _ident, 0.0, min_m2=5000.0)
    assert got0 == [] and c0["under_min_m2"] == 2


def test_the_witness_reads_the_law_and_the_dem():
    law = Law.for_airport("KASE")
    assert float(law.tables.structures.placement.slope_pad_float_m) == 0.5
    ap = types.SimpleNamespace(dem=types.SimpleNamespace(z=lambda x, y: 1.0))
    fn, t = slope_witness(ap, law)
    assert t == 0.5 and fn(box(0, 0, 10, 10)) == 0.0
    assert slope_witness(types.SimpleNamespace(dem=None), law) is None


def test_the_array_read_is_the_point_read():
    """#2206: ``z_many`` reads every sample in one call and gives the float
    the per-point reads give, bit for bit; the witness hands it on."""
    import numpy as np
    from shapely.geometry import Polygon

    def z(x, y):
        return 100.0 + 0.137 * x - 0.0291 * y + 1e-3 * x * y
    calls = []

    def many(xs, ys):
        calls.append(len(xs))
        return np.array([z(x, y) for x, y in zip(xs, ys)])
    u = Polygon([(0, 0), (37.3, 2.1), (41.9, 29.7), (12.2, 33.3), (3.1, 17.7)])
    assert seat_float_m(u, z, many) == seat_float_m(u, z) > 0.0 and len(calls) == 1
    law = Law.for_airport("KASE")
    ap = types.SimpleNamespace(dem=types.SimpleNamespace(z=z, z_many=many))
    w = slope_witness(ap, law)
    assert w.z_many is many and w[0](u) == seat_float_m(u, z)
