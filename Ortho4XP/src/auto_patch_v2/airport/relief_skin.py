"""A RELIEF SKIN AND ITS TOWN ARE ONE RIGID TERRAIN COMPOSITE (issue #2077,
owner 2026-11-15T05:46Z: "Yes to all three shell related rules").

Rule (A): a shared-origin object set that contains a terrain shell is ONE
rigid terrain-shaped composite, never split.  A pack may model a cliff or a
slope as one skin and stand a town on it in the same frame (LOWS's old
town: ``city_centr_08``, an 835 m skin from the river to the Moenchsberg
plateau, and thirteen files of walls, roofs and streets sharing its origin).
Read as buildings, the walls were split into 376 bodies and each re-anchored
on our ground, so the town no longer met its cliff.  The skin is too steep
and too low for :mod:`terrain_model` (its top does not follow the DEM's
shape, and its relief is 42 m) and has none of a terrain feature's floorless
underside area; this module RECOGNISES it by its geometry only (RULINGS 05e
-- no names, no DEM) and the frame then flows through ``obj8``'s terrain
model path: never read, split, re-anchored or padded.

THE CANDIDATE (one verdict per file version, :func:`shape_of`): the static
solid binned on the 5 m plan grid (``terrain_shaped.grid_of_triangles``),
its largest 8-connected component of covered cells --

* holds the object: at least :data:`MIN_SHARE` of the covered cells;
* spans ``terrain_model.MIN_PLAN_M`` on its longer side;
* has a top relief (5th-95th percentile) of at least :data:`MIN_RELIEF_M`;
* is a SINGLE SURFACE: at least :data:`MIN_SKIN` of its cells have top and
  bottom within :data:`SKIN_BAND_M` (a skin, not a building's stack);
* has NO FLOOR: at most :data:`MAX_FLOOR_SHARE` of its cells have their
  bottom within ``terrain_feature.FLOOR_BAND_M`` of the bottom's 5th
  percentile (``terrain_feature``'s floor share);
* is STEEP: at least :data:`MIN_STEEP` of its cells have a top gradient
  over :data:`STEEP_GRADIENT`.

Calibration over 12 packs (LOWS, SBRJ, SBGL, LXGB, BIKF, LICJ, KCRW, KEGE,
KHAF x2, KOAK, KBWI; spec ``docs/specs/2077-terrain-composites-spec.md`` 1):
the only new pass is ``city_centr_08``; every other pass is already a
terrain model or feature.  The nearest non-terrain objects measured fail one
gate each by a clear margin (KBWI_City/7 share 0.33, KCRW's landing-light
structure 485 m, city_centr_09 relief 14.5 m, KOAK Terminal_1 skin 0.00,
the Chesapeake Bay Bridge steep 0.00).

THE SEAT (2.2): the frame zero is our uncut ground under the set's origin
(the reader's ``anchor_z``): the author's town stands at its zero, and no
DEM fit seats a cliff (its crest cells read 405 m, its foot 428 m).  Every
member is written ``OBJECT_MSL`` at that zero plus its own lift.

THE ZERO FOOTPRINT (2.5, :func:`_zero_footprint`): a zero-level cell is a
5 m cell where a member that is not the skin has a near-vertical face
(``|n_y| <`` :data:`WALL_NY`) whose bottom lies within :data:`SKIRT_M` of the
frame zero -- a wall standing on the author's ground.  Their
:data:`CLOSE_M` morphological closing, less the skin's own plan, is the
footprint where the tile build conforms our ground to the frame zero
(``airport/terrain_fill``), so the walls stand on it and nothing pokes
through the streets.
"""
from __future__ import annotations

import dataclasses as _dc
import functools
import math
import os
import typing as _t

import numpy as np

from ..geom.terrain_deck import CELL_M
from . import terrain_model as _tm

__all__ = ["MIN_SHARE", "MIN_RELIEF_M", "MIN_SKIN", "SKIN_BAND_M", "MAX_FLOOR_SHARE",
           "MIN_STEEP", "STEEP_GRADIENT", "WALL_NY", "SKIRT_M", "CLOSE_M",
           "shape_of", "placement_skins", "with_planes", "log_line"]

