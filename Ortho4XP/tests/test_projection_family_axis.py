"""Cycle-7 fix 5 twin — the projection's uncertified exit NAMES the law.

Verdict (d) BROKEN INSTRUMENT in the c6attr attribution dossier: inside
``feasibility_project`` every flat group is collapsed onto a
representative, so the projection's own residual lives on REMAPPED pairs
and ``UnifiedGraph.family_by_pair`` — keyed on the ORIGINAL pairs —
resolves none of them.  At HECA that left the 1,184 structural edges
carrying the WORST residual of the whole solve (60.772738 m, carrier
``(962,5037)``) with no family name at all, in the one report that exists
to say which law could not be closed.

These twins pin the fixed contract:

1. a pad-member↔apron chord whose member end is aliased into a group
   representative is still named by its ORIGINAL family;
2. an entry that names its own law is never re-keyed per edge;
3. no map ⇒ the report is exactly what it was (absent, not empty).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "src"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    one_solve as OS)
from auto_patch.elevation_per_surface.route_profile.one_solve import (  # noqa: E402
    feasibility_project)


def _two_boxed_ends(family_tag):
    """A system that CANNOT certify, by construction.

    Node 0 and node 1 are one rigid pad group (representative 0, boxed at
    0.0); node 2 is an apron vertex boxed at 10.0.  The law edge is the
    PHYSICAL chord ``(1, 2)`` — pad-ring member to apron — with a 0.05 m
    budget it can never meet.  Every sweep moves both ends and the box
    clamps restore them: the exact 2-cycle the dossier measured at
    ``(962,5037)``, in four nodes.
    """
    return {
        "elev": [0.0, 0.0, 10.0],
        "shape_constraints": [{"family": family_tag,
                               "edges": [(1, 2, 0.05)]}],
        "flat_groups": [{0, 1}],
        "group_bounds": [(0.0, 0.0)],
        "node_bounds": {2: (10.0, 10.0)},
    }


def _run(capsys, *, family_of, family_tag="unified_graph"):
    kw = _two_boxed_ends(family_tag)
    elev = kw.pop("elev")
    sc = kw.pop("shape_constraints")
    feasibility_project(elev, sc, set(), max_iters=4, force_scalar=True,
                        family_of=family_of, **kw)
    return capsys.readouterr().out


def test_flat_group_member_edge_is_named_by_its_original_family(capsys):
    """The remapped pair resolves through the group→member map."""
    out = _run(capsys, family_of={(1, 2): "unified:apron"})
    assert "UNCERTIFIED EXIT" in out
    assert "residual BY FAMILY" in out
    assert "unified:apron" in out
    # The whole point: it is NOT dumped into the unnamed bucket.
    assert "<unmapped>" not in out


def test_entry_that_names_its_own_law_is_not_re_keyed(capsys):
    """A real shape entry already names its law — no per-edge lookup."""
    out = _run(capsys, family_of={(1, 2): "unified:apron"},
               family_tag="graded_strip:adjacent_ground")
    assert "graded_strip:adjacent_ground" in out
    assert "unified:apron" not in out


def test_no_family_map_leaves_the_report_unchanged(capsys):
    """Absent instrument ⇒ absent table (absent and empty differ)."""
    out = _run(capsys, family_of=None)
    assert "UNCERTIFIED EXIT" in out
    assert "residual BY FAMILY" not in out


def test_unmapped_pair_is_labelled_honestly_not_folded(capsys):
    """A catch-all entry with no map entry keeps its own construction tag.

    The catch-all tag is what the SOLVE's own untagged unified entry
    degrades to; a pair the map does not carry must keep that tag rather
    than silently joining a neighbouring law's count.
    """
    out = _run(capsys, family_of={})
    assert "unified_graph" in out


# ── THE FRAME, AND THE SIZE OF THE CATCH-ALL (2026-08-06 sweep) ──────────
# RULINGS 2026-08-06 §3-4.  The disagreement this axis exists to expose is
# a NODE-SPACE disagreement — the certificate's two readers ran on
# 142,635 / 144,056 nodes here against ``UnifiedGraph``'s 146,743 — so a
# table printed without its node space cannot be joined to the reader it
# disagrees with, and the disagreement stays invisible.  The owner's
# ruling names "the certificate's 80.6 % catch-all" as a falsified
# premise: the catch-all's SIZE and SHARE are therefore numbers, printed
# every time the table prints.

def test_the_family_table_carries_its_node_space(capsys):
    """KNOWN ANSWER: the fixture is 3 nodes and 1 law edge, and the pad
    group collapses node 1 onto representative 0 — so the table's own
    frame is ``fp-remapped, n=3, edges=1``, not the caller's space."""
    out = _run(capsys, family_of={(1, 2): "unified:apron"})
    assert "residual BY FAMILY [node-space fp-remapped: n=3, edges=1]" in out
    # the uncertified exit that carries it is stamped the same way
    assert "[stall-report] [node-space fp-remapped: n=3, edges=1]" in out


