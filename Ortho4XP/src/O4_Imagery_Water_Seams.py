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
* :func:`_find_water_seams` -- on a :data:`WORK`-px copy, the colour step
  across every vertical and horizontal line in EXCESS of the slope either
  side, averaged along the line over :data:`LINE` px.  A point is a seam
  where that step, times the mask's opacity, reaches :data:`MIN_STEP`
  with :data:`COHERENCE` (a ground edge crossing at an angle, or the
  ground's own texture, averages out), is the strongest across the line,
  lies in water, and belongs to a straight run of :data:`MIN_RUN` px; the
  run then grows along its line through weaker points (hysteresis); a
  shorter run counts where it turns a square corner (:data:`MIN_CORNER_RUN`).
  Red-cast squares (:func:`_red_squares`): patches of census cells whose
  R-G cast over their surroundings reaches :data:`RED_EXCESS`, bright and
  square enough to be a source tile; around them the lines measure
  brightness only (the tint owns the cast).  Outlier, red and cloud-like
  cells are counted for the report.
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
from PIL import Image
from scipy import ndimage, sparse
from scipy.sparse.linalg import factorized

import O4_Color_Harmonization as HARMONIZE

__all__ = [
    "apply_on_water",
    "repair_water_seams",
    "shows_water",
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
# ... it is the strongest within this many work px across the line (past
# the control lines two strips away, where the excess echoes the step) ...
SUPPRESS = 2 * STRIP + 1
# ... both sides are at least this much water ...
MIN_WATER = 0.5
# ... and it belongs to a straight run at least this long (work px, ~490 m
# at ZL16) -- or this long (~140 m) where it turns a square corner with a
# perpendicular run within CORNER_GAP px (a source tile's side).
MIN_RUN = 56
MIN_CORNER_RUN = 24
CORNER_GAP = 3
CORNER_COSINE = 0.8
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
# cells, the R-G cast over the median of the cells within this many cells
# around reaches RED_EXCESS over a patch of at least TINT_MIN_CELLS cells
# that fills TINT_FILL of its bounding box (a source tile, not a reef).
TINT_REFERENCE = 15
TINT_MIN_CELLS = 9
TINT_FILL = 0.6
# ... where the patch is bright enough for a cast to read as red (on dark
# water a 10-count R-G excess is no colour at all) ...
TINT_MIN_LUMA = 70.0
# ... each cell tinted by its own cast, softened over this many cells ...
TINT_SOFTEN = 0.75
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
            labels, _count = ndimage.label(flags, structure=_DRIFT)
            lengths += [box[0].stop - box[0].start
                        for box in ndimage.find_objects(labels)]
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
# A reported run continues to the next row one column either side.
_DRIFT = numpy.array([[1, 1, 1], [0, 1, 0], [1, 1, 1]], dtype=bool)


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


def _vertical_lines(a: numpy.ndarray, w: numpy.ndarray, opacity: numpy.ndarray,
                    grey: Optional[numpy.ndarray] = None):
    """``(evidence, strong, weak)`` of the vertical lines of ``a``: the
    averaged excess step (see :class:`_WaterSeams`) and the points passing
    the strong and the weak test; the horizontal ones are this on the
    transpose.  Where ``grey`` is set the step is its luminance only."""
    s = STRIP
    after = sum(_shift(a, k) for k in range(s)) / s
    before = sum(_shift(a, -1 - k) for k in range(s)) / s
    step = after - before
    excess = step - 0.5 * (_shift(step, -2 * s) + _shift(step, 2 * s))
    if grey is not None:  # brightness only: (l, l, l), l the luminance step
        excess[grey] = (excess[grey] @ _LUMA)[:, None]
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
    strong = candidate & (visible >= MIN_STEP) & (
        magnitude >= COHERENCE * spread)
    weak = candidate & (visible >= WEAK_STEP) & (
        magnitude >= WEAK_COHERENCE * spread)
    return evidence.astype(numpy.float32), strong, weak


def _thick(flags: numpy.ndarray) -> numpy.ndarray:
    """``flags`` widened by one column each side: a line whose strongest
    point wanders by a pixel stays whole in its own column."""
    return flags | _shift(flags, 1) | _shift(flags, -1)


def _column_runs(flags: numpy.ndarray):
    """Labels of the runs of ``flags`` down each column (count, labels)."""
    labels, count = ndimage.label(flags, structure=_VERTICAL)
    return labels, count


def _runs(flags: numpy.ndarray):
    """``(labels, table)``: the straight vertical runs of ``flags`` (down
    one column of :func:`_thick`) and per label ``[column, first row, end
    row]`` (row 0 of the table unused)."""
    labels, count = _column_runs(_thick(flags))
    table = numpy.zeros((count + 1, 3), dtype=int)
    for k, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is not None:
            table[k] = (box[1].start, box[0].start, box[0].stop)
    return labels, table


def _touching(runs: numpy.ndarray, others: numpy.ndarray, steps: numpy.ndarray,
              other_steps: numpy.ndarray) -> numpy.ndarray:
    """Per run (vertical, ``[column, row0, row1]``), whether one of its ends
    meets a perpendicular run (``[row, column0, column1]``) -- at the
    other's end or on its line, within :data:`CORNER_GAP` -- stepping the
    same colour (|cosine| of the two mean steps at least
    :data:`CORNER_COSINE`: the one patch of another flight on both
    sides)."""
    if not len(runs) or not len(others):
        return numpy.zeros(len(runs), dtype=bool)
    unit = steps / numpy.maximum(numpy.linalg.norm(steps, axis=1), 1e-6)[:, None]
    other_unit = other_steps / numpy.maximum(
        numpy.linalg.norm(other_steps, axis=1), 1e-6)[:, None]
    alike = numpy.abs(unit @ other_unit.T) >= CORNER_COSINE
    g = CORNER_GAP
    c, r0, r1 = (runs[:, k, None] for k in range(3))
    r, c0, c1 = (others[None, :, k] for k in range(3))
    on_other = (c >= c0 - g) & (c <= c1 - 1 + g)
    end_meets = on_other & ((numpy.abs(r - r0) <= g)
                            | (numpy.abs(r - (r1 - 1)) <= g))
    on_run = (r >= r0 - g) & (r <= r1 - 1 + g)
    other_end_meets = on_run & ((numpy.abs(c0 - c) <= g)
                                | (numpy.abs(c1 - 1 - c) <= g))
    return ((end_meets | other_end_meets) & alike).any(axis=1)


def _mean_steps(evidence: numpy.ndarray, flags: numpy.ndarray,
                labels: numpy.ndarray, count: int) -> numpy.ndarray:
    """``(count + 1, 3)``: each run's mean step over its flagged points."""
    marked = numpy.where(flags, labels, 0).ravel()
    counts = numpy.maximum(numpy.bincount(marked, minlength=count + 1), 1)
    return numpy.stack([numpy.bincount(marked, evidence[..., c].ravel(),
                                       minlength=count + 1) / counts
                        for c in range(3)], axis=-1)


def _straight_pairs(strong_x: numpy.ndarray, strong_y: numpy.ndarray,
                    evidence_x: numpy.ndarray, evidence_y: numpy.ndarray):
    """The strong points of each orientation on a run long enough ALONE
    (:data:`MIN_RUN`), or long enough to be a square's side
    (:data:`MIN_CORNER_RUN`) and meeting a perpendicular one at a corner:
    a source tile's edges are straight AND turn square, a channel bank that
    is straight for a while does neither for long."""
    labels_x, runs_x = _runs(strong_x)
    labels_y, runs_y = _runs(strong_y.T)
    length_x = runs_x[:, 2] - runs_x[:, 1]
    length_y = runs_y[:, 2] - runs_y[:, 1]
    side_x = length_x >= MIN_CORNER_RUN
    side_y = length_y >= MIN_CORNER_RUN
    side_x[0] = side_y[0] = False
    keep_x = length_x >= MIN_RUN
    keep_y = length_y >= MIN_RUN
    steps_x = _mean_steps(evidence_x, strong_x, labels_x, len(runs_x) - 1)
    steps_y = _mean_steps(evidence_y.transpose(1, 0, 2), strong_y.T,
                          labels_y, len(runs_y) - 1)
    keep_x[side_x] |= _touching(runs_x[side_x], runs_y[side_y],
                                steps_x[side_x], steps_y[side_y])
    keep_y[side_y] |= _touching(runs_y[side_y], runs_x[side_x],
                                steps_y[side_y], steps_x[side_x])
    keep_x[0] = keep_y[0] = False
    return strong_x & keep_x[labels_x], strong_y & keep_y[labels_y].T


def _grown(strong: numpy.ndarray, weak: numpy.ndarray) -> numpy.ndarray:
    """Hysteresis: the weak points on the same straight run as a strong
    one, so a seam keeps its line where its step weakens."""
    either = strong | weak
    labels, count = _column_runs(_thick(either))
    if not count:
        return strong
    keep = numpy.zeros(count + 1, dtype=bool)
    keep[numpy.unique(labels[strong])] = True
    keep[0] = False
    return either & keep[labels]


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
    """``(tint, tinted)`` on the :data:`WORK` grid: every red-cast square's
    census cells and the offset that removes each cell's cast over the
    water just around the square, luminance kept, softened over
    :data:`TINT_SOFTEN` cells (the square's own edge is up to half a cell
    off; the tint band hides that)."""
    k = CENSUS_CELL
    cell = _reduce(a, k)
    water = _reduce(w, k) >= MIN_WATER
    chroma = numpy.stack([cell[..., 0] - cell[..., 1],
                          cell[..., 2] - cell[..., 1]], axis=-1)
    # the surroundings' median on cells twice as coarse (a quarter of the
    # cost; the reference is smooth by construction)
    coarse = _reduce(chroma, 2)
    ref = numpy.stack([ndimage.median_filter(coarse[..., c],
                                             TINT_REFERENCE // 2 + 1,
                                             mode="nearest") for c in range(2)],
                      axis=-1)
    excess = chroma - numpy.kron(ref, numpy.ones((2, 2, 1), numpy.float32))
    tint = numpy.zeros(cell.shape, dtype=numpy.float32)
    tinted = numpy.zeros(water.shape, dtype=bool)
    labels, _count = ndimage.label(water & (excess[..., 0] >= RED_EXCESS))
    for label, box in enumerate(ndimage.find_objects(labels), start=1):
        part = labels[box] == label
        if (part.sum() < TINT_MIN_CELLS or part.mean() < TINT_FILL
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


def _work_image(image: Image.Image) -> numpy.ndarray:
    small = image.convert("RGB").resize((WORK, WORK), Image.BOX)
    return numpy.asarray(small, dtype=numpy.float32)


def _reduce(a: numpy.ndarray, k: int) -> numpy.ndarray:
    n = a.shape[0] // k
    return a.reshape(n, k, n, k, *a.shape[2:]).mean(axis=(1, 3))


def _find_water_seams(image: Image.Image, mask: numpy.ndarray,
                     weight: Optional[numpy.ndarray] = None,
                     census: bool = False) -> _WaterSeams:
    """The flagged seams of one texture (see the module doc).  ``mask`` is
    the texture's water mask (any square size, 255 = land); ``census``
    also counts the outlier, red and cloud-like cells (a report)."""
    a = _work_image(image)
    mask = numpy.asarray(mask)
    w = _water_weight(mask) if weight is None else weight
    opacity = _opacity(mask)
    # the red squares first: around them the lines see brightness only,
    # so a square's brightness step is matched and its cast (the tint's)
    # not twice
    tint, tinted = _red_squares(a, w)
    grey = None
    if tinted.any():
        grey = ndimage.binary_dilation(tinted, iterations=SUPPRESS + STRIP)
    ex, strong_x, weak_x = _vertical_lines(a, w, opacity, grey)
    ey, strong_y, weak_y = _vertical_lines(
        a.transpose(1, 0, 2), w.T, opacity.T,
        None if grey is None else grey.T)
    strong_x, strong_y = _straight_pairs(strong_x, strong_y.T, ex,
                                         ey.transpose(1, 0, 2))
    fx = _grown(strong_x, weak_x)
    fy = _grown(strong_y.T, weak_y).T
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
        seams = _find_water_seams(image, mask, weight=w)
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
