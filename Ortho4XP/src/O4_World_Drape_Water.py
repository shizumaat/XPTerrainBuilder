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
feather of ``inland_shore_feather_m``, floored at the open-water grey)
run over a pre-mask rasterised from the tile's water instead of from
mesh triangles, since a drape has no mesh.  The open-water grey is
:data:`OPEN_WATER_ALPHA` (RULINGS 2026-11-11j (2): 135/255, halfway
between the regular build's 99 and the flown 170); a square that is all
water takes it flat.  The water is the tile's OSM ``water`` layer
(``O4_Vector_Map.cached_water_multipolygon``, the one reader of it) and
its sea, closed from the ``coastline`` layer by the build's own
partition (``O4_Vector_Map.cached_coastline_multilinestring`` +
``sea_area_from_coastline``); both are fetched once when nothing is on
disk.  :func:`_start_water` runs that fetch on a thread so it overlaps the
photo download (``O4_World_Drape_Fetch``).
"""
from __future__ import annotations

import os
import threading
import time

import numpy
import O4_Geo_Utils as GEO
from PIL import Image, ImageDraw

__all__ = ["OPEN_WATER_ALPHA", "tile_water", "square_mask", "start_masks"]

#: Photo opacity over open water on a drape's water copy, 0-255 (RULINGS
#: 2026-11-11j (2), owner 14:17Z "halfway between those two": the regular
#: build's 99 and the flown 170).  The one constant: no setting, no knob.
OPEN_WATER_ALPHA = 135

#: Pixels of context around a square for the shore feather (the ramp
#: looks at most ``4 * feather + 8`` pixels away, ``O4_Shore_Feather``).
_MARGIN = 64


def _layer(tile, queries, tags, suffix, schema=None) -> bool:
    """Fetch one OSM layer of the tile into its cache (local regional
    extract or Overpass, the build's own query); False when it failed."""
    import O4_OSM_Utils as OSM
    kw = {"cache_schema": schema} if schema is not None else {}
    return bool(OSM.OSM_queries_to_OSM_layer(
        queries, OSM.OSM_layer(), tile.lat, tile.lon, tags,
        cached_suffix=suffix, **kw))


def _inland(tile):
    import O4_Vector_Map as VMAP
    area = VMAP.cached_water_multipolygon(tile)
    if area is None and _layer(tile, VMAP.WATER_QUERIES,
                               VMAP.WATER_TAGS_OF_INTEREST, "water",
                               VMAP.WATER_CACHE_TAG_SCHEMA):
        area = VMAP.cached_water_multipolygon(tile)
    return area


def _sea(tile):
    """The tile's sea (tile-relative), or ``None`` (no coastline data or
    none in the tile: the default mesh's own water stays as it is)."""
    import O4_Vector_Map as VMAP
    coast, custom = VMAP.cached_coastline_multilinestring(tile)
    if coast is None and not custom and _layer(
            tile, VMAP.COASTLINE_QUERIES, [], "coastline"):
        coast, custom = VMAP.cached_coastline_multilinestring(tile)
    if coast is None:
        return None
    sea = VMAP.sea_area_from_coastline(coast, tile.lat, tile.lon, custom)
    return None if sea.is_empty else sea


def _valid(area):
    """``area`` repaired to polygons once (OSM rings cross, seen at
    +54-063)."""
    if area is None or area.is_valid:
        return area
    import shapely
    from shapely.geometry import MultiPolygon
    parts = shapely.get_parts(shapely.make_valid(area))
    return MultiPolygon([q for p in parts for q in shapely.get_parts(p)
                         if q.geom_type == "Polygon"])


def _union(inland, sea):
    inland, sea = _valid(inland), _valid(sea)
    if sea is None:
        return inland
    return sea if inland is None else _valid(inland.union(sea))


def _thread(fn, tile) -> "callable":
    """Run ``fn(tile)`` on a thread; the returned callable
    ``join(timeout=None)`` gives ``(result, seconds)`` (``None`` while
    it still runs), re-raising what the thread raised."""
    box: dict = {}

    def work() -> None:
        t0 = time.time()
        try:
            box["value"] = fn(tile)
        except BaseException as error:  # handed to the joiner
            box["error"] = error
        box["s"] = round(time.time() - t0, 1)
    thread = threading.Thread(target=work, daemon=True, name="o4-drape-water")
    thread.start()

    def join(timeout=None):
        thread.join(timeout)
        if thread.is_alive():
            return None
        if "error" in box:
            raise box["error"]
        return box.get("value"), box.get("s", 0.0)
    return join


def _sea_or_none(tile):
    try:
        return _sea(tile)
    except Exception:                   # no sea: inland water still masks
        return None


def tile_water(tile):
    """The tile's water, tile-relative degrees (shapely): its inland OSM
    water and its sea (see the module), read from the cache, each layer
    fetched once when nothing is on disk.  ``None`` when no data could be
    had."""
    return _union(_inland(tile), _sea_or_none(tile))


def _start_water(tile):
    """Start the tile's water (:func:`tile_water`) on two threads, inland
    and sea at once, so the fetch overlaps the photo download; the
    returned callable ``join(timeout=None)`` gives ``(area, seconds)``,
    re-raising what a thread raised; past ``timeout`` seconds it gives
    ``(None, None)`` and leaves the threads to fill the cache."""
    t0 = time.time()
    inland, sea = _thread(_inland, tile), _thread(_sea_or_none, tile)

    def join(timeout=None):
        end = None if timeout is None else t0 + float(timeout)
        parts = []
        for joiner in (inland, sea):
            left = None if end is None else max(0.0, end - time.time())
            part = joiner(left)
            if part is None:
                return None, None
            parts.append(part)
        (a, a_s), (b, b_s) = parts
        return _union(a, b), max(a_s, b_s)
    return join


def _pixels(coords, lat, lon, pzl, origin):
    """Tile-relative (x, y) degrees -> pixel (column, row) on the canvas
    whose top-left pixel at zoom ``pzl`` is ``origin``."""
    pts = numpy.asarray(coords, dtype=numpy.float64)
    rat_x = (pts[:, 0] + lon) / 180
    rat_y = numpy.log(numpy.tan((90 + pts[:, 1] + lat) * numpy.pi / 360)) / numpy.pi
    scale = 2 ** (pzl + 7)
    return list(zip(((rat_x + 1) * scale - origin[0]).tolist(),
                    ((1 - rat_y) * scale - origin[1]).tolist(), strict=True))


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


def start_masks(tile, squares, zl: int, provider: str, px: int):
    """:func:`_write_masks` on a thread (the water read and the masks both
    overlap the photo download; a 4096 px tile's masks took 213 s); the
    returned callable ``join(timeout=None)`` gives its result, or ``None``
    while it still runs."""
    joiner = _thread(lambda t: _write_masks(t, squares, zl, provider, px),
                     tile)

    def join(timeout=None):
        done = joiner(timeout)
        return None if done is None else done[0]
    return join


def _write_masks(tile, squares, zl: int, provider: str, px: int,
                water=None) -> dict:
    """Write the mask of every square of ``squares`` that touches water
    into ``tile.build_dir/textures`` under the engine's mask name
    (``FNAMES.mask_file``), where ``convert_texture`` imprints it into a
    DXT5 when ``tile.imprint_masks_to_dds`` is set.  ``water`` is a
    :func:`_start_water` joiner (else the water is read here).  Returns
    counts and seconds."""
    import O4_File_Names as FNAMES
    import O4_Mask_Utils as MASK
    t0 = time.time()
    area, fetch_s = (water or _start_water(tile))()
    t1 = time.time()
    out = {"water_data": area is not None, "masked": 0,
           "water_fetch_s": fetch_s, "water_wait_s": round(t1 - t0, 1)}
    if area is None or area.is_empty:
        out["mask_s"] = 0.0
        return out
    pzl = zl - int(round(numpy.log2(4096 / px)))
    feather_px = int(MASK._inland_shore_feather_m(tile)
                     / GEO.webmercator_pixel_size(tile.lat + 0.5, pzl))
    tex = os.path.join(tile.build_dir, "textures")
    for til_x, til_y in squares:
        mask = square_mask(area, tile.lat, tile.lon, til_x, til_y, zl, px,
                           OPEN_WATER_ALPHA, feather_px)
        if mask is None:
            continue
        Image.fromarray(mask).save(os.path.join(
            tex, FNAMES.mask_file(til_x, til_y, zl, provider)))
        out["masked"] += 1
    out["mask_s"] = round(time.time() - t1, 1)
    return out
