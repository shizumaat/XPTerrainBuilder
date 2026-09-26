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

    derived = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6)).derived

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

    derived = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6)).derived

    assert (47, 6, "airport_small_roads") in derived, derived
    assert (47, 6) in writers["airport_small_roads"]


def test_an_absent_neighbour_feed_is_never_downloaded(corpus, writers):
    """Absence is lawful — the reader treats a missing tile as an empty
    feed — so a tile build must never widen into its neighbours'
    downloads.  Only the HOME tile's own airport_small_roads is derived
    when absent (RULINGS 2026-09-17ad)."""
    _feed_file(corpus, 46, 6, "big_roads", CURRENT)
    # nothing else on disk anywhere in the 3x3 square

    derived = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6)).derived

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

    derived = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6)).derived

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


# ---------------------------------------------------------------------
# 4. THE OFFLINE RESIDUAL (issue #24): what could NOT be refreshed
# ---------------------------------------------------------------------
def test_a_feed_that_could_not_be_refreshed_is_reported_still_stale(
        corpus, monkeypatch):
    """Offline (no extract, the download failed) both writers leave the
    STALE bytes on the disk — a stale corpus beats an absent one — so
    the v2 reader will refuse this exact file.  The pre-check hands it
    back instead of letting each airport's worker discover it."""
    stale = _feed_file(corpus, 46, 7, "big_roads", SUPERSEDED)
    _feed_file(corpus, 46, 6, "big_roads", CURRENT)
    _feed_file(corpus, 46, 6, "airport_small_roads", CURRENT)
    # Offline: neither writer brings anything back, neither rewrites.
    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer",
                        lambda *a, **k: 0)
    monkeypatch.setattr(VMAP, "_airport_auto_roads_layer_at",
                        lambda lat, lon: None)
    monkeypatch.setattr(VMAP, "wait_for_background_osm_prefetch",
                        lambda: None)

    precheck = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6))

    assert precheck.derived == []
    assert precheck.stale == [(46, 7, "big_roads", stale)]


def test_an_absent_feed_is_never_reported_stale(corpus, monkeypatch):
    """Absence is lawful and the reader reads it as an empty feed, so a
    home ``airport_small_roads`` that could not be derived is NOT a
    cause — reporting it would abort a tile the reader accepts."""
    _feed_file(corpus, 46, 6, "big_roads", CURRENT)
    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer",
                        lambda *a, **k: 0)
    monkeypatch.setattr(VMAP, "_airport_auto_roads_layer_at",
                        lambda lat, lon: None)
    monkeypatch.setattr(VMAP, "wait_for_background_osm_prefetch",
                        lambda: None)

    precheck = VMAP.ensure_auto_patch_road_feeds(_tile(46, 6))

    assert precheck.derived == []
    assert precheck.stale == []


def test_the_still_stale_feeds_reach_the_driver(corpus, monkeypatch):
    """The wiring: ``run_auto_patch_generation`` hands the residual to
    ``generate_auto_patches``, which owns the app-facing copy."""
    import auto_patch.driver as DRIVER

    residual = [(46, 7, "big_roads", "/corpus/+46+007_big_roads.osm.bz2")]
    monkeypatch.setattr(
        VMAP, "ensure_auto_patch_road_feeds",
        lambda tile: VMAP.RoadFeedPrecheck([], residual))
    monkeypatch.setattr(VMAP, "resolved_auto_patch_mode",
                        lambda tile: "ICAO")
    import O4_Settings_Model as SETTINGS
    monkeypatch.setattr(SETTINGS, "resolve_cifp_dir",
                        lambda *a, **k: str(corpus))
    monkeypatch.setattr(SETTINGS, "cifp_refusal_reason",
                        lambda *a, **k: None)
    seen = {}
    monkeypatch.setattr(DRIVER, "generate_auto_patches",
                        lambda *a, **k: seen.update(k) or [])

    VMAP.run_auto_patch_generation(_tile(46, 6), None, {})

    assert seen["stale_road_feeds"] == residual


# ---------------------------------------------------------------------
# 5. ONE CAUSE, ONE LINE — the +46+006 eleven-abort defect (issue #24)
# ---------------------------------------------------------------------
def _patch_candidate(icao, lat, lon):
    """A selection candidate the driver will collect as a build task."""
    return SimpleNamespace(
        icao=icao, cifp_file="/cifp/" + icao + ".dat",
        runways={"01": {"lat": lat, "lon": lon, "elev": 100.0}},
        disposition="patch", apt_dat="/apt/apt.dat", reason="")


