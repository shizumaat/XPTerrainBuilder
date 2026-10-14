"""WHICH BASE SLABS DRAPE (owner RULINGS 2026-10-14d (1); lane drape229).

"Every pack base slab over sloping terrain is DRAPED: its up-facing faces
are re-emitted as OBJ8 draped geometry with the author's texture and UVs,
laid on the graded mesh; the rest of the object stays rigid; slabs over
level ground may stay rigid (no visible difference)."

THE SLABS are the base-slab witness's (``geom.base_slab.base_slabs`` with
the face reader ``airport.slab_faces.witness_faces`` — the SAME reading
the gap mint grades the ground under).  THE DECISION is read on the design
surface the object stage seats on: a slab whose open part spans more than
TWICE THE FOOT TOLERANCE of ground relief (``[placement] split_tol_m``,
0.3 m — the residual the feet census and the seat tilt already judge a
foot by) cannot lie on it as one level plate within that tolerance at
every point, so it is OVER SLOPING TERRAIN and drapes.  The test is the
ground's, never the author's sheet: a sheet the author modelled to their
own terrain (HECA ``T23/T3_road``, 3.9 m of authored relief) misfits ours
however it is seated, and draping a sheet that would have fit loses
nothing (it has no kerbs).

:func:`drape_plan` answers ``{member id: frozenset(component)}`` — what the
writer drapes (``obj8_split.BodyCut.drape``) — and one :class:`DrapeRow`
per slab piece for the report.  Nothing is written here.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np
import shapely

from ..geom.base_slab import base_slabs
from ..law.tables import base_slab_law
from . import placement_geom as _pg
from .slab_faces import witness_faces

__all__ = ["DrapeRow", "drape_plan", "drape_for_graded", "relief_m"]

#: how many surface reads one slab piece takes at most
_SAMPLES = 2000


class DrapeRow(_t.NamedTuple):
    """One slab piece's drape verdict."""

    member: str
    resource: str
    comp: int
    lat: float
    lon: float
    open_m2: float
    relief_m: float
    drape: bool
    touches: bool


def relief_m(poly: _t.Any, to_ll, surface) -> float:
    """The design surface's RANGE (max − min) over ``poly`` (planar
    metres), read on a regular grid of at most :data:`_SAMPLES` points and
    the polygon's own vertices; ``nan`` where the surface answers none."""
    x0, y0, x1, y1 = poly.bounds
    step = max(1.0, math.sqrt(max(poly.area, 1.0) / _SAMPLES))
    xs, ys = np.meshgrid(np.arange(x0 + 0.5 * step, x1, step),
                         np.arange(y0 + 0.5 * step, y1, step))
    xs, ys = xs.ravel(), ys.ravel()
    k = shapely.contains_xy(poly, xs, ys)
    ring = np.asarray(poly.exterior.coords)
    px = np.concatenate([xs[k], ring[:, 0]])
    py = np.concatenate([ys[k], ring[:, 1]])
    pts = []
    for x, y in zip(px.tolist(), py.tolist()):
        la, lo = to_ll(x, y)
        pts.append((float(la), float(lo), 0.0))
    zs = _pg.surface_many(surface, pts)
    return float(max(zs) - min(zs)) if zs else float("nan")


def drape_plan(partition: _t.Any, to_xy, to_ll, law: _t.Any, surface
               ) -> tuple[dict[str, frozenset[int]], tuple[DrapeRow, ...]]:
    """``(member id -> components to drape, the rows)`` for ``partition``
    (module doc).  ``to_xy(lon, lat)`` / ``to_ll(x, y) -> (lat, lon)`` are
    the build frame's; ``surface(lat, lon)`` the design surface."""
    lw = base_slab_law(law)
    tol = float(law.tables.structures.placement.split_tol_m)
    if partition is None or not lw.armed or tol <= 0.0:
        return {}, ()
    out: dict[str, set[int]] = {}
    rows: list[DrapeRow] = []
    for s in base_slabs(partition, to_xy, lw, witness_faces(lw)):
        rel = relief_m(s.open, to_ll, surface)
        drape = rel == rel and rel > 2.0 * tol
        if drape:
            out.setdefault(s.member, set()).add(int(s.comp))
        rp = s.open.representative_point()
        la, lo = to_ll(rp.x, rp.y)
        rows.append(DrapeRow(s.member, s.resource, int(s.comp), float(la),
                             float(lo), float(s.open.area), rel, drape,
                             bool(s.touches)))
    return {k: frozenset(v) for k, v in out.items()}, tuple(rows)


def drape_for_graded(partition: _t.Any, graded_doc: _t.Mapping, law: _t.Any,
                     surface) -> tuple[dict[str, frozenset[int]], _t.Any,
                                       tuple[DrapeRow, ...]]:
    """THE OBJECT STAGE'S ONE CALL: ``(drape set, the writer's law, rows)``
    for the rebake plan ``partition`` on the build's graded document — its
    FRAME is rebuilt exactly as the load built it (origin, CRS, identity
    and the entry quantum of the law), so the witness reads the same
    rings in the same metres the gap mint read them in."""
    from ..law.tables import input_quantum_m
    from ..model.frame import Frame
    from .obj8_drape import drape_law
    fr = (graded_doc or {}).get("frame") or {}
    if not fr.get("origin"):
        return {}, None, ()
    frame = Frame(str(graded_doc.get("icao", "")), tuple(fr["origin"]),
                  int(fr.get("identity_dp", 11)), str(fr.get("crs", "")),
                  input_quantum_m=float(input_quantum_m(law)))
    drape, rows = drape_plan(partition, frame.entry(), frame.transformers()[1],
                             law, surface)
    return drape, (drape_law(law) if drape else None), rows
