"""#2239: a covered trench's rim stands at its cover's SIDES, never past
them, and the road under the cover is never cut back (``airport/cover_rim``;
owner sim read 2026-11-26T15:02Z: the strip under the deck's ends is not
support, the road envelope stays clear, the ends clean, not jagged)."""
from __future__ import annotations

from auto_patch_v2.airport.cover_rim import _lateral_strips, under_cover
from shapely.geometry import Polygon, box

AXIS = [(float(x), 0.0) for x in range(-40, 41, 5)]     # the trench runs along x
FAR = 2.0


def test_the_rim_past_the_cover_sides_is_cut_back_to_them():
    trench = box(-40, -13.83, 40, 12.21)
    footprint = box(-40, -15.03, 40, 13.00)        # the rim 1.28 / 0.83 m past the deck
    cover = box(-12, -13.75, 12, 12.17)            # the deck over the trench
    fp, tr, moved = under_cover(footprint, trench, AXIS, cover, FAR)
    assert moved > 0.0
    # under the deck the rim stands ON the cover's sides, its whole length
    for x0 in (-11.95, 0, 11.85):
        mid = fp.intersection(box(x0, -50, x0 + 0.1, 50))
        assert abs(mid.bounds[3] - 12.17) < 1e-6 and abs(mid.bounds[1] + 13.75) < 1e-6
    # beyond the cover's mouths nothing moves, the trench neither
    out = fp.intersection(box(12.0, -50, 40, 50))
    assert abs(out.bounds[3] - 13.00) < 1e-6 and abs(out.bounds[1] + 15.03) < 1e-6
    assert tr.intersection(box(12, -50, 40, 50)).equals(trench.intersection(box(12, -50, 40, 50)))
    # under the cover the trench (the road) is never cut back
    assert cover.difference(tr).area < 1e-6


def test_a_skewed_mouth_is_never_cut_into_the_road():
    trench = box(-40, -10, 40, 10)
    footprint = box(-40, -11.2, 40, 11.2)
    cover = Polygon([(-12, -10.5), (14, -10.5), (10, 10.5), (-16, 10.5)])   # skewed mouths
    fp, tr, _moved = under_cover(footprint, trench, AXIS, cover, FAR)
    # the road (the trench between the walls) keeps its whole plan
    assert abs(tr.area - trench.area) < 1e-6
    assert fp.contains(trench.buffer(-1e-6))


def test_a_footprint_under_its_cover_is_untouched():
    trench = box(-40, -10, 40, 10)
    footprint = box(-40, -11, 40, 11)
    cover = box(-12, -12, 12, 12)
    fp, tr, moved = under_cover(footprint, trench, AXIS, cover, FAR)
    assert moved == 0.0 and fp is footprint and tr is trench


def test_the_strips_stand_only_beside_the_cover():
    s = _lateral_strips(box(-12, -10, 12, 10), AXIS, FAR)
    assert abs(s.area - 2 * 24 * FAR) < 1e-6
    assert s.intersection(box(-50, -9.99, 50, 9.99)).area < 1e-9
    assert _lateral_strips(None, AXIS, FAR) is None
    assert under_cover(box(0, 0, 1, 1), box(0, 0, 1, 1), AXIS, None, FAR)[2] == 0.0


def test_a_staircase_mouth_is_no_side():
    # the mouth at x = 12 is a staircase: its along-axis steps face sideways
    cover = Polygon([(-12, -10), (12, -10), (12, -4), (13, -4), (13, 4), (12, 4),
                     (12, 10), (-12, 10)])
    trench = box(-40, -9.9, 40, 9.9)
    footprint = box(-40, -11, 40, 11)
    fp, tr, _moved = under_cover(footprint, trench, AXIS, cover, FAR)
    assert abs(tr.area - trench.area) < 1e-6     # nothing cut across the road past the mouth
    assert fp.contains(trench.buffer(-1e-6))
