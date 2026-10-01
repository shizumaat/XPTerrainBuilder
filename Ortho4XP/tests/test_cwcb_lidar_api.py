"""#154 lane cwcb154 -- the ``cwcb_lidar_api`` strategy (CWCB1M, KHDN /
KCAG).

Spec ``docs/specs/us-holder-providers-spec.md`` §3.5 / §4, RULINGS
2026-09-30bm.  A synthetic CWCB server (``requests`` faked): ``POST tiles``
answers keys over EVERY dataset, ``POST tileSummaries`` the per-dataset
listing, ``GET files/{tileKey}/{formatKey}`` a deflated zip holding one
ERDAS IMAGINE ``.img`` (Float32, 3 ft cells, NAD83(2011) Colorado North
ftUS, a plane in US survey FEET with a -9999 hole).  Proves: the dataset
filter, the footprint selection, the listing memo (cached / stale /
contradicted), the transient-vs-durable classes, the cap wording BEFORE
any byte moves, the LAS member refusal, and the fetch -> metres within
1 mm with ``vertical_unit_applied=m``, scratch removed.  No network.
"""

import io
import json
import os
import time
import zipfile

import numpy
import pytest

import O4_File_Names as FNAMES
import O4_Airport_Elevation_Insets as INSETS

gdal = pytest.importorskip("osgeo.gdal")
from osgeo import osr  # noqa: E402

FTUS = 1200.0 / 3937.0
CELL_FT = 3.0
SIZE = 40                                 # 40 x 40 cells of 3 ft
X0 = 2518000.0                            # KHDN's LD25181418 corner
Y0 = 1421000.0
DATASET = "d-routt"
OTHER = "d-other"
FORMAT = "f-img"
TILES = {                                  # key -> (tile id, column offset)
    "k1": ("LDT1", 0),
    "k2": ("LDT2", SIZE),
}


def _plane_ft(x, y):
    return 6500.0 + 0.01 * (x - X0) + 0.02 * (Y0 - y)


def _to_wgs84():
    source = osr.SpatialReference()
    source.ImportFromEPSG(6430)
    target = osr.SpatialReference()
    target.ImportFromEPSG(4326)
    for srs in (source, target):
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return osr.CoordinateTransformation(source, target)


def _tile_corners_ft(column_offset):
    west = X0 + column_offset * CELL_FT
    return (west, Y0 - SIZE * CELL_FT, west + SIZE * CELL_FT, Y0)


def _tile_wkt(column_offset):
    transform = _to_wgs84()
    (west, south, east, north) = _tile_corners_ft(column_offset)
    ring = [transform.TransformPoint(x, y)[:2] for (x, y) in (
        (west, south), (east, south), (east, north), (west, north),
        (west, south))]
    return "POLYGON ((%s))" % ", ".join("%.9f %.9f" % p for p in ring)


def _box_inside(column_offsets, inset_ft=15.0):
    transform = _to_wgs84()
    xs, ys = [], []
    for offset in column_offsets:
        (west, south, east, north) = _tile_corners_ft(offset)
        for (x, y) in ((west + inset_ft, south + inset_ft),
                       (east - inset_ft, north - inset_ft)):
            (lon, lat) = transform.TransformPoint(x, y)[:2]
            xs.append(lon)
            ys.append(lat)
    return (min(xs), min(ys), max(xs), max(ys))


