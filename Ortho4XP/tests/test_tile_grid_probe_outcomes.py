"""THE TILE-GRID EXISTENCE PROBE OBEYS THE OUTCOME LAW (issue #180).

``TileGridHttpStrategy._tile_exists`` -- the HEAD / ranged-GET probe that
tells a real tile from the water and border tiles a projected kilometre
grid inevitably names -- used to end:

    probe = session.head(url, timeout=30, headers=headers, ...)
    return probe.status_code == 200
    except Exception:
        return False

so a CDN 403, a proxy 407, a 429, a 503 and every transport death all
answered "this tile does not exist".  ``False`` SKIPS the candidate, and a
box whose every candidate is skipped leaves ``discover`` with no sources,
which the caller records as a DURABLE ``no-coverage`` for the airport:
the #121/#124 class again, a failed transport becoming a permanent
negative.  #124 fixed the sibling probe (``DegreeNamedCogStrategy.
_url_exists``, PR #183) with one shared classifier; this file holds the
same law at the second site.

One class per test, against a REAL HTTP server on loopback -- no
monkeypatched transport, so the statuses travel over a socket and a
change in how ``requests`` surfaces them cannot quietly pass:

* 2xx (and the 206 a ranged probe gets)  -> exists.
* 404 / 410              -> absent, the ONLY answer that may skip a tile.
* 401 403 405 407 451    -> ``ProviderUnavailable``.
* 429 / 5xx / unrecognised -> ``TransientFetchError``.
* no answer at all       -> ``TransientFetchError``, whatever the
  exception's wording.
"""
from __future__ import annotations

import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, "src")

import O4_Airport_Elevation_Insets as INSETS

#: The statuses the law sorts, mirrored from the module so a drift in
#: either direction is a twin failure rather than a silent re-reading.
UNAVAILABLE_STATUSES = (401, 403, 405, 407, 451)
ABSENT_STATUSES = (404, 410)
TRANSIENT_STATUSES = (429, 500, 501, 502, 503, 504, 400, 418, 304)

#: A Bavaria-shaped definition: kilometre-named tiles, HEAD probe.
TILE_URL_TEMPLATE_PATH = "/a/dgm/dgm1/{easting_km}_{northing_km}.tif"
#: The one candidate tile every twin probes.
PROBE_EASTING_KM, PROBE_NORTHING_KM = 690, 5334


