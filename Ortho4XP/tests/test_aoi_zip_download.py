"""THE AOI ZIP DOWNLOAD STRATEGY (spec us-holder-providers §3.6, RULINGS
2026-09-30bm; the WA DNR gate per OWNER RULINGS 2026-09-30bn; issue #154,
lane aoi154).

The Washington DNR lidar portal and the Alaska DGGS elevation portal run
the same software: ``POST query`` (form ``geojson=<Polygon>``) answers
``[{dataset_id, files, bytes, ...}]``; ``GET download?geojson=&ids=``
streams one zip of GeoTIFF tiles.  These twins pin, against a FAKE portal
(no network): the listing classes (durable no-coverage only for a
well-formed answer without the dataset; 5xx / non-JSON / an exception are
transient), the cap judged on the portal's byte answer BEFORE any download
(``unavailable`` in the shared cap wording, Zip64 refused), THE GATE (one
front-page GET per process, its cookies replayed until their Max-Age, a
browser agent; a 403 / a login / no cookie is ``unavailable: ... gate``
after exactly ONE request -- never a retry loop), the members read through
``/vsizip/`` into the shared warp with ``vertical_unit`` applied, the
surgical core, the scratch removed, and the three ``.elv`` files.
"""

import json
import os
import time
import zipfile

import numpy
import pytest
import requests

import O4_Airport_Elevation_Insets as INSETS
from elevation_access import base as ea_base
from elevation_access import definitions as ea_definitions
from elevation_access import las_tiles as ea_las_tiles
from elevation_access.strategies import aoi_zip_download as ea_aoi_zip_download
import O4_UI_Utils as UI

try:
    from osgeo import gdal, osr

    gdal.UseExceptions()
    HAS_GDAL = True
except Exception:                                        # pragma: no cover
    HAS_GDAL = False

pytestmark = pytest.mark.skipif(not HAS_GDAL, reason="no osgeo")

BOX = (-122.70, 48.33, -122.68, 48.35)        # KNUW-sized, Whidbey Island
SOURCE_BOX = (-122.71, 48.32, -122.67, 48.36)
SIZE = 40
FEET = 100.0                                  # every valid source cell, ftUS
NODATA = -999999.0
QUERY = "https://portal.test/query"
DOWNLOAD = "https://portal.test/download"
MEMBER = "datasetsC/whidbey_refresh23_2024/dtm/be_w1n1_dtm.tif"


@pytest.fixture(autouse=True)
def _fresh_gate_and_flag():
    ea_aoi_zip_download._aoi_gate_cookie_cache.clear()
    UI.red_flag = False
    yield
    ea_aoi_zip_download._aoi_gate_cookie_cache.clear()
    UI.red_flag = False


def _definition(**overrides):
    definition = {
        "code": "AOITEST",
        "access_strategy": "aoi_zip_download",
        "query_url": QUERY,
        "download_url": DOWNLOAD,
        "dataset_ids": "1783",
        "member_glob": "*/dtm/*_dtm.tif",
        "user_agent_profile": "engine",
        "vertical_unit": "ftUS",
        "source_nodata": str(NODATA),
        "native_resolution_m": 0.457,
        "max_bytes_per_airport": "300000000",
    }
    definition.update(overrides)
    return definition


