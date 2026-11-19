"""ONE GENERATED DECK PER TAXIWAY, AS WIDE AS ITS TAXIWAY AND SHOULDERS
(owner RULINGS 2026-11-19s (3) (b), (4) (c); ``docs/specs/airside-first-
bridges-spec.md`` section 1 row 1).

``planar/deck_generated`` reads where the airport's pavement covers a
road's cut (the piece ``P ∩ C``).  Its WIDTH is never that pavement's
(KBNA 1.0.565: "They seem wider than they need to be, I would expect them
to generally match the width of the taxiway + a shoulder"): each apt.dat
taxi route (row 1202) crossing the piece gets ITS OWN deck -- two parallel
taxiways two decks, the gap between them open over one cut (19s (3) (b))
-- a parallelogram whose ENDS run along the road (the cut's crests, the
piece's extent along the route) and whose SIDES run along the route at
``[deck_gen] width_by_class_m`` of the route's width class (ICAO Annex 14
§3.9.3 taxiway width plus §3.10.1 shoulders), centred on its centreline.
A route of no class takes the airport's most common class.

Nothing here names an airport.  Build-time impact: a few shapely
intersections per generated deck piece.
"""
from __future__ import annotations

import collections
import math
import typing as _t

from shapely.geometry import LineString, Polygon

__all__ = ["route_decks", "class_width_m", "route_ends"]

XY = tuple[float, float]
#: two crossing segments this near and this parallel are one route (m, deg)
_SAME_ROUTE_M = 3.0
_SAME_ROUTE_DEG = 20.0


def class_width_m(law, letter: "str | None", fallback: "str | None" = None) -> float:
    """The deck width (taxiway plus shoulders, m) of a width class letter."""
    table = dict(law.tables.structures.deck_gen.width_by_class_m)
    for k in (letter, fallback, "C"):
        if k and str(k).upper() in table:
            return float(table[str(k).upper()])
    return max(float(v) for v in table.values())


def _crossings(piece: Polygon, airport) -> list[tuple[LineString, _t.Any]]:
    """Every taxi edge's stretch across ``piece`` (longest first)."""
    nodes = getattr(airport, "taxi_nodes", {}) or {}
    out = []
    for e in getattr(airport, "taxi_edges", ()) or ():
        if getattr(e, "is_runway", False) or e.a not in nodes or e.b not in nodes:
            continue
        a, b = nodes[e.a].xy, nodes[e.b].xy
        if a == b:
            continue
        x = LineString([a, b]).intersection(piece)
        for q in getattr(x, "geoms", [x]):
            if q.geom_type == "LineString" and q.length > 1.0:
                out.append((q, e))
    return sorted(out, key=lambda r: -r[0].length)


def _unit(line: LineString) -> XY:
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    n = math.hypot(x1 - x0, y1 - y0)
    return ((x1 - x0) / n, (y1 - y0) / n) if n > 1e-9 else (0.0, 0.0)


def _routes(piece: Polygon, airport) -> list[tuple[LineString, list]]:
    """The crossings grouped into routes: ``(its longest stretch, its
    edges)`` -- one per taxiway NAME (a curve's segments, a split edge),
    an unnamed edge joining the route it continues (as near and as
    parallel as :data:`_SAME_ROUTE_M` / :data:`_SAME_ROUTE_DEG`)."""
    cos_t = math.cos(math.radians(_SAME_ROUTE_DEG))
    groups: list[tuple[LineString, list]] = []
    for q, e in _crossings(piece, airport):
        d, name = _unit(q), str(getattr(e, "name", "") or "")
        for main, edges in groups:
            m = _unit(main)
            same = any(str(getattr(x, "name", "") or "") == name for x in edges) if name \
                else (abs(d[0] * m[0] + d[1] * m[1]) >= cos_t
                      and q.distance(main) <= _SAME_ROUTE_M)
            if same:
                edges.append(e)
                break
        else:
            groups.append((q, [e]))
    return groups


def _common_class(airport) -> "str | None":
    got = collections.Counter(str(e.width_class).upper() for e in
                              getattr(airport, "taxi_edges", ()) or ()
                              if getattr(e, "width_class", None))
    return got.most_common(1)[0][0] if got else None


def _reach(b: float, sign: float, a0: float, a1: float, u: XY, w: XY, pave_at, reach: float
           ) -> float:
    """End ``b`` of a deck moved ``sign`` along its route until the airport's
    pavement lies just past it across most of its width (a deck over a
    pack's hole spans the hole, pavement to pavement: spec 2123 #2183 item
    4), at most ``reach`` metres; ``b`` where pavement already meets it."""
    (ux, uy), (wx, wy) = u, w
    lw = math.hypot(wx, wy)
    probes = [a0 + (a1 - a0) * k / 6.0 for k in range(1, 6)]
    e = 0.0
    while e <= reach:
        bb = b + sign * (e + 0.5) / lw
        hit = sum(1 for a in probes if pave_at((a * ux + bb * wx, a * uy + bb * wy)))
        if 2 * hit > len(probes):
            return b + sign * e / lw
        e += 0.5
    return b


