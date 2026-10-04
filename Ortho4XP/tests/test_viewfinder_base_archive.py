"""THE VIEWFINDER BASE ARCHIVE NEVER DEGRADES TO ZERO (issue #173).

Measured 2026-10-02 at KGEG (+47-118): the engine printed "Downloading
/.../Elevation_data/+40-120/N47W118.hgt from Viewfinderpanoramas" for all
nine cells of the 3x3, then "* Min altitude: 0.0 , Max altitude: 0.0 ,
Mean: 0.0", and no ``.hgt`` landed.  The #121 law (broken = refuse, never
degrade to zero) covered transport failures only, so every other way the
download could answer nothing ended in ``return 0`` -- which the DEM loader
turns into an ALL-ZERO cell and finishes the build with exit 0.

Two halves, both pinned here.

THE MAPPING (static, so it is twinned exhaustively rather than sampled):
the de Ferranti archive code is a 6x4 degree zone name, and the zone it
names must CONTAIN the tile asked for.  +47-118 -> ``L11`` ->
``https://viewfinderpanoramas.org/dem3/L11.zip``, and L11 is 44-48N,
120-114W: the mapping for KGEG is RIGHT, so the silent zero came from the
transport/answer classification, not from the zone table.

THE ANSWER (against a real HTTP server on loopback, serving archives with
the real member layout -- ``L11/N47W118.hgt``):

* a served archive extracts and the ``.hgt`` lands;
* a 404 for a LAND cell REFUSES, naming the URL and the cell;
* a 404 for an OCEAN-only cell keeps the historic 0 (lawfully absent --
  the land verdict comes from the same ``Utils/world_tiles.png`` mask the
  DEM loader consults before it asks for a cell at all);
* a 403 (a bot wall or a CDN) REFUSES inside ``http_request`` -- it used
  to print "Server said 'Not Found'" and return 0, because the historic
  test was the substring "[40" of ``str(response)``;
* a 429 or a 5xx REFUSES after the retry cap -- a 429 used to match no
  branch at all, so it was retried six times and then returned 0 with no
  refusal recorded;
* an archive that downloads but holds NO member for the cell REFUSES and
  LISTS the members it does hold (the measurement #173 asks for);
* an archive whose member for the cell is present but CRC-damaged keeps
  the historic contained 0 (the dem1/P32.zip case, decided earlier) --
  that is upstream data damage, not a mapping defect.
"""
from __future__ import annotations

import io
import os
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, "src")

import O4_Airport_Elevation_Insets as INSETS
from elevation_access import base_tiles as ea_base_tiles
from elevation_access import registry as ea_registry
import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

SHIPPED_PROVIDERS_DIRECTORY = os.path.join("Providers", "Elevation")

#: The owner's site in #173: Spokane International, tile +47-118.
KGEG_TILE = (47, -118)
#: The dem3 zone that must contain it, and its 6x4 degree extent.
KGEG_ZONE = "L11"
#: A cell the world mask calls ocean (mid North Pacific), where an absent
#: archive is lawful.
OCEAN_TILE = (40, -150)

#: Letters de Ferranti numbers his 4-degree latitude bands with.
ZONE_LETTERS = "".join(ea_base_tiles.DEFERRANTI_ALPHABET)
#: Degrees of latitude per zone row and of longitude per zone column.
ZONE_LATITUDE_SPAN = 4
ZONE_LONGITUDE_SPAN = 6
#: Enough bytes that ``cached_elevation_file_is_valid`` accepts the file;
#: the real 3 arc-second member is 1201*1201*2 bytes, which this twin has
#: no reason to move over a socket.
MEMBER_PAYLOAD = b"\x00\x7f" * 64

#: Shortened for the twins that must reach the retry cap: the shipped cap
#: of 6 spends 2+4+8+16+32 s of exponential back-off getting there.
TEST_ATTEMPT_CAP = 2


