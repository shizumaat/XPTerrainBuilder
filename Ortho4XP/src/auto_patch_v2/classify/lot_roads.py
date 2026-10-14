"""ROADS INSIDE A LOT ARE THE LOT (owner RULINGS 2026-10-14a (2), extending
the free-road ruling of 2026-07-27 — "roads inside or edge-sharing an apron
ARE the apron" — to groundside lots; issue #609).

The owner: "stop trying to treat lanes in the lot as roads, only roads
where there's a gap of no pavement, roads connecting between lots, etc."
A mapped road that runs INSIDE a lot is never ribboned (the mint subtracts
every standing cell).  This module reads the other half: a stretch of a
mapped road whose ribbon runs ALONG a lot's edge — its axis within the
ribbon's half-width (plus one identity cell, the touch witness) of the
lot, outside it, over at least two lane widths — is minted as LOT
pavement: the lot's role and kind, a ref of the lot's own
(``<lot ref>#road<k>``), graded under lot law with the lot in the stage
the lot stands in.  A road meeting a lot END-ON (its mouth: the axis comes
within the half-width over about one half-width) and a road across open
ground between two lots stay road.

A LOT is a standing groundside pavement cell that is not road: roles
:data:`LOT_ROLES`, never a §53 gap piece (a last-stage follower; a lot
minted beside it would stand before the piece it is part of).

MEASURED SPJC building24 (main 62db0dd93): pad road ``-6132#1`` ran
between two concrete lots (``dsf:pol37``, ``dsf:pol36#1``) along the pad's
east rim, welded to the pad at 24.36 m and to the lots at 28.1 m across
its 7 m width — the cross-fall rows of #658."""
from __future__ import annotations

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import substring, unary_union

from ..model.planar import is_gap_ref
from ..geom.parts import line_parts
from .evidence import polygon_parts

__all__ = ["LOT_ROLES", "lot_cells", "lot_stretches", "split_lot_ribbon"]

#: The groundside pavement a road along it becomes part of: the lot and
#: the landside paved island (``roles.open_pavement_role`` / the demotion
#: ladder's two landside classes).
LOT_ROLES = ("parking_lot", "groundside_pavement")


def lot_cells(cells) -> list[tuple[object, Polygon]]:
    """The standing lots among ``cells``: ``(cell, polygon)``."""
    return [(c, Polygon(c.ring, c.holes)) for c in cells
            if c.role in LOT_ROLES and c.side == "groundside"
            and not is_gap_ref(getattr(c, "ref", ""))]


def lot_stretches(line: LineString, lots_union, reach_m: float,
                  min_along_m: float) -> list[tuple[float, float]]:
    """The arclength intervals of ``line`` that run ALONG a lot: outside
    ``lots_union``, within ``reach_m`` of it, each at least ``min_along_m``
    long (a mouth meeting the lot end-on is shorter)."""
    if lots_union.is_empty or line.length <= 0.0:
        return []
    band = lots_union.buffer(reach_m).difference(lots_union)
    out = []
    for part in line_parts(line.intersection(band)):
        if part.length < min_along_m:
            continue
        a = line.project(shapely.geometry.Point(part.coords[0]))
        b = line.project(shapely.geometry.Point(part.coords[-1]))
        a, b = min(a, b), max(a, b)
        if b - a >= min_along_m:
            out.append((a, b))
    return sorted(out)


def split_lot_ribbon(rib, line: LineString, lots: list[tuple[object, Polygon]],
                     hw: float, touch_m: float, grid: float, min_area: float):
    """``rib`` (one way's ribbon, already less everything standing) cut in
    two: ``(road, parts)`` — the road's remainder and the lot parts, each
    ``(lot cell, polygon)`` with the lot it runs along (the nearest; the
    one it shares most edge with on a tie)."""
    if not lots or rib.is_empty:
        return rib, []
    near = [(c, p) for c, p in lots if p.distance(rib) <= touch_m]
    if not near:
        return rib, []
    union = unary_union([p for _c, p in near])
    spans = lot_stretches(line, union, hw + touch_m, 2.0 * hw)
    if not spans:
        return rib, []
    zone = unary_union([substring(line, a, b).buffer(
        hw + touch_m, cap_style="flat", join_style="mitre", mitre_limit=2.0)
        for a, b in spans])
    lot_geom = shapely.set_precision(rib.intersection(zone), grid)
    road = shapely.set_precision(rib.difference(zone), grid)
    parts = []
    for part in polygon_parts(lot_geom):
        if part.area < min_area:
            continue
        best = min(near, key=lambda cp: (
            round(cp[1].distance(part), 3),
            -cp[1].buffer(touch_m).intersection(part.boundary).length))
        parts.append((best[0], part))
    if not parts:
        return rib, []
    return road, parts
