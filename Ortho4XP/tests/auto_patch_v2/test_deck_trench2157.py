"""#2157 KRDU taxiway E (spec ``docs/specs/2157-krdu-trench-spec.md``): a
walled deck's floor stays under its OWN ring between its own opening's wall
pair (R2, F1), and the at-grade plan of a deck cut to its spans is pavement
only on the mapped airside (R1/R4, F3).  Synthetic frames; no pack."""
from __future__ import annotations

import types

import pytest
from shapely.geometry import box

from auto_patch_v2.geom.wall_lines import inner_faces
from auto_patch_v2.model.deck_bank import banked
from auto_patch_v2.planar import deck_bridge as DB
from auto_patch_v2.planar.deck_span_cut import _on_airside

# a two-span frame along the road (u across it): the W span's walls at
# u = -275 (whole) and -224 (40 m long, 0.3 m out of straight: two bins),
# the E span's at +161 / +185 -- the plan is 69 m along the road
FACES = ((-275.0, 0.0, 69.0),
         (-224.0, 0.0, 31.8), (-224.3, 31.8, 40.1),
         (161.0, 0.0, 69.0), (185.0, 0.0, 69.0))
W_RING = ((-290.0, 0.0), (-210.0, 0.0), (-210.0, 69.0), (-290.0, 69.0))


def test_without_its_reach_the_far_spans_wall_is_taken():
    """The old reading (no reach): the W span's own east wall covers 46 %
    of the plan in its larger bin and is refused -- the next line east is
    the E span's wall 436 m away (the measured KRDU pit)."""
    assert inner_faces(FACES, 0.0, 69.0, -250.0) == (-275.0, 161.0)


def test_a_span_takes_its_own_walls_within_its_reach():
    """R2 / F1 (a)+(b): only faces within the ring's reach are its walls;
    a wall shorter than the plan and a hair out of straight is a wall."""
    ua, ub = inner_faces(FACES, 0.0, 69.0, -250.0, (-290.0, -210.0))
    assert ua == -275.0 and ub == pytest.approx(-224.15)


def test_a_side_with_no_wall_in_reach_is_none():
    """F1 (a): the 30b bank stands where the ring's reach holds no wall."""
    faces = tuple(f for f in FACES if f[0] > -250.0)
    ua, ub = inner_faces(faces, 0.0, 69.0, -250.0, (-290.0, -210.0))
    assert ua is None and ub is not None
    assert DB._walled_trench(types.SimpleNamespace(
        walls=((0.0, 1.0), (1.0, 0.0), faces), ring=W_RING), 0.6) is None


def test_a_wall_line_passing_alone_keeps_its_own_line():
    """F1 (b) only ADDS walls: a bin covering the stretch alone keeps its
    exact line (KBNA's walled floor is unchanged)."""
    faces = ((-10.0, 0.0, 30.0), (-10.4, 0.0, 30.0), (10.0, 0.0, 30.0))
    assert inner_faces(faces, 0.0, 30.0, 0.0, (-12.0, 12.0)) == (-10.0, 10.0)


def _span(ring=W_RING):
    return types.SimpleNamespace(walls=((0.0, 1.0), (1.0, 0.0), FACES), ring=ring)


def test_the_floor_stays_under_its_own_ring():
    """R2 / F1 (c): the W span's floor is its own opening (51 m x 69 m),
    never the 436 m strip to the other span's wall."""
    floor, _rim = DB._walled_trench(_span(), 0.6)
    x0, y0, x1, y1 = floor.bounds
    assert (x0, y0, y1) == (-275.0, 0.0, 69.0) and x1 == pytest.approx(-224.15)
    assert not banked(_span())


def test_a_plan_wider_than_its_taxiway_is_pavement_only_on_it():
    """R1/R4 / F3: an 89 m at-grade plan over a mapped taxi route is
    pavement over the route's width and the zone-1 lip; the rest is the
    ground beside the taxiway."""
    from auto_patch_v2.law import Law
    from auto_patch_v2.law.tables import taxi_half_width_m
    law = Law.for_airport("ZZZZ")
    node = types.SimpleNamespace
    airport = types.SimpleNamespace(
        pavements=(), runways=(),
        taxi_nodes={1: node(xy=(-50.0, 0.0)), 2: node(xy=(250.0, 0.0))},
        taxi_edges=(node(a=1, b=2),))
    plan = box(0.0, -39.0, 200.0, 50.0)
    got = _on_airside(plan, airport, law, plan)
    half = taxi_half_width_m(law, None) + float(law.tables.zones.adjacent_ground.lip_width_m)
    assert got.bounds == pytest.approx((0.0, -half, 200.0, half))
    no_route = types.SimpleNamespace(pavements=(), runways=(), taxi_nodes={}, taxi_edges=())
    assert _on_airside(plan, no_route, law, plan).equals(plan)


def test_a_wall_pair_over_a_road_in_an_at_grade_stretch_is_a_span():
    """#2157 R3 (``deck_span_cut._wall_spans``): two facing wall lines of
    the frame inside a stretch the survey read at grade, a mapped road
    crossing between them and ground more than a storey under the crest on
    both flanks, are a span; without the drop on a flank they are not."""
    import types

    from shapely.geometry import Polygon

    from auto_patch_v2.geom.deck_spans import SpanCut
    from auto_patch_v2.planar.deck_span_cut import _wall_spans
    piece = Polygon([(0, -20), (300, -20), (300, 20), (0, 20)])
    cut = SpanCut((0.0, 0.0), (300.0, 0.0), ((40.0, 80.0),))
    faces = tuple((u, -20.0, 20.0) for u in (40.0, 80.0, 200.0, 212.0))

    def walls(r, n):
        return (0.0, 1.0), (1.0, 0.0), faces

    def airport(low):
        dem = types.SimpleNamespace(z=lambda x, y: 120.0 if abs(y) <= 20.0 else low)
        road = types.SimpleNamespace(points=[(206.0, -60.0), (206.0, 60.0)],
                                     tags={"highway": "service", "tunnel": "yes"})
        return types.SimpleNamespace(dem=dem, osm_ways=[road])
    assert _wall_spans(cut, walls, airport(112.0), piece, 3.0) == ((200.0, 212.0),)
    assert _wall_spans(cut, walls, airport(118.0), piece, 3.0) == ()
