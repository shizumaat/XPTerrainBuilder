"""Offline land witness: does a lon/lat geometry hold land? (#1731)

Reads only base elevation files already on disk (``<tile>.tif``, the
Viewfinder ``<tile>.hgt``, or the configured base source's 90 m cache
file) — never a download, except through :func:`fetch_elevation`, which
the extract chooser calls when a verdict is unknown: it fetches the base
file the tile build downloads anyway, only earlier (#2234).  A cell the world mask
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
    for path in _elevation_paths(lat, lon):
        if not path or not os.path.isfile(path):
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


def _base_cache_path(lat: int, lon: int) -> Optional[str]:
    """The configured base source's whole-cell cache file (90 m tier,
    what ``elevation_level`` auto builds read), or ``None``."""
    try:
        import O4_Airport_Elevation_Insets as PROVIDERS

        definition = PROVIDERS.resolve_base_definition(
            lat, lon, DEM.base_elevation_source, prefer_coarse=True)
        strategy = PROVIDERS.ACCESS_STRATEGIES.get(
            (definition or {}).get("access_strategy"))
        cache_path_of = getattr(strategy(), "tile_cache_path", None) \
            if strategy else None
        return cache_path_of(definition, lat, lon) if cache_path_of else None
    except Exception:
        return None


def _elevation_paths(lat: int, lon: int) -> tuple:
    return (FNAMES.generic_tif(lat, lon), FNAMES.viewfinderpanorama(lat, lon),
            _base_cache_path(lat, lon))


def _cells(bounding_box):
    """Integer (lat, lon) cells a ``(lat_min, lon_min, lat_max, lon_max)``
    box touches."""
    (lat_min, lon_min, lat_max, lon_max) = bounding_box
    return [(lat, lon)
            for lat in range(math.floor(lat_min), math.ceil(lat_max))
            for lon in range(math.floor(lon_min), math.ceil(lon_max))]


def fetch_elevation(bounding_box) -> bool:
    """Download the configured base elevation of every LAND cell the box
    touches whose witness verdict is unknown (#2234: on a first build the
    elevation arrives after the OSM step).  The same file the tile build
    fetches for its own cell and 3x3 neighbourhood, fetched earlier.
    True when a fetch made a cell readable."""
    fetched = False
    for (lat, lon) in _cells(bounding_box):
        if not DEM.tile_is_land(lat, lon) or \
                _land_posts(lat, lon) is not None:
            continue
        try:
            DEM.ensure_elevation(DEM.base_elevation_source, lat, lon,
                                 verbose=False, prefer_coarse=True)
        except Exception:
            continue
        _land_posts.cache_clear()
        fetched = fetched or _land_posts(lat, lon) is not None
    return fetched


def land_points(geometry):
    """(lons, lats) of every sampled land post inside ``geometry``, or
    ``None`` when any cell it touches has no readable elevation."""
    try:
        import shapely

        if geometry.is_empty:
            return (numpy.empty(0), numpy.empty(0))
        (lon_min, lat_min, lon_max, lat_max) = geometry.bounds
        shapely.prepare(geometry)
        (all_lons, all_lats) = ([], [])
        for lat in range(math.floor(lat_min), math.ceil(lat_max)):
            for lon in range(math.floor(lon_min), math.ceil(lon_max)):
                posts = _land_posts(lat, lon)
                if posts is None:
                    return None
                (lons, lats) = posts
                if lons.size:
                    inside = shapely.contains_xy(geometry, lons, lats)
                    all_lons.append(lons[inside])
                    all_lats.append(lats[inside])
        if not all_lons:
            return (numpy.empty(0), numpy.empty(0))
        return (numpy.concatenate(all_lons), numpy.concatenate(all_lats))
    except Exception:
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
