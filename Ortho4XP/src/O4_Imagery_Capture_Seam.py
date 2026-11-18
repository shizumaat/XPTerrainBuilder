"""Capture seams inside ONE photo provider's mosaic, and the colour field
that closes them (#2108).

A provider's mosaic joins scenes flown or shot on different days: where
two meet, the ground on one side reads darker, greyer or warmer than on the
other, along a line that ignores the ground (a N-S satellite strip edge
110 km long, with jogs, through the desert at 34 N 116 W).  The #2018
provider blend (``O4_Imagery_Provider_Blend``) acts only across tile edges
between two providers, and colour harmonization only at texture edges, so
a seam inside one provider's texture squares was never corrected.

* :func:`find_seams` -- the seams of one tile's mosaic (the provider's
  texture squares at :data:`SAMPLE` px each, ~63 m at 34 N): per band of
  :data:`BAND` rows (~1 km) the colour step across every column boundary
  (the mean of a :data:`STRIP`-px strip each side, :data:`GAP` px left out
  for the provider's own feather); candidates are steps of at least
  :data:`MIN_STEP` counts; a seam is a chain of candidates band after band
  (a jog of up to :data:`JOG` px allowed) whose steps point the same way
  (cosine :data:`MIN_COS`) over at least :data:`MIN_BANDS` bands, with a
  candidate in :data:`MIN_COVER` of them, standing still from
  :data:`MIN_STILL` of its bands to the next and stepping
  :data:`MIN_SEAM_STEP` at the median band, its far strips stepping the
  same way (:data:`MIN_FAR`) and its rows lying on a drawn line
  (:data:`MIN_TRUE`) -- a capture seam is a straight cut between two
  scenes; a mountain front, a shore, a road or a field edge follows the
  ground, ends or changes its step within a few km.  Last, a line is a
  seam only where another provider (:func:`reference_provider`, its
  squares on the line fetched) does NOT step the same way
  (:data:`MAX_REF`): a ground edge -- a farm against desert, a shore --
  shows in every photo, a capture seam in one.  Two lines stepping
  opposite ways a few px apart are a road's sides (:data:`PAIR`).  Steps
  where a side is dark water
  (:data:`WATER_LUMA`) or textureless against a textured side
  (:data:`FLAT_RATIO`) are never candidates.  Both axes are searched (a
  transposed mosaic for E-W seams); tilted seams beyond ~7 degrees are not.
* :class:`Seam` -- one seam: its line row by row and its knots (the
  colour move of each side, band by band), in ZL16 map-tile units.
* :class:`SeamField` -- the correction: each side moves halfway toward the
  other at the line, the move falling linearly to 0 at :data:`FEATHER_M`
  from it, across a :data:`RAMP_M` ramp at the line itself (the
  provider's feather; a continuous field, so it never adds a step at a
  texture edge -- ``O4_Color_Harmonization``'s lesson of 2026-09-18), and
  fading in over :data:`END_M` from a seam's ends inside the mosaic.
  :meth:`SeamField.fields` has ``Blend.fields``' shape, so
  ``O4_Imagery_Provider_Blend.add_field`` sums both.
* :class:`SeamBook` / :func:`book` -- the seams found, per tile and
  provider, in the data folder (every tier and every later conversion of
  a tile reads the same seams); :func:`attach` gives a tile its field.

No tile or airport is named here.
"""
from __future__ import annotations

import math
import os
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

import numpy
import O4_Imagery_Provider_Cast as CAST

__all__ = ["attach"]      # the rest is read by this module and its twin

