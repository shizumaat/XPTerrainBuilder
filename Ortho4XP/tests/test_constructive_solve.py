"""Twins for the constructive solve core (K1 lane, spec
``docs/specs/constructive-solve-spec.md``).

These pin the spec's pre-delegated properties at unit level:

* SELECTION DETERMINISM — envelope + midpoint + smoothing reproduce
  bit-identically on identical inputs (the build-level twin is the
  build-twice byte-identity arm).
* INTERVAL CONTAINMENT — the one smoothing sweep never exits a node's
  envelope interval and preserves pairwise cap-lawfulness.
* ENVELOPE CONTRACT — ``law_edge_limits`` / ``envelope_radj`` /
  ``reach_envelope`` agree with the projection's own documented
  semantics (tightest-wins dedup, signed-slab embedding, sign
  discipline, cap-Lipschitz envelopes, midpoint lawfulness).
* CERTIFIED-TIER RIDE — ``certified_pins`` pins every node a
  still-lazy entry names (body and ring), and nothing else.
* MODE KEY — ``solve_model`` resolution: layout attr > env > default,
  unknown value falls back loudly to iterative.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from auto_patch import solve_model
from auto_patch.elevation_per_surface.route_profile.one_solve import (
    envelope_radj, law_edge_limits, reach_envelope)
from auto_patch.elevation_per_surface.route_profile.constructive import (
    certified_pins, smooth_once)


def _entries(edges, **extra):
    e = {"edges": edges}
    e.update(extra)
    return e


# ── law_edge_limits: the projection's dedup contract ──────────────────

def test_law_edge_limits_tightest_symmetric_wins():
    scs = [_entries([(0, 1, 2.0), (1, 0, 0.5), (0, 1, 1.0)])]
    edge_lim, interval_lim, skip = law_edge_limits(scs, 2)
    assert edge_lim == {(0, 1): 0.5}
    assert interval_lim == {} and skip == set()


def test_law_edge_limits_unregulated_and_out_of_range_skipped():
    scs = [_entries([(0, 1, None), (0, 1, -1.0), (0, 5, 1.0),
                     (2, 2, 1.0)])]
    edge_lim, interval_lim, _ = law_edge_limits(scs, 3)
    assert edge_lim == {} and interval_lim == {}


def test_law_edge_limits_interval_flip_and_intersect():
    # (2, 1, lo, hi) flips to pair (1, 2) with negated/swapped sides.
    scs = [_entries([(1, 2, -1.0, 3.0), (2, 1, -2.0, 0.5)])]
    _, interval_lim, _ = law_edge_limits(scs, 3)
    # second slab flipped: z1 − z2 ∈ [−0.5, 2.0]; intersect with
    # [−1.0, 3.0] → [−0.5, 2.0]
    assert interval_lim == {(1, 2): (-0.5, 2.0)}


def test_law_edge_limits_envelope_skip_and_flat_pairs():
    scs = [_entries([(0, 1, -0.5, 0.5)], envelope_skip=True),
           _entries([(1, 2, 4.0)], flat_pairs=[(2, 3)])]
    edge_lim, interval_lim, skip = law_edge_limits(
        scs, 4, include_flat_pairs=True)
    assert skip == {(0, 1)}
    assert edge_lim[(2, 3)] == 0.0 and edge_lim[(1, 2)] == 4.0
    assert (0, 1) in interval_lim


# ── envelope_radj: the documented signed embedding ────────────────────

def test_envelope_radj_symmetric_embedding():
    ceil_radj, floor_radj = envelope_radj({(0, 1): 2.0}, {})
    assert (1, 2.0) in ceil_radj[0] and (0, 2.0) in ceil_radj[1]
    assert (1, -2.0) in floor_radj[0] and (0, -2.0) in floor_radj[1]


def test_envelope_radj_interval_embedding_and_sign_discipline():
    # slab: −1 ≤ z0 − z1 ≤ 3 → all four documented inequalities embed
    ceil_radj, floor_radj = envelope_radj({}, {(0, 1): (-1.0, 3.0)})
    assert (0, 3.0) in ceil_radj[1]        # ceil_0 ≤ ceil_1 + high
    assert (1, 1.0) in ceil_radj[0]        # ceil_1 ≤ ceil_0 − low
    assert (1, -3.0) in floor_radj[0]      # floor_1 ≥ floor_0 − high
    assert (0, -1.0) in floor_radj[1]      # floor_0 ≥ floor_1 + low
    # same-sign slab (must-climb: low > 0) embeds NOTHING for the low
    # side (the negative-cycle Dijkstra blowup class)
    ceil_radj, floor_radj = envelope_radj({}, {(0, 1): (1.0, None)})
    assert ceil_radj == {} and floor_radj == {}


def test_envelope_radj_zone_leaf_and_skip_exclusion():
    ceil_radj, _ = envelope_radj({}, {(1, 5): (-1.0, 1.0)},
                                 interval_yield_from=5)
    assert ceil_radj == {}                 # leaf slab excluded
    ceil_radj, _ = envelope_radj({}, {(0, 1): (-1.0, 1.0)},
                                 envelope_skip_pairs={(0, 1)})
    assert ceil_radj == {}                 # flagged entry excluded


# ── reach_envelope: cap-Lipschitz + midpoint lawfulness ──────────────

def _chain_graph(n, lim):
    edge_lim = {(i, i + 1): lim for i in range(n - 1)}
    return edge_lim


def test_reach_envelope_values_and_lipschitz():
    n = 6
    edge_lim = _chain_graph(n, 1.0)
    ceil_radj, floor_radj = envelope_radj(edge_lim, {})
    values = [10.0, 0, 0, 0, 0, 14.0]
    seeds = [0, 5]
    ceil, _ = reach_envelope(+1, ceil_radj, seeds, values, n)
    floor, _ = reach_envelope(-1, floor_radj, seeds, values, n)
    # exact multi-source arithmetic
    for k in range(n):
        assert ceil[k] == min(10.0 + k, 14.0 + (5 - k))
        assert floor[k] == max(10.0 - k, 14.0 - (5 - k))
        assert floor[k] <= ceil[k]
    # cap-Lipschitz across every edge, and the midpoint too
    mid = {k: 0.5 * (ceil[k] + floor[k]) for k in range(n)}
    for (i, j), lim in edge_lim.items():
        assert abs(ceil[i] - ceil[j]) <= lim + 1e-12
        assert abs(floor[i] - floor[j]) <= lim + 1e-12
        assert abs(mid[i] - mid[j]) <= lim + 1e-12


def test_reach_envelope_reports_infeasible_anchor_pair():
    # two anchors 10 apart in value, 3 apart in budget → floor > ceil
    n = 4
    edge_lim = _chain_graph(n, 1.0)
    ceil_radj, floor_radj = envelope_radj(edge_lim, {})
    values = [0.0, 0, 0, 10.0]
    ceil, _ = reach_envelope(+1, ceil_radj, [0, 3], values, n)
    floor, _ = reach_envelope(-1, floor_radj, [0, 3], values, n)
    assert any(floor[k] > ceil[k] for k in range(n))


def test_reach_envelope_deterministic():
    n = 30
    edge_lim = _chain_graph(n, 0.7)
    edge_lim[(0, 29)] = 5.0
    edge_lim[(3, 17)] = 0.2
    ceil_radj, floor_radj = envelope_radj(edge_lim, {})
    values = [float((7 * k) % 13) for k in range(n)]
    seeds = [0, 13, 29]
    a = reach_envelope(+1, ceil_radj, seeds, values, n)
    b = reach_envelope(+1, ceil_radj, seeds, values, n)
    assert a == b


# ── smooth_once: containment + lawfulness invariants ─────────────────

def test_smooth_once_stays_in_interval_and_lawful():
    n = 6
    edge_lim = _chain_graph(n, 1.0)
    ceil_radj, floor_radj = envelope_radj(edge_lim, {})
    values = [10.0, 0, 0, 0, 0, 14.0]
    seeds = [0, 5]
    ceil, _ = reach_envelope(+1, ceil_radj, seeds, values, n)
    floor, _ = reach_envelope(-1, floor_radj, seeds, values, n)
    elev = [values[0]] + [0.5 * (ceil[k] + floor[k])
                          for k in range(1, n - 1)] + [values[5]]
    sym_adj = {}
    for (i, j), lim in edge_lim.items():
        sym_adj.setdefault(i, []).append((j, lim))
        sym_adj.setdefault(j, []).append((i, lim))
    hard = {0, 5}
    moved = smooth_once(
        elev, n, movable=lambda i: i not in hard, sym_adj=sym_adj,
        interval_of=lambda i: (floor[i], ceil[i]))
    assert moved >= 0
    for k in range(1, n - 1):
        assert floor[k] - 1e-9 <= elev[k] <= ceil[k] + 1e-9
    for (i, j), lim in edge_lim.items():
        assert abs(elev[i] - elev[j]) <= lim + 1e-9
    # determinism: same inputs, same output
    elev2 = [values[0]] + [0.5 * (ceil[k] + floor[k])
                           for k in range(1, n - 1)] + [values[5]]
    smooth_once(elev2, n, movable=lambda i: i not in hard,
                sym_adj=sym_adj,
                interval_of=lambda i: (floor[i], ceil[i]))
    elev3 = [values[0]] + [0.5 * (ceil[k] + floor[k])
                           for k in range(1, n - 1)] + [values[5]]
    smooth_once(elev3, n, movable=lambda i: i not in hard,
                sym_adj=sym_adj,
                interval_of=lambda i: (floor[i], ceil[i]))
    assert elev2 == elev3


def test_smooth_once_skips_empty_clamp():
    # both-hard neighbours already over cap: the free middle node's
    # clamp interval is empty — it must not move (never forced).
    elev = [0.0, 5.0, 20.0]
    sym_adj = {1: [(0, 1.0), (2, 1.0)]}
    moved = smooth_once(
        elev, 3, movable=lambda i: i == 1, sym_adj=sym_adj,
        interval_of=lambda i: (None, None))
    assert moved == 0 and elev[1] == 5.0


# ── certified_pins: the C3 tier ride ─────────────────────────────────

def test_certified_pins_body_and_ring_minus_hard():
    scs = [
        # still-lazy: pins body (7, 8) and ring nodes from edges
        {"edges": [(0, 1, 1.0)], "lazy_expand": lambda: [],
         "lazy_nodes": [7, 8]},
        # eager entry: contributes nothing
        {"edges": [(2, 3, 1.0)]},
    ]
    base_hard = [False] * 10
    base_hard[1] = True
    pins, n_lazy = certified_pins(scs, base_hard, 10)
    assert n_lazy == 1
    assert pins == {0, 7, 8}          # 1 is hard, 2/3 eager


# ── the mode key ─────────────────────────────────────────────────────

def test_solve_model_resolution(monkeypatch):
    monkeypatch.delenv(solve_model.SOLVE_MODEL_ENV, raising=False)
    assert solve_model.resolve() == "iterative"

    class L:
        pass
    layout = L()
    assert solve_model.resolve(layout) == "iterative"
    monkeypatch.setenv(solve_model.SOLVE_MODEL_ENV, "constructive")
    assert solve_model.resolve(layout) == "constructive"
    layout.solve_model = "iterative"          # cfg wins over env
    assert solve_model.resolve(layout) == "iterative"
    layout.solve_model = "Constructive"       # case-insensitive
    assert solve_model.resolve(layout) == "constructive"
    layout.solve_model = "bogus"              # loud fallback
    assert solve_model.resolve(layout) == "iterative"
