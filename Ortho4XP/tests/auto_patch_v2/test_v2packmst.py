"""SLICE S1 of ``docs/specs/pack-read-once-fast-spec.md`` (row 1): the
Delaunay-candidate heap Prim must emit ``model/ground_fit.neighbour_pairs``'s
OWN ordered edge list — every edge, in its order, with its float — and fall
back to that reference on every degenerate input.

The contract under test is IDENTITY, not "an MST": ``ground_fit`` reads the
ORDER (its ``worst`` is the first pair reaching the maximum residual), so the
list is compared with ``==`` throughout, never as a set and never with a
tolerance.

Fixtures ``fixtures/feet_graph/feet_{TNCM,TFFG}_1500.npy`` are the first 1,500
feet of the two real maxima the findings pickled (the full 27,376 / 86,592
inputs are NOT committed; the opt-in slow test below reads them from
``.lanes/packreadprofile`` when that scratch dir is present).  They carry the
real ~6.7e6 m coordinate offset, real duplicates (TNCM: 94) and real tied
lengths — i.e. the three things that break a naive candidate graph.
"""
from __future__ import annotations

import ast
import math
import pathlib
import pickle
import random
import time

import numpy as np
import pytest

from auto_patch_v2.geom import feet_graph
from auto_patch_v2.geom.feet_graph import neighbour_pairs_fast
from auto_patch_v2.model import ground_fit as gf_mod
from auto_patch_v2.model.ground_fit import ground_fit, neighbour_pairs

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "feet_graph"
LANES = pathlib.Path("/Users/noah/XPTerrainBuilder/.lanes/packreadprofile")


def _pts(arr) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in arr]


def _assert_identical(pts, *, expect_fallbacks: int | None = 0):
    before = feet_graph.fallback_count()
    want = neighbour_pairs(pts)
    got = neighbour_pairs_fast(pts)
    assert got == want, (
        f"n={len(pts)}: first divergence at "
        f"{next((i for i, (a, b) in enumerate(zip(want, got)) if a != b), None)} "
        f"(len {len(want)} vs {len(got)})")
    if expect_fallbacks is not None:
        assert feet_graph.fallback_count() - before == expect_fallbacks
    return got


# --------------------------------------------------------------- T1 identity

@pytest.mark.parametrize("icao", ["TNCM", "TFFG"])
def test_identical_on_reduced_real_input(icao):
    """The real coordinate frame, real duplicates, real ties."""
    pts = _pts(np.load(FIXTURES / f"feet_{icao}_1500.npy"))
    edges = _assert_identical(pts)
    assert len(edges) == len(pts) - 1


@pytest.mark.parametrize("icao,pkl", [("TNCM", "npairs.pkl"),
                                      ("TFFG", "TFFGnpairs.pkl")])
def test_identical_on_full_real_input_slow(icao, pkl):
    """OPT-IN (``O4_PACKMST_SLOW=1``): the full n = 27,376 / 86,592 inputs.
    The reference side alone is 32 s / 345 s, which is the whole point of
    the slice — so it is not in the default run."""
    import os
    if not os.environ.get("O4_PACKMST_SLOW"):
        pytest.skip("set O4_PACKMST_SLOW=1 (the reference side is 32 s / 345 s)")
    path = LANES / pkl
    if not path.exists():
        pytest.skip(f"{path} absent (lane scratch, not committed)")
    with path.open("rb") as fh:
        pts = pickle.load(fh)["biggest"]
    _assert_identical(pts)


def test_identical_on_seeded_random_sets():
    """60 small sets plus 5 large ones; the reference is O(n^2), so the
    large arm is deliberately short."""
    rng = random.Random(20260918)
    sizes = [rng.randint(2, 300) for _ in range(60)]
    sizes += [1000, 1500, 2000, 2200, 2500]
    for n in sizes:
        pts = [(rng.uniform(-500.0, 500.0), rng.uniform(-500.0, 500.0))
               for _ in range(n)]
        _assert_identical(pts)


def test_identical_on_integer_lattice_maximal_ties():
    """A lattice is the maximal-tie input: every unit edge has the same
    length and the cocircular degeneracies are everywhere."""
    pts = [(float(i), float(j)) for i in range(40) for j in range(40)]
    edges = _assert_identical(pts)
    assert len({e[2] for e in edges}) == 1          # all unit-length


def test_identical_with_duplicates_and_mixed_classes():
    rng = random.Random(7)
    base = [(rng.uniform(0, 50), rng.uniform(0, 50)) for _ in range(120)]
    pts = []
    for i, p in enumerate(base):
        pts.extend([p] * (1 + i % 4))               # classes of size 1..4
    rng.shuffle(pts)
    _assert_identical(pts)


def test_identical_on_large_coordinate_offset():
    """THE CENTRING REGRESSION (spec §B.1): feet live at ~6.7e6 m with
    sub-metre spacing.  Un-centred, Qhull's precision merging discards
    almost every point; centred, nothing is dropped and no fallback is
    taken."""
    rng = random.Random(11)
    pts = [(-6.7e6 + rng.uniform(0, 400) * 0.4,
            2.0e6 + rng.uniform(0, 400) * 0.4) for _ in range(900)]
    _assert_identical(pts, expect_fallbacks=0)

    # the witness for WHY the translation is there
    from scipy.spatial import Delaunay
    raw = Delaunay(np.asarray(pts, float))
    if not len(raw.coplanar):
        pytest.skip("this Qhull build did not drop points un-centred")
    centred = np.asarray(pts, float)
    assert not len(Delaunay(centred - centred.mean(axis=0)).coplanar)


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 63, 64, 65])
def test_identical_at_the_small_boundaries(n):
    rng = random.Random(100 + n)
    pts = [(rng.uniform(0, 10), rng.uniform(0, 10)) for _ in range(n)]
    _assert_identical(pts)


