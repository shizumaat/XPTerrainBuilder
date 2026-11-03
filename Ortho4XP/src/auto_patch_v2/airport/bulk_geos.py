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
* :func:`any_within_distance` is ``[any(s.distance(o) <= d for s in
  sources) for o in others]`` — :func:`within_distance` per source, asked
  only of the ``others`` whose envelope comes within ``d`` (plus the
  bracket) of the source's (an envelope farther than ``d`` holds no point
  within ``d``).  Issue #1709: KIDA's grass resource paired 24,314
  footprint rings with 44,357 below-zero pieces, 139 s; 0.7 s this way.
* :func:`intersection_lengths` is ``[l.intersection(poly).length for l in
  lines]``, each line intersected with only the PARTS of ``poly`` whose
  envelope meets its own (no part means no intersection, ``0.0``).  The
  overlay nodes a line against the edges it meets, so the far parts add
  nothing; measured bitwise-equal on all 24,314 rings of #1709's grass
  resource (346 s -> 1.5 s against its 5,829-part, 1.36 M-vertex band).
"""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely

__all__ = ["within_distance", "intersecting_pairs", "any_within_distance",
           "intersection_lengths"]

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


def any_within_distance(sources: _t.Sequence, others: _t.Sequence, d: float) -> np.ndarray:
    """Per ``others`` member, whether any of ``sources`` lies within ``d``
    of it — :func:`within_distance` behind an envelope prefilter (module
    doc)."""
    arr = _geom_array(others)
    hit = np.zeros(arr.size, dtype=bool)
    if arr.size == 0:
        return hit
    tree = shapely.STRtree(arr)
    m = float(d) + 2.0 * _BRACKET_M
    for s in sources:
        x0, y0, x1, y1 = s.bounds
        cand = tree.query(shapely.box(x0 - m, y0 - m, x1 + m, y1 + m))
        cand = cand[~hit[cand]]
        if cand.size:
            hit[cand] = within_distance(s, arr[cand], d)
    return hit


def intersection_lengths(lines: _t.Sequence, poly) -> list[float]:
    """``[l.intersection(poly).length for l in lines]``, each against only
    the parts of ``poly`` its envelope meets (module doc)."""
    parts = shapely.get_parts(poly)
    tree = shapely.STRtree(parts)
    out: list[float] = []
    for line in lines:
        cand = np.sort(tree.query(line))
        if cand.size == 0:
            out.append(0.0)
            continue
        sub = parts[cand[0]] if cand.size == 1 else shapely.MultiPolygon(list(parts[cand]))
        out.append(line.intersection(sub).length)
    return out
