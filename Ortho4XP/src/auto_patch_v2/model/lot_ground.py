"""THE LOT FOLLOWS ITS GROUND (owner RULINGS 2026-11-25e (1), #2283 EKVG) —
which vertices are a groundside parking lot's own, with no level target.

``model`` holds the derivation because two packages read it and neither may
import the other (M0 §1): ``solve`` gives these vertices their weak DEM row
and ``constraints`` releases the road that leaves the lot among them.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..law.tables import family, role_side
from .planar import PlanarMap, face_vertex_set, is_car_lot_ref

__all__ = ["LOT_DATUM_ROLE", "is_datum_lot", "lot_datum_vertices", "lot_follower_vertices",
           "lot_road_faces"]

#: THE LOT ROLE that follows its ground (owner RULINGS 2026-11-25e (1)): a
#: groundside PARKING LOT; every other groundside body keeps its plane
LOT_DATUM_ROLE = "parking_lot"


def is_datum_lot(face) -> bool:
    """``face`` is a lot the datum reads: a parking lot of the main map.  A
    last-stage CAR LOT (``carlot:``) is not -- its own stage already gives
    its body its ground under the lot cap (``constraints/car_lot_follow``)
    with every standing level a constant."""
    return face.role == LOT_DATUM_ROLE and not is_car_lot_ref(face.ref)


def lot_road_faces(planar: PlanarMap, law: Law, lots: _t.AbstractSet[int]) -> set[int]:
    """THE ROADS IN A LOT ARE THE LOT (owner RULINGS 2026-10-14a (2): "a
    mapped road (or aisle) that runs inside or edge-shares a parking lot's
    pavement is part of that lot"; 14h's option (c), #684, "all after stage
    1 is insulated" -- the follower pass IS that insulation: every other
    vertex is a constant at its stage-2 level).  The ids of the road-family
    ribbons (the ``road_cross_section`` family's roles) that share a vertex
    with one of the datum lots ``lots``.  Their rows stay theirs (the road's
    10 % along, 2 % across); their vertices join the lot's datum.

    MEASURED EKVG (#2283, ``dsf:pol23``: the access road and its roundabout
    as one pack lot, 324 m over DEM 78.8-93.4 m, 80 of its 161 vertices
    shared with the OSM service ribbons laid in it): with the ribbons'
    vertices held at stage 2's 5 % body, the lot's own 32 could not follow
    their ground and the road band stood 2.0-3.4 m in its cut."""
    roles = set(family(law, "road_cross_section").roles)
    lot_v = {v for f in lots for v in face_vertex_set(planar, planar.faces[f])}
    return {f.id for f in planar.faces.values()
            if f.role in roles and role_side(law, f.role) == "groundside"
            and not lot_v.isdisjoint(face_vertex_set(planar, f))}


def lot_datum_vertices(planar: PlanarMap, law: Law) -> frozenset[int]:
    """THE LOT FOLLOWS ITS GROUND WITHIN ITS GRADE CAP (owner RULINGS
    2026-11-25e (1), #2283 EKVG; narrows 08t (1)'s "no DEM pull on a
    designed surface" for groundside lots only) -- the vertices that carry
    the weak per-vertex ``z = DEM`` row at ``[design] ground_datum``.

    A vertex qualifies when every face carrying it is a parking lot or a
    road in one (:func:`lot_road_faces`; a
    vertex an apron, a pad, another road or a building shares is that face's:
    its level is the pavement's, and airside is king), the lot it is on
    has NO LEVEL TARGET -- no follower pass levels it to a pad
    (``road_terrace['lot_level']['lots']``, ``pipeline/lot_follow``) and
    no road profile targets it (``PlanarMap.preferred_z``) -- and it has a
    DEM sample.  The lot's own grade rows (5 %, the law weight) outrank the
    datum, so the lot follows its DEM wherever the DEM is within its cap
    and grades at the cap where it is not.  MEASURED EKVG ``pav0#beyond1``
    (357 x 240 m over DEM 79-93 m): with no row of its own it took its
    neighbours' level, 83.9-87.3 m, a 6.2 m cut at its north road.

    THE SINGLE DERIVATION SITE: ``solve/design_assemble`` mints the rows
    and drops these vertices from the body plane it gives the rest,
    ``solve/design`` frees them from stage 1's levels, and
    ``pipeline/lot_neck`` releases the road leaving the lot among them."""
    preferred = getattr(planar, "preferred_z", None) or {}
    return frozenset(v for v in lot_follower_vertices(planar, law) if v not in preferred)


def _lot_faces(planar: PlanarMap, law: Law) -> set[int]:
    """The faces that follow their ground: every datum lot no follower pass
    levels to a pad (``road_terrace['lot_level']['lots']``) and the roads
    in them (:func:`lot_road_faces`)."""
    record = (getattr(planar, "road_terrace", None) or {}).get("lot_level") or {}
    levelled = {int(f) for f in record.get("lots") or ()}
    lots = {f.id for f in planar.faces.values() if is_datum_lot(f) and f.id not in levelled}
    return lots | lot_road_faces(planar, law, lots)


def lot_follower_vertices(planar: PlanarMap, law: Law) -> frozenset[int]:
    """The vertices the follower pass frees for a lot that follows its
    ground: :func:`lot_datum_vertices` plus the lot's vertices a road
    profile targets (``PlanarMap.preferred_z``).  Those take the profile's
    own ``road_fit`` row instead of the datum -- held at stage 2's level
    instead, they were the constants that kept the lot in its cut (MEASURED
    EKVG ``dsf:pol23`` vertex 62.06916, -7.27929: profile 91.21 m, DEM
    91.66, stage 2 88.74, and every lot vertex north of it chained to it at
    5 %)."""
    lots = _lot_faces(planar, law)
    lot_v: set[int] = set()
    held: set[int] = set()
    for f in planar.faces.values():
        vs = face_vertex_set(planar, f)
        if f.id in lots:
            lot_v |= vs
        else:
            held |= vs
    return frozenset(v for v in lot_v - held if planar.vertices[v].dem_z is not None)
