"""The ``direct_cog`` access strategy (:class:`DirectCogStrategy`).

National models published as a few fixed Cloud-Optimized GeoTIFFs.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import os

from elevation_access.definitions import _coverage_bbox_intersects
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.stac_assets import _stac_asset_href_to_vsicurl
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "DirectCogStrategy",
]


# =====================================================================
# Strategy 6: direct_cog (fixed Cloud-Optimized GeoTIFF URLs -> warp)
# =====================================================================
@register_access_strategy("direct_cog")
class DirectCogStrategy:
    """National models published as a few fixed Cloud-Optimized GeoTIFFs.

    The simplest provider family of all: no discovery API, no tiling
    scheme -- the definition lists the COG URL(s) outright (Wales
    publishes its whole 1 m lidar terrain model as ONE country-wide
    Cloud-Optimized GeoTIFF on Azure blob storage) and the fetch is a
    windowed ``/vsicurl/`` read straight out of them, exactly the warp
    core every other strategy uses.  The same all-nodata post-warp
    check as the wcs strategy turns inside-the-box-but-outside-the-data
    airports into cached no-coverage negatives.
    """

    # Windowed /vsicurl reader: eligible for whole-tile overlay fetches.
    supports_wide_area = True

    def _vsicurl_inputs(self, definition):
        return [
            _stac_asset_href_to_vsicurl(url.strip())
            for url in str(definition.get("cog_urls", "")).split(",")
            if url.strip()
        ]

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        inputs = self._vsicurl_inputs(definition)
        return [{"source": path} for path in inputs] or None

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        if not has_gdal:
            return None
        inputs = self._vsicurl_inputs(definition)
        if not inputs:
            return None
        if not warp_vsicurl_sources_to_geotiff(
            inputs,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=_raster_vertical_unit(definition),
            provider_code=definition.get("code"),
        ):
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
            "source_urls": inputs,
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
