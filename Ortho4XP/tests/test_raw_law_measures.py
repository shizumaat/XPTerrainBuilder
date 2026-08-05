"""Twins for the SEED-FIX round §1 — RAW LAW MEASURES (spec
``docs/specs/seed-fix-round-spec.md`` §1).

THE DEFECT.  ``_margined_budget`` subtracts the 0.01 m emit-quantization
margin from EVERY edge's budget.  That is correct PER PAIR at emit — one
0.01 m grid step — but the reach/envelope quantities the solver *measures*
are PATH quantities, so the margin compounds: an N-hop route loses
``N × margin`` of envelope that no law ever took.  Measured at HEAZ
(``seed_attrib/``): the default arm's stall adjudication read "593 of 2032
INFEASIBLE, max gap 0.7275 m" while the same system's RAW envelope is
"0 of 2032, gap 0.000000".

  (a) the compounding synthetic — an N-hop path RAW-feasible and
      MARGINED-infeasible: the adjudication is RED in the margined frame
      and GREEN in the law frame;
  (b) the instrument is inert: handing ``_project_chromatic`` the raw
      column changes no solved value;
  (c) the surface gate ``O4_RAW_LAW_SWEEPS`` is default OFF and, on, makes
      the sweeps enforce RAW budgets;
  (d) §1b LEAD AMENDMENT — the emit snap is LAW-AWARE per pair: a pair
      sitting at EXACTLY its raw cap snaps to a lawful pair, and the
      over-cap count on a snap-only synthetic is ZERO.
"""
import numpy as np
import pytest

from auto_patch.elevation_per_surface.route_profile import one_solve as OS


# ── helpers ──────────────────────────────────────────────────────────────

def _chain_columns(hops, raw_budget, margin, drop):
    """An ``hops``-hop chain 0..hops with both ends PINNED (weight 0 on
    every incident edge, which is how ``_stall_envelope_gap`` recognises an
    immovable node) and a total value drop of ``drop`` across it.

    Returns ``(endpoint_i, endpoint_j, raw_col, margined_col, mask, wi, wj,
    z, n, pairs)``.
    """
    n = hops + 1
    ei, ej, wi, wj = [], [], [], []
    for k in range(hops):
        ei.append(k)
        ej.append(k + 1)
        # kind 1 / 2 semantics: an endpoint that is an END of the chain is
        # pinned (weight 0.0); interior endpoints move (weight 0.5).
        wi.append(0.0 if k == 0 else 0.5)
        wj.append(0.0 if k == hops - 1 else 0.5)
    raw_col = np.full(hops, float(raw_budget))
    margined_col = np.array(
        [OS._margined_budget(float(raw_budget), margin) for _ in range(hops)])
    z = np.zeros(n)
    z[-1] = -float(drop)
    return (np.asarray(ei, dtype=np.intp), np.asarray(ej, dtype=np.intp),
            raw_col, margined_col, np.zeros(hops, dtype=bool),
            np.asarray(wi), np.asarray(wj), z, n, [(0, hops)])


# ── (a) the margin-compounding synthetic ─────────────────────────────────

def test_margin_compounds_along_a_path_and_the_law_frame_does_not():
    """69 hops x 0.02 m raw budget = 1.38 m of law envelope; the SAME path
    margined at 0.01 m carries only 0.69 m.  A 1.00 m end-to-end drop is
    therefore LAWFUL and MARGINED-INFEASIBLE — the exact shape that burned
    3983 sweeps at HEAZ."""
    pytest.importorskip("scipy")
    hops, raw_b, margin, drop = 69, 0.02, 0.01, 1.00
    ei, ej, raw_col, marg_col, mask, wi, wj, z, n, pairs = _chain_columns(
        hops, raw_b, margin, drop)
    assert hops * raw_b > drop, "the synthetic must be RAW-feasible"
    assert hops * OS._margined_budget(raw_b, margin) < drop, (
        "the synthetic must be MARGINED-infeasible")

    margined = OS._stall_envelope_gap(np, ei, ej, marg_col, mask, wi, wj,
                                      z, n, pairs)
    raw = OS._stall_envelope_gap(np, ei, ej, raw_col, mask, wi, wj,
                                 z, n, pairs)
    assert margined is not None and raw is not None
    # RED in the margined frame — the instrument's pre-fix reading.
    assert margined["infeasible"] > 0, (
        "the margined frame must mint an INFEASIBLE class here — that is "
        "the defect this round retires")
    assert margined["max_gap"] > 0.3
    # GREEN in the law frame.
    assert raw["infeasible"] == 0, (
        "the RAW law envelope of a raw-feasible chain is feasible")
    assert raw["max_gap"] == 0.0
    for (_a, _b, ga, gb) in raw["pairs"]:
        assert max(ga, gb) <= 1e-9