# ---------------------------------------------------------------------------
# the zone table -- pure arithmetic, so every zone is checked
# ---------------------------------------------------------------------------
def _zone_extent(code):
    """The (south, north, west, east) a zone code names."""
    southern = code.startswith("S")
    letters = code[1:] if southern else code
    letter, number = letters[0], int(letters[1:])
    row = ZONE_LETTERS.index(letter)
    if southern:
        south = -ZONE_LATITUDE_SPAN * (row + 1)
    else:
        south = ZONE_LATITUDE_SPAN * row
    west = ZONE_LONGITUDE_SPAN * (number - 31)
    return (south, south + ZONE_LATITUDE_SPAN,
            west, west + ZONE_LONGITUDE_SPAN)


def test_the_kgeg_zone_is_right():
    """#173's first question, answered: the mapping is NOT the defect."""
    assert ea_base_tiles.deferranti_archive_code(*KGEG_TILE) == KGEG_ZONE
    assert _zone_extent(KGEG_ZONE) == (44, 48, -120, -114)
    south, north, west, east = _zone_extent(KGEG_ZONE)
    assert south <= KGEG_TILE[0] < north
    assert west <= KGEG_TILE[1] < east


def test_the_kgeg_url_is_the_dem3_zone_archive(shipped_registry):
    definition = INSETS.elevation_providers_dict["VIEWFINDER3"]
    strategy = ea_registry.ACCESS_STRATEGIES["viewfinder_zip"]()
    assert strategy.download_url(definition, *KGEG_TILE) == (
        "https://viewfinderpanoramas.org/dem3/%s.zip" % KGEG_ZONE)


def test_every_zone_contains_the_tile_it_is_named_for():
    """The whole table, both hemispheres, every column."""
    checked = 0
    for latitude in range(-56, 60):
        for longitude in range(-180, 180):
            code = ea_base_tiles.deferranti_archive_code(latitude, longitude)
            south, north, west, east = _zone_extent(code)
            assert south <= latitude < north, (latitude, longitude, code)
            assert west <= longitude < east, (latitude, longitude, code)
            checked += 1
    assert checked == 116 * 360


def test_the_zone_columns_tile_the_globe_without_a_gap():
    """Column arithmetic: 1 at 180W through 60 at 174E, no repeats."""
    columns = {
        ea_base_tiles.deferranti_archive_code(0, longitude)[1:]
        for longitude in range(-180, 180)
    }
    assert len(columns) == 360 // ZONE_LONGITUDE_SPAN
    assert ea_base_tiles.deferranti_archive_code(0, -180) == "A01"
    assert ea_base_tiles.deferranti_archive_code(0, 174) == "A60"


@pytest.mark.parametrize("latitude,longitude,code", [
    (47, -118, "L11"),            # KGEG, the measured case
    (46, 7, "L32"),               # the Alps 1 arc-second zone
    (36, -87, "J16"),             # the historic dem3 witness
    (-42, 174, "SK60"),           # Wellington, southern hemisphere
    (-1, -1, "SA30"),             # just south-west of the origin
    (0, 0, "A31"),                # the origin cell
])
def test_known_zone_codes(latitude, longitude, code):
    assert ea_base_tiles.deferranti_archive_code(latitude, longitude) == code


# ---------------------------------------------------------------------------
# the member grammar -- a zone's own members must map back to its tiles
# ---------------------------------------------------------------------------
def _member_name(latitude, longitude):
    """The ``.hgt`` member name de Ferranti stores a tile under."""
    return "%s%02d%s%03d.hgt" % (
        "N" if latitude >= 0 else "S", abs(latitude),
        "E" if longitude >= 0 else "W", abs(longitude))


@pytest.mark.parametrize("latitude,longitude", [
    (47, -118), (46, 7), (-42, 174), (0, 0), (-1, -1), (60, 6), (25, 51),
])
def test_a_member_name_round_trips_to_its_cell(latitude, longitude, tmp_path,
                                               monkeypatch):
    """The parse ``ensure_tile`` does on each member, pinned per hemisphere."""
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    name = _member_name(latitude, longitude)
    parsed_latitude = int(name[1:3]) * (-1 if name[0] == "S" else 1)
    parsed_longitude = int(name[4:7]) * (-1 if name[3] == "W" else 1)
    assert (parsed_latitude, parsed_longitude) == (latitude, longitude)
    assert FNAMES.viewfinderpanorama(parsed_latitude, parsed_longitude) == (
        FNAMES.viewfinderpanorama(latitude, longitude))


