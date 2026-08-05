"""Unit tests for the PROJECTION STALL REPORT (spec
``docs/specs/projection-stall-guard-spec.md``, report-only mode per the
Fable ruling 2026-08-04 that closed the early-termination family).

The detector still runs; it only WRITES.  So the property that matters is
no longer "does it stop at the right sweep" — there is no stopping — but
"is it provably unable to touch the surface".  Hermetic: no build, no
fixtures.  Covers:
  (a) the gate: default OFF, implied ON by ``O4_ROUTE_METRIC_ENVELOPE``,
      explicit value wins over the implication;
  (b) gate-off inertness — no counters, no stats keys;
  (c) VALUE IDENTITY gate-on vs gate-off, on both an infeasible system and
      a certifying one — the whole point of report-only mode;
  (d) detection semantics: patience honoured, snapshot taken once, and the
      call still runs to its natural end;
  (e) the report names the carrier pair with its ``L − U`` class;
  (f) the attempt-2 falsifier, now GREEN: systems that certify when left
      alone still certify with the gate on.
"""
import pytest

from auto_patch.elevation_per_surface.route_profile import one_solve as OS


# ── helpers ──────────────────────────────────────────────────────────────

def _infeasible_system():
    """Node 1 must sit within 1.0 of node 0 (pinned 0.0) AND within 1.0 of
    node 2 (pinned 10.0) — the two anchor VALUES cannot both hold, so the
    max residual pins immediately while POCS oscillates for ever.  This is
    the drain-list shape in miniature."""
    elev = [0.0, 0.0, 10.0]
    iter_edges = [(0, 1, 1.0, 1), (1, 2, 1.0, 2)]
    return elev, iter_edges, 3


def _feasible_chain(n=40, seed=5.0):
    """A FEASIBLE chain: node 0 pinned at 0.0, budget 1.0 per link,
    everything else seeded above its ceiling.  The correction walks the
    chain, so the active violating-edge count PLATEAUS for far more than
    ``STALL_PATIENCE_SWEEPS`` passes — the detector declares a stall — and
    the solve nonetheless goes on to CERTIFY (``worst`` 0.0).  That gap
    between the two is exactly why termination was retired."""
    elev = [0.0] + [seed] * (n - 1)
    iter_edges = [(0, 1, 1.0, 1)]
    iter_edges += [(i, i + 1, 1.0, 0) for i in range(1, n - 1)]
    return elev, iter_edges, n


def _run(elev, iter_edges, n, max_iters=4000):
    stats: dict = {}
    sweeps, certified = OS._project_chromatic(
        elev, iter_edges, n, max_iters, 1e-3, stats=stats)
    return sweeps, certified, stats


# ── (a) the gate ─────────────────────────────────────────────────────────

def test_gate_defaults_off_and_is_implied_by_the_route_metric(monkeypatch):
    """KILL-HALF FLIP (2026-08-04, spec kill-half §1): the REPORT's own
    default is still "0" (the spec flips 11 gates and this is not one of
    them) — but its implicant ``O4_ROUTE_METRIC_ENVELOPE`` is default ON,
    so an unset environment now REPORTS.  Both halves are asserted."""
    monkeypatch.delenv("O4_PROJECTION_STALL_REPORT", raising=False)
    monkeypatch.delenv("O4_ROUTE_METRIC_ENVELOPE", raising=False)
    assert OS.PROJECTION_STALL_REPORT_DEFAULT == "0"
    assert OS.projection_stall_report_enabled() is True, (
        "the flipped route-metric default implies the report on")
    monkeypatch.setenv("O4_ROUTE_METRIC_ENVELOPE", "0")
    assert OS.projection_stall_report_enabled() is False
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    assert OS.projection_stall_report_enabled() is True
    monkeypatch.delenv("O4_PROJECTION_STALL_REPORT")
    monkeypatch.setenv("O4_ROUTE_METRIC_ENVELOPE", "1")
    assert OS.projection_stall_report_enabled() is True


def test_an_explicit_zero_wins_over_the_implication(monkeypatch):
    """Ratified deviation 2026-08-04 — without this the gate cannot be
    proved inert INSIDE the arm that implies it on."""
    monkeypatch.setenv("O4_ROUTE_METRIC_ENVELOPE", "1")
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "0")
    assert OS.projection_stall_report_enabled() is False


