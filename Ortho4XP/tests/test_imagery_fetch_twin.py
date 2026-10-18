"""The async imagery path paints the same texture as the threaded one (imagery-fetch-spec §5).

``O4_IMAGERY_FETCHER=async`` prefetches a texture's parts through the ported HTTP/2 fetcher
and replays each answer through the threaded chain (``O4_Imagery_Async``). Twin: the same
loopback server, the same provider, both arms → identical pixels and the same success flag,
across plain tiles, a Bing-style 1033-byte placeholder (parent-zoom fallback), a 404, a 500
and a 429 with ``Retry-After``. Plus: the in-flight cap is the provider's ``max_threads``,
``should_stop`` (``UI.red_flag``) cancels a prefetch, and the chooser's env values.
Loopback only; no network.
"""

from __future__ import annotations

import io
import os
import sys
import threading
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

pytest.importorskip("curl_cffi")

import numpy  # noqa: E402
from PIL import Image  # noqa: E402

import O4_Imagery_Async as FETCH_ASYNC  # noqa: E402
import O4_Imagery_Utils as IMG  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402

ZOOM = 6
TILBOX = (20, 24, 24, 28)  # 4 x 4 parts
PLACEHOLDER = (21, 25)
NOT_FOUND = (22, 26)
SERVER_ERROR = (23, 27)
RATE_LIMITED = (20, 27)


def _jpeg(z: int, x: int, y: int) -> bytes:
    buf = io.BytesIO()
    image = Image.new("RGB", (256, 256), ((x * 37) % 256, (y * 53) % 256, (z * 71) % 256))
    image.paste((x % 7 * 30, 200, y % 5 * 40), (32, 32, 96 + z, 96))
    image.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


class _Server:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.hits: dict[str, int] = defaultdict(int)
        self.in_flight: dict[str, int] = defaultdict(int)
        self.peak: dict[str, int] = defaultdict(int)
        state = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args: object) -> None:
                pass

            def handle(self) -> None:
                try:
                    super().handle()
                except ConnectionResetError:
                    pass  # a pooled connection closed by the client

            def _send(self, status: int, body: bytes, ctype: str, extra=None) -> None:
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(body)))
                    for k, v in (extra or {}).items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    pass  # the client went away (a cancelled prefetch)

            def do_GET(self) -> None:
                # /<arm>/virtualearth/<z>/<x>/<y>.jpg
                arm, _, z, x, y = self.path.strip("/").split("/")
                z, x, y = int(z), int(x), int(y.split(".")[0])
                with state.lock:
                    state.hits[self.path] += 1
                    count = state.hits[self.path]
                    state.in_flight[arm] += 1
                    state.peak[arm] = max(state.peak[arm], state.in_flight[arm])
                try:
                    time.sleep(0.02)
                    if z == ZOOM and (x, y) == PLACEHOLDER:
                        self._send(200, b"\xff" * 1033, "image/jpeg")
                    elif z == ZOOM and (x, y) == NOT_FOUND:
                        self._send(404, b"no tile", "text/plain")
                    elif z == ZOOM and (x, y) == SERVER_ERROR:
                        self._send(500, b"oops", "text/plain")
                    elif z == ZOOM and (x, y) == RATE_LIMITED and count == 1:
                        self._send(429, b"slow down", "text/plain", {"Retry-After": "1"})
                    else:
                        self._send(200, _jpeg(z, x, y), "image/jpeg")
                finally:
                    with state.lock:
                        state.in_flight[arm] -= 1

        ThreadingHTTPServer.request_queue_size = 128
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        host, port = self.httpd.server_address[:2]
        self.base = "http://%s:%d" % (host, port)

    def provider(self, arm: str, max_threads: int = 4) -> dict:
        return {
            "code": "TWIN" + arm,
            "request_type": "tms",
            "grid_type": "webmercator",
            "tile_size": 256,
            "max_threads": max_threads,
            # the template has no {xcenter}/{size}, but the builder evaluates them
            "resolutions": {z: 1.0 for z in range(25)},
            "top_left_corner": {z: [0.0, 0.0] for z in range(25)},
            "url_template": self.base + "/" + arm + "/virtualearth/{zoom}/{x}/{y}.jpg",
        }

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture(scope="module")
def server():
    srv = _Server()
    yield srv
    srv.close()


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(UI, "red_flag", False)
    monkeypatch.setattr(IMG, "shared_tile_cache_dir", None)


