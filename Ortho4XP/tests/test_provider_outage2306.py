"""A provider that is DOWN is asked once per outage, by all builds together (#2306).

Owner 2026-11-27: five tiles built in parallel while USGS TNM discovery
answered 504, and each tile kept asking -- 45 failed queries.  The first
5xx or timeout writes ONE machine-wide outage record
(``elevation_access.provider_outage``, a file under ``Elevation_data``);
every fetch and discovery of that provider in any build skips without a
request until it lapses, and it is never a coverage answer.

A REAL fake server (``http.server`` on 127.0.0.1) answers and counts; the
second "builder" is a second store with its OWN memory reading the same
file, as a second build process does -- and one test asks from a real
second process.
"""

import http.server
import json
import os
import subprocess
import sys
import threading
import time

import O4_Airport_Elevation_Insets as INSETS
import O4_File_Names as FNAMES
import O4_UI_Utils as UI
import pytest
from elevation_access import base as ea_base
from elevation_access import fetch_retry as FETCH_RETRY
from elevation_access import provider_outage as OUTAGE
from elevation_access import refusal_rest as REST
from elevation_access.rest_file import RestFile

_BOX = (-124.10, 44.50, -124.05, 44.55)
_SRC = os.path.dirname(os.path.abspath(INSETS.__file__))


