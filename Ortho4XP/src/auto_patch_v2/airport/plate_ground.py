"""THE GROUND ON AND UNDER A RUNWAY-END WALLED PLATE (owner RULINGS
2026-10-27t, #1201) — which map vertices a recognised plate
(``Airport.walled_plates``, ``airport/walled_plate``) stands on or hides.
Geometry only, kept apart from the recogniser so the target channels that
read it (``airport/road_ramp``) do not key on the pack stage's code."""
from __future__ import annotations

__all__ = ["vertices_on_plates", "under_plate_vertices", "plated_end_areas", "UNDER_EDGE_M"]


def vertices_on_plates(vertices, plates, edge_m: float) -> frozenset:
    """The ids of ``vertices`` (``id -> object with .xy``) standing ON a
    walled plate: inside its footprint or within ``edge_m`` of it.  The
    ground there is hidden by the plate and governed by its own ceiling
    (``constraints/walled_plate``), never by a road's ramp to the DEM
    (#1201 l1201c: that ramp at the inner edge pulled KSEA 16R's safety
    area 1.3 m under the plate)."""
    from shapely import points
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree
    polys = []
    for p in plates or ():
        g = Polygon(p.footprint)
        g = g if g.is_valid else g.buffer(0.0)
        if not g.is_empty:
            polys.append(g.buffer(edge_m))
    if not polys:
        return frozenset()
    ids = list(vertices)
    if not ids:
        return frozenset()
    tree = STRtree(points([vertices[k].xy for k in ids]))
    hit: set = set()
    for g in polys:
        hit.update(int(i) for i in tree.query(g, predicate="intersects"))
    return frozenset(ids[i] for i in hit)


#: a vertex this close to a plate's inner edge IS on it (m): the safety
#: area's own end, never under the plate
UNDER_EDGE_M = 2.5


def under_plate_vertices(pm, plates) -> frozenset:
    """The vertices UNDER the walled ``plates`` (#1201): inside a
    footprint, more than :data:`UNDER_EDGE_M` off its inner edge, and on
    no safety-area (``graded_strip``) face — the ground the plate hides."""
    from shapely import points
    from shapely.geometry import LineString, Polygon
    from shapely.strtree import STRtree
    plates = tuple(plates or ())
    if not plates or not pm.vertices:
        return frozenset()
    band = {f.id for f in pm.faces.values() if f.role == "graded_strip"}
    ids = [k for k, v in pm.vertices.items() if not any(f in band for f in v.incident_faces)]
    if not ids:
        return frozenset()
    pts = points([pm.vertices[k].xy for k in ids])
    tree = STRtree(pts)
    out: set = set()
    for p in plates:
        foot = Polygon(p.footprint)
        foot = foot if foot.is_valid else foot.buffer(0.0)
        if foot.is_empty or len(p.inner) < 2:
            continue
        edge = LineString(p.inner).buffer(UNDER_EDGE_M)
        for i in tree.query(foot.buffer(-0.25), predicate="contains"):
            if not edge.contains(pts[int(i)]):
                out.add(ids[int(i)])
    return frozenset(out)


def plated_end_areas(airport, law) -> tuple:
    """The END AREA of every runway end a walled plate caps (owner RULINGS
    2026-10-27t, #1201): the rectangle from the runway END to the plate's
    inner edge (``WalledPlate.inner_s``) over the safety area's width
    (``zone2_half_width_m`` each side, the band's own edges).  The safety
    area there is graded to meet the plate, not to its own ground, so a road
    at grade on it takes the safety area's level (28p (1))."""
    import math

    from shapely.geometry import Polygon

    from ..law.reference_code import runway_status
    from ..law.tables import zone2_half_width_m
    plates = tuple(getattr(airport, "walled_plates", ()) or ())
    rws = {rw.id: rw for rw in airport.runways}
    out = []
    for p in plates:
        rw = rws.get(p.runway)
        if rw is None:
            continue
        a, b = rw.ends[p.end].xy, rw.ends[1 - p.end].xy
        L = math.hypot(a[0] - b[0], a[1] - b[1])
        if L <= 0.0:
            continue
        ux, uy = (a[0] - b[0]) / L, (a[1] - b[1]) / L         # outward
        hw = float(zone2_half_width_m(law, "runway", rw.code_number, rw.code_letter,
                                      runway_status(rw)) or 0.0)
        s1 = float(p.inner_s)
        if hw <= 0.0 or s1 <= 0.0:
            continue
        px, py = -uy, ux
        out.append(Polygon([(a[0] + px * t + ux * s, a[1] + py * t + uy * s)
                            for s, t in ((0.0, -hw), (s1, -hw), (s1, hw), (0.0, hw))]))
    return tuple(out)
