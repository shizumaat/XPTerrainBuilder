"""§27 ACROSS A BARRIER (owner RULINGS 2026-10-28p (3), Q242 "a", #1338):
a lot's contact with airside pavement that runs under a building or along
the pack's own fence is no connection to airside — the lot stays
groundside (``classify/barrier_edge``).  The NZWN car park, synthetic: a
lot with a 100 m edge on the apron, part of it under the terminal and the
rest along a pack fence drawn a few metres off the shared edge."""
from __future__ import annotations

import types

from auto_patch_v2.airport.facade import LOT_SOURCE
from auto_patch_v2.classify.airside_edge import airside_edge_flip
from auto_patch_v2.classify.barrier_edge import BARRIER_M_KEY, barrier_band
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import FenceLine
from shapely.geometry import box

LAW = Law.for_airport("SYNT")
RULES = load_rules()

APRON = box(0.0, -100.0, 200.0, 0.0)          # the apron south of y 0
LOT = box(0.0, 0.0, 100.0, 60.0)              # the car park, 100 m on the apron


def _bldg(x0, y0, x1, y1, source="dsf:fac:terminal"):
    return types.SimpleNamespace(outer=((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
                                 holes=(), source=source)


def _airport(buildings=(), fences=()):
    return types.SimpleNamespace(buildings=tuple(buildings), fences=tuple(fences))


def _final():
    return [["apron", "apron0", APRON, None, {}, "apron"],
            ["parking_lot", "lot0", LOT, None, {}, "parking_lot"]]


def _flip(airport):
    final = _final()
    airside_edge_flip(final, [], LAW, RULES, barrier=barrier_band(airport, RULES))
    return final[1]


TERMINAL = _bldg(0.0, -30.0, 45.0, 5.0)        # straddles the first 45 m of edge
#: the pack fence, drawn 3 m inside the lot along the rest of the edge
FENCE = FenceLine("dsf:fence0", ((40.0, 3.0), (100.0, 3.0)), "lib/fence.fac")


def test_a_lot_under_a_building_and_along_the_fence_stays_groundside():
    lot = _flip(_airport([TERMINAL], [FENCE]))
    assert lot[0] == "parking_lot"
    assert lot[4][BARRIER_M_KEY] >= 90.0


def test_the_same_lot_without_its_barrier_is_an_apron():
    assert _flip(_airport())[0] == "apron"
    # half a barrier leaves an open edge longer than `airside_edge_min_m`
    assert _flip(_airport([TERMINAL]))[0] == "apron"
    assert _flip(_airport([], [FENCE]))[0] == "apron"


def test_a_fence_beyond_its_reach_is_no_barrier():
    far = float(RULES.lot.fence_contact_m) + 2.0
    fence = FenceLine("dsf:fence0", ((40.0, far), (100.0, far)), "lib/fence.fac")
    assert _flip(_airport([TERMINAL], [fence]))[0] == "apron"


def test_an_open_lot_facade_is_no_building():
    lot_fac = _bldg(0.0, -30.0, 45.0, 5.0, source=LOT_SOURCE)
    assert _flip(_airport([lot_fac], [FENCE]))[0] == "apron"
    assert barrier_band(_airport([lot_fac]), RULES) is None


def test_a_fence_crossing_the_contact_is_no_barrier_along_it():
    # the lot meets the apron on both sides of a fence that runs across it
    across = FenceLine("dsf:fence0", ((70.0, -40.0), (70.0, 40.0)), "lib/fence.fac")
    assert _flip(_airport([TERMINAL], [across]))[0] == "apron"
