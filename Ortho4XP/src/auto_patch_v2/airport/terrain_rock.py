"""ROCK OUTCROPS AND ADDED HILLS ARE TERRAIN SHELLS (owner RULINGS
2026-11-25j; #2197 follow-up, #2272 family).

Owner (2026-11-25T21:54Z): "Rock outcrops should ideally be seated and
matched to terrain like other terrain shell style objects."  A pack may
lay a rock, a boulder field, a berm or a small hill on the ground as a
plain ``OBJECT`` row: relief the AUTHOR adds on top of the ground, under
``terrain_model.MIN_PLAN_M``, too low, too hard or too coarsely textured
for ``terrain_shell``'s photo-textured candidate, and -- placed on the
ground, not at an ``OBJECT_MSL`` datum -- never matched by
``terrain_shell.small_match``.  This module is the family's ROCK member:
it RECOGNISES such an object by a witness of NATURAL RELIEF, read on its
geometry only (RULINGS 05e: no names, no texture names), and hands it to
``terrain_shell``'s one path (one rigid frame, never split, the skirt seat
``shell_seat``, the hide offer ``terrain_model.quality``).

THE WITNESS (:func:`rock_shape`, one verdict per file version):

* PLAN -- its static solid spans ``terrain_shell.SHELL_MIN_PLAN_M`` or more
  and less than ``terrain_model.MIN_PLAN_M`` (a larger one is
  ``terrain_model``'s);
* RELIEF -- its top spans at least :data:`ROCK_MIN_RELIEF_M` between its
  5th and 95th percentiles;
* A HILLSIDE -- ``relief_skin``'s steep measure on its largest piece:
  at least ``relief_skin.MIN_STEEP`` of its cells slope over
  ``relief_skin.STEEP_GRADIENT`` (a mound laid gently over a field, a
  logo, a terrace of kerbs is not);
* ONE BODY, OR A FEW LARGE ONES -- at least ``relief_skin.MIN_SHARE`` of
  its plan lies in 8-connected pieces each spanning
  ``SHELL_MIN_PLAN_M`` or more (a berm cut by a road is two bodies; a lot
  of scattered stockpiles, a fence line, a row of crates is not);
* NO STOREY WALLS -- at most :data:`ROCK_MAX_CAPPED` of its surface is
  CAPPED WALL: a near-vertical face (``|n_y| <`` :data:`WALL_NY`) at least
  :data:`STOREY_M` tall whose top edge is an edge of a non-vertical face
  (a wall under a roof, a parapet under a deck).  Rock has no storeys;
  a building, a hangar, a blast fence on a plinth has.  Tree cards on a
  berm stand free, capped by nothing, and do not count.

The ``ATTR_hard`` and photo-texture gates of ``terrain_shell`` are NOT
read: a rock is often hard (you cannot taxi through it) and often wears a
tiled rock texture, not an orthophoto.

THE MATCH (``terrain_shell.small_match`` with ``Shape.rock``): its datum
is the author's -- the ``OBJECT_MSL`` elevation, or, for a plain or
``OBJECT_AGL`` row, the ground under its anchor plus its lift
(:func:`row_datum`: X-Plane stands such a row's zero on the terrain at
its anchor) -- and its top must LIE ON OUR GROUND at that datum
(``terrain_shell``'s level test).  Correlation with the DEM is NOT asked:
the relief is the author's addition, our DEM need not have it; the
witness above is the filter.  The hide offer is unchanged: a rock is
hidden only where fine elevation matches it (``terrain_model.quality``),
which relief our DEM lacks never does.

Calibration (2026-11-25, lane lrocks; the census over every installed
pack, ``tools/terrain_model_census``): see the RULINGS entry and the
lane's report.  Nothing here names a pack, an object or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

__all__ = ["ROCK_MIN_RELIEF_M", "ROCK_MAX_CAPPED", "WALL_NY", "STOREY_M",
           "capped_wall_share", "big_piece_share", "rock_shape", "row_datum", "rock_match"]

ROCK_MIN_RELIEF_M = 5.0
ROCK_MAX_CAPPED = 0.05
#: a face is a wall when its unit normal's ``|y|`` is under this
WALL_NY = 0.1
#: a wall this tall or taller is a storey
STOREY_M = 3.0
#: vertices closer than this coincide (m)
_WELD_M = 0.05


def capped_wall_share(vertices: np.ndarray, tris: np.ndarray) -> float:
    """NO STOREY WALLS (module doc): the area share of the solid ``tris``
    (indices into ``vertices``) that is capped wall."""
    p = vertices[tris].astype(float)
    if not len(p):
        return 0.0
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = 0.5 * np.linalg.norm(n, axis=1)
    total = float(area.sum())
    if total <= 0.0:
        return 0.0
    ny = np.abs(n[:, 1]) / np.maximum(2.0 * area, 1e-12)
    wall = ny < WALL_NY
    tall = wall & (np.ptp(p[:, :, 1], axis=1) >= STOREY_M)
    if not tall.any():
        return 0.0
    q = np.round(p / _WELD_M).astype(np.int64)
    capping = q[~wall & (area > 1e-6)].reshape(-1, 3)
    if not len(capping):
        return 0.0
    # the top edge of each tall wall: its two highest corners
    order = np.argsort(p[tall][:, :, 1], axis=1)[:, 1:]
    tops = np.take_along_axis(q[tall], order[:, :, None], axis=1)
    known = {tuple(v) for v in np.unique(capping, axis=0)}
    cap = np.array([tuple(a) in known and tuple(b) in known for a, b in tops], dtype=bool)
    return float(area[tall][cap].sum()) / total


def big_piece_share(covered: np.ndarray, cell_m: float, min_m: float) -> float:
    """ONE BODY, OR A FEW LARGE ONES (module doc): the share of the
    ``covered`` plan cells lying in 8-connected pieces spanning ``min_m``
    or more."""
    from scipy import ndimage
    total = int(covered.sum())
    if not total:
        return 0.0
    lab, _n = ndimage.label(covered, structure=np.ones((3, 3), dtype=bool))
    big = 0
    for k, sl in enumerate(ndimage.find_objects(lab), start=1):
        if sl is None:
            continue
        span = cell_m * max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start)
        if span >= min_m:
            big += int((lab[sl] == k).sum())
    return big / total


def _witness(g: _t.Any, tris: np.ndarray, grid: _t.Any) -> bool:
    """THE WITNESS's grid and wall gates (module doc) on a parsed geometry."""
    from ..geom.terrain_deck import CELL_M
    from . import relief_skin as _rs
    from .terrain_shell import SHELL_MIN_PLAN_M
    m = _rs._measures(grid)
    if m is None or m["steep"] < _rs.MIN_STEEP:
        return False
    if big_piece_share(grid.covered, CELL_M, SHELL_MIN_PLAN_M) < _rs.MIN_SHARE:
        return False
    return capped_wall_share(g.vertices, tris) <= ROCK_MAX_CAPPED