class _FakeTnm:
    """A TNM products endpoint answering ``status`` and counting asks."""

    def __init__(self, status):
        self.status = status
        self.asked = []
        owner = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                owner.asked.append(self.path)
                body = (json.dumps({"total": 0, "items": []}).encode()
                        if owner.status == 200 else b"<html>Gateway</html>")
                self.send_response(owner.status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                                      _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()

    def definition(self, code="FAKETNM"):
        return {
            "code": code,
            "access_strategy": "tnm_cog",
            "discovery_url_template":
                "http://127.0.0.1:%d/api/v1/products?bbox={west},{south},"
                "{east},{north}" % self.server.server_address[1],
        }

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def tnm(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setattr(OUTAGE, "_STORE",
                        RestFile(OUTAGE._FILE_NAME, OUTAGE.OUTAGE_S))
    monkeypatch.setattr(OUTAGE, "_NOTED", {})
    server = _FakeTnm(504)
    yield server
    server.close()


def _second_build(monkeypatch):
    """A second build process: its own memory, the same file."""
    monkeypatch.setattr(OUTAGE, "_STORE",
                        RestFile(OUTAGE._FILE_NAME, OUTAGE.OUTAGE_S))


def test_a_second_builder_skips_a_provider_the_first_heard_down(
        tnm, monkeypatch):
    lines = []
    monkeypatch.setattr(UI, "vprint", lambda level, *a: lines.append(
        " ".join(str(x) for x in a)))
    builder_a = OUTAGE._STORE
    _second_build(monkeypatch)
    builder_b = OUTAGE._STORE
    # B read before A asked
    assert OUTAGE._STORE.live("FAKETNM", time.time()) is None
    # Builder A: a cell fetch hears 504 -- one request, one record.
    monkeypatch.setattr(OUTAGE, "_STORE", builder_a)
    with pytest.raises(ea_base.TransientFetchError) as raised:
        INSETS.fetch_inset(tnm.definition(), _BOX, 1.0,
                           os.path.join(FNAMES.Elevation_dir, "a.tif"))
    assert not isinstance(raised.value, OUTAGE.ProviderOutage)
    assert len(tnm.asked) == 1
    # Builder B (running all along): every path skips without a request.
    monkeypatch.setattr(OUTAGE, "_STORE", builder_b)
    for _cell in range(3):
        with pytest.raises(OUTAGE.ProviderOutage):
            INSETS.fetch_inset(tnm.definition(), _BOX, 1.0,
                               os.path.join(FNAMES.Elevation_dir, "b.tif"))
    with pytest.raises(OUTAGE.ProviderOutage):
        INSETS.discover_inset(tnm.definition(), _BOX)
    assert len(tnm.asked) == 1
    assert sum("FAKETNM is down" in line for line in lines) == 1, lines


def test_the_record_crosses_a_real_process(tnm):
    with pytest.raises(ea_base.TransientFetchError):
        INSETS.discover_inset(tnm.definition(), _BOX)
    probe = (
        "import sys; sys.path.insert(0, %r)\n"
        "import O4_File_Names as F; F.Elevation_dir = %r\n"
        "import time\nfrom elevation_access import provider_outage as O\n"
        "print('DOWN' if O._STORE.live('FAKETNM', time.time()) else 'UP')\n"
        % (_SRC, FNAMES.Elevation_dir))
    answer = subprocess.run([sys.executable, "-c", probe], cwd=_SRC,
                            capture_output=True, text=True, timeout=120)
    assert answer.stdout.strip().splitlines()[-1] == "DOWN", answer.stderr


def test_a_lapsed_record_asks_again(tnm):
    with pytest.raises(ea_base.TransientFetchError):
        INSETS.discover_inset(tnm.definition(), _BOX)
    record = OUTAGE._STORE.live("FAKETNM", time.time())
    assert record is not None and "504" in record["reason"]
    OUTAGE._remember_outage("FAKETNM", "status 504",
                           now=record["at"] - OUTAGE.OUTAGE_S - 1)
    tnm.status = 200
    assert INSETS.discover_inset(tnm.definition(), _BOX) is None
    assert len(tnm.asked) == 2


def test_an_outage_is_never_a_coverage_answer_nor_a_refusal(tnm):
    with pytest.raises(ea_base.TransientFetchError):
        INSETS.discover_inset(tnm.definition(), _BOX)
    with pytest.raises(OUTAGE.ProviderOutage) as raised:
        INSETS.discover_inset(tnm.definition(), _BOX)
    assert isinstance(raised.value, ea_base.TransientFetchError)
    assert not REST.is_refusal(raised.value)


def test_another_provider_is_still_asked(tnm):
    with pytest.raises(ea_base.TransientFetchError):
        INSETS.discover_inset(tnm.definition("FAKETNM"), _BOX)
    with pytest.raises(ea_base.TransientFetchError) as raised:
        INSETS.discover_inset(tnm.definition("OTHERTNM"), _BOX)
    assert not isinstance(raised.value, OUTAGE.ProviderOutage)
    assert len(tnm.asked) == 2


@pytest.mark.parametrize("status", [429, 400, 403])
def test_a_rate_limit_or_a_refusal_is_not_an_outage(tnm, status):
    tnm.status = status
    with pytest.raises((ea_base.TransientFetchError,
                        ea_base.ProviderUnavailable)):
        INSETS.discover_inset(tnm.definition(), _BOX)
    assert OUTAGE._STORE.live("FAKETNM", time.time()) is None


def test_a_timeout_is_an_outage_a_dead_connection_is_not():
    import requests
    from elevation_access import discovery as ea_discovery

    for (reason, outage) in ((requests.ReadTimeout("read timed out"), True),
                             (requests.ConnectionError("no route"), False)):
        with pytest.raises(ea_base.TransientFetchError) as raised:
            ea_discovery.raise_transient_discovery_failure("TNM", reason)
        assert OUTAGE.is_outage(raised.value) is outage


def test_an_outage_is_not_retried_after_a_wait(monkeypatch):
    waits = []
    monkeypatch.setattr(FETCH_RETRY.PUSHBACK, "pause_host",
                        lambda key, seconds: waits.append(seconds))
    asked = []

    def _down():
        asked.append(1)
        error = ea_base.TransientFetchError("TNM failed: status 504")
        error.http_status = 504
        raise error

    with pytest.raises(ea_base.TransientFetchError):
        FETCH_RETRY.retry_transient(_down, "FAKETNM", "KXXX")
    assert asked == [1] and waits == []
