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
    # the gap's midline, and the same declaration run along the pad's rim
    # (``shape_pad_corner``, owner 2026-11-03)
    mid = [j for j in gaps if not all(abs(x) < 1e-6 for x, _y in j.points)]
    assert len(mid) == 1 and len(gaps) == 2, pm.shape_joints
    (j,) = mid
    assert set(j.shapes) == {a, b} and "building" in j.roles and j.pairs
    assert all(-GAP - 0.1 < x < 0.1 for x, _y in j.points)        # the gap's midline
    assert j.length_m > 0.9 * (Y1 - Y0)


def _corner_cells():
    """Apron A faces only the SOUTH end of the pad's west edge; the strip it
    owns runs on north along the pad past the lens, as the strip by the
    hangar corner at the issue's site does."""
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-200, Y0, -GAP, Y0 + 20.0), (), None, None,
                 "airside", "apron", {}),
            Cell(2, "graded_strip", "strip", _rect(-GAP, Y0, 0.0, Y1), (), None, None,
                 "airside", "ground", {}),
            Cell(3, "building", "pad", _rect(0.0, Y0, 60.0, Y1), (), None, None,
                 "airside", "building", {}),
            Cell(4, "apron", "apronB", _rect(60.0, Y0, 200, Y1), (), None, None,
                 "airside", "apron", {})]


def test_the_gap_declaration_runs_along_the_pad_rim_past_the_lens(wide):
    """Owner 2026-11-03 ("accept recommendation", #883): the strip that
    carries the kept step off the pad past the facing lens is declared
    too — the run lies ON the pad rim, reaches the far corner, and pairs
    the rim with the strip's own vertices, so its step is the strip's."""
    _ap, pm, _st, _cl = _airport(wide, _corner_cells(), [])
    pad = _face(pm, "pad").id
    strip = _face(pm, "strip").id
    rim = [j for j in pm.shape_joints if j.gap and all(abs(x) < 1e-6 for x, _y in j.points)]
    assert len(rim) == 1, pm.shape_joints
    (j,) = rim
    ys = [y for _x, y in j.points]
    assert min(ys) <= Y0 + 1e-6 and max(ys) >= Y1 - 1e-6     # past the lens, to the corner
    on_pad = {v for v in pm.vertices if pad in pm.vertices[v].incident_faces}
    assert j.pairs and all(len({a, b} & on_pad) == 1 for a, b in j.pairs)
    assert any(strip in pm.vertices[w].incident_faces for a, b in j.pairs for w in (a, b)
               if w not in on_pad)


def test_no_rim_run_without_a_facing_gap(wide):
    """A pad no other shape faces declares nothing: the run needs the gap."""
    cells = [c for c in _corner_cells() if c.ref != "apronA"]
    _ap, pm, _st, _cl = _airport(wide, cells, [])
    assert not [j for j in pm.shape_joints if j.gap]
