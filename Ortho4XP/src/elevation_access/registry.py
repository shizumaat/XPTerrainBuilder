"""The registry: ``access_strategy`` key of a ``.elv`` file -> strategy class.

The key is a STRING IN DATA FILES (every ``Providers/Elevation/*.elv``
names one), so a key is never renamed.  Strategies register themselves
with :func:`register_access_strategy` when their module is imported;
``elevation_access.strategies`` imports every strategy module.
"""

from typing import Dict, Tuple

__all__ = [
    "ACCESS_STRATEGIES",
    "EXPECTED_STRATEGIES",
    "register_access_strategy",
    "registry_selfcheck",
]

#: THE PINNED SET: every key that must be registered, and the class that
#: registers it.  The one hand-kept list -- the frozen engine's
#: ``--import-selfcheck`` and ``tests/test_elevation_access_registry.py``
#: both read it.  It is not derived from ``strategies/__init__.py``: a
#: line dropped from that import list would shrink a derived set with it
#: and the lost provider would pass unnoticed.  Recorded at main
#: ``01662c75``; a new strategy adds its line here.
EXPECTED_STRATEGIES: Dict[str, str] = {
    "aoi_zip_download": "AoiZipDownloadStrategy",
    "arcgis_export_image": "ArcgisExportImageStrategy",
    "arcgis_feature_tiles": "ArcgisFeatureTileStrategy",
    "arcgis_lerc_tiles": "ArcgisLercTileStrategy",
    "authenticated_token_search": "AuthenticatedTokenSearchStrategy",
    "coordinate_named_url_list": "CoordinateNamedUrlListStrategy",
    "coral_atlas_library": "CoralAtlasLibraryStrategy",
    "cwcb_lidar_api": "CwcbLidarApiStrategy",
    "degree_named_cog": "DegreeNamedCogStrategy",
    "direct_cog": "DirectCogStrategy",
    "geojson_tile_index": "GeojsonTileIndexStrategy",
    "hgt_archive_drop": "HgtArchiveDropStrategy",
    "las_tile_index": "LasTileIndexStrategy",
    "manual_download": "ManualDownloadStrategy",
    "os_grid_bucket": "OsGridBucketStrategy",
    "stac": "StacCloudOptimizedGeoTiffStrategy",
    "static_stac": "StaticStacCatalogStrategy",
    "tile_grid_http": "TileGridHttpStrategy",
    "tnm_cog": "TnmCloudOptimizedGeoTiffStrategy",
    "usgs_seamless": "UsgsSeamlessStrategy",
    "viewfinder_zip": "ViewfinderZipStrategy",
    "wcs": "WcsStrategy",
    "wcs_kvp": "WcsKvpStrategy",
    "wfs_tile_index": "WfsTileIndexStrategy",
    "xyz_archive_drop": "XyzArchiveDropStrategy",
    "xyz_text_tiles": "XyzTextTileStrategy",
}


# =====================================================================
# Access-strategy registry (the code seam; strategy-agnostic below)
# =====================================================================
ACCESS_STRATEGIES = {}


def register_access_strategy(name):
    """Class/callable decorator that adds an access strategy to the registry."""

    def _register(strategy):
        ACCESS_STRATEGIES[name] = strategy
        return strategy

    return _register


def registry_selfcheck() -> Tuple[bool, str]:
    """Is every pinned strategy registered, and nothing else?

    Imports the package (which registers the strategies) and compares
    the registry with :data:`EXPECTED_STRATEGIES`.  Returns ``(ok, line)``
    for ``--import-selfcheck``: the frozen binary counting its own
    providers.  No network, no data root -- an import and a dict read.
    """
    name = "elevation_access registry"
    try:
        import elevation_access  # noqa: F401  (registers the strategies)
    except Exception as error:
        return (False, "%s: %s: %s" % (name, type(error).__name__, error))
    found = {key: getattr(strategy, "__name__", repr(strategy))
             for (key, strategy) in ACCESS_STRATEGIES.items()}
    missing = sorted(set(EXPECTED_STRATEGIES) - set(found))
    unexpected = sorted(set(found) - set(EXPECTED_STRATEGIES))
    wrong_class = sorted(
        "%s=%s" % (key, found[key]) for key in EXPECTED_STRATEGIES
        if key in found and found[key] != EXPECTED_STRATEGIES[key])
    if not (missing or unexpected or wrong_class):
        return (True, "%s: ok %d keys" % (name, len(found)))
    parts = ["%d of %d keys" % (len(found), len(EXPECTED_STRATEGIES))]
    if missing:
        parts.append("missing " + ",".join(missing))
    if unexpected:
        parts.append("unexpected " + ",".join(unexpected))
    if wrong_class:
        parts.append("wrong class " + ",".join(wrong_class))
    return (False, "%s: FAIL %s" % (name, "; ".join(parts)))
