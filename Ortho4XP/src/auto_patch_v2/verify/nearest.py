"""THE NEAREST POINT, FIRST ON A TIE (#2206, fastest-pipeline spec item 1).

Three verify readers took a point's nearest published point by a Python
``min`` over the whole list per query — ``lateral_contiguity``'s station
caps (KATL 165.6 s, KDFW 294.8 s of verify), the basin floor's rim and the
frontage witness.  :class:`FirstNearest` answers the SAME index: a
``cKDTree`` names the few points within the nearest distance (plus a
relative slack far above its rounding), and the caller's own squared
distance — the very expression the ``min`` read, on the very objects — picks
among them, the first in list order on a tie, exactly as ``min`` does.
Below :data:`SCAN_BELOW` points it is that ``min`` itself.
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["SCAN_BELOW", "FirstNearest"]

#: fewer points than this are scanned (the tree is not worth building)
SCAN_BELOW = 64
#: the candidate ball's slack over the tree's nearest distance: relative,
#: and absolute in the points' own units (metres) — both far above the
#: tree's float rounding, so every point at the exact minimum is in it
_REL, _ABS = 1e-9, 1e-9


class FirstNearest:
    """``index(x, y)``: the index ``i`` of ``points`` minimising
    ``(xy(points[i])[0] - x) ** 2 + (xy(points[i])[1] - y) ** 2`` — the
    first such ``i`` on a tie, ``ValueError`` for no point (``min``'s
    answer).  ``xy`` reads a point's plan coordinates (default: the point)."""

    def __init__(self, points: _t.Sequence, xy: _t.Callable[[_t.Any], _t.Sequence[float]]
                 = lambda q: q) -> None:
        self._xy = [xy(q) for q in points]
        self._tree = None
        if len(self._xy) >= SCAN_BELOW:
            from scipy.spatial import cKDTree
            self._tree = cKDTree(np.array([(float(a[0]), float(a[1])) for a in self._xy],
                                          dtype=float))

    def __len__(self) -> int:
        return len(self._xy)

    def index(self, x: float, y: float) -> int:
        pts = self._xy
        if self._tree is None:
            cand: _t.Iterable[int] = range(len(pts))
        else:
            d, _i = self._tree.query((float(x), float(y)))
            cand = sorted(self._tree.query_ball_point((float(x), float(y)),
                                                      float(d) * (1.0 + _REL) + _ABS))
        return min(cand, key=lambda i: (pts[i][0] - x) ** 2 + (pts[i][1] - y) ** 2)
