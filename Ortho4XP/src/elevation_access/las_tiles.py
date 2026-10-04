"""LAS point-cloud tiles: what the point-cloud strategies share.

Footprint geometry, progress lines and the Colorado (CWCB) lidar portal
vocabulary used by more than one of ``las_tile_index``,
``cwcb_lidar_api``, ``aoi_zip_download``, ``arcgis_feature_tiles`` and
``tnm_cog``.
"""

import os

import O4_File_Names as FNAMES
import O4_Geo_Utils as GEO

from elevation_access.definitions import _parse_float

__all__ = [
    "CWCB_SUMMARIES_DEFAULT_MAX_AGE_DAYS",
    "LAS_ARCHIVE_MEMBER_SUFFIX",
    "LAS_FOOTPRINT_KEY",
    "LAS_PROGRESS_INTERVAL_S",
    "_CWCB_LAS_MEMBER_SUFFIX",
    "_buffer_geometry_m",
    "_cwcb_dataset_ids",
    "_cwcb_request_polygon",
    "_esri_polygon_geometry",
    "_las_airport_label",
    "_las_progress_line",
    "_las_size_text",
    "cwcb_summaries_cache_path",
    "las_core_geometry",
]


#: The definition key a ladder rung carries the AIRPORT'S boundary polygon
#: under (GeoJSON-like mapping, EPSG:4326 degrees) -- the extent a
#: surgical LAS fetch is cut to after ``footprint_buffer_m`` (spec §2).
LAS_FOOTPRINT_KEY = "footprint_polygon_wgs84"


#: The #136 heartbeat: a streaming tile prints a progress line at most
#: this many seconds apart (never silent longer).
LAS_PROGRESS_INTERVAL_S = 30.0


LAS_ARCHIVE_MEMBER_SUFFIX = ".las"


def _buffer_geometry_m(geometry, metres):
    """``geometry`` (EPSG:4326 degrees) buffered by ``metres`` on a local
    equirectangular frame at its centroid latitude."""
    if not metres:
        return geometry
    from shapely import affinity

    latitude = geometry.centroid.y
    x_scale = GEO.lon_to_m(latitude)
    y_scale = GEO.lat_to_m
    local = affinity.scale(geometry, xfact=x_scale, yfact=y_scale,
                           origin=(0.0, 0.0))
    grown = local.buffer(float(metres))
    return affinity.scale(grown, xfact=1.0 / x_scale, yfact=1.0 / y_scale,
                          origin=(0.0, 0.0))


def las_core_geometry(definition):
    """The SURGICAL core a LAS rung is cut to: the aerodrome boundary
    polygon the definition carries (:data:`LAS_FOOTPRINT_KEY`) buffered
    by ``footprint_buffer_m``; ``None`` when the definition carries no
    footprint (the whole request box is then listed)."""
    footprint = (definition or {}).get(LAS_FOOTPRINT_KEY)
    if not footprint:
        return None
    from shapely.geometry import shape

    try:
        geometry = shape(footprint)
    except Exception:
        return None
    if geometry.is_empty:
        return None
    return _buffer_geometry_m(
        geometry,
        _parse_float(definition.get("footprint_buffer_m"), default=0.0))


def _esri_polygon_geometry(geometry):
    """An ArcGIS JSON polygon (``{"rings": [...]}``) as shapely, or None.
    Each ring is taken as its own polygon and the union returned (tile
    footprints are single squares; this also reads multipart)."""
    if not isinstance(geometry, dict) or not geometry.get("rings"):
        return None
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    parts = []
    for ring in geometry["rings"]:
        try:
            polygon = Polygon([(float(x), float(y)) for x, y in ring[:]])
        except Exception:
            continue
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if not polygon.is_empty:
            parts.append(polygon)
    return unary_union(parts) if parts else None


def _las_progress_line(label, have, total, moved, seconds, done=False):
    """``   [inset] KASE PITKIN1M tile 3/8 2016-LD26101509.las 41 %
    (38/93 MB, 0.4 MB/s)`` -- or ``done`` at completion."""
    rate = (moved / 1e6) / seconds if seconds > 0 else 0.0
    if done:
        return ("   [inset] %s done (%.0f MB in %.0f s, %.2f MB/s)"
                % (label, have / 1e6, seconds, rate))
    percent = (" %d %%" % int(100.0 * have / total)) if total else ""
    return ("   [inset] %s%s (%.0f/%s MB, %.2f MB/s)"
            % (label, percent, have / 1e6,
               "%.0f" % (total / 1e6) if total else "?", rate))


def _las_size_text(byte_count):
    return "%.1f GB" % (byte_count / 1e9)


def _las_airport_label(destination_path):
    """The airport an inset destination is for: the cache names every
    inset ``<ICAO>_<provider>.tif`` (:func:`FNAMES.airport_inset_dem`),
    ladder/refetch scratch suffixes included."""
    return os.path.basename(str(destination_path)).split("_", 1)[0]


#: The member suffix of a zipped point cloud -- NOT this strategy's
#: (CWCB's LAS-only 7V2 dataset is ``las_tile_index index_format=cwcb
#: archive_member=las``, spec §3.3).
_CWCB_LAS_MEMBER_SUFFIX = LAS_ARCHIVE_MEMBER_SUFFIX


#: Days a cached per-dataset ``tileSummaries`` listing is trusted before
#: it is re-listed (``summaries_max_age_days`` in the .elv overrides).  A
#: listing that CONTRADICTS a fresh ``tiles`` answer (the dataset is named
#: over the box and none of its keys is in the cache) is re-listed at once.
CWCB_SUMMARIES_DEFAULT_MAX_AGE_DAYS = 30.0


def cwcb_summaries_cache_path(provider_code, dataset_id):
    """``Elevation_data/<code>_<dataset>_summaries.json`` -- the per-
    dataset tile listing (tile id, footprint WKT, per-format bytes), the
    spec §3.5 memo.  Under the ``dem`` scope with every other inset
    artefact."""
    return os.path.join(
        FNAMES.Elevation_dir,
        "%s_%s_summaries.json" % (str(provider_code).lower(), dataset_id))


def _cwcb_dataset_ids(definition):
    return [token.strip()
            for token in str(definition.get("dataset_ids", "")).split(",")
            if token.strip()]


def _cwcb_request_polygon(definition, bounding_box_wgs84):
    """The polygon the API is asked over: the SURGICAL core (the aerodrome
    boundary buffered by ``footprint_buffer_m``, :func:`las_core_geometry`
    -- the §2 LAS rule) when the definition carries one, else the request
    box.  Exterior rings counter-clockwise: the server's geography type
    reads a clockwise ring as its complement."""
    from shapely.geometry import MultiPolygon, Polygon, box
    from shapely.geometry.polygon import orient

    core = las_core_geometry(definition)
    geometry = core if core is not None else box(*bounding_box_wgs84)
    if isinstance(geometry, Polygon):
        return orient(geometry, 1.0), core
    if isinstance(geometry, MultiPolygon):
        return MultiPolygon([orient(part, 1.0)
                             for part in geometry.geoms]), core
    return orient(box(*geometry.bounds), 1.0), core
