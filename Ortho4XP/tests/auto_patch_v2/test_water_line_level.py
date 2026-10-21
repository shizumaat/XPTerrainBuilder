"""#1177: the land meets an INLAND body at its bank terrain (the mesh's
``water_smoothing`` rides the body up the bank), never at the body's median
below it; the SEA (``sea_smoothing_mode=zero``) is met at its level, 0."""
import numpy as np
from auto_patch_v2.geom.water_level import water_line_level
from shapely.geometry import box


class _Dem:
    """Water east of x=0: a sea polygon for y<0, an inland body (median
    level 0.0) for y>=0."""

    def __init__(self):
        self.sea = box(0.0, -100.0, 100.0, 0.0)

    def water_many(self, xs, ys):
        xs = np.asarray(xs, float)
        wet = xs >= 0.0
        return wet, np.where(wet, 0.0, np.nan)

    def sea_geometry(self, bounds):
        return self.sea.intersection(box(*bounds))


def test_inland_bank_meets_water_at_its_terrain():
    assert water_line_level(_Dem(), [-0.5], [50.0], [2.6])[0] == 2.6


def test_sea_shore_meets_water_at_sea_level():
    assert water_line_level(_Dem(), [-0.5], [-50.0], [2.6])[0] == 0.0


def test_inland_bank_never_below_body_level():
    assert water_line_level(_Dem(), [-0.5], [50.0], [-1.0])[0] == 0.0
