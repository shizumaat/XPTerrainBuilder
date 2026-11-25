"""TERRAIN-MODELLING OBJECTS ARE SEATED SO NO VISIBLE EDGE FLOATS (owner
RULINGS 2026-11-13i, issues #2036 (c) and #2040).

Owner (2026-11-13T04:40Z, SBRJ's Sugarloaf): "ideally we can find a close
match to terrain, and realize it's modeling a feature ... and see it's
similar heigh so we know it needs to be seated at sea level so it just
covers the terrain."  (04:46Z, KHAF's bluff shell) "seating on top of the
hill so it floats, instead of down so it's lowest edges are on the
ground."  (04:49Z) "we don't want any visible edge to be floating."

A pack may model a piece of TERRAIN as one object -- a whole mountain, a
bluff along the water -- with an orthophoto laid over its shape.  Split
into bodies and re-anchored like a building it lands far from its frame
(Sugarloaf: a "class other" body anchored 330 m away, -81.77 m) or rides a
hilltop (KHAF ``mesh/mesh01``).  This module RECOGNISES one, by its
geometry and the DEM only (RULINGS 05e -- no names), and SEATS it.

THE CANDIDATE (no DEM; one verdict per file version, :func:`shape_of`):

* PLAN -- its static solid spans at least :data:`MIN_PLAN_M` on its longer
  plan side;
* RELIEF -- its top surface (the highest solid per ``CELL_M`` cell) spans
  at least :data:`MIN_RELIEF_M` between its 5th and 95th percentiles: a
  hill, not a roofscape;
* A PHOTO-TEXTURED TOP -- its upward-facing triangles carry ONE texel
  density: an orthophoto stretched over a terrain shape maps every square
  metre of plan to the same image area, however the shape was unwrapped,
  so the plan-weighted 10th-90th percentile spread of log10(texture area
  / plan area) is at most :data:`MAX_PHOTO_SPREAD` (a factor of about
  2.2).  A building or a bridge packs facades, roofs and details into an
  atlas at many densities.

THE MATCH (the DEM under the placement, :func:`match`): the top surface
sampled over its covered cells follows the ground --

* SHAPE -- Pearson correlation of top and DEM at least :data:`MIN_CORR`;
* PEAK -- the top shifted by its median offset from the DEM peaks within
  :data:`MAX_PEAK_ERR` of its relief of the DEM's peak ("similar height").

THE SEAT (#2077, owner 2026-11-15: "where our ground stands below such a
composite, fill the ground up to it instead of sinking the composite to
its lowest rim"): the object's ``y = 0`` plane is set at its RIGID L1 FIT
to the ground (``terrain_shaped.fit``) -- the hill where the ground is --
and the tile build FILLS the ground up to every outer-rim edge that then
stands over it (``cut["fill"]``, ``airport/terrain_fill``), so no visible
edge floats.  Over water the ground cannot be filled: where at least
:data:`WATER_RIM_SHARE` of the outer rim (every covered cell touching the
uncovered exterior) lies over water the zero is never above ``min`` over
those wet rim cells of (ground - bottom), the skirt under the water.  (The
2026-11-13i seat, ``min`` over the whole outer rim, is :func:`rim_seat`:
it sank LOWS's Festungsberg 20 m into a crater of its own.)  The seat is
one rigid frame: every row sharing the model's origin (the buildings a shell
carries, the cable-car stations on Sugarloaf) is written as an
``OBJECT_MSL`` row at ``z0`` plus its own authored lift, so each keeps its
place on the shell.  A terrain model's origin set is never split, never
re-anchored, never read as a pit, a pad or a deck (``obj8``'s
``terrain_feature`` path, RULINGS 2026-10-20aq).

HIDING (the pack adjustment "Hide terrain objects", off by default) is
offered only where QUALITY ELEVATION models the same ground
(:func:`quality`, #2077 section 4.1): at least :data:`MIN_QUALITY_COVER` of
the model's cells lie inside an inset whose source pixel is
:data:`QUALITY_PIXEL_M` or finer AND no coarser than the shell's own post
(the median plan edge of its upward triangles, at least 1 m), and at the
L1 fit to that ground the top correlates with it (at least
:data:`MIN_QUALITY_CORR`) and its 90th-percentile departure is at most
``max(QUALITY_P90_M, QUALITY_P90_SHARE x relief)``.  A model the user hid
(``hidden``, the pack's answer) dissolves: its own row is left out
(``ground_shell``'s HIDDEN path) and the rows of its frame are read like
any object.
"""
from __future__ import annotations

