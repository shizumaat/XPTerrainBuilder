"""Airport-region road feed: source selection, extraction, sidecar cache,
loud absence, and the shared corridor-union law.

Headless and hermetic: the "regional extract clip" is a hand-written OSM
XML fixture (the extract filter reads ``.osm`` / ``.osm.bz2`` / ``.osm.pbf``
alike), the clip LOOKUP is stubbed so nothing touches the real store, and
``O4_File_Names.OSM_dir`` points at ``tmp_path`` so sidecars and tile
caches land there.  No network, no X-Plane install, no production data
root.

What is deliberately NOT tested here: that the feed changes the emitted
patch.  It must not — it is a foundation, published on the layout for the
classification-refinement and inset-road-grading features, with no
existing consumer rewired.  That property is verified by an A/B build
(gate ON vs OFF, byte-identical patches), not by a unit test.
"""

from __future__ import annotations

import bz2
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
from auto_patch import clearance as CLEARANCE  # noqa: E402
from auto_patch import config as CONFIG  # noqa: E402
from auto_patch import osm_load as OSM_LOAD  # noqa: E402
from auto_patch.layout import PavementLayout  # noqa: E402


# ── fixtures ─────────────────────────────────────────────────────────
# A patch of road network around 30.10N 31.40E (HECA's neighbourhood):
# three drivable ways of classes the tile ``small_roads`` cache would
# never hold at default config (service / residential / track), one rail,
# and one way that is NOT a road at all (it must be dropped).
_WAYS = [
    ("101", "service", [(30.100, 31.400), (30.102, 31.400)],
     {"service": "driveway"}),
    ("102", "residential", [(30.101, 31.401), (30.101, 31.404)],
     {"lanes": "2"}),
    ("103", "track", [(30.099, 31.399), (30.098, 31.398)], {}),
]
_RAIL_WAY = ("104", [(30.103, 31.400), (30.103, 31.406)])
_NON_ROAD_WAY = ("105", [(30.104, 31.400), (30.104, 31.402)])

# Query box comfortably containing every way above.
_BOX = (30.09, 31.39, 30.11, 31.41)


def _osm_xml() -> bytes:
    """OSM XML for the fixture network (the extract filter's own input
    format, so no pbf writer is needed to build a test 'clip')."""
    nodes = []
    elements = []
    node_id = 1

    def add_way(way_id, points, tags):
        nonlocal node_id
        refs = []
        for latitude, longitude in points:
            nodes.append(
                '  <node id="%d" lat="%.6f" lon="%.6f" version="1"/>'
                % (node_id, latitude, longitude))
            refs.append(node_id)
            node_id += 1
        body = "".join(
            '    <nd ref="%d"/>\n' % ref for ref in refs)
        body += "".join(
            '    <tag k="%s" v="%s"/>\n' % (key, value)
            for key, value in tags.items())
        elements.append(
            '  <way id="%s" version="1">\n%s  </way>' % (way_id, body))

    for way_id, highway, points, extra in _WAYS:
        add_way(way_id, points, dict({"highway": highway}, **extra))
    add_way(_RAIL_WAY[0], _RAIL_WAY[1], {"railway": "rail"})
    add_way(_NON_ROAD_WAY[0], _NON_ROAD_WAY[1], {"waterway": "ditch"})
    return ("<?xml version='1.0' encoding='UTF-8'?>\n"
            "<osm version=\"0.6\" generator=\"test\">\n"
            + "\n".join(nodes) + "\n"
            + "\n".join(elements) + "\n</osm>\n").encode("utf-8")


@pytest.fixture
def clip(tmp_path):
    """A stand-in regional-extract clip part on disk."""
    path = tmp_path / "clip_+030+0031_deadbeef-part0.osm"
    path.write_bytes(_osm_xml())
    return str(path)


@pytest.fixture
def osm_dir(tmp_path, monkeypatch):
    """Point every FNAMES OSM path at tmp_path (sidecars, tile caches)."""
    directory = tmp_path / "OSM_data"
    directory.mkdir()
    monkeypatch.setattr(FNAMES, "OSM_dir", str(directory))
    OSM_LOAD._load_osm_road_layer.cache_clear()
    OSM_LOAD._load_osm_tile.cache_clear()
    yield directory
    OSM_LOAD._load_osm_road_layer.cache_clear()
    OSM_LOAD._load_osm_tile.cache_clear()


def _layout(icao="TEST"):
    """A layout whose anchor sits in the fixture network, with no
    geometry — the query box then falls back to the anchor square, which
    covers the fixture."""
    return PavementLayout(icao=icao, anchor=(30.101, 31.401))


def _serve_clip(monkeypatch, clip_path):
    monkeypatch.setattr(OSM_LOAD, "_regional_clip_parts_for_box",
                        lambda box: [clip_path])


