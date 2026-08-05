"""Twins for the DERIVED POCS SWEEP BUDGET (2026-08-05).

THE DEFECT THIS RETIRES.  The projection's sweep cap was a hand-set
constant (``PROJECTION_MAX_SWEEPS_FINAL = 2400`` and three siblings).  A
sweep cap is a NON-TERMINATION GUARD, not a law quantity — and that one
was BINDING: at composed SPJC+HECA (n = 72,472) the final scoped
projection exited UNCERTIFIED at 2400/2400 with 1,349 edges still over
cap, roughly 30x below the graph's worst-case propagation distance.  The
guard, not convergence, was choosing the emitted surface.

THE LAW OF THE FIX.  A correction propagates about one law edge per
sweep, so the budget must be derived from the graph's own hop diameter
and must sit provably above it:

    budget = clamp(SWEEP_BUDGET_SLACK * hop_eccentricity_bound(edges, n),
                   SWEEP_BUDGET_MIN, SWEEP_BUDGET_MAX)

These pin the three properties that make it a guard rather than a
tuning knob: it SCALES with hop diameter, the FLOOR holds, and the
CEILING holds.  Hermetic — no build, no fixtures.
"""
import pytest

import auto_patch.config as cfg
from auto_patch.elevation_per_surface.route_profile import one_solve as OS


def _chain(hops):
    """``hops`` edges over ``hops + 1`` nodes: a path graph whose hop
    diameter is exactly ``hops``."""
    return [(k, k + 1) for k in range(hops)], hops + 1


# ── the hop-diameter bound itself ────────────────────────────────────────

def test_the_bound_is_two_eccentricities_on_a_path():
    """A BFS from an END of a path has eccentricity == the path's own
    diameter, so the doubling is the guaranteed-safe over-estimate the
    bound advertises (never an under-estimate)."""
    for hops in (1, 7, 50):
        edges, n = _chain(hops)
        assert OS._hop_eccentricity_bound(edges, n) == 2 * hops


def test_the_bound_covers_every_component_of_a_disconnected_graph():
    """One arbitrary BFS would only have measured its own component.  The
    projection's graph is routinely disconnected (quarantined pockets,
    interval-only zone leaves, per-shape islands), so the bound must be
    the MAX over components — otherwise a long island silently gets the
    short island's budget."""
    short_edges, short_n = _chain(3)
    long_edges = [(short_n + k, short_n + k + 1) for k in range(40)]
    edges = short_edges + long_edges
    n = short_n + 41
    assert OS._hop_eccentricity_bound(edges, n) == 2 * 40


def test_isolated_nodes_do_not_inflate_the_bound():
    """A node with no incident law edge carries no correction, so it
    cannot lengthen a propagation path — padding ``n`` must not move the
    bound."""
    edges, n = _chain(10)
    assert OS._hop_eccentricity_bound(edges, n + 5000) == 2 * 10


def test_an_edgeless_graph_has_a_zero_bound():
    assert OS._hop_eccentricity_bound([], 0) == 0
    assert OS._hop_eccentricity_bound([], 100) == 0


def test_the_bound_reads_interval_edges_too():
    """Interval (signed-slab) entries carry the ``None`` budget sentinel
    in slot 2 and propagate a correction exactly like a symmetric edge,
    so only slots 0 and 1 may be read."""
    edges = [(0, 1, None, 0), (1, 2, None, 0), (2, 3, 1.0, 0)]
    assert OS._hop_eccentricity_bound(edges, 4) == 2 * 3


# ── SCALING: a longer graph gets a bigger budget ─────────────────────────

