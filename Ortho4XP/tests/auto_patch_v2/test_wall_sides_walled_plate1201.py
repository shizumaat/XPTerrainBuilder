"""#1201 (owner sim read 2026-11-04, KSEA 16C): a RUNWAY-END WALLED PLATE's
own walls are not two-level retaining walls for ``airport/wall_sides``: the
plate's top is seated on the solved safety area (RULINGS 2026-10-27u) and its
bottom sinks, so no band stops short of them, no wall slope holds the safety
area's end to a top read off the origin "as it sits" (16C: 131.1 m over a
DEM of 120-122 m), and no foot is held.

The synthetic wall of ``test_wall_sides1633``: 5 m thick along x = 60..65,
20 m retained, upper ground west, lower east."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport import wall_sides as WS
from shapely.geometry import box

WALL = box(60.0, -100.0, 65.0, 100.0)


class _StepDem:
    def z_many(self, xs, ys):
        t = np.clip((np.asarray(xs, float) - 50.0) / 25.0, 0.0, 1.0)
        return 300.0 - 20.0 * t

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


def _comp(mid):
    return types.SimpleNamespace(retains=True, retained_m=20.0, height_m=20.0,
                                 pieces=(WALL,), top_y=6.8, resource="w",
                                 member=types.SimpleNamespace(id=mid))


def _airport(plates=()):
    return types.SimpleNamespace(dem=_StepDem(), partition=object(),
                                 walled_plates=tuple(plates))


CFG = types.SimpleNamespace(retaining_wall_clear_step_m=2.0)


def test_an_ordinary_wall_is_read_as_two_levels():
    (w,) = WS.wall_sides(_airport(), CFG, [_comp("dsf:obj1")])
    assert w.upper is not None and w.lower is not None
    assert WS.band_setbacks((w,))


def test_a_walled_plate_wall_is_not_a_two_level_wall():
    plate = types.SimpleNamespace(ids=("dsf:obj1", "dsf:obj2"))
    got = WS.wall_sides(_airport([plate]), CFG, [_comp("dsf:obj2"), _comp("dsf:obj9")])
    # the plate's own wall is gone (no setback, no slope, no top or foot);
    # another placement's wall beside it stays
    assert len(got) == 1
    assert WS.band_setbacks(got) and len(WS.band_setbacks(got)) == 1
    assert WS.wall_sides(_airport([plate]), CFG, [_comp("dsf:obj1")]) == ()


def test_a_component_with_no_member_is_still_read():
    comp = _comp("x")
    del comp.member
    assert len(WS.wall_sides(_airport([types.SimpleNamespace(ids=("x",))]), CFG, [comp])) == 1
