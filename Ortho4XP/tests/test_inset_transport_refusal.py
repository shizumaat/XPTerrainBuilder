"""A BROKEN TRANSPORT IS NEVER A DURABLE ANSWER (issue #121, lane win121).

Measured on the SHIPPED beta.1 exe on windows-latest with TLS verification
broken on purpose (an unrelated CA bundle, run 36661272964): GDAL's libcurl
said "schannel: the certificate or certificate chain is based on an
untrusted root", ``requests`` said "SSLError(... CERTIFICATE_VERIFY_FAILED
...)", and the build then

* recorded SPAIN5M and COPERNICUSGLO30 as DURABLE ``no-coverage``,
* stamped the inset pass complete,
* downloaded no base raster and meshed the tile on an ALL-ZERO surface
  ("Min altitude: 0.0 , Max altitude: 0.0"),
* and finished ``BuildDone ok=true`` — every line of it in the console
  drawer only.

These twins pin each derivation site: the transient classifier, the
existence probe, the pass-level surfacing, the frame check and the base
download.  Headless, no network: every transport is monkeypatched.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, "src")

import O4_Airport_Elevation_Insets as INSETS
from elevation_access import base as ea_base
from elevation_access import failures as ea_failures
from elevation_access.strategies import degree_named_cog as ea_degree_named_cog
import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

#: The two error texts run 36661272964 printed, verbatim.
SCHANNEL_UNTRUSTED = ("schannel: the certificate or certificate chain is "
                      "based on an untrusted root")
REQUESTS_SSL = (
    "HTTPSConnectionPool(host='copernicus-dem-30m.s3.amazonaws.com', "
    "port=443): Max retries exceeded with url: /Copernicus_DSM_COG_10_N40_"
    "00_W004_00_DEM/Copernicus_DSM_COG_10_N40_00_W004_00_DEM.tif (Caused by "
    "SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] "
    "certificate verify failed: unable to get local issuer certificate "
    "(_ssl.c:1032)')))")

LAT, LON, ICAO = 40, -4, "LEMD"
#: LEMD's aerodrome bounds plus a ~2 km margin (the fetch's own box shape).
LEMD_BOX = (-3.62, 40.43, -3.50, 40.56)


@pytest.fixture(autouse=True)
def _clean_flag():
    UI.red_flag = False
    yield
    UI.red_flag = False


# ---------------------------------------------------------------------------
# 1. the classifier
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("message", [
    SCHANNEL_UNTRUSTED,
    REQUESTS_SSL,
    "CURL error: SSL certificate problem: unable to get local issuer "
    "certificate",
    "schannel: next InitializeSecurityContext failed: CRYPT_E_NO_REVOCATION"
    "_CHECK (0x80092012) - The revocation function was unable to check "
    "revocation for the certificate.",
    "HTTPSConnectionPool(host='x', port=443): Max retries exceeded with url: "
    "/ (Caused by NameResolutionError(\"Failed to resolve 'x' "
    "([Errno 11001] getaddrinfo failed)\"))",
    "ProxyError('Unable to connect to proxy')",
])
def test_transport_security_failures_are_transient(message):
    assert ea_failures.error_message_indicates_transient_network_failure(message)


@pytest.mark.parametrize("message", [
    "`/vsicurl/https://x/y.tif' does not exist in the file system, and is "
    "not recognized as a supported dataset name.",
    "Got 1111x823 instead of 1112x824",
])
def test_data_answers_stay_durable(message):
    assert not ea_failures.error_message_indicates_transient_network_failure(
        message)


# ---------------------------------------------------------------------------
# 2. the existence probe: no HTTP answer is not "the cell does not exist"
# ---------------------------------------------------------------------------
def test_existence_probe_raises_on_a_tls_failure(monkeypatch):
    import requests

    def _broken_head(url, timeout=None):
        raise requests.exceptions.SSLError(REQUESTS_SSL)

    monkeypatch.setattr(requests, "head", _broken_head)
    monkeypatch.setattr(ea_degree_named_cog.DegreeNamedCogStrategy,
                        "_cell_exists_by_url", {})
    strategy = ea_degree_named_cog.DegreeNamedCogStrategy()
    with pytest.raises(ea_base.TransientFetchError):
        strategy._url_exists("https://example.test/cell.tif")
    # ...and nothing was memoised as "does not exist".
    assert "https://example.test/cell.tif" not in \
        ea_degree_named_cog.DegreeNamedCogStrategy._cell_exists_by_url


def test_existence_probe_404_is_still_a_durable_no(monkeypatch):
    import requests

    class _Answer:
        status_code = 404

    monkeypatch.setattr(requests, "head", lambda url, timeout=None: _Answer())
    monkeypatch.setattr(ea_degree_named_cog.DegreeNamedCogStrategy,
                        "_cell_exists_by_url", {})
    assert ea_degree_named_cog.DegreeNamedCogStrategy()._url_exists(
        "https://example.test/none.tif") is False


# ---------------------------------------------------------------------------
# 3. the frame check: a record with an UNANSWERED covering provider is cold
# ---------------------------------------------------------------------------
def _index(tmp_path, monkeypatch, record):
    monkeypatch.setattr(FNAMES, "Elevation_dir",
                        str(tmp_path / "Elevation_data"))
    directory = FNAMES.airport_inset_directory(LAT, LON)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "index.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump({ICAO: record}, handle)


def _all_no_coverage():
    return {definition["code"]: INSETS.NO_COVERAGE
            for definition in INSETS.select_provider_definitions("auto")}


def test_frame_check_refuses_an_unanswered_covering_provider(
        tmp_path, monkeypatch):
    record = _all_no_coverage()
    del record["SPAIN5M"]          # its fetch raised: nothing recorded
    record["checked"] = "2026-09-30"
    _index(tmp_path, monkeypatch, record)
    assert INSETS.unanswered_inset_providers(
        LAT, LON, ICAO, LEMD_BOX) == ["SPAIN5M"]
    problem = INSETS.airport_inset_frame_problem(LAT, LON, ICAO, LEMD_BOX)
    assert problem is not None
    assert problem[0] == "missing"
    assert "SPAIN5M" in problem[1]


def test_frame_check_still_accepts_a_lawful_all_negative(
        tmp_path, monkeypatch):
    _index(tmp_path, monkeypatch, _all_no_coverage())
    assert INSETS.unanswered_inset_providers(LAT, LON, ICAO, LEMD_BOX) == []
    assert INSETS.airport_inset_frame_problem(
        LAT, LON, ICAO, LEMD_BOX) is None


def test_a_provider_ranked_below_an_ok_is_never_unanswered(
        tmp_path, monkeypatch):
    # The fetch loop stops at the first ``ok``: providers below it are
    # never asked, and their absence is lawful (the corpus census found
    # five such records, e.g. a renamed key whose raster file kept the
    # old name).
    codes = [d["code"] for d in INSETS.select_provider_definitions("auto")]
    assert codes.index("SPAIN5M") < codes.index("COPERNICUSGLO30")
    record = {code: INSETS.NO_COVERAGE
              for code in codes[:codes.index("SPAIN5M")]}
    record["SPAIN5M"] = "ok"
    _index(tmp_path, monkeypatch, record)
    assert INSETS.unanswered_inset_providers(LAT, LON, ICAO, LEMD_BOX) == []


# ---------------------------------------------------------------------------
# 4. the pass: a raised fetch is surfaced loudly and never stamped warm
# ---------------------------------------------------------------------------
class _Tile:
    lat, lon = LAT, LON
    airport_elevation_providers = "auto"
    airport_elevation_level = "auto"


def test_a_raised_fetch_is_loud_and_leaves_the_pass_unstamped(monkeypatch):
    loud, stamped = [], []

    def _fake_fetch(lat, lon, boxes, definitions, resolution, **kwargs):
        kwargs["fetch_failures"].append(
            (ICAO, "SPAIN5M", "WCS coverage open died on a network timeout "
                              "or outage: " + SCHANNEL_UNTRUSTED))

    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda tile: True)
    monkeypatch.setattr(INSETS, "resolved_inset_mode", lambda tile: "ICAO")
    monkeypatch.setattr(INSETS, "inset_keys", lambda dico, mode: {ICAO})
    monkeypatch.setattr(INSETS, "_airport_bounding_boxes",
                        lambda tile, dico, only=None: {ICAO: LEMD_BOX})
    monkeypatch.setattr(INSETS, "ensure_airport_insets", _fake_fetch)
    monkeypatch.setattr(INSETS, "_write_inset_completion_stamp",
                        lambda tile: stamped.append(tile))
    monkeypatch.setattr(UI, "loud_warning",
                        lambda *args: loud.append(" ".join(map(str, args))))
    INSETS.ensure_insets_for_tile(_Tile(), {ICAO: {}})
    assert stamped == []
    assert len(loud) == 1
    assert "SPAIN5M" in loud[0] and "untrusted root" in loud[0]


def test_a_clean_pass_is_still_stamped(monkeypatch):
    stamped = []
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda tile: True)
    monkeypatch.setattr(INSETS, "resolved_inset_mode", lambda tile: "ICAO")
    monkeypatch.setattr(INSETS, "inset_keys", lambda dico, mode: {ICAO})
    monkeypatch.setattr(INSETS, "_airport_bounding_boxes",
                        lambda tile, dico, only=None: {ICAO: LEMD_BOX})
    monkeypatch.setattr(INSETS, "ensure_airport_insets",
                        lambda *args, **kwargs: None)
    monkeypatch.setattr(INSETS, "_write_inset_completion_stamp",
                        lambda tile: stamped.append(tile))
    INSETS.ensure_insets_for_tile(_Tile(), {ICAO: {}})
    assert len(stamped) == 1


# ---------------------------------------------------------------------------
# 5. the base download: a transport failure REFUSES, a 404 stays 0
# ---------------------------------------------------------------------------
class _Session:
    def __init__(self, get):
        self._get = get

    def get(self, url, timeout=None, allow_redirects=None):
        # ``allow_redirects`` is passed explicitly since #193: the
        # transport follows redirects itself, bounded and recorded, so
        # the double has to accept the real signature.
        return self._get(url)


class _Response:
    def __init__(self, status):
        self._status = status
        self.status_code = status
        self.content = b""
        #: No ``Location``: nothing for the #193 redirect follow to
        #: follow, so every status below reaches the outcome classifier
        #: exactly as it did before.
        self.headers = {}

    def close(self):
        pass

    def __repr__(self):
        # The HISTORIC classifier read this repr as a string ("[40" in
        # str(response)), which is how a 403 became "Not Found" and a 429
        # matched nothing at all (#124/#173).  ``http_request`` now
        # classifies ``status_code``; the repr stays so the stub still
        # looks like a ``requests`` response in a traceback.
        return "<Response [%d]>" % self._status


def test_base_download_refuses_after_transport_failures(monkeypatch):
    import requests

    def _tls(url):
        raise requests.exceptions.SSLError(REQUESTS_SSL)

    monkeypatch.setattr(DEM.requests, "Session", lambda: _Session(_tls))
    monkeypatch.setattr(DEM.time, "sleep", lambda seconds: None)
    with pytest.raises(DEM.ElevationDownloadRefused) as caught:
        DEM.http_request("https://example.test/K30.zip", "View")
    assert "CERTIFICATE_VERIFY_FAILED" in str(caught.value)
    assert "View" in str(caught.value)


@pytest.mark.parametrize("status", [404, 410])
def test_base_download_absent_keeps_the_zero_convention(monkeypatch, status):
    """The server LOOKED and the file is not there: still a 0 here.

    The strategy above decides whether an absent file is lawful for the
    tile (``refuse_absent_base_archive``); only these two statuses get
    to reach that decision.
    """
    monkeypatch.setattr(DEM.requests, "Session",
                        lambda: _Session(lambda url: _Response(status)))
    assert DEM.http_request("https://example.test/none.zip", "View") == 0


@pytest.mark.parametrize("status", [401, 403, 407, 451])
def test_base_download_host_refusal_is_not_a_zero(monkeypatch, status):
    """#124/#173: all of 400-409 used to print "Not Found" and return 0."""
    monkeypatch.setattr(DEM.requests, "Session",
                        lambda: _Session(lambda url: _Response(status)))
    with pytest.raises(DEM.ElevationDownloadRefused) as caught:
        DEM.http_request("https://example.test/none.zip", "View")
    assert str(status) in str(caught.value)


