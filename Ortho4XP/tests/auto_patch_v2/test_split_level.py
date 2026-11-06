"""SPLIT-LEVEL BUILDINGS (owner 2026-11-05; #1886, #1905): a building closed
at its upper level with an open lower wall inside the terrain gets its pit
at the lower floor, its floor following the open side's rim
(``airport/split_level``, ``planar/split_level_pit``,
``constraints/structures._split_floor_rows``); an upper FLOOR over lower
ground is no level of the lot it overlooks (``classify/storey_edge.
ground_confirms``).  Synthetic: no pack, no airport."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.airport.split_level import _side_feet, read_split_levels, wall_box
from auto_patch_v2.classify.storey_edge import StoreyBand, ground_confirms
from auto_patch_v2.constraints.structures import _split_floor_rows
from auto_patch_v2.law import Law
from shapely.geometry import LineString, box

LAW = Law.for_airport("SYNT")


def _quad(v, t, p0, p1, y0, y1, out):
    """A wall quad from plan p0 to p1, y0..y1, wound so its OBJ8 normal
    (``-(b - a) x (c - a)``) points along ``out``."""
    i = len(v)
    v += [(p0[0], y0, p0[1]), (p1[0], y0, p1[1]), (p1[0], y1, p1[1]), (p0[0], y1, p0[1])]
    for tri in ((i, i + 1, i + 2), (i, i + 2, i + 3)):
        a, b, c = (np.array(v[k]) for k in tri)
        n = -np.cross(b - a, c - a)
        t.append(tri if n[0] * out[0] + n[2] * out[1] >= 0.0 else tri[::-1])


def _building(open_below: float):
    """A 40 x 30 m box, walls y 0..24 on three sides; the +z side's wall
    starts at ``open_below`` (open under it)."""
    v: list = []
    t: list = []
    _quad(v, t, (0, 0), (40, 0), 0.0, 24.0, (0, -1))            # -z
    _quad(v, t, (40, 0), (40, 30), 0.0, 24.0, (1, 0))           # +x
    _quad(v, t, (0, 30), (0, 0), 0.0, 24.0, (-1, 0))            # -x
    _quad(v, t, (40, 30), (0, 30), open_below, 24.0, (0, 1))    # +z
    return np.array(v, float), np.array(t, int)


def test_the_open_side_foot_is_the_upper_floor():
    v, t = _building(12.0)
    cs = wall_box(v, t)
    feet = _side_feet(v, t, [(cs[i], cs[(i + 1) % 4]) for i in range(4)], 3.0, 0.5)
    assert sorted(f for f in feet if f is not None) == [0.0, 0.0, 0.0, 12.0]


def _placed(v, t):
    geom = types.SimpleNamespace(vertices=v, solid=t, animated=np.zeros(0, bool))
    cache = types.SimpleNamespace(geometry=lambda _p: geom)
    o = types.SimpleNamespace(id="dsf:obj1", path="b/split.obj", resolved="b/split.obj",
                              xy=(0.0, 0.0), heading_deg=0.0)
    return [o], cache


def test_a_split_level_building_is_read_where_the_open_side_faces_higher_ground():
    objs, cache = _placed(*_building(12.0))
    # frame north = -z: the open (+z) side lies SOUTH; the ground rises southward
    sls, _notes = read_split_levels(objs, cache, LAW, lambda x, y: 100.0 - 0.6 * y)
    assert len(sls) == 1 and sls[0].y_lo == 0.0 and sls[0].y_up == 12.0
    assert len(sls[0].open_sides) == 1 and sls[0].ground_open_m > sls[0].ground_closed_m


def test_an_open_side_on_level_ground_is_no_split_level():
    objs, cache = _placed(*_building(12.0))                   # a hangar door
    assert read_split_levels(objs, cache, LAW, lambda x, y: 100.0)[0] == []


def test_a_closed_building_is_no_split_level():
    objs, cache = _placed(*_building(0.0))
    assert read_split_levels(objs, cache, LAW, lambda x, y: 100.0 - 0.6 * y)[0] == []


def test_the_floor_is_one_level_under_the_open_rim_and_grades_its_bare_rim():
    rows = _split_floor_rows([10, 11, 12], [1, 2], [3], 12.0, ("basin:0",))
    tie = rows[0]
    assert tie.lo == tie.hi == -12.0 and dict(tie.terms) == {10: 1.0, 1: -0.5, 2: -0.5}
    assert all(r.lo == r.hi == 0.0 for r in rows[1:3])
    assert rows[3].lo == rows[3].hi == 12.0 and dict(rows[3].terms) == {3: 1.0, 10: -1.0}


class _Dem:
    def __init__(self, f):
        self.z = f


def _band(dem):
    air = box(0.0, -50.0, 100.0, 0.0)
    return StoreyBand(box(0.0, 0.0, 100.0, 5.0), (), 0.5, air, dem, 3.0)


def test_an_upper_floor_over_lower_ground_is_no_level_of_the_lot():
    lot, run = box(0.0, 0.0, 100.0, 40.0), LineString([(0.0, 0.0), (100.0, 0.0)])
    # the landside 6 m UNDER the apron: an 11.6 m hall is a floor, not ground
    assert ground_confirms(_band(_Dem(lambda x, y: 790.0 - 6.0 * (y > 0))), lot, run,
                           11.6) is False
    # the forecourt a storey up: the storey is the lot's level
    assert ground_confirms(_band(_Dem(lambda x, y: 28.6 + 5.4 * (y > 0))), lot, run,
                           6.0) is True
    assert ground_confirms(_band(None), lot, run, 6.0) is None


def test_back_cut_reaches_past_the_tall_sides_only():
    """THE BACK IS CUT DOWN (owner sim read 2026-11-05T23:55Z): the pit
    reaches ``split_level_back_cut_m`` outside the three tall sides (the
    corners between them taken), never past the open (airside) side, and
    yields to what is blocked."""
    from auto_patch_v2.airport.split_level import SplitLevel
    from auto_patch_v2.planar.split_level_pit import _cut_region
    from shapely.geometry import Point
    foot = box(0.0, 0.0, 10.0, 10.0)
    open_ = (LineString([(0.0, 10.0), (10.0, 10.0)]),)
    tall = (LineString([(10.0, 10.0), (10.0, 0.0)]), LineString([(10.0, 0.0), (0.0, 0.0)]),
            LineString([(0.0, 0.0), (0.0, 10.0)]))
    sl = SplitLevel("o", ("o",), ("a.obj",), foot, 0.0, 6.0, open_, tall, 6.0, 0.0,
                    (5.0, 5.0))
    region = _cut_region(sl, 5.0, None)
    assert abs(region.area - 300.0) < 1e-6
    assert region.contains(Point(-4.0, -4.0)) and region.contains(Point(12.0, 9.0))
    assert not region.contains(Point(5.0, 11.0))          # the airside: no reach
    assert _cut_region(sl, 0.0, None).equals(foot)
    clipped = _cut_region(sl, 5.0, box(-10.0, -10.0, 20.0, -2.0))
    assert abs(clipped.area - (300.0 - 60.0)) < 1e-6


def test_the_map_confirms_a_split_level_the_flat_dem_cannot_see():
    """THE MAP WITNESS (owner 2026-11-05/06, SBSP's hangar row): on a DEM
    too flat to show the step, the open side facing airside pavement and
    the low side across not facing it read the building; airside behind
    it, or on both sides, or a low side's ground half a step higher, does
    not."""
    from shapely.prepared import prep
    objs, cache = _placed(*_building(12.0))
    south = prep(box(-50.0, -80.0, 90.0, -31.0))   # the open (+z) side lies south
    north = prep(box(-50.0, 1.0, 90.0, 60.0))
    both = prep(box(-50.0, -80.0, 90.0, 60.0))
    flat = lambda x, y: 100.0                      # noqa: E731
    sls, notes = read_split_levels(objs, cache, LAW, flat, south)
    assert len(sls) == 1 and "by the map" in notes[0]
    assert read_split_levels(objs, cache, LAW, flat, north)[0] == []
    assert read_split_levels(objs, cache, LAW, flat, both)[0] == []
    assert read_split_levels(objs, cache, LAW, lambda x, y: 100.0 + 0.3 * y, south)[0] == []


def test_one_tall_side_and_airside_clip_the_back_cut():
    """One tall side unions to a LineString (linemerge refused it and
    crashed KLAX); the back cut never enters what is passed as blocked
    (the pit passes airside pavement there), and a box clipped by a
    neighbour's pit is the region's core."""
    from auto_patch_v2.airport.split_level import SplitLevel
    from auto_patch_v2.planar.split_level_pit import _cut_region
    foot = box(0.0, 0.0, 10.0, 10.0)
    sl = SplitLevel("o", ("o",), ("a.obj",), foot, 0.0, 6.0,
                    (LineString([(0.0, 10.0), (10.0, 10.0)]),),
                    (LineString([(10.0, 0.0), (0.0, 0.0)]),), 6.0, 0.0, (5.0, 5.0))
    assert abs(_cut_region(sl, 5.0, None).area - 150.0) < 1e-6
    assert abs(_cut_region(sl, 5.0, box(-1.0, -9.0, 4.0, 0.0)).area - 130.0) < 1e-6
    core = box(0.0, 0.0, 6.0, 10.0)
    assert abs(_cut_region(sl, 5.0, None, core).area - (60.0 + 50.0)) < 1e-6
