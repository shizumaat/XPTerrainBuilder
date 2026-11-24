"""Straight axis-aligned colour steps in a texture: the lines a photo
provider's mosaic draws (owner 2026-11-24, tile +24-082).

On a working copy of a texture (``O4_Imagery_Water_Seams.WORK`` px), the
colour step across every vertical line -- the horizontal ones are the
same on the transpose -- in EXCESS of the slope either side, averaged
along the line over :data:`LINE_M` metres (:func:`vertical_lines`).  A point is
STRONG where that step, times the mask's opacity, reaches :data:`MIN_STEP`
with :data:`COHERENCE`, is the strongest across the line and lies in
water; WEAK at :data:`WEAK_STEP` / :data:`WEAK_COHERENCE`.
:func:`straight_pairs` keeps the strong points on a straight run long
alone (:data:`MIN_RUN_M`) or turning a square corner
(:data:`MIN_CORNER_RUN_M`), and drops a THING: a run stepping harder than
:data:`MAX_RUN_STEP`, or with an opposite twin beside it (a pier, a slip,
a boat, a seawall, a dredged channel).  :func:`grown` lets a run grow
along its own line through weak points (hysteresis).

Pure leaf: numpy and scipy.  No tile or airport is named here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy
from scipy import ndimage

__all__ = [
    "grown",
    "run_lengths",
    "scale_for",
    "straight_pairs",
    "vertical_lines",
]

# Strip width (work px) each side of a line, and the lines beside it whose
# step is the slope expected there (two strips away each side).
STRIP = 2
# The step is averaged along the line over this many metres: a straight
# edge keeps its step, a ground edge crossing the line at an angle, or the
# ground's own texture, averages out.  Every length below is GROUND
# metres (a ZL19 texture resolves piers, slips and boats that a ZL16 one
# blurs away), turned into work px by :func:`scale_for`.
LINE_M = 140.0
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
# ... and it belongs to a straight run at least this long (metres) -- or
# this long where it turns a square corner with a perpendicular run within
# CORNER_GAP px (a source tile's side; the finest such tile in a texture
# is ~140 m at ZL16).
MIN_RUN_M = 490.0
MIN_CORNER_RUN_M = 210.0
CORNER_GAP = 3
CORNER_COSINE = 0.8
# A run whose mean step exceeds this (counts) is a thing, not a seam ...
MAX_RUN_STEP = 60.0
# ... and so is one with an opposite twin this close (metres): a pier, a
# slip, a boat (any run), a channel or causeway (a lone run).
PAIR_GAP_M = 140.0
LONE_PAIR_GAP_M = 830.0
# A run grows along its line through points that step at least this much
# (visible counts) with this coherence: a scene edge keeps its line while
# the ground on either side changes how much it steps.
WEAK_STEP = 4.0
WEAK_COHERENCE = 0.4
# Rec. 601 luminance (a step's brightness part).
_LUMA = numpy.array([0.299, 0.587, 0.114], dtype=numpy.float32)

_VERTICAL = numpy.array([[0, 1, 0], [0, 1, 0], [0, 1, 0]], dtype=bool)


@dataclass(frozen=True)
class _Scale:
    """The metric lengths above in work px of one texture."""

    line: int
    min_run: int
    min_corner_run: int
    pair_gap: int
    lone_pair_gap: int


def scale_for(work_px_m: float) -> _Scale:
    """:class:`_Scale` for a work px of ``work_px_m`` ground metres."""
    def px(metres, least):
        return max(least, int(round(metres / float(work_px_m))))

    return _Scale(line=px(LINE_M, 8), min_run=px(MIN_RUN_M, 28),
                 min_corner_run=px(MIN_CORNER_RUN_M, 12),
                 pair_gap=px(PAIR_GAP_M, 4),
                 lone_pair_gap=px(LONE_PAIR_GAP_M, 16))
# A reported run continues to the next row one column either side.
_DRIFT = numpy.array([[1, 1, 1], [0, 1, 0], [1, 1, 1]], dtype=bool)


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


def vertical_lines(a: numpy.ndarray, w: numpy.ndarray, opacity: numpy.ndarray,
                   scale: _Scale, grey: Optional[numpy.ndarray] = None):
    """``(evidence, strong, weak)`` of the vertical lines of ``a``: the
    averaged excess step (see ``O4_Imagery_Water_Seams``) and the points passing
    the strong and the weak test; the horizontal ones are this on the
    transpose.  Where ``grey`` is set the step is its luminance only."""
    s = STRIP
    after = sum(_shift(a, k) for k in range(s)) / s
    before = sum(_shift(a, -1 - k) for k in range(s)) / s
    step = after - before
    excess = step - 0.5 * (_shift(step, -2 * s) + _shift(step, 2 * s))
    if grey is not None:  # brightness only: (l, l, l), l the luminance step
        excess[grey] = (excess[grey] @ _LUMA)[:, None]
    evidence = ndimage.uniform_filter1d(excess, scale.line, axis=0,
                                        mode="nearest")
    spread = ndimage.uniform_filter1d(numpy.linalg.norm(excess, axis=-1),
                                      scale.line, axis=0, mode="nearest")
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


def straight_pairs(strong_x: numpy.ndarray, strong_y: numpy.ndarray,
                   evidence_x: numpy.ndarray, evidence_y: numpy.ndarray,
                   scale: _Scale):
    """The strong points of each orientation on a run long enough ALONE
    (:data:`MIN_RUN_M`), or long enough to be a square's side
    (:data:`MIN_CORNER_RUN_M`) and meeting a perpendicular one at a corner:
    a source tile's edges are straight AND turn square, a channel bank that
    is straight for a while does neither for long."""
    labels_x, runs_x = _runs(strong_x)
    labels_y, runs_y = _runs(strong_y.T)
    length_x = runs_x[:, 2] - runs_x[:, 1]
    length_y = runs_y[:, 2] - runs_y[:, 1]
    side_x = length_x >= scale.min_corner_run
    side_y = length_y >= scale.min_corner_run
    side_x[0] = side_y[0] = False
    keep_x = length_x >= scale.min_run
    keep_y = length_y >= scale.min_run
    steps_x = _mean_steps(evidence_x, strong_x, labels_x, len(runs_x) - 1)
    steps_y = _mean_steps(evidence_y.transpose(1, 0, 2), strong_y.T,
                          labels_y, len(runs_y) - 1)
    # a run stepping harder than any acquisition seam is a thing: a pier,
    # a boat, a seawall, a dredged channel's bank
    side_x &= numpy.linalg.norm(steps_x, axis=1) <= MAX_RUN_STEP
    side_y &= numpy.linalg.norm(steps_y, axis=1) <= MAX_RUN_STEP
    keep_x &= side_x
    keep_y &= side_y
    # a lone run with the opposite step beside it is the other bank of a
    # channel or a causeway (a scene seam has no twin)
    keep_x &= ~_twinned(runs_x, steps_x, scale.lone_pair_gap)
    keep_y &= ~_twinned(runs_y, steps_y, scale.lone_pair_gap)
    keep_x[side_x] |= _touching(runs_x[side_x], runs_y[side_y],
                                steps_x[side_x], steps_y[side_y])
    keep_y[side_y] |= _touching(runs_y[side_y], runs_x[side_x],
                                steps_y[side_y], steps_x[side_x])
    # and any run with its twin close by is a thin thing: a pier, a slip
    keep_x &= ~_twinned(runs_x, steps_x, scale.pair_gap)
    keep_y &= ~_twinned(runs_y, steps_y, scale.pair_gap)
    keep_x[0] = keep_y[0] = False
    return strong_x & keep_x[labels_x], strong_y & keep_y[labels_y].T


def _twinned(runs: numpy.ndarray, steps: numpy.ndarray, gap: int) -> numpy.ndarray:
    """Per run (``[column, row0, row1]``), whether another run 2 to ``gap``
    columns away runs beside it for half the longer one's rows stepping
    the OPPOSITE way (|cosine| :data:`CORNER_COSINE`): the two sides of
    one narrow thing (a square's side beside a long seam is no twin)."""
    if len(runs) < 2:
        return numpy.zeros(len(runs), dtype=bool)
    c, r0, r1 = (runs[:, k] for k in range(3))
    apart = numpy.abs(c[:, None] - c[None, :])
    overlap = (numpy.minimum(r1[:, None], r1[None, :])
               - numpy.maximum(r0[:, None], r0[None, :]))
    longer = numpy.maximum((r1 - r0)[:, None], (r1 - r0)[None, :])
    unit = steps / numpy.maximum(numpy.linalg.norm(steps, axis=1), 1e-6)[:, None]
    opposite = (unit @ unit.T) <= -CORNER_COSINE
    twin = ((apart >= 2) & (apart <= gap) & (overlap * 2 >= longer)
            & opposite)
    twin[0, :] = twin[:, 0] = False
    return twin.any(axis=1)


def grown(strong: numpy.ndarray, weak: numpy.ndarray) -> numpy.ndarray:
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


def run_lengths(flags: numpy.ndarray) -> List[int]:
    """Lengths (rows) of every straight vertical run of ``flags`` (one
    column either side from row to row)."""
    labels, _count = ndimage.label(flags, structure=_DRIFT)
    return [box[0].stop - box[0].start for box in ndimage.find_objects(labels)]
