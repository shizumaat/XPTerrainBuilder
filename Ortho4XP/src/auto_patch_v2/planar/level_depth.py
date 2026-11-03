"""THE AIRPORT'S LEVEL B — the depth of its one lower level (owner RULINGS
2026-11-03b Q342 a / Q344 a; the master's reading of 11-03b's "one lower level
(B)", approved 2026-11-03; spec ``docs/specs/two-level-regions-20261103.md``
§3 and §13).

An airport has a graded airside level A and ONE lower level B.  Where the
pack's own objects state how deep B lies -- the lower storey of a two-level
building, read as the walled feet a storey under the stand-side floor
(``low_level.feet_levels``, RULINGS 2026-10-23b) -- that depth is the
airport's.  A lower region with no object of its own (the road under a
runway deck that states no floor) takes it before the ladder's defaults.
MEASURED LFPG (capture lfpg6): the T2 buildings' lower storeys at 7.03-7.44 m
under their floors; the owner's hand patch holds 7 m under the A1 decks.

:func:`airport_level_b` is the ONE reading: the median of every unit's
storey depth, weighted by the unit's walled feet, over the units whose feet
read a lower storey at least ``[building_pad] low_level_min_step_m`` down.
It reads the pack partition and the classification's airside cells only, so
it stands before the structures pass (the spec's probe P1).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law.tables import role_side

__all__ = ["airport_level_b"]


def airport_level_b(airport, classification, law) -> "tuple[float | None, str]":
    """``(depth_m, note)``: the airport's level-B depth under level A
    (module docstring), or ``(None, why)`` where no unit states one."""
    from .low_level import _stands_xy, feet_levels, walled_feet
    part = getattr(airport, "partition", None)
    if part is None or classification is None or not classification.cells:
        return None, "no pack partition"
    step_min = float(law.tables.structures.building_pad.low_level_min_step_m)
    air = [Polygon(c.ring, c.holes) for c in classification.cells
           if len(c.ring) >= 3 and role_side(law, c.role) == "airside"]
    air = [p if p.is_valid else p.buffer(0.0) for p in air]
    if not air:
        return None, "no airside cells"
    tree = STRtree(air)
    to_xy = airport.frame.entry()
    stands = _stands_xy(airport, to_xy)
    if not stands:
        return None, "no stands to read a floor at"
    pairs: list[tuple[float, int]] = []
    for u in part.units:
        parts = [(p, to_xy(p.lon, p.lat)) for m in u.members for p in m.parts
                 if not getattr(p, "line", False)]
        xy, _ys = walled_feet(parts, law, to_xy)
        if not xy:
            continue
        xs, ys = [a for a, _b in xy], [b for _a, b in xy]
        near = [air[int(j)] for j in tree.query(box(min(xs), min(ys), max(xs), max(ys))
                                                .buffer(50.0))]
        if not near:
            continue
        lv = feet_levels(parts, unary_union(near), stands, law, to_xy)
        if lv is None or lv[1] is None or lv[0] - lv[1] < step_min:
            continue
        pairs.append((float(lv[0] - lv[1]), len(xy)))
    if not pairs:
        return None, "no unit's feet read a lower storey"
    depth = _weighted_median(pairs)
    return round(depth, 3), (f"{len(pairs)} unit(s) read a lower storey; the airport's "
                             f"level B stands {depth:.2f} m under level A (RULINGS 2026-11-03b)")


def _weighted_median(pairs: _t.Sequence[tuple[float, int]]) -> float:
    """The median of ``(value, weight)`` pairs."""
    s = sorted(pairs)
    half = 0.5 * sum(w for _v, w in s)
    acc = 0.0
    for v, w in s:
        acc += w
        if acc >= half:
            return v
    return s[-1][0]
