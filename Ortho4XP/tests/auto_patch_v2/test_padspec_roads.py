"""Spec §56 (2): THE NEAR ROAD IS THE PAD — ``classify/road_absorb``
(owner RULINGS 2026-10-07a (6); issue #452)."""
from __future__ import annotations

import dataclasses as dc

import pytest
from shapely.geometry import Polygon, box

from auto_patch_v2.classify.road_absorb import (KEPT_PIECES, KEPT_STRUCTURE,
                                                KEPT_WALL,
                                                ROADS_KEPT, absorb_near_roads)
from auto_patch_v2.classify.roles import Cell, _cut_back_groundside
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import load_default
from auto_patch_v2.law.tables import pad_outline


def _cell(i, role, ref, poly, side):
    return Cell(i, role, ref, tuple(poly.exterior.coords)[:-1], (), None,
                None, side, role, {})


def _scene(road_gap_m: float, road_w: float = 6.0):
    """A 60 x 40 m pad, a road ``road_gap_m`` off its north face, a lot
    far to the south."""
    pad = box(0, 0, 60, 40)
    road = box(5, 40 + road_gap_m, 55, 40 + road_gap_m + road_w)
    lot = box(0, -80, 60, -40)
    return [_cell(0, "building", "building1", pad, "airside"),
            _cell(1, "service_road", "route7", road, "groundside"),
            _cell(2, "parking_lot", "pav3", lot, "groundside")]


@pytest.fixture(scope="module")
def law():
    return load_default()


def test_law_value(law):
    assert pad_outline(law).road_absorb_m == 10.0


def test_a_road_wholly_within_reach_is_the_pad_and_the_stand_off_fills(law):
    cells = _scene(1.1)                       # the set-back's own stand-off
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law))
    assert absorbed == {"building1": ["route7"]}
    assert [c.ref for c in out] == ["building1", "pav3"]
    assert [c.id for c in out] == [0, 1]
    pad = Polygon(out[0].ring, out[0].holes)
    assert pad.is_valid and not out[0].holes
    # the 1.1 m band between the old rim and the road is pad now
    assert pad.contains(box(6, 40.1, 54, 41.0))
    assert pad.contains(box(6, 41.2, 54, 47.0))
    assert out[1].ring == cells[2].ring       # a cell nothing touched


def test_a_road_partly_beyond_reach_keeps_its_shape(law):
    cells = _scene(6.0)                       # 6 + 6 m wide: far edge at 12 m
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law))
    assert absorbed == {} and out is cells    # byte-identical: the same list


def test_a_road_reaching_eight_metres_is_absorbed_and_twelve_is_not(law):
    near, _ = absorb_near_roads(_scene(1.1, 6.9), law, pad_outline(law))
    far, got = absorb_near_roads(_scene(1.1, 10.9), law, pad_outline(law))
    assert [c.ref for c in near] == ["building1", "pav3"]
    assert got == {} and [c.ref for c in far] == ["building1", "route7", "pav3"]


def test_a_road_the_close_cannot_join_is_kept(law):
    """A road wholly within reach but across a gap wider than the close
    (2 x 3 m) would leave the pad in two pieces: it stays a road."""
    cells = _scene(8.0, 2.0)
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law))
    assert absorbed == {} and out is cells
    assert ROADS_KEPT == [("route7", "building1", KEPT_PIECES)]


def test_a_road_over_a_structure_footprint_is_kept_with_its_reason(law):
    cells = _scene(1.1)
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law),
                                      keep_out=box(20, 30, 30, 60))
    assert absorbed == {} and out is cells
    assert ROADS_KEPT == [("route7", "building1", KEPT_STRUCTURE)]


def test_a_wall_extended_route_is_kept(law):
    cells = _scene(1.1)
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law),
                                      wall_extended=box(50, 41, 55, 47))
    assert absorbed == {} and ROADS_KEPT[0][2] == KEPT_WALL


def test_zero_disarms(law):
    cells = _scene(1.1)
    off = dc.replace(pad_outline(law), road_absorb_m=0.0)
    assert absorb_near_roads(cells, law, off) == (cells, {})


def test_only_a_changed_pad_draws_the_second_knife(law):
    """§56 (2) 6: the re-applied set-back cuts beside the GROWN pad and
    leaves every other pad's neighbours as the first pass cut them."""
    rules = load_rules()
    pad2 = box(200, 0, 260, 40)
    lot2 = box(200, 40.2, 260, 60)            # 0.2 m off pad2: inside its knife
    lot1 = box(5, 47.3, 55, 70)               # 0.2 m off the absorbed road
    cells = _scene(1.1) + [_cell(3, "building", "building2", pad2, "airside"),
                           _cell(4, "parking_lot", "pav9", lot2, "groundside"),
                           _cell(5, "parking_lot", "pav8", lot1, "groundside")]
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law))
    assert list(absorbed) == ["building1"]
    recut, n = _cut_back_groundside(out, law, rules, only=frozenset(absorbed))
    by = {c.ref: c for c in recut}
    assert n == 1
    assert by["pav9"].ring == cells[4].ring           # pad2 drew no knife
    back = law.tables.structures.building_pad.groundside_cutback_m
    grown = Polygon(by["building1"].ring)
    assert Polygon(by["pav8"].ring).distance(grown) >= back
