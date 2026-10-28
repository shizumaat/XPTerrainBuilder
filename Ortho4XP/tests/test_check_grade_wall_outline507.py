"""The census reads the step across a declared pack wall along its WHOLE
outline (owner RULINGS 2026-10-28s (2), Q250 a, issue #507; found at HECA
``metal_strip_2.obj`` comp 12, whose east bend stepped 4.18 m across a
3.10 m wall with no ``terrace_actual_step`` row within 80 m).

Reading 1 of ``_check_terrace_actual_step`` sides a vertex by the joint's
nearest segment; a wall terrace's joint is the wall's closed outline, so
two vertices on the wall's two faces are both "outside" and never
straddle it.  Reading 3 (``check_grade_lib.families.wall_outline_step``)
prices every pair whose segment touches the wall.

Synthetic, in an identity frame (a node's ``lat``/``lon`` ARE local
metres ``(y, x)``): a 40 m wall 0.3 m thick along y = 0 declared at
3.11 m; apron S's edge 4 m south of it at 95 m; apron N's edge drawn AT
the wall's north face (0.05 m outside it)."""
from __future__ import annotations

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "tools"), os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_grade  # noqa: E402
from check_grade_lib.rows import Way  # noqa: E402

#: the wall's outline, closed (x, y)
OUTLINE = [(0.0, -0.15), (40.0, -0.15), (40.0, 0.15), (0.0, 0.15), (0.0, -0.15)]
STEP = 3.11


def _ll(x, y):
    return (y, x)


def _to_m(la, lo):
    return (lo, la)


def _apron(wid, pts, z):
    nids = [f"{wid}:{i}" for i in range(len(pts))] + [f"{wid}:0"]
    nodes = {f"{wid}:{i}": _ll(*p) for i, p in enumerate(pts)}
    w = Way(wid, "apron", wid, "apron", nids, [z] * len(nids), {"ref": wid})
    return w, nodes


def _run(z_north):
    s, ns = _apron("S", [(10.0, -4.0), (20.0, -4.0), (20.0, -20.0), (10.0, -20.0)], 95.0)
    n, nn = _apron("N", [(10.0, 0.2), (20.0, 0.2), (20.0, 20.0), (10.0, 20.0)], z_north)
    rows = [{"kind": "wall_terrace", "points": [list(_ll(*p)) for p in OUTLINE],
             "step_m": 1.0, "height_m": STEP - 0.01, "shapes": ["wall.obj#comp0"]}]
    walls = check_grade._wall_outlines_m(rows, _to_m)
    jm = check_grade._terrace_joints_to_m(rows, _to_m)
    return check_grade._check_terrace_actual_step(jm, [s, n], {**ns, **nn}, _to_m,
                                                  0.015, walls)


def test_a_step_past_the_wall_across_its_two_faces_is_read():
    got = _run(99.2)
    assert got and all(abs(v.de_m - 4.2) < 1e-9 for v in got)
    assert all({v.way_a.ref, v.way_b.ref} == {"S", "N"} for v in got)


def test_a_step_within_the_wall_is_lawful():
    assert _run(98.0) == []


def test_a_mouth_or_an_open_joint_is_not_read_as_an_outline():
    pts = [list(_ll(*p)) for p in OUTLINE]
    mouth = [{"kind": "wall_terrace", "points": pts, "step_m": 1.0,
              "height_m": 3.1, "shapes": ["portal.obj#mouth"]}]
    assert check_grade._wall_outlines_m(mouth, _to_m) == []
    open_ = [{"kind": "wall_terrace", "points": pts[:-1], "step_m": 1.0, "height_m": 3.1}]
    assert check_grade._wall_outlines_m(open_, _to_m) == []
