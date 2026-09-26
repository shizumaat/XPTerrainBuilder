"""Colour harmonization v2 — seam-continuous correction field (pure leaf).

Ortho scenery tiles assemble textures flown on different dates, by different
campaigns, producing a patchwork of colour casts with hard steps at texture
seams.  ``docs/specs/color-harmonization-spec.md`` (v2, 2026-09-21, GitHub
issue #1) replaces the v1 per-texture constant shift — whose whole-texture
medians read the sea as the texture and minted a 26-count line along every
coast — with three ideas:

1. LAND comes from the builder's own mask tri-state (opaque mask ≥ 250; the
   feather band is shore, not land), never from a luminance gate alone.
2. The colour difference between two textures is MEASURED at the seam: the
   facing strips on either side photograph the same ground, so their
   difference is acquisition, not content (:func:`seam_cast`).
3. The correction is a per-texture offset FIELD solved by sparse least
   squares over the whole grid (:func:`solve_offset_field`) and applied by
   bilinear interpolation over texture centres (:func:`bilinear_field`,
   :func:`apply_color_field`): continuous by construction, so it can never
   add a step — two textures evaluate the same interpolant on their shared
   edge.

This module imports only numpy, scipy.sparse and PIL.  It performs no I/O,
holds no state and contains no randomness: every function is a
deterministic transform of its arguments.  Orchestration (statistics on the
download workers, the ``color_field.json`` sidecar, the download→convert
barrier, nested-zoom conditioning) lives in ``O4_Imagery_Utils``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy
from PIL import Image, ImageChops

# --- Frozen constants (spec §2, §5 defaults) ---------------------------------

# Per-channel strength as a function of zoom level, applied to the seam
# casts (spec §5 Q1, default kept).  At low zoom one texture covers enough
# ground that neighbouring blocks normally look alike, so most of the seam
# difference is acquisition and a strong pull is safe; at high zoom the
# textures are small enough that real content differences dominate, so the
# pull backs off.  Zoom levels at or below 16 use the ZL16 value, at or
# above 19 the ZL19 value.
STRENGTH_SCHEDULE_BY_ZOOMLEVEL = {
    16: 0.70,  # ZL <= 16
    17: 0.40,
    18: 0.20,
    19: 0.10,  # ZL >= 19
}

# Absolute per-channel cap on any texture's offset, in 0-255 counts.
MAXIMUM_SHIFT_MAGNITUDE = 20.0

# Every source image is reduced to this square before its statistics are
# computed, so cost is independent of the assembled texture size.
THUMBNAIL_SIZE = (512, 512)

# Rec. 601 luminance coefficients (0.299 R + 0.587 G + 0.114 B).
_LUMINANCE_COEFFICIENTS = numpy.array([0.299, 0.587, 0.114], dtype=numpy.float64)

# The luminance gate is kept ONLY for nodata white / cloud cores (upper
# bound) and true black (lower bound); water is excluded by the mask.
LUMINANCE_VALID_LOWER_BOUND = 10.0
LUMINANCE_VALID_UPPER_BOUND = 248.0

# A mask pixel at or above this value is opaque land; below it is the
# feather band (shore, wet sand, shallow water) or water (spec §5 Q6).
LAND_MASK_THRESHOLD = 250

# A texture is a WITNESS (carries seam data, receives a data-driven offset)
# when at least this fraction of its thumbnail is land.
WITNESS_LAND_FRACTION = 0.25

# Seam-strip width in thumbnail pixels: 8 of 512 = 64 texture pixels,
# about 140 m at ZL16.
STRIP_WIDTH = 8

# A seam carries a cast only when at least this many of its 512 rows are
# land on BOTH sides (10 %).
MINIMUM_SEAM_ROWS = 52

# Least-squares weights (spec §2.3): smoothness across every adjacent pair
# (water and non-witness textures inherit their neighbours harmonically)
# and the gauge that pins the field's mean near zero.
SMOOTHNESS_MU = 0.05
GAUGE_LAMBDA = 0.01

# Orthogrid tiles per texture edge at every zoom level.
GRID_STEP = 16

# The per-texture field is evaluated at this square and upsampled.
FIELD_SIZE = 256

SIDES = ("L", "R", "T", "B")
# The neighbour each side faces: (dx, dy) in grid steps and its facing side.
NEIGHBOUR_OF_SIDE = {
    "L": (-1, 0, "R"),
    "R": (1, 0, "L"),
    "T": (0, -1, "B"),
    "B": (0, 1, "T"),
}


def strength_for_zoomlevel(zoomlevel: int) -> float:
    """The seam-cast strength for a zoom level per the frozen schedule."""
    if zoomlevel <= 16:
        return STRENGTH_SCHEDULE_BY_ZOOMLEVEL[16]
    if zoomlevel >= 19:
        return STRENGTH_SCHEDULE_BY_ZOOMLEVEL[19]
    return STRENGTH_SCHEDULE_BY_ZOOMLEVEL[zoomlevel]


# --- Statistics (spec §2.1, §2.2) ----------------------------------------------


def thumbnail_and_land(
    image: Image.Image, land_class: str, mask_crop: Image.Image | None
) -> tuple[numpy.ndarray, numpy.ndarray]:
    """``(thumb, land)``: the 512² RGB thumbnail (uint8) of a source image
    and its boolean land mask at the same size.

    ``land_class`` is the builder's tri-state (``O4_Mask_Utils.
    land_class_for_texture``): ``"land"`` → every pixel is land, ``"water"``
    → none, ``"mask"`` → ``mask_crop`` resized with a box filter and
    thresholded at :data:`LAND_MASK_THRESHOLD` (feather excluded).  The
    luminance gate then removes nodata white / cloud cores and true black
    from the land set.
    """
    thumb = numpy.asarray(
        image.convert("RGB").resize(THUMBNAIL_SIZE, Image.BOX), dtype=numpy.uint8
    )
    if land_class == "water":
        land = numpy.zeros(THUMBNAIL_SIZE[::-1], dtype=bool)
    elif land_class == "mask" and mask_crop is not None:
        small = mask_crop.convert("L").resize(THUMBNAIL_SIZE, Image.BOX)
        land = numpy.asarray(small, dtype=numpy.uint8) >= LAND_MASK_THRESHOLD
    else:
        land = numpy.ones(THUMBNAIL_SIZE[::-1], dtype=bool)
    luminance = thumb.astype(numpy.float64) @ _LUMINANCE_COEFFICIENTS
    land &= (luminance > LUMINANCE_VALID_LOWER_BOUND) & (
        luminance < LUMINANCE_VALID_UPPER_BOUND
    )
    return thumb, land


def seam_strip_statistics(
    thumb: numpy.ndarray, land: numpy.ndarray, strip: int = STRIP_WIDTH
) -> dict:
    """Everything the field solve needs from one texture.

    ``strips``: per side (``L``/``R``/``T``/``B``), the per-row (per-column
    for T/B) mean colour across the ``strip``-pixel-wide edge band, shape
    ``(512, 3)`` float32.  ``land_strips``: per side, the rows whose whole
    band is land, shape ``(512,)`` bool.  ``land_fraction`` and ``witness``
    (≥ :data:`WITNESS_LAND_FRACTION`).
    """
    a = thumb.astype(numpy.float32)
    s = int(strip)
    strips = {
        "L": a[:, :s].mean(axis=1),
        "R": a[:, -s:].mean(axis=1),
        "T": a[:s, :].mean(axis=0),
        "B": a[-s:, :].mean(axis=0),
    }
    land_strips = {
        "L": land[:, :s].all(axis=1),
        "R": land[:, -s:].all(axis=1),
        "T": land[:s, :].all(axis=0),
        "B": land[-s:, :].all(axis=0),
    }
    land_fraction = float(land.mean())
    return {
        "strips": strips,
        "land_strips": land_strips,
        "land_fraction": land_fraction,
        "witness": land_fraction >= WITNESS_LAND_FRACTION,
    }


def seam_cast(
    stats_a: dict,
    side_a: str,
    stats_b: dict,
    side_b: str,
    min_rows: int = MINIMUM_SEAM_ROWS,
) -> tuple[numpy.ndarray, float] | None:
    """The colour step across one seam, measured on the facing strips.

    Returns ``(d, weight)`` with ``d = median over land rows of
    (B's strip − A's strip)`` per channel and ``weight = land_rows / rows``,
    or ``None`` when fewer than ``min_rows`` rows are land on BOTH sides
    (the seam carries no data).
    """
    rows = stats_a["land_strips"][side_a] & stats_b["land_strips"][side_b]
    n = int(rows.sum())
    if n < min_rows:
        return None
    diff = stats_b["strips"][side_b][rows] - stats_a["strips"][side_a][rows]
    d = numpy.median(diff.astype(numpy.float64), axis=0)
    return d, n / float(rows.size)


# --- The field (spec §2.3, §2.4) ------------------------------------------------


@dataclass
class OffsetField:
    """One (zoomlevel, provider) grid's solved offsets: a DENSE array over
    the bounding box of its textures (missing textures are harmonic
    fill-ins, so the interpolant is a function of ground position only —
    two textures beside a hole agree on what the hole is worth).

    ``origin`` is the ``(x, y)`` key of cell ``[0, 0]``; ``values`` has
    shape ``(ny, nx, 3)``; ``present[i, j]`` says whether a texture exists
    at that cell.
    """

    origin: tuple[int, int]
    step: int
    values: numpy.ndarray
    present: numpy.ndarray

    @property
    def shape(self) -> tuple[int, int]:
        return int(self.values.shape[0]), int(self.values.shape[1])

    def cell(self, key: tuple[int, int]) -> tuple[int, int]:
        """``(row, col)`` of a texture key (may lie outside the grid)."""
        return (
            (int(key[1]) - self.origin[1]) // self.step,
            (int(key[0]) - self.origin[0]) // self.step,
        )

    def has(self, key: tuple[int, int]) -> bool:
        i, j = self.cell(key)
        ny, nx = self.shape
        return 0 <= i < ny and 0 <= j < nx and bool(self.present[i, j])

    def offset(self, key: tuple[int, int]) -> numpy.ndarray | None:
        """The centre offset of one texture, or ``None`` when absent."""
        if not self.has(key):
            return None
        i, j = self.cell(key)
        return self.values[i, j].copy()

    def sample(self, gx, gy) -> numpy.ndarray:
        """Bilinear sample at continuous cell coordinates (``gx`` along
        columns/x, ``gy`` along rows/y; the centre of cell ``[i, j]`` is
        ``(j, i)``), coordinates CLAMPED to the grid (Neumann: the field
        is flat beyond its last texture centre).  Broadcasts over arrays.
        """
        ny, nx = self.shape
        gx = numpy.clip(numpy.asarray(gx, dtype=numpy.float64), 0.0, nx - 1)
        gy = numpy.clip(numpy.asarray(gy, dtype=numpy.float64), 0.0, ny - 1)
        c0 = numpy.floor(gx).astype(int)
        r0 = numpy.floor(gy).astype(int)
        c1 = numpy.minimum(c0 + 1, nx - 1)
        r1 = numpy.minimum(r0 + 1, ny - 1)
        tx = (gx - c0)[..., None]
        ty = (gy - r0)[..., None]
        v = self.values
        top = (1.0 - tx) * v[r0, c0] + tx * v[r0, c1]
        bottom = (1.0 - tx) * v[r1, c0] + tx * v[r1, c1]
        return (1.0 - ty) * top + ty * bottom

    def to_json(self) -> dict:
        ny, nx = self.shape
        keys = [
            [int(self.origin[0] + j * self.step), int(self.origin[1] + i * self.step)]
            for i in range(ny)
            for j in range(nx)
            if self.present[i, j]
        ]
        return {
            "origin": [int(self.origin[0]), int(self.origin[1])],
            "step": int(self.step),
            "shape": [ny, nx],
            "values": numpy.round(self.values, 3).tolist(),
            "present": keys,
        }

    @classmethod
    def from_json(cls, record: dict) -> "OffsetField":
        ny, nx = (int(v) for v in record["shape"])
        values = numpy.asarray(record["values"], dtype=numpy.float32).reshape(ny, nx, 3)
        origin = (int(record["origin"][0]), int(record["origin"][1]))
        step = int(record["step"])
        present = numpy.zeros((ny, nx), dtype=bool)
        for x, y in record["present"]:
            present[(int(y) - origin[1]) // step, (int(x) - origin[0]) // step] = True
        return cls(origin, step, values, present)


def solve_offset_field(
    keys,
    seams,
    strength: float,
    anchors=(),
    witnesses=None,
    mu: float = SMOOTHNESS_MU,
    lam: float = GAUGE_LAMBDA,
    step: int = GRID_STEP,
) -> OffsetField:
    """Solve one grid's per-texture RGB offsets (spec §2.3).

    Minimises, over one offset ``o`` per grid cell of the textures' bounding
    box::

        Σ_seams   w·(o_B − o_A + s·d_AB)²      (the measured casts)
      + Σ_anchors w·(o_i − c_i)²               (cross-zoom conditioning, §2.5)
      + μ Σ_adjacent (o_B − o_A)²              (harmonic through water/holes)
      + λ Σ_i o_i²                             (gauge)

    ``keys``: every ``(x, y)`` texture of the grid, witness or not.
    ``seams``: ``(key_a, key_b, d, weight)`` with ``d`` = B − A per channel.
    ``anchors``: ``(key, c, weight)`` absolute targets.  ``strength`` is
    ``s``.  After the solve the offsets are clipped to
    ±:data:`MAXIMUM_SHIFT_MAGNITUDE`; when the grid has no anchors and
    ``witnesses`` is given, the witness mean is subtracted (no whole-tile
    hue drift) and the clip re-applied.  The linear system is sparse,
    symmetric positive-definite, ≤ 3·N unknowns, solved with
    ``scipy.sparse.linalg.spsolve`` — deterministic.
    """
    from scipy import sparse
    from scipy.sparse.linalg import spsolve

    keys = [(int(k[0]), int(k[1])) for k in keys]
    if not keys:
        return OffsetField((0, 0), step, numpy.zeros((0, 0, 3), numpy.float32),
                           numpy.zeros((0, 0), bool))
    x0 = min(k[0] for k in keys)
    y0 = min(k[1] for k in keys)
    nx = (max(k[0] for k in keys) - x0) // step + 1
    ny = (max(k[1] for k in keys) - y0) // step + 1
    n = nx * ny

    def idx(key):
        return ((key[1] - y0) // step) * nx + (key[0] - x0) // step

    present = numpy.zeros((ny, nx), dtype=bool)
    for k in keys:
        present[(k[1] - y0) // step, (k[0] - x0) // step] = True

    rows, cols, vals = [], [], []
    rhs = numpy.zeros((n, 3), dtype=numpy.float64)

    def pair(i, j, w):
        rows.extend((i, j, i, j))
        cols.extend((i, j, j, i))
        vals.extend((w, w, -w, -w))

    # the measured casts
    measured = set()
    for key_a, key_b, d, w in seams:
        a, b = idx(key_a), idx(key_b)
        w = float(w)
        pair(a, b, w)
        measured.add((min(a, b), max(a, b)))
        d = numpy.asarray(d, dtype=numpy.float64) * float(strength)
        rhs[b] -= w * d
        rhs[a] += w * d
    # smoothness across every adjacent pair of the dense grid that carries
    # NO cast (water, holes and non-witnesses inherit harmonically, spec
    # §2.3).  A pair with a cast is left to its data term alone: a μ term
    # on it shrinks the seam residual by w/(w+μ) — a 40-count cast at
    # strength 0.7 solved to −26.7 instead of −28 with μ on every pair.
    for i in range(ny):
        for j in range(nx):
            p = i * nx + j
            if j + 1 < nx and (p, p + 1) not in measured:
                pair(p, p + 1, mu)
            if i + 1 < ny and (p, p + nx) not in measured:
                pair(p, p + nx, mu)
    # absolute anchors
    for key, c, w in anchors:
        p = idx(key)
        w = float(w)
        rows.append(p)
        cols.append(p)
        vals.append(w)
        rhs[p] += w * numpy.asarray(c, dtype=numpy.float64)
    # the gauge
    rows.extend(range(n))
    cols.extend(range(n))
    vals.extend([lam] * n)

    matrix = sparse.csc_matrix(
        (numpy.asarray(vals, dtype=numpy.float64), (rows, cols)), shape=(n, n)
    )
    solution = spsolve(matrix, rhs)
    solution = numpy.asarray(solution, dtype=numpy.float64).reshape(n, 3)
    solution = numpy.clip(solution, -MAXIMUM_SHIFT_MAGNITUDE, MAXIMUM_SHIFT_MAGNITUDE)
    if witnesses and not anchors:
        witness_rows = [idx((int(k[0]), int(k[1]))) for k in witnesses]
        if witness_rows:
            solution -= solution[witness_rows].mean(axis=0)
            solution = numpy.clip(
                solution, -MAXIMUM_SHIFT_MAGNITUDE, MAXIMUM_SHIFT_MAGNITUDE
            )
    values = solution.reshape(ny, nx, 3).astype(numpy.float32)
    return OffsetField((x0, y0), step, values, present)


# --- Nested zoom levels (spec §2.5) ----------------------------------------------


def covering_key(key, zoomlevel: int, coarse_zoomlevel: int, step: int = GRID_STEP):
    """``(coarse_key, rx, ry, factor)``: the texture of ``coarse_zoomlevel``
    that covers the finer texture ``key`` of ``zoomlevel``, the finer
    texture's sub-square index ``(rx, ry)`` inside it (``0 ≤ rx, ry <
    factor``) and ``factor = 2 ** (zoomlevel − coarse_zoomlevel)``.
    """
    factor = 2 ** (int(zoomlevel) - int(coarse_zoomlevel))
    x, y = int(key[0]), int(key[1])
    cx = (x // (step * factor)) * step
    cy = (y // (step * factor)) * step
    return (cx, cy), (x - factor * cx) // step, (y - factor * cy) // step, factor


def edge_midpoint_offset(side: str, rx: int, ry: int, factor: int) -> tuple[float, float]:
    """Where the finer texture's ``side`` edge midpoint lies inside its
    covering coarse texture, in coarse-cell units relative to the coarse
    texture's CENTRE (``(-0.5, -0.5)`` is the coarse top-left corner)."""
    cx = (rx + 0.5) / factor - 0.5
    cy = (ry + 0.5) / factor - 0.5
    if side == "L":
        cx = rx / factor - 0.5
    elif side == "R":
        cx = (rx + 1) / factor - 0.5
    elif side == "T":
        cy = ry / factor - 0.5
    elif side == "B":
        cy = (ry + 1) / factor - 0.5
    return cx, cy