import dataclasses as _dc
import functools
import math
import os
import typing as _t

import numpy as np

from ..geom.terrain_deck import CELL_M, DeckGrid

__all__ = ["MIN_PLAN_M", "MIN_RELIEF_M", "MAX_PHOTO_SPREAD", "MIN_CORR", "MAX_PEAK_ERR",
           "QUALITY_PIXEL_M", "MIN_QUALITY_COVER", "MIN_QUALITY_CORR", "QUALITY_P90_M",
           "QUALITY_P90_SHARE", "WATER_RIM_SHARE", "SEAT",
           "Shape", "TerrainModel", "shape_of", "photo_spread", "match", "outer_rim",
           "placement_models", "set_members", "member_lift", "seat_records", "log_line",
           "wet_cap", "model_paths",
           "hideable_paths", "plan_grid", "plan_solid", "rim_seat", "post_m", "quality"]

MIN_PLAN_M = 500.0
MIN_RELIEF_M = 50.0
MAX_PHOTO_SPREAD = 0.35
MIN_CORR = 0.6
MAX_PEAK_ERR = 0.25
QUALITY_PIXEL_M = 10.0
MIN_QUALITY_COVER = 0.9
MIN_QUALITY_CORR = 0.9
#: the hide offer's agreement (#2077 4.1, provisional): the 90th
#: percentile of |ground - top| at the L1 fit at most the larger of these
QUALITY_P90_M = 3.0
QUALITY_P90_SHARE = 0.1
#: the shell's own post is never read finer than this (m)
_MIN_POST_M = 1.0
#: the least share of the outer rim over water that caps the seat (module doc)
WATER_RIM_SHARE = 0.05
#: an upward-facing triangle (unit normal ``y`` at least this) is the top
_UP_NY = 0.5
#: the least plan area (m2) of a triangle the density reads
_MIN_TRI_M2 = 1.0
#: the seat record's ``seat`` value (``RebakePlan.authored_seats``;
#: ``terrain_shaped.row_seats`` writes it)
SEAT = "terrain model"


@_dc.dataclass(frozen=True)
class Shape:
    """A candidate's top and bottom on the plan grid (the ``DeckGrid`` of
    its static solid) and its candidate measures."""

    grid: DeckGrid
    plan_m: float
    relief_m: float
    photo_spread: float
    #: the shell's own post: the median plan edge of its upward triangles
    #: (m, at least ``_MIN_POST_M``; the hide offer's resolution test)
    post_m: float = _MIN_POST_M
    #: a SMALL TERRAIN SHELL (``terrain_shell``, #2272): under
    #: :data:`MIN_PLAN_M`, matched and seated by that module's law
    small: bool = False


@_dc.dataclass(frozen=True)
class TerrainModel:
    """One placement recognised as a terrain model, and its seat."""

    id: str
    path: str
    xy: tuple[float, float]
    heading: float
    #: the frame zero every row of its origin set is seated at (MSL m)
    z0: float
    corr: float
    peak_err: float
    #: the median offset of its top from the DEM ("similar height")
    fit_m: float
    area_m2: float
    relief_m: float
    #: share of its cells under quality elevation, and the hide offer
    quality_cover: float = 0.0
    hideable: bool = False
    #: the resolved OBJ8 file (the tile's cut re-reads its shape from it,
    #: ``airport/terrain_cut``); ``""`` in a capture written before it
    file: str = ""
    #: how ``z0`` was read when not by the outer rim: ``""`` (this module)
    #: or ``bridged_ground.SEAT_BY`` (#2053: a ground object in the water
    #: on its bridges' far ends -- the match fields above are then 0)
    seat_by: str = ""
    #: the cut's erosion radius when not ``terrain_cut.ERODE_M`` (m)
    erode_m: "float | None" = None
    #: > 0: the cut reads each cell's LOWEST surface where a roof stands at
    #: least this far over it -- its ground, not its roofs
    #: (``terrain_cut.cut_fit`` ``floor_m``; #2053 round 2)
    cut_floor_m: float = 0.0
    #: how far the other seat points sink under their ground at ``z0`` (m)
    spread_m: float = 0.0
    #: a GROUND SHELL's verdict (``ground_shell``, issue #2056): ``"seated"``
    #: (it lies on the ground at ``z0``) or ``"hidden"`` (its row is left
    #: out of the written DSF); ``""`` for a terrain model of this module
    ground: str = ""
    #: the authored zero of a model written ``OBJECT_MSL`` (its elevation
    #: column, #2077); ``None`` for a plain or ``OBJECT_AGL`` row
    datum: "float | None" = None
    #: #2077 rule B: the tile build FILLS the ground up to the outer-rim
    #: edges that stand over it (``cut["fill"]``, ``airport/terrain_fill``)
    fill: bool = False
    #: #2077 2.5: a relief skin's ZERO FOOTPRINT -- rings of frame
    #: ``(east, north)`` metres where the ground is conformed to the frame
    #: zero (``relief_skin``); ``()`` for none
    plane: tuple = ()
    #: #2077 rule A: a RELIEF SKIN (``airport/relief_skin``): a cliff or
    #: slope modelled with the town on it, seated at its origin's ground
    skin: bool = False
    #: #2272: a SMALL TERRAIN SHELL (``airport/terrain_shell``), seated at
    #: its author's ``OBJECT_MSL`` datum
    small: bool = False