def _serve_nothing(monkeypatch):
    monkeypatch.setattr(OSM_LOAD, "_regional_clip_parts_for_box",
                        lambda box: None)


# ── extraction ───────────────────────────────────────────────────────
def test_extract_region_roads_keeps_roads_and_rails_only(clip):
    nodes, ways, _node_tags = OSM_LOAD._extract_region_roads([clip], _BOX)
    assert len(ways) == 4, "3 highways + 1 railway, the ditch dropped"
    highways = sorted(w[2]["highway"] for w in ways if w[2].get("highway"))
    assert highways == ["residential", "service", "track"]
    assert sum(1 for w in ways if w[2].get("railway") == "rail") == 1
    # Every way's nodes resolve (the filter drags in the full closure).
    for _way_id, refs, _tags in ways:
        assert refs and all(ref in nodes for ref in refs)


def test_extract_keeps_the_tags_widths_need(clip):
    _nodes, ways, _node_tags = OSM_LOAD._extract_region_roads([clip], _BOX)
    by_class = {w[2].get("highway"): w[2] for w in ways}
    assert by_class["service"]["service"] == "driveway"
    assert by_class["residential"]["lanes"] == "2"


def test_query_box_is_padded_and_rounded():
    from shapely.geometry import box as shapely_box
    layout = _layout()
    layout.runway_union = shapely_box(-500.0, -200.0, 500.0, 200.0)
    feed_box = OSM_LOAD._airport_road_feed_box(layout, 500.0)
    lat_min, lon_min, lat_max, lon_max = feed_box
    assert lat_min < 30.101 < lat_max and lon_min < 31.401 < lon_max
    # 400 m of runway span + 500 m of pad each side = 1,400 m ≈ 0.0126°
    # of latitude, rounded outward to the 0.001° grid.
    assert 0.012 < lat_max - lat_min < 0.016
    # 2,000 m east-west, and a degree of longitude is shorter at 30°N.
    assert lon_max - lon_min > 0.020
    quantum = OSM_LOAD._ROAD_FEED_BOX_QUANTUM_DEG
    for value in feed_box:
        assert abs(value / quantum - round(value / quantum)) < 1e-6


# ── source selection + publication ───────────────────────────────────
def test_feed_published_from_regional_clip(clip, osm_dir, monkeypatch):
    _serve_clip(monkeypatch, clip)
    layout = _layout("HECA")
    network = OSM_LOAD._load_airport_road_network(layout)
    assert network is layout.airport_road_network
    assert network.source == "regional_extract"
    assert network.road_way_count == 3
    assert network.rail_way_count == 1
    # Carriageway widths are resolved once, for every way.
    assert set(network.widths) == {w[0] for w in network.ways}
    assert all(width > 0.0 for width in network.widths.values())


def test_tile_small_roads_cache_wins_when_present(clip, osm_dir,
                                                  monkeypatch):
    """A user who raised ``road_level`` keeps the pre-feed source."""
    for layer in ("big_roads", "small_roads"):
        path = FNAMES.osm_cached(30, 31, layer)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with bz2.open(path, "wb") as cache_file:
            cache_file.write(_osm_xml())
    OSM_LOAD._load_osm_road_layer.cache_clear()
    _serve_clip(monkeypatch, clip)
    layout = _layout()
    network = OSM_LOAD._load_airport_road_network(layout)
    assert network.source == "tile_cache"
    # big_roads + the "S|"-namespaced small_roads copy of the same
    # fixture: every way appears once per layer, never merged by id.
    assert network.road_way_count == 6
    assert len({way[0] for way in network.ways}) == len(network.ways)


def test_no_road_data_anywhere_is_loud(osm_dir, monkeypatch, capsys):
    _serve_nothing(monkeypatch)
    layout = _layout("NONE")
    assert OSM_LOAD._load_airport_road_network(layout) is None
    assert layout.airport_road_network is None
    message = capsys.readouterr().out
    assert "NO ROAD DATA" in message
    assert "without road evidence" in message
    assert message.count("NO ROAD DATA") == 1, "one line, not per way"


def test_a_road_free_region_is_loud_too(clip, osm_dir, monkeypatch, capsys):
    """A clip that simply holds no road near the field is the same
    evidence-less state as a missing one, and says so."""
    _serve_clip(monkeypatch, clip)
    monkeypatch.setattr(OSM_LOAD, "_extract_region_roads",
                        lambda parts, box: ({}, [], {}))
    layout = _layout("BARE")
    network = OSM_LOAD._load_airport_road_network(layout)
    assert network is not None and network.ways == []
    assert "NO ROAD DATA" in capsys.readouterr().out
    # The empty result is still cached — no re-parse per build.
    assert os.path.isfile(os.path.join(
        str(osm_dir), OSM_LOAD._ROAD_FEED_DIR_NAME, "BARE_road_feed.cache"))


