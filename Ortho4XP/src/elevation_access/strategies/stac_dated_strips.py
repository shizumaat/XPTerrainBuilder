"""Composite DATED elevation strips from a STAC search, newest first.

The ``stac_dated_strips`` access strategy
(:class:`StacDatedStripsStrategy`), shipped with ARCTICDEM2M.elv (PGC
ArcticDEM v4.1 2 m strips).  A strip collection is not a mosaic: each item
is one stereo pair's surface model on its acquisition date, with a
quality bitmask beside it, and many strips overlap the same ground.  A
mosaic built years ago predates whatever was built since (Nuuk's new
runway, opened 2024, is in the strips and not in the 2023 mosaic), so this
strategy builds its own:

1. search the box (the ``stac`` strategy's search, plus the definition's
   optional ``search_datetime`` interval);
2. order the strips NEWEST FIRST by acquisition date;
3. read each strip's surface model and bitmask over the box; a cell is
   valid where the bitmask is 0 (PGC: edge, water and cloud are bits);
4. fill only the cells no newer strip filled, until every cell is filled
   or the strips run out (``max_strips`` bounds the reads).

Which strip filled each cell is recorded in the provenance
(``strip_provenance``: the strips with their dates and cell counts, plus
the per-cell index grid, zlib-compressed).  Heights stay in the source
datum here; the ``geoid_shift`` key (:mod:`elevation_access.geoid_shift`)
reduces them after the fetch.
"""

import base64
import datetime
import os
import zlib

import numpy

from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.registry import register_access_strategy
from elevation_access.stac_assets import _stac_asset_href_to_vsicurl
from elevation_access.strategies.stac import (
    StacCloudOptimizedGeoTiffStrategy,
)
from elevation_access.warp import warp_vsicurl_sources_to_geotiff

__all__ = [
    "NO_STRIP",
    "StacDatedStripsStrategy",
]


#: Index-grid value of a cell no strip filled.
NO_STRIP = -1


_NODATA = -32768.0


#: Bitmask value written where a strip does not reach the cell.
_MASK_OUTSIDE = 255


def strips_newest_first(items, dem_key, mask_key):
    """The items carrying both assets, newest acquisition first (ties by
    id, so the order is deterministic)."""
    usable = [
        item for item in items
        if ((item.get("assets") or {}).get(dem_key) or {}).get("href")
        and ((item.get("assets") or {}).get(mask_key) or {}).get("href")
    ]
    usable.sort(key=lambda item: str(item.get("id")))
    usable.sort(key=_acquired, reverse=True)
    return usable