def _tile_zip(tmp_path, member=MEMBER):
    """One zip holding one Float32 tile: FEET everywhere, a nodata hole."""
    tile = str(tmp_path / "tile.tif")
    dataset = gdal.GetDriverByName("GTiff").Create(
        tile, SIZE, SIZE, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform(
        (SOURCE_BOX[0], (SOURCE_BOX[2] - SOURCE_BOX[0]) / SIZE, 0.0,
         SOURCE_BOX[3], 0.0, -(SOURCE_BOX[3] - SOURCE_BOX[1]) / SIZE))
    srs = osr.SpatialReference()
    srs.SetFromUserInput("EPSG:4326")
    dataset.SetProjection(srs.ExportToWkt())
    values = numpy.full((SIZE, SIZE), FEET, dtype=numpy.float32)
    values[0:4, 0:4] = NODATA
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteArray(values)
    dataset = None
    archive = str(tmp_path / "custom_download.zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        handle.write(tile, member)
    with open(archive, "rb") as handle:
        return handle.read()


class _Cookie:
    def __init__(self, name, value, expires):
        self.name = name
        self.value = value
        self.domain = "portal.test"
        self.path = "/"
        self.expires = expires


class _Response:
    def __init__(self, status=200, payload=None, body=b"", url=None,
                 cookies=(), text_body=False):
        self.status_code = status
        self._payload = payload
        self._body = body
        self.url = url
        self.cookies = list(cookies)
        self._text_body = text_body

    def json(self):
        if self._text_body or self._payload is None:
            raise ValueError("not json")
        return self._payload

    def iter_content(self, size):
        for start in range(0, len(self._body), size):
            yield self._body[start:start + size]

    def close(self):
        pass


class _Jar:
    def __init__(self):
        self.values = {}

    def set(self, name, value, domain=None, path=None):
        self.values[name] = value


class _Portal:
    """A fake portal: the gate page, the query, the download.  Every
    request is logged as ``(verb, url, headers, cookies-at-call)``."""

    def __init__(self, listing=None, archive=b"", gate=None,
                 query_status=200, download_status=200, query_raises=None,
                 require_cookie=None):
        self.listing = listing if listing is not None else []
        self.archive = archive
        self.gate = gate                    # a _Response for the gate GET
        self.query_status = query_status
        self.download_status = download_status
        self.query_raises = query_raises
        self.require_cookie = require_cookie
        self.calls = []

    def session(self):
        portal = self

        class _Session:
            def __init__(self):
                self.headers = {}
                self.cookies = _Jar()

            def _log(self, verb, url, headers, data=None):
                merged = dict(self.headers)
                merged.update(headers or {})
                portal.calls.append(
                    (verb, url, merged, dict(self.cookies.values), data))

            def get(self, url, headers=None, timeout=None, stream=False,
                    allow_redirects=True):
                self._log("GET", url, headers)
                if url.startswith(DOWNLOAD):
                    if (portal.require_cookie
                            and portal.require_cookie
                            not in self.cookies.values):
                        return _Response(403)
                    return _Response(portal.download_status,
                                     body=portal.archive)
                return portal.gate

            def post(self, url, data=None, headers=None, timeout=None):
                self._log("POST", url, headers, data)
                if portal.query_raises is not None:
                    raise portal.query_raises
                if (portal.require_cookie
                        and portal.require_cookie not in self.cookies.values):
                    return _Response(403)
                if portal.query_status != 200:
                    return _Response(portal.query_status)
                return _Response(200, payload=portal.listing)

            def close(self):
                pass

        return _Session()

    def verbs(self):
        return [(verb, url.split("?")[0]) for (verb, url, *_r) in self.calls]


def _listing(bytes_=50000000, files=7, dataset_id=1783):
    return [
        {"dataset_id": 16, "files": 1, "bytes": 542605151,
         "project_name": "Island 2014", "dataset_name": "DTM"},
        {"dataset_id": dataset_id, "files": files, "bytes": bytes_,
         "project_name": "Whidbey Refresh23 2024", "dataset_name": "DTM"},
    ]


def _install(monkeypatch, portal):
    monkeypatch.setattr(requests, "Session", portal.session)


def _fetch(tmp_path, definition, box=BOX):
    destination = str(tmp_path / "KNUW_aoitest.tif")
    provenance = INSETS.fetch_inset(definition, box, 10.0, destination)
    return (provenance, destination)


# ---------------------------------------------------------------------------
# delivery: members through /vsizip/ -> VRT -> the shared warp, in metres
# ---------------------------------------------------------------------------
def test_a_listed_dataset_is_downloaded_warped_in_metres_and_cleaned(
        tmp_path, monkeypatch):
    archive = _tile_zip(tmp_path)
    portal = _Portal(listing=_listing(), archive=archive)
    _install(monkeypatch, portal)
    (provenance, destination) = _fetch(tmp_path, _definition())
    assert provenance is not None
    assert portal.verbs() == [("POST", QUERY), ("GET", DOWNLOAD)]
    # The browser's polygon text: coordinates pruned to 4 decimals, the box
    # rounded OUTWARD; the download asks the same polygon for the one id.
    posted = json.loads(portal.calls[0][4]["geojson"])
    assert posted["coordinates"][0][0] == [-122.70, 48.33]
    download_url = portal.calls[1][1]
    assert download_url.endswith("&ids=1783")
    assert provenance["source_ids"] == ["1783"]
    assert provenance["bytes_listed"] == 50000000
    assert provenance["bytes_fetched"] == len(archive)
    assert provenance["archive_members"] == [os.path.basename(MEMBER)]
    assert provenance["request_geometry"] == "box"
    assert provenance["gate"] is None
    assert provenance["vertical_unit_source"] == "elv"
    assert provenance["vertical_unit_applied"] == "m"
    dataset = gdal.Open(destination)
    band = dataset.GetRasterBand(1)
    values = band.ReadAsArray().astype(numpy.float64)
    nodata = band.GetNoDataValue()
    dataset = None
    valid = values[values != nodata]
    assert valid.size
    metres = FEET * 1200.0 / 3937.0
    assert numpy.allclose(valid, metres, atol=1e-3)
    # The zip and the VRT are scratch: gone after the warp.
    leftovers = [name for name in os.listdir(tmp_path)
                 if name.startswith("KNUW_aoitest.tif.")]
    assert leftovers == []


def test_the_surgical_core_is_what_the_portal_is_asked_for(
        tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(), archive=_tile_zip(tmp_path))
    _install(monkeypatch, portal)
    footprint = {"type": "Polygon", "coordinates": [[
        [-122.695, 48.335], [-122.685, 48.335], [-122.685, 48.345],
        [-122.695, 48.345], [-122.695, 48.335]]]}
    definition = _definition(footprint_buffer_m="300")
    definition[ea_las_tiles.LAS_FOOTPRINT_KEY] = footprint
    (provenance, _destination) = _fetch(tmp_path, definition)
    posted = json.loads(portal.calls[0][4]["geojson"])
    # A buffered polygon, not the box: more than four corners.
    assert len(posted["coordinates"][0]) > 5
    assert all(round(value, 4) == value
               for point in posted["coordinates"][0] for value in point)
    assert provenance["request_geometry"] == "core"
    assert provenance["core"]["provider"] == "AOITEST"
    assert provenance["core"]["boundary_polygon_wgs84"] == footprint
    assert provenance["core"]["tile_names"] == [os.path.basename(MEMBER)]


# ---------------------------------------------------------------------------
# the listing classes
# ---------------------------------------------------------------------------
def test_a_listing_without_the_dataset_is_a_durable_no_coverage(
        tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(dataset_id=999))
    _install(monkeypatch, portal)
    (provenance, _destination) = _fetch(tmp_path, _definition())
    assert provenance is None
    assert portal.verbs() == [("POST", QUERY)]


@pytest.mark.parametrize("portal_kwargs", [
    {"query_status": 503},
    {"query_status": 429},
    {"query_raises": requests.ConnectionError("Connection reset by peer")},
])
def test_a_broken_query_is_transient(tmp_path, monkeypatch, portal_kwargs):
    portal = _Portal(listing=_listing(), **portal_kwargs)
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.TransientFetchError):
        _fetch(tmp_path, _definition())


def test_a_non_json_listing_is_transient(tmp_path, monkeypatch):
    portal = _Portal(listing=None)
    portal.listing = None
    _install(monkeypatch, portal)

    def _html_post(self, *args, **kwargs):              # noqa: ARG001
        return _Response(200, text_body=True)

    session_factory = portal.session

    def _session():
        session = session_factory()
        session.post = _html_post.__get__(session)
        return session

    monkeypatch.setattr(requests, "Session", _session)
    with pytest.raises(ea_base.TransientFetchError):
        _fetch(tmp_path, _definition())


def test_a_5xx_download_is_transient_and_leaves_no_scratch(
        tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(), archive=b"", download_status=502)
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.TransientFetchError):
        _fetch(tmp_path, _definition())
    assert not [name for name in os.listdir(tmp_path)
                if name.startswith("KNUW_aoitest.tif.")]