def _vt_rows(path: str) -> np.ndarray:
    """``(n, 8)`` ``VT`` rows (x y z nx ny nz s t) of an OBJ8, or empty."""
    rows = []
    with open(path, "r", encoding="latin-1") as fh:
        for line in fh:
            if line.startswith("VT"):
                parts = line.split()
                if len(parts) >= 9:
                    rows.append(parts[1:9])
    try:
        return np.asarray(rows, dtype=float).reshape(-1, 8)
    except ValueError:
        return np.zeros((0, 8))


def photo_spread(vertices: np.ndarray, vt: np.ndarray, tris: np.ndarray) -> float:
    """The plan-weighted 10th-90th percentile spread of log10(texture
    area / plan area) over the upward-facing triangles ``tris`` (indices
    into ``vertices`` and the ``VT`` rows ``vt``); ``inf`` with fewer than
    16 of them or when the tables disagree."""
    if len(vt) != len(vertices) or not len(tris):
        return math.inf
    p = vertices[tris]
    uv = vt[tris][:, :, 6:8]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    plan = 0.5 * np.abs(n[:, 1])
    # either winding: OBJ8 authors wind both ways
    up = np.abs(n[:, 1]) / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    f1, f2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    tex = 0.5 * np.abs(f1[:, 0] * f2[:, 1] - f1[:, 1] * f2[:, 0])
    k = (up >= _UP_NY) & (plan >= _MIN_TRI_M2) & (tex > 0.0)
    if int(k.sum()) < 16:
        return math.inf
    r = np.log10(tex[k] / plan[k])
    o = np.argsort(r)
    cw = np.cumsum(plan[k][o]) / float(plan[k].sum())
    q10, q90 = (r[o][min(int(np.searchsorted(cw, f)), len(o) - 1)] for f in (0.1, 0.9))
    return float(q90 - q10)


def post_m(vertices: np.ndarray, tris: np.ndarray) -> float:
    """THE SHELL'S OWN POST (module doc): the median plan edge of the
    upward-facing triangles ``tris`` of ``vertices``, at least
    ``_MIN_POST_M``."""
    if not len(tris):
        return _MIN_POST_M
    p = vertices[tris]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    up = np.abs(n[:, 1]) >= _UP_NY * np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    if not up.any():
        return _MIN_POST_M
    q = p[up][:, :, [0, 2]]
    e = np.linalg.norm(q - np.roll(q, 1, axis=1), axis=2).ravel()
    return max(_MIN_POST_M, float(np.median(e)))


def _solid(g: _t.Any) -> "np.ndarray | None":
    """``(n, 3, 3)`` authored corners of a geometry's static solid."""
    tris = g.solid
    if g.animated.shape[0]:
        tris = tris[~g.animated]
    if not tris.shape[0]:
        return None
    return g.vertices[tris]


def _grid(g: _t.Any) -> "DeckGrid | None":
    from .terrain_shaped import grid_of_triangles
    p = _solid(g)
    return None if p is None else grid_of_triangles(p)


def _plan_m(g: _t.Any, min_relief_m: float = MIN_RELIEF_M) -> float:
    """The longer plan side of a geometry's static solid when its height
    span reaches ``min_relief_m``, else 0 (the cheap gates, on a geometry
    the caller already parsed)."""
    from .msl_feet import static_vertices
    v = static_vertices(g) if g is not None else None
    if v is None or float(np.ptp(v[:, 1])) < min_relief_m:
        return 0.0
    return float(max(np.ptp(v[:, 0]), np.ptp(v[:, 2])))


