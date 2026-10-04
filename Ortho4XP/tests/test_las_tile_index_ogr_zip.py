"""#154 lane lasidx154 -- ``las_tile_index`` extensions (spec
``docs/specs/us-holder-providers-spec.md`` §3.3):

* ``index_format=ogr``: a GeoPackage tile index (NOAA Digital Coast's
  ``tileindex_*.gpkg``) opened over ``/vsicurl/`` with RANGE reads, cut to
  the surgical footprint exactly as the ArcGIS branch; ``index_url_field``
  / ``index_name_field`` keys;
* ``index_format=cwcb`` + ``archive_member=las``: the CWCB lidar API's
  zipped LAS tiles -- the zip comes whole into the ``las_tiles`` cache,
  its one member is extracted and the zip is deleted;
* LAZ through #153's ``CAPABILITY_LAZ`` door; caps judged before any
  byte moves.

No network: a loopback HTTP server (Range-aware) serves the index,
``requests`` is faked for tiles and the CWCB API.
"""

import http.server
import io
import os
import threading
import zipfile

import pytest

import O4_File_Names as FNAMES
import O4_Airport_Elevation_Insets as INSETS
from tests.inset_code import patch_inset_code
from elevation_access import base as ea_base
from elevation_access import capabilities as ea_capabilities
from elevation_access import definitions as ea_definitions
from elevation_access import las_tiles as ea_las_tiles
from elevation_access.strategies import las_tile_index as ea_las_tile_index

laspy = pytest.importorskip("laspy")
gdal = pytest.importorskip("osgeo.gdal")
from osgeo import ogr, osr  # noqa: E402

import test_las_tile_index as LTI  # noqa: E402  (the synthetic tile)


# ---------------------------------------------------------------------
# a synthetic tile index (EPSG 6428, ftUS -- a PROJECTED index, so the
# footprint test runs through the layer's own CRS)
# ---------------------------------------------------------------------
def _tile_square_ft(column, row, size_cells=LTI.N_CELLS):
    west = (LTI.I0 + column * size_cells) * LTI.CELL_FT
    south = (LTI.J0 + row * size_cells) * LTI.CELL_FT
    east = west + size_cells * LTI.CELL_FT
    north = south + size_cells * LTI.CELL_FT
    return (west, south, east, north)


