"""AN UNREADABLE TILE INDEX IS ONE CLEAR FAILURE, AND TLS IS EXTENDED, NEVER WEAKENED (#1923).

``tile_grid_http`` definitions whose tile names carry tokens only an index
knows (``tile_url_template={file_name}`` + ``index_url``) used to answer an
unreadable index with ``None``, and ``discover`` then took the TEMPLATE
path and HEAD-probed the literal ``{file_name}``: "tile existence probe for
{file_name} died on the transport: Invalid URL '{file_name}'" for every
Schleswig-Holstein airport.  The index failure itself must be the failure:

* no answer / 429 / 5xx / an index naming nothing -> ``TransientFetchError``;
* 401 / 403 / 404 / 410 ...                        -> ``ProviderUnavailable``;
* no request is ever made for a URL holding ``{file_name}``.

And the cause -- a host that omits its intermediate certificate -- is met
by a pinned, shipped intermediate added to certifi's roots for that
provider only (``elevation_access.tls_trust``): a pin mismatch refuses.
Loopback HTTP only; no network.
"""
from __future__ import annotations

import socket
import ssl
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, "src")

import O4_File_Names as FNAMES
from elevation_access import base as ea_base
from elevation_access import tls_trust
from elevation_access.strategies import tile_grid_http as ea_tile_grid_http

#: A box inside the Schleswig-Holstein coverage (Kiel).
KIEL_BOX = (10.15, 54.37, 10.17, 54.38)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _answer(self):
        self.server.paths.append(self.path)
        self.send_response(self.server.status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_HEAD = _answer                                      # noqa: N815
    do_GET = _answer                                       # noqa: N815

    def log_message(self, *args):
        return


@pytest.fixture
def host():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.status = 200
    server.paths = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(autouse=True)
def elevation_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))


def _definition(index_url):
    return {
        "code": "TESTSH1M",
        "access_strategy": "tile_grid_http",
        "tile_url_template": "{file_name}",
        "index_url": index_url,
        "tile_size_km": "1",
        "source_epsg": "25832",
        "coverage_bbox": "7.8,53.3,11.4,55.1",
    }


def _dead_url():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return "http://127.0.0.1:%d/index.geojson" % port


def _no_template_probes(monkeypatch):
    """Fail the test on any request whose URL still holds ``{file_name}``."""
    import requests

    for name in ("head", "get"):
        original = getattr(requests.Session, name)

        def _guard(self, url, *args, _original=original, **kwargs):
            assert "{" not in str(url), "probed an unfilled template: %s" % url
            return _original(self, url, *args, **kwargs)

        monkeypatch.setattr(requests.Session, name, _guard)


def test_an_unreachable_index_is_one_transient_failure(monkeypatch):
    _no_template_probes(monkeypatch)
    strategy = ea_tile_grid_http.TileGridHttpStrategy()
    with pytest.raises(ea_base.TransientFetchError) as raised:
        strategy.discover(_definition(_dead_url()), KIEL_BOX)
    message = str(raised.value)
    assert message.startswith("tile index ")
    assert "unavailable" in message and "{file_name}" not in message


@pytest.mark.parametrize("status", [429, 500, 503])
def test_a_server_side_index_failure_is_transient(host, status, monkeypatch):
    _no_template_probes(monkeypatch)
    host.status = status
    url = "http://127.0.0.1:%d/index.geojson" % host.server_address[1]
    with pytest.raises(ea_base.TransientFetchError):
        ea_tile_grid_http.TileGridHttpStrategy().discover(
            _definition(url), KIEL_BOX)
    assert host.paths == ["/index.geojson"]


@pytest.mark.parametrize("status", [401, 403, 404, 410])
def test_a_refused_or_vanished_index_is_unavailable(host, status):
    host.status = status
    url = "http://127.0.0.1:%d/index.geojson" % host.server_address[1]
    with pytest.raises(ea_base.ProviderUnavailable):
        ea_tile_grid_http.TileGridHttpStrategy().discover(
            _definition(url), KIEL_BOX)
    assert host.paths == ["/index.geojson"]