@pytest.mark.parametrize("status", [429, 500, 503, 400])
def test_base_download_transient_status_refuses_rather_than_zero(
        monkeypatch, status):
    """A 429/410/451 matched no branch, so it retried six times and then
    returned a SILENT 0 -- no ``last_failure`` had been recorded."""
    monkeypatch.setattr(DEM.requests, "Session",
                        lambda: _Session(lambda url: _Response(status)))
    monkeypatch.setattr(DEM.time, "sleep", lambda seconds: None)
    with pytest.raises(DEM.ElevationDownloadRefused) as caught:
        DEM.http_request("https://example.test/none.zip", "View")
    assert str(status) in str(caught.value)


def test_base_download_stop_is_not_a_refusal(monkeypatch):
    import requests

    def _tls_then_stop(url):
        UI.red_flag = True
        raise requests.exceptions.SSLError(REQUESTS_SSL)

    monkeypatch.setattr(DEM.requests, "Session",
                        lambda: _Session(_tls_then_stop))
    monkeypatch.setattr(DEM.time, "sleep", lambda seconds: None)
    assert DEM.http_request("https://example.test/K30.zip", "View") == 0


# ---------------------------------------------------------------------------
# 6. a NEIGHBOUR cell's refusal names the cell and says it is a neighbour
# ---------------------------------------------------------------------------
def test_neighbour_cell_refusal_names_the_cell(monkeypatch):
    def _ensure(source, lat0, lon0, verbose=True, prefer_coarse=False):
        if (lat0, lon0) == (40, -4):
            return 0                       # home cell: not the one failing
        raise DEM.ElevationDownloadRefused("the View elevation download of "
                                           "https://x/J30.zip failed")

    monkeypatch.setattr(DEM, "ensure_elevation", _ensure)
    with pytest.raises(DEM.ElevationDownloadRefused) as caught:
        DEM.build_combined_raster("View", 40, -4, False)
    text = str(caught.value)
    assert "+39-004" in text or "+41-004" in text or "-005" in text \
        or "-003" in text
    assert "NEIGHBOUR of tile +40-004" in text


