"""20g (3) / 20s (``planar/soffit_road``): a mapped road or rail short of
its class clearance under a pack soffit is an open trench of the R6 family
-- flat under the soffit, climbing at road / rail grade law beyond it,
level to a way's end inside the group (O4); refused by class near airside
(G1), in a level seed's passage, and deeper than ``max_depth_m`` (O5).
Synthetic field: flat ground at 100 m, one building (the anchor) beside a
deck over the way."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import crossing_seat as cs
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.structures import profile_z
from auto_patch_v2.planar.soffit_road import ID_PREFIX, soffit_road_groups
from shapely.geometry import Polygon, box

GROUND = 100.0


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _xy(lo, la):
    return (lo, la)              # the twin's frame IS lon/lat in metres


def _rec(soffit: float, need: float, kind: str, way: str, x0=-5.0, x1=5.0):
    """One crossing group: a building (anchor) at x -60..-40 and a deck
    over x0..x1 across the way along y = 0."""
    feet = [(-1.0, -60.0, 0.0), (1.0, -60.0, 0.0), (-1.0, -40.0, 0.0), (1.0, -40.0, 0.0)]
    bld = {"member": "dsf:b", "comp": 0, "vote": GROUND, "area": 400.0, "building": True,
           "feet": [(la, lo, y) for la, lo, y in feet],
           "fxy": [(lo, la, y) for la, lo, y in feet], "plan": box(-60, -10, -40, 10)}
    xs, ys = np.meshgrid(np.arange(x0, x1, 1.0) + 0.5, np.arange(-2.5, 2.5, 1.0) + 0.5)
    cells = np.stack([xs.ravel(), ys.ravel(), np.full(xs.size, soffit)], axis=1)
    c = {"member": "dsf:d", "comp": 0, "way": way, "kind": kind, "need": need,
         "soffit_y": soffit, "least_m": soffit - GROUND, "at": (0.0, 0.0), "cells": cells,
         "class": ""}
    return {"unit": "unit:0", "parts": [bld], "spread": 0.0, "anchor": ("dsf:b", 0),
            "vote_anchor": GROUND, "plan": box(-60, -10, x1, 10), "crossings": [c],
            "class": ""}


def _field(rec, ways, dem=lambda x, y: GROUND):
    return types.SimpleNamespace(
        elevated_crossings=(rec,), osm_ways=tuple(ways), runways=(), taxi_nodes={},
        ground_routes=(), dem=types.SimpleNamespace(z=dem),
        frame=types.SimpleNamespace(entry=lambda: _xy))


def _road(tags=None, x0=-600.0, x1=600.0):
    return OsmWay(1, "big_roads", ((x0, 0.0), (0.0, 0.0), (x1, 0.0)), False,
                  tags or {"highway": "service"})


def _halves(groups):
    assert len(groups) == 2 and all(g.tid.startswith(ID_PREFIX) for g in groups)
    assert all(g.kind == "sunken_road" for g in groups)
    return groups


def _floor(law, soffit, need):
    """The planned floor: the planned seat less the ground bar it may solve
    under (``seat_plan``'s ``slack``), the soffit, the need and the margin."""
    bar = law.tables.structures.placement.split_bar_m
    return GROUND - bar + soffit - need - cs.margin_m(law)


def _ramp(g) -> float:
    (_s0, _z0), (s_f, _zf), (s_top, _zt) = g.profile
    return s_top - s_f


def test_a_short_road_is_a_trench_at_road_grade(law):
    rec = _rec(2.5, 4.2, "highway=service", "1")          # 1.7 m short
    groups, notes, refused = soffit_road_groups(_field(rec, [_road()]), law, (), ())
    assert not refused and len(notes) == 1
    floor = _floor(law, 2.5, 4.2)
    grade = law.tables.structures.tunnel.ramp_grade
    for g in _halves(groups):
        assert profile_z(g.profile, 0.0) == pytest.approx(floor)
        # flat under the soffit (the deck spans x -5..5: 5 m pad each side)
        assert g.profile[1][0] >= 5.0 - 1e-6
        # the climb tops out at the ground at the design grade, one station
        assert _ramp(g) == pytest.approx((GROUND - floor) / grade, abs=5.0)
    assert cs.VERDICTS[("unit:0", "dsf:d", 0, "1")] == "trench"


def test_a_short_rail_climbs_at_rail_grade(law):
    rail = _road({"railway": "rail"})
    rec = _rec(3.3, 5.0, "railway=rail", "1")             # 1.7 m short
    groups, _n, refused = soffit_road_groups(_field(rec, [rail]), law, (), ())
    assert not refused
    floor = _floor(law, 3.3, 5.0)
    grade = law.tables.structures.tunnel.rail_ramp_grade
    for g in _halves(groups):
        assert _ramp(g) == pytest.approx((GROUND - floor) / grade, abs=5.0)
        assert g.design_grade == pytest.approx(grade)


def test_a_rail_ending_in_the_group_stays_level_to_its_end(law):
    rail = OsmWay(1, "big_roads", ((-600.0, 0.0), (0.0, 0.0), (2.0, 0.0)), False,
                  {"railway": "rail"})
    rec = _rec(3.3, 5.0, "railway=rail", "1", -5.0, 2.0)
    groups, _n, refused = soffit_road_groups(_field(rec, [rail]), law, (), ())
    assert not refused
    floor = _floor(law, 3.3, 5.0)
    end = next(g for g in _halves(groups) if g.axis[-1][0] > 0.0)
    assert all(z == pytest.approx(floor) for _s, z in end.profile)


def test_a_trench_near_airside_is_held(law):
    rec = _rec(2.5, 4.2, "highway=service", "1")
    apron = ((-20.0, 6.0), (20.0, 6.0), (20.0, 40.0), (-20.0, 40.0))
    cells = (Cell(0, "apron", "A", apron, (), None, None, "airside", "apron", {}),)
    groups, _n, refused = soffit_road_groups(_field(rec, [_road()]), law, cells,
                                             (Polygon(apron),))
    assert groups == [] and len(refused) == 1 and "airside_held" in refused[0]
    assert cs.VERDICTS[("unit:0", "dsf:d", 0, "1")] == "airside_held"


def test_a_run_in_a_level_seed_passage_is_refused(law):
    rec = _rec(2.5, 4.2, "highway=service", "1")
    seed = types.SimpleNamespace(unit=7, passage=box(-30, -10, 30, 10), plan=box(-30, -10, 30, 10))
    groups, _n, refused = soffit_road_groups(_field(rec, [_road()]), law, (), (), (seed,))
    assert groups == [] and "level_seed" in refused[0]


def test_a_trench_deeper_than_the_cap_is_refused(law):
    rec = _rec(2.2, 5.0, "highway=primary", "1")
    rec["parts"][0]["vote"] = rec["vote_anchor"] = GROUND - 1.5

    def dem(x, y):
        return GROUND - 1.5 if x < -30.0 else GROUND
    groups, _n, refused = soffit_road_groups(_field(rec, [_road({"highway": "primary"})], dem),
                                             law, (), ())
    assert groups == [] and "depth_cap" in refused[0]


def test_a_clear_crossing_cuts_nothing(law):
    rec = _rec(5.0, 4.2, "highway=service", "1")          # clears past the ground bar
    groups, notes, refused = soffit_road_groups(_field(rec, [_road()]), law, (), ())
    assert groups == [] and notes == [] and refused == []
