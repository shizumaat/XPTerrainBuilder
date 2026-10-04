"""Classified LAS point-cloud tiles behind an ArcGIS feature index.

The ``las_tile_index`` access strategy (:class:`LasTileIndexStrategy`).

Everything used by this strategy alone lives in this file; what it
shares with other strategies is imported from ``elevation_access``.
"""

import datetime
import json
import math
import numpy
import os

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base import ProviderUnavailable, TransientFetchError
from elevation_access.capabilities import (
    _definition_needs_laz,
    las_reader_available,
    laz_reader_available,
)
from elevation_access.definitions import (
    _coverage_bbox_intersects,
    _parse_boolean,
    _parse_float,
)
from elevation_access.discovery import (
    discovery_json_payload,
    discovery_listing_items,
    discovery_status_is_transient,
    raise_transient_discovery_failure,
    tnm_listing_items,
)
from elevation_access.downloads import (
    archive_raster_members,
    download_zip_whole,
)
from elevation_access.fetch_slots import (
    _held_provider_fetch_slot,
    provider_fetch_slots,
)
from elevation_access.gdal_support import gdal, has_gdal, ogr, osr
from elevation_access.las_tiles import (
    LAS_ARCHIVE_MEMBER_SUFFIX,
    LAS_FOOTPRINT_KEY,
    LAS_PROGRESS_INTERVAL_S,
    _esri_polygon_geometry,
    _las_airport_label,
    _las_progress_line,
    _las_size_text,
    las_core_geometry,
)
from elevation_access.registry import register_access_strategy
from elevation_access.strategies.cwcb_lidar_api import CwcbLidarApiStrategy
from elevation_access.vertical_units import (
    VERTICAL_UNIT_GRIDDED_IN_METRES,
    VERTICAL_UNIT_TO_M,
)
from elevation_access.warp import (
    _source_contribution_entry,
    _source_holds_data_over_bbox,
    inset_valid_fraction,
    warp_vsicurl_sources_to_geotiff,
)

__all__ = [
    "LAS_ARCHIVE_MEMBER_LAS",
    "LAS_CHUNK_POINTS",
    "LAS_DTM_NODATA",
    "LAS_GRID_RULE_VERSION",
    "LAS_INDEX_FORMAT_ARCGIS",
    "LAS_INDEX_FORMAT_CWCB",
    "LAS_INDEX_FORMAT_OGR",
    "LAS_INDEX_FORMAT_TNM",
    "LAS_OGR_DEFAULT_NAME_FIELD",
    "LAS_OGR_DEFAULT_URL_FIELD",
    "LAS_OGR_QUERY_DENSIFY_SEGMENTS",
    "LAS_UNIT_TO_M",
    "LasTileIndexStrategy",
    "grid_las_tile",
    "las_header_units",
    "las_raw_tile_path",
    "las_tile_cache_directory",
    "validate_las_tile",
]


# =====================================================================
# Strategy: las_tile_index (a LAS point-cloud tile index, gridded here)
# =====================================================================
# Spec ``docs/specs/las-tile-lidar-provider-spec.md`` (#130; owner RULINGS
# 2026-09-30av/aw).  Some lidar is published ONLY as classified point
# clouds: Pitkin County's 2016 flight is the one 1 m source over KASE's
# airfield (the tiles were withheld from the state and never reached
# USGS).  This strategy discovers the tiles through an ArcGIS feature
# index, downloads them whole into ``Elevation_data/_las_tiles/<CODE>/``
# (the ``las_tiles`` refresh scope), grids each tile ONCE to a per-tile
# DTM (a binning mean of the ground-class points, bounded nearest fill)
# and hands those DTMs to the shared warp -- the same EPSG:4326 float32
# inset every raster provider delivers.

#: The point-cloud gridder reads the SHARED unit table
#: (:data:`VERTICAL_UNIT_TO_M`, spec us-holder-providers §2): one table for
#: the LAS ``vertical_unit`` key and the raster warp's.  The old name is
#: kept as an alias for the readers that predate the share.
LAS_UNIT_TO_M = VERTICAL_UNIT_TO_M


#: The value a per-tile DTM cell holds when it has no ground estimate.
LAS_DTM_NODATA = -32768.0


#: Bumped whenever the gridding rule changes: a cached ``<name>_dtm.tif``
#: stamped with another version is re-gridded from the kept raw tile.
LAS_GRID_RULE_VERSION = 1


#: Points read per chunk (pf6 = 30 bytes a point, so ~60 MB a chunk).
LAS_CHUNK_POINTS = 2_000_000


#: ASPRS LAS point-format flag bits that mean "compressed" (LAZ).
_LAS_COMPRESSED_FORMAT_BITS = 0xC0


#: ``index_format`` of a ``las_tile_index`` provider -- where its tile
#: listing comes from (spec us-holder-providers §3.3):
#: an ArcGIS feature-service query (the default; PITKIN1M), the TNM Access
#: API product listing (#153, USGSLPC), any OGR-readable index (a NOAA
#: ``tileindex_*.gpkg``) opened over ``/vsicurl/`` with range reads, or the
#: Colorado CWCB lidar API (the same discovery ``cwcb_lidar_api`` uses).
LAS_INDEX_FORMAT_ARCGIS = "arcgis"


LAS_INDEX_FORMAT_TNM = "tnm"


LAS_INDEX_FORMAT_OGR = "ogr"


LAS_INDEX_FORMAT_CWCB = "cwcb"


#: ``index_format=ogr``: the attribute holding a tile's download URL and
#: the one naming its file (the NOAA Digital Coast tile-index schema:
#: ``filename``, ``srs``, ``url``).
LAS_OGR_DEFAULT_URL_FIELD = "url"


LAS_OGR_DEFAULT_NAME_FIELD = "filename"


#: The query box is densified to this many segments a side before it is
#: transformed into a projected index's CRS (its image there is curved).
LAS_OGR_QUERY_DENSIFY_SEGMENTS = 16


#: ``archive_member=las``: each listed tile is a ZIP holding ONE ``.las``
#: point cloud (CWCB's 2015 Western Colorado point cloud).  The zip comes
#: whole into the ``las_tiles`` cache, the member is extracted beside it
#: and the zip is deleted -- the raw LAS stays, as for a plain tile.
LAS_ARCHIVE_MEMBER_LAS = "las"


def las_tile_cache_directory(provider_code):
    """``Elevation_data/_las_tiles/<CODE>`` -- raw tiles + per-tile DTMs,
    shared across airports and re-cuts (the ``las_tiles`` scope)."""
    return os.path.join(FNAMES.Elevation_dir, "_las_tiles", provider_code)


