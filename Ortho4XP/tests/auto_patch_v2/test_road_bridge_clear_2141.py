"""Twins of #2141 items 4 and 5: the clearance under a generated road bridge
(``planar/road_bridge_clear``: the ends on the embankments the survey
shows, the lower roads cut by the rest, the survey's witness), the cut
(``airport/road_bridge_ground``) and the bank under a generated deck
(``constraints/edge_deck._bank_drop``).  Synthetic frames, no capture."""
from __future__ import annotations

import dataclasses as dc
import types

import numpy as np
from auto_patch_v2.airport.road_bridge_ground import clearance_ground, clearance_ribbons
from auto_patch_v2.law.tables import load_default
from auto_patch_v2.planar.road_bridge_clear import (
    clearance_plan,
    deck_at,
    _end_level,
    span_cuts,
    witnessed,
)
from shapely.geometry import LineString, Point

LAW = load_default()


@dc.dataclass(frozen=True)
class _Way:
    id: str
    points: tuple
    tags: dict


class _Dem:
    """Ground at 20 m; ``rise(x, y)`` added."""

    def __init__(self, rise):
        self.rise = rise

    def z(self, x, y):
        return 20.0 + self.rise(float(x), float(y))


def _airport(rise, lower_dip=0.0, lower_tags=None):
    """A 100 m bridge along x (0..100) at y=0, layer 1, over a lower road
    along y at x=60; approaches run on along x past each end."""
    bridge = _Way("-1", ((0.0, 0.0), (100.0, 0.0)), {"highway": "service", "bridge": "yes",
                                                      "layer": "1"})
    west = _Way("-2", ((0.0, 0.0), (-80.0, 0.0)), {"highway": "service"})
    east = _Way("-3", ((100.0, 0.0), (180.0, 0.0)), {"highway": "service"})
    low = _Way("-4", ((60.0, -80.0), (60.0, 80.0)), lower_tags or {"highway": "secondary"})

    def z(x, y):
        dip = -lower_dip if abs(x - 60.0) < 8.0 else 0.0
        return rise(x, y) + dip
    return types.SimpleNamespace(osm_ways=(bridge, west, east, low), dem=_Dem(z)), bridge, low


def _plan(ap, bridge, low):
    line = LineString(bridge.points)
    q = line.intersection(LineString(low.points))
    return clearance_plan(ap, LAW, bridge, line, [(low.id, LineString(low.points), q, low.tags)])


def _ground(ap, bridge, low, plan, half=8.0):
    """The cut under the span (``span_cuts``), the span ``half`` each side."""
    line = LineString(bridge.points)
    q = line.intersection(LineString(low.points))
    span = line.buffer(half, cap_style="flat")
    return span_cuts(ap, LAW, line, plan.levels, [(low.id, LineString(low.points), q, low.tags)],
                     span)


def test_end_stands_on_the_embankment_beyond_a_mapped_end():
    # the approach climbs 5 m in its first 20 m, then runs level: the end
    # stands as high as that less the service road's cap back to it
    cap = 0.1
    ap = LineString([(0, 0), (30, 0)])
    dem = _Dem(lambda x, _y: min(5.0, 0.25 * x))
    level, on, knee = _end_level(dem, [ap], cap)
    assert on is ap and abs(knee - 20.0) < 1e-6 and abs(level - 23.0) < 1e-6
    # an approach climbing at a lawful grade raises nothing
    level, on, _k = _end_level(_Dem(lambda x, _y: 0.05 * x), [ap], cap)
    assert on is None and abs(level - 20.0) < 1e-9


def test_raised_ends_witness_the_bridge_and_nothing_is_cut():
    # the east approach reaches a plateau 6 m up 20 m past the end
    ap, bridge, low = _airport(lambda x, _y: min(6.0, max(0.0, 0.3 * (x - 100.0))) - 2.0
                               * (1.0 if 10 < x < 90 else 0.0))
    plan = _plan(ap, bridge, low)
    assert plan is not None and plan.levels[1] > plan.ends[1] + 3.0
    assert witnessed(plan, LAW) and plan.witnessed >= 4.2 and not plan.ground
    # the chain runs on along the east approach to the crest; the west end
    # stands on its own survey
    assert plan.chain.coords[0] == (0.0, 0.0) and plan.chain.coords[-1][0] > 110.0


