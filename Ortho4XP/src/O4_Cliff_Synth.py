"""Make the cliff textures a build's DSF names (#2096), once its photos
are on disk.

For each region of the plan ``O4_Cliff_DSF.emit_cliff_overlays`` returned:

* its photos (the ones under it and under its exemplar candidates, at the
  primary photo's zoom level and provider) are laid side by side at a
  quarter of their resolution (:class:`_Mosaic`), and the region's
  triangles are rasterised onto them;
* the TARGET colour is the Lab mean of the LIT part of the footprint (its
  pixels at or above the footprint's 60th lightness percentile) and the
  spread of the whole footprint.  A face the photo has in shadow would
  otherwise be dark twice: X-Plane shades the face itself;
* the exemplar is the window of unstretched flank pixels nearest that
  colour (``O4_Cliff_Texture.pick_exemplar``), cut at full resolution from
  its photo, quilted into a seamless tile and colour-matched (lightness at
  least the exemplar's, spread at least 0.7 of the exemplar's: a smeared
  face has too little);
* the tile is written as a BC1 ``.dds`` with its mip chain, through the
  partial-name-and-land path every texture of the build takes.

A region with no photo on disk gets a flat tile of a neutral rock colour,
so the DSF never names a missing texture.
"""
from __future__ import annotations

import os
import time
from collections import OrderedDict

import numpy
import O4_Cliff_Texture as TEX
import O4_DDS_Encode as ENC
import O4_DDS_File as DDS
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

__all__ = ["synthesize"]

QUARTER = 4                 # mosaic / mask / search resolution: 1 / QUARTER
PHOTO_PX = 4096
CELL = PHOTO_PX // QUARTER
EXEMPLAR_PX = 192           # full-resolution exemplar window
TILE_PX = 512               # the face texture
LIT_PERCENTILE = 60
NEUTRAL_ROCK = (150, 140, 125)


