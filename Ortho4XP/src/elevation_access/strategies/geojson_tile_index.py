"""The ``geojson_tile_index`` access strategy (:class:`GeojsonTileIndexStrategy`).

One national GeoJSON tile catalog whose features carry file URLs.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import json
import os

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.definitions import (
    _bounding_boxes_intersect,
    _coverage_bbox_intersects,
    _geojson_geometry_bounding_box,
)
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "GeojsonTileIndexStrategy",
]


# =====================================================================
# Strategy 8: geojson_tile_index (one tile catalog file, direct URLs)
# =====================================================================


@register_access_strategy("geojson_tile_index")
class GeojsonTileIndexStrategy:
    """One national GeoJSON tile catalog whose features carry file URLs.

    Uruguay's national terrain model publishes exactly this: a single
    (few-megabyte) GeoJSON of ~6600 tile footprints in WGS84, each
    feature holding the direct GeoTIFF URL.  The catalog is fetched
    once, reduced to ``(bounding_box, url)`` pairs and cached in a
    per-provider index file; fetches then warp the intersecting tiles
    straight off the server through ``/vsicurl/`` (the host honours
    ranged reads).
    """

    # Windowed /vsicurl reader (inherited by os_grid_bucket): eligible for
    # whole-tile overlay fetches.
    supports_wide_area = True

    def index_path(self, definition):
        return os.path.join(
            FNAMES.Elevation_dir,
            definition["code"].lower() + "_geojson_tile_index.json",
        )

    def _tile_entries(self, definition):
        import requests

        try:
            with open(self.index_path(definition), "r") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            pass
        try:
            response = requests.get(definition["index_url"], timeout=180)
        except Exception as error:
            UI.vprint(
                1, "   WARNING: tile catalog request failed:", str(error)
            )
            return None
        if response.status_code != 200:
            return None
        try:
            features = response.json().get("features") or []
        except ValueError:
            return None
        url_property = definition.get("url_property", "url")
        entries = []
        for feature in features:
            url = (feature.get("properties") or {}).get(url_property)
            box = _geojson_geometry_bounding_box(feature.get("geometry"))
            if url and box:
                entries.append({"bbox": list(box), "url": url})
        if not entries:
            return None
        os.makedirs(
            os.path.dirname(self.index_path(definition)), exist_ok=True
        )
        with open(self.index_path(definition), "w", newline="\n") as handle:
            json.dump(entries, handle)
        return entries

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        entries = self._tile_entries(definition)
        if not entries:
            return None
        hits = [
            entry
            for entry in entries
            if _bounding_boxes_intersect(entry["bbox"], bounding_box_wgs84)
        ]
        return hits or None

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        if not has_gdal:
            return None
        sources = self.discover(definition, bounding_box_wgs84)
        if not sources:
            return None
        if not warp_vsicurl_sources_to_geotiff(
            ["/vsicurl/" + entry["url"] for entry in sources],
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
            "source_urls": [entry["url"] for entry in sources],
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
