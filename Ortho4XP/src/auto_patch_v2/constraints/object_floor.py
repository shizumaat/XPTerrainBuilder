"""THE OBJECT FLOOR'S PINS (#1903, owner 2026-11-06T00:07Z: "a simple
continuous trench tracing the whole object"): every vertex of a trench
object's footprint face (``planar/object_floor_cells``, ref
``object_floor:<id>``) is pinned at the object's own floor under it — the
lowest of its placed floor faces there (``airport/object_floor.floor_z_at``),
plates and ramps alike, end to end to the lips.  No station, no axis, no
descent law: the object states the surface and the pins are the law.
"""
from __future__ import annotations

import numpy as np

from ..airport.object_floor import floor_z_at
from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap

__all__ = ["GEN", "object_floor_pins"]

GEN = "object_floor"
#: a ring vertex the map placed this far outside its floor's faces still
#: reads the nearest face's plane (the ring's densified chords, snapping)
_EDGE_M = 1.0


def object_floor_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One senior ``Pin`` per vertex of every object floor's cut face."""
    floors = {f.id: f for f in (getattr(planar, "object_floors", ()) or ())}
    if not floors:
        return []
    by_floor: dict[str, set[int]] = {}
    for f in planar.faces.values():
        if f.role != "tunnel_trench":
            continue
        fid = f.ref.split("#")[0]
        if fid in floors:
            vs = by_floor.setdefault(fid, set())
            vs.update(planar.ring_vertices(f.ring))
            for h in getattr(f, "holes", ()) or ():
                vs.update(planar.ring_vertices(h))
    rows: list[Row] = []
    for fid, vs in sorted(by_floor.items()):
        fl = floors[fid]
        ids = sorted(vs)
        xy = np.array([planar.vertices[v].xy for v in ids], float)
        zs = floor_z_at(fl.faces, xy[:, 0], xy[:, 1], edge_m=_EDGE_M)
        src = Source(GEN, "owner 2026-11-06T00:07Z (#1903): the trench object's own floor "
                     "is the cut over its whole footprint", (fid, fl.object_id))
        for v, z in zip(ids, zs.tolist(), strict=True):
            if z == z:                      # nan: no face within reach
                rows.append(Pin(v, float(z), src))
    return rows
