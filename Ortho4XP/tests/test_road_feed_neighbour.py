"""``O4_Vector_Map.ensure_auto_patch_road_feeds`` — every road feed the
auto_patch_v2 reader will touch is made schema-current BEFORE it reads
them, home tile AND the eight neighbours.

THE DEFECT (app engine 1.50.1796, engine-stderr 2026-09-18): tile
+46+006 aborted ALL ELEVEN of its airports in ``build`` on ONE file —
the NEIGHBOUR tile's ``+46+007_big_roads.osm.bz2`` (o4_tag_schema
2026-07-16).  RULINGS 2026-09-17ad had closed this class for the HOME
tile's ``airport_small_roads`` only, and an app user has no
``build_airport.py --refresh-data osm_layers`` to run.

Headless, ``tmp_path``-based, no network: both production writers are
stubbed, so nothing here downloads or touches the shared corpus.
"""

from __future__ import annotations

import bz2
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools",
                                "harness"))

import O4_File_Names as FNAMES                              # noqa: E402
import O4_OSM_Utils as OSM                                  # noqa: E402
import O4_UI_Utils as UI                                    # noqa: E402
import O4_Vector_Map as VMAP                                # noqa: E402

CURRENT = VMAP.ROAD_CACHE_TAG_SCHEMA
SUPERSEDED = "2026-07-16"


def _feed_file(osm_root, lat, lon, feed, schema):
    """One cached feed, laid out exactly as the corpus is.  ``schema``
    None writes NO ``o4_tag_schema`` attribute at all (the pre-17ad
    ``airport_small_roads`` shape)."""
    tile_dir = os.path.join(osm_root,
                            f"{(lat // 10) * 10:+03d}{(lon // 10) * 10:+04d}",
                            f"{lat:+03d}{lon:+04d}")
    os.makedirs(tile_dir, exist_ok=True)
    path = os.path.join(tile_dir, f"{lat:+03d}{lon:+04d}_{feed}.osm.bz2")
    stamp = "" if schema is None else f' o4_tag_schema="{schema}"'
    with bz2.open(path, "wt", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                     f'<osm version="0.6" generator="test"{stamp}>\n'
                     "</osm>\n")
    return path


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """A private OSM corpus root, with the engine pointed at it."""
    osm_root = str(tmp_path / "OSM_data")
    os.makedirs(osm_root, exist_ok=True)
    monkeypatch.setattr(FNAMES, "OSM_dir", osm_root, raising=False)
    monkeypatch.setattr(UI, "red_flag", 0, raising=False)
    return osm_root


@pytest.fixture
def writers(monkeypatch):
    """Both production writers, stubbed: they record the calls and make
    the cache schema-current.  No network, no corpus."""
    calls = {"big_roads": [], "airport_small_roads": []}

    def fake_big(queries, layer, lat, lon, tags_of_interest=(),
                 cached_suffix="", node_tags_of_interest=(),
                 cache_schema="", bbox_margin_degrees=0.0):
        calls["big_roads"].append((lat, lon, cached_suffix, cache_schema))
        _feed_file(FNAMES.OSM_dir, lat, lon, cached_suffix, cache_schema)
        return 1

    def fake_small(lat, lon):
        calls["airport_small_roads"].append((lat, lon))
        _feed_file(FNAMES.OSM_dir, lat, lon, "airport_small_roads", CURRENT)
        return object()

    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer", fake_big)
    monkeypatch.setattr(VMAP, "_airport_auto_roads_layer_at", fake_small)
    monkeypatch.setattr(VMAP, "wait_for_background_osm_prefetch",
                        lambda: None)
    return calls


def _tile(lat, lon):
    return SimpleNamespace(lat=lat, lon=lon)


# ---------------------------------------------------------------------
# 1. The measured defect: a stale NEIGHBOUR feed is re-derived
# ---------------------------------------------------------------------
def test_stale_neighbour_big_roads_is_rederived_before_the_reader(
        corpus, writers):
    """+46+006's abort: the stale file is the NEIGHBOUR +46+007's."""
    _feed_file(corpus, 46, 6, "big_roads", CURRENT)
    _feed_file(corpus, 46, 6, "airport_small_roads", CURRENT)
    stale = _feed_file(corpus, 46, 7, "big_roads", SUPERSEDED)

    derived = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6))

    assert (46, 7, "big_roads") in derived, derived
    assert writers["big_roads"] == [(46, 7, "big_roads", CURRENT)]
    # The reader would now find it current — the refusal cannot fire.
    from auto_patch_v2.airport import osm as v2osm
    assert v2osm.feed_tag_schema(stale) == v2osm.ROAD_CACHE_TAG_SCHEMA