@pytest.fixture
def three_airport_tile(tmp_path, monkeypatch):
    """A tile whose three airports all need a rebuild, with every
    expensive per-airport step stubbed out.  Nothing here touches the
    corpus, the network or a DEM."""
    import auto_patch.driver as DRIVER

    patch_dir = tmp_path / "Patches" / "zOrtho4XP_+46+006"
    patch_dir.mkdir(parents=True)
    cifp_dir = tmp_path / "CIFP"
    cifp_dir.mkdir()
    monkeypatch.setattr(DRIVER.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir), raising=False)
    monkeypatch.setattr(DRIVER, "_auto_patch_is_current",
                        lambda *a, **k: False)
    monkeypatch.setattr(DRIVER, "_freshness_stamps_now",
                        lambda *a, **k: {})
    monkeypatch.setattr(DRIVER, "_object_anchor_worklist_entries",
                        lambda *a, **k: [])
    monkeypatch.setattr(DRIVER, "xplane_root_from_cifp_path",
                        lambda path: str(tmp_path))
    monkeypatch.setattr(DRIVER, "pair_runways", lambda runways: [])

    failed = []
    monkeypatch.setattr(DRIVER.UI, "auto_patch_failed",
                        lambda icao, stage, error:
                        failed.append((icao, stage, error)))
    monkeypatch.setattr(DRIVER.UI, "auto_patch_begin",
                        lambda icaos: failed.append(("BEGIN", icaos, None)))

    tile = SimpleNamespace(
        lat=46, lon=6, dem=None,
        auto_patch_selection=[_patch_candidate("LSGG", 46.2, 6.1),
                              _patch_candidate("LSGB", 46.3, 6.2),
                              _patch_candidate("LFLI", 46.4, 6.3)])
    return SimpleNamespace(tile=tile, cifp=str(cifp_dir), failed=failed,
                           patch_dir=patch_dir)


def test_stale_road_data_says_it_once_and_names_each_airport_against_it(
        three_airport_tile, capsys):
    """THE DEFECT: eleven airports on +46+006 printed eleven aborts for
    ONE stale file, each naming ``build_airport.py --refresh-data
    osm_layers`` — a developer command an app user does not have."""
    import auto_patch.driver as DRIVER

    with pytest.raises(DRIVER.AutoPatchBuildFailure) as excinfo:
        DRIVER.generate_auto_patches(
            three_airport_tile.tile, three_airport_tile.cifp,
            stale_road_feeds=[(46, 7, "big_roads",
                               "/corpus/+46+007_big_roads.osm.bz2")])

    out = capsys.readouterr().out
    # ONE line for the cause, naming the one file, in app words.
    notice = ("the cached OSM road data this tile reads is out of date "
              "and could not be refreshed")
    assert out.count(notice) == 1, out
    assert out.count("+46+007_big_roads.osm.bz2") == 1, out
    # ONE short line per airport, pointing back at it.
    for icao in ("LSGG", "LSGB", "LFLI"):
        assert out.count("Auto-patch: FAILED " + icao) == 1, out
    # NO developer command anywhere in what the app user sees.
    assert "--refresh-data" not in out
    assert "build_airport.py" not in out
    # Each airport still gets its own AutoPatchFailed event (the app's
    # client matches the name as a string literal), and no progress row
    # is opened for a pass that never launches a worker.
    assert three_airport_tile.failed == [
        (icao, "build", DRIVER.STALE_ROAD_FEED_AIRPORT_ERROR)
        for icao in ("LSGG", "LSGB", "LFLI")]
    # …and the tile still dies (H1).
    assert [f["icao"] for f in excinfo.value.failures] == [
        "LSGG", "LSGB", "LFLI"]


def test_no_worker_and_no_worklist_are_spent_on_the_doomed_pass(
        three_airport_tile, monkeypatch):
    """The abort is raised BEFORE the Phase 2 worklist sidecar, before
    the airports-OSM prefetch (which downloads) and before any worker:
    nothing is spent on a pass whose every airport would die inside
    ``load_with_report`` on the same file."""
    import auto_patch.driver as DRIVER

    spent = []
    monkeypatch.setattr(DRIVER, "_write_object_anchor_worklist",
                        lambda *a, **k: spent.append("worklist"))
    monkeypatch.setattr(DRIVER, "_run_build_tasks",
                        lambda *a, **k: spent.append("workers"))

    with pytest.raises(DRIVER.AutoPatchBuildFailure):
        DRIVER.generate_auto_patches(
            three_airport_tile.tile, three_airport_tile.cifp,
            stale_road_feeds=[(46, 7, "big_roads",
                               "/corpus/+46+007_big_roads.osm.bz2")])

    assert spent == []


def test_an_all_current_tile_is_not_aborted_by_a_feed_nothing_reads(
        three_airport_tile, monkeypatch, capsys):
    """With no rebuild collected there is no reader to refuse, so a
    stale feed nothing reads is not an abort."""
    import auto_patch.driver as DRIVER

    monkeypatch.setattr(DRIVER, "_auto_patch_is_current",
                        lambda *a, **k: True)
    monkeypatch.setattr(DRIVER, "_run_build_tasks", lambda *a, **k: None)

    DRIVER.generate_auto_patches(
        three_airport_tile.tile, three_airport_tile.cifp,
        stale_road_feeds=[(46, 7, "big_roads",
                           "/corpus/+46+007_big_roads.osm.bz2")])

    out = capsys.readouterr().out
    assert "out of date" not in out
    assert three_airport_tile.failed == []
