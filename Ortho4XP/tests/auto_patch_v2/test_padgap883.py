"""Issue #883: a PAD rim faces a gap joint like pavement does.

A rigid pad joins its body through the connectivity union and takes that
body's shape (07c (3)), but its rim vertices no pavement shares carry no
vertex label.  ``planar.shapes._gap_joints`` read only shape-role faces by
vertex label, so a pad standing within the readers' contact horizon of a
SEPARATE shape (beyond the 0.5 m separation) declared no joint: the solve
withheld the near-miss frontage weld across the shapes
(``constraints.pads.frontage_contacts``), and the census then read the
lawful separation step as frontage / mid-edge rows.  MEASURED on the
issue's airport: a pad corner 0.8 m from a separate junction body, 1.04 m,
8 airside rows.

The fixture: apron B with a pad on its west edge; apron A west of the pad
across a 1.2 m strip of graded ground (a non-shape face both rings touch,
which is not the contour's case).
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v2shapes import RUNWAY, Y0, Y1, _airport, _face, _rect  # noqa: E402

GAP = 1.2


@pytest.fixture(scope="module")
def wide():
    law = Law.for_airport("ZZZZ")
    emit = _dc.replace(law.tables.emit,
                       instrument=_dc.replace(law.tables.emit.instrument, step_contact_tol_m=2.0))
    return Law(tables=_dc.replace(law.tables, emit=emit), ruleset_key=law.ruleset_key)


def _cells():
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-200, Y0, -GAP, Y1), (), None, None,
                 "airside", "apron", {}),
            Cell(2, "graded_strip", "strip", _rect(-GAP, Y0, 0.0, Y1), (), None, None,
                 "airside", "ground", {}),
            Cell(3, "building", "pad", _rect(0.0, Y0, 60.0, Y1), (), None, None,
                 "airside", "building", {}),
            Cell(4, "apron", "apronB", _rect(60.0, Y0, 200, Y1), (), None, None,
                 "airside", "apron", {})]


def test_a_pad_facing_a_separate_shape_across_the_horizon_declares_a_gap_joint(wide):
    _ap, pm, st, _cl = _airport(wide, _cells(), [])
    a = pm.shape_of_face[_face(pm, "apronA").id]
    b = pm.shape_of_face[_face(pm, "apronB").id]
    assert a != b and pm.shape_of_face[_face(pm, "pad").id] == b
    gaps = [j for j in pm.shape_joints if j.gap]
    assert len(gaps) == 1, pm.shape_joints
    (j,) = gaps
    assert set(j.shapes) == {a, b} and "building" in j.roles and j.pairs
    assert all(-GAP - 0.1 < x < 0.1 for x, _y in j.points)        # the gap's midline
    assert j.length_m > 0.9 * (Y1 - Y0)
