"""Sources whose direct downloads are dead upstream (SRTM, ALOS).

The ``manual_download`` access strategy (:class:`ManualDownloadStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base_tiles import (
    base_definition_covers_tile,
    cached_elevation_file_is_valid,
)
from elevation_access.registry import register_access_strategy

__all__ = [
    "ManualDownloadStrategy",
]


@register_access_strategy("manual_download")
class ManualDownloadStrategy:
    """Sources whose direct downloads are dead upstream (SRTM, ALOS).

    The legacy code half-supports a manual workflow: a user places the
    file at the legacy cache path by hand and the build recycles it;
    otherwise one warning line and the source yields nothing.
    """

    def covers(self, definition, lat, lon):
        return base_definition_covers_tile(definition, lat, lon)

    def download_url(self, definition, lat, lon):
        return None

    def tile_cache_path(self, definition, lat, lon):
        return FNAMES.elevation_data(
            definition["legacy_keyword"], lat, lon
        )

    def ensure_tile(self, definition, lat, lon, verbose=True):
        cache_path = self.tile_cache_path(definition, lat, lon)
        if cached_elevation_file_is_valid(cache_path):
            UI.vprint(2, "   Recycling ", cache_path)
            return 1
        UI.vprint(
            1,
            "    WARNING : This elevation source has no longer direct downloads !"
        )
        return 0
