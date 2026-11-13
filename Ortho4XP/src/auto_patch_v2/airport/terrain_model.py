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
           "Shape", "TerrainModel", "shape_of", "photo_spread", "match", "outer_rim",
           "placement_models", "set_members", "seat_records", "log_line",
           "hideable_paths", "plan_grid"]

MIN_PLAN_M = 500.0
MIN_RELIEF_M = 50.0
MAX_PHOTO_SPREAD = 0.35
MIN_CORR = 0.6
MAX_PEAK_ERR = 0.25
QUALITY_PIXEL_M = 10.0
MIN_QUALITY_COVER = 0.9
MIN_QUALITY_CORR = 0.9
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
    span reaches :data:`MIN_RELIEF_M`, else 0 (the cheap gates, on a
    geometry the caller already parsed)."""
    from .msl_feet import static_vertices
    v = static_vertices(g) if g is not None else None
    if v is None or float(np.ptp(v[:, 1])) < MIN_RELIEF_M:
        return 0.0
    return float(max(np.ptp(v[:, 0]), np.ptp(v[:, 2])))


def _shape(path: str) -> "Shape | None":
    from .obj8 import parse_obj8
    g = parse_obj8(path)
    plan = _plan_m(g)
    if plan < MIN_PLAN_M:
        return None
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    spread = photo_spread(g.vertices, _vt_rows(path), tris)
    if spread > MAX_PHOTO_SPREAD:
        return None
    grid = _grid(g)
    if grid is None or not grid.covered.any():
        return None
    lo, hi = np.percentile(grid.top[grid.covered], [5.0, 95.0])
    if hi - lo < MIN_RELIEF_M:
        return None
    return Shape(grid, plan, float(hi - lo), spread)


@functools.lru_cache(maxsize=64)
def _file_grid(path: str, mtime_ns: int, size: int) -> "DeckGrid | None":
    from .obj8 import parse_obj8
    try:
        return _grid(parse_obj8(path))
    except (OSError, ValueError):
        return None


def plan_grid(path: str) -> "DeckGrid | None":
    """The plan grid of an OBJ8 file's static solid -- the grid a seat
    record's ``cut`` is made from (``auto_patch/terrain_cut_stage``), for a
    terrain model and for a ground object on its bridges
    (``bridged_ground``) alike; ``None`` when unreadable."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return _file_grid(path, st.st_mtime_ns, st.st_size)


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
    if geometry is not None and _plan_m(geometry) < MIN_PLAN_M:
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
    ri, rj = np.nonzero(outer_rim(grid.covered))
    rx, ry = _world(grid, ri, rj, xy, heading)
    gap = np.asarray(dem_many(rx, ry), dtype=float) - grid.bot[ri, rj]
    gap = gap[np.isfinite(gap)]
    if not len(gap):
        return None
    cover = 0.0 if fine is None else float(np.mean(np.asarray(fine(xs, ys), dtype=bool)))
    return {"z0": float(gap.min()), "corr": corr, "peak_err": float(peak_err),
            "fit_m": fit, "quality_cover": cover}


def _origin(xy: _t.Any, heading: float, elev: _t.Any) -> tuple:
    from .msl_feet import origin_key
    return origin_key(xy, heading) + (round(float(elev or 0.0), 3),)


def placement_models(placements: _t.Sequence[tuple],
                     path_of: _t.Callable[[str], "str | None"],
                     geometry: _t.Callable[[str], _t.Any],
                     dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                     fine: "_t.Callable | None" = None) -> dict[str, TerrainModel]:
    """The terrain models among ``placements`` -- ``(id, def path, xy,
    heading, elevation, kind)`` rows -- by id.  ``path_of(def path)`` is
    the resolved file or ``None``, ``geometry(def path)`` its parsed
    geometry (the reader's cache) or ``None``.  A plain ``OBJECT`` or ``OBJECT_AGL``
    row only: an ``OBJECT_MSL`` row already states its author's datum."""
    from .obj8 import is_stock_library_resource
    out: dict[str, TerrainModel] = {}
    shapes: dict[str, "Shape | None"] = {}
    for oid, dpath, xy, heading, _elev, kind in placements:
        if kind == "OBJECT_MSL" or is_stock_library_resource(dpath):
            continue
        if dpath not in shapes:
            phys = path_of(dpath)
            g = None if phys is None else geometry(dpath)
            shapes[dpath] = None if g is None else shape_of(phys, g)
        shape = shapes[dpath]
        if shape is None:
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
                                     m["quality_cover"], hideable, str(path_of(dpath) or ""))
    return out


def set_members(placements: _t.Sequence[tuple],
                models: _t.Mapping[str, TerrainModel]) -> dict[str, TerrainModel]:
    """Every placement id sharing an origin (xy, heading, elevation) with
    a terrain model, mapped to that model (the lowest seat where two
    models share one frame)."""
    by_id = {str(p[0]): p for p in placements}
    seeds: dict[tuple, TerrainModel] = {}
    for oid, m in models.items():
        p = by_id.get(oid)
        if p is None:
            continue
        k = _origin(p[2], p[3], p[4])
        if k not in seeds or m.z0 < seeds[k].z0:
            seeds[k] = m
    if not seeds:
        return {}
    return {str(oid): seeds[k] for oid, _d, xy, h, e, _k in placements
            if (k := _origin(xy, h, e)) in seeds}


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
    seated on its bridges has its own line, ``bridged_ground.log_line``)."""
    models = sorted({m.id: m for m in models if not getattr(m, "seat_by", "")}.values(),
                    key=lambda m: m.id)
    if not models:
        return f"[{icao}] terrain-modelling objects: none"
    return f"[{icao}] terrain-modelling objects: " + "; ".join(
        f"{m.path} ({m.id}) seated at {m.z0:.2f} m (no edge floats), top follows "
        f"the DEM r={m.corr:.2f}, peak off {m.peak_err:.0%} of {m.relief_m:.0f} m, "
        f"{m.area_m2:,.0f} m2" + (f", hideable ({m.quality_cover:.0%} under quality "
                                  f"elevation)" if m.hideable else "")
        for m in models)