def _may_be_candidate(g: _t.Any) -> bool:
    """The cheap plan and height gates of either class (a terrain model or
    a small terrain shell, ``terrain_shell``) on a parsed geometry."""
    from .terrain_shell import SHELL_MIN_PLAN_M, SHELL_MIN_RELIEF_M
    return (_plan_m(g) >= MIN_PLAN_M
            or _plan_m(g, SHELL_MIN_RELIEF_M) >= SHELL_MIN_PLAN_M)


def _shape(path: str) -> "Shape | None":
    from .obj8 import parse_obj8
    g = parse_obj8(path)
    plan = _plan_m(g)
    if plan >= MIN_PLAN_M:
        return _gated(path, g, plan, MAX_PHOTO_SPREAD, MIN_RELIEF_M)
    from .terrain_shell import small_shape
    return small_shape(path, g)


def _gated(path: str, g: _t.Any, plan: float, max_spread: float, min_relief: float,
           small: bool = False) -> "Shape | None":
    """The photo and top-relief gates of a geometry past its plan gate."""
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    spread = photo_spread(g.vertices, _vt_rows(path), tris)
    if spread > max_spread:
        return None
    grid = _grid(g)
    if grid is None or not grid.covered.any():
        return None
    lo, hi = np.percentile(grid.top[grid.covered], [5.0, 95.0])
    if hi - lo < min_relief:
        return None
    return Shape(grid, plan, float(hi - lo), spread, post_m(g.vertices, tris), small)


def plan_grid(path: str) -> "DeckGrid | None":
    """The plan grid of an OBJ8 file's static solid -- the grid a seat
    record's ``cut`` is made from (``auto_patch/terrain_cut_stage``), for a
    terrain model and for a ground object on its bridges
    (``bridged_ground``) alike; ``None`` when unreadable.  Read fresh: the
    tile build asks it once per record and step."""
    from .obj8 import parse_obj8
    try:
        return _grid(parse_obj8(path))
    except (OSError, ValueError):
        return None


def plan_solid(path: str) -> "np.ndarray | None":
    """The ``(n, 3, 3)`` authored static solid triangles of an OBJ8 file
    (what :func:`plan_grid` bins) -- THE HOLD's bound is binned finer from
    them (``terrain_cut.hold_bound``); ``None`` when unreadable."""
    from .obj8 import parse_obj8
    try:
        return _solid(parse_obj8(path))
    except (OSError, ValueError):
        return None


@functools.lru_cache(maxsize=256)
def _file_shape(path: str, mtime_ns: int, size: int) -> "Shape | None":
    try:
        return _shape(path)
    except (OSError, ValueError):
        return None


def shape_of(path: str, geometry: _t.Any = None) -> "Shape | None":
    """THE CANDIDATE TEST on an OBJ8 file (module doc), or ``None``.
    ``geometry``: its parsed ``ObjGeometry`` when the caller holds it --
    the plan and height gates then read it and most files stop there
    without a second parse."""
    if geometry is not None and not _may_be_candidate(geometry):
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return _file_shape(path, st.st_mtime_ns, st.st_size)


def outer_rim(covered: np.ndarray) -> np.ndarray:
    """The covered cells touching the uncovered EXTERIOR (8-neighbours;
    a hole inside the plan is not exterior)."""
    from scipy import ndimage
    pad = np.pad(covered, 1, constant_values=False)
    lab, _n = ndimage.label(~pad)
    near = ndimage.binary_dilation(lab == lab[0, 0], structure=np.ones((3, 3), dtype=bool))
    return covered & near[1:-1, 1:-1]


def _world(grid: DeckGrid, ii: np.ndarray, jj: np.ndarray, xy: tuple[float, float],
           heading: float) -> tuple[np.ndarray, np.ndarray]:
    """Frame metres of plan cells (``terrain_shaped.fit``'s rotation)."""
    h = math.radians(heading)
    s, c = math.sin(h), math.cos(h)
    x, z = grid.x0 + CELL_M * ii, grid.z0 + CELL_M * jj
    return xy[0] + x * c - z * s, xy[1] - (x * s + z * c)


