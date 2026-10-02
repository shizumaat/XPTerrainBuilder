"""#158 -- the OPR rung's WHOLE-TILE PREFETCH for stripped products.

THE MEASUREMENT (2026-10-02, a loopback server serving a synthetic
WA_NorthEast_B22 layout: 4 tiles, 2000 x 2000 px at 0.5 m in a State
Plane foot CRS, 2000 x 1 DEFLATE strips, no overviews, 10.3 MB each):

    windowed /vsicurl warp, full box    21 requests   82.7 MB  = 2.00x
    windowed /vsicurl warp, half box    26 requests   67.3 MB  = 1.63x
    windowed /vsicurl warp, runway band 21 requests   49.4 MB  = 1.19x
    windowed /vsicurl warp, 20 % box    15 requests   47.2 MB  = 1.14x
    whole GET per tile + local warp      4 requests   41.3 MB  = 1.00x

-- the multiplier is against the tiles' WHOLE bytes on disk, so the
windowed read NEVER moves less than the files whatever the window's
shape: a strip as wide as the raster must be decoded whole for any
pixel in it.  KGEG's 64 x ~16 MB campaign is the field case: 13 min 42 s
through the window at 1.25 MB/s against 8 parallel whole downloads at
2.2 MB/s aggregate (#158).  A 256 x 256 tiled COG is NOT this and stays
on /vsicurl (PANC's 68 of them fetch in 1:56).

No real network: an HTTP server on loopback serves both the TNM listing
and the tiles, so the transport under test is the real one.
"""

import hashlib
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy
import pytest

import O4_Airport_Elevation_Insets as INSETS

gdal = pytest.importorskip("osgeo.gdal")
from osgeo import osr  # noqa: E402

#: Washington North (ftUS), NAD83(2011) -- KGEG's OPR products' CRS.
SPFT = 6597
BOX = (-117.5480, 47.6120, -117.5320, 47.6260)
#: Small enough to keep the twin quick, wide enough that a "strip as
#: wide as the raster" is a real strip -- and fine enough (~1 m over
#: BOX) to pass the rung's ``max_source_resolution_m=2`` screen, which
#: is what makes these lidar-class products.
TILE_PX = 1200


def _corner(lon, lat):
    source = osr.SpatialReference()
    source.ImportFromEPSG(4326)
    source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    target = osr.SpatialReference()
    target.ImportFromEPSG(SPFT)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    (x, y, _z) = osr.CoordinateTransformation(source, target).TransformPoint(
        lon, lat)
    return (x, y)


