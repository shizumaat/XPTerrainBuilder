"""A FRONTAGE ROAD OVER A TWO-FLOOR BLOCK IS ON ITS LEVEL (RULINGS
2026-11-25g (3); spec ``docs/specs/terminal-frontage-split-level-20261125.md``
§3.2, step 3, lane lfront3).

A unit standing on two floors has its groundside at a level ``G`` a storey
off its airside floor; the held block is split into its airside block and
that level (``planar/low_level``: ``plan_low`` with the unit's held record
a storey down, ``plan_up`` where its landside lot meets it a storey up).
The level is read off the unit's parts (or the lot), and a road is no part
of the object: a mapped road that enters the building on its groundside
crossed a strip of the airside block between the pad's edge and the
level, and stepped a storey there twice.  MEASURED on the 1.0.583
integration gate: LDSP road ``-572`` 4.23 m (block ``building1`` at
18.77 m for 8 m between its lower level at 13.07 m and the road).

THE RULE (:func:`frontage_roads`): the mapped roads' carriageways over the
pad (``airport/road_ways.road_corridors``, the ``_with_roads`` corridor of
#1291) are one
network (a road mapped as two ways, one ending inside the pad, is one
road); each of its pieces off the level that LEAVES THE PAD on its
groundside -- where the pad's edge stands off the airside by more than
``pad_frontage_m`` -- and either meets the level or stays that far off the
airside itself (a road crossing a groundside arm of the block: MEASURED
LDSP ``-477`` / ``-478``, 5.8 m over an 8 m arm of ``building1``) is the
level's, whole, at any size (``level_cut`` keeps it under the unit pad's
least area; the arm it cuts off the airside is the level's orphan).  A
piece that leaves only toward the airside, or never leaves the pad, stays
the block's (#1291's "a road that merely touches the lower level and runs
on over the block never carries the low level with it").  Applied only
where the level IS a two-floor unit's groundside floor: ``plan_low`` with
the unit's held record (``frontage``), ``plan_up`` (the storey lot's)."""
from __future__ import annotations

from shapely.ops import unary_union

from ..airport.road_ways import road_corridors
from ..geom.parts import nonempty_polygon_parts
from ..geom.valid_area import valid_area

__all__ = ["frontage_roads"]


def frontage_roads(L, P, air, airport, law, near: float, riser: float) -> list:
    """The frontage road pieces over the pad ``P`` (module docstring): each
    piece of the mapped carriageway network over ``P`` off the level ``L``
    that leaves the pad on its groundside edge -- where the pad's edge
    stands off the airside ``air`` by more than ``near`` (``[design]
    pad_frontage_m``) -- and either meets the level or stays that far off
    the airside itself (a road crossing a groundside arm of the block);
    ``riser`` the riser strip's width."""
    if L.is_empty or air is None:
        return []
    edge = P.boundary.difference(air.buffer(near, join_style=2))
    cors = road_corridors(P, airport, law)
    if edge.is_empty or not cors:
        return []
    # ONE carriageway network: a road mapped as consecutive ways (a way
    # ending inside the pad, the next carrying on) is one road to the edge
    C = valid_area(unary_union([c for c, _w in cors]))
    out = []
    for q in nonempty_polygon_parts(valid_area(C.intersection(P)).difference(L)):
        if q.distance(edge) > riser or (q.distance(L) > riser
                                        and q.distance(air) <= near + riser):
            continue
        if edge.intersection(q.buffer(riser)).difference(L.buffer(riser)).length > riser:
            out.append(q)
    return out