def test_an_unstamped_neighbour_feed_is_rederived_too(corpus, writers):
    """RULINGS 2026-09-17t: no stamp at all is the same fact on weaker
    evidence, and the loader raises on it."""
    _feed_file(corpus, 46, 6, "big_roads", CURRENT)
    _feed_file(corpus, 47, 6, "airport_small_roads", None)

    derived = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6))

    assert (47, 6, "airport_small_roads") in derived, derived
    assert (47, 6) in writers["airport_small_roads"]


def test_an_absent_neighbour_feed_is_never_downloaded(corpus, writers):
    """Absence is lawful — the reader treats a missing tile as an empty
    feed — so a tile build must never widen into its neighbours'
    downloads.  Only the HOME tile's own airport_small_roads is derived
    when absent (RULINGS 2026-09-17ad)."""
    _feed_file(corpus, 46, 6, "big_roads", CURRENT)
    # nothing else on disk anywhere in the 3x3 square

    derived = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6))

    assert derived == [(46, 6, "airport_small_roads")]
    assert writers["big_roads"] == []


# ---------------------------------------------------------------------
# 2. A current corpus costs one header read per feed, nothing else
# ---------------------------------------------------------------------
def test_a_current_corpus_costs_only_the_header_read(corpus, writers,
                                                     monkeypatch):
    present = []
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            for feed in ("big_roads", "airport_small_roads"):
                present.append(
                    _feed_file(corpus, 46 + dlat, 6 + dlon, feed, CURRENT))

    reads = []
    real = OSM._cached_osm_schema_matches

    def counting(path, schema):
        reads.append(path)
        return real(path, schema)

    monkeypatch.setattr(OSM, "_cached_osm_schema_matches", counting)

    derived = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6))

    assert derived == []
    assert writers["big_roads"] == [] and writers["airport_small_roads"] == []
    # EXACTLY one header read per feed on disk — no parse, no re-read.
    assert sorted(reads) == sorted(present)
    assert len(reads) == 18


# ---------------------------------------------------------------------
# 3. Under the harness's armed guard the write is REFUSED and NAMED
# ---------------------------------------------------------------------
def test_the_armed_shared_repo_guard_still_refuses_and_names_the_write(
        tmp_path, corpus, monkeypatch):
    """Never a build side effect there (owner ruling e9daef5).  The
    refusal is a RuntimeError, so nothing on this path may swallow it."""
    import shared_repo_guard as GUARD

    stale = _feed_file(corpus, 46, 7, "big_roads", SUPERSEDED)

    def writing_big(queries, layer, lat, lon, tags_of_interest=(),
                    cached_suffix="", node_tags_of_interest=(),
                    cache_schema="", bbox_margin_degrees=0.0):
        # what the real writer does at the end: it writes the cache file
        with open(_feed_path(lat, lon, cached_suffix), "wb") as handle:
            handle.write(b"x")
        return 1

    def _feed_path(lat, lon, feed):
        return os.path.join(
            FNAMES.OSM_dir,
            f"{(lat // 10) * 10:+03d}{(lon // 10) * 10:+04d}",
            f"{lat:+03d}{lon:+04d}", f"{lat:+03d}{lon:+04d}_{feed}.osm.bz2")

    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer", writing_big)
    monkeypatch.setattr(VMAP, "wait_for_background_osm_prefetch",
                        lambda: None)
    monkeypatch.setattr(VMAP, "_airport_auto_roads_layer_at",
                        lambda lat, lon: None)

    guard = GUARD.SharedRepoWriteGuard(requested=(), root=str(tmp_path),
                                       repo=str(tmp_path))
    with pytest.raises(GUARD.SharedRepoWriteBlocked) as excinfo:
        with guard:
            VMAP.ensure_auto_patch_road_feeds(_tile(46, 6))

    assert "OSM_data" in str(excinfo.value)
    assert "+46+007_big_roads" in str(excinfo.value)
    assert "--refresh-data" in str(excinfo.value)
    assert [b["path"] for b in guard.blocked]
    # and the corpus is unchanged: the stale bytes are still stale
    from auto_patch_v2.airport import osm as v2osm
    assert v2osm.feed_tag_schema(stale) == SUPERSEDED
