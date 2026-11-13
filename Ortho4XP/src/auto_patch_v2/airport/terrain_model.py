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

A SMALLER PIECE (issue #2064: a pack that models a coast as several
cliffs, rocks and hilltops, each 150-450 m across and 20-90 m high) is a
candidate on stronger photo evidence instead of size: plan at least
:data:`SMALL_PLAN_M` and under :data:`MIN_PLAN_M`, top relief at least
:data:`SMALL_RELIEF_M`, and the photo spread at most
:data:`SMALL_PHOTO_SPREAD` (one orthophoto at one resolution, to about
12 %) -- and ONLY on an ``OBJECT_MSL`` row (:func:`admits`): a piece
modelled at an absolute height is the author modelling the ground, which
the on-ground conversion (RULINGS 2026-09-11d) throws onto its origin
(TFFJ: 23-114 m in the air); a small terrain-relative row was authored to
drape at its origin, and the frames-corpus census found the only small
plain rows that pass every gate to be ground skins of buildings (KBNA,
KASE condos, KCRW's runway-end fill), never a hill.  An object of
:data:`MIN_PLAN_M` or more with less relief is a ground shell's to read
(``ground_shell``), never this module's.  The match below is the same
for both.

AN ``OBJECT_MSL`` ROW is read like any other (#2064: LOWS's town rock,
LXGB's Rock of Gibraltar, TFFJ's coast are all placed at an MSL height
the author chose against X-Plane's own mesh, not ours).  Its datum is
kept on the model (``TerrainModel.datum``) so every row of its frame
keeps its authored height relative to it.

THE MATCH (the DEM under the placement, :func:`match`): the top surface
sampled over its covered cells follows the ground --

* SHAPE -- Pearson correlation of top and DEM at least :data:`MIN_CORR`;
* PEAK -- the top shifted by its median offset from the DEM peaks within
  :data:`MAX_PEAK_ERR` of its relief of the DEM's peak ("similar height").

THE SEAT -- no visible edge floats: the object's ``y = 0`` plane is set at

    z0 = min over its OUTER RIM cells of (ground - bottom)

the outer rim being every covered cell touching the uncovered exterior (a
hole inside the plan is not an edge one sees from outside) and ``bottom``
the lowest solid there: every lower edge then meets or lies under the
ground, and no lower seat is taken than that.  The seat is one rigid
frame: every row sharing the model's origin (the buildings a shell
carries, the cable-car stations on Sugarloaf) is written as an
``OBJECT_MSL`` row at ``z0`` plus its own authored lift, so each keeps its
place on the shell.  A terrain model's origin set is never split, never
re-anchored, never read as a pit, a pad or a deck (``obj8``'s
``terrain_feature`` path, RULINGS 2026-10-20aq).

RIDERS (#2064, LOWS's fortress on its rock): an ``OBJECT_MSL`` row of
ANOTHER origin over an ``OBJECT_MSL`` terrain model's plan -- at least
:data:`RIDER_ON_PLAN` of its covered cells inside the model's, and some of
it standing out of the model's top at the two authored heights -- was
authored against that model at an absolute height: it moves with the model
(:func:`riders`), written at its authored height plus the model's move.
Only that pair is certain (owner RULINGS 2026-11-13r: any doubt, and an
object stays where its author placed it); a terrain-relative row over the
plan is left to the object stage.

HIDING (the pack adjustment "Hide terrain objects", off by default) is
offered only where QUALITY ELEVATION models the same ground: at least
:data:`MIN_QUALITY_COVER` of the model's cells lie inside an inset whose
source pixel is :data:`QUALITY_PIXEL_M` or finer, and the match there is
close (correlation at least :data:`MIN_QUALITY_CORR`).
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
           "QUALITY_PIXEL_M", "MIN_QUALITY_COVER", "MIN_QUALITY_CORR", "SEAT",
           "SMALL_PLAN_M", "SMALL_RELIEF_M", "SMALL_PHOTO_SPREAD", "RIDER_ON_PLAN",
           "Shape", "TerrainModel", "candidate", "admits", "shape_of", "photo_spread", "match",
           "outer_rim",
           "placement_models", "set_members", "riders", "frame_rows", "seat_records",
           "log_line", "hideable_paths", "plan_grid", "rim_seat"]

MIN_PLAN_M = 500.0
MIN_RELIEF_M = 50.0
MAX_PHOTO_SPREAD = 0.35
MIN_CORR = 0.6
MAX_PEAK_ERR = 0.25
QUALITY_PIXEL_M = 10.0
MIN_QUALITY_COVER = 0.9
MIN_QUALITY_CORR = 0.9
#: a smaller piece (module doc): plan, top relief and photo spread
SMALL_PLAN_M = 150.0
SMALL_RELIEF_M = 20.0
SMALL_PHOTO_SPREAD = 0.05
#: the least share of a rider's covered cells over its model's plan
RIDER_ON_PLAN = 0.9
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
    #: how far the other seat points sink under their ground at ``z0`` (m)
    spread_m: float = 0.0
    #: a GROUND SHELL's verdict (``ground_shell``, issue #2056): ``"seated"``
    #: (it lies on the ground at ``z0``) or ``"hidden"`` (its row is left
    #: out of the written DSF); ``""`` for a terrain model of this module
    ground: str = ""
    #: the model row's authored elevation (#2064): its MSL height for an
    #: ``OBJECT_MSL`` row, its AGL lift for an ``OBJECT_AGL`` one, else 0.
    #: A row of its frame is written at ``z0`` plus its own elevation less
    #: this (:func:`frame_rows`)
    datum: float = 0.0
    #: the model row is ``OBJECT_MSL`` (its riders are, :func:`riders`)
    msl: bool = False
    #: on a ROW's copy (:func:`set_members`, :func:`riders`): that row's
    #: elevation less ``datum`` -- written at ``z0`` plus this; ``None`` on
    #: a model no membership read (its row's own AGL lift is used)
    lift: "float | None" = None


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


def _grid(g: _t.Any) -> "DeckGrid | None":
    from .terrain_shaped import grid_of_triangles
    tris = g.solid
    if g.animated.shape[0]:
        tris = tris[~g.animated]
    if not tris.shape[0]:
        return None
    return grid_of_triangles(g.vertices[tris])


def _plan_m(g: _t.Any) -> float:
    """The longer plan side of a geometry's static solid when its height
    span reaches its size class's relief (:data:`MIN_RELIEF_M` from
    :data:`MIN_PLAN_M` up, :data:`SMALL_RELIEF_M` below), else 0 (the cheap
    gates, on a geometry the caller already parsed)."""
    from .msl_feet import static_vertices
    v = static_vertices(g) if g is not None else None
    if v is None or not len(v):
        return 0.0
    plan = float(max(np.ptp(v[:, 0]), np.ptp(v[:, 2])))
    need = MIN_RELIEF_M if plan >= MIN_PLAN_M else SMALL_RELIEF_M
    return plan if float(np.ptp(v[:, 1])) >= need else 0.0


def candidate(plan_m: float, relief_m: float, spread: float) -> bool:
    """THE CANDIDATE's size and photo gates (module doc): a hill, or a
    smaller piece under one orthophoto."""
    if spread > MAX_PHOTO_SPREAD or plan_m < SMALL_PLAN_M:
        return False
    if plan_m >= MIN_PLAN_M:
        return relief_m >= MIN_RELIEF_M
    return relief_m >= SMALL_RELIEF_M and spread <= SMALL_PHOTO_SPREAD


def admits(shape: Shape, kind: str) -> bool:
    """A candidate ``shape`` placed by a row of ``kind`` may be read: a
    smaller piece only on an ``OBJECT_MSL`` row (module doc)."""
    return shape.plan_m >= MIN_PLAN_M or kind == "OBJECT_MSL"


def _shape(path: str) -> "Shape | None":
    from .obj8 import parse_obj8
    g = parse_obj8(path)
    plan = _plan_m(g)
    if plan < SMALL_PLAN_M:
        return None
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    spread = photo_spread(g.vertices, _vt_rows(path), tris)
    if not candidate(plan, math.inf, spread):
        return None
    grid = _grid(g)
    if grid is None or not grid.covered.any():
        return None
    lo, hi = np.percentile(grid.top[grid.covered], [5.0, 95.0])
    if not candidate(plan, float(hi - lo), spread):
        return None
    return Shape(grid, plan, float(hi - lo), spread)


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
    if geometry is not None and _plan_m(geometry) < SMALL_PLAN_M:
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
          fine: "_t.Callable[[np.ndarray, np.ndarray], np.ndarray] | None" = None,
          ) -> "dict[str, float] | None":
    """THE MATCH and THE SEAT of one placement of ``shape`` (module doc):
    ``{"z0", "corr", "peak_err", "fit_m", "quality_cover"}`` when the top
    follows the DEM, else ``None``.  ``fine(xs, ys)`` is True where
    quality elevation covers a point (``None``: nowhere)."""
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
    z0 = rim_seat(grid, xy, heading, dem_many)
    if z0 is None:
        return None
    cover = 0.0 if fine is None else float(np.mean(np.asarray(fine(xs, ys), dtype=bool)))
    return {"z0": z0, "corr": corr, "peak_err": float(peak_err),
            "fit_m": fit, "quality_cover": cover}


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
    """One author's frame: origin, heading, elevation -- and whether that
    elevation is MSL (an ``OBJECT_MSL`` row at 0 m is not a plain row)."""
    from .msl_feet import origin_key
    return origin_key(xy, heading) + (round(float(elev or 0.0), 3), kind == "OBJECT_MSL")


