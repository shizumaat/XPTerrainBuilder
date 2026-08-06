"""Cycle-7 fix 3 twin — the hard-anchor class axis names real provenance.

Verdict (d) BROKEN INSTRUMENT.  ``solve_route_profile`` built its
hard-anchor category map as ``{i: "seed_rwy_seam" for i in base_hard}``
— a BLANKET CONSTANT.  Every base-hard node came out with one class name
whatever made it hard, and the ``rwy_join`` / ``rwy_flexed``
``setdefault`` calls right after it were dead for exactly the nodes they
describe.

THE MEASURED COST (the known answer this twin is calibrated against,
RULINGS 2026-08-06 "Instrument truth is law" item 1): the c6attr
attribution dossier reported "610 strictly-immovable anchors, and 100 %
of them are class ``seed_rwy_seam``" and built a whole seam-depth
argument on it.  The classifier could not have returned anything else.
At HECA ``--dem 1`` the same population holds 48.50-142.43 m against a
DEM of 1.000 with ZERO nodes at the DEM value — no ride in any pin — so
the class name pointed the depth question at the wrong branch.

These twins pin the contract on the classification RULE itself, in
isolation from the 8,000-line solve: precedence, coverage, and the
honest residue bucket.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def classify(n, base_hard, flexed, seam_pins, runway_anchor, runway_nodes):
    """The rule as ``solve_route_profile`` applies it.

    Kept as an executable statement of the precedence so the twin tests a
    RULE rather than a transcription: highest-specificity source first,
    and an unclaimed node is NAMED unattributed rather than folded into a
    neighbouring class.
    """
    out = {}
    for i in range(n):
        if not base_hard[i]:
            continue
        if i in flexed:
            out[i] = "rwy_flexed"
        elif i in seam_pins:
            out[i] = "seam_pin"
        elif i in runway_anchor:
            out[i] = "rwy_join"
        elif i in runway_nodes:
            out[i] = "rwy_profile"
        else:
            out[i] = "base_hard:unattributed"
    return out


def test_the_map_is_not_a_constant():
    """THE DEFECT, stated as a test: five differently-sourced hard nodes
    must come out as five classes, not one."""
    cat = classify(5, [True] * 5, flexed={0}, seam_pins={1},
                   runway_anchor={2: 10.0}, runway_nodes={3})
    assert cat == {0: "rwy_flexed", 1: "seam_pin", 2: "rwy_join",
                   3: "rwy_profile", 4: "base_hard:unattributed"}
    assert len(set(cat.values())) == 5


def test_precedence_is_most_specific_first():
    """A flexed runway-join node is FLEXED: the flex is what chose its
    value, and the join anchor is the value it disagrees with."""
    cat = classify(1, [True], flexed={0}, seam_pins={0},
                   runway_anchor={0: 1.0}, runway_nodes={0})
    assert cat[0] == "rwy_flexed"
    cat = classify(1, [True], flexed=set(), seam_pins={0},
                   runway_anchor={0: 1.0}, runway_nodes={0})
    assert cat[0] == "seam_pin"


def test_a_soft_node_is_never_classified():
    cat = classify(3, [True, False, True], flexed=set(), seam_pins=set(),
                   runway_anchor={}, runway_nodes=set())
    assert set(cat) == {0, 2}


def test_an_unclaimed_node_is_named_not_folded():
    """The residue is the whole point: a node no source claims must be
    COUNTABLE, not silently inflating a real population.  That inflation
    is what turned 1,077 mixed-provenance anchors into "100 % seam"."""
    cat = classify(2, [True, True], flexed=set(), seam_pins=set(),
                   runway_anchor={}, runway_nodes=set())
    assert set(cat.values()) == {"base_hard:unattributed"}


def test_the_blanket_constant_is_gone_from_the_source():
    """The literal that produced the artefact must not come back."""
    import inspect
    from auto_patch.elevation_per_surface.route_profile import solve
    src = inspect.getsource(solve.solve_route_profile)
    assert '{i: "seed_rwy_seam" for i in _hard_cat}' not in src
    assert 'base_hard:unattributed' in src
