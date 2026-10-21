"""#1166: a plane row's coefficient that is 0 in exact arithmetic is
written as an exact 0, never as the ``cos(pi/2)`` rounding residue.

LPPS (tile +33-017): on an axis-aligned triangle the 16 direction rows
carried ~1e-16 on the corner the direction cannot see.  With the other two
corners fixed by stage 1 that residue was the row's only free term, the hard
set's ``2 / reduced row sum`` scaling multiplied its right-hand side by
~1e16, and a building pad solved to 1.2e11 m."""
from auto_patch_v2.constraints.taxi import box_rows, plane_rows
from auto_patch_v2.model.constraints import Source

SRC = Source("taxi", "plane_gradient (user 2026-07-05)", ())
XY = {1: (0.0, 0.0), 2: (5.0, 0.0), 3: (0.0, 2.5)}


def _coefs(rows):
    return [c for r in rows for _v, c in r.terms]


def test_axis_aligned_triangle_has_no_residue_terms():
    rows = plane_rows((1, 2, 3), XY, 0.015, SRC)
    assert len(rows) == 16
    tiny = [c for c in _coefs(rows) if 0.0 < abs(c) < 1e-9]
    assert tiny == []
    # the directions the triangle's legs span still carry their terms
    assert sum(1 for c in _coefs(rows) if c == 0.0) >= 4


def test_box_rows_have_no_residue_terms():
    rows = box_rows((1, 2, 3), XY, (1.0, 0.0), 0.015, 0.015, SRC)
    assert [c for c in _coefs(rows) if 0.0 < abs(c) < 1e-9] == []