def _img_zip_bytes(tile_id, column_offset, hole=True):
    """A deflated zip holding ``<tile_id>.img`` (HFA) of the ftUS plane."""
    scratch = "/vsimem/%s.img" % tile_id
    driver = gdal.GetDriverByName("HFA")
    dataset = driver.Create(scratch, SIZE, SIZE, 1, gdal.GDT_Float32)
    west = X0 + column_offset * CELL_FT
    dataset.SetGeoTransform((west, CELL_FT, 0.0, Y0, 0.0, -CELL_FT))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(6430)
    dataset.SetProjection(srs.ExportToWkt())
    cols, rows = numpy.meshgrid(numpy.arange(SIZE), numpy.arange(SIZE))
    values = _plane_ft(west + (cols + 0.5) * CELL_FT,
                       Y0 - (rows + 0.5) * CELL_FT).astype(numpy.float32)
    if hole:
        values[5:9, 5:9] = -9999.0
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-9999.0)
    band.WriteArray(values)
    dataset = None
    members = {}
    for name in gdal.ReadDir("/vsimem/") or []:
        if name.startswith(tile_id):
            path = "/vsimem/" + name
            handle = gdal.VSIFOpenL(path, "rb")
            gdal.VSIFSeekL(handle, 0, 2)
            size = gdal.VSIFTellL(handle)
            gdal.VSIFSeekL(handle, 0, 0)
            members[name] = bytes(gdal.VSIFReadL(1, size, handle))
            gdal.VSIFCloseL(handle)
            gdal.Unlink(path)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for (name, data) in members.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def _definition(**overrides):
    definition = {
        "code": "CWCBTEST",
        "access_strategy": "cwcb_lidar_api",
        "role": INSETS.ROLE_AIRPORT_INSET,
        "enabled": True,
        "tiles_url": "https://cwcb.test/api/lidar/tiles",
        "summaries_url": "https://cwcb.test/api/lidar/tileSummaries",
        "file_url_template": "https://cwcb.test/api/lidar/files/{tileKey}/"
                             "{formatKey}",
        "dataset_ids": DATASET,
        "format_key": FORMAT,
        "member_suffix": ".img",
        "source_srs": "EPSG:6430",
        "source_nodata": "-9999",
        "vertical_unit": "ftUS",
        "vertical_datum": "NAVD88",
        "native_resolution_m": 0.9144,
        "max_tiles_per_airport": "24",
        "max_bytes_per_airport": "120000000",
        "license": "test licence",
        "license_note": "test note",
        "attribution": "test attribution",
    }
    definition.update(overrides)
    return definition


class _Response:
    def __init__(self, status=200, payload=None, body=b"", headers=None):
        self.status_code = status
        self._payload = payload
        self._body = body
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def iter_content(self, size):
        for start in range(0, len(self._body), size):
            yield self._body[start:start + size]

    def close(self):
        pass


