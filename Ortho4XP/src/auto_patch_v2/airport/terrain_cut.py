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
    the 0.5 m ground bar (``O4_Mesh_Utils._apply_hold_curv_weights``);
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

A FILL RECORD'S BAND (#2077 round 2 R1): a drawn point is supported by one
triangle edge plus one posting diagonal, so a terrain composite whose
ground is filled to its rim (``terrain_fill``) holds the rim's level
``band_m`` = ``W + s`` inside the plan (the fill's shoulder plus the
larger posting step, ``terrain_cut_stage._fill_band``) -- never over the
lowest top within ``clip_m`` = one posting diagonal.  Every other record
keeps :data:`BAND_M`.

THE SHELL (#2272 round 2, spec ``docs/specs/terrain-shells-2272-round2.md``;
owner RULINGS 2026-11-24k (3)): a small terrain shell kept at its author's
``OBJECT_MSL`` datum writes ``cut["shell"]``.  It has a BODY (deeper than
:data:`BAND_M` from its plan edge, :func:`body_mask`) and an EDGE BAND (the
outer ``BAND_M``, where a shell carries its skirt -- 4-10 m of rise in its
outer 5 m at TFFJ).

* S2 THE BODY SHOWS: under the body the ground is cut to its own top
  eroded over the body alone (``erode(top, ERODE_M) - UNDER_M``, the skirt's
  low never bleeds in); in the fill band's inner part (``BAND_M`` < edge
  <= ``W + s``) never under the lowest body top within one posting diagonal.
* S3 THE EDGE BAND IS NOT CUT (``_bound(..., skirt=True)`` is ``inf``
  there): our ground may stand over the shell there -- the skirt is buried.
* S4 THE FEATHER (``terrain_fill.edge_feather``): the ground within
  ``terrain_fill.FEATHER_M`` of the body's edge is lowered toward it, from
  the residuals read before any cut; one correction over every kept shell.
* S5 NO EDGE FLOATS: the rim fill (``terrain_fill.rim_fill``) raises the
  ground to every rim cell still over it -- uncapped in the band, capped
  by the cut under the body.
* S6 THE BODY IS HELD BY THE MESH: its BODY RING (:func:`body_rings`, the
  :func:`hold_bound` body samples deeper than ``BAND_M - HOLD_CELL_M``)
  is a second DUMMY constrained ring, and THE HOLD lowers the free
  vertices inside it until every drawn triangle stands under ``z0 + top -
  UNDER_M`` at every 1 m body sample: the outline ring's vertices FIXED,
  a road ribbon's vertex under the body FREE, water / patch pins / patch
  INTERP_ALT FIXED, the water floor standing.
