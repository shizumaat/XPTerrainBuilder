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
from pathlib import Path

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
# THE MERGED airport_small_roads CACHE'S SCHEMA GATE (RULINGS
# 2026-09-15r chip): the auto-mode per-tile cache used to recycle on
# ``isfile`` alone and was written unstamped, so a pre-existing cache kept
# serving four-key ways after the bump — silently, forever.  It now
# carries the stamp on write and passes the SAME predicate as the
# tile-wide layers on read (``_layer_cache_is_current``); the harness
# names a stale one as a REFRESH before the build and re-derives it under
# ``--refresh-data osm_layers`` through the engine's own derivation.
# ---------------------------------------------------------------------
import json                                                # noqa: E402
import types                                               # noqa: E402

import pytest                                              # noqa: E402

import O4_Airport_Elevation_Insets as INSETS               # noqa: E402
import O4_OSM_Extracts as EXTRACTS                         # noqa: E402


def _auto_roads_fixture(tmp_path, monkeypatch, xml=b"<osm version='0.6'/>"):
    """One inset bbox on tile +35-081, the merged cache under a tmp
    ``OSM_dir``, the extract backend serving ``xml`` (recorded) and
    Overpass forbidden.  Returns ``(cache_path, extract_calls)``."""
    inset_dir = tmp_path / "insets"
    inset_dir.mkdir()
    (inset_dir / "A_usgs3dep.tif").write_bytes(b"")
    (inset_dir / "A_usgs3dep.json").write_text(json.dumps(
        {"bounding_box_wgs84": [-80.9, 35.1, -80.8, 35.2]}),
        encoding="utf-8")
    monkeypatch.setattr(
        INSETS, "list_cached_inset_dems",
        lambda lat, lon, provider_codes=None: [
            str(inset_dir / "A_usgs3dep.tif")])
    monkeypatch.setattr(FNAMES, "OSM_dir", str(tmp_path / "OSM_data"))
    cache_path = FNAMES.osm_cached(35, -81, VMAP.AIRPORT_SMALL_ROADS_SUFFIX)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    extract_calls = []

    def _fake_extracts(statements, boxes, request_description=""):
        extract_calls.append(request_description)
        return xml

    monkeypatch.setattr(
        EXTRACTS, "osm_xml_from_local_extracts", _fake_extracts)
    monkeypatch.setattr(
        OSM, "OSM_query_to_OSM_layer",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("extract-served run must not hit Overpass")))
    return cache_path, extract_calls


def _tile_35_81():
    return types.SimpleNamespace(lat=35, lon=-81, road_level="auto")


def test_the_merged_cache_is_stamped_with_the_road_schema_on_write(
        tmp_path, monkeypatch):
    """A cold derivation writes ``o4_tag_schema="<ROAD_CACHE_TAG_SCHEMA>"``
    on the ``<osm`` root — the marker the engine's own predicate reads."""
    cache_path, extract_calls = _auto_roads_fixture(tmp_path, monkeypatch)
    assert VMAP._airport_auto_roads_layer(_tile_35_81()) is not None
    assert extract_calls == [VMAP.AIRPORT_SMALL_ROADS_SUFFIX]
    assert os.path.isfile(cache_path)
    assert OSM._cached_osm_schema_matches(
        cache_path, VMAP.ROAD_CACHE_TAG_SCHEMA) is True
    assert OSM._cached_osm_schema_matches(cache_path, PREVIOUS_SCHEMA) is False
    with bz2.open(cache_path, "rt", encoding="utf-8") as handle:
        head = handle.readline() + handle.readline()
    assert 'o4_tag_schema="%s"' % VMAP.ROAD_CACHE_TAG_SCHEMA in head


@pytest.mark.parametrize("stale_schema", [PREVIOUS_SCHEMA, None],
                         ids=["old-stamp", "unstamped"])
