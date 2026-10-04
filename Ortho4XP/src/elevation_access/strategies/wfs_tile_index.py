"""The ``wfs_tile_index`` access strategy (:class:`WfsTileIndexStrategy`).

Tile catalogs served over WFS whose features carry download URLs.

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import os

import O4_UI_Utils as UI

from elevation_access.definitions import _coverage_bbox_intersects
from elevation_access.discovery import (
    discovery_json_payload,
    raise_transient_discovery_failure,
)
from elevation_access.failures import cap_exceeded_unavailable
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.vertical_units import _raster_vertical_unit
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "WfsTileIndexStrategy",
]


# =====================================================================
def _rescale_wms_tile_url(url, definition, target_resolution_m):
    """Ask a WMS GetMap tile for the resolution the inset actually needs.

    Tile catalogs (IGN LiDAR HD) hand out ready-made GetMap URLs at native
    resolution — measured on data.geopf.fr: a 50 cm 1 km tile is 16 MB and
    ~8 s, dominated by server render latency, and the fetch pipeline then
    warps it DOWN to the inset target (3 m default) anyway.  The same
    render asked at 3 m is 0.45 MB and ~1.3 s.  Rewrite WIDTH/HEIGHT from
    the BBOX extent whenever the target is coarser than native; anything
    unexpected (missing params, geographic-degree bbox, upscale) keeps the
    original URL.
    """
    try:
        native = float(definition.get("native_resolution_m") or 0)
        target = float(target_resolution_m or 0)
        if target <= 0 or native <= 0 or target <= native:
            return url
        from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

        parts = urlsplit(url)
        params = parse_qs(parts.query, keep_blank_values=True)
        by_upper = {key.upper(): key for key in params}
        if not {"WIDTH", "HEIGHT", "BBOX"} <= set(by_upper):
            return url
        bbox = [float(v) for v in params[by_upper["BBOX"]][0].split(",")]
        if len(bbox) != 4:
            return url
        extent_x = abs(bbox[2] - bbox[0])
        extent_y = abs(bbox[3] - bbox[1])
        # Extents in metres, or nothing: a geographic-degree bbox would
        # compute a nonsense pixel count.
        if extent_x < 10 or extent_y < 10:
            return url
        width = max(1, int(round(extent_x / target)))
        height = max(1, int(round(extent_y / target)))
        if (width >= int(float(params[by_upper["WIDTH"]][0]))
                or height >= int(float(params[by_upper["HEIGHT"]][0]))):
            return url
        params[by_upper["WIDTH"]] = [str(width)]
        params[by_upper["HEIGHT"]] = [str(height)]
        return urlunsplit(parts._replace(
            query=urlencode(params, doseq=True)))
    except Exception:
        return url


# Strategy 8: wfs_tile_index (WFS tile catalog carrying download URLs)
# =====================================================================
@register_access_strategy("wfs_tile_index")
class WfsTileIndexStrategy:
    """Tile catalogs served over WFS whose features carry download URLs.

    France's LiDAR HD terrain model (IGN Geoplateforme) indexes its
    1 km tiles as WFS features whose ``url`` property is a ready-made
    GeoTIFF request: discovery is one anonymous WFS GetFeature bbox
    query, fetch downloads each returned tile (they are dynamically
    rendered, so no range reads) to temporary files and warps them
    through the shared core.  Coverage grows as the national lidar
    campaign progresses; an empty feature set is an honest no-coverage.
    """

    MAXIMUM_TILES_PER_FETCH = 120

    def _feature_query_url(self, definition, bounding_box_wgs84):
        (west, south, east, north) = bounding_box_wgs84
        return (
            definition["wfs_service_url"]
            + ("&" if "?" in definition["wfs_service_url"] else "?")
            + "SERVICE=WFS&REQUEST=GetFeature&VERSION=2.0.0&TYPENAMES="
            + definition["wfs_type_name"]
            + "&outputFormat=application/json&count="
            + str(self.MAXIMUM_TILES_PER_FETCH)
            # WFS 2.0 with the urn CRS is latitude-first.
            + "&bbox=%s,%s,%s,%s,urn:ogc:def:crs:EPSG::4326"
            % (repr(south), repr(west), repr(north), repr(east))
        )

    def discover(self, definition, bounding_box_wgs84):
        import requests

        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        url_property = definition.get("url_property", "url")
        # Spec SQ3: an outage on the tile-index query is not an answer
        # about coverage -- it raises transient rather than recording a
        # durable no-coverage negative for this provider/airport.
        try:
            response = requests.get(
                self._feature_query_url(definition, bounding_box_wgs84),
                timeout=60,
            )
        except Exception as error:
            raise_transient_discovery_failure(
                "WFS tile-index query", error
            )
        payload = discovery_json_payload(response, "WFS tile-index query")
        if payload is None:
            return None
        features = payload.get("features") or []
        # ``count=`` caps the server's answer: a listing it TRUNCATED
        # (WFS 2.0 ``numberMatched`` above what came back) is not the
        # whole coverage and is never delivered as if it were.
        matched = payload.get("numberMatched")
        if isinstance(matched, int) and matched > len(features):
            raise cap_exceeded_unavailable(
                definition, "%d tiles (the WFS returned %d)"
                % (matched, len(features)),
                "%d tiles" % self.MAXIMUM_TILES_PER_FETCH,
                "MAXIMUM_TILES_PER_FETCH")
        sources = []
        for feature in features:
            properties = feature.get("properties") or {}
            tile_url = properties.get(url_property)
            if tile_url:
                sources.append(
                    {
                        "url": tile_url,
                        "name": properties.get("name", ""),
                    }
                )
        return sources or None

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
        sources = self.discover(definition, bounding_box_wgs84)
        if not sources:
            return None
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        temporary_paths = []
        for (number, entry) in enumerate(sources):
            temporary_path = destination_path + ".tile%d.tif" % number
            try:
                response = requests.get(
                    _rescale_wms_tile_url(
                        entry["url"], definition, target_resolution_m),
                    timeout=300)
                if response.status_code != 200:
                    continue
                with open(temporary_path, "wb") as handle:
                    handle.write(response.content)
                temporary_paths.append(temporary_path)
            except Exception as error:
                UI.vprint(
                    1,
                    "   WARNING: could not download elevation tile",
                    entry.get("name") or entry["url"][:80],
                    ":",
                    str(error),
                )
        warped = bool(temporary_paths) and warp_vsicurl_sources_to_geotiff(
            temporary_paths,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=_raster_vertical_unit(definition),
            provider_code=definition.get("code"),
        )
        for temporary_path in temporary_paths:
            try:
                os.remove(temporary_path)
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
            "source_urls": [entry["name"] or entry["url"] for entry in sources],
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