#: Seams are found on the provider's ZL16 squares (the casts' zoom)...
SEAM_ZL = CAST.CAST_ZL
#: ...each reduced to this many px per side (``CAST.fetch_square``'s).
SAMPLE = 128
#: Rows averaged into one band (one knot): ~1 km at 34 N.
BAND = 16
#: Columns left out at a boundary (the provider's own feather, ~150 m)...
GAP = 4
#: ...and the strip measured each side of them.
STRIP = 3
#: A band's step (RGB distance, counts) at least this is a candidate.
MIN_STEP = 15.0
#: A chain may jump this many px from one band to the next (a jog).
JOG = 12
#: ...and its steps' directions agree at least this well.
MIN_COS = 0.8
#: A seam holds at least this many bands (~8 km at 34 N)...
MIN_BANDS = 8
#: ...stands still (a jog of at most :data:`STILL` px) from this share of
#: its bands to the next...
STILL = 2
MIN_STILL = 0.6
#: ...holds a candidate in this share of the bands it spans...
MIN_COVER = 0.85
#: ...misses at most this many bands in a row...
MAX_MISS = 1
#: ...and steps this much at the median band (RGB distance, counts): a
#: seam a pilot sees, not a shade a field edge also makes.
MIN_SEAM_STEP = 25.0
#: The far strips: :data:`FAR` px wide, :data:`FAR` px beyond the near
#: ones (~0.5 km).  A seam parts two scenes, so the far strips step the
#: same way at least :data:`MIN_FAR` as much as the near ones at the
#: median band; a road or a field edge parts two fields and the ground
#: beyond them is alike.
FAR = 8
MIN_FAR = 0.5
#: The reference provider's step along ours, as a share of ours, at the
#: median band: at least this, the line is the ground's (a seam is not).
MAX_REF = 0.35
#: Two lines this close (px) stepping opposite ways are a road's or a
#: canal's two sides (:func:`_unpaired`).
PAIR = 2 * (GAP // 2 + STRIP)
#: Rows within 1 px of the line around them, at least (:func:`_drawn`).
MIN_TRUE = 0.72
#: A side this dark (mean luminance) is water: no candidate.
WATER_LUMA = 40.0
#: A side this much flatter than the other (luminance std ratio) is
#: water or a paved surface against textured ground: no candidate.
FLAT_RATIO = 0.25
#: The field: the ramp at the line, the feather each side, the fade-in
#: from a seam's ends (metres).
RAMP_M = 200.0
FEATHER_M = 800.0
END_M = 800.0
#: Providers with world cover, the first the reference of every other
#: (:func:`reference_provider`).
REFERENCES = ("Arc", "BI")
#: The field's samples per texture edge (``O4_Imagery_Provider_Blend``).
FIELD_SIZE = 256
_LUMA = numpy.array([0.299, 0.587, 0.114])
_EARTH_M = 40075016.686
_BOOK_NAME = "capture_seams.json"
#: The book's key carries this: seams found by other rules are found again.
_RULES = "v1"
RGB = Tuple[float, float, float]


@dataclass(frozen=True)
class Seam:
    """One capture seam.  ``axis`` "V" (runs north-south: ``along`` is the
    ZL16 map-tile y, ``across`` the x) or "H" (east-west: the other way
    round).  ``line``: ``(along, across)`` row by row; ``knots``:
    ``(along, offset_a, offset_b)`` band by band, the RGB move at the line
    of the side of smaller ``across`` (west or north) and of the other;
    ``open_start`` / ``open_end``: the seam runs off the mosaic there (no
    fade-in at that end)."""

    axis: str
    line: Tuple[Tuple[float, float], ...]
    knots: Tuple[Tuple[float, RGB, RGB], ...]
    open_start: bool = False
    open_end: bool = False

    def as_dict(self) -> dict:
        return {"axis": self.axis, "open": [self.open_start, self.open_end],
                "line": [[round(a, 4), round(c, 4)] for a, c in self.line],
                "knots": [[round(a, 4)] + [round(v, 2) for v in oa + ob]
                          for a, oa, ob in self.knots]}

    @classmethod
    def from_dict(cls, value: dict) -> "Seam":
        return cls(str(value["axis"]),
                   tuple((float(a), float(c)) for a, c in value["line"]),
                   tuple((float(k[0]), tuple(float(v) for v in k[1:4]),
                          tuple(float(v) for v in k[4:7]))
                         for k in value["knots"]),
                   bool(value["open"][0]), bool(value["open"][1]))


# --- finding ---------------------------------------------------------------

def _valid(mosaic: numpy.ndarray) -> numpy.ndarray:
    ok = numpy.isfinite(mosaic).all(axis=-1)
    luma = numpy.where(ok, numpy.nan_to_num(mosaic) @ _LUMA, 0.0)
    return ok & (luma >= 10.0) & (luma <= 248.0)


def _boundaries(width: int, gap: int, strip: int) -> numpy.ndarray:
    return numpy.arange(gap // 2 + strip, width - (gap - gap // 2) - strip + 1)


def _strips(mosaic: numpy.ndarray, ok: numpy.ndarray, gap: int, strip: int):
    """Per row, at every column boundary ``c`` (between columns ``c - 1``
    and ``c``, :func:`_boundaries`): the RGB sums of the strip left and
    right (``(h, n, 3)``), the sums of their luminance squares
    (``(h, n)``) and whether every pixel of both strips is valid."""
    h, w = ok.shape
    x = numpy.where(ok[..., None], numpy.nan_to_num(mosaic), 0.0)
    luma = x @ _LUMA

    def cum(a):
        pad = numpy.zeros((h, 1) + a.shape[2:])
        return numpy.concatenate([pad, a.cumsum(axis=1)], axis=1)
    cs, cq, co = cum(x), cum(luma ** 2), cum(ok.astype(numpy.float64))
    c = _boundaries(w, gap, strip)
    left, right = c - gap // 2 - strip, c + gap - gap // 2

    def take(a, lo):
        return a[:, lo + strip] - a[:, lo]
    full = (take(co, left) == strip) & (take(co, right) == strip)
    return (c, take(cs, left), take(cs, right), take(cq, left),
            take(cq, right), full)


def _bands(mosaic: numpy.ndarray):
    """Band by band at every boundary: ``(c, step, mean_a, mean_b,
    usable)`` -- ``step`` the mean ``right - left`` (``(nb, n, 3)``) over
    the band's rows whose strips are whole; ``usable`` where at least half
    the rows are, neither side is water and neither is flat against a
    textured other."""
    ok = _valid(mosaic)
    c, sl, sr, ql, qr, full = _strips(mosaic, ok, GAP, STRIP)
    nb = ok.shape[0] // BAND

    def per_band(a):
        a = a[:nb * BAND]
        return a.reshape((nb, BAND) + a.shape[1:]).sum(axis=1)
    rows = per_band(full.astype(numpy.float64))
    n = numpy.maximum(rows * STRIP, 1.0)
    keep = full[..., None]
    mean_a = per_band(numpy.where(keep, sl, 0.0)) / n[..., None]
    mean_b = per_band(numpy.where(keep, sr, 0.0)) / n[..., None]
    luma_a, luma_b = mean_a @ _LUMA, mean_b @ _LUMA
    sd_a = numpy.sqrt(numpy.maximum(
        per_band(numpy.where(full, ql, 0.0)) / n - luma_a ** 2, 0.0))
    sd_b = numpy.sqrt(numpy.maximum(
        per_band(numpy.where(full, qr, 0.0)) / n - luma_b ** 2, 0.0))
    flat = (numpy.minimum(sd_a, sd_b)
            < FLAT_RATIO * numpy.maximum(sd_a, sd_b))
    usable = ((rows >= BAND / 2) & (numpy.minimum(luma_a, luma_b) >= WATER_LUMA)
              & ~flat)
    return c, mean_b - mean_a, mean_a, mean_b, usable


def _candidates(step: numpy.ndarray, usable: numpy.ndarray) -> List[list]:
    """Per band, the column indices of local maxima (3 px each way) of the
    step's size at least :data:`MIN_STEP`."""
    size = numpy.where(usable, numpy.linalg.norm(step, axis=-1), 0.0)
    out = []
    for row in size:
        padded = numpy.pad(row, 3)
        peak = numpy.ones(row.shape, dtype=bool)
        for k in range(1, 4):
            peak &= (row >= padded[3 - k:3 - k + len(row)]) & (
                row >= padded[3 + k:3 + k + len(row)])
        out.append([int(j) for j in numpy.nonzero(peak & (row >= MIN_STEP))[0]])
    return out


def _unit(v: numpy.ndarray) -> numpy.ndarray:
    return v / max(float(numpy.linalg.norm(v)), 1e-9)


def _extend(chain: dict, step, size, free, b: int, j: int, direction: int) -> None:
    """Grow ``chain`` from band ``b`` (column index ``j``) one way."""
    heading, miss = _unit(step[b, j]), 0
    while miss <= MAX_MISS:
        b += direction
        if not 0 <= b < len(free):
            return
        near = [k for k in free[b] if abs(k - j) <= JOG
                and float(_unit(step[b, k]) @ heading) >= MIN_COS]
        if not near:
            miss += 1
            continue
        strong = max(size[b, k] for k in near)
        k = min((k for k in near if size[b, k] >= 0.5 * strong),
                key=lambda k: abs(k - j))
        chain[b], j, miss = k, k, 0
        free[b].discard(k)
        heading = _unit(heading * 3.0 + _unit(step[b, k]))


def _chains(step: numpy.ndarray, cands: List[list]) -> List[dict]:
    """Chains of candidates band after band (module docstring), strongest
    seed first; each ``{band: column index}``."""
    size = numpy.linalg.norm(step, axis=-1)
    free = [set(row) for row in cands]
    seeds = sorted(((size[b, j], b, j) for b, row in enumerate(cands)
                    for j in row), reverse=True)
    chains = []
    for _, b0, j0 in seeds:
        if j0 not in free[b0]:
            continue
        chain = {b0: j0}
        free[b0].discard(j0)
        for direction in (1, -1):
            _extend(chain, step, size, free, b0, j0, direction)
        chains.append(chain)
    return chains


def _straight(chain: dict, size: numpy.ndarray) -> bool:
    """A chain is a seam (module docstring): long, covered, still, strong."""
    bands = sorted(chain)
    if len(bands) < MIN_BANDS:
        return False
    if len(bands) < MIN_COVER * (bands[-1] - bands[0] + 1):
        return False
    jogs = numpy.array([abs(chain[b] - chain[a])
                        for a, b in zip(bands, bands[1:], strict=False)])
    if float((jogs <= STILL).mean()) < MIN_STILL:
        return False
    return float(numpy.median([size[b, chain[b]] for b in bands])) >= MIN_SEAM_STEP


def _far_ratio(far, c, chain: dict, step) -> float:
    """The median over a chain's bands of the far strips' step (``far``:
    :func:`_strips` of :data:`FAR` px beyond the near ones) along the near
    step, as a share of the near step."""
    cf, sl, sr, _, _, full = far
    ratios = []
    for b in sorted(chain):
        j = int(numpy.searchsorted(cf, c[chain[b]]))
        if j >= len(cf) or cf[j] != c[chain[b]]:
            continue
        rows = slice(b * BAND, (b + 1) * BAND)
        keep = full[rows, j]
        if keep.sum() < BAND / 2:
            continue
        far = (sr[rows, j][keep] - sl[rows, j][keep]).mean(axis=0) / FAR
        near = step[b, chain[b]]
        ratios.append(float(far @ near) / max(float(near @ near), 1e-9))
    return float(numpy.median(ratios)) if ratios else 0.0


def _joins(last: dict, chain: dict, step) -> bool:
    """``chain`` carries ``last`` on: it starts within :data:`MAX_MISS`
    bands of ``last``'s end, its first band beyond that end within
    :data:`JOG` px of it, stepping the same way."""
    end, start = max(last), min(chain)
    after = min((b for b in chain if b > end), default=None)
    return (after is not None and start <= end + MAX_MISS + 1
            and abs(last[end] - chain[after]) <= JOG
            and float(_unit(step[end, last[end]])
                      @ _unit(step[after, chain[after]])) >= MIN_COS)


def _merge(chains: List[dict], step) -> List[dict]:
    """Seams that meet end to end (:func:`_joins`) as one, the earlier's
    bands kept where they overlap."""
    out: List[dict] = []
    for chain in sorted(chains, key=min):
        last = next((o for o in out if _joins(o, chain, step)), None)
        if last is None:
            out.append(dict(chain))
            continue
        end = max(last)
        last.update({b: j for b, j in chain.items() if b > end})
    return out


def _median(values: numpy.ndarray, width: int) -> numpy.ndarray:
    """A running median of ``width`` (odd) along axis 0, edges held."""
    if len(values) < width:
        return values
    pad = width // 2
    padded = numpy.pad(values, ((pad, pad),) + ((0, 0),) * (values.ndim - 1),
                       mode="edge")
    return numpy.median(numpy.stack([padded[k:k + len(values)]
                                     for k in range(width)]), axis=0)


def _rows(fine, c, chain: dict, step) -> numpy.ndarray:
    """Row by row along a chain, the boundary (mosaic px; NaN where none
    steps 0.4 of its band's step) near its band's and its neighbours'
    that steps most along the band's step (``fine``: :func:`_strips` with
    2-px strips)."""
    cc, sl, sr, _, _, full = fine
    bands = sorted(chain)
    out = []
    for b in range(bands[0], bands[-1] + 1):
        cols = [c[chain[a]] for a in bands if abs(a - b) <= 1]
        nearest = min(bands, key=lambda a: abs(a - b))
        heading = _unit(step[nearest, chain[nearest]])
        need = 0.4 * float(numpy.linalg.norm(step[nearest, chain[nearest]]))
        lo = int(numpy.searchsorted(cc, min(cols or [c[chain[nearest]]]) - 2))
        hi = int(numpy.searchsorted(cc, max(cols or [c[chain[nearest]]]) + 2,
                                    side="right"))
        for r in range(b * BAND, (b + 1) * BAND):
            pick = numpy.nan
            if hi > lo:
                score = ((sr[r, lo:hi] - sl[r, lo:hi]) / 2.0) @ heading
                score = numpy.where(full[r, lo:hi], score, -numpy.inf)
                if score.max() >= need:
                    pick = float(cc[lo + int(numpy.argmax(score))])
            out.append(pick)
    return numpy.array(out)


def _drawn(rows: numpy.ndarray) -> bool:
    """A cutline is drawn straight: at least :data:`MIN_TRUE` of the rows
    lie within 1 px of the median of the 15 rows around them (a mountain
    front or a shore follows the ground, row by row)."""
    found = numpy.isfinite(rows)
    if found.mean() < 0.5:
        return False
    near = numpy.array([numpy.median(window) if len(window) else numpy.nan
                        for window in (rows[max(0, i - 7):i + 8][
                            found[max(0, i - 7):i + 8]]
                            for i in range(len(rows)))])
    off = numpy.abs(rows[found] - near[found])
    return float((off <= 1.0).mean()) >= MIN_TRUE


def _line(rows: numpy.ndarray, c, chain: dict) -> List[Tuple[float, float]]:
    """``(row, boundary)`` row by row along a chain, in mosaic px: the
    rows' boundaries (:func:`_rows`; a row without one on the line through
    the bands), a 5-row median of them."""
    bands = sorted(chain)
    first = bands[0] * BAND
    at = numpy.arange(first, first + len(rows))
    through = numpy.interp(at / BAND - 0.5, bands, [c[chain[b]] for b in bands])
    across = numpy.where(numpy.isfinite(rows), rows, through)
    return list(zip((at + 0.5).tolist(), _median(across, 5).tolist(), strict=True))


def _knots(chain: dict, mean_a, mean_b) -> List[Tuple[float, RGB, RGB]]:
    """``(row, offset_a, offset_b)`` band by band: each side halfway to the
    other (a 3-band median, clipped to half ``CAST.MAX_CAST``)."""
    bands = sorted(chain)
    half = numpy.array([(mean_b[b, chain[b]] - mean_a[b, chain[b]]) / 2.0
                        for b in bands])
    half = numpy.clip(_median(half, 3), -CAST.MAX_CAST / 2.0,
                      CAST.MAX_CAST / 2.0)
    return [((b + 0.5) * BAND, tuple(float(v) for v in h),
             tuple(float(-v) for v in h)) for b, h in zip(bands, half, strict=True)]


def _chains_of(mosaic: numpy.ndarray) -> Tuple[list, tuple]:
    """The chains of ``mosaic`` that look like seams running down its
    columns (every test but the reference's), with their rows
    (:func:`_rows`), and the bands they were found in (:func:`_bands`)."""
    bands = _bands(mosaic)
    c, step, _, _, usable = bands
    size = numpy.linalg.norm(step, axis=-1)
    ok = _valid(mosaic)
    far = _strips(mosaic, ok, 2 * (GAP // 2 + STRIP + FAR), FAR)
    fine = None
    out = []
    for chain in _merge([chain for chain in _chains(step, _candidates(step, usable))
                         if _straight(chain, size)
                         and _far_ratio(far, c, chain, step) >= MIN_FAR], step):
        if fine is None:
            fine = _strips(mosaic, ok, 2, 2)
        rows = _rows(fine, c, chain, step)
        if _drawn(rows):
            out.append((chain, rows))
    return out, bands


def _squares_of(chain: dict, c, square: int) -> set:
    """``(row, column)`` of the mosaic squares (``square`` px) a chain's
    strips lie in, in the chain's own (maybe transposed) frame."""
    out = set()
    reach = GAP // 2 + STRIP + 1
    for b, j in chain.items():
        for r in {b * BAND // square, ((b + 1) * BAND - 1) // square}:
            for col in {(c[j] - reach) // square, (c[j] + reach) // square}:
                out.add((int(r), int(col)))
    return out


def _seen_elsewhere(chain: dict, step, ref_bands) -> bool:
    """The reference provider shows the same step on the same line (the
    median over the bands it covers of its step along ours, as a share of
    ours, at least :data:`MAX_REF`) -- the ground's own edge, which every
    photo shows -- or covers too few bands to tell (half the chain)."""
    _, ref_step, _, _, ref_usable = ref_bands
    shares = []
    for b, j in chain.items():
        if not ref_usable[b, j]:
            continue
        ours = step[b, j]
        shares.append(float(ref_step[b, j] @ ours) / max(float(ours @ ours), 1e-9))
    if len(shares) < len(chain) / 2:
        return True
    return float(numpy.median(shares)) >= MAX_REF


def _seam(axis: str, chain: dict, rows, bands, a0, c0, px_per_tile, last) -> Seam:
    c, _, mean_a, mean_b, _ = bands
    order = sorted(chain)
    return Seam(
        axis,
        tuple((a0 + a / px_per_tile, c0 + x / px_per_tile)
              for a, x in _line(rows, c, chain)),
        tuple((a0 + a / px_per_tile, oa, ob)
              for a, oa, ob in _knots(chain, mean_a, mean_b)),
        order[0] <= MAX_MISS, order[-1] >= last - MAX_MISS)


def find_seams(mosaic: numpy.ndarray, x0: int, y0: int,
               reference: Optional[Callable[[int, int], Optional[numpy.ndarray]]]
               ) -> Optional[List[Seam]]:
    """The capture seams of ``mosaic`` (:func:`mosaic_of`: ``(h, w, 3)``,
    NaN where no photo, :data:`SAMPLE` px per ZL16 square, the north-west
    square at map tile (``x0``, ``y0``)).  ``reference(til_x, til_y)`` is
    another provider's photo of a square (any size, or None): a line is a
    seam only where that photo does not step the same way (a ground edge
    every photo shows is never one); without it no line is.  None when
    lines were found but no reference photo of them could be had (offline:
    nothing is known)."""
    if reference is None:
        return []
    mosaic = numpy.asarray(mosaic, dtype=numpy.float64)
    frames = (("V", mosaic, y0, x0, False),
              ("H", mosaic.transpose(1, 0, 2), x0, y0, True))
    found = [(frame, *_chains_of(frame[1])) for frame in frames]
    wanted = set()
    for (_, _, _, _, flip), chains, bands in found:
        for chain, _ in chains:
            for r, col in _squares_of(chain, bands[0], SAMPLE):
                wanted.add((col, r) if flip else (r, col))
    if not wanted:
        return []
    ref = numpy.full(mosaic.shape, numpy.nan)
    rows, cols = mosaic.shape[0] // SAMPLE, mosaic.shape[1] // SAMPLE
    got = 0
    for i, j in wanted:
        if not (0 <= i < rows and 0 <= j < cols):
            continue
        image = reference(x0 + 16 * j, y0 + 16 * i)
        if image is not None:
            ref[i * SAMPLE:(i + 1) * SAMPLE, j * SAMPLE:(j + 1) * SAMPLE] = _sampled(image)
            got += 1
    if not got:
        return None
    seams = []
    for (axis, _image, a0, c0, flip), chains, bands in found:
        if not chains:
            continue
        ref_bands = _bands(ref.transpose(1, 0, 2) if flip else ref)
        step = bands[1]
        kept = [(chain, rows) for chain, rows in _unpaired(chains, bands)
                if not _seen_elsewhere(chain, step, ref_bands)]
        seams += [_seam(axis, chain, rows, bands, a0, c0, SAMPLE / 16.0,
                        step.shape[0] - 1) for chain, rows in kept]
    return seams


def _unpaired(chains: list, bands) -> list:
    """``chains`` without the pairs that step opposite ways within
    :data:`PAIR` px of each other along shared bands: the two sides of a
    road, a canal or a fence, which a seam is not."""
    c, step = bands[0], bands[1]
    paired = set()
    for i, (one, _) in enumerate(chains):
        for k, (two, _) in enumerate(chains[:i]):
            shared = [b for b in one if b in two]
            if not shared:
                continue
            apart = numpy.median([abs(c[one[b]] - c[two[b]]) for b in shared])
            turn = numpy.median([float(_unit(step[b, one[b]])
                                       @ _unit(step[b, two[b]])) for b in shared])
            if apart <= PAIR and turn <= -0.5:
                paired.update((i, k))
    return [chain for i, chain in enumerate(chains) if i not in paired]


def _sampled(image) -> numpy.ndarray:
    """An RGB photo of a square reduced to :data:`SAMPLE` px."""
    from PIL import Image
    image = numpy.asarray(image)[..., :3]
    if image.shape[:2] != (SAMPLE, SAMPLE):
        image = numpy.asarray(Image.fromarray(image.astype(numpy.uint8))
                              .resize((SAMPLE, SAMPLE), Image.BOX))
    return image


def mosaic_of(lat: int, lon: int, provider: str,
              image_of: Callable[[str, int, int], Optional[numpy.ndarray]]
              ) -> Tuple[numpy.ndarray, int, int]:
    """Tile (``lat``, ``lon``)'s ZL16 squares from ``provider``
    (``image_of(provider, til_x, til_y)``, an RGB array of any size,
    reduced to :data:`SAMPLE` px) side by side: ``(mosaic, x0, y0)``, the
    north-west square's map-tile corner."""
    import O4_World_Drape as DRAPE
    squares = DRAPE.texture_squares(lat, lon, SEAM_ZL)
    xs = sorted({x for x, _ in squares})
    ys = sorted({y for _, y in squares})
    out = numpy.full((len(ys) * SAMPLE, len(xs) * SAMPLE, 3), numpy.nan,
                     dtype=numpy.float32)
    for til_x, til_y in squares:
        image = image_of(provider, til_x, til_y)
        if image is None:
            continue
        i, j = ys.index(til_y), xs.index(til_x)
        out[i * SAMPLE:(i + 1) * SAMPLE, j * SAMPLE:(j + 1) * SAMPLE] = _sampled(image)
    return out, xs[0], ys[0]


# --- the field -------------------------------------------------------------

def _metres_per_tile(y: numpy.ndarray) -> numpy.ndarray:
    """Ground metres per ZL16 map tile at map-tile row ``y``."""
    half = 2.0 ** (SEAM_ZL - 1)
    lat = numpy.arctan(numpy.sinh(math.pi * (1.0 - y / half)))
    return _EARTH_M * numpy.cos(lat) / 2.0 ** SEAM_ZL


def _weight(seam: Seam, along, dx, metres) -> numpy.ndarray:
    """How much of a seam's move applies: 1 within the ramp, falling to 0
    at :data:`FEATHER_M` beyond it, faded in from a closed end."""
    lo, hi = seam.line[0][0], seam.line[-1][0]
    reach = numpy.clip(1.0 - (numpy.abs(dx) - RAMP_M / 2.0) / FEATHER_M,
                       0.0, 1.0)
    fade = numpy.ones(numpy.shape(dx))
    if not seam.open_start:
        fade = numpy.minimum(fade, (along - lo) * metres / END_M)
    if not seam.open_end:
        fade = numpy.minimum(fade, (hi - along) * metres / END_M)
    inside = (along >= lo) & (along <= hi)
    return numpy.where(inside, reach * numpy.clip(fade, 0.0, 1.0), 0.0)


@dataclass
class SeamField:
    """The correction of a tile's :class:`Seam` s (module docstring)."""

    seams: List[Seam] = field(default_factory=list)

    def at(self, x, y) -> numpy.ndarray:
        """The RGB offset at ZL16 map-tile points (``x``, ``y``, arrays
        that broadcast): ``(..., 3)``."""
        x, y = numpy.broadcast_arrays(numpy.asarray(x, dtype=numpy.float64),
                                      numpy.asarray(y, dtype=numpy.float64))
        out = numpy.zeros(x.shape + (3,))
        metres = _metres_per_tile(y)
        for seam in self.seams:
            along, across = (y, x) if seam.axis == "V" else (x, y)
            line = numpy.array(seam.line)
            dx = (across - numpy.interp(along, line[:, 0], line[:, 1])) * metres
            weight = _weight(seam, along, dx, metres)
            if not weight.any():
                continue
            side_b = numpy.clip(0.5 + dx / RAMP_M, 0.0, 1.0)
            at = [k[0] for k in seam.knots]
            for ch in range(3):
                oa = numpy.interp(along, at, [k[1][ch] for k in seam.knots])
                ob = numpy.interp(along, at, [k[2][ch] for k in seam.knots])
                out[..., ch] += weight * (oa * (1.0 - side_b) + ob * side_b)
        return out

    def fields(self, til_x: int, til_y: int, zoomlevel: int,
               size: int = FIELD_SIZE
               ) -> Optional[Tuple[numpy.ndarray, None]]:
        """``(offset, None)`` over texture square (``til_x``, ``til_y``)
        at ``zoomlevel``, at its pixel centres (``Blend.fields``' shape,
        no slope); None when it moves no pixel by half a count."""
        if not self.seams:
            return None
        scale = 2.0 ** (zoomlevel - SEAM_ZL)
        u = (numpy.arange(size, dtype=numpy.float64) + 0.5) / size * 16.0
        offset = self.at(((til_x + u) / scale)[None, :],
                         ((til_y + u) / scale)[:, None]).astype(numpy.float32)
        if not numpy.rint(offset).any():
            return None
        return numpy.ascontiguousarray(offset), None


# --- the book --------------------------------------------------------------

class SeamBook(CAST.JsonBook):
    """The seams found, by tile and provider (module docstring)."""

    @staticmethod
    def key(lat: int, lon: int, provider: str) -> str:
        return f"{lat:+03d}{lon:+04d}:{provider}:{SEAM_ZL}:{SAMPLE}:{_RULES}"

    def seams(self, lat: int, lon: int, provider: str,
              image_of: Optional[Callable] = None) -> Optional[List[Seam]]:
        """The book's seams of the tile, else found now with ``image_of``
        (:func:`mosaic_of`'s) and written -- unless half the tile's photos
        or every reference photo could not be had (none, not written);
        None when the book has none and no ``image_of`` is given."""
        key = self.key(lat, lon, provider)
        known = self.get(key)
        if known is not None:
            try:
                return [Seam.from_dict(s) for s in known]
            except (KeyError, TypeError, ValueError, IndexError):
                pass                    # unreadable: found again
        if image_of is None:
            return None
        mosaic, x0, y0 = mosaic_of(lat, lon, provider, image_of)
        if numpy.isfinite(mosaic).all(axis=-1).mean() < 0.5:
            return []                   # offline: found again next time
        other = reference_provider(provider)
        found = find_seams(mosaic, x0, y0,
                           lambda til_x, til_y: image_of(other, til_x, til_y))
        if found is None:
            return []                   # no reference: found again next time
        self.put(key, [s.as_dict() for s in found])
        return found


_BOOK: dict = {}
_LOCKS: dict = {}
_LOCKS_LOCK = threading.Lock()


def book() -> SeamBook:
    """The data folder's book (``World_build/capture_seams.json``)."""
    import O4_File_Names as FNAMES
    path = os.path.join(FNAMES.data_path("World_build"), _BOOK_NAME)
    return _BOOK.setdefault(path, SeamBook(path))


def reference_provider(provider: str) -> str:
    """The provider a seam of ``provider`` is checked against: one with
    world cover that is not it."""
    return REFERENCES[1] if provider.startswith(REFERENCES[0]) else REFERENCES[0]


def _fetcher(lat: int, lon: int) -> Callable:
    """``image_of`` for :meth:`SeamBook.seams` (``CAST.fetch_square``, the
    tile's imagery cache): the first provider asked for has every square
    of the tile fetched at once, on 8 threads; another, square by
    square."""
    from concurrent.futures import ThreadPoolExecutor
    got: dict = {}

    def image_of(provider, til_x, til_y):
        if not got:
            import O4_World_Drape as DRAPE
            squares = DRAPE.texture_squares(lat, lon, SEAM_ZL)
            with ThreadPoolExecutor(8) as pool:
                images = pool.map(
                    lambda sq: CAST.fetch_square(provider, *sq, (lat, lon)),
                    squares)
                got[provider] = dict(zip(squares, images, strict=True))
        if provider in got:
            return got[provider].get((til_x, til_y))
        return CAST.fetch_square(provider, til_x, til_y, (lat, lon))
    return image_of


def attach(tile, provider_code: str, measure: bool = True) -> None:
    """Give ``tile`` the :class:`SeamField` of its seams from
    ``provider_code`` (``tile.capture_seams``), once per tile and
    provider: the book's, else found now when ``measure`` (a build's
    conversion; a follow-job tier only reads the book).  Any failure
    leaves the tile without one."""
    if getattr(tile, "capture_seams_of", None) == provider_code:
        return
    key = (int(tile.lat), int(tile.lon), provider_code)
    with _LOCKS_LOCK:
        lock = _LOCKS.setdefault(key, threading.Lock())
    with lock:              # one finding per tile; other tiles go on
        if getattr(tile, "capture_seams_of", None) == provider_code:
            return
        try:
            seams = book().seams(int(tile.lat), int(tile.lon), provider_code,
                                 _fetcher(int(tile.lat), int(tile.lon))
                                 if measure else None)
        except Exception:               # a correction, never a failed build
            seams = None
        tile.capture_seams = SeamField(list(seams)) if seams else None
        tile.capture_seams_of = provider_code