def test_home_cell_refusal_says_the_tile_itself(monkeypatch):
    def _ensure(source, lat0, lon0, verbose=True, prefer_coarse=False):
        raise DEM.ElevationDownloadRefused("failed")

    monkeypatch.setattr(DEM, "ensure_elevation", _ensure)
    with pytest.raises(DEM.ElevationDownloadRefused) as caught:
        DEM.build_combined_raster("View", 40, -4, False)
    assert "+40-004 (the tile itself)" in str(caught.value)


# ---------------------------------------------------------------------------
# 7. the system trust store: injected when the wheel is there, a logged
#    line (never a crash) when it is not
# ---------------------------------------------------------------------------
def test_truststore_is_injected_when_available(monkeypatch):
    import types

    import O4_Proj_Runtime as PR

    calls = []
    fake = types.SimpleNamespace(inject_into_ssl=lambda: calls.append(1))
    monkeypatch.setitem(sys.modules, "truststore", fake)
    assert PR.trust_system_certificate_store() == "injected"
    assert calls == [1]


def test_missing_truststore_is_a_logged_line_not_a_crash(monkeypatch,
                                                         capsys):
    import O4_Proj_Runtime as PR

    monkeypatch.setitem(sys.modules, "truststore", None)   # ImportError
    state = PR.trust_system_certificate_store()
    assert state.startswith("unavailable")
    captured = capsys.readouterr()
    assert captured.out == ""                 # stdout may be the protocol
    assert "system trust store" in captured.err


