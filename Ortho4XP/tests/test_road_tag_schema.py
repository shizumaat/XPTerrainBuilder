"""The road feed keeps OSM's DEPTH WITNESSES (spec §45 (9), owner
2026-09-15 "Bump the schema now").

``ROADS_TAGS_OF_INTEREST`` used to drop ``layer`` / ``cutting`` /
``covered`` / ``embankment`` at download, so a below-grade road/rail
channel cut through an airport (LGAV, KPHX, KDFW) reached the engine with
its depth evidence already thrown away.  Three things are pinned here:

* the four tags are on the whitelist, and the four that were always there
  still are;
* ``ROAD_CACHE_TAG_SCHEMA`` moved, so a cache written under the old
  schema is NOT recycled — it re-downloads once with the richer whitelist
  instead of silently serving four-key ways (the schema marker's whole
  purpose, ``O4_OSM_Utils._cached_osm_schema_matches``);
* the READER passes them through: a cached way carrying
  ``cutting=yes layer=-1`` comes out of the recycle path with those tags
  on its tag dict, through the same ``target_tags`` derivation the live
  download uses.

Headless, ``tmp_path``-based, no network (the cache is on disk, so the
recycle branch never reaches Overpass).
"""

from __future__ import annotations

import bz2
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES                             # noqa: E402
import O4_OSM_Utils as OSM                                 # noqa: E402
import O4_Vector_Map as VMAP                               # noqa: E402

#: The schema string the four new tags landed under.  A later bump must
#: change this test too — deliberately, so the bump is never silent.
SCHEMA_OF_RECORD = "2026-09-15"
#: The schema the four-key whitelist was cached under.
PREVIOUS_SCHEMA = "2026-07-16"

DEPTH_WITNESS_TAGS = ("layer", "cutting", "covered", "embankment")


def test_roads_whitelist_carries_the_depth_witnesses():
    for tag in DEPTH_WITNESS_TAGS:
        assert tag in VMAP.ROADS_TAGS_OF_INTEREST, tag
    # The four that size the ramps and state a span are untouched.
    for tag in ("bridge", "tunnel", "width", "lanes"):
        assert tag in VMAP.ROADS_TAGS_OF_INTEREST, tag


def test_node_whitelist_is_untouched():
    """The depth witnesses are WAY tags; the nodes carry none of them, and
    widening the node whitelist would change the level-crossing veto's
    evidence for no gain (spec §45 (9))."""
    assert VMAP.ROAD_NODE_TAGS_OF_INTEREST == [
        "aeroway", "crossing:aircraft", "barrier"]


def test_schema_was_bumped_with_the_whitelist():
    assert VMAP.ROAD_CACHE_TAG_SCHEMA == SCHEMA_OF_RECORD
    assert VMAP.ROAD_CACHE_TAG_SCHEMA != PREVIOUS_SCHEMA


def test_every_road_layer_specification_carries_the_bumped_schema(
        monkeypatch, tmp_path):
    """Both tile-wide road layers download under the whitelist AND the
    schema — a specification still naming the old schema would recycle a
    four-key cache in the prefetch/warm path."""
    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    monkeypatch.setattr(VMAP, "resolved_road_level", lambda tile: (2, False))
    tile = _fake_tile()
    specifications = VMAP.osm_layer_warm_specifications(tile)
    road_specifications = [s for s in specifications
                           if s[0] in ("big_roads", "small_roads")]
    assert len(road_specifications) == 2
    for _suffix, _queries, tags, _node_tags, schema in road_specifications:
        assert schema == SCHEMA_OF_RECORD
        for tag in DEPTH_WITNESS_TAGS:
            assert tag in tags


