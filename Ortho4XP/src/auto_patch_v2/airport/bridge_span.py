"""THE PAGE OVER A MAPPED ROAD BRIDGE'S SPAN IS NOT GRADED (issue #2073;
owner 2026-11-13T22:48Z on #1939 site 3: "keep the lower road cut, and
don't try to grade the bridge at all, it should be handled by a bridge
object or x-plane road").

A pack may paint a road's asphalt as ONE draped page along its whole course
-- the approach on the bank, the span over the road beneath, the far bank --
while the map carries the span as a ``bridge=yes`` way the engine leaves to
X-Plane (no deck face, ``planar/structures``).  Graded as one lot, the
page's span pieces sit on the ground UNDER the bridge (the lower road) and
the page's own cap drags its approaches down the bank to them.  MEASURED
ESSA (lessa2 capture replayed at 9e809287b): ``dsf:pol192``
(``asphalt_1L.pol``, a parking lot by class) face 580 reaches from the west
bank top (lidar 30.3 m) under bridge way -1063 to the motorway cutting
(22.5 m); its 5 % rows held the bank top at 24.2-24.3 m (6.0 m under its
ground), and the road page ``dsf:pol204`` beside it pulled service way
-2811's foot to 27.27 m, 2.25 m under its lidar at 59.642114, 17.936146.

THE WITNESS (geometry and the map only -- RULINGS 05e): a groundside road or
lot face (the classes ``constraints/roads.road_within_shape`` prices) that a
mapped bridge's centreline crosses (``deck_signature.is_bridge_way``; a
bridge the structures built a DECK for is graded as that deck and is out).
Its SPAN vertices are those whose foot on the bridge's centreline falls
strictly between the way's two ends and that stand within the REACH of it:
the way's ribbon half-width (``road_ways.ribbon_half_width_m``) plus one
ribbon (``[road_contact] pair_lateral_m``, the reach ``airport/road_ramp.
_feet_index`` adds for a road's far kerb).  Its APPROACH vertices stand
beyond one of the way's ends, within the reach of the centreline carried on
past that end.  A face is the bridge's CARRIED page when it holds both: the
page runs along the bridge's own course, off the bank and over the span.  A
road the bridge passes OVER (its page crossing under the span, no vertex
beyond the bridge's ends) is not carried and keeps its grade.

Geometry only: the rows yield in ``constraints/bridge_span_release`` and the
census lift is ``pipeline/publication.lifted_caps``'.  Nothing here names a
pack, a resource or an airport."""
from __future__ import annotations

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import family
from ..model.planar import PlanarMap, face_vertex_set
from .deck_signature import is_bridge_way
from .road_ways import ribbon_half_width_m

__all__ = ["bridge_span_faces"]

_SPAN, _APPROACH = 1, 2

#: the groundside classes without a cross-section axis that
#: ``constraints/roads.road_within_shape`` prices beside the road family
_SPAN_ROLES_EXTRA = ("groundside_pavement", "parking_lot")


def _bridges(pm: PlanarMap, airport, law: Law) -> list[tuple[LineString, float]]:
    """``(centreline, lateral reach)`` per mapped bridge with no deck face."""
    decked = {int(d.way) for tn in pm.structures for d in tn.decks}
    ribbon = float(law.tables.emit.road_contact.pair_lateral_m)
    out = []
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = w.tags or {}
        if not is_bridge_way(tags) or len(w.points) < 2:
            continue
        try:
            if int(w.id) in decked:
                continue
        except (TypeError, ValueError):
            pass
        ln = LineString(w.points)
        if ln.length > 0.0:
            out.append((ln, ribbon_half_width_m(tags, law) + ribbon))
    return out


def _place(ln: LineString, reach: float, p: Point, eps: float) -> int:
    """:data:`_SPAN`, :data:`_APPROACH` or 0 for one vertex and one bridge."""
    t = ln.project(p)
    if eps < t < ln.length - eps:
        return _SPAN if ln.distance(p) <= reach else 0
    cs = list(ln.coords)
    (ax, ay), (bx, by) = (cs[0], cs[1]) if t <= eps else (cs[-1], cs[-2])
    dx, dy = ax - bx, ay - by          # outward along the end's segment
    n = (dx * dx + dy * dy) ** 0.5
    if n == 0.0:
        return 0
    ux, uy = dx / n, dy / n
    px, py = p.x - ax, p.y - ay
    beyond = px * ux + py * uy
    return _APPROACH if beyond > 0.0 and abs(px * uy - py * ux) <= reach else 0


def bridge_span_faces(pm: PlanarMap, law: Law, airport
                      ) -> dict[int, frozenset[int]]:
    """``{face id: its span vertices}`` for every groundside road / lot face
    a deckless mapped bridge CARRIES (module docstring): a face of those
    classes, no bridge deck, holding span and approach vertices of one
    bridge.  Every other face is absent."""
    bridges = _bridges(pm, airport, law)
    if not bridges:
        return {}
    roles = set(family(law, "road_cross_section").roles) | set(_SPAN_ROLES_EXTRA)
    decks = {d.ref for tn in pm.structures for d in tn.decks}
    tree = STRtree([ln for ln, _r in bridges])
    eps = float(law.tables.emit.identity.min_distinct_spacing_m)
    out: dict[int, frozenset[int]] = {}
    for fid, f in pm.faces.items():
        if f.role not in roles or f.ref in decks:
            continue
        ring = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
        if len(ring) < 3:
            continue
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0.0)
        vs = face_vertex_set(pm, f)
        span: set[int] = set()
        for k in tree.query(poly, predicate="intersects"):
            ln, reach = bridges[int(k)]
            at = {v: _place(ln, reach, Point(pm.vertices[v].xy), eps) for v in vs}
            if _APPROACH in at.values():
                span.update(v for v, x in at.items() if x == _SPAN)
        if span:
            out[int(fid)] = frozenset(span)
    return out
