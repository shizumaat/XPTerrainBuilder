"""Twin for #1270: the stage solve's second LEVEL read continues the belt's
forest over the rows added since (the belt's own, the membrane's) and finds
exactly the columns a fresh read over every row and side finds."""
from __future__ import annotations

import random

from auto_patch_v2.solve.rows import _level_free_columns, _Reduction, _Rows


def _problem(seed: int, n: int = 80):
    rnd = random.Random(seed)
    red = _Reduction(n)
    for _ in range(n // 8):
        red.union(rnd.randrange(n), rnd.randrange(n))
    for _ in range(n // 12):
        red.fixed[rnd.randrange(n)] = rnd.uniform(200.0, 300.0)
    red.finish()
    rows = _Rows(red)
    for _ in range(n // 5):
        a, b = rnd.randrange(n), rnd.randrange(n)
        rows.add(((a, 1.0), (b, -1.0)), 0.0, 1.0)
    one = []
    for _ in range(n):
        a, b = rnd.randrange(n), rnd.randrange(n)
        if rnd.random() < 0.05:
            one.append((((a, 1.0),), rnd.uniform(250.0, 260.0), None))
        else:
            one.append((((a, 1.0), (b, -1.0)), rnd.uniform(0.0, 1.0), None))
    return rnd, rows, red, one


def test_continued_forest_reads_the_fresh_free_set():
    seen_change = 0
    for seed in range(60):
        rnd, rows, red, one = _problem(seed)
        before = set(_level_free_columns(rows, None, red, one, keep=True))
        # the rows the belt and the membrane add: levels and differences
        for _ in range(rnd.randrange(0, 12)):
            a, b = rnd.randrange(len(red.col)), rnd.randrange(len(red.col))
            if rnd.random() < 0.3:
                rows.add(((a, 1.0),), 250.0, 1.0)
            else:
                rows.add(((a, 1.0), (b, -1.0)), 0.0, 1.0)
        got = set(_level_free_columns(rows, None, red, one, resume=True))
        want = set(_level_free_columns(rows, None, red, one))
        assert got == want, seed
        seen_change += got != before
        assert rows.level_forest is None           # read once
    assert seen_change > 0                         # the fixture moves the set


def test_without_a_kept_forest_it_reads_fresh():
    _rnd, rows, red, one = _problem(3)
    assert _level_free_columns(rows, None, red, one, resume=True) == \
        _level_free_columns(rows, None, red, one)