def test_a_truncated_archive_is_transient(tmp_path, monkeypatch):
    archive = _tile_zip(tmp_path)
    portal = _Portal(listing=_listing(), archive=archive[: len(archive) // 2])
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.TransientFetchError):
        _fetch(tmp_path, _definition())


def test_no_member_matching_the_glob_is_unavailable(tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(),
                     archive=_tile_zip(tmp_path, member="hillshade/x.tif"))
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        _fetch(tmp_path, _definition())
    assert "member_glob" in caught.value.reason


# ---------------------------------------------------------------------------
# the cap: the portal's byte answer, judged BEFORE any download
# ---------------------------------------------------------------------------
def test_over_the_byte_cap_is_unavailable_before_any_download(
        tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(bytes_=304134301, files=42))
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        _fetch(tmp_path, _definition())
    reason = caught.value.reason
    assert "AOITEST: KNUW needs 42 files" in reason
    assert "max_bytes_per_airport in AOITEST.elv" in reason
    assert "SKIPPED, recorded unavailable, not no-coverage" in reason
    assert portal.verbs() == [("POST", QUERY)]


def test_the_default_cap_is_the_spec_default(tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(bytes_=300000001))
    _install(monkeypatch, portal)
    definition = _definition()
    definition.pop("max_bytes_per_airport")
    with pytest.raises(ea_base.ProviderUnavailable):
        _fetch(tmp_path, definition)
    assert ea_aoi_zip_download.AOI_ZIP_DEFAULT_MAX_BYTES_PER_AIRPORT == 300000000


def test_a_zip64_archive_is_unavailable_whatever_the_cap(
        tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(bytes_=9200000000, files=1))
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        _fetch(tmp_path, _definition(max_bytes_per_airport="20000000000"))
    assert "Zip64" in caught.value.reason
    assert portal.verbs() == [("POST", QUERY)]


# ---------------------------------------------------------------------------
# THE GATE (owner RULINGS 2026-09-30bn)
# ---------------------------------------------------------------------------
def _gated_definition():
    return _definition(gate_cookie_from="/", user_agent_profile="browser")


def _gate_page(expires_in=7200.0, cookies=None):
    if cookies is None:
        cookies = [_Cookie("dlgate", "ok", time.time() + expires_in)]
    return _Response(200, url="https://portal.test/", cookies=cookies)


def test_the_gate_is_opened_once_and_its_cookie_replayed(
        tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(), archive=_tile_zip(tmp_path),
                     gate=_gate_page(), require_cookie="dlgate")
    _install(monkeypatch, portal)
    (first, _destination) = _fetch(tmp_path, _gated_definition())
    assert first is not None
    assert portal.verbs() == [("GET", "https://portal.test/"),
                              ("POST", QUERY), ("GET", DOWNLOAD)]
    for (_verb, _url, headers, _cookies, _data) in portal.calls:
        assert headers["User-Agent"] == ea_aoi_zip_download.AOI_ZIP_BROWSER_USER_AGENT
    assert portal.calls[1][3] == {"dlgate": "ok"}
    assert first["gate"]["cookie_names"] == ["dlgate"]
    assert first["gate"]["cookie_reused"] is False
    assert first["user_agent_profile"] == "browser"
    # A second airport in the same process: NO second gate GET.
    portal.calls.clear()
    (second, _destination) = _fetch(tmp_path, _gated_definition())
    assert portal.verbs() == [("POST", QUERY), ("GET", DOWNLOAD)]
    assert second["gate"]["cookie_reused"] is True


def test_an_expired_gate_cookie_is_asked_for_again(tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(), archive=_tile_zip(tmp_path),
                     gate=_gate_page(expires_in=-1.0),
                     require_cookie="dlgate")
    _install(monkeypatch, portal)
    _fetch(tmp_path, _gated_definition())
    portal.calls.clear()
    _fetch(tmp_path, _gated_definition())
    assert portal.verbs()[0] == ("GET", "https://portal.test/")


def test_a_403_without_the_cookie_is_unavailable_gate_after_one_request(
        tmp_path, monkeypatch):
    # No gate declared: the portal refuses the bare query -- ONE request,
    # unavailable with the reason 'gate', never a retry loop.
    portal = _Portal(listing=_listing(), require_cookie="dlgate")
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        _fetch(tmp_path, _definition())
    assert caught.value.reason.startswith("AOITEST: gate - ")
    assert "HTTP 403" in caught.value.reason
    assert "never worked around" in caught.value.reason
    assert portal.verbs() == [("POST", QUERY)]


def test_a_403_after_the_gate_forgets_the_cookie(tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(), gate=_gate_page(),
                     query_status=403)
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        _fetch(tmp_path, _gated_definition())
    assert "gate" in caught.value.reason
    assert portal.verbs() == [("GET", "https://portal.test/"),
                              ("POST", QUERY)]
    assert ea_aoi_zip_download._aoi_gate_cookie_cache == {}


@pytest.mark.parametrize("gate_page", [
    _Response(200, url="https://portal.test/", cookies=[]),
    _Response(200, url="https://portal.test/login?next=/", cookies=[
        _Cookie("dlgate", "ok", None)]),
    _Response(401, url="https://portal.test/"),
    _Response(404, url="https://portal.test/"),
])
def test_a_gate_that_does_not_open_like_a_browser_is_unavailable(
        tmp_path, monkeypatch, gate_page):
    portal = _Portal(listing=_listing(), gate=gate_page)
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        _fetch(tmp_path, _gated_definition())
    assert caught.value.reason.startswith("AOITEST: gate - ")
    assert portal.verbs() == [("GET", "https://portal.test/")]


def test_a_5xx_gate_page_is_transient(tmp_path, monkeypatch):
    portal = _Portal(listing=_listing(),
                     gate=_Response(503, url="https://portal.test/"))
    _install(monkeypatch, portal)
    with pytest.raises(ea_base.TransientFetchError):
        _fetch(tmp_path, _gated_definition())


def test_an_unknown_user_agent_profile_is_unavailable(tmp_path, monkeypatch):
    _install(monkeypatch, _Portal(listing=_listing()))
    with pytest.raises(ea_base.ProviderUnavailable):
        _fetch(tmp_path, _definition(user_agent_profile="curl"))


# ---------------------------------------------------------------------------
# the three .elv files
# ---------------------------------------------------------------------------
AIRPORTS = {
    "AKHOMER": (59.6456, -151.4766),           # PAHO
    "AKHAINES": (59.2438, -135.5235),          # PAHN
    "WADNR": (48.3452, -122.6629),             # KNUW (and KNRA below)
}
CONTROLS = {
    "HECA": (30.1219, 31.4056), "KCLT": (35.2140, -80.9431),
    "SPJC": (-12.0219, -77.1143), "CYXY": (60.7096, -135.0674),
    "KASE": (39.2232, -106.8688),
}


def test_the_three_provider_files():
    providers = INSETS.initialize_elevation_providers_dict()
    for (code, (lat, lon)) in AIRPORTS.items():
        definition = providers[code]
        assert definition["access_strategy"] == "aoi_zip_download"
        assert definition["enabled"] is True
        assert ea_definitions._parse_boolean(definition["ladder_member"]) is True
        assert definition["priority"] == 90.0
        assert definition.get("license") and definition.get("attribution")
        assert definition.get("license_note")
        assert ea_definitions._coverage_bbox_intersects(
            definition, (lon, lat, lon, lat))
        for (clat, clon) in CONTROLS.values():
            assert not ea_definitions._coverage_bbox_intersects(
                definition, (clon - 0.1, clat - 0.1, clon + 0.1, clat + 0.1))
    wadnr = providers["WADNR"]
    assert wadnr["gate_cookie_from"] == "/"
    assert wadnr["user_agent_profile"] == "browser"
    assert wadnr["vertical_unit"] == "ftUS"
    assert "2026-09-30bn" in wadnr["license_note"]
    assert "honor the gate like a browser" in wadnr["license_note"]
    assert ea_definitions._coverage_bbox_intersects(
        wadnr, (-122.6316, 48.1878, -122.6316, 48.1878))          # KNRA
    for code in ("AKHOMER", "AKHAINES"):
        assert "gate_cookie_from" not in providers[code]
        assert providers[code]["user_agent_profile"] == "engine"
        assert providers[code]["vertical_unit"] == "m"
