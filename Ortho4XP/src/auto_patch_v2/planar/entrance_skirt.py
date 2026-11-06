"""THE ENTRANCE SKIRT (#1747; owner RULINGS 2026-11-06c (3) "option 1",
clarified 17:37Z: "the ramp depth and width should be set based on the
mouth object, such that the bottom of the ramp meets the bottom of the
mouth object that faces the ramp, and the terrain on the other/back side of
the mouth object should grade flush to the back of the object at the top of
the object, with the mouth object seated so it's bottom sits at the bottom
of the ramp and it's top is at grade").

An ENTRANCE face (``trench_objects.mouth_portals``: a trench object's face
at a mapped tunnel end, its top flush with the object's zero over a wall's
height of solids) is seated with its bottom on the mouth's floor and its top
on the ground over it (Q-A 2026-11-05).  Two readings follow, both here:

* THE MOUTH STANDS AT THE FACE'S FRONT (:func:`face_front_mouth`): the
  ramp ends where the face's top plate begins on the ramp's side, so the
  ramp's floor meets the face's bottom at the face, never under its top.
  MEASURED LOWS (lowspad, west mouth): the mapped end stood at the BACK of
  a 6 m-deep top, the ramp ran under it and the drawn top read 4.8 m over
  the ramp (``tools/drawn_site.py``, component c1, p50).
* THE GROUND ROUND THE TOP IS THE TOP (:func:`entrance_skirt`): the face's
  top plan, and the ground within ``[tunnel.object] entrance_skirt_m`` of
  it, is a face of its own (role ``model.structures.SKIRT_ROLE``, cut out
  of the tunnel's ``tunnel_wall`` void) whose vertices the constraint
  stage holds at the top (``constraints/entrance_skirt``), and a BANK face
  round it falls to the DEM at ``emit.design.bank_slope``.  Neither is a
  rim: read as one, the object stage took the entrance object for a
  basin's and seated both its faces at one zero (LOWS, lane lowsskirt).
  Neither takes airside pavement (airside is king: the apron keeps its own
  law) nor the ramp and its wall stand-off.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString
from shapely.ops import substring, unary_union

from ..model.frame import XY

__all__ = ["face_front_mouth", "is_entrance_face", "entrance_skirt", "skirt_refs"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)
#: plan samples along the skirt's ring for the bank width (metres)
_RING_STEP_M = 1.0


def face_front_mouth(axis: LineString, inward: XY, plan, half: float
                     ) -> "tuple[LineString, float]":
    """``(axis, metres moved into the bore)``: the mouth moved to the FRONT
    of an entrance face's top ``plan`` -- the least station, along
    ``inward`` from the mouth, of the plan inside the corridor (``half``
    either side of the axis).  Negative: the face stands out of the mapped
    end and the axis is cut back to it; positive: the mapped end stops
    short of the face and the axis runs on to it."""
    m = axis.coords[0]
    span = 4.0 * (axis.length + 1000.0)
    strip = LineString([(m[0] - inward[0] * span, m[1] - inward[1] * span),
                        (m[0] + inward[0] * span, m[1] + inward[1] * span)]
                       ).buffer(half, cap_style="flat")
    got = plan.intersection(strip)
    pts = [q for g in getattr(got, "geoms", [got]) if hasattr(g, "exterior")
           for q in g.exterior.coords] if not got.is_empty else []
    if not pts:
        return axis, 0.0
    d = min((q[0] - m[0]) * inward[0] + (q[1] - m[1]) * inward[1] for q in pts)
    if d > 0.0:
        new = (m[0] + inward[0] * d, m[1] + inward[1] * d)
        return LineString([new] + list(axis.coords)), float(d)
    if -d <= 1e-6 or -d >= axis.length - 1e-6:
        return axis, 0.0
    return substring(axis, -d, axis.length), float(d)


def _bank_width(core, top_z: float, dem_z: _t.Callable[[float, float], float],
               slope: float, cap_m: float) -> float:
    """The bank's plan width: the largest |top - DEM| round ``core``'s
    rings over ``slope``, at most ``cap_m``."""
    worst = 0.0
    for g in getattr(core, "geoms", [core]):
        ring = g.exterior
        n = max(4, int(math.ceil(ring.length / _RING_STEP_M)))
        for k in range(n):
            p = ring.interpolate(k * ring.length / n)
            z = float(dem_z(p.x, p.y))
            if not math.isnan(z):
                worst = max(worst, abs(top_z - z))
    return min(cap_m, worst / slope) if slope > 0.0 else 0.0


def _skirt_cells(plan, ramp, blocked, stand_off: float, band: float, bank: float):
    """``(core, bank)``: the skirt's level piece -- the face's top ``plan``
    and the ground within ``band`` of it -- and the bank ``bank`` wide round
    it, each clear of the ramp by ``stand_off`` (its own wall) and of
    ``blocked`` (the airside pavement); either may be empty."""
    keep_off = ramp.buffer(stand_off, **_MITRE)
    if blocked is not None and not blocked.is_empty:
        keep_off = unary_union([keep_off, blocked])
    core = unary_union([plan, plan.buffer(band, **_MITRE)]).difference(keep_off)
    if core.is_empty or bank <= 0.0:
        return core, core.difference(core)
    return core, core.buffer(bank, **_MITRE).difference(core).difference(keep_off)


def is_entrance_face(pin) -> bool:
    """``pin`` is an ENTRANCE face seated on its floor with a top plan
    (``trench_objects.mouth_portals``) -- the pins this module reads."""
    return (pin is not None and getattr(pin, "bottom_y", None) is not None
            and getattr(pin, "face_plan", None) is not None
            and getattr(pin, "face_top_z", None) is not None)


def entrance_skirt(pin, ramp, cells, polys, law, dem_z, stand_off: float):
    """``(core, bank, top z)`` of an entrance ``pin``'s skirt round the
    tunnel's ``ramp`` (module doc), or ``None``: the AIRSIDE ``cells``
    (``polys`` their plans) are kept out of it."""
    if not is_entrance_face(pin):
        return None
    ob = law.tables.structures.tunnel.object
    band, cap = float(ob.entrance_skirt_m), float(ob.entrance_bank_max_m)
    slope = float(law.tables.emit.design.bank_slope)
    plan, top = pin.face_plan, float(pin.face_top_z)
    reach = plan.buffer(band + cap)
    blocked = unary_union([p for c, p in zip(cells, polys, strict=False)
                           if c.side == "airside" and p.intersects(reach)])
    core, _ = _skirt_cells(plan, ramp, blocked, stand_off, band, 0.0)
    if core.is_empty:
        return None
    width = _bank_width(core, top, dem_z, slope, cap)
    core, bank = _skirt_cells(plan, ramp, blocked, stand_off, band, width)
    return core, bank, top


def skirt_refs(tid: str) -> tuple[str, str]:
    """The refs of a tunnel's skirt faces: its level piece and its bank."""
    return f"entrance_skirt:{tid}", f"entrance_bank:{tid}"