def placement_models(placements: _t.Sequence[tuple],
                     path_of: _t.Callable[[str], "str | None"],
                     geometry: _t.Callable[[str], _t.Any],
                     dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                     fine: "_t.Callable | None" = None) -> dict[str, TerrainModel]:
    """The terrain models among ``placements`` -- ``(id, def path, xy,
    heading, elevation, kind)`` rows -- by id.  ``path_of(def path)`` is
    the resolved file or ``None``, ``geometry(def path)`` its parsed
    geometry (the reader's cache) or ``None``.  Any row kind (#2064): an
    ``OBJECT_MSL`` row's height is kept as the model's ``datum``."""
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
        if shape is None or not admits(shape, kind):
            continue
        xy2 = (float(xy[0]), float(xy[1]))
        m = match(shape, xy2, float(heading), dem_many, fine)
        if m is None:
            continue
        hideable = (m["quality_cover"] >= MIN_QUALITY_COVER
                    and m["corr"] >= MIN_QUALITY_CORR)
        out[str(oid)] = TerrainModel(str(oid), str(dpath), xy2, float(heading), m["z0"],
                                     m["corr"], m["peak_err"], m["fit_m"],
                                     shape.grid.area_m2, shape.relief_m,
                                     m["quality_cover"], hideable, str(path_of(dpath) or ""),
                                     datum=float(elev or 0.0), msl=kind == "OBJECT_MSL")
    return out


