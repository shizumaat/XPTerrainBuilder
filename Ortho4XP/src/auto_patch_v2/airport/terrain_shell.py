"""SMALL TERRAIN SHELLS: A PACK'S PHOTO-TEXTURED ROCKS, CLIFFS AND ISLETS
(issue #2272; owner decisions 2026-11-24T15:33Z).

Owner (2026-11-24T15:19Z, TFFJ): "large terrain shell objects used to
model terrain features ... if they are not hidden we are supposed to grade
the terrain to tuck under them and seat them correctly, currently they are
floating."  TFFJ's sixteen shells are 88-474 m across and 12-93 m tall:
under ``terrain_model``'s :data:`~terrain_model.MIN_PLAN_M` (500 m) and
:data:`~terrain_model.MIN_RELIEF_M` (50 m), so none was recognised; the
11d conversion turned each on-ground, lifted it 7-40 m, and the split
re-anchored seven of them like buildings.  This module is the family's
SMALL member: a shell under ``MIN_PLAN_M`` is recognised here and then
travels ``terrain_model``'s one path (never split, one rigid frame, the
ground cut under it and filled up to its rim, the hide offer).

THE CANDIDATE (no DEM, :func:`small_shape`):

* PLAN -- its static solid spans at least :data:`SHELL_MIN_PLAN_M` (and
  less than ``MIN_PLAN_M``: a larger one is ``terrain_model``'s);
* RELIEF -- its top spans at least :data:`SHELL_MIN_RELIEF_M` between its
  5th and 95th percentiles;
* A PHOTO-TEXTURED TOP -- one texel density, at most
  :data:`SHELL_MAX_PHOTO_SPREAD` (tighter than a mountain's: at this size a
  roof photographed from above is the look-alike);
* SOFT -- no upward plan is ``ATTR_hard`` (:data:`SHELL_MAX_HARD`): rock
  and scrub, not a deck, a roof or a pad;
* ONE STEEP PIECE -- ``relief_skin``'s measures on its plan grid: its
  largest 8-connected component holds at least ``relief_skin.MIN_SHARE``
  of the plan with the top relief above, and at least
  ``relief_skin.MIN_STEEP`` of its cells slope over
  ``relief_skin.STEEP_GRADIENT`` (a hillside, not a terrace of kerbs).

Calibration 2026-11-24 (#2272), every OBJ8 of the 1,035 placements of the
196 airport packs installed whose objects pass the shape gates: 948 are
plain ``OBJECT`` rows and 52 ``OBJECT_AGL`` (not this module's); of the 35
``OBJECT_MSL`` rows, TFFJ's 16 shells and TNCS's Saba island match, a
LIPQ kerb terrace (largest piece 0.81, relief 0.6 m) is refused by ONE
STEEP PIECE, and CYUL's hangar footers, KCRW's Air National Guard hangars
and KDFW's terminal pieces by the level test (the nearest, KCRW, 5.45 m
over a 5.05 m bound); three rows had no raster to read.

THE MATCH (:func:`small_match`): only a row the author wrote
``OBJECT_MSL`` -- the author's own height is the seat (owner decision 3),
and a shell this small spans one to fifteen posts of a 30-90 m DEM, too
few to witness its shape on their own.  At its datum its top LIES ON OUR
GROUND: the median of ``|DEM - (datum + top)|`` over its covered cells is
at most ``max(SHELL_LEVEL_M, SHELL_LEVEL_SHARE x relief)``, and either the
top follows the DEM (Pearson ``r`` at least ``terrain_model.MIN_CORR``) or
the DEM cannot see it: its spread over the plan (5th-95th percentile) is
under :data:`SHELL_BLIND_SHARE` of the shell's relief (an islet our mesh
lacks), or no source fine enough to put :data:`SHELL_MIN_POSTS` posts
across the shell's plan covers it (a 90 m cliff on a 30 m inset).

THE SEAT (owner decision 3): the frame zero is the author's datum -- "not
refitted to our coarser terrain" -- capped over a wet rim exactly as
``terrain_model`` caps its fit (the skirt stays under the water), and the
tile build tucks our ground under it (``terrain_cut``, ``terrain_fill``).
The hide offer is ``terrain_model.quality``'s, unchanged.
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["SHELL_MIN_PLAN_M", "SHELL_MIN_RELIEF_M", "SHELL_MAX_PHOTO_SPREAD",
           "SHELL_MAX_HARD", "SHELL_LEVEL_M", "SHELL_LEVEL_SHARE", "SHELL_BLIND_SHARE",
           "SHELL_MIN_POSTS",
           "small_shape", "small_match"]

SHELL_MIN_PLAN_M = 50.0
SHELL_MIN_RELIEF_M = 10.0
SHELL_MAX_PHOTO_SPREAD = 0.1
SHELL_MAX_HARD = 0.0
SHELL_LEVEL_M = 5.0
SHELL_LEVEL_SHARE = 0.5
SHELL_BLIND_SHARE = 0.25
SHELL_MIN_POSTS = 4.0


def small_shape(path: str, g: _t.Any) -> "_t.Any | None":
    """THE CANDIDATE TEST of a small shell (module doc) on the parsed
    geometry ``g`` of ``path``: a ``terrain_model.Shape`` with ``small``
    set, or ``None``."""
    from . import terrain_model as _tm
    plan = _tm._plan_m(g, SHELL_MIN_RELIEF_M)
    if not SHELL_MIN_PLAN_M <= plan < _tm.MIN_PLAN_M:
        return None
    from .ground_shell import _hard_share
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    if not len(tris) or _hard_share(g, tris) > SHELL_MAX_HARD:
        return None
    shape = _tm._gated(path, g, plan, SHELL_MAX_PHOTO_SPREAD, SHELL_MIN_RELIEF_M, small=True)
    if shape is None:
        return None
    from . import relief_skin as _rs
    m = _rs._measures(shape.grid)
    if (m is None or m["share"] < _rs.MIN_SHARE or m["relief_m"] < SHELL_MIN_RELIEF_M
            or m["steep"] < _rs.MIN_STEEP):
        return None
    return shape


def _dem_sees(shape: _t.Any, d: np.ndarray, xs: np.ndarray, ys: np.ndarray,
              fine: "_t.Callable | None") -> bool:
    """Can the DEM witness the shell's shape (module doc)?  Not when its
    spread over the plan is under :data:`SHELL_BLIND_SHARE` of the
    shell's relief, nor when no source of ``plan / SHELL_MIN_POSTS`` or
    finer covers the plan (``fine``; ``None``: unknown, read as seeing)."""
    from . import terrain_model as _tm
    if float(np.subtract(*np.percentile(d, [95.0, 5.0]))) < SHELL_BLIND_SHARE * shape.relief_m:
        return False
    if fine is None or not len(xs):
        return True
    got = _tm._fine_at(fine, xs, ys, shape.plan_m / SHELL_MIN_POSTS)
    return float(np.mean(got)) >= _tm.MIN_QUALITY_COVER


def small_match(shape: _t.Any, xy: tuple[float, float], heading: float,
                dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                datum: "float | None", fine: "_t.Callable | None" = None,
                water: "_t.Callable | None" = None) -> "dict[str, float] | None":
    """THE MATCH and THE SEAT of one placement of a small shell (module
    doc): ``terrain_model.match``'s record, or ``None``.  ``datum``: the
    row's ``OBJECT_MSL`` elevation (``None``: not an ``OBJECT_MSL`` row)."""
    from . import terrain_model as _tm
    if datum is None:
        return None
    grid = shape.grid
    ii, jj = np.nonzero(grid.covered)
    xs, ys = _tm._world(grid, ii, jj, xy, heading)
    dem = np.asarray(dem_many(xs, ys), dtype=float)
    ok = np.isfinite(dem)
    if not len(ok) or ok.mean() < 0.9:
        return None
    top, d = grid.top[ii, jj][ok], dem[ok]
    level = float(np.median(np.abs(d - (float(datum) + top))))
    if level > max(SHELL_LEVEL_M, SHELL_LEVEL_SHARE * shape.relief_m):
        return None
    corr = (float(np.corrcoef(top, d)[0, 1])
            if float(np.std(top)) > 0.0 and float(np.std(d)) > 0.0 else 0.0)
    if corr < _tm.MIN_CORR and _dem_sees(shape, d, xs, ys, fine):
        return None
    fit = float(np.median(d - top))
    peak_err = abs(float(top.max()) + fit - float(d.max())) / shape.relief_m
    z0 = _tm.wet_cap(grid, xy, heading, dem_many, water, float(datum))
    cover, hideable = _tm.quality(shape, xy, heading, dem_many, fine)
    return {"z0": z0, "corr": corr, "peak_err": float(peak_err), "fit_m": fit,
            "quality_cover": cover, "hideable": hideable, "level_m": level}
