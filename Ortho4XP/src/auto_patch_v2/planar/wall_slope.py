"""THE WALL SLOPE: THE HILL OVER A RETAINING WALL GRADES TO ITS TOP (issue
#1661; owner RULINGS 2026-10-29a Q299 (a): "the top of a retaining wall,
which the hill grades down to, is the wall object's top edge as it sits.
The grass embankment above it is graded ground, and the back of the wall
is buried").

A retaining wall's upper band (``airport/wall_sides``: ``smear`` wide beside
its upper face) is where the lidar DEM smears the step, so ground left to
the mesh there falls away from the wall's top (KATL ``muro_27R.obj``,
capture on f82de7dfe: 0.2-8.1 m under its top along 479 m).  The band a
runway or taxiway grades stops short of it (spec §3 (2),
``wall_sides.band_setbacks``), and most of it lies past any band at all
(71 % at ``muro_27R``).  So that band is graded ground of its own: one
``graded_strip`` piece per part of it no other region holds, its ref under
``model/wall_reach.WALL_SLOPE_REF_PREFIX`` (a zone region's family, no zone
class — the zone law binds no foot to it).  Its outer ring meets the band or the mesh at their
level; its ring on the upper face is held at the wall's top
(``constraints/wall_zone.face_top``, ``constraints/road_ramp.wall_release``).
Geometry only; no airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import typing as _t

import shapely

from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
from ..model.wall_reach import WALL_SLOPE_REF_PREFIX

__all__ = ["wall_slopes"]


def wall_slopes(walls: _t.Sequence, taken: _t.Sequence, hairline_m: float
                ) -> list[tuple[str, _t.Any]]:
    """``(ref, polygon)`` per wall-slope piece: every retaining wall's upper
    band (``WallSides.upper``) whose top is read (``top_profile``), less
    its footprint and every polygon in ``taken`` (the regions already
    standing, the structure keep-outs)."""
    live = [w for w in walls if getattr(w, "top_profile", None)
            and w.upper is not None and not w.upper.is_empty]
    if not live:
        return []
    held = canonical_union([g for g in taken if g is not None and not g.is_empty])
    out: list[tuple[str, _t.Any]] = []
    k = 0
    for w in live:
        g = fixed_difference(w.upper, w.poly)
        if held is not None and not held.is_empty:
            g = fixed_difference(g, held)
        for part in shapely.get_parts(g):
            if part.geom_type != "Polygon" or part.area < 1.0 \
                    or is_hairline(part, hairline_m):
                continue
            out.append((f"{WALL_SLOPE_REF_PREFIX}{w.resource}#{k}", part))
            k += 1
    return out
