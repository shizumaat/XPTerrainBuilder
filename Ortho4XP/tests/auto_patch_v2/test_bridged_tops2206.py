"""#2206 step 4: ``airport/bridged_ground._tops`` box-tests its points in
blocks against every triangle at once -- bit for bit the per-point loop it
replaced (below), blocks smaller than the point count included."""
from __future__ import annotations

import numpy as np
from auto_patch_v2.airport import bridged_ground as BG


def _loop(tris, x, z):
    out = np.full(x.shape, np.nan)
    p0 = tris[:, 0]
    e1, e2 = tris[:, 1] - p0, tris[:, 2] - p0
    den = e1[:, 0] * e2[:, 2] - e2[:, 0] * e1[:, 2]
    live = np.abs(den) > 1e-9
    p0, e1, e2, den = p0[live], e1[live], e2[live], den[live]
    lo = tris[live].min(axis=1)
    hi = tris[live].max(axis=1)
    for k in range(x.shape[0]):
        px, pz = float(x[k]), float(z[k])
        m = (lo[:, 0] <= px) & (px <= hi[:, 0]) & (lo[:, 2] <= pz) & (pz <= hi[:, 2])
        if not m.any():
            continue
        qx, qz = px - p0[m, 0], pz - p0[m, 2]
        u = (qx * e2[m, 2] - e2[m, 0] * qz) / den[m]
        v = (e1[m, 0] * qz - qx * e1[m, 2]) / den[m]
        ins = (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1.0 + 1e-6)
        if ins.any():
            y = p0[m, 1] + u * e1[m, 1] + v * e2[m, 1]
            out[k] = float(np.max(y[ins]))
    return out


def test_the_block_tops_are_the_loop_bit_for_bit(monkeypatch):
    rnd = np.random.default_rng(2206)
    for trial in range(60):
        n = int(rnd.integers(0, 80))
        tris = rnd.uniform(-20.0, 20.0, (n, 3, 3))
        if trial % 3 == 0 and n:                 # shared corners, flat faces
            tris = np.round(tris / 5.0) * 5.0
        m = int(rnd.integers(0, 120))
        x, z = rnd.uniform(-25.0, 25.0, m), rnd.uniform(-25.0, 25.0, m)
        if trial % 2 and m:
            x[: m // 2] = np.round(x[: m // 2] / 5.0) * 5.0
            z[: m // 2] = np.round(z[: m // 2] / 5.0) * 5.0
        monkeypatch.setattr(BG, "_PAIRS", int(rnd.choice([1, 50, 1 << 21])))
        assert BG._tops(tris, x, z).tobytes() == _loop(tris, x, z).tobytes()


def test_far_triangles_and_unfinite_points_change_nothing():
    # the points' box pre-select (#2206): triangles far from a narrow strip
    # of points and NaN points beside finite ones read as the loop reads them
    rnd = np.random.default_rng(22062)
    for _trial in range(30):
        tris = rnd.uniform(-200.0, 200.0, (400, 3, 3))
        x = np.linspace(-10.0, 10.0, 50) + rnd.uniform(-1, 1)
        z = 0.3 * x + rnd.uniform(-1, 1)
        x[::7] = np.nan
        assert BG._tops(tris, x, z).tobytes() == _loop(tris, x, z).tobytes()
    nan = np.full(4, np.nan)
    assert np.isnan(BG._tops(rnd.uniform(-5, 5, (9, 3, 3)), nan, nan)).all()