def test_a_stale_or_unstamped_merged_cache_is_NOT_recycled(
        tmp_path, monkeypatch, stale_schema):
    """THE CHIP: a merged cache under another schema — or with no stamp
    at all, every cache written before this gate — is treated as absent:
    re-derived, and the rewrite carries the current stamp."""
    cache_path, extract_calls = _auto_roads_fixture(tmp_path, monkeypatch)
    if stale_schema is None:
        with bz2.open(cache_path, "wt", encoding="utf-8") as handle:
            handle.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                         '<osm version="0.6" generator="Ortho4XP">\n'
                         '</osm>\n')
    else:
        _write_road_cache(cache_path, stale_schema)
    stale_bytes = open(cache_path, "rb").read()
    recycled = []
    real_update = OSM.OSM_layer.update_dicosm

    def _spy(self, data, input_tags=None, target_tags=None):
        recycled.append(data)
        return real_update(self, data, input_tags, target_tags)

    monkeypatch.setattr(OSM.OSM_layer, "update_dicosm", _spy)
    assert VMAP._airport_auto_roads_layer(_tile_35_81()) is not None
    assert cache_path not in recycled, "a stale cache must never be read"
    assert extract_calls == [VMAP.AIRPORT_SMALL_ROADS_SUFFIX], (
        "exactly one re-derivation")
    assert open(cache_path, "rb").read() != stale_bytes
    assert OSM._cached_osm_schema_matches(
        cache_path, VMAP.ROAD_CACHE_TAG_SCHEMA) is True


def test_a_current_merged_cache_is_recycled_and_never_rewritten(
        tmp_path, monkeypatch):
    cache_path, extract_calls = _auto_roads_fixture(tmp_path, monkeypatch)
    _write_road_cache(cache_path, VMAP.ROAD_CACHE_TAG_SCHEMA, with_way=True)
    before = open(cache_path, "rb").read()
    layer = VMAP._airport_auto_roads_layer(_tile_35_81())
    assert layer is not None
    assert extract_calls == [], "a current cache derives nothing"
    assert open(cache_path, "rb").read() == before
    # And the recycled way carries the depth witnesses through the
    # merged path's own target_tags derivation.
    tags = list(layer.dicosmtags["w"].values())[0]
    assert tags.get("cutting") == "yes" and tags.get("layer") == "-1"


def test_the_bbox_query_entry_gates_and_stamps_like_the_tile_wide_one(
        tmp_path, monkeypatch):
    """``OSM_query_to_OSM_layer`` (the per-bbox entry the merged path and
    the insets use) takes ``cache_schema`` with the same meaning as
    ``OSM_queries_to_OSM_layer``: stamp on write, refuse-and-refetch a
    cache whose stamp differs, accept anything when empty (legacy)."""
    cache = str(tmp_path / "bbox.osm.bz2")
    fetched = []
    monkeypatch.setattr(OSM, "get_overpass_data",
                        lambda q, b: fetched.append(b) or
                        b"<osm version='0.6'/>")
    query = 'way["highway"="service"]'
    bbox = (35.1, -80.9, 35.2, -80.8)
    # 1. cold: fetched and stamped
    assert OSM.OSM_query_to_OSM_layer(
        query, bbox, OSM.OSM_layer(), cached_file_name=cache,
        cache_schema=SCHEMA_OF_RECORD) == 1
    assert fetched == [bbox]
    assert OSM._cached_osm_schema_matches(cache, SCHEMA_OF_RECORD) is True
    # 2. current: recycled, no fetch
    assert OSM.OSM_query_to_OSM_layer(
        query, bbox, OSM.OSM_layer(), cached_file_name=cache,
        cache_schema=SCHEMA_OF_RECORD) == 1
    assert fetched == [bbox]
    # 3. another schema wanted: the cache is refused and refetched
    assert OSM.OSM_query_to_OSM_layer(
        query, bbox, OSM.OSM_layer(), cached_file_name=cache,
        cache_schema="2099-01-01") == 1
    assert fetched == [bbox, bbox]
    assert OSM._cached_osm_schema_matches(cache, "2099-01-01") is True
    # 4. legacy callers (no schema) recycle any cache, and stamp nothing
    assert OSM.OSM_query_to_OSM_layer(
        query, bbox, OSM.OSM_layer(), cached_file_name=cache) == 1
    assert fetched == [bbox, bbox]


# --- the harness side: named as a REFRESH, re-derived under the scope ---

