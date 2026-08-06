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


def test_a_converged_exit_reports_its_stopping_criterion_by_the_numbers(
        capsys):
    """KNOWN-ANSWER CALIBRATION of the converged exit's report.

    ``_infeasible_system`` under ``block=10``: every block boundary
    measures the SAME state — one over-cap edge, one of them ≥ 0.01 m,
    worst residual exactly 8.000000 m (node 1 is dragged to 1.0 by the
    pin at 0.0 while the pin at 10.0 wants 9.0; ``|z0 − z1| − 1.0 = 8``).
    So the drop is +0 twice, ``SWEEP_CONVERGENCE_PATIENCE`` (2) is reached
    at the third block, and the loop exits at sweep 30.  Every number
    below is hand-derivable from those three sentences — which is the
    point: the report has to let a reader apply the criterion themselves.

    (RULINGS 2026-08-06 §1-2.  This test previously asserted the
    INTERPRETATION the report printed instead — see
    ``test_the_converged_exit_claims_nothing_about_the_feasible_set``.)
    """
    elev, iter_edges, n = _infeasible_system()
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, n, 10, 1e-3, stats=stats,
                          sweep_budget_basis=6, sweep_hard_cap=1000)
    text = capsys.readouterr().out

    assert "UNCERTIFIED EXIT [converged]" in text
    # the derived BLOCK and the bound it came from
    assert "block 10 DERIVED" in text
    assert "hop-diameter bound 6" in text

    # THE CRITERION, spelled out as the predicate that actually fired,
    # with both constants by NAME and VALUE.
    assert "criterion=convergence" in text
    assert f"SWEEP_CONVERGENCE_PATIENCE={cfg.SWEEP_CONVERGENCE_PATIENCE}" \
        in text
    assert (f"SWEEP_CONVERGENCE_MIN_DROP="
            f"{cfg.SWEEP_CONVERGENCE_MIN_DROP:.1%}") in text
    # the flat-block floor: max(1, int(0.005 * 1)) == 1
    assert "x previous n_material) = 1 edge(s)" in text

    # THE MEASURED TRAJECTORY — the ≥-material count per block, which is
    # what "stopped falling" means and the only thing that licenses the
    # exit.  Three blocks, all 1.
    assert "n_material trajectory over the last 3 block(s) 1 -> 1 -> 1" \
        in text
    assert "last block drop +0 edge(s) >= 0.01 m" in text
    assert "at exit n_material=1, n_over=1, worst residual 8.000000 m" \
        in text

    # the FRAME of every number above (RULINGS 2026-08-06 §3)
    assert "[node-space fp-remapped: n=3, edges=2]" in text

    record = stats["uncertified_exit"]
    assert record["sweep_budget_basis"] == 6
    assert record["exit_reason"] == "converged"
    assert record["sweep"] == 30            # 3 blocks of 10, not the 1000
    assert record["n_material"] == 1
    assert record["active_edges"] == 1
    assert record["worst"] == pytest.approx(8.0, abs=1e-9)
    assert stats["exit_reason"] == "converged"


def test_the_converged_exit_claims_nothing_about_the_feasible_set(capsys):
    """THE HEADLINE DEFECT OF THE STANDING-INSTRUMENT SWEEP, pinned shut.

    This report used to print, ungated, in every production build that
    took the ``converged`` branch:

        "This is NOT budget exhaustion: the projection has converged to a
         point that violates N constraint(s), so the polytope is EMPTY…"

    Three interpretations in one sentence — a negated cause, a geometric
    claim, and a defect classification — resting on a premise that is
    only a STOPPING HEURISTIC: ``SWEEP_CONVERGENCE_PATIENCE`` blocks below
    ``SWEEP_CONVERGENCE_MIN_DROP`` relative improvement.  Slow diffusive
    POCS convergence and a genuinely empty intersection produce the
    IDENTICAL trace, and the c6attr sweep ladders measured exactly that
    (100x/400x the derived budget closed a third of HECA's and over half
    of HEAZ's residual on systems this line had already called empty).
    It is the sentence the owner's ruling names in its own preamble.

    The system below IS infeasible — that is what makes this test sharp:
    even when the claim would happen to be TRUE, report code may not make
    it, because nothing here proves it.  The law layer adjudicates, from
    the numbers the sibling test calibrates.
    """
    elev, iter_edges, n = _infeasible_system()
    OS._project_chromatic(elev, iter_edges, n, 10, 1e-3,
                          sweep_budget_basis=6, sweep_hard_cap=1000)
    text = capsys.readouterr().out
    assert "UNCERTIFIED EXIT [converged]" in text, "the exit still reports"
    for banned in ("polytope",              # the geometric claim
                   "budget exhaustion",     # the negated cause
                   "no solution",
                   "law / anchor / instrument defect",
                   "infeasible ground"):
        assert banned not in text, (
            f"report code printed the unlicensed claim {banned!r}")


def test_the_convergence_exit_carries_its_own_evidence(capsys):
    """A criterion nobody can audit is not a criterion.

    Every converged exit prints the last blocks' (sweep, over-cap,
    ≥materiality, worst, drop) rows and the drop that tripped it, so the
    verdict can be checked from the log alone.
    """
    elev, iter_edges, n = _infeasible_system()
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, n, 10, 1e-3, stats=stats,
                          sweep_budget_basis=6, sweep_hard_cap=1000)
    text = capsys.readouterr().out
    assert "block @sweep" in text
    assert "last block drop" in text
    trace = stats["block_trace"]
    assert len(trace) >= cfg.SWEEP_CONVERGENCE_PATIENCE + 1
    # rows are (sweep, n_over, n_material, worst, drop); the ≥material
    # count is the criterion's denominator and it stopped falling.
    assert trace[-1][4] == 0
    assert all(row[0] % 10 == 0 for row in trace), "rows are block ends"


