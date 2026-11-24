"""Grid-aligned colour steps in the imagery under shallow water, and their
repair: colour match first, then a strong blur along the line, never on land.

A photo provider's mosaic over shallow water is a patchwork: squares of one
source tile (one tile of a zoom level up to three above the texture's) next
to another flown on a different day, a reddish or pale square, a scene
boundary that stairs down the tile grid (owner, 2026-11-24, tile +24-082).
Over land those steps hide in the ground's own texture; under water, where
the ground is a smooth gradient, every one shows.  Their lines lie on the
provider's tile grid, which is the texture's own pixel grid: a texture
covers 16 tiles of its zoom level, so the finest source tile it can carry
is 1/128 of its edge (:data:`GRID_DIVISIONS`).

* :func:`water_weight` -- 0 on land (the mask's opaque 255) and one mask
  pixel around it, rising to 1 over :data:`LAND_RAMP` pixels into the water.
  Every change this module makes is multiplied by it, so a land pixel
  never changes, and the blur is weighted by it, so land colour never
  bleeds into the water.
* :func:`find_water_seams` -- on a :data:`WORK`-px copy of the texture,
  the colour step across every grid line, segment by segment (one grid
  cell long), in EXCESS of the gradient on either side (a smooth slope is
  not a step); a segment is flagged when its excess is at least
  :data:`MIN_STEP` counts, :data:`NOISE_RATIO` times the steps on the
  off-grid lines beside it (a ground edge crossing the cell steps there
  too), and its water weight is at least :data:`MIN_WATER`.  It also counts
  cells far from their neighbours' median colour, red-cast and cloud-like
  cells (reported; the repair needs no separate rule for them, since a
  square's four edges are flagged lines).
* :func:`repair_water_seams` -- colour first: one offset per grid cell, the
  screened Poisson solution whose jumps cancel the flagged steps and decay
  over :data:`SCREEN_CELLS` cells away from them, held at 0 on the texture's
  border ring (the texture never steps against its neighbour), applied with
  ``O4_Color_Harmonization.apply_color_field``.  Then a water-weighted
  Gaussian blur of :data:`BLUR_SIGMA_M` metres blended in along the flagged
  lines only (a band of :data:`BAND_SIGMA_M`), hiding what the colour match
  left of the step.  Last, the result is composited over the original by
  :func:`water_weight`.

Pure leaf: numpy, scipy and PIL; no I/O, no state but a cached matrix
factorisation, no randomness.  No tile or airport is named here.
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy
from PIL import Image
from scipy import ndimage, sparse
from scipy.sparse.linalg import factorized

import O4_Color_Harmonization as HARMONIZE

__all__ = [
    "WaterSeams",
    "find_water_seams",
    "repair_water_seams",
    "water_weight",
]

# The working grid: the texture is box-reduced to this square (a 4096-px
# texture's mask is this size too, so the mask needs no resampling).
WORK = 1024
# Strip width (work px) each side of a line, and the lines beside it whose
# step is the slope expected there (two strips away each side).
STRIP = 2
# The step is averaged along the line over this many work px (~140 m at
# ZL16): a straight edge keeps its step, a ground edge crossing the line
# at an angle, or the ground's own texture, averages out.
LINE = 16
# A line point is flagged when the averaged excess step (Euclidean RGB
# counts) times the mask's opacity there (what shows over the water)
# reaches this ...
MIN_STEP = 8.0
# ... it is this coherent (|mean step| / mean |step| along the line) ...
COHERENCE = 0.7
# ... it is the strongest within this many work px across the line ...
SUPPRESS = 3
# ... both sides are at least this much water ...
MIN_WATER = 0.5
# ... and it belongs to a straight run at least this long (work px).
MIN_RUN = 28
# A run grows along its line through points that step at least this much
# (visible counts) with this coherence: a scene edge keeps its line while
# the ground on either side changes how much it steps.
WEAK_STEP = 4.0
WEAK_COHERENCE = 0.4
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
# Cell census (reported): on cells of 8 work px, a cell is an outlier when
# its colour is this far from the median of the 5x5 cells around it;
# red-cast when its R-G excess over that median is this large;
# cloud-like when this much brighter and grey.
CENSUS_CELL = 8
OUTLIER_STEP = 18.0
RED_EXCESS = 10.0
CLOUD_LUMA = 25.0
# Red-cast squares (repaired by a tint, luminance kept): on the census
# cells, the R-G cast over the median of the cells within this many cells
# around reaches RED_EXCESS over a patch of at least TINT_MIN_CELLS cells
# that fills TINT_FILL of its bounding box (a source tile, not a reef).
TINT_REFERENCE = 15
TINT_MIN_CELLS = 9
TINT_FILL = 0.6
# ... where the patch is bright enough for a cast to read as red (on dark
# water a 10-count R-G excess is no colour at all) ...
TINT_MIN_LUMA = 70.0
# ... and its edge is hidden by a blur band this wide (the tint lies on the
# census cells, up to half a cell off the square's own edge).
TINT_BAND_SIGMA_M = 20.0

_LUMA = numpy.array([0.299, 0.587, 0.114], dtype=numpy.float32)


@dataclass
class WaterSeams:
    """What :func:`find_water_seams` measured on one texture, on the
    :data:`WORK` grid.

    ``evidence_x[y, x]`` is the signed RGB excess step across the vertical
    line before column ``x``, averaged along it over :data:`LINE` rows;
    ``evidence_y[y, x]`` across the horizontal line before row ``y``.
    ``flag_x`` / ``flag_y`` mark the line points flagged as seams.
    ``tint`` is the ``(cells, cells, 3)`` offset (census cells of
    :data:`CENSUS_CELL` work px) that removes the cast of every red-cast
    square, ``tinted`` its cells.
    """

    evidence_x: numpy.ndarray
    evidence_y: numpy.ndarray
    flag_x: numpy.ndarray
    flag_y: numpy.ndarray
    tint: numpy.ndarray
    tinted: numpy.ndarray
    census: Dict[str, int] = field(default_factory=dict)

    @property
    def flagged(self) -> int:
        """Flagged line points plus tinted (census) cells."""
        return int(self.flag_x.sum() + self.flag_y.sum() + self.tinted.sum())

    def runs(self) -> List[int]:
        """Lengths (work px) of every straight run of flagged points."""
        lengths: List[int] = []
        for flags in (self.flag_x, self.flag_y.T):
            labels, count = ndimage.label(flags, structure=_VERTICAL)
            if count:
                lengths += numpy.bincount(labels.ravel())[1:].tolist()
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


_VERTICAL = numpy.array([[0, 1, 0], [0, 1, 0], [0, 1, 0]], dtype=bool)


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


def water_weight(mask: numpy.ndarray, n: int = WORK,
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


def _shift(a: numpy.ndarray, k: int) -> numpy.ndarray:
    """``a`` moved ``k`` columns (``out[:, x] = a[:, x + k]``), edge-padded."""
    if k == 0:
        return a
    out = numpy.empty_like(a)
    if k > 0:
        out[:, :-k] = a[:, k:]
        out[:, -k:] = a[:, -1:]
    else:
        out[:, -k:] = a[:, :k]
        out[:, :-k] = a[:, :1]
    return out


def _vertical_lines(a: numpy.ndarray, w: numpy.ndarray, opacity: numpy.ndarray):
    """``(evidence, flags)`` of the vertical lines of ``a`` (see
    :class:`WaterSeams`); the horizontal ones are this on the transpose."""
    s = STRIP
    after = sum(_shift(a, k) for k in range(s)) / s
    before = sum(_shift(a, -1 - k) for k in range(s)) / s
    step = after - before
    excess = step - 0.5 * (_shift(step, -2 * s) + _shift(step, 2 * s))
    evidence = ndimage.uniform_filter1d(excess, LINE, axis=0, mode="nearest")
    spread = ndimage.uniform_filter1d(numpy.linalg.norm(excess, axis=-1),
                                      LINE, axis=0, mode="nearest")
    magnitude = numpy.linalg.norm(evidence, axis=-1)
    water = numpy.minimum.reduce([_shift(w, k) for k in range(-s, s)])
    candidate = ((magnitude >= ndimage.maximum_filter1d(
        magnitude, 2 * SUPPRESS + 1, axis=1, mode="nearest"))
        & (water >= MIN_WATER))
    margin = 3 * s
    candidate[:, :margin] = False
    candidate[:, -margin:] = False
    visible = magnitude * opacity
    strong = _runs_at_least(candidate & (visible >= MIN_STEP)
                            & (magnitude >= COHERENCE * spread), MIN_RUN)
    weak = candidate & (visible >= WEAK_STEP) & (
        magnitude >= WEAK_COHERENCE * spread)
    # hysteresis: a weak run is kept where it carries a strong one
    labels, count = ndimage.label(weak | strong, structure=_VERTICAL)
    keep = numpy.zeros(count + 1, dtype=bool)
    keep[numpy.unique(labels[strong])] = True
    keep[0] = False
    return evidence.astype(numpy.float32), keep[labels]


def _runs_at_least(flags: numpy.ndarray, length: int) -> numpy.ndarray:
    """``flags`` without the vertical runs shorter than ``length``."""
    labels, count = ndimage.label(flags, structure=_VERTICAL)
    if not count:
        return flags
    keep = numpy.bincount(labels.ravel()) >= length
    keep[0] = False
    return keep[labels]


def _census(a: numpy.ndarray, w: numpy.ndarray) -> Dict[str, int]:
    """Outlier, red-cast and cloud-like water cells (counts)."""
    cell = _reduce(a, CENSUS_CELL)
    water = _reduce(w, CENSUS_CELL) >= MIN_WATER
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


def _red_squares(a: numpy.ndarray, w: numpy.ndarray):
    """``(tint, tinted)`` on the census cells: every red-cast square's cells
    and the offset that removes its median cast, luminance kept."""
    cell = _reduce(a, CENSUS_CELL)
    water = _reduce(w, CENSUS_CELL) >= MIN_WATER
    chroma = numpy.stack([cell[..., 0] - cell[..., 1],
                          cell[..., 2] - cell[..., 1]], axis=-1)
    ref = numpy.stack([ndimage.median_filter(chroma[..., k], TINT_REFERENCE,
                                             mode="nearest") for k in range(2)],
                      axis=-1)
    excess = chroma - ref
    tint = numpy.zeros(cell.shape, dtype=numpy.float32)
    tinted = numpy.zeros(water.shape, dtype=bool)
    labels, count = ndimage.label(water & (excess[..., 0] >= RED_EXCESS))
    for k, box in enumerate(ndimage.find_objects(labels), start=1):
        part = labels[box] == k
        if (part.sum() < TINT_MIN_CELLS or part.mean() < TINT_FILL
                or float(numpy.median(cell[box][part] @ _LUMA)) < TINT_MIN_LUMA):
            continue
        e_red, e_blue = numpy.median(excess[box][part], axis=0)
        green = 0.299 * e_red + 0.114 * e_blue
        region = water[box]
        tint[box][region] = (green - e_red, green, green - e_blue)
        tinted[box] |= region
    return tint, tinted


def _work_image(image: Image.Image) -> numpy.ndarray:
    small = image.convert("RGB").resize((WORK, WORK), Image.BOX)
    return numpy.asarray(small, dtype=numpy.float32)


def _reduce(a: numpy.ndarray, k: int) -> numpy.ndarray:
    n = a.shape[0] // k
    return a.reshape(n, k, n, k, *a.shape[2:]).mean(axis=(1, 3))


def find_water_seams(image: Image.Image, mask: numpy.ndarray,
                     weight: Optional[numpy.ndarray] = None) -> WaterSeams:
    """The flagged seams of one texture (see the module doc).  ``mask`` is
    the texture's water mask (any square size, 255 = land)."""
    a = _work_image(image)
    mask = numpy.asarray(mask)
    w = water_weight(mask) if weight is None else weight
    opacity = _opacity(mask)
    ex, fx = _vertical_lines(a, w, opacity)
    ey, fy = _vertical_lines(a.transpose(1, 0, 2), w.T, opacity.T)
    tint, tinted = _red_squares(a, w)
    return WaterSeams(ex, ey.transpose(1, 0, 2), fx, fy.T, tint, tinted,
                      _census(a, w))


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