def test_the_margin_theft_scales_with_path_length():
    """PER-PAIR the margin is one grid step; PER PATH it is N steps.  The
    envelope deficit the margined frame invents grows linearly in hops —
    which is why it is a measurement error and not a tolerance."""
    pytest.importorskip("scipy")
    gaps = []
    for hops in (10, 40, 80):
        ei, ej, _raw, marg, mask, wi, wj, z, n, pairs = _chain_columns(
            hops, 0.02, 0.01, 0.0)
        v = OS._stall_envelope_gap(np, ei, ej, marg, mask, wi, wj, z, n,
                                   pairs)
        # zero drop: the anchors agree, so any gap is pure instrument.
        gaps.append(v["max_gap"])
    assert gaps == [0.0, 0.0, 0.0], (
        "with the anchors in agreement even the margined frame is feasible")
    # now give each length the SAME 0.15 m drop and watch the margined
    # verdict flip purely on hop count.
    verdicts = []
    for hops in (10, 40, 80):
        ei, ej, _raw, marg, mask, wi, wj, z, n, pairs = _chain_columns(
            hops, 0.02, 0.01, 0.15)
        verdicts.append(
            OS._stall_envelope_gap(np, ei, ej, marg, mask, wi, wj, z, n,
                                   pairs)["infeasible"])
    assert verdicts[0] > 0 and verdicts[-1] == 0, (
        "a SHORT margined path condemns what a long one clears — the "
        "signature of a compounding measurement error")


# ── (b) the instrument half is value-inert ───────────────────────────────

def test_raw_budget_column_changes_no_solved_value():
    """§1a is a MEASUREMENT fix.  Handing the projection the raw column
    must not move a single elevation — if it does, it grades, and the
    round's STOP rule fires."""
    def _system():
        elev = [0.0, 5.0, 5.0, 5.0, 0.0]
        iter_edges = [(0, 1, 1.0, 1), (1, 2, 1.0, 0), (2, 3, 1.0, 0),
                      (3, 4, 1.0, 2)]
        return elev, iter_edges, 5

    elev_a, edges_a, n = _system()
    stats_a: dict = {}
    OS._project_chromatic(elev_a, edges_a, n, 4000, 1e-3, stats=stats_a)

    elev_b, edges_b, n = _system()
    stats_b: dict = {}
    OS._project_chromatic(elev_b, edges_b, n, 4000, 1e-3, stats=stats_b,
                          raw_budget_by_index=[2.0, 2.0, 2.0, 2.0])

    assert elev_a == elev_b
    assert stats_a["sweeps"] == stats_b["sweeps"]
    assert stats_a["worst"] == stats_b["worst"]
    assert stats_a["certified"] == stats_b["certified"]


def test_raw_budget_column_absent_is_the_old_behaviour():
    """``raw_budget_by_index=None`` (and an all-``None`` list) must leave
    the adjudication reading the sweep column exactly as before."""
    elev = [0.0, 5.0]
    edges = [(0, 1, 1.0, 1)]
    stats: dict = {}
    OS._project_chromatic(elev, edges, 2, 10, 1e-3, stats=stats,
                          raw_budget_by_index=[None])
    assert elev == [0.0, 1.0]


# ── (c) the surface gate ─────────────────────────────────────────────────

def test_raw_law_sweeps_gate_defaults_off(monkeypatch):
    monkeypatch.delenv("O4_RAW_LAW_SWEEPS", raising=False)
    assert OS.raw_law_sweeps_enabled() is False
    monkeypatch.setenv("O4_RAW_LAW_SWEEPS", "1")
    assert OS.raw_law_sweeps_enabled() is True


