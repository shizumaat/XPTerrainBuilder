"""Every access strategy, one module each, named for its registry key.

THE FREEZER LINE: a strategy registers itself when its module is
imported, and the frozen app carries only modules something imports
statically.  This file is that one place -- every strategy module is
imported here by name.  A module missing from this list never registers,
and its providers silently fall back to the base tier
(``tests/test_elevation_access_registry.py`` fails first).
"""

from elevation_access.strategies import (  # noqa: F401  (import registers)
    aoi_zip_download,
    arcgis_export_image,
    arcgis_feature_tiles,
    arcgis_lerc_tiles,
    authenticated_token_search,
    coordinate_named_url_list,
    coral_atlas_library,
    cwcb_lidar_api,
    degree_named_cog,
    direct_cog,
    geojson_tile_index,
    hgt_archive_drop,
    las_tile_index,
    manual_download,
    os_grid_bucket,
    stac,
    static_stac,
    tile_grid_http,
    tnm_cog,
    usgs_seamless,
    viewfinder_zip,
    wcs,
    wcs_kvp,
    wfs_tile_index,
    xyz_archive_drop,
    xyz_text_tiles,
)

__all__ = [
    "aoi_zip_download",
    "arcgis_export_image",
    "arcgis_feature_tiles",
    "arcgis_lerc_tiles",
    "authenticated_token_search",
    "coordinate_named_url_list",
    "coral_atlas_library",
    "cwcb_lidar_api",
    "degree_named_cog",
    "direct_cog",
    "geojson_tile_index",
    "hgt_archive_drop",
    "las_tile_index",
    "manual_download",
    "os_grid_bucket",
    "stac",
    "static_stac",
    "tile_grid_http",
    "tnm_cog",
    "usgs_seamless",
    "viewfinder_zip",
    "wcs",
    "wcs_kvp",
    "wfs_tile_index",
    "xyz_archive_drop",
    "xyz_text_tiles",
]
