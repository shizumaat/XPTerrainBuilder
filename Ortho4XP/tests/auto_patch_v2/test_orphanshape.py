"""Issue #81, owner RULINGS 2026-09-29j: a joint never mints a FACE-LESS
shape, and the per-body datum REFUSES one.

KCLT ``dsf:pol54`` (35.2009983, -80.9385961): contour joints inside ONE
face labelled 21 of its vertices for a shape that owned no face; the
per-body datum (09v) dropped them from the face's body and no body took
them, so they floated 4.5 m under the DEM on bending alone."""
from __future__ import annotations

import dataclasses as _dc

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.solve.rows import OrphanShapeError, _shape_bodies, orphan_shapes

from test_v2shapes import _airport, _dumbbell, law  # noqa: F401  (fixture)


def test_a_face_split_by_a_contour_joint_mints_no_orphan_shape(law):
    """The dumbbell is ONE face whose narrow mouth the body opening cuts:
    before 29j the minority side's label owned no face."""
    _ap, pm, st, _cl = _airport(law, _dumbbell(10.0), [])
    assert st.shapes.orphans_relabelled > 0          # the derivation met the class
    assert orphan_shapes(pm) == {}
    owned = set(pm.shape_of_face.values())
    assert set(pm.shape_of_vertex.values()) <= owned


def test_the_body_datum_refuses_a_hand_built_orphan(law):
    _ap, pm, _st, _cl = _airport(law, _dumbbell(10.0), [])
    v0, v1 = sorted(pm.shape_of_vertex)[:2]
    bad = dict(pm.shape_of_vertex)
    bad[v0] = bad[v1] = 999
    orphan = _dc.replace(pm, shape_of_vertex=bad)
    assert orphan_shapes(orphan) == {999: 2}
    with pytest.raises(OrphanShapeError, match=r"shape 999 \(2 vertices\)"):
        _shape_bodies(orphan, None, [])
