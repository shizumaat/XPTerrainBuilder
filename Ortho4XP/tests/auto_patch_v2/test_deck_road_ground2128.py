"""#2128 twins (KIAH sim read 2026-11-16, 1 m lidar): a road crossing a
wall-less deck on its end bank is not bored by it (``planar/deck_bores``);
a mapped bore that passes under a pack hard deck near its end has that
deck as the end's portal witness (``planar/end_witness``); a hard-deck
trench on a credible survey reads its cutting where it leaves the deck, and
pavement the survey reads on that cutting's floor is no stop
(``planar/survey_cut.deck_cutting``, ``planar/structure_mouth``)."""
from __future__ import annotations

import types

from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import deck_bores as DBO
from auto_patch_v2.planar import deck_bridge as DB
from auto_patch_v2.planar.structure_underpass import UNDERPASS_TAG
from shapely.geometry import box as _sbox

LAW = Law.for_airport("")


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


def test_a_hard_deck_over_the_bore_near_its_end_witnesses_that_end():
    """KIAH obj24551 (#2128 item 4): the service bore -3337 is mapped 23 m
    past the deck's edge; the deck over it is that end's portal witness.
    A deck beyond the approach's reach witnesses nothing; nor does one the
    bore only grazes."""
    from auto_patch_v2.planar.end_witness import EndWitness
    from shapely.geometry import LineString
    deck = _sbox(23.0, -15.0, 53.0, 15.0)
    on_field = types.SimpleNamespace(deck_polys=[deck], corridor_prints=[], portal_ends=[],
                                     airport=None)
    w = EndWitness(on_field, LAW)
    bore = LineString([(0.0, 0.0), (76.0, 0.0)])
    assert w.at((0.0, 0.0), [(0.0, 0.0), (-50.0, 0.0)]) is None          # end only: too far
    assert w.at((0.0, 0.0), [(0.0, 0.0), (-50.0, 0.0)], bore) == \
        "a pack hard deck over the bore near it"
    assert w.at((76.0, 0.0), [(76.0, 0.0), (126.0, 0.0)], bore) is not None
    long = LineString([(0.0, 0.0), (600.0, 0.0)])
    far = EndWitness(types.SimpleNamespace(deck_polys=[_sbox(400.0, -15.0, 430.0, 15.0)],
                                           corridor_prints=[], portal_ends=[], airport=None),
                     LAW)
    assert far.at((0.0, 0.0), [(0.0, 0.0), (-50.0, 0.0)], long) is None
    graze = EndWitness(types.SimpleNamespace(deck_polys=[_sbox(23.0, 0.0, 53.0, 30.0)],
                                             corridor_prints=[], portal_ends=[], airport=None),
                       LAW)
    assert graze.at((0.0, 0.0), [(0.0, 0.0), (-50.0, 0.0)], bore) is None


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


#: a 1 m survey of a deck (|y| <= 12.5) at 29 over a road cutting (|x| <= 20)
#: at 21.5, the ground at 28 beyond
_DECKED = _Airport(lambda x, y: 29.0 if abs(y) <= 12.5 else 21.5 if abs(x) <= 20.0 else 28.0)
_UNDER = _sbox(-50.0, -12.5, 50.0, 12.5)


def test_a_deck_trench_reads_its_cutting_where_it_leaves_the_deck():
    """KIAH obj24551 (#2128 item 4): the survey over the deck reads the deck;
    past its edge, the road in its cutting -- none on a coarse DEM, none
    where the axis never leaves the deck."""
    from auto_patch_v2.planar.survey_cut import deck_cutting
    from shapely.geometry import LineString
    axis = LineString([(0.0, 0.0), (0.0, 120.0)])
    cut = deck_cutting(_DECKED, LAW, True, 29.0, axis, _UNDER, 7.0)
    assert cut is not None and cut.road == 21.5 and cut.cover == 29.0
    assert cut.start == (0.0, 12.5)
    assert deck_cutting(_DECKED, LAW, False, 29.0, axis, _UNDER, 7.0) is None
    assert deck_cutting(_DECKED, LAW, True, 29.0, LineString([(0, 0), (0, 10)]), _UNDER,
                        7.0) is None


def test_airside_pavement_on_a_deck_trenchs_cutting_floor_is_no_stop():
    """An apron piece the survey reads down in the cutting 6-20 m past the
    deck's edge (the pack's apron polygon over the road, KIAH dsf:pol153#1)
    stops the run-out without the cutting and not with it -- read from where
    the cutting opens, never the mouth on the deck's midline; an apron up on
    the ground still stops."""
    from auto_patch_v2.classify.roles import Cell
    from auto_patch_v2.planar.structure_mouth import mouth_stops
    from auto_patch_v2.planar.structure_service import airside_cut_roles
    from auto_patch_v2.planar.survey_cut import deck_cutting
    from shapely.geometry import LineString, Polygon

    def cell(i, ref, ring):
        return Cell(i, "apron", ref, ring, (), None, "E", "airside", "corridor", {})
    cells = [cell(0, "sliver", ((-15, 18), (15, 18), (15, 33), (-15, 33))),
             cell(1, "high", ((25, 18), (60, 18), (60, 33), (25, 33)))]
    polys = [Polygon(c.ring) for c in cells]
    tn = LAW.tables.structures.tunnel
    rim_off = tn.wall_gap_m + tn.wall_band_width_m
    grid = LAW.tables.emit.identity.min_distinct_spacing_m
    axis = LineString([(0.0, 0.0), (0.0, 200.0)])
    cut = deck_cutting(_DECKED, LAW, True, 29.0, axis, _UNDER, 7.0)

    def stops(on_floor):
        return sorted(r for _p, r in mouth_stops(
            cells, polys, LAW, airside_cut_roles(LAW), axis, (0.0, 0.0), 3.5, rim_off, (),
            grid, (), None, on_floor))
    assert stops(None) == ["high", "sliver"]
    assert stops(lambda p, m: cut.floor_face(p, m, 2.0 * (3.5 + rim_off))) == ["high"]