# ---------------------------------------------------------------------------
# 8. #193 -- the transport follows redirects, BOUNDED and RECORDED
#
# MEASURED 2026-10-02 against a redirecting server on loopback.  BEFORE:
# ``requests`` followed a same-host 301 silently (so viewfinderpanoramas'
# http -> https move worked by accident and said nothing), and a redirect
# LOOP cost 31 requests per attempt x HTTP_REQUEST_ATTEMPT_CAP = 186
# requests and 62 s of exponential back-off before refusing with "failed
# on the transport" -- never naming the redirect.  AFTER: the same 301 is
# followed and RECORDED, and the loop refuses in 6 requests / 0.1 s
# naming the chain.
# ---------------------------------------------------------------------------
def _redirecting_server(redirects, body=b"PK\x05\x06" + b"\x00" * 18):
    """A loopback server: ``redirects`` {path: (status, Location)}, every
    other path the ``body``.  Returns ``(base_url, requests, close)``."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    seen = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            seen.append(self.path)
            hop = redirects.get(self.path)
            if hop is not None:
                (status, location) = hop
                self.send_response(status)
                self.send_header("Location", location)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_address[1]
    return (base, seen, server.shutdown)


def test_a_same_host_redirect_is_followed_and_recorded():
    """The #193 case: the http URL answers 301 to its https twin.  The
    object arrives, and the hop is on the record instead of invisible."""
    (base, seen, close) = _redirecting_server(
        {"/dem3/L11.zip": (301, "/L11.zip")})
    try:
        response = DEM.http_request(base + "/dem3/L11.zip", "View")
        assert response and response.status_code == 200
        assert len(response.o4_redirect_chain) == 1
        assert response.o4_redirect_chain[0].startswith("301 ")
        assert response.o4_redirect_chain[0].endswith("/L11.zip")
        assert seen == ["/dem3/L11.zip", "/L11.zip"]
    finally:
        close()


@pytest.mark.parametrize("status", DEM.HTTP_REQUEST_REDIRECT_STATUSES)
def test_every_followed_status_is_followed(status):
    (base, _seen, close) = _redirecting_server({"/a.zip": (status, "/b.zip")})
    try:
        response = DEM.http_request(base + "/a.zip", "View")
        assert response and response.status_code == 200
    finally:
        close()


def test_a_direct_answer_records_no_redirect():
    (base, seen, close) = _redirecting_server({})
    try:
        response = DEM.http_request(base + "/L11.zip", "View")
        assert response.o4_redirect_chain == []
        assert seen == ["/L11.zip"]
    finally:
        close()


def test_a_redirect_loop_refuses_within_the_hop_bound(monkeypatch):
    """A looping host is refused NAMING THE REDIRECT, in
    HTTP_REQUEST_REDIRECT_HOPS + 1 requests -- not 186 of them across
    the back-off, and never as an all-zero raster."""
    (base, seen, close) = _redirecting_server(
        {"/loop/a.zip": (302, "/loop/b.zip"),
         "/loop/b.zip": (302, "/loop/a.zip")})
    monkeypatch.setattr(DEM.time, "sleep",
                        lambda seconds: pytest.fail("backed off"))
    try:
        with pytest.raises(DEM.ElevationDownloadRefused) as caught:
            DEM.http_request(base + "/loop/a.zip", "View")
        assert "REDIRECTED more than %d" % DEM.HTTP_REQUEST_REDIRECT_HOPS \
            in str(caught.value)
        assert "/loop/b.zip" in str(caught.value)
        assert len(seen) == DEM.HTTP_REQUEST_REDIRECT_HOPS + 1
    finally:
        close()


def test_a_chain_within_the_bound_still_arrives():
    hops = DEM.HTTP_REQUEST_REDIRECT_HOPS
    redirects = {"/c%d.zip" % step: (301, "/c%d.zip" % (step + 1))
                 for step in range(hops - 1)}
    redirects["/c%d.zip" % (hops - 1)] = (301, "/L11.zip")
    (base, seen, close) = _redirecting_server(redirects)
    try:
        response = DEM.http_request(base + "/c0.zip", "View")
        assert response and response.status_code == 200
        assert len(response.o4_redirect_chain) == hops
        assert len(seen) == hops + 1
    finally:
        close()


def test_a_3xx_without_a_location_still_reaches_the_outcome_classifier(
        monkeypatch):
    """A 3xx this transport cannot follow (no ``Location``) is NOT a
    redirect: it goes to the one outcome classifier, which calls it
    transient because it says nothing about the object (#124/#173)."""
    monkeypatch.setattr(DEM.requests, "Session",
                        lambda: _Session(lambda url: _Response(304)))
    monkeypatch.setattr(DEM.time, "sleep", lambda seconds: None)
    with pytest.raises(DEM.ElevationDownloadRefused) as caught:
        DEM.http_request("https://example.test/K30.zip", "View")
    assert "status 304" in str(caught.value)
