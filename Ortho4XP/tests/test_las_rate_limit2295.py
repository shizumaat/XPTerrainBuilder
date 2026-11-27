"""#2295: a LAS tile GET answered HTTP 429 is WAITED OUT -- the provider
paused for every connection, ``Retry-After`` obeyed, a line while waiting,
one connection from then on -- and asked again, never the rung's answer
(TIST's lidar rung was dropped for 10 m fill on one 429).  No network:
``requests.get`` and the clock are faked."""
from __future__ import annotations

import contextlib
import types

import O4_Http_Pushback as PUSHBACK
import O4_UI_Utils as UI
import pytest
from elevation_access import base as ea_base
from elevation_access import rate_limit as RATE
from elevation_access.strategies import las_tile_index as ea_las_tile_index
from tests.test_las_tile_index import _definition, _Response, _write_las


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    fake = types.SimpleNamespace(monotonic=lambda: now[0], time=lambda: now[0],
                                 sleep=lambda s: now.__setitem__(0, now[0] + s))
    monkeypatch.setattr(PUSHBACK, "time", fake)
    monkeypatch.setattr(PUSHBACK, "_HOST_PAUSED_UNTIL", {})
    monkeypatch.setattr(RATE, "_THROTTLED", {})
    lines = []
    monkeypatch.setattr(UI, "vprint",
                        lambda lvl, *a: lines.append(" ".join(map(str, a))))
    return now, lines


def _serve(monkeypatch, answers):
    import requests
    calls = []

    def _get(url, **kwargs):
        calls.append(url)
        return answers.pop(0)
    monkeypatch.setattr(requests, "get", _get)
    return calls


def _source():
    return {"source_id": "T1", "download_url": "https://lpc.test/T1.las"}


def test_a_429_is_waited_out_and_the_tile_arrives(clock, monkeypatch, tmp_path):
    now, lines = clock
    with open(_write_las(tmp_path / "src.las"), "rb") as handle:
        body = handle.read()
    calls = _serve(monkeypatch, [
        _Response(429, headers={"Retry-After": "25"}),
        _Response(429),
        _Response(200, body=body, headers={"Content-Length": str(len(body))})])
    code = _definition()["code"]
    assert isinstance(RATE.throttled_connection(code), contextlib.nullcontext)
    t0 = now[0]
    ok = ea_las_tile_index.LasTileIndexStrategy()._download_tile(
        _definition(), _source(), str(tmp_path / "T1.part"),
        str(tmp_path / "cache" / "T1.las"))
    assert ok and len(calls) == 3
    # 25 s as the server asked, then the schedule's second wait
    waited = 25.0 + RATE.RATE_LIMIT_WAITS_S[1]
    assert now[0] - t0 == pytest.approx(waited)
    waits = [ln for ln in lines if "waiting" in ln]
    assert any("as it asked" in ln for ln in waits)
    # never silent longer than the progress interval while waiting
    assert len(waits) >= waited / RATE.RATE_LIMIT_PROGRESS_S
    # one connection to the provider from now on
    assert not isinstance(RATE.throttled_connection(code), contextlib.nullcontext)


def test_the_waits_spent_it_stays_transient(clock, monkeypatch, tmp_path):
    _serve(monkeypatch, [_Response(429)
                         for _ in range(len(RATE.RATE_LIMIT_WAITS_S) + 1)])
    with pytest.raises(ea_base.TransientFetchError, match="HTTP 429"):
        ea_las_tile_index.LasTileIndexStrategy()._download_tile(
            _definition(), _source(), str(tmp_path / "T1.part"),
            str(tmp_path / "T1.las"))


def test_a_plain_503_and_a_404_keep_their_answers(clock, monkeypatch, tmp_path):
    assert RATE.is_rate_limited(429) and not RATE.is_rate_limited(503)
    assert RATE.is_rate_limited(503, {"Retry-After": "5"})
    _serve(monkeypatch, [_Response(404)])
    assert ea_las_tile_index.LasTileIndexStrategy()._download_tile(
        _definition(), _source(), str(tmp_path / "T1.part"),
        str(tmp_path / "T1.las")) is False