def test_gate_off_publishes_nothing(clip, osm_dir, monkeypatch):
    monkeypatch.setattr(CONFIG, "AIRPORT_ROAD_FEED", False)
    _serve_clip(monkeypatch, clip)
    layout = _layout()
    assert OSM_LOAD._load_airport_road_network(layout) is None
    assert layout.airport_road_network is None


# ── sidecar cache ────────────────────────────────────────────────────
def test_sidecar_hit_on_second_load(clip, osm_dir, monkeypatch):
    _serve_clip(monkeypatch, clip)
    calls = []
    real_extract = OSM_LOAD._extract_region_roads

    def counting_extract(parts, box):
        calls.append(box)
        return real_extract(parts, box)

    monkeypatch.setattr(OSM_LOAD, "_extract_region_roads", counting_extract)
    first = OSM_LOAD._load_airport_road_network(_layout("HECA"))
    second = OSM_LOAD._load_airport_road_network(_layout("HECA"))
    assert len(calls) == 1, "the second build must not re-parse the clip"
    assert second.source == "regional_extract"
    assert (second.road_way_count, second.rail_way_count) == (
        first.road_way_count, first.rail_way_count)
    assert [w[0] for w in second.ways] == [w[0] for w in first.ways]
    assert second.widths == first.widths
    sidecar = os.path.join(str(osm_dir), OSM_LOAD._ROAD_FEED_DIR_NAME,
                           "HECA_road_feed.cache")
    assert os.path.isfile(sidecar)


def test_sidecar_invalidated_when_the_clip_changes(clip, osm_dir,
                                                   monkeypatch):
    _serve_clip(monkeypatch, clip)
    calls = []
    real_extract = OSM_LOAD._extract_region_roads

    def counting_extract(parts, box):
        calls.append(box)
        return real_extract(parts, box)

    monkeypatch.setattr(OSM_LOAD, "_extract_region_roads", counting_extract)
    OSM_LOAD._load_airport_road_network(_layout("HECA"))
    # A re-downloaded extract re-cuts the clip: size and mtime change.
    with open(clip, "ab") as clip_file:
        clip_file.write(b"<!-- extract refreshed -->\n")
    OSM_LOAD._load_airport_road_network(_layout("HECA"))
    assert len(calls) == 2, "a changed clip must invalidate the sidecar"


def test_sidecar_invalidated_when_the_query_box_changes(clip, osm_dir,
                                                        monkeypatch):
    from shapely.geometry import box as shapely_box
    _serve_clip(monkeypatch, clip)
    calls = []
    real_extract = OSM_LOAD._extract_region_roads
    monkeypatch.setattr(
        OSM_LOAD, "_extract_region_roads",
        lambda parts, box: (calls.append(box), real_extract(parts, box))[1])
    OSM_LOAD._load_airport_road_network(_layout("HECA"))
    grown = _layout("HECA")
    grown.runway_union = shapely_box(-2000.0, -2000.0, 2000.0, 2000.0)
    OSM_LOAD._load_airport_road_network(grown)
    assert len(calls) == 2
    assert calls[0] != calls[1]


def test_cache_gate_off_neither_reads_nor_writes(clip, osm_dir,
                                                 monkeypatch):
    monkeypatch.setattr(CONFIG, "AIRPORT_ROAD_FEED_CACHE", False)
    _serve_clip(monkeypatch, clip)
    calls = []
    real_extract = OSM_LOAD._extract_region_roads
    monkeypatch.setattr(
        OSM_LOAD, "_extract_region_roads",
        lambda parts, box: (calls.append(box), real_extract(parts, box))[1])
    OSM_LOAD._load_airport_road_network(_layout("HECA"))
    OSM_LOAD._load_airport_road_network(_layout("HECA"))
    assert len(calls) == 2
    assert not os.path.isdir(
        os.path.join(str(osm_dir), OSM_LOAD._ROAD_FEED_DIR_NAME))


def _stub_clip_store(tmp_path, monkeypatch, clip_name):
    """A clips directory holding one cached clip, with the EXACT-key
    lookup deliberately missing — only the same-area fallback can find it."""
    import O4_OSM_Extracts as EXTRACTS
    import json
    directory = tmp_path / "clips"
    directory.mkdir()
    (directory / (clip_name + "-part0.osm")).write_bytes(_osm_xml())
    (directory / (clip_name + ".parts.json")).write_text(
        json.dumps([clip_name + "-part0.osm"]))
    monkeypatch.setattr(EXTRACTS, "_clip_directory", lambda: str(directory))
    monkeypatch.setattr(EXTRACTS, "extracts_enabled", lambda: True)
    monkeypatch.setattr(EXTRACTS, "covering_regions",
                        lambda box: [("egypt", "https://example.invalid")])
    monkeypatch.setattr(EXTRACTS, "_clip_path",
                        lambda regions, clip_box: str(
                            directory / "clip_no_such_exact_key"))
    return directory


