"""THE UPPER FORECOURT OF A SPLIT-LEVEL BUILDING (#1934 R6; owner RULINGS
2026-11-17h (5), KLAX 13:07Z: the paved area beside Terminal 8 "is
relatively flat and grades between the two buildings there closer to
taxiway/apron level.  It's at the floor of the upper story of the split
level building"; 2026-11-13w (2): every wall bottom on terrain, the upper
storey's on the upper ground; 2026-11-16s: grade from the pack, the lidar
confirms at most).

``airport/split_level`` reads each run of a split-level building's outline
at the foot of its walls.  A wall footed on the UPPER floor stands on the
upper ground -- outside it too.  A mapped surface car park in front of
those walls is that ground: it lies at the upper floor, flat (the apron
grade law), not on the bare-earth survey a storey below (KLAX: the lidar
reads the lot 2.5 m under the wall foot; bare earth also strips the decks
and kerbs a lot is built on).

THE WITNESS IS THE WALL AND THE MAP.  A car park ``L`` (an OSM
``amenity=parking`` surface way, ``classify/evidence.parking_polys``) is
the upper storey's when an upper-footed run stands within ``reach`` of it
and no lower-footed run within ``back`` (the pit's back cut,
``[building_pad] split_level_back_cut_m``): a lot the lower storey's
walls stand on is the lower ground's, and keeps the survey (KLAX: the lot
north of Terminal 8's concourse meets the block's lower walls -- the owner's
"lower lot").  Its FORECOURT is the convex hull of ``L`` and those upper
runs (the ground between the wall and the lot is the same paved ground),
and a car park touching an admitted one, itself clear of the lower walls,
joins it (one paved area).  The caller takes out what is not bare ground
(every classified cell, the pits, the plan).

Pure geometry: no law constant lives here; nothing names a pack, a
resource or an airport."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..geom.parts import polygon_parts_with_area

__all__ = ["upper_forecourt"]

#: two car parks closer than this are one paved area (a shared edge the map
#: draws twice, never a gap a strip of ground fills)
_TOUCH_M = 1.0


def upper_forecourt(upper: _t.Sequence[LineString], lower: _t.Sequence[LineString],
                    lots: _t.Sequence[Polygon], reach: float, back: float,
                    clear=None) -> "Polygon | None":
    """The ground held at the upper floor in front of a split-level
    building's ``upper`` runs (module docstring), less ``clear``; ``None``
    when no car park fronts them.  ``lower`` are the runs at the lowest
    level; ``reach`` how far a wall fronts a lot, ``back`` how far the
    lower walls' ground reaches."""
    if not upper or not lots or reach <= 0.0:
        return None
    low = unary_union(list(lower)) if lower else None
    free = [i for i, lot in enumerate(lots)
            if low is None or low.is_empty or lot.distance(low) > back]
    pieces: list = []
    taken: set[int] = set()
    for i in free:
        up = [r for r in upper if r.distance(lots[i]) <= reach]
        if up:
            pieces.append(unary_union([lots[i], *up]).convex_hull)
            taken.add(i)
    if not pieces:
        return None
    # one paved area: a car park touching an admitted one joins it
    grown = True
    while grown:
        area = unary_union(pieces)
        more = [i for i in free if i not in taken and lots[i].distance(area) <= _TOUCH_M]
        pieces.extend(lots[i] for i in more)
        taken.update(more)
        grown = bool(more)
    court = unary_union(pieces).buffer(0)
    if clear is not None and not clear.is_empty:
        court = court.difference(clear).buffer(0)
    parts = polygon_parts_with_area(court)
    return unary_union(parts).buffer(0) if parts else None
