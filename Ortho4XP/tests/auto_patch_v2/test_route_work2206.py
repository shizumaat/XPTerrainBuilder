"""``constraints.route_work`` (#2206): the route pricing's walks read on the
work pool are the serial walks, float for float, and a chunked serial walk
is the one-call walk."""
from __future__ import annotations

import numpy as np
from auto_patch_v2.airport import pool
from auto_patch_v2.constraints import route_work as rw
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra


def _graph(n=300, e=1500, seed=2206):
    rng = np.random.default_rng(seed)
    a, b = rng.integers(0, n, e), rng.integers(0, n, e)
    m = csr_matrix((rng.uniform(1, 50, e), (a, b)), shape=(n, n))
    wb = csr_matrix((rng.uniform(0.1, 3, e), (a, b)), shape=(n, n))
    cols = {s: [np.sort(rng.choice(n, 7, replace=False)) for _ in range(2)] for s in range(n)}
    return m, wb, cols


def _plain(m, wb, cols):
    idx = sorted(cols)
    D, B = dijkstra(m, directed=True, indices=idx), dijkstra(wb, directed=True, indices=idx)
    return {s: [(D[i, c], B[i, c]) for c in cols[s]] for i, s in enumerate(idx)}


def _same(x, y):
    assert x.keys() == y.keys()
    for s in x:
        for (d0, b0), (d1, b1) in zip(x[s], y[s], strict=True):
            assert d0.tobytes() == d1.tobytes() and b0.tobytes() == b1.tobytes()


def test_serial_chunks_are_one_walk():
    m, wb, cols = _graph()
    _same(rw.walk_rows(m, wb, sorted(cols), cols, 17, workers=1), _plain(m, wb, cols))


def test_pooled_is_serial():
    m, wb, cols = _graph()
    pool.configure(None)
    try:
        got = rw.walk_rows(m, wb, sorted(cols), cols, 40, workers=2)
    finally:
        pool.configure(1)
    _same(got, _plain(m, wb, cols))
