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

from ..airport.portal_objects import _station
from ..model.frame import XY
from .mouth_opening import axis_left_normal

__all__ = ["face_front_mouth", "is_entrance_face", "entrance_skirt", "entrance_top",
           "host_blade", "skirt_refs"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)
#: plan samples along the skirt's ring for the bank width (metres)
_RING_STEP_M = 1.0
#: line spacing across the ramp for the face's front, and the inset from
#: the ramp's edges (a face's side wall standing on an edge is no front)
_FRONT_STEP_M = 0.5
_EDGE_INSET_M = 0.25


def face_front_mouth(axis: LineString, inward: XY, plan, half
                     ) -> "tuple[LineString, float]":
    """``(axis, metres moved into the bore)``: the mouth moved to the FRONT
    of an entrance face's top ``plan`` where it stands DEEPEST across the
    ramp -- per line along ``inward`` at each offset across the corridor
    (``half``: one half width either side of the axis, or its ``(left,
    right)`` pair, ``mouth_opening.opening_halves``), the least station of
    the plan on it; the mouth is the greatest of those, so the ramp's floor
    meets the face's bottom across its whole width (#1917: a face skewed
    across the bore -- LOWS west, 1.8 m over its 20.5 m opening -- reached
    at its nearest corner left the cut ground standing in front of the rest
    of it; where the face stands nearer, the floor runs on behind its
    front).  Negative: the face stands out of the mapped end and the axis is
    cut back to it; positive: the mapped end stops short of the face and the
    axis runs on to it."""
    m = axis.coords[0]
    d = _deepest_front(m, inward, plan, half, axis_left_normal(axis),
                       4.0 * (axis.length + 1000.0))
    if d is None:
        return axis, 0.0
    if d > 0.0:
        new = (m[0] + inward[0] * d, m[1] + inward[1] * d)
        return LineString([new] + list(axis.coords)), float(d)
    if -d <= 1e-6 or -d >= axis.length - 1e-6:
        return axis, 0.0
    return substring(axis, -d, axis.length), float(d)


def _line_stations(m: XY, inward: XY, plan, half, nv: XY, reach: float):
    """``(least, greatest)`` station from ``m`` of ``plan`` on each line
    along ``inward`` across the corridor (``half`` either side of ``m``, or
    ``(left, right)`` along ``nv``; inset ``_EDGE_INSET_M``, every
    ``_FRONT_STEP_M``) that meets it."""
    left, right = (half, half) if isinstance(half, (int, float)) else half
    lo, hi = -float(right) + _EDGE_INSET_M, float(left) - _EDGE_INSET_M
    n = max(1, int(math.ceil((hi - lo) / _FRONT_STEP_M))) if hi > lo else 0
    for k in range(n + 1):
        o = lo + (hi - lo) * k / n if n else 0.0
        c = (m[0] + nv[0] * o, m[1] + nv[1] * o)
        got = plan.intersection(LineString([(c[0] - inward[0] * reach, c[1] - inward[1] * reach),
                                            (c[0] + inward[0] * reach, c[1] + inward[1] * reach)]))
        if got.is_empty:
            continue
        s = [(q[0] - m[0]) * inward[0] + (q[1] - m[1]) * inward[1]
             for g in getattr(got, "geoms", [got]) for q in g.coords]
        yield min(s), max(s)


def _deepest_front(m: XY, inward: XY, plan, half, nv: XY, reach: float) -> "float | None":
    """The greatest, over lines along ``inward`` across the corridor
    (``half`` either side of ``m``, or ``(left, right)`` along ``nv``), of
    the least station from ``m`` of ``plan`` on each line; ``None`` where
    no line meets it."""
    fronts = [lo for lo, _hi in _line_stations(m, inward, plan, half, nv, reach)]
    return max(fronts) if fronts else None


def _cover_back(m: XY, inward: XY, plan, half, nv: XY, reach: float) -> "float | None":
    """A cover's BACK across the ramp (#1689 R5 M1): the least, over the
    lines :func:`_deepest_front` samples, of the GREATEST station from
    ``m`` of ``plan`` on each -- the cap standing within it stands under
    the cover on every line; ``None`` where no line meets it."""
    backs = [hi for _lo, hi in _line_stations(m, inward, plan, half, nv, reach)]
    return min(backs) if backs else None


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