def _las_crs_epsg(header):
    """The horizontal EPSG code a LAS header declares, or ``None``.

    LAS 1.4 point formats 6+ carry an OGC WKT VLR (record 2112); older
    files a GeoKey directory (record 34735, ProjectedCSTypeGeoKey 3072).
    A compound CRS answers its PROJCS code."""
    for vlr in getattr(header, "vlrs", ()) or ():
        record_id = getattr(vlr, "record_id", None)
        if record_id == 2112:
            wkt = getattr(vlr, "string", None)
            if not wkt:
                continue
            wkt = str(wkt).rstrip("\x00")
            if has_gdal:
                srs = osr.SpatialReference()
                try:
                    srs.ImportFromWkt(wkt)
                    for node in ("PROJCS", "GEOGCS", None):
                        code = srs.GetAuthorityCode(node)
                        if code:
                            return int(code)
                except Exception:
                    pass
            # No GDAL, or a PROJ database it cannot reach: the code is in
            # the WKT text itself (WKT1 AUTHORITY / WKT2 ID).
            code = _wkt_horizontal_epsg(wkt)
            if code is not None:
                return code
        if record_id == 34735:
            for key in getattr(vlr, "geo_keys", ()) or ():
                if getattr(key, "id", None) == 3072:
                    return int(key.value_offset)
    return None


def _wkt_horizontal_epsg(wkt):
    """The EPSG code of a WKT's PROJECTED (else geographic) CRS, read from
    the text: the authority that CLOSES that block (WKT1 ``AUTHORITY``,
    WKT2 ``ID``).  ``None`` when the text names none."""
    import re

    for keyword in ("PROJCS[", "PROJCRS[", "GEOGCS[", "GEOGCRS["):
        start = wkt.find(keyword)
        if start < 0:
            continue
        depth = 0
        end = None
        for position in range(start + len(keyword) - 1, len(wkt)):
            if wkt[position] == "[":
                depth += 1
            elif wkt[position] == "]":
                depth -= 1
                if depth == 0:
                    end = position
                    break
        block = wkt[start:end] if end is not None else wkt[start:]
        found = re.findall(
            r'(?:AUTHORITY|ID)\["EPSG",\s*"?(\d+)"?\]', block)
        if found:
            return int(found[-1])
    return None


def validate_las_tile(path, definition):
    """Refuse a tile that is not what the provider declares, BEFORE it is
    cached.  Returns the header summary; raises
    :class:`ProviderUnavailable` (never a durable no-coverage):

    * not ``LASF``, a compressed (LAZ) point format, or a ``.laz`` name
      -- "LAZ needs a backend" (the engine ships no lazrs/laszip);
    * a point format other than 6;
    * a size that disagrees with ``offset + count x record_length`` (a
      short or padded file; trailing EVLRs are allowed);
    * a header CRS other than ``source_crs``.
    """
    import struct

    code = definition.get("code")
    laz_declared = _definition_needs_laz(definition)
    if str(path).lower().endswith(".laz") and not laz_declared:
        raise ProviderUnavailable("%s: LAZ needs a backend" % code)
    size = os.path.getsize(path)
    with open(path, "rb") as handle:
        head = handle.read(375)
    if len(head) < 227 or head[:4] != b"LASF":
        raise ProviderUnavailable(
            "%s: %s is not a LAS file (no LASF signature)"
            % (code, os.path.basename(path)))
    (offset,) = struct.unpack_from("<I", head, 96)
    point_format = head[104]
    (record_length,) = struct.unpack_from("<H", head, 105)
    (legacy_count,) = struct.unpack_from("<I", head, 107)
    count = legacy_count
    evlr_start = evlr_count = 0
    if head[25] >= 4 and len(head) >= 375:
        (evlr_start,) = struct.unpack_from("<Q", head, 235)
        (evlr_count,) = struct.unpack_from("<I", head, 243)
        (count,) = struct.unpack_from("<Q", head, 247)
    compressed = bool(point_format & _LAS_COMPRESSED_FORMAT_BITS) or str(
        path).lower().endswith(".laz")
    if compressed and not laz_declared:
        raise ProviderUnavailable("%s: LAZ needs a backend" % code)
    if compressed and not laz_reader_available():
        raise ProviderUnavailable(
            "%s: LAZ needs a backend (lazrs missing)" % code)
    base_format = point_format & ~_LAS_COMPRESSED_FORMAT_BITS & 0xFF
    allowed = _las_point_formats(definition)
    if base_format not in allowed:
        raise ProviderUnavailable(
            "%s: %s holds point format %d, not %s"
            % (code, os.path.basename(path), base_format,
               "/".join(str(value) for value in allowed)))
    if not compressed:
        points_end = offset + count * record_length
        if points_end != size and not (
                evlr_count > 0 and points_end <= evlr_start < size):
            raise ProviderUnavailable(
                "%s: %s is %d bytes but its header describes %d (short "
                "or damaged download)"
                % (code, os.path.basename(path), size, points_end))
    import laspy

    with laspy.open(path, mode="r") as reader:
        if _las_crs_from_header(definition):
            # Per-tile CRS (#153, USGS LPC): every project carries its
            # own; a tile must declare one the engine can read.
            units = las_header_units(reader.header, definition)
            return {"points": count, "epsg": units["epsg"], "bytes": size,
                    "crs": units["label"]}
        epsg = _las_crs_epsg(reader.header)
    wanted = int(float(definition.get("source_crs", 0) or 0))
    if epsg != wanted:
        raise ProviderUnavailable(
            "%s: %s declares CRS EPSG:%s, the provider declares EPSG:%d"
            % (code, os.path.basename(path), epsg, wanted))
    return {"points": count, "epsg": epsg, "bytes": size}


def _las_point_formats(definition):
    """The LAS point formats a provider accepts (``point_formats``,
    comma list; ``6`` -- Pitkin County's -- when undeclared)."""
    formats = set()
    for token in str((definition or {}).get("point_formats", "6")).split(
            ","):
        token = token.strip()
        if token:
            try:
                formats.add(int(token))
            except ValueError:
                continue
    return sorted(formats) or [6]


def _las_crs_from_header(definition):
    """``source_crs=from_header``: each tile's CRS (and, with it, its
    horizontal and height units) is read from its own header (#153)."""
    return str((definition or {}).get("source_crs", "")).strip().lower() \
        == "from_header"


