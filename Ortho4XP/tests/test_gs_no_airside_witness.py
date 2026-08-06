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

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from auto_patch.elevation_per_surface.route_profile.one_solve import (  # noqa: E402
    feasibility_project)
from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    anchors as _anchors)
from auto_patch.elevation_per_surface.route_profile.anchors import (  # noqa: E402
    gs_mouth_allowance_m, gs_pin_float_cap, gs_pin_law_ceiling,
    gs_witness_horizon)


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


class TestTheCeilingDatumIsTheWeldNotTheDem:
    """Item 3(a), 2026-08-05 — RULINGS "DEM's role, and the constant-DEM
    invariant": *"DEM chooses WHERE in the lawful band a thing seats.  It
    never shapes the band, never constrains, never blocks."*

    Part C's VALUE bound used to be ``own DEM sample + cap·15 m``,
    published as a real solver bound (``layout._gs_pin_dem_ceiling_idx`` →
    ``feasibility_project``'s ``node_bounds``).  The ALLOWANCE is
    unchanged; the DATUM is now the surface the pin welds to — a SOLVED
    pavement variable."""

    def test_the_ceiling_is_the_reach_law_plus_one_throat(self):
        assert gs_pin_law_ceiling(100.0, 50.0, 0.08) == pytest.approx(
            100.0 + 0.08 * (50.0 + 15.0))

    def test_the_allowance_is_exactly_the_part_c_scalar(self):
        """Replace only the datum: at zero route length the ceiling sits
        one ``gs_pin_float_cap`` above the weld datum."""
        for cap in (0.01, 0.05, 0.08):
            assert (gs_pin_law_ceiling(207.5, 0.0, cap) - 207.5
                    == pytest.approx(gs_pin_float_cap(cap)))

    def test_the_ceiling_takes_no_terrain_input_at_all(self):
        """THE CONSTANT-DEM ORACLE, BY INSPECTION.  The signature admits a
        solved host datum, a route length and a law cap — there is no
        parameter a DEM sample could enter through, so the ceiling is
        identical in the plateau and canyon worlds."""
        import inspect
        params = list(inspect.signature(gs_pin_law_ceiling)
                      .parameters)
        assert params == ["host_datum", "route_len_m", "cap"]
        body = inspect.getsource(gs_pin_law_ceiling).split('"""')[-1]
        assert "dem" not in body.lower()

    def test_the_ceiling_moves_with_the_host_and_nothing_else(self):
        base = gs_pin_law_ceiling(100.0, 30.0, 0.08)
        assert gs_pin_law_ceiling(112.0, 30.0, 0.08) - base == \
            pytest.approx(12.0)

    def test_the_reach_pass_publishes_a_law_ceiling_not_a_dem_one(self):
        """The producer is renamed with its datum: nothing in the tree may
        still say ``dem`` about this bound, and the pass must build it
        through :func:`gs_pin_law_ceiling`."""
        import inspect
        src = inspect.getsource(_anchors.apply_groundside_reach)
        assert "layout._gs_pin_law_ceiling_idx" in src
        assert "layout._gs_pin_dem_ceiling_idx" not in src
        assert "layout._gs_pin_dem_ceiling_key" not in src
        assert "gs_pin_law_ceiling(" in src

    def test_the_mouth_relax_consumer_reads_the_renamed_bound(self):
        """A rename that misses the consumer silently drops the bound
        (``getattr(..., None) or {}``) — pin both sides."""
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve
        src = inspect.getsource(solve)
        assert '"_gs_pin_law_ceiling_idx"' in src
        assert "_gs_pin_dem_ceiling_idx" not in src

    def test_a_pin_with_no_weld_datum_gets_no_ceiling(self):
        """The owner-directed disposition: where no host datum resolves the
        honest answer is NO CEILING.  A missing datum must never fall back
        to the DEM sample — that fallback IS the defect."""
        import inspect
        src = inspect.getsource(_anchors.apply_groundside_reach)
        assert "no weld datum → unbounded above" in src


# ── NO GROUNDSIDE HARD PIN AT RAW DEM (cycle-5 spec fix 3) ─────────────

def test_the_groundside_pin_is_not_in_the_solves_immovable_sets():
    """THE fix-3 twin, asserted at the SITE.

    ``gs_pin`` has exactly ONE source: ``anchors.apply_groundside_reach``
    returns a weld set (two ``hard.add`` sites) that the solve bound as
    ``_gs_hard`` and tagged ``gs_pin``.  Its value is the piece's
    closest-to-DEM REACHABLE level, which on a constant-DEM world IS the
    raw DEM — so the anchor was DEM acting as a constraint (RULINGS
    2026-08-05: "DEM is a SEED, never a constraint, never an authority")
    and groundside pulling airside ("airside is king").

    Measured at HECA plateau: all 70 out-of-band hard nodes were
    ``gs_pin``; 25 sat exactly on the constant DEM; the single worst
    over-cap row in the solve (93.125 m) was one of them dragging an
    in-band building seat.

    The failure mode if this regresses is silent — the pin would simply
    re-anchor and every count would still look plausible — so the twin
    reads the source at both immovable sites rather than a value.
    """
    import inspect
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.solve_route_profile)

    # the early groundside re-projection's hard set
    blk = src[src.index("_ghard = hard | {i for i in runway_nodes"):]
    blk = blk[:blk.index("feasibility_project")]
    assert "_gs_hard" not in blk, "gs_pin must not re-enter _ghard"

    # fp#8's immovable set
    y = src[src.index("yield_hard = (truth_hard"):]
    y = y[:y.index(")\n") + 1]
    assert "_gs_hard" not in y, "gs_pin must not re-enter yield_hard"


def test_the_freed_groundside_pin_is_bounded_by_its_law_ceiling():
    """Demoted is not unbounded.  A freed pin carries the LAW ceiling the
    reach already computed — the weld datum plus one throat of reach, with
    NO DEM term — through the ratified bounded-yield channel."""
    import inspect
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.solve_route_profile)
    blk = src[src.index("THE FREED GROUNDSIDE PINS ARE BOUNDED"):]
    blk = blk[:blk.index("ADJACENT-GROUND: ONE AUTHORITY")]
    body = "\n".join(ln for ln in blk.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "_gs_pin_law_ceiling_idx" in body
    assert "_yield_node_bounds" in body
    # the ceiling is a LAW quantity: no terrain source may reach it.
    for terrain in ("dem_elev", "dem[", "dem_seed", "_dem_z"):
        assert terrain not in body, f"a law ceiling carries no {terrain}"


def test_the_kept_hard_classes_are_still_hard():
    """Fix 3 demotes ONE class.  Boundary/seam and CIFP truth keep their
    own law and must not be swept in with it."""
    import inspect
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.solve_route_profile)
    y = src[src.index("yield_hard = (truth_hard"):]
    y = y[:y.index(")\n") + 1]
    assert "truth_hard" in y          # seed_rwy_seam (CIFP + tile seam),
    assert "runway_nodes" in y        # rwy_join / rwy_flexed
    assert "building_seats" in y      # seat_on_spine
