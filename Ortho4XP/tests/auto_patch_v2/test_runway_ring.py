"""A pavement ring round a runway (#2281, #2282, #2286: EKVG's pack paints
one field-wide polygon round the slab): the taxiway entrance through it is
no wider than a corridor of its centreline, so the rest of the ring — the
narrow sides and the widened ends, the turn pads — stays the runway's
shoulder; and a side line already falling at the runway end never cuts the
end area off."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from auto_patch_v2.classify.apt_shoulder import taxiway_entrances
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.model.end_area import _end_length
from shapely.geometry import LineString, box
from shapely.strtree import STRtree

RULES = load_rules()
RW = SimpleNamespace(slab_corners=((0.0, -15.0), (1000.0, -15.0),
                                   (1000.0, 15.0), (0.0, 15.0)),
                     width_m=30.0, shoulder_m=0.0)


def test_an_entrance_through_a_ring_is_a_corridor_not_the_ring():
    slab = box(0.0, -15.0, 1000.0, 15.0)
    ring = box(-30.0, -22.0, 1030.0, 22.0).difference(slab)   # sides + end pads
    mouth = box(485.0, 15.0, 515.0, 40.0)                       # taxiway C's mouth
    inside = ring.union(mouth)
    taxi = LineString([(500.0, 120.0), (500.0, 15.0)])
    # a second centreline running along the ring's outer edge inflates the
    # length the corridor test reads (EKVG: the chain node beside the mouth)
    along = LineString([(380.0, 22.0), (620.0, 22.0)])
    parts = [(taxi, None), (along, None)]
    ents = taxiway_entrances(inside, RW, parts, STRtree([taxi, along]), RULES, 3.5)
    assert ents
    half = 0.5 * RULES.corridor.max_width_m
    reach = taxi.buffer(half + 0.5).union(along.buffer(half + 0.5))
    for p in ents:
        assert reach.contains(p)
        minx, _miny, maxx, _maxy = p.bounds
        assert minx > 0.0 and maxx < 1000.0      # never the end pads
    assert sum(p.area for p in ents) < 0.5 * ring.area


class _Dem:
    """Flat at 70 m within 30 m of the axis; beside it the ground falls
    away along the runway's own direction from just before the end (the
    gullies 75 m off EKVG's axis)."""

    def z(self, x, y):
        if abs(y) <= 30.0:
            return 70.0
        return 70.0 - 0.5 * max(0.0, x - 995.0)


def test_a_side_line_falling_at_the_end_does_not_end_the_end_area():
    law = Law.for_airport("SYNT")
    n = _end_length(_Dem(), (1000.0, 0.0), (1.0, 0.0), law, 4, "C", 0)
    assert n > float(law.tables.emit.design.edge_probe_m)


def test_a_blast_pad_within_the_end_area_is_a_turn_pad():
    from auto_patch_v2.classify.end_pad import end_pad_split
    rw = SimpleNamespace(ends=(SimpleNamespace(name="12", xy=(0.0, 0.0)),
                               SimpleNamespace(name="30", xy=(300.0, 0.0))))
    face = box(300.0, -17.0, 347.0, 10.0)          # 47 m past the 30 end
    pad, rest = end_pad_split(face, rw, "30", 30.0, 1.0)
    assert sum(p.area for p in pad) == pytest.approx(30.0 * 27.0)
    assert sum(p.area for p in rest) == pytest.approx(17.0 * 27.0)
    pad, rest = end_pad_split(box(-55.0, -16.0, 0.0, 17.0), rw, "12", 55.0, 1.0)
    assert rest == [] and len(pad) == 1
    pad, rest = end_pad_split(face, rw, "30", 0.0, 1.0)     # an end area cut at the end
    assert pad == [] and len(rest) == 1
    # a WIDENED face at a turn end is the turn pad whole (#2286, TNCS 30)
    pad, rest = end_pad_split(face, rw, "30", 30.0, 1.0, whole=True)
    assert rest == [] and sum(p.area for p in pad) == pytest.approx(47.0 * 27.0)


def test_a_turn_pad_is_widened_past_a_side_line():
    """#2286: TNCS 30's turnaround stands 6.9 m out past the runway's side
    line (a turn pad); a blast pad as wide as the slab does not."""
    from auto_patch_v2.classify.end_pad import widened
    rw = SimpleNamespace(width_m=19.8,
                         ends=(SimpleNamespace(name="12", xy=(0.0, 0.0)),
                               SimpleNamespace(name="30", xy=(300.0, 0.0))))
    assert widened(box(300.0, -16.8, 353.0, 10.1), rw, 1.0)
    assert not widened(box(300.0, -10.2, 353.0, 10.2), rw, 1.0)
    # past the end and beyond the far line
    assert widened(box(-46.0, -9.6, 0.0, 17.5), rw, 1.0)


def test_a_turn_pad_is_at_an_end_no_taxiway_reaches():
    from auto_patch_v2.classify.end_pad import taxi_reaches_end
    rw = SimpleNamespace(width_m=20.0,
                         ends=(SimpleNamespace(name="12", xy=(0.0, 0.0)),
                               SimpleNamespace(name="30", xy=(300.0, 0.0))))
    mid = LineString([(200.0, -60.0), (200.0, -10.0)])     # the apron's stub
    assert not taxi_reaches_end(rw, "30", [mid])
    assert not taxi_reaches_end(rw, "12", [mid])
    at_end = LineString([(295.0, -60.0), (295.0, -10.0)])  # an entrance at the threshold
    assert taxi_reaches_end(rw, "30", [mid, at_end])


def test_a_wrapping_page_is_shoulder_only_where_narrow():
    """14ba on the page, #2281: a piece of a page that wraps the runway is
    refused when deeper than the runway's half width, admitted when
    narrower; a page that does not wrap is never refused here."""
    from auto_patch_v2.classify.wrap_page import wide_on_wrapping_page
    slab = box(0.0, -15.0, 1000.0, 15.0)
    rw = SimpleNamespace(width_m=30.0)
    edges = [(rw, slab, slab.exterior.buffer(1.0, cap_style="flat"))]
    wrap = box(-30.0, -60.0, 1030.0, 60.0)               # painted over the slab
    deep = box(0.0, 15.0, 1000.0, 60.0)                  # 45 m deep
    narrow = box(0.0, 15.0, 1000.0, 22.0)                # 7 m deep
    assert wide_on_wrapping_page(deep, wrap, rw, 1000.0, edges, 0.75, 1.0)
    assert not wide_on_wrapping_page(narrow, wrap, rw, 1000.0, edges, 0.75, 1.0)
    side = box(0.0, 15.0, 1000.0, 60.0)                  # beside it only
    assert not wide_on_wrapping_page(deep, side, rw, 1000.0, edges, 0.75, 1.0)