def las_header_units(header, definition=None):
    """A LAS header's CRS facts for gridding, read through laspy's
    ``parse_crs`` (OGC WKT VLR or GeoKeys): ``{"wkt", "epsg", "label",
    "xy_to_m", "z_to_m", "z_unit", "z_rule"}``.  Heights take the
    VERTICAL CRS's unit when the CRS is compound, else the horizontal
    unit (the raster rule, :func:`raster_height_unit`).  A tile with no
    readable or no PROJECTED CRS is refused (:class:`ProviderUnavailable`)
    -- a 1 m lattice cannot be laid in degrees."""
    code = (definition or {}).get("code")
    try:
        crs = header.parse_crs()
    except Exception as error:
        raise ProviderUnavailable("%s: tile CRS unreadable: %s"
                                  % (code, error))
    if crs is None:
        raise ProviderUnavailable("%s: tile declares no CRS" % code)
    horizontal = crs
    vertical = None
    if crs.is_compound and crs.sub_crs_list:
        horizontal = crs.sub_crs_list[0]
        if len(crs.sub_crs_list) > 1:
            vertical = crs.sub_crs_list[1]
    if not horizontal.is_projected:
        raise ProviderUnavailable(
            "%s: tile CRS %s is not projected" % (code, horizontal.name))
    xy_to_m = float(horizontal.axis_info[0].unit_conversion_factor)
    if vertical is not None and vertical.axis_info:
        z_to_m = float(vertical.axis_info[0].unit_conversion_factor)
        z_unit = vertical.axis_info[0].unit_name
        z_rule = "vertical-crs"
    else:
        z_to_m = xy_to_m
        z_unit = horizontal.axis_info[0].unit_name
        z_rule = "horizontal-crs"
    epsg = horizontal.to_epsg()
    return {
        "wkt": horizontal.to_wkt(),
        "epsg": epsg,
        "label": ("EPSG:%d" % epsg) if epsg else str(horizontal.name),
        "xy_to_m": xy_to_m,
        "z_to_m": z_to_m,
        "z_unit": str(z_unit),
        "z_rule": z_rule,
    }


def _las_horizontal_unit_m(source_crs, vertical_unit):
    """Metres per horizontal unit of ``source_crs`` (GDAL), falling back
    to the declared vertical unit when GDAL cannot answer."""
    if has_gdal:
        try:
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(int(source_crs))
            units = float(srs.GetLinearUnits())
            if units > 0:
                return units
        except Exception:
            pass
    return VERTICAL_UNIT_TO_M[vertical_unit]


def _fill_empty_cells(values, valid, radius_cells):
    """Up to ``radius_cells`` rounds of 3 x 3 mean-of-valid dilation.

    Each round gives every EMPTY cell with at least one valid 8-neighbour
    the mean of those neighbours, then counts it valid for the next
    round -- so a hole closes from its rim inward, at most
    ``radius_cells`` cells deep; what is left stays empty (NoData).
    Pure numpy, sequential sums: bit-identical on every platform."""
    values = values.copy()
    valid = valid.copy()
    filled = numpy.zeros(valid.shape, dtype=bool)
    rows, cols = valid.shape
    for _round in range(int(radius_cells)):
        if valid.all():
            break
        padded_values = numpy.zeros((rows + 2, cols + 2), dtype=numpy.float64)
        padded_valid = numpy.zeros((rows + 2, cols + 2), dtype=numpy.float64)
        padded_values[1:-1, 1:-1] = numpy.where(valid, values, 0.0)
        padded_valid[1:-1, 1:-1] = valid
        total = numpy.zeros((rows, cols), dtype=numpy.float64)
        count = numpy.zeros((rows, cols), dtype=numpy.float64)
        for d_row in (0, 1, 2):
            for d_col in (0, 1, 2):
                if d_row == 1 and d_col == 1:
                    continue
                total += padded_values[d_row:d_row + rows, d_col:d_col + cols]
                count += padded_valid[d_row:d_row + rows, d_col:d_col + cols]
        grow = (~valid) & (count > 0)
        if not grow.any():
            break
        values[grow] = total[grow] / count[grow]
        valid = valid | grow
        filled |= grow
    return values, valid, filled


