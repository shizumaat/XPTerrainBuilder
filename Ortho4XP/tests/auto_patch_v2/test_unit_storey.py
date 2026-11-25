"""THE UPPER STOREY OF A UNIT (owner answer 47, 2026-10-20, #1099 / #1101):
a lot that meets the apron only across a unit's object-witnessed storey
stays groundside under §27, is cut back along it, and meets its pad's
UPPER level (``airport/unit_storey``, ``classify/storey_edge``,
``planar/low_level.plan_up``).  The LPHR terminal, synthetic: floor y 0 on
the apron, a 68 m parapet at +6 along the forecourt's edge with it."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport.unit_storey import upper_storeys
from auto_patch_v2.classify.airside_edge import airside_edge_flip
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.classify.storey_edge import (STOREY_M_KEY, STOREY_Y_KEY, knife_storeys,
                                                storey_band)
from auto_patch_v2.law import Law
from auto_patch_v2.planar.low_level import plan_up
from shapely.geometry import box

LAW = Law.for_airport("SYNT")
def XY(lon, lat):
    return (lon, lat)


def _part(x0, y0, x1, y1, base_y, feet=False):
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))      # (lat, lon) = (y, x)
    return types.SimpleNamespace(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=base_y,
                                 rings=(ring,), feet=((y0, x0, base_y),) if feet else (),
                                 line=False, scatter=False)


def _airport(parts):
    unit = types.SimpleNamespace(members=[types.SimpleNamespace(parts=parts)])
    return types.SimpleNamespace(partition=types.SimpleNamespace(units=[unit]),
                                 frame=types.SimpleNamespace(entry=lambda: XY))


APRON = box(0.0, -100.0, 200.0, 0.0)          # the apron south of y 0
LOT = box(0.0, 0.0, 68.0, 60.0)               # the forecourt, 68 m on the apron
FLOOR = [_part(100.0, -20.0, 140.0, -2.0, 0.0, feet=True)]
PARAPET = _part(0.0, 0.0, 68.0, 1.0, 6.0)     # the storey's retaining wall top


def _final():
    return [["apron", "apron0", APRON, None, {}, "apron"],
            ["parking_lot", "lot0", LOT, None, {}, "parking_lot"]]


def test_the_storey_is_read_from_the_grounded_floor():
    st = upper_storeys(_airport(FLOOR + [PARAPET]), LAW, APRON)
    assert len(st) == 1 and st[0].floor_y == 0.0
    assert [p.base_y for p in st[0].parts] == [6.0]
    # no grounded part at the airside: no floor, no storey
    assert upper_storeys(_airport([PARAPET]), LAW, APRON) == []


def test_a_lot_across_the_storey_stays_groundside_and_is_cut_back():
    final = _final()
    band = storey_band(_airport(FLOOR + [PARAPET]), LAW, [], final)
    cuts: dict = {}
    airside_edge_flip(final, [], LAW, load_rules(), storey=band, storey_cuts=cuts, to_xy=XY)
    assert final[1][0] == "parking_lot"
    assert final[1][4][STOREY_M_KEY] >= 60.0 and final[1][4][STOREY_Y_KEY] == 6.0
    assert knife_storeys(final, cuts, LAW, 1.0, band) == 1
    back = float(LAW.tables.structures.building_pad.groundside_cutback_m)
    assert final[1][2].distance(APRON) >= back
    # the same lot without the storey's witness is an apron (§27)
    final = _final()
    airside_edge_flip(final, [], LAW, load_rules(),
                      storey=storey_band(_airport(FLOOR), LAW, [], final), to_xy=XY)
    assert final[1][0] == "apron"


def test_the_pad_meets_the_storey_lot_at_its_upper_level():
    pad = box(70.0, 0.0, 170.0, 40.0)          # the terminal, the lot along its north
    lot = box(70.0, 40.0, 170.0, 80.0)
    got = plan_up(pad, APRON, lot, 6.0, LAW, 0.5)
    assert got is not None
    H, U, S, rec = got
    assert rec["y"] == 6.0
    assert U.distance(lot) == pytest.approx(0.0, abs=1e-6)        # the lot meets it
    assert U.distance(APRON) >= 3.0 - 1e-6                         # the frontage stays low
    assert U.intersection(H).area == pytest.approx(0.0, abs=1e-6) and S.area > 0.0
    assert plan_up(pad, APRON, box(300.0, 300.0, 310.0, 310.0), 6.0, LAW, 0.5) is None


def test_a_level_of_a_whole_unit_pad_is_its_own_plane():
    from auto_patch_v2.constraints.cluster_pad import _split_blocks
    F = types.SimpleNamespace
    planar = F(faces={1: F(ref="building1"), 2: F(ref="building1/p1"),
                      3: F(ref="building1/p1#strip")})
    groups = [(1, "building1", [10, 11]), (2, "building1/p1", [20, 21]),
              (3, "building1/p1#strip", [11, 20])]
    out = _split_blocks(planar, [(1, "cluster:u", [10, 11, 20, 21], (1, 2, 3))], groups)
    assert sorted(e[3] for e in out) == [(1,), (2, 3)]



class _Dem:
    def __init__(self, f):
        self.z = f


def _landside(dem):
    """#2279 PHLI, synthetic: a terminal whose landside floor stands a storey
    (+4.1) over its apron floor; the pack's landside lot reaches the apron
    along the terminal's whole airside face, in front of the upper parts
    (inside the storey's plan, under no single part), and past both of the
    unit's ends for 20 m each."""
    floor = _part(100.0, -20.0, 140.0, -2.0, 0.0, feet=True)
    upper = [_part(20.0, 0.0, 60.0, 60.0, 4.1), _part(200.0, 0.0, 250.0, 60.0, 4.1),
             _part(60.0, 20.0, 200.0, 60.0, 4.1)]
    ap = _airport([floor, *upper])
    ap.dem = dem
    final = [["apron", "apron0", box(-50.0, -100.0, 320.0, 0.0), None, {}, "apron"],
             ["parking_lot", "lot0", box(0.0, 0.0, 270.0, 100.0), None, {}, "parking_lot"]]
    return ap, final


def test_a_lot_meeting_the_apron_mostly_across_a_storey_is_its_landside():
    ap, final = _landside(_Dem(lambda x, y: 46.0 + 4.6 * (y > 0)))
    band = storey_band(ap, LAW, [], final)
    cuts: dict = {}
    airside_edge_flip(final, [], LAW, load_rules(), storey=band, storey_cuts=cuts, to_xy=XY)
    assert final[1][0] == "parking_lot"
    assert final[1][4][STOREY_Y_KEY] == 4.1 and final[1][4][STOREY_M_KEY] >= 200.0
    assert knife_storeys(final, cuts, LAW, 1.0, band) == 1
    back = float(LAW.tables.structures.building_pad.groundside_cutback_m)
    # the runs past the unit's ends are cut back with the rest; what the lot
    # drew under the storey's plan stays apron, the lot cut back from it
    lots = [f for f in final if f[0] == "parking_lot"]
    under = [f for f in final[2:] if f[0] == "apron"]
    plan = box(20.0, 0.0, 250.0, 60.0)
    assert all(f[2].distance(final[0][2]) >= back for f in lots)
    assert all(f[2].distance(plan) >= back for f in lots)
    assert sum(f[2].area for f in under) == pytest.approx(plan.area, rel=1e-6)


def test_a_landside_the_ground_does_not_confirm_is_still_an_apron():
    ap, final = _landside(_Dem(lambda x, y: 46.0))
    airside_edge_flip(final, [], LAW, load_rules(), storey=storey_band(ap, LAW, [], final),
                      storey_cuts={}, to_xy=XY)
    assert final[1][0] == "apron"