* UNDER WATER (owner RULINGS 2026-11-25a (3)): a kept shell whose rim
  reaches the water is meant to run under it (modelled underwater cliffs).
  A body edge, a rim cell or a body sample seated under the sea datum is no
  feather support, no rim-fill support and no hold sample; the feather
  never lowers under ``min(ground, 0)``; water stays a datum (its vertices
  fixed, the fills' change kept off them, ``terrain_cut_stage``).

THE SHELL's consumer rows (the census above holds for the rest; RULINGS
2026-08-30l, the spec's section 5): Triangle4XP reads the cut, feather and
rim fill (the dry raster within ``DRY_M`` of mapped water); the curvature
weights ride the fill records' boxes; the outline and body rings are DUMMY
lines; ``unfill_water`` / ``refill_land`` carry the feather in the delta
sidecar; the road banks run before the hold and may be lowered under a
body; roads and an unpatched airport's pavement follow the feathered and
cut ground; the airport patch, ``ProductionDem``, the masks and the DSF
elevation raster are never changed; a hidden shell has no cut, feather,
rings nor hold; riders follow the cut ground (reported, not judged); two
abutting shells are both cut and take one feather.

Pure geometry: the tile glue that reads the plans and writes the raster is
``auto_patch/terrain_cut_stage``.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np

from ..geom.terrain_deck import CELL_M, DeckGrid, TerrainFit, target_at

__all__ = ["ERODE_M", "BAND_M", "HOLD_CELL_M", "cut_fit", "projector", "cut_heights",
           "outline_rings", "plan_region", "body_rings", "body_region", "body_mask",
           "plan_box", "hold_bound", "hold_heights"]

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


def _disc(radius_m: float, cell: float) -> np.ndarray:
    """A disc footprint of ``radius_m`` on a ``cell``-metre grid (one cell
    at least)."""
    k = max(1, int(round(float(radius_m) / cell)))
    return np.hypot(*np.mgrid[-k:k + 1, -k:k + 1]) <= k


def _erode(surf: np.ndarray, where: np.ndarray, cell: float, radius_m: float) -> np.ndarray:
    """The lowest ``surf`` of the cells ``where`` within ``radius_m``."""
    from scipy import ndimage
    return ndimage.minimum_filter(np.where(where, surf, np.inf), footprint=_disc(radius_m, cell),
                                  mode="constant", cval=np.inf)


def _edge(cov: np.ndarray, cell: float) -> tuple[np.ndarray, np.ndarray]:
    """``(rim, edge)``: the edge cells (covered, touching an uncovered one,
    8-neighbours: the outer rim and the edge of every hole) and every
    cell's distance to the nearest (m, cell centre to cell centre)."""
    from scipy import ndimage
    rim = cov & ndimage.binary_dilation(~np.pad(cov, 1), np.ones((3, 3), bool))[1:-1, 1:-1]
    return rim, ndimage.distance_transform_edt(~rim) * cell


def body_mask(covered: np.ndarray, cell: float = CELL_M, band_m: float = BAND_M) -> np.ndarray:
    """A shell's BODY (module doc, THE SHELL) on a ``cell``-metre plan grid:
    the covered cells farther than ``band_m`` from the plan's edge."""
    cov = np.asarray(covered, bool)
    return cov & (_edge(cov, cell)[1] > band_m)


def _bound(bot: np.ndarray, top: np.ndarray, cell: float, erode_m: float,
           floor_m: float, band_m: float = BAND_M, clip_m: float | None = None,
           skirt: bool = False) -> np.ndarray:
    """The CUT SURFACE (module doc) of a plan binned on a ``cell``-metre
    grid (``bot`` / ``top`` ``nan`` where uncovered), in metres over the
    model's zero; ``inf`` / undefined off the plan.  ``erode_m``: the
    erosion radius.  ``floor_m`` == 0 (a terrain model): the edge band
    never under the edge's lowest surface.  ``floor_m`` > 0 (a ground
    object, THE FLOOR): the band keeps its own top eroded, beyond it the
    floor eroded -- no edge-lowest term (an arm's rim underside over low
    open ground is not the ground's bound).  ``band_m`` > :data:`BAND_M`
    (a FILL record, #2077 round 2 R1, ``floor_m`` == 0 only): the cells
    with ``BAND_M < edge <= band_m`` stand at least at ``min(L, T)`` --
    ``L`` the edge-lowest term read at the cell's nearest edge cell, ``T``
    the lowest top within ``clip_m`` of the cell -- so the drop from the
    rim's level to the eroded top lies a triangle and a posting diagonal
    behind the rim, never under it.  ``skirt`` (a SHELL, module doc THE
    SHELL, #2272 round 2 S2/S3): the edge band is ``inf`` (never cut); the
    body is its own top eroded over the body alone (the skirt's low never
    bleeds in), never under the lowest body top within ``clip_m`` where
    ``BAND_M < edge <= band_m``."""
    cov = np.isfinite(bot)
    rim, edge = _edge(cov, cell)
    if skirt:
        body = cov & (edge > BAND_M)
        out = _erode(top, body, cell, erode_m)
        if band_m > BAND_M:
            near_top = _erode(top, body, cell, float(clip_m if clip_m is not None else erode_m))
            reach = body & (edge <= band_m)
            out = np.where(reach, np.maximum(out, near_top), out)
        return np.where(body, out, np.inf)
    from scipy import ndimage
    eroded = _erode(top, cov, cell, erode_m)
    if floor_m > 0.0:
        return np.where(edge <= BAND_M, eroded,
                        _erode(_floor(bot, top, floor_m), cov, cell, erode_m))
    lowest = ndimage.maximum_filter(np.where(rim, bot, -np.inf), footprint=_disc(BAND_M, cell),
                                    mode="constant", cval=-np.inf)
    out = np.where(edge <= BAND_M, np.maximum(eroded, lowest), eroded)
    if band_m <= BAND_M or not rim.any():
        return out
    _, (ni, nj) = ndimage.distance_transform_edt(~rim, return_indices=True)
    near_top = _erode(top, cov, cell, float(clip_m if clip_m is not None else erode_m))
    reach = (edge > BAND_M) & (edge <= band_m)
    return np.where(reach, np.maximum(out, np.minimum(lowest[ni, nj], near_top)), out)


def _cut_grid(grid: DeckGrid, erode_m: float = ERODE_M, floor_m: float = 0.0,
              band_m: float = BAND_M, clip_m: float | None = None,
              skirt: bool = False) -> DeckGrid:
    """The CUT SURFACE of a model's plan grid (module doc) as a
    :class:`DeckGrid` whose ``top`` is the bound (``bot`` the model's own;
    the cut never fills).  ``erode_m``: the erosion radius (a ground object
    carrying riders takes one cell, ``bridged_ground.ERODE_M``).
    ``floor_m`` > 0: the bound of THE FLOOR; ``band_m`` / ``clip_m``: a fill
    record's edge band (:func:`_bound`); ``skirt``: a shell's (THE SHELL)."""
    bound = _bound(grid.bot, grid.top, CELL_M, erode_m, floor_m, band_m, clip_m, skirt)
    return DeckGrid(grid.x0, grid.z0, grid.bot.copy(),
                    np.where(grid.covered, bound, np.nan))


def cut_fit(grid: DeckGrid, zero: float, heading: float,
            erode_m: float = ERODE_M, floor_m: float = 0.0,
            band_m: float = BAND_M, clip_m: float | None = None,
            skirt: bool = False) -> TerrainFit:
    """The cut as a :class:`TerrainFit` anchored at the frame origin (the
    model's anchor), seated at ``zero``, filling nothing; ``floor_m`` > 0:
    cut to the object's floor per cell (module doc, THE FLOOR); ``band_m``
    / ``clip_m``: a fill record's edge band (:func:`_bound`, #2077 R1);
    ``skirt``: a shell's band is never cut, its body is (THE SHELL)."""
    cut = _cut_grid(grid, erode_m, floor_m, band_m, clip_m, skirt)
    return TerrainFit("cut", "", (0.0, 0.0), float(heading), float(zero), 1.0,
                      cut.area_m2, 0.0, cut, fill=False)


def hold_bound(tris: np.ndarray, erode_m: float, floor_m: float, skirt: bool = False
               ) -> tuple[float, float, np.ndarray]:
    """``(x0, z0, bound)``: THE HOLD's bound (module doc) of the authored
    triangles ``tris`` (``(n, 3, 3)``, the plan's static solid) on the
    :data:`HOLD_CELL_M` grid, metres over the model's zero (``nan`` off
    the plan): the cut surface's rule eroded by one cell -- a drawn
    triangle held under it at every sample centre stands under the object
    between them -- never wider than the record's ``erode_m``.  ``skirt``
    (a shell, THE SHELL S6): the top eroded one cell at the BODY's samples
    alone -- deeper than ``BAND_M - HOLD_CELL_M`` -- ``nan`` in the edge band."""
    from .terrain_shaped import bin_triangles
    x0, z0, bot, top = bin_triangles(np.asarray(tris, float), HOLD_CELL_M)
    cov = np.isfinite(bot)
    if skirt:
        bound = _erode(top, cov, HOLD_CELL_M, HOLD_CELL_M)
        return x0, z0, np.where(body_mask(cov, HOLD_CELL_M, BAND_M - HOLD_CELL_M), bound, np.nan)
    bound = _bound(bot, top, HOLD_CELL_M, min(float(erode_m), HOLD_CELL_M), floor_m)
    return x0, z0, np.where(cov, bound, np.nan)


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
                 sample_xy: np.ndarray, sample_bound: np.ndarray,
                 floor: np.ndarray | None = None) -> tuple[np.ndarray, int]:
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
    only lowers, and never under a bound its own triangles carry.
    ``floor`` (per vertex, optional): no vertex is lowered under it -- the
    water datum beside a shore vertex (#2053, owner 2026-11-13: never lower
    shore points below water); a sample it leaves over its bound counts as
    ``unresolved``."""
    z = np.asarray(z, float).copy()
    tris = np.asarray(tris, np.int64)
    free = np.asarray(free, bool)
    b_all = np.asarray(sample_bound, float)
    s, t, lam = _hold_pairs(np.asarray(xy, float), tris, np.asarray(sample_xy, float))
    if not len(s):
        return z, 0
    corner = tris[t]
    b = b_all[s]
    fl = (np.full(len(z), -np.inf) if floor is None
          else np.asarray(floor, float))[corner]
    bad = np.zeros(len(s), bool)
    for _ in range(_HOLD_PASSES):
        zc = z[corner]
        e = (lam * zc).sum(1) - b
        bad = e > _HOLD_TOL_M
        if not bad.any():
            return z, 0
        over = np.maximum(zc[bad] - np.maximum(b[bad, None], fl[bad]), 0.0)
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


def _cells_region(ii: np.ndarray, jj: np.ndarray, x0: float, z0: float, cell: float,
                  grow: float = 0.0, runs: bool = False) -> _t.Any:
    """The union of the ``cell``-metre boxes of grid cells ``(ii, jj)``
    (centres ``x0 + i * cell`` / ``z0 + j * cell``) -- with ``runs`` one box
    per run of cells along ``i`` (the same region, far fewer boxes) --
    grown by ``grow`` (mitred) and simplified within ``grow + cell / 4``."""
    import shapely
    h = cell / 2.0
    if not runs:
        x, z = x0 + cell * np.asarray(ii), z0 + cell * np.asarray(jj)
        region = shapely.union_all(shapely.box(x - h, z - h, x + h, z + h))
        if grow > 0.0:
            region = region.buffer(grow, join_style="mitre")
        return region.simplify(grow + h / 2.0)
    o = np.lexsort((ii, jj))
    i, j = np.asarray(ii)[o], np.asarray(jj)[o]
    new = np.r_[True, (j[1:] != j[:-1]) | (i[1:] != i[:-1] + 1)]
    start = np.flatnonzero(new)
    end = np.r_[start[1:], len(i)] - 1
    x_lo, x_hi = x0 + cell * i[start] - h, x0 + cell * i[end] + h
    z = z0 + cell * j[start]
    region = shapely.union_all(shapely.box(x_lo, z - h, x_hi, z + h))
    if grow > 0.0:
        region = region.buffer(grow, join_style="mitre")
    return region.simplify(grow + h / 2.0)


def _rings(fit: TerrainFit, region: _t.Any, to_ll: _t.Callable) -> list[np.ndarray]:
    """A plan-frame region's outer rings and holes as ``(lon, lat)`` rings."""
    from shapely.geometry import MultiPolygon, Polygon
    polys = region.geoms if isinstance(region, MultiPolygon) else [region]
    out = []
    for poly in polys:
        if not isinstance(poly, Polygon) or poly.is_empty:
            continue
        for ring in (poly.exterior, *poly.interiors):
            lo, la = to_ll(*_to_frame(fit, np.asarray(ring.coords, float)))
            out.append(np.c_[lo, la])
    return out


