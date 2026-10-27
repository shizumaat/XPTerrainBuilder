"""THE FILL RUNS TO THE ROAD (owner RULINGS 2026-10-20d; spec
``docs/specs/road-edge-drop-spec.md`` R2 and census row 5).

The owner: "put the drop along a road edge ... it should be graded to road
rules, and reach the high terminals, and then allow a vertical drop on the
low side".  A pad fill (``planar/pad_fill``: a plate riding a block, a
viaduct's ground prints) stands at its block's level; where its 1:3 collar
cannot reach the ground (MEASURED HECA: the #712 plate at a predicted
96.17 m over collar ground of 89.4-93.2 m, a 15 m collar dropping at most
5 m), the fill takes the ground between it and the ROAD STRIPS within
``[building_pad] fill_road_reach_m``, up to their kerb — a LENS
(:func:`extend_to_roads`), never a hull and never across the road.  The road
is never cut: its kerb is the fill's edge and the two share vertices there,
so the landing's own rows hold the kerb at the fill's level and the road
climbs to it by §37 (6) alone (its kerb vertices on the fill are mouths at
the fill's highest predicted level, ``airport/road_ramp``).  No collar goes
over or along a strip (``planar/landing`` PASS 2).

A ROAD STRIP is a road-family source cell — a pack road page, never a 1206
route corridor or a run-out — that touches no airside region (a road a
stage-1 surface borders is a stage-1 participant; cutting or welding one
moved stage 1, ``planar/landing.LOT_ROLES``).  The same strips are cut under
a viaduct's DECK landings (``planar/landing.landing_cut``), because R1
(``classify/sources._network_strip``) made the lot such a viaduct lands on a
road: the road meets the landing at its edge and carries the descent itself
(§37 (6))."""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts as _parts

__all__ = ["road_strips", "cannot_bank", "extend_to_roads", "STRIP_EXCLUDE"]

#: the road cells that are no road STRIP: a 1206 corridor (``route<i>``) and
#: a landing's run-out (``runout:...``) — never a pack page
STRIP_EXCLUDE = ("route", "runout")


def road_strips(base_regions: _t.Iterable, air_polys: _t.Sequence, law,
                roles: "_t.Collection[str] | None" = None) -> list:
    """The ROAD STRIPS among ``base_regions`` (module docstring): road-family
    source cells off every airside region by more than one weld spacing.
    ``roles`` reads another family the same way (the LOTS a fill runs to,
    RULINGS 2026-10-27i: ``planar/landing.LOT_ROLES``)."""
    from ..law.tables import family
    roads = frozenset(roles) if roles is not None else \
        frozenset(family(law, "road_cross_section").roles)
    weld = float(law.tables.emit.identity.weld_spacing_m)
    air = unary_union([a for a in air_polys if a is not None])
    out = []
    for r in base_regions:
        g = getattr(r, "polygon", None)
        if (g is None or g.is_empty or r.source != "cell" or r.role not in roads
                or str(r.ref).startswith(STRIP_EXCLUDE)):
            continue
        if not air.is_empty and g.distance(air) <= weld:
            continue
        out.append(r)
    return out


def cannot_bank(fill: Polygon, level: float, dem, collar_m: float,
                slope: float, step_m: float = 5.0) -> bool:
    """True when ``fill``'s collar cannot bank down: ``level`` stands more
    than the collar's drop (``collar_m x slope``) over the lowest DEM on the
    collar's outer line, sampled every ``step_m``."""
    if dem is None or collar_m <= 0.0:
        return False
    line = fill.buffer(collar_m, join_style=2)
    lows = []
    for ring in (g.exterior for g in _parts(line)):
        n = max(4, int(math.ceil(ring.length / step_m)))
        for k in range(n):
            p = ring.interpolate(k * ring.length / n)
            lows.append(float(dem.z(p.x, p.y)))
    return bool(lows) and level - min(lows) > collar_m * slope


def extend_to_roads(fill: Polygon, strips: _t.Sequence[Polygon], reach_m: float,
                    held=None):
    """THE LENS (spec road-edge-drop round 3, D2): ``fill`` and the ground
    within ``reach_m`` of BOTH the fill and a road strip (the intersection
    of their mitred buffers), less every strip, less ``held``, keeping only
    the pieces that touch the fill.  Never a hull, never across the road:
    the lens is also kept BETWEEN the fill and the strip (the morphological
    closing of the two at half the reach), so the ground beyond a strip's
    end, which is within reach of both, is never taken.  ``None`` when no
    strip is within reach."""
    if reach_m <= 0.0 or not strips:
        return None
    zone = fill.buffer(reach_m, join_style=2)
    near = [s for s in strips if s.distance(fill) <= reach_m]
    if not near:
        return None
    S = unary_union([s.intersection(fill.buffer(2.0 * reach_m, join_style=2))
                     for s in near])
    lens = zone.intersection(S.buffer(reach_m, join_style=2))
    half = 0.5 * reach_m
    between = unary_union([fill, S]).buffer(half).buffer(-half)
    E = unary_union([fill, lens.intersection(between)]).difference(
        unary_union(list(strips)))
    if held is not None and not held.is_empty:
        E = E.difference(held)
    keep = [q for q in _parts(E) if q.distance(fill) <= 1e-6]
    return unary_union(keep) if keep else None
