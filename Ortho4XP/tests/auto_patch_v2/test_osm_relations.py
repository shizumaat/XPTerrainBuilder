"""Spec §25 / §26 twins (RULINGS 2026-09-11aq).

§25 — a multipolygon's outer ways carry its tags: a tagged relation over
an UNTAGGED outer way makes that way an ``aeroway=apron`` / building ring
(the way's own tag wins where both exist), an outer ring chained from
several open ways is stitched into one closed way, and inner rings are
dropped (counted, with their area).

§26 — ``tunnel=building_passage`` is not a bore: it never seeds a
structure, and neither do ``culvert`` / ``avalanche_protector`` /
``flooded`` / ``no``; ``tunnel=yes`` still does.
"""
from __future__ import annotations

from auto_patch_v2.airport import osm as O
from auto_patch_v2.airport.deck_signature import (DEFAULT_TUNNEL_VALUES,
                                                  is_tunnel_way)

# ── §25 ──────────────────────────────────────────────────────────────────

_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n'
_TAIL = "</osm>\n"


def _nodes(spec: dict[str, tuple[float, float]]) -> str:
    return "".join(f'<node id="{i}" lat="{la}" lon="{lo}"/>\n'
                   for i, (la, lo) in spec.items())


def _way(wid: str, refs: list[str], tags: dict[str, str] | None = None) -> str:
    body = "".join(f'<nd ref="{r}"/>\n' for r in refs)
    body += "".join(f'<tag k="{k}" v="{v}"/>\n' for k, v in (tags or {}).items())
    return f'<way id="{wid}">\n{body}</way>\n'


def _rel(rid: str, members: list[tuple[str, str]], tags: dict[str, str]) -> str:
    body = "".join(f'<member type="way" ref="{r}" role="{role}"/>\n'
                   for r, role in members)
    body += "".join(f'<tag k="{k}" v="{v}"/>\n' for k, v in tags.items())
    return f'<relation id="{rid}">\n{body}</relation>\n'


def _write(tmp_path, xml: str) -> str:
    p = tmp_path / "feed.osm"
    p.write_text(_HEAD + xml + _TAIL)
    return str(p)


def test_a_tagged_relation_hands_its_tags_to_an_untagged_outer(tmp_path):
    """The LEMD class: relation −1 is the terminal, its outer way −48
    arrives tagless.  After §25 the way carries the relation's tags."""
    xml = _nodes({"1": (40.0, -3.0), "2": (40.0, -2.999), "3": (40.001, -2.999),
                  "4": (40.001, -3.0)})
    xml += _way("-48", ["1", "2", "3", "4", "1"])          # tagless outer
    xml += _rel("-1", [("-48", "outer")],
                {"type": "multipolygon", "building": "transportation",
                 "aeroway": "terminal", "name": "Terminal 2",
                 "operator": "Aena"})                       # operator: not of interest
    nodes, ways, rep = O.read_osm_file(_write(tmp_path, xml))
    by_id = {w[0]: w[2] for w in ways}
    assert by_id["-48"] == {"building": "transportation", "aeroway": "terminal",
                            "name": "Terminal 2"}
    assert (rep.relations, rep.tagged_ways, rep.stitched) == (1, 1, 0)
    assert rep.unclosable == () and rep.inners_dropped == 0


def test_the_ways_own_tag_wins_over_the_relations(tmp_path):
    xml = _nodes({"1": (40.0, -3.0), "2": (40.0, -2.999), "3": (40.001, -2.999)})
    xml += _way("-9", ["1", "2", "3", "1"], {"aeroway": "taxiway"})
    xml += _rel("-1", [("-9", "outer")], {"type": "multipolygon",
                                          "aeroway": "apron", "name": "R-2"})
    _, ways, rep = O.read_osm_file(_write(tmp_path, xml))
    tags = {w[0]: w[2] for w in ways}["-9"]
    assert tags["aeroway"] == "taxiway"      # the way's own tag wins
    assert tags["name"] == "R-2"             # the relation still adds the rest
    assert rep.tagged_ways == 1


def test_a_relation_that_is_not_an_area_hands_nothing_down(tmp_path):
    xml = _nodes({"1": (40.0, -3.0), "2": (40.0, -2.999)})
    xml += _way("-9", ["1", "2"])
    xml += _rel("-1", [("-9", "outer")], {"type": "route", "highway": "primary"})
    _, ways, rep = O.read_osm_file(_write(tmp_path, xml))
    assert {w[0]: w[2] for w in ways}["-9"] == {}
    assert rep.relations == 0


def test_open_outers_are_stitched_into_one_closed_ring(tmp_path):
    """Two open ways sharing endpoints make ONE outer ring; the stitched
    way carries the relation's tags and closes."""
    xml = _nodes({"1": (40.0, -3.0), "2": (40.0, -2.999),
                  "3": (40.001, -2.999), "4": (40.001, -3.0)})
    xml += _way("-11", ["1", "2", "3"])
    xml += _way("-12", ["3", "4", "1"])
    xml += _rel("-1", [("-11", "outer"), ("-12", "outer")],
                {"type": "multipolygon", "aeroway": "apron"})
    nodes, ways, rep = O.read_osm_file(_write(tmp_path, xml))
    assert rep.stitched == 1 and rep.unclosable == ()
    ring = [w for w in ways if w[0] == "-1#0"]
    assert len(ring) == 1
    _, nds, tags = ring[0]
    assert nds[0] == nds[-1] and len(nds) == 5
    assert tags == {"aeroway": "apron"}


