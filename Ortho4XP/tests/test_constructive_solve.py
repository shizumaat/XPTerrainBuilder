"""Twins for the constructive solve core (K1b, spec
``docs/specs/constructive-solve-spec.md`` AMENDMENT 1 — the living
band).

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
* THE LIVING BAND (A2/A4) — ``LivingBand.seed`` equals
  ``reach_envelope`` on both sides; in-band minting NEVER inverts the
  band anywhere (the amendment's induction); out-of-band values are the
  caller's refusal class, never absorbed; provenance names the anchor
  that authored every label, floor and ceiling separately.
* CERTIFIED-TIER RIDE — ``certified_pins`` pins every node a
  still-lazy entry names (body and ring), and nothing else.
* P1 SUBSTRATE — ``runway_station_chains`` orders ring vertices along
  the redistributed axis with the CIFP thresholds as the ONLY pegs
  (snapped or synthetic).

(The mode key itself — precedence, typo refusal, tile publication — is
K2's ``O4_Solve_Model``, twinned in ``tests/test_solve_model.py``; the
dispatch site here only calls ``is_constructive()``.)
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from auto_patch.elevation_per_surface.route_profile.one_solve import (
    LivingBand, envelope_radj, law_edge_limits, reach_envelope)
from auto_patch.elevation_per_surface.route_profile.constructive import (
    certified_pins, runway_station_chains, smooth_once)


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


# ── LivingBand: A2 (band-first, ordered minting) + A4 (provenance) ───

def _band_on_chain(n, lim):
    edge_lim = _chain_graph(n, lim)
    ceil_radj, floor_radj = envelope_radj(edge_lim, {})
    return LivingBand(ceil_radj, floor_radj, n), edge_lim


def test_living_band_seed_equals_reach_envelope():
    n = 8
    edge_lim = _chain_graph(n, 1.0)
    edge_lim[(1, 6)] = 0.4
    ceil_radj, floor_radj = envelope_radj(edge_lim, {})
    values = [3.0, 0, 0, 0, 0, 0, 0, 9.0]
    band = LivingBand(ceil_radj, floor_radj, n)
    band.seed({0: 3.0, 7: 9.0}, {0: "cifp:a", 7: "seam"})
    ceil, _ = reach_envelope(+1, ceil_radj, [0, 7], values, n)
    floor, _ = reach_envelope(-1, floor_radj, [0, 7], values, n)
    assert band.ceil == ceil and band.floor == floor


def test_living_band_in_band_mint_never_inverts():
    # THE AMENDMENT'S INDUCTION: accept only in-band values, and the
    # band stays non-empty at every node after every refinement.
    n = 10
    band, edge_lim = _band_on_chain(n, 1.0)
    band.seed({0: 0.0, 9: 5.0}, {0: "cifp:a", 9: "cifp:b"})
    for i in (3, 6, 1, 8):                # arbitrary priority order
        lo, hi = band.interval(i)
        v = 0.5 * (lo + hi)
        assert lo <= v <= hi
        band.add(i, v, f"mint:{i}")
        for k in range(n):
            b_lo, b_hi = band.interval(k)
            assert b_lo <= b_hi + 1e-12, (i, k, b_lo, b_hi)


def test_living_band_refusal_class_is_detectable_and_named():
    # A value outside the band is the caller's A3 refusal; A4 names the
    # two bounding anchors (floor minter and ceiling minter).
    n = 6
    band, _ = _band_on_chain(n, 1.0)
    band.seed({0: 0.0, 5: 2.0}, {0: "cifp:a", 5: "seam"})
    lo, hi = band.interval(2)
    assert lo == max(0.0 - 2, 2.0 - 3) and hi == min(0.0 + 2, 2.0 + 3)
    v = hi + 1.0                          # out of band → refuse
    assert not (lo - 1e-6 <= v <= hi + 1e-6)
    f_a, f_m, c_a, c_m = band.bounding(2)
    # floor at node 2: max(0−2, 2−3) = −1.0 → anchor 5 authors it;
    # ceiling at node 2: min(0+2, 2+3) = 2.0 → anchor 0 authors it.
    assert (f_a, f_m) == (5, "seam")
    assert (c_a, c_m) == (0, "cifp:a")


def test_living_band_non_seeding_mint_binds_nothing():
    # Witness admission: seed=False records the anchor (value + minter)
    # but refines no label — the band is unchanged.
    n = 5
    band, _ = _band_on_chain(n, 1.0)
    band.seed({0: 0.0}, {0: "cifp:a"})
    before = (dict(band.ceil), dict(band.floor))
    band.add(4, 100.0, "seat_on_spine", seed=False)
    assert (band.ceil, band.floor) == before
    assert band.anchors[4] == 100.0 and band.minter[4] == "seat_on_spine"


def test_living_band_anchor_keeps_its_own_label():
    # An accepted mint's own labels equal its value (later in-band
    # anchors can never undercut it — the induction's corollary).
    n = 7
    band, _ = _band_on_chain(n, 1.0)
    band.seed({0: 0.0, 6: 3.0}, {0: "a", 6: "b"})
    lo, hi = band.interval(3)
    band.add(3, hi, "mint:3")
    assert band.ceil[3] == hi and band.floor[3] == hi
    lo4, hi4 = band.interval(4)
    v4 = 0.5 * (lo4 + hi4)
    band.add(4, v4, "mint:4")
    assert band.ceil[3] == hi and band.floor[3] == hi


def test_living_band_deterministic_with_provenance():
    n = 20
    edge_lim = _chain_graph(n, 0.7)
    edge_lim[(0, 19)] = 5.0
    edge_lim[(3, 11)] = 0.2
    ceil_radj, floor_radj = envelope_radj(edge_lim, {})

    def run():
        band = LivingBand(ceil_radj, floor_radj, n)
        band.seed({0: 1.0, 19: 4.0}, {0: "a", 19: "b"})
        for i in (5, 12, 7):
            lo, hi = band.interval(i)
            band.add(i, 0.5 * (lo + hi), f"m:{i}")
        return (dict(band.ceil), dict(band.floor),
                dict(band.ceil_src), dict(band.floor_src))

    assert run() == run()


# ── runway_station_chains: the P1 substrate ──────────────────────────

class _FakePoly:
    def __init__(self, coords):
        self.is_empty = False
        self.exterior = type("E", (), {"coords": coords})()


class _FakeShape:
    def __init__(self, role, ref, coords):
        self.role = role
        self.ref = ref
        self.polygon = _FakePoly(coords)


class _FakeCps:
    def __init__(self):
        self._d = {}

    def get_or_add(self, x, y):
        return self._d.setdefault((round(x, 6), round(y, 6)),
                                  len(self._d))


def test_runway_station_chains_orders_and_pegs():
    from auto_patch.layout import ROLE_RUNWAY
    layout = type("L", (), {})()
    cps = _FakeCps()
    # a 100 m runway along +x, 4 corners (two stations at 0 and 100)
    ring = [(0.0, -5.0), (100.0, -5.0), (100.0, 5.0), (0.0, 5.0),
            (0.0, -5.0)]
    layout.shapes = [_FakeShape(ROLE_RUNWAY, "18/36", ring)]
    layout.canonical_points = cps
    layout._runway_redistributed_profiles = {
        "18/36": {"axis_a": (0.0, 0.0), "axis_d": (100.0, 0.0),
                  "axis_len2": 10000.0, "max_grade": 0.015,
                  # one threshold AT a ring station, one displaced
                  # 40 m in (no ring vertex → synthetic station)
                  "cifp_pins": [(0.0, 12.0), (0.4, 12.3)]}}
    b2i = {}
    for (x, y) in ring[:-1]:
        b2i[cps.get_or_add(x, y)] = len(b2i)
    chains = runway_station_chains(layout, b2i, len(b2i))
    assert len(chains) == 1
    ch = chains[0]
    assert ch.stations == [0.0, 40.0, 100.0]
    assert ch.members[0] and not ch.members[1] and ch.members[2]
    assert ch.pegs == {0: 12.0, 1: 12.3}
    assert ch.cap == 0.015


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
