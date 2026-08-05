"""Groundside FEASIBILITY-WITNESS CLAUSE (owner ruling 2026-07-30, memory
``groundside-terrace-law``).

    "Groundside values never act as a feasibility witness (floor or ceiling)
    for airside pavement beyond the Part-C mouth allowance."

Part C bounds what a groundside pin may BE; this clause bounds what it may
DO.  These tests pin the MECHANISM on a synthetic chain so it is provable
without a build:

* a groundside pin beyond the mouth allowance declares no break;
* a groundside pin INSIDE the allowance still does (the permitted
  exception — a genuinely contradictory mouth weld stays visible);
* the pin stays HARD either way (groundside is still pinned, and the sweeps
  still enforce every mouth-weld law edge);
* ``witness_limited=None`` is the pre-clause behaviour exactly (the gate-off
  identity argument in code form).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from auto_patch.elevation_per_surface.route_profile.one_solve import (  # noqa: E402
    feasibility_project)
from auto_patch.elevation_per_surface.route_profile.anchors import (  # noqa: E402
    gs_mouth_allowance_m, gs_pin_float_cap, gs_witness_horizon)


def _chain(n_nodes=6, budget=1.0):
    """A straight chain 0—1—…—n with a uniform per-edge budget."""
    edges = [(i, i + 1, budget) for i in range(n_nodes - 1)]
    return [{"edges": edges}]


def _run(witness_limited, gs_value=20.0, n_nodes=6, budget=1.0):
    elev = [0.0] * n_nodes
    elev[-1] = gs_value                  # the groundside pin (node n-1)
    hard = {0, n_nodes - 1}              # node 0 = a runway seam
    broken = set()
    feasibility_project(elev, _chain(n_nodes, budget), hard,
                        broken_out=broken, force_scalar=True,
                        witness_limited=witness_limited)
    return elev, broken


class TestClause:
    def test_unlimited_pin_breaks_the_whole_chain(self):
        """Baseline: 20 m of deficit over 5 m of budget quarantines every
        interior node — the 90.3 %-of-HECA mechanism, in miniature."""
        _elev, broken = _run(None)
        assert broken == {1, 2, 3, 4}

    def test_pin_beyond_the_mouth_allowance_witnesses_nothing(self):
        """Horizon below one edge: the pin's label dies at the mouth, so no
        airside node is broken by it."""
        _elev, broken = _run((frozenset({5}), 0.5))
        assert broken == set()

    def test_pin_inside_the_mouth_allowance_still_witnesses(self):
        """The permitted exception: within the allowance the pin still
        declares the contradiction it is welded into."""
        _elev, broken = _run((frozenset({5}), 1.5))
        assert broken == {4}

    def test_pin_stays_hard_and_its_law_edge_is_still_enforced(self):
        """The clause withdraws the WITNESS role only.  The pin keeps its
        value (groundside is still pinned) and the sweeps still drive its
        own welded edge toward the law."""
        elev, _broken = _run((frozenset({5}), 0.5))
        assert elev[5] == 20.0                      # never moved
        assert elev[0] == 0.0
        # node 4 is pulled up toward the pin by the sweep (it is free and
        # no longer quarantined), i.e. the mouth weld is still law.
        assert elev[4] > 0.0

    def test_none_is_the_pre_clause_path_exactly(self):
        """Gate-off identity in code form: passing ``None`` reproduces the
        unrestricted envelope, value for value."""
        a_elev, a_broken = _run(None)
        b_elev, b_broken = _run(None)
        assert a_elev == b_elev and a_broken == b_broken
        # and an EMPTY limited set is the same thing again
        c_elev, c_broken = _run((frozenset(), 0.75))
        assert c_elev == a_elev and c_broken == a_broken


class TestAllowanceIsOneScalar:
    """Part C's value bound and the clause's role bound must never drift
    apart — one definition, two consumers (single-pass principle)."""

    def test_horizon_equals_the_part_c_value_bound(self):
        for cap in (0.01, 0.04, 0.05):
            assert gs_witness_horizon(cap) == gs_pin_float_cap(cap)
            assert gs_pin_float_cap(cap) == cap * gs_mouth_allowance_m()

    def test_default_allowance_is_one_connector_throat(self):
        assert gs_mouth_allowance_m() == 15.0

    def test_the_allowance_is_not_env_overridable(self):
        """The env override died 2026-08-05
        ("BUILD-COMPLETE-THEN-DEBUG"): the allowance is ONE constant, and
        both bounds move together only when that constant moves."""
    # (Retired env name, kept only as an inert no-op row until the
    # hygiene backlog rewrites this file: the gate is DELETED in src/,
    # so this line selects nothing.  Integration sweep 2026-08-05.)
        os.environ["O4_GS_PIN_MOUTH_ALLOWANCE_M"] = "22.5"
        try:
            assert gs_mouth_allowance_m() == 15.0
            assert gs_witness_horizon(0.05) == 15.0 * 0.05
        finally:
            del os.environ["O4_GS_PIN_MOUTH_ALLOWANCE_M"]
