"""THE SUPPORT MEMBERS OF A BUILDING GROUP — EXPERIMENT (#1726; owner
2026-11-02T22:33Z-22:37Z, awaiting his sim read; REMOVE once he rules).

Owner, verbatim: "For poles or piers that are attached to the bottom of a
building, then they are supports for the building and should be considered
part of the building so they should be seated on the pad not underground"
and "I would expect the bottom of the poles and piers to be at grade,
likely lifting the building up".

A SUPPORT is a WALLED part (``[placement] chain_min_height_m``) that is
slender in plan: its plan box spans at most ``[building_pad]
support_max_extent_m`` on both axes (MEASURED KBWI ``BWI_Terminal_new``:
275 poles 0.3 x 0.3 m down to y -6.15, 171 piers 1.9 x 1.9 m down to
-3.46; walls and façades run tens of metres).  With ``[building_pad]
support_lift`` on:

* the planar storey readers do not take a support's feet as a STOREY's
  (``planar/low_level.walled_feet``): no lower pad is minted for them;
* the object stage lifts the group so its supports' DENSEST foot plane
  stands at grade (``airport/airside_group_seat.airside_zeros``), on top
  of the airside floor the stands read.

Off (the default) both readers are exactly as before.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["support_lift_on", "is_support", "support_plane"]

_M_PER_DEG = 111_320.0


def support_lift_on(law: _t.Any) -> bool:
    """Whether the experiment knob ``[building_pad] support_lift`` is on."""
    return bool(getattr(law.tables.structures.building_pad, "support_lift", False))


def is_support(part: _t.Any, law: _t.Any) -> bool:
    """A WALLED part whose lat/lon plan box (``part.box``: min lat, min
    lon, max lat, max lon) spans at most ``support_max_extent_m`` on both
    axes (module docstring)."""
    st = law.tables.structures
    if getattr(part, "line", False):
        return False
    if float(getattr(part, "height_m", 0.0) or 0.0) < float(st.placement.chain_min_height_m):
        return False
    box = getattr(part, "box", None)
    if not box:
        return False
    lim = float(getattr(st.building_pad, "support_max_extent_m", 0.0) or 0.0)
    dy = (float(box[2]) - float(box[0])) * _M_PER_DEG
    dx = (float(box[3]) - float(box[1])) * _M_PER_DEG * math.cos(math.radians(float(box[0])))
    return max(abs(dx), abs(dy)) <= lim


def support_plane(zs: _t.Sequence[float], band: float) -> "tuple[float, int] | None":
    """``(zero, feet)`` of the DENSEST ``band``-metre plane of the support
    feet's zero candidates ``ground z - y`` (the zero at which those feet
    stand at grade) — its median and how many feet hold it — or ``None``."""
    v = sorted(float(z) for z in zs)
    if not v:
        return None
    best, lo, j = 0, 0, 0
    for i in range(len(v)):
        while v[i] - v[j] > band:
            j += 1
        if i - j + 1 > best:
            best, lo = i - j + 1, j
    sel = v[lo:lo + best]
    return sel[len(sel) // 2], best
