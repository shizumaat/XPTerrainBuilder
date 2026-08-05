"""The §10.1 rod LAW CLAMP: budget sourcing and slab arithmetic.

``docs/specs/s1-taut-chord-constructor-spec.md`` §10.1 premises every
taut-string rod slab on being AT MOST cap-grade.  The clamp that enforces
that premise used to look its budget up in ``shape_constraints`` only —
but a rod pair is a CONSECUTIVE STRUNG-SPINE pair, and some spine pairs
carry no symmetric law edge there at all; their only cap budget lives in
the unified spine graph (``_solve_spine_profile``'s own frame).  Measured
at SPJC: pair (10625, 9623) has a 0.0087 m spine budget and no symmetric
law edge, so its slab was minted RAW at Δ = +0.356 m ± 0.02 over a 0.58 m
pair and every downstream projection then enforced that 62 % step AS LAW
(emitted corner +0.31 m above its neighbourhood, SPJC's worst
within-shape grade row at 50.67 %).

These tests are pure arithmetic — no layout, no DEM, no build:

  * ``_rod_pair_budgets`` — tightest-wins across BOTH sources, the
    historical shape-constraints map when the gate is off;
  * ``_clamp_rod_slab`` — the ride-the-cap / tighten / pass-through rules
    the inline block used to carry.
"""
from __future__ import annotations

from auto_patch.elevation_per_surface.route_profile.solve import (
    _clamp_rod_slab, _rod_pair_budgets)

GATE = "O4_ROD_SPINE_BUDGET_CLAMP"

# The SPJC specimen (guard arm): one strung pair, spine budget only.
SPJC_PIECE = [10625, 9623]
SPJC_KEY = (9623, 10625)
SPJC_BUDGET = 0.008736


def _on(monkeypatch):
    """Default state — the gate is ON unless the environment says "0"."""
    monkeypatch.delenv(GATE, raising=False)


# ── shape_constraints sourcing (the historical lookup) ─────────────────

def _historical_case():
    """Rod pieces + a joint list exercising every historical rule:
    duplicate symmetric edges (tightest wins), a 4-tuple interval edge
    (ignored — it is a rod/interval slab, not a symmetric cap), and an
    edge on a NON-rod pair (excluded)."""
    pieces = [[1, 2, 3]]
    shape_constraints = [
        {"edges": [(1, 2, 0.05), (2, 1, 0.02)]},          # duplicates
        {"edges": [(2, 3, 0.30), (2, 3, 0.30, 0.40)]},    # 4-tuple ignored
        {"edges": [(7, 8, 0.001)]},                       # non-rod pair
    ]
    return pieces, shape_constraints


def test_shape_constraints_only_reproduces_the_historical_map(monkeypatch):
    _on(monkeypatch)
    pieces, sc = _historical_case()
    assert _rod_pair_budgets(pieces, sc, {}) == {(1, 2): 0.02, (2, 3): 0.30}


# ── spine-graph sourcing (the SPJC defect) ─────────────────────────────

def test_spine_adj_only_budget_is_found(monkeypatch):
    """The pair with NO symmetric law edge anywhere in the joint list —
    its budget exists only in the unified spine graph."""
    _on(monkeypatch)
    spine_adj = {10625: [(9623, SPJC_BUDGET)],
                 9623: [(10625, SPJC_BUDGET)]}
    assert _rod_pair_budgets([SPJC_PIECE], [], spine_adj) == {
        SPJC_KEY: SPJC_BUDGET}


def test_tightest_of_the_two_sources_wins(monkeypatch):
    """Both orders of magnitude: whichever source is tighter is the
    budget, never "the last one looked up"."""
    _on(monkeypatch)
    sc = [{"edges": [(9623, 10625, 0.5)]}]
    spine_adj = {10625: [(9623, SPJC_BUDGET)],
                 9623: [(10625, SPJC_BUDGET)]}
    # spine graph tighter
    assert _rod_pair_budgets([SPJC_PIECE], sc, spine_adj) == {
        SPJC_KEY: SPJC_BUDGET}
    # shape constraint tighter
    sc = [{"edges": [(9623, 10625, 0.001)]}]
    assert _rod_pair_budgets([SPJC_PIECE], sc, spine_adj) == {
        SPJC_KEY: 0.001}


def test_partner_listed_only_on_the_b_side_is_found(monkeypatch):
    """The graph is symmetric by construction, but the lookup is
    two-sided so any builder asymmetry cannot hide a budget."""
    _on(monkeypatch)
    spine_adj = {9623: [(10625, SPJC_BUDGET)]}      # nothing under 10625
    assert _rod_pair_budgets([SPJC_PIECE], [], spine_adj) == {
        SPJC_KEY: SPJC_BUDGET}


def test_gate_off_ignores_the_spine_graph(monkeypatch):
    """``O4_ROD_SPINE_BUDGET_CLAMP=0`` restores the shape-constraints-only
    lookup — the map is exactly the historical one."""
    monkeypatch.setenv(GATE, "0")
    pieces, sc = _historical_case()
    spine_adj = {1: [(2, 0.001)], 2: [(1, 0.001), (3, 0.002)],
                 3: [(2, 0.002)]}
    assert _rod_pair_budgets(pieces, sc, spine_adj) == {
        (1, 2): 0.02, (2, 3): 0.30}
    # …and ON, the same graph tightens both pairs.
    monkeypatch.setenv(GATE, "1")
    assert _rod_pair_budgets(pieces, sc, spine_adj) == {
        (1, 2): 0.001, (2, 3): 0.002}


# ── the slab arithmetic ────────────────────────────────────────────────

def test_no_budget_keeps_the_raw_slab():
    assert _clamp_rod_slab(0.356, 0.02, None) == (0.356 - 0.02,
                                                  0.356 + 0.02, False)


def test_positive_step_beyond_the_law_rides_the_cap():
    """The SPJC slab: +0.356 m against a 0.008736 m budget."""
    lo, hi, clamped = _clamp_rod_slab(0.356, 0.02, SPJC_BUDGET)
    assert clamped is True
    assert abs(lo - (SPJC_BUDGET - 0.04)) < 1e-12
    assert abs(hi - SPJC_BUDGET) < 1e-12


def test_negative_step_beyond_the_law_rides_the_cap():
    lo, hi, clamped = _clamp_rod_slab(-0.356, 0.02, SPJC_BUDGET)
    assert clamped is True
    assert abs(lo - (-SPJC_BUDGET)) < 1e-12
    assert abs(hi - (-SPJC_BUDGET + 0.04)) < 1e-12


def test_overlapping_slab_is_tightened_not_re_seated():
    """The slab still intersects ±budget ⇒ intersect, don't ride."""
    lo, hi, clamped = _clamp_rod_slab(0.03, 0.02, 0.04)
    assert clamped is True
    assert abs(lo - 0.01) < 1e-12 and abs(hi - 0.04) < 1e-12


def test_slab_inside_the_law_is_untouched():
    lo, hi, clamped = _clamp_rod_slab(0.005, 0.02, 0.05)
    assert clamped is False
    assert abs(lo - (-0.015)) < 1e-12 and abs(hi - 0.025) < 1e-12
