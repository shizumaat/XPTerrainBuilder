"""AN AGP FOLLOWER'S GROUND FLOOR IS GRADED GROUND OF ITS OWN (#2090 C2;
spec ``2090-agp-group-groundside-spec.md`` C2 and amendment C; owner
2026-11-15T01:56Z Q1 (a): "the road along the garage wall under the bridges
stays on today's ground, a bank rises to the garage floor and each entrance
ramps at 5 %").

Each BUILT plate of a governed group (``airport/agp_plates``,
``AgpGroup.plates``) is minted as ``graded_strip`` pieces under
``model/planar.AGP_GROUND_PREFIX`` (a zone region's family, no zone class —
the form of ``planar/stack_ground``):

* ``agp_ground:<group>:<row>:plate#k`` the plate itself (held at its level,
  ``constraints/agp_level`` P1);
* ``agp_ground:<group>:<row>:bank#k`` the ring round it, ``max([emit.design]
  bank_min_width_m, max(L - DEM) / bank_slope)`` wide, its toe pinned on the
  DEM (``constraints/fill_bank``).

Every piece welds to the zone bands (the stack ground among them), yields to
the airside cells cut back ``[seam] pad_frontage_m``, and stands off every
other cell, road ribbon and keep-out by the zones' groundside stand-off.  A
plate over a building pad is cut back from it (listed ``agp_plate_on_pad``
with both levels); a bank a road ribbon cuts short is listed
``agp_bank_clipped`` with the grade it is left.  No plate: no piece.  No
airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely

from ..geom.agp_plate import built_plates
from ..model.planar import AGP_GROUND_PREFIX
from .bank_cut import bank_width, knives, pieces
from .stack_ground import _areal

__all__ = ["agp_ground_pieces"]


def _bank_width(airport, poly, level: float, law) -> tuple[float, float]:
    """``(width, rise)``: the bank's width round plate ``poly`` at ``level``
    (module doc) and the largest rise over the DEM along its edge."""
    from ..airport.dem import dem_z_many
    pts = np.asarray(shapely.segmentize(poly.exterior, 5.0).coords)[:, :2]
    dem = getattr(airport, "dem", None)
    dz = dem_z_many(dem, pts[:, 0], pts[:, 1]) if dem is not None else np.full(len(pts), np.nan)
    fin = np.isfinite(dz)
    rise = float(np.max(np.abs(level - dz[fin]))) if fin.any() else 0.0
    return bank_width(rise, law), rise


def agp_ground_pieces(airport, taken: _t.Sequence, apart: _t.Sequence, cut_m: float,
                      hairline_m: float, vertex_m: float, law=None, airside=(),
                      pads: _t.Sequence = (), ribbons: _t.Sequence = (),
                      notes: "list | None" = None) -> list[tuple[str, _t.Any]]:
    """``(ref, polygon)`` per AGP-ground piece (module doc): ``taken`` the
    zone bands (welded), ``apart`` every other cell / ribbon / keep-out
    (stood off by ``cut_m``), ``airside`` the airside cells (cut back
    ``pad_frontage_m``), ``pads`` ``[(ref, polygon)]`` the building pads
    (listed), ``ribbons`` the road ribbons (a bank they cut is listed)."""
    plates = built_plates(getattr(airport, "agp_groups", ())) if law is not None else []
    if not plates:
        return []
    wid = {id(p): _bank_width(airport, poly, float(p.level), law) for _g, p, poly in plates}
    outline = shapely.union_all([poly.buffer(wid[id(p)][0]) for _g, p, poly in plates])
    knife, rib = knives(outline, taken, apart, airside, ribbons, cut_m, law)
    out: list[tuple[str, _t.Any]] = []
    claimed = None
    for gid, p, poly in plates:
        base = f"{AGP_GROUND_PREFIX}{gid}:{p.member}"
        width, rise = wid[id(p)]
        for ref, pad in pads:
            if pad is not None and not pad.is_empty and pad.intersects(poly):
                if notes is not None:
                    notes.append(f"agp_plate_on_pad: {base}:plate {p.k} L {p.level:.2f} over "
                                 f"{ref} ({pad.intersection(poly).area:.0f} m²)")
        bank = poly.buffer(width, join_style="mitre", mitre_limit=2.0).difference(poly)
        if not rib.is_empty and bank.intersects(rib):
            gap = float(poly.exterior.distance(rib))
            if notes is not None and gap < width:
                notes.append(f"agp_bank_clipped: {base}:bank of plate {p.k} {gap:.1f} m wide "
                             f"against {width:.1f} m (rise {rise:.2f} m, grade "
                             f"{rise / max(gap, 0.1):.2f})")
        k = {"plate": 0, "bank": 0}
        for kind, geom in (("plate", poly), ("bank", bank)):
            if claimed is not None:
                geom = geom.difference(claimed)
            geom = _areal(geom)
            claimed = geom if claimed is None else claimed.union(geom)
            for q in pieces(geom, knife, hairline_m, vertex_m):
                out.append((f"{base}:{kind}#{k[kind]}", q))
                k[kind] += 1
    return out
