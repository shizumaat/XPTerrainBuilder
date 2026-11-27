"""THE DECK'S PLAN: ONE DERIVATION OF ITS EDGES, BANDS, FLOOR, MOUTH ZONE
AND APRONS (#2239 / #2241, spec cyyz-decks-r3 §2; owner sim read
2026-11-26T15:02Z on 1.0.585: "the end strip is NOT support -- the road
envelope under/through the bridge must stay clear; ends must be square").

A pack deck the airport's pavement drives across has two END EDGES
(``geom/deck_end_edge``: the ring's sides its end lines lie on, corner to
corner).  Everything the cut under it and the ground beside it stand on is
read off those two polylines here, once:

* THE SAFE BAND (:func:`safe_band`): two arrangement cells, ``2 x [cutout]
  ring_floor_m`` -- two rings nearer than ``ring_floor_m`` are welded into
  one by the arrangement (``planar/structure_geometry`` §47 (3)); a ring a
  band of exactly that from another still snaps onto its rounded stations
  (MEASURED CYYZ T: the floor ring 0.7071 m inside the rim shared the
  pavement's snapped stations), so the band is two cells, never one.
* THE BANDS: each edge PROLONGED past both corners along its own end
  segments' directions (never a road's: CYYZ T's road runs 26 deg off its
  deck), as a strip ``band`` wide on the deck's side of it.
* THE FLOOR: the strip between the two prolonged edges less both bands --
  the road's way under the deck, mouth to mouth, never narrowed by a rim
  inside the deck's reach.
* THE MOUTH ZONE (:meth:`_DeckPlan.mouth_zone`): the strip beyond each of
  the ring's mouths, between the prolonged edges, squared off at the
  farthest reach of a footprint along them: the cut there ends square.
* THE APRON (:meth:`_DeckPlan.apron`): the strip ``depth`` wide OUTSIDE an
  end edge, corner to corner -- the ground the deck's end meets.

Pure plan geometry; nothing here names a pack or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

__all__ = ["plan", "safe_band", "wall_inset"]

XY = tuple[float, float]


def safe_band(law) -> float:
    """``2 x [cutout] ring_floor_m`` (module doc), m."""
    return 2.0 * float(law.tables.structures.cutout.ring_floor_m)


def wall_inset(law) -> float:
    """How far a WALLED deck's rim stands behind its walls' inner faces
    (``geom/walled_trench._walled_trench``'s ``inset``): ``[tunnel]
    wall_gap_m``, never under the safe band -- MEASURED CYYZ M: a rim 0.6 m
    behind the face stood closer than ``ring_floor_m`` 0.7071 and the floor
    ring snapped onto it (spec cyyz-decks-r3 R2)."""
    return max(float(law.tables.structures.tunnel.wall_gap_m), safe_band(law))


def _unit(a: XY, b: XY) -> "XY | None":
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    return None if L <= 1e-9 else (dx / L, dy / L)


def prolonged(edge: _t.Sequence[XY], by: float) -> list[XY]:
    """``edge`` run on ``by`` metres past each end along its end segment."""
    pts = [(float(p[0]), float(p[1])) for p in edge]
    if len(pts) < 2:
        return pts
    u0, u1 = _unit(pts[1], pts[0]), _unit(pts[-2], pts[-1])
    head = [(pts[0][0] + u0[0] * by, pts[0][1] + u0[1] * by)] if u0 else []
    tail = [(pts[-1][0] + u1[0] * by, pts[-1][1] + u1[1] * by)] if u1 else []
    return head + pts + tail


def _areal(g):
    """``g``'s polygonal parts alone (an overlay of strips may leave
    lines and points beside them), one geometry."""
    parts = [q for q in getattr(g, "geoms", [g]) if q.geom_type in ("Polygon", "MultiPolygon")
             and q.area > 0.0]
    return unary_union(parts) if parts else Polygon()


def _inward(line: LineString, toward: XY, width: float):
    """The strip ``width`` wide on ``line``'s side holding ``toward``."""
    left = line.buffer(width, single_sided=True)
    right = line.buffer(-width, single_sided=True)
    p = Point(toward)
    return left if left.distance(p) <= right.distance(p) else right


