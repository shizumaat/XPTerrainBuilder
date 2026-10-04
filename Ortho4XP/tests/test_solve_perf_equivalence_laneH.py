"""Equivalence twins for perf P3 lane H (solve remaining halves).

Every transformation this lane landed claims to be BIT-EXACT, not merely
"close".  These twins hold each rewritten kernel against the code it
replaced on RAW FLOAT64 BYTES — a value that differs in the last ulp
would pass an ``==`` on some inputs and still move an emitted patch, so
nothing here compares with a tolerance.

The frozen-baseline replay (HECA ``f562cbfeb8f9``, CYXY
``61efa43c3aeb``) is the lane's real gate; these are the unit-level
statements of WHY it holds, and they fail on the exact inputs the
whole-airport gate would only catch by accident (negative zero, ties in
the Dijkstra origin, empty neighbour lists).
"""
from __future__ import annotations

import random
import struct

import pytest


def _bits(x: float) -> bytes:
    """Raw IEEE-754 bytes — ``0.0 == -0.0`` but their bytes differ."""
    return struct.pack("<d", x)


# ── the code lane H replaced, kept verbatim as the reference ──────────


# ── the merged Gauss-Seidel neighbour pass ───────────────────────────

def _sweep_accumulators_reference(elev, lst, _INF):
    """The three separate passes ``one_profile_solve`` used to run."""
    sw = acc = 0.0
    for (j, _l, w) in lst:
        sw += w
        acc += elev[j] * w
    pm = sum(elev[j] for (j, _l, _w) in lst) / len(lst)
    n_lo, n_hi = -_INF, _INF
    for (j, lim, _w) in lst:
        ej = elev[j]
        if ej - lim > n_lo:
            n_lo = ej - lim
        if ej + lim < n_hi:
            n_hi = ej + lim
    return sw, acc, pm, n_lo, n_hi


def _sweep_accumulators_merged(elev, lst, _INF, sw):
    """Lane H's single pass — ``sw`` hoisted out of the sweep entirely."""
    acc = 0.0
    vals = []
    _app = vals.append
    n_lo, n_hi = -_INF, _INF
    for (j, lim, w) in lst:
        ej = elev[j]
        acc += ej * w
        _app(ej)
        if ej - lim > n_lo:
            n_lo = ej - lim
        if ej + lim < n_hi:
            n_hi = ej + lim
    return acc, sum(vals) / len(lst), n_lo, n_hi


def _naive_running_sum(values):
    """What a hand-rolled ``pacc += ej`` would produce."""
    pacc = 0.0
    for v in values:
        pacc += v
    return pacc


@pytest.mark.parametrize("seed", range(25))
def test_merged_neighbour_pass_is_bit_identical(seed):
    """One pass over the neighbour list == the three it replaced.

    The claim is ORDER: each accumulator still adds its own terms
    left-to-right in list order, so every partial sum — and therefore
    every rounding — is the one the three-pass version produced.
    """
    _INF = float("inf")
    rng = random.Random(2000 + seed)
    n_nodes = rng.randrange(2, 40)
    elev = [rng.uniform(-30.0, 120.0) for _ in range(n_nodes)]
    if seed % 5 == 0:                       # negative zero in the field
        elev[rng.randrange(n_nodes)] = -0.0
    size = rng.randrange(1, 12)
    lst = [(rng.randrange(n_nodes),
            rng.choice([0.0, 0.001, 0.15, 1.0, rng.random() * 3.0]),
            rng.choice([1e-6, 0.5, 1.0, 1e6, rng.random() * 1e3]))
           for _ in range(size)]

    sw_r, acc_r, pm_r, lo_r, hi_r = _sweep_accumulators_reference(
        elev, lst, _INF)
    # the hoisted sum, accumulated exactly as the sweep accumulated it
    sw_h = 0.0
    for (_j, _l, w) in lst:
        sw_h += w
    assert _bits(sw_h) == _bits(sw_r)

    acc_m, pm_m, lo_m, hi_m = _sweep_accumulators_merged(
        elev, lst, _INF, sw_h)
    assert _bits(acc_m) == _bits(acc_r)
    assert _bits(pm_m) == _bits(pm_r)
    assert _bits(lo_m) == _bits(lo_r)
    assert _bits(hi_m) == _bits(hi_r)

    # …and the blended target the two feed, including the hoisted
    # ``1.0 - curvature``.
    for curvature in (0.0, 0.25, 1.0, 0.3333333333333333):
        harm_r = acc_r / sw_r if sw_r > 0 else elev[0]
        tgt_r = (1.0 - curvature) * harm_r + curvature * pm_r
        harm_m = acc_m / sw_h if sw_h > 0 else elev[0]
        tgt_m = (1.0 - curvature) * harm_m + curvature * pm_m
        assert _bits(tgt_m) == _bits(tgt_r)


def test_builtin_sum_is_compensated_so_it_must_stay_sum():
    """The trap this lane walked into, pinned so nobody re-walks it.

    ``sum()`` over floats is NOT ``a += b`` in a loop: CPython runs
    Neumaier compensated summation on the all-float fast path.  Replacing
    ``sum(elev[j] for ...)`` with a running accumulator in the merged
    neighbour pass changed ``pm`` on 9 of 25 random neighbour lists — a
    silent surface move that only a byte comparison sees.  The merged
    pass therefore GATHERS and still calls ``sum``.
    """
    rng = random.Random(4242)
    disagreements = 0
    for _ in range(400):
        vals = [rng.uniform(-30.0, 120.0) for _ in range(rng.randrange(2, 12))]
        if _bits(sum(vals)) != _bits(_naive_running_sum(vals)):
            disagreements += 1
    assert disagreements > 0, (
        "sum() and a running accumulator agreed everywhere on this "
        "interpreter — if that is real, this lane's gather could be "
        "simplified; verify before changing anything")
    # …and a list and a generator feed that same compensated path.
    for _ in range(200):
        vals = [rng.uniform(-30.0, 120.0) for _ in range(rng.randrange(1, 12))]
        assert _bits(sum(vals)) == _bits(sum(v for v in vals))
    # the empty-accumulator start is the one place a sign could leak
    for v in (-0.0, 0.0, -1.5, 3.25, 1e308, -1e-320):
        assert _bits(sum([v])) == _bits(0.0 + v)


# ── the nearest-hard backfill candidate bound ────────────────────────


