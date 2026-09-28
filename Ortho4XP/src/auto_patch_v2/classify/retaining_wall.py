"""§47 ADDENDUM — A WALL ALONG A ROAD EDGE IS A RETAINING WALL (owner
RULINGS 2026-09-27a (8), Q-8 adopted; issue #8 [HECA-3]).

Owner (HECA, 30.1122535, 31.4062746): "service road should extend to
[this point] along a retaining wall. The object wall on the road edge is
a RETAINING wall: road level at the wall top, ground beyond at the wall
bottom."  The wall is the pack's own ``Hangar_Tower/metal_strip_2.obj``
component 117 (3.1 m tall, ~330 m along the road); the 1206 ground route
it retains stops short of the wall's end, so the bare ground between the
road ribbon and the wall was never part of the road (lane ``hecabodies``).

THE RULE AS DATA.  A pack component is WALL-CLASS when it is thin (its
plan width ``2·area / perimeter`` at most ``[service] retaining_wall_
max_width_m``), at least ``[service] retaining_wall_min_height_m`` tall
and at least ``[service] retaining_wall_min_length_m`` long.  A piece of
it (one footprint ring) RUNS ALONG A ROAD EDGE when at least
``[service] retaining_wall_along_fraction`` of its plan area lies within
``[service] retaining_wall_reach_m`` (one lane width past the road the 6 m corridor under-draws — see rules.toml) of a service
road ribbon.  Such a piece is a RETAINING piece.

THE ROAD'S GRADED STRIP EXTENDS TO THE WALL (:func:`road_extension`): the
ground between a retaining piece and the ribbon it retains — the convex
hull of the piece and the ribbon within reach of it, less the piece
itself — joins the road, so the road runs up to the wall's face and on to
the wall's END, at the road's own level (the road profile grades it with
the ribbon it joins; no new role, no new row).  The far side is left to
the ground: the wall's foot stands there and the object stage seats the
wall on it.

ONE derivation site: ``classify/roles`` asks this module for the
extension and adds it to the ribbon before the ribbon is cut from the
pavement, the pads and the runways — so every consumer downstream sees
an ordinary ``service_road`` face.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..model.airport import Airport

__all__ = ["RetainingPiece", "WallComponent", "retaining_pieces",
           "road_extension", "wall_class_components", "STATS"]

#: What the last call found (``classify`` publishes it with its stats).
STATS: dict[str, float] = {}


@_dc.dataclass(frozen=True)
class RetainingPiece:
    """One footprint ring of a wall-class component that runs along a road
    edge: its plan polygon (frame xy), the component's solid height, and
    where it came from."""

    poly: Polygon
    height_m: float
    resource: str
    comp: int
    gap_m: float


def _wall_class(poly: Polygon, height_m: float, cfg) -> bool:
    if height_m < float(cfg.retaining_wall_min_height_m):
        return False
    if poly.area <= 0.0 or poly.length <= 0.0:
        return False
    width = 2.0 * poly.area / poly.length
    length = poly.length / 2.0 - width
    return (width <= float(cfg.retaining_wall_max_width_m)
            and length >= float(cfg.retaining_wall_min_length_m))


@_dc.dataclass(frozen=True)
class WallComponent:
    """One WALL-CLASS pack component (module docstring: thin, tall, long):
    its footprint pieces (frame xy), its solid height and its source."""

    pieces: tuple
    height_m: float
    resource: str
    comp: int


#: RULINGS 2026-09-29h (Q-72b): a FENCE is not a wall.  A footprint cannot
#: tell a fence from a retaining or sea wall (TFFJ ``beach_fence.obj``:
#: 92 m, 2.38 m, thin), so the pack's own resource name decides: a
#: component whose resource basename names one of these is never wall-class.
NOT_WALL_RESOURCE_WORDS = ("fence", "railing")


def _not_a_wall(resource: str) -> bool:
    base = str(resource or "").replace("\\", "/").rsplit("/", 1)[-1].lower()
    return any(w in base for w in NOT_WALL_RESOURCE_WORDS)


def wall_class_components(airport: Airport, cfg) -> list[WallComponent]:
    """THE WALL-CLASS CLASSIFIER, the one implementation: every pack
    component that is thin, at least ``retaining_wall_min_height_m`` tall
    and at least ``retaining_wall_min_length_m`` long.  Read by
    :func:`retaining_pieces` (a wall along a road edge) and by
    ``planar/shore`` (a wall along the shore — owner RULINGS 2026-09-29a
    (2)).  Retaining / sea-wall classes only: a fence resource is never
    wall-class (RULINGS 2026-09-29h, Q-72b)."""
    part = getattr(airport, "partition", None)
    if part is None:
        return []
    to_xy = airport.frame.entry()
    out: list[WallComponent] = []
    for u in part.units:
        for m in u.members:
            if _not_a_wall(m.resource):
                continue                    # 29h (Q-72b): a fence is no wall
            for p in m.parts:
                if not p.rings or getattr(p, "line", False) or \
                        p.height_m < float(cfg.retaining_wall_min_height_m):
                    continue
                polys = []
                for rg in p.rings:
                    if len(rg) < 3:
                        continue
                    g = Polygon([to_xy(lon, lat) for lat, lon in rg])
                    if not g.is_valid:
                        g = g.buffer(0.0)
                    if not g.is_empty and g.geom_type == "Polygon":
                        polys.append(g)
                if not polys:
                    continue
                whole = unary_union(polys)
                if whole.length <= 0.0:
                    continue
                # the COMPONENT is judged thin and long; its PIECES are
                # judged against the road (or the shore) one by one
                wide = 2.0 * whole.area / whole.length
                if wide > float(cfg.retaining_wall_max_width_m) or \
                        sum(g.length for g in polys) / 2.0 < \
                        float(cfg.retaining_wall_min_length_m):
                    continue
                out.append(WallComponent(tuple(polys), float(p.height_m),
                                         m.resource, int(p.comp)))
    return out


def retaining_pieces(airport: Airport, ribbon, lane_m: float, cfg
                     ) -> list[RetainingPiece]:
    """Every RETAINING piece (module docstring) against ``ribbon`` (the
    service-road corridor union, frame xy)."""
    if getattr(airport, "partition", None) is None or ribbon is None or \
            ribbon.is_empty or lane_m <= 0.0:
        return []
    near = ribbon.buffer(lane_m)
    frac = float(cfg.retaining_wall_along_fraction)
    out: list[RetainingPiece] = []
    walls = wall_class_components(airport, cfg)
    for w in walls:
        for g in w.pieces:
            if g.area <= 0.0 or not g.intersects(near):
                continue
            if g.intersection(near).area / g.area < frac:
                continue
            out.append(RetainingPiece(g, w.height_m, w.resource, w.comp,
                                      float(g.distance(ribbon))))
    STATS.update(wall_components=len(walls), retaining_pieces=len(out))
    return out


def road_extension(pieces: _t.Sequence[RetainingPiece], ribbon, lane_m: float):
    """THE ROAD'S GRADED STRIP EXTENDED TO THE WALL: per retaining piece,
    the convex hull of the piece and the ribbon within ``gap + lane`` of
    it, less the piece and the ribbon — the bare ground the road retains.
    Empty when nothing retains."""
    if not pieces:
        STATS.update(extension_m2=0.0)
        return Polygon()
    parts = []
    for rp in pieces:
        reach = rp.gap_m + lane_m
        bit = ribbon.intersection(rp.poly.buffer(reach))
        if bit.is_empty:
            continue
        hull = unary_union([rp.poly, bit]).convex_hull
        parts.append(hull.difference(rp.poly))
    ext = unary_union(parts).difference(ribbon) if parts else Polygon()
    # only what JOINS the road extends it: a hull remnant standing apart
    # from the ribbon is not the road's strip (closing build hecaroad_close1:
    # `route4`, 8 vertices, no vertex shared with the road, 2 m below it)
    keep = [g for g in getattr(ext, "geoms", [ext])
            if g.geom_type == "Polygon" and g.distance(ribbon) < 1e-6]
    ext = unary_union(keep) if keep else Polygon()
    STATS.update(extension_m2=round(float(ext.area), 1))
    return ext
