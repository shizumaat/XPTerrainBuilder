"""Twin of ``airport/wall_class._retains_its_height`` (issue #715): a THICK
wall is wall-class where it is slender for its height and the ground steps
across it by that height (KATL ``muro_concreto5``: 10.65 m tall, 3.46 m
thick, the apron 301.7 m on one side, the ground 291.1 m on the other)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np

from auto_patch_v2.classify.retaining_wall import wall_class_components
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.model.frame import Frame

FRAME = Frame("TEST", (33.64, -84.42), 16)
CFG = load_rules().service
_M_LAT = 1.0 / 111_320.0


class _StepDem:
    """``hi`` north of the wall's axis, ``lo`` south of it."""

    def __init__(self, y_axis: float, hi: float, lo: float):
        self.y, self.hi, self.lo = y_axis, hi, lo

    def z_many(self, xs, ys):
        return np.where(np.asarray(ys, dtype=float) > self.y, self.hi, self.lo)

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


def _airport(width_m: float, height_m: float, step_m: float):
    lat0, lon0 = 33.64, -84.42
    dlon = 100.0 / (111_320.0 * np.cos(np.radians(lat0)))
    ring = [(lat0, lon0), (lat0, lon0 + dlon), (lat0 + width_m * _M_LAT, lon0 + dlon),
            (lat0 + width_m * _M_LAT, lon0)]
    part = NS(rings=[ring], height_m=height_m, comp=0, line=False)
    m = NS(resource="objects/muro_concreto5.obj", parts=[part])
    _x, y_axis = FRAME.entry()(lon0, lat0 + 0.5 * width_m * _M_LAT)
    return NS(partition=NS(units=[NS(members=[m])]), frame=FRAME,
              dem=_StepDem(y_axis, 300.0, 300.0 - step_m))


def test_a_thick_wall_that_retains_its_height_is_wall_class():
    got = wall_class_components(_airport(3.46, 10.65, 10.6), CFG)
    assert len(got) == 1 and abs(got[0].height_m - 10.65) < 1e-9


def test_a_thick_wall_on_level_ground_is_not():
    assert wall_class_components(_airport(3.46, 10.65, 0.0), CFG) == []


def test_a_step_twice_the_height_is_not_this_wall():
    assert wall_class_components(_airport(3.46, 10.65, 21.3), CFG) == []


def test_a_block_too_thick_for_its_height_is_not():
    # 8 m wide for 10.65 m tall is a building on a slope, not a wall
    assert wall_class_components(_airport(8.0, 10.65, 10.6), CFG) == []


def test_without_a_dem_only_the_thin_rule_stands():
    ap = _airport(3.46, 10.65, 10.6)
    ap.dem = None
    assert wall_class_components(ap, CFG) == []
    assert len(wall_class_components(_airport(0.8, 10.65, 0.0), CFG)) == 1
