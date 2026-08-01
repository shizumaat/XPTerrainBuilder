"""Rod-link COMPOSITION across decimated runs (owner design 2026-07-29).

``docs/specs/rod-compose-and-band-single-source-spec.md`` §A.  The §10
taut-string rod is minted in the SOLVE's node space and carried into
``final_grade_projection``'s REBUILT space by canonical-registry key.  The
audit (memory ``rod-carry-loss-is-emit-decimation``) proved 100 % of the
carry loss is ``emit_decimate.decimate_emit_nodes`` DELETING 3D-collinear
strung ring vertices — so the endpoints of a removed RUN both survive and
only the interior vanishes.

``solve.compose_rod_chains`` replaces the links spanning a removed run by
ONE link between the survivors carrying the run's INTERVAL SUM.  These
tests are pure arithmetic (no layout, no DEM, no build): they pin

  * exactness — the composed interval is ``[ΣΔ − Σε, ΣΔ + Σε]``, and any
    profile satisfying the original chain satisfies the composed link;
  * the LEDGER — ``minted = carried_1to1 + absorbed + dropped`` for every
    survivor pattern, which is the audit's "carried + composed accounts
    for every minted link" acceptance;
  * 1:1 identity — a chain whose vertices all survive carries exactly the
    legacy per-pair edges (the ``O4_ROD_COMPOSE=0`` equivalence);
  * the one-sided rules — chain-end runs and runs whose survivors intern
    to ONE node are dropped, never enforced.
"""
from __future__ import annotations

import random

from auto_patch.elevation_per_surface.route_profile.solve import (
    compose_rod_chains)

EPS = 0.02


def _chain(deltas, first=0):
    """A key chain over keys ``first, first+1, ...`` with the rod's own
    ``[Δ − ε, Δ + ε]`` interval per link."""
    return [(first + i, first + i + 1, d - EPS, d + EPS)
            for i, d in enumerate(deltas)]


def _legacy(chain, resolve):
    """The pre-composition carry: every link whose BOTH endpoints resolve
    to distinct nodes, in order."""
    out = []
    for (ka, kb, lo, hi) in chain:
        ia, ib = resolve(ka), resolve(kb)
        if ia is None or ib is None or ia == ib:
            continue
        out.append((ia, ib, lo, hi))
    return out


def _identity(alive):
    alive = set(alive)
    return lambda k: (k if k in alive else None)


# ── 1. every vertex survives ⇒ 1:1, identical to the legacy carry ───────

def test_all_survivors_carry_one_to_one():
    chain = _chain([0.5, -0.25, 1.0])
    resolve = _identity(range(4))
    edges, dropped, recs, composed, absorbed, span = compose_rod_chains(
        [chain], resolve)
    assert edges == _legacy(chain, resolve)
    assert (dropped, composed, absorbed, span) == (0, 0, 0, 0)


# ── 2. an interior run is composed EXACTLY ─────────────────────────────

def test_interior_run_composes_to_the_interval_sum():
    """S1 · v · v · S2 — the three links become ONE with the interval sum."""
    deltas = [0.4, -0.1, 0.7]
    chain = _chain(deltas)
    edges, dropped, recs, composed, absorbed, span = compose_rod_chains(
        [chain], _identity({0, 3}))          # keys 1, 2 decimated away
    assert len(edges) == 1
    ia, ib, lo, hi = edges[0]
    assert (ia, ib) == (0, 3)
    assert lo == sum(d - EPS for d in deltas)
    assert hi == sum(d + EPS for d in deltas)
    # The spec's own form: [ΣΔ − Σε, ΣΔ + Σε].
    assert lo == sum(deltas) - 3 * EPS
    assert hi == sum(deltas) + 3 * EPS
    assert (dropped, composed, absorbed, span) == (0, 1, 3, 3)


