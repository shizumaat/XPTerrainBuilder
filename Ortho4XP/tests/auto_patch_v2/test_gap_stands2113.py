"""#2113 (KBNA owner sim read 2026-11-16T16:56:54Z): the ground between a
pack's concourses drawn only as photo drapes (gap sheets), the gates'
stands on it, is APRON — and a service-road corridor between it and the
apron reads it as airside contact in the §27 pass (``classify/gap_stands``).

Synthetic: an apron (0..100 x 0..40), a 300 m road corridor along its south
edge (y -8..0, perimeter 616 m), and a gap sheet south of the road
(y -48..-8) holding one 1300 startup: 100 m of apron contact is 16 %,
under §37 (2)'s 20 %; with the stands behind it 200 m is 32 %.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch_v2.classify import load_rules  # noqa: E402
from auto_patch_v2.classify.airside_edge import airside_edge_flip  # noqa: E402
from auto_patch_v2.classify.gap_stands import holds_stand, stand_ground  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402


class _Sheet:
    def __init__(self, ring):
        self.outer, self.holes = tuple(ring), ()


class _Start:
    def __init__(self, xy):
        self.xy = xy


class _Ap:
    def __init__(self, sheets, starts):
        self.gap_sheets, self.startups = tuple(sheets), tuple(starts)


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _scene():
    apron = Polygon(_rect(0.0, 0.0, 100.0, 40.0))
    road = Polygon(_rect(-100.0, -8.0, 200.0, 0.0))       # 300 m corridor
    ap = _Ap([_Sheet(_rect(0.0, -48.0, 100.0, -8.0))], [_Start((50.0, -30.0))])
    return apron, road, ap


def _tree(ap):
    from shapely.geometry import Point
    return STRtree([Point(s.xy) for s in ap.startups])


def test_stand_ground_is_the_sheet_left_by_the_faces_that_holds_a_stand():
    apron, road, ap = _scene()
    got = stand_ground(ap, [apron, road], _tree(ap), 50.0)
    assert len(got) == 1 and abs(got[0].area - 4000.0) < 1e-6
    assert holds_stand(got[0], _tree(ap))
    # no startup on the sheet: no stand ground, and no startup tree: none
    empty = _Ap(ap.gap_sheets, [_Start((50.0, 20.0))])
    assert stand_ground(empty, [apron, road], _tree(empty), 50.0) == []
    assert stand_ground(ap, [apron, road], None, 50.0) == []


def test_a_road_between_apron_and_stands_flips_only_with_the_stands(law):
    rules = load_rules()
    apron, road, ap = _scene()

    def run(stands):
        final = [["apron", "a", apron, None, {}, "apron"],
                 ["service_road", "r", road, None, {}, "service_road"]]
        airside_edge_flip(final, [], law, rules, stands=stands)
        return final[1]
    # the apron alone is 100 m of 616 m: under §37 (2)'s share, a road
    assert run(())[0] == "service_road"
    # with the stand ground behind it, 200 m of 616 m: the road is apron
    got = run(stand_ground(ap, [apron, road], _tree(ap), 50.0))
    assert got[0] == "apron" and got[4]["airside_edge_was"] == "service_road"
