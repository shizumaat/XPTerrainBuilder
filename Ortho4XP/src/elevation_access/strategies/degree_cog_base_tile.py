"""A whole base tile cut from Cloud-Optimized GeoTIFFs named by degree cell.

The ``degree_cog_base_tile`` access strategy
(:class:`DegreeCogBaseTileStrategy`): the base-tier reading of the same
buckets ``degree_named_cog`` reads for airport insets (Copernicus GLO-30
and GLO-90 on AWS Open Data).  It exists for the base-tile FALLBACK
(``elevation_access.base_fallback``, issue #561).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import os

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable
from elevation_access.base_tiles import (
    base_definition_covers_tile,
    cached_elevation_file_is_valid,
)
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.strategies.degree_named_cog import DegreeNamedCogStrategy
from elevation_access.warp import (
    _geotiff_has_valid_data,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "BASE_TILE_POSTS",
    "DegreeCogBaseTileStrategy",
    "fill_far_edges_from_next_post",
]

#: Posts per side of the tile this strategy writes: the 1 arc-second
#: whole-degree grid of an ``.hgt`` tile, both edges included, which is
#: what ``O4_DEM_Utils.build_combined_raster`` assembles.
BASE_TILE_POSTS = 3601

_NODATA = -32768.0


def fill_far_edges_from_next_post(values, nodata=_NODATA):
    """Fill void posts of the SOUTH row and EAST column from the post
    beside them, in place; how many posts were filled.

    A degree-named cell holds its north row and west column; the south
    row and east column are the neighbouring cells' (their north row,
    their west column).  Where a neighbour is not published -- open sea,
    or a cell the publisher withholds -- the warp leaves those posts
    void, and the next post inward (one post away) stands in.
    """
    filled = 0
    south_void = values[-1, :] == nodata
    if south_void.any():
        values[-1, south_void] = values[-2, south_void]
        filled += int(south_void.sum())
    east_void = values[:, -1] == nodata
    if east_void.any():
        values[east_void, -1] = values[east_void, -2]
        filled += int(east_void.sum())
    return filled


@register_access_strategy("degree_cog_base_tile")
class DegreeCogBaseTileStrategy:
    """One 3601-post base tile from a degree-named COG and the three
    neighbours that hold its south row and east column.

    The tile is written as a float32 GeoTIFF whose pixel CENTRES are the
    whole-degree arc-second posts, at a cache path keyed by the
    definition's CODE -- never at another source's path.
    """

    def covers(self, definition, lat, lon):
        return base_definition_covers_tile(definition, lat, lon)

    def tile_cache_path(self, definition, lat, lon):
        return "%s_%s.tif" % (FNAMES.base_file_name(lat, lon),
                              definition["code"])

    def _sources(self, definition, lat, lon):
        """``/vsicurl/`` inputs, the cell itself LAST (later inputs win),
        or ``None`` when the cell is not published."""
        cells = DegreeNamedCogStrategy()
        url = cells._cell_url(definition, lat, lon)
        if not cells._url_exists(url):
            return None
        east = (lon + 1 + 180) % 360 - 180
        sources = []
        for (lat0, lon0) in ((lat - 1, east), (lat - 1, lon), (lat, east)):
            if lat0 < -90:
                continue
            neighbour = cells._cell_url(definition, lat0, lon0)
            if cells._url_exists(neighbour):
                sources.append("/vsicurl/" + neighbour)
        return sources + ["/vsicurl/" + url]

    def ensure_tile(self, definition, lat, lon, verbose=True):
        cache_path = self.tile_cache_path(definition, lat, lon)
        if cached_elevation_file_is_valid(cache_path):
            UI.vprint(2, "   Recycling ", cache_path)
            return 1
        if not has_gdal:
            raise ProviderUnavailable(
                "%s needs GDAL to cut a base tile, and this engine has "
                "none" % definition.get("code"))
        sources = self._sources(definition, lat, lon)
        if not sources:
            return 0
        UI.vprint(1, "    Downloading ", cache_path, "from",
                  str(definition.get("display_name") or definition["code"])
                  + ".")
        half_post = 0.5 / (BASE_TILE_POSTS - 1)
        scratch_path = cache_path + ".part"
        reasons = []
        try:
            if not warp_vsicurl_sources_to_geotiff(
                sources,
                (lon - half_post, lat - half_post,
                 lon + 1 + half_post, lat + 1 + half_post),
                # Unread: ``output_size`` fixes the grid.
                30.0,
                scratch_path,
                provider_code=definition.get("code"),
                failure_reasons=reasons,
                output_size=(BASE_TILE_POSTS, BASE_TILE_POSTS),
            ):
                raise ProviderUnavailable(
                    "%s: the base tile could not be cut (%s)"
                    % (definition.get("code"),
                       "; ".join(reasons) or "no reason given"))
            dataset = gdal.Open(scratch_path, gdal.GA_Update)
            band = dataset.GetRasterBand(1)
            values = band.ReadAsArray()
            if fill_far_edges_from_next_post(values):
                band.WriteArray(values)
                band.FlushCache()
            dataset = None
            if not _geotiff_has_valid_data(scratch_path):
                return 0
            os.replace(scratch_path, cache_path)
        finally:
            if os.path.exists(scratch_path):
                os.remove(scratch_path)
        return 1
