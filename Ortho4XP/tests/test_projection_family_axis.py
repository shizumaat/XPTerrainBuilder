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