def match(shape: Shape, xy: tuple[float, float], heading: float,
          dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
          fine: "_t.Callable | None" = None, water: "_t.Callable | None" = None,
          datum: "float | None" = None) -> "dict[str, float] | None":
    """THE MATCH and THE SEAT of one placement of ``shape`` (module doc):
    ``{"z0", "corr", "peak_err", "fit_m", "quality_cover", "hideable"}``
    when the top follows the DEM, else ``None``.  ``fine(xs, ys[,
    pixel_m])`` is True where quality elevation of that pixel or finer
    covers a point (``None``: nowhere); ``water(xs, ys)`` is
    ``ProductionDem.water_many`` (``None``: no water).  ``datum``: the
    row's ``OBJECT_MSL`` elevation -- a small shell (``Shape.small``) is
    matched and seated at it by ``terrain_shell.small_match``."""
    if shape.small:
        from .terrain_shell import small_match
        return small_match(shape, xy, heading, dem_many, datum, fine, water)
    grid = shape.grid
    ii, jj = np.nonzero(grid.covered)
    xs, ys = _world(grid, ii, jj, xy, heading)
    dem = np.asarray(dem_many(xs, ys), dtype=float)
    ok = np.isfinite(dem)
    if ok.mean() < 0.9:
        return None
    top, d = grid.top[ii, jj][ok], dem[ok]
    if float(np.std(top)) <= 0.0 or float(np.std(d)) <= 0.0:
        return None
    corr = float(np.corrcoef(top, d)[0, 1])
    fit = float(np.median(d - top))
    peak_err = abs(float(top.max()) + fit - float(d.max())) / shape.relief_m
    if corr < MIN_CORR or peak_err > MAX_PEAK_ERR:
        return None
    z0 = _fit_seat(grid, xy, heading, dem_many, water)
    if z0 is None:
        return None
    cover, hideable = quality(shape, xy, heading, dem_many, fine)
    return {"z0": z0, "corr": corr, "peak_err": float(peak_err),
            "fit_m": fit, "quality_cover": cover, "hideable": hideable}


def _fit_seat(grid: DeckGrid, xy: tuple[float, float], heading: float,
             dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
             water: "_t.Callable | None" = None) -> "float | None":
    """THE SEAT (module doc, #2077 2.1): the rigid L1 fit of the plan to
    the ground, capped by the wet outer rim's ``min(ground - bottom)``
    where :data:`WATER_RIM_SHARE` or more of the rim lies over water;
    ``None`` with no DEM under the plan."""
    from .terrain_shaped import fit
    got = fit(grid, xy, heading, dem_many)
    if got is None:
        return None
    return wet_cap(grid, xy, heading, dem_many, water, float(got[0]))


def wet_cap(grid: DeckGrid, xy: tuple[float, float], heading: float,
            dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
            water: "_t.Callable | None", z0: float) -> float:
    """``z0`` capped by the wet outer rim's ``min(ground - bottom)`` where
    :data:`WATER_RIM_SHARE` or more of the rim lies over water (module
    doc, THE SEAT): the skirt stays under the water."""
    if water is None:
        return z0
    ri, rj = np.nonzero(outer_rim(grid.covered))
    rx, ry = _world(grid, ri, rj, xy, heading)
    wet = np.asarray(water(rx, ry)[0], dtype=bool)
    if not len(wet) or float(wet.mean()) < WATER_RIM_SHARE:
        return z0
    gap = np.asarray(dem_many(rx[wet], ry[wet]), dtype=float) - grid.bot[ri[wet], rj[wet]]
    gap = gap[np.isfinite(gap)]
    return min(z0, float(gap.min())) if len(gap) else z0


def _fine_at(fine: _t.Callable, xs: np.ndarray, ys: np.ndarray, pixel_m: float
             ) -> np.ndarray:
    """``fine`` asked at ``pixel_m`` (a two-argument ``fine`` answers at
    :data:`QUALITY_PIXEL_M`)."""
    try:
        got = fine(xs, ys, pixel_m)
    except TypeError:
        got = fine(xs, ys)
    return np.asarray(got, dtype=bool)


