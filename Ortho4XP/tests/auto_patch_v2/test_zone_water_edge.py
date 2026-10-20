"""Owner RULINGS 2026-10-20k (issue #1104): runway end areas, safety areas
and the adjacent graded ground stop at the WATER'S edge — every water body
the frame's witness names (``dem.water_geometry``), not the sea alone.  An
estuary the coastline partition calls inland (KOTH's bay) cuts the zones;
the shore DECISION (quay / natural bank / wedge) stays the sea's."""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.law import Law
from auto_patch_v2.planar.zones import zone_regions

from test_v2vmmcshore import _PlaneDem, _zone_cells


class _InlandDem(_PlaneDem):
    """No sea at all; an INLAND body south of ``y = -30``."""

    def sea_geometry(self, bounds=None):
        return None

    def water_geometry(self, bounds=None, sea_only=False):
        if sea_only:
            return None
        return Polygon(((-5000.0, -5000.0), (5000.0, -5000.0),
                        (5000.0, -30.0), (-5000.0, -30.0)))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_inland_water_cuts_every_zone(law):
    regions = zone_regions(_zone_cells(), law, (), _InlandDem(), ())
    assert regions
    wet = _InlandDem().water_geometry()
    for r in regions:
        assert r.polygon.intersection(wet).area < 1e-6, r.ref


def test_inland_water_is_decided_as_the_coast_is(law):
    """The part reaching the inland edge takes the ONE shore decision."""
    wet = _InlandDem().water_geometry()
    reach = [r for r in zone_regions(_zone_cells(), law, (), _InlandDem(), ())
             if r.polygon.distance(wet) < 0.5]
    assert reach
    assert all(r.shore is not None and (r.quay or r.natural_shore) for r in reach)


def test_without_water_the_zones_reach_past_it(law):
    """The control: the same cells over a dry plane reach y < -30."""
    regions = zone_regions(_zone_cells(), law, (), _PlaneDem(), ())
    assert min(r.polygon.bounds[1] for r in regions) < -30.0


class _LevelDem:
    """A witness that reads water east of x = 0 at level 2.5 m."""

    def water_many(self, xs, ys):
        import numpy as np
        wet = np.asarray(xs) > 0.0
        return wet, np.where(wet, 2.5, np.nan)


def test_the_level_beside_a_shore_point_is_its_bodys():
    from auto_patch_v2.airport.water_level import water_level_beside
    lv = water_level_beside(_LevelDem(), [0.0, -100.0], [0.0, 0.0])
    assert lv[0] == 2.5          # on the line: a ring sample is wet
    assert lv[1] == 0.0          # far from any water: the sea's level
