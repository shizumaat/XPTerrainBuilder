"""The feasibility envelope reads THE centerline graph's reach band.

Owner ruling 2026-07-30 (docs/specs/envelope-uses-the-centerline-graph-spec.md):
"Feasibility and reach must only follow actual taxi route centerlines… We
already have the graph, use it, don't duplicate it."  ``feasibility_project``
therefore takes its ``[floor, ceiling]`` from ``env_band`` — the per-node
``reach_band_unified`` sampling the build already computed — instead of a
transitive closure over the within-shape pavement PAIR graph.

These are the SEMANTIC gates the spec fixes, on graphs small enough to reason
about by hand:
  * a node the pair closure calls infeasible but the band admits is NOT broken,
    and is clamped into the BAND's interval (the closure interval is still
    empty there, so re-sourcing only the break predicate is not isolable);
  * off-net (band ``None``) is NOT broken and NOT envelope-clamped — the local
    within-shape law governs;
  * a band that INVERTS is the only thing that declares a break;
  * the bound is on FEASIBILITY only: every pair constraint still enforces in
    the sweeps and in the final RAW-budget tally;
  * gate off / no band ⇒ the pair-closure envelope, unchanged.

★ ONE DOCUMENTED DEFAULT (spec ``route-metric-envelope`` §1, 2026-08-01).
``O4_ENVELOPE_FROM_BAND`` used to read default ``"0"`` in ``solve.py`` and
default ``"1"`` in ``feasibility_project`` — the same name meaning two
things depending on who asked.  The surviving default is production's
``"0"``, resolved once by ``one_solve.envelope_from_band_enabled``, so the
BAND-SEMANTIC tests below now turn the gate on explicitly instead of
riding a default that no longer exists.  The semantics they assert are
unchanged.
"""
import pytest

from auto_patch.elevation_per_surface.route_profile.one_solve import (
    envelope_from_band_enabled, feasibility_project,
    route_metric_envelope_enabled)


def _chain(budget=1.0):
    """0 —b— 1 —b— 2 —b— 3, ends hard 50 m apart: the closure quarantines the
    interior (floor > ceiling by ~46 m) exactly like a real break region."""
    return [{"edges": [(0, 1, budget), (1, 2, budget), (2, 3, budget)]}]


def test_pair_closure_is_the_default_without_a_band():
    elev = [0.0, 0.0, 0.0, 50.0]
    broken = set()
    feasibility_project(elev, _chain(), {0, 3}, force_scalar=True,
                        max_iters=200, broken_out=broken)
    assert broken == {1, 2}, "the closure must still quarantine without a band"


def test_band_feasible_node_is_not_broken(monkeypatch):
    """The 13,056-node case: the closure interval is EMPTY here (see
    ``test_pair_closure_is_the_default_without_a_band``) and the band admits
    the node, so nothing is quarantined and the sweeps own the surface."""
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    elev = [0.0, 0.0, 0.0, 50.0]
    band = [None, (10.0, 20.0), (30.0, 40.0), None]
    broken = set()
    feasibility_project(elev, _chain(), {0, 3}, force_scalar=True,
                        max_iters=400, broken_out=broken, env_band=band)
    assert broken == set(), "the band admits both interior nodes"
    # freed, not frozen: the interior is no longer pinned at the closure
    # blend the quarantine would have written.
    assert elev[1] != elev[2]


def test_the_clamp_is_re_sourced_from_the_band(monkeypatch):
    """★ "The clamp moves with the declaration."  With slack budgets the
    sweeps have nothing to do, so what survives IS the envelope clamp — and
    it must be the BAND's interval, not the closure's."""
    loose = [{"edges": [(0, 1, 100.0), (1, 2, 100.0), (2, 3, 100.0)]}]
    band = [None, (10.0, 20.0), (30.0, 40.0), None]

    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    on = [0.0, 0.0, 0.0, 50.0]
    feasibility_project(on, loose, {0, 3}, force_scalar=True, max_iters=400,
                        env_band=band)
    assert on[1] == pytest.approx(10.0), on
    assert on[2] == pytest.approx(30.0), on

    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "0")
    off = [0.0, 0.0, 0.0, 50.0]
    feasibility_project(off, loose, {0, 3}, force_scalar=True, max_iters=400,
                        env_band=band)
    assert off[1] == pytest.approx(0.0), "the closure admits 0.0 and clamps"
    assert off[2] == pytest.approx(0.0), off


def test_off_net_is_not_envelope_clamped(monkeypatch):
    """Off-net ⇒ the LOCAL within-shape law governs: no break, and no
    envelope clamp either (there is no interval to source one from)."""
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    loose = [{"edges": [(0, 1, 100.0), (1, 2, 100.0), (2, 3, 100.0)]}]
    elev = [0.0, 7.0, 0.0, 50.0]
    band = [None, None, (30.0, 40.0), None]
    broken = set()
    feasibility_project(elev, loose, {0, 3}, force_scalar=True,
                        max_iters=400, broken_out=broken, env_band=band)
    assert broken == set()
    assert elev[1] == pytest.approx(7.0), "off-net node left alone"
    assert elev[2] == pytest.approx(30.0), "on-net node clamped into its band"