@_dc.dataclass(frozen=True)
class _DeckPlan:
    """One deck's plan (module doc).  ``edges`` the two end edges, ``band``
    the safe band, ``reach`` how far the edges were prolonged."""

    ring: tuple[XY, ...]
    edges: tuple[tuple[XY, ...], tuple[XY, ...]]
    band: float
    reach: float

    def _poly(self) -> Polygon:
        p = Polygon(self.ring)
        return p if p.is_valid else p.buffer(0.0)

    def _long(self, k: int) -> LineString:
        return LineString(prolonged(self.edges[k], self.reach))

    def strip(self) -> Polygon:
        """The region between the two prolonged edges."""
        a = prolonged(self.edges[0], self.reach)
        b = prolonged(self.edges[1], self.reach)
        if math.dist(a[0], b[0]) + math.dist(a[-1], b[-1]) > \
                math.dist(a[0], b[-1]) + math.dist(a[-1], b[0]):
            b = b[::-1]
        p = Polygon(a + b[::-1])
        return p if p.is_valid else p.buffer(0.0)

    def bands(self) -> list:
        """Each prolonged edge's band on the deck's side (module doc)."""
        c = self._poly().centroid
        return [_areal(_inward(self._long(k), (c.x, c.y), self.band).intersection(self.strip()))
                for k in (0, 1)]

    def floor(self):
        """The strip less both bands (module doc)."""
        return _areal(self.strip().difference(unary_union(self.bands())))

    def _along(self) -> "XY | None":
        """The edges' mean direction (``edges[0]`` oriented)."""
        sx = sy = 0.0
        for k, e in enumerate(self.edges):
            u = _unit(e[0], e[-1])
            if u is None:
                continue
            if k and (u[0] * sx + u[1] * sy) < 0.0:
                u = (-u[0], -u[1])
            sx, sy = sx + u[0], sy + u[1]
        n = math.hypot(sx, sy)
        return None if n <= 1e-9 else (sx / n, sy / n)

    def mouth_zone(self, outer):
        """The strip beyond the ring's mouths, between the prolonged edges,
        squared off at ``outer``'s farthest reach along them (module doc)."""
        d = self._along()
        if d is None or outer is None or outer.is_empty:
            return Polygon()
        ss = [x * d[0] + y * d[1] for g in getattr(outer, "geoms", [outer])
              for x, y in g.exterior.coords]
        s0, s1 = min(ss), max(ss)
        nx, ny = -d[1], d[0]
        big = self.reach * 4.0 + 1000.0
        box = Polygon([(d[0] * s0 + nx * big, d[1] * s0 + ny * big),
                       (d[0] * s1 + nx * big, d[1] * s1 + ny * big),
                       (d[0] * s1 - nx * big, d[1] * s1 - ny * big),
                       (d[0] * s0 - nx * big, d[1] * s0 - ny * big)])
        return _areal(self.strip().intersection(box).difference(self._poly()))

    def apron(self, k: int, depth: float):
        """The strip ``depth`` wide outside end edge ``k``, corner to
        corner (module doc)."""
        if depth <= 0.0 or len(self.edges[k]) < 2:
            return Polygon()
        c = self._poly().centroid
        line = LineString(self.edges[k])
        inner = _inward(line, (c.x, c.y), depth)
        both = line.buffer(depth, cap_style="flat")
        return _areal(both.difference(inner).difference(self._poly()))


def plan(ring: _t.Sequence[XY], edge_a: _t.Sequence[XY], edge_b: _t.Sequence[XY],
         band: float) -> "_DeckPlan | None":
    """The deck's plan off its ring and two end edges; ``None`` where an
    edge is degenerate."""
    if len(edge_a) < 2 or len(edge_b) < 2 or len(ring) < 3:
        return None
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    reach = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    return _DeckPlan(tuple((float(p[0]), float(p[1])) for p in ring),
                    (tuple(map(tuple, edge_a)), tuple(map(tuple, edge_b))), float(band),
                    float(reach))
