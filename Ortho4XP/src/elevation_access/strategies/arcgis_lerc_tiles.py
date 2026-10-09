"""Tiles-only ArcGIS elevation services (LERC blobs in Web Mercator).

The ``arcgis_lerc_tiles`` access strategy (:class:`ArcgisLercTileStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import numpy
import os

from elevation_access.base import ProviderUnavailable
from elevation_access.capabilities import (
    lerc_decode_available,
    lerc_worker_argv,
)
from elevation_access.definitions import (
    _WEB_MERCATOR_HALF_CIRCUMFERENCE,
    _coverage_bbox_intersects,
    _parse_float,
    transform_bounding_box_to_epsg,
)
from elevation_access.failures import cap_exceeded_unavailable
from elevation_access.gdal_support import gdal, has_gdal, osr
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "ArcgisLercTileStrategy",
]


# =====================================================================
# Strategy 12: arcgis_lerc_tiles (tiles-only ArcGIS elevation services)
# =====================================================================
@register_access_strategy("arcgis_lerc_tiles")
class ArcgisLercTileStrategy:
    """Tiles-only ArcGIS elevation services (LERC blobs in Web Mercator).

    Some open city terrain models (Rio de Janeiro's lidar) are hosted
    as ArcGIS image services whose ``exportImage`` is disabled: the
    only data channel is a pre-rendered tile pyramid of single-band
    float LERC blobs on the STANDARD global Web Mercator grid, so a
    tile's (row, column) at a level are ordinary slippy-map
    coordinates.  Fetch computes the covering tiles at ``tile_level``,
    downloads the blobs, decodes them ALL in one subprocess (the
    imagecodecs LERC decoder and the osgeo libraries abort a shared
    process -- the same isolation the New Zealand provider uses),
    assembles an EPSG:3857 mosaic and warps it through the shared
    core.  Missing tiles (outside the service's data mask) are simply
    absent from the mosaic.
    """

    MAXIMUM_TILES_PER_MOSAIC = 1024

    # The blob decode is the SAME worker the New Zealand provider uses
    # (:func:`lerc_worker_argv`): every ``*.lerc`` in the blob directory
    # becomes a ``.npy`` beside it, invalid samples marked -32768.

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        return [{"template": definition.get("tile_url_template")}]

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        import shutil
        import subprocess

        import requests

        import O4_Console_Encoding
        import O4_UI_Utils

        if not has_gdal:
            return None
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        if not lerc_decode_available():
            # Asked BEFORE the pyramid is downloaded: without the codecs
            # every blob is unreadable, and the answer must be
            # "unavailable", never a durable no-coverage negative.
            raise ProviderUnavailable(
                "the LERC decoder is not available (tifffile/imagecodecs)"
            )
        level = int(float(definition.get("tile_level", 15)))
        # The pyramid grid: Web Mercator with the global origin by
        # default (Rio, Hong Kong, Zagreb); services caching in a
        # projected CRS (Estonia's EPSG:3301, Scotland's EPSG:27700)
        # declare tile_epsg / tile_origin_x / tile_origin_y /
        # tile_resolution (metres per pixel AT tile_level) instead.
        tile_epsg = int(float(definition.get("tile_epsg", 3857)))
        origin_x = _parse_float(
            definition.get("tile_origin_x"),
            -_WEB_MERCATOR_HALF_CIRCUMFERENCE,
        )
        origin_y = _parse_float(
            definition.get("tile_origin_y"),
            _WEB_MERCATOR_HALF_CIRCUMFERENCE,
        )
        resolution = _parse_float(
            definition.get("tile_resolution"),
            2.0
            * _WEB_MERCATOR_HALF_CIRCUMFERENCE
            / (2 ** level)
            / 256.0,
        )
        tile_span = resolution * 256.0
        (grid_x_min, grid_y_min, grid_x_max, grid_y_max) = (
            transform_bounding_box_to_epsg(bounding_box_wgs84, tile_epsg)
        )
        x_min = int((grid_x_min - origin_x) // tile_span)
        x_max = int((grid_x_max - origin_x) // tile_span)
        y_min = int((origin_y - grid_y_max) // tile_span)
        y_max = int((origin_y - grid_y_min) // tile_span)
        columns = x_max - x_min + 1
        rows = y_max - y_min + 1
        maximum_tiles = int(float(definition.get(
            "max_tiles_per_airport", self.MAXIMUM_TILES_PER_MOSAIC)))
        if columns * rows > maximum_tiles:
            # A cap is no coverage answer (spec us-holder-providers fact
            # 5): KTPA sits at ~924 of 1,024 tiles at level 17, and a
            # longer box past the cap used to record a DURABLE
            # no-coverage that no later run re-asked.
            raise cap_exceeded_unavailable(
                definition, "%d LERC tiles at level %d" % (columns * rows,
                                                          level),
                "%d tiles" % maximum_tiles, "max_tiles_per_airport",
                destination_path)
        template = definition["tile_url_template"]
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        blob_directory = destination_path + ".lercblobs"
        decoded_directory = destination_path + ".lercnpy"
        os.makedirs(blob_directory, exist_ok=True)
        os.makedirs(decoded_directory, exist_ok=True)
        session = requests.Session()
        fetched = []
        try:
            for tile_y in range(y_min, y_max + 1):
                for tile_x in range(x_min, x_max + 1):
                    url = (
                        template.replace("{level}", str(level))
                        .replace("{row}", str(tile_y))
                        .replace("{col}", str(tile_x))
                    )
                    try:
                        response = session.get(url, timeout=60)
                    except Exception:
                        continue
                    if (
                        response.status_code != 200
                        or not response.content
                    ):
                        continue
                    name = "%d_%d" % (tile_x, tile_y)
                    with open(
                        os.path.join(blob_directory, name + ".lerc"), "wb"
                    ) as handle:
                        handle.write(response.content)
                    fetched.append((tile_x, tile_y, name))
            if not fetched:
                return None
            completed = subprocess.run(
                lerc_worker_argv(blob_directory, decoded_directory),
                capture_output=True,
                **O4_Console_Encoding.child_console_pipe(),
                **O4_UI_Utils.external_tool_keyword_arguments(),
                timeout=600,
            )
            if completed.returncode != 0:
                # The blobs ARRIVED and we could not read them: our
                # decoder, not their coverage (owner RULINGS 2026-09-13b).
                raise ProviderUnavailable(
                    "the LERC tile decode failed: "
                    + (completed.stderr.strip()[-200:] or "decode failed")
                )
            values = numpy.full(
                (rows * 256, columns * 256), -32768.0, dtype=numpy.float32
            )
            decoded_any = False
            for (tile_x, tile_y, name) in fetched:
                npy_path = os.path.join(decoded_directory, name + ".npy")
                try:
                    tile_values = numpy.load(npy_path)
                except (OSError, ValueError):
                    continue
                if tile_values.shape != (256, 256):
                    continue
                row0 = (tile_y - y_min) * 256
                column0 = (tile_x - x_min) * 256
                values[row0 : row0 + 256, column0 : column0 + 256] = (
                    tile_values
                )
                decoded_any = True
            if not decoded_any:
                raise ProviderUnavailable(
                    "the LERC tile decode produced no readable tile"
                )
        finally:
            shutil.rmtree(blob_directory, ignore_errors=True)
            shutil.rmtree(decoded_directory, ignore_errors=True)
        mosaic_path = destination_path + ".mosaic.tif"
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(
            mosaic_path,
            values.shape[1],
            values.shape[0],
            1,
            gdal.GDT_Float32,
        )
        dataset.SetGeoTransform(
            (
                origin_x + x_min * tile_span,
                resolution,
                0.0,
                origin_y - y_min * tile_span,
                0.0,
                -resolution,
            )
        )
        spatial_reference = osr.SpatialReference()
        spatial_reference.ImportFromEPSG(tile_epsg)
        dataset.SetProjection(spatial_reference.ExportToWkt())
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(-32768.0)
        band.WriteArray(values)
        band.FlushCache()
        dataset = None
        warped = warp_vsicurl_sources_to_geotiff(
            [mosaic_path],
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=_raster_vertical_unit(definition),
            provider_code=definition.get("code"),
        )
        try:
            os.remove(mosaic_path)
        except OSError:
            pass
        if not warped:
            return None
        if not _geotiff_has_valid_data(destination_path):
            try:
                os.remove(destination_path)
            except OSError:
                pass
            return None
        return {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_urls": [definition.get("tile_url_template")],
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
        }
