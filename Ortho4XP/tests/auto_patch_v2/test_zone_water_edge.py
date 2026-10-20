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


def test_inland_water_makes_no_shore_decision(law):
    for r in zone_regions(_zone_cells(), law, (), _InlandDem(), ()):
        assert r.shore is None and not r.quay and not r.natural_shore


def test_without_water_the_zones_reach_past_it(law):
    """The control: the same cells over a dry plane reach y < -30."""
    regions = zone_regions(_zone_cells(), law, (), _PlaneDem(), ())
    assert min(r.polygon.bounds[1] for r in regions) < -30.0
