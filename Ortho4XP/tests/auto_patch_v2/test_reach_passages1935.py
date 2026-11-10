"""THE UNIT JUDGED IS WHAT THE REACHABLE SWEEP LEAVES (#1935; owner RULINGS
2026-11-10a (5), 2026-10-19ag; ``planar/reach_after_pads.beyond_passages``).

The EFHK shape, in the abstract: a taxiway, one apron page with the stands,
and a long terminal pier cut out of the page.  The page runs on past the
pier's land side as a lot, joined to the stands only by a 1.5 m strip round
the pier's end -- one polygon, so the per-piece read keeps it all apron.
Read against the sweep of the reachable room, the lot and the strip that
leads to it are groundside and the stands stay apron.
"""
from __future__ import annotations

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_side
from auto_patch_v2.planar.overlay import Region
from auto_patch_v2.planar.reach_after_pads import BEYOND, unreachable_after_pads
from shapely.geometry import Point, box

TAXI = box(0.0, 0.0, 400.0, 25.0)
#: the pier; the page passes its east end as a 1.5 m strip (x 398.5..400)
PIER = box(0.0, 150.0, 398.5, 165.0)
PAGE = box(0.0, 25.0, 400.0, 240.0).difference(PIER)
STAND = (200.0, 100.0)
LOT = (200.0, 200.0)
STRIP = (399.25, 158.0)


class _Stand:
    def __init__(self, xy):
        self.xy = xy


class _Field:
    def __init__(self, startups=()):
        self.startups = tuple(_Stand(xy) for xy in startups)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _regions(law, page=PAGE):
    return [Region("primary_parallel", "twy", TAXI, 4, "E", role_side(law, "primary_parallel"),
                   "cell"),
            Region("apron", "page", page, None, None, role_side(law, "apron"), "cell")]


def _pads(law, pier=PIER):
    return [Region("building", "pier", pier, None, None, role_side(law, "building"), "pad")]


def _at(out, xy):
    return [r for r in out if r.polygon is not None and r.polygon.buffer(0.01).contains(Point(xy))]


def test_the_land_side_lot_and_its_strip_are_groundside(law):
    out, counts = unreachable_after_pads(_regions(law), _pads(law), law, _Field([STAND]))
    assert counts["beyond_passages"] == 1
    lot = _at(out, LOT)
    assert len(lot) == 1 and BEYOND in str(lot[0].ref)
    assert role_side(law, lot[0].role) == "groundside"
    # the strip leading to it is no apron either: inside the set-back it is
    # bare ground, the pad's edge the step (RULINGS 2026-11-10a (5))
    assert not [r for r in _at(out, STRIP) if r.role == "apron"]
    knife = law.tables.structures.building_pad.groundside_cutback_m
    assert lot[0].polygon.distance(PIER) >= knife
    # the stands keep the page, apron
    stand = _at(out, STAND)
    assert [r.role for r in stand] == ["apron"] and str(stand[0].ref) == "page"


def test_a_startup_in_the_lot_keeps_it_apron(law):
    out, counts = unreachable_after_pads(_regions(law), _pads(law), law, _Field([STAND, LOT]))
    assert counts.get("beyond_passages", 0) == 0
    assert [r.role for r in _at(out, LOT)] == ["apron"]


def test_a_wide_mouth_divides_nothing(law):
    # the pier stops 40 m short of the page edge: aircraft taxi round it
    pier = box(0.0, 150.0, 360.0, 165.0)
    page = box(0.0, 25.0, 400.0, 240.0).difference(pier)
    out, counts = unreachable_after_pads(_regions(law, page), _pads(law, pier), law,
                                         _Field([STAND]))
    assert counts.get("beyond_passages", 0) == 0
    assert [r.role for r in _at(out, LOT)] == ["apron"]
