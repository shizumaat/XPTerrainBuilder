"""#2116 (c) (owner 2026-11-17T00:13Z; RULINGS 2026-11-16g (3)): the part of
a lot page that climbs toward a mapped road at another level is a road.

``classify/lot_climb.climb_arms`` reads two witnesses, never the ground
alone (RULINGS 2026-11-16s): a mapped road within ``[lot] climb_reach_m`` of
the page that does not enter it, and the page's part whose ground runs
steeper than the lot cap, rising at least ``climb_min_rise_m`` toward that
road.  MEASURED KDEN ``dsf:pol32``: 3,473 m², rise 4.55 m, road -3642 14.5 m
off at 1644.94.
"""
from __future__ import annotations

import types

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.strtree import STRtree

from auto_patch_v2.classify.lot_climb import climb_arms
from auto_patch_v2.classify.rules import load_rules


class _Dem:
    """Flat at 100 for y >= 0; a 10 % berm south of y = 0 (y down to -40)."""

    def z_many(self, xs, ys):
        ys = np.asarray(ys, dtype=float)
        return 100.0 + 0.10 * np.clip(-ys, 0.0, 40.0)


LOT = Polygon([(0, 20), (200, 20), (200, 0), (60, 0), (60, -35), (0, -35)])


def _arms(road: LineString, dem=_Dem()):
    lot = load_rules().lot
    return climb_arms(LOT, [road], STRtree([road]), dem, lot)


def test_the_part_climbing_to_a_road_is_an_arm():
    arms = _arms(LineString([(-30, -45), (-5, -45)]))   # 10+ m off the SW corner
    assert len(arms) == 1
    arm, info = arms[0]
    assert arm.bounds[1] < -20 and arm.bounds[3] <= 2.0   # the berm part only
    assert info["rise_m"] >= 2.0


def test_no_road_within_reach_no_arm():
    assert _arms(LineString([(-90, -45), (-60, -45)])) == []


def test_a_road_entering_the_page_is_its_own_not_a_level():
    assert _arms(LineString([(30, -60), (30, -10)])) == []


def test_a_road_on_the_low_side_is_no_climb():
    # the road stands north of the flat part: the berm climbs AWAY from it
    assert _arms(LineString([(100, 30), (150, 30)])) == []


def test_flat_ground_has_no_arm():
    flat = types.SimpleNamespace(z_many=lambda xs, ys: np.full(len(xs), 100.0))
    assert _arms(LineString([(-30, -45), (-5, -45)]), flat) == []
