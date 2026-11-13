"""THE OBJECT FLOOR'S PINS (#1903, owner 2026-11-06T00:07Z: "a simple
continuous trench tracing the whole object"): every vertex of a trench
object's footprint face (``planar/object_floor_cells``, ref
``object_floor:<id>``) is pinned UNDER the object's own floor over it — the
lowest of its placed floor faces there (``airport/object_floor.floor_z_at``),
plates and ramps alike, end to end to the lips — by ``[tunnel.object]
floor_clearance_m`` (owner RULINGS 2026-11-06d (4): "the cut is deep enough
that it's completely below the floor so the floor is visible"; 2026-11-10o
(1)).  No station, no axis, no descent law: the object states the surface
and the pins are the law.

THE RIM AT THE FRAME'S TOP (2026-11-06d (5), #1921 / #1936): every vertex
of the cut's rim — the void band's outer ring — that no road, runway or
other structure carries is pinned at the frame's top there
(``ObjectFloor.rim_tops``, ``airport/floor_rim``): the taxiway crossing a
tunnel roof is held flush with the roof's edge and the ground meets the
walls' top edge; the solve grades what lies beyond to them.
"""
from __future__ import annotations

import numpy as np

from ..geom.lowest_face import floor_z_at
from ..law import Law
from ..law.tables import road_family_roles
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap
from ..model.structures import OBJECT_FLOOR_REF as FLOOR_REF
from ..model.structures import OBJECT_FLOOR_WALL_REF as FLOOR_WALL_REF

__all__ = ["GEN", "object_floor_pins"]

GEN = "object_floor"
#: a ring vertex the map placed this far outside its floor's faces still
#: reads the nearest face's plane (the ring's densified chords, snapping)
_EDGE_M = 1.0
#: the roles whose own law carries a rim vertex they share (the runway is
#: king, a road keeps its profile, another structure its own datum)
_KEEP_ROLES = ("runway", "runway_crossing", "tunnel_ramp", "tunnel_trench")


def object_floor_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One senior ``Pin`` per vertex of every object floor's cut face, and
    one per rim vertex at the frame's top (module doc)."""
    floors = {f.id: f for f in (getattr(planar, "object_floors", ()) or ())}
    if not floors:
        return []
    clearance = float(law.tables.structures.tunnel.object.floor_clearance_m)
    by_floor: dict[str, set[int]] = {}
    rim_of: dict[str, set[int]] = {}
    wall_of = {FLOOR_WALL_REF + fid[len(FLOOR_REF):]: fid for fid in floors}
    for f in planar.faces.values():
        fid = f.ref.split("#")[0]
        if f.role == "tunnel_trench" and fid in floors:
            vs = by_floor.setdefault(fid, set())
        elif f.role == "retaining_wall" and fid in wall_of:
            vs = rim_of.setdefault(wall_of[fid], set())
        else:
            continue
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
                     "is the cut over its whole footprint; RULINGS 2026-11-06d (4): the cut "
                     f"{clearance:g} m beneath it", (fid, fl.object_id))
        for v, z in zip(ids, zs.tolist(), strict=True):
            if z == z:                      # nan: no face within reach
                rows.append(Pin(v, float(z) - clearance, src))
    keep = set(_KEEP_ROLES) | set(road_family_roles(law))
    pinned = {r.v for r in rows}
    own = {fid: w for w, fid in wall_of.items()}
    for fid, vs in sorted(rim_of.items()):
        got = _rim_pins(planar, floors[fid], own[fid], sorted(vs - pinned), keep, law)
        pinned.update(r.v for r in got)
        rows.extend(got)
    return rows


def _rim_pins(planar: PlanarMap, fl, wall_ref: str, rim: list[int], keep: set[str],
              law: Law) -> list[Row]:
    """The rim vertices ``rim`` of floor ``fl`` pinned at its frame's top
    (module doc): the nearest ``rim_tops`` sample within one
    ``wall_sample_m``; a vertex a ``keep`` role shares, or another
    structure's void band (``retaining_wall`` of any ref but ``wall_ref``,
    the floor's own), is left to it, and one no surface shares is left
    alone."""
    tops = getattr(fl, "rim_tops", ()) or ()
    if not tops or not rim:
        return []
    from scipy.spatial import cKDTree
    T = np.asarray(tops, float)
    tree = cKDTree(T[:, :2])
    reach = float(law.tables.structures.tunnel.object.wall_sample_m)
    src = Source(GEN, "RULINGS 2026-11-06d (5) (#1921 / #1936): the pavement and the ground "
                 "meet a trench object's frame at its top edge", (fl.id, fl.object_id))
    rows: list[Row] = []
    for v in rim:
        faces = [planar.faces[f] for f in planar.vertices[v].incident_faces]
        if any(f.role in keep or (f.role == "retaining_wall"
                                  and f.ref.split("#")[0] != wall_ref) for f in faces):
            continue
        if all(f.ref.split("#")[0] == wall_ref for f in faces):
            # the band's own vertex alone (the patch ends there): no surface
            # meets the object at it, and the mesh draws the ground beyond
            # (MEASURED legll1E1: 35 such rim nodes pinned at the top drew
            # 1-4.3 m under it, the drawn gate's patch->drawn rows)
            continue
        d, k = tree.query(planar.vertices[v].xy)
        if d <= reach:
            rows.append(Pin(v, float(fl.zero_z + T[k, 2]), src))
    return rows
