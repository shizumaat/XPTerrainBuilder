"""THE APRON STAGED SOLVE — movement surfaces solve first, the interior
conforms with the seniors frozen (spec
``docs/specs/apron-staged-solve-spec.md``, owner "proceed", 2026-08-21).

The four twins the spec pre-registers (section 6):

  (a) after the full projection every SENIOR node's value equals its A1
      value exactly, and the interior pairs are satisfied or reported;
  (b) the seniority partition is IDENTICAL between the bake and the
      census (sidecar round-trip);
  (c) flag-off is compose-v3 byte-for-byte;
  (d) an apron with NO movement surface has no senior set and projects
      exactly as today.

Headless: synthetic constraint entries, no DEM, no X-Plane data.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch import grade_law as GL
from auto_patch.elevation_per_surface.route_profile import one_solve as OS


# ── the partition function itself (spec section 3) ───────────────────

def test_seniority_is_endpoints_of_strict_pairs_and_transects():
    """A node is SENIOR when a STRICT pair or a BOUND TRANSECT touches it;
    everything else on the apron ring is INTERIOR."""
    sen = GL.apron_node_seniority(
        apron_nodes=[1, 2, 3, 4, 5],
        strict_pairs=[(1, 2)],
        transect_nodes=[5])
    assert sen == {1: GL.APRON_SENIOR, 2: GL.APRON_SENIOR,
                   3: GL.APRON_INTERIOR, 4: GL.APRON_INTERIOR,
                   5: GL.APRON_SENIOR}


def test_seniority_domain_is_the_apron_nodes_only():
    """A strict pair reaching OFF the apron ring never invents a node."""
    sen = GL.apron_node_seniority([1, 2], [(2, 99)], [98])
    assert set(sen) == {1, 2}
    assert sen[2] == GL.APRON_SENIOR


def test_an_apron_with_no_movement_surface_has_no_senior_set():
    """Twin (d): no frontage, no corridor, no transect ⇒ every node
    INTERIOR, and the staged split therefore has nothing to withhold."""
    sen = GL.apron_node_seniority([1, 2, 3], [], [])
    assert set(sen.values()) == {GL.APRON_INTERIOR}


# ── the entry splitter (spec section 2) ──────────────────────────────

def test_the_split_moves_interior_edges_and_keeps_everything_else():
    ent = {"edges": [(1, 2, 0.1), (3, 4, 0.2), (2, 3, 0.3)],
           "stage": "A", "role": "apron",
           "hyper": [((1, 2, 3, 4), (1.0, -1.0, -1.0, 1.0), 0.5, "s0")]}
    senior, interior = OS._split_apron_interior([ent], {(3, 4)})
    assert len(senior) == 1 and len(interior) == 1
    assert senior[0]["edges"] == [(1, 2, 0.1), (2, 3, 0.3)]
    assert interior[0]["edges"] == [(3, 4, 0.2)]
    # THE TRANSECT ROWS STAY WITH THE SENIOR HALF: a transect is a
    # movement-surface law and its nodes are senior by construction.
    assert "hyper" in senior[0] and "hyper" not in interior[0]
    # every other key rides along, so the stage partition still sees a
    # correctly tagged entry on BOTH halves.
    assert senior[0]["stage"] == "A" and interior[0]["stage"] == "A"


def test_no_law_leaves_the_system_in_the_split():
    """Edges are MOVED, never dropped — the two halves partition the input."""
    ent = {"edges": [(1, 2, 0.1), (3, 4, 0.2)], "stage": "A"}
    senior, interior = OS._split_apron_interior([ent], {(1, 2), (3, 4)})
    got = [e for sc in senior for e in sc["edges"]]
    got += [e for sc in interior for e in sc["edges"]]
    assert sorted(got) == [(1, 2, 0.1), (3, 4, 0.2)]


def test_an_entry_with_no_interior_edge_is_returned_unchanged():
    ent = {"edges": [(1, 2, 0.1)], "stage": "A"}
    senior, interior = OS._split_apron_interior([ent], {(7, 8)})
    assert senior[0] is ent and interior == []


def test_no_interior_pairs_means_no_split_at_all():
    """Twin (c)'s mechanism: nothing to withhold ⇒ the senior pass IS the
    whole pass, which is what makes flag-off byte-identical."""
    ent = {"edges": [(1, 2, 0.1)], "stage": "A"}
    senior, interior = OS._split_apron_interior([ent], set())
    assert senior == [ent] and interior == []


# ── the freeze (spec section 2 and the pre-delegated STOP) ───────────

def _run(entries, elev, hard, interior, n, staged=True):
    rep = {}
    saved = GL.APRON_STAGED_SOLVE
    try:
        GL.APRON_STAGED_SOLVE = staged
        OS.feasibility_project_partitioned(
            elev, entries, set(hard), receiver_nodes={n - 1}, n_nodes=n,
            apron_interior_pairs=interior, staged_report=rep)
    finally:
        GL.APRON_STAGED_SOLVE = saved
    return rep


def test_a_senior_node_does_not_move_in_the_interior_pass():
    """Twin (a).  Node 0 is pinned; 1 is SENIOR (strict pair 0-1); 2 is
    INTERIOR (its only pair is 1-2, withheld from A1).  After the full
    projection node 1 must hold exactly the value A1 settled it at, and
    node 2 must have absorbed the interior law instead."""
    n = 4
    elev = [0.0, 10.0, 20.0, 0.0]
    entries = [{"edges": [(0, 1, 1.0), (1, 2, 1.0)], "stage": "A"}]
    rep = _run(entries, elev, {0, 3}, {(1, 2)}, n)
    assert rep.get("senior_moved") == 0
    # A1 drove the strict pair 0-1 to its cap; node 1 is senior and frozen
    # in A2, so the interior pair 1-2 could only move node 2.
    assert abs(elev[1] - 1.0) < 1e-6, elev
    assert abs(elev[2] - 2.0) < 1e-6, elev
    # ONE mover: node 2.  Node 1 is an endpoint of the interior pair but
    # is SENIOR (the strict pair 0-1 touches it), and the seniority
    # partition — not the pair's endpoints — is what decides.
    assert rep.get("interior_movers") == 1
    assert rep.get("senior_moved") == 0


def test_the_staged_report_splits_A1_and_A2():
    """Spec section 4: the certificate reports the two passes separately."""
    n = 4
    elev = [0.0, 10.0, 20.0, 0.0]
    rep = _run([{"edges": [(0, 1, 1.0), (1, 2, 1.0)], "stage": "A"}],
               elev, {0, 3}, {(1, 2)}, n)
    for k in ("a1_over_cap", "a1_both_hard", "a2_over_cap", "a2_both_hard"):
        assert k in rep, f"{k} missing from the staged report"


def test_flag_off_runs_one_pass_and_reports_nothing_staged():
    """Twin (c): with the kill switch off there is no A2 at all."""
    n = 4
    elev = [0.0, 10.0, 20.0, 0.0]
    rep = _run([{"edges": [(0, 1, 1.0), (1, 2, 1.0)], "stage": "A"}],
               elev, {0, 3}, {(1, 2)}, n, staged=False)
    assert "a2_over_cap" not in rep
    assert "a1_over_cap" not in rep


def test_flag_off_equals_the_unstaged_projection_value_for_value():
    """Twin (c) at the value level: the same system, staged off, lands
    exactly where a projection with no interior partition lands."""
    n = 4
    base = [0.0, 10.0, 20.0, 0.0]
    ents = [{"edges": [(0, 1, 1.0), (1, 2, 1.0)], "stage": "A"}]
    a = list(base)
    _run([dict(e) for e in ents], a, {0, 3}, {(1, 2)}, n, staged=False)
    b = list(base)
    _run([dict(e) for e in ents], b, {0, 3}, (), n, staged=True)
    assert a == pytest.approx(b)


def test_an_apron_with_no_movement_surface_projects_as_today():
    """Twin (d) at the projection level: every pair interior ⇒ A1 has no
    edges, A2 carries them all, and the surface still converges."""
    n = 4
    elev = [0.0, 10.0, 20.0, 0.0]
    rep = _run([{"edges": [(0, 1, 1.0), (1, 2, 1.0)], "stage": "A"}],
               elev, {0, 3}, {(0, 1), (1, 2)}, n)
    assert rep.get("senior_moved") == 0
    assert rep.get("a1_over_cap") == 0      # A1 had no law to enforce
    assert abs(elev[1] - 1.0) < 1e-6 and abs(elev[2] - 2.0) < 1e-6


def test_a_lazy_entry_is_never_split():
    """A lazy entry's pair set has not been generated yet, and half of one
    carrying ``lazy_expand`` without ``lazy_nodes``/``lazy_seed`` is a
    KeyError in the projection's own lazy-expansion check — measured: it
    killed the SPJC staged build at 288 s.  The whole entry stays senior."""
    ent = {"edges": [(1, 2, 0.1)], "stage": "A",
           "lazy_expand": lambda: [], "lazy_nodes": [1, 2],
           "lazy_seed": [0.0, 0.0]}
    senior, interior = OS._split_apron_interior([ent], {(1, 2)})
    assert senior == [ent] and interior == []


def test_no_interior_half_ever_carries_lazy_machinery():
    """Belt and braces for the same class: even a NON-lazy entry that
    happens to carry a lazy key hands none of it to the interior half."""
    ent = {"edges": [(1, 2, 0.1), (3, 4, 0.2)], "stage": "A",
           "lazy_move_tolerance": 1e-3}
    _senior, interior = OS._split_apron_interior([ent], {(3, 4)})
    assert interior and not any(
        k.startswith("lazy_") for k in interior[0])


# ── BOTH-SENIOR INTERIOR PAIRS ENTER A1 (lead 2026-08-23) ────────────

def test_a_both_senior_interior_pair_is_corrected_in_A1():
    """MEASURED GAP: A2 freezes every non-mover and the spec withholds
    interior pairs from A1, so an interior pair whose endpoints are BOTH
    SENIOR was priced by NEITHER pass — 21,117 of them at SPJC.  It now
    joins A1 at its own cap.

    Nodes 1 and 2 are both senior (each carries a strict pair to a pin);
    the interior pair 1-2 is over its 5 % cap.  A1 must correct it."""
    n = 6
    #        0 pin   1        2        3 pin    4,5 receivers/pad
    elev = [0.0, 0.0, 10.0, 0.0, 0.0, 0.0]
    entries = [{"edges": [(0, 1, 1.0), (3, 2, 1.0), (1, 2, 1.0)],
                "stage": "A"}]
    rep = _run(entries, elev, {0, 3, 5}, {(1, 2)}, n)
    assert rep.get("a1_both_senior_pairs") == 1, (
        "the both-senior interior pair must be handed to A1")
    assert abs(elev[1] - elev[2]) <= 1.0 + 1e-6, (
        f"A1 must bring the pair under its cap; got {elev[1]} vs {elev[2]}")
    # With the pair hoisted, A2 has no interior edge left at all, so it
    # never runs and never reports — which is itself the point: nothing was
    # left frozen-and-unpriced.
    assert rep.get("senior_moved") in (0, None)


def test_an_interior_pair_with_a_mover_stays_in_A2():
    """The complement: a pair with at least one interior MOVER is exactly
    what A2's freeze is built for and must not be hoisted."""
    n = 4
    elev = [0.0, 10.0, 20.0, 0.0]
    rep = _run([{"edges": [(0, 1, 1.0), (1, 2, 1.0)], "stage": "A"}],
               elev, {0, 3}, {(1, 2)}, n)
    assert not rep.get("a1_both_senior_pairs"), (
        "node 2 is an interior mover, so 1-2 belongs to A2")
    assert rep.get("interior_movers") == 1