def test_a_cache_under_the_old_schema_is_not_recycled(tmp_path):
    """The bump's ONE job: an old cache stops matching, so it is
    re-downloaded once instead of serving ways without the new tags."""
    cache_path = tmp_path / "old.osm.bz2"
    _write_road_cache(cache_path, PREVIOUS_SCHEMA)
    assert OSM._cached_osm_schema_matches(
        str(cache_path), PREVIOUS_SCHEMA) is True
    assert OSM._cached_osm_schema_matches(
        str(cache_path), VMAP.ROAD_CACHE_TAG_SCHEMA) is False
    current = tmp_path / "current.osm.bz2"
    _write_road_cache(current, VMAP.ROAD_CACHE_TAG_SCHEMA)
    assert OSM._cached_osm_schema_matches(
        str(current), VMAP.ROAD_CACHE_TAG_SCHEMA) is True


def test_the_reader_passes_the_witnesses_through(monkeypatch, tmp_path):
    """The whole point of the whitelist: a way tagged ``cutting=yes
    layer=-1 covered=no embankment=yes`` survives the parse with all four
    on its tag dict.  Read through ``OSM_queries_to_OSM_layer`` — the
    caller the encoder uses — so the ``target_tags`` derivation under
    test is production's, not the test's."""
    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    cache_path = FNAMES.osm_cached(10, 20, "big_roads")
    _write_road_cache(cache_path, VMAP.ROAD_CACHE_TAG_SCHEMA, with_way=True)
    layer = OSM.OSM_layer()
    assert OSM.OSM_queries_to_OSM_layer(
        VMAP.BIG_ROADS_QUERIES, layer, 10, 20,
        VMAP.ROADS_TAGS_OF_INTEREST,
        cached_suffix="big_roads",
        node_tags_of_interest=VMAP.ROAD_NODE_TAGS_OF_INTEREST,
        cache_schema=VMAP.ROAD_CACHE_TAG_SCHEMA,
    )
    way_tags = list(layer.dicosmtags["w"].values())
    assert len(way_tags) == 1, way_tags
    tags = way_tags[0]
    assert tags.get("highway") == "primary"
    assert tags.get("cutting") == "yes"
    assert tags.get("layer") == "-1"
    assert tags.get("covered") == "no"
    assert tags.get("embankment") == "yes"
    # An unlisted tag is still dropped: the whitelist grew, it did not
    # become ["all"] (which the AIRPORTS layer keeps, not this one).
    assert "maxspeed" not in tags


def test_the_airport_road_feed_still_carries_the_layer_witness():
    """The per-airport feed's own whitelist is a SEPARATE list whose
    fingerprint re-cuts every sidecar when it grows (a shared-repo write,
    scope ``osm_roadfeed``), so it was deliberately NOT widened here —
    but ``layer``, the witness §45 (1)(d) reads, is already on it."""
    from auto_patch import osm_load

    assert "layer" in osm_load._ROAD_FEED_WAY_TAGS


# ---------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------
def _fake_tile():
    class _Tile:
        lat = 10
        lon = 20
        grass_water_seep = False

    return _Tile()


def _write_road_cache(path, schema, with_way=False):
    """An OSM cache in exactly the shape ``OSM_layer.write_to_file``
    emits (the parser splits every line on ``"``)."""
    os.makedirs(os.path.dirname(str(path)) or ".", exist_ok=True)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>\n',
             '<osm version="0.6" o4_tag_schema="%s">\n' % schema]
    if with_way:
        lines += [
            '  <node id="1" lat="10.1000000" lon="20.1000000" version="1"/>\n',
            '  <node id="2" lat="10.2000000" lon="20.2000000" version="1"/>\n',
            '  <way id="100" version="1">\n',
            '    <nd ref="1"/>\n',
            '    <nd ref="2"/>\n',
            '    <tag k="highway" v="primary"/>\n',
            '    <tag k="cutting" v="yes"/>\n',
            '    <tag k="layer" v="-1"/>\n',
            '    <tag k="covered" v="no"/>\n',
            '    <tag k="embankment" v="yes"/>\n',
            '    <tag k="maxspeed" v="80"/>\n',
            '  </way>\n',
        ]
    lines.append("</osm>\n")
    with bz2.open(str(path), "wt") as handle:
        handle.write("".join(lines))
