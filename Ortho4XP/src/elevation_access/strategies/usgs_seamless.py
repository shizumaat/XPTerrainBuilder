"""USGS national elevation dataset staged GeoTIFF products.

The ``usgs_seamless`` access strategy (:class:`UsgsSeamlessStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import os

import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base_tiles import (
    base_definition_covers_tile,
    cached_elevation_file_is_valid,
)
from elevation_access.registry import register_access_strategy

__all__ = [
    "UsgsSeamlessStrategy",
    "usgs_seamless_tile_identifier",
]


def usgs_seamless_tile_identifier(lat, lon):
    """The USGS staged-products tile identifier, e.g. ``n37w087``.

    Exact transliteration of the legacy construction, INCLUDING its
    operator-precedence quirk on the third line: for ``lon >= 0`` the
    conditional expression evaluates to just ``"e"``, discarding the
    north/south prefix.  The USGS national elevation datasets live at
    western longitudes so the quirk was never reachable in practice; it
    is preserved verbatim because this refactor is behaviour-preserving
    (the compatibility tests pin the western-hemisphere URLs).
    """
    tile_identifier = "n" if lat >= 0 else "s"
    tile_identifier = tile_identifier + str(abs(lat + 1)).zfill(2)
    tile_identifier = tile_identifier + "w" if lon < 0 else "e"
    tile_identifier = tile_identifier + str(abs(lon)).zfill(3)
    return tile_identifier


@register_access_strategy("usgs_seamless")
class UsgsSeamlessStrategy:
    """USGS national elevation dataset staged GeoTIFF products.

    The existing ``prd-tnm .../StagedProducts/Elevation/{1,13}/TIFF/
    current/`` whole-tile URL scheme, downloading to the legacy
    ``FNAMES.elevation_data`` cache path.
    """

    def covers(self, definition, lat, lon):
        return base_definition_covers_tile(definition, lat, lon)

    def download_url(self, definition, lat, lon):
        return (
            definition["download_url_template"]
            .replace("{dataset}", str(definition.get("usgs_dataset", "1")))
            .replace(
                "{tile_identifier}", usgs_seamless_tile_identifier(lat, lon)
            )
        )

    def tile_cache_path(self, definition, lat, lon):
        return FNAMES.elevation_data(
            definition["legacy_keyword"], lat, lon
        )

    def ensure_tile(self, definition, lat, lon, verbose=True):
        cache_path = self.tile_cache_path(definition, lat, lon)
        if cached_elevation_file_is_valid(cache_path):
            UI.vprint(2, "   Recycling ", cache_path)
            return 1
        UI.vprint(1, "    Downloading ", cache_path, "from USGS.")
        url = self.download_url(definition, lat, lon)
        response = DEM.http_request(
            url, definition.get("legacy_keyword", definition["code"]), verbose
        )
        if not response:
            return 0
        if not os.path.isdir(os.path.dirname(cache_path)):
            os.makedirs(os.path.dirname(cache_path))
        with open(cache_path, "wb") as out:
            try:
                out.write(response.content)
            except Exception:
                return 0
        return 1
