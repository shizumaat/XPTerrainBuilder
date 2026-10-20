"""Twins for issue #1028 Q31 — the pack's OPEN descending plate a mapped
road runs along, under a mapped tunnel or bridge, is that road's ramp
object (``airport/sunken_roads``): the witness, and one ramp per grade end
cut where the roof begins.  Synthetic plates; law values from the tables."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport import sunken_roads as SR
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from shapely.geometry import LineString, box


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _rd(law, ways):
    return types.SimpleNamespace(law=law, airport=types.SimpleNamespace(osm_ways=ways),
                                 bores=None)


def test_the_witness_is_a_road_along_the_plate_under_a_crossing_way(law):
    plate = box(0, -10, 200, 10)
    road = OsmWay(-1, "big_roads", ((-50.0, 0.0), (250.0, 0.0)), False, {"highway": "primary"})
    deck = OsmWay(-2, "aeroway", ((100.0, -60.0), (100.0, 60.0)), False,
                  {"aeroway": "taxiway", "bridge": "yes"})
    across = OsmWay(-3, "big_roads", ((100.0, -60.0), (100.0, 60.0)), False,
                    {"highway": "primary"})
    assert SR._bore_enters(_rd(law, [road, deck]), plate, plate)
    assert not SR._bore_enters(_rd(law, [road]), plate, plate)          # nothing over it
    assert not SR._bore_enters(_rd(law, [across, deck]), plate, plate)  # no road ALONG it


def test_a_plate_at_grade_at_both_ends_is_two_ramps_cut_at_the_roof(law):
    """A V profile: grade at both ends, 6 m deep in the middle under a roof
    from s = 80 to 120.  Each end's ramp runs from its grade end down to
    where the roof begins — never under it."""
    sr = law.tables.structures.cutout.sunken_road
    axis = LineString([(0.0, 0.0), (200.0, 0.0)])
    rows = [(float(s), 100.0 - 6.0 * (1.0 - abs(s - 100.0) / 100.0), 5.0, 5.0, 100.0)
            for s in range(0, 201, 10)]
    roof = box(80, -20, 120, 20)
    a = SR._one_ramp(rows, rows, axis, sr, roof)
    b = SR._one_ramp(list(reversed(rows)), rows, axis, sr, roof)
    assert not isinstance(a, str) and not isinstance(b, str)
    xa = [p[0] for p in a[2]]
    xb = [p[0] for p in b[2]]
    assert xa[0] == pytest.approx(80.0) and max(xa) <= 80.0 + 1e-6
    assert xb[0] == pytest.approx(120.0) and min(xb) >= 120.0 - 1e-6
    assert "roof" in a[3]