def test_no_law_leaves_the_system_when_the_interior_is_repartitioned():
    ent = {"edges": [(1, 2, 0.1), (3, 4, 0.2)], "stage": "A"}
    both, rest = OS._partition_interior_by_mover([ent], {4})
    got = [e for sc in both for e in sc["edges"]]
    got += [e for sc in rest for e in sc["edges"]]
    assert sorted(got) == [(1, 2, 0.1), (3, 4, 0.2)]
    assert both and both[0]["edges"] == [(1, 2, 0.1)]
    assert rest and rest[0]["edges"] == [(3, 4, 0.2)]


def test_the_interior_partition_carries_no_lazy_machinery():
    ent = {"edges": [(1, 2, 0.1)], "stage": "A", "lazy_move_tolerance": 1e-3}
    both, _rest = OS._partition_interior_by_mover([ent], set())
    assert both and not any(k.startswith("lazy_") for k in both[0])


# ── ONE PARTITION INPUT (lead 2026-08-23) ────────────────────────────

def test_the_runtime_publishes_its_seniority_for_the_exporter():
    """The sidecar used to RECOMPUTE the partition from a narrower
    population (only unified:apron families counted as strict), exporting
    2,395/751 against the runtime's 2,962/83.  A partition nobody solved is
    not evidence about the solve, so the runtime publishes its own."""
    n = 4
    elev = [0.0, 10.0, 20.0, 0.0]
    rep = _run([{"edges": [(0, 1, 1.0), (1, 2, 1.0)], "stage": "A"}],
               elev, {0, 3}, {(1, 2)}, n)
    sen = rep.get("seniority")
    assert isinstance(sen, dict) and sen, "the runtime must publish it"
    import auto_patch.grade_law as GL
    assert sen.get(1) == GL.APRON_SENIOR
    assert sen.get(2) == GL.APRON_INTERIOR