# ---------------------------------------------------------------------------
# the answer classes, over a socket
# ---------------------------------------------------------------------------
def _zone_archive(zone, tiles):
    """A zip with the real layout: ``<zone>/<member>.hgt`` per tile."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for (latitude, longitude) in tiles:
            archive.writestr(
                "%s/%s" % (zone, _member_name(latitude, longitude)),
                MEMBER_PAYLOAD)
    return buffer.getvalue()


class _ArchiveHandler(BaseHTTPRequestHandler):
    """Serves ``server.body`` with ``server.status`` for any path."""

    protocol_version = "HTTP/1.1"

    def do_GET(self):                                     # noqa: N802
        self.server.requested_paths.append(self.path)
        body = self.server.body if self.server.status == 200 else b""
        self.send_response(self.server.status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, *args):
        return


@pytest.fixture
def fake_viewfinder():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ArchiveHandler)
    server.status = 200
    server.body = _zone_archive(KGEG_ZONE, [KGEG_TILE])
    server.requested_paths = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def shipped_registry():
    INSETS.initialize_elevation_providers_dict(SHIPPED_PROVIDERS_DIRECTORY)
    yield INSETS.elevation_providers_dict


@pytest.fixture(autouse=True)
def _clean_flag():
    UI.red_flag = False
    yield
    UI.red_flag = False


def _definition(server):
    host, port = server.server_address[0], server.server_address[1]
    return {
        "code": "VIEWFINDER3",
        "legacy_keyword": "View",
        "access_strategy": "viewfinder_zip",
        "download_url_template": (
            "http://%s:%d/dem3/{archive_code}.zip" % (host, port)),
    }


def _ensure(server, tmp_path, monkeypatch, tile=KGEG_TILE, cap=None):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    if cap is not None:
        monkeypatch.setattr(DEM, "HTTP_REQUEST_ATTEMPT_CAP", cap)
        monkeypatch.setattr(DEM.time, "sleep", lambda _seconds: None)
    strategy = ea_registry.ACCESS_STRATEGIES["viewfinder_zip"]()
    return strategy.ensure_tile(_definition(server), *tile, verbose=False)


def test_a_served_archive_lands_the_requested_hgt(
        fake_viewfinder, tmp_path, monkeypatch):
    assert _ensure(fake_viewfinder, tmp_path, monkeypatch) == 1
    landed = FNAMES.viewfinderpanorama(*KGEG_TILE)
    with open(landed, "rb") as handle:
        assert handle.read() == MEMBER_PAYLOAD
    assert fake_viewfinder.requested_paths == ["/dem3/%s.zip" % KGEG_ZONE]


def test_a_404_for_a_land_cell_refuses_with_the_url(
        fake_viewfinder, tmp_path, monkeypatch):
    fake_viewfinder.status = 404
    with pytest.raises(DEM.ElevationDownloadRefused) as refusal:
        _ensure(fake_viewfinder, tmp_path, monkeypatch)
    message = str(refusal.value)
    assert "/dem3/%s.zip" % KGEG_ZONE in message
    assert "+47-118" in message
    assert "all-zero" in message
    assert not os.path.exists(FNAMES.viewfinderpanorama(*KGEG_TILE))


def test_a_404_for_an_ocean_cell_is_lawfully_absent(
        fake_viewfinder, tmp_path, monkeypatch):
    assert DEM.tile_is_land(*OCEAN_TILE) is False
    fake_viewfinder.status = 404
    assert _ensure(fake_viewfinder, tmp_path, monkeypatch,
                   tile=OCEAN_TILE) == 0


@pytest.mark.parametrize("status", [401, 403, 407, 451])
def test_a_host_refusal_is_never_read_as_not_found(
        fake_viewfinder, tmp_path, monkeypatch, status):
    """The historic classifier called every 40x "Not Found"."""
    fake_viewfinder.status = status
    with pytest.raises(DEM.ElevationDownloadRefused) as refusal:
        _ensure(fake_viewfinder, tmp_path, monkeypatch)
    assert str(status) in str(refusal.value)
    assert "REFUSED" in str(refusal.value)
    # refused on the FIRST answer: there is nothing to retry
    assert len(fake_viewfinder.requested_paths) == 1


@pytest.mark.parametrize("status", [429, 500, 503])
def test_a_transient_answer_refuses_after_the_cap_never_zero(
        fake_viewfinder, tmp_path, monkeypatch, status):
    """A 429 matched no branch at all and returned a silent 0."""
    fake_viewfinder.status = status
    with pytest.raises(DEM.ElevationDownloadRefused) as refusal:
        _ensure(fake_viewfinder, tmp_path, monkeypatch,
                cap=TEST_ATTEMPT_CAP)
    assert str(status) in str(refusal.value)
    assert len(fake_viewfinder.requested_paths) == TEST_ATTEMPT_CAP


def test_an_archive_without_the_cell_refuses_and_lists_its_members(
        fake_viewfinder, tmp_path, monkeypatch):
    """The mapping-defect half: wrong zone, or a member grammar we misread."""
    neighbours = [(45, -119), (45, -118), (46, -119)]
    fake_viewfinder.body = _zone_archive(KGEG_ZONE, neighbours)
    with pytest.raises(DEM.ElevationDownloadRefused) as refusal:
        _ensure(fake_viewfinder, tmp_path, monkeypatch)
    message = str(refusal.value)
    assert "holds no member for this cell" in message
    for (latitude, longitude) in neighbours:
        assert _member_name(latitude, longitude) in message
    # the neighbours it DID hold still landed -- a refusal is not a rollback
    assert os.path.exists(FNAMES.viewfinderpanorama(*neighbours[0]))


def test_a_damaged_member_for_the_cell_is_still_contained(
        fake_viewfinder, tmp_path, monkeypatch):
    """Upstream CRC damage (dem1/P32.zip) stays a contained 0, not a refusal.

    The member IS in the archive: the mapping is right and the data is
    broken, which is a different fact from the archive not holding the
    cell at all.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr(
            "%s/%s" % (KGEG_ZONE, _member_name(*KGEG_TILE)),
            b"BADDATA!" * 64)
    fake_viewfinder.body = buffer.getvalue().replace(b"BADDATA!", b"XADDATA!")
    assert _ensure(fake_viewfinder, tmp_path, monkeypatch) == 0
    assert not os.path.exists(FNAMES.viewfinderpanorama(*KGEG_TILE))


