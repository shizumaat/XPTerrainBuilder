"""Cutting a cached airport inset down to the box the build now reads.

Issue #1725, item 2.  Owner RULINGS 2026-10-26t (a) cut the inset FETCH
box to the graded reach (``inset_fetch_margin_m``, about 465 m beyond the
aerodrome boundary, where it had been 2,000 m) -- but a cached raster cut
for the old, larger box stays valid under THE RE-CUT RULE (a superset is
never stale), so it was kept for ever.  Measured 2026-11-02 on the shared
corpus with ``O4_Disk_Usage.private_bytes``: airport insets are 61.5 GB of
the 88 GB ``Elevation_data``; 1,325 of the 1,669 insets (56 GB) predate
the cut, and about 43 GB of their pixels lie outside the box a build asks
for today.  That is what made single 10-degree areas hold 7-11 GB.

THE TRIM RULE: a cached inset whose raster the required box keeps less
than :data:`TRIM_KEEP_FRACTION` of is cut, IN PLACE and with no download,
to the whole source pixels that cover the required box.  The pixels kept
are copied, never resampled (``srcWin``), so inside the box the raster is
the one a fresh fetch of the same source cuts; outside it the build
already stands on the approach ring, exactly as it does for a fresh fetch.
The sidecar then records the trimmed box as the requested one, so THE
RE-CUT RULE judges it like any fresh fetch, and the old box under
``trimmed_from_bounding_box_wgs84``.

A write the harness's shared-repo guard refuses is skipped (a build is
not a refresh event); so is anything GDAL cannot open.  Never raises.
"""
from __future__ import annotations

import datetime
import json
import math
import os

from elevation_access import fetch_scratch as FETCH_SCRATCH
from elevation_access.downloads import _write_refused_by_armed_guard
from elevation_access.gdal_support import gdal, has_gdal

__all__ = ["TRIM_KEEP_FRACTION", "kept_fraction", "trim_cached_inset"]

#: Trim when the required box keeps less than this share of the raster's
#: area: a trim frees at least a fifth of the file, and warp slack (a
#: delivered box a pixel off the request) never triggers one.
TRIM_KEEP_FRACTION = 0.8

#: GeoTIFF creation options of every inset the warp writes
#: (``elevation_access.warp``): the trimmed file keeps the same layout.
_CREATION_OPTIONS = ["COMPRESS=DEFLATE", "PREDICTOR=3", "TILED=YES"]


def _pixel_window(geotransform, columns, rows, box):
    """``(x0, y0, width, height)``: the whole pixels of a north-up raster
    that cover ``box`` (west, south, east, north), clipped to the raster;
    ``None`` when they cover nothing."""
    x0, dx, _r1, y0, _r2, dy = geotransform
    west, south, east, north = box
    col0 = max(0, int(math.floor((west - x0) / dx + 1e-9)))
    col1 = min(columns, int(math.ceil((east - x0) / dx - 1e-9)))
    row0 = max(0, int(math.floor((north - y0) / dy + 1e-9)))
    row1 = min(rows, int(math.ceil((south - y0) / dy - 1e-9)))
    if col1 <= col0 or row1 <= row0:
        return None
    return (col0, row0, col1 - col0, row1 - row0)


def kept_fraction(geotransform, columns, rows, box):
    """The share of the raster's pixels the trim to ``box`` would keep
    (1.0 for a rotated or unreadable geometry: never trimmed)."""
    if geotransform[2] or geotransform[4] or geotransform[5] >= 0:
        return 1.0
    window = _pixel_window(geotransform, columns, rows, box)
    if window is None or columns * rows == 0:
        return 1.0
    return window[2] * window[3] / float(columns * rows)


def _rewrite_sidecar(sidecar_path, box, delivered):
    try:
        with open(sidecar_path, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, ValueError):
        return
    if not isinstance(meta, dict):
        return
    meta["trimmed_from_bounding_box_wgs84"] = meta.get(
        "requested_bounding_box_wgs84") or meta.get("bounding_box_wgs84")
    meta["requested_bounding_box_wgs84"] = list(box)
    meta["bounding_box_wgs84"] = list(box)
    meta["delivered_bounding_box_wgs84"] = list(delivered)
    meta["trim_date"] = datetime.date.today().isoformat()
    with open(sidecar_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(meta, handle, indent=2, sort_keys=True)


def trim_cached_inset(inset_path, sidecar_path, box,
                      keep_fraction=TRIM_KEEP_FRACTION):
    """THE TRIM RULE on one cached inset (see the module docstring).

    Returns the bytes the file shrank by, or 0 when it was left alone
    (already small enough, guarded, unreadable, or the cut failed)."""
    if not has_gdal or not os.path.isfile(inset_path):
        return 0
    if (_write_refused_by_armed_guard(inset_path)
            or _write_refused_by_armed_guard(sidecar_path)):
        return 0
    try:
        dataset = gdal.Open(inset_path)
        if dataset is None:
            return 0
        geotransform = dataset.GetGeoTransform()
        columns, rows = dataset.RasterXSize, dataset.RasterYSize
        if kept_fraction(geotransform, columns, rows, box) >= keep_fraction:
            return 0
        window = _pixel_window(geotransform, columns, rows, box)
        scratch = FETCH_SCRATCH.scratch_destination(inset_path)
        try:
            out = gdal.Translate(scratch, dataset, srcWin=list(window),
                                 creationOptions=_CREATION_OPTIONS)
            if out is None:
                return 0
            out_geotransform = out.GetGeoTransform()
            delivered = (
                out_geotransform[0],
                out_geotransform[3] + out.RasterYSize * out_geotransform[5],
                out_geotransform[0] + out.RasterXSize * out_geotransform[1],
                out_geotransform[3])
            out = None
            dataset = None
            before = os.path.getsize(inset_path)
            FETCH_SCRATCH.land(scratch, inset_path)
        finally:
            FETCH_SCRATCH.discard(scratch)
        stats = inset_path + ".aux.xml"         # statistics of the old cut
        if os.path.isfile(stats):
            os.remove(stats)
        _rewrite_sidecar(sidecar_path, box, delivered)
        return max(0, before - os.path.getsize(inset_path))
    except Exception:
        return 0
