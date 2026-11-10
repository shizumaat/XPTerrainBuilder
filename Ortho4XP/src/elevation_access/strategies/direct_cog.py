"""National models published as a few fixed Cloud-Optimized GeoTIFFs.

The ``direct_cog`` access strategy (:class:`DirectCogStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import os

from elevation_access.definitions import (
    _bounding_boxes_intersect,
    _coverage_bbox_intersects,
    _parse_bounding_box,
)
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.stac_assets import _stac_asset_href_to_vsicurl
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "COG_SOURCE_KEY",
    "DirectCogStrategy",
    "cog_sources",
]


#: The repeated ``.elv`` key of a FOOTPRINTED source (#1926):
#: ``cog_source=W,S,E,N|<url or GDAL virtual path>``, one line per raster.
#: A publisher of a few dozen regional blocks (the Norwegian Polar
#: Institute's S0 terrain-model zips) cannot be listed in ``cog_urls``:
#: every airport would open every block's header remotely.  With a
#: footprint per source only the blocks that touch the airport box are
#: read.  A raster whose data is several islands repeats its path on one
#: line per island (read once, at the first line touching the box).
#: Lines keep file order, and the warp lets LATER inputs win on overlap,
#: so a file lists the source it trusts most last.
COG_SOURCE_KEY = "cog_source"


def cog_sources(definition):
    """The ``(box, path)`` pairs of the definition's ``cog_source`` lines.

    Repeated lines arrive ``;``-joined (the reader's
    ``MULTI_VALUE_KEYS``).  A malformed line is skipped: one bad footprint
    must not widen a source to every airport.
    """
    pairs = []
    for record in str(definition.get(COG_SOURCE_KEY, "")).split(";"):
        if "|" not in record:
            continue
        (box_text, path) = record.split("|", 1)
        box = _parse_bounding_box(box_text.strip())
        if box is not None and path.strip():
            pairs.append((box, _stac_asset_href_to_vsicurl(path.strip())))
    return pairs


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

    def _vsicurl_inputs(self, definition, bounding_box_wgs84=None):
        """``cog_urls`` (read for every box), then the ``cog_source``
        rasters with a footprint touching ``bounding_box_wgs84``, each
        once, in the order of its first line touching the box."""
        inputs = [
            _stac_asset_href_to_vsicurl(url.strip())
            for url in str(definition.get("cog_urls", "")).split(",")
            if url.strip()
        ]
        for (box, path) in cog_sources(definition):
            if path not in inputs and (
                bounding_box_wgs84 is None
                or _bounding_boxes_intersect(box, bounding_box_wgs84)
            ):
                inputs.append(path)
        return inputs

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        inputs = self._vsicurl_inputs(definition, bounding_box_wgs84)
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
        inputs = self._vsicurl_inputs(definition, bounding_box_wgs84)
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
