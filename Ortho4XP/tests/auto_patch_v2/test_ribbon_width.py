"""ISSUE #949 — THE AT-GRADE RIBBON TAKES THE MAP'S WIDTH.

A mapped road's ribbon is half its mapped carriageway (``width``, else
``lanes`` x ``[tunnel] lane_width_m``) and never narrower than the core's
levelled half-width; the wider buffer only grows around the core-width
ribbon the same axis mints, so a road the pavement already traces never
lays a strip along that pavement's edge."""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, box

from auto_patch_v2.airport.road_ways import mapped_width_m, ribbon_half_width_m
from auto_patch_v2.classify.ribbon_mint import _ribbon_over
from auto_patch_v2.law import Law
from auto_patch_v2.planar.structure_approach import carriageway_width_m


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_the_ribbon_half_width_reads_the_map(law):
    tn = law.tables.structures.tunnel
    core = float(law.tables.emit.road_profile.lane_width_m)
    assert ribbon_half_width_m({"lanes": "7"}, law) == pytest.approx(3.5 * tn.lane_width_m)
    assert ribbon_half_width_m({"width": "30 m"}, law) == pytest.approx(15.0)
    # an untagged, two-lane or unparseable way keeps the core's ribbon
    for tags in ({}, {"lanes": "2"}, {"lanes": "1"}, {"lanes": "2;3"}):
        assert ribbon_half_width_m(tags, law) == pytest.approx(core)


def test_the_structures_read_the_same_width(law):
    tn = law.tables.structures.tunnel
    for tags in ({}, {"lanes": "5"}, {"width": "9.5"}, {"lanes": "x"}):
        assert carriageway_width_m(tags, law) == mapped_width_m(
            tags, tn.lane_width_m, tn.default_lanes)


def test_a_wide_ribbon_grows_around_the_core_ribbon_only():
    axis = [LineString([(0.0, 0.0), (100.0, 0.0)])]
    free = _ribbon_over(axis, 12.0, box(500, 500, 501, 501), 4.0, 0.01)
    assert free.area == pytest.approx(100.0 * 24.0, rel=1e-3)
    # pavement traces the road over its first 60 m (covers the core ribbon,
    # not the wider buffer): no strip is laid along that pavement's edge
    paved = box(-1.0, -5.0, 60.0, 5.0)
    rib = _ribbon_over(axis, 12.0, paved, 4.0, 0.01)
    assert rib.intersection(box(0.0, -20.0, 50.0, 20.0)).area == pytest.approx(0.0, abs=1e-6)
    assert rib.intersection(box(70.0, -20.0, 100.0, 20.0)).area == pytest.approx(30.0 * 24.0, rel=1e-3)
