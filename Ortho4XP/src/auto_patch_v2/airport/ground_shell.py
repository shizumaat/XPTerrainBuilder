"""A GROUND SHELL LIES FLAT ON OUR GROUND OR IS HIDDEN (issue #2056).

Owner sim read 2026-11-13T15:49Z (SBGL, 1.0.510): "a large terrain shell
object ... floating above the runway.  Either seat it flat on our terrain
or hide it."  The further law is the terrain model's (owner RULINGS
2026-11-13i: one rigid frame, seated where NO VISIBLE EDGE FLOATS) and its
cut (2026-11-13k).

A pack may model the GROUND of an airport as one large object: a
photo-textured skin over the grass between a runway and the water, its
edges dropping as a skirt to the sea floor (SBGL ``Objetos/Terreno/Objeto
Terreno.obj``: 1.1 x 2.5 km, the top within 3 m of a plane, the skirt to
-37.8 m), authored for the default mesh's flattened airport.  It is too
flat for :mod:`terrain_model` (top relief >= 50 m and a top that follows
the DEM's shape -- a level skin has no shape to correlate), and read as a
building it fails: split into bodies, its main body is anchored on its
lowest foot -- the skirt's bottom, in the bay -- and the whole skin stands
over 30 m above the runway strip.

THE CANDIDATE (no DEM; one verdict per file version, :func:`shape_of`):
:mod:`terrain_model`'s PLAN and PHOTO gates (its static solid spans at
least ``MIN_PLAN_M`` on its longer plan side; one texel density over its
upward faces) and, in place of the 50 m relief gate, three witnesses that
it is the GROUND:

* A SKIN WITH A SKIRT -- its lowest surface departs from its least-squares
  plane by at least ``terrain_shaped.MIN_RELIEF_M`` (#1730's terrain-skin
  witness: every plate and deck measured departs by under 2 m);
* AT GRADE -- its top stands nowhere above its own origin's ground (the
  95th percentile of the top over its plan at most ``AT_GRADE_M``): the
  ground the row is placed on, never a roof or a floor over it;
* HARD -- at least ``MIN_HARD`` of its upward plan carries ``ATTR_hard`` /
  ``ATTR_hard_deck``: a surface the aircraft and vehicles roll on.

Calibration (the dry census, ``tools/terrain_model_census.py``, 20 packs):
the plan, photo and skirt gates alone pass 207 objects -- roofs, terminal
floors, facades, city blocks; AT GRADE leaves SBGL's shell (top 95th
percentile -0.6 m, the next 4.8 m: KATL's control tower) and HARD confirms
it (88 % of its upward plan).  A candidate with the top relief of a hill
is :mod:`terrain_model`'s, never this module's.

THE SEAT: the shell's rigid fit to the ground (``terrain_shaped.fit``, the
L1 fit of its surface to the DEM) -- flat on our terrain -- but never above
the terrain model's (:func:`terrain_model.rim_seat`), the highest zero
where no visible edge floats.  THE VERDICT: at that ``z0`` the shell LIES
ON OUR GROUND when more than ``terrain_shaped.MIN_FOLLOW`` of its cells
hold the DEM inside the shell's span there or within ``FOLLOW_BAND_M`` of
it (``terrain_shaped.fit``'s measure).  Then it is SEATED as a terrain model:
its origin set one rigid frame written ``OBJECT_MSL`` at ``z0``.
Otherwise no seat lays it flat on our terrain -- the no-float seat buries
it, and a fit to the ground floats its edges -- and it is HIDDEN: its own
row is left out of the written DSF (``terrain_shaped.HIDDEN_SEAT``); the
rows sharing its origin are read like any other (:func:`off_the_shell`).

ITS RIDERS (:func:`off_the_shell`): a row authored in a hidden shell's
frame -- SBGL's fence and gutters -- stands on the shell's surface, metres
under its origin where the skin dips to the shore; read against our ground
that is a "below-grade solid" and the row would be kept as authored, its
fence buried 2 m (measured, lane lsbgl).  Seated with the shell, its deck
family exempted it.  With the shell hidden its below-grade reading is
dropped at its one derivation site: it is no pit, and it is seated on our
ground on its feet like any object.

AIRSIDE IS KING (:func:`airside_capped`): a seated shell never stands over
the solved airside surface -- its zero is lowered until its top lies at or
under every airside vertex in its plan.
"""
from __future__ import annotations

import dataclasses as _dc
import functools
import math
import os
import typing as _t

import numpy as np

from ..geom.terrain_deck import DeckGrid
from . import terrain_model as _tm
from . import terrain_shaped as _ts