@pytest.fixture
def server(monkeypatch, tmp_path):
    """The synthetic CWCB API.  ``state["tiles"]`` is the ``POST tiles``
    answer; ``state["summaries"]`` the per-dataset listing; ``state
    ["files"]`` the zips by tile key (absent = 404)."""
    import requests

    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    state = {
        "tiles": {"datasets": [DATASET, OTHER],
                  "tiles": ["k1", "k2", "k-other"]},
        "summaries": {DATASET: {
            key: {"geography": {"geography": {
                      "coordinateSystemId": 4326,
                      "wellKnownText": _tile_wkt(offset)}},
                  "model": {"tileId": tile_id, "dataset": DATASET,
                            "fileSummaries": [
                                {"format": FORMAT, "fileSizeTotal": 7000},
                                {"format": "f-las",
                                 "fileSizeTotal": 9000000}]}}
            for (key, (tile_id, offset)) in TILES.items()}},
        "files": {key: _img_zip_bytes(tile_id, offset)
                  for (key, (tile_id, offset)) in TILES.items()},
        "calls": [],
    }

    def _post(url, data=None, **kwargs):
        body = json.loads(data)
        state["calls"].append(("POST", url, body))
        answer = (state["tiles"] if url.endswith("/tiles")
                  else state["summaries"])
        if isinstance(answer, _Response):
            return answer
        return _Response(200, answer)

    def _get(url, **kwargs):
        state["calls"].append(("GET", url, dict(kwargs.get("headers")
                                                or {})))
        override = state.get("file_response")
        if override is not None:
            return override
        key = url.split("/files/", 1)[1].split("/", 1)[0]
        body = state["files"].get(key)
        if body is None:
            return _Response(404)
        return _Response(200, body=body, headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/octet-stream"})

    monkeypatch.setattr(requests, "post", _post)
    monkeypatch.setattr(requests, "get", _get)
    return state


def _posts(state, suffix):
    return [call for call in state["calls"]
            if call[0] == "POST" and call[1].endswith(suffix)]


# ---------------------------------------------------------------------
# the shipped definition
# ---------------------------------------------------------------------
def test_shipped_cwcb1m_definition():
    providers = INSETS.initialize_elevation_providers_dict()
    definition = providers["CWCB1M"]
    assert definition["access_strategy"] == "cwcb_lidar_api"
    assert definition["dataset_ids"] == "4e85e347-5533-4c2f-bf9e-522a9fd81bec"
    assert definition["format_key"] == "30993bf7-abc8-4339-978a-5e61cd692768"
    assert definition["member_suffix"] == ".img"
    assert definition["source_srs"] == "EPSG:6430"
    assert definition["vertical_unit"] == "ftUS"
    assert definition["native_resolution_m"] == pytest.approx(0.9144)
    assert int(definition["max_tiles_per_airport"]) == 24
    assert int(definition["max_bytes_per_airport"]) == 120000000
    assert INSETS._parse_boolean(definition["ladder_member"]) is True
    assert definition["priority"] == 90.0
    assert definition["enabled"] is True
    assert "2026-09-30aw" in definition["license_note"]
    assert "Merrick" in definition["attribution"]
    # KHDN (Yampa Valley) and KCAG (Craig) inside the box; KASE outside.
    for (lon, lat) in ((-107.2177, 40.4812), (-107.5217, 40.4952)):
        assert INSETS._coverage_bbox_intersects(
            definition, (lon - 0.01, lat - 0.01, lon + 0.01, lat + 0.01))
    assert not INSETS._coverage_bbox_intersects(
        definition, (-106.88, 39.21, -106.86, 39.23))
    assert INSETS.provider_required_capabilities(definition) == []


# ---------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------
def test_discovery_filters_to_the_dataset_and_memoises_the_listing(server):
    strategy = INSETS.CwcbLidarApiStrategy()
    sources = strategy.discover(_definition(), _box_inside([0, SIZE]))
    assert [source["source_id"] for source in sources] == ["LDT1", "LDT2"]
    assert all(source["dataset"] == DATASET for source in sources)
    assert sources[0]["download_url"] == (
        "https://cwcb.test/api/lidar/files/k1/" + FORMAT)
    assert sources[0]["bytes"] == 7000
    # The request polygon went as a JSON STRING of WKT, counter-clockwise.
    (_post, _url, body) = _posts(server, "/tiles")[0]
    assert isinstance(body, str) and body.startswith("POLYGON")
    assert _posts(server, "/tileSummaries")[0][2] == [DATASET]
    cache = INSETS.cwcb_summaries_cache_path("CWCBTEST", DATASET)
    assert os.path.isfile(cache)
    # A second discovery reads the memo: no second listing POST.
    strategy.discover(_definition(), _box_inside([0, SIZE]))
    assert len(_posts(server, "/tileSummaries")) == 1


def test_stale_or_contradicted_listing_is_relisted(server):
    strategy = INSETS.CwcbLidarApiStrategy()
    strategy.discover(_definition(), _box_inside([0]))
    cache = INSETS.cwcb_summaries_cache_path("CWCBTEST", DATASET)
    # STALE by age: re-listed; an unchanged listing is not rewritten.
    old = time.time() - 40 * 86400
    os.utime(cache, (old, old))
    strategy.discover(_definition(), _box_inside([0]))
    assert len(_posts(server, "/tileSummaries")) == 2
    assert os.path.getmtime(cache) == pytest.approx(old, abs=1)
    # CONTRADICTED: the server names the dataset over the box, the memo
    # holds none of its keys -> re-listed at once, whatever its age.
    with open(cache, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"k-gone": {"tile_id": "X", "wkt": _tile_wkt(0),
                              "bytes": {FORMAT: 1}}}, handle)
    sources = strategy.discover(_definition(), _box_inside([0]))
    assert len(_posts(server, "/tileSummaries")) == 3
    assert [source["source_id"] for source in sources] == ["LDT1"]


def test_footprint_selects_tiles_meeting_the_polygon(server):
    """The SURGICAL rule (§2 LAS rule): a tile whose footprint misses the
    buffered aerodrome polygon is not fetched, even inside the box."""
    from shapely.geometry import box as _box

    definition = _definition()
    definition[INSETS.LAS_FOOTPRINT_KEY] = INSETS._polygon_mapping(
        _box(*_box_inside([0], inset_ft=30.0)))
    sources = INSETS.CwcbLidarApiStrategy().discover(
        definition, _box_inside([0, SIZE]))
    assert [source["source_id"] for source in sources] == ["LDT1"]


def test_well_formed_empty_answer_is_durable_no_coverage(server):
    server["tiles"] = {"datasets": [OTHER], "tiles": ["k-other"]}
    assert INSETS.CwcbLidarApiStrategy().discover(
        _definition(), _box_inside([0])) is None
    server["tiles"] = {"datasets": [], "tiles": []}
    assert INSETS.CwcbLidarApiStrategy().discover(
        _definition(), _box_inside([0])) is None


