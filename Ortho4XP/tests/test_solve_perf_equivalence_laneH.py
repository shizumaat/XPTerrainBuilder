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

import heapq
import random
import struct

import pytest

from auto_patch.elevation_per_surface.route_profile.solve import (
    _flex_value_envelope)
from auto_patch.elevation_per_surface import solver_primitives as _sp
from auto_patch.elevation_per_surface.solver_primitives import (
    nearest_hard_candidates)


def _bits(x: float) -> bytes:
    """Raw IEEE-754 bytes — ``0.0 == -0.0`` but their bytes differ."""
    return struct.pack("<d", x)


# ── the code lane H replaced, kept verbatim as the reference ──────────

def _value_envelope_reference(adjacency, node_owner_ref, seeds, sign):
    """The pre-lane-H lazy Dijkstra, character for character.

    Every relaxation is pushed; nothing is suppressed.  This is the
    oracle the suppressed version owes equality to.
    """
    best: dict = {}
    _tie = 0
    pq = []
    for i, v in seeds.items():
        pq.append(((v if sign > 0 else -v), _tie, i,
                   node_owner_ref.get(i)))
        _tie += 1
    heapq.heapify(pq)
    while pq:
        key, _t, k, origin = heapq.heappop(pq)
        if k in best:
            continue
        best[k] = ((key if sign > 0 else -key), origin)
        for (j, budget) in adjacency.get(k, ()):
            if j in best:
                continue
            nt = best[k][0] + sign * budget
            _tie += 1
            heapq.heappush(pq, ((nt if sign > 0 else -nt), _tie, j, origin))
    return best


def _random_graph(rng, n_nodes, n_edges, *, budget_choices=None):
    """Symmetric budget adjacency in the hook's own shape."""
    adjacency: dict = {}

    def add(i, j, budget):
        if budget is None or budget < 0 or i == j:
            return
        adjacency.setdefault(i, []).append((j, budget))
        adjacency.setdefault(j, []).append((i, budget))

    for _ in range(n_edges):
        i = rng.randrange(n_nodes)
        j = rng.randrange(n_nodes)
        if budget_choices is None:
            b = rng.choice([0.0, 0.25, 1.0, 2.5, rng.random() * 5.0])
        else:
            b = rng.choice(budget_choices)
        add(i, j, b)
    return adjacency


def _compare(got, want):
    assert set(got) == set(want), "envelope reached a different node set"
    for k in sorted(want):
        g_val, g_org = got[k]
        w_val, w_org = want[k]
        assert _bits(g_val) == _bits(w_val), (
            f"node {k}: value bytes differ ({g_val!r} vs {w_val!r})")
        assert g_org == w_org, (
            f"node {k}: binding ORIGIN differs ({g_org!r} vs {w_org!r}) — "
            f"the origin decides whether a flex demand is split, so a tie "
            f"broken the other way is an emitted-surface change")