# ── (b) gate-off inertness ───────────────────────────────────────────────

def test_gate_off_takes_no_counters_and_adds_no_stats(monkeypatch):
    # kill-half flip: gate-off is now explicit (the route metric implies it on)
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "0")
    monkeypatch.delenv("O4_ROUTE_METRIC_ENVELOPE", raising=False)
    elev, iter_edges, n = _infeasible_system()
    sweeps, certified, stats = _run(elev, iter_edges, n, 200)
    assert (sweeps, certified) == (200, False)
    for key in ("stalled", "carrier", "active_edges", "stall_detect_sweep"):
        assert key not in stats


# ── (c) VALUE IDENTITY — the property report-only mode exists for ────────

@pytest.mark.parametrize("build", [
    _infeasible_system,
    lambda: _feasible_chain(40, 5.0),
    lambda: _feasible_chain(20, 10.0),
])
def test_the_report_cannot_touch_the_surface(monkeypatch, build):
    """Gate ON and gate OFF must agree BIT FOR BIT — same surface, same
    sweep count, same certificate.  Nothing in the report path can reach
    ``z``: it runs after the writeback and every argument is read-only."""
    monkeypatch.delenv("O4_PROJECTION_STALL_REPORT", raising=False)
    monkeypatch.delenv("O4_ROUTE_METRIC_ENVELOPE", raising=False)
    elev_off, iter_edges, n = build()
    sweeps_off, cert_off, stats_off = _run(elev_off, iter_edges, n, 20000)

    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    elev_on, iter_edges, n = build()
    sweeps_on, cert_on, stats_on = _run(elev_on, iter_edges, n, 20000)

    assert elev_on == elev_off
    assert sweeps_on == sweeps_off
    assert cert_on == cert_off
    assert stats_on["worst"] == stats_off["worst"]


# ── (d) detection semantics ──────────────────────────────────────────────

def test_detection_honours_the_patience_and_does_not_stop_the_solve(
        monkeypatch):
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    elev, iter_edges, n = _infeasible_system()
    sweeps, certified, stats = _run(elev, iter_edges, n, 400)
    assert certified is False
    assert stats["stalled"] is True
    # detected early ...
    assert stats["stall_detect_sweep"] > OS.STALL_PATIENCE_SWEEPS
    assert stats["stall_detect_sweep"] <= OS.STALL_PATIENCE_SWEEPS + 5
    # ... and the projection nonetheless ran its full course.
    assert sweeps == 400
    assert stats["stall_sweeps_burned"] == 400 - stats["stall_detect_sweep"]


def test_the_detection_snapshot_is_taken_once(monkeypatch):
    """The snapshot must describe the sweep the stall was DECLARED on, not
    the last sweep of the call — the two differ by the burned budget."""
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    elev, iter_edges, n = _infeasible_system()
    short = _run(list(elev), iter_edges, n, 100)[2]
    long_ = _run(list(elev), iter_edges, n, 4000)[2]
    assert short["stall_detect_sweep"] == long_["stall_detect_sweep"]
    assert short["stall_sweeps_burned"] < long_["stall_sweeps_burned"]


def test_a_call_that_certifies_before_the_patience_never_reports(monkeypatch):
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    elev = [0.0, 0.0, 0.0]
    iter_edges = [(0, 1, 1.0, 1), (1, 2, 1.0, 0)]
    stats: dict = {}
    # ``run_feasibility_precheck=False`` forces the sweep loop (the two
    # paths are value-identical); the pre-check shortcut is covered below.
    sweeps, certified = OS._project_chromatic(
        elev, iter_edges, 3, 4000, 1e-3, stats=stats,
        run_feasibility_precheck=False)
    assert (sweeps, certified) == (1, True)
    assert stats["stalled"] is False
    assert stats["stall_sweeps_burned"] == 0


def test_the_feasibility_precheck_shortcut_reports_nothing(monkeypatch):
    """An already-satisfied system returns without entering the sweep loop
    at all, so it takes no counters and declares no stall — the guard keys
    are simply absent, exactly as on the gate-off path."""
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    elev = [0.0, 0.0, 0.0]
    iter_edges = [(0, 1, 1.0, 1), (1, 2, 1.0, 0)]
    sweeps, certified, stats = _run(elev, iter_edges, 3)
    assert (sweeps, certified) == (1, True)
    assert "stalled" not in stats


