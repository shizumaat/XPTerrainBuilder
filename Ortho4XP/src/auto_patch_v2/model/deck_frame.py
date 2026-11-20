"""A GENERATED DECK'S PARALLELOGRAM (airside-first bridges spec section 1
row 4; RULINGS 2026-11-19s (8) (b)): its ring as ``o + s u + t w``, ``u``
along its carried route (the sides), ``w`` along its end lines (the cut's
crests).  Read by stage 2's top (``constraints/deck_floor_follow``), the
publication (``pipeline/generated_publication``, ``pipeline/road_deck``)
and the planar cut's road-deck landings (``planar/deck_carve``; moved here
from ``constraints/deck_floor_follow`` by lane lcross20 so the planar stage
reads the same frame).  Nothing here names an airport."""
from __future__ import annotations

from ..geom.exact import hypot
from ..geom.rotated_rect import rotated_rectangle

__all__ = ["deck_frame"]


def deck_frame(db) -> "tuple[tuple, tuple, tuple] | None":
    """``(o, u, w)``: the deck ring as the parallelogram ``o + s u + t w``
    -- ``s = 0`` its end A (the edge nearest ``seats_a`` of the two most
    nearly square to its carried route, RULINGS 2026-11-19s (8) (b): the
    axis ``u`` runs along the route), ``u`` along its sides to end B, ``w``
    along end A.  A ring of other than four corners reads its least
    rotated rectangle; ``None`` for no ring."""
    from shapely.geometry import MultiPoint, Point, Polygon
    if len(getattr(db, "ring", ()) or ()) < 3:
        return None
    poly = Polygon(db.ring).buffer(0.0).simplify(0.05)
    if poly.is_empty or poly.geom_type != "Polygon":
        return None
    pts = list(poly.exterior.coords)[:-1]
    if len(pts) != 4:
        pts = list(rotated_rectangle(poly).exterior.coords)[:-1]
    if len(pts) != 4:
        return None
    sa = getattr(db, "seats_a", ()) or ()
    ca = MultiPoint([tuple(p) for p in sa]).centroid if sa else Point(pts[0])
    from shapely.geometry import LineString
    ends = _across_route(pts, getattr(db, "route", ()) or ())
    i = min(ends, key=lambda k: LineString([pts[k], pts[(k + 1) % 4]]).distance(ca))
    c0, c1, c3 = pts[i], pts[(i + 1) % 4], pts[(i + 3) % 4]
    return (c0, (c3[0] - c0[0], c3[1] - c0[1]), (c1[0] - c0[0], c1[1] - c0[1]))


def _across_route(pts, route) -> list[int]:
    """The indices ``k`` of the two edges ``pts[k] -> pts[k + 1]`` most
    nearly square to ``route`` where it crosses the quadrilateral (its
    longest piece inside); all four where no route crosses it."""
    from math import atan2, cos, sin

    from shapely.geometry import LineString, Polygon
    quad = Polygon(pts)
    if len(route) < 2 or not quad.is_valid:
        return list(range(4))
    x = LineString(route).intersection(quad)
    parts = [q for q in getattr(x, "geoms", [x]) if q.geom_type == "LineString" and q.length > 1.0]
    if not parts:
        return list(range(4))
    c = list(max(parts, key=lambda q: q.length).coords)
    a = atan2(c[-1][1] - c[0][1], c[-1][0] - c[0][0])

    def along(k: int) -> float:
        (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % 4]
        n = hypot(x1 - x0, y1 - y0) or 1.0
        return abs((x1 - x0) * cos(a) + (y1 - y0) * sin(a)) / n
    return sorted(range(4), key=along)[:2]
