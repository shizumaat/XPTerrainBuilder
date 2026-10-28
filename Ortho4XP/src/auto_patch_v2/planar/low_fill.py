"""A LOWER LEVEL'S FILL ALONG A LOT IS CUT OFF (owner RULINGS 2026-10-28s (3),
Q251 a; #1572).

Owner: "the part of a block-held lower pad level that stands on fill along
a lot edge is cut off from the level and drops to its own ground.  The
terminal's airside level does not move."

A lower level ``<block>/p<k>`` (``planar/low_level``, kind ``low_level``)
is one rigid plate tied to its block (``constraints/platform.landing_rows``).
Where its own ground falls away under it toward a parking lot, the plate
stood on fill above the lot (KMCI ``building26/b1/p1``: level 302.52, its
area's ground median 302.34, the ground at its edge by ``dsf:objpav662``
299.9, the lot 2.4-2.7 m below the level behind a 0.74 m gap).

THE FILL BAND.  Over the level's area, every cell whose DEM lies more than
``[building_pad] frontage_hold_margin_m`` (the DEM proxy's float allowance)
under the level's OWN GROUND (the median DEM over its area,
``low_level._ground``) is fill; the connected pieces of that fill that come
within ``pad_frontage_m`` of a lot (``planar/landing.LOT_ROLES``) are the
BAND.  THE BAND REACHES THE LEVEL'S EDGE (owner RULINGS 2026-10-28u, Q273
a: "a road inside a lower level's cut-off fill band drops to the band's
ground"): the cells are read at their centres, so the strip of the level
between the last cell and its outline -- under one cell wide -- is fill the
cells did not see; every piece of the rest thinner than a cell that touches
the band goes with it.  Left as level, that strip stood the old plate's edge
beside the road or lot across the band, and the road's cap to it held the
road on the plate (KMCI ``dsf:objpav781``: 302.42 over band ground 301.0,
welded 1 m to a 0.5 m strip of ``building26/b1/p1`` at 302.52).  The band leaves the level: the level's regions are what remains,
and the band is no pad at all -- its ground places it, and the lot beside
it keeps its own.  A level that would be left under ``[building_pad]
min_area_m2`` is not cut (counted, ``low_level_fill_kept``).  The level's
tie, its riser and its block are untouched, so the airside never sees the
cut.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics as _st
import typing as _t

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts

__all__ = ["fill_band", "cut_fill_bands"]

#: the most DEM samples one level's band is read on (a cost bound, not law)
_MAX_CELLS = 40000


def _cells(L: Polygon, dem, grid: float) -> "tuple[float, list[tuple[float, float, float]]]":
    """``(cell size, [(x, y, dem)])`` over the level's area."""
    x0, y0, x1, y1 = L.bounds
    h = max(grid, 1.0, math.sqrt(max(L.area, 1.0) / _MAX_CELLS))
    import numpy as np
    from shapely import contains_xy
    xs = np.arange(x0 + 0.5 * h, x1, h)
    ys = np.arange(y0 + 0.5 * h, y1, h)
    if not len(xs) or not len(ys):
        return h, []
    X, Y = np.meshgrid(xs, ys)
    X, Y = X.ravel(), Y.ravel()
    keep = contains_xy(L, X, Y)
    out = []
    for x, y in zip(X[keep].tolist(), Y[keep].tolist(), strict=True):
        try:
            z = float(dem.z(x, y))
        except Exception:  # noqa: BLE001 - off the raster
            continue
        if z == z:
            out.append((x, y, z))
    return h, out


def fill_band(L: Polygon, lots: Polygon, dem, grid: float, margin_m: float,
              near_m: float) -> "Polygon | None":
    """The part of level ``L`` on fill along a lot (module doc), or None."""
    if L.is_empty or lots.is_empty or dem is None:
        return None
    if L.distance(lots) > near_m:
        return None
    h, cells = _cells(L, dem, grid)
    if not cells:
        return None
    ground = _st.median(z for _x, _y, z in cells)
    low = [box(x - 0.5 * h, y - 0.5 * h, x + 0.5 * h, y + 0.5 * h)
           for x, y, z in cells if z < ground - margin_m]
    if not low:
        return None
    fill = unary_union(low).intersection(L)
    reach = lots.buffer(near_m)
    band = [q for q in nonempty_polygon_parts(fill)
            if q.intersects(reach) and q.area >= 4.0 * h * h]
    if not band:
        return None
    return _with_edge_strips(L, unary_union(band), h)


def _with_edge_strips(L: Polygon, band, h: float):
    """``band`` and every piece of ``L`` less it thinner than one cell
    ``h`` that touches it (module doc: THE BAND REACHES THE LEVEL'S EDGE)."""
    rest = L.difference(band)
    core = rest.buffer(-0.5 * h, join_style=2).buffer(0.5 * h, join_style=2)
    near = band.buffer(1e-6)
    thin = [q for q in nonempty_polygon_parts(rest.difference(core))
            if q.intersects(near)]
    return unary_union([band, *thin]).intersection(L) if thin else band


def cut_fill_bands(res: list, reg, lots: _t.Sequence[Polygon], airport, law,
                   grid: float, counts: dict, kind: str) -> list:
    """``res`` with every lower level (``reg.landings`` of ``kind``) less its
    fill band (module doc)."""
    lot = unary_union([g for g in lots if g is not None and not g.is_empty])
    dem = getattr(airport, "dem", None)
    if lot.is_empty or dem is None:
        return res
    from ..law.tables import design as design_law
    bp = law.tables.structures.building_pad
    near = float(design_law(law).pad_frontage_m)
    margin = float(bp.frontage_hold_margin_m)
    pmin = float(bp.min_area_m2)
    out = list(res)
    for ref, rec in sorted(reg.landings.items()):
        if rec.get("kind") != kind:
            continue
        mine = [r for r in out if str(r.ref) == ref and r.polygon is not None]
        if not mine:
            continue
        L = unary_union([r.polygon for r in mine])
        band = fill_band(L, lot, dem, grid, margin, near)
        if band is None:
            continue
        keep = L.difference(band)
        if keep.area < pmin:
            counts["low_level_fill_kept"] = counts.get("low_level_fill_kept", 0) + 1
            continue
        tmpl = mine[0]
        out = [r for r in out if str(r.ref) != ref]
        out += [_dc.replace(tmpl, polygon=q) for q in nonempty_polygon_parts(keep)]
        rec["fill_cut_m2"] = round(band.area, 1)
        counts["low_level_fill_cut"] = counts.get("low_level_fill_cut", 0) + 1
        counts.setdefault("low_level_fill_cut_list", []).append(
            f"{ref}: {band.area:,.0f} m2 off {L.area:,.0f} m2")
    return out
