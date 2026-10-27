"""THE GROUND UNDER A WALLED PLATE NEVER RISES THROUGH IT (owner RULINGS
2026-10-27t / 2026-10-27u, #1201; spec ``docs/specs/walled-plate-rsa-spec.md``
§5 (2)).

A runway-end walled plate (``Airport.walled_plates``, recognised by
``airport/walled_plate``) is seated with its top flush with the safety area at
its inner edge (27u), and the safety area ends there (27t, ``model/end_area``).
Under the plate the ground is hidden — the step from the safety area down to
the road at the wall's foot happens there, in the heightfield — and it must
never stand above the plate: every map vertex inside the plate's footprint, off
its inner edge and off the safety area's own faces, takes a HARD ceiling
(``[design] hard_rulings``, ranked in the pad tier over the groundside rows)

    z(v) <= lowest DEM at the seat's stations - under_clearance_m

— a CONSTANT, so the vertex under the plate follows and the safety area is
never lifted by it (airside is king).  MEASURED, refuted on the KSEA replay: a
two-way row against the inner-edge vertex lifted the safety area 4.0 m to the
road mapped on the plate; a one-way hard row read its leader at the solve's
initial 0 m and sank the road to it.

Geometry only: no airport is named here (RULINGS 2026-10-05e).  KSEA: the
service road mapped on 16R's plate stood +14.1 m over its DEM.
"""
from __future__ import annotations

import numpy as np

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Band, Row, Source
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
        top = _station_ground(airport, p)
        if top is None:
            continue
        edge = LineString(p.inner)
        inside = prep(foot.buffer(-0.25))
        src = Source("walled_plate_under", RULING, tuple(p.ids))
        for v in planar.vertices.values():
            pt = Point(v.xy)
            if edge.distance(pt) <= _ON_EDGE_M or not inside.contains(pt):
                continue
            if any(f in band for f in v.incident_faces):
                continue            # the safety area's own ground is its law's
            out.append(Band(int(v.id), None, top - clear, src))
    return out


def _station_ground(airport: Airport, p) -> "float | None":
    """The LOWEST DEM sample at the plate's seat stations: a constant the
    plate's top (the safety area's solved ground at those stations, the seat)
    stands at or above wherever the safety area is graded in fill — KSEA's
    three plates stand 0–2 m over their DEM."""
    dem = getattr(airport, "dem", None)
    if dem is None or not p.stations:
        return None
    z = np.array([float(dem.z(float(x), float(y))) for x, y in p.stations])
    z = z[np.isfinite(z)]
    return float(np.min(z)) if z.size else None
