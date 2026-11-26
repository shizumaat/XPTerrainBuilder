"""#2239: a covered trench's footprint (its rim) stands under its cover
(``airport/cover_rim``): a rim past the cover's edge leaves a slot between
the deck and the taxiway that drives onto it."""
from __future__ import annotations

from shapely.geometry import box

from auto_patch_v2.airport.cover_rim import covered_strip, under_cover

GAP = 0.6
AXIS = [(float(x), 0.0) for x in range(-40, 41, 5)]     # the trench runs along x


def test_a_footprint_past_the_cover_is_clipped_under_it_across_the_covered_stretch():
    trench = box(-40, -13.83, 40, 12.21)
    footprint = box(-40, -15.03, 40, 13.00)        # the rim 0.8 / 1.3 m past the deck
    cover = box(-12, -13.75, 12, 12.17)            # the deck over the trench
    fp, tr, moved = under_cover(footprint, trench, AXIS, cover, GAP)
    assert moved > 0.0
    # under the deck the rim stands wall_gap_m inside the cover's edge
    mid = fp.intersection(box(-5, -50, 5, 50))
    assert abs(mid.bounds[3] - (12.17 - GAP)) < 1e-6
    assert abs(mid.bounds[1] - (-13.75 + GAP)) < 1e-6
    # beyond the covered stretch (the open trench, its mouths) nothing moves
    out = fp.intersection(box(20, -50, 40, 50))
    assert abs(out.bounds[3] - 13.00) < 1e-6 and abs(out.bounds[1] + 15.03) < 1e-6
    assert tr.within(fp.buffer(1e-9))


def test_a_footprint_under_its_cover_is_untouched():
    trench = box(-40, -10, 40, 10)
    footprint = box(-40, -11, 40, 11)
    cover = box(-12, -12, 12, 12)
    fp, tr, moved = under_cover(footprint, trench, AXIS, cover, GAP)
    assert moved == 0.0 and fp is footprint and tr is trench


def test_no_axis_point_under_the_cover_is_no_covered_stretch():
    assert covered_strip(AXIS, box(100, 100, 110, 110), 50.0) is None
    assert under_cover(box(0, 0, 1, 1), box(0, 0, 1, 1), AXIS, None, GAP)[2] == 0.0