__all__ = ["SEATED", "HIDDEN", "shape_of", "verdict", "placement_shells",
           "off_the_shell", "airside_capped", "log_line"]

SEATED = "seated"
HIDDEN = "hidden"
#: the highest the top may stand over its origin's ground (95th percentile)
AT_GRADE_M = 1.5
#: the least share of the upward plan that is hard
MIN_HARD = 0.5


def _static_plan_m(g: _t.Any) -> float:
    """The longer plan side of a geometry's static solid (0 with none)."""
    from .msl_feet import static_vertices
    v = static_vertices(g) if g is not None else None
    if v is None or not len(v):
        return 0.0
    return float(max(np.ptp(v[:, 0]), np.ptp(v[:, 2])))


@functools.lru_cache(maxsize=256)
def _shape(path: str, _mtime_ns: int, _size: int) -> "_tm.Shape | None":
    """The candidate test on one file version (module doc)."""
    from .obj8 import parse_obj8
    g = parse_obj8(path)
    plan = _static_plan_m(g)
    if plan < _tm.MIN_PLAN_M:
        return None
    tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
    # the cheap gates first: the grid is one pass per triangle
    if (_hard_share(g, tris) < MIN_HARD
            or float(np.percentile(g.vertices[tris][:, :, 1], 5.0)) > AT_GRADE_M):
        return None
    spread = _tm.photo_spread(g.vertices, _tm._vt_rows(path), tris)
    if spread > _tm.MAX_PHOTO_SPREAD:
        return None
    grid = _tm._grid(g)
    if grid is None or not grid.covered.any():
        return None
    lo, hi = np.percentile(grid.top[grid.covered], [5.0, 95.0])
    if (hi > AT_GRADE_M or hi - lo >= _tm.MIN_RELIEF_M      # a hill: terrain_model's
            or grid.relief_m < _ts.MIN_RELIEF_M):
        return None
    return _tm.Shape(grid, plan, float(hi - lo), spread)


def _hard_share(g: _t.Any, tris: np.ndarray) -> float:
    """The share of the upward plan of the static solid ``tris`` that is
    hard (``ATTR_hard`` or ``ATTR_hard_deck``)."""
    from .obj8 import HARD, HARD_DECK
    keep = ~g.animated if g.animated.shape[0] else np.ones(len(g.solid), dtype=bool)
    hard = np.isin(np.asarray(g.hardness)[keep], (HARD, HARD_DECK)) \
        if len(g.hardness) == len(g.solid) else np.zeros(len(tris), dtype=bool)
    p = g.vertices[tris]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    plan = 0.5 * np.abs(n[:, 1])
    up = np.abs(n[:, 1]) >= 0.9 * np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    total = float(plan[up].sum())
    return float(plan[up & hard].sum()) / total if total > 0.0 else 0.0


def shape_of(path: str, geometry: _t.Any = None) -> "_tm.Shape | None":
    """THE CANDIDATE TEST on an OBJ8 file (module doc), or ``None``.
    ``geometry``: its parsed ``ObjGeometry`` when the caller holds it --
    the plan gate then reads it and most files stop there."""
    if geometry is not None and _static_plan_m(geometry) < _tm.MIN_PLAN_M:
        return None
    try:
        st = os.stat(path)
        return _shape(path, st.st_mtime_ns, st.st_size)
    except (OSError, ValueError):
        return None


def verdict(grid: DeckGrid, xy: tuple[float, float], heading: float,
            dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]
            ) -> "tuple[str, float, float] | None":
    """``(SEATED | HIDDEN, z0, follow)`` of one placement (module doc), or
    ``None`` with no DEM under it."""
    rim = _tm.rim_seat(grid, xy, heading, dem_many)
    fit = _ts.fit(grid, xy, heading, dem_many)
    if rim is None or fit is None:
        return None
    z0 = min(rim, fit[0])
    ii, jj = np.nonzero(grid.covered)
    xs, ys = _tm._world(grid, ii, jj, xy, heading)
    dem = np.asarray(dem_many(xs, ys), dtype=float)
    ok = np.isfinite(dem)
    lo = dem[ok] - grid.top[ii[ok], jj[ok]]
    hi = dem[ok] - grid.bot[ii[ok], jj[ok]]
    gap = np.maximum(lo - z0, 0.0) + np.maximum(z0 - hi, 0.0)
    follow = float(np.mean(gap <= _ts.FOLLOW_BAND_M)) if len(gap) else 0.0
    return (SEATED if follow > _ts.MIN_FOLLOW else HIDDEN), z0, follow


