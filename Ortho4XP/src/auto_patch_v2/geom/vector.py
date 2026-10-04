"""PLAN VECTORS: the two readings of a direction every stage needs.

ONE implementation each (lane ``v2trim``, owner RULINGS 2026-10-04c (2));
they replaced private copies in ``airport/door_wells``, ``airport/
tunnel_walls``, ``airport/object_cut``, ``airport/wall_geometry``,
``planar/structure_approach``, ``planar/structure_geometry`` and
``planar/structure_deck``.  ``geom`` imports nothing of v2.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["unit_vector", "chord_bearing_mod180"]

XY = tuple[float, float]


def unit_vector(a: XY, b: XY) -> XY:
    """The unit vector from ``a`` towards ``b``; ``(0, 0)`` when they
    coincide (the length is taken as 1, never divided by zero)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1.0
    return (dx / L, dy / L)


def chord_bearing_mod180(line: _t.Any) -> float:
    """The bearing of a line's end-to-end CHORD in degrees from +y,
    folded to ``[0, 180)`` — an axis, not a heading: a line and its
    reverse read the same."""
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    return (math.degrees(math.atan2(x1 - x0, y1 - y0)) + 360.0) % 180.0