def _states_top(pin) -> bool:
    """``pin`` states a TOP plan and level its skirt is graded to: an
    ENTRANCE face (:func:`is_entrance_face`) or a TALL roofed portal (its
    roof at the cover on it, no bottom; #1689 R2 A3)."""
    return (pin is not None and getattr(pin, "face_plan", None) is not None
            and getattr(pin, "face_top_z", None) is not None)


def _swept(geom, d: XY):
    """``geom``'s plan swept along the vector ``d``: the plan, its
    translate and each ring edge's parallelogram (exact, never a hull)."""
    from shapely.affinity import translate
    from shapely.geometry import Polygon
    out = [geom, translate(geom, d[0], d[1])]
    for g in getattr(geom, "geoms", [geom]):
        if g.geom_type != "Polygon":
            continue
        for ring in [g.exterior, *g.interiors]:
            c = list(ring.coords)
            for a, b in zip(c, c[1:], strict=False):
                q = Polygon([a, b, (b[0] + d[0], b[1] + d[1]), (a[0] + d[0], a[1] + d[1])])
                if q.area > 0.0:
                    out.append(q.buffer(0))
    return unary_union(out)


def _half_plane(geom, end_xy: XY, into: XY, front: float, off: float):
    """The half plane (a box over ``geom``'s reach) into the bore from the
    line across it at station ``front + off`` (``off > 0``), or out of it
    from ``front + off`` (``off < 0``)."""
    from shapely.geometry import Polygon
    b = geom.bounds
    big = 2.0 * (math.hypot(b[2] - b[0], b[3] - b[1]) + abs(front) + abs(off)
                 + math.hypot(end_xy[0] - b[0], end_xy[1] - b[1])) + 1.0
    s0, s1 = (front + off, front + off + big) if off > 0.0 else (front + off - big, front + off)
    nx, ny = -into[1], into[0]
    return Polygon([(end_xy[0] + into[0] * s + nx * o, end_xy[1] + into[1] * s + ny * o)
                    for s, o in ((s0, -big), (s1, -big), (s1, big), (s0, big))])


def entrance_skirt(pin, ramp, cells, polys, law, dem_z, stand_off: float,
                   hosts: _t.AbstractSet[str] = frozenset(), outward: "XY | None" = None):
    """``(core, bank, top z)`` of a top-stating ``pin``'s skirt round the
    tunnel's ``ramp`` (module doc), or ``None``: the AIRSIDE ``cells``
    (``polys`` their plans) are kept out of it.  A roofed portal's skirt
    (#1689 R2 A4: no bottom) keeps off every ROAD cell and every building
    pad but its own ``hosts`` too, each by ``stand_off`` -- the mapped
    road behind the portal and the next pad keep their own law; an
    entrance face's skirt reads as before.

    #1689 R4 W2: given ``outward`` (the unit vector out of the bore), a
    roofed portal's skirt keeps off the CORRIDOR out of its mouth too --
    the ramp's plan swept along ``outward`` across the reach, grown by
    ``stand_off`` -- level piece and bank alike: the road leaving the
    mouth is never skirt.

    #1689 R5 S1 / S2: a pin with a COVER (``Portal.cover_plan``) keeps
    off the ground in front of its parapet too (swept along ``outward``,
    not grown), and its level piece stands at the cover's top; where
    wings run out beyond the cover's front, the piece out of the bore from
    the line across it there is theirs, at the portal's top, a strip
    ``min_distinct_spacing_m`` wide astride the line in neither (it goes
    with the bank): ``(cover's piece, bank, cover top, wings' piece,
    wings' top)``."""
    if not _states_top(pin):
        return None
    ob = law.tables.structures.tunnel.object
    band, cap = float(ob.entrance_skirt_m), float(ob.entrance_bank_max_m)
    slope = float(law.tables.emit.design.bank_slope)
    plan, top = pin.face_plan, float(pin.face_top_z)
    reach = plan.buffer(band + cap)
    blocked = unary_union([p for c, p in zip(cells, polys, strict=False)
                           if c.side == "airside" and p.intersects(reach)])
    if not is_entrance_face(pin):
        from ..model.planar import ROAD_ROLES
        held = [p.buffer(stand_off, **_MITRE) for c, p in zip(cells, polys, strict=False)
                if (c.role in ROAD_ROLES or (c.role == "building" and c.ref not in hosts))
                and p.intersects(reach)]
        b = reach.bounds
        far = math.hypot(b[2] - b[0], b[3] - b[1])
        if outward is not None and not ramp.is_empty:
            held.append(_swept(ramp, (outward[0] * far, outward[1] * far)).buffer(
                stand_off, **_MITRE))
        para = getattr(pin, "parapet_plan", None)
        if outward is not None and para is not None and not para.is_empty:
            # #1689 R5 S1: nor the ground in front of a wall rising over the cover
            held.append(_swept(para, (outward[0] * far, outward[1] * far)))
        if held:
            blocked = unary_union([blocked, *held])
    core, _ = _skirt_cells(plan, ramp, blocked, stand_off, band, 0.0)
    if core.is_empty:
        return None
    width = _bank_width(core, top, dem_z, slope, cap)
    core, bank = _skirt_cells(plan, ramp, blocked, stand_off, band, width)
    cover = getattr(pin, "cover_plan", None)
    if cover is None or cover.is_empty:
        return core, bank, top
    # #1689 R5 S2: the ground round the COVER is the cover's top; where
    # wings stand at the portal's top beyond its front, theirs is that top
    level = float(pin.cover_top_z)
    if not plan.difference(cover).area > 1e-6:
        return core, bank, level
    if outward is None:
        return core, bank, top
    into = (-outward[0], -outward[1])
    front = min(_station(q, pin.end_xy, into) for g in getattr(cover, "geoms", [cover])
                for q in g.exterior.coords)
    gap = float(law.tables.emit.identity.min_distinct_spacing_m)
    inner, outer = (core.intersection(_half_plane(core, pin.end_xy, into, front, k * 0.5 * gap))
                    for k in (1.0, -1.0))
    strip = core.difference(unary_union([inner, outer]))
    return inner, unary_union([bank, strip]), level, outer, top


