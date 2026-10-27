"""A mosaic warp that never reads a source the mosaic would hide (#1327).

Owner RULINGS 2026-10-26t: elevation is read only where the build uses it.
A later-wins mosaic of many remote rasters -- the SRSP lidar campaigns,
swissALTI3D's vintages of one tile -- spends most of its wall reading
sources whose every pixel a LATER source overwrites: one 10 m approach-ring
cell over Edinburgh read 18 campaign tiles in 150 s, and the same cell from
the 14 that carry overviews in 18 s, byte-identical; a Jura cell read 238
swissALTI3D tiles in 150 s and its 108 newest vintages in 10 s,
byte-identical (``docs/findings/inset-fetch-linsets.md`` section 1).

:func:`warp_sources_skipping_hidden` keeps the mosaic order as the law and
walks it from the END.  The sources are cut into CONTIGUOUS chunks
(:func:`contiguous_layers`); the last chunk is warped over the whole box
exactly as before; every earlier chunk is warped only from the members
whose footprint still touches a pixel without data, over the same box on
the same grid, and it fills nothing but those holes.  Because the chunks are contiguous, a filled pixel takes the value
the single mosaic would have given it -- except where GDAL would have
BLENDED a later source's partial-density edge pixel over an earlier one,
which is within the provider's own fetch-to-fetch noise.

A source whose footprint is unknown (``None``) is taken to cover the whole
box: it shares a chunk with nothing and is skipped only once no pixel
lacks data.
"""

import os
import shutil
import tempfile

import numpy

from elevation_access import fetch_scratch
from elevation_access.gdal_support import gdal, has_gdal
from elevation_access.warp import warp_vsicurl_sources_to_geotiff

__all__ = [
    "LAYER_OVERLAP_FRACTION",
    "contiguous_layers",
    "hidden_sources_record",
    "warp_sources_skipping_hidden",
]

#: The warp's nodata (``warp_vsicurl_sources_to_geotiff`` writes it).
_NODATA = -32768.0

#: Two footprints overlap -- and so cannot share a chunk -- when their
#: intersection holds more than this fraction of the smaller one.  A
#: projected 1 km tile's WGS84 hull overlaps its NEIGHBOUR's by a sliver
#: (a few per cent); a re-flown vintage or a nested campaign square
#: overlaps by 100 %.  Only efficiency rides on it: chunks stay contiguous
#: in mosaic order whatever it is, so the result does not.
LAYER_OVERLAP_FRACTION = 0.2

#: Hole bookkeeping is kept per block of this many pixels on a side.
_BLOCK = 16

#: Rows read at once when the destination is scanned or filled.
_STRIP_ROWS = 512


def _overlap_fraction(first, second):
    """Intersection area over the smaller box's area (degrees squared)."""
    west = max(first[0], second[0])
    south = max(first[1], second[1])
    east = min(first[2], second[2])
    north = min(first[3], second[3])
    if east <= west or north <= south:
        return 0.0
    smaller = min(
        (first[2] - first[0]) * (first[3] - first[1]),
        (second[2] - second[0]) * (second[3] - second[1]),
    )
    if smaller <= 0.0:
        return 1.0
    return (east - west) * (north - south) / smaller


def contiguous_layers(footprints):
    """Cut mosaic positions ``0..n-1`` into contiguous chunks, LAST first.

    Walking from the end, a chunk closes when the next source overlaps
    (:data:`LAYER_OVERLAP_FRACTION`) a source already in it, or either
    footprint is unknown.  Each chunk lists its positions in mosaic order.
    """
    chunks = []
    current = []
    for index in reversed(range(len(footprints))):
        footprint = footprints[index]
        if current and any(
            footprint is None
            or footprints[other] is None
            or _overlap_fraction(footprint, footprints[other])
            > LAYER_OVERLAP_FRACTION
            for other in current
        ):
            chunks.append(sorted(current))
            current = []
        current.append(index)
    if current:
        chunks.append(sorted(current))
    return chunks


