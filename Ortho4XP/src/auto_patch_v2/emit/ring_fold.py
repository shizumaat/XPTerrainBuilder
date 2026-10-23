"""THE EMITTED RING IS A SIMPLE RING (issue #1275).

The mesh reads every closed way of a patch as ``shapely Polygon(way)`` and
DROPS one that is not valid (``O4_Vector_Map.include_patches``): the ring
gets no INTERP_ALT seed and its interior keeps the raw DEM.  At KMCI the
terminal + garage pad (``building26/b0``, ``b1``) and the two plateau aprons
it fronts shipped as bow-ties and carried a +5.8 m DEM ridge across the gate
apron (39.2996, -94.7229).

Two readings live here, one per caller:

* :func:`folded` — the closed sequences a vertex remap turns from simple
  into NOT simple; ``osm_adapter.merge_sub_spacing`` refuses every merge
  that folds one;
* :func:`ring_folds` — every emitted face ring and hole of a surface that
  is not simple, as rows; the verify stage fails the airport on one
  (``pipeline/verify_stage``), so an invalid ring never ships silently.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon

__all__ = ["ring_is_simple", "collapsed", "folded", "ring_folds", "FAMILY_RING_FOLD"]

#: the DEFECT family a non-simple emitted ring is reported under
FAMILY_RING_FOLD = "ring_fold"

XY = tuple[float, float]


def ring_is_simple(xy: _t.Sequence[XY]) -> bool:
    """``xy`` (open: the first point is not repeated) is a ring the mesh
    keeps — the ``include_patches`` reading exactly: a valid polygon with
    area (no self-crossing, no self-touch, no zero-width spike)."""
    if len(xy) < 3:
        return False
    pg = Polygon(xy)
    return bool(pg.is_valid and pg.area > 0.0)


def collapsed(ids: _t.Sequence[int], remap: _t.Mapping[int, int]) -> list[int]:
    """``ids`` (a closed sequence) under ``remap``, consecutive repeats
    folded into one vertex."""
    col: list[int] = []
    for i in ids:
        t = remap.get(i, i)
        if not col or col[-1] != t:
            col.append(t)
    while len(col) > 1 and col[0] == col[-1]:
        col.pop()
    return col


def folded(seqs: _t.Sequence[_t.Sequence[int]], remap: _t.Mapping[int, int],
           pxy: _t.Mapping[int, XY]) -> list[int]:
    """The indices of the closed sequences in ``seqs`` that were simple
    before ``remap`` and are not after it.  A ring handed over already
    folded is not the remap's to answer for (:func:`ring_folds` reports
    it); a ring the remap would take under three vertices is kept whole
    by the merge, so it is not read either."""
    out: list[int] = []
    for k, ids in enumerate(seqs):
        if all(remap.get(i, i) == i for i in ids):
            continue
        col = collapsed(ids, remap)
        if len(col) < 3:
            continue
        if (not ring_is_simple([pxy[i] for i in col])
                and ring_is_simple([pxy[i] for i in ids])):
            out.append(k)
    return out


def ring_folds(surface) -> list[dict]:
    """One row per emitted face ring or hole of ``surface`` (a
    ``GradedSurface``) that is not simple — the closed way the mesh would
    drop: ``way_a`` names the face, ``site_ll`` is its first vertex."""
    vll = {v.id: v.ll for v in surface.vertices}
    rows: list[dict] = []
    for f in surface.faces:
        for name, ids in (("ring", f.ring),
                          *((f"hole{i}", h) for i, h in enumerate(f.holes))):
            pts = [(float(vll[i][1]), float(vll[i][0])) for i in ids]
            if ring_is_simple(pts):
                continue
            rows.append({"way_a": f"{f.role} {f.ref} face {f.id}",
                         "reading": f"{name} is not a simple ring",
                         "magnitude_m": 0.0,
                         "site_ll": [list(vll[ids[0]])] if ids else []})
    return rows