def _write_tile(path, seed, stripped, box=BOX):
    """One tile over ``box``: ``stripped`` gives it strips as wide as the
    raster and no overviews (the OPR shape), else 128 x 128 blocks with
    overviews (the Cloud-Optimized shape)."""
    (x0, y1) = _corner(box[0], box[3])
    (x1, y0) = _corner(box[2], box[1])
    options = (["COMPRESS=DEFLATE", "BLOCKYSIZE=1"] if stripped
               else ["COMPRESS=DEFLATE", "TILED=YES", "BLOCKXSIZE=128",
                     "BLOCKYSIZE=128"])
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), TILE_PX, TILE_PX, 1, gdal.GDT_Float32, options=options)
    dataset.SetGeoTransform(((x0, (x1 - x0) / TILE_PX, 0.0,
                              y1, 0.0, -(y1 - y0) / TILE_PX)))
    dataset.SetProjection(_wkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(-999999.0)
    rows = numpy.arange(TILE_PX, dtype=numpy.float32)[:, None]
    columns = numpy.arange(TILE_PX, dtype=numpy.float32)[None, :]
    # Noisy, so DEFLATE cannot collapse the file to a few bytes.
    values = (2400.0 + seed + 0.01 * rows + 0.013 * columns
              + numpy.sin(rows / 7.0) * numpy.cos(columns / 11.0) * 5.0)
    band.WriteArray(values.astype(numpy.float32))
    dataset = None
    if not stripped:
        dataset = gdal.Open(str(path), gdal.GA_Update)
        dataset.BuildOverviews("AVERAGE", [2, 4])
        dataset = None
    return str(path)


def _wkt():
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(SPFT)
    return srs.ExportToWkt()


def _block_shape(path):
    dataset = gdal.Open(path)
    shape = (dataset.RasterXSize, dataset.GetRasterBand(1).GetBlockSize())
    dataset = None
    return shape


class _Layout:
    """The loopback server: the TNM listing at ``/api/products`` and the
    tiles at ``/OPR/<id>.tif``, with per-request accounting."""

    def __init__(self, root, tiles, statuses=None, whole_statuses=None):
        self.root = str(root)
        self.tiles = dict(tiles)                 # {source_id: disk path}
        self.statuses = dict(statuses or {})     # {source_id: http status}
        # Statuses answered ONLY to a GET with no Range header -- the
        # whole-file download the prefetch issues.  The header read (a
        # HEAD plus ranged GETs) still succeeds, so the failure lands
        # MID-PREFETCH, which is the case under test.
        self.whole_statuses = dict(whole_statuses or {})
        self.requests = []
        self.lock = threading.Lock()
        layout = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                pass

            def _note(self, sent):
                with layout.lock:
                    layout.requests.append(
                        (self.command, self.path.split("?", 1)[0],
                         self.headers.get("Range"), sent))

            def _answer(self, status, body=b"", extra=None):
                self._note(len(body))
                self.send_response(status)
                for (key, value) in (extra or {}).items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body and self.command == "GET":
                    self.wfile.write(body)

            def _serve(self):
                path = self.path.split("?", 1)[0]
                if path.startswith("/api/products"):
                    return self._answer(
                        200, json.dumps(layout.listing()).encode("utf-8"),
                        {"Content-Type": "application/json"})
                name = os.path.basename(path)
                source_id = name[:-4] if name.endswith(".tif") else name
                status = layout.statuses.get(source_id)
                if status is None and self.headers.get("Range") is None \
                        and self.command == "GET":
                    status = layout.whole_statuses.get(source_id)
                if status is not None:
                    return self._answer(status)
                disk = layout.tiles.get(source_id)
                if disk is None or not os.path.isfile(disk):
                    return self._answer(404)
                total = os.path.getsize(disk)
                (start, end, partial) = (0, total - 1, False)
                match = re.match(r"bytes=(\d*)-(\d*)",
                                 (self.headers.get("Range") or "").strip())
                if match:
                    partial = True
                    (first, last) = match.groups()
                    if first:
                        start = int(first)
                        end = int(last) if last else total - 1
                    else:
                        start = max(0, total - int(last))
                    end = min(end, total - 1)
                length = max(0, end - start + 1)
                self._note(length)
                self.send_response(206 if partial else 200)
                self.send_header("Content-Type", "image/tiff")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                if partial:
                    self.send_header(
                        "Content-Range",
                        "bytes %d-%d/%d" % (start, end, total))
                self.end_headers()
                if self.command == "GET" and length:
                    with open(disk, "rb") as handle:
                        handle.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = handle.read(min(1 << 20, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)

            def do_HEAD(self):
                self._serve()

            def do_GET(self):
                self._serve()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()

    def listing(self):
        items = [
            {"downloadURL": "%s/OPR/%s.tif" % (self.base, source_id),
             "sourceId": source_id,
             "title": "USGS OPR %s" % source_id,
             "publicationDate": "2022-01-0%d" % (number + 1),
             "boundingBox": {"minX": BOX[0], "minY": BOX[1],
                             "maxX": BOX[2], "maxY": BOX[3]}}
            for (number, source_id) in enumerate(sorted(self.tiles))
        ]
        return {"total": len(items), "items": items}

    def whole_gets(self, source_id):
        """GETs for one tile that carried NO Range header -- a whole-file
        download, which is what the prefetch issues."""
        with self.lock:
            return [entry for entry in self.requests
                    if entry[0] == "GET" and entry[2] is None
                    and entry[1].endswith("/%s.tif" % source_id)]

    def tile_requests(self):
        with self.lock:
            return [entry for entry in self.requests
                    if entry[1].startswith("/OPR/")]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def layout(tmp_path, request):
    made = []

    def _make(stripped_ids=("S0", "S1"), cog_ids=(), statuses=None,
              whole_statuses=None):
        tiles = {}
        for (number, source_id) in enumerate(stripped_ids):
            tiles[source_id] = _write_tile(
                tmp_path / ("%s.tif" % source_id), number, stripped=True)
        for (number, source_id) in enumerate(cog_ids):
            tiles[source_id] = _write_tile(
                tmp_path / ("%s.tif" % source_id), 100 + number,
                stripped=False)
        built = _Layout(tmp_path, tiles, statuses, whole_statuses)
        made.append(built)
        return built

    yield _make
    for built in made:
        built.close()


def _definition(served, code, **overrides):
    definition = {
        "code": code,
        "access_strategy": "tnm_cog",
        "discovery_url_template":
            served.base + "/api/products?bbox={west},{south},{east},{north}",
        "native_resolution_m": 1.0,
        "source_units": "from_source",
        "max_source_resolution_m": "2",
        "ladder_judge": "airport_cover",
        "vertical_datum": "NAVD88",
        "fetch_slots": "4",
    }
    definition.update(overrides)
    return definition


def _array(path):
    dataset = gdal.Open(path)
    band = dataset.GetRasterBand(1)
    out = (band.ReadAsArray().tobytes(), dataset.GetGeoTransform(),
           dataset.GetProjection())
    dataset = None
    return out


def _file_digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def test_the_synthetic_layout_really_is_stripped(tmp_path):
    """The twin's premise: the stripped tile's block is as wide as the
    raster and the COG's is not, and :func:`_raster_source_is_stripped`
    reads exactly that distinction off the header."""
    stripped = _write_tile(tmp_path / "s.tif", 0, stripped=True)
    cog = _write_tile(tmp_path / "c.tif", 1, stripped=False)
    (width, (block_x, block_y)) = _block_shape(stripped)
    assert (block_x, block_y) == (width, 1)
    (width, (block_x, _block_y)) = _block_shape(cog)
    assert block_x == 128 < width
    assert INSETS._raster_source_is_stripped(
        INSETS._inspect_raster_source(stripped))
    assert not INSETS._raster_source_is_stripped(
        INSETS._inspect_raster_source(cog))


def test_prefetch_output_is_byte_identical_to_the_window_read(layout,
                                                              tmp_path):
    """THE acceptance twin: the same warp over the same tiles, once
    through the windowed /vsicurl read and once through the whole-tile
    prefetch, produces the same raster -- and the prefetch asks for each
    tile exactly ONCE, with no Range header."""
    served = layout(stripped_ids=("S0", "S1"))
    strategy = INSETS.TnmCloudOptimizedGeoTiffStrategy()

    window_out = str(tmp_path / "win" / "KGEG_window.tif")
    window_record = strategy.fetch(
        _definition(served, "OPRWINDOW", prefetch_whole_stripped="False"),
        BOX, 1.0, window_out)
    window_requests = len(served.tile_requests())
    assert window_record["sources_prefetched_whole"] == 0
    assert window_record["sources_stripped"] == 2
    assert not served.whole_gets("S0")

    served.requests.clear()
    prefetch_out = str(tmp_path / "pre" / "KGEG_prefetch.tif")
    prefetch_record = strategy.fetch(
        _definition(served, "OPRPREFETCH"), BOX, 1.0, prefetch_out)
    prefetch_requests = len(served.tile_requests())

    assert _array(prefetch_out) == _array(window_out)
    assert _file_digest(prefetch_out) == _file_digest(window_out)
    assert prefetch_record["sources_prefetched_whole"] == 2
    assert prefetch_record["prefetched_whole_bytes"] > 0
    assert prefetch_record["prefetch_whole_slots"] == 4
    assert "prefetch_whole_skipped" not in prefetch_record
    # one whole GET per tile, and no more
    for source_id in ("S0", "S1"):
        assert len(served.whole_gets(source_id)) == 1, source_id
    # and no scratch file survives the fetch
    assert sorted(os.listdir(os.path.dirname(prefetch_out))) == [
        "KGEG_prefetch.tif"]
    # the window read needed more requests than the prefetch did
    assert prefetch_requests < window_requests


def test_a_tiled_cog_stays_on_the_window_read(layout, tmp_path):
    """A 256 x 256-class tiled COG is the window read's own case and is
    never prefetched; a stripped neighbour in the same listing still is."""
    served = layout(stripped_ids=("S0",), cog_ids=("C0",))
    destination = str(tmp_path / "mix" / "KGEG_mixed.tif")
    record = INSETS.TnmCloudOptimizedGeoTiffStrategy().fetch(
        _definition(served, "OPRMIXED"), BOX, 1.0, destination)
    assert record["sources_stripped"] == 1
    assert record["sources_prefetched_whole"] == 1
    assert len(served.whole_gets("S0")) == 1
    assert served.whole_gets("C0") == []


def test_the_pool_is_bounded_by_fetch_slots(layout, tmp_path, monkeypatch):
    """``fetch_slots`` bounds the concurrent whole downloads: four tiles
    over two slots never put three transfers on the server at once."""
    served = layout(stripped_ids=("S0", "S1", "S2", "S3"))
    state = {"now": 0, "peak": 0}
    lock = threading.Lock()
    real = INSETS.download_whole

    def _counted(*args, **kwargs):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        try:
            return real(*args, **kwargs)
        finally:
            with lock:
                state["now"] -= 1

    monkeypatch.setattr(INSETS, "download_whole", _counted)
    record = INSETS.TnmCloudOptimizedGeoTiffStrategy().fetch(
        _definition(served, "OPRSLOTS", fetch_slots="2"), BOX, 1.0,
        str(tmp_path / "slots" / "KGEG_slots.tif"))
    assert record["sources_prefetched_whole"] == 4
    assert record["prefetch_whole_slots"] == 2
    assert 0 < state["peak"] <= 2, state["peak"]


def test_a_5xx_mid_prefetch_is_transient_and_leaves_no_scratch(layout,
                                                               tmp_path):
    """A listed tile answering 500 half way through is TRANSIENT -- the
    ladder records nothing durable -- and no partial scratch file is left
    beside the destination."""
    served = layout(stripped_ids=("S0", "S1", "S2", "S3"),
                    whole_statuses={"S2": 500})
    destination = str(tmp_path / "boom" / "KGEG_boom.tif")
    with pytest.raises(INSETS.TransientFetchError, match="S2"):
        INSETS.TnmCloudOptimizedGeoTiffStrategy().fetch(
            _definition(served, "OPR5XX"), BOX, 1.0, destination)
    assert os.listdir(os.path.dirname(destination)) == []


def test_a_404_tile_is_unavailable_never_no_coverage(layout, tmp_path):
    """The listing named it, the server does not have it: ``unavailable``
    with the reason (the #157 wording), never the durable no-coverage a
    ``None`` would record."""
    served = layout(stripped_ids=("S0", "S9"),
                    whole_statuses={"S9": 404})
    with pytest.raises(INSETS.ProviderUnavailable, match="S9"):
        INSETS.TnmCloudOptimizedGeoTiffStrategy().fetch(
            _definition(served, "OPR404"), BOX, 1.0,
            str(tmp_path / "gone" / "KGEG_gone.tif"))


def test_the_byte_threshold_is_judged_before_any_get(layout, tmp_path):
    """``prefetch_whole_max_bytes`` is judged on the sizes the headers
    already carry: over the threshold NOTHING is downloaded whole, the
    window read carries the fetch, and the record says why."""
    served = layout(stripped_ids=("S0", "S1"))
    destination = str(tmp_path / "cap" / "KGEG_cap.tif")
    record = INSETS.TnmCloudOptimizedGeoTiffStrategy().fetch(
        _definition(served, "OPRCAP", prefetch_whole_max_bytes="1"),
        BOX, 1.0, destination)
    assert record["sources_stripped"] == 2
    assert record["sources_prefetched_whole"] == 0
    assert "prefetch_whole_max_bytes threshold" in (
        record["prefetch_whole_skipped"])
    assert served.whole_gets("S0") == [] and served.whole_gets("S1") == []
    # the inset is still delivered -- a threshold is not a refusal
    assert os.path.isfile(destination)


def test_the_provider_can_switch_the_prefetch_off(layout, tmp_path):
    served = layout(stripped_ids=("S0",))
    record = INSETS.TnmCloudOptimizedGeoTiffStrategy().fetch(
        _definition(served, "OPROFF", prefetch_whole_stripped="False"),
        BOX, 1.0, str(tmp_path / "off" / "KGEG_off.tif"))
    assert record["prefetch_whole_skipped"] == (
        "prefetch_whole_stripped=False")
    assert served.whole_gets("S0") == []


def test_download_zip_whole_rides_the_one_whole_file_downloader(monkeypatch,
                                                                tmp_path):
    """ONE whole-file downloader (#157/#158): the zip reader is
    :func:`download_whole` plus a zip validator, never a second
    streaming body."""
    seen = {}

    def _spy(definition, source, scratch_path, progress_label,
             validate=None):
        seen["validate"] = validate
        seen["label"] = progress_label
        with open(scratch_path, "wb") as handle:
            handle.write(b"not a zip")
        return True

    monkeypatch.setattr(INSETS, "download_whole", _spy)
    scratch = str(tmp_path / "a.zip")
    assert INSETS.download_zip_whole(
        {"code": "Z"}, {"source_id": "T", "download_url": "u"},
        scratch, None, "label") is True
    assert seen["label"] == "label"
    assert "not a zip" in seen["validate"](scratch).lower() or \
        "zip" in seen["validate"](scratch).lower()


def test_usgsopr_elv_declares_the_prefetch():
    """The shipped provider carries the keys the measurement asked for."""
    definition = INSETS.initialize_elevation_providers_dict()["USGSOPR"]
    assert INSETS.provider_fetch_slots(definition) == 8
    assert INSETS._parse_float(
        definition["prefetch_whole_max_bytes"]) == pytest.approx(3.0e9)
