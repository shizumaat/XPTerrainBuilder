"""THE LOT FOLLOWS ITS GROUND (owner RULINGS 2026-11-25e (1), #2283 EKVG) —
which vertices are a groundside parking lot's own, with no level target.

``model`` holds the derivation because two packages read it and neither may
import the other (M0 §1): ``solve`` gives these vertices their weak DEM row
and ``constraints`` releases the road that leaves the lot among them.
"""
from __future__ import annotations

from .planar import PlanarMap

__all__ = ["LOT_DATUM_ROLE", "lot_datum_vertices"]

#: THE LOT ROLE that follows its ground (owner RULINGS 2026-11-25e (1)): a
#: groundside PARKING LOT; every other groundside body keeps its plane
LOT_DATUM_ROLE = "parking_lot"


def lot_datum_vertices(planar: PlanarMap) -> frozenset[int]:
    """THE LOT FOLLOWS ITS GROUND WITHIN ITS GRADE CAP (owner RULINGS
    2026-11-25e (1), #2283 EKVG; narrows 08t (1)'s "no DEM pull on a
    designed surface" for groundside lots only) -- the vertices that carry
    the weak per-vertex ``z = DEM`` row at ``[design] ground_datum``.

    A vertex qualifies when every face carrying it is a parking lot (a
    vertex an apron, a pad, a road or a building shares is that face's:
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
    ``constraints/lot_neck`` releases the road leaving the lot among them."""
    record = (getattr(planar, "road_terrace", None) or {}).get("lot_level") or {}
    levelled = {int(f) for f in record.get("lots") or ()}
    preferred = getattr(planar, "preferred_z", None) or {}
    lot_v: set[int] = set()
    held: set[int] = set()
    for f in planar.faces.values():
        vs = {v for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)}
        if f.role == LOT_DATUM_ROLE and f.id not in levelled:
            lot_v |= vs
        else:
            held |= vs
    return frozenset(v for v in lot_v - held
                     if v not in preferred and planar.vertices[v].dem_z is not None)
