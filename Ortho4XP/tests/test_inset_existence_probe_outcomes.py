"""THE EXISTENCE PROBE OBEYS THE OUTCOME LAW (issue #124, RULINGS 2026-09-13b).

``DegreeNamedCogStrategy._url_exists`` -- the one HEAD probe COPERNICUSGLO30
and every other degree-named COG provider use to tell an ocean-only cell
(absent from the bucket) from a land cell -- used to answer ``False`` for
EVERY answer that was not a 200 or a 404.  A CDN 403, a proxy 407, a 429 or
a 503 therefore meant "this cell does not exist", ``discover`` returned
``None``, and the module-wide convention records a returned ``None`` as a
DURABLE ``no-coverage`` for the airport: the #121 class again, a failed
transport becoming a permanent negative.

The law these twins pin, one class per test, against a REAL HTTP server on
loopback (no monkeypatched transport: the statuses travel over a socket, so
a change in how ``requests`` surfaces them cannot quietly pass):

* 2xx                    -> exists, memoised.
* 404 / 410              -> absent, memoised -- the ONLY durable negative.
* 401 403 405 407 451 501-> ``ProviderUnavailable`` (the host refused to
  serve this client; it never looked for the cell), NOT memoised.
* 429 / 5xx              -> ``TransientFetchError``, NOT memoised.
* anything else           -> ``TransientFetchError``: an answer nobody
  recognised says nothing about the cell.
* no answer at all       -> ``TransientFetchError``, whatever the
  exception's wording (#121 classified the MESSAGE and fell through to a
  durable absent for every message not on its fragment list).
"""
from __future__ import annotations

import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, "src")

import O4_Airport_Elevation_Insets as INSETS
from elevation_access import base as ea_base
from elevation_access import discovery as ea_discovery
from elevation_access.strategies import degree_named_cog as ea_degree_named_cog

#: A cell whose object the Copernicus mirror would hold, as a URL template
#: of the shape the .elv definitions use.
CELL_LATITUDE, CELL_LONGITUDE = 47, -118
#: A box wholly inside that one cell, so discovery probes exactly once.
ONE_CELL_BOX = (-117.6, 47.6, -117.5, 47.7)

#: Statuses the law calls a host refusal, and the one it calls absent.
UNAVAILABLE_STATUSES = (401, 403, 405, 407, 451)
ABSENT_STATUSES = (404, 410)
TRANSIENT_STATUSES = (429, 500, 501, 502, 503, 504, 400, 418)


class _FixedStatusHandler(BaseHTTPRequestHandler):
    """Answers every HEAD with the status in ``server.fixed_status``."""

    protocol_version = "HTTP/1.1"

    def do_HEAD(self):                                    # noqa: N802
        self.server.probed_paths.append(self.path)
        self.send_response(self.server.fixed_status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):                         # keep pytest quiet
        return


