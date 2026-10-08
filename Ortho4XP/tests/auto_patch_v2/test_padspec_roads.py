"""Spec §56 (2): THE NEAR ROAD IS THE PAD — ``classify/road_absorb``
(owner RULINGS 2026-10-07a (6); issue #452)."""
from __future__ import annotations

import dataclasses as dc

import pytest
from shapely.geometry import Polygon, box

from auto_patch_v2.classify.road_absorb import (ABSORB_GROWTH, KEPT_CLIPPED,
                                                KEPT_PIECES,
                                                KEPT_STRUCTURE, ROADS_KEPT,
                                                absorb_near_roads)
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


def _growth_sums(pad_before, closed_area, ref="building1"):
    g = ABSORB_GROWTH[ref]
    assert set(g) == {"road", "shade_clipped", "airside_clipped", "fill"}
    assert sum(g.values()) == pytest.approx(closed_area - pad_before.area, abs=1.0)
    return g


def test_the_re_close_takes_no_airside(law):
    """§56 (2) 8: a road 8 m from the pad across a 4 m apron TONGUE is
    absorbed and the tongue stays apron — the old pad is never cut."""
    pad = box(0, 0, 60, 40)
    road = box(0, 44, 60, 48)                 # joined to the pad at its west end
    link = box(0, 40, 10, 44)                 # bare ground the close fills
    tongue = box(20, 40, 80, 44)              # apron between road and pad
    cells = [_cell(0, "building", "building1", pad, "airside"),
             _cell(1, "service_road", "route7", road.union(link), "groundside"),
             _cell(2, "apron", "pav1", tongue, "airside")]
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law))
    assert absorbed == {"building1": ["route7"]}
    grown = Polygon(out[0].ring, out[0].holes)
    assert grown.intersection(tongue).area == pytest.approx(0.0, abs=1e-6)
    assert grown.covers(pad) and grown.covers(road)
    assert out[1].ring == cells[2].ring       # the apron cell is untouched
    g = ABSORB_GROWTH["building1"]
    # §56 (11) R-W: the fill over the tongue is never made — the frontage
    # is pinned through the re-close — so rule 8's clip has nothing to take
    assert g["airside_clipped"] == 0.0
    assert g["road"] == pytest.approx(road.union(link).area, abs=1.0)
    assert g["shade_clipped"] == 0.0


def test_a_road_the_clip_leaves_off_the_pad_is_kept_and_the_rest_absorbed(law):
    """§56 (2) 8 + 4 (d), per road: an apron strip wholly between a road
    and the pad leaves that road off the pad once the airside is clipped —
    it stays a road; the road on the other face is still absorbed."""
    cells = _scene(1.1) + [
        _cell(3, "service_road", "route9", box(5, -8, 55, -4), "groundside"),
        _cell(4, "apron", "pav1", box(-20, -4, 80, 0).difference(box(0, 0, 60, 40)),
              "airside")]
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law))
    assert absorbed == {"building1": ["route7"]}
    assert ("route9", "building1", KEPT_PIECES) in ROADS_KEPT
    assert [c.ref for c in out] == ["building1", "pav3", "route9", "pav1"]
    grown = Polygon(out[0].ring, out[0].holes)
    assert grown.intersection(box(-20, -4, 80, 0)).area == pytest.approx(0.0, abs=1e-6)


def test_a_shade_notch_beside_an_absorbed_road_stays_a_notch(law):
    """§56 (2) 8: the mint cut a 5 m deck-shade notch out of the pad; the
    absorption's re-close (mouth < 6 m) may not fill it back."""
    notch = box(27.5, 30, 32.5, 40)
    pad = box(0, 0, 60, 40).difference(notch)
    cells = _scene(1.1)
    cells[0] = _cell(0, "building", "building1", pad, "airside")
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law), shades=notch)
    assert absorbed == {"building1": ["route7"]}
    grown = Polygon(out[0].ring, out[0].holes)
    assert grown.is_valid
    assert grown.intersection(notch).area == pytest.approx(0.0, abs=1e-6)
    assert ABSORB_GROWTH["building1"]["shade_clipped"] == pytest.approx(50.0, abs=1.0)
    # without the shade the same notch fills (the closing's own behaviour)
    out2, _ = absorb_near_roads(cells, law, pad_outline(law))
    assert Polygon(out2[0].ring, out2[0].holes).intersection(notch).area > 45.0
    assert ABSORB_GROWTH["building1"]["shade_clipped"] == 0.0


def test_a_road_under_a_deck_shade_is_not_folded_in(law):
    """§56 (2) 8: a road the clip would CUT (it runs under a deck's shade)
    stays a road — folding it in would leave the shaded stretch no cell."""
    cells = _scene(1.1)
    out, absorbed = absorb_near_roads(cells, law, pad_outline(law),
                                      shades=box(20, 40.5, 30, 60))
    assert absorbed == {} and out is cells
    assert ROADS_KEPT == [("route7", "building1", KEPT_CLIPPED)]


def test_a_route_beside_the_buildings_own_wall_is_absorbed(law):
    """§56 (2) 4 (b) DELETED: no wall-extension keep-out exists — the only
    keep-out is the mapped bore."""
    import inspect
    assert set(inspect.signature(absorb_near_roads).parameters) == {
        "cells", "law", "outline", "keep_out", "shades"}


def test_zero_disarms(law):
    cells = _scene(1.1)
    off = dc.replace(pad_outline(law), road_absorb_m=0.0)
    assert absorb_near_roads(cells, law, off) == (cells, {})


def test_with_the_outline_close_disarmed_no_held_off_road_is_absorbed(law):
    """§56 (11) fix 3, the coupling STATED: the stand-off between a pad
    and its near road is filled by the re-close at ``outline_close_m``, so
    with that key 0 the road cannot join — ``pad_road_absorb_m`` alone
    absorbs nothing across a stand-off.  (A cell already touching the pad
    needs no close and still joins.)"""
    cells = _scene(1.1)                       # the set-back's own stand-off
    no_close = dc.replace(pad_outline(law), close_m=0.0)
    assert absorb_near_roads(cells, law, no_close) == (cells, {})
    assert ("route7", "building1", KEPT_PIECES) in ROADS_KEPT
    out, absorbed = absorb_near_roads(_scene(0.0), law, no_close)
    assert absorbed == {"building1": ["route7"]}


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
