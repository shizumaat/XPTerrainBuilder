"""#2128 round 2 twins (owner RULINGS 2026-11-17a (1)-(2); ``planar/
survey_deck_cut``, ``planar/deck_bores`` R5): on a credible survey the cut
at a wall-less hard deck whose floor is the ladder's is the survey's -- the
floor per lane is the lower edge road, the region C runs rim to rim out to
where the road comes up within ``object_min_depth_m`` of the deck's top,
and the pavement over C is cut away; a coarse DEM, a walled deck, a level-B
airport, a floor the object states, or a cut shallower than the clearance
keep today's path.  A road the survey reads at grade at a side edge is not
bored (R5)."""
from __future__ import annotations

import dataclasses as _dc
import types

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import deck_bores as DBO
from auto_patch_v2.planar import deck_bridge as DB
from auto_patch_v2.planar import survey_deck_cut as SDC
from auto_patch_v2.planar.lidar_road import KEPT
from auto_patch_v2.planar.structure_underpass import UNDERPASS_TAG
from shapely.geometry import Point, Polygon
from shapely.geometry import box as _sbox

LAW = Law.for_airport("")
TOP = 30.0


class _Survey:
    """Ground at ``TOP``; a road along x = 0 in a cut ``depth`` deep and
    40 m wide (|x| < 20, 1:1 banks) out to |y| = 150, climbing out by
    |y| = 230.  ``lidar`` False is a coarse DEM."""
    provenance = {"synthetic": "deck cut"}

    def __init__(self, depth: float, lidar: bool = True):
        self.depth, self.lidar = depth, lidar

    def z(self, x: float, y: float) -> float:
        ay = abs(y)
        d = self.depth if ay <= 150.0 else max(0.0, self.depth * (230.0 - ay) / 80.0)
        floor = TOP - d
        if abs(x) <= 20.0:
            return floor
        return min(TOP, floor + (abs(x) - 20.0))

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)

    def source_pixel_m(self):
        return (1.0, "inset") if self.lidar else (30.0, "inset")


def _road():
    return OsmWay(-7, "big_roads", ((0.0, -400.0), (0.0, 400.0)), False,
                  {"highway": "primary", "lanes": "2"})


def _airport(depth=6.0, lidar=True):
    return types.SimpleNamespace(dem=_Survey(depth, lidar), flat_site=None,
                                 osm_ways=(_road(),), taxi_nodes={}, taxi_edges=())


def _deck(floor_min=5.0, oid="dsf:obj1"):
    """A taxiway deck along x (-60..60), 30 m along the road (y -15..15);
    its end lines at x = -60 / +60, its top ``TOP``; the ladder's floor."""
    ring = tuple(_sbox(-60.0, -15.0, 60.0, 15.0).exterior.coords[:-1])
    a = tuple((-60.0, y) for y in (-10.0, 0.0, 10.0))
    b = tuple((60.0, y) for y in (-10.0, 0.0, 10.0))
    return DB.DeckBridge(oid, "objects/deck.obj", (oid,), ring, a, b, 0.0, 0.0, -7.5, TOP,
                         floor_min_m=floor_min)


def test_the_surveyed_cut_at_a_hard_deck_is_kept_rim_to_rim():
    recs, notes = SDC.survey_deck_cuts((_deck(),), _airport(), LAW)
    assert len(recs) == 1 and "kept" in notes[0]
    r = recs[0]
    assert r.floor == pytest.approx(TOP - 6.0, abs=0.01)            # F: the lower edge road
    c = r.region
    assert c is not None
    assert not c.intersects(DB.deck_polygon(_deck()).buffer(-0.01))  # never the deck ring
    assert c.contains(Point(15.0, 60.0)) and c.contains(Point(-15.0, -100.0))  # rim to rim
    assert not c.contains(Point(40.0, 60.0))                        # past the rim
    assert not c.contains(Point(0.0, 220.0))                        # the road came up
    # the mouth under it is KEPT at F
    m = types.SimpleNamespace(xy=(0.0, 14.0), bore=types.SimpleNamespace(ways=[_road()]))
    sm = SDC.deck_survey_mouth(recs, _deck(), [m], LAW)
    assert sm.verdict == KEPT and sm.floor == pytest.approx(r.floor) and sm.cover == TOP


@pytest.mark.parametrize("case", ["coarse", "walled", "level_b", "stated", "shallow"])
def test_today_s_path_stands_without_a_kept_survey_cut(case, monkeypatch):
    deck, ap, level_b = _deck(), _airport(), None
    if case == "coarse":
        ap = _airport(lidar=False)
    elif case == "walled":
        monkeypatch.setattr(SDC, "is_walled", lambda db, inset: True)
    elif case == "level_b":
        level_b = 7.0
    elif case == "stated":
        deck = _deck(floor_min=0.0)
    elif case == "shallow":
        ap = _airport(depth=4.0)                      # under clearance_m 5, over 3 m
    recs, notes = SDC.survey_deck_cuts((deck,), ap, LAW, (), level_b)
    assert recs == ()
    if case == "shallow":
        assert "keeps the ladder" in notes[0]


def test_r5_a_road_the_survey_reads_at_grade_is_not_bored():
    ways, _p, notes = DBO.deck_bores((_deck(),), [_road()], [], LAW, UNDERPASS_TAG,
                                     _airport(depth=2.0))
    assert ways == [] and "#2128 R5" in notes[0]
    ways, _p, _n = DBO.deck_bores((_deck(),), [_road()], [], LAW, UNDERPASS_TAG,
                                  _airport(depth=6.0))
    assert [w.id for w in ways] == [-7]


def _cell(i, role, ref, x0, y0, x1, y1, side="airside"):
    ring = tuple(_sbox(x0, y0, x1, y1).exterior.coords[:-1])
    return Cell(i, role, ref, ring, (), None, "C", side, role, {})


@_dc.dataclass(frozen=True)
class _Cl:
    cells: tuple


def test_r2_pavement_over_the_cut_is_cut_away_a_taxi_route_piece_is_kept():
    ap = _airport()
    cells = (_cell(0, "apron", "plaza", -10.0, 40.0, 10.0, 80.0),
             _cell(1, "apron", "route", -10.0, -80.0, 10.0, -40.0),
             _cell(2, "service_road", "rib", -3.0, 90.0, 3.0, 120.0, "groundside"))
    ap.taxi_nodes = {1: types.SimpleNamespace(xy=(-30.0, -60.0)),
                     2: types.SimpleNamespace(xy=(30.0, -60.0))}
    ap.taxi_edges = (types.SimpleNamespace(a=1, b=2, is_runway=False),)
    recs, _n = SDC.survey_deck_cuts((_deck(),), ap, LAW, cells)
    assert recs and recs[0].region.contains(Point(0.0, 60.0))
    assert not recs[0].region.contains(Point(0.0, -60.0))     # a taxi route's piece
    out, notes = SDC.cut_pavement(_Cl(cells), recs, ap, LAW)
    left = {c.ref: Polygon(c.ring).area for c in out.cells}
    assert left.get("route") == pytest.approx(800.0)          # kept whole
    assert left.get("rib") == pytest.approx(180.0)            # a road ribbon stays
    assert left.get("plaza", 0.0) < 1.0                       # cut away
    assert any("plaza" in n and "#2128 R2" in n for n in notes)
