"""``ribbon_mint._way_intervals`` answers a way that misses the extent by the
prepared predicate (issue #803) and every other way by the overlay, so its
intervals are the plain overlay's on every case."""
from auto_patch_v2.classify.ribbon_mint import _way_intervals
from auto_patch_v2.geom.parts import line_parts
from shapely.geometry import LineString, Point, box


def _overlay(line, inside):
    out = []
    for part in line_parts(line.intersection(inside)):
        a = line.project(Point(part.coords[0]))
        b = line.project(Point(part.coords[-1]))
        a, b = min(a, b), max(a, b)
        if b - a > 0.0:
            out.append((a, b))
    return sorted(out)


def test_intervals_equal_the_overlay():
    inside = box(0, 0, 100, 100).union(box(150, 0, 200, 50))
    ways = [LineString([(-50, 50), (250, 20)]),          # crosses both
            LineString([(300, 300), (400, 310)]),        # nowhere near
            LineString([(100, -10), (100, 110)]),        # along an edge
            LineString([(110, 10), (140, 10)]),          # in the gap
            LineString([(10, 10), (20, 30), (300, 30)])]
    for ln in ways:
        assert _way_intervals(ln, inside) == _overlay(ln, inside)
    assert _way_intervals(ways[1], inside) == []
