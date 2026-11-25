"""PARTIAL TERRAIN SHELLS: A PACK OBJECT WHOSE OUTER RIM IS GROUND MEETS OUR
MESH FLUSH ALL ROUND (issue #2197; ELLX, LDSP).

Owner sim read 2026-11-20T14:20Z (ELLX): "the large parking lots ... that
have underground parking on the two sides of the terminal are modeled
almost as partial terrain shells, the terrain should meet it's outer edges
flush all the way around so you can't see under it."  2026-11-22T16:25Z
(LDSP): "the terminal area objects include their immediate surrounding
terrain as objects ... we need to recognize that and seat and grade things
so it blends into the natural terrain correctly."

Such an object is no terrain model (``terrain_model``: a 50 m hill, one
photo density, a 500 m FILE) and no small shell (``terrain_shell``: soft,
steep, ``OBJECT_MSL``): it is a landside COMPOSITE -- many OBJ8 files
exported at ONE origin (the author's one frame), paved, multi-level, and
its outer skirt is the GROUND around it.  Every terrain gate reads one
file and a hill; this module reads the ORIGIN SET and its rim.

THE PLAN (:func:`_set_raster`): the static solids of every row sharing one
origin (``msl_feet.origin_key`` plus the row's lift), placed at the
origin's heading and rasterised together (``geom.shape_class.rasterise``:
per cell its top and its lowest surface).

THE GROUND SHEET (:func:`_ground_sheet`, the DEM ``g`` over the frame zero
``z0`` at each cell): SEEDS are the covered cells whose top lies within
``ground_shell.AT_GRADE_M`` of ``g``; the sheet is every covered cell
reached from a seed through 4-neighbours whose tops differ by at most
:data:`SHEET_STEP_M` (a continuous surface: a kerb, a ramp, never a wall)
and whose top stays within ``terrain_shell.SHELL_LEVEL_M`` of ``g`` (a
deck reached up a car-park ramp is not ground).  A roof is cut off from
the sheet by its wall.

THE CANDIDATE (:func:`_recognise`): the set spans at least
``terrain_shell.SHELL_MIN_PLAN_M``; the sheet holds at least
:data:`MIN_SHEET_SHARE` of the plan and at least :data:`MIN_RIM_SHARE` of
the outer rim (``terrain_model.outer_rim``): the object's edge is, for the
most part, its ground; and the sheet MODELS GROUND -- its top departs
from its least-squares plane by at least :data:`MIN_RELIEF_M`
(``terrain_shaped.MIN_RELIEF_M``, #1730's terrain-skin witness: every
plate and deck measured departs by under 2 m).  An apron plate, a pad or a
car park laid on a grade is no partial shell.

THE SHEET IS OUR GROUND, REMODELLED (#2197 round 2, the narrowing; spec
``docs/specs/2197-partial-shell-patch-rim-spec.md`` §1): round 1's three
shares also held 92 sets in 61 packs whose "ground" is a bridge deck, a
viaduct's approach, a tunnel's portal, a landmark's plinth, a hangar's
apron, an earth-covered bunker, a hill or a rock -- relief the author
added, not the ground it stands on.  At the seat, the sheet must also:

* FOLLOW our ground (:data:`MIN_FOLLOW_SHARE` of its cells within
  ``ground_shell.AT_GRADE_M`` of it): the author's ground is ours, never
  a terrace standing far from credible terrain (RULINGS 2026-11-25f: such
  a pack is left as authored and our ground never rises to it);
* have its RELIEF EXPLAINED by ours: the sheet's departure from OUR ground
  carries at most :data:`MAX_UNEXPLAINED` of the sheet's own relief (the
  same 5th-95th percentile span beyond a plane) -- a bridge, a plinth or
  a hill models relief our ground does not have;
* be a SKIN (:data:`MIN_SKIN_SHARE` of its cells no thicker than
  :data:`SKIN_M`, top to lowest surface): a ground surface, never a deck
  or a slab over a void.

THE SEAT (never moves the object's shape): one rigid frame, every row of
the set ``OBJECT_MSL`` at ``z0`` plus its own lift (``terrain_model``'s
SEAT path).  ``z0`` is the origin's ground (``X-Plane``'s own seat of an
``OBJECT`` row) moved by the median of ``g - top`` over the sheet: the
rigid L1 fit of the author's ground to ours.  Never refitted in shape.

THE RIM (:func:`_rim_stations`): every outer-rim cell IN THE SHEET is a
station at ``z0 + top`` -- the height the author's ground stands at its
edge.  The tile build GRADES our raster to the stations
(``terrain_fill.rim_grade``): within the fill's shoulder of a station the
ground takes the station's height (raised OR lowered), then a linear
feather to ``terrain_fill.REACH_M``; never a frozen posting (patch, tile
edge).  A wall's rim cell is no station: our ground there is left alone.

Nothing here names a pack, an object or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

#: the least relief of the sheet beyond its plane (module doc)
from .terrain_shaped import MIN_RELIEF_M

__all__ = ["SHEET_STEP_M", "MIN_SHEET_SHARE", "MIN_RIM_SHARE", "MIN_RELIEF_M",
           "MIN_FOLLOW_SHARE", "MAX_UNEXPLAINED", "MIN_SKIN_SHARE", "SKIN_M",
           "placement_models", "rim_record", "log_line"]

#: the most two neighbouring cells of the ground sheet may differ (m)
SHEET_STEP_M = 0.5
#: the least share of the set's plan the ground sheet holds
MIN_SHEET_SHARE = 0.5
#: the least share of the set's outer rim the ground sheet holds
MIN_RIM_SHARE = 0.5
#: the least share of the sheet within ``AT_GRADE_M`` of our ground at the
#: seat (module doc, THE SHEET IS OUR GROUND; census: genuine 0.85-0.96,
#: the nearest refused skin 0.69-0.71)
MIN_FOLLOW_SHARE = 0.8
#: the most of the sheet's relief its departure from our ground may carry
#: (census: genuine 0.21-0.31, the nearest refused skin 0.53)
MAX_UNEXPLAINED = 0.5
#: the least share of the sheet that is a skin (census: genuine 0.95-1.00;
#: the bridges and elevated roads that follow our ground 0.06-0.81)
MIN_SKIN_SHARE = 0.9
#: the thickest a skin cell stands, top to lowest surface (m)
SKIN_M = 0.5
#: the plan grid of the set (m; ``terrain_cut.HOLD_CELL_M``)
CELL_M = 1.0
_MAX_CELLS = 1_000_000


@_dc.dataclass(frozen=True)
class _RimSet:
    """One recognised origin set: its frame zero, sheet and rim stations
    (frame metres east / north of the origin; ``z`` MSL)."""

    xy: tuple[float, float]
    heading: float
    z0: float
    plan_m: float
    sheet_share: float
    rim_share: float
    #: the sheet's top relief beyond its least-squares plane (m)
    relief_m: float
    stations: np.ndarray          # (n, 3): east, north, z MSL
    rings: tuple                  # outline rings, frame metres
    #: THE SHEET SURFACE (#2197 round 2, the patch half): ``(e0, n0, step,
    #: z)`` -- the plan grid's corner, its cell and ``z`` MSL of every sheet
    #: cell (``nan`` off the sheet): the author's ground the patch meets
    sheet: tuple = ()

    def sheet_at(self, e: np.ndarray, n: np.ndarray) -> np.ndarray:
        """The author's ground (z MSL) at frame ``(e, n)``; ``nan`` off
        the sheet."""
        e, n = np.asarray(e, float), np.asarray(n, float)
        out = np.full(e.shape, np.nan)
        if not self.sheet:
            return out
        e0, n0, step, z = self.sheet
        j = np.floor((e - e0) / step).astype(np.int64)
        i = np.floor((n - n0) / step).astype(np.int64)
        ok = (i >= 0) & (j >= 0) & (i < z.shape[0]) & (j < z.shape[1])
        out[ok] = z[i[ok], j[ok]]
        return out


def _set_raster(solids: _t.Sequence[np.ndarray], heading: float) -> "_t.Any | None":
    """The plan of an origin set (module doc): ``solids`` the authored
    ``(n, 3, 3)`` static triangles of each member (``x`` east, ``y`` up,
    ``z`` south, already lifted by the member's own lift)."""
    tris = [p for p in solids if p is not None and len(p)]
    if not tris:
        return None
    p = np.concatenate(tris)
    h = math.radians(heading)
    s, c = math.sin(h), math.cos(h)
    e = p[:, :, 0] * c - p[:, :, 2] * s
    n = -(p[:, :, 0] * s + p[:, :, 2] * c)
    return _raster_of(np.stack([e, n, p[:, :, 1]], -1))


def _raster_of(p: np.ndarray, step: float = CELL_M, chunk: int = 4_000_000) -> "_t.Any | None":
    """``geom.shape_class.Raster`` (per cell its top and lowest surface)
    of the plan triangles ``p`` ``(n, 3, 3)`` as ``(east, north, z)``,
    binned at cell centres, vectorised (an origin set is 10^5-10^6
    triangles; ``shape_class.rasterise`` reads one triangle at a time)."""
    from ..geom import shape_class as _sc
    if not len(p):
        return None
    xy = p[:, :, :2]
    lo = xy.reshape(-1, 2).min(0)
    hi = xy.reshape(-1, 2).max(0)
    ncol, nrow = int((hi[0] - lo[0]) // step) + 1, int((hi[1] - lo[1]) // step) + 1
    if ncol * nrow > _MAX_CELLS * 4:
        return None
    top = np.full(nrow * ncol, -np.inf)
    low = np.full(nrow * ncol, np.inf)
    x, y, z = p[:, :, 0], p[:, :, 1], p[:, :, 2]
    d = (y[:, 1] - y[:, 2]) * (x[:, 0] - x[:, 2]) + (x[:, 2] - x[:, 1]) * (y[:, 0] - y[:, 2])
    ok = np.abs(d) > 1e-12
    c0 = np.ceil((x.min(1) - lo[0]) / step - 0.5).astype(np.int64)
    c1 = np.floor((x.max(1) - lo[0]) / step - 0.5).astype(np.int64)
    r0 = np.ceil((y.min(1) - lo[1]) / step - 0.5).astype(np.int64)
    r1 = np.floor((y.max(1) - lo[1]) / step - 0.5).astype(np.int64)
    c0, r0 = np.maximum(c0, 0), np.maximum(r0, 0)
    c1, r1 = np.minimum(c1, ncol - 1), np.minimum(r1, nrow - 1)
    nc, nr = c1 - c0 + 1, r1 - r0 + 1
    ok &= (nc > 0) & (nr > 0)
    t_all = np.flatnonzero(ok)
    cnt = (nc * nr)[t_all]
    starts = np.r_[0, np.cumsum(cnt)]
    k0 = 0
    while k0 < len(t_all):
        k1 = int(np.searchsorted(starts, starts[k0] + chunk, side="right")) - 1
        k1 = max(k1, k0 + 1)
        t = np.repeat(t_all[k0:k1], cnt[k0:k1])
        off = np.arange(len(t)) - np.repeat(starts[k0:k1] - starts[k0], cnt[k0:k1])
        cc = c0[t] + off % nc[t]
        rr = r0[t] + off // nc[t]
        cx, cy = lo[0] + (cc + 0.5) * step, lo[1] + (rr + 0.5) * step
        w1 = ((y[t, 1] - y[t, 2]) * (cx - x[t, 2]) + (x[t, 2] - x[t, 1]) * (cy - y[t, 2])) / d[t]
        w2 = ((y[t, 2] - y[t, 0]) * (cx - x[t, 2]) + (x[t, 0] - x[t, 2]) * (cy - y[t, 2])) / d[t]
        w3 = 1.0 - w1 - w2
        inn = (w1 >= -1e-9) & (w2 >= -1e-9) & (w3 >= -1e-9)
        zz = (w1 * z[t, 0] + w2 * z[t, 1] + w3 * z[t, 2])[inn]
        cell = (rr * ncol + cc)[inn]
        np.maximum.at(top, cell, zz)
        np.minimum.at(low, cell, zz)
        k0 = k1
    top[~np.isfinite(top)] = np.nan
    low[~np.isfinite(low)] = np.nan
    return _sc.Raster(float(lo[0]), float(lo[1]), step, top.reshape(nrow, ncol),
                      low.reshape(nrow, ncol))


def _centres(r: _t.Any) -> tuple[np.ndarray, np.ndarray]:
    ny, nx = r.top.shape
    return (r.e0 + (np.arange(nx) + 0.5) * r.step)[None, :].repeat(ny, 0), \
        (r.n0 + (np.arange(ny) + 0.5) * r.step)[:, None].repeat(nx, 1)


def _ground_sheet(top: np.ndarray, g: np.ndarray) -> np.ndarray:
    """THE GROUND SHEET (module doc) of a plan's ``top`` over the ground
    ``g`` (both over the frame zero; ``nan`` uncovered): a boolean mask."""
    from .ground_shell import AT_GRADE_M
    from .terrain_shell import SHELL_LEVEL_M
    cov = np.isfinite(top) & np.isfinite(g)
    near = cov & (np.abs(np.where(cov, top - g, np.inf)) <= SHELL_LEVEL_M)
    seed = near & (np.abs(np.where(cov, top - g, np.inf)) <= AT_GRADE_M)
    if not seed.any():
        return seed
    t = np.where(near, top, np.nan)
    # two cells join where both are near and their tops differ <= the step
    link_e = near[:, :-1] & near[:, 1:] & (np.abs(t[:, 1:] - t[:, :-1]) <= SHEET_STEP_M)
    link_n = near[:-1, :] & near[1:, :] & (np.abs(t[1:, :] - t[:-1, :]) <= SHEET_STEP_M)
    lab = _components(near.shape, link_e, link_n)
    keep = np.unique(lab[seed])
    return near & np.isin(lab, keep)


def _components(shape: tuple, link_e: np.ndarray, link_n: np.ndarray) -> np.ndarray:
    """Connected-component labels of a grid graph whose edges are the
    east and north links (union-find through scipy's sparse graph)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    ny, nx = shape
    idx = np.arange(ny * nx).reshape(shape)
    a = np.concatenate([idx[:, :-1][link_e], idx[:-1, :][link_n]])
    b = np.concatenate([idx[:, 1:][link_e], idx[1:, :][link_n]])
    m = coo_matrix((np.ones(len(a), dtype=np.int8), (a, b)), shape=(ny * nx, ny * nx))
    return connected_components(m, directed=False)[1].reshape(shape)


def _rim_stations(r: _t.Any, sheet: np.ndarray, z0: float) -> np.ndarray:
    """``(n, 3)`` frame ``(east, north, z MSL)`` of every outer-rim cell in
    the ground sheet (module doc, THE RIM)."""
    from .terrain_model import outer_rim
    rim = outer_rim(np.isfinite(r.top)) & sheet
    ii, jj = np.nonzero(rim)
    e, n = _centres(r)
    return np.column_stack([e[ii, jj], n[ii, jj], z0 + r.top[ii, jj]])


def _outline_rings(r: _t.Any, simplify_m: float = 1.0) -> tuple:
    """The plan's outer outline rings (frame metres), simplified."""
    import shapely
    from shapely.geometry import box
    cov = np.isfinite(r.top)
    ii, jj = np.nonzero(cov)
    if not len(ii):
        return ()
    cells = []
    for i in np.unique(ii):
        row = np.flatnonzero(cov[i])
        cut = np.flatnonzero(np.diff(row) > 1)
        for a, b in zip(np.r_[row[0], row[cut + 1]], np.r_[row[cut], row[-1]], strict=True):
            cells.append(box(r.e0 + a * r.step, r.n0 + i * r.step,
                             r.e0 + (b + 1) * r.step, r.n0 + (i + 1) * r.step))
    u = shapely.union_all(cells).simplify(simplify_m)
    polys = getattr(u, "geoms", [u])
    return tuple(np.asarray(p.exterior.coords) for p in polys if p.area > 4 * r.step ** 2)


def _recognise(r: _t.Any, xy: tuple[float, float], heading: float,
              dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray]
              ) -> "_RimSet | None":
    """THE CANDIDATE and THE SEAT of one origin set's plan ``r`` placed at
    frame ``xy`` (module doc), or ``None``."""
    from .terrain_model import outer_rim
    from .terrain_shell import SHELL_MIN_PLAN_M
    if r is None:
        return None
    cov = np.isfinite(r.top)
    plan = float(max(cov.shape) * r.step)
    if plan < SHELL_MIN_PLAN_M or not cov.any():
        return None
    e, n = _centres(r)
    dem = np.full(cov.shape, np.nan)
    dem[cov] = np.asarray(dem_many(xy[0] + e[cov], xy[1] + n[cov]), dtype=float)
    z_or = float(np.asarray(dem_many(np.array([xy[0]]), np.array([xy[1]])), float)[0])
    if not math.isfinite(z_or):
        return None
    z0 = z_or
    sheet = _ground_sheet(r.top, dem - z0)
    if sheet.any():
        # the rigid L1 fit of the author's ground to ours, then read again
        z0 = z_or + float(np.median((dem - z_or - r.top)[sheet]))
        sheet = _ground_sheet(r.top, dem - z0)
    rim = outer_rim(cov)
    sheet_share = float(sheet.sum()) / float(cov.sum())
    rim_share = float((rim & sheet).sum()) / max(1.0, float(rim.sum()))
    if sheet_share < MIN_SHEET_SHARE or rim_share < MIN_RIM_SHARE:
        return None
    relief = _sheet_relief(e[sheet], n[sheet], r.top[sheet])
    if relief < MIN_RELIEF_M or not _is_our_ground(r, sheet, dem - z0, e, n, relief):
        return None
    return _RimSet((float(xy[0]), float(xy[1])), float(heading), z0, plan, sheet_share,
                  rim_share, relief, _rim_stations(r, sheet, z0), _outline_rings(r),
                  (r.e0, r.n0, r.step, np.where(sheet, z0 + r.top, np.nan).astype(np.float32)))


def _sheet_relief(e: np.ndarray, n: np.ndarray, top: np.ndarray) -> float:
    """THE MODELLED GROUND: the 5th-95th percentile span of the sheet's
    departure from its least-squares plane (``terrain_deck.DeckGrid.
    relief_m``'s measure): a pad or an apron plate on a grade has none."""
    if len(top) < 3:
        return 0.0
    a = np.c_[e, n, np.ones(len(e))]
    coef, *_ = np.linalg.lstsq(a, top, rcond=None)
    lo, hi = np.percentile(top - a @ coef, [5.0, 95.0])
    return float(hi - lo)


def _is_our_ground(r: _t.Any, sheet: np.ndarray, g: np.ndarray, e: np.ndarray,
                   n: np.ndarray, relief: float) -> bool:
    """THE SHEET IS OUR GROUND, REMODELLED (module doc): it follows ``g``
    (our ground over the seat's zero), our ground explains its relief, and
    it is a skin."""
    from .ground_shell import AT_GRADE_M
    dev = (r.top - g)[sheet]
    if float(np.mean(np.abs(dev) <= AT_GRADE_M)) < MIN_FOLLOW_SHARE:
        return False
    if _sheet_relief(e[sheet], n[sheet], dev) > MAX_UNEXPLAINED * relief:
        return False
    return float(np.mean((r.top - r.low)[sheet] <= SKIN_M)) >= MIN_SKIN_SHARE


def _span_m(solids: _t.Sequence[np.ndarray]) -> float:
    """The longer plan side of a set's authored solids (m)."""
    v = np.concatenate([p.reshape(-1, 3) for p in solids])
    return float(max(np.ptp(v[:, 0]), np.ptp(v[:, 2])))


def _placement_sets(placements: _t.Sequence[tuple],
                   solid_of: _t.Callable[[str], "np.ndarray | None"],
                   dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                   skip: _t.AbstractSet[str] = frozenset()) -> dict[tuple, tuple]:
    """The recognised origin sets among ``placements`` -- ``(id, def path,
    xy, heading, elevation, kind)`` rows; ``solid_of(def path)`` the
    authored static solid or ``None``; ``skip`` ids already read as
    terrain objects -- as ``{origin key: (_RimSet, [member ids])}``.  A
    plain ``OBJECT`` or ``OBJECT_AGL`` row only (an ``OBJECT_MSL`` set is
    the author's own height: ``terrain_shell``'s)."""
    from .obj8 import is_stock_library_resource
    from .terrain_model import _origin
    from .terrain_shell import SHELL_MIN_PLAN_M
    groups: dict[tuple, list] = {}
    for oid, dpath, xy, heading, elev, kind in placements:
        if kind == "OBJECT_MSL" or is_stock_library_resource(dpath):
            continue
        groups.setdefault(_origin(xy, heading, elev, kind), []).append(
            (str(oid), dpath, xy, heading, elev))
    out: dict[tuple, tuple] = {}
    for key, rows in groups.items():
        if any(oid in skip for oid, *_ in rows):
            continue
        solids = []
        for _oid, dpath, _xy, _h, elev in rows:
            p = solid_of(dpath)
            if p is not None and len(p):
                p = p.copy()
                p[:, :, 1] += float(elev or 0.0)
                solids.append(p)
        oid, _d, xy, heading, _e = rows[0]
        if not solids or _span_m(solids) < SHELL_MIN_PLAN_M:
            continue
        r = _set_raster(solids, float(heading))
        if r is None or max(r.top.shape) * r.step < SHELL_MIN_PLAN_M:
            continue
        got = _recognise(r, (float(xy[0]), float(xy[1])), float(heading), dem_many)
        if got is not None:
            out[key] = (got, [row[0] for row in rows])
    return out


def placement_models(placements: _t.Sequence[tuple],
                     solid_of: _t.Callable[[str], "np.ndarray | None"],
                     dem_many: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                     skip: _t.AbstractSet[str] = frozenset()) -> dict[str, _t.Any]:
    """:func:`_placement_sets` as ``terrain_model.TerrainModel`` records by
    the set's first row id (``terrain_model.set_members`` then maps every
    row of the origin to it: one rigid frame at ``z0``)."""
    from .terrain_model import TerrainModel
    out: dict[str, _t.Any] = {}
    paths = {str(p[0]): str(p[1]) for p in placements}
    for rs, ids in _placement_sets(placements, solid_of, dem_many, skip).values():
        oid = ids[0]
        out[oid] = TerrainModel(oid, paths[oid], rs.xy, rs.heading, rs.z0, 0.0, 0.0, 0.0,
                                float(len(rs.stations)), 0.0, rim=rs)
    return out


def rim_record(rs: _RimSet, to_ll: _t.Callable) -> dict[str, _t.Any]:
    """The seat record's ``rim`` (``terrain_model.seat_records``): the
    anchor, the stations ``[lat, lon, z MSL]`` and the plan rings
    ``[[lat, lon], ...]``; ``to_ll(x, y) -> (lat, lon)`` the airport
    frame's."""
    def ll(e: float, n: float) -> list:
        la, lo = to_ll(rs.xy[0] + float(e), rs.xy[1] + float(n))
        return [round(float(la), 8), round(float(lo), 8)]
    lat, lon = ll(0.0, 0.0)
    return {"lat": lat, "lon": lon, "z0": round(rs.z0, 3),
            "sheet": round(rs.sheet_share, 3), "rim_share": round(rs.rim_share, 3),
            "stations": [ll(e, n) + [round(float(z), 3)] for e, n, z in rs.stations],
            "rings": [[ll(e, n) for e, n in r] for r in rs.rings]}


def log_line(icao: str, models: _t.Iterable[_t.Any]) -> str:
    """The build log's one line on the partial shells."""
    got = sorted({m.id: m for m in models if getattr(m, "rim", None) is not None}.values(),
                 key=lambda m: m.id)
    if not got:
        return f"[{icao}] partial shells: none"
    return f"[{icao}] partial shells: " + "; ".join(
        f"{m.path} ({m.id}) one frame at {m.z0:.2f} m, ground sheet "
        f"{m.rim.sheet_share:.0%} of its plan and {m.rim.rim_share:.0%} of its rim, "
        f"{len(m.rim.stations)} rim station(s) our ground is graded to" for m in got)