def _acquired(item):
    """The item's acquisition instant as a sortable UTC string."""
    properties = item.get("properties") or {}
    stamp = properties.get("datetime") or properties.get("start_datetime")
    try:
        parsed = datetime.datetime.fromisoformat(
            str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return parsed.isoformat()


def fill_from_strip(composite, strip_index, values, bitmask, number):
    """Fill the composite's empty cells from one strip, in place.

    A strip cell is used when its value is valid and its bitmask is 0;
    cells a newer strip already filled are never overwritten.  Returns
    the number of cells this strip filled."""
    usable = (
        (strip_index == NO_STRIP)
        & (bitmask == 0)
        & numpy.isfinite(values)
        & (values != _NODATA)
    )
    composite[usable] = values[usable]
    strip_index[usable] = number
    return int(usable.sum())


def encode_strip_index(strip_index):
    """The per-cell strip index as a JSON-safe record."""
    raw = numpy.ascontiguousarray(strip_index, dtype="<i2").tobytes()
    return {
        "rows": int(strip_index.shape[0]),
        "columns": int(strip_index.shape[1]),
        "encoding": "zlib+base64, int16 little-endian, row-major from "
                    "the north-west cell; -1 = no strip",
        "data": base64.b64encode(zlib.compress(raw, 9)).decode("ascii"),
    }


def decode_strip_index(record):
    """The per-cell strip index array of an :func:`encode_strip_index`
    record."""
    raw = zlib.decompress(base64.b64decode(record["data"]))
    return numpy.frombuffer(raw, dtype="<i2").reshape(
        record["rows"], record["columns"]).astype(numpy.int16)


def _warp_bitmask(href, like_dataset):
    """The strip's bitmask on ``like_dataset``'s grid (nearest);
    255 where the strip does not reach."""
    (left, step_x, _rx, top, _ry, step_y) = like_dataset.GetGeoTransform()
    columns = like_dataset.RasterXSize
    rows = like_dataset.RasterYSize
    warped = gdal.Warp(
        "", _stac_asset_href_to_vsicurl(href),
        options=gdal.WarpOptions(
            format="MEM", dstSRS="EPSG:4326", outputType=gdal.GDT_Byte,
            outputBounds=(left, top + rows * step_y,
                          left + columns * step_x, top),
            width=columns, height=rows, resampleAlg="near",
            dstNodata=_MASK_OUTSIDE),
    )
    if warped is None:
        return numpy.full((rows, columns), _MASK_OUTSIDE, dtype=numpy.uint8)
    return warped.GetRasterBand(1).ReadAsArray()


def _holes_bbox(strip_index, geotransform):
    """The lon/lat box of the still-empty cells, or ``None``."""
    (rows, columns) = numpy.nonzero(strip_index == NO_STRIP)
    if rows.size == 0:
        return None
    (left, step_x, _rx, top, _ry, step_y) = geotransform
    return (left + columns.min() * step_x, top + (rows.max() + 1) * step_y,
            left + (columns.max() + 1) * step_x, top + rows.min() * step_y)


def _item_reaches(item, box):
    """Does the item's footprint bbox meet ``box`` (west,south,east,north)?
    Items without a readable bbox are assumed to."""
    bbox = item.get("bbox")
    if not bbox or len(bbox) < 4:
        return True
    return not (bbox[2] < box[0] or bbox[0] > box[2]
                or bbox[3] < box[1] or bbox[1] > box[3])


@register_access_strategy("stac_dated_strips")
class StacDatedStripsStrategy(StacCloudOptimizedGeoTiffStrategy):
    """Newest-valid-first composite of dated strips (module docstring)."""

    # One composite of up to max_strips strip reads is an airport-box
    # job; a whole-tile overlay would read every strip of a degree cell.
    supports_wide_area = False

    _DEFAULT_MAX_STRIPS = 40

    def _search_url_and_body(self, definition, bounding_box_wgs84):
        (url, body, collections, bbox) = super()._search_url_and_body(
            definition, bounding_box_wgs84)
        interval = str(definition.get("search_datetime") or "").strip()
        if interval:
            body["datetime"] = interval
        return (url, body, collections, bbox)

    def fetch(self, definition, bounding_box_wgs84, target_resolution_m,
              destination_path):
        if not has_gdal:
            return None
        items = self.discover(definition, bounding_box_wgs84)
        if not items:
            return None
        dem_key = definition.get("strip_asset_key", "dem")
        mask_key = definition.get("strip_mask_asset_key", "mask")
        strips = strips_newest_first(items, dem_key, mask_key)
        max_strips = int(float(definition.get(
            "max_strips", self._DEFAULT_MAX_STRIPS)))
        state = self._composite(definition, strips[:max_strips],
                                bounding_box_wgs84, target_resolution_m,
                                destination_path)
        if state is None:
            return None
        return self._record(definition, items, state, bounding_box_wgs84,
                            target_resolution_m)

    def _composite(self, definition, strips, bounding_box_wgs84,
                   target_resolution_m, destination_path):
        """Read strips newest first into ``destination_path``; the
        composite state, or ``None`` when no strip gave a cell."""
        scratch = destination_path + ".strip.tif"
        composite = strip_index = dataset = None
        used = []
        try:
            for strip in strips:
                if strip_index is not None:
                    holes = _holes_bbox(strip_index,
                                        dataset.GetGeoTransform())
                    if holes is None:
                        break
                    if not _item_reaches(strip, holes):
                        continue
                assets = strip["assets"]
                if not warp_vsicurl_sources_to_geotiff(
                        [_stac_asset_href_to_vsicurl(assets[
                            definition.get("strip_asset_key", "dem")]["href"])],
                        bounding_box_wgs84, target_resolution_m, scratch,
                        value_floor_m=float(definition.get(
                            "value_floor_m", -600.0)),
                        provider_code=definition.get("code")):
                    continue
                strip_dataset = gdal.Open(scratch)
                values = strip_dataset.GetRasterBand(1).ReadAsArray()
                if composite is None:
                    dataset = gdal.GetDriverByName("MEM").CreateCopy(
                        "", strip_dataset)
                    composite = numpy.full(values.shape, _NODATA,
                                           dtype=numpy.float32)
                    strip_index = numpy.full(values.shape, NO_STRIP,
                                             dtype=numpy.int16)
                bitmask = _warp_bitmask(assets[definition.get(
                    "strip_mask_asset_key", "mask")]["href"], strip_dataset)
                strip_dataset = None
                filled = fill_from_strip(composite, strip_index, values,
                                         bitmask, len(used))
                used.append((strip, filled))
        finally:
            if os.path.exists(scratch):
                os.remove(scratch)
        if composite is None or not (strip_index != NO_STRIP).any():
            return None
        band = dataset.GetRasterBand(1)
        band.WriteArray(composite)
        band.SetNoDataValue(_NODATA)
        gdal.GetDriverByName("GTiff").CreateCopy(
            destination_path, dataset,
            options=["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"])
        return {"used": used, "strip_index": strip_index,
                "geotransform": list(dataset.GetGeoTransform())}

    @staticmethod
    def _record(definition, items, state, bounding_box_wgs84,
                target_resolution_m):
        strip_index = state["strip_index"]
        cells = int(strip_index.size)
        strips = [{
            "number": number,
            "id": strip.get("id"),
            "acquired": (strip.get("properties") or {}).get("datetime"),
            "cells_filled": filled,
        } for (number, (strip, filled)) in enumerate(state["used"])]
        index_record = encode_strip_index(strip_index)
        index_record["geotransform"] = state["geotransform"]
        return {
            "provider": definition.get("code"),
            "access_strategy": definition.get("access_strategy"),
            "source_ids": [strip["id"] for strip in strips
                           if strip["cells_filled"]],
            "collections": [
                token.strip() for token in
                str(definition.get("collections", "")).split(",")
                if token.strip()],
            "native_resolution_m": definition.get("native_resolution_m"),
            "license": definition.get("license"),
            "attribution": definition.get("attribution"),
            "vertical_datum": definition.get("vertical_datum"),
            "strip_provenance": {
                "order": "newest acquisition first; a cell takes the "
                         "newest strip whose bitmask is 0 there",
                "strips_listed": len(items),
                "strips": strips,
                "covered_fraction": round(
                    float((strip_index != NO_STRIP).sum()) / cells, 6),
                "index_grid": index_record,
            },
            "fetch_date": datetime.date.today().isoformat(),
            "bounding_box_wgs84": list(bounding_box_wgs84),
            "resolution_m": target_resolution_m,
        }
