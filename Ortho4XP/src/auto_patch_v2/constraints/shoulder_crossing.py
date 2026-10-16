"""THE SHOULDER A TAXI ROUTE CROSSES (owner RULINGS 2026-10-16a, master's
reading (i), under 15l): where a taxi route crosses a runway SHOULDER —
the runway-family pavement beyond the runway's own half-width (§40 (2)) —
the TAXIWAY's law governs the pavement it crosses; the shoulder's own
transverse slope (``runway.shoulder_transverse_max``, FAA Table 3-6 S-2's
5 %) applies only to shoulder no taxi route crosses.

ONE predicate at the derivation site: a shoulder vertex within the route
edge's own pavement half-width (``tables.taxi_half_width_m`` by its 1202
width class) of an apt.dat 1202 TAXI ROUTE edge — the route itself, which
runs on across the shoulder where the taxiway's centreline breakline stops
at its own face — takes that
taxiway's LONGITUDINAL cap as its slope beyond the half-width (the route
runs across the shoulder, so the taxiway's along-route grade is the law
there).  The generator reads it (``runway_profile.runway_transverse``);
the sidecar publishes it (``shoulder_taxi_crossings``: ``[lat, lon,
cap]``) and v2 verify and the census read that list, never a second
derivation."""
from __future__ import annotations

from ..law import Law
from ..law.tables import role_cap, taxi_half_width_m
from ..model.airport import Airport
from ..model.planar import PlanarMap
from .precedence import view
from .runway_profile import runway_half_widths

__all__ = ["crossed_shoulder_caps"]

_LAST: list = []


def crossed_shoulder_caps(planar: PlanarMap, law: Law, airport: Airport
                          ) -> dict[int, float]:
    """Shoulder vertex id -> the crossing taxiway's longitudinal cap."""
    key = (id(planar), id(law), id(airport))
    if _LAST and _LAST[0] == key:
        return dict(_LAST[1])
    from shapely.geometry import LineString, Point
    from shapely.strtree import STRtree
    vw = view(planar, law)
    half_of = runway_half_widths(airport)
    axes = {rw.id: rw for rw in airport.runways}
    lines, caps = [], []
    nodes = getattr(airport, "taxi_nodes", None) or {}
    for e in getattr(airport, "taxi_edges", None) or ():
        if e.is_runway or e.a not in nodes or e.b not in nodes:
            continue
        hw = taxi_half_width_m(law, e.width_class)
        rc = role_cap(law, "primary_parallel", None, e.width_class)
        if not hw or rc is None:
            continue
        lines.append(LineString([nodes[e.a].xy, nodes[e.b].xy]).buffer(float(hw)))
        caps.append(float(rc.longitudinal))
    out: dict[int, float] = {}
    if lines:
        tree = STRtree(lines)
        for f in vw.faces_of_role(("runway",)):
            rw, half = axes.get(f.ref), half_of.get(f.ref, 0.0)
            if rw is None or half <= 0.0 or rw.length_m <= 0.0:
                continue
            (ax, ay), (bx, by) = rw.ends[0].xy, rw.ends[1].xy
            ux, uy = (bx - ax) / rw.length_m, (by - ay) / rw.length_m
            for v in vw.face_vertices(f.id):
                x, y = vw.xy[v]
                if abs(-(x - ax) * uy + (y - ay) * ux) <= half:
                    continue                      # the runway proper
                pt = Point(x, y)
                hit = [caps[i] for i in tree.query(pt) if lines[i].covers(pt)]
                if hit:
                    out[v] = max(hit)
    _LAST[:] = [key, dict(out)]
    return out