def test_same_area_clip_serves_a_box_the_exact_key_misses(tmp_path,
                                                          monkeypatch):
    """The clip on disk is cut for whatever hull its cutter was called
    with, so an airport-sized box hashes to a different key (SPJC got NO
    ROAD DATA off a clip that covered it).  A same-prefix clip covers the
    whole degree square, so it serves."""
    _stub_clip_store(tmp_path, monkeypatch, "clip_+030+0031_wider")
    parts = OSM_LOAD._regional_clip_parts_for_box(_BOX)
    assert parts and parts[0].endswith("clip_+030+0031_wider-part0.osm")


def test_same_area_clip_covers_a_box_just_past_the_degree_line(
        tmp_path, monkeypatch):
    """Every clip box is padded by 0.05°, so a box that pokes a few
    hundred metres into the next degree is still provably covered.  SPJC's
    3.4 km north-south runway does exactly that (its box reaches 0.007°
    past −12°) and was refused before the pad was accounted for."""
    _stub_clip_store(tmp_path, monkeypatch, "clip_+030+0031_wider")
    just_past = (30.98, 31.98, 31.007, 32.007)
    assert OSM_LOAD._regional_clip_parts_for_box(just_past)


def test_same_area_clip_refused_beyond_the_guaranteed_extent(
        tmp_path, monkeypatch):
    """Past the pad there is no coverage guarantee — refuse rather than
    serve a silently truncated road network."""
    _stub_clip_store(tmp_path, monkeypatch, "clip_+030+0031_wider")
    straddling = (30.9, 31.9, 31.1, 32.1)
    assert OSM_LOAD._regional_clip_parts_for_box(straddling) is None


def test_clip_lookup_never_cuts_or_downloads(monkeypatch):
    """The lookup is strictly read-only: absent clip ⇒ None, never a cut
    (minutes) or a country download (network) inside an airport build."""
    import O4_OSM_Extracts as EXTRACTS

    def explode(*_args, **_kwargs):  # pragma: no cover - must not run
        raise AssertionError("the road feed must not cut or download")

    monkeypatch.setattr(EXTRACTS, "_clip_for_query", explode)
    monkeypatch.setattr(EXTRACTS, "osm_xml_from_local_extracts", explode)
    monkeypatch.setattr(EXTRACTS, "covering_regions", lambda box: None)
    assert OSM_LOAD._regional_clip_parts_for_box(_BOX) is None


# ── the shared corridor union ────────────────────────────────────────
def test_feed_corridors_use_the_shared_law(clip, osm_dir, monkeypatch):
    _serve_clip(monkeypatch, clip)
    layout = _layout("HECA")
    network = OSM_LOAD._load_airport_road_network(layout)
    union = CLEARANCE.airport_road_feed_corridors(layout, layout.ll_to_m)
    assert union is not None and union.area > 0.0
    direct = CLEARANCE.road_corridors_from_ways(
        network.nodes, network.ways, layout.ll_to_m,
        widths=network.widths)
    assert union.equals(direct)


def test_feed_corridors_are_memoized_separately_from_clearance(
        clip, osm_dir, monkeypatch):
    """Clearance's own memo must stay untouched — it is the byte-identity
    guarantee for every airport built today."""
    _serve_clip(monkeypatch, clip)
    layout = _layout("HECA")
    OSM_LOAD._load_airport_road_network(layout)
    first = CLEARANCE.airport_road_feed_corridors(layout, layout.ll_to_m)
    assert layout._airport_road_feed_corridors_cache == (first,)
    assert layout._surface_road_corridors_cache is None
    second = CLEARANCE.airport_road_feed_corridors(layout, layout.ll_to_m)
    assert second is first


def test_feed_corridors_none_without_a_feed():
    layout = _layout()
    assert CLEARANCE.airport_road_feed_corridors(
        layout, layout.ll_to_m) is None
    assert layout._airport_road_feed_corridors_cache == (None,)


def test_corridor_law_skips_tunnels():
    """Same exclusion the skirt reader has always applied: filling over a
    tunnel is lawful, so a tunnel way contributes no corridor."""
    nodes = {"a": (30.100, 31.400), "b": (30.102, 31.400)}
    surface = [("1", ["a", "b"], {"highway": "service"})]
    tunnelled = [("1", ["a", "b"], {"highway": "service", "tunnel": "yes"})]
    to_m = _layout().ll_to_m
    assert CLEARANCE.road_corridors_from_ways(nodes, surface, to_m) is not None
    assert CLEARANCE.road_corridors_from_ways(nodes, tunnelled, to_m) is None