def route_decks(piece: Polygon, road_dir: "XY | None", airport, law, pave_at=None
                ) -> list[tuple[Polygon, str]]:
    """``(deck ring, note)`` per taxi route across ``piece`` (module doc);
    ``[]`` where no route crosses it at an angle to the road (the caller
    keeps the piece).  ``pave_at(xy)``: whether the airport's pavement
    stands there -- each end then reaches it (:func:`_reach`)."""
    if road_dir is None or piece.is_empty:
        return []
    ux, uy = road_dir
    cos_t = math.cos(math.radians(_SAME_ROUTE_DEG))
    common = _common_class(airport)
    got: list[list] = []          # [w, det, a0, a1, b0, b1, note]
    for main, edges in _routes(piece, airport):
        wx, wy = _unit(main)
        if abs(wx * ux + wy * uy) >= cos_t:
            continue                     # a route along the road crosses no cut
        det = ux * wy - uy * wx
        b0, b1 = _span((ux, uy), (wx, wy), piece.exterior.coords)[1]
        mx, my = main.interpolate(0.5, normalized=True).coords[0]
        a_c = (mx * wy - my * wx) / det
        letters = sorted({str(e.width_class).upper() for e in edges if e.width_class})
        letter = letters[-1] if letters else None
        width = class_width_m(law, letter, common)
        ha = 0.5 * width / abs(det)
        if pave_at is not None:
            reach = float(law.tables.structures.deck_gen.end_reach_m)
            b0 = _reach(b0, -1.0, a_c - ha, a_c + ha, (ux, uy), (wx, wy), pave_at, reach)
            b1 = _reach(b1, 1.0, a_c - ha, a_c + ha, (ux, uy), (wx, wy), pave_at, reach)
        names = sorted({str(e.name) for e in edges if getattr(e, "name", "")})
        got.append([(wx, wy), det, a_c - ha, a_c + ha, b0, b1,
                    f"taxiway {'/'.join(names) or '?'} class "
                    f"{letter or (common or '?') + ' (the airport common)'}: deck "
                    f"{width:g} m wide (taxiway + shoulders, RULINGS 2026-11-19s (4) (c))"])
    return [(_ring((ux, uy), d), d[6]) for d in _merged((ux, uy), got)]


def _span(u: XY, w: XY, pts) -> tuple[tuple[float, float], tuple[float, float]]:
    """The ``(a, b)`` ranges of ``pts`` in the basis ``p = a u + b w``."""
    (ux, uy), (wx, wy) = u, w
    det = ux * wy - uy * wx
    ab = [((x * wy - y * wx) / det, (ux * y - uy * x) / det) for x, y in pts]
    return ((min(a for a, _b in ab), max(a for a, _b in ab)),
            (min(b for _a, b in ab), max(b for _a, b in ab)))


def _ring(u: XY, d: list) -> Polygon:
    (ux, uy), (wx, wy) = u, d[0]
    return Polygon([(a * ux + b * wx, a * uy + b * wy)
                    for a, b in ((d[2], d[4]), (d[3], d[4]), (d[3], d[5]), (d[2], d[5]))])


def _merged(u: XY, got: list[list]) -> list[list]:
    """Route decks that overlap (a lead-in beside its taxiway, two routes
    meeting over the road) are ONE deck: the senior's (the longer
    crossing, first) widened over the other's plan."""
    out: list[list] = []
    for d in got:
        ring = _ring(u, d)
        for k in out:
            if _ring(u, k).intersection(ring).area > 1.0:
                (a0, a1), _b = _span(u, k[0], ring.exterior.coords)
                k[2], k[3] = min(k[2], a0), max(k[3], a1)
                k[6] += f"; widened over a second route ({d[6].split(':')[0]})"
                break
        else:
            out.append(d)
    return out


def route_ends(ring: Polygon, road_dir: "XY | None", at_role, pave, step: float, to_ll
               ) -> "tuple[list, list] | None":
    """A route deck's END LINES read off its own ends -- its two edges along
    the road -- where ``airside_deck_seat.facing_contacts`` reads none (a
    deck the class width leaves inside a wider pavement meets pavement on
    its sides too, one contact all round): per end edge, the longest run of
    stations every ``step`` metres whose ground one step outside is the
    airport's pavement (``at_role(xy)``, ``pave(role)``), as ``(lat, lon)``
    (``to_ll``); ``None`` where an end meets no pavement run."""
    pts = list(ring.exterior.coords)[:-1]
    if road_dir is None or len(pts) != 4 or step <= 0.0:
        return None
    ux, uy = road_dir

    def along(e) -> float:
        dx, dy = e[1][0] - e[0][0], e[1][1] - e[0][1]
        n = math.hypot(dx, dy)
        return abs(dx * ux + dy * uy) / n if n > 1e-9 else 0.0
    edges = sorted(((pts[i], pts[(i + 1) % 4]) for i in range(4)), key=lambda e: -along(e))[:2]
    c = ring.centroid
    out = []
    for a, b in edges:
        L = math.dist(a, b)
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        if nx * ((a[0] + b[0]) / 2 - c.x) + ny * ((a[1] + b[1]) / 2 - c.y) < 0.0:
            nx, ny = -nx, -ny
        runs, cur = [], []
        for k in range(max(2, int(L / step) + 1)):
            f = k / max(1, int(L / step))
            p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            if pave(at_role((p[0] + nx * step, p[1] + ny * step))):
                cur.append(tuple(to_ll(*p)))
            elif cur:
                runs.append(cur)
                cur = []
        runs.append(cur)
        best = max(runs, key=len)
        if len(best) < 2:
            return None
        out.append(best)
    return out[0], out[1]
