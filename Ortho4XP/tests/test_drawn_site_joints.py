"""``tools/drawn_site_joints.py`` (#2144): the drawn joint step of two span
rows -- a draped row on a mesh step, then the same rows as MSL seats."""
from __future__ import annotations

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

import drawn_site_joints as J  # noqa: E402
from auto_patch_v2.airport import deck_chain as DC  # noqa: E402


def test_draped_rows_step_and_msl_rows_meet():
    pc = DC.Piece((0.0, -32.6, 10.4, 8.0), (0.0, 0.0, 10.4, 8.0))
    placed = [DC.Placed(0, "s.obj", 0.0, 0.0, 0.0, (0.0, 0.0), pc),
              DC.Placed(1, "s.obj", 0.0, 0.0, 0.0, (0.0, 33.2), pc)]
    row = types.SimpleNamespace
    draped = [row(kind="OBJECT", elevation=None), row(kind="OBJECT", elevation=None)]
    steps = J.steps_of(placed, draped, [10.0, 11.5])
    assert len(steps) == 1 and abs(abs(steps[0]["step"]) - 1.5) < 1e-9
    msl = [row(kind="OBJECT_MSL", elevation=10.7), row(kind="OBJECT_MSL", elevation=10.7)]
    assert J.steps_of(placed, msl, [10.0, 11.5])[0]["step"] == 0.0
