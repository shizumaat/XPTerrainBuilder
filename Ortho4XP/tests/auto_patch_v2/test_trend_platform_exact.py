"""§46 (7) twin: the long-wave trend reads the same doubles on every
platform (release dry run 41005579641, 2026-10-29).

``x ** n`` on a float is the C library's ``pow``, which macOS, glibc and
the Windows CRT round differently in the last bit.  The tricube kernel of
``constraints/trend.py`` used it, every runway crossing pin and DEM end
pin is read off that kernel, and at CYXY the noise reached a yielded
runway cap and 23,000 constraint rows.  These twins hold the kernels to
IEEE-exact operations and the station mean to the samples' order.
"""
from __future__ import annotations

import ast
import pathlib
import random

from auto_patch_v2.constraints import trend as T

_PKG = pathlib.Path(T.__file__).resolve().parent

#: The smoothing kernels every runway / taxi / surface pin is read off.
_KERNELS = ("trend.py", "surface_trend.py")


def test_trend_kernels_never_call_pow():
    found = []
    for name in _KERNELS:
        tree = ast.parse((_PKG / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                found.append("%s:%d" % (name, node.lineno))
    assert not found, ("``**`` is the C library's pow, which differs per "
                       "platform (§46 (7)); multiply instead: %s" % found)


def test_tricube_is_the_product():
    rng = random.Random(46)
    for _ in range(2000):
        u = rng.uniform(-1.0, 1.0)
        a = abs(u)
        c = 1.0 - a * a * a
        assert T._tricube(u) == c * c * c


def test_trend_is_free_of_the_samples_order():
    rng = random.Random(7)
    samples = [(float(rng.randrange(0, 2000)) * 0.5, 690.0 + rng.random() * 30.0)
               for _ in range(600)]
    ref = T.trend_of(samples, 500.0)
    probes = [rng.uniform(0.0, 1000.0) for _ in range(50)]
    want = [ref.at(q) for q in probes]
    for seed in range(5):
        shuffled = list(samples)
        random.Random(seed).shuffle(shuffled)
        got = T.trend_of(shuffled, 500.0)
        assert got.s == ref.s and got.z == ref.z
        assert [got.at(q) for q in probes] == want


def test_trend_reads_on_the_micrometre_grid():
    """A last-bit difference in a DEM sample (PROJ's inverse differs per
    platform) must not reach a pin: the trend's value is on the 1e-6 m
    grid, and a sample nudged by an ulp reads the same value."""
    rng = random.Random(11)
    samples = [(float(i) * 12.0, 690.0 + rng.random() * 30.0) for i in range(200)]
    ref = T.trend_of(samples, 500.0)
    nudged = T.trend_of([(s, z + z * 2.0 ** -51) for s, z in samples], 500.0)
    for q in (rng.uniform(0.0, 2400.0) for _ in range(100)):
        v = ref.at(q)
        assert v == round(v, T.TREND_DP)
        assert nudged.at(q) == v
