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


def _run(law, parts, tmp_path, roads=(), ground=lambda x, y: 26.0):
    A = _airport(parts, tmp_path, ground=ground)
    A.osm_ways = list(roads)
    A.frame.transformers = lambda: ((lambda lon, lat: (lon, lat)), (lambda x, y: (y, x)))
    seeds, _notes = LR.level_seeds(A, _cls(), law)
    reg = Registries()
    reg.held["term"] = {"unit": "term", "datum_pred": 30.0}
    reg.held["stn"] = {"unit": "stn", "datum_pred": 30.0}
    regs = [Region(role="building", ref=ref, polygon=g, code_number=None, code_letter=None,
                   side="airside", source="cell") for ref, g in (("term", T), ("stn", STN))]
    counts: dict = {}
    out = LR.seed_levels(regs, reg, seeds, [AirRegion(AIR, "cell")], A, law, 0.5, counts)
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