def test_the_budget_scales_with_hop_diameter():
    """THE PROPERTY THE WHOLE CHANGE EXISTS FOR: a graph that needs more
    propagation distance is GIVEN more sweeps, without anyone editing a
    constant.  Both chains here are chosen above the floor and below the
    ceiling so the clamp is not what is being measured."""
    short_edges, short_n = _chain(60)
    long_edges, long_n = _chain(300)

    short_budget, short_bound = OS.derive_sweep_budget(short_edges, short_n)
    long_budget, long_bound = OS.derive_sweep_budget(long_edges, long_n)

    assert cfg.SWEEP_BUDGET_MIN < short_budget < long_budget
    assert long_budget < cfg.SWEEP_BUDGET_MAX
    assert short_bound == 2 * 60 and long_bound == 2 * 300
    # …and the budget is exactly the advertised formula, not a fudge.
    assert short_budget == cfg.SWEEP_BUDGET_SLACK * short_bound
    assert long_budget == cfg.SWEEP_BUDGET_SLACK * long_bound


def test_the_budget_is_above_the_graphs_propagation_distance():
    """The guard's whole contract: strictly more sweeps than the hop
    diameter can need, with slack for the several passes per diameter a
    CYCLIC projection actually takes."""
    for hops in (30, 60, 120, 400):
        edges, n = _chain(hops)
        budget, bound = OS.derive_sweep_budget(edges, n)
        assert bound >= hops, "the bound must never under-state the diameter"
        assert budget > bound


# ── the FLOOR ────────────────────────────────────────────────────────────

def test_the_floor_holds_on_a_tiny_graph():
    edges, n = _chain(3)
    budget, bound = OS.derive_sweep_budget(edges, n)
    assert bound == 6
    assert budget == cfg.SWEEP_BUDGET_MIN, (
        "a graph whose derived budget is below the floor gets the floor")


def test_the_floor_holds_on_an_empty_graph():
    """A zero bound must never become a zero-sweep budget — that would
    turn an empty edge list into a silently unswept projection."""
    assert OS.derive_sweep_budget([], 0) == (cfg.SWEEP_BUDGET_MIN, 0)
    assert OS.derive_sweep_budget([], 500) == (cfg.SWEEP_BUDGET_MIN, 0)


# ── the CEILING ──────────────────────────────────────────────────────────

def test_the_ceiling_holds_on_a_pathological_graph(monkeypatch):
    """The absolute anti-hang guard.  A graph long enough to price past
    the ceiling is clamped to it, so no derivation can hang a build
    forever.  The ceiling is monkeypatched DOWN rather than building a
    31k-node chain: the clamp is what is under test, not numpy."""
    monkeypatch.setattr(OS, "SWEEP_BUDGET_MAX", 300)
    edges, n = _chain(500)                      # bound 1000, slack*bound 4000
    budget, bound = OS.derive_sweep_budget(edges, n)
    assert bound == 1000
    assert budget == 300


def test_the_ceiling_is_never_exceeded_at_any_length():
    for hops in (10, 1000, 20000):
        edges, n = _chain(hops)
        budget, _bound = OS.derive_sweep_budget(edges, n)
        assert cfg.SWEEP_BUDGET_MIN <= budget <= cfg.SWEEP_BUDGET_MAX


def test_the_floor_and_ceiling_are_ordered():
    """A misordered pair would make the clamp silently return the wrong
    end — cheap to assert, impossible to notice otherwise."""
    assert 0 < cfg.SWEEP_BUDGET_MIN < cfg.SWEEP_BUDGET_MAX
    assert cfg.SWEEP_BUDGET_SLACK >= 1


# ── the derivation reaches production ────────────────────────────────────

def test_feasibility_project_derives_its_own_budget():
    """No ``max_iters``: the projection must price its own graph and still
    drive the law to the raw budget."""
    elev = [0.0, 5.0]
    rem, both_hard = OS.feasibility_project(
        elev, [{"edges": [(0, 1, 1.0)]}], {0})
    assert (rem, both_hard) == (0, 0)
    assert elev[1] == pytest.approx(1.0, abs=1e-9)