def test_a_materially_certified_exit_reports_its_count_and_its_floor(capsys):
    """KNOWN ANSWER: node 1 sits 0.008 m past its cap — over the 1 mm sweep
    tolerance, under the 0.01 m campaign floor — so exactly one edge is
    over cap and ZERO are at or above materiality, at the first block.

    THE DISPOSITION MOVED TO THE LAW LAYER (RULINGS 2026-08-06 §2).  The
    line used to end "…so every remaining residual is PASS-with-residual
    by ruling", which is an ADJUDICATION printed by report code.  The
    ruling is real (owner convergence guard (a), 2026-08-02) and the
    report still cites it — as the PROVENANCE OF THE CONSTANT it measured
    against, which is a frame stamp, not a verdict.
    """
    elev = [0.0, 0.0, 2.008]
    iter_edges = [(0, 1, 1.0, 1), (1, 2, 1.0, 2)]
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, 3, 10, 1e-3, stats=stats,
                          sweep_budget_basis=6, sweep_hard_cap=1000)
    text = capsys.readouterr().out
    assert "MATERIALLY CERTIFIED EXIT" in text
    assert "criterion=materiality: n_material=0" in text
    # the constant, its value, and where the value comes from
    assert (f"materiality {cfg.PROJECTION_MATERIALITY_M:g} m = "
            f"config.PROJECTION_MATERIALITY_M") in text
    assert "owner convergence guard (a) 2026-08-02" in text
    # the numbers a reader re-derives the criterion from
    assert "n_over=1" in text
    assert "worst residual 0.008000 m" in text
    assert stats["exit_reason"] == "material"
    assert stats["uncertified_exit"]["n_material"] == 0
    assert stats["uncertified_exit"]["active_edges"] == 1
    assert stats["uncertified_exit"]["sweep"] == 10
    # no verdict about the feasible set rides this branch either
    assert "polytope" not in text


def test_an_imposed_budget_is_reported_as_imposed(capsys):
    """A caller-supplied ``max_iters`` (a test, a bounded probe, a ladder
    arm) is not a derivation, and the report must not pretend it was —
    nor may the convergence criterion extend past it.  The caller's
    number is the law."""
    elev, iter_edges, n = _infeasible_system()
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, n, 40, 1e-3, stats=stats)
    text = capsys.readouterr().out
    assert "UNCERTIFIED EXIT [imposed budget]" in text
    assert "block 40 IMPOSED by the caller" in text
    # THE FACT, not the story: this branch is selected by
    # ``sweep_budget_basis is None``, which is a property of the CALL.
    assert ("criterion=imposed-budget: sweeps 40 reached the caller's "
            "bound 40 (sweep_budget_basis=None)") in text
    assert "at exit n_material=1, n_over=1, worst residual 8.000000 m" \
        in text
    # the honest NON-claim survives — it withdraws a conclusion rather
    # than asserting one.
    assert "This exit reports no property of the feasible set." in text
    assert "polytope" not in text
    assert stats["uncertified_exit"]["sweep_budget_basis"] is None
    assert stats["uncertified_exit"]["sweep"] == 40
    assert stats["hard_cap"] == 40


def test_the_hard_cap_exit_reports_the_two_numbers_that_define_it(capsys):
    """KNOWN ANSWER: patience needs 3 blocks, the ceiling allows 2 — so the
    loop ends at ``sweeps == hard_cap == 10`` with the count still at 1.

    ``sweeps >= hard_cap`` IS world-invariant and it is printed.  What is
    deleted is the prose that rode on it — "THE GUARD DECIDED THIS
    SURFACE, not convergence: attribute the graph or raise the ceiling,
    and do NOT read this as an empty polytope" — a cause, an instruction
    to the reader, and a second instruction not to draw a conclusion.
    """
    elev, iter_edges, n = _infeasible_system()
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, n, 5, 1e-3, stats=stats,
                          sweep_budget_basis=6, sweep_hard_cap=10)
    text = capsys.readouterr().out
    assert "UNCERTIFIED EXIT [hard cap]" in text
    assert ("criterion=cap: sweeps 10 reached hard_cap 10 "
            "(config.SWEEP_BUDGET_MAX in production)") in text
    assert "last_block_drop +0 edge(s) >= 0.01 m" in text
    assert "at exit n_material=1, n_over=1, worst residual 8.000000 m" \
        in text
    # the criterion label is a measured fact and stays greppable ...
    assert stats["exit_reason"] == "cap"
    assert stats["uncertified_exit"]["sweep"] == 10
    # ... the adjudication and the instructions do not come back.
    for banned in ("THE GUARD DECIDED THIS SURFACE", "polytope",
                   "attribute the graph", "raise the ceiling"):
        assert banned not in text, f"report code printed {banned!r}"


def test_a_certified_call_still_reports_nothing(capsys):
    """The complement — the loudness must not have leaked into the happy
    path."""
    elev = [0.0, 5.0, 5.0]
    stats: dict = {}
    OS._project_chromatic(elev, [(0, 1, 1.0, 1), (1, 2, 1.0, 0)], 3,
                          4000, 1e-3, stats=stats, sweep_budget_basis=4)
    assert stats["certified"] is True
    assert "UNCERTIFIED EXIT" not in capsys.readouterr().out