def _cell_offsets(seams: WaterSeams) -> numpy.ndarray:
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


def _band(seams: WaterSeams, cell_m: float) -> numpy.ndarray:
    """``(cells, cells)`` float32 in [0, 1]: 1 along the flagged lines and
    the tinted squares' edges, falling off as a Gaussian of
    :data:`BAND_SIGMA_M` (:data:`TINT_BAND_SIGMA_M`) either side."""
    lines = _reduce((seams.flag_x | seams.flag_y).astype(numpy.float32), CELL)
    edge = seams.tinted ^ ndimage.binary_erosion(seams.tinted)
    k = CENSUS_CELL // CELL
    edge = numpy.kron(edge, numpy.ones((k, k), numpy.float32))
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


def _plane(values: numpy.ndarray, size, resample) -> Image.Image:
    data = numpy.clip(numpy.rint(values * 255.0), 0, 255).astype(numpy.uint8)
    return Image.fromarray(data, "L").resize(size, resample)


def repair_water_seams(image: Image.Image, mask, metres_per_px: float,
                       seams: Optional[WaterSeams] = None,
                       ) -> Tuple[Image.Image, WaterSeams]:
    """``(repaired, seams)``: the texture with its flagged water seams
    colour-matched and blurred (see the module doc), and what was found.

    ``mask`` is the texture's water mask (``L`` image or 2-D array, any
    square size; 255 is land); ``metres_per_px`` the ground size of one
    texture px.  The input image is never mutated; when nothing is
    flagged it is returned as is.  Every pixel whose mask is land, and
    every pixel within one mask px of land, is returned byte-identical.
    """
    mask = numpy.asarray(mask.convert("L") if isinstance(mask, Image.Image)
                         else mask)
    w = water_weight(mask, texture_px=image.size[0])
    if seams is None:
        seams = find_water_seams(image, mask, weight=w)
    if not seams.flagged:
        return image, seams
    mode = image.mode
    rgb = image.convert("RGB")
    size = rgb.size
    k = CENSUS_CELL // CELL
    offsets = _cell_offsets(seams) + numpy.kron(
        seams.tint, numpy.ones((k, k, 1), numpy.float32))
    matched = HARMONIZE.apply_color_field(rgb, offsets)
    # the blur and its band, on the cell grid (the blur is wide)
    cell_m = metres_per_px * size[0] / float(WORK) * CELL
    blurred = _water_blur(_reduce(_work_image(matched), CELL),
                          _reduce(w, CELL), BLUR_SIGMA_M / cell_m)
    blurred_im = Image.fromarray(
        numpy.clip(numpy.rint(blurred), 0, 255).astype(numpy.uint8),
        "RGB").resize(size, Image.BICUBIC)
    band = _band(seams, cell_m)
    mixed = Image.composite(blurred_im, matched,
                            _plane(band, size, Image.BILINEAR))
    result = Image.composite(mixed, rgb, _plane(w, size, Image.BILINEAR))
    if mode == "RGBA":
        result.putalpha(image.getchannel("A"))
    elif mode != "RGB":
        result = result.convert(mode)
    return result, seams