def set_members(placements: _t.Sequence[tuple],
                models: _t.Mapping[str, TerrainModel]) -> dict[str, TerrainModel]:
    """Every placement id sharing an origin (xy, heading, elevation) with
    a terrain model, mapped to that model (the lowest seat where two
    models share one frame) -- a copy carrying the row's ``lift``."""
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
    return {str(oid): _dc.replace(seeds[k], lift=float(e or 0.0) - seeds[k].datum)
            for oid, _d, xy, h, e, kind in placements
            if (k := _origin(xy, h, e, kind)) in seeds}


def _cells_xy(grid: DeckGrid, xy: tuple[float, float], heading: float
              ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """``(i, j, east, north)`` of a plan grid's covered cells."""
    ii, jj = np.nonzero(grid.covered)
    xs, ys = _world(grid, ii, jj, xy, heading)
    return ii, jj, xs, ys


def _top_at(grid: DeckGrid, xy: tuple[float, float], heading: float,
            xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """A model's authored top (its own frame metres) under frame points,
    NaN off its covered plan (the inverse of :func:`_world`)."""
    h = math.radians(heading)
    s, c = math.sin(h), math.cos(h)
    de, dn = np.asarray(xs, dtype=float) - xy[0], np.asarray(ys, dtype=float) - xy[1]
    x, z = de * c - dn * s, -de * s - dn * c
    i = np.rint((x - grid.x0) / CELL_M).astype(int)
    j = np.rint((z - grid.z0) / CELL_M).astype(int)
    ok = (i >= 0) & (j >= 0) & (i < grid.covered.shape[0]) & (j < grid.covered.shape[1])
    out = np.full(len(x), np.nan)
    ok[ok] = grid.covered[i[ok], j[ok]]
    out[ok] = grid.top[i[ok], j[ok]]
    return out


def riders(placements: _t.Sequence[tuple], models: _t.Mapping[str, TerrainModel],
           geometry: _t.Callable[[str], _t.Any]) -> dict[str, TerrainModel]:
    """RIDERS (module doc): every ``OBJECT_MSL`` row outside a model's
    origin set whose covered plan lies at least :data:`RIDER_ON_PLAN` over
    an ``OBJECT_MSL`` model's plan and stands out of its top somewhere at
    the two authored heights, mapped to that model (the lowest seat where
    two qualify), a copy carrying the row's ``lift`` (its authored height
    over the model's).  ``geometry(def path)``: the parsed geometry or
    ``None``; ``placements`` rows carry an ``OBJECT_MSL`` row's height."""
    own = [m for m in {m.id: m for m in models.values()}.values()
           if m.msl and not m.ground and not m.seat_by and m.file]
    if not own:
        return {}
    grids = {m.id: plan_grid(m.file) for m in own}
    taken = set(set_members(placements, models))
    out: dict[str, TerrainModel] = {}
    for oid, dpath, xy, heading, elev, kind in placements:
        if kind != "OBJECT_MSL" or str(oid) in taken or elev is None:
            continue
        g = geometry(dpath)
        grid = None if g is None else _grid(g)
        if grid is None or not grid.covered.any():
            continue
        ii, jj, xs, ys = _cells_xy(grid, (float(xy[0]), float(xy[1])), float(heading))
        for m in own:
            mg = grids.get(m.id)
            if mg is None:
                continue
            under = _top_at(mg, m.xy, m.heading, xs, ys)
            on = np.isfinite(under)
            if on.mean() < RIDER_ON_PLAN:
                continue
            proud = float(elev) + grid.top[ii, jj][on] - (m.datum + under[on])
            if float(proud.max()) > 0.0 and (str(oid) not in out
                                            or m.z0 < out[str(oid)].z0):
                out[str(oid)] = _dc.replace(m, lift=float(elev) - m.datum)
    return out


def frame_rows(objects: _t.Iterable[_t.Any]) -> tuple:
    """``Airport.terrain_models``: ``(id, def path, TerrainModel, lift)``
    of every loaded placement carrying a model's frame, ``lift`` the row's
    own (``TerrainModel.lift``: its elevation less the model's ``datum`` --
    a member of the origin set 0, a rider its authored height over the
    model's), else its AGL lift."""
    out = []
    for o in objects:
        m = getattr(o, "terrain_model", None)
        if m is None:
            continue
        lift = getattr(m, "lift", None)
        out.append((o.id, o.path, m, float(o.agl_m or 0.0) if lift is None else float(lift)))
    return tuple(out)


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
            out.append({"id": oid, "resource": dpath, "datum": "terrain",
                        "seat": HIDDEN_SEAT, "elevation": round(m.z0, 3)})
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
        out.append(rec)
    return out


def hideable_paths(records: _t.Iterable[_t.Any]) -> tuple[str, ...]:
    """The resources a build's seat records offer for hiding (sorted)."""
    return tuple(sorted({str(r.get("resource")) for r in records or ()
                         if hasattr(r, "get") and r.get("seat") == SEAT
                         and r.get("hideable")}))


def log_line(icao: str, models: _t.Iterable[TerrainModel]) -> str:
    """The build log's one line on the terrain models (a ground object
    seated on its bridges has its own line, ``bridged_ground.log_line``;
    a ground shell has its own, ``ground_shell.log_line``)."""
    models = sorted({m.id: m for m in models
                     if not getattr(m, "seat_by", "") and not getattr(m, "ground", "")}.values(),
                    key=lambda m: m.id)
    if not models:
        return f"[{icao}] terrain-modelling objects: none"
    return f"[{icao}] terrain-modelling objects: " + "; ".join(
        f"{m.path} ({m.id}) seated at {m.z0:.2f} m (no edge floats"
        + (f"; authored MSL {m.datum:.2f} m" if m.msl else "") + "), top follows "
        f"the DEM r={m.corr:.2f}, peak off {m.peak_err:.0%} of {m.relief_m:.0f} m, "
        f"{m.area_m2:,.0f} m2" + (f", hideable ({m.quality_cover:.0%} under quality "
                                  f"elevation)" if m.hideable else "")
        for m in models)
