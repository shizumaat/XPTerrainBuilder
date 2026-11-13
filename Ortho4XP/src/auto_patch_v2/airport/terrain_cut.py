"""THE GROUND UNDER A TERRAIN MODEL IS CUT TO IT (owner RULINGS
2026-11-13k, issue #2036 (c) / #2040).

Owner (2026-11-13T05:51Z): "Yes to cutting terrain under a terrain object
if it's not being hidden".  A terrain model (``airport/terrain_model``,
RULINGS 13i) is seated so no visible edge floats; over a coarse DEM its
top then lies under our ground over much of its plan (SBRJ's Sugarloaf
over 90 m SRTM: 64 % of the plan) and the ground pokes through it.  The
tile's elevation raster under the plan is CUT to the object's surface, so
the object covers it -- the way the patch under a terrain-shaped deck is
drawn to the deck (#1730, ``geom/terrain_deck.target_at``), here with
``fill`` off: the ground is only ever lowered.

THE CUT SURFACE (:func:`_cut_grid`, on the model's own plan grid, metres
over its zero): inside the plan the ground stands at most at

    erode(top, ERODE_M) - UNDER_M

-- the lowest top within :data:`ERODE_M` of the point.  The mesher draws
the raster as triangles whose corners it samples and whose interior it
interpolates; a triangle no wider than ``ERODE_M`` whose corners stand
under the lowest top near each of them stands under the top everywhere
(a linear interpolation peaks at a corner, and every point of the
triangle is within ``ERODE_M`` of each corner).  Within :data:`BAND_M` of
the plan's edge (the outer rim and the edge of every hole) the bound is
never under the lowest surface of the EDGE within ``BAND_M`` (the bottom
of the edge cells, dilated: a skirt drops metres from one cell to the
next, and the mesher's corner by the edge may sample a cell inside it):
the ground the seat put at or over the object's lowest edge
(``terrain_model``'s ``z0``) is lowered to that edge and no further, so
no edge floats.  Outside the plan nothing is cut, and the plan's edge is
drawn as a constrained line (:func:`outline_rings`) so no mesh triangle
straddles it.

THE CONSUMER CENSUS (CLAUDE.md, RULINGS 2026-08-30l), ruled before any
consumer was edited.  The region is the tile ``.alt`` raster inside a
non-hidden terrain model's plan, after the airport patches are built:

* Triangle4XP (mesh step) reads the ``.alt``: CUT -- the purpose.
* The tile's edge (gluing edges; the neighbour's raster is not cut):
  never cut within two postings of it.
* The plan's edge: a DUMMY constrained ring, sampled on the cut raster.
* The auto patch's DEM (``ProductionDem``: the seat, the match) reads the
  corpus, not the ``.alt``: UNCUT -- the seat is read on the ground the
  object models.
* A patch face inside the plan: its ``alt_abs`` nodes are the ground
  there (INTERP_ALT keeps its own values).
* Roads and unpatched airports (step 1, after the cut) read ``tile.dem``:
  they follow the cut ground, under the object.
* Sea and water triangles: the water is a datum (RULINGS 2026-09-09m), its
  vertices stay at the water level, so the cut never reaches under water;
  a skirt modelled below the water surface stays under the water (SBRJ's
  Sugarloaf: 15.5 % of its plan, the skirt 5-27 m deep).
* The pack's ``OBJECT`` / ``AGL`` rows and autogen in the plan (X-Plane,
  the object stage) stand on the drawn mesh: they follow the cut ground,
  under the object; the model's origin set is ``OBJECT_MSL`` and stays.
* The masks step, the DSF elevation raster, the coastline vetting read
  the raw source DEM: UNCUT (not the drawn ground).
* The mesh step's refinement re-bake (``tile.iterate``) rewrites the
  ``.alt``: it re-applies the cut.
* Step reuse: the set of models cut is a vector-step input, so a hide
  answer re-runs the cut.
* "Hide terrain objects" (``drape_stage.TERRAIN``): a hidden model is not
  cut -- the ground under it is the plain DEM.

THE SAME REGION, A SECOND CLASS (#2053): a ground object in the water seated
on its bridges' far ends (``airport/bridged_ground``) writes the same seat
record with ``cut``, and every consumer above reads it as it reads a
terrain model's; its record names ``erode_m`` (one cell: it carries riders
draped on the drawn ground, which a 30 m erosion would sink).

Pure geometry: the tile glue that reads the plans and writes the raster is
``auto_patch/terrain_cut_stage``.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..geom.terrain_deck import CELL_M, DeckGrid, TerrainFit, target_at

__all__ = ["ERODE_M", "BAND_M", "cut_fit", "projector", "cut_heights",
           "outline_rings", "plan_box"]

#: the radius the top is eroded over inside the plan (module doc): wider
#: than the triangles the mesher leaves on a surface this smooth
ERODE_M = 30.0
#: the rim band where the cut stops at the object's lowest surface
BAND_M = 10.0


def _cut_grid(grid: DeckGrid, erode_m: float = ERODE_M) -> DeckGrid:
    """The CUT SURFACE of a model's plan grid (module doc) as a
    :class:`DeckGrid` whose ``top`` is the bound (``bot`` the model's own;
    the cut never fills).  ``erode_m``: the erosion radius (a ground object
    carrying riders takes one cell, ``bridged_ground.ERODE_M``)."""
    from scipy import ndimage
    cov = grid.covered
    k = max(1, int(round(erode_m / CELL_M)))
    disc = np.hypot(*np.mgrid[-k:k + 1, -k:k + 1]) <= k
    top = np.where(cov, grid.top, np.inf)
    eroded = ndimage.minimum_filter(top, footprint=disc, mode="constant", cval=np.inf)
    # the edge cells: covered, touching an uncovered one (8-neighbours,
    # the outer rim and the edge of every hole), and how far each cell is
    rim = cov & ndimage.binary_dilation(~np.pad(cov, 1), np.ones((3, 3), bool))[1:-1, 1:-1]
    edge = ndimage.distance_transform_edt(~rim) * CELL_M
    b = max(1, int(round(BAND_M / CELL_M)))
    band = np.hypot(*np.mgrid[-b:b + 1, -b:b + 1]) <= b
    lowest = ndimage.maximum_filter(np.where(rim, grid.bot, -np.inf), footprint=band,
                                    mode="constant", cval=-np.inf)
    bound = np.where(edge <= BAND_M, np.maximum(eroded, lowest), eroded)
    return DeckGrid(grid.x0, grid.z0, grid.bot.copy(), np.where(cov, bound, np.nan))


def cut_fit(grid: DeckGrid, zero: float, heading: float,
            erode_m: float = ERODE_M) -> TerrainFit:
    """The cut as a :class:`TerrainFit` anchored at the frame origin (the
    model's anchor), seated at ``zero``, filling nothing."""
    cut = _cut_grid(grid, erode_m)
    return TerrainFit("cut", "", (0.0, 0.0), float(heading), float(zero), 1.0,
                      cut.area_m2, 0.0, cut, fill=False)


def projector(lat: float, lon: float) -> tuple[_t.Callable, _t.Callable]:
    """``(to_xy(lons, lats), to_ll(xs, ys))``: degrees <-> metres east /
    north of the anchor (the transverse Mercator the airport frames use,
    centred on the anchor, so its north is the object's)."""
    from pyproj import Transformer

    from ..model.frame import Frame
    crs = Frame("", (float(lat), float(lon)), 11).crs
    fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    inv = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    def to_xy(lons, lats):
        x, y = fwd.transform(np.asarray(lons, float), np.asarray(lats, float))
        return np.asarray(x, float), np.asarray(y, float)

    def to_ll(xs, ys):
        lo, la = inv.transform(np.asarray(xs, float), np.asarray(ys, float))
        return np.asarray(lo, float), np.asarray(la, float)
    return to_xy, to_ll


def cut_heights(fit: TerrainFit, to_xy: _t.Callable, lons: np.ndarray,
                lats: np.ndarray, ground: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(z, inside)``: the ground at ``(lons, lats)`` after the cut, and
    where the plan covers them (``geom/terrain_deck.target_at``)."""
    x, y = to_xy(lons, lats)
    return target_at(fit, x, y, np.asarray(ground, float))


def _to_frame(fit: TerrainFit, xz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Authored plan ``(x, z)`` -> frame ``(east, north)``, the inverse of
    ``TerrainFit.local``."""
    h = math.radians(fit.heading_deg)
    s, c = math.sin(h), math.cos(h)
    x, z = xz[:, 0], xz[:, 1]
    return fit.xy[0] + x * c - z * s, fit.xy[1] - (x * s + z * c)


def plan_box(fit: TerrainFit, to_ll: _t.Callable) -> tuple[float, float, float, float]:
    """``(west, south, east, north)`` degrees around the plan grid."""
    ni, nj = fit.grid.bot.shape
    xs = fit.grid.x0 + CELL_M * np.array([-0.5, ni - 0.5])
    zs = fit.grid.z0 + CELL_M * np.array([-0.5, nj - 0.5])
    lo, la = to_ll(*_to_frame(fit, np.array([(x, z) for x in xs for z in zs])))
    return float(lo.min()), float(la.min()), float(lo.max()), float(la.max())


def outline_rings(fit: TerrainFit, to_ll: _t.Callable) -> list[np.ndarray]:
    """The plan's EDGE -- the boundary of its covered cells, outer rings and
    holes -- as ``(n, 2)`` ``(lon, lat)`` rings, simplified within a
    quarter cell (the constrained line the mesh draws there)."""
    import shapely
    from shapely.geometry import MultiPolygon, Polygon
    ii, jj = np.nonzero(fit.grid.covered)
    if not len(ii):
        return []
    x = fit.grid.x0 + CELL_M * ii
    z = fit.grid.z0 + CELL_M * jj
    h = CELL_M / 2.0
    region = shapely.union_all(shapely.box(x - h, z - h, x + h, z + h)).simplify(h / 2.0)
    polys = region.geoms if isinstance(region, MultiPolygon) else [region]
    out = []
    for poly in polys:
        if not isinstance(poly, Polygon) or poly.is_empty:
            continue
        for ring in (poly.exterior, *poly.interiors):
            lo, la = to_ll(*_to_frame(fit, np.asarray(ring.coords, float)))
            out.append(np.c_[lo, la])
    return out
