"""THE ROAD BESIDE THE BAND TRUMPS THE BAND (owner 2026-10-19, issue #944;
``planar/road_yield``).

The test case was KBUR (34.196709421, -118.348961910): a 7-lane road beside
an apron whose centreline ran 6.7 m outside the taxiway band, so the band
graded 5.5 m of the road's 24.5 m carriageway.  The twins hold the general
rule: a road whose centreline runs OUTSIDE every band takes its carriageway
(plus the groundside stand-off) out of the band; a road INSIDE a band is
left to the standing in-band law (RULINGS 2026-09-13ar / 29r: it grades
with the zone).
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, box
from shapely.ops import unary_union

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import snap_margin_m, zone_edge_offset_m
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.road_yield import road_carriageways
from auto_patch_v2.planar.zones import zone_regions

#: a taxiway 30 m wide along y, its east edge at x = 0
PAV = ((-30.0, -400.0), (0.0, -400.0), (0.0, 400.0), (-30.0, 400.0))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cells():
    return (Cell(0, "junction", "T", PAV, (), None, "C", "airside", "junction", {}),)


def _road(x: float, **tags) -> OsmWay:
    return OsmWay(1, "big_roads", ((x, -300.0), (x, 300.0)), False,
                  {"highway": "secondary", **tags})


def _bands(law, ways=()):
    regions = zone_regions(_cells(), law, carriageways=road_carriageways(ways, law))
    return unary_union([r.polygon for r in regions])


def test_a_road_beside_the_band_keeps_its_carriageway(law):
    reach = zone_edge_offset_m(law, "junction", None, "C")
    # the centreline outside the band, the near kerb inside it (and clear
    # of the pavement, so a gap remains for the band to stand in)
    x = reach + 12.0
    road = _road(x, lanes="7")
    carriageway = LineString([(x, -300.0), (x, 300.0)]).buffer(12.25, cap_style="flat")
    before = _bands(law)
    after = _bands(law, (road,))
    # the defect the rule removes: the band stood on the road
    assert before.intersection(carriageway).area > 100.0
    assert after.intersection(carriageway).area == pytest.approx(0.0, abs=1e-6)
    # the band ends the stand-off short of the carriageway, not further
    # (the stand-off every groundside cell gets: the cut-back past the
    # identity snap)
    cut = float(law.tables.zones.adjacent_ground.groundside_cutback_m) + snap_margin_m(law)
    # (read beside the road: past its ends the band keeps its full reach)
    east = after.intersection(box(-100.0, -250.0, 100.0, 250.0)).bounds[2]
    assert east == pytest.approx(x - 12.25 - cut, abs=0.01)


def test_a_road_inside_the_band_grades_with_it(law):
    # 13ar / 29r: a road running INSIDE the band is the zone's (it is
    # ribboned there); the band is not trimmed for it
    reach = zone_edge_offset_m(law, "junction", None, "C")
    road = _road(0.5 * reach, lanes="7")
    assert _bands(law, (road,)).symmetric_difference(_bands(law)).area \
        == pytest.approx(0.0, abs=1e-6)


def test_the_carriageway_reads_the_map(law):
    lw = float(law.tables.emit.road_profile.lane_width_m)
    ways = (_road(0.0, lanes="7"), _road(0.0), _road(0.0, width="30"),
            _road(0.0, highway="footway"), _road(0.0, tunnel="yes"))
    halves = [h for _l, h in road_carriageways(ways, law)]
    # 7 lanes x 3.5 m; no tag: never narrower than the ribbon's own lane
    # width; a stated width wins; a footway and a bore are not the road
    assert halves == pytest.approx([12.25, max(lw, 3.5), 15.0])
