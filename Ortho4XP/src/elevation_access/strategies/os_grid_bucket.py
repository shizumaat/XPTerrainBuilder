"""Anonymous S3 buckets of Ordnance-Survey-grid-named GeoTIFFs.

The ``os_grid_bucket`` access strategy (:class:`OsGridBucketStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import json
import os

import O4_UI_Utils as UI

from elevation_access.gdal_support import osr
from elevation_access.registry import register_access_strategy
from elevation_access.strategies.geojson_tile_index import (
    GeojsonTileIndexStrategy,
)

__all__ = [
    "OsGridBucketStrategy",
]


# =====================================================================
# Strategy 13: os_grid_bucket (S3 buckets of OS-grid-named GeoTIFFs)
# =====================================================================
_OS_GRID_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"  # no I, the OS way


def _ordnance_survey_square_extent(square_name):
    """The (x0, y0, x1, y1) EPSG:27700 extent of an OS grid square name.

    Handles the three forms in Scotland's lidar bucket: two letters +
    two digits (10 km, ``NS16``), the same + a quadrant (5 km,
    ``NS16NE``), and two letters + four digits (1 km, ``NR5712``).
    Returns ``None`` for anything else.
    """
    name = square_name.upper()
    if (
        len(name) < 4
        or name[0] not in _OS_GRID_LETTERS
        or name[1] not in _OS_GRID_LETTERS
    ):
        return None
    first = _OS_GRID_LETTERS.index(name[0])
    second = _OS_GRID_LETTERS.index(name[1])
    easting_100km = ((first - 2) % 5) * 500000 + (second % 5) * 100000
    northing_100km = (19 - (first // 5) * 5) * 100000 - (
        second // 5
    ) * 100000
    rest = name[2:]
    if len(rest) == 4 and rest.isdigit():
        x0 = easting_100km + int(rest[:2]) * 1000
        y0 = northing_100km + int(rest[2:]) * 1000
        return (x0, y0, x0 + 1000, y0 + 1000)
    if len(rest) >= 2 and rest[:2].isdigit():
        x0 = easting_100km + int(rest[0]) * 10000
        y0 = northing_100km + int(rest[1]) * 10000
        quadrant = rest[2:4]
        if quadrant in ("NE", "NW", "SE", "SW"):
            if quadrant[1] == "E":
                x0 += 5000
            if quadrant[0] == "N":
                y0 += 5000
            return (x0, y0, x0 + 5000, y0 + 5000)
        if not rest[2:]:
            return (x0, y0, x0 + 10000, y0 + 10000)
    return None


@register_access_strategy("os_grid_bucket")
class OsGridBucketStrategy(GeojsonTileIndexStrategy):
    """Anonymous S3 buckets of Ordnance-Survey-grid-named GeoTIFFs.

    Scotland's Remote Sensing Portal bucket lays its lidar campaigns
    out as ``lidar/<campaign>/dtm/27700/gridded/<OSSQUARE>_<RES>_...tif``
    -- the square name IS the footprint, so the index is built by
    paginating the bucket listings once, computing each name's extent
    arithmetically, and caching ``(bounding_box, url, resolution)``
    exactly like the GeoJSON-catalog strategy this extends (discover
    and fetch are inherited).  Overlapping campaigns are ordered
    coarse-first so the warp's later-wins mosaic keeps the finest data.
    """

    def _tile_entries(self, definition):
        import re
        import urllib.parse

        import requests

        try:
            with open(self.index_path(definition), "r") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            pass
        bucket_url = definition["bucket_url"].rstrip("/")
        wgs84 = osr.SpatialReference()
        wgs84.ImportFromEPSG(4326)
        wgs84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        projected = osr.SpatialReference()
        projected.ImportFromEPSG(27700)
        projected.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        to_wgs84 = osr.CoordinateTransformation(projected, wgs84)
        entries = []
        UI.vprint(
            1,
            "    Indexing the",
            definition["code"],
            "lidar bucket (once per install).",
        )
        for prefix in str(definition.get("bucket_prefixes", "")).split(","):
            prefix = prefix.strip()
            if not prefix:
                continue
            continuation = None
            while True:
                url = (
                    bucket_url
                    + "/?list-type=2&max-keys=1000&prefix="
                    + urllib.parse.quote(prefix)
                )
                if continuation:
                    url += "&continuation-token=" + urllib.parse.quote(
                        continuation
                    )
                try:
                    response = requests.get(url, timeout=120)
                except Exception as error:
                    UI.vprint(
                        1,
                        "   WARNING: bucket listing failed:",
                        str(error),
                    )
                    return entries or None
                if response.status_code != 200:
                    break
                keys = re.findall(r"<Key>([^<]+)</Key>", response.text)
                for key in keys:
                    if not key.lower().endswith(".tif"):
                        continue
                    base = os.path.basename(key)
                    square = base.split("_")[0]
                    extent = _ordnance_survey_square_extent(square)
                    if extent is None:
                        continue
                    (x0, y0, x1, y1) = extent
                    corners = [
                        to_wgs84.TransformPoint(x, y)
                        for (x, y) in (
                            (x0, y0),
                            (x0, y1),
                            (x1, y0),
                            (x1, y1),
                        )
                    ]
                    resolution = (
                        0.5 if "50CM" in base.upper() else 1.0
                    )
                    entries.append(
                        {
                            "bbox": [
                                min(c[0] for c in corners),
                                min(c[1] for c in corners),
                                max(c[0] for c in corners),
                                max(c[1] for c in corners),
                            ],
                            "url": bucket_url + "/" + key,
                            "resolution": resolution,
                        }
                    )
                token_match = re.search(
                    r"<NextContinuationToken>([^<]+)"
                    r"</NextContinuationToken>",
                    response.text,
                )
                if token_match:
                    continuation = token_match.group(1)
                else:
                    break
        if not entries:
            return None
        # Coarse first: the warp keeps the LAST valid sample, so the
        # finest campaign wins wherever several overlap.
        entries.sort(key=lambda entry: -entry["resolution"])
        os.makedirs(
            os.path.dirname(self.index_path(definition)), exist_ok=True
        )
        with open(self.index_path(definition), "w", newline="\n") as handle:
            json.dump(entries, handle)
        return entries