def _pixel_window(footprint, transform, columns, rows):
    """``(col0, row0, col1, row1)`` of ``footprint`` on the grid, clipped;
    ``None`` when it misses the grid.  A ``None`` footprint is the grid."""
    if footprint is None:
        return (0, 0, columns, rows)
    (origin_x, step_x, _a, origin_y, _b, step_y) = transform
    col0 = int(numpy.floor((footprint[0] - origin_x) / step_x))
    col1 = int(numpy.ceil((footprint[2] - origin_x) / step_x))
    row0 = int(numpy.floor((footprint[3] - origin_y) / step_y))
    row1 = int(numpy.ceil((footprint[1] - origin_y) / step_y))
    col0, col1 = max(col0, 0), min(col1, columns)
    row0, row1 = max(row0, 0), min(row1, rows)
    if col0 >= col1 or row0 >= row1:
        return None
    return (col0, row0, col1, row1)


def _block_range(window):
    (col0, row0, col1, row1) = window
    return (
        col0 // _BLOCK,
        row0 // _BLOCK,
        -(-col1 // _BLOCK),
        -(-row1 // _BLOCK),
    )


def _scan_holes(band, columns, rows, holes, window=None):
    """Set ``holes[block]`` to whether any pixel of the block lacks data,
    over ``window`` (block-aligned) or the whole band."""
    (col0, row0, col1, row1) = window or (0, 0, columns, rows)
    for strip in range(row0, row1, _STRIP_ROWS):
        height = min(_STRIP_ROWS, row1 - strip)
        values = band.ReadAsArray(col0, strip, col1 - col0, height)
        missing = values == _NODATA
        pad_rows = -height % _BLOCK
        pad_cols = -(col1 - col0) % _BLOCK
        if pad_rows or pad_cols:
            missing = numpy.pad(
                missing, ((0, pad_rows), (0, pad_cols)), constant_values=False
            )
        reduced = missing.reshape(
            missing.shape[0] // _BLOCK, _BLOCK, missing.shape[1] // _BLOCK,
            _BLOCK,
        ).any(axis=(1, 3))
        block_row = strip // _BLOCK
        holes[
            block_row:block_row + reduced.shape[0],
            col0 // _BLOCK:col0 // _BLOCK + reduced.shape[1],
        ] = reduced


def _fill_holes(band, scratch_band, window):
    """Copy ``scratch_band`` (the same grid) into ``band`` over
    ``window``, holes only."""
    (col0, row0, col1, row1) = window
    width = col1 - col0
    for strip in range(row0, row1, _STRIP_ROWS):
        height = min(_STRIP_ROWS, row1 - strip)
        values = band.ReadAsArray(col0, strip, width, height)
        fill = scratch_band.ReadAsArray(col0, strip, width, height)
        take = (values == _NODATA) & (fill != _NODATA)
        if take.any():
            values[take] = fill[take]
            band.WriteArray(values, col0, strip)


def warp_sources_skipping_hidden(
    sources,
    footprints,
    bounding_box_wgs84,
    target_resolution_m,
    destination_path,
    **warp_options,
):
    """:func:`warp_vsicurl_sources_to_geotiff` of ``sources`` (mosaic
    order, later wins) without reading a source the mosaic hides.

    ``footprints`` -- one ``(west, south, east, north)`` WGS84 box per
    source, or ``None`` for one whose extent is unknown.  ``warp_options``
    pass through to every warp (nodata, vertical unit, GDAL options...).
    Returns ``(ok, read)``: the warp's own success answer and the
    positions of the sources actually warped.
    """
    sources = list(sources)
    if footprints is None or len(footprints) != len(sources):
        footprints = [None] * len(sources)
    chunks = contiguous_layers(footprints)
    if not has_gdal or len(chunks) < 2:
        ok = warp_vsicurl_sources_to_geotiff(
            sources, bounding_box_wgs84, target_resolution_m,
            destination_path, **warp_options)
        return (ok, list(range(len(sources))))
    read = list(chunks[0])
    if not warp_vsicurl_sources_to_geotiff(
        [sources[index] for index in chunks[0]], bounding_box_wgs84,
        target_resolution_m, destination_path, **warp_options,
    ):
        return (False, read)
    try:
        dataset = gdal.Open(destination_path, gdal.GA_Update)
    except RuntimeError:
        dataset = None
    if dataset is None:
        # Not a raster this function can fill (never so for a real warp):
        # the single mosaic, as before.
        ok = warp_vsicurl_sources_to_geotiff(
            sources, bounding_box_wgs84, target_resolution_m,
            destination_path, **warp_options)
        return (ok, list(range(len(sources))))
    scratch = tempfile.mkdtemp(
        prefix="layered.", dir=_ensured(fetch_scratch.scratch_root()))
    try:
        band = dataset.GetRasterBand(1)
        transform = dataset.GetGeoTransform()
        (columns, rows) = (dataset.RasterXSize, dataset.RasterYSize)
        holes = numpy.zeros(
            (-(-rows // _BLOCK), -(-columns // _BLOCK)), dtype=bool)
        _scan_holes(band, columns, rows, holes)
        for number, chunk in enumerate(chunks[1:], start=1):
            if not holes.any():
                break
            wanted = numpy.zeros_like(holes)
            members = []
            for index in chunk:
                window = _pixel_window(
                    footprints[index], transform, columns, rows)
                if window is None:
                    continue
                (b0, r0, b1, r1) = _block_range(window)
                if holes[r0:r1, b0:b1].any():
                    members.append(index)
                    wanted[r0:r1, b0:b1] = True
            target = wanted & holes
            if not members or not target.any():
                continue
            block_rows = numpy.flatnonzero(target.any(axis=1))
            block_cols = numpy.flatnonzero(target.any(axis=0))
            window = (
                int(block_cols[0]) * _BLOCK,
                int(block_rows[0]) * _BLOCK,
                min(int(block_cols[-1] + 1) * _BLOCK, columns),
                min(int(block_rows[-1] + 1) * _BLOCK, rows),
            )
            band.FlushCache()
            scratch_path = os.path.join(scratch, "chunk%d.tif" % number)
            # The SAME box and resolution as the first warp, never a window
            # of it: GDAL warps each source over that source's own window
            # of the output, so its pixels land exactly where the single
            # mosaic put them (a window warp shifts the approximate
            # transformer's segments -- measured: mm everywhere, metres on
            # cliffs).
            if not warp_vsicurl_sources_to_geotiff(
                [sources[index] for index in members], bounding_box_wgs84,
                target_resolution_m, scratch_path, **warp_options,
            ):
                continue
            read.extend(members)
            filled = gdal.Open(scratch_path)
            try:
                _fill_holes(band, filled.GetRasterBand(1), window)
            finally:
                filled = None
            _scan_holes(band, columns, rows, holes, window)
        band.FlushCache()
    except BaseException:
        # A raised fill (a transient outage, a Stop) must not leave a
        # raster holding only the last chunk where a reader would take it
        # for the whole answer.
        dataset = None
        _remove_quietly(destination_path)
        raise
    finally:
        dataset = None
        shutil.rmtree(scratch, ignore_errors=True)
    return (True, sorted(read))


def _remove_quietly(path):
    try:
        os.remove(path)
    except OSError:
        pass


def hidden_sources_record(listed, read):
    """The provenance key a strategy adds: how many LISTED sources the
    mosaic hid and the warp never read (``{}`` when none)."""
    skipped = int(listed) - len(read)
    return {"hidden_sources_skipped": skipped} if skipped > 0 else {}


def _ensured(folder):
    os.makedirs(folder, exist_ok=True)
    return folder
