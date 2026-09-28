"""§37 (11) (7) THE SHORE-STRUCTURE FEED (issue #72).

The quay wall stands only where OSM DECLARES a built shore
(``planar.zones.shore_declarations`` over ``Airport.osm_ways``), and no
cached feed carried ``man_made=quay`` & co. — so every coast read natural,
VMMC's 15f quay included.  A per-tile ``shore_structures`` feed is now
filled by the explicit ``--refresh-data shore`` and read by the v2 loader
with ITS OWN tag whitelist.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "src", ROOT / "tools" / "harness", ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from auto_patch_v2.airport import osm as _osm                  # noqa: E402
from auto_patch_v2.planar.zones import (                       # noqa: E402
    SHORE_WALL_TAGS, shore_declarations)

_FEED = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" o4_tag_schema="2026-09-28">
  <node id="-1" lat="22.1500" lon="113.5700"/>
  <node id="-2" lat="22.1500" lon="113.5710"/>
  <node id="-3" lat="22.1510" lon="113.5710"/>
  <node id="-4" lat="22.9000" lon="113.9000"/>
  <node id="-5" lat="22.9000" lon="113.9010"/>
  <way id="-10">
    <nd ref="-1"/><nd ref="-2"/><nd ref="-3"/>
    <tag k="man_made" v="quay"/>
    <tag k="highway" v="footway"/>
    <tag k="name" v="Cais"/>
  </way>
  <way id="-11">
    <nd ref="-4"/><nd ref="-5"/>
    <tag k="barrier" v="seawall"/>
  </way>
</osm>
"""


def _write_feed(root: Path, lat: int, lon: int) -> Path:
    d = Path(_osm.tile_dir(str(root), lat, lon))
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{lat:+03d}{lon:+04d}_{_osm.SHORE_FEED}.osm"
    p.write_text(_FEED)
    return p


def test_the_shore_feed_is_a_loader_feed_with_its_own_whitelist(tmp_path):
    assert _osm.SHORE_FEED in _osm.FEEDS
    _write_feed(tmp_path, 22, 113)
    doc = _osm.load_feed(str(tmp_path), _osm.SHORE_FEED, 22.15, 113.57)
    assert [w.id for w in doc.ways] == ["+22+113:-10"], (
        "the selection box keeps the quay and drops the far seawall")
    quay = doc.ways[0]
    assert quay.tags == {"man_made": "quay", "name": "Cais"}, (
        "the shore feed keeps its own tags only — a pier that is also a "
        "footway must not arrive a second time as a road")
    assert doc.tag_schemas[0][1] == _osm.SHORE_CACHE_TAG_SCHEMA


def test_the_general_feeds_still_drop_the_shore_tags(tmp_path):
    d = Path(_osm.tile_dir(str(tmp_path), 22, 113))
    d.mkdir(parents=True)
    (d / "+22+113_airports.osm").write_text(_FEED)
    doc = _osm.load_feed(str(tmp_path), "airports", 22.15, 113.57)
    assert doc.ways[0].tags == {"highway": "footway", "name": "Cais"}


def test_a_loaded_quay_is_a_shore_declaration(tmp_path):
    _write_feed(tmp_path, 22, 113)
    doc = _osm.load_feed(str(tmp_path), _osm.SHORE_FEED, 22.15, 113.57)
    lines = shore_declarations(doc.ways)
    assert len(lines) == 1 and len(lines[0].coords) == 3


def test_the_engine_query_list_is_the_readers_tag_list():
    """``O4_Vector_Map`` must not import the planar stage, so it spells
    the list itself — twin-asserted equal, like the road schema."""
    import O4_Vector_Map as VM
    assert {k: frozenset(v) for k, v in VM.SHORE_STRUCTURE_TAGS.items()} \
        == dict(SHORE_WALL_TAGS)
    stmts = set(VM.SHORE_STRUCTURE_QUERIES[0])
    assert stmts == {f'way["{k}"="{v}"]' for k, vals in
                     SHORE_WALL_TAGS.items() for v in vals}
    assert VM.SHORE_STRUCTURE_CACHE_TAG_SCHEMA == _osm.SHORE_CACHE_TAG_SCHEMA
    assert VM.SHORE_STRUCTURE_SUFFIX == _osm.SHORE_FEED
    assert set(SHORE_WALL_TAGS) <= set(VM.SHORE_STRUCTURE_TAGS_OF_INTEREST)
    assert set(VM.SHORE_STRUCTURE_TAGS_OF_INTEREST) == set(
        _osm.SHORE_TAGS_OF_INTEREST)


def test_the_engine_query_parses_into_the_cache_writers_tag_pairs():
    """The OSM cache writer reads each statement as ``items[1]`` /
    ``items[3]`` of a ``'"'`` split — every shore statement must parse."""
    import O4_Vector_Map as VM
    for stmt in VM.SHORE_STRUCTURE_QUERIES[0]:
        items = stmt.split('"')
        assert stmt.startswith("way[") and items[1] in SHORE_WALL_TAGS
        assert items[3] in SHORE_WALL_TAGS[items[1]]


def test_the_shore_fill_is_its_own_refresh_scope():
    import shared_repo_guard as G
    rel = "OSM_data/+20+110/+22+113/+22+113_shore_structures.osm.bz2"
    assert G.scope_of(rel) == "shore"
    assert G.scope_of("OSM_data/+20+110/+22+113/+22+113_big_roads.osm.bz2") \
        == "osm_layers"
    assert "shore" in {s for s, _p, _w in G.REFRESH_SCOPES}
    assert "#72" in G.scope_description("shore")
