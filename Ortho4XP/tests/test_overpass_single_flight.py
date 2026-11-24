"""Overpass layer caches through the download manager (#2258, round
lrm1): one download per cache across callers, the file installed with one
rename and byte-identical to a direct write, Stop heard within a poll
during an Overpass answer's wait.  Headless; Overpass is stubbed."""
from __future__ import annotations

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Machine_Slots as SLOTS  # noqa: E402
import O4_OSM_Utils as OSM  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402

XML = (b"<?xml version='1.0' encoding='UTF-8'?>\n<osm version='0.6'>\n"
       b"<node id='1' lat='38.5' lon='-9.1'/>\n"
       b"<node id='2' lat='38.6' lon='-9.0'/>\n"
       b"<way id='10'><nd ref='1'/><nd ref='2'/>"
       b"<tag k='highway' v='primary'/></way>\n</osm>\n")


@pytest.fixture
def cache(tmp_path, monkeypatch):
    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "8")
    path = tmp_path / "osm" / "+38-010_roads.osm.bz2"
    monkeypatch.setattr(OSM.FNAMES, "osm_cached",
                        lambda lat, lon, suffix: str(path))
    import O4_OSM_Extracts as EXTRACTS
    monkeypatch.setattr(EXTRACTS, "osm_xml_from_local_extracts",
                        lambda *a, **k: None)
    UI.red_flag = False
    yield path
    UI.red_flag = False


def _layer(queries=('way["highway"="primary"]',)):
    layer = OSM.OSM_layer()
    got = OSM.OSM_queries_to_OSM_layer(list(queries), layer, 38, -10,
                                       cached_suffix="roads",
                                       cache_schema="s1")
    return layer, got


def test_the_cache_is_installed_whole_and_byte_identical(cache, tmp_path,
                                                         monkeypatch):
    asked = []
    monkeypatch.setattr(OSM, "get_overpass_data",
                        lambda *a, **k: asked.append(1) or XML)
    layer, got = _layer()
    assert got == 1 and asked == [1]
    reference = OSM.OSM_layer()
    reference.update_dicosm(XML, {"n": [], "w": [("highway", "primary")],
                                  "r": []},
                            {"n": [], "w": [("highway", "primary")],
                             "r": []})
    direct = tmp_path / "direct.osm.bz2"
    reference.write_to_file(str(direct),
                            header_attributes={"o4_tag_schema": "s1"})
    assert cache.read_bytes() == direct.read_bytes()
    assert [n for n in os.listdir(cache.parent) if ".tmp-" in n] == []
    # the next caller recycles it
    _layer()
    assert asked == [1]


def test_two_callers_make_one_overpass_request(cache, monkeypatch):
    asked = []
    release = threading.Event()

    def answer(*_a, **_k):
        asked.append(1)
        release.wait(10)
        return XML

    monkeypatch.setattr(OSM, "get_overpass_data", answer)
    # two different in-process locks would both reach the manager: the
    # per-cache-file thread lock is bypassed to stand for two processes
    monkeypatch.setattr(OSM, "_osm_cache_lock",
                        lambda name: threading.Lock())
    results = []
    threads = [threading.Thread(target=lambda: results.append(_layer()[1]))
               for _ in range(2)]
    for thread in threads:
        thread.start()
    time.sleep(0.5)
    release.set()
    for thread in threads:
        thread.join(10)
    assert asked == [1]
    assert sorted(results) == [1, 1]


def test_a_failed_download_installs_nothing(cache, monkeypatch):
    monkeypatch.setattr(OSM, "get_overpass_data", lambda *a, **k: 0)
    assert _layer()[1] == 0
    assert not cache.exists()


def test_stop_is_heard_within_a_poll_while_overpass_works(cache,
                                                         monkeypatch):
    release = threading.Event()

    class _Session:
        def post(self, *_a, **_k):
            release.wait(10)
            raise OSError("released")

    monkeypatch.setattr(OSM, "_get_http_session", lambda: _Session())
    monkeypatch.setitem(OSM.overpass_servers, "test",
                        "https://overpass.test/api")
    timer = threading.Timer(0.3, lambda: setattr(UI, "red_flag", True))
    timer.start()
    started = time.monotonic()
    try:
        answer = OSM._post_overpass_query_reporting_progress("test", "q")
    finally:
        release.set()
        timer.cancel()
    assert answer is None
    assert time.monotonic() - started < 1.5


def test_what_the_download_raises_is_raised(cache, monkeypatch):
    def broken(*_a, **_k):
        raise ValueError("parser")

    monkeypatch.setattr(OSM, "get_overpass_data", broken)
    with pytest.raises(ValueError):
        _layer()
    assert not cache.exists()