def grid_las_tile(las_path, dtm_path, definition):
    """Grid one LAS tile to a DTM GeoTIFF in the SOURCE CRS (spec §3).

    Ground points (``ground_classes``, never ``withheld``) are binned on a
    ``grid_resolution_m`` lattice ANCHORED ON THE CRS ORIGIN (whole cells
    from x = 0 / y = 0), so adjacent tiles share cell edges; each cell is
    the MEAN of its points (``numpy.bincount``: O(n), sequential, so
    bit-identical across platforms); a cell with fewer than
    ``min_points_per_cell`` points is empty, then up to
    ``fill_radius_cells`` rounds of 3 x 3 mean-of-valid dilation close
    small holes; beyond that the cell is NoData.  Heights convert from
    ``vertical_unit`` to metres in the source vertical datum (never
    shifted).  Writes ``dtm_path`` (deflate GeoTIFF, EPSG ``source_crs``)
    and ``<dtm stem>.json``; returns that record.
    """
    import laspy

    from_header = _las_crs_from_header(definition)
    tile_units = None
    if from_header:
        source_crs = "from_header"
        vertical_unit = "from_header"
        with laspy.open(las_path, mode="r") as reader:
            tile_units = las_header_units(reader.header, definition)
        z_to_m = tile_units["z_to_m"]
        xy_to_m = tile_units["xy_to_m"]
    else:
        source_crs = int(float(definition.get("source_crs")))
        vertical_unit = str(definition.get("vertical_unit", "m"))
        if vertical_unit not in LAS_UNIT_TO_M:
            raise ProviderUnavailable(
                "%s: unknown vertical_unit %r" % (definition.get("code"),
                                                  vertical_unit))
        z_to_m = LAS_UNIT_TO_M[vertical_unit]
        xy_to_m = _las_horizontal_unit_m(source_crs, vertical_unit)
    resolution_m = float(definition.get("grid_resolution_m", 1))
    cell = resolution_m / xy_to_m
    ground_classes = sorted(
        {int(token) for token in
         str(definition.get("ground_classes", "2")).split(",")
         if token.strip()})
    min_points = int(float(definition.get("min_points_per_cell", 1)))
    fill_radius = int(float(definition.get("fill_radius_cells", 0)))

    with laspy.open(las_path, mode="r") as reader:
        header = reader.header
        (min_x, min_y) = (float(header.mins[0]), float(header.mins[1]))
        (max_x, max_y) = (float(header.maxs[0]), float(header.maxs[1]))
        origin_x = math.floor(min_x / cell) * cell
        top_y = math.ceil(max_y / cell) * cell
        if top_y <= max_y:
            top_y += cell
        cols = max(1, int(math.floor((max_x - origin_x) / cell)) + 1)
        rows = max(1, int(math.floor((top_y - min_y) / cell)) + 1)
        cells = rows * cols
        sums = numpy.zeros(cells, dtype=numpy.float64)
        counts = numpy.zeros(cells, dtype=numpy.int64)
        points_total = int(header.point_count)
        points_ground = 0
        for points in reader.chunk_iterator(LAS_CHUNK_POINTS):
            classification = numpy.asarray(points.classification)
            keep = numpy.isin(classification, ground_classes)
            withheld = numpy.asarray(points.withheld).astype(bool)
            keep &= ~withheld
            if not keep.any():
                continue
            x = numpy.asarray(points.x)[keep]
            y = numpy.asarray(points.y)[keep]
            z = numpy.asarray(points.z, dtype=numpy.float64)[keep]
            col = numpy.floor((x - origin_x) / cell).astype(numpy.int64)
            row = numpy.floor((top_y - y) / cell).astype(numpy.int64)
            inside = (col >= 0) & (col < cols) & (row >= 0) & (row < rows)
            index = row[inside] * cols + col[inside]
            sums += numpy.bincount(index, weights=z[inside], minlength=cells)
            counts += numpy.bincount(index, minlength=cells)
            points_ground += int(inside.sum())
    measured = counts >= max(1, min_points)
    means = numpy.zeros(cells, dtype=numpy.float64)
    means[measured] = sums[measured] / counts[measured]
    points_in_measured = int(counts[measured].sum())
    values, valid, filled = _fill_empty_cells(
        means.reshape(rows, cols), measured.reshape(rows, cols), fill_radius)
    grid = numpy.full((rows, cols), LAS_DTM_NODATA, dtype=numpy.float32)
    grid[valid] = (values[valid] * z_to_m).astype(numpy.float32)

    os.makedirs(os.path.dirname(dtm_path) or ".", exist_ok=True)
    scratch = dtm_path + ".part"
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(
        scratch, cols, rows, 1, gdal.GDT_Float32,
        options=["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"])
    dataset.SetGeoTransform((origin_x, cell, 0.0, top_y, 0.0, -cell))
    srs = osr.SpatialReference()
    if tile_units is not None:
        srs.ImportFromWkt(tile_units["wkt"])
    else:
        srs.ImportFromEPSG(source_crs)
    dataset.SetProjection(srs.ExportToWkt())
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(LAS_DTM_NODATA)
    band.WriteArray(grid)
    dataset = None
    cells_valid = int(measured.sum())
    cells_filled = int(filled.sum())
    record = {
        "points_total": points_total,
        "points_ground": points_ground,
        "points_in_valid_cells": points_in_measured,
        "ground_density_per_m2": (
            round(points_in_measured / (cells_valid * resolution_m ** 2), 4)
            if cells_valid else 0.0),
        "cells_total": int(cells),
        "cells_valid": cells_valid,
        "cells_filled": cells_filled,
        "fill_radius_cells": fill_radius,
        "min_points_per_cell": min_points,
        "ground_classes": ground_classes,
        "grid_resolution_m": resolution_m,
        "vertical_unit": vertical_unit,
        "source_crs": source_crs,
        "laspy_version": str(getattr(laspy, "__version__", "?")),
        "grid_rule_version": LAS_GRID_RULE_VERSION,
    }
    if tile_units is not None:
        record["tile_crs"] = tile_units["label"]
        record["tile_vertical_unit"] = tile_units["z_unit"]
        record["tile_vertical_unit_rule"] = tile_units["z_rule"]
    os.replace(scratch, dtm_path)
    with open(_las_dtm_record_path(dtm_path), "w", newline="\n") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
    return record


def _las_dtm_record_path(dtm_path):
    return dtm_path[:-4] + ".json" if dtm_path.endswith(".tif") \
        else dtm_path + ".json"


def _las_dtm_record_if_current(dtm_path, definition):
    """The cached per-tile DTM record when it was gridded under THIS rule
    and these keys, else ``None`` (the tile is re-gridded)."""
    try:
        with open(_las_dtm_record_path(dtm_path), "r") as handle:
            record = json.load(handle)
    except (OSError, ValueError):
        return None
    if not os.path.isfile(dtm_path):
        return None
    wanted = {
        "grid_rule_version": LAS_GRID_RULE_VERSION,
        "grid_resolution_m": float(definition.get("grid_resolution_m", 1)),
        "fill_radius_cells": int(float(definition.get("fill_radius_cells",
                                                      0))),
        "min_points_per_cell": int(float(definition.get(
            "min_points_per_cell", 1))),
        "vertical_unit": ("from_header"
                          if _las_crs_from_header(definition)
                          else str(definition.get("vertical_unit", "m"))),
        "source_crs": ("from_header" if _las_crs_from_header(definition)
                       else int(float(definition.get("source_crs")))),
        "ground_classes": sorted(
            {int(token) for token in
             str(definition.get("ground_classes", "2")).split(",")
             if token.strip()}),
    }
    for key, value in wanted.items():
        if record.get(key) != value:
            return None
    return record


