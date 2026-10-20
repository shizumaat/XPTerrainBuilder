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

It lives in ``airport`` because ``classify`` reads it before any pad
exists and ``planar`` reads the same floor rule inside a pad."""
from __future__ import annotations

import dataclasses as _dc
import statistics as _st
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

__all__ = ["Storey", "part_footprint", "unit_floor", "upper_storeys"]


@_dc.dataclass(frozen=True)
class Storey:
    """One unit's upper storey: the unit's index in ``airport.partition``,
    its airside floor ``floor_y`` (authored), its upper parts and the union
    of their plan footprints (the engine's xy frame)."""

    unit: int
    floor_y: float
    parts: tuple
    footprint: _t.Any


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
