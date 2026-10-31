"""Offline land witness: does a lon/lat geometry hold land? (#1731)

Reads only base elevation files already on disk (``<tile>.tif`` or the
Viewfinder ``<tile>.hgt``) — never a download.  A cell the world mask
calls ocean-only is sea without a read.  Answers ``True`` (a post above
sea level lies inside), ``False`` (every post inside is at or below sea
level), or ``None`` (a cell's elevation is not on disk or unreadable):
callers treat ``None`` as "may hold land".
"""

import math
import os
from functools import lru_cache
from typing import Optional

import numpy
import O4_DEM_Utils as DEM
import O4_File_Names as FNAMES

# Posts sampled every _STRIDE (about 90 m at 1" resolution): a speck of
# land smaller than that is not worth an Overpass fallback.
_STRIDE = 3


@lru_cache(maxsize=8)
def _land_posts(lat: int, lon: int):
    """(lons, lats) of the cell's above-sea-level posts; an empty pair
    for an ocean-only cell; ``None`` when no elevation is on disk."""
    if not DEM.tile_is_land(lat, lon):
        return (numpy.empty(0), numpy.empty(0))
    for path in (FNAMES.generic_tif(lat, lon),
                 FNAMES.viewfinderpanorama(lat, lon)):
        if not os.path.isfile(path):
            continue
        try:
            (epsg, x0, y0, x1, y1, nodata, nx, ny, alt) = \
                DEM.read_elevation_from_file(path, lat, lon)
        except Exception:
            return None
        if epsg != 4326 or alt is None:
            return None
        if x0 == 0 and y0 == 0 and x1 <= 1 and y1 <= 1:   # .hgt: relative
            (x0, x1, y0, y1) = (x0 + lon, x1 + lon, y0 + lat, y1 + lat)
        sub = alt[::_STRIDE, ::_STRIDE]
        rows, cols = numpy.nonzero((sub > 0) & (sub != nodata))
        lons = x0 + cols * _STRIDE * (x1 - x0) / (nx - 1)
        lats = y1 - rows * _STRIDE * (y1 - y0) / (ny - 1)
        return (lons, lats)
    return None


def holds_land(geometry) -> Optional[bool]:
    """True / False / None (unknown) for land inside ``geometry``."""
    try:
        import shapely

        if geometry.is_empty:
            return False
        (lon_min, lat_min, lon_max, lat_max) = geometry.bounds
        shapely.prepare(geometry)
        unknown = False
        for lat in range(math.floor(lat_min), math.ceil(lat_max)):
            for lon in range(math.floor(lon_min), math.ceil(lon_max)):
                posts = _land_posts(lat, lon)
                if posts is None:
                    unknown = True
                    continue
                (lons, lats) = posts
                if lons.size and shapely.contains_xy(
                        geometry, lons, lats).any():
                    return True
        return None if unknown else False
    except Exception:
        return None
