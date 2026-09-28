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

__all__ = ["RetainingPiece", "retaining_pieces", "road_extension", "STATS"]

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


def retaining_pieces(airport: Airport, ribbon, lane_m: float, cfg
                     ) -> list[RetainingPiece]:
    """Every RETAINING piece (module docstring) against ``ribbon`` (the
    service-road corridor union, frame xy)."""
    part = getattr(airport, "partition", None)
    if part is None or ribbon is None or ribbon.is_empty or lane_m <= 0.0:
        return []
    to_xy = airport.frame.entry()
    near = ribbon.buffer(lane_m)
    frac = float(cfg.retaining_wall_along_fraction)
    out: list[RetainingPiece] = []
    walls = 0
    for u in part.units:
        for m in u.members:
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
                # judged along the road one by one
                wide = 2.0 * whole.area / whole.length
                if wide > float(cfg.retaining_wall_max_width_m) or \
                        sum(g.length for g in polys) / 2.0 < \
                        float(cfg.retaining_wall_min_length_m):
                    continue
                walls += 1
                for g in polys:
                    if g.area <= 0.0 or not g.intersects(near):
                        continue
                    if g.intersection(near).area / g.area < frac:
                        continue
                    out.append(RetainingPiece(g, float(p.height_m), m.resource,
                                              int(p.comp), float(g.distance(ribbon))))
    STATS.update(wall_components=walls, retaining_pieces=len(out))
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
    STATS.update(extension_m2=round(float(ext.area), 1))
    return ext
