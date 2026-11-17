"""#2128 twins (KIAH sim read 2026-11-16, 1 m lidar): a ramp climbs to its
road's ground read on its axis, never to the ground under its ring's edge
vertices; a road crossing a wall-less deck on its end bank is not bored by
it (``planar/structure_geometry.ramp_targets``, ``planar/deck_bores``)."""
from __future__ import annotations

import types

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import deck_bores as DBO
from auto_patch_v2.planar import deck_bridge as DB
from auto_patch_v2.planar.structure_geometry import ramp_targets
from auto_patch_v2.planar.structure_mouth import mouth_stops
from auto_patch_v2.planar.structure_service import airside_cut_roles
from auto_patch_v2.planar.structure_underpass import UNDERPASS_TAG
from auto_patch_v2.planar.survey_cut import deck_cutting
from shapely.geometry import LineString, Polygon
from shapely.geometry import box as _sbox

LAW = Law.for_airport("")


def _ramp():
    """One tunnel along +x from a 20.0 floor at x = 0, its ramp face a ring
    whose vertices stand on the corridor's edges (y = +-10)."""
    tn = types.SimpleNamespace(
        id="t", axis=((0.0, 0.0), (100.0, 0.0)), design_grade=0.1, profile=(),
        climb_from_s=0.0, source="osm", wall_length_m=0.0, deck_bridge="",
        mouth_z=20.0, deck_floor_min_m=0.0, top_s=100.0)
    vxy = [(20.0, -10.0), (20.0, 10.0), (40.0, 10.0), (40.0, -10.0)]
    edges = [types.SimpleNamespace(a=i, b=(i + 1) % 4) for i in range(4)]
    faces = {0: types.SimpleNamespace(role="tunnel_ramp", ring=[0, 1, 2, 3])}
    return tn, vxy, edges, faces


def test_the_ramp_climbs_to_its_roads_ground_on_the_axis_not_the_banks():
    """KIAH obj24615: the edge vertices stood on a surveyed cutting's banks
    (25 m) over a road whose ground was 20.5; read there, the station took
    floor + grade x run (a 1.5 m hump against the road beyond)."""
    tn, vxy, edges, faces = _ramp()
    banks = [25.0] * 4
    edge_read = ramp_targets([tn], LAW, faces, edges, vxy, banks)
    assert edge_read[0] == 22.0 and edge_read[2] == 24.0     # floor + 0.1 x s
    axis_read = ramp_targets([tn], LAW, faces, edges, vxy, banks,
                             axis_dem=lambda x, y: 20.5 if abs(y) < 1e-9 else 99.0)
    assert set(axis_read.values()) == {20.5}


def test_on_level_ground_the_axis_and_the_edge_read_the_same():
    tn, vxy, edges, faces = _ramp()
    flat = [21.0] * 4
    assert ramp_targets([tn], LAW, faces, edges, vxy, flat) == ramp_targets(
        [tn], LAW, faces, edges, vxy, flat, axis_dem=lambda x, y: 21.0)


def _deck():
    """A 200 m wall-less deck (end lines x = -100 / +100), 5 m deep, 30 m
    across the road under it."""
    ring = tuple(_sbox(-100.0, -15.0, 100.0, 15.0).exterior.coords[:-1])
    a = tuple((-100.0, y) for y in (-10.0, 0.0, 10.0))
    b = tuple((100.0, y) for y in (-10.0, 0.0, 10.0))
    return DB.DeckBridge("dsf:obj1", "objects/deck.obj", ("dsf:obj1",), ring, a, b,
                         1.5, 1.5, -3.5, 30.0)


def _road(wid, x):
    return OsmWay(wid, "airport_small_roads", ((x, -200.0), (x, 200.0)), False,
                  {"highway": "service"})


def test_a_road_on_the_end_bank_is_not_bored_one_on_the_floor_is():
    """KIAH obj24614 (#2128 item 3): the airside service road 6.9 m inside an
    end line -- its carriageway clear of the line, but on the bank the
    ground climbs from the floor to the deck on -- crosses at grade; a road
    past the bank's run passes under."""
    db = _deck()
    bank = db.depth_m / float(LAW.tables.structures.channel.bank_slope)
    on_bank, on_floor = _road(-1, -91.0), _road(-2, -100.0 + bank + 3.0)
    ways, _p, notes = DBO.deck_bores((db,), [on_bank, on_floor], [], LAW, UNDERPASS_TAG)
    assert [w.id for w in ways] == [-2]
    assert any("not bored (#2128)" in n and "-1" in n for n in notes)


class _Dem:
    provenance = {"synthetic": "survey"}

    def __init__(self, fn):
        self._fn = fn

    def z(self, x: float, y: float) -> float:
        return self._fn(x, y)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _Airport:
    def __init__(self, fn):
        self.dem = _Dem(fn)


#: a 1 m survey of a deck (y within 12.5 of 0) at 29 over a road cutting
#: (|x| <= 20) at 21.5, the ground at 28 beyond
_DECKED = _Airport(lambda x, y: 29.0 if abs(y) <= 12.5 else 21.5 if abs(x) <= 20.0 else 28.0)


def test_a_deck_trench_reads_its_cutting_where_it_leaves_the_deck():
    """KIAH obj24551 (#2128 item 4): the survey over the deck reads the deck;
    past its edge, the road in its cutting -- the cutting's floor; none on a
    coarse DEM, none where the axis never leaves the deck."""
    under = Polygon([(-50, -12.5), (50, -12.5), (50, 12.5), (-50, 12.5)])
    axis = LineString([(0.0, 0.0), (0.0, 120.0)])
    cut = deck_cutting(_DECKED, LAW, True, 29.0, axis, under, 7.0)
    assert cut is not None and cut.road == 21.5 and cut.cover == 29.0
    assert deck_cutting(_DECKED, LAW, False, 29.0, axis, under, 7.0) is None
    assert deck_cutting(_DECKED, LAW, True, 29.0, LineString([(0, 0), (0, 10)]), under,
                        7.0) is None


def test_airside_pavement_on_a_deck_trenchs_cutting_floor_is_no_stop():
    """An apron piece the survey reads down in the cutting (the pack's apron
    polygon drawn over the road, KIAH dsf:pol153) stops the run-out without
    the cutting and not with it; an apron up on the ground still stops."""

    def cell(i, ref, ring):
        return Cell(i, "apron", ref, ring, (), None, "E", "airside", "corridor", {})
    cells = [cell(0, "sliver", ((-15, 20), (15, 20), (15, 35), (-15, 35))),
             cell(1, "high", ((25, 20), (60, 20), (60, 35), (25, 35)))]
    polys = [Polygon(c.ring) for c in cells]
    tn = LAW.tables.structures.tunnel
    rim_off = tn.wall_gap_m + tn.wall_band_width_m
    grid = LAW.tables.emit.identity.min_distinct_spacing_m
    axis = LineString([(0.0, 12.5), (0.0, 200.0)])
    under = Polygon([(-50, -12.5), (50, -12.5), (50, 12.5), (-50, 12.5)])
    cut = deck_cutting(_DECKED, LAW, True, 29.0, LineString([(0.0, 0.0), (0.0, 200.0)]),
                       under, 7.0)

    def stops(on_floor):
        return sorted(r for _p, r in mouth_stops(
            cells, polys, LAW, airside_cut_roles(LAW), axis, (0.0, 12.5), 3.5, rim_off, (),
            grid, (), None, on_floor))
    assert stops(None) == ["high", "sliver"]
    assert stops(lambda p, m: cut.floor_face(p, m, 40.0)) == ["high"]
