"""A COMPOSITE'S SHEET JOINS ITS MEMBERS INTO ONE UNDERSIDE MAP (owner
RULINGS 2026-11-25l "composites like partial shells", 25m (5); spec
``docs/specs/underside-height-map-20261125.md`` §1).

A landside COMPOSITE is one origin set (a pack ``Unit``: every row at one
anchor spelling) whose author modelled the GROUND round his buildings:
paved, multi-level, its outer skirt the ground (#2197: ELLX ``Terminal-A``
+ SkyPark, ``Lux_Fuel_base``, ``firestation``, ``pool_5``).  The §16g
clusters split it into its buildings; its sheet is what makes it one
group, so the clusters its sheet touches share ONE map.

THE TEST, on the plan of the set's every part (``unit_underside``'s set
layers, lines and scatter included) over our DEM -- the partial-shell gates
of #2197 round 2 (``ground_rim``'s, the same constants):

* the set spans ``terrain_shell.SHELL_MIN_PLAN_M`` or more;
* THE SHEET (``underside_map.ground_sheet``: cells within
  ``terrain_shell.SHELL_LEVEL_M`` of our ground joined to one within
  ``ground_shell.AT_GRADE_M``, at the frame zero ``z0`` = the L1 fit of
  its top to our ground) holds :data:`MIN_SHEET_SHARE` of the plan and of
  the outer rim;
* it MODELS GROUND: relief beyond its plane ``terrain_shaped.MIN_RELIEF_M``
  or more;
* it IS OUR GROUND, REMODELLED: :data:`MIN_FOLLOW_SHARE` of it within
  ``AT_GRADE_M`` of our ground, at most :data:`MAX_UNEXPLAINED` of its
  relief unexplained by ours, and :data:`MIN_SKIN_SHARE` of it a skin.

Read on the day's DEM, never cached.  Nothing here names a pack, an object
or an airport."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from ..geom import underside_map as _um

__all__ = ["MIN_SHEET_SHARE", "MIN_RIM_SHARE", "MIN_FOLLOW_SHARE", "MAX_UNEXPLAINED", "dem_many",
           "MIN_SKIN_SHARE", "is_composite", "join"]

#: the least share of the set's plan, and of its outer rim, the sheet holds
MIN_SHEET_SHARE = 0.5
MIN_RIM_SHARE = 0.5
#: the least share of the sheet within ``AT_GRADE_M`` of our ground
MIN_FOLLOW_SHARE = 0.8
#: the most of the sheet's relief its departure from our ground may carry
MAX_UNEXPLAINED = 0.5
#: the least share of the sheet that is a skin (``underside_map.SKIN_M``)
MIN_SKIN_SHARE = 0.9


def dem_many(dem) -> _t.Callable[[np.ndarray, np.ndarray], np.ndarray]:
    many = getattr(dem, "z_many", None)
    if many is not None:
        return lambda x, y: np.asarray(many(x, y), dtype=float)

    def one(x, y):
        out = np.full(len(x), np.nan)
        for k, (a, b) in enumerate(zip(x, y, strict=True)):
            try:
                out[k] = float(dem.z(float(a), float(b)))
            except Exception:                   # noqa: BLE001 -- off the raster
                pass
        return out
    return one


def is_composite(g: _um.Layers, dem_many) -> "np.ndarray | None":
    """THE TEST (module doc) of one origin set's composed layers ``g``:
    its sheet (a boolean grid) when it is a composite, else ``None``."""
    from .ground_shell import AT_GRADE_M
    from .terrain_model import outer_rim
    from .terrain_shaped import MIN_RELIEF_M
    from .terrain_shell import SHELL_LEVEL_M, SHELL_MIN_PLAN_M
    cov = np.isfinite(g.top)
    if not cov.any() or max(cov.shape) * g.step < SHELL_MIN_PLAN_M:
        return None
    ii, jj = np.nonzero(cov)
    e, n = g.centres(ii, jj)
    dem = np.full(cov.shape, np.nan)
    dem[ii, jj] = dem_many(e, n)
    top = g.top.astype(float)
    with np.errstate(invalid="ignore"):
        z0 = float(np.nanmedian(dem - top))
    if not np.isfinite(z0):
        return None
    sheet = _um.ground_sheet(top, dem - z0, SHELL_LEVEL_M, AT_GRADE_M)
    if sheet.any():          # the rigid L1 fit of the author's ground to ours
        z0 = float(np.median((dem - top)[sheet]))
        sheet = _um.ground_sheet(top, dem - z0, SHELL_LEVEL_M, AT_GRADE_M)
    rim = outer_rim(cov)
    if (sheet.sum() < MIN_SHEET_SHARE * cov.sum()
            or (rim & sheet).sum() < MIN_RIM_SHARE * max(1, rim.sum())):
        return None
    si, sj = np.nonzero(sheet)
    se, sn = g.centres(si, sj)
    rel = _um.relief(se, sn, top[sheet])
    if rel < MIN_RELIEF_M:
        return None
    dev = top[sheet] - (dem[sheet] - z0)
    if float(np.mean(np.abs(dev) <= AT_GRADE_M)) < MIN_FOLLOW_SHARE:
        return None
    if _um.relief(se, sn, dev) > MAX_UNEXPLAINED * rel:
        return None
    if float(np.mean((top - g.low)[sheet] <= _um.SKIN_M)) < MIN_SKIN_SHARE:
        return None
    return sheet


def _on(sheet: np.ndarray, src: _um.Layers, dst: _um.Layers) -> np.ndarray:
    """``sheet`` (on ``src``'s grid) read on ``dst``'s grid (one lattice)."""
    out = np.zeros(dst.top.shape, dtype=bool)
    di = int(round((src.n0 - dst.n0) / dst.step))
    dj = int(round((src.e0 - dst.e0) / dst.step))
    h, w = sheet.shape
    i0, j0 = max(di, 0), max(dj, 0)
    i1, j1 = min(di + h, out.shape[0]), min(dj + w, out.shape[1])
    if i1 > i0 and j1 > j0:
        out[i0:i1, j0:j1] = sheet[i0 - di:i1 - di, j0 - dj:j1 - dj]
    return out


def join(airport, law, maps: _t.Mapping[tuple, _um.UndersideMap],
         sets: _t.Mapping[str, _um.Layers]) -> dict:
    """``maps`` with every recognised composite's sheet members joined into
    one map (module doc), keyed by the union of their rows; ``sets`` the
    origin sets' whole plans (``unit_underside._set_layers``)."""
    from types import SimpleNamespace

    from .footprint_unit import _wall_base
    from .unit_underside import _law, _near_airside, unit_population
    part = getattr(airport, "partition", None)
    if part is None or not maps or not sets:
        return dict(maps)
    unit_of = {str(c.id): str(c.unit) for c in getattr(airport, "clusters", None) or ()}
    by_set: dict[str, list[tuple]] = {}
    for key, m in maps.items():
        if m.layers.step == _um.CELL_M and m.unit in unit_of:
            by_set.setdefault(unit_of[m.unit], []).append(key)
    pids_of = {key: pids for key, _cid, pids in unit_population(airport)}
    parts = {p.pid: p for u in part.units for mm in u.members for p in mm.parts}
    many = dem_many(airport.dem)
    _ny, _band, storey, wall_min = _law(law)
    out = dict(maps)
    for uid, keys in sorted(by_set.items()):
        g = sets.get(uid)
        sheet = is_composite(g, many) if g is not None and g.step == _um.CELL_M else None
        if sheet is None:
            continue
        members = [k for k in keys if (_on(sheet, g, maps[k].layers) & maps[k].plan).any()]
        if not members:
            continue
        joined = _um.compose([maps[k].layers for k in members])
        rows = tuple(sorted({r for k in members for r in k if not str(r).startswith("@")}))
        cid = "+".join(sorted(maps[k].unit for k in members))
        m = _um.underside(joined, rows, cid, _near_airside(airport), storey,
                          sheet=_on(sheet, g, joined))
        pids = frozenset().union(*(pids_of.get(k, frozenset()) for k in members))
        base = _wall_base(un := SimpleNamespace(id=cid, pids=pids), (un,), parts, wall_min, {})
        for k in members:
            out.pop(k, None)
        out[rows] = _dc.replace(m, base=float(base), composite=True)
    return out
