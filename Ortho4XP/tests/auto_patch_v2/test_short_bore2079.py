"""Twins for #2079 R2 — A ONE-MOUTHED SHORT BORE IS A ROAD AT GRADE UNDER
THE BUILDING (owner RULINGS 2026-11-16h; ``planar/short_bore``).

Measured at a field where a 55 m mapped bore under a terminal building
had its mouth cut 7.5 m deep at one end and its other end at grade inside
a pad, where the road leaves it: a 13.6 % through-grade against the 10 %
cap.  The bore is refused whole; every other case stands.

Law values are read from the tables, never retyped."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.short_bore import bore_end, short_bore_refusal
from auto_patch_v2.planar.structure_approach import Bore, Mouth


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _way(wid, pts, tags) -> OsmWay:
    return OsmWay(wid, "small_roads", tuple(pts), False, tags)


def _case(law, length: float, depth: float, *, road_at_far=True, rail=False):
    tag = {"railway": "rail"} if rail else {"highway": "service"}
    bore_way = _way(-6785, [(0.0, 0.0), (length, 0.0)], {**tag, "tunnel": "yes"})
    bore = Bore([bore_way], [(0.0, 0.0), (length, 0.0)])
    m = Mouth(bore, (0.0, 0.0), (1.0, 0.0), 7.0, [(0.0, 0.0), (-200.0, 0.0)], (-6785,))
    group = NS(corridor=None, members=[m])
    t = NS(id="tunnel:-6785@0", mouth_dem_z=10.0, mouth_z=10.0 - depth)
    ways = [bore_way, _way(-1, [(-200.0, 0.0), (0.0, 0.0)], dict(tag))]
    if road_at_far:
        ways.append(_way(-340, [(length, 0.0), (length + 80.0, 0.0)], dict(tag)))
    return t, group, ways, {bore_end(m)}


def test_short_one_mouthed_bore_is_refused(law):
    cap = law.tables.structures.tunnel.ramp_max_grade
    depth = 7.5
    length = 0.7 * depth / cap            # too short to climb out at the cap
    t, g, ways, opened = _case(law, length, depth)
    why = short_bore_refusal(t, g, law, ways, opened)
    assert why and "ONE-MOUTHED SHORT BORE" in why and "-6785" in why and "-340" in why
    assert "2026-11-16h" in why


def test_a_bore_that_can_climb_out_stands(law):
    cap = law.tables.structures.tunnel.ramp_max_grade
    t, g, ways, opened = _case(law, 1.2 * 7.5 / cap, 7.5)
    assert short_bore_refusal(t, g, law, ways, opened) is None


def test_a_two_mouthed_bore_stands(law):
    t, g, ways, opened = _case(law, 30.0, 7.5)
    b = g.members[0].bore
    assert short_bore_refusal(t, g, law, ways, opened | {(id(b), 1)}) is None


def test_no_road_at_the_far_end_stands(law):
    t, g, ways, opened = _case(law, 30.0, 7.5, road_at_far=False)
    assert short_bore_refusal(t, g, law, ways, opened) is None


def test_a_pack_portal_or_object_corridor_stands(law):
    t, g, ways, opened = _case(law, 30.0, 7.5)
    t.portal_seat = ("portal.obj", 2.5)
    assert short_bore_refusal(t, g, law, ways, opened) is None
    t2, g2, ways2, opened2 = _case(law, 30.0, 7.5)
    g2.corridor = object()
    assert short_bore_refusal(t2, g2, law, ways2, opened2) is None


def test_rail_reads_the_rail_cap(law):
    tn = law.tables.structures.tunnel
    depth = 7.5
    length = 0.5 * (depth / tn.ramp_max_grade + depth / tn.rail_ramp_max_grade)
    # between the two caps' lengths: a road would climb out, a railway not
    t, g, ways, opened = _case(law, length, depth, rail=True)
    assert short_bore_refusal(t, g, law, ways, opened)
    t, g, ways, opened = _case(law, length, depth)
    assert short_bore_refusal(t, g, law, ways, opened) is None


def test_a_bore_going_on_underground_stands(law):
    """A far end where another tunnel way goes on is no end: the bore is
    longer than its chain (``bore_continuation``'s case)."""
    t, g, ways, opened = _case(law, 30.0, 7.5)
    ways.append(_way(-509, [(30.0, 0.0), (30.0, 60.0)], {"highway": "service", "tunnel": "yes"}))
    assert short_bore_refusal(t, g, law, ways, opened) is None


def test_the_refused_far_mouth_is_named(law):
    t, g, ways, opened = _case(law, 30.0, 7.5)
    why = short_bore_refusal(t, g, law, ways, opened, refused=[
        "tunnel:-6785@1: the mouth stands against building pad building69"])
    assert why and "building69" in why
