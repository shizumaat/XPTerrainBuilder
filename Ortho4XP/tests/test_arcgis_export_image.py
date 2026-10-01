"""THE arcgis_export_image STRATEGY (spec us-holder-providers §3.4,
RULINGS 2026-09-30bm, issue #154) AND THE EMPTY-noData DEFECT (#155).

An ArcGIS ImageServer with no tile cache (Oregon DOGAMI, Hillsborough's
native 2.5 ft DEM) is asked through ``exportImage``, which refuses a
request above a few megapixels -- one inset box is ~76 Mpx -- so the box
is CHUNKED.  These twins pin the contract with a synthetic server, no
network:

* the chunker (fewest chunks, every chunk within the pixel budget and the
  per-side limits, the grid covered exactly once; 76 Mpx -> 13 at 6 Mpx);
* the classes: a cap -> ``ProviderUnavailable`` before any GET; 5xx ->
  retried, then transient; an oversize answer -> ``ProviderUnavailable``
  naming the CHUNKER (a bug, never a transient); a 4xx -> unavailable;
  every chunk all-nodata -> ``None``;
* ``nodata`` mandatory: refused at parse, and an UNTAGGED chunk (the
  empty-noData answer, 0.0 = false sea level) refused at fetch (#155);
* the feet raster comes out in metres through the ONE vertical-unit site;
* the ``.elv`` parser keeps a ``rendering_rule`` JSON intact.
"""
from __future__ import annotations

import os
import subprocess
import sys
import types
from urllib.parse import parse_qs, urlsplit

import numpy
import pytest

sys.path.insert(0, "src")

import O4_Airport_Elevation_Insets as INSETS
import O4_UI_Utils as UI

gdal = pytest.importorskip("osgeo.gdal")
osr = pytest.importorskip("osgeo.osr")

FT = 0.3048
#: A small box at KEUG (Eugene, Oregon) -- inside DOGAMI's frame.
KEUG_BOX = (-123.222, 44.118, -123.204, 44.130)
NODATA = -9999.0


def _definition(**extra):
    definition = {
        "code": "TESTEXPORT",
        "access_strategy": "arcgis_export_image",
        "export_url": "https://export.test/arcgis/rest/services/dem/ImageServer",
        "source_epsg": "6557",
        "native_resolution_m": 0.9144,
        "nodata": "-9999",
        "vertical_unit": "ft",
        "export_format": "tiff",
        "max_request_px": "20000",
        "coverage_bbox": (-125.0, 41.0, -116.0, 47.0),
    }
    definition.update(extra)
    return definition


def _plane_ft(x, y):
    """The synthetic surface, in FEET, in the request frame's units."""
    return 361.0 + 0.001 * (x - 600000.0) - 0.0005 * (y - 877000.0)


