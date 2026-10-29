"""Twins for issue #1028 E1 (spec ``docs/specs/eddf-tunnel-mouths-spec.md``):
a second OSM feed's coincident copy of a tunnel way is the same bore, never
a chain out and back (``planar/structure_approach.chains``).  Synthetic
ways; law values read from the tables, never retyped."""
from __future__ import annotations

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.bore_continuation import continues_underground, tunnel_ends
from auto_patch_v2.planar.structure_approach import approach, chains

_T = {"highway": "service", "tunnel": "yes", "layer": "-1"}
_R = {"highway": "service"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_a_coincident_copy_is_one_bore_with_both_real_ends():
    """The copy (reversed, from the other feed) rides in the bore's ways;
    the bore runs end to end once, so its two ends are the two portals."""
    a = OsmWay(-1, "big_roads", ((0.0, 0.0), (0.0, 75.0)), False, _T)
    b = OsmWay(-2, "small_roads", ((0.0, 75.0), (0.0, 0.0)), False, _T)
    (bore,) = chains([a, b])
    assert [w.id for w in bore.ways] == [-1, -2]
    assert bore.points[0] == (0.0, 0.0) and bore.points[-1] == (0.0, 75.0)


def test_a_copy_inside_a_longer_chain_keeps_the_chain():
    """Two ways meeting end to end, each with its copy: one bore of four
    ways whose line is the two ways once (the four-ways-meet node no longer
    splits it)."""
    ws = [OsmWay(-1, "big_roads", ((0.0, 0.0), (50.0, 0.0)), False, _T),
          OsmWay(-2, "big_roads", ((50.0, 0.0), (120.0, 0.0)), False, _T),
          OsmWay(-3, "small_roads", ((0.0, 0.0), (50.0, 0.0)), False, _T),
          OsmWay(-4, "small_roads", ((120.0, 0.0), (50.0, 0.0)), False, _T)]
    (bore,) = chains(ws)
    assert sorted(w.id for w in bore.ways) == [-4, -3, -2, -1]
    assert bore.line.length == pytest.approx(120.0)


def test_the_copy_is_not_a_tunnel_going_on_underground(law):
    """The copy's end at the portal is the bore's own way: the end is a
    portal where the open road runs on (#1028 Q32 rule 1 reads other bores
    only)."""
    tn = law.tables.structures.tunnel
    a = OsmWay(-1, "big_roads", ((0.0, 0.0), (75.0, 0.0)), False, _T)
    b = OsmWay(-2, "small_roads", ((75.0, 0.0), (0.0, 0.0)), False, _T)
    road = OsmWay(-3, "big_roads", ((75.0, 0.0), (600.0, 0.0)), False, _R)
    (bore,) = chains([a, b])
    ends = tunnel_ends([a, b, road], tn.admitted_values)
    path = approach((75.0, 0.0), (-1.0, 0.0), [a, b, road], 400.0, tn.admitted_values,
                    tn.approach_turn_max_deg)
    assert continues_underground(bore, (-1.0, 0.0), path, ends, law, 400.0) is None
