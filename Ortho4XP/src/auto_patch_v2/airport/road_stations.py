"""THE ROAD STATION TABLE (issue #412, cold-patch-300s spec C8; owner
answer Q56 2026-10-20).

:meth:`RoadProfiles.answer` projects one vertex onto EVERY candidate way
(the ways through its faces and the ways within the core's radius) — on
a late map ~240 candidates per vertex, two GEOS calls (``project``,
``distance``) each: 3.4 M calls at HECA.  This module answers the same
question for all candidates of one vertex in one numpy pass over a
table of their segments, built once per candidate set.

The reading is GEOS's own (``LengthIndexOfPoint``): per way the FIRST
segment at the minimum point-segment distance, the measure its start's
arclength plus the clamped projection factor times its length; the
lateral distance that minimum.  Rounding only (numpy against GEOS).
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["StationTable"]


class StationTable:
    """The segments of an ordered set of polylines, concatenated:
    start ``a`` (m, 2), direction ``d`` (m, 2), squared length, length,
    start arclength along its own polyline, and each polyline's first
    segment index."""

    __slots__ = ("a", "d", "len2", "seglen", "s0", "starts", "own", "ids")

    def __init__(self, polylines: _t.Sequence[np.ndarray]):
        a, d, s0, starts = [], [], [], []
        k = 0
        for xy in polylines:
            xy = np.asarray(xy, dtype=float)
            dd = np.diff(xy, axis=0)
            L = np.hypot(dd[:, 0], dd[:, 1])
            starts.append(k)
            k += len(dd)
            a.append(xy[:-1])
            d.append(dd)
            s0.append(np.concatenate(([0.0], np.cumsum(L)[:-1])))
        self.a = np.concatenate(a)
        self.d = np.concatenate(d)
        self.len2 = (self.d * self.d).sum(axis=1)
        self.seglen = np.sqrt(self.len2)
        self.s0 = np.concatenate(s0)
        self.starts = np.asarray(starts, dtype=np.intp)
        counts = np.diff(np.append(self.starts, k))
        self.own = np.repeat(np.arange(len(starts)), counts)
        self.ids = np.arange(k)

    def project(self, x: float, y: float) -> tuple[np.ndarray, np.ndarray]:
        """``(s, dist)`` per polyline: the arclength of ``(x, y)``'s
        projection (``LineString.project``) and its distance
        (``LineString.distance``)."""
        px = x - self.a[:, 0]
        py = y - self.a[:, 1]
        with np.errstate(divide="ignore", invalid="ignore"):
            r = (px * self.d[:, 0] + py * self.d[:, 1]) / self.len2
        r = np.clip(np.nan_to_num(r, nan=0.0), 0.0, 1.0)
        dist = np.hypot(px - r * self.d[:, 0], py - r * self.d[:, 1])
        best = np.minimum.reduceat(dist, self.starts)
        idx = np.where(dist == best[self.own], self.ids, len(dist))
        first = np.minimum.reduceat(idx, self.starts)
        return self.s0[first] + r[first] * self.seglen[first], best
