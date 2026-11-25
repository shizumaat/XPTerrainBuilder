"""OUR GROUND IS GRADED TO A PARTIAL SHELL'S GROUND RIM (issue #2197).

The tile-raster half of ``airport/ground_rim``: a recognised origin set's
RIM STATIONS (its outer-rim cells in the author's ground sheet, at the
height the author's ground stands at its edge) pull our raster to them,
raised OR lowered -- the object never moves.

THE GRADE (:func:`rim_grade`), per free posting within
``terrain_fill.REACH_M`` of a station: the TARGET is the inverse-distance-
squared mean of the :data:`NEAREST` nearest stations' heights less
``UNDER_M`` (distance floored at half a posting diagonal); ``d`` the
distance to the nearest station, ``W`` the fill's shoulder
(``Raster.shoulder_m``); the weight ``w`` is 1 within ``W`` and falls
linearly to 0 at ``REACH_M``; the posting takes ``ground + w (target -
ground)``.  Inside the set's plan only postings within ``W`` of a station
move (the object covers the rest).  Never a frozen posting (the tile edge,
an airport patch: airside is king), never a posting within ``W`` of
another composite's ground (``terrain_fill.Owned``).  A station left more
than ``terrain_fill.SERVED_M`` off its target after the grade is UNSERVED
(it stands over or under a frozen posting), counted on the log line.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from ..geom.terrain_deck import UNDER_M
from . import terrain_fill as _tf

__all__ = ["NEAREST", "rim_grade"]

#: the stations a posting's target is read from
NEAREST = 8


def rim_grade(raster: "_tf.Raster", to_xy: _t.Callable, to_ll: _t.Callable,
              stations: np.ndarray, rings_xy: _t.Sequence[np.ndarray],
              owned: _t.Iterable["_tf.Owned"] = ()) -> dict[str, int]:
    """THE GRADE (module doc) on ``raster``: ``stations`` ``(n, 3)`` frame
    ``(east, north, z MSL)``, ``rings_xy`` the set's plan rings in frame
    metres, ``to_xy`` / ``to_ll`` its projector, ``owned`` the other
    composites' ground.  ``{"stations", "moved", "raised", "lowered",
    "unserved"}``."""
    from scipy.spatial import cKDTree
    rep = {"stations": int(len(stations)), "moved": 0, "raised": 0, "lowered": 0,
           "unserved": 0}
    if not len(stations):
        return rep
    sxy = np.asarray(stations, float)[:, :2]
    sz = np.asarray(stations, float)[:, 2] - UNDER_M
    reach = _tf.REACH_M
    lo, la = to_ll(np.r_[sxy[:, 0].min() - reach, sxy[:, 0].max() + reach],
                   np.r_[sxy[:, 1].min() - reach, sxy[:, 1].max() + reach])
    rows, cols, lons, lats = raster.window(float(np.min(lo)), float(np.min(la)),
                                           float(np.max(lo)), float(np.max(la)))
    if len(rows):
        x, y = to_xy(lons, lats)
        tree = cKDTree(sxy)
        k = min(NEAREST, len(sz))
        d, idx = tree.query(np.c_[x, y], k=k, distance_upper_bound=reach)
        d, idx = d.reshape(len(x), k), idx.reshape(len(x), k)
        near = np.isfinite(d[:, 0])
        w_sh = raster.shoulder_m()
        floor = 0.5 * float(np.hypot(*raster.posting_m()))
        ok = np.isfinite(d)
        iw = np.where(ok, 1.0 / np.maximum(np.where(ok, d, 1.0), floor) ** 2, 0.0)
        zz = np.where(ok, sz[np.minimum(idx, len(sz) - 1)], 0.0)
        target = (iw * zz).sum(1) / np.maximum(iw.sum(1), 1e-12)
        w = np.clip(1.0 - (d[:, 0] - w_sh) / max(reach - w_sh, 1e-6), 0.0, 1.0)
        inside = _tf._distance(_tf._polygon(rings_xy), x, y) <= 0.0
        free = near & ~(inside & (d[:, 0] > w_sh)) \
            & ~_tf._owned_mask(owned, to_xy, x, y, w_sh)
        old = raster.alt[rows, cols].astype(float)
        new = np.where(free, old + w * (target - old), old)
        moved = np.abs(new - old) > 1e-3
        raster.alt[rows[moved], cols[moved]] = new[moved]
        rep["moved"] = int(moved.sum())
        rep["raised"] = int((moved & (new > old)).sum())
        rep["lowered"] = int((moved & (new < old)).sum())
    after = raster.sample(*to_ll(sxy[:, 0], sxy[:, 1]))
    rep["unserved"] = int(np.sum(~(np.abs(after - sz) <= _tf.SERVED_M)))
    return rep
