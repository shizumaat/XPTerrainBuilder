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


def _necked(road_y: float | None = 80.0):
    """#1900 (owner RULINGS 2026-11-10l, HECA ``dsf:objpav99``): two
    taxiway lobes (centrelines y=10) joined by a 9 m pavement NECK that
    climbs out of their route territory and runs 500 m along y 60-69, no
    centreline on it; a mapped road beside it at ``road_y`` (11 m off its
    edge at 80), over the middle 200 m of its run."""
    a, b = box(0.0, 0.0, 200.0, 20.0), box(600.0, 0.0, 800.0, 20.0)
    neck = unary_union([box(150.0, 20.0, 159.0, 69.0),
                        box(150.0, 60.0, 650.0, 69.0),
                        box(641.0, 20.0, 650.0, 69.0)])
    face = unary_union([a, b, neck])
    centres = [LineString([(0.0, 10.0), (200.0, 10.0)]),
               LineString([(600.0, 10.0), (800.0, 10.0)])]
    roads = [] if road_y is None else \
        [LineString([(300.0, road_y), (500.0, road_y)])]
    return face, centres, roads


def test_a_neck_a_road_runs_beside_is_the_road():
    rules = load_rules()
    face, centres, roads = _necked()
    necks = road_arms(face, centres, roads, rules)
    assert [n.kind for n in necks] == ["neck"]
    pieces = split_at_necks(face, necks, rules)
    assert sum(1 for _p, is_neck in pieces if is_neck) == 1


def test_a_neck_with_no_road_beside_it_stays():
    rules = load_rules()
    face, centres, _ = _necked(road_y=None)
    assert road_arms(face, centres, [], rules) == []
    # a road more than one road width off the neck's far edge is not beside it
    face, centres, roads = _necked(road_y=69.0 + 9.0 + rules.apron.arm_road_max_width_m + 5.0)
    assert road_arms(face, centres, roads, rules) == []


def test_a_road_neck_is_never_flipped_by_section_27():
    """§27 must not flip the road neck to apron (RULINGS 2026-11-10l)."""
    from auto_patch_v2.classify.airside_edge import _road_neck
    neck = {"arm_road": 1.0, "corridor_road_arm": 1.0, "neck_kind": "neck"}
    assert _road_neck(neck)
    assert not _road_neck(dict(neck, neck_kind="arm"))     # #1728 unchanged
    assert _road_neck(dict(neck, neck_kind="arm", neck_road_beside=1.0))  # 11e (1a)
    assert not _road_neck({"arm_road": 1.0, "neck_kind": "neck"})


def test_a_neck_a_road_runs_beside_reads_the_free_road_width():
    """RULINGS 2026-11-11e (1a), HECA: a strip a mapped road runs beside is
    read against the free-road width (``service.free_max_width_m``), not
    the #1877 12 m arm-road cap; with no road beside it the cap stands."""
    from auto_patch_v2.classify.neck import road_beside
    rules = load_rules()
    cap, free = rules.apron.arm_road_max_width_m, rules.service.free_max_width_m
    w = (cap + free) / 2.0                    # wider than the cap, a free road
    strip = box(0.0, 0.0, 200.0, w)
    road = LineString([(0.0, w + 5.0), (200.0, w + 5.0)])
    assert road_beside(strip, w, road, rules)
    assert not road_beside(strip, w, None, rules)
    far = LineString([(0.0, 2 * w + cap + 5.0), (200.0, 2 * w + cap + 5.0)])
    assert not road_beside(strip, w, far, rules)
    wide = box(0.0, 0.0, 200.0, free + 1.0)
    assert not road_beside(wide, free + 1.0, road, rules)


def test_an_arm_a_road_runs_beside_reads_the_free_road_width():
    """#1900 (RULINGS 2026-11-11e (1a)): an arm wider than the 12 m cap with
    a mapped road BESIDE it (not down it) is a road arm, flagged so the
    arm-road verdict reads it against the free-road width; a road running
    DOWN an arm that wide still is not (#1728 unchanged)."""
    rules = load_rules()
    w = rules.apron.arm_road_max_width_m + 2.0
    face, centre, _down = _page(arm_w=w)
    beside = LineString([(200.0 + w + 6.0, 40.0), (200.0 + w + 6.0, 300.0)])
    arms = road_arms(face, [centre], [beside], rules)
    assert len(arms) == 1 and arms[0].kind == "arm" and arms[0].road_beside
    assert road_arms(face, [centre], [_down], rules) == []


def test_the_arm_road_width_bar():
    from auto_patch_v2.classify.roles import _road_wide
    rules = load_rules()
    cap, free = rules.apron.arm_road_max_width_m, rules.service.free_max_width_m
    assert _road_wide({"neck_width_m": cap}, rules)
    assert not _road_wide({"neck_width_m": cap + 0.3}, rules)
    assert _road_wide({"neck_width_m": cap + 0.3, "neck_road_beside": 1.0}, rules)
    assert not _road_wide({"neck_width_m": free + 0.1, "neck_road_beside": 1.0}, rules)