def plan_region(fit: TerrainFit) -> _t.Any:
    """The plan's covered cells as one region in the authored plan frame
    ``(x, z)`` -- what :func:`outline_rings` draws; ``None`` when empty."""
    ii, jj = np.nonzero(fit.grid.covered)
    if not len(ii):
        return None
    return _cells_region(ii, jj, fit.grid.x0, fit.grid.z0, CELL_M)


def outline_rings(fit: TerrainFit, to_ll: _t.Callable) -> list[np.ndarray]:
    """The plan's EDGE -- the boundary of its covered cells, outer rings and
    holes -- as ``(n, 2)`` ``(lon, lat)`` rings, simplified within a
    quarter cell (the constrained line the mesh draws there)."""
    region = plan_region(fit)
    return [] if region is None else _rings(fit, region, to_ll)


def body_region(tris: np.ndarray, held: "tuple | None" = None) -> _t.Any:
    """A shell's BODY RING region (THE SHELL S6) in the authored plan frame:
    the :func:`hold_bound` body samples' cells (``held``: its result when
    the caller holds it) grown by half a cell and simplified, so every
    body sample centre lies a quarter cell or more inside it; ``None``
    without a body."""
    x0, z0, bound = held if held is not None else hold_bound(tris, ERODE_M, 0.0, skirt=True)
    ii, jj = np.nonzero(np.isfinite(bound))
    if not len(ii):
        return None
    return _cells_region(ii, jj, x0, z0, HOLD_CELL_M, HOLD_CELL_M / 2.0, runs=True)


def body_rings(fit: TerrainFit, to_ll: _t.Callable, tris: np.ndarray) -> list[np.ndarray]:
    """A shell's BODY RING (THE SHELL S6), the second DUMMY constrained ring
    beside its plan outline, as ``(lon, lat)`` rings: it encloses every
    1 m sample deeper than ``BAND_M - HOLD_CELL_M`` (:func:`body_region`
    of the authored solid ``tris``), so no drawn triangle spans from the
    rim to the body."""
    region = body_region(tris)
    return [] if region is None else _rings(fit, region, to_ll)
