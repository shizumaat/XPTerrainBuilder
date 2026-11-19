"""THE CUT UNDER A GENERATED DECK, AS NUMBERS (owner RULINGS 2026-11-19s
(2)-(4); owner 2026-11-19T23:07Z / 23:09Z: "if we insert a bridge, we need
the cut, and the cut needs to grade smoothly away from the bridge back to
the natural terrain").

Pure numpy: the planar stage (``planar/deck_carve``, where the cut's cells
are minted) and stage 2 (``constraints/deck_carve``, where its vertices are
levelled) read ONE definition.

* :class:`PathFrame` -- a polyline's arclength frame: each point's station
  ``s`` and distance ``n`` off the line.
* :func:`floor_profile` -- the cut's FLOOR along its path: level at each
  deck's floor over the stretch under that deck (``z <= zf``), straight
  through the gap between two decks, then ramping back out of both ends at
  the grade cap until it meets the terrain along the path, with vertical
  curves (``O4_Road_Grade._smooth_grade_changes``: the profile closest to
  that target holding the cap and the grade-change rate).  The floor never
  stands more than ``fill_tol`` over the terrain past the decks.
* :func:`lateral` -- the cut across its path: the floor over ``half``
  either side of the line, then the bank at ``bank`` (rise/run).
* :func:`ramp_lengths` -- how far each ramp runs before it meets the
  terrain (``inf`` when the path ends first: the shortfall).

Nothing here names an airport.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from .exact import hypot_array, sq

__all__ = ["PathFrame", "floor_profile", "lateral", "ramp_lengths", "smoothed"]

XY = tuple[float, float]


class PathFrame:
    """The arclength frame of the polyline ``coords`` (module doc)."""

    def __init__(self, coords: _t.Sequence[XY]) -> None:
        p = np.asarray(coords, dtype=np.float64)
        self.a = p[:-1]
        self.d = p[1:] - p[:-1]
        self.len = hypot_array(self.d[:, 0], self.d[:, 1])
        self.s0 = np.concatenate(([0.0], np.cumsum(self.len)[:-1]))
        self.length = float(self.len.sum())

    def project(self, xs, ys) -> tuple[np.ndarray, np.ndarray]:
        """``(s, n)`` of every point: its station along the path and its
        distance off it (both ``np.ndarray``)."""
        x = np.asarray(xs, dtype=np.float64)[:, None]
        y = np.asarray(ys, dtype=np.float64)[:, None]
        l2 = np.maximum(sq(self.len), 1e-12)
        t = ((x - self.a[:, 0]) * self.d[:, 0] + (y - self.a[:, 1]) * self.d[:, 1]) / l2
        t = np.clip(t, 0.0, 1.0)
        px = self.a[:, 0] + t * self.d[:, 0]
        py = self.a[:, 1] + t * self.d[:, 1]
        dist = hypot_array(x - px, y - py)
        k = np.argmin(dist, axis=1)
        rows = np.arange(len(k))
        return self.s0[k] + t[rows, k] * self.len[k], dist[rows, k]

    def at(self, s: float) -> tuple[XY, XY]:
        """``(point, unit tangent)`` at station ``s`` (clamped)."""
        s = min(max(s, 0.0), self.length)
        k = int(np.clip(np.searchsorted(self.s0, s, side="right") - 1, 0, len(self.len) - 1))
        ln = max(float(self.len[k]), 1e-12)
        f = (s - self.s0[k]) / ln
        u = (float(self.d[k, 0] / ln), float(self.d[k, 1] / ln))
        return (float(self.a[k, 0] + f * self.d[k, 0]), float(self.a[k, 1] + f * self.d[k, 1])), u


def smoothed(z: _t.Sequence[float], k: int = 2) -> np.ndarray:
    """A running median over ``2k + 1`` samples (a lidar road's noise)."""
    a = np.asarray(z, dtype=np.float64)
    if len(a) <= 2 * k:
        return a.copy()
    pad = np.pad(a, k, mode="edge")
    return np.median(np.lib.stride_tricks.sliding_window_view(pad, 2 * k + 1), axis=1)


def _design(s: np.ndarray, stretches: _t.Sequence[tuple[float, float, float]],
            cap: float) -> tuple[np.ndarray, np.ndarray]:
    """``(design, inside)``: each deck's floor over its stretch, straight
    between two stretches, ``cap`` outward past the outermost; ``inside``
    marks the stations under a deck."""
    st = sorted(stretches)
    d = np.full(len(s), np.inf)
    inside = np.zeros(len(s), dtype=bool)
    for s0, s1, zf in st:
        m = (s >= s0) & (s <= s1)
        d[m] = np.minimum(d[m], zf)
        inside |= m
    for (_a0, a1, za), (b0, _b1, zb) in zip(st, st[1:], strict=False):
        if b0 > a1:
            m = (s > a1) & (s < b0)
            d[m] = np.minimum(d[m], za + (zb - za) * (s[m] - a1) / (b0 - a1))
    lo, hi = st[0], st[-1]
    m = s < lo[0]
    d[m] = np.minimum(d[m], lo[2] + cap * (lo[0] - s[m]))
    m = s > hi[1]
    d[m] = np.minimum(d[m], hi[2] + cap * (s[m] - hi[1]))
    return d, inside


def floor_profile(s: _t.Sequence[float], terrain: _t.Sequence[float],
                  stretches: _t.Sequence[tuple[float, float, float]], cap: float,
                  rate: float, fill_tol: float = 0.3) -> np.ndarray:
    """The floor at stations ``s`` (module doc).  ``terrain``: the ground
    along the path there; ``stretches``: ``(s0, s1, floor)`` under each
    deck; ``cap``: the grade cap; ``rate``: the vertical curve's grade
    change per metre."""
    s = np.asarray(s, dtype=np.float64)
    r = np.asarray(terrain, dtype=np.float64)
    if len(s) < 2 or not stretches:
        return r.copy()
    design, inside = _design(s, stretches, cap)
    target = np.minimum(design, r)
    upper = np.maximum(r + fill_tol, design)
    upper[inside] = design[inside]
    target[inside] = design[inside]
    # the floor under a deck is the rule's, level: the curves stand outside
    lower = np.where(inside, design, -np.inf)
    try:
        from O4_Road_Grade import _smooth_grade_changes
        got = _smooth_grade_changes(s, target, cap, rate, lower=lower, upper=upper)
    except Exception:          # noqa: BLE001 -- the LP refines; the capped target stands
        got = None
    return np.minimum(target, upper) if got is None else np.minimum(got, upper)


def lateral(floor_z, n, half: float, bank: float):
    """The cut at distance ``n`` off its path over a floor at ``floor_z``:
    level over ``half``, then the bank at ``bank`` (rise per run)."""
    return np.asarray(floor_z, dtype=np.float64) + bank * np.maximum(
        0.0, np.asarray(n, dtype=np.float64) - half)


def ramp_lengths(s, z, terrain, stretches, tol: float = 0.05) -> tuple[float, float]:
    """``(before, after)``: how far the floor runs from the first / last
    stretch before it stands within ``tol`` of the terrain; ``inf`` when the
    path ends first."""
    s = np.asarray(s, dtype=np.float64)
    met = np.asarray(z, dtype=np.float64) >= np.asarray(terrain, dtype=np.float64) - tol
    lo = min(a for a, _b, _z in stretches)
    hi = max(b for _a, b, _z in stretches)
    before = [lo - x for x, m in zip(s, met, strict=True) if m and x < lo]
    after = [x - hi for x, m in zip(s, met, strict=True) if m and x > hi]
    return (min(before) if before else math.inf, min(after) if after else math.inf)
