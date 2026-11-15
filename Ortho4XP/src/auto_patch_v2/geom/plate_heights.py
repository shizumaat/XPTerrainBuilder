"""A DECK PLATE'S HEIGHT AT ROAD VERTICES (#2091 R3): pure shape read off a
deck's ``plate`` triangles and ``ring``, shared by ``model.deck_ends``."""
from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import Polygon

from .lowest_face import floor_z_at

__all__ = ["plate_heights"]


def plate_heights(d, xy, top: float, flush: float, edge_m: float) -> list[float]:
    """#2091 R3: the deck plate's own height (over the stack's zero) at each
    road vertex ``xy`` -- ``floor_z_at(plate, edge_m=H)``, ``flush`` lower
    inside the deck's ring; ``top`` (less the same flush) where the plate
    gives none."""
    if not xy:
        return []
    pts = np.asarray(xy, float).reshape(-1, 2)
    plate = np.asarray(d.plate, float).reshape(-1, 3, 3)
    ys = (floor_z_at(plate, pts[:, 0], pts[:, 1], edge_m=edge_m) if len(plate)
          else np.full(len(pts), np.nan))
    inside = (shapely.contains_xy(Polygon(d.ring), pts[:, 0], pts[:, 1])
              if len(d.ring) >= 3 else np.zeros(len(pts), bool))
    return [(y if y == y else top) - (flush if ins else 0.0)
            for y, ins in zip(ys.tolist(), inside.tolist(), strict=True)]
