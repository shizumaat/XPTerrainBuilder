"""THE PLATES OF A DECK IN PLAN (#2112): pieces within the rigid reach
chained into one plate, and the plates told apart only where they stand in
order along one axis with every gap along it wider than that reach -- the
pure-geometry half of ``airport/deck_plates`` (the object stage's rule),
kept in ``geom`` so ``constraints/deck_lines.plate_of`` (the patch half)
reads the same rule without importing ``airport`` (M0 §1).

No airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from .union_find import find_root

__all__ = ["Plates", "plate_clusters", "plate_bands", "piece_plates"]


@_dc.dataclass(frozen=True)
class Plates:
    """The bands of a deck in plates: ``axis`` the unit plan direction
    ``(ux, uz)`` in the authored frame, ``extents`` each plate's
    ``(lo, hi)`` along it in order, ``cuts`` the band lines between them
    (each gap's middle), ``gaps`` the gap widths along the axis."""

    axis: tuple[float, float]
    extents: tuple[tuple[float, float], ...]
    cuts: tuple[float, ...]
    gaps: tuple[float, ...]

    def __len__(self) -> int:
        return len(self.extents)

    def band_of(self, x: float, z: float) -> int:
        """The band the authored plan point ``(x, z)`` stands in."""
        s = self.axis[0] * float(x) + self.axis[1] * float(z)
        return int(sum(1 for c in self.cuts if s >= c))

    def band(self, k: int) -> tuple[float, float, float, float]:
        """``(ux, uz, lo, hi)`` of band ``k`` -- what ``obj8_split.BodyCut.
        band`` clips to; the outer bands run to infinity."""
        lo = -math.inf if k == 0 else self.cuts[k - 1]
        hi = math.inf if k == len(self.cuts) else self.cuts[k]
        return (self.axis[0], self.axis[1], lo, hi)

    def axis_of(self, _k: int) -> tuple[float, float]:
        """Band ``_k``'s axis -- the one axis (``plate_cells.Cells`` answers
        per cell)."""
        return self.axis

    def extent_of(self, k: int) -> tuple[float, float]:
        """Band ``k``'s ``(lo, hi)`` along the axis."""
        return self.band(k)[2:]


def plate_clusters(polys: list, reach_m: float) -> list[list[int]]:
    """Pieces within ``reach_m`` of each other chained into one plate."""
    parent = list(range(len(polys)))
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)):
            if polys[i].distance(polys[j]) <= reach_m:
                parent[find_root(parent, i)] = find_root(parent, j)
    out: dict[int, list[int]] = {}
    for i in range(len(polys)):
        out.setdefault(find_root(parent, i), []).append(i)
    return list(out.values())


def plate_bands(plates: _t.Sequence[np.ndarray], reach_m: float) -> "Plates | None":
    """The bands of ``plates`` (each an ``(n, 2)`` array of its plan points
    ``(x, z)``), or None where they do not stand in order along one axis
    with every gap along it wider than ``reach_m`` (``airport/deck_plates`` module doc)."""
    if len(plates) < 2:
        return None
    cen = np.asarray([np.asarray(p, float).mean(axis=0) for p in plates])
    d = cen - cen.mean(axis=0)
    w, vec = np.linalg.eigh(d.T @ d)        # the plates' centres' main axis
    ax = vec[:, int(np.argmax(w))]
    if ax[0] < 0 or (ax[0] == 0 and ax[1] < 0):
        ax = -ax
    ext = sorted((float((np.asarray(p, float) @ ax).min()),
                  float((np.asarray(p, float) @ ax).max())) for p in plates)
    gaps = tuple(b[0] - a[1] for a, b in zip(ext, ext[1:], strict=False))
    if min(gaps) <= reach_m:
        return None
    cuts = tuple(0.5 * (a[1] + b[0]) for a, b in zip(ext, ext[1:], strict=False))
    return Plates((float(ax[0]), float(ax[1])), tuple(ext), cuts, gaps)


def piece_plates(rings: _t.Sequence[_t.Sequence[tuple[float, float]]],
                 reach_m: float) -> "tuple[int, ...] | None":
    """The plate of each deck PIECE (``rings``: one deck object's piece
    outlines in plan, any one frame) -- the patch half's reading of the
    same rule (``constraints/deck_lines.plate_of``): pieces within
    ``reach_m`` are one plate, and the plates are told apart only where
    they band (:func:`plate_bands`); ``None`` otherwise (one zero for the
    object, as before)."""
    import shapely
    if len(rings) < 2 or reach_m <= 0.0:
        return None
    polys = [shapely.Polygon(r).buffer(0.0) for r in rings]
    if any(p.is_empty for p in polys):
        return None
    groups = plate_clusters(polys, reach_m)
    if len(groups) < 2:
        return None
    pts = [np.concatenate([np.asarray(rings[i], float) for i in g]) for g in groups]
    p = plate_bands(pts, reach_m)
    if p is None:
        return None
    out = [0] * len(rings)
    for g, grp in zip(pts, groups, strict=True):
        k = p.band_of(*g.mean(axis=0))
        for i in grp:
            out[i] = k
    return tuple(out)