def quality(shape: Shape, xy: tuple[float, float], heading: float,
            dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
            fine: "_t.Callable | None") -> tuple[float, bool]:
    """``(cover, hideable)``: THE HIDE OFFER's quality test (module doc,
    #2077 4.1) against the baked frame ``dem_many`` -- the share of the
    plan under quality elevation no coarser than the shell's own post,
    and whether that ground models the shell."""
    if fine is None:
        return 0.0, False
    grid = shape.grid
    ii, jj = np.nonzero(grid.covered)
    xs, ys = _world(grid, ii, jj, xy, heading)
    pixel = min(QUALITY_PIXEL_M, max(float(shape.post_m), _MIN_POST_M))
    cover = float(np.mean(_fine_at(fine, xs, ys, pixel))) if len(xs) else 0.0
    if cover < MIN_QUALITY_COVER:
        return cover, False
    from .terrain_shaped import fit
    got = fit(grid, xy, heading, dem_many)
    d = np.asarray(dem_many(xs, ys), dtype=float)
    ok = np.isfinite(d)
    if got is None or ok.sum() < 3:
        return cover, False
    top = grid.top[ii, jj][ok]
    if float(np.std(top)) <= 0.0 or float(np.std(d[ok])) <= 0.0:
        return cover, False
    corr = float(np.corrcoef(top, d[ok])[0, 1])
    p90 = float(np.percentile(np.abs(d[ok] - (got[0] + top)), 90.0))
    return cover, (corr >= MIN_QUALITY_CORR
                   and p90 <= max(QUALITY_P90_M, QUALITY_P90_SHARE * shape.relief_m))


def rim_seat(grid: DeckGrid, xy: tuple[float, float], heading: float,
             dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]
             ) -> "float | None":
    """THE SEAT (module doc): the zero where no visible edge floats --
    ``min`` over the outer rim of ``(ground - bottom)`` -- or ``None``
    with no DEM under the rim."""
    ri, rj = np.nonzero(outer_rim(grid.covered))
    rx, ry = _world(grid, ri, rj, xy, heading)
    gap = np.asarray(dem_many(rx, ry), dtype=float) - grid.bot[ri, rj]
    gap = gap[np.isfinite(gap)]
    return float(gap.min()) if len(gap) else None


def _origin(xy: _t.Any, heading: float, elev: _t.Any, kind: str = "") -> tuple:
    """The origin-set key; an ``OBJECT_MSL`` row's column is an absolute
    height, not a lift, and is left out (its lift is :func:`member_lift`)."""
    from .msl_feet import origin_key
    e = 0.0 if kind == "OBJECT_MSL" else float(elev or 0.0)
    return origin_key(xy, heading) + (round(e, 3),)


def placement_models(placements: _t.Sequence[tuple],
                     path_of: _t.Callable[[str], "str | None"],
                     geometry: _t.Callable[[str], _t.Any],
                     dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                     fine: "_t.Callable | None" = None, water: "_t.Callable | None" = None,
                     hidden: _t.AbstractSet[str] = frozenset()) -> dict[str, TerrainModel]:
    """The terrain models among ``placements`` -- ``(id, def path, xy,
    heading, elevation, kind)`` rows -- by id.  ``path_of(def path)`` is
    the resolved file or ``None``, ``geometry(def path)`` its parsed
    geometry (the reader's cache) or ``None``.  ``water``: the water
    witness (:func:`_fit_seat`).  ``hidden``: the def paths the user hid
    (module doc, HIDING) -- such a model comes back with ``ground =
    "hidden"`` (``ground_shell.HIDDEN``): its row is left out and its
    frame dissolves.

    An ``OBJECT_MSL`` row is read like any other (#2077): its elevation is
    the author's datum on the AUTHOR's terrain, and the 11d conversion
    drops it anyway (``dsf_write.conversions_for_dump``) -- LOWS's
    Festungsberg shell, authored at 430 m, was converted to on-ground at
    its anchor on the hilltop and drawn 73-106 m over the hill.  Its datum
    is kept on the model (:attr:`TerrainModel.datum`) so the rows the
    author stood on it keep their place (:func:`set_members`)."""
    from .obj8 import is_stock_library_resource
    out: dict[str, TerrainModel] = {}
    shapes: dict[str, "Shape | None"] = {}
    for oid, dpath, xy, heading, elev, kind in placements:
        if is_stock_library_resource(dpath):
            continue
        if dpath not in shapes:
            phys = path_of(dpath)
            g = None if phys is None else geometry(dpath)
            shapes[dpath] = None if g is None else shape_of(phys, g)
        shape = shapes[dpath]
        if shape is None:
            continue
        xy2 = (float(xy[0]), float(xy[1]))
        datum = float(elev) if kind == "OBJECT_MSL" and elev is not None else None
        m = match(shape, xy2, float(heading), dem_many, fine, water, datum)
        if m is None:
            continue
        out[str(oid)] = TerrainModel(str(oid), str(dpath), xy2, float(heading), m["z0"],
                                     m["corr"], m["peak_err"], m["fit_m"],
                                     shape.grid.area_m2, shape.relief_m,
                                     m["quality_cover"],
                                     m["hideable"] or str(dpath) in hidden,
                                     str(path_of(dpath) or ""),
                                     datum=datum,
                                     fill=True,
                                     ground="hidden" if str(dpath) in hidden else "",
                                     small=shape.small)
    return out


