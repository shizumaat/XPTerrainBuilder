"""THE ROAD UNDER A PACK'S ELEVATED STRUCTURE KEEPS ITS CLEARANCE (owner
RULINGS 2026-11-20g (3) / 20k: "the remaining clearance comes from 20g (3)
ramps"; ``airport/crossing_seat`` reads the crossings at load).

Every crossing still short at its frame's seat (``Airport.elevated_
crossings``) puts ONE hard ceiling ``Band`` on every map vertex inside its
cells' region: the frame's seat plus the least authored soffit ``y`` there,
less the crossed way's class minimum -- ``model/road_clearance.
design_clearance_m``, 4.2 m over a small road, 5.0 m over every other road
and rail.  The road's own profile and ramp rows (road grade law: 5 %
design, the 10 % cap) carry the ramp down to it; the ways were densified
under the region at load, so the ceiling has vertices to bind.  Only a
ROAD-family vertex takes a row, and never one an AIRSIDE face shares:
airside is king.  A RAIL crossing mints nothing yet -- no face carries a
rail (no ribbon class): its corridor comes first (RULINGS 2026-11-20k).  Groundside law (the
``groundside`` tier); the lowest ceiling over a vertex wins.  Nothing here
names an airport; no crossing, no row.
"""
from __future__ import annotations

from shapely.geometry import Point, Polygon
from shapely.prepared import prep

from ..law.tables import road_family_roles, role_side
from ..model.constraints import Band, Row, Source

__all__ = ["elevated_clearance_rows", "GEN", "RULING"]

GEN = "elevated_clearance"
#: the ruling HEAD ``[design] hard_rulings`` names
RULING = "structures.elevated crossing clearance under the soffit (owner RULINGS 2026-11-20g)"


def elevated_clearance_rows(planar, law, airport) -> list[Row]:
    """One hard ceiling per map vertex under each short crossing (module
    doc)."""
    recs = tuple(getattr(airport, "elevated_crossings", ()) or ())
    if not recs:
        return []
    roads = set(road_family_roles(law))

    def road_vertex(v: int) -> bool:
        roles = planar.roles_at(v)
        return (any(r in roads for r in roles)
                and not any(role_side(law, r) == "airside" for r in roles))
    lo: dict[int, tuple[float, Source]] = {}
    for r in recs:
        if not str(r.get("kind", "")).startswith("highway="):
            continue
        region = Polygon(r["region"])
        if region.is_empty or not region.is_valid:
            continue
        z = float(r["zero"]) + float(r["soffit_y"]) - float(r["need"])
        src = Source(GEN, RULING, (f"crossing:{r['member']}#{r['comp']}", f"osm:{r['way']}"))
        pr, (x0, y0, x1, y1) = prep(region), region.bounds
        for v, vx in planar.vertices.items():
            x, y = vx.xy
            if not (x0 <= x <= x1 and y0 <= y <= y1) or not pr.covers(Point(x, y)) \
                    or not road_vertex(v):
                continue
            if v not in lo or z < lo[v][0]:
                lo[v] = (z, src)
    return [Band(v, None, z, src) for v, (z, src) in sorted(lo.items())]