def test_raw_law_sweeps_makes_the_sweeps_enforce_raw_budgets(monkeypatch):
    """Gate ON ⇒ the sweep budget IS the raw budget (no margin term), so a
    pair solved exactly AT cap is no longer pushed a margin inside it."""
    monkeypatch.setenv("O4_QUANT_MARGIN", "0.01")
    monkeypatch.delenv("O4_RAW_LAW_SWEEPS", raising=False)
    elev = [0.0, 5.0]
    OS.feasibility_project(elev, [{"edges": [(0, 1, 1.0)]}], {0})
    margined_result = elev[1]

    monkeypatch.setenv("O4_RAW_LAW_SWEEPS", "1")
    elev = [0.0, 5.0]
    OS.feasibility_project(elev, [{"edges": [(0, 1, 1.0)]}], {0})
    raw_result = elev[1]

    assert margined_result == pytest.approx(0.99, abs=1e-9), (
        "default: the sweep enforces budget - margin")
    assert raw_result == pytest.approx(1.00, abs=1e-9), (
        "gate ON: the sweep enforces the RAW law budget")


# ── (d) §1b LEAD AMENDMENT — the emit snap is LAW-AWARE per pair ─────────

def test_emit_snap_keeps_a_pair_at_exact_cap_lawful():
    """A naive nearest-grid snap of a pair sitting AT its cap can round the
    two endpoints apart by a full grid step and re-mint an over-cap census
    row (the HECA emit-consensus class).  The law-aware snap chooses the
    rounding DIRECTION per pair, so the snapped pair never exceeds the raw
    cap."""
    from auto_patch.emit_snap import _nearest, law_aware_snap, snap_grid_m

    # z1 - z0 == cap exactly, and both values sit mid-grid so the naive
    # nearest-snap pushes them APART.
    cap = 0.0402
    z = {0: 1.0049, 1: 1.0049 + cap}
    assert abs(z[1] - z[0] - cap) < 1e-12
    naive = {k: _nearest(v) for k, v in z.items()}
    assert abs(naive[1] - naive[0]) - cap > 1e-9, (
        "the synthetic must actually break under a naive snap")

    snapped, report = law_aware_snap(z, [(0, 1, cap)])
    assert abs(snapped[1] - snapped[0]) <= cap + 1e-12
    assert report["over_cap_after"] == 0
    for k, v in snapped.items():
        assert abs(v - z[k]) <= snap_grid_m() + 1e-12, (
            "the guard is bounded by ONE grid step per node, by "
            "construction — it cannot compound along a path")


def test_emit_snap_census_over_cap_count_is_zero_on_a_snap_only_chain():
    """The twin the spec names: on a synthetic whose ONLY defect source is
    the snap (every pair exactly at cap on the solved field), the over-cap
    count after the law-aware snap is ZERO."""
    from auto_patch.emit_snap import _nearest, law_aware_snap

    cap = 0.0302
    z = {i: 1.0049 + i * cap for i in range(30)}
    pairs = [(i, i + 1, cap) for i in range(29)]
    naive = {k: _nearest(v) for k, v in z.items()}
    assert any(abs(naive[i] - naive[j]) - b > 1e-12 for (i, j, b) in pairs), (
        "the synthetic must actually break under a naive snap")
    snapped, report = law_aware_snap(z, pairs)
    over = [(i, j) for (i, j, b) in pairs
            if abs(snapped[i] - snapped[j]) - b > 1e-12]
    assert over == []
    assert report["over_cap_after"] == 0


def test_emit_snap_is_bounded_by_one_grid_step_per_node():
    """The property that makes the guard a REPLACEMENT for the margin: the
    correction is per-NODE bounded, so a 69-hop path loses at most one
    grid step end-to-end, never 69."""
    from auto_patch.emit_snap import law_aware_snap, snap_grid_m

    cap = 0.0201
    z = {i: 0.0049 + i * cap for i in range(70)}
    pairs = [(i, i + 1, cap) for i in range(69)]
    snapped, _report = law_aware_snap(z, pairs)
    worst = max(abs(snapped[i] - z[i]) for i in z)
    assert worst <= snap_grid_m() + 1e-12
    end_to_end = abs((snapped[69] - snapped[0]) - (z[69] - z[0]))
    assert end_to_end <= 2.0 * snap_grid_m() + 1e-12, (
        "end-to-end error is bounded by the two endpoints' own snaps — it "
        "does NOT grow with hop count (the margin did)")