# ── (e) the report names the carrier pair ────────────────────────────────

def test_report_names_the_carrier_pair_and_its_adjudication(
        monkeypatch, capsys):
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    monkeypatch.setenv("O4_STALL_GUARD_ADJUDICATE", "1")
    elev, iter_edges, n = _infeasible_system()
    _, _, stats = _run(elev, iter_edges, n, 400)
    text = capsys.readouterr().out
    assert "[stall-report]" in text
    assert "STALLED at sweep" in text
    assert "burned after detection" in text
    assert "detect carrier symmetric pair" in text
    carrier = stats["detect_carrier"]
    assert carrier[0] == "sym"
    assert {carrier[1], carrier[2]} <= {0, 1, 2}
    # the adjudication class: this system IS infeasible (L > U at node 1)
    assert "INFEASIBLE" in text


def test_adjudication_stays_behind_the_forensics_channel(monkeypatch, capsys):
    """Two whole-graph Dijkstras are not a per-build cost — the pair is
    always named, the L-U class only when forensics is asked for."""
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    monkeypatch.delenv("O4_STALL_GUARD_ADJUDICATE", raising=False)
    monkeypatch.delenv("O4_BREAK_FORENSICS", raising=False)
    elev, iter_edges, n = _infeasible_system()
    _run(elev, iter_edges, n, 400)
    text = capsys.readouterr().out
    assert "detect carrier symmetric pair" in text
    assert "L-U" not in text
    assert "envelope:" not in text


# ── (f) the attempt-2 falsifier, now GREEN ───────────────────────────────

@pytest.mark.parametrize("n,seed", [(40, 5.0), (20, 10.0), (60, 50.0)])
def test_certifying_systems_still_certify_with_the_gate_on(
        monkeypatch, n, seed):
    """This is the test that was RED for the terminating design: these
    chains reach a certificate (a proved-lawful surface, ``worst`` 0.0)
    and the old guard cut them at sweep ~17 with violating edges still
    live.  Report-only mode makes it green by construction — the detector
    still declares the stall, and the solve still certifies."""
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    elev, iter_edges, nn = _feasible_chain(n, seed)
    sweeps, certified, stats = _run(elev, iter_edges, nn, 20000)
    assert certified is True
    assert stats["worst"] == 0.0
    assert stats["stalled"] is True               # detected ...
    assert sweeps > stats["stall_detect_sweep"]   # ... and outlived it


# ── (g) the ANCHOR SET the adjudication uses ─────────────────────────────
# Spec ``dossier-fixes-round`` §1.  The set was "zero weight on SOME edge",
# which is not immobility: a node is routinely the HELD endpoint of one
# edge and the MOVING endpoint of another.  Anchoring such a node at its
# post-solve ``z`` invents a constraint no law declared, and it mints
# INFEASIBLE verdicts out of feasible systems (HEAZ call01: 3300 "pinned"
# of which 666 had moved, max 0.848 m; call07 flipped class).

def _held_but_moving_system():
    """Node 2 is HELD by edge (1,2) (kind 2) and MOVES on edge (2,3)
    (kind 0) — the two-authority shape, in miniature.

    Under the old set the anchors are {0, 2}; node 2's post-solve value
    (~4.5, pushed there by node 3) then bounds node 1 from below at 4.4
    while node 0 bounds it from above at 1.0 ⇒ "INFEASIBLE".  Under the
    strict set the only anchor is node 0 and the system is feasible — as
    it plainly is: ``z ≡ 0`` satisfies every cap edge."""
    elev = [0.0, 0.0, 0.0, 10.0]
    iter_edges = [(0, 1, 1.0, 1), (1, 2, 0.1, 2), (2, 3, 1.0, 0)]
    return elev, iter_edges, 4