def test_a_dead_server_still_refuses_on_the_transport(
        fake_viewfinder, tmp_path, monkeypatch):
    """The #121 half, unchanged: no answer at all refuses."""
    fake_viewfinder.shutdown()
    fake_viewfinder.server_close()
    with pytest.raises(DEM.ElevationDownloadRefused):
        _ensure(fake_viewfinder, tmp_path, monkeypatch, cap=TEST_ATTEMPT_CAP)


# ---------------------------------------------------------------------------
# the land predicate -- ONE spelling, shared by every reader
# ---------------------------------------------------------------------------
def test_the_land_mask_is_read_one_way():
    assert DEM.tile_is_land(*KGEG_TILE) is True
    assert DEM.tile_is_land(*OCEAN_TILE) is False
    # unreadable mask -> land, the conservative direction
    monkey = DEM._world_tiles_mask[0]
    try:
        DEM._world_tiles_mask[0] = False
        assert DEM.tile_is_land(*OCEAN_TILE) is True
    finally:
        DEM._world_tiles_mask[0] = monkey
    # An impossible latitude must not be answered from the far side of
    # the mask by a negative numpy index: out of range is conservative.
    assert DEM.tile_is_land(95, 0) is True
    assert DEM.tile_is_land(-91, 0) is True
    assert DEM.tile_is_land(None, None) is True
    # longitude still wraps, which is how the DEM loader asks for the
    # neighbours of a tile at the antimeridian
    assert DEM.tile_is_land(47, -118) == DEM.tile_is_land(47, 242)
