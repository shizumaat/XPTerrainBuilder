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

THE FLOOR (#2053 round 2): a terrain model's top IS its ground; a ground
object's top is not -- over its ground stand roofs and raised terraces, and
cut to the HIGHEST surface the ground under a roof stays uncut, so the mesh
triangle from that posting to the open ground beside the wall lifts the
open ground through the object (SBRJ's island: 53 of 1,156 open samples
over its top, worst 1.44 m).  Its record names ``floor_m`` (one storey,
``[building_pad] low_level_min_step_m``): where a roof stands that far or
more over a cell's lowest surface, the surface eroded beyond the edge band
is that lowest one (the ground under the roof); a thinner stack (a
footbridge over a court) keeps its top.  The edge band keeps the top: a
bridge's arch carries its deck metres over its own underside, and at the
arm's far end the ground must meet the deck.  A terrain model keeps its
top.

THE HOLD (#2053 round 3, spec ``docs/specs/2053-round3-hold-spec.md``):
the cut raster is not the drawn ground.  Every mesh vertex is the bilinear
raster at the vertex, and a drawn point is supported by one triangle edge
plus one posting diagonal -- wider than one cell, so 13k's "no triangle
pokes" proof does not hold for an object eroded over one cell, and a patch
node inside the plan carries the uncut DEM.  A record whose ``cut`` names
``erode_m`` (an object carrying riders) is therefore HELD by the mesh:

(a) the mesh step's curvature weight over its plan box is raised so
    Triangle4XP refines to one posting wherever the cut ground steps by
    the 0.5 m ground bar (``O4_Mesh_Utils.apply_hold_curv_weights``);
(b) after the altitudes are post-processed every FREE vertex is lowered by
    the least amount that puts every drawn triangle under the object's
    bound at every :data:`HOLD_CELL_M` sample (:func:`hold_bound`, the cut
    surface's rule binned at 1 m and eroded one cell; :func:`hold_heights`)
    -- only lowered, never under a bound of its own triangles;
(c) the patch's groundside vertices under the plan read the cut ground
    (``airport/object_ground``).

A terrain model's record (no ``erode_m``) is untouched by all three.  THE
HOLD's consumer rows (the census above holds for the rest):

* free mesh vertices (attribute 0) and the plan-edge ring's: HELD;
* water / sea vertices (the datum), INTERP_ALT corners (patch, ribbons,
  apt.dat) and patch-pinned stranded vertices (#2034): FIXED in the mesh
  -- the patch's are right at the source through (c);
* the patch's airside vertices: untouched (airside is king);
* the seat (``bridged_ground``) and the match: the uncut corpus DEM;
* the pack's riders on the plan: follow the held ground (reported by
  ``tools/drawn_cover.py``, not judged);
* the refinement re-bake (``tile.iterate``): the hold runs after every mesh.

THE FLOOR's band, round 3: for a ground object (``floor_m`` > 0) the edge
band keeps its own top eroded, with no edge-lowest term -- an arm's rim
underside over low open ground is not the ground's bound there.

Pure geometry: the tile glue that reads the plans and writes the raster is
``auto_patch/terrain_cut_stage``.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..geom.terrain_deck import CELL_M, DeckGrid, TerrainFit, target_at

__all__ = ["ERODE_M", "BAND_M", "HOLD_CELL_M", "cut_fit", "projector", "cut_heights",
           "outline_rings", "plan_box", "hold_bound", "hold_heights"]

#: the radius the top is eroded over inside the plan (module doc): wider
#: than the triangles the mesher leaves on a surface this smooth
ERODE_M = 30.0
#: the rim band where the cut stops at the object's lowest surface
BAND_M = 10.0
#: THE HOLD's sample grid (module doc): the bound the drawn mesh is held
#: under is binned and sampled at this spacing, eroded by one cell
HOLD_CELL_M = 1.0
#: a held sample is over its bound when the drawn surface there stands
#: more than this over it (m)
_HOLD_TOL_M = 1e-3
#: the hold's passes at most
_HOLD_PASSES = 20


def _floor(bot: np.ndarray, top: np.ndarray, floor_m: float) -> np.ndarray:
    """Each cell's walkable surface (module doc, THE FLOOR): its lowest
    where a roof stands ``floor_m`` or more over it, else its top."""
    return np.where(top - bot >= floor_m, bot, top)


def _bound(bot: np.ndarray, top: np.ndarray, cell: float, erode_m: float,
           floor_m: float) -> np.ndarray:
    """The CUT SURFACE (module doc) of a plan binned on a ``cell``-metre
    grid (``bot`` / ``top`` ``nan`` where uncovered), in metres over the
    model's zero; ``inf`` / undefined off the plan.  ``erode_m``: the
    erosion radius.  ``floor_m`` == 0 (a terrain model): the edge band
    never under the edge's lowest surface.  ``floor_m`` > 0 (a ground
    object, THE FLOOR): the band keeps its own top eroded, beyond it the
    floor eroded -- no edge-lowest term (an arm's rim underside over low
    open ground is not the ground's bound)."""
    from scipy import ndimage
    cov = np.isfinite(bot)
    k = max(1, int(round(erode_m / cell)))
    disc = np.hypot(*np.mgrid[-k:k + 1, -k:k + 1]) <= k

    def erode(surf):
        return ndimage.minimum_filter(np.where(cov, surf, np.inf), footprint=disc,
                                      mode="constant", cval=np.inf)

    eroded = erode(top)
    # the edge cells: covered, touching an uncovered one (8-neighbours,
    # the outer rim and the edge of every hole), and how far each cell is
    rim = cov & ndimage.binary_dilation(~np.pad(cov, 1), np.ones((3, 3), bool))[1:-1, 1:-1]
    edge = ndimage.distance_transform_edt(~rim) * cell
    if floor_m > 0.0:
        return np.where(edge <= BAND_M, eroded, erode(_floor(bot, top, floor_m)))
    b = max(1, int(round(BAND_M / cell)))
    band = np.hypot(*np.mgrid[-b:b + 1, -b:b + 1]) <= b
    lowest = ndimage.maximum_filter(np.where(rim, bot, -np.inf), footprint=band,
                                    mode="constant", cval=-np.inf)
    return np.where(edge <= BAND_M, np.maximum(eroded, lowest), eroded)


def _cut_grid(grid: DeckGrid, erode_m: float = ERODE_M, floor_m: float = 0.0
              ) -> DeckGrid:
    """The CUT SURFACE of a model's plan grid (module doc) as a
    :class:`DeckGrid` whose ``top`` is the bound (``bot`` the model's own;
    the cut never fills).  ``erode_m``: the erosion radius (a ground object
    carrying riders takes one cell, ``bridged_ground.ERODE_M``).
    ``floor_m`` > 0: the bound of THE FLOOR (:func:`_bound`)."""
    bound = _bound(grid.bot, grid.top, CELL_M, erode_m, floor_m)
    return DeckGrid(grid.x0, grid.z0, grid.bot.copy(),
                    np.where(grid.covered, bound, np.nan))


def cut_fit(grid: DeckGrid, zero: float, heading: float,
            erode_m: float = ERODE_M, floor_m: float = 0.0) -> TerrainFit:
    """The cut as a :class:`TerrainFit` anchored at the frame origin (the
    model's anchor), seated at ``zero``, filling nothing; ``floor_m`` > 0:
    cut to the object's floor per cell (module doc, THE FLOOR)."""
    cut = _cut_grid(grid, erode_m, floor_m)
    return TerrainFit("cut", "", (0.0, 0.0), float(heading), float(zero), 1.0,
                      cut.area_m2, 0.0, cut, fill=False)


def hold_bound(tris: np.ndarray, erode_m: float, floor_m: float
               ) -> tuple[float, float, np.ndarray]:
    """``(x0, z0, bound)``: THE HOLD's bound (module doc) of the authored
    triangles ``tris`` (``(n, 3, 3)``, the plan's static solid) on the
    :data:`HOLD_CELL_M` grid, metres over the model's zero (``nan`` off
    the plan): the cut surface's rule eroded by one cell -- a drawn
    triangle held under it at every sample centre stands under the object
    between them -- never wider than the record's ``erode_m``."""
    from .terrain_shaped import bin_triangles
    x0, z0, bot, top = bin_triangles(np.asarray(tris, float), HOLD_CELL_M)
    bound = _bound(bot, top, HOLD_CELL_M, min(float(erode_m), HOLD_CELL_M), floor_m)
    return x0, z0, np.where(np.isfinite(bot), bound, np.nan)


def _hold_pairs(xy: np.ndarray, tris: np.ndarray, sample_xy: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(sample, triangle, lambda)``: every sample centre inside each mesh
    triangle with its barycentric weights (a sample on a shared edge pairs
    with both triangles)."""
    order = np.lexsort((sample_xy[:, 1], sample_xy[:, 0]))
    sx = sample_xy[order, 0]
    ss, tt, ll = [], [], []
    for t, (a, b, c) in enumerate(np.asarray(tris, np.int64)):
        p = xy[[a, b, c]]
        lo, hi = p.min(0), p.max(0)
        k0, k1 = np.searchsorted(sx, lo[0] - 1e-9), np.searchsorted(sx, hi[0] + 1e-9, "right")
        if k1 <= k0:
            continue
        cand = order[k0:k1]
        q = sample_xy[cand]
        cand = cand[(q[:, 1] >= lo[1] - 1e-9) & (q[:, 1] <= hi[1] + 1e-9)]
        if not len(cand):
            continue
        q = sample_xy[cand]
        (x0, y0), (x1, y1), (x2, y2) = p
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-12:
            continue
        l0 = ((y1 - y2) * (q[:, 0] - x2) + (x2 - x1) * (q[:, 1] - y2)) / d
        l1 = ((y2 - y0) * (q[:, 0] - x2) + (x0 - x2) * (q[:, 1] - y2)) / d
        lam = np.c_[l0, l1, 1.0 - l0 - l1]
        inside = (lam >= -1e-9).all(1)
        ss.append(cand[inside])
        tt.append(np.full(int(inside.sum()), t))
        ll.append(np.clip(lam[inside], 0.0, 1.0))
    if not ss:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros((0, 3))
    return np.concatenate(ss), np.concatenate(tt), np.concatenate(ll)


def hold_heights(xy: np.ndarray, z: np.ndarray, tris: np.ndarray, free: np.ndarray,
                 sample_xy: np.ndarray, sample_bound: np.ndarray
                 ) -> tuple[np.ndarray, int]:
    """THE HOLD (module doc) on one mesh: ``(z_new, unresolved)``.

    ``xy`` / ``z`` the mesh vertices (plan metres, height), ``tris`` its
    triangles (vertex indices), ``free`` the vertices the hold may move,
    ``sample_xy`` / ``sample_bound`` the bound's sample centres and their
    heights in ``z``'s datum.  Each pass reads the drawn surface at every
    sample (the barycentric blend of its triangle's corners); at a sample
    standing over its bound it picks the free corner that carries the most
    of the excess (``lambda_k * (z_k - b)``) and lowers it by
    ``min(e / lambda_k, z_k - b)``; each vertex takes the largest lowering
    asked of it.  It stops when no sample stands over its bound or no such
    sample has a free corner over it (``unresolved``: those samples).  It
    only lowers, and never under a bound its own triangles carry."""
    z = np.asarray(z, float).copy()
    tris = np.asarray(tris, np.int64)
    free = np.asarray(free, bool)
    b_all = np.asarray(sample_bound, float)
    s, t, lam = _hold_pairs(np.asarray(xy, float), tris, np.asarray(sample_xy, float))
    if not len(s):
        return z, 0
    corner = tris[t]
    b = b_all[s]
    bad = np.zeros(len(s), bool)
    for _ in range(_HOLD_PASSES):
        zc = z[corner]
        e = (lam * zc).sum(1) - b
        bad = e > _HOLD_TOL_M
        if not bad.any():
            return z, 0
        over = np.maximum(zc[bad] - b[bad, None], 0.0)
        score = lam[bad] * over * free[corner[bad]]
        k = score.argmax(1)
        rows = np.arange(len(k))
        ok = score[rows, k] > 0.0
        if not ok.any():
            break
        lk = lam[bad][rows, k][ok]
        d = np.minimum(e[bad][ok] / lk, over[rows, k][ok])
        drop = np.zeros(len(z))
        np.maximum.at(drop, corner[bad][rows, k][ok], d)
        z -= drop
    zc = z[corner]
    bad = (lam * zc).sum(1) - b > _HOLD_TOL_M
    return z, int(len(np.unique(s[bad])))


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
