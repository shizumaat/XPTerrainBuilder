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

── CYCLE-7.5 INSTRUMENT SWEEP, TWO REPAIRS TO THIS FILE ──────────────

1. THESE TWINS RE-IMPLEMENTED THE THING UNDER TEST.  They ran a local
   ``classify()`` that transcribed the solve's precedence, so a change
   to the real precedence order could NOT fail them — a second
   implementation of the classifier, which is the same defect shape the
   file exists to guard against.  The rule now lives in ONE place,
   ``solve.classify_hard_anchors``, and both the solve and these twins
   call it.
2. THE SOURCE-TEXT SCAN IS GONE.  ``assert '{i: "seed_rwy_seam" for i in
   _hard_cat}' not in src`` was trivially satisfied and would stay
   satisfied under any rename, so it guarded nothing.  Its replacement is
   BEHAVIOURAL: no class may be assigned by a blanket — proven by
   feeding differently-sourced nodes and asserting they come out
   different, and by asserting the blanket's own residual counter reads
   zero when every hardened node has a publisher.

⚠ ``_hard_cat`` IS NOT REPORT-ONLY.  Two production consumers read its
VALUES by equality (the crown-freeze set and the runway-join sample set,
both feeding ``crown.build_crown_drop_field``, the writeback transform on
emitted elevations), so a change to WHICH NODES CARRY a class MOVES THE
SURFACE.  ``tests/test_solve_certificate_instrument.py`` carries the
membership-identity twins for both consumers.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import auto_patch.pipeline  # noqa: F401,E402  (import-cycle order)
from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    solve as SOLVE)

# THE CLASSIFIER THE SOLVE RUNS — not a transcription of it.
classify = SOLVE.classify_hard_anchors


def test_the_map_is_not_a_constant():
    """THE DEFECT, stated as a test: five differently-sourced hard nodes
    must come out as five classes, not one."""
    cat = classify(5, [True] * 5, flexed_idx={0}, seam_pins={1},
                   runway_anchor={2: 10.0}, runway_nodes={3})
    assert cat == {0: "rwy_flexed", 1: "seam_pin", 2: "rwy_join",
                   3: "rwy_profile", 4: "base_hard:unattributed"}
    assert len(set(cat.values())) == 5


def test_precedence_is_most_specific_first():
    """A flexed runway-join node is FLEXED: the flex is what chose its
    value, and the join anchor is the value it disagrees with."""
    cat = classify(1, [True], flexed_idx={0}, seam_pins={0},
                   runway_anchor={0: 1.0}, runway_nodes={0})
    assert cat[0] == "rwy_flexed"
    cat = classify(1, [True], flexed_idx=set(), seam_pins={0},
                   runway_anchor={0: 1.0}, runway_nodes={0})
    assert cat[0] == "seam_pin"
    cat = classify(1, [True], flexed_idx=set(), seam_pins=set(),
                   runway_anchor={0: 1.0}, runway_nodes={0})
    assert cat[0] == "rwy_join"


def test_a_soft_node_is_never_classified():
    cat = classify(3, [True, False, True], flexed_idx=set(),
                   seam_pins=set(), runway_anchor={}, runway_nodes=set())
    assert set(cat) == {0, 2}


def test_an_unclaimed_node_is_named_not_folded():
    """The residue is the whole point: a node no source claims must be
    COUNTABLE, not silently inflating a real population.  That inflation
    is what turned 1,077 mixed-provenance anchors into "100 % seam"."""
    cat = classify(2, [True, True], flexed_idx=set(), seam_pins=set(),
                   runway_anchor={}, runway_nodes=set())
    assert set(cat.values()) == {"base_hard:unattributed"}


def test_the_solve_calls_this_classifier_and_no_other():
    """The twin and the solve must share ONE implementation — the repair
    that replaced the old local ``classify()``.  A second copy is how a
    precedence change lands without failing this file."""
    import inspect
    src = inspect.getsource(SOLVE.solve_route_profile)
    assert "_hard_cat: dict = classify_hard_anchors(" in src
    assert classify is SOLVE.classify_hard_anchors


def test_no_class_is_assigned_by_blanket():
    """THE BEHAVIOURAL REPLACEMENT for the source-text scan.

    Every hard node here has a real publisher — the classifier claims
    all four, and the seam pass pinned two it had already claimed — so
    the downstream blanket must label NOTHING.  Its residual counter is
    the instrument: a nonzero ``unattributed`` IS an unattributed
    hardening channel, by definition, and this assertion is what makes
    a new one visible instead of silently named ``seam_spine_anchor``."""
    cat = classify(4, [True] * 4, flexed_idx={0}, seam_pins={1},
                   runway_anchor={2: 1.0}, runway_nodes={3})
    rep = SOLVE.attribute_seam_spine_hardening(cat, set(range(4)), {1, 2})
    assert rep["unattributed"] == 0
    assert rep["attributed"] == 0
    assert set(cat.values()) == {"rwy_flexed", "seam_pin", "rwy_join",
                                 "rwy_profile"}
    # and a node with no publisher at all is COUNTED, not absorbed.
    cat2 = classify(2, [True, False], flexed_idx={0}, seam_pins=set(),
                    runway_anchor={}, runway_nodes=set())
    rep2 = SOLVE.attribute_seam_spine_hardening(cat2, {0, 1}, set())
    assert rep2["unattributed"] == 1