def test_the_exporter_prefers_the_runtime_partition():
    import inspect
    from auto_patch.elevation_per_surface.route_profile import solve as S
    src = inspect.getsource(S.final_grade_projection)
    assert '_fp_staged_report.get("seniority")' in src, (
        "the export must read the runtime's own partition first")


# ── REPORTING FRAME (lead 2026-08-23) ────────────────────────────────

def test_the_exit_line_names_the_excluded_both_hard_population():
    """[converged] describes the SWEPT set while the tally counts every
    edge, so the difference must be named or the two cannot reconcile."""
    import inspect
    src = inspect.getsource(OS)
    assert "excluded_both_hard=" in src
    assert "_excluded_both_hard += 1" in src
    assert src.count("_excluded_both_hard += 1") == 2, (
        "both exclusion sites (symmetric and interval) must count")


def test_an_all_hard_hyper_row_neither_blocks_nor_moves():
    """3(c): a hyperplane row whose every node is frozen cannot be
    projected, so it must not hold ``any_active`` — otherwise the sweep can
    never certify and burns its whole budget on a row it cannot touch.  It
    is still reported."""
    import inspect
    src = inspect.getsource(OS)
    assert "_movable = _nrm > 0.0" in src
    assert "_act = (_r > tol) & _movable" in src


def test_the_A2_docket_exists_and_mirrors_A1s():
    import inspect
    src = inspect.getsource(OS)
    assert '_report["a2_both_hard_raw"]' in src
    from auto_patch.elevation_per_surface.route_profile import solve as S
    csrc = Path(S.__file__).read_text()
    # (the phrase is split across source lines by the formatter, so match
    # its halves rather than the concatenated literal)
    assert "A2 BOTH-HARD top" in csrc
    assert "THE FREEZE " in csrc and "DOCKET (an interior pair" in csrc
    assert 'report["a2_both_hard_rows"]' in csrc