def placement_shells(placements: _t.Sequence[tuple],
                     path_of: _t.Callable[[str], "str | None"],
                     geometry: _t.Callable[[str], _t.Any],
                     dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                     skip: _t.AbstractSet[str] = frozenset()
                     ) -> dict[str, _tm.TerrainModel]:
    """The ground shells among ``placements`` -- ``(id, def path, xy,
    heading, elevation, kind)`` rows -- by id, each a
    :class:`terrain_model.TerrainModel` carrying its verdict in ``ground``
    and its follow share in ``fit_m`` (``skip``: ids already read as
    terrain models).  A plain ``OBJECT`` or ``OBJECT_AGL`` row only, as
    :func:`terrain_model.placement_models`."""
    from .obj8 import is_stock_library_resource
    out: dict[str, _tm.TerrainModel] = {}
    shapes: dict[str, "_tm.Shape | None"] = {}
    for oid, dpath, xy, heading, _elev, kind in placements:
        if (kind == "OBJECT_MSL" or str(oid) in skip
                or is_stock_library_resource(dpath)):
            continue
        if dpath not in shapes:
            phys = path_of(dpath)
            g = None if phys is None else geometry(dpath)
            shapes[dpath] = None if g is None else shape_of(phys, g)
        shape = shapes[dpath]
        if shape is None:
            continue
        xy2 = (float(xy[0]), float(xy[1]))
        got = verdict(shape.grid, xy2, float(heading), dem_many)
        if got is None:
            continue
        ground, z0, follow = got
        out[str(oid)] = _tm.TerrainModel(
            str(oid), str(dpath), xy2, float(heading), z0, 0.0, 0.0, follow,
            shape.grid.area_m2, shape.relief_m, file=str(path_of(dpath) or ""),
            ground=ground)
    return out


def off_the_shell(o: _t.Any) -> _t.Any:
    """A rider of a HIDDEN ground shell (module doc) with its below-grade
    reading dropped -- it stood on the shell, in no pit."""
    return _dc.replace(o, below_grade=None, solid_min_z=None, solid_min_depth_m=None,
                       witnesses=(), below_grade_comps=(), buried=())


def airside_capped(models: _t.Sequence[tuple], surface: _t.Any, to_xy
                   ) -> tuple:
    """AIRSIDE IS KING: ``Airport.terrain_models`` rows ``(id, def path,
    TerrainModel, lift)`` with every SEATED ground shell's zero lowered so
    its top stands at or under each solved AIRSIDE vertex of ``surface``
    (``emit.surface.GradedSurface``) inside its plan.  Every other row,
    and a shell with no airside under it, unchanged."""
    shells = {m.id: m for _o, _d, m, _l in models if getattr(m, "ground", "") == SEATED}
    if not shells or surface is None:
        return tuple(models)
    air = set()
    for f in surface.faces:
        if f.side == "airside":
            air.update(f.ring)
            for h in f.holes:
                air.update(h)
    pts = [(to_xy(v.ll[1], v.ll[0]), v.z) for v in surface.vertices if v.id in air]
    if not pts:
        return tuple(models)
    px = np.array([p[0][0] for p in pts], dtype=float)
    py = np.array([p[0][1] for p in pts], dtype=float)
    pz = np.array([p[1] for p in pts], dtype=float)
    capped: dict[str, float] = {}
    for oid, m in shells.items():
        shape = shape_of(m.file) if m.file else None
        if shape is None:
            continue
        grid = shape.grid
        h = math.radians(m.heading)
        s, c = math.sin(h), math.cos(h)
        dx, dy = px - m.xy[0], py - m.xy[1]
        i, j, ok = grid.cell_of(dx * c - dy * s, -dx * s - dy * c)
        if not ok.any():
            continue
        over = float(np.min(pz[ok] - (m.z0 + grid.top[i[ok], j[ok]])))
        if over < 0.0:
            capped[oid] = m.z0 + over
    if not capped:
        return tuple(models)
    return tuple((oid, dpath, m if m.id not in capped else _dc.replace(m, z0=capped[m.id]),
                  lift) for oid, dpath, m, lift in models)


def log_line(icao: str, models: _t.Iterable[_tm.TerrainModel]) -> str:
    """The build log's one line on the ground shells."""
    shells = sorted({m.id: m for m in models if getattr(m, "ground", "")}.values(),
                    key=lambda m: m.id)
    if not shells:
        return f"[{icao}] ground shells: none"
    return f"[{icao}] ground shells: " + "; ".join(
        f"{m.path} ({m.id}) {m.ground.upper()}: {m.fit_m:.0%} of its "
        f"{m.area_m2:,.0f} m2 on the ground at its seat {m.z0:.2f} m"
        for m in shells)