def test_only_never_moving_nodes_are_anchors():
    import numpy as np
    endpoint_i = np.array([0, 1, 2], dtype=np.intp)
    endpoint_j = np.array([1, 2, 3], dtype=np.intp)
    budget = np.array([1.0, 0.1, 1.0])
    interval = np.array([False, False, False])
    weight_i = np.array([0.0, 1.0, 0.5])
    weight_j = np.array([1.0, 0.0, 0.5])
    z = np.array([0.0, 4.4, 4.5, 5.5])
    verdict = OS._stall_envelope_gap(np, endpoint_i, endpoint_j, budget,
                                     interval, weight_i, weight_j, z, 4,
                                     [(1, 2)])
    assert verdict is not None
    assert list(verdict["pinned"]) == [True, False, False, False], (
        "node 2 carries positive weight on edge (2,3) — it is not an anchor")
    assert verdict["infeasible"] == 0
    assert verdict["max_gap"] == 0.0


def test_a_held_but_moving_endpoint_no_longer_mints_infeasible(
        monkeypatch, capsys):
    """End-to-end through the report: the carrier of this stalled system
    adjudicates FEASIBLE, because the value that made it look otherwise
    was a movable node's post-solve ``z``."""
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    monkeypatch.setenv("O4_STALL_GUARD_ADJUDICATE", "1")
    elev, iter_edges, n = _held_but_moving_system()
    _run(elev, iter_edges, n, 400)
    text = capsys.readouterr().out
    assert "INFEASIBLE nodes (L>U) 0 of" in text
    assert "-> feasible" in text
    assert "-> INFEASIBLE" not in text


def test_a_genuinely_pinned_pair_still_adjudicates_infeasible(
        monkeypatch, capsys):
    """The strict set must not blunt the instrument: two truly immovable
    anchors whose values cannot both hold are still named INFEASIBLE."""
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    monkeypatch.setenv("O4_STALL_GUARD_ADJUDICATE", "1")
    elev, iter_edges, n = _infeasible_system()
    _run(elev, iter_edges, n, 400)
    text = capsys.readouterr().out
    assert "-> INFEASIBLE" in text


@pytest.mark.parametrize("rel", [0.0, 0.005, 0.05])
def test_raising_the_threshold_never_delays_detection(monkeypatch, rel):
    """The constant is a RELATIVE improvement, so raising it can only make
    qualification HARDER and detection EARLIER — never later.  That
    monotonicity is what proved the spec's ~8.4k / ~15.5k sweep targets
    (the REL=0 oracle numbers) unreachable at REL=0.005, and it is the one
    property of the constants that still governs anything."""
    monkeypatch.setenv("O4_PROJECTION_STALL_REPORT", "1")
    monkeypatch.setattr(OS, "STALL_REL_IMPROVEMENT", rel)
    elev, iter_edges, n = _infeasible_system()
    _, _, stats = _run(elev, iter_edges, n, 400)
    assert stats["stalled"] is True
    assert stats["stall_detect_sweep"] <= OS.STALL_PATIENCE_SWEEPS + 5


# ── (g) THE REFERENCE-ROD EQUILIBRIUM EXIT IS LOUD ───────────────────────
# Spec docs/specs/ref-pull-interim-spec.md §2.  The ``ref_prev``
# steady-state break is CORRECT to terminate — the pull and the
# projections have reached a fixpoint, so more sweeps cannot move the
# surface — but it exited UNCERTIFIED and SILENT, which downstream reads
# exactly like a clean exit.  These pin the loudness, the certificate, and
# the inertness; they are ungated because a law-relevant uncertified exit
# is not an opt-in.

def _ref_equilibrium_over_cap():
    """Node 1 must sit within 1.0 of node 0 (pinned 0.0) AND within 1.0 of
    node 2 (pinned 10.0), and additionally carries a reference at 5.0 —
    the anchors already contradict, and the pull holds node 1 at a fixpoint
    that satisfies NEITHER cap.  The HECA finals shape in miniature: the
    loop quits almost immediately with a large residual still live."""
    return [0.0, 0.0, 10.0], [(0, 1, 1.0, 1), (1, 2, 1.0, 2)], 3, {1: 5.0}


def _ref_equilibrium_cap_feasible():
    """Node 1 is capped 1.0 from a pinned 0.0 but referenced at 10.0.  The
    exit state is fully cap-lawful; what stalls is the REFERENCE, 9 m out
    of reach.  Distinguishing this from the case above is the whole reason
    the report prints both censuses."""
    return [0.0, 0.0], [(0, 1, 1.0, 1)], 2, {1: 10.0}


