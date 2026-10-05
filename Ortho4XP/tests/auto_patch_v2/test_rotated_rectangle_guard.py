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


# --- #418: the harness tools take the same guard -------------------------

TOOLS = Path(__file__).resolve().parents[2] / "tools"


def test_no_bare_minimum_rotated_rectangle_in_tools():
    """``tools/check_grade.py`` and ``tools/tunnel_portal_acceptance.py``
    read rectangles bare and printed the ``oriented_envelope`` warning in
    ``test_harness`` (#418); no tool may again."""
    bare = []
    for path in sorted(TOOLS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute)
                    and node.attr == "minimum_rotated_rectangle"):
                bare.append(f"{path.relative_to(TOOLS).as_posix()}:"
                            f"{node.lineno}")
    assert not bare, (
        "bare .minimum_rotated_rectangle in a tool (use "
        "auto_patch_v2.geom.rotated_rect.rotated_rectangle): "
        + ", ".join(bare))


def _load_check_grade():
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location(
        "rrguard_check_grade", TOOLS / "check_grade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_check_grade_ring_width_is_the_bare_reading():
    """``_ring_width_m`` through the guard reads the same width as the bare
    call, and stays silent with RuntimeWarning promoted to an error."""
    import math
    cg = _load_check_grade()
    rings = [
        [(0, 0), (10, 0), (10, 4), (0, 4)],                 # axis-aligned
        [(0, 0), (8, 6), (5, 10), (-3, 4)],                 # rotated
        [(0, 0), (30, 0.5), (29.5, 6), (0.2, 5.8), (-0.3, 3)],
    ]
    for ring in rings:
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            got = cg._ring_width_m(ring)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            xy = list(Polygon(ring).minimum_rotated_rectangle.exterior.coords)
        want = min(s for s in (math.hypot(xy[k + 1][0] - xy[k][0],
                                          xy[k + 1][1] - xy[k][1])
                               for k in range(len(xy) - 1)) if s > 0.0)
        assert got == want, (ring, got, want)