@pytest.mark.parametrize("answer", [
    _Response(503),
    _Response(429),
    _Response(200, None),                                    # non-JSON
    _Response(200, {"error": "boom"}),
    _Response(200, {"message": "An error has occurred.",
                    "exceptionMessage": "24114: bad WKT"}),
    _Response(200, {"datasets": [DATASET]}),                 # no listing
    _Response(200, {"tiles": ["k1"]}),                       # no datasets
])
def test_degraded_tiles_answer_is_transient(server, answer):
    server["tiles"] = answer
    with pytest.raises(INSETS.TransientFetchError):
        INSETS.CwcbLidarApiStrategy().discover(_definition(),
                                               _box_inside([0]))


def test_degraded_listing_is_transient(server):
    server["summaries"] = {"something": {}}
    with pytest.raises(INSETS.TransientFetchError):
        INSETS.CwcbLidarApiStrategy().discover(_definition(),
                                               _box_inside([0]))


def test_out_of_coverage_makes_no_call(server):
    definition = _definition(coverage_bbox=(0.0, 0.0, 1.0, 1.0))
    assert INSETS.CwcbLidarApiStrategy().discover(
        definition, _box_inside([0])) is None
    assert server["calls"] == []


# ---------------------------------------------------------------------
# refusals
# ---------------------------------------------------------------------
def test_las_member_is_refused_with_the_reason(server, tmp_path):
    with pytest.raises(INSETS.ProviderUnavailable) as caught:
        INSETS.CwcbLidarApiStrategy().fetch(
            _definition(member_suffix=".las"), _box_inside([0]), 1.0,
            str(tmp_path / "KHDN_x.tif"))
    assert "member_suffix=.las" in caught.value.reason
    assert "lasidx154" in caught.value.reason
    assert server["calls"] == []


def test_cap_wording_is_exact_and_no_byte_moves(server, tmp_path):
    with pytest.raises(INSETS.ProviderUnavailable) as caught:
        INSETS.CwcbLidarApiStrategy().fetch(
            _definition(max_tiles_per_airport="1"), _box_inside([0, SIZE]),
            1.0, str(tmp_path / "KHDN_cwcbtest.tif"))
    assert caught.value.reason == (
        "CWCBTEST: KHDN needs 2 tiles / 0 MB, cap 1 / 120 MB "
        "(max_tiles_per_airport / max_bytes_per_airport in CWCBTEST.elv) "
        "— SKIPPED, recorded unavailable, not no-coverage")
    with pytest.raises(INSETS.ProviderUnavailable) as caught:
        INSETS.CwcbLidarApiStrategy().fetch(
            _definition(max_bytes_per_airport="10000"),
            _box_inside([0, SIZE]), 1.0, str(tmp_path / "KHDN_cwcbtest.tif"))
    assert "needs 2 tiles" in caught.value.reason
    assert not [call for call in server["calls"] if call[0] == "GET"]


