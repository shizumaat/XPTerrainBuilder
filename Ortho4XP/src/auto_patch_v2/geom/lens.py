"""THE LENS — the ground between a senior footprint and the roads within
reach of it (spec ``road-edge-drop-spec.md`` round 3, D2), one geometry for
its two readers: a pad fill running to its road strips
(``planar/fill_road.extend_to_roads``) and a pad's KERBSIDE, the unmapped
pavement between a building and the road that serves its frontage
(``classify/frontage_road``, issue #2057)."""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from .parts import nonempty_polygon_parts as _parts

__all__ = ["lens_to_roads"]


def lens_to_roads(fill: Polygon, strips: _t.Sequence[Polygon], reach_m: float,
                  held=None):
    """``fill`` and the ground within ``reach_m`` of BOTH the fill and a
    road strip (the intersection of their mitred buffers), less every
    strip, less ``held``, keeping only the pieces that touch the fill.
    Never a hull, never across the road: the lens is also kept BETWEEN the
    fill and the strip (the morphological closing of the two at half the
    reach), so the ground beyond a strip's end, which is within reach of
    both, is never taken.  ``None`` when no strip is within reach."""
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
