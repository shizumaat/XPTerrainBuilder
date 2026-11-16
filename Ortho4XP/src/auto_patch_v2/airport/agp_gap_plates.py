"""THE GROUND BETWEEN TWO GROUND-FLOOR PARTS OF ONE FOLLOWER IS ITS GROUND
FLOOR (#2116 R2 C1b; owner RULINGS 2026-11-16s/v).

A follower's ground floors (``airport/agp_plates``) cover only where the
pack authored a floor; the ground between two parts of the follower — a
service yard between a garage and the hall, open to the sky — is no floor,
so C1 left it to the DEM and a bank fell into it.  The SIDES of such a strip
are the follower's own parts standing on its datum: its built plates and
its FEET (``agp_floors.feet_of``: the bottoms of its pieces' solids) within
``[agp] ground_band_m`` of the datum (``agp_ground.member_feet``).  Near a
built plate, a gap a closing of ``[agp] plate_gap_max_m`` fills between two
DIFFERENT side parts is a strip; it is OPEN where no floor of the member
stands over it at any height (the member's floor plan stands in for its
solids above the ground — no second OBJ8 walk).  Where the sides' lowest
solids agree within ``[agp] flat_step_tol_m`` the open strip is a plate part
at ``L = zero_pred + y_low - deck_flush_m``, exempt from ``plate_max_off_m``
(the pack's own feet on both sides are the witness), listed
``agp_gap_plate``.  Sides differing by more are listed, never built (RULINGS
2026-11-16v: the step between them is the author's).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..model.agp_group import AgpPlate

__all__ = ["with_gap_plates"]

#: a gap smaller than this (m²) is a seam between two parts, not a strip
_MIN_GAP_M2 = 10.0
#: a side touches a gap within this (m)
_TOUCH_M = 0.3
#: a foot sample stands for a square this far either side (m): the feet's
#: 1 m cells (``agp_floors.FOOT_CELL_M``) join into one wall
_FOOT_M = 0.75


def _sides(plates: list, feet: np.ndarray, region):
    """``(side parts, side y, tree)``: the connected parts of the built
    plates and the feet inside ``region``; per part, the y of each foot in
    it (a part with no foot reads its plate's ``y``)."""
    import shapely
    pts = shapely.points(feet[:, 0, :2]) if len(feet) else np.array([])
    inside = shapely.intersects(pts, region) if len(pts) else np.zeros(0, bool)
    pts, ys = pts[inside], feet[inside][:, 0, 2]
    geoms = [shapely.Polygon(p.ring, p.holes) for p in plates]
    if len(pts):
        geoms.append(shapely.union_all(shapely.buffer(pts, _FOOT_M, cap_style="square")))
    parts = [q for q in shapely.get_parts(shapely.union_all(geoms)) if q.area > 0.0]
    tree = shapely.STRtree(parts)
    side_y: list[list[float]] = [[] for _ in parts]
    if len(pts):
        hit = tree.query(pts, predicate="intersects")
        for i, k in zip(hit[0].tolist(), hit[1].tolist(), strict=True):
            side_y[k].append(float(ys[i]))
    for p in plates:
        hit = tree.query(shapely.Polygon(p.ring).representative_point(), predicate="intersects")
        for k in hit.tolist():
            if not side_y[k]:
                side_y[k].append(float(p.y))
    return parts, side_y, tree


def _open_part(gap, floors: np.ndarray):
    """``gap`` less the member's floor plan over it (``floors`` ``(k, 3, 2)``
    in the frame), or ``None`` when nothing of it is open."""
    import shapely
    if floors.shape[0]:
        x0, y0, x1, y1 = gap.bounds
        lo, hi = floors.min(axis=1), floors.max(axis=1)
        near = (hi[:, 0] >= x0) & (lo[:, 0] <= x1) & (hi[:, 1] >= y0) & (lo[:, 1] <= y1)
        if near.any():
            cover = shapely.union_all(shapely.polygons(floors[near]), grid_size=0.01)
            gap = gap.difference(cover)
    parts = [p for p in shapely.get_parts(gap) if p.geom_type == "Polygon"]
    return max(parts, key=lambda p: p.area) if parts else None


def with_gap_plates(plates: _t.Sequence[AgpPlate], feet: np.ndarray,
                    floors: _t.Callable[[], np.ndarray], zp: float | None, agp, flush: float,
                    dem, notes: list[str]) -> list[AgpPlate]:
    """``plates`` (ONE member's, :func:`agp_plates._member_plates`) plus a
    plate part per open strip between two of its side parts (module doc).
    ``feet`` ``(k, 1, 3)`` its feet in the frame within the ground band;
    ``floors`` reads its whole floor plan ``(k, 3, 2)``, once, when a strip
    is found."""
    import shapely

    from .dem import dem_z_many
    built = [p for p in plates if p.built and len(p.ring) >= 3]
    if zp is None or not built:
        return list(plates)
    width, tol = float(agp.plate_gap_max_m), float(agp.flat_step_tol_m)
    region = shapely.union_all([shapely.Polygon(p.ring) for p in built]).buffer(width + 5.0)
    parts, side_y, tree = _sides(built, feet, region)
    if len(parts) < 2:
        return list(plates)
    union = shapely.union_all(parts)
    r = 0.5 * width
    closed = union.buffer(r, join_style="mitre", mitre_limit=2.0).buffer(
        -r, join_style="mitre", mitre_limit=2.0)
    out = list(plates)
    k_next = 1 + max(p.k for p in plates)
    for gap in shapely.get_parts(closed.difference(union)):
        if gap.geom_type != "Polygon" or gap.area < _MIN_GAP_M2 or not gap.intersects(region):
            continue
        sides = tree.query(gap.buffer(_TOUCH_M), predicate="intersects").tolist()
        sides = [k for k in sides if side_y[k]]
        if len(sides) < 2:
            continue
        w = 2.0 * gap.area / max(gap.length, 1e-9)
        lows = [min(side_y[k]) for k in sides]
        tag = f"{built[0].member} {w:.1f} m strip, sides y " + "/".join(f"{y:+.2f}" for y in lows)
        if max(lows) - min(lows) > tol:
            notes.append(f"agp_gap_listed: {tag} differ > flat_step_tol_m, not built")
            continue
        open_ = _open_part(gap, floors())
        if open_ is None or sum(1 for k in sides
                                if parts[k].distance(open_) <= _TOUCH_M) < 2:
            notes.append(f"agp_gap_covered: {tag} under the member's own floors, not built")
            continue
        y = min(lows)
        L = float(zp) + y - flush
        pts = np.asarray(shapely.segmentize(open_.exterior, 5.0).coords)[:, :2]
        dz = dem_z_many(dem, pts[:, 0], pts[:, 1]) if dem is not None else np.full(len(pts),
                                                                                    np.nan)
        fin = np.isfinite(dz)
        off = float(np.median(np.abs(L - dz[fin]))) if fin.any() else math.inf
        ys = "/".join(f"{v:+.2f}" for v in lows)
        why = f"agp_gap_plate: {w:.1f} m, y {ys}, |L - DEM| {off:.2f}"
        out.append(_dc.replace(
            built[0], k=k_next,
            ring=tuple((float(a), float(b)) for a, b in open_.exterior.coords[:-1]),
            holes=tuple(tuple((float(a), float(b)) for a, b in h.coords[:-1])
                        for h in open_.interiors),
            y=round(y, 4), level=round(L, 4), area_m2=round(float(open_.area), 1),
            dem_off_m=round(off, 3), built=True, why=why))
        k_next += 1
    return out
