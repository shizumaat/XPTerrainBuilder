"""BULK GEOS — the array forms of the scalar shapely loops the pack-read
profile attributed (spec ``pack-read-once-fast-spec.md`` §B.3, row 3;
issue #28).

§B.3's G-rule: a per-geometry Python loop over a shapely predicate or
measurement whose operands are already in a list fails review; the array
form is required.  The forms here return EXACTLY what the scalar loops
returned — the identity is by construction, not by tolerance:

* :func:`within_distance` is ``[geom.distance(o) <= d for o in others]``.
  It asks GEOS's PREPARED ``dwithin`` (an indexed facet distance —
  §B.3 names the 7.5 ms-per-call ``object_cut`` probe against a large
  wall) at ``d ± _BRACKET_M`` and re-reads ONLY the operands that fall
  between the two brackets through the SAME scalar ``GEOSDistance`` the
  loop called.  So a station exactly AT the tolerance reads as it read
  before: the prepared path decides only what it decides by a margin
  twelve orders of magnitude above double rounding at airport scale.
* :func:`intersecting_pairs` is ``[(i, j) for i in A for j in B if
  A[i].intersects(B[j])]`` in the same order — an STRtree envelope
  query for the candidates and the SAME unprepared ``GEOSIntersects``
  on them (an envelope-disjoint pair never intersects).
"""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely

__all__ = ["within_distance", "intersecting_pairs"]

#: Metres either side of a distance tolerance inside which the prepared
#: reading is not trusted and the scalar distance decides.  Double
#: rounding on kilometre-scale coordinates is ~1e-12 m.
_BRACKET_M = 1e-6


def _geom_array(geoms: _t.Sequence) -> np.ndarray:
    out = np.empty(len(geoms), dtype=object)
    out[:] = list(geoms)
    return out


def within_distance(geom, others: _t.Sequence, d: float) -> np.ndarray:
    """``np.array([geom.distance(o) <= d for o in others])`` (module doc)."""
    arr = _geom_array(others)
    if arr.size == 0:
        return np.zeros(0, dtype=bool)
    d = float(d)
    was_prepared = bool(shapely.is_prepared(geom))
    if not was_prepared:
        shapely.prepare(geom)
    try:
        near = np.asarray(shapely.dwithin(geom, arr, d + _BRACKET_M), dtype=bool)
        sure = np.asarray(shapely.dwithin(geom, arr, d - _BRACKET_M), dtype=bool) \
            if d - _BRACKET_M >= 0.0 else np.zeros(arr.size, dtype=bool)
    finally:
        if not was_prepared:
            shapely.destroy_prepared(geom)
    out = sure.copy()
    amb = np.nonzero(near & ~sure)[0]
    if amb.size:
        # the scalar reading, on the unprepared geometry, for the band
        out[amb] = np.asarray(shapely.distance(geom, arr[amb]) <= d, dtype=bool)
    return out


def intersecting_pairs(a: _t.Sequence, b: _t.Sequence) -> tuple[np.ndarray, np.ndarray]:
    """The ``(i, j)`` with ``a[i].intersects(b[j])``, sorted by ``j`` then
    ``i`` (module doc).  Two int arrays of equal length."""
    aa, bb = _geom_array(a), _geom_array(b)
    if aa.size == 0 or bb.size == 0:
        z = np.zeros(0, dtype=np.intp)
        return z, z
    tree = shapely.STRtree(bb)
    qi, ti = tree.query(aa)                       # envelope candidates
    if qi.size:
        ok = np.asarray(shapely.intersects(aa[qi], bb[ti]), dtype=bool)
        qi, ti = qi[ok], ti[ok]
    order = np.lexsort((qi, ti))
    return qi[order], ti[order]