def _build(server: _Server, arm: str, fetcher: str, monkeypatch) -> tuple[int, numpy.ndarray]:
    monkeypatch.setenv(FETCH_ASYNC.FETCHER_ENV, fetcher)
    success, image = IMG.build_texture_from_tilbox(TILBOX, ZOOM, server.provider(arm))
    return success, numpy.asarray(image)


def test_async_and_threads_paint_the_same_texture(server, monkeypatch) -> None:
    calls: list[int] = []
    real = FETCH_ASYNC.fetch_parts

    def spy(parts, *args, **kwargs):
        calls.append(len(parts))
        return real(parts, *args, **kwargs)

    monkeypatch.setattr(FETCH_ASYNC, "fetch_parts", spy)
    threads_ok, threads_px = _build(server, "t", "threads", monkeypatch)
    assert calls == []
    async_ok, async_px = _build(server, "a", "async", monkeypatch)
    assert calls == [16]
    assert threads_ok == async_ok == 0  # the 500 part is white in both arms
    assert threads_px.shape == async_px.shape == (1024, 1024, 3)
    assert numpy.array_equal(threads_px, async_px)
    # the placeholder part came from its parent tile, not white
    x0 = (PLACEHOLDER[0] - TILBOX[0]) * 256
    y0 = (PLACEHOLDER[1] - TILBOX[1]) * 256
    assert not (async_px[y0 : y0 + 256, x0 : x0 + 256] == 255).all()
    # the parent request was the part's second request, served by the fallback session
    parent = "/a/virtualearth/%d/%d/%d.jpg" % (ZOOM - 1, PLACEHOLDER[0] // 2, PLACEHOLDER[1] // 2)
    assert server.hits[parent] == 1
    # the 429 was obeyed once, then answered
    limited = "/a/virtualearth/%d/%d/%d.jpg" % (ZOOM, *RATE_LIMITED)
    assert server.hits[limited] == 2


def test_the_window_never_exceeds_max_threads(server, monkeypatch) -> None:
    monkeypatch.setenv(FETCH_ASYNC.FETCHER_ENV, "async")
    IMG.build_texture_from_tilbox(TILBOX, ZOOM, server.provider("cap", max_threads=3))
    assert 1 <= server.peak["cap"] <= 3


def test_should_stop_cancels_a_prefetch(server) -> None:
    provider = server.provider("stop", max_threads=1)
    parts = []
    for i in range(40):
        url, headers = IMG.wmts_request(ZOOM, 30 + i, 30, provider)
        parts.append((i, url, headers))
    t0 = time.monotonic()
    deadline = t0 + 0.3
    results = FETCH_ASYNC.fetch_parts(
        parts, "STOP", 1, should_stop=lambda: time.monotonic() > deadline
    )
    assert time.monotonic() - t0 < 1.5
    cancelled = [r for r in results.values() if r.error == "SYS_CANCELLED"]
    assert len(results) == 40 and len(cancelled) >= 20


def test_a_transport_failure_is_raised_as_a_requests_connection_error() -> None:
    class Result:
        status, headers, body, error, detail = 0, {}, b"", "NET_TIMEOUT", "curl: (28) timed out"

    answer = FETCH_ASYNC.answer_of(Result())
    session = FETCH_ASYNC.PartSession(answer, fallback=None)
    with pytest.raises(IMG.requests.exceptions.ConnectionError):
        session.get("http://127.0.0.1/x")


def test_the_prefetched_answer_reads_like_a_requests_response() -> None:
    response = FETCH_ASYNC.PrefetchedResponse(200, {"content-length": "1033"}, b"x")
    assert str(response) == "<Response [200]>"
    assert response.headers["Content-Length"] == "1033"
    assert response.o4_prefetched


@pytest.mark.parametrize(
    "value, expected",
    [(None, "async"), ("", "async"), ("threads", "threads"), (" THREADS ", "threads"),
     ("ASYNC", "async"), ("async ", "async"), ("bogus", "async")],
)
def test_the_chooser_defaults_to_async(monkeypatch, value, expected) -> None:
    if value is None:
        monkeypatch.delenv(FETCH_ASYNC.FETCHER_ENV, raising=False)
    else:
        monkeypatch.setenv(FETCH_ASYNC.FETCHER_ENV, value)
    assert FETCH_ASYNC.fetcher_choice() == expected


def test_the_fetch_selfcheck_refuses_bad_arguments(capsys) -> None:
    import O4_Imagery_Fetch_Selfcheck as SELFCHECK

    assert SELFCHECK.main(["x", "--imagery-fetch-selfcheck", "BI", "sixteen"]) == 2
    assert "usage" in capsys.readouterr().out