def test_composed_link_is_implied_by_the_original_chain():
    """Soundness: any profile satisfying every minted link satisfies the
    composed link — composition can never over-constrain the survivors."""
    rng = random.Random(20260729)
    for _ in range(200):
        k = rng.randint(2, 8)
        deltas = [rng.uniform(-2.0, 2.0) for _ in range(k)]
        chain = _chain(deltas)
        edges, *_ = compose_rod_chains([chain], _identity({0, k}))
        (_, _, lo, hi) = edges[0]
        # z built by walking the chain with a per-link slack inside ±ε
        z = [0.0]
        for (_, _, l_i, h_i) in chain:
            slack = rng.uniform(l_i, h_i)
            z.append(z[-1] - slack)          # link is z[a] − z[b] ∈ [l, h]
        assert lo - 1e-9 <= z[0] - z[-1] <= hi + 1e-9


# ── 3. chain ends and collapsed runs are DROPPED, never one-sided ───────

def test_chain_head_and_tail_runs_are_dropped():
    chain = _chain([0.1, 0.2, 0.3, 0.4, 0.5])       # keys 0..5
    edges, dropped, recs, composed, absorbed, span = compose_rod_chains(
        [chain], _identity({1, 4}), want_drop_records=True)
    assert len(edges) == 1
    assert edges[0][0] == 1 and edges[0][1] == 4
    assert composed == 1 and absorbed == 3 and span == 3
    # link 0 (before the first survivor) + link 4 (after the last).
    assert dropped == 2
    assert all(r[4] == "chain_end_unresolved" for r in recs)


def test_no_survivor_drops_the_whole_chain():
    chain = _chain([0.1, 0.2, 0.3])
    edges, dropped, recs, composed, absorbed, span = compose_rod_chains(
        [chain], _identity(()), want_drop_records=True)
    assert edges == [] and dropped == 3 and composed == 0
    assert len(recs) == 3


def test_run_collapsing_to_one_node_is_dropped():
    """Both survivors interning to the SAME rebuilt node leaves nothing to
    constrain — the run is dropped, not emitted as a self-edge."""
    chain = _chain([0.3, 0.3])
    edges, dropped, recs, composed, absorbed, span = compose_rod_chains(
        [chain], lambda k: (7 if k in (0, 2) else None),
        want_drop_records=True)
    assert edges == [] and dropped == 2 and composed == 0
    assert all(r[4] == "run_collapsed_to_one_node" for r in recs)


# ── 4. the LEDGER holds for every survivor pattern ─────────────────────

def test_ledger_balances_over_random_survivor_patterns():
    """``minted = carried_1to1 + absorbed + dropped`` — the audit's
    "carried + composed accounts for every minted link" acceptance."""
    rng = random.Random(4068)
    for _ in range(500):
        k = rng.randint(1, 12)
        chain = _chain([rng.uniform(-1.0, 1.0) for _ in range(k)])
        alive = {i for i in range(k + 1) if rng.random() < 0.5}
        edges, dropped, recs, composed, absorbed, span = compose_rod_chains(
            [chain], _identity(alive))
        carried_1to1 = len(edges) - composed
        assert carried_1to1 >= 0
        assert carried_1to1 + absorbed + dropped == k
        # every emitted edge joins two DISTINCT resolved nodes
        for (ia, ib, lo, hi) in edges:
            assert ia != ib and lo <= hi


def test_multiple_chains_are_independent():
    a = _chain([1.0, 1.0], first=0)          # keys 0,1,2
    b = _chain([2.0], first=10)              # keys 10,11
    edges, dropped, recs, composed, absorbed, span = compose_rod_chains(
        [a, b], _identity({0, 2, 10, 11}))
    assert sorted(edges) == [(0, 2, 2.0 - 2 * EPS, 2.0 + 2 * EPS),
                             (10, 11, 2.0 - EPS, 2.0 + EPS)]
    assert composed == 1 and absorbed == 2 and dropped == 0
