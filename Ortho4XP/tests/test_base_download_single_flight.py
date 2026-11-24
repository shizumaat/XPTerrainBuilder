"""Base elevation downloads through the download manager (#2258, round
lrm1): the cells of one de Ferranti archive share ONE download, a file is
streamed to a private temporary and installed whole, and a Stop ends a
transfer or a wait for the cell's flight at once.  Loopback only."""
from __future__ import annotations

import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_DEM_Utils as DEM  # noqa: E402
import O4_Download_Manager as DOWNLOADS  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Machine_Slots as SLOTS  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from elevation_access import registry as ea_registry  # noqa: E402

from test_viewfinder_base_archive import (  # noqa: E402
    KGEG_ZONE, MEMBER_PAYLOAD, _ArchiveHandler, _definition, _zone_archive)

#: Two cells of the L11 zone (44-48N, 120-114W).
CELLS = [(47, -118), (46, -117)]


@pytest.fixture(autouse=True)
def _session(tmp_path, monkeypatch):
    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "8")
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "elev"))
    UI.red_flag = False
    yield
    UI.red_flag = False


@pytest.fixture
def archive_server():
    """The viewfinder twin's loopback archive server."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ArchiveHandler)
    server.status = 200
    server.body = b""
    server.requested_paths = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def _temporaries(root):
    return [name for (_d, _s, names) in os.walk(root) for name in names
            if ".tmp-" in name]


def test_the_cells_of_one_archive_share_one_download(archive_server,
                                                     tmp_path):
    archive_server.body = _zone_archive(KGEG_ZONE, CELLS)
    strategy = ea_registry.ACCESS_STRATEGIES["viewfinder_zip"]()
    results = []
    threads = [threading.Thread(target=lambda cell=cell: results.append(
        strategy.ensure_tile(_definition(archive_server), *cell,
                             verbose=False))) for cell in CELLS]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert results == [1, 1]
    assert archive_server.requested_paths == ["/dem3/%s.zip" % KGEG_ZONE]
    for cell in CELLS:
        with open(FNAMES.viewfinderpanorama(*cell), "rb") as handle:
            assert handle.read() == MEMBER_PAYLOAD
    assert _temporaries(tmp_path / "elev") == []


class _SlowHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):                                     # noqa: N802
        self.send_response(200)
        self.send_header("Content-Length", str(1 << 24))
        self.end_headers()
        try:
            for _ in range(1 << 10):
                self.wfile.write(b"\x00" * (1 << 14))
                self.wfile.flush()
                time.sleep(0.05)
        except OSError:
            pass

    def log_message(self, *args):
        return


@pytest.fixture
def slow_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()
    server.server_close()


def test_stop_ends_a_usgs_transfer_and_installs_nothing(slow_server,
                                                        tmp_path):
    definition = {"code": "NED1", "legacy_keyword": "NED1",
                  "access_strategy": "usgs_seamless",
                  "download_url_template": slow_server + "/{tile_identifier}"}
    strategy = ea_registry.ACCESS_STRATEGIES["usgs_seamless"]()
    timer = threading.Timer(0.5, lambda: setattr(UI, "red_flag", True))
    timer.start()
    stopped_at = []
    UI_watch = threading.Thread(target=lambda: (
        timer.join(), stopped_at.append(time.monotonic())))
    UI_watch.start()
    assert strategy.ensure_tile(definition, 37, -87, verbose=False) == 0
    ended = time.monotonic()
    UI_watch.join(5)
    assert ended - stopped_at[0] < 2.0
    assert not os.path.exists(FNAMES.elevation_data("NED1", 37, -87))
    assert _temporaries(tmp_path / "elev") == []


def test_http_request_streams_to_its_destination(archive_server, tmp_path):
    archive_server.body = b"payload" * 100
    path = str(tmp_path / "body")
    host, port = archive_server.server_address
    response = DEM.http_request("http://%s:%d/x.zip" % (host, port), "View",
                                destination=path)
    assert response
    with open(path, "rb") as handle:
        assert handle.read() == b"payload" * 100


def test_stop_ends_the_wait_for_another_build_s_cell(tmp_path):
    INSETS.initialize_elevation_providers_dict(
        os.path.join("Providers", "Elevation"))
    definition = INSETS.resolve_base_definition(47, -118, "View")
    lock = os.path.join(FNAMES.Elevation_dir, FNAMES.round_latlon(47, -118),
                        ".lock_%s_%s.lock" % (definition["code"],
                                                FNAMES.hem_latlon(47, -118)))
    with DOWNLOADS.hold_flight(lock):
        timer = threading.Timer(0.3, lambda: setattr(UI, "red_flag", True))
        timer.start()
        started = time.monotonic()
        assert INSETS.ensure_base_tile("View", 47, -118, verbose=False) == 0
        assert time.monotonic() - started < 2.0
