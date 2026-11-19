"""Twin for owner RULINGS 2026-11-19l (``classify/pad_ground``): a building
pad stands only where the building touches the ground.  A sky bridge over a
road adds no pad and the road keeps its own ground under it; a building on
its feet keeps its pad; the facade reader states how far a facade's walls
stop over the ground.  Synthetic geometry, law values read from the tables."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport.facade import ROOFED, parse_facade
from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.pad_ground import (GROUND_TRIMMED, PASSAGE_NOTES,
                                               trim_to_ground)
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Building, FacadeRead, OsmWay
from auto_patch_v2.model.rebake import Part
from shapely.geometry import LineString, Point, box


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def _frame():
    # rings are ``(lat, lon)``; ``to_xy(lon, lat)`` -> ``(x, y)`` = (lon, lat)
    return types.SimpleNamespace(entry=lambda: (lambda lon, lat: (lon, lat)))


def _facade(i, g, base):
    x0, y0, x1, y1 = g.bounds
    ring = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return Building(f"dsf:fac{i}", ring, (), "dsf:fac:terminal", None, None, None,
                    FacadeRead("lib/t.fac", ROOFED, (), 0, base))


def _airport(buildings=(), ways=(), parts=()):
    members = [types.SimpleNamespace(parts=tuple(parts))] if parts else []
    part = types.SimpleNamespace(units=[types.SimpleNamespace(members=members)])
    return types.SimpleNamespace(frame=_frame(), buildings=tuple(buildings),
                                 osm_ways=tuple(ways), partition=part)


def _road(y):
    return OsmWay(-1, "big_roads", ((-200.0, y), (200.0, y)), False,
                  {"highway": "primary", "lanes": "2"})


def _part(pid, g, base_y, feet):
    x0, y0, x1, y1 = g.bounds
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))
    return Part(pid, pid, 0.5 * (y0 + y1), 0.5 * (x0 + x1), base_y, g.area,
                (y0, x0, y1, x1), ((y0, x0, base_y),) if feet else (), rings=(ring,),
                height_m=5.0)


def _terminal(g, layer):
    x0, y0, x1, y1 = g.bounds
    pts = ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))
    return OsmWay(-215, "airports", pts, True,
                  {"aeroway": "terminal", "building": "yes", "layer": str(layer)})


@pytest.mark.parametrize("layer", [4, 0])
def test_a_sky_bridge_over_a_road_adds_no_pad_and_the_road_keeps_its_ground(law, rules, layer):
    """Two terminal blocks on their feet, a levels facade 3.83 m up between
    them over a road, and the OSM terminal outline taking in all three: the
    pad keeps the blocks and loses the bridge.  The road leaves the pad
    under the bridge; where the outline is mapped a layer over the road it
    leaves it all the way through (KPHX Terminal 3, ``layer=4``), where it
    is not, the road off the bridge stays under the pad."""
    north, south = box(0, 40, 100, 100), box(0, -100, 100, -40)
    bridge = box(40, -40, 60, 40)
    outline = box(0, -100, 100, 100)
    ap = _airport([_facade(1, north, -1.0), _facade(2, south, -1.0),
                   _facade(3, bridge, 3.83)], [_road(0.0), _terminal(outline, layer)])
    out = trim_to_ground([outline], ap, law, rules)
    pad = out[0]
    assert pad.contains(Point(50, 70)) and pad.contains(Point(50, -70))
    assert not pad.contains(Point(50, 30))          # under the bridge, off the road
    assert not pad.intersects(LineString([(41, 0), (59, 0)]))      # under the bridge
    assert pad.intersects(LineString([(-200, 0), (200, 0)])) == (layer == 0)
    assert GROUND_TRIMMED["parts"] == 1
    assert any("clearance 3.83 m LOW" in n for n in PASSAGE_NOTES)


def test_a_building_on_its_feet_keeps_its_pad(law, rules):
    """A footed hall, a road mapped through it and an upper floor over it:
    nothing leaves the pad."""
    hall = box(0, 0, 80, 60)
    ap = _airport(ways=[_road(30.0)],
                  parts=[_part(0, hall, 0.0, True), _part(1, box(10, 10, 70, 50), 8.0, False)])
    out = trim_to_ground([hall], ap, law, rules)
    assert len(out) == 1 and out[0].equals(hall)
    assert not GROUND_TRIMMED.get("parts")


def test_a_road_under_a_canopy_keeps_its_ground_and_a_garage_deck_keeps_its_pad(law, rules):
    """A footed core with a canopy 6 m up past its wall over a road: the
    road leaves the pad under the canopy (its clearance reported), the rest
    of the canopy's ground stays (an OBJ roof is not told from a bridge by
    the plan's rings).  A garage deck 2 m over its columns with a road mapped
    under it is under a storey: it stays ground and keeps its pad."""
    core, canopy = box(0, 0, 40, 40), box(40, 0, 60, 40)
    deck = box(100, -20, 160, 40)
    road = OsmWay(-2, "big_roads", ((50.0, -100.0), (50.0, 100.0)), False,
                  {"highway": "service"})
    ap = _airport(ways=[road, _road(10.0)],
                  parts=[_part(0, core, 0.0, True), _part(1, canopy, 6.0, False),
                         _part(2, box(100, -20, 101, -19), 0.0, True),
                         _part(3, deck, 2.0, False)])
    out = trim_to_ground([box(0, 0, 60, 40), deck], ap, law, rules)
    assert not out[0].intersects(LineString([(50, -100), (50, 100)]))
    assert out[0].contains(Point(20, 20)) and out[0].contains(Point(58, 38))
    assert abs(out[1].area - deck.area) < 1e-6
    assert any("-2 (service)" in n and "clearance 6.00 m" in n and "LOW" not in n
               for n in PASSAGE_NOTES)


def test_the_facade_reader_reads_where_its_walls_stop(tmp_path):
    def fac(y):
        return ("A\n1000\nFACADE\nGRADED\nSHADER_ROOF\nFLOOR one\nROOF_HEIGHT 9.4\n"
                "SEGMENT 0\nMESH 0 1000 1 4 6\n"
                f"VERTEX 0 {y} 0 0 1 0 0 0\nVERTEX 0 9.4 0 0 1 0 0 0\n"
                f"VERTEX 0 {y} -1 0 1 0 0 0\nVERTEX 0 9.4 -1 0 1 0 0 0\n"
                "IDX 0 1 2 1 3 2\nWALL 0 1000 0 0 w\nSPELLING 0\n")
    p = tmp_path / "lifted.fac"
    p.write_text(fac(3.83), encoding="utf-8", newline="")
    assert parse_facade(str(p)).floors[0].base_y == pytest.approx(3.83)
    p.write_text(fac(-1.0), encoding="utf-8", newline="")
    assert parse_facade(str(p)).floors[0].base_y == pytest.approx(-1.0)


def test_a_road_through_a_building_is_levelled_at_its_own_grade():
    """The road profile levels a ``tunnel=building_passage`` way like any
    road (it runs under the building at grade); a bore is still not."""
    from auto_patch_v2.airport.road_profile import _osm_levelled
    pts = ((0.0, 0.0), (50.0, 0.0))
    passage = OsmWay(-3, "big_roads", pts, False,
                     {"highway": "primary", "tunnel": "building_passage"})
    bore = OsmWay(-4, "big_roads", pts, False, {"highway": "primary", "tunnel": "yes"})
    assert _osm_levelled(passage) and not _osm_levelled(bore)
