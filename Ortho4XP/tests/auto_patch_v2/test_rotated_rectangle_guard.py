"""ONE spelling of the oriented-envelope guard (owner 2026-09-04, 2026-10-04).

shapely 2.1's ``oriented_envelope`` emits a spurious numpy
``divide by zero`` RuntimeWarning on an axis-aligned or zero-length hull
edge; the rectangle it returns is correct.  The app shows engine stderr, so
a bare ``.minimum_rotated_rectangle`` anywhere in ``auto_patch_v2`` leaks
that noise into the owner's build log (OTHH tile +25+051, app 1.0.376).
Every caller goes through ``geom.rotated_rect.rotated_rectangle`` (the
``geom`` leaf; ``model.frame`` re-exports it).
"""
from __future__ import annotations

import ast
import warnings
from pathlib import Path

from shapely.geometry import Polygon

from auto_patch_v2.model.frame import rotated_rectangle

SRC = Path(__file__).resolve().parents[2] / "src" / "auto_patch_v2"

# a call site that carries its own numpy errstate guard, kept as written
OWN_GUARD = {"classify/airside_edge.py"}


def test_no_bare_minimum_rotated_rectangle_in_v2():
    bare = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        if rel == "geom/rotated_rect.py" or rel in OWN_GUARD:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute)
                    and node.attr == "minimum_rotated_rectangle"):
                bare.append(f"{rel}:{node.lineno}")
    assert not bare, (
        "bare .minimum_rotated_rectangle (use model.frame.rotated_rectangle): "
        + ", ".join(bare))


def test_the_guard_is_silent_and_returns_the_same_rectangle():
    box = Polygon([(0, 0), (10, 0), (10, 4), (0, 4)])      # axis-aligned
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        rect = rotated_rectangle(box)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        want = box.minimum_rotated_rectangle
    assert rect.equals(want)
    assert abs(rect.area - 40.0) < 1e-9
