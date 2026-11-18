"""#2060 round 4: THE SEAT TILT FLOATS NO FOOT (owner 2026-10-20f #1086,
"so nothing floats"; 2026-10-22c, no support floats).

CYLW ``Hangar_9`` b0 (49.955886, -119.380657): a flat 75 m hangar on a
pad graded 1.6 m across, anchored at its low-side foot.  The least-
squares plane through its 13 ground-contact feet passes 0.23 m under that
foot, and :func:`placement_seat_tilt.fit` applies the plane's gradient
about the body's ORIGIN (pinned to the ground under the anchor) and drops
the intercept -- so the tilt lifted the far corners 0.17-0.45 m off the
pad (the owner's read; the drawn wall feet 0.15-0.19 m over the mesh).
The zero now sinks by what the tilt floats past the level seat, and every
body written in the frame (frame mates, attached and unattached riders)
sinks with it.
"""
from __future__ import annotations

import dataclasses as dc

import numpy as np
import test_tilted_group2060 as TG
from auto_patch_v2.airport import placement_seat_tilt as PST

# CYLW Hangar_9 b0's own fit rows: (x, authored y, z) in the body frame
# and the rise each foot owes at the level seat (- floats)
HANGAR_FEET = [(-74.8, 0.003, 65.9, 1.443), (-63.6, 0.002, 6.1, 0.467),
               (-10.5, 0.002, 65.4, 0.744), (0.0, 0.0, 0.0, 0.0),
               (-31.4, 0.002, 16.9, 0.250), (-29.4, 0.002, 17.3, 0.234),
               (-26.7, 0.0, 10.8, 0.097), (-26.7, 0.159, 10.9, -0.061),
               (-26.1, 0.002, 63.3, 0.947), (-26.0, 0.002, 63.5, 0.947),
               (-26.1, 0.002, 63.4, 0.949), (-26.0, 0.002, 63.4, 0.946),
               (-24.2, 0.002, 63.8, 0.925)]


def _fit(rows):
    pts = [(x, y, z) for x, y, z, _d in rows]
    rise = [d for *_p, d in rows]
    return PST.fit(pts, rise, max_total_deg=1.5, foot_tol_m=0.3), pts, rise


def test_the_cylw_hangar_tilt_sinks_its_zero_so_no_foot_floats_past_the_level_seat():
    seat, pts, rise = _fit(HANGAR_FEET)
    assert seat.applied
    assert 0.35 < seat.drop_m < 0.45            # the tilt alone floats 0.45 m
    p, d = np.asarray(pts, float), np.asarray(rise, float)
    after = p @ np.asarray(PST._split.tilt_matrix(seat.grad)).T
    res = d + p[:, 1] - after[:, 1] + seat.drop_m
    assert -res.min() <= 0.061 + 1e-6           # the level seat's own float
    assert res.max() <= 0.45                     # and it buries no deeper
    assert "zero sunk" in seat.reason


def test_a_tilt_that_floats_nothing_sinks_nothing():
    rows = [(x, 0.0, z, 0.01 * x + 0.02 * z) for x in (0.0, 30.0) for z in (0.0, 20.0)]
    seat, _p, _r = _fit(rows)
    assert seat.applied and seat.drop_m == 0.0
    assert "zero sunk" not in seat.reason


def test_no_float_drop_reads_only_the_float_the_tilt_adds():
    level = np.array([0.0, -0.10, 0.5])
    assert PST._no_float_drop(level, np.array([0.2, -0.05, 0.1])) == 0.0
    assert abs(PST._no_float_drop(level, np.array([0.2, -0.30, 0.1])) - 0.20) < 1e-12


def test_sunk_lowers_the_zero_and_the_offset_together():
    seat = dc.replace(TG._seat(TG._walls()), drop_m=0.25)
    b = TG._body(TG._walls())
    s = PST._sunk(b, seat)
    assert abs(s.anchor.y_zero - (b.anchor.y_zero + 0.25)) < 1e-12
    assert abs(s.anchor.offset[1] - (b.anchor.offset[1] + 0.25)) < 1e-12
    assert PST._sunk(b, dc.replace(seat, applied=False)) is b
