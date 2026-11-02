"""THE TERRAIN-SHAPED DECK'S SHAPE (issue #1730) -- a hard deck binned on a
plan grid in its own frame, its rigid seat, and the surface the ground
under it is drawn to.  Pure shape: the recogniser is
``airport/terrain_shaped``, the rows ``constraints/terrain_shaped``.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np

__all__ = ["CELL_M", "UNDER_M", "DeckGrid", "TerrainFit", "target_at"]

#: the plan grid the deck is binned on, metres
CELL_M = 5.0
#: the ground stands this far under the deck where the two meet, so the
#: deck draws over the mesh instead of fighting it
UNDER_M = 0.1


@_dc.dataclass(frozen=True)
class DeckGrid:
    """The deck binned in its own plan frame: cell centres ``x0 + i *
    CELL_M`` / ``z0 + j * CELL_M``; ``bot`` / ``top`` the lowest / highest
    deck surface per cell (``nan`` where the deck does not cover it)."""

    x0: float
    z0: float
    bot: np.ndarray
    top: np.ndarray

    @property
    def covered(self) -> np.ndarray:
        return np.isfinite(self.bot)

    @property
    def area_m2(self) -> float:
        return float(self.covered.sum()) * CELL_M * CELL_M

    @property
    def relief_m(self) -> float:
        """The lowest surface's RELIEF BEYOND A PLANE: the 5th to 95th
        percentile span of its departure from its least-squares plane (a
        deck on a grade has none, however long)."""
        ii, jj = np.nonzero(self.covered)
        a = np.c_[ii, jj, np.ones(len(ii))].astype(float)
        b = self.bot[ii, jj]
        coef, *_ = np.linalg.lstsq(a, b, rcond=None)
        lo, hi = np.percentile(b - a @ coef, [5.0, 95.0])
        return float(hi - lo)

    def cell_of(self, x: np.ndarray, z: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """``(i, j, inside)`` of authored plan points ``(x, z)``."""
        i = np.rint((np.asarray(x, dtype=float) - self.x0) / CELL_M).astype(np.int64)
        j = np.rint((np.asarray(z, dtype=float) - self.z0) / CELL_M).astype(np.int64)
        ok = (i >= 0) & (j >= 0) & (i < self.bot.shape[0]) & (j < self.bot.shape[1])
        ok[ok] = self.covered[i[ok], j[ok]]
        return i, j, ok


@_dc.dataclass(frozen=True)
class TerrainFit:
    """One terrain-shaped placement's seat: ``z0`` the MSL height of its
    ``y = 0`` plane; ``follow`` the share of its cells on the ground."""

    id: str
    path: str
    xy: tuple[float, float]
    heading_deg: float
    z0: float
    follow: float
    area_m2: float
    relief_m: float
    grid: DeckGrid = _dc.field(repr=False, compare=False)

    def local(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Frame ``(east, north)`` -> authored plan ``(x, z)`` (the inverse
        of the placement's rigid frame: heading clockwise, ``-z`` north)."""
        h = math.radians(self.heading_deg)
        s, c = math.sin(h), math.cos(h)
        dx = np.asarray(x, dtype=float) - self.xy[0]
        dy = np.asarray(y, dtype=float) - self.xy[1]
        return dx * c - dy * s, -(dx * s + dy * c)


def target_at(f: TerrainFit, x: np.ndarray, y: np.ndarray, dem: np.ndarray
              ) -> tuple[np.ndarray, np.ndarray]:
    """``(target z, under the deck)`` at frame points ``(x, y)`` with ground
    ``dem``: the deck surface nearest the ground there (``UNDER_M`` under
    it), or the ground itself where it lies inside the deck's span."""
    lx, lz = f.local(x, y)
    i, j, ok = f.grid.cell_of(lx, lz)
    out = np.asarray(dem, dtype=float).copy()
    if ok.any():
        lo = f.z0 + f.grid.bot[i[ok], j[ok]] - UNDER_M
        hi = f.z0 + f.grid.top[i[ok], j[ok]] - UNDER_M
        out[ok] = np.clip(out[ok], lo, hi)
    return out, ok