def _render_tiff(query, tagged=True, hole=True):
    """One exportImage answer: an F32 GeoTIFF of the plane over the
    requested bbox/size in EPSG:6557, holes as the requested noData."""
    (left, bottom, right, top) = [float(v) for v in
                                  query["bbox"][0].split(",")]
    (width, height) = [int(v) for v in query["size"][0].split(",")]
    pixel_x = (right - left) / width
    pixel_y = (top - bottom) / height
    xs = left + (numpy.arange(width) + 0.5) * pixel_x
    ys = top - (numpy.arange(height) + 0.5) * pixel_y
    grid_x, grid_y = numpy.meshgrid(xs, ys)
    values = _plane_ft(grid_x, grid_y).astype(numpy.float32)
    nodata_text = query.get("noData", [""])[0]
    if hole:
        values[:2, :2] = float(nodata_text) if nodata_text else 0.0
    path = "/vsimem/export_%d.tif" % id(values)
    dataset = gdal.GetDriverByName("GTiff").Create(
        path, width, height, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((left, pixel_x, 0.0, top, 0.0, -pixel_y))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(int(query["imageSR"][0]))
    dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    if tagged and nodata_text:
        band.SetNoDataValue(float(nodata_text))
    band.WriteArray(values)
    dataset = None
    handle = gdal.VSIFOpenL(path, "rb")
    gdal.VSIFSeekL(handle, 0, 2)
    size = gdal.VSIFTellL(handle)
    gdal.VSIFSeekL(handle, 0, 0)
    payload = gdal.VSIFReadL(1, size, handle)
    gdal.VSIFCloseL(handle)
    gdal.Unlink(path)
    return payload


def _answer(status, payload, text=None):
    return types.SimpleNamespace(
        status_code=status,
        iter_content=lambda size: iter([payload]),
        text=text if text is not None else "",
    )


class _Server:
    """A ``requests.Session`` stand-in serving ``answer(query, n)``."""

    def __init__(self, answer):
        self.answer = answer
        self.urls = []

    def __call__(self):
        return self

    def get(self, url, timeout=None, stream=False):
        self.urls.append(url)
        query = parse_qs(urlsplit(url).query, keep_blank_values=True)
        return self.answer(query, len(self.urls))


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    UI.red_flag = False
    yield
    UI.red_flag = False


def _serve(monkeypatch, answer):
    import requests

    server = _Server(answer)
    monkeypatch.setattr(requests, "Session", server)
    return server


# ---------------------------------------------------------------------
# 1. the chunker
# ---------------------------------------------------------------------
def _assert_tiles_exactly(chunks, width, height, max_px, max_w=None,
                          max_h=None):
    covered = numpy.zeros((height, width), dtype=numpy.int32)
    for (column0, row0, chunk_w, chunk_h) in chunks:
        assert chunk_w * chunk_h <= max_px
        if max_w:
            assert chunk_w <= max_w
        if max_h:
            assert chunk_h <= max_h
        covered[row0:row0 + chunk_h, column0:column0 + chunk_w] += 1
    assert (covered == 1).all()


def test_a_76_mpx_box_is_13_chunks_at_6_mpx():
    """Spec §6.5: the DOGAMI-sized box (8718 x 8718 = 76.0 Mpx, no side
    limit -- maxImageWidth/Height 120,000) is the floor ceil(76/6)."""
    chunks = INSETS.export_image_chunk_grid(8718, 8718, 6000000)
    assert len(chunks) == 13
    _assert_tiles_exactly(chunks, 8718, 8718, 6000000)


def test_the_per_side_limits_bind():
    """Hillsborough's service: 15,000 wide, 4,100 tall at most."""
    chunks = INSETS.export_image_chunk_grid(7000, 9000, 6000000,
                                            15000, 4100)
    _assert_tiles_exactly(chunks, 7000, 9000, 6000000, 15000, 4100)
    assert len(chunks) == 11


@pytest.mark.parametrize("width,height,max_px,max_w,max_h", [
    (1, 1, 6000000, None, None),
    (123, 4567, 1000, None, None),
    (4567, 123, 1000, 300, None),
    (9001, 7003, 6000000, 15000, 4100),
    (20000, 50, 6000000, 15000, 4100),
    (3, 3, 4, 2, 2),
])
def test_the_chunker_covers_once_within_every_limit(width, height, max_px,
                                                    max_w, max_h):
    chunks = INSETS.export_image_chunk_grid(width, height, max_px, max_w,
                                            max_h)
    _assert_tiles_exactly(chunks, width, height, max_px, max_w, max_h)
    assert len(chunks) >= -(-width * height // max_px)


# ---------------------------------------------------------------------
# 2. nodata mandatory (#155) and the .elv parse
# ---------------------------------------------------------------------
def _write_elv(directory, name, text):
    (directory / (name + ".elv")).write_text(text, encoding="utf-8", newline="\n")


def test_a_definition_without_nodata_is_refused_at_parse(tmp_path):
    _write_elv(tmp_path, "NONODATA",
               "access_strategy=arcgis_export_image\n"
               "export_url=https://x.test/ImageServer\nsource_epsg=6557\n")
    _write_elv(tmp_path, "EMPTYKVP",
               "access_strategy=wcs_kvp\nwcs_getcoverage_template="
               "https://x.test/ImageServer/exportImage?bbox={xmin},{ymin},"
               "{xmax},{ymax}&noData=&f=image\n")
    _write_elv(tmp_path, "PLACEHOLDERNOKEY",
               "access_strategy=wcs_kvp\nwcs_getcoverage_template="
               "https://x.test/ImageServer/exportImage?noData={nodata}"
               "&f=image\n")
    _write_elv(tmp_path, "HESSELIKE",
               "access_strategy=wcs_kvp\nwcs_getcoverage_template="
               "https://x.test/wcs?REQUEST=GetCoverage&SUBSET=E({xmin},"
               "{xmax})\n")
    registry = INSETS.initialize_elevation_providers_dict(str(tmp_path))
    for code in ("NONODATA", "EMPTYKVP", "PLACEHOLDERNOKEY"):
        assert registry[code]["enabled"] is False
        assert "#155" in registry[code]["definition_refusal"]
    # A true WCS KVP (Hesse) has no noData parameter: untouched.
    assert registry["HESSELIKE"]["enabled"] is True
    assert "definition_refusal" not in registry["HESSELIKE"]


def test_the_elv_parser_keeps_a_rendering_rule_json_intact(tmp_path):
    rule = ('{"rasterFunction":"Arithmetic","rasterFunctionArguments":'
            '{"Raster":"$$","Raster2":0.3048,"Operation":3},'
            '"outputPixelType":"F32"}')
    _write_elv(tmp_path, "RULED",
               "access_strategy=arcgis_export_image\n"
               "export_url=https://x.test/ImageServer\nsource_epsg=6557\n"
               "nodata=-9999\nrendering_rule=" + rule + "\n")
    registry = INSETS.initialize_elevation_providers_dict(str(tmp_path))
    assert registry["RULED"]["rendering_rule"] == rule
    assert registry["RULED"]["enabled"] is True
    strategy = INSETS.ArcgisExportImageStrategy()
    definition = dict(registry["RULED"], native_resolution_m=0.9144)
    grid = strategy.request_grid(definition, KEUG_BOX)
    url = strategy.chunk_url(definition, grid, (0, 0, 10, 10))
    sent = parse_qs(urlsplit(url).query)["renderingRule"][0]
    import json

    assert json.loads(sent) == json.loads(rule)


def test_the_shipped_exportimage_providers_carry_nodata():
    registry = INSETS.initialize_elevation_providers_dict(
        os.path.join("Providers", "Elevation"))
    for code in ("CURITIBA50CM", "CZECHIA2M", "LITHUANIA1M"):
        definition = registry[code]
        assert definition["nodata"] == "-9999"
        assert "noData={nodata}" in definition["wcs_getcoverage_template"]
        assert "definition_refusal" not in definition
        url = INSETS.WcsKvpStrategy()._request_url(
            definition, definition["coverage_bbox"], 50.0)
        assert "noData=-9999&" in url
    for (code, unit, epsg) in (("OREGONDOGAMI", "ft", "6557"),
                               ("HILLSBOROUGHNATIVE", "ftUS", "6443")):
        definition = registry[code]
        assert definition["access_strategy"] == "arcgis_export_image"
        assert definition["enabled"] is True
        assert definition["vertical_unit"] == unit
        assert definition["source_epsg"] == epsg
        assert definition["nodata"] == "-9999"
        assert definition["ladder_member"] is True
        assert definition["priority"] < registry["USGS3DEP"]["priority"]
        assert definition["license_note"] and definition["attribution"]
        assert "definition_refusal" not in definition
    # The controls never meet a holder box (spec §6.4).
    for box in ((31.38, 30.08, 31.44, 30.14),      # HECA
                (-106.88, 39.20, -106.85, 39.24),  # KASE
                (-80.97, 35.19, -80.92, 35.24),    # KCLT
                (-135.09, 60.70, -135.05, 60.72),  # CYXY
                (-77.13, -12.03, -77.10, -12.01)):  # SPJC
        for code in ("OREGONDOGAMI", "HILLSBOROUGHNATIVE"):
            assert not INSETS._coverage_bbox_intersects(registry[code], box)


# ---------------------------------------------------------------------
# 3. the fetch, end to end on a synthetic server
# ---------------------------------------------------------------------
def test_the_chunked_feet_export_arrives_in_metres(tmp_path, monkeypatch):
    server = _serve(monkeypatch, lambda query, n: _answer(
        200, _render_tiff(query)))
    definition = _definition()
    strategy = INSETS.ArcgisExportImageStrategy()
    grid = strategy.request_grid(definition, KEUG_BOX, 5.0)
    expected_chunks = strategy.chunks(definition, grid)
    assert len(expected_chunks) > 1
    destination = str(tmp_path / "KEUG_TESTEXPORT.tif")
    provenance = INSETS.fetch_inset(definition, KEUG_BOX, 5.0, destination)
    assert provenance is not None
    assert provenance["request_count"] == len(expected_chunks)
    assert len(server.urls) == len(expected_chunks)
    assert provenance["bytes_fetched"] > 0
    assert provenance["vertical_unit_applied"] == "m"
    assert provenance["vertical_unit_source"] == "elv"
    for url in server.urls:
        query = parse_qs(urlsplit(url).query, keep_blank_values=True)
        assert query["noData"] == ["-9999"]
        (w, h) = [int(v) for v in query["size"][0].split(",")]
        assert w * h <= 20000
    assert not os.path.exists(destination + ".exportchunks")
    # Every valid cell is the plane in METRES (one site, x0.3048).
    dataset = gdal.Open(destination)
    values = dataset.GetRasterBand(1).ReadAsArray()
    transform = dataset.GetGeoTransform()
    rows, columns = values.shape
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target = osr.SpatialReference()
    target.ImportFromEPSG(6557)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    to_source = osr.CoordinateTransformation(source, target)
    checked = 0
    for row in range(5, rows - 5, max(1, rows // 7)):
        for column in range(5, columns - 5, max(1, columns // 7)):
            value = values[row, column]
            if value == -32768.0:
                continue
            lon = transform[0] + (column + 0.5) * transform[1]
            lat = transform[3] + (row + 0.5) * transform[5]
            (x, y, _z) = to_source.TransformPoint(lon, lat)
            assert value == pytest.approx(_plane_ft(x, y) * FT, abs=0.01)
            checked += 1
    assert checked > 10


def test_a_cap_is_unavailable_before_any_get(tmp_path, monkeypatch):
    server = _serve(monkeypatch, lambda query, n: pytest.fail("a GET"))
    definition = _definition(max_bytes_per_airport="1000")
    with pytest.raises(INSETS.ProviderUnavailable) as raised:
        INSETS.fetch_inset(definition, KEUG_BOX, 5.0,
                           str(tmp_path / "KEUG_TESTEXPORT.tif"))
    assert "max_bytes_per_airport" in raised.value.reason
    assert "not no-coverage" in raised.value.reason
    assert server.urls == []


def test_an_untagged_chunk_is_refused_never_sea_level(tmp_path, monkeypatch):
    """#155: the empty-noData answer -- 0.0 with no nodata tag."""
    _serve(monkeypatch, lambda query, n: _answer(
        200, _render_tiff(query, tagged=False)))
    with pytest.raises(INSETS.ProviderUnavailable) as raised:
        INSETS.fetch_inset(_definition(), KEUG_BOX, 5.0,
                           str(tmp_path / "KEUG_TESTEXPORT.tif"))
    assert "#155" in raised.value.reason
    assert not os.path.exists(str(tmp_path / "KEUG_TESTEXPORT.tif"))


def test_an_oversize_answer_is_a_chunker_bug_not_a_transient(
        tmp_path, monkeypatch):
    body = (b'{"error":{"code":400,"message":"Invalid or missing input '
            b'parameters.","details":["The requested image exceeds the '
            b'size limit."]}}')
    for status in (200, 500):
        _serve(monkeypatch, lambda query, n: _answer(
            status, body, body.decode()))
        with pytest.raises(INSETS.ProviderUnavailable) as raised:
            INSETS.fetch_inset(_definition(), KEUG_BOX, 5.0,
                               str(tmp_path / "KEUG_TESTEXPORT.tif"))
        assert "CHUNKER BUG" in raised.value.reason


def test_a_5xx_is_retried_then_transient(tmp_path, monkeypatch):
    server = _serve(monkeypatch, lambda query, n: _answer(
        503, b"", "Service Unavailable"))
    with pytest.raises(INSETS.TransientFetchError):
        INSETS.fetch_inset(_definition(), KEUG_BOX, 5.0,
                           str(tmp_path / "KEUG_TESTEXPORT.tif"))
    assert len(server.urls) == INSETS.EXPORT_IMAGE_TRANSIENT_ATTEMPTS


def test_one_5xx_then_the_chunk_arrives(tmp_path, monkeypatch):
    def answer(query, n):
        if n == 1:
            return _answer(502, b"", "Bad Gateway")
        return _answer(200, _render_tiff(query))

    _serve(monkeypatch, answer)
    provenance = INSETS.fetch_inset(_definition(), KEUG_BOX, 5.0,
                                    str(tmp_path / "KEUG_TESTEXPORT.tif"))
    assert provenance is not None


def test_a_non_tiff_200_is_transient(tmp_path, monkeypatch):
    _serve(monkeypatch, lambda query, n: _answer(
        200, b"<html>maintenance</html>"))
    with pytest.raises(INSETS.TransientFetchError):
        INSETS.fetch_inset(_definition(), KEUG_BOX, 5.0,
                           str(tmp_path / "KEUG_TESTEXPORT.tif"))


def test_a_404_is_unavailable_never_no_coverage(tmp_path, monkeypatch):
    _serve(monkeypatch, lambda query, n: _answer(404, b"", "Not Found"))
    with pytest.raises(INSETS.ProviderUnavailable):
        INSETS.fetch_inset(_definition(), KEUG_BOX, 5.0,
                           str(tmp_path / "KEUG_TESTEXPORT.tif"))


def test_every_chunk_all_nodata_is_no_coverage(tmp_path, monkeypatch):
    def answer(query, n):
        payload = _render_tiff(query, hole=False)
        path = "/vsimem/blank_%d.tif" % n
        gdal.FileFromMemBuffer(path, payload)
        dataset = gdal.Open(path, gdal.GA_Update)
        band = dataset.GetRasterBand(1)
        band.WriteArray(numpy.full((dataset.RasterYSize,
                                    dataset.RasterXSize), NODATA,
                                   dtype=numpy.float32))
        dataset = None
        handle = gdal.VSIFOpenL(path, "rb")
        gdal.VSIFSeekL(handle, 0, 2)
        size = gdal.VSIFTellL(handle)
        gdal.VSIFSeekL(handle, 0, 0)
        data = gdal.VSIFReadL(1, size, handle)
        gdal.VSIFCloseL(handle)
        gdal.Unlink(path)
        return _answer(200, data)

    _serve(monkeypatch, answer)
    assert INSETS.fetch_inset(_definition(), KEUG_BOX, 5.0,
                              str(tmp_path / "KEUG_TESTEXPORT.tif")) is None


def test_outside_the_coverage_box_no_call(tmp_path, monkeypatch):
    server = _serve(monkeypatch, lambda query, n: pytest.fail("a GET"))
    assert INSETS.fetch_inset(_definition(), (31.38, 30.08, 31.44, 30.14),
                              5.0, str(tmp_path / "HECA_X.tif")) is None
    assert server.urls == []


def test_lerc_without_the_decoder_is_unavailable(tmp_path, monkeypatch):
    server = _serve(monkeypatch, lambda query, n: pytest.fail("a GET"))
    monkeypatch.setattr(INSETS, "lerc_decode_available", lambda: False)
    with pytest.raises(INSETS.ProviderUnavailable):
        INSETS.fetch_inset(_definition(export_format="lerc",
                                       lerc_max_error="0.01"),
                           KEUG_BOX, 5.0,
                           str(tmp_path / "KEUG_TESTEXPORT.tif"))
    assert server.urls == []


def test_the_lerc_chunks_decode_uncropped_and_georeference(
        tmp_path, monkeypatch):
    """The LERC body path: every chunk blob is decoded OUT OF PROCESS
    (the shared worker; ``*.lercimg`` is never cropped to a 256 tile)
    and laid back on the request grid."""
    definition = _definition(export_format="lerc", lerc_max_error="0.001")
    strategy = INSETS.ArcgisExportImageStrategy()
    grid = strategy.request_grid(definition, KEUG_BOX, 5.0)
    chunks = strategy.chunks(definition, grid)
    (x_min, y_max, pixel, _w, _h, _epsg) = grid
    blobs = []
    for (index, (column0, row0, chunk_w, chunk_h)) in enumerate(chunks):
        xs = x_min + (column0 + numpy.arange(chunk_w) + 0.5) * pixel
        ys = y_max - (row0 + numpy.arange(chunk_h) + 0.5) * pixel
        grid_x, grid_y = numpy.meshgrid(xs, ys)
        values = _plane_ft(grid_x, grid_y).astype(numpy.float32)
        source = tmp_path / ("plane%d.npy" % index)
        numpy.save(source, values)
        blob = tmp_path / ("blob%d.lerc" % index)
        # Encoded in a CHILD: imagecodecs' LERC beside GDAL aborts.
        completed = subprocess.run(
            [sys.executable, "-c",
             "import sys, numpy, imagecodecs\n"
             "v = numpy.load(sys.argv[1])\n"
             "open(sys.argv[2], 'wb').write(imagecodecs.lerc_encode(v))\n",
             str(source), str(blob)],
            capture_output=True, text=True, timeout=180)
        if completed.returncode != 0:
            pytest.skip("imagecodecs LERC not available")
        blobs.append(blob.read_bytes())
    _serve(monkeypatch, lambda query, n: _answer(200, blobs[n - 1]))
    destination = str(tmp_path / "KEUG_TESTEXPORT.tif")
    provenance = INSETS.fetch_inset(definition, KEUG_BOX, 5.0, destination)
    assert provenance is not None
    assert provenance["export_format"] == "lerc"
    assert provenance["request_count"] == len(chunks)
    dataset = gdal.Open(destination)
    values = dataset.GetRasterBand(1).ReadAsArray()
    dataset = None
    valid = values[values > -32768]
    assert valid.size > 0.9 * values.size
    low = _plane_ft(x_min, y_max - _h * pixel) * FT
    assert abs(float(numpy.median(valid)) - 361.0 * FT) < 5.0
    assert float(valid.min()) > low - 5.0


# ---------------------------------------------------------------------
# 4. wcs_kvp's exportImage templates (#155)
# ---------------------------------------------------------------------
def test_wcs_kvp_fills_nodata_and_refuses_an_untagged_answer(
        tmp_path, monkeypatch):
    import requests

    definition = {
        "code": "TESTKVPEXPORT",
        "access_strategy": "wcs_kvp",
        "wcs_getcoverage_template": (
            "https://x.test/ImageServer/exportImage?bbox={xmin},{ymin},"
            "{xmax},{ymax}&bboxSR=6557&imageSR=6557&format=tiff"
            "&pixelType=F32&noData={nodata}&size={width},{height}"
            "&f=image"),
        "source_epsg": "6557",
        "native_resolution_m": 5.0,
        "nodata": "-9999",
    }
    seen = []

    def fake_get(url, timeout=None, headers=None, tagged=True):
        seen.append(url)
        query = parse_qs(urlsplit(url).query, keep_blank_values=True)
        return types.SimpleNamespace(
            status_code=200, content=_render_tiff(query, tagged=tagged))

    monkeypatch.setattr(requests, "get", fake_get)
    provenance = INSETS.fetch_inset(definition, KEUG_BOX, 5.0,
                                    str(tmp_path / "KEUG_A.tif"))
    assert provenance is not None
    assert "noData=-9999&" in seen[-1]
    monkeypatch.setattr(requests, "get", lambda url, timeout=None,
                        headers=None: fake_get(url, tagged=False))
    with pytest.raises(INSETS.ProviderUnavailable) as raised:
        INSETS.fetch_inset(definition, KEUG_BOX, 5.0,
                           str(tmp_path / "KEUG_B.tif"))
    assert "#155" in raised.value.reason
