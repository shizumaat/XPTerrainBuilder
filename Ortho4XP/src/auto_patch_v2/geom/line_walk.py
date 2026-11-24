"""POINTS AT DISTANCES ALONG A LINE IN ONE WALK -- ``shapely.
line_interpolate_point(line, d)`` for MANY distances, bit for bit, without
walking the line from its start once per distance (#2206: a walled pit's
outline sampled every ``wall_sample_m``, thousands of points on a ring of
thousands of vertices).

GEOS (``LengthLocationMap.getLocationForward``) walks the segments of every
component in order, adding each segment's length to a running total, and
stops at the first segment whose ``total + length`` passes ``d``: the point
is that segment's own interpolation at ``d - total``.  Here the running
totals are the sequential sum (``np.cumsum``) of the segments' lengths as
GEOS measures them (``shapely.length`` of each two-point segment), the
segment is found by one search, and the point is GEOS's own interpolation
on that ONE segment at ``d - total`` -- the same subtraction, division and
interpolation GEOS makes in the long walk.  A distance GEOS would answer
otherwise -- on a component's end, at or past the line's end, at or before
its start, or where the one-segment walk would not stop on that segment --
is handed to ``shapely.line_interpolate_point`` on the whole line, so every
answer is GEOS's own.
"""
from __future__ import annotations

import numpy as np
import shapely

__all__ = ["points_along"]


def points_along(line, d: np.ndarray) -> np.ndarray:
    """``shapely.line_interpolate_point(line, d)`` (``line`` a LineString,
    LinearRing or MultiLineString; ``d`` distances from its start): the
    same Points, bit for bit (module doc)."""
    d = np.asarray(d, dtype=np.float64)
    segs, ends = [], []
    for part in shapely.get_parts(line):
        c = shapely.get_coordinates(part)
        if len(c) >= 2:
            segs.append(np.stack([c[:-1], c[1:]], axis=1))
            ends.append(len(c) - 1)
    if not segs or not len(d):
        return shapely.line_interpolate_point(line, d)
    S = np.concatenate(segs)
    lines = shapely.linestrings(S)
    seg = shapely.length(lines)
    after = np.cumsum(seg)
    before = np.concatenate([[0.0], after[:-1]])
    k = np.searchsorted(after, d, side="right")
    # on a component's end GEOS answers that end, not the next one's start
    ok = (d > 0.0) & (k < len(S)) & ~np.isin(d, after[np.cumsum(ends) - 1])
    kk = np.where(ok, k, 0)
    off = d - before[kk]
    # the one-segment walk stops on its segment only where it passes ``off``
    ok &= seg[kk] > off
    out = np.empty(len(d), dtype=object)
    if ok.any():
        out[ok] = shapely.line_interpolate_point(lines[kk[ok]], off[ok])
    if (~ok).any():
        out[~ok] = shapely.line_interpolate_point(line, d[~ok])
    return out
