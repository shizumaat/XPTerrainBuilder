"""THE EDGE BRIDGE: ONE READING OF WHERE ITS COVER ENDS (owner RULINGS
2026-10-27l, 2026-10-27r, 2026-10-28d Q211–Q214; 2026-10-20am/ao/ar/as;
#1138, round-5 spec).

A pack may model a bridge over a mapped bore by its EDGES only
(``airport/hanging_objects.edge_wall_reading``: deck slabs flush with its
zero on walls hanging the road's depth under it, no hard deck over the
span — KATL ``tunel_A`` ×2 over runway 10/28, ``tunel_B`` / ``tunel_C``
over the taxiway north of it).  Four readers used to derive where the cover
ends (the pavement's end, a ribbon along the bore, the nearest back, a
pre-solve deck height) and every missed bar was a seam between two of
them.  This module is the ONE derivation, computed once in
``planar/build`` before ``build_structures`` and handed to it and to
``planar/covered_ground``:

* the BACK is the object's deep walls' line on its SPAN side — per
  lateral line (across the direction toward the airside pavement it
  edges) the wall reaching furthest toward the span.  20ao "the road ends
  at the back of the object", 20as "the cut encompasses the object": the
  trench takes in the object and stops at the back.
* the SPAN is the ground between the back and the airside pavement the
  object edges: ``hull(back ∪ the nearest pavement point of each back
  vertex) − pavement``.  (A facing bridge's back across the same cut is
  NOT taken: at KATL the hull of the two runway edges drew a 1,500 m2
  wedge past the objects' ends over the open carriageways.)
  The COVER is that span (with any of the object's own top plates on the
  span side of the back — none at KATL, whose plates all stand over the
  cut).  Inside the cover the ground is lifted as #714's covered ground
  (27l "the span stays graded at deck level"; Q212 "graded strip, lifted
  to deck level").
* the DEPTH is the object's top minus its walls' bottom (20am / 20ar),
  and ``deck_z`` the covered ground at the back over its bores — the
  floor's top: the trench beyond the back stands at ``deck_z − depth``,
  held relationally under the solved rim by ``tunnel.mouth_depth_m``.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math

from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely.ops import nearest_points, unary_union

__all__ = ["EdgeBridge", "edge_bridges", "back_line", "bridge_crossed", "bridge_pin", "edge_cut", "edge_flat_s", "span_side", "far_back_s"]

#: the lateral sampling step of a back (metres)
_BACK_STEP_M = 1.0


@_dc.dataclass(frozen=True)
class EdgeBridge:
    """One edge-wall bridge over served bores (module doc)."""

    object_id: str
    resource: str
    #: the object's top minus its walls' bottom (metres)
    depth_m: float
    #: the back line (frame xy), lateral order
    back: tuple[tuple[float, float], ...]
    #: the object's placed plan hull (frame xy)
    plan: tuple[tuple[float, float], ...]
    #: the unit direction from the object toward the span it edges
    toward: tuple[float, float]
    #: the cover (the span), a polygon (frame metres)
    cover: Polygon
    #: the covered ground at the back over its bores: the floor's top
    deck_z: float
    #: the served bores (``"+".join(way ids)``) whose cut it meets
    bores: tuple[str, ...]

    @property
    def back_line(self) -> LineString:
        return LineString(self.back)


def back_line(walls, toward: tuple[float, float], step: float = _BACK_STEP_M
              ) -> list[tuple[float, float]]:
    """The BACK of ``walls`` (plan segments): per lateral line across
    ``toward`` (every ``step``), the point of the walls furthest along
    ``toward`` — the span-side face, a skewed or stepped wall followed
    exactly."""
    ux, uy = toward
    nx, ny = -uy, ux
    segs = []
    for seg in walls:
        for p0, p1 in zip(seg[:-1], seg[1:], strict=False):
            segs.append((p0[0] * ux + p0[1] * uy, p1[0] * ux + p1[1] * uy,
                         p0[0] * nx + p0[1] * ny, p1[0] * nx + p1[1] * ny))
    if not segs:
        return []
    lo = min(min(s[2], s[3]) for s in segs)
    hi = max(max(s[2], s[3]) for s in segs)
    n = max(2, int(math.ceil((hi - lo) / step)) + 1)
    out = []
    for k in range(n):
        lat = lo + (hi - lo) * k / (n - 1)
        reach = None
        for a0, a1, l0, l1 in segs:
            if min(l0, l1) - 1e-9 > lat or max(l0, l1) + 1e-9 < lat:
                continue
            a = max(a0, a1) if abs(l1 - l0) <= 1e-12 else a0 + (a1 - a0) * (lat - l0) / (l1 - l0)
            reach = a if reach is None else max(reach, a)
        if reach is not None:
            out.append((reach * ux + lat * nx, reach * uy + lat * ny))
    return out


def _toward(hull: Polygon, pav) -> tuple[float, float] | None:
    c = hull.centroid
    _a, q = nearest_points(c, pav)
    dx, dy = q.x - c.x, q.y - c.y
    n = math.hypot(dx, dy)
    return None if n <= 1e-9 else (dx / n, dy / n)


def _span_side(p, q, toward) -> bool:
    return (q[0] - p[0]) * toward[0] + (q[1] - p[1]) * toward[1] > 0.0


def edge_bridges(objects, cache, cuts, pav, law) -> tuple[EdgeBridge, ...]:
    """Every edge-wall bridge (module doc) whose plan meets a served bore's
    cut ribbon: ``cuts`` are ``planar/covered_ground.covered_cuts``' (bore,
    sections, ribbon) BEFORE the pavement clip, ``pav`` the airside
    pavement union they are clipped to."""
    from ..airport.hanging_objects import edge_wall_reading
    from .covered_ground import ground_beside
    if not cuts or pav is None or pav.is_empty or cache is None:
        return ()
    raw = []
    for o in objects or ():
        box = getattr(o, "plan_bbox", None)
        if box is None or getattr(o, "resolved", None) is None:
            continue
        met = [k for k, (_b, _s, rib) in enumerate(cuts) if box.intersects(rib)]
        if not met:
            continue
        g = cache.geometry(o.resolved)
        r = edge_wall_reading(o, g, law) if g is not None else None
        if r is None:
            continue
        depth, plan, walls = r[0], r[1], r[2]
        hull = Polygon(plan)
        met = [k for k in met if hull.intersects(cuts[k][2])]
        u = _toward(hull, pav) if met else None
        if u is None:
            continue
        back = back_line(walls, u)
        if len(back) < 2:
            continue
        raw.append((o, depth, plan, u, back, met))
    out = []
    for o, depth, plan, u, back, met in raw:
        pts = list(back)
        for p in back:
            _a, q = nearest_points(Point(p), pav)
            if _span_side(p, (q.x, q.y), u):
                pts.append((q.x, q.y))
        span = MultiPoint(pts).convex_hull.difference(pav)
        parts = [p for p in getattr(span, "geoms", [span]) if p.geom_type == "Polygon"
                 and p.area > 0.0 and p.distance(LineString(back)) <= 1.0]
        if not parts:
            continue
        cover = unary_union(parts)
        line = LineString(back)
        zs = []
        for k in met:
            b, secs, _rib = cuts[k]
            x = b.line.intersection(line)
            at = (x if not x.is_empty and x.geom_type == "Point"
                  else nearest_points(line, b.line)[0])
            z = ground_beside(at, b.line, secs)
            if z is not None:
                zs.append(z)
        if not zs:
            continue
        out.append(EdgeBridge(str(o.id), str(o.path), float(depth), tuple(back),
                              tuple(plan), u, cover, float(max(zs)),
                              tuple("+".join(str(w.id) for w in cuts[k][0].ways) for k in met)))
    return tuple(out)


def bridge_crossed(mouth, bridges, tol: float) -> "EdgeBridge | None":
    """The edge bridge PINNING ``mouth`` (a ``structure_approach.Mouth``):
    one whose back its line crosses — the mapped bore or the approach
    beyond its end — going INTO the span (the mouth's inward runs toward
    the span), at most the object's own run along that line plus ``tol``
    (``tunnel.object.bore_end_tolerance_m``) from the mapped end; the
    nearest such.  A pin by CROSSING, never by the end's distance to the
    object (a bore mapped 8-12 m short of the object still runs through
    its back)."""
    lines = [mouth.bore.line]
    if len(getattr(mouth, "approach", ()) or ()) >= 2:
        lines.append(LineString(mouth.approach))
    best = None
    for br in bridges:
        if mouth.inward[0] * br.toward[0] + mouth.inward[1] * br.toward[1] <= 0.0:
            continue
        bl, hull = br.back_line, Polygon(br.plan)
        for ln in lines:
            x = ln.intersection(bl)
            run = ln.intersection(hull).length
            for q in getattr(x, "geoms", [x]):
                if q.is_empty or q.geom_type != "Point":
                    continue
                d = math.hypot(q.x - mouth.xy[0], q.y - mouth.xy[1])
                if d <= run + tol and (best is None or d < best[0]):
                    best = (d, br)
    return None if best is None else best[1]


def span_side(br: EdgeBridge, reach: float) -> Polygon:
    """The ground on the SPAN side of ``br``'s back — the back swept
    ``reach`` toward the span, with the cover: where its trench never
    stands."""
    ux, uy = br.toward
    sweep = Polygon(list(br.back) + [(x + ux * reach, y + uy * reach)
                                     for x, y in reversed(br.back)]).buffer(0)
    return unary_union([sweep, br.cover])


def edge_cut(br: EdgeBridge, ramp, outer, rim_off: float, reach: float, others=()):
    """``(ramp, outer)``: an edge-bridge corridor's ramp and footprint TAKE
    IN THE OBJECT'S WHOLE PLAN (owner RULINGS 2026-10-28d Q213: the cut
    stands at the walls' bottom along the whole back, where no highway runs
    beneath too; 20as: the cut encompasses the object) and STOP AT THE BACK
    (:func:`span_side`, ``reach`` the corridor's own length) — its own and
    every other edge bridge's in ``others`` it runs into: the footprint
    runs to the back exactly, a skewed one too, and the floor stands the
    rim stand-off ``rim_off`` off it — the wall between is the step."""
    side = unary_union([span_side(b, reach) for b in (br, *others)])
    plan = Polygon(br.plan)
    ramp2 = unary_union([ramp, plan]).difference(side.buffer(rim_off, join_style="mitre"))
    outer2 = unary_union([outer, plan.buffer(rim_off, join_style="mitre")]).difference(side)

    def one(g, keep):
        parts = [q for q in getattr(g, "geoms", [g]) if q.geom_type == "Polygon" and q.area > 0]
        return max(parts, key=lambda q: q.area) if parts else keep
    return one(ramp2, ramp), one(outer2, outer)


def far_back_s(br: EdgeBridge, axis: LineString, bridges) -> "tuple[float, tuple] | None":
    """``(station, bridges)``: where the corridor ``axis`` (from ``br``'s
    back outward) runs into ANOTHER edge bridge's back from its cut side —
    the open stretch between two bridges over one road (owner RULINGS
    2026-10-27r: the highway runs at the objects' bottom; KATL between the
    runway's and the taxiway's bridges) — the nearest such and the bridges
    met there, else ``None``: the trench is level from back to back and
    climbs nowhere."""
    best = None
    for o in bridges:
        if o is br or o.object_id == br.object_id:
            continue
        x = axis.intersection(o.back_line)
        for q in getattr(x, "geoms", [x]):
            if q.is_empty or q.geom_type != "Point":
                continue
            s = axis.project(q)
            p0 = axis.interpolate(max(0.0, s - 1.0))
            p1 = axis.interpolate(min(axis.length, s + 1.0))
            if (p1.x - p0.x) * o.toward[0] + (p1.y - p0.y) * o.toward[1] <= 0.0:
                continue            # met from its span side: not its cut
            if best is None or s < best[0]:
                best = (s, o)
    return None if best is None else (float(best[0]), (best[1],))


def edge_flat_s(br: EdgeBridge, axis: LineString) -> float:
    """The station along ``axis`` (from the mouth) the floor stays level
    to: the object's furthest point out along it — the highway runs at the
    objects' bottom under the whole object (27r), then climbs."""
    return float(max((axis.project(Point(q)) for q in br.plan), default=0.0))


def bridge_pin(br: EdgeBridge, mouth):
    """The edge bridge as the ``airport/portal_objects.Portal`` the
    structure pass pins ``mouth`` with (its back the edge walls)."""
    from ..airport.portal_objects import Portal
    return Portal(br.object_id, br.resource, tuple(mouth.xy),
                  int(mouth.ways[0]) if mouth.ways else 0, br.depth_m, 0.0,
                  br.back[len(br.back) // 2], True, br.plan, (br.back,))
