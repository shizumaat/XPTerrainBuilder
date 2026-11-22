"""ONE MEMBER'S PLACEMENT MATRIX (spec §51 (2)): the ``[a, b, d, e, xoff,
yoff]`` taking an object member's authored ``(x, z)`` into the unit frame.
Pure arithmetic, a leaf, so ``airport/obj8_grade`` (which applies it) and
``model/pad_base_slope`` (which rotates a member's authored gradient by it)
read ONE matrix.  Moved from ``airport/obj8_grade`` unchanged.  Nothing
here names an airport.
"""
from __future__ import annotations

import math

__all__ = ["place_matrix"]


def place_matrix(dx: float, dz: float, heading_deg: "float | None"
                  ) -> tuple[float, float, float, float, float, float]:
    """The ``[a, b, d, e, xoff, yoff]`` taking one member's AUTHORED
    ``(x, z)`` into the unit frame — ``obj8.placement_affine``'s matrix
    for a placed member, and a pure TRANSLATION for ``heading_deg`` None
    (the dry roll-up, ``airport/obj8_grade._part_row``).  The matrix is BUILT here and
    APPLIED by ``airport/frame_entry.enter``, which §51 (2) makes the one
    site that puts a placement affine on a polygon."""
    if heading_deg is None:
        return (1.0, 0.0, 0.0, 1.0, dx, dz)
    h = math.radians(heading_deg)
    sn, cs = math.sin(h), math.cos(h)
    return (cs, -sn, -sn, -cs, dx, dz)