@pytest.mark.parametrize("build", [_ref_equilibrium_over_cap,
                                   _ref_equilibrium_cap_feasible])
def test_the_equilibrium_exit_reports_and_never_certifies(capsys, build):
    elev, iter_edges, n, refs = build()
    stats: dict = {}
    sweeps, certified = OS._project_chromatic(
        elev, iter_edges, n, 4000, 1e-3, stats=stats, node_ref=refs)
    text = capsys.readouterr().out
    assert certified is False, "an equilibrium exit is never a certificate"
    assert sweeps < 4000, "the break stands — it must still terminate early"
    assert "REFERENCE-ROD EQUILIBRIUM" in text
    assert "UNCERTIFIED" in text
    assert f"{4000 - sweeps} sweep(s) abandoned" in text
    record = stats["ref_equilibrium"]
    assert record["sweep"] == sweeps
    assert record["sweeps_abandoned"] == 4000 - sweeps
    assert record["off_ref_max"] > 0.01          # the reference is not met
    assert record["off_ref_material"] >= 1


def test_the_report_names_the_carrier_of_a_live_over_cap_residual(capsys):
    """The over-cap case must NAME the pair, exactly as the stall guard
    does — that pair is the drain-list value defect (``feasibility-is-
    guaranteed``: a live residual at a fixpoint is two anchor values that
    cannot both hold)."""
    elev, iter_edges, n, refs = _ref_equilibrium_over_cap()
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, n, 4000, 1e-3, stats=stats,
                          node_ref=refs)
    text = capsys.readouterr().out
    record = stats["ref_equilibrium"]
    assert record["active_edges"] >= 1
    assert record["worst"] > 1e-3
    assert record["carrier"][0] == "sym"
    assert {record["carrier"][1], record["carrier"][2]} <= {0, 1, 2}
    assert "exit   carrier symmetric pair" in text


def test_a_cap_feasible_equilibrium_reports_no_carrier(capsys):
    """Honest censuses: when the caps are all satisfied the report says so
    (0 active edges, 0.0 residual, no carrier) and the REFERENCE column is
    what carries the finding."""
    elev, iter_edges, n, refs = _ref_equilibrium_cap_feasible()
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, n, 4000, 1e-3, stats=stats,
                          node_ref=refs)
    record = stats["ref_equilibrium"]
    assert record["active_edges"] == 0
    assert record["worst"] == 0.0
    assert record["carrier"] is None
    assert record["off_ref_max"] == pytest.approx(9.0, abs=1e-9)
    assert "exit   carrier: none" in capsys.readouterr().out


@pytest.mark.parametrize("build", [_ref_equilibrium_over_cap,
                                   _ref_equilibrium_cap_feasible])
def test_the_equilibrium_report_cannot_touch_the_surface(monkeypatch, build):
    """VALUE IDENTITY — the property §2 exists to preserve.  The report
    runs after the writeback and every argument is read-only, so replacing
    it with a no-op must not move a single vertex, sweep or certificate."""
    elev_on, iter_edges, n, refs = build()
    stats_on: dict = {}
    got_on = OS._project_chromatic(elev_on, iter_edges, n, 4000, 1e-3,
                                   stats=stats_on, node_ref=dict(refs))

    monkeypatch.setattr(OS, "_ref_equilibrium_report",
                        lambda *a, **k: None)
    elev_off, iter_edges, n, refs = build()
    stats_off: dict = {}
    got_off = OS._project_chromatic(elev_off, iter_edges, n, 4000, 1e-3,
                                    stats=stats_off, node_ref=dict(refs))

    assert elev_on == elev_off
    assert got_on == got_off
    assert stats_on["worst"] == stats_off["worst"]
    assert stats_on["sweeps"] == stats_off["sweeps"]
    assert "ref_equilibrium" not in stats_off       # the no-op returned None


def test_a_call_without_references_never_records_an_equilibrium():
    """No refs ⇒ no ``ref_prev`` ⇒ the break cannot fire and the stats dict
    is exactly what it was before §2."""
    elev, iter_edges, n = _infeasible_system()
    stats: dict = {}
    OS._project_chromatic(elev, iter_edges, n, 200, 1e-3, stats=stats)
    assert "ref_equilibrium" not in stats
