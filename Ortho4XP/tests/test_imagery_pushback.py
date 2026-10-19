"""Imagery fetches obey server pushback; the temp PNG saves fast and lossless.

#834 (imagery-fetch-spec §3.1): a 429 / 503 is retried after its
Retry-After (or an exponential backoff), within a bounded budget, with the
host paused for every thread and ``UI.red_flag`` honoured mid-wait.
#833 (texture-encode-spec §3): ``save_temp_png`` decodes to the same pixels
as a default PNG save.  Headless: a stub session and a fake clock.
"""

import email.utils
import io
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

import O4_Http_Pushback as PUSHBACK  # noqa: E402
import O4_Imagery_Utils as IMG  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


class _Response:
    def __init__(self, code, headers=None, content=b""):
        self.code = code
        self.headers = dict(headers or {})
        self.content = content

    def __str__(self):
        return "<Response [%d]>" % self.code


def _ok():
    return _Response(200, {"Content-Type": "image/png"}, _png_bytes())


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, timeout=None, headers=None):
        self.urls.append(url)
        return self.responses.pop(0)


@pytest.fixture
def clock(monkeypatch):
    """Fake monotonic clock; time.sleep advances it instantly."""
    state = {"now": 1000.0, "slept": [], "on_sleep": None}

    def sleep(seconds):
        state["slept"].append(seconds)
        state["now"] += seconds
        if state["on_sleep"]:
            state["on_sleep"]()

    monkeypatch.setattr(time, "monotonic", lambda: state["now"])
    monkeypatch.setattr(time, "sleep", sleep)
    monkeypatch.setattr(UI, "red_flag", False)
    PUSHBACK._HOST_PAUSED_UNTIL.clear()
    yield state
    PUSHBACK._HOST_PAUSED_UNTIL.clear()


def _fetch(session, url="https://tiles.example/1/2/3.png"):
    return IMG.http_request_to_image(256, 256, url, None, session)


def test_429_retry_after_then_200_succeeds_after_the_wait(clock):
    session = _Session([_Response(429, {"Retry-After": "1"}), _ok()])
    ok, image = _fetch(session)
    assert ok == 1 and image.size == (4, 4)
    assert len(session.urls) == 2
    assert sum(clock["slept"]) == pytest.approx(1.0)


def test_repeated_429_stops_within_the_budget(clock):
    session = _Session([_Response(429, {"Retry-After": "30"})] * 50)
    ok, status = _fetch(session)
    assert ok == 0 and "[429]" in status
    assert sum(clock["slept"]) <= PUSHBACK.PUSHBACK_MAX_TOTAL + 1e-9
    assert len(session.urls) <= PUSHBACK.PUSHBACK_MAX_PAUSES + 1


def test_repeated_503_without_header_backs_off_then_fails(clock):
    session = _Session([_Response(503)] * 50)
    ok, status = _fetch(session)
    assert ok == 0 and "[503]" in status
    assert len(session.urls) == PUSHBACK.BACKOFF_MAX_STEPS + 2
    # Exponential, jittered within +-25 %, capped.
    assert sum(clock["slept"]) <= 1.25 * sum(
        min(PUSHBACK.BACKOFF_BASE * 2 ** k, PUSHBACK.BACKOFF_CAP)
        for k in range(PUSHBACK.BACKOFF_MAX_STEPS + 1)
    ) + 1e-9


def test_502_is_retried_like_503_whatever_check_tms_response(clock, monkeypatch):
    """#863: USGS NAIP answers ~1 in 12 requests 502 (overloaded gateway);
    it is pushback like a 503, not a give-up 5xx, within the same bound."""
    monkeypatch.setattr(IMG, "check_tms_response", False)
    session = _Session([_Response(502), _ok()])
    ok, image = _fetch(session)
    assert ok == 1 and len(session.urls) == 2
    session = _Session([_Response(502)] * 50)
    ok, status = _fetch(session)
    assert ok == 0 and "[502]" in status
    assert len(session.urls) == PUSHBACK.BACKOFF_MAX_STEPS + 2
    session = _Session([_Response(500), _ok()])  # other 5xx unchanged
    ok, status = _fetch(session)
    assert ok == 0 and len(session.urls) == 1


def test_red_flag_during_backoff_stops_promptly(clock):
    def raise_flag():
        UI.red_flag = True

    clock["on_sleep"] = raise_flag
    session = _Session([_Response(429, {"Retry-After": "60"}), _ok()])
    assert _fetch(session) == (0, "Stopped")
    assert len(session.urls) == 1
    assert clock["slept"] == [PUSHBACK.SLEEP_SLICE]


def test_host_pause_is_shared_across_calls(clock):
    # One thread's 429 pauses the host ...
    first = _Session([_Response(429, {"Retry-After": "7"}), _ok()])
    PUSHBACK.Pushback().next_wait(
        first.get("https://tiles.example/a.png").headers,
        pause_url="https://tiles.example/a.png",
    )
    assert PUSHBACK.host_pause_remaining("https://tiles.example/b.png") == 7
    assert PUSHBACK.host_pause_remaining("https://other.example/b.png") == 0
    # ... so another call to the same host waits before its request.
    second = _Session([_ok()])
    assert _fetch(second, "https://tiles.example/b.png")[0] == 1
    assert sum(clock["slept"]) == pytest.approx(7.0)
    # A different host is not held.
    clock["slept"].clear()
    PUSHBACK.pause_host("https://tiles.example/c.png", 5)
    assert _fetch(_Session([_ok()]), "https://other.example/c.png")[0] == 1
    assert clock["slept"] == []


def test_404_and_403_answer_without_waiting(clock):
    assert _fetch(_Session([_Response(404)])) == (0, "<Response [404]>")
    assert _fetch(_Session([_Response(403)])) == (0, "<Response [403]>")
    assert clock["slept"] == []


def test_retry_after_reads_seconds_and_http_date():
    assert PUSHBACK.retry_after_seconds({"Retry-After": "12"}) == 12
    when = email.utils.formatdate(time.time() + 20, usegmt=True)
    assert 15 < PUSHBACK.retry_after_seconds({"Retry-After": when}) <= 20
    assert PUSHBACK.retry_after_seconds({"Retry-After": "soon"}) is None
    assert PUSHBACK.retry_after_seconds({}) is None


def test_save_temp_png_is_pixel_identical_to_default_save(tmp_path):
    rng = numpy.random.default_rng(833)
    pixels = rng.integers(0, 256, size=(256, 256, 4), dtype=numpy.uint8)
    image = Image.fromarray(pixels, "RGBA")
    fast = tmp_path / "fast.png"
    default = tmp_path / "default.png"
    IMG.save_temp_png(image, str(fast))
    image.save(str(default))
    with Image.open(fast) as a, Image.open(default) as b:
        assert a.mode == b.mode == "RGBA"
        assert numpy.array_equal(numpy.asarray(a), numpy.asarray(b))
        assert numpy.array_equal(numpy.asarray(a), pixels)
