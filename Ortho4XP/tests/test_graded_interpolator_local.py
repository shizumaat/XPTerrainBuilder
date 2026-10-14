"""Issue #660: the replay instrument's design-surface sampler is LOCAL.

``tools/obj8_split_report.surface_from_graded`` (and through it
``seat_feet_census``, ``jetway_rider_census`` and ``v2_rebake_replay``'s
``--graded`` sampler) reads the emitted surface by linear interpolation over
a Delaunay of its vertices.  Built over raw ``(lat, lon)``, Qhull resolved
every near-cocircular quad by its processing order, so a face added 800 m
away re-triangulated the ground under another unit (OTHH: ``03_003`` b0
moved −1.62 m with 0.00 m difference at its plan feet).  The twin: a field
of near-tied quads, then vertices added FAR AWAY but inside the field's
extent — the readings over the field must not change.  The raw-degree
interpolator is the RED arm and must still fail, so the twin keeps proving
that it tests something.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))
import obj8_split_report as RPT                                  # noqa: E402

_LA0, _LO0 = 25.2575, 51.6124
_DLA, _DLO = 2.0 / 111320.0, 2.0 / 100700.0        # a 2 m grid


def _field(seed: int = 1):
    """A 40 x 40 grid of 2 m quads, each vertex off the grid by up to
    1e-8 deg (~1 mm: the float noise of a metric-to-degree emit), random
    z; a frame of corner points so the far additions fall INSIDE the
    extent; the far vertices 800 m away; and query points inside the grid."""
    rng = np.random.default_rng(seed)
    grid = np.array([(_LA0 + i * _DLA, _LO0 + j * _DLO)
                     for i in range(40) for j in range(40)])
    grid = grid + rng.uniform(-1e-8, 1e-8, grid.shape)
    frame = np.array([(_LA0 - 0.002, _LO0 - 0.002), (_LA0 - 0.002, _LO0 + 0.012),
                      (_LA0 + 0.012, _LO0 - 0.002), (_LA0 + 0.012, _LO0 + 0.012)])
    pts = np.r_[grid, frame]
    z = np.r_[rng.uniform(0.0, 2.0, len(grid)), np.zeros(len(frame))]
    far = np.c_[_LA0 + 0.007 + rng.uniform(0, 0.002, 300),
                _LO0 + 0.008 + rng.uniform(0, 0.002, 300)]
    zf = rng.uniform(0.0, 1.0, len(far))
    q = np.c_[_LA0 + rng.uniform(2 * _DLA, 37 * _DLA, 4000),
              _LO0 + rng.uniform(2 * _DLO, 37 * _DLO, 4000)]
    return pts, z, far, zf, q


def _moved(make) -> int:
    pts, z, far, zf, q = _field()
    a = np.asarray(make(pts, z)(q[:, 0], q[:, 1])).reshape(-1)
    b = np.asarray(make(np.r_[pts, far], np.r_[z, zf])(q[:, 0], q[:, 1])
                   ).reshape(-1)
    return int((np.abs(a - b) > 1e-6).sum())


def test_far_vertices_do_not_move_the_field():
    assert _moved(RPT.GradedInterpolator) == 0


def test_raw_degree_delaunay_is_the_red_arm():
    from scipy.interpolate import LinearNDInterpolator

    def raw(pts, z):
        f = LinearNDInterpolator(pts, z)
        return lambda la, lo: f(np.c_[la, lo])
    assert _moved(raw) > 0


def test_origin_is_not_moved_by_a_vertex_inside_the_extent():
    pts, z, far, zf, _q = _field()
    assert np.array_equal(RPT.GradedInterpolator(pts, z).origin,
                          RPT.GradedInterpolator(np.r_[pts, far],
                                                 np.r_[z, zf]).origin)


def test_translation_keeps_the_readings():
    """A translation is the same Delaunay: on a plane the reading is the
    plane, through the scalar and the vectorised calls alike."""
    pts, _z, _far, _zf, q = _field()
    plane = 3.0 + 1e4 * (pts[:, 0] - _LA0) - 2e4 * (pts[:, 1] - _LO0)
    f = RPT.GradedInterpolator(pts, plane)
    want = 3.0 + 1e4 * (q[:, 0] - _LA0) - 2e4 * (q[:, 1] - _LO0)
    assert np.allclose(np.asarray(f(q[:, 0], q[:, 1])).reshape(-1), want,
                       atol=1e-6)
    assert abs(float(np.asarray(f(q[0, 0], q[0, 1])).reshape(-1)[0])
               - want[0]) < 1e-6
    # outside the hull the interpolator reads nothing
    assert not np.isfinite(np.asarray(f(_LA0 - 1.0, _LO0)).reshape(-1)[0])
