"""The X-Plane Next-Gen (S2 cell) elevation-layer adapter — STUB
(plan "Portability requirement", milestone M6).

WHAT LAMINAR HAS PUBLISHED (FSExpo 2026, Supnik; plan §Portability):
S2 hierarchical cells replace the 1° DSF tiles; terrain becomes layered
raster datasets (elevation grids, orthophotos, LiDAR) patchable PER
LAYER; a tile engine ships late 2026 with third-party support; DSF stays
compatible.

WHAT HAS NOT BEEN PUBLISHED (so this module cannot be implemented):
the elevation-layer raster format (cell size, datum, encoding, tiling
within a cell), the S2 cell level the terrain layer uses, whether
breaklines / constrained edges exist in the raster model or are baked,
how airport flattening is expressed, the authoring format, and any SDK.

THE INTERFACE (stable regardless of the answers): rasterise the
:class:`GradedSurface` into a cell's elevation layer — for every raster
sample inside a face, the plane of its triangle in the graded surface's
constrained triangulation; outside every face, untouched.  Breaklines
are the triangulation's constrained edges (a heightfield cannot carry a
vertical face: the wall gap, RULINGS 2026-09-01c, is a steep triangle
here exactly as in the mesh).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .surface import GradedSurface

__all__ = ["S2Cell", "RasterPatch", "rasterise"]


@_dc.dataclass(frozen=True)
class S2Cell:
    """An S2 cell id at the terrain layer's level (level TBD)."""

    token: str
    level: int


@_dc.dataclass(frozen=True)
class RasterPatch:
    """A rectangular elevation-grid patch inside one cell: ``origin``
    (lat, lon) of sample (0, 0), ``step_deg`` per sample, ``rows`` ×
    ``cols`` samples, ``z`` row-major, ``mask`` row-major (True where
    the graded surface wrote a sample)."""

    cell: S2Cell
    origin: tuple[float, float]
    step_deg: float
    rows: int
    cols: int
    z: tuple[float, ...]
    mask: tuple[bool, ...]


def rasterise(surface: GradedSurface, cells: _t.Sequence[S2Cell],
              step_deg: float) -> tuple[RasterPatch, ...]:
    """Rasterise the graded surface into the given cells.  Not
    implementable until the layer format is published (M6)."""
    raise NotImplementedError(
        "S2 elevation-layer format unpublished (see module docstring)")
