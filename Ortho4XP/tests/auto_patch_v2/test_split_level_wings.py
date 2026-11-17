"""THE UPPER WING OF A SPLIT-LEVEL BUILDING (#1934 R5; owner sim read
2026-11-17T05:18Z, KLAX Terminal 8: "There's no pit there ... sitting on the
apron"): the part of the plan an arc of upper-footed walls holds between
itself and its chord stands on the upper level -- in the storey plans and
under the pit (``airport/split_level_wings``, ``airport/split_level.
_level_plans``, ``planar/split_level_pit._lower_plan``).  A straight upper
arc (one open side) holds nothing.  Synthetic: no pack, no airport."""
from __future__ import annotations

from auto_patch_v2.airport.split_level import SplitLevel, _level_plans
from auto_patch_v2.airport.split_level_wings import _arcs, upper_wings
from auto_patch_v2.planar.split_level_pit import _upper_wing, _wing_edges
from shapely.geometry import LineString, Point, Polygon, box

#: a 40 x 30 block (y 0..30) with a 10 m wide wing running 40 m south of
#: its west end; the wing's walls and the block's west face stand on the
#: upper level (1), the block's south, east and north walls on the lower (0)
_PLAN = Polygon([(0, -40), (10, -40), (10, 0), (40, 0), (40, 30), (0, 30)])
_RUNS = [((0, -40), (10, -40)), ((10, -40), (10, 0)), ((10, 0), (40, 0)),
         ((40, 0), (40, 30)), ((40, 30), (0, 30)), ((0, 30), (0, -40))]
_NORMALS = [(0, -1), (1, 0), (0, -1), (1, 0), (0, 1), (-1, 0)]
_LEVELS = [1, 1, 0, 0, 0, 1]


def test_arcs_fill_unread_runs_and_fold_slivers_into_their_neighbours():
    assert sorted(_arcs([0, None, 0, 1, 1, None])) == [(0, [0, 1, 2]), (1, [3, 4, 5])]
    assert _arcs([0, 0, None]) == []                   # one level: no arcs
    lengths = [20.0, 1.0, 20.0, 30.0]
    # the 1 m upper run is a corner's sliver: it joins the lower arc
    assert sorted(_arcs([0, 1, 0, 1], lengths, 3.0)) == [(0, [0, 1, 2]), (1, [3])]


def test_an_upper_arc_holds_the_plan_between_itself_and_its_chord():
    wings = upper_wings(_PLAN, _RUNS, _LEVELS, 3.0)
    assert set(wings) == {1}
    # the wing, and the sliver of block west of the chord (0,30)-(10,0)
    assert abs(wings[1].area - (400.0 + 150.0)) < 1e-6
    assert wings[1].contains(box(1, -39, 9, -1))
    assert not wings[1].intersects(box(15, 5, 35, 25))


def test_a_straight_open_side_holds_nothing():
    """A building cut into a slope with one open side, its open wall in two
    collinear runs: the chord is the arc, the whole plan stays lower."""
    plan = box(0, 0, 40, 30)
    runs = [((0, 0), (40, 0)), ((40, 0), (40, 30)), ((40, 30), (20, 30)),
            ((20, 30), (0, 30)), ((0, 30), (0, 0))]
    assert upper_wings(plan, runs, [0, 0, 1, 1, 0], 3.0) == {}


def test_the_wing_takes_the_upper_level_not_the_lowest_it_touches():
    """Spec 2062 A1 (1) (c) handed the wing's interior to the LOWEST level
    it touched (the block's); the wing's own walls witness the upper one."""
    p0, p1 = _level_plans(_PLAN, (0.0, 4.0), _RUNS, _NORMALS, _LEVELS, 3.0, 3.0)
    assert p1.contains(box(1, -39, 9, -1))
    assert p0.contains(box(15, 5, 35, 25))
    assert abs(p0.area + p1.area - _PLAN.area) < 1e-6


def _record(levels):
    runs = tuple((LineString([p0, p1]), 0.0 if k == 0 else 4.0)
                 for (p0, p1), k in zip(_RUNS, levels, strict=True))
    return SplitLevel("o", ("o",), ("a.obj",), _PLAN.envelope, 0.0, 4.0, (), (), 4.0, 0.0,
                      (20.0, 15.0), _PLAN, runs=runs, levels=(0.0, 4.0),
                      run_levels=tuple(levels))


def test_the_pit_holds_its_upper_wing_at_the_upper_floor():
    """The pit pass takes the wing out of the floor and publishes the
    wing's edge inside the pit as one more open side (its rim held at the
    upper floor)."""
    wing = _upper_wing(_record(_LEVELS), 3.0)
    assert abs(wing.area - 550.0) < 1e-6
    edges = _wing_edges(wing, _PLAN, 0.25)
    assert len(edges) == 1
    # the chord, less the grid at its ends
    assert abs(edges[0].length - LineString([(0, 30), (10, 0)]).length) < 1.5
    assert edges[0].distance(Point(5.0, 15.0)) < 1e-6


def test_a_building_its_upper_walls_hold_whole_has_no_pit():
    """Every wall but one face footed on the upper level: the low face is a
    facade down to the ground beyond it, the building stands on its upper
    ground (the pit pass refuses it by name)."""
    wing = _upper_wing(_record([1, 1, 1, 1, 0, 1]), 3.0)
    assert _PLAN.difference(wing).area < 1e-6
