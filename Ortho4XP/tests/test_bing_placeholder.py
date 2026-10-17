"""Bing placeholder detection survives the https host (#835).

imagery-fetch-spec §3.2: the ``X-VE-Tile-Info: no-tile`` header marks the
placeholder BESIDE the 1033-byte test, never instead of it.  Headless: a
stub session; no network.
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PIL import Image  # noqa: E402

import O4_Imagery_Utils as IMG  # noqa: E402

BING = "https://ecn.t1.tiles.virtualearth.net/tiles/a0313131310301312.jpeg?g=15312"
LAY = os.path.join(os.path.dirname(__file__), "..", "Providers", "Global", "BI.lay")


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (40, 90, 30)).save(buf, format="JPEG")
    return buf.getvalue()


class _Response:
    def __init__(self, headers, content):
        self.headers = headers
        self.content = content

    def __str__(self):
        return "<Response [200]>"


class _Session:
    def __init__(self, response):
        self.response = response

    def get(self, url, timeout=None, headers=None):
        return self.response


def _fetch(headers, content):
    session = _Session(_Response(headers, content))
    return IMG.http_request_to_image(256, 256, BING, None, session)


def test_header_only_placeholder_is_detected():
    body = _jpeg()
    headers = {"content-type": "image/jpeg", "content-length": str(len(body)),
               "x-ve-tile-info": "no-tile"}
    assert _fetch(headers, body) == (0, "[404]")


def test_1033_byte_placeholder_is_still_detected():
    headers = {"Content-Type": "image/jpeg", "Content-Length": "1033"}
    assert _fetch(headers, b"\0" * 1033) == (0, "[404]")


def test_normal_tile_is_not_flagged():
    body = _jpeg()
    headers = {"Content-Type": "image/jpeg", "Content-Length": str(len(body))}
    ok, image = _fetch(headers, body)
    assert ok == 1 and image.size == (8, 8)


def test_rule_is_host_scoped():
    assert not IMG.is_placeholder_tile("https://example.org/t.jpg",
                                       {"X-VE-Tile-Info": "no-tile"})
    assert IMG.is_placeholder_tile("https://x.arcgisonline.com/t",
                                   {"Content-Length": "2521"})


def test_bing_layer_uses_the_https_host():
    with open(LAY, encoding="utf-8", newline="") as lay:
        template = [line for line in lay if line.startswith("url_template=")]
    assert template == [
        "url_template=https://ecn.t{switch:0,1,2,3}.tiles.virtualearth.net"
        "/tiles/a{quadkey}.jpeg?g=15312\n"]