def test_a_file_name_template_without_an_index_is_refused():
    definition = _definition("")
    with pytest.raises(ea_base.ProviderUnavailable):
        ea_tile_grid_http.TileGridHttpStrategy().discover(
            definition, KIEL_BOX)


# ---------------------------------------------------------------------------
# the extra certificate authority
# ---------------------------------------------------------------------------
def _shipped_definition(code):
    import O4_Airport_Elevation_Insets as INSETS

    return INSETS.initialize_elevation_providers_dict()[code]


@pytest.mark.parametrize(
    "code", ["SCHLESWIGHOLSTEIN1M", "SCHLESWIGHOLSTEINTIDAL"])
def test_the_shipped_intermediate_matches_its_pin_and_chains_to_certifi(code):
    import certifi

    definition = _shipped_definition(code)
    bundle = tls_trust.requests_verify(definition)
    assert isinstance(bundle, str)
    subjects = {}
    context = ssl.create_default_context(cafile=bundle)
    for cert in context.get_ca_certs():
        subject = dict(pair[0] for pair in cert["subject"])
        issuer = dict(pair[0] for pair in cert["issuer"])
        subjects[subject.get("commonName")] = issuer.get("commonName")
    assert subjects["D-TRUST BR CA 1-20-1 2020"] == "D-TRUST BR Root CA 1 2020"
    roots = ssl.create_default_context(cafile=certifi.where())
    assert any(
        dict(pair[0] for pair in cert["subject"]).get("commonName")
        == "D-TRUST BR Root CA 1 2020" for cert in roots.get_ca_certs())


def test_no_extra_ca_keeps_requests_default():
    assert tls_trust.requests_verify({"code": "X"}) is True


def test_a_pin_mismatch_refuses_rather_than_weakens():
    definition = dict(_shipped_definition("SCHLESWIGHOLSTEIN1M"))
    definition["tls_extra_ca_sha256"] = "00" * 32
    with pytest.raises(ea_base.ProviderUnavailable) as raised:
        tls_trust.requests_verify(definition)
    assert "not its pin" in str(raised.value)


def test_a_missing_pin_refuses():
    definition = dict(_shipped_definition("SCHLESWIGHOLSTEIN1M"))
    definition.pop("tls_extra_ca_sha256")
    with pytest.raises(ea_base.ProviderUnavailable):
        tls_trust.requests_verify(definition)


# ---------------------------------------------------------------------------
# an archive index: one remote zip whose members are the tiles (Hamburg)
# ---------------------------------------------------------------------------
def _archive_definition(zip_path):
    definition = _definition("/vsizip/" + str(zip_path))
    definition["code"] = "TESTHH1M"
    return definition


def test_an_archive_index_lists_members_and_discover_reads_them_in_place(
        tmp_path):
    import zipfile

    from elevation_access.definitions import transform_bounding_box_to_epsg

    (x_min, y_min, _x, _y) = transform_bounding_box_to_epsg(KIEL_BOX, 25832)
    (easting, northing) = (int(x_min // 1000), int(y_min // 1000))
    member = "dgm1/s32_%d/dgm1_32_%d_%d_1_hh_2022.tif" % (
        easting, easting, northing)
    zip_path = tmp_path / "dgm1.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(member, b"not read here")
        archive.writestr("dgm1/readme.csv", b"x")
    sources = ea_tile_grid_http.TileGridHttpStrategy().discover(
        _archive_definition(zip_path), KIEL_BOX)
    urls = [source["url"] for source in sources]
    assert urls == ["/vsizip/%s/%s" % (zip_path, member)]


def test_an_unreadable_archive_index_is_transient(tmp_path):
    definition = _archive_definition(tmp_path / "missing.zip")
    with pytest.raises(ea_base.TransientFetchError) as raised:
        ea_tile_grid_http.TileGridHttpStrategy().discover(
            definition, KIEL_BOX)
    assert str(raised.value).startswith("tile index /vsizip/")
