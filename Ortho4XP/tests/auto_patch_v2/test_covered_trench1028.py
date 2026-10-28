"""Twins for RULINGS 2026-10-28s (5) (owner Q255 a; issue #1028, spec
``docs/specs/eddf-tunnel-mouths-spec.md`` E2): a road mapped ``covered=yes``
is a bore where the survey reads a cut at its end or a pack trench object
stands there (``planar/covered_bores``).  Synthetic ways and DEMs; law
values read from the tables, never retyped."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.airport.trench_objects import TrenchObject, covered_candidates
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.covered_bores import covered_bore_ways
from shapely.geometry import box

_C = {"highway": "tertiary", "lanes": "2", "covered": "yes"}


class _Dem:
    """``top`` over the cover (0 <= x <= 200) and away from the road; ``low``
    in a road-wide trench beyond the cover's ends when ``cut``."""

    def __init__(self, top: float, low: float, cut: bool):
        self.top, self.low, self.cut = top, low, cut

    def z(self, x: float, y: float) -> float:
        if self.cut and not (0.0 <= x <= 200.0) and abs(y) < 6.0:
            return self.low
        return self.top


def _airport(dem, ways):
    return types.SimpleNamespace(dem=dem, osm_ways=tuple(ways))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _way(tags=_C):
    return OsmWay(-1, "small_roads", ((0.0, 0.0), (200.0, 0.0)), False, tags)


def test_a_covered_road_in_a_surveyed_cut_is_a_bore(law):
    """7 m of cover over a road whose ends stand in the survey's trench."""
    ap = _airport(_Dem(111.0, 104.0, True), [_way()])
    ways, notes = covered_bore_ways(ap, law, True, (), 2.0)
    assert [w.id for w in ways] == [-1]
    assert ways[0].tags["tunnel"] == "yes" and ways[0].tags["o4_covered"] == "yes"
    assert "survey reads" in notes[0]


def test_a_covered_road_at_grade_stays_a_road(law):
    """No cut at either end, no trench object: not a bore (11aq A stands)."""
    ap = _airport(_Dem(111.0, 104.0, False), [_way()])
    assert covered_bore_ways(ap, law, True, (), 2.0) == ([], [])


def test_a_coarse_dem_is_no_witness_but_a_trench_object_is(law):
    """On a coarse DEM the cut is not read (14f); a pack trench object at an
    end admits the road all the same."""
    ap = _airport(_Dem(111.0, 104.0, True), [_way()])
    assert covered_bore_ways(ap, law, False, (), 2.0) == ([], [])
    t = TrenchObject("dsf:obj1", "GP/trench.obj", box(-60.0, -20.0, 2.0, 20.0), 6.0,
                     (((0.0, 0.0), -1),))
    ways, notes = covered_bore_ways(ap, law, False, (t,), 2.0)
    assert [w.id for w in ways] == [-1] and "trench object dsf:obj1" in notes[0]


def test_a_tunnel_value_is_never_a_covered_candidate():
    """``building_passage`` (and every other ``tunnel`` value) is read by
    11aq A alone."""
    bp = _way({**_C, "tunnel": "building_passage"})
    assert covered_candidates([bp, _way()]) == [_way()]