def test_a_resolved_family_counts_zero_unresolved(capsys):
    """KNOWN ANSWER: one over-cap edge, named by ``family_of`` ⇒ 0 of 1."""
    out = _run(capsys, family_of={(1, 2): "unified:apron"})
    assert ("NAMED BY NEITHER AUTHORITY: 0 of 1 over-cap edge(s) (0.0%) "
            "= 0 absent from family_by_pair + 0 left on a "
            "construction-site tag (_CATCH_ALL_FAMILY_TAGS)") in out


def test_the_catch_all_share_is_printed_as_its_own_number(capsys):
    """KNOWN ANSWER: the entry tag is a CONSTRUCTION SITE
    (``unified_graph``) and ``family_of`` is empty, so the one over-cap
    edge is named by NEITHER authority — 1 of 1, 100.0 %.

    Before this it appeared as an ordinary table row and the share had to
    be computed by hand from a truncated top-10 listing, which is how an
    80.6 % catch-all shipped as a family attribution.
    """
    out = _run(capsys, family_of={})
    assert ("NAMED BY NEITHER AUTHORITY: 1 of 1 over-cap edge(s) (100.0%) "
            "= 0 absent from family_by_pair + 1 left on a "
            "construction-site tag (_CATCH_ALL_FAMILY_TAGS)") in out
    assert "unified_graph" in out, "the row keeps its own honest tag"


def test_the_unresolved_accounting_splits_its_two_causes(capsys):
    """KNOWN-ANSWER CALIBRATION of the accounting itself, on a table whose
    answer is arithmetic: 4 unmapped + 3 + 2 catch-all = 9 of 20 = 45.0 %,
    and the named family is never counted.

    The two components are DIFFERENT findings — a pair the projection's
    own ``family_by_pair`` never carried, versus one whose entry named a
    construction site that the original-space map did not resolve — so
    they are reported as two numbers, not one bucket.
    """
    families = {
        "apron:x": (11, 5, 4.0, 0),          # named: never unresolved
        "<unmapped>": (4, 4, 9.5, 1),
        "unified_graph": (3, 1, 2.0, 0),
        "?:-": (2, 0, 0.5, 2),
    }
    OS._report_exit_families(families, n=7, n_edges=20)
    out = capsys.readouterr().out
    assert "[node-space fp-remapped: n=7, edges=20]" in out
    assert ("NAMED BY NEITHER AUTHORITY: 9 of 20 over-cap edge(s) (45.0%) "
            "= 4 absent from family_by_pair + 5 left on a "
            "construction-site tag (_CATCH_ALL_FAMILY_TAGS)") in out


