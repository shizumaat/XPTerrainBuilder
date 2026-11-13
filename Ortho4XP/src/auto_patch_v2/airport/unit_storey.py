"""THE UPPER STOREY OF A PACK UNIT (#1101 / #1099; owner answer 47,
2026-10-20: "yes to both" — the mirror of the lower level, RULINGS
2026-10-19ai, #809; spec ``docs/specs/low-level-pad-spec.md`` §5).

A terminal cut into a hill stands with its airside floor on the apron and
its landside one storey up.  The OBJECT says so: the unit's parts at the
apron are authored at its floor ``t``, its landside parts — the forecourt
parapet, the kerb columns, the landside hall — a storey higher.  MEASURED
LPHR (38.521557, −28.716632): the terminal unit's grounded parts stand at
y 0; a 68 m x 1 m parapet (``lphr_tps_06``) runs at y +6.0 exactly along
the forecourt's 68 m contact with the apron, and the landside hall and its
columns stand at +6.0 too.

THE FLOOR.  ``t`` is the base most of the unit's GROUNDED parts (a part
with its own ground feet, ``Part.feet``) within ``pad_frontage_m`` of
airside pavement stand at — the floor the apron meets.  A part the plan
judged elevated (a canopy, a roof, the parapet itself) never sets it.

THE UPPER STOREY.  The unit's parts authored at least ``[building_pad]
low_level_min_step_m`` (one storey) above ``t``.  Their plan footprints
are the storey's witness on the map: ``classify/airside_edge`` reads a
lot's contact with the apron ALONG them as a contact across the storey —
no apron contact (§27 amended).

THE UPPER PAD (RULINGS 2026-11-13aa (1), #2068; spec
``docs/specs/2068-upper-pad-spec.md`` §1): a pad whose every part of the
unit stands a storey over its floor, with a walled part at the lowest of
those bases covering a share of it, over ground that stands that storey
over the airside the floor meets (:func:`upper_pads`) — the pad under a
unit's upper storey (a tower on a hill behind its terminal).  Doubt
refuses (13r).

It lives in ``airport`` because ``classify`` reads it before any pad
exists and ``planar`` reads the same floor rule inside a pad."""
from __future__ import annotations

import dataclasses as _dc
import statistics as _st
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

__all__ = ["Storey", "UpperPad", "dem_samples", "part_footprint", "unit_floor", "upper_pads",
           "upper_storeys"]


@_dc.dataclass(frozen=True)
class Storey:
    """One unit's upper storey: the unit's index in ``airport.partition``,
    its airside floor ``floor_y`` (authored), its upper parts and the union
    of their plan footprints (the engine's xy frame)."""

    unit: int
    floor_y: float
    parts: tuple
    footprint: _t.Any


@_dc.dataclass(frozen=True)
class UpperPad:
    """One pad under a unit's upper storey (:func:`upper_pads`): the pad's
    ref and plan, the unit, its floor ``floor_y`` and the storey's base
    ``y`` (authored), the walled-plane cover of the pad, the ground step
    ``delta`` (pad DEM median less the floor's airside), the pad's DEM
    ``relief`` and whether a pack wall/fence of the unit retains it
    (recorded only, spec §1 (5))."""

    ref: str
    polygon: _t.Any
    unit: int
    floor_y: float
    y: float
    cover: float
    walled: int
    delta: float
    relief: float
    fence: bool

    @property
    def rise(self) -> float:
        return self.y - self.floor_y


def dem_samples(dem, g, step: float = 2.0) -> list:
    """The DEM over ``g`` on a ``step`` grid (at most ~400 samples)."""
    import math

    from shapely.geometry import Point
    if dem is None or g is None or g.is_empty:
        return []
    x0, y0, x1, y1 = g.bounds
    h = max(step, math.sqrt(max(g.area, 1.0) / 400.0))
    zs = []
    y = y0 + 0.5 * h
    while y < y1:
        x = x0 + 0.5 * h
        while x < x1:
            if g.contains(Point(x, y)):
                try:
                    z = float(dem.z(x, y))
                except Exception:  # noqa: BLE001 -- off the raster
                    z = float("nan")
                if z == z:
                    zs.append(z)
            x += h
        y += h
    return zs


def part_footprint(p, to_xy) -> "Polygon | None":
    """The plan footprint of one pack part (the union of its rings), or
    ``None`` where it carries no ring of three vertices."""
    gs = []
    for rg in getattr(p, "rings", ()) or ():
        if len(rg) < 3:
            continue
        g = Polygon([to_xy(lon, lat) for lat, lon in rg])
        g = g if g.is_valid else g.buffer(0.0)
        if not g.is_empty:
            gs.append(g)
    return unary_union(gs) if gs else None


def unit_floor(parts, near, to_xy) -> "float | None":
    """THE AIRSIDE FLOOR of a unit (module docstring): the base most of its
    GROUNDED ``parts`` whose footprint meets ``near`` stand at (the lowest
    of a tie), or ``None`` where no grounded part meets it."""
    ys = [p.base_y for p in parts if getattr(p, "feet", ())
          and (g := part_footprint(p, to_xy)) is not None and g.intersects(near)]
    return float(min(_st.multimode(round(y) for y in ys))) if ys else None


def _solid(u) -> list:
    return [p for m in u.members for p in m.parts
            if not getattr(p, "line", False) and not getattr(p, "scatter", False)]