# ---------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------
def test_fetch_converts_feet_to_metres_and_records(server, tmp_path,
                                                   monkeypatch):
    monkeypatch.setattr(INSETS, "LAS_PROGRESS_INTERVAL_S", 0.0)
    lines = []
    monkeypatch.setattr(INSETS.UI, "vprint",
                        lambda level, *parts: lines.append(" ".join(
                            str(p) for p in parts)))
    from shapely.geometry import box as _box

    definition = _definition()
    definition[INSETS.LAS_FOOTPRINT_KEY] = INSETS._polygon_mapping(
        _box(*_box_inside([0, SIZE], inset_ft=20.0)))
    destination = str(tmp_path / "out" / "KHDN_cwcbtest.tif")
    provenance = INSETS.fetch_inset(definition, _box_inside([0, SIZE]),
                                    1.0, destination)
    assert provenance["provider"] == "CWCBTEST"
    assert provenance["source_ids"] == ["LDT1", "LDT2"]
    assert provenance["tiles_missing"] == []
    assert provenance["vertical_unit_source"] == "elv"
    assert provenance["vertical_unit_applied"] == "m"
    assert provenance["bytes_fetched"] > 0
    assert provenance["core"]["tile_names"] == ["LDT1", "LDT2"]
    # Scratch (zips, VRT) removed: only the inset is left.
    assert sorted(os.listdir(tmp_path / "out")) == ["KHDN_cwcbtest.tif"]
    # Every valid cell is the plane in METRES (bilinear of a plane is the
    # plane), the hole stays nodata.
    dataset = gdal.Open(destination)
    (x0, dx, _a, y0, _b, dy) = dataset.GetGeoTransform()
    values = dataset.ReadAsArray().astype(numpy.float64)
    rows, cols = numpy.mgrid[0:values.shape[0], 0:values.shape[1]]
    lon = x0 + (cols + 0.5) * dx
    lat = y0 + (rows + 0.5) * dy
    target = osr.SpatialReference()
    target.ImportFromEPSG(6430)
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    for srs in (source, target):
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source, target)
    valid = (values != -32768.0) & numpy.isfinite(values)
    assert valid.mean() > 0.8
    assert (~valid).any()                      # the -9999 hole survived
    errors = []
    for (r, c) in zip(rows[valid][::7], cols[valid][::7]):
        (x, y) = transform.TransformPoint(float(lon[r, c]),
                                          float(lat[r, c]))[:2]
        errors.append(abs(values[r, c] - _plane_ft(x, y) * FTUS))
    # Interior cells away from the hole's bilinear rim: within 5 mm (Float32
    # at ~2,000 m plus the LCC -> EPSG:4326 resample); a feet raster baked
    # as metres would be ~4,000 m off.
    assert numpy.percentile(errors, 90) < 5e-3
    assert any("[inset] KHDN CWCBTEST tile 2/2 LDT2" in line
               and " done (" in line for line in lines)


def test_missing_tiles_are_recorded_and_all_missing_is_unavailable(
        server, tmp_path):
    del server["files"]["k2"]
    provenance = INSETS.CwcbLidarApiStrategy().fetch(
        _definition(), _box_inside([0, SIZE]), 1.0,
        str(tmp_path / "KHDN_cwcbtest.tif"))
    assert provenance["tiles_missing"] == ["LDT2"]
    server["files"].clear()
    with pytest.raises(INSETS.ProviderUnavailable) as caught:
        INSETS.CwcbLidarApiStrategy().fetch(
            _definition(), _box_inside([0, SIZE]), 1.0,
            str(tmp_path / "KHDN_cwcbtest2.tif"))
    assert "server has none" in caught.value.reason


@pytest.mark.parametrize("response, expected", [
    (_Response(503), INSETS.TransientFetchError),
    (_Response(429), INSETS.TransientFetchError),
    (_Response(403), INSETS.ProviderUnavailable),
    (_Response(200, body=b'{"error": "x"}',
               headers={"Content-Type": "application/json"}),
     INSETS.TransientFetchError),
    (_Response(200, body=b"PK\x03\x04truncated",
               headers={"Content-Type": "application/octet-stream"}),
     INSETS.TransientFetchError),
])
def test_tile_download_classes(server, tmp_path, response, expected):
    server["file_response"] = response
    with pytest.raises(expected):
        INSETS.CwcbLidarApiStrategy().fetch(
            _definition(), _box_inside([0]), 1.0,
            str(tmp_path / "KHDN_cwcbtest.tif"))
    # No scratch survives a failed fetch.
    assert [name for name in os.listdir(tmp_path)
            if name.startswith("KHDN_")] == []


def test_died_transfer_is_regot_whole_once(server, tmp_path):
    """No Range support: a transfer that died is re-GET from byte 0."""
    good = server["files"]["k1"]
    answers = [_Response(200, body=good[:100], headers={
                   "Content-Length": str(len(good)),
                   "Content-Type": "application/octet-stream"}),
               _Response(200, body=good, headers={
                   "Content-Length": str(len(good)),
                   "Content-Type": "application/octet-stream"})]
    import requests

    calls = []

    def _get(url, **kwargs):
        calls.append(dict(kwargs.get("headers") or {}))
        return answers.pop(0)

    original = requests.get
    requests.get = _get
    try:
        provenance = INSETS.CwcbLidarApiStrategy().fetch(
            _definition(), _box_inside([0]), 1.0,
            str(tmp_path / "KHDN_cwcbtest.tif"))
    finally:
        requests.get = original
    assert provenance["source_ids"] == ["LDT1"]
    assert calls == [{}, {}]                    # never a Range header
