"""THE COVERS STAND IN THE AIRCRAFT'S WAY (#1717 S1; owner RULINGS 2026-11-03b
Q340 a, 2026-10-19ag; spec two-level-regions §15, ``planar/reach_under_covers``).

The LFPG T2 shape, in the abstract: a taxiway, one apron page round two
terminal blocks, and the corridor between the blocks open to the apron at
both ends.  A road viaduct runs along the corridor and road bridges cross
its two mouths.  Read with the pads alone, the corridor is reached through
its mouths and stays apron; read with the covers standing, no aircraft gets
in and the corridor is groundside -- one part of the page, the rest of the
page apron.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_side
from auto_patch_v2.model.airport import Boundary, OsmWay
from auto_patch_v2.planar.overlay import Region
from auto_patch_v2.planar.reach_after_pads import BEYOND
from auto_patch_v2.planar.reach_under_covers import bridge_covers, covered_beyond
from shapely.geometry import Point, box

TAXI = box(0.0, 0.0, 400.0, 25.0)
#: the two terminal blocks (cut out of the page); the corridor between them
#: is x 50..350, y 125..175, open at both ends
BLOCKS = (box(50.0, 90.0, 350.0, 125.0), box(50.0, 175.0, 350.0, 210.0))
PAGE = box(0.0, 25.0, 400.0, 260.0).difference(BLOCKS[0]).difference(BLOCKS[1])
BOX = ((-2000.0, -2000.0), (2000.0, -2000.0), (2000.0, 2000.0), (-2000.0, 2000.0))


class _Field:
    def __init__(self, ways, startups=()):
        self.osm_ways = tuple(ways)
        self.boundaries = (Boundary("b", BOX, ()),)
        self.startups = tuple(startups)


class _Stand:
    def __init__(self, xy):
        self.xy = xy


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _regions(law):
    return [Region("primary_parallel", "twy", TAXI, 4, "E", role_side(law, "primary_parallel"),
                   "cell"),
            Region("apron", "page", PAGE, None, None, role_side(law, "apron"), "cell")]


def _ways(layer: int = 1, axis: bool = True):
    def bridge(i, pts, lyr, width):
        return OsmWay(i, "big_roads", pts, False,
                      {"highway": "primary", "bridge": "yes", "layer": str(lyr),
                       "width": str(width)})
    ways = [bridge(1, ((50.0, 115.0), (50.0, 185.0)), layer, 12.0),
            bridge(2, ((350.0, 115.0), (350.0, 185.0)), layer, 12.0)]
    if axis:
        ways.append(bridge(3, ((50.0, 150.0), (350.0, 150.0)), 2, 16.0))
    return ways


def _beyond(out):
    return [r for r in out if BEYOND in str(r.ref)]


def test_the_corridor_behind_covered_mouths_is_groundside(law):
    out, counts = covered_beyond(_regions(law), law, _Field(_ways()))
    lost = _beyond(out)
    assert counts["covered_beyond"] == 1 and len(lost) == 1
    q = lost[0]
    assert role_side(law, q.role) == "groundside"
    assert q.polygon.contains(Point(200.0, 140.0))
    # the rest of the page stays apron, one region per part
    kept = [r for r in out if r.ref == "page"]
    assert kept and all(r.role == "apron" and r.polygon.geom_type == "Polygon" for r in kept)
    assert any(r.polygon.contains(Point(200.0, 50.0)) for r in kept)


def test_no_cover_divides_nothing(law):
    out, counts = covered_beyond(_regions(law), law, _Field([]))
    assert not _beyond(out) and not counts
    assert bridge_covers(_Field([]), law) is None


def test_a_bridge_under_the_cover_layer_is_no_cover(law):
    # layer 0 mouths: aircraft enter by them, the axis viaduct alone seals nothing
    out, _counts = covered_beyond(_regions(law), law, _Field(_ways(layer=0)))
    assert not _beyond(out)


def test_a_part_barely_under_covers_keeps_its_role(law):
    # the mouths alone close the corridor, but under a quarter of it is covered
    out, counts = covered_beyond(_regions(law), law, _Field(_ways(axis=False)))
    assert not _beyond(out) and counts == {"covered_beyond": 0}


def test_a_stand_in_the_corridor_keeps_it_apron(law):
    out, _counts = covered_beyond(_regions(law), law, _Field(_ways(), [_Stand((200.0, 140.0))]))
    assert not _beyond(out)