class _FixedStatusHandler(BaseHTTPRequestHandler):
    """Answers every HEAD and GET with ``server.fixed_status``."""

    protocol_version = "HTTP/1.1"

    def _answer(self):
        self.server.probed_paths.append(self.path)
        self.server.probed_methods.append(self.command)
        self.server.probed_headers.append(dict(self.headers))
        self.send_response(self.server.fixed_status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_HEAD = _answer                                      # noqa: N815
    do_GET = _answer                                       # noqa: N815

    def log_message(self, *args):                          # keep pytest quiet
        return


@pytest.fixture
def fake_host():
    """A loopback HTTP server whose status each test sets."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FixedStatusHandler)
    server.fixed_status = 200
    server.probed_paths = []
    server.probed_methods = []
    server.probed_headers = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _definition(server, **extra):
    (host, port) = server.server_address[0], server.server_address[1]
    definition = {
        "code": "BAVARIA1M",
        "tile_url_template": (
            "http://%s:%d%s" % (host, port, TILE_URL_TEMPLATE_PATH)
        ),
        "tile_size_km": 1,
        "source_epsg": 25832,
        "coverage_bbox": "8.9,47.2,13.9,50.6",
    }
    definition.update(extra)
    return definition


def _tile_url(definition):
    return (
        definition["tile_url_template"]
        .replace("{easting_km}", str(PROBE_EASTING_KM))
        .replace("{northing_km}", str(PROBE_NORTHING_KM))
    )


def _probe(server, status, **extra):
    """Run the ONE probe site against ``status``; returns its answer."""
    server.fixed_status = status
    strategy = INSETS.TileGridHttpStrategy()
    definition = _definition(server, **extra)
    import requests

    with requests.Session() as session:
        return strategy._tile_exists(
            definition,
            session,
            strategy._http_headers(definition),
            _tile_url(definition),
        )


def _dead_url():
    """A loopback URL whose port has no listener: no HTTP answer at all."""
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return "http://127.0.0.1:%d%s" % (port, TILE_URL_TEMPLATE_PATH)


# ---------------------------------------------------------------------------
# 1. a tile that is there
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status", [200, 201, 204, 206, 299])
def test_a_success_says_the_tile_is_there(fake_host, status):
    assert _probe(fake_host, status) is True


def test_the_default_probe_is_a_HEAD(fake_host):
    _probe(fake_host, 200)
    assert fake_host.probed_methods == ["HEAD"]


# ---------------------------------------------------------------------------
# 2. the ONLY durable negative -- the answer that may skip a tile
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status", ABSENT_STATUSES)
def test_only_a_look_that_found_nothing_skips_the_tile(fake_host, status):
    assert _probe(fake_host, status) is False


# ---------------------------------------------------------------------------
# 3. the host refused THIS CLIENT: unavailable, never absent
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status", UNAVAILABLE_STATUSES)
def test_a_host_refusal_is_unavailable_not_absent(fake_host, status):
    with pytest.raises(INSETS.ProviderUnavailable) as raised:
        _probe(fake_host, status)
    assert str(status) in str(raised.value)
    assert "unavailable" in str(raised.value)


def test_the_401_a_HEAD_rejecting_host_answers_is_not_a_missing_tile(
        fake_host):
    """The docstring's own case: Saxony's host answers 401 to HEAD.

    Before the law that 401 skipped the tile, so a provider whose every
    tile answered 401 recorded a durable no-coverage for the airport.
    """
    with pytest.raises(INSETS.ProviderUnavailable):
        _probe(fake_host, 401)


# ---------------------------------------------------------------------------
# 4. nothing was learned about the tile: transient, nothing recorded
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status", TRANSIENT_STATUSES)
def test_an_answer_that_says_nothing_is_transient(fake_host, status):
    with pytest.raises(INSETS.TransientFetchError) as raised:
        _probe(fake_host, status)
    assert "NOT recorded as no-coverage" in str(raised.value)


def test_no_answer_at_all_is_transient_whatever_the_wording():
    strategy = INSETS.TileGridHttpStrategy()
    import requests

    with requests.Session() as session:
        with pytest.raises(INSETS.TransientFetchError) as raised:
            strategy._tile_exists({"code": "X"}, session, None, _dead_url())
    assert "NOT recorded as no-coverage" in str(raised.value)


# ---------------------------------------------------------------------------
# 5. the other probe modes
# ---------------------------------------------------------------------------
def test_a_ranged_get_probe_asks_for_one_byte_and_obeys_the_same_law(
        fake_host):
    assert _probe(fake_host, 206, probe_mode="ranged_get") is True
    assert fake_host.probed_methods == ["GET"]
    assert fake_host.probed_headers[0].get("Range") == "bytes=0-0"


@pytest.mark.parametrize("status", UNAVAILABLE_STATUSES)
def test_a_ranged_get_refusal_is_also_unavailable(fake_host, status):
    with pytest.raises(INSETS.ProviderUnavailable):
        _probe(fake_host, status, probe_mode="ranged_get")


@pytest.mark.parametrize("status", TRANSIENT_STATUSES)
def test_a_ranged_get_non_answer_is_also_transient(fake_host, status):
    with pytest.raises(INSETS.TransientFetchError):
        _probe(fake_host, status, probe_mode="ranged_get")


def test_probe_mode_none_is_the_escape_for_a_host_that_cannot_be_probed(
        fake_host):
    """#180's open measurement: a host whose absent answer is not a 404.

    The definition's own ``probe_mode=none`` is the shipped escape --
    probe nothing, let the warp decide -- so routing the probe through
    the law needs no new knob.
    """
    assert _probe(fake_host, 403, probe_mode="none") is True
    assert fake_host.probed_methods == []


def test_a_gdal_probe_that_raises_is_transient_not_absent(monkeypatch):
    """``gdal.Open`` has ONE answer for absent and refused alike, so
    ``None`` still skips the tile -- but an EXCEPTION is no answer."""
    strategy = INSETS.TileGridHttpStrategy()

    class _Boom:
        @staticmethod
        def Open(url):                                     # noqa: N802
            raise RuntimeError("CURL error: Peer certificate")

    monkeypatch.setattr(INSETS, "gdal", _Boom)
    with pytest.raises(INSETS.TransientFetchError):
        strategy._tile_exists(
            {"code": "X"}, None, None, "/vsizip//vsicurl/http://h/x.zip/a.tif"
        )

    class _Absent:
        @staticmethod
        def Open(url):                                     # noqa: N802
            return None

    monkeypatch.setattr(INSETS, "gdal", _Absent)
    assert strategy._tile_exists(
        {"code": "X"}, None, None, "/vsizip//vsicurl/http://h/x.zip/a.tif"
    ) is False


# ---------------------------------------------------------------------------
# 6. structural: the law cannot drift from the module's ONE convention
# ---------------------------------------------------------------------------
def test_no_status_outside_the_absent_set_can_ever_skip_a_tile(fake_host):
    """Every status in 100..599 that answers ``False`` is in the set.

    Walked against the classifier the probe uses, so a status added to
    the probe without being added to :data:`HTTP_ABSENT_STATUSES` is a
    failure here rather than a new durable negative in the field.
    """
    durable = [
        status
        for status in range(100, 600)
        if INSETS.http_answer_outcome(status) == INSETS.HTTP_OUTCOME_ABSENT
    ]
    assert tuple(durable) == INSETS.HTTP_ABSENT_STATUSES


def test_the_probe_shares_the_modules_one_transient_convention():
    for status in range(100, 600):
        if INSETS.discovery_status_is_transient(status):
            assert (INSETS.http_answer_outcome(status)
                    == INSETS.HTTP_OUTCOME_TRANSIENT), status


def test_the_probe_timeout_is_a_named_constant():
    assert INSETS.TILE_GRID_PROBE_TIMEOUT_S == 30


# ---------------------------------------------------------------------------
# 7. the answer reaches the CALLER the way the law needs it to
# ---------------------------------------------------------------------------
@pytest.fixture
def one_tile_box(monkeypatch):
    """``discover`` with the projection stubbed to name ONE candidate.

    The transform is GDAL's; stubbing it keeps these twins about the
    outcome law rather than about a projection, and they then run
    wherever GDAL does not.
    """
    def _transform(bounding_box_wgs84, epsg):
        return (
            PROBE_EASTING_KM * 1000.0, PROBE_NORTHING_KM * 1000.0,
            PROBE_EASTING_KM * 1000.0, PROBE_NORTHING_KM * 1000.0,
        )

    monkeypatch.setattr(INSETS, "transform_bounding_box_to_epsg", _transform)
    return (11.7, 48.1, 11.8, 48.2)


def test_an_absent_tile_is_skipped_and_discovery_answers_no_sources(
        fake_host, one_tile_box):
    fake_host.fixed_status = 404
    strategy = INSETS.TileGridHttpStrategy()
    assert strategy.discover(_definition(fake_host), one_tile_box) is None


def test_a_present_tile_is_discovered(fake_host, one_tile_box):
    fake_host.fixed_status = 200
    strategy = INSETS.TileGridHttpStrategy()
    sources = strategy.discover(_definition(fake_host), one_tile_box)
    assert sources == [{"url": _tile_url(_definition(fake_host))}]


def test_a_refusal_climbs_out_of_discover_instead_of_emptying_it(
        fake_host, one_tile_box):
    """The whole point: ``discover`` must NOT answer ``None`` here.

    ``None`` is what the caller records as a durable no-coverage, so a
    403 reaching the ladder as "no sources" is the defect.  It must
    arrive as the refusal it is.
    """
    fake_host.fixed_status = 403
    strategy = INSETS.TileGridHttpStrategy()
    with pytest.raises(INSETS.ProviderUnavailable):
        strategy.discover(_definition(fake_host), one_tile_box)


def test_an_outage_climbs_out_of_discover_instead_of_emptying_it(
        fake_host, one_tile_box):
    fake_host.fixed_status = 503
    strategy = INSETS.TileGridHttpStrategy()
    with pytest.raises(INSETS.TransientFetchError):
        strategy.discover(_definition(fake_host), one_tile_box)
