"""Twins for O4_Imagery_Freshness (#1666) on recorded answers, no network.

The tile info's "Imagery check" row: is the imagery a built tile was made
from (its cached orthophoto JPEGs) what the provider serves now?  Every
case below is one server answer recorded as status, headers and body:
the first look (pixels compared with the JPEG), a 304, an ETag that
changed for the same bytes (a CDN), validators missing, the provider's
no-imagery tile, and the cache that keeps map browsing off the network.
"""

from __future__ import annotations

import io
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import O4_File_Names as FNAMES
import O4_Imagery_Freshness as FRESH
import pytest
from PIL import Image

ZL = 17
LAT, LON = 45, 7
#: A texture's top-left provider tile (any 16-aligned grid position).
TEXTURE = (68112, 47296)


def _provider():
    resolutions = [156543.03392804097 / 2 ** z for z in range(23)]
    corner = [[-20037508.34, 20037508.34]] * 23
    return {"code": "TST", "name": "Test Imagery", "request_type": "tms",
            "grid_type": "webmercator", "imagery_dir": "normal", "tile_size": 256,
            "url_template": "https://imagery.example/{zoom}/{x}/{y}.jpg",
            "resolutions": resolutions, "top_left_corner": corner}


def _colour(dx, dy):
    return (16 * dx, 16 * dy, 128)


def _jpeg_bytes(colour, size=256):
    out = io.BytesIO()
    Image.new("RGB", (size, size), colour).save(out, format="JPEG", quality=90)
    return out.getvalue()


@dataclass
class Answer:
    status: int
    body: bytes = b""
    headers: dict = field(default_factory=dict)


class Server:
    """Records the requests; answers from ``answer(key, headers)``."""

    def __init__(self, answer):
        self.answer = answer
        self.requests = []

    def __call__(self, provider, requests_, should_stop):
        self.requests.extend(requests_)
        return {key: self.answer(key[1], headers) for key, _url, headers in requests_}


@pytest.fixture
def tile(tmp_path, monkeypatch):
    """A built tile with one texture, and its orthophoto in the cache."""
    monkeypatch.setattr(FNAMES, "Imagery_dir", str(tmp_path / "Orthophotos"))
    build_dir = tmp_path / "zOrtho4XP_+45+007"
    (build_dir / "textures").mkdir(parents=True)
    til_x, til_y = TEXTURE
    (build_dir / "textures" / FNAMES.dds_file_name_from_attributes(
        til_x, til_y, ZL, "TST")).write_bytes(b"DDS ")
    (build_dir / "textures" / (FNAMES.dds_file_name_from_attributes(
        til_x, til_y, ZL, "TST")[:-4] + "_airport_fade.dds")).write_bytes(b"DDS ")
    folder = FNAMES.jpeg_file_dir_from_attributes(LAT, LON, ZL, _provider())
    os.makedirs(folder)
    image = Image.new("RGB", (16 * 16, 16 * 16))
    for dy in range(16):
        for dx in range(16):
            image.paste(_colour(dx, dy), (16 * dx, 16 * dy, 16 * dx + 16, 16 * dy + 16))
    jpeg = os.path.join(folder, FNAMES.jpeg_file_name_from_attributes(
        til_x, til_y, ZL, "TST"))
    image.save(jpeg, format="JPEG", quality=95)
    return str(build_dir), jpeg


def _check(build_dir, server, **kw):
    return FRESH.tile_freshness(LAT, LON, build_dir, "TST", ZL,
                                providers={"TST": _provider()}, fetch=server, **kw)


def _offset(key):
    _zl, x, y = (int(v) for v in key.split("/"))
    return x - TEXTURE[0], y - TEXTURE[1]


def _same(key, headers, etag='"v1"'):
    return Answer(200, _jpeg_bytes(_colour(*_offset(key))), {"etag": etag})


def test_first_look_compares_pixels_and_records_validators(tile):
    build_dir, jpeg = tile
    server = Server(_same)
    answer = _check(build_dir, server, now=1000.0)
    assert answer["status"] == FRESH.UP_TO_DATE
    assert (answer["sampled"], answer["changed"]) == (2, 0)
    assert len(server.requests) == 2                      # two samples, one texture
    assert all("If-None-Match" not in h for _k, _u, h in server.requests)
    parts = FRESH._read_record(jpeg)
    assert {r["etag"] for r in parts.values()} == {'"v1"'}
    assert all(r["matches"] for r in parts.values())


def test_reflown_imagery_reads_newer(tile):
    build_dir, _jpeg = tile
    answer = _check(build_dir, Server(
        lambda key, h: Answer(200, _jpeg_bytes((250, 250, 20)), {"etag": '"v2"'})))
    assert answer["status"] == FRESH.NEWER
    assert answer["label"] == "Newer imagery available"
    assert answer["changed"] == 2


def test_304_keeps_the_recorded_answer(tile):
    build_dir, _jpeg = tile
    _check(build_dir, Server(_same), now=1000.0)
    server = Server(lambda key, h: Answer(304))
    answer = _check(build_dir, server, now=1000.0 + FRESH.CHECK_TTL_S + 1)
    assert answer["status"] == FRESH.UP_TO_DATE
    assert all(h.get("If-None-Match") == '"v1"' for _k, _u, h in server.requests)


def test_cdn_etag_drift_with_the_same_body_is_not_newer(tile, monkeypatch):
    build_dir, _jpeg = tile
    _check(build_dir, Server(_same), now=1000.0)
    monkeypatch.setattr(FRESH, "_jpeg_part", lambda *a: pytest.fail("re-decoded"))
    answer = _check(build_dir, Server(lambda key, h: _same(key, h, etag='"edge-7"')),
                    force=True, now=2000.0)
    assert answer["status"] == FRESH.UP_TO_DATE


