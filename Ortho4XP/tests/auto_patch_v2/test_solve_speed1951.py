"""#1951 — the stage solve's per-side passes, made cheap, read EXACTLY as
before: each fast reading is held to the plain reading it replaced on
random inputs (the roots, the level set, the matrix and the head test are
the same values, never "close")."""
from __future__ import annotations

import random
import types

import numpy as np

from auto_patch_v2.geom.union_find import find_root
from auto_patch_v2.solve.design_roles import HeadTest, ruling_head
from auto_patch_v2.solve.rows import (_level_free_columns, _one_matrix,
                                      _Reduction, _Rows)


def _reference_level_free(rows, red, one, tol=1e-9):
    """The reading before #1951: a DICT forest, numpy scalar reads."""
    parent = {c: c for c in range(red.n_cols)}
    has_level = set()

    def take(cols, coefs):
        if not cols:
            return
        r0 = find_root(parent, int(cols[0]))
        for c in cols[1:]:
            parent[find_root(parent, int(c))] = r0
            r0 = find_root(parent, r0)
        if abs(sum(coefs)) > tol:
            has_level.add(find_root(parent, int(cols[0])))
    per = {}
    for k, c, v in zip(rows.r, rows.c, rows.v, strict=True):
        per.setdefault(k, []).append((int(c), float(v)))
    for terms in per.values():
        take([c for c, _ in terms], [v for _, v in terms])
    for terms, _hi, _row in one:
        cols, coefs = [], []
        for vid, coef in terms:
            col = int(red.col[vid])
            if col >= 0:
                cols.append(col)
                coefs.append(float(coef))
        take(cols, coefs)
    level_roots = {find_root(parent, r) for r in has_level}
    return {c: find_root(parent, c) for c in range(red.n_cols)
            if find_root(parent, c) not in level_roots}


def _problem(seed: int, n: int = 60):
    rnd = random.Random(seed)
    red = _Reduction(n)
    for _ in range(n // 6):                   # a few rigid groups
        red.union(rnd.randrange(n), rnd.randrange(n))
    for _ in range(n // 10):                  # a few pins
        red.fixed[rnd.randrange(n)] = rnd.uniform(200.0, 300.0)
    red.finish()
    rows = _Rows(red)
    for _ in range(n // 4):
        a, b = rnd.randrange(n), rnd.randrange(n)
        rows.add(((a, 1.0), (b, -1.0)), 0.0, 1.0)
    one = []
    for _ in range(4 * n):
        a, b = rnd.randrange(n), rnd.randrange(n)
        if rnd.random() < 0.1:
            one.append((((a, 1.0),), rnd.uniform(250.0, 260.0), None))
        else:
            one.append((((a, 1.0), (b, -1.0)), rnd.uniform(0.0, 1.0), None))
    return rows, red, one


def test_level_free_columns_read_as_the_dict_forest_did():
    for seed in range(40):
        rows, red, one = _problem(seed)
        assert _level_free_columns(rows, None, red, one) == \
            _reference_level_free(rows, red, one), seed


def test_one_matrix_is_the_scalar_reading():
    for seed in range(20):
        _rows, red, one = _problem(seed)
        A, b = _one_matrix(one, red)
        ref_b = np.zeros(len(one))
        for k, (terms, hi, _row) in enumerate(one):
            rhs = float(hi)
            for vid, coef in terms:
                if int(red.col[vid]) < 0:
                    rhs -= coef * float(red.value[vid])
            ref_b[k] = rhs
        assert np.array_equal(b, ref_b)
        assert A.shape == (len(one), red.n_cols)


def _row(ruling: str):
    return types.SimpleNamespace(source=types.SimpleNamespace(ruling=ruling))


def test_head_test_is_ruling_head_in_heads():
    heads = frozenset({"pads: structures.building_pad pad_slope_max ceiling",
                       "taxi cap"})
    test = HeadTest(heads)
    for r in ("pads: structures.building_pad pad_slope_max ceiling (owner 09-09c)",
              "taxi cap (x) (y)", "taxi cap", "taxi", "roads: road (2026)", ""):
        want = ruling_head(_row(r)) in heads
        assert test[r] is want
        assert test[r] is want            # the learnt answer, read again


def test_row_blocks_is_the_plain_product_bit_for_bit():
    import scipy.sparse as sp

    from auto_patch_v2.solve.linear import RowBlocks
    rng = np.random.default_rng(7)
    n, m = 5000, 300
    rows = np.repeat(np.arange(n), 2)
    A = sp.csr_matrix((rng.normal(size=2 * n), (rows, rng.integers(0, m, 2 * n))),
                      shape=(n, m))
    x = rng.normal(size=m)
    blocks = RowBlocks(A, workers=4, min_rows=1000)
    try:
        assert len(blocks.blocks) == 4
        assert np.array_equal(blocks @ x, A @ x)
    finally:
        blocks.close()
    whole = RowBlocks(A, workers=4)            # under min_rows: one block
    assert len(whole.blocks) == 1 and np.array_equal(whole @ x, A @ x)


def test_row_blocks_penalty_and_active_set_are_the_plain_reading():
    import scipy.sparse as sp

    from auto_patch_v2.solve.linear import RowBlocks, _objective
    rng = np.random.default_rng(11)
    n, m = 6000, 200
    rows = np.repeat(np.arange(n), 2)
    A1 = sp.csr_matrix((rng.normal(size=2 * n), (rows, rng.integers(0, m, 2 * n))),
                       shape=(n, m))
    A0 = sp.csr_matrix(rng.normal(size=(50, m)))
    b0, b1 = rng.normal(size=50), rng.normal(size=n)
    shift, w = rng.normal(size=n) * 0.1, rng.random(n) + 0.5
    x = rng.normal(size=m)
    bb = b1 - shift
    blocks = RowBlocks(A1, workers=3, min_rows=1000)
    try:
        r, pen = blocks.penalty(x, bb, w)
        assert np.array_equal(r, A1 @ x)
        assert _objective(A0, b0, A1, b1, w, shift, x, pen=pen) == \
            _objective(A0, b0, A1, b1, w, shift, x)
        assert np.array_equal(blocks.above(r, bb, 0.0),
                              np.flatnonzero(A1 @ x - bb > 0.0))
    finally:
        blocks.close()
