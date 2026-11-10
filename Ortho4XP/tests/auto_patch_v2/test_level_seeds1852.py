"""THE ROADS UNDER A BUILDING ARE ITS ONE LOWER LEVEL (#1852, two-level round
4; ``planar/level_regions``, ``planar/cut_runout`` roads, ``constraints/
ramp_runout``).

KIAH's train station: walls a storey under its zero on a §20 conforming pad,
the terminal roads running through it.  The pad is cut into ONE flat lower
level at the walls' depth, tied to the terminal block it fronts; the roads
leaving it climb to their ground; a basement (no road through) mints
nothing; a support founds nothing.
"""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.planar import level_regions as LR
from auto_patch_v2.planar.low_extent import AirRegion
from auto_patch_v2.planar.low_level import LOW_KIND
from auto_patch_v2.planar.overlay import Region
from shapely.geometry import box
from shapely.ops import unary_union
from test_two_pads1214 import _airport, _wall

T = box(400.0, 0.0, 500.0, 100.0)        # the terminal's held block (D 30)
STN = box(500.0, 10.0, 540.0, 60.0)      # the station's pad, the station on it
AIR = box(400.0, 100.0, 500.0, 130.0)    # the terminal's apron


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _station(y=-4.0):
    return [_wall(500.0, 10.0, 540.0, 60.0, y, 8)]


def _road(x0=480.0, x1=620.0, y=35.0):
    return types.SimpleNamespace(id=-1, points=[(x0, y), (x1, y)],
                                 tags={"highway": "service"})


def _cls():
    ring = tuple(AIR.exterior.coords)[:-1]
    return types.SimpleNamespace(cells=[types.SimpleNamespace(ring=ring, holes=(), role="apron")])


def _run(law, parts, tmp_path, roads=(), ground=lambda x, y: 26.0, pads=(), held=(), **kw):
    A = _airport(parts, tmp_path, ground=ground)
    A.osm_ways = list(roads)
    A.frame.transformers = lambda: ((lambda lon, lat: (lon, lat)), (lambda x, y: (y, x)))
    seeds, _notes = LR.level_seeds(A, _cls(), law)
    reg = Registries()
    reg.held["term"] = {"unit": "term", "datum_pred": 30.0}
    reg.held["stn"] = {"unit": "stn", "datum_pred": 30.0}
    for ref in held:
        reg.held[ref] = {"unit": ref, "datum_pred": 30.0}
    regs = [Region(role="building", ref=ref, polygon=g, code_number=None, code_letter=None,
                   side="airside", source="cell")
            for ref, g in (("term", T), ("stn", STN), *pads)]
    counts: dict = {}
    out = LR.seed_levels(regs, reg, seeds, [AirRegion(AIR, "cell")], A, law, 0.5, counts, **kw)
    return seeds, out, reg, counts


def test_the_roads_through_a_building_are_its_one_level(law, tmp_path):
    seeds, out, reg, counts = _run(law, _station(), tmp_path, roads=[_road()])
    (s,) = seeds
    assert s.depth == pytest.approx(4.0) and s.passage is not None
    (ref, rec), = ((k, v) for k, v in reg.landings.items() if v.get("witness") == "passage")
    # the level hangs off the station's own block (its zero), never the
    # terminal's beside it
    assert ref == "stn/p1" and rec["kind"] == LOW_KIND and rec["block"] == "stn"
    assert rec["y_lo"] == pytest.approx(-4.0) and rec["pad"] == "stn"
    L = next(r.polygon for r in out if r.ref == ref)
    assert L.area > 0.8 * STN.area                     # the station's whole floor, one level
    assert sum(r.polygon.area for r in out if r.ref == "stn") < 0.2 * STN.area
    assert any(r.ref == ref + "#strip" for r in out)


def test_the_roads_leaving_the_level_climb_to_their_ground(law, tmp_path):
    # the level stands at 26 (30 - 4); the ground beyond the station rises to 28
    def ground(x, y):
        return 26.0 if x < 545.0 else 26.0 + min(2.0, 0.05 * (x - 545.0))
    _s, _out, reg, counts = _run(law, _station(), tmp_path, roads=[_road()], ground=ground)
    ups = [v for v in reg.landing_runouts.values() if v.get("kind") == "level_end"]
    assert ups and all(v["sign"] < 0 and v["from_level"] for v in ups)
    assert max(v["run_m"] for v in ups) > 10.0


def _rising(x, y):
    return 26.0 if x < 545.0 else 26.0 + min(2.0, 0.05 * (x - 545.0))


def test_each_road_leaving_the_level_is_its_own_run_out_its_own_width(law, tmp_path):
    # two parallel roads through the station, 15 m apart: two ends, each
    # strip its own carriageway (never one strip across both, nor the
    # widest road's width), minted though the region's own riser strips
    # stand beside them (spec §19 E1/E2)
    from auto_patch_v2.airport.road_ways import ribbon_half_width_m
    roads = [_road(y=25.0), _road(y=40.0)]
    _s, _out, reg, counts = _run(law, _station(), tmp_path, roads=roads, ground=_rising)
    ups = sorted((v for v in reg.landing_runouts.values() if v.get("kind") == "level_end"),
                 key=lambda v: v["lip"][1])
    w = 2.0 * ribbon_half_width_m(roads[0].tags, law)
    assert len(ups) == 2 and counts["level_runout_ends"]["taken"] == 0
    assert [round(v["lip"][1]) for v in ups] == [25, 40]
    assert all(v["width_m"] == pytest.approx(w) for v in ups)
    for v in ups:                                   # inside its own carriageway only
        lo, hi = v["lip"][1] - 0.5 * w - 1e-6, v["lip"][1] + 0.5 * w + 1e-6
        assert all(lo <= y <= hi for q in v["polys"] for _x, y in q.exterior.coords)


