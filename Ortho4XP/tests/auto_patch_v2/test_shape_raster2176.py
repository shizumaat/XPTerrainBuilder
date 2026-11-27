"""#2176: ``shape_class.rasterise`` rasters its triangles in batches; every
cell's top and lowest are bit for bit the one-triangle-at-a-time fill's."""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.geom import shape_class as sc


def _each(p, max_cells, min_step=0.5):
    """The reference: the same grid, filled one triangle at a time."""
    real = sc._raster_batched
    try:
        sc._raster_batched = sc._raster_each
        return sc.rasterise(p, max_cells, min_step)
    finally:
        sc._raster_batched = real


def _tris(rng, n, dtype, span=80.0):
    a = rng.uniform(-span, span, (n, 1, 3))
    p = a + rng.normal(0.0, rng.uniform(0.2, 12.0, (n, 1, 1)), (n, 3, 3))
    p[: n // 10, 2] = p[: n // 10, 1]                      # degenerate: d == 0
    p[n // 10: n // 5, :, 2] = -0.0                        # signed zero heights
    return p.astype(dtype)


@pytest.mark.parametrize("dtype", [np.float64, np.float32])
@pytest.mark.parametrize("max_cells,min_step", [(160000, 0.5), (4000, 0.5), (10 ** 9, 0.25)])
def test_batched_raster_is_the_triangle_loop(dtype, max_cells, min_step, monkeypatch):
    rng = np.random.default_rng(2176)
    p = _tris(rng, 600, dtype)
    monkeypatch.setattr(sc, "_BATCH_CELLS", 5000)          # many batches, one-triangle ones too
    got, want = sc.rasterise(p, max_cells, min_step), _each(p, max_cells, min_step)
    assert (got.e0, got.n0, got.step) == (want.e0, want.n0, want.step)
    for a, b in ((got.top, want.top), (got.low, want.low)):
        assert a.shape == b.shape
        assert a.tobytes() == b.tobytes()                   # nan, -0.0 and all


def test_non_finite_input_takes_the_loop():
    p = _tris(np.random.default_rng(1), 50, np.float64)
    p[3, 1, 2] = np.nan
    got, want = sc.rasterise(p, 4000), _each(p, 4000)
    assert got.top.tobytes() == want.top.tobytes()
    assert got.low.tobytes() == want.low.tobytes()