def test_the_retired_per_role_constants_are_gone():
    """Four hand-set caps (DEFAULT / ONE_SOLVE / FINAL / MOUTH_RELAX) are
    DELETED, not merely unused — a surviving constant is an invitation to
    pass it again."""
    for gone in ("PROJECTION_MAX_SWEEPS_DEFAULT",
                 "PROJECTION_MAX_SWEEPS_ONE_SOLVE",
                 "PROJECTION_MAX_SWEEPS_FINAL",
                 "PROJECTION_MAX_SWEEPS_MOUTH_RELAX"):
        assert not hasattr(cfg, gone), f"config.{gone} must be deleted"


def test_the_projection_call_sites_pass_no_sweep_constant():
    """The solve's four projection calls must DERIVE.  Read from source:
    a re-introduced ``max_iters=`` on those calls is exactly the defect
    this change removes, and it would be invisible in any value assert."""
    import inspect

    from auto_patch.elevation_per_surface.route_profile import solve as SOLVE
    source = inspect.getsource(SOLVE)
    assert "max_iters=" not in source, (
        "a solve-side projection call is imposing a sweep budget again")


# ── the uncertified exit names its derivation ────────────────────────────

def _infeasible_system():
    """Node 1 must sit within 1.0 of node 0 (pinned 0.0) AND within 1.0 of
    node 2 (pinned 10.0): the two anchor VALUES cannot both hold, so no
    budget can certify it."""
    return [0.0, 0.0, 10.0], [(0, 1, 1.0, 1), (1, 2, 1.0, 2)], 3


def test_the_uncertified_exit_says_it_is_not_budget_exhaustion(capsys):
    """After this change an uncertified exit means the POLYTOPE IS EMPTY
    (a law / anchor / instrument defect — RULINGS 2026-08-05, there is no
    lawful-infeasible ground) or the graph is pathological.  The report
    must SAY that, and must stay as loud as it was."""
    elev, iter_edges, n = _infeasible_system()
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, n, 120, 1e-3, stats=stats,
                          sweep_budget_basis=6)
    text = capsys.readouterr().out
    assert "UNCERTIFIED EXIT" in text
    assert "NOT budget exhaustion" in text
    assert "polytope is EMPTY" in text
    # the derived budget AND the bound it came from, so the test phase can
    # attribute the exit without re-deriving anything
    assert "budget 120 DERIVED" in text
    assert "hop-diameter bound 6" in text
    assert stats["uncertified_exit"]["sweep_budget_basis"] == 6


def test_an_imposed_budget_is_reported_as_imposed(capsys):
    """A caller-supplied ``max_iters`` (a test, a bounded probe) is not a
    derivation, and the report must not pretend it was."""
    elev, iter_edges, n = _infeasible_system()
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, n, 40, 1e-3, stats=stats)
    text = capsys.readouterr().out
    assert "budget IMPOSED by the caller" in text
    assert stats["uncertified_exit"]["sweep_budget_basis"] is None


def test_the_ceiling_case_is_flagged_in_the_report(capsys):
    """The two meanings of an uncertified exit are told apart by ONE
    printed fact: whether the budget was clamped to the ceiling."""
    elev, iter_edges, n = _infeasible_system()
    OS._project_chromatic(elev, iter_edges, n, cfg.SWEEP_BUDGET_MAX, 1e-3,
                          sweep_budget_basis=10 ** 9)
    assert "AT SWEEP_BUDGET_MAX CEILING" in capsys.readouterr().out


def test_a_certified_call_still_reports_nothing(capsys):
    """The complement — the loudness must not have leaked into the happy
    path."""
    elev = [0.0, 5.0, 5.0]
    stats: dict = {}
    OS._project_chromatic(elev, [(0, 1, 1.0, 1), (1, 2, 1.0, 0)], 3,
                          4000, 1e-3, stats=stats, sweep_budget_basis=4)
    assert stats["certified"] is True
    assert "UNCERTIFIED EXIT" not in capsys.readouterr().out
