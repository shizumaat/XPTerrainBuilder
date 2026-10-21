"""GetCoverage by explicit key-value URL for quirky WCS servers.

The ``wcs_kvp`` access strategy (:class:`WcsKvpStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import numpy
import os

import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable
from elevation_access.definitions import (
    _coverage_bbox_intersects,
    _parse_float,
    export_image_definition_refusal,
    transform_bounding_box_to_epsg,
)
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "WcsKvpStrategy",
]


# =====================================================================
# Strategy 10: wcs_kvp (hand-built GetCoverage for non-standard WCS)
# =====================================================================
@register_access_strategy("wcs_kvp")
class WcsKvpStrategy:
    """GetCoverage by explicit key-value URL for quirky WCS servers.

    Some INSPIRE deployments defeat GDAL's WCS driver (Hesse's
    advertises octet-stream as its native format and the driver's
    negotiation returns empty rasters), yet answer a plain KVP
    GetCoverage perfectly.  The definition spells the WHOLE request
    out as ``wcs_getcoverage_template`` with ``{xmin}/{ymin}/{xmax}/
    {ymax}`` placeholders in ``source_epsg`` coordinates; fetch pads
    the airport box, downloads the returned GeoTIFF and warps it
    through the shared core.
    """

    PAD_M = 60.0

    def _request_url(self, definition, bounding_box_wgs84,
                     target_resolution_m=None):
        """The first (for an untiled definition, the only) request."""
        return self._request_urls(definition, bounding_box_wgs84,
                                  target_resolution_m)[0]

    def _request_urls(self, definition, bounding_box_wgs84,
                      target_resolution_m=None):
        """The padded box as one request, or -- when the definition
        declares the server's ``max_request_pixels`` -- as a grid of
        requests each within that size at the requested pixel (#1217:
        a WMS GetMap above MaxWidth is refused, and capping one request
        would silently coarsen a large airport's inset)."""
        source_epsg = int(float(definition.get("source_epsg", 25832)))
        (x_min, y_min, x_max, y_max) = transform_bounding_box_to_epsg(
            bounding_box_wgs84, source_epsg
        )
        x_min, y_min = x_min - self.PAD_M, y_min - self.PAD_M
        x_max, y_max = x_max + self.PAD_M, y_max + self.PAD_M
        native = _parse_float(
            definition.get("native_resolution_m"), 1.0
        )
        # Never ask for finer pixels than the inset target: the fetch
        # core warps down to the target anyway, so requesting native
        # only inflates the server render and the transfer (the same
        # over-fetch the FRANCE50CM tiles had — measured ~6x slower).
        pixel_m = native
        target = _parse_float(target_resolution_m, 0.0)
        if target and target > native:
            pixel_m = target
        width = max(1, int(round((x_max - x_min) / pixel_m)))
        height = max(1, int(round((y_max - y_min) / pixel_m)))
        declared = _parse_float(definition.get("max_request_pixels"), 0.0)
        if not declared:
            # Legacy single request: ArcGIS exportImage caps at 8000 px.
            return [self._fill(definition, (x_min, y_min, x_max, y_max),
                               min(width, 8000), min(height, 8000))]
        limit = int(declared)
        columns = -(-width // limit)
        rows = -(-height // limit)
        urls = []
        for row in range(rows):
            for column in range(columns):
                pixels_x = min(limit, width - column * limit)
                pixels_y = min(limit, height - row * limit)
                left = x_min + column * limit * pixel_m
                bottom = y_min + row * limit * pixel_m
                urls.append(self._fill(
                    definition,
                    (left, bottom, left + pixels_x * pixel_m,
                     bottom + pixels_y * pixel_m),
                    pixels_x, pixels_y))
        return urls

    @staticmethod
    def _fill(definition, box, width, height):
        (x_min, y_min, x_max, y_max) = box
        return (
            definition["wcs_getcoverage_template"]
            .replace("{xmin}", repr(round(x_min, 2)))
            .replace("{ymin}", repr(round(y_min, 2)))
            .replace("{xmax}", repr(round(x_max, 2)))
            .replace("{ymax}", repr(round(y_max, 2)))
            # ArcGIS exportImage / WMS GetMap want an explicit pixel size.
            .replace("{width}", str(width))
            .replace("{height}", str(height))
            # #155: an ArcGIS exportImage template sends noData={nodata},
            # filled from the definition's own nodata key -- never empty.
            .replace("{nodata}", str(definition.get("nodata", "")).strip())
        )

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        return [{"url": url} for url in
                self._request_urls(definition, bounding_box_wgs84)]

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        if not has_gdal:
            return None
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        refusal = export_image_definition_refusal(definition)
        if refusal:
            raise ProviderUnavailable(refusal)
        urls = self._request_urls(definition, bounding_box_wgs84,
                                  target_resolution_m=target_resolution_m)
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        scratch_paths = []
        try:
            for index, url in enumerate(urls):
                scratch_path = "%s.getcoverage%d.tif" % (
                    destination_path, index)
                if not self._download(definition, url, scratch_path):
                    return None
                scratch_paths.append(scratch_path)
            return self._warp(definition, bounding_box_wgs84,
                              target_resolution_m, destination_path,
                              scratch_paths, urls)
        finally:
            for scratch_path in scratch_paths:
                try:
                    os.remove(scratch_path)
                except OSError:
                    pass

    @staticmethod
    def _download(definition, url, scratch_path):
        """One GeoTIFF answer written to ``scratch_path``, or ``None``."""
        import requests

        try:
            response = requests.get(url, timeout=300)
            if response.status_code != 200 or not response.content[
                :4
            ].startswith((b"II*\x00", b"MM\x00*")):
                return None
            with open(scratch_path, "wb") as handle:
                handle.write(response.content)
        except Exception as error:
            UI.vprint(
                1, "   WARNING: WCS GetCoverage failed:", str(error)
            )
            return None
        if "exportimage" in url.lower():
            # #155: an exportImage answer must carry the declared nodata
            # TAG; an untagged body reads 0.0 (false sea level) where the
            # service has no data.  Refused before it can be warped.
            try:
                dataset = gdal.Open(scratch_path)
                band = dataset.GetRasterBand(1) if dataset else None
                tag = band.GetNoDataValue() if band is not None else None
                dataset = None
            except Exception:
                tag = None
            declared = _parse_float(definition.get("nodata"), None)
            if tag is None or declared is None or not numpy.isclose(
                    float(tag), float(declared)):
                try:
                    os.remove(scratch_path)
                except OSError:
                    pass
                raise ProviderUnavailable(
                    "%s: exportImage answer carries nodata tag %r, declared "
                    "%r - refused (an untagged answer reads 0.0 where the "
                    "service has no data, #155)"
                    % (definition.get("code"), tag, declared))
        return True

    @staticmethod
    def _warp(definition, bounding_box_wgs84, target_resolution_m,
              destination_path, scratch_paths, urls):
        warped = warp_vsicurl_sources_to_geotiff(
            scratch_paths,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=_raster_vertical_unit(definition),
            provider_code=definition.get("code"),
        )
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
            "source_urls": list(urls),
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
