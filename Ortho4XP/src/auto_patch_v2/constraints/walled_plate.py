"""THE GROUND UNDER A WALLED PLATE NEVER RISES THROUGH IT (owner RULINGS
2026-10-27t / 2026-10-27u, #1201; spec ``docs/specs/walled-plate-rsa-spec.md``
§5 (2)).

A runway-end walled plate (``Airport.walled_plates``, recognised by
``airport/walled_plate``) is seated with its top flush with the safety area at
its inner edge (27u), and the safety area ends there (27t, ``model/end_area``).
Under the plate the ground is hidden — the step from the safety area down to
the road at the wall's foot happens there, in the heightfield — and it must
never stand above the plate: every map vertex inside the plate's footprint, off
its inner edge, takes a one-sided row

    z(inner) - z(v) >= under_clearance_m

against the safety-area vertex nearest it on the inner edge (the plate's level
is that vertex's, by the seat), or, where no graded vertex stands on the inner
edge, ``z(v) <= median DEM at the seat's stations - under_clearance_m`` (the
mesh there is the DEM, which is what the seat then reads).  ONE-WAY and HARD
(``[design] one_way_rulings`` / ``hard_rulings``): the vertex under the plate
follows, the safety area leads — a road mapped on top of the plate never lifts
the safety area (airside is king).

Geometry only: no airport is named here (RULINGS 2026-10-05e).  KSEA: the
service road mapped on 16R's plate stood +14.1 m over its DEM.
"""
from __future__ import annotations

import numpy as np

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Band, Linear, Row, Source
from ..model.planar import PlanarMap

__all__ = ["RULING", "under_plate_rows"]

#: the ruling head ``[design] hard_rulings`` / ``one_way_rulings`` list
RULING = "structures.walled_plate under-plate cap (RULINGS 2026-10-27t/u, #1201)"

#: a vertex this close to the inner edge IS on it (m): the safety area's own
#: end, never capped against itself
_ON_EDGE_M = 2.5


def under_plate_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """The rows (module docstring), every walled plate of ``airport``."""
    plates = tuple(getattr(airport, "walled_plates", ()) or ())
    if not plates:
        return []
    from shapely.geometry import LineString, Point, Polygon
    from shapely.prepared import prep
    clear = float(law.tables.structures.walled_plate.under_clearance_m)
    band = {f.id for f in planar.faces.values() if f.role == "graded_strip"}
    out: list[Row] = []
    for p in plates:
        foot = Polygon(p.footprint)
        if not foot.is_valid:
            foot = foot.buffer(0.0)
        if foot.is_empty or len(p.inner) < 2:
            continue
        edge = LineString(p.inner)
        inside = prep(foot.buffer(-0.25))
        refs, under = [], []
        for v in planar.vertices.values():
            pt = Point(v.xy)
            d = edge.distance(pt)
            if d <= _ON_EDGE_M and any(f in band for f in v.incident_faces):
                refs.append(v)
            elif d > _ON_EDGE_M and inside.contains(pt):
                under.append(v)
        if not under:
            continue
        src = Source("walled_plate_under", RULING, tuple(p.ids))
        if refs:
            rxy = np.array([r.xy for r in refs])
            for v in under:
                r = refs[int(np.argmin(np.hypot(rxy[:, 0] - v.xy[0], rxy[:, 1] - v.xy[1])))]
                out.append(Linear(((int(r.id), 1.0), (int(v.id), -1.0)), clear, None, src,
                                  follows=int(v.id)))
            continue
        top = _station_ground(airport, p)
        if top is None:
            continue
        out.extend(Band(int(v.id), None, top - clear, src) for v in under)
    return out


def _station_ground(airport: Airport, p) -> "float | None":
    """The median DEM at the plate's seat stations (the ground its top meets
    where no graded vertex stands on its inner edge)."""
    dem = getattr(airport, "dem", None)
    if dem is None or not p.stations:
        return None
    z = np.array([float(dem.z(float(x), float(y))) for x, y in p.stations])
    z = z[np.isfinite(z)]
    return float(np.median(z)) if z.size else None