def _in_plan(m: TerrainModel, xy: _t.Any) -> bool:
    """Does frame point ``xy`` lie over a covered cell of ``m``'s plan?"""
    shape = shape_of(m.file) if m.file else None
    if shape is None:
        return False
    g = shape.grid
    h = math.radians(m.heading)
    s, c = math.sin(h), math.cos(h)
    e, n = float(xy[0]) - m.xy[0], float(xy[1]) - m.xy[1]
    # the inverse of :func:`_world`
    x, z = e * c - n * s, -(e * s + n * c)
    i, j = int(round((x - g.x0) / CELL_M)), int(round((z - g.z0) / CELL_M))
    return 0 <= i < g.covered.shape[0] and 0 <= j < g.covered.shape[1] and bool(g.covered[i, j])


def member_lift(m: TerrainModel, kind: str, elev: _t.Any) -> "float | None":
    """An ``OBJECT_MSL`` member's lift over its model's frame zero -- its
    elevation less the model's authored :attr:`~TerrainModel.datum` --
    or ``None`` (the row's own ``OBJECT_AGL`` lift is its lift)."""
    if kind != "OBJECT_MSL" or m.datum is None or elev is None:
        return None
    return float(elev) - float(m.datum)


def set_members(placements: _t.Sequence[tuple],
                models: _t.Mapping[str, TerrainModel]) -> dict[str, TerrainModel]:
    """Every placement id sharing an origin (xy, heading, elevation) with
    a terrain model, mapped to that model (the lowest seat where two
    models share one frame) -- and, for a model the author wrote
    ``OBJECT_MSL``, every other ``OBJECT_MSL`` row whose anchor stands
    over its plan (#2077): both state heights in the author's ONE
    absolute frame, so the castle the author set at 510 m on a hill shell
    set at 430 m is that shell's content and keeps its 80 m
    (:func:`member_lift`); converted on its own it stood on our hilltop
    24.7 m over the place its walls were built for."""
    by_id = {str(p[0]): p for p in placements}
    seeds: dict[tuple, TerrainModel] = {}
    for oid, m in models.items():
        p = by_id.get(oid)
        if p is None:
            continue
        k = _origin(p[2], p[3], p[4], p[5])
        if k not in seeds or m.z0 < seeds[k].z0:
            seeds[k] = m
    if not seeds:
        return {}
    out = {str(oid): seeds[k] for oid, _d, xy, h, e, kd in placements
           if (k := _origin(xy, h, e, kd)) in seeds}
    from .obj8 import is_stock_library_resource
    msl = sorted((m for m in seeds.values() if m.datum is not None), key=lambda m: m.z0)
    for oid, dpath, xy, _h, e, kind in placements if msl else ():
        if (str(oid) in out or kind != "OBJECT_MSL" or e is None
                or is_stock_library_resource(dpath)):
            continue
        for m in msl:
            if _in_plan(m, xy):
                out[str(oid)] = m
                break
    return out


