"""THE GROUND ON AND UNDER A RUNWAY-END WALLED PLATE (owner RULINGS
2026-10-27t, #1201) — which map vertices a recognised plate
(``Airport.walled_plates``, ``airport/walled_plate``) stands on or hides.
Geometry only, kept apart from the recogniser so the target channels that
read it (``airport/road_ramp``) do not key on the pack stage's code."""
from __future__ import annotations

__all__ = ["vertices_on_plates", "under_plate_vertices", "UNDER_EDGE_M"]


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