def test_deterministic_across_runs():
    rng = random.Random(3)
    pts = [(rng.uniform(0, 100), rng.uniform(0, 100)) for _ in range(800)]
    runs = [neighbour_pairs_fast(pts) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


# ----------------------------------------------------------------- T2 guards

def test_collinear_falls_back_and_is_counted():
    pts = [(float(i), 2.0 * float(i)) for i in range(200)]
    before = feet_graph.fallback_count()
    assert neighbour_pairs_fast(pts) == neighbour_pairs(pts)
    assert feet_graph.fallback_count() - before == 1


def test_all_duplicate_points_fall_back():
    pts = [(5.0, 7.0)] * 200
    before = feet_graph.fallback_count()
    assert neighbour_pairs_fast(pts) == neighbour_pairs(pts)
    assert feet_graph.fallback_count() - before == 1    # < 3 unique points


def test_non_finite_falls_back():
    pts = [(float(i), 0.5 * i * i) for i in range(100)]
    pts[7] = (float("nan"), 0.0)
    before = feet_graph.fallback_count()
    neighbour_pairs_fast(pts)
    assert feet_graph.fallback_count() - before == 1


def test_coplanar_report_forces_fallback(monkeypatch):
    """A Qhull run that DROPPED points cannot be trusted to contain every
    MST edge — even though the triangulation it returns is usable."""
    rng = random.Random(5)
    pts = [(rng.uniform(0, 100), rng.uniform(0, 100)) for _ in range(300)]
    real = feet_graph._Delaunay

    class _Liar:
        def __init__(self, *a, **k):
            self._t = real(*a, **k)
            self.coplanar = np.zeros((3, 3), dtype=np.int64)

        def __getattr__(self, name):
            return getattr(self._t, name)

    monkeypatch.setattr(feet_graph, "_Delaunay", _Liar)
    before = feet_graph.fallback_count()
    assert neighbour_pairs_fast(pts) == neighbour_pairs(pts)
    assert feet_graph.fallback_count() - before == 1


def test_qhull_error_falls_back(monkeypatch):
    rng = random.Random(6)
    pts = [(rng.uniform(0, 100), rng.uniform(0, 100)) for _ in range(300)]

    def _boom(*a, **k):
        raise feet_graph._QhullError("synthetic")

    monkeypatch.setattr(feet_graph, "_Delaunay", _boom)
    before = feet_graph.fallback_count()
    assert neighbour_pairs_fast(pts) == neighbour_pairs(pts)
    assert feet_graph.fallback_count() - before == 1


def test_small_path_is_not_a_fallback():
    """``n < SMALL_N`` is the DESIGNED small path, not a degeneracy: it
    must not pollute the ``mst_fallback`` count."""
    pts = [(float(i), float(i % 3)) for i in range(10)]
    before = feet_graph.fallback_count()
    neighbour_pairs_fast(pts)
    assert feet_graph.fallback_count() == before


# ------------------------------------------------------- T3 the import twin

def test_model_imports_neither_numpy_nor_scipy():
    """M0 §1: the reference stays pure.  AST over the whole ``model``
    package, so a function-level import is caught too."""
    root = pathlib.Path(gf_mod.__file__).parent
    offenders = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), str(path))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if name.split(".")[0] in {"numpy", "scipy", "shapely"}:
                    offenders.append(f"{path.name}:{node.lineno} {name}")
    assert not offenders, offenders


# ---------------------------------------------------------- the whole reading

def test_ground_fit_reads_the_same_verdict_through_either_graph():
    """The injected graph must not move ``GroundFit`` — level, residual,
    limit, ``worst`` AND ``worst_pair`` (the ORDER-dependent fields)."""
    class _F:
        def __init__(self, lat, lon, y):
            self.lat, self.lon, self.y = lat, lon, y

    rng = random.Random(42)
    feet = [_F(18.04 + rng.uniform(0, 0.004), -63.11 + rng.uniform(0, 0.004),
               rng.uniform(0.0, 3.0)) for _ in range(400)]

    def dem_at(lat, lon):
        return 5.0 + 900.0 * (lat - 18.04) + 700.0 * (lon + 63.11)

    a = ground_fit(feet, 0.0, dem_at, 0.05)
    b = ground_fit(feet, 0.0, dem_at, 0.05, pairs=neighbour_pairs_fast)
    assert a == b
    assert a is not None and a.worst_pair != (-1, -1)


def test_complexity_guard_20000_points():
    """n = 20,000 in seconds, not the reference's minutes (the reference
    is NOT run here — that is the regression this slice removes)."""
    rng = random.Random(2026)
    pts = [(-6.7e6 + rng.uniform(0, 900), 2.0e6 + rng.uniform(0, 900))
           for _ in range(20_000)]
    before = feet_graph.fallback_count()
    start = time.perf_counter()
    edges = neighbour_pairs_fast(pts)
    wall = time.perf_counter() - start
    assert len(edges) == len(pts) - 1
    assert feet_graph.fallback_count() == before
    assert wall < 30.0, f"{wall:.1f}s for n=20000"


def test_group_report_carries_mst_fallback():
    from auto_patch_v2.planar import group as group_mod
    src = pathlib.Path(group_mod.__file__).read_text()
    assert '"mst_fallback"' in src
    assert "pairs=_pairs_fast" in src
