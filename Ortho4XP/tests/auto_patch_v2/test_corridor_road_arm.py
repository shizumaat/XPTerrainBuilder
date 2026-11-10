"""#1728 (owner 2026-10-31, KBWI ``dsf:pol177``): a service road hanging
off a taxiway page is the road, not a taxiway stub.

The ladder reads the page by its mean width along the taxi centreline and
calls the whole of it a corridor.  ``neck.road_arms`` reads §43 (1)'s arm
off the corridor's own ROUTE TERRITORY instead: road-wide pavement that
leaves it across a cross-section, follows a path and carries a road
centreline is cut at its mouth (the #1877 verdict then names it a road).
"""
from __future__ import annotations

from auto_patch_v2.classify.neck import road_arms, split_at_necks
from auto_patch_v2.classify.rules import load_rules
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union


def _page(arm_w: float = 9.0, spike: bool = False):
    """A 20 m x 400 m taxiway (centreline y=10) and, off its north side
    at x 200, a 150 m road arm ``arm_w`` wide; ``spike`` adds a zero-width
    wedge of pack ring along the taxiway's edge from the arm's root."""
    taxi = box(0.0, 0.0, 400.0, 20.0)
    arm = box(200.0, 20.0, 200.0 + arm_w, 190.0)
    face = unary_union([taxi, arm])
    if spike:
        x0 = 200.0 + arm_w
        face = unary_union([face, Polygon([(x0, 60.0), (x0, 61.5),
                                           (x0 + 140.0, 40.0)])])
    centre = LineString([(0.0, 10.0), (400.0, 10.0)])
    road = LineString([(200.0 + arm_w / 2.0, 0.0), (200.0 + arm_w / 2.0, 300.0)])
    return face, centre, road


def test_the_road_arm_is_cut_at_its_mouth():
    rules = load_rules()
    face, centre, road = _page()
    arms = road_arms(face, [centre], [road], rules)
    assert len(arms) == 1 and arms[0].kind == "arm"
    pieces = split_at_necks(face, arms, rules)
    arm = [p for p, is_arm in pieces if is_arm]
    rest = [p for p, is_arm in pieces if not is_arm]
    assert len(arm) == 1 and len(rest) == 1
    # the mouth is where the route territory ends, 25 m off the centreline
    assert abs(arm[0].bounds[1] - (10.0 + rules.junction.route_territory_half_width_m)) < 1.0


def test_no_road_no_cut():
    rules = load_rules()
    face, centre, _road = _page()
    assert road_arms(face, [centre], [], rules) == []
    off = LineString([(100.0, 100.0), (100.0, 300.0)])      # a road elsewhere
    assert road_arms(face, [centre], [off], rules) == []


def test_a_wide_arm_is_not_a_road():
    """Wider than ``apron.arm_road_max_width_m`` (#1877): not road-wide."""
    rules = load_rules()
    face, centre, road = _page(arm_w=rules.apron.arm_road_max_width_m + 6.0)
    assert road_arms(face, [centre], [road], rules) == []


def test_a_spike_stays_out_of_the_road():
    """A zero-width wedge riding on the arm is cut off at its base, so its
    run along the taxiway is never the road's lateral airside contact."""
    rules = load_rules()
    face, centre, road = _page(spike=True)
    arms = road_arms(face, [centre], [road], rules)
    assert len(arms) == 1
    arm = [p for p, is_arm in split_at_necks(face, arms, rules) if is_arm]
    assert len(arm) == 1 and arm[0].bounds[2] < 200.0 + 9.0 + 2.0
