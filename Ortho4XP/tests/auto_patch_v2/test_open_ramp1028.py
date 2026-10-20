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


def test_the_ground_already_carrying_the_cutting_sets_no_mouth(law):
    """Owner 2026-10-20 answer 41: a ramp whose floor lies within
    ``open_dem_carries_m`` of the DEM at every station is the DEM's own
    cutting; one plate standing deeper somewhere sets the mouth."""
    sr = law.tables.structures.cutout.sunken_road
    tol = sr.open_dem_carries_m
    shallow = [SR.RoadStation(float(s), 100.0 - 0.9 * tol, 5.0, 5.0, 100.0) for s in (0, 10, 20)]
    deep = shallow[:2] + [SR.RoadStation(20.0, 100.0 - 2.0 * tol - 0.1, 5.0, 5.0, 100.0)]
    assert "already carries the cutting" in SR._dem_carries(shallow, sr)
    assert SR._dem_carries(deep, sr) is None


def _group(tid, foot, open_ramp=True):
    c = types.SimpleNamespace(footprint=foot, open_ramp=open_ramp, objects=(tid,), id=tid)
    return types.SimpleNamespace(tid=tid, corridor=c)


def test_an_open_ramp_meeting_a_strip_is_refused(law):
    """Owner answer 41: never inside a taxiway strip — the strip is the
    cell grown by its class's strip half width; a ramp clear of it stands,
    and a non-open group is never this gate's."""
    from auto_patch_v2.planar import open_ramps as OR
    from auto_patch_v2.planar.structure_underpass import strip_half_width_m

    taxi = types.SimpleNamespace(role="primary_parallel", ref="P", code_number=4, code_letter="E",
                                 kind="pavement", ring=())
    pav = box(0, 0, 400, 23)
    strip = OR.strip_region([pav], [taxi], law, {})
    hw = strip_half_width_m(law, taxi)
    assert hw > 0.0 and strip.contains(box(10, 23, 20, 23 + 0.9 * hw))
    stats = types.SimpleNamespace(refused=[])
    near = _group("near", box(50, 23 + 0.5 * hw, 90, 23 + hw + 20))
    clear = _group("clear", box(50, 23 + hw + 5, 90, 23 + hw + 40))
    roofed = _group("roofed", box(50, 30, 90, 60), open_ramp=False)
    kept = OR.open_ramps_off_strip([near, clear, roofed], strip, stats.refused)
    assert [g.tid for g in kept] == ["clear", "roofed"]
    assert "strip" in stats.refused[0]