def test_no_validators_falls_back_to_the_body(tile):
    build_dir, _jpeg = tile
    plain = lambda key, h: Answer(200, _jpeg_bytes(_colour(*_offset(key))))  # noqa: E731
    _check(build_dir, Server(plain), now=1000.0)
    server = Server(plain)
    answer = _check(build_dir, server, force=True, now=2000.0)
    assert answer["status"] == FRESH.UP_TO_DATE
    assert all("If-None-Match" not in h and "If-Modified-Since" not in h
               for _k, _u, h in server.requests)


def test_a_fresh_record_sends_no_request_and_cached_only_never_does(tile):
    build_dir, _jpeg = tile
    assert _check(build_dir, Server(_same), cached_only=True)["status"] == FRESH.NOT_CHECKED
    _check(build_dir, Server(_same), now=1000.0)
    server = Server(_same)
    assert _check(build_dir, server, now=1000.0 + 3600)["status"] == FRESH.UP_TO_DATE
    assert server.requests == []
    assert _check(build_dir, server, cached_only=True,
                  now=1000.0 + 3600)["status"] == FRESH.UP_TO_DATE


def test_a_redownloaded_jpeg_forgets_its_record(tile):
    build_dir, jpeg = tile
    _check(build_dir, Server(_same), now=1000.0)
    os.utime(jpeg, (5000.0, 5000.0))
    assert FRESH._read_record(jpeg) == {}


def test_no_imagery_tile_and_errors_say_nothing(tile):
    build_dir, _jpeg = tile
    body = _jpeg_bytes((255, 255, 255))
    assert FRESH._judge_sample(None, 200, {}, b"", lambda: None, 0.0) is None
    assert FRESH._judge_sample(None, 503, {}, body, lambda: None, 0.0) is None
    assert FRESH._judge_sample(None, 200, {}, body, lambda: None, 0.0,
                              placeholder=True) is None
    answer = _check(build_dir, Server(lambda key, h: Answer(404)))
    assert answer["status"] == FRESH.UNKNOWN


def test_sources_that_cannot_be_checked_say_why(tile):
    build_dir, _jpeg = tile
    wms = dict(_provider(), request_type="wms", grid_type="")
    answer = FRESH.tile_freshness(LAT, LON, build_dir, "TST", ZL,
                                  providers={"TST": wms}, fetch=Server(_same))
    assert answer["status"] == FRESH.UNKNOWN and "grid" in answer["detail"]
    answer = FRESH.tile_freshness(LAT, LON, build_dir, "MIX", ZL,
                                  providers={}, fetch=Server(_same))
    assert answer["status"] == FRESH.UNKNOWN


def test_no_cached_jpeg_is_unknown(tile):
    build_dir, jpeg = tile
    os.remove(jpeg)
    assert _check(build_dir, Server(_same))["status"] == FRESH.UNKNOWN


def test_at_most_sixteen_requests(tile, tmp_path):
    build_dir, jpeg = tile
    folder = os.path.dirname(jpeg)
    for i in range(1, 30):
        til_x, til_y = TEXTURE[0] + 16 * i, TEXTURE[1]
        name = FNAMES.dds_file_name_from_attributes(til_x, til_y, ZL, "TST")
        open(os.path.join(build_dir, "textures", name), "wb").close()
        Image.new("RGB", (256, 256)).save(os.path.join(
            folder, FNAMES.jpeg_file_name_from_attributes(til_x, til_y, ZL, "TST")))
    server = Server(lambda key, h: Answer(404))
    _check(build_dir, server)
    assert len(server.requests) == 2 * FRESH.MAX_TEXTURES == 16


def test_discard_removes_jpegs_records_and_base_textures(tile):
    build_dir, jpeg = tile
    _check(build_dir, Server(_same), now=1000.0)
    removed = FRESH.discard_tile_imagery(LAT, LON, build_dir, "TST", ZL,
                                         providers={"TST": _provider()})
    assert removed == {"jpegs": 1, "textures": 1}
    assert not os.path.exists(jpeg) and not os.path.exists(FRESH._record_path(jpeg))
    left = os.listdir(os.path.join(build_dir, "textures"))
    assert left == [n for n in left if n.endswith("_airport_fade.dds")] and left


def test_the_command_completes_through_its_event(monkeypatch):
    import o4_engine.imagery_commands as CMDS
    from o4_engine import events as EV

    events = []
    monkeypatch.setattr(CMDS, "_imagery_freshness",
                        lambda *a, **k: {"status": FRESH.UP_TO_DATE})
    reply = CMDS.start_imagery_freshness(events.append, 45, 7, "/nowhere", request=9)
    assert reply == {"status": "started"}
    for _ in range(200):
        if events:
            break
        time.sleep(0.01)
    assert isinstance(events[0], EV.ImageryFreshnessReady)
    assert events[0].request == 9 and events[0].result["status"] == FRESH.UP_TO_DATE


def test_the_mac_app_shows_the_same_update_words():
    """Two UIs, one layout (#1244): the Mac's strings are the engine's."""
    import O4_Qt_Imagery_Freshness as QTFRESH

    kit = Path(__file__).resolve().parents[2] / "Sources" / "SceneryKit"
    swift = (kit / "ImageryFreshness.swift").read_text(encoding="utf-8")
    for text in (QTFRESH.UPDATE_TITLE, QTFRESH.UPDATE_HELP,
                 FRESH.UPDATE_CONFIRM_TITLE, FRESH.UPDATE_CONFIRM_TEXT):
        assert '"%s"' % text in swift
    client = (kit / "OrthoEngineClient.swift").read_text(encoding="utf-8")
    assert '"ImageryFreshnessReady"' in client