@register_access_strategy("las_tile_index")
class LasTileIndexStrategy:
    """Classified LAS point-cloud tiles behind an ArcGIS feature index.

    Discovery is ONE GET on ``index_url_template`` (the airport box in
    EPSG:4326, the ``tnm_cog`` idiom), classified by the module's one
    discovery law: 5xx/429/non-JSON/an ArcGIS ``{"error": ...}`` inside a
    200/a truncated listing are TRANSIENT; a well-formed empty
    ``features`` list is the durable no-coverage.  Fetch downloads every
    listed tile whole (resumable), validates it, caches it, grids it
    once (:func:`grid_las_tile`) and warps the per-tile DTMs to the inset
    window.  Never a whole-tile overlay: a 7 GB point cloud is not a
    tile-wide source.
    """

    supports_wide_area = False

    def _index_url(self, definition, bounding_box_wgs84):
        (west, south, east, north) = bounding_box_wgs84
        return (
            str(definition.get("index_url_template", ""))
            .replace("{west}", repr(west))
            .replace("{south}", repr(south))
            .replace("{east}", repr(east))
            .replace("{north}", repr(north))
        )

    def _tile_url(self, definition, name):
        return str(definition.get("tile_url_template", "")).replace(
            "{name}", name)

    def discover(self, definition, bounding_box_wgs84):
        """The tile listing, SURGICAL when the definition carries the
        airport's footprint (spec §2, owner 30ay): the index is queried
        over the buffered footprint's envelope and a tile is kept only
        when its FOOTPRINT meets the buffered boundary POLYGON -- a
        diagonal runway's bbox must not buy corner tiles.  Without a
        footprint the whole ``bounding_box_wgs84`` is listed."""
        import requests

        self.last_listing = []
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        core = las_core_geometry(definition)
        query_box = core.bounds if core is not None else bounding_box_wgs84
        description = "%s tile index" % definition.get("code")
        index_format = _las_index_format(definition)
        if index_format == LAS_INDEX_FORMAT_TNM:
            return self._discover_tnm(definition, query_box, core,
                                      description)
        if index_format == LAS_INDEX_FORMAT_OGR:
            return self._discover_ogr(definition, query_box, core,
                                      description)
        if index_format == LAS_INDEX_FORMAT_CWCB:
            return self._discover_cwcb(definition, bounding_box_wgs84)
        if index_format != LAS_INDEX_FORMAT_ARCGIS:
            raise ProviderUnavailable(
                "%s: index_format=%s is not one of %s"
                % (definition.get("code"), index_format, ", ".join(
                    _LAS_INDEX_FORMATS)))
        try:
            response = requests.get(
                self._index_url(definition, query_box), timeout=60)
        except Exception as error:
            raise_transient_discovery_failure(description + " request",
                                              error)
        payload = discovery_json_payload(response, description)
        if payload is None:
            return None
        features = discovery_listing_items(
            payload, description, items_key="features", total_key=None)
        if isinstance(payload, dict) and payload.get(
                "exceededTransferLimit"):
            # A PAGE, not the listing: the tiles beyond it would be
            # silently missing from the inset.
            raise_transient_discovery_failure(
                description, "a truncated listing (exceededTransferLimit)")
        name_field = definition.get("index_name_field", "name")
        names = set()
        unnamed = 0
        for feature in features:
            attributes = (feature or {}).get("attributes") or {}
            name = attributes.get(name_field)
            if not name:
                unnamed += 1
                continue
            if core is not None:
                footprint = _esri_polygon_geometry(
                    (feature or {}).get("geometry"))
                if footprint is None:
                    raise_transient_discovery_failure(
                        description,
                        "feature %s carries no footprint geometry (the "
                        "surgical fetch needs returnGeometry=true)" % name)
                if not footprint.intersects(core):
                    continue
            names.add(str(name).strip())
        if not names and unnamed:
            raise_transient_discovery_failure(
                description,
                "a listing of %d feature(s) with no '%s' attribute"
                % (len(features), name_field))
        if not names:
            return None
        listing = [
            {
                "source_id": name,
                "title": name,
                "download_url": self._tile_url(definition, name),
                "publication_date": definition.get("publication_date") or "",
            }
            for name in sorted(names)
        ]
        self.last_listing = listing
        return listing

    def _discover_tnm(self, definition, query_box, core, description):
        """``index_format=tnm`` (#153, the USGS Lidar Point Cloud rung):
        the index is a TNM Access API product listing (paged,
        :func:`tnm_listing_items`); a tile is an item's ``downloadURL``,
        its name the file stem, its footprint the item's ``boundingBox``
        (kept only when it meets the buffered boundary polygon), its
        size the listing's ``sizeInBytes``.  OLDEST PROJECT FIRST, so in
        the warp the newest flight wins where two overlap (the R13-2
        rule)."""
        from shapely.geometry import box as shapely_box

        items = tnm_listing_items(self._index_url(definition, query_box),
                                  description)
        if items is None:
            return None
        extensions = tuple(
            "." + token.strip().lower().lstrip(".")
            for token in str(definition.get("tile_extensions",
                                            "laz,las")).split(",")
            if token.strip())
        by_name = {}
        unusable = 0
        for item in items:
            url = str((item or {}).get("downloadURL") or "")
            stem = url.split("?", 1)[0].rsplit("/", 1)[-1]
            if not stem.lower().endswith(extensions):
                unusable += 1
                continue
            name = stem.rsplit(".", 1)[0]
            if core is not None:
                extent = (item or {}).get("boundingBox") or {}
                try:
                    footprint = shapely_box(
                        float(extent["minX"]), float(extent["minY"]),
                        float(extent["maxX"]), float(extent["maxY"]))
                except (KeyError, TypeError, ValueError):
                    raise_transient_discovery_failure(
                        description,
                        "item %s carries no boundingBox (the surgical "
                        "fetch needs one)" % name)
                if not footprint.intersects(core):
                    continue
            try:
                size_bytes = int(item.get("sizeInBytes") or 0)
            except (TypeError, ValueError):
                size_bytes = 0
            by_name[name] = {
                "source_id": name,
                "title": item.get("title") or name,
                "download_url": url,
                "publication_date": str(item.get("publicationDate") or ""),
                "size_bytes": size_bytes,
            }
        if not by_name and unusable:
            raise_transient_discovery_failure(
                description,
                "a listing of %d item(s) with no %s download URL"
                % (len(items), "/".join(extensions)))
        listing = sorted(by_name.values(),
                         key=lambda source: (source["publication_date"],
                                             source["source_id"]))
        self.last_listing = listing
        return listing or None

    def _discover_ogr(self, definition, query_box, core, description):
        """``index_format=ogr`` (spec us-holder-providers §3.3): the index
        is any OGR-readable vector file -- a NOAA ``tileindex_*.gpkg`` --
        opened over ``/vsicurl/`` (GDAL fetches only the byte RANGES the
        spatial filter touches, never the whole file).  The layer is
        filtered by the query box in the layer's own CRS, then each tile's
        FOOTPRINT is tested against the buffered boundary polygon exactly
        as the ArcGIS branch does.  ``index_url_field`` names a tile's
        download URL, ``index_name_field`` its file name (the source id is
        the name without its last extension).

        An index that cannot be opened or read is no coverage answer
        (TRANSIENT); a readable index listing no tile over the footprint
        is the durable no-coverage."""
        from shapely import wkb as shapely_wkb

        index_url = str(definition.get("index_url", "")).strip()
        if not index_url:
            raise ProviderUnavailable(
                "%s: index_format=ogr needs index_url"
                % definition.get("code"))
        url_field = str(definition.get(
            "index_url_field", LAS_OGR_DEFAULT_URL_FIELD)).strip()
        name_field = str(definition.get(
            "index_name_field", LAS_OGR_DEFAULT_NAME_FIELD)).strip()
        path = (index_url if index_url.startswith("/vsi")
                or "://" not in index_url else "/vsicurl/" + index_url)
        wgs84 = osr.SpatialReference()
        wgs84.ImportFromEPSG(4326)
        wgs84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        by_name = {}
        unusable = 0
        try:
            # No directory listing on open and no ``.aux.xml`` probe on
            # close: the index's own byte ranges are the only reads.
            with gdal.config_options({
                    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
                    "GDAL_PAM_ENABLED": "NO"}):
                dataset = ogr.Open(path)
                if dataset is None or not dataset.GetLayerCount():
                    raise RuntimeError("no vector layer at %s" % index_url)
                layer = dataset.GetLayer(int(float(
                    definition.get("index_layer", 0) or 0)))
                layer_srs = layer.GetSpatialRef()
                to_wgs84 = None
                query = ogr.CreateGeometryFromWkt(
                    "POLYGON ((%r %r, %r %r, %r %r, %r %r, %r %r))" % (
                        query_box[0], query_box[1], query_box[2],
                        query_box[1], query_box[2], query_box[3],
                        query_box[0], query_box[3], query_box[0],
                        query_box[1]))
                # Densified, so a projected layer's curved image of the
                # box still holds it: the envelope filter is what the
                # range reads follow; the polygon test below is exact.
                query.Segmentize(max(query_box[2] - query_box[0],
                                     query_box[3] - query_box[1])
                                 / LAS_OGR_QUERY_DENSIFY_SEGMENTS or 1.0)
                if layer_srs is not None:
                    layer_srs = layer_srs.Clone()
                    layer_srs.SetAxisMappingStrategy(
                        osr.OAMS_TRADITIONAL_GIS_ORDER)
                    if not layer_srs.IsSame(wgs84):
                        query.Transform(osr.CoordinateTransformation(
                            wgs84, layer_srs))
                        to_wgs84 = osr.CoordinateTransformation(
                            layer_srs, wgs84)
                layer.SetSpatialFilter(query)
                layer.ResetReading()
                for feature in layer:
                    url = feature.GetField(url_field) if feature.GetFieldIndex(
                        url_field) >= 0 else None
                    name = (feature.GetField(name_field)
                            if feature.GetFieldIndex(name_field) >= 0
                            else None)
                    if not url or not name:
                        unusable += 1
                        continue
                    name = str(name).strip().rsplit("/", 1)[-1]
                    stem = name.rsplit(".", 1)[0] if "." in name else name
                    if core is not None:
                        geometry = feature.GetGeometryRef()
                        if geometry is None:
                            raise RuntimeError(
                                "feature %s carries no footprint geometry"
                                % name)
                        geometry = geometry.Clone()
                        if to_wgs84 is not None:
                            geometry.Transform(to_wgs84)
                        footprint = shapely_wkb.loads(
                            bytes(geometry.ExportToWkb()))
                        if not footprint.intersects(core):
                            continue
                    by_name[stem] = {
                        "source_id": stem,
                        "title": name,
                        "download_url": str(url).strip(),
                        "publication_date": definition.get(
                            "publication_date") or "",
                    }
                layer = None
                dataset = None
        except (TransientFetchError, ProviderUnavailable):
            raise
        except Exception as error:
            raise_transient_discovery_failure(description, error)
        if not by_name and unusable:
            raise_transient_discovery_failure(
                description,
                "an index of %d feature(s) with no '%s'/'%s' attribute"
                % (unusable, url_field, name_field))
        listing = [by_name[name] for name in sorted(by_name)]
        self.last_listing = listing
        return listing or None

    def _discover_cwcb(self, definition, bounding_box_wgs84):
        """``index_format=cwcb``: the tile listing of the Colorado CWCB
        lidar API -- the ONE CWCB discovery
        (:meth:`CwcbLidarApiStrategy.discover_tiles`, the surgical polygon
        included); each listed tile is a zip (``archive_member=las``)."""
        sources = CwcbLidarApiStrategy().discover_tiles(
            definition, bounding_box_wgs84)
        listing = []
        for source in sources or ():
            entry = dict(source)
            # The listing's size is the point cloud's (the zip is smaller):
            # the byte cap is judged on it, before any byte moves.
            entry["size_bytes"] = int(source.get("bytes") or 0)
            listing.append(entry)
        self.last_listing = listing
        return listing or None

    def _download_zip_member(self, definition, source, final_path,
                             progress_label=None):
        """``archive_member=las``: the tile's zip comes WHOLE into the
        ``las_tiles`` cache (:func:`download_zip_whole`), its one ``.las``
        member is extracted beside it, validated and ``os.replace``d into
        place; the zip is deleted whatever happens.  ``True``, or
        ``False`` for a 404 (the listed tile is not on the server)."""
        import shutil
        import zipfile

        code = definition.get("code")
        # ``.zip`` LAST: GDAL's /vsizip/ recognises an archive inside a
        # longer path (a member folder) only by that suffix.
        zip_path = final_path + ".part.zip"
        member_path = final_path + ".part"
        label = progress_label or "%s %s" % (code, source["source_id"])
        try:
            if not download_zip_whole(definition, source, zip_path, None,
                                      label):
                return False
            root = "/vsizip/" + zip_path
            members = [member[len(root) + 1:] for member in
                       archive_raster_members(
                           root, (LAS_ARCHIVE_MEMBER_SUFFIX,))]
            if len(members) != 1:
                raise ProviderUnavailable(
                    "%s: tile %s zip holds %d %s member(s), the provider "
                    "declares one (archive_member=%s)"
                    % (code, source["source_id"], len(members),
                       LAS_ARCHIVE_MEMBER_SUFFIX, LAS_ARCHIVE_MEMBER_LAS))
            with zipfile.ZipFile(zip_path) as archive:
                with archive.open(members[0]) as reader, open(
                        member_path, "wb") as writer:
                    shutil.copyfileobj(reader, writer, 1 << 20)
            validate_las_tile(member_path, definition)
            os.replace(member_path, final_path)
            return True
        finally:
            for leftover in (zip_path, member_path):
                if os.path.isfile(leftover):
                    os.remove(leftover)

    def _check_caps(self, definition, sources, cache_directory,
                    destination_path):
        """Refuse an over-cap fetch BEFORE any byte moves (spec §2)."""
        import requests

        code = definition.get("code")
        max_tiles = int(float(definition.get("max_tiles_per_airport", 0)
                              or 0))
        max_bytes = int(float(definition.get("max_bytes_per_airport", 0)
                              or 0))
        total_bytes = 0
        for source in sources:
            cached = las_raw_tile_path(cache_directory, source)
            if os.path.isfile(cached):
                total_bytes += os.path.getsize(cached)
                continue
            if not max_bytes:
                continue
            if source.get("size_bytes"):
                # The listing already says (TNM ``sizeInBytes``).
                total_bytes += int(source["size_bytes"])
                continue
            try:
                head = requests.head(source["download_url"], timeout=30,
                                     allow_redirects=True)
                total_bytes += int(head.headers.get("Content-Length") or 0)
            except Exception as error:
                raise TransientFetchError(
                    "%s: size query for %s failed: %s"
                    % (code, source["source_id"], error)) from error
        over_tiles = max_tiles and len(sources) > max_tiles
        over_bytes = max_bytes and total_bytes > max_bytes
        if over_tiles or over_bytes:
            raise ProviderUnavailable(
                "%s: %s%s needs %d tiles / %s, cap %d / %s "
                "(max_tiles_per_airport / max_bytes_per_airport in %s.elv)"
                " — SKIPPED, recorded unavailable, not no-coverage"
                % (code, _las_airport_label(destination_path),
                   " core" if las_core_geometry(definition) is not None
                   else "", len(sources),
                   _las_size_text(total_bytes), max_tiles,
                   _las_size_text(max_bytes), code))
        return total_bytes

    def _download_tile(self, definition, source, scratch_path, final_path,
                       progress_label=None):
        """One tile, resumable, validated, then ``os.replace``d into the
        cache.  Returns ``True``, or ``False`` for a 404 (the server
        answered: this listed tile does not exist).

        PROGRESS (the #136 heartbeat law: nothing silent > 60 s): while
        the tile streams, one ``[inset]`` line at most every
        :data:`LAS_PROGRESS_INTERVAL_S` and one at completion, through
        the ordinary ``UI.vprint`` channel (stdout / Qt / Ortho4XP.log)."""
        import requests
        import time as _time

        code = definition.get("code")
        url = source["download_url"]
        label = progress_label or "%s %s" % (code, source["source_id"])
        for _attempt in range(2):
            headers = {}
            resume_from = 0
            if os.path.isfile(scratch_path):
                resume_from = os.path.getsize(scratch_path)
                if resume_from:
                    headers["Range"] = "bytes=%d-" % resume_from
            try:
                response = requests.get(url, stream=True, timeout=(30, 120),
                                        headers=headers)
            except Exception as error:
                raise TransientFetchError(
                    "%s: tile %s download failed: %s"
                    % (code, source["source_id"], error)) from error
            try:
                status = int(response.status_code)
                if status == 404:
                    return False
                if status == 416 and resume_from:
                    os.remove(scratch_path)          # stale scratch; retry
                    continue
                if discovery_status_is_transient(status):
                    raise TransientFetchError(
                        "%s: tile %s answered HTTP %d"
                        % (code, source["source_id"], status))
                if status not in (200, 206):
                    raise ProviderUnavailable(
                        "%s: tile %s answered HTTP %d"
                        % (code, source["source_id"], status))
                os.makedirs(os.path.dirname(scratch_path), exist_ok=True)
                appending = status == 206 and resume_from
                if appending:
                    handle = open(scratch_path, "ab")
                else:
                    handle = open(scratch_path, "wb")
                have = resume_from if appending else 0
                try:
                    total = have + int(
                        (getattr(response, "headers", None) or {}).get(
                            "Content-Length") or 0)
                except (TypeError, ValueError):
                    total = 0
                started = _time.monotonic()
                last_line = started
                moved = 0
                with handle:
                    for block in response.iter_content(1 << 20):
                        if UI.red_flag:
                            raise TransientFetchError(
                                "%s tile download stopped with the build"
                                % code)
                        if block:
                            handle.write(block)
                            have += len(block)
                            moved += len(block)
                        now = _time.monotonic()
                        if now - last_line >= LAS_PROGRESS_INTERVAL_S:
                            last_line = now
                            UI.vprint(1, _las_progress_line(
                                label, have, total, moved, now - started))
                UI.vprint(1, _las_progress_line(
                    label, have, total or have, moved,
                    _time.monotonic() - started, done=True))
                if total and have != total and url.lower().split(
                        "?", 1)[0].endswith(".laz"):
                    # A LAZ file has no size its header can vouch for:
                    # the transfer's own length is the integrity check.
                    raise TransientFetchError(
                        "%s: tile %s stopped at %d of %d bytes"
                        % (code, source["source_id"], have, total))
            except (TransientFetchError, ProviderUnavailable):
                raise
            except Exception as error:
                raise TransientFetchError(
                    "%s: tile %s download died: %s"
                    % (code, source["source_id"], error)) from error
            finally:
                response.close()
            validate_las_tile(scratch_path, definition)
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            os.replace(scratch_path, final_path)
            return True
        raise TransientFetchError(
            "%s: tile %s could not be resumed" % (code, source["source_id"]))

    def fetch(
        self,
        definition,
        bounding_box_wgs84,
        target_resolution_m,
        destination_path,
    ):
        code = definition.get("code")
        if not has_gdal:
            return None
        if not _coverage_bbox_intersects(definition, bounding_box_wgs84):
            return None
        if not las_reader_available():
            # A missing reader is never a coverage answer (13b): the
            # engine could not ASK, so the record says unavailable and
            # the next run with laspy asks again.
            raise ProviderUnavailable("laspy missing")
        if _definition_needs_laz(definition) and not laz_reader_available():
            # Same door for the LAZ decompressor (#153): the ladder
            # records ``unavailable`` and climbs on to the next rung.
            raise ProviderUnavailable("LAZ backend (lazrs) missing")
        archive_member = _las_archive_member(definition)
        if archive_member not in ("", LAS_ARCHIVE_MEMBER_LAS):
            raise ProviderUnavailable(
                "%s: archive_member=%s is not supported (only %s)"
                % (code, archive_member, LAS_ARCHIVE_MEMBER_LAS))
        sources = self.discover(definition, bounding_box_wgs84)
        if not sources:
            return None
        cache_directory = las_tile_cache_directory(code)
        self._check_caps(definition, sources, cache_directory,
                         destination_path)
        keep_raw = _parse_boolean(definition.get("keep_raw_las", "True"))
        zipped = archive_member == LAS_ARCHIVE_MEMBER_LAS
        slots = provider_fetch_slots(definition)
        airport = _las_airport_label(destination_path)
        # DOWNLOAD the tiles that have neither a current DTM nor a cached
        # raw file -- each GET under one of the provider's politeness
        # slots (``fetch_slots``), so at most that many transfers run
        # against the county's server at once.
        wanted = []
        for (number, source) in enumerate(sources):
            name = source["source_id"]
            las_path = las_raw_tile_path(cache_directory, source)
            dtm_path = os.path.join(cache_directory, name + "_dtm.tif")
            if _las_dtm_record_if_current(dtm_path, definition) is None \
                    and not os.path.isfile(las_path):
                wanted.append((number, source, las_path))
        missing = []
        if wanted:
            UI.vprint(
                1,
                "    [inset] %s %s: downloading %d of %d LAS tile(s) over "
                "%d connection(s) into %s"
                % (airport, code, len(wanted), len(sources), slots,
                   cache_directory),
            )

            def _download(item):
                (number, source, las_path) = item
                order = wanted.index(item) + 1
                label = "%s %s tile %d/%d %s" % (
                    airport, code, order, len(wanted),
                    os.path.basename(source["download_url"]))
                with _held_provider_fetch_slot(code, slots):
                    if zipped:
                        return self._download_zip_member(
                            definition, source, las_path,
                            progress_label=label)
                    return self._download_tile(
                        definition, source,
                        destination_path + ".las%d.part" % number, las_path,
                        progress_label=label)

            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=slots) as pool:
                results = list(pool.map(_download, wanted))
            missing = sorted(
                item[1]["source_id"]
                for (item, ok) in zip(wanted, results) if not ok)
        # GRID each present tile once (a current DTM is re-used as is).
        dtm_paths = []
        records = []
        for source in sources:
            name = source["source_id"]
            if name in missing:
                continue
            las_path = las_raw_tile_path(cache_directory, source)
            dtm_path = os.path.join(cache_directory, name + "_dtm.tif")
            record = _las_dtm_record_if_current(dtm_path, definition)
            if record is None:
                try:
                    record = grid_las_tile(las_path, dtm_path, definition)
                except ProviderUnavailable:
                    raise
                except Exception as error:
                    # A cached raw tile that will not decode (a LAZ cut
                    # short before the length check existed, a damaged
                    # disk copy): drop it so the next run downloads it
                    # again -- an unreadable file is no coverage answer.
                    if os.path.isfile(las_path):
                        os.remove(las_path)
                    raise TransientFetchError(
                        "%s: tile %s could not be gridded: %s"
                        % (code, name, error)) from error
                if not keep_raw and os.path.isfile(las_path):
                    os.remove(las_path)
            dtm_paths.append(dtm_path)
            records.append(record)
        if not dtm_paths:
            raise ProviderUnavailable(
                "index lists %d tiles, server has none" % len(sources))
        from_header = _las_crs_from_header(definition)
        if not warp_vsicurl_sources_to_geotiff(
            dtm_paths,
            bounding_box_wgs84,
            target_resolution_m,
            destination_path,
            # Per-tile CRS (#153): each DTM carries its own.
            source_srs=(None if from_header else "EPSG:%d" % int(float(
                definition.get("source_crs")))),
            source_nodata=LAS_DTM_NODATA,
            value_floor_m=float(definition.get("value_floor_m", -600.0)),
            vertical_unit=VERTICAL_UNIT_GRIDDED_IN_METRES,
            provider_code=definition.get("code"),
        ):
            return None
        present = [source for source in sources
                   if source["source_id"] not in missing]
        used = []
        empty = []
        for source, dtm_path in zip(present, dtm_paths):
            if _source_holds_data_over_bbox(dtm_path, bounding_box_wgs84,
                                            source_nodata=LAS_DTM_NODATA):
                used.append(source)
            else:
                empty.append(source)
        cells_valid = sum(record["cells_valid"] for record in records)
        cells_filled = sum(record["cells_filled"] for record in records)
        points_valid = sum(record.get("points_in_valid_cells", 0)
                           for record in records)
        resolution = float(definition.get("grid_resolution_m", 1))
        valid_fraction = inset_valid_fraction(destination_path)
        density = (round(points_valid / (cells_valid * resolution ** 2), 4)
                   if cells_valid else 0.0)
        provenance = {
            "provider": code,
            "access_strategy": definition.get("access_strategy"),
            "source_urls": [source["download_url"] for source in sources],
            "source_ids": [source["source_id"] for source in sources],
            "sources_used": [
                _source_contribution_entry(source) for source in used],
            "sources_empty_over_bbox": [
                _source_contribution_entry(source) for source in empty],
            "tiles_missing": sorted(missing),
            "publication_date": definition.get("publication_date"),
            "valid_fraction": round(valid_fraction, 6),
            "filled_fraction": round(
                cells_filled / float(cells_valid + cells_filled), 6)
            if cells_valid + cells_filled else 0.0,
            "point_density_per_m2": density,
            "ground_density_per_m2": density,
            # The empty-cell rate a 1 m bin reads at this density by
            # chance alone (e^-lambda, spec §3): the fill target is
            # ``2 * poisson_empty_rate + 0.05``.
            "poisson_empty_rate": round(math.exp(-density), 6)
            if density else 1.0,
            "rmse_z_m": _parse_float(definition.get("rmse_z_m")),
            "license": definition.get("license"),
            "license_note": definition.get("license_note"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "vertical_unit_source": (
                sorted({"%s (%s)" % (record.get("tile_vertical_unit"),
                                     record.get("tile_vertical_unit_rule"))
                        for record in records})
                if from_header else definition.get("vertical_unit")),
            "source_crs": (
                sorted({str(record.get("tile_crs")) for record in records})
                if from_header else "EPSG:%d" % int(float(
                    definition.get("source_crs")))),
            "datum_note": (
                "Elevations are in the source vertical datum; lidar is "
                "treated as truth and is NOT shifted toward the base DEM."
            ),
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            "native_resolution_m": definition.get("native_resolution_m"),
            "resolution_m": target_resolution_m,
        }
        core = las_core_geometry(definition)
        if core is not None:
            # THE SURGICAL CORE (spec §4): what the ladder assembles the
            # two-layer inset around.  The raster above covers the whole
            # request box; outside the core's tiles it is NoData.
            provenance["core"] = {
                "provider": code,
                "bounding_box_wgs84": [round(v, 9) for v in core.bounds],
                "boundary_polygon_wgs84": definition.get(
                    LAS_FOOTPRINT_KEY),
                "footprint_buffer_m": _parse_float(
                    definition.get("footprint_buffer_m"), default=0.0),
                "tile_names": [source["source_id"] for source in present],
                "feather_m": _parse_float(
                    definition.get("core_feather_m"), default=None),
            }
        return provenance


_LAS_INDEX_FORMATS = (LAS_INDEX_FORMAT_ARCGIS, LAS_INDEX_FORMAT_TNM,
                      LAS_INDEX_FORMAT_OGR, LAS_INDEX_FORMAT_CWCB)


def _las_index_format(definition):
    """The definition's ``index_format`` (absent = ``arcgis``)."""
    return str((definition or {}).get("index_format")
               or LAS_INDEX_FORMAT_ARCGIS).strip().lower()


def _las_archive_member(definition):
    """The definition's ``archive_member`` (``las``), or ``""`` when its
    tiles are plain LAS/LAZ files."""
    return str((definition or {}).get("archive_member") or "").strip() \
        .lower()


def las_raw_tile_path(cache_directory, source):
    """Where a listed tile's raw point cloud is cached: ``<name>.las``,
    or ``<name>.laz`` when the tile URL is a LAZ file (#153)."""
    url = str(source.get("download_url") or "").split("?", 1)[0].lower()
    extension = ".laz" if url.endswith(".laz") else ".las"
    return os.path.join(cache_directory, source["source_id"] + extension)
