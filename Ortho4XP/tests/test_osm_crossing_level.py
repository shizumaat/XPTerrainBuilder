"""THE OSM-LEVEL CROSSING CLASSIFIER (redesign spec §4).

Owner policy, restated in ``docs/POSTMORTEM-20260831.md`` and ratified as
RULINGS 2026-08-31a:

    OSM carries crossing levels: ``layer=*``, ``bridge=*``, ``tunnel=*``;
    shared nodes = same-level intersection (our road feed preserves these
    — measured ``bridge=yes layer=1`` at the LEMD crossing).

The order of the two rules is the law, and the LEMD measurement is why:
a way can carry ``bridge=yes layer=1`` for a kilometre and still have
at-grade junctions inside that stretch.  Tags first would call such a
junction a span.
"""
from __future__ import annotations

from auto_patch import osm_crossing_level as X


class TestRuleOneASharedNodeIsAJunction:

    def test_a_shared_node_beats_every_tag(self):
        """The LEMD class, verbatim: ``bridge=yes layer=1`` against a
        tunnel, sharing one node — SAME LEVEL."""
        assert X.classify({"bridge": "yes", "layer": "1"}, [1, 2, 3],
                          {"tunnel": "yes", "layer": "-1"}, [3, 9]) == X.SAME

    def test_no_shared_node_lets_the_tags_speak(self):
        assert X.classify({"bridge": "yes", "layer": "1"}, [1, 2, 3],
                          {"tunnel": "yes"}, [7, 8]) == X.A_ABOVE

    def test_the_join_is_identity_not_proximity(self):
        """Two ways whose node ids are disjoint do not share a node,
        however close their coordinates might be — this module never
        sees a coordinate (memory ``canonical-identity-join``)."""
        assert not X.shares_a_node([1, 2], [3, 4])
        assert X.shares_a_node([1, 2], [2, 5])
        assert not X.shares_a_node([], [1])


class TestRuleTwoTheTagsOrderTheCrossing:

    def test_layer_wins_where_it_is_stated(self):
        assert X.way_level({"layer": "2"}) == 2.0
        assert X.way_level({"layer": "-3"}) == -3.0
        # a bridge tag does not override an explicit layer
        assert X.way_level({"bridge": "yes", "layer": "0"}) == 0.0

    def test_a_multi_valued_layer_takes_its_first(self):
        """``layer=-2;0`` is this way's own level first — the same parse
        ``bridges._has_tunnel_tag_evidence`` already applies."""
        assert X.way_level({"layer": "-2;0"}) == -2.0

    def test_bridge_and_tunnel_stand_in_for_a_missing_layer(self):
        assert X.way_level({"bridge": "yes"}) == 1.0
        assert X.way_level({"tunnel": "yes"}) == -1.0
        assert X.way_level({"tunnel": "building_passage"}) == -1.0
        assert X.way_level({"highway": "service"}) == 0.0

    def test_a_negated_tag_is_ordinary_ground(self):
        """``bridge=no`` is a road, not a bridge — the truthy-value
        reading the core's exclusion set and ``_way_is_bridge`` share."""
        assert X.way_level({"bridge": "no"}) == 0.0
        assert X.way_level({"tunnel": "no"}) == 0.0
        assert X.classify({"bridge": "no"}, [1],
                          {"highway": "service"}, [9]) == X.SAME

    def test_an_unparseable_layer_falls_back_to_the_tags(self):
        assert X.parse_layer({"layer": "ground"}) is None
        assert X.way_level({"layer": "ground", "bridge": "yes"}) == 1.0

    def test_equal_levels_are_the_same_level(self):
        assert X.classify({"bridge": "yes"}, [1],
                          {"bridge": "yes"}, [9]) == X.SAME
        assert X.classify({}, [1], {}, [9]) == X.SAME

    def test_b_above_is_reported_too(self):
        assert X.classify({"tunnel": "yes"}, [1],
                          {"bridge": "yes"}, [9]) == X.B_ABOVE


class TestSpansOverIsTheDeckQuestion:

    def test_a_bridge_over_a_bore_spans_it(self):
        assert X.spans_over({"bridge": "yes"}, [1],
                            {"tunnel": "yes"}, [5])

    def test_a_bridge_sharing_a_node_with_the_bore_does_not(self):
        """The candidacy filter in ``road_bridge_deck.publish_candidates``:
        no span ⇒ no deck ⇒ nothing put over a road the driver turns
        onto."""
        assert not X.spans_over({"bridge": "yes"}, [1, 5],
                                {"tunnel": "yes"}, [5, 6])

    def test_tags_may_be_missing_entirely(self):
        assert not X.spans_over(None, [1], None, [2])
        assert X.way_level(None) == 0.0
