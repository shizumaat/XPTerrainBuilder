"""Straight colour steps and red-cast squares in the imagery under shallow
water, and their repair: colour match first, then a strong blur along the
line only -- never on land.

A photo provider's mosaic over shallow water is a patchwork: squares from
another flight, reddish squares, a scene edge that stairs down the map
(owner, 2026-11-24, tile +24-082: "under water we can get away with a lot
softer blurring").  Over land those steps hide in the ground's texture;
under water, where the ground is a smooth gradient, every one shows.  They
are STRAIGHT and run along the map's axes (the mosaic is assembled from
Web Mercator tiles), but not on any fixed grid of the texture.

* :func:`_water_weight` -- 0 on land (the mask's opaque 255) and one DXT
  block around it, rising to 1 over :data:`LAND_RAMP` px into the water.
  Every change is composited by it, so a land pixel (and every
  compressed block holding one) never changes, and the blur is weighted
  by it, so land colour never bleeds into the water.
* :func:`_find_water_seams` -- the straight lines of the mosaic
  (``O4_Imagery_Water_Lines``: axis-aligned runs of excess colour step,
  long alone or turning square corners, never a pier, a boat or a
  channel), and the red-cast squares (:func:`_red_squares`): patches of
  census cells whose R-G cast over their surroundings reaches
  :data:`RED_EXCESS`, bright and square enough to be a source tile, their
  box's sides showing straight steps (:data:`TINT_EDGE_SEEN`); around them
  the lines measure brightness only (the tint owns the cast).  Outlier,
  red and cloud-like cells are counted for the report.
* :func:`repair_water_seams` -- one offset per :data:`CELL`, the screened
  Poisson solution whose jumps cancel the flagged steps and decay over
  :data:`SCREEN_CELLS` cells, held at 0 on the border ring (the texture
  never steps against its neighbour), plus the tint that removes each red
  square's cast with its luminance kept, applied with
  ``O4_Color_Harmonization.apply_color_field``; then a water-weighted
  Gaussian blur of :data:`BLUR_SIGMA_M` blended in along the flagged lines
  (:data:`BAND_SIGMA_M`) and the squares' edges (:data:`TINT_BAND_SIGMA_M`).
* :func:`apply_on_water` -- any change composited by :func:`_water_weight`.

Pure leaf: numpy, scipy and PIL; no I/O, no state but a cached matrix
factorisation, no randomness.  No tile or airport is named here.
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy
import O4_Color_Harmonization as HARMONIZE
import O4_Imagery_Water_Lines as LINES
from PIL import Image
from scipy import ndimage, sparse
from scipy.sparse.linalg import factorized

__all__ = [
    "apply_on_water",
    "repair_water_seams",
    "shows_water",
]

# The working grid: the texture is box-reduced to this square (a 4096-px
# texture's mask is this size too, so the mask needs no resampling).
WORK = 1024
# Mask value of land: the compositor returns every land pixel to full
# opacity (``O4_Mask_Utils.compose_water_mask``).
LAND_VALUE = 255
# The water weight rises from 0 to 1 over this many work px off land.
LAND_RAMP = 6.0
# The colour match is solved on cells of this many work px ...
CELL = 4
# ... decays over this many cells away from a seam ...
SCREEN_CELLS = 24.0
# ... and is held at 0 on the border ring with this weight.
BORDER_PIN = 4.0
# No cell moves by more than this (counts per channel).
MAX_SHIFT = 60.0
# The blur along the flagged lines, and the half-width of its band, in
# metres on the ground (a ZL16 texture is ~2.2 m/px at 24 N).  The blur
# runs on the cell grid.
BLUR_SIGMA_M = 120.0
BAND_SIGMA_M = 45.0
# The band is fully blurred out to about one band sigma from the line.
BAND_GAIN = 1.6
# A texture is repaired only when at least this fraction of it is water
# that shows (mask opacity at least VISIBLE_ALPHA, below land's 255).
VISIBLE_ALPHA = 64
MIN_VISIBLE_WATER = 0.01
# Cell census (reported): on cells of 8 work px, a cell is an outlier when
# its colour is this far from the median of the 5x5 cells around it;
# red-cast when its R-G excess over that median is this large;
# cloud-like when this much brighter and grey.
CENSUS_CELL = 8
OUTLIER_STEP = 18.0
RED_EXCESS = 10.0
CLOUD_LUMA = 25.0
# Red-cast squares (repaired by a tint, luminance kept): on the census
# cells, the R-G cast over the median of the cells within this many
# metres around reaches RED_EXCESS over a patch at least TINT_MIN_SIDE_M
# on a side (in area) that fills TINT_FILL of its bounding box (a source
# tile, not a reef or a boat) ...
TINT_REFERENCE_M = 1110.0
TINT_MIN_SIDE_M = 210.0
TINT_FILL = 0.6
# ... where the patch is bright enough for a cast to read as red (on dark
# water a 10-count R-G excess is no colour at all) ...
TINT_MIN_LUMA = 70.0
# ... each cell tinted by its own cast, softened over this many cells ...
TINT_SOFTEN = 0.75
# ... and its box's sides show straight steps over this fraction of their
# length.
TINT_EDGE_SEEN = 0.5
# ... and its edge is hidden by a blur band this wide (the tint lies on the
# census cells, up to half a cell off the square's own edge).
TINT_BAND_SIGMA_M = 20.0

_LUMA = numpy.array([0.299, 0.587, 0.114], dtype=numpy.float32)


@dataclass
class _WaterSeams:
    """What :func:`_find_water_seams` measured on one texture, on the
    :data:`WORK` grid.

    ``evidence_x[y, x]`` is the signed RGB excess step across the vertical
    line before column ``x``, averaged along it over :data:`LINE` rows;
    ``evidence_y[y, x]`` across the horizontal line before row ``y``.
    ``flag_x`` / ``flag_y`` mark the line points flagged as seams.
    ``tint`` is the ``(WORK, WORK, 3)`` offset that removes the cast of
    every red-cast square, ``tinted`` its pixels.  ``cells`` is the texture's mean colour
    per :data:`CELL`.
    """

    evidence_x: numpy.ndarray
    evidence_y: numpy.ndarray
    flag_x: numpy.ndarray
    flag_y: numpy.ndarray
    tint: numpy.ndarray
    tinted: numpy.ndarray
    cells: numpy.ndarray
    census: Dict[str, int] = field(default_factory=dict)

    @property
    def flagged(self) -> int:
        """Flagged line points plus tinted pixels."""
        return int(self.flag_x.sum() + self.flag_y.sum() + self.tinted.sum())

    def runs(self) -> List[int]:
        """Lengths (work px) of every straight run of flagged points."""
        lengths: List[int] = []
        for flags in (self.flag_x, self.flag_y.T):
            lengths += LINES.run_lengths(flags)
        return lengths

    def step_stats(self, flags_x=None, flags_y=None) -> Tuple[float, float]:
        """``(median, max)`` step magnitude at the given line points (by
        default the flagged ones)."""
        fx = self.flag_x if flags_x is None else flags_x
        fy = self.flag_y if flags_y is None else flags_y
        v = numpy.concatenate([
            numpy.linalg.norm(self.evidence_x[fx], axis=-1),
            numpy.linalg.norm(self.evidence_y[fy], axis=-1)])
        if v.size == 0:
            return 0.0, 0.0
        return float(numpy.median(v)), float(v.max())


def shows_water(mask) -> bool:
    """Whether enough of a texture is water that shows (see
    :data:`MIN_VISIBLE_WATER`) for a repair to matter."""
    m = numpy.asarray(mask.convert("L") if isinstance(mask, Image.Image)
                      else mask)
    visible = (m >= VISIBLE_ALPHA) & (m < LAND_VALUE)
    return float(visible.mean()) >= MIN_VISIBLE_WATER


def _land_at(mask: numpy.ndarray, n: int) -> numpy.ndarray:
    """``n x n`` boolean: a work px is land when ANY mask px it covers is
    land (conservative: a coarser grid never thins land)."""
    land = mask >= LAND_VALUE
    m = land.shape[0]
    if m == n:
        return land
    if m > n and m % n == 0:
        k = m // n
        return land.reshape(n, k, n, k).any(axis=(1, 3))
    idx = (numpy.arange(n) * m) // n
    return land[numpy.ix_(idx, idx)]


def _water_weight(mask: numpy.ndarray, n: int = WORK,
                 texture_px: int = 4 * WORK) -> numpy.ndarray:
    """``(n, n)`` float32 in [0, 1]: exactly 0 on land and around it,
    rising linearly to 1 over :data:`LAND_RAMP` px into the water.

    The zero zone reaches one DXT block (4 texture px) past land, at least
    one work px, 8-connected (a bilinear upsample reads the diagonal
    neighbour too): a block holding a land pixel is never touched, so the
    compressed texture's land blocks stay byte-identical as well."""
    radius = max(1, -(-4 * n // int(texture_px)))
    zone = ndimage.binary_dilation(_land_at(numpy.asarray(mask), n),
                                   structure=numpy.ones((3, 3), bool),
                                   iterations=radius)
    if not zone.any():
        return numpy.ones((n, n), dtype=numpy.float32)
    distance = ndimage.distance_transform_edt(~zone)
    return numpy.clip(distance / LAND_RAMP, 0.0, 1.0).astype(numpy.float32)


def _census(a: numpy.ndarray, w: numpy.ndarray) -> Dict[str, int]:
    """Outlier, red-cast and cloud-like water cells (counts)."""
    cell = _reduce(a, CENSUS_CELL)
    water = _reduce(w, CENSUS_CELL) >= LINES.MIN_WATER
    if not water.any():
        return {"outlier": 0, "red": 0, "cloud": 0}
    ref = numpy.stack([ndimage.median_filter(cell[..., c], size=5,
                                             mode="nearest")
                       for c in range(3)], axis=-1)
    diff = cell - ref
    outlier = water & (numpy.linalg.norm(diff, axis=-1) >= OUTLIER_STEP)
    red = outlier & ((diff[..., 0] - diff[..., 1]) >= RED_EXCESS)
    grey = cell.max(axis=-1) - cell.min(axis=-1)
    cloud = outlier & ((diff @ _LUMA) >= CLOUD_LUMA) & (grey < 40.0)
    return {"outlier": int(outlier.sum()), "red": int(red.sum()),
            "cloud": int(cloud.sum())}


def _opacity(mask: numpy.ndarray) -> numpy.ndarray:
    """The mask's opacity (0-1) on the :data:`WORK` grid."""
    im = Image.fromarray(numpy.asarray(mask, dtype=numpy.uint8), "L")
    if im.size != (WORK, WORK):
        im = im.resize((WORK, WORK), Image.BOX)
    return numpy.asarray(im, dtype=numpy.float32) / 255.0


def _red_squares(a: numpy.ndarray, w: numpy.ndarray, weak_x: numpy.ndarray,
                 weak_y: numpy.ndarray, work_m: float):
    """``(tint, tinted)`` on the :data:`WORK` grid: every red-cast square's
    census cells and the offset that removes each cell's cast over the
    water just around the square, luminance kept, softened over
    :data:`TINT_SOFTEN` cells (the square's own edge is up to half a cell
    off; the tint band hides that).  A patch is a square only where its
    box's sides show straight steps (``weak_x`` / ``weak_y``, the weak
    line points) over :data:`TINT_EDGE_SEEN` of their length: a sandy
    shallow is reddish too, but its edge wanders."""
    k = CENSUS_CELL
    cell = _reduce(a, k)
    water = _reduce(w, k) >= LINES.MIN_WATER
    chroma = numpy.stack([cell[..., 0] - cell[..., 1],
                          cell[..., 2] - cell[..., 1]], axis=-1)
    # the surroundings' median on cells twice as coarse (a quarter of the
    # cost; the reference is smooth by construction)
    coarse = _reduce(chroma, 2)
    cell_m = work_m * k
    window = min(coarse.shape[0], max(3, int(round(TINT_REFERENCE_M
                                                   / (2.0 * cell_m)))))
    min_cells = max(4, int(round((TINT_MIN_SIDE_M / cell_m) ** 2)))
    ref = numpy.stack([ndimage.median_filter(coarse[..., c], window,
                                             mode="nearest") for c in range(2)],
                      axis=-1)
    excess = chroma - numpy.kron(ref, numpy.ones((2, 2, 1), numpy.float32))
    tint = numpy.zeros(cell.shape, dtype=numpy.float32)
    tinted = numpy.zeros(water.shape, dtype=bool)
    labels, _count = ndimage.label(water & (excess[..., 0] >= RED_EXCESS))
    for label, box in enumerate(ndimage.find_objects(labels), start=1):
        part = labels[box] == label
        if (part.sum() < min_cells or part.mean() < TINT_FILL
                or float(numpy.median(cell[box][part] @ _LUMA)) < TINT_MIN_LUMA):
            continue
        # each cell's own cast (a square is rarely one flat cast) over the
        # patch with its holes filled, against the water just around it
        grown = tuple(slice(max(b.start - 2, 0), b.stop + 2) for b in box)
        region = numpy.zeros(water[grown].shape, dtype=bool)
        inner = tuple(slice(b.start - g.start, b.stop - g.start)
                      for b, g in zip(box, grown, strict=True))
        # a large square shows only its rim against a local median: close
        # the rim's corners, then fill it
        closed = ndimage.binary_closing(numpy.pad(part, 2), iterations=2)[2:-2, 2:-2]
        region[inner] = ndimage.binary_fill_holes(closed | part) & water[box]
        if _edges_seen(box, k, weak_x, weak_y) < TINT_EDGE_SEEN:
            continue
        ring = ndimage.binary_dilation(region, iterations=2) & ~region & (
            water[grown])
        if not ring.any():
            continue
        around = numpy.median(chroma[grown][ring], axis=0)
        e_red = numpy.maximum(chroma[grown][..., 0] - around[0], 0.0)
        e_blue = numpy.where(e_red > 0.0, chroma[grown][..., 1] - around[1], 0.0)
        green = 0.299 * e_red + 0.114 * e_blue
        cast = numpy.stack([green - e_red, green, green - e_blue], axis=-1)
        tint[grown][region] = cast[region]
        tinted[grown] |= region
    # soften the cell steps inside a square and at its edge
    tint = ndimage.gaussian_filter(tint, (TINT_SOFTEN, TINT_SOFTEN, 0),
                                   mode="nearest")
    block = numpy.ones((k, k), bool)
    return numpy.kron(tint, block[..., None]), numpy.kron(tinted, block)


def _edges_seen(box, k: int, weak_x: numpy.ndarray,
                weak_y: numpy.ndarray) -> float:
    """The fraction of a cell box's sides (in work px) with a weak line
    point within half a cell of the side, along it."""
    top, bottom = box[0].start * k, box[0].stop * k
    left, right = box[1].start * k, box[1].stop * k
    h = k // 2 + 1

    def seen(flags, line, start, stop):
        band = flags[start:stop, max(line - h, 0):line + h]
        return int(band.any(axis=1).sum())

    covered = (seen(weak_x, left, top, bottom) + seen(weak_x, right, top, bottom)
               + seen(weak_y.T, top, left, right)
               + seen(weak_y.T, bottom, left, right))
    return covered / float(2 * (bottom - top) + 2 * (right - left))


def _work_image(image: Image.Image) -> numpy.ndarray:
    small = image.convert("RGB").resize((WORK, WORK), Image.BOX)
    return numpy.asarray(small, dtype=numpy.float32)


def _reduce(a: numpy.ndarray, k: int) -> numpy.ndarray:
    n = a.shape[0] // k
    return a.reshape(n, k, n, k, *a.shape[2:]).mean(axis=(1, 3))


def _find_water_seams(image: Image.Image, mask: numpy.ndarray,
                      metres_per_px: float,
                      weight: Optional[numpy.ndarray] = None,
                      census: bool = False) -> _WaterSeams:
    """The flagged seams of one texture (see the module doc).  ``mask`` is
    the texture's water mask (any square size, 255 = land);
    ``metres_per_px`` the ground size of one texture px (every length
    rule is in metres); ``census`` also counts the outlier, red and
    cloud-like cells (a report)."""
    a = _work_image(image)
    mask = numpy.asarray(mask)
    w = _water_weight(mask) if weight is None else weight
    opacity = _opacity(mask)
    work_m = metres_per_px * image.size[0] / float(WORK)
    scale = LINES.scale_for(work_m)
    ex, strong_x, weak_x = LINES.vertical_lines(a, w, opacity, scale)
    ey, strong_y, weak_y = LINES.vertical_lines(a.transpose(1, 0, 2), w.T,
                                                opacity.T, scale)
    tint, tinted = _red_squares(a, w, weak_x, weak_y.T, work_m)
    if tinted.any():
        # around a tinted square the lines see brightness only, so its
        # brightness step is matched and its cast (the tint's) not twice
        grey = ndimage.binary_dilation(
            tinted, iterations=LINES.SUPPRESS + LINES.STRIP)
        ex, strong_x, weak_x = LINES.vertical_lines(a, w, opacity, scale,
                                                    grey)
        ey, strong_y, weak_y = LINES.vertical_lines(
            a.transpose(1, 0, 2), w.T, opacity.T, scale, grey.T)
    strong_x, strong_y = LINES.straight_pairs(strong_x, strong_y.T, ex,
                                              ey.transpose(1, 0, 2), scale)
    fx = LINES.grown(strong_x, weak_x)
    fy = LINES.grown(strong_y.T, weak_y).T
    return _WaterSeams(ex, ey.transpose(1, 0, 2), fx, fy, tint, tinted,
                      _reduce(a, CELL), _census(a, w) if census else {})


_FACTOR_LOCK = threading.Lock()
_FACTORS: Dict[int, object] = {}


def _solver(n: int):
    """The factorised screened-Poisson matrix of an ``n x n`` cell grid (it
    does not depend on the seams found, only on the grid: cached)."""
    with _FACTOR_LOCK:
        if n in _FACTORS:
            return _FACTORS[n]
        size = n * n
        idx = numpy.arange(size).reshape(n, n)
        pairs = [(idx[:, :-1].ravel(), idx[:, 1:].ravel()),
                 (idx[:-1, :].ravel(), idx[1:, :].ravel())]
        diag = numpy.full(size, 1.0 / SCREEN_CELLS ** 2)
        border = numpy.zeros((n, n), dtype=bool)
        border[0, :] = border[-1, :] = border[:, 0] = border[:, -1] = True
        diag[border.ravel()] += BORDER_PIN
        rows, cols, vals = [], [], []
        for p, q in pairs:
            numpy.add.at(diag, p, 1.0)
            numpy.add.at(diag, q, 1.0)
            rows += [p, q]
            cols += [q, p]
            vals += [-numpy.ones(p.size), -numpy.ones(p.size)]
        rows.append(numpy.arange(size))
        cols.append(numpy.arange(size))
        vals.append(diag)
        matrix = sparse.csc_matrix(
            (numpy.concatenate(vals),
             (numpy.concatenate(rows), numpy.concatenate(cols))),
            shape=(size, size))
        _FACTORS[n] = factorized(matrix)
        return _FACTORS[n]


def _cell_offsets(seams: _WaterSeams) -> numpy.ndarray:
    """``(cells, cells, 3)`` float32: the colour match (module doc).  A
    flagged point before work column ``x`` asks the cells either side of
    the nearest cell boundary to differ by minus its step."""
    n = seams.flag_x.shape[0] // CELL
    rhs = numpy.zeros((n, n, 3), dtype=numpy.float64)
    for evidence, flags, transpose in ((seams.evidence_x, seams.flag_x, False),
                                       (seams.evidence_y, seams.flag_y, True)):
        if transpose:
            evidence = evidence.transpose(1, 0, 2)
            flags = flags.T
        target = numpy.zeros((n, n + 1, 3), dtype=numpy.float64)
        ys, xs = numpy.nonzero(flags)
        j = numpy.clip(numpy.rint(xs / float(CELL)).astype(int), 1, n - 1)
        numpy.add.at(target, (ys // CELL, j), -evidence[ys, xs] / CELL)
        t = target[:, 1:n]
        if transpose:
            r = numpy.zeros((n, n, 3))
            r[:, 1:] += t
            r[:, :-1] -= t
            rhs += r.transpose(1, 0, 2)
        else:
            rhs[:, 1:] += t
            rhs[:, :-1] -= t
    solve = _solver(n)
    out = numpy.stack([solve(rhs[..., c].ravel()) for c in range(3)], axis=-1)
    out = numpy.clip(out, -MAX_SHIFT, MAX_SHIFT)
    return out.reshape(n, n, 3).astype(numpy.float32)


def _band(seams: _WaterSeams, cell_m: float) -> numpy.ndarray:
    """``(cells, cells)`` float32 in [0, 1]: 1 along the flagged lines and
    the tinted squares' edges, falling off as a Gaussian of
    :data:`BAND_SIGMA_M` (:data:`TINT_BAND_SIGMA_M`) either side."""
    lines = _reduce((seams.flag_x | seams.flag_y).astype(numpy.float32), CELL)
    edge = _reduce((seams.tinted ^ ndimage.binary_erosion(seams.tinted))
                   .astype(numpy.float32), CELL)
    return numpy.maximum(_gauss_band(lines > 0, BAND_SIGMA_M / cell_m),
                         _gauss_band(edge > 0, TINT_BAND_SIGMA_M / cell_m))


def _gauss_band(lines: numpy.ndarray, sigma: float) -> numpy.ndarray:
    band = ndimage.gaussian_filter(lines.astype(numpy.float32), sigma,
                                   mode="nearest")
    return numpy.clip(band * math.sqrt(2.0 * math.pi) * sigma * BAND_GAIN,
                      0.0, 1.0).astype(numpy.float32)


def _water_blur(a: numpy.ndarray, w: numpy.ndarray, sigma: float) -> numpy.ndarray:
    """Gaussian blur of ``a`` weighted by the water weight ``w`` (normalised
    convolution: land never bleeds into water)."""
    den = ndimage.gaussian_filter(w, sigma, mode="nearest")
    out = numpy.empty_like(a)
    for c in range(3):
        num = ndimage.gaussian_filter(a[..., c] * w, sigma, mode="nearest")
        out[..., c] = numpy.where(den > 1e-3, num / numpy.maximum(den, 1e-3),
                                  a[..., c])
    return out


def _upsampled(field: numpy.ndarray, n: int) -> numpy.ndarray:
    """``(n, n, 3)`` float32: a field bilinearly resampled (pixel centres
    aligned, as ``apply_color_field`` upsamples)."""
    return numpy.stack([numpy.asarray(Image.fromarray(
        numpy.ascontiguousarray(field[..., c], dtype=numpy.float32), "F")
        .resize((n, n), Image.BILINEAR)) for c in range(3)], axis=-1)


def _plane(values: numpy.ndarray, size, resample) -> Image.Image:
    data = numpy.clip(numpy.rint(values * 255.0), 0, 255).astype(numpy.uint8)
    return Image.fromarray(data, "L").resize(size, resample)


def repair_water_seams(image: Image.Image, mask, metres_per_px: float,
                       seams: Optional[_WaterSeams] = None,
                       ) -> Tuple[Image.Image, _WaterSeams]:
    """``(repaired, seams)``: the texture with its flagged water seams
    colour-matched and blurred (see the module doc), and what was found.

    ``mask`` is the texture's water mask (``L`` image or 2-D array, any
    square size; 255 is land); ``metres_per_px`` the ground size of one
    texture px.  The input image is never mutated; when nothing is
    flagged it is returned as is.  Every land pixel (mask 255), and every
    pixel of a DXT block that holds one, is returned byte-identical.
    """
    mask = numpy.asarray(mask.convert("L") if isinstance(mask, Image.Image)
                         else mask)
    w = _water_weight(mask, texture_px=image.size[0])
    if seams is None:
        seams = _find_water_seams(image, mask, metres_per_px, weight=w)
    if not seams.flagged:
        return image, seams
    rgb = image.convert("RGB")
    size = rgb.size
    offsets = _upsampled(_cell_offsets(seams), WORK) + seams.tint
    matched = HARMONIZE.apply_color_field(rgb, offsets)
    # the blur and its band, on the cell grid (the blur is wide): the cell
    # means of the matched texture are the source's plus the offsets
    cell_m = metres_per_px * size[0] / float(WORK) * CELL
    cells = seams.cells + _reduce(numpy.rint(offsets), CELL)
    blurred = _water_blur(numpy.clip(cells, 0, 255), _reduce(w, CELL),
                          BLUR_SIGMA_M / cell_m)
    blurred_im = Image.fromarray(
        numpy.clip(numpy.rint(blurred), 0, 255).astype(numpy.uint8),
        "RGB").resize(size, Image.BILINEAR)
    band = _band(seams, cell_m)
    mixed = Image.composite(blurred_im, matched,
                            _plane(band, size, Image.BILINEAR))
    return _composite_on_water(mixed, image, w), seams


def apply_on_water(image: Image.Image, changed: Image.Image,
                   mask) -> Image.Image:
    """``changed`` where the texture is water, ``image`` on land, blended by
    :func:`_water_weight` (exactly ``image`` on land and one DXT block
    around it).  ``mask`` as in :func:`repair_water_seams`."""
    mask = numpy.asarray(mask.convert("L") if isinstance(mask, Image.Image)
                         else mask)
    return _composite_on_water(changed, image,
                               _water_weight(mask, texture_px=image.size[0]))


def _composite_on_water(changed: Image.Image, image: Image.Image,
                        w: numpy.ndarray) -> Image.Image:
    mode = image.mode
    rgb = image.convert("RGB")
    result = Image.composite(changed.convert("RGB"), rgb,
                             _plane(w, rgb.size, Image.BILINEAR))
    if mode == "RGBA":
        result.putalpha(image.getchannel("A"))
    elif mode != "RGB":
        result = result.convert(mode)
    return result