def test_the_lower_road_takes_the_rest_as_a_cut():
    # flat approaches, the lower road (a secondary: [tunnel] clearance_m
    # 5.0) already 2.5 m down: 2.5 m is cut, all the way under the span
    ap, bridge, low = _airport(lambda _x, _y: 0.0, lower_dip=2.5)
    plan = _plan(ap, bridge, low)
    assert witnessed(plan, LAW) and not plan.ground
    (cut,) = [g for g in _ground(ap, bridge, low, plan) if g["kind"] == "cut"]
    prof = cut["prof"]
    flat = [s for s, z in prof if abs(z - 15.0) < 1e-6]
    assert abs(min(z for _s, z in prof) - 15.0) < 1e-6
    # the floor runs the carriageway's whole reach under the 16 m span
    assert max(flat) - min(flat) >= 16.0


def test_a_small_road_clears_by_the_minimum():
    # owner 2026-11-17T19:08Z: 4.2 m for a small road -- 1.7 m is cut
    ap, bridge, low = _airport(lambda _x, _y: 0.0, lower_dip=2.5,
                               lower_tags={"highway": "service"})
    plan = _plan(ap, bridge, low)
    (cut,) = _ground(ap, bridge, low, plan)
    assert abs(min(z for _s, z in cut["prof"]) - (20.0 - 4.2)) < 1e-6


def test_the_cut_follows_a_sloping_deck_under_the_span():
    # the deck rises 1:20 along x and the lower road crosses it obliquely:
    # every station under the span stands its clearance under the deck
    # above it, never only the crossing's
    ap, bridge, low = _airport(lambda x, _y: 0.05 * x - (3.0 if 20 < x < 80 else 0.0))
    low = _Way("-4", ((30.0, -40.0), (90.0, 40.0)), {"highway": "service"})
    ap = types.SimpleNamespace(osm_ways=(*ap.osm_ways[:3], low), dem=ap.dem)
    plan = _plan(ap, bridge, low)
    assert witnessed(plan, LAW)
    (cut,) = _ground(ap, bridge, low, plan)
    axis, line = LineString(cut["axis"]), LineString(bridge.points)
    for s, z in cut["prof"]:
        p = axis.interpolate(s)
        if abs(p.y) <= 8.0:
            # the profile is rounded to 0.1 mm
            assert z <= deck_at(plan.levels, line.length, line.project(p)) - 4.2 + 1e-3


def test_an_at_grade_crossing_is_no_witness():
    # an elevated ramp the survey carries at grade over an at-grade road
    ap, bridge, low = _airport(lambda _x, _y: 0.0)
    assert not witnessed(_plan(ap, bridge, low), LAW)
    # an approach reading 10 m up within 30 m is a structure, not an
    # embankment: the end stays on its own survey
    ap, bridge, low = _airport(lambda x, _y: min(10.0, max(0.0, x - 100.0)))
    plan = _plan(ap, bridge, low)
    assert plan.levels == plan.ends and not witnessed(plan, LAW)


def test_the_lower_road_is_cut_off_the_airside():
    ap, bridge, low = _airport(lambda _x, _y: 0.0, lower_dip=2.5)
    plan = _plan(ap, bridge, low)
    rec = types.SimpleNamespace(road_bridges=({"ground": list(_ground(ap, bridge, low, plan))},))
    rs = clearance_ribbons(rec)
    xs = np.array([60.0, 60.0, 0.0])
    ys = np.array([0.0, 2.0, 40.0])
    zs = np.array([17.5, 17.5, 20.0])
    out, rep = clearance_ground(rs, xs, ys, zs, airside={1})
    assert abs(out[0] - 15.0) < 1e-6 and out[1] == 17.5 and out[2] == 20.0
    assert rep.cut == 1 and abs(rep.max_cut_m - 2.5) < 1e-6


def test_a_generated_deck_s_span_stands_on_its_bank():
    from auto_patch_v2.constraints.edge_deck import _bank_drop
    e = types.SimpleNamespace(line=((0.0, 0.0), (40.0, 0.0)), depth=6.0)
    assert _bank_drop([e], Point(20.0, 3.0), 0.33) == 0.33 * 3.0
    assert _bank_drop([e], Point(20.0, 30.0), 0.33) == 6.0       # the floor beyond the toe
    assert _bank_drop([], Point(0.0, 0.0), 0.33) == 0.0