def _write_index(path, tiles, url_field="url", name_field="filename",
                 padding=0, padding_tiles=0):
    """A GeoPackage of tile footprints, ``tiles = [(name, url, square)]``;
    ``padding_tiles`` far-away features pad the file (so a range read is
    measurably smaller than the whole)."""
    driver = ogr.GetDriverByName("GPKG")
    if os.path.exists(str(path)):
        driver.DeleteDataSource(str(path))
    dataset = driver.CreateDataSource(str(path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(6428)
    layer = dataset.CreateLayer("tileindex", srs, ogr.wkbPolygon)
    for field in (name_field, "srs", url_field):
        layer.CreateField(ogr.FieldDefn(field, ogr.OFTString))
    rows = list(tiles)
    for number in range(padding_tiles):
        square = _tile_square_ft(200 + number % 100, 200 + number // 100)
        rows.append(("PAD_%05d.copc.laz" % number,
                     "https://tiles.test/PAD_%05d.copc.laz" % number,
                     square))
    for (name, url, (west, south, east, north)) in rows:
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetField(name_field, name)
        feature.SetField("srs", "EPSG:6428")
        feature.SetField(url_field, url)
        feature.SetGeometry(ogr.CreateGeometryFromWkt(
            "POLYGON ((%r %r, %r %r, %r %r, %r %r, %r %r))" % (
                west, south, east, south, east, north, west, north, west,
                south)))
        layer.CreateFeature(feature)
        feature = None
    layer = None
    dataset = None
    return str(path)


def _to_wgs84_box(square):
    source = osr.SpatialReference()
    source.ImportFromEPSG(6428)
    target = osr.SpatialReference()
    target.ImportFromEPSG(4326)
    for srs in (source, target):
        srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(source, target)
    (west, south, east, north) = square
    corners = [transform.TransformPoint(x, y)[:2]
               for x in (west, east) for y in (south, north)]
    return (min(c[0] for c in corners), min(c[1] for c in corners),
            max(c[0] for c in corners), max(c[1] for c in corners))


def _ogr_definition(index_url, **overrides):
    definition = LTI._definition(
        code="OGRTEST",
        index_format="ogr",
        index_url=index_url,
        index_url_field="url",
        index_name_field="filename",
    )
    definition.pop("index_url_template", None)
    definition.pop("tile_url_template", None)
    definition.update(overrides)
    return definition


def _core_mapping(box):
    from shapely.geometry import box as shapely_box

    return INSETS._polygon_mapping(shapely_box(*box))


# ---------------------------------------------------------------------
# index_format=ogr
# ---------------------------------------------------------------------
def test_ogr_index_is_cut_to_the_footprint_with_its_field_keys(tmp_path):
    inside = _tile_square_ft(0, 0)
    beside = _tile_square_ft(1, 0)       # in the query box, off the core
    far = _tile_square_ft(40, 40)
    index = _write_index(tmp_path / "idx.gpkg", [
        ("T1.copc.laz", "https://tiles.test/T1.copc.laz", inside),
        ("T2.copc.laz", "https://tiles.test/T2.copc.laz", beside),
        ("FAR.copc.laz", "https://tiles.test/FAR.copc.laz", far),
    ], url_field="href", name_field="tile")
    tile_box = _to_wgs84_box(inside)
    # the core: a small polygon well inside T1 (shrunk 20 %)
    (w, s, e, n) = tile_box
    dx, dy = (e - w) * 0.2, (n - s) * 0.2
    core_box = (w + dx, s + dy, e - dx, n - dy)
    definition = _ogr_definition(
        index, index_url_field="href", index_name_field="tile",
        **{ea_las_tiles.LAS_FOOTPRINT_KEY: _core_mapping(core_box)})
    strategy = ea_las_tile_index.LasTileIndexStrategy()
    # the request box spans T1 and T2 -- only the footprint decides
    request_box = (w, s, _to_wgs84_box(beside)[2], n)
    listing = strategy.discover(definition, request_box)
    assert [source["source_id"] for source in listing] == ["T1.copc"]
    assert listing[0]["download_url"] == "https://tiles.test/T1.copc.laz"
    assert listing[0]["title"] == "T1.copc.laz"
    assert strategy.last_listing == listing
    # without a footprint the whole request box is listed (T1 + T2)
    plain = _ogr_definition(index, index_url_field="href",
                            index_name_field="tile")
    names = [source["source_id"] for source in
             strategy.discover(plain, request_box)]
    assert names == ["T1.copc", "T2.copc"]
    # the default keys are url / filename: absent here -> transient
    with pytest.raises(ea_base.TransientFetchError,
                       match="no 'url'/'filename' attribute"):
        strategy.discover(_ogr_definition(index), request_box)


def test_ogr_index_empty_is_durable_unreadable_is_transient(tmp_path):
    index = _write_index(tmp_path / "idx.gpkg", [
        ("FAR.copc.laz", "https://tiles.test/FAR.copc.laz",
         _tile_square_ft(40, 40))])
    box = _to_wgs84_box(_tile_square_ft(0, 0))
    strategy = ea_las_tile_index.LasTileIndexStrategy()
    assert strategy.discover(_ogr_definition(index), box) is None
    with open(tmp_path / "junk.gpkg", "wb") as handle:
        handle.write(b"not a geopackage")
    with pytest.raises(ea_base.TransientFetchError):
        strategy.discover(_ogr_definition(str(tmp_path / "junk.gpkg")),
                          box)
    with pytest.raises(ea_base.ProviderUnavailable, match="needs index_url"):
        strategy.discover(_ogr_definition(""), box)


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    """Serves one file with HEAD and single-range GET; counts bytes."""

    payload = b""
    served = [0]
    requests_seen = []

    def log_message(self, *args):
        pass

    def _missing(self):
        """Only the index path exists (an ``.aux.xml`` probe is a 404,
        as on S3)."""
        if self.path.endswith(".gpkg"):
            return False
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def do_HEAD(self):
        if self._missing():
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.payload)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()

    def do_GET(self):
        if self._missing():
            return
        header = self.headers.get("Range")
        self.requests_seen.append(header)
        body = self.payload
        if header and header.startswith("bytes="):
            (start, _dash, end) = header[6:].partition("-")
            start = int(start)
            end = min(int(end) if end else len(body) - 1, len(body) - 1)
            chunk = body[start:end + 1]
            self.send_response(206)
            self.send_header("Content-Range", "bytes %d-%d/%d"
                             % (start, end, len(body)))
            self.send_header("Content-Length", str(len(chunk)))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            self.wfile.write(chunk)
            self.served[0] += len(chunk)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.served[0] += len(body)


@pytest.fixture
def range_server(tmp_path):
    handler = type("Handler", (_RangeHandler,),
                   {"served": [0], "requests_seen": []})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, handler
    server.shutdown()
    server.server_close()


def test_remote_gpkg_is_read_by_ranges_not_whole(tmp_path, range_server):
    (server, handler) = range_server
    inside = _tile_square_ft(0, 0)
    index = _write_index(tmp_path / "big.gpkg", [
        ("T1.copc.laz", "https://tiles.test/T1.copc.laz", inside)],
        padding_tiles=20000)
    with open(index, "rb") as handle:
        handler.payload = handle.read()
    url = "http://127.0.0.1:%d/idx_%s.gpkg" % (server.server_address[1],
                                              os.getpid())
    gdal.VSICurlClearCache()
    listing = ea_las_tile_index.LasTileIndexStrategy().discover(
        _ogr_definition(url), _to_wgs84_box(inside))
    assert [source["source_id"] for source in listing] == ["T1.copc"]
    whole = len(handler.payload)
    assert whole > 2_000_000
    assert handler.served[0] < whole / 4, (handler.served[0], whole)
    assert all(header for header in handler.requests_seen)   # ranges only


# ---------------------------------------------------------------------
# LAZ door + caps before any byte moves (ogr index)
# ---------------------------------------------------------------------
def test_laz_without_the_backend_is_unavailable_before_any_read(
        tmp_path, monkeypatch):
    patch_inset_code(monkeypatch, "laz_reader_available", lambda: False)
    calls = []
    monkeypatch.setattr(ea_las_tile_index.LasTileIndexStrategy, "discover",
                        lambda *args: calls.append(args))
    definition = _ogr_definition(str(tmp_path / "none.gpkg"),
                                 point_compression="laz")
    with pytest.raises(ea_base.ProviderUnavailable,
                       match=r"LAZ backend \(lazrs\) missing"):
        ea_las_tile_index.LasTileIndexStrategy().fetch(
            definition, _to_wgs84_box(_tile_square_ft(0, 0)), 1.0,
            str(tmp_path / "PAVD_x.tif"))
    assert calls == []
    assert INSETS.provider_required_capabilities(definition) == [
        ea_capabilities.CAPABILITY_LAS, ea_capabilities.CAPABILITY_LAZ]


def test_ogr_caps_are_judged_before_any_tile_get(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    squares = [_tile_square_ft(c, 0) for c in range(3)]
    index = _write_index(tmp_path / "idx.gpkg", [
        ("T%d.las" % n, "https://tiles.test/T%d.las" % n, square)
        for (n, square) in enumerate(squares)])
    calls = []

    def _head(url, **kwargs):
        calls.append(("HEAD", url))
        return LTI._Response(200, headers={"Content-Length": "600000000"})

    def _get(url, **kwargs):
        calls.append(("GET", url))
        return LTI._Response(404)

    monkeypatch.setattr(requests, "head", _head)
    monkeypatch.setattr(requests, "get", _get)
    box = (_to_wgs84_box(squares[0])[0], _to_wgs84_box(squares[0])[1],
           _to_wgs84_box(squares[2])[2], _to_wgs84_box(squares[2])[3])
    with pytest.raises(ea_base.ProviderUnavailable) as caught:
        ea_las_tile_index.LasTileIndexStrategy().fetch(
            _ogr_definition(index, max_tiles_per_airport="16",
                            max_bytes_per_airport="1500000000"),
            box, 1.0, str(tmp_path / "PAVD_noaavaldezlaz.tif"))
    assert "needs 3 tiles / 1.8 GB, cap 16 / 1.5 GB" in caught.value.reason
    assert "not no-coverage" in caught.value.reason
    assert [c for c in calls if c[0] == "GET"] == []


# ---------------------------------------------------------------------
# index_format=cwcb + archive_member=las (zip-LAS)
# ---------------------------------------------------------------------
DATASET = "d-wco"
FORMAT = "f-las"


def _las_zip_bytes(las_path, member="WCO_1.las", extra_member=None):
    buffer = io.BytesIO()
    with open(las_path, "rb") as handle:
        body = handle.read()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, body)
        if extra_member:
            archive.writestr(extra_member, body)
    return buffer.getvalue()


def _cwcb_las_definition(**overrides):
    definition = LTI._definition(
        code="CWCBLASTEST",
        index_format="cwcb",
        tiles_url="https://cwcb.test/api/lidar/tiles",
        summaries_url="https://cwcb.test/api/lidar/tileSummaries",
        file_url_template="https://cwcb.test/api/lidar/files/{tileKey}/"
                          "{formatKey}",
        dataset_ids=DATASET,
        format_key=FORMAT,
        archive_member="las",
        point_formats="6",
    )
    definition.pop("index_url_template", None)
    definition.pop("tile_url_template", None)
    definition.update(overrides)
    return definition


@pytest.fixture
def fake_cwcb(monkeypatch):
    import requests

    tile_box = LTI._box_of_tile()
    ring = [(tile_box[0], tile_box[1]), (tile_box[2], tile_box[1]),
            (tile_box[2], tile_box[3]), (tile_box[0], tile_box[3]),
            (tile_box[0], tile_box[1])]
    wkt = "POLYGON ((%s))" % ", ".join("%.9f %.9f" % p for p in ring)
    state = {"zips": {}, "calls": [], "size": 1000}

    def _post(url, data=None, **kwargs):
        state["calls"].append(("POST", url))
        if url.endswith("/tiles"):
            return LTI._Response(200, {"datasets": [DATASET],
                                       "tiles": ["k1"]})
        return LTI._Response(200, {DATASET: {"k1": {
            "geography": {"geography": {"wellKnownText": wkt}},
            "model": {"tileId": "WCO_1", "dataset": DATASET,
                      "fileSummaries": [{"format": FORMAT,
                                         "fileSizeTotal": state["size"]}]},
        }}})

    def _get(url, **kwargs):
        state["calls"].append(("GET", url))
        body = state["zips"].get(url.split("/files/", 1)[-1].split("/")[0])
        if body is None:
            return LTI._Response(404)
        return LTI._Response(200, body=body, headers={
            "Content-Length": str(len(body)),
            "Content-Type": "application/x-zip-compressed"})

    def _head(url, **kwargs):
        state["calls"].append(("HEAD", url))
        return LTI._Response(405)

    monkeypatch.setattr(requests, "post", _post)
    monkeypatch.setattr(requests, "get", _get)
    monkeypatch.setattr(requests, "head", _head)
    return state


def test_zip_las_extracts_the_member_and_leaves_no_zip(fake_cwcb, tmp_path,
                                                       monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    las = LTI._write_las(tmp_path / "src" / "WCO_1.las")
    fake_cwcb["zips"]["k1"] = _las_zip_bytes(las)
    with open(las, "rb") as handle:
        fake_cwcb["size"] = len(handle.read())
    destination = str(tmp_path / "out" / "7V2_cwcblastest.tif")
    os.makedirs(os.path.dirname(destination))
    provenance = ea_las_tile_index.LasTileIndexStrategy().fetch(
        _cwcb_las_definition(), LTI._box_of_tile(), 1.0, destination)
    cache = ea_las_tile_index.las_tile_cache_directory("CWCBLASTEST")
    assert sorted(os.listdir(cache)) == [
        "WCO_1.las", "WCO_1_dtm.json", "WCO_1_dtm.tif"]
    with open(os.path.join(cache, "WCO_1.las"), "rb") as cached, \
            open(las, "rb") as original:
        assert cached.read() == original.read()
    assert not [name for name in os.listdir(os.path.dirname(destination))
                if name.endswith((".zip", ".part"))]
    assert [c[0] for c in fake_cwcb["calls"]].count("HEAD") == 0
    assert provenance["source_ids"] == ["WCO_1"]
    assert provenance["valid_fraction"] >= 0.95
    values, _transform = LTI._read(destination)
    good = values[values != -32768.0]
    assert 7800 * LTI.FTUS - 1 < good.min() < good.max() \
        < 7803 * LTI.FTUS + 1


def test_zip_with_two_las_members_is_unavailable_and_removed(
        fake_cwcb, tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    las = LTI._write_las(tmp_path / "src" / "WCO_1.las")
    fake_cwcb["zips"]["k1"] = _las_zip_bytes(las, extra_member="b/x.las")
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="holds 2 .las member"):
        ea_las_tile_index.LasTileIndexStrategy().fetch(
            _cwcb_las_definition(), LTI._box_of_tile(), 1.0,
            str(tmp_path / "7V2_x.tif"))
    cache = ea_las_tile_index.las_tile_cache_directory("CWCBLASTEST")
    assert os.listdir(cache) == []


def test_zip_las_cap_is_judged_on_the_listing_before_download(
        fake_cwcb, tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "E"))
    fake_cwcb["size"] = 2_000_000_000
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="SKIPPED, recorded unavailable"):
        ea_las_tile_index.LasTileIndexStrategy().fetch(
            _cwcb_las_definition(max_bytes_per_airport="1800000000"),
            LTI._box_of_tile(), 1.0, str(tmp_path / "7V2_x.tif"))
    assert [c for c in fake_cwcb["calls"] if c[0] in ("GET", "HEAD")] == []


def test_unknown_archive_member_and_index_format_refuse(tmp_path):
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="archive_member=tar is not supported"):
        ea_las_tile_index.LasTileIndexStrategy().fetch(
            _cwcb_las_definition(archive_member="tar"),
            LTI._box_of_tile(), 1.0, str(tmp_path / "x.tif"))
    with pytest.raises(ea_base.ProviderUnavailable,
                       match="index_format=wfs is not one of"):
        ea_las_tile_index.LasTileIndexStrategy().discover(
            _ogr_definition("x", index_format="wfs"), LTI._box_of_tile())


