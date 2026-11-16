"""A DECK PLATE'S HEIGHT AT ROAD VERTICES (#2091 R3): pure shape read off a
deck's ``plate`` triangles and ``ring``, shared by ``model.deck_ends``."""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import Polygon

from .lowest_face import every_z_at, floor_z_at

__all__ = ["plate_heights", "driven_y_at"]

#: #2062 R5: a plate face read further than this from the end's top is no
#: driven layer there (an underside, a pier, a wall's plane read off its edge)
DRIVEN_TOL_M = 1.0


def driven_y_at(plate: np.ndarray, xs, ys, top: float, edge_m: float) -> np.ndarray:
    """#2062 R5 E′4: the DRIVEN layer's height at each point -- of the plate
    faces over it (or within ``edge_m`` of it, on its plane), the one nearest
    the end's ``top``, within :data:`DRIVEN_TOL_M`; ``nan`` with none.  A
    plate carrying its underside, piers and kerbs as hard faces (KLAX
    Road_Bridge: y -6 / -1 / -0.3 / +0.5) is read at its road, never at its
    lowest face."""
    out = np.full(len(np.asarray(xs)), np.nan)
    for k, zs in enumerate(every_z_at(plate, xs, ys, edge_m=edge_m)):
        if len(zs):
            z = float(zs[np.argmin(np.abs(np.asarray(zs) - top))])
            if abs(z - top) <= DRIVEN_TOL_M:
                out[k] = z
    return out


def plate_heights(d, xy, top: float, flush: float, edge_m: float,
                  driven: bool = False) -> list[float]:
    """#2091 R3: the deck plate's own height (over the stack's zero) at each
    road vertex ``xy`` -- ``floor_z_at(plate, edge_m=H)`` (``driven``:
    :func:`driven_y_at`, #2062 R5), ``flush`` lower inside the deck's ring;
    ``top`` (less the same flush) where the plate gives none."""
    if not xy:
        return []
    pts = np.asarray(xy, float).reshape(-1, 2)
    plate = np.asarray(d.plate, float).reshape(-1, 3, 3)
    if not len(plate):
        ys = np.full(len(pts), np.nan)
    elif driven:
        ys = driven_y_at(plate, pts[:, 0], pts[:, 1], float(top), edge_m)
    else:
        ys = floor_z_at(plate, pts[:, 0], pts[:, 1], edge_m=edge_m)
    ring = Polygon(d.ring) if len(d.ring) >= 3 else None
    if ring is not None and driven:
        # #2062 R5: an end-line vertex (within the edge read of the ring) is
        # the deck's end, flush with it -- never a flush under it
        ring = ring.buffer(-min(0.5, edge_m), join_style="mitre")
    inside = (shapely.contains_xy(ring, pts[:, 0], pts[:, 1])
              if ring is not None and not ring.is_empty else np.zeros(len(pts), bool))
    return [(y if y == y else top) - (flush if ins else 0.0)
            for y, ins in zip(ys.tolist(), inside.tolist(), strict=True)]
