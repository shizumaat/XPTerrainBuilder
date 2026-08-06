"""Twins for RULINGS 2026-08-06 "Slab budgets floor at the law".

Owner, verbatim: "smoothing beyond law as a constraint makes no sense,
that's the point of the law.  Smoothest, minimum grade is the target, but
where needed, the budget is certainly the law."

Spec: ``docs/specs/cycle75-slab-floor-spec.md``.  The pricing authority is
``one_solve.price_slab_against_law`` — ONE site, imported by the rod mint
in ``solve.py``; these twins pin its answers on cases whose answer is
known by hand, and pin the projection-level consequence the ruling exists
for: a slab bound tighter than its pair's law turns a FEASIBLE law
problem into an infeasible one, and flooring it at the law gives the
feasible answer back.

Hermetic — no build, no fixtures.
"""
import pytest

import auto_patch.config as cfg
from auto_patch.elevation_per_surface.route_profile import solve as _solve
from auto_patch.elevation_per_surface.route_profile.one_solve import (
    feasibility_project, price_slab_against_law)


# ── (a) the pricing itself, on hand-computable cases ─────────────────────

def test_slab_tighter_than_law_is_floored_to_the_law():
    """The ruling's population: |Δ| ± ε well inside the pair's budget.

    Δ = 0.5 m, ε = 0.02 m, law budget 1.0 m.  The raw window
    [0.48, 0.52] is 25x tighter than the law's [-1.0, 1.0] — the median
    HECA rod slab is 5.26x tighter.  It comes out AT the law.
    """
    lo, hi, floored, clamped = price_slab_against_law(0.5, 0.02, 1.0)
    assert (lo, hi) == (-1.0, 1.0)
    assert floored is True
    assert clamped is False


def test_floored_slab_never_narrows_freedom_below_the_law():
    """The ruling's operative sentence, as a property over the sign range.

    "A slab may narrow freedom only down TO the law, never below it": the
    priced interval must CONTAIN every value the pair's symmetric law
    edge admits, whatever Δ the rod snapshotted.
    """
    budget = 1.5
    for delta in (-9.0, -1.6, -1.5, -0.7, 0.0, 0.7, 1.5, 1.6, 9.0):
        lo, hi, _, _ = price_slab_against_law(delta, 0.02, budget)
        assert lo <= -budget and hi >= budget, delta


def test_slab_looser_than_law_is_still_clamped():
    """§10.1 (2026-07-29, CYXY service spine 6.2 %) is not weakened.

    A rod tolerance wider than the pair's budget must not license an
    over-cap step: the slab is clamped back to the law.
    """
    lo, hi, floored, clamped = price_slab_against_law(0.0, 5.0, 1.0)
    assert (lo, hi) == (-1.0, 1.0)
    assert clamped is True
    assert floored is False


def test_snapshot_beyond_the_law_no_longer_rides_the_cap():
    """The old clamp's empty-intersection branch is gone by construction.

    A Δ far beyond the pair's budget used to be pinned into a 2ε window
    AT the cap (the "ride the ceiling" branch).  Under the floor the
    interval is the full law interval — the pair is free to come back
    inside the law from either side.
    """
    lo, hi, floored, clamped = price_slab_against_law(9.0, 0.02, 1.0)
    assert (lo, hi) == (-1.0, 1.0)
    assert hi - lo == pytest.approx(2.0)
    assert floored is True and clamped is True


def test_pair_with_no_law_edge_keeps_the_raw_rod_window():
    """33 of HECA's 7,920 rod pairs carry no symmetric law edge.

    There is no budget to floor at, so the raw window stands: the ruling
    REPRICES slabs against law, it does not retire the channel where no
    law is present.
    """
    lo, hi, floored, clamped = price_slab_against_law(0.5, 0.02, None)
    assert (lo, hi) == pytest.approx((0.48, 0.52))
    assert floored is False and clamped is False


