"""THE SPAN BETWEEN A PACK BRIDGE'S EDGES IS COVER (owner RULINGS 2026-10-27l
"keep the span between them graded at deck level"; 2026-10-27r "they should
drop straight down from the pavement edge at the back of those edge objects,
with the top of the objects flush with the airside surface").

``planar/covered_ground`` lifts the ground over a covered bore to the ground
beside the cover, clipped to the airside pavement over it (#714).  Where a
pack models the bridge by its EDGES (``airport/hanging_objects.
edge_wall_reading``: KATL ``tunel_A`` ×2 over runway 10/28, ``tunel_B`` /
``tunel_C`` over the taxiway north of it), the ground between the two edges'
walls is the bridge's span whether or not pavement is mapped over all of it
(measured with #1495, which drops the pavement KATL borrowed from Global: the
zones between 10/28's south edge and ``tunel_A``'s back followed the lidar
down to 280-289 m, a 20 m strip_transverse row).  This module returns that
span per covered bore — the stretch of its cut between consecutive edge
objects along it, each bounded by its walls' back (the walls' furthest
station toward the other edge) — so the clip is the pavement and the spans.
Beyond the walls' backs the open cut keeps its DEM and the structure stage's
trench (``Tunnel.span_deck_z``).  Nothing here names a pack or an airport.
"""
from __future__ import annotations

from shapely.geometry import LineString, Point
from shapely.ops import substring, unary_union

__all__ = ["edge_spans"]


def _wall_stations(line: LineString, walls, rib) -> "tuple[float, float] | None":
    """The stations along ``line`` the object's deep walls reach inside the
    cut's ribbon ``rib``, as ``(lo, hi)``, or ``None``."""
    ss = []
    for seg in walls:
        part = LineString(seg).intersection(rib)
        for g in getattr(part, "geoms", [part]):
            if g.is_empty:
                continue
            ss.extend(line.project(Point(q)) for q in g.coords)
    return (min(ss), max(ss)) if ss else None


def edge_spans(cuts, objects, cache, law) -> list:
    """Per covered cut ``(bore, sections, ribbon)``, the ribbon's pieces
    between consecutive edge-wall objects over it (module doc)."""
    from ..airport.hanging_objects import edge_wall_reading
    edges = []
    for o in objects or ():
        box = getattr(o, "plan_bbox", None)
        if box is None or getattr(o, "resolved", None) is None or cache is None:
            continue
        if not any(box.intersects(rib) for _b, _s, rib in cuts):
            continue
        g = cache.geometry(o.resolved)
        r = edge_wall_reading(o, g, law) if g is not None else None
        if r is not None:
            edges.append(r[2])
    out = []
    if len(edges) < 2:
        return out
    for b, secs, rib in cuts:
        line = b.line
        at = sorted(st for st in (_wall_stations(line, w, rib) for w in edges) if st is not None)
        reach = max([max(c.dl, c.dr) for c in secs] or [0.0]) + 1.0
        for (_lo0, hi0), (lo1, _hi1) in zip(at[:-1], at[1:], strict=False):
            if lo1 <= hi0:
                continue
            piece = substring(line, hi0, lo1).buffer(reach, cap_style="flat")
            span = piece.intersection(rib)
            if not span.is_empty and span.area > 0.0:
                out.append(span)
    return [unary_union(out)] if out else []
