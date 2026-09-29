"""Issue #81, owner RULINGS 2026-09-29j narrowed by 29k: an in-face joint
(08k's narrow mouth inside ONE face) keeps its face-less minority shape only
where the DEM EARNS it (a drop >= ``materiality.step_m`` across the mouth);
that shape gets its OWN datum body, and the refusal fires only on a
face-less shape that could land in no body.

KCLT ``dsf:pol54`` (35.2009983, -80.9385961): an UNEARNED in-face joint
(DEM 214.98 vs 215.12) labelled 21 vertices for a face-less shape; the
per-body datum dropped them from every body and they floated 4.5 m under
the DEM on bending alone."""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch_v2.solve.rows import OrphanShapeError, _shape_bodies, orphan_shapes  # noqa: E402

from test_v2shapes import MOUTH_BENCH, _airport, _dumbbell, law  # noqa: E402,F401  (fixture)


class _Red:
    """Every vertex a free column (the membership read needs only ``col``)."""

    class _Col(dict):
        def __missing__(self, _k):
            return 0

    col = _Col()


def _bodies(pm):
    from auto_patch_v2.solve.rows import _role_bodies_faced
    return _shape_bodies(pm, _Red, _role_bodies_faced(pm, {"apron"}, _Red))


def test_an_unearned_in_face_joint_mints_no_orphan_shape(law):
    _ap, pm, st, _cl = _airport(law, _dumbbell(10.0), [])
    assert st.shapes.orphans_relabelled > 0 and st.shapes.orphans_earned == 0
    assert orphan_shapes(pm) == {}


def test_an_earned_in_face_joint_keeps_its_shape_and_gets_its_own_body(law):
    _ap, pm, st, _cl = _airport(law, _dumbbell(10.0), [], dem=MOUTH_BENCH)
    assert st.shapes.orphans_earned == 1
    (sh, n), = orphan_shapes(pm).items()
    bodies = _bodies(pm)
    mine = [b for b in bodies if all(pm.shape_of_vertex.get(v) == sh for v in b)]
    assert len(mine) == 1 and len(mine[0]) == n              # every vertex of it, in its own body
    assert not any(v in b for b in bodies if b is not mine[0] for v in mine[0])


def test_the_body_datum_refuses_a_face_less_shape_that_lands_in_no_body(law):
    _ap, pm, _st, _cl = _airport(law, _dumbbell(10.0), [])
    bad = dict(pm.shape_of_vertex)
    bad[-7] = bad[-8] = 999                                   # ringing no face at all
    orphan = _dc.replace(pm, shape_of_vertex=bad)
    assert orphan_shapes(orphan) == {999: 2}
    with pytest.raises(OrphanShapeError, match=r"shape 999 \(2 vertices\)"):
        _shape_bodies(orphan, _Red, [])