def _harness_build_module():
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "tools",
                        "harness", "build_airport.py")
    spec = importlib.util.spec_from_file_location(
        "road_tag_schema_twin_build", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class _Notes:
    def __init__(self):
        self.lines = []

    def note(self, msg):
        self.lines.append(msg)


def test_the_harness_names_a_stale_merged_cache_under_osm_layers(
        tmp_path, monkeypatch):
    """Before the build, not after: a stale ``airport_small_roads`` cache
    is a REFRESH the plain build refuses, naming ``--refresh-data
    osm_layers`` — the same refusal the tile-wide road layers get."""
    build_mod = _harness_build_module()
    root = tmp_path / "lane"
    monkeypatch.setattr(FNAMES, "OSM_dir", str(root / "OSM_data"))
    monkeypatch.setattr(VMAP, "resolved_road_level", lambda tile: (1, False))
    cache = FNAMES.osm_cached(40, -4, VMAP.AIRPORT_SMALL_ROADS_SUFFIX)
    _write_road_cache(cache, PREVIOUS_SCHEMA)

    missing = build_mod.schema_stale_osm_layers(root, 40, -4)
    assert [m[:2] for m in missing] == [(
        "osm_layers",
        "OSM_data/+40-010/+40-004/+40-004_airport_small_roads.osm.bz2")]
    why = missing[0][2]
    assert "SCHEMA-STALE" in why
    assert PREVIOUS_SCHEMA in why and VMAP.ROAD_CACHE_TAG_SCHEMA in why
    with pytest.raises(SystemExit) as exc:
        build_mod.require_no_implicit_refresh(missing, set())
    assert "--refresh-data osm_layers" in str(exc.value)
    build_mod.require_no_implicit_refresh(missing, {"osm_layers"})

    # unstamped (written before the gate) is stale by the same rule
    with bz2.open(cache, "wt", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                     '<osm version="0.6" generator="Ortho4XP">\n</osm>\n')
    missing = build_mod.schema_stale_osm_layers(root, 40, -4)
    assert len(missing) == 1 and "<no schema marker>" in missing[0][2]

    # current: named by nothing; absent: absence is not staleness
    _write_road_cache(cache, VMAP.ROAD_CACHE_TAG_SCHEMA)
    assert build_mod.schema_stale_osm_layers(root, 40, -4) == []
    os.unlink(cache)
    assert build_mod.schema_stale_osm_layers(root, 40, -4) == []


def test_the_authorised_refresh_re_derives_the_merged_cache_via_the_engine(
        tmp_path, monkeypatch):
    """``--refresh-data osm_layers`` moves the stale merged cache aside and
    calls the ENGINE's own derivation (``_airport_auto_roads_layer``) —
    the prefetch cannot, it has no specification for this cache — then
    reads the verdict off disk through the same naming function."""
    build_mod = _harness_build_module()
    root = tmp_path / "lane"
    monkeypatch.setattr(FNAMES, "OSM_dir", str(root / "OSM_data"))
    monkeypatch.setattr(VMAP, "resolved_road_level", lambda tile: (1, False))
    # the tile-wide layers: present and current, so the prefetch is idle
    for suffix in ("big_roads", "coastline", "water"):
        schema = {"big_roads": VMAP.ROAD_CACHE_TAG_SCHEMA,
                  "water": VMAP.WATER_CACHE_TAG_SCHEMA}.get(suffix, "")
        _write_road_cache(FNAMES.osm_cached(40, -4, suffix), schema)
    prefetch_calls = []
    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer",
                        lambda *a, **k: prefetch_calls.append(a) or 1)
    cache = FNAMES.osm_cached(40, -4, VMAP.AIRPORT_SMALL_ROADS_SUFFIX)
    _write_road_cache(cache, PREVIOUS_SCHEMA)
    stale_bytes = open(cache, "rb").read()
    derived = []

    def _fake_engine_derivation(tile):
        derived.append((tile.lat, tile.lon))
        assert not os.path.exists(cache), "the stale cache is aside"
        _write_road_cache(cache, VMAP.ROAD_CACHE_TAG_SCHEMA)
        return OSM.OSM_layer()

    monkeypatch.setattr(VMAP, "_airport_auto_roads_layer",
                        _fake_engine_derivation)
    prog = _Notes()
    summary = build_mod.refresh_stale_osm_layers(root, 40, -4, prog)
    assert derived == [(40, -4)]
    assert prefetch_calls == [], "nothing tile-wide was stale"
    assert summary["refetched"] == [
        "OSM_data/+40-010/+40-004/+40-004_airport_small_roads.osm.bz2"]
    assert open(cache, "rb").read() != stale_bytes
    assert list(Path(cache).parent.glob("*.stale-*")) == []
    assert build_mod.schema_stale_osm_layers(root, 40, -4) == []

    # and a derivation that brings nothing back restores and refuses
    _write_road_cache(cache, PREVIOUS_SCHEMA)
    before = open(cache, "rb").read()
    monkeypatch.setattr(VMAP, "_airport_auto_roads_layer", lambda tile: None)
    with pytest.raises(SystemExit) as exc:
        build_mod.refresh_stale_osm_layers(root, 40, -4, _Notes())
    assert "re-derived NOTHING" in str(exc.value)
    assert open(cache, "rb").read() == before
    assert list(Path(cache).parent.glob("*.stale-*")) == []


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
