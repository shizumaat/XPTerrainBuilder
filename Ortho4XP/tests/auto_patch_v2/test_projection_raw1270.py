"""Twin for #1270: the runway projection extends the stage's own one-sided
matrix with its equality pairs instead of re-assembling every side — the
stack is ``_one_matrix`` of the whole list, array for array."""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from auto_patch_v2.solve.rows import _one_matrix, _Reduction


def _sides(rng, n_v: int, m: int):
    out = []
    for _ in range(m):
        k = int(rng.integers(1, 5))
        vs = rng.choice(n_v, size=k, replace=True)          # repeats merge
        out.append((tuple((int(v), float(rng.normal())) for v in vs),
                    float(rng.normal()), None))
    return out


def test_extended_stack_is_the_whole_assembly():
    rng = np.random.default_rng(1270)
    n_v = 400
    red = _Reduction(n_v)
    for v in rng.choice(n_v, size=60, replace=False):
        red.fixed[int(v)] = float(rng.normal(100.0, 5.0))
    red.finish()
    one = _sides(rng, n_v, 3000)
    eq = _sides(rng, n_v, 40)
    pairs = []
    for terms, hi, row in eq:
        pairs.append((terms, hi, row))
        pairs.append((tuple((v, -c) for v, c in terms), -float(hi), row))
    A_raw, b_raw = _one_matrix(one, red)
    A_eq, b_eq = _one_matrix(pairs, red)
    got_A = sp.vstack([A_raw, A_eq], format="csr")
    got_b = np.concatenate([b_raw, b_eq])
    want_A, want_b = _one_matrix(one + pairs, red)
    assert np.array_equal(got_A.indptr, want_A.indptr)
    assert np.array_equal(got_A.indices, want_A.indices)
    assert got_A.data.tobytes() == want_A.data.tobytes()
    assert got_b.tobytes() == want_b.tobytes()
