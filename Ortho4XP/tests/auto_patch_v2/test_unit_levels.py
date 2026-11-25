"""THE UNIT'S TWO FLOORS (RULINGS 2026-11-25g, 25h; spec
``docs/specs/terminal-frontage-split-level-20261125.md`` §1, step 1):
``airport/unit_storey.unit_levels`` reads a terminal-sized unit's airside
and groundside floors, both signs, and the ground's verdict.  Synthetic: a
100 x 90 m terminal, apron to its west (x < 0), landside to its east."""
from __future__ import annotations

import types

from auto_patch_v2.airport import unit_storey as us
from auto_patch_v2.law import Law
from shapely.geometry import box

LAW = Law.for_airport("SYNT")
AIR = box(-80.0, -10.0, 0.0, 100.0)
LAND = box(100.0, -10.0, 160.0, 100.0)


def _part(x0, y0, x1, y1, base_y, feet=True, height=4.0, line=False):
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))      # (lat, lon) = (y, x)
    return types.SimpleNamespace(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=base_y,
                                 rings=(ring,), feet=((y0, x0, base_y),) if feet else (),
                                 line=line, scatter=False, height_m=height)


class _Dem:
    def __init__(self, land: float):
        self.land = land

    def z(self, x, y):
        return self.land if x > 40.0 else 0.0


def _airport(parts, land=0.0):
    unit = types.SimpleNamespace(id="unit:0",
                                 members=[types.SimpleNamespace(id="m0", parts=parts)])
    return types.SimpleNamespace(partition=types.SimpleNamespace(units=[unit]),
                                 frame=types.SimpleNamespace(
                                     entry=lambda: (lambda lon, lat: (lon, lat))),
                                 dem=_Dem(land), retaining_walls=(), osm_ways=(),
                                 flat_site=None)


def _terminal(y_land, n=6, size=90.0):
    floor = [_part(0.0, 0.0, 40.0, size, 0.0)]
    land = [_part(60.0 + 6.0 * i, 0.0, 64.0 + 6.0 * i, size, y_land) for i in range(n)]
    return floor + land


def test_an_upper_storey_over_rising_ground_is_held():
    got = us.unit_levels(_airport(_terminal(4.1), land=4.0), LAW, AIR, ground=LAND)
    assert len(got) == 1
    r = got[0]
    assert (r.air_y, r.land_y, r.witness, r.verdict) == (0.0, 4.1, "storey_parts", us.HELD)
    assert abs(r.rise - 4.1) < 1e-9 and r.ground == (0.0, 4.0)


def test_a_lower_storey_is_read_with_its_sign():
    r = us.unit_levels(_airport(_terminal(-5.8), land=-6.0), LAW, AIR, ground=LAND)[0]
    assert (r.land_y, r.verdict) == (-5.8, us.HELD) and r.rise < 0.0


def test_level_ground_does_not_confirm_a_storey():
    r = us.unit_levels(_airport(_terminal(-5.8), land=-0.5), LAW, AIR, ground=LAND)[0]
    assert r.verdict == us.UNCONFIRMED


def test_ground_beyond_every_level_the_pack_explains_is_far():
    r = us.unit_levels(_airport(_terminal(-5.8), land=-20.0), LAW, AIR, ground=LAND)[0]
    assert r.verdict == us.FAR


def test_a_second_groundside_level_explains_a_deeper_ground():
    """Owner 25h Q1: the groundside may drop more than one level."""
    parts = _terminal(-5.8) + [_part(96.0, 0.0, 100.0, 90.0, -15.0, height=20.0)]
    r = us.unit_levels(_airport(parts, land=-14.0), LAW, AIR, ground=LAND)[0]
    assert sorted(round(lv.y, 1) for lv in r.levels) == [-15.0, -5.8]
    assert r.land_y == -5.8 and r.verdict == us.HELD


def test_one_level_and_small_units():
    r = us.unit_levels(_airport(_terminal(0.0), land=4.0), LAW, AIR, ground=LAND)[0]
    assert r.verdict == us.SINGLE and r.land_y is None and r.rise == 0.0
    assert us.unit_levels(_airport(_terminal(4.1, size=20.0), land=4.0), LAW, AIR) == []


def test_upper_storeys_still_reads_every_size():
    """``upper_storeys`` shares the floor read; its population is unchanged."""
    st = us.upper_storeys(_airport(_terminal(4.1, size=20.0)), LAW, AIR)
    assert len(st) == 1 and st[0].floor_y == 0.0 and len(st[0].parts) == 6
