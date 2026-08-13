"""The sweep's ACTIVE-ROW COMPRESSION is a bit-identical fast path.

``one_solve._project_chromatic`` skips the corrections it can prove are
value-preserving (a row inside tolerance contributes ``sign(d) * 0.0``).
These twins hold the two code paths against each other on the RAW BYTES
of the solved field — ``-0.0`` and ``0.0`` are different results here, so
``==`` would not be a test.  ``COMPRESSION_MIN_ROWS`` is the switch: it
selects WHICH of the two paths runs and may never select a value.
"""
import random

import numpy as np
import pytest

from auto_patch.elevation_per_surface.route_profile import one_solve


def _run(edges, elev, *, min_rows, tol=0.0, sweeps=40, bounds=None,
         node_box=None):
    field = list(elev)
    stats: dict = {}
    saved = one_solve.COMPRESSION_MIN_ROWS
    one_solve.COMPRESSION_MIN_ROWS = min_rows
    try:
        one_solve._project_chromatic(
            field, edges, max(max(e[0] for e in edges),
                              max(e[1] for e in edges)) + 1,
            sweeps, tol, bounds, stats=stats, coloring_state={},
            node_box=node_box)
    finally:
        one_solve.COMPRESSION_MIN_ROWS = saved
    return np.asarray(field, dtype=np.float64).tobytes(), stats


def _both_paths(edges, elev, **kw):
    """(compressed, full-width) results — 1 forces the fast path on, a
    number above the row count forces it off."""
    hot, hot_stats = _run(edges, elev, min_rows=1, **kw)
    cold, cold_stats = _run(edges, elev, min_rows=10 ** 9, **kw)
    return (hot, hot_stats), (cold, cold_stats)


def _symmetric_fixture(seed=7, rows=400, nodes=260):
    rng = random.Random(seed)
    edges = []
    for _ in range(rows):
        i = rng.randrange(nodes)
        j = rng.randrange(nodes)
        if i == j:
            j = (j + 1) % nodes
        # kinds 1 and 2 pin one endpoint (weight 0) — they are what makes a
        # colour's columns repeat, which is the case the masks exist for.
        kind = rng.choice((0, 0, 0, 1, 2))
        edges.append((i, j, rng.uniform(0.05, 2.0), kind))
    elev = [rng.uniform(-40.0, 900.0) for _ in range(nodes)]
    return edges, elev


def test_compressed_sweep_is_bit_identical_to_full_width():
    edges, elev = _symmetric_fixture()
    (hot, hot_stats), (cold, cold_stats) = _both_paths(edges, elev)
    assert hot == cold
    assert hot_stats["sweeps"] == cold_stats["sweeps"]
    assert hot_stats["certified"] == cold_stats["certified"]
    assert hot_stats["exit_reason"] == cold_stats["exit_reason"]
    assert hot_stats["worst"] == cold_stats["worst"]


def test_compressed_interval_slabs_are_bit_identical():
    rng = random.Random(11)
    nodes = 220
    edges = []
    bounds = {}
    for k in range(360):
        i = rng.randrange(nodes)
        j = (i + 1 + rng.randrange(nodes - 1)) % nodes
        kind = rng.choice((0, 1, 2))
        edges.append((i, j, None, kind))          # budget None => interval
        low = rng.uniform(-3.0, 0.0)
        bounds[k] = (low, low + rng.uniform(0.5, 4.0))
    elev = [rng.uniform(0.0, 120.0) for _ in range(nodes)]
    (hot, _), (cold, _) = _both_paths(edges, elev, bounds=bounds)
    assert hot == cold


def test_compressed_sweep_is_bit_identical_under_the_stall_report(monkeypatch):
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    edges, elev = _symmetric_fixture(seed=3)
    (hot, hot_stats), (cold, cold_stats) = _both_paths(edges, elev)
    assert hot == cold
    # the forensics the compressed path reproduces rather than skips
    assert hot_stats["active_edges"] == cold_stats["active_edges"]
    assert hot_stats["carrier"] == cold_stats["carrier"]


def test_compressed_sweep_is_bit_identical_with_bounded_yield_boxes():
    edges, elev = _symmetric_fixture(seed=5)
    box = {v: (10.0, 400.0) for v in range(0, 260, 3)}
    (hot, _), (cold, _) = _both_paths(edges, elev, node_box=box)
    assert hot == cold


def test_negative_zero_field_stands_the_compression_down():
    """A -0.0 in the field is exactly the case the skip is NOT value-
    preserving, so the gate must fall back — and still agree."""
    edges, elev = _symmetric_fixture(seed=9)
    elev[0] = -0.0
    elev[17] = -0.0
    assert np.signbit(np.asarray(elev)[0])
    (hot, _), (cold, _) = _both_paths(edges, elev)
    assert hot == cold


@pytest.mark.parametrize("column,expected", [
    ([3, 1, 4, 1, 5], [True, False, True, True, True]),
    ([9, 9, 9], [False, False, True]),
])
def test_last_write_mask_marks_the_surviving_row(column, expected):
    mask = one_solve._column_last_write_mask(np, np.asarray(column,
                                                            dtype=np.intp))
    assert mask is not None
    assert list(mask) == expected


def test_last_write_mask_is_none_when_nothing_repeats():
    column = np.asarray([4, 0, 9, 2], dtype=np.intp)
    assert one_solve._column_last_write_mask(np, column) is None


def test_last_write_mask_matches_numpy_scatter_semantics():
    """The mask must name exactly the rows a fancy-indexed scatter keeps."""
    rng = np.random.default_rng(42)
    column = rng.integers(0, 12, size=60).astype(np.intp)
    delta = rng.normal(size=60)
    base = rng.normal(size=12)

    full = base.copy()
    full[column] += delta

    mask = one_solve._column_last_write_mask(np, column)
    kept = base.copy()
    rows = np.flatnonzero(mask)
    kept[column[rows]] += delta[rows]
    assert full.tobytes() == kept.tobytes()
