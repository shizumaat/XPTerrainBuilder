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

    # (The "gate off ⇒ the closure admits 0.0" half is GONE with the gate,
    # integration sweep 2026-08-05: the band IS the clamp's source and no
    # environment selects the pavement-PAIR closure any more.)


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


def test_the_pair_closure_arm_cannot_be_selected(monkeypatch):
    """OBITUARY for the OFF arm (integration sweep 2026-08-05).

    The pavement-PAIR closure is one of the audit's three superseded
    SECOND AUTHORITIES; the route-metric band replaced it and the gates
    that could still reach it are deleted.  A stale ``=0`` in an
    environment must produce the BAND result, not the closure's — the
    silent-no-op hazard the sweep exists to close."""
    band = [None, (10.0, 20.0), (30.0, 40.0), None]

    def _run():
        e = [0.0, 0.0, 0.0, 50.0]
        br = set()
        feasibility_project(e, _chain(), {0, 3}, force_scalar=True,
                            max_iters=200, broken_out=br, env_band=band)
        return e, br

    monkeypatch.delenv("O4_ENVELOPE_FROM_BAND", raising=False)
    monkeypatch.delenv("O4_ROUTE_METRIC_ENVELOPE", raising=False)
    clean_elev, clean_broken = _run()
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "0")
    monkeypatch.setenv("O4_ROUTE_METRIC_ENVELOPE", "0")
    stale_elev, stale_broken = _run()
    assert stale_broken != {1, 2}, (
        "an env value must not restore the pair closure — that is the "
        "arm the sweep deleted")
    assert (stale_elev, stale_broken) == (clean_elev, clean_broken), (
        "the retired env names must make NO difference to the answer")


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

    The flag has exactly ONE resolver and ONE default.  KILL-HALF FLIP
    (2026-08-04, spec kill-half §1): that default is now ON — the
    route-metric envelope ships, so an UNSET environment gets the BAND
    envelope at every call site.  The property the old
    ``solve.py``-"0"-vs-``one_solve.py``-"1" split violated (one resolver,
    one default, same answer everywhere) is what is asserted here, not the
    value of the default."""
    monkeypatch.delenv("O4_ENVELOPE_FROM_BAND", raising=False)
    monkeypatch.delenv("O4_ROUTE_METRIC_ENVELOPE", raising=False)
    assert route_metric_envelope_enabled() is True
    assert envelope_from_band_enabled() is True

    elev = [0.0, 0.0, 0.0, 50.0]
    broken = set()
    feasibility_project(elev, _chain(), {0, 3}, force_scalar=True,
                        max_iters=400, broken_out=broken,
                        env_band=[None, (10.0, 20.0), (30.0, 40.0), None])
    assert broken == set(), "unset ⇒ THE band, and this band is feasible"

    # STANDING LAW 2026-08-05 (integration sweep): both gates are DELETED
    # — the route-metric band IS the envelope law, and the pavement-PAIR
    # closure it replaced is one of the audit's three superseded second
    # authorities.  A stale ``=0`` in an environment must not restore the
    # closure; that is what the rest of this test now pins.
    monkeypatch.setenv("O4_ROUTE_METRIC_ENVELOPE", "0")
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "0")
    assert route_metric_envelope_enabled() is True
    assert envelope_from_band_enabled() is True, (
        "the route-metric band IS the envelope; no env selects the closure")


# ── THE BAND BINDS PER SWEEP (cycle-5 solve-certification spec, fix 2) ──

def test_the_band_floor_survives_the_sweeps(monkeypatch):
    """THE fix-2 twin, and the whole round in one assertion.

    The band clamp used to be ONE-SHOT: applied once before the sweeps and
    then relaxed away by them, while caps and node boxes bound every
    sweep.  Measured at HECA plateau fp#8 EXIT: 11,144 banded nodes BELOW
    their own floor (worst 89.637 m) against 112 above their ceiling
    (worst 0.187 m) — 99.5 : 1.  A two-sided band producing a one-sided
    error at that ratio is a mechanism, not noise.

    The graph here reproduces it in miniature: node 1 carries a band floor
    of 10 m, and a TIGHT cap edge to hard node 0 at 0.0 pulls it back down
    to 0.  One-shot ⇒ the clamp lifts it to 10 and the sweeps drag it to
    ~0.  Per-sweep ⇒ the floor is re-applied after every step and the
    node CANNOT be dragged below it; the unsatisfiable cap edge then
    surfaces as a remaining over-cap edge, which is the honest outcome.
    """
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    tight = [{"edges": [(0, 1, 0.01)]}]        # hard 0 at 0.0 pulls 1 down
    band = [None, (10.0, 20.0)]
    elev = [0.0, 0.0]
    feasibility_project(elev, tight, {0}, force_scalar=True, max_iters=400,
                        env_band=band)
    assert elev[0] == pytest.approx(0.0), "hard node never moves"
    assert elev[1] >= 10.0 - 1e-9, (
        f"the band FLOOR must survive the sweeps, got {elev[1]}")


def test_an_inverted_band_still_gets_no_box(monkeypatch):
    """An inverted band must NOT become an empty per-sweep box: that would
    clamp to ``hi`` every sweep and freeze a node the kill-half ruling
    requires to stay MOVABLE (quarantine is unauthorized)."""
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    loose = [{"edges": [(0, 1, 100.0), (1, 2, 100.0)]}]
    band = [None, (25.0, 5.0), None]           # node 1 inverted
    elev = [0.0, 0.0, 40.0]
    broken = set()
    feasibility_project(elev, loose, {0, 2}, force_scalar=True,
                        max_iters=400, broken_out=broken, env_band=band)
    assert broken == {1}
    assert 5.0 - 1e-9 <= elev[1] <= 25.0 + 1e-9, elev


def test_the_band_ceiling_binds_per_sweep_too(monkeypatch):
    """Two-sided: the ceiling was already effectively binding (112 vs
    11,144), so this twin exists to keep it that way after the floor is
    fixed rather than to change anything."""
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    tight = [{"edges": [(0, 1, 0.01)]}]
    band = [None, (-20.0, -10.0)]
    elev = [0.0, 0.0]
    feasibility_project(elev, tight, {0}, force_scalar=True, max_iters=400,
                        env_band=band)
    assert elev[1] <= -10.0 + 1e-9, (
        f"the band CEILING must survive the sweeps, got {elev[1]}")


# ── THE BAND WINS A DECLARED GROUNDSIDE CONFLICT (cycle-6 Part P) ──────
#
# ``docs/specs/cycle6-band-wins-and-ingestion-spec.md``.  A freed
# groundside pin carries a per-sweep LAW ceiling (the lot's weld datum
# plus one throat of reach — ~1 m in a plateau world).  Where that box
# and the airside reach band are DISJOINT the merge used to declare a
# conflict, keep the pin box and DISCARD the band: measured at HECA, 14
# apron / service_junction nodes parked up to 87 m below their own band
# floor, which "airside is king" forbids outright.  The band binds; the
# groundside box yields.

def _pin_box_vs_band(monkeypatch, gs_pin, band=(90.0, 104.0), ceil=4.0):
    """Node 1: a groundside pin ceiling at ``ceil`` against a band that
    starts 86 m higher — the HECA carrier in miniature.  Hard node 0 sits
    in the band so the sweeps have a lawful place to put node 1."""
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    loose = [{"edges": [(0, 1, 100.0)]}]
    elev = [94.0, 4.0]
    feasibility_project(elev, loose, {0}, force_scalar=True, max_iters=400,
                        node_bounds={1: (-1e18, ceil)},
                        gs_pin_nodes=(gs_pin or None),
                        env_band=[None, band])
    return elev


def test_a_disjoint_pin_box_yields_to_the_band(monkeypatch):
    """THE Part-P twin: the conflict resolves AIRSIDE."""
    elev = _pin_box_vs_band(monkeypatch, {1})
    assert elev[0] == pytest.approx(94.0), "hard node never moves"
    assert elev[1] >= 90.0 - 1e-9, (
        f"the BAND must bind at a declared conflict, got {elev[1]}")
    assert elev[1] <= 104.0 + 1e-9, elev


def test_the_pin_box_still_binds_when_it_does_not_conflict(monkeypatch):
    """The yield is scoped to the CONFLICT.  A pin ceiling that overlaps
    the band still binds — this clause withdraws a groundside ceiling
    only where the two laws cannot both hold."""
    elev = _pin_box_vs_band(monkeypatch, {1}, band=(90.0, 104.0), ceil=95.0)
    assert elev[1] <= 95.0 + 1e-9, (
        f"a compatible pin ceiling must still bind, got {elev[1]}")
    assert elev[1] >= 90.0 - 1e-9, elev


def test_a_box_that_is_not_a_groundside_pin_is_not_ruled_here(monkeypatch):
    """A conflict on any OTHER box class (a building seat box) keeps
    today's behaviour and is reported UNRESOLVED — this clause resolves
    the groundside-vs-airside direction the owner has already ruled, and
    invents no ruling for a class the dossier never measured."""
    elev = _pin_box_vs_band(monkeypatch, set())
    assert elev[1] <= 4.0 + 1e-9, (
        f"an unruled conflict keeps the pre-existing box, got {elev[1]}")


def test_the_conflict_is_reported_loud_and_certified_at_exit(
        monkeypatch, capsys):
    """Never a silent resolution: the conflict prints one line naming
    BOTH halves and the resolution, ungated (no ``O4_STEP_DEBUG``), and
    the exit certificate re-checks that the node left the projection
    inside the band it was given."""
    monkeypatch.delenv("O4_STEP_DEBUG", raising=False)
    _pin_box_vs_band(monkeypatch, {1})
    out = capsys.readouterr().out
    assert "DECLARED CONFLICT(S)" in out, out
    assert "BAND WINS" in out, out
    assert "GROUNDSIDE box" in out and "AIRSIDE band" in out, out
    assert "conflict resolution EXIT" in out, out
    assert "1 band-bound node(s), 1 at or above their band floor" in out, out


# ── THE CONFLICT LINES REPORT FACTS, AND STAMP THEIR NODE SPACE ─────────
# Standing-instrument sweep 2026-08-06.  Two claims rode these lines that
# nothing here computes:
#   * "the lot conforms via the terrace/wall machinery" — a forward-looking
#     prediction about the groundside terrace/retaining-wall subsystem;
#   * "attribute at source" on the UNRESOLVED half — a catch-all bucket
#     labelled with a cause, plus an instruction to the reader.
# The RULE CITATION stays (this clause does implement airside-is-king) and
# the membership fact — in ``gs_pin_nodes`` or not — is world-invariant and
# printable.  Every node index is stamped with the space it lives in.

def test_the_conflict_line_states_membership_not_a_prediction(
        monkeypatch, capsys):
    """KNOWN ANSWER: one node, one conflict, resolved because node 1 IS in
    ``gs_pin_nodes`` — and the report says exactly that."""
    monkeypatch.delenv("O4_STEP_DEBUG", raising=False)
    _pin_box_vs_band(monkeypatch, {1})
    out = capsys.readouterr().out
    assert ("1 DECLARED CONFLICT(S) band vs pre-existing box "
            "[node-space fp-remapped: n=2]: 1 resolved BAND WINS "
            "(node in gs_pin_nodes; groundside pin box withdrawn — "
            "airside is king, RULINGS 2026-07-30), 0 UNRESOLVED "
            "(node not in gs_pin_nodes; pre-existing box kept)") in out
    # the per-node row carries both intervals AND its node space
    assert ("node 1 [fp-remapped]: GROUNDSIDE box [-1000000000000000000.000, "
            "4.000] vs AIRSIDE band [90.000, 104.000]") in out
    assert "conflict resolution EXIT [node-space fp-remapped: n=2]" in out
    for banned in ("terrace/wall machinery", "attribute at source",
                   "the lot conforms"):
        assert banned not in out, f"report code printed {banned!r}"


def test_an_unresolved_conflict_is_named_by_its_membership(
        monkeypatch, capsys):
    """The complement, KNOWN ANSWER: node 1 is NOT in ``gs_pin_nodes``, so
    the conflict is 0 resolved / 1 UNRESOLVED — and "UNRESOLVED" is
    defined by that membership, not by a guessed cause."""
    monkeypatch.delenv("O4_STEP_DEBUG", raising=False)
    _pin_box_vs_band(monkeypatch, set())
    out = capsys.readouterr().out
    assert ("1 DECLARED CONFLICT(S) band vs pre-existing box "
            "[node-space fp-remapped: n=2]: 0 resolved BAND WINS") in out
    assert ("1 UNRESOLVED (node not in gs_pin_nodes; pre-existing box "
            "kept)") in out
    assert "UNRESOLVED (box kept)" in out          # the per-node row
    assert "attribute at source" not in out


def test_the_per_sweep_band_box_line_is_a_known_answer(monkeypatch, capsys):
    """TWIN FOR AN UNTWINNED LINE (the ``O4_STEP_DEBUG`` band-box trace).

    KNOWN ANSWER on the pin-box fixture: node 0 is hard, so the ONLY
    candidate is node 1, which already carries a groundside box disjoint
    from its band — 0 added, 0 intersected, 1 declared conflict, 1 of them
    resolved BAND WINS.  Every count is a partition of the same one node.
    """
    monkeypatch.setenv("O4_STEP_DEBUG", "1")
    _pin_box_vs_band(monkeypatch, {1})
    out = capsys.readouterr().out
    assert ("band bound PER SWEEP [node-space fp-remapped: n=2]: 0 node "
            "box(es) added, 0 intersected with an existing box, 1 DECLARED "
            "CONFLICT(S) (1 resolved BAND WINS, 0 unresolved — existing "
            "box kept)") in out


def test_the_graph_envelope_line_counts_intervals_not_feasibility(
        monkeypatch, capsys):
    """TWIN FOR AN UNTWINNED LINE (the ``O4_STEP_DEBUG`` envelope-from-graph
    trace), and the calibration that fixes its vocabulary.

    KNOWN ANSWER, one node of each kind among the free nodes: node 1 has
    no band (off-net), node 2's band INVERTS (25 > 5), node 3's band is a
    non-empty interval.  Nodes 0 and 4 are hard and never counted.  So the
    three counters are exactly 1 / 1 / 1.

    ``non-inverted`` is the whole predicate — ``_b[0] <= _b[1]`` on ONE
    node.  It was printed as ``feasible=``, which names a property of the
    system that this loop never evaluates (the same over-claim the L−U
    carrier line carried).  ``the band answers`` was likewise an
    interpretation of these counters; what is a fact is that the
    pair-closure envelope was not computed, and why.
    """
    monkeypatch.setenv("O4_ENVELOPE_FROM_BAND", "1")
    monkeypatch.setenv("O4_STEP_DEBUG", "1")
    loose = [{"edges": [(0, 1, 100.0), (1, 2, 100.0),
                        (2, 3, 100.0), (3, 4, 100.0)]}]
    elev = [0.0, 0.0, 0.0, 0.0, 50.0]
    broken = set()
    feasibility_project(elev, loose, {0, 4}, force_scalar=True, max_iters=50,
                        broken_out=broken,
                        env_band=[None, None, (25.0, 5.0), (30.0, 40.0),
                                  None])
    out = capsys.readouterr().out
    assert broken == {2}, "only the INVERTED band declares a break"
    assert ("envelope from THE graph [node-space fp-remapped: n=5]: "
            "band-inverted=1 non-inverted=1 off-net=1 "
            "(pair-closure envelope not computed: env_band supplied)") in out
    assert "feasible=" not in out, (
        "a non-empty interval on one node is not a feasibility verdict")
    assert "the band answers" not in out


def test_no_pin_conflict_prints_nothing(monkeypatch, capsys):
    """Cost and noise: a build with no declared conflict is silent on
    this channel (the ungated report is a conflict report, not a trace)."""
    monkeypatch.delenv("O4_STEP_DEBUG", raising=False)
    _pin_box_vs_band(monkeypatch, {1}, band=(90.0, 104.0), ceil=95.0)
    out = capsys.readouterr().out
    assert "DECLARED CONFLICT" not in out, out
    assert "conflict resolution EXIT" not in out, out
