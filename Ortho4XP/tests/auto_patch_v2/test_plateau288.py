"""Twins for issue #288 (HECA apron shapeID 1175 ``pav1#plateau:building4/b1``:
spines, an erratic outline, and a pit 1.92 m under the plateau).

1. THE SPAN IS ONE BAND PER RUN (``pad_cut._held_span``): a frontage that
   bends in 2 m steps sweeps ONE band, with no wedge on the outside of a
   bend and no hole — the per-segment flat-capped bands fanned into a comb
   (HECA building4/b1: 122 zone holes, the spine at 30.1133729,
   31.4011679).  A ramp still ends the run, so the stretch between two
   blocks stays uncovered.
2. A REST PART ENCLOSED BY A PLATEAU PIECE JOINS IT
   (``pad_cut._enclosed_rests_to_plateau``): it borders no apron ring and
   no rest body, so it would stand as an apron face of its own inside the
   plateau — the 1.92 m pit's class.  A rest touching the outline's
   outside is untouched.
"""
from __future__ import annotations

import math

from shapely.geometry import Point, Polygon, box

from auto_patch_v2.planar.pad_cut import _enclosed_rests_to_plateau, _held_span


def _arc(n: int = 120, radius: float = 400.0, step_m: float = 2.0):
    """A frontage that turns gently, ``step_m`` between samples."""
    dth = step_m / radius
    return [(radius * math.cos(k * dth), radius * math.sin(k * dth))
            for k in range(n)]


def test_a_bending_frontage_sweeps_one_band_without_holes_or_wedges():
    pts = _arc()
    span = _held_span(pts, [False] * len(pts), 90.0)
    assert span.geom_type == "Polygon", span.geom_type
    assert len(span.interiors) == 0
    # no wedge on the outside of the bend: every point 85 m outward of a
    # sample is inside the band
    for x, y in pts[2:-2]:
        r = math.hypot(x, y)
        p = Point(x * (r + 85.0) / r, y * (r + 85.0) / r)
        assert span.covers(p)


def test_a_ramp_still_ends_the_run():
    pts = [(float(2 * k), 0.0) for k in range(60)]
    ramp = [20 <= k < 30 for k in range(60)]
    span = _held_span(pts, ramp, 30.0)
    assert span.geom_type == "MultiPolygon" and len(span.geoms) == 2
    assert not span.covers(Point(50.0, 0.0))          # the ramp stretch


def test_a_rest_enclosed_by_the_plateau_joins_it_and_an_outside_one_does_not():
    plateau = box(0.0, 0.0, 100.0, 50.0).difference(box(40.0, 20.0, 46.0, 26.0))
    island = box(40.0, 20.0, 46.0, 26.0)              # the plateau's hole
    outside = box(100.0, 0.0, 104.0, 4.0)              # touches it, outside
    rests, pieces, n = _enclosed_rests_to_plateau([island, outside], [plateau])
    assert n == 1
    assert rests == [outside]
    assert len(pieces) == 1 and len(pieces[0].interiors) == 0
    assert abs(pieces[0].area - 5000.0) < 1e-6
