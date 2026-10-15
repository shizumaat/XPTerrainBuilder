"""THE THIN PLATES AT THE BASE OF OBJECTS — the components the pack
partition's thickness gate drops, read as base-slab candidates (issue #712;
owner RULINGS 2026-10-10o (B), 2026-10-14d).

The partition keeps a member's GENUINE components only (``obj8.
ResourceCache.genuine``: solid height at least ``thickness_m``), so a paved
plate 0.3 m thick is no part and the base-slab witness (``geom/base_slab``)
never saw it.  MEASURED at HECA (#712, app 1.0.394 at 30.1096365,
31.3889978): ``Seasonal_Terminal/asphalt_3.obj`` component 1 — a 23,716 m2
asphalt plate, y 0.00-0.30 — rides the Seasonal Terminal's unit at 96.53 m;
10,264 m2 of it lies on the unit's pad, 13,236 m2 over ground no face
grades (the pack's draped asphalt page has a hole there: 38 m2 of overlap),
10,372 m2 of that floating more than 0.3 m, worst 5.17 m over the app's
mesh; the lot beside it (``gap:3``) meets its edge 3.0-4.1 m low.

:func:`thin_plates` reads, per member, the components the partition holds
no part for, wherever the member's own base profile (``Member.
base_profile``, the pack read's §1 base planes) names a base plane at the
objects' zero that the member's own parts do not cover — so a floor under a
building's own walls is never re-read, and only a file with such a plane is
parsed.  Each comes back in the witness's own part shape (``comp``,
``base_y``, ``height_m``, ``area_m2``, a lat/lon ``box``, one foot) with
its plan outline in the planar frame (``poly_xy``); the witness then judges
it exactly as it judges a genuine part (rules 1-7).
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

__all__ = ["PlatePart", "thin_plates"]


class PlatePart(_t.NamedTuple):
    """A thin component in the base-slab witness's part shape."""

    comp: int
    base_y: float
    height_m: float
    area_m2: float
    box: tuple[float, float, float, float]
    feet: tuple
    poly_xy: _t.Any
    rings: tuple = ()
    line: bool = False
    scatter: bool = False


def _placed(poly, origin_xy, heading_deg: float, q: float):
    from . import frame_entry as _fe
    from . import obj8 as _obj8
    got = _fe.enter([poly], _obj8.placement_affine(origin_xy, heading_deg), q)
    return got[0] if len(got) else None


def _ll_box(g, origin_ll, origin_xy) -> tuple[float, float, float, float]:
    """A lat/lon box around ``g`` (frame metres) — the witness's plan-box
    PREFILTER only (it keeps too much by design, ``_NEAR_DEG``)."""
    la0, lo0 = origin_ll
    mlat = 110574.0
    mlon = 111320.0 * math.cos(math.radians(la0))
    x0, y0, x1, y1 = g.bounds
    ox, oy = origin_xy
    return (la0 + (y0 - oy) / mlat, lo0 + (x0 - ox) / mlon,
            la0 + (y1 - oy) / mlat, lo0 + (x1 - ox) / mlon)


def _uncovered_plane(m, lw, origin_xy, own, q: float) -> bool:
    """Does the member's base profile name a plane at the objects' zero,
    ``min_m2`` or more, that its own parts leave open?"""
    prof = getattr(m, "base_profile", None) or {}
    for p in prof.get("planes", ()) or ():
        if abs(float(p.get("y", 99.0))) > lw.base_y_max_m or float(p.get("area_m2", 0.0)) < lw.min_m2:
            continue
        try:
            g = _placed(shape(p["polygon"]), origin_xy, float(m.heading_deg or 0.0), q)
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
        if g is None or g.is_empty:
            continue
        open_ = g.difference(own) if own is not None else g
        if open_.area >= lw.min_m2 and open_.area >= lw.open_min_share * g.area:
            return True
    return False


def thin_plates(u, m, to_xy, lw, q: float = 0.0) -> list[PlatePart]:
    """The member's thin plate components (module docstring), ``[]`` where
    its base profile names no uncovered plane at the objects' zero."""
    from .obj8_grade import _plan_union
    from .slab_faces import _components
    path = str(getattr(m, "authored_path", "") or "")
    org = getattr(m, "origin", None) or getattr(u, "anchor", None)
    if not path or org is None:
        return []
    ox, oy = to_xy(float(org[1]), float(org[0]))
    own_rings = []
    for part in m.parts:
        for r in getattr(part, "rings", ()) or ():
            if len(r) >= 3:
                g = Polygon([to_xy(lo, la) for la, lo in r])
                own_rings.append(g if g.is_valid else g.buffer(0.0))
    own = unary_union(own_rings) if own_rings else None
    if not _uncovered_plane(m, lw, (ox, oy), own, q):
        return []
    got = _components(path)
    if got is None:
        return []
    v, comps = got
    have = {int(p.comp) for p in m.parts}
    out: list[PlatePart] = []
    for i, c in enumerate(comps):
        if i in have or getattr(c, "animated", False):
            continue
        y0, h = float(c.min_y), float(c.max_y - c.min_y)
        if abs(y0) > lw.base_y_max_m or h > lw.max_height_m:
            continue
        local = _plan_union(v, c.tris.reshape(-1, 3))
        if local is None or local.is_empty or local.area < lw.min_m2:
            continue
        g = _placed(local, (ox, oy), float(m.heading_deg or 0.0), q)
        if g is None or g.is_empty:
            continue
        box = _ll_box(g, (float(org[0]), float(org[1])), (ox, oy))
        out.append(PlatePart(i, y0, h, float(g.area), box,
                             ((0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3]), y0),), g))
    return out