MIN_SHARE = 0.9
MIN_RELIEF_M = 30.0
MIN_SKIN = 0.6
SKIN_BAND_M = 1.0
MAX_FLOOR_SHARE = 0.25
MIN_STEEP = 0.3
STEEP_GRADIENT = 0.25
#: a face is a wall when its unit normal's ``|y|`` is under this
WALL_NY = 0.5
#: a wall's bottom within this of the frame zero stands on the author's ground
SKIRT_M = 3.0
#: the zero-level cells' morphological closing radius (m)
CLOSE_M = 30.0


def _measures(grid: _t.Any) -> "dict[str, float] | None":
    """The candidate's _measures on a plan grid (module doc): ``share``,
    ``extent_m``, ``relief_m``, ``skin``, ``floor``, ``steep``; ``None``
    with no covered cell."""
    from scipy import ndimage

    from .terrain_feature import FLOOR_BAND_M
    cov = grid.covered
    lab, n = ndimage.label(cov, structure=np.ones((3, 3), dtype=bool))
    if not n:
        return None
    sizes = ndimage.sum(cov, lab, range(1, n + 1))
    k = int(np.argmax(sizes)) + 1
    comp = lab == k
    ii, jj = np.nonzero(comp)
    top, bot = grid.top[ii, jj], grid.bot[ii, jj]
    lo, hi = np.percentile(top, [5.0, 95.0])
    gy, gx = np.gradient(np.where(comp, grid.top, np.nan), CELL_M)
    slope = np.hypot(gx, gy)[ii, jj]
    slope = slope[np.isfinite(slope)]
    return {"share": float(sizes[k - 1] / cov.sum()),
            "extent_m": CELL_M * float(max(np.ptp(ii) + 1, np.ptp(jj) + 1)),
            "relief_m": float(hi - lo),
            "skin": float(np.mean(top - bot < SKIN_BAND_M)),
            "floor": float(np.mean(bot <= np.percentile(bot, 5.0) + FLOOR_BAND_M)),
            "steep": float(np.mean(slope > STEEP_GRADIENT)) if len(slope) else 0.0}


def _passes(m: "dict[str, float] | None") -> bool:
    return (m is not None and m["share"] >= MIN_SHARE and m["extent_m"] >= _tm.MIN_PLAN_M
            and m["relief_m"] >= MIN_RELIEF_M and m["skin"] >= MIN_SKIN
            and m["floor"] <= MAX_FLOOR_SHARE and m["steep"] >= MIN_STEEP)


def _cheap(g: _t.Any) -> bool:
    """The plan and height spans a candidate needs, before any binning."""
    from .msl_feet import static_vertices
    v = static_vertices(g) if g is not None else None
    return (v is not None and float(np.ptp(v[:, 1])) >= MIN_RELIEF_M
            and float(max(np.ptp(v[:, 0]), np.ptp(v[:, 2]))) >= _tm.MIN_PLAN_M)


@functools.lru_cache(maxsize=256)
def _file_shape(path: str, _mtime_ns: int, _size: int) -> "_tm.Shape | None":
    from .obj8 import parse_obj8
    try:
        g = parse_obj8(path)
        if not _cheap(g):
            return None
        grid = _tm._grid(g)
        m = None if grid is None else _measures(grid)
        if m is None or not _passes(m):
            return None
        tris = g.solid[~g.animated] if g.animated.shape[0] else g.solid
        return _tm.Shape(grid, m["extent_m"], m["relief_m"], 0.0,
                         _tm.post_m(g.vertices, tris))
    except (OSError, ValueError):
        return None


def shape_of(path: str, geometry: _t.Any = None) -> "_tm.Shape | None":
    """THE CANDIDATE TEST on an OBJ8 file (module doc), or ``None``;
    ``geometry`` (its parsed ``ObjGeometry``) lets most files stop at the
    cheap gates without a second parse."""
    if geometry is not None and not _cheap(geometry):
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return _file_shape(path, st.st_mtime_ns, st.st_size)