def cross_zoom_cast(
    stats_fine: dict,
    side: str,
    thumb_coarse: numpy.ndarray,
    land_coarse: numpy.ndarray,
    rx: int,
    ry: int,
    factor: int,
    strip: int = STRIP_WIDTH,
    min_fraction: float = MINIMUM_SEAM_ROWS / 512.0,
) -> tuple[numpy.ndarray, float] | None:
    """The colour step between a finer texture's outer ``side`` strip and
    the co-located sub-strip of the coarse thumbnail that covers it
    (spec §2.5).  The fine strip (512 rows) is block-averaged to the
    coarse sub-square's ``512 / factor`` rows; the coarse sub-strip is
    ``strip / factor`` (≥ 1) thumbnail pixels wide.  Returns ``(d, weight)``
    with ``d = median over land rows of (coarse − fine)`` per channel and
    ``weight = land_rows / rows``, or ``None`` when fewer than
    ``min_fraction`` of the rows are land on both sides.
    """
    n = int(thumb_coarse.shape[0])
    sub = n // factor
    w = max(1, strip // factor)
    fine_strip = numpy.asarray(stats_fine["strips"][side], dtype=numpy.float64)
    fine_land = numpy.asarray(stats_fine["land_strips"][side], dtype=bool)
    rows_fine = fine_strip.shape[0]
    block = rows_fine // sub
    if sub < 1 or block < 1 or rows_fine != sub * block:
        return None
    fine_strip = fine_strip.reshape(sub, block, 3).mean(axis=1)
    fine_land = fine_land.reshape(sub, block).all(axis=1)
    x0, y0 = rx * sub, ry * sub
    coarse = numpy.asarray(thumb_coarse, dtype=numpy.float64)
    land_coarse = numpy.asarray(land_coarse, dtype=bool)
    if side == "L":
        region = coarse[y0:y0 + sub, x0:x0 + w]
        land = land_coarse[y0:y0 + sub, x0:x0 + w]
        axis = 1
    elif side == "R":
        region = coarse[y0:y0 + sub, x0 + sub - w:x0 + sub]
        land = land_coarse[y0:y0 + sub, x0 + sub - w:x0 + sub]
        axis = 1
    elif side == "T":
        region = coarse[y0:y0 + w, x0:x0 + sub]
        land = land_coarse[y0:y0 + w, x0:x0 + sub]
        axis = 0
    else:
        region = coarse[y0 + sub - w:y0 + sub, x0:x0 + sub]
        land = land_coarse[y0 + sub - w:y0 + sub, x0:x0 + sub]
        axis = 0
    coarse_strip = region.mean(axis=axis)
    coarse_land = land.all(axis=axis)
    rows = fine_land & coarse_land
    k = int(rows.sum())
    if k < max(1, int(round(min_fraction * sub))):
        return None
    d = numpy.median(coarse_strip[rows] - fine_strip[rows], axis=0)
    return d, k / float(sub)


def bilinear_field(field: OffsetField, key, size: int = FIELD_SIZE) -> numpy.ndarray:
    """The correction field over one texture: ``(size, size, 3)`` float32,
    the bilinear interpolant of the grid's centre offsets evaluated at the
    texture's pixel centres (spec §2.4).  Two textures evaluate the SAME
    interpolant on their shared edge, so the step the correction introduces
    there is rounding only.
    """
    i, j = field.cell(key)
    u = (numpy.arange(size, dtype=numpy.float64) + 0.5) / size - 0.5
    gx = j + u
    gy = i + u
    return field.sample(gx[None, :], gy[:, None]).astype(numpy.float32)


def apply_color_field(image: Image.Image, field: numpy.ndarray) -> Image.Image:
    """Add a correction field to an image with saturating uint8 arithmetic.

    ``field`` is a ``(h, w, 3)`` float array (any size).  It is rounded to
    whole counts, BIASED by +128 into uint8, upsampled with
    ``Image.BILINEAR`` to the image size and added with PIL's saturating
    ``ImageChops.add(..., offset=-128)`` in C — the sum is formed in int
    and clipped once, at the end.  No float copy of the 4096² texture is
    ever made, and the whole apply is ONE upsample and ONE chop (spec §6:
    the budget is a per-texture 0.15 s, and each full-size pass costs about
    half of it).

    The bias is exact for any field within ±128 counts, which the ±20 clip
    of :func:`solve_offset_field` guarantees.  Splitting the field into a
    positive and a negative part instead — one upsample and one chop each —
    costs twice as much AND rounds differently: the intermediate
    ``add`` saturates at 255 before the negative part is subtracted, so a
    bright pixel under a field that changes sign across the texture came
    out up to 10 counts wrong.

    RGB and RGBA inputs are supported; alpha passes through untouched.  The
    input is never mutated.  When the whole field rounds to zero a copy is
    returned unchanged.
    """
    rounded = numpy.rint(numpy.asarray(field, dtype=numpy.float32))
    if not numpy.any(rounded):
        return image.copy()
    biased = numpy.clip(rounded + 128.0, 0, 255).astype(numpy.uint8)
    has_alpha = image.mode == "RGBA"
    if has_alpha:
        red, green, blue, alpha = image.split()
        rgb = Image.merge("RGB", (red, green, blue))
    else:
        rgb = image.convert("RGB")
    upsampled = Image.fromarray(biased, "RGB").resize(rgb.size, Image.BILINEAR)
    result = ImageChops.add(rgb, upsampled, 1.0, -128)
    if has_alpha:
        result.putalpha(alpha)
    return result
