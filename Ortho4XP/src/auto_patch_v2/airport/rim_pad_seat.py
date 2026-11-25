"""A PARTIAL SHELL THAT CARRIES AN AIRSIDE FLOOR IS SEATED ON ITS PAD
(issue #2197; RULINGS 2026-11-20r, 2026-11-16u: the unit seats on airside
and stays with the buildings it touches; airside is king).

``airport/ground_rim`` recognises a partial shell -- an origin set whose
outer rim is its author's ground -- and seats a set with no airside floor
as one rigid frame at its DEM fit.  A set whose plan touches airside
pavement (``ground_rim``, THE AIRSIDE FLOOR) is read like any object: the
planar holds its pad and the object stage seats its buildings on it
(§16g units).  Its RIM still travels (``Airport.rim_sets``), and this
module seats it, after the solve, where the pad puts the set:

THE PAD (:func:`pad_zero`): among the solved surface's ``building`` faces
(``placement_read.pads_rims_from_graded_doc``, the pads the object stage
reads), the REF holding the most of the set's ground contacts (its
``feet``: per plan cell the lowest surface); the set's zero is the median
over the contacts on that pad of the pad's plane (the least-squares plane
of its ring heights, every face of the ref folded) less the contact's
authored ``y`` -- the generic anchor's on-pad median (``anchor_rule``,
§16d (6)) read over the set as one frame.  No contact on any pad: the rim
keeps the DEM-fit ``z0`` it was recognised at.

THE RECORD (:func:`seat_records`): one ``RebakePlan.authored_seats``
record on the set's first row, seat :data:`SEAT`, carrying the ``rim``
(``ground_rim.rim_record``) with every station moved by the pad's zero
less the DEM fit.  :data:`SEAT` is no row seat (``terrain_shaped.
row_seats`` writes none): the object stage's own seat stands, and the
tile build grades our free ground to the rim
(``terrain_cut_stage.rim_records``).

Nothing here names a pack, an object or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

__all__ = ["SEAT", "pad_zero", "seat_records"]

#: the seat record's ``seat`` value (module doc, THE RECORD)
SEAT = "partial shell on its pad"


def _pads(surface: _t.Any, to_xy: _t.Callable) -> list[tuple[str, _t.Any, np.ndarray]]:
    """``(ref, polygon, plane)`` per pad ref of the solved ``surface``:
    the frame-metre polygon of every face of the ref and the coefficients
    ``(a, b, c)`` of its plane ``z = a x + b y + c``."""
    import shapely
    from shapely.geometry import Polygon

    from .placement_read import pads_rims_from_graded_doc
    pads, _rims = pads_rims_from_graded_doc(surface.to_dict())
    by: dict[str, list] = {}
    for p in pads:
        by.setdefault(p.ref, []).append(p)
    out = []
    for ref, faces in sorted(by.items()):
        polys, pts = [], []
        for p in faces:
            xy = [tuple(to_xy(lon, lat)) for lat, lon in p.ring]
            g = Polygon(xy)
            polys.append(g if g.is_valid else g.buffer(0))
            pts += [(x, y, z) for (x, y), z in zip(xy, p.z, strict=False)]
        if len(pts) < 3:
            continue
        P = np.asarray(pts, dtype=float)
        co, *_ = np.linalg.lstsq(np.c_[P[:, 0], P[:, 1], np.ones(len(P))], P[:, 2],
                                 rcond=None)
        out.append((ref, shapely.union_all(polys), co))
    return out


def pad_zero(rs: _t.Any, pads: _t.Sequence[tuple]) -> "tuple[str, float] | None":
    """THE PAD (module doc) of the ``ground_rim._RimSet`` ``rs`` among
    ``pads`` (:func:`_pads`): ``(ref, zero)``, or ``None``."""
    import shapely
    if rs.feet is None or not len(rs.feet):
        return None
    x = rs.xy[0] + rs.feet[:, 0]
    y = rs.xy[1] + rs.feet[:, 1]
    best = None
    for ref, poly, co in pads:
        on = shapely.intersects_xy(poly, x, y)
        if on.any() and (best is None or int(on.sum()) > best[0]):
            best = (int(on.sum()), ref, on, co)
    if best is None:
        return None
    _n, ref, on, co = best
    z = co[0] * x[on] + co[1] * y[on] + co[2]
    return ref, float(np.median(z - rs.feet[on, 2]))


def seat_records(rim_sets: _t.Sequence[tuple], surface: _t.Any, to_xy: _t.Callable,
                 to_ll: _t.Callable) -> list[dict[str, _t.Any]]:
    """THE RECORD (module doc) of every ``Airport.rim_sets`` row ``(id,
    def path, _RimSet)`` on the solved ``surface``; ``to_xy(lon, lat)``
    and ``to_ll(x, y)`` the airport frame's."""
    from .ground_rim import rim_record
    if not rim_sets or surface is None:
        return []
    pads = _pads(surface, to_xy)
    out = []
    for oid, dpath, rs in sorted(rim_sets, key=lambda r: str(r[0])):
        got = pad_zero(rs, pads)
        ref, z0 = got if got is not None else ("", rs.z0)
        st = np.array(rs.stations, dtype=float, copy=True).reshape(-1, 3)
        st[:, 2] += z0 - rs.z0
        seated = _dc.replace(rs, z0=z0, stations=st)
        out.append({"id": str(oid), "resource": dpath, "datum": "terrain", "seat": SEAT,
                    "elevation": round(z0, 3), "pad": ref, "fit": round(rs.z0, 3),
                    "rim": rim_record(seated, to_ll)})
    return out