def placement_skins(placements: _t.Sequence[tuple],
                    path_of: _t.Callable[[str], "str | None"],
                    geometry: _t.Callable[[str], _t.Any],
                    dem_z: _t.Callable[[float, float], float],
                    skip: _t.AbstractSet[str] = frozenset(),
                    dem_many: "_t.Callable | None" = None,
                    fine: "_t.Callable | None" = None,
                    hidden: _t.AbstractSet[str] = frozenset()
                    ) -> dict[str, _tm.TerrainModel]:
    """The relief skins among ``placements`` -- ``(id, def path, xy,
    heading, elevation, kind)`` rows, plain ``OBJECT`` / ``OBJECT_AGL``
    only (an ``OBJECT_MSL`` skin keeps its reading) -- by id, each a
    :class:`terrain_model.TerrainModel` seated at ``dem_z`` under its
    origin (module doc).  ``skip``: ids another reading already holds (a
    terrain model, a ground shell, a terrain feature, a terrain-shaped
    deck: they come first).  ``dem_many`` / ``fine``: the hide offer
    (``terrain_model.quality``, the skin re-matched to the quality ground
    for that test only).  ``hidden``: the def paths the user hid (they
    come back with ``ground = "hidden"``)."""
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
        z0 = float(dem_z(*xy2))
        if not math.isfinite(z0):
            continue
        cover, hideable = (0.0, False) if dem_many is None else \
            _tm.quality(shape, xy2, float(heading), dem_many, fine)
        out[str(oid)] = _tm.TerrainModel(
            str(oid), str(dpath), xy2, float(heading), z0, 0.0, 0.0, 0.0,
            shape.grid.area_m2, shape.relief_m, cover, hideable or str(dpath) in hidden,
            str(path_of(dpath) or ""), fill=True, skin=True,
            ground="hidden" if str(dpath) in hidden else "")
    return out


