"""OPT-1 correctness pin — the STRtree two-nearest-parent index.

``gap_fill`` used to pick the two bounding pavement parents of a station
by scanning EVERY airside shape and calling
``s.polygon.exterior.distance(p)`` (three call sites: ``_spine_interval``,
``_build_collar_rings._point_interval``, ``_freeze_spine_parent_specs``).
That scan is now answered by ``_AirsideNearestIndex`` — hoisted exteriors
+ an STRtree bbox prefilter with a DOUBLING radius.

This is a pure OPTIMISATION: the selection must be bit-identical to the
old scan, tie order included.  The old scan sorted by DISTANCE ONLY with
Python's stable sort, so equal distances resolved to the original
``airside`` order; the index therefore has to rank by
``(distance, original airside index)``.  Ties are not exotic here — a
station equidistant from two mirrored rects, or sitting ON two touching
pavement rings (d == 0.0 for both), happens all over a real apron.

Every test below compares against the brute-force scan VERBATIM, on
randomised fixtures that deliberately manufacture ties, coincident
shapes, zero distances and far-away shapes (which force the radius to
double several times).
"""
import random

import pytest
from shapely.geometry import Point, Polygon

from auto_patch.gap_fill import (
    _GEOM_EXC, _AirsideNearestIndex, _airside_index)


class _Shape:
    """Minimal ``BuiltShape`` stand-in — the index reads ``.polygon``."""

    def __init__(self, polygon):
        self.polygon = polygon


def _brute_two_nearest(airside, p):
    """The scan this optimisation replaced, copied VERBATIM from
    ``gap_fill._spine_interval`` (pre-OPT-1) so the pin cannot drift with
    a later edit of the production path."""
    cands = []
    for s in airside:
        try:
            d = s.polygon.exterior.distance(p)
        except _GEOM_EXC:
            continue
        cands.append((d, s))
    cands.sort(key=lambda t: t[0])
    return cands[:2]


def _assert_same(airside, pts):
    """Index result == brute-force result for every point: same shapes,
    same ORDER, same distances (exact float equality — these values feed
    ``adjacent_ground_envelope`` and land in emitted altitudes)."""
    index = _AirsideNearestIndex(airside)
    for px, py in pts:
        p = Point(px, py)
        want = _brute_two_nearest(airside, p)
        got = index.two_nearest(p)
        assert len(got) == len(want), (px, py)
        for (dg, sg), (dw, sw) in zip(got, want):
            assert sg is sw, (px, py, dg, dw)
            assert dg == dw, (px, py)


def _rect(cx, cy, hw, hh):
    return Polygon([(cx - hw, cy - hh), (cx + hw, cy - hh),
                    (cx + hw, cy + hh), (cx - hw, cy + hh)])


# ── randomised fixtures ───────────────────────────────────────────────

@pytest.mark.parametrize("seed", list(range(12)))
def test_matches_brute_force_on_random_layouts(seed):
    """Random rect fields of varying density, queried on a grid + random
    points (including points inside shapes, where several distances are
    exactly 0.0)."""
    rng = random.Random(seed)
    n = rng.choice((2, 3, 5, 17, 60))
    airside = [_Shape(_rect(rng.uniform(-500, 500), rng.uniform(-500, 500),
                            rng.uniform(3, 90), rng.uniform(3, 90)))
               for _ in range(n)]
    pts = [(rng.uniform(-600, 600), rng.uniform(-600, 600))
           for _ in range(120)]
    pts += [(x, y) for x in range(-600, 601, 150)
            for y in range(-600, 601, 150)]
    _assert_same(airside, pts)


@pytest.mark.parametrize("seed", list(range(8)))
def test_ties_are_broken_by_original_airside_order(seed):
    """DUPLICATE shapes: every copy is at the identical distance, so the
    winner is decided purely by list position.  A tie-break on anything
    else (shape id, tree order) shows up here."""
    rng = random.Random(1000 + seed)
    base = [_rect(0.0, 0.0, 20.0, 20.0),
            _rect(120.0, 0.0, 20.0, 20.0),
            _rect(0.0, 120.0, 20.0, 20.0)]
    airside = []
    for poly in base:
        for _ in range(rng.choice((2, 3, 4))):
            # A fresh Polygon with the SAME coordinates: equal distance,
            # distinct object — exactly the tie the stable sort resolved.
            airside.append(_Shape(Polygon(poly.exterior.coords)))
    rng.shuffle(airside)
    pts = [(60.0, 60.0), (0.0, 0.0), (60.0, 0.0), (0.0, 60.0),
           (-40.0, -40.0), (20.0, 20.0), (300.0, 300.0)]
    pts += [(rng.uniform(-200, 300), rng.uniform(-200, 300))
            for _ in range(80)]
    _assert_same(airside, pts)