def test_only_a_band_inversion_declares_a_break(monkeypatch):
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    elev = [0.0, 0.0, 0.0, 50.0]
    band = [None, (25.0, 5.0), (30.0, 40.0), None]      # node 1 inverted
    broken = set()
    feasibility_project(elev, _chain(), {0, 3}, force_scalar=True,
                        max_iters=400, broken_out=broken, env_band=band)
    assert broken == {1}
    # the blend lands inside the inverted interval it reports
    assert 5.0 - 1e-6 <= elev[1] <= 25.0 + 1e-6, elev


def test_pair_constraints_still_enforce_and_still_tally(monkeypatch):
    """This bounds FEASIBILITY, not the surface law: a pair the band cannot
    reconcile is still swept and still reported against the RAW budget."""
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    elev = [0.0, 0.0, 0.0, 50.0]
    band = [None, (10.0, 20.0), (30.0, 40.0), None]
    rem, bh = feasibility_project(elev, _chain(), {0, 3}, force_scalar=True,
                                  max_iters=400, env_band=band)
    assert rem > 0, "the 50 m drop over 3 one-metre budgets cannot vanish"
    # And the sweeps did run the local law: adjacent free nodes were pulled
    # as close together as the boxes allow (10 m apart, not 30).
    assert abs(elev[2] - elev[1]) <= 30.0 + 1e-6


def test_gate_off_is_the_pair_closure(monkeypatch):
    band = [None, (10.0, 20.0), (30.0, 40.0), None]
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "0")
    elev = [0.0, 0.0, 0.0, 50.0]
    broken = set()
    feasibility_project(elev, _chain(), {0, 3}, force_scalar=True,
                        max_iters=200, broken_out=broken, env_band=band)
    assert broken == {1, 2}, "gate off must ignore the band entirely"


def test_gate_off_is_byte_identical_to_no_band(monkeypatch):
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "0")
    band = [None, (10.0, 20.0), (30.0, 40.0), None]
    a = [0.0, 0.0, 0.0, 50.0]
    b = [0.0, 0.0, 0.0, 50.0]
    ra = feasibility_project(a, _chain(), {0, 3}, force_scalar=True,
                             max_iters=200, env_band=band)
    rb = feasibility_project(b, _chain(), {0, 3}, force_scalar=True,
                             max_iters=200)
    assert ra == rb
    assert a == b


def test_flat_group_members_ride_their_representative(monkeypatch):
    """A rigid pad's members are aliased onto the representative; the band
    path must not clamp them individually or the flatness invariant breaks."""
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    edges = [(0, 1, 1.0), (1, 2, 1.0), (2, 3, 1.0), (3, 4, 1.0)]
    elev = [0.0, 0.0, 0.0, 0.0, 50.0]
    # nodes 1,2,3 are one pad; give the members mutually exclusive bands.
    band = [None, (10.0, 12.0), (80.0, 90.0), (20.0, 22.0), None]
    broken = set()
    feasibility_project(elev, [{"edges": edges}], {0, 4}, force_scalar=True,
                        max_iters=400, flat_groups=[{1, 2, 3}],
                        broken_out=broken, env_band=band)
    assert broken == set(), "no member's own band may quarantine the pad"
    assert elev[1] == elev[2] == elev[3], "the pad must still emit FLAT"


def test_one_documented_default(monkeypatch):
    """★ Spec ``route-metric-envelope`` §1: "one default, defined once,
    documented; the historical '0'/'1' split dies."

    The flag has exactly ONE resolver and ONE default, and the default is
    OFF — so an unset environment gets the pair-closure envelope even when
    a band is handed in, at EVERY call site (this is the property the old
    ``solve.py``-"0"-vs-``one_solve.py``-"1" split violated).  The
    route-metric gate implies it."""
    monkeypatch.delenv("O4_ENVELOPE_FROM_BAND", raising=False)
    monkeypatch.delenv("O4_ROUTE_METRIC_ENVELOPE", raising=False)
    assert envelope_from_band_enabled() is False
    assert route_metric_envelope_enabled() is False

    elev = [0.0, 0.0, 0.0, 50.0]
    broken = set()
    feasibility_project(elev, _chain(), {0, 3}, force_scalar=True,
                        max_iters=400, broken_out=broken,
                        env_band=[None, (10.0, 20.0), (30.0, 40.0), None])
    assert broken == {1, 2}, "unset ⇒ the pair closure, band ignored"

    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    assert envelope_from_band_enabled() is True
    monkeypatch.delenv("O4_ENVELOPE_FROM_BAND")
    monkeypatch.setenv("O4_ROUTE_METRIC_ENVELOPE", "1")
    assert route_metric_envelope_enabled() is True
    assert envelope_from_band_enabled() is True, (
        "the route-metric gate IS the band envelope (spec §1)")