def _pixel_coords(lonlat, attrs, size):
    """(..., 2) pixel (col, row) of lon/lat points in a ``size``-pixel
    rendering of photo ``attrs``; beyond its edges for points beyond."""
    til_x, til_y, zl = attrs[0], attrs[1], attrs[2]
    lon, lat = lonlat[..., 0], lonlat[..., 1]
    mult = 2 ** (zl - 5)
    s = (lon / 180 + 1) * mult - til_x // 16
    ratio_y = numpy.log(numpy.tan((90 + lat) * numpy.pi / 360)) / numpy.pi
    t = 1 - ((1 - ratio_y) * mult - til_y // 16)
    return numpy.stack((s * size, (1 - t) * size), -1)


class _Photos:
    """Photos of a build read from its ``textures`` folder: the last few at
    full resolution, many more at a quarter."""

    def __init__(self, tile, keep_full=2, keep_small=64):
        self.folder = os.path.join(tile.build_dir, "textures")
        self.full, self.small = OrderedDict(), OrderedDict()
        self.keep_full, self.keep_small = keep_full, keep_small

    def _remember(self, cache, key, value, keep):
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > keep:
            cache.popitem(last=False)
        return value

    def full_res(self, attrs):
        if attrs in self.full:
            self.full.move_to_end(attrs)
            return self.full[attrs]
        from PIL import Image
        path = os.path.join(self.folder,
                            FNAMES.dds_file_name_from_attributes(*attrs))
        try:
            with Image.open(path) as im:
                rgb = numpy.asarray(im.convert("RGB"))
        except OSError:
            rgb = None
        if rgb is not None and rgb.shape[:2] != (PHOTO_PX, PHOTO_PX):
            rgb = None
        return self._remember(self.full, attrs, rgb, self.keep_full)

    def quarter(self, attrs):
        if attrs in self.small:
            self.small.move_to_end(attrs)
            return self.small[attrs]
        rgb = self.full_res(attrs)
        small = None if rgb is None else rgb[::QUARTER, ::QUARTER].copy()
        return self._remember(self.small, attrs, small, self.keep_small)


class _Mosaic:
    """A region's photos side by side at quarter resolution, on the grid
    of its primary photo (same zoom level and provider only)."""

    def __init__(self, photos, source):
        zl, provider = photos[0][2], photos[0][3]
        same = [a for a in photos if a[2] == zl and a[3] == provider]
        self.x0 = min(a[0] for a in same)
        self.y0 = min(a[1] for a in same)
        nx = (max(a[0] for a in same) - self.x0) // 16 + 1
        ny = (max(a[1] for a in same) - self.y0) // 16 + 1
        self.origin = (self.x0, self.y0, zl, provider)
        self.image = numpy.zeros((ny * CELL, nx * CELL, 3), numpy.uint8)
        self.have = numpy.zeros((ny * CELL, nx * CELL), bool)
        self.cells = {}
        for a in same:
            small = source.quarter(a)
            if small is None:
                continue
            r, c = (a[1] - self.y0) // 16 * CELL, (a[0] - self.x0) // 16 * CELL
            self.image[r:r + CELL, c:c + CELL] = small
            self.have[r:r + CELL, c:c + CELL] = True
            self.cells[(r // CELL, c // CELL)] = a
        self.source = source

    def raster(self, tris_lonlat):
        from PIL import Image, ImageDraw
        h, w = self.have.shape
        mask = Image.new("1", (w, h), 0)
        draw = ImageDraw.Draw(mask)
        for tri in _pixel_coords(tris_lonlat, self.origin, CELL):
            draw.polygon([tuple(p) for p in tri], fill=1)
        return numpy.asarray(mask, dtype=bool) & self.have

    def window(self, r, c, win):
        """The full-resolution EXEMPLAR_PX window at quarter-res ``(r, c)``
        (cut inside the one photo holding its centre)."""
        cr, cc = (r + win // 2) // CELL, (c + win // 2) // CELL
        photo = self.source.full_res(self.cells[(cr, cc)])
        fr = int(numpy.clip((r - cr * CELL) * QUARTER, 0, PHOTO_PX - EXEMPLAR_PX))
        fc = int(numpy.clip((c - cc * CELL) * QUARTER, 0, PHOTO_PX - EXEMPLAR_PX))
        return photo[fr:fr + EXEMPLAR_PX, fc:fc + EXEMPLAR_PX]


def _target(mosaic, foot_mask):
    """(lit mean, spread) of the footprint's Lab pixels."""
    lab = TEX.srgb_to_lab(mosaic.image[foot_mask])
    lit = lab[lab[:, 0] >= numpy.percentile(lab[:, 0], LIT_PERCENTILE)]
    return lit.mean(0), lab.std(0)


def _region_texture(mosaic, foot, exemplar, rng=None):
    """The face texture (TILE_PX square, uint8 RGB) of one region: its
    footprint and exemplar candidates are (k, 3, 2) lon/lat triangles."""
    foot_mask = mosaic.raster(foot)
    if foot_mask.sum() < 16:
        return None
    mean, spread = _target(mosaic, foot_mask)
    cand = mosaic.raster(exemplar) if len(exemplar) else None
    win = EXEMPLAR_PX // QUARTER
    at = None
    for fill in (0.85, 0.6, 0.35):
        if cand is None:
            break
        at = TEX.pick_exemplar(mosaic.image, cand, mean, win, min_fill=fill)
        if at is not None:
            break
    if at is None:      # no flank in reach: the footprint's own pixels
        rows, cols = numpy.nonzero(foot_mask)
        h, w = foot_mask.shape
        at = (int(numpy.clip(numpy.median(rows) - win // 2, 0, h - win)),
              int(numpy.clip(numpy.median(cols) - win // 2, 0, w - win)))
    ex = mosaic.window(at[0], at[1], win)
    tile_px = TEX.quilt(ex, size=TILE_PX, rng=rng)
    ex_lab = TEX.srgb_to_lab(ex[::2, ::2]).reshape(-1, 3)
    goal = mean.copy()
    goal[0] = max(goal[0], ex_lab[:, 0].mean())
    return TEX.match_lab(tile_px, goal, numpy.maximum(spread,
                                                      0.7 * ex_lab.std(0)))


def _write_dds(rgb, path):
    partial = DDS.partial_name(path)
    ENC.encode_file(rgb, "bc1", partial)
    DDS.land(partial, path)


def synthesize(tile):
    """Write every texture of ``tile.cliff_plan``; returns how many."""
    plan = getattr(tile, "cliff_plan", None) or []
    if not plan:
        return 0
    start = time.time()
    source = _Photos(tile)
    rng = numpy.random.default_rng(2096)
    flat = 0
    for region in sorted(plan, key=lambda reg: reg["ortho"]):
        mosaic = _Mosaic(region["photos"], source)
        rgb = (_region_texture(mosaic, region["foot"], region["exemplar"],
                              rng=rng) if mosaic.cells else None)
        if rgb is None:
            flat += 1
            rgb = numpy.empty((TILE_PX, TILE_PX, 3), numpy.uint8)
            rgb[:] = NEUTRAL_ROCK
        _write_dds(rgb, os.path.join(tile.build_dir, "textures",
                                     region["texture"]))
        if UI.red_flag:
            return 0
    UI.vprint(1, "-> Cliff textures: %d made in %.1f s (%d without a photo)."
              % (len(plan), time.time() - start, flat))
    return len(plan)
