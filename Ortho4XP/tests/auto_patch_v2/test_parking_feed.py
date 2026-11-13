"""#1854 / #1338 THE PARKING FEED.

``Evidence.parking_polys`` was read by the ``[lot]`` rung
(``rules.lot.parking_cover_fraction``) but no cached feed carried
``amenity=parking`` — the airports layer queries ``aeroway`` only — so the
rung never fired on any airport.  A per-tile ``parking`` feed is now
filled by ``O4_Vector_Map.fetch_parking`` (``--refresh-data parking`` in
the harness, the auto-patch step in a tile build) and read by the v2
loader with ITS OWN tag whitelist.
"""
from __future__ import annotations

import dataclasses as _dc
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "src", ROOT / "tools" / "harness", ROOT / "tools",
          Path(__file__).resolve().parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from auto_patch_v2.airport import osm as _osm                  # noqa: E402
from auto_patch_v2.classify import load_rules                  # noqa: E402
from auto_patch_v2.classify.evidence import build_evidence      # noqa: E402
from auto_patch_v2.classify.sources import classify_sources     # noqa: E402
from auto_patch_v2.law import Law                              # noqa: E402
from auto_patch_v2.model.airport import OsmWay                 # noqa: E402
from test_classify import _rect, _synthetic                    # noqa: E402

_FEED = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" o4_tag_schema="2026-11-13">
  <node id="-1" lat="22.1500" lon="113.5700"/>
  <node id="-2" lat="22.1500" lon="113.5710"/>
  <node id="-3" lat="22.1510" lon="113.5710"/>
  <way id="-10">
    <nd ref="-1"/><nd ref="-2"/><nd ref="-3"/><nd ref="-1"/>
    <tag k="amenity" v="parking"/>
    <tag k="parking" v="multi-storey"/>
    <tag k="building" v="parking"/>
    <tag k="layer" v="1"/>
    <tag k="name" v="Car Park"/>
  </way>
</osm>
"""


def test_the_parking_feed_is_a_loader_feed_with_its_own_whitelist(tmp_path):
    assert _osm.PARKING_FEED in _osm.FEEDS
    d = Path(_osm.tile_dir(str(tmp_path), 22, 113))
    d.mkdir(parents=True)
    (d / f"+22+113_{_osm.PARKING_FEED}.osm").write_text(
        _FEED, encoding="utf-8", newline="")
    doc = _osm.load_feed(str(tmp_path), _osm.PARKING_FEED, 22.15, 113.57)
    assert len(doc.ways) == 1
    assert doc.ways[0].tags == {"amenity": "parking", "parking": "multi-storey",
                                "name": "Car Park"}, (
        "no building / layer: a mapped garage must not arrive as a second "
        "building or as a deck")
    assert doc.tag_schemas[0][1] == _osm.PARKING_CACHE_TAG_SCHEMA


def test_the_engine_writer_is_the_readers_twin():
    import O4_Vector_Map as VM
    assert VM.PARKING_SUFFIX == _osm.PARKING_FEED
    assert VM.PARKING_CACHE_TAG_SCHEMA == _osm.PARKING_CACHE_TAG_SCHEMA
    assert set(VM.PARKING_TAGS_OF_INTEREST) == set(_osm.PARKING_TAGS_OF_INTEREST)
    for stmt in VM.PARKING_QUERIES[0]:
        items = stmt.split('"')          # the cache writer's own parse
        assert (items[1], items[3]) == ("amenity", "parking")


def test_the_parking_fill_is_its_own_refresh_scope():
    import shared_repo_guard as G
    rel = "OSM_data/-50+170/-42+174/-42+174_parking.osm.bz2"
    assert G.scope_of(rel) == "parking"
    assert G.scope_of("OSM_data/-50+170/-42+174/-42+174_airports.osm.bz2") \
        == "osm_layers"
    assert "#1854" in G.scope_description("parking")


# ── the rung reads it ────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _parked(cover: float, **tags):
    """The synthetic airport's detached ``island`` page (800..900 x
    300..400: no road, no taxi centreline, no startup) with a mapped car
    park over ``cover`` of it."""
    a = _synthetic(gate=True)
    y1 = 300.0 + 100.0 * cover
    lot = OsmWay(99, _osm.PARKING_FEED,
                 _rect(800.0, 300.0, 900.0, y1) + ((800.0, 300.0),), True,
                 {"amenity": "parking", **tags})
    return _dc.replace(a, osm_ways=a.osm_ways + (lot,))


def _island(a, law):
    rules = load_rules()
    ev = build_evidence(a, rules, law.tables.structures.building_pad.min_area_m2)
    return ev, {r.id: r for r in classify_sources(a, ev, rules)[0]}["island"]


def test_a_mapped_car_park_makes_the_page_a_lot(law):
    ev, rec = _island(_synthetic(gate=True), law)
    assert ev.parking_polys == [] and rec.cls != "lot", rec
    ev, rec = _island(_parked(0.8), law)
    assert len(ev.parking_polys) == 1
    assert rec.parking_cover == pytest.approx(0.8, abs=0.02)
    assert rec.cls == "lot" and "amenity=parking" in rec.reason, rec


def test_below_the_rule_s_fraction_the_rung_is_silent(law):
    _ev, rec = _island(_parked(0.3), law)
    assert rec.cls != "lot", rec


def test_an_underground_car_park_is_not_surface_evidence(law):
    ev, rec = _island(_parked(1.0, parking="underground"), law)
    assert ev.parking_polys == [] and rec.cls != "lot", rec