def test_a_basement_mints_nothing(law, tmp_path):
    seeds, out, reg, _c = _run(law, _station(), tmp_path, roads=())
    assert len(seeds) == 1 and seeds[0].passage is None
    assert not reg.landings and {r.ref for r in out} == {"term", "stn"}


def test_walls_at_the_zero_seed_nothing(law, tmp_path):
    seeds, _out, reg, _c = _run(law, _station(y=-1.0), tmp_path, roads=[_road()])
    assert seeds == () and not reg.landings


def test_a_support_founds_no_seed(law, tmp_path):
    pole = _wall(500.0, 10.0, 500.00001, 10.00001, -4.0, 8)
    pole.box = (10.0, 500.0, 10.00001, 500.00001)
    seeds, _out, _reg, _c = _run(law, [pole], tmp_path, roads=[_road()])
    assert seeds == ()




#: a deck of the station's block standing over its lower storey (#1905
#: round 3, ``pad_fill.StoreyFloor``): its ground prints east of the station
FLOOR_PRINTS = (box(543.0, 10.0, 580.0, 32.0), box(543.0, 38.0, 580.0, 60.0))
FOOT = box(552.0, 33.0, 558.0, 37.0)        # a pad of its own on the deck floor


def _lower():
    """The arrivals road under the deck floor: the map places it lower."""
    return types.SimpleNamespace(id=-2, points=[(543.0, 35.0), (580.0, 35.0)],
                                 tags={"highway": "service", "layer": "-1", "covered": "yes"})


def _floor():
    from auto_patch_v2.planar.pad_fill import StoreyFloor
    return StoreyFloor("stn", "deck6", FLOOR_PRINTS)


@pytest.fixture
def no_deck(monkeypatch):
    """No pack deck carries a road here (``airport/carried_roads``)."""
    from auto_patch_v2.airport import partition_prints as PP
    monkeypatch.setattr(PP, "partition_prints", lambda _part: [])


def test_the_deck_floor_is_a_piece_of_the_level_at_its_depth(law, tmp_path, no_deck):
    """SBSP (owner RULINGS 2026-11-10f (1) "b"): the arrivals level spans
    the departures deck's floor -- one more piece ``<block>/p<k>`` at the
    host level's y, its record the host's with ``floor_of`` the deck."""
    _s, out, reg, _c = _run(law, _station(), tmp_path, roads=[_road(), _lower()],
                            floors=(_floor(),))
    (ref, rec), = ((k, v) for k, v in reg.landings.items() if v.get("floor_of"))
    host = reg.landings["stn/p1"]
    assert ref == "stn/p2" and rec["floor_of"] == "deck6" and rec["piece_of"] == "stn/p1"
    assert rec["y_lo"] == host["y_lo"] == pytest.approx(-4.0) and rec["block"] == "stn"
    q = next(r.polygon for r in out if r.ref == ref)
    # the prints and the lower road between them (closed), short of the riser
    assert q.area > 0.8 * 35.0 * 50.0
    assert any(r.ref == ref + "#strip" for r in out)


def test_a_pad_of_its_own_on_the_deck_floor_joins_it_a_held_one_is_kept(law, tmp_path,
                                                                         no_deck):
    _s, out, reg, c = _run(law, _station(), tmp_path, roads=[_road(), _lower()], floors=(_floor(),),
                           pads=(("foot", FOOT),))
    assert c["forecourt_pads_absorbed"] == 1 and not any(r.ref == "foot" for r in out)
    q = unary_union([r.polygon for r in out if r.ref == "stn/p2"])
    assert q.contains(FOOT.buffer(-0.01))
    _s, out, reg, c = _run(law, _station(), tmp_path, roads=[_road(), _lower()], floors=(_floor(),),
                           pads=(("foot", FOOT),), held=("foot",))
    assert "forecourt_pads_absorbed" not in c
    assert unary_union([r.polygon for r in out if r.ref == "foot"]).equals(FOOT)
    q = unary_union([r.polygon for r in out if r.ref == "stn/p2"])
    assert q.intersection(FOOT).area < 1e-6


def test_no_floor_no_change(law, tmp_path):
    """``floors=()`` is the level as before; a floor of another block is
    not this level's."""
    from auto_patch_v2.planar.pad_fill import StoreyFloor
    _s, a, ra, ca = _run(law, _station(), tmp_path, roads=[_road()])
    _s, b, rb, cb = _run(law, _station(), tmp_path, roads=[_road()], floors=())
    _s, c, rc, cc = _run(law, _station(), tmp_path, roads=[_road()],
                         floors=(StoreyFloor("term", "deck6", FLOOR_PRINTS),))
    for got, rg, cn in ((b, rb, cb), (c, rc, cc)):
        assert [(r.ref, r.polygon.wkt) for r in got] == [(r.ref, r.polygon.wkt) for r in a]
        assert rg.landings == ra.landings and cn == ca