# ---------------------------------------------------------------------
# the shipped definitions
# ---------------------------------------------------------------------
def test_shipped_holder_las_definitions():
    providers = INSETS.initialize_elevation_providers_dict()
    valdez = providers["NOAAVALDEZLAZ"]
    assert valdez["access_strategy"] == "las_tile_index"
    assert valdez["index_format"] == ea_las_tile_index.LAS_INDEX_FORMAT_OGR
    assert valdez["index_url"].endswith(
        "/laz/geoid12b/8539/tileindex_ak2012_valdez_m8539.gpkg")
    assert valdez["point_compression"] == "laz"
    assert INSETS.provider_required_capabilities(valdez) == [
        ea_capabilities.CAPABILITY_LAS, ea_capabilities.CAPABILITY_LAZ]
    seven = providers["CWCB7V2LAS"]
    assert seven["index_format"] == ea_las_tile_index.LAS_INDEX_FORMAT_CWCB
    assert seven["archive_member"] == ea_las_tile_index.LAS_ARCHIVE_MEMBER_LAS
    for definition in (valdez, seven):
        assert str(definition["ladder_member"]).lower() == "true"
        assert int(float(definition["priority"])) == 90
        assert definition["enabled"] is True
        assert definition["license_note"]
        assert definition["attribution"]
        assert definition.get("coverage_bbox")
        assert ea_las_tiles.las_core_geometry(definition) is None
    # the boxes hold their airports (PAVD 61.132 N -146.248 E; 7V2
    # 38.833 N -107.643 E) and nothing of the five controls
    assert ea_definitions._coverage_bbox_intersects(
        valdez, (-146.26, 61.12, -146.23, 61.14))
    assert ea_definitions._coverage_bbox_intersects(
        seven, (-107.66, 38.82, -107.63, 38.84))
    for definition in (valdez, seven):
        for box in ((31.38, 30.10, 31.42, 30.14),      # HECA
                    (-80.96, 35.20, -80.92, 35.24),    # KCLT
                    (-106.88, 39.21, -106.86, 39.23)):  # KASE
            assert not ea_definitions._coverage_bbox_intersects(definition, box)

