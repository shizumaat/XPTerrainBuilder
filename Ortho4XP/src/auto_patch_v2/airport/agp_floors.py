"""AN ``.agp`` PIECE'S FLOORS (#2090): the up-facing static floor triangles
of one OBJ8 piece, the one read every AGP reader shares
(``agp_ground``'s connector floors, the deck join and the ground-floor
plates of spec 2090 B1 / C1).

A floor is a solid face whose normal's vertical share is at least
``[agp] flat`` (X-Plane's front face is clockwise seen from the front: an
up-facing floor's ``(b - a) x (c - a)`` points DOWN in the OBJ frame); a
face under an animation (a jetway's tunnel) is no floor.
"""
from __future__ import annotations

import numpy as np

__all__ = ["floors_of", "parse_floors", "flush"]


def parse_floors(path: str, flat: float) -> np.ndarray:
    """``(k, 3, 3)`` float32 — every up-facing static floor triangle of
    the OBJ8 at ``path`` as its three ``(x, y, z)`` corners (authored
    frame); empty when the file does not parse."""
    from . import obj8 as _obj8
    try:
        g = _obj8.parse_obj8(path, at_rest=True)
    except (OSError, ValueError):
        g = None
    out = np.zeros((0, 3, 3), np.float32)
    if g is not None and g.solid.shape[0]:
        v, t = g.vertices, g.solid
        a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        n = np.cross(b - a, c - a)
        norm = np.linalg.norm(n, axis=1)
        up = (norm > 1e-9) & (-n[:, 1] >= flat * norm)
        if g.animated.shape[0] == up.shape[0]:
            up &= ~g.animated          # a moving floor (a jetway) joins nothing
        if up.any():
            out = np.stack([a[up], b[up], c[up]], axis=1).astype(np.float32)
    return out


def floors_of(path: str, flat: float) -> np.ndarray:
    """:func:`parse_floors` of ``path``."""
    return parse_floors(path, flat)


def flush() -> int:
    """Nothing to write (no cache yet)."""
    return 0
