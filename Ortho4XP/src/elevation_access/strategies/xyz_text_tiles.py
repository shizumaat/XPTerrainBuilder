"""Slippy-map elevation tiles carrying comma-separated metre values.

The ``xyz_text_tiles`` access strategy (:class:`XyzTextTileStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import numpy
import os

import O4_UI_Utils as UI

from elevation_access.definitions import (
    _WEB_MERCATOR_HALF_CIRCUMFERENCE,
    _coverage_bbox_intersects,
)
from elevation_access.gdal_support import gdal, has_gdal, osr
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "XyzTextTileStrategy",
]


# =====================================================================
# Strategy 5: xyz_text_tiles (slippy-map elevation text tiles -> warp)
# =====================================================================


def _slippy_tile_of(latitude, longitude, zoom):
    """The (x, y) slippy-map tile containing a WGS84 point at ``zoom``."""
    import math

    n = 2 ** zoom
    x = int((longitude + 180.0) / 360.0 * n)
    latitude_radians = math.radians(latitude)
    y = int(
        (
            1.0
            - math.log(
                math.tan(latitude_radians) + 1.0 / math.cos(latitude_radians)
            )
            / math.pi
        )
        / 2.0
        * n
    )
    return (min(max(x, 0), n - 1), min(max(y, 0), n - 1))


@register_access_strategy("xyz_text_tiles")
class XyzTextTileStrategy:
    """Slippy-map elevation tiles carrying comma-separated metre values.

    Japan's Geospatial Information Authority publishes its national
    elevation model this way and ONLY this way (no GeoTIFF, WCS or
    STAC anywhere in its stack): anonymous 256x256 text tiles in Web
    Mercator, one elevation per cell, the letter ``e`` for nodata.
    Fetch computes the covering tiles at ``tile_zoom``, assembles them
    into an EPSG:3857 mosaic, and (when any primary tile is missing --
    the 5 m lidar is not wall-to-wall) underlays a second mosaic from
    ``fallback_url_template`` at ``fallback_zoom``, the server-side
    priority-merged nationwide composite.  Both land as temporary
    GeoTIFFs beside the destination and go through the same warp core
    as every other strategy (mosaic order makes the primary win where
    it has data).
    """

    MAXIMUM_TILES_PER_MOSAIC = 4096

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        return [{"template": definition.get("tile_url_template")}]

    def _tile_range(self, bounding_box_wgs84, zoom):
        (west, south, east, north) = bounding_box_wgs84
        (x_min, y_min) = _slippy_tile_of(north, west, zoom)
        (x_max, y_max) = _slippy_tile_of(south, east, zoom)
        return (x_min, y_min, x_max, y_max)

    def _mosaic_to_geotiff(
        self, session, template, zoom, bounding_box_wgs84, temporary_path
    ):
        """Fetch all covering tiles at ``zoom`` into one local GeoTIFF.

        Returns ``(path, missing_tile_count)`` or ``(None, 0)`` when
        nothing at all was retrieved (outside the dataset).
        """
        (x_min, y_min, x_max, y_max) = self._tile_range(
            bounding_box_wgs84, zoom
        )
        columns = x_max - x_min + 1
        rows = y_max - y_min + 1
        if columns * rows > self.MAXIMUM_TILES_PER_MOSAIC:
            UI.vprint(
                1,
                "   WARNING: elevation tile mosaic of",
                columns * rows,
                "tiles exceeds the cap - skipping this source.",
            )
            return (None, 0)
        values = numpy.full(
            (rows * 256, columns * 256), -32768.0, dtype=numpy.float32
        )
        fetched = 0
        missing = 0
        for tile_y in range(y_min, y_max + 1):
            for tile_x in range(x_min, x_max + 1):
                url = (
                    template.replace("{zoom}", str(zoom))
                    .replace("{x}", str(tile_x))
                    .replace("{y}", str(tile_y))
                )
                try:
                    response = session.get(url, timeout=60)
                except Exception:
                    missing += 1
                    continue
                if response.status_code != 200:
                    missing += 1
                    continue
                try:
                    tile_values = numpy.array(
                        [
                            [
                                -32768.0 if token == "e" else float(token)
                                for token in line.split(",")
                            ]
                            for line in response.text.strip().split("\n")
                        ],
                        dtype=numpy.float32,
                    )
                    if tile_values.shape != (256, 256):
                        raise ValueError(str(tile_values.shape))
                except Exception:
                    missing += 1
                    continue
                row0 = (tile_y - y_min) * 256
                column0 = (tile_x - x_min) * 256
                values[row0 : row0 + 256, column0 : column0 + 256] = (
                    tile_values
                )
                fetched += 1
        if not fetched:
            return (None, missing)
        tile_size_m = 2.0 * _WEB_MERCATOR_HALF_CIRCUMFERENCE / (2 ** zoom)
        origin_x = x_min * tile_size_m - _WEB_MERCATOR_HALF_CIRCUMFERENCE
        origin_y = _WEB_MERCATOR_HALF_CIRCUMFERENCE - y_min * tile_size_m
        pixel_m = tile_size_m / 256.0
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(
            temporary_path,
            values.shape[1],
            values.shape[0],
            1,
            gdal.GDT_Float32,
        )
        dataset.SetGeoTransform(
            (origin_x, pixel_m, 0.0, origin_y, 0.0, -pixel_m)
        )
        spatial_reference = osr.SpatialReference()
        spatial_reference.ImportFromEPSG(3857)
        dataset.SetProjection(spatial_reference.ExportToWkt())
        band = dataset.GetRasterBand(1)
        band.SetNoDataValue(-32768.0)
        band.WriteArray(values)
        band.FlushCache()
        dataset = None
        return (temporary_path, missing)

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        import requests

        if not has_gdal:
            return None
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        session = requests.Session()
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        primary_zoom = int(float(definition.get("tile_zoom", 15)))
        (primary_path, missing) = self._mosaic_to_geotiff(
            session,
            definition["tile_url_template"],
            primary_zoom,
            bounding_box_wgs84,
            destination_path + ".primary.tif",
        )
        fallback_path = None
        fallback_template = definition.get("fallback_url_template")
        if fallback_template and (primary_path is None or missing):
            (fallback_path, _fallback_missing) = self._mosaic_to_geotiff(
                session,
                fallback_template,
                int(float(definition.get("fallback_zoom", 14))),
                bounding_box_wgs84,
                destination_path + ".fallback.tif",
            )
        # Later inputs win where they carry data: the primary (finer)
        # mosaic overlays the fallback composite.
        warp_inputs = [
            path for path in (fallback_path, primary_path) if path
        ]
        warped = bool(warp_inputs) and warp_vsicurl_sources_to_geotiff(
            warp_inputs,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=_raster_vertical_unit(definition),
            provider_code=definition.get("code"),
        )
        for path in (primary_path, fallback_path):
            if path:
                try:
                    os.remove(path)
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