def host_blade(pin, outer, skirt_parts, law):
    """The blade a pinned ramp cuts its HOST pads with: its footprint
    ``outer`` -- and for a TALL roofed portal (:func:`_states_top`, no
    bottom; #1689 R2 A5 / R3) the portal object's OWN FOOTPRINT (its
    solids' plan, ``Portal.footprint``; its top plan where it has none)
    grown by ``entrance_skirt_m``, and its skirt and bank (``skirt_parts``)
    too: the host pad is the portal frame's own footprint read as a
    building, and held at the pad's level its remnants stood 1.9-2.6 m
    over the roof (KBNA P1 ``building5``); cut by the top plan alone, the
    remnants over the wings held the ramp's top 2.2 m up."""
    if not _states_top(pin) or is_entrance_face(pin):
        return outer
    band = float(law.tables.structures.tunnel.object.entrance_skirt_m)
    foot = getattr(pin, "footprint", None)
    plan = pin.face_plan if foot is None or foot.is_empty else foot.union(pin.face_plan)
    return unary_union([outer, plan.buffer(band, **_MITRE), *skirt_parts])


def skirt_refs(tid: str) -> tuple[str, str, str]:
    """The refs of a tunnel's skirt faces: its level piece, its bank and
    its wings' level piece (#1689 R5 S2)."""
    return f"entrance_skirt:{tid}", f"entrance_bank:{tid}", f"entrance_wing:{tid}"


def entrance_top(pin) -> tuple:
    """``Tunnel.entrance_top`` of an entrance ``pin`` (#1737): ``(its top
    plan's exterior rings, top y, top y - bottom y)`` -- the top y over the
    object's zero, read back from the seat its cover set (``trench_objects.
    mouth_portals``: zero = floor - bottom, top = cover - zero) -- or ``()``
    with no top plan."""
    plan = getattr(pin, "top_plan", None)
    top_z, bottom = getattr(pin, "face_top_z", None), getattr(pin, "bottom_y", None)
    floor = getattr(pin, "floor_z", None)
    if plan is None or plan.is_empty or None in (top_z, bottom, floor):
        return ()
    top_y = float(top_z) - (float(floor) - float(bottom))
    rings = tuple(tuple((float(x), float(y)) for x, y in g.exterior.coords)
                  for g in getattr(plan, "geoms", [plan]) if not g.is_empty)
    return (rings, top_y, top_y - float(bottom)) if rings else ()