def rock_shape(path: str, g: _t.Any) -> "_t.Any | None":
    """THE WITNESS of a rock (module doc) on the parsed geometry ``g`` of
    ``path`` (one ``terrain_shell.small_shape`` refused): a
    ``terrain_model.Shape`` with ``small`` and ``rock`` set, or ``None``."""
    from . import terrain_model as _tm
    from .terrain_shell import SHELL_MIN_PLAN_M
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    plan = _tm._plan_m(g, ROCK_MIN_RELIEF_M)
    if not SHELL_MIN_PLAN_M <= plan < _tm.MIN_PLAN_M or not len(tris):
        return None
    grid = _tm._grid(g)
    if grid is None or not grid.covered.any():
        return None
    lo, hi = np.percentile(grid.top[grid.covered], [5.0, 95.0])
    if hi - lo < ROCK_MIN_RELIEF_M or not _witness(g, tris, grid):
        return None
    spread = _tm.photo_spread(g.vertices, _tm._vt_rows(path), tris)
    return _tm.Shape(grid, plan, float(hi - lo), spread, _tm.post_m(g.vertices, tris),
                     small=True, rock=True)


def row_datum(kind: str, elev: _t.Any, xy: tuple[float, float],
              dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]) -> "float | None":
    """THE MATCH's datum of a rock's row (module doc): the ``OBJECT_MSL``
    elevation, else the ground under the anchor plus the ``OBJECT_AGL``
    lift (0 for a plain row); ``None`` with no ground there."""
    if kind == "OBJECT_MSL":
        return None if elev is None else float(elev)
    z = float(np.asarray(dem_many(np.array([float(xy[0])]), np.array([float(xy[1])])),
                         dtype=float)[0])
    if not np.isfinite(z):
        return None
    lift = float(elev or 0.0) if kind == "OBJECT_AGL" else 0.0
    return z + lift


def rock_match(shape: _t.Any, xy: tuple[float, float], heading: float,
               dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray], datum: float,
               fine: "_t.Callable | None" = None, water: "_t.Callable | None" = None
               ) -> "dict[str, float] | None":
    """THE MATCH and THE SEAT of one placement of a rock (module doc):
    ``terrain_model.match``'s record, or ``None``.  Its BASE rests on our
    ground at ``datum``: the median of ``|DEM - (datum + bottom)|`` over
    its outer rim is at most ``terrain_shell.SHELL_LEVEL_M``."""
    from . import terrain_model as _tm
    from .terrain_shell import SHELL_LEVEL_M
    grid = shape.grid
    ri, rj = np.nonzero(_tm.outer_rim(grid.covered))
    rx, ry = _tm._world(grid, ri, rj, xy, heading)
    d = np.asarray(dem_many(rx, ry), dtype=float)
    ok = np.isfinite(d)
    if not len(ok) or ok.mean() < 0.9:
        return None
    level = float(np.median(np.abs(d[ok] - (datum + grid.bot[ri, rj][ok]))))
    if level > SHELL_LEVEL_M:
        return None
    z0 = _tm.wet_cap(grid, xy, heading, dem_many, water, datum)
    cover, hideable = _tm.quality(shape, xy, heading, dem_many, fine)
    return {"z0": z0, "corr": 0.0, "peak_err": 0.0, "fit_m": float(np.median(d[ok]) - datum),
            "quality_cover": cover, "hideable": hideable, "level_m": level}