@pytest.fixture
def fake_bucket():
    """A loopback HTTP server whose status each test sets."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FixedStatusHandler)
    server.fixed_status = 200
    server.probed_paths = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _clear_the_memo():
    """The existence memo is process-lifetime state on the CLASS."""
    ea_degree_named_cog.DegreeNamedCogStrategy._cell_exists_by_url.clear()
    yield
    ea_degree_named_cog.DegreeNamedCogStrategy._cell_exists_by_url.clear()


def _definition(server):
    host, port = server.server_address[0], server.server_address[1]
    return {
        "code": "COPERNICUSGLO30",
        "url_template": (
            "http://%s:%d/Copernicus_DSM_COG_10_{latitude_token}_00_"
            "{longitude_token}_00_DEM.tif" % (host, port)
        ),
    }


def _probe(server, status):
    server.fixed_status = status
    strategy = ea_degree_named_cog.DegreeNamedCogStrategy()
    definition = _definition(server)
    url = strategy._cell_url(definition, CELL_LATITUDE, CELL_LONGITUDE)
    return strategy, definition, url


# ---------------------------------------------------------------------------
# 1. the classifier itself -- and that it never drifts from the module's
#    ONE transient convention
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status", [200, 201, 204, 206, 299])
def test_a_success_is_an_existence_answer(status):
    assert ea_discovery.http_answer_outcome(status) == ea_discovery.HTTP_OUTCOME_OK


@pytest.mark.parametrize("status", ABSENT_STATUSES)
def test_only_a_look_that_found_nothing_is_durable(status):
    assert ea_discovery.http_answer_outcome(status) == ea_discovery.HTTP_OUTCOME_ABSENT


@pytest.mark.parametrize("status", UNAVAILABLE_STATUSES)
def test_a_host_refusal_is_unavailable(status):
    assert (ea_discovery.http_answer_outcome(status)
            == ea_discovery.HTTP_OUTCOME_UNAVAILABLE)


@pytest.mark.parametrize("status", TRANSIENT_STATUSES)
def test_everything_else_is_transient(status):
    assert ea_discovery.http_answer_outcome(status) == ea_discovery.HTTP_OUTCOME_TRANSIENT


def test_no_status_outside_the_two_absent_ones_is_ever_durable():
    """The whole point of the law, swept over every HTTP status."""
    durable = [
        status for status in range(100, 600)
        if ea_discovery.http_answer_outcome(status) == ea_discovery.HTTP_OUTCOME_ABSENT
    ]
    assert durable == list(ea_discovery.HTTP_ABSENT_STATUSES)


def test_the_outcome_law_never_drifts_from_the_discovery_classifier():
    """SQ3: the module has ONE transient convention, not two."""
    for status in range(100, 600):
        if ea_discovery.discovery_status_is_transient(status):
            assert (ea_discovery.http_answer_outcome(status)
                    == ea_discovery.HTTP_OUTCOME_TRANSIENT), status


@pytest.mark.parametrize("status", [None, "", "not a status", object()])
def test_an_unreadable_status_is_transient(status):
    assert ea_discovery.http_answer_outcome(status) == ea_discovery.HTTP_OUTCOME_TRANSIENT


# ---------------------------------------------------------------------------
# 2. the probe, over a socket, one outcome class per test
# ---------------------------------------------------------------------------
def test_a_served_cell_exists_and_is_memoised(fake_bucket):
    strategy, definition, url = _probe(fake_bucket, 200)
    assert strategy._url_exists(url) is True
    assert ea_degree_named_cog.DegreeNamedCogStrategy._cell_exists_by_url[url] is True
    # the memo answers the second ask without a second request
    assert strategy._url_exists(url) is True
    assert len(fake_bucket.probed_paths) == 1


@pytest.mark.parametrize("status", ABSENT_STATUSES)
def test_a_cell_the_server_looked_for_is_absent_and_memoised(
        fake_bucket, status):
    strategy, definition, url = _probe(fake_bucket, status)
    assert strategy._url_exists(url) is False
    assert ea_degree_named_cog.DegreeNamedCogStrategy._cell_exists_by_url[url] is False
    assert strategy.discover(definition, ONE_CELL_BOX) is None


@pytest.mark.parametrize("status", UNAVAILABLE_STATUSES)
def test_a_host_refusal_raises_unavailable_and_is_not_memoised(
        fake_bucket, status):
    strategy, definition, url = _probe(fake_bucket, status)
    with pytest.raises(ea_base.ProviderUnavailable) as refusal:
        strategy._url_exists(url)
    assert str(status) in str(refusal.value)
    assert url in str(refusal.value)
    assert "no-coverage" in str(refusal.value)
    assert ea_degree_named_cog.DegreeNamedCogStrategy._cell_exists_by_url == {}


@pytest.mark.parametrize("status", TRANSIENT_STATUSES)
def test_a_transient_answer_raises_and_is_not_memoised(fake_bucket, status):
    strategy, definition, url = _probe(fake_bucket, status)
    with pytest.raises(ea_base.TransientFetchError) as refusal:
        strategy._url_exists(url)
    assert str(status) in str(refusal.value)
    assert ea_degree_named_cog.DegreeNamedCogStrategy._cell_exists_by_url == {}


def test_no_answer_at_all_raises_whatever_the_wording(fake_bucket):
    """The #121 half: a probe that got no HTTP answer is never absent.

    The server is shut down first, so the connection is refused -- an
    error whose text is on no fragment list, which the historic code
    answered ``False`` to.
    """
    strategy, definition, url = _probe(fake_bucket, 200)
    fake_bucket.shutdown()
    fake_bucket.server_close()
    with pytest.raises(ea_base.TransientFetchError) as refusal:
        strategy._url_exists(url)
    assert "transport" in str(refusal.value)
    assert ea_degree_named_cog.DegreeNamedCogStrategy._cell_exists_by_url == {}


# ---------------------------------------------------------------------------
# 3. the pass level: a refusal must reach the caller, never a None
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status", [403, 503])
def test_discovery_raises_rather_than_answering_no_coverage(
        fake_bucket, status):
    """``discover`` returning ``None`` is what gets written to the index."""
    strategy, definition, _url = _probe(fake_bucket, status)
    with pytest.raises(
            (ea_base.ProviderUnavailable, ea_base.TransientFetchError)):
        strategy.discover(definition, ONE_CELL_BOX)


@pytest.mark.parametrize("status", [403, 503])
def test_a_fetch_refuses_too_rather_than_returning_nothing(
        fake_bucket, status):
    strategy, definition, _url = _probe(fake_bucket, status)
    if not INSETS.has_gdal:
        pytest.skip("the fetch short-circuits without GDAL")
    with pytest.raises(
            (ea_base.ProviderUnavailable, ea_base.TransientFetchError)):
        strategy.fetch(definition, ONE_CELL_BOX, 30.0, "unused.tif")


def test_one_refused_cell_does_not_poison_the_next_airport(fake_bucket):
    """The memo must not carry a non-definitive answer forward."""
    strategy, definition, url = _probe(fake_bucket, 403)
    with pytest.raises(ea_base.ProviderUnavailable):
        strategy._url_exists(url)
    fake_bucket.fixed_status = 200
    assert strategy._url_exists(url) is True