@pytest.mark.parametrize("sign", [+1, -1])
@pytest.mark.parametrize("seed", range(12))
def test_flex_value_envelope_matches_the_unsuppressed_dijkstra(sign, seed):
    """Random graphs: suppressed pushes change nothing that is read."""
    rng = random.Random(1000 + seed)
    n_nodes = rng.randrange(6, 60)
    adjacency = _random_graph(rng, n_nodes, n_nodes * 3)
    owners = {i: rng.choice(["05L/23R", "05C/23C", None])
              for i in range(n_nodes)}
    n_seeds = max(1, rng.randrange(1, max(2, n_nodes // 3)))
    seeds = {i: rng.uniform(-40.0, 90.0)
             for i in sorted(rng.sample(range(n_nodes), n_seeds))}
    _compare(_flex_value_envelope(adjacency, owners, seeds, sign),
             _value_envelope_reference(adjacency, owners, seeds, sign))


@pytest.mark.parametrize("sign", [+1, -1])
def test_flex_value_envelope_ties_keep_the_first_origin(sign):
    """A DELIBERATE tie: two seeds reach one node at the same key.

    The suppression drops the second (equal-key) push.  The reference
    kept it and then threw it away at the pop guard — so both must
    record the FIRST pusher's origin.  This is the case the random
    graphs above hit only by luck.
    """
    # 0 --1.0-- 2 --1.0-- 1 : seeds 0 and 1 at the same value.
    adjacency = {0: [(2, 1.0)], 1: [(2, 1.0)], 2: [(0, 1.0), (1, 1.0)]}
    owners = {0: "05L/23R", 1: "05C/23C"}
    seeds = {0: 12.0, 1: 12.0}
    _compare(_flex_value_envelope(adjacency, owners, seeds, sign),
             _value_envelope_reference(adjacency, owners, seeds, sign))


@pytest.mark.parametrize("sign", [+1, -1])
def test_flex_value_envelope_zero_budgets_and_negative_zero(sign):
    """Zero budgets and a ``-0.0`` seed — the lane C negative-zero class.

    ``-0.0`` and ``0.0`` compare equal, so only a byte comparison can
    see a divergence here.  Zero-budget edges make EVERY relaxation an
    exact tie, which is the suppression's worst case.
    """
    rng = random.Random(77)
    adjacency = _random_graph(rng, 24, 60, budget_choices=[0.0, 0.0, 1.5])
    owners = {i: (None if i % 3 else "05R/23L") for i in range(24)}
    seeds = {0: -0.0, 3: 0.0, 7: -0.0, 11: 4.25}
    _compare(_flex_value_envelope(adjacency, owners, seeds, sign),
             _value_envelope_reference(adjacency, owners, seeds, sign))


@pytest.mark.parametrize("sign", [+1, -1])
def test_flex_value_envelope_isolated_and_empty(sign):
    """Nodes with no adjacency at all, and an empty seed set."""
    adjacency = {0: [(1, 2.0)], 1: [(0, 2.0)]}
    owners = {}
    _compare(_flex_value_envelope(adjacency, owners, {0: 5.0, 9: 1.0}, sign),
             _value_envelope_reference(adjacency, owners,
                                       {0: 5.0, 9: 1.0}, sign))
    assert _flex_value_envelope(adjacency, owners, {}, sign) == {}


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

def _backfill_winner(nodes, i, hard_pts, candidates):
    """``_seed_elevations``' backfill loop, verbatim, over ``candidates``."""
    x, y = nodes[i]
    best_d2 = float("inf")
    best_e = 0.0
    for _h in candidates:
        hx, hy, he = hard_pts[_h]
        d2 = (hx - x) ** 2 + (hy - y) ** 2
        if d2 < best_d2:
            best_d2 = d2
            best_e = he
    return best_d2, best_e


@pytest.mark.parametrize("seed", range(20))
def test_nearest_hard_candidates_keep_the_exact_winner(seed):
    """The bounded scan picks what the full scan picked, byte for byte."""
    rng = random.Random(5000 + seed)
    n_hard = rng.randrange(1, 400)
    n_soft = rng.randrange(1, 250)
    hard_pts = [(rng.uniform(-5e3, 5e3), rng.uniform(-5e3, 5e3),
                 rng.uniform(-20.0, 300.0)) for _ in range(n_hard)]
    nodes = [(rng.uniform(-5e3, 5e3), rng.uniform(-5e3, 5e3))
             for _ in range(n_soft)]
    soft_idx = list(range(n_soft))
    cand = nearest_hard_candidates(nodes, soft_idx, hard_pts)
    assert len(cand) == n_soft
    full = tuple(range(n_hard))
    for s, i in enumerate(soft_idx):
        w_d2, w_e = _backfill_winner(nodes, i, hard_pts, full)
        g_d2, g_e = _backfill_winner(nodes, i, hard_pts, cand[s])
        assert _bits(g_d2) == _bits(w_d2)
        assert _bits(g_e) == _bits(w_e)


def test_nearest_hard_candidates_survive_exact_ties():
    """Coincident hard points: the FIRST index must still win.

    ``if d2 < best_d2`` is a STRICT test, so a duplicate at the same
    distance never displaces the earlier one.  The candidate lists are
    ascending for exactly this reason.
    """
    hard_pts = ([(0.0, 0.0, 10.0), (0.0, 0.0, 20.0), (3.0, 4.0, 30.0)] * 40)
    nodes = [(0.0, 0.0), (3.0, 4.0), (1.5, 2.0), (-900.0, 12.0)]
    soft_idx = list(range(len(nodes)))
    cand = nearest_hard_candidates(nodes, soft_idx, hard_pts)
    full = tuple(range(len(hard_pts)))
    for s, i in enumerate(soft_idx):
        assert (_backfill_winner(nodes, i, hard_pts, cand[s])
                == _backfill_winner(nodes, i, hard_pts, full))


def test_nearest_hard_candidates_degenerate_inputs():
    """No soft nodes, a tiny hard set, and non-finite coordinates.

    The last one is the reason the bound is guarded at all: a NaN makes
    every comparison false, and the fallback is "every hard point is a
    candidate" — i.e. the original scan.
    """
    assert nearest_hard_candidates([(0.0, 0.0)], [], [(1.0, 1.0, 2.0)]) == []
    small = [(1.0, 1.0, 2.0), (2.0, 2.0, 3.0)]
    assert nearest_hard_candidates([(0.0, 0.0)], [0], small) == [(0, 1)]
    big = [(float(k), float(k), float(k)) for k in range(200)]
    nan_nodes = [(float("nan"), 0.0)]
    assert nearest_hard_candidates(nan_nodes, [0], big) == [tuple(range(200))]
    big_nan = list(big)
    big_nan[7] = (float("inf"), 0.0, 1.0)
    assert (nearest_hard_candidates([(0.0, 0.0)], [0], big_nan)
            == [tuple(range(200))])


def test_nearest_hard_candidates_blocks_do_not_shift_rows():
    """More soft nodes than one block: row r must still get row r's list."""
    rng = random.Random(99)
    n_hard = 120
    hard_pts = [(rng.uniform(-1e3, 1e3), rng.uniform(-1e3, 1e3),
                 rng.uniform(0.0, 50.0)) for _ in range(n_hard)]
    n_soft = _sp._NEAREST_HARD_BLOCK * 2 + 37
    nodes = [(rng.uniform(-1e3, 1e3), rng.uniform(-1e3, 1e3))
             for _ in range(n_soft)]
    soft_idx = list(range(n_soft))
    cand = nearest_hard_candidates(nodes, soft_idx, hard_pts)
    assert len(cand) == n_soft
    full = tuple(range(n_hard))
    for s in (0, 1, _sp._NEAREST_HARD_BLOCK - 1, _sp._NEAREST_HARD_BLOCK,
              _sp._NEAREST_HARD_BLOCK + 1, n_soft - 1):
        assert (_backfill_winner(nodes, s, hard_pts, cand[s])
                == _backfill_winner(nodes, s, hard_pts, full))