def seat_records(airport: _t.Any) -> list[dict[str, _t.Any]]:
    """One ``RebakePlan.authored_seats`` record per row of a terrain
    model's origin set (``Airport.terrain_models``: ``(id, def path,
    TerrainModel, authored lift)``): seat :data:`SEAT`, ``elevation`` the
    frame zero plus the row's own lift -- the ``OBJECT_MSL`` row
    ``terrain_shaped.row_seats`` writes.  ``hideable`` (the model's own
    row, under quality elevation) travels to the pack adjustment.  The
    model's OWN row carries ``cut`` -- its file, anchor and heading, from
    which the tile build cuts the ground under it (owner RULINGS
    2026-11-13k, ``airport/terrain_cut``) unless the user hides it."""
    out = []
    to_ll = None
    for oid, dpath, m, lift in sorted(getattr(airport, "terrain_models", ()) or (),
                                      key=lambda r: r[0]):
        if getattr(m, "ground", "") == "hidden":
            # issue #2056: a ground shell no seat lays flat on our ground is
            # left out of the written DSF -- no seat, no cut
            from .terrain_shaped import HIDDEN_SEAT
            rec = {"id": oid, "resource": dpath, "datum": "terrain",
                   "seat": HIDDEN_SEAT, "elevation": round(m.z0, 3)}
            if m.hideable and dpath == m.path:
                # #2077 4.2: the user hid it -- the offer stands, for Undo
                rec["hideable"] = True
            out.append(rec)
            continue
        rec = {"id": oid, "resource": dpath, "datum": "terrain", "seat": SEAT,
               "elevation": round(m.z0 + float(lift or 0.0), 3),
               "hideable": bool(m.hideable and dpath == m.path),
               "corr": round(m.corr, 3), "quality_cover": round(m.quality_cover, 3)}
        if getattr(m, "seat_by", ""):
            rec["by"] = m.seat_by
        if oid == m.id and getattr(m, "file", ""):
            if to_ll is None:
                to_ll = airport.frame.transformers()[1]
            lat, lon = to_ll(*m.xy)
            rec["cut"] = {"file": m.file, "lat": round(float(lat), 9),
                          "lon": round(float(lon), 9), "heading": round(m.heading, 6)}
            if getattr(m, "erode_m", None) is not None:
                rec["cut"]["erode_m"] = float(m.erode_m)
            if getattr(m, "cut_floor_m", 0.0) > 0.0:
                rec["cut"]["floor_m"] = float(m.cut_floor_m)
            if getattr(m, "fill", False):
                rec["cut"]["fill"] = True
            if getattr(m, "small", False):
                # #2272: seated at its author's height -- its body cut and
                # held, its edge band not cut, the ground feathered to it
                # (``terrain_cut`` THE SHELL)
                rec["cut"]["shell"] = True
            if getattr(m, "plane", ()):
                from ..geom.terrain_deck import UNDER_M
                # ``to_ll`` is the frame's: one point, ``(lat, lon)``
                rec["cut"]["plane"] = {
                    "z": round(m.z0 - UNDER_M, 3),
                    "rings": [[[round(float(q[1]), 9), round(float(q[0]), 9)]
                               for q in (to_ll(x, y) for x, y in r)] for r in m.plane]}
        out.append(rec)
    return out


def hideable_paths(records: _t.Iterable[_t.Any]) -> tuple[str, ...]:
    """The resources a build's seat records offer for hiding (sorted)."""
    from .terrain_shaped import HIDDEN_SEAT
    return tuple(sorted({str(r.get("resource")) for r in records or ()
                         if hasattr(r, "get") and r.get("seat") in (SEAT, HIDDEN_SEAT)
                         and r.get("hideable")}))


def model_paths(records: _t.Iterable[_t.Any]) -> tuple[str, ...]:
    """Every terrain object a build's seat records name (#2272: the
    Adjust… row's per-object list): each model's own row (the one with a
    ``cut``, not a ground object seated on its bridges) and every
    resource offered for hiding (sorted)."""
    own = {str(r.get("resource")) for r in records or ()
           if hasattr(r, "get") and r.get("seat") == SEAT and "cut" in r and not r.get("by")}
    return tuple(sorted(own | set(hideable_paths(records))))


def log_line(icao: str, models: _t.Iterable[TerrainModel]) -> str:
    """The build log's one line on the terrain models (a ground object
    seated on its bridges has its own line, ``bridged_ground.log_line``;
    a ground shell has its own, ``ground_shell.log_line``)."""
    models = sorted({m.id: m for m in models
                     if not getattr(m, "seat_by", "") and not getattr(m, "skin", False)
                     and (not getattr(m, "ground", "") or getattr(m, "fill", False))}.values(),
                    key=lambda m: m.id)
    if not models:
        return f"[{icao}] terrain-modelling objects: none"
    return f"[{icao}] terrain-modelling objects: " + "; ".join(
        f"{m.path} ({m.id}) " + ("HIDDEN (the user's answer; its frame read as objects), "
                                 if m.ground else "")
        + f"seated at {m.z0:.2f} m ("
        + ("its author's datum, a small shell" if getattr(m, "small", False) else "its L1 fit")
        + ", the rim filled), top follows "
        f"the DEM r={m.corr:.2f}, peak off {m.peak_err:.0%} of {m.relief_m:.0f} m, "
        f"{m.area_m2:,.0f} m2" + (f", hideable ({m.quality_cover:.0%} under quality "
                                  f"elevation)" if m.hideable else "")
        for m in models)
