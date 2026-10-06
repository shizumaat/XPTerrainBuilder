"""Chunked ``exportImage`` against an ArcGIS ImageServer with no tile cache.

The ``arcgis_export_image`` access strategy (:class:`ArcgisExportImageStrategy`).

Chunked ``exportImage`` against an ArcGIS ImageServer with no tile cache
(Oregon DOGAMI, Hillsborough County's native 2.5 ft DEM).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import json
import math
import numpy
import os

import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.capabilities import (
    lerc_decode_available,
    lerc_worker_argv,
)
from elevation_access.definitions import (
    _coverage_bbox_intersects,
    _parse_float,
    export_image_definition_refusal,
    transform_bounding_box_to_epsg,
)
from elevation_access.discovery import (
    discovery_status_is_transient,
    raise_transient_discovery_failure,
)
from elevation_access.failures import (
    cap_exceeded_unavailable,
    error_message_indicates_transient_network_failure,
)
from elevation_access.gdal_support import gdal, has_gdal, osr
from elevation_access.las_tiles import (
    LAS_PROGRESS_INTERVAL_S,
    _las_progress_line,
)
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "ArcgisExportImageStrategy",
    "EXPORT_IMAGE_ESTIMATED_BYTES_PER_PX",
    "EXPORT_IMAGE_MAX_BYTES_PER_AIRPORT_DEFAULT",
    "EXPORT_IMAGE_MAX_REQUEST_PX_DEFAULT",
    "EXPORT_IMAGE_RETRY_DELAY_S",
    "EXPORT_IMAGE_TRANSIENT_ATTEMPTS",
    "export_image_chunk_grid",
    "verify_export_image_chunk",
]


# =====================================================================
# Strategy 10b: arcgis_export_image (chunked ArcGIS ImageServer
# exportImage; spec us-holder-providers §3.4, RULINGS 2026-09-30bm)
# =====================================================================
#: The per-request pixel ceiling when the .elv names none.  DOGAMI's
#: ImageServer refuses a request above ~8 Mpx (scout hold154c, #154); one
#: inset box needs ~76 Mpx, so the box is ALWAYS chunked.
EXPORT_IMAGE_MAX_REQUEST_PX_DEFAULT = 6000000


#: The per-airport byte cap when the .elv names none (spec §3.4).
EXPORT_IMAGE_MAX_BYTES_PER_AIRPORT_DEFAULT = 400 * 1000 * 1000


#: The cap is judged BEFORE the first GET on the uncompressed size -- an
#: exportImage has no HEAD -- one float32 sample per requested pixel.
EXPORT_IMAGE_ESTIMATED_BYTES_PER_PX = 4


#: In-run retries of ONE chunk on a 30t transient before the run gives
#: up (and raises transient: no durable record).
EXPORT_IMAGE_TRANSIENT_ATTEMPTS = 3


#: Seconds between those retries.
EXPORT_IMAGE_RETRY_DELAY_S = 5.0


#: Fragments of an ArcGIS error body that mean the REQUEST was too big:
#: the chunker produced it, so it is our defect -- never a transient that
#: retries forever, never a no-coverage.  (Measured 2026-09-30 on the
#: Hillsborough native service: a 3000x4200 request answers HTTP 200,
#: ``Content-Type: image/tiff``, body ``{"error":{"code":400,...,
#: "details":["The requested image exceeds the size limit."]}}``.)
_EXPORT_IMAGE_OVERSIZE_FRAGMENTS = ("exceeds the size limit",
                                    "size limit", "too large")


_TIFF_MAGIC = (b"II*\x00", b"MM\x00*")


def export_image_chunk_grid(width, height, max_request_px,
                            max_width_px=None, max_height_px=None):
    """Split a ``width`` x ``height`` request into the FEWEST chunks that
    each hold at most ``max_request_px`` pixels and respect the service's
    per-side limits.  Returns ``[(column0, row0, chunk_width,
    chunk_height), ...]`` row-major, covering the grid exactly once.

    The search walks the column count up from the fewest the width limit
    allows; per column count the chunk is as tall as the pixel budget
    lets it be, and the first (fewest-columns) minimum wins -- so a box
    with no side limit is cut into full-width strips (a 76 Mpx box at 6
    Mpx is 13 chunks, the floor of ``ceil(76/6)``)."""
    width = int(width)
    height = int(height)
    max_request_px = int(max_request_px)
    if width < 1 or height < 1:
        return []
    if max_request_px < 1:
        raise ValueError("max_request_px must be >= 1")
    side_w = int(max_width_px) if max_width_px else width
    side_h = int(max_height_px) if max_height_px else height
    side_w = max(1, min(side_w, width, max_request_px))
    side_h = max(1, min(side_h, height))
    best = None
    columns = -(-width // side_w)
    while columns <= width:
        chunk_w = -(-width // columns)
        chunk_h = min(side_h, max_request_px // chunk_w, height)
        if chunk_h >= 1:
            rows = -(-height // chunk_h)
            count = columns * rows
            if best is None or count < best[0]:
                best = (count, columns, rows)
        if best is not None and columns >= best[0]:
            break
        columns += 1
    (_count, columns, rows) = best
    chunk_w = -(-width // columns)
    chunk_h = -(-height // rows)
    chunks = []
    for row in range(rows):
        row0 = row * chunk_h
        if row0 >= height:
            break
        for column in range(columns):
            column0 = column * chunk_w
            if column0 >= width:
                break
            chunks.append((column0, row0, min(chunk_w, width - column0),
                           min(chunk_h, height - row0)))
    return chunks


def _source_linear_unit_m(source_epsg):
    """Metres per HORIZONTAL unit of ``source_epsg`` (0.3048 for a foot
    State Plane, 1200/3937 for a US-survey-foot one, 1.0 for UTM)."""
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(int(source_epsg))
    units = float(srs.GetLinearUnits() or 1.0)
    return units if units > 0 else 1.0


@register_access_strategy("arcgis_export_image")
class ArcgisExportImageStrategy:
    """Chunked ``exportImage`` against an ArcGIS ImageServer with no tile
    cache (Oregon DOGAMI, Hillsborough County's native 2.5 ft DEM).

    The padded airport box is laid on a grid in ``source_epsg`` (metric
    or feet-projected; the request pixel is ``native_resolution_m``, never
    finer than the inset target -- the ``wcs_kvp`` rule), split by
    :func:`export_image_chunk_grid` into chunks of at most
    ``max_request_px`` (and the service's ``max_request_width_px`` /
    ``max_request_height_px``), and every chunk is ONE GET with
    ``noData=<nodata>``.  Each chunk is verified (a TIFF, the requested
    size, the nodata tag equal to the declared nodata) BEFORE it may enter
    the mosaic; a VRT over the chunks goes through the shared warp with
    the provider's ``vertical_unit``.

    Classes (30t): a cap exceeded -> :class:`ProviderUnavailable` before
    any byte moves; 5xx / 429 / a transport failure / a non-TIFF body ->
    retried in-run, then :class:`TransientFetchError`; an oversize answer
    -> :class:`ProviderUnavailable` naming the chunker (a BUG, never a
    transient); a 4xx -> :class:`ProviderUnavailable`; every chunk all
    nodata -> ``None`` (the one durable no-coverage).
    """

    PAD_M = 60.0

    def request_grid(self, definition, bounding_box_wgs84,
                     target_resolution_m=None):
        """``(x_min, y_max, pixel, width, height, epsg)`` of the request
        grid in source units: the padded box snapped outward to whole
        pixels."""
        source_epsg = int(float(definition.get("source_epsg")))
        unit_m = _source_linear_unit_m(source_epsg)
        native = _parse_float(definition.get("native_resolution_m"), 1.0)
        pixel_m = native
        target = _parse_float(target_resolution_m, 0.0)
        if target and target > native:
            pixel_m = target
        pixel = pixel_m / unit_m
        pad = self.PAD_M / unit_m
        (x_min, y_min, x_max, y_max) = transform_bounding_box_to_epsg(
            bounding_box_wgs84, source_epsg)
        x_min = math.floor((x_min - pad) / pixel) * pixel
        y_min = math.floor((y_min - pad) / pixel) * pixel
        x_max = math.ceil((x_max + pad) / pixel) * pixel
        y_max = math.ceil((y_max + pad) / pixel) * pixel
        width = max(1, int(round((x_max - x_min) / pixel)))
        height = max(1, int(round((y_max - y_min) / pixel)))
        return (x_min, y_max, pixel, width, height, source_epsg)

    def chunks(self, definition, grid):
        (_x_min, _y_max, _pixel, width, height, _epsg) = grid
        return export_image_chunk_grid(
            width, height,
            int(float(definition.get("max_request_px",
                                     EXPORT_IMAGE_MAX_REQUEST_PX_DEFAULT))),
            _parse_float(definition.get("max_request_width_px"), None),
            _parse_float(definition.get("max_request_height_px"), None))

    def chunk_url(self, definition, grid, chunk):
        """The exportImage URL of one chunk."""
        from urllib.parse import quote

        (x_min, y_max, pixel, _width, _height, epsg) = grid
        (column0, row0, chunk_w, chunk_h) = chunk
        left = x_min + column0 * pixel
        top = y_max - row0 * pixel
        right = left + chunk_w * pixel
        bottom = top - chunk_h * pixel
        base = str(definition["export_url"]).strip().rstrip("/")
        if not base.lower().endswith("/exportimage"):
            base += "/exportImage"
        export_format = str(definition.get("export_format", "tiff")).strip()
        parameters = [
            ("bbox", "%.4f,%.4f,%.4f,%.4f" % (left, bottom, right, top)),
            ("bboxSR", str(epsg)),
            ("imageSR", str(epsg)),
            ("size", "%d,%d" % (chunk_w, chunk_h)),
            ("format", export_format),
            ("pixelType", "F32"),
            ("noData", str(definition["nodata"]).strip()),
            ("noDataInterpretation", "esriNoDataMatchAny"),
            ("interpolation", "RSP_BilinearInterpolation"),
        ]
        if export_format == "tiff":
            # Lossless DEFLATE-family body (LZW on the wire, ~25 % fewer
            # bytes than an uncompressed body, read by every GDAL).
            parameters.append(("compression", "LZ77"))
        else:
            parameters.append(("compressionTolerance", str(
                definition["lerc_max_error"]).strip()))
        rule = definition.get("rendering_rule")
        if rule is not None and str(rule).strip():
            # The JSON is sent COMPACT and percent-encoded whole (the .elv
            # parser keeps it verbatim: no '#', and '=' is re-joined).
            parameters.append(("renderingRule", json.dumps(
                json.loads(str(rule)), separators=(",", ":"))))
        parameters.append(("f", "image"))
        return base + "?" + "&".join(
            "%s=%s" % (key, quote(value, safe=",.-_"))
            for (key, value) in parameters)

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        return [{"url": str(definition.get("export_url"))}]

    # -----------------------------------------------------------------
    def _get_chunk(self, session, definition, url, path, label,
                   expected_px):
        """Stream one chunk into ``path``; returns the bytes moved.
        Raises per the class table above."""
        import time as _time

        code = definition.get("code") or "elevation provider"
        last_reason = None
        for attempt in range(1, EXPORT_IMAGE_TRANSIENT_ATTEMPTS + 1):
            if UI.red_flag:
                raise TransientFetchError(
                    "%s exportImage stopped with the build" % code)
            try:
                response = session.get(url, timeout=300, stream=True)
            except Exception as error:
                if not error_message_indicates_transient_network_failure(
                        error):
                    raise ProviderUnavailable(
                        "%s: exportImage request failed (%s)"
                        % (code, error)) from error
                last_reason = str(error)
                _time.sleep(EXPORT_IMAGE_RETRY_DELAY_S)
                continue
            status = int(getattr(response, "status_code", 200))
            if discovery_status_is_transient(status):
                body = _response_head_text(response)
                if _export_image_oversize(body):
                    raise _export_image_oversize_error(code, expected_px,
                                                       body)
                last_reason = "HTTP %d" % status
                _time.sleep(EXPORT_IMAGE_RETRY_DELAY_S)
                continue
            if not 200 <= status < 300:
                body = _response_head_text(response)
                if _export_image_oversize(body):
                    raise _export_image_oversize_error(code, expected_px,
                                                       body)
                raise ProviderUnavailable(
                    "%s: exportImage answered HTTP %d (%s)"
                    % (code, status, body[:160]))
            moved = 0
            started = _time.monotonic()
            last_line = started
            head = b""
            try:
                with open(path, "wb") as handle:
                    for block in response.iter_content(1 << 20):
                        if not block:
                            continue
                        if len(head) < 512:
                            head += block[:512 - len(head)]
                        handle.write(block)
                        moved += len(block)
                        now = _time.monotonic()
                        if now - last_line >= LAS_PROGRESS_INTERVAL_S:
                            last_line = now
                            UI.vprint(1, _las_progress_line(
                                label, moved, 0, moved, now - started))
            except Exception as error:
                if not error_message_indicates_transient_network_failure(
                        error):
                    raise ProviderUnavailable(
                        "%s: exportImage body read failed (%s)"
                        % (code, error)) from error
                last_reason = str(error)
                _time.sleep(EXPORT_IMAGE_RETRY_DELAY_S)
                continue
            text = head.decode("latin-1", "replace")
            if _export_image_oversize(text):
                raise _export_image_oversize_error(code, expected_px, text)
            export_format = str(definition.get("export_format",
                                               "tiff")).strip()
            if export_format == "tiff" and not head.startswith(_TIFF_MAGIC):
                # An error envelope or a maintenance page inside a 200 is
                # an outage artefact, never a coverage answer (SQ3).
                last_reason = "a 200 body that is not a TIFF (%r)" % (
                    text[:120],)
                _time.sleep(EXPORT_IMAGE_RETRY_DELAY_S)
                continue
            if export_format == "lerc" and head.lstrip().startswith(b"{"):
                last_reason = "a 200 body that is not LERC (%r)" % (
                    text[:120],)
                _time.sleep(EXPORT_IMAGE_RETRY_DELAY_S)
                continue
            UI.vprint(1, _las_progress_line(
                label, moved, moved, moved, _time.monotonic() - started,
                done=True))
            return moved
        raise_transient_discovery_failure(
            "%s exportImage chunk" % code,
            "%s after %d attempts" % (last_reason,
                                      EXPORT_IMAGE_TRANSIENT_ATTEMPTS))

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        import shutil
        import time as _time

        import requests

        if not has_gdal:
            return None
        refusal = export_image_definition_refusal(definition)
        if refusal:
            raise ProviderUnavailable(refusal)
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        code = definition.get("code") or "elevation provider"
        export_format = str(definition.get("export_format", "tiff")).strip()
        if export_format == "lerc" and not lerc_decode_available():
            raise ProviderUnavailable(
                "the LERC decoder is not available (tifffile/imagecodecs)")
        vertical_unit = _raster_vertical_unit(definition)
        nodata = float(str(definition["nodata"]).strip())
        grid = self.request_grid(definition, bounding_box_wgs84,
                                 target_resolution_m)
        (x_min, y_max, pixel, width, height, epsg) = grid
        chunks = self.chunks(definition, grid)
        estimated = width * height * EXPORT_IMAGE_ESTIMATED_BYTES_PER_PX
        maximum_bytes = int(float(definition.get(
            "max_bytes_per_airport",
            EXPORT_IMAGE_MAX_BYTES_PER_AIRPORT_DEFAULT)))
        if estimated > maximum_bytes:
            raise cap_exceeded_unavailable(
                definition,
                "%d chunks / %.0f MB (%d x %d px)" % (
                    len(chunks), estimated / 1e6, width, height),
                "%.0f MB" % (maximum_bytes / 1e6), "max_bytes_per_airport",
                destination_path)
        airport = os.path.basename(str(destination_path)).split("_", 1)[0]
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        scratch = destination_path + ".exportchunks"
        shutil.rmtree(scratch, ignore_errors=True)
        os.makedirs(scratch, exist_ok=True)
        UI.vprint(1, "   [inset] %s %s exportImage: %d x %d px in %d "
                  "chunk(s), <= %.0f MB" % (airport, code, width, height,
                                           len(chunks), estimated / 1e6))
        session = requests.Session()
        bytes_fetched = 0
        chunk_paths = []
        chunk_report = []
        started = _time.monotonic()
        try:
            for (index, chunk) in enumerate(chunks):
                url = self.chunk_url(definition, grid, chunk)
                suffix = ".tif" if export_format == "tiff" else ".lercimg"
                raw_path = os.path.join(scratch, "chunk%04d%s" % (index,
                                                                   suffix))
                label = "%s %s chunk %d/%d (%d x %d px)" % (
                    airport, code, index + 1, len(chunks), chunk[2],
                    chunk[3])
                bytes_fetched += self._get_chunk(
                    session, definition, url, raw_path, label,
                    chunk[2] * chunk[3])
                chunk_paths.append((chunk, raw_path))
            if export_format == "lerc":
                chunk_paths = self._decode_lerc_chunks(
                    definition, grid, chunk_paths, scratch, nodata)
            valid_total = 0
            tiff_paths = []
            for (chunk, path) in chunk_paths:
                valid = verify_export_image_chunk(
                    path, chunk[2], chunk[3], nodata, code)
                chunk_report.append({"chunk": list(chunk), "valid": valid})
                valid_total += valid
                tiff_paths.append(path)
            if valid_total == 0:
                # Every chunk answered, well-formed, all nodata: the ONE
                # durable no-coverage this strategy writes.
                return None
            vrt_path = os.path.join(scratch, "chunks.vrt")
            vrt = gdal.BuildVRT(vrt_path, tiff_paths,
                                options=gdal.BuildVRTOptions(
                                    srcNodata=nodata, VRTNodata=nodata))
            if vrt is None:
                raise ProviderUnavailable(
                    "%s: could not assemble the exportImage chunks" % code)
            vrt = None
            warped = warp_vsicurl_sources_to_geotiff(
                [vrt_path],
                bounding_box_wgs84,
                target_resolution_m,
                destination_path,
                source_nodata=nodata,
                value_floor_m=float(definition.get("value_floor_m", -600.0)),
                vertical_unit=vertical_unit,
                provider_code=code,
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        if not warped:
            return None
        if not _geotiff_has_valid_data(destination_path):
            try:
                os.remove(destination_path)
            except OSError:
                pass
            return None
        rule = definition.get("rendering_rule")
        provenance = {
            "provider": code,
            "access_strategy": definition.get("access_strategy"),
            "source_urls": [self.chunk_url(definition, grid, chunk)
                            for chunk in chunks],
            "native_resolution_m": definition.get("native_resolution_m"),
            "license": definition.get("license"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "datum_note": (
                "Elevations are in the source vertical datum; lidar is "
                "treated as truth and is NOT shifted toward the base DEM."
            ),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            "resolution_m": target_resolution_m,
            "export_format": export_format,
            "request_grid": {
                "epsg": epsg, "pixel": pixel, "width_px": width,
                "height_px": height, "x_min": x_min, "y_max": y_max,
            },
            "request_count": len(chunks),
            "bytes_fetched": bytes_fetched,
            "bytes_estimated": estimated,
            "fetch_seconds": round(_time.monotonic() - started, 1),
            "chunk_valid_px": [entry["valid"] for entry in chunk_report],
        }
        if rule is not None and str(rule).strip():
            provenance["rendering_rule"] = json.loads(str(rule))
            # The unit conversion happened SERVER-side; the shared warp
            # stamps the cells metres (``vertical_unit=m``).
            provenance["vertical_unit_source"] = "rendering_rule"
        return provenance

    def _decode_lerc_chunks(self, definition, grid, chunk_paths, scratch,
                            nodata):
        """LERC chunk blobs -> georeferenced GeoTIFFs (the shared decode
        worker, out of process: :func:`lerc_worker_argv`)."""
        import subprocess

        import O4_Console_Encoding

        code = definition.get("code") or "elevation provider"
        decoded = os.path.join(scratch, "decoded")
        os.makedirs(decoded, exist_ok=True)
        completed = subprocess.run(
            lerc_worker_argv(scratch, decoded),
            capture_output=True, timeout=600,
            **O4_Console_Encoding.child_console_pipe())
        if completed.returncode != 0:
            raise ProviderUnavailable(
                "the LERC chunk decode failed: "
                + (completed.stderr.strip()[-200:] or "decode failed"))
        (x_min, y_max, pixel, _w, _h, epsg) = grid
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(int(epsg))
        out = []
        for (chunk, raw_path) in chunk_paths:
            name = os.path.basename(raw_path)[: -len(".lercimg")]
            try:
                values = numpy.load(os.path.join(decoded, name + ".npy"))
            except (OSError, ValueError) as error:
                raise ProviderUnavailable(
                    "%s: LERC chunk %s did not decode (%s)"
                    % (code, name, error)) from error
            (column0, row0, chunk_w, chunk_h) = chunk
            if values.shape != (chunk_h, chunk_w):
                raise ProviderUnavailable(
                    "%s: LERC chunk %s is %r, asked %dx%d"
                    % (code, name, values.shape, chunk_w, chunk_h))
            values = values.astype(numpy.float32)
            values[values == numpy.float32(-32768.0)] = nodata
            path = os.path.join(scratch, name + ".tif")
            dataset = gdal.GetDriverByName("GTiff").Create(
                path, chunk_w, chunk_h, 1, gdal.GDT_Float32)
            dataset.SetGeoTransform((x_min + column0 * pixel, pixel, 0.0,
                                     y_max - row0 * pixel, 0.0, -pixel))
            dataset.SetProjection(srs.ExportToWkt())
            band = dataset.GetRasterBand(1)
            band.SetNoDataValue(nodata)
            band.WriteArray(values)
            dataset = None
            out.append((chunk, path))
        return out


def _response_head_text(response):
    try:
        return str(response.text or "")[:2000]
    except Exception:
        return ""


def _export_image_oversize(text):
    lowered = str(text or "").lower()
    return any(fragment in lowered
               for fragment in _EXPORT_IMAGE_OVERSIZE_FRAGMENTS)


def _export_image_oversize_error(code, expected_px, body):
    return ProviderUnavailable(
        "%s: the service refused a %d px exportImage chunk as oversize - "
        "a CHUNKER BUG (max_request_px / max_request_width_px / "
        "max_request_height_px in %s.elv exceed the service), never a "
        "transient: %s" % (code, expected_px, code, str(body)[:160]))


def verify_export_image_chunk(path, width, height, nodata, code):
    """Verify one exportImage chunk; returns its valid-pixel count.

    A chunk is admitted only when it is a raster of exactly the requested
    size whose band nodata TAG equals the declared ``nodata`` (#155: the
    empty-noData answer carries NO tag and reads 0.0 -- that chunk is
    refused here, never mosaicked as sea level).  Valid cells outside the
    shared sanitizer's plausible range are reported (the warp voids them)."""
    try:
        dataset = gdal.Open(path)
    except Exception as error:
        raise ProviderUnavailable(
            "%s: exportImage chunk unreadable (%s)" % (code, error)
        ) from error
    if dataset is None:
        raise ProviderUnavailable("%s: exportImage chunk unreadable" % code)
    if (dataset.RasterXSize, dataset.RasterYSize) != (int(width),
                                                      int(height)):
        raise ProviderUnavailable(
            "%s: exportImage chunk is %dx%d, asked %dx%d - refused"
            % (code, dataset.RasterXSize, dataset.RasterYSize, width,
               height))
    band = dataset.GetRasterBand(1)
    tag = band.GetNoDataValue()
    if tag is None or not numpy.isclose(float(tag), float(nodata)):
        raise ProviderUnavailable(
            "%s: exportImage chunk carries nodata tag %r, declared %r - "
            "refused (an untagged answer reads 0.0 where the service has "
            "no data, #155)" % (code, tag, nodata))
    values = band.ReadAsArray()
    dataset = None
    if values is None:
        raise ProviderUnavailable("%s: exportImage chunk empty" % code)
    valid = numpy.isfinite(values) & ~numpy.isclose(values, float(nodata))
    return int(valid.sum())
