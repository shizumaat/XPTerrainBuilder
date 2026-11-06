"""A TRIANGULATED SURFACE'S PLANES: its faces grouped where they meet
without a crease (#1883 round 3 A5).

Two faces sharing a plan edge are one plane when their normals differ by
no more than ``crease_deg`` and they meet at one height along that edge (no
step); a crease or a step parts them.  ``planar/object_floor_cells`` cuts a
pack shell's footprint into one cell per plane, so the mesh's harmonic
interior (a planar ring reproduces its plane exactly) IS the shell.

``geom`` imports nothing of v2.
"""
from __future__ import annotations

import math

import numpy as np

from .union_find import find_root

__all__ = ["plane_groups"]

#: plan coordinates are matched at this precision (a pack repeats a vertex
#: per face; one POSITION is one vertex)
_KEY_DP = 2


def plane_groups(faces: np.ndarray, crease_deg: float, step_m: float) -> list[np.ndarray]:
    """The indices of ``faces`` ``(n, 3, 3)`` per plane (module doc), the
    faces with no plan area left out; largest plan area first."""
    p = np.asarray(faces, float)
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    plan = 0.5 * np.abs(n[:, 2])
    unit = n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
    unit[unit[:, 2] < 0.0] *= -1.0
    live = np.flatnonzero(plan > 1e-3)
    parent = {int(i): int(i) for i in live}
    edges: dict[tuple, list[tuple[int, float]]] = {}
    for i in live:
        for a, b in ((0, 1), (1, 2), (2, 0)):
            ka = (round(p[i, a, 0], _KEY_DP), round(p[i, a, 1], _KEY_DP))
            kb = (round(p[i, b, 0], _KEY_DP), round(p[i, b, 1], _KEY_DP))
            key = (ka, kb) if ka <= kb else (kb, ka)
            z = p[i, a, 2] + p[i, b, 2] if ka <= kb else p[i, b, 2] + p[i, a, 2]
            edges.setdefault(key, []).append((int(i), float(z)))
    cos = math.cos(math.radians(crease_deg))
    for share in edges.values():
        for k, (a, za) in enumerate(share):
            for b, zb in share[k + 1:]:
                if abs(float(unit[a] @ unit[b])) >= cos and abs(za - zb) <= 2.0 * step_m:
                    ra, rb = find_root(parent, a), find_root(parent, b)
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
    groups: dict[int, list[int]] = {}
    for i in live:
        groups.setdefault(find_root(parent, int(i)), []).append(int(i))
    out = [np.asarray(g, dtype=np.int64) for g in groups.values()]
    out.sort(key=lambda g: -float(plan[g].sum()))
    return out
