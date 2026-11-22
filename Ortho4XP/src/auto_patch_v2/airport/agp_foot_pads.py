"""THE GROUND UNDER A SEATED FOLLOWER'S WHOLE FOOTPRINT IS A FLAT PAD
(owner 2026-11-18T20:26Z, RULINGS 2026-11-18j (2): "it should extend under
the terminal and Westin hotel as well, which should all have a flat pad
under it so it's not floating").

A follower's ground floors (``airport/agp_plates``) cover only where the
pack authored an up-facing floor near its datum; a hall or a hotel whose
ground storey is walls and columns has no such floor, so its contact feet
stood over the DEM where the group's lawful lift (14m (3)) seated it above
the natural ground.  Its FOOTPRINT is the plan of its contact FEET (within
``[agp] ground_band_m`` of the datum, ``agp_ground.member_feet``), the gaps
between them up to ``[agp] plate_gap_max_m`` closed and its courts filled.
Outside the member's plates, each part of it is a PAD at ``L = zero_pred +
y_top - deck_flush_m`` (``y_top`` the highest contact foot on it, so no foot
floats), built only where the DEM stands under ``L`` (the ground is raised
to meet the objects, never cut: where the ground already stands at or over
the seat the pad does not reach), listed ``agp_foot_pad``.  A mapped
at-grade road through the footprint keeps its own ground (RULINGS
2026-11-14m (1): a road passing under the building stays on the ground):
its ribbon, grown by the groundside cut-back every road receives, is no
pad.  The planar
stage grades it as any plate (``planar/agp_ground``) and banks it back to
the DEM at the bank law.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..model.agp_group import AgpPlate

__all__ = ["with_foot_pads", "road_corridors"]

#: the DEM is read on a grid this fine over a footprint part (m)
_GRID_M = 4.0
#: a foot stands on a pad part within this (m): a foot cell's half width
_FOOT_REACH_M = 0.6


def _footprint(feet: np.ndarray, width: float):
    """The member's footprint (module doc): its foot cells' union, gaps up
    to ``width`` closed, courts filled."""
    import shapely
    cells = shapely.box(feet[:, 0, 0] - 0.5, feet[:, 0, 1] - 0.5,
                        feet[:, 0, 0] + 0.5, feet[:, 0, 1] + 0.5)
    r = 0.5 * width
    u = shapely.union_all(cells, grid_size=0.01).buffer(
        r, join_style="mitre", mitre_limit=2.0).buffer(-r, join_style="mitre", mitre_limit=2.0)
    return shapely.union_all([shapely.Polygon(p.exterior) for p in shapely.get_parts(u)
                              if p.geom_type == "Polygon"])


def road_corridors(airport, law):
    """The union of every mapped at-grade road's ribbon grown by the
    groundside cut-back (``airport/road_ways``), or ``None``."""
    import shapely

    from .road_ways import ribbon_half_width_m, road_ways
    ways = getattr(airport, "osm_ways_mapped", None) or getattr(airport, "osm_ways", ()) or ()
    cut = float(law.tables.zones.adjacent_ground.groundside_cutback_m)
    got = [ln.buffer(ribbon_half_width_m(w.tags or {}, law) + cut, cap_style="flat")
           for w, ln in road_ways(ways)]
    return shapely.union_all(got) if got else None


def _under(part, level: float, dem):
    """The part of ``part`` where the DEM stands under ``level`` (a
    ``_GRID_M`` grid of cells, clipped to the part)."""
    import shapely

    from .dem import dem_z_many
    x0, y0, x1, y1 = part.bounds
    xs = np.arange(x0 + 0.5 * _GRID_M, x1, _GRID_M)
    ys = np.arange(y0 + 0.5 * _GRID_M, y1, _GRID_M)
    if not len(xs) or not len(ys):
        return None
    gx, gy = (a.ravel() for a in np.meshgrid(xs, ys))
    dz = dem_z_many(dem, gx, gy)
    low = np.isfinite(dz) & (dz < level)
    if not low.any():
        return None
    h = 0.5 * _GRID_M
    cells = shapely.box(gx[low] - h, gy[low] - h, gx[low] + h, gy[low] + h)
    return shapely.union_all(cells, grid_size=0.01).intersection(part)


def with_foot_pads(plates: _t.Sequence[AgpPlate], feet: np.ndarray, zp: float | None, agp,
                   flush: float, dem, notes: list[str], roads=None) -> list[AgpPlate]:
    """``plates`` (ONE member's) plus a pad per part of its footprint outside
    them where the DEM stands under the seat (module doc).  ``feet``
    ``(k, 1, 3)`` its contact feet in the frame within the ground band;
    ``roads`` the road corridors (:func:`road_corridors`) no pad takes."""
    import shapely

    from .dem import dem_z_many
    out = list(plates)
    if zp is None or dem is None or not feet.shape[0] or not plates:
        return out
    taken = shapely.union_all([shapely.Polygon(p.ring, p.holes) for p in plates
                               if p.built and len(p.ring) >= 3])
    rest = _footprint(feet, float(agp.plate_gap_max_m)).difference(taken)
    if roads is not None:
        rest = rest.difference(roads)
    k_next = 1 + max(p.k for p in plates)
    min_a = float(agp.floor_min_area_m2)
    for part in sorted(shapely.get_parts(rest), key=lambda p: -p.area):
        if part.geom_type != "Polygon" or part.area < min_a:
            continue
        on = shapely.contains_xy(part.buffer(_FOOT_REACH_M), feet[:, 0, 0], feet[:, 0, 1])
        if not on.any():
            continue
        y = float(feet[on, 0, 2].max())
        L = float(zp) + y - flush
        fill = _under(part, L, dem)
        for pad in shapely.get_parts(fill) if fill is not None else ():
            if pad.geom_type != "Polygon" or pad.area < min_a:
                continue
            pts = np.asarray(shapely.segmentize(pad.exterior, 10.0).coords)[:, :2]
            dz = dem_z_many(dem, pts[:, 0], pts[:, 1])
            fin = np.isfinite(dz)
            off = float(np.median(np.abs(L - dz[fin]))) if fin.any() else math.inf
            why = f"agp_foot_pad: y {y:+.2f}, |L - DEM| {off:.2f} (the seated footprint)"
            out.append(_dc.replace(
                plates[0], k=k_next,
                ring=tuple((float(a), float(b)) for a, b in pad.exterior.coords[:-1]),
                holes=tuple(tuple((float(a), float(b)) for a, b in h.coords[:-1])
                            for h in pad.interiors),
                y=round(y, 4), level=round(L, 4), area_m2=round(float(pad.area), 1),
                dem_off_m=round(off, 3), built=True, why=why))
            k_next += 1
    if len(out) > len(plates):
        notes.append(f"agp_foot_pads: {plates[0].member} {len(out) - len(plates)} pad(s), "
                     f"{sum(p.area_m2 for p in out[len(plates):]):.0f} m²")
    return out
