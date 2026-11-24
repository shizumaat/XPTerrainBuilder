"""A WCS 2.0 coverage read by plain ``subset=`` requests.

The ``wcs_subset`` access strategy (:class:`WcsSubsetStrategy`): for a
server GDAL's WCS driver cannot open.  EMODnet's coverage is labelled
``Lat Long``; the driver's open failed there with "InvalidSubsetting:
Empty intersection" (HTTP 404), while a GetCoverage naming each axis by
its label answers (#2265).  The definition names the labels
(``wcs_lon_axis``, ``wcs_lat_axis``), so no axis order is guessed.

Any answer that is not a GeoTIFF is a TRANSIENT failure: the box is inside
the provider's declared coverage, so a refusal says nothing about data.
"""
import datetime
import os
import urllib.parse

from elevation_access.base import TransientFetchError
from elevation_access.definitions import (
    _coverage_bbox_intersects,
    _parse_float,
)
from elevation_access.fetch_slots import (
    _held_provider_fetch_slot,
    provider_fetch_slots,
)
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = ["WcsSubsetStrategy"]

REQUEST_TIMEOUT_SECONDS = 120
METRES_PER_DEGREE = 111320.0
#: Source pixels read beyond the box, so the warp's bilinear kernel has
#: data at the cell edge.
PAD_PIXELS = 2


def request_url(definition, bounding_box_wgs84) -> str:
    """The GetCoverage URL for the padded box."""
    (west, south, east, north) = bounding_box_wgs84
    native_m = _parse_float(definition.get("native_resolution_m"), 100.0)
    pad = PAD_PIXELS * native_m / METRES_PER_DEGREE
    lon_axis = definition.get("wcs_lon_axis", "Long")
    lat_axis = definition.get("wcs_lat_axis", "Lat")
    query = [
        ("service", "WCS"),
        ("version", str(definition.get("wcs_version", "2.0.1"))),
        ("request", "GetCoverage"),
        ("coverageId", definition["wcs_coverage"]),
        ("format", "image/tiff"),
        ("subset", "%s(%.6f,%.6f)" % (lon_axis, west - pad, east + pad)),
        ("subset", "%s(%.6f,%.6f)" % (lat_axis, south - pad, north + pad)),
    ]
    return (definition["wcs_service_url"] + "?"
            + urllib.parse.urlencode(query, safe="(),"))


def _download(url: str, scratch_path: str) -> None:
    """The GeoTIFF answer at ``scratch_path``, or a transient failure."""
    import requests

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        raise TransientFetchError("WCS request failed: %s" % error) from error
    if response.status_code != 200 or not response.content[:4].startswith(
            (b"II*\x00", b"MM\x00*")):
        raise TransientFetchError(
            "WCS answered HTTP %d without a GeoTIFF" % response.status_code)
    with open(scratch_path, "wb") as handle:
        handle.write(response.content)


@register_access_strategy("wcs_subset")
class WcsSubsetStrategy:
    """GetCoverage by axis label, then the shared warp."""

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        return [{"url": request_url(definition, bounding_box_wgs84)}]

    def fetch(self, definition, bounding_box_wgs84, target_resolution_m,
              destination_path):
        if not has_gdal or not _coverage_bbox_intersects(
                definition, bounding_box_wgs84):
            return None
        url = request_url(definition, bounding_box_wgs84)
        scratch_path = destination_path + ".getcoverage.tif"
        try:
            with _held_provider_fetch_slot(
                    definition.get("code"), provider_fetch_slots(definition)):
                _download(url, scratch_path)
            if not warp_vsicurl_sources_to_geotiff(
                    [scratch_path], bounding_box_wgs84, target_resolution_m,
                    destination_path,
                    value_floor_m=float(
                        definition.get("value_floor_m", -600.0)),
                    vertical_unit=_raster_vertical_unit(definition),
                    provider_code=definition.get("code")):
                return None
        finally:
            if os.path.exists(scratch_path):
                os.remove(scratch_path)
        if not _geotiff_has_valid_data(destination_path):
            os.remove(destination_path)
            return None
        return {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_urls": [url],
            "wcs_coverage": definition.get("wcs_coverage"),
            "native_resolution_m": definition.get("native_resolution_m"),
            "license": definition.get("license"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            "resolution_m": target_resolution_m,
        }