def _wall_feet(tris: np.ndarray, lift: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(x, z, y)`` of every vertex of the near-vertical faces of the
    authored triangles ``tris``, ``y`` over the frame zero."""
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ny = np.abs(n[:, 1]) / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    v = tris[ny < WALL_NY].reshape(-1, 3)
    return v[:, 0], v[:, 2], v[:, 1] + float(lift)


def _zero_footprint(members: _t.Iterable[tuple[np.ndarray, float]],
                   skins: _t.Iterable[_t.Any]) -> list[np.ndarray]:
    """THE ZERO FOOTPRINT (module doc) in the composite's plan frame:
    ``members`` are ``(triangles (n, 3, 3), lift)`` of the members that are
    not skins, ``skins`` the skins' plan grids (``DeckGrid``).  ``(k, 2)``
    plan ``(x, z)`` rings, outer rings and holes, simplified within a
    quarter cell (``terrain_cut.outline_rings``); ``[]`` for none."""
    import shapely
    from scipy import ndimage
    from shapely.geometry import MultiPolygon, Polygon
    xs, zs, ys = [], [], []
    for tris, lift in members:
        if tris is None or not len(tris):
            continue
        x, z, y = _wall_feet(np.asarray(tris, float), lift)
        xs.append(x)
        zs.append(z)
        ys.append(y)
    if not xs or not sum(len(x) for x in xs):
        return []
    x, z, y = np.concatenate(xs), np.concatenate(zs), np.concatenate(ys)
    ix = np.floor(x / CELL_M).astype(np.int64)
    iz = np.floor(z / CELL_M).astype(np.int64)
    k = max(1, int(round(CLOSE_M / CELL_M)))
    # padded by the closing radius, so the closing never meets the border
    i0, j0 = int(ix.min()) - k, int(iz.min()) - k
    foot = np.full((int(ix.max()) - i0 + 1 + k, int(iz.max()) - j0 + 1 + k), np.inf)
    np.minimum.at(foot, (ix - i0, iz - j0), y)
    zero = np.isfinite(foot) & (np.abs(foot) <= SKIRT_M)
    if not zero.any():
        return []
    disc = np.hypot(*np.mgrid[-k:k + 1, -k:k + 1]) <= k
    closed = ndimage.binary_closing(zero, structure=disc)
    for g in skins:
        ci, cj = np.nonzero(g.covered)
        ii = np.round((g.x0 + CELL_M * ci) / CELL_M - 0.5).astype(np.int64) - i0
        jj = np.round((g.z0 + CELL_M * cj) / CELL_M - 0.5).astype(np.int64) - j0
        ok = (ii >= 0) & (jj >= 0) & (ii < closed.shape[0]) & (jj < closed.shape[1])
        closed[ii[ok], jj[ok]] = False
    fi, fj = np.nonzero(closed)
    if not len(fi):
        return []
    h = CELL_M / 2.0
    cx, cz = (fi + i0 + 0.5) * CELL_M, (fj + j0 + 0.5) * CELL_M
    region = shapely.union_all(shapely.box(cx - h, cz - h, cx + h, cz + h)).simplify(h / 2.0)
    out = []
    for poly in (region.geoms if isinstance(region, MultiPolygon) else [region]):
        if isinstance(poly, Polygon) and not poly.is_empty:
            out += [np.asarray(r.coords, float) for r in (poly.exterior, *poly.interiors)]
    return out


def _to_frame(xy: tuple[float, float], heading: float, ring: np.ndarray) -> tuple:
    """Plan ``(x, z)`` -> frame ``(east, north)`` (``terrain_model._world``)."""
    h = math.radians(heading)
    s, c = math.sin(h), math.cos(h)
    x, z = ring[:, 0], ring[:, 1]
    e, n = xy[0] + x * c - z * s, xy[1] - (x * s + z * c)
    return tuple((round(float(a), 3), round(float(b), 3)) for a, b in zip(e, n, strict=True))


def with_planes(models: _t.Mapping[str, _tm.TerrainModel], placements: _t.Sequence[tuple],
                geometry: _t.Callable[[str], _t.Any]) -> dict[str, _tm.TerrainModel]:
    """``models`` (``terrain_model.set_members``' map) with every seated
    relief skin's frame carrying its :func:`_zero_footprint` in frame metres
    (:attr:`TerrainModel.plane`); ``geometry(def path)`` the parsed
    geometry or ``None``."""
    seeds = {m.id: m for m in models.values() if m.skin and not m.ground}
    if not seeds:
        return dict(models)
    by_id = {str(p[0]): p for p in placements}
    planes: dict[str, tuple] = {}
    for sid, m in seeds.items():
        members, skins = [], []
        for oid, mm in models.items():
            p = by_id.get(oid)
            if mm.id != sid or p is None:
                continue
            g = geometry(p[1])
            if g is None:
                continue
            if oid == sid or shape_of(str(getattr(g, "path", "") or ""), g) is not None:
                grid = _tm._grid(g)
                if grid is not None:
                    skins.append(grid)
                continue
            lift = float(p[4] or 0.0) if p[5] == "OBJECT_AGL" else 0.0
            members.append((_tm._solid(g), lift))
        rings = _zero_footprint(members, skins)
        planes[sid] = tuple(_to_frame(m.xy, m.heading, r) for r in rings)
    return {oid: (_dc.replace(m, plane=planes[m.id]) if m.id in planes else m)
            for oid, m in models.items()}


def log_line(icao: str, models: _t.Iterable[_tm.TerrainModel]) -> str:
    """The build log's one line on the relief skins."""
    skins = sorted({m.id: m for m in models if getattr(m, "skin", False)}.values(),
                   key=lambda m: m.id)
    if not skins:
        return f"[{icao}] relief skins: none"
    return f"[{icao}] relief skins: " + "; ".join(
        f"{m.path} ({m.id}) {'HIDDEN' if m.ground else 'seated'} at its origin's ground "
        f"{m.z0:.2f} m, {m.relief_m:.0f} m relief, {m.area_m2:,.0f} m2, zero footprint "
        f"{len(m.plane)} ring(s)" + (f", hideable ({m.quality_cover:.0%} under quality "
                                     f"elevation)" if m.hideable else "")
        for m in skins)
