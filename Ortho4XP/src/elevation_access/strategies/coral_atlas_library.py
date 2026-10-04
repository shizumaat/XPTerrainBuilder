"""Locally downloaded Allen Coral Atlas packages as a provider.

The ``coral_atlas_library`` access strategy (:class:`CoralAtlasLibraryStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import os

from elevation_access.definitions import _coverage_bbox_intersects
from elevation_access.gdal_support import has_gdal
from elevation_access.registry import register_access_strategy

__all__ = [
    "CoralAtlasLibraryStrategy",
]


@register_access_strategy("coral_atlas_library")
class CoralAtlasLibraryStrategy:
    """Locally downloaded Allen Coral Atlas packages as a provider.

    The Atlas's 10 m reef bathymetry is account-gated (free), so it is
    served from the user-populated library under
    ``Elevation_data/AllenCoralAtlas/`` instead of a live URL — see
    ``O4_Coral_Atlas`` for the library, the unit conversion (positive
    centimetres -> negative metres) and the guided in-app fetch.
    Discovery consults only the local index: a tile has coverage exactly
    when the user has downloaded a package that overlaps it.
    """

    supports_wide_area = True

    def discover(self, definition, bounding_box_wgs84):
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        import O4_Coral_Atlas as CORAL

        return CORAL.entries_intersecting(bounding_box_wgs84) or None

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
        import O4_Coral_Atlas as CORAL

        if not CORAL.fetch_window_to_geotiff(
            sources,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
        ):
            return None
        return {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_urls": sources,
            "source_ids": [os.path.basename(s) for s in sources],
            "project_titles": ["Allen Coral Atlas bathymetry"],
            "publication_date": "",
            "license": definition.get("license"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "datum_note": (
                "Satellite-derived depths below the sea surface;"
                " converted from positive centimetres to negative metres."
            ),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            # Every other strategy stamps what the SOURCE publishes
            # beside what the warp targeted; without it a manifest
            # reader has only the target and calls a 1 m lidar cut
            # coarse (the 2026-08-15 N32W098 class), and a
            # manifest-side pixel tolerance cannot be computed at
            # all (measured 2026-09-17: 229 usgs3dep manifests).
            "native_resolution_m": definition.get(
                "native_resolution_m"),
            "resolution_m": target_resolution_m,
        }