def upper_storeys(airport, law, air) -> list[Storey]:
    """Every pack unit of ``airport`` that stands at airside pavement
    ``air`` (one geometry, the engine's frame) and carries parts a storey
    above its airside floor (module docstring)."""
    part = getattr(airport, "partition", None)
    frame = getattr(airport, "frame", None)
    if part is None or frame is None or air is None or air.is_empty:
        return []
    step = float(getattr(law.tables.structures.building_pad,
                         "low_level_min_step_m", 0.0) or 0.0)
    if step <= 0.0:
        return []
    from ..law.tables import design as design_law
    near = air.buffer(float(design_law(law).pad_frontage_m))
    to_xy = frame.entry()
    out: list[Storey] = []
    for ui, u in enumerate(part.units):
        parts = _solid(u)
        t = unit_floor(parts, near, to_xy)
        if t is None:
            continue
        up = [p for p in parts if p.base_y >= t + step]
        polys = [g for p in up if (g := part_footprint(p, to_xy)) is not None]
        if polys:
            out.append(Storey(ui, t, tuple(up), unary_union(polys)))
    return out



@_dc.dataclass(frozen=True)
class _UnitRead:
    """One unit as :func:`upper_pads` reads it: its solid parts with their
    footprints, its floor ``t`` and the union of its footprints' boxes."""

    ui: int
    unit: _t.Any
    parts: tuple
    t: float
    bounds: tuple


def _unit_reads(part, near, to_xy) -> list:
    out = []
    for ui, u in enumerate(part.units):
        parts = _solid(u)
        t = unit_floor(parts, near, to_xy)
        if t is None:
            continue
        pg = tuple((p, g) for p in parts if (g := part_footprint(p, to_xy)) is not None
                   and g.area > 0.0)
        if pg:
            bx = [g.bounds for _p, g in pg]
            out.append(_UnitRead(ui, u, pg, float(t),
                                 (min(b[0] for b in bx), min(b[1] for b in bx),
                                  max(b[2] for b in bx), max(b[3] for b in bx))))
    return out


def _upper_pad(ref, P, ur: _UnitRead, near, air, dem, law, to_xy) -> "UpperPad | None":
    """:func:`upper_pads` for one pad ``P`` and one unit, or ``None``."""
    from ..geom.foot_planes import PLANE_SHARE
    from .split_level import BAND_M
    t = ur.t
    step = float(law.tables.structures.building_pad.low_level_min_step_m)
    wall = float(law.tables.structures.placement.chain_min_height_m)
    on = [(p, g) for p, g in ur.parts if g.intersects(P)
          and g.intersection(P).area >= 0.5 * g.area]
    if not on or any(p.base_y < t + step for p, _g in on):
        return None                                       # (1)-(2)
    y_p = min(p.base_y for p, _g in on)
    plane = [(p, g) for p, g in on if p.base_y <= y_p + BAND_M]
    cover = unary_union([g for _p, g in plane]).intersection(P).area / P.area
    walled = sum(1 for p, _g in plane if float(getattr(p, "height_m", 0.0) or 0.0) >= wall)
    if cover < PLANE_SHARE or walled < 1:
        return None                                       # (3)
    rise = y_p - t
    floor = [g for p, g in ur.parts if getattr(p, "feet", ()) and round(p.base_y) == t
             and g.intersects(near)]
    zp = dem_samples(dem, P)
    za = dem_samples(dem, air.intersection(unary_union(floor).buffer(near_m(law))))
    if not zp or not za:
        return None                                       # (4): no ground
    delta, relief = _st.median(zp) - _st.median(za), max(zp) - min(zp)
    if not (0.5 * rise <= delta <= 1.5 * rise) or relief >= rise:
        return None
    reach = P.buffer(near_m(law))
    fence = any(getattr(p, "line", False) and p.base_y <= y_p - 0.5 * rise
                and p.base_y + float(getattr(p, "height_m", 0.0) or 0.0) >= y_p - BAND_M
                and (g := part_footprint(p, to_xy)) is not None and g.intersects(reach)
                for m in ur.unit.members for p in m.parts)
    return UpperPad(str(ref), P, ur.ui, t, float(y_p), round(cover, 3), walled,
                    round(delta, 2), round(relief, 2), fence)


def near_m(law) -> float:
    """``[design] pad_frontage_m``."""
    from ..law.tables import design as design_law
    return float(design_law(law).pad_frontage_m)


def upper_pads(airport, law, air, pads) -> list[UpperPad]:
    """THE UPPER PADS (module docstring; spec 2068 §1 (1)-(5)) among
    ``pads`` (``(ref, polygon)``, the engine's frame), read against the
    airside pavement ``air``: a pad is under unit ``u``'s upper storey when
    ``u`` has a floor ``t``; every solid part of ``u`` with half its plan
    on the pad stands at least ``low_level_min_step_m`` over ``t``; the
    parts within ``split_level.BAND_M`` of the lowest of those bases
    ``y_p`` cover ``PLANE_SHARE`` of the pad and one is walled; and the
    ground confirms both sides — the pad's DEM median stands half to one
    and a half rises over the median of the airside within
    ``pad_frontage_m`` of the floor's parts, and the pad's own relief is
    under the rise.  No DEM refuses."""
    part = getattr(airport, "partition", None)
    frame = getattr(airport, "frame", None)
    dem = getattr(airport, "dem", None)
    if part is None or frame is None or dem is None or air is None or air.is_empty:
        return []
    near = air.buffer(near_m(law))
    to_xy = frame.entry()
    units = None
    out: list[UpperPad] = []
    for ref, P in pads:
        if P is None or P.is_empty or P.area <= 0.0:
            continue
        units = _unit_reads(part, near, to_xy) if units is None else units
        x0, y0, x1, y1 = P.bounds
        for ur in units:
            b = ur.bounds
            if b[0] > x1 or b[2] < x0 or b[1] > y1 or b[3] < y0:
                continue
            got = _upper_pad(ref, P, ur, near, air, dem, law, to_xy)
            if got is not None:
                out.append(got)
                break
    return out
