"""INSIDE THE FENCE THE TAG IS NOT ITS OWN WITNESS (owner RULINGS
2026-10-28p (4), Q243 "a", #1338): pavement painted over a tagged tunnel
is not by itself a witness that the tunnel exists; it needs one of RULINGS
2026-10-27z's witnesses.  NZWN's multi-storey car park maps its ground
level as ``layer=-1 tunnel=yes`` service ways under its own pavement, and
the classified cover and that layer cut them to -3.1 m.  SPJC -5724's
fixture (``test_tunnelwitness2._spjc``), with the car park's cover and
layer laid on it."""
from __future__ import annotations

import pytest
import test_tunnelwitness2 as TW  # noqa: E402
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay

CAR_PARK = {"highway": "service", "lanes": "1", "tunnel": "yes", "layer": "-1"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_cover_and_layer_alone_inside_the_fence_are_REFUSED_by_name(law):
    for tags, kw in ((TW.SPJC_TAGS, {"extra_cells": (TW.APRON,)}),
                     (CAR_PARK, {}), (CAR_PARK, {"extra_cells": (TW.APRON,)})):
        _cl, tunnels, st = TW._spjc(law, tags=tags, **kw)
        assert st.tunnels == 0 and not tunnels, (tags, st.mouths_off_field_nearest)
        named = TW._refusals(st)
        assert len(named) == 1 and "WITH NO WITNESS" in named[0], named
        assert "28p (4)" in named[0]


def test_the_same_bore_OUTSIDE_the_fence_is_built_by_cover_or_layer(law):
    for tags, kw in ((TW.SPJC_TAGS, {"extra_cells": (TW.APRON,)}), (CAR_PARK, {})):
        _cl, _t, st = TW._spjc(law, tags=tags, fence=None, **kw)
        assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest


def test_a_27z_witness_still_builds_it_inside_the_fence(law):
    # a rise of the ground over the bore (witness 1)
    _cl, _t, st = TW._spjc(law, tags=CAR_PARK, extra_cells=(TW.APRON,), dem=TW._hill(2.0))
    assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest
    # a road crossing over it at grade, outside any pack building (witness 4)
    road = OsmWay(-9010, "small_roads", ((317.0, -150.0), (317.0, -50.0)), False,
                  {"highway": "service"})
    _cl, _t, st = TW._spjc(law, tags=CAR_PARK, more_ways=(road,))
    assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest


def test_inside_a_pack_building_the_building_is_the_cover(law):
    """Owner RULINGS 2026-10-28q (3), Q249 "a": NZWN's multi-storey car
    park — its decks mapped as at-grade roads across its layer -1 ground
    floor.  Inside the pack building's footprint neither the road crossing
    there nor the building itself is a witness."""
    road = OsmWay(-9010, "small_roads", ((317.0, -150.0), (317.0, -50.0)), False,
                  {"highway": "service"})
    garage = TW._part(0.0, 12.0, TW._ll_ring(305, -120, 330, -80))   # holds neither end
    _cl, tunnels, st = TW._spjc(law, tags=CAR_PARK, partition=TW._link(garage),
                                more_ways=(road,))
    assert st.tunnels == 0 and not tunnels, st.mouths_off_field_nearest
    assert len(TW._refusals(st)) == 1 and "WITH NO WITNESS" in TW._refusals(st)[0]
    # outside the fence the crossing still builds it (§34 (12) (5) (c))
    _cl, _t, st = TW._spjc(law, tags=CAR_PARK, partition=TW._link(garage),
                           more_ways=(road,), fence=None)
    assert st.tunnels == 2


def test_stacked_ways_are_a_car_parks_decks(law):
    """Owner RULINGS 2026-10-28s (4), Q252 "a": several ways stacked on one
    line — the same two ends, a few metres apart between them — are a car
    park's own decks, not roads crossing the tunnel: no witness inside the
    fence and no (c) crossing outside it.  NZWN: the garage's three
    unclassified ramps (36-37 m, 3.4-6.9 m apart) across its ground floor."""
    a, b = (317.0, -150.0), (317.0, -50.0)
    decks = tuple(OsmWay(-9020 - k, "small_roads", (a, (317.0 + 3.0 * k, -100.0), b)
                         if k % 2 == 0 else (b, (317.0 + 3.0 * k, -100.0), a), False,
                         {"highway": "unclassified"}) for k in range(3))
    for fence in (TW._rect(-800, -800, 800, 800), None):
        _cl, tunnels, st = TW._spjc(law, tags=TW.SPJC_TAGS, more_ways=decks, fence=fence)
        assert st.tunnels == 0 and not tunnels, (fence, st.mouths_off_field_nearest)
    # ONE of them alone is a road crossing over it, and builds it
    _cl, _t, st = TW._spjc(law, tags=TW.SPJC_TAGS, more_ways=decks[:1])
    assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest


def test_two_halves_of_a_roundabout_are_not_decks(law):
    """Two ways sharing both ends but standing far apart (a roundabout's
    halves) are independent roads: each crossing still witnesses."""
    a, b = (317.0, -115.0), (317.0, -85.0)
    halves = (OsmWay(-9030, "small_roads", (a, (332.0, -100.0), b), False, {"highway": "service"}),
              OsmWay(-9031, "small_roads", (a, (302.0, -100.0), b), False, {"highway": "service"}))
    _cl, _t, st = TW._spjc(law, tags=TW.SPJC_TAGS, more_ways=halves)
    assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest


def test_one_road_the_feeds_carry_twice_is_not_decks(law):
    """The SAME vertices under two ids (two OSM feeds carrying one way,
    measured LFPG -48615 / -19838) are one road crossing over the bore, and
    it still witnesses."""
    pts = ((317.0, -150.0), (317.0, -50.0))
    twice = (OsmWay(-9040, "big_roads", pts, False, {"highway": "unclassified"}),
             OsmWay(-9041, "small_roads", pts[::-1], False, {"highway": "unclassified"}))
    _cl, _t, st = TW._spjc(law, tags=TW.SPJC_TAGS, more_ways=twice)
    assert st.tunnels == 2 and not TW._refusals(st), st.mouths_off_field_nearest
