"""THE PATCH UNDER A HELD OBJECT READS THE CUT GROUND (#2053 round 3).

A ground object in the water seated on its bridges' far ends
(``airport/bridged_ground``) has the tile's ground under its plan cut to
its floor (``airport/terrain_cut``, owner RULINGS 2026-11-13k), and the
mesh holds that cut (THE HOLD).  But the patch's own vertices under the
plan (the roads, lots and courts the map draws on the island) carry the
UNCUT DEM: Ortho4XP pins them (INTERP_ALT, ``alt_abs``) where the mesh
cannot hold them, and the attribute-0 triangles round them ramp up from
the open ground through the object (SBRJ: 1.44 m at the island's
south-west road).

THE VALUE.  At the planar site (``planar/build``, the fourth substitution
of ``Vertex.dem_z`` after ``covered_ground`` #714, ``road_shadow`` #951
and ``bridge_ground`` #1935), every vertex no airside face carries reads
the lower of its DEM and the cut surface there
(``geom/terrain_deck.target_at`` of ``terrain_cut.cut_fit`` at the
model's own seat, ``fill`` off): CUT ONLY, never raised.  Airside vertices
keep their DEM (airside is king) and are counted.  The seat
(``bridged_ground``'s models) was read before, on the uncut DEM, and
stays.  A terrain model (``seat_by`` empty) is not read here: its cut has
no riders and the patch over it is the DEM's.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..geom.terrain_deck import target_at
from . import terrain_model as _tm
from .bridged_ground import SEAT_BY
from .terrain_cut import ERODE_M, cut_fit

__all__ = ["ObjectGround", "object_ground"]


@_dc.dataclass
class ObjectGround:
    """What the object ground did at the planar site (the build's line)."""

    models: list[str] = _dc.field(default_factory=list)
    vertices_inside: int = 0
    vertices_lowered: int = 0
    max_lower_m: float = 0.0
    max_xy: tuple[float, float] | None = None
    airside_inside: int = 0

    def line(self) -> str:
        at = f" at ({self.max_xy[0]:.0f}, {self.max_xy[1]:.0f})" if self.max_xy else ""
        return (f"object ground (#2053): {len(self.models)} held object(s) "
                f"{self.models}, {self.vertices_inside} vertex(es) under them, "
                f"{self.vertices_lowered} lowered to the cut ground, max "
                f"{self.max_lower_m:.2f} m{at}; airside vertices inside (kept): "
                f"{self.airside_inside}")


def _cuts(airport: _t.Any) -> list:
    """``(id, TerrainFit)`` of every held model's cut, in the airport frame."""
    out = []
    for oid, _dpath, m, lift in getattr(airport, "terrain_models", ()) or ():
        if oid != m.id or getattr(m, "seat_by", "") != SEAT_BY or not getattr(m, "file", ""):
            continue
        grid = _tm.plan_grid(m.file)
        if grid is None:
            continue
        erode = m.erode_m if m.erode_m is not None else ERODE_M
        fit = cut_fit(grid, m.z0 + float(lift or 0.0), m.heading, erode,
                      float(getattr(m, "cut_floor_m", 0.0)))
        out.append((str(oid), _dc.replace(fit, xy=(float(m.xy[0]), float(m.xy[1])))))
    return out


def object_ground(airport: _t.Any, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray,
                  airside: _t.AbstractSet[int]) -> tuple[np.ndarray, ObjectGround]:
    """THE PLANAR SITE (module doc): ``zs`` with every vertex under a held
    object's plan that no airside face carries lowered to the cut ground;
    and the report."""
    cuts = _cuts(airport)
    rep = ObjectGround(models=[oid for oid, _f in cuts])
    out = np.array(zs, dtype=float, copy=True)
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    for _oid, fit in cuts:
        cut, inside = target_at(fit, xs, ys, out)
        for v in (int(i) for i in np.flatnonzero(inside)):
            rep.vertices_inside += 1
            if v in airside:
                rep.airside_inside += 1
                continue
            here = float(out[v])
            if not math.isfinite(here) or not cut[v] < here:
                continue
            out[v] = float(cut[v])
            rep.vertices_lowered += 1
            if here - cut[v] > rep.max_lower_m:
                rep.max_lower_m, rep.max_xy = here - float(cut[v]), (float(xs[v]), float(ys[v]))
    return out, rep