def test_an_outer_that_cannot_be_closed_is_dropped_and_named(tmp_path):
    xml = _nodes({"1": (40.0, -3.0), "2": (40.0, -2.999), "3": (40.001, -2.999)})
    xml += _way("-11", ["1", "2"])
    xml += _way("-12", ["2", "3"])          # no way back to node 1
    xml += _rel("-77", [("-11", "outer"), ("-12", "outer")],
                {"type": "multipolygon", "aeroway": "apron"})
    _, ways, rep = O.read_osm_file(_write(tmp_path, xml))
    assert rep.stitched == 0
    assert rep.unclosable == ("-77",)
    assert not [w for w in ways if "#" in w[0]]


def test_inner_rings_are_dropped_counted_and_measured(tmp_path):
    """§25 (2): the courtyard is not a hole this round — it is counted
    with its area and given NONE of the relation's tags."""
    xml = _nodes({"1": (40.0, -3.0), "2": (40.0, -2.99), "3": (40.01, -2.99),
                  "4": (40.01, -3.0),
                  "5": (40.004, -2.996), "6": (40.004, -2.995),
                  "7": (40.005, -2.995), "8": (40.005, -2.996)})
    xml += _way("-48", ["1", "2", "3", "4", "1"])
    xml += _way("-610", ["5", "6", "7", "8", "5"])
    xml += _rel("-1", [("-48", "outer"), ("-610", "inner")],
                {"type": "multipolygon", "building": "yes"})
    _, ways, rep = O.read_osm_file(_write(tmp_path, xml))
    by_id = {w[0]: w[2] for w in ways}
    assert by_id["-48"] == {"building": "yes"}
    assert by_id["-610"] == {}               # the inner gets nothing
    assert rep.inners_dropped == 1
    assert 8_000.0 < rep.inner_area_m2 < 12_000.0   # ~1e-3 x 1e-5 deg


def test_namespacing_survives_the_relation_join(tmp_path):
    xml = _nodes({"1": (40.0, -3.0), "2": (40.0, -2.999), "3": (40.001, -2.999)})
    xml += _way("-48", ["1", "2", "3", "1"])
    xml += _rel("-1", [("-48", "outer")], {"type": "building",
                                           "building": "transportation"})
    _, ways, rep = O.read_osm_file(_write(tmp_path, xml), namespace="+40-004:")
    assert {w[0] for w in ways} == {"+40-004:-48"}
    assert {w[0]: w[2] for w in ways}["+40-004:-48"]["building"] == "transportation"
    assert rep.tagged_ways == 1


def test_a_file_with_no_relations_is_untouched(tmp_path):
    xml = _nodes({"1": (40.0, -3.0), "2": (40.0, -2.999)})
    xml += _way("-9", ["1", "2"], {"highway": "service"})
    _, ways, rep = O.read_osm_file(_write(tmp_path, xml))
    assert [w[2] for w in ways] == [{"highway": "service"}]
    assert rep == O.RelationReport()


# ── §26 ──────────────────────────────────────────────────────────────────

def test_a_building_passage_never_seeds_a_bore():
    """The LEMD site: OSM ways −17295 / −7905, roads UNDER the old
    terminal, tagged ``tunnel=building_passage``."""
    tags = {"highway": "service", "tunnel": "building_passage"}
    assert is_tunnel_way(tags) is False
    assert is_tunnel_way(tags, DEFAULT_TUNNEL_VALUES) is False


def test_the_not_a_bore_values_never_seed():
    for v in ("building_passage", "culvert", "avalanche_protector",
              "flooded", "no"):
        assert is_tunnel_way({"highway": "service", "tunnel": v}) is False
        assert is_tunnel_way({"railway": "rail", "tunnel": v}) is False


def test_tunnel_yes_still_seeds_on_highway_and_railway():
    assert is_tunnel_way({"highway": "primary", "tunnel": "yes"}) is True
    assert is_tunnel_way({"railway": "rail", "tunnel": "yes"}) is True
    assert is_tunnel_way({"tunnel": "yes"}) is False       # neither road nor rail


def test_the_admitted_set_is_the_laws(tmp_path):
    """A law that admits ``building_passage`` would seed it — the values
    live in ``[tunnel] admitted_values``, never in Python."""
    tags = {"highway": "service", "tunnel": "building_passage"}
    assert is_tunnel_way(tags, ("yes", "building_passage")) is True


def test_the_law_default_is_yes_only():
    from auto_patch_v2.law import Law
    assert Law.for_airport("LEMD").tables.structures.tunnel.admitted_values \
        == ("yes",)
