"""#2201: an extract address that answers 404 re-reads the index once and
retries at the index's new address; a 404 that persists is remembered —
logged once, never re-queued or re-asked each build.

Geofabrik moved its leaf extracts into per-region folders (2026-11); the
stored index kept the old address, whose redirect lands on a 404, so
kansai/kyushu/shikoku/sudeste failed every build.  Headless: no network.
"""

from __future__ import annotations

import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_OSM_Extracts as EXTRACTS  # noqa: E402

_PBF_HEADER = b"\x00\x00\x00\x0e\x0a\x09OSMHeader\x18\xb0\x01"
OLD = "https://example.invalid/asia/japan/kansai-latest.osm.pbf"
NEW = "https://example.invalid/asia/japan/kansai/kansai-latest.osm.pbf"


def _index(url):
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {"id": "kansai", "parent": "japan",
                       "urls": {"pbf": url}},
        "geometry": {"type": "Polygon", "coordinates": [[
            [134, 33], [136, 33], [136, 35], [134, 35], [134, 33]]]},
    }]}


class _Response:
    def __init__(self, status):
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status_code != 200:
            error = Exception("%d Client Error" % self.status_code)
            error.response = self
            raise error

    def iter_content(self, _chunk_bytes):
        yield _PBF_HEADER


@pytest.fixture
def store(tmp_path, monkeypatch):
    directory = str(tmp_path / "extracts")
    os.makedirs(directory)
    monkeypatch.setattr(EXTRACTS, "STORE_DIRECTORY", directory)
    monkeypatch.setattr(EXTRACTS, "extracts_enabled", lambda: True)
    EXTRACTS._leaf_regions.cache = None
    index_path = os.path.join(directory, "index-v1.json")
    with open(index_path, "w", encoding="utf-8", newline="") as handle:
        json.dump(_index(OLD), handle)
    old = os.path.getmtime(index_path) - 30 * 86400
    os.utime(index_path, (old, old))
    yield directory
    EXTRACTS._leaf_regions.cache = None


def _network(monkeypatch, live_urls, index_url):
    calls = {"get": [], "index": 0}

    def get(url, **_kwargs):
        calls["get"].append(url)
        return _Response(200 if url in live_urls else 404)

    def refresh_index():
        calls["index"] += 1
        with open(EXTRACTS._index_path(), "w", newline="\n") as handle:
            json.dump(_index(index_url), handle)
        EXTRACTS._leaf_regions.cache = None
        return True

    monkeypatch.setattr(EXTRACTS, "requests", types.SimpleNamespace(get=get))
    monkeypatch.setattr(EXTRACTS, "_refresh_index", refresh_index)
    return calls


def test_moved_address_reads_index_and_downloads(store, monkeypatch):
    calls = _network(monkeypatch, {NEW}, NEW)
    assert EXTRACTS._acquire_extract("kansai", OLD, foreground=True)
    assert calls["get"] == [OLD, NEW] and calls["index"] == 1
    assert os.path.isfile(EXTRACTS._region_file("kansai"))
    state = EXTRACTS._read_json(os.path.join(store, "state.json"))
    assert state["kansai"]["url"] == NEW


def test_persistent_404_is_remembered_not_retried(store, monkeypatch):
    calls = _network(monkeypatch, set(), OLD)
    assert not EXTRACTS._acquire_extract("kansai", OLD, foreground=True)
    assert calls["get"] == [OLD] and calls["index"] == 1
    # The next build: no request, no index read.
    assert not EXTRACTS._acquire_extract("kansai", OLD, foreground=True)
    assert calls["get"] == [OLD] and calls["index"] == 1


def test_fresh_index_404_does_not_reread_index(store, monkeypatch):
    os.utime(EXTRACTS._index_path(), None)
    calls = _network(monkeypatch, set(), NEW)
    assert not EXTRACTS._acquire_extract("kansai", OLD)
    assert calls["index"] == 0


def test_other_failures_are_not_remembered(store, monkeypatch):
    calls = _network(monkeypatch, set(), OLD)
    monkeypatch.setattr(
        EXTRACTS, "requests", types.SimpleNamespace(
            get=lambda url, **k: (_ for _ in ()).throw(OSError("offline"))))
    assert not EXTRACTS._acquire_extract("kansai", OLD)
    assert not EXTRACTS._url_not_found(OLD) and calls["index"] == 0


def test_remembered_404_region_is_not_requeued(store, monkeypatch):
    monkeypatch.setattr(EXTRACTS, "foreground_download_enabled", lambda: True)
    _network(monkeypatch, set(), OLD)
    bbox = (34, 135, 34.5, 135.5)
    assert EXTRACTS.osm_xml_from_local_extracts(['way["x"]'], bbox) is None
    assert EXTRACTS._url_not_found(OLD)
    wanted = EXTRACTS._read_json(os.path.join(store, "wanted.json"))
    assert not wanted
