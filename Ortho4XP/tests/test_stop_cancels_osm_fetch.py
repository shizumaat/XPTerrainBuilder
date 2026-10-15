"""Stop is a cancellation in the OSM fetch path (#704).

Owner, app 1.0.393, tile +33-085: Stop during the in-band download of a
regional extract cancelled only the download.  The vector step then read
the empty result as "extract not stored yet", queued the region for the
background downloader and queried Overpass (coastline, airports); after
the hard stop the app respawned an engine whose maintenance thread drained
that want and started the 340 MB download AFTER the stop.

Twins: a stop during the extract download ends the request with no
Overpass call and nothing queued; Overpass sends no query under a stop;
the respawned engine's maintenance pass finds nothing to download.
Headless — the HTTP stream and Overpass are stubbed; no network.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_OSM_Extracts as EXTRACTS  # noqa: E402
import O4_OSM_Utils as OSM  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402

from test_osm_extracts_store import _PBF_HEADER, store  # noqa: E402,F401

BBOX = (38, -9.5, 39, -8.5)   # the synthetic index's "portugal" leaf


class _StreamStoppedMidway:
    """An extract stream during which the user presses Stop."""

    def __init__(self, stop_after_chunks=3):
        self._stop_after = stop_after_chunks
        self.headers = {"Content-Length": str(100 * 1024)}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, _chunk_bytes):
        yield _PBF_HEADER
        for index in range(100):
            if index == self._stop_after:
                UI.red_flag = True
            yield b"x" * 1024


@pytest.fixture
def stop_during_download(store, monkeypatch):  # noqa: F811
    monkeypatch.setattr(UI, "red_flag", False)
    monkeypatch.setattr(EXTRACTS, "FOREGROUND_POLL_SECONDS", 0.01)
    monkeypatch.setattr(EXTRACTS, "foreground_download_enabled",
                        lambda: True)
    monkeypatch.setattr(
        EXTRACTS.requests, "get",
        lambda url, stream, timeout: _StreamStoppedMidway())
    monkeypatch.setitem(
        sys.modules, "O4_OSM_Extract_Filter",
        types.SimpleNamespace(filter_extracts_to_osm_xml=lambda *a: (
            pytest.fail("a stopped download must not be filtered"))))
    yield store
    UI.red_flag = False


def _wanted(store_directory):
    return EXTRACTS._read_json(os.path.join(store_directory, "wanted.json"))


def test_stop_during_extract_download_queues_nothing(stop_during_download):
    lines = []
    original_vprint = UI.vprint
    UI.vprint = lambda *args, **kwargs: lines.append(
        " ".join(str(a) for a in args[1:]))
    try:
        result = EXTRACTS.osm_xml_from_local_extracts(
            ['way["natural"="coastline"]'], BBOX)
    finally:
        UI.vprint = original_vprint
    assert result is None
    assert UI.red_flag
    assert _wanted(stop_during_download) in (None, [])
    assert not any("not stored yet" in line for line in lines)
    assert not any("using Overpass" in line for line in lines)


def test_stop_during_extract_download_makes_no_overpass_call(
        stop_during_download, tmp_path, monkeypatch):
    def _no_overpass(*args, **kwargs):
        raise AssertionError("no Overpass query after a stop")

    monkeypatch.setattr(OSM, "get_overpass_data", _no_overpass)
    monkeypatch.setattr(
        OSM.FNAMES, "osm_cached",
        lambda lat, lon, suffix: str(tmp_path / "never-written.osm.bz2"))
    layer = OSM.OSM_layer()
    assert OSM.OSM_queries_to_OSM_layer(
        ['way["natural"="coastline"]'], layer, 38, -10,
        cached_suffix="coastline", cache_schema="t") == 0
    assert _wanted(stop_during_download) in (None, [])


def test_overpass_sends_no_query_under_a_stop(monkeypatch):
    def _no_post(*args, **kwargs):
        raise AssertionError("no Overpass request may be sent under Stop")

    monkeypatch.setattr(OSM, "_post_overpass_query_reporting_progress",
                        _no_post)
    monkeypatch.setattr(UI, "red_flag", True)
    assert OSM.get_overpass_data(
        ['way["aeroway"]'], (38, -10, 39, -9)) == 0


def test_engine_respawned_after_stop_starts_no_download(
        stop_during_download, monkeypatch):
    # The stopped build ...
    EXTRACTS.osm_xml_from_local_extracts(['way["aeroway"]'], BBOX)
    # ... then the app's fresh engine process: flag clear, maintenance
    # thread drains the wanted list.  It must find nothing to start.
    monkeypatch.setattr(UI, "red_flag", False)
    assert list(EXTRACTS._consume_wanted_regions()) == []