def test_the_accounting_survives_a_truncated_table(capsys):
    """The share is over the WHOLE table, not the printed top-``top``.  A
    catch-all pushed past the cut-off is exactly the case where the number
    matters most.  KNOWN ANSWER: rows of 10 + 9 + 8 + 1 = 28 over-cap
    edges, of which the truncated-away ``unified_graph`` row is 1 —
    1 / 28 = 3.6 %."""
    families = {f"fam{k}": (10 - k, 0, 1.0, 0) for k in range(3)}
    families["unified_graph"] = (1, 1, 0.5, 0)
    OS._report_exit_families(families, top=3, n=5, n_edges=5)
    out = capsys.readouterr().out
    assert "... 1 more family(ies), 1 edge(s)" in out
    assert "NAMED BY NEITHER AUTHORITY: 1 of 28 over-cap edge(s) (3.6%)" \
        in out


def test_certified_exit_prints_no_family_table(capsys):
    """The axis rides the UNCERTIFIED exit only — a clean solve is quiet."""
    elev = [0.0, 0.0]
    feasibility_project(elev, [{"family": "unified_graph",
                                "edges": [(0, 1, 5.0)]}], set(),
                        max_iters=4, force_scalar=True,
                        family_of={(0, 1): "unified:apron"})
    out = capsys.readouterr().out
    assert "residual BY FAMILY" not in out
    assert "UNCERTIFIED EXIT" not in out


@pytest.mark.parametrize("materiality_side", ["over", "under"])
def test_materiality_column_splits_at_the_campaign_floor(capsys,
                                                         materiality_side):
    """The ≥0.01 m column is the convergence criterion's own denominator."""
    budget = 0.05
    gap = 10.0 if materiality_side == "over" else budget + 0.001
    elev = [0.0, 0.0, gap]
    feasibility_project(elev, [{"family": "unified_graph",
                                "edges": [(1, 2, budget)]}], set(),
                        max_iters=4, force_scalar=True,
                        flat_groups=[{0, 1}], group_bounds=[(0.0, 0.0)],
                        node_bounds={2: (gap, gap)},
                        family_of={(1, 2): "unified:apron"})
    out = capsys.readouterr().out
    row = [ln for ln in out.splitlines() if "unified:apron" in ln]
    assert row, out
    n_over, n_material = row[0].split()[1:3]
    assert n_over == "1"
    assert n_material == ("1" if materiality_side == "over" else "0")


def test_a_slab_and_a_cap_on_ONE_pair_keep_their_OWN_constructors(capsys):
    """FIX-4 ATTRIBUTION PRECONDITION — the kind is part of the identity.

    One remapped pair legitimately carries BOTH a symmetric cap (from the
    junction/apron shape that owns the chord) and a signed SLAB (from the
    zone law or a §10 rod), minted by DIFFERENT constructors and enforced
    as two separate edges.  A pair-only key let whichever entry was read
    first name both: at HECA that reported 2,038 adjacent-ground slabs as
    ``junction:-`` and 742 as ``apron:-``, while the dump shows those two
    families own ZERO interval edges — a slab-class decomposition that is
    simply wrong, in the instrument the fix-4 attribution rests on.

    KNOWN ANSWER: one slab, one cap, one pair, two families, one each.
    """
    elev = [0.0, 0.0, 10.0]
    feasibility_project(
        elev,
        [{"family": "junction:-", "edges": [(1, 2, 0.05)]},
         {"family": "graded_strip:adjacent_ground",
          "edges": [(1, 2, -0.02, 0.02)]}],
        set(), max_iters=4, force_scalar=True,
        flat_groups=[{0, 1}], group_bounds=[(0.0, 0.0)],
        node_bounds={2: (10.0, 10.0)},
        family_of={})
    out = capsys.readouterr().out
    # row layout: [stall-report] n_over n_material worst m n_interval family
    rows = {ln.split()[-1]: ln.split() for ln in out.splitlines()
            if ln.rstrip().split()[-1] in ("junction:-",
                                           "graded_strip:adjacent_ground")}
    assert set(rows) == {"junction:-", "graded_strip:adjacent_ground"}
    assert rows["junction:-"][5] == "0", "the cap is not a slab"
    assert rows["graded_strip:adjacent_ground"][5] == "1", (
        "the slab is not a cap")