def test_slab_exactly_at_the_law_reports_neither_flag():
    lo, hi, floored, clamped = price_slab_against_law(0.0, 1.0, 1.0)
    assert (lo, hi) == (-1.0, 1.0)
    assert floored is False and clamped is False


# ── (b) ONE pricing site — the rod mint imports it, never re-derives ─────

def test_rod_mint_uses_the_one_pricing_site():
    """``solve`` prices its rod slabs through ``one_solve``'s authority.

    The ruling asks for one clamp site at the minting/pricing authority;
    a second copy of the arithmetic in the mint loop is exactly the
    drift this asserts against.
    """
    assert _solve.price_slab_against_law is price_slab_against_law


# ── (c) the projection-level consequence, with a known answer ────────────

@pytest.fixture(params=[True, False], ids=["chromatic", "scalar"])
def _sweep_path(request, monkeypatch):
    monkeypatch.setattr(cfg, "CHROMATIC_PROJECTION", request.param)
    return request.param


def _three_node_case(slab):
    """Two hard anchors 2 m apart over two 1 m-budget law edges.

    ``z0 = 100`` and ``z2 = 102`` are hard; the symmetric law edges
    ``|z0 − z1| ≤ 1`` and ``|z1 − z2| ≤ 1`` leave exactly one feasible
    value, ``z1 = 101``.  ``slab`` is the rod's signed interval on
    ``z0 − z1``, appended as its own envelope-skip entry the way the
    mint registers it.
    """
    law = [(0, 1, 1.0), (1, 2, 1.0)]
    entries = [{"edges": law},
               {"edges": [(0, 1, slab[0], slab[1])], "envelope_skip": True}]
    elev = [100.0, 100.0, 102.0]
    rem, both_hard = feasibility_project(elev, entries, {0, 2},
                                         force_scalar=True)
    return elev, rem, both_hard


def test_law_only_case_is_feasible(_sweep_path):
    """The control: no rod at all, the law alone is satisfiable."""
    law = [(0, 1, 1.0), (1, 2, 1.0)]
    elev = [100.0, 100.0, 102.0]
    rem, _ = feasibility_project(elev, [{"edges": law}], {0, 2},
                                 force_scalar=True)
    assert rem == 0
    assert elev[1] == pytest.approx(101.0)


def test_tighter_than_law_slab_makes_a_feasible_case_infeasible(_sweep_path):
    """The defect the ruling names, reproduced at three nodes.

    The rod snapshots Δ = z0 − z1 = 0 and prices ±0.02 m around it —
    50x tighter than the pair's own 1 m law budget, where the median
    HECA rod slab was 5.26x tighter.  The projection now reports an
    UNCERTIFIED exit on a problem the LAW satisfies exactly: both
    symmetric law edges end up satisfied and the surviving violation is
    the smoothing slab's own.  A refinement that mints violations the
    law does not have is the surface authority the string purpose
    statement (RULINGS 2026-08-01) forbids, and at HECA that class was
    6,300 over-cap edges — 31.5 % of the converged fp#8 residual.
    """
    elev, rem, _ = _three_node_case((-0.02, 0.02))
    assert rem > 0
    assert abs(elev[0] - elev[1]) <= 1.0 + 1e-9      # law edge satisfied
    assert abs(elev[1] - elev[2]) <= 1.0 + 1e-9      # law edge satisfied
    assert abs(elev[0] - elev[1]) > 0.02             # the SLAB is violated


def test_floored_slab_restores_the_lawful_answer(_sweep_path):
    """The ruling applied to the same case, through the one pricing site.

    Priced against the pair's 1 m budget the slab floors to the law, the
    projection recovers the unique lawful value, and nothing is over cap.
    """
    lo, hi, floored, _ = price_slab_against_law(0.0, 0.02, 1.0)
    assert floored is True
    elev, rem, _ = _three_node_case((lo, hi))
    assert rem == 0
    assert elev[1] == pytest.approx(101.0)
