"""Water masks for a DRAPED World-pack tile (``O4_World_Drape``,
``world.py drape --water-alpha``): partially transparent orthophoto over
water, opaque over land, like a regular build's water overlay.

A regular build puts the photo over its water triangles as a second,
non-physical terrain patch whose ``.ter`` carries the tile's water mask
(``O4_DSF_Utils.create_terrain_file``: ``BORDER_TEX`` + ``WET``).  A drape
is an OVERLAY DSF, where mesh patches are not allowed (Laminar, "DSF
Usage in X-Plane"), so the only carrier is the draped polygon itself: the
mask goes into the DDS alpha (the engine's ``imprint_masks_to_dds``
path of ``O4_Imagery_Utils.convert_texture``) and a second ``.pol`` per
water square draws that DXT5 with its alpha on a layer group above the
default ground (``O4_World_Drape.write_drape(water_layer=...)``).

The mask is the regular build's own inland compositor
(``O4_Mask_Utils._build_inland_shore_mask``: land opaque, the shore
feather of ``inland_shore_feather_m``, floored at the ``ratio_water``
grey) run over a pre-mask rasterised from the tile's OSM water
(``O4_Vector_Map.cached_water_multipolygon``, the one reader of the
``water`` layer) instead of from mesh triangles, since a drape has no
mesh.  A square that is all water takes the constant grey, as a regular
build's ``water_transition`` blend does.  Sea (coastline) squares are not
masked here: the sea fade needs the coastline partition and is left to a
later round.
"""
from __future__ import annotations

import os
import time

import numpy
import O4_Geo_Utils as GEO
from PIL import Image, ImageDraw

__all__ = ["tile_water", "square_mask", "write_masks"]

#: Pixels of context around a square for the shore feather (the ramp
#: looks at most ``4 * feather + 8`` pixels away, ``O4_Shore_Feather``).
_MARGIN = 64


def tile_water(tile):
    """The tile's inland water, tile-relative degrees (shapely), from the
    ``water`` OSM layer: read from the cache, fetched once (local regional
    extract or Overpass, the build's own query) when nothing is on disk.
    ``None`` when no data could be had."""
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP
    area = VMAP.cached_water_multipolygon(tile)
    if area is None:
        layer = OSM.OSM_layer()
        if not OSM.OSM_queries_to_OSM_layer(
                VMAP.WATER_QUERIES, layer, tile.lat, tile.lon,
                VMAP.WATER_TAGS_OF_INTEREST, cached_suffix="water",
                cache_schema=VMAP.WATER_CACHE_TAG_SCHEMA):
            return None
        area = VMAP.cached_water_multipolygon(tile)
    return area


def _pixels(coords, lat, lon, pzl, origin):
    """Tile-relative (x, y) degrees -> pixel (column, row) on the canvas
    whose top-left pixel at zoom ``pzl`` is ``origin``."""
    pts = numpy.asarray(coords, dtype=numpy.float64)
    rat_x = (pts[:, 0] + lon) / 180
    rat_y = numpy.log(numpy.tan((90 + pts[:, 1] + lat) * numpy.pi / 360)) / numpy.pi
    scale = 2 ** (pzl + 7)
    return list(zip(((rat_x + 1) * scale - origin[0]).tolist(),
                    ((1 - rat_y) * scale - origin[1]).tolist()))


def square_mask(area, lat: int, lon: int, til_x: int, til_y: int, zl: int,
                px: int, sea_level: int, feather_px: int):
    """The ``px`` x ``px`` mask (uint8, 255 = opaque photo) of texture
    square (til_x, til_y) at ``zl``, or ``None`` when no water reaches it."""
    import O4_Mask_Utils as MASK
    import O4_Vector_Utils as VECT
    import shapely
    pzl = zl - int(round(numpy.log2(4096 / px)))
    step = 2 ** (zl - pzl)
    origin = (til_x * 256 // step - _MARGIN, til_y * 256 // step - _MARGIN)
    north, west = GEO.pix_to_wgs84(origin[0], origin[1], pzl)
    side = px + 2 * _MARGIN
    south, east = GEO.pix_to_wgs84(origin[0] + side, origin[1] + side, pzl)
    near = shapely.clip_by_rect(area, west - lon, south - lat, east - lon,
                                north - lat)
    if near.is_empty:
        return None
    canvas = Image.new("L", (side, side), 255)
    draw = ImageDraw.Draw(canvas)
    for pol in VECT.ensure_MultiPolygon(near).geoms:
        if pol.is_empty:
            continue
        draw.polygon(_pixels(pol.exterior.coords, lat, lon, pzl, origin),
                     fill=int(sea_level))
        for ring in pol.interiors:
            draw.polygon(_pixels(ring.coords, lat, lon, pzl, origin), fill=255)
    pre = numpy.array(canvas, dtype=numpy.uint8)
    inner = pre[_MARGIN:-_MARGIN, _MARGIN:-_MARGIN]
    if (inner == 255).all():
        return None
    mask = MASK._build_inland_shore_mask(pre, sea_level, feather_px, _MARGIN)
    if mask is None:            # all water, or feather off: the flat blend
        mask = numpy.where(inner == 255, 255, int(sea_level)).astype(numpy.uint8)
    return mask


def write_masks(tile, squares, zl: int, provider: str, px: int) -> dict:
    """Write the mask of every square of ``squares`` that touches water
    into ``tile.build_dir/textures`` under the engine's mask name
    (``FNAMES.mask_file``), where ``convert_texture`` imprints it into a
    DXT5 when ``tile.imprint_masks_to_dds`` is set.  Returns counts and
    seconds."""
    import O4_File_Names as FNAMES
    import O4_Mask_Utils as MASK
    t0 = time.time()
    area = tile_water(tile)
    t1 = time.time()
    if area is not None and not area.is_valid:   # OSM rings cross (seen
        import shapely  # at +54-063): repair once
        from shapely.geometry import MultiPolygon
        parts = shapely.get_parts(shapely.make_valid(area))
        area = MultiPolygon([q for p in parts for q in shapely.get_parts(p)
                             if q.geom_type == "Polygon"])
    out = {"water_data": area is not None, "masked": 0,
           "water_fetch_s": round(t1 - t0, 1)}
    if area is None or area.is_empty:
        out["mask_s"] = 0.0
        return out
    im = Image.open(os.path.join(FNAMES.Utils_dir, "water_transition.png"))
    sea_level = im.getpixel((0, 127 * (1 - min(1, 0.1 + tile.ratio_water))))
    pzl = zl - int(round(numpy.log2(4096 / px)))
    feather_px = int(MASK._inland_shore_feather_m(tile)
                     / GEO.webmercator_pixel_size(tile.lat + 0.5, pzl))
    tex = os.path.join(tile.build_dir, "textures")
    for til_x, til_y in squares:
        mask = square_mask(area, tile.lat, tile.lon, til_x, til_y, zl, px,
                           sea_level, feather_px)
        if mask is None:
            continue
        Image.fromarray(mask).save(os.path.join(
            tex, FNAMES.mask_file(til_x, til_y, zl, provider)))
        out["masked"] += 1
    out["mask_s"] = round(time.time() - t1, 1)
    return out
