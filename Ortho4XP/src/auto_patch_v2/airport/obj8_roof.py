"""The roof over an object's own floor plate — how much of a component's
deepest near-horizontal plate lies under the SAME object's solids above
it (spec §47 (8), issue #551: a roofed room under a thing taller than the
room is deep is a basement / service room, never a pit; an open-topped
plate, or one roofed only in part, is a pit — covered or open — however
tall what stands beside it).  Private to the ``airport`` package: the
reader is :func:`obj8.read_placement`; nothing numeric lives here.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from .obj8_clip import _union_rings

if _t.TYPE_CHECKING:  # annotations only — obj8 imports this module
    from .obj8 import Component

__all__ = ["roofed_fraction"]


def roofed_fraction(v: np.ndarray, comps: _t.Sequence["Component"], ci: int,
                    thickness_m: float, normal_y_min: float,
                    memo: dict | None = None, key: object = None) -> float:
    """The share of component ``ci``'s FLOOR PLATE — its near-horizontal
    faces (|n_y| >= ``normal_y_min``) within one solid thickness of the
    component's bottom — lying under any of the object's genuine solids
    whose faces stand above the plate (triangle centroid more than a
    thickness over the plate's top), in the authored plan.  0 for a
    component with no plate; memoised under ``key`` in ``memo`` (the read
    depends on the resource alone, never on where a placement stands)."""
    if memo is not None and key in memo:
        return memo[key]
    comp = comps[ci]
    t = comp.tris
    p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(p1 - p0, p2 - p0)
    ln = np.linalg.norm(n, axis=1)
    ny = np.zeros(t.shape[0])
    ok = ln > 1e-12
    ny[ok] = np.abs(n[ok, 1] / ln[ok])
    y_max = np.maximum(np.maximum(p0[:, 1], p1[:, 1]), p2[:, 1])
    floor = (ny >= normal_y_min) & (y_max <= comp.min_y + thickness_m)
    out = 0.0
    plate = _union_rings([[(float(v[i][0]), float(v[i][2])) for i in tri]
                          for tri in t[floor].tolist()]) if floor.any() else None
    if plate is not None and not plate.is_empty and plate.area > 0.0:
        top = float(y_max[floor].max()) + thickness_m
        x0, y0, x1, y1 = plate.bounds
        rings: list[list[tuple[float, float]]] = []
        for c in comps:
            if c.max_y - c.min_y < thickness_m or c.max_y <= top:
                continue            # a decal never roofs; nothing up there
            ct = c.tris
            q0, q1, q2 = v[ct[:, 0]], v[ct[:, 1]], v[ct[:, 2]]
            cy = (q0[:, 1] + q1[:, 1] + q2[:, 1]) / 3.0
            xs = np.stack([q0[:, 0], q1[:, 0], q2[:, 0]], axis=1)
            zs = np.stack([q0[:, 2], q1[:, 2], q2[:, 2]], axis=1)
            sel = (cy > top) & (xs.max(axis=1) >= x0) & (xs.min(axis=1) <= x1) \
                & (zs.max(axis=1) >= y0) & (zs.min(axis=1) <= y1)
            rings.extend([(float(v[i][0]), float(v[i][2])) for i in tri]
                         for tri in ct[sel].tolist())
        roof = _union_rings(rings) if rings else None
        if roof is not None and not roof.is_empty:
            out = float(plate.intersection(roof).area / plate.area)
    if memo is not None:
        memo[key] = out
    return out