def test_mirrored_pair_exact_tie():
    """Two rects mirrored about x = 0: every point on the axis is
    exactly equidistant from both.  The first in list order must win."""
    left = _Shape(_rect(-50.0, 0.0, 20.0, 200.0))
    right = _Shape(_rect(50.0, 0.0, 20.0, 200.0))
    for airside in ([left, right], [right, left]):
        pts = [(0.0, y) for y in range(-250, 251, 10)]
        _assert_same(airside, pts)
        index = _AirsideNearestIndex(airside)
        got = index.two_nearest(Point(0.0, 0.0))
        assert got[0][1] is airside[0]
        assert got[1][1] is airside[1]
        assert got[0][0] == got[1][0]


def test_touching_shapes_zero_distance_ties():
    """A station ON a shared pavement edge sits at distance 0.0 from
    several rings at once — the densest tie class in production."""
    airside = [_Shape(_rect(cx, 0.0, 25.0, 25.0))
               for cx in (0.0, 50.0, 100.0, 150.0)]
    pts = [(25.0, 0.0), (75.0, 0.0), (125.0, 0.0), (25.0, 25.0),
           (0.0, 0.0), (75.0, 25.0), (75.0, -25.0)]
    _assert_same(airside, pts)


def test_far_field_forces_radius_doubling():
    """Shapes far outside the seed radius: the query must keep doubling
    until the candidate set is provably sufficient, never settle for the
    empty/short set the seed window returns."""
    rng = random.Random(7)
    airside = [_Shape(_rect(rng.uniform(-30, 30) + 40000.0,
                            rng.uniform(-30, 30), 5.0, 5.0))
               for _ in range(6)]
    pts = [(0.0, 0.0), (-90000.0, 12000.0), (39000.0, 0.0),
           (40000.0, 0.0)]
    _assert_same(airside, pts)


def test_degenerate_populations():
    """0 / 1 / 2 shapes — the short-list edges of ``cands[:2]``."""
    assert _AirsideNearestIndex([]).two_nearest(Point(0, 0)) == []
    one = [_Shape(_rect(0.0, 0.0, 10.0, 10.0))]
    _assert_same(one, [(0.0, 0.0), (100.0, 100.0), (10.0, 0.0)])
    assert len(_AirsideNearestIndex(one).two_nearest(Point(5, 5))) == 1
    two = one + [_Shape(_rect(300.0, 0.0, 10.0, 10.0))]
    _assert_same(two, [(0.0, 0.0), (150.0, 0.0), (1000.0, 1000.0)])


def test_repeated_queries_are_stable():
    """The index carries an adaptive seed radius between queries; that is
    a search-window heuristic and must not perturb the ANSWER."""
    rng = random.Random(3)
    airside = [_Shape(_rect(rng.uniform(-400, 400), rng.uniform(-400, 400),
                            rng.uniform(4, 60), rng.uniform(4, 60)))
               for _ in range(25)]
    index = _AirsideNearestIndex(airside)
    pts = [(rng.uniform(-500, 500), rng.uniform(-500, 500))
           for _ in range(60)]
    # Warm the seed radius on far points first, then re-query in a
    # different order and demand identical answers.
    first = [index.two_nearest(Point(*q)) for q in pts]
    for q in reversed(pts):
        index.two_nearest(Point(*q))
    again = [index.two_nearest(Point(*q)) for q in pts]
    for a, b in zip(first, again):
        assert [(d, id(s)) for d, s in a] == [(d, id(s)) for d, s in b]


# ── the per-pass cache ────────────────────────────────────────────────

def test_airside_index_cache_is_identity_keyed():
    """One index per ``airside`` LIST (built once per pass); a different
    list — even an equal one — gets its own index."""
    airside = [_Shape(_rect(0.0, 0.0, 10.0, 10.0)),
               _Shape(_rect(60.0, 0.0, 10.0, 10.0))]
    a = _airside_index(airside)
    assert _airside_index(airside) is a
    other = list(airside)
    assert _airside_index(other) is not a
    # …and the cached index still answers correctly for its own list.
    _assert_same(airside, [(30.0, 0.0), (0.0, 0.0)])
