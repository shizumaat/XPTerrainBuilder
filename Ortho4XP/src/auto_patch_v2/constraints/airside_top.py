"""AN ENTRANCE FACE'S TOP IS FLUSH WITH THE AIRSIDE IT ABUTS (#1737; owner
2026-11-02 ENGM: "Tunnel mouth object ... is floating, not seated with top
flush to apron area"; RULINGS 2026-11-06c (5) "the mouth object seated so
it's bottom sits at the bottom of the ramp and it's top is at grade",
2026-11-06d (5) "the airside pavement must grade smoothly to the object
edge", 2026-10-27r "the top of the objects flush with the airside surface";
airside is king: the apron keeps its own law).

An ENTRANCE face (``trench_objects.mouth_portals``) is seated with its top
on the surveyed ground over it -- the highest DEM sample over its top plan --
and its bottom on the mouth's floor.  Where AIRSIDE pavement (a §20b stage-1
face) abuts that top plan, the ground at grade IS the pavement, and the
pavement is graded by its own law, not to the DEM: MEASURED ENGM's north
rail portal (``Ham3.obj``, a lid 0.17-0.46 m over its zero, walls 8.5 m
under it), the apron at its edge solved 2.3-3.2 m under the DEM max its top
was seated on, and the object stood that far proud of it.  So the face's
SEAT is the mean of the airside vertices within ``[tunnel.object]
entrance_airside_reach_m`` of its top plan, read off the SOLVED surface:

* the mouth's floor is that mean less the face's height (top - bottom) --
  the two one-sided rows of the mouth-depth idiom (``edge_floor.seat_pair``,
  head ``tunnel.mouth_depth_m``, hard), with the airside vertices constants
  of stage 2 (stage 1 solves the apron first and never reads the floor);
* the skirt's level piece, if it has one, is held level with it;
* the object stage seats the face's zero at that mean less its top y
  (``pipeline/rebake_inputs``, the entrance record's elevation).

A face no airside vertex reaches keeps its DEM seat.  Nothing here names a
pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from ..law import Law
from ..model.planar import PlanarMap

__all__ = ["top_seat", "top_seats", "solved_entrance_zeros", "TOP_FLUSH"]

#: the skirt's level-piece rows' ruling (the floor's is the mouth-depth head)
TOP_FLUSH = ("tunnel.mouth_depth_m (#1737: an entrance face's top is flush with the "
             "airside it abuts)")

#: ``(terms, height, top y)``: the seat as ``((vertex, weight), ...)`` summing
#: to one, the face's height (top - bottom) and its top over its zero
Seat = tuple[tuple[tuple[int, float], ...], float, float]


def _plan(rings):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = [Polygon(r) for r in rings if len(r) >= 3]
    polys = [p if p.is_valid else p.buffer(0) for p in polys]
    u = unary_union([p for p in polys if not p.is_empty]) if polys else None
    return None if u is None or u.is_empty else u


def top_seats(planar: PlanarMap, law: Law) -> dict[str, Seat]:
    """Tunnel id -> its entrance face's airside seat (module doc), for every
    tunnel whose ``entrance_top`` plan an airside vertex reaches."""
    tops = [tn for tn in getattr(planar, "structures", ()) or ()
            if getattr(tn, "entrance_top", ())]
    if not tops:
        return {}
    from shapely import distance, points

    from ..model.platform import stage_air_vertices
    air = sorted(stage_air_vertices(planar, law))
    if not air:
        return {}
    xy = np.array([planar.vertices[v].xy for v in air], dtype=float)
    reach = float(law.tables.structures.tunnel.object.entrance_airside_reach_m)
    out: dict[str, Seat] = {}
    for tn in tops:
        rings, top_y, height = tn.entrance_top
        plan = _plan(rings)
        if plan is None:
            continue
        x0, y0, x1, y1 = plan.bounds
        box = ((xy[:, 0] >= x0 - reach) & (xy[:, 0] <= x1 + reach)
               & (xy[:, 1] >= y0 - reach) & (xy[:, 1] <= y1 + reach))
        idx = np.flatnonzero(box)
        if not len(idx):
            continue
        near = idx[distance(plan, points(xy[idx])) <= reach]
        if not len(near):
            continue
        w = 1.0 / len(near)
        out[tn.id] = (tuple((air[int(k)], w) for k in near), float(height), float(top_y))
    return out


def top_seat(seats: _t.Mapping[str, Seat], tn) -> "tuple[tuple, float] | None":
    """``(terms, height)`` of ``tn``'s seat for ``edge_floor.seat_pair``, or
    ``None`` where its face meets no airside."""
    got = seats.get(getattr(tn, "id", ""))
    return None if got is None else (got[0], got[1])


def _solved_zero(seat: Seat, planar: PlanarMap,
                z_at: _t.Callable[[float, float], "float | None"]) -> "float | None":
    """The face's zero on the solved surface: the seat vertices' mean solved
    level (``z_at(x, y)``, the surface at a vertex's plan point) less its
    top y; ``None`` where the surface carries none of them."""
    acc, wsum = 0.0, 0.0
    for v, w in seat[0]:
        x, y = planar.vertices[v].xy
        z = z_at(float(x), float(y))
        if z is not None and np.isfinite(z):
            acc += w * float(z)
            wsum += w
    return None if wsum <= 0.0 else acc / wsum - seat[2]


def _surface_z_at(surface, to_xy, tol_m: float = 0.05
                 ) -> _t.Callable[[float, float], "float | None"]:
    """``z_at(x, y)`` over a graded ``surface``'s vertices (``.ll`` lat/lon,
    ``.z``; ``to_xy(lon, lat)`` the frame's): the solved level of the
    vertex standing within ``tol_m`` of the point, else ``None``."""
    vs = list(getattr(surface, "vertices", None) or ())
    if not vs:
        return lambda x, y: None
    xy = np.array([to_xy(v.ll[1], v.ll[0]) for v in vs], dtype=float)
    zs = np.array([float(v.z) for v in vs], dtype=float)

    def z_at(x: float, y: float) -> "float | None":
        d2 = (xy[:, 0] - x) ** 2 + (xy[:, 1] - y) ** 2
        k = int(np.argmin(d2))
        return float(zs[k]) if d2[k] <= tol_m * tol_m else None
    return z_at


def solved_entrance_zeros(planar: PlanarMap, law: Law, surface, to_xy) -> dict[str, float]:
    """Tunnel id -> its entrance face's zero on the solved ``surface``
    (:func:`_solved_zero`) for every tunnel :func:`top_seats` seats --
    the elevation the object stage's entrance record carries
    (``pipeline/rebake_inputs``)."""
    seats = top_seats(planar, law)
    if not seats or surface is None:
        return {}
    z_at = _surface_z_at(surface, to_xy)
    out = {}
    for tid, seat in seats.items():
        z = _solved_zero(seat, planar, z_at)
        if z is not None:
            out[tid] = z
    return out
